"""Stage 1 of EC-2: the presidential nowcast, scored by how well the average predicts the next polls.
No results are used. ELECTORAL_COLLEGE.md, section 11, "Stage 1: pre-registration", is the protocol this follows.

Test bed: president_general_polls.csv, 2004 to 2020, states, Maine and Nebraska districts, and the nation. 2000 is
out (late polls only, no population field). 2024 is refused at load (held out of everything in section 11).

Per poll, one question: head-to-head if the poll has one, then likely voters, voters, registered voters, adults.
A poll's date is its last field day (the middle where the last is missing: 2004 national). A pollster is the firm
that fielded the poll (firm_key), so a firm polling for several sponsors counts once.

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
      python src/model/pres_nowcast.py <candidate>     (round 1: half_life | house | rv_lean; round 2: count_decay | trend
                                                    | house_week | house_week_corrected | total_error | method
                                                    | no_rv)
      python src/model/pres_nowcast.py checks2         (round 2: target count and a leak test per candidate)
      python src/model/pres_nowcast.py density         (diagnostic: the half-life grid by poll density)
Writes data/processed/pres_nowcast_<name>.json
"""
import json
import re
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


STOP = {"the", "inc", "llc", "corporation", "corp", "co", "and", "of"}


def firm_key(name, poll_id):
    """The firm that fielded the poll: the last part of a sponsor/firm name ("KATU-TV Portland/SurveyUSA",
    "Fox News/Rasmussen Reports/Pulse Opinion Research"), lower case, without notes in brackets, punctuation or
    filler words, its words sorted ("Mason-Dixon Polling & Research" = "Mason-Dixon Research & Polling"). A poll with
    no pollster name gets a key of its own."""
    if not isinstance(name, str) or not name.strip():
        return f"unknown-{poll_id}"
    s = re.sub(r"\(.*?\)", " ", name.split("/")[-1].lower())
    words = sorted(set(re.sub(r"[^a-z0-9 ]", " ", s.replace("&", " ")).split()) - STOP)
    return " ".join(words) or name.lower()


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
    q["pkey"] = [firm_key(n, i) for n, i in zip(q.pollster, q.poll_id)]
    q["n"] = q.n.fillna(600)
    q["sg"] = np.where(q.partisan == "DEM", 1, np.where(q.partisan == "REP", -1, 0))
    return q.dropna(subset=["m"]).sort_values(["cycle", "geo", "end"]).reset_index(drop=True)


def adjusted(pool, s):
    """Each pool poll's margin after the population lean, the sponsor shift and (if any) house effects and the
    national trend (round 2, candidates 5 and 6; columns set by predict)."""
    m = pool.m.values - pool["pop"].map(s["pop_lean"]).fillna(0).values - s["sponsor_shift"] * pool.sg.values
    if s.get("house") is not None:
        m = m - pool.house.values
    if s.get("trend") is not None:
        m = m + pool.trend.values
    return m


def count_decay(pool, H):
    """Round 2, candidate 4: weight halves with every H firms that published a newer poll of the place (a firm counts
    once however many newer polls it has; polls ending the same day do not count each other)."""
    r = np.zeros(len(pool))
    seen = set()
    ends = pool.end.values
    firms = pool.pkey.values
    for d in np.unique(ends)[::-1]:
        at = ends == d
        r[at] = len(seen)
        seen.update(firms[at])
    return 0.5 ** (r / H)


def weights(pool, t, s):
    if s.get("count_decay") is not None:
        w = count_decay(pool, s["count_decay"])
    else:
        age = (t - pool.end).dt.days.values
        w = 0.5 ** (age / s["half_life"])
    if s.get("size_tau2") is not None:                  # round 2, candidate 7: total expected error
        w = w / (s["size_tau2"] + 1e4 / pool.n.values)
    else:
        w = w * np.sqrt(np.minimum(pool.n.values, 3000) / 600)
    if s.get("method_w") is not None:                   # round 2, candidate 8
        w = w * pool.method.map(s["method_w"]).fillna(1.0).values
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


def firm_readings(e, s):
    """Round 3, candidate 10: each firm's latest reading (its polls on its latest end date, weighted mean of the
    adjusted margins) with its weight (mean sample-size x population weight) and date, newest first."""
    w0 = np.sqrt(np.minimum(e.n.values, 3000) / 600) * e["pop"].map(s["pop_w"]).fillna(0.7).values
    a = adjusted(e, s)
    x = pd.DataFrame({"pkey": e.pkey.values, "end": e.end.values, "aw": a * w0, "w": w0})
    x = x[x.end.values == x.groupby("pkey").end.transform("max").values]
    r = x.groupby("pkey").agg(end=("end", "first"), aw=("aw", "sum"), w=("w", "sum"), cnt=("w", "size"))
    r["m"] = r.aw / r.w
    r["wt"] = r.w / r.cnt
    return r.sort_values("end", ascending=False)


def latest_k_value(r, k):
    if len(r) > k:
        r = r[r.end >= r.end.iloc[k - 1]]
    return float(np.average(r.m, weights=r.wt))


