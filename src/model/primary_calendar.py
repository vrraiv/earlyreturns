"""The primary calendar and delegate rules as inputs (PP-4; PRIMARIES.md section 2).

The one place the primaries model reads contest dates and delegate rules, for past cycles and 2028 alike
(section 2, rule 1). Nothing here allocates delegates (PP-7).

    contests(cycle, party, as_of=None)   one row per place: its main contest as known on `as_of`
    events(cycle, party, as_of=None)     every vote in the calendar, main and non-binding, as known on `as_of`
    first_contest(cycle, party, as_of)   section 1, rule 8: the first vote held for the party, of either kind
    voting_day(cycle, party, state, as_of)  section 1, rule 12: a place's first vote of either kind

Inputs: data/interim/primary_calendar.csv and primary_delegate_rules.csv (DA-6); primary_delegate_allocation_d/r.csv
for pledged and unpledged counts (2016-2024); hand-kept data/supplement/primary_contest_flags.csv (rule 4),
primary_date_changes.csv (rule 5), primary_allocation_classes.csv (rule 8) and primary_calendar_2028.csv (rules 9-11).
"""
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data/interim"
SUPP = ROOT / "data/supplement"

PAST = (2008, 2012, 2016, 2020, 2024)
STANDIN_CYCLE = 2024          # rules 10 and 11: 2028 stand-ins come from 2024
WINDOW_DAYS = 180             # rule 5: section 1's window before the first contest
VOTE_FLAGS = ("main", "non_binding")   # votes of ordinary voters; 'convention' and 'not_held' are not
CLASSES = ("proportional", "winner_take_all", "winner_take_most", "unbound", "no_contest")


def _ts(x):
    return None if x is None else pd.Timestamp(x)


# ---------------------------------------------------------------- inputs

@lru_cache(None)
def _calendar():
    c = pd.read_csv(INTERIM / "primary_calendar.csv", dtype={"cycle": int})
    c["date"] = pd.to_datetime(c["date"])
    c["cancelled"] = c["contest"].eq("cancelled")
    f = _csv(SUPP / "primary_contest_flags.csv")
    if f is not None:
        f["date"] = pd.to_datetime(f["date"])
        c = c.merge(f[["cycle", "party", "state", "contest", "date", "flag", "note"]].rename(columns={"note": "flag_note"}),
                    on=["cycle", "party", "state", "contest", "date"], how="left")
        missing = f.merge(c, on=["cycle", "party", "state", "contest", "date"], how="left", indicator=True)
        if (missing["_merge"] == "left_only").any():
            raise ValueError("contest flags with no calendar row:\n"
                             + missing.loc[missing["_merge"] == "left_only", ["cycle", "party", "state", "contest"]].to_string())
    else:
        c["flag"], c["flag_note"] = pd.NA, pd.NA
    c["flag"] = c["flag"].fillna("main")
    add = _csv(SUPP / "primary_calendar_additions.csv")   # places the FEC calendar never listed (territories, DA)
    if add is not None:
        add["cycle"] = add["cycle"].astype(int)
        add["date"] = pd.to_datetime(add["date"])
        add["cancelled"] = False
        dup = add.merge(c, on=["cycle", "party", "state"])
        if len(dup):
            raise ValueError("calendar additions for places already in the calendar:\n"
                             + dup[["cycle", "party", "state"]].drop_duplicates().to_string())
        c = pd.concat([c, add.rename(columns={"note": "flag_note"})], ignore_index=True)
    return c


def _csv(path):
    if not path.exists():
        return None
    return pd.read_csv(path, dtype={"cycle": "Int64"}, keep_default_na=False, na_values=[""])


@lru_cache(None)
def _changes():
    ch = _csv(SUPP / "primary_date_changes.csv")
    if ch is None:
        return pd.DataFrame(columns=["cycle", "party", "state", "contest", "old_date", "new_date", "announced"])
    ch["cycle"] = ch["cycle"].astype(int)
    ch["announced"] = pd.to_datetime(ch["announced"])
    return ch.sort_values("announced")


@lru_cache(None)
def _classes():
    return pd.read_csv(SUPP / "primary_allocation_classes.csv", dtype=str, keep_default_na=False)


