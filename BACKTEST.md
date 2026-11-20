# Backtest

The out-of-sample test every change to the House, Senate and governor models has to pass (work plan card CM-1). Each
past cycle is forecast with every parameter fitted on earlier cycles only, then scored against the result.

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
| Governors (even years) | 1998 | 2004 to 2024 | the polls |

So both chambers, governors and the national environment are scored on the same 11 cycles.

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
- **Governors.** The first governor model (`governor_model.py`), re-estimated as of each cycle: prior = constant +
  slope x lean (the state's presidential lean, averaged over two elections) + slope x environment + incumbency,
  blended with the poll average; a polled race carries the statewide polls' shared miss in proportion to its weight
  on polls, and the environment's error in proportion to the rest. Run on that model's own sample, the harness's
  estimator returns its ten published parameters exactly (`parity_governor` in `backtest_asof.json`). The lean
  measure was chosen there with every cycle in view; it is fixed here, not re-chosen each cycle.
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
- **Governors are even years only, two-way races, 21-day polls.** Odd years (New Jersey, Virginia, Kentucky,
  Louisiana, Mississippi) and 2025 have no House vote to stand for the environment. `governor_inputs.py` now builds
  an environment for each as of its election day and tests it on the prior alone (results below); the odd-year
  races themselves stay in `governor_model.py`'s own backtest. That backtest scores 353 races at log loss 0.244, against 0.212 on 239 races
  here, and the two are not comparable: it leaves one cycle out at a time (so each fit sees later cycles), includes
  odd years, and uses 538's 60-day averages. Nothing from 2026 is in either (GV-4).
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
| Polls only | Governor | 239 | 0.066 | 0.213 | 130 | 0.114 | 0.353 | 7.7 | -2.1 | 82% | 48% | 11 of 11 | 0.24 | 1.4 |
| Polls and fundamentals | Governor | 239 | 0.065 | 0.212 | 133 | 0.110 | 0.342 | 8.1 | -2.1 | 81% | 51% | 11 of 11 | 0.23 | 1.3 |
| Bias-adjusted | Governor | 239 | 0.065 | 0.212 | 129 | 0.113 | 0.349 | 6.8 | -1.4 | 81% | 50% | 11 of 11 | 0.23 | 1.3 |

For governors the versions differ only in the environment fed to the prior. "Polls only" is the governor model as
written (its environment is the generic ballot). "Seat count" for governors is the number of races Democrats won.

Margins are Democratic minus Republican, two-party; a positive mean error means Democrats did better than forecast.
Rows for different versions are not like for like: each version has its own competitive set (156 Senate races polls
only, 158 with fundamentals). Version against version on the same races is in the chance section below.
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
- **Fundamentals help the environment** (error 3.7 to 2.7) but not clearly the races. On the same races they move
  log loss by +0.004 for the Senate, +0.002 for the House and -0.005 for governors, each within about one standard
  deviation of cycle luck (see "How much a score moves by chance").
- **The simplified bias adjustment is mixed for the House.** District log loss is worse (0.446 against 0.431) and
  fewer districts fall inside their ranges (76%); the seat count is closer (seat RMSE 10.9 against 12.4). It is not
  the published adjustment, so it is a pointer for CM-7, not a verdict.
- **2012 is the worst House cycle** (log loss 0.648), the first on new lines. More history did not rescue it: fitted
  on seven cycles it scores much as it did on three (0.700).
- **Incumbency has shrunk steadily.** The fitted advantage is 23 points as of 2004 and 6 as of 2024
  (`backtest_asof_params.csv`). The four-cycle window follows it with a lag, which is CM-4's subject.
- **Governors: few competitive races, and Democrats run behind the forecast.** There are 133 competitive races in 11
  cycles, and only 3 to 9 in a presidential year. Democrats did 2.1 points worse than forecast on average. The count
  of Democratic wins fell inside its 80% range in all 11 cycles, which is more often than 80% implies but is no
  evidence of ranges that are too wide on 11 cycles. The 27 unpolled races are forecast badly (margin RMSE 20).
- **Senate races without polls are the Senate's weak point.** Their prior misses popular incumbents by 30 to 50
  points in 2004 and 2006 (margin RMSE 19 and 15 in those cycles, 3 to 6 since 2008).

Against the first version of this baseline (House from 2012, seven cycles): every Senate forecast is identical, and
House log loss in 2014 to 2024 moved by 0.02 or less, because those cycles now have 1998 to 2004 in the national
slope and the district-poll weight.

Forecasts are in `backtest_asof_races.csv` (governors included; all but the 2004 districts, as above), the as-of parameters by cycle in
`backtest_asof_params.csv`, and coverage, parity, all scores and the checksum of Jacobson's file in
`backtest_asof.json`.

## How much a score moves by chance

Two kinds of chance sit under every comparison, and they are very different in size.

- **Simulation noise** is small. Rerunning the baseline with other random draws moves pooled log loss on competitive
  races by at most 0.0015 (House, Senate) and 0.0006 (governors).
- **Which cycles history dealt** is the large one. `--compare` now estimates it by redrawing the 11 cycles with
  replacement and recomputing the pooled gap. Between versions of the baseline itself:

| Comparison | Office | Pooled log-loss gap | SD over redrawn cycles | Cycles better |
|---|---|---|---|---|
| Polls only to polls and fundamentals | Senate | +0.004 | 0.004 | 7 of 11 |
| | House | +0.002 | 0.006 | 8 of 11 |
| | Governor | -0.005 | 0.005 | 7 of 11 |
| Polls and fundamentals to bias-adjusted | Senate | -0.004 | 0.006 | 4 of 11 |
| | House | +0.016 | 0.021 | 4 of 11 |
| | Governor | -0.002 | 0.002 | 5 of 11 |

(A negative gap is an improvement.) Three things follow:

- A gap of 0.005 is about one standard deviation of cycle luck for most of these pairs. It is clear of simulation
  noise and not clear of history. The standard deviation depends on the change (0.002 to 0.021 here), which is why
  `--compare` prints it for each candidate and no single threshold stands in for it.
- The count of cycles can disagree with the pooled gap: fundamentals "improve" 8 of 11 House cycles and make the
  pooled score slightly worse, because the three bad cycles are worse by more.
- The redraw test cannot stand without a size threshold either: a rerun that changes only the random draws came out
  "better in 96% of redraws" for governors, at a gap of 0.0005.

## Adoption rule

*Confirmed 2026-11-20, with the three-cycle burn-in, after the chance table above. A first version asked only for a
gain of 0.005, which is clear of simulation noise but not of cycle luck; rule 1 now asks for both. No candidate change
had been scored when it was set.*

Before running a change:

1. Write down the change, the office it is aimed at (House, Senate or governor), and what it should improve.
2. Run it with `--tag`, then `--compare`. The comparison scores both versions on the same races: the baseline's
   competitive set.

A change is adopted if, in the office it is aimed at, on the polls-and-fundamentals version:

1. **Log loss on competitive races, pooled over all scored cycles, falls by more than 0.005 and by more than its own
   standard deviation over redrawn cycles.** `--compare` prints the gap and that standard deviation for each
   candidate. The floor of 0.005 keeps out effects that are consistent but too small to matter; the standard
   deviation scales the bar to how much this particular change depends on which cycles are in the test. The gap must
   also exceed 0.005 with the first scored cycle left out: 2004 has the thinnest fit, and a change should not pass
   or fail on it alone.
2. **For the House and Senate, it falls in at least two thirds of the cycles** (8 of 11), so one cycle cannot carry
   it. This does not apply to governors: a presidential year has 3 to 9 competitive governor races, and a cycle that
   small is close to a coin flip.
3. **Calibration does not get worse**: the share of competitive races inside the 80% range stays between 75% and 85%
   or moves toward 80%, and the seat spread does not move away from 0.25 by more than 0.02.
4. **No other office gets worse** by more than 0.005 in log loss.

One standard deviation is a modest bar: a change with no real effect clears it about one time in six, before the
other conditions. Two would be the usual standard, and with 11 cycles almost nothing would reach it. That is the
trade made here, and the 2026 step below is the check on it.

The fixed thresholds sit above what chance in the simulation does. Over reruns of the baseline with other random
draws, pooled log loss moved by at most 0.0015, the 80% share by 0.007 and the seat spread by 0.003. The count of
cycles moved much more (a rerun that changes nothing "improves" 4 or 5 of 11), which is why rule 2 never stands
without rule 1.

A change that only alters uncertainty (ranges, correlations) is judged on 1, 3 and the seat spread, since it cannot
move margins. Margin RMSE and Brier are reported for every change and decide nothing by themselves.

Then 2026, once:

5. The adopted change is scored on 2026 with the same scores. The result is recorded whichever way it goes. Nothing
   is retuned after seeing it. A change that passes history and does worse in 2026 is a decision for the plan, not
   an automatic rejection: one cycle is one cycle.

A change to the harness itself (a new score, a wider poll window, new cycles from DA-2) is not a model change: it is
made first, the baseline is rerun and recorded, and candidates are compared with the new baseline.

## Candidates

Each entry is written before its first run, and every candidate that was run is reported, pass or fail.

### Governor lean (GV-3), written 2026-11-20 before any run

The baseline governor prior uses the state's presidential lean, averaged over the last two elections. Presidential
lean explains little of a governor's margin (slope about 0.4), so the question is whether recent statewide results
do better. Office: governor. Expected to improve: log loss and margin error on competitive races, mostly through
the races with few or no polls, since a polled race puts about 0.85 of its weight on polls.

Definitions, each using only results from before the race:

- *Statewide lean*: the mean of the state's Senate and governor general elections in the six years before the
  cycle, each as its two-party margin minus that year's national House margin. Senate results from MEDSL (1976 on),
  governor results from `governor_history.csv` (1998 on, even years; so the earliest training cycles lean on Senate
  results alone). Past margins include whatever the incumbents of the time were worth; no adjustment.
- *Previous governor margin*: the state's last governor race, two-party margin minus that year's national House
  margin. Where there is none on file (odd-year or pre-1998), the race falls back to the baseline prior.

Three candidates, run with `--gov-lean`:

| Tag | Prior |
|---|---|
| `govlean_statewide` | statewide lean in place of presidential lean |
| `govlean_both` | presidential lean and statewide lean together |
| `govlean_prevgov` | presidential lean and the previous governor margin together |

With three candidates, the chance that at least one clears the one-standard-deviation part of rule 1 by luck is
about 40%. If more than one passes, the one with the larger pooled gain is taken.

### Governor interval width (GV-3), written 2026-11-20 before any run

The first governor backtest (leave-one-cycle-out, 60-day polls) suggested count ranges that were too wide. No
candidate is defined in advance. The as-of baseline is read first: race-level coverage of the 50% and 80% ranges,
and where the count of Democratic wins fell in its forecast distribution in the five midterm cycles. A width change
is proposed, and written here before its run, only if those point the same way.

### Governor polls: earlier polls where there are no late ones (GV-3), written 2026-11-20 before its run

Found while building the 2026 poll table: under the 21-day rule 34 of 318 governor races (1998 to 2024) have no
polls, and 17 of those have polls ending 22 to 60 days out. The baseline forecasts such a race from the prior alone.
In 2026, 8 of the 36 races have no poll in the final 21 days.

Candidate `govpolls_fallback60` (`--gov-poll-fallback all`): a governor race with no polls ending in the final 21 days
uses its polls ending 22 to 60 days out, averaged and weighted exactly as late polls are. Late polls, where there
are any, are used alone as now. Office: governor. Expected to improve: margin error and log loss in the races
concerned; the rest should not move. Older polls are treated as being as accurate as late ones, which flatters
them; if the candidate passes, that is the next thing to test, not something to tune here.

### The same, in the forecast only (GV-3), written 2026-11-20 after the run above and before its own

`govpolls_fallback60` was run and its result is in the results section. It also fed the earlier polls into the fit,
which lowered the weight on polls for every race (0.86 to 0.83 by 2024) and moved races it was not aimed at: of
its pooled gain of 0.016, the 7 competitive races it changed directly gave 0.018 and the other 126 lost 0.002.

Candidate `govpolls_fallback60_fcst` (`--gov-poll-fallback forecast`): the fit is the baseline's, on late polls
only; the earlier polls enter only the forecast of a race that has no late ones. Expected: the same gain in those
races, and nothing else moves. This is a second look at one idea, chosen after seeing the first result, and counts
as such.

### Governor interval width, read first (GV-3), 2026-11-20

Read from the baseline before proposing anything, as written above:

- **Races.** On the 133 competitive races the 80% range held 81% of results and the 50% range 51%.
- **Counts.** The number of Democratic wins fell inside its 80% range in all 11 cycles, and in the five midterms
  sat at the 16th, 61st, 27th, 20th and 78th percentile of its forecast distribution. Eleven of eleven happens by
  chance about one time in twelve when the ranges are right, so this is weak evidence of ranges that are too wide.
- **Shared error.** Each cycle's mean error on the margin, set against the spread the model gives it: in the five
  midterms it was 0.6 of that spread on average (too wide, if anything), and in the six presidential years 1.8
  (too narrow), with 2020 alone at 3.6. The two halves disagree, and both rest on five or six cycles.

These do not point the same way, so no change to the overall width is proposed. The first backtest's "too wide"
reading does not survive the as-of test.

One part does stand out. For the 27 races forecast from the prior alone, the 80% range held 52% of results. Their
spread is a robust (median-based) estimate of the prior's error, about 13 points, and their actual error was 20.

Candidate `govwidth_unpolled` (`--gov-unpolled-sd rms`): a race forecast from the prior alone takes the prior's
root-mean-square error over the training races (about 15 points) as its spread, in place of the robust estimate.
Office: governor. It changes uncertainty only, so it is judged on log loss, coverage and the count spread. Expected:
better coverage in those races and a small log-loss gain; nothing else moves.

### Results (GV-3), 2026-11-20

Six candidates were run, all against the governor baseline on its 133 competitive races, polls-and-fundamentals
version. Every baseline forecast was matched in every run, and no Senate or House forecast moved in any of them.
A negative gap is an improvement.

| Candidate | Pooled log-loss gap | Its SD over redrawn cycles | Gap without 2004 | Cycles better | Share in 80% range (0.81) | Count spread (0.228) | Rule |
|---|---|---|---|---|---|---|---|
| `govlean_statewide` | -0.007 | 0.009 | -0.007 | 7 of 11 | 0.79 | 0.210 | fails: gain smaller than its SD |
| `govlean_both` | +0.003 | 0.002 | +0.002 | 4 of 11 | 0.81 | 0.231 | fails: worse |
| `govlean_prevgov` | +0.034 | 0.036 | +0.038 | 6 of 11 | 0.79 | 0.235 | fails: worse |
| `govpolls_fallback60` | -0.016 | 0.011 | -0.023 | 7 of 11 | 0.77 | 0.235 | passes |
| `govpolls_fallback60_fcst` | -0.018 | 0.008 | -0.019 | 6 of 11 | 0.80 | 0.229 | passes |
| `govwidth_unpolled` | +0.001 | 0.001 | +0.001 | 3 of 11 | 0.81 | 0.230 | fails: worse |

The comparison files are `data/processed/backtest_asof_<candidate>_vs_baseline.json`.

One more run was made and is not a candidate: the forecast-only earlier-polls change and the width change together
(gap -0.017, SD 0.008). It was meant as the combined design if both passed alone; the width change did not, so it
shows only that the two together score as the first does.

**Lean: presidential lean stays.** Recent statewide results do not beat it.

- In place of presidential lean, the statewide measure gets a slope of 0.05 to 0.29 against 0.21 to 0.36, and
  the prior's error over all 239 races rises from 15.5 to 15.9 points. Its log-loss gain is within what a redraw
  of cycles produces.
- Beside presidential lean it adds nothing: its slope is between -0.11 and +0.07.
- The previous governor margin makes things worse. It can only be fitted on states with an earlier race on file
  (35 races for 2004, 46 for 2006), and there its slope comes out negative (-0.29) with an environment slope above
  1.3. In 2006 it put three safe Republican seats (Hawaii, Vermont, Nebraska) at 76% to 91% Democratic. By 2016 the
  slope is near zero. More history (DA-2) would settle whether there is anything here; this test cannot.
- As run, "governor results" in both measures are the harness's own races: two-way, even years, 1998 on. None of
  the measures was adjusted for who the incumbents were.

**Earlier polls where there are no late ones: passes, in both versions.** In 17 scored races with no poll in the
final 21 days but some 22 to 60 days out, the margin error falls from 22.0 points to 10.4 (forecast-only) or 10.8
(refit). Seven of them were "competitive" in the baseline only because the prior put them near even, and in both
versions those seven carry the whole gain: Vermont 2006 and 2020, North Dakota 2008, Wyoming 2010, Maryland 2018
and Delaware 2024 improve, Nebraska 2022 gets slightly worse. The baseline had Maryland 2018 (Hogan, re-elected by
12) at 47% Democratic and Vermont 2020 (Scott, by 43) at 48%. Over all 239 races, competitive or not, log loss
falls from 0.212 to 0.200 (forecast-only) or 0.201 (refit).

- The forecast-only version is the cleaner of the two: the other 222 races are unchanged to the last digit, the gain
  is more than twice its standard deviation, and coverage stays at 80%. The version that also refits on the earlier
  polls lowers the weight on polls for every race, takes the 80% range's coverage down to 77%, and makes the other
  126 competitive races slightly worse (+0.002).
- The ranges for these 17 races are too narrow: the 80% range held 53% of results in the baseline, 53% in the
  forecast-only version and 47% in the refit. Earlier polls are given a late poll's accuracy, which they do not
  have. That is the next thing to test, and it was not tuned here.
- Every historical gain is a lopsided race the prior had near even. In 2026 the change applies to Maryland and
  Oregon, and Oregon is not of that kind: its earlier polls are about even where the prior expects a clear
  Democratic win. History says nothing about how well earlier polls do in a case like that.
- Not adopted in the harness's default yet: fixing the design is GV-4's step. The baseline tables above are
  unchanged.

**Interval width: no change.** The overall width is about right on races and not clearly wrong on counts (above).
Widening the prior-only races failed: log loss on competitive races got slightly worse (+0.001) and coverage in
those 27 races moved only from 52% to 56%. Their problem is the prior's centre in races with a popular incumbent,
not its spread, and the earlier-polls change addresses 17 of the 27 directly.

**Chance.** With six candidates, about one would be expected to clear the one-standard-deviation bar by luck.
One idea passed. Its two versions are not two confirmations: both gains come from the same seven races. What
speaks for it is the size of the gain (more than two standard deviations in the forecast-only version) and a
mechanism visible race by race. It still gets its single test on 2026 (rule 5).

### Odd-year environment as of each date (GV-3), 2026-11-20

`python src/model/governor_inputs.py offyear` writes, for each odd year 1999 to 2025, what was known on election
day: the generic-ballot average of the day before, the president's approval, the last House vote, and the
off-cycle estimator fitted on elections before that year (`data/interim/governor_offyear_env.csv`). Each odd-year
race is then forecast from the prior alone, fitted on even years before it (31 races, 2003 to 2025;
`data/processed/governor_offyear_env.json`). Margin error by environment:

| Environment | All 31 | Year after a presidential election (12) | Year before one (19) |
|---|---|---|---|
| Last House vote, carried forward | 18.7 | 15.9 | 20.3 |
| Generic ballot of the day | 18.6 | 12.9 | 21.4 |
| Estimator, midterm-like | 18.3 | 11.6 | 21.4 |
| Estimator, scaled by term year on earlier odd years | 17.7 | 10.7 | 21.0 |

The term-year estimator holds up when every fit is as of the date: in New Jersey and Virginia it has the lowest
error, and the generic ballot of the day does not beat it. For 2025 it gave D+16.5 from data through 2024 (the
generic ballot said D+2.9), and the prior's errors were 1.7 and 3.7 points. In the year before a presidential
election no environment helps; those races turn on the candidates. Twelve races is a small sample, and before
2016 the generic-ballot series is FiveThirtyEight's published historical average, not a rebuild from polls.

### 2026 inputs (GV-3), 2026-11-20

`python src/model/governor_inputs.py 2026` reads the final forecast's poll snapshot (Nov 3, before polls closed)
and writes the 2026 races in the harness's shape, with no results: `data/interim/governor_2026_polls.csv` (383
polls naming both nominees) and `data/interim/governor_2026_inputs.csv` (36 races: incumbency, lean, the plain
21-day mean, the 22-to-60-day mean, and the published forecast's weighted average for comparison).

- 28 races have a poll in the final 21 days; 2 more (Maryland, Oregon) have only earlier ones; 6 have none in 60
  days (Arkansas, Hawaii, Idaho, New Mexico, Oklahoma, Wyoming).
- The plain late mean and the weighted average differ by 4.4 points RMS over 28 races, but most of that is Rhode
  Island; without it the gap is about 2. The model was fitted on plain 21-day means, so that is the one to feed
  it. Which average the frozen design names is for GV-4.
- The sponsor columns count VoteHub's party flag, which also marks a pollster's affiliation where no sponsor is
  listed; the backtest's sponsor shift was fitted on FiveThirtyEight's flag. The poll file carries
  `sponsor_listed` so the two can be told apart when the shift is applied.
- Rhode Island is a three-way race in the polls (an independent at 25% to 34%). The model covers two-way races, so
  it needs a decision at GV-4, before any result is read.
- Found on the way: `pollavg.statewide()` matched candidates by surname alone, and Nevada has two Fords on the
  ballot. Its weighted average read R+36; it is D+2.6 once the nominee's full name decides. Fixed there and in
  the new table. No published number used that function.

### Presidential approval in the governor prior, written 2026-11-20 before any run

The prior already carries the national environment, which moves with the president's approval and shifts every
race alike. The idea tested here is that approval also bears unevenly: more on a state whose governor is of the
president's party, and more or less depending on the state's lean. Approval is Gallup's average from July 15 to
October 31 of the election year, known before the election; a = approval minus 50, and s = +1 under a Democratic
president, -1 under a Republican.

- *Party agreement*: s x a x agree, where agree = +1 if the sitting governor is of the president's party (running
  or not) and -1 if not. A positive slope means a popular president helps his party hold its own governorships
  more than he helps it take the other side's.
