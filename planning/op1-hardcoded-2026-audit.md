# OP-1 step (a): where 2026 is hardcoded

Audit of every place the 2026 cycle is written into the code, done 2026-11-20 for card OP-1 of the work plan. It is
read-only: no code changed. Steps (b) and (c), the cycle config and the frozen-rebuild check, are a separate session
once the daily scorecard refresh has finished (California certifies in mid-December 2026).

Method: `grep -rn "2026" src --include=*.py` (319 lines in 40 files), plus a search for cycle facts written without
the year: election dates, seat counts, the president's name and party, random seeds.

## Summary

| Class | Lines | What to do |
|---|---|---|
| A. Cycle config | ~140 | Move into one cycle config read everywhere. Includes names derived from the year: file names, race keys, Wikipedia titles, report titles. |
| B. Historical constants | ~30 | Leave. Facts about past cycles, keyed by year already. |
| C. 2026 by design | ~150 | Leave. Post-mortem, scorecard and frozen-check code is about the 2026 forecast and stays that way. |

The forecast proper (`model/forecast.py`, `model/pollavg.py`, `collect/wiki.py`, `collect/polls.py`, `site/build.py`,
`run_all.py`) is the part that must become cycle-neutral for 2028. The scorecard and post-mortem scripts repeat for
2028 by taking the same config, but their 2026 copies are left as they are: they document the 2026 result.

## A. Cycle config: values to move

Grouped by the config key they would become. Each entry: file, line, what is there now.

**Election date and poll close**
- `run_all.py:25` `POLLS_CLOSE_UTC = 2026-11-03 23:00 UTC`
- `collect/generic_ballot.py:31` `END = 2026-11-03`; `:97` the list of election dates ends with 2026-11-03
- `collect/specials.py:31` the election-date list ends with 2026-11-03; `:41` `range(2007, 2026, 2)`
- `site/history.py:33` `ELECTION_2026 = 2026-11-03`
- `model/single_race.py:239` lines in force "after 2026-11-03"
- `collect/official_house.py:321`, `collect/official_senate.py:231, 263, 353` the date embedded in state result URLs and election ids (20261103)
- `collect/official_senate.py:307` Texas constants key `electionInfo["2026"]["GE"]`

**Cycle year, as a number**
- `collect/governors.py:36` `GOV_YEARS = range(1998, 2026)`; `:259-288` `races_2026()` and its output file
- `collect/fec_money.py:169-180` `y2026()`, `cycle: 2026`, the `"2026"` command word
- `collect/results_fec.py:23` `fec(cycle=2026)`
- `collect/results_margins.py:167` `general_boxes(..., year=2026)`; `:422` reporting-time check `"2026" in ...`
- `model/pollavg.py:159` `statewide(..., year=2026)`
- `model/bias_decay.py:67, 103` decay weight `0.5 ** ((2026 - cycle) / H)`; `:89-90` train/target split on `cycle < 2026`
- `model/fundamentals.py:86, 137` target row `year == 2026`
- `model/money_test.py:149` `cycle = 2026`
- `site/history.py:224-310` 2026 rows appended to the charts and CSVs, `year == 2026` lookups; `:345, 507, 618` axis tick ranges ending at 2026

**Poll windows (dates that are the cycle year plus a month and day)**
- `model/pollavg.py:119` generic ballot since 2026-08-01; `:138, 196, 254` Senate and governor since 2026-06-15; `:200, 293` House since 2026-07-01; `:227` approval since 2026-09-01; `:239` multi-candidate Senate since 2026-08-01
- `model/poll_audit.py:47` `SINCE = {senate: 2026-06-15, house: 2026-07-01}`
- `model/forecast.py:238` recent Senate polls since 2026-09-01
- `model/pollster_effects.py:156` 2026 pollsters since 2026-06-15
- `model/bias_confidence.py:146, 148` generic since 2026-01-01, Senate since 2026-08-01
- `site/build.py:118` sponsored-poll adjustments since 2026-06-15

**Seats and chambers**
- `model/forecast.py:355` `SENATE_NOT_UP = {R: 31, D: 34}` with the 53/47 split and the 22 R / 13 D seats up in the comment
- `model/forecast.py:385` `435 - d_seats - kiley_win` (435 is fixed; the independent-candidate carve-out is a 2026 special case)
- `model/forecast.py:539` majority threshold `51 - SENATE_NOT_UP["D"]`

**President and party**
- `model/bias_analysis.py:26` `2026: "R"` party holding the White House
- `model/bias_decay.py:33` `2026: ("Trump", "R", 2, "R")` president, party, term, House control
- `model/fundamentals.py:36` `2026: "R"`
- `model/environment.py:53` approval polls with `subject == "Donald Trump"`
- `model/pollavg.py:227` `approval(polls, subject="Donald Trump", ...)`
- `site/history.py:226, 252, 310` `president: "R"` on the appended 2026 rows

