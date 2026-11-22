"""EC-4: the state prior and the weight on polls (ELECTORAL_COLLEGE.md, section 13).

Every rung is  estimate = prior + w x (p - prior)  for a state with a poll; a state with no poll that cycle takes the
prior. p is stage 1's nowcast from every poll of the state before the date; the prior is the national two-party
nowcast (lagged 3 days) plus the state's lean.
  baseline  w = 1 (EC-2's outcome: own polls however old)
  F         one fixed weight, fitted per date (suggested by the overfitting challenge)
  V         w = 1 / (1 + alpha + beta / (1 + n)), n = sum over the state's polls of 0.5^(age / 60)
  M         the prior's lean = a + b1 x (lean last election) + b2 x (lean the one before), fitted on results from 1980;
            the weight is refitted with that prior. S is M without b2 (the slope alone).
Fits use earlier elections only: F and V on the polled states of earlier elections at the same date, with one constant
per election (2000 is in the fits at 30 and 7 days and is never scored); M on the elections before each election.
Score: the lean error at 30 and 7 days: a state's error less the vote-weighted mean error of the 51, squared, averaged
over the 51, the two dates, then elections equally.
Rule: positive gain against the rung below that stands, 4 of 5 elections better, and F a sign-flip over the 10
election-date units (p < 0.05); V beats 19 in 20 of 200 shuffles of n; M beats 19 in 20 of 200 shuffles of the change
in lean. Flags send a pass to the user.

Run:  python src/model/pres_prior.py checks     (prints pass or fail only; no loss and no fitted number)
      python src/model/pres_prior.py run
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
import pres_nowcast as P  # noqa: E402
import pres_thin_states as TS  # noqa: E402
import pres_addup as AU  # noqa: E402
import pres_reversion as RV  # noqa: E402

INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed"
SCORED = (2004, 2008, 2012, 2016, 2020)
FIT_ONLY = (2000,)                      # late polls only: in the fits at 30 and 7 days, never scored
SCORE_DAYS = (30, 7)
REPORT_DAYS = (150, 100, 60)
ALL_DAYS = SCORE_DAYS + REPORT_DAYS
HL = float(P.BASE["half_life"])         # 60 days: the nowcast's half-life, reused for the effective count
LEAN_FROM = 1980                        # first election M is fitted on (its two earlier leans are 1976 and 1972)
SHUFFLES = 200
STARTS = ((0.25, 0.0), (1.0, 1.0), (0.25, 4.0))
BETA_ZERO = 1e-4                        # a fitted beta below this is zero: the bounded fit stops just inside the bound
GROUPS = ("none", "0", "1-3", "4-9", "10+")
STATES = None


# ------------------------------------------------------------------------------------------------ loading
def load_polls():
    q = P.load(cycles=FIT_ONLY + SCORED)
    assert 2024 not in set(q.cycle), "2024 is held out"
    return q


def load_national():
    d = pd.read_csv(INTERIM / "president_national_poll_days.csv", parse_dates=["date", "election_date"])
    assert 2024 not in set(d.cycle), "2024 is held out"
    out = {}
    for y in FIT_ONLY + SCORED:
        x = d[d.cycle == y]
        el = x.election_date.iloc[0]
        out[y] = {"t": (el - x.date).dt.days.values.astype(float), "m": x.margin_2p.values.astype(float)}
    return out


def load_leans(R):
    """Lean by (year, state). 1992 on is state_presidential.csv (through R, so the baseline prior and M read the same
    numbers); 1972 to 1988 is the history file. No row after 2020 is kept from either."""
    h = pd.read_csv(INTERIM / "state_presidential_history.csv", usecols=["year", "state", "lean_2p"])
    h = h[(h.year >= 1972) & (h.year < 1992)]
    L = {(int(y), s): float(l) for y, s, l in zip(h.year, h.state, h.lean_2p)}
    L.update({k: v[2] for k, v in R.items() if k[0] >= 1992})
    assert max(y for y, _ in L) <= 2020, "2024 is held out"
    return L


def load_all():
    global STATES
    q = load_polls()
    R = TS.load_results()                                           # years to 2020 only
    assert max(y for y, _ in R) <= 2020
    STATES = sorted({s for (_, s) in R if s != "US"})
    Nd = load_national()
    L = load_leans(R)
    votes = AU.vote_shares()
    return q, R, Nd, L, votes


def national_forecast():
    """Stage 3's national forecast (nowcast x (1 - u / 100)) by election and date, for the after-shift report only."""
    E = RV.load()
    return {(y, d): float(E[y]["N"][d]) * (1 - float(E[y]["u"][d]) / 100) for y in SCORED for d in ALL_DAYS}


# ------------------------------------------------------------------------------------------------ the table
def all_cells():
    return [(y, d) for y in FIT_ONLY for d in SCORE_DAYS] + [(y, d) for y in SCORED for d in ALL_DAYS]


