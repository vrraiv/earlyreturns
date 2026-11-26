# Special elections: design note

The note for the specials track (work plan cards SP-1 to SP-8 in `planning/plan.js`). Started 2026-11-25 with SP-3.
SP-1 and SP-2 (House specials and the single-race path, November 2026) are written up in `PLAN.md`, section 5.
Rules are written here before anything they govern is run, agreed with the project owner, and every run is reported.

## 1. Senate special elections (SP-3)

### What the card's source turned out to be

The card named The Downballot's Special Elections Index (1989-2022) as the source. The fetched workbook
(`data/linked/downballot/`, store-and-link) holds 84 U.S. House and about 690 state legislative specials and no U.S.
Senate races. Each row gives the special's margin and its difference from the district's earlier House or
legislative margins; there is no presidential vote. It cannot give the Senate history. It is used below only for a
recent-specials signal before 2008 (rule 6). The MIT Election Lab's Senate file flags specials, but almost all of its
specials are on a general-election day; off-cycle ones are missing except Georgia's January 2021 runoff.

The Senate races come from Wikipedia's "List of special elections to the United States Senate" (cached in
`data/raw/wikipedia_hist/`, revision 1387305102) and each race's own page for the date and the result.

### Rules (written and agreed 2026-11-25, before any Senate special was compared with a forecast)

Decisions the owner made on 2026-11-25: specials only; report only, no pass mark; a recent-specials signal back to
1989 from The Downballot's index; the state's lean from the last federal election before the special, presidential
or midterm, with the midterm measured by the statewide House vote.

**Which races**

