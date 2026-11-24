"""Presidential primary results by state and the primary calendar, 2008-2020, from the FEC (DA-6).

Source: the FEC's yearly *Federal Elections* workbooks (federalelections2008.xls ... federalelections2020.xlsx),
fetched into data/raw/fec_results/<date>/ (public domain). Each has a "Pres Primary Results" sheet (votes by state,
party and candidate, with the primary's date) and a "Primary Dates" sheet (primary and caucus dates by state). The
FEC has not published a 2024 workbook (checked 2026-11-23); 2024 comes from elsewhere.

Outputs (data/interim/):
  primary_results.csv    one row per state, party and ballot line: date, candidate, FEC id, votes, share of the
                         party's total, the party's total, the line's kind (candidate, uncommitted, other) and the
                         FEC's note. Primaries only: caucuses are not in the FEC's results (their figures mix votes,
                         delegate equivalents and delegates, and come from the parties). Ranked-choice primaries
                         (2020) keep the first round, flagged. candidate_key matches primary_candidates.csv where
                         the candidate is in that timeline.
  primary_calendar.csv   one row per state, party and contest: primary or caucus, date, the sheet's text. A date
                         given for one party only ("1/5 (Republicans)") is that party's; a plain date is both
                         parties'. The 2008 and 2016 date sheets read a year late (2016's Iowa caucus shows as
                         2017-02-01); they are corrected, and every primary date is checked against the
                         results sheet's dates on each run.

Run:  python src/collect/primary_results.py
"""
import datetime as dt
import re
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, latest  # noqa: E402
from primary_polls import ABBR, match_keys  # noqa: E402

warnings.filterwarnings("ignore", message="Cannot parse header or footer")
INTERIM = ROOT / "data" / "interim"
FILES = {2008: "/documents/1666/federalelections2008.xls", 2012: "/documents/1691/federalelections2012.xls",
         2016: "/documents/1890/federalelections2016.xlsx", 2020: "/documents/4228/federalelections2020.xlsx"}
NOT_CANDIDATE = re.compile(r"uncommitted|scatter|all others|^other|none of|blank|void|write|no preference|"
                           r"candidate none|not voting|undecided", re.I)
PARTY = {"D": "D", "R": "R", "DEM": "D", "REP": "R"}
NAME_TO_ABBR = {**{k.upper(): v for k, v in ABBR.items()}, "D.C.": "DC", "PUERTO RICO": "PR"}


def snapshot():
    out = {}
    for y, u in FILES.items():
        try:
            out[y] = latest("fec_results", u.split("/")[-1])
        except FileNotFoundError:
            out[y] = fetch("fec_results", u.split("/")[-1], "https://www.fec.gov" + u)
    return out


def sheet(path, words):
    x = pd.ExcelFile(path)
    return next(n for n in x.sheet_names if words in n)