def predict(q, tg, s):
    """Prediction for every target: the average at its week's start without its own pollster."""
    out = np.empty(len(tg))
    for (c, g, t), idx in tg.groupby(["cycle", "geo", "t"]).groups.items():
        d = q[(q.cycle == c) & (q.geo == g) & (q.end < t)]
        if s.get("latest_k") is not None:               # round 3, candidate 10
            for j in idx:
                e = d[d.pkey != tg.at[j, "pkey"]]
                out[tg.index.get_loc(j)] = latest_k_value(firm_readings(e, s), int(s["latest_k"]))
            continue
        if s.get("dens_hl") is not None:                # round 3, candidate 11
            hd, hs, D = s["dens_hl"]
            for j in idx:
                e = d[d.pkey != tg.at[j, "pkey"]]
                k = int((e.end >= t - pd.Timedelta(days=30)).sum())
                s2 = dict(s, half_life=float(hd if k >= D else hs))
                out[tg.index.get_loc(j)] = np.average(adjusted(e, s2), weights=weights(e, t, s2))
            continue
        if s.get("house") is not None and getattr(s["house"], "per_target", False):
            for j in idx:                               # effects estimated again without the target's firm
                pk = tg.at[j, "pkey"]
                e = d[d.pkey != pk]
                e = e.assign(house=s["house"](c, t, e, pk))
                out[tg.index.get_loc(j)] = np.average(adjusted(e, s), weights=weights(e, t, s))
            continue
        if s.get("trend") is not None and getattr(s["trend"], "per_target", False):
            for j in idx:                               # national line again without the target's firm
                pk = tg.at[j, "pkey"]
                e = d[d.pkey != pk]
                e = e.assign(trend=s["trend"](c, t, e, pk))
                if s.get("house") is not None:
                    e = e.assign(house=s["house"](c, t, e))
                out[tg.index.get_loc(j)] = np.average(adjusted(e, s), weights=weights(e, t, s))
            continue
        if s.get("house") is not None:
            d = d.assign(house=s["house"](c, t, d))
        if s.get("trend") is not None:
            d = d.assign(trend=s["trend"](c, t, d))
        if s.get("count_decay") is not None:            # weights depend on the firms present: no shortcut
            for j in idx:
                e = d[d.pkey != tg.at[j, "pkey"]]
                out[tg.index.get_loc(j)] = np.average(adjusted(e, s), weights=weights(e, t, s))
            continue
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


# ---------------- round 2 builders ----------------
COUNT_H = (1, 2, 4, 8, 16)
TREND_NAT_HL = (7, 14, 30)
TREND_STATE_HL = (60, 90, 180)
SIZE_S = (0.0, 0.5, 1.0, 2.0)
WEEK_DAYS = 7
MIN_FIRMS = 5


def trend_fn(q, h_nat, corrected=False):
    """Candidate 5: shift for each state or district poll = national average at t minus at the poll's end date.
    The national average is the baseline's (half-life h_nat) from national polls that ended before each date.
    corrected: the national line leaves out the target's own firm (called per target, with its firm key)."""
    nat = {c: d for c, d in q[q.geo == "US"].groupby("cycle")}
    nat_firms = {c: set(d.pkey) for c, d in nat.items()}
    s_nat = dict(BASE, half_life=float(h_nat))
    cache = {}

    def N(c, d, ex=None):
        if (c, d, ex) not in cache:
            cache[(c, d, ex)] = average(nat[c], d, s_nat, exclude=ex) if c in nat else np.nan
        return cache[(c, d, ex)]

    def f(c, t, d, pk=None):
        if not len(d) or d.geo.iloc[0] == "US":
            return np.zeros(len(d))
        ex = pk if (pk is not None and pk in nat_firms.get(c, ())) else None
        now = N(c, t, ex)
        then = np.array([N(c, e + pd.Timedelta(days=1), ex) for e in d.end])
        return np.nan_to_num(now - then, nan=0.0)
    f.per_target = corrected
    return f


def house_week_fn(q, corrected=False):
    """Candidate 6: house effects from gaps against other firms' polls of the same place within 7 days either side,
    using only polls that ended before t; shrinkage estimated within the cycle as of t.
    corrected=True (the version of record): the effects are estimated again without the target's own firm, which
    otherwise reaches its prediction through the other firms' gaps; and in each same-week mean a firm's weight is
    divided by the square root of its polls there, as the baseline's weights are."""
    s0 = dict(BASE)
    pairs = []
    for (c, g), d in q.groupby(["cycle", "geo"]):
        if len(d) < 2:
            continue
        a = adjusted(d, s0)
        w0 = np.sqrt(np.minimum(d.n.values, 3000) / 600) * d["pop"].map(s0["pop_w"]).fillna(0.7).values
        e = d.end.values.astype("datetime64[D]").astype(int)
        f = d.pkey.to_numpy(dtype=object)
        I, J = np.where((np.abs(e[:, None] - e[None, :]) <= WEEK_DAYS) & (f[:, None] != f[None, :]))
        pairs.append(pd.DataFrame({"cycle": c, "i": d.index.values[I], "firm": f[I], "m_i": a[I], "end_i": e[I],
                                   "end_j": e[J], "firm_j": f[J], "a_j": a[J], "wm_j": w0[J] * a[J], "w_j": w0[J]}))
    P = pd.concat(pairs, ignore_index=True)
    P = {c: x for c, x in P.groupby("cycle")}
    cache = {}

    def effects(c, t, excl=None):
        tt = np.datetime64(t.date()).astype("datetime64[D]").astype(int)
        x = P.get(c)
        if x is None:
            return pd.Series(dtype=float)
        x = x[(x.end_i < tt) & (x.end_j < tt)]
        if corrected:
            if excl is not None:
                x = x[(x.firm != excl) & (x.firm_j != excl)]
            k = x.groupby(["i", "firm_j"]).i.transform("size").values
            x = x.assign(w_j=x.w_j.values / np.sqrt(k))
            x = x.assign(wm_j=x.w_j.values * x.a_j.values)
        g = x.groupby("i").agg(firm=("firm", "first"), m=("m_i", "first"), wm=("wm_j", "sum"), w=("w_j", "sum"))
        g["gap"] = g.m - g.wm / g.w
        fs = g.groupby("firm").gap.agg(["mean", "size", "var"])
        two = fs[fs["size"] >= 2]
        if len(two) < MIN_FIRMS:
            return pd.Series(0.0, index=fs.index)
        sigma2 = float(((two["size"] - 1) * two["var"]).sum() / (two["size"] - 1).sum())
        tau2 = float(two["mean"].var(ddof=1) - (sigma2 / two["size"]).mean())
        if tau2 <= 0:
            return pd.Series(0.0, index=fs.index)
        lam = sigma2 / tau2
        return fs["mean"] * fs["size"] / (fs["size"] + lam)

    def fn(c, t, d, excl=None):
        key = (c, t, excl if corrected else None)
        if key not in cache:
            cache[key] = effects(c, t, excl if corrected else None)
        return d.pkey.map(cache[key]).fillna(0.0).values
    fn.per_target = corrected
    return fn


