# Presidential primaries: design note

The note for the primaries track (work plan cards PP-1 to PP-11 in `planning/plan.js`). Started 2026-11-24 with PP-3.
Rules are written here before anything they govern is built or run, agreed with the project owner, and every run is
reported. PP-2 kept no holdout (too few open contests), so nothing is tuned against results unless it is declared as
such.

## 1. Polling averages (PP-3)

### Rules (written and agreed 2026-11-24, before any average was computed)

Nothing below is built yet, and no value in it was fitted: every value is a judgment, fixed before any run. The poll
files are `data/interim/primary_polls.csv` (2008, 2020, 2024) and `data/interim/primary_polls_huffpost.csv` (2012,
2016), described in `DATA.md`. "Declared" means running or exploratory on the poll's end date, or in the candidate
timeline with no announcement date (Keyes and Cox in 2008, minor 2024 candidates). "Undeclared" covers both
`not_yet` and `not_running`: the files tell them apart only by how the cycle ended, so no rule here separates them.

**What goes in**

1. **Questions.** Every question counts, with any candidate it names. There is no filter on ballot or status. A
   ballot test built from results (only candidates who later got votes) was considered and rejected: it uses what
   was not known on the poll's date.
2. **One question per poll.** Where a poll asks more than one (in 2020 and 2024 only), the question chosen has, in
   order:
   1. the most declared candidates;
   2. then the fewest withdrawn candidates;
   3. then the most candidates named;
   4. then likely voters over registered voters over adults;
   5. then the first listed in the file.
3. **Measure.** Each candidate's raw share as published. Undecided, other, uncommitted and write-ins stay in each
   poll's share and get no line; nothing is rescaled to 100.
