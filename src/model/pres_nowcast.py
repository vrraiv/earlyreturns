"""Stage 1 of EC-2: the presidential nowcast, scored by how well the average predicts the next polls.
No results are used. ELECTORAL_COLLEGE.md, section 11, "Stage 1: pre-registration", is the protocol this follows.

Test bed: president_general_polls.csv, 2004 to 2020, states, Maine and Nebraska districts, and the nation. 2000 is
out (late polls only, no population field). 2024 is refused at load (held out of everything in section 11).

Per poll, one question: head-to-head if the poll has one, then likely voters, voters, registered voters, adults.
A poll's date is its last field day (the middle where the last is missing: 2004 national).

The average at date t uses polls that ended before t. Weights, borrowed from the Senate average (pollavg.py):
  0.5 ** (age / half_life) * sqrt(min(n, 3000) / 600) * population weight / sqrt(polls by that pollster in the pool)
Margins: two-party, Democrat minus Republican. Registered-voter and adult polls are shifted by the population lean;
sponsored polls by the flat sponsor shift (the partisan flag exists only in 2020 in this test bed).

Score: each week from 161 days out, the polls that end in the next 7 days are the targets. A target is a likely-voter
(or "voters") poll with no sponsor flag. It is predicted by the average at the start of its week, built without
its own pollster's polls. A target counts if another pollster polled that place in the 60 days before. Loss =
squared error; mean by cycle; cycles weighted equally. The targets are the same for every candidate.

Run:  python src/model/pres_nowcast.py checks         (2024 refusal, leak test, parity with pollavg.weighted_avg)
      python src/model/pres_nowcast.py baseline
      python src/model/pres_nowcast.py <candidate>     (half_life | house | rv_lean)
Writes data/processed/pres_nowcast_<name>.json
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
CYCLES = (2004, 2008, 2012, 2016, 2020)
_PS = json.loads((OUT / "poll_settings.json").read_text())["chosen"]
BASE = {"half_life": float(_PS["half_life_races"]),                        # 60 days
        "pop_w": {"lv": 1.0, "v": 1.0, "rv": _PS["pop_weight"]["rv"], "a": _PS["pop_weight"]["a"]},
        "pop_lean": {"lv": 0.0, "v": 0.0, "rv": _PS["pop_dem_lean"]["rv"], "a": _PS["pop_dem_lean"]["a"]},
        "sponsor_shift": float(_PS["partisan_shift_statewide"]), "house": None}
POP_RANK = {"lv": 0, "v": 1, "rv": 2, "a": 3}
WEEKS = 23                       # target weeks: polls ending 1 to 161 days before the election
ELIG_DAYS = 60
HALF_LIVES = (7, 10, 14, 21, 30, 45, 60, 90)
BANDS = [(1, 30), (31, 90), (91, 161)]


def norm(name):
    import pollster_effects as PE
    return PE.norm(name) or str(name).lower()


def load(cycles=CYCLES):
    p = pd.read_csv(INTERIM / "president_general_polls.csv", low_memory=False)
    assert 2024 not in cycles, "2024 is held out"
    p = p[p.cycle.isin(cycles) & ~p.presumptive & ~p.state_subsample.fillna(False).astype(bool)].copy()
    assert 2024 not in set(p.cycle)
    p["pop"] = p.population.fillna("lv").str.lower()
    p["h2h"] = p.head_to_head.fillna(False).astype(bool)
    p["rank"] = p["pop"].map(POP_RANK).fillna(4)
    p = p[p.h2h == p.groupby("poll_id").h2h.transform("max")]
    p = p[p["rank"] == p.groupby("poll_id")["rank"].transform("min")]
    p["m"] = 100 * (p.d_pct - p.r_pct) / (p.d_pct + p.r_pct)
    q = p.groupby("poll_id").agg(cycle=("cycle", "first"), geo=("geo", "first"), pollster=("pollster", "first"),
                                 pop=("pop", "first"), n=("sample_size", "first"), partisan=("partisan", "first"),
                                 end=("end_date", "first"), mid=("mid_date", "first"),
                                 election=("election_date", "first"), m=("m", "mean")).reset_index()
    q["end"] = pd.to_datetime(q.end.fillna(q.mid))
    q["election"] = pd.to_datetime(q.election)
    q["dte"] = (q.election - q.end).dt.days
    q["pkey"] = q.pollster.map(norm)
    q["n"] = q.n.fillna(600)
    q["sg"] = np.where(q.partisan == "DEM", 1, np.where(q.partisan == "REP", -1, 0))
    return q.dropna(subset=["m"]).sort_values(["cycle", "geo", "end"]).reset_index(drop=True)


def adjusted(pool, s):
    """Each pool poll's margin after the population lean, the sponsor shift and (if any) house effects."""
    m = pool.m.values - pool["pop"].map(s["pop_lean"]).fillna(0).values - s["sponsor_shift"] * pool.sg.values
    if s.get("house") is not None:
        m = m - pool.house.values
    return m


