"""EC-6: simulation and outputs (ELECTORAL_COLLEGE.md, section 15).

The assembly of EC-2 to EC-5 into one simulation of the electoral college, the two spreads the earlier cards left to
it (each state's range by days out and poll count; the national range around the adopted centre), and the card's
tests under section 8's rule: two range candidates (R1 lopsided, R2 unusual), two turnout-share candidates (T1 own
trend, T2 population growth) and a demographic swing model for Maine's and Nebraska's districts (D1).

  one draw      margin_s = mu_s + eta + eps_s,   eps = D (h_c + e * sqrt(diag C_own)),  h_c ~ N(0, P_v C_sh P_v'),  e ~ t_nu own
                C = corr(A) is EC-5's structure (similarity, tilt, white-without-a-degree draw) split into its shared
                part C_sh and the states' own part C_own; P_v = I - 1 v' centres the shared part on the turnout shares
                before it is sized, so it carries no level; D_s makes each state's lean error's spread the range model's s_s; eta ~ t_nu is the remainder that makes the
                popular vote's spread the national range sigma_N(d).
  districts     margin_d = margin_s + lean_d + eps_d, one spread sigma_D for the five, F's weight on district polls.
  the count     exact given the shared draws: a convolution over the contests, Maine and Nebraska as blocks integrating
                the state's own error; averaged over 40,000 shared draws. The tipping point, the gap, the popular vote's
                split and the quantiles come from plain simulation on the same draws.
  range R0      s^2 = a + b / (1 + n) + c * days, maximum likelihood on the centred misses (the lean error) of the
                elections before the scored one; R1 multiplies by exp(e |prior| / 10), R2 by exp(f u), u = 1 - mean kernel row.
  national      sigma_N^2(d) = a_N + b_N * days by least squares on (natF - result)^2, 1952 on, days 7 to 150.

Run:  python src/model/pres_sim.py checks     (planted inputs and identities; prints pass or fail only)
      python src/model/pres_sim.py run        (the one round: the tests, the reports; the as-of outputs are written, not printed)
      python src/model/pres_sim.py asof       (part D alone, with the adopted turnout weights read from pres_sim.json)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm, t as student_t

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
import pres_prior as PP  # noqa: E402
import pres_reversion as RV  # noqa: E402
import pres_errors as PE  # noqa: E402
import pres_nowcast as P  # noqa: E402

INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed"
FIT_ONLY = (2000, 2004)
SCORED = (2008, 2012, 2016, 2020)
ELECTIONS = FIT_ONLY + SCORED
ALL_DAYS = (150, 100, 60, 30, 7)
SIM_DAYS = (100, 60, 30, 7)
SCORE_DAY = 7
RANGE_DAYS = {2000: (30, 7), 2004: (30, 7), 2008: ALL_DAYS, 2012: ALL_DAYS, 2016: ALL_DAYS, 2020: ALL_DAYS}
STRUCTURE = "c3c2"                     # EC-5's confirmed structure: similarity, tilt, the white-without-a-degree draw
NSIM = 40_000
SEED = 2028
MC_SEEDS = (2028, 1, 2, 3, 4)
SHUFFLES = 200
SEEDS = {"R1": 6, "R2": 7, "T1": 8, "T2": 9, "D1": 10}
NEED = 3
TOL = 1e-5
NODES = 64                             # equal-probability nodes of the Student-t for a state's own error in a block
LAMBDAS = np.round(np.arange(0, 2.0001, 0.05), 2)
DISTRICTS = ["ME-1", "ME-2", "NE-1", "NE-2", "NE-3"]
NAT_FLOOR = 1.0                        # stage 3's floor on the national variance
NU_MIN = 2.5                           # a fitted nu below this is set to it: the variance must exist (nu > 2)


# ------------------------------------------------------------------------------------------------ inputs
def load():
    """Per (election, date): the centre as EC-2 to EC-4 leave it, the result, the miss, the previous lean, the baseline
    prior, the effective poll count, the turnout shares, F's weight and the national forecast. 2000 and 2004 at 30 and
    7 days only (2004's earlier dates kept stage 4's estimate and are not used here)."""
    q, R, Nd, L, votes = PP.load_all()
    A = PP.assemble(PP.poll_cells(q), Nd, R, L, votes)
    EF, wF = PP.rung(A, "F")
    E = RV.load()
    assert 2024 not in E and max(y for y, _ in R) <= 2020
    cells = {}
    for y in ELECTIONS:
        for d in RANGE_DAYS[y]:
            a = A[(y, d)]
            if y in PP.SCORED and wF.get((y, d)):
                mu, w = EF[(y, d)], float(wF[(y, d)][0])
            else:
                mu, w = PP.estimate(a, "prior0", 1.0), 1.0
            natF = float(E[y]["N"][d]) * (1 - float(E[y]["u"][d]) / 100)
            C = mu + (natF - float(a["v"] @ mu))
            cells[(y, d)] = {"states": list(PP.STATES), "mu": C, "mu0": np.asarray(mu, float).copy(), "result": a["result"].copy(), "miss": a["result"] - C,
                             "lean": a["lean1"].copy(), "prior0": a["prior0"].copy(), "n": a["n"].copy(),
                             "has": a["has"].copy(), "v": a["v"].copy(), "w": w, "natF": natF}
    return cells, E, q


def national_errors(E):
    """(election, day) -> natF - result for every election the national series has, days 7 to 150."""
    out = {}
    for y, e in E.items():
        for d in RV.RANGE_DAYS:
            natF = float(e["N"][d]) * (1 - float(e["u"][d]) / 100)
            if np.isfinite(natF):
                out[(y, d)] = natF - float(e["result"])
    return out


def national_range(nat_err, before):
    rows = [(d, err ** 2) for (y, d), err in nat_err.items() if y < before]
    a, b = RV.range_fit(rows)
    return a, b


def sigma_nat(ab, d):
    return float(np.sqrt(max(ab[0] + ab[1] * d, NAT_FLOOR)))


def centred(c):
    """The lean error: each state's miss less the vote-weighted mean miss."""
    m = c["miss"]
    return m - float(c["v"] @ m)


# ------------------------------------------------------------------------------------------------ EC-5's structure
def structure_cells(cells, demo):
    M = {(y, 7): {"states": cells[(y, 7)]["states"], "miss": cells[(y, 7)]["miss"], "lean": cells[(y, 7)]["lean"]}
         for y in ELECTIONS}
    ecells, Q, states = PE.build_cells(M, demo, d=7)
    return ecells, Q, states


def fit_structure(ecells, Q, before):
    train = [(PE.comps_for(STRUCTURE, c["Rm"], c["lean"], c["feat"]), c["ym"], None) for e, c in ecells.items() if e < before]
    rho, s2, _, _ = PE.fit(train, Q, 3)
    keys = list(PE.comps_for(STRUCTURE, ecells[ELECTIONS[0]]["Rm"], ecells[ELECTIONS[0]]["lean"], ecells[ELECTIONS[0]]["feat"]))
    return dict(zip(keys, map(float, rho)))


def correlation_parts(ecell, rho):
    """C = corr(A) at this election's features, split into the shared part and the states' own (diagonal) part."""
    comps = PE.comps_for(STRUCTURE, ecell["Rm"], ecell["lean"], ecell["feat"])
    n = len(ecell["lean"])
    A = np.eye(n)
    for k, Cm in comps.items():
        A = A + rho[k] * Cm
    dinv = 1.0 / np.sqrt(np.diag(A))
    C = A * dinv[:, None] * dinv[None, :]
    C_own = np.diag(dinv ** 2)
    return C, C - C_own, np.diag(C_own).copy()


def unusual(ecell):
    K = PE.kernel(ecell["feat"]["M"])
    n = len(K)
    return 1.0 - (K.sum(1) - 1.0) / (n - 1)


# ------------------------------------------------------------------------------------------------ the range (B)
def range_rows(cells, before, days=None):
    """Rows for the range fit: the centred misses of the elections before `before` at their dates."""
    out = []
    for (y, d), c in cells.items():
        if y < before and (days is None or d in days):
            out.append(dict(r=centred(c), n=c["n"], days=float(d), lop=np.abs(c["prior0"]) / 10.0, y=y, d=d))
    return out


def spread2(theta, row, kind, u=None):
    s2 = theta[0] + theta[1] / (1.0 + row["n"]) + theta[2] * row["days"]
    if kind in ("R1", "R12"):
        s2 = s2 * np.exp(theta[3] * row["lop"])
    if kind in ("R2", "R12"):
        s2 = s2 * np.exp(theta[-1] * u[row["y"]])
    return s2


def nparams(kind):
    return {"R0": 3, "R1": 4, "R2": 4, "R12": 5}[kind]


def range_nll(theta, rows, kind, u):
    tot = 0.0
    for row in rows:
        s2 = spread2(theta, row, kind, u)
        tot += 0.5 * float(np.sum(np.log(2 * np.pi * s2) + row["r"] ** 2 / s2))
    return tot


def fit_range(rows, kind, u=None):
    k = nparams(kind)
    bounds = [(1e-6, None), (0.0, None), (0.0, None)] + [(0.0, None)] * (k - 3)
    best = None
    for scale in (0.25, 1.0, 4.0):
        x0 = np.array([4.0 * scale, 4.0 * scale, 0.02 * scale] + [0.0] * (k - 3))
        o = minimize(range_nll, x0, args=(rows, kind, u), method="L-BFGS-B", bounds=bounds)
        if best is None or o.fun < best.fun - 1e-12:
            best = o
    return np.array(best.x, float)


def range_score(theta, cell, kind, u):
    row = dict(r=centred(cell), n=cell["n"], days=float(cell["d"]) if "d" in cell else None, lop=np.abs(cell["prior0"]) / 10.0, y=cell["y"])
    s2 = spread2(theta, row, kind, u)
    return float(np.sum(norm.logpdf(row["r"], 0.0, np.sqrt(s2)))), np.sqrt(s2), row["r"]


