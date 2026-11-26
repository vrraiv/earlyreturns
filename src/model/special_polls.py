"""Polls of past specials (SP-4, SPECIALS.md section 2).

  python src/model/special_polls.py shift    the partisan-sponsor shift re-estimated without special elections

shift: the frozen forecast's estimator (src/model/poll_settings.py, sponsor_shift) on the same FiveThirtyEight rows,
minus every House or Senate race whose election day is not the regular November general-election day of an even year
(specials, runoffs and odd-year House races). Governor races are all kept: off-cycle governors are regular elections.
So no special-election poll is ever compared with its result here. Writes data/processed/special_polls_shift.json.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
import bias_analysis as BA  # noqa: E402
import poll_settings as PS  # noqa: E402

OUT = ROOT / "data" / "processed"


def general_day(year):
    """Tuesday after the first Monday in November."""
    d = pd.Timestamp(f"{year}-11-01")
    first_monday = d + pd.Timedelta(days=(0 - d.weekday()) % 7)
    return first_monday + pd.Timedelta(days=1)


def is_special(r):
    ed = pd.to_datetime(r.electiondate, format="mixed")
    regular = (ed.dt.year % 2 == 0) & (ed == ed.dt.year.map(general_day))
    return r.type_simple.isin(["House-G", "Sen-G"]) & ~regular


def shift():
    r = BA.load()
    sp = is_special(r)
    frozen = PS.sponsor_shift(r)
    clean = PS.sponsor_shift(r[~sp])
    out = {"frozen": frozen, "without_specials": clean,
           "dropped": {"rows": int(sp.sum()), "races": int(r[sp].race_id.nunique())},
           "chosen": {"partisan_shift_house": round(max(clean["house_district"]["shift"], 0.0), 1),
                      "partisan_shift_statewide": round(max(clean["statewide"]["shift"], 0.0), 1)},
           "note": "poll_settings.sponsor_shift on FiveThirtyEight raw_polls 1998-2022, House and Senate races off the "
                   "even-year general-election day removed (SP-4 rule 5, P3)"}
    (OUT / "special_polls_shift.json").write_text(json.dumps(out, indent=1))
    for k in ("house_district", "statewide"):
        f, c = frozen[k], clean[k]
        print(f"{k}: frozen {f['shift']:.2f} ({f['n_polls']} polls, {f['n_races']} races) -> without specials "
              f"{c['shift']:.2f} +/- {c['se']:.2f} ({c['n_polls']} polls, {c['n_races']} races)")
    print("dropped:", out["dropped"], "chosen:", out["chosen"])


# ---------------- the test (rules 5-8) ----------------
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

POLLS = ROOT / "data" / "interim" / "special_polls.csv"
EXCLUDED = {"HI-1-2010-05-22", "AK-0-2022-08-16"}           # amendment to rule 2: keep the prior alone
SD_DIST = float(json.loads((ROOT / "data/final/house_structure.json").read_text())["district_polls"]["implied_poll_sd"])
_CAL = json.loads((ROOT / "data/final/calibration.json").read_text())["pollavg_sd_by_n"]
SD_STATE_A, SD_STATE_B = float(_CAL["a"]), float(_CAL["b"])
DF_T = float(json.loads((OUT / "poll_settings.json").read_text())["chosen"]["df_t"])
SD_SENATE = 18.0
MIN_P4 = 10


def shifts():
    c = json.loads((OUT / "special_polls_shift.json").read_text())["chosen"]
    return c["partisan_shift_house"], c["partisan_shift_statewide"]


def poll_set(polls, kind, shift_pts=0.0, window60=False):
    """Margins of one race's polls under a candidate: 'all', 'nonpartisan' or 'shifted'."""
    p = polls[polls.days <= 60] if window60 else polls[polls.in_window]
    if kind == "nonpartisan":
        p = p[p.partisan.isna()]
    m = p.margin.to_numpy(dtype=float).copy()
    if kind == "shifted":
        m = m - shift_pts * (p.partisan == "DEM").to_numpy() + shift_pts * (p.partisan == "REP").to_numpy()
    return m


