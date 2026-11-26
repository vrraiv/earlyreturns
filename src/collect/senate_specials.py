"""U.S. Senate special elections off the general-election day, 1970 on, and post-November regular-seat runoffs (SP-3;
rules in SPECIALS.md section 1).

Universe: Wikipedia's "List of special elections to the United States Senate" (rows from 1970 on), each race's own page
for the deciding round's date and result. A race is kept when its deciding round was not on a regular November
general-election day and had a Democrat and a Republican. The runoff set (diagnostic only) is every Georgia and
Louisiana regular-seat Senate race whose infobox shows a round after the general-election day (the only states with
post-November Senate runoffs); the scan is in scan_runoffs().

Each race: deciding-round votes for the Democrat and the Republican (two-party margin), incumbency (+1 a sitting U.S.
senator from the state runs as a Democrat, -1 as a Republican), and the state's lean in the last federal general
election before the deciding round:
  presidential year   state two-party presidential margin minus the nation's (state_presidential_history.csv)
  midterm             all the state's House votes, Democrats against Republicans, minus the national House margin
                      (house_national_vote.csv); MIT House file (1976-2018), regular general-election rows. 1970 and
                      1974 from the yearly House page's district percentages, and 2022 (GA 2022, runoff set only)
                      from house_history.csv, neither with vote counts: the districts' two-party margins averaged
                      with equal weight.

Run:  python src/collect/senate_specials.py
Writes data/interim/senate_specials.csv
"""
import io
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from common import RAW, ROOT  # noqa: E402
from governors import get_page  # noqa: E402

LIST_PAGE = "List of special elections to the United States Senate"
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
PRES_YEARS = set(range(1968, 2028, 4))

# key: (page, date of deciding round, Democrat, Republican, incumbency, set, note)
RACES = {
    "VT1972": ("1972 United States Senate special election in Vermont", "1972-01-07", "Randolph T. Major", "Robert Stafford", -1, "special", ""),
    "NH1975": ("1975 United States Senate special election in New Hampshire", "1975-09-16", "John A. Durkin", "Louis C. Wyman", 0, "special",
               "rerun after the 1974 result could not be settled; the page's section heading says September 19, its text September 16"),
    "WA1983": ("1983 United States Senate special election in Washington", "1983-11-08", "Mike Lowry", "Daniel J. Evans", -1, "special", ""),
    "PA1991": ("1991 United States Senate special election in Pennsylvania", "1991-11-05", "Harris Wofford", "Dick Thornburgh", 1, "special", ""),
    "ND1992": ("1992 United States Senate special election in North Dakota", "1992-12-04", "Kent Conrad", "Jack Dalrymple", 1, "special",
               "Conrad held the state's other seat"),
    "TX1993": ("1993 United States Senate special election in Texas", "1993-06-05", "Bob Krueger", "Kay Bailey Hutchison", 1, "special",
               "runoff; the race page says June 6, the list June 5 (a Saturday, Texas's election day); June 5 used"),
    "OR1996": ("1996 United States Senate special election in Oregon", "1996-01-30", "Ron Wyden", "Gordon H. Smith", 0, "special", "mail ballot"),
    "MA2010": ("2010 United States Senate special election in Massachusetts", "2010-01-19", "Martha Coakley", "Scott Brown", 0, "special", ""),
    "MA2013": ("2013 United States Senate special election in Massachusetts", "2013-06-25", "Ed Markey", "Gabriel Gomez", 0, "special", ""),
    "NJ2013": ("2013 United States Senate special election in New Jersey", "2013-10-16", "Cory Booker", "Steve Lonegan", 0, "special", ""),
    "AL2017": ("2017 United States Senate special election in Alabama", "2017-12-12", "Doug Jones", "Roy Moore", 0, "special",
               "the appointee, Luther Strange, lost the primary"),
    "MS2018": ("2018 United States Senate special election in Mississippi", "2018-11-27", "Mike Espy", "Cindy Hyde-Smith", -1, "special", "runoff"),
    "GA2021S": ("2020–21 United States Senate special election in Georgia", "2021-01-05", "Raphael Warnock", "Kelly Loeffler", -1, "special", "runoff"),
    # diagnostic: regular-seat runoffs after November
    "GA1992": ("1992 United States Senate election in Georgia", "1992-11-24", "Wyche Fowler", "Paul Coverdell", 1, "runoff", ""),
    "LA2002": ("2002 United States Senate election in Louisiana", "2002-12-07", "Mary Landrieu", "Suzanne Haik Terrell", 1, "runoff", ""),
    "GA2008": ("2008 United States Senate election in Georgia", "2008-12-02", "Jim Martin", "Saxby Chambliss", -1, "runoff", ""),
    "LA2014": ("2014 United States Senate election in Louisiana", "2014-12-06", "Mary Landrieu", "Bill Cassidy", 1, "runoff", ""),
    "LA2016": ("2016 United States Senate election in Louisiana", "2016-12-10", "Foster Campbell", "John Kennedy", 0, "runoff", ""),
    "GA2021R": ("2020 United States Senate election in Georgia", "2021-01-05", "Jon Ossoff", "David Perdue", -1, "runoff", ""),
    "GA2022": ("2022 United States Senate election in Georgia", "2022-12-06", "Raphael Warnock", "Herschel Walker", 1, "runoff", ""),
}
STATE_OF = {"VT": "Vermont", "NH": "New Hampshire", "WA": "Washington", "PA": "Pennsylvania", "ND": "North Dakota", "TX": "Texas",
            "OR": "Oregon", "MA": "Massachusetts", "NJ": "New Jersey", "AL": "Alabama", "MS": "Mississippi", "GA": "Georgia",
            "LA": "Louisiana"}