def method_class(s):
    if not isinstance(s, str) or not s.strip():
        return "unknown"
    cls = set()
    for part in s.split("/"):
        p = part.strip().lower()
        if p == "live phone":
            cls.add("live phone")
        elif p == "ivr":
            cls.add("ivr")
        elif p == "probability panel":
            cls.add("probability panel")
        elif p in ("text", ""):
            continue                                    # text alone or with IVR: folded into its partner
        elif "online" in p or "text-to-web" in p or p == "email":
            cls.add("online")
        else:
            cls.add("other")
    if not cls:
        return "ivr" if "text" in s.lower() else "unknown"
    return cls.pop() if len(cls) == 1 else "mixed"


def attach_methods(q):
    """Each firm's main method in each cycle, from FiveThirtyEight's late-poll file (pollster, cycle and method
    columns only; the file's results columns are not read)."""
    import glob
    f = sorted(glob.glob(str(ROOT / "data/raw/538_github/*/raw_polls.csv")))[-1]
    r = pd.read_csv(f, usecols=["cycle", "type_simple", "pollster", "methodology"], low_memory=False)
    r = r[(r.type_simple == "Pres-G") & r.cycle.isin(CYCLES)]
    assert 2024 not in set(r.cycle)
    r["pkey"] = [firm_key(n, i) for n, i in zip(r.pollster, range(len(r)))]
    r["cls"] = r.methodology.map(method_class)
    main = r[r.cls != "unknown"].groupby(["cycle", "pkey"]).cls.agg(lambda x: x.value_counts().index[0])
    return q.assign(method=[main.get((c, k), "unknown") for c, k in zip(q.cycle, q.pkey)])


def poll_density(q):
    """Polls of the same place that ended in the 30 days before each poll."""
    out = pd.Series(0, index=q.index)
    for _, d in q.groupby(["cycle", "geo"]):
        e = d.end.values.astype("datetime64[D]").astype(int)
        out[d.index] = ((e[None, :] < e[:, None]) & (e[None, :] >= e[:, None] - 30)).sum(axis=1)
    return pd.cut(out, [-1, 3, 9, 10 ** 6], labels=["3 or fewer", "4-9", "10+"]).astype(str)


def method_weights(q, gp, held_out):
    """Candidate 8: weight of method k = spread of all gaps / spread of method k's gaps (mean squared gap), each
    within a density class, combined in proportion to method k's polls; other cycles only."""
    x = q.assign(gap=gp)
    x = x[(x.cycle != held_out) & x.gap.notna()]
    allc = x.groupby("dens").gap.apply(lambda v: (v ** 2).mean())
    w = {}
    for k, d in x[x.method != "unknown"].groupby("method"):
        byc = d.groupby("dens").gap.agg(lambda v: (v ** 2).mean())
        n = d.groupby("dens").size()
        w[k] = float((n * allc[n.index]).sum() / (n * byc).sum())
    return w


def size_tau2(q, gp, held_out):
    """Candidate 7: non-sampling variance = intercept of squared gaps on 10,000/n, mean over the other cycles."""
    x = q.assign(gap=gp).dropna(subset=["gap"])
    a = []
    for c, d in x[x.cycle != held_out].groupby("cycle"):
        v = 1e4 / d.n.values
        b, a0 = np.polyfit(v, d.gap.values ** 2, 1)
        a.append(a0)
    return max(float(np.mean(a)), 0.0)


def leak_check(q, tg, s_builder, label, n=15, seed=1):
    """Moving every poll that ends on or after t (all places, same cycle) by 50 points leaves predictions unchanged.
    s_builder(q) -> settings, rebuilt on the moved polls."""
    rng = np.random.default_rng(seed)
    groups = list(tg.groupby(["cycle", "geo", "t"]).groups.items())
    bad = 0
    for k in rng.choice(len(groups), size=n, replace=False):
        (c, g, t), idx = groups[k]
        sub = tg.loc[idx]
        a = predict(q, sub, s_builder(q))
        q2 = q.copy()
        q2.loc[(q2.cycle == c) & (q2.end >= t), "m"] += 50
        b = predict(q2, sub, s_builder(q2))
        bad += int(np.max(np.abs(a - b)) > 1e-9)
    print(f"leak test, {label}: {'PASS' if bad == 0 else f'FAIL in {bad} of {n}'}", flush=True)
    return bad == 0


