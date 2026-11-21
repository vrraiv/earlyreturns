"""EC-3: presidential fundamentals (ELECTORAL_COLLEGE.md, section 12).

Outcome: the incumbent party's national two-party margin, 1952 to 2020 (2024 refused). Inputs as of 150, 100, 60, 30
and 7 days before each election, from figures published by then:
  approval       Gallup, mean of readings ending in the 30 days before the date, else the latest one
  economic index equal-weight mean of six signed measures, each standardized against its own monthly history from
                 1948 to the date: real income per head growth (+), real GDP growth over two quarters (+), the rise
                 in unemployment (-), inflation (-), real gasoline price growth (-), the S&P's 12-month change (+)
  term-limited   1 when the sitting president has won two elections and cannot run (1960, 1988, 2000, 2008, 2016)
Primary model: margin = a + b1 (approval - 50) + b2 index + b3 term-limited; ridge on b2 and b3 (toward approval
alone), penalty by leaving one election out within the fit.
Test 1 (reported): leave-one-out errors. Test 2 (decides): stage 3's national forecast blended with the fundamentals
by precision, 1980 to 2020, each fitted on earlier elections; rule for stages 2 to 4.

Run:  python src/model/pres_fundamentals.py checks
      python src/model/pres_fundamentals.py test1
      python src/model/pres_fundamentals.py test2
"""
import itertools
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
FRED = ROOT / "data" / "raw" / "fred" / "2026-11-03"
YEARS = tuple(range(1952, 2021, 4))
SCORED = tuple(range(1980, 2021, 4))
DAYS = (150, 100, 60, 30, 7)
SCORE_DAYS = (150, 100, 60)
REPORT_DAYS = (30, 7)
PENS = (0.0, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 1e6)
PARTY = {1952: "D", 1956: "R", 1960: "R", 1964: "D", 1968: "D", 1972: "R", 1976: "R", 1980: "D", 1984: "R",
         1988: "R", 1992: "R", 1996: "D", 2000: "D", 2004: "R", 2008: "R", 2012: "D", 2016: "D", 2020: "R"}
TERM_LIMITED = {1960, 1988, 2000, 2008, 2016}
NO_SITTING = {1952, 1960, 1968, 1988, 2000, 2008, 2016}
MEASURES = ("rdi", "gdp", "unemp", "infl", "gas", "sp")
SIGN = {"rdi": 1, "gdp": 1, "unemp": -1, "infl": -1, "gas": -1, "sp": 1}
LAG = {"rdi": 35, "infl": 35, "gas": 35, "unemp": 10, "sp": 1}


# ---------------------------------------------------------------- data
def _monthly(sid):
    x = pd.read_csv(FRED / f"{sid}.csv")
    x.columns = ["date", "v"]
    x["date"] = pd.to_datetime(x.date)
    x["v"] = pd.to_numeric(x.v, errors="coerce")
    return x.dropna().set_index("date").v


def monthly_changes():
    """Each measure's monthly series of 12-month changes (GDP: quarterly mean of two quarters), indexed by period."""
    rdi = _monthly("A229RX0")
    cpi = _monthly("CPIAUCNS")
    gas = _monthly("CUUR0000SETB01") / cpi
    un = _monthly("UNRATE")
    gdp = _monthly("A191RL1Q225SBEA")
    sp = pd.read_csv(INTERIM / "sp500_monthly_change.csv", parse_dates=["month"]).set_index("month").change_12m
    out = {
        "rdi": 100 * (rdi / rdi.shift(12) - 1),
        "infl": 100 * (cpi / cpi.shift(12) - 1),
        "gas": 100 * (gas / gas.shift(12) - 1),
        "unemp": un - un.shift(12),
        "gdp": (gdp + gdp.shift(1)) / 2,
        "sp": sp,
    }
    return {k: v.dropna()[v.dropna().index >= "1948-01-01"] for k, v in out.items()}


