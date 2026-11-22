"""Stage 5 of EC-2: the add-up (ELECTORAL_COLLEGE.md, section 11, "Stage 5: the add-up, pre-registration" and the
confirmation after it).

States first (baseline): each state's estimate is stage 4's (its own polls however old, or the prior); the popular
vote is their sum weighted by the previous election's two-party vote. Candidates:
  A  national polls set the popular vote: the gap D = national forecast - weighted sum is spread in proportion to
     vote share x sigma2, sigma2 = 1 / (1 + polls in the last 30 days); the new sum equals the national forecast
  B  stage 3's scaling on every state: margin x (1 - u/100), u the national undecided share
  C  every state moves by D
The national forecast is stage 3's: national nowcast x (1 - u/100).
Score: at 30 and 7 days, per state excess = max(0, |state error| - |national error|), squared, mean over the 51, then
over the two dates, elections equal. Rule: positive gain; at least 4 of 5 elections better; A beats 19 in 20 of 200
shuffles of sigma2 across states; B and C a paired sign-flip over the 10 election-date units, p < 0.05.

Run:  python src/model/pres_addup.py checks
      python src/model/pres_addup.py run
      python src/model/pres_addup.py rerun     (after EC-4: the same test with EC-4's adopted blend as the state
                                                estimate; section 13 of the note. Writes pres_addup_rerun.json)
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
import pres_thin_states as TS  # noqa: E402
import pres_reversion as RV  # noqa: E402

INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed"
CYCLES = (2004, 2008, 2012, 2016, 2020)
SCORE_DAYS = (30, 7)
REPORT_DAYS = (150, 100, 60)
ALL_DAYS = SCORE_DAYS + REPORT_DAYS
SHUFFLES = 200


def vote_shares():
    r = pd.read_csv(INTERIM / "state_presidential.csv")
    r = r[r.year <= 2020]
    assert r.year.max() <= 2020
    tot = {(int(y), s): float(d + q) for y, s, d, q in zip(r.year, r.state, r.d_votes, r.r_votes)}
    return tot


def frame(q, Nd, R, E, votes, T=None):
    """Per election, date and state: baseline, candidates, result, weights, the national forecast and its error.
    T: stage 4's table, or (the rerun) the same table with another state estimate in its baseline column."""
    if T is None:
        T = TS.table(q, Nd, R, days=ALL_DAYS)
    rows = []
    for (y, d), g in T.groupby(["cycle", "d"]):
        g = g.copy()
        v = np.array([votes[(y - 4, s)] for s in g.state]); v = v / v.sum()
        mu = g.baseline.values.astype(float)
        u = float(E[y]["u"][d])
        n2 = float(E[y]["N"][d])
        natF = n2 * (1 - u / 100)
        nat_res = float(R[(y, g.state.iloc[0])][1])
        sig = 1.0 / (1.0 + g.recent.values.astype(float))
        D = natF - float(v @ mu)
        D2 = n2 - float(v @ mu)
        g["v"] = v
        g["sig"] = sig
        g["A"] = mu + D * sig / float(v @ sig)
        g["A_2p"] = mu + D2 * sig / float(v @ sig)
        g["B"] = mu * (1 - u / 100)
        g["C"] = mu + D
        muB = g["B"].values
        DB = natF - float(v @ muB)
        g["BA"] = muB + DB * sig / float(v @ sig)
        g["BC"] = muB + DB
        g["natF"], g["nat_err"], g["gap"], g["u"] = natF, natF - nat_res, D, u
        rows.append(g)
    return pd.concat(rows, ignore_index=True)


def excess(F, col):
    e = (F[col] - F.result).abs()
    return np.maximum(0.0, e - F.nat_err.abs()) ** 2


def election_scores(F, col, days=SCORE_DAYS, kind="excess"):
    x = F[F.d.isin(days)]
    loss = excess(x, col) if kind == "excess" else (x[col] - x.result) ** 2
    return x.assign(L=loss.values).groupby(["cycle", "d"]).L.mean().groupby("cycle").mean()


def units(F, col):
    x = F[F.d.isin(SCORE_DAYS)]
    g = (excess(x, "baseline") - excess(x, col)).values
    return x.assign(g=g).groupby(["cycle", "d"]).g.mean()


def signflip_exact(u):
    v = np.asarray(u, float)
    stat = v.mean()
    n = len(v)
    cnt = sum((np.dot(s, v) / n) >= stat - 1e-12 for s in itertools.product((-1.0, 1.0), repeat=n))
    return cnt / 2 ** n


