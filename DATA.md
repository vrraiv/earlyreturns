# Data

The sources this project collects, the datasets built from them, and how to credit them. The licence for derived
data is in `LICENSE-DATA.md`. The public version of this page is the Election data site's
[Sources and downloads](https://polling2026.vikramrai.com/history/sources.html) page.

## Sources

Raw copies live in `data/raw/<source>/<date>/`, each with a `manifest.json` of URLs and retrieval times.

| Source | What we take | Years | Raw copy | Credit |
|---|---|---|---|---|
| **Wikipedia** (REST and action APIs) | Election overview pages (House 1946-2026, governors 1998-2026, presidential 1992-2024, House specials 2007-2026); statewide and nationwide presidential polling pages (2004-2016); 2026 race pages and poll tables; aggregator tables | 1946-2026 | `wikipedia/`, `wikipedia_hist/`, `wikipedia_results/` (in git); `wikipedia_results_pages/`, `wikipedia_polls_asof/` (not in git; revision ids kept) | Wikipedia contributors, CC BY-SA 4.0 |
| Cook PVI and expert ratings, via Wikipedia | District and state lean; Cook, Sabato, Inside Elections and other ratings | 2006-2026 | within the Wikipedia pages | Cook Political Report; each rater by name |
| Aggregator averages, via Wikipedia | 2026 generic-ballot and approval averages (DDHQ, RealClearPolitics, Silver Bulletin, NBC, FiftyPlusOne and others) | 2026 | within the Wikipedia pages | Each aggregator by name |
| **FiveThirtyEight data repository** (GitHub) | `raw_polls.csv` (20,466 final-three-week polls with results, 1998-2023, including 485 for House specials); pollster ratings; generic-ballot average | 1995-2023 | `538_github/` | FiveThirtyEight (ABC News), CC BY 4.0 |
| **FiveThirtyEight poll files**, via the Internet Archive | Presidential approval (15,181 polls, 2017-2025); generic-ballot, Senate, House and governor polls (2016-2024); presidential general-election and primary polls, full cycles (2020-2024); the 2016 forecast's presidential polls (Nov 2015 to Election Day) | 2016-2025 | `538_wayback/` | FiveThirtyEight (ABC News), via the Internet Archive |
| **The Economist** presidential model ([us-potus-model](https://github.com/TheEconomist/us-potus-model), pinned commit) | State and national presidential polls, compiled from HuffPost Pollster and others (2012 national in the dataset; the rest for cross-checking) | 2008-2016 | `economist_potus/` | The Economist (G. Elliott Morris, Merlin Heidemanns, Andrew Gelman), MIT licence |
| **VoteHub** API | Senate, House, governor, generic-ballot and approval polls (6,108 records in the final snapshot) | 2025-2026 | `votehub/`, `votehub_audit/` | VoteHub |
| **American Presidency Project** (UC Santa Barbara) | Gallup presidential approval, poll by poll | 1941-2021 | `ucsb/` | Gallup, via the American Presidency Project (Gerhard Peters). Not openly licensed: the site shows derived figures only |
| **FRED / ALFRED** (St. Louis Fed) | CPI, gasoline, real disposable income, unemployment, payrolls, GDP growth; vintage series | 1946-2026 | `fred/`, `alfred/` | BLS, BEA and EIA, via FRED (public domain) |
| **FRED state series** | State unemployment and income | 1950-2026 | `fred_state/` | BLS and BEA, via FRED (public domain) |
| **FEC** API | Candidate fundraising totals (no individual contributor data) | 2002-2026 | `fec/` | Federal Election Commission (public domain) |
| **California Secretary of State** API | 2026 House results by district | 2026 | `ca_sos/` | California Secretary of State |
| **State election offices** (GA, IA, LA, MN, MT, NE, SC, TX) | 2026 official Senate and House results | 2026 | `official/`, `official_manual/` | Each state's office |
| **AtlasIntel** poll reports | Toplines of 8 Senate polls missing from VoteHub (`data/supplement/polls_supplement.json`) | 2026 | not in git (checksums kept) | AtlasIntel |

University of Michigan consumer sentiment (`UMCSENT`) is in the raw FRED folder but isn't used in any output.

### Linked sources

Some sources are free to use with credit but ask that their tables not be reproduced whole. Their raw copies are not
committed: they live in `data/linked/<source>/<date>/`, which is gitignored, and `data/linked/manifest.json` (committed)
records every fetch with its URL, the source's page, the sheet and tab, the retrieval time and a checksum. Running the
collector rebuilds the store. Only tables derived from them are committed, and the site links to the source's own page
wherever it would otherwise link to a copy of the data.

| Source | What we take | Years | Collector | Credit and link |
|---|---|---|---|---|
| **The Downballot** data sheets | Presidential results by state (vote counts for the Democrat and the main opposition) | 1828-2024 | `src/collect/downballot.py` | The Downballot, [the-downballot.com/p/data](https://www.the-downballot.com/p/data). Free to use with a citation and a link; please do not reproduce whole spreadsheets |

## Derived datasets

All in git, under the licence in `LICENSE-DATA.md`.

| File | Built by | Years | Contents |
|---|---|---|---|
| `data/interim/house_national_vote.csv` | `src/collect/history.py` | 1946-2024 | National House vote, two-party margin |
| `data/interim/gallup_approval.csv` | `src/collect/history.py` | 1941-2021 | Gallup approval, poll by poll |
| `data/interim/fundamentals_dataset.csv` | `src/model/fundamentals.py` | 1946-2026 | Per election: president's party, House margin, previous margin, approval, inflation, gas, income, unemployment |
| `data/interim/house_history.csv` | `src/model/house_structure.py` | 2006-2024 | Every House district: Cook PVI, incumbent, status, vote shares, national vote |
| `data/interim/state_presidential.csv` | `src/collect/governors.py` | 1992-2024 | State presidential results and lean vs the nation |
| `data/interim/state_presidential_history.csv` | `src/collect/downballot.py` | 1828-2024 | State two-party margin, the nation's, and lean, computed from The Downballot's vote counts (counts not included). Matches the Wikipedia table above within 0.22 points for 1992-2024 |
| `data/interim/president_general_polls.csv` | `src/collect/pres_polls.py` | 2000-2024 | Presidential polls by state, district (ME, NE) and nationally, one row per poll question: eventual nominees' shares and margin. Whole cycles from 2004 (Wikipedia for 2004 states, 2008 and 2012 states; The Economist for 2012 national; FiveThirtyEight for 2016 to 2024); late polls only for 2000 and 2004 national (FiveThirtyEight `raw_polls.csv`). The script's docstring records why each source was chosen |
| `data/interim/president_poll_crosscheck*.csv` | `src/collect/pres_polls_crosscheck.py` | 2004-2020 | The poll sources matched against each other poll by poll: share found, share agreeing, gaps between their averages by state and window, and the matched polls that differ by more than 2 points |
| `data/interim/president_poll_coverage.csv` | `src/collect/pres_polls.py` | 2000-2024 | Polls and pollsters by cycle and state, in the final three weeks and in all, with the result's margin and lean |
| `data/interim/governor_history.csv` | `src/collect/governors.py` | 1998-2025 | Every governor race: incumbent, status, candidates and shares |
| `data/interim/governor_dataset.csv` | `src/collect/governors.py` | 1998-2025 | Governor races with lean, environment, approval, previous margin, poll averages |
| `data/interim/governor_polls_wiki.csv` | `src/collect/governors.py` | 2022-2024 | Governor polls from Wikipedia race pages |
| `data/interim/house_specials.csv` | `src/collect/specials.py` | 2007-2026 | House specials with district lean on the lines in force |
| `data/interim/generic_ballot_daily.csv` | `src/collect/generic_ballot.py` | 1995-2026 | Generic-ballot polling average by day: FiveThirtyEight's average to 2016, then a plain average of FiveThirtyEight's and VoteHub's polls (latest per pollster, 30 days) |
| `data/final/bias_race_level.csv` | `src/model/bias_analysis.py` | 2002-2022 | Senate and governor races: final-three-week poll average vs result |
| `data/final/calibration.json` | `src/model/calibrate.py` | 1998-2022 | Polling misses by cycle; poll-average error by number of polls |
| `data/final/pollster_effects.json` | `src/model/pollster_effects.py` | 1998-2022 | Pollster house effects and the sponsored-poll shift |
| `data/final/error_structure.json` | `src/model/error_structure.py` | 1998-2022 | Census-region shocks; slope on lean |
| `data/final/state_econ.json`, `money_test.json` | `src/model/state_econ.py`, `money_test.py` | 1998-2022 | Tests of local unemployment and fundraising |
| `data/final/*` (the rest) | the frozen forecast | 2026 | Forecast inputs and outputs; never rewritten |
| `data/scorecard/*` | `src/run_scorecard.py` | 2026 | Results, margins, poll audit |
| `data/postmortem/*` | `src/postmortem/*.py` | 1946-2026 | What-if environment, House upsets, history context, state-level error |
| `data/processed/governor_*`, `environment_offcycle.json`, `specials_environment.json` | `governor_model.py`, `environment.py`, `special_model.py` | 1946-2026 | Governor model and backtest, off-cycle environment, special elections |

## Election data pages

`src/site/history.py` builds `site/history/` from the files above: six sections and a Sources and downloads page,
with a CSV of every chart's numbers in `site/history/data/`. 2026 figures are marked provisional until the results are
certified; rerun the script to refresh them.

Gaps that would extend the pages:

- **Senate results history** (every race with incumbency, as for governors), for Senate incumbency and
  Senate-vs-presidential lean. The yearly Senate pages share the governor pages' table format.
- **Presidential state results before 1992** are now in `state_presidential_history.csv` (from The Downballot, 1828 on); the lean and polarization charts can be extended with them, linking to The Downballot's page.
- **House district results before 2006**: older pages lack district PVI, so this needs another source.
- **Special-election polls for 2025-26**, which have to be gathered by hand.