def published(series, name, date):
    """The part of a series published by `date`: a month (or quarter) counts from LAG days after it ends."""
    idx = series.index
    if name == "gdp":
        end = idx + pd.offsets.QuarterEnd(0)
        ok = end + pd.Timedelta(days=35) <= date
    else:
        end = idx + pd.offsets.MonthEnd(0)
        ok = end + pd.Timedelta(days=LAG[name]) <= date
    return series[ok]


def econ_inputs(M, date):
    """Signed standardized value of each measure on `date` (NaN where not available) and the equal-weight index."""
    z = {}
    for k in MEASURES:
        s = published(M[k], k, date)
        if len(s) < 3 or (s.index.max() - s.index.min()).days < 730:      # at least two years of history
            z[k] = np.nan
            continue
        z[k] = SIGN[k] * float((s.iloc[-1] - s.mean()) / s.std())
    vals = [v for v in z.values() if not np.isnan(v)]
    z["index"] = float(np.mean(vals)) if vals else np.nan
    return z


def pca_index(M, date):
    """Reported only: first principal component of the six monthly standardized series (months with all six, up to
    the date), signed so income growth loads positively; its score in the latest such month."""
    cols = []
    for k in MEASURES:
        s = published(M[k], k, date)
        if k == "gdp":
            s = s.resample("MS").ffill()
        cols.append(SIGN[k] * s.rename(k))
    X = pd.concat(cols, axis=1, sort=True).dropna()
    if len(X) < 36:
        return np.nan
    Z = (X - X.mean()) / X.std()
    w, V = np.linalg.eigh(np.cov(Z.values.T))
    v = V[:, -1]
    if v[0] < 0:
        v = -v
    return float(Z.values[-1] @ v)


def approval_on(g, date, age=False):
    w = g[(g.end < date) & (g.end >= date - pd.Timedelta(days=30))]
    if len(w):
        return (float(w.Approving.mean()), int((date - w.end.max()).days)) if age else float(w.Approving.mean())
    w = g[g.end < date]
    return (float(w.Approving.iloc[-1]), int((date - w.end.iloc[-1]).days)) if age else float(w.Approving.iloc[-1])


def load():
    h = pd.read_csv(INTERIM / "state_presidential_history.csv")
    nat = h.groupby("year").national_margin_2p.first()
    d = pd.read_csv(INTERIM / "president_national_poll_days.csv", parse_dates=["election_date"])
    assert 2024 not in set(d.cycle)
    eldate = d.groupby("cycle").election_date.first()
    res = d.groupby("cycle").result_margin_2p.first()
    assert max(abs(float(nat[y]) - float(res[y])) for y in YEARS) < 1e-6, "the two result sources disagree"
    g = pd.read_csv(INTERIM / "gallup_approval.csv", parse_dates=["end"]).sort_values("end")
    M = monthly_changes()
    rows = []
    for y in YEARS:
        sg = 1.0 if PARTY[y] == "D" else -1.0
        for dd in DAYS:
            date = eldate[y] - pd.Timedelta(days=dd)
            z = econ_inputs(M, date)
            ap, age = approval_on(g, date, age=True)
            rows.append({"year": y, "d": dd, "sign": sg, "y": sg * float(nat[y]), "approval": ap - 50, "approval_age": age,
                         "term": float(y in TERM_LIMITED), "nosit": float(y in NO_SITTING), "pca": pca_index(M, date),
                         **z})
    X = pd.DataFrame(rows)
    assert 2024 not in set(X.year)
    return X


# ---------------------------------------------------------------- estimation
def ridge(Xm, y, pen, penalized):
    """Least squares with an intercept and ridge `pen` on the columns flagged in `penalized` (standardized first)."""
    mu, sd = Xm.mean(0), Xm.std(0)
    sd[sd == 0] = 1
    Z = (Xm - mu) / sd
    A = np.column_stack([np.ones(len(y)), Z])
    P = np.diag([0.0] + [pen if p else 0.0 for p in penalized])
    beta = np.linalg.solve(A.T @ A + P + 1e-9 * np.eye(A.shape[1]), A.T @ y)
    return mu, sd, beta