def weights(pool, t, s):
    age = (t - pool.end).dt.days.values
    w = 0.5 ** (age / s["half_life"]) * np.sqrt(np.minimum(pool.n.values, 3000) / 600)
    w = w * pool["pop"].map(s["pop_w"]).fillna(0.7).values
    k = pool.groupby("pkey").pkey.transform("size").values
    return w / np.sqrt(k)


def average(pool, t, s, exclude=None):
    """Weighted average at t of pool (polls ended before t), optionally without one pollster."""
    pool = pool[pool.end < t]
    if exclude is not None:
        pool = pool[pool.pkey != exclude]
    if not len(pool):
        return np.nan
    return float(np.average(adjusted(pool, s), weights=weights(pool, t, s)))


def targets(q):
    """The fixed target set: (poll, week start t). Same for every candidate."""
    rows = []
    for (c, g), d in q.groupby(["cycle", "geo"]):
        e = d.election.iloc[0]
        for k in range(1, WEEKS + 1):
            t = e - pd.Timedelta(days=7 * k)
            tg = d[(d.end >= t) & (d.end < t + pd.Timedelta(days=7)) & d["pop"].isin(["lv", "v"]) & (d.sg == 0)]
            prior = d[(d.end < t) & (d.end >= t - pd.Timedelta(days=ELIG_DAYS))]
            for i, r in tg.iterrows():
                if (prior.pkey != r.pkey).any():
                    rows.append({"idx": i, "cycle": c, "geo": g, "t": t, "week": k, "pkey": r.pkey, "y": r.m,
                                 "n": r.n, "dte": r.dte})
    return pd.DataFrame(rows)


def predict(q, tg, s):
    """Prediction for every target: the average at its week's start without its own pollster."""
    out = np.empty(len(tg))
    for (c, g, t), idx in tg.groupby(["cycle", "geo", "t"]).groups.items():
        d = q[(q.cycle == c) & (q.geo == g) & (q.end < t)]
        if s.get("house") is not None:
            d = d.assign(house=s["house"](c, t, d))
        a, w = adjusted(d, s), weights(d, t, s)
        S, W = (a * w).sum(), w.sum()
        by = pd.DataFrame({"p": d.pkey.values, "aw": a * w, "w": w}).groupby("p").sum()
        for j in idx:
            pk = tg.at[j, "pkey"]
            sp, wp = (by.at[pk, "aw"], by.at[pk, "w"]) if pk in by.index else (0.0, 0.0)
            out[tg.index.get_loc(j)] = (S - sp) / (W - wp)
    return out


