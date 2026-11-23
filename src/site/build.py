"""Build the static forecast site into site/ (served by a Cloudflare Worker with static assets, no container).

  python src/site/build.py          the forecast unit and the pages around it (what the daily scorecard job runs)
  python src/site/build.py --all    ...and the election data pages (history.py), so one command rebuilds every page

Reads data/processed/* and data/interim/* (the frozen copy in data/final once it exists), writes:
  site/2026/forecast/index.html   the page (data inlined as JSON, charts drawn client-side in SVG; styles and
                                  fonts are shared with every page: site/assets/site.css, site/assets/fonts/)
  site/2026/data/*.csv|json       downloadable model outputs
  site/og.png, site/favicon.*     the link-preview card and the icons (favicon.svg, favicon.ico, apple-touch-icon.png)
and then runs landing.py for the pages around the elections (the landing page, /2028/, /2026/, 404.html, _redirects).

Each election is one unit in a folder under its year; 2026 is the first. The header and footer come from shell.py
and the settings in site.json, which the election data pages (history.py) share. Those pages carry a build date, so the
daily scorecard job leaves them alone; `--all` builds them too.
"""
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MADE_AT = ROOT / "data" / "final" / "MADE_AT.txt"
# Once the final forecast is frozen, the page is built from the frozen copy and keeps its lock time, so a later rebuild
# (e.g. to link the scorecard) can't change what the final forecast shows.
PROC = MADE_AT.parent if MADE_AT.exists() else ROOT / "data" / "processed"
SITE = ROOT / "site"
UNIT = SITE / "2026"            # this election's folder
PAGE = UNIT / "forecast" / "index.html"
DOWNLOADS = UNIT / "data"
sys.path.insert(0, str(Path(__file__).parent))
import landing  # noqa: E402
import shell  # noqa: E402
TEMPLATE = Path(__file__).with_name("template.html")


