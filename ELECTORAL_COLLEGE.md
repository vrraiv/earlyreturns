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
(2020 was added on 2026-11-20, built from the repo's polls: section 11.)

## 8. Adoption rule

*Decided 2026-11-20, before any candidate was run.* The governors' rule compares a gain with its spread over
redrawn cycles. With four elections that spread means nothing, so the threshold here is computed from what a
meaningless change scores on the same elections.

A candidate is written down before its run. It is adopted if all three hold, on the pooled score for its target at
7 days:

1. **It beats its own scrambled versions.** The candidate's feature is shuffled across states (one state's value
   handed to another), which keeps its shape and its number of fitted parameters and removes its information. At
   least 200 shuffles are run through the same backtest. The candidate's gain has to exceed the gain that 1 in 20
   of them reaches.
2. **It clears simulation noise.** The baseline is rerun with other random draws; the candidate's gain has to
   exceed the largest change between reruns.
3. **It is better in at least three of the four scored elections.**

Then 2024, once, recorded whichever way it goes.

- The 1 in 20 is the one number chosen by hand. It is a convention, not tuned to this data.
- Scrambling asks whether a feature carries any information. Whether it adds to what the baseline already has (the
  tilt by lean, for education) is answered by the comparison itself, since the baseline keeps that term.
- A change with no feature to shuffle, such as the alternative in section 4, is judged on conditions 2 and 3 alone.
- This is strict. With four elections a real but modest effect will often fail, which is what four elections can
  support. Every candidate run is reported, pass or fail, with its scrambled versions' distribution.
- The scores at 30, 60 and 100 days are reported beside the 7-day score and decide nothing by themselves.

## 9. Not in the repo yet

- Electoral votes by election.
- Maine's and Nebraska's district results and lean, 2000 to 2024.
- Whole-campaign state polls for 2000 (only the final 60 days are held).
- Demographics by year (DA-4). The one snapshot is from 2015-19.
- Fundamentals for presidential elections (EC-3).

## 10. Open questions

1. Whether the popular vote should be pulled toward the national polls (the alternative in section 4).
2. What to show before the nominees are known (EC-8).
3. Third candidates: a state where one polls in double digits needs a rule, as for governors.
4. The check against the 2026 lessons list is done at the design freeze (EC-9). The list (SC-4) waits for the final
   scorecard, and the build does not wait for it.

## 11. From today's polls to election day: evaluation plan (EC-2)

*Plan written 2026-11-20. Nothing in it has been run.* A poll average says how people would vote today. The
forecast needs what the polls will say on election day, and the adjustment between the two is the heart of this
model. Sections 6 and 7 only widened the range with distance from the election; this section adds changes to the
centre. It was confirmed the same day, and where it differs from sections 4 to 8 and 10, this section stands.

**Decided 2026-11-20**

- Only the forecast is published. The nowcast is kept as the yardstick: every adjustment is scored as forecast
  against nowcast.
- The forecast starts when both nominees are presumptive, which can be June. A test date near 150 days is added to
  100, 60, 30 and 7.
- Third-party support is dropped. Undecided voters are modelled, not just dropped.
- Polls of registered voters are corrected to likely voters, as the Senate average does.
- 2024 is out of everything in this section, including the tests that use no results. *One exception, decided
  2026-11-21:* the pollster-quality test below reads 2024 polls and results, and only if its fit on 2016 and 2020
  picks something other than the baseline. EC-7's 2024 score is then in-sample for that one choice.
- The date a nominee became presumptive is taken late when in doubt. Starting early is not worth a wrong matchup.
- The popular vote and the states come from the same draw, so the chance of a split and the gap to the
  tipping-point state stay meaningful. Two numbers that need not agree are ruled out.

**What the files show already** (checks, not fits)

