"""Presidential primary polls and the candidate timeline they are judged against (DA-6).

Candidate timeline (data/interim/primary_candidates.csv): every candidate in the candidate tables of Wikipedia's
"<year> <Democratic|Republican> Party presidential primaries" pages, 2008 to 2024, fetched through
governors.get_page (cached in data/raw/wikipedia_hist/, revision id in every row). Dates kept separately:
  exploratory   exploratory committee formed, where the table gives it
  announced     campaign announced (the 2008 tables give none: read from each campaign article, CAMPAIGN_2008)
  suspended     campaign suspended or withdrawn; for a candidate who lost at the convention, that date
  secured       nomination secured (nominees)
Each date is labelled by the words before it in its cell ("Exploratory committee:", "Withdrew:", "Secured
nomination:", "Lost nomination:") or else by its column's header. Birth dates are left out by year.
Minor candidates listed only in "Other candidates" bullet lists (2024) are added with their withdrawal date only.

Polls (data/interim/primary_polls.csv), one row per question and candidate:
  2008         Wikipedia (CC BY-SA): the two nationwide polling pages (wide tables and the two- and three-way
               sections; acceptability and candidate-quality tables left out), and the statewide pages read from
               each poll's "Highlights" text (WIKI_STATES_2008: the Democratic page at its last full revision,
               2008-02-07). Democratic state polls taken after that revision: 538's raw_polls.csv late polls, top
               two candidates only (notes say so). Each state's "actual result" row is checked against the FEC.
  2020, 2024   538's archived primary poll file (538_wayback/president_primary_polls_historical.csv, Feb 2025
               capture, CC BY): every poll of the cycle, every question, all candidates, state and national.
HuffPost Pollster's 2012 (Republican) and 2016 primary polls, state and national, go to a separate file,
data/interim/primary_polls_huffpost.csv, because Pollster licensed its data CC BY-NC-SA 3.0 ("If you use our API,
please attribute it. Link back to our site", the API page; saved as licence_api_page.html beside the raw files),
which cannot be relicensed under this project's CC BY-SA (LICENSE-DATA.md lists the file as not covered). One
archived file per contest, chosen by the rules in hp_snapshot(); file_rule 3 marks a contest whose only capture
may predate the contest, so its last polls can be missing (Georgia's 2016 Republican file was captured in
November 2015). Pollster's files give one row per poll and population with a column per candidate surname; each
row becomes a question here. Undecided and Other are kept as columns, not as candidates.
Nothing is dropped. Poll URLs are left out (they would double the file); the 538 archive has them by poll_id.
538's own `hypothetical` flag is kept as hypothetical_538 but not used: it is a ballot test
(the question is hypothetical unless every candidate is confirmed on the ballot; FiftyPlusOne's readme and 538's
polls policy), so it marks every national primary poll in 2024 and was applied more loosely in 2020 (DA-6 card,
planning/plan.js).
Instead each row carries the candidate's status on the question's end date, from the timeline:
  running       announced on or before the end date, not yet suspended
  exploratory   exploratory committee formed, not yet announced
  not_yet       in the timeline, but neither announced nor exploring by the end date
  withdrawn     suspended before the end date
  not_running   not in that cycle and party's timeline at all (never ran, e.g. Michelle Obama)
  unknown       in the timeline with no announcement date (Keyes and Cox in 2008; minor 2024 candidates)
and each question carries counts of its named candidates by status (q_running, q_exploratory, q_not_yet,
q_withdrawn, q_not_running, q_unknown). Which statuses a "real field" allows is decided later (PP-3, PP-7), not here.

Candidates are matched to the timeline by surname, with the first initial (or a listed nickname) to confirm.

Run:  python src/collect/primary_polls.py
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, ROOT, SESSION, fetch, latest, raw_dir  # noqa: E402
from downballot import STATE_ABBR  # noqa: E402
from governors import get_page  # noqa: E402

INTERIM = ROOT / "data" / "interim"
PARTY_NAME = {"D": "Democratic", "R": "Republican"}
CYCLES = [2008, 2012, 2016, 2020, 2024]
ABBR = {**STATE_ABBR, "District of Columbia": "DC"}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}
DATE = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)"
                  r"\s+(?:(\d{1,2}),\s*)?(\d{4})")
NICK = {("william", "bill"), ("robert", "bob"), ("joseph", "joe"), ("richard", "dick"), ("michael", "mike"),
        ("james", "jim"), ("lawrence", "larry"), ("thomas", "tom"), ("benjamin", "ben"), ("christopher", "chris"),
        ("edward", "ed"), ("frederick", "fred"), ("newton", "newt"), ("willard", "mitt"), ("rafael", "ted"),
        ("charles", "buddy")}
SUFFIX = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
# dates the candidate tables leave out, entered by hand with their source
OVERRIDES = {(2008, "D", "hillary-clinton"): {"suspended": "2008-06-07", "note": "suspended date from the page's text "
                                              "(conceded and endorsed Obama), as in campaign_calendar.py"}}
# 2008: the primaries pages give no announcement dates, so they are read from each candidate's "<name> 2008
# presidential campaign" article (infobox, or the lead where the infobox has none) and entered here by hand with the
# article's revision. key: (announced, exploratory committee, revision, note)
CAMPAIGN_2008 = {
    ("D", "barack-obama"): ("2007-02-10", None, 1387444957, "infobox"),
    ("D", "bill-richardson"): ("2007-05-21", None, 1337519140, "infobox"),
    ("D", "chris-dodd"): ("2007-01-11", None, 1387455541, "lead: launched on January 11, 2007"),
    ("D", "dennis-kucinich"): ("2006-12-11", None, 1386687508,
                               "text: announced in a speech on December 11, 2006 (the lead says the campaign began December 12)"),
    ("D", "hillary-clinton"): ("2007-01-20", None, 1387311704, "infobox"),
    ("D", "joe-biden"): ("2007-01-07", None, 1387225521, "infobox: announced January 7 on Meet the Press, launched January 31"),
    ("D", "john-edwards"): ("2006-12-28", None, 1387472252, "infobox"),
    ("D", "mike-gravel"): ("2006-04-17", None, 1387324927, "infobox"),
    ("D", "tom-vilsack"): ("2006-11-30", "2006-11-09", 1381374535,
                           "lead: formal announcement November 30, 2006; filed with the FEC November 9 (entered as exploratory)"),
    ("R", "alan-keyes"): (None, None, 1385915083, "text: entered in late September 2007, no day given (left blank)"),
    ("R", "duncan-hunter"): ("2007-01-01", "2006-10-30", 1387304707,
                             "text: announced in January 2007, month only (entered as the 1st); exploratory committee October 30, 2006"),
    ("R", "fred-thompson"): ("2007-09-05", None, 1387308487, "infobox"),
    ("R", "jim-gilmore"): ("2007-04-26", "2007-01-10", 1366886283, "text: exploratory committee January 10, announced April 26, 2007"),
    ("R", "john-mccain"): ("2007-02-28", None, 1387445813, "infobox: informal announcement February 28, formal April 25, 2007"),
    ("R", "mike-huckabee"): ("2007-01-28", None, 1387324932, "infobox"),
    ("R", "mitt-romney"): ("2007-02-13", None, 1387406283, "infobox"),
    ("R", "ron-paul"): ("2007-03-12", None, 1387331942, "infobox"),
    ("R", "rudy-giuliani"): ("2007-02-05", None, 1387332181, "infobox"),
    ("R", "sam-brownback"): ("2007-01-20", "2006-12-04", 1387432452, "lead: exploratory committee December 4, 2006; announced January 20, 2007"),
    ("R", "tom-tancredo"): ("2007-04-02", None, 1319548861, "lead"),
    ("R", "tommy-thompson"): ("2007-04-01", "2006-11-16", 1345339539, "text: exploratory committee November 16, 2006; entered April 1, 2007"),
}
STATUSES = ["running", "exploratory", "not_yet", "withdrawn", "not_running", "unknown"]


def fold(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def name_parts(name):
    """(first, surname) in folded form; suffixes dropped, 'de la Fuente' and 'de Blasio' kept whole."""
    toks = [t for t in re.sub(r"[\"'“”].*?[\"'“”]", " ", fold(name)).replace(",", " ").split() if t not in SUFFIX]
    toks = [t for t in toks if not re.fullmatch(r"[a-z]\.", t)] or toks   # middle initials
    i = len(toks) - 1
    while i > 1 and toks[i - 1] in ("de", "la", "van", "von", "o"):
        i -= 1
    return (toks[0] if toks else ""), " ".join(toks[i:])


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")


def to_date(m, cycle):
    month, day, year = m.group(1), m.group(2), int(m.group(3))
    if year < cycle - 5 or year > cycle + 1:          # birth dates, office terms
        return None
    return pd.Timestamp(year, MONTHS[month], int(day) if day else 1)


def cell_name(td):
    for s in td.select('[style*="display:none"]'):   # sort keys such as "Clinton, Hillary"
        s.decompose()
    a = [x for x in td.find_all("a") if not str(x.get("href", "")).startswith("/wiki/File:")
         and x.get_text(strip=True)]
    return (a[0].get_text(" ", strip=True) if a else td.get_text(" ", strip=True)).strip()


def header_kind(h):
    h = h.lower()
    if "announc" in h:
        return "announced"
    if "suspend" in h or "withdr" in h or "lost nomination" in h:
        return "suspended"
    return None


LABELS = [("exploratory", "exploratory"), ("secured", "secured"), ("withdr", "suspended"), ("lost nomination", "suspended"),
          ("suspend", "suspended"), ("announc", "announced")]


def parse_row(cells, headers, cycle):
    out = {}
    aligned = len(cells) == len(headers)
    for i, td in enumerate(cells[1:], start=1):
        text = td.get_text(" ", strip=True)
        if "(age" in text:
            continue
        for m in DATE.finditer(text):
            d = to_date(m, cycle)
            if d is None or "erroneous" in text[m.end():m.end() + 20].lower():   # Gingrich 2012: "May 1 (erroneously)"
                continue
            before = text[max(0, m.start() - 40):m.start()].lower()
            kind = next((k for w, k in LABELS if w in before.split(")")[-1]), None)
            if kind is None and aligned:
                kind = header_kind(headers[i])
            if kind is None:
                kind = "announced" if "announced" not in out else "suspended"
            if kind not in out and not m.group(2):
                out.setdefault("month_only", []).append(kind)
            out.setdefault(kind, d)
    return out


def candidates():
    rows = []
    for cycle in CYCLES:
        for p in "DR":
            title = f"{cycle} {PARTY_NAME[p]} Party presidential primaries"
            html, rev = get_page(title)
            soup = BeautifulSoup(html, "html.parser")
            for s in soup.find_all("sup"):
                s.decompose()
            h2 = next(h for h in soup.find_all("h2") if h.get_text(strip=True).startswith("Candidates"))
            section, other = "", False
            for el in h2.find_all_next(["h2", "h3", "h4", "table", "ul"]):
                if el.name == "h2":
                    break
                if el.name in ("h3", "h4"):
                    other = el.name == "h4" and el.get_text(strip=True) == "Other candidates"
                    if el.name == "h3":
                        section = el.get_text(" ", strip=True)
                    continue
                if el.name == "ul":
                    if other:      # minor candidates: a bullet list with a withdrawal date and no announcement date
                        for li in el.find_all("li", recursive=False):
                            name = li.get_text(" ", strip=True).split(",")[0].strip()
                            m = re.search(r"withdrew\s+" + DATE.pattern, li.get_text(" ", strip=True))
                            sus = to_date(DATE.search(m.group(0)), cycle) if m else None
                            rows.append({"cycle": cycle, "party": p, "candidate": name, "candidate_key": slug(name),
                                         "section": section + " (other candidates)", "exploratory": None,
                                         "announced": None, "suspended": sus, "secured": None, "wiki_revision": rev})
                        other = False
                    continue
                trs = el.find_all("tr")
                if not trs:
                    continue
                headers = [c.get_text(" ", strip=True) for c in trs[0].find_all(["th", "td"])]
                if not headers or headers[0] not in ("Candidate", "Name"):
                    continue
                for tr in trs[1:]:
                    cells = tr.find_all(["td", "th"])
                    if len(cells) < 3:
                        continue
                    name = cell_name(cells[0])
                    if not name or name in ("Candidate", "Name"):
                        continue
                    d = parse_row(cells, headers, cycle)
                    rows.append({"cycle": cycle, "party": p, "candidate": name, "candidate_key": slug(name),
                                 "section": section, "exploratory": d.get("exploratory"), "announced": d.get("announced"),
                                 "suspended": d.get("suspended"), "secured": d.get("secured"), "wiki_revision": rev,
                                 "note": ("month only on the page (entered as the 1st): " + ", ".join(d["month_only"]))
                                 if d.get("month_only") else ""})
    df = pd.DataFrame(rows)
    df["note"] = df.note.fillna("")
    for (cy, p, key), o in OVERRIDES.items():
        i = df.index[(df.cycle == cy) & (df.party == p) & (df.candidate_key == key)]
        assert len(i) == 1, (cy, p, key)
        for k, v in o.items():
            df.loc[i, k] = v if k == "note" else pd.Timestamp(v)
    for (p, key), (ann, exp, rev, note) in CAMPAIGN_2008.items():
        i = df.index[(df.cycle == 2008) & (df.party == p) & (df.candidate_key == key)]
        assert len(i) == 1, key
        df.loc[i, "announced"] = pd.Timestamp(ann) if ann else None
        df.loc[i, "exploratory"] = pd.Timestamp(exp) if exp else None
        df.loc[i, "note"] = ("; ".join(x for x in [df.loc[i[0], "note"], f"announcement from the campaign article, "
                                                   f"revision {rev} ({note})"] if x))
    # the 2012 Republican page repeats its nominee and Ron Paul in a delegate table above the candidate tables
    df = df.sort_values(["cycle", "party", "candidate_key", "announced"]).drop_duplicates(
        ["cycle", "party", "candidate_key"], keep="first")
    for c in ["exploratory", "announced", "suspended", "secured"]:
        df[c] = pd.to_datetime(df[c]).dt.date
    df = df.sort_values(["cycle", "party", "announced", "candidate_key"], na_position="last")
    df.to_csv(INTERIM / "primary_candidates.csv", index=False)
    return df


def match_keys(polls, cands):
    """candidate_key for each (cycle, party, candidate_name); None where not in the timeline."""
    idx = {}
    for r in cands.itertuples():
        idx.setdefault((r.cycle, r.party, name_parts(r.candidate)[1]), []).append(r)
    out = {}
    for (cycle, party, name) in polls[["cycle", "party", "candidate_name"]].drop_duplicates().itertuples(index=False):
        first, sur = name_parts(name)
        hits = idx.get((cycle, party, sur), [])
        hit = None
        if len(fold(name).split()) == 1:          # surname only: unambiguous, or every candidate of that surname
            out[(cycle, party, name)] = hits[0].candidate_key if len(hits) == 1 else \
                ("AMBIGUOUS:" + "|".join(r.candidate_key for r in hits) if hits else None)
            continue
        for r in hits:
            f2 = name_parts(r.candidate)[0]
            if f2[:1] == first[:1] or (first, f2) in NICK or (f2, first) in NICK:
                hit = r.candidate_key
        out[(cycle, party, name)] = hit
    return out


def status(end, c):
    if c is None:
        return "not_running"
    if pd.notna(c["suspended"]) and end > c["suspended"]:
        return "withdrawn"
    if pd.isna(c["announced"]):
        return "exploratory" if pd.notna(c["exploratory"]) and end >= c["exploratory"] else "unknown"
    if end >= c["announced"]:
        return "running"
    if pd.notna(c["exploratory"]) and end >= c["exploratory"]:
        return "exploratory"
    return "not_yet"


QCOLS = ["q_" + x for x in STATUSES]


def add_status(a, cands):
    """candidate_key, cand_status on the end date, and per-question counts by status and of answers."""
    keys = match_keys(a, cands)
    a["candidate_key"] = [keys[k] for k in zip(a.cycle, a.party, a.candidate_name)]
    cinfo = {(r["cycle"], r["party"], r["candidate_key"]): r for r in cands.to_dict("records")}
    # a bare surname shared by two candidates (2008 "Thompson": Fred or Tommy): the one running on the end date,
    # else left unmatched
    amb = a.candidate_key.astype(str).str.startswith("AMBIGUOUS:")
    for i in a.index[amb]:
        opts = a.at[i, "candidate_key"].split(":", 1)[1].split("|")
        live = [k for k in opts if status(a.at[i, "end_date"], cinfo[(a.at[i, "cycle"], a.at[i, "party"], k)]) == "running"]
        a.at[i, "candidate_key"] = live[0] if len(live) == 1 else None
    a["cand_status"] = [status(e, cinfo.get((c, p, k)) if k else None)
                        for e, c, p, k in zip(a.end_date, a.cycle, a.party, a.candidate_key)]
    a["candidate_key"] = a.candidate_key.fillna(a.candidate_name.map(slug))
    q = pd.crosstab(a.question_id, a.cand_status).reindex(columns=STATUSES, fill_value=0).add_prefix("q_")
    a = a.join(q, on="question_id")
    a["n_answers"] = a.groupby("question_id").question_id.transform("size")
    return a


def polls_538(cands):
    a = pd.read_csv(latest("538_wayback", "president_primary_polls_historical.csv"), low_memory=False)
    a["candidate_party"] = a.party.map({"DEM": "D", "REP": "R"})
    a = a[a.candidate_party.notna()].copy()
    # a few questions list a candidate of the other party (Trump in a Democratic question): the question's party is
    # the party of most of its candidates, and the outsider counts as not running in that primary
    share = a.groupby(["question_id", "candidate_party"]).pct.agg(["size", "sum"]).reset_index()
    share = share.sort_values(["question_id", "size", "sum"]).drop_duplicates("question_id", keep="last")
    a["party"] = a.question_id.map(share.set_index("question_id").candidate_party)   # ties (one each): larger share
    geo = a.state.map(lambda s: "US" if pd.isna(s) else ABBR.get(s))
    bad = a.state[geo.isna() & a.state.notna()].unique()
    assert len(bad) == 0, f"unmapped states: {bad}"
    a["geo"] = geo
    for c in ["start_date", "end_date", "election_date"]:
        a[c] = pd.to_datetime(a[c], format="mixed").dt.date
    a = add_status(a, cands)
    a["days_to_contest"] = pd.array([(e - d).days if pd.notna(e) else None for e, d in zip(a.election_date, a.end_date)],
                                    dtype="Int64")
    a["source"] = "538"
    out = a.rename(columns={"hypothetical": "hypothetical_538", "sponsors": "sponsor"})[
        ["cycle", "party", "geo", "stage", "poll_id", "question_id", "pollster", "pollster_rating_id", "sponsor",
         "partisan", "internal", "population", "sample_size", "tracking", "start_date", "end_date", "election_date",
         "days_to_contest", "notes", "hypothetical_538", "candidate_key", "candidate_name", "candidate_party", "answer", "pct",
         "cand_status", "n_answers"] + QCOLS + ["source"]]
    return out.sort_values(["cycle", "party", "end_date", "poll_id", "question_id", "pct"],
                           ascending=[True, True, True, True, True, False])


WIKI_NATIONAL_2008 = {"D": "Nationwide opinion polling for the 2008 Democratic Party presidential primaries",
                      "R": "Nationwide opinion polling for the 2008 Republican Party presidential primaries"}
WIKI_SKIP = re.compile(r"accept|qualit|ideolog|other polls|see also|notes|references|statewide|state primary", re.I)
WIKI_NOT_CAND = re.compile(r"poll|date|moe|margin|sample|other|undeci|undeclared|none|lead|question|^%|candidate$|"
                           r"no opinion|unsure|someone|wouldn|n/a|don.?t know|^know$|not sure|refused|not applicable|"
                           r"no one|not voting|will not vote|miscellaneous|too early|undisclosed|neither|uncommit", re.I)
# misspellings in the 2008 tables
WIKI_SPELLING = {"Sam Browback": "Sam Brownback", "Dennis Kucicinich": "Dennis Kucinich", "Dennis Kucincih": "Dennis Kucinich",
                 "Mike Huckbee": "Mike Huckabee", "Sandford": "Sanford"}


def wiki_name(x):
    x = re.sub(r"^VOL-\s*", "", str(x)).strip()
    return WIKI_SPELLING.get(x, x)


def wiki_dates(text, year):
    """Wikipedia's date cells, with the section's year where the cell has none ("Aug. 30 - Sep. 5")."""
    from wiki_polls import parse_dates
    t = str(text).replace("\xa0", " ")
    # day first ("4 January -7, 2007", "29 January - 4 February 2007") to month first
    t = re.sub(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|"
               r"December)\b", r"\2 \1", t)
    if not re.search(r"\d{4}", t) and year:
        t = f"{t}, {year}"
    a, b = parse_dates(t)
    if a is None:                      # month only ("Jan 2007"): the whole month is unknown, take its last day
        m = re.match(r"([A-Za-z]+)\.?\s+(\d{4})$", t.strip())
        if m and m.group(1)[:3].lower() in [x[:3].lower() for x in MONTHS]:
            mo = [x[:3].lower() for x in MONTHS].index(m.group(1)[:3].lower()) + 1
            b = (pd.Timestamp(int(m.group(2)), mo, 1) + pd.offsets.MonthEnd(0)).date()
            a = b.replace(day=1)
    return a, b


def wiki_pct(x):
    m = re.match(r"^\s*<?\s*(\d+(?:\.\d+)?)\s*%?\s*$", str(x).replace("\xa0", " "))
    return float(m.group(1)) if m else None


def table_grid(table):
    """A wikitable as rows of cell texts, with rowspan and colspan cells repeated where they span."""
    grid, carry = [], {}
    for tr in table.find_all("tr"):
        row, col = [], 0
        cells = tr.find_all(["th", "td"])
        it = iter(cells)
        while True:
            if col in carry and carry[col][0] > 0:
                n, txt = carry[col]
                row.append(txt)
                carry[col] = (n - 1, txt)
                col += 1
                continue
            c = next(it, None)
            if c is None:
                break
            txt = c.get_text(" ", strip=True)
            rs, cs = int(c.get("rowspan", 1) or 1), int(c.get("colspan", 1) or 1)
            for _ in range(cs):
                row.append(txt)
                if rs > 1:
                    carry[col] = (rs - 1, txt)
                col += 1
        while col in carry and carry[col][0] > 0:     # spans running past the row's last cell
            n, txt = carry[col]
            row.append(txt)
            carry[col] = (n - 1, txt)
            col += 1
        grid.append(row)
    return grid


def polls_wiki_2008_national():
    """2008 national primary polls from Wikipedia's two nationwide pages: wide tables (a column per candidate) and
    the pair tables of the two- and three-way sections. One question per table row."""
    rows = []
    for party, title in WIKI_NATIONAL_2008.items():
        html, rev = get_page(title)
        soup = BeautifulSoup(html, "html.parser")
        for x in soup.find_all("sup"):
            x.decompose()
        section, year, n = "", None, 0
        for el in soup.find_all(["h2", "h3", "table"]):
            if el.name in ("h2", "h3"):
                head = el.get_text(" ", strip=True)
                if el.name == "h2":
                    section = head
                else:
                    section = section.split(" / ")[0] + " / " + head
                y = re.findall(r"(19|20)(\d\d)", head)
                # "Before 2007" names no year of its own; sections without one keep their cells' years only
                year = None if head.startswith("Before") or not y else int("".join(y[-1]))
                continue
            if "wikitable" not in " ".join(el.get("class", [])) or WIKI_SKIP.search(section):
                continue
            grid = table_grid(el)
            hdr = grid[0]
            if len(hdr) < 3:
                continue
            pair = "%" in hdr
            date_i = next((i for i, h in enumerate(hdr) if h.lower().startswith("date")), None)
            if date_i is None:
                continue
            cand_i = [i for i, h in enumerate(hdr) if (hdr[i + 1] == "%" if pair and i + 1 < len(hdr) else not pair)
                      and not WIKI_NOT_CAND.search(h)]
            need = max(cand_i + [date_i]) + (2 if pair else 1)
            for cells in grid[1:]:
                # some rows carry an extra "[data missing]" cell after the candidates; the columns up to the last
                # candidate still line up
                if len(cells) < need:
                    continue
                start, end = wiki_dates(cells[date_i], year)
                if end is None:
                    continue
                n += 1
                qid = f"wk-08-US-{party}-{n}"
                if pair:
                    named = [(cells[i], wiki_pct(cells[i + 1])) for i in range(len(hdr) - 1)
                             if hdr[i + 1] == "%" and not WIKI_NOT_CAND.search(hdr[i])]
                else:
                    named = [(h, wiki_pct(c)) for h, c in zip(hdr, cells) if not WIKI_NOT_CAND.search(h)]
                ss = next((cells[i] for i, h in enumerate(hdr) if "sample" in h.lower()), None)
                for name, v in named:
                    name = wiki_name(name)
                    if v is not None and name and not WIKI_NOT_CAND.search(name):
                        rows.append({"cycle": 2008, "party": party, "geo": "US", "poll_id": qid, "question_id": qid,
                                     "pollster": cells[0], "sample_size": ss, "start_date": start, "end_date": end,
                                     "notes": section, "candidate_name": name, "pct": v,
                                     "source": f"Wikipedia, {title}, revision {rev}"})
    return pd.DataFrame(rows)


# 2008 state polls. Republican: the current statewide page. Democratic: the state polls were moved to per-state
# articles on 2008-02-07 and later removed from them, so the page's last full revision (that day, before the move)
# is read: every state's polls up to Super Tuesday. Polls taken after that revision come from 538's raw_polls.csv
# late polls (top two candidates only, flagged).
WIKI_STATES_2008 = {"R": ("Statewide opinion polling for the 2008 Republican Party presidential primaries", None),
                    "D": ("Statewide opinion polling for the 2008 Democratic Party presidential primaries", 189814648)}
D_STATES_REVISION_DAY = pd.Timestamp("2008-02-07").date()
HIGHLIGHT = re.compile(r"([A-Z][A-Za-z.'\- ]+?)\s+(\d+(?:\.\d+)?)\s*%")


def polls_wiki_2008_states():
    """One question per poll row: the "Highlights" cell read as name-and-percent pairs. The first row of each state
    is the actual result: kept apart (returned second) to test the parser against the FEC's results."""
    from collections import Counter
    rows, results, dropped = [], [], Counter()
    for party, (title, oldid) in WIKI_STATES_2008.items():
        name = title + (f" (revision {oldid})" if oldid else "")
        html, rev = get_page(title, oldid=oldid, cache_name=name if oldid else None)
        soup = BeautifulSoup(html, "html.parser")
        for x in soup.find_all("sup"):
            x.decompose()
        state, n = None, 0
        for el in soup.find_all(["h2", "h3", "table"]):
            if el.name in ("h2", "h3"):
                state = ABBR.get(el.get_text(" ", strip=True)) if el.name == "h3" else None
                continue
            if state is None or "wikitable" not in " ".join(el.get("class", [])):
                continue
            grid = table_grid(el)
            hdr = [h.lower() for h in grid[0]]
            if not hdr or "highlights" not in hdr:
                continue
            si, di, hi = 0, next(i for i, h in enumerate(hdr) if h.startswith("date")), hdr.index("highlights")
            for cells in grid[1:]:
                if len(cells) <= hi:
                    continue
                src = cells[si]
                start, end = wiki_dates(cells[di].replace(" ,", ","), None)
                pairs = [(wiki_name(m.group(1).strip(" ,")), float(m.group(2))) for m in HIGHLIGHT.finditer(cells[hi])]
                pairs = [(a, v) for a, v in pairs if not WIKI_NOT_CAND.search(a)]
                if re.search(r"result", src, re.I):
                    results += [{"party": party, "geo": state, "candidate_name": a, "pct": v} for a, v in pairs]
                    continue
                if end is None or not pairs:
                    dropped[(party, "no date" if end is None else "no name-and-percent pairs")] += 1
                    continue
                n += 1
                qid = f"wk-08-{state}-{party}-{n}"
                pollster = re.split(r"\s*(Sampl|Margin|MoE)", src)[0].strip()
                ss = re.search(r"Sampl\w*\s*Size:?\s*([\d,]+)", src)
                for a, v in pairs:
                    rows.append({"cycle": 2008, "party": party, "geo": state, "poll_id": qid, "question_id": qid,
                                 "pollster": pollster, "sample_size": ss.group(1).replace(",", "") if ss else None,
                                 "start_date": start, "end_date": end, "notes": "", "candidate_name": a, "pct": v,
                                 "source": f"Wikipedia, {title}, revision {rev}"})
    print("2008 state poll rows skipped:", dict(dropped))
    return pd.DataFrame(rows), pd.DataFrame(results)


