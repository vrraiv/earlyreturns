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

### Readings for the build (PP-10; agreed with the owner 2026-11-25, before any average was computed)

Section 1 is silent or slightly wrong on the points below. Each reading was settled before any average was computed or
any result joined. The data checks behind them are listed after the readings.

**Polls and pollsters**

R1. **A poll** is (cycle, party, `poll_id`). 538 and HuffPost give one `poll_id` to a poll that asked both parties'
    voters; that is two polls here, one per party.
R2. **Pollster names.** One pollster key per name within a cycle, from a hand-kept file,
    `data/supplement/primary_pollster_names.csv` (raw name, key), built by a mechanical clean-up checked by hand. k
    (rule 7) and tracking (rule 6) use the key. Mainly 2008: Wikipedia gives 406 raw names, among them variants of one
    pollster ("Rasmussen Reports", "Rasmussen Reports Poll", "Scott Rasmussen (Rasmussen Reports)") and citation text.
R3. **One poll entered as several.** Rows with the same pollster key, place, party and field dates are one poll with
    several questions, and rule 2's ladder chooses among them. Wikipedia 2008 lists ABC/Washington Post's Iowa poll
    three ways; HuffPost 2012 lists one Fairleigh Dickinson question twice. Rule 2's "in 2020 and 2024 only" is wrong:
    HuffPost 2012 has four polls with more than one question.
R4. **Population.** HuffPost's "Likely Voters - Republican" and the like are read as likely voters, registered voters
    or adults; 538's `v` (six polls) as likely voters, as in `pollavg.py`.

**The average**

R5. A candidate's average is over the polls in the window that name them. A poll that does not name them does not
    count as zero for them.
R6. k is counted per place: the pollster's polls in that place's window after thinning, the same for every candidate.
R7. **Band.** The weighted 10th and 90th percentiles of the readings, by the inverted CDF: the smallest reading at
    which the cumulative share of weight reaches 10% (or 90%).

**Lines and places**

R8. A line's last day is the withdrawal date itself, and for rule 10's cut the day of the first contest, so the first
    contest's last average still has every candidate.
R9. The national average runs to the last vote held for that party in the cycle.
R10. A place with polls but no vote (2016 Republicans in Colorado, 2020 Republicans in Nevada and South Carolina, 2024
    Democrats in Florida and Republicans in South Dakota) has its average stop on the day the cancellation was known
    (the loader's dates as known); no result is set beside it.
R11. **Cycles.** Every cycle and party in the poll files is built, the incumbents' parties too (2020 Republicans, 2024
    Democrats). Reports mark the seven open contests, which are the ones PP-6 uses.

**The report (rule 15)**

R12. The result beside a place's last average is that of the vote on its voting day, where the average stops (section
    2, rule 7). Where that vote is non-binding, the main contest's result is shown too. The share is the results file's
    (one measure per contest: votes, or delegate equivalents for some caucuses), in points. Ranked-choice contests use
    the first round, since polls ask first preferences (Alaska and Kansas Democrats 2020).

**Outputs**

