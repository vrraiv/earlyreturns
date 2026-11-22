"""Electoral votes by election and Maine's and Nebraska's district results (ELECTORAL_COLLEGE.md, section 15, A2 and A5).

  electoral_votes.csv        election (2000 to 2028), contest (51 states and DC, ME-1, ME-2, NE-1, NE-2, NE-3), ev.
                             A state's figure is its apportionment, not the votes its electors cast. Maine and
                             Nebraska statewide carry 2 and each district 1.
                             2000 to 2020: the results-by-state table of the cached yearly presidential pages (the same
                             pages state_presidential.csv is built from). 2000 to 2008 have a state column; 2012 to 2020
                             give votes cast per candidate, faithless electors in "Others", and the row's sum is the
                             apportionment.
                             2024 and 2028: the 2020 census column of Wikipedia's apportionment page (House seats + 2,
                             DC 3). The 2024 presidential page is never opened: 2024 is held out.
  district_presidential.csv  1996 to 2020: the five districts' votes for the two nominees, their two-party margin, the
                             state's, and the district's lean against its state. 1996 is read for the districts' lean
                             at the 2000 election.

Pages come from data/raw/wikipedia_hist/<date>/ through governors.get_page (cached; revision ids kept in every row).

Run:  python src/collect/electoral_college.py          build both files
      python src/collect/electoral_college.py check    the checks of section 15 (prints pass or fail; sums, cross-checks)
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT  # noqa: E402
from governors import STATE_NAMES, clean, get_page, read_tables  # noqa: E402

INTERIM = ROOT / "data" / "interim"
PAGE_YEARS = tuple(range(1996, 2021, 4))         # pages read; 2024 is never opened
EV_YEARS = tuple(range(2000, 2029, 4))           # elections electoral_votes.csv covers
APPORTIONMENT_PAGE = "United States congressional apportionment"
CENSUS_FOR = {2000: 1990, 2004: 2000, 2008: 2000, 2012: 2010, 2016: 2010, 2020: 2010, 2024: 2020, 2028: 2020}
DISTRICTS = {"ME": 2, "NE": 3}
DIST_RE = re.compile(r"^(?:(ME|NE)-(\d)|(Maine|Nebraska)-(\d)|(Maine|Nebraska)'s (\d)(?:st|nd|rd|th))(?!\d)")
ABBR = {"Maine": "ME", "Nebraska": "NE"}


def _norm(s):
    return clean(str(s).replace("\xad", ""))


def contest_of(cell):
    """'NY' for a state row, 'ME-1' for a district row, None otherwise."""
    s = _norm(cell)
    m = DIST_RE.match(s)
    if m:
        st = m.group(1) or ABBR[m.group(3) or m.group(5)]
        return f"{st}-{m.group(2) or m.group(4) or m.group(6)}"
    return STATE_NAMES.get(re.sub(r"\s*\(.*?\)|†|\*|�", "", s).strip())


def _num(col):
    return pd.to_numeric(col.astype(str).str.replace(r"[^\d]", "", regex=True), errors="coerce")


def results_table(html):
    """The results-by-state table: both nominees' votes, every electoral-vote column, and the state column if any."""
    for t in read_tables(html):
        if not isinstance(t.columns, pd.MultiIndex) or len(t) < 50:
            continue
        tops = [_norm(" ".join(map(str, c[:-1]))) for c in t.columns]
        subs = [_norm(c[-1]) for c in t.columns]
        is_votes = lambda b: b in ("#", "Votes", "Vote", "Votes #")
        is_ev = lambda b: b == "EV" or "electoral" in b.lower()
        vote = lambda party: next((i for i, (a, b) in enumerate(zip(tops, subs)) if party in a and is_votes(b)), None)
        di, ri = vote("Democratic"), vote("Republican")
        if di is None or ri is None:
            continue
        cand_ev = [i for i, (a, b) in enumerate(zip(tops, subs)) if is_ev(b) and not a.startswith("Unnamed")
                   and "Margin" not in a and "Total" not in a]
        state_ev = [i for i, (a, b) in enumerate(zip(tops, subs)) if is_ev(b) and a.startswith("Unnamed")]
        con = t.iloc[:, 0].map(contest_of)
        if con.notna().sum() < 50:
            continue
        k = con.notna()
        out = pd.DataFrame({"contest": con[k].values, "d_votes": _num(t.iloc[:, di])[k].values,
                            "r_votes": _num(t.iloc[:, ri])[k].values})
        ev_cast = sum(_num(t.iloc[:, i]).fillna(0) for i in cand_ev)
        out["ev_cast_sum"] = ev_cast[k].values
        out["ev_state_col"] = _num(t.iloc[:, state_ev[0]])[k].values if state_ev else np.nan
        assert not out.contest.duplicated().any(), "a contest appears twice"
        return out
    raise RuntimeError("no results-by-state table found")


def page_rows():
    rows = []
    for y in PAGE_YEARS:
        html, rev = get_page(f"{y}_United_States_presidential_election")
        t = results_table(html)
        t.insert(0, "year", y)
        t["revision"] = rev
        rows.append(t)
        print(f"  {y}: {len(t)} contests (revision {rev})")
    return pd.concat(rows, ignore_index=True)


