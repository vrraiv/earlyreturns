"""Stage 3 of EC-2: reversion and trend, on the national test bed (ELECTORAL_COLLEGE.md, section 11, "Stage 3:
reversion and trend, pre-registration" and the decisions and amendments after it).

Scored elections 1980 to 2020, each fitted on the elections before it (from 1952). Baseline: forecast = nowcast
(readings dated at least 3 days before the date, 60-day half-life), range a + b * days. Candidates:
  1 anchor pull            forecast = N + clip(k * d/150) * (anchor - N); anchor = ridge on approval and previous result
  2 trend survival         forecast = N + drift * direction * expected remaining weeks (shrunk discrete-time hazard)
  3 durability             (a) pull * exp(beta * s), (b) squared spread * exp(gamma * s); s = standardized steadiness
  4 undecided voters       (a) N * (1 - (1 - alpha) * u/100), (b) squared spread + kappa * u
  5 approval shifts        forecast = N - rho * (30-day movement not explained by the 30-day approval change)
  6 evenly spread shifts   diagnostic only (state polls 2004 to 2020)
Rule: mean squared error over 150, 100 and 60 days (log score for 3b and 4b), elections equal; positive gain; beat 19
in 20 of 200 shuffles of the candidate's feature between elections; better in at least 8 of 11; 30 and 7 days not
worse on average.

Run:  python src/model/pres_reversion.py checks
      python src/model/pres_reversion.py run
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402

INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed"
CYCLES = tuple(range(1952, 2021, 4))
SCORED = tuple(range(1980, 2021, 4))
LAG = 3
HL, HL_LIGHT = 60.0, 14.0
DMAX = 260
SCORE_DAYS = (150, 100, 60)
REPORT_DAYS = (30, 7)
FIT_DAYS = tuple(range(150, 9, -10)) + (7,)
RANGE_DAYS = tuple(range(7, 151))
THR = 1.5
PENS = (0.0, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)
HAZ_PENS = (0.0, 0.1, 1.0, 10.0, 100.0, 1e6)
BETAS = (0.0, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0)
GAMMAS = (0.0, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5)
ALPHAS = tuple(np.round(np.arange(0, 1.0001, 0.05), 2))
KAPPAS = tuple(np.concatenate([[0.0], np.geomspace(0.01, 20, 120)]))
SHUFFLES = 200


# ---------------------------------------------------------------- data
def wavg(t, v, d, hl):
    ok = (t >= d + LAG) & ~np.isnan(v)
    if not ok.any():
        return np.nan
    return float(np.average(v[ok], weights=0.5 ** ((t[ok] - d) / hl)))


def approval_on(g, date):
    w = g[(g.end < date) & (g.end >= date - pd.Timedelta(days=30))]
    if len(w):
        return float(w.Approving.mean())
    w = g[g.end < date]
    return float(w.Approving.iloc[-1]) if len(w) else np.nan


def undecided_repo():
    """2008 to 2016: the undecided share from the repo's national polls (the series' sources are two-party only)."""
    p = pd.read_csv(INTERIM / "president_general_polls.csv", low_memory=False)
    p = p[(p.geo == "US") & p.cycle.isin([2008, 2012, 2016]) & ~p.presumptive.astype(bool)].copy()
    p["h2h"] = p.head_to_head.fillna(False).astype(bool)
    p = p[p.h2h == p.groupby("poll_id").h2h.transform("max")]
    rank = {"lv": 0, "v": 1, "rv": 2, "a": 3}
    p["rank"] = p.population.fillna("lv").str.lower().map(rank).fillna(4)
    p = p[p["rank"] == p.groupby("poll_id")["rank"].transform("min")]
    q = p.groupby("poll_id").agg(cycle=("cycle", "first"), mid=("mid_date", "first"), el=("election_date", "first"),
                                 d=("d_pct", "mean"), r=("r_pct", "mean")).reset_index()
    q["t"] = (pd.to_datetime(q.el) - pd.to_datetime(q.mid)).dt.days.astype(float)
    q["u"] = 100 - q.d - q.r
    return {int(c): (x.t.values, x.u.values) for c, x in q.groupby("cycle")}


def load():
    d = pd.read_csv(INTERIM / "president_national_poll_days.csv", parse_dates=["date", "election_date"])
    assert 2024 not in set(d.cycle), "2024 is held out"
    g = pd.read_csv(INTERIM / "gallup_approval.csv", parse_dates=["end"]).sort_values("end")
    f = pd.read_csv(INTERIM / "fundamentals_dataset.csv")
    party = {int(y): (1.0 if p == "D" else -1.0) for y, p in zip(f.year, f.pres_party)}
    c = pd.read_csv(INTERIM / "convention_dates.csv", parse_dates=["start", "end", "election_date"])
    ur = undecided_repo()
    res = d.groupby("cycle").result_margin_2p.first().to_dict()
    E = {}
    days = np.arange(DMAX + 1)
    for y in CYCLES:
        x = d[d.cycle == y]
        el = x.election_date.iloc[0]
        t = (el - x.date).dt.days.values.astype(float)
        m = x.margin_2p.values.astype(float)
        if y in ur:
            tu, uu = ur[y]
        else:
            tu, uu = t, (100 - x.d_pct - x.r_pct).values.astype(float)
        cc = c[c.cycle == y]
        E[y] = {
            "t": t, "m": m, "result": float(res[y]), "party": party[y],
            "prev": float(res[y - 4]) if (y - 4) in res else np.nan,
            "N": np.array([wavg(t, m, k, HL) for k in days]),
            "L": np.array([wavg(t, m, k, HL_LIGHT) for k in days]),
            "u": np.array([wavg(tu, uu, k, HL) for k in days]),
            "A": np.array([approval_on(g, el - pd.Timedelta(days=int(k))) for k in days]),
            "e2": float((el - cc.end.max()).days),          # days before the election the second convention ended
        }
    return E


# ---------------------------------------------------------------- shared estimators
def ridge_scalar(x, r, pen):
    """argmin sum (r - k x)^2 + pen k^2."""
    return float((x * r).sum() / ((x * x).sum() + pen)) if ((x * x).sum() + pen) > 0 else 0.0


def loeo_pen(groups, fit, err, pens=PENS):
    """Penalty by leaving one group (election) out: fit(pen, keep) -> params; err(params, group) -> squared error."""
    best = None
    for pen in pens:
        tot = 0.0
        for gk in groups:
            keep = [g for g in groups if g != gk]
            if not keep:
                continue
            tot += err(fit(pen, keep), gk)
        if best is None or tot < best[0] - 1e-12:
            best = (tot, pen)
    return best[1]


def range_fit(errs):
    """errs: list of (days, squared error). a + b * days by least squares."""
    D = np.array([e[0] for e in errs], float)
    S = np.array([e[1] for e in errs], float)
    b, a = np.polyfit(D, S, 1)
    return float(a), float(b)


def logscore(f, res, var):
    return -0.5 * (np.log(2 * np.pi * var) + (f - res) ** 2 / var)


# ---------------------------------------------------------------- candidate 1: anchor
def anchor_model(E, years, d, pen=None):
    """Ridge of the incumbent party's result on (approval at d - 50, incumbent party's previous margin), intercept
    unpenalized, features standardized; penalty by leaving one election out. Returns a predictor and the penalty."""
    ys = [y for y in years if not np.isnan(E[y]["prev"]) and not np.isnan(E[y]["A"][d])]

    def feats(y):
        return np.array([E[y]["A"][d] - 50.0, E[y]["party"] * E[y]["prev"]])

    def fit(p, keep):
        X = np.array([feats(y) for y in keep]); Y = np.array([E[y]["party"] * E[y]["result"] for y in keep])
        mu, sd = X.mean(0), X.std(0); sd[sd == 0] = 1
        Z = (X - mu) / sd
        yb = Y.mean()
        beta = np.linalg.solve(Z.T @ Z + p * np.eye(2), Z.T @ (Y - yb))
        return (mu, sd, yb, beta)

    def pred(params, y):
        mu, sd, yb, beta = params
        return float(yb + ((feats(y) - mu) / sd) @ beta)

    if len(ys) < 4:
        return None, None
    if pen is None:
        pen = loeo_pen(ys, fit, lambda prm, g: (pred(prm, g) - E[g]["party"] * E[g]["result"]) ** 2)
    prm = fit(pen, ys)
    return (lambda y: E[y]["party"] * pred(prm, y)), pen


def anchors_for(E, earlier, target):
    """Anchor for the target election at every fit/score day (fitted on `earlier`), and leave-one-out anchors for
    each earlier election (fitted on the other earlier ones, same penalty)."""
    out_t, out_e = {}, {e: {} for e in earlier}
    for d in sorted(set(FIT_DAYS + SCORE_DAYS + REPORT_DAYS)):
        f, pen = anchor_model(E, earlier, d)
        out_t[d] = f(target) if f is not None and not np.isnan(E[target]["A"][d]) else np.nan
        for e in earlier:
            others = [x for x in earlier if x != e]
            fe, _ = anchor_model(E, others, d, pen=pen) if pen is not None else (None, None)
            ok = fe is not None and not np.isnan(E[e]["prev"]) and not np.isnan(E[e]["A"][d])
            out_e[e][d] = fe(e) if ok else np.nan
    return out_t, out_e


def pull_rows(E, years, anc_e, days=FIT_DAYS, extra=None):
    rows = []
    for e in years:
        for d in days:
            A, N = anc_e[e].get(d, np.nan), E[e]["N"][d]
            if np.isnan(A) or np.isnan(N):
                continue
            w = 1.0 if extra is None else extra(e, d)
            rows.append((e, d, (d / 150.0) * (A - N) * w, E[e]["result"] - N))
    return rows


def fit_k(rows, years):
    def fit(p, keep):
        r = [x for x in rows if x[0] in keep]
        return min(max(ridge_scalar(np.array([x[2] for x in r]), np.array([x[3] for x in r]), p), 0.0), 1.0) if r else 0.0

    def err(k, g):
        r = [x for x in rows if x[0] == g]
        return sum((x[3] - k * x[2]) ** 2 for x in r)
    pen = loeo_pen(years, fit, err)
    return fit(pen, years), pen


# ---------------------------------------------------------------- candidate 2: trend survival
def zigzag(L, thr=THR, dstart=DMAX):
    """Walk forward in time (days before the election falling). A turning point is confirmed on the day L has moved
    back thr from its latest extreme. Returns per-day (direction, start day of the current episode) and the episodes
    as (start_day, end_day or None if censored at day 0, direction). Uses only L at days >= the day."""
    state_dir = np.zeros(DMAX + 1); state_start = np.full(DMAX + 1, np.nan)
    eps = []
    dirn, ext, start_val, ep_start = 0, None, None, None
    for d in range(dstart, -1, -1):
        v = L[d]
        if not np.isnan(v):
            if start_val is None:
                start_val = v
            elif dirn == 0:
                if abs(v - start_val) >= thr:
                    dirn = 1 if v > start_val else -1
                    ext, ep_start = v, d
            else:
                if (dirn == 1 and v > ext) or (dirn == -1 and v < ext):
                    ext = v
                elif abs(v - ext) >= thr:
                    eps.append((ep_start, d, dirn))
                    dirn, ext, ep_start = -dirn, v, d
        state_dir[d] = dirn
        state_start[d] = ep_start if ep_start is not None else np.nan
    if dirn != 0:
        eps.append((ep_start, None, dirn))
    return state_dir, state_start, eps


def person_weeks(eps):
    """Discrete-time rows (age in weeks, event) from episodes on the confirmation clock."""
    rows = []
    for s, e, _ in eps:
        last = 0 if e is None else e
        n = int(np.ceil((s - last) / 7.0)) if s > last else 1
        for w in range(n):
            rows.append((w, int(e is not None and w == n - 1)))
    return rows


def drift_rows(L, eps):
    """Movement of L in the episode's direction over each week it was running, on the same clock as person_weeks
    (the final, partial week up to the confirmation day included)."""
    rows = []
    for s, e, dirn in eps:
        last = 0 if e is None else e
        n = int(np.ceil((s - last) / 7.0)) if s > last else 1
        for w in range(n):
            a, b = L[s - 7 * w], L[max(s - 7 * (w + 1), last)]
            if not (np.isnan(a) or np.isnan(b)):
                rows.append(dirn * (b - a))
    return rows


def logit_fit(w, y, pen, firth=False, iters=60):
    """Logistic hazard alpha + delta * age; ridge pen on delta only; optional Firth correction (no ridge)."""
    X = np.column_stack([np.ones_like(w, dtype=float), w.astype(float)])
    th = np.array([np.log((y.mean() + 1e-3) / (1 - y.mean() + 1e-3)), 0.0])
    P = np.diag([0.0, pen])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ th)))
        W = p * (1 - p)
        I = X.T @ (X * W[:, None]) + P
        if firth:
            H = (X * W[:, None]) @ np.linalg.solve(I, X.T)
            h = np.diag(H)
            U = X.T @ (y - p + h * (0.5 - p))
        else:
            U = X.T @ (y - p) - P @ th
        step = np.linalg.solve(I, U)
        th = th + step
        if np.abs(step).max() < 1e-9:
            break
    return th


def fit_hazard(pw_by_e, years):
    def fit(pen, keep):
        r = [x for e in keep for x in pw_by_e[e]]
        if not r:
            return np.array([0.0, 0.0])
        a = np.array(r)
        return logit_fit(a[:, 0], a[:, 1], pen)

    def err(th, g):
        r = pw_by_e[g]
        if not r:
            return 0.0
        a = np.array(r)
        p = 1 / (1 + np.exp(-(th[0] + th[1] * a[:, 0])))
        p = np.clip(p, 1e-9, 1 - 1e-9)
        return float(-(a[:, 1] * np.log(p) + (1 - a[:, 1]) * np.log(1 - p)).sum())
    pen = loeo_pen(years, fit, err, HAZ_PENS)
    return fit(pen, years), pen


def fit_drift(dr_by_e, years):
    def fit(pen, keep):
        x = np.array([v for e in keep for v in dr_by_e[e]])
        return float(x.sum() / (len(x) + pen)) if len(x) + pen > 0 else 0.0

    def err(dr, g):
        return float(sum((v - dr) ** 2 for v in dr_by_e[g]))
    pen = loeo_pen(years, fit, err)
    return fit(pen, years), pen


def remaining_weeks(th, age, cap):
    s, tot = 1.0, 0.0
    for j in range(cap):
        h = 1 / (1 + np.exp(-(th[0] + th[1] * (age + j))))
        s *= (1 - h)
        tot += s
    return tot


def km(pw):
    """Kaplan-Meier survival at weeks 1..8 from person-week rows."""
    a = np.array(pw) if pw else np.zeros((0, 2))
    out, s = [], 1.0
    for w in range(8):
        at = (a[:, 0] == w).sum() if len(a) else 0
        ev = ((a[:, 0] == w) & (a[:, 1] == 1)).sum() if len(a) else 0
        if at > 0:
            s *= 1 - ev / at
        out.append(s)
    return out


# ---------------------------------------------------------------- candidate 3: steadiness
def spread_raw(L, d, start=200):
    pts = [L[k] for k in range(start, d - 1, -7) if not np.isnan(L[k])]
    ch = np.diff(pts)
    return float(np.std(ch, ddof=1)) if len(ch) >= 3 else np.nan


# ---------------------------------------------------------------- the backtest
def prep(E):
    """Per election: episode states (candidate 2) and steadiness (candidate 3) from its own light average."""
    P = {}
    for y in CYCLES:
        sd_, ss_, eps = zigzag(E[y]["L"])
        P[y] = {"dir": sd_, "start": ss_, "eps": eps, "pw": person_weeks(eps), "dr": drift_rows(E[y]["L"], eps),
                "s": {d: spread_raw(E[y]["L"], d) for d in set(FIT_DAYS + SCORE_DAYS + REPORT_DAYS + RANGE_DAYS)}}
    return P


def zscore(P, years, y, d):
    v = [P[e]["s"][d] for e in years if not np.isnan(P[e]["s"][d])]
    x = P[y]["s"][d]
    if np.isnan(x) or len(v) < 3 or np.std(v) == 0:
        return 0.0
    return float((x - np.mean(v)) / np.std(v))


def backtest(E, P, which=("c1", "c2", "c3", "c4", "c5")):
    """Every scored election fitted on the elections before it. Returns per-election forecasts by day and fits."""
    out = {}
    allD = SCORE_DAYS + REPORT_DAYS
    for y in SCORED:
        earlier = [x for x in CYCLES if x < y]
        Ey = E[y]
        N = {d: Ey["N"][d] for d in allD}
        row = {"fc": {"baseline": dict(N)}, "fit": {}}
        # baseline range from earlier elections' errors
        a, b = range_fit([(d, (E[e]["N"][d] - E[e]["result"]) ** 2) for e in earlier for d in RANGE_DAYS
                          if not np.isnan(E[e]["N"][d])])
        row["fit"]["range"] = (a, b)
        base_var = {d: max(a + b * d, 1.0) for d in allD}
        row["var"] = {"baseline": dict(base_var)}
        need_anchor = "c1" in which or "c3" in which
        if need_anchor:
            anc_t, anc_e = anchors_for(E, earlier, y)
            rows = pull_rows(E, earlier, anc_e)
            k, kpen = fit_k(rows, earlier)
            row["fit"]["c1"] = {"k": k, "pen": kpen}
            if "c1" in which:
                row["fc"]["c1"] = {d: (N[d] + min(max(k * d / 150, 0), 1) * (anc_t[d] - N[d])
                                       if not np.isnan(anc_t[d]) else N[d]) for d in allD}
        if "c2" in which:
            th, hpen = fit_hazard({e: P[e]["pw"] for e in earlier}, earlier)
            dr, dpen = fit_drift({e: P[e]["dr"] for e in earlier}, earlier)
            row["fit"]["c2"] = {"alpha": float(th[0]), "delta": float(th[1]), "haz_pen": hpen, "drift": dr, "drift_pen": dpen}
            fc = {}
            for d in allD:
                dirn, st = P[y]["dir"][d], P[y]["start"][d]
                if dirn == 0 or np.isnan(st):
                    fc[d] = N[d]
                    continue
                age = int((st - d) // 7)
                fc[d] = N[d] + dr * dirn * remaining_weeks(th, age, int(d // 7))
            row["fc"]["c2"] = fc
            row["fc"]["c2_control"] = {d: Ey["L"][d] for d in allD}
        if "c3" in which:
            def scale(beta, years_z):
                return lambda e, d: np.exp(beta * zscore(P, years_z, e, d))
            # beta by leaving one election out; k refitted inside with candidate 1's penalty
            best = None
            for beta in BETAS:
                tot = 0.0
                for g in earlier:
                    keep = [x for x in earlier if x != g]
                    r = pull_rows(E, keep, anc_e, extra=scale(beta, earlier))
                    kk = min(max(ridge_scalar(np.array([x[2] for x in r]), np.array([x[3] for x in r]), kpen), 0), 1) if r else 0
                    tot += sum((x[3] - kk * x[2]) ** 2 for x in pull_rows(E, [g], anc_e, extra=scale(beta, earlier)))
                if best is None or tot < best[0] - 1e-12:
                    best = (tot, beta)
            beta = best[1]
            r = pull_rows(E, earlier, anc_e, extra=scale(beta, earlier))
            k3 = min(max(ridge_scalar(np.array([x[2] for x in r]), np.array([x[3] for x in r]), kpen), 0), 1)
            row["fc"]["c3a"] = {}
            for d in allD:
                lam = min(max(k3 * d / 150 * np.exp(beta * zscore(P, earlier, y, d)), 0), 1)
                row["fc"]["c3a"][d] = N[d] + lam * (anc_t[d] - N[d]) if not np.isnan(anc_t[d]) else N[d]
            # range: gamma by maximum likelihood on earlier elections
            rr = [(d, (E[e]["N"][d] - E[e]["result"]) ** 2, zscore(P, earlier, e, d)) for e in earlier for d in RANGE_DAYS
                  if not np.isnan(E[e]["N"][d])]
            Dd = np.array([x[0] for x in rr]); Ss = np.array([x[1] for x in rr]); Zz = np.array([x[2] for x in rr])
            base = np.maximum(a + b * Dd, 1.0)
            ll = [(-0.5 * (np.log(base * np.exp(gm * Zz)) + Ss / (base * np.exp(gm * Zz)))).sum() for gm in GAMMAS]
            gamma = GAMMAS[int(np.argmax(ll))]
            row["fit"]["c3"] = {"beta": beta, "k": k3, "gamma": gamma}
            row["var"]["c3b"] = {d: base_var[d] * np.exp(gamma * zscore(P, earlier, y, d)) for d in allD}
        if "c4" in which:
            rr = [(E[e]["N"][d], E[e]["u"][d], E[e]["result"]) for e in earlier for d in FIT_DAYS
                  if not np.isnan(E[e]["N"][d]) and not np.isnan(E[e]["u"][d])]
            Nn = np.array([x[0] for x in rr]); Uu = np.array([x[1] for x in rr]); Rr = np.array([x[2] for x in rr])
            sse = [((Nn * (1 - (1 - al) * Uu / 100) - Rr) ** 2).sum() for al in ALPHAS]
            alpha = float(ALPHAS[int(np.argmin(sse))])
            row["fc"]["c4a"] = {d: (N[d] * (1 - (1 - alpha) * Ey["u"][d] / 100) if not np.isnan(Ey["u"][d]) else N[d])
                                for d in allD}
            rr = [(d, (E[e]["N"][d] - E[e]["result"]) ** 2, E[e]["u"][d]) for e in earlier for d in RANGE_DAYS
                  if not np.isnan(E[e]["N"][d]) and not np.isnan(E[e]["u"][d])]
            Dd = np.array([x[0] for x in rr]); Ss = np.array([x[1] for x in rr]); Uu = np.array([x[2] for x in rr])
            base = np.maximum(a + b * Dd, 1.0)
            ll = [(-0.5 * (np.log(base + kp * Uu) + Ss / (base + kp * Uu))).sum() for kp in KAPPAS]
            kappa = float(KAPPAS[int(np.argmax(ll))])
            row["fit"]["c4"] = {"alpha": alpha, "kappa": kappa}
            row["var"]["c4b"] = {d: base_var[d] + kappa * (Ey["u"][d] if not np.isnan(Ey["u"][d]) else 0.0) for d in allD}
        if "c5" in which:
            def parts(e, d):
                if d + 30 > DMAX:
                    return None
                dn = E[e]["N"][d] - E[e]["N"][d + 30]
                da = E[e]["party"] * (E[e]["A"][d] - E[e]["A"][d + 30])
                return None if (np.isnan(dn) or np.isnan(da)) else (dn, da)
            pr = [(e, d, *parts(e, d)) for e in earlier for d in FIT_DAYS if parts(e, d) is not None]
            dn = np.array([x[2] for x in pr]); da = np.array([x[3] for x in pr])
            bapp = float((dn * da).sum() / (da * da).sum()) if (da * da).sum() > 0 else 0.0

            def rho_fit(rows_, years_):
                def fit(p, keep):
                    r = [x for x in rows_ if x[0] in keep]
                    return min(max(ridge_scalar(np.array([x[2] for x in r]), np.array([x[3] for x in r]), p), 0.0), 1.0) if r else 0.0

                def err(k, g):
                    return sum((x[3] - k * x[2]) ** 2 for x in rows_ if x[0] == g)
                pen = loeo_pen(years_, fit, err)
                return fit(pen, years_)
            rows5 = [(e, d, -(x_dn - bapp * x_da), E[e]["result"] - E[e]["N"][d]) for e, d, x_dn, x_da in pr]
            rho = rho_fit(rows5, earlier)
            rowsv = [(e, d, -x_dn, E[e]["result"] - E[e]["N"][d]) for e, d, x_dn, x_da in pr]
            rho_v = rho_fit(rowsv, earlier)
            row["fit"]["c5"] = {"beta_approval": bapp, "rho": rho, "rho_both": rho_v}
            fc, fv = {}, {}
            for d in allD:
                pp = parts(y, d)
                fc[d] = N[d] - rho * (pp[0] - bapp * pp[1]) if pp is not None else N[d]
                fv[d] = N[d] + rho_v * (-pp[0]) if pp is not None else N[d]
            row["fc"]["c5"], row["fc"]["c5_both"] = fc, fv
        row["result"] = Ey["result"]
        out[y] = row
    return out


def scores(bt):
    """Per election: squared-error score (150/100/60), report days, log scores."""
    S = {}
    for y, r in bt.items():
        res = r["result"]
        for k, fc in r["fc"].items():
            assert all(np.isfinite(fc[d]) for d in SCORE_DAYS + REPORT_DAYS), (y, k)
        for k, v in r["var"].items():
            assert all(np.isfinite(v[d]) for d in SCORE_DAYS + REPORT_DAYS), (y, k)
        S[y] = {}
        for k, fc in r["fc"].items():
            sq = [(fc[d] - res) ** 2 for d in SCORE_DAYS if not np.isnan(fc[d])]
            S[y][k] = {"sq": float(np.mean(sq)) if sq else np.nan,
                       "sq_report": {d: float((fc[d] - res) ** 2) for d in REPORT_DAYS},
                       "log": float(np.mean([logscore(fc[d], res, r["var"]["baseline"][d]) for d in SCORE_DAYS])),
                       "by_day": {d: float(fc[d] - res) for d in SCORE_DAYS + REPORT_DAYS}}
        for k in ("c3b", "c4b"):
            if k in r["var"]:
                v = r["var"][k]
                S[y][k] = {"log": float(np.mean([logscore(r["fc"]["baseline"][d], res, v[d]) for d in SCORE_DAYS])),
                           "log_report": float(np.mean([logscore(r["fc"]["baseline"][d], res, v[d]) for d in REPORT_DAYS]))}
        S[y]["baseline"]["log_report"] = float(np.mean([logscore(r["fc"]["baseline"][d], res, r["var"]["baseline"][d])
                                                        for d in REPORT_DAYS]))
    return S


def summary(S, keys):
    ys = list(S)
    g = {}
    for k in keys:
        if k in ("c3b", "c4b"):
            d = np.array([S[y][k]["log"] - S[y]["baseline"]["log"] for y in ys])
            nw = np.mean([S[y][k]["log_report"] for y in ys]) >= np.mean([S[y]["baseline"]["log_report"] for y in ys]) - 1e-12
        else:
            d = np.array([S[y]["baseline"]["sq"] - S[y][k]["sq"] for y in ys])
            nw = all(np.mean([S[y][k]["sq_report"][dd] for y in ys])
                     <= np.mean([S[y]["baseline"]["sq_report"][dd] for y in ys]) + 1e-12 for dd in REPORT_DAYS)
        g[k] = {"gain": float(d.mean()), "better": int((d > 1e-12).sum()), "not_worse_30_7": bool(nw)}
    return g


CAND_KEYS = {"c1": ["c1"], "c2": ["c2"], "c3": ["c3a", "c3b"], "c4": ["c4a", "c4b"], "c5": ["c5"]}


def shuffled(E, P, cand, rng):
    """Hand the candidate's feature between elections as a whole series by days out."""
    E2 = {y: dict(v) for y, v in E.items()}
    P2 = {y: dict(v) for y, v in P.items()}
    pool = [y for y in CYCLES if cand != "c1" or y >= 1956]
    perm = dict(zip(pool, [pool[i] for i in rng.permutation(len(pool))]))
    for y, src in perm.items():
        if cand == "c1":                                   # approval series and previous margin, incumbent terms
            E2[y]["A"] = E[src]["A"]
            E2[y]["prev"] = E[src]["party"] * E[src]["prev"] * E[y]["party"]
        elif cand == "c2":
            for k in ("dir", "start", "eps", "pw", "dr"):
                P2[y][k] = P[src][k]
        elif cand == "c3":
            P2[y]["s"] = P[src]["s"]
        elif cand == "c4":
            E2[y]["u"] = E[src]["u"]
        elif cand == "c5":
            E2[y]["A"] = E[src]["A"]
    return E2, P2