def polls_raw_2008_late():
    """538 raw_polls.csv late polls (top two only) for 2008 Democratic state contests, taken after the page revision
    (which cannot hold them)."""
    r = pd.read_csv(latest("538_github", "raw_polls.csv"), low_memory=False)
    r = r[(r.type_simple == "Pres-P") & (r.cycle == 2008) & r.race.str.contains("-D-P")].copy()
    r = r[pd.to_datetime(r.polldate).dt.date > D_STATES_REVISION_DAY]
    rows = []
    for x in r.itertuples():
        for k in (1, 2):
            rows.append({"cycle": 2008, "party": "D", "geo": x.location, "poll_id": f"raw-{x.poll_id}",
                         "question_id": f"raw-{x.question_id}", "pollster": x.pollster, "sample_size": x.samplesize,
                         "start_date": pd.to_datetime(x.polldate).date(), "end_date": pd.to_datetime(x.polldate).date(),
                         "notes": "late poll, top two candidates only (538 raw_polls.csv; poll date is its middle day)",
                         "candidate_name": getattr(x, f"cand{k}_name"), "pct": getattr(x, f"cand{k}_pct"),
                         "source": "538 raw_polls.csv"})
    return pd.DataFrame(rows)


def contest_dates(df):
    """election_date, stage and days_to_contest from the FEC calendar (primary_results.calendar) for state rows that
    lack them; national rows have no contest date."""
    from primary_results import calendar, snapshot     # primary_results imports this module: import here
    cal = calendar(snapshot())
    # where a party held two contests in a state (West Virginia Republicans 2008: a convention in February and a
    # primary in May), no single contest date is given: election_date is blank and stage names both
    g = cal.sort_values("date").groupby(["cycle", "party", "state"])
    key = pd.DataFrame({"date": g.date.first().where(g.size() == 1),
                        "contest": g.contest.agg(lambda x: "/".join(x))})
    df = df.copy()
    idx = list(zip(df.cycle, df.party, df.geo))
    df["election_date"] = [key.date.get(i) for i in idx]
    df["stage"] = [key.contest.get(i) for i in idx]
    df["days_to_contest"] = pd.array([(e - d).days if e is not None and pd.notna(e) else None
                                      for e, d in zip(df.election_date, df.end_date)], dtype="Int64")
    return df


