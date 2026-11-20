/* Work plan content for planning/workplan.html.
   Card ids and checklist item ids are permanent: saved statuses, ticks and notes are keyed by them.
   Add new ids; never renumber or reuse one.
   Public file: findings quoted here come from PLAN.md, src/postmortem/README.md and the public scorecard page.
   No provisional numbers and nothing private; those belong in notes on the hosted page. */
window.PLAN = {
  version: "2026-11-20j",

  deadlines: [
    { id: "primaries", label: "Primaries model, first version", date: "2027-05-31", display: "May 2027", note: "Decided 2026-11-20 (PP-1): the track goes ahead, both parties." },
    { id: "models", label: "Electoral college and every other model frozen", date: "2028-05-31", display: "May 2028", note: "House, Senate, governors and special elections included." },
    { id: "election", label: "Election Day", date: "2028-11-07", display: "November 7, 2028", note: "Final forecast frozen before polls close." }
  ],

  events: [
    { when: "December 2026", phase: "p1", text: "Certification ends. California certifies last." },
    { when: "Through 2027", phase: "any", text: "Special elections, as they are called." },
    { when: "May 2027", phase: "p3", text: "Deadline: first primaries model.", deadline: true },
    { when: "Fall 2027", phase: "p4", text: "Governor races in Kentucky, Louisiana and Mississippi." },
    { when: "Early 2028", phase: "p4", text: "First primaries and caucuses. The order of states is not set yet." },
    { when: "May 2028", phase: "p4", text: "Deadline: electoral college model and every other model frozen.", deadline: true },
    { when: "Summer 2028", phase: "p5", text: "Conventions. The nominees are known." },
    { when: "November 7, 2028", phase: "p5", text: "Election Day." }
  ],

  phases: [
    { id: "p1", name: "Close out 2026", when: "Now, until the scorecard is final", note: "Counting and certification run into December 2026." },
    { id: "p2", name: "Decide", when: "After the scorecard is final", note: "Lessons, the brainstorm, and the choices that shape everything after." },
    { id: "p3", name: "Primaries build", when: "To May 2027", note: "Decided 2026-11-20: the track goes ahead, both parties." },
    { id: "p4", name: "Build and backtest", when: "Through 2027 to May 2028", note: "Every model designed, tested on history and frozen." },
    { id: "p5", name: "2028 season", when: "May to November 2028", note: "Frozen models running on live polls." },
    { id: "any", name: "Any time", when: "No fixed date", note: "Work that waits on outside events, such as a special election being called." }
  ],

  rules: [
    { title: "The frozen 2026 forecast is never changed.", text: "`data/final` and the `final-forecast-2026` tag stay as they are. A change to shared code is checked by rebuilding the frozen forecast and comparing." },
    { title: "Every parameter is estimated, and the evidence is shown.", text: "No assumed constants. Each one comes with its backtest and a sensitivity check." },
    { title: "A change is adopted only if it passes a test set in advance.", text: "Out of sample on history first. 2026 is a held-out check, scored once per change." },
    { title: "2026 governor results stay unscored until the governor design is frozen.", text: "That keeps 2026 a true out-of-sample test for the governors model." },
    { title: "Scorecard numbers are provisional until counting ends.", text: "Nothing built on them is final before then." },
    { title: "Plan changes and forecast changes never share a commit.", text: "Changes reach main through a pull request." },
    { title: "No manual live-results tools.", text: "Only an automatic results feed is worth building." },
    { title: "Sources that ask not to be copied are linked, not committed.", text: "The Downballot, and any source with the same terms: raw copies live in a gitignored store, only derived tables are committed, each use is cited in DATA.md, and the site links to the source's own page where it would otherwise link to our data (OP-8)." }
  ],

  tracks: [
    {
      id: "lessons", code: "SC", name: "Scorecard close-out and lessons", short: "Scorecard and lessons",
      goal: "Finish scoring 2026, write down what it taught us, and decide which changes are worth testing.",
      doneWhen: "The scorecard is final, the lessons are written up, and every candidate change has a yes, a no or a test attached.",
      deadline: "",
      cards: [
        { id: "SC-1", title: "Finish the scorecard", kind: "story", phase: "p1", base: "doing",
          why: "Every later decision leans on these numbers, and they are provisional until counting ends.",
          details: [
            "The daily refresh runs until every race is settled. Certification runs into December, and California certifies last.",
            "Scores use settled counts only. States that count mail ballots for weeks need the count to hold for 7 days.",
            "Alaska's Senate race needs its final ranked-choice round before it can settle.",
            "States with no scripted official source use Wikipedia margins, checked against a second source when a run flags them."
          ],
          checklist: [
            { id: "a", text: "All 35 Senate races settled" },
            { id: "b", text: "All contested House districts settled" },
            { id: "c", text: "Official counts loaded wherever a source exists" },
            { id: "d", text: "Provisional label removed from the site" },
            { id: "e", text: "Final scorecard tagged in git" }
          ],
          refs: ["src/run_scorecard.py", "src/check_scorecard.py", ".github/workflows/scorecard.yml", "data/scorecard"] },
        { id: "SC-2", title: "Rerun the post-mortem on final results", kind: "story", phase: "p1", needs: ["SC-1"],
          why: "The four post-mortem analyses were run on early counts and are marked provisional.",
          details: [
            "Four scripts: the what-if environment, where the House upsets fell, how unusual 2026 was, and the shared state-level error.",
            "Rerun all four on final results, then update the findings and note what changed."
          ],
          checklist: [
            { id: "a", text: "`whatif_environment.py` rerun" },
            { id: "b", text: "`house_2026_breakdown.py` rerun" },
            { id: "c", text: "`history_context.py` rerun" },
            { id: "d", text: "`state_error.py` rerun" },
            { id: "e", text: "README findings updated, with what changed" }
          ],
          refs: ["src/postmortem/README.md", "data/postmortem"] },
        { id: "SC-3", title: "Error split by chamber, in Brier and in margin", kind: "story", phase: "p1", needs: ["SC-1"],
          why: "The Brier split and the margin split tell different stories, and a model change should answer to both.",
          details: [
            "Compute each chamber's error split two ways: in Brier terms, as the scorecard page does, and in squared-margin terms.",
            "The two can disagree. Brier only rewards flipped winners, so a large shared shift on races the forecast already had right adds little to it.",
            "Test whether House residuals cluster by state after the national, region and slope layers. Use a permutation test and name the outliers.",
            "Keep four explanations apart: a state shock, demographic swing, wrong lean on redrawn lines, and too much weight on a stale lean prior.",
            "Same-state correlation changes seat ranges and joint outcomes. It does not change per-race Brier by itself."
          ],
          checklist: [
            { id: "a", text: "Both splits computed on final counts, for all three versions" },
            { id: "b", text: "State-clustering test rerun on final counts" },
            { id: "c", text: "Largest district misses listed with poll count, prior and lean" },
            { id: "d", text: "Written into the lessons list" }
          ],
          refs: ["src/model/scorecard_margins.py", "data/scorecard/scorecard.json"] },
        { id: "SC-4", title: "Write the lessons list", kind: "story", phase: "p2", needs: ["SC-2", "SC-3"],
          why: "One page of lessons, each tied to evidence, is the input to the brainstorm.",
          details: [
            "Starting points, from the provisional findings in the post-mortem README and on the scorecard page:",
            "One national draw can't fit both chambers. House districts moved more than Senate races.",
            "House upsets all went one way, concentrated in modestly Republican seats held by Republican incumbents.",
            "Districts in the same state share an error the model left out.",
            "The environment sat outside the range the fundamentals were trained on.",
            "Race-level spreads: check each layer's interval coverage, and whether each layer was needed at all.",
            "One poll source was not enough. The poll audit found gaps.",
            "How the bias-adjusted version scored against face value."
          ],
          checklist: [
            { id: "a", text: "Each lesson has a number and a source file" },
            { id: "b", text: "Each lesson names the track it feeds" },
            { id: "c", text: "Draft handed to the post-mortem page (SI-4)" }
          ],
          refs: ["src/postmortem/README.md"] },
        { id: "SC-5", title: "Brainstorm: what to add to the model", kind: "session", phase: "p2", needs: ["SC-4"],
          why: "A wide list first, then a shortlist with a test for each idea.",
          details: [
            "Collect candidates on the Ideas page before and during the session.",
            "Start from the four candidate changes in the post-mortem README and the ideas already logged.",
            "For each idea: what it would fix, what data it needs, how it would be tested, and what it costs.",
            "Sort every idea into shortlist, park or drop."
          ],
          checklist: [
            { id: "a", text: "Ideas collected on the Ideas page" },
            { id: "b", text: "Session held" },
            { id: "c", text: "Each shortlisted idea has a test written down" },
            { id: "d", text: "Shortlist turned into cards in the rework and data tracks" }
          ] },
        { id: "SC-6", title: "Which changes go forward", kind: "decision", phase: "p2", needs: ["SC-5"],
          why: "The brainstorm ends in a list of yes, no and test-first, not a wish list.",
          details: [
            "Rule: a change is adopted only if it beats the current model out of sample on history, with 2026 as a held-out check.",
            "Record a yes, a no or a test-first for each candidate, with one line of reasoning."
          ] }
      ]
    },

    {
      id: "rework", code: "CM", name: "House and Senate model rework", short: "House and Senate",
      goal: "Carry the House and Senate models to 2028 with the changes that pass their tests.",
      doneWhen: "A frozen design, backtested on history with 2026 held out, running on the 2028 seats and districts.",
      deadline: "May 2028",
      cards: [
        { id: "CM-1", title: "Backtest harness for the whole model", kind: "story", phase: "p2",
          why: "Each candidate change needs the same out-of-sample test, set before looking at the answer.",
          details: [
            "Today's backtest covers the Senate and the generic ballot in 2018 and 2022. Extend it to House districts and to 2006 through 2024.",
            "Each cycle is forecast with parameters fitted on earlier data only.",
            "Scores: Brier, log loss, margin error, interval coverage and seat-count coverage.",
            "2026 stays out of every fit and is scored once per change.",
            "Governors go through the same harness, with the office as a setting. The first governor model already has its own backtest on 353 races; its scores become the governor baseline that GV-3 tries to beat.",
            "Mostly implementation. The one decision is the adoption rule, and it is written after the baseline: the baseline scores, and how much they move by chance from cycle to cycle, set how large a gain has to be. It is still fixed before any candidate change is scored.",
            "Built 2026-11-20: `src/model/backtest_asof.py`, written up in BACKTEST.md with the baseline scores and the adoption rule. The three-cycle burn-in is confirmed. The adoption rule was confirmed after the baseline and its chance analysis: a gain has to exceed 0.005 and its own standard deviation over redrawn cycles (BACKTEST.md, \"How much a score moves by chance\"). Governors use the same rule without the count of cycles.",
            "The start was reassessed against the data now in hand. Polls with results begin in 1998, so both chambers and the national environment are scored from 2004 (three earlier cycles to fit on) to 2024: 11 cycles.",
            "House districts for 1998 to 2004 come from Gary Jacobson's House elections file, which arrived the same day (DA-3). It is used with credit to him and is not in the repo, so a clone without it scores the House from 2012 only. Districts from 2006 stay on `house_history.csv`.",
            "The polls now set the start, not district lean. Jacobson's file runs back to 1946, but fitting on years before 1998 is DA-2's and CM-4's question.",
            "Governors are in the harness: the first governor model re-estimated as of each cycle, even years 2004 to 2024, 239 races. Odd years and 2025 stay in `governor_model.py`'s own backtest. GV-3 built their environment as of each date and tested it on the prior alone; putting the odd-year races themselves through the harness is not done.",
            "Still to build: scoring 2026. The 2026 polls and results have to be put in the harness's shape, and that waits for the final scorecard (SC-1)."
          ],
          checklist: [
            { id: "a", text: "House districts in the backtest" },
            { id: "b", text: "Cycles extended back to 2006" },
            { id: "e", text: "Governors in the harness" },
            { id: "d", text: "Baseline scores recorded for the current model, governors included" },
            { id: "c", text: "Adoption rule written down, before any candidate change is scored" }
          ],
          refs: ["BACKTEST.md", "src/model/backtest_asof.py", "src/model/backtest.py", "src/model/house_structure.py", "src/model/governor_model.py"] },
        { id: "CM-2", title: "State-level House error and a carried state intercept", kind: "story", phase: "p4", needs: ["CM-1", "SC-6"],
          why: "History shows a shared state shock of about 3.3 points that the model left out.",
          details: [
            "Adds a state layer between the region and the district.",
            "Carrying 0.4 of a state's last shock forward cut the state-shock error by 18% out of sample.",
            "It widens seat ranges and changes joint outcomes more than single-race odds.",
            "Only weakly shared with the same state's Senate and governor races."
          ],
          checklist: [
            { id: "a", text: "State shock estimated without the test cycle" },
            { id: "b", text: "Carried intercept tested" },
            { id: "c", text: "Seat-range coverage compared with the current model" },
            { id: "d", text: "Adopt or drop recorded" }
          ],
          refs: ["src/postmortem/state_error.py", "src/model/error_structure.py"] },
        { id: "CM-3", title: "National errors grouped by what was measured", kind: "story", phase: "p4", needs: ["CM-1", "SC-6"],
          why: "The model drew one national error for both chambers. Historically the two correlate at about 0.5.",
          details: [
            "Two national factors: statewide polls (Senate, governor, president by state) and the generic ballot with district structure.",
            "Changes joint outcomes, such as the chance of winning both chambers, not single-race odds.",
            "The governors model already uses this structure."
          ],
          checklist: [
            { id: "a", text: "Correlation estimated with 2026 added" },
            { id: "b", text: "Joint House and Senate outcomes compared with history" },
            { id: "c", text: "Adopt or drop recorded" }
          ],
          refs: ["src/model/governor_model.py", "src/postmortem/history_context.py"] },
        { id: "CM-4", title: "Wave response and year type", kind: "story", phase: "p4", needs: ["CM-1", "DA-2"],
          why: "In wave years, near-even districts move further than a straight swing, and the type of year may matter.",
          details: [
            "The post-mortem found 1 to 2 extra points in near-even and modestly opposed districts in wave years.",
            "Test year type (midterm or presidential, and the president's party) as an interaction term, not by picking analog years.",
            "The pull of lean and incumbency has drifted over time, so older or same-type years can't simply be pooled.",
            "Split incumbency by whether the incumbent is in the president's party.",
            "Needs more midterms than 2006 to 2024 offers."
          ],
          checklist: [
            { id: "a", text: "Year-type test on the national series" },
            { id: "b", text: "Interaction terms tested on the district history" },
            { id: "c", text: "Adopt or drop recorded" }
          ],
          refs: ["src/model/house_structure.py", "src/postmortem/state_error.py"] },
        { id: "CM-5", title: "Demographic covariates in the district prior", kind: "story", phase: "p4", needs: ["CM-1", "DA-4"],
          why: "Some of the largest district misses may be demographic swing that lean alone can't see.",
          details: [
            "Test education, race and ethnicity, age and urban share as shifts to the district prior.",
            "Compare against the state shock. Covariates move the expected margin. A shock only widens the joint spread.",
            "Also test a lower weight on the lean prior where the lean is stale, as on newly drawn lines."
          ],
          checklist: [
            { id: "a", text: "Covariates joined to the district history" },
            { id: "b", text: "Out-of-sample test against the lean-only prior" },
            { id: "c", text: "Stale-lean weight tested" },
            { id: "d", text: "Adopt or drop recorded" }
          ] },
        { id: "CM-6", title: "Re-estimate the error layers with 2026 added", kind: "story", phase: "p4", needs: ["SC-1", "CM-1"],
          why: "2026 adds one national draw, four region shocks and a few hundred race-level errors.",
          details: [
            "Re-estimate each layer's spread and tail shape.",
            "Report whether each layer was needed, not only whether it was fitted correctly.",
            "Race-level tails: check whether pooling thinly polled and well-polled races fattens them.",
            "Test a wider national spread when the fundamentals inputs leave their training range."
          ],
          checklist: [
            { id: "a", text: "Layer estimates updated" },
            { id: "b", text: "Interval coverage by layer reported" },
            { id: "c", text: "Tail shape chosen by out-of-sample log score" }
          ],
          refs: ["src/model/error_structure.py", "src/model/calibrate.py"] },
        { id: "CM-7", title: "Bias adjustment: keep, change or retire", kind: "decision", phase: "p4", needs: ["SC-1"],
          why: "2026 is one more cycle of evidence on whether adjusting the polls pays.",
          details: [
            "Rerun the real-time tests with 2026 added.",
            "Decide whether 2028 publishes a face-value version and an adjusted one, or a single version."
          ],
          refs: ["src/model/bias_realtime.py", "src/model/bias_decay.py"] },
        { id: "CM-8", title: "One simulation for president, Senate, House and governors", kind: "story", phase: "p4", needs: ["CM-3", "EC-1"],
          why: "In 2028 every office shares a ballot, so the national and state errors have to be drawn together.",
          details: [
            "Shared draws: the national factors, the state layer and the regions.",
            "New output: the chance of each combination of presidency, Senate and House.",
            "The House environment in a presidential year comes from the presidential race and the generic ballot together."
          ],
          checklist: [
            { id: "a", text: "Shared draws designed" },
            { id: "b", text: "Joint outcomes checked against 2008 to 2024" },
            { id: "c", text: "Explorer data format extended" }
          ],
          refs: ["src/model/forecast.py"] },
        { id: "CM-9", title: "2028 seats, districts and candidates", kind: "story", phase: "p4", needs: ["OP-1"],
          why: "The collectors and race lists are built around the 2026 map.",
          details: [
            "Senate: the class 3 seats, plus any specials.",
            "House: districts on the lines in force, with lean rebuilt where lines changed.",
            "Candidates and incumbents collected as nominees are chosen.",
            "Lean on new lines: The Downballot's presidential results by district for each map since 2006, with predecessor-district versions and its 2010s and 2020s redistribution analyses (store-and-link, OP-8)."
          ],
          checklist: [
            { id: "a", text: "Senate race list for 2028" },
            { id: "b", text: "House race list on the lines in force" },
            { id: "c", text: "Candidate collectors pointed at the 2028 pages" }
          ],
          refs: ["src/collect"] },
        { id: "CM-10", title: "Design freeze", kind: "milestone", phase: "p4", due: "May 2028", needs: ["CM-2", "CM-3", "CM-4", "CM-5", "CM-6", "CM-7", "CM-8", "CM-9"],
          why: "After this the model only takes in new data.",
          details: [
            "Every adopted change merged.",
            "Backtest table published on the site.",
            "Parameters frozen for the season."
          ] }
      ]
    },

    {
      id: "data", code: "DA", name: "Data decisions and collection", short: "Data",
      goal: "Decide what extra data is worth collecting, then collect it with sources and licences recorded.",
      doneWhen: "Every dataset a model needs is in the repo or written off as unobtainable, and DATA.md lists it.",
      deadline: "",
      cards: [
        { id: "DA-1", title: "What to collect", kind: "decision", phase: "p2", needs: ["SC-5"],
          why: "Each dataset costs time, so each one should answer a named question.",
          details: [
            "District results before 2006: more midterms for the year-type and wave tests.",
            "District lean before 2006: presidential vote by district.",
            "Census demographics by district and state.",
            "Primary polls, results, calendars and delegate rules.",
            "Senate special elections, and polls of past specials.",
            "Who drew each state's map, by cycle.",
            "For each: the question it answers, the source and licence, the hours to collect, and what is lost by skipping it.",
            "The Downballot's data page (the-downballot.com/p/data) has a start on several of these; each card below says which. Its terms: free use with a citation and a link, no reproducing whole spreadsheets, so it follows the store-and-link rule (OP-8).",
            "Availability checked on 2026-11-20. What to keep is still decided here, after the brainstorm.",
            "District results before 2006: in the repo for 1976 to 2018 (MIT Election Lab). The lab's current file, to 2024, needs a sign-in form that you would fill in. 1946 to 1974 exist only as saved Wikipedia pages, not yet parsed.",
            "District lean before 2006: a public file has the presidential vote in every district for 1952 to 2004 (Broockman 2009, public domain), but without district labels. A trial on 2000 matched three in four contested districts on the House vote alone. Proving the match is DA-2. Since then Gary Jacobson has sent his file (DA-3), which has the lean with district labels for 1952 to 2024, so the matching is no longer needed.",
            "Census demographics: The Downballot's district tables for 2016 to 2022 are fetched. Anything earlier needs the Census key.",
            "Primaries: 538's primary polls for 2020 and 2024 are in the repo. Earlier polls, results by state and date, and delegate rules are not collected.",
            "Senate specials: results with a special-election flag are in the repo for 1976 to 2024 (MIT Election Lab). Polls of past specials sit in 538's late-polls file, to be picked out with that flag.",
            "Who drew each map: one search found boundary files but no table of who drew them. Assume hand work (DA-7)."
          ],
          refs: ["DATA.md", "data/raw/medsl", "data/raw/broockman_2009"] },
        { id: "DA-2", title: "House district history before 2006", kind: "story", phase: "p2", needs: ["DA-1"],
          why: "Six midterms can't separate the type of year from the drift over time.",
          details: [
            "Stage 1: test year-type questions on the national series, which already runs from 1946.",
            "Stage 2: districts back to 1976, using the MIT Election Lab House returns plus a lean source.",
            "Stage 3: the 1950s, only if a district presidential vote file arrives (DA-3).",
            "Wikipedia's House pages before 2006 carry no district lean, so even 1998 and 2002 need a second source.",
            "Older years only help if coefficients are allowed to drift over time. Pooling them would hurt.",
            "The Downballot's presidential results by district start with 2008, so the years before 2006 still rest on the authors' files (DA-3).",
            "Update 2026-11-20: the MIT House returns for 1976 to 2018 are in the repo, and so is a public file of district presidential vote for 1952 to 2004 without district labels (see DA-1). If its rows can be matched to districts on the House vote, stages 2 and 3 no longer wait for the authors.",
            "Update, later on 2026-11-20: Gary Jacobson's file arrived (DA-3). It has House vote, incumbency and district presidential vote by labelled district for 1946 to 2024, and agrees with `house_history.csv` on 2006 to 2024 (margins to a median of 0.04 points). It is the lean source for stages 2 and 3. Two limits: in a presidential year after a redistricting (1972, 1992, 2012) it has no lean known before the election, and the 1960s are patchy. It is not ours to redistribute, so an extended `house_history.csv` could not be committed with his values in it; the backtest (CM-1) reads his file directly for 1998 to 2004."
          ],
          checklist: [
            { id: "a", text: "National-series test done" },
            { id: "b", text: "MIT returns loaded and checked against 2006 to 2024" },
            { id: "c", text: "Lean source chosen" },
            { id: "d", text: "`house_history.csv` extended" },
            { id: "e", text: "DATA.md updated" }
          ],
          refs: ["src/model/house_structure.py", "data/interim/house_history.csv"] },
        { id: "DA-3", title: "Ask authors for district presidential vote files", kind: "story", phase: "p1",
          why: "The best lean sources have no public download, and a reply can take weeks.",
          details: [
            "Kiernan Park-Egan: presidential results by congressional district, 1952 to 2024, published as maps.",
            "Gary Jacobson: House elections data from 1946, with district presidential vote, incumbency and challenger quality.",
            "Ask about format, coverage, how redistricting is handled, and terms of reuse.",
            "You send these. Claude can draft them.",
            "Jacobson replied on 2026-11-20 with the file: one row per district and election, 1946 to 2024, with a codebook. Presidential vote is recalculated for new districts; the previous House vote is not. Terms: use it and cite him as the source. He did not give leave to redistribute, so the file is kept out of the repo and only results derived from it are published."
          ],
          checklist: [
            { id: "a", text: "Request drafted" },
            { id: "b", text: "Sent to Park-Egan" },
            { id: "c", text: "Sent to Jacobson" },
            { id: "d", text: "Replies logged, with terms of use" }
          ] },
        { id: "DA-4", title: "Census demographics by district and state", kind: "story", phase: "p4", needs: ["DA-1"],
          why: "Needed to test whether demographic swing explains district and state misses.",
          details: [
            "Education, race and ethnicity, age, income and urban share.",
            "By congressional district on the lines in force each cycle, and by state.",
            "Needs a free Census API key, which you create.",
            "Decide how far back to go. District tables from the yearly survey start in the mid-2000s.",
            "A start without the Census: The Downballot publishes education and income, race by age and citizenship, and urban-rural classifications by district for 2016 to 2022 (store-and-link, OP-8)."
          ],
          checklist: [
            { id: "a", text: "API key in `.env`" },
            { id: "b", text: "Collector written" },
            { id: "c", text: "Districts matched to the lines in force, by cycle" },
            { id: "d", text: "DATA.md updated" }
          ] },
        { id: "DA-5", title: "Presidential polls and results by state", kind: "story", phase: "p2",
          why: "The electoral college model and its backtest are built on these.",
          details: [
            "Split out of DA-1 on 2026-11-20: the electoral college model needs this whatever the 2026 lessons say, so it does not wait for the brainstorm.",
            "Done on 2026-11-20.",
            "State results: every state from 1828 to 2024, built from The Downballot's vote counts (store-and-link, OP-8).",
            "State and national polls: whole cycles from 2004 to 2024 and the final two months of 2000, with the sources cross-checked poll by poll.",
            "National polls by day: 17 cycles from 1952 to 2016, from Jennings and Wlezien, checked on every run against Erikson and Wlezien's original file.",
            "Limits: whole-cycle state polls start in 2004, and the daily national series stops at 2016."
          ],
          checklist: [
            { id: "a", text: "Coverage table by cycle and state" },
            { id: "b", text: "State poll history assembled" },
            { id: "c", text: "National poll history assembled" }
          ],
          refs: ["data/interim/state_presidential_history.csv", "data/interim/president_general_polls.csv", "data/interim/president_national_poll_days.csv", "data/interim/president_poll_coverage.csv", "src/collect/pres_polls_crosscheck.py"] },
        { id: "DA-6", title: "Primary polls, results and rules", kind: "story", phase: "p3", needs: ["PP-1"],
          why: "The primaries track can't start without them.",
          details: [
            "Past cycles: national and state primary polls, results by state and date, and delegate rules.",
            "2028: a source for primary polls, checked for coverage.",
            "The 2028 calendar is not set. Collect it when each party publishes it.",
            "The Downballot's primary and filing-deadline calendars cover 2018 to 2026 and will carry 2028 once it is set. It has no presidential primary polls or state results."
          ],
          checklist: [
            { id: "a", text: "Past primary polls collected" },
            { id: "b", text: "Past results by state and date collected" },
            { id: "c", text: "Delegate rules by party and cycle" },
            { id: "d", text: "2028 poll source chosen" }
          ] },
        { id: "DA-7", title: "Map type by state and cycle", kind: "story", phase: "p4", optional: true,
          why: "Tests whether the state shock or the wave response is larger under partisan maps.",
          details: [
            "Who drew each congressional map: a legislature, a commission or a court.",
            "Manual work, checked by hand."
          ],
          refs: ["src/postmortem/state_error.py"] },
        { id: "DA-8", title: "Sources and licences kept current", kind: "story", phase: "any",
          why: "The data catalogue is public, and derived data carries a licence.",
          details: [
            "Each new source goes into DATA.md with its licence before its data is committed.",
            "Sources whose terms ask that whole tables not be reproduced follow the store-and-link rule (OP-8): raw copies gitignored, derived tables committed, the site linking to the source."
          ],
          refs: ["DATA.md", "LICENSE-DATA.md"] }
      ]
    },

    {
      id: "site", code: "SI", name: "Site: 2026 archive and 2028 preview", short: "Site",
      goal: "Fold 2026 into a compact archive with its scorecard, and turn the front page toward 2028.",
      doneWhen: "The front page previews 2028 and shows development results. The 2026 forecast and scorecard sit in one archived section, with old links intact.",
      deadline: "",
      cards: [
        { id: "SI-1", title: "Name, address and structure", kind: "decision", phase: "p2",
          why: "The site and the repo are both named for 2026.",
          details: [
            "Decide whether 2028 gets a new address, a new repo, or a section of this one.",
            "Old links to the 2026 forecast should keep working.",
            "Decide the top-level sections: 2028 preview, development results, 2026 archive, election data.",
            "Plan for a repeating cycle: forecast, scorecard, post-mortem, then archive. The 2030 midterms follow 2028, so the structure should take one archived section per election without a redesign."
          ] },
        { id: "SI-2", title: "Archive the 2026 forecast", kind: "story", phase: "p2", needs: ["SC-1", "SI-1"],
          why: "The forecast is history now and should read as a record, not a live page.",
          details: [
            "One compact section: the final forecast as locked, the scorecard and the post-mortem.",
            "The frozen forecast data is shown unchanged. The build already checks it against the final.",
            "Keep the lock label and timestamp.",
            "Trim the parts that only mattered before the election."
          ],
          checklist: [
            { id: "a", text: "Archive layout sketched" },
            { id: "b", text: "Forecast data verified identical to `data/final`" },
            { id: "c", text: "Scorecard marked final" },
            { id: "d", text: "Old links still load" }
          ],
          refs: ["src/site/build.py", "src/site/template.html", "data/final"] },
        { id: "SI-3", title: "2028 preview front page", kind: "story", phase: "p2", needs: ["SI-1"],
          why: "The landing page should say what is coming, not what is over.",
          details: [
            "What is being built and when: the tracks and the two deadlines.",
            "Key 2028 dates as they become known.",
            "The latest development results, each labeled as work in progress.",
            "No forecast numbers until a model is frozen."
          ],
          checklist: [
            { id: "a", text: "Layout sketched" },
            { id: "b", text: "Copy written" },
            { id: "c", text: "Live on the site" }
          ] },
        { id: "SI-4", title: "2026 post-mortem page", kind: "story", phase: "p2", needs: ["SC-4"],
          why: "The lessons should be public and in plain terms.",
          details: [
            "What the forecast got right and wrong, drawn from the lessons list.",
            "Final numbers only."
          ],
          refs: ["src/postmortem/README.md"] },
        { id: "SI-5", title: "Development results pages", kind: "story", phase: "p4", needs: ["SI-6"],
          why: "Each model earns its place by showing its backtest.",
          details: [
            "One page per model as its backtest lands: governors, special elections, electoral college, primaries.",
            "Each shows the backtest table, what was estimated, and how sensitive the result is."
          ] },
        { id: "SI-6", title: "Split the template and the build", kind: "story", phase: "p2", needs: ["SI-1"],
          why: "The site is one large template built for one election.",
          details: [
            "Split it so the archive, the preview and each model page build separately.",
            "Build the archive to scale: each election is one unit holding its locked forecast, scorecard and post-mortem.",
            "Folding in the next election should mean adding its data, not writing a new template. 2026 is the first unit, then 2028, then the 2030 midterms.",
            "Keep the checks that the archived forecast matches the final."
          ],
          refs: ["src/site/template.html", "src/site/build.py", "src/site/history.py"] },
        { id: "SI-7", title: "2028 forecast pages", kind: "story", phase: "p5", needs: ["CM-10", "EC-9"],
          why: "The season needs pages for each office and for the map.",
          details: [
            "President and the electoral college map, Senate, House and governors.",
            "The what-if explorer extended to the electoral college."
          ] },
        { id: "SI-8", title: "Election data pages", kind: "story", phase: "p1", base: "doing",
          why: "The historical pages are built and need 2026 once it is final.",
          details: [
            "Built in November 2026: vote shares over time, approval and incumbency, states and regions, polling accuracy, off-cycle elections, and sources."
          ],
          checklist: [
            { id: "a", text: "Pages built and live", done: true },
            { id: "b", text: "Final 2026 results added" }
          ],
          refs: ["src/site/history.py", "DATA.md"] }
      ]
    },

    {
      id: "college", code: "EC", name: "Electoral college model", short: "Electoral college",
      goal: "A presidential forecast by state, simulated through to electoral votes.",
      doneWhen: "Backtested on 2008 to 2024, frozen by May 2028, and running on 2028 polls.",
      deadline: "May 2028",
      cards: [
        { id: "EC-1", title: "Design note", kind: "story", phase: "p2",
          why: "The presidential race is the one office the 2026 code has never forecast.",
          details: [
            "State margin from state lean, the national environment and state polls, as in the Senate model.",
            "Error layers: national, region and state. The statewide-poll factor is shared with Senate and governor races.",
            "Maine and Nebraska award some votes by district.",
            "Outputs: win probability, the electoral vote range, the tipping-point state, the chance that the popular vote and the electoral college split, and the chance of a tie."
          ],
          checklist: [
            { id: "a", text: "Design note written" },
            { id: "b", text: "Open questions listed" },
            { id: "c", text: "Checked against the lessons list" }
          ] },
        { id: "EC-2", title: "Presidential poll average", kind: "story", phase: "p4", needs: ["EC-1", "DA-5"],
          why: "The Senate poll average needs to handle national and state presidential polls.",
          details: [
            "Recency, sample size, pollster effects and voter-population adjustments, as for the Senate.",
            "Check that pollster effects estimated on Senate and generic-ballot polls hold for presidential polls."
          ],
          refs: ["src/model/pollavg.py", "src/model/pollster_effects.py"] },
        { id: "EC-3", title: "Presidential fundamentals", kind: "story", phase: "p4", needs: ["EC-1"],
          why: "Polls are thin early, and 2028 is an open seat.",
          details: [
            "Candidates: approval of the outgoing president, the economy, and time in office.",
            "There are few elections to fit on. Show the leave-one-out error and how far the choice of predictors moves the answer."
          ],
          refs: ["src/model/fundamentals.py"] },
        { id: "EC-4", title: "State prior and weight on polls", kind: "story", phase: "p4", needs: ["EC-1", "DA-5"],
          why: "Thinly polled states lean on the prior.",
          details: [
            "Lean from past presidential results.",
            "The weight on polls is estimated from history, as it was for the Senate."
          ],
          refs: ["src/model/prior_weight.py"] },
        { id: "EC-5", title: "How state errors move together", kind: "story", phase: "p4", needs: ["EC-1", "DA-5"],
          why: "The electoral college is decided by correlated misses in a handful of states.",
          details: [
            "Estimate national, regional and state-level components from past presidential polling misses.",
            "Test demographic similarity between states against plain regions."
          ],
          refs: ["src/model/error_structure.py"] },
        { id: "EC-6", title: "Simulation and outputs", kind: "story", phase: "p4", needs: ["EC-4", "EC-5"],
          why: "State odds only become a forecast once they are added up to 270.",
          details: [
            "538 electoral votes, 270 to win.",
            "Maine's and Nebraska's districts are simulated as their own races.",
            "A 269 to 269 tie is reported as its own outcome."
          ] },
        { id: "EC-7", title: "Backtest, 2008 to 2024", kind: "story", phase: "p4", needs: ["EC-2", "EC-3", "EC-6"],
          why: "Five elections is a small sample, so the backtest has to be read with care.",
          details: [
            "Each election forecast with only what was known then.",
            "Score the states (Brier and log loss), the winner, the electoral vote range and the tipping point.",
            "Report the small sample plainly."
          ] },
        { id: "EC-8", title: "What to show before the nominees are known", kind: "decision", phase: "p4",
          why: "Nominees are unknown until mid-2028.",
          details: [
            "Options: nothing until there are nominees, a generic party matchup, or the leading candidates' matchups."
          ] },
        { id: "EC-9", title: "Design freeze", kind: "milestone", phase: "p4", due: "May 2028", needs: ["EC-7", "EC-8"],
          why: "After this the model only takes in new polls.",
          details: [
            "Backtest published on the site.",
            "Parameters frozen for the season."
          ] }
      ]
    },

    {
      id: "primaries", code: "PP", name: "Presidential primaries", short: "Primaries",
      goal: "Forecast the 2028 nomination contests in both parties. Decided 2026-11-20 (PP-1).",
      doneWhen: "A first version by May 2027, with a backtest on past contests behind it.",
      deadline: "May 2027",
      cards: [
        { id: "PP-1", title: "Go or no-go", kind: "gate", phase: "p2",
          why: "The deadline is May 2027, so this has to be decided early.",
          details: [
            "For: both parties have open contests, and it gives the site something live in 2027.",
            "Against: few past cycles to learn from, an order of states that is new and not yet set, and its own polls, rules and results data.",
            "A middle path: polling averages only, with no win probabilities."
          ] },
        { id: "PP-2", title: "Scope", kind: "decision", phase: "p2", needs: ["PP-1"],
          why: "The track can stop at three different depths.",
          details: [
            "Level 1: national and early-state polling averages.",
            "Level 2: state win probabilities, once the calendar is known.",
            "Level 3: delegate projection and nomination odds.",
            "Both parties, decided with PP-1 on 2026-11-20."
          ] },
        { id: "PP-3", title: "Polling averages", kind: "story", phase: "p3", needs: ["PP-2", "DA-6"],
          why: "The first useful output, and the base for everything else.",
          details: [
            "National and state averages per candidate, with the same pollster handling as the general-election averages.",
            "Many candidates, and a field that changes as candidates enter and withdraw."
          ],
          refs: ["src/model/pollavg.py"] },
        { id: "PP-4", title: "Calendar and rules as inputs", kind: "story", phase: "p3", needs: ["PP-2"],
          why: "The 2028 order of states is not set.",
          details: [
            "The model takes the calendar and each party's delegate rules as data, so it can be rerun when they change.",
            "Track announcements from each party."
          ] },
        { id: "PP-5", title: "State model and momentum", kind: "story", phase: "p3", needs: ["PP-3", "PP-4"],
          why: "Primaries are sequential, and early results move later states.",
          details: [
            "From national standing to state results.",
            "How early results shift later states.",
            "Withdrawals, and where a candidate's support goes."
          ] },
        { id: "PP-6", title: "Backtest on past contests", kind: "story", phase: "p3", needs: ["PP-5"],
          why: "The order differed in every past cycle, which is the property to test.",
          details: [
            "Past open contests in both parties, forecast in order with what was known before each state voted.",
            "Check that the model handles a calendar it was not fitted on."
          ] },
        { id: "PP-7", title: "Delegate simulation", kind: "story", phase: "p3", needs: ["PP-5"],
          why: "Nominations are won on delegates, not states.",
          details: [
            "Allocation rules by state and party, including viability thresholds, through to the nomination."
          ] },
        { id: "PP-8", title: "Primaries pages on the site", kind: "story", phase: "p3", needs: ["PP-3", "SI-6"],
          why: "The track is only useful once it is published.",
          details: [
            "Averages first, then state odds and delegates as each level is built."
          ] },
        { id: "PP-9", title: "First version", kind: "milestone", phase: "p3", due: "May 2027", needs: ["PP-3", "PP-6"],
          why: "The fixed date for this track.",
          details: [
            "At the least: polling averages and a backtest."
          ] }
      ]
    },

    {
      id: "specials", code: "SP", name: "Special elections", short: "Special elections",
      goal: "Forecast a single House or Senate special election whenever one is called.",
      doneWhen: "A special can be forecast within a day of being called, with a backtest behind it.",
      deadline: "No fixed date. Sooner is better.",
      cards: [
        { id: "SP-1", title: "House specials data and environment", kind: "story", phase: "p1", base: "done",
          why: "Built in November 2026.",
          details: [
            "79 House specials from 2007 to 2026, of which 77 are usable.",
            "The first half of a presidential term behaves like a midterm or stronger. The second half shows no midterm effect.",
            "A recent-specials term picks up shifts in who turns out for specials."
          ],
          refs: ["src/collect/specials.py", "src/model/special_model.py", "data/interim/house_specials.csv"] },
        { id: "SP-2", title: "Single-race forecast path", kind: "story", phase: "p1", base: "done",
          why: "Built in November 2026.",
          details: [
            "One race on one date, using only what was known before it.",
            "Tested in date order on 68 House specials from 2008 to 2026: margin error 11.5 against 13.8 for carrying the last House vote forward.",
            "Its 50, 80 and 95% intervals covered 49, 82 and 100% of results."
          ],
          refs: ["src/model/single_race.py"] },
        { id: "SP-3", title: "Senate special elections", kind: "story", phase: "any",
          why: "The single-race path covers House specials and off-cycle governors, not Senate specials.",
          details: [
            "A history like the House one: results against state lean and the environment.",
            "Few races, so borrow the House pattern and test it.",
            "Source: The Downballot's Special Elections Index, 1989 to 2022, partisan congressional and legislative specials with the district's presidential vote (store-and-link, OP-8). It also extends the House specials history back from 2007."
          ],
          checklist: [
            { id: "a", text: "Senate specials history collected" },
            { id: "b", text: "Environment pattern tested" },
            { id: "c", text: "Added to the single-race path" }
          ] },
        { id: "SP-4", title: "Polls of past specials in the backtest", kind: "story", phase: "any",
          why: "No historical special-election polls are collected, so the backtest uses the prior alone.",
          details: [
            "Collect polls for past specials.",
            "Estimate how much weight they deserve against the prior."
          ] },
        { id: "SP-5", title: "Recent specials as a signal for off-year governors", kind: "story", phase: "any",
          why: "The recent-specials term helped House specials. It has not been tested on governor races.",
          details: [
            "Test it on off-year governor races."
          ],
          refs: ["src/model/environment.py"] },
        { id: "SP-6", title: "Swap in the reworked district model", kind: "story", phase: "p4", needs: ["CM-10"],
          why: "The specials prior is the frozen 2026 House district model.",
          details: [
            "Update it when the rework lands, then rerun the backtest."
          ] },
        { id: "SP-7", title: "Runbook and page for a live special", kind: "story", phase: "any", optional: true,
          why: "Being ready early is the nice-to-have for this track.",
          details: [
            "The steps from a special being called to a published page: race details, lean on the lines in force, polls, run, publish.",
            "Decide where a special lives on the site."
          ],
          checklist: [
            { id: "a", text: "Runbook written" },
            { id: "b", text: "Page template built" },
            { id: "c", text: "Dry run on a past special" }
          ] },
        { id: "SP-8", title: "Watch list", kind: "story", phase: "any",
          why: "Specials are called on short notice.",
          details: [
            "Vacancies and scheduled specials, checked monthly.",
            "The Downballot keeps a special elections sheet for 2027 to 2028, with results as they come."
          ] }
      ]
    },

    {
      id: "governors", code: "GV", name: "Governors", short: "Governors",
      goal: "A governors forecast for 2027 and 2028, tested honestly on 2026.",
      doneWhen: "A frozen design, scored once on 2026, run live on the 2027 races, and part of the 2028 simulation.",
      deadline: "May 2028",
      cards: [
        { id: "GV-1", title: "Results history, state lean and the 2026 races", kind: "story", phase: "p1", base: "done",
          why: "Built in November 2026.",
          details: [
            "All 370 governor races from 1998 to 2025.",
            "State presidential results from 1992 to 2024.",
            "The 36 races of 2026 as they stood before the election. Results are deliberately not collected yet."
          ],
          refs: ["src/collect/governors.py", "data/interim/governor_history.csv"] },
        { id: "GV-2", title: "First model and backtest", kind: "story", phase: "p1", base: "done",
          why: "Built in November 2026.",
          details: [
            "Prior from lean, the environment and incumbency. Weight on polls of 0.84.",
            "Backtest on 353 races from 1998 to 2025: Brier 0.0772, against 0.0796 for polls alone.",
            "The environment for off-cycle races depends on the year of the presidential term."
          ],
          refs: ["src/model/governor_model.py", "src/model/environment.py"] },
        { id: "GV-3", title: "Open design questions", kind: "story", phase: "p2",
          why: "The first model leaves four questions open.",
          details: [
            "Lean: presidential lean explains little. Test a composite of recent statewide results against it.",
            "Poll average: generalize the Senate average to governors for the 2026 snapshot.",
            "Off-cycle environment for 2025, using figures as of each date.",
            "Intervals look too wide in cycles with ten or more races. Suggestive, not conclusive.",
            "Worked through 2026-11-20. Six changes were each written into BACKTEST.md before being run, then judged by the adoption rule on the as-of backtest (\"Candidates\" there has the table).",
            "Lean: presidential lean stays. A composite of recent Senate and governor results, alone or beside it, and the previous governor margin all failed.",
            "Poll average: `src/model/governor_inputs.py` builds the 2026 poll table from the final forecast's snapshot in the shape the backtest uses, with the published weighted average beside it. No results are read. A surname-matching fault in `pollavg.statewide()` was fixed on the way.",
            "Found while building it: a race with no poll in the final 21 days was forecast from the prior alone. Using its polls from 22 to 60 days out passes the rule; in the 17 past races concerned, the margin error falls from 22 to about 10 points. This is the one change that passed. It is not switched on in the harness: that is GV-4's decision.",
            "Off-cycle environment: built for every odd-year election day from 1999 to 2025 and tested with every fit as of the date. The term-year estimator holds up; the generic ballot of the day does not beat it.",
            "Intervals: about right race by race, and the count of wins was inside its range in all 11 cycles. The \"too wide\" reading does not survive the as-of test. Widening the races forecast from the prior alone failed the rule. No change.",
            "Added the same day, a seventh change: presidential approval in the prior, by party agreement between governor and president and by state lean. It failed the rule (the gain is under the floor), though the lean term keeps its sign in every fit. Worth rerunning when DA-2 adds cycles.",
            "A governor's own approval could not be tested: there is no such data in the repo. The backtest shows where it would matter: races with few or no polls, where a popular incumbent can beat the prior by 20 points, and any forecast made before polls exist. Finding a source is a data question, not yet a card."
          ],
          checklist: [
            { id: "a", text: "Lean measure tested" },
            { id: "b", text: "Governor poll average built" },
            { id: "c", text: "2025 environment as of each date" },
            { id: "d", text: "Interval width reviewed" }
          ],
          refs: ["src/model/governor_model.py", "src/model/pollavg.py", "src/model/governor_inputs.py", "BACKTEST.md"] },
        { id: "GV-4", title: "Freeze the design before touching 2026 results", kind: "gate", phase: "p2", needs: ["GV-3"],
          why: "2026 is only a real test if the design is fixed first.",
          details: [
            "2026 governor results stay uncollected and unscored until this gate is passed.",
            "Record the frozen design: the commit, the parameters and the scoring rule.",
            "Three decisions come from GV-3: whether to adopt the earlier-polls change (and in which of its two versions), which poll average the design names (the plain 21-day mean the model was fitted on, or the published weighted one), and what to do with a race that is three-way in the polls, since the model covers two-way races."
          ] },
        { id: "GV-5", title: "Score 2026", kind: "story", phase: "p2", needs: ["GV-4", "SC-1"],
          why: "One clean out-of-sample test.",
          details: [
            "Run the frozen design on the snapshot from before the election.",
            "Then collect certified results and score once."
          ],
          checklist: [
            { id: "a", text: "Forecast run on the frozen snapshot" },
            { id: "b", text: "Certified results collected" },
            { id: "c", text: "Scored and written up" }
          ] },
        { id: "GV-6", title: "2027 races as a live run", kind: "story", phase: "p4", needs: ["GV-5"],
          why: "The first live use, and a dry run for the site and the results collectors.",
          details: [
            "Kentucky, Louisiana and Mississippi elect governors in fall 2027.",
            "Uses the single-race path with the term-year environment."
          ],
          refs: ["src/model/single_race.py"] },
        { id: "GV-7", title: "2028 governors in the joint simulation", kind: "story", phase: "p4", needs: ["CM-8", "GV-5"],
          why: "In 2028 governors share a ballot with the president.",
          details: [
            "A state-level component shared with that state's presidential and Senate races."
          ] },
        { id: "GV-8", title: "Governors page on the site", kind: "story", phase: "p4", needs: ["SI-6"],
          why: "Planned since the first governors design.",
          details: [
            "Win probability per race and the count of governorships, with its range."
          ] }
      ]
    },

    {
      id: "pipeline", code: "OP", name: "Pipeline and operations", short: "Pipeline",
      goal: "Make the code reusable across cycles and offices, and the routine runs dependable.",
      doneWhen: "A new cycle is a config change, polls come from two sources, and scheduled work runs on time.",
      deadline: "",
      cards: [
        { id: "OP-1", title: "Audit of hardcoded 2026 values", kind: "story", phase: "p2",
          why: "The code was built against one election date and one map.",
          details: [
            "Seats not up, key dates, the poll-closing time, and filenames with 2026 in them.",
            "Move them into one cycle config that can describe any election, midterm or presidential.",
            "Include the scorecard and post-mortem scripts, so the cycle of forecast, scorecard, post-mortem and archive repeats for 2028 and 2030 without rewriting them.",
            "Confirm the frozen 2026 forecast still rebuilds exactly.",
            "Step (a) done 2026-11-20: planning/op1-hardcoded-2026-audit.md lists every occurrence, sorted into config values, historical constants and 2026-by-design, with a proposed config and the order for steps (b) and (c). Those two wait until the daily scorecard has finished in mid-December, since they touch the modules it imports."
          ],
          checklist: [
            { id: "a", text: "Hardcoded values listed" },
            { id: "b", text: "Cycle config in place" },
            { id: "c", text: "Frozen forecast rebuild check passes" }
          ],
          refs: ["planning/op1-hardcoded-2026-audit.md", "src/model/forecast.py", "src/run_all.py"] },
        { id: "OP-2", title: "Two poll sources and a blocklist", kind: "story", phase: "p4",
          why: "The poll audit on the scorecard page found polls missing from our one source, and polls from a pollster that should have been left out.",
          details: [
            "Ingest a second source and reconcile the two.",
            "Keep the pollster blocklist as data.",
            "Check that every House poll is matched to its district.",
            "Have a fallback if the main source goes away."
          ],
          checklist: [
            { id: "a", text: "Second source ingested" },
            { id: "b", text: "Reconciliation rule written" },
            { id: "c", text: "District matching checked" },
            { id: "d", text: "Fallback tested" }
          ],
          refs: ["src/model/pollavg.py", "src/model/poll_audit.py", "src/collect/wiki_polls.py"] },
        { id: "OP-3", title: "Dependable scheduled runs", kind: "decision", phase: "p3",
          why: "GitHub's scheduler has run the daily job hours late or not at all.",
          details: [
            "Decided 2026-11-20: an outside trigger, a small Cloudflare cron Worker that starts the workflow through workflow_dispatch with a fine-grained token. Not built for 2026, where a late scorecard run costs nothing; built when the first 2027 daily job exists, the primaries refresh.",
            "One Worker serves every scheduled job after that: the 2027 governor and 2028 primaries scorecards, the specials check (SP-8) and the redistricting watch (OP-6). A new job is one more cron line and a workflow name.",
            "Until then late runs are tolerated and a missed run is dispatched by hand. Every run still ends in a pull request.",
            "The token expires within a year, so building it in spring 2027 lines up its lifetime with the 2028 season."
          ],
          checklist: [
            { id: "a", text: "Worker written and deployed, token stored as a secret" },
            { id: "b", text: "GitHub cron removed from the workflow it replaces" },
            { id: "c", text: "A missed GitHub run no longer possible: one week of on-time triggers" }
          ],
          refs: [".github/workflows/scorecard.yml", "wrangler.jsonc"] },
        { id: "OP-4", title: "Results collectors for 2027 and 2028", kind: "story", phase: "p4", needs: ["OP-1"],
          why: "The scorecard collectors are written for the 2026 races.",
          details: [
            "Official state counts where a source can be scripted, Wikipedia otherwise.",
            "Some state sites block cloud runners. Keep the saved-copy fallback."
          ],
          refs: ["src/collect/official_senate.py", "src/collect/results_margins.py"] },
        { id: "OP-5", title: "Automatic results feed", kind: "story", phase: "any",
          why: "A nice-to-have. Only an automatic feed is worth building.",
          details: [
            "Options to evaluate: state and county election-night files, and paid wire tiers.",
            "Dry runs: special elections, the 2027 governor races and the 2028 primaries."
          ] },
        { id: "OP-6", title: "Redistricting watch", kind: "story", phase: "any",
          why: "District lines can change again before 2028.",
          details: [
            "Track passed plans and court rulings.",
            "Rebuild district lean on the lines in force.",
            "The Downballot's redistribution analyses show how each new district is built from old ones; see CM-9."
          ] },
        { id: "OP-7", title: "Freeze routine for 2028", kind: "story", phase: "p4", needs: ["OP-1"],
          why: "The final-forecast routine handles one election date and two chambers.",
          details: [
            "Freeze, tag and lock label, extended to more offices and more than one date."
          ],
          refs: ["src/run_all.py"] },
        { id: "OP-8", title: "Store for sources that are linked, not committed", kind: "story", phase: "p2",
          why: "The Downballot's data is free to use with a citation and a link, but it asks that whole spreadsheets not be reproduced. The repo commits its raw inputs, which would do just that.",
          details: [
            "A gitignored raw store for such sources, filled by script and rebuilt on demand. A committed manifest records each fetch: sheet id, tab, date.",
            "Only derived tables are committed, each cited in DATA.md with a link to the source's page.",
            "Where the site would link to our copy of the data, it links to the source's own page instead.",
            "Needed before the first Downballot table is used: specials history (SP-3), state presidential results (DA-5), presidential results by district (CM-9, OP-6), district demographics (DA-4)."
          ],
          checklist: [
            { id: "a", text: "Gitignored store and committed manifest in place" },
            { id: "b", text: "Fetch helper for Google Sheets tabs" },
            { id: "c", text: "DATA.md and LICENSE-DATA.md describe the convention" },
            { id: "d", text: "Site build links to the source where a data link would be" }
          ],
          refs: ["DATA.md", "LICENSE-DATA.md", "src/collect/common.py", ".gitignore"] }
      ]
    }
  ]
};
