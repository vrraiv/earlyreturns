"""EC-7: the backtest of the assembled electoral college model, 2008 to 2020 (ELECTORAL_COLLEGE.md, section 16).

Scores an outputs file of section 15's A6 shape (default: data/processed/pres_sim_asof.json) against the results.
No candidates and no fits: the scoring was written down before any output was read. 2024 is never loaded.

    python src/model/pres_backtest.py checks            planted inputs and identities; prints pass or fail only
    python src/model/pres_backtest.py run [outputs.json] the one scoring run; writes data/processed/pres_backtest.json
    python src/model/pres_backtest.py rungs             a declared diagnostic: errors by B2's rung (decides nothing)
    python src/model/pres_backtest.py plain7            a diagnostic: a plain 7-day poll average (decides nothing)
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
import pres_nowcast as P  # noqa: E402
import pres_thin_states as TS  # noqa: E402
import pres_addup as AU  # noqa: E402

INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed"
DEFAULT = OUT / "pres_sim_asof.json"
SCORED = (2008, 2012, 2016, 2020)
DAYS = (100, 60, 30, 7)
LEAD = 7
NOT_SCORED = {(2008, 100), (2008, 60)}             # section 7: 2000 has only late polls
DISTRICTS = ["ME-1", "ME-2", "NE-1", "NE-2", "NE-3"]
CLIP = 0.001
COMPETITIVE = (0.05, 0.95)
WINDOW = 30                                         # B2, rung 1: days before the date
NEED = 3                                            # B2: firms (rung 1) or polls (rung 2)
BANDS = ((0.0, 0.05), (0.05, 0.25), (0.25, 0.75), (0.75, 0.95), (0.95, 1.0000001))
PLEDGED = {2008: 365, 2012: 332, 2016: 232, 2020: 306}
MID_TOL = 0.25                                      # amended from 0.15 before any score was read (section 16)


# ------------------------------------------------------------------------------------------------ the results
def load_truth():
    """Results, electoral votes and vote totals, 2004 to 2020 only (2004 is the earlier election for 2008)."""
    R = TS.load_results()
    assert max(y for y, _ in R) <= 2020, "2024 is held out"
    D = pd.read_csv(INTERIM / "district_presidential.csv")
    D = D[D.year <= 2020]
    assert D.year.max() <= 2020
    E = pd.read_csv(INTERIM / "electoral_votes.csv")
    E = E[E.election <= 2020]
    votes = AU.vote_shares()
    assert max(y for y, _ in votes) <= 2020
    states = sorted({s for (_, s) in R if s != "US"})
    T = {}
    for y in (2004,) + SCORED:
        m = {s: R[(y, s)][0] for s in states}
        for c in DISTRICTS:
            m[c] = float(D[(D.year == y) & (D.contest == c)].margin_2p.iloc[0])
        nat = float(R[(y, states[0])][1])
        ev = {c: int(v) for c, v in zip(E[E.election == y].contest, E[E.election == y].ev)}
        T[y] = {"margin": m, "national": nat, "ev": ev, "lean": {c: m[c] - nat for c in m},
                "votes": {s: votes[(y, s)] for s in states}}
    return T, states


def count_dem(margin, ev):
    return int(sum(ev[c] for c in ev if margin[c] > 0))


def tipping(margin, ev):
    """The contests ordered by margin; the one whose votes take the winner past 269. None in a 269 tie."""
    dem = count_dem(margin, ev)
    if dem == 269:
        return None
    order = sorted(ev, key=lambda c: -margin[c] if dem >= 270 else margin[c])
    cum = 0
    for c in order:
        cum += ev[c]
        if cum >= 270:
            return c
    raise AssertionError("no tipping point")


def weighted_national(margin, votes):
    tot = sum(votes.values())
    return float(sum(votes[s] * margin[s] for s in votes) / tot)


# ------------------------------------------------------------------------------------------------ the benchmarks
def ladder(pool, t):
    """B2 for one contest: (value, rung). pool: its polls that ended before t. Rung 3 returns (nan, 3)."""
    if len(pool):
        age = (t - pool.end).dt.days
        win = pool[age.values <= WINDOW]
        if win.pkey.nunique() >= NEED:
            readings = [g[g.end == g.end.max()].m.mean() for _, g in win.groupby("pkey")]
            return float(np.mean(readings)), 1
        if len(pool) >= NEED:
            ends = pool.end.sort_values(ascending=False).values
            return float(pool[pool.end.values >= ends[NEED - 1]].m.mean()), 2
    return float("nan"), 3


def benchmarks(q, T, states, y, d):
    """Point margins for the 56 contests: B1 (four years earlier, repeated) and B2 (recent polls, the ladder)."""
    prev = T[y - 4]
    b1 = dict(prev["margin"])
    qy = q[q.cycle == y]
    t = qy.election.iloc[0] - pd.Timedelta(days=d)
    qy = qy[qy.end < t]
    nat, nat_rung = ladder(qy[qy.geo == "US"], t)
    assert nat_rung < 3, f"no national figure for {y} at {d} days"
    b2, rungs = {}, {}
    for c in states + DISTRICTS:
        v, r = ladder(qy[qy.geo == c], t)
        b2[c] = v if r < 3 else nat + prev["lean"][c]
        rungs[c] = r
    return {"B1": b1, "B2": b2}, {"rungs": {str(k): int(sum(1 for r in rungs.values() if r == k)) for k in (1, 2, 3)},
                                  "national_rung": int(nat_rung), "national": nat}


# ------------------------------------------------------------------------------------------------ the scores
def _err(f, r):
    e = np.asarray(r, float) - np.asarray(f, float)
    return {"n": int(len(e)), "mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e ** 2))), "signed": float(np.mean(e))}


def contest_rows(cell, truth, states, y, d):
    rows = []
    for c in states + DISTRICTS:
        o = cell["contests"][c]
        r = truth["margin"][c]
        p = float(o["p_dem"])
        won = r > 0
        pc = min(max(p, CLIP), 1 - CLIP)
        rows.append({"year": y, "d": d, "contest": c, "district": c in DISTRICTS, "p": p, "won": bool(won), "result": r,
                     "point": 0.5 * (o["q25"] + o["q75"]), "in50": o["q25"] <= r <= o["q75"], "in80": o["q10"] <= r <= o["q90"],
                     "brier": (p - won) ** 2, "logloss": -math.log(pc if won else 1 - pc),
                     "clipped": p != pc, "wrong": (p >= 0.5) != won,
                     "competitive": COMPETITIVE[0] <= p <= COMPETITIVE[1]})
    return rows


def state_scores(df):
    if not len(df):
        return None
    s = _err(df.point, df.result)
    s.update({"brier": float(df.brier.mean()), "logloss": float(df.logloss.mean()), "cover50": float(df.in50.mean()),
              "cover80": float(df.in80.mean()), "wrong": int(df.wrong.sum()), "clipped": int(df.clipped.sum()),
              "clipped_and_wrong": int((df.clipped & df.wrong).sum())})
    return s


def groups(df):
    return {"all56": state_scores(df), "competitive": state_scores(df[df.competitive]),
            "states51": state_scores(df[~df.district]), "districts5": state_scores(df[df.district])}


def top_scores(cell, truth):
    """The popular vote, the count, the winner, the gap and the tipping point for one cell."""
    m, ev, nat = truth["margin"], truth["ev"], truth["national"]
    dem = count_dem(m, ev)
    pmf = np.asarray(cell["count_pmf"], float)
    pv = cell["popular_vote"]
    p_win = cell["p_dem_270_exact"] if dem >= 270 else cell["p_rep_270_exact"]
    tp = tipping(m, ev)
    gap = m[tp] - nat
    g = cell["gap"]
    shares = cell["tipping_point"]["shares"]
    ranked = sorted(shares, key=lambda k: -shares[k])
    listed = tp in shares
    return {
        "popular_vote": {"actual": nat, "median": pv["median"], "error": nat - pv["median"], "in80": bool(pv["p10"] <= nat <= pv["p90"])},
        "count": {"actual": dem, "median": int(cell["count_median_exact"]), "error": dem - int(cell["count_median_exact"]),
                  "p10": int(cell["count_p10_exact"]), "p90": int(cell["count_p90_exact"]),
                  "in80": bool(cell["count_p10_exact"] <= dem <= cell["count_p90_exact"]),
                  "position": float(pmf[:dem].sum() + 0.5 * pmf[dem])},
        "winner": {"dem_won": bool(dem >= 270), "p_winner": float(p_win), "logloss": -math.log(min(max(p_win, CLIP), 1 - CLIP))},
        "gap": {"actual": gap, "median": g["median"], "error": gap - g["median"], "in80": bool(g["p10"] <= gap <= g["p90"]),
                "sign_right": bool((g["median"] > 0) == (gap > 0))},
        "tipping_point": {"actual": tp, "mode": cell["tipping_point"]["mode"], "listed": bool(listed),
                          "share": float(shares[tp]) if listed else None, "rank": (ranked.index(tp) + 1) if listed else None,
                          "share_bound_if_not_listed": None if listed else (float(min(shares.values())) if len(shares) >= 12 else 0.0),
                          "n_listed": len(shares)},
    }


def point_scores(margin, truth, states, prev_votes):
    """What a set of 56 point margins scores: used for both benchmarks."""
    m, ev, nat = truth["margin"], truth["ev"], truth["national"]
    cs = states + DISTRICTS
    f = np.array([margin[c] for c in cs]); r = np.array([m[c] for c in cs])
    pv = weighted_national(margin, prev_votes)
    tp, tp_true = tipping(margin, ev), tipping(m, ev)
    gap = (margin[tp] - pv) if tp else None
    gap_true = m[tp_true] - nat
    out = {"all56": _err(f, r), "states51": _err(f[:len(states)], r[:len(states)]),
           "wrong": int(((f > 0) != (r > 0)).sum()),
           "count": count_dem(margin, ev), "count_error": count_dem(m, ev) - count_dem(margin, ev),
           "popular_vote": pv, "popular_vote_error": nat - pv,
           "tipping_point": tp, "tipping_point_right": bool(tp == tp_true),
           "gap": gap, "gap_error": None if gap is None else gap_true - gap,
           "gap_sign_right": None if gap is None else bool((gap > 0) == (gap_true > 0))}
    return out


def score_file(outputs, T, states, q):
    cells, rows = {}, []
    for y in SCORED:
        for d in DAYS:
            if (y, d) in NOT_SCORED:
                continue
            cell = outputs[f"{y}/{d}"]
            rr = contest_rows(cell, T[y], states, y, d)
            rows += rr
            df = pd.DataFrame(rr)
            B, binfo = benchmarks(q, T, states, y, d)
            cells[f"{y}/{d}"] = {"states": groups(df), **top_scores(cell, T[y]),
                                 "benchmarks": {k: point_scores(B[k], T[y], states, T[y - 4]["votes"]) for k in B},
                                 "B2_ladder": binfo}
    return cells, pd.DataFrame(rows)


def pooled(cells, df):
    out = {}
    for d in DAYS:
        years = [y for y in SCORED if (y, d) not in NOT_SCORED]
        x = df[df.d == d]
        cs = [cells[f"{y}/{d}"] for y in years]
        o = {"years": years, "states": groups(x), "states_without_2008": groups(x[x.year != 2008])}
        o["popular_vote"] = {"mae": float(np.mean([abs(c["popular_vote"]["error"]) for c in cs])),
                             "signed": float(np.mean([c["popular_vote"]["error"] for c in cs])),
                             "in80": int(sum(c["popular_vote"]["in80"] for c in cs))}
        o["count"] = {"mae": float(np.mean([abs(c["count"]["error"]) for c in cs])), "in80": int(sum(c["count"]["in80"] for c in cs))}
        o["winner"] = {"logloss": float(np.mean([c["winner"]["logloss"] for c in cs])),
                       "favoured": int(sum(c["winner"]["p_winner"] > 0.5 for c in cs))}
        o["gap"] = {"mae": float(np.mean([abs(c["gap"]["error"]) for c in cs])), "in80": int(sum(c["gap"]["in80"] for c in cs)),
                    "sign_right": int(sum(c["gap"]["sign_right"] for c in cs))}
        o["tipping_point"] = {"listed": int(sum(c["tipping_point"]["listed"] for c in cs))}
        for b in ("B1", "B2"):
            bs = [c["benchmarks"][b] for c in cs]
            f = np.sqrt(np.mean([c_["all56"]["rmse"] ** 2 for c_ in bs]))
            o[b] = {"rmse56": float(f), "mae56": float(np.mean([c_["all56"]["mae"] for c_ in bs])),
                    "wrong": int(sum(c_["wrong"] for c_ in bs)),
                    "count_mae": float(np.mean([abs(c_["count_error"]) for c_ in bs])),
                    "popular_vote_mae": float(np.mean([abs(c_["popular_vote_error"]) for c_ in bs])),
                    "gap_mae": float(np.mean([abs(c_["gap_error"]) for c_ in bs if c_["gap_error"] is not None])),
                    "tipping_point_right": int(sum(c_["tipping_point_right"] for c_ in bs))}
        out[str(d)] = o
    return out


def calibration(df):
    x = df[df.d == LEAD]
    tab = []
    for lo, hi in BANDS:
        g = x[(x.p >= lo) & (x.p < hi)]
        tab.append({"band": f"{lo:.2f} to {min(hi, 1):.2f}", "n": int(len(g)),
                    "mean_p": float(g.p.mean()) if len(g) else None, "share_won": float(g.won.mean()) if len(g) else None})
    return tab


def flags(cells):
    """The six flags of section 16, at 7 days. Each: fires (bool) and what it counted."""
    cs = {y: cells[f"{y}/{LEAD}"] for y in SCORED}
    out = {}
    n = sum(not c["count"]["in80"] for c in cs.values())
    out["1_count"] = {"fires": n >= 3, "outside80": int(n)}
    ll = float(np.mean([c["winner"]["logloss"] for c in cs.values()]))
    out["2_winner"] = {"fires": ll > math.log(2), "mean_logloss": ll}
    n = sum(not c["popular_vote"]["in80"] for c in cs.values())
    out["3_popular_vote"] = {"fires": n >= 3, "outside80": int(n)}
    n1 = sum(not c["gap"]["in80"] for c in cs.values()); n2 = sum(not c["gap"]["sign_right"] for c in cs.values())
    out["4_gap"] = {"fires": n1 >= 3 or n2 >= 3, "outside80": int(n1), "wrong_sign": int(n2)}
    under, undet = 0, 0
    for c in cs.values():
        t = c["tipping_point"]
        if t["listed"]:
            under += t["share"] < 1 / 56
        elif t["share_bound_if_not_listed"] < 1 / 56:
            under += 1
        else:
            undet += 1
    out["5_tipping_point"] = {"fires": under >= 3, "under_1_in_56": int(under), "undetermined": int(undet)}
    det = {}
    for b in ("B1", "B2"):
        r = sum(c["benchmarks"][b]["all56"]["rmse"] < c["states"]["all56"]["rmse"] for c in cs.values())
        k = sum(abs(c["benchmarks"][b]["count_error"]) < abs(c["count"]["error"]) for c in cs.values())
        det[b] = {"smaller_state_rmse": int(r), "smaller_count_error": int(k)}
    out["6_benchmarks"] = {"fires": any(v["smaller_state_rmse"] >= 3 or v["smaller_count_error"] >= 3 for v in det.values()), **det}
    return out


# ------------------------------------------------------------------------------------------------ checks
def _planted_cell(truth, states, kind):
    """An outputs cell with known answers. kind: 'perfect', 'coin' or 'wrong'."""
    m, ev, nat = truth["margin"], truth["ev"], truth["national"]
    dem = count_dem(m, ev)
    tp = tipping(m, ev)
    gap = m[tp] - nat
    pmf = np.zeros(539)
    if kind == "perfect":
        pmf[dem] = 1.0
        con = {c: {"p_dem": float(m[c] > 0), "q10": m[c], "q25": m[c], "q75": m[c], "q90": m[c]} for c in m}
        pd_, pv = float(dem >= 270), {"median": nat, "p10": nat, "p90": nat, "sd": 0.0}
        g = {"median": gap, "p10": gap, "p90": gap}
        sh = {tp: 1.0}
    elif kind == "coin":
        pmf[:] = 1 / 539
        con = {c: {"p_dem": 0.5, "q10": m[c] - 12, "q25": m[c] - 5, "q75": m[c] + 5, "q90": m[c] + 12} for c in m}
        pd_, pv = 0.5, {"median": nat, "p10": nat - 5, "p90": nat + 5, "sd": 4.0}
        g = {"median": gap, "p10": gap - 2, "p90": gap + 2}
        sh = {tp: 0.5, "ZZ": 0.5}
    else:
        wrong = 538 - dem
        pmf[wrong] = 1.0
        con = {c: {"p_dem": float(m[c] < 0), "q10": -m[c] + 30, "q25": -m[c] + 30, "q75": -m[c] + 30, "q90": -m[c] + 30} for c in m}
        pd_, pv = float(wrong >= 270), {"median": nat + 20, "p10": nat + 19, "p90": nat + 21, "sd": 1.0}
        g = {"median": -gap - 5 if gap > 0 else -gap + 5, "p10": -gap - 6 if gap > 0 else -gap + 4, "p90": -gap - 4 if gap > 0 else -gap + 6}
        sh = {f"X{i}": (0.89 if i == 0 else 0.01) for i in range(12)}
    cum = np.cumsum(pmf)
    return {"p_dem_270_exact": pd_, "p_rep_270_exact": 1 - pd_, "p_tie_exact": 0.0, "count_pmf": [float(x) for x in pmf],
            "count_median_exact": int(np.searchsorted(cum, 0.5)), "count_p10_exact": int(np.searchsorted(cum, 0.10)),
            "count_p90_exact": int(np.searchsorted(cum, 0.90)), "popular_vote": pv, "gap": g,
            "tipping_point": {"mode": max(sh, key=sh.get), "shares": sh}, "contests": con}


def checks():
    ok = {}
    T, states = load_truth()
    q = P.load(cycles=SCORED)
    raw = json.loads(DEFAULT.read_text())
    ok["no 2024 in the results, the districts, the votes, the polls or the outputs"] = (
        max(T) <= 2020 and 2024 not in set(q.cycle) and q.end.max() < pd.Timestamp("2021-01-01")
        and not any(k.startswith("2024") for k in raw))
    ok["16 cells, 56 contests in each"] = len(raw) == 16 and all(
        set(c["contests"]) == set(states + DISTRICTS) for c in raw.values())
    ok["the three outcomes sum to one and the count's distribution sums to one"] = all(
        abs(c["p_dem_270_exact"] + c["p_rep_270_exact"] + c["p_tie_exact"] - 1) < 1e-6 and abs(sum(c["count_pmf"]) - 1) < 1e-6
        and len(c["count_pmf"]) == 539 for c in raw.values())
    ok["electoral votes: 56 contests summing to 538 in each election"] = all(
        set(T[y]["ev"]) == set(states + DISTRICTS) and sum(T[y]["ev"].values()) == 538 for y in T)
    ok["pledged counts are 365, 332, 232 and 306"] = all(count_dem(T[y]["margin"], T[y]["ev"]) == PLEDGED[y] for y in SCORED)
    fr = pd.read_csv(OUT / "pres_addup_rerun_frame.csv")
    fr = fr[fr.cycle.isin(SCORED) & (fr.d == LEAD)]
    ok["state results equal the frame's result column"] = all(
        abs(T[int(y)]["margin"][s] - r) < 1e-9 for y, s, r in zip(fr.cycle, fr.state, fr.result))
    r = pd.read_csv(INTERIM / "state_presidential.csv"); r = r[r.year.isin(SCORED)]
    nat = {int(y): 100 * (g.d_votes.sum() - g.r_votes.sum()) / (g.d_votes.sum() + g.r_votes.sum()) for y, g in r.groupby("year")}
    ok["the national margin is the two-party margin of the state totals"] = all(abs(nat[y] - T[y]["national"]) < 0.01 for y in SCORED)
    # the point margin against the stored centre: values are compared, only pass or fail is printed
    fa = pd.read_csv(OUT / "pres_addup_rerun_frame.csv")
    worst = 0.0
    for y in SCORED:
        for d in DAYS:
            g = fa[(fa.cycle == y) & (fa.d == d)].set_index("state").C
            c = raw[f"{y}/{d}"]["contests"]
            worst = max(worst, max(abs(0.5 * (c[s]["q25"] + c[s]["q75"]) - g[s]) for s in states))
    ok[f"point margins equal the stored centre within {MID_TOL} points for the 51 states"] = worst <= MID_TOL
    if worst > MID_TOL:
        print(f"   (largest difference: {worst:.2f} points)")
    # the tipping point and the gap on made-up margins
    ev = {"A": 200, "B": 100, "C": 38, "D": 200}
    ok["tipping point on made-up margins, either winner"] = (
        tipping({"A": 10, "B": 2, "C": -1, "D": -9}, ev) == "B" and tipping({"A": 10, "B": -2, "C": -1, "D": -9}, ev) == "B"
        and tipping({"A": 10, "B": -2, "C": 1, "D": -9}, ev) == "B" and tipping({"A": 10, "B": 5, "C": 1, "D": -9}, ev) == "B")
    ev2 = {"A": 269, "B": 269}
    ok["a 269 tie has no tipping point"] = tipping({"A": 5, "B": -5}, ev2) is None
    # planted outputs
    def run_planted(kind):
        outs = {f"{y}/{d}": _planted_cell(T[y], states, kind) for y in SCORED for d in DAYS}
        return score_file(outs, T, states, q)
    cp, dfp = run_planted("perfect")
    a = pooled(cp, dfp)["7"]
    ok["a perfect forecast scores zero error, zero Brier and full coverage"] = (
        a["states"]["all56"]["mae"] < 1e-12 and a["states"]["all56"]["brier"] == 0 and a["states"]["all56"]["cover80"] == 1
        and a["count"]["mae"] == 0 and a["gap"]["mae"] < 1e-12 and a["popular_vote"]["mae"] < 1e-12
        and all(c["tipping_point"]["rank"] == 1 for c in cp.values()))
    ok["a perfect forecast raises no flag"] = not any(f["fires"] for f in flags(cp).values())
    cc, dfc = run_planted("coin")
    b = pooled(cc, dfc)["7"]
    ok["a 50% forecast scores Brier 0.25 and log loss 0.693, states and winner"] = (
        abs(b["states"]["all56"]["brier"] - 0.25) < 1e-12 and abs(b["states"]["all56"]["logloss"] - math.log(2)) < 1e-12
        and abs(b["winner"]["logloss"] - math.log(2)) < 1e-12 and b["states"]["all56"]["cover50"] == 1)
    ok["a flat count returns the result's own percentile"] = all(
        abs(c["count"]["position"] - (c["count"]["actual"] + 0.5) / 539) < 1e-9 for c in cc.values())
    cw, dfw = run_planted("wrong")
    fw = flags(cw)
    ok["a planted failure fires every flag"] = all(f["fires"] for f in fw.values())
    cu = {k: json.loads(json.dumps(v)) for k, v in cw.items()}
    for c in cu.values():
        c["tipping_point"]["share_bound_if_not_listed"] = 0.04
    f5 = flags(cu)["5_tipping_point"]
    ok["an unlisted tipping point with a twelfth share above 1 in 56 is undetermined, not counted"] = (
        not f5["fires"] and f5["undetermined"] == 4 and f5["under_1_in_56"] == 0)
    ok["a planted failure: every state clipped and wrong, log loss at the clip"] = (
        pooled(cw, dfw)["7"]["states"]["all56"]["clipped_and_wrong"] == 224
        and abs(pooled(cw, dfw)["7"]["states"]["all56"]["logloss"] + math.log(CLIP)) < 1e-9)
    # the ladder on made-up polls
    t = pd.Timestamp("2020-10-27")
    mk = lambda rows: pd.DataFrame(rows, columns=["pkey", "end", "m"]).assign(end=lambda x: pd.to_datetime(x.end))
    p1 = mk([("a", "2020-10-20", 2.0), ("a", "2020-10-25", 4.0), ("a", "2020-10-25", 6.0), ("b", "2020-10-01", 1.0), ("c", "2020-10-10", 3.0), ("d", "2020-06-01", 50.0)])
    p2 = mk([("a", "2020-10-20", 2.0), ("a", "2020-10-25", 4.0), ("b", "2020-07-01", 9.0), ("b", "2020-07-01", 11.0), ("c", "2020-03-01", 50.0)])
    p3 = mk([("a", "2020-10-20", 2.0), ("a", "2020-10-25", 4.0)])
    ok["B2's ladder: firms once in the window; the three latest polls with ties; then the lean"] = (
        ladder(p1, t) == (3.0, 1) and ladder(p2, t) == (6.5, 2) and ladder(p3, t)[1] == 3 and ladder(p3.iloc[:0], t)[1] == 3)
    B, info = benchmarks(q, T, states, 2012, 7)
    ok["B1 is the 2008 result in 2012; B2's rungs cover the 56"] = (
        all(B["B1"][c] == T[2008]["margin"][c] for c in states + DISTRICTS) and sum(info["rungs"].values()) == 56
        and not any(np.isnan(v) for v in B["B2"].values()))
    for k, v in ok.items():
        print(("pass  " if v else "FAIL  ") + k)
    print(f"{sum(ok.values())} of {len(ok)} checks pass")
    return all(ok.values())


# ------------------------------------------------------------------------------------------------ the one run
def run():
    path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    outputs = json.loads(path.read_text())
    assert not any(k.startswith("2024") for k in outputs), "2024 is held out"
    T, states = load_truth()
    q = P.load(cycles=SCORED)
    cells, df = score_file(outputs, T, states, q)
    res = {"outputs_file": path.name, "sha256": before, "cells": cells, "pooled": pooled(cells, df),
           "calibration_7d": calibration(df), "flags_7d": flags(cells)}
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    dest = OUT / ("pres_backtest.json" if path == DEFAULT else f"pres_backtest_{path.stem}.json")
    dest.write_text(json.dumps(res, indent=1, default=float))
    df.to_csv(dest.with_name(dest.stem + "_contests.csv"), index=False)
    print(json.dumps({"pooled": res["pooled"], "flags_7d": res["flags_7d"], "calibration_7d": res["calibration_7d"]}, indent=1, default=float))
    print("written:", dest.name, dest.stem + "_contests.csv")


# ------------------------------------------------------------------------------------------------ B2 by rung (diagnostic)
def rungs():
    """Section 16's declared diagnostic: B2's, B1's and the model's error by B2's rung, and the firms behind rung 2."""
    outputs = json.loads(DEFAULT.read_text())
    T, states = load_truth()
    q = P.load(cycles=SCORED)
    res = {}
    for y in SCORED:
        for d in DAYS:
            if (y, d) in NOT_SCORED:
                continue
            B, _ = benchmarks(q, T, states, y, d)
            qy = q[q.cycle == y]
            t = qy.election.iloc[0] - pd.Timedelta(days=d)
            qy = qy[qy.end < t]
            rows = []
            for c in states + DISTRICTS:
                pool = qy[qy.geo == c]
                _, r = ladder(pool, t)
                firms = None
                if r == 2:
                    ends = pool.end.sort_values(ascending=False).values
                    firms = sorted(set(pool[pool.end.values >= ends[NEED - 1]].pkey))
                o = outputs[f"{y}/{d}"]["contests"][c]
                rows.append({"contest": c, "rung": r, "firms": firms, "result": T[y]["margin"][c], "B1": B["B1"][c], "B2": B["B2"][c],
                             "model": 0.5 * (o["q25"] + o["q75"])})
            df = pd.DataFrame(rows)
            cell = {}
            for r, g in df.groupby("rung"):
                e = {k: float(np.sqrt(np.mean((g.result - g[k]) ** 2))) for k in ("B2", "B1", "model")}
                e["signed_B2"] = float(np.mean(g.result - g.B2))
                e["n"] = int(len(g))
                if r == 2:
                    e["one_firm"] = int(sum(len(f) == 1 for f in g.firms))
                    allf = pd.Series([f for fs in g.firms for f in fs]).value_counts()
                    e["distinct_firms"] = int(len(allf))
                    e["most_common_firm_contests"] = int(allf.iloc[0])
                    one = g[[len(f) == 1 for f in g.firms]]
                    e["rmse_B2_one_firm"] = float(np.sqrt(np.mean((one.result - one.B2) ** 2))) if len(one) else None
                    e["rmse_B2_other"] = float(np.sqrt(np.mean((g.result - g.B2)[[len(f) > 1 for f in g.firms]] ** 2))) if (len(g) - len(one)) else None
                cell[str(int(r))] = e
            res[f"{y}/{d}"] = cell
            print(f"{y}/{d}", json.dumps({k: {a: (round(b, 2) if isinstance(b, float) else b) for a, b in v.items()} for k, v in cell.items()}))
    (OUT / "pres_backtest_rungs.json").write_text(json.dumps(res, indent=1, default=float))
    print("written: pres_backtest_rungs.json")


