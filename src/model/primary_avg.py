"""Primary polling averages (PP-10), built as PRIMARIES.md section 1 sets them out (rules 1-15, readings R1-R15).

    polls(cycle, party)                       every usable question, after rules 1-5 (one question per poll)
    average(cycle, party, place, as_of)       one row per candidate line: the average as of a date, or empty
    national_series(cycle, party)             the national average for every day it exists
    last_averages(cycle, party)               each place's last average (on its voting day) beside its result

Nothing here reads a poll that ended after `as_of`: thinning, k, n and the window are all worked out as of the date
(rules 6 and 13), so any past average can be rebuilt, which PP-6 needs. Dates of contests come only from
primary_calendar.py (section 2, rule 1).
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

import primary_calendar as pc

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data/interim"
SUPP = ROOT / "data/supplement"

HALF_LIFE_BEFORE, HALF_LIFE_FROM = 30, 7     # rule 8
WINDOW_HALF_LIVES = 6                         # rule 9
RECENT_DAYS = 60                              # rules 11 and 12
N0, N_CAP = 600, 3000                         # rule 7
POP_W = dict(json.loads((ROOT / "data/processed/poll_settings.json").read_text())["chosen"]["pop_weight"])
POP_RANK = {"lv": 0, "rv": 1, "a": 2}         # rule 2, step 4
OPEN = {(2008, "D"), (2008, "R"), (2012, "R"), (2016, "D"), (2016, "R"), (2020, "D"), (2024, "R")}   # R11
CYCLES = ((2008, "D"), (2008, "R"), (2012, "R"), (2016, "D"), (2016, "R"), (2020, "D"), (2020, "R"),
          (2024, "D"), (2024, "R"))


# ---------------------------------------------------------------- polls (rules 1-5, readings R1-R4)

def _population(raw):
    """R4: lv, rv or a; None for independents only (rule 5). A missing population counts as likely voters (rule 7)."""
    if not isinstance(raw, str) or not raw.strip():
        return "lv"
    s = raw.strip().lower()
    if "independent" in s:
        return None
    if s in ("lv", "v") or s.startswith("likely"):
        return "lv"
    if s == "rv" or s.startswith("registered"):
        return "rv"
    if s == "a" or s.startswith("adults"):
        return "a"
    raise ValueError(f"unknown population {raw!r}")


@lru_cache(None)
def _names():
    m = pd.read_csv(SUPP / "primary_pollster_names.csv", dtype={"cycle": int}, keep_default_na=False)
    return {(c, r): p for c, r, p in zip(m["cycle"], m["raw_name"], m["pollster"])}


@lru_cache(None)
def _rows():
    """Both poll files in one frame, one row per question and candidate."""
    a = pd.read_csv(INTERIM / "primary_polls.csv", low_memory=False)
    a["file"] = np.where(a["source"].str.startswith("Wikipedia"), "wikipedia", "538")
    a["file_rule"] = np.nan
    h = pd.read_csv(INTERIM / "primary_polls_huffpost.csv", low_memory=False)
    h["file"], h["internal"] = "huffpost", False
    cols = ["cycle", "party", "geo", "poll_id", "question_id", "pollster", "population", "sample_size", "internal",
            "start_date", "end_date", "candidate_key", "candidate_name", "pct", "n_answers", "q_running",
            "q_exploratory", "q_withdrawn", "q_unknown", "file", "file_rule"]
    d = pd.concat([a[cols], h[cols]], ignore_index=True)
    d["row"] = np.arange(len(d))                              # file order, for rule 2's last step
    names = _names()
    raw = d["pollster"].astype(str)
    d["pollster"] = [names[(c, r)] for c, r in zip(d["cycle"], raw)]
    d["pop"] = d["population"].map(_population)
    d["n"] = pd.to_numeric(d["sample_size"].astype(str).str.replace(",", ""), errors="coerce")
    d["start"], d["end"] = pd.to_datetime(d["start_date"]), pd.to_datetime(d["end_date"])
    swap = d["start"] > d["end"]                              # 8 rows in the 2008 file; field dates taken in order
    d.loc[swap, ["start", "end"]] = d.loc[swap, ["end", "start"]].values
    d["internal"] = d["internal"].fillna(False).astype(bool)
    d["declared"] = d[["q_running", "q_exploratory", "q_unknown"]].sum(axis=1)
    return d


@lru_cache(None)
def polls(cycle, party):
    """One question per poll, one row per candidate. A poll is one pollster, place, party and pair of field dates (R1,
    R3); rule 2's ladder picks the question. Internal polls (rule 4) and independents-only samples (rule 5) are out."""
    return select_questions(_rows(), cycle, party)


