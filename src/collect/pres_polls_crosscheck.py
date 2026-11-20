"""Cross-check of the presidential poll sources against each other (DA-5).

president_general_polls.csv takes one source per cycle and geography (pres_polls.py). Most cycles have two or three
independent compilations, so this script matches them poll by poll and compares what they say:

  2004  Wikipedia (states)                    538 raw_polls (late)
  2008  Wikipedia            The Economist    538 raw_polls (late)
  2012  Wikipedia            The Economist    538 raw_polls (late)     (Wikipedia's national page starts in September)
  2016  538 2016 forecast    The Economist    538 raw_polls (late)     Wikipedia (national only, from June)
  2020  538 archive                           538 raw_polls (late)

2000 has one source (raw_polls) and 2024 one (the 538 archive); neither can be checked here.

Matching: a poll in source A is "found" in source B if B has a poll in the same place whose midpoint is within two
days and whose pollster name shares a distinctive word; of several candidates the one with the closest shares is taken
(a poll often has likely- and registered-voter versions, two-way and multi-way). A is first cut to B's reach: its
date range and, where B has only states or only late polls, those.

Outputs (data/interim/):
  president_poll_crosscheck.csv        one row per cycle and ordered source pair: polls compared, share found,
                                       share agreeing within 1 point of margin, mean and mean absolute difference
  president_poll_crosscheck_avg.csv    one row per cycle, window and source pair: how far apart the two sources'
                                       plain poll averages are, place by place (the number that matters for a model)
  president_poll_crosscheck_diffs.csv  matched polls whose margins differ by more than 2 points, for reading

Run:  python src/collect/pres_polls_crosscheck.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pres_polls as P  # noqa: E402

INTERIM = P.INTERIM
STOP = set("""the of and for at in a poll polls polling research university college news survey surveys opinion
institute center centre group associates strategies strategy inc llc co company corporation corp public reports
report state national times post daily journal tv radio television media communications consulting marketing
interactive international online data analytics tracking""".split())
ALIAS = {"ppp": "policy", "arg": "american", "wsj": "wall", "nyt": "york", "abc": "abc", "wapo": "washington",
         "ibd": "investor", "investors": "investor", "tipp": "tipp", "lat": "angeles", "mason": "mason",
         "dixon": "mason", "pulse": "rasmussen", "yougov": "yougov", "polimetrix": "yougov", "zogby": "zogby",
         "srbi": "srbi", "orc": "cnn", "upi": "upi", "cvoter": "cvoter", "surveyusa": "surveyusa", "susa": "surveyusa",
         "selzer": "selzer", "quinnipiac": "quinnipiac", "village": "orc"}


def key(name):
    """Distinctive lower-case words of a pollster name."""
    toks = re.findall(r"[a-z0-9]+", re.sub(r"\(.*?\)", lambda m: " " + m.group(0)[1:-1] + " ", str(name).lower()))
    out = {ALIAS.get(t, t) for t in toks if t not in STOP and len(t) > 1}
    return out or set(toks)


def sources(cycle):
    raw = P.raw_polls(all_rows=True)
    raw = raw[raw.cycle == cycle]
    if cycle == 2004:
        s = {"Wikipedia": P.wiki_states(2004)}
    elif cycle in (2008, 2012):
        s = {"Wikipedia": pd.concat([P.wiki_states(cycle), P.wiki_national(cycle)]), "Economist": P.economist(cycle)}
    elif cycle == 2016:
        s = {"538 forecast": P.fte2016(), "Economist": P.economist(2016), "Wikipedia (national)": P.wiki_national(2016)}
    else:
        a = P.archive()
        s = {"538 archive": a[(a.cycle == 2020) & ~a.presumptive]}
    s["538 raw_polls"] = raw
    out = {}
    for name, d in s.items():
        d = d.dropna(subset=["d_pct", "r_pct", "mid_date"]).copy()
        d["margin"] = d.d_pct.astype(float) - d.r_pct.astype(float)
        d["key"] = d.pollster.map(key)
        d["days"] = (pd.to_datetime(d.election_date) - d.mid_date).dt.days
        out[name] = d
    return out


def match(a, b):
    """For each poll in a (cut to b's reach): the closest same-place, same-pollster, same-dates row of b, if any."""
    lo, hi = b.mid_date.min() - pd.Timedelta(days=2), b.mid_date.max() + pd.Timedelta(days=2)
    a = a[(a.mid_date >= lo) & (a.mid_date <= hi) & a.geo.isin(set(b.geo))]
    by_geo = {g: x for g, x in b.groupby("geo")}
    rows = []
    for r in a.itertuples():
        x = by_geo[r.geo]
        x = x[(x.mid_date - r.mid_date).abs() <= pd.Timedelta(days=2)]
        x = x[[bool(r.key & k) for k in x.key]] if len(x) else x
        if len(x) == 0:
            rows.append((r.poll_id, r.geo, r.pollster, r.mid_date, r.d_pct, r.r_pct, None, None, None, None))
            continue
        cost = (x.d_pct.astype(float) - r.d_pct).abs() + (x.r_pct.astype(float) - r.r_pct).abs()
        m = x.loc[cost.idxmin()]
        rows.append((r.poll_id, r.geo, r.pollster, r.mid_date, r.d_pct, r.r_pct, m.pollster, m.d_pct, m.r_pct,
                     cost.min()))
    m = pd.DataFrame(rows, columns=["poll_id", "geo", "pollster", "mid_date", "d_pct", "r_pct", "pollster_b", "d_pct_b",
                                    "r_pct_b", "cost"])
    # a poll with several questions counts once: found if any question is, with its best-agreeing question
    m["found"] = m.cost.notna()
    m = m.sort_values(["found", "cost"], ascending=[False, True]).drop_duplicates("poll_id")
    m["margin_diff"] = (m.d_pct - m.r_pct) - (m.d_pct_b.astype(float) - m.r_pct_b.astype(float))
    return m


WINDOWS = {"final 3 weeks": (0, 21), "22-60 days": (22, 60), "61-120 days": (61, 120), "121-300 days": (121, 300)}


def averages(cycle, name_a, a, name_b, b):
    """Plain average margin per place and window in each source, where both have 2+ polls; then the gap."""
    out = []
    for w, (lo, hi) in WINDOWS.items():
        fa = a[(a.days >= lo) & (a.days <= hi)].groupby(["geo", "poll_id"]).margin.mean().groupby("geo").agg(["mean", "size"])
        fb = b[(b.days >= lo) & (b.days <= hi)].groupby(["geo", "poll_id"]).margin.mean().groupby("geo").agg(["mean", "size"])
        j = fa.join(fb, lsuffix="_a", rsuffix="_b", how="inner")
        j = j[(j.size_a >= 2) & (j.size_b >= 2)]
        if len(j) < 3:
            continue
        gap = j.mean_a - j.mean_b
        out.append({"cycle": cycle, "window": w, "source_a": name_a, "source_b": name_b, "places": len(j),
                    "mean_gap": gap.mean(), "mean_abs_gap": gap.abs().mean(), "max_abs_gap": gap.abs().max(),
                    "worst_place": gap.abs().idxmax(), "correlation": j.mean_a.corr(j.mean_b)})
    return out


def run():
    summ, avg, diffs = [], [], []
    for cycle in (2004, 2008, 2012, 2016, 2020):
        s = sources(cycle)
        names = list(s)
        for i, na in enumerate(names):
            for nb in names:
                if na == nb:
                    continue
                m = match(s[na], s[nb])
                f = m[m.found]
                summ.append({"cycle": cycle, "source_a": na, "source_b": nb, "polls_a_in_reach_of_b": len(m),
                             "found_in_b": len(f), "found_share": len(f) / len(m) if len(m) else None,
                             "agree_within_1pt": (f.margin_diff.abs() <= 1).mean() if len(f) else None,
                             "exact": (f.cost == 0).mean() if len(f) else None,
                             "mean_margin_diff": f.margin_diff.mean() if len(f) else None,
                             "mean_abs_margin_diff": f.margin_diff.abs().mean() if len(f) else None})
                big = f[f.margin_diff.abs() > 2].assign(cycle=cycle, source_a=na, source_b=nb)
                diffs.append(big)
            for nb in names[i + 1:]:
                avg += averages(cycle, na, s[na], nb, s[nb])
    summ, avg = pd.DataFrame(summ), pd.DataFrame(avg)
    diffs = pd.concat(diffs)[["cycle", "source_a", "source_b", "geo", "mid_date", "pollster", "d_pct", "r_pct",
                              "pollster_b", "d_pct_b", "r_pct_b", "margin_diff"]]
    diffs["mid_date"] = diffs.mid_date.dt.strftime("%Y-%m-%d")
    summ.round(3).to_csv(INTERIM / "president_poll_crosscheck.csv", index=False)
    avg.round(3).to_csv(INTERIM / "president_poll_crosscheck_avg.csv", index=False)
    diffs.sort_values(["cycle", "geo", "mid_date"]).round(2).to_csv(INTERIM / "president_poll_crosscheck_diffs.csv",
                                                                    index=False)
    pd.set_option("display.width", 250)
    print("\nPoll by poll (a's polls within b's reach):")
    print(summ.round(2).to_string(index=False))
    print("\nPoll averages by place and window (places where both sources have 2+ polls):")
    print(avg.round(2).to_string(index=False))
    print(f"\n{len(diffs)} matched pairs differ by more than 2 points of margin -> president_poll_crosscheck_diffs.csv")


if __name__ == "__main__":
    run()
