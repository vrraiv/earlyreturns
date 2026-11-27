"""SP-5: recent House specials as a signal for off-year governor races (SPECIALS.md, section 3; rules agreed
2026-11-27 before any run).

Each odd-year governor race 2007-2025 (two-way, contested, no recalls) is forecast as of its year: the governor prior
fitted on even-year races before the year (governor_model.estimate, spec lean_avg2), with the race's poll average
weighted against it as single_race.py governor does. Environments:
  B   GV-3's term-year estimator for the year (governor_offyear_env.csv, m from governor_offyear_env.json)
  C1  B plus the recent-specials shift (House specials in the 365 days before the race, shrunk n / (n + 2)), every race
  C2  B plus the shift in the year after a presidential election only (term year 1: NJ, VA)
The shift is rebuilt as of the race: environment.py's model fitted on elections before the year, m by term half
fitted on House specials strictly before the race's date.

Run:
  python src/model/specials_governors.py check    race dates, shift, n and poll weight; no result is read
  python src/model/specials_governors.py score    the one scoring run; refuses once its output exists
Writes data/processed/specials_governors.json (score).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
import environment as E  # noqa: E402
import governor_model as GV  # noqa: E402
import special_model as SM  # noqa: E402

OUT = ROOT / "data" / "processed"
INTERIM = ROOT / "data" / "interim"
RESULT = OUT / "specials_governors.json"
FIRST_YEAR, K, MIN_HALF, WINDOW = 2007, 2, 8, 365
N_BOOT, SEED = 10000, 20261127
HS = SM.HS
# rule 3: the date of the round the table's margin comes from, where it is not the November election day
RACE_DATES = {(2011, "WV"): "2011-10-04", (2007, "LA"): "2007-10-20", (2011, "LA"): "2011-10-22",
              (2015, "LA"): "2015-11-21", (2019, "LA"): "2019-11-16", (2023, "LA"): "2023-10-14"}


def election_day(y):
    d = pd.Timestamp(f"{y}-11-01")
    return d + pd.Timedelta(days=(0 - d.dayofweek) % 7 + 1)


# ---------------- inputs ----------------
def races():
    """The test races with their dates; no result column is used by check()."""
    d = GV.load()
    odd = d[(d.year % 2 == 1) & (d.year >= FIRST_YEAR)].copy()
    odd["date"] = [pd.Timestamp(RACE_DATES.get((y, s), election_day(y))) for y, s in zip(odd.year, odd.state)]
    odd["term_year"] = np.where(odd.year % 4 == 1, 1, 3)
    return d, odd.sort_values(["year", "state"]).reset_index(drop=True)


def baseline_env():
    """GV-3's term-year estimator by year: e0 + m (e1 - e0), m as GV-3 fitted it on earlier odd years."""
    env = pd.read_csv(INTERIM / "governor_offyear_env.csv").set_index("year")
    m = {r["year"]: r["m_term_year"] for r in json.loads((OUT / "governor_offyear_env.json").read_text())["m_by_year"]}
    return {y: float(env.estimator_m0[y] + m[y] * (env.estimator_m1[y] - env.estimator_m0[y])) for y in m}


_SPECIALS = None


def specials():
    """House specials with the frozen House prior's base and implied environment (no environment fit involved)."""
    global _SPECIALS
    if _SPECIALS is None:
        s = pd.read_csv(INTERIM / "house_specials.csv", parse_dates=["date"])
        s = s[~s.multi_candidate.astype(bool) & s.pvi.notna()].copy()
        s["term_year"] = s.date.map(SM.term_year)
        s["half2"] = (s.term_year >= 3).astype(int)
        s["base"] = HS["const"] + HS["b_lean2"] * s.lean2
        s["implied_env"] = (s.margin_2p - s.base) / HS["g_nat"]
        _SPECIALS = s.sort_values("date").reset_index(drop=True)
    return _SPECIALS


_MODELS, _PARTS = {}, {}


def env_model(y):
    if y not in _MODELS:
        tr = E.training()
        _MODELS[y] = E.fit(tr[tr.year < y])
    return _MODELS[y]


