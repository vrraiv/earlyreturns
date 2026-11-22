"""State demographics by year from the Census Bureau's Data API (work plan card DA-11, for EC-5).

This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.

For the 50 states and DC: the share of adults 25 and over with a bachelor's degree, the same among white non-Hispanic
adults, white non-Hispanic adults without a degree as a share of all adults 25 and over, race and ethnicity as shares
of the total population, two age shares of adults, and median household income.

  year        source                                                         what it is
  2000        2000 census long form (2000/dec/sf3)                           published tables; income is for 1999
  2004        2004 American Community Survey microdata (2004/acs/acs1/pums)  our own tabulation, not a Census estimate
  2005-2019,  American Community Survey one-year tables (<year>/acs/acs1)    published tables
  2021 on
  2020        none: the Bureau published no standard one-year tables for 2020

Also fetched, for checks only: the 2005 microdata (tabulated the same way as 2004 and compared with the published
2005 tables) and the 2015-19 five-year tables (compared with The Downballot's state tables, which use them).

What a reader should know:
- The survey left out people in group quarters (dormitories, prisons, barracks, nursing homes) before 2006. The 2000
  census and the survey from 2006 include them.
- 2004 was a smaller, trial-stage sample (the survey reached full size in 2005), so its figures are noisier. One state
  is clearly off: South Dakota's white share is about 6 points above 2000 and 2005. No other state is more than 2
  points from a line between those two years on white share or on white adults without a degree.
- From the 2020 survey year the race question and its coding changed, so race shares from 2021 on are not like for
  like with 2019 and earlier.
- The API's household income field in the 2004 and 2005 microdata is unusable (every value is capped at 127), so a
  household's income is rebuilt here as the sum of its members' incomes, times the file's adjustment factor.
- The microdata is never written to disk. Only three sets of state totals are kept: by broad age group, by race and
  ethnicity, and by degree for white non-Hispanic and all other adults 25 and over.
- The key (census_bureau_api_key in .env) is sent only to api.census.gov and is never written to a file or printed.

Which year an election uses (decided 2026-11-21): the year before the election, the latest published before its
7-day forecast. The election's own year is kept beside it for a comparison that decides nothing. 2000, 2004 and 2020
take the same year in both, because the API has no survey for 1999, 2003 or 2020. See VINTAGES below, written to
data/interim/state_demographics_vintages.csv.

Run:  python src/collect/census_demographics.py [fetch|build|check|all]
      fetch skips any file already held under data/raw/census/, whatever its date; `refetch` pulls everything again.
"""
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, ROOT, SESSION, TODAY, env_key, latest, latest_linked  # noqa: E402

API = "https://api.census.gov/data"
SOURCE = "census"
INTERIM = ROOT / "data" / "interim"
CHECKS = ROOT / "data" / "checks"

ACS1_YEARS = [y for y in range(2005, 2026) if y != 2020]
# role -> table. The survey's tables keep these ids in every year from 2005.
ACS_TABLES = {"education": "B15002", "education_white": "B15002H", "race": "B03002", "age": "B01001", "income": "B19013"}
# the five-year tables carry the white non-Hispanic education table only in its collapsed form
ACS5_TABLES = {**ACS_TABLES, "education_white": "C15002H"}
SF3_TABLES = {"education": "P037", "education_white": "P148I", "race": "P007", "age": "P008", "income": "P053"}
PUMS_YEARS = [2004, 2005]
PUMS_VARS = "PWGTP,WGTP,AGEP,SCHL,RAC1P,HISP,PINCP,ADJUST,REL,SERIALNO"

# election -> (the year before, the election's own year). Same year twice where the API has nothing else.
VINTAGES = [
    (2000, 2000, 2000, "2000 census in both: no survey for 1999"),
    (2004, 2004, 2004, "2004 microdata in both: no survey for 2003"),
    (2008, 2007, 2008, ""),
    (2012, 2011, 2012, ""),
    (2016, 2015, 2016, ""),
    (2020, 2019, 2019, "2019 in both: no standard one-year tables for 2020"),
    (2024, 2023, 2024, "enters no electoral college test before the design freeze (EC-9)"),
]

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC",
        "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
        "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT",
        "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
        "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
        "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}
MEASURES = ["degree_share", "white_degree_share", "white_no_degree_share", "white_share", "black_share",
            "latino_share", "asian_share", "age_18_29_share", "age_65_plus_share", "median_household_income"]
DEGREE = re.compile(r"^(Bachelor's degree|Master's degree|Professional school degree|Doctorate degree|"
                    r"Graduate degree|Graduate or professional degree|Bachelor's degree or higher)$")


