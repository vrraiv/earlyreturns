"""Stage 4 of EC-2: states with few polls (ELECTORAL_COLLEGE.md, section 11, "Stage 4: states with few polls,
pre-registration").

Scored: on each date (150, 100, 60 days; 30 and 7 reported), the states and DC with no poll that ended in the previous
30 days, 2004 to 2020. Baseline: the state's own nowcast (stage 1's weighting, every poll before the date), or the
prior if it has no poll yet. Methods, none fitted:
  1 prior          national nowcast (two-party, 60-day half-life, readings dated 3+ days before) + previous lean
  2 average swing  previous result + mean over recently polled states of (nowcast - previous result)
  3 carry-forward  baseline + movement of the 14-day national average since the day after the state's last poll
Rule: squared error over 150/100/60 days, elections equal; positive gain; at least 4 of 5 elections better; 30 and 7
days not worse; methods 1 and 2: paired sign-flip over election-date units, p < 0.05; method 3: beat 19 in 20 of 200
shuffles of its movement term across the scored states with old polls.

Run:  python src/model/pres_thin_states.py checks
      python src/model/pres_thin_states.py run
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
import pres_nowcast as P  # noqa: E402

INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed"
CYCLES = (2004, 2008, 2012, 2016, 2020)
SCORE_DAYS = (150, 100, 60)
REPORT_DAYS = (30, 7)
LAG = 3
SHUFFLES = 200


def load_results():
    r = pd.read_csv(INTERIM / "state_presidential.csv")
    r = r[r.year <= 2020]                                          # no 2024 row is read
    assert r.year.max() <= 2020
    return {(int(y), s): (float(m), float(n), float(l)) for y, s, m, n, l in
            zip(r.year, r.state, r.margin_2p, r.national_margin_2p, r.lean_2p)}


def load_national():
    d = pd.read_csv(INTERIM / "president_national_poll_days.csv", parse_dates=["date", "election_date"])
    assert 2024 not in set(d.cycle)
    out = {}
    for y in CYCLES:
        x = d[d.cycle == y]
        el = x.election_date.iloc[0]
        out[y] = {"t": (el - x.date).dt.days.values.astype(float), "m": x.margin_2p.values.astype(float)}
    return out


def nat(Nd, y, day, hl):
    """National average `day` days before the election from readings dated at least LAG days before."""
    t, m = Nd[y]["t"], Nd[y]["m"]
    ok = t >= day + LAG
    if not ok.any():
        return np.nan
    return float(np.average(m[ok], weights=0.5 ** ((t[ok] - day) / hl)))


def nat_since(Nd, y, day_from, day_to, hl):
    """Movement of the national average from day_from to day_to (days before the election). If there is no reading
    as far back as day_from, from the earliest day with one."""
    a = nat(Nd, y, day_from, hl)
    if np.isnan(a):
        first = int(Nd[y]["t"].max()) - LAG
        a = nat(Nd, y, first, hl)
    return nat(Nd, y, day_to, hl) - a


STATES = None


def table(q, Nd, R, days=SCORE_DAYS + REPORT_DAYS):
    """One row per election, date and state (50 states and DC)."""
    global STATES
    if STATES is None:
        STATES = sorted({s for (y, s) in R if s != "US"})
    rows = []
    for y in CYCLES:
        qy = q[(q.cycle == y) & (q.geo != "US")]
        el = q[q.cycle == y].election.iloc[0]
        for d in days:
            t = el - pd.Timedelta(days=d)
            x = qy[qy.end < t]
            recent = x[x.end >= t - pd.Timedelta(days=30)].groupby("geo").size()
            n60 = nat(Nd, y, d, 60.0)
            now = {s: P.average(g, t, P.BASE) for s, g in x.groupby("geo")}
            polled = [s for s in recent.index if s in now and (y - 4, s) in R]
            swing = float(np.mean([now[s] - R[(y - 4, s)][0] for s in polled])) if polled else np.nan
            for s in STATES:
                prev_m, prev_n, prev_l = R[(y - 4, s)]
                prior = n60 + prev_l
                xs = x[x.geo == s]
                has_old = len(xs) > 0
                base = now[s] if has_old else prior
                if has_old:
                    last = xs.end.max()
                    d_from = (el - (last + pd.Timedelta(days=1))).days
                    mv14 = nat_since(Nd, y, d_from, d, 14.0)
                    mv60 = nat_since(Nd, y, d_from, d, 60.0)
                else:
                    mv14 = mv60 = 0.0
                rows.append({"cycle": y, "d": d, "state": s, "recent": int(recent.get(s, 0)),
                             "scored": int(recent.get(s, 0)) == 0, "has_old": has_old,
                             "baseline": base, "m1": prior, "m2": prev_m + swing if polled else prior,
                             "m3": base + mv14 if has_old else prior, "m3_60": base + mv60 if has_old else prior,
                             "mv14": mv14, "result": R[(y, s)][0]})
    return pd.DataFrame(rows)


def election_scores(T, col, days=SCORE_DAYS):
    """Per election: mean over its dates (with scored states) of the mean squared error over scored states."""
    x = T[T.scored & T.d.isin(days)]
    per = x.assign(se=(x[col] - x.result) ** 2).groupby(["cycle", "d"]).se.mean()
    return per.groupby("cycle").mean()


def units(T, col):
    """Election-date units at 150/100/60 days: mean gain (baseline minus method) across scored states."""
    x = T[T.scored & T.d.isin(SCORE_DAYS)]
    g = x.assign(gain=(x.baseline - x.result) ** 2 - (x[col] - x.result) ** 2).groupby(["cycle", "d"]).gain.mean()
    return g


def signflip_exact(u):
    """One-sided p for mean > 0, every sign pattern (units are few)."""
    v = np.asarray(u, float)
    stat = v.mean()
    n = len(v)
    cnt = 0
    tot = 0
    for signs in itertools.product((-1.0, 1.0), repeat=n):
        tot += 1
        cnt += (np.dot(signs, v) / n) >= stat - 1e-12
    return cnt / tot


def summarize(T, col):
    b, c = election_scores(T, "baseline"), election_scores(T, col)
    gain = float((b - c).mean())
    better = int(((b - c) > 1e-12).sum())
    nw = all(float(election_scores(T, col, (dd,)).mean()) <= float(election_scores(T, "baseline", (dd,)).mean()) + 1e-12
             for dd in REPORT_DAYS)
    return {"gain": gain, "better": better, "by_election": {int(k): [float(b[k]), float(c[k])] for k in b.index},
            "not_worse_30_7": bool(nw),
            "report_days": {dd: [float(election_scores(T, "baseline", (dd,)).mean()),
                                 float(election_scores(T, col, (dd,)).mean())] for dd in REPORT_DAYS},
            "by_day": {dd: [float(election_scores(T, "baseline", (dd,)).mean()),
                            float(election_scores(T, col, (dd,)).mean())] for dd in SCORE_DAYS}}


def shuffle_m3(T, rng):
    """Method 3's movement term shuffled across the scored states with old polls, within each election and date."""
    T2 = T.copy()
    for (y, d), idx in T2[T2.scored & T2.has_old].groupby(["cycle", "d"]).groups.items():
        mv = T2.loc[idx, "mv14"].values
        T2.loc[idx, "m3"] = T2.loc[idx, "baseline"].values + rng.permutation(mv)
    return T2