def predict(fit, xrow):
    mu, sd, beta = fit
    return float(beta[0] + ((xrow - mu) / sd) @ beta[1:])


PRIMARY = ["approval", "index", "term"]
PEN_FLAGS = [False, True, True]


def choose_pen(D, cols, flags, pens=PENS):
    """Penalty by leaving one election out within D."""
    best = None
    for pen in pens:
        err = 0.0
        for i in range(len(D)):
            tr = np.delete(np.arange(len(D)), i)
            f = ridge(D[cols].values[tr], D.y.values[tr], pen, flags)
            err += (predict(f, D[cols].values[i]) - D.y.values[i]) ** 2
        if best is None or err < best[0] - 1e-12:
            best = (err, pen)
    return best[1]


def fit_primary(D, cols=PRIMARY, flags=PEN_FLAGS, pen=None):
    pen = choose_pen(D, cols, flags) if pen is None else pen
    return ridge(D[cols].values, D.y.values, pen, flags), pen


def loo_errors(D, cols, flags=None, nested=True):
    """Leave-one-out errors; for a penalized model the penalty is chosen again inside each fit (nested)."""
    errs = []
    for i in range(len(D)):
        tr = D.drop(D.index[i])
        if flags is None:
            f = ridge(tr[cols].values, tr.y.values, 0.0, [False] * len(cols)) if cols else None
            p = predict(f, D[cols].values[i]) if cols else float(tr.y.mean())
        else:
            f, _ = fit_primary(tr, cols, flags, pen=None if nested else 0.0)
            p = predict(f, D[cols].values[i])
        errs.append(p - D.y.values[i])
    return np.array(errs)


# ---------------------------------------------------------------- test 1
def test1():
    X = load()
    out = {"by_day": {}}
    pool = ["approval", "term", "index", "pca"] + list(MEASURES)
    for dd in DAYS:
        D = X[X.d == dd].reset_index(drop=True)
        r = {}
        r["constant"] = float(np.sqrt(np.mean(loo_errors(D, []) ** 2)))
        r["approval_alone"] = float(np.sqrt(np.mean(loo_errors(D, ["approval"]) ** 2)))
        r["primary"] = float(np.sqrt(np.mean(loo_errors(D, PRIMARY, PEN_FLAGS) ** 2)))
        r["primary_no_sitting"] = float(np.sqrt(np.mean(loo_errors(D, ["approval", "index", "nosit"], PEN_FLAGS) ** 2)))
        f, pen = fit_primary(D)
        mu, sd, beta = f
        r["primary_fit"] = {"pen": pen, "intercept": float(beta[0]),
                            "per_unit": {c: float(b / s) for c, b, s in zip(PRIMARY, beta[1:], sd)}}
        tl = []
        for i in range(len(D)):
            fi, _ = fit_primary(D.drop(D.index[i]))
            tl.append(fi[2][3] / fi[1][2])
        un = ridge(D[PRIMARY].values, D.y.values, 0.0, PEN_FLAGS)
        r["term_limited_effect_points"] = {"shrunk": float(beta[3] / sd[2]), "unshrunk": float(un[2][3] / un[1][2]),
                                           "penalty": pen, "loo_min": float(min(tl)), "loo_max": float(max(tl))}
        C = D[D.year >= 1964].reset_index(drop=True)                 # every measure, and the PCA, exist from 1964
        subsets = {}
        for k in (1, 2, 3):
            for cols in itertools.combinations(pool, k):
                if C[list(cols)].isna().any().any():
                    continue
                subsets["+".join(cols)] = float(np.sqrt(np.mean(loo_errors(C, list(cols)) ** 2)))
        r["primary_1964_2020"] = float(np.sqrt(np.mean(loo_errors(C, PRIMARY, PEN_FLAGS) ** 2)))
        r["constant_1964_2020"] = float(np.sqrt(np.mean(loo_errors(C, []) ** 2)))
        r["approval_1964_2020"] = float(np.sqrt(np.mean(loo_errors(C, ["approval"]) ** 2)))
        r["subsets_1964_2020"] = dict(sorted(subsets.items(), key=lambda kv: kv[1]))
        r["subsets_count"] = len(subsets)
        r["subsets_rmse_range"] = [min(subsets.values()), max(subsets.values())]
        r["primary_rank_among_subsets"] = int(sum(v < r["primary_1964_2020"] for v in subsets.values()) + 1)
        r["approval_age_days_max"] = int(D.approval_age.max())
        out["by_day"][dd] = r
    out["inputs"] = X.round(3).to_dict("records")
    out["real_time_check"] = real_time_check()
    (OUT / "pres_fundamentals_test1.json").write_text(json.dumps(out, indent=1, default=float))
    for dd, r in out["by_day"].items():
        print(dd, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()
                   if k in ("constant", "approval_alone", "primary", "primary_no_sitting", "primary_1960_2020",
                            "constant_1960_2020", "approval_1960_2020")}, "term", r["term_limited_effect_points"],
              "fit", r["primary_fit"])


