"""Checks on the primary polling averages (PP-10; PRIMARIES.md section 1, reading R15).

1. Truncation: an average rebuilt from the raw poll rows with every row that ended after its date deleted, put
   through the question ladder and merging again, is the same number (thinning, k, n and the window worked out as of
   the date). A sanity case confirms the comparison can fail.
2. Hand-worked cases: the weights (rule 7), the thinning chain (rule 6), the question ladder (rule 2), the switch to a
   7-day half-life and 42-day window (rules 8-9), a line's last day (rule 10, R8).

Exits non-zero on any failure.
"""
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/model"))
import primary_avg as pa  # noqa: E402

FAIL = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        FAIL.append(what)


def fixture_polls(rows):
    d = pd.DataFrame(rows, columns=["poll", "pollster", "pop", "n", "start", "end", "candidate_key", "pct"])
    d["geo"], d["cycle"], d["party"] = "US", 2016, "R"
    d["candidate_name"] = d["candidate_key"]
    d["start"], d["end"] = pd.to_datetime(d["start"]), pd.to_datetime(d["end"])
    return d


def weights_case():
    """Three polls on 1 Dec 2015 (before Iowa, half-life 30). Pollster A has two (k=2), B one."""
    D = pd.Timestamp("2015-12-01")
    rows = [(1, "A", "lv", 600, "2015-10-29", "2015-10-31", "donald-trump", 30),
            (1, "A", "lv", 600, "2015-10-29", "2015-10-31", "ted-cruz", 10),
            (2, "A", "rv", 2400, "2015-11-29", "2015-12-01", "donald-trump", 40),
            (2, "A", "rv", 2400, "2015-11-29", "2015-12-01", "ted-cruz", 20),
            (3, "B", "a", None, "2015-11-20", "2015-11-21", "donald-trump", 20)]
    w1 = 0.5 ** (31 / 30) * 1 * 1.0 / np.sqrt(2)
    w2 = 1 * 2 * pa.POP_W["rv"] / np.sqrt(2)
    w3 = 0.5 ** (10 / 30) * 1 * pa.POP_W["a"] / 1
    want_trump = (30 * w1 + 40 * w2 + 20 * w3) / (w1 + w2 + w3)
    want_cruz = (10 * w1 + 20 * w2) / (w1 + w2)                 # R5: B's poll does not name Cruz
    a = pa.average(2016, "R", "US", D, poll_rows=fixture_polls(rows)).set_index("candidate_key")
    check(abs(a.loc["donald-trump", "avg"] - want_trump) < 1e-9, f"weights: Trump {a.loc['donald-trump', 'avg']:.4f} "
          f"= {want_trump:.4f}")
    check(abs(a.loc["ted-cruz", "avg"] - want_cruz) < 1e-9, f"weights: Cruz over the polls naming him = {want_cruz:.4f}")
    check(a.loc["ted-cruz", "n_polls"] == 2 and a.loc["donald-trump", "n_pollsters"] == 2, "weights: counts")
    # band (R7): Trump's readings 20 (w3), 30 (w1), 40 (w2), weights in that order
    w = np.array([w3, w1, w2]) / (w1 + w2 + w3)
    lo = [20, 30, 40][int(np.searchsorted(np.cumsum(w), 0.10 - 1e-12))]
    hi = [20, 30, 40][int(np.searchsorted(np.cumsum(w), 0.90 - 1e-12))]
    check((a.loc["donald-trump", "band_lo"], a.loc["donald-trump", "band_hi"]) == (lo, hi), f"band: {lo} to {hi}")


def thinning_case():
    """A daily tracker with three-day fields, days 1-3, 2-4, ..., 5-7: as of day 7 the 5-7 and 2-4 releases stay."""
    day = lambda i: pd.Timestamp("2015-12-01") + pd.Timedelta(days=i)  # noqa: E731
    t = pd.DataFrame([dict(poll=i, geo="US", pollster="T", start=day(i), end=day(i + 2)) for i in range(1, 6)])
    kept = sorted(pa.thin(t)["poll"])
    check(kept == [2, 5], f"thinning: kept releases {kept} (want [2, 5])")
    kept6 = sorted(pa.thin(t[t["end"] <= day(6)])["poll"])
    check(kept6 == [1, 4], f"thinning as of day 6: kept {kept6} (want [1, 4])")


