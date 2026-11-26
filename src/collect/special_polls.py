"""Polls of past specials (SP-4, SPECIALS.md section 2, rules 1-4) -> data/interim/special_polls.csv

  python src/collect/special_polls.py fetch     cache each 2023-2026 House special's Wikipedia page (with revision id)
  python src/collect/special_polls.py collect   build the poll table and print the coverage table

Sources (rule 1): FiveThirtyEight's pollster-ratings file (data/raw/538_github/2026-11-01/raw_polls.csv) for House
specials through 2022 and every Senate special and runoff; each 2023-2026 House special's Wikipedia page
(data/raw/wikipedia_hist/<date>/sp4_<race>.json, the parse API's answer with its revision id). The result columns of
FiveThirtyEight's file are dropped on reading: no poll is compared with a result here.
"""
import json
import re
import sys
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import ROOT, RAW, SESSION, raw_dir  # noqa: E402

INTERIM = ROOT / "data" / "interim"
RAW538 = RAW / "538_github" / "2026-11-01" / "raw_polls.csv"
WINDOW, FALLBACK = 21, 60
ORD = {1: "1st", 2: "2nd", 3: "3rd"}
STATES = {"VA": "Virginia", "RI": "Rhode Island", "UT": "Utah", "NY": "New York", "OH": "Ohio", "CO": "Colorado",
          "NJ": "New Jersey", "FL": "Florida", "AZ": "Arizona", "TN": "Tennessee", "GA": "Georgia", "CA": "California"}


def ordinal(n):
    return ORD.get(n if n < 20 else n % 10, f"{n}th") if n not in (11, 12, 13) else f"{n}th"


def recent_specials():
    h = pd.read_csv(INTERIM / "house_specials.csv", parse_dates=["date"])
    return h[h.date >= "2023-01-01"].drop(columns=["margin_2p", "margin_raw", "d_pct", "r_pct", "winner", "winner_party",
                                                    "winner_pct", "d_total", "r_total"], errors="ignore")


def title(r):
    return f"{r.date.year} {STATES[r.state]}'s {ordinal(int(r.district))} congressional district special election"


def fetch():
    d = raw_dir("wikipedia_hist")
    for _, r in recent_specials().iterrows():
        race = f"{r.state}-{int(r.district)}-{r.date.date()}"
        out = d / f"sp4_{race}.json"
        if out.exists():
            continue
        resp = SESSION.get("https://en.wikipedia.org/w/api.php", params={
            "action": "parse", "page": title(r), "redirects": 1, "prop": "text|revid", "format": "json", "formatversion": 2},
            timeout=60)
        j = resp.json()
        if "error" in j:
            print(race, "MISSING:", title(r), j["error"].get("info"))
            continue
        out.write_text(json.dumps({"title": j["parse"]["title"], "revid": j["parse"]["revid"], "html": j["parse"]["text"]}))
        print(race, j["parse"]["title"], j["parse"]["revid"])


# Wikipedia polls of the deciding round (Democrat against Republican) for the 2023-2026 House specials, read by hand
# from the cached pages (revision ids in data/raw/wikipedia_hist/*/sp4_<race>.json). Partisan from the footnote
# linked to each row (rule 3). Where a page gives a second version of the same question with leaners pushed, the
# first (as asked) is kept. Pages for VA-4 2023, NY-26, OH-6, CO-4, NJ-10 2024, FL-1, VA-11, AZ-7 2025, GA-14 and CA-1
# 2026 have no such poll.
# (race, pollster, field end, population, D, R, partisan, footnote)
WIKI = [
    ("FL-6-2025-04-01", "Fabrizio Ward", "2025-03-28", "", 44, 41, "REP", "a GOP poll"),
    ("FL-6-2025-04-01", "St. Pete Polls", "2025-03-25", "lv", 44, 48, "", "sponsored by Florida Politics"),
    ("NJ-11-2026-04-16", "GBAO", "2026-03-10", "lv", 53, 36, "DEM", "sponsored by Mejia's campaign"),
    ("NY-3-2024-02-13", "JL Partners", "2024-02-12", "lv", 46, 45, "", "sponsored by the New York Post"),
    ("NY-3-2024-02-13", "Siena College", "2024-02-06", "lv", 48, 44, "", "sponsored by Newsday"),
    ("NY-3-2024-02-13", "Emerson College", "2024-02-05", "lv", 50, 47, "", "sponsored by Nexstar Media Group"),
    ("NY-3-2024-02-13", "Emerson College", "2024-01-15", "rv", 45, 42, "", "sponsored by Nexstar Media Group"),
    ("NY-3-2024-02-13", "Opinion Diagnostics", "2023-11-30", "lv", 43, 40, "REP", "sponsored by Curry's campaign"),
    ("RI-1-2023-11-07", "Salve Regina University/Embold Research", "2023-10-17", "rv", 46, 35, "", ""),
    ("TN-7-2025-12-02", "Emerson College", "2025-11-24", "lv", 46, 48, "", "sponsored by Nexstar Media Group"),
    ("TN-7-2025-12-02", "Impact Research", "2025-10-19", "lv", 44, 52, "DEM", "sponsored by Your Community PAC"),
    ("TN-7-2025-12-02", "Workbench Strategy", "2025-10-19", "lv", 41, 51, "DEM", "sponsored by Behn's campaign"),
    ("UT-2-2023-11-21", "Lighthouse Research", "2023-10-06", "rv", 34, 43, "", ""),
]