def subset_cells(cells, mask):
    """The cells restricted to a subset of states (report d), turnout shares renormalized."""
    out = {}
    for k, c in cells.items():
        c2 = dict(c)
        for f in ("mu", "result", "miss", "lean", "prior0", "n", "has"):
            c2[f] = c[f][mask]
        c2["v"] = c["v"][mask] / c["v"][mask].sum()
        c2["states"] = [s_ for s_, m_ in zip(c["states"], mask) if m_]
        out[k] = c2
    return out


def cell_with(cells, y, d):
    c = dict(cells[(y, d)]); c["y"] = y; c["d"] = d
    return c


def run_range(cells, kind, u=None, years=SCORED, day=SCORE_DAY, perm=None, states=None):
    """Fit on the elections before each scored one and score it at `day`. perm reorders the states' feature (|prior|
    for R1, u for R2); states restricts to a subset (report d, without DC)."""
    out = {}
    for y in years:
        rows = range_rows(cells, y)
        uu = u
        if perm is not None:
            if kind == "R1":
                rows = [dict(r, lop=r["lop"][perm]) for r in rows]
            if kind == "R2":
                uu = {yy: v[perm] for yy, v in u.items()}
        if states is not None:
            rows = [dict(r, r=r["r"][states], n=r["n"][states], lop=r["lop"][states]) for r in rows]
            if uu is not None:
                uu = {yy: v[states] for yy, v in uu.items()}
        theta = fit_range(rows, kind, uu)
        c = cell_with(cells, y, day)
        if perm is not None and kind == "R1":
            c["prior0"] = c["prior0"][perm]
        if states is not None:
            c = dict(c, miss=c["miss"][states], v=c["v"][states] / c["v"][states].sum(), n=c["n"][states], prior0=c["prior0"][states])
        ld, sd, r = range_score(theta, c, kind, uu)
        out[y] = {"ld": ld, "theta": [float(x) for x in theta], "sd": sd, "r": r}
    return out


def pooled(res, years=SCORED):
    return float(np.mean([res[y]["ld"] for y in years]))


def verdict(base, cand, shuffled, years=SCORED, need=NEED):
    gain = pooled(cand, years) - pooled(base, years)
    by = {int(y): cand[y]["ld"] - base[y]["ld"] for y in years}
    better = int(sum(v > TOL for v in by.values()))
    p95 = float(np.percentile(shuffled, 95)) if len(shuffled) else None
    out = {"gain": gain, "by_election": by, "better": better, "need": need, "shuffles": len(shuffled),
           "shuffle_p95": p95, "shuffle_share_beaten": float(np.mean(np.array(shuffled) < gain - TOL)) if len(shuffled) else None,
           "shuffled_gains": [round(float(g), 6) for g in shuffled],
           "clause_positive": gain > TOL, "clause_elections": better >= need,
           "clause_shuffle": (p95 is not None and gain > p95 + TOL)}
    out["passes"] = bool(out["clause_positive"] and out["clause_elections"] and out["clause_shuffle"])
    return out


def shuffled_gains_range(cells, kind, u, base, seed, shuffles, years=SCORED):
    rng = np.random.default_rng(seed)
    n = len(cells[(ELECTIONS[0], 7)]["states"])
    gains = []
    for _ in range(shuffles):
        perm = rng.permutation(n)
        res = run_range(cells, kind, u, years, perm=perm)
        gains.append(pooled(res, years) - pooled(base, years))
    return gains


def coverage(res, nu=None):
    """Share of centred misses inside the 50% and 80% ranges: Gaussian quantiles, and (if nu, a dict by election)
    each election's Student-t quantiles scaled to unit variance, so the spread is the same and only the shape differs."""
    out = {}
    r = np.concatenate([v["r"] for v in res.values()]); s = np.concatenate([v["sd"] for v in res.values()])
    out["normal"] = {"p50": float(np.mean(np.abs(r) <= norm.ppf(0.75) * s)), "p80": float(np.mean(np.abs(r) <= norm.ppf(0.90) * s))}
    if nu:
        def tq(p, df):
            return norm.ppf(p) if df > 1e5 else student_t.ppf(p, df) * np.sqrt((df - 2) / df)
        z50 = np.concatenate([np.full(len(v["r"]), tq(0.75, nu[y])) for y, v in res.items()])
        z80 = np.concatenate([np.full(len(v["r"]), tq(0.90, nu[y])) for y, v in res.items()])
        out["t"] = {"p50": float(np.mean(np.abs(r) <= z50 * s)), "p80": float(np.mean(np.abs(r) <= z80 * s))}
    return out


def fit_nu(cells, theta, kind, u, before):
    """Student-t degrees of freedom by maximum likelihood (location 0) on the standardized centred misses of the fitting
    elections under the fitted range model; the fitted scale is reported beside it (about 1 if the range is right)."""
    z = []
    for row in range_rows(cells, before):
        s2 = spread2(theta, row, kind, u)
        z.append(row["r"] / np.sqrt(s2))
    z = np.concatenate(z)
    df, _, scale = student_t.fit(z, floc=0)
    return float(max(df, NU_MIN)), float(scale), int(len(z))


# ------------------------------------------------------------------------------------------------ turnout (C)
def shares():
    r = pd.read_csv(INTERIM / "state_presidential.csv")
    r = r[r.year <= 2020]
    assert r.year.max() <= 2020
    tot = r.assign(t=r.d_votes + r.r_votes)
    sh = tot.pivot(index="state", columns="year", values="t")
    sh = sh / sh.sum(axis=0)
    marg = r.pivot(index="state", columns="year", values="margin_2p")
    nat = r.groupby("year").national_margin_2p.first()
    return sh.sort_index(), marg.sort_index(), nat


def populations():
    D = pd.read_csv(INTERIM / "state_demographics.csv")
    V = pd.read_csv(INTERIM / "state_demographics_vintages.csv")
    V = V[V.election <= 2020].set_index("election")
    pop = D.pivot(index="state", columns="year", values="population").sort_index()
    return pop, V.year_before.to_dict()


def growth(kind, y, sh, pop, vint):
    """g_s for candidate kind at election y, or None if the data do not reach."""
    if kind == "T1":
        if (y - 8) not in sh.columns:
            return None
        return (sh[y - 4] / sh[y - 8]).values
    if kind == "T2":
        if y not in vint or (y - 4) not in vint:
            return None
        y1, y0 = vint[y], vint[y - 4]
        if y1 == y0:
            return None
        return ((pop[y1] / pop[y0]) ** (4.0 / (y1 - y0))).values
    raise ValueError(kind)


def pv_error(v, y, marg, nat):
    return float(v @ marg[y].values - nat[y])


def turnout_weights(y, sh, g, lam):
    base = sh[y - 4].values
    if g is None or lam == 0:
        v = base
    else:
        v = base * g ** lam
    return v / v.sum()


def run_turnout(kind, sh, marg, nat, pop, vint, years=SCORED, perm=None):
    """lambda fitted on the elections before each scored one (grid), scored as the squared popular-vote error."""
    all_years = [y for y in ELECTIONS if growth(kind, y, sh, pop, vint) is not None]
    G = {y: growth(kind, y, sh, pop, vint) for y in all_years}
    if perm is not None:
        G = {y: g[perm] for y, g in G.items()}
    out = {}
    for y in years:
        train = [e for e in all_years if e < y]
        if y not in G:
            out[y] = None
            continue
        best = None
        for lam in LAMBDAS:
            loss = float(np.mean([pv_error(turnout_weights(e, sh, G[e], lam), e, marg, nat) ** 2 for e in train])) if train else 0.0
            if best is None or loss < best[0] - 1e-12:
                best = (loss, float(lam))
        lam = best[1]
        err = pv_error(turnout_weights(y, sh, G[y], lam), y, marg, nat)
        out[y] = {"sq": err ** 2, "err": err, "lambda": lam, "train": train}
    return out


def turnout_verdict(base, cand, shuffled, years):
    sb = {y: base[y]["sq"] for y in years}; sc = {y: cand[y]["sq"] for y in years if cand[y] is not None}
    ys = [y for y in years if y in sc]
    gain = float(np.mean([sb[y] for y in ys]) - np.mean([sc[y] for y in ys]))
    by = {int(y): sb[y] - sc[y] for y in ys}
    better = int(sum(v > 1e-12 for v in by.values()))
    p95 = float(np.percentile(shuffled, 95)) if len(shuffled) else None
    collapse = all(cand[y]["lambda"] == 0 for y in ys)
    out = {"gain_sq_points": gain, "by_election": by, "better": better, "need": NEED, "years": ys,
           "shuffle_p95": p95, "shuffled_gains": [round(float(g), 8) for g in shuffled],
           "lambda_by_election": {int(y): cand[y]["lambda"] for y in ys}, "collapse_lambda_zero": collapse,
           "clause_positive": gain > 1e-12, "clause_elections": better >= NEED, "clause_shuffle": p95 is not None and gain > p95 + 1e-12}
    out["passes"] = bool(not collapse and out["clause_positive"] and out["clause_elections"] and out["clause_shuffle"])
    return out


def shuffled_gains_turnout(kind, sh, marg, nat, pop, vint, base, seed, shuffles, years=SCORED):
    rng = np.random.default_rng(seed)
    n = len(sh)
    gains = []
    for _ in range(shuffles):
        perm = rng.permutation(n)
        res = run_turnout(kind, sh, marg, nat, pop, vint, years, perm=perm)
        ys = [y for y in years if res[y] is not None]
        gains.append(float(np.mean([base[y]["sq"] - res[y]["sq"] for y in ys])))
    return gains


# ------------------------------------------------------------------------------------------------ districts (A5, A7)
def district_table():
    D = pd.read_csv(INTERIM / "district_presidential.csv")
    assert D.year.max() <= 2020
    return D


