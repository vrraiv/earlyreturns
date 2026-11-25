"""Checks on the primary calendar and delegate rules (PP-4; PRIMARIES.md section 2, rule 14).

Lists problems; fixes nothing. Writes data/checks/primary_calendar_check.csv (one row per finding) and prints a
summary. Known disagreements from DA-6 (primary_calendar_check.csv) are carried as 'known'; the gaps DA-6 closed as
unresolved are not reopened.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/model"))
import primary_calendar as pc  # noqa: E402

OPEN = [(2008, "D"), (2008, "R"), (2012, "R"), (2016, "D"), (2016, "R"), (2020, "D"), (2024, "R")]
ALL = [(c, p) for c in pc.PAST for p in ("D", "R")]
OUT = ROOT / "data/checks/primary_calendar_check.csv"


def main():
    rows = []

    def add(kind, cycle, party, state, detail, severity="problem"):
        rows.append(dict(severity=severity, kind=kind, cycle=cycle, party=party, state=state, detail=detail))

    cal = pc._calendar()
    rules = pc._rules()

    for cycle, party in ALL:
        is_open = (cycle, party) in OPEN
        sev = "problem" if is_open else "note"
        ev = pc.events(cycle, party)
        # rule 4: at most one main contest per place, and every doubled place flagged by hand
        for st, g in ev.groupby("state"):
            n_main = int((g["flag"].eq("main") & ~g["cancelled"]).sum())
            if n_main > 1:
                add("two main contests", cycle, party, st, "; ".join(f"{r.contest} {r.date:%Y-%m-%d}" for r in g.itertuples()), sev)
        # calendar rows with no delegate rules
        r = rules[(rules["cycle"] == cycle) & (rules["party"] == party)]
        for st in sorted(set(ev["state"]) - set(r["state"])):
            add("contest with no delegate rules", cycle, party, st, "calendar row, no Green Papers rules row", sev)
        # rules 2 and 3 as of every date that matters: places with delegates but no main contest, date or class
        first = pc.first_contest(cycle, party)
        dates = [first - pd.Timedelta(days=pc.WINDOW_DAYS), first, None]
        for as_of in dates:
            c = pc.contests(cycle, party, as_of)
            canc = c["cancelled_known"].fillna(False).astype(bool)
            label = "as held" if as_of is None else f"as of {as_of:%Y-%m-%d}"
            if as_of is None:
                conv = set(ev.loc[ev["flag"].eq("convention"), "state"])
                for st in c.loc[c["date_known"].isna() & ~canc, "state"]:
                    if st in conv:
                        add("no vote of ordinary voters", cycle, party, st,
                            "delegates chosen by a convention only (rule 4)", "note")
                    else:
                        add("no main contest", cycle, party, st,
                            f"delegates in the rules, no contest in the calendar ({label})", sev)
            for st in c.loc[c["allocation_class"].isna(), "state"]:
                add("no allocation class", cycle, party, st, f"selection text not mapped ({label})", sev)
            for st in c.loc[c["total_delegates"].isna(), "state"]:
                add("no delegate total", cycle, party, st, label, sev)

    # rule 5: each date change reads back as the old date the day before it was announced
    # every change must belong to a calendar row, and each row must read back its earlier date the day before
    # its first change and its held date (or cancellation) after its last
    ch = pc._changes()
    used = set()
    for _, row in cal[cal["cycle"].isin(pc.PAST)].iterrows():
        mine = pc._changes_for(row)
        if mine.empty:
            continue
        used.update(mine.index)
        first, last = mine.iloc[0], mine.iloc[-1]
        before, _ = pc._known_date(row, first["announced"] - pd.Timedelta(days=1))
        want = pd.Timestamp(first["old_date"]) if pd.notna(first["old_date"]) else pd.NaT
        if not (before == want or (pd.isna(before) and pd.isna(want))):
            add("date change does not read back", row["cycle"], row["party"], row["state"],
                f"{row['contest']}: expected {first['old_date']} the day before {first['announced']:%Y-%m-%d}, got {before}")
        after, canc = pc._known_date(row, last["announced"])
        # a cancelled vote can leave a meeting behind: fine when the row is flagged as a convention (rule 4)
        if not ((canc and (row["cancelled"] or row["flag"] == "convention")) or after == row["date"]):
            add("last change is not the held date", row["cycle"], row["party"], row["state"],
                f"{row['contest']}: after {last['announced']:%Y-%m-%d} reads {after}, held {row['date']}")
    for r in ch.loc[~ch.index.isin(used)].itertuples():
        add("date change for a contest not in the calendar", r.cycle, r.party, r.state,
            f"{r.contest} {r.old_date} -> {r.new_date} ({r.announced:%Y-%m-%d})", "note")

    # rule 4 for 2024: hand flags beside the Green Papers' "major delegate selection event" column
    gp = pd.read_csv(ROOT / "data/interim/primary_greenpapers_events.csv", dtype=str)
    gp = gp[gp["major_delegate_selection_event"].eq("1") & gp["state"].notna()]
    for r in cal[(cal["cycle"] == 2024) & cal["flag"].eq("main") & ~cal["cancelled"]].itertuples():
        g = gp[gp["state"].eq(r.state) & gp["party"].eq(r.party)]
        if len(g) and not (pd.to_datetime(g["date_begin"]) == r.date).any():
            add("2024 main contest is not the Green Papers' major event", 2024, r.party, r.state,
                f"main {r.contest} {r.date:%Y-%m-%d}; major event(s) " + ", ".join(g["date_begin"]), "check")

    # known disagreements from DA-6, carried, not fixed
    known = pd.read_csv(ROOT / "data/interim/primary_calendar_check.csv", dtype=str)
    for r in known[known["green_papers_has_date"].eq("False")].itertuples():
        add("known: date not among the Green Papers' events", r.cycle, r.party, r.state, f"{r.contest} {r.date}", "known")

    # 2028 (rules 9 to 12)
    f = pc._csv(pc.SUPP / "primary_calendar_2028.csv")
    if f is not None:
        bad = f[~f["status"].isin(["set_by_law", "set_by_party", "proposed", "assumed", "to_be_checked"])]
        for r in bad.itertuples():
            add("2028: unknown status", 2028, r.party, r.state, str(r.status))
        for r in f[f["source"].isna()].itertuples():
            add("2028: no source", 2028, r.party, r.state, "")
    for party in ("D", "R"):
        n = pc.assumed_counts(party)
        add("2028: assumed", 2028, party, "", f"{n['assumed_date']} of {n['contests']} dates assumed; "
                                              f"{n['assumed_rules']} rules assumed", "note")

    out = pd.DataFrame(rows, columns=["severity", "kind", "cycle", "party", "state", "detail"])
    out = out.drop_duplicates()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(out.groupby(["severity", "kind"]).size().to_string())
    print(f"\n{len(out)} rows -> {OUT.relative_to(ROOT)}")
    return out


if __name__ == "__main__":
    main()