# ------------------------------------------------------------------------------------------------ a plain 7-day average (diagnostic)
PLAIN_DAYS = 7
PLAIN_WINDOWS = (("A", "the 7 days before the forecast date", LEAD), ("B", "the final 7 days before the election", 0))
PLAIN_COLS = ("plain", "model", "B2", "B1", "poll_avg", "after_pull")


def _plain_frame(q, T, states, outputs):
    """One row per contest with a poll in the window, at the 7-day forecast, and the top line for each election.

    plain: the plain mean of the raw two-party margin of every poll of the contest (the loader's polls, one row a
    poll) that ended in the 7 days before the window's reference date. No firm rule, no weights, no corrections.
    model, B1, B2: EC-7's. poll_avg and after_pull (the 51 states): the model's own poll average before any prior
    (stage 1's nowcast, `p` in pres_prior_frame.csv) and after EC-4's fixed pull toward the prior (`F`), before the
    even shift. filled (all 56): a contest with no poll in the window takes the window's plain national average
    plus its lean four years earlier, B2's last rung."""
    pf = pd.read_csv(OUT / "pres_prior_frame.csv")
    pf = pf[(pf.d == LEAD) & pf.cycle.isin(SCORED)].set_index(["cycle", "state"])
    au = pd.read_csv(OUT / "pres_addup_rerun_frame.csv")
    au = au[(au.d == LEAD) & au.cycle.isin(SCORED)].set_index(["cycle", "state"])
    cs = states + DISTRICTS
    rows, tops, chk = [], {}, {"point_vs_C": 0.0, "addup_input_vs_F": 0.0, "calls_differ": 0}
    for y in SCORED:
        cell = outputs[f"{y}/{LEAD}"]
        model = {r["contest"]: r for r in contest_rows(cell, T[y], states, y, LEAD)}
        bm, _ = benchmarks(q, T, states, y, LEAD)
        qy = q[q.cycle == y]
        elec = qy.election.iloc[0]
        for c in states:                                          # the model's point against the stored centre; EC-4's F
            chk["point_vs_C"] = max(chk["point_vs_C"], abs(model[c]["point"] - float(au.loc[(y, c), "C"])))
            if bool(pf.loc[(y, c), "has"]):
                chk["addup_input_vs_F"] = max(chk["addup_input_vs_F"],
                                              abs(float(au.loc[(y, c), "baseline"]) - float(pf.loc[(y, c), "F"])))
        chk["calls_differ"] += sum((model[c]["point"] > 0) != (model[c]["p"] >= 0.5) for c in cs)
        for wname, _, back in PLAIN_WINDOWS:
            ref = elec - pd.Timedelta(days=back)
            w = qy[(qy.end < ref) & ((ref - qy.end).dt.days <= PLAIN_DAYS)]
            avg, npoll, nfirm = w.groupby("geo").m.mean(), w.groupby("geo").size(), w.groupby("geo").pkey.nunique()
            for c in cs:
                has = c in avg.index
                st = c in states and bool(pf.loc[(y, c), "has"])
                rows.append({"year": y, "window": wname, "contest": c, "state": c in states, "result": T[y]["margin"][c],
                             "covered": has, "plain": float(avg[c]) if has else np.nan,
                             "npolls": int(npoll[c]) if has else 0, "nfirms": int(nfirm[c]) if has else 0,
                             "model": model[c]["point"], "p_dem": model[c]["p"], "competitive": model[c]["competitive"],
                             "B2": bm["B2"][c], "B1": bm["B1"][c],
                             "poll_avg": float(pf.loc[(y, c), "p"]) if st else np.nan,
                             "after_pull": float(pf.loc[(y, c), "F"]) if st else np.nan})
            nat = float(avg["US"]) if "US" in avg.index else float("nan")
            filled = {c: (float(avg[c]) if c in avg.index else nat + T[y - 4]["lean"][c]) for c in cs}
            ps = point_scores(filled, T[y], states, T[y - 4]["votes"])
            s = json.loads((OUT / "pres_backtest.json").read_text())["cells"][f"{y}/{LEAD}"]
            tops[f"{y}/{wname}"] = {
                "national_polls": int(npoll.get("US", 0)), "national_plain": nat, "national_result": T[y]["national"],
                "national_plain_error": T[y]["national"] - nat, "model_popular_vote_error": s["popular_vote"]["error"],
                "filled": {"rmse": ps["all56"]["rmse"], "signed": ps["all56"]["signed"], "wrong": ps["wrong"],
                           "count": ps["count"], "count_error": ps["count_error"]},
                "model_all56": {"rmse": s["states"]["all56"]["rmse"], "wrong": s["states"]["all56"]["wrong"],
                                "count_error": s["count"]["error"]},
                "B2_all56_rmse": s["benchmarks"]["B2"]["all56"]["rmse"]}
    return pd.DataFrame(rows), tops, chk


