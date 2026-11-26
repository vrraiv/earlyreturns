"""Senate special elections against the House specials' environment pattern (SP-3; rules in SPECIALS.md section 1).

Step 2 (index): the recent-specials term for 1989-2007 from The Downballot's Special Elections Index (store-and-link:
read from data/linked/, only the derived term by month is written), and its comparison with the House term on
2008-2022 dates. Uses no Senate result.
  For each index special: swing = its margin minus the district's margin in the most recent earlier regular election
  shown (the sheet's "Margin Differences" column for that year); expected = the H estimate on the special's date
  (m by half of the term, fitted on all House specials) minus the national House margin in that earlier year;
  residual = swing - expected. Term on a date = mean residual of index specials in the prior 12 months x n / (n + 2).

Step 2b (rule 6a): G, the generic ballot as an exponentially weighted mean over the 182 days before a date (from 2017
over polls, before over FiveThirtyEight's daily average); its half-life chosen on the House specials backtest
(G replacing the whole House environment), default the flat six-month mean unless a half-life beats it by 0.3 RMSE.
Uses no Senate result.

Run:  python src/model/senate_specials.py index | halflife
Writes data/processed/senate_specials_index_term.csv (term by month) and data/processed/senate_specials_index_check.json;
halflife writes data/processed/senate_specials_halflife.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT, latest_linked  # noqa: E402
import environment as E  # noqa: E402
import special_model as SM  # noqa: E402

OUT = ROOT / "data" / "processed"
K = 2
NAT = pd.read_csv(ROOT / "data/interim/house_national_vote.csv").set_index("year").two_party_margin_D
_MODEL = None
_ENV = {}


def model():
    global _MODEL
    if _MODEL is None:
        _MODEL = E.fit(E.training())
    return _MODEL


def m_all():
    """m by half of the term, fitted on all House specials (2007-2026): rule 6's H before 2008."""
    sp = SM.load()
    sp["half2"] = (sp.term_year >= 3).astype(int)
    return {h: SM.best_m(sp[sp.half2 == h]) for h in (0, 1)}


def env_parts(date):
    date = pd.Timestamp(date)
    if date not in _ENV:
        e0, info = E.env_on(date, "fund", 0.0, model())
        slope = E.env_on(date, "fund", 1.0, model())[0] - e0
        _ENV[date] = (e0, slope)
    return _ENV[date]


def h_estimate(date, m):
    e0, slope = env_parts(date)
    return e0 + slope * m[int(SM.term_year(pd.Timestamp(date)) >= 3)]


def index_specials():
    """One row per index special: date, district, swing against the most recent earlier regular election, that year."""
    x = pd.ExcelFile(latest_linked("downballot", "special_elections_index.xlsx"))
    rows = []
    for s in x.sheet_names[2:]:
        d = x.parse(s, header=None)
        hdr = d.iloc[2].tolist()
        c_date, c_margin = hdr.index("Date"), hdr.index("Margin")
        years = {}
        for c in range(c_margin + 1, len(hdr)):
            v = hdr[c]
            if isinstance(v, str):
                break
            if pd.notna(v):
                years[c] = int(v)
        for _, r in d.iloc[3:].iterrows():
            dt = pd.to_datetime(r[c_date], errors="coerce")
            if pd.isna(dt) or pd.isna(r[c_margin]):
                continue
            earlier = [(y, c) for c, y in years.items() if pd.Timestamp(f"{y}-11-01") < dt and pd.notna(r[c])]
            if not earlier:
                continue
            y, c = max(earlier)
            rows.append({"date": dt, "district": r[1], "swing": float(r[c]), "earlier_year": y})
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def index_residuals():
    m = m_all()
    d = index_specials()
    d["h_env"] = d.date.map(lambda t: h_estimate(t, m))
    d["expected"] = d.h_env - d.earlier_year.map(NAT)
    d["resid"] = d.swing - d.expected
    return d, m


def term_on(d, date, k=K):
    date = pd.Timestamp(date)
    w = d[(d.date < date) & (d.date >= date - pd.Timedelta(days=365))]
    if not len(w):
        return 0.0, 0
    return float(w.resid.mean() * len(w) / (len(w) + k)), int(len(w))


