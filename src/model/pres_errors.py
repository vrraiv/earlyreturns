"""EC-5: how state errors move together (ELECTORAL_COLLEGE.md, section 14).

A state's miss is its result less the forecast as EC-2 to EC-4 leave it: the prior plus F's weight times the gap to its
polls (pres_prior.py), then the even shift to stage 3's national forecast (pres_addup.py). 2000's estimate is its own
polls (w = 1). Each election's 51 misses are centred on their plain mean and scored by the Gaussian log density of the
50 contrasts under a structure fitted on the elections before it.
  structure  Sigma = sigma_T^2 x corr(A),  A = I + sum of components   (the state's own error fixed at 1)
  baseline   rho_r R + rho_b ll'        R: same Census region; l: lean at the previous election, centred, in tens
  1          + rho_e z_e z_e'           z_e: degree share of adults 25 and over, standardized within the year used
  2          + rho_w z_w z_w'           z_w: white share without a degree, standardized likewise
  3          rho_k K + rho_b ll'        K: exp(-d^2 / 2 m^2) on six standardized by-year measures, in place of R
Fits: maximum likelihood on earlier elections only (2000 and 2004 fit-only; 2008 to 2020 scored), sigma_T^2 profiled,
sizes bounded at zero, three starting points. Score: the mean log density over the four scored elections at 7 days.
Rule: the gain beats the 95th percentile of 200 shuffles of the feature (one reordering of the states, held across
years); better in 3 of 4 elections; simulation noise is nil (closed form). Five flags send a pass to the user.

Run:  python src/model/pres_errors.py checks     (prints pass or fail only; no loss and no fitted number)
      python src/model/pres_errors.py run
      python src/model/pres_errors.py spread    (after the round: each contest's centred spread under each fitted structure)
      python src/model/pres_errors.py checks2      (round 2: the spread-matched control for candidate 3)
      python src/model/pres_errors.py calibrate2   (round 2's noise threshold from 200 spread-only plants; before run2)
      python src/model/pres_errors.py run2
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
import pres_prior as PP  # noqa: E402
import pres_reversion as RV  # noqa: E402
import error_structure as ES  # noqa: E402
from wiki import STATE_ABBR  # noqa: E402

INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed"
FIT_ONLY = (2000, 2004)
SCORED = (2008, 2012, 2016, 2020)
ELECTIONS = FIT_ONLY + SCORED
DAYS = (7, 30)
SCORE_DAY = 7
SHUFFLES = 200
SEEDS = {"c1": 0, "c2": 1, "c3": 2, "f": 3, "g": 4}
STARTS = (0.1, 1.0, 0.01)             # every size starts at this value
ZERO = 1e-6                           # a fitted size below this is zero (the bounded fit stops just inside the bound)
LEAN_SCALE = 10.0                     # lean enters the fit in tens of points, for conditioning only
MEASURES6 = ["degree_share", "log_inc", "white_share", "black_share", "latino_share", "rural_share"]
FEAT_KEY = {"c1": "feat", "c2": "feat", "c3": "sim", "g": "sim", "f": None}
COLLAPSE = ("c1", "c2")              # at zero size these are the baseline; candidate 3 at zero size is the tilt alone
TOL = 1e-5                            # the iterative fit's tolerance: margins for "better", "positive" and the shuffle
NEED = 3


# ------------------------------------------------------------------------------------------------ the misses
def load_misses():
    """By (election, day): the 51 misses (result less the forecast as EC-2 to EC-4 leave it), the estimate, the lean at
    the previous election and the states. 2000 to 2020 at 7 and 30 days; 2000's estimate is its own polls."""
    q, R, Nd, L, votes = PP.load_all()
    A = PP.assemble(PP.poll_cells(q), Nd, R, L, votes)
    EF, _ = PP.rung(A, "F")
    E = RV.load()
    assert 2024 not in E and max(y for y, _ in R) <= 2020
    out = {}
    for y in ELECTIONS:
        for d in DAYS:
            a = A[(y, d)]
            mu = EF[(y, d)] if y in PP.SCORED else PP.estimate(a, "prior0", 1.0)
            natF = float(E[y]["N"][d]) * (1 - float(E[y]["u"][d]) / 100)
            C = mu + (natF - float(a["v"] @ mu))
            out[(y, d)] = {"states": list(PP.STATES), "miss": a["result"] - C, "est": C, "result": a["result"].copy(),
                           "lean": a["lean1"].copy(), "has": a["has"].copy()}
    return out


# ------------------------------------------------------------------------------------------------ the features
class Demo:
    """DA-11's tables, with 2024 refused: no survey year after 2019, no census after 2010, no election after 2020."""

    def __init__(self):
        V = pd.read_csv(INTERIM / "state_demographics_vintages.csv")
        V = V[V.election <= 2020]
        assert V.election.max() <= 2020
        self.V = V.set_index("election")
        last = int(self.V[["year_before", "own_year"]].max().max())
        assert last <= 2019
        D = pd.read_csv(INTERIM / "state_demographics.csv")
        self.D = D[D.year <= last]
        U = pd.read_csv(INTERIM / "state_rural_share.csv")
        self.U = U[U.census <= int(self.V.rural_census.max())]
        assert self.U.census.max() <= 2010
        self._urban = None

    def urban(self):
        """The Downballot's urban share by state, one snapshot (118th Congress), for report (g) only."""
        if self._urban is None:
            d = sorted((ROOT / "data/linked/downballot").glob("*/urban_rural_cd118.xlsx"))[-1]
            u = pd.read_excel(d).drop_duplicates("CD")
            abbr = dict(STATE_ABBR, **{"District of Columbia": "DC"})     # wiki's table has the 50 states only
            u = u[u.CD.isin(abbr)]
            s = pd.Series(100.0 * u["Urban %"].astype(float).values, index=u.CD.map(abbr).values)
            assert "DC" in s.index and len(s) == 51
            self._urban = s
        return self._urban

    def features(self, y, vintage="year_before", states=None, urban=False):
        yr = int(self.V.loc[y, vintage]); cen = int(self.V.loc[y, "rural_census"])
        states = list(states)
        d = self.D[self.D.year == yr].set_index("state").loc[states]
        d = d.select_dtypes("number").copy()
        d["log_inc"] = np.log(d.median_household_income)
        d["rural_share"] = self.U[self.U.census == cen].set_index("state").rural_share.loc[states].values
        cols = MEASURES6 + (["urban_share"] if urban else [])
        if urban:
            d["urban_share"] = self.urban().loc[states].values
        z = (d - d.mean()) / d.std(ddof=1)
        return {"z_e": z.degree_share.values.copy(), "z_w": z.white_no_degree_share.values.copy(),
                "M": z[cols].values.copy(), "year": yr, "census": cen}