def allocation_class(party, selection, cycle=None, state=None):
    """Rule 8: the hand mapping of the Green Papers' selection text to one of five classes."""
    m = _classes()
    m = m[m["party"].eq(party)]
    sel = (selection or "").strip()
    for _, r in m.iterrows():
        if r["selection"] not in ("*", sel):
            continue
        if r["cycle"] and str(cycle) != r["cycle"]:
            continue
        if r["state"] and state != r["state"]:
            continue
        return r["class"]
    return None


def _unpledged_from_text(breakdown):
    """2008 and 2012: unpledged delegates named in the Green Papers' breakdown text."""
    if not isinstance(breakdown, str):
        return None
    n = [int(x) for x in re.findall(r"(\d+)\s+Unpledged", breakdown, flags=re.I)]
    return sum(n) if n else 0


@lru_cache(None)
def _rules():
    r = pd.read_csv(INTERIM / "primary_delegate_rules.csv", dtype={"cycle": int})
    r = r[r["total_delegates"].notna()].copy()          # drops the empty 'UN' rows
    alloc = []
    for party, name, col in (("D", "primary_delegate_allocation_d.csv", "total_unpledged"),
                             ("R", "primary_delegate_allocation_r.csv", "total_unpledged")):
        a = pd.read_csv(INTERIM / name, dtype={"cycle": int})
        a["party"] = party
        alloc.append(a[["cycle", "party", "state", "total_pledged", col]].rename(columns={col: "unpledged"}))
    a = pd.concat(alloc)
    r = r.merge(a, on=["cycle", "party", "state"], how="left")
    early = r["unpledged"].isna()
    r.loc[early, "unpledged"] = r.loc[early, "delegate_breakdown"].map(_unpledged_from_text)
    r["pledged"] = r["total_pledged"].where(~early, r["total_delegates"] - r["unpledged"])
    r["allocation_class"] = [allocation_class(p, s, c, st) for p, s, c, st
                             in zip(r["party"], r["selection"], r["cycle"], r["state"])]
    return r[["cycle", "party", "state", "total_delegates", "pledged", "unpledged", "threshold_pct",
              "selection", "allocation_class", "green_papers_page"]]


# ---------------------------------------------------------------- dates as known (rule 5)

def _known_date(row, as_of):
    """The date (or cancellation) of one calendar row as it stood on `as_of`."""
    held = row["date"]
    if as_of is None:
        return held, bool(row["cancelled"])
    ch = _changes()
    ch = ch[(ch["cycle"] == row["cycle"]) & (ch["party"] == row["party"]) & (ch["state"] == row["state"])
            & (ch["contest"] == row["contest"] if not row["cancelled"] else True)]
    if ch.empty:
        return held, bool(row["cancelled"])
    seen = ch[ch["announced"] <= as_of]
    if seen.empty:                                   # before the first change: the earliest scheduled date
        return pd.Timestamp(ch.iloc[0]["old_date"]), False
    last = seen.iloc[-1]["new_date"]
    if str(last).lower() == "cancelled":
        return pd.NaT, True
    return pd.Timestamp(last), False


def events(cycle, party, as_of=None):
    """Every calendar row for a past cycle and party, with its date as known on `as_of` (None: as held)."""
    if cycle not in PAST:
        return _events_2028(party)
    as_of = _ts(as_of)
    c = _calendar()
    c = c[(c["cycle"] == cycle) & (c["party"] == party)].copy()
    known = [_known_date(r, as_of) for _, r in c.iterrows()]
    c["date_known"] = [k[0] for k in known]
    c["cancelled_known"] = [k[1] for k in known]
    c["date_status"] = "held"
    return c


def contests(cycle, party, as_of=None):
    """One row per place with delegates: its main contest (rule 4) as known on `as_of`, joined to its rules."""
    ev = events(cycle, party, as_of)
    main = ev[ev["flag"].eq("main") | ev["cancelled"]].drop_duplicates(["state"], keep="first")
    rules = _rules_for(cycle, party)
    out = rules.merge(main, on=["party", "state"], how="left", suffixes=("", "_cal"))
    out["cycle"] = cycle
    out.loc[out["cancelled_known"].fillna(False).astype(bool), "allocation_class"] = "no_contest"
    return out.sort_values(["date_known", "state"]).reset_index(drop=True)