**Poll-source subjects and race keys**
- VoteHub subject `f"2026 {state_name}"`: `model/forecast.py:237`, `model/pollavg.py:148, 245, 264`, `model/poll_audit.py:104, 123`, `model/poll_settings.py:226, 246`, `site/build.py:170`
- Race key prefix `f"2026|{st}|H|..."` and `"2026|{st}|S|..."`: `collect/wiki.py:137, 183`, `collect/results.py:198, 222`, `collect/results_margins.py:75, 370, 414`, `collect/official_house.py:403`, `collect/wiki_polls.py:207-212`

**Wikipedia page titles**
- `collect/wiki.py:18-19` the four 2026 pages; `:112` the `"2026 PVI"` column match
- `collect/results.py:35` `PAGES` for Senate and House
- `collect/results_margins.py:67, 70` the per-state race-page title pattern
- `collect/governors.py:262` `2026_United_States_gubernatorial_elections`
- `collect/specials.py:40` the 2026 House page glob
- `model/forecast.py:161` the House page file name

**File names carrying the year**
- `data/interim/house_2026_races.csv`: `collect/wiki.py:138-139`, `model/forecast.py:312`, `model/single_race.py:240`, `site/build.py:105, 179`, `site/history.py:356`
- `data/interim/senate_2026_races.csv`: `collect/wiki.py:184-185`, `model/forecast.py:226`, `model/poll_settings.py:221`, `site/build.py:180`
- `generic_ballot_aggregates_2026.csv`: `collect/wiki.py:149`
- `fec_money_2026.csv`: `collect/fec_money.py:174`, `model/money_test.py:145`
- `governor_2026_races.csv`: `collect/governors.py:13, 287, 516`
- VoteHub snapshot folder `data/raw/votehub/2026-11-03`: `collect/wiki_polls.py:37`, `model/poll_audit.py:44`. This is the frozen snapshot and a pinned path by design; the config should name it rather than the code.
- Git tag `final-forecast-2026`: `run_all.py:26, 93`, `check_frozen.py:4`

**JSON output keys carrying the year** (rename only together with the site templates that read them)
- `inputs_2026`, `pred_2026`, `pred_2026_pres_party`, `range_check["2026"]`: `model/fundamentals.py:144-195`, `model/forecast.py:128, 190-191`, `model/report.py:73`, `postmortem/history_context.py:33-34`
- `top10_avg_pred_2026`, `pred_2026`: `model/bias_decay.py:110-132`, `model/forecast.py:48`, `site/build.py:95-99`
- `n_2026`, `n_polls_2026`, `polls_2026`, `table_2026`: `model/bias_confidence.py:91-98`, `model/pollster_effects.py:164-183`
- `n_pairs_2026`, `mean_2026`, `se_2026`, `weight_on_2026`, `pairs_2026`, `mean_generic_2026`, `mean_senate_2026`: `model/poll_settings.py:122-251`
- `votehub_polls_by_pollster_2026`: `model/poll_audit.py:466`
- `y2026`: `model/money_test.py:178`

**Economic vintages**
- `collect/econ.py:14` `VINTAGES["2026"] = "2026-10-01"`, the as-published data a forecaster had five weeks out. The config adds the next cycle's entry.

**Titles, labels and prose**
- `model/report.py:37` "# 2026 Midterm Forecast"; `:129, 160, 186` 2026 in explanatory text
- `site/og_image.py:32` "2026 Midterm Forecast"
- `site/history.py:229, 255, 333, 604-724` chart titles and source-table year ranges ending in 2026
- Module docstrings that say 2026 where they mean "the current cycle": `collect/polls.py:1`, `collect/wiki.py:1-6`, `collect/results.py:1`, `model/forecast.py:1-5`, `model/backtest.py:4, 32`, `model/prior_weight.py:6-7`, `model/pollster_effects.py:10`

**Random seeds**
- `model/forecast.py:31` `default_rng(2026)`; `model/governor_model.py:45` seed 20261108; `model/scorecard_margins.py:256` seed 20261103; `postmortem/state_error.py:47` and `postmortem/whatif_environment.py:21` seed 20261108. The forecast seed must stay 2026 for the frozen rebuild to match, so the config carries a `seed` that is 2026 for this cycle.

## B. Historical constants: leave as they are

Facts about past cycles, already keyed by year, where 2026 is simply the last entry or the end of a range.

