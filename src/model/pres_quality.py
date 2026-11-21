"""Pollster quality: a separate test of weighting polls by 538's ratings as they stood (ELECTORAL_COLLEGE.md, section 11,
"Pollster quality: a separate test"). Fitted on 2016 and 2020 against results; 2024 is opened only if the fit's gate
opens, and only through test2024.

Each poll's weight in the fixed nowcast (pres_nowcast.BASE) is multiplied by exp(-gamma * z), z being the firm's 538
error score (predictive plus-minus 2016 and 2020, POLLSCORE 2024) standardized across the firms that version rates.
Unrated firms get z_u. Score: each place's average from polls that ended before 7 days out (30 and 60 reported),
against the result; places are the states, DC and the nation.

Run:  python src/model/pres_quality.py fit        (checks, then the fit on 2016 and 2020; never reads 2024)
      python src/model/pres_quality.py test2024   (refuses unless the committed fit opened the gate)
      python src/model/pres_quality.py stability  (how much ratings change between versions; reads no 2024 result)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
import pres_nowcast as P  # noqa: E402

INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "538_github"
GAMMAS = (0.0, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0)
ZU = (0.0, 0.5, 1.0)
DATES = (7, 30, 60)
BIDEN_OUT = pd.Timestamp("2024-07-21")
FLIPS = 2000


def ratings():
    """{cycle: (key column, {key: z})}: each version standardized across the firms it rates."""
    r16 = pd.read_csv(RAW / "2026-11-21" / "pollster-ratings-2016.csv")
    r20 = pd.read_csv(RAW / "2026-11-21" / "pollster-ratings-2020.csv", encoding="utf-8-sig")
    r20.columns = [" ".join(c.split()) for c in r20.columns]
    r24 = pd.read_csv(RAW / "2026-11-01" / "pollster-ratings-combined.csv")

    def z(keys, vals):
        v = pd.to_numeric(pd.Series(vals), errors="coerce")
        ok = v.notna().values
        v = (v - v[ok].mean()) / v[ok].std()
        return {k: float(x) for k, x, o in zip(keys, v, ok) if o}
    return {2016: ("pollster", z(r16.Pollster.str.strip(), r16["Predictive Plus-Minus"])),
            2020: ("pollster_rating_id", z(r20["Pollster Rating ID"], r20["Predictive Plus-Minus"])),
            2024: ("pollster_rating_id", z(r24.pollster_rating_id, r24.POLLSCORE))}


def load(cycles):
    """Stage 1's loader, with the rating key carried, districts dropped, and 2024 (Harris against Trump, polls ending
    on or after 21 July 2024) only when asked for by name."""
    p = pd.read_csv(INTERIM / "president_general_polls.csv", low_memory=False)
    p = p[p.cycle.isin(cycles) & ~p.presumptive & ~p.state_subsample.fillna(False).astype(bool)].copy()
    if 2024 in cycles:
        e = pd.to_datetime(p.end_date.fillna(p.mid_date))
        p = p[(p.cycle != 2024) | (e >= BIDEN_OUT)]
        x = p[p.cycle == 2024]
        assert x.d_candidate.str.contains("Harris").all() and x.r_candidate.str.contains("Trump").all()
        assert (pd.to_datetime(x.end_date.fillna(x.mid_date)) >= BIDEN_OUT).all()
    p["pop"] = p.population.fillna("lv").str.lower()
    p["h2h"] = p.head_to_head.fillna(False).astype(bool)
    p["rank"] = p["pop"].map(P.POP_RANK).fillna(4)
    p = p[p.h2h == p.groupby("poll_id").h2h.transform("max")]
    p = p[p["rank"] == p.groupby("poll_id")["rank"].transform("min")]
    p["m"] = 100 * (p.d_pct - p.r_pct) / (p.d_pct + p.r_pct)
    q = p.groupby("poll_id").agg(cycle=("cycle", "first"), geo=("geo", "first"), pollster=("pollster", "first"),
                                 rid=("pollster_rating_id", "first"), pop=("pop", "first"), n=("sample_size", "first"),
                                 partisan=("partisan", "first"), end=("end_date", "first"), mid=("mid_date", "first"),
                                 election=("election_date", "first"), m=("m", "mean")).reset_index()
    q["end"] = pd.to_datetime(q.end.fillna(q.mid))
    q["election"] = pd.to_datetime(q.election)
    q["pkey"] = [P.firm_key(n, i) for n, i in zip(q.pollster, q.poll_id)]
    q["n"] = q.n.fillna(600)
    q["sg"] = np.where(q.partisan == "DEM", 1, np.where(q.partisan == "REP", -1, 0))
    q = q[~q.geo.str.contains("-", na=False)]                      # no results for Maine's and Nebraska's districts
    R = ratings()
    q["z"] = np.nan
    for c, (col, zmap) in R.items():
        m = q.cycle == c
        keys = q.loc[m, "pollster"].str.strip() if col == "pollster" else q.loc[m, "rid"]
        q.loc[m, "z"] = keys.map(zmap).values
    return q.dropna(subset=["m"]).sort_values(["cycle", "geo", "end"]).reset_index(drop=True)


def results(cycles):
    r = pd.read_csv(INTERIM / "state_presidential.csv")
    r = r[r.year.isin(cycles)]
    out = {(int(y), s): float(m) for y, s, m in zip(r.year, r.state, r.margin_2p)}
    for y, m in r.groupby("year").national_margin_2p.first().items():
        out[(int(y), "US")] = float(m)
    return out


def average(pool, t, gamma, zu):
    pool = pool[pool.end < t]
    if not len(pool):
        return np.nan
    w = P.weights(pool, t, P.BASE) * np.exp(-gamma * pool.z.fillna(zu).values)
    return float(np.average(P.adjusted(pool, P.BASE), weights=w))


def errors(q, res, gamma, zu, days):
    """One row per (cycle, place) with at least one poll before the date: average minus result."""
    rows = []
    for (c, g), d in q.groupby(["cycle", "geo"]):
        if (c, g) not in res:
            continue
        t = d.election.iloc[0] - pd.Timedelta(days=days)
        a = average(d, t, gamma, zu)
        if not np.isnan(a):
            rows.append({"cycle": c, "geo": g, "err": a - res[(c, g)]})
    return pd.DataFrame(rows)


def losses(e):
    """Per cycle: raw loss, loss with the year's mean error removed, the nation's squared error, places."""
    out = {}
    for c, d in e.groupby("cycle"):
        out[int(c)] = {"loss": float((d.err ** 2).mean()),
                       "loss_within": float(((d.err - d.err.mean()) ** 2).mean()),
                       "mean_err": float(d.err.mean()),
                       "nation_sq": float(d.loc[d.geo == "US", "err"].iloc[0] ** 2) if (d.geo == "US").any() else None,
                       "places": int(len(d))}
    return out


def grid():
    cells = [(0.0, 0.0)] + [(g, z) for g in GAMMAS if g > 0 for z in ZU]
    return cells


def checks(q):
    rng = np.random.default_rng(1)
    groups = list(q.groupby(["cycle", "geo"]))
    bad = 0
    same = 0.0
    for k in rng.choice(len(groups), size=15, replace=False):
        (c, g), d = groups[k]
        t = d.election.iloc[0] - pd.Timedelta(days=7)
        if not (d.end < t).any():
            continue
        d2 = d.copy()
        d2.loc[d2.end >= t, "m"] += 50
        bad += int(abs(average(d, t, 0.5, 0.5) - average(d2, t, 0.5, 0.5)) > 1e-9)
        same = max(same, abs(average(d, t, 0.0, 0.0) - P.average(d, t, P.BASE)))
    print(f"leak test: {'PASS' if not bad else f'FAIL {bad}'}; gamma 0 = baseline average: "
          f"{'PASS' if same < 1e-9 else 'FAIL'} ({same:.1e})", flush=True)
    if bad or same >= 1e-9:
        raise SystemExit("a check failed")


def fit():
    cyc = (2016, 2020)
    q = load(cyc)
    assert set(q.cycle) == set(cyc)
    cov = q.groupby("cycle").z.apply(lambda v: round(float(v.notna().mean()), 3)).to_dict()
    print("rated share of polls:", cov)
    checks(q)
    res = results(cyc)
    table = {}
    for g, z in grid():
        L = {d: losses(errors(q, res, g, z, d)) for d in DATES}
        table[(g, z)] = L
        print(f"  gamma {g}, z_u {z}: 7 days " + ", ".join(f"{c} {v['loss']:.2f} (within {v['loss_within']:.2f})"
                                                        for c, v in L[7].items()), flush=True)
    score = {k: np.mean([v[7][c]["loss"] for c in cyc]) for k, v in table.items()}
    pick = min(score, key=score.get)
    base = table[(0.0, 0.0)][7]
    gate = pick != (0.0, 0.0) and all(table[pick][7][c]["loss"] < base[c]["loss"] for c in cyc)
    out = {"rated_share": {int(k): v for k, v in cov.items()},
           "grid": {f"{g}/{z}": {str(d): v for d, v in L.items()} for (g, z), L in table.items()},
           "fit_score_7d": {f"{g}/{z}": round(float(v), 3) for (g, z), v in score.items()},
           "picked": {"gamma": pick[0], "z_u": pick[1]}, "gate_open": bool(gate)}
    (OUT / "pres_quality_fit.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"\npicked gamma {pick[0]}, z_u {pick[1]}; fit score {score[pick]:.3f} against baseline "
          f"{score[(0.0, 0.0)]:.3f}; better in 2016: {table[pick][7][2016]['loss'] < base[2016]['loss']}, "
          f"in 2020: {table[pick][7][2020]['loss'] < base[2020]['loss']}; gate {'OPEN' if gate else 'closed'}")


def test2024():
    f = json.loads((OUT / "pres_quality_fit.json").read_text())
    if not f["gate_open"]:
        raise SystemExit("the fit did not open the gate: 2024 stays closed")
    import subprocess
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(OUT / "pres_quality_fit.json")], cwd=ROOT).returncode:
        raise SystemExit("commit the fit before opening 2024")
    g, z = f["picked"]["gamma"], f["picked"]["z_u"]
    q = load((2024,))
    print("rated share of 2024 polls:", round(float(q.z.notna().mean()), 3))
    res = results((2024,))
    out = {"picked": f["picked"]}
    for d in DATES:
        eb, ec = errors(q, res, 0.0, 0.0, d), errors(q, res, g, z, d)
        m = eb.merge(ec, on=["cycle", "geo"], suffixes=("_b", "_c"))
        diff = (m.err_b ** 2 - m.err_c ** 2).values
        stat = diff.mean()
        null = np.random.default_rng(0).choice([-1.0, 1.0], size=(FLIPS, len(diff))) @ diff / len(diff)
        p = float((np.sum(null >= stat) + 1) / (FLIPS + 1))
        out[str(d)] = {"baseline": losses(eb)[2024], "candidate": losses(ec)[2024], "gain": float(stat),
                       "p_signflip": round(p, 4)}
        print(f"{d} days: baseline {out[str(d)]['baseline']['loss']:.3f}, candidate {out[str(d)]['candidate']['loss']:.3f}, "
              f"gain {stat:.3f}, p {p:.4f}; within-year {out[str(d)]['baseline']['loss_within']:.3f} against "
              f"{out[str(d)]['candidate']['loss_within']:.3f}")
    out["passes"] = bool(out["7"]["gain"] > 0 and out["7"]["p_signflip"] < 0.05)
    (OUT / "pres_quality_2024.json").write_text(json.dumps(out, indent=1, default=float))
    print("passes:", out["passes"])


def _norm(s):
    import re
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower().replace("&", "and")).strip()


def stability():
    """How stable are the ratings? Firms rated in consecutive versions (2016-2020 by name, 2016's ids being another
    scheme; 2020-2024 by rating id), their z in each, and what a four-year-old version would do to each poll's weight
    at the fitted setting. Also, as a diagnostic on a fit year only: the 2016 ratings applied to 2020's polls."""
    r16 = pd.read_csv(RAW / "2026-11-21" / "pollster-ratings-2016.csv")
    r20 = pd.read_csv(RAW / "2026-11-21" / "pollster-ratings-2020.csv", encoding="utf-8-sig")
    r20.columns = [" ".join(c.split()) for c in r20.columns]
    r24 = pd.read_csv(RAW / "2026-11-01" / "pollster-ratings-combined.csv")
    R = ratings()
    z16 = {_norm(k): v for k, v in R[2016][1].items()}
    z20, z24 = R[2020][1], R[2024][1]
    name20 = {i: _norm(n) for i, n in zip(r20["Pollster Rating ID"], r20.Pollster)}
    f = json.loads((OUT / "pres_quality_fit.json").read_text())
    g, zu = f["picked"]["gamma"], f["picked"]["z_u"]
    q = load((2016, 2020))
    # 2024 polls: pollster ids only, for coverage and poll counts; no margin or result is used
    p24 = pd.read_csv(INTERIM / "president_general_polls.csv", low_memory=False,
                      usecols=["cycle", "poll_id", "pollster_rating_id", "presumptive", "end_date", "geo"])
    p24 = p24[(p24.cycle == 2024) & ~p24.presumptive.astype(bool) & (pd.to_datetime(p24.end_date) >= BIDEN_OUT)
              & ~p24.geo.str.contains("-", na=False)].drop_duplicates("poll_id")
    out = {}
    pairs = {
        "2016_to_2020": (q[q.cycle == 2020].rid.map(name20).map(z16), q[q.cycle == 2020].z),
        "2020_to_2024": (p24.pollster_rating_id.map(z20), p24.pollster_rating_id.map(z24)),
    }
    firm_pairs = {
        "2016_to_2020": pd.DataFrame({"old": [z16.get(name20[i]) for i in z20], "new": list(z20.values())}),
        "2020_to_2024": pd.DataFrame({"old": [z20.get(i) for i in z24], "new": list(z24.values())}),
    }
    for k, (old, new) in pairs.items():
        fp = firm_pairs[k].dropna()
        both = old.notna() & new.notna()
        lr = (-g * old.fillna(zu)) - (-g * new.fillna(zu))           # log of old weight factor over new
        out[k] = {
            "firms_in_both": int(len(fp)),
            "corr_firms_pearson": round(float(fp.old.corr(fp.new)), 3),
            "corr_firms_spearman": round(float(fp.old.corr(fp.new, method="spearman")), 3),
            "corr_polls_pearson": round(float(old[both].corr(new[both])), 3),
            "polls_rated_new": round(float(new.notna().mean()), 3),
            "polls_rated_old": round(float(old.notna().mean()), 3),
            "polls_rated_new_not_old": round(float((new.notna() & old.isna()).mean()), 3),
            "median_abs_weight_change_pct": round(float(100 * np.median(np.abs(np.exp(lr) - 1))), 1),
            "polls_weight_off_by_25pct_or_more": round(float((np.abs(np.exp(lr) - 1) >= 0.25).mean()), 3),
        }
    # the firms that carry the most polls, z in each version
    cnt20 = q[q.cycle == 2020].groupby("rid").size().sort_values(ascending=False).head(12)
    cnt24 = p24.groupby("pollster_rating_id").size().sort_values(ascending=False).head(12)
    out["top_2020_firms"] = [{"firm": r20.set_index("Pollster Rating ID").Pollster.get(i), "polls": int(n),
                              "z2016": z16.get(name20.get(i)), "z2020": z20.get(i)} for i, n in cnt20.items()]
    out["top_2024_firms"] = [{"firm": r24.set_index("pollster_rating_id").pollster.get(i), "polls": int(n),
                              "z2020": z20.get(i), "z2024": z24.get(i)} for i, n in cnt24.items()]
    # diagnostic on a fit year: 2020's polls weighted by the 2016 ratings (four years stale), fitted setting
    q20 = q[q.cycle == 2020].copy()
    res = results((2020,))
    stale = q20.assign(z=q20.rid.map(name20).map(z16))
    out["stale_2016_ratings_on_2020"] = {}
    for d in DATES:
        b = losses(errors(q20, res, 0.0, 0.0, d))[2020]
        cur = losses(errors(q20, res, g, zu, d))[2020]
        st = losses(errors(stale, res, g, zu, d))[2020]
        out["stale_2016_ratings_on_2020"][str(d)] = {
            "baseline": [round(b["loss"], 3), round(b["loss_within"], 3)],
            "current_2020_ratings": [round(cur["loss"], 3), round(cur["loss_within"], 3)],
            "stale_2016_ratings": [round(st["loss"], 3), round(st["loss_within"], 3)]}
    (OUT / "pres_quality_stability.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fit"
    {"fit": fit, "test2024": test2024, "stability": stability}[cmd]()