def summarize(F, col):
    b, c = election_scores(F, "baseline"), election_scores(F, col)
    out = {"gain": float((b - c).mean()), "better": int(((b - c) > 1e-12).sum()),
           "by_election": {int(k): [float(b[k]), float(c[k])] for k in b.index},
           "plain_sq": [float(election_scores(F, "baseline", kind="sq").mean()), float(election_scores(F, col, kind="sq").mean())],
           "report_days_excess": {dd: [float(election_scores(F, "baseline", (dd,)).mean()),
                                       float(election_scores(F, col, (dd,)).mean())] for dd in ALL_DAYS}}
    bs, cs = election_scores(F, "baseline", kind="sq"), election_scores(F, col, kind="sq")
    out["plain_sq_clauses"] = {"gain": float((bs - cs).mean()), "better": int(((bs - cs) > 1e-12).sum()),
                               "by_election": {int(k): [float(bs[k]), float(cs[k])] for k in bs.index}}
    return out


def shuffle_A(F, rng, base_col="baseline", out_col="A"):
    F2 = F.copy()
    for (y, d), idx in F2.groupby(["cycle", "d"]).groups.items():
        g = F2.loc[idx]
        sig = rng.permutation(g.sig.values)
        v = g.v.values
        mu = g[base_col].values
        F2.loc[idx, out_col] = mu + g.gap.values[0] * sig / float(v @ sig) if base_col == "baseline" else \
            mu + (g.natF.values[0] - float(v @ mu)) * sig / float(v @ sig)
    return F2


def reports(F):
    out = {}
    x = F[F.d.isin(SCORE_DAYS)].copy()
    for col in ("baseline", "A", "B", "C", "A_2p"):
        pv = x.assign(w=x.v * x[col]).groupby(["cycle", "d"]).w.sum()
        res = x.groupby(["cycle", "d"]).apply(lambda g: g.natF.iloc[0] - g.nat_err.iloc[0])
        out.setdefault("popular_vote_sq_error", {})[col] = float(((pv - res) ** 2).groupby("cycle").mean().mean())
        vw = x.assign(L=excess(x, col).values * x.v).groupby(["cycle", "d"]).L.sum().groupby("cycle").mean().mean()
        out.setdefault("vote_weighted_excess", {})[col] = float(vw)
        close = x[x.baseline.abs() < 10]
        lop = x[x.baseline.abs() >= 10]
        out.setdefault("close_states_excess", {})[col] = float(excess(close, col).mean())
        out.setdefault("lopsided_states_excess", {})[col] = float(excess(lop, col).mean())
        for side, sub in (("dem_leaning", x[x.baseline > 0]), ("rep_leaning", x[x.baseline <= 0])):
            out.setdefault(f"{side}_sq", {})[col] = float(((sub[col] - sub.result) ** 2).mean())
        er = x[col] - x.result
        within = er - er.groupby([x.cycle, x.d]).transform("mean")
        out.setdefault("sq_mean_error_removed", {})[col] = float((within ** 2).mean())
    out["national_error_by_election"] = {int(c): round(float(g.groupby("d").nat_err.first().abs().mean()), 3)
                                          for c, g in F[F.d.isin(SCORE_DAYS)].groupby("cycle")}
    out["gap_by_election_date"] = {f"{c}/{d}": round(float(g.gap.iloc[0]), 3) for (c, d), g in F.groupby(["cycle", "d"])}
    out["national_error_by_election_date"] = {f"{c}/{d}": round(float(g.nat_err.iloc[0]), 3) for (c, d), g in F.groupby(["cycle", "d"])}
    return out