def select_questions(d, cycle, party):
    """Rules 1-5 on raw rows (any subset of _rows(), such as the rows that ended by a date, for the checks)."""
    d = d[(d["cycle"] == cycle) & (d["party"] == party) & ~d["internal"] & d["pop"].notna()].copy()
    q = d.groupby("question_id").agg(geo=("geo", "first"), pollster=("pollster", "first"), start=("start", "first"),
                                     end=("end", "first"), declared=("declared", "first"),
                                     withdrawn=("q_withdrawn", "first"), named=("candidate_key", "nunique"),
                                     pop=("pop", "first"), row=("row", "min")).reset_index()
    q["pop_rank"] = q["pop"].map(POP_RANK)
    q = q.sort_values(["declared", "withdrawn", "named", "pop_rank", "row"], ascending=[False, True, False, True, True])
    q["poll"] = q.groupby(["geo", "pollster", "start", "end"]).ngroup()
    keep = q.drop_duplicates("poll", keep="first")
    out = d[d["question_id"].isin(keep["question_id"])].merge(keep[["question_id", "poll"]], on="question_id")
    out = out.drop_duplicates(["poll", "candidate_key"])
    return out[["cycle", "party", "geo", "poll", "question_id", "poll_id", "pollster", "pop", "n", "start", "end",
                "candidate_key", "candidate_name", "pct", "file", "file_rule"]].reset_index(drop=True)


# ---------------------------------------------------------------- thinning (rule 6)

def thin(t):
    """Within a pollster and place: keep the latest release, then the latest that ended before it started, and so on.
    `t` holds only polls that ended on or before the date. Ties on end date: the later start (shorter field), then
    the lower poll number."""
    keep = []
    for _, g in t.sort_values(["end", "start", "poll"], ascending=[False, False, True]).groupby(["geo", "pollster"],
                                                                                                    sort=False):
        bound = None
        for poll, start, end in zip(g["poll"], g["start"], g["end"]):
            if bound is None or end < bound:
                keep.append(poll)
                bound = start
    return t[t["poll"].isin(keep)]


# ---------------------------------------------------------------- dates (rules 8, 10, 12; R8-R10)

@lru_cache(None)
def first_contest(cycle, party):
    return pc.first_contest(cycle, party)


@lru_cache(None)
def last_vote(cycle, party):
    ev = pc.events(cycle, party)
    ev = ev[ev["flag"].isin(pc.VOTE_FLAGS) & ~ev["cancelled"].astype(bool)]
    return ev["date"].max()


def half_life(cycle, party, as_of):
    return HALF_LIFE_FROM if as_of >= first_contest(cycle, party) else HALF_LIFE_BEFORE


@lru_cache(None)
def _place_rows(cycle, party):
    ev = pc.events(cycle, party)
    vote = ev["flag"].isin(pc.VOTE_FLAGS)
    # R10: a row labelled 'convention' whose vote was cancelled counts as a vote until the cancellation was known
    conv = ev["flag"].eq("convention").to_numpy() & np.array([len(pc._changes_for(r)) > 0 for _, r in ev.iterrows()],
                                                              dtype=bool)
    return ev[vote | conv]