def permute(feat, perm):
    if perm is None:
        return feat
    return dict(feat, z_e=feat["z_e"][perm], z_w=feat["z_w"][perm], M=feat["M"][perm])


def kernel(M):
    diff = M[:, None, :] - M[None, :, :]
    dist = np.sqrt((diff ** 2).sum(2))
    m = float(np.median(dist[np.triu_indices(len(M), 1)]))
    return np.exp(-dist ** 2 / (2 * m * m))


def region_matrix(states):
    r = [ES.STATE_REGION[s] for s in states]
    return np.array([[1.0 if a == b else 0.0 for b in r] for a in r])


def contrast_basis(n):
    """A fixed orthonormal basis (n-1 rows) of the space orthogonal to a constant."""
    w, v = np.linalg.eigh(np.eye(n) - np.ones((n, n)) / n)
    Q = v[:, w > 0.5].T
    assert Q.shape == (n - 1, n) and np.allclose(Q @ np.ones(n), 0) and np.allclose(Q @ Q.T, np.eye(n - 1))
    return Q


def comps_for(kind, Rm, lean, feat):
    """The structure's components for one election, in the order of its fitted sizes."""
    l = (lean - lean.mean()) / LEAN_SCALE
    tilt = np.outer(l, l)
    if kind == "indep":
        return {}
    if kind == "tilt":
        return {"tilt": tilt}
    base = {"region": Rm, "tilt": tilt}
    if kind in ("base", "f"):
        return base
    if kind == "c1":
        return dict(base, feat=np.outer(feat["z_e"], feat["z_e"]))
    if kind == "c2":
        return dict(base, feat=np.outer(feat["z_w"], feat["z_w"]))
    if kind in ("c3", "g"):
        return {"sim": kernel(feat["M"]), "tilt": tilt}
    if kind == "c3c1":
        return {"sim": kernel(feat["M"]), "tilt": tilt, "feat": np.outer(feat["z_e"], feat["z_e"])}
    if kind == "c3c2":
        return {"sim": kernel(feat["M"]), "tilt": tilt, "feat": np.outer(feat["z_w"], feat["z_w"])}
    raise ValueError(kind)


def build_cells(M, demo, d=SCORE_DAY, vintage="year_before", states=None, urban=False):
    """Per election: the centred misses in the contrast basis, the region matrix, the lean and the features."""
    all_states = M[(ELECTIONS[0], d)]["states"]
    states = list(states) if states is not None else list(all_states)
    ix = np.array([all_states.index(s) for s in states])
    Q = contrast_basis(len(states))
    Rm = region_matrix(states)
    cells = {}
    for y in ELECTIONS:
        m = M[(y, d)]["miss"][ix]
        cells[y] = {"ym": Q @ (m - m.mean()), "miss": m, "Rm": Rm, "lean": M[(y, d)]["lean"][ix],
                    "feat": demo.features(y, vintage, states, urban=urban), "states": states}
    return cells, Q, states


# ------------------------------------------------------------------------------------------------ the density
def corr_from(A):
    dinv = 1.0 / np.sqrt(np.diag(A))
    return A * dinv[:, None] * dinv[None, :]


def full_corr(comps, rho, n):
    A = np.eye(n)
    for r, Cm in zip(rho, comps.values()):
        A = A + r * Cm
    return corr_from(A)


def contrast_cov(comps, rho, Q):
    """comps: the structure's components (a dict), or a callable rho -> a 51 x 51 covariance shape (round 2's control)."""
    V = comps(rho) if callable(comps) else full_corr(comps, rho, Q.shape[1])
    return Q @ V @ Q.T


def centred_var(V, n):
    P = np.eye(n) - np.ones((n, n)) / n
    return np.diag(P @ V @ P)


def control_builder(comps0, D):
    """Round 2's spread-matched control: candidate 3's centred variances D with the baseline's centred correlations.
    rho are the baseline's two sizes; the overall scale is profiled as sigma_T^2."""
    n = len(D)
    P = np.eye(n) - np.ones((n, n)) / n
    sq = np.sqrt(D)

    def build(rho):
        C0 = P @ full_corr(comps0, rho, n) @ P
        dinv = 1.0 / np.sqrt(np.diag(C0))
        return (C0 * dinv[:, None] * dinv[None, :]) * sq[:, None] * sq[None, :]
    return build


def _solve(S, ym, xm):
    cf = cho_factor(S)
    logdet = 2.0 * float(np.log(np.diag(cf[0])).sum())
    Siy = cho_solve(cf, ym)
    if xm is None:
        return logdet, float(ym @ Siy), 0.0, 0.0, 0.0
    Six = cho_solve(cf, xm)
    return logdet, float(ym @ Siy), float(xm @ Siy), float(xm @ Six), 0.0


def profile(rho, data, Q):
    """For given sizes: the profiled sigma_T^2 and mean coefficient, and the negative log likelihood up to a constant.
    data: list of (comps, ym, xm); xm is None without a mean term."""
    k = Q.shape[0]
    parts = [_solve(contrast_cov(c, rho, Q), ym, xm) for c, ym, xm in data]
    with_mean = data[0][2] is not None
    beta = sum(p[2] for p in parts) / sum(p[3] for p in parts) if with_mean else 0.0
    quad = 0.0
    for (c, ym, xm), p in zip(data, parts):
        if with_mean:
            S = contrast_cov(c, rho, Q)
            r = ym - beta * xm
            quad += float(r @ cho_solve(cho_factor(S), r))
        else:
            quad += p[1]
    n = len(data)
    s2 = quad / (k * n)
    nll = 0.5 * (sum(p[0] for p in parts) + k * n * np.log(s2) + k * n)
    return nll, s2, beta


