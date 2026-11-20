"""As-of backtest of the whole model: Senate races, House districts and seat counts, 1998-2024 data (work plan CM-1).

Each cycle Y is forecast with every parameter fitted on cycles before Y only, then scored against the result.
BACKTEST.md describes the design, the coverage by cycle, what differs from the published 2026 model and the
adoption rule. In short:

  polls        final-21-day polls, equal weights, sponsored polls shifted by an as-of flat amount. This is the one
               poll window every cycle has (538 raw_polls.csv, 1998-2022; 2024 rebuilt the same way from the archived
               538 poll files). The published model's time decay and population weights need whole-cycle polls
               (2018 on) and stay in backtest.py.
  national     generic-ballot average, blended with fundamentals fitted on elections before Y.
  Senate       prior = state lean (previous presidential election) + environment + incumbency; blended with the poll
               average by precision. Democrat-vs-Republican races only.
  House        prior = const + b * 2PVI + g * environment + incumbency, fitted on earlier cycles; blended with district
               polls. Seats with one major party on the ballot are fixed. Districts for 2006 on come from
               house_history.csv (Cook PVI); 1998 to 2004 come from Gary Jacobson's House elections file, which is
               not in the repo (DATA.md). Without that file the House starts in 2006 and is scored from 2012.
  simulation   as forecast.simulate: one shared national draw, a Census-region shock, a random slope on lean and a
               race draw, Student-t with as-of degrees of freedom.
  governors    the first governor model (governor_model.py) re-estimated as of each cycle: prior = const + b * lean
               (two-election average) + g * environment + incumbency; blended with the poll average; two national
               errors, the statewide-poll miss and the environment's. Even years only; two-way races.
               --gov-lean swaps the prior's lean measure (GV-3's candidates, BACKTEST.md).

Burn-in: a layer is scored for Y only if it has MIN_PRIOR earlier cycles to fit on. 2026 is in no fit and is not scored
here yet: that needs its polls, results and districts in this script's shape.

Run:  python src/model/backtest_asof.py                  the baseline: writes data/processed/backtest_asof*.{json,csv}
      python src/model/backtest_asof.py --tag NAME       a candidate change: writes backtest_asof_NAME*.{json,csv}
      python src/model/backtest_asof.py --compare NAME   NAME against the baseline, cycle by cycle, on the same races
      options: --seed-shift N (other random draws, to see how much a score moves by chance)
               --gov-lean pres|statewide|both|prevgov|approval|incprev|ratings|ratings_unpolled (the governor prior; pres is the baseline)
               --gov-poll-fallback all|forecast (a governor race with no polls in the final 21 days uses those 22
               to 60 days out: in the fit and the forecast, or in the forecast only)
               --gov-unpolled-sd robust|rms (the spread of a governor race forecast from the prior alone)
               --gov-unpolled flat|demo (an unpolled governor race borrows the polled races' gap from the prior:
               from all alike, or by demographic similarity; needs The Downballot's tables in data/linked/)
"""
import argparse
import hashlib
import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT, latest  # noqa: E402
from wiki import STATE_ABBR  # noqa: E402
import bias_analysis as BA  # noqa: E402
import calibrate as CAL  # noqa: E402
import error_structure as ES  # noqa: E402
import fundamentals as FU  # noqa: E402
import poll_settings as PS  # noqa: E402

OUT = ROOT / "data" / "processed"
MIN_PRIOR = 3                    # burn-in: earlier cycles a layer needs before a cycle is scored
LATE_DAYS = 21                   # the poll window, the same in every cycle (raw_polls itself runs to 60 days out)
HELD_OUT = (2026,)               # never in a fit, never scored here
NSIM = 20000
INC_SENATE = 2.0                 # as the 2026 model (an assumed constant there too)
FUND_SD_INFLATE = 1.15           # the 2026 model widened the fundamentals' leave-one-out RMSE by about 15%
HALF_LIFE_BIAS = 8.0             # years; bias_realtime.py
CLIP = 0.001                     # win probabilities are clipped to [CLIP, 1 - CLIP] for log loss
COMP = 15.0                      # "competitive": |forecast margin| <= 15
VARIANTS = ("polls_only", "polls_fundamentals", "polls_fundamentals_biasadj")
CHAMBERS = ("senate", "house", "governor")
GOV_LEAN = "pres"                # the governor prior's lean measure; main() sets it from --gov-lean
GOV_PRIORS = {"pres": "actual ~ lean_avg2 + env + inc", "statewide": "actual ~ lean_sw + env + inc",
              "both": "actual ~ lean_avg2 + lean_sw + env + inc", "prevgov": "actual ~ lean_avg2 + prevgov + env + inc",
              "approval": "actual ~ lean_avg2 + env + inc + ap_agree + ap_lean",
              "incprev": "actual ~ lean_avg2 + env + inc + inc_prev", "ratings": "actual ~ lean_avg2 + env + inc + rating",
              "ratings_unpolled": "actual ~ lean_avg2 + env + inc"}       # the ratings prior is fitted beside it, for unpolled races
GOV_PRIOR_SD_SCALE, GOV_SD_SCALE = 1.0, 1.0   # --gov-prior-sd-scale, --gov-sd-scale (polled races)
SW_YEARS = 6                     # statewide lean: Senate and governor results this many years back
ELECTION = {y: pd.Timestamp(d) for y, d in {2018: "2018-11-06", 2020: "2020-11-03", 2022: "2022-11-08", 2024: "2024-11-05"}.items()}
REGIONS = ["Northeast", "Midwest", "South", "West"]
STATE_REGION = ES.STATE_REGION


def prior_pres(c):
    return c - 2 if c % 4 == 2 else c - 4


def rms(x):
    x = np.asarray(x, float)
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else float("nan")


# ---------------------------------------------------------------- data
def wayback_polls(fname, cycle, kind, lo=0, hi=21):
    """Final-21-day polls for one cycle from the archived 538 files, in raw_polls shape: one row per poll, two-party
    Democratic margin `poll2`. Used for 2024 (raw_polls stops in 2022) and, on 2018-2022, to check the rebuild."""
    p = pd.read_csv(latest("538_wayback", fname), low_memory=False)
    p = p[p.cycle == cycle].copy()
    p["end"] = pd.to_datetime(p.end_date, format="%m/%d/%y", errors="coerce")
    e = ELECTION[cycle]
    p = p[(p.end <= e - pd.Timedelta(days=lo)) & (p.end >= e - pd.Timedelta(days=hi))]
    if kind == "generic":
        q = p.assign(DEM=p.dem, REP=p.rep, location="US", race_key="US")
    else:
        p = p[(p.stage == "general") & (p.hypothetical != True) & p.party.isin(["DEM", "REP"])]  # noqa: E712
        q = p.groupby(["question_id", "party"]).pct.max().unstack().dropna()
        meta = p.drop_duplicates("question_id").set_index("question_id")
        q = q.join(meta[["poll_id", "pollster", "state", "seat_number", "population", "partisan"]])
        top = p.sort_values("pct", ascending=False).drop_duplicates(["question_id", "party"]).pivot(index="question_id", columns="party", values="candidate_name")
        q["cand1_name"], q["cand2_name"] = top.DEM.reindex(q.index), top.REP.reindex(q.index)
        q["st"] = q.state.map(STATE_ABBR)
        q = q.dropna(subset=["st"])
        if kind == "senate":
            q["location"] = q.st
        else:
            q["location"] = q.st + "-" + q.seat_number.astype(int).astype(str)
        q["race_key"] = q.location
    # one question per poll: likely voters first, then registered, then adults
    q["pop_rank"] = q.population.astype(str).str.lower().map({"lv": 0, "v": 0, "rv": 1, "a": 2}).fillna(3)
    q = q.sort_values("pop_rank").drop_duplicates(["poll_id", "race_key"]) if "poll_id" in q else q
    q["poll2"] = 100 * (q.DEM - q.REP) / (q.DEM + q.REP)
    q["cycle"] = cycle
    for c in ("partisan", "cand1_name", "cand2_name"):
        if c not in q:
            q[c] = np.nan
    return q[["cycle", "location", "pollster", "partisan", "poll2", "cand1_name", "cand2_name"]].reset_index(drop=True)


def load_polls():
    """raw_polls (1998-2022, even years, D-vs-R) plus the 2024 targets. `scored` marks November generals (no runoffs)."""
    r = BA.load()
    r = r[r.type_simple.isin(["Sen-G", "Gov-G", "House-G", "House-G-US"])].copy()
    r["scored"] = ~r.race.str.contains(r"-S?R_")
    r["late"] = r.time_to_election <= LATE_DAYS
    r["source"] = "raw_polls"
    extra = []
    for fname, kind, ts in [("senate_polls_historical.csv", "senate", "Sen-G"), ("house_polls_historical.csv", "house", "House-G"),
                            ("generic_ballot_polls_historical.csv", "generic", "House-G-US"), ("governor_polls_historical.csv", "senate", "Gov-G")]:
        w = wayback_polls(fname, 2024, kind)
        w["type_simple"], w["scored"], w["late"], w["source"] = ts, True, True, "538_wayback"
        w["race_id"] = "wb2024_" + ts + "_" + w.location + "_" + w.cand1_name.map(_lastname)
        w["act2"] = np.nan
        extra.append(w)
    return pd.concat([r] + extra, ignore_index=True).assign(gov_fb=False)


FALLBACK_DAYS = (22, 60)         # --gov-poll-fallback: the earlier window (raw_polls itself stops about 60 days out)
GOV_UNPOLLED_SD = "robust"       # --gov-unpolled-sd: "rms" uses the prior's root-mean-square error instead
GOV_UNPOLLED = None              # --gov-unpolled
GOV_FB_FIT = True                # whether the governor fit reads the marked polls too ("all") or only the forecast does