# ---------------------------------------------------------------- fetching

def held(name: str):
    c = sorted((RAW / SOURCE).glob(f"*/{name}"))
    return c[-1] if c else None


def _save(name: str, content: bytes, url: str, note=None):
    d = RAW / SOURCE / TODAY
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(content)
    mf = d / "manifest.json"
    m = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
    m[name] = {"url": url, "retrieved": dt.datetime.now().isoformat(timespec="seconds"), "bytes": len(content),
               "sha256": hashlib.sha256(content).hexdigest(), **({"note": note} if note else {})}
    mf.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")


def call(path: str, query: str = "", key=None):
    """One API call, returned as parsed JSON. The key goes on the request only; errors are raised without it."""
    url = f"{API}/{path}" + (f"?{query}" if query else "")
    last = "no attempt"
    for i in range(4):
        try:
            r = SESSION.get(url + (f"&key={key}" if key else ""), timeout=600)
        except Exception as e:  # noqa: BLE001  (the exception text carries the full URL, so it is not repeated)
            last = type(e).__name__
            time.sleep(3 * (i + 1))
            continue
        if r.status_code == 200:
            try:
                return r.json(), url
            except ValueError:
                # a missing or rejected key is redirected to an HTML page
                raise RuntimeError(f"not JSON from {url}: is census_bureau_api_key set and valid?") from None
        last = f"HTTP {r.status_code}: {r.text[:200]}"
        if key:
            last = last.replace(key, "KEY")
        if r.status_code in (400, 404):
            break
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"failed {url}: {last}")


def cells(labels: dict, table: str):
    """Estimate cells of a table: {variable: label segments}, e.g. ['Total', 'Male', "Bachelor's degree"]."""
    pat = re.compile(rf"^{table}(_\d{{3}}E|\d{{3}})$")
    out = {}
    for k, v in labels.items():
        if pat.match(k):
            out[k] = [s.strip().rstrip(":") for s in v["label"].replace("Estimate!!", "").split("!!")]
    return dict(sorted(out.items()))


def fetch_table(dataset: str, table: str, tag: str, key: str, refetch=False):
    """Labels (no key needed) and the state rows of one table, estimates only, at most 49 cells a call."""
    lname = f"{tag}_{table}_labels.json"
    if refetch or not held(lname):
        js, url = call(f"{dataset}/groups/{table}.json")
        slim = {k: {"label": v["label"]} for k, v in js["variables"].items() if "label" in v}
        _save(lname, (json.dumps(slim, indent=1, sort_keys=True) + "\n").encode("utf-8"), url)
    names = list(cells(json.loads(held(lname).read_text(encoding="utf-8")), table))
    if not names:
        raise RuntimeError(f"no estimate cells found for {dataset} {table}")
    for i in range(0, len(names), 49):
        dname = f"{tag}_{table}_p{i // 49 + 1}.json"
        if refetch or not held(dname):
            js, url = call(dataset, "get=NAME," + ",".join(names[i:i + 49]) + "&for=state:*", key)
            _save(dname, (json.dumps(js) + "\n").encode("utf-8"), url)
    print("held", tag, table, len(names), "cells")


def weighted_median(v, w):
    o = np.argsort(np.asarray(v, dtype=float), kind="stable")
    v, c = np.asarray(v, dtype=float)[o], np.cumsum(np.asarray(w, dtype=float)[o])
    return float(v[np.searchsorted(c, c[-1] / 2)])


