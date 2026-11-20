# Backtest

The out-of-sample test every change to the House and Senate models has to pass (work plan card CM-1). Each past
cycle is forecast with every parameter fitted on earlier cycles only, then scored against the result.

```powershell
python src/model/backtest_asof.py                  # the baseline: data/processed/backtest_asof*.{json,csv}
python src/model/backtest_asof.py --tag NAME       # a candidate change: backtest_asof_NAME*.{json,csv}
python src/model/backtest_asof.py --compare NAME   # the candidate against the baseline, cycle by cycle
```

It fetches nothing and touches no file the forecast or `check_frozen.py` uses. It reads files already in the repo,
plus one that is not: Gary Jacobson's House elections file, which supplies the House districts for 1998 to 2004 and
is used with his permission but is not ours to redistribute (DATA.md, "Linked sources"). Without that file the
script still runs, says so, and scores the House from 2012 only; its House numbers then differ from the ones below.

## What can be scored, and from when

Two dates matter for each part of the model: the first cycle with data, and the first cycle that can be scored.
A cycle is scored only when the part has **three earlier cycles** to fit on (`MIN_PRIOR`).

| Part | Data from | Scored | What sets the start |
|---|---|---|---|
| Generic ballot, Senate polls, district polls | 1998 | 2004 to 2024 | 538's poll archive with results starts in 1998 |
| Fundamentals | 1946 (fitted from 1962) | 2004 to 2024 | not binding |
| Senate prior (state lean, incumbency) | 1998 | 2004 to 2024 | the polls; state lean now runs back to 1828 |
| House districts | 1998 | 2004 to 2024 | the polls; district lean now runs back to the 1950s |

So both chambers and the national environment are scored on the same 11 cycles.

**Where the House districts come from.** Two sources, joined at 2006:

- *2006 to 2024*: `house_history.csv`, with Cook PVI as the lean, as in the published model.
- *1998 to 2004*: Gary Jacobson's House elections file (1946 to 2024: House vote, incumbency and district
  presidential vote, with labelled districts). It arrived on 2026-11-20, after the first version of this test, which
  scored the House from 2012 only.

Three points about how his file is used:

- *The lean is one known before the election.* His presidential vote is the previous election's in a midterm row,
  recalculated for new lines after a redistricting, but that year's own vote in a presidential-year row. So for 2000
  and 2004 the lean is taken from the row two years earlier, and only for districts not redrawn in between. That drops
  the redrawn Texas districts in 2004: 404 of 435 seats are in that year's test.
- *It is one election's vote, where Cook PVI averages two.* On 2006 to 2024, where both exist, the two leans correlate
  at 0.994. Putting his lean on every cycle moved pooled log loss by 0.007 (better, nearly all of it in 2018) and
  improved 5 of 11 cycles, which is short of the adoption rule below, so the join costs little and 2006 on stays on
  Cook PVI.
- *It agrees with our own history.* On 2006 to 2024 his margins match `house_history.csv` to a median of 0.04 points
  (3 of 3,331 races differ by more than 5), and incumbency matches in 97% of districts.
- *Seats with one major party on the ballot are fixed only where his codes say so* (unopposed, or two candidates of
  one party). A race with no vote share and no such code, mostly Louisiana runoffs, is left out of the test.

The file's history before 1998 is not used here: the polls set the start. Fitting the district model on earlier
decades is DA-2 and CM-4's question, and needs coefficients that are allowed to drift.

**What is committed.** The scores, the parameters by cycle and every Senate forecast. District forecasts for 2004
are scored in the totals but written beside Jacobson's file, outside the repo, because his lean could be worked back
out of them. District forecasts for 2006 on are in the repo as before (a run with `--house-lean jacobson` keeps all
its district forecasts out of the repo, for the same reason).

**2024** is in the test. 538's `raw_polls.csv` stops in 2022, so the 2024 late polls are rebuilt from the archived
538 poll files. On 2018 to 2022, where both exist, the rebuilt race averages differ from `raw_polls` by 0.7 points
for Senate races, 0.3 for House districts and 0.2 for the generic ballot (mean absolute difference).

**2026** is in no fit (`HELD_OUT`) and is not scored here yet. That is work still to do, not a switch: the 2026 polls
come from VoteHub and the results from the scorecard, and both have to be put in this script's shape (late polls per
race, a district table like `house_history.csv`, Senate results). It waits for the final scorecard (SC-1). Until then
the 2026 step of the adoption rule cannot be run.

