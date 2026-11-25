"""The primaries backtest (PP-6), as PRIMARIES.md section 4 sets it out (rules 1-14).

    python src/model/primary_backtest.py           first reading: scores the committed left-out-race forecasts
    python src/model/primary_backtest.py --year    second reading (rule 10): refits with both parties of 2008, and of
                                                   2016, left out together, and scores those four races again
    python src/model/primary_backtest.py --ranges  the declared round's diagnostic of the share ranges (D1 to D5);
                                                   prints only

The first reading reads only `primary_state_forecasts.csv` and the results (through the model's own functions); it
refits nothing. Both write `data/processed/primary_backtest.csv`, one row per scored forecast, model and reading.
Set PRIMARY_STATE_CACHE for the second reading: it rebuilds the averages otherwise. Run the first reading before
the second: the first writes the table afresh, without the second's rows, and the second adds its own.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import primary_state as ps  # noqa: E402

OUT = ps.OUT / "primary_backtest.csv"
FORECASTS = ps.OUT / "primary_state_forecasts.csv"
VALUES = ps.OUT / "primary_state_values.csv"
MODELS = ["state_model", "baseline"]
EDGES = [0, 0.05, 0.15, 0.30, 0.50, 0.70, 0.85, 0.95, 1.0]                  # rule 7: calibration bins
VOTED = [(0, 0, "none"), (1, 4, "1 to 4"), (5, 19, "5 to 19"), (20, 99, "20 or more")]            # rule 9
DAYS = [(0, 0, "0"), (1, 7, "1 to 7"), (8, 14, "8 to 14"), (15, 30, "15 to 30"), (31, 60, "31 to 60"),
        (61, 9999, "61 or more")]                                           # rule 11
YEARS = {"2008": [(2008, "D"), (2008, "R")], "2016": [(2016, "D"), (2016, "R")]}                  # rule 10
FKEY = ["cycle", "party", "state", "as_of"]
CKEY = ["cycle", "party", "state"]
MEASURES = ["log_loss", "brier", "sq_error", "called"]
FIRST, SECOND = "race left out", "year left out"


# ---------------------------------------------------------------- results (rule 2)

def truth(races):
    """Every main contest held in the open contests: its date, whether it is one of the 50 states and DC, the
    winner (S19) and each candidate's share; `why` says why a contest is not scored (rule 1 of section 3, S20)."""
    rows, actual = [], {}
    for (cycle, party), race in races.items():
        for state, day in race.held.items():
            res = race.result(state)
            why = "no result row" if res is None else "measure unclear" if res[1] == "unclear" else ""
            rows.append(dict(cycle=cycle, party=party, state=state, held=day, in51=state in ps.STATES, why=why,
                             winner=None if res is None else res[2]))
            if res is not None:
                actual[(cycle, party, state)] = res[0]
    return pd.DataFrame(rows), actual


def scored_keys(t):
    """Rule 2: the contests of the 50 states and DC with a usable result, on the days 30 and 7 before and the day."""
    t = t[t["in51"] & t["why"].eq("")]
    return pd.concat([t.assign(horizon=h, as_of=t["held"] - pd.Timedelta(days=h)) for h in ps.SCORED],
                     ignore_index=True)[FKEY + ["horizon"]]


# ---------------------------------------------------------------- scoring (rules 4 and 7)

