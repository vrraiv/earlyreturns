"""Polling collectors: VoteHub (2026) and archived 538 files (2018-2024; presidential 2020-2024)."""
import sys

from common import fetch

WAYBACK_538 = {
    # file -> wayback timestamp (Feb 2025 snapshots, verified to exist)
    "senate_polls_historical.csv": "20250210111722",
    "house_polls_historical.csv": "20250209145115",
    "generic_ballot_polls_historical.csv": "20250207030755",
    "president_approval_polls_historical.csv": "20250305204636",
    "governor_polls_historical.csv": None,
}
# Presidential polls (DA-5), pinned to the captures checked on 2026-11-20: the general-election file holds the full
# 2020 and 2024 cycles (state and national), the primary file both parties' 2020 and 2024 primaries.
WAYBACK_538_PRES = {
    "president_polls_historical.csv": ("20250205084149", "polls/data"),
    "president_primary_polls_historical.csv": ("20250212092020", "polls/data"),
    # 2016's full cycle (Nov 2015 to Election Day), as the 2016 forecast used it
    "president_general_polls_2016.csv": ("20250305151657", "general-model"),
}
# The Economist's 2020 presidential model (github.com/TheEconomist/us-potus-model, MIT licence), pinned to its last
# commit: full-cycle state and national polls for 2008 and 2012, compiled from HuffPost Pollster and others.
ECONOMIST_SHA = "b89e602ec03e81c797c66cf2743af6fdae4aa526"
ECONOMIST_FILES = ["all_polls_2008.csv", "all_polls_2012.csv"]
GH = "https://raw.githubusercontent.com/fivethirtyeight/data/master/"


def votehub():
    p = fetch("votehub", "polls.json", "https://api.votehub.com/polls", skip_existing=False)
    print("votehub", p, p.stat().st_size)


def wayback_538():
    import requests
    for f, ts in WAYBACK_538.items():
        if ts is None:
            j = requests.get("https://archive.org/wayback/available",
                             params={"url": f"projects.fivethirtyeight.com/polls/data/{f}", "timestamp": "20250201"},
                             timeout=60).json()
            snap = j["archived_snapshots"].get("closest")
            if not snap:
                print("no snapshot", f)
                continue
            ts = snap["timestamp"]
        url = f"https://web.archive.org/web/{ts}id_/https://projects.fivethirtyeight.com/polls/data/{f}"
        try:
            p = fetch("538_wayback", f, url, timeout=300)
            print("538", f, p.stat().st_size)
        except Exception as e:  # noqa: BLE001
            print("FAILED", f, e)


def wayback_538_pres():
    for f, (ts, path) in WAYBACK_538_PRES.items():
        url = f"https://web.archive.org/web/{ts}id_/https://projects.fivethirtyeight.com/{path}/{f}"
        p = fetch("538_wayback", f, url, timeout=600)
        print("538", f, p.stat().st_size)


def economist_potus():
    for f in ECONOMIST_FILES:
        url = f"https://raw.githubusercontent.com/TheEconomist/us-potus-model/{ECONOMIST_SHA}/data/{f}"
        p = fetch("economist_potus", f, url)
        print("economist", f, p.stat().st_size)


def github_538():
    for path in ["pollster-ratings/raw_polls.csv", "pollster-ratings/pollster-ratings-combined.csv",
                 "congress-generic-ballot/generic_topline_historical.csv"]:
        p = fetch("538_github", path.split("/")[-1], GH + path)
        print("gh", path, p.stat().st_size)


if __name__ == "__main__":
    which = sys.argv[1:] or ["votehub", "wayback_538", "github_538"]
    for w in which:
        globals()[w]()
