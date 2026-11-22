# Data

The sources this project collects, the datasets built from them, and how to credit them. The licence for derived
data is in `LICENSE-DATA.md`. The public version of this page is the Election data site's
[Sources and downloads](https://polling2026.vikramrai.com/history/sources.html) page.

## Sources

Raw copies live in `data/raw/<source>/<date>/`, each with a `manifest.json` of URLs and retrieval times.

| Source | What we take | Years | Raw copy | Credit |
|---|---|---|---|---|
| **Wikipedia** (REST and action APIs) | Election overview pages (House 1946-2026, governors 1998-2026, presidential 1992-2024, House specials 2007-2026); statewide and nationwide presidential polling pages (2004-2016); the two lists of national conventions; the presidential primaries pages of 1980-2020 (read for dates, not stored); 2026 race pages and poll tables; aggregator tables | 1946-2026 | `wikipedia/`, `wikipedia_hist/`, `wikipedia_results/` (in git); `wikipedia_results_pages/`, `wikipedia_polls_asof/` (not in git; revision ids kept) | Wikipedia contributors, CC BY-SA 4.0 |
| Cook PVI and expert ratings, via Wikipedia | District and state lean; Cook, Sabato, Inside Elections and other ratings | 2006-2026 | within the Wikipedia pages | Cook Political Report; each rater by name |
| Aggregator averages, via Wikipedia | 2026 generic-ballot and approval averages (DDHQ, RealClearPolitics, Silver Bulletin, NBC, FiftyPlusOne and others) | 2026 | within the Wikipedia pages | Each aggregator by name |
| **FiveThirtyEight data repository** (GitHub) | `raw_polls.csv` (20,466 polls from the final 60 days before an election, with results, 1998-2023; about half are from the final 21 days; including 485 for House specials); pollster ratings; generic-ballot average | 1995-2023 | `538_github/` | FiveThirtyEight (ABC News), CC BY 4.0 |
| **FiveThirtyEight poll files**, via the Internet Archive | Presidential approval (15,181 polls, 2017-2025); generic-ballot, Senate, House and governor polls (2016-2024); presidential general-election and primary polls, full cycles (2020-2024); the 2016 forecast's presidential polls (Nov 2015 to Election Day) | 2016-2025 | `538_wayback/` | FiveThirtyEight (ABC News), via the Internet Archive |
| **The Economist** presidential model ([us-potus-model](https://github.com/TheEconomist/us-potus-model), pinned commit) | State and national presidential polls, compiled from HuffPost Pollster and others (2012 national in the dataset; the rest for cross-checking) | 2008-2016 | `economist_potus/` | The Economist (G. Elliott Morris, Merlin Heidemanns, Andrew Gelman), MIT licence |
| **MIT Election Data and Science Lab** returns | U.S. Senate by state, with a special-election flag ([doi:10.7910/DVN/PEJ5QU](https://doi.org/10.7910/DVN/PEJ5QU)); U.S. House by district, from the lab's [GitHub copy](https://github.com/MEDSL/constituency-returns) at a pinned commit, because the current House file on Dataverse ([doi:10.7910/DVN/IG0UN2](https://doi.org/10.7910/DVN/IG0UN2), to 2024) sits behind a sign-in form. The Senate file gives the backtest its results; the House file is not yet used | Senate 1976-2024; House 1976-2018 | `medsl/` | MIT Election Data and Science Lab. CC0 on Dataverse; the GitHub copy states no licence |
| **David Broockman**, replication data for "Do Congressional Candidates Have Reverse Coattails?" (*Political Analysis*, 2009), [Harvard Dataverse](https://doi.org/10.7910/DVN/DCKUNX) | The Democratic two-party share for president and for the House in every district. No state or district columns: rows must be matched to districts on the House share. Fetched for the work plan; not yet used | 1952-2004 | `broockman_2009/` | David E. Broockman. CC0 |
| **Jennings and Wlezien**, "Election Polling Errors across Time and Space" (2018), [Harvard Dataverse](https://doi.org/10.7910/DVN/8421DX) | Daily average of national presidential polls, United States rows only; 2008 and 2012 from the 2016 version of the same collection ([doi:10.7910/DVN/28856](https://doi.org/10.7910/DVN/28856)) | 1952-2016 | `jennings_wlezien/` (the US extract in git; the 290 MB file is not) | Will Jennings and Christopher Wlezien, CC0 |
| **VoteHub** API | Senate, House, governor, generic-ballot and approval polls (6,108 records in the final snapshot) | 2025-2026 | `votehub/`, `votehub_audit/` | VoteHub |
| **American Presidency Project** (UC Santa Barbara) | Gallup presidential approval, poll by poll | 1941-2021 | `ucsb/` | Gallup, via the American Presidency Project (Gerhard Peters). Not openly licensed: the site shows derived figures only |
| **FRED / ALFRED** (St. Louis Fed) | CPI, gasoline, real disposable income, unemployment, payrolls, GDP growth; vintage series | 1946-2026 | `fred/`, `alfred/` | BLS, BEA and EIA, via FRED (public domain) |
| **FRED state series** | State unemployment and income | 1950-2026 | `fred_state/` | BLS and BEA, via FRED (public domain) |
| **FEC** API | Candidate fundraising totals (no individual contributor data) | 2002-2026 | `fec/` | Federal Election Commission (public domain) |
| **California Secretary of State** API | 2026 House results by district | 2026 | `ca_sos/` | California Secretary of State |
| **State election offices** (GA, IA, LA, MN, MT, NE, SC, TX) | 2026 official Senate and House results | 2026 | `official/`, `official_manual/` | Each state's office |
| **AtlasIntel** poll reports | Toplines of 8 Senate polls missing from VoteHub (`data/supplement/polls_supplement.json`) | 2026 | not in git (checksums kept) | AtlasIntel |
| **U.S. Census Bureau** Data API | State demographics by year: education of adults 25 and over (all, and white non-Hispanic), race and ethnicity, age and median household income. From the 2000 census long form, the American Community Survey's one-year tables, its 2015-19 five-year tables (for a check only), and its 2004 and 2005 microdata. The microdata is tabulated by state as it is read and never stored; only three sets of state totals are kept (by age group, by race and ethnicity, and by degree for adults 25 and over) | 2000, 2004-2025 (no 2020) | `census/` | U.S. Census Bureau (public domain). This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau. Figures for 2004 are this project's own tabulation, not Census Bureau estimates |

University of Michigan consumer sentiment (`UMCSENT`) is in the raw FRED folder but isn't used in any output.

### Linked sources

Some sources are free to use with credit but ask that their tables not be reproduced whole. Their raw copies are not
committed: they live in `data/linked/<source>/<date>/`, which is gitignored, and `data/linked/manifest.json` (committed)
records every fetch with its URL, the source's page, the sheet and tab, the retrieval time and a checksum. Running the
collector rebuilds the store. Only tables derived from them are committed, and the site links to the source's own page
wherever it would otherwise link to a copy of the data.

One linked source was not fetched but sent by its author: Gary Jacobson's House elections file sits in
`data/raw/jacobson/<date received>/`, also gitignored, with his codebook. It has no collector and no manifest entry;
`backtest_asof.json` records the checksum of the copy the backtest read. He gave leave to use the data with credit to
him, not to pass the file on. **Wherever this file is used, the credit is
to Gary Jacobson by name.**

**Backup.** Files kept out of git exist only on the machine that fetched them, and some of their sources are live pages
that can change. `python src/backup_offrepo.py` copies every git-ignored file under `data/` to the folder named by
`backup_dir` in `.env`, with a manifest of checksums. It never deletes from the backup. Run it after fetching a new
off-repo source.

| Source | What we take | Years | Collector | Credit and link |
|---|---|---|---|---|
| **Gary Jacobson**, House elections file (sent by the author, 2026-11-20) | For each district and election: the Democrat's share of the two-party House vote, incumbency, whether the district was redrawn, and the district's two-party presidential vote. Used for the House districts of 1998 to 2004 in the backtest. Also in the file and not yet used: the same for 1946 to 1996, challenger experience, freshman status and campaign spending | 1946-2024 | none (`src/model/backtest_asof.py` reads it) | Gary Jacobson, University of California, San Diego, who compiled the data over 50 years from various sources. Used with his permission; cite him as the source. Not redistributed |
| **Erikson and Wlezien**, poll data for *The Timeline of Presidential Elections* (2012) | The Democrat's two-party poll share by day; used only to check the national poll-day table | 1952-2012 | `src/collect/pres_polls_national_history.py` | Robert S. Erikson and Christopher Wlezien, via [Wlezien's page](https://liberalarts.utexas.edu/government/faculty/cw26629) (link dead; Internet Archive copy). No licence stated |
| **The Downballot** data sheets | Presidential results by state (vote counts for the Democrat and the main opposition). Also fetched and not yet used: the special elections index, open and uncontested House seats, and district education, income, race and urban-rural tables | 1828-2024 (results); 1989-2026 (the rest) | `src/collect/downballot.py` | The Downballot, [the-downballot.com/p/data](https://www.the-downballot.com/p/data). Free to use with a citation and a link; please do not reproduce whole spreadsheets |

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
| `data/interim/state_demographics.csv` | `src/collect/census_demographics.py` | 2000, 2004-2019, 2021-2025 | For the 50 states and DC, one row per year: the share of adults 25 and over with a bachelor's degree; the same among white non-Hispanic adults; white non-Hispanic adults without a degree as a share of all adults 25 and over; white, Black, Asian (each non-Hispanic, one race) and Latino shares of the total population; adults aged 18 to 29 and 65 and over as shares of adults; median household income in that year's dollars (1999's for 2000). 2000 is the census long form; 2004 is our tabulation of the survey's microdata; later years are the survey's published one-year tables; there are none for 2020. To know: the survey left out group quarters (dormitories, prisons, nursing homes) before 2006; 2004 was a smaller trial-stage sample, so its figures are noisier, and one state is clearly off (South Dakota's white share is about 6 points above 2000 and 2005); the race question changed from the 2020 survey year, so 2021 on is not like for like with earlier years. Checks are in `data/checks/state_demographics_check.json`: the 2005 microdata tabulated the same way lands within 0.25 points of the published 2005 tables on average (income within 0.7%), and our 2015-19 figures match The Downballot's state tables built from the same survey (50 states; education, income and Latino share to rounding, white share within 0.7 points and Black share within 0.3) |
| `data/interim/state_demographics_vintages.csv` | `src/collect/census_demographics.py` | 2000-2024 | Which year of `state_demographics.csv` each presidential election uses: the year before it (the latest published before the election) and the election's own year. The same year in both for 2000, 2004 and 2020 |
| `data/interim/president_general_polls.csv` | `src/collect/pres_polls.py` | 2000-2024 | Presidential polls by state, district (ME, NE) and nationally, one row per poll question: eventual nominees' shares and margin. Whole cycles from 2004 (Wikipedia for 2004 states, 2008 and 2012 states; The Economist for 2012 national; FiveThirtyEight for 2016 to 2024); late polls only for 2000 and 2004 national (FiveThirtyEight `raw_polls.csv`). The script's docstring records why each source was chosen |
| `data/interim/president_national_poll_days.csv` | `src/collect/pres_polls_national_history.py` | 1952-2020 | National presidential polls by day: both shares, two-party margin, polls that day, and the result. From Jennings and Wlezien's 2018 file, except 2008 (which that file fills with its 2004 series) and 2012 (a different compilation there), both from their 2016 file. Checked on each run against Erikson and Wlezien's original file for 1952-2012. 2020 is in neither file: it is built from the national polls in `president_general_polls.csv`, one reading per poll and a plain mean by day, and the same build for 2016 is printed against the source's 2016 rows on each run. 2024 is never built |
| `data/interim/convention_dates.csv` | `src/collect/campaign_calendar.py` | 1948-2028 | First and last day of each party's national convention, the election date, and days from the last day to the election. From Wikipedia's two convention lists (revision ids kept) |
| `data/interim/presumptive_nominees.csv` | `src/collect/campaign_calendar.py` | 1980-2020 | For each nominee: the day news delegate counts gave them a majority (the latest where sources differ), the other days found, and, where a rival with a large share of delegates fought on, the day the rival stopped. Entered by hand; each row names its source. 2024 is left out until the holdout is scored |
| `data/interim/president_poll_crosscheck*.csv` | `src/collect/pres_polls_crosscheck.py` | 2004-2020 | The poll sources matched against each other poll by poll: share found, share agreeing, gaps between their averages by state and window, and the matched polls that differ by more than 2 points |
| `data/interim/president_poll_coverage.csv` | `src/collect/pres_polls.py` | 2000-2024 | Polls and pollsters by cycle and state, in the final three weeks and in all, with the result's margin and lean |
| `data/interim/governor_history.csv` | `src/collect/governors.py` | 1998-2025 | Every governor race: incumbent, status, candidates and shares |
| `data/interim/governor_dataset.csv` | `src/collect/governors.py` | 1998-2025 | Governor races with lean, environment, approval, previous margin, poll averages |
| `data/interim/governor_polls_wiki.csv` | `src/collect/governors.py` | 2022-2024 | Governor polls from Wikipedia race pages |
| `data/interim/governor_2026_polls.csv`, `governor_2026_inputs.csv` | `src/model/governor_inputs.py` | 2026 | The 2026 governor polls in the final forecast's snapshot that name both nominees, and one row per race with incumbency, lean and the poll averages the backtest's governor model takes. No results |
| `data/interim/governor_ratings.csv` | `src/model/governor_inputs.py` | 2002-2024 | Final pre-election ratings of each governor race by Cook, Sabato and Rothenberg / Inside Elections, from the yearly Wikipedia overview pages, on a scale from -3 (safe Republican) to +3 (safe Democratic) |
| `data/interim/governor_offyear_env.csv` | `src/model/governor_inputs.py` | 1999-2025 | For each odd-year election day: the generic-ballot average, approval, last House vote and the off-cycle estimator, each from figures known that day |
| `data/interim/house_specials.csv` | `src/collect/specials.py` | 2007-2026 | House specials with district lean on the lines in force |
| `data/interim/generic_ballot_daily.csv` | `src/collect/generic_ballot.py` | 1995-2026 | Generic-ballot polling average by day: FiveThirtyEight's average to 2016, then a plain average of FiveThirtyEight's and VoteHub's polls (latest per pollster, 30 days) |
| `data/final/bias_race_level.csv` | `src/model/bias_analysis.py` | 2002-2022 | Senate and governor races: average of polls from the final 60 days vs result |
| `data/final/calibration.json` | `src/model/calibrate.py` | 1998-2022 | Polling misses by cycle; poll-average error by number of polls |
| `data/final/pollster_effects.json` | `src/model/pollster_effects.py` | 1998-2022 | Pollster house effects and the sponsored-poll shift |
| `data/final/error_structure.json` | `src/model/error_structure.py` | 1998-2022 | Census-region shocks; slope on lean |
| `data/final/state_econ.json`, `money_test.json` | `src/model/state_econ.py`, `money_test.py` | 1998-2022 | Tests of local unemployment and fundraising |
| `data/processed/backtest_asof*` | `src/model/backtest_asof.py` | 2004-2024 | The as-of backtest (BACKTEST.md): Senate, House and governor forecasts made with parameters fitted on earlier cycles, the parameters by cycle, and the scores. `backtest_asof_<candidate>_vs_baseline.json` is each tested change against the baseline. The governor lean candidates read Senate results from the MIT Election Lab file (`data/raw/medsl/`). The demographic-similarity candidate reads The Downballot's state tables from the gitignored `data/linked/` store (Linked sources); nothing from them is committed. House districts for 1998 to 2004 come from Gary Jacobson's file (Linked sources); the 2004 district forecasts are kept beside that file, not here |
| `data/final/*` (the rest) | the frozen forecast | 2026 | Forecast inputs and outputs; never rewritten |
| `data/scorecard/*` | `src/run_scorecard.py` | 2026 | Results, margins, poll audit |
| `data/postmortem/*` | `src/postmortem/*.py` | 1946-2026 | What-if environment, House upsets, history context, state-level error |
| `data/processed/governor_*`, `environment_offcycle.json`, `specials_environment.json` | `governor_model.py`, `governor_inputs.py`, `environment.py`, `special_model.py` | 1946-2026 | Governor model and backtest, off-cycle environment, special elections |

## Election data pages

`src/site/history.py` builds `site/history/` from the files above: six sections and a Sources and downloads page,
with a CSV of every chart's numbers in `site/history/data/`. 2026 figures are marked provisional until the results are
certified; rerun the script to refresh them.

Gaps that would extend the pages:

- **Senate results history** (every race with incumbency, as for governors), for Senate incumbency and
  Senate-vs-presidential lean. The MIT Election Lab's Senate returns (1976-2024, specials flagged) are now in `data/raw/medsl/`; they carry no incumbency, which the yearly Senate pages (the governor pages' table format) would add.
- **Presidential state results before 1992** are now in `state_presidential_history.csv` (from The Downballot, 1828 on); the lean and polarization charts can be extended with them, linking to The Downballot's page.
- **House district results before 2006**: the MIT Election Lab's House returns (1976-2018) are now in `data/raw/medsl/`. District lean and results by labelled district are in Gary Jacobson's file for 1946-2024 (Linked sources; not in the repo). The Broockman file in `data/raw/broockman_2009/` has the presidential vote by district for 1952-2004 but no district labels.
- **Special-election polls for 2025-26**, which have to be gathered by hand.