def score(fc, t, actual, races):
    """One row per forecast (model, contest, date) from rule 17's rows, and the candidate rows behind it."""
    c = fc.merge(t[CKEY + ["held", "in51", "winner"]], on=CKEY)
    c["actual"] = [actual[k].get(cand, 0.0) for k, cand in zip(zip(c["cycle"], c["party"], c["state"]),
                                                                c["candidate_key"])]
    c["won"] = (c["candidate_key"] == c["winner"]).astype(float)
    c["covered"] = ((c["p10"] <= c["actual"]) & (c["actual"] <= c["p90"])).astype(float)
    c["sq"] = (c["share"] - c["actual"]) ** 2
    c["b"] = (c["win"] - c["won"]) ** 2
    c["pw"] = c["win"] * c["won"]
    c = c.sort_values(["model"] + FKEY + ["candidate_key"], kind="stable").reset_index(drop=True)
    g = c.groupby(["model"] + FKEY, sort=False)
    top = c.loc[g["win"].idxmax(), ["model"] + FKEY + ["won"]].rename(columns={"won": "called"})
    f = g.agg(held=("held", "first"), date_known=("date_known", "first"), polled=("polled", "first"),
              caucus=("caucus", "first"), in51=("in51", "first"), field=("win", "size"), winner=("winner", "first"),
              p_winner=("pw", "sum"), brier=("b", "sum"), sq_error=("sq", "mean"), covered=("covered", "sum"),
              values=("values", "first")).reset_index().merge(top, on=["model"] + FKEY)
    f["log_loss"] = -np.log(np.maximum(f["p_winner"], ps.P_FLOOR))          # rule 4: the floor
    f["horizon"] = (f["held"] - f["as_of"]).dt.days
    f["days_known"] = (f["date_known"] - f["as_of"]).dt.days
    days = f.drop_duplicates(["cycle", "party", "as_of"])
    voted = {(cy, p, d): len(races[(cy, p)].voted(d)) for cy, p, d in zip(days["cycle"], days["party"], days["as_of"])}
    f["voted_before"] = [voted[k] for k in zip(f["cycle"], f["party"], f["as_of"])]
    return f, c


def pooled(f, col):
    """Rule 4's weighting: the mean over a contest's dates, then over contests."""
    return f.groupby(CKEY)[col].mean().mean() if len(f) else np.nan


def by_race(f, col):
    return f.groupby(CKEY)[col].mean().groupby(["cycle", "party"]).mean()


def side_by_side(f, col, split=None):
    """Model against baseline for one measure: pooled, or one row per value of `split`."""
    rows = []
    groups = [("pooled", f)] if split is None else list(f.groupby(split, sort=True))
    for name, g in groups:
        m, b = (g[g["model"] == x] for x in MODELS)
        rows.append({"": name, "model": pooled(m, col), "baseline": pooled(b, col),
                     "difference": pooled(m, col) - pooled(b, col), "contests": m.groupby(CKEY).ngroups,
                     "forecasts": len(m)})
    return pd.DataFrame(rows).set_index("")


def coverage(f, split=None):
    groups = [("pooled", f)] if split is None else list(f.groupby(split, sort=True))
    rows = []
    for name, g in groups:
        row = {"": name}
        for x in MODELS:
            gx = g[g["model"] == x]
            row[x] = gx["covered"].sum() / gx["field"].sum() if len(gx) else np.nan
        row["candidates"] = int(g[g["model"] == MODELS[0]]["field"].sum())
        rows.append(row)
    return pd.DataFrame(rows).set_index("")


def calibration(c):
    """Rule 7: every field candidate's chance in bins; a chance on an edge goes to the upper bin, 100% to the last."""
    b = np.minimum(np.searchsorted(EDGES, c["win"].to_numpy(), side="right") - 1, len(EDGES) - 2)
    label = [f"{100 * EDGES[i]:.0f} to {100 * EDGES[i + 1]:.0f}%" for i in range(len(EDGES) - 1)]
    out = c.assign(bin=b).groupby(["model", "bin"]).agg(n=("win", "size"), mean_chance=("win", "mean"),
                                                         won=("won", "mean")).reset_index()
    out["bin"] = out["bin"].map(dict(enumerate(label)))
    w = out.pivot(index="bin", columns="model", values=["n", "mean_chance", "won"]).reindex(label)
    return w.reorder_levels([1, 0], axis=1)[[(m, k) for m in MODELS for k in ("n", "mean_chance", "won")]]