def diagnostics(T, q):
    x = T[T.d.isin(SCORE_DAYS)].copy()
    x["grp"] = pd.cut(x.recent, [-1, 0, 3, 9, 1e9], labels=["0", "1-3", "4-9", "10+"])
    x["err_prior"] = x.m1 - x.result
    a_pool = x.groupby("grp", observed=True).err_prior.agg(mse=lambda e: float((e ** 2).mean()),
                                                           mean=lambda e: float(e.mean()), n="size")
    a_el = x.groupby(["cycle", "grp"], observed=True).err_prior.agg(mse=lambda e: float((e ** 2).mean()), n="size")
    b = x[(x.recent >= 1) & (x.recent <= 3)]
    b_closer = (b.baseline - b.result).abs() < (b.m1 - b.result).abs()
    s = T[T.scored & T.has_old & T.d.isin(SCORE_DAYS)]
    flag_share = float(((s.baseline - s.result).abs() < (s.m1 - s.result).abs()).mean()) if len(s) else np.nan
    changed = {}
    for col in ("m1", "m2", "m3"):
        z = T[T.scored & T.d.isin(SCORE_DAYS + REPORT_DAYS)]
        changed[col] = z.assign(ch=(z[col] - z.baseline).abs() > 1e-9).groupby(["cycle", "d"]).ch.sum().astype(int)
    thin_states = T[T.scored][["cycle", "d", "state"]]
    spons = 0
    for (y, d), g in thin_states.groupby(["cycle", "d"]):
        el = q[q.cycle == y].election.iloc[0]
        t = el - pd.Timedelta(days=d)
        spons += int(((q.cycle == y) & q.geo.isin(g.state) & (q.end < t) & (q.sg != 0)).sum())
    a_el_signed = x.groupby(["cycle", "grp"], observed=True).err_prior.mean()
    gain_changed = {}
    for col in ("m1", "m2", "m3"):
        z = T[T.scored & T.d.isin(SCORE_DAYS)]
        z = z[(z[col] - z.baseline).abs() > 1e-9]
        gain_changed[col] = {"n": int(len(z)), "mse_baseline": float(((z.baseline - z.result) ** 2).mean()) if len(z) else None,
                             "mse_method": float(((z[col] - z.result) ** 2).mean()) if len(z) else None}
    return {
        "a_by_election_signed": {f"{c}/{g}": round(float(v), 3) for (c, g), v in a_el_signed.items()},
        "gain_on_changed_states": gain_changed,
        "a_pooled": a_pool.round(3).to_dict("index"),
        "a_by_election": {f"{c}/{g}": v for (c, g), v in a_el.round(3).to_dict("index").items()},
        "b_cases": int(len(b)),
        "b_nowcast_mse": float(((b.baseline - b.result) ** 2).mean()),
        "b_prior_mse": float(((b.m1 - b.result) ** 2).mean()),
        "b_share_nowcast_closer": float(b_closer.mean()),
        "b_by_election": {int(c): {"n": int(len(g)), "share_closer": float(((g.baseline - g.result).abs()
                                                                            < (g.m1 - g.result).abs()).mean())}
                          for c, g in b.groupby("cycle")},
        "c_sponsored_old_polls_in_thin_states": spons,
        "m3_flag_share_old_polls_closer": flag_share,
        "m3_flag": bool(flag_share < 0.5) if not np.isnan(flag_share) else None,
        "changed_by_method": {k: {f"{c}/{d}": int(v) for (c, d), v in s_.items()} for k, s_ in changed.items()},
    }