def ladder_case():
    p = pa.polls(2012, "R")
    q = lambda pid: set(p.loc[p["poll_id"].eq(pid), "question_id"])  # noqa: E731
    # FOX, May 2009: three versions (all registered voters, Republicans, independents); independents are out (rule 5),
    # the other two tie on every step to the last, so the first listed stays
    check(q("fox-5241") == {"hp-12-US-R-354"}, f"ladder: FOX May 2009 -> {q('fox-5241')}")
    # CNN, May 2011: with Giuliani or with Cain; Cain had declared (21 May), Giuliani had not -> the Cain version
    check(q("cnn-11392") == {"hp-12-US-R-291"}, f"ladder: CNN May 2011 -> {q('cnn-11392')}")
    # Fairleigh Dickinson, June 2011: one question entered twice -> one poll (R3)
    check(p.loc[p["poll_id"].eq("fairleigh-dickinson-11461"), "poll"].nunique() == 1, "ladder: FDU entered twice is one poll")


def dates_case():
    a = pa.average(2016, "R", "US", "2016-01-31")
    b = pa.average(2016, "R", "US", "2016-02-01")
    check(a["half_life"].iat[0] == 30 and b["half_life"].iat[0] == 7, "half-life 30 the day before Iowa, 7 on the day")
    us = pa.polls(2016, "R")
    us = pa.thin(us[us["geo"].eq("US") & us["end"].between(pd.Timestamp("2016-02-01") - pd.Timedelta(days=42),
                                                           pd.Timestamp("2016-02-01"))].drop_duplicates("poll"))
    check(b["polls_in_place"].iat[0] == len(us), f"window from Iowa: 42 days, {len(us)} polls")
    bush_on = pa.average(2016, "R", "US", "2016-02-20")
    bush_off = pa.average(2016, "R", "US", "2016-02-21")
    check("jeb-bush" in set(bush_on["candidate_key"]) and "jeb-bush" not in set(bush_off["candidate_key"]),
          "Bush's line ends on his withdrawal date, 20 February 2016 (inclusive)")
    ia = pa.average(2016, "R", "IA", "2016-02-01")
    check(len(ia) > 0 and pa.average(2016, "R", "IA", "2016-02-02").empty, "Iowa's average stops on its voting day")


def truncation_case(n=60, seed=20261125):
    rng = random.Random(seed)
    bad = 0
    for _ in range(n):
        cycle, party = rng.choice(pa.CYCLES)
        p = pa.polls(cycle, party)
        place = rng.choice(["US", "US"] + sorted(set(p["geo"]) - {"US"}))
        pp = p[p["geo"].eq(place)]
        if pp.empty:
            continue
        lo, hi = pp["end"].min(), min(pp["end"].max() + pd.Timedelta(days=20), pa.last_vote(cycle, party))
        if hi <= lo:
            continue
        d = lo + pd.Timedelta(days=rng.randrange((hi - lo).days + 1))
        full = pa.average(cycle, party, place, d)
        raw = pa._rows()
        cut = pa.average(cycle, party, place, d, poll_rows=pa.select_questions(raw[raw["end"] <= d], cycle, party))
        same = (full.empty and cut.empty) or (len(full) == len(cut) and np.allclose(full["avg"], cut["avg"]) and
                                              (full["shown"].values == cut["shown"].values).all())
        if not same:
            bad += 1
            print(f"     differs: {cycle} {party} {place} {d:%Y-%m-%d}")
    check(bad == 0, f"truncation: {n} random averages unchanged with later polls deleted")
    # sanity: the same comparison does fail when polls the average should see are removed
    raw, d = pa._rows(), pd.Timestamp("2016-01-15")
    short = pa.average(2016, "R", "US", d, poll_rows=pa.select_questions(raw[raw["end"] <= d - pd.Timedelta(days=7)],
                                                                         2016, "R"))
    full = pa.average(2016, "R", "US", d)
    check(len(full) != len(short) or not np.allclose(full["avg"], short["avg"]),
          "truncation sanity: deleting the last week's polls does change the 15 January 2016 national average")


def data_notes():
    d = pa._rows()
    swapped = d[pd.to_datetime(d["start_date"]) > pd.to_datetime(d["end_date"])].drop_duplicates("poll_id")
    print(f"note {len(swapped)} polls with start after end, dates taken in order: "
          + ", ".join(f"{r.cycle} {r.party} {r.geo} {r.pollster}" for r in swapped.itertuples()))


if __name__ == "__main__":
    weights_case()
    thinning_case()
    ladder_case()
    dates_case()
    truncation_case()
    data_notes()
    print(f"\n{len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