def own_firm_check(q, tg, s_builder, label, n=20, seed=2):
    """A target's own firm must not reach its prediction: moving all that firm's polls in the cycle (every place,
    every date) by 50 points leaves the target's prediction unchanged."""
    rng = np.random.default_rng(seed)
    bad = 0
    for j in rng.choice(tg.index.values, size=n, replace=False):
        sub = tg.loc[[j]]
        c, pk = sub.cycle.iloc[0], sub.pkey.iloc[0]
        a = predict(q, sub, s_builder(q))
        q2 = q.copy()
        q2.loc[(q2.cycle == c) & (q2.pkey == pk), "m"] += 50
        b = predict(q2, sub, s_builder(q2))
        bad += int(np.max(np.abs(a - b)) > 1e-9)
    print(f"own-firm test, {label}: {'PASS' if bad == 0 else f'FAIL in {bad} of {n}'}", flush=True)
    return bad == 0

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
    if name == "count_decay":
        table = {}
        for h in COUNT_H:
            table[h] = cycle_losses(tg, predict(q, tg, dict(BASE, count_decay=float(h))))
            print(f"  H {h}: " + ", ".join(f"{c} {v:.2f}" for c, v in table[h].items()), flush=True)
        table = pd.DataFrame(table).T
        pick = loo_pick(table)
        info = {"grid": {int(h): {int(c): round(float(v), 3) for c, v in r.items()} for h, r in table.iterrows()},
                "picked": {int(c): int(h) for c, h in pick.items()}}
        return run_per_cycle(q, tg, {c: dict(BASE, count_decay=float(h)) for c, h in pick.items()}), info
    if name == "trend":
        table = {}
        fns = {hn: trend_fn(q, hn) for hn in TREND_NAT_HL}
        for hn in TREND_NAT_HL:
            for hs in TREND_STATE_HL:
                table[(hn, hs)] = cycle_losses(tg, predict(q, tg, dict(BASE, half_life=float(hs), trend=fns[hn])))
                print(f"  national {hn}, state {hs}: " + ", ".join(f"{c} {v:.2f}" for c, v in table[(hn, hs)].items()),
                      flush=True)
        table = pd.DataFrame(table).T
        pick = loo_pick(table)
        info = {"grid": {f"{hn}/{hs}": {int(c): round(float(v), 3) for c, v in r.items()}
                         for (hn, hs), r in table.iterrows()},
                "picked": {int(c): f"{k[0]}/{k[1]}" for c, k in pick.items()}}
        return run_per_cycle(q, tg, {c: dict(BASE, half_life=float(k[1]), trend=fns[k[0]])
                                     for c, k in pick.items()}), info
    if name == "trend_corrected":
        # pre-registration: national polls are not moved and the nation's own average is the baseline's, so the
        # state half-life applies to states and districts only (the first run applied it to the nation too)
        nat = (tg.geo == "US").values
        base_nat = predict(q, tg[nat], BASE)

        def nat_base(pred):
            pred = pred.copy()
            pred[nat] = base_nat
            return pred
        table = {}
        fns = {hn: trend_fn(q, hn, corrected=True) for hn in TREND_NAT_HL}
        for hn in TREND_NAT_HL:
            for hs in TREND_STATE_HL:
                table[(hn, hs)] = cycle_losses(tg, nat_base(
                    predict(q, tg, dict(BASE, half_life=float(hs), trend=fns[hn]))))
                print(f"  national {hn}, state {hs}: " + ", ".join(f"{c} {v:.2f}" for c, v in table[(hn, hs)].items()),
                      flush=True)
        table = pd.DataFrame(table).T
        pick = loo_pick(table)
        info = {"grid": {f"{hn}/{hs}": {int(c): round(float(v), 3) for c, v in r.items()}
                         for (hn, hs), r in table.iterrows()},
                "picked": {int(c): f"{k[0]}/{k[1]}" for c, k in pick.items()},
                "note": "national line without the target's own firm; grid picked again; the nation's average "
                        "is the baseline's"}
        return nat_base(run_per_cycle(q, tg, {c: dict(BASE, half_life=float(k[1]), trend=fns[k[0]])
                                              for c, k in pick.items()})), info
    if name == "latest_k":
        allk = {k: np.empty(len(tg)) for k in LATEST_K}
        for (c, g, t), idx in tg.groupby(["cycle", "geo", "t"]).groups.items():
            d = q[(q.cycle == c) & (q.geo == g) & (q.end < t)]
            for j in idx:
                r = firm_readings(d[d.pkey != tg.at[j, "pkey"]], BASE)
                for k in LATEST_K:
                    allk[k][tg.index.get_loc(j)] = latest_k_value(r, k)
        table = pd.DataFrame({k: cycle_losses(tg, v) for k, v in allk.items()}).T
        for k, r in table.iterrows():
            print(f"  k {k}: " + ", ".join(f"{c} {v:.2f}" for c, v in r.items()), flush=True)
        pick = loo_pick(table)
        pred = run_per_cycle(q, tg, {c: dict(BASE, latest_k=int(k)) for c, k in pick.items()})
        fast = np.empty(len(tg))
        for c, k in pick.items():
            m = (tg.cycle == c).values
            fast[m] = allk[k][m]
        assert np.allclose(pred, fast, atol=1e-9), "grid path and predict path differ"
        info = {"grid": {int(k): {int(c): round(float(v), 3) for c, v in r.items()} for k, r in table.iterrows()},
                "picked": {int(c): int(k) for c, k in pick.items()},
                "edge_picks": sorted({int(k) for k in pick.values() if k in (min(LATEST_K), max(LATEST_K))})}
        return pred, info
    if name == "dens_hl":
        hls = sorted(set(DENS_HD) | set(DENS_HS))
        ph = {h: predict(q, tg, dict(BASE, half_life=float(h))) for h in hls}
        cnt = np.array([int(((q.cycle == r.cycle) & (q.geo == r.geo) & (q.end < r.t)
                             & (q.end >= r.t - pd.Timedelta(days=30)) & (q.pkey != r.pkey)).sum())
                        for r in tg.itertuples()])
        table, preds = {}, {}
        for hd in DENS_HD:
            for hs in DENS_HS:
                for D in DENS_D:
                    preds[(hd, hs, D)] = np.where(cnt >= D, ph[hd], ph[hs])
                    table[(hd, hs, D)] = cycle_losses(tg, preds[(hd, hs, D)])
                    print(f"  dense {hd}, sparse {hs}, D {D}: "
                          + ", ".join(f"{c} {v:.2f}" for c, v in table[(hd, hs, D)].items()), flush=True)
        table = pd.DataFrame(table).T
        pick = loo_pick(table)
        pred = run_per_cycle(q, tg, {c: dict(BASE, dens_hl=k) for c, k in pick.items()})
        fast = np.empty(len(tg))
        for c, k in pick.items():
            m = (tg.cycle == c).values
            fast[m] = preds[k][m]
        assert np.allclose(pred, fast, atol=1e-9), "grid path and predict path differ"
        edges = []
        for c, (hd, hs, D) in pick.items():
            if hd in (min(DENS_HD), max(DENS_HD)) or hs in (min(DENS_HS), max(DENS_HS)):
                edges.append(int(c))
        info = {"grid": {f"{hd}/{hs}/{D}": {int(c): round(float(v), 3) for c, v in r.items()}
                         for (hd, hs, D), r in table.iterrows()},
                "picked": {int(c): f"{k[0]}/{k[1]}/{k[2]}" for c, k in pick.items()},
                "cycles_with_an_edge_pick": edges,
                "share_dense_at_D": {int(D): round(float((cnt >= D).mean()), 3) for D in DENS_D}}
        return pred, info
    if name == "house_week":
        return predict(q, tg, dict(BASE, house=house_week_fn(q))), {"note": "no grid; shrinkage within cycle; "
                                                                    "first version (target firm in other gaps)"}
    if name == "house_week_corrected":
        return predict(q, tg, dict(BASE, house=house_week_fn(q, corrected=True))), {
            "note": "no grid; shrinkage within cycle; effects without the target's firm; firm weight / sqrt(polls)"}
    if name in ("total_error", "method"):
        gp = gaps(q)
        if name == "total_error":
            tau = {c: size_tau2(q, gp, c) for c in CYCLES}
            table = {}
            for sv in SIZE_S:
                pred = run_per_cycle(q, tg, {c: dict(BASE, size_tau2=sv * tau[c]) for c in CYCLES})
                table[sv] = cycle_losses(tg, pred)
                print(f"  s {sv}: " + ", ".join(f"{c} {v:.2f}" for c, v in table[sv].items()), flush=True)
            table = pd.DataFrame(table).T
            pick = loo_pick(table)
            info = {"tau2": {int(c): round(v, 2) for c, v in tau.items()},
                    "grid": {float(k): {int(c): round(float(v), 3) for c, v in r.items()} for k, r in table.iterrows()},
                    "picked": {int(c): float(k) for c, k in pick.items()}}
            return run_per_cycle(q, tg, {c: dict(BASE, size_tau2=k * tau[c]) for c, k in pick.items()}), info
        qm = attach_methods(q)
        qm["dens"] = poll_density(qm)
        mw = {c: method_weights(qm, gp, c) for c in CYCLES}
        cov = qm.groupby("cycle").method.apply(lambda v: round(float((v != "unknown").mean()), 3))
        info = {"weights": {int(c): {k: round(v, 3) for k, v in w.items()} for c, w in mw.items()},
                "coverage": {int(c): v for c, v in cov.items()},
                "polls_by_method": qm.groupby(["cycle", "method"]).size().unstack(fill_value=0).to_dict("index")}
        return run_per_cycle(qm, tg, {c: dict(BASE, method_w=mw[c]) for c in CYCLES}), info
    if name == "no_rv":
        return predict(q, tg, dict(BASE, pop_lean={k: 0.0 for k in BASE["pop_lean"]})), {"note": "nothing fitted"}
    raise SystemExit(f"unknown candidate {name}")