**Two checks on the test itself.** Scrambling every result at or after the target cycle leaves that cycle's forecasts
unchanged to the last digit (2004, 2006, 2008, 2012, 2018, 2024), so no fit sees its own or a later result. The
scramble includes Jacobson's presidential vote in presidential-year rows, which is a result of that year. And the
district lean
on each Wikipedia page is the Cook PVI published before that election: it repeats the previous cycle's value where
Cook had not yet updated (2008, 2016, 2020, 2024) and changes where it had.

## What is tested

The published model's structure, with each estimated number re-estimated as of each cycle:

- **National environment.** Generic-ballot average; in the fundamentals versions, blended by precision with
  fundamentals chosen and fitted by the same search as `fundamentals.py` on elections before the target year.
- **Senate.** Prior = state lean at the previous presidential election + environment + incumbency (2 points, as
  published); blended with the poll average by precision. Poll-average error by number of polls, the prior's error,
  the shared Senate miss and the tail weight are all fitted on earlier cycles.
- **House.** Prior = constant + slope x lean + slope x environment + incumbency; blended with district polls. Lean
  is twice the Cook PVI from 2006, and the same quantity from one presidential election before that. The
  hand-picked windows in `house_structure.py` become a rule: national slope from every earlier cycle; constant, lean
  slope and incumbency from the latest four; district error from the latest five. Seats with one major party on the
  ballot are fixed.
- **Simulation.** As `forecast.simulate`: one national draw shared by both chambers, a region shock, a random slope on
  lean, a race draw. 20,000 draws per cycle.
- **The three versions**: polls only, polls and fundamentals, and bias-adjusted. The bias-adjusted version here is
  simpler than the published one: the generic-ballot shift is the decay-weighted mean of earlier misses, without the
  likely-voter discount or the averaged specifications of `bias_decay.py`; the state-lean term uses earlier cycles
  since 2010, so it is zero before 2012.

Run on everything the frozen forecast had, the harness's estimators return the frozen values (`parity` in
`backtest_asof.json`): identical for the national and Senate miss, the poll-average error curve, the sponsor shifts
and all five House district numbers (the parity run uses the 2006 to 2024 districts only, as the frozen model did).
The rest differ for known reasons:

- State lean is now available for every state and for 1998 and 2000, which adds 20 races the frozen fit dropped and
  two cycles. That moves the weight on Senate polls from 0.865 to 0.833 (and with it the two prior errors), the
  lean-slope error from 0.078 to 0.062, and the regional shock from 0.48 points to zero.
- The tail weight is not rounded (3.95 against 3.9).
- The weight on district polls is fitted on every earlier cycle with polls and lean, about 0.65. The frozen model
  fitted it on 2018 and 2022 only and got 0.46.

### Where the test differs from the published model

- **One poll window.** Final 21 days, equal weights, sponsored polls shifted by a flat as-of amount. Before 2018 only
  late polls exist, so the time decay, population weights and pollster-level sponsor rule cannot be tested further back;
  `backtest.py` still tests those on 2018 and 2022.
- **Senate races are Democrat against Republican only.** Races with an independent in the top two, all-party November
  rounds and a same-day special with the same two candidates are left out, from both the forecast and the seat count.
- **Appointed senators are not counted as incumbents.** The returns carry no incumbency; the flag is a name match to
  earlier winners.
- **Economic inputs are today's revised figures**, not what was published at the time.
- **The seat count covers modeled and fixed seats**: 418 to 432 of the 435 House seats from 2006, and 404 in 2004. The
  rest are all-party or three-way contests, rows the page parser skips (ranked-choice seats), or, in 2004, redrawn
  districts with no lean known beforehand.

### Found on the way

No number is changed for any of these: they are in frozen code or belong to other cards.

1. **`raw_polls.csv` is not a 21-day file.** It runs to 60 days before the election, and about half its polls are
   older than 21 days. The frozen model's calibrations (`calibrate.py`, `prior_weight.py`, `bias_analysis.py`) read
   every row, so "final three weeks" in their docstrings, in FORECAST.md and on the site described a 60-day window.
   The wording was corrected on 2026-11-20 (a correction note in FORECAST.md; the frozen `data/final/FORECAST.md` and
   `report.py` keep the original). No number changed. The harness filters to 21 days for fits and targets alike.
2. **Some results in `raw_polls.csv` are wrong or leave out fusion lines**: New Jersey 2006 is off by 7 points, New
   York 2010 by 7.5. The harness scores against the MIT Election Lab returns, summing a candidate's lines.