def fetch_pums(year: int, key: str, refetch=False):
    """Tabulate one year's microdata by state. The person rows are held in memory only."""
    cname, iname = f"pums_{year}_cells.csv", f"pums_{year}_income.csv"
    if not refetch and held(cname) and held(iname):
        print("held pums", year)
        return
    tab, inc = [], []
    base = f"{API}/{year}/acs/acs1/pums?get={PUMS_VARS}&for=state:"
    for fips in FIPS:
        js, _ = call(f"{year}/acs/acs1/pums", f"get={PUMS_VARS}&for=state:{fips}", key)
        d = pd.DataFrame(js[1:], columns=js[0]).drop(columns="state").astype(float)
        age = pd.cut(d.AGEP, [-1, 17, 29, 64, 200], labels=["0-17", "18-29", "30-64", "65+"]).astype(str)
        nh = d.HISP == 1
        race = np.select([~nh, d.RAC1P == 1, d.RAC1P == 2, d.RAC1P == 6], ["latino", "white_nh", "black_nh", "asian_nh"],
                         "other_nh")
        edu = (np.where(race == "white_nh", "white_nh", "everyone_else") + np.where(d.SCHL >= 13, "_degree", "_no_degree"))
        # three separate margins, not their cross, so that no kept cell rests on a handful of records
        for table, grp, rows in (("age", age, d), ("race", race, d), ("education_25_plus", edu[d.AGEP >= 25], d[d.AGEP >= 25])):
            g = rows.groupby(np.asarray(grp)).PWGTP.agg(["sum", "size"]).reset_index()
            g.columns = ["group", "persons_weighted", "records"]
            g.insert(0, "table", table)
            g.insert(0, "state_fips", fips)
            tab.append(g)
        # household income: the members' incomes summed (PINCP is -19999 for children under 15), on the reference
        # person's row, which carries the household weight. The API's own household income field is unusable.
        summed = d[d.PINCP > -19999].groupby("SERIALNO").PINCP.sum()
        h = d[d.REL == 0].set_index("SERIALNO")
        assert h.index.is_unique, (year, fips)
        hinc = summed.reindex(h.index).fillna(0) * h.ADJUST / 1e6
        inc.append({"state_fips": fips, "households": len(h), "person_records": len(d),
                    "median_household_income": round(weighted_median(hinc, h.WGTP))})
        print("pums", year, FIPS[fips], len(d), "records", flush=True)
    note = ("our own tabulation of the microdata returned by this query for each state; the microdata is not kept. "
            "Not a Census Bureau estimate")
    _save(cname, pd.concat(tab).to_csv(index=False, lineterminator="\n").encode("utf-8"), base + "<state>", note)
    _save(iname, pd.DataFrame(inc).to_csv(index=False, lineterminator="\n").encode("utf-8"), base + "<state>", note)


def fetch(refetch=False):
    key = env_key("census_bureau_api_key")
    if not key:
        raise SystemExit("set census_bureau_api_key in .env (free, from api.census.gov/data/key_signup.html)")
    for t in SF3_TABLES.values():
        fetch_table("2000/dec/sf3", t, "sf3_2000", key, refetch)
    for y in ACS1_YEARS:
        for t in ACS_TABLES.values():
            fetch_table(f"{y}/acs/acs1", t, f"acs1_{y}", key, refetch)
    for t in ACS5_TABLES.values():
        fetch_table("2019/acs/acs5", t, "acs5_2019", key, refetch)
    for y in PUMS_YEARS:
        fetch_pums(y, key, refetch)


# ---------------------------------------------------------------- building

def read_table(tag: str, table: str):
    """State rows of a table (index: two-digit state code, 51 rows) and its cells' label segments."""
    seg = cells(json.loads(latest(SOURCE, f"{tag}_{table}_labels.json").read_text(encoding="utf-8")), table)
    parts = []
    for p in sorted((RAW / SOURCE).glob(f"*/{tag}_{table}_p*.json")):
        if p.parent == latest(SOURCE, p.name).parent:
            js = json.loads(p.read_text(encoding="utf-8"))
            parts.append(pd.DataFrame(js[1:], columns=js[0]).set_index("state").drop(columns="NAME"))
    d = pd.concat(parts, axis=1)
    d = d[d.index.isin(FIPS)].astype(float).sort_index()
    assert len(d) == 51 and set(d.columns) == set(seg), (tag, table, len(d))
    return d, seg


def lower_age(band: str) -> int:
    return 0 if band.startswith("Under") else int(re.search(r"\d+", band).group())