- `collect/governors.py:352, 418` `ELECTION_2025` and `ELECTION_DATES` for the 2022 to 2024 governor polls
- `model/bias_decay.py:32-33`, `model/bias_analysis.py:26`, `model/fundamentals.py:36` the per-year president and party tables (2026's entry moves to config, the rest stays)
- `collect/econ.py:14` the 2018 and 2022 vintages
- `collect/history.py`, `collect/governors.py:3-7` ranges of historical Wikipedia pages
- `collect/fec_money.py:157` `cycle >= 2002`
- `site/history.py:712-724` source-table year ranges (the end year comes from config, the start years are facts)
- `model/single_race.py:18, 237`, `model/special_model.py:4`, `collect/specials.py:1-5` "2007-2026" ranges, which grow by one cycle each time

## C. 2026 by design: leave as they are

Code whose subject is the 2026 forecast and its scoring. For 2028 the same scripts run again with the new config;
their 2026 behaviour is the record and is not to be made generic.

- `check_frozen.py` throughout: the frozen final forecast is the 2026 one, with its tag, lock time and seed.
- `check_scorecard.py:12`, `collect/results.py:129`, `collect/results_margins.py:17-48, 227, 288, 447`, `collect/official_senate.py:36-45`: comments recording what happened in the 2026 count and the fixes it needed.
- `collect/fec_money.py:120, 126`: 2026 name-collision special cases (Graham, Sullivan) in comments.
- `collect/governors.py:10-12, 272`: 2026 governors are a held-out test, scored after certification.
- `collect/official_house.py` and `collect/official_senate.py` state adapters: written against 2026 result sites, whose URLs and ids change every election. OP-4 rewrites these for 2027 and 2028; a config value for the date helps but does not make them reusable on its own.
- `postmortem/*.py` (history_context, house_2026_breakdown, state_error, whatif_environment): the 2026 post-mortem by name. OP-1 keeps a template of these for 2028, not a generic version.
- `model/scorecard.py`, `model/scorecard_margins.py`: score the frozen 2026 forecast. Reusable once the config names the frozen folder and results files.
- `site/history.py`: the historical pages treat 2026 as the latest, provisional data point (`nat2026`, `label="2026*"`, `provisional = year == 2026`). Reusable once "latest cycle" comes from config.
- `collect/common.py:12`, `collect/econ.py:56`, `site/history.py:194, 730`, `site/og_image.py:61`, `wrangler.jsonc`: the project and site name, `polling2026`. A naming decision for SI-1, not a config value.

## Proposed config

One module, `src/cycle.py`, or a TOML file per cycle that it loads, chosen by an environment variable or a command
flag, defaulting to the current cycle:

```
year = 2026                     # cycle year
kind = "midterm"                # midterm | presidential
election_date = 2026-11-03
polls_close_utc = 2026-11-03T23:00:00Z
president = "Donald Trump"      # VoteHub approval subject
president_party = "R"
president_term = 2
house_control_before = "R"
senate_not_up = { R = 31, D = 34 }
poll_since = { generic = 2026-08-01, senate = 2026-06-15, house = 2026-07-01, governor = 2026-06-15, approval = 2026-09-01 }
econ_vintage = 2026-10-01
wikipedia = { house = "2026_United_States_House_of_Representatives_elections", senate = "2026_United_States_Senate_elections", governors = "2026_United_States_gubernatorial_elections", redistricting = "2025–2026_United_States_redistricting", pvi_column = "2026 PVI" }
votehub_snapshot = "data/raw/votehub/2026-11-03"
final_tag = "final-forecast-2026"
seed = 2026
```

Derived from it in code: race keys `f"{year}|..."`, VoteHub subjects `f"{year} {state}"`, file names
`house_{year}_races.csv`, report and image titles, chart axis ranges, the FEC cycle and the governor year range.

## Order of work for steps (b) and (c)

1. Add the config with the 2026 values and leave `check_frozen.py` unchanged. Run the frozen check: it must pass before anything else moves.
2. Replace the forecast path first (`forecast.py`, `pollavg.py`, `wiki.py`, `polls.py`, `fundamentals.py`, `bias_decay.py`, `run_all.py`, `site/build.py`). Frozen check after each file.
3. Replace the collectors and `site/history.py`. The scorecard run must still produce the same results tables from the saved 2026 snapshots.
4. Rename output JSON keys last, together with the site templates that read them, or leave them with a note. Renaming is cosmetic and is the one step that can break the site without the frozen check noticing.
5. Leave classes B and C untouched. Add a short note to the repo README saying how a new cycle is started: copy the config, fill in the dates and seats, run the collectors.

Open question for that session: whether the file names should drop the year entirely (`house_races.csv`) with a year
folder under `data/`, or keep `house_{year}_races.csv`. The frozen 2026 inputs are referenced by their current names,
so renaming means a compatibility shim in `check_frozen.py` or leaving the 2026 files where they are.
