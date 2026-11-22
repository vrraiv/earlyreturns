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
| Education, race, age, income | shared state errors | `state_demographics.csv`, by year from the Census Bureau (DA-11, section 9) | candidate |
| Rural share | shared state errors | `state_rural_share.csv`, from the census in force at each election (DA-11, section 9) | candidate |
| Urban against suburban | shared state errors | The Downballot's state tables (one snapshot); no by-year source (section 9) | candidate; EC-5's pre-registration decides whether it stays |
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
- An urban against suburban split by year. The one snapshot is The Downballot's (below).
- Fundamentals for presidential elections (EC-3).

**Demographics by year: in the repo since 2026-11-21 (DA-11).** `data/interim/state_demographics.csv`, built by
`src/collect/census_demographics.py` from the Census Bureau's API; sources and caveats are in `DATA.md`. Decided
with the user that day, before any EC-5 candidate is written down. Choices first made in the build are marked; the
user confirmed each of them the same day:

- **Fields.** Education, race and ethnicity, age, white adults without a degree, and median household income.
  Income was added to the card because candidate 3 in section 5 uses it.
- **How the fields are measured (the build's choices, confirmed by the user 2026-11-21).** Degree share of adults 25 and
  over; the same among white non-Hispanic adults; white non-Hispanic adults without a degree as a share of all
  adults 25 and over, not of white adults; white, Black and Asian (each non-Hispanic, one race) and Latino shares;
  age as two shares of adults, 18 to 29 and 65 and over.
- **The seven measures** of candidate 3 are those in `state_similarity()` (`src/model/backtest_asof.py`): degree
  share, the log of median income, white, Black and Latino shares, and urban and rural share. Age, Asian share and
  the two white education measures are collected but are not among the seven.
- **Why adults 25 and over for education, not 18 and over (the user's question, 2026-11-21).** The Bureau publishes
  education for white non-Hispanic adults only at 25 and over; its one table for 18 and over has no breakdown by
  race, so the white share without a degree at 18 and over would need the microdata in every year. Adults 18 to 24
  are about 12% of adults and 9% to 12% of them hold a degree, so including them lowers the level by about 2.5
  points and barely reorders states (the two degree shares correlate 0.997 in 2007 and 0.998 in 2019). The
  Downballot's tables use 25 and over too. The user kept 25 and over, with no 18-and-over share added.
- **Population base.** Total population for race and adults 25 and over for education, as in The Downballot's
  snapshot, so the two can be compared.
- **Which year an election uses.** The year before it: the latest survey published before the 7-day forecast, and
  what 2028 will have. A year's survey comes out the following September (confirmed for the 2021, 2023 and 2024
  survey years; earlier years not checked). The election's own year is run beside it as a comparison that decides
  nothing. `state_demographics_vintages.csv` holds both. 2000, 2004 and 2020 take the same year in both, because
  the API has no survey for 1999, 2003 or 2020; for 2000 and 2004 that was the build's choice, confirmed by the
  user.
- **2020.** The Bureau published no standard one-year tables for 2020, so 2020 uses 2019. From the 2020 survey year
  the race question and its coding changed, so 2019 is like for like with 2008 to 2016 and 2021 is not. The inputs
  for 2024 and 2028 are after that change.
- **2004.** Tabulated here from that year's survey microdata. It is our own tabulation, not a Census estimate, and
  2004 is used for fitting only (2008 is the first scored election). The 2004 survey was a smaller, trial-stage
  sample. On white share and on white adults without a degree, every state but one is within 2 points of a line
  from 2000 to 2005. South Dakota is the one: its white share is about 6 points above both years, and its white
  share without a degree about 5. The cause is not established (other states with large reservations are not
  off).
- **Rural share: decided 2026-11-21, on my recommendation.** From the census in force at each election: the 2000
  census for 2000 to 2008, the 2010 census for 2012 to 2020, the 2020 census for 2024 and 2028
  (`data/interim/state_rural_share.csv`; `state_demographics_vintages.csv` names the census for each election). It
  gives rural share only. Whether The Downballot's urban share stays beside it as a fixed measure is for EC-5's
  pre-registration of candidate 3. Background: urban and rural share are the other two of candidate 3's seven
  measures. The Census Bureau has no suburban
  class. It counts urban and rural population at each census (2000, 2010, 2020) and changed the definition in 2020.
  Its yearly survey also reports the urban and rural parts of each state: the API returns them for 2005 to 2021
  and not from 2022. The 2012 survey was the first on the 2010 census's urban areas, by the Bureau's account. The Downballot's figures are a different measure with
  three classes. An earlier version of
  it was described by its authors as built on a federal housing department model of how people describe their own
  neighbourhood; how the current file is built has not been confirmed. Across states its rural share tracks the
  2020 census's closely (correlation 0.98), and states' census urban shares barely change order over time (0.987
  between 2000 and 2020).
- **Urban and rural: what each route showed (2026-11-21, 49 states), before the user chose the last one.** An earlier
  version of this section said the Bureau measures urban and rural only at each census; the survey figures were
  found afterwards.
  - *How much the 2020 definition moves states against each other.* With rural share standardized across states
    within each year, the typical state moves 0.10 standard deviations between the 2000 and 2010 censuses and 0.09
    between 2010 and 2020. So states moved against each other no more across the 2020 change than in the decade
    before. This is all movement, not the definition's effect alone (which the Bureau puts at about a point
    nationally), and it matters only if EC-5 standardizes each year's states separately.
  - *One set of urban boundaries held over time* (overlaying older boundaries on newer blocks, or a series
    standardized to one census's urban areas). The yearly survey appears to do this already, and it shows the
    cost: rural share climbs every year and drops back in 2012 to the 2010 census's figure. Nationally 24.5% in 2011
    and 19.2% in 2012; Nevada 14.0% in 2005, 24.5% in 2011, 5.9% in 2012 (5.8% in the 2010 census). The climb is
    steepest in the fastest-growing states and nearly flat in Ohio and Pennsylvania, which fits building spreading
    past a fixed boundary; the Bureau's documentation of the earlier years was not read.
  - *Counties classed as metropolitan or not by one vintage of the USDA's rural-urban continuum codes*, with county
    populations by year. Stable over time (0.993 between 2000 and 2020) and free of both breaks, but a different
    measure: 0.86 with the census's rural share and 0.83 with The Downballot's. Wyoming is 69% non-metropolitan and
    38% rural; New Jersey is 0% and 6%. A trial only: the 2023 codes, census-year populations, the two-way split
    and the largest metropolitan class, with about 1% of the population in counties that did not match.
  - *The census in force at each election* (2000 for 2000 to 2008, 2010 for 2012 to 2020, 2020 for 2024 and 2028).
    Each year's states are then measured one way, and the scored elections never meet the 2020 definition. The 2010
    classification was published in March 2012 and the 2020 one in December 2022, so nothing is taken from after an
    election except in 2000, a fit-only year. It gives rural share only, with no urban against suburban split.

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

**Stage 4: amendments after the code review, before any loss was read** (`src/model/pres_thin_states.py`).

- **What method 3's scramble tests.** It shuffles the movement term between states, so it asks whether matching the
  movement to each state's own gap since its last poll matters. It does not ask whether adding national movement
  helps at all.
  - The terms do differ between states. Within an election and date their spread is mostly as large as their mean
    size (for example 2.08 against 2.97 in 2016 at 100 days).
  - A few cells are tight: 2008 at 7 days, 0.25 against 4.47; 2004 at 100 days, 0.44 against 1.05.
- **The sign-flip test's limits.**
  - Its 13 units are three dates of the same election, with largely the same states and the same national miss.
    They behave more like 5 units than 13, so p overstates the evidence.
  - It weights units equally, where the gain weights elections equally; 2020 has one date and the others three.
  - The election-level version (5 units; the smallest possible p is about 0.03) is reported beside it and decides
    nothing.
- **Behaviour checks, as run:**
  - method 1 equals national plus lean;
  - with no national movement, method 3 equals the baseline;
  - a planted national step after a state's last poll moves method 3 the right way and no further than the step,
    in both directions;
  - with every 2012 state poll set to its state's 2008 result plus 3 points, method 2 gives exactly the previous
    result plus 3 in the thin states.
- **Other checks, passed:**
  - 2024 is absent from the polls and the results;
  - the leak and deletion tests (scored set, polled set and every forecast unchanged);
  - changing the scored election's results leaves every forecast unchanged.
- **Method 2 with no recently polled state** falls back to the prior.
- **Also reported:** diagnostic (a)'s mean signed error by election, and each method's error on the states it
  actually changes.

### Stage 4: results (run 2026-11-21). None of the three passes.

`src/model/pres_thin_states.py run`, `data/processed/pres_thin_states.json` (and the per-state table
`pres_thin_states_table.csv`).

| | Score (150/100/60) | 2004 | 2008 | 2012 | 2016 | 2020 | 30 days | 7 days | Test | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline (own polls, however old) | 61.7 | 43.7 | 69.2 | 52.3 | 116.2 | 27.1 | 52.8 | 69.5 | | |
| 1. Prior (national + lean) | 64.3 | 34.1 | 143.7 | 30.5 | 102.3 | 11.0 | 55.5 | 95.8 | p 0.68 | fails |
| 2. Average swing | 68.3 | 36.0 | 145.2 | 30.9 | 109.4 | 19.7 | 61.5 | 97.8 | p 0.78 | fails |
| 3. Carry-forward (14-day) | 59.2 | 44.0 | 71.4 | 52.9 | 97.4 | 30.6 | 51.3 | 58.5 | 97% of shuffles | fails |

The score is the mean of the five elections' columns.

- **1. The prior** is better in 4 of 5 elections, often by a lot (2012: 30.5 against 52.3; 2020: 11.0 against 27.1).
  But it is far worse in 2008 (143.7 against 69.2) and at 30 and 7 days. Overall −2.63, sign-flip p 0.68 (0.53
  with elections as units). 2008's thin states moved toward Obama well beyond their 2004 lean: mean signed error −6.1
  in states with no recent poll.
- **2. The average swing** fails in the same way, worse (−6.56).
- **3. Carry-forward** gains 2.43, beats 97% of its shuffles, and is better at 30 and 7 days. But it is better in only
  1 of 5 elections (2016, 97.4 against 116.2); the other four are slightly worse. So it fails.
  - Its flag would also have applied: in the states it is scored on, the old polls beat the prior in only 46% of
    cases.
  - The 60-day version (reported only) gains 1.18 and is better in 4 of 5.
- **States each method changes:** methods 1 and 3 change the 171 scored state-dates that have old polls, method 2
  all 250. On those, the error is 68.4 for the baseline against 66.4 for the prior and 62.1 for carry-forward.

**The user's selection question.**

- **(a) Thinly polled states do not land closer to their no-poll forecast; they land further.**

  | Polls in the previous 30 days | 0 | 1 to 3 | 4 to 9 | 10 or more |
  |---|---|---|---|---|
  | Prior's squared error | 66.3 | 34.7 | 26.1 | 17.4 |
  | State-dates | 250 | 388 | 110 | 17 |

  - The 0 group is furthest in every election but 2020, where all groups are close.
  - The signed errors show why: states that pollsters skipped moved off their old lean by more. They moved toward
    the Democrat in 2008 (−6.1) and toward the Republican in 2016 (+7.1).
  - So pollsters do skip lopsided states, but lopsided states are where the lean shifts most between elections.
  - Being unpolled is not evidence that the prior is right.
- **(b) The few polls in thin states do worse than the prior.**
  - Where a state had 1 to 3 recent polls, its own nowcast was closer to the result than the prior in 43% of 388
    cases. Its squared error was 42.7 against the prior's 34.7.
  - By election, the share closer was 49% (2004), 59% (2008), 43% (2012), 46% (2016) and 22% (2020). Only 2008, the
    year the leans moved most, favoured the polls.
  - That fits the user's suspicion that lone polls in thin states are noisy or selected. It also says a thin
    state's estimate should lean on the prior more than the baseline does.
- **(c) Sponsored against independent:** only 3 sponsored polls appear among the old polls of thin states (all
  2020). Not possible, as expected.

**Stage 4 closed.** One round, as agreed. **Thinly polled states keep the baseline**: their own polls however old,
or the prior if they have none.

**Pointers for later, deciding nothing now:**

- **Blend polls with the prior by how much polling there is.** The diagnostics argue for a weighted blend of a
  state's polls and its prior, with the poll weight growing with the number of recent polls. That needs a fitted
  weight, so it belongs where section 4's model combines prior and polls.
- **Watch the lean.** The prior's failures are years when leans moved: 2008, and 2016 in lopsided states. A prior
  that allows the lean to move (from demographics, DA-4, or a trend in lean over two elections) would address what
  the thin states got wrong.
- **Carry-forward** came close (97% of shuffles, better at 30 and 7 days) but won only 1 election of 5.

**Stage 4, a pointer for EC-4 (in-sample, written 2026-11-21 after the results; decides nothing).** The user asked
whether unpolled states should lean more on the prior.

- At 150, 100 and 60 days, a mix of a state's own polls and the prior (national plus lean) was scored at every
  weight from 0 to 1 against the same results. The best weight was chosen after seeing them, so these are not tested
  numbers:

  | States | Cases | Polls only | Prior only | Best mix | Best weight on prior | By election |
  |---|---|---|---|---|---|---|
  | No recent poll, old polls only | 171 | 68.4 | 66.4 | 47.1 | 0.50 | 0.20 (2008) to 0.85 (2020) |
  | 1 to 3 recent polls | 388 | 42.7 | 34.7 | 26.3 | 0.60 | 0.40 to 0.85 |
  | 4 to 9 recent polls | 110 | 27.0 | 26.1 | 24.0 | 0.55 | 0.0 to 1.0 |

- **What it says:**
  - The baseline gives the prior no weight once a state has any poll. That is too little where polling is thin
    or light; a roughly even mix cuts the error by about a third there.
  - The weight moves a lot between elections, so it should come from each side's uncertainty, not be fixed.
  - The gain fades as polls accumulate.
  - The prior is weakest where the lean shifts most (lopsided states, and 2008).
- **Where it goes:** EC-4 (state prior and weight on polls). There the weight on polls is estimated on earlier
  elections only and tested under section 8, and a prior that lets the lean move is a candidate.

### Stage 5: the add-up, pre-registration (written 2026-11-21, before any run; confirmed by the user the same day, with the score amended below)

Section 4 puts states first: the popular vote is the vote-weighted sum of the state estimates, and the gap between
that sum and the national estimate is only reported. Stage 5 tests the plan's one alternative: national polls set
the popular vote, and the gap is spread over the states by their uncertainty and size, so large, thinly polled
states absorb most of it. Stage 3 also left a question here: how its raw-margin scaling applies to states.

**Test bed.** State polls 2004 to 2020 (stage 1's loader; 2024 refused, and no 2024 result row read), the national
series, and `state_presidential.csv`.

- Every state and DC is scored. Maine's and Nebraska's districts are left out, having no results.
- Dates are 150, 100 and 60 days (scored) and 30 and 7 (reported), as in stages 2 to 4.

**Pieces, all as the earlier stages left them:**

- **State estimates, states-first:** each state's nowcast from its own polls, however old, or, with none yet, the
  prior (national two-party nowcast plus previous lean). That is stage 4's outcome.
- **National estimate:** stage 3's adopted forecast, the national nowcast × (1 − u/100), with u the undecided share
  averaged like the nowcast.
- **Vote weights:** each state's share of the two-party vote at the previous election.
- **A state's uncertainty, for spreading the gap:** σ²_s = 1 / (1 + n_s), where n_s is the number of the state's
  polls in the 30 days before the date. It has no fitted number, and only its relative size matters. An unpolled
  state has the largest.

**Baseline (section 4, states first).** State margins are the state estimates; the popular vote is their
vote-weighted sum. The gap to the national estimate is reported on every date.

**Candidates.**

- **A. National polls set the popular vote.**
  - The gap D = national estimate − the states' vote-weighted sum is spread so that the new sum equals the national
    estimate exactly.
  - Each state moves by D × σ²_s / Σ_j (v_j × σ²_j). So a state's share of the correction is in proportion to its
    vote share times its uncertainty.
- **B. Stage 3's scaling applied to every state, states first.** Each state's margin × (1 − u/100), with u the
  national undecided share. The popular vote is still their sum.
  - Only a national u exists for every year: state polls' undecided shares are not kept consistently. So this
    scales every state alike.
  - B has nothing to shuffle across states.
- **C. Every state moves by the same amount** so that the sum meets the national estimate. This is the alternative
  section 4 names. Its "blend of itself and N" is set to N in full, as in A, so A and C differ only in how the gap
  is spread. C has nothing to shuffle.
- **Reported only:** A with the national two-party nowcast in place of stage 3's forecast. This separates spreading
  the gap from the scaling.

**What the gap is made of** (no results used). Two parts:

- The national two-party nowcast minus the states' vote-weighted sum: state and national polls disagreeing. This
  ranges from −1.08 to +2.50 across the 25 election-dates.
- Stage 3's scaling: −0.06 to −1.14.

The scaling is the larger part only in 2016, where u was 16 to 18. So A and C mostly decide how far state polls are
pulled toward national polls, and only partly where stage 3's shift lands. Typical moves:

| | 2004 | 2008 | 2012 | 2016 | 2020 |
|---|---|---|---|---|---|
| A, mean absolute shift | 0.1 to 1.2 | 0.3 to 3.0 | 1.1 to 2.0 | 1.6 to 2.6 | 1.2 to 2.5 |
| B, mean absolute shift | 1.2 to 1.8 | 1.3 to 1.7 | 1.2 to 1.5 | 2.7 to 3.1 | 1.2 to 1.7 |

σ²'s coefficient of variation across states within an election and date is 0.3 to 1.0, so A's shuffle can pass
or fail. It is lowest in 2020 at 7 days.

Previous-election vote weights are adequate: the weighted sum of each year's actual state results lands within 0.17
points of the national result.

**Score.**

- State margins: the squared error, averaged over the 51 on each date, then over 150, 100 and 60 days, with
  elections weighted equally.
- 30 and 7 days must not be worse on average.
- The popular vote's error, and a vote-weighted state score, are reported beside it.

**The rule (section 8 on the state test bed, as stage 4 applied it).**

- A positive gain, and at least 4 of 5 elections better.
- **A:** σ² shuffled across states within each election and date, 200 times; the gain must beat 19 in 20. This asks
  whether spreading by uncertainty matters, not whether the national estimate helps at all.
- **B:** a paired sign-flip test over election-date units, at p < 0.05, as for stage 4's methods 1 and 2. Its limits
  are the same: about 13 units that behave more like 5, and an election-level version reported beside it.
- **C:** the sign-flip test, as for B.
- **Sign-flip units:** every state is scored on every date, so there are 15 election-date units at 150, 100 and 60
  days.
- **If more than one passes:** A and C are alternatives, and the larger gain is adopted. B can join either (A or C
  after B's scaling). A combination is adopted only if it passes the same clauses; otherwise the largest single gain.
- **None passes:** section 4's states-first rule stands.

**Reported, so B and the others are not over-read.**

- B's shift is in proportion to the margin, so it is near zero in close states and largest in lopsided ones, which
  drive an equally weighted score. Close states (forecast margin under 10 points) and lopsided ones are reported
  apart.
- Shrinking toward a tie helps one party's states and hurts the other's, depending on the year's shared miss.
  Results are reported by the leading party's states, and with each year's mean error removed.
- Every candidate is reported by election. 2016's u (full-field questions) makes B much larger that year.

**Provisional.** The states-first baseline is a stand-in. Section 4's state estimate blends polls with the prior,
and that blend is EC-4's work, which does not exist yet. Stage 4's pointer says EC-4 will move thin states a lot
and pull the states' sum toward the national estimate. So a verdict here holds until EC-4's estimates exist
(question 6).

**Checks before any loss is read.**

- 2024 is absent.
- The leak, deletion and own-results tests, as in stage 4.
- Behaviour:
  - A's new vote-weighted sum equals the national estimate exactly;
  - with D = 0 nothing moves;
  - with equal σ², every state moves by D, which is C;
  - B with u = 0 is the baseline.

**Questions for the user:**

1. **Three candidates, A, B and C, where the plan has one.** C is section 4's named alternative (an even shift). B
   answers stage 3's open question within this stage.
2. **The score:** state margins, equally weighted over the 51, with the popular vote and a vote-weighted score
   reported. The alternative is to put the popular vote into the score.
3. **σ²_s = 1 / (1 + recent polls),** no fitted number. The full model's spreads (section 4) do not exist yet.
4. **The rule as above:** a shuffle for A; a sign-flip for B and C; 4 of 5; positive gain; 30 and 7 days not worse.
5. **One round.**
6. **Retest after EC-4.** Proposed: stage 5's verdict is provisional and is rerun once EC-4's blended state
   estimates exist, with the same pre-registration.

**Stage 5: demographics considered and moved to EC-5 (2026-11-21, before any run).**

- **What was asked.** The user asked whether candidate A should spread the gap by more than uncertainty: by
  demographics, fitted on how past national-state disagreements lined up with age, race and education.
- **Why it moved.** On reflection the user judged that demographics may matter, but not through this mechanism.
  2016's state polling errors were correlated across states, yet they did not come from the national polls
  missing.
- **Where it went.** So the question belongs with how state errors move together. It is recorded on EC-5, which now
  waits for DA-4 (demographics by year), so it is tested on demographics as they stood in each election rather than
  one late-2010s snapshot.
- **What stays here.** Candidate A stays as written, spreading the gap by vote share and uncertainty.

**Stage 5: confirmed by the user on 2026-11-21, with the score amended (before any run).**

- **Confirmed as written:**
  - three candidates (A, B, C);
  - σ²_s = 1 / (1 + recent polls);
  - A's shuffle, and the sign-flip test for B and C;
  - 4 of 5 elections better, and a positive gain;
  - one round;
  - the verdict provisional until EC-4's state estimates exist, then rerun with this pre-registration.
- **The score, amended at the user's direction.** Results blur many causes over long gaps, and the add-up is not to
  blame for the shared national miss.
  - **Dates:** only 30 and 7 days are scored. 150, 100 and 60 are reported. 14 and 7 were considered; with a 60-day
    half-life, those two averages share most of their polls.
  - **Loss:** for each state on each scored date, excess = max(0, |state error| − |national error|), squared and
    averaged over the 51 states, then over the two dates, with elections weighted equally.
  - **The national error** is stage 3's national forecast against the national result, the same for every
    candidate. A state that misses by no more than the nation costs nothing.
  - The plain squared error is reported beside it.
  - With 30 and 7 days now the score, the "30 and 7 days not worse" clause falls away.
  - The sign-flip units are 10 (5 elections × 2 dates).
- **Turnout, a known limit (raised by the user).**
  - Every add-up weights states by their share of the previous election's two-party vote, so differential turnout
    never enters. Applied to the actual results, the previous election's weights put the popular vote 0.1 to 0.2
    points off the actual weights' figure (−0.17, +0.09, +0.11, −0.17 and −0.17 for 2004 to 2020). That is 10 to
    15% of the typical gap stage 5 is about.
  - The largest change in one state's share in a cycle is 0.34 to 0.73 points (California in 2020).
  - It enters twice: in the sum the states are reconciled to, and in how A spreads the gap.
  - It is reported beside the results and carried to EC-6, where a forecast of each state's turnout share is a
    candidate.

**Stage 5: amendments after the code review, before any loss was read** (`src/model/pres_addup.py`).

- **What the excess score cannot see.**
  - The allowance (the national forecast's miss) is the same for every candidate, and A and C are built to hit the
    national forecast.
  - When that forecast is wrong and the state polls were right, A and C pull states toward the wrong number, and the
    allowance forgives most of that. When the forecast is right, they get full credit.
  - So the score is lenient to A and C on their main risk.
  - The national miss also differs by election, larger in 2016 and 2020, so elections are not on the same footing.
    Each election's national error is reported beside its loss.
  - For every candidate, the same clauses are computed on the plain squared error, by election. This is reported
    and decides nothing, unless the user decides otherwise (question below).
- **The sign-flip units** are 10: five pairs of dates from the same election, which behave more like 5. The
  election-level version is reported.
- A's sign-flip p is reported, and C's shuffle is not defined; neither decides anything.
- 30 and 7 days are reported separately.
- **Checks, run and passed:**
  - A and C sum exactly to the national forecast on every election and date.
  - On the code's own output: A's shift always has the gap's sign and is larger for states with fewer recent
    polls, and C moves every state by the gap.
  - With D = 0 nothing moves.
  - With u = 0 throughout, B equals the baseline.
  - The leak and deletion tests pass, as does changing the scored election's results.
  - 2024 is absent from the polls, the results and the national series.

**Stage 5: the flag, decided by the user on 2026-11-21 before any run.** A candidate that passes on the excess score
but is worse than the baseline on the plain squared error (mean over elections at 30 and 7 days) is flagged, and the
pass goes to the user. An unflagged pass is adopted under the rule. The same holds when stage 5 is rerun after EC-4.

### Stage 5: results (run 2026-11-21). C passes and is adopted, provisionally.

`src/model/pres_addup.py run`, `data/processed/pres_addup.json` (and `pres_addup_frame.csv`).

| | Excess score (30 and 7 days) | 2004 | 2008 | 2012 | 2016 | 2020 | Elections better | Test | Plain squared error | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline (states first) | 20.46 | 10.09 | 13.75 | 14.40 | 48.47 | 15.57 | | | 36.64 | |
| A. Spread by uncertainty | 16.75 | 10.42 | 10.67 | 17.11 | 34.41 | 11.14 | 3 | 90.5% of shuffles (needs 95%) | 30.88 | fails |
| B. Scale every state | 29.60 | 15.79 | 22.59 | 18.28 | 70.83 | 20.51 | 0 | p 1.0 | 48.00 | fails |
| **C. Even shift** | **16.82** | 9.18 | 11.31 | 15.13 | 36.81 | 11.66 | **4** | **p 0.012** | **31.08** | **passes** |

The excess score is the mean of the five elections' columns. The national forecast's miss, which is each state's
allowance, averaged 0.7 (2004), 3.3 (2008), 1.4 (2012), 1.7 (2016) and 3.2 (2020) at 30 and 7 days.

**C passes, and no flag applies, so it is adopted under the rule, provisionally until the rerun after EC-4.**

- Its gain is 3.64, better in 4 of 5 elections (2012 slightly worse), with sign-flip p 0.012 over the 10
  election-date units. The election-level version, reported only, is 0.062.
- It is also better on the plain squared error (31.08 against 36.64), in the same 4 elections, so the flag does
  not apply.
- It is better at every date, reported ones included: 27.5 against 33.5 at 150 days, 16.8 against 20.5 at 30, and
  16.8 against 20.4 at 7.
- **What it means.** The forecast popular vote is the national forecast (stage 3's: the national nowcast's raw
  margin), not the states' sum. Every state moves by the same amount so the states add up to it.
  - With each year's mean error removed, C equals the baseline (23.48 both). All of its gain is in the level the
    states share; it changes nothing between states.
  - The popular vote's squared error falls from 9.68 to 5.41.

**The others.**

- **A** gains about as much (3.71), but is better in only 3 of 5 elections and beats 90.5% of its shuffles. Spreading
  the gap by uncertainty adds a little error between states (24.57 against 23.48 with each year's mean error
  removed). So the gain comes from closing the gap, not from where it goes. Its sign-flip p, reported only, is
  0.047.
- **B** is worse in every election and at every date, mostly in lopsided states (39.4 against 25.3). Shrinking every
  state toward a tie does not carry stage 3's national finding down to the states. It is flagged as well.
- **A with the unscaled national nowcast** (reported) gains 2.69 against A's 3.71. So stage 3's scaling helps when
  it enters through the national total.

**Where the gain is.** Close states 9.38 against 12.74; lopsided 21.46 against 25.28. Republican-leaning states gain
more (37.5 against 45.3) than Democratic-leaning ones (24.6 against 27.9).

**Turnout.** As written beforehand, the vote weights are the previous election's, which puts the popular vote 0.1 to
0.2 points off each cycle. Carried to EC-6.

**Stage 5 closed.** One round, as agreed. **Section 4's states-first rule is replaced, provisionally, by C:** national
polls (stage 3's forecast) set the popular vote, and every state moves by the same amount to meet it. The verdict is
rerun with this pre-registration once EC-4's blended state estimates exist, since EC-4 will itself move the states'
sum toward the national estimate.

### EC-2's stages, closed (2026-11-21)

What the five stages fixed, for the forecast from poll averages to election day:

1. **The nowcast** is the Senate average's weighting (stage 1).
2. **No convention treatment** (stage 2).
3. **The national forecast** is the nowcast's raw margin: the two-party margin × (1 − u/100) (stage 3; a narrow
   pass).
4. **Thinly polled states keep their own polls**, or the prior if they have none (stage 4).
5. **States move together** to meet the national forecast (stage 5; provisional).

Open items, carried forward:

- **The registered-voter lean** stays in the nowcast, though the 2020 paired questions point the other way (stage 1).
- **The range** is refitted around the adopted forecast when the model is assembled (stage 3).
- **Head-to-head or full-field questions** for the undecided share in 2028, and a third candidate (stage 3;
  section 10).
- **The pollster-quality weight** passed in 2024 and is deferred until 2028's ratings are known, or the repo's own
  tiers from 2026 exist (DA-10).
- **Blending a state's polls with its prior,** with a lean that can move (EC-4, from stage 4).
- **Demographics in how state errors move together** (EC-5, after DA-4).
- **Each state's turnout share** in the popular vote (EC-6).
- **Stage 5's rerun** once EC-4 exists.
  - Done 2026-11-21: the even shift passes again on EC-4's estimates (section 13, "Stage 5's rerun after EC-4").

## 12. Presidential fundamentals: evaluation plan (EC-3)

*Plan written 2026-11-21, before any fit; confirmed by the user the same day (decisions below).* The fundamentals give the national
estimate a prior that does not depend on polls. Section 4 combines that prior with the poll average by precision.
EC-2's stage 3 tried a crude version (approval plus the previous result) and it failed as built.

**2028 is a case the history has never seen.**

| Terms the incumbent party has held | Sitting president running | Not running |
|---|---|---|
| One | 9 elections | **none (2028; and 2024, held out)** |
| Two or more | 2 (1976, 1992) | 7 |

- 2028 is one term with no president running. "Time in office" says no penalty; "a sitting president running" says a
  penalty. Only 1976 and 1992 separate the two codings.
- The classic coding, "a first-term president running", treats 2028 like a long-held seat.
- So the 2028 fundamentals depend on which coding a model keeps. It is reported under each coding, and selection is
  not allowed to choose among them silently.

**What is predicted.**

- The incumbent party's national two-party margin, 1952 to 2020 (18 elections). 1948 is added only where every
  predictor exists.
- 2024 is refused at load (the result history holds it) and scored once at the design freeze (section 7).
- Turned into the Democratic margin by the president's party, as in stage 3.

**Candidate predictors.**

| Predictor | Measure | From |
|---|---|---|
| Approval | Gallup job approval: mean of readings ending in the 30 days before the date, else the latest one | 1948 |
| The economy | one of: real GDP growth over the latest two published quarters; real disposable income per head, growth over the latest published year; the change in unemployment over the latest year | GDP 1947, income 1959, unemployment 1948 |
| Time in office | one of three codings: one term against two or more; a sitting president running; a first-term president running | all |

The previous result is not a candidate; the card does not list it, and stage 3's version failed.

**As of a date.** Only figures published by the date are used.

- **Publication lags:**
  - a GDP quarter counts from 35 days after the quarter ends;
  - an income month from 35 days after the month ends;
  - an unemployment month from 10 days after it ends.
- **A gate** checks that changing not-yet-published periods changes nothing.
- **Revisions.** GDP and income are revised, and the repo's copies are today's vintage. Real-time vintages (ALFRED)
  are checked for coverage before any fit. Where they exist they are a check; elsewhere the limit is stated.
- **Approval after January 2021.** The Gallup file ends then. A source for 2024's scoring and for 2028 is written
  down before 2024 is scored.

**Small-sample rules.**

- **One primary model, written down in advance** (question 2), fitted with ridge shrinkage toward approval alone.
  Every model of up to three predictors is reported as "how far the choice of predictors moves the answer". It is
  compared on a common sample (1960 on wherever income enters) and decides nothing.
- **Nested as-of fitting.** Every choice made from data (the shrinkage penalty, any weights) happens inside each
  as-of fit, using earlier elections only. Each earlier election's fundamentals error, used for the weights and the
  standard error, comes from a fit that left that election out.
- **Thin early fits.** 1980's fit has 7 earlier elections (5 where income enters). The ridge penalty carries this:
  with few elections it holds the model near approval alone. Or there is a burn-in (question 3).

**Tests.**

1. **The fundamentals alone** (reported). Leave-one-out error of the primary model, of every model of up to three
   predictors, of a constant (the average incumbent margin) and of approval alone. Plus the 2028 case under each
   time-in-office coding.
2. **Do they improve the forecast?** This decides adoption.
   - At 150, 100, 60, 30 and 7 days, EC-2's adopted national forecast (the poll average's raw margin) is combined
     with the primary model by precision.
   - The polls' precision comes from the fitted range (a + b × days); the fundamentals' from their nested
     leave-one-out error. Both are fitted on earlier elections only.
   - It is scored against results on EC-2's national test bed, 1980 to 2020, under the rule for stages 2 to 4: a
     positive gain; better in 8 of 11; beat 19 in 20 shuffles of the fundamentals between elections; 30 and 7 days
     not worse.
   - **A control row:** the polls blended with a constant prior (the earlier elections' average incumbent margin),
     at the same precision rule. Stage 3 showed that shrinking toward a centre helps by itself. The shuffle asks
     whether the fundamentals add to that.
3. **Open seats** (reported; a candidate only through test 2). Whether approval counts for less when no president is
   running: an interaction, shrunk toward none.

**If test 2 fails,** section 4's national estimate is the polls alone (EC-2's forecast), and the fundamentals stay a
reported number.

**Questions for the user:**

1. **The outcome:** the incumbent party's two-party margin 1952 to 2020, 1948 only where every predictor exists, 2024
   refused?
2. **The primary model.** Proposed: approval, real disposable income growth (the measure most models use, 1960 on),
   and one time-in-office coding. Which coding? The choice decides 2028:
   - two or more terms (2028: no penalty);
   - a sitting president running (2028: a penalty);
   - a first-term president running (2028: treated like a long-held seat).
3. **Thin early fits:** ridge toward approval alone, or a burn-in (score from 1988, needing two thirds of 9)?
4. **Revised data:** today's vintage, with ALFRED as a check where it exists, and the publication lags above?
5. **The tests:** test 1 reported; test 2 decides, with the constant-prior control row?
6. **Open seats** reported, and a candidate only through test 2?
7. **One round per test,** written down here before each run, as for EC-2?

**EC-3: decisions of 2026-11-21 (before any fit).**

1. **The outcome** as proposed: 1952 to 2020, 1948 only where every predictor exists, 2024 refused.
2. **Time in office: one coding, "a term-limited incumbent"** (the user's).
   - It is 1 when the sitting president has already won two elections and cannot run: 1960, 1988, 2000, 2008,
     2016 and 2028. Consecutive and non-consecutive terms are not told apart, since the history is too sparse;
     2028 is coded like 2008 and 2016.
   - 1952 and 1968 are coded 0. Truman was exempt from the two-term limit and Johnson had won only once; both
     chose not to run.
   - The variant "no sitting president on the ballot", which differs only in those two years, is reported beside
     it and decides nothing.
   - The other codings in the plan are dropped.
3. **Thin early fits:** shrink, and use all the data. Ridge toward approval alone, no burn-in.
4. **Revised data:** today's vintage, with ALFRED as a check where it exists, and the publication lags as written.
5. **The tests:** test 1 is reported; test 2 decides, with the constant-prior control row.
6. **Open seats:** reported, and a candidate only through test 2.
7. **One round per test,** each written down here before it runs.

**Still open: the economic measure.** The user would consider inflation, gas prices and unemployment as well as
income and GDP. With approval and the term-limit flag, one slot remains. Proposed: a composite of the five
(standardized, equal weights, signs fixed in advance: income growth and GDP growth +, the rise in unemployment,
inflation and real gas-price growth −). The alternative is picking one measure inside each as-of fit.

**EC-3: the economic measure, decided 2026-11-21 (before any fit).**

- **A composite index of six measures**, equal weights, signs fixed in advance:

  | Measure | Series | Sign | From |
  |---|---|---|---|
  | Real disposable income per head, growth over the latest published year | A229RX0 | + | 1959 |
  | Real GDP growth, mean of the latest two published quarters | A191RL1Q225SBEA | + | 1947 |
  | Change in unemployment over the latest year | UNRATE | − | 1948 |
  | Inflation over the latest published year | CPIAUCNS | − | 1913 |
  | Real gasoline price growth over the latest year | CUUR0000SETB01 / CPIAUCNS | − | 1935 |
  | S&P Composite, change in the monthly average over 12 months | Shiller (store-and-link) | + | 1871 |

- **The S&P** was the user's addition. FRED keeps only ten years of the S&P 500 and the Dow, so the history is Robert
  Shiller's monthly series. The copy fetched ends in September 2023; a newer copy is needed before 2024 is scored
  or 2028 is forecast.
- **Standardizing.** Each measure is standardized against its own monthly history from 1948 up to the date (never
  later data). The index is the mean of the signed standardized values available on the date. 1952 and 1956 have no
  income figure, so their index averages the other five.
- **Why equal weights over PCA:**
  - PCA weights measures by how much they move together, not by what voters respond to. It would turn the index into
    a growth factor and mostly drop inflation and gas prices.
  - On 15 to 18 elections its loadings (even their sign) would shift between as-of fits.
  - Equal weights are fixed before any data is seen.
  - The PCA version (first component of the monthly standardized series, on data before each date, signed so that
    income growth loads positively) is reported in test 1 and decides nothing.
- **Publication lags:**
  - income, CPI and gasoline months count from 35 days after the month ends;
  - a GDP quarter from 35 days after the quarter ends;
  - an unemployment month from 10 days after it ends;
  - an S&P month from the day after it ends.

### EC-3, test 1 (reported) and test 2 (decides): pre-registration (written 2026-11-21, before any fit)

**The primary model.** The incumbent party's two-party margin = a + b1 × (approval − 50) + b2 × economic index +
b3 × term-limited.

- a and b1 are unpenalized. b2 and b3 carry a ridge penalty, so the model shrinks toward approval alone.
- The penalty is chosen by leaving one election out at a time, among the elections the fit uses.
- Approval is Gallup's mean over readings ending in the 30 days before the date, or else the latest reading.
- Dates: 150, 100, 60, 30 and 7 days before each election. Each date has its own inputs and its own fit.

**Test 1, the fundamentals alone (reported, deciding nothing).** At each date, on 1952 to 2020:

- the leave-one-out error of:
  - the primary model;
  - a constant (the average incumbent margin);
  - approval alone;
  - every model of up to three predictors drawn from approval, term-limited, the index, the PCA index and each of
    the six measures alone, on the common sample 1960 to 2020;
- the primary model with "no sitting president on the ballot" in place of term-limited;
- the fitted coefficients, and what term-limited does to the 2028 prediction (its coefficient), with its uncertainty.

**Test 2, does it improve the forecast (decides adoption)?**

- **Scored elections.** 1980 to 2020 on EC-2's national test bed. Each is fitted only on the elections before it,
  from 1952, with every choice inside that fit (the ridge penalty, the weights).
- **The forecast.** At each date: (stage 3's forecast) × w + (fundamentals) × (1 − w), with
  w = 1/V_polls ÷ (1/V_polls + 1/V_fund).
  - V_polls is the stage 2 range (a + b × days), refitted on the earlier elections' errors of stage 3's forecast.
  - V_fund is the mean squared error of the fundamentals on the earlier elections, each from a fit that left that
    election out.
- **The score.** Squared error against the result, averaged over 150, 100 and 60 days, elections equal.
- **The rule (stages 2 to 4):**
  - a positive gain;
  - better in at least 8 of 11;
  - beat 19 in 20 of 200 shuffles, in which each election's fundamentals inputs (approval, the index and the
    term-limited flag, in the incumbent party's terms) are handed to another election from 1952 to 2020, with the
    fit redone inside;
  - 30 and 7 days not worse on average.
- **A control row,** deciding nothing: the same blend with a constant prior (the earlier elections' average
  incumbent margin) in place of the fundamentals. The shuffle asks whether the fundamentals add to that.
- **Open seats** (reported): the primary model plus approval × term-limited, shrunk toward none.

**If test 2 fails,** section 4's national estimate is stage 3's poll forecast alone, and the fundamentals stay a
reported number.

**Checks before any result is read.**

- 2024 is refused.
- Publication: changing not-yet-published months and quarters changes no input.
- As-of: changing a scored election's result and every later election leaves its fit unchanged.
- Behaviour:
  - a planted relation is recovered;
  - with a huge penalty the model is approval alone;
  - with V_fund huge the forecast is stage 3's;
  - the index is the mean of the signed standardized values.

One round per test.

**EC-3: amendments after the code review, before any result was read** (`src/model/pres_fundamentals.py`).

- **When a measure counts.** It needs at least two years of published history by the date. Income's yearly change
  begins in 1960, so 1952, 1956 and 1960 have no income figure (not only 1952 and 1956 as written above). Their
  index averages the other five.
- **1948 is left out.** Its unemployment change would need 1947, which FRED does not hold, and it has no income
  figure.
- **The common sample for the full table** of models of up to three predictors is 1964 to 2020, where all six
  measures and the PCA index exist. The table reports every model, not the top ten, and where the primary model
  ranks. The constant, approval alone and the primary model are shown on that same sample.
- **The fundamentals' variance is nested.** Each earlier election's error comes from a fit that left it out, with the
  penalty chosen again inside that fit. Without this the variance is optimistic: on a check that reads no scored
  result, the weight on polls rose from 0.405 to 0.551 in 1980 at 60 days. This applies in the real run and in
  every shuffle.
- **Real-time vintages, coverage checked.** ALFRED holds as-published real disposable income (total, not per head)
  from about 1980 and real GDP from about 1991, but not the per-head income or the GDP growth series the index uses.
  Test 1 reports how far today's figures differ from the as-published ones for 1980 to 2020, at every date. That is
  a check on the size of revisions and decides nothing.
- **Further checks, passed:**
  - the two result sources (the Downballot history and the national series) agree exactly for 1952 to 2020;
  - in a Republican-held year the fundamentals enter as minus the incumbent prediction;
  - a huge fundamentals variance gives stage 3's forecast, and a huge poll variance the fundamentals.
- **Also reported:**
  - the term-limited effect unshrunk, beside the shrunk value and its penalty;
  - each as-of fit's count of term-limited elections (one in 1980's fit, 1960 alone);
  - the age of the approval reading by election and date.

### EC-3: results (run 2026-11-21). Test 2 fails on one clause, so the fundamentals are not adopted.

`src/model/pres_fundamentals.py test1` (`data/processed/pres_fundamentals_test1.json`) and `test2`
(`pres_fundamentals_test2.json`).

**Test 1, the fundamentals alone** (leave-one-out error, in points of margin, 1952 to 2020; reported):

| Days out | 150 | 100 | 60 | 30 | 7 |
|---|---|---|---|---|---|
| Constant | 11.06 | 11.06 | 11.06 | 11.06 | 11.06 |
| Approval alone | 7.01 | 5.99 | 7.03 | 6.73 | 6.80 |
| Primary (approval, index, term-limited) | 7.30 | 5.96 | 6.79 | 7.53 | 7.90 |
| Primary with "no sitting president" | 7.40 | 6.06 | 6.73 | 7.29 | 7.54 |

- **Approval carries the fundamentals.** It cuts the error from 11 to 6 or 7 points. The economic index and the
  term-limited flag add little on their own terms, and at 30 and 7 days the primary model does worse than approval
  alone.
- **The term-limited effect:** −0.6 to −3.4 points shrunk (penalties 10 to 100), −3.0 to −4.6 unshrunk. Leaving one
  election out moves it between about 0 and −6. So a term-limited incumbent's party does worse by a few points, but
  the estimate rests on five elections.
- **The full table (1964 to 2020, 175 models).**
  - The primary ranks 7th of 175 at 150 and 100 days, and 18th to 32nd later.
  - The best single models are approval alone (150 days) and approval + term-limited + the S&P (100 days and
    later, 5.3 to 6.1 points). That is chosen after seeing the table, so it is a pointer, not a result.
  - The index alone scores 7.7 to 9.3, the PCA version 9.4 to 9.5. Equal weights did no worse than PCA, and with
    approval the PCA does slightly better late (6.2 against 6.8 at 7 days).
- **Revisions.** Today's real income and GDP growth differ from the as-published figures by 1.3 points on average
  (up to 5.9 for income, 2.5 for GDP), over 95 cases from 1980 to 2020.
- **Approval** was at most 20 days old at 150 days, but up to 134 days old at 7 days (sparse Gallup years).

**Test 2, blended with the polls** (squared error, 1980 to 2020, each fitted on earlier elections):

| | 150 | 100 | 60 | 30 | 7 | Score (150/100/60) | Better | Shuffles beaten |
|---|---|---|---|---|---|---|---|---|
| Stage 3's poll forecast | 82.7 | 47.6 | 26.1 | 16.1 | 13.1 | 52.1 | | |
| **Blended with the primary model** | 45.7 | 20.4 | 19.7 | **17.4** | 10.5 | 28.6 | **8 of 11** | **100% (95th: 7.3)** |
| Blended with a constant (control) | 73.0 | 48.5 | 28.7 | 19.3 | 13.5 | 50.1 | 6 | |
| Primary + approval × term-limited (reported) | 52.1 | 24.0 | 15.9 | 12.5 | 10.0 | 30.7 | 7 | |

- **It fails the rule on "30 and 7 days not worse".** At 30 days its error is 17.37 against the polls' 16.14.
  Every other clause passes, by a wide margin:
  - the gain is 23.5;
  - it is better in 8 of 11 (1980, 1988, 1992, 1996, 2004, 2008, 2016, and 2000 by a hair);
  - it beats every one of the 200 shuffles.
  It is worse in 1984 (78.8 against 32.9), 2012 and 2020.
- **The fundamentals carry real information.** The constant prior gains only 2.0, in 6 of 11, so the gain is not
  just shrinkage toward a centre.
- **The weight on polls** is about 0.2 to 0.3 at 150 and 100 days, 0.4 to 0.5 at 60 and 30 days, and 0.65 to 0.77 at
  7 days. At 30 days the fundamentals still get about half the weight; that is where the blend loses.
- **The open-seat interaction** (reported, no shuffle run) keeps 30 and 7 days better (12.5 and 10.0) but is
  better in only 7 of 11. It is not a candidate that passed.

**EC-3 closed for this round.** One round, as agreed.

- The primary model fails test 2 on one clause, so **section 4's national estimate stays stage 3's poll forecast**.
- The fundamentals stay a reported number: approval-led, with a term-limited penalty of a few points and a
  leave-one-out error of about 6 to 8 points.
- Nothing is refitted after seeing these results. A second round would need new candidates written down first.
  The obvious one, a weight on the fundamentals that falls faster as the election nears, was suggested by these
  results, and that has to be said if it is tried.

### EC-3, round 2: pre-registration (written 2026-11-21, before any round 2 run)

Agreed with the user on 2026-11-21: one candidate, a weight on the fundamentals that falls faster as the election
nears. **It was suggested by round 1's results** (the blend lost at 30 days, where the fundamentals still had about
half the weight), so a pass here is weaker evidence than a candidate written down blind. That is stated with any
result.

**The candidate.**

- **The weight.** Round 1's weight on the fundamentals is (1 − w), where w is the polls' precision weight. Round 2
  multiplies it by (days / 150)^γ:
  - w' = 1 − (1 − w) × (days / 150)^γ;
  - at 150 days the weight is unchanged;
  - closer in, the fundamentals' share falls faster the larger γ is;
  - γ = 0 is round 1.
- **How γ is fitted.** From the grid 0, 0.25, 0.5, 1, 2 and 4, on the earlier elections only.
  - For each earlier election and date, the blend is built from that election's out-of-sample fundamentals
    prediction (its leave-one-out prediction within the fit, as already used for the variance), the polls'
    forecast, and the two variances.
  - γ minimizes the squared error over the earlier elections at all five dates (150, 100, 60, 30 and 7), so that the
    late dates count in the fit.
  - Ties go to the smaller γ.
- **Everything else is round 1's:** the primary model, its ridge penalty, the nested variance and the polls' range.

**The rule (stages 2 to 4), as in round 1:**

- a positive gain;
- better in at least 8 of 11;
- beat 19 in 20 of 200 shuffles of the fundamentals inputs between elections, with γ refitted inside each;
- 30 and 7 days not worse on average.

**Reported, deciding nothing:**

- γ picked for each election;
- a fixed γ = 1 (the weight falls in proportion to days);
- the constant-prior control with the same falling weight.

**Checks before any result is read:**

- γ = 0 reproduces round 1 exactly;
- with γ huge, the forecast is the polls' everywhere but at 150 days;
- γ's fit uses no scored election (as-of test).

One round. If it fails, EC-3 closes with the fundamentals reported and unused.

**EC-3 round 2: amendments after the code review, before any result was read.**

- **The 30-day clause is applied as written,** however small the difference, and the margin is reported. From
  γ = 2 up, the fundamentals' weight at 30 days is about 2% or less, so the blend and the polls may differ by
  hundredths of a point there. A tolerance would change the user's rule, so there is none.
- **Every piece of γ's fit must be finite.** It is checked: no poll forecast is missing at the five dates in any
  election from 1952 to 2020.
- **Limits, written now:**
  - 150 days carries no information about γ.
  - 1980's γ rests on 7 earlier elections and four informative dates.
  - Each earlier election's weight uses variances that include its own error.
  - These 11 elections suggested the candidate, so the only untouched test is 2024 at the design freeze.
- **Reported:** γ by election, with any pick at a grid edge (0 or 4) flagged, and the weight on polls at each date.
- **Checks, passed:**
  - γ = 0 reproduces round 1;
  - round 1's stored result reproduces exactly;
  - a huge γ gives the polls at every date but 150 days;
  - γ's fit uses no scored election;
  - on made-up pieces, noisy fundamentals pick the top of the grid and exact ones pick 0.

### EC-3, round 2: results (run 2026-11-21). It fails; EC-3 closes with the fundamentals unused.

`src/model/pres_fundamentals.py test2b`, `data/processed/pres_fundamentals_round2.json`.

- **γ came out at 0 in every one of the 11 fits**, the bottom edge of the grid. Measured on the earlier elections'
  out-of-sample pieces, a falling weight never helped. So the candidate is round 1 exactly, and it fails on the same
  clause: at 30 days its error is 17.37 against the polls' 16.14. Its other clauses pass as in round 1: gain 23.52,
  8 of 11, beats every shuffle.
- **Reported, deciding nothing: a fixed γ = 1** (the fundamentals' weight falling in proportion to days).
  - It would have passed every clause: gain 23.34, better in 8 of 11, and 30 and 7 days better (13.91 against
    16.14; 12.76 against 13.11).
  - But γ = 1 was not what the pre-registered fit chose, and it is reported only because round 1 suggested it.
    Adopting it now would be choosing after seeing the scored elections.
- **The constant-prior control with the same falling weight** gains 2.0 in 6 of 11, unchanged; its γ was 0 too.

**EC-3 closed (2026-11-21).**

- Two rounds; neither passes. **Section 4's national estimate stays stage 3's poll forecast.**
- **The fundamentals are reported, not used.** They are approval-led, with a term-limited penalty of a few points,
  and their leave-one-out error is about 6 to 8 points.
- Blended with the polls, they cut the error by almost half at 150 to 60 days in these elections, and lose only in
  the last month. **That is the case for revisiting them at the design freeze (EC-9).** A blend with a weight
  falling in proportion to days (γ = 1) can be written down as a candidate there and tested on 2024, the one
  election that has not shaped it, together with the rest of the model. It could not be adopted here.

## 13. State prior and weight on polls: evaluation plan (EC-4)

EC-2 left each state on its own polls, however old, with the prior used only where a state has no poll at all.
Stage 4's diagnostics said that gives the prior too little weight. EC-4 tests how a state's polls and its prior
should be mixed, and whether the prior's lean should be allowed to move.

### EC-4: pre-registration (written 2026-11-21, before any run; the owner's review done and all eight questions confirmed by the user the same day)

Nothing below has been run. The only numbers in it are counts of polls, taken without results.

**How blind this test is.** Not very, and that is said first.

- **Stage 4's pointer** already scored fixed mixes of polls and prior on 2004 to 2020 at 150, 100 and 60 days,
  in-sample. It found a roughly even mix best where polling was thin and the benefit fading at 4 or more recent
  polls.
- **The overfitting challenge** (the owner's name for it) is an off-tracker search by another agent, kept outside
  this repo. It looked with hindsight for a model that calls 2012, 2016 and 2020. Its log was read on 2026-11-21,
  before this draft, at the owner's direction. The card's gate had placed that reading after the draft.
  - The EC-4 card's entries from stage 4 were on `main` before the reading (commit `49e5a1a`, merged with PR #47):
    a weight from each side's uncertainty that grows with the number of recent polls, a lean that can move, and a
    wider range for lopsided states.
  - **What the log showed that bears on this card.** One state-level correction, which it calls the poll swing:
    every polled state pulled part of the way back toward last election's lean, with one fitted weight. Fitted on
    earlier elections only, it cut the state error in 2012, 2016 and 2020, at 7, 30, 60 and 100 days and in each
    of the three elections. The fitted pull was 12% to 46% depending on the fit.
  - **What comes from it here.** Rung 1 below, a fixed weight for every polled state, is declared as **suggested
    by the overfitting challenge**. So is the report of the gain by poll count: the challenge found a gain across
    all polled states where stage 4 saw it fade.
  - **What does not.** Its demographic term (polls overstate the Democrat where white adults without a degree are
    many) is not a candidate here. Its data is one 2015-19 snapshot, and it belongs with EC-5 once demographics
    by year exist (DA-4). Its election-level shifts and its pull toward fundamentals give this card nothing.
  - **Also seen, shaping nothing.** The log has a table of Senate polling misses by cycle that includes 2024
    Senate slopes on the poll swing and on the demographic term. No 2024 presidential poll or result appears in
    the log or its code. The table also covers the 2026 Senate races, on the scorecard's provisional margins; no
    number from it is given here (added at the user's direction, 2026-11-21).
  - **Bearing on rung 3.** Its search list included a two-election lean trend; the log reports no result for it.
    The log does report a fitted slope on the previous lean beside the poll swing: the state error at 7 days fell
    from 5.57 to 5.37. That bears on the slope b1 below, so the slope is declared as touched by the challenge.
- **So what is new in this test:** 2004 and 2008 as scored elections for the fixed weight; the score below; the
  weight that varies with poll count, with its own scramble; and the moving lean.
- **The only untouched test is 2024**, once, at the design freeze (EC-9).

**Test bed.**

- State polls 2004 to 2020 through stage 1's loader. 2024 is refused.
- 2000's polls are loaded for fitting only and never scored (question 1). The repo holds 530 state polls from the
  last 60 days of 2000, in all 51 contests, with no population field, so the loader reads them all as
  likely-voter polls. At 30 days out, 2000's averages and counts rest on about 30 days of polls, not a whole
  campaign's.
- Results are `state_presidential.csv`, years to 2020 only. Lean history for rung 3 is
  `state_presidential_history.csv`; its 2024 rows are refused at load, and a fit for an election reads only the
  elections before it.
- 50 states and DC. Maine's and Nebraska's districts are left out, having no results in the repo.

**Pieces, as the earlier stages left them.**

- **p**, a state's poll average: stage 1's nowcast from every poll of the state that ended before the date, however
  old.
- **N**, the national input to the prior: the two-party national nowcast on the national series, from readings
  dated at least 3 days before the date (stage 4's). Stage 3's scaling is not applied inside the prior; it enters
  through the even shift.
- **The prior:** N plus the state's lean. In the baseline and rungs 1 and 2 the lean is the state's lean at the
  previous election.
- **The even shift** (stage 5's C, provisional): every state moves by the same amount so the vote-weighted sum
  meets stage 3's national forecast.

**A state's effective number of polls, n.** Each of its polls counts 0.5^(age / 60), with age in days from the
poll's end to the date. A poll that ended yesterday counts about 1 and one from 60 days back counts 0.5. The 60
days is the nowcast's own half-life, so this adds no number. A state with only old polls has a small n: as low as
0.001 in 2012, where a state's last poll can be over a year old.

Counted without results, at the scored dates (30 and 7 days), 2004 to 2020, of 510 state-dates:

| Polls in the previous 30 days | None that cycle | 0, old polls only | 1 to 3 | 4 to 9 | 10 or more |
|---|---|---|---|---|---|
| State-dates at 30 and 7 days | 13 | 44 | 183 | 127 | 143 |
| State-dates at 150, 100 and 60 days | 79 | 171 | 388 | 110 | 17 |

- The median n is about 3 to 9 at 30 and 7 days (19 in 2020 at 7 days) and 1.4 to 5 at the earlier dates.
- One firm's sweep still decides a lot: in 2020 at 7 days all 51 contests have 10 or more recent polls.
- 2000 has all 51 polled at 30 days (195 polls) and at 7 days (403 polls), and 3 states at 60 days.

**Baseline.** EC-2's outcome: p where the state has any poll, the prior where it has none.

**The ladder.** Every rung is: estimate = prior + w × (p − prior), for states with a poll. A state with no poll that
cycle takes the prior on every rung.

1. **F, one fixed weight** (suggested by the overfitting challenge). w is one number for every polled state.
   - The challenge's poll swing is this with a pull of 1 − w.
2. **V, a weight that grows with the number of polls.** w = 1 / (1 + α + β / (1 + n)), with α and β not below zero.
   - This is the card's "weight from each side's uncertainty": with the poll average's squared spread
     a + b / (1 + n) and the prior's τ², the weight on polls is τ² / (τ² + a + b / (1 + n)), so α = a / τ² and
     β = b / τ².
   - The 1 beside n is stage 5's shape, 1 / (1 + n). Without it a state with only old polls would be sent almost
     wholly to the prior, and stage 4's pointer found such states did best on a mix. With it their weight has a
     floor, 1 / (1 + α + β), that the fit sets.
   - With β = 0 it is F. With α above zero the prior never gets zero weight, however many polls.
3. **M, a lean that can move.** The prior's lean becomes a + b1 × (lean at the previous election) + b2 × (lean at the
   one before), section 4's form. The weight on polls is refitted with this prior.
   - **Reported only:** the same with b2 left out, so the slope on the last lean is separated from the trend.

**Fits, on earlier elections only.**

- **F and V** are fitted separately for each date, on the polled states of the earlier elections at that date,
  every state counting equally. Least squares of (result − prior) on w × (p − prior), with one constant for each
  election, so the year's shared miss does not enter the weight.
  - F: w kept between 0 and 1.
  - V: bounded least squares from three fixed starting points for (α, β), keeping the lowest loss: (0.25, 0),
    (1, 1) and (0.25, 4).
  - The fit's constant for each election is an equal-weighted mean over its polled states. The score below removes
    a vote-weighted mean over all 51. They are not the same mean; both leave the shared level out.
- **Which elections each fit has:**

  | Scored election | At 30 and 7 days | At 150, 100 and 60 days (reported) |
  |---|---|---|
  | 2004 | 2000 | none: not reported |
  | 2008 | 2000, 2004 | 2004 |
  | 2012 | 2000 to 2008 | 2004, 2008 |
  | 2016 | 2000 to 2012 | 2004 to 2012 |
  | 2020 | 2000 to 2016 | 2004 to 2016 |

- **M** is fitted on results alone: each election's state leans on the two before, over every election from 1980 to
  the one before the scored election (6 elections for 2004, 10 for 2020). No polls enter. 1980 is chosen by hand:
  it is the first election whose two earlier leans both come after the three-way race of 1968 (question 4).

**The score.** The lean error, at 30 and 7 days.

- For each election and date: each state's error (estimate minus result), less the vote-weighted mean error of the
  51 (weights from the previous election's two-party vote). Squared, averaged over the 51, then over the two dates,
  with elections weighted equally.
- **Why this score.** It asks how well the estimate places each state against the nation. It does not change when
  every state moves by the same amount, so the verdict here does not rest on stage 5's even shift, which is itself
  provisional on this card. The shared level stays stage 5's question.
- **Why 30 and 7 days.** They are stage 5's scored dates (section 8 decides at 7 days alone), and they are the only
  dates at which 2000 gives 2004 something to be fitted on.
- **What that leaves out.** Whatever is adopted is used at every date, with weights fitted at each. Thin states
  (no poll in the previous 30 days) are 250 of 765 state-dates at 150, 100 and 60 days against 57 of 510 at the
  scored dates, and 2008 at those dates is fitted on 2004 alone. Flag 3 covers this.
- **Reported beside it:**
  - the plain squared error states-first, with no shift. This one can disagree with the score, because a blend
    moves the states' sum;
  - the plain squared error after the even shift, which is the forecast as it stands. After the shift every rung
    has the same vote-weighted mean error, so this is the lean error plus a term common to all rungs and a small
    cross term. It is reported and can decide nothing by itself;
  - close states (baseline prior within 10 points) and the rest, apart;
  - the lean error weighted by votes;
  - 150, 100 and 60 days for 2008 to 2020.

**The rule** (section 8 on the state test bed, as stages 4 and 5 applied it).

- **Every rung:** a positive gain against the rung below it that stands, and better in at least 4 of the 5
  elections.
- **"Stands"** means the rung met its clauses, flagged or not. Whether it is adopted is a separate step (below).
- **F, against the baseline:** a paired sign-flip test over the 10 election-date units, at p < 0.05. F has nothing
  to shuffle that binds: stage 4 found that shuffling lean across states is close to automatic. The 10 units are
  five pairs from the same election and behave more like 5; the election-level version is reported.
- **V, against F if F passed, otherwise against the baseline:** n is shuffled across the polled states within each
  election and date, in the fitted elections and the scored one alike, 200 times. V's gain must beat 19 in 20 of
  the shuffled versions' gains. This tests the dependence on poll count itself, and is the test of "fades at 4 or
  more" against "a gain everywhere". V's clauses against the baseline are reported as well.
- **M, against whichever of V or F stands:** the change in lean between the two previous elections is shuffled
  across states within each election, in the fit and the scored election alike, 200 times. M's gain must beat 19
  in 20. The shuffle keeps the slope on the last lean, so it tests the trend only.
  - If neither F nor V stands, M would change only the states with no poll that cycle (13 of 510 state-dates). It
    is then reported and not tested.
  - **The slope alone** (question 4). If M has a positive gain and 4 of 5 elections but fails its shuffle, the
    trend carries nothing, and the slope-only version is judged in M's place: a positive gain, 4 of 5, and the
    sign-flip test at p < 0.05. Its pass is flagged (flag 4), since the challenge touched the slope.
- **What is adopted:** the highest rungs that pass with no flag. V replaces F. M joins whichever stands. There is
  no other combination.
- **A flagged pass** goes to the user. If the user declines it, every rung above it that passed goes to the user
  too, shown against the rung below the declined one. V's α carries F's content, so declining F does not by itself
  keep that content out of V.
- **Collapse, written now.** If V's fitted β is zero in every fit, V is F and is reported as F with no verdict of
  its own. If F's fitted w is 1 in every fit, F is the baseline.
- **If nothing passes,** the baseline stands: a state's own polls, however old.

**Flags.** A flagged pass goes to the user and is not adopted under the rule. No diagnostic turns a fail into a
pass.

1. A rung that passes on the lean error but is worse than the rung below it on the plain squared error
   states-first.
2. A rung that passes but is worse than the rung below it in close states.
3. A rung that passes but is worse than the rung below it on the lean error at 150, 100 and 60 days, averaged over
   2008 to 2020.
4. Any pass by F (question 5), and any pass by the slope alone.
5. M passing here while it is worse than the previous lean on the long history of results (report c).

**Reports, fixed now.**

- **(a) The gain by poll count.** Each rung's gain over the baseline, split by the state's polls in the previous 30
  days (none that cycle; 0 with old polls; 1 to 3; 4 to 9; 10 or more), at 30 and 7 days and at 150, 100 and 60,
  with the number of state-dates and the number of elections in which each group gains.
- **(b) The fitted numbers** (w; α and β; b1 and b2), by scored election and date.
- **(c) The prior alone, on results only.** The previous lean against M's lean, and against the slope alone, for
  each election from 1988 to 2020, each fitted on the elections before it. No polls enter.
- **(d) Lopsided states.** The lean error by the size of the baseline prior (under 10 points, 10 to 20, over 20),
  for the baseline and for whatever is adopted.
- **(e) 2004 apart.** Its weights come from 2000 alone. Every clause is also shown on 2008 to 2020 only, asking for
  3 of 4.
- **(f) Each rung by election and by date,** and how many state-dates it changes.

**The wider range for lopsided states.** This is a question about spread, and nothing on this card estimates a
spread. Proposed: it is left to the assembly, where stage 3 already put the range refit, with report (d) as its
evidence (question 6).

**What EC-4 hands to stage 5's rerun.**

- The estimate of whatever is adopted here, before any shift, for all 51 contests, 2004 to 2020, at all five dates.
  Stage 5's pre-registration is unchanged.
- 2004 at 150, 100 and 60 days has no earlier election to fit on, so it keeps the baseline there. Those dates are
  reported in stage 5, not scored.
- **If nothing is adopted here,** the rerun's input is the first run's, and it would reproduce it. That is recorded,
  and whether the even shift stops being provisional is the user's decision.
- **If the rerun withdraws the even shift,** the verdict here does not move, since the lean error ignores the
  shift. The states-first table goes to the user, who decides whether the adoption stands.

**How this version differs from the challenge's poll swing.**

- The national input is stage 4's (the national series, lagged 3 days). The challenge used the average of the
  national polls in the poll file up to the date.
- 50 states and DC only. The challenge also fitted Maine's and Nebraska's districts on results entered by hand.
- 2004 and 2008 are scored, with 2000 in the fits. The challenge scored 2012 to 2020 and fitted from 2004.
- The score is the lean error. The challenge reported the state error after the even shift.

**Checks before any loss is read.**

- 2024 is absent from the polls, the results, the national series and the lean history.
- The leak and deletion tests, as in stages 4 and 5: polls ending on or after the date, and national readings
  within 3 days of it, change no estimate and no fit.
- Changing the scored election's results changes no estimate and no fitted number for that election.
- Behaviour on made-up inputs:
  - w = 1 gives the baseline, and w = 0 gives the prior;
  - V with β = 0 equals F;
  - a planted weight is recovered by F's fit, and a planted α and β by V's;
  - M with b1 = 1 and b2 = 0 equals the previous lean;
  - a shuffle keeps the same set of values within each election and date.
- The lean error of any estimate is unchanged by adding a constant to every state.

**Questions for the user.**

1. **2000 for fitting, and five scored elections.** Proposed: load 2000's late polls for fitting only, score 2004
   to 2020 and ask for 4 of 5, with 2004 shown apart. 2000's polls cover only its last 60 days. The alternative is
   section 7's burn-in: 2004 unscored, 3 of 4, and 2004 left on the baseline in stage 5's rerun.
2. **The score.** Proposed: the lean error at 30 and 7 days, with the states-first squared error in flag 1 and the
   earlier dates in flag 3. The alternatives: the states-first squared error as the score, which mixes in the
   level that stage 5 decides; or 150, 100 and 60 days in the score, which drops 2004 and rests 2008 on one
   fitted election.
3. **The ladder and the weight's form.** F, then V with w = 1 / (1 + α + β / (1 + n)) on the effective count,
   fitted separately at each date.
4. **How lean is defined for M.** The two previous elections' leans with fitted slopes, fitted on results from 1980.
   Section 4 specifies an estimated slope on lean. Proposed: the slope alone can be adopted only through the
   fallback above (M gains but its trend fails the shuffle), and then flagged. The alternatives: the slope alone
   as its own rung ahead of the trend, or reported only.
5. **What a pass by F buys.** The challenge already scored F's idea on 2012 to 2020, so only 2004 and 2008 are new
   to it. Proposed: a pass by F is flagged to the user rather than adopted under the rule. The alternative is to
   adopt it provisionally until 2024 is scored at the design freeze.
6. **The range for lopsided states** left to the assembly, with report (d).
7. **The five flags.**
8. **One round.**

**The human gate.** The card asks for the owner's off-tracker review once this draft exists and before the first
run. Nothing on this card is run, and no module for it is written, until the owner says that review is done.

**EC-4: the review and the user's answers (2026-11-21, before any run).**

- **The gate.** The owner was prompted when the draft was committed and said the same day that the off-tracker
  review is done. No change to the draft came from it.
- **Confirmed as proposed:**
  - 1: 2000's late polls for fitting only; 2004 to 2020 scored; 4 of 5, with 2004 shown apart;
  - 2: the lean error at 30 and 7 days;
  - 3: the ladder, and V's form on the effective count, fitted separately at each date;
  - 5: a pass by F is flagged to the user, not adopted under the rule;
  - 6: the range for lopsided states is left to the assembly, with report (d);
  - 7: the five flags;
  - 8: one round.
- **Question 4**, confirmed as proposed after one exchange. The user asked what the slope is. It is fitted across
  states: an election's state leans against the same states' leans at the previous election (b1) and at the one
  before (b2), a lean being the state's margin less the national margin. With that settled the user agreed: the
  two leans fitted from 1980, and the slope alone adoptable only through the fallback, flagged. No loss had been
  read.
- **The 2026 Senate races** in the challenge's table are now disclosed above, at the user's direction.

**EC-4: amendments after the code review, before any loss was read** (`src/model/pres_prior.py`). The code makes
choices the draft did not state. They are fixed here; no loss and no fitted number had been read.

- **Where lean comes from.** `state_presidential.csv` from 1992, the same numbers the baseline prior reads, and the
  history file for 1972 to 1988 only. The two files differ by up to 0.2 points where they overlap.
- **M inside the weight's fit.** Each earlier election in a fit takes the prior M would have given it then, fitted on
  the elections before that election. The scored election's coefficients are not used for it.
- **2004 at 150, 100 and 60 days** keeps the baseline with the previous lean under M too.
- **V's fit.** α and β have no upper bound. A fitted β below 0.0001 counts as zero for the collapse clause, because a
  bounded fit stops just inside the bound.
- **The shuffle clause.** The gain has to exceed the 95th percentile of the 200 shuffled gains by more than rounding.
  The seeds are 0 for V and 1 for M. M's shuffle draws one reordering of the states for each election from 1980,
  used wherever that election's two earlier leans appear.
- **Flags 1 to 3.** "Worse" means a negative gain on the score's own averaging: dates, then elections equally.
  Close states are those whose baseline prior is under 10 points in size.
- **Report (c) and flag 5.** The squared error of the predicted lean, intercept included, averaged over the 51 and
  then over the elections from 1988 to 2020.
- **Report (e).** The clauses on 2008 to 2020 include the shuffle clause, from the same 200 draws.
- **M and the slope alone** are the standing rung's form (F or V) refitted with their prior.
- **Checks, run and passed (23):**
  - 2024 is absent from the polls, the results, the national series and the lean history;
  - the leak and deletion tests at 30, 7 and 100 days, with 2000 included. Polls that ended before the date do
    move that date's estimates and the later elections' fits, so the test can fail;
  - changing a scored election's results changes no estimate and no fitted number for it;
  - the behaviour checks listed above, and planted lean slopes recovered;
  - an identity shuffle reproduces V and M exactly, and a real one changes the fit and the estimate.
- **The decision path, run on planted results** (30 shuffles each), so that what stands, the collapse, the fallback
  and the flags were executed before the one round:
  - a planted α and β: F passes and is flagged, V passes against F, M fails;
  - a planted fixed weight: F passes, V does not;
  - a planted trend in lean: M passes;
  - a planted slope with no trend: M fails its shuffle, and the slope alone is judged, passes and is flagged;
  - results equal to the baseline: nothing passes and M is not tested.
- **A failed check, recorded.** Commit `0f4c30a` says the checks pass. One check added just before it had failed:
  it moved every 2016 poll by the same amount, which the fit's constant for the election absorbs by design. The
  fault was in the check; it now moves half the states (commit `5caa87a`).

### EC-4: results (run 2026-11-21, one round). F passes with two flags, so it goes to the user. V and M fail.

`src/model/pres_prior.py run`, `data/processed/pres_prior.json` (and the per-state table `pres_prior_frame.csv`).

| | Lean error (30 and 7 days) | 2004 | 2008 | 2012 | 2016 | 2020 | Elections better | Test | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| Baseline (own polls, however old) | 24.32 | 12.30 | 24.90 | 22.56 | 43.00 | 18.83 | | | |
| **F, a fixed weight** (against the baseline) | **20.22** | 11.48 | 23.87 | 19.45 | 37.00 | 9.26 | **5** | **p 0.001** | **passes; flags 2 and 4** |
| V, weight by poll count (against F) | 20.25 | 11.67 | 23.64 | 17.89 | 34.86 | 13.21 | 3 | 88.5% of shuffles (needs 95%) | fails |
| M, a lean that can move (against F) | 21.33 | 12.20 | 24.36 | 20.67 | 38.78 | 10.66 | 0 | | fails |
| The slope alone (reported; not judged) | 21.47 | 12.24 | 24.45 | 20.98 | 39.01 | 10.68 | 0 | | |

The score is the mean of the five elections' columns. V and M are scored against F because F met its clauses.

**The table reproduces the earlier stages.** The baseline's squared error states-first (36.64) and after the even
shift (31.08) are stage 5's figures for its baseline and for C. Each rung changes 497 of the 510 scored state-dates,
every one with a poll; M and the slope alone change all 510.

**F passes its clauses, and two flags apply, so it is not adopted under the rule: it goes to the user.**

- **The clauses.** Its gain is 4.10, better in all 5 elections, with sign-flip p 0.001 over the 10 election-date
  units, the smallest value 10 units can give. The election-level version, reported only, is 0.031, the smallest
  5 can give.
- **The fitted weight on polls** is 0.71 to 0.90 at 30 and 7 days: a pull of 10% to 29% toward the prior. It is
  lower for the later elections (0.86 and 0.90 for 2004; 0.77 for 2016; 0.71 and 0.74 for 2020). At 150, 100 and 60
  days it is 0.43 to 0.71.
- **Flag 4:** any pass by F is flagged, since the overfitting challenge had scored its idea on 2012 to 2020.
- **Flag 2: F is worse in close states.** Where the baseline prior is within 10 points (167 of the 510
  state-dates), the lean error rises from 14.37 to 15.13.

  | Close states | 2004 | 2008 | 2012 | 2016 | 2020 |
  |---|---|---|---|---|---|
  | Baseline | 14.72 | 28.65 | 5.88 | 18.50 | 4.10 |
  | F | 14.76 | 31.02 | 5.66 | 20.57 | 3.62 |

  - It is better there in 2 elections of 5 (2012 and 2020).
  - Computed after the results: it is the closer of the two in 47% of close state-dates, against 60% over all
    states.
  - Everywhere else it gains a lot: 28.30 to 21.99, better in 5 of 5.
- **Flags 1 and 3 do not apply.** States-first, with no shift, the squared error falls from 36.64 to 31.07 (5 of 5).
  At 150, 100 and 60 days, 2008 to 2020, the lean error falls from 39.98 to 25.81 (4 of 4).
- **Beside the score:** weighted by votes, the lean error falls from 14.65 to 12.92 (5 of 5). After the even shift,
  the squared error falls from 31.08 to 26.55 (5 of 5).
- **Without 2004** (report e): gain 4.92, 4 of 4, p 0.004.
- **2020 carries the most:** 18.83 to 9.26. The other four gain 0.81, 1.02, 3.11 and 5.99.

**V fails.** Against F its gain is −0.04, it is better in 3 of 5 elections, and it beats 88.5% of its shuffles.

- It did not collapse: the fits put α near zero and β at 0.66 to 1.66 at the scored dates. So a heavily polled
  state gets almost the full weight on its polls, and a state with only old polls about 0.4 to 0.6.
- It is better than F in 2008, 2012 and 2016 and worse in 2004 and 2020. In 2020 it is much worse (13.21 against
  9.26), almost all of it at 7 days (18.73 against 11.23; at 30 days 7.70 against 7.29). At 7 days every state had
  10 or more recent polls, so V pulled almost nothing toward the prior.
- Against the baseline (reported) it gains 4.06, in 5 of 5. All of that is what it shares with F.
- **Declining F would not reopen V.** The shuffle clause does not depend on the rung below: V's gain and every
  shuffled gain move by the same amount. Against the baseline V beats the same 88.5% of its shuffles and fails.
- **So a weight that depends on the number of polls is not shown.** That answers the pre-registered question of
  "fades at 4 or more" against "a gain everywhere" only in part; report (a) is below.

**M fails.** With F's weight refitted on its prior, it is worse in every election (gain −1.12).

- The fitted slopes are 0.89 to 0.93 on the last lean and 0.05 to 0.07 on the one before. The second is above
  zero: a small pull back toward the older lean, not a trend continuing.
- On results alone, 1988 to 2020 (report c), it also loses: the squared error of the predicted lean is 39.8 for the
  previous lean, 41.8 for M and 41.0 for the slope alone. Flag 5 would have applied.
- The slope alone was not judged in M's place, since M had no gain. It is worse too (21.47).
- M's shuffle share (it beats 97.5% of its shuffles, with a negative gain) decides nothing.

**Report (a): each rung's gain over the baseline by the state's polls in the previous 30 days.**

| | None that cycle | 0, old polls only | 1 to 3 | 4 to 9 | 10 or more |
|---|---|---|---|---|---|
| **State-dates at 30 and 7 days** | 13 | 44 | 183 | 127 | 143 |
| F: mean gain | 0.09 | 7.13 | 5.60 | 0.11 | 5.16 |
| F: elections gaining | 1 of 2 | 4 of 4 | 5 of 5 | 3 of 5 | 5 of 5 |
| V: mean gain | 0.09 | 12.05 | 6.53 | 0.29 | 2.15 |
| V: elections gaining | 1 of 2 | 4 of 4 | 5 of 5 | 4 of 5 | 5 of 5 |
| M with F's weight: mean gain | −2.80 | 4.89 | 3.97 | −0.01 | 4.32 |
| M with F's weight: elections gaining | 1 of 2 | 3 of 4 | 5 of 5 | 2 of 5 | 5 of 5 |
| **State-dates at 150, 100 and 60 days, 2008 to 2020** | 57 | 148 | 310 | 81 | 16 |
| F: mean gain | −0.19 | 23.57 | 16.37 | 1.47 | 0.05 |
| F: elections gaining | 3 of 4 | 4 of 4 | 4 of 4 | 3 of 4 | 2 of 3 |
| V: mean gain | −0.75 | 22.96 | 15.82 | 1.22 | 0.07 |
| V: elections gaining | 3 of 4 | 4 of 4 | 4 of 4 | 3 of 4 | 3 of 3 |
| M with F's weight: mean gain | −2.04 | 21.52 | 15.81 | 1.30 | −0.27 |
| M with F's weight: elections gaining | 2 of 4 | 4 of 4 | 4 of 4 | 3 of 4 | 1 of 3 |

States with no poll that cycle take the prior on every rung; their small gains under F and V come from the mean
error that the score removes, which the other states move.

- The gain is where polling is thin (old polls only, or 1 to 3 recent polls), and it is close to nothing at 4 to 9.
  That much agrees with stage 4.
- V gains more than F where polls are old (12.05 against 7.13) and less at 10 or more (2.15 against 5.16). The two
  about cancel.
- F's gain at 10 or more is mostly 2020. Computed after the results and not among the fixed reports: that group's
  mean gain is 10.33 in 2020 (61 state-dates) and 0.29 to 3.58 in the other four elections (1.32 over their 82).
  It is 14.5 in the 49 lopsided state-dates and 0.3 in the 94 close ones. 2020 is the year one firm polled every
  state, so lopsided states sit in the 10-or-more group.
- So "a gain everywhere" is not what this shows. The gain follows thin polling and lopsided states, and V's
  form did not capture it better than one fixed weight.

**Report (d): the lean error by the size of the baseline prior.**

| | Under 10 points | 10 to 20 | Over 20 |
|---|---|---|---|
| Baseline | 14.37 | 24.02 | 33.10 |
| F | 15.13 | 20.66 | 23.93 |
| State-dates | 167 | 167 | 176 |

Under either, lopsided states miss by more than close ones. That is the evidence the assembly gets for a wider
range there.

**Where the close states lose, computed after the results and deciding nothing.** Pooled over state-dates, close
states with 1 to 3 recent polls go from 47.4 to 54.2 (19 state-dates), those with 4 to 9 from 15.0 to 15.6 (53),
and those with 10 or more from 7.65 to 7.36 (94). The one left over is Vermont in 2004 at 7 days, with old polls
only (118.0 to 121.9). The loss is in 2008 and 2016, the two years stage 4 found leans moving most. No further
split is made after the results; anything these suggest is a declared candidate for the design freeze.

**The rest of the fixed reports** are in `pres_prior.json`: the fitted numbers by election and date (b), the prior
alone by election (c), the clauses on 2008 to 2020 for V and M (e), and every rung by date (f).

**What stands, under the rule.**

- **V and M are closed.** One round, as agreed.
- **The prior keeps the previous lean as it is.** Section 4 specified a fitted slope on lean. Fitted with or without
  the second lean, it is worse in every election here and on the 1988 to 2020 results. So the prior is the national
  estimate plus the state's lean at the previous election, with a slope of 1 and no second lean.
- **F is the user's decision.** It met every clause and carries flags 2 and 4.
  - Adopting it means every polled state is pulled toward its prior by the fitted weight at each date, provisionally
    until 2024 is scored at the design freeze (EC-9).
  - Declining it leaves the baseline: a state's own polls, however old.
  - A version that spares close states, or pulls only thinly polled ones, would be a new candidate suggested by
    these results. This card had one round, so it could only be written down for the design freeze.
- **Stage 5's rerun** waits for that decision. If F is adopted, its estimates before any shift are the rerun's
  input. If it is declined, the input is the first run's.

**EC-4: the user's decision on F (2026-11-21).**

- **F is adopted, provisionally, until 2024 is scored at the design freeze (EC-9).** The user was shown the clauses,
  both flags, the close-states table and report (a), and decided to adopt.
- **What that means for the forecast.** A state with a poll is estimated as its prior plus w times (its poll average
  less its prior), with w the fixed weight fitted at each date on earlier elections. The prior is the national
  estimate plus the state's lean at the previous election. A state with no poll that cycle takes the prior.
- **A modified version goes to the design freeze, at the user's direction.** F with no pull in close states: a state
  whose prior is within 10 points keeps its own polls, and every other polled state is pulled by the fixed weight.
  - It is declared as **suggested by EC-4's results** (flag 2), on top of F's own debt to the overfitting challenge.
  - The 10 points is flag 2's threshold, fixed before the results. Nothing else about it has been run or fitted.
  - Its exact fit is written down at EC-9 before 2024 is opened, and 2024 is its only test.
- **Stage 5's rerun** now runs on F's estimates before any shift, with stage 5's pre-registration unchanged.

### Stage 5's rerun after EC-4 (run 2026-11-21). The even shift passes again.

`src/model/pres_addup.py rerun`, `data/processed/pres_addup_rerun.json` (and `pres_addup_rerun_frame.csv`).

Stage 5's pre-registration is unchanged: the same candidates, score, rule and flag. The one thing that differs is
the state estimate each candidate starts from. It is now EC-4's F before any shift, in place of each state's own
polls. That changes 497 of the 510 scored state-dates. 2004 at 150, 100 and 60 days keeps stage 4's estimate.

- The module's first run still reproduces its saved output exactly, and stage 5's checks pass.
- EC-4's baseline equals stage 4's state estimate in every state and date (asserted in the code).
- The two runs agree where they overlap: on the plain squared error, the rerun's baseline (31.07) and C (26.55) are
  EC-4's states-first and after-shift figures for F.

| | Excess score (30 and 7 days) | 2004 | 2008 | 2012 | 2016 | 2020 | Elections better | Test | Plain squared error | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Baseline (F, states first) | 16.66 | 9.06 | 12.89 | 12.08 | 42.43 | 6.86 | | | 31.07 | |
| A. Spread by uncertainty | 13.57 | 9.56 | 10.68 | 14.14 | 29.19 | 4.26 | 3 | 96.5% of shuffles | 26.04 | fails |
| B. Scale every state | 25.50 | 14.21 | 21.21 | 16.32 | 65.31 | 10.47 | 0 | p 1.0 | 42.31 | fails |
| **C. Even shift** | **13.81** | 8.43 | 11.10 | 12.58 | 32.44 | 4.49 | **4** | **p 0.014** | **26.55** | **passes** |

For comparison, the first run's row for C was 16.82 against a baseline of 20.46 (gain 3.64, 4 of 5, p 0.012).

- **C passes, with no flag.** Its gain is 2.86, better in 4 of 5 elections (2012 slightly worse, as before), with
  sign-flip p 0.014 over the 10 election-date units. The election-level version, reported only, is 0.062. It is
  better on the plain squared error too (26.55 against 31.07, in the same 4 elections).
- **The gain is smaller than in the first run** (2.86 against 3.64), as stage 5 expected: the blend already pulls
  the states' sum toward the national estimate. The gap between that sum and the national forecast shrinks in most
  cells (for example −1.75 to −1.52 in 2016 at 7 days, and 2.21 to 0.85 in 2008 at 150 days).
- **A** failed two clauses in the first run: its shuffle (90.5%) and the elections (3 of 5). Now it beats 96.5% of
  its shuffles and gains slightly more than C (3.10 against 2.86), but it is still better in only 3 of 5 elections,
  so it fails on that clause alone. This decides nothing.
- **B** is worse in every election, as before, and is flagged as before.
- **Reported:** the popular vote's squared error falls from 8.84 to 5.41 under C. With each year's mean error
  removed, C equals its baseline (19.37 both): its gain is still all in the level the states share. It is better
  at every date, the reported ones included.

**So the even shift stands on EC-4's estimates.** Stage 5 made its adoption provisional until this rerun; the rerun
passes, so that condition is met. What remains provisional is F itself, until 2024 is scored at the design freeze.
The even shift does not hang on F: it passed on the states' own polls and on the blend, so it stands whichever way
F goes.

**The state estimate, as EC-2 to EC-4 leave it:**

1. The prior is the national two-party nowcast plus the state's lean at the previous election.
2. A state with a poll is its prior plus w times (its poll average less its prior), w fitted at each date on
   earlier elections (F, provisional). A state with no poll takes the prior.
3. Every state then moves by the same amount so the vote-weighted sum meets the national forecast (C).

**Carried forward from EC-4:**

- **To the design freeze (EC-9):** F's one untouched test on 2024, and the version with no pull in close states.
  The two share one holdout, so how 2024 decides between them is also written down before 2024 is opened.
- **To the assembly:** the wider range for lopsided states, with report (d) as its evidence.
- **To EC-5, after DA-4:** the challenge's demographic term.
- **Closed here:** a weight that depends on the number of polls, and a fitted slope or second lean in the prior.

## 14. How state errors move together: evaluation plan (EC-5)

Section 5 fixes the baseline (a national draw, a draw per Census region, a tilt by lean, and each state's own
error) and names at most three candidates. EC-5 fits that structure on past presidential misses and asks whether
demographics explain state errors that move together, beyond what regions and the tilt already carry. The
demographics are DA-11's, by election year (section 9).

### EC-5: pre-registration (written 2026-11-21, before any run)

Nothing below has been run. No miss has been read: the only numbers in this draft are counts, correlations between
demographic measures and leans (results that are already the baseline prior's inputs), and standardized demographic
values. They use no poll and no forecast.

**How blind this test is.**

- **Section 5's three candidates** were written on 2026-11-20 (commit `aaee2b5`, EC-1), before the overfitting
  challenge's log was read.
- **The overfitting challenge** (section 13) scored a signed demographic term on 2012, 2016 and 2020 at 7, 30, 60 and
  100 days: polls overstate the Democrat where white adults without a degree are many, as one fixed coefficient on a
  2015-19 snapshot, and it beat 200 shuffles. Its log was read on 2026-11-21, before this draft. So candidate 2 below
  uses a feature whose sign on three of the four scored elections has been seen, though in a different form (a
  fitted shift of the centre, not a draw). Its pass is flagged (flag 1). The fixed-sign form is run and reported here
  and is declared **suggested by the overfitting challenge** (question 5).
- **Candidate 1's and candidate 3's features were in the challenge's search.** Its search list (`src/search.py`,
  `STATE_F`) included the degree share and the rural share as centred state terms, searched over 2012 to 2020 with
  hindsight; the log reports no result for either, and neither survived. So a pass by candidate 1 is flagged as
  candidate 2's is (flag 5, question 8). Candidate 3 uses rural share as one of six measures inside a kernel and is
  not flagged on this ground. The two education measures are not the same: across the 51 contests the degree share
  and the white share without a degree correlate at about −0.55 in each of the years 2004, 2007, 2011, 2015 and
  2019 (−0.4 without DC); each tracks lean more closely than it tracks the other.
- **The log's Senate table** reports the demographic term's slope by Senate cycle, 2024 and the provisional 2026
  races included, and finds its sign inconstant. No number from it is given here (section 13). The card's wording
  that the term's size may differ by election (commit `c6ad38d`, 2026-11-21) follows the log's recommendation; a
  zero-mean draw is that wording's form.
- **Both education measures track lean.** The year-before degree share correlates with the election's lean at 0.57
  (2000), 0.67, 0.72, 0.72, 0.79 and 0.82 (2020); the white share without a degree at −0.53, −0.52, −0.56, −0.62,
  −0.73 and −0.71. Against the previous election's lean, the prior's input, they run 0.49 to 0.79 and −0.43 to −0.73.
  This is section 5's warning: a demographic draw can look useful only because it restates the tilt. The baseline
  keeps the tilt, so the comparison answers whether education adds to it.

**Test bed.**

- **The misses.** For each election and date, a state's miss is its result less the forecast as EC-2 to EC-4 leave it
  (section 13, "The state estimate"): the prior plus F's weight times the gap to its polls, then the even shift to
  stage 3's national forecast. For 2004 to 2020 these are the `C` and `result` columns of `pres_addup_rerun_frame.csv`,
  rebuilt by the same code and checked equal. The scored date is 7 days (section 7); 30 days is reported.
- **2000 (question 1).** 2000 has 403 state polls at 7 days, in all 51 contests, and the national series and 1996's leans exist
  and stage 3's national forecast for 2000 is finite at 30 and 7 days (checked), so its 7-day forecast can be built. No earlier election exists to fit F's weight on,
  so 2000's estimate takes w = 1 (its own polls, EC-2's outcome), then the even shift. 2000's misses are used for
  fitting only.
- **Which elections.** Section 7's burn-in of two elections: 2000 and 2004 are fit-only; 2008, 2012, 2016 and 2020 are
  scored. Each scored election's structure is fitted on the elections before it: 2008 on two, 2020 on five. 2008's
  fit is the thinnest and its score is shown apart.
- **51 contests**, 50 states and DC, as section 13: Maine's and Nebraska's districts have no results in the repo.
  Section 7 says 56; this is a departure, recorded.
- **Demographics.** `state_demographics.csv` and `state_rural_share.csv` through `state_demographics_vintages.csv`: each
  election uses the year before it (2000, 2004 and 2020 as the vintages file says), and rural share from the census in
  force. The election's own year is run as a comparison that decides nothing (report b), as the user decided for
  DA-11. 2024 is refused at load from the demographics, the rural shares, the results and the frame.

**The national layer stays out (question 2).** Each election's 51 misses are centred on their plain mean, and the
score is the density of the 50 contrasts that remain. The card's question is how states move against each other
apart from any national miss (2016's errors were correlated across states without the national polls missing);
the national draw's size is section 6's and the assembly's. In the contrast space the national component vanishes,
so no structure here fits it. For a model covariance Σ the contrasts have covariance QΣQ', with Q one fixed
orthonormal basis of the space orthogonal to a constant; the log density is the Gaussian one in 50 dimensions.

**Every structure gets the same spread (question 3).** This test is about co-movement, so each state's total spread
is the same under every structure: one fitted σ_T for all 51 contests, and the components set the correlations
only. A structure is Σ = σ_T² × corr(A), where corr rescales a matrix A to unit diagonal, and A is the sum of the
components below with the state's own error fixed at 1. Without this a draw on a standardized feature would widen
the states where the feature is extreme (DC is 3 to 4 standard deviations out on both education measures) and could
win on spread rather than on co-movement, which the shuffle would not catch. This is how section 5 and
`error_structure.py` already treat the components: carved out of a fixed total. The national draw sits outside this
rescaling: it vanishes in the contrasts here, and the assembly adds it beside the rescaled structure. ℓ is centred on
the 51's plain mean before anything is rescaled; in the contrast space the tilt is the same component either way,
but the rescaling reads each state's diagonal, and DC's lean is far from the others', so the choice is fixed here.

**Baseline.** A_0 = ρ_r R + ρ_b ℓℓ' + I.

- R_st = 1 if s and t are in the same Census region (the four regions of `error_structure.py`, DC in the South),
  else 0.
- ℓ_s = the state's lean at the previous election, in points: the lean the forecast's prior used.
- ρ_r, ρ_b ≥ 0 are the regional and tilt sizes relative to the state's own error.

**The candidates** (section 5), each against the baseline.

1. **A degree draw.** A_1 = A_0 + ρ_e z_e z_e', z_e the share of adults 25 and over with a degree, standardized
   across the 51 within the year used.
2. **A white-without-a-degree draw.** A_2 = A_0 + ρ_w z_w z_w', z_w the white non-Hispanic share of adults 25 and
   over without a degree, standardized likewise.
3. **Similarity in place of regions.** A_3 = ρ_k K + ρ_b ℓℓ' + I, with K_st = exp(−d²_st / 2m²): d the distance between
   s and t on the standardized measures, m the median distance over all pairs that year, K_ss = 1. The measures
   (question 6): degree share, the log of median household income, white, Black and Latino shares, and rural share
   from the census in force. Six, all by year. The Downballot's urban share, the seventh in `state_similarity()`, is
   one snapshot (its file is for the 118th Congress; how it is built is unconfirmed, section 9) and is proposed
   dropped; a version with it as a fixed seventh measure is reported (report g).

Every draw has mean zero: a candidate says which states miss together and by how much relative to each other, not
in which direction. Candidate 2's fixed-sign form is question 5.

**Fits, on earlier elections only.** Maximum likelihood on the centred misses of the elections before the scored
one, each election with its own year's R, ℓ, z and K. For given sizes ρ, σ_T² has a closed form, so the search is
over the two or three sizes, bounded at zero with no upper bound, from three fixed starting points, keeping the
lowest loss. Each scored election is fitted on its own; the scored election's misses enter no fit.

- **Collapse, written now.** A candidate whose fitted size is zero in every fit is the baseline and gets no verdict.
  A zero fitted ρ_r in the baseline is reported; the baseline is then the tilt alone.
- **Senate and governor misses** are not used (question 10): section 5 says the components are re-estimated on
  presidential elections, and the card says the same.

**The score.** For each scored election, the log density of its 50 centred 7-day misses under the structure fitted
on the elections before it. Pooled: the mean over the four scored elections. A candidate's gain is its pooled score
less the baseline's, in log-density units. Reported beside it: each election; 2008 apart; 30 days; the own-year
vintage; without DC.

**The rule** (section 8).

1. **Shuffle.** The candidate's feature is shuffled across the 51 contests: one reordering of the states, drawn once
   per shuffle and applied in every year, fit and scored alike. For candidates 1 and 2 the reordering moves z; for
   candidate 3 it moves the states' six-measure vectors, so K's rows and columns are permuted together. R and ℓ are
   never shuffled. 200 shuffles, seeds 0, 1 and 2 for the three candidates; each refits and rescores. The
   candidate's gain has to exceed the 95th percentile of the 200 shuffled gains by more than rounding.
2. **Simulation noise.** The density is closed-form Gaussian, so no simulation enters and this condition is met by
   construction. That is a departure from section 5's Student-t components, taken for the test only (question 4).
3. **Better than the baseline in at least three of the four scored elections**, on each election's log density.

**What is adopted (question 9).** A candidate that passes all three with no flag is adopted provisionally, until 2024
at the design freeze. If more than one passes, the one with the largest gain is adopted; the combination of a
passing candidate 3 with a passing candidate 1 or 2 (similarity in place of regions, plus the draw) is reported and
goes to the user, not adopted under the rule. Candidates 1 and 2 are never adopted together. If nothing passes,
the baseline stands: regions and the tilt.

**Flags.** A flagged pass goes to the user and is not adopted under the rule. No diagnostic turns a fail into a pass.

1. Any pass by candidate 2: the challenge scored its feature on three of the four scored elections.
2. A pass that disappears without DC (report c): the gain on the 50 states is not positive, or clause 3 fails there.
3. A pass that is worse than the baseline at 30 days, pooled.
4. A pass whose fitted size is zero in the 2020 fit, the one with the most elections behind it.
5. Any pass by candidate 1: its feature was in the challenge's search list over the same elections, though the log
   reports no result for it.

**Reports, fixed now.**

- **(a) The fitted sizes** by scored election, for the baseline and each candidate, and what they imply: the
  correlation between two states in the same region, between two states one standard deviation apart on the
  feature, and the share of a typical state's variance each component carries.
- **(b) The own-year vintage.** Every clause rerun with each election's own-year demographics. Decides nothing.
- **(c) Without DC.** Every clause rerun on the 50 states, with z and K recomputed over the 50. Flag 2 reads it.
- **(d) 30 days.** The score against the 30-day forecast, with the structure fitted on 30-day misses. Flag 3 reads it.
- **(e) 2008 apart, and the clauses on 2012 to 2020 only**, asking for 2 of 3.
- **(f) The fixed-sign form of candidate 2** (question 5): E[miss_s] = β z_w,s with β fitted on earlier elections,
  on top of the baseline's covariance, with its three clauses and seed 3. Declared suggested by the challenge.
- **(g) Candidate 3 with The Downballot's urban share** as a fixed seventh measure, with its clauses and seed 4.
- **(h) The baseline's own parts.** The baseline against the tilt alone and against the state's own error alone, so
  the reader sees what regions and the tilt carry on presidential misses before any candidate is added.

**What EC-5 hands on.**

- **To EC-6:** the adopted structure as correlations, to be sized against section 4's totals at the assembly. The
  Student-t tails and the national draw are the assembly's.
- **To the design freeze (EC-9):** the adopted candidate's one untouched test on 2024; whatever is flagged and
  declined; report (f) if it passes its clauses.

**Checks before any loss is read.**

- 2024 is absent from the demographics, the rural shares, the results, the frame and the national series.
- The rebuilt 7-day and 30-day estimates for 2004 to 2020 equal `pres_addup_rerun_frame.csv`'s `C` column.
- Adding a constant to every miss of an election changes no score and no fit.
- At ρ = 0 everywhere the log density equals the known formula for independent errors with one spread.
- Planted structures are recovered: misses drawn from a known regional size, tilt size and feature size are fitted
  back to within sampling error, from each of the three starting points.
- An identity shuffle reproduces each candidate exactly; a real one changes the fit and the score.
- The decision path runs on planted misses before the one round: a planted feature draw makes its candidate pass; a
  planted region-only structure makes every candidate fail; a planted DC-only effect trips flag 2.

**Questions for the user.**

1. **2000 for fitting, with w = 1.** Proposed: build 2000's misses with the state's own polls as the estimate and use
   them for fitting only, so 2008 is fitted on two elections. The alternative is to leave 2000 out and fit 2008 on
   2004 alone, where one election cannot size a draw. Why 2004 is not scored here though EC-4 scored it: EC-4's
   weight is one number per date, fitted across 2000's 51 polled states; a structure's sizes are the spread of
   draws across elections, and 2000 alone offers one draw. Section 7's burn-in of two elections holds.
2. **The national layer out.** Proposed: centred misses, density on 50 contrasts. The alternative is to fit a national
   size as a fourth parameter from the same few elections; it would be the same under every candidate and add noise
   to every fit.
3. **One spread for every state and structure.** Proposed as above. The alternative is a per-state total, which
   mixes the question of spread into the one about co-movement, and which EC-4 already left to the assembly.
4. **Gaussian for the test, 51 contests.** Proposed, as departures from sections 5 and 7, recorded.
5. **Candidate 2's mean.** Proposed: candidate 2 is a zero-mean draw (the card's "size allowed to differ by
   election"), and the challenge's fixed-sign form is run as report (f) with its own clauses, adoptable only at the
   design freeze if it passes them. The alternative is the fixed-sign form as candidate 2 itself. A non-zero mean
   moves point forecasts, so it touches F and stage 5's rerun, which this card does not reopen.
6. **Candidate 3's measures.** Proposed: six measures by year, urban share dropped; the seven-measure version
   reported (g).
7. **DC.** Proposed: in the test bed, with the 50-state rerun as report (c) and flag 2.
8. **The five flags.** Proposed as above, flag 5 included: the challenge searched the degree share on the scored
   elections, though the log reports no result for it. The alternative is to judge candidate 1 on the rule alone and
   flag candidate 2 only.
9. **What is adopted** when more than one candidate passes: the largest gain; the combination reported.
10. **Presidential misses only** in the fits, no Senate or governor cycles.
11. **One round.**

**The human gate.** The card has no checklist. The draft is shown to the user before any run, as with every
pre-registration; the code review's amendments are written here before any loss is read, as in section 13.

**EC-5: the user's answers (2026-11-21, before any run).** The user confirmed all eleven questions as proposed, in
one reply: 2000 and 2004 fit-only with 2000's estimate on its own polls, 2008 to 2020 scored and 3 of 4; the national
layer out through centred misses on 50 contrasts; one spread for every state and structure; Gaussian density and 51
contests; candidate 2 as a zero-mean draw with the fixed-sign form as report (f); six by-year measures for candidate
3 with the urban-share version as report (g); DC in, with report (c) and flag 2; the five flags; the largest gain
adopted when more than one passes, the combination reported; presidential misses only in the fits; one round. The
run is to follow once the code's checks pass and its amendments are written here.