def _rules_for(cycle, party):
    r = _rules()
    if cycle in PAST:
        out = r[(r["cycle"] == cycle) & (r["party"] == party)].copy()
        out["rules_status"] = "adopted"
        return out
    out = r[(r["cycle"] == STANDIN_CYCLE) & (r["party"] == party)].copy()   # rule 11
    out["cycle"] = cycle
    out["rules_status"] = "assumed"
    return out


def first_contest(cycle, party, as_of=None):
    """Section 1, rule 8: the first vote held for the party, main or non-binding, sanctioned or not."""
    ev = events(cycle, party, as_of)
    ev = ev[ev["flag"].isin(VOTE_FLAGS) & ~ev["cancelled_known"].astype(bool)]
    return ev["date_known"].min()


def voting_day(cycle, party, state, as_of=None):
    """Section 1, rule 12 as clarified by section 2, rule 7: a place's first vote of either kind."""
    ev = events(cycle, party, as_of)
    ev = ev[ev["state"].eq(state) & ev["flag"].isin(VOTE_FLAGS) & ~ev["cancelled_known"].astype(bool)]
    return ev["date_known"].min() if len(ev) else pd.NaT


# ---------------------------------------------------------------- 2028 (rules 9 to 12)

def _events_2028(party):
    """2028 as known now: the hand-kept file, with 2024 stand-ins where no date is set (rule 10)."""
    base = _calendar()
    base = base[(base["cycle"] == STANDIN_CYCLE)]
    f = _csv(SUPP / "primary_calendar_2028.csv")
    rows = []
    for st in sorted(_rules_for(2028, party)["state"]):
        hand = f[(f["state"] == st) & (f["party"] == party)] if f is not None else pd.DataFrame()
        # rule 10: a date the national party set overrides; then a date in state law; 'proposed' and
        # 'to_be_checked' rows are recorded but never used
        hand = hand[hand["status"].isin(["set_by_party", "set_by_law"]) & hand["date"].notna()] if len(hand) else hand
        if len(hand):
            h = hand.sort_values("status", key=lambda s: s.map({"set_by_party": 0, "set_by_law": 1})).iloc[0]
            rows.append(dict(state=st, contest=h["kind"], date_known=pd.Timestamp(h["date"]),
                             date_status=h["status"], source=h["source"]))
            continue
        own = base[(base["state"] == st) & (base["party"] == party) & base["flag"].eq("main") & ~base["cancelled"]]
        other = base[(base["state"] == st) & (base["party"] != party) & base["flag"].eq("main") & ~base["cancelled"]]
        src = own if len(own) else other
        if len(src):
            s = src.iloc[0]
            rows.append(dict(state=st, contest=s["contest"], date_known=same_weekday(s["date"], 2028),
                             date_status="assumed", source=f"{STANDIN_CYCLE} {s['party']} date "
                                                           f"({s['date']:%Y-%m-%d}), same weekday of the month"))
        else:
            rows.append(dict(state=st, contest=None, date_known=pd.NaT, date_status="unknown", source=None))
    ev = pd.DataFrame(rows)
    ev["cycle"], ev["party"], ev["flag"] = 2028, party, "main"
    ev["cancelled"] = ev["cancelled_known"] = False
    ev["date"] = ev["date_known"]
    return ev


def same_weekday(d, year):
    """The same weekday and week of the month in another year (the 1st Tuesday in March stays one).
    A fifth weekday that does not exist in `year` becomes the last one."""
    d = pd.Timestamp(d)
    nth = (d.day - 1) // 7
    first = pd.Timestamp(year=year, month=d.month, day=1)
    day = first + pd.Timedelta(days=(d.weekday() - first.weekday()) % 7 + 7 * nth)
    return day if day.month == d.month else day - pd.Timedelta(days=7)


def assumed_counts(party):
    """Rule 12: how many 2028 contests rest on an assumed date, and on assumed rules."""
    c = contests(2028, party)
    return {"contests": len(c),
            "assumed_date": int((~c["date_status"].isin(["set_by_law", "set_by_party"])).sum()),
            "assumed_rules": int(c["rules_status"].eq("assumed").sum())}