- *Lean*: a x lean (the presidential lean already in the prior). A positive slope means a popular president helps
  his party more in the states that already lean to it.

Candidate `govprior_approval` (`--gov-lean approval`): both terms added to the baseline prior. Office: governor.
Expected to improve: the prior, and so mostly races with few or no polls. Approval takes one value per cycle, and
the first fits have three to five cycles, so the slopes will be unstable early; the slopes by cycle are reported
with the result. One candidate, not one per term, to keep the count of tries down.

**Result (2026-11-20): fails.** Pooled gap -0.0025 against a standard deviation of 0.0030 (-0.0047 without 2004;
better in 7 of 11 cycles; coverage and count spread unchanged). The gain is under the 0.005 floor and under its
own standard deviation. That makes seven candidates run in GV-3.

- Both slopes keep their sign in every fit, which is more than the lean candidates managed. The lean term is
  about -0.06 per point of approval per 10 points of lean: under a president at 40%, state lean counts for roughly
  0.39 a point where the baseline has 0.33. On all 14 cycles its t-ratio is -2.2 with errors clustered by cycle.
- The party-agreement term is about -0.10 to -0.23 and not distinguishable from zero (t = -1.2).
- The prior's own error does not fall (15.5 to 15.6 points); the model's margin error falls from 9.0 to 8.7, and
  in the 27 races without polls from 20.2 to 19.3.