def fit(data, Q, ncomp, starts=STARTS):
    """Sizes bounded at zero, from three fixed starting points, keeping the lowest loss."""
    if ncomp == 0:
        nll, s2, beta = profile(np.zeros(0), data, Q)
        return np.zeros(0), s2, beta, nll
    best = None
    for s in starts:
        o = minimize(lambda r: profile(r, data, Q)[0], np.full(ncomp, s), method="L-BFGS-B",
                     bounds=[(0.0, None)] * ncomp)
        if best is None or o.fun < best.fun - 1e-12:
            best = o
    nll, s2, beta = profile(best.x, data, Q)
    return np.array(best.x, float), s2, beta, nll


def logdens(comps, ym, xm, rho, s2, beta, Q):
    k = Q.shape[0]
    S = contrast_cov(comps, rho, Q)
    r = ym - (beta * xm if xm is not None else 0.0)
    cf = cho_factor(S)
    logdet = 2.0 * float(np.log(np.diag(cf[0])).sum())
    return float(-0.5 * (k * np.log(2 * np.pi) + k * np.log(s2) + logdet + float(r @ cho_solve(cf, r)) / s2))


# ------------------------------------------------------------------------------------------------ one structure
def run_control(cells, Q, perm=None, years=SCORED, flat=False):
    """Round 2: for each scored election, fit candidate 3 on the earlier elections, take the centred variances its
    fitted covariance gives every contest (in each election, from that election's features), and fit the control
    (those variances, the baseline's correlations) on the same earlier elections. flat=True uses the baseline's own
    centred variances instead (report iii)."""
    n = Q.shape[1]
    feats = {y: permute(c["feat"], perm) for y, c in cells.items()}
    c3 = {y: comps_for("c3", c["Rm"], c["lean"], feats[y]) for y, c in cells.items()}
    c0 = {y: comps_for("base", c["Rm"], c["lean"], feats[y]) for y, c in cells.items()}
    out = {}
    for y in years:
        train_y = [e for e in ELECTIONS if e < y]
        if flat:
            rho0, s20, _, _ = fit([(c0[e], cells[e]["ym"], None) for e in train_y], Q, 2)
            D = {e: centred_var(s20 * full_corr(c0[e], rho0, n), n) for e in train_y + [y]}
            fitted = {"rho": {k: float(v) for k, v in zip(c0[y], rho0)}, "sigma_T": float(np.sqrt(s20))}
        else:
            rho3, s23, _, _ = fit([(c3[e], cells[e]["ym"], None) for e in train_y], Q, 2)
            D = {e: centred_var(s23 * full_corr(c3[e], rho3, n), n) for e in train_y + [y]}
            fitted = {"rho": {k: float(v) for k, v in zip(c3[y], rho3)}, "sigma_T": float(np.sqrt(s23))}
        builders = {e: control_builder(c0[e], D[e]) for e in train_y + [y]}
        rho, s2, beta, _ = fit([(builders[e], cells[e]["ym"], None) for e in train_y], Q, 2)
        sd = np.sqrt(D[y])
        names = cells[y].get("states", list(range(n)))
        out[y] = {"ld": logdens(builders[y], cells[y]["ym"], None, rho, s2, beta, Q),
                  "rho": {k: float(r) for k, r in zip(c0[y], rho)}, "sigma_T": float(np.sqrt(s2)), "beta": 0.0,
                  "from_candidate3": fitted, "spread_ratio": float(sd.max() / sd.min()),
                  "widest": {str(names[i]): round(float(sd[i]), 2) for i in np.argsort(-sd)[:5]}}
    return out


def run_kind(kind, cells, Q, perm=None, years=SCORED):
    """Fit on the elections before each scored one and score it. kind 'f' is the baseline's covariance with a mean
    beta x z_w (report f); 'ctrl' is round 2's control. Returns by scored election: the log density, the fitted
    sizes, sigma_T and beta."""
    if kind == "ctrl":
        return run_control(cells, Q, perm, years)
    data = {}
    for y, c in cells.items():
        f = permute(c["feat"], perm)
        data[y] = (comps_for(kind, c["Rm"], c["lean"], f), c["ym"], Q @ f["z_w"] if kind == "f" else None)
    out = {}
    for y in years:
        train = [data[e] for e in ELECTIONS if e < y]
        keys = list(data[y][0].keys())
        rho, s2, beta, _ = fit(train, Q, len(keys))
        out[y] = {"ld": logdens(*data[y], rho, s2, beta, Q), "rho": {k: float(r) for k, r in zip(keys, rho)},
                  "sigma_T": float(np.sqrt(s2)), "beta": float(beta)}
    return out


def pooled(res, years=SCORED):
    return float(np.mean([res[y]["ld"] for y in years]))


def shuffle_gains(kind, cells, Q, base, seed, shuffles, years=SCORED):
    """Each shuffle draws one reordering of the states and applies it to the feature in every election."""
    rng = np.random.default_rng(seed)
    n = Q.shape[1]
    G = np.zeros((shuffles, len(years)))
    for s in range(shuffles):
        perm = rng.permutation(n)
        c = run_kind(kind, cells, Q, perm=perm, years=years)
        G[s] = [c[y]["ld"] - base[y]["ld"] for y in years]
    return G