def apportionment():
    """House seats by state from the apportionment page, by census year (columns), with the page's revision."""
    html, rev = get_page(APPORTIONMENT_PAGE)
    best = None
    for t in read_tables(html):
        levels = [[_norm(x) for x in (c if isinstance(c, tuple) else (c,))] for c in t.columns]
        years = {}
        for i, lv in enumerate(levels):
            yrs = [int(x) for x in lv if re.fullmatch(r"(18|19|20)\d0", x)]
            if yrs:
                years[i] = yrs[0]
        if 2020 not in years.values() or 1990 not in years.values():
            continue
        state_col = next((i for i, lv in enumerate(levels) if "State" in lv and i not in years), 0)
        abbr = set(STATE_NAMES.values())
        sts = t.iloc[:, state_col].map(lambda s: (lambda x: STATE_NAMES.get(x, x if x in abbr else None))(
            re.sub(r"\[.*?\]|\*", "", _norm(s)).strip()))
        if sts.notna().sum() < 50:
            continue
        d = pd.DataFrame({"state": sts[sts.notna()].values})
        for i, yr in years.items():
            d[yr] = _num(t.iloc[:, i])[sts.notna()].values
        best = d.dropna(axis=1, how="all").drop_duplicates("state").set_index("state")
        break
    if best is None:
        raise RuntimeError("no apportionment table found")
    return best, rev


def ev_from_pages(P):
    """Electoral votes by (year, contest) from the pages, 2000 to 2020: the state column where there is one, else the
    row's sum of votes cast; districts 1; Maine and Nebraska statewide 2."""
    out = []
    for y in EV_YEARS:
        if y > 2020:
            continue
        g = P[P.year == y]
        for _, r in g.iterrows():
            if "-" in r.contest:
                ev = 1
            else:
                ev = r.ev_state_col if not np.isnan(r.ev_state_col) else r.ev_cast_sum
                if r.contest in DISTRICTS:
                    ev = 2
            out.append({"election": y, "contest": r.contest, "ev": int(ev), "source": f"page {y} revision {int(r.revision)}"})
    return pd.DataFrame(out)


def ev_from_apportionment(A, rev, years=(2024, 2028)):
    out = []
    for y in years:
        seats = A[CENSUS_FOR[y]]
        for st, n in seats.items():
            n = int(n)
            if st in DISTRICTS:
                out.append({"election": y, "contest": st, "ev": 2, "source": f"apportionment page revision {rev}, census {CENSUS_FOR[y]}"})
                for k in range(1, DISTRICTS[st] + 1):
                    out.append({"election": y, "contest": f"{st}-{k}", "ev": 1, "source": f"apportionment page revision {rev}, census {CENSUS_FOR[y]}"})
            else:
                out.append({"election": y, "contest": st, "ev": n + 2, "source": f"apportionment page revision {rev}, census {CENSUS_FOR[y]}"})
        out.append({"election": y, "contest": "DC", "ev": 3, "source": "Twenty-third Amendment"})
    return pd.DataFrame(out)


def districts(P):
    st_m = P[~P.contest.str.contains("-")].assign(margin_2p=lambda d: 100 * (d.d_votes - d.r_votes) / (d.d_votes + d.r_votes))
    st_m = st_m.set_index(["year", "contest"]).margin_2p
    d = P[P.contest.str.contains("-")].copy()
    d["state"] = d.contest.str[:2]
    d["margin_2p"] = 100 * (d.d_votes - d.r_votes) / (d.d_votes + d.r_votes)
    d["state_margin_2p"] = [st_m[(y, s)] for y, s in zip(d.year, d.state)]
    d["lean_vs_state"] = d.margin_2p - d.state_margin_2p
    return d[["year", "contest", "state", "d_votes", "r_votes", "margin_2p", "state_margin_2p", "lean_vs_state", "revision"]] \
        .sort_values(["year", "contest"]).reset_index(drop=True)


def build():
    print("pages:")
    P = page_rows()
    assert P.year.max() <= 2020
    A, rev = apportionment()
    print(f"  apportionment page (revision {rev}): censuses {sorted(A.columns)}")
    E = pd.concat([ev_from_pages(P), ev_from_apportionment(A, rev)], ignore_index=True).sort_values(["election", "contest"])
    E.to_csv(INTERIM / "electoral_votes.csv", index=False)
    D = districts(P)
    D.to_csv(INTERIM / "district_presidential.csv", index=False)
    print(f"electoral_votes.csv: {len(E)} rows, totals by election", E.groupby("election").ev.sum().to_dict())
    print(f"district_presidential.csv: {len(D)} rows, {D.year.min()} to {D.year.max()}")
    return P, A, rev, E, D