def score(tg, pred):
    t = tg.assign(pred=pred, se=(pred - tg.y) ** 2)
    pv = (1 - (t.y / 100) ** 2) / t.n * 1e4        # sampling variance of a two-party margin, points squared
    t = t.assign(samp=pv)
    by_cycle = t.groupby("cycle").agg(targets=("se", "size"), mse=("se", "mean"), sampling=("samp", "mean"))
    by_cycle["beyond_sampling"] = by_cycle.mse - by_cycle.sampling
    bands = {f"{a}-{b}": t[t.dte.between(a, b)].groupby("cycle").se.mean().mean() for a, b in BANDS}
    nat = t[t.geo == "US"].groupby("cycle").se.mean().mean()
    sta = t[t.geo != "US"].groupby("cycle").se.mean().mean()
    return t, {"loss": float(by_cycle.mse.mean()), "by_cycle": by_cycle.round(3).to_dict("index"),
               "by_band": {k: round(float(v), 3) for k, v in bands.items()},
               "national": round(float(nat), 3), "states": round(float(sta), 3), "targets": int(len(t))}


# ---------------- checks ----------------
def checks():
    try:
        load(cycles=(2020, 2024))
        raise SystemExit("FAIL: 2024 was not refused")
    except AssertionError:
        print("2024 refused at load: PASS")
    q = load()
    rng = np.random.default_rng(0)
    bad = 0
    for _ in range(40):
        r = q.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        t = r.end - pd.Timedelta(days=int(rng.integers(1, 30)))
        d = q[(q.cycle == r.cycle) & (q.geo == r.geo)]
        a = average(d, t, BASE)
        d2 = d.copy()
        d2.loc[d2.end >= t, "m"] += 50
        b = average(d2, t, BASE)
        bad += not (np.isnan(a) and np.isnan(b)) and abs(a - b) > 1e-12
    print(f"leak test, 40 random places and dates (polls ending on or after t moved by 50 points): "
          f"{'PASS' if bad == 0 else f'FAIL in {bad}'}")
    import pollavg as PA
    PA.PE_EST = None
    worst = 0.0
    for _ in range(25):
        r = q.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        t = r.end + pd.Timedelta(days=1)
        d = q[(q.cycle == r.cycle) & (q.geo == r.geo) & (q.end < t)]
        rows = [({"pollster": x.pkey, "end": x.end, "sample_size": x.n, "population": x["pop"],
                  "partisan": {1: "DEM", -1: "REP"}.get(x.sg, "")}, x.m) for _, x in d.iterrows()]
        PA.ASOF = t
        ref = PA.weighted_avg(rows, BASE["half_life"], shift=BASE["sponsor_shift"])["avg"]
        worst = max(worst, abs(ref - average(d, t, BASE)))
    print(f"parity with pollavg.weighted_avg (25 random places and dates): largest gap {worst:.2e} "
          f"{'PASS' if worst < 1e-9 else 'FAIL'}")


# ---------------- candidates ----------------
def run(name, s, tg=None, q=None, write=True):
    q = load() if q is None else q
    tg = targets(q) if tg is None else tg
    t, res = score(tg, predict(q, tg, s))
    res["settings"] = {k: v for k, v in s.items() if k != "house"} | {"house": s.get("house_desc")}
    if write:
        (OUT / f"pres_nowcast_{name}.json").write_text(json.dumps(res, indent=1, default=float))
    return t, res


def report(name, res, base=None):
    print(f"\n== {name}: loss {res['loss']:.3f} (targets {res['targets']}); national {res['national']}, "
          f"states {res['states']}; by band {res['by_band']}")
    bc = pd.DataFrame(res["by_cycle"]).T
    if base is not None:
        bc["baseline_mse"] = pd.DataFrame(base["by_cycle"]).T.mse
        bc["gain"] = bc.baseline_mse - bc.mse
    print(bc.to_string())


LAMBDAS = (2, 5, 10, 20, 50)
FLIPS = 2000


def run_per_cycle(q, tg, settings_by_cycle):
    """Predictions with settings that differ by held-out cycle."""
    pred = np.empty(len(tg))
    for c, s in settings_by_cycle.items():
        sub = tg[tg.cycle == c]
        pred[tg.index.get_indexer(sub.index)] = predict(q, sub, s)
    return pred