def place_open(cycle, party, place, as_of):
    """Rule 12 and R10: a state's average stops on the day it votes (its first vote, as known on the date), and a
    place whose every vote is cancelled, as known on the date, has none."""
    if place == "US":
        return as_of <= last_vote(cycle, party)
    rows = _place_rows(cycle, party)
    rows = rows[rows["state"].eq(place)]
    known = [pc._known_date(r, as_of) for _, r in rows.iterrows()]
    live = [d for d, cancelled in known if not cancelled]
    if not live:
        return False
    dated = [d for d in live if pd.notna(d)]
    return not dated or as_of <= min(dated)


@lru_cache(None)
def voting_day(cycle, party, place):
    return pc.voting_day(cycle, party, place)


@lru_cache(None)
def _timeline(cycle, party):
    c = pd.read_csv(INTERIM / "primary_candidates.csv")
    c = c[(c["cycle"] == cycle) & (c["party"] == party)]
    return {k: (pd.to_datetime(e), pd.to_datetime(a), pd.to_datetime(s))
            for k, e, a, s in zip(c["candidate_key"], c["exploratory"], c["announced"], c["suspended"])}


@lru_cache(None)
def line_end(cycle, party, key):
    """Rule 10 and R8: the line's last day. The withdrawal date; or, for a candidate undeclared on the day of the
    first contest (never in the timeline, or not yet in), that day."""
    fc = first_contest(cycle, party)
    t = _timeline(cycle, party).get(key)
    if t is None:
        return fc
    expl, ann, susp = t
    dates = [x for x in (expl, ann) if pd.notna(x)]
    declared = (not dates) or min(dates) <= fc            # in the timeline with no date counts as declared
    end = susp if pd.notna(susp) else pd.NaT
    if not declared:
        end = fc if pd.isna(end) else min(end, fc)
    return end


# ---------------------------------------------------------------- the average (rules 7, 9, 11, 13, 14; R5-R7)

def wpercentile(x, w, q):
    """R7: the smallest reading at which the cumulative share of weight reaches q (inverted CDF)."""
    o = np.argsort(x, kind="stable")
    x, w = np.asarray(x)[o], np.asarray(w)[o]
    c = np.cumsum(w) / w.sum()
    return float(x[np.searchsorted(c, q - 1e-12)])


def weights(t, as_of, hl):
    """Rule 7 for the polls in the window, k per place (R6)."""
    age = (as_of - t["end"]).dt.days
    n = t["n"].fillna(N0).clip(upper=N_CAP)
    k = t.groupby("pollster")["poll"].transform("size")
    return 0.5 ** (age / hl) * np.sqrt(n / N0) * t["pop"].map(POP_W) / np.sqrt(k)