def check():
    P = page_rows()
    A, rev = apportionment()
    E = pd.read_csv(INTERIM / "electoral_votes.csv")
    D = pd.read_csv(INTERIM / "district_presidential.csv")
    S = pd.read_csv(INTERIM / "state_presidential.csv")
    H = pd.read_csv(INTERIM / "house_history.csv")
    ok = True

    def report(name, passed):
        nonlocal ok
        ok &= bool(passed)
        print(f"  {'pass' if passed else 'FAIL'}  {name}")

    report("2024 is absent from the pages read and from the district results", P.year.max() <= 2020 and D.year.max() <= 2020)
    report("electoral votes sum to 538 in every election 2000 to 2028", (E.groupby("election").ev.sum() == 538).all()
           and set(E.election) == set(EV_YEARS))
    report("56 contests in every election", (E.groupby("election").size() == 56).all())
    me = E[E.contest.str.startswith("ME")].groupby("election").ev.sum(); ne = E[E.contest.str.startswith("NE")].groupby("election").ev.sum()
    report("Maine is 4 and Nebraska 5, as 2 plus the districts", (me == 4).all() and (ne == 5).all())
    old = P[(P.year.between(2000, 2008)) & ~P.contest.str.contains("-") & P.ev_state_col.notna()]
    diff = old.ev_state_col - old.ev_cast_sum
    odd = old[diff != 0]
    if len(odd):
        print("        state column above the candidates' sum (a faithless vote in no column):",
              [(int(y), c, int(a), int(b)) for y, c, a, b in zip(odd.year, odd.contest, odd.ev_state_col, odd.ev_cast_sum)])
    report("2000 to 2008: the state column equals the sum of the candidates' electoral votes, or exceeds it by one faithless vote",
           len(old) >= 150 and diff.between(0, 1).all() and (diff != 0).sum() <= 2)
    # pages against the apportionment page, by census
    agree = True
    for y in range(2000, 2021, 4):
        e = E[(E.election == y) & ~E.contest.str.contains("-") & (E.contest != "DC")].set_index("contest").ev
        a = A[CENSUS_FOR[y]].reindex(e.index) + 2
        a[a.index.isin(list(DISTRICTS))] = 2
        agree &= bool((e == a).all())
    report("2000 to 2020: the pages' figures equal the apportionment page's census column plus two", agree)
    # the House file: highest district number per state plus two, where the file has the state
    agree = True
    for y in range(2008, 2025, 2):
        if y not in set(H.year):
            continue
        hy = H[H.year == y].groupby("state").district.max().clip(lower=1) + 2     # an at-large seat is district 0
        hy[hy.index.isin(list(DISTRICTS))] = 2
        cen = {2008: 2000, 2010: 2000, 2012: 2010, 2014: 2010, 2016: 2010, 2018: 2010, 2020: 2010, 2022: 2020, 2024: 2020}[y]
        a = A[cen].reindex(hy.index) + 2
        a[a.index.isin(list(DISTRICTS))] = 2
        at_large = hy.index[hy == 2 + 1]  # states with one district: file says 1, apportionment 1
        agree &= bool((hy == a).all())
    report("the House file's highest district number per state plus two equals the apportionment page, 2008 to 2024", agree)
    # districts: five per year, both nominees' votes, and the districts' sum equals the state's votes
    report("five districts with both nominees' votes in every election 1996 to 2020",
           (D.groupby("year").size() == 5).all() and set(D.year) == set(PAGE_YEARS) and D[["d_votes", "r_votes"]].notna().all().all())
    sums = D.groupby(["year", "state"])[["d_votes", "r_votes"]].sum()
    st = P[P.contest.isin(list(DISTRICTS))].set_index(["year", "contest"])[["d_votes", "r_votes"]]
    st.index.names = ["year", "state"]
    rel = (sums.sort_index().values - st.sort_index().values) / st.sort_index().values
    gaps = pd.DataFrame(rel, index=sums.sort_index().index, columns=["d", "r"])
    gaps = gaps[(gaps.abs() > 0).any(axis=1)]
    if len(gaps):
        print("        districts' sum short of the state's votes (ballots not assigned to a district), as a share:",
              {f"{y} {s}": (round(float(a), 5), round(float(b), 5)) for (y, s), a, b in zip(gaps.index, gaps.d, gaps.r)})
    report("each state's districts sum to the state's votes for each nominee, within 0.1%", (np.abs(rel) <= 0.001).all())
    # the states' votes on the pages equal state_presidential.csv where both exist
    sp = S[S.year.between(1996, 2020)].set_index(["year", "state"])[["d_votes", "r_votes"]]
    pp = P[~P.contest.str.contains("-")].set_index(["year", "contest"])[["d_votes", "r_votes"]]
    pp.index.names = ["year", "state"]
    j = sp.join(pp, rsuffix="_page", how="inner")
    report("the pages' state votes equal state_presidential.csv, 1996 to 2020",
           len(j) == 51 * 7 and np.allclose(j.d_votes, j.d_votes_page) and np.allclose(j.r_votes, j.r_votes_page))
    print("all checks pass" if ok else "SOME CHECKS FAIL")
    return ok


if __name__ == "__main__":
    {"build": build, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "build"]()
