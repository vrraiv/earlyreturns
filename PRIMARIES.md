# Presidential primaries: design note

The note for the primaries track (work plan cards PP-1 to PP-9 in `planning/plan.js`). Started 2026-11-24 with PP-3.
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