def parts(y, date):
    """(e0, slope) for a special's date with the environment model fitted on elections before year y."""
    key = (y, date)
    if key not in _PARTS:
        mod = env_model(y)
        e0 = E.env_on(date, "fund", 0.0, mod)[0]
        _PARTS[key] = (e0, E.env_on(date, "fund", 1.0, mod)[0] - e0)
    return _PARTS[key]


def shift_for(y, date):
    """Rule 4: the recent-specials shift for a race in year y on `date`, as of the race."""
    sp = specials()
    earlier = sp[sp.date < date].copy()
    pe = [parts(y, dt) for dt in earlier.date]
    earlier["e0"] = [p[0] for p in pe]
    earlier["slope"] = [p[1] for p in pe]
    m = {}
    for h in (0, 1):
        x = earlier[earlier.half2 == h]
        m[h] = SM.best_m(x) if len(x) >= MIN_HALF else 1.0
    recent = earlier[earlier.date >= date - pd.Timedelta(days=WINDOW)]
    if recent.empty:
        return 0.0, 0, m, 0.0
    resid = float((recent.implied_env - (recent.e0 + recent.slope * recent.half2.map(m))).mean())
    return resid * len(recent) / (len(recent) + K), int(len(recent)), m, resid


def build():
    """Every race's inputs: prior pieces, poll weight, baseline environment and shift. Reads no result."""
    GV.GEN = GV.generic_final()
    d, odd = races()
    benv = baseline_env()
    rows = []
    for y, grp in odd.groupby("year"):
        train = d[(d.year < y) & (d.year % 2 == 0)]
        P = GV.estimate(train, "lean_avg2")
        g = P["g_env"]
        s = P["sd_prior_implied"]
        for _, r in grp.iterrows():
            row = pd.DataFrame({"lean_avg2": [float(r.lean_avg2)], "inc": [float(r.inc)], "env": [0.0]})
            base = float(GV.prior_pred(P["prior"], row, P["fallback"]).iloc[0])
            shift, n, m, resid = shift_for(y, r.date)
            polled = bool(r.n_polls > 0 and pd.notna(r.poll_avg))
            w = float(s ** 2 / (s ** 2 + GV.sd_poll(r.n_polls) ** 2)) if polled else 0.0
            rows.append({"year": int(y), "state": r.state, "date": str(r.date.date()), "term_year": int(r.term_year),
                         "base0": base, "g_env": g, "env_B": benv[y], "shift": shift, "n_specials": n, "resid_raw": resid,
                         "m_half1": m[0], "m_half2": m[1], "n_polls": int(r.n_polls) if polled else 0,
                         "poll_avg": float(r.poll_avg) if polled else np.nan, "w": w})
    return pd.DataFrame(rows)


# ---------------- scoring ----------------
def forecasts(t):
    env = {"B": t.env_B, "C1": t.env_B + t["shift"], "C2": t.env_B + np.where(t.term_year == 1, t["shift"], 0.0)}
    prior = {k: t.base0 + t.g_env * v for k, v in env.items()}
    with_polls = {k: np.where(t.w > 0, t.w * t.poll_avg.fillna(0) + (1 - t.w) * p, p) for k, p in prior.items()}
    return prior, with_polls


def rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def summary(err, t):
    out = {}
    for k, e in err.items():
        e = np.asarray(e)
        out[k] = {"races": int(len(e)), "rmse": rmse(e), "mae": float(np.abs(e).mean()), "mean_err": float(e.mean()),
                  "rmse_term_year_1": rmse(e[t.term_year.values == 1]), "rmse_term_year_3": rmse(e[t.term_year.values == 3])}
    return out


