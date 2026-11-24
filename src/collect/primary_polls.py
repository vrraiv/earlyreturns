"""Presidential primary polls and the candidate timeline they are judged against (DA-6).

Candidate timeline (data/interim/primary_candidates.csv): every candidate in the candidate tables of Wikipedia's
"<year> <Democratic|Republican> Party presidential primaries" pages, 2008 to 2024, fetched through
governors.get_page (cached in data/raw/wikipedia_hist/, revision id in every row). Dates kept separately:
  exploratory   exploratory committee formed, where the table gives it
  announced     campaign announced (the 2008 tables give no announcement dates: blank)
  suspended     campaign suspended or withdrawn; for a candidate who lost at the convention, that date
  secured       nomination secured (nominees)
Each date is labelled by the words before it in its cell ("Exploratory committee:", "Withdrew:", "Secured
nomination:", "Lost nomination:") or else by its column's header. Birth dates are left out by year.
Minor candidates listed only in "Other candidates" bullet lists, with no table row, are not in the timeline.

Polls (data/interim/primary_polls.csv), one row per question and candidate:
  2020, 2024   538's archived primary poll file (538_wayback/president_primary_polls_historical.csv, Feb 2025
               capture, CC BY): every poll of the cycle, every question, all candidates, state and national.
  2012, 2016   to come: archived HuffPost Pollster files (CC BY-NC-SA), in a separately licensed file.
  2008         to come.
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
  unknown       in the timeline with no announcement date (2008)
and each question carries counts of its named candidates by status (q_running, q_exploratory, q_not_yet,
q_withdrawn, q_not_running, q_unknown). Which statuses a "real field" allows is decided later (PP-3, PP-7), not here.

Candidates are matched to the timeline by surname, with the first initial (or a listed nickname) to confirm.

Run:  python src/collect/primary_polls.py
"""
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, latest  # noqa: E402
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
        ("edward", "ed"), ("frederick", "fred"), ("newton", "newt"), ("willard", "mitt"), ("rafael", "ted")}
SUFFIX = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
# dates the candidate tables leave out, entered by hand with their source
OVERRIDES = {(2008, "D", "hillary-clinton"): {"suspended": "2008-06-07", "note": "suspended date from the page's text "
                                              "(conceded and endorsed Obama), as in campaign_calendar.py"}}
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
            if d is None:
                continue
            before = text[max(0, m.start() - 40):m.start()].lower()
            kind = next((k for w, k in LABELS if w in before.split(")")[-1]), None)
            if kind is None and aligned:
                kind = header_kind(headers[i])
            if kind is None:
                kind = "announced" if "announced" not in out else "suspended"
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
                                 "suspended": d.get("suspended"), "secured": d.get("secured"), "wiki_revision": rev})
    df = pd.DataFrame(rows)
    df["note"] = ""
    for (cy, p, key), o in OVERRIDES.items():
        i = df.index[(df.cycle == cy) & (df.party == p) & (df.candidate_key == key)]
        assert len(i) == 1, (cy, p, key)
        for k, v in o.items():
            df.loc[i, k] = v if k == "note" else pd.Timestamp(v)
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
        hit = None
        for r in idx.get((cycle, party, sur), []):
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
        return "unknown" if c["cycle"] == 2008 else ("exploratory" if pd.notna(c["exploratory"]) and end >= c["exploratory"] else "unknown")
    if end >= c["announced"]:
        return "running"
    if pd.notna(c["exploratory"]) and end >= c["exploratory"]:
        return "exploratory"
    return "not_yet"


def polls_538(cands):
    a = pd.read_csv(latest("538_wayback", "president_primary_polls_historical.csv"), low_memory=False)
    a["candidate_party"] = a.party.map({"DEM": "D", "REP": "R"})
    a = a[a.candidate_party.notna()].copy()
    # a few questions list a candidate of the other party (Trump in a Democratic question): the question's party is
    # the party of most of its candidates, and the outsider counts as not running in that primary
    a["party"] = a.groupby("question_id").candidate_party.transform(lambda s: s.mode().iloc[0])
    geo = a.state.map(lambda s: "US" if pd.isna(s) else ABBR.get(s))
    bad = a.state[geo.isna() & a.state.notna()].unique()
    assert len(bad) == 0, f"unmapped states: {bad}"
    a["geo"] = geo
    for c in ["start_date", "end_date", "election_date"]:
        a[c] = pd.to_datetime(a[c], format="mixed").dt.date
    keys = match_keys(a, cands)
    a["candidate_key"] = [keys[k] for k in zip(a.cycle, a.party, a.candidate_name)]
    cinfo = {(r["cycle"], r["party"], r["candidate_key"]): r for r in cands.to_dict("records")}
    a["cand_status"] = [status(e, cinfo.get((c, p, k)) if k else None)
                        for e, c, p, k in zip(a.end_date, a.cycle, a.party, a.candidate_key)]
    a["candidate_key"] = a.candidate_key.fillna(a.candidate_name.map(slug))
    q = pd.crosstab(a.question_id, a.cand_status).reindex(columns=STATUSES, fill_value=0).add_prefix("q_")
    a = a.join(q, on="question_id")
    a["n_answers"] = a.groupby("question_id").question_id.transform("size")
    a["days_to_contest"] = pd.array([(e - d).days if pd.notna(e) else None for e, d in zip(a.election_date, a.end_date)],
                                    dtype="Int64")
    a["source"] = "538"
    out = a.rename(columns={"hypothetical": "hypothetical_538", "sponsors": "sponsor"})[
        ["cycle", "party", "geo", "stage", "poll_id", "question_id", "pollster", "pollster_rating_id", "sponsor",
         "partisan", "internal", "population", "sample_size", "tracking", "start_date", "end_date", "election_date",
         "days_to_contest", "notes", "hypothetical_538", "candidate_key", "candidate_name", "candidate_party", "answer", "pct",
         "cand_status", "n_answers"] + list(q.columns) + ["source"]]
    return out.sort_values(["cycle", "party", "end_date", "poll_id", "question_id", "pct"],
                           ascending=[True, True, True, True, True, False])


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
    polls.to_csv(INTERIM / "primary_polls.csv", index=False)
    checks(cands, polls)


if __name__ == "__main__":
    main()
