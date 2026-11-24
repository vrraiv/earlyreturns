"""Presidential primary and caucus results by state from Wikipedia's "Results of the <year> <party> Party presidential
primaries" pages (DA-6): the fallback where a state office can't be read, and the only source used for caucuses, which
neither the FEC nor the states report.

Each page has, under a heading per state (and a "Primary" / "Caucus" subheading where a party held both), a table of
candidate, votes, percentage, delegates. Only those per-state tables are read; the pages' overview tables are not. The
Republican pages (2008, 2012, 2016, 2024) have them for nearly every state; the Democratic pages mostly don't (2016 has
13, the others none); the Democratic caucuses missing there (2008, and six of 2016) are read from each contest's
own page (CONTEST_PAGES).

The measure is taken from the table's header: "votes" (a popular or straw-poll vote), "state delegates" (caucuses that
report delegates elected, e.g. Colorado 2008), or "popular vote" (2016 Democratic tables). Nothing is converted.

Pages are fetched through governors.get_page and cached in data/raw/wikipedia_hist/<date>/ with their revision ids;
each row carries the page title and revision. Wikipedia text is CC BY-SA; much of it cites The Green Papers or the
states, and the per-state reference is not carried here.

Run:  python src/collect/primary_results_wiki.py      (writes nothing; prints the FEC comparison)
"""
import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402
from governors import get_page  # noqa: E402
from primary_polls import ABBR  # noqa: E402

INTERIM = ROOT / "data" / "interim"
PAGES = [(2008, "D"), (2008, "R"), (2012, "R"), (2016, "D"), (2016, "R"), (2020, "D"), (2020, "R"), (2024, "D"), (2024, "R")]
STATE = {**{k.lower(): v for k, v in ABBR.items()}, "washington d.c.": "DC", "washington, d.c.": "DC",
         "district of columbia": "DC", "puerto rico": "PR", "us virgin islands": "VI", "u.s. virgin islands": "VI",
         "virgin islands": "VI", "guam": "GU", "american samoa": "AS", "northern mariana islands": "MP",
         "northern marianas": "MP"}
NOT_CAND = re.compile(r"^total|^uncommitted|uncommit|noncommit|^other|write|scatter|none of|no preference|blank|void|"
                      r"inactive|invalid|"
                      r"undecided|^unprojected|^not on|^over|^under", re.I)


def title(cycle, party):
    return f"Results of the {cycle} {'Democratic' if party == 'D' else 'Republican'} Party presidential primaries"


def num(x):
    # footnotes, thousands commas, percent signs and invisible formatting marks (U+2066 in the 2024 Virginia table)
    x = re.sub(r"\[[^\]]*\]", "", str(x))
    x = re.sub(r"[^\d.\-]", "", x.replace(",", ""))
    try:
        return float(x) if re.search(r"\d", x) else None
    except ValueError:
        return None


def state_in(text):
    t = re.sub(r"\[[^\]]*\]", "", text or "").strip().lower()
    t = re.sub(r"\s*\((primary|caucus(es)?|convention|state convention)\)", "", t)
    for name in sorted(STATE, key=len, reverse=True):
        if t == name or t.startswith(name + " "):
            return STATE[name]
    return None


def kind_in(text):
    t = (text or "").lower()
    return "caucus" if "caucus" in t else "convention" if "convention" in t else "primary" if "primar" in t else None


def tables(cycle, party):
    """One dict per per-state table: heading path, state, contest kind, header text, the table element."""
    html, rev = get_page(title(cycle, party))
    soup = BeautifulSoup(html, "html.parser")
    path = {}
    out = []
    for el in soup.find_all(["h2", "h3", "h4", "table"]):
        if el.name != "table":
            lvl = int(el.name[1])
            path = {k: v for k, v in path.items() if k < lvl}
            path[lvl] = el.get_text(" ", strip=True)
            continue
        if el.find_parent("table") is not None:
            continue
        ths = [th.get_text(" ", strip=True) for th in el.find_all("th")[:12]]
        hdr = " ".join(ths)
        if "Candidate" not in hdr or not re.search(r"Votes|Popular vote|State delegates", hdr):
            continue
        heads = [path[k] for k in sorted(path)]
        st = next((state_in(h) for h in reversed(heads) if state_in(h)), None)
        kind = next((kind_in(h) for h in reversed(heads) if kind_in(h)), None)
        cap = el.find("caption")
        if cap is not None:
            st = state_in(cap.get_text(" ", strip=True)) or st
            kind = kind_in(cap.get_text(" ", strip=True)) or kind
        out.append({"cycle": cycle, "party": party, "heading": " > ".join(heads), "state": st, "contest": kind,
                    "header": hdr, "table": el, "page": title(cycle, party), "revision": rev})
    return out