def half_life_by_density(q, tg):
    """Diagnostic, not a candidate: the half-life grid's loss split by the nation and by how many polls the place had
    in the 30 days before the target's week (cycles weighted equally)."""
    dens = [((q.cycle == r.cycle) & (q.geo == r.geo) & (q.end < r.t) & (q.end >= r.t - pd.Timedelta(days=30))).sum()
            for r in tg.itertuples()]
    tg = tg.assign(kind=np.where(tg.geo == "US", "nation", np.select(
        [np.array(dens) >= 10, np.array(dens) >= 4], ["state, 10+ polls", "state, 4-9 polls"], "state, 1-3 polls")))
    rows = {}
    for h in HALF_LIVES + (180, 10000):
        se = (predict(q, tg, dict(BASE, half_life=float(h))) - tg.y) ** 2
        rows[h] = tg.assign(se=se).groupby(["kind", "cycle"]).se.mean().groupby("kind").mean()
    out = pd.DataFrame(rows)
    out["targets"] = tg.groupby("kind").size()
    return out


# ---------------- who the score sees: loss by density (diagnostic) ----------------
DENS_CLASSES = ["nation", "10+", "4-9", "1-3", "0"]


def density_class(q, tg):
    """Polls of the target's place in the 30 days before its week starts, not counting the target's own firm."""
    out = []
    for r in tg.itertuples():
        if r.geo == "US":
            out.append("nation")
            continue
        k = int(((q.cycle == r.cycle) & (q.geo == r.geo) & (q.end < r.t) & (q.end >= r.t - pd.Timedelta(days=30))
                 & (q.pkey != r.pkey)).sum())
        out.append("10+" if k >= 10 else "4-9" if k >= 4 else "1-3" if k >= 1 else "0")
    return np.array(out)


def stored(name):
    return json.loads((OUT / f"pres_nowcast_{name}.json").read_text())


