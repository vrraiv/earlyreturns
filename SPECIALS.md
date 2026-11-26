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
  one 2021 date): KS-4, MT-AL, SC-5 and GA-6 in 2017 (121 to 158 days), NM-1 in 2021 (170). None of G's Senate races
  is affected.

### Step 3 report: the scoring run (2026-11-26, run once)

`python src/model/senate_specials.py score` -> `data/processed/senate_specials_scores.json` (summaries, runoffs,
coverage) and `data/processed/senate_specials_races.csv` (every race, lean, environment, forecast and error). Margin =
lean + environment + 2 x incumbency; positive error = Democrats beat the forecast. The first run's summaries were
written before a print of the race table failed on a column name; that print was fixed and the table read from the
saved file, with no rerun of the scoring.

**Specials, margin RMSE (MAE in brackets; winners right of n)**

| Lean | Env | All 13 | 1989 on (10) | 2008 on (6) | G's 6 |
|---|---|---|---|---|---|
| L1 | N | 22.5 (18.0; 7) | 23.9 (18.5; 6) | 20.5 (15.2; 3) | 20.5 |
| L1 | F1 | **17.9** (14.0; 8) | 18.2 (13.7; 7) | 14.7 (10.5; 4) | 14.7 |
| L1 | H | 20.7 (16.4; 7) | 20.7 (15.6; 5) | 14.3 (11.2; 2) | 14.3 |
| L1 | H+R | 20.2 (16.4; 7) | 20.0 (15.6; 5) | 14.1 (11.7; 2) | 14.1 |
| L1 | G | | | | 16.3 (12.9; 4) |
| LP | N | 22.8 (17.4; 7) | 23.7 (17.9; 5) | 20.6 (15.8; 3) | 20.6 |
| LP | F1 | 19.7 (15.1; 7) | 18.2 (13.5; 6) | 14.6 (10.0; 4) | 14.6 |
| LP | H | 19.1 (14.0; 8) | 19.9 (13.9; 6) | 14.0 (10.6; 3) | 14.0 |
| LP | H+R | 18.0 (14.0; 7) | 18.6 (14.0; 5) | **13.7** (11.1; 2) | 13.7 |
| LP | G | | | | 16.4 (13.5; 4) |
| LB | N | 24.1 (17.8; 7) | 26.5 (19.4; 6) | 29.3 (20.8; 3) | 29.3 |
| LB | F1 | 20.0 (14.9; 9) | 21.1 (14.9; 7) | 23.7 (16.1; 3) | 23.7 |
| LB | H | 20.2 (15.7; 9) | 21.9 (17.1; 7) | 23.6 (17.5; 3) | 23.6 |
| LB | H+R | 19.6 (15.7; 8) | 21.3 (17.1; 6) | 23.7 (18.0; 2) | 23.7 |
| LB | G | | | | 25.2 (18.4; 3) |

Mean errors are within about 4 points of zero for L1 and LP in every cut; LB runs 2 to 6 points too Democratic, and G
3 to 7 (as the generic ballot did in odd-year governor races).

**What drives it**

- **Single races dominate.** ND 1992 (Conrad, the state's sitting senator, lean R+23 from the 1992 presidential vote)
  misses by 38 to 49 under every L1 and LP cell; alone it is 110 to 180 of the 320 to 430 of mean squared error
  (L1 F1, L1 H, LP H). Others above 20 under most cells: AL 2017 (Moore), MA 2010 (Brown), TX 1993, NH 1975. These are candidate
  effects no lean or environment here carries.
- **The environments.** Under L1, F1 (midterm-like everywhere) has the lowest error on all 13 and the 1989-on cut; H
  and H+R come out level with F1 from 2008 and behind it before (the pre-2008 m is fitted out of time order). N is the
  worst environment in every lean and cut. The index term moves H+R by -1.8 to +7.5 on the four 1989-2007 races; it
  helps TX 1993 (error -20 to -11) and hurts OR 1996 (-17 to -24).
- **G** is behind F1, H and H+R on its 6 races under every lean (16.3 against 14.1 to 14.7 under L1), and too
  Democratic on average.
- **The leans.** L1 and LP differ on 6 specials. LP is closer on VT 1972, NH 1975 and OR 1996 under most
  environments, farther on VT 1972 under H (Stafford's own race made L1's R+49 lean nearly right). LB is worst from
  2008 because midterm House votes with uncontested seats give extreme leans: Massachusetts 2006 (10 seats) gives
  D+70, so MA 2010 misses by 51 under LB and H.
- With 13 races, and 6 from 2008, differences of a point or two between cells are well inside the noise.

**Coverage** (SD 10.7; races inside the interval, of 13; normal / t(3.9))

| Lean | Env | 50% | 80% | 95% |
|---|---|---|---|---|
| L1 | N | 4 / 3 | 7 / 7 | 8 / 8 |
| L1 | F1 | 6 / 5 | 7 / 7 | 9 / 9 |
| L1 | H | 4 / 4 | 6 / 6 | 10 / 10 |
| L1 | H+R | 3 / 3 | 7 / 6 | 9 / 9 |
| L1 | G (of 6) | 2 / 2 | 3 / 3 | 4 / 4 |
| LP | H | 7 / 6 | 8 / 7 | 10 / 10 |
| LB | H | 3 / 2 | 8 / 8 | 10 / 10 |

The borrowed SD is too narrow for Senate specials: the 95% intervals hold 8 to 10 of 13, about what an SD near 18 to
20 would give. Errors here are about twice the frozen Senate prior's in-cycle error.

**Runoff set (diagnostic, 7 races; G on 6)**: RMSE from 7.0 (LP and G) and 9.4 (LP and N) to 22.5 (L1 and H+R).
Every cell's mean error is positive (Democrats beat the forecast by 0.5 to 13.5); Louisiana's runoffs (2002, 2014)
carry the largest misses under L1, whose midterm leans there come from House races with 6 or 7 seats. Not scored into
anything.

**No decision** (rule 9). What the Senate branch of the single-race path uses (checklist c) is the owner's call.