4. **Internal polls** (538's flag, 2020 and 2024) are left out. Party-sponsored polls stay in. 2008 and the Pollster
   files carry no internal flag, so nothing is dropped there.
5. **Who was surveyed.** Party voters and all voters count. Pollster's samples of independents only (three rows) are
   left out.
6. **Tracking polls.** Within the same pollster, place and party, releases whose field dates overlap are thinned:
   keep the latest release, then the latest one that ended before that release started, and so on back. This is
   applied as of each date, on field dates, in every cycle (538's `tracking` flag is not needed).

**Weights** (as in the general-election averages, `src/model/pollavg.py`)

7. Each poll's weight is its recency weight × √(sample size / 600), with the sample capped at 3,000 and a missing one
   counted as 600, × the population weight from `data/processed/poll_settings.json` (a missing population, as in
   every 2008 row, counts as likely voters), ÷ √k, where k is the pollster's number of polls in the average. No house
   effects, no sponsor shift.
8. **Recency.** A half-life of 30 days until the cycle's first contest, then 7 days. The half-life goes by the date
   the average is computed: from the day of the first contest every poll is reweighted at 7 days. The first contest is
   the first state contest held for that party, sanctioned or not (Iowa in every cycle but the 2024 Democrats, whose
   first was New Hampshire's unsanctioned primary on 23 January).
9. **Window.** An average uses only polls that ended within six half-lives of its date: 180 days before the first
   contest, 42 days from it. k counts polls in the window only.

**The field and the map**

10. **Lines.** A candidate's line ends on their withdrawal date (`data/interim/primary_candidates.csv`); their earlier
    polls still count for everyone else, and nothing is reallocated (that is PP-5). A candidate undeclared on the day
    of the first contest has their line end that day.
11. **What is shown.** A candidate is shown where their average is at least 100 / (2n + 1) points and they have at
    least one poll in the past 60 days. n is counted per place (national, and each state): the candidates named in at
    least one poll in that place's window whose line has not ended. The cut is for display only; the output keeps
    every line, for PP-5.
12. **Places.** One national average and one per state, each from its own polls. A state has an average only with a
    poll from the past 60 days; nothing is borrowed from the national average or other states (PP-5). A state's
    average stops on the day it votes.

**Time**

13. **As of a date.** The average for a date uses polls that ended on or before it (no lag; the files carry end
    dates, not release dates). A contest's last average includes polls that ended on the day of the vote. Every
    average can be rebuilt as of any past date, which PP-6 needs; 2008's list comes from Wikipedia's page history.
14. **Band.** Each average carries the weighted spread of its polls (the 10th to 90th percentile of poll readings),
    labelled as the spread of the polls, not as a range for the result. Calibrated ranges belong to PP-5. Each average
    also shows its number of polls, number of pollsters and latest poll date.

**What is reported, and what may not be changed**

15. Reported, with no pass mark: coverage by cycle, party and place; and each contest's last average beside its
    result, as a description. Neither feeds any choice above. A value changed after results have been seen is
    declared as suggested by them.

**Not in PP-3**

- **2028 polls.** No collector is built now: the sources (Wikipedia first, VoteHub as the cross-check, decided at DA-6)
  may change before they are needed, and 2028 polls are not needed until after the design freeze. Wikipedia's page
  history lets the 2028 poll list be rebuilt as of any date later, so nothing is lost by waiting.
- States with no polls, where support goes when a candidate withdraws, and calibrated ranges: PP-5.

## 2. Calendar and delegate rules as inputs (PP-4)

### Rules (written and agreed 2026-11-25, before anything was built)

Nothing below is built yet. The past files are DA-6's: `data/interim/primary_calendar.csv` (dates),
`primary_delegate_rules.csv`, `primary_delegate_events.csv` and `primary_greenpapers_events.csv` (TheGreenPapers.com,
attributed and linked). This card adds a loader, `src/model/primary_calendar.py`, and hand-kept files in
`data/supplement/`. It builds no delegate allocation (PP-7).

**One input for every cycle**

1. **One loader.** The model reads the calendar and the rules only through `primary_calendar.py`, for past cycles
   and 2028 alike, so the backtest (PP-6) runs the same code on a calendar it was not fitted on. PP-10 takes the first
   contest (section 1, rule 8) and each state's voting day (rule 12) from it, with no copy of its own.
2. **Places.** Every place with delegates in that cycle's rules for that party: states, DC, the territories and
   Democrats Abroad. A place with no contest gets a row that says so (rule 6).
3. **Fields per contest.** Cycle, party, place; date; kind (primary or caucus); party-run or state-run; main or
   non-binding (rule 4); the date as known on any given day (rule 5); total delegates, split into pledged (bound) and
   unpledged; the threshold; the allocation class (rule 8); the source of each.

**Which event is the contest**

4. **Main contest.** A place's contest is the vote of ordinary voters from which its delegates are chosen, directly or
   through later conventions. Where a place holds two such votes for a party in a cycle (17 cases in 2008 to 2024,
   such as Washington's 2016 caucus and primary, or Nevada's 2024 Republican primary and caucus), the one that feeds
   delegate selection is the main contest and the other is kept, labelled non-binding. The flags are entered by hand
   in `data/supplement/primary_contest_flags.csv`, each with its source (the Green Papers page for that state and
   party), and each one is listed in this note. For 2024, they are checked against the Green Papers events file's
   "major delegate selection event" column. Whether a non-binding result counts as information about the candidates
   is for PP-5.

**Dates as they were known**

5. **Held and scheduled dates.** `primary_calendar.csv` holds the dates contests were held. For each contest whose
   date changed, or which was cancelled, on or after the start of its cycle's window (180 days before the first
   contest, as in section 1, rule 9), the earlier date and the day the change was announced are entered in
   `data/supplement/primary_date_changes.csv`, each with a source. Changes before the window count as known from its
   start. The loader then gives the calendar as it stood on any date, and PP-6 forecasts each state on that calendar,
   not the one held. The 2020 Democratic postponements are the main case; every cycle is checked.
6. **Cancelled contests.** A cancelled contest (four in 2024: Delaware and South Dakota Republicans, Delaware and
   Florida Democrats) has no date and no result. It is known as cancelled from the day it was announced (rule 5). The
   row is kept, so a place never looks merely missing.
7. **The first contest and voting day, for section 1.** The first contest stays as section 1, rule 8 has it: the
   first vote held for that party, sanctioned or not, main or non-binding (New Hampshire's Democratic primary on
   23 January 2024). A place's voting day for rule 12 is its first vote of either kind, since results are public from
   then. These clarify section 1 and do not change it; neither was set with any average computed.

**Delegate rules: only what PP-5 needs**

8. **Allocation class.** The Green Papers' "selection" text, which has some 25 forms, is kept as written and mapped by
   hand to one of five classes: proportional, winner-take-all, winner-take-most or mixed (any rule that gives most or
   all of the delegates to the leader at some level), unbound (delegates not tied to the vote) and no contest. The
   mapping is listed in this note. Thresholds, district and at-large splits and bonus delegates are carried as data
   for PP-7 and used by nothing in this card.

**2028**

9. **The 2028 file.** `data/supplement/primary_calendar_2028.csv`: one row per place and party, with the date, kind,
   status, source link and the date recorded. Status is one of: set by law, set by the party, proposed, assumed. Every
   change is appended to `data/supplement/primary_calendar_2028_log.csv` (date seen, field, old value, new value,
   source), never edited over. Nothing goes in from memory: each value is looked up, or marked "to be checked".
10. **Stand-ins for an unset date.** In order: a date set in state law (status "set by law"); else the party's 2024
    date for that place (status "assumed"); else, where that party's 2024 contest was cancelled, the other party's
    2024 date for that place (status "assumed"). A date the national party sets for the early states, once adopted,
    overrides the stand-in for those states.
11. **Stand-ins for unset rules.** Each party's 2024 rules for each place (totals, threshold, allocation class),
    status "assumed", until that party's 2028 rules are adopted and published. Totals that depend on 2024 results
    (Republican bonus delegates, Democratic allocation formulas) stay assumed until published.
12. **Shown with every forecast.** Every 2028 forecast states how many of its contests have an assumed date and how
    many have assumed rules.

**Keeping it current**

13. **Sources to watch.** The two national parties' calendar and rules decisions; state election offices and
    legislatures; TheGreenPapers.com's 2028 pages; Wikipedia's 2028 primaries pages. Checked by hand whenever the
    primaries track is worked on, until a scheduled routine is set up (optional, the owner's call).
14. **Checks.** A script confirms that every place the model uses has a main contest, a date or a cancelled status,
    a delegate total and an allocation class, as of any date. Known disagreements (such as the 20 of 538 dates that
    are not among the Green Papers' events) are listed, not fixed. The gaps DA-6 closed as unresolved are not reopened.
