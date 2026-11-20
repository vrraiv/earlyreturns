"""The Downballot's data sheets (https://www.the-downballot.com/p/data), a store-and-link source (DATA.md).

The Downballot welcomes use of its data with a citation and a link, and asks that whole spreadsheets not be
reproduced. So the sheets are fetched into the gitignored store (data/linked/downballot/<date>/), each fetch is
recorded in data/linked/manifest.json, and only tables derived here are committed.

  pres_state   Presidential results by state, 1828-2024: vote counts for the Democrat and the main opposition
               (National Republican 1828-32, Whig 1836-52, Republican from 1856; 1836's regional Whig tickets summed),
               -> data/interim/state_presidential_history.csv: two-party margin, the nation's, and the state's lean,
               computed here from the counts. The sheet's own partisanship score is not carried over.

Fetched for later cards and not yet used (whole workbooks, as .xlsx): the special elections index (1989-2022), open
and uncontested House seats (2006-2026), and district demographics (education and income; race by age and citizenship;
urban-rural classes). See DA-1 and DA-4 in the work plan.

Run:  python src/collect/downballot.py [fetch|build|all]   (default all; fetch skips files already in today's store)
"""
import csv
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch_linked, gsheet_csv, latest_linked  # noqa: E402

PAGE = "https://www.the-downballot.com/p/data"
SHEETS = {
    "pres_state.csv": {"sheet_id": "1D-edaVHTnZNhVU840EPUhz3Cgd7m39Urx7HM8Pq6Pus", "gid": 29622862,
                       "title": "Presidential results by state, 1828-2024"},
}
BOOKS = {
    "special_elections_index.xlsx": {"sheet_id": "1mP8z1TWsrJbWGXk_pz3QgOZQpAmQxLY6sZjPp4qzY6c",
                                     "title": "Special Elections Index and results data, 1989-2022"},
    "open_uncontested_house.xlsx": {"sheet_id": "12RhR9oZZpyKKceyLO3C5am84abKzu2XqLWjP2LnQDgI",
                                    "title": "Open and uncontested congressional districts, 2006-2026"},
    "education_income_cd.xlsx": {"sheet_id": "1mCaLsoAuf19srhnU3UL37MoEOk4kcd_JxEgj96vIgJk",
                                 "title": "Education and income by congressional district and state, 2018-2022"},
    "race_age_citizenship_cd.xlsx": {"sheet_id": "14gFG9uQgJ-qTq3lkTNQ9YbhB9C8s3Gy78I1eqd7EpRM",
                                     "title": "Racial demographics by age and citizenship, by district and state, 2016-2019"},
    "urban_rural_cd118.xlsx": {"sheet_id": "1COIr226wGZQu1_i2ArF_ap5hUxYQ1Tb1QIH_tpUm0o4",
                               "title": "Rural/Suburban/Urban classification of districts, 118th Congress"},
}
INTERIM = ROOT / "data" / "interim"

STATE_ABBR = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
              "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
              "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
              "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
              "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
              "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
              "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
              "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
              "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
              "Wisconsin": "WI", "Wyoming": "WY", "Washington D.C.": "DC"}


def fetch():
    for name, s in SHEETS.items():
        p = fetch_linked("downballot", name, gsheet_csv(s["sheet_id"], s["gid"]), PAGE, meta=s)
        print("downballot", name, p.stat().st_size)
    for name, s in BOOKS.items():
        url = f"https://docs.google.com/spreadsheets/d/{s['sheet_id']}/export?format=xlsx"
        p = fetch_linked("downballot", name, url, PAGE, meta=s)
        print("downballot", name, p.stat().st_size)


def num(x):
    x = (x or "").replace(",", "").strip()
    try:
        return float(x)
    except ValueError:
        return None


def pres_state():
    """Vote-count block of the sheet: row 0 has the year over each group's 'Total' column, row 1 the candidate labels
    ('Name - Party'). The block runs from the first 'Total' to the first partisanship-score ('P.S.') column."""
    rows = list(csv.reader(latest_linked("downballot", "pres_state.csv").open(encoding="utf-8")))
    r0, r1 = rows[0], rows[1]
    start, end = r1.index("Total"), r0.index("P.S.")
    groups, cur = [], None
    for c in range(start, end):
        if r1[c] == "Total":
            cur = {"year": int(r0[c]), "total": c, "cands": []}
            groups.append(cur)
        elif r1[c]:
            cur["cands"].append(c)
    out = []
    for g in groups:
        d_col, r_col = g["cands"][0], g["cands"][1]
        r_party = r1[r_col].rsplit(" - ", 1)[-1]
        r_cols = [r_col] + [c for c in g["cands"][2:] if r1[c].rsplit(" - ", 1)[-1] == r_party]   # 1836's Whigs
        for row in rows[2:]:
            name = row[0].strip()
            st = "US" if name == "Nationwide" else STATE_ABBR.get(name)
            if st is None:
                continue
            tot, d = num(row[g["total"]]), num(row[d_col])
            rs = [num(row[c]) for c in r_cols]
            if not tot or d is None or any(v is None for v in rs) or d + sum(rs) <= 0:
                continue      # not yet a state, or no popular vote (electors chosen by the legislature)
            r = sum(rs)
            out.append({"year": g["year"], "state": st, "d_candidate": r1[d_col].split(" - ")[0],
                        "r_candidate": " / ".join(r1[c].split(" - ")[0] for c in r_cols), "r_party": r_party,
                        "d_votes": d, "r_votes": r, "total_votes": tot})
    df = pd.DataFrame(out)
    df["margin_2p"] = 100 * (df.d_votes - df.r_votes) / (df.d_votes + df.r_votes)
    df["other_share"] = 100 * (1 - (df.d_votes + df.r_votes) / df.total_votes)
    nat = df[df.state == "US"].set_index("year").margin_2p.rename("national_margin_2p")
    df = df[df.state != "US"].join(nat, on="year")
    df["lean_2p"] = df.margin_2p - df.national_margin_2p
    # Derived table only: counts stay in the store; shares and leans are computed here.
    keep = ["year", "state", "d_candidate", "r_candidate", "r_party", "margin_2p", "national_margin_2p", "lean_2p",
            "other_share"]
    df = df[keep].sort_values(["year", "state"], ascending=[False, True])
    df.round(3).to_csv(INTERIM / "state_presidential_history.csv", index=False)
    print(f"state_presidential_history.csv: {len(df)} rows, {df.year.nunique()} elections "
          f"({df.year.min()}-{df.year.max()}), {df.state.nunique()} states")
    check(df)


def check(df):
    """Against the Wikipedia-built table for 1992-2024 (data/interim/state_presidential.csv)."""
    w = pd.read_csv(INTERIM / "state_presidential.csv")
    m = w.merge(df, on=["year", "state"], suffixes=("_wiki", "_db"))
    diff = (m.margin_2p_wiki - m.margin_2p_db).abs()
    print(f"check vs Wikipedia 1992-2024: {len(m)} of {len(w)} state-years matched; "
          f"margin difference median {diff.median():.3f}, max {diff.max():.3f} pts")
    big = m[diff > 0.25]
    if len(big):
        print(big[["year", "state", "margin_2p_wiki", "margin_2p_db"]].round(2).to_string(index=False))


def build():
    pres_state()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("fetch", "all"):
        fetch()
    if what in ("build", "all"):
        build()
