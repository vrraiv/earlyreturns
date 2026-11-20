# Electoral college model: design note

Work plan card EC-1, written 2026-11-20. This is a specification. Nothing here is built, no number in it was
estimated for it, and no 2024 presidential poll was set against a result while writing it. Each part is marked:

- **borrowed**: taken from the 2026 Senate model as it stands (`src/model/forecast.py`, `FORECAST.md`);
- **re-estimated**: the Senate model's form, with its numbers fitted again on presidential data;
- **new**: the Senate model has nothing like it;
- **candidate**: to be tested against the baseline before it is used;
- **decision**: for the project owner, not for the data.

## 1. Targets

The forecast is scored on four things, each at several dates before the election (section 6).

| Target | What is scored | Elections with data |
|---|---|---|
| State margins and winners | margin error, Brier, log loss, coverage of the 50% and 80% ranges | 2008 to 2020, with 2024 held out |
| National popular vote | error of the two-party margin, coverage | the same, and 1952 to 2016 for the national layer alone (section 7) |
| Electoral votes | where the result falls in the simulated count, the winner's probability | 2008 to 2020, with 2024 held out |
| The gap | tipping-point state's margin minus the national margin, forecast against actual | the same |

The popular vote is the two-party national margin computed from state totals, so the national figure and the state
figures always add up. With four scored elections, the last two targets can show a model that is plainly wrong and
little more.

## 2. Contests and electoral votes (new)

- 56 contests: 50 states, the District of Columbia, Maine's two districts and Nebraska's three.
- Electoral votes change with each census. The backtest needs them by election (2000; 2004 and 2008; 2012 to 2020;
  2024 and 2028). **Not in the repo yet.**
- Maine and Nebraska: the statewide winner takes two votes, each district one. A district is its own contest:
  prior = the state's forecast plus the district's lean relative to the state; its own polls where there are any
  (in the repo for 2016 to 2024); the state's shared errors plus a district error. **District results and lean are
  not in the repo yet.**
- 270 to win. A 269 to 269 tie is its own outcome, not split between the candidates.

## 3. Features

| Feature | Use | Source | Status |
|---|---|---|---|
| State lean, last two presidential elections | state prior | `state_presidential_history.csv` | re-estimated |
| National poll average as of a date | national estimate | EC-2 | re-estimated |
| State poll average as of a date, and its number of polls | state estimate, its weight | EC-2 | re-estimated |
| Pollster, sponsor and voter-population adjustments | inside the averages | `pollavg.py`, `pollster_effects.py` | borrowed, checked on presidential polls (EC-2) |
| Days to the election | spread of every poll-based estimate, and so the weight on polls | polls' dates | new |
| Fundamentals: outgoing president's approval, the economy, time in office | national prior | EC-3 | interface only (below) |
| A sitting president running | national prior | results history | re-estimated (2028 is an open seat) |
| Census region | shared state errors | `error_structure.py` | re-estimated |
| State's vote share of the nation | popular vote | previous election's two-party votes | new |
| Electoral votes by election | the count | to collect | new |
| Education, race, income, urban share | shared state errors | The Downballot's state tables (one snapshot, 2015-19) | candidate |
| Candidate's home state | state prior | candidate lists | candidate |
| Third-party share in the polls | wider spread in that state | polls | candidate |
| Expert ratings | none | | left out: every state that matters is polled |
| State economy | none | | left out: no effect found for the Senate |

Fundamentals interface (EC-3 decides what is inside): for each election and date, a national two-party margin and
its standard error, from data known on that date and fitted on earlier elections only.

## 4. Model

All margins are Democratic minus Republican, two-party, in points.

**National estimate (re-estimated).** N = the national poll average and the fundamentals, combined by precision.
The poll average's spread depends on days out (section 6), so fundamentals count for more early and for almost
nothing at the end.

**State prior (re-estimated).** prior_s = N + a + b1 x lean_s (last election) + b2 x lean_s (the one before), fitted
on earlier elections. The Senate model fixes the slope on lean at 1; here it is estimated.

**State estimate (borrowed form).** mu_s = w_s x poll average_s + (1 - w_s) x prior_s, with w_s from the two spreads:
the poll average's (falling with the number of polls, rising with days out) and the prior's (from the fitted weight
on polls, as `prior_weight.py` does for the Senate). An unpolled state takes the prior.

**National and state polls together (new; fixed here, before any score).** States come first. National polls and
fundamentals enter each state through its prior, so they carry a thinly polled state and count for little in a
heavily polled one. The forecast popular vote is the vote-weighted sum of the state estimates, not N. The
difference between that sum and N is reported with every forecast. One alternative is a candidate: move every state
by the same amount so the sum meets a blend of itself and N.

## 5. Errors and simulation

