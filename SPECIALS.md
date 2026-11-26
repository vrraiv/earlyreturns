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
9. **No decision at this card.** What the Senate branch of the single-race path uses (checklist c) is the owner's
   call after the report. A diagnostic never rescues anything, and any candidate suggested by these results is
   declared as such wherever it is used later.

**Live case.** The list carries a Minnesota special scheduled for November 2, 2027 (Amy Klobuchar's seat). That is
on an odd-year November date, so it is in scope for the path this card builds.