def clean(v):
    if isinstance(v, (float, np.floating)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def records(df, cols):
    return [{c: clean(r[c]) for c in cols} for _, r in df[cols].iterrows()]


SCORECARD = ROOT / "data" / "scorecard" / "scorecard.json"


def site_scorecard():
    """The scorecard (src/model/scorecard.py) trimmed for the page: House race rows only for contested districts."""
    if not SCORECARD.exists():
        return None
    sc = json.loads(SCORECARD.read_text())
    sc["house"]["races"] = [r for r in sc["house"]["races"] if r.get("contested")]
    return sc


def main():
    models = {}
    for key in ["polls_only", "polls_fundamentals", "polls_fundamentals_biasadj"]:
        s = json.loads((PROC / f"summary_{key}.json").read_text())
        sen = pd.read_csv(PROC / f"senate_{key}.csv")
        house = pd.read_csv(PROC / f"house_{key}.csv")
        house["label"] = house.state + "-" + house.district.astype(int).astype(str)
        house["inc"] = house.incumbent.fillna("").str.split(" Redistricted").str[0]
        comp = house[(house.p_dem > 0.05) & (house.p_dem < 0.95)].sort_values("p_dem", ascending=False)
        opt = lambda df, cols: [c for c in cols if c in df.columns]  # columns added 2026-11-02 (older outputs lack them)
        sims_meta = PROC / f"sims_{key}.json"
        models[key] = {
            "sims": json.loads(sims_meta.read_text()) if sims_meta.exists() else None,
            "house": {k: v for k, v in s["house"].items()},
            "senate": {k: v for k, v in s["senate"].items()},
            "G": s["national"]["G_used"], "shift": s["national"].get("bias_shift", 0.0),
            "sd_nat_house": s["national"].get("sd_nat_house_used", 0.0), "sd_nat_senate": s["national"].get("sd_nat_senate_used", 0.0),
            "senate_shift": s["national"].get("senate_bias_shift", s["national"].get("bias_shift", 0.0)), "lean": s["national"].get("senate_lean_correction", False),
            "w_polls": s["national"].get("w_polls_national", 1.0), "race_w": s["national"].get("race_poll_weight_mean_polled", 0.0),
            "senate_races": records(sen.sort_values("p_dside", ascending=False),
                                    ["race_key", "state", "special", "dem", "rep", "dside", "inc_party", "pvi", "prior",
                                     "poll_avg", "n_polls", "poll_weight", "mu", "sd_race", "p_dside", "rating_cook", "rating_silver"]
                                    + opt(sen, ["poll_avg_raw", "prior_env", "prior_inc", "prior_econ", "q10", "q25", "q75", "q90"])),
            "house_comp": records(comp, ["label", "inc", "inc_party", "pvi", "inc_running", "poll_avg", "mu", "p_dem",
                                         "dem_cand", "rep_cand", "race_key", "poll_weight", "sd_race", "prior_G"]
                                  + opt(comp, ["prior", "prior_inc", "n_polls", "q10", "q25", "q75", "q90"])),
            "house_counts": {
                "fixed_d": int((house.fixed == "D").sum()), "fixed_r": int((house.fixed == "R").sum()),
                "safe_d": int(((house.p_dem >= 0.95) & house.fixed.isna()).sum()),
                "safe_r": int(((house.p_dem <= 0.05) & house.fixed.isna()).sum()),
                "competitive": int(len(comp)),
            },
        }
    nat = json.loads((PROC / "national_inputs.json").read_text())
    bt = json.loads((PROC / "backtest_summary.json").read_text())
    btr = pd.read_csv(PROC / "backtest_senate_2018_2022.csv")
    btr["bin"] = pd.cut(btr.p_dem, [0, .1, .3, .5, .7, .9, 1.0001], labels=["0–10%", "10–30%", "30–50%", "50–70%", "70–90%", "90–100%"])
    calib = btr.groupby("bin", observed=True).agg(n=("dem_won", "size"), p=("p_dem", "mean"), won=("dem_won", "mean")).reset_index()
    sens = json.loads((PROC / "sensitivity.json").read_text()) if (PROC / "sensitivity.json").exists() else None
    bd = json.loads((PROC / "bias_decay.json").read_text())
    bdf = pd.DataFrame(bd["specs"])
    bias = {"history": bd["history"], "flat_mean": bd["flat_mean"], "decay_estimate": bd["top10_avg_pred_2026"],
            "with_covariates": bd.get("top10_with_covariates", bd["top10_avg_pred_2026"]),
            "decay_range": bd["top10_range"],
            "specs": bdf.sort_values("loo_rmse_weighted").head(12)[["half_life", "midterm_mult", "covariates", "president_effect", "pred_2026", "pred_sd", "loo_rmse_weighted"]].to_dict("records"),
            "covariate_specs": bdf[(bdf.half_life.astype(str) == "10") & (bdf.midterm_mult == 2) & (~bdf.president_effect)][["covariates", "pred_2026", "pred_sd", "loo_rmse_weighted"]].to_dict("records")}
    bstate = json.loads((PROC / "bias_analysis.json").read_text())["state"]
    bias["state"] = {"post2010": bstate["post2010_symmetric"], "post2010_asym": bstate["post2010_asymmetric"],
                     "realtime_rmse": bstate["realtime_rmse_within"], "realtime_winner": bstate["realtime_winner"],
                     "slope_by_cycle": bstate["slope_by_cycle"]}
    cal = json.loads((PROC / "calibration.json").read_text())
    h_int = pd.read_csv(ROOT / "data/interim/house_2026_races.csv")
    sys.path.insert(0, str(ROOT / "src" / "model")); sys.path.insert(0, str(ROOT / "src" / "collect"))
    import pollavg as P
    from forecast import senate_races
    vh = P.load_votehub()
    poll_lists = P.senate_poll_list(vh, senate_races(vh))
    from forecast import house_races
    comp_keys = {r["race_key"] for m in models.values() for r in m["house_comp"]}
    house_polls = {k: v for k, v in sorted(P.house_poll_list(vh, house_races()).items()) if k in comp_keys}  # sorted: stable rebuilds
    # sponsored-poll adjustments actually applied to 2026 polls (new tiered rule vs the old flat shift)
    pe = json.loads((PROC / "pollster_effects.json").read_text())
    rows_sp = {}
    for x in vh:
        if x["poll_type"] not in ("us-senator", "us-representative") or x["end_date"] < "2026-06-15" or not x.get("partisan"):
            continue
        lvl = "house" if x["poll_type"] == "us-representative" else "statewide"
        new = -P.sponsor_adj(x, level=lvl) * (1 if x["partisan"].upper() == "DEM" else -1)
        old = 4.3 if lvl == "statewide" else 6.3
        k = (x["pollster"], x["partisan"].upper(), bool(x.get("sponsors")))
        r_ = rows_sp.setdefault(k, {"pollster": x["pollster"], "flag": x["partisan"].upper(), "sponsor_listed": bool(x.get("sponsors")),
                                    "n": 0, "old": old, "new": round(new, 2), "levels": set()})
        r_["n"] += 1; r_["levels"].add(lvl)
    sp_table = sorted(({**v, "levels": sorted(v["levels"])} for v in rows_sp.values()), key=lambda z: -z["n"])[:14]
    pollster_fx = {"beta": pe["beta"], "beta_se": pe["beta_se"], "thin": pe["thin_by_level"], "tau": pe["tau"],
                   "backtest": pe["backtest"], "big_loco": pe.get("big_loco"), "table": sp_table}
    try:
        from zoneinfo import ZoneInfo
        et = dt.datetime.now(ZoneInfo("America/New_York"))
        if MADE_AT.exists():  # the lock time, written by run_all.py --final ("2026-11-03 16:08 <local zone>", local = ET)
            et = dt.datetime.strptime(MADE_AT.read_text().strip()[:16], "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/New_York"))
        gen_label = f"{et:%b} {et.day}, {et.year}, {et.hour % 12 or 12}:{et:%M} {'am' if et.hour < 12 else 'pm'} ET"
        generated = et.strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001  (no tz database: fall back to local time with its offset)
        gen_label = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M UTC%z")
        generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {
        "generated": generated,
        "generated_label": gen_label,
        "final": os.environ.get("FORECAST_FINAL") == "1" or (ROOT / "data" / "final" / "MADE_AT.txt").exists(),
        "scorecard": site_scorecard(),
        "models": models,
        "national": nat,
        "backtest": bt,
        "calibration_bins": [{"bin": str(r.bin), "n": int(r.n), "p": float(r.p), "won": float(r.won)} for _, r in calib.iterrows()],
        "sensitivity": sens,
        "bias": bias,
        "senate_polls": poll_lists,
        "house_polls": house_polls,
        "house_model": {"sd_district": json.loads((PROC / "house_structure.json").read_text())["chosen"]["sd_district"]},
        "fund": json.loads((PROC / "fundamentals.json").read_text()),
        "state_econ": json.loads((PROC / "state_econ.json").read_text()),
        "prior_weight": json.loads((PROC / "prior_weight.json").read_text()),
        "house_structure": json.loads((PROC / "house_structure.json").read_text()),
        "poll_settings": json.loads((PROC / "poll_settings.json").read_text()),
        "pollster_fx": pollster_fx,
        "sdn": json.loads((PROC / "calibration.json").read_text()).get("pollavg_sd_by_n"),
        "bias_confidence": json.loads((PROC / "bias_confidence.json").read_text()),
        "bias_realtime": json.loads((PROC / "bias_realtime.json").read_text()),
        "bias_decomposition": json.loads((PROC / "bias_decomposition.json").read_text()) if (PROC / "bias_decomposition.json").exists() else None,
        "errors": {"structure": json.loads((PROC / "error_structure.json").read_text()),
                   "sensitivity": json.loads((PROC / "error_sensitivity.json").read_text())},
        "error_model": {"sen_cycles": cal["Sen-G"]["cycles"], "gen_cycles": cal["House-G-US"]["cycles"]},
        "inputs": {
            "house_districts": int(len(h_int)), "house_open": int((~h_int.status.fillna("").str.contains("renominated|advanced|re-elected|running", case=False)).sum()),
            "votehub_polls": len(json.loads(sorted((ROOT / "data/raw/votehub").glob("*/polls.json"))[-1].read_text(encoding="utf-8"))),
            "supplement_polls": [{"pollster": x["pollster"], "state": x["subject"].replace("2026 ", ""), "url": x["url"]}
                                 for x in P.SUPPLEMENT_USED],
        },
    }
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for f in list(PROC.glob("*.csv")) + list(PROC.glob("*.json")) + list(PROC.glob("sims_*.bin")):
        shutil.copy(f, DOWNLOADS / f.name)   # every output is a download; error_sensitivity.json is listed on the Data tab
    shutil.copy(ROOT / "data/interim/house_2026_races.csv", DOWNLOADS / "house_2026_races.csv")
    shutil.copy(ROOT / "data/interim/senate_2026_races.csv", DOWNLOADS / "senate_2026_races.csv")
    shutil.copy(ROOT / "data/interim/fundamentals_dataset.csv", DOWNLOADS / "fundamentals_dataset.csv")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__BASE_URL__", shell.SETTINGS["base_url"]).replace("/*__DATA__*/null", json.dumps(data, default=clean).replace("</", "<\\/"))
    prefix = "../" * len(PAGE.parent.relative_to(SITE).parts)
    for mark, part in (("<!--__SITE_HEAD__-->", shell.head(prefix)), ("<!--__SITE_HEADER__-->", shell.header(prefix, UNIT.name)),
                       ("<!--__SITE_FOOTER__-->", shell.footer()), ("<!--__SITE_SCRIPT__-->", shell.script())):
        assert html.count(mark) == 1, mark
        html = html.replace(mark, part)
    PAGE.write_text(html, encoding="utf-8")
    for f in ("favicon.svg", "favicon.ico", "apple-touch-icon.png"):   # the Early Returns icons (SI-9)
        shutil.copy(Path(__file__).with_name("brand") / f, SITE / f)
    try:  # regenerate the link-preview card from today's numbers
        sys.path.insert(0, str(Path(__file__).parent))
        import og_image
        og_image.make(models, SITE / "og.png", data["generated_label"], final=data["final"])
    except Exception as ex:  # noqa: BLE001
        print("og image skipped:", ex)
        og = Path(__file__).with_name("og.png")
        if og.exists():
            shutil.copy(og, SITE / "og.png")
    print("built", PAGE, f"{PAGE.stat().st_size / 1024:.0f} KB")
    landing.main(data["scorecard"], cards="--all" in sys.argv[1:])   # the landing page's seat figures, from the same read as the scorecard tab
    if "--all" in sys.argv[1:]:   # after a change to the header, the footer or site.json: every page, in one command
        import history
        history.main()


if __name__ == "__main__":
    main()