def real_time_check():
    """ALFRED as-published vintages against today's vintage, where they exist: real disposable income (DSPIC96, total,
    from 1980) and real GDP (GDPC1, from 1992). Growth as the index uses it, at each date of 1980 to 2020."""
    from common import fetch
    d = pd.read_csv(INTERIM / "president_national_poll_days.csv", parse_dates=["election_date"])
    eldate = d.groupby("cycle").election_date.first()

    def series(sid, vintage=None):
        name = f"{sid}.csv" if vintage is None else f"{sid}_v{vintage}.csv"
        params = {"id": sid} if vintage is None else {"id": sid, "vintage_date": vintage}
        url = ("https://fred.stlouisfed.org/graph/fredgraph.csv" if vintage is None
               else "https://alfred.stlouisfed.org/graph/alfredgraph.csv")
        x = pd.read_csv(fetch("alfred_ec3", name, url, params=params))
        x.columns = ["date", "v"]
        x["date"] = pd.to_datetime(x.date)
        x["v"] = pd.to_numeric(x.v, errors="coerce")
        return x.dropna().set_index("date").v

    cur = {"DSPIC96": series("DSPIC96"), "GDPC1": series("GDPC1")}
    rows = []
    for y in SCORED:
        for dd in DAYS:
            date = eldate[y] - pd.Timedelta(days=dd)
            v = date.strftime("%Y-%m-%d")
            for sid, first in (("DSPIC96", 1980), ("GDPC1", 1992)):
                if y < first:
                    continue
                try:
                    old = series(sid, v)
                except Exception:   # noqa: BLE001
                    continue
                for lab, s in (("as_published", old), ("today", cur[sid])):
                    if sid == "DSPIC96":
                        s = s[s.index + pd.offsets.MonthEnd(0) + pd.Timedelta(days=35) <= date]
                        g = 100 * (s.iloc[-1] / s.iloc[-13] - 1)
                    else:
                        s = s[s.index + pd.offsets.QuarterEnd(0) + pd.Timedelta(days=35) <= date]
                        g = 100 * ((s.iloc[-1] / s.iloc[-3]) ** 2 - 1)
                    rows.append({"year": y, "d": dd, "series": sid, "kind": lab, "growth": float(g)})
    R = pd.DataFrame(rows)
    if R.empty:
        return {"note": "no vintages fetched"}
    P = R.pivot_table(index=["year", "d", "series"], columns="kind", values="growth").dropna()
    P["diff"] = P.today - P.as_published
    return {"cases": int(len(P)),
            "mean_abs_revision_points": {s: float(P.xs(s, level="series")["diff"].abs().mean()) for s in P.index.get_level_values("series").unique()},
            "max_abs_revision_points": {s: float(P.xs(s, level="series")["diff"].abs().max()) for s in P.index.get_level_values("series").unique()}}


# ---------------------------------------------------------------- test 2
def national_forecasts():
    """Stage 3's national forecast (two-party nowcast x (1 - u/100)) at every day 0..260, by election."""
    import pres_reversion as RV
    E = RV.load()
    return {y: E[y]["N"] * (1 - E[y]["u"] / 100) for y in YEARS}, {y: E[y]["result"] for y in YEARS}