# 1970 and 1974 midterm House results by district (percent), from the yearly House pages: {(year, state): [(D%, R%), ...]}
EARLY_HOUSE_PAGES = {1970: "1970 United States House of Representatives elections", 1974: "1974 United States House of Representatives elections"}


def general_day(d):
    return d.month == 11 and d.year % 2 == 0 and d.weekday() == 1 and 2 <= d.day <= 8


def votes_in_row(text):
    nums = [int(x.replace(",", "")) for x in re.findall(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{4,}\b", text)]
    return nums[0] if nums else None


def deciding_round(page, dem, rep):
    """Votes for dem and rep from the last results table on the page holding both (the deciding round)."""
    html, rev = get_page(page)
    soup = BeautifulSoup(html, "html.parser")
    last = lambda n: n.split()[-1]
    found = None
    for tb in soup.find_all("table", class_="wikitable"):
        rows = [tr.get_text(" ", strip=True) for tr in tb.find_all("tr")]
        if not any("Votes" in r or "votes" in r for r in rows[:3]):
            continue
        dv = [votes_in_row(r) for r in rows if last(dem) in r and dem.split()[0] in r]
        rv = [votes_in_row(r) for r in rows if last(rep) in r and rep.split()[0] in r]
        dv, rv = [v for v in dv if v], [v for v in rv if v]
        if dv and rv:
            total = next((votes_in_row(r) for r in rows if r.lower().startswith("total")), None)
            found = (dv[0], rv[0], total)
    if found is None:
        raise ValueError(f"no results table with both candidates: {page}")
    return found, rev


def house_midterm_lean(year, st):
    """(state D-R House margin, seats, uncontested seats, source) for a midterm year."""
    if year in EARLY_HOUSE_PAGES:
        html, rev = get_page(EARLY_HOUSE_PAGES[year])
        soup = BeautifulSoup(html, "html.parser")
        margins, unc, seen = [], 0, set()
        for tr in soup.find_all("tr"):
            x = re.sub(r"\s+", " ", tr.get_text(" ", strip=True).replace(" ", " "))
            m = re.match(rf"{STATE_OF[st]} (at-large|\d+) ", x)
            if not m or "%" not in x or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            d = sum(float(v) for v in re.findall(r"\(Democratic\) (\d+(?:\.\d+)?)%", x))
            r = sum(float(v) for v in re.findall(r"\(Republican\) (\d+(?:\.\d+)?)%", x))
            unc += int(d == 0 or r == 0)
            margins.append(100 * (d - r) / (d + r))
        return float(np.mean(margins)), len(margins), unc, f"{EARLY_HOUSE_PAGES[year]} (rev {rev}), district percentages, equal weight"
    if year > 2018:
        h = pd.read_csv(ROOT / "data/interim/house_history.csv")
        h = h[(h.year == year) & (h.state == st)]
        return (float(h.margin.mean()), int(len(h)), int((~h.contested.astype(bool)).sum()),
                "house_history.csv district margins (no vote counts), equal weight")
    h = pd.read_csv(sorted(RAW.glob("medsl/*/1976-2018-house.csv"))[-1], encoding="latin-1", low_memory=False)
    h = h[(h.year == year) & (h.state_po == st) & (h.stage == "gen") & (~h.special.astype(bool)) & (h.runoff.astype(str) != "True")]
    party = h.party.fillna("").str.lower()
    h = h.assign(side=np.where(party.str.startswith("democrat"), "D", np.where(party == "republican", "R", "")))
    by = h.pivot_table(index="district", columns="side", values="candidatevotes", aggfunc="sum").fillna(0)
    for c in "DR":
        if c not in by:
            by[c] = 0.0
    d, r = by.D.sum(), by.R.sum()
    return float(100 * (d - r) / (d + r)), int(len(by)), int(((by.D == 0) | (by.R == 0)).sum()), "MIT Election Lab House file, regular general"


def lean_for(st, date):
    """Lean in the last federal general election before the date."""
    years = [y for y in range(1968, 2026, 2) if pd.Timestamp(f"{y}-11-01") < date]
    y = max(years)
    nat = pd.read_csv(ROOT / "data/interim/house_national_vote.csv").set_index("year").two_party_margin_D
    if y in PRES_YEARS:
        p = pd.read_csv(ROOT / "data/interim/state_presidential_history.csv")
        row = p[(p.year == y) & (p.state == st)].iloc[0]
        return {"lean_year": y, "lean_kind": "presidential", "state_margin": row.margin_2p, "national_margin": row.national_margin_2p,
                "lean": row.lean_2p, "house_seats": np.nan, "house_uncontested": np.nan, "lean_source": "state_presidential_history.csv"}
    m, seats, unc, src = house_midterm_lean(y, st)
    return {"lean_year": y, "lean_kind": "midterm House vote", "state_margin": m, "national_margin": float(nat[y]),
            "lean": m - float(nat[y]), "house_seats": seats, "house_uncontested": unc, "lean_source": src}


def check_universe():
    """Every list row from 1970 on, its deciding-round date from the race's infobox, and whether it falls off the
    general-election day. Prints the rows the rule keeps, for comparison with RACES."""
    html, _ = get_page(LIST_PAGE)
    soup = BeautifulSoup(html, "html.parser")
    keep = []
    for tr in soup.find_all("table", class_="wikitable")[0].find_all("tr"):
        a = next((a for a in tr.find_all("a") if re.match(r"/wiki/\d{4}.*United_States_Senate_(special_)?elections?_in_", a.get("href", ""))), None)
        if not a:
            continue
        title = BeautifulSoup(a.get("title", ""), "html.parser").get_text() or a.get("href").split("/wiki/")[1].replace("_", " ")
        yr = int(title[:4])
        if yr < 1970 or yr > 2026:
            continue
        ph, _ = get_page(title)
        ib = BeautifulSoup(ph, "html.parser").find("table", class_="infobox")
        ds = [pd.Timestamp(x) for x in re.findall(rf"(?:{MONTHS}) \d{{1,2}}, \d{{4}}", ib.get_text(" ", strip=True)[:700] if ib else "")]
        last = max(ds) if ds else None
        if last is None or not general_day(last):
            keep.append((title, last))
    return keep


def main():
    rows = []
    for key, (page, date, dem, rep, inc, kind, note) in RACES.items():
        date = pd.Timestamp(date)
        st = key[:2]
        (dv, rv, total), rev = deciding_round(page, dem, rep)
        rows.append({"race": key, "state": st, "date": date.date(), "set": kind, "dem": dem, "rep": rep, "d_votes": dv, "r_votes": rv,
                     "total_votes": total, "margin_2p": 100 * (dv - rv) / (dv + rv), "inc": inc, **lean_for(st, date),
                     "page": page, "revid": rev, "note": note})
    df = pd.DataFrame(rows)
    df.round(3).to_csv(ROOT / "data/interim/senate_specials.csv", index=False)
    print(df[["race", "date", "set", "dem", "rep", "margin_2p", "inc", "lean_year", "lean_kind", "state_margin", "national_margin", "lean",
              "house_seats", "house_uncontested"]].round(1).to_string(index=False))
    kept = check_universe()
    print("\nuniverse check (list rows from 1970 whose last infobox date is off the general-election day, or has no date):")
    for t, d in kept:
        print(f"  {d.date() if d is not None else 'no date in infobox'}  {t}")


if __name__ == "__main__":
    main()