def cycle_losses(tg, pred):
    return tg.assign(se=(pred - tg.y) ** 2).groupby("cycle").se.mean()


def loo_pick(table):
    """table: rows = grid values, columns = cycles (loss). For each cycle, the value best on the other cycles."""
    return {c: table.drop(columns=c).mean(axis=1).idxmin() for c in table.columns}


def gaps(q, s=BASE, lv_only=False):
    """Each poll's margin minus the average of the other pollsters in the same place as of its end date (polls that
    ended before it). Default: baseline adjustments on both sides. lv_only: the poll's raw margin against an average
    of likely-voter polls only."""
    out = pd.Series(np.nan, index=q.index)
    for _, d in q.groupby(["cycle", "geo"]):
        ref = d[d["pop"].isin(["lv", "v"])] if lv_only else d
        own = d.m.values if lv_only else adjusted(d, s)
        for j, (i, r) in enumerate(d.iterrows()):
            out[i] = own[j] - average(ref, r.end, s, exclude=r.pkey)
    return out


def house_fn(q, gap, lam):
    """House effect at date t for the polls of d (one cycle): the shrunk mean of each pollster's earlier gaps."""
    cache = {}
    dq = q.assign(gap=gap).dropna(subset=["gap"])

    def f(c, t, d):
        if (c, t) not in cache:
            e = dq[(dq.cycle == c) & (dq.end < t)].groupby("pkey").gap.agg(["mean", "size"])
            cache[(c, t)] = e["mean"] * e["size"] / (e["size"] + lam)
        return d.pkey.map(cache[(c, t)]).fillna(0.0).values
    return f


def adoption(tg, base_pred, cand_pred, seed=0):
    """The stage 1 rule (ELECTORAL_COLLEGE.md, section 11)."""
    t = tg.assign(sb=(base_pred - tg.y) ** 2, sc=(cand_pred - tg.y) ** 2)
    lb, lc = t.groupby("cycle").sb.mean(), t.groupby("cycle").sc.mean()
    gain = float(lb.mean() - lc.mean())
    better = int((lc < lb).sum())
    late = t[t.dte.between(91, 161)]
    late_gain = float(late.groupby("cycle").sb.mean().mean() - late.groupby("cycle").sc.mean().mean())
    u = t.assign(d=t.sb - t.sc).groupby(["cycle", "geo"]).agg(d=("d", "mean"), n=("d", "size")).reset_index()
    u["w"] = u.n / u.groupby("cycle").n.transform("sum") / u.cycle.nunique()
    stat = float((u.w * u.d).sum())
    flips = np.random.default_rng(seed).choice([-1.0, 1.0], size=(FLIPS, len(u)))
    null = flips @ (u.w * u.d).values
    pval = float((np.sum(null >= stat) + 1) / (FLIPS + 1))
    ok = gain > 0 and better >= 4 and pval < 0.05 and late_gain >= 0
    return {"gain": round(gain, 3), "cycles_better": better, "p_signflip": round(pval, 4),
            "gain_91_161": round(late_gain, 3), "adopted": bool(ok),
            "by_cycle": {int(c): {"baseline": round(float(lb[c]), 3), "candidate": round(float(lc[c]), 3)}
                         for c in lb.index}}


def paired_2020():
    """2020 polls that asked both likely and registered voters (head-to-head): mean LV minus RV margin."""
    p = pd.read_csv(INTERIM / "president_general_polls.csv", low_memory=False)
    p = p[(p.cycle == 2020) & ~p.presumptive]
    p["m"] = 100 * (p.d_pct - p.r_pct) / (p.d_pct + p.r_pct)
    p = p[p.head_to_head.fillna(False).astype(bool)]
    x = p.groupby(["poll_id", "population"]).m.mean().unstack().dropna(subset=["lv", "rv"])
    d = x.lv - x.rv
    return {"polls": int(len(d)), "mean_lv_minus_rv": round(float(d.mean()), 3),
            "se": round(float(d.std() / np.sqrt(len(d))), 3)}