def polls_2008(cands):
    nat = polls_wiki_2008_national()
    st, res = polls_wiki_2008_states()
    late = polls_raw_2008_late()
    a = pd.concat([nat, st, late], ignore_index=True)
    a["start_date"] = pd.to_datetime(a.start_date).dt.date
    a["end_date"] = pd.to_datetime(a.end_date).dt.date
    a = add_status(a, cands)
    a = contest_dates(a)
    a["hypothetical_538"] = None
    check_2008_states(a)
    if not (INTERIM / "primary_results.csv").exists():
        print("\n2008 parser test skipped: run src/collect/primary_results.py, then this script again")
        return a
    print("\n2008 parser test: each state's 'actual result' row against the FEC results (share points, abs diff)")
    fec = pd.read_csv(INTERIM / "primary_results.csv")
    fec = fec[(fec.cycle == 2008) & (fec.line == "candidate")].copy()
    fec["sur"] = fec.candidate_name.map(lambda x: name_parts(x)[1])
    res["sur"] = res.candidate_name.map(lambda x: name_parts(x)[1])
    m = res.merge(fec, left_on=["party", "geo", "sur"], right_on=["party", "state", "sur"], suffixes=("", "_fec"))
    m["diff"] = (m.pct - 100 * m.share).abs()
    print(f"  {len(m)} candidate results matched in {m.groupby(['party', 'geo']).ngroups} contests; "
          f"within 1 point: {(m['diff'] <= 1).mean():.0%}; largest gaps:")
    print(m.sort_values("diff", ascending=False).head(6)[["party", "geo", "candidate_name", "pct", "share"]]
          .to_string(index=False))
    return a