R13. Committed: the national average day by day from the start of the window (180 days before the first contest) to
    the last vote; each place's last average beside its result; the coverage table. Any other date is rebuilt by the
    function. (The owner's call, 2026-11-25, on file size: every day from the first national poll came to 14 MB.) Averages for 2012 and 2016 come from the HuffPost file: they credit HuffPost
    Pollster and are non-commercial, as `LICENSE-DATA.md` says for anything derived from it.
R14. The coverage table flags HuffPost contests whose only archived file may predate the contest (`file_rule` 3).
R15. **Checks.** Rebuilding an average with every later poll deleted gives the same number (thinning, k and n as of the
    date); small hand-worked cases for the weights, the ladder, the thinning chain and the switch to a 7-day half-life.

### What was built (PP-10, 2026-11-25)

`src/model/primary_avg.py` builds every average as the rules and readings above set them out; `average(cycle, party,
place, as_of)` rebuilds any one as of any date, for PP-6. Outputs in `data/processed/`: `primary_avg_national.csv`,
`primary_avg_last.csv`, `primary_avg_coverage.csv` (described in `DATA.md`). `src/check_primary_averages.py` passes:
60 random averages are unchanged with every later poll deleted, and hand-worked cases agree for the weights, the band,
the thinning chain, the ladder (two 2012 polls), the half-life switch and window, a line's last day and a state's last
day.

Data notes from the build:

- Pollster keys (R2): 2008's 406 raw names come down to 115 keys, 2012's 103 to 86 and 2016's 220 to 151; 2020 and
  2024 keep 538's names.
- One 2008 poll (American Research Group, Iowa Republicans) has its start after its end in the file; its dates are
  taken in order.
- Kept under the rules as written, and listed here for the owner rather than acted on: 2008's Wikipedia lists include
  campaign polls the file has no flag for (Global Strategy Group for Edwards, Harstad for Obama, Fairbank, Maslin for
  Richardson), which rule 4 keeps because 2008 carries no internal flag; and 94 polls by Strategic Vision (53 Democratic, 41 Republican), which AAPOR
  censured in 2009 for not disclosing its methods and which was then suspected of fabricating results. Leaving either
  out would be a new rule.
- 2020 Republicans in Nevada and South Carolina have polls but no vote and no date-change rows (date changes were
  collected for the open contests only), so they never have an average.

**Report (rule 15; a description, no pass mark, and nothing above was changed after it).** By cycle and party: states
with any poll; states with a last average (a poll in the 60 days before the vote); polls (after the question ladder,
before thinning); HuffPost places whose only file may predate the contest; and, for the places with a last average,
how often the leader in it won, the mean absolute miss on the top two's margin, and the share of candidate lines whose
result fell inside the poll spread.

| Cycle | Party | Open | States with polls | With a last average | State polls | National polls | HuffPost file may predate | Leader won | Top-two margin miss (points) | Result inside poll spread |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 2008 | D | yes | 45 | 40 | 816 | 242 | | 32 of 40 | 8.5 | 38% |
| 2008 | R | yes | 40 | 27 | 630 | 219 | | 23 of 27 | 6.4 | 50% |
| 2012 | R | yes | 21 | 18 | 438 | 353 | 0 | 15 of 18 | 7.8 | 52% |
| 2016 | D | yes | 38 | 33 | 555 | 360 | 6 | 29 of 33 | 12.4 | 35% |
| 2016 | R | yes | 44 | 34 | 695 | 363 | 15 | 29 of 34 | 9.2 | 49% |
| 2020 | D | yes | 42 | 28 | 578 | 514 | | 23 of 28 | 10.1 | 60% |
| 2020 | R | no | 23 | 8 | 74 | 115 | | 8 of 8 | 4.4 | 12% |
| 2024 | D | no | 23 | 12 | 100 | 307 | | 12 of 12 | 8.9 | 31% |
| 2024 | R | yes | 41 | 22 | 797 | 979 | | 20 of 22 | 11.0 | 32% |

In all, the leader in the last average won 191 of 222 contests (171 of 202 in the open contests), and the top two's
margin was missed by 9.2 points on average. Since undecided voters stay in each poll's share (rule 3), winners usually
finish above their averages, and the poll spread is not a range for the result (rule 14): calibrated ranges are PP-5's.
Where the first vote was non-binding (Nevada Republicans 2024, among others), the result beside the average is that
vote's, with the main contest's next to it (R12).


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

### What was entered (2026-11-25)

**Main and non-binding contests (rule 4).** In `data/supplement/primary_contest_flags.csv`, each with its reason.

- Main contest the caucus, primary non-binding: Democrats in Idaho 2008, Nebraska 2008, 2012 and 2016, Washington
  2008 and 2016; Missouri Republicans 2012 (the February primary was a beauty contest); Nevada Republicans 2024.
- Main contest the primary: Washington Republicans 2008 (it bound 19 delegates; the caucuses started the election of
  18 who went unpledged); New Hampshire Democrats 2024 (the party-run primary of 27 April; the unsanctioned state
  primary of 23 January is non-binding but stays the first contest under section 1, rule 8).
- Not votes of ordinary voters, so not contests: Nebraska Republicans' 2012 "caucus" (the state convention),
  Washington Republicans' 2016 precinct caucuses, Michigan Republicans' 2024 convention, Colorado and North Dakota
  Republicans 2016 (preference votes cancelled) and Wyoming Republicans 2016 (the state convention; the precinct
  caucuses tallied no preference vote), labelled `convention`. The test is whether a vote of ordinary voters was held
  and counted, not what the Green Papers call the event: Northern Mariana contests they call conventions (Republicans
  2012 and 2016, Democrats 2016 and 2020) have candidate vote counts in `primary_results.csv` and are contests.
  Wyoming Republicans' other cycles were not examined this way. Calendar rows for contests that were
  never held for that party (Utah Democrats' 2012 primary, Idaho Democrats' 2016 primary, DC and Kentucky
  Republicans' 2016 primaries) are labelled `not_held`.
- Added from the Green Papers' event lists (the owner's call, 2026-11-25): the territories and Democrats Abroad, which
  the FEC calendar never listed (`primary_calendar_additions.csv`). Three of them have only a convention and no vote
  counts (Virgin Islands Democrats 2008 and 2012, South Carolina Republicans 2020) and so have delegates but no
  contest. Northern Mariana and Nevada Republicans 2020 (not an open contest) are left as gaps.
- The flags are as held, not as known: where a party switched which vote binds during the cycle (Missouri Republicans
  2012, Nevada Republicans 2024), the switch is in the date changes, but a forecast made before it still sees the
  final main contest.

**Allocation classes (rule 8).** In `data/supplement/primary_allocation_classes.csv`. Every Democratic contest is
proportional (15% threshold). Republican wording: "Proportional" and "Combined Selection [ Proportional Primary with
Caucus/Convention ]" are proportional; "Winner-Take-All" in a primary or caucus is winner-take-all; winner-take-all by
district and statewide, winner-take-most, and the majority-trigger rules are winner-take-most or mixed; "Caucus/
Convention" (2008 and 2012), "Delegate Selection" caucuses and primaries and "Advisory Primary" are unbound. The
loophole primaries are mapped by state: Illinois winner-take-most (delegates listed with a candidate), Pennsylvania
unbound. A cancelled contest is "no contest". Checked against the rules file's thresholds and triggers and, for
2016-2024, the hard delegate totals; the stored pages then moved four to winner-take-most or mixed: North Dakota
Republicans 2008 and Kansas Republicans 2012 (caucuses that allocated every delegate from the vote) and West Virginia
Republicans 2012 and 2016 (delegates elected by name with a candidate listed, as in Illinois). Iowa and Nevada
Republicans 2008 stay unbound: their "5%" is the Green Papers' own estimate. A Democratic place with no vote keeps
"proportional", which then applies at the convention.