def results(paths, cands, cal):
    rows = []
    for y, p in paths.items():
        t = pd.read_excel(p, sheet_name=sheet(p, "Pres Primary Results"))
        t.columns = [str(c).strip() for c in t.columns]
        note_col = next((c for c in t.columns if c in ("Notes", "FOOTNOTES")), None)
        # ranked-choice primaries (2020) list a "Final Round" block and a "First Round" block: label each row
        hdr = t["PRIMARY RESULTS"].astype(str).str.extract(r"^(Final|First) Round", expand=False).str.lower()
        new_state = t["STATE ABBREVIATION"].ne(t["STATE ABBREVIATION"].shift())
        t["rcv_round"] = hdr.where(hdr.notna(), pd.Series(["" if n else None for n in new_state], index=t.index))
        t["rcv_round"] = t.groupby(t["STATE ABBREVIATION"].ne(t["STATE ABBREVIATION"].shift()).cumsum()
                                   ).rcv_round.ffill().replace("", None)
        t = t[t.PARTY.isin(PARTY) & t["PRIMARY RESULTS"].notna() & t["STATE ABBREVIATION"].notna()].copy()
        # total rows ("Total Party Votes:", "Total State Votes:") are dropped: some carry the wrong party (New Mexico
        # 2008, Louisiana 2020), so the party total is summed from the ballot lines instead
        t = t[~t["TOTAL VOTES"].astype(str).str.contains("Total", na=False)].copy()
        t["cycle"] = y
        t["party"] = t.PARTY.map(PARTY)
        t["state"] = t["STATE ABBREVIATION"].str.strip()
        t["results_sheet_date"] = pd.to_datetime(t["PRIMARY DATE"].astype(str).str.strip().str[:10], errors="coerce",
                                   format="mixed").dt.date
        last = t["LAST NAME"].fillna("").astype(str).str.strip().str.strip('"')
        first = t["FIRST NAME"].fillna("").astype(str).str.replace('"', "").str.strip()   # '"Ted"' -> 'Ted'
        t["candidate_name"] = (first + " " + last).str.strip()
        t["line"] = ["candidate" if (pd.notna(i) and not NOT_CANDIDATE.search(n)) else
                     "uncommitted" if re.search("uncommitted", n, re.I) else "other"
                     for i, n in zip(t["FEC ID"], last)]
        t["votes"] = pd.to_numeric(t["PRIMARY RESULTS"], errors="coerce")
        t["unopposed"] = t["PRIMARY RESULTS"].astype(str).str.strip().str.lower().eq("unopposed")
        t["fec_note"] = t[note_col] if note_col else None
        counted = ~t.fec_note.astype(str).str.contains("Not included", na=False)   # NY 2008 blank and void
        t["rcv_round"] = t.rcv_round.fillna("")
        t["party_total"] = t.votes.where(counted).groupby([t.state, t.party, t.rcv_round]).transform(
            lambda v: v.sum(min_count=1))
        t["share_listed"] = (t.votes / t.party_total).where(counted)
        t["fec_pct"] = pd.to_numeric(t["PRIMARY %"], errors="coerce")
        # share: the FEC's own percentage where it gives one (its totals include write-ins it does not list, as
        # in New Hampshire), else the share of the listed lines
        t["share"] = t.fec_pct.fillna(t.share_listed)
        t["ranked_choice"] = t.fec_note.astype(str).str.contains("Ranked Choice", na=False)
        t["fec_id"] = t["FEC ID"]
        rows.append(t[["cycle", "party", "state", "results_sheet_date", "candidate_name", "fec_id", "line", "votes",
                       "share", "share_listed", "fec_pct", "party_total", "unopposed", "ranked_choice", "rcv_round", "fec_note"]])
    r = pd.concat(rows, ignore_index=True)
    r["results_sheet_date"] = r.groupby(["cycle", "party", "state"]).results_sheet_date.transform(
        lambda s: s.ffill().bfill())
    # the date: the calendar's primary date for that state and party where there is one (the results sheet has a few
    # wrong: Ohio 2012 shows June 12 for the March 6 primary, Texas 2012 April 3 for May 29), else the sheet's
    prim = cal[cal.contest == "primary"].groupby(["cycle", "party", "state"]).date.min()
    r["date"] = [prim.get((y, p, st), d) for y, p, st, d in zip(r.cycle, r.party, r.state, r.results_sheet_date)]
    r["date_source"] = ["calendar" if (y, p, st) in prim.index else "results sheet"
                        for y, p, st in zip(r.cycle, r.party, r.state)]
    keys = match_keys(r[r.line == "candidate"], cands)
    r["candidate_key"] = [keys.get((c, p, n)) if ln == "candidate" else None
                          for c, p, n, ln in zip(r.cycle, r.party, r.candidate_name, r.line)]
    r["source"] = "FEC Federal Elections " + r.cycle.astype(str)
    cols = ["cycle", "party", "state", "date", "date_source", "results_sheet_date", "candidate_name", "candidate_key",
            "fec_id", "line", "votes", "share", "share_listed", "party_total", "unopposed", "ranked_choice", "rcv_round",
            "fec_note", "source"]
    return r[cols].sort_values(["cycle", "party", "date", "state", "votes"], ascending=[True, True, True, True, False])


def fix_1904(d, cycle):
    """The 2008 and 2016 sheets read a year late (2016's Iowa caucus shows as 2017-02-01)."""
    if isinstance(d, dt.datetime) and d.year == cycle + 1:
        return d.replace(year=cycle).date()
    return d.date() if isinstance(d, dt.datetime) else d


def parse_cell(v, cycle):
    """[(party or None, date, text)] from one date cell."""
    if pd.isna(v) or str(v).strip() == "":
        return []
    if isinstance(v, dt.datetime):
        return [(None, fix_1904(v, cycle), str(v))]
    text = str(v).strip()
    out = []
    # entries such as "1/5 (Republicans)", "2/22/2020 (Democrats)", "2/4-2/11 (Republicans)" (a range: its first
    # day), "3/3/20203" (a footnote digit after the year)
    for m in re.finditer(r"(\d{1,2})/(\d{1,2})(?:/\d{4}\d?)?(?:\s*-\s*\d{1,2}/\d{1,2}(?:/\d{4})?)?\s*(?:\(([^)]*)\))?",
                         text):
        mo, da = int(m.group(1)), int(m.group(2))
        who = (m.group(3) or "").lower()
        party = "D" if "democrat" in who else "R" if "republican" in who else None
        out.append((party, dt.date(cycle, mo, da), text))
    return out