def band(x, bands):
    return next(name for lo, hi, name in bands if lo <= x <= hi)


def show(title, frame, places=3):
    print(f"\n{title}\n" + frame.to_string(float_format=lambda v: f"{v:.{places}f}"), flush=True)


def report(f, c, label):
    """Rules 4 and 7 to 9 for a set of scored forecasts (`f`) and their candidate rows (`c`)."""
    head = f[f["field"] >= 2]                                              # rule 3
    hk = head[["model"] + FKEY]
    chead = c.merge(hk, on=["model"] + FKEY)
    print(f"\n{'=' * 100}\n{label}: {f[f['model'] == MODELS[0]].groupby(CKEY).ngroups} contests, "
          f"{(f['model'] == MODELS[0]).sum()} forecasts; headline (field of two or more): "
          f"{head[head['model'] == MODELS[0]].groupby(CKEY).ngroups} contests, "
          f"{(head['model'] == MODELS[0]).sum()} forecasts")
    for col in MEASURES:
        for name, g in (("headline", head), ("all forecasts", f)):
            t = pd.concat([side_by_side(g, col, ["cycle", "party"]), side_by_side(g, col)])
            show(f"{col}, {name}, by race and pooled", t)
    for name, g in (("headline", head), ("all forecasts", f)):
        show(f"coverage of the 10th-90th range, {name}", pd.concat([coverage(g, ["cycle", "party"]), coverage(g)]))
    for col in MEASURES:
        show(f"{col}, headline, by days before", side_by_side(head, col, "horizon"))
        show(f"{col}, headline, by polled", side_by_side(head, col, "polled"))
    show("coverage, headline, by days before", coverage(head, "horizon"))
    show("coverage, headline, by polled", coverage(head, "polled"))
    show("calibration, headline, all three dates", calibration(chead))
    show("calibration, headline, the day", calibration(chead[chead["held"] == chead["as_of"]]))
    v = head.assign(voted=[band(x, VOTED) for x in head["voted_before"]])
    order = [name for _, _, name in VOTED]
    for col in ("log_loss", "sq_error"):
        show(f"{col}, headline, by states voted before the forecast date", side_by_side(v, col, "voted").reindex(order))
    return head


def mark(head):
    """Rule 4: below the baseline in at least 5 of the 7 races and in the pooled figure; equal is not below."""
    t = side_by_side(head, "log_loss", ["cycle", "party"])
    p = side_by_side(head, "log_loss")
    races_below = int((t["model"] < t["baseline"]).sum())
    pooled_below = bool(p["model"].iat[0] < p["baseline"].iat[0])
    verdict = "PASS" if races_below >= 5 and pooled_below else "MISS"
    print(f"\nTHE MARK (rule 4): the model's log loss is below the baseline's in {races_below} of {len(t)} races; "
          f"pooled {p['model'].iat[0]:.4f} against {p['baseline'].iat[0]:.4f} "
          f"({'below' if pooled_below else 'not below'}): {verdict}")
    return verdict


def table(f, reading):
    cols = ["model"] + FKEY + ["held", "horizon", "polled", "caucus", "field", "voted_before", "winner", "p_winner",
                               "log_loss", "brier", "sq_error", "called", "covered", "values"]
    out = f[cols].copy()
    out.insert(0, "reading", reading)
    for col, places in (("p_winner", 4), ("log_loss", 4), ("brier", 4), ("sq_error", 2)):
        out[col] = out[col].round(places)
    for col in ("called", "covered"):
        out[col] = out[col].astype(int)
    return out


def write(out):
    out.sort_values(["reading", "model"] + FKEY, kind="stable").to_csv(OUT, index=False, date_format="%Y-%m-%d")
    print(f"\nwrote {OUT.name}: {len(out)} rows")


# ---------------------------------------------------------------- the first reading (rules 1 to 9, 11 to 13)