def poll_cell(q, y, d):
    """For one election and date, by state: has a poll, the nowcast p, the effective count n, polls in the last 30
    days. Reads polls that ended before the date and nothing else."""
    qy = q[(q.cycle == y) & (q.geo != "US")]
    el = q[q.cycle == y].election.iloc[0]
    t = el - pd.Timedelta(days=d)
    x = qy[qy.end < t]
    age = (t - x.end).dt.days.values
    x = x.assign(_w=0.5 ** (age / HL), _rec=(age <= 30))
    grp = {s: g for s, g in x.groupby("geo")}
    has = np.array([s in grp for s in STATES])
    p = np.array([P.average(grp[s], t, P.BASE) if s in grp else np.nan for s in STATES])
    n = np.array([float(grp[s]._w.sum()) if s in grp else 0.0 for s in STATES])
    rec = np.array([int(grp[s]._rec.sum()) if s in grp else 0 for s in STATES])
    assert not np.isnan(p[has]).any()
    return {"has": has, "p": p, "n": n, "recent": rec}


def poll_cells(q, cells=None):
    return {c: poll_cell(q, *c) for c in (cells or all_cells())}


def assemble(pc, Nd, R, L, votes):
    A = {}
    for (y, d), c in pc.items():
        N = TS.nat(Nd, y, d, HL)
        l1 = np.array([L[(y - 4, s)] for s in STATES])
        l2 = np.array([L[(y - 8, s)] for s in STATES])
        v = np.array([votes[(y - 4, s)] for s in STATES])
        A[(y, d)] = dict(c, N=N, lean1=l1, lean2=l2, v=v / v.sum(), prior0=N + l1,
                         result=np.array([R[(y, s)][0] for s in STATES]))
    return A


# ------------------------------------------------------------------------------------------------ the lean (M, S)
def lean_xy(L, perm=None):
    """For each election t from LEAN_FROM to 2020: (lean at t-4, lean at t-8, lean at t), by state. With perm, the
    change between the two earlier leans is handed from one state to another within each election."""
    out = {}
    for t in range(LEAN_FROM, 2021, 4):
        x1 = np.array([L[(t - 4, s)] for s in STATES])
        x2 = np.array([L[(t - 8, s)] for s in STATES])
        if perm is not None:
            x2 = x1 - (x1 - x2)[perm[t]]
        out[t] = (x1, x2, np.array([L[(t, s)] for s in STATES]))
    return out


def lean_coef(XY, e, slope_only=False):
    """Least squares of lean on the earlier lean(s) over the elections from LEAN_FROM to the one before e."""
    tr = [t for t in XY if t < e]
    X1 = np.concatenate([XY[t][0] for t in tr]); X2 = np.concatenate([XY[t][1] for t in tr])
    Y = np.concatenate([XY[t][2] for t in tr])
    X = np.column_stack([np.ones(len(Y)), X1] + ([] if slope_only else [X2]))
    b = np.linalg.lstsq(X, Y, rcond=None)[0]
    return np.array([b[0], b[1], 0.0 if slope_only else b[2]])


def lean_pred(XY, e, slope_only=False):
    b = lean_coef(XY, e, slope_only)
    return b[0] + b[1] * XY[e][0] + b[2] * XY[e][1], b


def add_lean_priors(A, XY):
    """Adds priorM and priorS to every cell: the national input plus the lean predicted for that election from the
    elections before it."""
    coef = {}
    pred = {}
    for y in FIT_ONLY + SCORED:
        m, bm = lean_pred(XY, y)
        s, bs = lean_pred(XY, y, slope_only=True)
        pred[y] = (m, s); coef[y] = {"M": bm, "S": bs}
    B = {c: dict(a, priorM=a["N"] + pred[c[0]][0], priorS=a["N"] + pred[c[0]][1]) for c, a in A.items()}
    return B, coef


# ------------------------------------------------------------------------------------------------ the weight (F, V)
def train_cells(y, d):
    first = FIT_ONLY[0] if d in SCORE_DAYS else SCORED[0]
    return [(e, d) for e in FIT_ONLY + SCORED if first <= e < y]


def _xy(A, cells, prior, nkey):
    out = []
    for c in cells:
        a = A[c]; m = a["has"]
        out.append((a["result"][m] - a[prior][m], a["p"][m] - a[prior][m], a[nkey][m]))
    return out


def fit_F(A, cells, prior):
    num = den = 0.0
    for yv, xv, _ in _xy(A, cells, prior, "n"):
        yv = yv - yv.mean(); xv = xv - xv.mean()
        num += float(xv @ yv); den += float(xv @ xv)
    return float(np.clip(num / den, 0.0, 1.0)) if den > 0 else 1.0


def w_V(th, n):
    return 1.0 / (1.0 + th[0] + th[1] / (1.0 + n))


def fit_V(A, cells, prior, nkey="n"):
    data = _xy(A, cells, prior, nkey)

    def resid(th):
        out = []
        for yv, xv, nv in data:
            r = yv - w_V(th, nv) * xv
            out.append(r - r.mean())
        return np.concatenate(out)

    best = None
    for s in STARTS:
        o = least_squares(resid, np.array(s, float), bounds=([0.0, 0.0], [np.inf, np.inf]))
        if best is None or o.cost < best.cost - 1e-12:
            best = o
    return np.array(best.x, float)