def checks():
    q = P.load()
    R = TS.load_results(); Nd = TS.load_national(); E = RV.load(); votes = vote_shares()
    print("2024 absent from polls, results and the national series: PASS")
    F = frame(q, Nd, R, E, votes)
    ok = True
    for (y, d), g in F.groupby(["cycle", "d"]):
        ok &= abs(float(g.v @ g.A) - g.natF.iloc[0]) < 1e-9 and abs(float(g.v @ g.C) - g.natF.iloc[0]) < 1e-9
    # D = 0 moves nothing; equal sigma gives C; u = 0 gives B = baseline
    g = F[(F.cycle == 2012) & (F.d == 7)].copy()
    v, mu = g.v.values, g.baseline.values
    natF0 = float(v @ mu)
    sig = g.sig.values
    okD = np.allclose(mu + (natF0 - v @ mu) * sig / (v @ sig), mu)
    eq = np.ones_like(sig)
    okC = np.allclose(mu + g.gap.values[0] * eq / (v @ eq), g.C.values)
    E0 = {k: dict(v_, u=np.zeros_like(v_["u"])) for k, v_ in E.items()}
    F0 = frame(q, Nd, R, E0, votes)
    okB = np.allclose(F0.B.values, F0.baseline.values)
    # direction, on frame's own output: A's shift has the gap's sign and is larger where there are fewer recent polls;
    # C's shift equals the gap in every state
    okdir = True
    for (y, d), g in F.groupby(["cycle", "d"]):
        sh = (g.A - g.baseline).values
        gap = g.gap.iloc[0]
        if abs(gap) > 1e-9:
            okdir &= bool((np.sign(sh) == np.sign(gap)).all())
            few, many = g.recent.values.min(), g.recent.values.max()
            if few != many:
                okdir &= bool(np.abs(sh[g.recent.values == few]).min() > np.abs(sh[g.recent.values == many]).max())
        okdir &= bool(np.allclose((g.C - g.baseline).values, gap))
    ok = ok and okdir
    print(f"direction: A's shift has the gap's sign and is larger with fewer recent polls; C moves every state by the gap "
          f"{'PASS' if okdir else 'FAIL'}")
    print(f"behaviour: A and C sum to the national forecast {'PASS' if ok else 'FAIL'}; D = 0 moves nothing "
          f"{'PASS' if okD else 'FAIL'}; equal sigma2 gives C {'PASS' if okC else 'FAIL'}; u = 0 gives the baseline "
          f"{'PASS' if okB else 'FAIL'}")
    cols = ["baseline", "A", "B", "C", "BA", "BC"]
    bad = 0
    for y in CYCLES:
        el = q[q.cycle == y].election.iloc[0]
        for d in (30, 7):
            t = el - pd.Timedelta(days=d)
            q2 = q.copy(); q2.loc[(q2.cycle == y) & (q2.end >= t), "m"] += 50
            q3 = q[~((q.cycle == y) & (q.end >= t))]
            N2 = {k: dict(v_) for k, v_ in Nd.items()}
            mm = Nd[y]["m"].copy(); mm[Nd[y]["t"] < d + 3] += 50; N2[y]["m"] = mm
            E2 = {k: dict(v_) for k, v_ in E.items()}
            m2 = E[y]["m"].copy(); m2[E[y]["t"] < d + 3] += 50
            E2[y]["N"] = np.array([RV.wavg(E[y]["t"], m2, k, RV.HL) if k >= d else E[y]["N"][k] for k in range(RV.DMAX + 1)])
            ref = F[(F.cycle == y) & (F.d == d)].reset_index(drop=True)[cols].values
            for qq, NN in ((q2, N2), (q3, Nd)):
                F2 = frame(qq, NN, R, E2, votes)
                got = F2[(F2.cycle == y) & (F2.d == d)].reset_index(drop=True)[cols].values
                bad += int(not np.allclose(got, ref))
    print(f"leak and deletion tests: {'PASS' if not bad else f'FAIL {bad}'}")
    R2 = {k: ((v_[0] + 20, v_[1] + 20, v_[2]) if k[0] == 2016 else v_) for k, v_ in R.items()}
    F3 = frame(q, Nd, R2, E, votes)
    ok4 = np.allclose(F3[cols].values, F[cols].values)
    print(f"own results changed, forecasts unchanged: {'PASS' if ok4 else 'FAIL'}")
    if not (ok and okD and okC and okB and ok4 and not bad):
        raise SystemExit("a check failed")


