# Presidential primaries: design note

The note for the primaries track (work plan cards PP-1 to PP-12 in `planning/plan.js`). Started 2026-11-24 with PP-3.
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

### Readings for the build (PP-10, 2026-11-25)

Section 1 is silent or slightly wrong on the points below. All fifteen readings were written into this note before any
average was computed. The owner agreed R2, R3, R8 and R12 then. R4 to R7 and R9 to R11 were agreed later the same day,
after the first build and with the comparison of last averages and results already computed, and are unchanged from
what was written before it. R13 was changed at that point, for file size only. R1, R14 and R15 were not put as
questions. The data checks behind the readings are in "What was built" below.

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
`primary_avg_last.csv`, `primary_avg_coverage.csv`, `primary_avg_report.csv` (described in `DATA.md`). `src/check_primary_averages.py` passes:
60 random averages are unchanged when rebuilt from the raw rows with every later row deleted (a sanity case confirms
the comparison can fail), and hand-worked cases agree for the weights, the band,
the thinning chain, the ladder (two 2012 polls), the half-life switch and window, a line's last day and a state's last
day.

Data notes from the build:

- Pollster keys (R2): 2008's 406 raw names come down to 115 keys, 2012's 103 to 86 and 2016's 220 to 151; 2020 and
  2024 keep 538's names.
- Merges in the pollster keys that rest on who conducted a poll rather than on its name: Concord Monitor, the two Reno
  Gazette-Journal names and a bare "2000" to Research 2000; bare CNN and "CNN Poll" to Opinion Research Corporation;
  bare Fox News to Opinion Dynamics; CNN/WMUR to the University of New Hampshire; Cook Political Report to RT
  Strategies; the Keystone Poll names (WTAE/Pittsburgh Tribune-Review among them) to Franklin & Marshall; Des Moines
  Register to Selzer; Whit Ayres to Ayres McHenry; and Reuters/Zogby/ARG (three national polls, late 2007) to Zogby,
  the least certain of these.
- FiveThirtyEight's late 2008 polls (Democratic state polls after 7 February, top two only) are dated by their middle
  day, not their last, so they enter an average a day or two before they ended.
- One 2008 poll (American Research Group, Iowa Republicans) has its start after its end in the file; its dates are
  taken in order.
- Kept under the rules as written, and listed here for the owner rather than acted on: 2008's Wikipedia lists include
  campaign polls the file has no flag for (Global Strategy Group for Edwards, Harstad for Obama, Fairbank, Maslin for
  Richardson), which rule 4 keeps because 2008 carries no internal flag; and 94 polls by Strategic Vision (53 Democratic, 41 Republican), which AAPOR
  censured in 2009 for not disclosing its methods and which was then suspected of fabricating results. Leaving either
  out would be a new rule.
- 2020 Republicans in Nevada and South Carolina have polls but no vote and no date-change rows (date changes were
  collected for the open contests only), so they never have an average.

**Report (rule 15; a description, no pass mark).** Of the readings above, R4 to R7 and R9 to R11 were agreed with
this comparison already computed, and are as written before it; R13 changed after it, for file size. Nothing else
changed. Written by `primary_avg.py` to `primary_avg_report.csv`. By cycle and party: states
with any poll; states with a last average (a poll in the 60 days before the vote); polls (after the question ladder,
before thinning); HuffPost places whose only file may predate the contest; and, for the places with a last average,
how often the leader in it won (the winner being the top candidate in the results file for that vote), the mean absolute miss on the top two's margin, and the share of candidate lines whose
result fell inside the poll spread.

| Cycle | Party | Open | States with polls | With a last average | State polls | National polls | HuffPost file may predate | Leader won | Top-two margin miss (points) | Result inside poll spread |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 2008 | D | yes | 45 | 40 | 816 | 242 | | 32 of 40 | 8.5 | 38% |
| 2008 | R | yes | 40 | 27 | 630 | 219 | | 23 of 27 | 6.4 | 50% |
| 2012 | R | yes | 21 | 18 | 438 | 353 | 0 | 15 of 18 | 7.8 | 52% |
| 2016 | D | yes | 38 | 33 | 555 | 360 | 6 | 28 of 33 | 12.4 | 35% |
| 2016 | R | yes | 44 | 34 | 695 | 363 | 15 | 29 of 34 | 9.2 | 49% |
| 2020 | D | yes | 42 | 28 | 578 | 514 | | 23 of 28 | 10.1 | 60% |
| 2020 | R | no | 23 | 8 | 74 | 115 | | 8 of 8 | 4.4 | 12% |
| 2024 | D | no | 23 | 12 | 100 | 307 | | 12 of 12 | 8.9 | 31% |
| 2024 | R | yes | 41 | 22 | 797 | 979 | | 20 of 22 | 11.0 | 32% |

In all, the leader in the last average won 190 of 222 contests (170 of 202 in the open contests), and the top two's
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

## 3. State model (PP-5)

### Scope (the owner's choices, 2026-11-25, made before any rule below was drafted)

The four questions were put as options. These are the options chosen, as worded then:

- **Fitting.** "A short pre-registered list of fitted values (e.g. undecided split, error size, momentum strength),
  each fitted with the cycle being forecast left out, so PP-6 scores each cycle on values not fitted to it.
  Everything else fixed by judgment."
- **Withdrawals.** "Each forecast uses the field as known that day; a withdrawn candidate's support is shared out
  among those left. Simulated future withdrawals move to PP-7, which needs them for delegates."
- **Split.** "This session writes section 3 of PRIMARIES.md (the rules, pre-registered) and adds a new build card
  (PP-12) to plan.js. PP-6 would then need PP-12."
- **States with no polls.** "Each candidate's share relative to national, predicted from state demographics and
  region, then updated with how they did in states that have already voted (similar states weigh more). Also handles
  momentum. Territories and Democrats Abroad stay on the national average." PP-6 compares the method against a plain
  baseline: the state average where there is one, the national average otherwise.

**Where the rules depart from the last choice (agreed by the owner 2026-11-25):**

- There is no separate demographic prediction. Demographics and region enter only through similarity: a state's
  standing is borrowed from similar states that have voted or been polled (rule 10). Before any state has voted or
  been polled, every unpolled state sits at the national average. A fitted regression on demographics per candidate
  would need values fitted within each cycle, from very few states.
- States polled but not yet voted count as evidence too, at half the weight of a result (rule 9).

**Already seen:** the PP-10 report (section 1). In each open contest, between a third and two-thirds of the places that
voted had no state average. Rule 6 is marked as suggested by that report.

### Rules (written 2026-11-25 before anything was built or run; agreed with the owner the same day)