# ---------------------------------------------------------------- diagnostics
def null_survival(E, P, n=200, seed=5):
    """Episodes from each election's light-average daily changes in shuffled order: KM at weeks 1-8."""
    rng = np.random.default_rng(seed)
    real = km([x for y in CYCLES for x in P[y]["pw"]])
    sims = []
    for _ in range(n):
        pw = []
        for y in CYCLES:
            t, m = E[y]["t"], E[y]["m"]
            o = np.argsort(-t)                              # readings in time order
            mm = m[o]
            m2 = np.empty_like(mm)
            m2[0] = mm[0]
            m2[1:] = mm[0] + np.cumsum(rng.permutation(np.diff(mm)))
            back = np.empty_like(m2); back[o] = m2
            L2 = np.array([wavg(t, back, k, HL_LIGHT) for k in range(DMAX + 1)])
            pw += person_weeks(zigzag(L2)[2])
        sims.append(km(pw))
    sims = np.array(sims)
    lo, hi = np.quantile(sims, 0.025, axis=0), np.quantile(sims, 0.975, axis=0)
    inside = bool(all(lo[i] <= real[i] <= hi[i] for i in range(8)))
    return {"real_km": real, "null_lo": lo.tolist(), "null_hi": hi.tolist(), "real_inside_null": inside}