def district_lean(D, y, contest):
    """The district's lean against its state at the election before y, on the lines the page reports."""
    r = D[(D.year == y - 4) & (D.contest == contest)]
    return float(r.lean_vs_state.iloc[0]) if len(r) else np.nan


def district_sigma(D, before):
    """One spread for the five: the root mean squared change in lean_vs_state from one election to the next, over the
    elections from 2004 up to the one before `before`."""
    ch = []
    for contest in DISTRICTS:
        s = D[D.contest == contest].set_index("year").lean_vs_state
        for y in range(2004, before, 4):
            if y in s.index and (y - 4) in s.index:
                ch.append(s[y] - s[y - 4])
    ch = np.array(ch)
    return float(np.sqrt(np.mean(ch ** 2))), len(ch), {c: float(np.sqrt(np.mean([(D[(D.contest == c) & (D.year == y)].lean_vs_state.iloc[0] - D[(D.contest == c) & (D.year == y - 4)].lean_vs_state.iloc[0]) ** 2 for y in range(2004, before, 4) if ((D.contest == c) & (D.year == y)).any() and ((D.contest == c) & (D.year == y - 4)).any()]))) for c in DISTRICTS}


def district_poll(q, y, d, contest):
    """The district's nowcast at the date, from its own polls (none before 2016), or nan."""
    el = q[q.cycle == y].election.iloc[0]
    tdate = el - pd.Timedelta(days=d)
    pool = q[(q.cycle == y) & (q.geo == contest) & (q.end < tdate)]
    if not len(pool):
        return np.nan
    return float(P.average(pool, tdate, P.BASE))


def district_centres(cells, q, D, y, d, states, beta_x=None):
    """The five districts' centres: the state's final centre plus the district's previous lean (plus beta x_d if D1 is
    adopted), pulled toward the district's own polls by F's weight at that date."""
    c = cells[(y, d)]
    out = {}
    for contest in DISTRICTS:
        st = contest[:2]
        prior = float(c["mu"][states.index(st)]) + district_lean(D, y, contest) + (0.0 if beta_x is None else beta_x.get(contest, 0.0))
        p = district_poll(q, y, d, contest)
        est = prior if np.isnan(p) else prior + c["w"] * (p - prior)
        out[contest] = {"state": st, "prior": prior, "poll": None if np.isnan(p) else p, "est": est}
    return out


# ------------------------------------------------------------------------------------------------ D1: the swing model
def jacobson_districts():
    """Gary Jacobson's file (private store): district presidential two-party margin by election on the lines in force,
    the redistricting flag, at-large seats marked. 2024 refused."""
    import backtest_asof as BA
    j = BA.jacobson_raw()
    j = j[j.year <= 2020].copy()
    assert j.year.max() <= 2020
    j["state"] = (j.stcd // 100).map(lambda k: BA.JACOBSON_STATES[int(k) - 1])
    j["cd"] = (j.stcd % 100).astype(int)
    j["at_large"] = j.groupby(["year", "state"]).cd.transform("size") == 1
    j["margin"] = 2 * j.dpres - 100
    return j


def downballot_check(J, tol=2.0):
    """Jacobson's district presidential margins against The Downballot's district sheets where the lines match: 2020
    on the 117th Congress's sheet; 2016 on the 116th's, for states not redrawn in 2018 (Jacobson's redist flag in the
    2018 row). Rows more than `tol` points apart are dropped from D1's fit and listed. 2008 has no sheet."""
    import glob
    f = sorted(glob.glob(str(ROOT / "data/linked/downballot/*/education_income_cd.xlsx")))
    if not f:
        return J, {"available": False}
    x = pd.ExcelFile(f[-1])
    dropped, compared = [], {}
    for sheet, year, dcol, rcol in (("2018 - 116th House", 2016, "Clinton", "Trump"), ("2019 - 117th House", 2020, "Biden", "Trump")):
        d = x.parse(sheet)
        d = d[d.District.astype(str).str.match(r"^[A-Z]{2}-(\d\d|AL)$")]
        d = d.assign(state=d.District.str[:2], cd=d.District.str[3:].replace("AL", "1").astype(int),
                     m=100 * (d[dcol] - d[rcol]) / (d[dcol] + d[rcol]))
        redrawn_after = set(J[(J.year == year + 2) & (J.redist == 1)].state) if year == 2016 else set()
        jj = J[(J.year == year) & ~J.state.isin(redrawn_after)][["state", "cd", "margin"]]
        mg = d.merge(jj, on=["state", "cd"], how="inner")
        bad = mg[(mg.m - mg.margin).abs() > tol]
        compared[int(year)] = {"compared": int(len(mg)), "dropped": int(len(bad)), "not_comparable_states": sorted(redrawn_after),
                               "median_abs_gap": float((mg.m - mg.margin).abs().median())}
        for _, r in bad.iterrows():
            dropped.append((int(year), f"{r.state}-{int(r.cd)}"))              # no value from the private file is written
            J = J[~((J.year == year) & (J.state == r.state) & (J.cd == int(r.cd)))]
    return J, {"available": True, "by_year": compared, "dropped": dropped}


def swing_frame(J, S_marg, X, years):
    """Usable district-elections: lines unchanged at the election and the midterm before, both presidential votes
    present, not at-large, with the district's standardized feature in the year the election uses."""
    rows = []
    for y in years:
        a = J[J.year == y].set_index("stcd"); m = J[J.year == y - 2].set_index("stcd"); p = J[J.year == y - 4].set_index("stcd")
        ok = (a.redist == 0) & (m.reindex(a.index).redist == 0) & p.reindex(a.index).margin.notna() & a.margin.notna() & ~a.at_large
        a = a[ok]
        lean1 = a.margin - a.state.map(S_marg[y])
        lean0 = p.reindex(a.index).margin - a.state.map(S_marg[y - 4])
        x = X.get(y)
        if x is None:
            continue
        xd = pd.Series([x.get((s, int(cd)), np.nan) for s, cd in zip(a.state, a.cd)], index=a.index)
        f = pd.DataFrame({"year": y, "state": a.state, "cd": a.cd, "swing": (lean1 - lean0).values, "x": xd.values}).dropna()
        rows.append(f)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["year", "state", "cd", "swing", "x"])


def district_features(years_used):
    """(state, cd) -> standardized white share without a degree, by election, from district_demographics.csv."""
    f = INTERIM / "district_demographics.csv"
    if not f.exists():
        return {}
    X = pd.read_csv(f, dtype={"cd": str})
    assert X.year.max() <= 2019
    out = {}
    for y, yr in years_used.items():
        d = X[(X.year == yr) & (X.cd != "00")]
        if not len(d):
            continue
        z = (d.white_no_degree_share - d.white_no_degree_share.mean()) / d.white_no_degree_share.std(ddof=1)
        out[y] = {(s, int(cd)): float(v) for s, cd, v in zip(d.state, d.cd, z)}
    return out


def fit_beta(F, years):
    """Least squares of swing on x with one constant per election."""
    g = F[F.year.isin(years)]
    if not len(g):
        return 0.0
    xc = g.x - g.groupby("year").x.transform("mean"); yc = g.swing - g.groupby("year").swing.transform("mean")
    return float((xc * yc).sum() / (xc * xc).sum()) if (xc * xc).sum() > 0 else 0.0


def run_swing(F, scored, fit_only, perm_seed=None):
    """Fit beta on the usable elections before each scored one; score the mean squared error of the predicted lean
    against the realized one over all usable districts (D0: the previous lean, i.e. a predicted swing of zero)."""
    F = F.copy()
    if perm_seed is not None:
        rng = np.random.default_rng(perm_seed)
        for y, g in F.groupby("year"):
            F.loc[g.index, "x"] = g.x.values[rng.permutation(len(g))]
    years = sorted(set(F.year))
    out = {}
    for y in scored:
        if y not in years:
            continue
        train = [e for e in years if e < y]
        beta = fit_beta(F, train)
        g = F[F.year == y]
        out[y] = {"beta": beta, "mse_d1": float(np.mean((g.swing - beta * g.x) ** 2)), "mse_d0": float(np.mean(g.swing ** 2)),
                  "n": int(len(g)), "train": train}
    return out


def swing_verdict(res, shuffled, need):
    ys = sorted(res)
    gain = float(np.mean([res[y]["mse_d0"] - res[y]["mse_d1"] for y in ys]))
    by = {int(y): res[y]["mse_d0"] - res[y]["mse_d1"] for y in ys}
    better = int(sum(v > 1e-12 for v in by.values()))
    p95 = float(np.percentile(shuffled, 95)) if len(shuffled) else None
    out = {"gain_mse": gain, "by_election": by, "better": better, "need": need, "years": ys,
           "beta_by_election": {int(y): res[y]["beta"] for y in ys}, "n_by_election": {int(y): res[y]["n"] for y in ys},
           "shuffle_p95": p95, "shuffled_gains": [round(float(g), 6) for g in shuffled],
           "clause_positive": gain > 1e-12, "clause_elections": better >= need, "clause_shuffle": p95 is not None and gain > p95 + 1e-12}
    out["passes"] = bool(out["clause_positive"] and out["clause_elections"] and out["clause_shuffle"])
    return out


# ------------------------------------------------------------------------------------------------ the simulation
def sized_structure(C_sh, c_own, s, v):
    """D, P_v and the covariance of eps = D (h_c + e sqrt(c_own)), h_c ~ N(0, P_v C_sh P_v'): the shared part is centred
    on the turnout shares before it is sized, so the level all states share is removed from it and the state's size
    does not change its loading on that level. D_s is set so that each state's lean error (eps_s - v' eps) has the range
    model's spread s_s: a closed form, then a short fixed-point polish for the small v' eps term."""
    n = len(s)
    Pv = np.eye(n) - np.outer(np.ones(n), v)
    C_c = Pv @ C_sh @ Pv.T

    def cov_of(D):
        return D[:, None] * C_c * D[None, :] + np.diag(D ** 2 * c_own)

    D = s / np.sqrt(np.diag(C_c) + c_own)
    for _ in range(500):
        var = np.diag(Pv @ cov_of(D) @ Pv.T)
        D_new = D * s / np.sqrt(var)
        if np.abs(D_new - D).max() < 1e-13:
            D = D_new
            break
        D = D_new
    cov = cov_of(D)
    assert np.abs(np.sqrt(np.diag(Pv @ cov @ Pv.T)) - s).max() < 1e-8, float(np.abs(np.sqrt(np.diag(Pv @ cov @ Pv.T)) - s).max())
    return D, Pv, C_c, cov