The owner agreed four questions put after the draft: the two departures above; the dates scored (rule 16);
leaving out one contest, not one year (rule 16); and a proportional undecided split (rule 6). Everything else was
written as a judgment and not put as a question, except three put to the owner in a third round the same day and agreed (rules 9, 11 and 16, marked).
After an advisor review the same day, before anything was built or run, rules 3, 6, 10, 11 and 16 were tightened
(each contest's own 30-day and 7-day dates, a flat other share before any result, the region term in d², the
own-average exclusion, a floor on the log loss).

**What is forecast**

1. **Contests.** Every main contest (section 2, rule 4) of the seven open contests, 2008 to 2024. Incumbent-party
   contests (2020 R, 2024 D) are built but neither fitted nor scored. The four contests whose results measure is
   "unclear" (North Dakota D 2008, American Samoa R 2012, Maine D 2016, Guam D 2024) are forecast but neither fitted,
   scored nor used as evidence. A contest with no date as known on the forecast date is not forecast that day.
2. **Measure and winner.** Each candidate's share by the contest's own measure (votes, or delegate equivalents for some
   caucuses), as in R12. The winner is the top candidate by that measure.
3. **Forecast dates.** On every voting day of the cycle, as of the morning (results of that day unknown, polls that
   ended that day included, as in section 1, rule 13), every contest still to come is forecast. Also, for each
   contest, on the days 30 and 7 days before it (only that contest is forecast on those days, unless they are
   voting days). The eve-of-contest forecast is the one made on its own voting day.
4. **As known.** The calendar as known on the forecast date (section 2, rule 5), the field as known (announced
   candidacies and withdrawals, `primary_candidates.csv`), results of contests already held, and polls that had ended.
   Main-contest flags are as held (section 2, "What was entered").

**From polls to a result share**

5. **Field.** The live candidates on the forecast date who have a national average. A candidate who withdraws is
   dropped from every later forecast; their support goes to the others by rule 6. Ballot access is not modelled: a
   candidate absent from a state's ballot (Clinton alone in Michigan's 2008 Democratic primary, Romney and Paul alone
   in Virginia's 2012 Republican primary) is forecast there all the same. Votes cast before a withdrawal (early and
   absentee ballots) are not modelled either.
6. **Undecided and other.** On the poll scale the live candidates' averages sum to less than 100. Each is scaled up
   proportionally, so that the live candidates sum to 100 less an "other" share. *Suggested by the PP-10 report*
   (winners finish above their averages). Proportional is a judgment: EC-2 adopted the raw margin for the general
   election, which splits the undecided evenly between two candidates, and an even split in points was the
   alternative, and the owner chose proportional.
   - **The other share** in a voted state is 100 less the summed shares of the candidates live on the morning of its
     vote. It therefore includes uncommitted, write-ins, minor candidates and votes for withdrawn candidates still on
     the ballot.
   - **The forecast uses** the mean other share over the cycle's voted states so far, each weighted equally.
      - **Before any result** it is 2 points in every cycle (judgment). A previous contest's other share was rejected
     as the default: late states with one live candidate count every other vote as other, which inflates it.
7. **Scale.** A candidate's standing in a state is r = log(state share / national share), both on the result scale.
   Shares are floored at 1 point before the log.

**A state's expected share**

8. **National standing.** The national average on the forecast date (section 1), on the result scale (rule 6).
9. **Evidence from other states.** For each live candidate there are two kinds of observation r_t, both on the result
   scale:
   - each state already voted, at weight 1: its result against the national average on the morning it voted;
   - each state with a current average (section 1, rule 12) that has not yet voted, at weight ½ (judgment): that
     average against the national average on the forecast date.
   Only the 50 states and DC count as evidence. Territories and Democrats Abroad have no demographics, and small
   electorates move a lot. Non-binding votes are not evidence: their fields often differ, as in Nevada's 2024
   Republican primary. Section 2, rule 4 left this to PP-5; the owner's call.
10. **Level and pattern.** The level is the weighted mean of r_t over all observations, by rule 9's weights: does the
    candidate run above or below their national polls everywhere? The pattern is each observation's gap from the level.
    A state s gets:

        prior r_s = β × level + (W / (W + κ)) × the kernel-weighted mean of the pattern,

    where W is the summed kernel weight (kernel × rule 9 weight) over the observations.
    - **The kernel** has the same form as EC-5's similarity, exp(−d² / 2m²), m the median distance between states.
      d² is the squared distance on six standardized measures, plus 1 (judgment) where the two states are in
      different census regions; this is the region term, and m is computed with it included. The measures are degree share, log median income, and the white, Black and
      Latino shares from `state_demographics.csv` (the year before the election, per
      `state_demographics_vintages.csv`), with the rural share from `state_rural_share.csv` (the census in force).
      These are DA-11's tables, not the seven Downballot measures in `state_similarity()`.
    - **β carries momentum.** After a candidate beats their polls in early states, national polls move too, so β
      below 1 avoids counting it twice.
    - **Territories and Democrats Abroad** take r = 0: the national average, as chosen.
11. **A polled state.** A state with its own current average blends it with its prior on the log scale: r_s = w ×
    own-average r + (1 − w) × prior r_s, where w = n / (n + λ) and n is the polls in that average (section 1's
    `n_polls`). Its own average does not enter its own prior, neither the level nor the pattern.
    - **A main contest held after a non-binding vote** (Nevada R 2024, Missouri R 2012, and the rest in section 2): the
      state's average stopped on the first vote (section 2, rule 7). That last average is used as its own, as of the
      first vote. The owner's call.
12. **Expected shares.** National share × exp(r_s) for each live candidate, rescaled to sum to 100 less the other share.

**Uncertainty and draws**

13. **Error.** In each draw, on the log scale:
    - **National shock.** Each candidate gets one national shock, the same in every state. Its SD is τ × √(days to the
      contest / 30), with days floored at 1.
    - **State shock.** Each candidate also gets one shock per contest: SD σ_p in a polled state and σ_u in an unpolled
      one, × 1.5 in a caucus (judgment). The state shocks are correlated across states by the kernel (rule 10).
    - **Totals.** Shares are re-normalised after the shocks. There are 10,000 draws.
14. **No updating within a draw.** A simulated early result does not move later states within that draw. The shared
    national shock and the correlated state shocks are what link them. (Judgment, for the first version.) Rule 16 scores
    contests one at a time, so this joint structure is never tested here. It is a judgment, checked at PP-7, which
    depends on it.

**Fitted values, and how**