def check_2008_states(a):
    """538's raw_polls.csv late 2008 primary polls against the Wikipedia state polls: shares match = a poll of the same
    contest in the field that day (give or take one) with both candidates within a point."""
    w = a[(a.geo != "US") & a.source.str.startswith("Wikipedia")]
    r = pd.read_csv(latest("538_github", "raw_polls.csv"), low_memory=False)
    r = r[(r.type_simple == "Pres-P") & (r.cycle == 2008)].copy()
    r["party"] = r.race.str.extract(r"Pres-([DR])-P")[0]
    r["day"] = pd.to_datetime(r.polldate).dt.date
    shares, spans = {}, {}
    for x in w.itertuples():
        shares.setdefault(x.question_id, {})[name_parts(x.candidate_name)[1]] = x.pct
    for x in w.drop_duplicates("question_id").itertuples():
        spans.setdefault((x.party, x.geo), []).append((x.start_date or x.end_date, x.end_date, x.question_id))
    one = pd.Timedelta(days=1)

    def result(x):
        found = False
        for s0, e0, q in spans.get((x.party, x.location), []):
            if s0 - one <= x.day <= e0 + one:
                found = True
                a1, a2 = shares[q].get(name_parts(x.cand1_name)[1]), shares[q].get(name_parts(x.cand2_name)[1])
                if a1 is not None and a2 is not None and abs(a1 - x.cand1_pct) <= 1 and abs(a2 - x.cand2_pct) <= 1:
                    return "shares match"
        if x.party == "D" and x.day > D_STATES_REVISION_DAY:
            return "after the revision (taken from raw_polls)"
        return "in field, shares differ" if found else "not found"
    r["result"] = r.apply(result, axis=1)
    print("2008 cross-check: 538's raw_polls.csv late state polls against the Wikipedia state polls")
    print(pd.crosstab(r.party, r.result).to_string())