- Conventions are mostly inside the last 100 days. The later convention ended between 61 and 103 days before the
  election in every year from 1952 to 2024, and within 100 days in 16 of 19. So the 100-day and 60-day forecasts
  often sit inside a bounce. (`data/interim/convention_dates.csv`, from Wikipedia's convention lists.)
- Undecided voters can be measured: in head-to-head questions, the share for neither candidate falls from about
  9 to 11 points five months out to 3 or 4 in the last week (2004 to 2012 and 2020; 2016 ran about twice that).
  Questions that name other candidates mix third-party support in, and the national series before 2004 always does.

**Two test beds**

| | National | States |
|---|---|---|
| Data | daily national average 1952 to 2020 (2020 built from the repo's polls) | state polls 2004 to 2020 |
| Scored elections | about 11 (1980 to 2020, where polls are dense), fitted on earlier ones | 2012 to 2020 at 150, 100 and 60 days; 2008 as well at 30 and 7 |
| Decides | how polls move over a campaign | what to do in states with few polls |

**Baseline.** Forecast = nowcast, with a range that widens with days out. The nowcast is the Senate average's
weighting applied to presidential polls.

**Stages, in order. Each candidate is written down before its run.**

1. *The nowcast itself.* How fast a poll goes stale, the registered-to-likely-voter correction and pollster
   effects, each chosen by how well the average predicts the next polls. No results are used. The weighting that
   gives the best nowcast is not necessarily the best for the forecast, so it is fixed here and not retuned later.
2. *Convention windows.* Three treatments: subtract a fitted rise and fade; down-weight polls in the window; only
   widen the range. National test bed.
3. *Reversion and trend.* National test bed, at most six candidates:
   - pull toward an anchor, by an amount that depends on days out. The anchor until EC-3 exists: the incumbent
     party's margin predicted from the sitting president's approval on that date and the previous result;
   - continue (or reverse) the last month's movement;
   - durability: a lead that has held for longer is pulled less toward the anchor. Measured as how much the
     average has moved over the campaign so far (its day-to-day spread), so a steady race gets both a weaker pull
     and a narrower range. Compared at the same number of days out, since every lead is older late in the year.
     This measure is agreed for now and may be revisited once the later cards are settled. 2008 is the case to
     look at by eye: after the financial crisis broke in mid-September the Democratic lead stopped moving. One
     case picked with hindsight illustrates a result; it cannot pass or fail a candidate;
   - undecided voters: how they break (in proportion to decided voters, evenly, or a fitted mix), and a wider
     range when there are many;
   - whether a shift that comes with a change in presidential approval lasts longer. Candidate favourability is
     not in the repo; collecting it for past elections is on the data track (DA-9), and it is tested beside the
     president's approval once it is. News is left out: nothing in the data measures it;
   - whether a shift spread evenly across states lasts longer than a concentrated one. Only the state polls from
     2004 can test this, so it is the weakest of the six.
4. *States with few polls.* Scored on states with no poll in the previous 30 days; at 100 days that was 15 to 29
   of 51 states in 2004 to 2016. Three ways to fill the gap: the prior (national estimate plus lean); the average
   swing in the polled states; the state's last poll carried forward by the national movement since. (The third
   was tried at stage 1, round 2, and not adopted. Stage 1's targets barely reach thinly polled places: in 60% of
   place-weeks there is no eligible new poll to score, and three in four where a place had 0 to 3 polls in the past
   month. So stage 1 says little about it there, and it stays a stage 4 candidate, scored against results. Its
   settings are written when stage 4 is pre-registered; stage 1's grid picks are not carried over.)
   *Selection, raised by the user on 2026-11-21 and placed here:* polls are fielded where races are close, so an
   unpolled state is usually lopsided, and being unpolled is itself evidence. And a lone poll in a thin state may
   be there because someone expected, or wanted to show, a surprise. Stage 4's pre-registration answers, against
   results in 2004 to 2020: how far thinly polled states landed from their no-poll forecast (national result plus
   lean), by how many polls they had; whether the few polls there moved toward the result or away from it, against
   that forecast alone; and sponsored against independent polls there, if there are enough. Thin-state results are
   not looked at before that pre-registration.
5. *The add-up.* One candidate against section 4's states-first rule: national polls set the popular vote, and the
   difference from the states' sum is spread over the states by their uncertainty and size, so large, thinly
   polled states absorb most of it. Either way the two come from one draw.

**Adoption rule for stages 2 to 4 (decided 2026-11-20; adds to section 8).** Section 8 judges at 7 days, where an adjustment
from nowcast to forecast is close to nothing. For these candidates:

- the score is the forecast's error against the result, averaged over 150, 100 and 60 days; 30 and 7 days are
  reported and must not get worse;
- on the national test bed, a candidate with a feature (an anchor, a trend, an undecided share) has to beat 19 in
  20 versions with that feature shuffled between elections, and be better in at least two thirds of the scored
  elections;
- a candidate with nothing to shuffle has to pass a sign test on its election-by-election gains at the same 1 in 20;
- on the state test bed, section 8 applies as written, at the dates above.

**Collected 2026-11-20** (calendar facts and polls; no results are used)

- Convention dates, 1948 to 2028: `data/interim/convention_dates.csv`. The figures above hold.
- The date each nominee became presumptive, 1980 to 2020: `data/interim/presumptive_nominees.csv`, entered by hand
  with a source on each row. 2024 gets its rows, under the rule below, when the holdout is scored.
- A 2020 national series, added to `president_national_poll_days.csv`. It is built from the repo's polls the way
  the source describes its own series: one reading per poll, and a plain mean of the polls centred on each day.
  The check is 2016 built the same way against the source's 2016 rows. Over the whole campaign ours is 0.5 point
  more Democratic on average, and the two differ by 2.0 points on a typical day and 1.6 by week. In the last 150
  days the average gap is 0.1 point and the typical day's 1.9. They draw on different sets of polls (1,106 against
  816). So 2020 is comparable on average and noisier day to day than a like-for-like series would be.
  That check covers how polls are dated and averaged. It does not test which question is taken from a poll that
  asked several, because every 2016 poll in the repo has one. In 2020, taking every question instead moves the
  weekly series by 0.1 point on average and by 1.1 in the worst week.

Still not in the repo: candidate favourability (DA-9).

**Presumptive rule (confirmed 2026-11-20).**

- A nominee is presumptive from the day news delegate counts gave them a majority of the convention's delegates.
  Where sources give different days for that, the latest is used. The convention's roll call is not such a day.
- A sitting president whom no rival took delegates from is presumptive throughout. Reagan in 1984 is the one case;
  no count day was found for him, and the table carries the first contest as a placeholder.
- Where a rival with a large share of the delegates fought on after that day, the table also records the day the
  rival stopped: Kennedy in 1980, Hart in 1984, Jackson in 1988, Brown in 1992, Clinton in 2008, Sanders in 2016.
- In 2028 the forecast starts on the later of the two parties' days, and waits for a rival who is still
  contesting. That is what "late when in doubt" means here.
- In the backtest, an election is scored at a test date if both nominees had their majority by then. All 11
  elections from 1980 to 2020 qualify at 150 days, but narrowly: in seven of them the majority came 151 to 155
  days out (151 in 2020). The polls of the eventual matchup exist in every one.
- The stricter reading, which also waits for the rival, would score 6 of 11 at 150 days and 10 of 11 at 100 (1980
  drops out: Kennedy withdrew 85 days before the election). It is reported beside the rule as a check. 1980 is
  the election the choice matters most for: Carter had his majority in June and Kennedy contested it to the
  convention, so it is scored at 150 and 100 days under the default and at neither under the stricter reading.

**Confirmed 2026-11-20.** Three things the decisions above imply, written first as assumptions and then confirmed,
with the two under them:

- How polls move over a campaign is learned on the national series and applied to the national part of every
  state. A state's own distance from the nation gets no separate rule for bounces or reversion: four elections of
  state polls cannot support one.
- Before both nominees are presumptive there is no forecast. That answers most of EC-8, which stays open for what
  the page shows in the meantime.
- A state where a third candidate polls in double digits still needs a rule (section 10).
- Until the fundamentals model exists (EC-3), the anchor is the president's approval plus the previous result.
- The three convention treatments are the ones listed in stage 2.

### Stage 1: pre-registration (written 2026-11-20, before any candidate run)

The harness is `src/model/pres_nowcast.py`. Only its baseline has been run.

**Test bed.** The repo's presidential polls, 2004 to 2020: states, the Maine and Nebraska districts, and the nation
(11,427 polls). Each poll contributes one question: the head-to-head question if the poll asked one, then the
likely-voter version, then voters, registered voters and adults. Its limits:

- 2000 is out: only the last 60 days are held, and there is no population field.
- 2004 has only late national polls, with no population field. A missing population is read as likely voters.
- 2012's national polls carry no head-to-head flag.
- 2016's 1,944 state subsamples of national online panels are left out, as the collector flags them.
- The partisan-sponsor flag exists only in 2020. The sponsor shift does nothing in the other cycles.
- Pollster names come from different sources by cycle, so pollster effects are estimated within a cycle only.
- 2024 is refused at load.

**Score (no candidate can move it).**

- The test runs each week from 161 days before the election. The polls that end in the next 7 days are that
  week's targets, so each poll is a target at most once.
- A target is a likely-voter (or "voters") poll with no sponsor flag, taken as published. Its prediction is the
  average at the start of its week, built only from polls that ended before then and without its own pollster's
  polls. Otherwise a pollster with overlapping field periods would predict itself, and short half-lives would win
  for that reason.
- A target counts if a different pollster polled the same place in the 60 days before. The target set is fixed
  before any candidate runs: 7,549 polls.
- Loss is the squared error in the two-party margin. It is averaged within each cycle and the cycles are weighted
  equally, because 2020 alone has more than twice the targets of any cycle before 2016. It is also reported for the
  nation and the states, and for three bands: 1 to 30, 31 to 90 and 91 to 161 days out.
- Each cycle's sampling variance of the targets is reported beside its loss. No average can remove it.

**Baseline: the Senate average's weighting, borrowed as it is.** Checks passed: it matches `pollavg.weighted_avg`
exactly on 25 random places and dates; moving every poll that ends on or after the date by 50 points leaves the
average unchanged in 40 random cases; and 2024 is refused at load.

- **60-day half-life.** Chosen on the 2018 and 2022 Senate backtest against results, over about the last 140 days.
  No decay at all was best there, by 0.12 points; 60 days was kept so the average still reacts to late shifts.
- **Population weights.** Registered voters 0.69, adults 0.5. From Senate and House polls of 2018 to 2024, against
  results.
- **Population lean.** Registered-voter and adult polls are moved 0.45 points toward the Democrat. This is paired
  likely-against-registered questions in generic-ballot, Senate and House polls of 2018 to 2024, updated with 2026's.
  It is a figure for midterms under a Republican president, which presidential years may not share.
- **Sponsor shift.** A flat 4.3 points.
- **Pollster weight.** Each pollster's weight is divided by the square root of its number of polls in the place.

None of these figures used presidential polls or results. Some of the inputs are 2024 Senate and House polls.

| | 2004 | 2008 | 2012 | 2016 | 2020 | Cycles equal |
|---|---|---|---|---|---|---|
| Targets | 1,098 | 1,181 | 939 | 1,562 | 2,769 | 7,549 |
| Loss (points squared) | 24.1 | 38.4 | 18.2 | 33.8 | 20.7 | **27.1** |
| Sampling part | 15.0 | 14.3 | 13.2 | 11.6 | 8.2 | |

By band the loss is 23.2 (1 to 30 days), 27.4 (31 to 90) and 35.5 (91 to 161). It is 19.2 for the nation and 28.4
for the states.

**Candidates.** Three, one per item the plan names. Each is run alone against the baseline. If more than one is
adopted, the combination is run and reported, but it is not a fourth candidate.

1. **Half-life.** Grid: 7, 10, 14, 21, 30, 45, 60 and 90 days. For each cycle, the value is the one with the lowest
   loss on the other four cycles, and it is scored on the held-out cycle. A value picked and scored on the same
   cycles is not a test.
2. **Pollster house effects, as of each date.**
   - Every poll's gap is its margin minus the baseline average of the other pollsters in the same place, as of
     the poll's end date.
   - A pollster's effect at date t is the mean of its gaps from polls that ended before t, in the same cycle,
     shrunk toward zero as gaps × k / (k + λ), where k is its number of polls.
   - The effect is subtracted from each of its polls in the average.
   - λ is chosen from 2, 5, 10, 20 and 50 on the other four cycles. No results are used.
   - The existing `pollster_effects.json` is not used: it was fitted on 2010 to 2022 polls, including the
     presidential polls scored here.
3. **Registered-to-likely correction re-estimated for presidential polls.**
   - Each registered-voter poll's gap is its margin minus the average of other pollsters' likely-voter polls in the
     same place, as of its end date.
   - The correction for a cycle is the mean of those gaps in the other four cycles, each cycle's mean weighted
     equally. It replaces the borrowed 0.45 for registered-voter and adult polls.
   - Paired questions (the same poll asked of both groups) exist only in 2020, in 1,653 polls. Their mean is
     reported as a check and not used.
   - The targets are likely-voter polls, so this candidate is judged on the quantity the forecast needs.

Anything that moves a state's polls using the national series belonged to stage 4 when this was written. After
round 1 it moved to stage 1 (round 2, candidate 5).

**Adoption rule for stage 1 (confirmed 2026-11-20, with the score).** A candidate is adopted if all four hold:

- its loss, with cycles weighted equally, is lower than the baseline's;
- it is lower in at least 4 of the 5 cycles;
- it passes a paired sign-flip test at 1 in 20, over place-and-cycle units with 2,000 flips. Each unit is the mean
  loss difference over that place's targets in that cycle, weighted as in the loss;
- it is not worse in the 91 to 161 day band, where the forecast's first test dates fall.

A sign test over five cycles alone cannot reach 1 in 20 unless all five agree. That is why the place-and-cycle test
carries the significance and the cycle count guards against one cycle driving the result.

If no candidate beats the baseline, a second round is run with different candidates (decided the same day). They
are written here before they run, under the same score and rule, and every round is reported.

### Stage 1, round 1: results (run 2026-11-20). None of the three is adopted.

**A correction to the harness, made after the first run.** The first run keyed pollsters by their full published
name. One firm then appeared under several names: SurveyUSA under each TV station that sponsored it, Rasmussen
alone and as "Fox News/Rasmussen", Gallup's tracking models. That weakens the rule that a target is predicted
without its own pollster, and it splits house effects. Pollsters are now keyed by the firm that fielded the poll
(the last part of the name). That gives 136 to 230 firms a cycle, where there had been 144 to 270 names. This
corrects the harness and is not a candidate. Both runs are reported below; the verdicts are the same.

| | Baseline loss | Half-life | House effects | Registered-voter correction |
|---|---|---|---|---|
| First run (published names) | 27.08 | gain 0.08, 3 of 5 cycles, p 0.13 | gain 0.03, 4 of 5, p 0.44 | gain −0.08, 3 of 5, p 0.92 |
| Corrected (firms), of record | 27.29 | gain 0.08, 3 of 5, p 0.13 | gain 0.10, 4 of 5, p 0.35 | gain −0.07, 3 of 5, p 0.89 |

The corrected baseline has 7,547 targets. Its loss is 23.3, 27.8 and 35.9 in the three bands, 19.3 for the nation
and 28.6 for the states.

**1. Half-life.** Fails: better in only 3 cycles, p 0.13. Gain in the 91 to 161 day band: 0.10.

| Half-life (days) | 7 | 10 | 14 | 21 | 30 | 45 | 60 | 90 |
|---|---|---|---|---|---|---|---|---|
| Loss, cycles equal | 29.07 | 28.66 | 28.35 | 28.00 | 27.70 | 27.42 | 27.29 | 27.21 |

Ninety days was picked for every held-out cycle, and 90 is the edge of the grid. The loss falls steadily from 7
days to 60 and barely moves after that (27.29 to 27.21). Short half-lives are clearly worse.

**2. Pollster house effects.** Fails: p 0.35, though better in 4 cycles, with a gain of 0.79 in the 91 to 161 day
band. (Found 2026-11-21: these figures leak. The own-firm test fails in 18 of 20; see "Who the score sees: results".
They are not rerun.)

- Every λ in the grid has a lower loss than the baseline over the five cycles: 26.71 at λ = 2 or 5, up to 26.85
  at 50, against 27.29. The held-out test fails because the cycles disagree on how strong the effects should be:
  the picks were 2, 2, 5, 2 and 50, the wrong end for both 2008 and 2020.
- Strong house effects (λ = 2) cut 2020's loss from 20.7 to 17.9 and 2012's from 18.5 to 17.5, but raised 2008's
  from 39.2 to 40.5.
- A plausible reason, not tested: in a fast-moving year like 2008, a poll's gap against the polls before it
  includes the movement since those polls, which a frequent pollster seems to carry as a house effect.
- A fixed λ chosen now would be chosen on these results, so none is.

**3. Registered-to-likely correction.** Fails: worse overall (−0.07) and worse in the 91 to 161 day band (−0.91).

- The cross-poll gap (registered-voter polls minus other pollsters' likely-voter polls) changes sign by cycle:
  −2.0 in 2004, +1.5 in 2008, +2.2 in 2012, −0.8 in 2016 and +2.0 in 2020. A constant learned from the other
  cycles cannot follow that.
- The 2020 paired questions (1,600 polls) put likely voters 1.46 points more Republican than registered voters
  (standard error 0.07). The borrowed correction moves registered-voter polls 0.45 toward the Democrat, which is
  the opposite direction in 2020. It stays in the baseline only because nothing passed.

Three candidates have been run for stage 1 so far.

**Diagnostic after round 1: the half-life depends on how densely a place is polled** (run 2026-11-21; not a
candidate; `pres_nowcast.py density`). The grid's loss, split by the nation and by the number of polls the place had
in the 30 days before the target's week:

| | Targets | 7 days | 14 | 30 | 60 | 90 | 180 | No decay |
|---|---|---|---|---|---|---|---|---|
| Nation | 1,866 | **19.07** | 19.31 | 19.32 | 19.26 | 19.29 | 19.39 | 19.81 |
| States, 10 or more polls | 2,730 | **19.11** | 19.18 | 19.37 | 19.55 | 19.74 | 20.10 | 20.95 |
| States, 4 to 9 polls | 1,579 | 30.13 | 29.05 | 28.42 | 28.03 | 27.88 | **27.78** | 28.16 |
| States, 1 to 3 polls | 1,372 | 50.45 | 48.05 | 45.59 | 43.97 | 43.43 | **43.07** | 43.47 |

Where polls are dense, a short half-life is best, as the published models find. Where they are sparse, a short
half-life leaves little more than the last poll, and its errors are large enough to decide the pooled score. So
the score is not at fault: one half-life for every place was the wrong shape of candidate. Published models also
carry old state polls forward by the national movement since they were taken, which this baseline does not do.

### Stage 1, round 2: pre-registration (written 2026-11-21, before any round 2 run)

Agreed with the user on 2026-11-21. Four candidates come from round 1's results and the diagnostic above, and two
are the user's (sample size and survey method). That makes nine candidates for stage 1 in all. The score, the
targets (the same 7,547) and the four clauses of the rule are unchanged. Grids are picked on the other four cycles
and scored on the held-out one, as in round 1. Each candidate is run alone against the baseline.

4. **Memory by poll count.** A poll's weight halves with every H firms that have published a newer poll of the same
   place before the date. A firm's own newer poll counts as one, and a daily tracker counts once however many polls
   it publishes. There is no decay by days. When a target is predicted without its own firm, the counts are taken
   again without that firm. Grid for H: 1, 2, 4, 8 and 16 firms.
5. **National trend adjustment.**
   - Each state or district poll is moved by the change in the national average between the poll's end date and the
     date of the forecast.
   - The national average is the baseline's, built from national polls that ended before each date. Where it
     cannot be built at either date, the poll is not moved.
   - National polls are not moved, and the nation's own average is the baseline's.
   - Grid, picked jointly: the national half-life for this trend line (7, 14, 30 days) and the state half-life
     (60, 90, 180 days).
   - 2004 is nearly inert: its national polls begin 61 days out. It counts in the 4-of-5 clause as it falls.
6. **House effects against polls of the same week.**
   - A poll's gap is its margin minus the mean of other firms' polls of the same place that ended within 7 days of
     it, either side. Only polls that ended before the date are used, so a poll's gap firms up as later polls
     arrive. That mean uses the baseline's weights without decay.
   - A firm's effect is the mean of its gaps in that cycle before the date, shrunk by gaps × k / (k + λ), where
     λ = σ² / τ²: σ² is the spread of gaps within firms and τ² the spread of firm means beyond it.
   - λ is estimated from the same cycle's gaps before the date, so nothing is picked from other cycles. Where fewer
     than 5 firms have two or more gaps, or τ² comes out at zero or below, every effect is zero.
7. **Weight by a poll's total expected error.** The baseline's square-root sample weight is replaced by
   1 / (s × τ² + 10,000 / n). Here 10,000 / n is the sampling variance of a two-party margin, in points squared, and
   τ² is the error that does not shrink with sample size. τ² is the intercept of a regression of squared gaps
   (round 1's gap against the other firms' average) on 10,000 / n, fitted on the other four cycles. There is no cap
   on n. Grid for s: 0, 0.5, 1, 2. At s = 0 the weight is in proportion to the sample, giving large polls more weight
   than the baseline does. At s = 1 or 2 a 1,500-person poll may get less extra weight over a 600-person one than
   the baseline's 1.58 times. So the grid tests both directions.
8. **Weight by survey method.**
   - **Source.** Each firm's main method in a cycle is taken from FiveThirtyEight's late-poll file (`raw_polls.csv`,
     read for the pollster, cycle and method only; it also carries results, which are not read).
   - **Classes.** Live phone, IVR (automated phone, alone or with text), online (opt-in and matched panels, online
     ads, text-to-web), probability panel, mixed (more than one of these), and unknown.
   - **Coverage.** The file records a method for about two thirds of its polls in 2004 to 2012 and for all of them
     in 2016 and 2020. Coverage of our polls is reported.
   - **Weights.** A method's weight is the spread of all gaps divided by the spread of that method's gaps, both
     measured on the other four cycles. Both are measured within the same density class, since gaps are larger
     wherever a place is thinly polled: 10 or more, 4 to 9, or 1 to 3 polls in the 30 days before the poll. The
     classes are then combined in proportion to the method's polls.
   - **Unknown.** A poll of unknown method, or a method with no polls in the other cycles, keeps a weight of 1.
9. **No registered-voter correction.** Registered-voter and adult polls are not moved; their 0.69 and 0.5 weights
   stay. Nothing is fitted.

**Mechanical checks before any result is read.**

- Each candidate passes its own leak test: moving every poll that ends on or after the date by 50 points, in every
  place of that cycle, leaves its predictions unchanged.
- The target set is still the 7,547.
- The baseline file is unchanged byte for byte.

**If more than one passes.**

- The passing candidates are combined. Candidate 5's adjustment works with either memory: with candidate 4's
  weights if candidate 4 passed, otherwise with its own half-lives. Candidates 6, 7 and 8 combine by multiplying
  their adjustments and weights. Each component keeps the grid value it was picked at alone.
- The combination must pass the same four clauses against the baseline.
- If it fails, the single passing candidate with the largest gain is adopted.
- If none passes, stage 1 keeps the baseline and says so.

### Stage 1, round 2: results (run 2026-11-21). None is adopted.

The checks passed before any result was read: each candidate's own leak test, the 7,547 targets, and a
byte-identical baseline file.

| Candidate | Gain | Cycles better | p (sign-flip) | Gain, 91 to 161 days | Verdict |
|---|---|---|---|---|---|
| 4. Memory by poll count | −0.09 | 2 | 0.61 | −1.07 | fails |
| 5. National trend adjustment (leaked; superseded by the corrected run below) | −0.01 | 2 | 0.51 | −0.06 | fails |
| 6. House effects, same week: first version (leaked; withdrawn) | +1.34 | 5 | 0.0005 | +2.22 | void |
| **6. House effects, same week: corrected, of record** | **+0.40** | **3** | **0.006** | **+1.22** | **fails** |
| 7. Weight by total expected error | −0.19 | 0 | 0.99 | −0.15 | fails |
| 8. Weight by survey method | +0.02 | 2 | 0.29 | −0.02 | fails |
| 9. No registered-voter correction | −0.02 | 3 | 0.68 | −0.26 | fails |

Gain is the baseline's loss minus the candidate's, cycles weighted equally (baseline 27.29).

**6. House effects against polls of the same week.**

*The first version leaked, and was withdrawn the same day.* It was first reported here as adopted. A review then
found that a target's own firm could reach its prediction. The target's polls are left out of the average, but
every other firm's house effect was still measured against all firms' polls, the target firm's included. So the
other firms' polls were pulled toward the target firm's. The leak test could not see this, because it moves only
polls after the date. A new test moves every poll by the target's firm in the cycle and checks the prediction does
not change: the first version fails it in 18 of 20 cases, the baseline and the corrected version pass. The
corrected version also divides a firm's weight in each same-week mean by the square root of its polls there, as
the baseline's weights do (the pre-registration said "the baseline's weights"; the first version left this out).
Most of the first version's gain was the leak.

*Corrected, of record.* Loss 26.89. It fails the rule on the cycle count alone:

| | 2004 | 2008 | 2012 | 2016 | 2020 |
|---|---|---|---|---|---|
| Baseline | 24.25 | 39.17 | 18.47 | 33.84 | 20.72 |
| Corrected | 24.26 | 37.77 | 18.13 | 34.00 | 20.32 |
| First version (void) | 23.51 | 37.67 | 17.58 | 32.45 | 18.52 |

- 2004 is worse by 0.01 and 2016 by 0.16, so it is better in 3 cycles, not 4. The sign-flip test (p 0.006) and
  the early band (+1.22) pass.
- It helps the nation (19.26 to 19.13) and the states (28.64 to 28.28). By band: 23.3 to 23.1, 27.8 to 27.6, and
  35.9 to 34.7.
- Robustness figures, not part of the rule:
  - The gain does not come only from the big trackers. By the size of the target's firm: 0.66 for firms with 1 to
    9 polls in the cycle, −0.09 for 10 to 49, and 0.55 for 50 or more.
  - A sign-flip over firm-and-cycle units (672) gives p 0.025.
- Effects could be estimated on all 115 target dates.
- The estimates (first version, which differ little firm by firm) look like the known ones. A week before the 2016 election the USC Dornsife/LA Times tracker sat 6.9
  points more Republican than other firms' polls of the same week, and Ipsos 4.3 more Democratic. In 2020
  Rasmussen was 3.4 more Republican and Quinnipiac 4.2 more Democratic.
- Round 1's house effects compared each poll with the polls before it. Comparing it with polls of the same week
  turns 2008's loss into a gain (39.17 to 37.77). That fits round 1's reading: movement was being taken for house
  effects.

**The others.**

- **Memory by poll count.** The cycles disagree on H (2008 wants 2 firms, 2020 wants 16). The picks were mostly 4,
  and that loses in 2016 and in the early band.
- **National trend adjustment.** It has a leak of the same kind: the national trend line includes the target
  firm's national polls, and the own-firm test fails in 8 of 20 cases. This run also gave the nation the state
  half-life, where the pre-registration kept the nation's average at the baseline's. Both are corrected below
  ("Who the score sees: results"); the corrected run also fails. 2008 gains a lot: 39.17 to 33.07 with a 7-day national trend line. That is the
  autumn the financial crisis moved every state at once. But it loses in 2004, 2012 and 2016, where moving state
  polls by a noisy national line adds more error than it removes. It is not adopted here. Its natural test is
  stage 4, in states with no recent poll, which stage 1's targets rarely reach (see "Who the score sees", below).
  It also bears on the durability questions of stage 3.
- **Weight by total expected error.** The error that does not shrink with sample size is large: 15 to 20 points
  squared, against 17 for the sampling variance of a 600-person poll. So larger samples deserve little extra weight.
  Weighting in proportion to sample size (s = 0) is worse in 2012 and 2020. The baseline's square root is a fair
  middle.
- **Weight by survey method.** Method was known for 50 to 74 per cent of polls. In the other cycles, IVR polls sat
  about as far from other firms' polls as live-phone polls did: weights of 0.98 to 1.11 for IVR and 0.90 to 1.06 for
  live phone. Mixed-mode polls and probability panels got more weight (1.2 to 1.6, and 1.1 to 2.3), but they are few. The
  weights hardly moved the average. This measures distance from other polls, not accuracy against results.
- **No registered-voter correction.** It is neither better nor worse to within noise. The borrowed 0.45 stays, as
  the baseline's.

**Stage 1 result after round 2.** No candidate passes, so the nowcast is still the baseline: the Senate average's
weighting. Under the user's decision of 2026-11-20 a further round with different candidates follows, written here
before it runs. Corrected same-week house effects came closest (p 0.006, but 3 cycles of 5).

### Who the score sees, and the national trend's leak (written 2026-11-21, before either is run)

**What prompted this.** The user pointed out on 2026-11-21 that a national trend adjustment should matter most in
thinly polled states, and those rarely produce a target. A count, made with no candidate's predictions:

| Polls in the place in the prior 30 days | Place-weeks with an average | Has a target | New polls, none eligible | No new poll |
|---|---|---|---|---|
| 0 | 1,133 | 77 | 147 | 909 |
| 1 to 3 | 2,788 | 865 | 187 | 1,736 |
| 4 to 9 | 1,155 | 772 | 62 | 321 |
| 10 or more | 550 | 536 | 6 | 8 |
| All | 5,626 | 2,250 | 402 | 2,974 |

Places with 10 or more polls in the past month give 61% of the 7,547 targets; places with 0 to 3 give 18%. 30 of
the 264 place-cycles with polls have no target at all. The user decided the same day: report every candidate's
loss by density (below), and leave thin states to stage 4 (amended above). The stage 1 score is not changed.

**A diagnostic, not a candidate: loss by density.**

- Every target is put in one class: the nation; or a state or district by the number of polls of that place in the
  30 days before its week starts, not counting the target's own firm (the prediction does not use that firm
  either): 10 or more, 4 to 9, 1 to 3, or 0.
- For each candidate run so far, the loss in each class: cycles weighted equally, with the number of targets in
  every cycle and class shown, and the gain against the baseline.
- Candidates are rebuilt at the grid values already picked for each held-out cycle. Before any split is read, the
  rebuilt per-cycle losses must match the stored ones to three decimals.
- The first version of same-week house effects (void) is left out. Every candidate in the table gets the own-firm
  test; round 1's house effects have never had it, and a failure is marked in the table, not rerun.
- No cell passes or fails a candidate, and no verdict changes. With about ten candidates and five classes, some
  cells will look good by chance. The 0 class is small (about 90 targets over five cycles).
- It sees only thin-place targets that exist, that is, weeks when a thin place did get a new eligible poll. The
  2,974 weeks with no new poll stay unseen. The split is a hint; stage 4 is the test.

**The national trend adjustment, corrected (candidate 5).** As with same-week house effects, this corrects a
leak and is not a new candidate.

- The national trend line used for a target leaves out the target's own firm's national polls. Where that firm
  has no national polls in the cycle, the prediction is the same as before, which is checked.
- Before results are read: the own-firm test passes in 20 of 20, and the leak test passes.
- The full grid (national half-life 7, 14, 30; state half-life 60, 90, 180) is run again and picked again on the
  other four cycles. The old picks were chosen on leaking losses.
- The corrected run is of record under the same four clauses. The round 2 verdict stands until it is in.
- **The trend's part, apart from the longer memory.** The trend's picks pair it with a 90- or 180-day state
  half-life, and the density diagnostic already showed thin places prefer 180 days without any trend. So beside
  the corrected run, the table shows a run with each cycle's picked state half-life and the trend turned off. The
  trend's own contribution is the difference between those two, class by class. This row is a diagnostic and
  passes or fails nothing.

### Who the score sees: results (run 2026-11-21)

**Checks, before any figure below was read.**

- Corrected trend: the leak test passes, and the own-firm test passes in 20 of 20 (the first version fails in 8 of
  20). Where the target's firm has no national polls, the corrected and first versions agree (largest difference
  7e-15 over 300 targets).
