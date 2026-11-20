"""Presidential general-election polls by state and nationally, 2000-2024, with a coverage table (DA-5).

One source per cycle and geography, all in data/raw/ (window "full" = the whole cycle, "late" = late polls only):
  2000, and 2004 national   538 raw_polls.csv (538_github): late polls only (most in the final three weeks, none more
                            than about two months out), one Democrat-Republican pair per question. No full-cycle source:
                            Wikipedia's 2000 statewide page is a stub and there is no 2004 national page.
  2004 states               Wikipedia's statewide polling page (wikipedia_hist/, revision id kept).
  2008                      Wikipedia's statewide and nationwide polling pages.
  2012 states               Wikipedia's three statewide polling pages (pre-2012, early/mid 2012, autumn).
  2012 national             The Economist's presidential model repository (economist_potus/, pinned commit, MIT),
                            from March. Wikipedia's national page starts only in September.
Chosen on the cross-check of 2026-11-20 (pres_polls_crosscheck.py), which matches the sources poll by poll:
Wikipedia agrees with 538's raw_polls.csv in 2004, 2008 and 2012 (84-91% of polls found, 95-98% of those within a
point of margin). The Economist's 2008 file holds fewer polls, and its 2012 state polls carry dates about four days
late (release dates, by the look of it), so it is used only where nothing else covers the months before September.
  2016                      538's 2016 forecast poll file (538_wayback/president_general_polls_2016.csv), polls-only
                            branch: November 2015 to Election Day, states, districts and national.
  2020, 2024                538's archived poll file (538_wayback/president_polls_historical.csv, Feb 2025 capture):
                            every poll of the cycle, every question, all candidates.
The run prints, per cycle, the late-window count from the chosen source against raw_polls.csv, as a check that the
full-cycle source does not drop the late polls that raw_polls has.

Outputs (data/interim/):
  president_general_polls.csv   one row per poll question: cycle, geo (state code, ME-1/ME-2/NE-1..3, or US),
                                pollster, dates, the Democrat's and Republican's shares, margin (D-R), and flags:
                                head_to_head (only those two answered), presumptive (Biden against Trump in
                                2024, before his withdrawal), state_subsample (2016 state slices of national
                                online panels), window ("late" or "full").
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
SUBSAMPLERS = ["Google Consumer Surveys", "Ipsos", "SurveyMonkey", "CVOTER International"]
COLS = ["cycle", "geo", "poll_id", "question_id", "pollster", "pollster_rating_id", "partisan", "population",
        "sample_size", "start_date", "end_date", "mid_date", "election_date", "days_to_election", "d_candidate",
        "r_candidate", "d_pct", "r_pct", "margin", "n_answers", "head_to_head", "presumptive", "state_subsample", "window",
        "source", "url"]


def geo_archive(s):
    if pd.isna(s):
        return "US"
    if " CD-" in s:
        st, n = s.split(" CD-")
        return f"{ABBR[st]}-{n}"
    return ABBR.get(s)


def raw_polls(all_rows=False):
    """2000, and 2004 national. all_rows=True returns every presidential row (2000-2020), for the checks."""
    r = pd.read_csv(latest("538_github", "raw_polls.csv"), low_memory=False)
    r = r[r.type_simple == "Pres-G"].copy()
    if not all_rows:
        r = r[(r.cycle == 2000) | ((r.cycle == 2004) & (r.location == "US"))]
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


POP = {"Likely Voters": "lv", "Registered Voters": "rv", "Adults": "a", "lv": "lv", "rv": "rv", "a": "a", "v": "v"}


def economist(year, national_only=False):
    """2008, 2012 and 2016 (the last only for the cross-check): state code or '--' for national. One row per poll in
    2008 and 2012; 2016 has a row per population and question."""
    e = pd.read_csv(latest("economist_potus", "all_polls.csv" if year == 2016 else f"all_polls_{year}.csv"))
    if national_only:
        e = e[e.state == "--"].reset_index(drop=True)
    if year == 2016:                       # drop the by-party subsamples ("Likely Voters - Democrat")
        e = e[e.population.isin(POP)].reset_index(drop=True)
    d_col, r_col = {2008: ("obama", "mccain"), 2012: ("obama", "romney"), 2016: ("clinton", "trump")}[year]
    fmt = "%Y-%m-%d" if year == 2016 else "%m/%d/%y"
    start = pd.to_datetime(e["start.date"], format=fmt)
    end = pd.to_datetime(e["end.date"], format=fmt)
    eday = pd.Timestamp({2008: "2008-11-04", 2012: "2012-11-06", 2016: "2016-11-08"}[year])
    ids = [f"econ{year}-{i}" for i in range(len(e))]
    out = pd.DataFrame({
        "cycle": year, "geo": e.state.replace("--", "US"), "poll_id": ids, "question_id": ids, "pollster": e.pollster,
        "pollster_rating_id": pd.NA, "partisan": pd.NA, "population": e.population.map(POP),
        "sample_size": e["number.of.observations"], "start_date": start, "end_date": end,
        "mid_date": start + (end - start) / 2, "election_date": eday,
        "d_candidate": NOMINEES[year][0], "r_candidate": NOMINEES[year][1], "d_pct": e[d_col], "r_pct": e[r_col],
        "n_answers": pd.NA, "head_to_head": pd.NA, "presumptive": False, "window": "full",
        "source": "The Economist us-potus-model", "url": pd.NA})
    return out[out.end_date <= eday]       # 2008's file runs into December


def fte2016():
    f = pd.read_csv(latest("538_wayback", "president_general_polls_2016.csv"), low_memory=False)
    f = f[f.type == "polls-only"]
    start, end = pd.to_datetime(f.startdate, format="%m/%d/%Y"), pd.to_datetime(f.enddate, format="%m/%d/%Y")
    n = 2 + f.rawpoll_johnson.notna().astype(int) + f.rawpoll_mcmullin.notna().astype(int)
    geo = f.state.map(lambda x: "US" if x == "U.S." else geo_archive(x))
    return pd.DataFrame({
        "cycle": 2016, "geo": geo, "poll_id": f.poll_id, "question_id": f.question_id, "pollster": f.pollster,
        "pollster_rating_id": pd.NA, "partisan": pd.NA, "population": f.population.map(POP),
        "sample_size": f.samplesize, "start_date": start, "end_date": end, "mid_date": start + (end - start) / 2,
        "election_date": pd.Timestamp("2016-11-08"), "d_candidate": NOMINEES[2016][0],
        "r_candidate": NOMINEES[2016][1], "d_pct": f.rawpoll_clinton, "r_pct": f.rawpoll_trump, "n_answers": n,
        "head_to_head": n == 2, "presumptive": False, "window": "full", "source": "538 2016 forecast polls",
        "url": f.url})


MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}


def wiki_dates(s, year):
    """'October 21-30', 'May 31-June 2', 'October 26', 'Sept. 9-11' (any dash) -> (start, end); None if unreadable."""
    import re
    s = re.sub(r"\[\d+\]", "", str(s)).replace("\u2013", "-").replace("\u2014", "-").replace(",", " ")
    toks = re.findall(r"[A-Za-z]+|\d+|-", s)
    years = [int(t) for t in toks if t.isdigit() and 1990 <= int(t) <= 2100]
    year = years[-1] if years else year           # "December 1-4, 2011" on a 2012 page
    out, month = [], None
    for t in toks:
        if t.isalpha():
            m = next((v for k, v in MONTHS.items() if k.startswith(t.lower()[:3])), None)
            if m:
                month = m
        elif t.isdigit() and month and int(t) <= 31:
            out.append(pd.Timestamp(year, month, int(t)))
    if not out:
        return None
    start, end = out[0], out[-1]
    if start > end:                                  # "December 28 - January 3": the start is in the year before
        start = start - pd.DateOffset(years=1)
    return start, end


def pct(x):
    try:
        return float(str(x).split("%")[0].replace("\u2212", "-").strip())
    except ValueError:
        return None


WIKI = {  # year -> (statewide pages, Democrat's and Republican's column words, election day)
    2004: (["Statewide_opinion_polling_for_the_2004_United_States_presidential_election"], "Kerry", "Bush",
           "2004-11-02"),
    2008: (["Statewide_opinion_polling_for_the_2008_United_States_presidential_election"], "Obama", "McCain",
           "2008-11-04"),
    2012: (["Pre-2012_statewide_opinion_polling_for_the_2012_United_States_presidential_election",
            "Early/Mid_2012_statewide_opinion_polling_for_the_2012_United_States_presidential_election",
            "Statewide_opinion_polling_for_the_2012_United_States_presidential_election"], "Obama", "Romney",
           "2012-11-06"),
}


def wiki_states(year):
    """One or more wikitables per state under the state's heading; columns Poll source, Date administered, the
    Democrat, the Republican, [others], Margin, Sample size, Margin of error. A poll appears once per matchup table,
    so a two-way and a three-way question of the same poll share a poll_id."""
    import io
    import re

    from bs4 import BeautifulSoup
    from governors import get_page
    titles, dw, rw, eday = WIKI[year]
    rows, skipped = [], 0
    for title in titles:
        html, rev = get_page(title, cache_name=title.replace("/", "-"))
        rows_t, skipped_t = wiki_page(html, rev, year, dw, rw, eday)
        rows += rows_t
        skipped += skipped_t
    out = pd.DataFrame(rows).drop_duplicates("question_id")
    out = out[(out.end_date <= pd.Timestamp(eday)) & (out.start_date >= pd.Timestamp(year - 2, 11, 1))]
    print(f"  wikipedia {year}: {len(out)} questions, {out.poll_id.nunique()} polls in {out.geo.nunique()} states; "
          f"{skipped} rows unreadable")
    return out


WIKI_NATIONAL = {2008: "Nationwide_opinion_polling_for_the_2008_United_States_presidential_election",
                 2012: "Nationwide_opinion_polling_for_the_2012_United_States_presidential_election",
                 2016: "Nationwide_opinion_polling_for_the_2016_United_States_presidential_election"}


def wiki_national(year):
    """National polls from Wikipedia's nationwide page: every table with the two nominees, whatever its heading."""
    from governors import get_page
    _, dw, rw, eday = WIKI.get(year, (None, "Clinton", "Trump", "2016-11-08"))
    html, rev = get_page(WIKI_NATIONAL[year])
    rows, skipped = wiki_page(html, rev, year, dw, rw, eday, fixed_geo="US")
    out = pd.DataFrame(rows).drop_duplicates("question_id")
    out = out[(out.end_date <= pd.Timestamp(eday)) & (out.start_date >= pd.Timestamp(year - 2, 11, 1))]
    print(f"  wikipedia {year} national: {len(out)} questions, {out.poll_id.nunique()} polls; {skipped} rows unreadable")
    return out