def calendar(paths):
    rows = []
    for y, p in paths.items():
        t = pd.read_excel(p, sheet_name=sheet(p, "Primary Dates"), header=None)
        hdr = next(i for i in range(15) if str(t.iloc[i, 0]).strip().upper() == "STATE")
        for _, r in t.iloc[hdr + 1:].iterrows():
            st = str(r.iloc[0]).strip()
            if st.upper() in ("NAN", "") or st.upper().startswith("NOTE"):
                continue
            abbr = NAME_TO_ABBR.get(re.sub(r"[\d*]+$", "", st).strip().upper())
            if abbr is None:
                continue          # territories and Democrats Abroad
            for kind, col in (("primary", 1), ("caucus", 2)):
                for party, d, text in parse_cell(r.iloc[col], y):
                    for pa in ([party] if party else ["D", "R"]):
                        rows.append({"cycle": y, "state": abbr, "party": pa, "contest": kind, "date": d,
                                     "fec_text": text, "source": f"FEC Federal Elections {y}, primary dates"})
    c = pd.DataFrame(rows).drop_duplicates(["cycle", "state", "party", "contest", "date"])
    return c.sort_values(["cycle", "date", "state", "party"])


def checks(r, c):
    print("Results: ballot lines, states and party totals by cycle and party")
    print(r.groupby(["cycle", "party"]).agg(lines=("votes", "size"), states=("state", "nunique"),
                                             votes=("votes", "sum")).to_string())
    print("\nCandidate lines not matched to the timeline, most votes:")
    um = r[(r.line == "candidate") & r.candidate_key.isna()].groupby(["cycle", "party", "candidate_name"]).votes.sum()
    print(um.sort_values(ascending=False).head(15).to_string())
    print("\nUnopposed (no vote count):", sorted({f"{y} {p} {s}" for y, p, s in
                                                  r.loc[r.unopposed, ["cycle", "party", "state"]].values}))
    dd = r[(r.share - r.share_listed).abs() > 0.005]
    print("FEC percentages that differ from the share of listed lines by more than half a point:",
          len(dd), "lines in", dd.groupby(["cycle", "party", "state"]).ngroups, "contests")
    if len(dd):
        print(dd.groupby(["cycle", "party", "state"]).apply(
            lambda g: pd.Series({"lines": len(g), "max_gap": (g.share - g.share_listed).abs().max(),
                                 "fec_note": "; ".join(sorted(set(g.fec_note.dropna().astype(str))))[:60]}),
            include_groups=False).to_string())
    print("Results-sheet dates that differ from the calendar's (the calendar's is used):")
    d = r.drop_duplicates(["cycle", "party", "state"])
    d = d[(d.date_source == "calendar") & (d.date != d.results_sheet_date)]
    print(d[["cycle", "party", "state", "date", "results_sheet_date"]].to_string(index=False) if len(d) else "  none")
    print("\nCalendar check: each results date against the calendar's primary date for that state and party")
    pr = r.drop_duplicates(["cycle", "party", "state"])[["cycle", "party", "state", "results_sheet_date"]].rename(
        columns={"results_sheet_date": "date"})
    cal = c[c.contest == "primary"].groupby(["cycle", "party", "state"]).date.apply(set)
    pr["in_calendar"] = [d in cal.get((y, p, s), set()) for y, p, s, d in zip(pr.cycle, pr.party, pr.state, pr.date)]
    print(pr.groupby("cycle").in_calendar.agg(["sum", "size"]).to_string())
    bad = pr[~pr.in_calendar]
    if len(bad):
        print(bad.to_string(index=False))
    print("\nCalendar: contests by cycle and kind")
    print(c.groupby(["cycle", "contest"]).size().unstack(fill_value=0).to_string())


def main():
    paths = snapshot()
    cands = pd.read_csv(INTERIM / "primary_candidates.csv")
    c = calendar(paths)
    r = results(paths, cands, c)
    r.to_csv(INTERIM / "primary_results.csv", index=False)
    c.to_csv(INTERIM / "primary_calendar.csv", index=False)
    checks(r, c)


if __name__ == "__main__":
    main()