- Every candidate in the table, rebuilt at its stored picks, matches its stored per-cycle losses to three decimals.
- Own-firm test, 20 targets each: every candidate passes except **round 1's house effects, which fail in 18 of
  20**. Candidates 3, 7 and 8 pass by construction: they are fitted on the other four cycles, and the test moves
  only the target's cycle, so their settings were not refitted for it. They compare each poll with other firms' earlier polls, and those other firms' effects were measured
  against the target firm's polls too: the same leak as the first version of same-week house effects. They failed
  the rule even with that help, so they are not rerun. Their row below leaks.

**The national trend adjustment, corrected, of record. Fails.**

| | Gain | Cycles better | p (sign-flip) | Gain, 91 to 161 days |
|---|---|---|---|---|
| Round 2 run (leaked; nation given the state half-life) | −0.01 | 2 | 0.51 | −0.06 |
| Own firm left out, nation still given the state half-life | −0.02 | 2 | 0.53 | −0.19 |
| **Corrected, of record: own firm left out, nation at the baseline** | **+0.03** | **2** | **0.43** | **−0.27** |

- A second fault was found after the first corrected run, by the density table: the nation's targets lost 0.19.
  The code gave national polls the state half-life (90 or 180 days), where the pre-registration says the nation's
  own average is the baseline's. The run of record follows the pre-registration. The run before it is kept
  (`pres_nowcast_trend_corrected_nation_moved.json`), and the verdict is the same either way.
- Picks, unchanged: national 7 days with state 180 (2004, 2016) or 90 (2012, 2020); national 30 with state 180
  (2008).
- By cycle against the baseline: 25.10 against 24.25, 36.98 against 39.17, 19.30 against 18.47, 34.23 against
  33.84, and 20.67 against 20.72. 2008 gains 2.2; 2004, 2012 and 2016 lose.

**Loss by density.** Classes count the polls of the target's place in the 30 days before its week, without the
target's own firm. Cycles weighted equally within each class.