def rows_of(t):
    """Candidate rows of one per-state table: name, value (votes or delegates), percentage, line kind."""
    hdr = t["header"]
    # Iowa and Nevada Democrats 2020 report a first and a final alignment, then delegate equivalents: the first
    # column, the first alignment, is read
    measure = "state delegates" if re.search(r"State delegates", hdr) and "Votes" not in hdr else \
        "first alignment" if re.search(r"(Initial|First) alignment", hdr) else \
        "popular vote" if "Popular vote" in hdr else "votes"
    out = []
    for tr in t["table"].find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        # some tables put a colour swatch cell before the name (2016 Minnesota Republicans)
        if cells and len(cells[0]) <= 1:
            cells = cells[1:]
        if len(cells) < 3 or cells[0] == "Candidate" or tr.find("th") and not tr.find("td"):
            continue
        name = re.sub(r"\[[^\]]*\]", "", cells[0])
        name = re.sub(r"\s*\(\s*(withdrawn|withdrew|suspended|incumbent)[^)]*\)", "", name, flags=re.I).strip(" *")
        nums = [num(c) for c in cells[1:]]
        # the value is the first number not printed as a percentage; the percentage is the cell after it (printed
        # with or without a % sign)
        vi = next((i for i, (v, c) in enumerate(zip(nums, cells[1:])) if v is not None and "%" not in c), None)
        if vi is None or not name:
            continue
        value = nums[vi]
        pcts = [nums[vi + 1]] if vi + 1 < len(nums) and nums[vi + 1] is not None and nums[vi + 1] <= 100 else []
        if re.match(r"^total", name, re.I):
            out.append({"candidate_name": name, "value": value, "pct": pcts[0] if pcts else None, "line": "total",
                        "measure": measure})
            continue
        line = "uncommitted" if re.search("uncommit|noncommit|uninstructed", name, re.I) else "other" if NOT_CAND.search(name) else "candidate"
        out.append({"candidate_name": name, "value": value, "pct": pcts[0] if pcts else None, "line": line,
                    "measure": measure})
    return out


def wiki_results():
    rows = []
    for cycle, party in PAGES:
        for i, t in enumerate(tables(cycle, party)):
            for r in rows_of(t):
                rows.append({**{k: t[k] for k in ("cycle", "party", "state", "contest", "heading", "page", "revision")},
                             "table_no": i, **r})
    w = pd.DataFrame(rows)
    # check: each table's values against its own percentages. Where shares computed from the values miss the
    # table's percentages by more than 5 points the values are not what the header says (delegate counts in the
    # American Samoa 2012, Wyoming 2016 and Guam 2024 tables), and the measure is marked unclear
    k = ["cycle", "party", "table_no"]
    lines = w.line != "total"
    calc = 100 * w.value / w[lines].groupby(k).value.transform("sum")
    gap = (calc - w.pct).abs().where(lines)
    worst = gap.groupby([w.cycle, w.party, w.table_no]).transform("max")
    w.loc[worst > 5, "measure"] = "unclear"
    return w


# Democratic caucuses with no per-state table on the cycle's results page: read from the contest's own page.
# measure: from the table's header where the page bears it out; where the page says what the count is and the header
# doesn't, the page's (with its wording in the note); where neither settles it, "unclear".
CONTEST_PAGES = {
    (2008, "IA"): ("caucus", "state delegate equivalents", None),
    (2008, "NV"): ("caucus", "county delegates", None),
    (2008, "AK"): ("caucus", "votes", None),
    (2008, "CO"): ("caucus", "votes", None),
    (2008, "ID"): ("caucus", "votes", None),
    (2008, "KS"): ("caucus", "votes", None),
    (2008, "MN"): ("caucus", "votes", None),
    (2008, "ND"): ("caucus", "unclear", "the table says precinct delegates; the page describes secret ballots and gives no turnout"),
    (2008, "NE"): ("caucus", "votes", None),
    (2008, "WA"): ("caucus", "precinct delegates", None),
    (2008, "ME"): ("caucus", "unclear", "the table says votes; the page does not say what its 3,500 total counts"),
    (2008, "HI"): ("caucus", "votes", None),
    (2008, "WY"): ("caucus", "votes", "the page: most sites used secret ballots, which were counted"),
    (2008, "NM"): ("caucus", "votes", "a party-run primary, kept under the FEC's label (caucus) so it joins the calendar and polls"),
    (2016, "IA"): ("caucus", "state delegate equivalents", None),
    (2016, "NV"): ("caucus", "county delegates", None),
    (2016, "KS"): ("caucus", "votes", None),
    (2016, "ME"): ("caucus", "unclear", "the table says count; the page does not say what its 3,500 total counts"),
    (2016, "ID"): ("caucus", "votes", None),
    (2016, "WA"): ("caucus", "legislative district delegates", "the table says count; the page gives about 230,000 participants and the shares as legislative district delegates"),
    (2016, "WY"): ("caucus", "county delegates", "the table says count; the page gives the shares as county delegates"),
}