def shared_root(C_sh):
    w, V = np.linalg.eigh((C_sh + C_sh.T) / 2)
    keep = w > 1e-10
    return V[:, keep] * np.sqrt(w[keep])            # n x r, so that L L' = C_sh


def draws(n_states, r, nsim, seed, n_dist=len(DISTRICTS)):
    """The random numbers of one run, shared by every variant: standard normals for the shared part, standard t
    deviates (unit-variance scaled later) for the national draw, the states' own errors and the districts'."""
    rng = np.random.default_rng(seed)
    return {"g": rng.standard_normal((nsim, r)), "eta": rng.standard_normal(nsim), "e": rng.standard_normal((nsim, n_states)),
            "ed": rng.standard_normal((nsim, n_dist)), "chi_eta": rng.chisquare, "rng": rng}


def t_from_normal(z, nu, rng, size):
    """A unit-variance Student-t deviate from a standard normal and a chi-square draw."""
    if nu is None or nu > 1e5:
        return z
    w = rng.chisquare(nu, size=size)
    return z / np.sqrt(w / nu) * np.sqrt((nu - 2) / nu)


class Model:
    """Everything one simulation needs, for one election and date."""

    def __init__(self, mu, s, C_sh, c_own, v, sigma_N, nu, ev, districts, natF, states):
        self.mu, self.s, self.v, self.nu, self.natF, self.states = np.asarray(mu, float), np.asarray(s, float), np.asarray(v, float), nu, natF, states
        self.D, self.Pv, self.C_c, self.cov = sized_structure(C_sh, c_own, self.s, self.v)
        self.c_own = np.asarray(c_own, float)
        self.C_sh = C_sh
        self.own_sd = self.D * np.sqrt(self.c_own)                       # each state's own error's spread
        self.L = shared_root(self.C_c)                                   # root of the centred shared covariance
        self.pv_var_from_states = float(self.v @ self.cov @ self.v)       # v' Cov(eps) v: own errors, and a little shared
        self.pv_var_shared = float(self.v @ (self.D[:, None] * self.C_c * self.D[None, :]) @ self.v)
        self.var_eta = sigma_N ** 2 - self.pv_var_from_states
        self.eta_flag = self.var_eta < 0
        self.sigma_eta = float(np.sqrt(max(self.var_eta, 0.0)))
        self.ev = ev                                                     # dict contest -> electoral votes (56)
        self.districts = districts                                       # contest -> {state, est, sigma}
        self.total_sd = np.sqrt(self.sigma_eta ** 2 + self.s ** 2)

    def shared(self, dr):
        """Per draw: the shared part of eps (n), eta, and the Student-t own deviates."""
        nu, rng = self.nu, dr["rng"]
        h = dr["g"] @ self.L.T                                            # N x n, Cov P_v C_sh P_v' (no level)
        sh = h * self.D[None, :]                                          # D h_c
        eta = t_from_normal(dr["eta"], nu, rng, len(dr["eta"])) * self.sigma_eta
        return sh, eta

    def simulate(self, dr):
        nu, rng = self.nu, dr["rng"]
        sh, eta = self.shared(dr)
        e = t_from_normal(dr["e"], nu, rng, dr["e"].shape) * self.own_sd[None, :]
        margins = self.mu[None, :] + eta[:, None] + sh + e
        pv = self.natF + eta + ((sh + e) @ self.v)
        dm = {}
        for k, (contest, spec) in enumerate(self.districts.items()):
            si = self.states.index(spec["state"])
            ed = t_from_normal(dr["ed"][:, k], nu, rng, len(eta)) * spec["sigma"]
            dm[contest] = margins[:, si] + (spec["est"] - self.mu[si]) + ed
        return margins, pv, dm, sh, eta

    def exact_count(self, sh, eta):
        """The distribution of the Democratic count given the shared draws, averaged over them. Returns the mean pmf
        over 0 to 538 and the per-draw P(D >= 270) and P(tie) (for the Monte Carlo error)."""
        N = len(eta)
        base = self.mu[None, :] + eta[:, None] + sh                        # N x n: margins before own errors
        nu = self.nu
        cdf = (lambda x: student_t.cdf(x, nu)) if nu and nu < 1e5 else norm.cdf
        tscale = np.sqrt((nu - 2) / nu) if nu and nu < 1e5 else 1.0        # own_sd is unit-variance scaled
        block_states = sorted({spec["state"] for spec in self.districts.values()})
        pmf = np.zeros((N, 539)); pmf[:, 0] = 1.0
        for i, st in enumerate(self.states):
            if st in block_states:
                continue
            p = cdf(base[:, i] / (self.own_sd[i] * tscale))
            evs = self.ev[st]
            new = pmf * (1 - p)[:, None]
            new[:, evs:] += pmf[:, :539 - evs] * p[:, None]
            pmf = new
        # Maine and Nebraska: integrate the state's own error on equal-probability nodes
        nodes = (student_t.ppf((np.arange(NODES) + 0.5) / NODES, nu) * tscale) if nu and nu < 1e5 else norm.ppf((np.arange(NODES) + 0.5) / NODES)
        for st in block_states:
            si = self.states.index(st)
            dists = [(c, spec) for c, spec in self.districts.items() if spec["state"] == st]
            evs_state = self.ev[st]
            block_ev = evs_state + sum(self.ev[c] for c, _ in dists)
            bp = np.zeros((N, block_ev + 1))
            for z in nodes:
                m = base[:, si] + self.own_sd[si] * z                        # the state's margin at this node
                part = np.zeros((N, block_ev + 1)); part[:, 0] = 1.0
                win = (m > 0).astype(float)
                new = part * (1 - win)[:, None]; new[:, evs_state:] += part[:, :block_ev + 1 - evs_state] * win[:, None]; part = new
                for c, spec in dists:
                    pd_ = cdf((m + (spec["est"] - self.mu[si])) / (spec["sigma"] * tscale))
                    e1 = self.ev[c]
                    new = part * (1 - pd_)[:, None]; new[:, e1:] += part[:, :block_ev + 1 - e1] * pd_[:, None]; part = new
                bp += part / NODES
            new = np.zeros_like(pmf)
            for k in range(block_ev + 1):
                new[:, k:] += pmf[:, :539 - k] * bp[:, k][:, None]
            pmf = new
        assert np.allclose(pmf.sum(1), 1.0, atol=1e-6)
        p_dem = pmf[:, 270:].sum(1); p_tie = pmf[:, 269]
        self.p_state_exact = {st: float(cdf(base[:, i] / (self.own_sd[i] * tscale)).mean()) for i, st in enumerate(self.states)}
        return pmf.mean(0), p_dem, p_tie

    def outputs(self, dr):
        margins, pv, dm, sh, eta = self.simulate(dr)
        pmf, p_dem, p_tie = self.exact_count(sh, eta)
        contests = list(self.states) + list(self.districts)
        allm = np.column_stack([margins] + [dm[c] for c in self.districts])
        evs = np.array([self.ev[c] for c in contests])
        dwin = allm > 0
        count = (dwin * evs[None, :]).sum(1)
        # the tipping point: order the contests by margin, the one whose votes take the winner past 269
        order_d = np.argsort(-allm, axis=1)
        cum = np.cumsum(evs[order_d], axis=1)
        tp_idx = np.full(len(count), -1)
        dem = count >= 270; rep = count <= 268
        pos = np.argmax(cum >= 270, axis=1)
        tp_idx[dem] = order_d[dem, pos[dem]]
        order_r = np.argsort(allm, axis=1); cum_r = np.cumsum(evs[order_r], axis=1); pos_r = np.argmax(cum_r >= 270, axis=1)
        tp_idx[rep] = order_r[rep, pos_r[rep]]
        has_tp = tp_idx >= 0
        tp_margin = np.where(has_tp, allm[np.arange(len(count)), np.maximum(tp_idx, 0)], np.nan)
        gap = tp_margin - pv
        tp_counts = pd.Series([contests[i] for i in tp_idx[has_tp]]).value_counts(normalize=True)
        q = np.percentile(allm, [10, 25, 75, 90], axis=0)
        out = {
            "p_dem_270_exact": float(p_dem.mean()), "p_rep_270_exact": float(1 - p_dem.mean() - p_tie.mean()), "p_tie_exact": float(p_tie.mean()),
            "count_pmf": [float(x) for x in pmf], "count_mean_exact": float(np.sum(np.arange(539) * pmf)),
            "count_median_exact": int(np.searchsorted(np.cumsum(pmf), 0.5)),
            "count_p10_exact": int(np.searchsorted(np.cumsum(pmf), 0.10)), "count_p90_exact": int(np.searchsorted(np.cumsum(pmf), 0.90)),
            "p_dem_270_sim": float(dem.mean()), "p_tie_sim": float((count == 269).mean()), "count_median_sim": float(np.median(count)),
            "popular_vote": {"median": float(np.median(pv)), "p10": float(np.percentile(pv, 10)), "p90": float(np.percentile(pv, 90)), "sd": float(pv.std())},
            "p_split_dem_pv_rep_ec": float(((pv > 0) & rep).mean()), "p_split_rep_pv_dem_ec": float(((pv < 0) & dem).mean()),
            "tipping_point": {"mode": tp_counts.index[0] if len(tp_counts) else None, "shares": {k: float(v) for k, v in tp_counts.head(12).items()}},
            "gap": ({"median": float(np.nanmedian(gap)), "p10": float(np.nanpercentile(gap, 10)), "p90": float(np.nanpercentile(gap, 90))}
                    if has_tp.any() else {"median": None, "p10": None, "p90": None}),
            "contests": {c: {"p_dem": float(dwin[:, i].mean()), "q10": float(q[0, i]), "q25": float(q[1, i]), "q75": float(q[2, i]), "q90": float(q[3, i])}
                         for i, c in enumerate(contests)},
            "identities": {"pv_sd": float(pv.std()), "sigma_eta": self.sigma_eta, "eta_flag": bool(self.eta_flag),
                           "pv_sd_from_shared": float(np.sqrt(self.pv_var_shared)), "pv_sd_from_own": float(np.sqrt(self.pv_var_from_states - self.pv_var_shared)),
                           "centred_sd_sim": [float(x) for x in (margins - margins @ self.v[:, None] * 0 - (margins @ self.v)[:, None]).std(0)],
                           "state_total_sd_sim": [float(x) for x in margins.std(0)]},
        }
        return out, allm, pv