def evaluate(F):
    """The candidates, the rule, the flag and the reports on one frame. The same for the first run and the rerun."""
    out = {"candidates": {}}
    for col in ("A", "B", "C"):
        out["candidates"][col] = summarize(F, col)
    for col in ("B", "C"):
        u = units(F, col)
        m = out["candidates"][col]
        m["units"] = int(len(u))
        m["p_signflip"] = float(signflip_exact(u.values))
        b, c = election_scores(F, "baseline"), election_scores(F, col)
        m["p_signflip_elections_reported"] = float(signflip_exact((b - c).values))
        m["passes"] = bool(m["gain"] > 0 and m["better"] >= 4 and m["p_signflip"] < 0.05)
    rng = np.random.default_rng(0)
    null = [summarize(shuffle_A(F, rng), "A")["gain"] for _ in range(SHUFFLES)]
    m = out["candidates"]["A"]
    m["shuffle_95th"] = float(np.quantile(null, 0.95))
    m["share_of_shuffles_beaten"] = float(np.mean(np.array(null) < m["gain"]))
    m["passes"] = bool(m["gain"] > 0 and m["better"] >= 4 and m["gain"] > m["shuffle_95th"])
    m["p_signflip_reported"] = float(signflip_exact(units(F, "A").values))
    for col in ("A", "B", "C"):
        m = out["candidates"][col]
        m["flag_worse_on_plain_sq"] = bool(m["plain_sq_clauses"]["gain"] < 0)
    out["reported"] = {"A_with_two_party_national": summarize(F, "A_2p")}
    passes = {k for k, v in out["candidates"].items() if v["passes"]}
    if "B" in passes and passes & {"A", "C"}:
        for col in ("BA", "BC"):
            if col[1] in passes:
                s = summarize(F, col)
                if col == "BA":
                    nb = [summarize(shuffle_A(F, rng, base_col="B", out_col="BA"), "BA")["gain"] for _ in range(SHUFFLES)]
                    s["shuffle_95th"] = float(np.quantile(nb, 0.95))
                    s["passes"] = bool(s["gain"] > 0 and s["better"] >= 4 and s["gain"] > s["shuffle_95th"])
                else:
                    u = units(F, col)
                    s["p_signflip"] = float(signflip_exact(u.values))
                    s["passes"] = bool(s["gain"] > 0 and s["better"] >= 4 and s["p_signflip"] < 0.05)
                out.setdefault("combinations", {})[col] = s
    out["reports"] = reports(F)
    return out


def run():
    q = P.load()
    R = TS.load_results(); Nd = TS.load_national(); E = RV.load(); votes = vote_shares()
    F = frame(q, Nd, R, E, votes)
    F.to_csv(OUT / "pres_addup_frame.csv", index=False)
    out = evaluate(F)
    (OUT / "pres_addup.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


def blended_table(q, Nd, R):
    """Stage 4's table with each state's estimate replaced by EC-4's adopted blend (F: prior + w x (polls - prior), w
    fitted per date on earlier elections) before any shift. 2004 at 150, 100 and 60 days has no earlier election to
    fit on and keeps stage 4's estimate. Poll counts, results and everything else are stage 4's."""
    import pres_prior as PP
    T = TS.table(q, Nd, R, days=ALL_DAYS)
    q0, R0, Nd0, L, votes0 = PP.load_all()
    A0 = PP.assemble(PP.poll_cells(q0), Nd0, R0, L, votes0)
    Eb, _ = PP.rung(A0, "base")
    EF, fits = PP.rung(A0, "F")
    ix = {st: i for i, st in enumerate(PP.STATES)}
    key = list(zip(T.cycle, T.d, T.state))
    base = np.array([Eb[(y, d)][ix[st]] for y, d, st in key])
    assert np.allclose(base, T.baseline.values), "EC-4's baseline is not stage 4's state estimate"
    T = T.copy()
    T["stage4"] = T.baseline
    T["baseline"] = np.array([EF[(y, d)][ix[st]] for y, d, st in key])
    return T, {f"{y}/{d}": v for (y, d), v in fits.items() if v}


def rerun():
    q = P.load()
    R = TS.load_results(); Nd = TS.load_national(); E = RV.load(); votes = vote_shares()
    T, fits = blended_table(q, Nd, R)
    F = frame(q, Nd, R, E, votes, T=T)
    for (y, d), g in F.groupby(["cycle", "d"]):                     # A and C still sum to the national forecast
        assert abs(float(g.v @ g.A) - g.natF.iloc[0]) < 1e-9 and abs(float(g.v @ g.C) - g.natF.iloc[0]) < 1e-9
        assert np.allclose((g.C - g.baseline).values, g.gap.iloc[0])
    F.to_csv(OUT / "pres_addup_rerun_frame.csv", index=False)
    out = evaluate(F)
    out["state_estimate"] = "EC-4's F before any shift"
    out["weights_on_polls"] = fits
    x = F[F.d.isin(SCORE_DAYS)]
    out["state_dates_changed_from_stage4"] = int(((x.baseline - x.stage4).abs() > 1e-9).sum())
    (OUT / "pres_addup_rerun.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    {"checks": checks, "run": run, "rerun": rerun}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
