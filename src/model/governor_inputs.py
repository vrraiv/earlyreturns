"""Governor inputs that the first model left unbuilt (work plan GV-3). No 2026 results are read or written here.

  2026    every 2026 governor poll in the final forecast's VoteHub snapshot (Nov 3, before polls closed) that names
          both nominees, and one row per race with what the as-of backtest's governor model needs: incumbency, lean,
          and the poll averages built the way the backtest builds them (BACKTEST.md): a plain mean of polls ending in
          the final 21 days, one version per poll (likely voters, then registered, then adults), with the count of
          polls VoteHub flags for a party so the as-of sponsor shift can be applied (the flag also marks a pollster's
          affiliation where no sponsor is listed; `sponsor_listed` in the poll file tells the two apart). Polls ending 22 to 60 days out are averaged
          the same way, for races with no late poll. The published forecast's weighted average (pollavg.statewide,
          as of Nov 3) is kept beside them for comparison.
          -> data/interim/governor_2026_polls.csv, data/interim/governor_2026_inputs.csv
  offyear the national environment an odd-year governor race could have used, from figures known on its election
          day: the generic-ballot average of the day before, the president's approval, the last House vote, and the
          off-cycle estimator (environment.py) fitted on elections before that year. Then a test on the odd-year
          races, each forecast from the prior alone, fitted on even years before it.
          -> data/interim/governor_offyear_env.csv, data/processed/governor_offyear_env.json

Run:  python src/model/governor_inputs.py [2026|offyear]     (default both)
"""
import difflib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
from wiki import STATE_ABBR  # noqa: E402

INTERIM, OUT = ROOT / "data" / "interim", ROOT / "data" / "processed"
SNAPSHOT = ROOT / "data/raw/votehub/2026-11-03/polls.json"      # pinned: the final forecast's snapshot, not the latest
ELECTION_2026 = pd.Timestamp("2026-11-03")
LATE_DAYS, EARLIER_DAYS = 21, 60                                 # as backtest_asof.LATE_DAYS and FALLBACK_DAYS
POP_RANK = {"lv": 0, "v": 0, "rv": 1, "a": 2}
BURN_IN = 3                                                      # even cycles before an odd year is tested