**Dates as known (rule 5).** 105 changes in `data/supplement/primary_date_changes.csv`, scoped to the seven open
contests. A blank earlier date means no date was set before the change; the loader then shows the contest with no
date until it was announced. Where sources disagree on a date, the note names both; the one used is stated. A change
whose sources name another kind of contest than the calendar does (Hawaii Democrats 2020: a party-run primary the
calendar calls a caucus) is matched to the row whose held date its last change produced. Checked: every change
reads back; on the eve of every main contest the known date is the held one.

Not found, so a missing row does not mean no change: decision dates for 2008 Kansas (both parties), North Dakota,
New Mexico Democrats, West Virginia, Alaska and Maine Republicans; the 2008 and 2012 territories and Democrats Abroad;
2024 DC Republicans' switch to a party-run primary and Montana, Oregon and South Dakota Republicans' switch to
conventions. Two changes concern contests not in the calendar (Montana Republicans' 2008 caucus, Idaho Republicans'
2012 primary) and are listed by the check. Changes before each window were collected too but are not entered: rule 5
counts them as known from its start.

**2028 (rules 9 to 11).** `data/supplement/primary_calendar_2028.csv`, as known on 2026-11-25: the DNC's early window
(South Carolina 22 January, Nevada 1 February, New Hampshire 8 February, New Mexico 15 February, Michigan 22 February,
Virginia 29 February; the Rules and Bylaws Committee on 24 July 2026, the full DNC in August), the RNC's order with no
dates (Iowa, New Hampshire, Nevada, South Carolina; 10 September 2026), and the dates that follow from state law. Where
the DNC's date and state law differ (New Mexico and Virginia Democrats), the DNC's date is used under rule 10's last
sentence.

**Agreed with the owner (2026-11-25).** Choices made while building, put to the owner afterwards and agreed:

1. A national party's date over state law where they differ (New Mexico and Virginia Democrats).
2. A 2028 stand-in date keeps the 2024 date's weekday and week of the month (Tuesday 5 March 2024 becomes Tuesday
   7 March 2028), not its day of the month.
3. Date changes collected for the seven open contests only, though rule 5 says every cycle.
4. The `convention` and `not_held` labels for calendar rows that are not votes of ordinary voters.
5. Matching a change to a calendar row by the date its last change produced, where the kinds differ.
6. 2028 Democratic rules: adopted and published (August 2026), so under rule 11 they replace the 2024 stand-ins.
   Loaded from Appendix B of the adopted Call (`data/supplement/primary_rules_2028_d.csv`): 3,774 pledged and 744
   automatic delegate votes, 4,518 in all, matching the Call's own totals. The automatic delegates follow
   office-holders and may change. Republican 2028 rules stay assumed.

PP-4's place before PP-10 (PP-10 takes its dates from this loader) is understood but not written into the plan, by
the owner's call.