HP_HOST = "elections.huffingtonpost.com/pollster/"
HP_SOURCE = "huffpost_pollster"
HP_NOT_CANDIDATES = {"Undecided", "Other", "Not Voting", "Refused", "None", "Wouldn't Vote", "Someone else"}


def hp_contest(fname):
    """'2016-iowa-presidential-republican-caucus.csv' -> (2016, 'IA', 'R', 'caucus'); None if not a presidential
    primary chart (Senate and governor primaries share the folder)."""
    m = re.match(r"(\d{4})-(.+)\.csv$", fname)
    if not m:
        return None
    cycle, rest = int(m.group(1)), m.group(2)
    if cycle not in (2012, 2016) or not re.search(r"primary|caucus", rest):
        return None
    if re.search(r"senate|governor|house", rest):
        return None
    party = "R" if re.search(r"gop|republican", rest) else "D" if "democratic" in rest else None
    if party is None or (cycle == 2012 and party == "D"):
        return None
    words = re.sub(r"-?(presidential|republican|democratic|gop|primary|caucus)", "", rest).strip("-")
    geo = "US" if words == "national" else ABBR.get(words.replace("-", " ").title())
    if geo is None:
        raise ValueError(f"unmapped Pollster chart {fname}")
    return cycle, geo, party, "caucus" if "caucus" in rest else "primary"