def rebuild_settings(q, gp=None, qm=None):
    """Per held-out cycle settings for every candidate in the table, from the stored picks (refitted where the
    stored figure is rounded: the method weights and tau2, both fitted on the other cycles)."""
    S = {"baseline": {c: dict(BASE) for c in CYCLES}}
    pk = {int(c): v for c, v in stored("half_life")["info"]["picked"].items()}
    S["half_life"] = {c: dict(BASE, half_life=float(pk[c])) for c in CYCLES}
    lam = {int(c): v for c, v in stored("house")["info"]["picked"].items()}
    hf = {l: house_fn(q, gp, l) for l in set(lam.values())}
    S["house"] = {c: dict(BASE, house=hf[lam[c]]) for c in CYCLES}
    cor = {int(c): v for c, v in stored("rv_lean")["info"]["correction_used"].items()}
    S["rv_lean"] = {c: dict(BASE, pop_lean=dict(BASE["pop_lean"], rv=cor[c], a=cor[c])) for c in CYCLES}
    pk = {int(c): v for c, v in stored("count_decay")["info"]["picked"].items()}
    S["count_decay"] = {c: dict(BASE, count_decay=float(pk[c])) for c in CYCLES}
    hw = house_week_fn(q, corrected=True)
    S["house_week_corrected"] = {c: dict(BASE, house=hw) for c in CYCLES}
    pk = {int(c): v for c, v in stored("total_error")["info"]["picked"].items()}
    S["total_error"] = {c: dict(BASE, size_tau2=pk[c] * size_tau2(q, gp, c)) for c in CYCLES}
    S["method"] = {c: dict(BASE, method_w=method_weights(qm, gp, c)) for c in CYCLES}
    S["no_rv"] = {c: dict(BASE, pop_lean={k: 0.0 for k in BASE["pop_lean"]}) for c in CYCLES}
    return S


def trend_settings(q):
    """The corrected trend at its picks, and the same state half-lives with the trend off (the control)."""
    pk = {int(c): v.split("/") for c, v in stored("trend_corrected")["info"]["picked"].items()}
    fns = {hn: trend_fn(q, int(hn), corrected=True) for hn in {v[0] for v in pk.values()}}
    return ({c: dict(BASE, half_life=float(pk[c][1]), trend=fns[pk[c][0]]) for c in CYCLES},
            {c: dict(BASE, half_life=float(pk[c][1])) for c in CYCLES})


def own_firm_check_by_cycle(q, tg, builder, label, n=20, seed=2):
    """own_firm_check for settings that differ by cycle: builder(x, c) -> settings, rebuilt on the moved polls."""
    rng = np.random.default_rng(seed)
    bad = 0
    for j in rng.choice(tg.index.values, size=n, replace=False):
        sub = tg.loc[[j]]
        c, pk = sub.cycle.iloc[0], sub.pkey.iloc[0]
        a = predict(q, sub, builder(q, c))
        q2 = q.copy()
        q2.loc[(q2.cycle == c) & (q2.pkey == pk), "m"] += 50
        b = predict(q2, sub, builder(q2, c))
        bad += int(np.max(np.abs(a - b)) > 1e-9)
    print(f"own-firm test, {label}: {'PASS' if bad == 0 else f'FAIL in {bad} of {n}'}", flush=True)
    return bad


def checks3():
    """Gates for the corrected trend (before its results are read) and the own-firm test for every table row."""
    q = load()
    tg = targets(q)
    assert len(tg) == 7547, len(tg)
    qm = attach_methods(q)
    qm["dens"] = poll_density(qm)
    ok = leak_check(q, tg, lambda x: dict(BASE, half_life=180.0, trend=trend_fn(x, 7, corrected=True)),
                    "national trend, corrected")
    # regression: where the target's firm has no national polls, corrected = first version
    natf = {c: set(d.pkey) for c, d in q[q.geo == "US"].groupby("cycle")}
    sub = tg[(tg.geo != "US") & ~np.array([p in natf.get(c, ()) for c, p in zip(tg.cycle, tg.pkey)])]
    sub = sub.sample(300, random_state=3)
    a = predict(q, sub, dict(BASE, half_life=180.0, trend=trend_fn(q, 7)))
    b = predict(q, sub, dict(BASE, half_life=180.0, trend=trend_fn(q, 7, corrected=True)))
    same = float(np.max(np.abs(a - b)))
    print(f"corrected = first version where the firm has no national polls (300 targets): "
          f"{'PASS' if same < 1e-9 else 'FAIL'} (max diff {same:.2e})", flush=True)
    res = {"leak_trend_corrected": ok, "regression_max_diff": same}

    def gp_cycle(x, c):
        return gaps(x[x.cycle == c])
    gp = gaps(q)
    S = rebuild_settings(q, gp, qm)
    lam = {int(c): v for c, v in stored("house")["info"]["picked"].items()}
    builders = {
        "trend_corrected (7/180)": lambda x, c: dict(BASE, half_life=180.0, trend=trend_fn(x, 7, corrected=True)),
        "trend first version (7/180)": lambda x, c: dict(BASE, half_life=180.0, trend=trend_fn(x, 7)),
        "house (round 1)": lambda x, c: dict(BASE, house=house_fn(x, gp_cycle(x, c), lam[c])),
        "house_week_corrected": lambda x, c: dict(BASE, house=house_week_fn(x, corrected=True)),
    }
    for k in ["baseline", "half_life", "rv_lean", "count_decay", "total_error", "no_rv"]:
        builders[k] = (lambda k: lambda x, c: S[k][c])(k)
    own = {k: own_firm_check_by_cycle(q, tg, b, k) for k, b in builders.items()}
    # method weights come from other cycles' gaps: moving the target's firm in its own cycle cannot change them
    own["method"] = own_firm_check_by_cycle(qm, tg, lambda x, c: S["method"][c], "method")
    res["own_firm_fails_of_20"] = own
    (OUT / "pres_nowcast_checks3.json").write_text(json.dumps(res, indent=1, default=float))
    if not ok or same >= 1e-9 or own["trend_corrected (7/180)"] or own["baseline"]:
        raise SystemExit("a gate failed")