def pull_before_after(E):
    """Full-sample diagnostic: k fitted on days before the second convention ends against days after."""
    years = [y for y in CYCLES if y >= 1956]
    out = {}
    for name, cond in (("before", lambda e, d: d > E[e]["e2"]), ("after", lambda e, d: d <= E[e]["e2"])):
        rows = []
        for e in years:
            others = [x for x in years if x != e]
            for d in FIT_DAYS:
                if not cond(e, d):
                    continue
                f, _ = anchor_model(E, others, d)
                if f is None or np.isnan(E[e]["A"][d]) or np.isnan(E[e]["N"][d]):
                    continue
                rows.append((e, d, (d / 150) * (f(e) - E[e]["N"][d]), E[e]["result"] - E[e]["N"][d]))
        k, pen = fit_k(rows, years)
        out[name] = {"k": k, "pen": pen, "rows": len(rows)}
    out["flag"] = bool(out["before"]["k"] > 0 and out["after"]["k"] < 0.5 * out["before"]["k"])
    return out


def evenness_diagnostic(E):
    """Candidate 6 (diagnostic): state polls 2004-2020. A 30-day national shift of 1 point or more is 'even' when the
    standard deviation of the state shifts is below the median, and 'held' when the next 30 days do not take back more
    than half of it."""
    import pres_nowcast as PN
    q = PN.load()
    rows = []
    for y in (2004, 2008, 2012, 2016, 2020):
        el = q[q.cycle == y].election.iloc[0]
        for d in range(150, 39, -10):
            if d + 30 > DMAX:
                continue
            nat = E[y]["N"][d] - E[y]["N"][d + 30]
            nxt = E[y]["N"][d - 30] - E[y]["N"][d] if d - 30 >= 0 else np.nan
            if np.isnan(nat) or np.isnan(nxt) or abs(nat) < 1:
                continue
            t1, t0 = el - pd.Timedelta(days=d), el - pd.Timedelta(days=d + 30)
            sh = []
            for g, x in q[(q.cycle == y) & (q.geo != "US")].groupby("geo"):
                if ((x.end < t1) & (x.end >= t1 - pd.Timedelta(days=30))).any() and \
                        ((x.end < t0) & (x.end >= t0 - pd.Timedelta(days=30))).any():
                    sh.append(PN.average(x, t1, PN.BASE) - PN.average(x, t0, PN.BASE))
            if len(sh) < 5:
                continue
            rows.append({"cycle": y, "d": d, "nat": nat, "sd": float(np.std(sh)), "held": bool(np.sign(nat) * nxt >= -0.5 * abs(nat))})
    r = pd.DataFrame(rows)
    if r.empty:
        return {"cases": 0}
    med = r.sd.median()
    even, conc = r[r.sd < med], r[r.sd >= med]
    diff = float(even.held.mean() - conc.held.mean()) if len(even) and len(conc) else np.nan
    return {"cases": int(len(r)), "by_cycle": r.groupby("cycle").size().to_dict(), "hold_even": float(even.held.mean()),
            "hold_concentrated": float(conc.held.mean()), "n_even": int(len(even)), "n_conc": int(len(conc)),
            "difference_pts": round(100 * diff, 1), "flag": bool(abs(diff) * 100 >= 15)}


