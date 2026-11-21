"""The campaign calendar for presidential elections (EC-2): convention dates, and the date each nominee became
presumptive. Calendar facts only: no polls and no results are read.

Conventions: Wikipedia's "List of Democratic National Conventions" and "List of Republican National Conventions",
fetched through governors.get_page (cached in data/raw/wikipedia_hist/, revision ids kept in every row). 1948 on,
including any announced future convention.

Presumptive nominees, 1980 to 2020: entered by hand below, each row with its source. 2024 is left out on purpose: it
is added, under the rule fixed here, when the 2024 holdout is scored (ELECTORAL_COLLEGE.md, section 11).
  clinched         the day news delegate counts gave the nominee a majority of convention delegates. Where sources
                   give different days, the latest. A sitting president whom no rival took delegates from has no
                   such day on record in one case (Reagan, 1984): the first contest is entered and flagged.
  other_dates      the other days found in sources, so the choice can be seen.
  contested_until  where a rival with a large share of the delegates fought on after that day: the day the rival
                   conceded, endorsed, withdrew or lost the roll call. Which rivals count is a judgment from the
                   pages (delegate shares are not collected): Kennedy 1980, Hart 1984, Jackson 1988, Brown 1992,
                   Clinton 2008, Sanders 2016.
"Wikipedia table" means the candidate table of that year's "<year> <party> Party presidential primaries" page
("Secured nomination", "Withdrew", "Eliminated at Convention"), at the revision in wiki_revision. "Found by search"
means the report was found by a web search and read in summary, not opened in full.

Outputs: data/interim/convention_dates.csv, data/interim/presumptive_nominees.csv.
Run:  python src/collect/campaign_calendar.py   (prints both checks used in ELECTORAL_COLLEGE.md, section 11)
"""
import datetime as dt
import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402
from governors import get_page, read_tables  # noqa: E402

INTERIM = ROOT / "data" / "interim"
PAGES = {"D": "List of Democratic National Conventions", "R": "List of Republican National Conventions"}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}
TEST_DAYS = (150, 100)
WIKI = "Wikipedia table"
REUTERS = "Reuters chronology of 5 February 2008"

# cycle, party, nominee, clinched, basis, other_dates, contested_until, contested_by, wiki_revision
NOMINEES = [
    (1980, "D", "Jimmy Carter", "1980-06-03",
     "majority in news counts after the last primaries (Wikipedia's campaign page, found by search)",
     "1980-08-11 (" + WIKI + ": secured at the convention)",
     "1980-08-11", "Ted Kennedy, withdrew at the convention after losing the rules vote (" + WIKI + ")", 1385536192),
    (1980, "R", "Ronald Reagan", "1980-05-24", WIKI,
     "1980-05-20 (after the Michigan and Oregon primaries, found by search)", "", "", 1386009125),
    (1984, "D", "Walter Mondale", "1984-06-06",
     "claimed a majority, counting superdelegates, the day after the last primaries (UPI of 7 June 1984 and the "
     "Michigan Daily, found by search)", "",
     "1984-07-18", "Gary Hart, lost the roll call (" + WIKI + ")", 1385086113),
    (1984, "R", "Ronald Reagan", "1984-02-20",
     "sitting president, no rival with delegates; no clinch day found, so the first contest is entered",
     "1984-08-23 (" + WIKI + ": the roll call)", "", "", 1379396600),
    (1988, "D", "Michael Dukakis", "1988-06-07", WIKI + "; " + REUTERS, "",
     "CONVENTION", "Jesse Jackson, to the convention (the roll call's date is not collected: the convention's last "
     "day is used)", 1382452519),
    (1988, "R", "George H. W. Bush", "1988-04-26", WIKI + "; " + REUTERS, "", "", "", 1375540017),
    (1992, "D", "Bill Clinton", "1992-06-02", WIKI + "; " + REUTERS, "",
     "1992-07-15", "Jerry Brown, lost the roll call (" + WIKI + ")", 1386194946),
    (1992, "R", "George H. W. Bush", "1992-05-05", WIKI, "1992-04-28 (" + REUTERS + ")", "", "", 1381811601),
    (1996, "D", "Bill Clinton", "1996-03-26", WIKI, "", "", "", 1369052814),
    (1996, "R", "Bob Dole", "1996-03-26",
     "held back from claiming the nomination until California voted (Irish Times, found by search)",
     "1996-03-19 (" + WIKI + "; " + REUTERS + ")", "", "", 1379384283),
    (2000, "D", "Al Gore", "2000-03-14", WIKI + "; " + REUTERS, "", "", "", 1384248113),
    (2000, "R", "George W. Bush", "2000-03-14", WIKI + "; " + REUTERS, "", "", "", 1386824263),
    (2004, "D", "John Kerry", "2004-03-16",
     "passed 2,162 delegates with the Illinois primary (Washington Times and PBS of 17 March 2004, found by search)",
     "2004-03-02 (" + WIKI + "; " + REUTERS + "); 2004-03-11 (the page's text, counting superdelegates)", "", "",
     1386704803),
    (2004, "R", "George W. Bush", "2004-03-10", WIKI, "", "", "", 1379449467),
    (2008, "D", "Barack Obama", "2008-06-03", WIKI, "",
     "2008-06-07", "Hillary Clinton, conceded and endorsed (the page's text)", 1384443023),
    (2008, "R", "John McCain", "2008-03-04", WIKI, "", "", "", 1381785936),
    (2012, "D", "Barack Obama", "2012-04-03", WIKI, "", "", "", 1385393019),
    (2012, "R", "Mitt Romney", "2012-05-29", WIKI,
     "2012-04-25 (declared presumptive by the party's national committee)", "", "", 1386168214),
    (2016, "D", "Hillary Clinton", "2016-06-06", WIKI + " (the Associated Press count, with superdelegates)", "",
     "2016-07-12", "Bernie Sanders, endorsed (the page's text)", 1386824791),
    (2016, "R", "Donald Trump", "2016-05-26", WIKI, "2016-05-03 (declared presumptive by the party's chairman)", "", "",
     1375633886),
    (2020, "D", "Joe Biden", "2020-06-05", WIKI, "2020-04-08 (the last rival withdrew)", "", "", 1381856294),
    (2020, "R", "Donald Trump", "2020-03-17", WIKI, "", "", "", 1386793513),
]