def from_tables(tag: str, tables: dict) -> pd.DataFrame:
    out = {}
    # education, adults 25 and over
    e, s = read_table(tag, tables["education"])
    tot = [k for k, v in s.items() if v == ["Total"]]
    ba = [k for k, v in s.items() if DEGREE.match(v[-1])]
    assert len(tot) == 1 and len(ba) == 8, (tag, "education", len(ba))
    adults25 = e[tot[0]]
    out["adults_25_plus"] = adults25
    out["degree_share"] = 100 * e[ba].sum(axis=1) / adults25
    w, s = read_table(tag, tables["education_white"])
    tot = [k for k, v in s.items() if v == ["Total"]]
    ba = [k for k, v in s.items() if DEGREE.match(v[-1])]
    assert len(tot) == 1 and len(ba) in (2, 4), (tag, "education_white", len(ba))
    out["white_degree_share"] = 100 * w[ba].sum(axis=1) / w[tot[0]]
    out["white_no_degree_share"] = 100 * (w[tot[0]] - w[ba].sum(axis=1)) / adults25
    # race and ethnicity, total population
    r, s = read_table(tag, tables["race"])
    pick = {"population": ["Total"], "white_share": ["Total", "Not Hispanic or Latino", "White alone"],
            "black_share": ["Total", "Not Hispanic or Latino", "Black or African American alone"],
            "asian_share": ["Total", "Not Hispanic or Latino", "Asian alone"], "latino_share": ["Total", "Hispanic or Latino"]}
    for name, want in pick.items():
        k = [c for c, v in s.items() if v == want]
        assert len(k) == 1, (tag, "race", name)
        out[name] = r[k[0]] if name == "population" else 100 * r[k[0]] / out["population"]
    # age, as shares of adults 18 and over
    a, s = read_table(tag, tables["age"])
    leaf = {k: lower_age(v[2]) for k, v in s.items() if len(v) == 3}
    tot = [k for k, v in s.items() if v == ["Total"]][0]
    assert (a[list(leaf)].sum(axis=1) - a[tot]).abs().max() < 1, (tag, "age")
    adults = a[[k for k, lo in leaf.items() if lo >= 18]].sum(axis=1)
    out["age_18_29_share"] = 100 * a[[k for k, lo in leaf.items() if 18 <= lo < 30]].sum(axis=1) / adults
    out["age_65_plus_share"] = 100 * a[[k for k, lo in leaf.items() if lo >= 65]].sum(axis=1) / adults
    # median household income, in the dollars of the survey year (the 2000 census asks about 1999)
    i, s = read_table(tag, tables["income"])
    assert i.shape[1] == 1, (tag, "income")
    out["median_household_income"] = i.iloc[:, 0]
    return pd.DataFrame(out)


def from_pums(year: int) -> pd.DataFrame:
    c = pd.read_csv(latest(SOURCE, f"pums_{year}_cells.csv"), dtype={"state_fips": str})
    assert c.state_fips.nunique() == 51, year
    t = c.pivot_table(index="state_fips", columns=["table", "group"], values="persons_weighted", aggfunc="sum").fillna(0)
    age, race, edu = t["age"], t["race"], t["education_25_plus"]
    pop, a25, a18 = race.sum(axis=1), edu.sum(axis=1), age.drop(columns="0-17").sum(axis=1)
    assert (age.sum(axis=1) - pop).abs().max() < 1, year
    out = pd.DataFrame({
        "population": pop, "adults_25_plus": a25,
        "degree_share": 100 * (edu.white_nh_degree + edu.everyone_else_degree) / a25,
        "white_degree_share": 100 * edu.white_nh_degree / (edu.white_nh_degree + edu.white_nh_no_degree),
        "white_no_degree_share": 100 * edu.white_nh_no_degree / a25,
        "white_share": 100 * race.white_nh / pop, "black_share": 100 * race.black_nh / pop,
        "asian_share": 100 * race.asian_nh / pop, "latino_share": 100 * race.latino / pop,
        "age_18_29_share": 100 * age["18-29"] / a18, "age_65_plus_share": 100 * age["65+"] / a18})
    i = pd.read_csv(latest(SOURCE, f"pums_{year}_income.csv"), dtype={"state_fips": str}).set_index("state_fips")
    out["median_household_income"] = i.median_household_income
    return out


def tidy(d: pd.DataFrame, year: int, source: str) -> pd.DataFrame:
    d = d.copy()
    d.insert(0, "state", d.index.map(FIPS))
    d.index.name = None
    d.insert(0, "year", year)
    d.insert(2, "source", source)
    for c in MEASURES[:-1]:
        d[c] = d[c].round(2)
    for c in ("population", "adults_25_plus", "median_household_income"):
        d[c] = d[c].round().astype(int)
    return d[["year", "state", "source", "population", "adults_25_plus"] + MEASURES].sort_values("state")


def build() -> pd.DataFrame:
    rows = [tidy(from_tables("sf3_2000", SF3_TABLES), 2000, "census_2000_long_form"),
            tidy(from_pums(2004), 2004, "survey_microdata_own_tabulation")]
    rows += [tidy(from_tables(f"acs1_{y}", ACS_TABLES), y, "survey_one_year") for y in ACS1_YEARS]
    df = pd.concat(rows, ignore_index=True)
    assert (df.groupby("year").state.nunique() == 51).all() and not df[MEASURES].isna().any().any()
    df.to_csv(INTERIM / "state_demographics.csv", index=False, lineterminator="\n")
    v = pd.DataFrame(VINTAGES, columns=["election", "year_before", "own_year", "note"])
    assert set(v.year_before).union(v.own_year) <= set(df.year)
    v.to_csv(INTERIM / "state_demographics_vintages.csv", index=False, lineterminator="\n")
    print(f"state_demographics.csv: {len(df)} rows, {df.year.nunique()} years ({df.year.min()}-{df.year.max()})")
    return df