def density_split():
    q = load()
    tg = targets(q)
    assert len(tg) == 7547, len(tg)
    qm = attach_methods(q)
    qm["dens"] = poll_density(qm)
    gp = gaps(q)
    S = rebuild_settings(q, gp, qm)
    S["trend_corrected"], S["trend_control"] = trend_settings(q)
    cls = density_class(q, tg)
    preds, check = {}, {}
    for name, sc in S.items():
        qq = qm if name == "method" else q
        pred = run_per_cycle(qq, tg, sc)
        if name.startswith("trend"):                    # the nation's average is the baseline's
            pred[(tg.geo == "US").values] = preds["baseline"][(tg.geo == "US").values]
        got = cycle_losses(tg, pred).round(3)
        if name != "trend_control":
            ref = stored(name)
            want = (pd.Series({int(c): v["mse"] for c, v in ref["by_cycle"].items()}) if name == "baseline" else
                    pd.Series({int(c): v["candidate"] for c, v in ref["by_cycle"].items()}))
            diff = float((got - want).abs().max())
            check[name] = diff
            print(f"rebuilt {name}: max per-cycle difference from stored {diff:.4f}", flush=True)
            assert diff <= 0.0011, (name, got.to_dict(), want.to_dict())
        preds[name] = pred
    t = tg[["cycle", "geo", "week", "pkey", "y"]].assign(cls=cls)
    for k, v in preds.items():
        t[k] = v
    t.round(4).to_csv(OUT / "pres_nowcast_target_preds.csv", index_label="target")
    cnt = t.groupby(["cls", "cycle"]).size().unstack(fill_value=0)
    loss = {}
    for k in preds:
        se = (t[k] - t.y) ** 2
        loss[k] = t.assign(se=se).groupby(["cls", "cycle"]).se.mean().groupby("cls").mean()
    L = pd.DataFrame(loss).reindex(DENS_CLASSES)
    G = L.drop(columns="baseline").rsub(L.baseline, axis=0)
    G["trend_own_part"] = L.trend_control - L.trend_corrected
    out = {"targets": cnt.reindex(DENS_CLASSES).to_dict("index"), "loss": L.round(3).to_dict("index"),
           "gain_vs_baseline": G.round(3).to_dict("index"), "rebuild_max_diff": check}
    (OUT / "pres_nowcast_density_split.json").write_text(json.dumps(out, indent=1, default=float))
    pd.set_option("display.width", 250)
    print(cnt.reindex(DENS_CLASSES).to_string())
    print(L.round(2).T.to_string())
    print(G.round(2).T.to_string())


# ---------------- round 3 ----------------
LATEST_K = (2, 3, 5, 8, 12, 20)
DENS_HD = (7, 14, 30)
DENS_HS = (60, 90, 180, 365)
DENS_D = (4, 10)


def deletion_check(q, tg, s_builder, label, n=15, seed=4):
    """Deleting polls must not change predictions: (a) every poll ending on or after t (all places, same cycle);
    (b) every poll by the target's firm in the cycle."""
    rng = np.random.default_rng(seed)
    groups = list(tg.groupby(["cycle", "geo", "t"]).groups.items())
    bad_a = 0
    for k in rng.choice(len(groups), size=n, replace=False):
        (c, g, t), idx = groups[k]
        sub = tg.loc[idx]
        q2 = q[~((q.cycle == c) & (q.end >= t))]
        bad_a += int(np.max(np.abs(predict(q, sub, s_builder(q)) - predict(q2, sub, s_builder(q2)))) > 1e-9)
    bad_b = 0
    for j in rng.choice(tg.index.values, size=20, replace=False):
        sub = tg.loc[[j]]
        q2 = q[~((q.cycle == sub.cycle.iloc[0]) & (q.pkey == sub.pkey.iloc[0]))]
        bad_b += int(np.max(np.abs(predict(q, sub, s_builder(q)) - predict(q2, sub, s_builder(q2)))) > 1e-9)
    print(f"deletion tests, {label}: later polls {'PASS' if not bad_a else f'FAIL {bad_a}/{n}'}; "
          f"own firm {'PASS' if not bad_b else f'FAIL {bad_b}/20'}", flush=True)
    return bad_a == 0 and bad_b == 0


def checks4():
    q = load()
    tg = targets(q)
    assert len(tg) == 7547, len(tg)
    ok = True
    for label, b in [("baseline", lambda x: dict(BASE)),
                     ("latest 5 firms", lambda x: dict(BASE, latest_k=5)),
                     ("half-life by density 14/180/10", lambda x: dict(BASE, dens_hl=(14, 180, 10))),
                     ("half-life by density 7/365/4", lambda x: dict(BASE, dens_hl=(7, 365, 4)))]:
        ok &= leak_check(q, tg, b, label)
        ok &= own_firm_check(q, tg, b, label)
        ok &= deletion_check(q, tg, b, label)
    if not ok:
        raise SystemExit("a check failed")


# ---------------- naive benchmarks (not candidates) ----------------
NAIVE = ("latest_poll", "latest_five_firms", "every_poll")


def naive_one(pool, kind):
    """pool: other firms' polls of the place that ended before the date. Raw margins, no weights or adjustments."""
    if kind == "every_poll":
        return float(pool.m.mean())
    if kind == "latest_poll":
        return float(pool.m[pool.end == pool.end.max()].mean())
    last = pool.groupby("pkey").end.transform("max")
    rd = pool[pool.end == last].groupby("pkey").agg(end=("end", "first"), m=("m", "mean"))
    if len(rd) > 5:
        cut = rd.end.sort_values(ascending=False).iloc[4]
        rd = rd[rd.end >= cut]
    return float(rd.m.mean())


def naive_predict(q, tg, kind):
    out = np.empty(len(tg))
    for (c, g, t), idx in tg.groupby(["cycle", "geo", "t"]).groups.items():
        d = q[(q.cycle == c) & (q.geo == g) & (q.end < t)]
        for j in idx:
            out[tg.index.get_loc(j)] = naive_one(d[d.pkey != tg.at[j, "pkey"]], kind)
    return out