def candidate(name, q, tg):
    if name == "half_life":
        table = {}
        for h in HALF_LIVES:
            table[h] = cycle_losses(tg, predict(q, tg, dict(BASE, half_life=float(h))))
            print(f"  half-life {h}: " + ", ".join(f"{c} {v:.2f}" for c, v in table[h].items()), flush=True)
        table = pd.DataFrame(table).T
        pick = loo_pick(table)
        info = {"grid": {int(h): {int(c): round(float(v), 3) for c, v in r.items()} for h, r in table.iterrows()},
                "picked": {int(c): int(h) for c, h in pick.items()}}
        return run_per_cycle(q, tg, {c: dict(BASE, half_life=float(h)) for c, h in pick.items()}), info
    if name == "house":
        gp = gaps(q)
        table = {}
        for lam in LAMBDAS:
            table[lam] = cycle_losses(tg, predict(q, tg, dict(BASE, house=house_fn(q, gp, lam))))
            print(f"  lambda {lam}: " + ", ".join(f"{c} {v:.2f}" for c, v in table[lam].items()), flush=True)
        table = pd.DataFrame(table).T
        pick = loo_pick(table)
        g = q.assign(gap=gp).dropna(subset=["gap"])
        info = {"grid": {int(k): {int(c): round(float(v), 3) for c, v in r.items()} for k, r in table.iterrows()},
                "picked": {int(c): int(k) for c, k in pick.items()},
                "gap_sd_by_cycle": {int(c): round(float(v), 2) for c, v in g.groupby("cycle").gap.std().items()}}
        return run_per_cycle(q, tg, {c: dict(BASE, house=house_fn(q, gp, lam)) for c, lam in pick.items()}), info
    if name == "rv_lean":
        gp = gaps(q, lv_only=True)
        g = q.assign(gap=gp)[q["pop"].isin(["rv", "a"])].dropna(subset=["gap"])
        per = g.groupby("cycle").gap.agg(["mean", "size"])
        corr = {c: float(per.drop(index=c)["mean"].mean()) for c in CYCLES}
        info = {"rv_minus_lv_by_cycle": {int(c): {"mean": round(float(r["mean"]), 3), "polls": int(r["size"])}
                                         for c, r in per.iterrows()},
                "correction_used": {int(c): round(v, 3) for c, v in corr.items()},
                "paired_2020": paired_2020()}
        return run_per_cycle(q, tg, {c: dict(BASE, pop_lean=dict(BASE["pop_lean"], rv=v, a=v))
                                     for c, v in corr.items()}), info
    raise SystemExit(f"unknown candidate {name}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    if cmd == "checks":
        checks()
    elif cmd == "baseline":
        q = load()
        tg = targets(q)
        print(f"polls {len(q)} ({q.groupby('cycle').size().to_dict()}); targets {len(tg)} "
              f"({tg.groupby('cycle').size().to_dict()})")
        _, res = run("baseline", BASE, tg, q)
        report("baseline", res)
    else:
        q = load()
        tg = targets(q)
        base_pred = predict(q, tg, BASE)
        pred, info = candidate(cmd, q, tg)
        _, sc = score(tg, pred)
        res = adoption(tg, base_pred, pred) | {"score": sc, "info": info}
        (OUT / f"pres_nowcast_{cmd}.json").write_text(json.dumps(res, indent=1, default=float))
        print(f"\n== {cmd}: " + json.dumps({k: v for k, v in res.items() if k not in ("info", "score")}))
        print("score: " + json.dumps({k: sc[k] for k in ("loss", "national", "states", "by_band")}))
        print("info: " + json.dumps(info, default=float))