PARTY_RUN_PAGES = {(2008, "NM")}   # pages titled "... presidential primary"


def contest_page_title(cycle, st):
    from primary_polls import ABBR
    name = {v: k for k, v in ABBR.items()}[st]
    kind = "primary" if (cycle, st) in PARTY_RUN_PAGES else "caucuses"
    return f"{cycle} {name} Democratic presidential {kind}"


def contest_page_results():
    """The first results table (a Candidate column, then the count, then the percentage) on each CONTEST_PAGES page."""
    out = []
    for (cycle, st), (kind, measure, why) in CONTEST_PAGES.items():
        t = contest_page_title(cycle, st)
        html, rev = get_page(t)
        soup = BeautifulSoup(html, "html.parser")
        tab = next(x for x in soup.find_all("table") if x.find_parent("table") is None
                   and "infobox" not in " ".join(x.get("class", []))
                   and any(th.get_text(" ", strip=True) == "Candidate" for th in x.find_all("th")[:12])
                   and not re.search(r"Money|Sept\.", x.get_text(" ")[:400]))
        for tr in tab.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c not in ("", "Democratic", "Democratic (DFL)")]   # party columns
            if len(cells) < 3 or cells[0] in ("Candidate", "Party") or tr.find("th") and not tr.find("td"):
                continue
            name = re.sub(r"\[[^\]]*\]", "", cells[0]).strip(" *")
            value = num(cells[1])
            if value is None or re.match(r"^total", name, re.I):
                continue
            line = "uncommitted" if re.search("uncommit", name, re.I) else "other" if NOT_CAND.search(name) else "candidate"
            out.append({"cycle": cycle, "party": "D", "state": st, "contest": kind, "heading": t, "page": t,
                        "revision": rev, "table_no": 0, "candidate_name": name, "value": value,
                        "pct": num(cells[2]) if "%" in cells[2] else None, "line": line, "measure": measure,
                        "measure_note": why, "party_run": (cycle, st) in PARTY_RUN_PAGES})
    return pd.DataFrame(out)


def calendar_2024():
    """The 2024 contest calendar from the "2024 <party> Party presidential primaries" pages' delegate table (date,
    delegates, contest): one row per party, state and contest. Contests outside the states, DC and PR are dropped."""
    out = []
    for party in ("D", "R"):
        t = f"2024 {'Democratic' if party == 'D' else 'Republican'} Party presidential primaries"
        html, rev = get_page(t)
        soup = BeautifulSoup(html, "html.parser")
        tab = next(x for x in soup.find_all("table") if "Total delegates" in re.sub(r"\s+", " ", x.get_text(" "))
                   and "caucus" in x.get_text())
        date, cancelled = None, False
        for tr in tab.find_all("tr")[1:]:
            cells = [re.sub(r"\[[^\]]*\]", "", c.get_text(" ", strip=True)).strip() for c in tr.find_all(["td", "th"])]
            if not cells:
                continue
            m = re.match(r"(January|February|March|April|May|June|July|August)\s+(\d{1,2})", cells[0])
            if m:
                date, cancelled = pd.Timestamp(f"{m.group(1)} {m.group(2)} 2024").date(), False
            elif len(cells) >= 3:
                # a row of its own whose date cell is not a date ('Cancelled', 'None'): no date, and not the
                # previous row's (rows continuing a spanned date have only two cells)
                date, cancelled = None, bool(re.search(r"cancel|none", cells[0], re.I))
            text = cells[-1]
            st = state_in(re.sub(r"\s*(primary|primaries|caucus(es)?|convention|\(.*?\)).*$", "", text, flags=re.I))
            kind = "cancelled" if cancelled else kind_in(text)
            if st is None or kind is None:
                continue
            out.append({"cycle": 2024, "state": st, "party": party, "contest": kind, "date": date,
                        "party_run": "party-run" in text.lower(), "fec_text": text,
                        "source": f"Wikipedia, {t} (revision {rev})"})
    c = pd.DataFrame(out)
    # cancelled Democratic primaries the delegate table leaves out (Biden the only candidate to file)
    add = [{"cycle": 2024, "state": st, "party": "D", "contest": "cancelled", "date": None, "party_run": False,
            "fec_text": None, "source": why} for st, why in
           (("DE", "Delaware Department of Elections public notice, 2024-03-19 (primary_results_states.py)"),
            ("FL", "Florida's official results extract has no Democratic presidential contest"))
           if not ((c.state == st) & (c.party == "D")).any()]
    c = pd.concat([c, pd.DataFrame(add)], ignore_index=True)
    for (st, party), (kind, party_run, why) in CAL_2024_FIX.items():
        i = c.index[(c.state == st) & (c.party == party)]
        c.loc[i, "contest"], c.loc[i, "party_run"] = kind, party_run
        c.loc[i, "source"] += f"; corrected: {why}"
    return c