3. **Minnesota is missing from the House district fit.** `house_history.csv` counts candidates labelled
   "Democratic", and Minnesota's are DFL, so its eight seats are never `contested`. The harness forecasts and scores
   them but leaves the fit sample as the frozen model had it.
4. **The MIT Senate file has gaps**: Connecticut 2022 is absent, party is blank for six candidates (Wyoming 2020,
   Mississippi and Nevada 2024), and Georgia 2008 labels November "pre" and the runoff "gen". Each is handled in
   `senate_universe()`.

## Baseline

Scores of the current model, run 2026-11-20 with the House from 2004. "Competitive" means a forecast margin within 15
points; that is where the seat counts are decided, and the scores to watch.

| Version | Chamber | Races | Brier | Log loss | Competitive | Brier | Log loss | Margin RMSE | Mean error | In 80% range | In 50% range | Seat count in 80% range | Seat spread | Seat RMSE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Polls only | Senate | 352 | 0.043 | 0.143 | 156 | 0.090 | 0.294 | 8.8 | -0.3 | 79% | 53% | 9 of 11 | 0.27 | 1.9 |
| Polls only | House | 4172 | 0.034 | 0.124 | 897 | 0.134 | 0.422 | 9.5 | -1.8 | 82% | 47% | 9 of 11 | 0.30 | 11.8 |
| Polls and fundamentals | Senate | 352 | 0.043 | 0.145 | 158 | 0.086 | 0.282 | 8.3 | -0.4 | 82% | 54% | 10 of 11 | 0.26 | 1.9 |
| Polls and fundamentals | House | 4172 | 0.034 | 0.123 | 874 | 0.138 | 0.431 | 9.3 | -1.1 | 80% | 45% | 7 of 11 | 0.30 | 12.4 |
| Bias-adjusted | Senate | 352 | 0.043 | 0.144 | 154 | 0.087 | 0.285 | 8.3 | +0.0 | 82% | 56% | 10 of 11 | 0.25 | 1.9 |
| Bias-adjusted | House | 4172 | 0.035 | 0.126 | 860 | 0.141 | 0.446 | 9.6 | +0.9 | 76% | 44% | 7 of 11 | 0.31 | 10.9 |

Margins are Democratic minus Republican, two-party; a positive mean error means Democrats did better than forecast.
"Seat spread" is how far, on average, the result sat from the middle of the simulated seat distribution: 0.25 when
the ranges are right, toward 0.5 when results keep landing in the tails. It moves smoothly, where a count of cycles
inside a range can flip on one seat.
National environment error (RMSE, 11 cycles): polls only 3.7, polls and fundamentals 2.7, bias-adjusted 2.5.

Polls and fundamentals, by cycle (competitive races; seat forecast with its 80% range, then the result):

| Cycle | Environment: polls, fundamentals, blend, result | Senate log loss | Senate seats | House log loss | House seats |
|---|---|---|---|---|---|
| 2004 | +2.3, -6.8, -1.8, -2.7 | 0.288 | 15 (13 to 18), 15 | 0.417 | 195 (188 to 202), 193 |
| 2006 | +15.8, +7.1, +11.6, +8.3 | 0.272 | 20 (17 to 22), 22 | 0.470 | 213 (200 to 226), 207 |
| 2008 | +10.3, +13.0, +11.9, +11.0 | 0.132 | 18 (16 to 20), 19 | 0.504 | 252 (241 to 263), 244 |
| 2010 | -7.5, +1.6, -2.4, -7.0 | 0.357 | 12 (9 to 14), 13 | 0.469 | 221 (210 to 232), 191 |
| 2012 | +0.3, -5.4, -2.4, +1.1 | 0.330 | 19 (16 to 22), 23 | 0.648 | 181 (171 to 191), 195 |
| 2014 | -2.9, -8.6, -5.3, -5.9 | 0.211 | 13 (11 to 15), 12 | 0.475 | 186 (178 to 194), 182 |
| 2016 | +3.1, -2.2, +0.9, -1.0 | 0.397 | 13 (10 to 15), 11 | 0.357 | 196 (188 to 204), 194 |
| 2018 | +8.0, +9.2, +8.5, +8.8 | 0.240 | 21 (18 to 24), 21 | 0.468 | 209 (198 to 219), 222 |
| 2020 | +8.4, +7.1, +7.9, +3.2 | 0.355 | 16 (13 to 19), 13 | 0.327 | 237 (229 to 246), 221 |
| 2022 | -0.3, -7.7, -3.6, -2.8 | 0.281 | 13 (10 to 16), 15 | 0.407 | 207 (197 to 216), 211 |
| 2024 | -0.1, -1.4, -0.7, -2.7 | 0.234 | 17 (15 to 20), 17 | 0.221 | 211 (203 to 219), 213 |