def first():
    races = {k: ps.Race(*k) for k in ps.OPEN}
    t, actual = truth(races)
    fc = pd.read_csv(FORECASTS, parse_dates=["as_of", "date_known"])
    fc = fc.merge(pd.DataFrame(ps.OPEN, columns=["cycle", "party"]), on=["cycle", "party"])
    usable = t[t["why"].eq("")]
    fc = fc.merge(usable[CKEY], on=CKEY)
    keys = scored_keys(t)
    sfc = fc.merge(keys[FKEY], on=FKEY)

    # rule 1: checked before any score exists
    own = sfc["cycle"].astype(str) + " " + sfc["party"]
    assert (sfc["values"] == own).all(), "a scored row does not use its own race's left-out values"
    for m in MODELS:
        k = sfc[sfc["model"] == m].drop_duplicates(FKEY)
        assert (k.groupby(CKEY).ngroups, len(k)) == (335, 987), (m, k.groupby(CKEY).ngroups, len(k))
    print("rule 1: every scored row uses the values fitted without its own race; 335 contests, 987 forecasts")

    f, c = score(sfc, t, actual, races)
    head = report(f, c, "FIRST READING (each race left out)")
    verdict = mark(head)

    # rule 11: every forecast date, the 50 states and DC, a field of two or more; each forecast counted once
    allf, _ = score(fc[fc["state"].isin(ps.STATES)], t, actual, races)
    allf = allf[allf["field"] >= 2].assign(days=lambda x: [band(d, DAYS) for d in x["days_known"]])
    rows = []
    for _, _, name in DAYS:
        g = allf[allf["days"] == name]
        row = {"days to the contest": name, "forecasts": int((g["model"] == MODELS[0]).sum())}
        for col in ("log_loss", "sq_error"):
            for m in MODELS:
                row[f"{col} {m}"] = g.loc[g["model"] == m, col].mean()
        rows.append(row)
    show("every forecast date (rule 11), a mean over forecasts", pd.DataFrame(rows).set_index("days to the contest"))

    # rule 12: territories and Democrats Abroad, on the day
    terr, _ = score(fc[~fc["state"].isin(ps.STATES)], t, actual, races)
    terr = terr[terr["as_of"] == terr["held"]]
    for name, g in (("a field of two or more", terr[terr["field"] >= 2]), ("all", terr)):
        rows = [{"": col, **{m: g.loc[g["model"] == m, col].mean() for m in MODELS},
                 "forecasts": int((g["model"] == MODELS[0]).sum())} for col in ("log_loss", "sq_error")]
        show(f"territories and Democrats Abroad on the day (rule 12), {name}", pd.DataFrame(rows).set_index(""))

    # rule 13: not scored
    have = sfc[sfc["model"] == MODELS[0]].drop_duplicates(FKEY)[FKEY]
    gone = keys.merge(have, on=FKEY, how="left", indicator=True).query("_merge == 'left_only'")
    whole = gone.groupby(CKEY).size()
    print(f"\nnot scored (rule 13): {len(gone)} contest-dates with no forecast, {int((whole == 3).sum())} contests "
          f"on all three dates")
    print(t[t["in51"] & t["why"].ne("")][CKEY + ["why"]].to_string(index=False))
    write(table(f, FIRST))
    return verdict


# ---------------------------------------------------------------- the second reading (rule 10)