def benchmarks():
    q = load()
    tg = targets(q)
    assert len(tg) == 7547, len(tg)
    rng = np.random.default_rng(1)
    groups = list(tg.groupby(["cycle", "geo", "t"]).groups.items())
    ok = True
    for kind in NAIVE:
        bad = 0
        for k in rng.choice(len(groups), size=15, replace=False):
            (c, g, t), idx = groups[k]
            sub = tg.loc[idx]
            q2 = q.copy()
            q2.loc[(q2.cycle == c) & (q2.end >= t), "m"] += 50
            bad += int(np.max(np.abs(naive_predict(q, sub, kind) - naive_predict(q2, sub, kind))) > 1e-9)
        own = 0
        for j in np.random.default_rng(2).choice(tg.index.values, size=20, replace=False):
            sub = tg.loc[[j]]
            q2 = q.copy()
            q2.loc[(q2.cycle == sub.cycle.iloc[0]) & (q2.pkey == sub.pkey.iloc[0]), "m"] += 50
            own += int(np.max(np.abs(naive_predict(q, sub, kind) - naive_predict(q2, sub, kind))) > 1e-9)
        print(f"{kind}: leak test {'PASS' if not bad else f'FAIL {bad}/15'}; own-firm test "
              f"{'PASS' if not own else f'FAIL {own}/20'}", flush=True)
        ok = ok and not bad and not own
    if not ok:
        raise SystemExit("a check failed")
    base_pred = predict(q, tg, BASE)
    preds = pd.read_csv(OUT / "pres_nowcast_target_preds.csv", index_col="target")
    assert np.allclose(preds.baseline.values, base_pred, atol=1e-3)
    cls = preds.cls.values
    out = {}
    for kind in NAIVE:
        pred = naive_predict(q, tg, kind)
        _, sc = score(tg, pred)
        # adoption() reports the baseline as the candidate's comparator; here the benchmark is the comparator, so
        # gain > 0 means the baseline is better
        res = adoption(tg, pred, base_pred)
        res["by_cycle"] = {c: {"benchmark": v["baseline"], "baseline": v["candidate"]} for c, v in res["by_cycle"].items()}
        res.pop("adopted")
        res["benchmark_passes_rule"] = adoption(tg, base_pred, pred)["adopted"]
        se = tg.assign(se=(pred - tg.y) ** 2, cls=cls)
        dens = se.groupby(["cls", "cycle"]).se.mean().groupby("cls").mean().reindex(DENS_CLASSES)
        out[kind] = {"baseline_vs_benchmark": res, "score": sc, "loss_by_density": dens.round(3).to_dict()}
        preds[kind] = np.round(pred, 4)
        print(f"\n== {kind}: loss {sc['loss']:.3f}; nation {sc['national']}, states {sc['states']}; bands {sc['by_band']}")
        print("   baseline against it: " + json.dumps(res))
        print("   by density: " + json.dumps(out[kind]["loss_by_density"]))
    preds.to_csv(OUT / "pres_nowcast_target_preds.csv", index_label="target")
    (OUT / "pres_nowcast_benchmarks.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    if cmd == "checks":
        checks()
    elif cmd == "checks2":
        q = load()
        tg = targets(q)
        assert len(tg) == 7547, len(tg)
        print("targets: 7,547 PASS")
        qm = attach_methods(q)
        ok = [leak_check(q, tg, lambda x: dict(BASE, count_decay=4.0), "memory by poll count"),
              leak_check(q, tg, lambda x: dict(BASE, half_life=90.0, trend=trend_fn(x, 14)), "national trend"),
              leak_check(q, tg, lambda x: dict(BASE, house=house_week_fn(x)), "house effects, same week"),
              leak_check(q, tg, lambda x: dict(BASE, house=house_week_fn(x, corrected=True)),
                         "house effects, same week, corrected"),
              leak_check(q, tg, lambda x: dict(BASE, size_tau2=20.0), "total expected error"),
              leak_check(qm, tg, lambda x: dict(BASE, method_w={"ivr": 0.5, "online": 0.8}), "method weights"),
              leak_check(q, tg, lambda x: dict(BASE, pop_lean={k: 0.0 for k in BASE["pop_lean"]}), "no correction")]
        own = {"baseline": own_firm_check(q, tg, lambda x: dict(BASE), "baseline"),
               "first version": own_firm_check(q, tg, lambda x: dict(BASE, house=house_week_fn(x)),
                                               "house effects, same week, first version"),
               "corrected": own_firm_check(q, tg, lambda x: dict(BASE, house=house_week_fn(x, corrected=True)),
                                           "house effects, same week, corrected")}
        if not all(ok) or not own["baseline"] or not own["corrected"]:
            raise SystemExit("a leak test failed")
    elif cmd == "checks3":
        checks3()
    elif cmd == "checks4":
        checks4()
    elif cmd == "benchmarks":
        benchmarks()
    elif cmd == "split":
        density_split()
    elif cmd == "density":
        q = load()
        out = half_life_by_density(q, targets(q))
        out.round(3).to_json(OUT / "pres_nowcast_half_life_by_density.json", orient="index", indent=1)
        print(out.round(2).to_string())
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
        if cmd in ("latest_k", "dens_hl"):              # round 3: keep per-target predictions and the density split
            pp = pd.read_csv(OUT / "pres_nowcast_target_preds.csv", index_col="target")
            pp[cmd] = np.round(pred, 4)
            pp.to_csv(OUT / "pres_nowcast_target_preds.csv", index_label="target")
            se = tg.assign(se=(pred - tg.y) ** 2, cls=pp.cls.values)
            res["loss_by_density"] = (se.groupby(["cls", "cycle"]).se.mean().groupby("cls").mean()
                                      .reindex(DENS_CLASSES).round(3).to_dict())
        (OUT / f"pres_nowcast_{cmd}.json").write_text(json.dumps(res, indent=1, default=float))
        print(f"\n== {cmd}: " + json.dumps({k: v for k, v in res.items() if k not in ("info", "score")}))
        print("score: " + json.dumps({k: sc[k] for k in ("loss", "national", "states", "by_band")}))
        print("info: " + json.dumps(info, default=float))