def avg(m):
    return float(m.mean()), max(float(m.std(ddof=0)), 4.0) ** 2 / len(m), len(m)


def blend(prior, sd_prior, pa, sd_p):
    w = sd_prior ** 2 / (sd_prior ** 2 + sd_p ** 2)
    return w * pa + (1 - w) * prior, 1 / np.sqrt(1 / sd_p ** 2 + 1 / sd_prior ** 2), w


def house_table():
    """The backtest's 68 specials with their stored prospective prior and SD, joined to their polls."""
    b = pd.DataFrame(json.loads((OUT / "single_race_backtest.json").read_text())["races"])
    b["key"] = b.race + "-" + b.date
    p = pd.read_csv(POLLS, parse_dates=["date", "end"])
    p = p[p.office == "H"]
    return b, p


def house_runs(b, p, only=None):
    """Forecasts for every candidate on every backtest special. Returns a long table."""
    sh, _ = shifts()
    hs = pd.read_csv(ROOT / "data/interim/house_specials.csv", parse_dates=["date"])
    hs["key"] = hs.state + "-" + hs.district.astype(int).astype(str) + "-" + hs.date.dt.date.astype(str)
    actual = hs.set_index("key").margin_2p
    universe = set(hs[~hs.multi_candidate.astype(bool) & hs.pvi.notna()].key)   # special_model.load()'s specials
    polled = sorted((set(p[p.in_window].race) & universe) - EXCLUDED, key=lambda k: k[-10:])
    rows = []
    for _, r in b.iterrows():
        g = p[p.race == r.key]
        use = r.key in polled
        out = {"key": r.key, "date": r.date, "polled": use, "excluded": r.key in EXCLUDED, "actual": r.actual,
               "P0_mu": r.mu, "P0_sd": r.sd}
        # P4's poll error from earlier polled specials (2007 included), all polls, as P1
        earlier = [k for k in polled if k[-10:] < r.date]
        if len(earlier) >= MIN_P4:
            e2, s2 = [], []
            for k in earlier:
                pa_k, v_k, _ = avg(poll_set(p[p.race == k], "all"))
                e2.append((pa_k - actual[k]) ** 2); s2.append(v_k)
            a = float(np.sqrt(max(np.mean(e2) - np.mean(s2), 0.0)))
        else:
            a = SD_DIST
        out["P4_a"], out["P4_n_earlier"] = a, len(earlier)
        for name, kind, sd0, w60 in (("P1", "all", SD_DIST, False), ("P2", "nonpartisan", SD_DIST, False),
                                     ("P3", "shifted", SD_DIST, False), ("P4", "all", a, False),
                                     ("P1w60", "all", SD_DIST, True)):
            m = poll_set(g, kind, sh, w60) if use else np.array([])
            if len(m):
                pa, v, n = avg(m)
                mu, s, w = blend(r.mu, r.sd, pa, np.sqrt(sd0 ** 2 + v))
            else:
                pa, n, mu, s, w = np.nan, 0, r.mu, r.sd, 0.0
            out.update({f"{name}_mu": mu, f"{name}_sd": s, f"{name}_w": w, f"{name}_n": n, f"{name}_pa": pa})
        rows.append(out)
    return pd.DataFrame(rows)


def summ(t, name, mask):
    x = t[mask]
    err = x.actual - x[f"{name}_mu"]
    z = err / x[f"{name}_sd"]
    return {"n": int(len(x)), "rmse": float(np.sqrt((err ** 2).mean())), "mae": float(err.abs().mean()),
            "mean_err": float(err.mean()), "log_score": float((stats.norm.logpdf(z) - np.log(x[f"{name}_sd"])).mean()),
            "cover_80": float((z.abs() <= stats.norm.ppf(0.9)).mean()),
            "cover_50": float((z.abs() <= stats.norm.ppf(0.75)).mean()),
            "cover_95": float((z.abs() <= stats.norm.ppf(0.975)).mean()),
            "winners": int(((x[f"{name}_mu"] > 0) == (x.actual > 0)).sum())}


