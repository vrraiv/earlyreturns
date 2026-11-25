# Data licence

**Derived data** produced by this project is licensed under the
[Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/)
(CC BY-SA 4.0). That covers the files in `data/interim/`, `data/processed/`, `data/final/`, `data/scorecard/` and
`data/postmortem/`, and the downloads on the site (`site/2026/data/`, `site/history/data/`).

Credit: "Early Returns (earlyreturns.vikramrai.com, formerly polling2026), CC BY-SA 4.0", and credit the original sources below.

Share-alike is required because many tables are adapted from Wikipedia (CC BY-SA 4.0).

## Not covered

- **Raw source files** in `data/raw/` stay under their sources' own terms: see `DATA.md`.
- **Gallup approval** (from the American Presidency Project, "Data adapted from the Gallup Poll and compiled by
  Gerhard Peters"; © The American Presidency Project) is not openly licensed. Derived figures such as window
  averages appear in this project's tables with credit; the poll-level series is Gallup's and the American
  Presidency Project's, not this project's to license.
- **Cook PVI** (the Cook Political Report) and **expert ratings** (Cook, Sabato's Crystal Ball, Inside Elections and
  others), reproduced via Wikipedia, are their publishers' figures; credit them by name.
- **The Downballot**'s sheets, kept in the gitignored `data/linked/` store, are The Downballot's. Tables derived from
  them (such as `state_presidential_history.csv`) are covered above, with credit and a link to
  [the-downballot.com/p/data](https://www.the-downballot.com/p/data); please do not rebuild their whole sheets from
  this project's files.
- **`data/interim/primary_polls_huffpost.csv`** is adapted from HuffPost Pollster, which licensed its data
  under [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). That file, and anything derived
  from it poll by poll, is under the same licence: non-commercial use only, with credit to HuffPost Pollster
  and to this project.
- **State election offices' 2024 presidential primary files** in `data/raw/state_primary/` are public records kept
  as published, not this project's to license; the Missouri Democratic Party's results sheet there is the party's.
- **TheGreenPapers.com**'s pages, its downloaded spreadsheets and the 2016 computation tables its webmaster sent us to
  are kept in the git-ignored store only. The tables derived from them (`primary_delegate_rules.csv`,
  `primary_delegates.csv`, `primary_delegate_events.csv`, `primary_calendar_check.csv`, `primary_greenpapers_counts.csv`,
  `primary_results_greenpapers_check.csv`, `primary_greenpapers_tallies.csv`, `primary_delegate_units.csv`,
  `primary_delegate_count.csv`, `primary_delegate_allocation_d.csv`, `primary_delegate_allocation_r.csv`,
  `primary_greenpapers_events.csv`, and the hand-entered `data/supplement/primary_calendar_additions.csv`,
  `primary_contest_flags.csv` and `primary_allocation_classes.csv`, which draw on its pages) are covered above, attributed to
  TheGreenPapers.com, as the site asked, with a link to [thegreenpapers.com](https://www.thegreenpapers.com/); the site gave leave to use its data.
- **University of Michigan consumer sentiment** (in the raw FRED folder) is copyrighted and not used in any output.

## Sources to credit

Wikipedia contributors (CC BY-SA 4.0); FiveThirtyEight / ABC News; HuffPost Pollster (CC BY-NC-SA 3.0, the primary polls file only); VoteHub; Gallup via the American Presidency
Project; BLS, BEA and EIA via FRED (public domain); the Federal Election Commission (public domain); TheGreenPapers.com (delegate rules and counts, with a link to the site); the U.S. Census Bureau (public domain; its Data API is used, without its endorsement or certification); state election offices and the California Secretary of State (public records); AtlasIntel (poll toplines); Will Jennings and Christopher Wlezien (national presidential polls 1952-2016, CC0); The Economist (presidential polls, MIT); the MIT Election Data and Science Lab (House and Senate returns, CC0); David Broockman (district presidential vote 1952-2004, CC0); The
Downballot (presidential results by state, with a link to its data page).
