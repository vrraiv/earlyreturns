"""Single-race forecast on any date: a House special election or an off-cycle governor race (PLAN.md, "After the
scorecard", item 5). Uses only what was known before the race's date.

House special (open seat):
  environment  the off-cycle estimate on the date (src/model/environment.py: approval, last House vote) with m for
               the half of the presidential term, fitted on earlier specials only (src/model/special_model.py), plus
               the shrunk mean miss of specials in the prior 12 months (n / (n + 2)).
  prior        the frozen House district model: const + b * lean2 + g * environment (+ incumbency if one runs).
  polls        optional: two-party average, SD sqrt(8.06^2 + max(spread, 4)^2 / n) (district-poll error estimated in
               house_structure.py), precision-weighted against the prior.
  error        t (3.9 df) with SD = the RMS of earlier specials' own prospective forecast errors.
Senate special (off the general-election day; SP-3, decided 2026-11-26, SPECIALS.md section 1):
  lean         the state's lean in the last federal general election before the date (presidential margin minus the
               nation's, or after a midterm the state's House vote margin minus the national House margin).
  environment  the off-cycle fundamentals estimate on the date at m = 1 (F1).
  prior        lean + environment + 2 x incumbency (+1 a sitting senator from the state runs as a Democrat, -1 as a
               Republican), the frozen Senate prior's form.
  polls        optional (SP-4, SPECIALS.md section 2, rule 9): all polls, unshifted, two-party average with the frozen
               forecast's statewide SD sqrt(a^2 + b^2 / n) (data/final/calibration.json pollavg_sd_by_n, n the plain
               count), precision-weighted against 18. The House test settled on all polls unshifted (P1).
  error        t (3.9 df), SD 18: measured on the 13 Senate specials 1972-2021 (F1, RMSE 17.9), so chosen from the
               same results it is checked on.
Governor (off-cycle): the governor model's prior, poll weight and national factors (src/model/governor_model.py),
fitted on races before the date; environment from the same estimator with the governor term-year m.

Run:
  python src/model/single_race.py house --state TN --district 7 --date 2025-12-02 [--poll 45,52 ...] [--pvi -10]
  python src/model/single_race.py senate --state MN --date 2027-11-02 [--inc 0] [--lean -2.5] [--poll 48,45 ...]
  python src/model/single_race.py governor --state VA --date 2025-11-04 [--inc 0] [--poll 52,46 ...] [--votehub]
  python src/model/single_race.py backtest     every House special 2007-2026 in date order, strictly prospective
Writes data/processed/single_race_backtest.json (backtest) and prints the forecast otherwise.

A live special (SP-7, SPECIALS.md section 5): `--save <race>` reads the race's record, data/specials/<race>.json (or a
path to one), takes the state, seat, election date and incumbency from it, and, unless --poll is given, the polls
entered in it under SP-4's window (ending in the 21 days before election day, else 22 to 60 days before; only those
ending on or before the run date). The run is appended to the record's "runs"; --asof sets the run date (default
today), --lock marks the last run before election day. Nothing in the model changes.
  python src/model/single_race.py senate --save mn-senate-2027
  python src/model/single_race.py house --save data/specials/dry_runs/tn-07-2025.json --asof 2025-12-01 --lock
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
import environment as E  # noqa: E402
import special_model as SM  # noqa: E402

OUT = ROOT / "data" / "processed"
HS = SM.HS
SD_DISTRICT_POLL = float(json.loads((ROOT / "data/final/house_structure.json").read_text())["district_polls"]["implied_poll_sd"])
DF_T = float(json.loads((OUT / "poll_settings.json").read_text())["chosen"]["df_t"])
T_SCALE = np.sqrt((DF_T - 2) / DF_T)
K_RECENT, MIN_HALF, MIN_SD_N, SD_FALLBACK = 2, 8, 15, 15.0
# error shape for House specials, chosen by the prospective backtest (log score of the margins); None = normal.
# Specials' errors are broad in the middle: a fat-tailed t matched to the same SD puts too much mass near zero.
SPECIAL_DF = None
_SPECIALS = None


def specials():
    global _SPECIALS
    if _SPECIALS is None:
        d = SM.load().sort_values("date").reset_index(drop=True)
        d["half2"] = (d.term_year >= 3).astype(int)
        _SPECIALS = d
    return _SPECIALS


def dist(df):
    """Unit-variance error distribution: t with df degrees of freedom, or normal (df None)."""
    return stats.norm() if df is None else stats.t(df, scale=np.sqrt((df - 2) / df))


def p_win(mu, sd, df=DF_T):
    return float(dist(df).cdf(mu / sd))


def interval(mu, sd, q, df=DF_T):
    z = dist(df).ppf(0.5 + q / 2) * sd
    return mu - z, mu + z


# ---------------- environment on a date ----------------
def special_environment(date, earlier=None, k=K_RECENT):
    """Environment for a House special on `date`, from specials strictly before it."""
    date = pd.Timestamp(date)
    sp = specials()
    earlier = sp[sp.date < date] if earlier is None else earlier
    model = E.fit(E.training())
    e0, info = E.env_on(date, "fund", 0.0, model)
    slope = E.env_on(date, "fund", 1.0, model)[0] - e0
    half = int(SM.term_year(date) >= 3)
    m = {}
    for h in (0, 1):
        x = earlier[earlier.half2 == h]
        m[h] = SM.best_m(x) if len(x) >= MIN_HALF else 1.0
    base_env = e0 + slope * m[half]
    recent = earlier[earlier.date >= date - pd.Timedelta(days=365)]
    shift = 0.0
    if len(recent):
        resid = (recent.implied_env - (recent.e0 + recent.slope * recent.half2.map(m))).mean()
        shift = float(resid * len(recent) / (len(recent) + k))
    return {"env": base_env + shift, "env_estimate": base_env, "recent_specials_shift": shift, "n_recent": int(len(recent)),
            "m": m[half], "term_year": SM.term_year(date), "e0": e0, "slope": slope, **info}


def poll_average(polls):
    """polls: [(d_pct, r_pct)] -> (two-party average, SD of the average, n)."""
    if not polls:
        return None, None, 0
    m = np.array([100 * (d - r) / (d + r) for d, r in polls])
    spread = max(float(m.std(ddof=0)), 4.0)
    return float(m.mean()), float(np.sqrt(SD_DISTRICT_POLL ** 2 + spread ** 2 / len(m))), len(m)


def house_forecast(date, lean2, polls=(), inc=0, sd=None, earlier=None):
    date = pd.Timestamp(date)
    env = special_environment(date, earlier)
    prior = HS["const"] + HS["b_lean2"] * lean2 + HS["g_nat"] * env["env"] + HS.get("inc", 0.0) * inc
    sd_prior = sd if sd is not None else house_sd(date)
    pa, sd_p, n = poll_average(list(polls))
    if pa is None:
        mu, s, w = prior, sd_prior, 0.0
    else:
        w = sd_prior ** 2 / (sd_prior ** 2 + sd_p ** 2)
        mu, s = w * pa + (1 - w) * prior, 1 / np.sqrt(1 / sd_p ** 2 + 1 / sd_prior ** 2)
    return {"date": str(date.date()), "lean2": lean2, "environment": env, "prior": prior, "sd_prior": sd_prior,
            "poll_avg": pa, "n_polls": n, "poll_weight": w, "mu": mu, "sd": s, "p_dem": p_win(mu, s, SPECIAL_DF),
            "interval_80": interval(mu, s, 0.8, SPECIAL_DF), "error_shape": "normal" if SPECIAL_DF is None else f"t({SPECIAL_DF})"}


def house_sd(date):
    """RMS of the prospective forecast errors of specials before the date (from the backtest file)."""
    p = OUT / "single_race_backtest.json"
    if not p.exists():
        return SD_FALLBACK
    r = pd.DataFrame(json.loads(p.read_text())["races"])
    e = r[pd.to_datetime(r.date) < pd.Timestamp(date)].err
    return float(np.sqrt((e ** 2).mean())) if len(e) >= MIN_SD_N else SD_FALLBACK


# ---------------- Senate special (off-cycle) ----------------
SD_SENATE_SPECIAL = 18.0
_CAL = json.loads((ROOT / "data/final/calibration.json").read_text())["pollavg_sd_by_n"]
SD_STATE_A, SD_STATE_B = float(_CAL["a"]), float(_CAL["b"])


def senate_lean(state, date):
    """L1: the state's lean in the last federal general election before the date (src/collect/senate_specials.py)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("collect_senate_specials", HERE.parent / "collect" / "senate_specials.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        out = mod.lean_for(state, pd.Timestamp(date))
    except (KeyError, IndexError):
        raise SystemExit(f"no lean for {state} before {pd.Timestamp(date).date()}: the last election's results are not in the repo's files; pass --lean")
    if out["lean"] is None or not np.isfinite(out["lean"]):
        raise SystemExit(f"no lean for {state} from the {out['lean_year']} election in the repo's files; pass --lean")
    return out