def adopt(t, cand, base, mask):
    a, b0 = summ(t, cand, mask), summ(t, base, mask)
    early, late = mask & (t.date < "2017-01-01"), mask & (t.date >= "2017-01-01")
    d_early = summ(t, cand, early)["rmse"] - summ(t, base, early)["rmse"]
    d_late = summ(t, cand, late)["rmse"] - summ(t, base, late)["rmse"]
    cov_ok = (0.70 <= a["cover_80"] <= 0.90) or abs(a["cover_80"] - 0.8) < abs(b0["cover_80"] - 0.8)
    checks = {"rmse_gain": b0["rmse"] - a["rmse"], "rmse_ok": b0["rmse"] - a["rmse"] >= 0.3,
              "log_ok": a["log_score"] > b0["log_score"], "log_gain": a["log_score"] - b0["log_score"],
              "rmse_2008_2016": d_early, "rmse_2017_2026": d_late, "periods_ok": d_early < 0 and d_late < 0,
              "cover_80": a["cover_80"], "cover_80_base": b0["cover_80"], "cover_ok": bool(cov_ok)}
    checks["pass"] = bool(checks["rmse_ok"] and checks["log_ok"] and checks["periods_ok"] and checks["cover_ok"])
    return checks


def check():
    """Plumbing check before the run: counts, poll averages' sizes and P4's n; no result is read or printed."""
    b, p = house_table()
    b = b.assign(actual=np.nan)
    polled = set(p[p.in_window].race) - EXCLUDED
    print("backtest specials:", len(b), "| polled in the backtest:", len(set(b.key) & polled),
          "| polled races not in the backtest:", sorted(polled - set(b.key)))
    print("excluded present:", sorted(EXCLUDED & set(b.key)))
    sen = pd.read_csv(OUT / "senate_specials_races.csv")
    sp = pd.read_csv(POLLS); sp = sp[(sp.office == "S") & sp.in_window]
    print("Senate races with polls:", sorted(set(sp.race) & set(sen.race)))
    print("shifts:", shifts(), "SD_DIST", round(SD_DIST, 2), "statewide a,b", round(SD_STATE_A, 2), round(SD_STATE_B, 2))


def senate_runs():
    _, sh = shifts()
    sen = pd.read_csv(OUT / "senate_specials_races.csv")
    p = pd.read_csv(POLLS, parse_dates=["date", "end"])
    p = p[p.office == "S"]
    rows = []
    for _, r in sen.iterrows():
        g = p[p.race == r.race]
        out = {"race": r.race, "set": r["set"], "actual": r.actual, "S0_mu": r.mu_L1_F1, "S0_sd": SD_SENATE, "S0_n": 0}
        for name, kind in (("S1", "all"), ("S2", "nonpartisan"), ("S3", "shifted")):
            m = poll_set(g, kind, sh)
            if len(m):
                pa, n = float(m.mean()), len(m)
                mu, s, w = blend(r.mu_L1_F1, SD_SENATE, pa, np.sqrt(SD_STATE_A ** 2 + SD_STATE_B ** 2 / n))
            else:
                pa, n, mu, s, w = np.nan, 0, r.mu_L1_F1, SD_SENATE, 0.0
            out.update({f"{name}_mu": mu, f"{name}_sd": s, f"{name}_w": w, f"{name}_n": n, f"{name}_pa": pa})
        rows.append(out)
    return pd.DataFrame(rows)


def senate_summ(t, name, mask):
    x = t[mask]
    err = x.actual - x[f"{name}_mu"]
    u = stats.t(DF_T, scale=np.sqrt((DF_T - 2) / DF_T))
    z = (err / x[f"{name}_sd"]).abs()
    return {"n": int(len(x)), "rmse": float(np.sqrt((err ** 2).mean())), "mae": float(err.abs().mean()),
            "mean_err": float(err.mean()), "winners": int(((x[f"{name}_mu"] > 0) == (x.actual > 0)).sum()),
            **{f"cover_{q}": int((z <= u.ppf(0.5 + q / 200)).sum()) for q in (50, 80, 95)}}


