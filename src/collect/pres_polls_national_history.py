"""National presidential trial-heat polls by day, 1952-2020 (DA-5, EC-2): the long history for poll decay and convention
bounces, which the poll-level table (president_general_polls.csv, from 2004) is too short to estimate.

Source: Will Jennings and Christopher Wlezien, "Election Polling Errors across Time and Space", Nature Human
Behaviour 2 (2018), replication data on Harvard Dataverse, doi:10.7910/DVN/8421DX, CC0. The file covers 45 countries;
for each election and party it has one row per day with the average of the polls centred on that day (poll_), their
number (npolls) and pooled sample, and the result (vote_). It is a daily series, not a list of polls: there are no
pollster names, and a day with no poll has no value.

The 290 MB file is fetched into data/raw/jennings_wlezien/<date>/ and not committed (gitignored); the United States
presidential rows that have a poll are saved beside it as us_presidential_poll_days.csv, which is committed.

Where the series comes from, and which version is used (checked 2026-11-20):
- The original is Robert Erikson and Christopher Wlezien's file for The Timeline of Presidential Elections (2012):
  the Democrat's share of the two-party poll total on each of the last 300 days, 1952-2012. It was posted on
  Wlezien's university page (Timeline_Poll_Data.xlsx); the link is dead and the Internet Archive has it. It carries
  no licence, so it is fetched into the gitignored store (data/linked/) and used only as a check, printed on each run.
- 1952-2004 and 2016 come from the 2018 file, which matches the book's file to 0.1 point on nearly every day and
  adds poll counts, samples and the days more than 300 out.
- 2008 and 2012 come from the 2016 version of the same collection (Jennings and Wlezien, "The Timeline of Elections:
  A Comparative Perspective", AJPS 60, doi:10.7910/DVN/28856, CC0), which matches the book's file exactly (2012 with every reading dated one day earlier; left as published). In the
  2018 file (Dataverse, and the identical file on Wlezien's page) the 2008 series is 2004's again, with McCain ahead
  in the last fortnight, and 2012 is a different compilation: three times the readings, about 2 points more
  Republican than the book's file and than The Economist's polls. The 2016 version gives shares of the two-party
  total, has no poll counts, and starts 300 days out.
- 2020 is not in either file. It is built here from the national polls in president_general_polls.csv
  (FiveThirtyEight), the way the source describes its own series: one reading per poll, dated by the middle of its
  field period, and a plain mean of the polls centred on each day. A poll that asked several questions gives its
  head-to-head question, and of those the likely-voter one, then registered voters, then adults. The same build
  for 2016 is printed against the source 2016 rows on each run. Shares are of all respondents.
  2024 is never built: it is held out (ELECTORAL_COLLEGE.md, section 11), and from_polls refuses it.
The column source_version says which file a row comes from ("polls" for 2020).
Results are taken from state_presidential_history.csv, not from the source (they agree but for 2008).

Output: data/interim/president_national_poll_days.csv, one row per cycle and day with a poll: the Democrat's and
Republican's poll shares (as published: of all respondents to 2012 and in 2020, of the two-party total in 2016), the two-party
margin, polls and sample that day, and the result's two-party margin. Third candidates (1968, 1980, 1992, 1996) are
in the source but not carried here.

Run:  python src/collect/pres_polls_national_history.py   (prints the cross-check against our 2004-2016 national polls)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, latest, raw_dir  # noqa: E402

INTERIM = ROOT / "data" / "interim"
URL = "https://dataverse.harvard.edu/api/access/datafile/3107210"     # LONG_MI_NATURE_20180111.tab
BIG, SMALL = "LONG_MI_NATURE_20180111.tab", "us_presidential_poll_days.csv"
URL_2016 = "https://dataverse.harvard.edu/api/access/datafile/2533797"   # LONG_MI.tab, 1.4 GB: streamed, not kept
SMALL_2016V = "us_presidential_2008_2012_from_2016_version.csv"
BOOK_PAGE = "https://liberalarts.utexas.edu/government/faculty/cw26629"
BOOK_URL = ("https://web.archive.org/web/20220222171405id_/https://liberalarts.utexas.edu/government/_files/wlezien/"
            "Timeline_Poll_Data.xlsx")


def extract():
    """The US presidential poll-days, from the committed extract if present, else from the full file (fetched)."""
    try:
        return pd.read_csv(latest("jennings_wlezien", SMALL))
    except FileNotFoundError:
        pass
    big = fetch("jennings_wlezien", BIG, URL, timeout=1800)
    d = pd.read_csv(big, sep="\t", low_memory=False)
    d = d[(d.country == "United States") & (d.election == "Presidential") & d.poll_.notna()]
    d = d[["polldate", "electionyr", "elecdate", "daysbeforeED", "partyid", "poll_", "vote_", "inc_", "sample",
           "npolls"]]
    d.to_csv(big.parent / SMALL, index=False)
    return d


def extract_2016_version():
    """2008's and 2012's poll-days from the 2016 version: the committed extract if present, else streamed from
    Dataverse, keeping only the rows of the presidential elections of 2008-11-04 and 2012-11-06 (the file has no
    country name; no other country in it voted for a president on those days)."""
    import datetime as dt
    import io
    import json

    import requests
    try:
        return pd.read_csv(latest("jennings_wlezien", SMALL_2016V))
    except FileNotFoundError:
        pass
    r = requests.get(URL_2016, stream=True, timeout=600)
    r.raise_for_status()
    lines = []
    for i, line in enumerate(r.iter_lines(decode_unicode=True)):
        if i == 0 or "\t2008-11-04\t" in line or "\t2012-11-06\t" in line:
            lines.append(line)
    d = pd.read_csv(io.StringIO("\n".join(lines)), sep="\t", low_memory=False)
    d = d[(d.election == "Presidential") & d.poll_.notna()].drop_duplicates(["electionyr", "daysbeforeED", "partyid"])
    d = d[["polldate", "electionyr", "elecdate", "daysbeforeED", "partyid", "poll_", "vote_", "inc_"]]
    out = raw_dir("jennings_wlezien") / SMALL_2016V
    d.to_csv(out, index=False)
    mf = out.parent / "manifest.json"
    m = json.loads(mf.read_text()) if mf.exists() else {}
    m[SMALL_2016V] = {"url": URL_2016, "retrieved": dt.datetime.now().isoformat(timespec="seconds"),
                     "bytes": out.stat().st_size, "note": "rows of the 2008-11-04 and 2012-11-06 presidential elections with a poll"}
    mf.write_text(json.dumps(m, indent=2))
    return d


POP_RANK = {"lv": 0, "v": 1, "rv": 2, "a": 3}
D_INCUMBENT = {2016: 1, 2020: 0}


def from_polls(cycle):
    """One cycle of poll-days built from president_general_polls.csv (see the docstring): for 2020, and for 2016
    as a check on the method. Never 2024."""
    assert cycle in D_INCUMBENT and cycle != 2024, "only 2016 and 2020; 2024 is held out"
    p = pd.read_csv(INTERIM / "president_general_polls.csv", low_memory=False)
    p = p[(p.cycle == cycle) & (p.geo == "US") & ~p.presumptive & ~p.state_subsample]
    p = p.assign(h2h=p.head_to_head.fillna(False).astype(bool), pop=p.population.map(POP_RANK).fillna(4))
    p = p[p.h2h == p.groupby("poll_id").h2h.transform("max")]
    p = p[p["pop"] == p.groupby("poll_id")["pop"].transform("min")]
    q = p.groupby("poll_id").agg(date=("mid_date", "first"), election_date=("election_date", "first"),
                                 d_pct=("d_pct", "mean"), r_pct=("r_pct", "mean"), sample=("sample_size", "mean"))
    d = q.groupby(["date", "election_date"]).agg(d_pct=("d_pct", "mean"), r_pct=("r_pct", "mean"),
                                                 npolls=("d_pct", "size"), sample=("sample", "sum")).reset_index()
    # days from the middle of the field period, as in the source (the poll table counts from the last day)
    d["days_to_election"] = (pd.to_datetime(d.election_date) - pd.to_datetime(d.date)).dt.days
    return d.assign(cycle=cycle, d_incumbent_party=D_INCUMBENT[cycle], source_version="polls",
                    npolls=d.npolls.astype(float))


def polls_check(w):
    """The method of from_polls against the source, on the one cycle both cover (2016): two-party margin by day."""
    b = from_polls(2016)
    b["ours"] = 100 * (b.d_pct - b.r_pct) / (b.d_pct + b.r_pct)
    s = w[w.cycle == 2016]
    j = b.merge(s[["date", "margin_2p", "npolls"]], on="date", how="outer", suffixes=("", "_src"))
    both = j.dropna(subset=["ours", "margin_2p"])
    gap = both.ours - both.margin_2p
    late = both[both.days_to_election <= 150]
    wk = both.assign(week=both.days_to_election // 7).groupby("week")[["ours", "margin_2p"]].mean()
    print()
    print("check of the 2020 build: 2016 built the same way from our polls, against the source 2016 rows")
    print(f"  days with a reading: ours {b.date.nunique()}, source {len(s)}, both {len(both)}")
    print(f"  two-party margin, ours minus source: mean {gap.mean():+.2f}, mean abs {gap.abs().mean():.2f} by day; "
          f"last 150 days mean {(late.ours - late.margin_2p).mean():+.2f}, mean abs "
          f"{(late.ours - late.margin_2p).abs().mean():.2f}; by week mean abs "
          f"{(wk.ours - wk.margin_2p).abs().mean():.2f}, correlation {wk.ours.corr(wk.margin_2p):.2f}")
    print(f"  polls: ours {int(b.npolls.sum())}, source {int(s.npolls.sum())}")


def build():
    d = extract()
    d = d[~d.electionyr.isin([2008, 2012])].assign(source_version="2018")      # see the docstring
    d = pd.concat([d, extract_2016_version().assign(source_version="2016")], ignore_index=True)
    d["cycle"] = d.electionyr.astype(int)
    two = d[d.partyid.isin([1, 2])]         # 1 = the Democrat, 2 = the Republican, in every cycle
    w = two.pivot_table(index=["cycle", "polldate", "elecdate", "daysbeforeED"], columns="partyid",
                        values=["poll_", "vote_"]).reset_index()
    w.columns = ["cycle", "date", "election_date", "days_to_election", "d_pct", "r_pct", "d_vote", "r_vote"]
    meta = two[two.partyid == 1].set_index(["cycle", "polldate"])[["npolls", "sample", "inc_", "source_version"]]
    w = w.join(meta, on=["cycle", "date"]).rename(columns={"inc_": "d_incumbent_party"})
    w = pd.concat([w, from_polls(2020)], ignore_index=True)
    assert 2024 not in set(w.cycle)
    w["margin_2p"] = 100 * (w.d_pct - w.r_pct) / (w.d_pct + w.r_pct)
    # The result comes from our own table (state_presidential_history.csv). The source's agrees with it within 0.2
    # points in every cycle but 2008, where the 2016 version carries 55.4-44.6 against the actual 53.7-46.3.
    ours = pd.read_csv(INTERIM / "state_presidential_history.csv").groupby("year").national_margin_2p.first()
    w["result_margin_2p"] = w.cycle.map(ours)
    w["days_to_election"] = w.days_to_election.astype(int)
    w["d_incumbent_party"] = w.d_incumbent_party.astype(int)
    w = w[["cycle", "date", "election_date", "days_to_election", "d_pct", "r_pct", "margin_2p", "npolls", "sample",
           "d_incumbent_party", "result_margin_2p", "source_version"]].sort_values(["cycle", "date"])
    w.round(3).to_csv(INTERIM / "president_national_poll_days.csv", index=False)
    w["wt"] = w.npolls.fillna(1)            # 2008 has no poll counts: each day counts once
    g = w.groupby("cycle")
    last = w[w.days_to_election <= 14].groupby("cycle").apply(
        lambda x: (x.margin_2p * x.wt).sum() / x.wt.sum(), include_groups=False)
    summ = pd.DataFrame({"poll_days": g.size(), "polls": g.npolls.sum().round().astype(int),
                         "first_poll_days_out": g.days_to_election.max(),
                         "days_60_to_200_out": w[w.days_to_election.between(60, 200)].groupby("cycle").size(),
                         "final_2w_margin": last.round(1), "result": g.result_margin_2p.first().round(1)})
    summ["miss"] = (summ.final_2w_margin - summ.result).round(1)
    print(f"president_national_poll_days.csv: {len(w)} poll-days, {w.cycle.nunique()} cycles")
    print(summ.to_string())
    crosscheck(w[w.source_version != "polls"])
    book_check(w)
    polls_check(w)


def book_check(w):
    """Against Erikson and Wlezien's own file (the last 300 days of 1952-2012): the Democrat's two-party share."""
    from common import fetch_linked
    f = fetch_linked("erikson_wlezien", "Timeline_Poll_Data.xlsx", BOOK_URL, BOOK_PAGE,
                     meta={"title": "Poll Data for Erikson and Wlezien 2012, The Timeline of Presidential Elections",
                           "note": "the page's link is dead; this is the Internet Archive capture of 2022-02-22"})
    b = pd.read_excel(f, engine="openpyxl")
    b.columns = ["cycle", "til", "raw", "interp"]
    b["raw"] = pd.to_numeric(b.raw, errors="coerce")
    b = b.dropna(subset=["raw"]).assign(days_to_election=lambda x: -x.til)
    ours = w.assign(ours=50 + w.margin_2p / 2)
    ours.loc[ours.cycle == 2012, "days_to_election"] -= 1     # the 2016 version dates 2012 a day earlier
    j = b.merge(ours, on=["cycle", "days_to_election"], how="left")
    j["gap"] = j.raw - j.ours
    out = j.groupby("cycle").agg(book_days=("raw", "size"), matched=("ours", "count"),
                                 within_0_1=("gap", lambda x: (x.abs() < 0.1).mean()),
                                 mean_abs_gap=("gap", lambda x: x.abs().mean()))
    print("\ncheck against the book's file, Democratic two-party share by day:")
    print(out.round(2).to_string())
    worst = out[(out.matched < out.book_days - 2) | (out.within_0_1 < 0.5)]
    if len(worst):
        raise SystemExit(f"the series no longer matches the book's file in {list(worst.index)}")


def crosscheck(w):
    """Against president_general_polls.csv national polls, 2004-2016: the same days' two-party margins."""
    p = pd.read_csv(INTERIM / "president_general_polls.csv", low_memory=False)
    p = p[(p.geo == "US") & ~p.presumptive & p.cycle.isin(w.cycle.unique())]
    p["m2"] = 100 * (p.d_pct - p.r_pct) / (p.d_pct + p.r_pct)
    p["week"] = p.days_to_election // 7
    ours = p.groupby(["cycle", "poll_id"]).agg(m2=("m2", "mean"), week=("week", "first")).groupby(["cycle", "week"]).m2.mean()
    w = w.assign(week=w.days_to_election // 7)
    theirs = w.groupby(["cycle", "week"]).apply(lambda x: (x.margin_2p * x.wt).sum() / x.wt.sum(),
                                                include_groups=False)
    j = pd.concat({"ours": ours, "jw": theirs}, axis=1).dropna().reset_index()
    j["gap"] = j.ours - j.jw
    out = j.groupby("cycle").agg(weeks=("gap", "size"), mean_gap=("gap", "mean"),
                                 mean_abs_gap=("gap", lambda x: x.abs().mean()), corr=("ours", lambda x: x.corr(j.loc[x.index, "jw"])))
    print("\ncross-check, weekly national two-party margin: our polls minus Jennings-Wlezien")
    print(out.round(2).to_string())


if __name__ == "__main__":
    build()