def senate_forecast(state, date, inc=0, lean=None, polls=()):
    date = pd.Timestamp(date)
    info = {"lean_year": None, "lean_kind": "given"} if lean is not None else senate_lean(state, date)
    lean = float(lean) if lean is not None else float(info["lean"])
    model = E.fit(E.training())
    env, einfo = E.env_on(date, "fund", 1.0, model)
    if not np.isfinite(env):
        raise SystemExit(f"no environment estimate on {date.date()} (approval or the last House vote not in the repo yet)")
    last_even = max(y for y in range(1946, date.year + 1, 2) if pd.Timestamp(f"{y}-11-01") < date)
    if einfo.get("prev_year") is not None and einfo["prev_year"] < last_even:
        raise SystemExit(f"the environment would use the {einfo['prev_year']} House vote, but the {last_even} vote is not in the repo yet")
    prior = lean + env + 2 * inc
    sp = SD_SENATE_SPECIAL
    pl = list(polls)
    if pl:
        pa, n = float(np.mean([100 * (d - r) / (d + r) for d, r in pl])), len(pl)
        sdp = float(np.sqrt(SD_STATE_A ** 2 + SD_STATE_B ** 2 / n))
        w = sp ** 2 / (sp ** 2 + sdp ** 2)
        mu, s = w * pa + (1 - w) * prior, float(1 / np.sqrt(1 / sdp ** 2 + 1 / sp ** 2))
    else:
        pa, n, w, mu, s = None, 0, 0.0, prior, sp
    return {"date": str(date.date()), "lean": lean, "lean_year": info["lean_year"], "lean_kind": info["lean_kind"], "inc": inc,
            "environment": {"env": env, "m": 1.0, "term_year": SM.term_year(date), **einfo}, "prior": prior, "poll_avg": pa,
            "n_polls": n, "poll_weight": w, "mu": mu, "sd": s, "p_dem": p_win(mu, s, DF_T), "interval_80": interval(mu, s, 0.8, DF_T),
            "error_shape": f"t({DF_T})"}