def wiki_page(html, rev, year, dw, rw, eday, fixed_geo=None):
    import io
    import re

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    rows, state, skipped = [], fixed_geo, 0
    for el in soup.find_all(["h2", "h3", "h4", "table"]):
        if el.name in ("h2", "h3", "h4"):
            if fixed_geo:
                continue
            head = re.sub(r"\[.*?\]", "", el.get_text(" ", strip=True)).strip()
            m = re.match(r"(Maine|Nebraska)(?:'s)? (\d)", head)
            if m:
                state = f"{ABBR[m.group(1)]}-{m.group(2)}"
            elif head in ABBR:
                state = ABBR[head]
            elif el.name == "h2":
                state = None
            continue
        if state is None or "wikitable" not in (el.get("class") or []):
            continue
        t = pd.read_html(io.StringIO(str(el)))[0]
        cols = {c: str(c) for c in t.columns}
        names = list(t.columns)
        dc = next((c for c, n in cols.items() if "Date" in n), None)
        sc = next((c for c, n in cols.items() if "Poll" in n), None)
        zc = next((c for c, n in cols.items() if "Sample" in n), None)
        party_cols = "Democrat" in cols.values() and "Republican" in cols.values()
        if party_cols:
            # 2012 layout: candidate names in the cells of "Democrat" and "Republican", each share in the next column
            dn = next(c for c, n in cols.items() if n == "Democrat")
            rn = next(c for c, n in cols.items() if n == "Republican")
            kc, bc = names[names.index(dn) + 1], names[names.index(rn) + 1]
            n_cand = sum(1 for n in cols.values() if n.startswith("%"))
        else:
            kc = next((c for c, n in cols.items() if dw in n), None)
            bc = next((c for c, n in cols.items() if rw in n), None)
            n_cand = sum(1 for n in cols.values()
                         if not re.search(r"poll|date|margin|sample|lead|error|undecided|other", n, re.I))
        if not (kc and bc and dc and sc):
            continue
        for _, r in t.iterrows():
            if party_cols and not (dw in str(r[dn]) and rw in str(r[rn])):
                continue                       # another matchup (Obama against Cain, Gingrich, Perry...)
            dd = wiki_dates(r[dc], year)
            k, b = pct(r[kc]), pct(r[bc])
            if dd is None or k is None or b is None:
                skipped += 1
                continue
            pollster = re.sub(r"\[\d+\]", "", str(r[sc])).strip()
            size = str(r[zc]) if zc else ""
            m = re.search(r"(\d[\d,]*)", size)
            pop = re.search(r"\b(LV|RV|A)\b", size)
            pid = f"wp{year}-{state}-{pollster}-{dd[0]:%m%d}-{dd[1]:%m%d}"
            rows.append({"cycle": year, "geo": state, "poll_id": pid, "question_id": f"{pid}-{n_cand}",
                         "pollster": pollster, "pollster_rating_id": pd.NA, "partisan": pd.NA,
                         "population": pop.group(1).lower() if pop else pd.NA,
                         "sample_size": float(m.group(1).replace(",", "")) if m else pd.NA,
                         "start_date": dd[0], "end_date": dd[1], "mid_date": dd[0] + (dd[1] - dd[0]) / 2,
                         "election_date": pd.Timestamp(eday), "d_candidate": NOMINEES[year][0],
                         "r_candidate": NOMINEES[year][1], "d_pct": k, "r_pct": b, "n_answers": n_cand,
                         "head_to_head": n_cand == 2, "presumptive": False, "window": "full",
                         "source": f"Wikipedia (revision {rev})", "url": pd.NA})
    return rows, skipped