def _ridge_np(Xm, y, pen, flags):
    mu, sd = Xm.mean(0), Xm.std(0)
    sd = np.where(sd == 0, 1.0, sd)
    A = np.column_stack([np.ones(len(y)), (Xm - mu) / sd])
    P = np.diag([0.0] + [pen if f else 0.0 for f in flags])
    beta = np.linalg.solve(A.T @ A + P + 1e-9 * np.eye(A.shape[1]), A.T @ y)
    return mu, sd, beta


def _pred_np(fit, x):
    mu, sd, beta = fit
    return float(beta[0] + ((x - mu) / sd) @ beta[1:])


def _choose_pen_np(Xm, y, flags):
    n = len(y)
    best = None
    for pen in PENS:
        err = 0.0
        for i in range(n):
            m = np.arange(n) != i
            err += (_pred_np(_ridge_np(Xm[m], y[m], pen, flags), Xm[i]) - y[i]) ** 2
        if best is None or err < best[0] - 1e-12:
            best = (err, pen)
    return best[1]


def fund_fit_and_var(Xm, y, flags):
    """Fit on all rows with the penalty chosen by leaving one out; the variance is the mean squared error of each row
    predicted by a fit that left it out, with the penalty chosen again inside that fit (nested)."""
    pen = _choose_pen_np(Xm, y, flags)
    fit = _ridge_np(Xm, y, pen, flags)
    n = len(y)
    errs = []
    for i in range(n):
        m = np.arange(n) != i
        pi = _choose_pen_np(Xm[m], y[m], flags)
        errs.append(_pred_np(_ridge_np(Xm[m], y[m], pi, flags), Xm[i]) - y[i])
    return fit, pen, float(np.mean(np.square(errs)))


def blend(P, F, Vp, Vf):
    """Precision-weighted blend of the polls' forecast P and the fundamentals F; returns it and the weight on P."""
    w = (1 / Vp) / (1 / Vp + 1 / Vf)
    return w * P + (1 - w) * F, w


def blend_backtest(X, NF, RES, prior="fund", cols=PRIMARY, flags=PEN_FLAGS):
    """Every scored election fitted on the elections before it. Returns per election the blended forecast's error at
    each date, with the fitted weight and pieces."""
    out = {}
    for y in SCORED:
        earlier = [e for e in YEARS if e < y]
        # the polls' range from earlier elections' errors of stage 3's forecast, 7 to 150 days
        pts = [(k, (NF[e][k] - RES[e]) ** 2) for e in earlier for k in range(7, 151) if np.isfinite(NF[e][k])]
        b, a = np.polyfit([p[0] for p in pts], [p[1] for p in pts], 1)
        row = {}
        for dd in DAYS:
            D = X[(X.d == dd) & X.year.isin(earlier)].reset_index(drop=True)
            T = X[(X.d == dd) & (X.year == y)].iloc[0]
            if prior == "fund":
                f, pen, Vf = fund_fit_and_var(D[cols].values.astype(float), D.y.values.astype(float), flags)
                F = T.sign * _pred_np(f, T[cols].values.astype(float))
            else:
                F = T.sign * float(D.y.mean())
                pen = None
                errs = [float(D.drop(D.index[i]).y.mean()) - D.y.values[i] for i in range(len(D))]
                Vf = float(np.mean(np.square(errs)))
            Vp = max(a + b * dd, 1.0)
            P = float(NF[y][dd])
            fc, w = blend(P, F, Vp, Vf)
            row[dd] = {"err": fc - RES[y], "err_polls": P - RES[y], "w_polls": w, "fund": F, "pen": pen, "Vf": Vf, "Vp": Vp,
                       "term_limited_in_fit": int(D.term.sum())}
        out[y] = row
    return out


def score(bt, key="err", days=SCORE_DAYS):
    return {y: float(np.mean([r[dd][key] ** 2 for dd in days])) for y, r in bt.items()}