def judge(err, t, cand):
    """Rule 6: gain over B > its SD over years redrawn with replacement, and > 0 with each year left out."""
    years = np.array(sorted(t.year.unique()))
    eb, ec, yr = np.asarray(err["B"]), np.asarray(err[cand]), t.year.values
    gain = rmse(eb) - rmse(ec)
    rng = np.random.default_rng(SEED)
    idx = {y: np.where(yr == y)[0] for y in years}
    boot = []
    for _ in range(N_BOOT):
        pick = np.concatenate([idx[y] for y in rng.choice(years, len(years), replace=True)])
        boot.append(rmse(eb[pick]) - rmse(ec[pick]))
    sd = float(np.std(boot, ddof=1))
    loyo = {int(y): rmse(eb[yr != y]) - rmse(ec[yr != y]) for y in years}
    passes = bool(gain > sd and all(v > 0 for v in loyo.values()))
    return {"gain": gain, "boot_sd": sd, "loyo_gain": loyo, "loyo_min": min(loyo.values()), "passes": passes}


def check():
    t = build()
    pd.set_option("display.width", 220)
    print(t[["year", "state", "date", "term_year", "env_B", "n_specials", "resid_raw", "shift", "m_half1", "m_half2", "n_polls", "w"]]
          .round(2).to_string(index=False))


def score():
    if RESULT.exists():
        sys.exit(f"{RESULT.relative_to(ROOT)} exists: SP-5's scoring run is done and is not rerun (SPECIALS.md, section 3).")
    t = build()
    _, odd = races()
    t = t.merge(odd[["year", "state", "margin_2p"]], on=["year", "state"], validate="one_to_one")
    prior, polls = forecasts(t)
    # internal check: B on the prior alone must equal GV-3's term-year errors race by race
    gv3 = pd.DataFrame(json.loads((OUT / "governor_offyear_env.json").read_text())["races"])
    gv3 = gv3[gv3.environment == "estimator, by term year"].set_index(["year", "state"]).error
    b_err = (t.margin_2p - prior["B"]).values
    ref = gv3.reindex(list(zip(t.year, t.state))).values
    assert np.allclose(b_err, ref, atol=1e-3), "B on the prior alone does not reproduce GV-3's errors"
    err_p = {k: t.margin_2p.values - v for k, v in polls.items()}
    err_0 = {k: t.margin_2p.values - v for k, v in prior.items()}
    dec = {c: judge(err_p, t, c) for c in ("C1", "C2")}
    passed = [c for c in dec if dec[c]["passes"]]
    adopted = min(passed, key=lambda c: summary(err_p, t)[c]["rmse"]) if passed else None
    winners = {k: int(((v > 0) == (t.margin_2p.values > 0)).sum()) for k, v in polls.items()}
    for k in polls:
        t[f"fc_{k}"] = polls[k]
        t[f"prior_{k}"] = prior[k]
    out = {"card": "SP-5", "rules": "SPECIALS.md section 3, agreed 2026-11-27", "races": int(len(t)),
           "with_polls": summary(err_p, t), "decision": dec, "adopted": adopted, "winners_with_polls": winners,
           "prior_alone (reported, deciding nothing)": summary(err_0, t),
           "prior_alone_judged (deciding nothing)": {c: judge(err_0, t, c) for c in ("C1", "C2")},
           "race_table": t.round(3).to_dict("records")}
    RESULT.write_text(json.dumps(out, indent=1, default=float))
    pd.set_option("display.width", 220)
    print("with polls (decides):"); print(pd.DataFrame(out["with_polls"]).T.round(2).to_string())
    for c, v in dec.items():
        print(c, {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items() if k != "loyo_gain"},
              "loyo:", {k: round(x, 2) for k, x in v["loyo_gain"].items()})
    print("adopted:", adopted, "| winners:", winners)
    print("prior alone (deciding nothing):"); print(pd.DataFrame(out["prior_alone (reported, deciding nothing)"]).T.round(2).to_string())
    print({c: {k: round(x, 3) for k, x in v.items() if isinstance(x, float)} for c, v in out["prior_alone_judged (deciding nothing)"].items()})
    print(t[["year", "state", "term_year", "margin_2p", "shift", "w", "fc_B", "fc_C1", "fc_C2"]].round(1).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["check", "score"])
    {"check": check, "score": score}[ap.parse_args().what]()