def verdict(base, cand, G, years=SCORED, need=NEED, key=None, collapse=False):
    """The three clauses on the pooled score (the noise clause at zero noise is a positive gain), plus the collapse
    clause for candidates 1 and 2. The shuffled pooled gains are kept for the report."""
    by = {int(y): float(cand[y]["ld"] - base[y]["ld"]) for y in years}
    gain = float(np.mean(list(by.values())))
    better = int(sum(g > TOL for g in by.values()))
    sg = G.mean(1)
    p95 = float(np.percentile(sg, 95))
    sizes = {int(y): float(cand[y]["rho"][key]) for y in years} if key else {}
    collapsed = bool(collapse and key and all(v < ZERO for v in sizes.values()))
    c_shuf, c_pos, c_el = bool(gain > p95 + TOL), bool(gain > TOL), bool(better >= need)
    passes = c_shuf and c_pos and c_el and not collapsed
    return {"gain": gain, "by_election": by, "better": better, "need": need, "shuffle_p95": p95,
            "shuffle_share_beaten": float(np.mean(sg < gain - TOL)), "shuffles": int(len(sg)),
            "shuffled_gains": [round(float(x), 6) for x in sg],
            "clause_shuffle": c_shuf, "clause_positive_gain": c_pos, "clause_simulation_noise": "nil: closed form",
            "clause_elections": c_el, "fitted_size": sizes, "collapsed": collapsed, "passes": passes}


def implied(kind, cells, res, Q):
    """Report (a): what the fitted sizes mean for a scored election: the mean correlation within and between regions
    and each component's share of a typical state's variance."""
    out = {}
    for y, r in res.items():
        c = cells[y]
        comps = comps_for(kind, c["Rm"], c["lean"], c["feat"])
        rho = np.array([r["rho"][k] for k in comps])
        A = np.eye(Q.shape[1])
        for rr, Cm in zip(rho, comps.values()):
            A = A + rr * Cm
        C = corr_from(A)
        off = ~np.eye(len(A), dtype=bool)
        same = (c["Rm"] > 0.5) & off
        out[int(y)] = {"sigma_T": r["sigma_T"], "within_region_corr": float(C[same].mean()),
                       "between_region_corr": float(C[off & ~same].mean()),
                       "variance_share": {k: float(rr * np.mean(np.diag(Cm)) / np.mean(np.diag(A)))
                                          for k, rr, Cm in zip(comps, rho, comps.values())}}
    return out


# ------------------------------------------------------------------------------------------------ the decision
def judge(cells, Q, kinds=("c1", "c2", "c3"), shuffles=SHUFFLES, years=SCORED, need=NEED, seeds=SEEDS):
    """The baseline and each candidate on one set of cells, with the shuffle clause. Returns the verdicts and the
    per-shuffle gains by election (for report e)."""
    base = run_kind("base", cells, Q, years=years)
    out = {"base": {"by_election": {int(y): base[y]["ld"] for y in years}, "pooled": pooled(base, years),
                    "fits": {int(y): base[y] for y in years}}}
    G = {}
    for kind in kinds:
        cand = run_kind(kind, cells, Q, years=years)
        G[kind] = shuffle_gains(kind, cells, Q, base, seeds[kind], shuffles, years)
        v = verdict(base, cand, G[kind], years, need, FEAT_KEY[kind], collapse=kind in COLLAPSE)
        v["fits"] = {int(y): cand[y] for y in years}
        v["pooled"] = pooled(cand, years)
        out[kind] = v
    return out, base, G


def flags_for(kind, v, no_dc, day30):
    f = []
    if kind == "c2":
        f.append(1)
    if no_dc is None or not (no_dc["gain"] > 0 and no_dc["clause_elections"]):
        f.append(2)
    if day30 is None or not day30["gain"] > 0:
        f.append(3)
    if v["fitted_size"] and v["fitted_size"][max(v["fitted_size"])] < ZERO:
        f.append(4)
    if kind == "c1":
        f.append(5)
    return f


def decide(M, demo, shuffles=SHUFFLES):
    cells, Q, states = build_cells(M, demo)
    out = {"scored": list(SCORED), "fit_only": list(FIT_ONLY), "contests": len(states), "score_day": SCORE_DAY,
           "shuffles": shuffles}
    main, base, G = judge(cells, Q, shuffles=shuffles)
    out["main"] = main
    out["implied"] = {k: implied(k, cells, main[k]["fits"] if k != "base" else base, Q) for k in ("base", "c1", "c2", "c3")}
    # variants: own-year vintage (b), without DC (c), 30 days (d); full clauses each
    out["variants"] = {}
    for name, kw in (("own_year", dict(vintage="own_year")), ("no_dc", dict(states=[s for s in states if s != "DC"])),
                     ("day30", dict(d=30))):
        cv, Qv, _ = build_cells(M, demo, **kw)
        res, _, _ = judge(cv, Qv, shuffles=shuffles)
        out["variants"][name] = res
    # report (e): 2008 apart, and the clauses on 2012 to 2020 asking 2 of 3
    late = SCORED[1:]
    out["report_e"] = {k: verdict(base, {y: main[k]["fits"][y] for y in late}, G[k][:, 1:], late, 2, FEAT_KEY[k], k in COLLAPSE)
                       for k in ("c1", "c2", "c3")}
    # report (f): the fixed-sign form, suggested by the overfitting challenge
    f = run_kind("f", cells, Q)
    Gf = shuffle_gains("f", cells, Q, base, SEEDS["f"], shuffles)
    vf = verdict(base, f, Gf); vf["fits"] = {int(y): f[y] for y in SCORED}; vf["pooled"] = pooled(f)
    out["report_f"] = vf
    # report (g): candidate 3 with The Downballot's urban share as a fixed seventh measure
    cg, Qg, _ = build_cells(M, demo, urban=True)
    g = run_kind("g", cg, Qg)
    Gg = shuffle_gains("g", cg, Qg, base, SEEDS["g"], shuffles)
    vg = verdict(base, g, Gg, key="sim"); vg["fits"] = {int(y): g[y] for y in SCORED}; vg["pooled"] = pooled(g)
    out["report_g"] = vg
    # report (h): the baseline's own parts
    out["report_h"] = {k: {"by_election": {int(y): r[y]["ld"] for y in SCORED}, "pooled": pooled(r),
                           "fits": {int(y): r[y] for y in SCORED}}
                       for k, r in (("tilt_only", run_kind("tilt", cells, Q)), ("independent", run_kind("indep", cells, Q)))}
    # flags, adoption
    out["flags"] = {}
    passing = []
    for k in ("c1", "c2", "c3"):
        if main[k]["passes"]:
            fl = flags_for(k, main[k], out["variants"]["no_dc"][k], out["variants"]["day30"][k])
            out["flags"][k] = fl
            passing.append((main[k]["gain"], k, fl))
    clean = [p for p in passing if not p[2]]
    out["passing"] = [k for _, k, _ in passing]
    out["adopted"] = max(clean)[1] if clean else None
    out["to_user"] = [k for _, k, fl in passing if fl]
    if "c3" in out["passing"] and ({"c1", "c2"} & set(out["passing"])):
        out["combination"] = {}
        for k2 in ("c1", "c2"):
            if k2 in out["passing"]:
                comb = run_kind("c3" + k2, cells, Q)
                out["combination"]["c3+" + k2] = {"by_election": {int(y): comb[y]["ld"] - base[y]["ld"] for y in SCORED},
                                                  "gain": pooled(comb) - pooled(base), "fits": {int(y): comb[y] for y in SCORED}}
    out["standing"] = out["adopted"] or "baseline: regions and the tilt"
    return out