def summary(bt):
    sp, sc = score(bt, "err_polls"), score(bt, "err")
    gain = np.array([sp[y] - sc[y] for y in bt])
    nw = all(np.mean([bt[y][dd]["err"] ** 2 for y in bt]) <= np.mean([bt[y][dd]["err_polls"] ** 2 for y in bt]) + 1e-12
             for dd in REPORT_DAYS)
    return {"gain": float(gain.mean()), "better": int((gain > 1e-12).sum()), "not_worse_30_7": bool(nw),
            "by_election": {int(y): [round(sp[y], 3), round(sc[y], 3)] for y in bt},
            "by_day": {dd: [float(np.mean([bt[y][dd]["err_polls"] ** 2 for y in bt])),
                            float(np.mean([bt[y][dd]["err"] ** 2 for y in bt]))] for dd in DAYS}}


def shuffled_inputs(X, rng):
    perm = dict(zip(YEARS, [YEARS[i] for i in rng.permutation(len(YEARS))]))
    X2 = X.copy()
    for y, src in perm.items():
        for dd in DAYS:
            m2 = (X2.year == y) & (X2.d == dd)
            ms = (X.year == src) & (X.d == dd)
            for c in ("approval", "index", "term"):
                X2.loc[m2, c] = X.loc[ms, c].values
    return X2


