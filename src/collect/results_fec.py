"""MIT Election Lab returns, the Broockman district file, and FEC candidates/financial totals (DEMO_KEY).

medsl      Senate 1976-2024 from Harvard Dataverse (CC0). The House file there (1976-2024, CC0) sits behind a
           guestbook form, which this script does not fill in; the House file comes from the lab's own GitHub copy,
           which stops at 2018 (pinned commit). house_history.csv already covers 2006-2024 from other sources.
broockman  David Broockman's replication file for "Do Congressional Candidates Have Reverse Coattails?" (Political
           Analysis 2009; doi:10.7910/DVN/DCKUNX, CC0): the Democratic two-party share for president and for the
           House in every district, 1952-2004. It has no state or district columns; rows have to be matched to
           districts on the House share (DA-2).
"""
import json
import time

from common import fetch, raw_dir, SESSION, env_key

DATAVERSE = {"house": "doi:10.7910/DVN/IG0UN2", "senate": "doi:10.7910/DVN/PEJ5QU"}


MEDSL_GITHUB_SHA = "fe67c056502fc09ddb1ace2ff8f87c53233a744e"       # MEDSL/constituency-returns, 2026-02-12
BROOCKMAN_FILE = 2886556                                            # RvsCtlsReplication to post.dta


def medsl():
    meta = SESSION.get("https://dataverse.harvard.edu/api/datasets/:persistentId/",
                       params={"persistentId": DATAVERSE["senate"]}, timeout=60).json()["data"]["latestVersion"]
    for f in meta["files"]:
        df = f["dataFile"]
        if df["filename"].endswith(".tab"):
            p = fetch("medsl", df["filename"],
                      f"https://dataverse.harvard.edu/api/access/datafile/{df['id']}?format=original", timeout=600)
            print("medsl senate", df["filename"], p.stat().st_size)
    p = fetch("medsl", "1976-2018-house.csv", "https://raw.githubusercontent.com/MEDSL/constituency-returns/"
              f"{MEDSL_GITHUB_SHA}/1976-2018-house.csv", timeout=600)
    print("medsl house", p.name, p.stat().st_size)


def broockman():
    p = fetch("broockman_2009", "RvsCtlsReplication.dta",
              f"https://dataverse.harvard.edu/api/access/datafile/{BROOCKMAN_FILE}?format=original", timeout=300)
    print("broockman", p.name, p.stat().st_size)


def fec(cycle=2026):
    """Candidate financial totals for House and Senate. DEMO_KEY is rate-limited, so paginate gently."""
    d = raw_dir("fec")
    for office in ["S", "H"]:
        out = d / f"totals_{office}_{cycle}.json"
        if out.exists():
            continue
        rows, page = [], 1
        while True:
            for attempt in range(6):
                r = SESSION.get("https://api.open.fec.gov/v1/candidates/totals/",
                                params={"api_key": env_key("fec_api_key", "DEMO_KEY"), "cycle": cycle, "election_year": cycle,
                                        "office": office, "per_page": 100, "page": page,
                                        "is_active_candidate": "true", "sort": "-receipts"}, timeout=60)
                if r.status_code == 429:
                    time.sleep(30 * (attempt + 1))
                    continue
                r.raise_for_status()
                break
            j = r.json()
            rows += j["results"]
            pages = j["pagination"]["pages"]
            print(f"fec {office} page {page}/{pages}", flush=True)
            if page >= pages:
                break
            page += 1
            time.sleep(0.3 if env_key("fec_api_key") else 1.5)
        out.write_text(json.dumps(rows))
        print("fec", office, len(rows))


if __name__ == "__main__":
    import sys
    for w in sys.argv[1:] or ["medsl", "broockman", "fec"]:
        globals()[w]()