1. **Universe.** U.S. Senate special elections (filling a vacancy) from 1970 on whose deciding round was not held on a
   regular November general-election day, with a Democrat and a Republican in the deciding round. The date is the
   deciding round's, checked on the race's own page (the list's date column is sometimes the swearing-in date).
2. **Margin.** All Democrats' share against all Republicans' in the deciding round, two-party, as for House specials
   (`src/collect/specials.py`).
3. **Expected set** (from the list's 47 rows from 1970 on, every date parsed; to be confirmed race by race): VT 1972,
   NH 1975, WA 1983, PA 1991, ND 1992, TX 1993 (runoff), OR 1996, MA 2010, MA 2013, NJ 2013, AL 2017, MS 2018 (runoff),
   GA 2021 (runoff). NC 1986 shows an off-day date in the list but is expected to drop: its election was on the 1986
   general-election day. NH 1975 was a rerun ordered after the 1974 result could not be settled; it stays in and is
   flagged. Any race the rule adds or drops on checking is reported.
4. **Diagnostic set, not scored into anything.** Runoffs for a regular (not special) Senate seat whose deciding round
   fell after the November general-election day, from 1970 on, Democrat against Republican, from the yearly Senate
   pages. Expected, from memory and to be confirmed: GA 1992, LA 2002, GA 2008, LA 2014, GA 2021 (Ossoff), GA 2022.
   Reported in their own table.

**The prior**

5. **The frozen Senate prior's form** (`src/model/forecast.py`): margin = lean + environment + 2 x incumbency, with no
   fitted coefficients. The frozen forecast's lean is 2 x Cook PVI (a margin, so coefficient 1); the lean here is the
   owner's measure below, also a margin at coefficient 1.
   - **Lean**: the state's two-party lean in the last federal general election before the special. After a
     presidential election: the state's presidential margin minus the nation's
     (`data/interim/state_presidential_history.csv`). After a midterm: the margin of all the state's House votes
     (Democrats against Republicans) minus the national House margin (`data/interim/house_national_vote.csv`),
     from the MIT House file (1976 on). 1970 and 1974 need another source, to be found and reported; uncontested
     seats are left as recorded, and the number of seats and how many were uncontested are reported beside each
     midterm lean. In small states this lean is one or two candidates' margins: Vermont's 1970 at-large House race,
     the lean for VT 1972, was won by Robert Stafford, the special's own Republican.
   - **Incumbency**: +1 if a sitting U.S. senator from the state runs as a Democrat, -1 as a Republican, 0 otherwise.
     That covers appointees, as the 2026 forecast treated Florida's and Ohio's, and ND 1992, where Kent Conrad held
     the state's other seat (the appointee, Jocelyn Burdick, did not run). In the runoff set the incumbent is elected
     and coded the same way.
   - The state-economy term is off. No polls (SP-4).

**Environments compared** (on the special's date, from `src/model/environment.py`)

6. All four are reported; none is chosen here.
   - **N**: the last national House vote carried forward (SP-2's baseline).
   - **F1**: the fundamentals estimate at m = 1 (midterm-like).
   - **H**: m by half of the presidential term, the House specials' pattern. From 2008, m is fitted on House specials
     before the date, as `single_race.py` does. Before 2008 there are none, so m is fitted on all 77 House specials
     (2007-2026): declared as out of time order for those races. From 2008, where a half of the term has fewer than 8
     earlier House specials, m = 1, as `single_race.py` does (probably MA 2010).
   - **H+R**: H plus a recent-specials term.
     - From 2008: the existing House term (House specials in the prior 12 months, shrunk n / (n + 2)).
     - 1989 to 2007: an index term from The Downballot's index (House and legislative specials, as Daily Kos
       Elections selected them). For each index special in the 12 months before the Senate special: swing = its
       margin minus the district's margin in the most recent earlier regular election shown; expected = the H
       estimate on the special's date minus the national House margin in that earlier year; residual = swing minus
       expected. The term is the mean residual shrunk n / (n + 2), with lean moving one for one with the environment
       (the Senate prior's coefficient, not the House model's 0.78).
     - Before 1989: no term (H+R equals H for VT 1972, NH 1975 and WA 1983).
     - So the index term changes four races: PA 1991, ND 1992, TX 1993, OR 1996. With dozens of index races a year
       the n / (n + 2) shrink does almost nothing; k = 2 is kept from the House term, not tuned.
     - Only the derived term by date is committed (OP-8); no table of index races.
   - **Fitted on later years.** The fundamentals estimator behind F1, H and H+R (`E.fit(E.training())`) is fitted on
     every election 1946-2022, so for every race it uses later elections, as SP-2's backtest did. N uses nothing
     after the date.
   - `special_model.term_year` counts terms from 2005; it is extended back to 1969 for this card (Ford counted in
     Nixon's second term), leaving every existing date unchanged. The House backtest (`single_race.py backtest`) is
     rerun to confirm it still gives 68 specials and margin RMSE 11.5.

**Additions agreed 2026-11-26, after step 2 and before step 3** (written and agreed before anything below was run;
the owner confirmed LB's midterm term is the state's House margin minus the national House margin)

G was proposed before any Senate forecast was computed and uses no Senate result. LP and LB were proposed after the
step 1 table, which shows each race's margin beside its L1 lean, had been seen; they are declared as added after that
table, though before any forecast or error was computed.

6a. **A fifth environment, G: the generic ballot averaged over the prior six months.**
   - **From 2017 on, over polls**: each generic-ballot poll (`src/collect/generic_ballot.py`'s FiveThirtyEight file to
     2024-11-05, VoteHub after) ending in the 182 days before the date (the day itself excluded), two-party margin,
     weight 0.5^(age in days / half-life). One poll counts as one poll, so a lone late poll (GA 2021: one poll, R+2.1,
     the day before) moves G only as much as its weight against the rest.
   - **Before 2017, over FiveThirtyEight's daily average** (raw polls before 2016 are not in the repo): the same
     weights on each day's value. That series is already smoothed, so short half-lives mean less there; declared.
   - **The half-life is fitted on House specials, not Senate ones.** Grid: 7, 14, 30, 60, 90 and 182 days, and a flat
     six-month mean. Each is scored by margin RMSE in `single_race.py backtest` (same 68 specials, same lean,
     incumbency and coefficients) with G replacing the whole House environment (no recent-specials term), at the House
     prior's environment coefficient. **Default: the flat six-month mean, unless a half-life beats it by at least 0.3
     points of RMSE**; then the best one. One value, fitted on all House specials 2007-2026, so it is out of time order
     for every Senate race it scores. The grid and its RMSEs are reported before the Senate run (step 2b).
   - In the Senate prior G enters raw, as a margin at coefficient 1, with no recent-specials term and no midterm
     adjustment.
   - Scored only where the series covers the full six months: MA 2010, MA 2013, NJ 2013, AL 2017, MS 2018, GA 2021
     (6 specials; OR 1996 has 2.5 months and is left out, as is every race before it). Runoff set: LA 2002, GA 2008,
     LA 2014, LA 2016, GA 2021, GA 2022.
   - Known beforehand: in odd-year governor races (`data/processed/governor_offyear_env.json`) the generic ballot on
     the day ran about 4.5 points too Democratic across 31 races, with RMSE close to the last House vote's.

6b. **Three leans, compared.** Rule 5's lean is one of three, each a margin at coefficient 1, relative to the nation:
   - **L1 (rule 5, as written)**: the last federal general election before the special, presidential or midterm.
   - **LP**: the state's presidential margin minus the nation's in the last presidential election before the special.
   - **LB**: the mean of LP and the state's House-vote lean (rule 5's midterm measure: the state's House margin minus
     the national House margin) in the last midterm before the special.
   - L1 equals LP wherever the last federal election was presidential: 7 of the 13 specials (ND 1992, TX 1993,
     MA 2010, MA 2013, NJ 2013, AL 2017, GA 2021). L1 against LP rests on the other 6 (VT 1972, NH 1975, WA 1983,
     PA 1991, OR 1996, MS 2018); in G's subset only MS 2018 differs.
   - LB still carries thin midterm leans at half weight (VT 1972's is Stafford's own one-seat race).
   - No lean is fitted or chosen here.

**What is reported**

7. **Before any Senate result is used**: the race table (date, deciding round, margin, lean and its source,
   incumbency) for the owner to check; and, on 2008-2022 dates, the index term against the House term (correlation,
   mean difference), which shows whether the index term measures the same thing. Neither touches a Senate forecast.
   The index term is used as written whatever that comparison shows.
8. **Then one run**, each environment through the same prior:
   - margin MAE, RMSE and mean error (positive = Democrats beat the forecast), winners right;
   - on all races, on 1989 on (where H+R differs from H) and on 2008 on;
   - the race-by-race table: each environment's forecast and error, and the environment each result implies;
   - coverage of 50, 80 and 95% intervals, normal (SP-2's choice) and t(3.9) (the forecast's race error,
     `data/processed/poll_settings.json`). SD = sqrt(9.67^2 + 4.56^2) = 10.7: the frozen Senate prior's error for
     races without polls (`data/final/prior_weight.json`, `prior_sd_robust`, 9.67), which is measured within cycle and
     so leaves out the environment's error, plus the off-cycle environment SD (`environment_offcycle.json`,
     `sd_env_offcycle`, 4.56), as the governor path combines them. The same SD for all four environments. Borrowed,
     not estimated: too few races to estimate one.
   - the diagnostic runoff set (rule 4) through the same four, in its own table.
   - **With 6a and 6b**: the summary (MAE, RMSE, mean error, winners) for all 15 cells, 3 leans x 5
     environments, on all 13, 1989 on, 2008 on, and G's 6 (G's row on G's 6 only). L1 stays the headline lean, as
     rule 5 was agreed first. The race-by-race table and coverage are given for the L1 row (all five environments) and
     for each lean under H; the runoff table for all 15 cells.
9. **No decision at this card.** What the Senate branch of the single-race path uses (checklist c) is the owner's
   call after the report. A diagnostic never rescues anything, and any candidate suggested by these results is
   declared as such wherever it is used later.

**Live case.** The list carries a Minnesota special scheduled for November 2, 2027 (Amy Klobuchar's seat). That is
on an odd-year November date, so it is in scope for the path this card builds.

### Step 1 report: the race table (2026-11-25)

`src/collect/senate_specials.py` -> `data/interim/senate_specials.csv`. The rule keeps exactly the 13 expected
specials. NC 1986 drops (decided on the 1986 general-election day); Hawaii 1990's infobox date is a typo for the 1990
general-election day; NH 1975's infobox shows the 1974 date, so it was checked by hand. The runoff set is 7, not the 6
expected: Louisiana 2016 (December 10) was missing from the list written from memory, and turned up in the scan of
every Georgia and Louisiana Senate page. Midterm leans that rest on few seats or on percentages: VT 1972 (one seat,
Stafford's own race, R+49), NH 1975 (two seats, equal weight), GA 2022 (runoff set; equal weight, no 2022 vote
counts); Pennsylvania's 1990 House vote has 6 of 23 seats uncontested. The owner checked the table before step 2.

### Step 2 report: the index term against the House term (2026-11-26, no Senate result used)

`python src/model/senate_specials.py index` -> `data/processed/senate_specials_index_term.csv` (term by month, the
only derived table) and `senate_specials_index_check.json`.

- 666 index specials with an earlier regular result, 1989-2022, of which 79 U.S. House. m by half of the term on all
  77 House specials: 1.28 (years 1-2), -0.19 (years 3-4). Residuals: mean -1.8, SD 22.4.
- **2008-2022, 173 months with both terms: correlation 0.20.** Means +0.2 (index) and -1.5 (House); SDs 5.9 and 5.4.
  By year they part most in 2009 (index -5.9, House +3.8), 2012, 2015-16 and 2020-21 (2021: +11.6 against -0.6).
- **Diagnostic, not pre-registered:** split by race type, the index's 79 U.S. House rows track the House term
  (correlation 0.64 over 166 months), its legislative rows do not (0.06 over 173). So the index's measure (swing from
  the district's last result) agrees with the House term on House races; what differs is legislative specials.
- **On the four Senate dates it changes**: PA 1991 -1.8 (11 index specials in the prior 12 months), ND 1992 +3.1 (8),
  TX 1993 -8.7 (6), OR 1996 +7.5 (15). Runoff set: GA 1992 +3.1 (8), LA 2002 -13.6 (22).
- Under rule 7 the index term is used in step 3 as written (House and legislative rows).
- Housekeeping: `special_model.term_year` now runs from 1969; the House backtest is unchanged (68 specials, RMSE
  11.51, output identical); `check_frozen.py` passes.

### Step 2b report: G's half-life on House specials (2026-11-26, no Senate result used)

`python src/model/senate_specials.py halflife` -> `data/processed/senate_specials_halflife.json`. The 68 House
specials of `single_race.py backtest`, G replacing the whole House environment at the House prior's coefficient.

| Half-life (days) | 7 | 14 | 30 | 60 | 90 | 182 | flat |
|---|---|---|---|---|---|---|---|
| Margin RMSE | 12.56 | 12.64 | 12.73 | 12.77 | 12.79 | 12.80 | 12.81 |
| MAE | 10.36 | 10.46 | 10.59 | 10.67 | 10.70 | 10.73 | 10.75 |

- The shortest half-life does best, but by 0.25 points, under the 0.3 the rule asks for: **G is the flat six-month
  mean.**
- For reference on the same 68: the House path as built (H plus the recent-specials term, fitted in date order) RMSE
  11.51; the last House vote 13.75. G sits between them.
- Five House specials had less than the full six months of polls behind them (the poll file starts in late 2016, and
  one 2021 date): KS-4, MT-AL, SC-5 and GA-6 in 2017 (121 to 158 days), NM-1 in 2021 (170). Of G's Senate races, the
  six specials have the full six months. Correction (added with step 3): in the runoff set, LA 2016 (December 10,
  2016) falls before 2017 and so uses FiveThirtyEight's daily average, which ends on November 6, 2016: its last 34
  days are missing. Kept as the rule computes it, not recomputed.

### Step 3 report: the scoring run (2026-11-26, run once)

`python src/model/senate_specials.py score` -> `data/processed/senate_specials_scores.json` (summaries, runoffs,
coverage) and `data/processed/senate_specials_races.csv` (every race, lean, environment, forecast and error). Margin =
lean + environment + 2 x incumbency; positive error = Democrats beat the forecast. The run's outputs were written
before a final print of the race table failed on a column name; the print was fixed and the tables below are read from
the saved files. The scoring was not rerun.

**What it shows**

- **Single races swamp the differences between cells.** ND 1992 (Kent Conrad, the state's sitting senator, against a
  lean of R+23 from the 1992 presidential vote) misses by 38 to 49 under every L1 and LP cell; alone it is 110 to 180
  of the 320 to 430 of mean squared error (L1 F1, L1 H, LP H). AL 2017 (Moore), MA 2010 (Brown), TX 1993 and NH 1975
  miss by more than 20 under most cells. These are candidate effects no lean or environment here carries. With 13
  races, 6 from 2008, a point or two between cells is noise.
- **The borrowed SD is far too narrow.** Errors' RMSE is 18 to 24 on all 13 against the 10.7 assumed; 95% intervals
  hold 8 to 10 of 13.
- **Environments.** Under L1, F1 (midterm-like on every date) has the lowest RMSE on all 13 (17.9) and on 1989 on;
  from 2008 F1, H and H+R are level (14.1 to 14.7). H and H+R trail F1 before 2008, where their m is fitted out of
  time order. N is the worst environment under every lean and cut. The index term moves H+R by -8.7 to +7.5 on the
  four 1989-2007 races: it helps TX 1993 (error -20.1 to -11.4) and hurts OR 1996 (-16.7 to -24.3).
- **G** is behind F1, H and H+R on its 6 races under every lean (L1: 16.3 against 14.1 to 14.7), and too Democratic
  on average (-3.1 to -7.3), as the generic ballot was in odd-year governor races.
- **Leans.** L1 and LP differ on 6 specials. L1 is closer on VT 1972 (under every environment; the 1970 House race
  was Stafford's own) and, narrowly, on WA 1983; LP is closer on NH 1975 (every environment), OR 1996 (all but F1)
  and MS 2018 (all but N); PA 1991 is within a point either way. Overall LP is level with L1 or slightly ahead under
  H and H+R, behind under F1. **LB is worst**, most of all from 2008 (23.6 to 29.3 against 13.7 to 20.6). Observed
  after the run: the midterm House votes behind it include uncontested seats, and Massachusetts 2006 (7 of 10 seats
  uncontested) gives a midterm lean of D+70, so MA 2010 misses by 51 under LB and H. A version using contested seats
  only would be a candidate suggested by these results.
- **Runoffs** (diagnostic): every cell's mean error is positive (Democrats beat the forecast by 0.5 to 13.5). LP with
  G has the lowest RMSE (7.0, on 6; LA 2016's G is missing its last 34 days, see step 2b). Louisiana 2002 and 2014
  carry the largest misses under L1, whose midterm leans there come from 7 and 6 House seats with 4 and 3 uncontested.

**Specials: margin RMSE / MAE / mean error / winners right**

| Lean | Env | All 13 | 1989 on (10) | 2008 on (6) = G's 6 |
|---|---|---|---|---|
| L1 | N | 22.5 / 18.0 / +0.6 / 7 | 23.9 / 18.5 / -1.0 / 6 | 20.5 / 15.2 / -1.3 / 3 |
| L1 | F1 | 17.9 / 14.0 / -0.1 / 8 | 18.2 / 13.7 / -0.6 / 7 | 14.7 / 10.5 / -1.2 / 4 |
| L1 | H | 20.7 / 16.4 / +3.5 / 7 | 20.7 / 15.6 / +0.8 / 5 | 14.3 / 11.2 / -1.1 / 2 |
| L1 | H+R | 20.2 / 16.4 / +2.8 / 7 | 20.0 / 15.6 / -0.1 / 5 | 14.1 / 11.7 / -2.6 / 2 |
| L1 | G |  |  | 16.3 / 12.9 / -3.7 / 4 |
| LP | N | 22.8 / 17.4 / -3.0 / 7 | 23.7 / 17.9 / +0.8 / 5 | 20.6 / 15.8 / -0.7 / 3 |
| LP | F1 | 19.7 / 15.1 / -3.8 / 7 | 18.2 / 13.5 / +1.2 / 6 | 14.6 / 10.0 / -0.6 / 4 |
| LP | H | 19.0 / 14.0 / -0.2 / 8 | 19.9 / 13.9 / +2.6 / 6 | 14.0 / 10.6 / -0.6 / 3 |
| LP | H+R | 18.0 / 14.0 / -0.9 / 7 | 18.6 / 14.0 / +1.7 / 5 | 13.7 / 11.1 / -2.1 / 2 |
| LP | G |  |  | 16.4 / 13.5 / -3.1 / 4 |
| LB | N | 24.1 / 17.8 / -5.2 / 7 | 26.5 / 19.4 / -5.2 / 6 | 29.3 / 20.8 / -4.9 / 3 |
| LB | F1 | 20.0 / 14.8 / -5.9 / 9 | 21.1 / 14.9 / -4.9 / 7 | 23.6 / 16.1 / -4.8 / 3 |
| LB | H | 20.2 / 15.7 / -2.3 / 9 | 21.9 / 17.1 / -3.4 / 7 | 23.6 / 17.5 / -4.7 / 3 |
| LB | H+R | 19.6 / 15.7 / -3.0 / 8 | 21.3 / 17.1 / -4.3 / 6 | 23.7 / 18.0 / -6.2 / 2 |
| LB | G |  |  | 25.2 / 18.4 / -7.3 / 3 |

The 2008-on cut and G's 6 are the same six races (MA 2010, MA 2013, NJ 2013, AL 2017, MS 2018, GA 2021).

**Race by race (specials): forecast, error in brackets; implied environment under L1 (actual - L1 - 2 x inc)**

| Race | Actual | Inc | L1 N | L1 F1 | L1 H | L1 H+R | L1 G | LP H | LB H | Implied (L1) |
|---|---|---|---|---|---|---|---|---|---|---|
| VT1972 | -31.6 | -1 | -42.1 (+10.5) | -37.1 (+5.5) | -48.2 (+16.6) | -48.2 (+16.6) |  | -8.0 (-23.6) | -28.1 (-3.5) | +19.3 |
| NH1975 | +10.9 | +0 | -12.1 (+23.0) | -8.4 (+19.4) | -19.5 (+30.5) | -19.5 (+30.5) |  | +3.8 (+7.2) | -7.9 (+18.8) | +40.1 |
| WA1983 | -10.8 | -1 | +4.6 (-15.5) | +10.1 (-20.9) | -1.1 (-9.8) | -1.1 (-9.8) |  | +0.7 (-11.5) | -0.2 (-10.6) | -3.5 |
| PA1991 | +10.0 | +1 | +16.1 (-6.1) | +17.9 (-7.9) | +6.8 (+3.2) | +5.0 (+5.0) |  | +6.3 (+3.8) | +6.5 (+3.5) | +2.0 |
| ND1992 | +30.3 | +1 | -15.4 (+45.7) | -7.2 (+37.6) | -18.4 (+48.7) | -15.2 (+45.6) |  | -18.4 (+48.7) | +4.1 (+26.2) | +51.0 |
| TX1993 | -34.7 | +1 | -4.1 (-30.5) | -11.9 (-22.8) | -14.6 (-20.1) | -23.3 (-11.4) |  | -14.6 (-20.1) | -8.8 (-25.8) | -25.3 |
| OR1996 | +1.6 | +0 | +12.9 (-11.3) | +7.2 (-5.6) | +18.4 (-16.7) | +25.9 (-24.3) |  | +4.7 (-3.1) | +11.5 (-9.9) | -18.4 |
| MA2010 | -4.8 | +0 | +30.0 (-34.9) | +21.1 (-25.9) | +21.1 (-25.9) | +21.4 (-26.2) | +22.4 (-27.2) | +21.1 (-25.9) | +46.6 (-51.4) | -23.8 |
| MA2013 | +10.3 | +0 | +20.8 (-10.5) | +13.4 (-3.1) | +13.1 (-2.9) | +15.3 (-5.0) | +25.1 (-14.8) | +13.1 (-2.9) | +19.1 (-8.9) | -9.4 |
| NJ2013 | +11.0 | +0 | +15.2 (-4.2) | +7.1 (+3.9) | +6.9 (+4.1) | +9.1 (+2.0) | +18.8 (-7.8) | +6.9 (+4.1) | +2.6 (+8.4) | -3.0 |
| AL2017 | +1.6 | +0 | -32.0 (+33.7) | -22.4 (+24.0) | -19.1 (+20.8) | -14.5 (+16.1) | -21.8 (+23.5) | -19.1 (+20.8) | -18.7 (+20.3) | +32.6 |
| MS2018 | -7.3 | -1 | -10.3 (+3.0) | -3.5 (-3.8) | +0.9 (-8.1) | +4.3 (-11.6) | -10.7 (+3.4) | -2.5 (-4.8) | -0.8 (-6.5) | +11.8 |
| GA2021S | +2.1 | -1 | -3.1 (+5.2) | +4.4 (-2.3) | -3.2 (+5.2) | -7.0 (+9.0) | +1.2 (+0.9) | -3.2 (+5.2) | -7.7 (+9.8) | +8.4 |

**Leans and the inputs behind them** (midterm House vote: seats, of which uncontested)

| Race | L1 | LP (year) | Midterm lean (year; seats, uncontested) | LB | N | F1 | H | H+R (R term, n) | G |
|---|---|---|---|---|---|---|---|---|---|
| VT1972 | -49.0 | -8.8 (1968) | -49.0 (1970; 1, 0) | -28.9 | +8.8 | +13.9 | +2.8 | +2.8 (+0.0, 0) |  |
| NH1975 | -29.2 | -5.9 (1972) | -29.2 (1974; 2, 0) | -17.6 | +17.1 | +20.8 | +9.7 | +9.7 (+0.0, 0) |  |
| WA1983 | -5.3 | -3.6 (1980) | -5.3 (1982; 8, 0) | -4.5 | +12.0 | +17.4 | +6.3 | +6.3 (+0.0, 0) |  |
| PA1991 | +6.0 | +5.5 (1988) | +6.0 (1990; 23, 6) | +5.7 | +8.1 | +9.9 | -1.2 | -3.0 (-1.8, 11) |  |
| ND1992 | -22.7 | -22.7 (1992) | +22.3 (1990; 1, 0) | -0.2 | +5.2 | +13.4 | +2.3 | +5.4 (+3.1, 8) |  |
| TX1993 | -11.4 | -11.4 (1992) | +0.0 (1990; 27, 13) | -5.7 | +5.2 | -2.5 | -5.2 | -13.9 (-8.7, 6) |  |
| OR1996 | +20.0 | +6.4 (1992) | +20.0 (1994; 5, 0) | +13.2 | -7.1 | -12.8 | -1.6 | +5.9 (+7.5, 15) |  |
| MA2010 | +19.0 | +19.0 (2008) | +70.0 (2006; 10, 7) | +44.5 | +11.0 | +2.0 | +2.0 | +2.4 (+0.3, 4) | +3.4 |
| MA2013 | +19.6 | +19.6 (2012) | +31.6 (2010; 10, 1) | +25.6 | +1.1 | -6.3 | -6.5 | -4.3 (+2.2, 3) | +5.4 |
| NJ2013 | +14.0 | +14.0 (2012) | +5.6 (2010; 13, 0) | +9.8 | +1.1 | -6.9 | -7.2 | -5.0 (+2.2, 3) | +4.8 |
| AL2017 | -31.0 | -31.0 (2016) | -30.1 (2014; 7, 3) | -30.5 | -1.1 | +8.6 | +11.9 | +16.5 (+4.7, 5) | +9.2 |
| MS2018 | -17.1 | -20.4 (2016) | -17.1 (2018; 4, 1) | -18.7 | +8.8 | +15.6 | +19.9 | +23.4 (+3.5, 4) | +8.4 |
| GA2021S | -4.3 | -4.3 (2020) | -13.3 (2018; 14, 2) | -8.8 | +3.2 | +10.7 | +3.1 | -0.7 (-3.8, 4) | +7.5 |
| GA1992 | -6.2 | -6.2 (1992) | +14.6 (1990; 10, 0) | +4.2 | +5.2 | +13.7 | +2.5 | +5.6 (+3.1, 8) |  |
| LA2002 | -27.4 | -8.4 (2000) | -27.4 (2002; 7, 4) | -17.9 | -5.0 | -0.1 | +2.5 | -11.1 (-13.6, 22) | +1.6 |
| GA2008 | -12.6 | -12.6 (2008) | -18.2 (2006; 13, 1) | -15.4 | +11.0 | +19.8 | +7.9 | +10.6 (+2.6, 9) | +11.7 |
| LA2014 | -37.6 | -21.4 (2012) | -37.6 (2014; 6, 3) | -29.5 | -5.9 | -13.2 | -14.1 | -15.3 (-1.2, 4) | +0.3 |
| LA2016 | -22.6 | -22.6 (2016) | -37.6 (2014; 6, 3) | -30.1 | -1.1 | -7.1 | -1.8 | -12.7 (-10.9, 1) | +5.4 |
| GA2021R | -4.3 | -4.3 (2020) | -13.3 (2018; 14, 2) | -8.8 | +3.2 | +10.7 | +3.1 | -0.7 (-3.8, 4) | +7.5 |
| GA2022 | -0.8 | -4.3 (2020) | -0.8 (2022; 14, 0) | -2.5 | -2.8 | -10.8 | -11.9 | -5.6 (+6.4, 8) | +1.8 |

GA 2022's midterm lean is from district margins at equal weight (no 2022 vote counts); 1970 and 1974 from district percentages.

**Coverage** (specials inside the interval; SD 10.7; normal / t(3.9))

| Lean | Env | n | 50% | 80% | 95% |
|---|---|---|---|---|---|
| L1 | N | 13 | 4 / 3 | 7 / 7 | 8 / 8 |
| L1 | F1 | 13 | 6 / 5 | 7 / 7 | 9 / 9 |
| L1 | H | 13 | 4 / 4 | 6 / 6 | 10 / 10 |
| L1 | H+R | 13 | 3 / 3 | 7 / 6 | 9 / 9 |
| L1 | G | 6 | 2 / 2 | 3 / 3 | 4 / 4 |
| LP | H | 13 | 7 / 6 | 8 / 7 | 10 / 10 |
| LB | H | 13 | 3 / 2 | 8 / 8 | 10 / 10 |

**Runoff set (diagnostic, not scored into anything): RMSE / MAE / mean error / winners right**

| Lean | N | F1 | H | H+R | G |
|---|---|---|---|---|---|
| L1 | 17.7 / 12.6 / +8.7 / 3 of 7 | 20.5 / 17.2 / +7.5 / 3 of 7 | 18.5 / 13.4 / +11.0 / 4 of 7 | 22.5 / 17.4 / +13.5 / 3 of 7 | 15.5 / 11.2 / +5.7 / 5 of 6 |
| LP | 9.4 / 8.1 / +4.2 / 3 of 7 | 14.0 / 12.7 / +3.0 / 3 of 7 | 11.4 / 8.9 / +6.5 / 4 of 7 | 14.4 / 12.9 / +9.0 / 3 of 7 | 7.0 / 5.8 / +0.5 / 4 of 6 |
| LB | 14.6 / 13.1 / +7.1 / 3 of 7 | 18.5 / 16.8 / +5.9 / 2 of 7 | 15.7 / 13.8 / +9.4 / 3 of 7 | 20.1 / 17.9 / +11.9 / 3 of 7 | 10.5 / 8.6 / +5.6 / 4 of 6 |

| Runoff | Actual | Inc | L1 N | L1 F1 | L1 H | L1 H+R | L1 G | LP G |
|---|---|---|---|---|---|---|---|---|
| GA1992 | -1.3 | +1 | -2.3 | -10.7 | +0.4 | -2.7 |  |  |
| LA2002 | +3.4 | +1 | +33.8 | +28.9 | +26.2 | +39.8 | +27.2 | +8.2 |
| GA2008 | -14.9 | -1 | -11.3 | -20.0 | -8.2 | -10.8 | -11.9 | -11.9 |
| LA2014 | -11.9 | +1 | +29.6 | +36.9 | +37.8 | +39.0 | +23.4 | +7.2 |
| LA2016 | -21.3 | +0 | +2.3 | +8.4 | +3.1 | +13.9 | -4.1 | -4.1 |
| GA2021R | +1.2 | -1 | +4.3 | -3.2 | +4.4 | +8.2 | +0.0 | +0.0 |
| GA2022 | +2.8 | +1 | +4.3 | +12.3 | +13.5 | +7.1 | -0.3 | +3.3 |

(Runoff table: errors.)

**No decision** (rule 9). What the Senate branch of the single-race path uses (checklist c) is the owner's call.

### Decision (2026-11-26, after the step 3 report)

- **The owner's decision: F1, with an error SD of 18.** The Senate branch of the single-race path is margin = lean +
  F1 + 2 x incumbency (`python src/model/single_race.py senate --state GA --date 2021-01-05 --inc -1`; checklist c).
- **SD 18** replaces the borrowed 10.7. It is the one change from what was tested, suggested by the step 3 results
  (F1 with L1: margin RMSE 17.9 on the 13 specials). Checked on the same 13, so not a test: 50% / 80% / 95% normal
  intervals hold 7 / 10 / 12. ND 1992 alone pulls the SD up a good deal.
- **Defaults pending the owner's confirmation**: lean L1 (rule 5's headline lean, and F1's best lean in step 3) and a
  normal error shape (SP-2's choice for House specials; t(3.9) covered the same in step 3).
- Not used: H, H+R, N and G as the environment. A contested-seats-only midterm lean was not run.
- The Minnesota special on November 2, 2027 cannot be forecast until the 2026 national and state House votes are in
  the repo: the command refuses rather than use the 2024 House vote in the environment, and asks for `--lean` when
  the lean's election is missing. `src/collect/senate_specials.py`'s lean lookup now runs to the date's year (it
  stopped at 2024); rerun, the race table is unchanged.