def frame_csv(M, demo):
    rows = []
    for (y, d), m in M.items():
        f = demo.features(y, "year_before", m["states"])
        for i, s in enumerate(m["states"]):
            rows.append({"cycle": y, "d": d, "state": s, "region": ES.STATE_REGION[s], "has_poll": bool(m["has"][i]),
                         "estimate": m["est"][i], "result": m["result"][i], "miss": m["miss"][i], "prev_lean": m["lean"][i],
                         "demo_year": f["year"], "z_degree": f["z_e"][i], "z_white_no_degree": f["z_w"][i]})
    return pd.DataFrame(rows)


def run():
    M = load_misses(); demo = Demo()
    frame_csv(M, demo).to_csv(OUT / "pres_errors_frame.csv", index=False)
    out = decide(M, demo)
    (OUT / "pres_errors.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("passing", "flags", "adopted", "to_user", "standing")}, indent=1))
    for k in ("c1", "c2", "c3"):
        v = out["main"][k]
        print(f"{k}: gain {v['gain']:.3f}  p95 {v['shuffle_p95']:.3f}  better {v['better']}/4  sizes {v['fitted_size']}  passes {v['passes']}")
    print("report f:", {k: out["report_f"][k] for k in ("gain", "shuffle_p95", "better", "passes")})
    print("report g:", {k: out["report_g"][k] for k in ("gain", "shuffle_p95", "better", "passes")})


# ------------------------------------------------------------------------------------------------ checks
def plant(cells, Q, kind, rho, sigma, rng, mean_beta=0.0):
    """Synthetic centred misses drawn from a known structure built on the real matrices of each election."""
    out = {}
    for y, c in cells.items():
        comps = comps_for(kind, c["Rm"], c["lean"], c["feat"])
        A = np.eye(Q.shape[1])
        for r, Cm in zip(rho, comps.values()):
            A = A + r * Cm
        L = np.linalg.cholesky(corr_from(A))
        m = sigma * (L @ rng.standard_normal(len(A))) + mean_beta * c["feat"]["z_w"]
        out[y] = dict(c, ym=Q @ (m - m.mean()), miss=m)
    return out


def checks():
    ok = True

    def report(name, passed):
        nonlocal ok
        ok = ok and bool(passed)
        print(f"{'pass' if passed else 'FAIL'}  {name}")

    M = load_misses(); demo = Demo()
    report("2024 absent from demographics, rural shares, vintages, results and the national series",
           demo.D.year.max() <= 2019 and demo.U.census.max() <= 2010 and demo.V.index.max() <= 2020
           and max(y for y, _ in M) <= 2020)
    F = pd.read_csv(OUT / "pres_addup_rerun_frame.csv")
    same = True
    for y in PP.SCORED:
        for d in DAYS:
            g = F[(F.cycle == y) & (F.d == d)].set_index("state")
            m = M[(y, d)]
            same &= np.allclose(g.loc[m["states"], "C"].values, m["est"]) and np.allclose(g.loc[m["states"], "result"].values, m["result"])
    report("rebuilt 7- and 30-day estimates and results equal pres_addup_rerun_frame.csv's C and result, 2004 to 2020", same)
    report("2000's estimate exists at 7 and 30 days for all 51 contests, all polled",
           all(np.isfinite(M[(2000, d)]["est"]).all() and M[(2000, d)]["has"].all() for d in DAYS))
    cells, Q, states = build_cells(M, demo)
    # a constant added to every miss of an election changes nothing
    c2 = {y: dict(c) for y, c in cells.items()}
    for y in (2004, 2016):
        m = cells[y]["miss"] + 7.5
        c2[y]["ym"] = Q @ (m - m.mean())
    a, b = run_kind("c1", cells, Q), run_kind("c1", c2, Q)
    report("a constant added to every miss changes no score and no fit (to the iterative fit's tolerance, 1e-5)",
           all(abs(a[y]["ld"] - b[y]["ld"]) < 1e-5 and all(abs(a[y]["rho"][k] - b[y]["rho"][k]) < 1e-5 for k in a[y]["rho"]) for y in SCORED))
    # at rho = 0 the log density is the independent-errors formula
    k = Q.shape[0]
    y0 = cells[2016]["ym"]; s2 = 4.0
    ld = logdens(comps_for("base", cells[2016]["Rm"], cells[2016]["lean"], cells[2016]["feat"]), y0, None, np.zeros(2), s2, 0.0, Q)
    report("at sizes zero the log density equals the formula for independent errors with one spread",
           abs(ld - (-0.5 * (k * np.log(2 * np.pi) + k * np.log(s2) + float(y0 @ y0) / s2))) < 1e-9)
    # planted structures are recovered, from each starting point
    rng = np.random.default_rng(11)
    truth = np.array([0.5, 0.3, 0.8]); sig = 5.0
    many = {}
    for rep in range(10):
        for y, c in plant(cells, Q, "c1", truth, sig, rng).items():
            many[(rep, y)] = c
    data = [(comps_for("c1", c["Rm"], c["lean"], c["feat"]), c["ym"], None) for c in many.values()]
    recovered = True
    for s in STARTS:
        rho, s2, _, _ = fit(data, Q, 3, starts=(s,))
        recovered &= bool(np.all(np.abs(rho - truth) < 0.25 * truth + 0.05) and abs(np.sqrt(s2) - sig) < 0.5)
    report("planted region, tilt and feature sizes and the spread are recovered from 60 synthetic elections, from each start", recovered)
    # identity shuffle reproduces; a real one changes
    ident = run_kind("c3", cells, Q, perm=np.arange(len(states)))
    real = run_kind("c3", cells, Q, perm=np.random.default_rng(5).permutation(len(states)))
    plain = run_kind("c3", cells, Q)
    report("an identity shuffle reproduces candidate 3 exactly and a real one changes its score",
           all(abs(ident[y]["ld"] - plain[y]["ld"]) < 1e-9 for y in SCORED) and any(abs(real[y]["ld"] - plain[y]["ld"]) > 1e-6 for y in SCORED))
    # the decision path on planted misses, 30 shuffles
    rng = np.random.default_rng(3)
    pl = plant(cells, Q, "c1", np.array([0.3, 0.3, 3.0]), 5.0, rng)
    res, _, _ = judge(pl, Q, shuffles=30)
    report("planted degree draw: candidate 1 passes its clauses", res["c1"]["passes"])
    pl = plant(cells, Q, "base", np.array([1.5, 0.3]), 5.0, rng)
    res, _, _ = judge(pl, Q, shuffles=30)
    report("planted regions and tilt only: no candidate passes", not any(res[k]["passes"] for k in ("c1", "c2", "c3")))
    pl = plant(cells, Q, "c3", np.array([3.0, 0.3]), 5.0, rng)
    res, _, _ = judge(pl, Q, shuffles=30)
    report("planted similarity: candidate 3 passes its clauses", res["c3"]["passes"])
    pl = plant(cells, Q, "base", np.array([0.3, 0.3]), 5.0, rng, mean_beta=-3.0)
    base = run_kind("base", pl, Q); f = run_kind("f", pl, Q)
    report("planted fixed-sign term: report (f) recovers its sign and beats the baseline",
           all(f[y]["beta"] < 0 for y in SCORED) and pooled(f) > pooled(base))
    # the flag code path
    v_pass = {"fitted_size": {2020: 0.4}}
    report("flag 2 trips when the pass is not there without DC, and not otherwise",
           2 in flags_for("c3", v_pass, {"gain": -0.1, "clause_elections": True}, {"gain": 0.1})
           and 2 not in flags_for("c3", v_pass, {"gain": 0.1, "clause_elections": True}, {"gain": 0.1}))
    report("flags 1, 3, 4 and 5 trip on their conditions",
           flags_for("c2", {"fitted_size": {2020: 0.0}}, {"gain": 0.1, "clause_elections": True}, {"gain": -0.1}) == [1, 3, 4]
           and flags_for("c1", v_pass, {"gain": 0.1, "clause_elections": True}, {"gain": 0.1}) == [5])
    # the whole decision path, on planted misses at both dates, 3 shuffles: every report, flag and output executes
    rng = np.random.default_rng(8)
    M2 = {k: dict(v) for k, v in M.items()}
    for d in DAYS:
        cd, Qd, _ = build_cells(M, demo, d=d)
        for y, c in plant(cd, Qd, "c1", np.array([0.3, 0.3, 3.0]), 5.0, rng).items():
            M2[(y, d)]["miss"] = c["miss"]
    full = decide(M2, demo, shuffles=3)
    txt = json.dumps(full, default=float)
    fr = frame_csv(M2, demo)
    report("decide() runs end to end on planted misses: candidate 1 passes, is flagged and goes to the user; every report is "
           "present; the frame has 51 x 6 x 2 rows",
           "c1" in full["passing"] and 5 in full["flags"]["c1"] and "c1" in full["to_user"] and full["adopted"] != "c1"
           and all(k in full for k in ("variants", "report_e", "report_f", "report_g", "report_h", "implied"))
           and len(full["variants"]) == 3 and len(fr) == 51 * len(ELECTIONS) * len(DAYS) and len(txt) > 1000)
    print("ALL CHECKS PASS" if ok else "SOME CHECKS FAILED")


# ------------------------------------------------------------------------------------------------ round 2
def judge_round2(cells, Q, shuffles=SHUFFLES, years=SCORED, need=NEED, seed=5):
    """Candidate 3 against its spread-matched control, with the shuffle of the kernel re-deriving both."""
    base = run_kind("base", cells, Q, years=years)
    ctrl = run_kind("ctrl", cells, Q, years=years)
    c3 = run_kind("c3", cells, Q, years=years)
    rng = np.random.default_rng(seed)
    n = Q.shape[1]
    G = np.zeros((shuffles, len(years)))
    for s in range(shuffles):
        perm = rng.permutation(n)
        a = run_kind("c3", cells, Q, perm=perm, years=years)
        b = run_kind("ctrl", cells, Q, perm=perm, years=years)
        G[s] = [a[y]["ld"] - b[y]["ld"] for y in years]
    v = verdict(ctrl, c3, G, years, need)
    v["fits_control"] = {int(y): ctrl[y] for y in years}
    v["fits_candidate3"] = {int(y): c3[y] for y in years}
    v["report_i_control_vs_baseline"] = {"gain": pooled(ctrl, years) - pooled(base, years),
                                         "by_election": {int(y): ctrl[y]["ld"] - base[y]["ld"] for y in years}}
    v["report_ii_spreads"] = {int(y): {"ratio": ctrl[y]["spread_ratio"], "widest": ctrl[y]["widest"]} for y in years}
    return v


def decide_round2(M, demo, shuffles=SHUFFLES):
    cells, Q, states = build_cells(M, demo)
    out = {"round": 2, "question": "candidate 3 against its spread-matched control", "shuffles": shuffles}
    out["main"] = judge_round2(cells, Q, shuffles)
    flat = run_control(cells, Q, flat=True)
    base = run_kind("base", cells, Q)
    out["report_iii_flat_control"] = {int(y): {"flat": flat[y]["ld"], "baseline": base[y]["ld"]} for y in SCORED}
    out["variants"] = {}
    for name, kw in (("own_year", dict(vintage="own_year")), ("no_dc", dict(states=[s for s in states if s != "DC"])),
                     ("day30", dict(d=30))):
        cv, Qv, _ = build_cells(M, demo, **kw)
        out["variants"][name] = judge_round2(cv, Qv, shuffles)
    v = out["main"]
    fl = []
    if v["passes"]:
        nd, d30 = out["variants"]["no_dc"], out["variants"]["day30"]
        if not (nd["gain"] > 0 and nd["clause_elections"]):
            fl.append(2)
        if not d30["gain"] > 0:
            fl.append(3)
    out["flags"] = fl
    out["passes"] = v["passes"]
    out["standing"] = ("candidate 3 adopted provisionally: the combination (similarity, tilt, candidate 2's draw)" if v["passes"] and not fl
                       else "candidate 3 passes but is flagged: to the user" if v["passes"]
                       else "candidate 3 closed; the baseline with candidate 2 stands")
    return out


def spread_only_plants(cells, Q, base_fits, reps, seed=31):
    """Round 2's noise threshold: misses drawn from the control's own covariance (candidate 3's spreads as fitted in
    round 1, the baseline's correlation sizes as fitted in round 1), scored as candidate 3 minus its control. No
    shuffles. Returns the increments by plant and scored election."""
    n = Q.shape[1]
    ctrl = run_kind("ctrl", cells, Q)
    rng = np.random.default_rng(seed)
    V = {}
    for y, c in cells.items():
        yy = y if y in SCORED else SCORED[0]
        c3 = comps_for("c3", c["Rm"], c["lean"], c["feat"]); c0 = comps_for("base", c["Rm"], c["lean"], c["feat"])
        r3 = ctrl[yy]["from_candidate3"]
        D = centred_var(r3["sigma_T"] ** 2 * full_corr(c3, [r3["rho"][k] for k in c3], n), n)
        V[y] = np.linalg.cholesky(control_builder(c0, D)([base_fits[yy]["rho"][k] for k in c0]) + 1e-9 * np.eye(n))
    G = np.zeros((reps, len(SCORED)))
    for r in range(reps):
        pl = {}
        for y, c in cells.items():
            m = V[y] @ rng.standard_normal(n)
            pl[y] = dict(c, ym=Q @ (m - m.mean()), miss=m)
        a = run_kind("c3", pl, Q); b = run_kind("ctrl", pl, Q)
        G[r] = [a[y]["ld"] - b[y]["ld"] for y in SCORED]
    return G


def calibrate2(reps=200):
    """Writes pres_errors_round2_calibration.json: the increment's distribution on spread-only plants."""
    M = load_misses(); demo = Demo()
    cells, Q, states = build_cells(M, demo)
    base = run_kind("base", cells, Q)
    G = spread_only_plants(cells, Q, base, reps)
    pooled_g = G.mean(1)
    meets = np.mean([(g.mean() > TOL) and (np.sum(g > TOL) >= NEED) for g in G])
    out = {"plants": int(reps), "pooled_increment": {"p50": float(np.percentile(pooled_g, 50)), "p95": float(np.percentile(pooled_g, 95)),
                                                     "max": float(pooled_g.max()), "min": float(pooled_g.min())},
           "by_election_p95": {int(y): float(np.percentile(G[:, i], 95)) for i, y in enumerate(SCORED)},
           "share_meeting_positive_and_3_of_4": float(meets), "increments": [[round(float(x), 4) for x in g] for g in G]}
    (OUT / "pres_errors_round2_calibration.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "increments"}, indent=1))


def run2():
    M = load_misses(); demo = Demo()
    out = decide_round2(M, demo)
    cal = json.loads((OUT / "pres_errors_round2_calibration.json").read_text())
    thr = cal["pooled_increment"]["p95"]
    v = out["main"]
    v["planted_threshold_p95"] = thr
    v["clause_planted"] = bool(v["gain"] > thr + TOL)
    v["passes"] = bool(v["passes"] and v["clause_planted"])
    out["passes"] = v["passes"]
    fl = []
    if v["passes"]:
        nd, d30 = out["variants"]["no_dc"], out["variants"]["day30"]
        if not (nd["gain"] > 0 and nd["clause_elections"]):
            fl.append(2)
        if not d30["gain"] > 0:
            fl.append(3)
    out["flags"] = fl
    out["standing"] = ("candidate 3 passes round 2 with no flag: to the user to confirm" if v["passes"] and not fl
                       else "candidate 3 passes round 2 but is flagged: to the user" if v["passes"]
                       else "candidate 3 closed; the baseline with candidate 2 stands")
    (OUT / "pres_errors_round2.json").write_text(json.dumps(out, indent=1, default=float))
    v = out["main"]
    print(json.dumps({k: v[k] for k in ("gain", "by_election", "better", "shuffle_p95", "shuffle_share_beaten",
                                        "clause_shuffle", "clause_positive_gain", "clause_elections", "passes")}, indent=1))
    print("control vs baseline:", v["report_i_control_vs_baseline"])
    print("planted threshold p95:", v["planted_threshold_p95"], "clause_planted:", v["clause_planted"])
    print("flags", out["flags"], "standing:", out["standing"])


def checks2():
    ok = True

    def report(name, passed):
        nonlocal ok
        ok = ok and bool(passed)
        print(f"{'pass' if passed else 'FAIL'}  {name}")

    M = load_misses(); demo = Demo()
    cells, Q, states = build_cells(M, demo)
    base = run_kind("base", cells, Q); n = len(states)
    exact = True
    for y in SCORED:
        c = cells[y]; c0 = comps_for("base", c["Rm"], c["lean"], c["feat"]); rho0 = [base[y]["rho"][k] for k in c0]
        D = centred_var(base[y]["sigma_T"] ** 2 * full_corr(c0, rho0, n), n)
        S1 = Q @ control_builder(c0, D)(rho0) @ Q.T
        exact &= bool(np.abs(S1 - base[y]["sigma_T"] ** 2 * contrast_cov(c0, rho0, Q)).max() < 1e-9)
    report("the flat control at the baseline's sizes is the baseline's covariance exactly", exact)
    ident = run_kind("ctrl", cells, Q, perm=np.arange(len(states))); plain = run_kind("ctrl", cells, Q)
    real = run_kind("ctrl", cells, Q, perm=np.random.default_rng(5).permutation(len(states)))
    report("an identity shuffle reproduces the control and a real one changes it",
           all(abs(ident[y]["ld"] - plain[y]["ld"]) < 1e-9 for y in SCORED) and any(abs(real[y]["ld"] - plain[y]["ld"]) > 1e-6 for y in SCORED))
    rng = np.random.default_rng(21)
    pl = plant(cells, Q, "c3", np.array([3.0, 0.3]), 5.0, rng)
    v = judge_round2(pl, Q, shuffles=30)
    report("planted similarity: candidate 3 beats its spread-matched control", v["passes"])
    # a spread-only plant: draws from the control's own covariance built on candidate 3's fitted spreads
    n = len(states)
    ctrl = run_kind("ctrl", cells, Q)
    pl2 = {}
    for y, c in cells.items():
        yy = y if y in SCORED else SCORED[0]
        c3 = comps_for("c3", c["Rm"], c["lean"], c["feat"]); c0 = comps_for("base", c["Rm"], c["lean"], c["feat"])
        r3 = ctrl[yy]["from_candidate3"]; D = centred_var(r3["sigma_T"] ** 2 * full_corr(c3, [r3["rho"][k] for k in c3], n), n)
        V = control_builder(c0, D)([0.3, 0.3])
        L = np.linalg.cholesky(V + 1e-9 * np.eye(n))
        m = L @ rng.standard_normal(n)
        pl2[y] = dict(c, ym=Q @ (m - m.mean()), miss=m)
    v2 = judge_round2(pl2, Q, shuffles=30)
    report("planted spread only (no similarity): candidate 3 does not pass against its control", not v2["passes"])
    # decide_round2 end to end on planted misses at both dates, 2 shuffles
    M2 = {k: dict(v) for k, v in M.items()}
    for d in DAYS:
        cd, Qd, _ = build_cells(M, demo, d=d)
        for y, c in plant(cd, Qd, "c3", np.array([3.0, 0.3]), 5.0, rng).items():
            M2[(y, d)]["miss"] = c["miss"]
    full = decide_round2(M2, demo, shuffles=2)
    txt = json.dumps(full, default=float)
    report("decide_round2() runs end to end on planted misses: variants, reports and flags present, JSON written",
           len(full["variants"]) == 3 and "report_iii_flat_control" in full and "flags" in full and len(txt) > 1000)
    G = spread_only_plants(cells, Q, run_kind("base", cells, Q), reps=3, seed=1)
    report("the spread-only plants run and give one increment per plant and election", G.shape == (3, len(SCORED)) and np.isfinite(G).all())
    print("ALL ROUND-2 CHECKS PASS" if ok else "SOME ROUND-2 CHECKS FAILED")


# ------------------------------------------------------------------------------------------------ after the run
def spread():
    """Diagnostic computed after the round (2026-11-21), reading the saved fits and the features and no miss: each
    contest's centred spread, the square root of the diagonal of P Sigma P, under each structure's fitted 2020 sizes.
    It asks whether a structure widens some contests against others, which the shuffle cannot separate from
    co-movement. It flags a pass for the user and decides nothing. Writes pres_errors_spread.json."""
    o = json.loads((OUT / "pres_errors.json").read_text())
    demo = Demo()
    R = pd.read_csv(INTERIM / "state_presidential.csv"); R = R[R.year <= 2020]
    states = sorted(R.state.unique())
    n = len(states); P = np.eye(n) - np.ones((n, n)) / n
    Rm = region_matrix(states)
    out = {}
    for y in SCORED:
        lean = R[R.year == y - 4].set_index("state").lean_2p.loc[states].values
        feat = demo.features(y, "year_before", states)
        out[y] = {}
        for kind, fits in (("base", o["main"]["base"]["fits"][str(y)]), ("c1", o["main"]["c1"]["fits"][str(y)]),
                           ("c2", o["main"]["c2"]["fits"][str(y)]), ("c3", o["main"]["c3"]["fits"][str(y)])):
            A = np.eye(n)
            for k, Cm in comps_for(kind, Rm, lean, feat).items():
                A = A + fits["rho"][k] * Cm
            sd = pd.Series(np.sqrt(np.diag(P @ (fits["sigma_T"] ** 2 * corr_from(A)) @ P)), index=states)
            out[y][kind] = {"min": float(sd.min()), "median": float(sd.median()), "max": float(sd.max()),
                            "ratio_max_min": float(sd.max() / sd.min()),
                            "widest": {k: round(float(v), 2) for k, v in sd.sort_values(ascending=False).head(6).items()},
                            "narrowest": {k: round(float(v), 2) for k, v in sd.sort_values().head(4).items()},
                            "by_state": {k: round(float(v), 3) for k, v in sd.items()}}
    (OUT / "pres_errors_spread.json").write_text(json.dumps(out, indent=1))
    for y in SCORED:
        for kind in ("base", "c1", "c2", "c3"):
            s = out[y][kind]
            print(f"{y} {kind:4s} centred sd min {s['min']:.2f} median {s['median']:.2f} max {s['max']:.2f} ratio {s['ratio_max_min']:.2f}  widest {list(s['widest'])[:4]}")


if __name__ == "__main__":
    {"checks": checks, "run": run, "spread": spread, "checks2": checks2, "calibrate2": calibrate2, "run2": run2}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