# ------------------------------------------------------------------------------------------------ electoral votes
def electoral_votes(y):
    E = pd.read_csv(INTERIM / "electoral_votes.csv")
    e = E[E.election == y]
    assert len(e) == 56 and e.ev.sum() == 538
    return dict(zip(e.contest, e.ev.astype(int)))


# ------------------------------------------------------------------------------------------------ the as-of assembly
def assemble(cells, q, D, ecells, Q, states, nat_err, y, d, range_kind="R0", u=None, nu_fixed=None, beta_x=None, theta=None, v_override=None):
    c = cells[(y, d)]
    if v_override is not None:
        v1 = np.asarray(v_override, float)
        c = dict(c, v=v1, mu=c["mu0"] + (c["natF"] - float(v1 @ c["mu0"])))
        cells = dict(cells); cells[(y, d)] = c
    rho = fit_structure(ecells, Q, y)
    C, C_sh, c_own = correlation_parts(ecells[y], rho)
    if theta is None:
        theta = fit_range(range_rows(cells, y), range_kind, u)
    cc = cell_with(cells, y, d)
    _, s, _ = range_score(theta, cc, range_kind, u)
    ab = national_range(nat_err, y)
    sigma_N = sigma_nat(ab, d)
    nu = nu_fixed if nu_fixed is not None else fit_nu(cells, theta, range_kind, u, y)[0]
    sigD, nch, _ = district_sigma(D, y)
    dc = district_centres(cells, q, D, y, d, states, beta_x)
    districts = {k: {"state": v["state"], "est": v["est"], "sigma": sigD} for k, v in dc.items()}
    m = Model(c["mu"], s, C_sh, c_own, c["v"], sigma_N, nu, electoral_votes(y), districts, c["natF"], states)
    meta = {"rho": rho, "theta": [float(x) for x in theta], "national_range": [float(ab[0]), float(ab[1])], "sigma_N": sigma_N,
            "nu": nu, "sigma_D": sigD, "district_changes": nch, "C": C, "C_sh": C_sh, "c_own": c_own}
    return m, meta


def mc_error(m, nsim=NSIM, seeds=MC_SEEDS):
    vals = []
    for sd in seeds:
        dr = draws(len(m.states), m.L.shape[1], nsim, sd)
        o, _, _ = m.outputs(dr)
        vals.append({"p_dem_exact": o["p_dem_270_exact"], "median_exact": o["count_median_exact"], "p_tie_exact": o["p_tie_exact"],
                     "p_dem_sim": o["p_dem_270_sim"], "p_tie_sim": o["p_tie_sim"], "gap_median": o["gap"]["median"] or 0.0,
                     "tp_mode_share": max(o["tipping_point"]["shares"].values()) if o["tipping_point"]["shares"] else 0.0,
                     "p_split": o["p_split_dem_pv_rep_ec"] + o["p_split_rep_pv_dem_ec"]})
    return {k: float(max(v[k] for v in vals) - min(v[k] for v in vals)) for k in vals[0]}


# ------------------------------------------------------------------------------------------------ checks
def _planted_cells(rng, theta, kind, u, cells):
    """Cells with misses drawn from a known range model (independent, Gaussian), keeping everything else."""
    out = {}
    for (y, d), c in cells.items():
        row = dict(r=None, n=c["n"], days=float(d), lop=np.abs(c["prior0"]) / 10.0, y=y)
        s = np.sqrt(spread2(theta, row, kind, u))
        miss = rng.standard_normal(len(s)) * s
        miss = miss - float(c["v"] @ miss)
        out[(y, d)] = dict(c, miss=miss)
    return out