15. **The list.** Point values β, κ, λ; spread values τ, σ_p, σ_u. Six in all, nothing else fitted.
16. **How.** Each open contest is left out in turn and the values are fitted on the other six by grid search, on grids
    written down before the run. Leaving out 2008 D still fits on 2008 R, the same year (the owner's call, over
    leaving out the whole year).
        - **Dates scored** (the owner's call): each contest's forecasts made 30 days and 7 days before it and on its own
      voting day, each taken as the latest forecast date on or before that day. Each contest is weighted equally, and
      each of its three dates equally within it. Far-ahead dates are not fitted: announced-only withdrawals leave a
      field there that later shrinks, and those misses would dominate the loss.
    - **Point values** are fitted by the mean squared error of candidate shares, in points. Every candidate live on
      the forecast date is scored against their share in the result, 0 if absent; a withdrawal before the vote is a
      real miss.
        - **Spread values** are fitted next, by the log loss of the winner, with the winner's chance floored at one
      draw in 20,000.
    - **Which places are fitted and scored** (the owner's call): the 50 states and DC only. Territories and Democrats Abroad
      are forecast with the fitted errors but neither fitted nor scored: they sit at the national average and would
      pull σ_u and τ toward their misses.
    - **Reporting.** The fitted values for each left-out contest are all reported. The 2028 values are fitted on all
      seven.

**Output**

17. **For every forecast date and contest:** each live candidate's expected share, 10th and 90th percentiles, and
    chance of winning; whether the contest was polled; and W. The draws are kept for PP-7's thresholds: shares per
    candidate per contest, in calendar order, with the national shocks shared.
18. **Baseline (for PP-6).** The state average where there is one, otherwise the national average, both on the result
    scale (rule 6). It gets its own τ, σ_p and σ_u, fitted the same way (rule 16).

**Known gaps and open questions**

- **Home states** are not in the first version. A candidate's home state is almost always polled, so rule 11
  covers it. A home-state bonus would need a hand-entered home state per candidate.
- **Caucus results as evidence for primaries,** and the reverse, are treated alike. 2008 D (Obama far stronger in
  caucuses) suggests they differ. Left open.
- **Judgments that could be fitted instead:** rule 9's half weight, rule 10's region penalty, and rule 13's caucus
  multiplier. Fitting any of them takes the list past six.

### Readings and grids for the build (PP-12, 2026-11-25)

Written before any forecast was compared with a result. Three things were computed first, none of which reads a
result: the kernel (rule 10) for each cycle, the summed kernel weight W a state gets from 1, 5, 15 and 30 other states,
and the number of polls in each last average (already in `primary_avg_last.csv`). They set the scale of the κ and λ
grids. The PP-10 report (section 1) had been seen: its 9-point average miss on the top two's margin is why the σ grids
run as wide as they do.

**Put to the owner as questions and agreed, 2026-11-25, before any run** (each agreed as proposed):

S1. **A live candidate with no line in a voted state's result** (rule 9 is silent; Obama in Michigan 2008, most of the
    field in Virginia 2012): no observation for that candidate from that state. Rule 7's floor would otherwise give
    r = log(1 / national share), a very large negative number, to the level of every later state. The other
    candidates' results there still count. The forecast and the scoring are unchanged (rules 5 and 16: forecast all
    the same, scored as 0).
S2. **Rule 11's n** is the candidate's own `n_polls` in the state's average (polls that name them), as the rule's
    wording has it, so w differs by candidate within a state. The alternative was the place's poll count, the same
    for every candidate.
S3. **Keeping the draws** (rule 17). Draws are not stored: 10,000 draws for every contest, candidate and forecast
    date is several gigabytes. A function rebuilds them from a fixed seed, identically each time, and a check
    confirms it. Committed: the summary table of rule 17.
S4. **The grids**, below.

**Grids (rule 16).** Point values, searched jointly (11 × 9 × 9 = 891 points):

| Value | Grid | Corners |
|---|---|---|
| β | 0, 0.1, 0.2, … 1.0 | 0: the level is ignored; 1: taken in full |
| κ | 0, 0.5, 1, 2, 4, 8, 16, 32, ∞ | 0: the pattern in full; ∞: no pattern |
| λ | 0, 0.5, 1, 2, 4, 8, 16, 32, ∞ | 0: a polled state is its own average; ∞: its own polls are ignored |

W is about 0.6 per observed state (the median kernel value between two states is 0.61 in every cycle, m = 3.1): about
3 with five states observed, 9 with fifteen, 18 with thirty. A last average has a median of 5 polls per candidate
(a tenth have 1, a tenth 26 or more).

Spread values, on the log scale, searched jointly after the point values are fixed (8 × 8 × 8 = 512 points):

| Value | Grid |
|---|---|
| τ (at 30 days) | 0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.6 |
| σ_p | 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.6, 0.8 |
| σ_u | 0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0, 1.5 |

- **Ties** go to the first point in grid order (β slowest, then κ, then λ; τ, then σ_p, then σ_u; each ascending).
- **An edge.** A fitted value on the end of its grid is reported as such. No grid is extended or refined without the
  owner, and any such change is declared as suggested by the results.
- **Seed.** 2028, combined with the cycle, party and forecast date, so any forecast's draws can be rebuilt alone.
- **The spread fit** uses the same 10,000 standard draws for a forecast at every grid point. Scored one contest at a
  time, the winner's chance depends only on that contest's total SD (the candidates' shocks have the same SD, and
  re-normalising does not change who is top), so the kernel correlation plays no part in the fit.
- **The baseline** (rule 18) is the same code at β = 0, κ = ∞, λ = 0; only its three spread values are fitted.

**Readings not put as questions before the run.** After run 1 the owner was asked about the ones that move numbers
(S10, S11, S13, S24, S26) and agreed them as written; S9 was changed, as it says.

*Dates and the calendar*

