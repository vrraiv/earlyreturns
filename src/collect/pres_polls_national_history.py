"""National presidential trial-heat polls by day, 1952-2016 without 2008 (DA-5): the long history for poll decay and convention
bounces, which the poll-level table (president_general_polls.csv, from 2004) is too short to estimate.

Source: Will Jennings and Christopher Wlezien, "Election Polling Errors across Time and Space", Nature Human
Behaviour 2 (2018), replication data on Harvard Dataverse, doi:10.7910/DVN/8421DX, CC0. The file covers 45 countries;
for each election and party it has one row per day with the average of the polls centred on that day (poll_), their
number (npolls) and pooled sample, and the result (vote_). It is a daily series, not a list of polls: there are no
pollster names, and a day with no poll has no value.

The 290 MB file is fetched into data/raw/jennings_wlezien/<date>/ and not committed (gitignored); the United States
presidential rows that have a poll are saved beside it as us_presidential_poll_days.csv, which is committed.

Two cautions found on 2026-11-20:
- 2008 is dropped. The file's 2008 series is its 2004 series again (91% of days carry identical shares at the same
  distance from the election; its last fortnight has McCain ahead). The results attached to it are 2008's.
  president_general_polls.csv has 2008 from Wikipedia.
- 2012 runs about 2 points more Republican than The Economist's compilation of the same months. It holds 1,044
  poll readings against 191 there, so daily tracking polls are probably counted on each release.

Output: data/interim/president_national_poll_days.csv, one row per cycle and day with a poll: the Democrat's and
Republican's poll shares (as published: of all respondents to 2012, of the two-party total in 2016), the two-party
margin, polls and sample that day, and the result's two-party margin. Third candidates (1968, 1980, 1992, 1996) are
in the source but not carried here.

Run:  python src/collect/pres_polls_national_history.py   (prints the cross-check against our 2004-2016 national polls)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch, latest  # noqa: E402

INTERIM = ROOT / "data" / "interim"
URL = "https://dataverse.harvard.edu/api/access/datafile/3107210"     # LONG_MI_NATURE_20180111.tab
BIG, SMALL = "LONG_MI_NATURE_20180111.tab", "us_presidential_poll_days.csv"


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


def build():
    d = extract()
    d["cycle"] = d.electionyr.astype(int)
    d = d[d.cycle != 2008]                  # a copy of 2004's polls: see the docstring
    two = d[d.partyid.isin([1, 2])]         # 1 = the Democrat, 2 = the Republican, in every cycle
    w = two.pivot_table(index=["cycle", "polldate", "elecdate", "daysbeforeED"], columns="partyid",
                        values=["poll_", "vote_"]).reset_index()
    w.columns = ["cycle", "date", "election_date", "days_to_election", "d_pct", "r_pct", "d_vote", "r_vote"]
    meta = two[two.partyid == 1].set_index(["cycle", "polldate"])[["npolls", "sample", "inc_"]]
    w = w.join(meta, on=["cycle", "date"]).rename(columns={"inc_": "d_incumbent_party"})
    w["margin_2p"] = 100 * (w.d_pct - w.r_pct) / (w.d_pct + w.r_pct)
    w["result_margin_2p"] = 100 * (w.d_vote - w.r_vote) / (w.d_vote + w.r_vote)
    w["days_to_election"] = w.days_to_election.astype(int)
    w["d_incumbent_party"] = w.d_incumbent_party.astype(int)
    w = w[["cycle", "date", "election_date", "days_to_election", "d_pct", "r_pct", "margin_2p", "npolls", "sample",
           "d_incumbent_party", "result_margin_2p"]].sort_values(["cycle", "date"])
    w.round(3).to_csv(INTERIM / "president_national_poll_days.csv", index=False)
    g = w.groupby("cycle")
    last = w[w.days_to_election <= 14].groupby("cycle").apply(
        lambda x: (x.margin_2p * x.npolls).sum() / x.npolls.sum(), include_groups=False)
    summ = pd.DataFrame({"poll_days": g.size(), "polls": g.npolls.sum().round().astype(int),
                         "first_poll_days_out": g.days_to_election.max(),
                         "days_60_to_200_out": w[w.days_to_election.between(60, 200)].groupby("cycle").size(),
                         "final_2w_margin": last.round(1), "result": g.result_margin_2p.first().round(1)})
    summ["miss"] = (summ.final_2w_margin - summ.result).round(1)
    print(f"president_national_poll_days.csv: {len(w)} poll-days, {w.cycle.nunique()} cycles")
    print(summ.to_string())
    crosscheck(w)


def crosscheck(w):
    """Against president_general_polls.csv national polls, 2004-2016: the same days' two-party margins."""
    p = pd.read_csv(INTERIM / "president_general_polls.csv", low_memory=False)
    p = p[(p.geo == "US") & ~p.presumptive & p.cycle.isin(w.cycle.unique())]
    p["m2"] = 100 * (p.d_pct - p.r_pct) / (p.d_pct + p.r_pct)
    p["week"] = p.days_to_election // 7
    ours = p.groupby(["cycle", "poll_id"]).agg(m2=("m2", "mean"), week=("week", "first")).groupby(["cycle", "week"]).m2.mean()
    w = w.assign(week=w.days_to_election // 7)
    theirs = w.groupby(["cycle", "week"]).apply(lambda x: (x.margin_2p * x.npolls).sum() / x.npolls.sum(),
                                                include_groups=False)
    j = pd.concat({"ours": ours, "jw": theirs}, axis=1).dropna().reset_index()
    j["gap"] = j.ours - j.jw
    out = j.groupby("cycle").agg(weeks=("gap", "size"), mean_gap=("gap", "mean"),
                                 mean_abs_gap=("gap", lambda x: x.abs().mean()), corr=("ours", lambda x: x.corr(j.loc[x.index, "jw"])))
    print("\ncross-check, weekly national two-party margin: our polls minus Jennings-Wlezien")
    print(out.round(2).to_string())


if __name__ == "__main__":
    build()