def index_step():
    import single_race as SR
    d, m = index_residuals()
    months = pd.date_range("1989-01-01", "2023-01-01", freq="MS")
    series = pd.DataFrame([(t, *term_on(d, t)) for t in months], columns=["date", "index_term", "n_index"])
    series.round(3).to_csv(OUT / "senate_specials_index_term.csv", index=False)
    cmp = series[(series.date >= "2008-01-01") & (series.date < "2023-01-01")].copy()
    house = [SR.special_environment(t) for t in cmp.date]
    cmp["house_term"] = [h["recent_specials_shift"] for h in house]
    cmp["n_house"] = [h["n_recent"] for h in house]
    both = cmp[(cmp.n_index > 0) & (cmp.n_house > 0)]
    out = {"n_index_specials": int(len(d)), "by_kind": {"US House": int(d.district.str.match(r"^[A-Z]{2}-(\d+|AL)$").sum())},
           "years": [int(d.date.dt.year.min()), int(d.date.dt.year.max())], "m_all_house_specials": m,
           "residual_mean": float(d.resid.mean()), "residual_sd": float(d.resid.std()),
           "comparison_2008_2022": {"months": int(len(both)), "corr": float(both.index_term.corr(both.house_term)),
                                    "mean_index": float(both.index_term.mean()), "mean_house": float(both.house_term.mean()),
                                    "mean_diff_index_minus_house": float((both.index_term - both.house_term).mean()),
                                    "sd_index": float(both.index_term.std()), "sd_house": float(both.house_term.std()),
                                    "by_year": both.assign(y=both.date.dt.year).groupby("y")[["index_term", "house_term"]].mean().round(2)
                                    .reset_index().to_dict("records")},
           "senate_dates": {}}
    sen = pd.read_csv(ROOT / "data/interim/senate_specials.csv", parse_dates=["date"])
    for _, r in sen[(sen.date >= "1989-01-01") & (sen.date < "2008-01-01")].iterrows():
        v, n = term_on(d, r.date)
        out["senate_dates"][r.race] = {"date": str(r.date.date()), "index_term": v, "n": n}
    (OUT / "senate_specials_index_check.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"{len(d)} index specials {out['years']}, {out['by_kind']['US House']} U.S. House; m (all House specials) {m}")
    print(f"residual mean {out['residual_mean']:.2f}, SD {out['residual_sd']:.2f}")
    c = out["comparison_2008_2022"]
    print(f"2008-2022, {c['months']} months with both: corr {c['corr']:.2f}; mean index {c['mean_index']:+.2f}, house {c['mean_house']:+.2f}; "
          f"SD index {c['sd_index']:.2f}, house {c['sd_house']:.2f}")
    print(pd.DataFrame(c["by_year"]).to_string(index=False))
    print("index term on Senate dates 1989-2007:", {k: (round(v["index_term"], 2), v["n"]) for k, v in out["senate_dates"].items()})


# ---------------- step 2b: G, the generic ballot over the prior six months ----------------
WINDOW_G, POLLS_FROM, MARGIN_G = 182, pd.Timestamp("2017-01-01"), 0.3
HALF_LIVES = [7, 14, 30, 60, 90, 182, None]          # None = flat six-month mean
_GB = {}


def gb_sources():
    if not _GB:
        import generic_ballot as GB
        _GB["polls"] = pd.concat([GB.polls_538(), GB.polls_votehub()]).sort_values("end").reset_index(drop=True)
        top = GB.topline()
        _GB["daily"] = top[top.margin_2p.notna()][["date", "margin_2p"]].rename(columns={"date": "end"})
    return _GB


def g_on(date, half_life):
    """Exponentially weighted generic-ballot margin over the WINDOW_G days before date (the day itself excluded)."""
    date = pd.Timestamp(date)
    s = gb_sources()
    src = s["polls"] if date >= POLLS_FROM else s["daily"]
    w = src[(src.end < date) & (src.end >= date - pd.Timedelta(days=WINDOW_G))]
    if not len(w):
        return np.nan, 0, None
    age = (date - w.end).dt.days.to_numpy(float)
    wt = np.ones_like(age) if half_life is None else 0.5 ** (age / half_life)
    return float(np.sum(wt * w.margin_2p) / wt.sum()), int(len(w)), int(age.max())


def halflife_step():
    import single_race as SR
    sp = SR.specials()
    rows = []
    for i, r in sp.iterrows():                       # the same 68 specials single_race.backtest scores
        earlier = sp.iloc[:i]
        if len(earlier[earlier.date < r.date]) < SR.MIN_HALF:
            continue
        row = {"date": str(r.date.date()), "race": f"{r.state}-{int(r.district)}", "actual": float(r.margin_2p)}
        for h in HALF_LIVES:
            g, n, oldest = g_on(r.date, h)
            mu = SR.HS["const"] + SR.HS["b_lean2"] * r.lean2 + SR.HS["g_nat"] * g
            row[f"err_{h or 'flat'}"] = r.margin_2p - mu
        row["n_g"], row["oldest_day"] = n, oldest
        rows.append(row)
    b = pd.DataFrame(rows)
    grid = {str(h or "flat"): {"rmse": float(np.sqrt((b[f"err_{h or 'flat'}"] ** 2).mean())),
                               "mae": float(b[f"err_{h or 'flat'}"].abs().mean()), "mean_err": float(b[f"err_{h or 'flat'}"].mean())}
            for h in HALF_LIVES}
    flat = grid["flat"]["rmse"]
    best = min((k for k in grid if k != "flat"), key=lambda k: grid[k]["rmse"])
    chosen = best if grid[best]["rmse"] <= flat - MARGIN_G else "flat"
    bt = json.loads((OUT / "single_race_backtest.json").read_text())
    short = b[b.oldest_day < WINDOW_G - 7]
    out = {"n": int(len(b)), "grid": grid, "best_half_life": best, "chosen": chosen, "rule": f"flat unless a half-life beats it by {MARGIN_G} RMSE",
           "reference_house_backtest_rmse": bt["model"]["rmse"], "reference_last_house_vote_rmse": bt["naive_last_house_vote"]["rmse"],
           "specials_with_short_window": short[["date", "race", "n_g", "oldest_day"]].to_dict("records"),
           "note": "G replaces the whole House environment (no recent-specials term) at the House prior's coefficient; all House specials 2007-2026"}
    (OUT / "senate_specials_halflife.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"{len(b)} House specials; reference: House backtest RMSE {out['reference_house_backtest_rmse']:.2f}, "
          f"last House vote {out['reference_last_house_vote_rmse']:.2f}")
    print(pd.DataFrame(grid).T.round(2).to_string())
    print(f"best half-life {best}; chosen: {chosen}")
    print("short windows:", out["specials_with_short_window"])


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "index"
    if what == "index":
        index_step()
    elif what == "halflife":
        halflife_step()