def checks():
    ok = True

    def report(name, passed):
        nonlocal ok
        ok &= bool(passed)
        print(f"  {'pass' if passed else 'FAIL'}  {name}")

    print("loading (polls, results, national series, demographics)")
    cells, E, q = load()
    demo = PE.Demo()
    ecells, Q, states = structure_cells(cells, demo)
    D = district_table()
    nat_err = national_errors(E)
    n = len(states)
    # 1. holdout
    report("2024 is absent from the polls, the results, the district results, the electoral votes' pages and the national series",
           2024 not in set(q.cycle) and max(y for y, _ in cells) <= 2020 and D.year.max() <= 2020 and max(y for y, _ in nat_err) <= 2020
           and pd.read_csv(INTERIM / "electoral_votes.csv").query("election <= 2020").pipe(lambda e: e.source.str.contains("page").all()))
    # 2. the rebuilt centre equals the saved frame's C column
    F = pd.read_csv(OUT / "pres_addup_rerun_frame.csv")
    diffs = []
    for (y, d), g in F.groupby(["cycle", "d"]):
        if (y, d) in cells:
            g = g.set_index("state").loc[states]
            diffs.append(np.abs(g.C.values - cells[(y, d)]["mu"]).max())
    report("the rebuilt centre equals pres_addup_rerun_frame.csv's C column (2004 to 2020, 22 cells)", len(diffs) == 22 and max(diffs) < 1e-9)
    # 3. electoral votes
    ev = {y: electoral_votes(y) for y in SCORED}
    report("electoral votes: 56 contests summing to 538 in every scored election", all(sum(v.values()) == 538 and len(v) == 56 for v in ev.values()))
    # 4. a planted model, for the identities and the counting
    rho = fit_structure(ecells, Q, 2020)
    C, C_sh, c_own = correlation_parts(ecells[2020], rho)
    v = cells[(2020, 7)]["v"]
    rng = np.random.default_rng(0)
    mu = rng.standard_normal(n) * 15
    s = 3.0 + rng.random(n) * 2
    sigma_N = 3.0
    districts = {c_: {"state": c_[:2], "est": mu[states.index(c_[:2])] + (5.0 if c_.endswith("1") else -5.0), "sigma": 4.0} for c_ in DISTRICTS}
    m = Model(mu, s, C_sh, c_own, v, sigma_N, 1e9, ev[2020], districts, 1.0, states)
    hc = rng.standard_normal((2000, m.L.shape[1])) @ m.L.T
    report("the centred shared draws carry no level: v' h_c = 0 for every draw, and v' D h_c is small (reported)",
           np.abs(hc @ v).max() < 1e-9 and m.pv_var_shared < 0.25 * sigma_N ** 2)
    print(f"        popular-vote sd from the sized shared part {np.sqrt(m.pv_var_shared):.3f}, from own errors {np.sqrt(m.pv_var_from_states - m.pv_var_shared):.3f}, sigma_eta {m.sigma_eta:.3f} of sigma_N {sigma_N}")
    dr = draws(n, m.L.shape[1], NSIM, 11)
    margins, pv, dm, sh, eta = m.simulate(dr)
    cen = margins - (margins @ v)[:, None]
    report("each state's centred spread equals s_s and the popular vote's spread equals sigma_N, to Monte Carlo error",
           np.abs(cen.std(0) - s).max() < 0.12 and abs(pv.std() - sigma_N) < 0.05)
    report("a state's total spread is sqrt(var eta + s_s^2 + own term), to Monte Carlo error",
           np.abs(margins.std(0) - np.sqrt(m.sigma_eta ** 2 + s ** 2 + 2 * 0)).max() < 0.25)
    # 5. the contrast covariance with one spread reproduces EC-5's Q C Q' up to scale
    Pv = np.eye(n) - np.outer(np.ones(n), v)
    Cov = 16.0 * (Pv @ C_sh @ Pv.T + np.diag(c_own))                    # D set to one constant: D (C_c + C_own) D
    QC = Q @ Cov @ Q.T; QE = Q @ C @ Q.T
    scale = np.trace(QC) / np.trace(QE)
    report("with D one constant, Q Cov(eps) Q' equals EC-5's Q C Q' up to one scale (1e-9)", np.abs(QC - scale * QE).max() < 1e-9)
    report("the sizing reproduces every state's lean-error spread (1e-8)", np.abs(np.sqrt(np.diag(m.Pv @ m.cov @ m.Pv.T)) - s).max() < 1e-8)
    # 6. exact count against plain simulation (Gaussian), including the Maine and Nebraska blocks
    o, allm, pv2 = m.outputs(dr)
    report("exact count and plain simulation agree on P(D >= 270), the median count and P(tie) within Monte Carlo error",
           abs(o["p_dem_270_exact"] - o["p_dem_270_sim"]) < 0.01 and abs(o["count_median_exact"] - o["count_median_sim"]) <= 3
           and abs(o["p_tie_exact"] - o["p_tie_sim"]) < 0.003)
    mt = Model(mu, s, C_sh, c_own, v, sigma_N, 4.0, ev[2020], districts, 1.0, states)
    ot, _, _ = mt.outputs(draws(n, mt.L.shape[1], NSIM, 12))
    report("the same with Student-t errors (nu 4)", abs(ot["p_dem_270_exact"] - ot["p_dem_270_sim"]) < 0.012
           and abs(ot["count_median_exact"] - ot["count_median_sim"]) <= 3 and abs(ot["p_tie_exact"] - ot["p_tie_sim"]) < 0.003)
    # per contest, nu 4: the exact probability against the simulated frequency, on the 15 closest states
    drt = draws(n, mt.L.shape[1], NSIM, 12)
    mg_t, _, _, sh_t, eta_t = mt.simulate(drt)
    mt.exact_count(sh_t, eta_t)
    close = np.argsort(np.abs(mu))[:15]
    gaps = [abs(mt.p_state_exact[states[i]] - float((mg_t[:, i] > 0).mean())) for i in close]
    print(f"        per-contest exact against simulated, nu 4, 15 closest states: largest gap {max(gaps):.4f}")
    report("per contest, the exact win probability equals the simulated frequency within Monte Carlo error (nu 4)", max(gaps) < 0.01)
    # one contest at nu 4: the exact probability is the Student-t at margin / (own spread x sqrt((nu - 2) / nu)), and the
    # simulated frequency agrees (the own spread here is the sizing's, a little above 1 because the lean error is centred)
    one = Model(np.array([1.0] + [-30.0] * (n - 1)), np.full(n, 1.0), C_sh * 0, c_own * 0 + 1.0, v, 1e-6, 4.0, ev[2020], {}, 0.0, states)
    one.exact_count(np.zeros((10, n)), np.zeros(10))
    expect = float(student_t.cdf(1.0 / (one.own_sd[0] * np.sqrt(0.5)), 4))
    mg1, _, _, _, _ = one.simulate(draws(n, one.L.shape[1], NSIM, 13))          # a shared root with no columns
    report("one contest at nu 4: the exact probability is the t at margin / (own spread x sqrt(1/2)) and matches simulation",
           abs(one.p_state_exact[states[0]] - expect) < 1e-9 and abs(float((mg1[:, 0] > 0).mean()) - expect) < 0.006 and 0.85 < expect < 0.9)
    report("a nu of 1e9 reproduces Gaussian draws", np.allclose(t_from_normal(dr["e"][:5], 1e9, dr["rng"], (5, n)), dr["e"][:5]))
    # 7. districts
    me = dm["ME-1"] - margins[:, states.index("ME")]
    report("a district's margin less its state's has the district's lean and spread sigma_D over draws",
           abs(me.mean() - 5.0) < 0.1 and abs(me.std() - 4.0) < 0.1)
    # 8. tipping point and tie on made-up margins
    mu2 = np.full(n, -20.0); mu2[states.index("PA")] = 0.3; mu2[states.index("CA")] = 30; mu2[states.index("NY")] = 30
    big = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "MI", "NC", "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MD", "MO", "WI", "CO", "MN", "SC", "AL"]
    for st in big:
        mu2[states.index(st)] = 25.0
    mu2[states.index("PA")] = 0.3
    md = Model(mu2, np.full(n, 1e-6), C_sh, c_own, v, 1e-6, 1e9, ev[2020], {c_: {"state": c_[:2], "est": -20.0, "sigma": 1e-6} for c_ in DISTRICTS}, 0.0, states)
    o2, allm2, _ = md.outputs(draws(n, md.L.shape[1], 2000, 5))
    dem_ev = sum(ev[2020][st] for st in big)
    report(f"tipping point on fixed margins is the closest state the winner needs (Democratic votes {dem_ev})",
           (o2["tipping_point"]["mode"] == "PA") == (dem_ev >= 270 and dem_ev - ev[2020]["PA"] < 270))
    # a 269 tie: Democrats take exactly 269 by construction
    mu3 = np.full(n, -20.0)
    tie_set, tot = [], 0
    for st in sorted(states, key=lambda s_: -ev[2020][s_]):
        if st in ("ME", "NE"):
            continue
        if tot + ev[2020][st] <= 269:
            tie_set.append(st); tot += ev[2020][st]
    for st in tie_set:
        mu3[states.index(st)] = 25.0
    assert tot == 269, tot
    m3 = Model(mu3, np.full(n, 1e-6), C_sh, c_own, v, 1e-6, 1e9, ev[2020], {c_: {"state": c_[:2], "est": -20.0, "sigma": 1e-6} for c_ in DISTRICTS}, 0.0, states)
    o3, _, _ = m3.outputs(draws(n, m3.L.shape[1], 2000, 6))
    report("a 269 to 269 draw is counted as a tie, with no tipping point, in both methods",
           o3["p_tie_exact"] > 0.999 and o3["p_tie_sim"] > 0.999 and o3["tipping_point"]["mode"] is None)
    # 9. the same seed reproduces the same outputs
    oa, _, _ = m.outputs(draws(n, m.L.shape[1], 5000, 7)); ob, _, _ = m.outputs(draws(n, m.L.shape[1], 5000, 7))
    report("the same seed reproduces the same outputs", oa["p_dem_270_exact"] == ob["p_dem_270_exact"] and oa["gap"]["median"] == ob["gap"]["median"])
    # 10. the range: planted sizes recovered, the decision path on planted misses
    u = {y: unusual(ecells[y]) for y in ELECTIONS}
    prng = np.random.default_rng(21)
    theta_true = np.array([9.0, 12.0, 0.03, 0.4])
    pc = _planted_cells(prng, theta_true, "R1", u, cells)
    th = fit_range(range_rows(pc, 2024), "R1", u)
    print(f"        planted (a, b, c, e) {theta_true.tolist()} fitted {np.round(th, 3).tolist()}")
    report("planted range sizes recovered (R1: a within 2, b within 4, c within 0.015, e within 0.15)",
           abs(th[0] - 9.0) < 2 and abs(th[1] - 12.0) < 4 and abs(th[2] - 0.03) < 0.015 and abs(th[3] - 0.4) < 0.15)
    base = run_range(pc, "R0"); cand = run_range(pc, "R1", u)
    sh_g = shuffled_gains_range(pc, "R1", u, base, 99, 30)
    vr = verdict(base, cand, sh_g)
    report("the decision path: a planted lopsided term passes R1 (30 shuffles)", vr["passes"])
    pc0 = _planted_cells(prng, theta_true[:3], "R0", u, cells)
    base0 = run_range(pc0, "R0"); c1 = run_range(pc0, "R1", u); c2 = run_range(pc0, "R2", u)
    v1 = verdict(base0, c1, shuffled_gains_range(pc0, "R1", u, base0, 98, 30)); v2 = verdict(base0, c2, shuffled_gains_range(pc0, "R2", u, base0, 97, 30))
    report("a flat plant passes nothing", not v1["passes"] and not v2["passes"])
    nu_hat, sc, nz = fit_nu(pc0, base0[2020]["theta"], "R0", u, 2024)
    report("nu fitted on Gaussian plants is large and the scale about 1", nu_hat > 15 and abs(sc - 1) < 0.1)
    # 11. turnout
    sh, marg, nat = shares(); pop, vint = populations()
    t0 = {y: {"sq": pv_error(turnout_weights(y, sh, None, 0), y, marg, nat) ** 2} for y in SCORED}
    report("T0's popular-vote error is 0.1 to 0.2 points in 2008 to 2020 (section 11's figures)", all(0.05 < abs(np.sqrt(t0[y]["sq"])) < 0.25 for y in SCORED))
    g = growth("T1", 2020, sh, pop, vint)
    report("lambda = 0 reproduces T0", np.allclose(turnout_weights(2020, sh, g, 0.0), sh[2016].values))
    r1 = run_turnout("T1", sh, marg, nat, pop, vint); r1s = run_turnout("T1", sh, marg, nat, pop, vint, perm=np.arange(len(sh)))
    report("an identity shuffle reproduces T1 and a real one changes it", all(r1[y]["sq"] == r1s[y]["sq"] for y in SCORED)
           and any(run_turnout("T1", sh, marg, nat, pop, vint, perm=np.random.default_rng(3).permutation(len(sh)))[y]["sq"] != r1[y]["sq"] for y in SCORED))
    # planted growth: results built so that the true shares follow a known lambda
    report("T2's growth factors exist for 2004 to 2020 and not for 2000", growth("T2", 2000, sh, pop, vint) is None and all(growth("T2", y, sh, pop, vint) is not None for y in (2004,) + SCORED))
    # a planted lambda: the national margin made to equal the sum with weights at lambda = 1 exactly
    nat_pl = pd.Series({y: float(turnout_weights(y, sh, growth("T1", y, sh, pop, vint), 1.0) @ marg[y].values) for y in ELECTIONS})
    rpl = run_turnout("T1", sh, marg, nat_pl, pop, vint)
    report("a planted lambda (1.0) is recovered by T1's grid fit in every scored election", all(rpl[y]["lambda"] == 1.0 for y in SCORED))
    # districts: a centre with polls and one without
    dc20 = district_centres(cells, q, D, 2020, 7, states); dc08 = district_centres(cells, q, D, 2008, 7, states)
    c20 = cells[(2020, 7)]
    me2 = dc20["ME-2"]
    manual = me2["prior"] + c20["w"] * (me2["poll"] - me2["prior"]) if me2["poll"] is not None else None
    report("a district with polls is prior + w (poll - prior), and one without is its prior (ME-2 in 2020 and 2008)",
           manual is not None and abs(me2["est"] - manual) < 1e-9 and dc08["ME-2"]["poll"] is None and dc08["ME-2"]["est"] == dc08["ME-2"]["prior"]
           and abs(me2["prior"] - (float(c20["mu"][states.index("ME")]) + district_lean(D, 2020, "ME-2"))) < 1e-9)
    # 12. the swing model on planted data
    Fp = pd.DataFrame({"year": np.repeat([2000, 2008, 2016, 2020], 400), "state": "XX", "cd": np.tile(np.arange(400), 4)})
    Fp["x"] = prng.standard_normal(len(Fp)); Fp["swing"] = 1.5 * Fp.x + prng.standard_normal(len(Fp)) * 3
    rs = run_swing(Fp, (2008, 2016, 2020), (2000,))
    vs = swing_verdict(rs, [swing_verdict(run_swing(Fp, (2008, 2016, 2020), (2000,), perm_seed=k), [], 2)["gain_mse"] for k in range(30)], 2)
    report("the swing model recovers a planted slope and passes; a flat plant fails",
           all(abs(rs[y]["beta"] - 1.5) < 0.3 for y in rs) and vs["passes"]
           and not swing_verdict(run_swing(Fp.assign(swing=prng.standard_normal(len(Fp)) * 3), (2008, 2016, 2020), (2000,)), [0.0] * 30, 2)["passes"])
    # 13. district data and Jacobson's file against the pages
    sigD, nch, byd = district_sigma(D, 2024)
    report("sigma_D is computed from 25 lean changes, 2004 to 2020", nch == 25 and sigD > 0)
    print("all checks pass" if ok else "SOME CHECKS FAIL")
    return ok