# ---------------------------------------------------------------- checks
def checks():
    E = load()
    print("2024 absent: PASS")
    import pres_conventions as PC
    EC = PC.load()
    same = max(abs(E[y]["N"][d] - PC.forecast(EC[y], d, {}, EC[y]["conv"])) for y in SCORED for d in SCORE_DAYS + REPORT_DAYS)
    print(f"nowcast equals stage 2's: {'PASS' if same < 1e-9 else 'FAIL'} ({same:.1e})")
    ok = same < 1e-9
    # behaviour
    x = np.linspace(-3, 3, 50); ok_k = abs(ridge_scalar(x, 0.4 * x, 0.0) - 0.4) < 1e-12
    L = np.full(DMAX + 1, np.nan)
    path = np.concatenate([np.linspace(0, 3, 41), np.linspace(3, 0, 41)[1:], np.linspace(0, 2, 30)[1:]])
    L[200:200 - len(path):-1] = path
    sd_, ss_, eps = zigzag(L, 1.5)
    # rises 0 -> 3 (days 200..160), falls 3 -> 0 (159..120): up confirmed when L reaches 1.5 (day 180); the peak (day
    # 160) is confirmed once L has fallen to 1.5 (day 140)
    ok_z = len(eps) >= 2 and eps[0][2] == 1 and eps[0][0] == 180 and eps[0][1] == 140 and sd_[150] == 1 and sd_[140] == -1
    rng = np.random.default_rng(3)
    pw = []
    for _ in range(400):
        n = rng.geometric(0.3)
        pw += [(w, int(w == n - 1)) for w in range(n)]
    a = np.array(pw); th = logit_fit(a[:, 0], a[:, 1], 1e6)
    ok_h = abs(1 / (1 + np.exp(-th[0])) - 0.3) < 0.03 and abs(th[1]) < 1e-3
    dr_ = drift_rows(L, eps)
    # episode 1 runs from day 180 (L 1.5) to 140 (L 1.5): net 0 in its direction over its weeks; episode 2 (down) from
    # day 140 (1.5) to 98 (1.5): also net 0; the forecast adjustment's sign follows the drift's
    ok_dr = abs(sum(dr_[:6])) < 1e-9 and remaining_weeks(np.array([-1.0, 0.0]), 0, 3) > 0
    ok_h = ok_h and ok_dr
    Ey = dict(E[2000]); Ey["u"] = np.zeros(DMAX + 1)
    ok_u = abs(Ey["N"][60] * (1 - (1 - 0.3) * Ey["u"][60] / 100) - Ey["N"][60]) < 1e-12
    print(f"behaviour: pull recovered {'PASS' if ok_k else 'FAIL'}; turning points confirmed on the right days and "
          f"not before {'PASS' if ok_z else 'FAIL'} {eps[:2]}; geometric durations give back their rate "
          f"{'PASS' if ok_h else 'FAIL'} ({1 / (1 + np.exp(-th[0])):.3f}); u = 0 gives the baseline {'PASS' if ok_u else 'FAIL'}")
    ok &= ok_k and ok_z and ok_h and ok_u
    # leak: readings within LAG days of the date or after it, and approval after it, moved
    P = prep(E)
    base = backtest(E, P)
    bad = 0
    for y in (1988, 2008, 2016):
        for d in (100, 30):
            E2 = {k: dict(v) for k, v in E.items()}
            m = E[y]["m"].copy(); m[E[y]["t"] < d + LAG] += 50
            E2[y]["m"] = m
            E2[y]["N"] = np.array([wavg(E[y]["t"], m, k, HL) if k >= d else E[y]["N"][k] + 50 for k in range(DMAX + 1)])
            E2[y]["L"] = np.array([wavg(E[y]["t"], m, k, HL_LIGHT) if k >= d else E[y]["L"][k] + 50 for k in range(DMAX + 1)])
            A = E[y]["A"].copy(); A[:d] += 20; E2[y]["A"] = A
            u = E[y]["u"].copy(); u[:d] += 20; E2[y]["u"] = u
            P2 = dict(P); P2[y] = prep({y: E2[y], **{k: E2[k] for k in CYCLES if k != y}})[y]
            r2 = backtest(E2, P2)
            for k, fc in base[y]["fc"].items():
                bad += int(abs(r2[y]["fc"][k][d] - fc[d]) > 1e-9)
    print(f"leak test: {'PASS' if not bad else f'FAIL {bad}'}")
    ok &= not bad
    # as-of: own result and every later election changed
    bad2 = 0
    rng2 = np.random.default_rng(9)
    for y in (1984, 2000, 2012):
        E2 = {k: dict(v) for k, v in E.items()}
        E2[y]["result"] += 20
        for later in CYCLES:
            if later > y:
                m = E[later]["m"] * 1.7 + rng2.normal(0, 6, len(E[later]["m"]))
                E2[later]["m"] = m
                E2[later]["N"] = np.array([wavg(E[later]["t"], m, k, HL) for k in range(DMAX + 1)])
                E2[later]["L"] = np.array([wavg(E[later]["t"], m, k, HL_LIGHT) for k in range(DMAX + 1)])
                E2[later]["u"] = E[later]["u"] * 2 + rng2.normal(0, 3, DMAX + 1)
                E2[later]["A"] = E[later]["A"] + rng2.normal(0, 8, DMAX + 1)
                E2[later]["result"] += rng2.normal(0, 15)
        P2 = prep(E2)
        r2 = backtest(E2, P2)
        same_fit = json.dumps(r2[y]["fit"], default=float) == json.dumps(base[y]["fit"], default=float)
        same_fc = all(abs(r2[y]["fc"][k][d] - base[y]["fc"][k][d]) < 1e-9 for k in base[y]["fc"] for d in SCORE_DAYS)
        bad2 += int(not (same_fit and same_fc))
    print(f"as-of test: {'PASS' if not bad2 else f'FAIL {bad2}'}")
    ok &= not bad2
    if not ok:
        raise SystemExit("a check failed")