# ---------------------------------------------------------------- 2026
def polls_2026():
    import pollavg as PA
    PA.ASOF = ELECTION_2026                                      # the weighted average as the forecast saw it
    polls = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for x in polls:
        x["end"] = pd.Timestamp(x["end_date"])
    races = pd.read_csv(INTERIM / "governor_2026_races.csv")
    name = {v: k for k, v in STATE_ABBR.items()}
    races["state_name"], races["race_key"] = races.state.map(name), races.state
    races = races.rename(columns={"dem_cand": "dem_nominee", "rep_cand": "rep_nominee"})
    weighted = PA.statewide(polls, races, "governor", "2026-06-15")
    lean = pd.read_csv(INTERIM / "state_presidential.csv").pivot(index="state", columns="year", values="lean_2p")
    rows, out = [], []
    for _, r in races.iterrows():
        rel = [x for x in polls if x["poll_type"] == "governor" and x["subject"] == f"2026 {r.state_name}" and len(x["answers"]) >= 2
               and x["end"] <= ELECTION_2026]

        def pick(cell):
            names = [PA.lastname(n) for n in str(cell).split(",")]
            if len(names) == 1:
                return names[0]
            share = {n: [y["pct"] for x in rel for y in x["answers"] if PA.lastname(y["choice"]) == n] for n in names}
            return max(names, key=lambda n: np.mean(share[n]) if share[n] else -1)
        dl, rl = pick(r.dem_nominee), pick(r.rep_nominee)
        full = {PA.lastname(n): n.strip().lower() for cell in (r.dem_nominee, r.rep_nominee) for n in str(cell).split(",")}
        # two candidates can share a surname (Nevada: Aaron Ford and Danielle Ford): the nominee's full name decides
        near = lambda y: difflib.SequenceMatcher(None, y["choice"].lower(), full.get(PA.lastname(y["choice"]), "")).ratio()  # noqa: E731

        def find(a, key):
            if key in a:
                return a[key]
            close = difflib.get_close_matches(key, list(a), n=2, cutoff=0.8)
            return a[close[0]] if len(close) == 1 else None
        mine = []
        for x in rel:
            a = {PA.lastname(y["choice"]): y["pct"] for y in sorted(x["answers"], key=near)}
            d_, r_ = find(a, dl), find(a, rl)
            if d_ is None or r_ is None:
                continue
            rest = sorted(y["pct"] for y in x["answers"])           # every share but one each of the nominees'
            rest.remove(d_); rest.remove(r_)
            third = max(rest, default=0.0)
            days = int((ELECTION_2026 - x["end"]).days)
            sp = (x.get("partisan") or "").upper()
            mine.append({"state": r.state, "pollster": x["pollster"], "start_date": x.get("start_date"), "end_date": x["end_date"], "days_out": days,
                         "population": (x.get("population") or "").lower(), "sample_size": x.get("sample_size"),
                         "sponsor_party": sp if sp in ("DEM", "REP") else "", "sponsor_listed": bool(x.get("sponsors")), "dem": dl, "rep": rl, "dem_pct": d_, "rep_pct": r_,
                         "poll2": 100 * (d_ - r_) / (d_ + r_), "candidates_named": len(x["answers"]), "third_pct": third,
                         "window": "late" if days <= LATE_DAYS else "earlier" if days <= EARLIER_DAYS else "older"})
        m = pd.DataFrame(mine)
        if len(m):
            m["rank"] = m.population.map(POP_RANK).fillna(3)
            m = m.sort_values(["rank", "candidates_named"]).drop_duplicates(["pollster", "start_date", "end_date"]).drop(columns="rank").sort_values("end_date")
            rows.append(m)
        row = {"state": r.state, "dem": dl, "rep": rl, "inc": int(r.inc_running) * (1 if r.inc_party == "D" else -1 if r.inc_party == "R" else 0),
               "lean_prev": float(lean.loc[r.state, 2024]), "lean_avg2": float(lean.loc[r.state, [2020, 2024]].mean()),
               "other_candidates_listed": isinstance(r.ind_cand, str) or isinstance(r.other_cand, str),
               # the largest share any third candidate had in a poll of the last 60 days (the model's races are two-way)
               "third_candidate_max_pct": float(m[m.window != "older"].third_pct.max()) if len(m) and (m.window != "older").any() else np.nan}
        for w in ("late", "earlier"):
            x = m[m.window == w] if len(m) else m
            row.update({f"n_{w}": len(x), f"avg_{w}": float(x.poll2.mean()) if len(x) else np.nan,
                        f"n_{w}_dem_sponsored": int((x.sponsor_party == "DEM").sum()) if len(x) else 0,
                        f"n_{w}_rep_sponsored": int((x.sponsor_party == "REP").sum()) if len(x) else 0})
        wv = weighted.get(r.state)
        row.update({"weighted_avg": wv["avg"] if wv else np.nan, "weighted_n": wv["n_polls"] if wv else 0, "weighted_latest": wv["latest"] if wv else None})
        out.append(row)
    p, t = pd.concat(rows, ignore_index=True), pd.DataFrame(out)
    p.round(3).to_csv(INTERIM / "governor_2026_polls.csv", index=False)
    t.round(3).to_csv(INTERIM / "governor_2026_inputs.csv", index=False)
    both = t[(t.n_late > 0) & t.weighted_avg.notna()]
    d = both.avg_late - both.weighted_avg
    print(f"governor_2026_polls.csv: {len(p)} polls in {p.state.nunique()} races (snapshot {SNAPSHOT.parent.name})")
    print(f"governor_2026_inputs.csv: {len(t)} races; polls in the final {LATE_DAYS} days: {int((t.n_late > 0).sum())}; "
          f"none late but some {LATE_DAYS + 1}-{EARLIER_DAYS} days out: {int(((t.n_late == 0) & (t.n_earlier > 0)).sum())}; "
          f"neither: {int(((t.n_late == 0) & (t.n_earlier == 0)).sum())}; weighted average: {int(t.weighted_avg.notna().sum())}")
    print(f"  plain late mean minus weighted average, {len(both)} races: mean {d.mean():+.2f}, RMS {np.sqrt((d ** 2).mean()):.2f}, largest {d.abs().max():.1f}")
    return p, t


# ---------------------------------------------------------------- off years
def election_day(y):
    d = pd.Timestamp(f"{y}-11-01")
    return d + pd.Timedelta(days=(0 - d.dayofweek) % 7 + 1)      # the Tuesday after the first Monday


