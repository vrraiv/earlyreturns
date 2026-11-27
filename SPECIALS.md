# Special elections: design note

The note for the specials track (work plan cards SP-1 to SP-8 in `planning/plan.js`). Started 2026-11-25 with SP-3; section 2 is SP-4, section 3 SP-5, section 4 SP-8, section 5 SP-7.
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
  (F1 with L1: margin RMSE 17.9 on the 13 specials). ND 1992 alone pulls the SD up a good deal.
- **Lean L1 and error shape t(3.9)**, both confirmed by the owner the same day (the shape is the forecast's race error,
  `poll_settings.json`). Checked on the same 13, so not a test: at SD 18, 50% / 80% / 95% intervals hold 7 / 7 / 12
  under t(3.9) (7 / 10 / 12 under a normal); the t's narrower middle leaves out three races near the 80% edge.
- Not used: H, H+R, N and G as the environment. A contested-seats-only midterm lean was not run.
- The Minnesota special on November 2, 2027 cannot be forecast until the 2026 national and state House votes are in
  the repo: the command refuses rather than use the 2024 House vote in the environment, and asks for `--lean` when
  the lean's election is missing. `src/collect/senate_specials.py`'s lean lookup now runs to the date's year (it
  stopped at 2024); rerun, the race table is unchanged.

## 2. Polls of past specials (SP-4)

The single-race path takes polls for a House special (`house_forecast`: a two-party average with SD
sqrt(8.06^2 + max(spread, 4)^2 / n), weighted by precision against the prior), but the backtest has never seen one:
no polls of past specials were collected, so its 68 races were scored on the prior alone. The Senate branch takes no
polls. This card collects them and tests the weighting.

### What is in the repo (counted 2026-11-26, no poll compared with a result)

- FiveThirtyEight's pollster-ratings file (`data/raw/538_github/2026-11-01/raw_polls.csv`, cycles 1998-2023) carries
  polls of 33 House specials, 31 of them inside the backtest (2008 on), and of all 6 Senate specials from 2010 on (MA
  2010, MA 2013, NJ 2013, AL 2017, MS 2018, GA 2021) and the 6 runoffs from 2002 on. Polls end up to about 60 days
  before the election; many are sponsored by a party or campaign. The file carries each race's result beside each poll;
  collection drops those columns.
- Nothing covers the 16 House specials from 2023 to 2026: the file stops at 2023 and VoteHub holds only 2026's regular
  seats.

### Rules (written and agreed 2026-11-26, before any poll was compared with a result)

Decisions the owner made on 2026-11-26: FiveThirtyEight's file plus each 2023-2026 special's Wikipedia page; the Senate
reported, with a poll option added to its branch; an adoption rule for the House; partisan polls compared as
candidates.

**The polls**

1. **Sources.** FiveThirtyEight's file for specials through 2022, matched on date, state and district
   (`location`, e.g. `NY-20`; at-large seats are `-1`) and, for the Senate, `race_id` (GA 2021 has two races on one
   date). For 2023-2026, the polling table on each special's Wikipedia page (or the special's section of the year's
   House page), cached in `data/raw/wikipedia_hist/` with the revision id. Each poll keeps its source.
2. **Which polls.** Field end date before election day, in the deciding round, with the deciding round's Democrat and
   Republican both named (`dem_cand` and `rep_cand` in the race table; a poll of another pairing is dropped and
   counted). Window: polls ending in the 21 days before the date; if a race has none, those ending 22 to 60 days
   before (the governor rule adopted at GV-3). One question per poll: likely voters over registered voters over adults,
   then the full-field question over a head-to-head.
3. **Partisan.** A poll is partisan if FiveThirtyEight's `partisan` column names a party, or, on Wikipedia, its
   footnote names a party, a party committee, a candidate's campaign or a group backing one side. Wikipedia tags are
   written down before any result is read and reported in a table.
4. **Margin.** Two-party, 100 x (D - R) / (D + R), as `poll_average` does now. A race's poll average is the plain mean
   with n = number of polls.