def score():
    out_f = OUT / "special_polls_scores.json"
    if out_f.exists():
        raise SystemExit(f"{out_f.name} exists: SP-4's scoring run is done once (SPECIALS.md section 2)")
    b, p = house_table()
    t = house_runs(b, p)
    pol = t.polled
    names = ["P0", "P1", "P2", "P3", "P4", "P1w60"]
    res = {"house": {"polled": {n: summ(t, n, pol) for n in names},
                     "all_68": {n: summ(t, n, t.key.notna()) for n in names},
                     "wikipedia_races": {n: summ(t, n, pol & t.key.isin(set(p[p.source == "wikipedia"].race))) for n in names}}}
    ad = {"P1_vs_P0": adopt(t, "P1", "P0", pol)}
    for c in ("P2", "P3", "P4"):
        ad[f"{c}_vs_P1"] = adopt(t, c, "P1", pol)
    # rule 6: P4 with P2 or P3, only if both pass (a candidate suggested by these results)
    set_pass = [c for c in ("P2", "P3") if ad[f"{c}_vs_P1"]["pass"]]
    if ad["P4_vs_P1"]["pass"] and set_pass:
        best = min(set_pass, key=lambda c: res["house"]["polled"][c]["rmse"])
        sh, _ = shifts()
        kind = {"P2": "nonpartisan", "P3": "shifted"}[best]
        mu, sd = [], []
        for _, r in t.iterrows():
            g = p[p.race == r.key]
            m = poll_set(g, kind, sh) if r.polled else np.array([])
            if len(m):
                pa, v, _ = avg(m)
                a_, s_, _ = blend(r.P0_mu, r.P0_sd, pa, np.sqrt(r.P4_a ** 2 + v))
            else:
                a_, s_ = r.P0_mu, r.P0_sd
            mu.append(a_); sd.append(s_)
        t["P5_mu"], t["P5_sd"] = mu, sd
        single = min(["P4", best], key=lambda c: res["house"]["polled"][c]["rmse"])
        ad[f"P5_vs_{single}"] = {**adopt(t, "P5", single, pol), "pair": f"P4 + {best}"}
        res["house"]["polled"]["P5"] = summ(t, "P5", pol)
    res["house"]["adoption"] = ad
    x = t[pol]
    res["house"]["polls_alone"] = {"rmse": float(np.sqrt(((x.actual - x.P1_pa) ** 2).mean())),
                                   "mae": float((x.actual - x.P1_pa).abs().mean()),
                                   "mean_poll_error": float((x.actual - x.P1_pa).mean()),
                                   "winners": int(((x.P1_pa > 0) == (x.actual > 0)).sum())}
    res["house"]["P4_final_a"] = float(t.P4_a.iloc[-1]); res["house"]["sd_district_poll"] = SD_DIST
    s = senate_runs()
    res["senate"] = {st: {n: senate_summ(s, n, s["set"] == st) for n in ("S0", "S1", "S2", "S3")} for st in ("special", "runoff")}
    s_pol = s.S1_n > 0
    res["senate"]["special_polled"] = {n: senate_summ(s, n, (s["set"] == "special") & s_pol) for n in ("S0", "S1", "S2", "S3")}
    res["senate"]["runoff_polled"] = {n: senate_summ(s, n, (s["set"] == "runoff") & s_pol) for n in ("S0", "S1", "S2", "S3")}
    res["note"] = "SP-4 scoring run, once (SPECIALS.md section 2). House: stored prospective priors from single_race_backtest.json."
    t.round(3).to_csv(OUT / "special_polls_house.csv", index=False)
    s.round(3).to_csv(OUT / "special_polls_senate.csv", index=False)
    out_f.write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res["house"]["adoption"], indent=1, default=lambda v: round(float(v), 3)))


if __name__ == "__main__":
    {"shift": shift, "check": check, "score": score}[sys.argv[1]]()
