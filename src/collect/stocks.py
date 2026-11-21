"""Stock prices for the presidential fundamentals (EC-3): Robert Shiller's monthly S&P Composite series.

FRED keeps only the last ten years of the S&P 500 and the Dow (licensing), so the long history comes from Shiller's
"Irrational Exuberance" data (monthly averages of daily closes, 1871 on). The workbook states no licence beyond a
disclaimer, so it is treated as store-and-link (DATA.md): the workbook goes to the gitignored store
(data/linked/shiller/<date>/), each fetch is recorded in data/linked/manifest.json, and only the derived table below
is committed.

  -> data/interim/sp500_monthly_change.csv: month, the 12-month percentage change in the monthly average price.
     A month's figure is known once the month has ended.

Run:  python src/collect/stocks.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch_linked, latest_linked  # noqa: E402

URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
PAGE = "http://www.econ.yale.edu/~shiller/data.htm"


def build():
    p = latest_linked("shiller", "ie_data.xls")
    d = pd.read_excel(p, sheet_name="Data", header=None, skiprows=8, usecols=[0, 1])
    d.columns = ["date", "price"]
    d = d[pd.to_numeric(d.date, errors="coerce").notna() & pd.to_numeric(d.price, errors="coerce").notna()].copy()
    d["date"] = d.date.astype(float)
    s = d.date.map(lambda v: f"{v:.2f}")                           # "1871.1" is October: read two-digit months
    year = s.str[:4].astype(int)
    month = s.str[5:7].astype(int)
    out = pd.DataFrame({"month": pd.to_datetime(dict(year=year, month=month, day=1)), "price": d.price.astype(float)})
    out = out[out.month.dt.year >= 1946].sort_values("month").reset_index(drop=True)
    out["change_12m"] = 100 * (out.price / out.price.shift(12) - 1)
    out = out.dropna(subset=["change_12m"])
    out["change_12m"] = out.change_12m.round(3)
    out[["month", "change_12m"]].to_csv(ROOT / "data/interim/sp500_monthly_change.csv", index=False)
    print("sp500_monthly_change.csv:", len(out), "months,", out.month.min().date(), "to", out.month.max().date())


if __name__ == "__main__":
    fetch_linked("shiller", "ie_data.xls", URL, PAGE, meta={"title": "Shiller, Irrational Exuberance data (S&P Composite, monthly)"})
    build()
