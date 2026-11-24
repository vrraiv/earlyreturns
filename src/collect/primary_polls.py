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
Minor candidates listed only in "Other candidates" bullet lists (2024) are added with their withdrawal date only.

Polls (data/interim/primary_polls.csv), one row per question and candidate:
  2020, 2024   538's archived primary poll file (538_wayback/president_primary_polls_historical.csv, Feb 2025
               capture, CC BY): every poll of the cycle, every question, all candidates, state and national.
  2008         to come.
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
  unknown       in the timeline with no announcement date (2008)
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
        if len(fold(name).split()) == 1:          # surname only (HuffPost's columns): only an unambiguous match
            hit = hits[0].candidate_key if len(hits) == 1 else None
        for r in hits if hit is None else []:
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


QCOLS = ["q_" + x for x in STATUSES]


def add_status(a, cands):
    """candidate_key, cand_status on the end date, and per-question counts by status and of answers."""
    keys = match_keys(a, cands)
    a["candidate_key"] = [keys[k] for k in zip(a.cycle, a.party, a.candidate_name)]
    cinfo = {(r["cycle"], r["party"], r["candidate_key"]): r for r in cands.to_dict("records")}
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
        # stage is left blank: Pollster's chart names do not settle it (Iowa's files say "primary"); the results
        # calendar will
        long["cycle"], long["geo"], long["party"], long["stage"] = int(cycle), geo, party, None
        long["file"], long["capture"], long["file_rule"] = s_["path"], s_["timestamp"][:8], s_["rule"]
        long["question_id"] = "hp-" + cycle[2:] + "-" + geo + "-" + party + "-" + long.row.astype(str)
        frames.append(long)
    a = pd.concat(frames, ignore_index=True)
    a["start_date"] = pd.to_datetime(a.start_date).dt.date
    a["end_date"] = pd.to_datetime(a.end_date).dt.date
    a = add_status(a, cands)
    a["source"] = "HuffPost Pollster"
    out = a[["cycle", "party", "geo", "stage", "poll_id", "question_id", "pollster", "partisan", "population",
             "sample_size", "start_date", "end_date", "question_text", "candidate_key", "candidate_name", "pct",
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
    polls.to_csv(INTERIM / "primary_polls.csv", index=False)
    checks(cands, polls)
    hp = polls_huffpost(cands)
    hp.to_csv(INTERIM / "primary_polls_huffpost.csv", index=False)
    hp_checks(hp)


if __name__ == "__main__":
    main()