**The House test** (the backtest's 68 specials, `single_race.py backtest`: same prior, same SD, same date order)

5. **Candidates**, each scored on every polled special (a special with no usable poll under a candidate keeps the
   prior alone):
   - **P0**: the prior alone, as the backtest stands.
   - **P1**: the formula in the code, run as written: all polls, SD sqrt(8.06^2 + max(spread, 4)^2 / n), precision
     weight against the backtest's prior SD. 8.06 is the district-poll error fitted on general elections 2006-2024
     (`data/final/house_structure.json`), so it uses later years for every race; declared.
   - **P2**: P1 on nonpartisan polls only.
   - **P3**: P1 with every partisan poll moved 6.4 points against its sponsor's party. Added by me beside the owner's
     two options and kept by the owner on 2026-11-26, with the shift re-estimated without specials:
     - The frozen forecast's House sponsor shift (6.3, `poll_settings.json`, `partisan_shift_house`) was estimated on
       FiveThirtyEight's file, 1998-2022, which includes special elections: about 36 of its 671 sponsored-poll rows
       came from 15 specials, compared there with their results.
     - `python src/model/special_polls.py shift` reruns the frozen estimator (`poll_settings.sponsor_shift`) with
       every House and Senate race off the even-year general-election day removed (202 rows, 35 races; governors
       kept). It reproduces the frozen 6.27 and 4.32 on the full set and gives **6.44 +/- 0.34 for House districts**
       (640 polls, 342 races) and **4.37 +/- 0.32 statewide** (799 polls, 273 races) without specials
       (`data/processed/special_polls_shift.json`). Rounded: 6.4 and 4.4. No special-election poll was compared with
       a result.
   - **P4**: P1 with 8.06 replaced by a specials-specific poll error, estimated in date order from earlier polled
     specials only: a = sqrt(max(mean((poll average - result)^2) - mean(max(spread, 4)^2 / n), 0)) over them. 8.06 until
     10 earlier specials have polls. All polls, as P1.
6. **Adoption rule.** A candidate beats its baseline if, on the polled specials:
   - margin RMSE falls by at least 0.3 points (SP-3's rule 6a threshold);
   - the mean log score of the margin (the backtest's normal error shape, density at the result) rises;
   - RMSE falls in both 2008-2016 and 2017-2026, so one period cannot carry it;
   - the share of results inside the 80% range stays within 70-90% or moves toward 80%.
   The baselines:
   - P1 against P0 decides whether the House path's poll weighting stands. If P1 fails, the poll option stays in the
     code but is flagged on the card for the owner; P4 is still run.
   - P2, P3 and P4 each against P1. P2 and P3 change the same thing: if both pass, the one with the lower RMSE.
   - If P4 and one of P2 or P3 both pass, the pair together is run once more as a candidate suggested by these results,
     and must beat the better single one under the same rule.
7. **Reported, deciding nothing.** Polls alone (the poll average as the forecast), the mean poll error (positive =
   Democrats beat their polls), a = P4's final estimate against 8.06, the weight on polls race by race, the race table,
   all candidates on the specials from Wikipedia alone, and the P1 run with the window fixed at 60 days.

**Senate** (report only)

8. On the 6 Senate specials with polls, through SP-3's branch (L1, F1, t(3.9), SD 18): the prior alone against the
   prior plus polls, all polls and nonpartisan only, and partisan polls moved 4.4 (the statewide shift without specials, rule 5). The
   poll-average SD is the frozen forecast's statewide one, sqrt(4.24^2 + 11.81^2 / n) (`data/final/calibration.json`,
   `pollavg_sd_by_n`), weighted by precision against 18. MAE, RMSE, mean error, winners, coverage, race by race. The
   6 runoffs are a diagnostic table, as at SP-3. Nothing is fitted or chosen on these races.
9. **The poll option** (checklist for the Senate branch): `single_race.py senate --poll D,R ...` with that SD and the
   poll set the House test settles on (rule 6), with the statewide shift if P3 is adopted. Not changed by rule 8's
   results.

**Run once.** Collection first, with a coverage table (polls per special, partisan share, window used) reported before
any score is computed. Then one scoring run; every result is reported here, and the owner decides what the live path
uses.

### Collection report (2026-11-26, no poll compared with a result)

`python src/collect/special_polls.py fetch` cached the 16 Wikipedia pages (`data/raw/wikipedia_hist/2026-11-26/`,
`sp4_<race>.json` with revision ids); `collect` -> `data/interim/special_polls.csv` (every poll found, with its window
and whether it is in it).

| Polls in window | Races | Polls | Partisan |
|---|---|---|---|
| House specials from 2008 (31 of the backtest's 68 after the amendment below) | 37 | 87 | 22 |
| Senate specials | 6 | 71 | 12 |
| Senate runoffs (diagnostic) | 6 | 48 | 9 |

- **Wikipedia** adds 6 House specials: FL-6 2025, NJ-11 2026, NY-3 2024, RI-1 2023, TN-7 2025, UT-2 2023. The other ten
  pages hold only primary polls or none. The 13 Wikipedia polls are entered by hand in the collector (`WIKI`), each
  with its footnote; partisan tags were read from the footnote linked to each row. Where a page gives a second version
  of a question with leaners pushed (NY-3 and TN-7 Emerson, TN-7 Workbench), the first is kept.
- **The 22-60 day window** is used for 7 House races (IN-7 2008, MS-1 2008, KS-4 2017, UT-3 2017, AK-0 2022, UT-2
  2023, NJ-11 2026).
- **Only partisan polls**, so P2 leaves them on the prior: CA-25 2020, CA-36 2011, KS-4 2017, MS-1 2008, NJ-11 2026.
- One poll is dropped for another pairing (a Warnock-Loeffler question filed under the GA 2021 runoff). One poll's
  `partisan` names a minor party: partisan under rule 3, so left out of P2, and not shifted in P3 (no side to shift
  against).
- FiveThirtyEight's file gives one date per poll (`polldate`), not a field end date; the window uses it.
- In FiveThirtyEight's file a poll can carry several questions of the same pairing; the lowest `question_id` is kept.
  The file gives no population, so rule 2's order by population applies to Wikipedia polls only.

**Amendment to rule 2 (agreed 2026-11-26, after collection and before any score).** The result is all Democrats
against all Republicans; FiveThirtyEight's file records two candidates per poll. In two polled races they measure
different things, and full-field margins cannot be rebuilt from the file:
- **HI-1 2010**: two Democrats (Hanabusa, Case) against one Republican (Djou); the polls give Hanabusa against Djou.
- **AK-0 2022**: ranked-choice, two Republicans (Palin, Begich); a two-candidate poll and the deciding round can be
  different rounds.
Both keep the prior alone in every candidate and are listed in the report.

**Correction to the counts (found by the plumbing check, before the run).** The 37 House races above are those from
2008, not those in the backtest. The backtest (`special_model.load()`) leaves out multi-candidate races, NY-23 2009
among them, and starts scoring only once 8 earlier specials exist, so IL-14, IN-7 and LA-6 (early 2008) are not
scored. **31 polled House specials are scored** (33 before the amendment). P4 learns its poll error from earlier
polled specials in the backtest's own universe: the scored ones before the date plus MA-5 and OH-5 2007 and IL-14,
IN-7 and LA-6 2008; never NY-23 2009 or the two amended races. NY-23 is therefore not in the test at all.

**Two clarifications (agreed 2026-11-26, with the correction above, before the run).**
- Rule 6 is this card's own adoption rule. `BACKTEST.md`'s rule is built on whole cycles and log loss and does not
  apply to single specials; it was named when the pass mark was chosen, but rule 6 as written is what decides.
- In the Senate report (rule 8), n in the poll-average SD is the plain number of polls. The frozen forecast counts
  older polls at half weight; the report does not. Nothing is chosen from the report.

### Step report: the scoring run (2026-11-26, run once)

`python src/model/special_polls.py score` -> `data/processed/special_polls_scores.json`, `special_polls_house.csv`,
`special_polls_senate.csv`. The script refuses to run again once the scores file exists.

**House, the 31 polled specials** (margin in points, Democrat minus Republican; error = result minus forecast, positive = Democrats beat the
forecast)

| | RMSE | MAE | Mean error | Log score | 50% | 80% | 95% | Winners |
|---|---|---|---|---|---|---|---|---|
| P0 prior alone | 10.77 | 8.55 | +1.68 | -3.798 | 52% | 90% | 100% | 25 |
| **P1 all polls (code)** | **7.66** | **6.01** | +0.34 | **-3.451** | 55% | 71% | 97% | 26 |
| P2 nonpartisan only | 9.05 | 6.84 | +0.28 | -3.439 | 55% | 74% | 100% | 26 |
| P3 partisan shifted 6.4 | 8.38 | 6.53 | +1.24 | -3.554 | 52% | 71% | 94% | 26 |
| P4 specials poll error | 7.78 | 6.08 | +0.24 | -3.648 | 48% | 65% | 81% | 27 |
| P1w60 (diagnostic) | 8.09 | 6.56 | +1.05 | -3.509 | 48% | 71% | 97% | 24 |
| Polls alone (diagnostic) | 8.18 | 6.45 | | | | | | 25 |

**The adoption rule (rule 6)**

| | RMSE change | Log score change | RMSE change 2008-16 / 2017-26 | 80% coverage | Result |
|---|---|---|---|---|---|
| P1 against P0 | -3.11 | +0.347 | -7.86 / -0.60 | 90% -> 71% | **passes** |
| P2 against P1 | +1.39 | +0.012 | +4.35 / +0.03 | 71% -> 74% | fails (RMSE, periods) |
| P3 against P1 | +0.73 | -0.103 | +1.13 / +0.59 | 71% -> 71% | fails (RMSE, log, periods) |
| P4 against P1 | +0.12 | -0.197 | +0.07 / +0.14 | 71% -> 65% | fails (all four) |

P5 was not run (P4 failed). So the House path's poll weighting stands as it is in the code: all polls, partisan ones
unshifted, the district poll SD 8.06.

**Reported, deciding nothing (rule 7)**
- **Most of P1's gain comes from 2008-2016.** RMSE falls 7.9 points there and 0.6 in 2017-2026. P1's 80% coverage
  (71%) is just inside the 70-90% band.
- **Mean poll error**: results were 0.2 points more Republican than the poll average (n = 31). This is no sign of
  a lean in either direction.
- **P4's own poll error** ended at 7.05 (36 earlier polled specials), against 8.06. Early on it was much lower (2.5 to
  4.2 in 2011-2017), which made P4's ranges too narrow (81% at 95%).
- **Weight on polls**: P1 0.62 to 0.77; P4 0.66 to 0.94.
- **The six Wikipedia races (2023-2026)**: the prior alone did best, RMSE 5.89 against P1's 8.71 (P2 8.42, P3 9.11,
  P4 9.15). All four candidates picked every winner. Six races cannot decide anything. Three single polls or pairs
  missed by 14 to 16 points: RI-1 (polls too Republican), UT-2 and FL-6 (polls too Democratic).
- **All 68 specials** (unpolled races keep the prior): RMSE P0 11.51, P1 10.31, P2 10.81, P3 10.57, P4 10.35.
- **Excluded by the amendment**: HI-1 2010 and AK-0 2022 keep the prior in every candidate.
- Race by race: `data/processed/special_polls_house.csv`.

**Senate (rule 8, report only)**, SP-3's branch with SD 18 against the prior plus polls (statewide poll SD, plain n)

| | Specials with polls (6): RMSE | MAE | Mean error | Winners | In 80% | Runoffs with polls (6): RMSE | MAE | Mean error | Winners |
|---|---|---|---|---|---|---|---|---|---|
| S0 prior alone | 14.67 | 10.50 | -1.19 | 4 | 4 | 21.71 | 18.27 | +10.54 | 3 |
| S1 all polls | 3.48 | 2.62 | -0.29 | 4 | 5 | 6.19 | 4.35 | +0.45 | 6 |
| S2 nonpartisan only | 3.27 | 2.56 | -0.55 | 5 | 5 | 6.06 | 4.28 | +0.46 | 6 |
| S3 partisan shifted 4.4 | 3.29 | 2.50 | -0.66 | 5 | 5 | 5.91 | 3.99 | +0.07 | 6 |

The polls carry 0.79 to 0.93 of the weight. MA 2010 (prior D+21, result R+5) and AL 2017 (prior R+22, result D+2)
are where the prior alone fails. The three poll versions differ in calls only on MA 2010 (S1 has Brown losing narrowly)
and otherwise by fractions of a point. Race by race: `data/processed/special_polls_senate.csv`.

**Rule 9, done**: `single_race.py senate --poll D,R ...` uses the House result's poll set (all polls, unshifted) and
the frozen statewide SD, weighted against 18. Checked on MA 2010 with its 13 polls: D+0.3, SD 5.1, weight 0.92, the
same as S1 in the run.


## 3. Recent specials as a signal for off-year governors (SP-5)

A House special's environment adds a recent-specials term: the mean miss of House specials in the 365 days before
it, shrunk by n / (n + 2) (`single_race.py special_environment`; SP-1). Off-year governor races (New Jersey and
Virginia in the year after a presidential election, Kentucky, Louisiana and Mississippi in the year before one) use
the off-cycle estimator scaled by term year (GV-3, BACKTEST.md "Odd-year environment as of each date"), with no such
term. This card tests whether adding it helps them.

### Rules (written and agreed 2026-11-27, before any recent-specials shift was compared with a governor result)

Decisions the owner made on 2026-11-27: the pass rule in rule 6 (no fixed floor); a second candidate declared now (C2); judged with
polls; adoption changes the 2027 path only.

**What is already known, declared.** The baseline's errors by year on the prior alone are public in BACKTEST.md
(for example, 1.7 and 3.7 points in New Jersey and Virginia in 2025). The direction House specials have leaned by era
(Republican in 2009-10, Democratic since 2017) is in `special_model.py`'s docstring. No recent-specials shift has been
computed for a governor race, and none has been set beside a governor result.

**The test bed**

1. **Races.** The odd-year governor races in `governor_inputs.py offyear` (contested, two-way, no recalls) from 2007
   on, because the House specials table (`data/interim/house_specials.csv`) starts in August 2007: 26 races in 10
   years (2007 to 2025; West Virginia's 2011 special included). The shift is one number per year, the same for
   every race in it (apart from the race dates in rule 3), so this is about 10 observations, not 26. Expect a weak
   test.
2. **Forecast of a race, as of its year.** Fitted on even-year races before the year only, as GV-3's test:
   - the prior, `GV.estimate` on those races with spec `lean_avg2` (margin ~ lean_avg2 + env + inc, env the
     realized national House vote); the race's prior uses the environment under test;
   - with polls (the owner's choice): the race's `poll_avg` (n = `n_polls`) weighted against the prior as
     `single_race.py governor` does: w = s^2 / (s^2 + sd_poll(n)^2), s = the fit's `sd_prior_implied`,
     sd_poll(n) = sqrt(4.24^2 + 11.81^2 / n). A race with no polls on file (Louisiana 2007, 2011, 2023; Mississippi
     2007) keeps the prior alone. The 2025 races' polls are VoteHub's, the rest FiveThirtyEight's, as the table has them.
   - The baseline environment is GV-3's `estimator, by term year` for the year (`governor_offyear_env.csv`: the
     estimator fitted on elections before the year, its midterm term scaled by m fitted on earlier odd years of the
     same term year), on election day of that year.
3. **Race dates** for the specials window (the date of the round the table's margin comes from): Kentucky,
   Mississippi, New Jersey and Virginia on the November election day; West Virginia 2011 on 4 Oct; Louisiana on its
   deciding round: 20 Oct 2007, 22 Oct 2011, 21 Nov 2015 (runoff), 16 Nov 2019 (runoff), 14 Oct 2023.

**The shift, as of the race**

4. For a race on date D in year y:
   - The environment model is `environment.py`'s, fitted on elections before y (as the baseline is). Each House
     special's e0 and slope (its environment at m = 0, and the change per unit of m) are recomputed on its own date
     with that fit. The `SM.load()` table uses the full-sample fit; the test does not.
   - m for each half of the presidential term is fitted on House specials strictly before D (`SM.best_m`; 1.0 until a
     half has 8 earlier specials), as `special_environment` does.
   - shift = mean over House specials in [D - 365 days, D) of (implied environment - (e0 + slope x m for its half)),
     times n / (n + 2). No specials in the window: shift 0.
   - The implied environment inverts the frozen House district prior (`data/final/house_structure.json`), which was
     fitted on general elections 2006-2024 and cannot be made as of the date. Declared, as at SP-1.
   - k = 2 is kept as chosen on House specials and not retuned here.
5. **Candidates**, each against the baseline B:
   - **C1**: B plus the shift, in every race.
   - **C2**: B plus the shift in the year after a presidential election only (New Jersey and Virginia, 10 races);
     the year before one keeps B. Declared now at the owner's request; GV-3 found the environment helps only in the
     year after a presidential election. If C2 alone is adopted, the 2027 races (term year 3) are unchanged.

**The decision**

6. **Pass rule.** A candidate passes against B if, on the 26 races with polls in (rule 2):
   - margin RMSE falls by more than its standard deviation over the 10 years redrawn with replacement (10,000
     draws, seed 20261127; a draw takes every race of each year it picks);
   - and still falls with each of the 10 years left out in turn.
   If both pass, the one with the lower RMSE. No fixed floor: a 0.5-point floor was drafted and dropped by the owner
   before any run, because with polls in a race's margin moves by only (1 - w) times the prior's move, w near 0.8 in
   most polled races, and the two conditions above guard against one lucky year.
7. **Reported, deciding nothing.** The same table on the prior alone (GV-3's footing); the split by term year; the
   shift, its n and the poll weight race by race; mean error; winners called.
8. **If a candidate passes**, `single_race.py governor` (the 2027 path, GV-6) adds the shift in the races it
   covers. The frozen governor design (tag `governor-design-2026`), `backtest_asof.py` and the 2026 forecast files
   are not touched, and GV-5 scores what was frozen. If none passes, nothing changes and the result is recorded on
   the card.

**Run once.** First `python src/model/governor_inputs.py offyear` is rerun to confirm GV-3's table and files
reproduce exactly. A `check` step then prints each race's date, shift and n, with no result in it. Then one scoring
run (`python src/model/specials_governors.py score`), which refuses to run again once its output
(`data/processed/specials_governors.json`) exists. Every result is reported here.

### Step report: the scoring run (2026-11-27, run once)

**Before the run.** `governor_inputs.py offyear` was rerun and rewrote GV-3's two files with no change (`git diff`
empty). The `check` step printed each race's date, shift and n with no result in it: shifts run from -13.3 (2007,
from 2 specials, with m still at its default of 1) to +8.9 (2023, from 1 special), and the baseline environments
match GV-3's (2025: D+16.5). Two faults were fixed before any score came out, each in its own commit: a column name
that clashed with a pandas method (the run crashed before computing anything), and the check that B on the prior
alone reproduces GV-3's errors race by race, which was set to 0.001 while GV-3's files are rounded to 3 decimals
(largest gap 0.001; now 0.01). Then one scoring run (`data/processed/specials_governors.json`).

**Result: neither candidate passes; nothing is adopted.**

| With polls (decides), 26 races | RMSE | MAE | Mean error | RMSE, year after a presidential election (10) | RMSE, year before one (16) | Winners |
|---|---|---|---|---|---|---|
| B, term-year estimator | 14.24 | 8.19 | -5.26 | 5.16 | 17.69 | 21 |
| C1, plus the shift in every race | 12.82 | 7.96 | -4.39 | 5.13 | 15.84 | 22 |
| C2, plus the shift in the year after only | 14.24 | 8.19 | -5.36 | 5.13 | 17.69 | 21 |

| Rule 6 | Gain in RMSE | SD over redrawn years | Smallest gain with one year left out | Passes |
|---|---|---|---|---|
| C1 | 1.42 | 1.17 | -0.07 (2007 left out) | No |
| C2 | 0.004 | 0.02 | -0.01 (2025 left out) | No |

- **C1** clears the redrawn-years condition but fails the leave-one-year-out one. Its gain rests on 2007: Louisiana
  2007 has no polls, and the 2007 shift (-13.3, toward Republicans, from the two specials of 2007 before the race, CA-37 on 21 August and MA-5
  on 16 October, when no earlier specials had yet fixed m) moves Jindal's forecast from D+6.7 to R+3.4, against a result of R+51. Without
  2007 the gain is -0.07. Every other year left out keeps a gain of 1.4 to 2.0, but those all contain 2007.
- **C2** changes almost nothing: in New Jersey and Virginia the polls carry 0.88 to 0.92 of the weight, so a shift of
  2 to 7 points moves a forecast by a few tenths.
- Mean error is negative throughout (Republicans did better than forecast). Under B the three Louisiana races with
  no polls (2007, 2011, 2023) carry -108 of the -137 summed error; the year-after races average -0.3. Those three
  races also dominate the year-before RMSE, and so the deciding statistic (figures from the saved race table).

**Reported, deciding nothing: the prior alone (GV-3's footing).** Both candidates are worse than B: RMSE 18.72 for B,
18.91 for C1 (worse in both halves of the term) and 18.84 for C2 (worse in the year after a presidential election,
the same in the year before). Under rule 6 on this footing: C1 gain -0.19, SD 0.68, smallest leave-out gain -0.77;
C2 -0.12, 0.22, -0.23. C1 removes the mean error (-1.22 to -0.09) but adds spread. Winners called on the prior alone
(derived from the saved table): B 19, C1 21, C2 19 of 26. Race by race: the `race_table` in
`data/processed/specials_governors.json`.

**What this means.** On the 26 off-year races since 2007, with polls in, adding the House specials term to every
race cut the margin RMSE from 14.24 to 12.82 and cleared the redrawn-years condition, but the gain disappears with
2007 left out: it comes from a single unpolled Louisiana race in a year when the shift rests on two specials. On the
prior alone both versions are worse. `single_race.py governor` and the frozen governor
design are unchanged (rule 8). The 2027 races (GV-6) use the term-year estimator as they stand.

## 4. Watch list (SP-8)

The card: vacancies and scheduled specials, checked regularly, so a special is caught when it is called rather than
when someone notices. Decided by the owner on 2026-11-27: the House Clerk's vacancy list and Wikipedia as the sources,
a weekly check, House and Senate seats, and a live special tripped by the check leads to a page for it. No news API:
NewsAPI's free plan is for development only, World News API's free plan forbids storing anything derived from it, and
GDELT failed a reliability test and is out (the owner's rule: low reliability means out; result below, after the
build report).

### What the sources hold (checked 2026-11-27)

- **House Clerk, "Vacancies of the 119th Congress"** (`clerk.house.gov/Members/ViewVacancies`): official, plain HTML,
  one block per vacancy: district, how it fell vacant and when, the member, and either the successor with the oath
  date or "Special Election Date TBD" with the state's election office. Only vacancies that have happened; nothing
  for announced resignations, nothing for the Senate.
- **Wikipedia, "<n>th United States Congress", section "Changes in membership"**: a Senate table and a House table
  (state or district, vacated by, reason for change, successor, date seated). The reason column carries announced
  resignations, appointments and special election dates in prose. The 120th Congress page already exists and lists
  two Senate seats to be vacated in January 2027 (Minnesota, special in November 2027; Tennessee, special in November
  2028).
- **The Downballot's 2027-2028 special elections sheet**: results after the fact, for races with one Democrat and
  one Republican, congressional and legislative. Not a vacancy list. Linked for results, not used by the check.

Where the Clerk and Wikipedia disagree (on 2026-11-27 the Clerk shows "Special Election Date TBD" for TX-23 and FL-20,
Wikipedia "Vacant until the next Congress"), the check reports both and decides nothing.

### Rules (written and agreed 2026-11-27, before the check was built)

1. **Universe.** Every U.S. House and Senate seat that is vacant, or that Wikipedia says will be vacated, in the
   current Congress and the next one once its page exists.
2. **The watch file.** `data/interim/specials_watch.csv`, one row per vacancy: chamber, state, district or class,
   vacated by and party, reason (died, resigned, appointed elsewhere, other), vacancy date (actual or announced),
   successor (appointed or elected) and date seated, special election dates found (primary, runoff, general),
   status, and the source of each field. Committed; it holds public facts only.
3. **Status**, one of: announced (resignation not yet in effect); vacant, no date; special scheduled; appointed
   (Senate, special still to come); held (result not yet seated); filled; no special (seat left vacant to the end of
   the Congress). A special held on a regular November general-election day is marked `general_day` and handled by
   the regular forecast, not as a live special.
4. **What trips.** Any new row, or any change of status or date on an existing one. A trip on a special that is
   scheduled and not on a general-election day is a **live special**: the check names it in the pull request as
   ready for the live-special steps (SP-7: race details, lean on the lines in force, polls, run, page at
   `/specials/<race>/`). Building that page is SP-7's work; SP-8 detects and hands over (agreed 2026-11-27; SP-7 is the
   next card, since one live special is already known).
5. **Weekly run.** GitHub Actions (agreed 2026-11-27; Windows Task Scheduler on this machine is the fallback if a
   source blocks GitHub's runners), Monday morning, ending in a pull request only when the watch file changes, with the changes listed
   in the description. A source that fails to load or parse fails the run visibly instead of writing an empty list.
6. **Dates in prose.** Special election dates are read from Wikipedia's reason column with a date pattern; a reason
   that mentions a special election with no date it can read is listed in the pull request for a person to check.

### Build report (2026-11-27)

`src/collect/specials_watch.py` writes `data/interim/specials_watch.csv` and the change list `ci_out/specials_watch.md`;
`.github/workflows/specials-watch.yml` runs it on Mondays at 7:17 am Toronto time (and by hand) and opens a pull
request only when the watch file changed. Raw copies of each check go to `data/raw/specials_watch/<date>/` and are
committed with a changed list.

Rules as built, where the draft left room:

- Clerk rows are matched to Wikipedia's House rows by seat and Congress; where Wikipedia has two rows for a seat, the
  one with the nearest vacancy date. Once the Clerk lists a vacancy, its vacancy date is used.
- Wikipedia's party-change rows are dropped (not vacancies).
- Special election dates are read from sentences that mention a special election, a runoff, a special primary or a
  successor "elected ... to finish the term"; a date after "ending", "through" or "until" is a term's end and skipped.
  A bare month ("November 2027") is kept as a month. A month of November in an even year counts as a general-election day.
  A date written without a year ("a runoff will be held on August 18") takes the year of the sentence's previous date
  (the next year if that would put it earlier).
- An announced resignation's vacancy date is the "effective" date where the prose gives one.
- A special is live while any round, first or runoff, is still to come, unless that next round falls on a
  general-election day.
- Rows of the watched Congresses that vanish from both sources stay in the file with status `gone` and the live flag
  cleared, so the change trips the check once. A row Wikipedia renames shows up as gone beside a new one.
- An empty Clerk list is valid (a new Congress opens with none); a page without the "Vacancies of the <n>th Congress"
  heading fails the run.

**Check on past revisions (2026-11-27, scratchpad only).** The Wikipedia parser was run on the 119th Congress page as
it stood on eight dates from February 2025 to August 2026, with "today" set to each date. Every House special of the
period came out scheduled and live while it was ahead (FL-1, FL-6, AZ-7, VA-11, TX-18, TN-7, NJ-11, CA-1, CA-14,
GA-13) and held once past. Three faults were found and fixed (the rules just above): TX-18's pending runoff was not
live, CA-14's and GA-13's runoffs were missed (dates without a year), and GA-14's announced resignation took the
announcement date instead of the effective date. "A special election will be held on a date TBD" and "... will be
called within 30 days" correctly give no date.

First run, 2026-11-27 (the seed for the weekly comparison, rebuilt after the fixes above): 24 rows, 15 House and
9 Senate, 22 for the 119th Congress and 2 for the 120th; 16 filled, 5 announced, 2 with no special, 1 held (Ohio Senate,
winner not yet seated).

- **Live special:** Minnesota Senate (class 1). Klobuchar resigns in January 2027 to become governor; an appointee
  serves until a special in November 2027.
- **Announced, not live:** Tennessee Senate (class 1), special in November 2028 (general-election day); OK-1 (Hern,
  30 November 2026, no special: vacant until the next Congress); CA-34 (Gomez, 1 December 2026); Oklahoma Senate
  (Armstrong replaced by Hern on 30 November 2026).
- **For a person to check:** TX-23 and FL-20, where the Clerk says "Special Election Date TBD" and Wikipedia "Vacant
  until the next Congress"; FL-1, where the Clerk dates the vacancy 3 January 2025 and Wikipedia Gaetz's resignation
  13 November 2024. These notes stay until a source changes; only changes trip the check.

**First run on GitHub Actions (2026-11-27, dispatched by the owner after the merge).** It found no changes from the
seed, as expected: the House Clerk's page and Wikipedia both serve GitHub's runners, so the Task Scheduler fallback is
not needed.

### GDELT reliability test (2026-11-27, stopped early)

GDELT's DOC 2.0 API was the one news source whose terms fit (free, no key, unrestricted use with a citation and a link,
results may be stored). It was tested as a possible tripwire beside the check, from this machine, after a first burst
of requests on 2026-11-27 was refused with HTTP 429 ("Please limit requests to one every 5 seconds").

- **Design:** one request every 10 minutes, about 120 times slower than the stated limit, rotating three queries
  (specials for Congress; members resigning or dying; governors setting a House special's date), each limited to US
  sources in English over the past month. No retries inside a slot. Planned for six hours.
- **Result:** 19 requests from 15:10 to 18:14 UTC; 5 accepted (26%), 14 refused with 429, in runs of up to seven in a
  row, the last six all refused. Every accepted request returned an empty result (`{}`): most likely the queries were
  too strict or in a form the API rejects without an error, but with most requests refused there was no room to try
  other wordings.
- **Decision (owner, 2026-11-27):** stopped after three hours; the refusal rate alone settles it. GDELT is out. The
  check stays on the House Clerk and Wikipedia. Script and log were kept in the session's scratchpad, not the repo.


## 5. Runbook and page for a live special (SP-7)

The card: the steps from a special being called to a published page (race details, lean on the lines in force, polls,
run, publish), a page template at `/specials/<race>/` (SI-1, 2026-11-20), and a dry run on a past special. SP-8 hands
over each live special it finds; the first is Minnesota's Senate seat (class 1), special on November 2, 2027.

### What is in the repo (checked 2026-11-27)

- **The run.** `src/model/single_race.py house | senate` forecasts one special on any date, with polls passed by hand
  (`--poll D,R`). It prints the forecast and saves nothing; only `backtest` writes a file. The Senate branch refuses
  a date after November 3, 2026 until the certified 2026 House vote is in (DA-12), so Minnesota cannot be run yet.
- **Polls.** `src/collect/special_polls.py` collects polls of past specials only (SP-4). There is no collector for a
  race still ahead.
- **The site.** `src/site/landing.py` builds the landing page and the coming pages from `src/site/site.json`; the
  landing page prints `callout.text` when the callout is set (it is `null`) and has no end date. There is no
  `/specials/` page or template. The scorecard job rebuilds and commits `site/`, so anything under `site/specials/`
  ships on the next merge.

### Decided by the owner (2026-11-27, before the rules below were drafted)

- **Dry run:** one of each, a 2025-26 House special with polls and one past Senate special. The House run is
  prospective; the Senate run is a walk-through, not a test, because its SD of 18 was chosen on the same 13 races.
  (Found at the dry run: the House race, TN-7, was in SP-4's scoring run, so it is a walk-through as well.)
- **Dry-run pages** are built locally and on a Cloudflare preview only, never committed under `site/`.
- **Minnesota before DA-12:** its page goes up in the coming state, with the landing callout and an end date.
- **Refresh by hand,** following the runbook, not by a scheduled job.

### Rules (written and agreed 2026-11-27, before anything was built)

1. **One record per race.** `data/specials/<race>.json`, with `<race>` as `<state>-<seat>-<year>` (`mn-senate-2027`,
   `tn-07-2025`): chamber, state, seat, vacancy (from the watch file row), election dates (each round), candidates and
   parties as filed, the lean used and its source, polls entered (pollster, dates, sample, D, R, source link), and
   a list of runs. Committed; public facts and the repo's own outputs only.
2. **A run is saved, not printed.** `single_race.py` gains a `--save <race>` option that appends the run to the
   record: run date, inputs (lean, environment, incumbency, polls used), margin, interval (50/80/95%), win
   probability, and the git commit. No change to the model or its settings; `check_frozen.py` must still pass.
3. **Page states** (SI-1's states for one race): **coming** (the race, the dates, what the forecast waits on, no
   numbers); **forecast** (latest run: margin, interval, win probability, and every earlier run as a line); **result**
   (the locked last run beside the certified result, the miss in points, and whether the result fell inside each
   interval). A page moves to forecast only once the branch it uses is decided in this note (House: PLAN.md item 5
   and SP-4; Senate: section 1's decision). A poll-only state is not used: the single-race path always has a prior.
4. **Page template.** One template, `src/site/special.py`, built from the same entry point as the landing page, with
   the shared header, footer and stylesheet; every word that is not a number comes from the record or `site.json`.
   The page says which branch ran, that the Senate SD was chosen on the races it was checked on, and links to this
   note.
5. **Callout.** `site.json` `callout` gains `path` and `ends` (a date); the build drops a callout past its end date.
   For a live special it ends the day after the last round.
6. **When to rerun** (the runbook): on the day the page goes to forecast; on each new poll entered; on the first of
   each month; daily in the final 7 days; and a last run the evening before election day, which is locked. Each
   rerun is a pull request with the record and the rebuilt page.
7. **Polls by hand.** Polls are entered into the record from Wikipedia's page for the race (revision id kept) or the
   pollster's release, under SP-4's rules (two-party share; leaners pushed where given; one question per poll, the
   first if several). No poll is dropped for its result.
8. **Dry runs.** Each runs strictly as of a date before the race (the House one at the last-run point, the evening
   before), using only polls released by then, and is reported here with its miss. Proposed: TN-7 (December 2, 2025;
   polls from SP-4) for the House, and Alabama 2017 (December 12, 2017) for the Senate. The dry runs change nothing in
   the model whatever their result.
9. **The runbook** is section 5's last part, written as numbered steps a person can follow from the SP-8 pull request
   to a published page and, after the race, to the result state.

### Build report (2026-11-27)

- **Records.** `data/specials/<race>.json` for live races; dry runs in `data/specials/dry_runs/`, which the site build
  never reads (it refuses a record marked `dry_run` at the top level). Minnesota's record, `mn-senate-2027`, is in the
  coming state: the vacancy, a month for the election (Wikipedia gives November 2027; the day waits on Minnesota's
  Secretary of State), and four things the forecast waits on.
- **The run.** `single_race.py house | senate --save <race>` (rule 2) takes the state, seat, date and incumbency from
  the record, and the record's polls under SP-4's window as of the run date (`--asof`, default today); `--lock` marks
  the last run. It refuses a run on or after election day, and a record whose election date is not a full date. The
  model and its settings are unchanged; the forecast functions are called as before.
- **The page.** `src/site/special.py`, called by `landing.py` (and so by `build.py` and the daily scorecard job),
  writes `site/specials/<race>/` for every live record; `--preview OUT <records>` writes dry runs elsewhere. The
  latest run is shown as figures and one strip (forecast margin, 80% and 95% intervals, the result once in), then
  every run, the polls, the key dates, the candidates, and the branch's method in words, with the Senate SD's caveat.
- **Callout.** `site.json` `callout` takes `link`, `path` and `ends`; `landing.py` drops it after `ends`. Minnesota's
  is up, ending 2027-11-30 until the day is confirmed (rule 5 then moves it to the day after the election).

Rules as built, where the draft left room or the build departed from it:

- **The poll window.** Rule 7's "under SP-4's rules" includes SP-4 rule 2's window, so a run averages only polls that
  ended in the 21 days before election day, or, with none there, 22 to 60 days before. A poll more than 60 days out
  is listed on the page but enters no run, and once one poll lands in the last 21 days the older ones drop out. For
  Minnesota, that means polls from early and mid 2027 move nothing until September; a rerun on such a poll (rule 6)
  repeats the prior. **For the owner:** keep the window as is, or widen it for a race months away (that would be a
  new rule, untested on past specials).
- **Fixed wording** (the branch descriptions, the state notes, the table headings) lives in `src/site/special.py`, not
  the record or `site.json` as rule 4 said; it is the same for every race.
- **Polls** carry pollster, field end date, population, D, R, partisan tag, source and note; no sample size or start
  date, which rule 1 listed (the SP-4 tables the dry runs drew on have neither, and no run uses them).
- **Dry-run records** are committed in `data/specials/dry_runs/` so the runs can be repeated; their pages are not.
- **Link preview:** each special's page uses the landing page's card (`og-home.png`); `site/og.png` is the 2026
  forecast's.

### Dry runs (2026-11-27, pages on a local preview only)

Each run as of a date before the race, with the polls whose field ended by then; the last is locked. Records:
`data/specials/dry_runs/tn-07-2025.json`, `al-senate-2017.json`.

| Race | Run | Polls (window) | Prior | Poll avg (weight) | Forecast | 80% interval | P(D) | Result | Miss |
|---|---|---|---|---|---|---|---|---|---|
| TN-7, Dec 2, 2025 (House) | Oct 21 | 2 (22-60 days) | R+5.3 | R+9.6 (0.64) | R+8.1 | R+16.8 to D+0.7 | 12% | | |
| | Dec 1, locked | 1 (1-21 days) | R+5.3 | R+2.1 (0.62) | R+3.4 | R+12.4 to D+5.7 | 32% | R+8.9 | 5.5 toward R |
| Alabama Senate, Dec 12, 2017 | Nov 1 | 4 (22-60 days) | R+22.4 | R+10.5 (0.86) | R+12.1 | R+19.4 to R+4.9 | 3% | | |
| | Dec 11, locked | 18 (1-21 days) | R+22.4 | R+2.9 (0.93) | R+4.3 | R+9.6 to D+0.9 | 14% | D+1.6 | 6.0 toward D |

- **TN-7** had the winner; the result fell inside the 80% and 95% intervals, outside the 50%. The one poll in the
  final window (Emerson, R+2.1) was further from the result than the prior's R+5.3 and pulled the forecast toward the
  Democrat. TN-7 is a walk-through too, not a test: it was one of the six Wikipedia races in SP-4's scoring run, with
  these polls, and the poll rule (P1) was settled on that run.
- **Alabama 2017** missed the winner (Jones at 14%); the result fell inside the 95% interval only. As agreed, this is
  a walk-through, not a test: the SD of 18 was chosen on these races, and Alabama is one of them.
- **What the dry runs found about the steps**, none of it a change to the model:
  - The environment is taken on election day, as the backtest does, not on the run date; an early dry run therefore
    sees approval up to election day. A live run sees only what exists on its date, so this matters only for dry runs.
  - "Polls released by then" is read as field ended by then; the collected tables carry no release date.
  - FiveThirtyEight's file does not tag the NRSC's Alabama poll as partisan; SP-4 rule 3 takes the file's tag, so the
    page shows it untagged. A live race's polls are tagged by hand (runbook step 6).
  - The runs saved the base commit (`cdbaa89`) because `--save` itself was not yet committed.
- Dry-run pages were checked in a browser in light and dark mode in all three states (coming: Minnesota; forecast:
  TN-7 with its result removed; result: both dry runs).

### Runbook: from a live special to a published page

1. **The trip.** The weekly SP-8 pull request names a live special. Merge it, then read the race's row in
   `data/interim/specials_watch.csv`.
2. **The record.** Copy `data/specials/mn-senate-2027.json` to `data/specials/<race>.json` (`<state>-<seat>-<year>`,
   e.g. `oh-03-2027`, `mn-senate-2027`). Fill in: title, chamber, `branch` (`house` or `senate`), state, state name,
   seat, `district` (House), the vacancy, each round's date, and `waits_on`. Enter a round's date as a full
   `YYYY-MM-DD` only once it is checked against the state's election office; until then the month alone.
3. **The inputs the branch needs.** House: the district's PVI on the lines in force (`lookup_lean2`; after the 2026
   general, `data/interim/house_2026_races.csv`). Senate: the lean's election and the last House vote (DA-12 for any
   date after November 3, 2026). If one is missing, say so in `waits_on`; the run refuses rather than guess.
4. **Coming page and callout.** `python src/site/landing.py` writes `site/specials/<race>/`. In `src/site/site.json`
   set `callout` to `{"text": ..., "link": "The race page", "path": "specials/<race>/", "ends": <the day after the
   last round, or the month's last day while only the month is known>}`. Open a pull request; check the page on its
   Cloudflare preview; merge.
5. **Candidates.** After the nominations, add `candidates` (name, party) and `inc`: +1 if a sitting member from the
   seat (an appointee included) runs as a Democrat, -1 as a Republican, 0 for an open seat.
6. **Polls.** Enter every poll of the deciding round's Democrat against its Republican, from the race's Wikipedia
   page (note the revision id in `source`) or the pollster's release: pollster, field end date, population, D, R,
   `partisan` (the party, if a party, a party committee, a campaign or a group backing one side paid for it), source.
   One question per poll: likely voters over registered voters over adults, then the full field over a head-to-head.
   No poll is dropped for its numbers.
7. **First run.** `python src/model/single_race.py <branch> --save <race>`, once step 3's inputs and the candidates
   are in. Rebuild (`python src/site/landing.py`), open a pull request with the record and the page, merge.
8. **Reruns** (rule 6), each the same command and a pull request: on each new poll entered; on the first of each
   month; daily in the final 7 days.
9. **Last run,** the evening before election day: add `--lock`.
10. **Result.** Once the state certifies, add `"result": {"margin": <two-party D-R>, "dem_votes": ..., "rep_votes":
    ..., "source": ...}`, rebuild (the page moves to the result state), and report the race here: the locked run,
    the result, the miss, the intervals that held it. Set `callout` back to `null`. (The callout drops at the first
    build after `ends`; the daily scorecard job rebuilds only while it runs, so check the landing page then.)
11. **A dry run or a check** of any record: `python src/site/special.py --preview ci_out/preview <record.json>` and
    serve `ci_out/preview` (with a copy of `site/assets`) locally; nothing under `site/` changes.