# ---------------- governor (off-cycle) ----------------
def governor_forecast(state, date, inc=0, polls=(), dem=None, rep=None, use_votehub=False):
    import governor_model as GV
    date = pd.Timestamp(date)
    GV.GEN = GV.generic_final()
    d = GV.load()
    train = d[d.year < date.year]
    P = GV.estimate(train, "lean_avg2")
    pres = pd.read_csv(ROOT / "data/interim/state_presidential.csv").set_index(["year", "state"]).lean_2p
    py = max(y for y in range(1992, 2025, 4) if pd.Timestamp(f"{y}-11-15") < date)
    lean = np.nanmean([pres.get((py, state), np.nan), pres.get((py - 4, state), np.nan)])
    model = E.fit(E.training())
    e0, info = E.env_on(date, "fund", 0.0, model)
    slope = E.env_on(date, "fund", 1.0, model)[0] - e0
    ty = GV.term_year(date.year) if date.year % 2 == 1 else None
    m = GV.fit_offcycle_m(train, P)[ty] if ty else (1.0 if date.year % 4 == 2 else 0.0)
    env = e0 + slope * m
    row = pd.DataFrame({"lean_avg2": [lean], "lean_prev": [pres.get((py, state), np.nan)], "inc": [inc], "env": [env],
                        "prev_gov_margin": [np.nan]})
    prior = float(GV.prior_pred(P["prior"], row, P["fallback"]).iloc[0])
    pl = list(polls)
    if use_votehub:
        pl += votehub_governor_polls(state, date, dem, rep)
    sp = P["sd_prior_implied"]
    if pl:
        vals = [100 * (a - b) / (a + b) for a, b in pl]
        pa, n = float(np.mean(vals)), len(vals)
        sdp = float(GV.sd_poll(n))
        w = sp ** 2 / (sp ** 2 + sdp ** 2)
        mu, s_race = w * pa + (1 - w) * prior, 1 / np.sqrt(1 / sdp ** 2 + 1 / sp ** 2)
    else:
        pa, n, w, mu, s_race = None, 0, 0.0, prior, P["sd_prior_robust"]
    # national factors: statewide-poll miss (weight w) and environment error (weight 1-w), correlated rho
    a, b = w * P["sd_S"], (1 - w) * P["g_env"] * GV.ENV_SD
    s = float(np.sqrt(s_race ** 2 + a ** 2 + b ** 2 + 2 * P["rho"] * a * b))
    return {"state": state, "date": str(date.date()), "lean_avg2": float(lean), "inc": inc,
            "environment": {"env": env, "e0": e0, "slope": slope, "m": m, "term_year": ty, **info},
            "prior": prior, "poll_avg": pa, "n_polls": n, "poll_weight": w, "mu": mu, "sd": s,
            "p_dem": p_win(mu, s), "interval_80": interval(mu, s, 0.8)}