Targets per class and cycle (the 0 class is 215 here, not the "about 90" written beforehand, because the
target's own firm is now left out of the count):

| | 2004 | 2008 | 2012 | 2016 | 2020 |
|---|---|---|---|---|---|
| Nation | 141 | 203 | 151 | 726 | 645 |
| State, 10+ polls | 196 | 314 | 353 | 289 | 928 |
| State, 4 to 9 | 409 | 283 | 231 | 256 | 470 |
| State, 1 to 3 | 314 | 346 | 178 | 262 | 637 |
| State, 0 | 38 | 33 | 26 | 29 | 89 |

Baseline loss: 19.26 (nation), 17.39 (10+), 25.80 (4 to 9), 40.96 (1 to 3), 53.62 (0). Gain against the baseline
(positive is better):

| Candidate | Nation | 10+ | 4 to 9 | 1 to 3 | 0 |
|---|---|---|---|---|---|
| 1. Half-life (90 days) | −0.02 | −0.23 | +0.04 | +0.48 | +1.08 |
| 2. House effects, round 1 (leaks) | −0.07 | −1.15 | +0.08 | +0.53 | +2.80 |
| 3. Registered-voter correction | −0.05 | −0.13 | −0.09 | +0.02 | −0.48 |
| 4. Memory by poll count | −0.69 | −0.33 | −0.01 | +1.18 | +1.90 |
| 5. National trend, corrected | 0.00 | −0.60 | +0.15 | +0.31 | +2.41 |
| 5, control: same state half-life, no trend | 0.00 | −0.63 | −0.09 | +0.48 | +1.50 |
| 5, the trend's own part (5 minus control) | 0.00 | +0.04 | +0.24 | −0.17 | +0.91 |
| 6. House effects, same week, corrected | +0.14 | −0.29 | +0.42 | +0.72 | +2.49 |
| 7. Weight by total expected error | −0.22 | −0.17 | −0.51 | +0.03 | +0.18 |
| 8. Weight by survey method | −0.02 | +0.03 | +0.05 | +0.08 | +0.04 |
| 9. No registered-voter correction | −0.02 | −0.08 | −0.04 | +0.07 | −0.03 |

What it shows, as a hint and not a verdict:

- **What helps thin places hurts dense ones.** Slower forgetting (1, 4 and the trend's half-lives) gains 0.5 to 1.9 in
  places with 0 to 3 recent polls and loses 0.2 to 0.6 where there are 10 or more. In this table's classes, states
  with 10 or more polls give 2,080 targets (28%) and the nation 1,866 (25%), against 1,952 (26%) for states with 0
  to 3. The thin gains are larger per target, but they are cancelled in the overall score. This is the density diagnostic's
  finding again, now for every candidate.
- **The trend adds little beyond the longer memory it brings.** Against the control with the same half-life, the
  trend itself gains 0.91 in the 0 class, 0.24 at 4 to 9, and loses 0.17 at 1 to 3. By cycle, its part in the 0
  class is −0.86, +2.30, +3.24, −1.86 and +1.71 (2004 to 2020), on 26 to 89 targets a cycle; at 1 to 3 it is
  −0.23, +3.26, −2.20, −1.96 and +0.29. 2008 gains in every class (+3.0 to +3.3); the other cycles split.
- **Corrected same-week house effects are the only candidate with a real gain in the nation (+0.14).** They also
  gain in every state class except the dense one (−0.29).
- The weight changes (7, 8) and the registered-voter changes (3, 9) barely move any class.
- Over fifty cells were read. Some will look good by chance, and no cell passes or fails anything. The 2,974 weeks
  with no new poll remain unseen; stage 4 is the test for thin states.

**Stage 1 after this.** Unchanged: no candidate passes, and the nowcast is the baseline. A third round follows,
written here before it runs.

### How good is the baseline: naive benchmarks (written 2026-11-21, before any run)

Asked by the user on 2026-11-21: nothing beats the baseline, but how good is it? The Senate average's settings
were tested across half-lives against results (2018 and 2022); no comparison with a naive average was found. So
the presidential baseline is compared with three naive averages, each with no free parameter and no grid.

**The floor first** (from the stored baseline file, no new run). Of the baseline's 27.29, 12.47 is the sampling
variance of the target polls themselves, which no average can remove; 14.82 is beyond it. By cycle the part
beyond sampling is 9.3, 24.9, 5.2, 22.2 and 12.5. This is a lower bound on what is irreducible: it assumes simple
random samples, and a missing sample size is taken as 600. So a gain of 0.40 is about 3% of the reducible part.

**The benchmarks.** Same 7,547 targets, same score, polls that ended before the week, the target's own firm left
out. Margins are taken raw: the poll's chosen question as it is, any population, no registered-voter lean, no
sponsor shift, no weights.

- **N1. Latest poll.** The most recent poll of the place by another firm. If several end on that day, their plain
  mean.
- **N2. Latest five firms.** Each other firm's latest poll of the place (several on its latest day are averaged
  into one reading). The five firms whose latest readings are most recent, with every firm tied at the fifth
  date included, or all of them if fewer than five. The plain mean of those readings. This is the familiar
  "latest poll from each firm" average, with a fixed count and no time window.
- **N3. Every poll so far.** The plain mean of every poll of the place in the cycle by other firms, each poll
  counted once (so a daily tracker counts every day).

**Checks before any result is read.** Each passes the leak test and the own-firm test (20 each), and the baseline
file is unchanged byte for byte.

**What is reported.** For each benchmark: the loss overall, by cycle, by band, for the nation and the states, and
by density class; and the baseline against it under the four clauses of the stage 1 rule (gain, cycles better,
sign-flip p, the 91 to 161 day band).

**If a benchmark beats the baseline.** It is reported as such under the same four clauses. Whether it replaces the
baseline is the user's decision; it would enter round 3 as a candidate. Benchmarks are not candidates and do not
count among the nine. A benchmark that wins in one density class is a hint for round 3, not a verdict. A previous
election's result would make a fourth benchmark but would bring results into stage 1, so it is left out unless the
user asks.

### Naive benchmarks: results (run 2026-11-21)

The checks passed before any loss was read: each benchmark passes the leak test (15) and the own-firm test (20),
and the baseline file is unchanged byte for byte.

| | Loss | 2004 | 2008 | 2012 | 2016 | 2020 | Nation | States | 91 to 161 days |
|---|---|---|---|---|---|---|---|---|---|
| **Baseline** | **27.29** | 24.25 | 39.17 | 18.47 | 33.84 | 20.72 | 19.26 | 28.64 | 35.9 |
| N1. Latest poll | 36.58 | 35.02 | 50.14 | 26.58 | 43.11 | 28.05 | 22.28 | 40.04 | 49.9 |
| N2. Latest five firms | 27.54 | 25.64 | 34.70 | 20.05 | 35.72 | 21.60 | 20.38 | 28.82 | 37.4 |
| N3. Every poll so far | 29.60 | 26.90 | 47.03 | 17.77 | 36.36 | 19.94 | 20.91 | 30.66 | 40.8 |

The baseline against each, under the four clauses (gain is the benchmark's loss minus the baseline's):

| | Gain to the baseline | Cycles the baseline is better | p (sign-flip) | Gain, 91 to 161 days |
|---|---|---|---|---|
| N1. Latest poll | 9.29 | 5 | 0.0005 | 14.05 |
| N2. Latest five firms | 0.25 | 4 | 0.29 | 1.46 |
| N3. Every poll so far | 2.31 | 3 | 0.0005 | 4.85 |

No benchmark passes the rule against the baseline. Loss by density:

| | Nation | 10+ | 4 to 9 | 1 to 3 | 0 |
|---|---|---|---|---|---|
| Baseline | 19.26 | 17.39 | 25.80 | 40.96 | 53.62 |
| N1. Latest poll | 22.28 | 26.18 | 37.92 | 53.46 | 75.48 |
| N2. Latest five firms | 20.38 | 17.01 | 26.61 | 41.09 | 53.79 |
| N3. Every poll so far | 20.91 | 20.67 | 27.80 | 41.70 | 52.78 |

What it shows:

- **The baseline is clearly better than the latest poll** (by 9.3, every cycle) **and than a plain mean of every
  poll** (by 2.3, p 0.0005, though that mean is better in 2012 and 2020).
- **It is not clearly better than the latest poll from each of the last five firms.** The gap is 0.25 and not
  significant (p 0.29), though the baseline is better in 4 cycles and early in the year (1.46). For scale, the
  reducible part of the loss is about 14.8 (see the floor above).
- **2008 is where it falls short.** The five-firm mean beats the baseline by 4.5 in 2008 (34.70 against 39.17):
  by 8.1 in densely polled states, 5.0 in thin ones, and 1.3 in the nation. In every other cycle the baseline is
  better in most classes. The baseline's 60-day memory is slow for a year when the race moved, which round 1's
  half-life grid and round 2's trend run both pointed at.
- The five-firm mean is close to a memory that adapts to density without being told to: where polls are dense,
  the latest five firms are all recent; where they are thin, it reaches back as far as it must. It is better than
  the baseline only in the dense class (17.01 against 17.39), and that is 2008 alone.
- For the nation the baseline is better than all three (19.26 against 20.38 at best).

This is a benchmark, not a candidate, and nothing changes. Whether a five-firm style average, or an adaptive
memory like it, enters round 3 is the user's decision.

### Stage 1, round 3: pre-registration (written 2026-11-21, before any round 3 run)

Agreed with the user on 2026-11-21: round 3 tests a memory that adapts to how densely a place is polled, in the
two forms below, and then the work moves to stage 2. **Round 3 is the last round of stage 1, whatever it shows.**
If nothing passes, the nowcast is the baseline and is fixed; if one passes, it is fixed as the nowcast. That makes
eleven candidates for stage 1 in all. The score, the 7,547 targets and the four clauses are unchanged. Grids are
picked on the other four cycles and scored on the held-out one. A pick at the edge of a grid is reported.

**Where the idea came from.** The density diagnostic, the loss-by-density table and benchmark N2 all used all five
cycles. Leaving one cycle out protects the grid values only, not the idea, the 30-day window or the form of each
candidate. That limits what a pass can claim.

10. **Latest k firms.**
    - Each other firm's reading is its poll (or the weighted mean of its polls) of the place on its latest end date
      before the forecast date, after the baseline's population lean and sponsor shift.
    - The k firms whose readings are most recent are used. Every firm tied at the k-th date is included, or all
      firms if there are fewer than k.
    - The average is the mean of those readings, weighted by the baseline's sample-size and population weights
      (a reading with several polls takes their mean weight). There is no decay by age, and no division by a firm's
      poll count, since each firm gives one reading.
    - The nation follows the same rule as every other place.
    - Grid for k: 2, 3, 5, 8, 12, 20. Unlike N2, this keeps the baseline's adjustments and weights.
11. **Half-life by density.**
    - The baseline, except that each place's half-life depends on how many polls of that place ended in the 30 days
      before the forecast date, not counting the target's firm (the prediction does not use that firm either).
    - At D polls or more, the half-life is h_dense; below D, h_sparse.
    - The nation is counted the same way; in practice it is almost always dense.
    - Grid, picked jointly: h_dense 7, 14, 30; h_sparse 60, 90, 180, 365; D 4 or 10.

**Checks before any loss is read.** Each candidate, and the baseline:

- passes the leak test and the own-firm test as before (moving margins by 50 points);
- passes two deletion tests, since both candidates depend on which polls exist and when, which moving margins
  cannot reveal: deleting every poll that ends on or after the date (all places, same cycle), and deleting every
  poll by the target's firm in the cycle, each leaves the prediction unchanged.

The baseline file must stay unchanged byte for byte.

**If both pass.** Both replace the memory, so they cannot be combined: the one with the larger gain is adopted.
Corrected same-week house effects failed and are not combined with either.

**Reported.** The four clauses, the picks by cycle, the loss by density, and each candidate beside N2.

### Stage 1, round 3: results (run 2026-11-21). Neither is adopted.

The checks passed before any loss was read. Both candidates and the baseline pass the leak test, the own-firm test
and both deletion tests. Each candidate's grid path matches its per-target path exactly. The baseline file is
unchanged byte for byte.

| Candidate | Loss | Gain | Cycles better | p (sign-flip) | Gain, 91 to 161 days | Verdict |
|---|---|---|---|---|---|---|
| 10. Latest k firms | 26.90 | +0.39 | 2 | 0.16 | +0.21 | fails |
| 11. Half-life by density | 27.35 | −0.06 | 2 | 0.62 | −1.46 | fails |

| | 2004 | 2008 | 2012 | 2016 | 2020 | Nation |
|---|---|---|---|---|---|---|
| Baseline | 24.25 | 39.17 | 18.47 | 33.84 | 20.72 | 19.26 |
| 10. Latest k firms | 24.68 | 35.77 | 19.31 | 34.21 | 20.53 | 18.67 |
| 11. Half-life by density | 24.64 | 38.59 | 18.33 | 34.26 | 20.95 | 19.60 |
| N2. Latest five firms (benchmark) | 25.64 | 34.70 | 20.05 | 35.72 | 21.60 | 20.38 |

**10. Latest k firms.** Fails on cycles (2 of 5) and p (0.16).

- k = 20 was picked for every held-out cycle, the top of the grid. The loss was still falling at 20 in 2004, 2012
  and 2016, so a larger k might do better there; the grid is not widened after the run.
- 2008 wants fewer firms (8 is best there, 34.79), the other cycles more. That is the same disagreement as every
  memory candidate.
- It beats the baseline for the nation (18.67 against 19.26) and slightly in every state class (17.27, 25.66,
  40.69 and 53.38, against 17.39, 25.80, 40.96 and 53.62). It loses in 2004, 2012 and 2016.
- Keeping the baseline's adjustments and weights helps: it beats N2 (the raw five-firm mean) in every cycle but
  2008.

**11. Half-life by density.** Fails on every clause but none by much.

- Picks: D = 10 every time (never 4), with 7 days for dense places (30 in 2008) and 180 or 365 for sparse ones. Every cycle has a pick at a grid edge (7 or 365).
- It gains where places are thin (1 to 3 polls: 40.26 against 40.96; 0: 51.84 against 53.62) but loses in dense
  states and the nation, where the 7-day half-life picked on the other cycles is too short for 2008 and the 30-day
  one too long for the rest. Early in the year it is worse (−1.46).
- Checked by hand, because the nation's 19.60 is worse than the 19.07 the density diagnostic found at 7 days: the
  difference is 2008, held out with 30 days (18.82 against 16.14 at 7). Not a fault.

### Stage 1 closed (2026-11-21)

Eleven candidates in three rounds. None passes the rule. **The nowcast is the baseline**, the Senate average's
weighting applied to presidential polls, and it is fixed for the later stages:

- 60-day half-life; sample-size weight sqrt(min(n, 3000) / 600); population weights 1 (likely voters, "voters"),
  0.69 (registered), 0.5 (adults); each firm's weight divided by the square root of its polls in the place;
- registered-voter and adult polls moved 0.45 toward the Democrat; the flat 4.3-point sponsor shift;
- pollsters keyed by fielding firm.

What stage 1 found, for later stages and for 2028:

- The baseline is clearly better than the latest poll and than a plain mean of every poll, but not clearly better
  than a latest-five-firms mean. About 12.5 of its 27.3 is sampling noise in the target polls.
- The right memory depends on how fast the race is moving, and 2008 disagrees with the other four cycles about it
  every time. A fixed rule cannot know in advance. This bears on stage 3 (reversion and trend).
- Thinly polled places gain from longer memory; stage 1's score barely sees them, and stage 4 tests them against
  results.
- Corrected same-week house effects came closest (p 0.006, 3 cycles of 5).

Open, carried forward:

- The registered-voter lean (0.45 toward the Democrat) stays in the nowcast, though the 2020 paired questions put
  likely voters 1.46 more Republican than registered voters, the opposite sign.
- Pollster quality gets its own test (decided 2026-11-21): grades as they stood, fit on 2016 and 2020 and tested
  on 2024. How that spends the 2024 holdout is still to be settled.

### Pollster quality: a separate test (pre-registration, written 2026-11-21, before any run)

Decided with the user on 2026-11-21. It does not fit stage 1: 538's ratings are built from accuracy against
results, so they are tested against results, and the only ratings that existed before an election are for 2016,
2020 and 2024. It is a detour from the stages, not a stage, and it is the one use of 2024 in this section.

**Ratings as they stood**, from 538's public repository: the last version committed before each election. That is
30 July 2016 (commit f2c6f781a6, `pollster-ratings-2016.csv`), May 2020 (commit 7b6455abc3,
`pollster-ratings-2020.csv`; its latest poll is from March 2020) and 13 September 2024
(`pollster-ratings-combined.csv`, fetched 2026-11-01; the last change to that file). The 2016 and 2020 files are
byte-identical to the copies 538 later archived in its `2016` and `2020` folders. Each is built from earlier elections, so applying it to every
poll of its year leaks none of that year's general-election results. No version predates 2004, 2008 or 2012, so
those years are not used.

- **The measure:** 538's error score, lower is better: predictive plus-minus in 2016 and 2020, POLLSCORE in 2024.
  The scales differ (SD 0.56 and 0.68 against 0.41), so each version is standardized across the firms it rates
  (mean 0, SD 1), giving z.
- **Matching:** 2020 and 2024 polls carry 538's pollster rating id. 2016 polls come from 538's forecast file and
  are matched by exact name. Coverage, counted before any margin was read: 81% of 2016 polls, 91% of 2020, 82% of
  2024. Most unmatched 2016 polls are firms 538 had not rated yet (USC Dornsife/LA Times, Lucid, Morning Consult). A
  looser search of the 2016 file for the 15 most common unmatched names found no variant spellings.
  Firms 538 had banned keep their score.

**Polls.** Those of stage 1's loader: one question per poll, two-party margins, the same adjustments. 2024 uses
Harris against Trump only, from polls that ended on or after 21 July 2024, the day Biden withdrew. Maine's and
Nebraska's districts are left out, since the repo has no results for them.

**The candidate.** Each poll's baseline weight is multiplied by exp(−γ × z) for its firm. An unrated firm gets z_u
in place of z. Everything else is the fixed nowcast.

- Grid: γ 0, 0.1, 0.2, 0.35, 0.5, 0.75, 1; z_u 0 (an average firm), 0.5 or 1 (half or one SD worse). At γ = 0
  every factor is 1, so all three γ = 0 cells are the baseline and count as one. The unrated weight is tied to γ:
  it cannot down-weight unrated firms on its own.
- Fitted on 2016 and 2020 together: the lowest loss at 7 days, cycles weighted equally.

**The score.** At 7 days before the election (30 and 60 days reported), each place's average from polls that ended
before that date, against its result (two-party margin). Places are the 50 states, DC and the nation, wherever at
least one poll ended before the date. Loss is the mean squared error over places; the nation is also reported
alone.

Polls in 2016 and 2020 missed in the same direction across most states, so a fit against results on those two
years can learn which firms leaned the right way that year rather than which were better. The raw loss decides.
Beside it, every loss (fit and 2024) is also reported with each year's mean error removed, as the Senate half-life
test did.

**2024.**

- 2024 is opened only if the picked setting is not the baseline and its 7-day loss is lower than the baseline's
  in 2016 and in 2020, each on its own. Otherwise the test ends with the baseline kept, and 2024 stays closed.
  (Without that second condition the gate would nearly always open: one of 18 alternatives will beat the baseline
  in-sample by chance.)
- If it opens, the picked setting is run on 2024 once. It passes if, at 7 days, its loss is lower than the
  baseline's and a paired sign-flip test over places (2,000 flips) gives p < 0.05. 30 and 60 days are reported.
- Places in one year share most of their error, so a sign-flip over places overstates the evidence. A pass would
  rest on one election.
- If it passes, the user decides whether it joins the nowcast. If it fails, the baseline stands. Nothing is refitted
  after 2024 is seen.

**Checks before any loss is read:** the leak test (moving polls that end on or after the date leaves the average
unchanged), and γ = 0 reproducing the baseline average exactly. The fit on 2016 and 2020 is written here and
committed before any code reads a 2024 margin or result. The 2024 loader checks the Harris-Trump matchup and the
21 July cutoff, and stage 1's refusal of 2024 stays in place.

**Where this differs from what the user approved on 2026-11-21:** the gate (when 2024 is opened) is added, and the
unrated weight is tied to γ. The fit and the pass are at 7 days, with 30 and 60 days reported, as approved.

### Pollster quality: the fit on 2016 and 2020 (run 2026-11-21, before 2024 was opened)

`src/model/pres_quality.py fit`, `data/processed/pres_quality_fit.json`. Checks passed first: the leak test, and
γ = 0 reproducing the baseline average exactly. Rated share of polls: 81% (2016), 91% (2020). Places: 50 in 2016
and 52 in 2020 at 7 days.

**Picked: γ = 0.35, z_u = 1** (an unrated firm is treated as one SD worse than the average rated firm). Neither is
at a grid edge for γ; z_u is at its edge (1). A firm one SD better than average gets exp(0.35), about 1.4 times the
weight of an average firm, and one SD worse about 0.7 times.

| 7 days out | 2016 | 2020 | Fit score |
|---|---|---|---|
| Baseline | 66.60 | 51.75 | 59.17 |
| γ 0.35, z_u 1 | 65.76 | 50.73 | 58.24 |
| With the year's mean error removed: baseline | 35.17 | 22.23 | |
| With the year's mean error removed: γ 0.35, z_u 1 | 33.97 | 22.14 | |

- It is lower than the baseline in 2016 and in 2020, so **the gate opens** and 2024 is run once at this setting.
- The gain survives removing each year's mean error (1.20 in 2016, 0.09 in 2020), so it is not only a matter of
  leaning the right way. In 2020 it is almost all lean.
- **Warnings, reported and not part of the gate:**
  - At 30 and 60 days it is worse in 2020, by a lot (28.44 to 35.24, and 28.68 to 33.08), and worse in 2016 at
    60 days (70.98 to 72.92). It is better in 2016 at 30 days (63.41 to 61.97).
  - The nation is worse at 7 days in both years: its squared error goes from 7.11 to 9.66 (2016) and from 22.74 to
    23.77 (2020).
  - The grid is smooth: every γ from 0.1 to 0.5 beats the baseline at 7 days in both years. γ = 0.75 or more is
    worse.

### Pollster quality: 2024 (run once, 2026-11-21). It passes.

`src/model/pres_quality.py test2024`, `data/processed/pres_quality_2024.json`. The fit was committed first; the run
refuses otherwise. 2024 polls: Harris against Trump, ending on or after 21 July; 82% of them rated.

| 2024 | Places | Baseline | γ 0.35, z_u 1 | Gain | p (sign-flip) | Mean error removed: baseline | candidate |
|---|---|---|---|---|---|---|---|
| **7 days** | 45 | 39.88 | 38.00 | **+1.88** | **0.0085** | 16.19 | 15.61 |
| 30 days | 42 | 46.71 | 46.02 | +0.69 | 0.12 | 22.78 | 22.51 |
| 60 days | 32 | 44.32 | 45.21 | −0.89 | 0.93 | 33.51 | 33.85 |

- **At 7 days it passes both clauses:** lower loss, and p 0.0085.
- **Most of the gain is a shared shift, not better accuracy state by state.** Each loss is the within-year part
  plus the square of the mean error. The 7-day gain splits as follows:

  | Year | Gain | Within-year part | Shift of the mean error | Mean error, baseline to candidate |
  |---|---|---|---|---|
  | 2016 (fit) | 0.84 | 1.20 | −0.36 | 5.61 to 5.64 |
  | 2020 (fit) | 1.02 | 0.10 | 0.92 | 5.43 to 5.35 |
  | 2024 (test) | 1.88 | 0.57 | 1.31 | 4.87 to 4.73 |

  In 2024 about 70% of the gain is the average moving 0.14 point toward the Republican in a year the polls missed
  toward the Democrat. The rest (0.57) is real accuracy across states. p was computed on the raw loss, so it
  mostly reflects that shared shift. No test of the within-year part alone was written beforehand, and none is
  added now.
- **The nation improves** at every date: its squared error goes from 17.07 to 15.83 at 7 days.
- **The average still missed toward the Democrat by about 4.8 points across places.** Quality weighting moves that
  by 0.1; it is not a fix for a shared miss.
- **The caveats:**
  - One election.
  - Places share most of their error, so p overstates the evidence.
  - It is worse at 60 days in 2024, and at 30 and 60 days in 2020.
  - The unrated weight is tied to γ.

**Whether it joins the nowcast is the user's decision.** Two things bear on that:

- **Where the gain is.** At 7 days it was chosen on 2016 and 2020, so only 2024 is out of sample there. It is mixed
  at 30 days and worse at 60 in all three years. So it may belong only close to the election, or be tied to how
  far out the date is. That would be a new candidate, not this one.
- **What adoption would touch.** Ratings as they stood exist only for 2016, 2020 and 2024, while stage 4 and EC-7
  also score 2008 and 2012, so a quality weight could not be applied the same way there. And stage 1 fixed the
  nowcast; adopting this would amend that.
- **2028 needs a source of ratings.** 538 stopped publishing in 2025, and its last ratings are those of September
  2024. Using them in 2028 means ratings four years old, with every firm new since then unrated, or another rater
  if one is available, with its own scale. Either needs a check before it is relied on.

### Pollster quality: how stable are the ratings? (run 2026-11-21)

Asked by the user: in 2027 and 2028 the model would work from the September 2024 ratings unless newer ones turn up,
so how much do ratings change in four years? `pres_quality.py stability`, `data/processed/pres_quality_stability.json`.
No 2024 margin or result is read; 2024 polls are used only for which firm fielded them.

| | 2016 to 2020 | 2020 to 2024 |
|---|---|---|
| Firms rated in both versions | 318 | 419 |
| Correlation of z across firms, Pearson (Spearman) | 0.73 (0.69) | 0.55 (0.48) |
| Correlation across polls (each firm counted by its polls in the later year) | 0.93 | 0.57 |
| Later year's polls rated in the later version | 91% | 82% |
| ... and in the version four years older | 59% | 67% |
| Median change in a poll's weight, older version against current, at the fitted setting | 25% | 27% |
| Polls whose weight is off by 25% or more | 51% | 53% |

- **2020 to 2024 changed a lot.** 538 also changed its method in between (predictive plus-minus to POLLSCORE), so
  this is the same kind of break a new rater would bring in 2028.
  - Among the firms with the most 2024 polls, AtlasIntel went from below average (z +0.46) to near the top (−1.99),
    Morning Consult from +0.61 to −0.77, and RMG Research from +0.91 to −1.01.
  - Trafalgar (+1.05 to +1.42) and NYT/Siena (−2.49 to −3.69) kept their places.
- **2016 to 2020 was steadier,** and the poll-weighted correlation (0.93) is carried by the heaviest pollster,
  SurveyMonkey, rated poorly both times.
- **A diagnostic on a fit year, not a test:** the 2016 ratings applied to 2020's polls at the fitted setting.

  | 2020 | Baseline | Current (2020) ratings | Four-year-old (2016) ratings |
  |---|---|---|---|
  | 7 days | 51.75 | 50.73 | 50.89 |
  | 30 days | 28.44 | 35.24 | 30.85 |
  | 60 days | 28.68 | 33.08 | 29.99 |

  - At 7 days the stale ratings kept most of the gain (and more of the within-year part: 21.91 against 22.23 for
    the baseline).
  - But that was over the steadier interval, and 2020 helped choose the setting.
- **For 2028:**
  - The September 2024 ratings would be four years old across a period that has already shown one break.
  - Every firm new since 2024 would be unrated, as a third of 2020's polls and a sixth of 2024's were against the
    version four years older.
  - Some firms' ratings swing with their last election's luck.

**Decided 2026-11-21: deferred.** The quality weight passed its 2024 test but does not join the nowcast now, which
stays as stage 1 fixed it. Ratings moved too much from 2020 to 2024 to trust a four-year-old version in 2028, and
the ratings that will exist then are not known. It comes back when they are, or once the repo has its own
pollster tiers built from 2026 polls and results (plan card DA-10). Either goes through this test's rule again,
written down first. The 2024 holdout is not spent a second time.

### Stage 2: convention windows, pre-registration (written 2026-11-21, before any run; confirmed by the user the same day)

The three treatments are those confirmed on 2026-11-20: subtract a fitted rise and fade, down-weight polls in the
window, or only widen the range. Stage 2 runs on the national test bed and is scored against results under the
rule for stages 2 to 4.

**Test bed.** `president_national_poll_days.csv`: daily national readings for 1952 to 2020.

- Scored elections are 1980 to 2020 (11). Each is fitted only on the elections before it, from 1952 on.
- All 11 qualify at 150 days under the presumptive rule.
- 2024 is not in the file, which is checked.
- The early fits are thin (17 to 33 readings a cycle in 1952 to 1976), so 1980 to 1988 are also reported apart.

**What stands in for the nowcast on this series.** The file holds daily means, not polls, before 2004. The same rule
is used for every year.

- The forecast for a date uses every reading of the eventual matchup dated at least 3 days before it. Readings are
  dated by the middle of the field period, so the lag keeps out most polls still in the field. A poll fielded for
  longer than about five days can still end after the date. That is a limit of the file, and the leak test cannot
  see it.
- Each reading has weight 0.5^(age / 60): the fixed nowcast's 60-day half-life. Readings are not weighted by their
  number of polls, which is missing in some cycles. No firm, population or sponsor information exists here.
- **Baseline: forecast = nowcast**, with a range as in section 6: squared spread a + b × days, fitted on the
  earlier elections' squared errors at every date from 7 to 150 days.
- **A diagnostic, deciding nothing:** the same with a 7-day half-life. Stage 1 found that short memory suits the
  nation, and a 60-day memory already damps a bounce.

**Dates and score.** The rule's score is the forecast's error against the result, averaged over 150, 100 and 60
days.

- No convention has started by 150 days in any year from 1952 to 2020 (the earliest start is 120 days out). So at
  150 days the three treatments are the baseline. 100 and 60 days are also reported on their own.
- Loss is the squared error, averaged over the three dates within each election, with elections weighted equally.
- 30 and 7 days are reported. "Must not get worse" means the mean over the 11 elections is not higher than the
  baseline's at either date.

**The treatments.**

1. **Subtract a rise and fade.**
   - Each convention adds a bump to the margin in its party's favour. It rises in a straight line from the
     convention's first day to B on its last, then fades with half-life τ.
   - Readings are adjusted by subtracting both parties' bumps. Convention dates are scheduled in advance, so using
     them leaks nothing.
   - **Fitted to the poll path, not to results.** In each earlier election, the readings from the first
     convention's start to 60 days after the second one's end are measured against the mean of the readings in the
     21 days before the first convention. B is fitted by least squares for each τ in 7, 14, 30 and 60 days, and τ
     is the best of the four. That uses many readings per election and keeps results for scoring. An election with
     no reading in the 21 days before is left out of the fit.
2. **Down-weight the window.**
   - Readings dated from a convention's first day to W days after its last get weight ω times their usual weight.
   - There is no path to fit this to, so ω and W are picked by the score on the earlier elections. The grid is kept
     small because so few elections inform it: ω 0 or 0.5, W 14 or 30 days.
   - If no reading is left at a date, the readings before the window are used.
3. **Only widen the range.** The forecast is the baseline's; the squared spread gains κ on dates within 30 days of a
   convention's end. κ ≥ 0 is fitted by maximum likelihood on the earlier elections. This needs a score that sees
   the spread (point 1 below).

**The rule for stages 2 to 4, as it applies here.**

- **The shuffle.** Each election's convention timing is handed to another election as a unit: both conventions'
  start and end, counted in days before the election, and which party went first. Elections 1952 to 2020 are
  permuted; 2024 and 2028 are not in the pool. The whole as-of backtest is rerun with the fit inside, for 200
  shuffles. The candidate's gain must beat the gain of 19 in 20 shuffles (above the 95th percentile).
- **Elections better:** at least 8 of the 11.
- **A limit, written now:** convention timing is much alike from year to year, so shuffled windows overlap the real
  ones. The test is weak, most of all for the down-weight, which has no party sign.

**Outcomes.**

- Treatments 1 and 2 both change the centre; if both pass, the larger gain is adopted.
- Treatment 3 changes only the range, and can join either.
- If none passes, the forecast is the nowcast, with the baseline's range.
- One round only, unless the user decides otherwise.

**Checks before any loss is read.**

- Changing a scored election's result, or anything in a later election, leaves its fitted values and its forecast
  unchanged.
- Moving readings dated within 3 days of the date, or after it, leaves the forecast unchanged.
- 2024 is absent.

**Confirmed by the user on 2026-11-21, both as proposed:**

1. **A score for treatment 3.** Widening the range cannot change the error, so as the rule stands treatment 3 can
   neither pass nor fail. Proposed: the mean log score of a normal forecast (centre, and spread from the range) at
   the same dates, with the same shuffle and 8-of-11 clauses, and 30 and 7 days not worse. The log score is also
   reported for treatments 1 and 2.
2. **One round.** Stage 1 ran three rounds under the user's decision then. For stage 2 the proposal is one round,
   with the three treatments above.

**Stage 2: four clarifications, written 2026-11-21 after the checks and before any loss was read.**

- **When no reading is left.** The text above says that if down-weighting leaves no reading at a date, the readings
  before the window are used. But if every eligible reading is in the window, there are none before it. So the
  window's readings are then used at their usual weight. How often that happens is counted.
- **A negative bump.** The fitted B is not constrained. If it comes out negative it is used and reported as fitted.
- **Gain above zero.** A treatment must also have a positive gain. Beating the 95th percentile of the shuffles is not
  enough if that percentile is negative.
- **Treatment 3 at 30 and 7 days.** The latest convention ends 61 days out (2004 to 2012), so no date 30 or 7 days
  out is within 30 days of a convention's end. The extra term never applies there, and that clause is met trivially
  for treatment 3.

Checks passed before the run:

- On a made-up flat series with 2016's dates:
  - The bump shape is 0 before the start and on the first day, the party's sign on the last day, and half that one
    half-life later.
  - A planted bump (4 points, 14 days) is recovered exactly and removed by the adjustment.
  - Down-weighting to 0 equals deleting the window, which runs to W days after the end.
  - The extra range applies 100 days out in 2016 and not at 60.
  - With a very long half-life, the baseline is the plain mean of the eligible readings.
- The leak test passes.
- The as-of test passes: changing an election's own result and every later election leaves its fits and forecasts
  unchanged.

### Stage 2: results (run 2026-11-21). None of the three is adopted.

`src/model/pres_conventions.py run`, `data/processed/pres_conventions.json`. 11 scored elections, 200 shuffles.
The empty-window fallback never triggered.

| | Score (150/100/60) | 100 days | 60 days | 30 days | 7 days | Log score | Gain | Elections better | Beats shuffles | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline (nowcast) | 64.68 | 57.32 | 30.26 | 19.18 | 17.03 | −3.654 | | | | |
| 1. Rise and fade | 64.54 | 54.58 | 32.60 | 22.83 | 19.12 | −3.666 | +0.13 | 6 | 68% (needs 95%) | fails |
| 2. Down-weight | 66.99 | 61.69 | 32.83 | 19.26 | 17.08 | −3.674 | −2.32 | 5 | 42% | fails |
| 3. Widen the range | (same as baseline) | | | | | −3.662 | −0.008 | 1 | 6% | fails |

The 150-day loss is 106.46 for all three, as expected.

**1. Rise and fade.** Fails on every clause but the positive gain (+0.13). It is better in 6 of 11 elections, falls
far short of the shuffles' 95th percentile (2.99), and is worse at 30 and 7 days (22.83 and 19.12 against 19.18
and 17.03).