# The 2024 table's labels corrected from the state offices (primary_results_states.py)
CAL_2024_FIX = {
    ("KY", "R"): ("primary", False, "a state-run primary in the State Board of Elections' certified results; the table says caucuses"),
    ("MO", "D"): ("primary", True, "run by the Missouri Democratic Party"),
    ("ND", "D"): ("primary", True, "run by the Democratic-NPL"),
    ("AK", "R"): ("primary", True, "run by the Alaska Republican Party"),
    ("AK", "D"): ("primary", True, "run by the Alaska Democratic Party"),
    ("DC", "R"): ("primary", True, "run by the DC Republican Party"),
    ("PR", "R"): ("primary", True, "run by the party"),
    ("PR", "D"): ("primary", True, "run by the party (counted by the CEE)"),
}


def compare_fec(w):
    """Each Wikipedia primary candidate line against the FEC's votes for the same state, party and surname."""
    fec = pd.read_csv(INTERIM / "primary_results.csv")
    fec = fec[fec.line == "candidate"].copy()
    sur = lambda n: re.sub(r"[^a-z]", "", str(n).split()[-1].lower()) if str(n).split() else ""
    fec["sur"] = fec.candidate_name.map(sur)
    w = w[(w.line == "candidate") & w.measure.isin(["votes", "popular vote"]) & (w.contest != "caucus")
          & (w.cycle <= 2020)].copy()
    w["sur"] = w.candidate_name.map(sur)
    # two candidates of one surname on a ballot (Arizona 2012: Rick and Al "Dick" Perry): match on the first initial too
    for d in (w, fec):
        d["ini"] = d.candidate_name.astype(str).str.replace('"', "").str.strip().str[:1].str.lower()
        d["n_sur"] = d.groupby(["cycle", "party", "state", "sur"]).sur.transform("size")
    w["ini"] = w.ini.where(w.n_sur > 1, "")
    fec["ini"] = fec.ini.where(fec.n_sur > 1, "")
    m = w.merge(fec[["cycle", "party", "state", "sur", "ini", "votes", "rcv_round"]],
                on=["cycle", "party", "state", "sur", "ini"], how="left")
    m = m[m.rcv_round.fillna("").isin(["", "first"])]
    m["diff"] = (m.value - m.votes).abs()
    m["result"] = pd.cut(m["diff"].fillna(-1), [-2, -0.5, 0.5, 100, 1e12],
                         labels=["no FEC line", "exact", "within 100", "differs"])
    print("Wikipedia per-state primary tables against the FEC (candidate lines, votes):")
    print(pd.crosstab([m.cycle, m.party], m.result).to_string())
    return m


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    w = wiki_results()
    print(w.groupby(["cycle", "party"]).agg(tables=("table_no", "nunique"), states=("state", "nunique"),
                                           no_state=("state", lambda s: s.isna().sum())).to_string())
    print(w.groupby(["cycle", "party", "measure"]).size().to_string())
    compare_fec(w)
    return w


if __name__ == "__main__":
    main()