def forecast_at(race, as_of, state, v):
    """Rule 17's rows for one contest on one date at any values: the same draws as Race.forecast() (S27)."""
    comp = race.components(as_of, only=[state])
    if comp.empty:
        return comp
    contests, cands, d = race.draws(as_of, v, comp)
    comp = comp.assign(share=ps.shares(comp, v["beta"], v["kappa"], v["lambda"]))
    top = d.max(axis=2, keepdims=True)
    win = ((d == top) / (d == top).sum(axis=2, keepdims=True)).mean(axis=0)
    lo, hi = np.percentile(d, [10, 90], axis=0)
    ix = pd.MultiIndex.from_product([contests, cands], names=["state", "candidate_key"])
    s = pd.DataFrame(dict(p10=lo.ravel(), p90=hi.ravel(), win=win.ravel()), index=ix).reset_index()
    return comp.merge(s, on=["state", "candidate_key"])[
        ["cycle", "party", "as_of", "state", "date_known", "days", "caucus", "polled", "W", "other", "candidate_key",
         "share", "p10", "p90", "win"]]


def rebuild(races, keys, values, fold_of):
    out = []
    for model in MODELS:
        for (cycle, party), g in keys.groupby(["cycle", "party"]):
            fold = fold_of(cycle, party)
            v = values[(values["model"] == model) & (values["left_out"] == fold)].iloc[0].to_dict()
            for state, as_of in zip(g["state"], g["as_of"]):
                fc = forecast_at(races[(cycle, party)], as_of, state, v)
                if len(fc):
                    out.append(fc.assign(model=model, values=fold))
            races[(cycle, party)].save_cache()
    out = pd.concat(out, ignore_index=True)
    for col, places in (("W", 2), ("other", 2), ("share", 2), ("p10", 2), ("p90", 2), ("win", 4)):
        out[col] = out[col].astype(float).round(places)
    return out


def second():
    races = {k: ps.Race(*k) for k in ps.OPEN}
    t, actual = truth(races)
    values, _, _ = ps.fit(races, extra=YEARS)
    year = values[values["left_out"].isin(list(YEARS))]
    print("the year left out (rule 10): fitted values\n" + year.to_string(index=False), flush=True)

    # the folds of section 3 are unchanged by the extra ones
    old = pd.read_csv(VALUES)
    same = values[~values["left_out"].isin(list(YEARS))].reset_index(drop=True)
    num = ["beta", "kappa", "lambda", "tau", "sigma_p", "sigma_u", "fit_mse", "fit_log_loss"]
    assert np.allclose(same[num].to_numpy(float), old[num].to_numpy(float), atol=1e-4), "section 3's folds moved"
    print("section 3's folds are unchanged by the two added")

    four = [r for rs in YEARS.values() for r in rs]
    keys = scored_keys(t)
    keys = keys[[k in four for k in zip(keys["cycle"], keys["party"])]]

    # the rebuilt forecasts equal the committed ones at the committed values
    committed = pd.read_csv(FORECASTS, parse_dates=["as_of", "date_known"]).merge(keys[FKEY], on=FKEY)
    again = rebuild(races, keys, values, lambda cy, p: f"{cy} {p}")
    cmp = committed.merge(again, on=["model"] + FKEY + ["candidate_key"], suffixes=("", "_again"))
    assert len(cmp) == len(committed) == len(again), (len(cmp), len(committed), len(again))
    for col in ("share", "p10", "p90", "win"):
        assert np.allclose(cmp[col], cmp[col + "_again"], atol=1e-9), col
    print(f"the rebuilt forecasts match the committed table ({len(cmp)} rows)")

    f1, c1 = score(committed, t, actual, races)
    f2, c2 = score(rebuild(races, keys, values, lambda cy, p: str(cy)), t, actual, races)
    h1 = report(f1, c1, "THE FOUR RACES, FIRST READING (each race left out)")
    h2 = report(f2, c2, "THE FOUR RACES, SECOND READING (the year left out)")
    for col in MEASURES:
        a, b = side_by_side(h1, col, ["cycle", "party"]), side_by_side(h2, col, ["cycle", "party"])
        a2, b2 = side_by_side(h1, col), side_by_side(h2, col)
        t2 = pd.concat([a, a2]).join(pd.concat([b, b2]), lsuffix=" (race out)", rsuffix=" (year out)")
        show(f"{col}, headline, the two readings side by side", t2[[x for x in t2.columns if "contests" not in x
                                                                      and "forecasts" not in x]])
    cov = pd.concat([coverage(h1, ["cycle", "party"]), coverage(h1)]).join(
        pd.concat([coverage(h2, ["cycle", "party"]), coverage(h2)]), lsuffix=" (race out)", rsuffix=" (year out)")
    show("coverage, headline, the two readings side by side", cov)

    out = pd.read_csv(OUT, parse_dates=["as_of", "held"])
    write(pd.concat([out[out["reading"] != SECOND], table(f2, SECOND)], ignore_index=True))