def offyear_env():
    import environment as E
    gb = pd.read_csv(INTERIM / "generic_ballot_daily.csv", parse_dates=["date"]).set_index("date")
    tr = E.training()
    rows = []
    for y in range(1999, 2026, 2):
        day = election_day(y)
        eve = gb.loc[day - pd.Timedelta(days=1)]
        appr, src = E.approval_on(day)
        prev, prev_year = E.last_house_vote(day)
        party = E.president_party(day)
        sign = 1 if party == "D" else -1
        model = E.fit(tr[tr.year < y])                            # as of the year: elections before it only
        est = [sign * float(model.predict(pd.DataFrame({"approval": [appr], "prev": [sign * prev], "midterm": [m]})).iloc[0]) for m in (0.0, 1.0)]
        rows.append({"year": y, "election_day": day.date().isoformat(), "term_year": 1 if y % 4 == 1 else 3, "president": party,
                     "generic_ballot": float(eve.margin_2p), "generic_ballot_source": eve.source, "approval": appr, "approval_source": src,
                     "last_house_vote": prev, "last_house_year": prev_year, "estimator_m0": est[0], "estimator_m1": est[1],
                     "estimator_fit_through": int(tr[tr.year < y].year.max())})
    t = pd.DataFrame(rows)
    t.round(3).to_csv(INTERIM / "governor_offyear_env.csv", index=False)
    return t


def offyear_test(env):
    """Each odd-year race from the prior alone: fitted on even-year races before it, with each environment in turn.
    The term-year version scales the estimator's midterm term by m, fitted on earlier odd years of the same term year
    (m = 1 until there is one)."""
    d = pd.read_csv(INTERIM / "governor_dataset.csv")
    d = d[d.contested.astype(bool) & ~d.multi_candidate.astype(bool) & ~d.recall.astype(bool)].copy()
    even, odd = d[d.nat_house.notna()], d[d.year % 2 == 1]
    e = env.set_index("year")
    rows, ms = [], []
    for y in sorted(odd.year.unique()):
        tr = even[even.year < y]
        if tr.year.nunique() < BURN_IN:
            continue
        fit = smf.ols("margin_2p ~ lean_avg2 + nat_house + inc", tr).fit()
        g = float(fit.params["nat_house"])
        base = lambda x: fit.predict(x.assign(nat_house=0.0))    # noqa: E731
        # m for this term year, from earlier odd years: margin - base - g*e0 = g*(e1 - e0)*m
        past = odd[(odd.year < y) & (odd.year % 4 == y % 4) & (odd.year >= 1999)]
        if len(past):
            e0, sl = past.year.map(e.estimator_m0), past.year.map(e.estimator_m1 - e.estimator_m0)
            yv, xv = past.margin_2p - base(past) - g * e0, g * sl
            m = float((xv * yv).sum() / (xv ** 2).sum())
        else:
            m = 1.0
        ms.append({"year": int(y), "m_term_year": m, "earlier_races": int(len(past))})
        x = odd[odd.year == y]
        cands = {"last House vote": e.last_house_vote[y], "generic ballot of the day": e.generic_ballot[y], "estimator, midterm-like": e.estimator_m1[y],
                 "estimator, by term year": e.estimator_m0[y] + m * (e.estimator_m1[y] - e.estimator_m0[y])}
        for k, v in cands.items():
            rows += [{"year": int(y), "state": s, "environment": k, "env": float(v), "error": float(a - p)}
                     for s, a, p in zip(x.state, x.margin_2p, base(x) + g * v)]
    r = pd.DataFrame(rows)
    summ = r.groupby("environment", sort=False).error.agg(races="size", mean="mean", rmse=lambda v: float(np.sqrt((v ** 2).mean())), mae=lambda v: float(v.abs().mean()))
    by_term = r.assign(term_year=np.where(r.year % 4 == 1, 1, 3)).groupby(["term_year", "environment"], sort=False).error.agg(
        races="size", mean="mean", rmse=lambda v: float(np.sqrt((v ** 2).mean())))
    out = {"note": "odd-year governor races, prior only, every fit on earlier years (governor_inputs.py)", "burn_in_even_cycles": BURN_IN,
           "summary": summ.reset_index().to_dict("records"), "by_term_year": by_term.reset_index().to_dict("records"),
           "m_by_year": ms, "environments": env.to_dict("records"), "races": r.round(3).to_dict("records")}
    (OUT / "governor_offyear_env.json").write_text(json.dumps(out, indent=1, default=float))
    pd.set_option("display.width", 220)
    print(env[["year", "term_year", "president", "generic_ballot", "approval", "last_house_vote", "estimator_m0", "estimator_m1"]].round(1).to_string(index=False))
    print(summ.round(2).to_string()); print(by_term.round(2).to_string())
    print(pd.DataFrame(ms).round(2).to_string(index=False))
    print(r[r.year == 2025].round(1).to_string(index=False))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    if what in ("2026", "both"):
        polls_2026()
    if what in ("offyear", "both"):
        offyear_test(offyear_env())