def election_day(year):
    """The Tuesday after the first Monday of November."""
    d = dt.date(year, 11, 1)
    return d + dt.timedelta(days=(7 - d.weekday()) % 7 + 1)


def span(text, year):
    """'July 31-August 3' -> (start, end); None for a convention with no dates yet."""
    m = re.match(r"([A-Z][a-z]+) (\d{1,2})(?:\s*[–-]\s*(?:([A-Z][a-z]+) )?(\d{1,2}))?", str(text).strip())
    if not m or m.group(1) not in MONTHS:
        return None
    m1, d1, m2, d2 = m.group(1), int(m.group(2)), m.group(3) or m.group(1), int(m.group(4) or m.group(2))
    return dt.date(year, MONTHS[m1], d1), dt.date(year, MONTHS[m2], d2)


def conventions():
    rows = []
    for party, title in PAGES.items():
        html, rev = get_page(title)
        soup = BeautifulSoup(html, "html.parser")
        for s in soup.find_all("sup"):          # footnote marks would run into the dates and years
            s.decompose()
        t = next(x for x in read_tables(str(soup)) if "Year" in x.columns and str(x.columns[0]).startswith("Dates"))
        for dates, year in zip(t.iloc[:, 0], t["Year"]):
            year = int(str(year)[:4])
            if year < 1948:
                continue
            sp = span(dates, year)
            e = election_day(year)
            rows.append({"cycle": year, "party": party, "start": sp[0] if sp else "", "end": sp[1] if sp else "",
                         "election_date": e, "end_days_to_election": (e - sp[1]).days if sp else "",
                         "wiki_revision": rev})
    df = pd.DataFrame(rows).sort_values(["cycle", "party"])
    assert not df.duplicated(["cycle", "party"]).any()
    df.to_csv(INTERIM / "convention_dates.csv", index=False)
    return df


def presumptive(conv):
    cols = ["cycle", "party", "nominee", "clinched", "basis", "other_dates", "contested_until", "contested_by",
            "wiki_revision"]
    df = pd.DataFrame(NOMINEES, columns=cols)
    assert 2024 not in set(df.cycle)
    end = conv.set_index(["cycle", "party"]).end
    df["contested_until"] = [str(end[(c, p)]) if u == "CONVENTION" else u
                             for c, p, u in zip(df.cycle, df.party, df.contested_until)]
    df["election_date"] = df.cycle.map(election_day)
    df["clinched_days_to_election"] = [(e - dt.date.fromisoformat(c)).days for e, c in zip(df.election_date, df.clinched)]
    df["contested_days_to_election"] = [(e - dt.date.fromisoformat(u)).days if u else ""
                                        for e, u in zip(df.election_date, df.contested_until)]
    df = df[cols[:4] + ["clinched_days_to_election"] + cols[4:8] + ["contested_days_to_election", "election_date",
                                                                   "wiki_revision"]]
    df.to_csv(INTERIM / "presumptive_nominees.csv", index=False)
    return df


def checks(conv, nom):
    c = conv[(conv.end != "") & conv.cycle.between(1952, dt.date.today().year)]
    later = c.groupby("cycle").end_days_to_election.min().astype(int)
    print(f"later convention's last day, days before the election, {later.index.min()} to {later.index.max()}: "
          f"{later.min()} to {later.max()}; within 100 days in {(later <= 100).sum()} of {len(later)}")
    print(later.to_string())
    a = nom.groupby("cycle").clinched_days_to_election.min()
    b = nom.assign(x=[min(c, u) if u != "" else c for c, u in
                      zip(nom.clinched_days_to_election, nom.contested_days_to_election)]).groupby("cycle").x.min()
    out = pd.DataFrame({"both_clinched_days_out": a, "and_uncontested_days_out": b})
    for d in TEST_DAYS:
        out[f"clinched_by_{d}"] = a >= d
        out[f"uncontested_by_{d}"] = b >= d
    print("\nboth nominees presumptive, days before the election (1980 to 2020):")
    print(out.to_string())
    print(out.iloc[:, 2:].sum().to_string())


if __name__ == "__main__":
    cv = conventions()
    print(f"convention_dates.csv: {len(cv)} rows, {cv.cycle.min()} to {cv.cycle.max()}")
    nm = presumptive(cv)
    print(f"presumptive_nominees.csv: {len(nm)} rows, {nm.cycle.min()} to {nm.cycle.max()}\n")
    checks(cv, nm)