def estimate(a, prior, w):
    est = a[prior].copy()
    m = a["has"]
    ww = w[m] if isinstance(w, np.ndarray) else w
    est[m] = a[prior][m] + ww * (a["p"][m] - a[prior][m])
    return est


def rung(A, kind, prior="prior0", nkey="n", days=ALL_DAYS, fixed=None):
    """Estimates and fitted numbers for one rung, for every scored election and date. kind: 'base', 'F' or 'V'. A cell
    with no earlier election to fit on (2004 at 150, 100 and 60 days) keeps the baseline with the previous lean.
    fixed: a weight (F) or (alpha, beta) (V) used in place of the fit, for the behaviour checks."""
    est, fits = {}, {}
    for y in SCORED:
        for d in days:
            a = A[(y, d)]
            tc = train_cells(y, d)
            if not tc:
                est[(y, d)] = estimate(a, "prior0", 1.0); fits[(y, d)] = None
            elif kind == "base":
                est[(y, d)] = estimate(a, prior, 1.0); fits[(y, d)] = None
            elif kind == "F":
                w = fit_F(A, tc, prior) if fixed is None else float(fixed)
                est[(y, d)] = estimate(a, prior, w); fits[(y, d)] = [w]
            else:
                th = fit_V(A, tc, prior, nkey) if fixed is None else np.array(fixed, float)
                est[(y, d)] = estimate(a, prior, w_V(th, a[nkey])); fits[(y, d)] = [float(th[0]), float(th[1])]
    return est, fits


# ------------------------------------------------------------------------------------------------ scores
def lean_sq(est, a):
    """Each state's squared lean error: its error less the vote-weighted mean error of the 51."""
    e = est - a["result"]
    return (e - float(a["v"] @ e)) ** 2


def cell_loss(est, a, kind="lean", natF=None):
    if kind == "lean":
        return float(lean_sq(est, a).mean())
    if kind == "sq":                                                # states first, no shift
        return float(((est - a["result"]) ** 2).mean())
    if kind == "shift":                                             # after the even shift to the national forecast
        return float(((est + (natF - float(a["v"] @ est)) - a["result"]) ** 2).mean())
    if kind == "lean_vw":
        return float(a["v"] @ lean_sq(est, a))
    if kind == "close":
        m = np.abs(a["prior0"]) < 10
        return float(lean_sq(est, a)[m].mean()) if m.any() else np.nan
    if kind == "rest":
        m = np.abs(a["prior0"]) >= 10
        return float(lean_sq(est, a)[m].mean()) if m.any() else np.nan
    raise ValueError(kind)


def scores(E, A, days=SCORE_DAYS, kind="lean", years=SCORED, NF=None):
    """Per election: the mean over the dates of the cell loss."""
    return pd.Series({y: float(np.nanmean([cell_loss(E[(y, d)], A[(y, d)], kind, NF[(y, d)] if NF else None)
                                           for d in days])) for y in years})


def units(Eb, Ec, A, days=SCORE_DAYS, years=SCORED):
    return np.array([cell_loss(Eb[(y, d)], A[(y, d)]) - cell_loss(Ec[(y, d)], A[(y, d)]) for y in years for d in days])


def compare(Eb, Ec, A, days=SCORE_DAYS, kind="lean", years=SCORED, NF=None):
    b, c = scores(Eb, A, days, kind, years, NF), scores(Ec, A, days, kind, years, NF)
    return {"below": float(b.mean()), "rung": float(c.mean()), "gain": float((b - c).mean()),
            "better": int(((b - c) > 1e-12).sum()), "of": int(len(years)),
            "by_election": {int(y): [float(b[y]), float(c[y])] for y in years}}


def clauses(Eb, Ec, A, NF):
    """Everything the rule and the flags read for one rung against the rung below it."""
    out = compare(Eb, Ec, A)
    out["passes_gain_and_elections"] = bool(out["gain"] > 0 and out["better"] >= 4)
    u = units(Eb, Ec, A)
    out["p_signflip_10_units"] = float(TS.signflip_exact(u))
    out["p_signflip_elections_reported"] = float(TS.signflip_exact(
        (scores(Eb, A) - scores(Ec, A)).values))
    out["states_first_sq"] = compare(Eb, Ec, A, kind="sq")
    out["after_shift_sq_reported"] = compare(Eb, Ec, A, kind="shift", NF=NF)
    out["close_states"] = compare(Eb, Ec, A, kind="close")
    out["other_states"] = compare(Eb, Ec, A, kind="rest")
    out["vote_weighted"] = compare(Eb, Ec, A, kind="lean_vw")
    late = SCORED[1:]
    out["early_dates_2008_2020"] = compare(Eb, Ec, A, days=REPORT_DAYS, years=late)
    out["flags"] = {"1_worse_states_first": bool(out["states_first_sq"]["gain"] < 0),
                    "2_worse_close_states": bool(out["close_states"]["gain"] < 0),
                    "3_worse_early_dates": bool(out["early_dates_2008_2020"]["gain"] < 0)}
    # report (e): 2004 apart; every clause on 2008 to 2020, asking for 3 of 4
    e = compare(Eb, Ec, A, years=late)
    e["passes_gain_and_elections"] = bool(e["gain"] > 0 and e["better"] >= 3)
    e["p_signflip_8_units"] = float(TS.signflip_exact(units(Eb, Ec, A, years=late)))
    out["without_2004"] = e
    out["by_date"] = {int(d): compare(Eb, Ec, A, days=(d,)) for d in SCORE_DAYS}
    out["by_date_reported_2008_2020"] = {int(d): compare(Eb, Ec, A, days=(d,), years=late) for d in REPORT_DAYS}
    out["state_dates_changed"] = int(sum((np.abs(Eb[(y, d)] - Ec[(y, d)]) > 1e-9).sum() for y in SCORED for d in SCORE_DAYS))
    return out