def hp_api_contest(path):
    """'16-MI-Pres-DemPR/poll-responses-clean.tsv' -> (2016, 'MI', 'D'); None for other questions."""
    m = re.match(r"(\d\d)-([A-Z]{2})-Pres-(Dem|Rep)PR/poll-responses-clean\.tsv$", path)
    if not m or int(m.group(1)) not in (12, 16):
        return None
    geo = m.group(2)
    if geo != "US" and geo not in ABBR.values():
        raise ValueError(f"unmapped Pollster question {path}")
    return 2000 + int(m.group(1)), geo, "D" if m.group(3) == "Dem" else "R"


def cdx(prefix):
    for attempt in range(5):
        r = SESSION.get("https://web.archive.org/cdx/search/cdx", timeout=300,
                        params={"url": prefix, "matchType": "prefix", "filter": "statuscode:200",
                                "fl": "original,timestamp,length", "output": "json"})
        if r.status_code not in (429, 503, 504):
            break
        time.sleep(30 * (attempt + 1))
    r.raise_for_status()
    return [{"original": o, "timestamp": t, "length": int(n)} for o, t, n in r.json()[1:]]


def hp_snapshot():
    """One archived file per contest (cycle, state or US, party), chosen from every Wayback capture of Pollster's
    2012 and 2016 primary files:
      1. the API's poll-responses file for the question (pollster/api/v2/questions/<yy>-<geo>-Pres-<Dem|Rep>PR/),
         where archived: every capture of it postdates the cycle, and it adds question text and partisanship;
      2. else the chart CSV (pollster/<year>-<state>-...-primary.csv): its largest capture after July 1 of the cycle;
      3. else the chart CSV's latest capture, which may predate the contest and miss its last polls.
    The choice per contest is written to sources.json beside the files, with each capture's timestamp; the full
    capture listing to cdx_listing.json. Cached: the latest data/raw/huffpost_pollster/<date>/ with a sources.json
    is reused."""
    hits = sorted((RAW / HP_SOURCE).glob("*/sources.json"))
    if hits:
        return hits[-1].parent
    d = raw_dir(HP_SOURCE)
    caps = []
    for pre in ["2012-", "2016-", "api/v2/questions/12-", "api/v2/questions/16-"]:
        caps += cdx(HP_HOST + pre)
    opts = {}
    for c in caps:
        path = c["original"].split("/pollster/", 1)[-1].split("?")[0]
        if path.startswith("api/v2/questions/"):
            con = hp_api_contest(path[len("api/v2/questions/"):])
            if con:
                opts.setdefault(con, []).append({**c, "path": path, "rank": 1, "stage": None})
            continue
        con = hp_contest(path)
        if con is None:
            continue
        late = c["timestamp"][:8] >= f"{con[0]}0701"
        opts.setdefault(con[:3], []).append({**c, "path": path, "rank": 2 if late else 3, "stage": con[3]})
    chosen = {}
    for con, lst in sorted(opts.items()):
        rank = min(x["rank"] for x in lst)
        pool = [x for x in lst if x["rank"] == rank]
        pick = max(pool, key=lambda x: (x["length"], x["timestamp"])) if rank < 3 else \
            max(pool, key=lambda x: (x["timestamp"], x["length"]))
        stages = sorted({x["stage"] for x in lst if x["stage"]})
        fname = ("api-" + pick["path"].split("/")[3] + ".tsv") if rank == 1 else pick["path"]
        fetch(HP_SOURCE, fname, f"https://web.archive.org/web/{pick['timestamp']}id_/http://{HP_HOST}{pick['path']}")
        time.sleep(1)
        chosen["|".join(map(str, con))] = {"file": fname, "path": pick["path"], "timestamp": pick["timestamp"],
                                           "rule": rank, "chart_names_say": "/".join(stages)}
    # the licence, as the API page stated it (January 2017 capture)
    fetch(HP_SOURCE, "licence_api_page.html",
          "https://web.archive.org/web/20170126155740id_/http://elections.huffingtonpost.com/pollster/api")
    (d / "cdx_listing.json").write_text(json.dumps([c for lst in opts.values() for c in lst], indent=0))
    (d / "sources.json").write_text(json.dumps(chosen, indent=1, sort_keys=True))
    return d