def _plain_scores(g):
    """n, and for each column the root mean square error, the mean signed miss and the winners called wrong (by the
    sign of the point margin). The model's own poll average and the pull exist for the 51 states only."""
    out = {"n": int(len(g)), "n_states": int(g.state.sum()), "polls": int(g.npolls.sum()),
           "one_poll": int((g.npolls == 1).sum()), "one_firm": int((g.nfirms == 1).sum())}
    for col in PLAIN_COLS:
        for name, h in (("", g), ("_states", g[g.state])):
            h = h.dropna(subset=[col])
            if not len(h):
                out[col + name] = None
                continue
            e = h.result - h[col]
            out[col + name] = {"n": int(len(h)), "rmse": float(np.sqrt((e ** 2).mean())), "signed": float(e.mean()),
                               "wrong": int(((h[col] > 0) != (h.result > 0)).sum())}
    return out


def plain7():
    """Section 16's diagnostic, run on 2026-11-27 before it was written down: a plain average of the last 7 days'
    polls against the model at 7 days. Decides nothing; no score, benchmark or flag of EC-7 changes."""
    before = {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in ("pres_sim_asof.json", "pres_backtest.json")}
    outputs = json.loads(DEFAULT.read_text())
    assert not any(k.startswith("2024") for k in outputs), "2024 is held out"
    T, states = load_truth()
    q = P.load(cycles=SCORED)
    assert q.poll_id.is_unique and 2024 not in set(q.cycle)
    df, tops, chk = _plain_frame(q, T, states, outputs)
    assert chk["point_vs_C"] <= MID_TOL and chk["addup_input_vs_F"] < 1e-6, chk
    cov = df[df.covered].copy()
    cov["bin"] = np.where(cov.npolls == 1, "1", np.where(cov.npolls <= 3, "2-3", "4+"))
    res = {"checks": chk, "windows": {}}
    for wname, label, _ in PLAIN_WINDOWS:
        g = cov[cov.window == wname]
        by = lambda keys: {"/".join(str(k) for k in (key if isinstance(key, tuple) else (key,))): _plain_scores(h)  # noqa: E731
                           for key, h in g.groupby(keys)}
        res["windows"][wname] = {
            "label": label, "pooled": _plain_scores(g), "by_election": by(["year"]),
            "competitive": by(["competitive"]), "competitive_by_election": by(["competitive", "year"]),
            "by_polls": by(["bin"]), "by_polls_by_election": by(["bin", "year"]), "competitive_by_polls": by(["competitive", "bin"]),
            "top": {str(y): tops[f"{y}/{wname}"] for y in SCORED}}
    a = df[df.window == "A"]
    plain_wrong = a.covered & ((a.plain > 0) != (a.result > 0))
    model_wrong = (a.p_dem >= 0.5) != (a.result > 0)
    res["calls_A"] = [{"year": int(r.year), "contest": r.contest, "result": float(r.result), "model": float(r.model),
                       "p_dem": float(r.p_dem), "model_wrong": bool(mw), "plain": None if not r.covered else float(r.plain),
                       "npolls": int(r.npolls), "plain_wrong": None if not r.covered else bool(pw)}
                      for (_, r), mw, pw in zip(a.iterrows(), model_wrong, plain_wrong) if mw or pw]
    assert all(hashlib.sha256((OUT / f).read_bytes()).hexdigest() == h for f, h in before.items())
    (OUT / "pres_backtest_plain7.json").write_text(json.dumps(res, indent=1, default=float))
    cov.drop(columns=["covered"]).to_csv(OUT / "pres_backtest_plain7_contests.csv", index=False)
    f2 = lambda s: "-" if s is None else f"{s['rmse']:.2f} ({s['signed']:+.2f}, {s['wrong']}w)"  # noqa: E731
    for wname, label, _ in PLAIN_WINDOWS:
        W = res["windows"][wname]
        print(f"\nwindow {wname}: {label}   [rmse (signed, called wrong)]")
        for title, key in (("by election", "by_election"), ("competitive", "competitive"), ("polls in the window", "by_polls")):
            for k, s in W[key].items():
                print(f"  {title:20s} {k:6s} n {s['n']:3d}  plain {f2(s['plain'])}  model {f2(s['model'])}  | states: "
                      f"plain {f2(s['plain_states'])}  poll average {f2(s['poll_avg_states'])}  after pull {f2(s['after_pull_states'])}"
                      f"  model {f2(s['model_states'])}")
        for y, t in W["top"].items():
            print(f"  {y}: national plain {t['national_plain']:+.2f} (result {t['national_result']:+.2f}); filled 56: "
                  f"{t['filled']['rmse']:.2f}, {t['filled']['wrong']}w, count error {t['filled']['count_error']:+d}; "
                  f"model {t['model_all56']['rmse']:.2f}, {t['model_all56']['wrong']}w, {t['model_all56']['count_error']:+d}")
    print("\ncalls that differ or are wrong (window A):", len(res["calls_A"]), "| checks:", chk)
    print("written: pres_backtest_plain7.json pres_backtest_plain7_contests.csv")


if __name__ == "__main__":
    {"checks": checks, "run": run, "rungs": rungs, "plain7": plain7}[sys.argv[1] if len(sys.argv) > 1 else "checks"]()