# ------------------------------------------------------------------------------------------------ shuffles
def shuffle_n(A, permute):
    """n handed from one polled state to another within each election and date. permute: values -> the same values
    in another order."""
    B = {}
    for c, a in A.items():
        n = a["n"].copy(); m = a["has"]
        n[m] = permute(n[m])
        B[c] = dict(a, n_sh=n)
    return B


def lean_perms(permute_index):
    """One reordering of the states for each election from LEAN_FROM. permute_index: count -> an order."""
    return {t: permute_index(len(STATES)) for t in range(LEAN_FROM, 2021, 4)}


def shuffled_gains_V(A, E_below, rng, shuffles, prior="prior0"):
    """Per shuffle and election: the gain of V with n shuffled, against the rung below."""
    b = scores(E_below, A)
    out = []
    for _ in range(shuffles):
        B = shuffle_n(A, rng.permutation)
        Es, _f = rung(B, "V", prior=prior, nkey="n_sh", days=SCORE_DAYS)
        out.append((b - scores(Es, A)).values)
    return np.array(out)


def shuffled_gains_M(A0, L, E_below, kind, rng, shuffles):
    """Per shuffle and election: the gain of the standing rung with M's prior, the change in lean shuffled."""
    b = scores(E_below, A0)
    out = []
    for _ in range(shuffles):
        B, _c = add_lean_priors(A0, lean_xy(L, lean_perms(rng.permutation)))
        Es, _f = rung(B, kind, prior="priorM", days=SCORE_DAYS)
        out.append((b - scores(Es, A0)).values)
    return np.array(out)


def shuffle_verdict(gain, null):
    """null: one gain per shuffle. The gain has to exceed the 95th percentile by more than rounding."""
    q = float(np.quantile(null, 0.95))
    return {"gain": float(gain), "shuffle_95th": q, "share_of_shuffles_beaten": float(np.mean(null < gain - 1e-9)),
            "beats_19_in_20": bool(gain > q + 1e-9)}


def with_shuffles(c, null, need_late=3):
    """Adds the shuffle clause to a rung's clauses, on all five elections and (report e) on 2008 to 2020."""
    c["shuffle"] = shuffle_verdict(c["gain"], null.mean(axis=1))
    e = c["without_2004"]
    e["shuffle"] = shuffle_verdict(e["gain"], null[:, 1:].mean(axis=1))
    e["passes_reported"] = bool(e["gain"] > 0 and e["better"] >= need_late and e["shuffle"]["beats_19_in_20"])
    return c


# ------------------------------------------------------------------------------------------------ reports
def group_of(a):
    g = np.where(~a["has"], "none", np.where(a["recent"] == 0, "0", np.where(a["recent"] <= 3, "1-3",
                 np.where(a["recent"] <= 9, "4-9", "10+"))))
    return g


def report_a(Ebase, E, A, days, years):
    """The gain over the baseline by polls in the previous 30 days: state-dates, mean gain, elections gaining."""
    rows = []
    for y in years:
        for d in days:
            a = A[(y, d)]
            rows.append(pd.DataFrame({"y": y, "g": group_of(a),
                                      "gain": lean_sq(Ebase[(y, d)], a) - lean_sq(E[(y, d)], a)}))
    x = pd.concat(rows)
    out = {}
    for g in GROUPS:
        z = x[x.g == g]
        by = z.groupby("y").gain.mean()
        out[g] = {"state_dates": int(len(z)), "mean_gain": float(z.gain.mean()) if len(z) else None,
                  "elections_gaining": int((by > 1e-12).sum()), "elections_with_cases": int(len(by))}
    return out


def report_c(L):
    """The prior alone on results only, 1988 to 2020: mean squared error of the predicted lean, each election
    predicted from the elections before it."""
    XY = lean_xy(L)
    out = {}
    for e in range(LEAN_FROM + 8, 2021, 4):
        x1, _x2, yv = XY[e]
        m, _ = lean_pred(XY, e); s, _ = lean_pred(XY, e, slope_only=True)
        out[e] = {"previous_lean": float(((x1 - yv) ** 2).mean()), "M": float(((m - yv) ** 2).mean()),
                  "slope_alone": float(((s - yv) ** 2).mean())}
    mean = {k: float(np.mean([v[k] for v in out.values()])) for k in ("previous_lean", "M", "slope_alone")}
    return {"by_election": out, "mean": mean}