def hp_read(f, rule):
    """A Pollster file as one row per poll row and candidate, with common column names."""
    if rule == 1:
        t = pd.read_csv(f, sep="\t")
        cols = list(t.columns)
        cand = [c for c in cols[:cols.index("poll_slug")] if re.sub(r"\.\d+$", "", c) not in HP_NOT_CANDIDATES]
        t = t.rename(columns={"survey_house": "pollster", "poll_slug": "poll_id", "sample_subpopulation": "population",
                              "observations": "sample_size", "partisan_affiliation": "partisan"})
        t["url"] = "http://" + HP_HOST + "polls/" + t.poll_id
    else:
        t = pd.read_csv(f)
        cols = list(t.columns)
        first = cols.index("Mode") + 1 if "Mode" in cols else cols.index("Population") + 1
        cand = [c for c in cols[first:cols.index("Pollster URL")] if re.sub(r"\.\d+$", "", c) not in HP_NOT_CANDIDATES]
        t = t.rename(columns={"Pollster": "pollster", "Start Date": "start_date", "End Date": "end_date",
                              "Number of Observations": "sample_size", "Population": "population",
                              "Pollster URL": "url"})
        t["poll_id"] = t.url.str.rsplit("/", n=1).str[-1]
        t["question_text"] = None
        t["partisan"] = None
    t["undecided"] = t["Undecided"] if "Undecided" in cols else None
    t["other"] = t["Other"] if "Other" in cols else None
    t["row"] = range(len(t))
    keep = ["row", "pollster", "poll_id", "population", "sample_size", "start_date", "end_date", "question_text",
            "partisan", "undecided", "other", "url"]
    return t.melt(id_vars=keep, value_vars=cand, var_name="candidate_name", value_name="pct").dropna(subset=["pct"])