def checks():
    q = P.load()
    assert 2024 not in set(q.cycle)
    R = load_results()
    Nd = load_national()
    print("2024 absent from polls and results: PASS")
    T = table(q, Nd, R)
    # behaviour
    ok1 = np.allclose(T.m1, [nat(Nd, y, d, 60.0) + R[(y - 4, s)][2] for y, d, s in zip(T.cycle, T.d, T.state)])
    Nflat = {y: {"t": v["t"], "m": np.full_like(v["m"], 5.0)} for y, v in Nd.items()}
    Tf = table(q, Nflat, R, days=(100,))
    ok3 = np.allclose(Tf[Tf.has_old].m3, Tf[Tf.has_old].baseline)
    # made-up uniform swing: every state poll of 2012 set to its state's 2008 result + 3 (likely voters, no sponsor),
    # so every polled state's nowcast is its previous result + 3 and method 2 must give previous result + 3
    qs = q.copy()
    m12 = (qs.cycle == 2012) & (qs.geo != "US")
    qs.loc[m12, "m"] = [R[(2008, g)][0] + 3.0 if (2008, g) in R else 0.0 for g in qs.loc[m12, "geo"]]
    qs.loc[m12, "pop"] = "lv"
    qs.loc[m12, "sg"] = 0
    Ts = table(qs, Nd, R, days=(100,))
    z = Ts[(Ts.cycle == 2012) & Ts.scored]
    ok2 = len(z) > 0 and np.allclose(z.m2.values, [R[(2008, s)][0] + 3.0 for s in z.state])
    # planted national step: readings after a state's last poll 4 points higher (then 4 lower); method 3 must move
    # the baseline up (then down), by no more than the step
    y, d = 2016, 100
    el = q[q.cycle == y].election.iloc[0]
    t = el - pd.Timedelta(days=d)
    st = T[(T.cycle == y) & (T.d == d) & T.scored & T.has_old].state.iloc[0]
    last = q[(q.cycle == y) & (q.geo == st) & (q.end < t)].end.max()
    d_from = (el - (last + pd.Timedelta(days=1))).days
    ok3b = True
    for step in (4.0, -4.0):
        Ns = {k: dict(v) for k, v in Nd.items()}
        Ns[y]["m"] = np.where(Nd[y]["t"] < d_from, step, 0.0)
        Tp = table(q, Ns, R, days=(d,))
        row = Tp[(Tp.cycle == y) & (Tp.state == st)].iloc[0]
        mv = row.m3 - row.baseline
        ok3b &= (0 < mv <= step + 1e-9) if step > 0 else (step - 1e-9 <= mv < 0)
    print(f"behaviour: method 1 = national + lean {'PASS' if ok1 else 'FAIL'}; no national movement -> method 3 = "
          f"baseline {'PASS' if ok3 else 'FAIL'}; a planted national step moves method 3 the right way and no further "
          f"{'PASS' if ok3b else 'FAIL'}; a made-up uniform swing of 3 is recovered by method 2 {'PASS' if ok2 else 'FAIL'}")
    ok3 = ok3 and ok3b
    cols = ["scored", "baseline", "m1", "m2", "m3", "m3_60"]
    # leak and deletion
    bad = 0
    for y in CYCLES:
        el = q[q.cycle == y].election.iloc[0]
        for d in (100, 60):
            t = el - pd.Timedelta(days=d)
            q2 = q.copy(); q2.loc[(q2.cycle == y) & (q2.end >= t), "m"] += 50
            q3 = q[~((q.cycle == y) & (q.end >= t))]
            N2 = {k: dict(v) for k, v in Nd.items()}
            m = Nd[y]["m"].copy(); m[Nd[y]["t"] < d + LAG] += 50; N2[y]["m"] = m
            ref = T[(T.cycle == y) & (T.d == d)].reset_index(drop=True)[cols]
            for qq, NN in ((q2, N2), (q3, Nd)):
                T2 = table(qq, NN, R, days=(d,))
                T2 = T2[T2.cycle == y].reset_index(drop=True)[cols]
                bad += int(not np.allclose(T2[cols[1:]].values.astype(float), ref[cols[1:]].values.astype(float))
                           or not (T2.scored.values == ref.scored.values).all())
    print(f"leak and deletion tests: {'PASS' if not bad else f'FAIL {bad}'}")
    # results of the scored election changed
    R2 = {k: ((v[0] + 20, v[1] + 20, v[2]) if k[0] == 2012 else v) for k, v in R.items()}
    T3 = table(q, Nd, R2, days=(100,))
    ref = T[T.d == 100].reset_index(drop=True)
    ok4 = np.allclose(T3[cols[1:]].values.astype(float), ref[cols[1:]].values.astype(float))
    print(f"own results changed, forecasts unchanged: {'PASS' if ok4 else 'FAIL'}")
    if not (ok1 and ok2 and ok3 and ok4 and not bad):
        raise SystemExit("a check failed")