def report_d(E, A):
    out = {}
    for lab, lo, hi in (("under 10", 0, 10), ("10 to 20", 10, 20), ("over 20", 20, 1e9)):
        k = 0
        per = []
        for y in SCORED:
            v = []
            for d in SCORE_DAYS:
                a = A[(y, d)]; m = (np.abs(a["prior0"]) >= lo) & (np.abs(a["prior0"]) < hi)
                if m.any():
                    v.append(float(lean_sq(E[(y, d)], a)[m].mean())); k += int(m.sum())
            if v:
                per.append(float(np.mean(v)))
        out[lab] = {"lean_error": float(np.mean(per)) if per else None, "state_dates": k}
    return out


def frame_csv(A, ests):
    rows = []
    for y in SCORED:
        for d in ALL_DAYS:
            a = A[(y, d)]
            f = pd.DataFrame({"cycle": y, "d": d, "state": STATES, "has": a["has"], "recent": a["recent"], "n": a["n"],
                              "p": a["p"], "prior0": a["prior0"], "priorM": a["priorM"], "priorS": a["priorS"],
                              "v": a["v"], "result": a["result"]})
            for k, E in ests.items():
                f[k] = E[(y, d)]
            rows.append(f)
    return pd.concat(rows, ignore_index=True)


# ------------------------------------------------------------------------------------------------ run
def decide(A0, L, NF, shuffles=SHUFFLES):
    """The whole ladder on one table: every rung, the rule, the flags and the reports. Returns the output, the
    estimates of every rung and the table with M's priors."""
    A, lean_coefs = add_lean_priors(A0, lean_xy(L))
    out = {"rungs": {}, "fits": {}, "reports": {}}
    Eb, _ = rung(A, "base")
    EF, fF = rung(A, "F")
    EV, fV = rung(A, "V")
    out["fits"]["F"] = {f"{y}/{d}": v for (y, d), v in fF.items() if v}
    out["fits"]["V"] = {f"{y}/{d}": v for (y, d), v in fV.items() if v}
    out["fits"]["lean"] = {int(y): {k: [float(z) for z in b] for k, b in c.items()} for y, c in lean_coefs.items()}
    scored_fits = lambda f: [f[(y, d)] for y in SCORED for d in SCORE_DAYS]  # noqa: E731

    # rung 1: F against the baseline
    cF = clauses(Eb, EF, A, NF)
    cF["collapsed_to_baseline"] = bool(all(abs(v[0] - 1.0) < 1e-9 for v in scored_fits(fF)))
    cF["passes"] = bool(cF["passes_gain_and_elections"] and cF["p_signflip_10_units"] < 0.05 and not cF["collapsed_to_baseline"])
    cF["flags"]["4_any_pass_by_F"] = cF["passes"]
    cF["without_2004"]["passes_reported"] = bool(cF["without_2004"]["passes_gain_and_elections"]
                                                 and cF["without_2004"]["p_signflip_8_units"] < 0.05)
    out["rungs"]["F"] = cF
    below_V, E_below_V = ("F", EF) if cF["passes"] else ("baseline", Eb)

    # rung 2: V against F if F passed, otherwise against the baseline
    cV = clauses(E_below_V, EV, A, NF)
    cV["against"] = below_V
    cV["collapsed_to_F"] = bool(all(v[1] < BETA_ZERO for v in scored_fits(fV)))
    with_shuffles(cV, shuffled_gains_V(A, E_below_V, np.random.default_rng(0), shuffles))
    cV["passes"] = bool(cV["passes_gain_and_elections"] and cV["shuffle"]["beats_19_in_20"] and not cV["collapsed_to_F"])
    cV["against_baseline_reported"] = clauses(Eb, EV, A, NF) if below_V != "baseline" else None
    out["rungs"]["V"] = cV

    # rung 3: M against whichever of V or F stands
    standing = "V" if cV["passes"] else ("F" if cF["passes"] else None)
    ests = {"baseline": Eb, "F": EF, "V": EV}
    for kind in ("F", "V"):                                          # computed whatever stands, for the reports
        ests[f"M_{kind}"], fm = rung(A, kind, prior="priorM")
        ests[f"S_{kind}"], fs = rung(A, kind, prior="priorS")
        out["fits"][f"M_{kind}"] = {f"{y}/{d}": v for (y, d), v in fm.items() if v}
        out["fits"][f"S_{kind}"] = {f"{y}/{d}": v for (y, d), v in fs.items() if v}
    ests["M_baseline"], _ = rung(A, "base", prior="priorM")
    rc = report_c(L)
    out["reports"]["c_prior_alone_1988_2020"] = rc
    if standing is None:
        out["rungs"]["M"] = {"tested": False, "passes": False,
                             "why": "neither F nor V stands; M would change only states with no poll",
                             "reported_M_on_baseline": clauses(Eb, ests["M_baseline"], A, NF)}
    else:
        E_st = ests[standing]
        cM = clauses(E_st, ests[f"M_{standing}"], A, NF)
        cM["tested"] = True; cM["against"] = standing
        with_shuffles(cM, shuffled_gains_M(A0, L, E_st, standing, np.random.default_rng(1), shuffles))
        cM["passes"] = bool(cM["passes_gain_and_elections"] and cM["shuffle"]["beats_19_in_20"])
        cM["flags"]["5_worse_on_long_history"] = bool(rc["mean"]["M"] > rc["mean"]["previous_lean"])
        cS = clauses(E_st, ests[f"S_{standing}"], A, NF)
        cS["against"] = standing
        cS["judged_in_Ms_place"] = bool(cM["passes_gain_and_elections"] and not cM["shuffle"]["beats_19_in_20"])
        cS["passes"] = bool(cS["judged_in_Ms_place"] and cS["passes_gain_and_elections"] and cS["p_signflip_10_units"] < 0.05)
        cS["flags"]["4_any_pass_by_slope_alone"] = cS["passes"]
        cS["flags"]["5_worse_on_long_history"] = bool(rc["mean"]["slope_alone"] > rc["mean"]["previous_lean"])
        out["rungs"]["M"] = cM
        out["rungs"]["slope_alone"] = cS
    out["standing"] = {"below_V": below_V, "for_M": standing}

    # reports
    late = SCORED[1:]
    out["reports"]["a_gain_by_poll_count"] = {
        k: {"30_and_7_days": report_a(Eb, E, A, SCORE_DAYS, SCORED),
            "150_100_60_days_2008_2020": report_a(Eb, E, A, REPORT_DAYS, late)} for k, E in ests.items() if k != "baseline"}
    out["reports"]["d_by_size_of_prior"] = {k: report_d(E, A) for k, E in ests.items()}
    out["reports"]["f_by_election"] = {k: {int(y): float(v) for y, v in scores(E, A).items()} for k, E in ests.items()}
    out["reports"]["f_by_date"] = {k: {int(d): float(scores(E, A, days=(d,)).mean()) for d in SCORE_DAYS}
                                   for k, E in ests.items()}
    out["reports"]["early_dates_2008_2020"] = {k: float(scores(E, A, days=REPORT_DAYS, years=late).mean())
                                               for k, E in ests.items()}
    out["reports"]["counts"] = {f"{y}/{d}": {g: int((group_of(A[(y, d)]) == g).sum()) for g in GROUPS}
                                for y in SCORED for d in ALL_DAYS}
    return out, ests, A