def polls_huffpost(cands):
    d = hp_snapshot()
    src = json.loads((d / "sources.json").read_text())
    frames = []
    for key, s_ in src.items():
        cycle, geo, party = key.split("|")
        long = hp_read(d / s_["file"], s_["rule"])
        # stage comes from the FEC calendar (contest_dates): Pollster's chart names do not settle it
        long["cycle"], long["geo"], long["party"] = int(cycle), geo, party
        long["file"], long["capture"], long["file_rule"] = s_["path"], s_["timestamp"][:8], s_["rule"]
        long["question_id"] = "hp-" + cycle[2:] + "-" + geo + "-" + party + "-" + long.row.astype(str)
        frames.append(long)
    a = pd.concat(frames, ignore_index=True)
    a["start_date"] = pd.to_datetime(a.start_date).dt.date
    a["end_date"] = pd.to_datetime(a.end_date).dt.date
    a = add_status(a, cands)
    a = contest_dates(a)
    a["source"] = "HuffPost Pollster"
    early = a[(a.file_rule == 3) & a.election_date.notna()].drop_duplicates(["cycle", "party", "geo"])
    early = early[pd.to_datetime(early.capture) < pd.to_datetime(early.election_date)]
    print("Pollster contests whose only capture predates the contest (their last polls may be missing):",
          sorted(f"{y} {p} {g}" for y, p, g in early[["cycle", "party", "geo"]].values))
    out = a[["cycle", "party", "geo", "stage", "poll_id", "question_id", "pollster", "partisan", "population",
             "sample_size", "start_date", "end_date", "election_date", "days_to_contest", "question_text", "candidate_key", "candidate_name", "pct",
             "undecided", "other", "cand_status", "n_answers"] + QCOLS + ["source", "file", "file_rule", "capture", "url"]]
    rules = pd.Series([v["rule"] for v in src.values()]).value_counts().sort_index()
    print(f"\nHuffPost Pollster: {len(src)} contests; by rule (1 API file, 2 chart after July 1, 3 chart, earlier "
          f"capture): {rules.to_dict()}")
    return out.sort_values(["cycle", "party", "geo", "end_date", "question_id", "pct"],
                           ascending=[True, True, True, True, True, False])


def hp_checks(hp):
    qq = hp.drop_duplicates("question_id")
    allrun = qq.q_running == qq.n_answers
    print(pd.DataFrame({"questions": qq.groupby(["cycle", "party"]).size(),
                        "states": qq[qq.geo != "US"].groupby(["cycle", "party"]).geo.nunique(),
                        "national": qq[qq.geo == "US"].groupby(["cycle", "party"]).size(),
                        "all_running": qq[allrun].groupby(["cycle", "party"]).size()}).fillna(0).astype(int).to_string())
    print("Polled names not matched to the timeline (cycle, party, name, rows):")
    nr = hp[hp.cand_status == "not_running"].groupby(["cycle", "party", "candidate_name"]).size()
    print(nr.sort_values(ascending=False).head(30).to_string())
    print("Cross-check: 538's raw_polls.csv late primary polls (top two only). Found = a Pollster poll of the same "
          "contest in the field that day, give or take a day (the two sources name pollsters differently):")
    r = pd.read_csv(latest("538_github", "raw_polls.csv"), low_memory=False)
    r = r[(r.type_simple == "Pres-P") & r.cycle.isin([2012, 2016])].copy()
    r["party"] = r.race.str.extract(r"Pres-([DR])-P")[0]
    r["day"] = pd.to_datetime(r.polldate).dt.date
    spans = {}
    for x in qq.itertuples():
        spans.setdefault((x.cycle, x.party, x.geo), []).append((x.start_date, x.end_date))
    one = pd.Timedelta(days=1)
    r["result"] = ["no Pollster file" if (c, p, g) not in spans else
                   "in field" if any(s0 - one <= day <= e0 + one for s0, e0 in spans[(c, p, g)]) else "not found"
                   for c, p, g, day in zip(r.cycle, r.party, r.location, r.day)]
    # stricter: a Pollster question of that contest in the field that day with both candidates' shares within a point
    shares = {}
    for x in hp.itertuples():
        shares.setdefault(x.question_id, {})[name_parts(x.candidate_name)[1]] = x.pct
    byc = {}
    for x in qq.itertuples():
        byc.setdefault((x.cycle, x.party, x.geo), []).append((x.start_date, x.end_date, x.question_id, x.file_rule))

    def strict(row):
        for s0, e0, qid, rule in byc.get((row.cycle, row.party, row.location), []):
            if not (s0 - one <= row.day <= e0 + one):
                continue
            sh = shares[qid]
            a1, a2 = sh.get(name_parts(row.cand1_name)[1]), sh.get(name_parts(row.cand2_name)[1])
            if a1 is not None and a2 is not None and abs(a1 - row.cand1_pct) <= 1 and abs(a2 - row.cand2_pct) <= 1:
                return f"shares match (file rule {rule})"
        return None
    r["strict"] = r.apply(strict, axis=1)
    r.loc[r.strict.notna(), "result"] = r.strict
    print(pd.crosstab([r.cycle, r.party], r.result).to_string())
    print("  contests with no Pollster file:", sorted(set(r.loc[r.result == "no Pollster file", "location"])))


def checks(cands, polls):
    print("Candidate timeline, rows by cycle and party (with announcement date / suspension date):")
    print(cands.groupby(["cycle", "party"]).agg(n=("candidate", "size"), announced=("announced", "count"),
                                                suspended=("suspended", "count")).to_string())
    print("\nPolled names not in the timeline, most-asked (cycle, party, name, rows):")
    nr = polls[polls.cand_status == "not_running"].groupby(["cycle", "party", "candidate_name"]).size()
    print(nr.sort_values(ascending=False).head(25).to_string())
    print("\nQuestions by cycle and party: all, and those whose named candidates are all running on the end date")
    qq = polls.drop_duplicates("question_id")
    allrun = qq.q_running == qq.n_answers
    t = pd.DataFrame({"questions": qq.groupby(["cycle", "party"]).size(),
                      "all_running": qq[allrun].groupby(["cycle", "party"]).size(),
                      "national": qq[qq.geo == "US"].groupby(["cycle", "party"]).size(),
                      "national_all_running": qq[allrun & (qq.geo == "US")].groupby(["cycle", "party"]).size()})
    print(t.fillna(0).astype(int).to_string())
    print("\nCross-check: 538's raw_polls.csv (pollster ratings, late primary polls, top two only), 2020 questions "
          "found in the archive by question_id:")
    r = pd.read_csv(latest("538_github", "raw_polls.csv"), low_memory=False)
    r = r[(r.type_simple == "Pres-P") & (r.cycle == 2020)]
    print(f"  {r.question_id.isin(polls.question_id).sum()} of {len(r)}")


def main():
    cands = candidates()
    polls = polls_538(cands)
    p08 = polls_2008(cands)
    polls = pd.concat([p08.reindex(columns=polls.columns), polls], ignore_index=True)
    polls.to_csv(INTERIM / "primary_polls.csv", index=False)
    checks(cands, polls)
    hp = polls_huffpost(cands)
    hp.to_csv(INTERIM / "primary_polls_huffpost.csv", index=False)
    hp_checks(hp)


if __name__ == "__main__":
    main()