def test2():
    X = load()
    NF, RES = national_forecasts()
    bt = blend_backtest(X, NF, RES)
    g = summary(bt)
    (OUT / "pres_fundamentals_test2_real.json").write_text(json.dumps({"summary": g}, indent=1, default=float))
    print(json.dumps(g, indent=1, default=float), flush=True)
    rng = np.random.default_rng(0)
    null = []
    for i in range(200):
        null.append(summary(blend_backtest(shuffled_inputs(X, rng), NF, RES))["gain"])
        if (i + 1) % 50 == 0:
            print("  shuffles", i + 1, flush=True)
    g["shuffle_95th"] = float(np.quantile(null, 0.95))
    g["share_of_shuffles_beaten"] = float(np.mean(np.array(null) < g["gain"]))
    g["passes"] = bool(g["gain"] > 0 and g["better"] >= 8 and g["not_worse_30_7"] and g["gain"] > g["shuffle_95th"])
    ctrl = summary(blend_backtest(X, NF, RES, prior="const"))
    inter = X.assign(appr_term=X.approval * X.term)
    open_seat = summary(blend_backtest(inter, NF, RES, cols=PRIMARY + ["appr_term"], flags=PEN_FLAGS + [True]))
    out = {"primary": g, "control_constant_prior": ctrl, "open_seat_interaction": open_seat,
           "weights_on_polls": {int(y): {dd: round(r[dd]["w_polls"], 3) for dd in DAYS} for y, r in bt.items()},
           "penalties": {int(y): {dd: r[dd]["pen"] for dd in DAYS} for y, r in bt.items()},
           "shuffle_gains": null}
    (OUT / "pres_fundamentals_test2.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "shuffle_gains"}, indent=1, default=float)[:5000])


# ---------------------------------------------------------------- checks
def checks():
    X = load()
    assert 2024 not in set(X.year)
    print("2024 refused: PASS")
    M = monthly_changes()
    # publication: changing months not yet published by the date changes nothing
    date = pd.Timestamp("2008-08-01")
    a = econ_inputs(M, date)
    M2 = {k: v.copy() for k, v in M.items()}
    for k in MEASURES:
        pub = published(M2[k], k, date)
        late = M2[k].index > pub.index.max()
        M2[k][late] = M2[k][late] + 99
    b = econ_inputs(M2, date)
    ok_pub = all((np.isnan(a[k]) and np.isnan(b[k])) or abs(a[k] - b[k]) < 1e-12 for k in a)
    # the latest usable GDP quarter on 2008-08-01 is 2008Q1 (Q2 ends Jun 30, + 35 days = Aug 4)
    ok_gdp = published(M["gdp"], "gdp", date).index.max() == pd.Timestamp("2008-01-01")
    # index = mean of signed standardized values
    vals = [a[k] for k in MEASURES if not np.isnan(a[k])]
    ok_idx = abs(a["index"] - np.mean(vals)) < 1e-12
    # planted relation; huge penalty -> approval alone
    rng = np.random.default_rng(1)
    Dt = pd.DataFrame({"approval": rng.normal(0, 10, 40), "index": rng.normal(0, 1, 40), "term": rng.integers(0, 2, 40).astype(float)})
    Dt["y"] = 2 + 0.5 * Dt.approval + 3 * Dt["index"] - 4 * Dt.term
    f = ridge(Dt[PRIMARY].values, Dt.y.values, 0.0, PEN_FLAGS)
    per = f[2][1:] / f[1]
    ok_plant = np.allclose(per, [0.5, 3, -4], atol=1e-6)
    f2 = ridge(Dt[PRIMARY].values, Dt.y.values, 1e9, PEN_FLAGS)
    ok_pen = abs(f2[2][2]) < 1e-3 and abs(f2[2][3]) < 1e-3
    print(f"publication: unpublished months change nothing {'PASS' if ok_pub else 'FAIL'}; GDP quarter lag "
          f"{'PASS' if ok_gdp else 'FAIL'}; index is the mean {'PASS' if ok_idx else 'FAIL'}; planted relation "
          f"recovered {'PASS' if ok_plant else 'FAIL'}; huge penalty gives approval alone {'PASS' if ok_pen else 'FAIL'}")
    NF, RES = national_forecasts()
    base = blend_backtest(X, NF, RES)
    # as-of: own result and later elections changed
    bad = 0
    for y in (1984, 2000, 2012):
        X2 = X.copy()
        RES2 = dict(RES)
        X2.loc[X2.year == y, "y"] += 15
        RES2[y] += 15
        for later in YEARS:
            if later > y:
                X2.loc[X2.year == later, ["approval", "index"]] += 7
                X2.loc[X2.year == later, "y"] -= 9
                RES2[later] -= 9
        b2 = blend_backtest(X2, NF, RES2)
        bad += int(not all(abs((b2[y][dd]["err"] + 15) - base[y][dd]["err"]) < 1e-9 for dd in DAYS))
    print(f"as-of test: {'PASS' if not bad else f'FAIL {bad}'}")
    # V_fund huge -> stage 3's forecast; V_polls huge -> the fundamentals
    ok_w = abs(blend(3.0, -5.0, 20.0, 1e12)[0] - 3.0) < 1e-9 and abs(blend(3.0, -5.0, 1e12, 20.0)[0] + 5.0) < 1e-9
    ok_w &= all(0 < base[y][dd]["w_polls"] < 1 for y in base for dd in DAYS)
    # party sign end to end: in a Republican-held year the blend's fundamentals are minus the incumbent prediction
    y = 2004
    earlier = [e for e in YEARS if e < y]
    D = X[(X.d == 60) & X.year.isin(earlier)].reset_index(drop=True)
    T = X[(X.d == 60) & (X.year == y)].iloc[0]
    f, _, _ = fund_fit_and_var(D[PRIMARY].values.astype(float), D.y.values.astype(float), PEN_FLAGS)
    inc = _pred_np(f, T[PRIMARY].values.astype(float))
    ok_w &= T.sign == -1 and abs(base[y][60]["fund"] + inc) < 1e-9
    print(f"party sign: a Republican year's fundamentals enter as minus the incumbent prediction {'PASS' if ok_w else 'FAIL'}")
    print(f"huge fundamentals variance gives stage 3's forecast, huge poll variance the fundamentals "
          f"{'PASS' if ok_w else 'FAIL'}")
    print("inputs sample:", X[X.d == 100][["year", "approval", "index", "term", "pca"]].round(2).to_dict("records")[:4])
    if not (ok_pub and ok_gdp and ok_idx and ok_plant and ok_pen and not bad and ok_w):
        raise SystemExit("a check failed")


if __name__ == "__main__":
    {"checks": checks, "test1": test1, "test2": test2}[sys.argv[1] if len(sys.argv) > 1 else "checks"]()