- Worth another look when DA-2 adds cycles: a term that is steady in sign but too small to clear the bar on 11
  cycles is the kind of thing more history can settle.

### A governor's own approval: not tested, no data on hand (2026-11-20)

Nothing in the repo measures a governor's approval, so this is a question for the data track, not a candidate.
What the backtest can say is how much there is to gain:

- **Polls carry most of it, not all.** In the 125 polled races with an incumbent running, the prior misses by 15.4
  points and the model by 6.2. But the model's miss still follows the prior's: for each point the incumbent beats
  the prior, the result beats the final forecast by 0.21 of a point. About 0.14 of that is the weight the model
  keeps on the prior; the rest is polls understating well-liked incumbents.
- **Without polls there is nothing else.** In the 21 unpolled races with an incumbent the prior misses by 19.7
  points. These are the Hogan and Scott cases: governors far more popular than their state's lean.
- So approval would matter most where polls are thin or absent, which is also every forecast made early in a cycle
  (2027's races, and 2028 before the autumn).

### Unpolled governor races from the polled ones, written 2026-11-20 before any run

A race with no polls is forecast from the prior alone. The idea: the polled races of the same cycle show how far
polls sit from the prior, and an unpolled state can borrow that gap, either from all polled states alike or mostly
from the states that resemble it.

- For each polled race, gap = poll average minus prior. For an unpolled race, z = the weighted mean gap of that
  cycle's polled races, and the forecast is prior + c x z. The spread of the forecast is unchanged.
- c is fitted as of each cycle on the earlier cycles' polled races, each treated as if it were unpolled: its result
  minus its prior, regressed on the z it would have had from the other polled races of its cycle.
- *Flat* weights every polled race equally. *Demographic* weights a polled state by exp(-d^2 / 2m^2), where d is
  the distance between the two states on seven standardized measures (share with a bachelor's degree, log median
  income, white, Black and Latino shares, urban and rural shares) and m is the median distance between states.

Candidates: `govunpolled_flat` and `govunpolled_demo` (`--gov-unpolled flat|demo`). Office: governor. Expected to
improve: margin error and log loss in the unpolled races. Flat is the control: demographic similarity has to beat
it, not just the baseline.

Two limits known in advance. The demographics are one snapshot (the 2015-2019 American Community Survey, from The
Downballot's state tables), used for every cycle back to 2004; states change slowly, but for the early cycles this
is a look ahead at demographics, though not at any result. And the largest unpolled misses so far were popular
incumbents, which no neighbouring state's polls can see.

### The incumbent's own last margin, written 2026-11-20 before its run

`govlean_prevgov` above used the state's previous governor race whoever was running, and failed. This is the
narrower idea: when the incumbent is running, how they did last time says something about them as a candidate.

- *Incumbent's last margin*: where the incumbent is running and won the state's previous governor race (matched
  by surname), that race's two-party margin minus that year's national House margin. Zero for an open seat. Where
  an incumbent is running and there is no such race on file (first elected before 1998 or in an odd year, or
  never elected: a successor), the race keeps the baseline prior and is left out of this term's fit.

Candidate `govprior_incprev` (`--gov-lean incprev`): the term added to the baseline prior. Office: governor.
Expected to improve: races with an incumbent and few or no polls. Known in advance: results on file start in 1998,
so the 2004 and 2006 fits have few incumbents with a past margin, the weakness that sank `govlean_prevgov`; open
seats are kept in the fit this time, which should steady the other slopes.

**Results (2026-11-20): all three fail.**

| Candidate | Pooled log-loss gap | Its SD | Margin error, 27 unpolled races (20.2) | Rule |
|---|---|---|---|---|
| `govunpolled_flat` | +0.001 | 0.001 | 20.7 | fails: worse |
| `govunpolled_demo` | +0.001 | 0.001 | 20.6 | fails: worse |
| `govprior_incprev` | +0.027 | 0.017 | 22.1 | fails: worse |

- Borrowing from polled races does not help, and the fitted c is negative in every cycle (-0.06 to -0.6): where
  polls sit above the prior in the polled states, the unpolled states did not follow. Demographic weights are no
  better than flat ones. An unpolled governor race is unpolled because it is not close, and what the prior gets
  wrong there is the candidate, which other states' polls do not carry.
- The incumbent's last margin has the same weakness as the previous-governor margin: the slope is -0.45 in the
  fits for 2004 to 2008, when few incumbents have a race on file, and it wrecks 2006 and 2008. From 2010 the slope
  is small and positive (0.08 to 0.22) and the forecasts barely move. It needs governor results from before 1998
  to be tested fairly (DA-2).

### Expert ratings in the governor prior, written 2026-11-20 before any run

The governor model uses no expert ratings. The yearly Wikipedia overview pages, already cached, carry the final
pre-election ratings for 2002 and every even year from 2006 (`python src/model/governor_inputs.py ratings` ->
`data/interim/governor_ratings.csv`).

- *Rating*: the mean of Cook, Sabato and Rothenberg / Inside Elections where each rated the race, on a scale from
  -3 (safe Republican) through 0 (toss-up) to +3 (safe Democratic), with tilt at 0.5, lean at 1 and likely at 2.
  These three are the raters present throughout. The dates are the ones on the page, mostly the final week, a few
  earlier (Cook: August 2016, early October 2010); none is after the election.
- Candidate `govprior_ratings` (`--gov-lean ratings`): the rating added to the baseline prior, everything else
  (weight on polls, spreads) refitted as of each cycle as usual. A cycle is forecast this way once three earlier
  cycles have ratings, so 2010 to 2024; 2004 to 2008 keep the baseline. Office: governor.
- Expected to improve: races with few or no polls, where a rating knows what the prior cannot (a popular
  incumbent). In polled races ratings mostly restate the polls, so little should change there.
- Known in advance: raters see the polls, so this is not independent information; and the pages are today's
  versions of the tables, trusted to show the ratings as they stood before each election.

### More weight on polls, with more uncertainty, written 2026-11-20 before any run

The weight on polls is fitted (0.75 rising to 0.86) and the prior's spread follows from it. The question is whether
forecasts would do better leaning harder on polls while admitting more uncertainty. In the model the two are tied:
a wider prior raises the weight on polls and widens the race's spread together.

| Tag | Change |
|---|---|
| `govw_prior15` | the prior's spread x 1.5 in polled races: weight on polls about 0.93, race spread up about 4% |
| `gov_wide15` | the spread of every polled race x 1.15, weights unchanged |
| `govw_prior15_wide15` | both |

(`--gov-prior-sd-scale`, `--gov-sd-scale`.) Office: governor. The baseline's coverage on competitive races is
already 81% and 51%, so the expectation is that widening alone fails; the open question is the weight.

### Results: ratings, and weight with uncertainty (2026-11-20)

| Candidate | Pooled log-loss gap | Its SD | Gap without 2004 | Cycles better | Share in 80% range (0.81) | Count spread (0.228) | Rule |
|---|---|---|---|---|---|---|---|
| `govprior_ratings` | -0.018 | 0.017 | -0.019 | 6 of 11 | 0.77 | 0.261 | passes, narrowly |
| `govw_prior15` | +0.007 | 0.009 | +0.013 | 3 of 11 | 0.81 | 0.237 | fails: worse |
| `gov_wide15` | +0.005 | 0.003 | +0.006 | 2 of 11 | 0.83 | 0.228 | fails: worse |
| `govw_prior15_wide15` | +0.012 | 0.010 | +0.018 | 3 of 11 | 0.84 | 0.236 | fails: worse |

**More weight on polls, more uncertainty: the data does not support either.** Raising the weight on polls to
about 0.93 makes log loss worse, widening the ranges makes it worse, and doing both is worst. The fitted weight
and the present widths stand.

**Ratings: pass, by a hair, and the gain is in the races without polls.** The gain (0.018) is just over its
standard deviation (0.017). Ratings enter only from 2010, so the test is eight cycles, not eleven. Over those 184
races:

| | Races | Prior's margin error | Model's margin error | Log loss |
|---|---|---|---|---|
| No polls | 20 | 19.2 to 10.4 | 19.2 to 10.4 | 0.350 to 0.066 |
| One or two polls | 53 | 18.9 to 12.1 | 9.0 to 8.0 | 0.083 to 0.060 |
| All polled races | 164 | 14.4 to 9.6 | 6.6 to 6.3 | 0.207 to 0.206 |

- With a rating in it the prior's error falls by a third, the slope on lean drops from about 0.33 to 0.06 and
  incumbency from 15 points to about 2: the raters have already priced both in. The fitted weight on polls falls
  from 0.86 to 0.76.
- In polled races it is a wash on log loss. It fixes Vermont 2020 and Maryland 2018, the same races the
  earlier-polls change fixes, and it moves some polled toss-ups the wrong way (Kansas 2014 from 39% to 65%
  Democratic, Iowa 2018 from 41% to 61%; Republicans won both).
- Ranges get too narrow: the 80% range's coverage on competitive races falls from 81% to 77%, and over all races
  from 77% to 74%. The spread given to an unpolled race drops to about 8.5 points where its error is 10.4. A
  design that adopts ratings needs its widths looked at again.
- Limits: raters see the polls, so a rating is not independent of them; the tables are today's versions of the
  pages; Cook's rating is from August in 2016 and early October in 2010.

**Ratings and earlier polls together** (a confirmation run, since each passed alone, not a new candidate): gap
-0.022, SD 0.018, better in 8 of 11 cycles; log loss over all 239 races 0.212 to 0.185 (ratings alone 0.188,
earlier polls alone 0.200). Coverage on competitive races is 75%, at the edge of the band the rule allows.

**Count.** Fourteen candidates have now been run for governors. About two would be expected to clear the
one-standard-deviation bar by luck. Two ideas passed, and both act on the same weakness: races the polls do not
reach. Ratings passed with almost no margin; what speaks for them is the table above, not the pooled score.

One version not run: ratings used only for races without late polls, which is where the whole gain is. It was not
written down in advance, so it is left as the next candidate, not slipped in here.