- **The fit does not look like a bounce.** B comes out at 11 to 19 points, with τ = 60 days (the top of the grid)
  in 9 of 11 fits and 30 in the other two.
- The two parties' bumps mostly cancel, so the net adjustment is smaller: 6.4 points at the end of 1984's second
  convention, 4.3 in 2004, 0.8 in 2020. But it hardly fades. In 1984 it is still 5.4 at 60 days out.
- So the fit is taking up lasting movement after the conventions, not a rise that goes away. That is stage 3's
  question (reversion and trend) more than stage 2's.
- It helps most in 1988, 1984 and 2000, and hurts most in 1996, 1992 and 1980. The fits pool readings, so recent,
  densely polled elections weigh most; 5 elections informed 1980's fit, 15 informed 2020's.

**2. Down-weight.** Worse overall (−2.32) and worse at 100 days (61.69 against 57.32). The pick was a weight of 0.5
for 14 days after a convention in every election. As written beforehand, this test was weak, and it was not needed:
the treatment does not help.

**3. Widen the range.** The extra term κ came out positive in every election (2.1 to 19.1), but the log score is
slightly worse in 10 of 11 (−3.662 against −3.654). The range fitted to all dates already covers the convention
weeks. No evidence for a wider range there.

**1980 to 1988 apart:** baseline 130.61, rise and fade 118.52, down-weight 130.44. From 1992 on: 39.95, 44.30 and
43.20. The rise and fade's gain comes from 1984 and 1988, whose fits are thin.