One draw of the election, for every contest s:

    margin_s = mu_s + national_s + region_s + slope x lean_s + state_s

| Part | What it is | Status |
|---|---|---|
| national | one draw shared by every state: the polls' common miss. Student-t. Its size depends on days out | re-estimated on presidential elections |
| region | one draw per Census region | re-estimated |
| slope x lean | one draw that tilts the map: Republican states more Republican and Democratic ones more Democratic, or the reverse | re-estimated |
| state | the state's own error, sized so the state's total spread is the one from section 4. Student-t | borrowed form |

- **Popular vote in a draw** = the sum over states of (vote share x margin_s), with vote shares from the previous
  election. It is never drawn separately. The size of the national error this implies is checked against history.
- **Electoral votes in a draw**: each contest's winner, added up. Reported: each side's win probability, the count's
  range, the tipping-point state, the chance the popular vote and the electoral college split, and the chance of a tie.
- **With other offices (CM-8)**: the national draw is the statewide-poll factor that Senate and governor races in
  the same year already share, and a state's own error can be shared with that state's other races.

**How state errors move together (candidates; EC-5).** The baseline above already has regions and the tilt by lean,
and that is what a demographic structure has to beat. Education is close to lean in today's map, so a demographic
term can look useful only because it restates the tilt. At most three candidates:

1. one draw on the share of adults with a degree, added to the baseline;
2. the same on the white share without a degree;
3. similarity between states on the seven measures in section 3, in place of regions.

## 6. Dates before the election (new)

The 2026 model was only ever run at the end. This one is scored at 100, 60, 30 and 7 days out.

- The spread of a poll average gains a term that grows with days out: squared spread = a + b / (number of polls) +
  d x days. The national error does the same. Both are fitted on earlier elections.
- Polls count for a date if they ended before it and name the two candidates presumed to be the nominees on that
  date. What to show before nominees are known is EC-8's decision.

## 7. Test

**As of each election.** Every parameter is fitted on earlier elections only, as in `BACKTEST.md`. The burn-in is
two elections for this office (decided 2026-11-20), so 2008 is scored; its fit is the thinnest, and its scores are
reported apart as well as pooled.

| Election | 100 days | 60 days | 30 days | 7 days |
|---|---|---|---|---|
| 2008 | no (2000 has only late polls) | no | scored | scored |
| 2012, 2016, 2020 | scored | scored | scored | scored |
| 2024 | held out | held out | held out | held out |

**Holdout (decided 2026-11-20).** 2024 presidential polls and results enter no fit, no choice between candidates
and no diagnostic until the design is frozen. Then 2024 is scored once and the result recorded whichever way it
goes. What the holdout does not cover: everyone knows roughly how the 2024 polls missed; the repo's
`president_poll_coverage.csv` already lists 2024 results beside poll counts; and 2024 Senate and governor races
are already scored in the backtest. The only test nobody has seen is 2028.

**How state errors move together.** A state's miss is its result minus its 7-day forecast. For each scored
election, each structure is fitted on earlier elections and gives a joint distribution for that election's 56
misses; the score is the log of the density it gives the misses that happened. This can show a structure is
clearly worse. Seven elections to learn from and four to score on will probably not separate two good ones.

**The national layer on a longer history.** `president_national_poll_days.csv` has a daily national average for 17
elections, 1952 to 2016. It tests how the poll average's error shrinks as the election nears and how fundamentals
should be weighed against it. It is a plain average, not EC-2's, it says nothing about states, and it stops at 2016.

## 8. Adoption rule (decision)

The governors' rule compares a gain with its spread over redrawn cycles. With four elections that spread means
nothing. Options:

1. **Recommended.** A candidate is written down before its run. It is adopted if the pooled score on its target
   improves by more than 0.005 at 7 days, it is better in at least three of the four elections, and it is no worse
   pooled at 30, 60 and 100 days. Then 2024, once.
2. No rule: every candidate is reported, and choices are argued case by case.
3. Wait for more history before choosing between structures, and ship the baseline.

## 9. Not in the repo yet

- Electoral votes by election.
- Maine's and Nebraska's district results and lean, 2000 to 2024.
- Whole-campaign state polls for 2000 (only the final 60 days are held).
- Demographics by year (DA-4). The one snapshot is from 2015-19.
- Fundamentals for presidential elections (EC-3).

## 10. Open questions

1. The adoption rule (section 8).
2. Whether the popular vote should be pulled toward the national polls (the alternative in section 4).
3. What to show before the nominees are known (EC-8).
4. Third candidates: a state where one polls in double digits needs a rule, as for governors.
5. The check against the 2026 lessons list is done at the design freeze (EC-9). The list (SC-4) waits for the final
   scorecard, and the build does not wait for it.
