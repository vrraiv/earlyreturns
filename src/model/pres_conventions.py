"""Stage 2 of EC-2: convention windows, on the national test bed (ELECTORAL_COLLEGE.md, section 11, "Stage 2:
convention windows, pre-registration").

Data: president_national_poll_days.csv (daily national readings, 1952 to 2020) and convention_dates.csv. Scored
elections 1980 to 2020, each fitted on the elections before it. 2024 is refused.

Forecast for a date (baseline = nowcast): readings of the matchup dated at least LAG days before it, weight
0.5 ** (age / 60). Range: squared spread a + b * days, fitted on the earlier elections' squared errors, 7 to 150 days.
Treatments: 1 rise and fade (bump fitted to the poll path), 2 down-weight the window (picked by score), 3 widen the
range within 30 days of a convention's end (kappa by maximum likelihood; judged by log score).
Rule: mean squared error over 150, 100 and 60 days (log score for treatment 3), elections equal; beat 19 in 20 of 200
shuffles of convention timing between elections; better in at least 8 of 11; 30 and 7 days not worse.

Run:  python src/model/pres_conventions.py checks
      python src/model/pres_conventions.py run
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
HALF_LIFE = 60.0
SCORE_DAYS = (150, 100, 60)
REPORT_DAYS = (30, 7)
RANGE_DAYS = tuple(range(7, 151))
TAUS = (7, 14, 30, 60)
OMEGAS = (0.0, 0.5)
WINDOWS = (14, 30)
WIDEN_DAYS = 30
SHUFFLES = 200
PRE_DAYS = 21
FIT_N = {}
POST_DAYS = 60


def load():
    d = pd.read_csv(INTERIM / "president_national_poll_days.csv", parse_dates=["date", "election_date"])
    assert 2024 not in set(d.cycle), "2024 is held out"
    d = d[d.cycle.isin(CYCLES)]
    c = pd.read_csv(INTERIM / "convention_dates.csv", parse_dates=["start", "end", "election_date"])
    c = c[c.cycle.isin(CYCLES)]
    E = {}
    for y in CYCLES:
        x = d[d.cycle == y]
        cc = c[c.cycle == y].sort_values("start")
        el = x.election_date.iloc[0]
        E[y] = {"t": (el - x.date).dt.days.values.astype(float),           # days before the election
                "m": x.margin_2p.values.astype(float),
                "result": float(x.result_margin_2p.iloc[0]),
                # timing unit: (start, end) in days before the election for the first and second convention, signs
                "conv": [((el - r.start).days, (el - r.end).days, 1.0 if r.party == "D" else -1.0)
                         for r in cc.itertuples()]}
    return E


def bump_shape(t, conv, tau):
    """Sum over conventions of sign x shape: 0 before the start, a straight rise to 1 at the end, then a fade with
    half-life tau. t and the convention dates are in days before the election (larger = earlier)."""
    out = np.zeros_like(t)
    for s, e, sg in conv:
        since_start = s - t
        since_end = e - t
        rise = np.where((since_start >= 0) & (since_end <= 0), since_start / max(s - e, 1), 0.0)
        fade = np.where(since_end > 0, 0.5 ** (since_end / tau), 0.0)
        out += sg * (rise + fade)
    return out


def forecast(el, day, s, conv):
    """The forecast `day` days before the election, from readings dated at least LAG days before it."""
    t, m = el["t"], el["m"]
    ok = t >= day + LAG
    if not ok.any():
        return np.nan
    tt, mm = t[ok], m[ok]
    w = 0.5 ** ((tt - day) / s.get("half_life", HALF_LIFE))
    if s.get("bump") is not None:
        B, tau = s["bump"]
        mm = mm - B * bump_shape(tt, conv, tau)
    if s.get("down") is not None:
        om, W = s["down"]
        inwin = np.zeros_like(tt, dtype=bool)
        for st, en, _ in conv:
            inwin |= (tt <= st) & (tt >= en - W)
        w2 = np.where(inwin, w * om, w)
        if w2.sum() > 0:                                # if no reading is left, the window's readings are used
            w = w2
    return float(np.average(mm, weights=w))


def fit_bump(E, conv_of, years):
    """B and tau by least squares on the poll path around the conventions of the given (earlier) elections."""
    best = None
    for tau in TAUS:
        X, Y = [], []
        for y in years:
            el, conv = E[y], conv_of[y]
            s1 = max(st for st, _, _ in conv)                                # first convention's start
            e2 = min(en for _, en, _ in conv)                                # second convention's end
            pre = (el["t"] > s1) & (el["t"] <= s1 + PRE_DAYS)
            win = (el["t"] <= s1) & (el["t"] >= e2 - POST_DAYS)
            if not pre.any() or not win.any():
                continue
            X.append(bump_shape(el["t"][win], conv, tau))
            Y.append(el["m"][win] - el["m"][pre].mean())
        if not X:
            return (0.0, 30)
        n_used = len(X)
        X, Y = np.concatenate(X), np.concatenate(Y)
        B = float((X * Y).sum() / (X * X).sum()) if (X * X).sum() > 0 else 0.0
        sse = float(((Y - B * X) ** 2).sum())
        if best is None or sse < best[0]:
            best = (sse, B, tau, n_used)
    FIT_N[tuple(years)] = best[3]
    return (best[1], best[2])


def sq_loss(E, conv_of, years, s_of, days=SCORE_DAYS):
    """Per election: mean squared error over the given days (dates with no reading are skipped)."""
    out = {}
    for y in years:
        e = [(forecast(E[y], d, s_of(y), conv_of[y]) - E[y]["result"]) ** 2 for d in days]
        e = [v for v in e if not np.isnan(v)]
        out[y] = float(np.mean(e)) if e else np.nan
    return out


def fit_down(E, conv_of, years):
    best = None
    for om in OMEGAS:
        for W in WINDOWS:
            L = sq_loss(E, conv_of, years, lambda y: {"down": (om, W)})
            v = np.nanmean(list(L.values()))
            if best is None or v < best[0]:
                best = (v, om, W)
    return (best[1], best[2])


def in_widen(day, conv):
    return any(0 <= en - day <= WIDEN_DAYS for _, en, _ in conv)


def fit_range(E, conv_of, years, s_of, widen=False):
    """a + b * days by least squares on squared errors (7 to 150 days); kappa >= 0 by maximum likelihood."""
    rows = []
    for y in years:
        for d in RANGE_DAYS:
            f = forecast(E[y], d, s_of(y), conv_of[y])
            if not np.isnan(f):
                rows.append((d, (f - E[y]["result"]) ** 2, in_widen(d, conv_of[y])))
    D = np.array([r[0] for r in rows], float)
    S = np.array([r[1] for r in rows], float)
    I = np.array([r[2] for r in rows], float)
    b, a = np.polyfit(D, S, 1)
    base = np.maximum(a + b * D, 1.0)
    kappa = 0.0
    if widen:
        grid = np.concatenate([[0.0], np.geomspace(0.1, 400, 200)])
        ll = [(-0.5 * (np.log(base + k * I) + S / (base + k * I))).sum() for k in grid]
        kappa = float(grid[int(np.argmax(ll))])
    return {"a": float(a), "b": float(b), "kappa": kappa}


def log_score(E, conv_of, years, s_of, rng_of, days=SCORE_DAYS):
    out = {}
    for y in years:
        r = rng_of(y)
        v = []
        for d in days:
            f = forecast(E[y], d, s_of(y), conv_of[y])
            if np.isnan(f):
                continue
            var = max(r["a"] + r["b"] * d, 1.0) + r["kappa"] * in_widen(d, conv_of[y])
            v.append(-0.5 * (np.log(2 * np.pi * var) + (f - E[y]["result"]) ** 2 / var))
        out[y] = float(np.mean(v)) if v else np.nan
    return out


def backtest(E, conv_of, half_life=HALF_LIFE):
    """Every scored election fitted on the elections before it. Returns per-election settings and losses."""
    res = {}
    for y in SCORED:
        earlier = [x for x in CYCLES if x < y]
        bump = fit_bump(E, conv_of, earlier)
        down = fit_down(E, conv_of, earlier)
        base_s = {"half_life": half_life}
        r_base = fit_range(E, conv_of, earlier, lambda _: base_s)
        r_wide = fit_range(E, conv_of, earlier, lambda _: base_s, widen=True)
        S = {"baseline": base_s, "bump": {"bump": bump, "half_life": half_life},
             "down": {"down": down, "half_life": half_life}}
        R = {"baseline": r_base, "bump": fit_range(E, conv_of, earlier, lambda _: S["bump"]),
             "down": fit_range(E, conv_of, earlier, lambda _: S["down"]), "widen": r_wide}
        row = {"fit": {"bump": bump, "bump_elections": FIT_N.get(tuple(earlier)), "down": down, "range": r_base,
                       "kappa": r_wide["kappa"]}}
        for k, s in S.items():
            row[k] = {"sq": sq_loss(E, conv_of, [y], lambda _: s)[y],
                      "by_day": {d: forecast(E[y], d, s, conv_of[y]) - E[y]["result"] for d in SCORE_DAYS + REPORT_DAYS},
                      "log": log_score(E, conv_of, [y], lambda _: s, lambda _: R[k])[y],
                      "log_report": log_score(E, conv_of, [y], lambda _: s, lambda _: R[k], REPORT_DAYS)[y],
                      "sq_report": {d: sq_loss(E, conv_of, [y], lambda _: s, (d,))[y] for d in REPORT_DAYS}}
        row["widen"] = {"log": log_score(E, conv_of, [y], lambda _: base_s, lambda _: r_wide)[y],
                        "log_report": log_score(E, conv_of, [y], lambda _: base_s, lambda _: r_wide, REPORT_DAYS)[y]}
        res[y] = row
    return res


def summary(res):
    ys = list(res)
    g = {}
    for k in ("bump", "down"):
        d = np.array([res[y]["baseline"]["sq"] - res[y][k]["sq"] for y in ys])
        g[k] = {"gain": float(d.mean()), "better": int((d > 1e-12).sum()),
                "not_worse_30_7": all(np.mean([res[y][k]["sq_report"][dd] for y in ys])
                                      <= np.mean([res[y]["baseline"]["sq_report"][dd] for y in ys]) + 1e-12
                                      for dd in REPORT_DAYS)}
    d = np.array([res[y]["widen"]["log"] - res[y]["baseline"]["log"] for y in ys])
    g["widen"] = {"gain": float(d.mean()), "better": int((d > 1e-12).sum()),
                  "not_worse_30_7": float(np.mean([res[y]["widen"]["log_report"] for y in ys]))
                  >= float(np.mean([res[y]["baseline"]["log_report"] for y in ys])) - 1e-12}
    return g


def shuffled_conv(E, rng):
    units = [E[y]["conv"] for y in CYCLES]
    perm = rng.permutation(len(units))
    return {y: units[perm[i]] for i, y in enumerate(CYCLES)}


def checks():
    E = load()
    conv = {y: E[y]["conv"] for y in CYCLES}
    print("2024 absent: PASS")
    # behaviour on a made-up flat series with 2016's convention dates (no results involved)
    c16 = conv[2016]
    tt = np.arange(200, -1, -1).astype(float)
    ok = True
    for s, e, sg in c16:
        one = [(s, e, sg)]
        ok &= abs(bump_shape(np.array([s + 5.0]), one, 14)[0]) < 1e-12           # before the start
        ok &= abs(bump_shape(np.array([float(s)]), one, 14)[0]) < 1e-12           # first day
        ok &= abs(bump_shape(np.array([float(e)]), one, 14)[0] - sg) < 1e-12      # last day: 1, with the party's sign
        ok &= abs(bump_shape(np.array([e - 14.0]), one, 14)[0] - 0.5 * sg) < 1e-12  # one half-life later: one half
    fake = {"t": tt, "m": 2.0 + 4.0 * bump_shape(tt, c16, 14), "result": 0.0, "conv": c16}
    Efake = {2016: fake}
    B, tau = fit_bump(Efake, {2016: c16}, [2016])
    ok_fit = abs(B - 4.0) < 1e-9 and tau == 14
    ok_adj = abs(forecast(fake, 60, {"bump": (4.0, 14), "half_life": 60}, c16) - 2.0) < 1e-9
    inwin = np.zeros_like(tt, dtype=bool)
    for s, e, _ in c16:
        inwin |= (tt <= s) & (tt >= e - 30)
    noisy = {"t": tt, "m": np.sin(tt), "result": 0.0}
    cut = {"t": tt[~inwin], "m": np.sin(tt)[~inwin], "result": 0.0}
    ok_down = abs(forecast(noisy, 40, {"down": (0.0, 30)}, c16) - forecast(cut, 40, {}, c16)) < 1e-12
    ok_down &= inwin[tt == min(e for _, e, _ in c16) - 30].all() and not inwin[tt == min(e for _, e, _ in c16) - 31].any()
    ok_widen = in_widen(100, c16) and not in_widen(60, c16)
    ok_base = abs(forecast(noisy, 40, {"half_life": 1e12}, c16) - np.sin(tt[tt >= 43]).mean()) < 1e-9
    print(f"behaviour: shape {'PASS' if ok else 'FAIL'}; bump recovered {'PASS' if ok_fit else 'FAIL'} ({B:.3f}, {tau}); "
          f"bump removed {'PASS' if ok_adj else 'FAIL'}; down-weight = window deleted, to W after the end "
          f"{'PASS' if ok_down else 'FAIL'}; widen on at 100, off at 60 (2016) {'PASS' if ok_widen else 'FAIL'}; "
          f"long half-life = plain mean {'PASS' if ok_base else 'FAIL'}")
    if not (ok and ok_fit and ok_adj and ok_down and ok_widen and ok_base):
        raise SystemExit("a behaviour check failed")
    bad = 0
    for y in SCORED:
        for d in SCORE_DAYS + REPORT_DAYS:
            for s in ({}, {"bump": (3.0, 14)}, {"down": (0.0, 30)}):
                a = forecast(E[y], d, s, conv[y])
                el = dict(E[y]); m = el["m"].copy(); m[el["t"] < d + LAG] += 50; el["m"] = m
                b = forecast(el, d, s, conv[y])
                bad += int(not (np.isnan(a) and np.isnan(b)) and abs(a - b) > 1e-9)
    print(f"leak test (readings within {LAG} days of the date or after it moved): {'PASS' if not bad else f'FAIL {bad}'}")
    base = backtest(E, conv)
    bad2 = 0
    for y in (1984, 2000, 2012):
        E2 = {k: dict(v) for k, v in E.items()}
        E2[y]["result"] += 20
        for later in CYCLES:
            if later > y:
                E2[later]["m"] = E2[later]["m"] + 30
                E2[later]["result"] += 30
        r2 = backtest(E2, conv)
        same_fit = json.dumps(r2[y]["fit"], default=float) == json.dumps(base[y]["fit"], default=float)
        same_fc = all(abs((r2[y][k]["by_day"][d] + 20) - base[y][k]["by_day"][d]) < 1e-9
                      for k in ("baseline", "bump", "down") for d in SCORE_DAYS)
        bad2 += int(not (same_fit and same_fc))
    print(f"as-of test (own result and later elections changed): {'PASS' if not bad2 else f'FAIL {bad2}'}")
    if bad or bad2:
        raise SystemExit("a check failed")


def run():
    E = load()
    conv = {y: E[y]["conv"] for y in CYCLES}
    res = backtest(E, conv)
    g = summary(res)
    rng = np.random.default_rng(0)
    null = {k: [] for k in g}
    for i in range(SHUFFLES):
        cs = shuffled_conv(E, rng)
        gs = summary(backtest(E, cs))
        for k in g:
            null[k].append(gs[k]["gain"])
        if (i + 1) % 20 == 0:
            print(f"  shuffles {i + 1}", flush=True)
    for k in g:
        q = float(np.quantile(null[k], 0.95))
        g[k]["shuffle_95th"] = q
        g[k]["share_of_shuffles_beaten"] = float(np.mean(np.array(null[k]) < g[k]["gain"]))
        g[k]["passes"] = bool(g[k]["gain"] > 0 and g[k]["gain"] > q and g[k]["better"] >= 8 and g[k]["not_worse_30_7"])
    empty = 0
    for y in SCORED:
        for d in SCORE_DAYS + REPORT_DAYS:
            for om in OMEGAS:
                for W in WINDOWS:
                    tt = E[y]["t"][E[y]["t"] >= d + LAG]
                    inwin = np.zeros_like(tt, dtype=bool)
                    for st, en, _ in conv[y]:
                        inwin |= (tt <= st) & (tt >= en - W)
                    empty += int(om == 0 and len(tt) > 0 and inwin.all())
    g["down"]["empty_window_fallbacks"] = empty
    g["widen"]["on_at_30_or_7_days"] = int(sum(in_widen(d, conv[y]) for y in SCORED for d in REPORT_DAYS))
    short = backtest(E, conv, half_life=7.0)
    diag = {"baseline_7day_half_life_sq": {y: short[y]["baseline"]["sq"] for y in SCORED},
            "baseline_7day_half_life_sq_report": {y: short[y]["baseline"]["sq_report"] for y in SCORED}}
    out = {"summary": g, "by_election": res, "shuffle_gains": null, "diagnostic": diag}
    (OUT / "pres_conventions.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(g, indent=1, default=float))
    for y in SCORED:
        r = res[y]
        print(y, "fit", r["fit"]["bump"], r["fit"]["down"], round(r["fit"]["kappa"], 2),
              "| sq base", round(r["baseline"]["sq"], 2), "bump", round(r["bump"]["sq"], 2), "down",
              round(r["down"]["sq"], 2), "| log base", round(r["baseline"]["log"], 3), "widen", round(r["widen"]["log"], 3),
              "| 7-day hl", round(short[y]["baseline"]["sq"], 2))


if __name__ == "__main__":
    {"checks": checks, "run": run}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