def gov_fallback(r):
    """Mark (`gov_fb`) the governor polls ending 22 to 60 days out in races that have no poll in the final 21 days, and
    add 2024's from the archived file. Only the governor fit and forecast read the mark."""
    w = wayback_polls("governor_polls_historical.csv", 2024, "senate", *FALLBACK_DAYS)
    w["type_simple"], w["scored"], w["late"], w["source"], w["act2"], w["gov_fb"] = "Gov-G", True, False, "538_wayback", np.nan, False
    w["race_id"] = "wb2024_Gov-G_" + w.location + "_" + w.cand1_name.map(_lastname)
    r = pd.concat([r, w], ignore_index=True)
    g = (r.type_simple == "Gov-G") & r.scored
    key = r.cycle.astype(int).astype(str) + r.location.astype(str)
    days = r.time_to_election.fillna(FALLBACK_DAYS[0])                  # the archive rows are already in the window
    r["gov_fb"] = g & ~r.late & ~key.isin(set(key[g & r.late])) & days.between(*FALLBACK_DAYS)
    return r


def wayback_check(r):
    """How close the rebuilt final-21-day averages are to raw_polls where both exist (2018-2022)."""
    out = {}
    for fname, kind, ts in [("senate_polls_historical.csv", "senate", "Sen-G"), ("house_polls_historical.csv", "house", "House-G"),
                            ("generic_ballot_polls_historical.csv", "generic", "House-G-US"), ("governor_polls_historical.csv", "senate", "Gov-G")]:
        d = []
        for c in (2018, 2020, 2022):
            w = wayback_polls(fname, c, kind).groupby("location").poll2.agg(["mean", "size"])
            a = r[(r.cycle == c) & (r.type_simple == ts) & r.scored & r.late & ~r.race.astype(str).str.contains("-GS_")].groupby("location").poll2.agg(["mean", "size"])
            j = a.join(w, lsuffix="_raw", rsuffix="_wb", how="inner")
            d.append(j.assign(cycle=c))
        d = pd.concat(d)
        out[ts] = {"races": int(len(d)), "mean_abs_diff": float((d.mean_raw - d.mean_wb).abs().mean()),
                   "p90_abs_diff": float((d.mean_raw - d.mean_wb).abs().quantile(0.9)),
                   "polls_raw": int(d.size_raw.sum()), "polls_rebuilt": int(d.size_wb.sum())}
    return out


def _lastname(n):
    n = re.sub(r'"[^"]*"|\([^)]*\)|\b(JR|SR|II|III|IV)\b\.?', " ", str(n).upper())
    if "," in n:                      # "MURKOWSKI, LISA" or "KEAN, JR."
        n = n.split(",")[0]
    n = re.sub(r"[^A-Z ]", " ", n).split()
    return n[-1] if n else ""


def _tokens(n):
    """Name parts of three letters or more: some 2022 rows in the returns are written "WYDEN RON"."""
    return {t for t in re.sub(r"[^A-Z ]", " ", str(n).upper()).split() if len(t) >= 3}


# the returns leave the party blank for these candidates
PARTY_PATCH = {(2020, "WY", "LUMMIS"): "R", (2020, "WY", "DAVID"): "D", (2024, "MS", "WICKER"): "R", (2024, "MS", "PINKINS"): "D",
               (2024, "NV", "ROSEN"): "D", (2024, "NV", "BROWN"): "R"}


def senate_universe(r):
    """Every November Senate general with a Democrat and a Republican as the top two: result, state lean and whether
    an elected incumbent is running. From the MIT Election Lab returns (fusion lines summed per candidate); a race
    the returns lack is taken from raw_polls. Left out: races whose top two are not a Democrat and a Republican,
    all-party November rounds (a second candidate of either party with 5% or more), and a special on the same day
    with the same two candidates as the regular election. Appointed senators are not flagged as incumbents: the
    returns carry no incumbency, so the flag is a name match to the winners of the state's Senate elections in the
    previous six years."""
    m = pd.read_csv(latest("medsl", "1976-2024-senate-state.tab"), low_memory=False)
    m["stage"] = m.stage.str.lower()
    m = m[m.stage.isin(["gen", "pre"]) & m.candidate.notna() & ~m.writein.fillna(False).astype(bool)].copy()
    has_pre = m[m.stage == "pre"].groupby(["year", "state_po", "special"]).size().index   # Georgia 2008: "pre" is November, "gen" the runoff
    m = m[(m.stage == "pre") | ~pd.MultiIndex.from_frame(m[["year", "state_po", "special"]]).isin(has_pre)]
    m["ln"] = m.candidate.map(_lastname)
    pd_ = m.party_detailed.fillna("").str.upper()
    m["party"] = np.where(pd_.str.startswith("DEMOCRAT"), "D", np.where(pd_.str.startswith("REPUBLICAN") | (pd_ == "GOP"), "R", "O"))
    patch = [PARTY_PATCH.get(k) for k in zip(m.year, m.state_po, m.ln)]
    m["party"] = [b or a for a, b in zip(m.party, patch)]
    c = m.groupby(["year", "state_po", "special", "ln"]).agg(v=("candidatevotes", "sum"), candidate=("candidate", "first"),
                                                             p=("party", lambda x: "D" if "D" in set(x) else "R" if "R" in set(x) else "O")).reset_index()
    c = c[~c.ln.isin(["VOTES", "OTHER", "SCATTERING", ""])].sort_values("v", ascending=False)
    winners = c.groupby(["year", "state_po", "special"]).head(1)[["year", "state_po", "ln", "p"]]
    lean = pd.read_csv(ROOT / "data/interim/state_presidential_history.csv").set_index(["year", "state"]).lean_2p

    def incumbent(y, st, d_name, r_name):
        prev = set(winners[(winners.state_po == st) & (winners.year < y) & (winners.year >= y - 6)].ln)
        return 1 if _tokens(d_name) & prev else -1 if _tokens(r_name) & prev else 0
    rows = []
    for (y, st, sp), g in c.groupby(["year", "state_po", "special"]):
        if y < 1998 or y % 2 or len(g) < 2:
            continue
        top, tot = g.head(2), g.v.sum()
        if set(top.p) != {"D", "R"}:
            continue
        if any((g[g.p == k].v.iloc[1:] / tot >= 0.05).any() for k in ("D", "R")):
            continue
        d, rr = top[top.p == "D"].iloc[0], top[top.p == "R"].iloc[0]
        rows.append(dict(cycle=int(y), state=st, special=bool(sp), dem=d.candidate, rep=rr.candidate, d_ln=d.ln, r_ln=rr.ln,
                         actual=100 * (d.v - rr.v) / (d.v + rr.v), inc=incumbent(y, st, d.candidate, rr.candidate), source="medsl"))
    have = set(zip(m.year, m.state_po))
    x = r[(r.type_simple == "Sen-G") & r.scored & (r.source == "raw_polls")].drop_duplicates("race_id")
    for _, a in x.iterrows():
        if (a.cycle, a.location) in have or not str(a.electiondate).startswith(f"{a.cycle}-11"):
            continue
        dn, rn = (a.cand1_name, a.cand2_name) if a.cand1_party == "DEM" else (a.cand2_name, a.cand1_name)
        rows.append(dict(cycle=int(a.cycle), state=a.location, special="-GS_" in a.race, dem=dn, rep=rn, d_ln=_lastname(dn), r_ln=_lastname(rn),
                         actual=a.act2, inc=incumbent(a.cycle, a.location, dn, rn), source="raw_polls"))
    u = pd.DataFrame(rows)
    u["lean"] = [lean.get((prior_pres(y), st), np.nan) for y, st in zip(u.cycle, u.state)]
    u = u.dropna(subset=["lean"]).sort_values(["cycle", "state", "special"])
    dup = u.duplicated(["cycle", "state", "d_ln", "r_ln"], keep="first")     # regular sorts first
    u = u[~dup].reset_index(drop=True)
    u["key"] = u.state + np.where(u.special & u.duplicated(["cycle", "state"], keep=False), "-sp", "")
    return u


def link_senate(r, u):
    """Attach each Senate poll to its race in the universe by state and a candidate's last name (`ukey`)."""
    names = {}
    for _, a in u.iterrows():
        for t in _tokens(a.dem) | _tokens(a.rep):
            names.setdefault((a.cycle, a.state, t), a.key)
    s = (r.type_simple == "Sen-G").values
    k1 = [names.get((c, l, _lastname(n))) for c, l, n in zip(r.cycle, r.location, r.cand1_name)]
    k2 = [names.get((c, l, _lastname(n))) for c, l, n in zip(r.cycle, r.location, r.cand2_name)]
    r = r.copy()
    r["ukey"] = [(a or b) if f else None for a, b, f in zip(k1, k2, s)]
    return r


JACOBSON = "hr4624.xlsx"          # Gary Jacobson's House elections file, 1946-2024; kept out of the repo (DATA.md)
JACOBSON_YEARS = (1998, 2000, 2002, 2004)   # the cycles it supplies; 2006 on stays on house_history.csv
# his state codes are 1 to 50 in order of state name
JACOBSON_STATES = [STATE_ABBR[n] for n in sorted(n for n in STATE_ABBR if STATE_ABBR[n] != "DC")]


def jacobson_path():
    try:
        return latest("jacobson", JACOBSON)
    except FileNotFoundError:
        return None