**A diagnostic (decides nothing):** the nowcast with a 7-day half-life does worse on this test bed: 66.13 against
64.68, and 24.41 and 22.20 at 30 and 7 days against 19.18 and 17.03. Against results, the 60-day memory is the
better one for the nation, though stage 1 found short memory best at predicting the next national polls. Polls
that move fast also move back.

**Stage 2 closed.** One round, as agreed. **The forecast through the convention window is the nowcast**, with the
baseline's range (squared spread a + b × days). Conventions get no special treatment. What the rise and fade did
pick up, a lasting shift after the conventions, goes to stage 3.

### Stage 3: reversion and trend, pre-registration (written 2026-11-21, before any run; three questions await the user)

Stage 3 runs on the national test bed, under the rule for stages 2 to 4 as stage 2 applied it:

- **Elections.** 1980 to 2020 are scored, each fitted on the elections before it.
- **Forecast inputs.** Readings dated at least 3 days before the date; the nowcast with its 60-day half-life.
- **Score.** Squared error against the result, averaged over 150, 100 and 60 days.
- **Clauses.** Beat 19 in 20 of 200 shuffles; better in at least 8 of 11 elections; a positive gain; and 30 and 7
  days not worse on average.
- **Baseline.** Forecast = nowcast, with stage 2's range (a + b × days). Stage 2 found no convention treatment, so
  the nowcast enters stage 3 unchanged.

**Decided with the user on 2026-11-21:**

- Estimators must behave well in small samples.
- The user's trend-survival model replaces "continue or reverse the last month's movement".
- Its episode panel is presidential only. What pooling other series would add is reported.

**Small-sample commitments, for every candidate.**

- At most two fitted numbers in a candidate's adjustment. Not counted: the anchor's own regression, and a survival
  curve estimated without parameters.
- Every adjustment is shrunk toward none:
  - a ridge penalty, chosen by leaving one earlier election out at a time within the fit (nested inside the
    as-of backtest);
  - or bounded to the range that makes sense (a pull between 0 and 1).
- Elections are the independent units. Uncertainty on fitted values comes from leaving one election out at a time.
- Every fitted value is reported election by election, with any grid-edge pick.
- A yes/no model is fitted by Firth's bias-reduced method.

**Data.**

- **Approval:** `gallup_approval.csv` (Gallup, 1941 to January 2021). Approval on a date is the mean of the
  readings that ended in the 30 days before it, or else the latest one before it. Readings are sparse in some
  years (2 to 4 in the 200 days before 1972 and 1976). The 30-day change is zero in 18 of the 90 election-date
  cells, so candidate 5 has little to work with there.
- **The president's party:** `fundamentals_dataset.csv`.
  - The series' `d_incumbent_party` column is not used. In the source years it appears to mark an incumbent
    president running (1 in 1964, 1980, 1996 and 2012; 0 in 1952, 1968 and 2000).
  - The repo's own 2016 and 2020 rows mark the party in office instead.
  - Approval moves the incumbent party's margin: + for a Democratic president, − for a Republican.
- **The previous result:** the series' result for the election before. 1952 has none, so it is left out wherever
  the previous result is needed (fits and shuffles for candidates 1 and 3).
- **The undecided share u:** 100 minus both candidates' shares, averaged like the nowcast.
  - The series has it for 1952 to 2004 and for 2020. Before 2004 it includes third-party support, which cannot be
    separated.
  - Its 2008 to 2016 sources are two-party only (u is 0 on every row), so for those years u comes from the repo's
    national polls (`president_general_polls.csv`). There the margin and the share come from different sets of
    polls.
- **Reading density** rises from 17 readings a cycle (1952) to 347 (2020). Measures built from the lighter average
  (episodes, spread) will partly track density. Standardizing against earlier, sparser elections builds a time
  trend into them. Density is reported beside them.

**The six candidates.**

