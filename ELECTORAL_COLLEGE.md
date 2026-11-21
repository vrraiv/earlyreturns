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
- 2024 is out of everything in this section, including the tests that use no results.
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
   is tested for every state at stage 1, round 2. If it is adopted there, it is stage 4's starting point.)
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
band.

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
| 5. National trend adjustment | −0.01 | 2 | 0.51 | −0.06 | fails |
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
  firm's national polls, and the own-firm test fails in 8 of 20 cases. It fails the rule even with that help, so it
  was not rerun. 2008 gains a lot: 39.17 to 33.07 with a 7-day national trend line. That is the
  autumn the financial crisis moved every state at once. But it loses in 2004, 2012 and 2016, where moving state
  polls by a noisy national line adds more error than it removes. This bears on stage 4 and on the durability
  questions of stage 3, and it is not adopted here.
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