# ---------------------------------------------------------------- the declared round: a diagnostic of the ranges

def split(c, by):
    """D1: the share of results below the 10th percentile, within the range and above the 90th."""
    g = c.groupby(["model"] + by, sort=True)["pos"].value_counts(normalize=True).unstack(fill_value=0.0)
    g = g.reindex(columns=["below", "within", "above"], fill_value=0.0)
    return g.assign(candidates=c.groupby(["model"] + by, sort=True).size())


def ranges():
    races = {k: ps.Race(*k) for k in ps.OPEN}
    t, actual = truth(races)
    fc = pd.read_csv(FORECASTS, parse_dates=["as_of", "date_known"])
    sfc = fc.merge(scored_keys(t)[FKEY], on=FKEY).merge(t.loc[t["why"].eq(""), CKEY], on=CKEY)
    f, c = score(sfc, t, actual, races)
    head = f[f["field"] >= 2]
    c = c.merge(head[["model"] + FKEY + ["horizon"]], on=["model"] + FKEY)
    print(f"headline candidate rows: {(c['model'] == MODELS[0]).sum()} (the model), "
          f"{(head['model'] == MODELS[0]).sum()} forecasts")
    c["pos"] = np.where(c["actual"] < c["p10"], "below", np.where(c["actual"] > c["p90"], "above", "within"))
    still = {k: set(races[k[:2]].field(d)) for k, d in zip(zip(t["cycle"], t["party"], t["state"]), t["held"])
             if k in actual and k[:2] in races}
    key = list(zip(c["cycle"], c["party"], c["state"]))
    c["still_in"] = [cand in still[k] for k, cand in zip(key, c["candidate_key"])]
    c["no_line"] = [cand not in actual[k] for k, cand in zip(key, c["candidate_key"])]
    c["rank"] = c.groupby(["model"] + FKEY)["share"].rank(ascending=False, method="first")
    c["top_two"] = c["rank"] <= 2
    show("D1: results against the 10th-90th range", split(c, ["horizon"]))
    show("D2: by whether the candidate was still in the field on the morning of the vote", split(c, ["horizon", "still_in"]))
    left = c[~c["still_in"]]
    show("D2: candidates who had left, and those of them with no line in the result",
         left.groupby(["model", "horizon"]).agg(left=("no_line", "size"), no_line=("no_line", "sum"),
                                                mean_expected=("share", "mean"), mean_result=("actual", "mean")), 2)
    show("D3: candidates still in, the top two by expected share and the rest",
         split(c[c["still_in"]], ["horizon", "top_two"]))
    o = c.groupby(["model"] + FKEY + ["horizon"]).agg(result=("actual", "sum"), other=("other", "first")).reset_index()
    o["diff"] = (100 - o["result"]) - o["other"]
    show("D4: the other share in the result less the one the forecast used, in points",
         o.groupby(["model", "horizon"])["diff"].agg(forecasts="size", mean="mean", median="median",
                                                      over_5=lambda x: (x > 5).mean(),
                                                      under_5=lambda x: (x < -5).mean()), 2)
    show("D5: calibration, headline, 30 days", calibration(c[c["horizon"] == 30]))


if __name__ == "__main__":
    args = sys.argv[1:]
    ranges() if "--ranges" in args else second() if "--year" in args else first()