1. **Pull toward an anchor.**
   - The anchor is the incumbent party's margin, predicted from approval on that date and the previous result: a
     ridge regression on the earlier elections at the same number of days out, with an unpenalized intercept.
     Turned into the Democratic margin by the president's party.
   - Forecast = nowcast + λ × (anchor − nowcast), with λ = k × days / 150, bounded to 0 to 1.
   - k is fitted by ridge least squares on the earlier elections, at every tenth day from 150 to 10 and at 7.
   - Reported, not decided: k fitted separately before and after the second convention ends. Stage 2 found that
     movement after the conventions lasts.
2. **Trend survival** (the user's idea, replacing "continue or reverse").
   - **The lighter average.** The nowcast with a 14-day half-life, computed each day.
   - **Episodes, on the clock of what is known.** A turning point is confirmed on the day the lighter average has
     moved back 1.5 points from its latest extreme (a zig-zag filter). An episode runs from one confirmed turning
     point to the next. Its age on a day is the weeks since its start was confirmed, and it ends in the week the
     next turning point is confirmed. Fit and forecast both use this clock, so neither uses a peak that was not yet
     known. An episode still running on election day is censored. Thresholds of 1.0 and 2.0 points are reported.
   - **Episode counts** (no results used):

     | Threshold | 1980 to 2020 | 1952 to 1976 |
     |---|---|---|
     | 1.0 | 82 | 23 |
     | 1.5 | 50 | 17 |
     | 2.0 | 33 | 14 |

     2020 has none at 1.5 points. 1980 has 6.
   - **The survival curve.** The chance an episode is still running after each week, by Kaplan-Meier on the earlier
     elections' episodes (no parameters). A discrete-time logistic hazard with one term for age, fitted by Firth's
     method, is reported beside it.
   - **Uncertainty, reported only.** A bootstrap that resamples elections, and leave-one-election-out. With few
     elections the bootstrap understates uncertainty, and early fits have too few elections for it to mean much.
   - **The drift.** The lighter average's mean weekly movement in the episode's direction, over the weeks the
     earlier elections' episodes were running, on the same clock. Pooled and shrunk toward zero (ridge). This is the
     one fitted number.
   - **The forecast.** Forecast = nowcast + drift × direction × the expected weeks the current episode has left,
     given its age, capped at the weeks to the election.
   - **A control row, deciding nothing.** The 60-day nowcast lags the 14-day average, so a trend term partly just
     catches up. The 14-day average alone, with no trend term, is reported beside it.
   - **The null, deciding nothing.** The same episode-finding is run on each election's daily changes in shuffled
     order. Its survival curve is shown beside the real one, to show whether episodes last longer than noise and
     smoothing alone make them.
3. **Durability.** A steady race gets a weaker pull and a narrower range, as the plan says.
   - s is the spread of the lighter average's weekly changes so far, standardized against the earlier elections at
     the same number of days out. High s means an unsteady race.
   - **(a) The pull.** λ × exp(β × s), with β ≥ 0. A steady race (low s) is pulled less; an unsteady one more. β is
     ridge-shrunk toward 0. Squared error decides.
   - **(b) The range.** The squared spread × exp(γ × s), with γ ≥ 0 fitted by maximum likelihood. Log score decides.
   - Judged against the baseline under the rule, and also reported against candidate 1, to show what steadiness
     adds.
4. **Undecided voters.**
   - **(a) How they break.** A proportional break leaves the two-party margin as it is; an even break gives the
     margin in points of all respondents, which is the two-party margin × (1 − u/100). Centre = nowcast ×
     (1 − (1 − α) × u/100), with α between 0 and 1 fitted on the earlier elections. Squared error decides.
   - **(b) A wider range when there are many.** The squared spread gains κ × u. κ ≥ 0 is fitted by maximum
     likelihood. Log score decides.
5. **Shifts that come with approval.**
   - The nowcast's movement over the last 30 days is split in two: the part predicted by the change in approval over
     the same 30 days (a pooled regression on the earlier elections, in the incumbent party's terms), and the rest.
   - Forecast = nowcast − ρ × the rest, with ρ between 0 and 1 and ridge-shrunk. The part that comes with approval is
     kept.
   - The variant that reverts both parts by the same ρ is reported beside it, so the comparison shows whether the
     approval part lasts longer.
6. **Shifts spread evenly against concentrated ones.** Only the state polls from 2004 can measure this, so at most
   2012, 2016 and 2020 could be scored (question 2 below).

Candidates 3 and 4 have two parts each. Each part is tested on its own and can pass on its own; they count as one
candidate each toward the six.

**The shuffle.** Each candidate's feature is handed between elections as a whole series by days out, and the fit is
redone inside each of 200 shuffles:

- **1:** the anchor's inputs (approval series and previous result, in the incumbent party's terms, turned into the
  Democratic margin by the receiving election's president's party). Elections 1956 to 2020.
- **2:** the lighter average's path, which carries the episode state.
- **3:** the spread series only, with the anchor left as it is. So this tests what steadiness adds.
- **4:** the undecided share.
- **5:** the approval series.

This is weak wherever a feature is much alike from year to year.

**Many tests.** Six candidates, eight tests, each at 1 in 20: there is roughly a one-in-four chance that at least
one passes by noise alone.

**If more than one passes.**

- 1 and 3(a) are alternatives: the larger gain is adopted.
- 2 and 5 adjust for movement and may join 1 or 3(a). A combination is adopted only if it passes the rule against
  the baseline; otherwise the single best.
- 3(b) and 4(b) change only the range. If both pass, the one with the better log score is adopted.
- 4(a) changes the centre for undecided voters and may join anything.
- If none passes, the forecast is the nowcast with the baseline's range.

**Checks before any loss is read.**

- 2024 is absent.
- The leak test.
- The as-of test: changing an election's own result, and every later election, leaves its fits and forecast
  unchanged.
- Behaviour on made-up series:
  - a planted pull is recovered;
  - a made-up series with known turning points gives the right confirmation days, and none before they happen;
  - planted episode lengths give back their survival curve;
  - u = 0 makes candidate 4(a) the baseline.

**Questions for the user:**

1. **Early fits for candidate 2.** With 1980 as the first scored election and fits only on earlier ones, 1980 has no
   presidential episodes from 1980 on to learn from, and 1984 only 1980's six.
   - Either the early fits also use 1952 to 1976 (17 episodes at 1.5 points, from sparse readings);
   - or candidate 2 gets a burn-in and is scored on 1988 to 2020 only (9 elections, needing 6 of 9 better).

   Proposed: the first, with 1980 to 1988 reported apart.
2. **Candidate 6.** Three scored elections cannot meet a rule built for eleven. Proposed: a diagnostic deciding
   nothing. It shows how often a 30-day national shift that was evenly spread across states (a small standard
   deviation of the state shifts, against the national shift) held over the next 30 days, against a concentrated
   one.
3. **One round,** as in stage 2.

**Stage 3: decisions of 2026-11-21, and amendments before any run.**

The user decided:

- **The survival curve** is a discrete-time hazard: the chance an episode ends in a given week, as a logistic
  function of its age.
  - The age term is shrunk toward zero by a ridge penalty, chosen by leaving one earlier election out at a time.
    With no clear age effect it becomes a constant weekly chance of ending (a geometric model).
  - Kaplan-Meier, the unshrunk Firth fit and the bootstrap over elections are reported beside it as checks.
  - A random survival forest was considered and set aside: about 50 episodes in 11 elections are too few, they are
    not independent, and a forest has no shrinkage toward "no effect".
  - **Exception to the two-number limit:** candidate 2 has three fitted numbers (the base rate, the age term and the
    drift). The extra one is shrunk toward zero, so at worst it adds nothing.
- **Early fits for candidate 2** also use the 1952 to 1976 episodes. 1980 to 1988 are reported apart.
- **Candidate 6 is a diagnostic,** deciding nothing on its own.

**What diagnostics may do** (confirmed by the user on 2026-11-21).

- No diagnostic can turn a failing candidate into a pass.
- A diagnostic can only **flag** a pass. A flagged pass goes to the user to decide; an unflagged pass is adopted
  under the rule. The flags, fixed now:
  - **Candidate 2:**
    - The 14-day average with no trend term scores at least as well as candidate 2 on the rule's score. The gain is
      then shorter memory, not the trend.
    - Or the real survival curve lies inside the range of the shuffled-changes null. The episodes then last no longer
      than noise makes them.
  - **Candidate 3:** candidate 1 alone scores at least as well as 3(a). Steadiness then adds nothing.
  - **Candidates 1, 2 and 5 against candidate 6.** These forecast that recent movement reverts (1, 5) or continues
    (2). The flag is raised if candidate 6 finds that evenly spread shifts held more often than concentrated ones
    by 15 percentage points or more over the next 30 days, in either direction. A forecast that treats all shifts
    alike would then be missing something. The flag also says the evidence is three elections.
  - **Candidate 1:** the pull fitted after the conventions is less than half the pull fitted before them, on the
    elections where both can be fitted. Stage 2's lasting post-convention shift would then be at odds with a single
    pull.
- Otherwise a diagnostic is reported for what it shows, and it points to later work, not to a change now.

**Confirmed by the user on 2026-11-21:** the diagnostic rule above, and one round, as in stage 2.

**Stage 3: amendments after the code review, before any loss was read** (`src/model/pres_reversion.py`).

- **Candidate 2's drift is on the same clock as the hazard.** Each episode's final, partial week up to the
  confirmation day is included.
  - Between two confirmations an episode's net movement is its swing less twice the threshold, so the drift could
    have come out near zero. Checked without results, it does not.
  - Over 92 finished episodes (1952 to 2020, found from 260 days out), the mean net movement is +1.18 points in the
    episode's direction, and the mean weekly movement +0.30.
  - The adjustments it gives are typically 0.1 to 2 points.
  - A negative fitted drift would be used as fitted.
  - Episodes are found from 260 days out, not the 200 behind the counts above, so there are more of them.
- **The null rebuilds the readings, then smooths.** The text said the light average's own changes are shuffled; that
  would remove the smoothing too. Instead, each election's reading-to-reading changes are shuffled, the readings
  rebuilt, the 14-day average recomputed and the episodes found again.
- **Seven tests on five candidates:** 1, 2, 3(a), 3(b), 4(a), 4(b) and 5; candidate 6 is a diagnostic. At 1 in 20
  each, the chance that at least one passes by noise is about 30%, not one in four.
- **Candidate 6 uses five elections** (2004 to 2020), not three. Its flag says so.
- **What candidate 1's shuffle tests.** With the inputs shuffled, the pull is still toward an average incumbent
  margin. Passing means approval and the previous result add to that, not that a pull helps at all.
- **Approval has no publication lag.** It uses readings that ended before the date; Gallup published within days.
- **Checks, rerun and passed:**
  - the nowcast equals stage 2's exactly;
  - a pull is recovered;
  - turning points are confirmed on the right days and never before;
  - geometric durations give back their rate;
  - the drift's net movement over a made-up episode is zero, and the sign of the adjustment follows the drift;
  - u = 0 gives the baseline;
  - the leak test passes;
  - the as-of test passes, with later elections' series reshaped (scaled and noised, not shifted) and their
    results moved by random amounts.
- Every forecast and spread is checked to be finite before it is scored. The real-data results are written to disk
  before the shuffles start.

### Stage 3: results (run 2026-11-21). One test passes: the undecided break, 4(a).

`src/model/pres_reversion.py run` (`data/processed/pres_reversion.json`) and `report`
(`data/processed/pres_reversion_report.json`). 11 scored elections; 200 shuffles per candidate.

| Test | Score | Gain | Elections better | Shuffles beaten | 30 and 7 days not worse | Verdict |
|---|---|---|---|---|---|---|
| Baseline (nowcast) | 64.68 | | | | | |
| 1. Pull toward an anchor | 76.93 | −12.25 | 6 | 12% | no | fails |
| 2. Trend survival | 63.37 | +1.31 | 6 | 81% | no (7 days worse) | fails |
| 3(a). Durability, pull | 76.25 | −11.57 | 6 | 76% | no | fails |
| 3(b). Durability, range (log score) | −3.55 against −3.65 | +0.105 | 5 | 99% | yes | fails (5 of 11) |
| **4(a). Undecided break** | **52.10** | **+12.58** | **8** | **97.5%** | **yes** | **passes** |
| 4(b). Undecided, range | κ = 0 in every fit: the baseline | 0 | 0 | | | fails |
| 5. Approval shifts | ρ = 0 in every fit: the baseline | 0 | 0 | | | fails |

**4(a) passes every clause, and no diagnostic flag applies to it, so under the rule it is adopted.**

- α came out at 0 in every fit, the edge of its grid: an even break, so the forecast is the nowcast × (1 − u/100).
- It is better at every date: 100 days 47.58 against 57.32, 60 days 26.07 against 30.26, 30 days 16.14 against
  19.18, and 7 days 13.11 against 17.03.
- **What carries it.** With the undecided share shuffled between elections, the gain is still positive in every
  shuffle (median 8.2, 95th percentile 11.84). So most of the gain comes from shrinking the margin toward a tie by
  about the size of a typical undecided share. The election's own share adds the rest (12.58 against the
  shuffles' 8.2), enough to beat 19 in 20.
- Before 2004 the share includes third-party support (Anderson 1980, Perot 1992 and 1996), so "undecided" there
  partly means third-party voters. The formula treats them as splitting evenly, which they do not. It works
  empirically, but the mechanism is a margin that shrinks toward a tie, not only undecided voters breaking.
- For 2008 to 2016 the share comes from the repo's polls.
- By election at 7 days its squared error is lower in 1992, 1996, 2000, 2016 and 2020, and higher in 1980, 1984,
  1988, 2004, 2008 and 2012. Most of the 7-day gain is 1992 and 1996, the Perot years.

**The others.**

- **1. The anchor pull fails badly.** k came out at its bound of 1 (full pull to the anchor at 150 days) in 8 of 11
  fits, with no shrinkage chosen. The anchor from approval and the previous result is far worse than the polls at
  150 days (134.89 against 106.46). It helps in 1988, 1992, 1996, 2000, 2004 and 2008, and is very wrong in 1980
  (530 against 197) and 1984. EC-3's fundamentals model replaces this anchor later. The diagnostic pull before and after the conventions
  is 0.94 and 1.0, so no flag.
- **2. Trend survival fails.** It gains 1.31 and beats 81% of the shuffles, but is better in only 6 elections and
  worse at 7 days (18.16 against 17.03).
  - Both of its flags would have applied had it passed. The 14-day average alone scores better (60.50).
  - The episodes' survival curve lies inside the shuffled-readings null at every week: about half still running at
    4 weeks and a quarter at 8, as noise and smoothing alone would give.
  - The hazard's age term was kept (about +0.03 to +0.04 a week, older episodes slightly likelier to end) in 7 of
    11 fits, and shrunk to 0 in 4. The unshrunk Firth fits agree (+0.025 to +0.048).
  - The bootstrap over elections puts survival at 4 weeks between about 0.47 and 0.61.
  - At thresholds of 1.0 and 2.0 points, the gains are −3.69 and +2.00, each better in 5 and 6 elections and worse
    at 30 and 7 days.
  - The approval series would add 1 to 6 episodes an election if pooled.
- **3. Durability fails.** β was 0 or 0.1, so the pull is candidate 1's and fails with it.
  - The range part, 3(b), beat 99% of its shuffles and kept 30 and 7 days, but is better in only 5 of 11
    elections.
  - γ rose from 0 to 0.5 as elections were added, so later fits say an unsteady race deserves a wider range. That
    is worth testing again with more years.
- **4(b) and 5 never moved off the baseline.**
  - κ = 0 and ρ = 0 in every fit; the undecided share adds nothing to the range, and no part of the last month's
    movement reverts, whether it came with approval or not.
  - The pooled approval effect is about 0.2 points of margin per point of approval over 30 days.
  - Leave-one-out ranges for the 2020 fit: k 0.72 to 1.0, drift 0.20 to 0.30 a week, α 0 and ρ 0 throughout.
- **6. Evenness diagnostic.**
  - Only 8 cases qualified: a national shift of a point or more in 30 days, with five or more states polled in
    both windows, in 2004, 2008 and 2016. Every one held.
  - So there is no difference between even and concentrated shifts, and no flag. Too few to say anything.

**Many tests.** Seven tests, about a 30% chance of one fluke pass. 4(a) beats its shuffles narrowly (97.5% against
the 95% needed). It is better at every date and in 8 of 11 elections.

**Stage 3 closed.** One round, as agreed.

- **The forecast is the nowcast scaled by (1 − u/100)**, u being the undecided (and, before 2004, third-party)
  share averaged like the nowcast. Its range is the baseline's.
- No pull toward an anchor, no trend term and no reversion of recent movement.

**For later:**

- Stage 5 and the 2028 model need the undecided share measured the way it is here. In 2028 that means asking which
  polls report it and whether third-party support is in it.
- The anchor returns with EC-3.

**Stage 3 results: corrections and additions after review (2026-11-21; no rerun).**

- **How narrowly 4(a) passes.**
  - The 8 of 11 includes 2004 at 6.80 against 6.89.
  - It beats 97.5% of the shuffles, where 95% is needed.
  - α sat on its bound (0) in every fit.
  - With about a 30% chance of a fluke across seven tests, this is a pass at the margin.
- **What 4(a) is, plainly.** The two-party margin × (1 − u/100) is the raw margin: the Democrat's share minus the
  Republican's, in points of all respondents. For example, 1992 at 43.5 against 46.5 gives −3.0 against −3.33
  two-party. The forecast is the raw margin averaged like the nowcast.
- **Third-party support is in u after 2004 too.** In 2016 the repo's national polls give a median share of about 13
  where a poll asked the head-to-head question and 20 where it asked only the full field (Johnson, Stein). So the
  adjustment depends heavily on which question a poll asked. For 2028 this is a decision, not a detail: full field
  or head-to-head, and how to treat a third candidate (section 10).
- **Bounds hide signs.** Several picks sat on a bound:
  - k = 1 in 8 of 11 fits;
  - α = 0 in all;
  - κ = 0, ρ = 0 and both reversion variants at 0 in all;
  - β at 0 or 0.1.

  ρ could not go negative, so "no part of the last month's movement reverts" is supported, but "it does not
  continue" is not. Candidate 2's gain and the 14-day row both lean toward continuation at 150 to 60 days.
- **Candidate 1 failed as built.** In the fit for k, each earlier election's anchor came from all the other earlier
  elections, including ones after it. The scored election's anchor came only from strictly earlier ones. That
  flatters the anchor in the fitting rows and probably explains k at its bound with no shrinkage. The failure is
  this build's, not necessarily the idea's. It is not rerun (one round). EC-3 replaces the anchor.
- **Periods.** 4(a) scores 121.34 against 130.61 in 1980 to 1988, and 26.14 against 39.95 from 1992 on. Most of
  the 7-day gain is 1992 and 1996, when third-party support was large.
- **Leave-one-out ranges** were computed for 2020's fit only.
- **Reading density**, readings within 260 days: 14 to 29 a cycle in 1952 to 1976, 61 to 97 in 1980 to 1988, and 114
  to 242 from 1992.
- **Open items the adoption creates:**
  - **The range.** The baseline's range was fitted to the nowcast's errors; the adopted centre's are smaller. It is
    refitted when the model is assembled.
  - **States.** How the raw-margin scaling applies to state margins is stage 5's question.

### Stage 4: states with few polls, pre-registration (written 2026-11-21, before any run; confirmed by the user the same day)

Stage 4 runs on the state test bed: state polls 2004 to 2020 through stage 1's loader. 2024 is refused there.
Results are `state_presidential.csv`. Maine's and Nebraska's districts are left out, having no results in the repo.

**Which states are scored.** On each date, the states (and DC) with no poll that ended in the previous 30 days.
Counted without results:

| Days out | 150 | 100 | 60 | 30 | 7 |
|---|---|---|---|---|---|
| 2004 | 14 | 15 | 16 | 0 | 8 |
| 2008 | 13 | 10 | 15 | 0 | 4 |
| 2012 | 22 | 29 | 26 | 14 | 12 |
| 2016 | 28 | 25 | 15 | 10 | 9 |
| 2020 | 22 | 0 | 0 | 0 | 0 |

- **States with no poll yet that cycle, by that date:** 6 to 9 in 2004 at 150 to 60 days, 1 in 2008, 3 to 6 in 2012,
  2 to 12 in 2016, and 12 in 2020 at 150 days.
- **One firm's sweep decides a lot.** American Research Group polled 49 to 51 states between 30 and 60 days out in
  2004 and 2008, and SurveyMonkey all 51 in 2020. That is why no state is thin at 30 days in 2004 and 2008, or
  after 150 days in 2020.
- **Against the plan's "15 to 29 states at 100 days":** the counts here are 15, 10, 29 and 25 for 2004 to 2016. 2008
  differs because this count uses stage 1's poll set and firm keys.

**The national input.** The national nowcast on the national series, two-party, as in stages 2 and 3, from
readings dated at least 3 days before the date. Stage 3's raw-margin scaling is not applied here: how it applies to
states is stage 5's question.

**Baseline.** The state's own nowcast (stage 1's weighting, every poll of it that ended before the date, however
old). A state with no poll at all that cycle gets the prior below.