# ---------------------------------------------------------------- checks

def gaps(a: pd.DataFrame, b: pd.DataFrame, cols) -> dict:
    """a minus b by state. Income as a percentage of b, the rest in points."""
    out = {}
    for c in cols:
        d = (100 * (a[c] - b[c]) / b[c]) if c == "median_household_income" else (a[c] - b[c])
        out[c] = {"mean": round(float(d.mean()), 2), "mean_abs": round(float(d.abs().mean()), 2),
                  "max_abs": round(float(d.abs().max()), 2), "worst": str(d.abs().idxmax()),
                  "corr": round(float(np.corrcoef(a[c], b[c])[0, 1]), 4)}
    return out


def downballot_snapshot() -> pd.DataFrame:
    """The Downballot's 2015-19 state tables, from the gitignored store. Only summary differences leave this file."""
    from downballot import STATE_ABBR
    e = pd.read_excel(latest_linked("downballot", "education_income_cd.xlsx"), sheet_name="2019 - State").set_index("State")
    x = pd.ExcelFile(latest_linked("downballot", "race_age_citizenship_cd.xlsx"))
    rc = x.parse([n for n in x.sheet_names if n.startswith("Senate") and n.endswith("2019")][0], header=None).iloc[3:, :4].set_index(0)
    f = pd.DataFrame({"degree_share": e["Bachelor's"], "white_degree_share": e["White Bachelor's"],
                      "median_household_income": e["Median Income"], "white_share": rc[1], "black_share": rc[2],
                      "latino_share": rc[3]})
    f = f[f.index.isin(STATE_ABBR)].astype(float)
    f.index = f.index.map(STATE_ABBR)
    return f.sort_index()


def check(df=None):
    df = pd.read_csv(INTERIM / "state_demographics.csv") if df is None else df
    by = {y: g.set_index("state") for y, g in df.groupby("year")}
    rep = {"note": "Differences across the 51 states. Income as a percentage, everything else in points."}
    # 1. the tabulation method: 2005 microdata against the published 2005 tables
    m05 = tidy(from_pums(2005), 2005, "x").set_index("state")
    rep["microdata_2005_minus_published_2005"] = gaps(m05, by[2005], MEASURES)
    # 2. where 2004 sits: against a straight line from 2000 to 2005, and against 2005
    line = by[2000][MEASURES] + 0.8 * (by[2005][MEASURES] - by[2000][MEASURES])
    rep["microdata_2004_minus_line_2000_to_2005"] = gaps(by[2004], line, MEASURES)
    rep["microdata_2004_minus_published_2005"] = gaps(by[2004], by[2005], MEASURES)
    # 3. cell choices: our 2015-19 figures against The Downballot's tables built from the same survey
    try:
        snap = downballot_snapshot()
        five = tidy(from_tables("acs5_2019", ACS5_TABLES), 2019, "x").set_index("state").loc[snap.index]
        rep["five_year_2015_19_minus_downballot"] = {"states": len(snap), **gaps(five, snap, list(snap.columns))}
        rep["one_year_2019_minus_downballot"] = gaps(by[2019].loc[snap.index], snap, list(snap.columns))
    except FileNotFoundError as e:
        rep["five_year_2015_19_minus_downballot"] = f"skipped: {e}"
    # 4. how much the choice of year can matter: an election's own year against the year before
    rep["own_year_minus_year_before"] = {str(el): gaps(by[own], by[lag], MEASURES)
                                         for el, lag, own, _ in VINTAGES if own != lag}
    # 5. the race question's change: 2021 against 2019
    rep["2021_minus_2019"] = gaps(by[2021], by[2019], ["white_share", "black_share", "latino_share", "asian_share"])
    CHECKS.mkdir(exist_ok=True)
    (CHECKS / "state_demographics_check.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    for k, v in rep.items():
        if isinstance(v, dict) and k != "own_year_minus_year_before":
            print(k)
            for c, s in v.items():
                print("   ", c, s)
    for el, v in rep["own_year_minus_year_before"].items():
        print("own year minus year before,", el)
        for c, s in v.items():
            print("   ", c, s)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("fetch", "refetch", "all"):
        fetch(refetch=what == "refetch")
    if what in ("build", "all"):
        build()
    if what in ("check", "build", "all"):
        check()