def late_check(df):
    """Per cycle, state and national polls within 21 days of the election: chosen source vs raw_polls.csv."""
    r = raw_polls(all_rows=True)
    r["days"] = (r.election_date - r.mid_date).dt.days
    a = df[(~df.presumptive) & (df.days_to_election <= 21)].groupby("cycle").poll_id.nunique()
    b = r[r.days <= 21].groupby("cycle").poll_id.nunique()
    print("late-window check (polls within 21 days; chosen source vs raw_polls.csv):")
    print(pd.DataFrame({"chosen": a, "raw_polls": b}).fillna(0).astype(int).to_string())


def build():
    df = pd.concat([raw_polls(), wiki_states(2004), wiki_states(2008), wiki_national(2008), wiki_states(2012),
                    economist(2012, national_only=True), fte2016(), archive()], ignore_index=True)
    # 2016's file carries state subsamples of national online panels, by the thousand; they pull state averages
    # 2-3 points from the other sources' (cross-check), so they are flagged for the model to weigh or drop
    df["state_subsample"] = (df.cycle == 2016) & (df.geo != "US") & df.pollster.isin(SUBSAMPLERS)
    df["margin"] = df.d_pct - df.r_pct
    df["days_to_election"] = (df.election_date - df.mid_date).dt.days
    bad = df.geo.isna()
    if bad.any():
        raise SystemExit(f"unmapped geography in {int(bad.sum())} rows")
    late_check(df)
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
    cov["window"] = cov.window.fillna(cov.cycle.map(lambda c: "late" if c == 2000 else "full"))
    for c in ("polls", "pollsters", "polls_final3w"):
        cov[c] = cov[c].fillna(0).astype(int)
    cov = cov.sort_values(["cycle", "geo"])
    cov.round(3).to_csv(INTERIM / "president_poll_coverage.csv", index=False)
    st = cov[(cov.geo != "US") & ~cov.geo.str.contains("-")]
    summ = st.groupby("cycle").agg(states_polled=("polls_final3w", lambda x: int((x > 0).sum())),
                                   states_3plus=("polls_final3w", lambda x: int((x >= 3).sum())),
                                   state_polls_final3w=("polls_final3w", "sum"))
    summ["national_polls_final3w"] = cov[cov.geo == "US"].set_index("cycle").polls_final3w
    summ["all_polls"] = cov.groupby("cycle").polls.sum()
    summ["window"] = cov.groupby("cycle").window.agg(lambda w: "/".join(sorted(set(w))))
    print("president_poll_coverage.csv (eventual nominees; states and DC, final three weeks; all = whole cycle):")
    print(summ.to_string())


if __name__ == "__main__":
    build()