**The three ways to fill the gap,** none with a fitted number:

1. **The prior:** the national nowcast plus the state's lean at the previous election (its margin minus the
   national margin).
2. **The average swing in the polled states:** the state's previous result plus the mean, over the states polled in
   the last 30 days, of their nowcast minus their previous result.
3. **The last poll carried forward:** the state's nowcast as of the day after its last poll, plus the national
   movement since that day.
   - With exponential weights, the state's nowcast on the day after its last poll is its nowcast on the date
     (checked: 173 of 173 cases). So method 3 is the baseline plus one term, the national movement.
   - **The national movement** is measured on the 14-day national average, not the 60-day nowcast. Stage 1 found
     short memory best at tracking the national polls, and this term tracks movement; it does not forecast. There
     is no grid.
     - Checked without results: the 60-day nowcast moves only 0.86 points on average over these gaps, which would
       make the term almost inert. The 14-day average moves 1.49 (90th percentile 3.79).
     - The 60-day version is reported beside it.
   - In the scored states the last poll is typically 70 days old (middle half 41 to 122, up to 563).
   - Where there is no national reading as far back as the last poll (42 cases), the movement is measured from the
     earliest day with one.
   - A state with no poll yet that cycle gets the prior.

Having nothing to fit means no fit leans on earlier elections. So every election from 2004 to 2020 can be scored
at every date, including the two that section 7's table had held back for burn-in (question 1).

**The rule: section 8, as the plan says for the state test bed, at stage 4's dates.**

- **Score.** Squared error against the result, averaged over the scored states on each date, then over 150, 100 and
  60 days, with elections weighted equally. An election with no scored state on a date skips that date.
- **30 and 7 days** are reported and must not be worse on average, over the elections with scored states there:
  2012 and 2016 at 30 days; 2004, 2008, 2012 and 2016 at 7.
- **Scrambled versions.** Each method's information is handed from one state to another within the election, and
  rerun 200 times. The gain must beat 19 in 20 of them.
  - **1:** the previous lean is shuffled across states.
  - **2:** the previous results are shuffled across states.
  - **3:** the national-movement term is shuffled across the scored states that have old polls; their levels stay.
  - **For methods 1 and 2 this clause is close to automatic.** Leans and previous results differ by tens of points
    across states, so any shuffled version is far worse. For them the clauses that bind are a positive gain and 4 of
    5 elections, which a coin flip meets about one time in five (question 2).
- **Simulation noise:** section 8's second condition does not apply; nothing here is simulated.
- **Elections better:** section 8 asks for three of four. With five elections, at least 4 of 5 (question 1).
- **Gain above zero.**

**If more than one passes,** the one with the largest gain is adopted; the three are alternatives for the same
states. If none passes, thinly polled states keep the baseline.

**Limits, written now.**

- **Where methods coincide.** For a state with no poll yet, the baseline, method 1 and method 3 give the same
  number. How many scored states each method changes, by election and date, is reported.
- **Method 2 against method 1:** they differ by one constant per election and date, so comparing them rests on about
  15 effective observations.
- States in one election share most of their error, so states are not independent.

**The user's selection question, answered against results** (diagnostics; how they may be used is question 3).
Every state is used on every date from 150 to 60 days, not only the thin ones. Both (a) and (b) are reported
pooled and by election, since states in one year share the national miss.

- **(a) How far states land from their no-poll forecast.** The prior's error against the result, by the state's
  polls in the previous 30 days (0, 1 to 3, 4 to 9, 10 or more): mean squared error and mean signed error.
  If pollsters skip lopsided states, the 0 group should land closer to its prior.
- **(b) Whether the few polls in thin places help.** For states with 1 to 3 polls in the previous 30 days: the
  state's nowcast error against the prior's, and the share of cases where the nowcast is the closer of the two.
- **(c) Sponsored against independent polls there.** Sponsor flags exist only in 2020 (312 state polls), and 2020
  has no thin states after 150 days. So this is counted and, very likely, reported as not possible.

**Checks before any loss is read.**

- 2024 is absent from the polls, and no 2024 row of the results file is read.
- The leak test: moving polls ending on or after the date, and national readings within 3 days of it or after,
  leaves every forecast unchanged.
- The deletion test: deleting the polls that end on or after the date leaves the scored set, method 2's polled set
  and every forecast unchanged.
- Changing the scored election's results leaves every forecast unchanged.
- Behaviour on made-up inputs:
  - with no movement since a state's last poll, method 3 equals the baseline;
  - with every state polled at a uniform swing, method 2 recovers it;
  - method 1 equals national plus lean.

**Confirmed by the user on 2026-11-21, all five as proposed:**

1. **Elections and the count.** Score 2004 to 2020 at every date, since nothing is fitted, and ask for at least
   4 of 5 better. The alternative is section 7's table: 2008 only at 30 and 7 days, 2004 not at all.
2. **A stricter clause for methods 1 and 2.** Their scramble is close to automatic. Proposed: in its place, a paired
   sign-flip test over election-date units (each unit's mean gain across its scored states; about 15 units), at
   p < 0.05. Method 3 keeps its scramble of the movement term.
3. **The national input.** Use the two-party national nowcast, leaving stage 3's scaling to stage 5.
4. **What the diagnostics may do.** As in stage 3, none can turn a fail into a pass. One flag, fixed now and measured
   on the states method 3 is scored on (thin states with old polls): if their old polls (the baseline) are closer to
   the result than the prior in fewer than half the cases, a pass by method 3, which leans on those polls, goes to
   the user. Otherwise the diagnostics are reported and point to later work.
5. **One round.**