S5. The 30-day and 7-day dates are counted back from the date the contest was held. The forecast made that day uses
    the calendar as known that day, so the days to the contest in rule 13 are to its date as then known. A contest
    with no date known that day, or known as cancelled, has no forecast that day and that date is not scored (the
    contest's other dates keep equal weight among themselves).
S6. A voting day (rule 3) is a day with any vote, main or non-binding, as held. A state has voted once its main
    contest's date is before the forecast date; contests on the forecast date itself are not evidence for each other.
S7. A state between its non-binding vote and its main contest has no current average (section 1, rule 12), so it is
    not half-weight evidence. Its last average still serves as its own (rule 11), set against the national average
    of the day of the first vote.
S8. A caucus, for rule 13's multiplier, is a main contest the calendar calls a caucus or a convention.

*Shares*

S9. The field (rule 5) is the candidates whose national line is live on the forecast date (section 1, rule 10 and
    R8) and who have a national average that day. **Changed after run 1** (the owner's call; see "What was built"):
    and who are in the candidate timeline and had announced, or were exploring, by that date. A candidate in the
    timeline with no date counts as announced, as in section 1.
S10. The other share (rule 6) is averaged over the main contests of the 50 states and DC held before the forecast
    date, those with a result. In each it is 100 less the summed shares of the field as it stood on the morning of
    that vote.
S11. The result scale: the field's averages are multiplied by one factor so that they sum to 100 less the other
    share. A state's average is scaled by its own factor, over the field candidates it names.
S12. A voted state's observation sets its result against the national average on the morning it voted, on the result
    scale as it stood that morning (that morning's field and other share). Only candidates in today's field are
    observed.
S13. A field candidate missing from a state's average takes the prior alone (w = 0) in that state, and that state's
    average is no observation for them elsewhere.
S14. With no observation at all, the prior r is 0 (the national average). W and the kernel-weighted mean leave out
    the state itself; the level leaves out only the state's own average (rule 11), so it is the same for every
    state that is not itself an observation.
S15. A polled state, for σ_p, is one with an average of its own that day (S7's included); every other is unpolled.

*Draws*

S16. Each candidate gets one standard national draw per forecast date, scaled by each contest's own horizon (τ ×
    √(days / 30)), so the national shock is perfectly correlated across contests of different dates. A path over time
    (independent increments) is the alternative, and matters only jointly: flagged for PP-7.
S17. State shocks are drawn per candidate, independently between candidates, with correlation across the 50 states
    and DC equal to the kernel. Territories and Democrats Abroad get independent shocks at σ_u (× 1.5 in a caucus).
S18. The other share is fixed within a forecast's draws. The expected share (rule 17) is rule 12's value, not the mean
    of the draws; the percentiles and the chance of winning come from the draws. A tie for top is split.
S19. The winner is the top candidate line in the result. A winner outside the field gets rule 16's floor.

*Fitting and outputs*

S20. A main contest with no result row is forecast but neither scored nor used as evidence; the count is reported.
S21. The committed forecasts of each open contest use the values fitted with that contest left out; the incumbents'
    contests use the values fitted on all seven. Every row names the values it used. The all-seven values, for 2028,
    are reported beside them.
S22. Outputs for 2012 and 2016 derive from the HuffPost file and carry its terms (`LICENSE-DATA.md`).
S23. **Checks.** A forecast is unchanged when every later poll, result, withdrawal and date change is deleted; changing
    a left-out contest's results leaves that fold's fitted values unchanged; the kernel has no negative eigenvalue;
    a hand-worked case for rule 10; the baseline corner returns the state average or the national one; the seed
    rebuilds the same draws.

*Added while the code was written, still before any forecast was compared with a result; not put as questions*

S24. **The squared error of a forecast** (rule 16) is the mean over the field candidates, so a contest counts the
    same whatever the size of its field. A contest's loss is the mean over its scored dates, and a fit's loss the
    mean over its contests.
S25. **The floor and the baseline.** Rule 7's 1-point floor sits inside r, so at the baseline's corner a candidate
    below 1 point in a state's average or nationally is not returned exactly at their state average. The check in
    S23 is made where every share is at least 1 point.
S26. A contest is forecast only until its date as then known has passed (reworded before any run; see "What was
    built").
S27. The spread fit and the committed chances use the same draws: a forecast date's standard draws are fixed by the
    seed whatever is forecast from them, so a fitted chance is the chance the table shows at those values.

### What was built (PP-12, 2026-11-25)

`src/model/primary_state.py` builds the model as the rules and readings above set them out. `Race(cycle,
party).forecast(as_of, values)` gives rule 17's table for any date, `.draws()` the 10,000 draws behind it, contests in
calendar order (S3), and `fit()` the values. Outputs in `data/processed/`: `primary_state_values.csv` and
`primary_state_forecasts.csv` (described in `DATA.md`; 42,232 rows, 4.7 MB, every forecast date of rule 3 for the model
and the baseline). `src/check_primary_state.py` runs S23's checks, and passes. The owner agreed to commit the whole table and to the line in
`LICENSE-DATA.md` for its 2012 and 2016 rows.

**One change to S23 as written.** "Every later date change is deleted" could not be done as such: the calendar file
holds each contest's date as held, so deleting its later changes does not give the date as known earlier. The check
instead hides from the model every contest not yet held, so that it can reach a date only through the loader as of
the forecast date (whose own check is `src/check_primary_calendar.py`). Writing that check changed S26 before any
run: as first coded, a contest was dropped once its known date had passed only if it was never held, which needs the
future to tell.

**The runs.** The fit was run twice, both times on the grids as written.

*Run 1* used S9 as first written. A listing of its field then showed people who were polled nationally but never
ran, kept by the averages until the first contest (section 1, rule 10): Gore (15 points) in 2008 D, Gingrich (8) in
2008 R, Giuliani (10) in 2012 R, Biden, Warren, Cuomo and Gillibrand (15, 6, 2 and 1) in 2016 D, Hillary Clinton and
Kerry (9 and 6) in 2020 D, and nine names at 2 points or less in 2024 R. They were in 62 of the 987 fitted forecasts,
all on the 30-day and 7-day dates of early states, took share in rule 6's scale-up and were scored against 0. Rule 4
says the field is announced candidacies. The owner chose the announced field and a rerun. The change was made with
run 1's losses already seen; it was found from the listing of the field, not from the losses.

*Run 2* is the model as it stands, and what the outputs hold. The point values are the same as run 1's in every
fold. Three spread values moved by one grid step (σ_u from 0.4 to 0.6 with 2012 R left out, τ from 0.3 to 0.4 with
2016 R left out and from 0.3 to 0.2 with 2024 R left out), and three of the baseline's.

Run 2:

| Left out | β | κ | λ | τ | σ_p | σ_u | Squared error (fit) | Log loss (fit) | Baseline τ | σ_p | σ_u | Squared error | Log loss |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 2008 D | 0.6 | 0 | 0.5 | 0.3 | 0.3 | 0.4 | 158.4 | 0.527 | 0.4 | 0.3 | 0.4 | 164.7 | 0.544 |
| 2008 R | 0.7 | 0 | 0.5 | 0.2 | 0.3 | 0.4 | 159.1 | 0.484 | 0.3 | 0.3 | 0.4 | 166.6 | 0.494 |
| 2012 R | 0.6 | 0 | 0.5 | 0.3 | 0.3 | 0.6 | 168.6 | 0.520 | 0.3 | 0.3 | 0.6 | 174.6 | 0.528 |
| 2016 D | 0.6 | 0 | 0 | 0.4 | 0.3 | 0.4 | 150.7 | 0.527 | 0.4 | 0.3 | 0.4 | 154.0 | 0.538 |
| 2016 R | 0.9 | 0 | 0.5 | 0.4 | 0.3 | 0.4 | 160.0 | 0.538 | 0.4 | 0.3 | 0.6 | 169.8 | 0.557 |
| 2020 D | 0.7 | 0 | 0.5 | 0.4 | 0.3 | 0.4 | 161.6 | 0.550 | 0.3 | 0.3 | 0.6 | 169.2 | 0.561 |
| 2024 R | 0.6 | 0 | 0.5 | 0.2 | 0.3 | 0.4 | 166.0 | 0.592 | 0.3 | 0.3 | 0.4 | 174.3 | 0.609 |
| none (for 2028) | 0.7 | 0 | 0.5 | 0.3 | 0.3 | 0.4 | 160.7 | 0.534 | 0.4 | 0.3 | 0.4 | 167.6 | 0.548 |

Run 1 (superseded):

| Left out | β | κ | λ | τ | σ_p | σ_u | Squared error (fit) | Log loss (fit) | Baseline τ | σ_p | σ_u | Squared error | Log loss |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 2008 D | 0.6 | 0 | 0.5 | 0.3 | 0.3 | 0.4 | 157.7 | 0.528 | 0.4 | 0.3 | 0.4 | 163.8 | 0.545 |
| 2008 R | 0.7 | 0 | 0.5 | 0.2 | 0.3 | 0.4 | 158.8 | 0.485 | 0.3 | 0.3 | 0.4 | 166.0 | 0.495 |
| 2012 R | 0.6 | 0 | 0.5 | 0.3 | 0.3 | 0.4 | 168.0 | 0.522 | 0.3 | 0.3 | 0.6 | 173.7 | 0.530 |
| 2016 D | 0.6 | 0 | 0 | 0.4 | 0.3 | 0.4 | 150.7 | 0.527 | 0.4 | 0.3 | 0.4 | 154.0 | 0.539 |
| 2016 R | 0.9 | 0 | 0.5 | 0.3 | 0.3 | 0.4 | 159.4 | 0.539 | 0.4 | 0.3 | 0.4 | 169.0 | 0.560 |
| 2020 D | 0.7 | 0 | 0.5 | 0.4 | 0.3 | 0.4 | 160.8 | 0.551 | 0.4 | 0.3 | 0.4 | 168.1 | 0.562 |
| 2024 R | 0.6 | 0 | 0.5 | 0.3 | 0.3 | 0.4 | 165.6 | 0.593 | 0.3 | 0.3 | 0.4 | 173.6 | 0.611 |
| none (for 2028) | 0.7 | 0 | 0.5 | 0.3 | 0.3 | 0.4 | 160.3 | 0.535 | 0.4 | 0.3 | 0.4 | 166.9 | 0.550 |

Both losses are on the contests each row was fitted on, not on the one left out: they say how the fit went, and are no
test. Scoring each contest on values not fitted to it is PP-6. (The check script also runs the fit twice on 300
draws, to compare a fold before and after its left-out contest's results are shuffled.)

- **On an end of its grid:** κ, at 0, in every fold of both runs (the pattern is taken in full, with no shrinkage; 0
  is the lowest value κ can take), and λ, at 0, with 2016 D left out. Reported as S4 requires; no grid was changed.
- **How flat the fit is** (run 2, all seven; squared error): 160.7 at the fitted point. β from 0.5 to 0.9 stays
  within 0.3 of it; β = 0 gives 163.2 and β = 1 gives 161.3. κ = ∞ (no pattern) gives 165.2. λ = 2 gives 163.6 and
  λ = ∞ (own polls ignored) 191.1. Everything at the national average gives 200.9. Seven contests do not pin β down.
- **By date and by whether the state was polled** (run 2, all-seven values; squared error, model against baseline):
  on the day, 71.6 against 70.9 in polled states (201 forecasts) and 251.2 against 282.5 in unpolled ones (124); 7
  days before, 100.0 against 100.4 (188) and 233.6 against 250.0 (139); 30 days before, 123.0 against 129.1 (135)
  and 228.8 against 228.4 (200). What the model adds on these fitted contests is in the unpolled states, close to
  the vote. A description on the fitted contests, not a test.
- **In the averages:** 123 of the 987 forecasts have a field of one candidate, which no fitted value moves. In no
  forecast was the winner outside the field or at the floor of rule 16.
- **S27 holds:** the fitted chance of each winner equals the chance in the committed table (291 forecasts compared).

**What was scored.** 345 main contests in the 50 states and DC have a usable result; 335 are fitted, on 987 forecasts.

- **No national average, so no field (rule 5):** 48 contest-dates, among them all three dates of 10 contests. These
  are late contests of races already settled, where no national poll fell in the 42-day window. All three dates:
  eight Republican contests of May and June 2008 (Idaho, Kentucky, Montana, Nebraska, New Mexico, Oregon, South
  Dakota, West Virginia) and the Democrats' Connecticut and Louisiana in 2020. The last two dates: Indiana, North
  Carolina and Pennsylvania R 2008, Utah R 2012, and Delaware, Kentucky, New Jersey and New York D 2020. The day
  itself: Kentucky and Oregon R 2024. The model makes no forecast there.
- **Measure unclear (rule 1):** North Dakota D 2008, Maine D 2016.
- **No result row (S20):** Hawaii and Wyoming R 2008, Missouri R 2012 (the caucuses after its non-binding primary),
  Wyoming R 2024, and DC R 2016, whose convention result is in the file with no date. Forecast, not scored, not
  evidence. Collecting them would be a data card's work.

**Flagged for the owner, not acted on**

- **The other share is large after an odd contest.** On 5 February 2008 the Democratic other share is 8.6 points,
  mostly from Michigan (Obama and Edwards off the ballot, 40% uncommitted). Rule 6 as written; every later forecast
  that cycle carries it.
- **Late contests with no national polls** have no forecast at all (above). A rule for them (carry the last
  national average forward, say) would be new.
- **S16** (one national draw scaled by horizon) and rule 14 are untested here and are PP-7's to check.

## 4. Backtest on past contests (PP-6)

### Scope (the owner's choices, 2026-11-25, made before any left-out forecast was scored)

Four questions were put as options. The options chosen:

- **Pass mark.** One mark, on the winner's log loss (rule 4 below); everything else is reported with no mark. A miss
  means the first version (PP-9) publishes the baseline's odds, not the model's.
- **A calendar not fitted on.** The test is the left-out-race forecasts already committed. A second reading refits
  with both parties of 2008, and of 2016, left out together, and scores those four races again beside the first.
- **A field of one candidate.** Out of the headline; the all-forecasts figures are reported beside it. (The question
  as put said these forecasts "score perfectly" for model and baseline. That holds for the winner's chance. Their
  squared error is not zero, only the same for both.)
- **If the test suggests a change.** One declared round: after the report the owner may choose one set of changes,
  written into this note before the rerun, and both runs are reported side by side.

### What had been seen when this was written

- **The fit's losses** (section 3, run 1 and run 2): the model's and the baseline's squared error and log loss on the
  contests each fold was fitted on, and on all seven. The model is below the baseline on both in every fold. The point
  values barely move between folds, so each left-out race's squared error is roughly implied by its fold's loss set
  against the all-seven loss, and much the same for the log loss. **The pass mark is therefore suggested by numbers
  already seen**, and is declared as such. No left-out score had been computed.
- **Section 3's descriptions on the fitted contests:** how flat the fit is, and the squared error by date and by
  polled or unpolled.
- **The PP-10 report** (section 1).
- **Choices settled with all seven races in view:** the grids, S9 as changed after run 1, and readings S10, S11, S13,
  S24 and S26, agreed after run 1. Leaving a race out removes it from the six fitted values, not from these.
- **Not seen:** calibration, the coverage of the 10th-to-90th range, the Brier score, any score by race on left-out
  values, and anything on the forecast dates that were not fitted.

### Rules (written 2026-11-25 before any score was computed)

Rules 1, 4, 6 and 10 carry the owner's four choices. The rest are judgments, put to the owner as a whole before the
run.

**What is scored**

1. **The forecasts.** The rows of `primary_state_forecasts.csv` as committed (PP-12, run 2): each open contest's
   rows use the values fitted with that race left out (S21). Nothing is refitted for the headline. Before any score is
   printed the script confirms that every scored row's `values` names its own race, and that the scored set comes to
   335 contests and 987 forecasts, as in section 3.
2. **The scored set** is PP-12's (rule 16 of section 3; `scored_set()`): main contests of the seven open contests in
   the 50 states and DC with a usable result, on the days 30 and 7 before each and on its own day. The winner is S19's.
   Results are read through the model's own functions, not derived again.
3. **A field of one.** A forecast whose field has one candidate is out of the headline (the owner's call). A contest
   with no other scored forecast drops out of the headline with it. Every table also gives the all-forecasts figure,
   and the counts of each.

**The mark**

4. **Winner's log loss** (the owner's call; suggested by the fit's losses, as above). The loss of a forecast is −log
   of the chance given to the winner, floored at one draw in 20,000. A contest's loss is the mean over its scored
   dates in the headline; a race's is the mean over its contests; the pooled figure is the mean over all contests, each
   weighted equally (as S24). **The model passes if its loss is below the baseline's in at least 5 of the 7 races and
   in the pooled figure.** Equal is not below. A miss on either part is a miss.
5. **A miss** means PP-9 publishes the baseline's odds. No other figure in the report rescues a miss, and none turns
   a pass into a miss; the owner may still act on what the report shows, and says so if they do.
6. **The rerun** (the owner's call: one declared round). The mark is read on the first run. If the owner chooses a set
   of changes afterwards, it is written here before the rerun, the second run is reported beside the first, and its
   figures are described as following a change suggested by this test. A second run is no longer a test of anything it
   changed, and it does not turn a first-run miss into a pass (judgment; the standing rule that a diagnostic never
   rescues a fail). What PP-9 publishes after a rerun is the owner's call, written here.

**What is reported, with no mark**

Each for the model and the baseline, pooled and by race, and at 30 days, 7 days and the day; pooled figures also by
whether the state was polled (S15).

7. **Measures.**
   - **Winner's log loss,** as rule 4.
   - **Brier score:** the sum over the field's candidates of (chance of winning − 1 if they won, else 0)², weighted as
     rule 4.
   - **Squared error of shares,** as S24.
   - **Winner called:** the share of forecasts in which the candidate with the highest chance won.
   - **Coverage:** the share of field candidates whose result (0 if absent) lies from the 10th to the 90th percentile,
     ends included. 80% is the nominal figure. One count per candidate per forecast.
   - **Calibration:** every field candidate's chance of winning, in bins with edges at 0, 5, 15, 30, 50, 70, 85, 95 and
     100% (a chance on an edge goes to the upper bin; 100% to the last). For each bin: the count, the mean chance and
     the share who won. One count per candidate per forecast, pooled over races and dates, and once more on the day's
     forecasts alone. Candidates in one forecast are not independent, and no test is made.
8. **How the comparison is read.** As seven paired differences, one per race. The contests of a race share candidates
   and a national shock, so they are not separate tests, and seven are too few for a significance test. None is made;
   the seven differences are listed.
9. **By place in the calendar** (the card's question, described on the left-out forecasts). The headline's log loss
   and squared error by how many of the 50 states and DC had voted before the forecast date (S6): none, 1 to 4, 5 to
   19, 20 or more.
10. **The year left out** (the owner's call; second reading). `fit()` gains two folds: 2008 D and R left out together,
    and 2016 D and R together. Their fitted values are reported with any on a grid's end. The four races are forecast
    again on their scored dates at those values, model and baseline, and every measure of rule 7 is given beside the
    first reading's for those races. No mark. 2012 R, 2020 D and 2024 R are alone in their years and are unchanged.
11. **The other forecast dates.** Every row of the table for the 50 states and DC (rule 3 of section 3: every voting
    day, every contest still to come), with a field of two or more, by days to the contest as then known: 0, 1 to 7,
    8 to 14, 15 to 30, 31 to 60, 61 or more. Log loss and squared error, model against baseline, each row counted
    once. A description: these dates were not fitted, and a contest far ahead has many rows.
12. **Territories and Democrats Abroad.** Their forecasts on the day, where the results file has a usable result:
    log loss and squared error, counted apart from everything above. They sit at the national average in model and
    baseline alike, so the two differ only in their spread values.
13. **Not scored,** and listed as such: the 48 contest-dates with no forecast (late contests of settled races, so not
    a random gap), the two contests with an unclear measure and the five with no result row (section 3).

**Outputs**

14. `src/model/primary_backtest.py` writes one row per scored forecast and model to
    `data/processed/primary_backtest.csv` (the winner, the chance given to them, the losses, the reading) and prints
    the tables. It is run once for the first reading and once for the second; every run is reported here.

### What was run (PP-6, 2026-11-25)

The owner agreed the rules above as written, and rule 6's reading of the rerun, before anything ran.
`src/model/primary_backtest.py` scores the forecasts; `data/processed/primary_backtest.csv` holds one row per scored
forecast (described in `DATA.md`). The first reading ran once.

**The mark is met.** On the headline forecasts (a field of two or more: 303 contests, 864 forecasts), the model's
log loss is below the baseline's in 5 of the 7 races and in the pooled figure, 0.613 against 0.625. It is met with
nothing to spare on the count of races, and the pooled gap is 0.011. The mark was suggested by the fit's losses, as
declared above.

First reading, headline, each race on the values fitted without it (model, then baseline):

| Race | Contests | Log loss | | Brier | | Squared error | | Favourite won | | In the 10th-90th range | |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 2008 D | 50 | 0.573 | 0.575 | 0.380 | 0.382 | 174.3 | 184.0 | 64% | 59% | 60% | 62% |
| 2008 R | 41 | 0.905 | 0.945 | 0.492 | 0.504 | 172.2 | 174.5 | 64% | 63% | 52% | 54% |
| 2012 R | 50 | 0.646 | 0.668 | 0.338 | 0.348 | 116.1 | 127.8 | 75% | 75% | 77% | 75% |
| 2016 D | 50 | 0.586 | 0.608 | 0.400 | 0.421 | 222.9 | 245.4 | 73% | 67% | 80% | 77% |
| 2016 R | 42 | 0.625 | 0.585 | 0.332 | 0.305 | 109.0 | 85.3 | 76% | 81% | 58% | 63% |
| 2020 D | 32 | 0.712 | 0.762 | 0.384 | 0.400 | 79.4 | 84.8 | 74% | 72% | 47% | 46% |
| 2024 R | 38 | 0.249 | 0.240 | 0.106 | 0.104 | 101.9 | 100.5 | 95% | 95% | 55% | 56% |
| Pooled | 303 | 0.613 | 0.625 | 0.351 | 0.356 | 144.3 | 148.9 | 74% | 73% | 60% | 61% |

- **The seven differences** (rule 8; log loss, model less baseline): −0.001, −0.040, −0.022, −0.022, +0.040, −0.050,
  +0.009. The same five races favour the model on the Brier score and on squared error. The model is worse in both
  2016 R (clearly, on every measure) and 2024 R (slightly). In 2008 D the two are level.
- **With fields of one included** (335 contests, 987 forecasts): log loss 0.549 against 0.560, Brier 0.314 against
  0.319, squared error 162.4 against 167.6, the favourite won in 77% against 75%, coverage 58% against 59%. The
  same five races favour the model. The baseline's 167.6 is the figure section 3 gives for it on all seven, as it
  should be: its point values are not fitted.
- **The ranges are too narrow.** A candidate's result lies from the 10th to the 90th percentile 60% of the time,
  against a nominal 80%, and the baseline's ranges are no better (61%). By date: 79% on the day, 63% at 7 days, 46% at
  30 days (baseline 79%, 63%, 48%). By race it runs from 47% (2020 D) to 80% (2016 D). Two possible reasons, neither
  tested: the spread values were fitted to the winner's chance, not to shares; and announced-only withdrawals leave
  candidates in the field at 30 days who are gone by the vote and are scored against 0.
- **The chances of winning are close to what happened** (every field candidate, all three dates; model, then
  baseline):

  | Chance | Count | Mean chance | Won | Count | Mean chance | Won |
  |---|--:|--:|--:|--:|--:|--:|
  | 0 to 5% | 1,441 | 0.7% | 1.0% | 1,414 | 0.8% | 1.0% |
  | 5 to 15% | 438 | 9% | 7% | 474 | 10% | 7% |
  | 15 to 30% | 342 | 22% | 18% | 335 | 22% | 19% |
  | 30 to 50% | 442 | 40% | 38% | 457 | 39% | 41% |
  | 50 to 70% | 350 | 59% | 63% | 332 | 59% | 60% |
  | 70 to 85% | 156 | 77% | 83% | 148 | 77% | 82% |
  | 85 to 95% | 141 | 91% | 96% | 144 | 90% | 93% |
  | 95 to 100% | 108 | 99% | 94% | 114 | 99% | 96% |

  From 5 to 50% candidates win a little less often than stated, and from 50 to 95% a little more: the middle of the
  scale is slightly underconfident. The top bin is the exception, 94% won at a stated 99% (six misses in 108; the
  baseline four in 114). On the day's forecasts alone the pattern is the same, on a third of the counts (the 30 to 50%
  bin: 41% stated, 34% won; the top bin 95% won at 98.5%). No test is made (rule 7).
- **By date** (log loss, squared error): on the day 0.516 against 0.537, and 112.0 against 123.3; at 7 days 0.615
  against 0.638, and 141.9 against 148.1; at 30 days 0.772 against 0.768, and 179.9 against 180.7. The model's gain
  is close to the vote. At 30 days there is none.
- **By whether the state was polled:** unpolled, 0.769 against 0.789 and 216.4 against 224.4 (361 forecasts); polled,
  0.524 against 0.523 and 84.6 against 83.6 (503 forecasts). As on the fitted contests in section 3, what the model
  adds is in the states with no polls. In a polled state it is no better than the state's average.
- **By place in the calendar** (rule 9; states voted before the forecast date; log loss, squared error): none, 0.810
  against 0.804 and 93.4 against 96.2 (85 forecasts); 1 to 4, 0.815 against 0.805 and 196.1 against 197.0 (294);
  5 to 19, 0.645 against 0.679 and 166.4 against 173.4 (223); 20 or more, 0.395 against 0.414 and 127.6 against 137.8
  (262). With fewer than five states voted the model is level with the baseline or slightly behind on the winner;
  from five on it is ahead on both.
- **The other forecast dates** (rule 11; every row, a field of two or more, a mean over forecasts; log loss, squared
  error): on the day 0.516 against 0.537 and 112.0 against 123.3 (277 forecasts); 1 to 7 days, 0.624 against 0.648
  and 137.5 against 145.1 (498); 8 to 14, 0.603 against 0.620 and 169.2 against 175.7 (322); 15 to 30, 0.713 against
  0.721 and 192.0 against 194.4 (932); 31 to 60, 0.791 against 0.785 and 240.1 against 244.3 (854); 61 or more, 0.727
  against 0.712 and 333.0 against 321.9 (1,044). Beyond 30 days the model is behind on the winner, and beyond 60 on
  shares too. These dates were not fitted.
- **Territories and Democrats Abroad** (rule 12): only 10 forecasts on the day have a usable result and a national
  average, 6 of them with a field of two or more. On those 6, log loss 0.743 against 0.603 and squared error 438
  against 422; on all 10, 0.446 against 0.362 and 271 against 260. Too few to read. Rule 12 said the two differ only
  in their spread values. That was wrong: a territory with polls of its own is blended with them under rule 11, at
  the model's λ against the baseline's 0, so the expected shares differ too.
- **Not scored** (rule 13): 48 contest-dates with no forecast, 10 contests on all three dates; North Dakota D 2008
  and Maine D 2016 (measure unclear); Wyoming and Hawaii R 2008, Missouri R 2012, DC R 2016 and Wyoming R 2024 (no
  result row). As in section 3.

**The second reading: the year left out** (rule 10; run once, no mark). `fit()` took two more folds, and section 3's
folds came out unchanged. The rebuilt forecasts of the four races match the committed table at the committed values
(3,974 rows) before any were rebuilt at the new ones.

| Left out | β | κ | λ | τ | σ_p | σ_u | Baseline τ | σ_p | σ_u |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 2008 D and R | 0.6 | 0 | 0.5 | 0.2 | 0.3 | 0.4 | 0.3 | 0.3 | 0.4 |
| 2016 D and R | 0.9 | 0 | 0.5 | 0.4 | 0.3 | 0.4 | 0.4 | 0.3 | 0.4 |

κ is on the end of its grid, as in every fold. Against the race-left-out values, 2008 D's τ moves from 0.3 to 0.2
(baseline 0.4 to 0.3); 2008 R's β moves from 0.7 to 0.6; 2016 D's β moves from 0.6 to 0.9 and its λ from 0 to 0.5;
2016 R's are the same, and its baseline's σ_u moves from 0.6 to 0.4.

Headline forecasts of the four races, the race left out and then the year left out (model, baseline):

| Race | Log loss, race out | | Log loss, year out | | Squared error, race out | | Squared error, year out | |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 2008 D | 0.573 | 0.575 | 0.570 | 0.569 | 174.3 | 184.0 | 174.3 | 184.0 |
| 2008 R | 0.905 | 0.945 | 0.903 | 0.945 | 172.2 | 174.5 | 171.9 | 174.5 |
| 2016 D | 0.586 | 0.608 | 0.580 | 0.608 | 222.9 | 245.4 | 216.5 | 245.4 |
| 2016 R | 0.625 | 0.585 | 0.625 | 0.566 | 109.0 | 85.3 | 109.0 | 85.3 |
| The four | 0.663 | 0.669 | 0.660 | 0.663 | 172.1 | 176.0 | 170.3 | 176.0 |

- **The model's own figures barely move** with the same year's other party out of the fit: its log loss on the four
  goes from 0.663 to 0.660 and its squared error from 172.1 to 170.3. A calendar from a year not fitted on does it no
  harm.
- **The comparison narrows on the winner,** because the baseline's spread values change: the gap on the four goes
  from −0.006 to −0.003. 2008 D turns from just below the baseline (−0.001) to just above (+0.001), and 2016 R's
  deficit grows from 0.040 to 0.059. On this reading the model is below the baseline in two of the four races, not
  three. The mark is read on the first reading (rules 4 and 10); had it been read with the year left out, the count
  would be 4 of 7, a miss. 2008 D decides it, on a difference of a thousandth either way.
- **The deciding margin is within the noise of the draws.** 2008 D's difference is −0.0014 on the first reading and
  +0.0010 on the second, each a mean over 150 forecasts whose own differences have a standard deviation of 0.11.
  The chances come from 10,000 draws, and forecasts made on one date share their national draw, so a different
  seed could plausibly turn the sign. The verdict stands as registered, because rule 1 scores the committed table;
  a run on another seed would be a new diagnostic, and none was made.
- **Calibration on the second reading** (the four races, every field candidate, all three dates; model, then
  baseline):

  | Chance | Count | Mean chance | Won | Count | Mean chance | Won |
  |---|--:|--:|--:|--:|--:|--:|
  | 0 to 5% | 738 | 0.7% | 0.8% | 745 | 0.8% | 0.8% |
  | 5 to 15% | 218 | 10% | 10% | 248 | 10% | 10% |
  | 15 to 30% | 232 | 22% | 19% | 207 | 22% | 19% |
  | 30 to 50% | 286 | 40% | 40% | 277 | 40% | 44% |
  | 50 to 70% | 270 | 59% | 59% | 248 | 60% | 54% |
  | 70 to 85% | 126 | 77% | 80% | 132 | 77% | 82% |
  | 85 to 95% | 74 | 90% | 96% | 74 | 90% | 92% |
  | 95 to 100% | 22 | 98% | 100% | 35 | 98% | 97% |
- **The other measures** (the four pooled, race out then year out, model against baseline): Brier 0.400 against
  0.402, then 0.399 against 0.399; the favourite won in 69% against 67%, then 69% against 67% (2016 D's falls from
  73% to 70%); coverage 60% against 62%, then 60% against 61%.

**What the test does and does not show**

- The model meets the mark it was set, by the smallest count allowed, and the mark was itself suggested by losses
  already seen. The pooled gain on the winner is about 2% of the baseline's log loss. It is not a strong result.
- What the model adds is where it was built to add it: states with no polls, close to the vote, once five or more
  states have voted. In polled states, at 30 days and before five states have voted, it is level with the plain
  baseline.
- It is clearly worse in 2016 R. Nothing here says why, and no cause was looked for (rule 6: any change is the
  owner's one declared round).
- The share ranges are too narrow in model and baseline alike, most of all far from the vote. The chances of
  winning are much closer to what happened than the ranges are, apart from the top bin.
- A warning the fit prints (a log of zero in `win_chances`, so some candidate has an expected share of zero at
  some point) is in PP-12's code as built and is left alone. Which candidate was not looked up; with a log of minus
  infinity that candidate wins no draw.

**Put to the owner, not acted on:** whether to use the declared round (rule 6), and on what. Candidates the report
suggests, each of which would be declared as suggested by this test: the spread of shares (the ranges), the top of
the chance scale, and the dates beyond 30 days.

### The declared round: the share ranges (the owner's choice, 2026-11-25, after the report above)

The owner chose to use the round of rule 6, on the share ranges. Run 1's forecasts, values and scores stay in the repo
as they are; anything a change produces goes under its own label, so the verdict can be rebuilt.

**A diagnostic first** (written 2026-11-25 before it ran; run once, all of it reported). No change is proposed
before it: one total spread per forecast sets both the share ranges and the winner's chance, the chances are close
to what happened, and coverage on the day is 79%, so the shortfall is in the 30-day and 7-day forecasts. Those carry
more candidates (4.9 a forecast at 30 days against 3.2 on the day). The diagnostic asks whether the misses are
candidates who had left by the vote, the whole field moving together, or surviving leaders missing both ways. It
reads results already scored, so whatever follows from it is suggested by this test.

On the headline candidate rows of the first reading, for the model and the baseline, at 30 days, 7 days and the day:

- **D1.** The share of results below the 10th percentile, within the range, and above the 90th.
- **D2.** D1 split by whether the candidate was still in the field on the morning of the vote (section 3, S9) or had
  left it; and, of those who had left, how many have no line in the result.
- **D3.** D1 for candidates still in on the morning of the vote, split by the top two by expected share and the rest.
- **D4.** The other share: per forecast, 100 less the summed results of the forecast's field, set against the other
  share the forecast used. The mean and median difference, and the share of forecasts where it is more than 5 points
  either way.
- **D5.** The calibration table of rule 7 on the 30-day forecasts alone.

**What each outcome would mean** (written before the run):

- Mostly candidates who had left, scored at or near 0, with those still in above the 90th: no spread value mends
  this. It is the simulated withdrawals of PP-7. The proposal to the owner would be no change to the model, coverage
  among candidates still in at the vote as an added measure, and a reworded line on PP-7.
- The whole field off one way together: letting the other share vary in the draws would widen the ranges without
  moving the chances of winning.
- Candidates still in missing both ways: a change to the spread by horizon is defensible, at a cost to the winner's
  chance that would be put to the owner.