def votehub_governor_polls(state, date, dem, rep):
    """VoteHub governor polls for the race ending in the 21 days before the date (the backtest's poll rule)."""
    from common import latest  # noqa: E402
    from wiki import STATE_ABBR  # noqa: E402
    name = next(k for k, v in STATE_ABBR.items() if v == state)
    vh = json.loads(latest("votehub", "polls.json").read_text(encoding="utf-8"))
    last = lambda s: str(s).split()[-1].lower()
    out = []
    for x in vh:
        if x.get("poll_type") != "governor" or x.get("subject") != f"{date.year} {name}":
            continue
        if not (date - pd.Timedelta(days=21) <= pd.Timestamp(x["end_date"]) < date):
            continue
        a = {last(y["choice"]): y["pct"] for y in x["answers"]}
        if dem and rep and last(dem) in a and last(rep) in a:
            out.append((a[last(dem)], a[last(rep)]))
    return out


# ---------------- backtest ----------------
def backtest():
    """Every House special in date order, each forecast from earlier specials only (no polls: none are collected)."""
    sp = specials()
    rows = []
    for i, r in sp.iterrows():
        earlier = sp.iloc[:i]
        earlier = earlier[earlier.date < r.date]
        if len(earlier) < MIN_HALF:
            continue
        prev = [x["err"] for x in rows]
        sd = float(np.sqrt(np.mean(np.square(prev)))) if len(prev) >= MIN_SD_N else SD_FALLBACK
        f = house_forecast(r.date, r.lean2, (), 0, sd, earlier)
        base = HS["const"] + HS["b_lean2"] * r.lean2 + HS["g_nat"] * r.prev_vote          # naive: last House vote
        rows.append({"date": str(r.date.date()), "race": f"{r.state}-{int(r.district)}", "actual": r.margin_2p, "mu": f["mu"],
                     "sd": sd, "err": r.margin_2p - f["mu"], "p_dem": f["p_dem"], "y": int(r.margin_2p > 0),
                     "naive_mu": base, "naive_p": p_win(base, sd, SPECIAL_DF), "env": f["environment"]["env"],
                     "recent_shift": f["environment"]["recent_specials_shift"]})
    b = pd.DataFrame(rows)
    shapes = {}
    for name, df in (("t(3.9)", DF_T), ("t(10)", 10.0), ("normal", None)):
        z = b.err / b.sd
        pit = dist(df).cdf(z)
        shapes[name] = {"log_score": float(np.mean(dist(df).logpdf(z) - np.log(b.sd))),
                        "brier": float(((dist(df).cdf(b.mu / b.sd) - b.y) ** 2).mean()),
                        **{f"cover_{int(q * 100)}": float(((pit >= 0.5 - q / 2) & (pit <= 0.5 + q / 2)).mean()) for q in (0.5, 0.8, 0.95)}}
    b["pit"] = dist(SPECIAL_DF).cdf(b.err / b.sd)
    sc = lambda p: {"brier": float(((b[p] - b.y) ** 2).mean()),
                    "log_loss": float(-(b.y * np.log(b[p].clip(1e-4, 1 - 1e-4)) + (1 - b.y) * np.log((1 - b[p]).clip(1e-4, 1 - 1e-4))).mean()),
                    "accuracy": float(((b[p] > 0.5) == (b.y == 1)).mean())}
    cov = {f"{int(q * 100)}%": float(((b.pit >= 0.5 - q / 2) & (b.pit <= 0.5 + q / 2)).mean()) for q in (0.5, 0.8, 0.95)}
    out = {"n": len(b), "model": {**sc("p_dem"), "rmse": float(np.sqrt((b.err ** 2).mean())), "mae": float(b.err.abs().mean()),
                                  "mean_err": float(b.err.mean())},
           "naive_last_house_vote": {**sc("naive_p"), "rmse": float(np.sqrt(((b.actual - b.naive_mu) ** 2).mean()))},
           "interval_coverage": cov, "error_shapes": shapes, "error_shape_used": "normal" if SPECIAL_DF is None else f"t({SPECIAL_DF})",
           "races": b.round(3).to_dict("records"),
           "note": "strictly prospective: environment m, recent-specials term and error SD use only earlier specials"}
    (OUT / "single_race_backtest.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"{len(b)} specials, forecast in date order from earlier specials only")
    print("model:", {k: round(v, 3) for k, v in out["model"].items()})
    print("naive (last House vote):", {k: round(v, 3) for k, v in out["naive_last_house_vote"].items()})
    print("interval coverage (nominal 50/80/95):", {k: round(v, 2) for k, v in cov.items()})
    print("error shapes:"); print(pd.DataFrame(shapes).T.round(3).to_string())
    print(b[b.date >= "2025-01-01"][["date", "race", "actual", "mu", "sd", "p_dem", "env", "recent_shift"]].round(1).to_string(index=False))


def lookup_lean2(state, district, date):
    """2 x Cook PVI on the lines in force on the date (House history; 2026 lines after the 2026 general)."""
    date = pd.Timestamp(date)
    if date > pd.Timestamp("2026-11-03"):
        r = pd.read_csv(ROOT / "data/interim/house_2026_races.csv")
        return 2 * float(r[(r.state == state) & (r.district == district)].pvi.iloc[0])
    h = pd.read_csv(ROOT / "data/interim/house_history.csv")
    y = max(yy for yy in range(2006, 2027, 2) if pd.Timestamp(f"{yy}-11-01") < date)
    return 2 * float(h[(h.year == y) & (h.state == state) & (h.district == district)].pvi.iloc[0])


def show(f, actual=None):
    e = f["environment"]
    print(f"environment D{e['env']:+.1f}  (estimate {e.get('env_estimate', e['env']):+.1f}: approval {e.get('approval', float('nan')):.1f}, "
          f"term year {e['term_year']}, m {e['m']:.2f}" + (f"; recent specials {e['recent_specials_shift']:+.1f} from {e['n_recent']})" if "n_recent" in e else ")"))
    print(f"prior D{f['prior']:+.1f}" + (f"  | polls D{f['poll_avg']:+.1f} (n={f['n_polls']}, weight {f['poll_weight']:.2f})" if f["poll_avg"] is not None else "  | no polls"))
    lo, hi = f["interval_80"]
    print(f"forecast margin D{f['mu']:+.1f}  (80%: {lo:+.1f} to {hi:+.1f}; SD {f['sd']:.1f})  P(Democrat wins) {f['p_dem']:.0%}"
          + (f"  | actual D{actual:+.1f}" if actual is not None else ""))


# ---------------- a live special's record (SP-7) ----------------
RECORDS = ROOT / "data" / "specials"
WINDOW, FALLBACK = 21, 60        # SP-4 rule 2


def record_path(race):
    p = Path(race)
    return p if p.suffix == ".json" else RECORDS / f"{race}.json"


def window_polls(polls, election, asof):
    """SP-4 rule 2 as of a run date: polls ending before election day and on or before the run date, in the 21 days
    before election day, else 22 to 60 days before. Returns the polls used and the window."""
    election, asof = pd.Timestamp(election), pd.Timestamp(asof)
    seen = [p for p in polls if pd.Timestamp(p["end"]) < election and pd.Timestamp(p["end"]) <= asof]
    days = lambda p: (election - pd.Timestamp(p["end"])).days
    near = [p for p in seen if days(p) <= WINDOW]
    if near:
        return near, f"1-{WINDOW} days"
    return [p for p in seen if WINDOW < days(p) <= FALLBACK], f"{WINDOW + 1}-{FALLBACK} days"


def save_run(path, rec, kind, f, asof, used, window, lock):
    df = SPECIAL_DF if kind == "house" else DF_T
    mu, sd = f["mu"], f["sd"]
    r2 = lambda x: None if x is None else round(float(x), 2)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ""
    e = f["environment"]
    run = {"run_date": str(pd.Timestamp(asof).date()), "election_date": f["date"], "branch": kind,
           "lean": r2(f["lean"] if kind == "senate" else f["lean2"]),
           "lean_source": (f"{f['lean_kind']}, {f['lean_year']}" if kind == "senate" and f["lean_year"] else
                           "given" if kind == "senate" else "2 x Cook PVI, lines in force"),
           "environment": r2(e["env"]), "inc": rec.get("inc", 0), "prior": r2(f["prior"]),
           "polls_used": [p["pollster"] + ", " + p["end"] for p in used], "poll_window": window if used else None,
           "poll_avg": r2(f["poll_avg"]), "poll_weight": r2(f["poll_weight"]),
           "margin": r2(mu), "sd": r2(sd), "error_shape": f["error_shape"], "p_dem": round(float(f["p_dem"]), 4),
           "intervals": {str(int(q * 100)): [r2(x) for x in interval(mu, sd, q, df)] for q in (0.5, 0.8, 0.95)},
           "commit": commit, "locked": bool(lock)}
    rec.setdefault("runs", []).append(run)
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved run {run['run_date']} to {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["house", "senate", "governor", "backtest"])
    ap.add_argument("--state"); ap.add_argument("--district", type=int, default=0); ap.add_argument("--date")
    ap.add_argument("--pvi", type=float, help="Cook PVI (D positive); default: looked up for the lines in force")
    ap.add_argument("--inc", type=int, default=0, help="+1 Democratic incumbent running, -1 Republican, 0 open")
    ap.add_argument("--lean", type=float, help="Senate: state lean as a D-R margin; default: the last federal election")
    ap.add_argument("--poll", action="append", default=[], help="'D,R' percentages; repeat for each poll")
    ap.add_argument("--dem"); ap.add_argument("--rep"); ap.add_argument("--votehub", action="store_true")
    ap.add_argument("--save", help="a live special's record (SP-7): race name or path; the run is appended to it")
    ap.add_argument("--asof", help="with --save: the run date (default today); polls ending after it are left out")
    ap.add_argument("--lock", action="store_true", help="with --save: the last run before election day")
    a = ap.parse_args()
    polls = [tuple(float(x) for x in p.split(",")) for p in a.poll]
    if a.kind == "backtest":
        return backtest()
    rec = used = window = None
    if a.save:
        if a.kind not in ("house", "senate"):
            raise SystemExit("--save takes house or senate")
        path = record_path(a.save)
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec["branch"] != a.kind:
            raise SystemExit(f"{path.name} is a {rec['branch']} race")
        a.state, a.date, a.inc = rec["state"], rec["rounds"][-1]["date"], rec.get("inc", 0)
        a.district = rec.get("district") or 0
        if a.lean is None and rec.get("lean") is not None:
            a.lean = rec["lean"]
        if len(str(a.date)) != 10:
            raise SystemExit(f"{path.name}: election date {a.date} is not a full date; confirm it with the state first")
        asof = a.asof or str(dt.date.today())
        if pd.Timestamp(asof) >= pd.Timestamp(a.date):
            raise SystemExit(f"run date {asof} is not before election day {a.date}")
        if polls:
            used, window = [{"pollster": "given", "end": asof, "dem": d, "rep": r} for d, r in polls], "given"
        else:
            used, window = window_polls(rec.get("polls", []), a.date, asof)
            polls = [(p["dem"], p["rep"]) for p in used]
    if a.kind == "house":
        lean2 = 2 * a.pvi if a.pvi is not None else lookup_lean2(a.state, a.district, a.date)
        f = house_forecast(a.date, lean2, polls, a.inc)
        sp = specials()
        hit = sp[(sp.state == a.state) & (sp.district == a.district) & (sp.date == pd.Timestamp(a.date))]
        print(f"{a.state}-{a.district} special, {a.date}: lean {lean2:+.0f} (PVI {lean2 / 2:+.0f})")
        show(f, float(hit.margin_2p.iloc[0]) if len(hit) else None)
        if rec is not None:
            save_run(path, rec, "house", f, asof, used, window, a.lock)
    elif a.kind == "senate":
        f = senate_forecast(a.state, a.date, a.inc, a.lean, polls)
        sen = pd.read_csv(ROOT / "data/interim/senate_specials.csv", parse_dates=["date"])
        hit = sen[(sen.state == a.state) & (sen.date == pd.Timestamp(a.date))]
        src = "given" if f["lean_year"] is None else f"{f['lean_kind']}, {f['lean_year']}"
        print(f"{a.state} Senate special, {a.date}: lean {f['lean']:+.1f} ({src}), incumbent {a.inc:+d}")
        show(f, float(hit.margin_2p.iloc[0]) if len(hit) else None)
        if rec is not None:
            save_run(path, rec, "senate", f, asof, used, window, a.lock)
    else:
        f = governor_forecast(a.state, a.date, a.inc, polls, a.dem, a.rep, a.votehub)
        h = pd.read_csv(ROOT / "data/interim/governor_history.csv")
        hit = h[(h.state == a.state) & (h.year == pd.Timestamp(a.date).year)]
        print(f"{a.state} governor, {a.date}: lean {f['lean_avg2']:+.1f}, incumbent {a.inc:+d}")
        show(f, float(hit.margin_2p.iloc[0]) if len(hit) else None)


if __name__ == "__main__":
    main()