def surname(name):
    toks = [t for t in re.sub(r"[.,]", " ", str(name)).lower().split() if t not in ("jr", "sr", "ii", "iii")]
    return toks[-1] if toks else ""


def races():
    """Every race the test scores: House specials and Senate specials and runoffs, with the deciding round's pair."""
    h = pd.read_csv(INTERIM / "house_specials.csv", parse_dates=["date"])
    h = pd.DataFrame({"race": h.state + "-" + h.district.astype(int).astype(str) + "-" + h.date.dt.date.astype(str),
                      "office": "H", "set": "special", "state": h.state, "district": h.district.astype(int),
                      "date": h.date, "dem": h.dem_cand, "rep": h.rep_cand})
    s = pd.read_csv(INTERIM / "senate_specials.csv", parse_dates=["date"])
    s = pd.DataFrame({"race": s.race, "office": "S", "set": s["set"], "state": s.state, "district": 0, "date": s.date,
                      "dem": s.dem, "rep": s.rep})
    return pd.concat([h, s], ignore_index=True)


def from_538(rc):
    r = pd.read_csv(RAW538, low_memory=False)
    r = r.drop(columns=[c for c in r.columns if "actual" in c])            # no results read here
    r = r[r.type_simple.isin(["House-G", "Sen-G"])].copy()
    r["ed"] = pd.to_datetime(r.electiondate, format="mixed")
    r["end"] = pd.to_datetime(r.polldate, format="mixed")
    rows, dropped = [], []
    for _, x in rc.iterrows():
        if x.office == "H":
            loc = f"{x.state}-{x.district if x.district else 1}"
            k = r[(r.type_simple == "House-G") & (r.location == loc) & (r.ed == x.date)]
        else:
            k = r[(r.type_simple == "Sen-G") & (r.location == x.state) & (r.ed == x.date)]
        dn, rn = surname(x.dem), surname(x.rep)
        for pid, g in k.groupby("poll_id"):
            ok = []
            for _, q in g.sort_values("question_id").iterrows():
                names = {q.cand1_party: q.cand1_name, q.cand2_party: q.cand2_name}
                pct = {q.cand1_party: q.cand1_pct, q.cand2_party: q.cand2_pct}
                if surname(names.get("DEM")) == dn and surname(names.get("REP")) == rn:
                    ok.append((q, pct["DEM"], pct["REP"]))
            if not ok:
                dropped.append((x.race, int(pid), f"{g.cand1_name.iloc[0]} v {g.cand2_name.iloc[0]}"))
                continue
            q, d, rr = ok[0]                                                  # lowest question_id of the pair
            part = str(q.partisan).upper() if pd.notna(q.partisan) else ""
            rows.append({"race": x.race, "source": "538", "poll_id": str(int(pid)), "pollster": q.pollster,
                         "end": q.end, "population": "", "d": float(d), "r": float(rr),
                         "partisan": part if part in ("DEM", "REP") else ("OTHER" if part else ""),
                         "note": f"question {int(q.question_id)}" + (f"; {len(ok)} questions of the pair" if len(ok) > 1 else "")})
    return pd.DataFrame(rows), dropped


def from_wiki():
    return pd.DataFrame([{"race": a, "source": "wikipedia", "poll_id": f"wiki-{i}", "pollster": b, "end": pd.Timestamp(c),
                          "population": p, "d": float(d), "r": float(r), "partisan": s, "note": n}
                         for i, (a, b, c, p, d, r, s, n) in enumerate(WIKI)])


def collect():
    rc = races()
    a, dropped = from_538(rc)
    p = pd.concat([a, from_wiki()], ignore_index=True)
    p = p.merge(rc[["race", "office", "set", "date"]], on="race")
    p["days"] = (p.date - p.end).dt.days
    p = p[p.days > 0].copy()                                                  # field ended before election day
    p["margin"] = 100 * (p.d - p.r) / (p.d + p.r)
    win = {}
    for race, g in p.groupby("race"):
        win[race] = WINDOW if (g.days <= WINDOW).any() else FALLBACK
    p["window"] = p.race.map(win)
    p["in_window"] = p.days <= p.window
    p = p.sort_values(["date", "race", "end"])
    cols = ["race", "office", "set", "date", "source", "poll_id", "pollster", "end", "days", "population", "d", "r",
            "margin", "partisan", "window", "in_window", "note"]
    p[cols].to_csv(INTERIM / "special_polls.csv", index=False, date_format="%Y-%m-%d")
    w = p[p.in_window]
    cov = w.groupby(["office", "set", "race"]).agg(polls=("margin", "size"), partisan=("partisan", lambda s: (s != "").sum()),
                                                   window=("window", "first"), source=("source", "first")).reset_index()
    print(cov.to_string(index=False))
    print(f"\npolls in window: {len(w)} in {w.race.nunique()} races; outside the window: {(~p.in_window).sum()}; "
          f"dropped for another pairing: {len(dropped)}")
    for d in dropped:
        print("  dropped", d)
    return p


if __name__ == "__main__":
    {"fetch": fetch, "collect": collect}[sys.argv[1]]()