Seat counts are of the seats in the test, not of all 435 (see above). 2004 has only 36 competitive districts.

What the baseline shows:

- **The House seat range may be too narrow; the evidence is mixed.** With fundamentals the result fell outside the 80%
  range in 4 of 11 cycles (2010, 2012, 2018, 2020) where about 2 are expected; polls only, it was outside in 2 of 11
  (2010, 2020). The seat spread is 0.30 in both. Single districts are covered as often as stated (80%), so any
  shortfall is in what districts share, which is what CM-2 and CM-3 test. Eleven cycles cannot settle it.
- **2010 is the largest seat miss**: 221 Democratic seats forecast, 191 won. The fundamentals are a small part of it:
  polls only, with the environment almost exactly right (-7.5 against -7.0), the forecast was still 216.
- **Fundamentals help the environment** (error 3.7 to 2.7) and the Senate, but not the House scores.
- **The simplified bias adjustment is mixed for the House.** District log loss is worse (0.446 against 0.431) and
  fewer districts fall inside their ranges (76%); the seat count is closer (seat RMSE 10.9 against 12.4). It is not
  the published adjustment, so it is a pointer for CM-7, not a verdict.
- **2012 is the worst House cycle** (log loss 0.648), the first on new lines. More history did not rescue it: fitted
  on seven cycles it scores much as it did on three (0.700).
- **Incumbency has shrunk steadily.** The fitted advantage is 23 points as of 2004 and 6 as of 2024
  (`backtest_asof_params.csv`). The four-cycle window follows it with a lag, which is CM-4's subject.
- **Senate races without polls are the Senate's weak point.** Their prior misses popular incumbents by 30 to 50
  points in 2004 and 2006 (margin RMSE 19 and 15 in those cycles, 3 to 6 since 2008).

Against the first version of this baseline (House from 2012, seven cycles): every Senate forecast is identical, and
House log loss in 2014 to 2024 moved by 0.02 or less, because those cycles now have 1998 to 2004 in the national
slope and the district-poll weight.

Forecasts are in `backtest_asof_races.csv` (all but the 2004 districts, as above), the as-of parameters by cycle in
`backtest_asof_params.csv`, and coverage, parity, all scores and the checksum of Jacobson's file in
`backtest_asof.json`.

## Adoption rule

*Confirmed 2026-11-20, with the three-cycle burn-in.*

Before running a change:

1. Write down the change, the chamber it is aimed at, and what it should improve.
2. Run it with `--tag`, then `--compare`. The comparison scores both versions on the same races: the baseline's
   competitive set.

A change is adopted if, in the chamber it is aimed at, on the polls-and-fundamentals version:

1. **Log loss on competitive races falls by more than 0.005 pooled over all scored cycles**, and also with the first
   scored cycle left out. That cycle, 2004, has the thinnest fit, and a change should not pass or fail on it alone.
   `--compare` prints both.
2. **It falls in at least two thirds of the cycles** (8 of 11 in either chamber), so one cycle cannot carry it.
3. **Calibration does not get worse**: the share of competitive races inside the 80% range stays between 75% and 85%
   or moves toward 80%, and the seat spread does not move away from 0.25 by more than 0.02.
4. **The other chamber does not get worse** by more than 0.005 in log loss.

The thresholds sit above what chance in the simulation does. Over reruns of the baseline with other random draws
(four on the first version, two on this one), pooled log loss moved by at most 0.0015, the 80% share by 0.007 and
the seat spread by 0.003. The count of cycles moved much more (a rerun that changes nothing "improves" 4 or 5 of 11),
which is why rule 2 never stands without rule 1.

A change that only alters uncertainty (ranges, correlations) is judged on 1, 3 and the seat spread, since it cannot
move margins. Margin RMSE and Brier are reported for every change and decide nothing by themselves.

Then 2026, once:

5. The adopted change is scored on 2026 with the same scores. The result is recorded whichever way it goes. Nothing
   is retuned after seeing it. A change that passes history and does worse in 2026 is a decision for the plan, not
   an automatic rejection: one cycle is one cycle.

A change to the harness itself (a new score, a wider poll window, new cycles from DA-2) is not a model change: it is
made first, the baseline is rerun and recorded, and candidates are compared with the new baseline.