def average(cycle, party, place, as_of, poll_rows=None):
    """The average for one place as of a date: one row per live candidate line, or an empty frame.
    `poll_rows` replaces polls(cycle, party) (for the checks)."""
    as_of = pd.Timestamp(as_of)
    if not place_open(cycle, party, place, as_of):
        return pd.DataFrame()
    p = polls(cycle, party) if poll_rows is None else poll_rows
    p = p[p["geo"].eq(place) & (p["end"] <= as_of)]
    if p.empty:
        return pd.DataFrame()
    hl = half_life(cycle, party, as_of)
    t = p.drop_duplicates("poll")[["poll", "geo", "pollster", "pop", "n", "start", "end"]]
    t = t[t["end"] >= as_of - pd.Timedelta(days=WINDOW_HALF_LIVES * hl)]
    t = thin(t)
    if t.empty or (place != "US" and t["end"].max() < as_of - pd.Timedelta(days=RECENT_DAYS)):
        return pd.DataFrame()                                  # rule 12: a state needs a poll in the past 60 days
    t = t.assign(w=weights(t, as_of, hl).values)
    r = p.merge(t[["poll", "w"]], on="poll")
    r["line_end"] = [line_end(cycle, party, k) for k in r["candidate_key"]]
    r = r[r["line_end"].isna() | (r["line_end"] >= as_of)]
    if r.empty:
        return pd.DataFrame()
    out = []
    for key, g in r.groupby("candidate_key", sort=False):
        out.append(dict(candidate_key=key, candidate_name=g["candidate_name"].mode().iat[0],
                        avg=float(np.average(g["pct"], weights=g["w"])),
                        band_lo=wpercentile(g["pct"], g["w"], 0.10), band_hi=wpercentile(g["pct"], g["w"], 0.90),
                        n_polls=int(g["poll"].nunique()), n_pollsters=int(g["pollster"].nunique()),
                        latest=g["end"].max()))
    out = pd.DataFrame(out)
    n = len(out)                                                # rule 11: lines named in the window, not ended
    out["cut"] = 100 / (2 * n + 1)
    out["shown"] = (out["avg"] >= out["cut"]) & (out["latest"] >= as_of - pd.Timedelta(days=RECENT_DAYS))
    out.insert(0, "as_of", as_of)
    out.insert(0, "place", place)
    out.insert(0, "party", party)
    out.insert(0, "cycle", cycle)
    out["half_life"] = hl
    out["polls_in_place"] = len(t)
    out["pollsters_in_place"] = t["pollster"].nunique()
    return out.sort_values("avg", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- outputs (R12, R13)

def national_series(cycle, party, start=None):
    """The national average for every day from `start` (default: the first national poll) to the last vote."""
    p = polls(cycle, party)
    us = p[p["geo"].eq("US")]
    if us.empty:
        return pd.DataFrame()
    days = pd.date_range(max(us["end"].min(), pd.Timestamp(start or us["end"].min())), last_vote(cycle, party))
    return pd.concat([average(cycle, party, "US", d) for d in days], ignore_index=True)


@lru_cache(None)
def _results():
    r = pd.read_csv(INTERIM / "primary_results.csv", low_memory=False)
    r = r[r["line"].eq("candidate")]
    r = r[r["rcv_round"].isna() | r["rcv_round"].eq("first")]  # R12: first round
    r["date"] = pd.to_datetime(r["date"])
    return r


def _result(cycle, party, place, date):
    r = _results()
    r = r[(r["cycle"] == cycle) & (r["party"] == party) & (r["state"] == place) & (r["date"] == date)]
    if r["contest"].nunique() > 1:
        raise ValueError(f"two results on one day: {cycle} {party} {place} {date:%Y-%m-%d}")
    return r[["candidate_key", "share", "measure", "contest"]].assign(share=lambda x: 100 * x["share"])


def last_averages(cycle, party):
    """Each place's last average, on its voting day (rule 13), beside the result of that vote (R12); where that
    vote is non-binding, the main contest's result too."""
    p = polls(cycle, party)
    main = pc.contests(cycle, party).set_index("state")
    out = []
    for place in sorted(set(p["geo"]) - {"US"}):
        day = voting_day(cycle, party, place)
        if pd.isna(day):
            continue
        a = average(cycle, party, place, day)
        if a.empty:
            continue
        res = _result(cycle, party, place, day)
        a = a.merge(res[["candidate_key", "share"]], on="candidate_key", how="left")
        a["result_measure"] = res["measure"].iat[0] if len(res) else None
        a["result_contest"] = res["contest"].iat[0] if len(res) else None
        main_day = main["date_known"].get(place) if place in main.index else pd.NaT
        if pd.notna(main_day) and main_day != day:
            m = _result(cycle, party, place, main_day)
            a = a.merge(m[["candidate_key", "share"]].rename(columns={"share": "share_main"}), on="candidate_key",
                        how="left")
            a["main_date"] = main_day
        out.append(a)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def coverage(cycle, party, last):
    """Rule 15: coverage by place. `last` is last_averages(cycle, party)."""
    p = polls(cycle, party)
    t = p.drop_duplicates("poll")
    cal = pc.contests(cycle, party)
    places = sorted(set(t["geo"]) | set(cal["state"].dropna()))
    rows = []
    for place in places:
        g = t[t["geo"].eq(place)]
        la = last[last["place"].eq(place)] if len(last) else last
        rows.append(dict(cycle=cycle, party=party, place=place, open_contest=(cycle, party) in OPEN,
                         polls=len(g), pollsters=g["pollster"].nunique(),
                         first_poll=g["end"].min(), last_poll=g["end"].max(),
                         voting_day=pd.NaT if place == "US" else voting_day(cycle, party, place),
                         last_average=bool(len(la)) if place != "US" else None,
                         last_average_polls=int(la["polls_in_place"].iat[0]) if len(la) else None,
                         huffpost_file_may_predate=bool((g["file_rule"] == 3).any())))
    out = pd.DataFrame(rows)
    out["last_average_polls"] = out["last_average_polls"].astype("Int64")
    return out


def report(last, cov):
    """Rule 15's description, by cycle and party (no pass mark). The winner is the top candidate in the results file for
    the vote beside the average (R12), whether or not they have a line; the leader is the top line in the average."""
    rows = []
    for (cycle, party, place), g in last.groupby(["cycle", "party", "place"]):
        g = g.sort_values("avg", ascending=False)
        res = _result(cycle, party, place, voting_day(cycle, party, place))
        winner = res.loc[res["share"].idxmax(), "candidate_key"] if len(res) else None
        top = g.head(2)
        miss = None
        if len(top) == 2 and top["share"].notna().all():
            miss = abs((top["share"].iat[0] - top["share"].iat[1]) - (top["avg"].iat[0] - top["avg"].iat[1]))
        has = g["share"].notna()
        inside = (g.loc[has, "share"] >= g.loc[has, "band_lo"]) & (g.loc[has, "share"] <= g.loc[has, "band_hi"])
        rows.append(dict(cycle=cycle, party=party, leader_won=g["candidate_key"].iat[0] == winner, miss=miss,
                         inside=int(inside.sum()), lines=int(has.sum())))
    r = pd.DataFrame(rows).groupby(["cycle", "party"]).agg(
        contests=("leader_won", "size"), leader_won=("leader_won", "sum"), top_two_margin_miss=("miss", "mean"),
        lines_inside_spread=("inside", "sum"), lines_with_result=("lines", "sum"))
    st = cov[cov["place"].ne("US")]
    c = st.groupby(["cycle", "party"]).agg(open_contest=("open_contest", "first"),
                                           states_with_polls=("polls", lambda x: int((x > 0).sum())),
                                           states_with_last_average=("last_average", "sum"), state_polls=("polls", "sum"),
                                           huffpost_file_may_predate=("huffpost_file_may_predate", "sum"))
    c["national_polls"] = cov[cov["place"].eq("US")].set_index(["cycle", "party"])["polls"]
    return c.join(r).reset_index()


def build():
    out = ROOT / "data/processed"
    nat, last, cov = [], [], []
    for cycle, party in CYCLES:
        print(cycle, party, flush=True)
        # R13 as agreed: committed from the start of the window (180 days before the first contest); earlier days
        # are rebuilt by national_series() or average()
        nat.append(national_series(cycle, party, first_contest(cycle, party) - pd.Timedelta(days=WINDOW_HALF_LIVES
                                                                                            * HALF_LIFE_BEFORE)))
        la = last_averages(cycle, party)
        last.append(la)
        cov.append(coverage(cycle, party, la))
    fmt = dict(index=False, float_format="%.2f", date_format="%Y-%m-%d")
    nat = pd.concat(nat, ignore_index=True)
    nat[["cycle", "party", "as_of", "candidate_key", "avg", "band_lo", "band_hi", "n_polls", "n_pollsters", "latest",
         "shown", "polls_in_place"]].to_csv(out / "primary_avg_national.csv", **fmt)
    last, cov = pd.concat(last, ignore_index=True), pd.concat(cov, ignore_index=True)
    last.to_csv(out / "primary_avg_last.csv", **fmt)
    cov.to_csv(out / "primary_avg_coverage.csv", **fmt)
    rep = report(last, cov)
    rep.to_csv(out / "primary_avg_report.csv", **fmt)
    print(rep.to_string(index=False))
    o = rep[rep["open_contest"]]
    print(f"leader won {rep.leader_won.sum()} of {rep.contests.sum()} (open: {o.leader_won.sum()} of {o.contests.sum()})")


if __name__ == "__main__":
    build()