def run():
    q, R, Nd, L, votes = load_all()
    NF = national_forecast()
    A0 = assemble(poll_cells(q), Nd, R, L, votes)
    out, ests, A = decide(A0, L, NF)
    frame_csv(A, ests).to_csv(OUT / "pres_prior_frame.csv", index=False)
    (OUT / "pres_prior.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


# ------------------------------------------------------------------------------------------------ checks
def _all_estimates(A0, L):
    """Every rung's estimates and fitted numbers, as one flat dict of arrays, for comparing two runs."""
    A, coef = add_lean_priors(A0, lean_xy(L))
    got = {}
    for name, kind, prior in (("base", "base", "prior0"), ("F", "F", "prior0"), ("V", "V", "prior0"),
                              ("M_F", "F", "priorM"), ("M_V", "V", "priorM"), ("S_F", "F", "priorS"),
                              ("M_base", "base", "priorM")):
        E, f = rung(A, kind, prior=prior)
        for c in E:
            got[(name, "est") + c] = E[c]
            got[(name, "fit") + c] = np.array(f[c] if f[c] else [np.nan])
    for y, c in coef.items():
        got[("lean", "coef", y, 0)] = np.concatenate([c["M"], c["S"]])
    return got


def _same(a, b, keys):
    return all(np.allclose(a[k], b[k], atol=1e-7, rtol=1e-7, equal_nan=True) for k in keys)


def checks():
    q, R, Nd, L, votes = load_all()
    print("2024 absent from the polls, the results, the national series and the lean history: PASS")
    pc = poll_cells(q)
    A0 = assemble(pc, Nd, R, L, votes)
    ref = _all_estimates(A0, L)
    ok = {}

    # leak and deletion: polls of an election ending on or after a date, and its national readings within 3 days of
    # the date, change no estimate and no fit at that date, in that election or any other
    bad = 0
    for y in FIT_ONLY + SCORED:
        el = q[q.cycle == y].election.iloc[0]
        for d in (SCORE_DAYS if y in FIT_ONLY else (30, 7, 100)):
            t = el - pd.Timedelta(days=d)
            q2 = q.copy(); q2.loc[(q2.cycle == y) & (q2.end >= t), "m"] += 50
            q3 = q[~((q.cycle == y) & (q.end >= t))]
            N2 = {k: dict(v) for k, v in Nd.items()}
            m = Nd[y]["m"].copy(); m[Nd[y]["t"] < d + TS.LAG] += 50; N2[y]["m"] = m
            keys = [k for k in ref if k[0] != "lean" and k[3] == d]
            for qq, NN in ((q2, N2), (q3, Nd)):
                pc2 = dict(pc); pc2[(y, d)] = poll_cell(qq, y, d)
                got = _all_estimates(assemble(pc2, NN, R, L, votes), L)
                bad += int(not _same(ref, got, keys))
    ok["leak and deletion tests"] = not bad
    # the test has teeth: polls that ended before the date do move the estimates at that date
    y, d = 2016, 30
    t = q[q.cycle == y].election.iloc[0] - pd.Timedelta(days=d)
    # (half the states only: a move shared by every state is absorbed by the fit's constant for the election)
    q4 = q.copy(); q4.loc[(q4.cycle == y) & (q4.end < t) & (q4.geo < "M"), "m"] += 50
    pc4 = dict(pc); pc4[(y, d)] = poll_cell(q4, y, d)
    got = _all_estimates(assemble(pc4, Nd, R, L, votes), L)
    ok["polls before the date do move the estimates"] = not _same(ref, got, [("base", "est", y, d)])
    ok["and the later elections' fits"] = not _same(ref, got, [("F", "fit", 2020, d)]) and         not _same(ref, got, [("V", "fit", 2020, d)])

    # the scored election's own results change no estimate and no fitted number for that election
    bad = 0
    for y in SCORED:
        R2 = {k: ((v[0] + 20, v[1] + 5, v[2] + 15) if k[0] == y else v) for k, v in R.items()}
        L2 = dict(L); L2.update({k: v + 15 for k, v in L.items() if k[0] == y})
        got = _all_estimates(assemble(pc, Nd, R2, L2, votes), L2)
        keys = [k for k in ref if (k[0] != "lean" and k[2] == y) or (k[0] == "lean" and k[2] == y)]
        bad += int(not _same(ref, got, keys))
    ok["own results changed, estimates and fits unchanged"] = not bad

    # behaviour on made-up inputs
    A, _ = add_lean_priors(A0, lean_xy(L))
    E1, _ = rung(A, "F", fixed=1.0); Eb, _ = rung(A, "base")
    ok["w = 1 gives the baseline"] = all(np.allclose(E1[c], Eb[c]) for c in Eb)
    E0, _ = rung(A, "F", fixed=0.0)
    ok["w = 0 gives the prior"] = all(np.allclose(E0[c], A[c]["prior0"]) for c in E0 if train_cells(*c))
    EVf, _ = rung(A, "V", fixed=(0.5, 0.0)); EFf, _ = rung(A, "F", fixed=1 / 1.5)
    ok["V with beta = 0 equals F"] = all(np.allclose(EVf[c], EFf[c]) for c in EFf)
    # planted weights: results rebuilt as prior + w (p - prior) + a constant per election
    rng = np.random.default_rng(7)

    def planted(wfun):
        B = {}
        for c, a in A.items():
            miss = rng.normal(0, 3)                                 # the election's shared miss
            m = a["has"]
            res = a["prior0"] + miss
            res[m] = a["prior0"][m] + wfun(a["n"][m]) * (a["p"][m] - a["prior0"][m]) + miss
            B[c] = dict(a, result=res)
        return B
    B = planted(lambda n: 0.6)
    ok["a planted fixed weight is recovered"] = all(abs(fit_F(B, train_cells(y, d), "prior0") - 0.6) < 1e-6
                                                    for y in SCORED for d in SCORE_DAYS)
    B = planted(lambda n: w_V((0.3, 2.0), n))
    ok["a planted alpha and beta are recovered"] = all(
        np.allclose(fit_V(B, train_cells(y, d), "prior0"), (0.3, 2.0), atol=1e-4) for y in (2008, 2020) for d in SCORE_DAYS)
    # M with b1 = 1 and b2 = 0 equals the previous lean; planted slopes are recovered
    XY = lean_xy(L)
    x1, x2, _ = XY[2012]
    ok["M with b1 = 1 and b2 = 0 is the previous lean"] = np.allclose(0.0 + 1.0 * x1 + 0.0 * x2, [L[(2008, s)] for s in STATES])
    Lp = dict(L)
    for t in range(LEAN_FROM, 2021, 4):
        for s in STATES:
            Lp[(t, s)] = 1.5 + 0.9 * Lp[(t - 4, s)] - 0.2 * Lp[(t - 8, s)]
    ok["planted lean slopes are recovered"] = np.allclose(lean_coef(lean_xy(Lp), 2012), (1.5, 0.9, -0.2), atol=1e-6)
    # shuffles keep the same set of values within each election and date
    Bs = shuffle_n(A, np.random.default_rng(3).permutation)
    ok["the n shuffle keeps the values"] = all(np.allclose(np.sort(Bs[c]["n_sh"]), np.sort(A[c]["n"])) and
                                               np.allclose(Bs[c]["n_sh"][~A[c]["has"]], 0) for c in A)
    XYs = lean_xy(L, lean_perms(np.random.default_rng(4).permutation))
    ok["the lean shuffle keeps the changes and the last lean"] = all(
        np.allclose(np.sort(XYs[t][0] - XYs[t][1]), np.sort(XY[t][0] - XY[t][1])) and np.allclose(XYs[t][0], XY[t][0])
        and np.allclose(XYs[t][2], XY[t][2]) for t in XY)
    # the lean error ignores a constant added to every state
    c = (2016, 7)
    ok["the lean error ignores an even shift"] = abs(cell_loss(Eb[c], A[c]) - cell_loss(Eb[c] + 3.7, A[c])) < 1e-9
    # 2000 is in the fits at 30 and 7 days and nowhere else; 2004 has no fit at the earlier dates
    ok["fit elections are the earlier ones"] = (train_cells(2004, 30) == [(2000, 30)] and train_cells(2004, 100) == []
                                                and train_cells(2008, 100) == [(2004, 100)]
                                                and train_cells(2020, 7) == [(e, 7) for e in (2000, 2004, 2008, 2012, 2016)])
    # an identity "shuffle" reproduces V and M exactly; a real one changes the fit and the scored estimate
    EV, fV = rung(A, "V", days=SCORE_DAYS)
    Ei, fi = rung(shuffle_n(A, lambda x: x), "V", nkey="n_sh", days=SCORE_DAYS)
    Er, fr = rung(Bs, "V", nkey="n_sh", days=SCORE_DAYS)
    c = (2016, 7)
    ok["an identity shuffle of n reproduces V; a real one changes it"] = (
        all(np.allclose(EV[k], Ei[k]) for k in EV) and fV == fi
        and not np.allclose(EV[c], Er[c]) and not np.allclose(fV[c], fr[c]))
    Am, _ = add_lean_priors(A0, lean_xy(L))
    Ai, _ = add_lean_priors(A0, lean_xy(L, lean_perms(np.arange)))
    Ar, _ = add_lean_priors(A0, XYs)
    ok["an identity shuffle of the lean change reproduces M; a real one changes it"] = (
        all(np.allclose(Am[k]["priorM"], Ai[k]["priorM"]) for k in Am) and not np.allclose(Am[c]["priorM"], Ar[c]["priorM"])
        and np.allclose(Am[c]["priorS"], Ar[c]["priorS"]))

    # the decision path, on planted results (30 shuffles): what stands, the collapse, the fallback and the flags
    NF = national_forecast()
    o1, _e, _a = decide(planted(lambda n: w_V((0.3, 2.0), n)), L, NF, shuffles=30)
    ok["planted alpha and beta: F passes and is flagged, V passes against F, M fails"] = bool(
        o1["rungs"]["F"]["passes"] and o1["rungs"]["F"]["flags"]["4_any_pass_by_F"] and o1["rungs"]["V"]["passes"]
        and o1["rungs"]["V"]["against"] == "F" and o1["standing"]["for_M"] == "V" and o1["rungs"]["M"]["tested"]
        and not o1["rungs"]["M"]["passes"] and not o1["rungs"]["slope_alone"]["passes"]
        and o1["rungs"]["V"]["without_2004"]["passes_reported"])
    o2, _e, _a = decide(planted(lambda n: 0.6), L, NF, shuffles=30)
    ok["a planted fixed weight: F passes, V collapses to F or fails its shuffle"] = bool(
        o2["rungs"]["F"]["passes"] and not o2["rungs"]["V"]["passes"] and o2["standing"]["for_M"] == "F"
        and not o2["rungs"]["M"]["passes"])

    def planted_leans(b1, b2):
        """Leans from 1980 follow the rule exactly; each election's results are those leans plus one number."""
        Lp = dict(L)
        for t in range(LEAN_FROM, 2021, 4):
            for st in STATES:
                Lp[(t, st)] = b1 * Lp[(t - 4, st)] + b2 * Lp[(t - 8, st)]
        Rp = {k: ((v[1] + Lp[k], v[1], Lp[k]) if k[0] >= 1992 else v) for k, v in R.items()}
        return assemble(pc, Nd, Rp, Lp, votes), Lp
    A3, L3 = planted_leans(0.9, -0.4)
    o3, _e, _a = decide(A3, L3, NF, shuffles=30)
    ok["a planted trend in lean: M passes with no flag 5"] = bool(
        o3["rungs"]["M"].get("tested", False) and o3["rungs"]["M"]["passes"]
        and not o3["rungs"]["M"]["flags"]["5_worse_on_long_history"] and not o3["rungs"]["slope_alone"]["passes"])
    A4, L4 = planted_leans(0.8, 0.0)
    o4, _e, _a = decide(A4, L4, NF, shuffles=30)
    ok["a planted slope with no trend: M fails its shuffle; the slope alone is judged, passes and is flagged"] = bool(
        o4["rungs"]["M"].get("tested", False) and not o4["rungs"]["M"]["passes"]
        and o4["rungs"]["slope_alone"]["judged_in_Ms_place"] and o4["rungs"]["slope_alone"]["passes"]
        and o4["rungs"]["slope_alone"]["flags"]["4_any_pass_by_slope_alone"])
    Anone = {k: dict(a, result=np.where(a["has"], a["p"], a["prior0"])) for k, a in A0.items()}
    o5, _e, _a = decide(Anone, L, NF, shuffles=30)
    ok["results equal to the baseline: nothing passes and M is not tested"] = bool(
        not o5["rungs"]["F"]["passes"] and not o5["rungs"]["V"]["passes"] and o5["standing"]["for_M"] is None
        and not o5["rungs"]["M"]["tested"])
    json.dumps(o1, default=float)                                    # the output serialises
    for k, v in ok.items():
        print(f"{k}: {'PASS' if v else 'FAIL'}")
    if not all(ok.values()):
        raise SystemExit("a check failed")


if __name__ == "__main__":
    {"checks": checks, "run": run}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
