"""Presidential general-election polls by state and nationally, 2000-2024, with a coverage table (DA-5).

Two FiveThirtyEight sources, both already in data/raw/:
  538 raw_polls.csv (538_github)            2000-2016: late polls only (most in the final three weeks, none more
                                            than about two months out), one Democrat-Republican pair per poll
                                            question. Its 2020 rows are dropped in favour of the archive.
  president_polls_historical.csv (538_wayback, Feb 2025 capture)
                                            2020 and 2024: every poll of the cycle, every question, all candidates.

Outputs (data/interim/):
  president_general_polls.csv   one row per poll question: cycle, geo (state code, ME-1/ME-2/NE-1..3, or US),
                                pollster, dates, the Democrat's and Republican's shares, margin (D-R), and flags:
                                head_to_head (only those two answered), presumptive (Biden against Trump in
                                2024, before his withdrawal), window ("late" or "full").
  president_poll_coverage.csv   cycle x geo: polls, pollsters, polls in the final three weeks, first poll date, and
                                the result's two-party margin and lean (state_presidential_history.csv).

Questions kept: matchups between the eventual nominees, plus Biden against Trump in 2024 up to Biden's withdrawal on
July 21, the matchup everyone expected until then. Other matchups are dropped: the archive's hypothetical flag is not
consistent (2024's Biden-Trump questions are flagged, 2020's Sanders-Trump ones are not), so it is not used. Also
dropped: Puerto Rico, and the Maine ranked-choice reallocations (duplicates of round one).

Run:  python src/collect/pres_polls.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, latest  # noqa: E402
from downballot import STATE_ABBR  # noqa: E402

INTERIM = ROOT / "data" / "interim"
NOMINEES = {2000: ("Al Gore", "George W. Bush"), 2004: ("John Kerry", "George W. Bush"),
            2008: ("Barack Obama", "John McCain"), 2012: ("Barack Obama", "Mitt Romney"),
            2016: ("Hillary Rodham Clinton", "Donald Trump"), 2020: ("Joe Biden", "Donald Trump"),
            2024: ("Kamala Harris", "Donald Trump")}
ABBR = {**STATE_ABBR, "District of Columbia": "DC"}
RAW_GEO = {"M1": "ME-1", "M2": "ME-2", "N1": "NE-1", "N2": "NE-2", "N3": "NE-3"}
BIDEN_OUT = pd.Timestamp("2024-07-21")
COLS = ["cycle", "geo", "poll_id", "question_id", "pollster", "pollster_rating_id", "partisan", "population",
        "sample_size", "start_date", "end_date", "mid_date", "election_date", "days_to_election", "d_candidate",
        "r_candidate", "d_pct", "r_pct", "margin", "n_answers", "head_to_head", "presumptive", "window",
        "source", "url"]


def geo_archive(s):
    if pd.isna(s):
        return "US"
    if " CD-" in s:
        st, n = s.split(" CD-")
        return f"{ABBR[st]}-{n}"
    return ABBR.get(s)


def raw_polls():
    r = pd.read_csv(latest("538_github", "raw_polls.csv"), low_memory=False)
    r = r[(r.type_simple == "Pres-G") & (r.cycle < 2020)].copy()
    return pd.DataFrame({
        "cycle": r.cycle, "geo": r.location.map(lambda x: RAW_GEO.get(x, x)), "poll_id": r.poll_id,
        "question_id": r.question_id, "pollster": r.pollster, "pollster_rating_id": r.pollster_rating_id,
        "partisan": r.partisan, "population": pd.NA, "sample_size": r.samplesize, "start_date": pd.NaT,
        "end_date": pd.NaT, "mid_date": pd.to_datetime(r.polldate), "election_date": pd.to_datetime(r.electiondate),
        "d_candidate": r.cand1_name, "r_candidate": r.cand2_name, "d_pct": r.cand1_pct, "r_pct": r.cand2_pct,
        "n_answers": pd.NA, "head_to_head": pd.NA, "presumptive": False, "window": "late",
        "source": "538 raw_polls", "url": pd.NA})


def archive():
    a = pd.read_csv(latest("538_wayback", "president_polls_historical.csv"), low_memory=False)
    a = a[(a.state != "Puerto Rico") & ~a.ranked_choice_reallocated.fillna(False).astype(bool)]
    rows = []
    for qid, q in a.groupby("question_id", sort=False):
        d, r = q[q.party == "DEM"], q[q.party == "REP"]
        if d.empty or r.empty:
            continue
        d, r, f = d.loc[d.pct.idxmax()], r.loc[r.pct.idxmax()], q.iloc[0]
        cyc = int(f.cycle)
        start, end = pd.to_datetime(f.start_date, format="%m/%d/%y"), pd.to_datetime(f.end_date, format="%m/%d/%y")
        pair = (d.candidate_name, r.candidate_name)
        presumptive = cyc == 2024 and pair == ("Joe Biden", "Donald Trump") and end <= BIDEN_OUT
        if pair != NOMINEES[cyc] and not presumptive:
            continue
        rows.append({"cycle": cyc, "geo": geo_archive(f.state), "poll_id": f.poll_id, "question_id": qid,
                     "pollster": f.pollster, "pollster_rating_id": f.pollster_rating_id, "partisan": f.partisan,
                     "population": f.population, "sample_size": f.sample_size, "start_date": start, "end_date": end,
                     "mid_date": start + (end - start) / 2,
                     "election_date": pd.to_datetime(f.election_date, format="%m/%d/%y"),
                     "d_candidate": d.candidate_name, "r_candidate": r.candidate_name, "d_pct": d.pct, "r_pct": r.pct,
                     "n_answers": len(q), "head_to_head": len(q) == 2, "presumptive": presumptive,
                     "window": "full", "source": "538 archive (Feb 2025)", "url": f.url})
    return pd.DataFrame(rows)


def build():
    df = pd.concat([raw_polls(), archive()], ignore_index=True)
    df["margin"] = df.d_pct - df.r_pct
    df["days_to_election"] = (df.election_date - df.mid_date).dt.days
    bad = df.geo.isna()
    if bad.any():
        raise SystemExit(f"unmapped geography in {int(bad.sum())} rows")
    df = df[COLS].sort_values(["cycle", "geo", "mid_date", "poll_id", "question_id"])
    for c in ("start_date", "end_date", "mid_date", "election_date"):
        df[c] = df[c].dt.strftime("%Y-%m-%d")
    df.to_csv(INTERIM / "president_general_polls.csv", index=False)
    print(f"president_general_polls.csv: {len(df)} questions, {df.poll_id.nunique()} polls, "
          f"cycles {', '.join(map(str, sorted(df.cycle.unique())))}; {int(df.presumptive.sum())} Biden-Trump 2024")
    coverage(df)


def coverage(df):
    n = df[~df.presumptive]
    g = n.groupby(["cycle", "geo"])
    cov = pd.DataFrame({"window": g.window.first(), "polls": g.poll_id.nunique(), "pollsters": g.pollster.nunique(),
                        "polls_final3w": n[n.days_to_election <= 21].groupby(["cycle", "geo"]).poll_id.nunique(),
                        "first_poll": g.mid_date.min()}).reset_index()
    res = pd.read_csv(INTERIM / "state_presidential_history.csv")
    nat = res.groupby("year").national_margin_2p.first().rename("result_margin_2p").reset_index().assign(geo="US")
    res = pd.concat([res.rename(columns={"state": "geo", "margin_2p": "result_margin_2p"}), nat])
    res = res.rename(columns={"year": "cycle"})[["cycle", "geo", "result_margin_2p", "lean_2p"]]
    # every state, DC and the nation in every cycle, polled or not, so gaps show as zeros
    full = res[res.cycle.isin(NOMINEES)][["cycle", "geo"]]
    cov = full.merge(cov, on=["cycle", "geo"], how="outer").merge(res, on=["cycle", "geo"], how="left")
    cov["window"] = cov.window.fillna(cov.cycle.map(lambda c: "late" if c < 2020 else "full"))
    for c in ("polls", "pollsters", "polls_final3w"):
        cov[c] = cov[c].fillna(0).astype(int)
    cov = cov.sort_values(["cycle", "geo"])
    cov.round(3).to_csv(INTERIM / "president_poll_coverage.csv", index=False)
    st = cov[(cov.geo != "US") & ~cov.geo.str.contains("-")]
    summ = st.groupby("cycle").agg(states_polled=("polls_final3w", lambda x: int((x > 0).sum())),
                                   states_3plus=("polls_final3w", lambda x: int((x >= 3).sum())),
                                   state_polls_final3w=("polls_final3w", "sum"))
    summ["national_polls_final3w"] = cov[cov.geo == "US"].set_index("cycle").polls_final3w
    summ["full_cycle_polls"] = cov.groupby("cycle").polls.sum().where(summ.index >= 2020)
    print("president_poll_coverage.csv (eventual nominees; states and DC, final three weeks):")
    print(summ.to_string())


if __name__ == "__main__":
    build()