def run():
    E = load()
    P = prep(E)
    bt = backtest(E, P)
    S = scores(bt)
    keys = ["c1", "c2", "c3a", "c3b", "c4a", "c4b", "c5"]
    g = summary(S, keys)
    print(json.dumps(g, indent=1), flush=True)
    (OUT / "pres_reversion_real.json").write_text(json.dumps({"summary": g, "scores": S, "fits": {y: bt[y]["fit"] for y in bt}},
                                                             indent=1, default=float))
    null = {k: [] for k in keys}
    for cand, ks in CAND_KEYS.items():
        rng = np.random.default_rng({"c1": 11, "c2": 12, "c3": 13, "c4": 14, "c5": 15}[cand])
        for i in range(SHUFFLES):
            E2, P2 = shuffled(E, P, cand, rng)
            gs = summary(scores(backtest(E2, P2, which=(cand,) if cand != "c3" else ("c3",))), ks)
            for k in ks:
                null[k].append(gs[k]["gain"])
        print(f"  shuffles done: {cand}", flush=True)
    for k in keys:
        q = float(np.quantile(null[k], 0.95))
        g[k].update({"shuffle_95th": q, "share_of_shuffles_beaten": float(np.mean(np.array(null[k]) < g[k]["gain"]))})
        g[k]["passes"] = bool(g[k]["gain"] > 0 and g[k]["gain"] > q and g[k]["better"] >= 8 and g[k]["not_worse_30_7"])
    ctrl = summary(S, ["c2_control", "c5_both"])
    diag = {
        "c2_control_14day_no_trend": ctrl["c2_control"],
        "c2_flag_control_as_good": bool(ctrl["c2_control"]["gain"] >= g["c2"]["gain"]),
        "c2_null_survival": null_survival(E, P),
        "c3_flag_c1_as_good": bool(g["c1"]["gain"] >= g["c3a"]["gain"]),
        "c1_before_after_conventions": pull_before_after(E),
        "c5_variant_both_revert": ctrl["c5_both"],
        "c6_evenness": evenness_diagnostic(E),
        "episodes_by_threshold": {thr: {y: len(zigzag(E[y]["L"], thr)[2]) for y in CYCLES} for thr in (1.0, 1.5, 2.0)},
    }
    out = {"summary": g, "scores": S, "fits": {y: bt[y]["fit"] for y in bt}, "shuffle_gains": null, "diagnostics": diag}
    (OUT / "pres_reversion.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(g, indent=1))
    print(json.dumps(diag, indent=1, default=float)[:4000])


if __name__ == "__main__":
    {"checks": checks, "run": run}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