def run():
    q = P.load()
    R = load_results()
    Nd = load_national()
    T = table(q, Nd, R)
    T.to_csv(OUT / "pres_thin_states_table.csv", index=False)
    out = {"methods": {}}
    for col in ("m1", "m2", "m3"):
        out["methods"][col] = summarize(T, col)
    for col in ("m1", "m2"):
        u = units(T, col)
        out["methods"][col]["units"] = int(len(u))
        out["methods"][col]["p_signflip"] = float(signflip_exact(u.values))
        b, c = election_scores(T, "baseline"), election_scores(T, col)
        out["methods"][col]["p_signflip_elections_reported"] = float(signflip_exact((b - c).values))
        m = out["methods"][col]
        m["passes"] = bool(m["gain"] > 0 and m["better"] >= 4 and m["not_worse_30_7"] and m["p_signflip"] < 0.05)
    rng = np.random.default_rng(0)
    null = []
    for _ in range(SHUFFLES):
        T2 = shuffle_m3(T, rng)
        null.append(summarize(T2, "m3")["gain"])
    m = out["methods"]["m3"]
    m["shuffle_95th"] = float(np.quantile(null, 0.95))
    m["share_of_shuffles_beaten"] = float(np.mean(np.array(null) < m["gain"]))
    m["passes"] = bool(m["gain"] > 0 and m["gain"] > m["shuffle_95th"] and m["better"] >= 4 and m["not_worse_30_7"])
    out["methods"]["m3_60_reported"] = summarize(T, "m3_60")
    out["diagnostics"] = diagnostics(T, q)
    out["scored_states"] = {f"{c}/{d}": int(n) for (c, d), n in T[T.scored].groupby(["cycle", "d"]).size().items()}
    (OUT / "pres_thin_states.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    {"checks": checks, "run": run}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