# ------------------------------------------------------------------------------------------------ the as-of assembly
def asof_weights(kind, y, sh, pop, vint):
    """The adopted turnout candidate's weights for election y, lambda fitted on the elections before it."""
    sh_, marg, nat_m = shares()
    r = run_turnout(kind, sh_, marg, nat_m, pop, vint, years=(y,))
    lam = r[y]["lambda"]
    return turnout_weights(y, sh_, growth(kind, y, sh_, pop, vint), lam), lam


def asof_assembly(cells, q, D, ecells, Q, states, nat_err, turnout, sh, pop, vint):
    """Part D: every scored election at the simulated dates, everything fitted on the elections before it; the outputs
    are written for EC-7 and only the identities and the Monte Carlo error are read here."""
    print(f"D. the as-of assembly with turnout weights {turnout or 'T0'} (outputs written to pres_sim_asof.json, not printed)")
    asof, ident, mce = {}, {}, {}
    for y in SCORED:
        v_over, lam = (None, None)
        if turnout:
            v_over, lam = asof_weights(turnout, y, sh, pop, vint)
        for d in SIM_DAYS:
            m, meta = assemble(cells, q, D, ecells, Q, states, nat_err, y, d, "R0", v_override=v_over)
            dr = draws(len(states), m.L.shape[1], NSIM, SEED)
            o, _, _ = m.outputs(dr)
            asof[f"{y}/{d}"] = dict(o, meta={k: v for k, v in meta.items() if k not in ("C", "C_sh", "c_own")},
                                    turnout={"weights": turnout or "T0", "lambda": lam}, scored_in_EC7=not (y == 2008 and d in (100, 60)))
            ident[f"{y}/{d}"] = {"pv_sd_sim": o["identities"]["pv_sd"], "sigma_N": meta["sigma_N"], "sigma_eta": m.sigma_eta, "eta_flag": bool(m.eta_flag),
                                 "pv_sd_from_shared": o["identities"]["pv_sd_from_shared"], "pv_sd_from_own": o["identities"]["pv_sd_from_own"],
                                 "max_abs_centred_sd_gap": float(np.max(np.abs(np.array(o["identities"]["centred_sd_sim"]) - m.s))),
                                 # report (e): corr(D M D) = corr(M) for diagonal D, so the sizing changes no pairwise state
                                 # correlation; what changes them against EC-5's C is the centring of the shared part
                                 "max_abs_state_corr_change_from_sizing": float(np.max(np.abs(
                                     (lambda Cv: Cv / np.sqrt(np.outer(np.diag(Cv), np.diag(Cv))))(m.cov)
                                     - (lambda Cv: Cv / np.sqrt(np.outer(np.diag(Cv), np.diag(Cv))))(m.C_c + np.diag(m.c_own)))[~np.eye(len(states), dtype=bool)])),
                                 "state_corr_change_from_centring": {"median": float(np.median(np.abs(
                                     (lambda Cv: Cv / np.sqrt(np.outer(np.diag(Cv), np.diag(Cv))))(m.C_c + np.diag(m.c_own)) - meta["C"])[~np.eye(len(states), dtype=bool)])),
                                     "max": float(np.max(np.abs(
                                     (lambda Cv: Cv / np.sqrt(np.outer(np.diag(Cv), np.diag(Cv))))(m.C_c + np.diag(m.c_own)) - meta["C"])[~np.eye(len(states), dtype=bool)])),
                                     "mean_corr_EC5": float(np.mean(meta["C"][~np.eye(len(states), dtype=bool)])),
                                     "mean_corr_centred": float(np.mean((lambda Cv: Cv / np.sqrt(np.outer(np.diag(Cv), np.diag(Cv))))(m.C_c + np.diag(m.c_own))[~np.eye(len(states), dtype=bool)]))}}
            if d == 7:
                mce[f"{y}/{d}"] = mc_error(m)
            print(f"  {y} at {d} days: assembled; sigma_N {meta['sigma_N']:.2f}, sigma_eta {m.sigma_eta:.2f}, nu {meta['nu']:.1f}, sigma_D {meta['sigma_D']:.2f}")
    return asof, ident, mce


def asof():
    """Part D alone, with the turnout decision read from pres_sim.json (after a run)."""
    out = json.loads((OUT / "pres_sim.json").read_text())
    tt = out["turnout"]
    adopted = tt.get("adopted")
    if adopted is None:
        adopted = "T1" if tt["T1"]["passes"] and not tt["T2"]["passes"] else ("T2" if tt["T2"]["passes"] and not tt["T1"]["passes"] else None)
        out["turnout"]["adopted"] = adopted
    cells, E, q = load()
    demo = PE.Demo()
    ecells, Q, states = structure_cells(cells, demo)
    D = district_table()
    nat_err = national_errors(E)
    sh, _, _ = shares(); pop, vint = populations()
    asof_, ident, mce = asof_assembly(cells, q, D, ecells, Q, states, nat_err, adopted, sh, pop, vint)
    out["identities"] = ident
    out["monte_carlo_error_7d"] = mce
    (OUT / "pres_sim_asof.json").write_text(json.dumps(asof_, indent=0, default=float))
    (OUT / "pres_sim.json").write_text(json.dumps(out, indent=1, default=float))
    print("identities:", json.dumps(ident, indent=1, default=float))
    print("Monte Carlo error at 7 days:", json.dumps(mce, indent=1, default=float))
    print("written: pres_sim.json, pres_sim_asof.json")


