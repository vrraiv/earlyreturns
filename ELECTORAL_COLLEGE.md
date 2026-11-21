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
   swing in the polled states; the state's last poll carried forward by the national movement since.
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

Anything that moves a state's polls using the national series belongs to stage 4, not here.

**Adoption rule for stage 1 (a default, awaiting a ruling).** A candidate is adopted if all four hold:

- its loss, with cycles weighted equally, is lower than the baseline's;
- it is lower in at least 4 of the 5 cycles;
- it passes a paired sign-flip test at 1 in 20, over place-and-cycle units with 2,000 flips. Each unit is the mean
  loss difference over that place's targets in that cycle, weighted as in the loss;
- it is not worse in the 91 to 161 day band, where the forecast's first test dates fall.

A sign test over five cycles alone cannot reach 1 in 20 unless all five agree. That is why the place-and-cycle test
carries the significance and the cycle count guards against one cycle driving the result.