def jacobson_raw():
    j = pd.read_excel(jacobson_path(), sheet_name="data")
    j.columns = [c.strip() for c in j.columns]
    return j.apply(pd.to_numeric, errors="coerce")


def jacobson_house(j, years):
    """Districts in house_history's shape from Jacobson's file. The lean has to be known before the election: `dpres`
    is the previous presidential vote in a midterm row (redrawn to new lines where needed) but that year's own vote in
    a presidential-year row, so for a presidential year the lean is taken from the row two years earlier and only for
    districts not redrawn since. Districts left without a lean are dropped. Lean is one election's vote against the
    national vote, where Cook PVI averages two. His vote share is two-party, so a few races count here that
    house_history leaves out for a large third-party vote (26 of 3,331 on 2006 to 2024)."""
    pres = pd.read_csv(ROOT / "data/interim/state_presidential_history.csv").groupby("year").national_margin_2p.first()
    out = []
    for y in years:
        a = j[j.year == y].copy()
        if y % 4 == 2:
            share, py = a.dpres, y - 2
        else:
            share, py = a.stcd.map(j[j.year == y - 2].set_index("stcd").dpres).where(a.redist == 0), y - 4
        lean2 = 2 * share - 100 - float(pres[py])
        st = (a.stcd // 100).map(lambda k: JACOBSON_STATES[int(k) - 1])
        n = st.map(st.value_counts())
        dist = np.where(n == 1, 0, a.stcd % 100)                       # at-large seats are district 0 in house_history
        two = a.dv.notna() & a.inc.isin([0, 1, 2, 3, 4, 5]) & (a.po2 != 9) & (a.pwin != 9)   # a Democrat against a Republican
        # one major party on the ballot, which is known beforehand: coded unopposed, or both candidates of one party.
        # A race with no vote share and no such code (Louisiana runoffs, mostly) is left out, not fixed to its winner.
        one = ~two & a.pwin.isin([0, 1]) & ((a.dv.isna() & ((a.po2 == 2) | a.po1.isin([5, 6, 7]))) | a.inc.isin([6, 7, 8, 9, 10, 11]))
        d = pd.DataFrame({"year": y, "state": st.values, "district": dist, "pvi": (lean2 / 2).values, "lean2": lean2.values,
                          "inc": a.inc.map({0: -1, 1: 1}).fillna(0).astype(int).values, "margin": (2 * a.dv - 100).where(two).values,
                          "modeled": (two & lean2.notna()).values,
                          "fixed": np.where(one, np.where(a.pwin == 1, "D", "R"), None)})
        d["actual"], d["fit"], d["at_large"] = d.margin, d.modeled, d.district == 0
        d["key"] = d.state + "-" + d.district.astype(str)
        d["source"] = "jacobson"
        out.append(d[d.modeled | d.fixed.notna()])
    return pd.concat(out, ignore_index=True)


def house_universe(jac=None, lean="cook"):
    """Districts by cycle: house_history.csv for 2006 on, Jacobson's file for JACOBSON_YEARS when it is on this machine
    (`jac` is its table). lean="jacobson" also puts his one-election lean on the later cycles where he has one, to
    measure what mixing the two kinds of lean costs."""
    h = house_history_universe()
    h["source"] = "house_history"
    if jac is None:
        return h
    if lean == "jacobson":
        alt = jacobson_house(jac, sorted(h.year.unique())).set_index(["year", "key"]).lean2
        k = pd.MultiIndex.from_frame(h[["year", "key"]])
        v = pd.Series(alt.reindex(k).values, index=h.index)
        h["lean2"] = v.where(v.notna() & h.pvi.notna(), h.lean2)
    return pd.concat([jacobson_house(jac, JACOBSON_YEARS), h], ignore_index=True)


def house_history_universe():
    """house_history.csv with the harness's own flags. `fit` is the district model's estimation sample (the file's
    `contested`, as house_structure.py uses it). `modeled` adds the Minnesota seats that flag leaves out (their
    Democrats are listed as DFL). `fixed` seats have one major party on the ballot."""
    h = pd.read_csv(ROOT / "data/interim/house_history.csv")
    both = (h.d_top > 0) & (h.r_top > 0)
    h["fit"] = h.contested.astype(bool)
    h["modeled"] = both & (h.other < 15) & h.pvi.notna() & (h.n_d <= 1) & (h.n_r <= 1)
    h["fixed"] = np.where((h.d_top > 0) & (h.r_top == 0), "D", np.where((h.r_top > 0) & (h.d_top == 0), "R", None))
    h["actual"] = np.where(both, 100 * (h.d_top - h.r_top) / (h.d_top + h.r_top).replace(0, np.nan), np.nan)
    h["at_large"] = h.district == 0
    h["key"] = h.state + "-" + h.district.astype(str)
    return h


def senate_results():
    """Senate general elections 1976-2024 from MEDSL: year, state, two-party margin between the leading Democrat and
    the leading Republican (a candidate's votes summed over party lines). Races without both are left out, as are
    runoffs."""
    m = pd.read_csv(latest("medsl", "1976-2024-senate-state.tab"), sep=None, engine="python")
    m = m[m.stage.str.lower().eq("gen") & ~m.writein.fillna(False).astype(bool) & m.candidate.notna()]
    m = m[~m.year.isin(HELD_OUT)]
    k = ["year", "state_po", "special", "candidate"]
    c = m.groupby(k).candidatevotes.sum().rename("v").reset_index()
    for pty, col in (("DEMOCRAT", "d"), ("REPUBLICAN", "r")):
        c = c.merge(m[m.party_simplified == pty][k].drop_duplicates().assign(**{col: True}), on=k, how="left")
    c["d"], c["r"] = c.d.eq(True) & ~c.r.eq(True), c.r.eq(True) & ~c.d.eq(True)
    top = lambda col: c[c[col]].groupby(["year", "state_po", "special"]).v.max()  # noqa: E731
    t = pd.concat([top("d").rename("dv"), top("r").rename("rv")], axis=1).dropna().reset_index()
    t["margin"] = 100 * (t.dv - t.rv) / (t.dv + t.rv)
    return t.rename(columns={"state_po": "state"})[["year", "state", "margin"]]


def governor_universe(sen_res=None, gov_res=None):
    """Two-way governor races in even years from governor_dataset.csv (no recalls, no third candidate at 15% or more),
    as governor_model.load() selects them. The file's own poll averages are not used: they are 60-day averages for
    538's rows. Odd years are left to governor_model.py, whose environment for them is a separate estimator.

    Two more lean measures for GV-3's candidates, each from results before the race only, each result taken as its
    two-party margin minus that year's national House margin:
      lean_sw   mean of the state's Senate and even-year governor results in the SW_YEARS years before the cycle
      prevgov   the state's previous governor race, if it was in an even year
    `sen_res` and `gov_res` (year, state, margin) can be passed in, for the leak test."""
    d = pd.read_csv(ROOT / "data/interim/governor_dataset.csv")
    d = d[d.contested.astype(bool) & ~d.multi_candidate.astype(bool) & ~d.recall.astype(bool) & (d.year % 2 == 0)]
    d = d[~d.year.isin(HELD_OUT)]
    g = pd.DataFrame({"cycle": d.year.values, "state": d.state.values, "key": d.state.values, "lean_avg2": d.lean_avg2.values,
                      "inc": d.inc.values, "env": d.nat_house.values, "actual": d.margin_2p.values})
    assert not g.duplicated(["cycle", "state"]).any()
    nat = pd.read_csv(ROOT / "data/interim/house_national_vote.csv").set_index("year").two_party_margin_D
    gov_res = g.rename(columns={"cycle": "year", "actual": "margin"})[["year", "state", "margin"]] if gov_res is None else gov_res
    past = pd.concat([senate_results() if sen_res is None else sen_res, gov_res], ignore_index=True)
    past["dev"] = past.margin - past.year.map(nat)
    by_state = {s: x for s, x in past.groupby("state")}
    gs = {s: x.sort_values("year") for s, x in gov_res.groupby("state")}

    def sw(c, s):
        x = by_state.get(s)
        x = x[(x.year < c) & (x.year >= c - SW_YEARS)] if x is not None else None
        return float(x.dev.mean()) if x is not None and len(x) else np.nan

    def pg(c, s):
        x = gs.get(s)
        x = x[x.year < c] if x is not None else None
        return float(x.margin.iloc[-1] - nat[x.year.iloc[-1]]) if x is not None and len(x) else np.nan
    # presidential approval (Gallup, Jul 15 - Oct 31, known before the election), centred on 50, by party agreement
    # between the sitting governor and the president and by state lean (BACKTEST.md, "Presidential approval ...")
    import environment as EN
    appr = {int(y): (float(a) if pd.notna(a) else EN.approval_on(f"{int(y)}-11-04")[0]) for y, a in d.groupby("year").approval.first().items()}
    a50, sgn = g.cycle.map(appr) - 50, np.where(d.pres_party.values == "D", 1, -1)
    g["ap_agree"] = sgn * a50 * np.where(d.inc_party.values == d.pres_party.values, 1, -1)
    g["ap_lean"] = a50 * g.lean_avg2 / 10
    g["lean_sw"] = [sw(c, s) for c, s in zip(g.cycle, g.state)]
    rp = ROOT / "data/interim/governor_ratings.csv"
    if rp.exists():
        rt_ = pd.read_csv(rp)
        rt_ = rt_[~rt_.year.isin(HELD_OUT)].groupby(["year", "state"]).value.mean()
        g["rating"] = [rt_.get((c, s), np.nan) for c, s in zip(g.cycle, g.state)]
    # the incumbent's own last margin: the state's previous governor race, if the incumbent now running won it
    h = pd.read_csv(ROOT / "data/interim/governor_dataset.csv")
    h = h[~h.recall.astype(bool) & ~h.year.isin(HELD_OUT)].sort_values(["state", "year", "special"])
    h["pw"], h["py"], h["pm"] = h.groupby("state").winner.shift(1), h.groupby("state").year.shift(1), h.groupby("state").margin_2p.shift(1)
    h = h.drop_duplicates(["year", "state"], keep="last").set_index(["year", "state"]).reindex(list(zip(g.cycle, g.state)))
    same = [isinstance(a, str) and isinstance(b, str) and _lastname(a) == _lastname(b) for a, b in zip(h.incumbent, h.pw)]
    dev = h.pm.values - h.py.map(nat).values
    g["inc_prev"] = np.where(g.inc.values == 0, 0.0, np.where(np.array(same), dev, np.nan))
    g["prevgov"] = [pg(c, s) for c, s in zip(g.cycle, g.state)]
    return g


_SIM = {}


def state_similarity():
    """Weight of state t's polls for state s: exp(-d^2 / 2m^2) on seven standardized demographic measures (2015-19 ACS,
    from The Downballot's state tables in the gitignored data/linked/ store), m the median distance between states."""
    if "w" not in _SIM:
        d = sorted((ROOT / "data/linked/downballot").glob("*/education_income_cd.xlsx"))[-1].parent
        e = pd.read_excel(d / "education_income_cd.xlsx", sheet_name="2019 - State").set_index("State")
        x = pd.ExcelFile(d / "race_age_citizenship_cd.xlsx")
        rc = x.parse([n for n in x.sheet_names if n.startswith("Senate") and n.endswith("2019")][0], header=None).iloc[3:, :4].set_index(0)
        u = pd.read_excel(d / "urban_rural_cd118.xlsx").drop_duplicates("CD").set_index("CD")
        f = pd.DataFrame({"ba": e["Bachelor's"], "inc": np.log(e["Median Income"].astype(float)), "white": rc[1], "black": rc[2], "latino": rc[3],
                          "urban": u["Urban %"], "rural": u["Rural %"]}).astype(float)
        f = f[f.index.isin(STATE_ABBR)].dropna()
        f.index = f.index.map(STATE_ABBR)
        z = ((f - f.mean()) / f.std()).values
        dist = np.sqrt(((z[:, None, :] - z[None, :, :]) ** 2).sum(2))
        m = np.median(dist[np.triu_indices(len(f), 1)])
        _SIM["w"] = pd.DataFrame(np.exp(-dist ** 2 / (2 * m ** 2)), index=f.index, columns=f.index)
    return _SIM["w"]


def borrowed_gap(states, gap, polled):
    """For each race, the weighted mean of (poll - prior) over the cycle's other polled races."""
    W = state_similarity().reindex(index=states, columns=states).values if GOV_UNPOLLED == "demo" else np.ones((len(states), len(states)))
    W = W * polled[None, :] * (1 - np.eye(len(states)))
    return (W * np.where(polled, gap, 0.0)[None, :]).sum(1) / np.maximum(W.sum(1), 1e-9)


def gov_estimate(tr, gen_miss, a, b):
    """governor_model.estimate() on a training table (cycle, lean_avg2, env, inc, actual, poll, n): the prior, the
    weight on polls and the prior error it implies, and the two national errors. `gen_miss` is the generic ballot's
    miss by cycle; a and b are the poll-average error curve."""
    base = smf.ols(GOV_PRIORS["pres"], tr).fit()
    thin = GOV_LEAN.startswith("ratings") and tr[tr.rating.notna()].cycle.nunique() < MIN_PRIOR      # too few rated cycles yet
    prior = base if GOV_LEAN in ("pres", "ratings_unpolled") or thin else smf.ols(GOV_PRIORS[GOV_LEAN], tr).fit()
    unp_r = {}
    if GOV_LEAN == "ratings_unpolled" and not thin:
        rf = smf.ols(GOV_PRIORS["ratings"], tr).fit()
        unp_r = {"_g_unp_fit": rf, "g_sd_unp_rating": float(1.4826 * np.median(np.abs(rf.resid - np.median(rf.resid)))),
                 "g_c_unp_rating": float(rf.params["rating"])}
    # a race without the candidate's lean measure takes the baseline prior
    tr = tr.assign(prior=prior.fittedvalues if prior is base else prior.predict(tr).fillna(base.predict(tr)))
    resid = tr.actual - tr.prior
    pol = tr[tr.n > 0].copy()
    pol["y"], pol["x"], pol["yr"] = pol.actual - pol.prior, pol.poll - pol.prior, pol.cycle.astype(str)
    wfit = smf.ols("y ~ x + C(yr)", pol).fit()
    w = float(np.clip(wfit.params["x"], 0.01, 0.99))
    sd_p_typ = float(np.sqrt(np.mean(a ** 2 + b ** 2 / np.maximum(pol.n, 1))))
    unp = {}
    if GOV_UNPOLLED and "state" in tr:
        zs = pd.concat([pd.Series(borrowed_gap(x.state.values, (x.poll - x.prior).values, (x.n > 0).values), index=x.index) for _, x in tr.groupby("cycle")])
        zp = zs[pol.index]
        unp = {"g_unp_c": float((zp * pol.y).sum() / (zp ** 2).sum())}
    cyc = (pol.actual - pol.poll).groupby(pol.cycle).mean().rename("S").to_frame().join(gen_miss.rename("H"), how="inner").dropna()
    rho = float(np.corrcoef(cyc.S, cyc.H)[0, 1]) if len(cyc) >= 3 else 0.0
    return {"g_const": float(base.params["Intercept"]), "g_b_lean": float(base.params["lean_avg2"]), "g_env": float(prior.params["env"]),
            "g_inc": float(base.params["inc"]), "g_poll_w": w, "g_sd_prior": float(sd_p_typ * np.sqrt(w / (1 - w))),
            "g_sd_prior_unpolled": float(1.4826 * np.median(np.abs(resid - np.median(resid)))),
            "g_sd_S": rms(cyc.S), "g_sd_H": rms(cyc.H), "g_rho": rho if np.isfinite(rho) else 0.0,
            "g_races": int(len(tr)), "g_races_polled": int(len(pol)), "g_cycles": int(tr.cycle.nunique()),
            **({"g_sd_prior_rms": rms(resid)} if GOV_UNPOLLED_SD == "rms" else {}), **unp, **unp_r,
            **({} if prior is base else {"_g_fit": (prior, base), "g_races_lean_fit": int(prior.nobs),
                                               **{"g_c_" + k: float(v) for k, v in prior.params.items()}})}


def gov_polls(rt):
    """One poll average per state and cycle from a set of polls (the race with the most polls, if a state has two)."""
    g = BA.race_level(rt, ["Gov-G"]).sort_values("n").drop_duplicates(["cycle", "location"], keep="last")
    return g.rename(columns={"location": "state"})[["cycle", "state", "poll", "n"]]


def fundamentals_table():
    """fundamentals_dataset.csv plus a 2024 row built the way fundamentals.build() builds the others (stored FRED
    files, Gallup approval from the 538 archive), so 2024 can be forecast. Nothing is fetched."""
    f = pd.read_csv(ROOT / "data/interim/fundamentals_dataset.csv")
    if 2024 in f.year.values:
        return f

    def series(sid):
        d = pd.read_csv(latest("fred", f"{sid}.csv")); d.columns = ["date", "v"]
        d["date"] = pd.to_datetime(d.date); d["v"] = pd.to_numeric(d.v, errors="coerce")
        return d.dropna().set_index("date").v
    cpi, gas, rdi, ur = series("CPIAUCNS"), series("CUUR0000SETB01"), series("A229RX0"), series("UNRATE")
    vote = pd.read_csv(ROOT / "data/interim/house_national_vote.csv").set_index("year").two_party_margin_D
    g = pd.read_csv(latest("538_wayback", "president_approval_polls_historical.csv"), low_memory=False)
    g["end"] = pd.to_datetime(g.end_date, format="%m/%d/%y", errors="coerce")
    w = g[(g.politician == "Joe Biden") & g.pollster.str.contains("Gallup", na=False) & (g.end >= "2024-07-15") & (g.end <= "2024-10-31")]
    y = 2024
    row = dict(year=y, pres_party="D", midterm=0, outcome=float(vote[y]), prev=float(vote[y - 2]), approval=float(w.yes.mean()),
               approval_source="Gallup (538 archive)", infl=FU.yoy(cpi, y), gas=FU.yoy((gas / cpi).dropna(), y), rdi=FU.yoy(rdi, y),
               unemp=FU.yoy(ur, y, pct=False), unemp_level=float(ur.get(pd.Timestamp(year=y, month=9, day=1), np.nan)))
    return pd.concat([f, pd.DataFrame([row])], ignore_index=True).sort_values("year").reset_index(drop=True)


# ---------------------------------------------------------------- as-of parameters
def house_fit(d, cycles, rec_n=4, sd_n=5):
    """The rule behind house_structure.py's chosen values, made mechanical: national slope from every earlier cycle;
    constant, lean slope and incumbency from the latest `rec_n`; district SD from the latest `sd_n` (competitive band)."""
    cycles = sorted(cycles)
    d = d[d.year.isin(cycles)]
    g = float(smf.ols("margin ~ lean2 + nat + inc", d).fit().params["nat"])
    rec = d[d.year.isin(cycles[-rec_n:])]
    m = smf.ols("adj ~ lean2 + inc", rec.assign(adj=rec.margin - g * rec.nat)).fit()
    r5 = d[d.year.isin(cycles[-sd_n:])]
    m5 = smf.ols("margin ~ lean2 + nat + inc", r5).fit() if r5.year.nunique() > 1 else smf.ols("margin ~ lean2 + inc", r5).fit()
    e = r5.margin - m5.fittedvalues
    return {"const": float(m.params["Intercept"]), "b_lean2": float(m.params["lean2"]), "g_nat": g, "inc": float(m.params["inc"]),
            "sd_district": float(e[m5.fittedvalues.abs() <= COMP].std()), "house_cycles": cycles}


def fit_params(r, sen, hh, fund, train, late_only=True, gov=None):
    """Every estimated quantity the forecast uses, from the cycles in `train` only."""
    train = sorted(c for c in train if c not in HELD_OUT)
    rt = r[r.cycle.isin(train) & r.act2.notna() & (r.late | (not late_only))]
    rt = rt.assign(poll_m=rt.poll2, act_m=rt.act2)
    p = {"train_cycles": train}
    sen_cal, gen_cal = CAL.summarize(rt, "Sen-G"), CAL.summarize(rt, "House-G-US")
    gen_miss = pd.Series({c["cycle"]: c["mean"] for c in gen_cal["cycles"]})
    p["sd_nat_generic"] = rms(gen_miss)
    p["sd_nat_senate"] = rms([c["mean"] for c in sen_cal["cycles"]])
    w = 0.5 ** ((max(train) + 2 - gen_miss.index.values) / HALF_LIFE_BIAS)
    p["generic_bias"] = float(np.average(gen_miss, weights=w))
    p["bias_sd"] = float(gen_miss.std(ddof=1) * np.sqrt(1 + 1 / len(gen_miss)))
    p["sd_race_midterms"] = sen_cal["race_resid_sd_midterms"] if np.isfinite(sen_cal["race_resid_sd_midterms"]) else sen_cal["race_resid_sd"]
    sdn = CAL.sd_by_n(rt)
    p["sdn_a"], p["sdn_b"] = sdn["a"], sdn["b"]
    # tails
    rl = BA.race_level(rt, ["Sen-G", "Gov-G"])
    rl["resid"] = rl.err - rl.groupby("cycle").err.transform("mean")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p["df_t"] = float(min(max(stats.t.fit(rl.resid.values, floc=0)[0], 3.0), 30.0))
    # sponsored polls
    sp = PS.sponsor_shift(rt)
    p["sponsor_statewide"] = max(sp["statewide"]["shift"], 0.0) if sp["statewide"]["n_polls"] else 0.0
    p["sponsor_house"] = max(sp["house_district"]["shift"], 0.0) if sp["house_district"]["n_polls"] else 0.0
    # state lean on statewide races: Senate prior weight, regional and lean-slope error, lean correction
    lean = pd.read_csv(ROOT / "data/interim/state_presidential_history.csv").set_index(["year", "state"]).lean_2p
    rl = rl[rl.location.str.len() == 2].copy()
    rl["lean"] = [lean.get((prior_pres(c), s), np.nan) for c, s in zip(rl.cycle, rl.location)]
    rl = rl.dropna(subset=["lean"])
    rl["resid"] = rl.err - rl.groupby("cycle").err.transform("mean")
    es = ES.estimate(rl)
    p["sigma_region"], p["sigma_lean_slope"] = es["sigma_region"], es["lean_slope"]["all"]["sd_true"]
    post = rl[rl.cycle >= 2010]
    p["lean_slope"] = float(smf.ols("resid ~ lean", post).fit().params["lean"]) if post.cycle.nunique() >= 1 and len(post) > 5 else 0.0
    gen_poll = BA.race_level(rt, ["House-G-US"]).set_index("cycle").poll
    s = rl[rl.type_simple == "Sen-G"].copy()
    s["prior"] = s.lean + s.cycle.map(gen_poll)
    s["y"], s["x"] = s.act - s.prior, s.poll - s.prior
    for c in ("y", "x", "act", "prior"):
        s[c + "_d"] = s[c] - s.groupby("cycle")[c].transform("mean")
    wq = float(smf.ols("y_d ~ x_d - 1", s).fit().params["x_d"])
    wc = min(max(wq, 0.01), 0.99)
    e_prior = s.act_d - s.prior_d
    p["prior_w"] = wq
    p["sd_senate_prior"] = float(p["sd_race_midterms"] * np.sqrt(wc / (1 - wc)))
    p["sd_senate_prior_unpolled"] = float(1.4826 * np.median(np.abs(e_prior - np.median(e_prior))))
    # fundamentals: the same search as fundamentals.py, on elections before the target
    fd = fund[fund.year.isin(range(1962, max(train) + 1)) & ~fund.year.isin(HELD_OUT)].dropna(subset=FU.PREDICTORS + ["outcome"])
    specs = FU.select(fd, extra=("midterm",))[:5]
    wts = np.array([1 / x["loo_rmse"] ** 2 for x in specs]); wts /= wts.sum()
    p["_fund"] = [(x["vars"], float(wi), FU.fit(fd, x["vars"]).params.to_dict() if x["vars"] else {"const": float(fd.outcome.mean())})
                  for x, wi in zip(specs, wts)]
    p["fund_sd"] = FUND_SD_INFLATE * rms(sum(wi * x["loo_errs"] for x, wi in zip(specs, wts)))
    p["fund_n"] = int(len(fd))
    # House district model and district polls
    hc = sorted(set(hh.year) & set(train))
    p["house_cycles_n"] = len(hc)
    if len(hc) >= MIN_PRIOR:
        d = hh[hh.fit & hh.year.isin(hc)]
        hf = house_fit(d, hc)
        p.update({"h_" + k: v for k, v in hf.items() if k != "house_cycles"})
        hp = BA.race_level(rt, ["House-G"])
        hp["key"] = hp.location
        dd = hh.assign(cycle=hh.year)
        al = dd[dd.at_large].assign(key=lambda x: x.state + "-1")
        dd = pd.concat([dd[~dd.at_large], al])
        hp = hp.merge(dd[["cycle", "key", "lean2", "inc", "pvi"]], on=["cycle", "key"], how="inner").dropna(subset=["pvi"])
        hp["prior"] = hf["const"] + hf["b_lean2"] * hp.lean2 + hf["g_nat"] * hp.cycle.map(gen_poll) + hf["inc"] * hp.inc
        hp["y"], hp["x"] = hp.act - hp.prior, hp.poll - hp.prior
        for c in ("y", "x"):
            hp[c + "_d"] = hp[c] - hp.groupby("cycle")[c].transform("mean")
        wh = float(smf.ols("y_d ~ x_d - 1", hp).fit().params["x_d"])
        whc = min(max(wh, 0.02), 0.98)
        p["h_poll_w"], p["h_poll_races"] = wh, int(len(hp))
        p["h_sd_poll"] = float(hf["sd_district"] * np.sqrt((1 - whc) / whc))
    # governors
    if gov is not None and gov[gov.cycle.isin(train)].cycle.nunique() >= MIN_PRIOR:
        gt = gov[gov.cycle.isin(train)].merge(gov_polls(r[r.cycle.isin(train) & r.act2.notna() & (r.late | (r.gov_fb & GOV_FB_FIT))]), on=["cycle", "state"], how="left")
        gt["n"] = gt.n.fillna(0)
        p.update(gov_estimate(gt, gen_miss, p["sdn_a"], p["sdn_b"]))
    return p


def fundamentals_pred(p, row):
    """Democratic national margin the as-of fundamentals expect for the target year."""
    preds, ws = [], []
    for vars_, wi, coef in p["_fund"]:
        preds.append(coef.get("const", 0.0) + sum(coef[v] * float(row[v]) for v in vars_))
        ws.append(wi)
    pres = float(np.average(preds, weights=ws))
    return pres if row.pres_party == "D" else -pres


# ---------------------------------------------------------------- one cycle
def poll_table(r, cycle, ts, shift):
    """Race-level average of a cycle's late polls, sponsored polls moved `shift` points away from the sponsor."""
    x = r[(r.cycle == cycle) & (r.type_simple == ts) & r.scored & (r.late | r.gov_fb)].copy()
    x["k"] = x.ukey if ts == "Sen-G" else x.location
    sg = np.where(x.partisan.astype(str).str.upper() == "DEM", 1, np.where(x.partisan.astype(str).str.upper() == "REP", -1, 0))
    x["m"] = x.poll2 - shift * sg
    return x.dropna(subset=["k"]).groupby("k").m.agg(avg="mean", n="size", spread=lambda v: float(v.std(ddof=0))).reset_index()


def simulate(rng, p, sen, hou, sd_nat, do_house):
    df = p["df_t"]
    ts = np.sqrt((df - 2) / df)
    z = rng.standard_t(df, NSIM) * ts
    region = rng.standard_normal((NSIM, 4)) * p["sigma_region"]
    slope = rng.standard_normal(NSIM) * p["sigma_lean_slope"]

    def draw(mu, sd, state, lean, nat_scale):
        ridx = np.array([REGIONS.index(STATE_REGION.get(s, "South")) for s in state])
        corr = region[:, ridx] + slope[:, None] * lean[None, :]
        var_corr = p["sigma_region"] ** 2 + (p["sigma_lean_slope"] * lean) ** 2
        idio = np.sqrt(np.maximum(sd ** 2 - var_corr, (0.5 * sd) ** 2))
        return mu[None, :] + (nat_scale * z)[:, None] + corr + rng.standard_t(df, (NSIM, len(mu))) * ts * idio[None, :]
    out = {"senate": draw(sen.mu.values, sen.sd_race.values, sen.state.values, sen.lean.values, p["sd_nat_senate"])}
    if do_house:
        out["house"] = draw(hou.mu.values, hou.sd_race.values, hou.state.values, hou.lean2.values.astype(float), p["h_g_nat"] * sd_nat)
    return out


def gov_forecast(rng, y, G, sd_nat, p, gov_u, pt):
    """governor_model.forecast(), two-factor structure: a polled race carries the statewide-poll miss in proportion
    to its weight on polls and the environment's error in proportion to the rest."""
    g = gov_u[gov_u.cycle == y].merge(pt.rename(columns={"k": "state"}), on="state", how="left")
    g["n"] = g.n.fillna(0).astype(int)
    g["prior"] = p["g_const"] + p["g_b_lean"] * g.lean_avg2 + p["g_env"] * G + p["g_inc"] * g.inc
    if "_g_fit" in p:
        g["prior"] = p["_g_fit"][0].predict(g.assign(env=G)).fillna(p["_g_fit"][1].predict(g.assign(env=G)))
    sdp, sp = np.sqrt(p["sdn_a"] ** 2 + p["sdn_b"] ** 2 / g.n.clip(lower=1)), p["g_sd_prior"] * GOV_PRIOR_SD_SCALE
    w = np.where(g.n > 0, sp ** 2 / (sp ** 2 + sdp ** 2), 0.0)
    g["poll_weight"] = w
    g["sd_race"] = np.where(g.n > 0, GOV_SD_SCALE / np.sqrt(1 / sdp ** 2 + 1 / sp ** 2), p.get("g_sd_prior_rms", p["g_sd_prior_unpolled"]))
    g["mu"] = np.where(g.n > 0, w * g.avg.fillna(0) + (1 - w) * g.prior, g.prior)
    if "_g_unp_fit" in p:
        pr = p["_g_unp_fit"].predict(g.assign(env=G))
        use = (g.n == 0) & pr.notna()
        g["prior"], g["mu"] = np.where(use, pr, g.prior), np.where(use, pr, g.mu)
        g["sd_race"] = np.where(use, p["g_sd_unp_rating"], g.sd_race)
    if "g_unp_c" in p and (g.n > 0).any():
        z = borrowed_gap(g.state.values, (g.avg - g.prior).values, (g.n > 0).values)
        g["mu"] = np.where(g.n > 0, g.mu, g.prior + p["g_unp_c"] * z)
    df = p["df_t"]
    ts = np.sqrt((df - 2) / df)
    chi = np.sqrt(rng.chisquare(df, NSIM) / df)
    z1 = rng.standard_normal(NSIM)
    z2 = p["g_rho"] * z1 + np.sqrt(1 - p["g_rho"] ** 2) * rng.standard_normal(NSIM)
    S, H = ts * z1 / chi * p["g_sd_S"], ts * z2 / chi * sd_nat
    nat = S[:, None] * w[None, :] + (p["g_env"] * H)[:, None] * (1 - w)[None, :]
    return g, g.mu.values[None, :] + nat + rng.standard_t(df, (NSIM, len(g))) * ts * g.sd_race.values[None, :]


def forecast_cycle(y, variant, p, r, sen_u, hh, fund, seed, gov_u=None):
    gen = r[(r.cycle == y) & (r.type_simple == "House-G-US") & r.late]
    g_polls = float(gen.poll2.mean())
    adj = variant.endswith("biasadj")
    shift = p["generic_bias"] if adj else 0.0
    sd_polls = p["bias_sd"] if adj else p["sd_nat_generic"]
    nat = {"G_polls": g_polls, "n_generic_polls": int(len(gen)), "shift": shift, "df_t": p["df_t"]}
    if variant == "polls_only":
        G, sd_nat = g_polls + shift, sd_polls
    else:
        F = fundamentals_pred(p, fund[fund.year == y].iloc[0])
        w = (1 / sd_polls ** 2) / (1 / sd_polls ** 2 + 1 / p["fund_sd"] ** 2)
        G = w * (g_polls + shift) + (1 - w) * F
        sd_nat = 1 / np.sqrt(1 / sd_polls ** 2 + 1 / p["fund_sd"] ** 2)
        nat.update(fundamentals=F, w_polls=w)
    nat.update(G=G, sd_nat=sd_nat)
    # Senate
    s = sen_u[sen_u.cycle == y].merge(poll_table(r, y, "Sen-G", p["sponsor_statewide"]), left_on="key", right_on="k", how="left")
    s["n"] = s.n.fillna(0).astype(int)
    s["prior"] = s.lean + G + INC_SENATE * s.inc
    pav = s.avg + (p["lean_slope"] * s.lean if adj else 0.0)
    sd_p = np.sqrt(p["sdn_a"] ** 2 + p["sdn_b"] ** 2 / s.n.clip(lower=1))
    wp = np.where(s.n > 0, (1 / sd_p ** 2) / (1 / sd_p ** 2 + 1 / p["sd_senate_prior"] ** 2), 0.0)
    s["poll_weight"] = wp
    s["mu"] = np.where(s.n > 0, wp * pav.fillna(0) + (1 - wp) * s.prior, s.prior)
    s["sd_race"] = np.where(s.n > 0, 1 / np.sqrt(1 / sd_p ** 2 + 1 / p["sd_senate_prior"] ** 2), p["sd_senate_prior_unpolled"])
    # House
    do_house = "h_const" in p and y in set(hh.year)
    h = None
    if do_house:
        h = hh[(hh.year == y) & (hh.modeled | hh.fixed.notna())].copy()
        pt = poll_table(r, y, "House-G", p["sponsor_house"])
        h["pkey"] = np.where(h.at_large, h.state + "-1", h.key)
        h = h.merge(pt.rename(columns={"k": "pkey"}), on="pkey", how="left")
        h["n"] = h.n.fillna(0).astype(int)
        h["prior"] = p["h_const"] + p["h_b_lean2"] * h.lean2 + p["h_g_nat"] * G + p["h_inc"] * h.inc
        sd_p = np.sqrt(p["h_sd_poll"] ** 2 + np.maximum(h.spread.fillna(0), 4.0) ** 2 / h.n.clip(lower=1))
        wp = np.where(h.n > 0, (1 / sd_p ** 2) / (1 / sd_p ** 2 + 1 / p["h_sd_district"] ** 2), 0.0)
        h["poll_weight"] = wp
        h["mu"] = np.where(h.n > 0, wp * h.avg.fillna(0) + (1 - wp) * h.prior, h.prior) + shift * wp
        h["sd_race"] = np.where(h.n > 0, 1 / np.sqrt(1 / sd_p ** 2 + 1 / p["h_sd_district"] ** 2), p["h_sd_district"])
        h["lean2"] = h.lean2.fillna(0)
    sims = simulate(np.random.default_rng(seed), p, s, h, sd_nat, do_house)
    gv = None
    if gov_u is not None and "g_const" in p and y in set(gov_u.cycle):
        # its own random stream, so the Senate and House draws are the same with or without governors
        gv, sims["governor"] = gov_forecast(np.random.default_rng(seed + 5_000_000), y, G, sd_nat, p, gov_u, poll_table(r, y, "Gov-G", p["sponsor_statewide"]))
    res = {"national": nat}
    tabs = []
    for ch, t in (("senate", s), ("house", h), ("governor", gv)):
        if ch not in sims:
            continue
        m = sims[ch]
        win = m > 0
        live = np.ones(len(t), bool)
        if ch == "house":
            fx = t.fixed.notna().values & ~t.modeled.values
            win[:, fx] = (t.fixed.values[fx] == "D")[None, :]
            live = t.modeled.values
            actual_d = int(np.where(live, t.actual > 0, t.fixed == "D").sum())
        else:
            actual_d = int((t.actual > 0).sum())
        seats = win.sum(1)
        q = np.percentile(m, [10, 25, 75, 90], axis=0)
        tt = pd.DataFrame({"cycle": y, "variant": variant, "chamber": ch, "race": t.key.values, "n_polls": t.n.values,
                           "prior": t.prior.values, "poll_avg": t.avg.values, "mu": t.mu.values, "sd_race": t.sd_race.values,
                           "p_dem": win.mean(0), "q10": q[0], "q25": q[1], "q75": q[2], "q90": q[3], "actual": t.actual.values,
                           # set before the file is rounded, so a margin of exactly 15 falls the same side here and in --compare
                           "competitive": np.abs(t.mu.values) <= COMP})[live]
        tabs.append(tt)
        res[ch] = {"races": int(live.sum()), "fixed": int((~live).sum()), "seats_mean": float(seats.mean()),
                   "seats_p10": float(np.percentile(seats, 10)), "seats_p90": float(np.percentile(seats, 90)),
                   "seats_actual": actual_d, "seats_pit": float((seats < actual_d).mean() + 0.5 * (seats == actual_d).mean())}
    return res, pd.concat(tabs, ignore_index=True)


# ---------------------------------------------------------------- scores
def score(t):
    p = t.p_dem.clip(CLIP, 1 - CLIP)
    won = (t.actual > 0).astype(float)
    e = t.actual - t.mu
    return {"races": int(len(t)), "brier": float(((t.p_dem - won) ** 2).mean()),
            "log_loss": float(-(won * np.log(p) + (1 - won) * np.log(1 - p)).mean()),
            "winner_acc": float(((t.p_dem > 0.5) == (won > 0)).mean()),
            "margin_bias": float(e.mean()), "margin_mae": float(e.abs().mean()), "margin_rmse": rms(e),
            "cover80": float(((t.actual >= t.q10) & (t.actual <= t.q90)).mean()),
            "cover50": float(((t.actual >= t.q25) & (t.actual <= t.q75)).mean())}


def summarize(races, cyc):
    out = {}
    for v in VARIANTS:
        out[v] = {}
        for ch in CHAMBERS:
            t = races[(races.variant == v) & (races.chamber == ch)]
            if t.empty:
                continue
            cs = [c for c in cyc if ch in c["res"][v]]
            seats = [dict(cycle=c["cycle"], **{k: c["res"][v][ch][k] for k in ("seats_mean", "seats_p10", "seats_p90", "seats_actual", "seats_pit")})
                     for c in cs]
            sd = pd.DataFrame(seats)
            comp = t[t.mu.abs() <= COMP]
            out[v][ch] = {"cycles": sorted(int(c) for c in t.cycle.unique()), "all": score(t), "competitive": score(comp),
                          "by_cycle": {int(c): {"all": score(g), "competitive": score(g[g.mu.abs() <= COMP])} for c, g in t.groupby("cycle")},
                          "seats": {"by_cycle": seats, "cover80": float(((sd.seats_actual >= sd.seats_p10) & (sd.seats_actual <= sd.seats_p90)).mean()),
                                    "n_cycles": int(len(sd)), "mean_error": float((sd.seats_mean - sd.seats_actual).mean()),
                                    # where the result fell in the simulated seat distribution: 0.25 if the ranges are right, 0.5 if every result is in a tail
                                    "pit_spread": float((sd.seats_pit - 0.5).abs().mean()),
                                    "rmse": rms(sd.seats_mean - sd.seats_actual)}}
        nat = pd.DataFrame([dict(cycle=c["cycle"], actual=c["actual_nat"], **c["res"][v]["national"]) for c in cyc])
        out[v]["national"] = {"by_cycle": nat.round(3).to_dict("records"), "rmse": rms(nat.G - nat.actual), "bias": float((nat.G - nat.actual).mean()),
                              "cover80": float(((nat.actual - nat.G).abs() <= stats.t.ppf(0.9, nat.df_t) * np.sqrt((nat.df_t - 2) / nat.df_t) * nat.sd_nat).mean())}
    return out


def coverage(r, sen_u, hh, fund, gov_u):
    """Component by cycle: is the data there, and is the cycle scored after burn-in."""
    poll_c = sorted(c for c in r[r.source == "raw_polls"].cycle.unique())
    house_c = sorted(hh.year.unique())
    rows = []
    for y in range(1998, 2026, 2):
        rows.append({"cycle": y,
                     "generic_polls": int(((r.cycle == y) & (r.type_simple == "House-G-US") & r.late).sum()),
                     "senate_races": int((sen_u.cycle == y).sum()),
                     "senate_races_polled": int(r[(r.cycle == y) & (r.type_simple == "Sen-G") & r.scored & r.late].ukey.nunique()),
                     "house_districts_with_lean": int(((hh.year == y) & hh.pvi.notna()).sum()),
                     "house_districts_polled": int(r[(r.cycle == y) & (r.type_simple == "House-G") & r.late].location.nunique()),
                     "governor_races": int((gov_u.cycle == y).sum()),
                     "governor_races_polled": int(gov_u[gov_u.cycle == y].state.isin(r[(r.cycle == y) & (r.type_simple == "Gov-G") & r.scored & r.late].location).sum()),
                     "fundamentals": bool(y in set(fund.dropna(subset=FU.PREDICTORS).year)),
                     "prior_poll_cycles": int(sum(c < y for c in poll_c)), "prior_house_cycles": int(sum(c < y for c in house_c)),
                     "senate_scored": bool(sum(c < y for c in poll_c) >= MIN_PRIOR),
                     "house_scored": bool(sum(c < y for c in poll_c) >= MIN_PRIOR and sum(c < y for c in house_c) >= MIN_PRIOR and y in house_c)})
    return rows


def parity(r, sen_u, hh, fund):
    """The harness's estimators run on everything the frozen 2026 forecast had (every raw_polls row to 2022, districts
    to 2024), beside the frozen values: a check that the as-of fits are the same estimators. The rows that differ
    are the ones BACKTEST.md lists: state lean is now complete, the tail weight is not rounded, and the district-poll
    weight is fitted on every earlier cycle (the frozen model used 2018 and 2022)."""
    p = fit_params(r, sen_u, hh, fund, [c for c in range(1998, 2023, 2)], late_only=False)
    p.update({"h_" + k: v for k, v in house_fit(hh[hh.fit], sorted(hh.year.unique())).items() if k != "house_cycles"})
    F = ROOT / "data" / "final"
    cal, hs, pw = json.loads((F / "calibration.json").read_text()), json.loads((F / "house_structure.json").read_text()), json.loads((F / "prior_weight.json").read_text())
    es, ps = json.loads((F / "error_structure.json").read_text()), json.loads((F / "poll_settings.json").read_text())
    fz = {"sd_nat_generic": rms([c["mean"] for c in cal["House-G-US"]["cycles"]]), "sd_nat_senate": rms([c["mean"] for c in cal["Sen-G"]["cycles"] if c["cycle"] % 2 == 0]),
          "sdn_a": cal["pollavg_sd_by_n"]["a"], "sdn_b": cal["pollavg_sd_by_n"]["b"], "df_t": ps["chosen"]["df_t"],
          "prior_w": pw["w"], "sd_senate_prior": pw["implied_prior_sd"], "sd_senate_prior_unpolled": pw["prior_sd_robust"],
          "sigma_region": es["sigma_region"], "sigma_lean_slope": es["lean_slope"]["all"]["sd_true"],
          "sponsor_statewide": ps["sponsor"]["statewide"]["shift"], "sponsor_house": ps["sponsor"]["house_district"]["shift"],
          "h_const": hs["chosen"]["const"], "h_b_lean2": hs["chosen"]["b_lean2"], "h_g_nat": hs["chosen"]["g_nat"], "h_inc": hs["chosen"]["inc"],
          "h_sd_district": hs["chosen"]["sd_district"],
          "h_poll_w": hs["district_polls"]["w"], "h_sd_poll": hs["district_polls"]["implied_poll_sd"]}
    return [{"parameter": k, "as_of_all_data": float(p[k]), "frozen_2026": float(v)} for k, v in fz.items()]


def parity_governor():
    """gov_estimate() on governor_model.py's own sample, polls and constants, beside governor_model.json: a check that
    the as-of governor fit is that model's estimator. (The as-of runs differ in data: even years, 21-day polls.)"""
    import governor_model as GM
    global GOV_LEAN
    keep, GOV_LEAN = GOV_LEAN, "pres"       # that model has the baseline lean only
    d = GM.load()
    t = pd.DataFrame({"cycle": d.year.values, "lean_avg2": d.lean_avg2.values, "env": d.env.values, "inc": d.inc.values, "actual": d.margin_2p.values,
                      "poll": d.poll_avg.values, "n": d.n_polls.fillna(0).values})
    e = gov_estimate(t[t.env.notna()], GM.generic_final().generic_miss, GM.SDN["a"], GM.SDN["b"])
    GOV_LEAN = keep
    m = json.loads((OUT / "governor_model.json").read_text())
    ref = {"g_const": m["prior_coef"]["Intercept"], "g_b_lean": m["prior_coef"]["lean_avg2"], "g_env": m["prior_coef"]["env"], "g_inc": m["prior_coef"]["inc"],
           "g_poll_w": m["params"]["w"], "g_sd_prior": m["params"]["sd_prior_implied"], "g_sd_prior_unpolled": m["params"]["sd_prior_robust"],
           "g_sd_S": m["params"]["sd_S"], "g_sd_H": m["params"]["sd_H"], "g_rho": m["params"]["rho"]}
    return [{"parameter": k, "harness_estimator": float(e[k]), "governor_model": float(v)} for k, v in ref.items()]


def compare(tag):
    """A candidate run against the baseline on the baseline's races: the competitive set is fixed by the baseline's
    forecast margins, so both are scored on the same contests. Differences are candidate minus baseline (negative
    log loss and Brier differences are improvements)."""
    def races(sfx):
        t, jp = pd.read_csv(OUT / f"backtest_asof{sfx}_races.csv"), jacobson_path()
        extra = jp.parent / f"backtest_asof{sfx}_races_jacobson.csv" if jp else None
        return pd.concat([t, pd.read_csv(extra)], ignore_index=True) if extra is not None and extra.exists() else t
    base, new = races(""), races(f"_{tag}")
    keys = ["cycle", "variant", "chamber", "race"]
    j = base.merge(new, on=keys, suffixes=("_b", "_n"))
    print(f"{len(j)} of {len(base)} baseline race forecasts matched in '{tag}'")
    out = {}
    for (v, ch), g in j[j.competitive_b.astype(bool)].groupby(["variant", "chamber"]):
        rows = []
        for c, x in list(g.groupby("cycle")) + [("all", g), ("all but first", g[g.cycle > g.cycle.min()])]:
            b = score(x.rename(columns=lambda k: k[:-2] if k.endswith("_b") else k).assign(actual=x.actual_b))
            n = score(x.rename(columns=lambda k: k[:-2] if k.endswith("_n") else k).assign(actual=x.actual_b))
            rows.append({"cycle": c, "races": b["races"], **{f"d_{k}": n[k] - b[k] for k in ("log_loss", "brier", "margin_rmse", "cover80")}})
        d = pd.DataFrame(rows)
        cyc = d[~d.cycle.astype(str).str.startswith("all")]
        # how far the pooled gap could move if history had dealt other cycles: whole cycles redrawn with replacement
        won = (g.actual_b > 0).astype(float)
        ll = lambda q: -(won * np.log(q.clip(CLIP, 1 - CLIP)) + (1 - won) * np.log(1 - q.clip(CLIP, 1 - CLIP)))  # noqa: E731
        per = pd.DataFrame({"cycle": g.cycle.values, "d": (ll(g.p_dem_n) - ll(g.p_dem_b)).values}).groupby("cycle").d.agg(["sum", "size"])
        rng = np.random.default_rng(0)
        pick = rng.integers(0, len(per), (4000, len(per)))
        boot = per["sum"].values[pick].sum(1) / per["size"].values[pick].sum(1)
        lo, hi = np.percentile(boot, [10, 90])
        out[f"{v}/{ch}"] = {"by_cycle": rows, "cycles_improved": int((cyc.d_log_loss < 0).sum()), "cycles": int(len(cyc)),
                            "pooled_d_log_loss": float(per["sum"].sum() / per["size"].sum()), "pooled_d_log_loss_sd_over_cycles": float(boot.std()),
                            "pooled_d_log_loss_80pct_range_over_cycles": [float(lo), float(hi)], "share_of_redraws_improved": float((boot < 0).mean())}
        print(f"\n{v} / {ch}: log loss better in {int((cyc.d_log_loss < 0).sum())} of {len(cyc)} cycles; "
              f"pooled gap {per['sum'].sum() / per['size'].sum():+.4f}, SD with cycles redrawn {boot.std():.4f} "
              f"(80% between {lo:+.4f} and {hi:+.4f}, better in {(boot < 0).mean():.0%} of redraws)")
        print(d.round(4).to_string(index=False))
    sb, sn = (json.loads((OUT / f"backtest_asof{x}.json").read_text())["scores"] for x in ("", f"_{tag}"))
    print("\nseat counts (baseline -> candidate): spread of the result's position in the simulated distribution (0.25 is calibrated), RMSE")
    for v in VARIANTS:
        for ch in CHAMBERS:
            if ch in sb[v] and ch in sn[v]:
                b, n = sb[v][ch]["seats"], sn[v][ch]["seats"]
                out[f"{v}/{ch}"]["seats"] = {"pit_spread": [b["pit_spread"], n["pit_spread"]], "rmse": [b["rmse"], n["rmse"]]}
                print(f"  {v:28} {ch:6} spread {b['pit_spread']:.3f} -> {n['pit_spread']:.3f}   RMSE {b['rmse']:.2f} -> {n['rmse']:.2f}")
    (OUT / f"backtest_asof_{tag}_vs_baseline.json").write_text(json.dumps(out, indent=1, default=float))


def main(tag=None, seed_shift=0, lean="cook", gov_lean="pres", gov_fb=None, gov_unpolled_sd="robust", gov_unpolled=None, gov_scales=(1.0, 1.0)):
    global GOV_LEAN, GOV_FB_FIT, GOV_UNPOLLED_SD, GOV_UNPOLLED, GOV_PRIOR_SD_SCALE, GOV_SD_SCALE
    GOV_PRIOR_SD_SCALE, GOV_SD_SCALE = gov_scales
    GOV_LEAN, GOV_FB_FIT, GOV_UNPOLLED_SD, GOV_UNPOLLED = gov_lean, gov_fb != "forecast", gov_unpolled_sd, gov_unpolled
    pd.set_option("display.width", 220)
    sfx = f"_{tag}" if tag else ""
    r = gov_fallback(load_polls()) if gov_fb else load_polls()
    jp = jacobson_path()
    if jp is None:
        print(f"data/raw/jacobson/*/{JACOBSON} is not on this machine (it is not in the repo): the House starts in 2006 and is "
              f"scored from 2012, so the House scores will not match BACKTEST.md.")
    sen_u, hh, fund = senate_universe(r), house_universe(jacobson_raw() if jp else None, lean), fundamentals_table()
    gov_u = governor_universe()
    r = link_senate(r, sen_u)
    vote = pd.read_csv(ROOT / "data/interim/house_national_vote.csv").set_index("year").two_party_margin_D
    hh["nat"] = hh.year.map(vote)
    cov = coverage(r, sen_u, hh, fund, gov_u)
    poll_cycles = sorted(int(c) for c in r.cycle.unique() if c not in HELD_OUT)
    cyc, tabs, prm = [], [], []
    for row in cov:
        y = row["cycle"]
        if not row["senate_scored"] or y in HELD_OUT:
            continue
        p = fit_params(r, sen_u, hh, fund, [c for c in poll_cycles if c < y], gov=gov_u)
        if not row["house_scored"]:
            p = {k: v for k, v in p.items() if not k.startswith("h_")}
        res = {}
        for i, v in enumerate(VARIANTS):
            res[v], t = forecast_cycle(y, v, p, r, sen_u, hh, fund, seed=y * 10 + i + 100000 * seed_shift, gov_u=gov_u)
            tabs.append(t)
        cyc.append({"cycle": y, "res": res, "actual_nat": float(vote[y])})
        prm.append(dict(cycle=y, **{k: v for k, v in p.items() if not k.startswith("_") and k != "train_cycles"}, n_train=len(p["train_cycles"])))
        print(y, "G polls %+.1f, +fund %+.1f, actual %+.1f | Senate %d races | House %s" % (
            res["polls_only"]["national"]["G"], res["polls_fundamentals"]["national"]["G"], vote[y], res["polls_only"]["senate"]["races"],
            ("%d seats modeled" % res["polls_only"]["house"]["races"]) if "house" in res["polls_only"] else "not scored"))
    races = pd.concat(tabs, ignore_index=True)
    # district rows of the cycles that come from Jacobson's file would let his lean be worked back out of the prior:
    # they are scored in the totals below but written beside his file, outside the repo
    held = (races.chamber == "house") & (races.cycle.isin(JACOBSON_YEARS) | (lean == "jacobson"))
    races[~held].round(4).to_csv(OUT / f"backtest_asof{sfx}_races.csv", index=False)
    if jp:
        races[held].round(4).to_csv(jp.parent / f"backtest_asof{sfx}_races_jacobson.csv", index=False)
    pd.DataFrame(prm).round(4).to_csv(OUT / f"backtest_asof{sfx}_params.csv", index=False)
    summ = summarize(races, cyc)
    out = {"min_prior_cycles": MIN_PRIOR, "nsim": NSIM, "clip": CLIP, "competitive_band": COMP, "held_out": list(HELD_OUT),
           "house_districts": {"2006 on": "data/interim/house_history.csv (Cook PVI)",
                               "1998-2004": None if jp is None else {"source": "Gary Jacobson, House elections file (not in the repo)", "file": JACOBSON,
                                                                     "received": jp.parent.name, "sha256": hashlib.sha256(jp.read_bytes()).hexdigest()},
                               "lean_2006_on": lean},
           "governor_lean": gov_lean, "governor_unpolled_sd": gov_unpolled_sd, "governor_unpolled": gov_unpolled, "governor_prior_sd_scale": GOV_PRIOR_SD_SCALE, "governor_sd_scale": GOV_SD_SCALE, "governor_poll_fallback": {"days": list(FALLBACK_DAYS), "used_in": gov_fb} if gov_fb else None,
           "coverage": cov, "wayback_check": wayback_check(r), "parity": parity(r, sen_u, hh[hh.source == "house_history"], fund), "parity_governor": parity_governor(), "scores": summ}
    (OUT / f"backtest_asof{sfx}.json").write_text(json.dumps(out, indent=1, default=float))
    for v in VARIANTS:
        for ch in CHAMBERS:
            if ch in summ[v]:
                a, c, s = summ[v][ch]["all"], summ[v][ch]["competitive"], summ[v][ch]["seats"]
                print(f"{v:28} {ch:8} {summ[v][ch]['cycles'][0]}-{summ[v][ch]['cycles'][-1]} n={a['races']:5d} Brier {a['brier']:.4f} logloss {a['log_loss']:.4f} "
                      f"| competitive n={c['races']} Brier {c['brier']:.3f} logloss {c['log_loss']:.3f} RMSE {c['margin_rmse']:.2f} bias {c['margin_bias']:+.2f} "
                      f"cover80 {c['cover80']:.2f} cover50 {c['cover50']:.2f} | seats in 80% {s['cover80']:.2f} of {s['n_cycles']}, spread {s['pit_spread']:.2f}, mean err {s['mean_error']:+.1f}, RMSE {s['rmse']:.1f}")
        n = summ[v]["national"]
        print(f"{v:28} national environment RMSE {n['rmse']:.2f}, bias {n['bias']:+.2f}, in 80% {n['cover80']:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag"); ap.add_argument("--compare"); ap.add_argument("--seed-shift", type=int, default=0)
    ap.add_argument("--house-lean", choices=("cook", "jacobson"), default="cook")
    ap.add_argument("--gov-lean", choices=tuple(GOV_PRIORS), default="pres")
    ap.add_argument("--gov-poll-fallback", choices=("all", "forecast"))
    ap.add_argument("--gov-unpolled-sd", choices=("robust", "rms"), default="robust")
    ap.add_argument("--gov-unpolled", choices=("flat", "demo"))
    ap.add_argument("--gov-prior-sd-scale", type=float, default=1.0); ap.add_argument("--gov-sd-scale", type=float, default=1.0)
    a = ap.parse_args()
    if a.compare:
        compare(a.compare)
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)     # empty region cells in the first cycles
            main(a.tag, a.seed_shift, a.house_lean, a.gov_lean, a.gov_poll_fallback, a.gov_unpolled_sd, a.gov_unpolled, (a.gov_prior_sd_scale, a.gov_sd_scale))