# ------------------------------------------------------------------------------------------------ the one round
def run():
    print("loading")
    cells, E, q = load()
    demo = PE.Demo()
    ecells, Q, states = structure_cells(cells, demo)
    D = district_table()
    nat_err = national_errors(E)
    u = {y: unusual(ecells[y]) for y in ELECTIONS}
    M7 = {(y, 7): {"states": cells[(y, 7)]["states"], "miss": cells[(y, 7)]["miss"], "lean": cells[(y, 7)]["lean"]} for y in ELECTIONS}
    ecells50, _, _ = PE.build_cells(M7, demo, d=7, states=[s_ for s_ in states if s_ != "DC"])
    out = {"scored": SCORED, "fit_only": FIT_ONLY, "structure": STRUCTURE, "nsim": NSIM, "shuffles": SHUFFLES}

    # ---- B. the range
    print("B. the range")
    base = run_range(cells, "R0")
    res = {"R0": base}
    tests = {}
    for kind in ("R1", "R2"):
        cand = run_range(cells, kind, u)
        res[kind] = cand
        sh_g = shuffled_gains_range(cells, kind, u, base, SEEDS[kind], SHUFFLES)
        tests[kind] = verdict(base, cand, sh_g)
        d30 = run_range(cells, kind, u, day=30); b30 = run_range(cells, "R0", day=30)
        tests[kind]["gain_30"] = pooled(d30) - pooled(b30)
        no_dc = np.array([s != "DC" for s in states])
        cells50 = subset_cells(cells, no_dc)
        u50 = {y: unusual(ecells50[y]) for y in ELECTIONS} if kind == "R2" else None
        bnd = run_range(cells50, "R0"); cnd = run_range(cells50, kind, u50)
        sh50 = shuffled_gains_range(cells50, kind, u50, bnd, SEEDS[kind] + 100, SHUFFLES)
        tests[kind]["without_dc"] = verdict(bnd, cnd, sh50)
        tests[kind]["without_dc"].pop("shuffled_gains")
        tests[kind]["flags"] = {"suggested_by_earlier_results": True, "worse_at_30_days": tests[kind]["gain_30"] < -TOL}
        tests[kind]["standing"] = ("passes; flagged (suggested by earlier results" + ("; worse at 30 days" if tests[kind]["gain_30"] < -TOL else "") + "): to the user") if tests[kind]["passes"] else "fails"
    res["R12"] = run_range(cells, "R12", u)
    tests["R12_reported"] = {"gain": pooled(res["R12"]) - pooled(base), "by_election": {int(y): res["R12"][y]["ld"] - base[y]["ld"] for y in SCORED}}
    out["range"] = {"tests": tests, "fits": {k: {int(y): {"ld": v[y]["ld"], "theta": v[y]["theta"]} for y in SCORED} for k, v in res.items()}}
    # report (a): implied spreads
    rep_a = {}
    for y in SCORED:
        th = base[y]["theta"]
        rep_a[int(y)] = {f"{d}d_{nn}polls": float(np.sqrt(th[0] + th[1] / (1 + nn) + th[2] * d)) for d in (7, 100) for nn in (0, 3, 10)}
    out["range"]["report_a_typical_spread_R0"] = rep_a
    # nu and the national range
    nus = {}
    for y in SCORED:
        nu, sc, nz = fit_nu(cells, base[y]["theta"], "R0", u, y)
        raw_df = float(student_t.fit(np.concatenate([row["r"] / np.sqrt(spread2(base[y]["theta"], row, "R0", None)) for row in range_rows(cells, y)]), floc=0)[0])
        nus[int(y)] = {"nu": nu, "nu_unfloored": raw_df, "scale": sc, "implied_sd": sc * float(np.sqrt(nu / (nu - 2))) if nu < 1e5 else sc, "n": nz}
    out["nu"] = nus
    nat = {}
    for y in SCORED:
        ab = national_range(nat_err, y)
        nat[int(y)] = {"a": ab[0], "b": ab[1], "sigma_by_day": {d: sigma_nat(ab, d) for d in ALL_DAYS}}
    ab_all = national_range(nat_err, 2024)
    nat["all_to_2020"] = {"a": ab_all[0], "b": ab_all[1], "sigma_by_day": {d: sigma_nat(ab_all, d) for d in ALL_DAYS}}
    zn = [nat_err[(y, 7)] for y in range(1952, 2021, 4) if (y, 7) in nat_err]
    dfn, _, scn = student_t.fit(np.array(zn) / np.std(zn), floc=0)
    nat["national_nu_own_fit_7d"] = {"nu": float(dfn), "n": len(zn)}
    # national coverage, as of each election from 1980
    cov_n = {"p50": [], "p80": []}
    for y in range(1980, 2021, 4):
        ab = national_range(nat_err, y)
        for d in SIM_DAYS:
            if (y, d) in nat_err:
                e = abs(nat_err[(y, d)]); sN = sigma_nat(ab, d)
                cov_n["p50"].append(e <= norm.ppf(0.75) * sN); cov_n["p80"].append(e <= norm.ppf(0.90) * sN)
    nat["coverage_1980_2020_asof"] = {k: float(np.mean(v)) for k, v in cov_n.items()}
    out["national_range"] = nat
    # report (b): coverage by date under R0 and the candidates (fitted as of each election, scored at each date)
    cov = {}
    for kind in ("R0", "R1", "R2"):
        cov[kind] = {}
        for d in SIM_DAYS:
            rr = run_range(cells, kind, u if kind != "R0" else None, day=d)
            cov[kind][d] = coverage(rr, nu={y: nus[int(y)]["nu"] for y in SCORED})
    out["range"]["report_b_coverage"] = cov
    # report (c): gains by group
    def by_group(kind, groups):
        g = {}
        for lab, mask_fn in groups.items():
            tot_b = tot_c = 0.0
            for y in SCORED:
                c = cell_with(cells, y, 7); mk = mask_fn(c, y)
                b = norm.logpdf(base[y]["r"], 0, base[y]["sd"]); cc = norm.logpdf(res[kind][y]["r"], 0, res[kind][y]["sd"])
                tot_b += float(b[mk].sum()); tot_c += float(cc[mk].sum())
            g[lab] = (tot_c - tot_b) / len(SCORED)
        return g
    out["range"]["report_c"] = {
        "R1_by_prior": by_group("R1", {"under 10": lambda c, y: np.abs(c["prior0"]) < 10, "10 to 20": lambda c, y: (np.abs(c["prior0"]) >= 10) & (np.abs(c["prior0"]) < 20), "over 20": lambda c, y: np.abs(c["prior0"]) >= 20}),
        "R2_by_u_third": by_group("R2", {"near": lambda c, y: u[y] <= np.percentile(u[y], 33.3), "middle": lambda c, y: (u[y] > np.percentile(u[y], 33.3)) & (u[y] <= np.percentile(u[y], 66.7)), "far": lambda c, y: u[y] > np.percentile(u[y], 66.7)})}
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "shuffled_gains"} for k, v in tests.items() if k != "R12_reported"}, indent=1, default=float))

    # ---- C. turnout
    print("C. turnout")
    sh, marg, nat_m = shares(); pop, vint = populations()
    t0 = {y: {"sq": pv_error(turnout_weights(y, sh, None, 0), y, marg, nat_m) ** 2, "err": pv_error(turnout_weights(y, sh, None, 0), y, marg, nat_m)} for y in SCORED}
    tt = {"T0": {int(y): t0[y] for y in SCORED}}
    for kind in ("T1", "T2"):
        r = run_turnout(kind, sh, marg, nat_m, pop, vint)
        sg = shuffled_gains_turnout(kind, sh, marg, nat_m, pop, vint, t0, SEEDS[kind], SHUFFLES)
        tt[kind] = turnout_verdict(t0, r, sg, SCORED)
        tt[kind]["by_election_detail"] = {int(y): r[y] for y in SCORED if r[y] is not None}
        tt[kind]["standing"] = "passes: adopted provisionally" if tt[kind]["passes"] else ("collapse: lambda 0 everywhere, the baseline" if tt[kind]["collapse_lambda_zero"] else "fails")
    out["turnout"] = tt
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("shuffled_gains", "by_election_detail")} for k, v in tt.items() if k != "T0"}, indent=1, default=float))

    # ---- A7. the district swing model
    print("A7. the district swing model")
    S_marg = {y: marg[y].to_dict() for y in marg.columns}
    V = pd.read_csv(INTERIM / "state_demographics_vintages.csv"); V = V[V.election <= 2020].set_index("election")
    years_used = {y: int(V.loc[y, "year_before"]) for y in (2000, 2008, 2016, 2020)}
    X = district_features(years_used)
    swing = {"years_with_features": sorted(int(y) for y in X)}
    if X:
        J = jacobson_districts()
        # Jacobson's five districts against the pages: rows more than 2 points off are reported and dropped from the fit
        bad = []
        for _, r in D[D.year.isin(ELECTIONS)].iterrows():
            jj = J[(J.year == r.year) & (J.state == r.state) & (J.cd == int(r.contest[-1]))]
            if len(jj) and abs(float(jj.margin.iloc[0]) - r.margin_2p) > 2:
                bad.append((int(r.year), r.contest))                               # no value from the private file is written
        for y, contest in bad:
            J = J[~((J.year == y) & (J.state == contest[:2]) & (J.cd == int(contest[-1])))]
        swing["jacobson_vs_pages_dropped"] = bad
        J, db = downballot_check(J)
        swing["jacobson_vs_downballot"] = db
        F = swing_frame(J, S_marg, X, [y for y in (2000, 2008, 2016, 2020) if y in X])
        fit_only = tuple(y for y in (2000,) if y in set(F.year))
        scored = tuple(y for y in (2008, 2016, 2020) if y in set(F.year))
        if 2000 not in set(F.year):
            fit_only, scored = (2008,), tuple(y for y in (2016, 2020) if y in set(F.year))
        need = 2
        rs = run_swing(F, scored, fit_only)
        rng = np.random.default_rng(SEEDS["D1"])
        sg = [swing_verdict(run_swing(F, scored, fit_only, perm_seed=int(rng.integers(1 << 31))), [], need)["gain_mse"] for _ in range(SHUFFLES)]
        vd = swing_verdict(rs, sg, need)
        # the five districts, reported
        five = {}
        for y in scored:
            beta = rs[y]["beta"]
            rows = []
            for contest in DISTRICTS:
                st, cd = contest[:2], int(contest[-1])
                x = X.get(y, {}).get((st, cd))
                r1 = D[(D.year == y) & (D.contest == contest)]; r0 = D[(D.year == y - 4) & (D.contest == contest)]
                if x is None or not len(r1) or not len(r0):
                    continue
                sw = float(r1.lean_vs_state.iloc[0] - r0.lean_vs_state.iloc[0])
                rows.append({"contest": contest, "x": x, "swing": sw, "pred_d1": beta * x, "sq_d0": sw ** 2, "sq_d1": (sw - beta * x) ** 2})
            five[int(y)] = rows
        five_gain = float(np.mean([np.mean([r["sq_d0"] - r["sq_d1"] for r in rows]) for rows in five.values() if rows])) if any(five.values()) else None
        vd["five_districts"] = {"rows": five, "gain_mse": five_gain}
        vd["flags"] = {"five_districts_worse": five_gain is not None and five_gain < 0}
        vd["fit_only"], vd["scored"] = fit_only, scored
        vd["standing"] = ("passes" + ("; flagged (the five districts are worse): to the user" if vd["flags"]["five_districts_worse"] else ": adopted provisionally")) if vd["passes"] else "fails"
        swing["D1"] = vd
        swing["usable_by_election"] = {int(y): int((F.year == y).sum()) for y in sorted(set(F.year))}
        print(json.dumps({k: v for k, v in vd.items() if k not in ("shuffled_gains", "five_districts")}, indent=1, default=float))
        print("  five districts:", json.dumps(vd["five_districts"], default=float)[:1500])
    else:
        swing["D1"] = "not run: district_demographics.csv has no usable year"
    out["districts"] = swing
    sigD, nch, byd = district_sigma(D, 2024)
    out["districts"]["sigma_D_all_to_2020"] = {"sigma": sigD, "changes": nch, "by_district": byd}

    # ---- D. the as-of assembly: outputs written, identities and Monte Carlo error read
    adopted_turnout = "T1" if tt["T1"]["passes"] and not tt["T2"]["passes"] else ("T2" if tt["T2"]["passes"] and not tt["T1"]["passes"]
                      else ("T1" if tt["T1"]["passes"] and tt["T1"]["gain_sq_points"] >= tt["T2"]["gain_sq_points"] else ("T2" if tt["T2"]["passes"] else None)))
    out["turnout"]["adopted"] = adopted_turnout
    asof, ident, mce = asof_assembly(cells, q, D, ecells, Q, states, nat_err, adopted_turnout, sh, pop, vint)
    out["identities"] = ident
    out["monte_carlo_error_7d"] = mce
    (OUT / "pres_sim_asof.json").write_text(json.dumps(asof, indent=0, default=float))
    (OUT / "pres_sim.json").write_text(json.dumps(out, indent=1, default=float))
    print("identities:", json.dumps(ident, indent=1, default=float))
    print("Monte Carlo error at 7 days:", json.dumps(mce, indent=1, default=float))
    print("written: pres_sim.json, pres_sim_asof.json")


if __name__ == "__main__":
    {"checks": checks, "run": run, "asof": asof}[sys.argv[1] if len(sys.argv) > 1 else "checks"]()
