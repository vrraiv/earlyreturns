"""Official state results for House races: the state's own count replaces Wikipedia's, district by district.

The same state results systems official_senate.py reads for the Senate also publish every House contest, mostly in the
very same file: Georgia, Iowa, South Carolina, Louisiana and Texas reuse the files official_senate.py already saved that
day (nothing is fetched twice). Montana, Nebraska and Minnesota keep House results in separate files, fetched here into
data/raw/official/<ST>/<date>/. California's House numbers already come from its Secretary of State (results_margins.py).

Margins use the Wikipedia path's House definition (results_margins.margins_rcv): the leading Democrat vs. the leading
Republican, two-party. Every official margin is compared with Wikipedia's from the same run; a difference over 0.5
points is written into the race's `issues`, so check_scorecard.py puts it up for review.

The same rules decide when a count has settled (results_margins.settledness), judged on the official source's own
history: the earlier days' saved files are re-parsed into data/scorecard/margins_history_house.csv, so an official
count is judged on as many days as the files go back, not from the day this script was added. When the state certifies,
the same files carry the certified count, and the race keeps the official source.

Writes data/scorecard/official_house.csv (one row per district: official margin, Wikipedia margin, difference) and
replaces the matching rows of data/scorecard/margins_house.csv.

Run:  python src/collect/official_house.py          (fetch the House-only files, then parse every state)
      python src/collect/official_house.py parse    (re-parse the saved files, fetching nothing)
Run after official_senate.py (src/run_scorecard.py does), which saves the shared files.
"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import RAW, ROOT, SESSION, raw_dir  # noqa: E402
from official_senate import ADAPTERS, get, norm_title, party_code  # noqa: E402
from results import FINAL, OUT  # noqa: E402
import results_margins as RM  # noqa: E402

DIFF_REVIEW = 0.5   # points: an official margin this far from Wikipedia's is flagged for review
# Louisiana's November House vote is an all-party primary and Georgia requires a majority: a contest where nobody won a
# majority goes to a December runoff, and "leading Democrat vs. leading Republican" in a field of ten says nothing about
# the race. Those stay unscored here (the runoff's count is what the forecast's margin is about).
MAJORITY_STATES = {"LA", "GA"}


def runoff(st, contest):
    v = [c["votes"] for c in contest["candidates"]]
    return st in MAJORITY_STATES and sum(v) > 0 and 2 * max(v) <= sum(v)
ORDINAL = r"(\d+)(?:ST|ND|RD|TH)?"


def cands_total_ok(cands, total):
    return total is None or sum(c["votes"] for c in cands) == int(total)


def strip_suffix(name):
    """'James "Jim" Kingston (Rep)' / 'AUGUST PFLUGER (I)' -> the name alone ((I) = incumbent, not independent)."""
    return re.sub(r"(\s*\([^)]*\))+\s*$", "", str(name)).replace('"', "").strip()


# ---------------- per-state House parsers ----------------
# Each: files -> the raw file names it reads in data/raw/official/<ST>/<date>/; fetch(st) -> fetch any House-only files
# (the shared ones come from official_senate.py); parse(paths) -> {"source", "url", "as_of", "contests": {district:
# {"candidates": [{"name", "party", "votes"}], "reporting", "complete"[, "as_of"]}}}.
HOUSE = {}


def house(*states):
    def deco(cls):
        for s in states:
            HOUSE[s] = cls
        return cls
    return deco


class Shared:
    """Reads the files official_senate.py's adapter for the state saved; fetches nothing of its own."""
    files = []

    @classmethod
    def fetch(cls, st):
        return None

    @classmethod
    def source(cls, st):
        return ADAPTERS[st].name


class Clarity(Shared):
    files = ["summary.json", "electionsettings.json"]
    TITLE = re.compile(r"^(?:U S|UNITED STATES)\s+(?:HOUSE OF REPRESENTATIVES|REPRESENTATIVE)\W*DISTRICT\s+(\d+)$")

    @classmethod
    def parse(cls, paths, st):
        summ = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        sett = json.loads(Path(paths[1]).read_text(encoding="utf-8"))
        out = {}
        for c in summ:
            m = cls.TITLE.match(norm_title(c.get("C")))
            if not m:
                continue
            d = int(m.group(1))
            if d in out:
                raise ValueError(f"two contests for district {d}")
            cands = []
            for name, p, v in zip(c["CH"], c.get("P") or [""] * len(c["CH"]), c["V"]):
                name = re.sub(rf"^{re.escape(p)}\s+", "", name) if p else name   # SC prefixes the party
                cands.append({"name": name, "party": p, "votes": int(v)})
            if not cands_total_ok(cands, (c.get("T") or [None])[0]):
                raise ValueError(f"district {d}: candidate votes don't add up to the contest total")
            out[d] = {"candidates": cands, "reporting": f"counties reporting {c.get('PR')}/{c.get('TP')}",
                      "complete": bool(c.get("TP")) and c.get("PR") == c.get("TP")
                                  and sett.get("stateprecinctsreporting") == sett.get("stateprecinctsparticipating")}
        return {"as_of": sett.get("websiteupdatedat"), "url": ADAPTERS[st].base, "contests": out}


house("SC", "IA")(Clarity)


@house("GA")
class Georgia(Shared):
    files = ["election_data.json"]
    TITLE = re.compile(r"^US HOUSE OF REPRESENTATIVES\s*-\s*DISTRICT\s+(\d+)$")

    @classmethod
    def parse(cls, paths, st):
        d = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        en = lambda names: next((n["text"] for n in names if n.get("languageCode", n.get("languageId", "en")).startswith("en")),
                                names[0]["text"] if names else "")
        out = {}
        for b in d["ballotItems"]:
            m = cls.TITLE.match(norm_title(en(b["name"])))
            if not m or b.get("parentJurisdictionName"):
                continue
            k = int(m.group(1))
            if k in out:
                raise ValueError(f"two ballot items for district {k}")
            cands = [{"name": strip_suffix(en(o["name"])), "party": (o.get("party") or {}).get("abbreviation", ""),
                      "votes": int(o["voteCount"])} for o in b["summaryResults"]["ballotOptions"]]
            if not cands_total_ok(cands, b.get("voteTotal")):
                raise ValueError(f"district {k}: candidate votes don't add up to the contest total")
            rs = b.get("reportingStatus") or {}
            out[k] = {"candidates": cands, "reporting": f"counties reporting {rs.get('reportingUnits')}/{rs.get('totalUnits')}",
                      "complete": bool(rs.get("totalUnits")) and rs.get("reportingUnits") == rs.get("totalUnits")}
        el = d.get("election", {})
        return {"as_of": el.get("asOf"), "url": ADAPTERS[st].API + "/elections/Georgia", "contests": out,
                "certified": bool(el.get("isOfficialResults"))}


@house("LA")
class Louisiana(Shared):
    files = ["RacesCandidates_Multiparish.json", "Votes_Multiparish.json"]
    TITLE = re.compile(r"^U S REPRESENTATIVE\s*-*\s*" + ORDINAL + r" CONGRESSIONAL DISTRICT$")

    @classmethod
    def parse(cls, paths, st):
        lst = lambda x: x if isinstance(x, list) else [x]
        rc = json.loads(Path(paths[0]).read_text(encoding="utf-8"))["Races"]
        vt = {r["ID"]: r for r in lst(json.loads(Path(paths[1]).read_text(encoding="utf-8"))["Races"]["Race"])}
        out = {}
        for race in lst(rc["Race"]):
            m = cls.TITLE.match(norm_title(race.get("SpecificTitle")))
            if not m:
                continue
            k = int(m.group(1))
            if k in out:
                raise ValueError(f"two races for district {k}")
            votes = vt[race["ID"]]
            vmap = {c["ID"]: int(c["VoteTotal"]) for c in lst(votes["Choice"])}
            cands = []
            for c in lst(race["Choice"]):
                p = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", c["Desc"])
                cands.append({"name": (p.group(1) if p else c["Desc"]).replace('"', ""), "party": p.group(2) if p else "", "votes": vmap[c["ID"]]})
            out[k] = {"candidates": cands,
                      "reporting": f"precincts {votes.get('PrecinctsReporting')}/{votes.get('PrecinctsExpected')}, absentee "
                                   f"{votes.get('NumAbsenteeReporting')}/{votes.get('NumAbsenteeExpected')}",
                      "complete": votes.get("PrecinctsReporting") == votes.get("PrecinctsExpected")
                                  and votes.get("NumAbsenteeReporting") == votes.get("NumAbsenteeExpected")}
        return {"as_of": f"{rc.get('WriteTime')} (Louisiana time)", "url": "https://voterportal.sos.la.gov/graphical", "contests": out}


@house("TX")
class Texas(Shared):
    files = ["election.json"]
    TITLE = re.compile(r"^U S REPRESENTATIVE DISTRICT\s+(\d+)$")

    @classmethod
    def parse(cls, paths, st):
        T = ADAPTERS[st]
        d = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        fed, home = T.unwrap(d["Federal"]), T.unwrap(d["Home"])
        cr = home.get("CountiesReporting", {})
        complete = bool(cr.get("CT")) and cr.get("CR") == cr.get("CT")
        out = {}
        for r in fed["Races"]:
            m = cls.TITLE.match(norm_title(r["N"]))
            if not m:
                continue
            k = int(m.group(1))
            if k in out:
                raise ValueError(f"two races for district {k}")
            cands = [{"name": strip_suffix(c["N"]).title(), "party": c.get("P", ""), "votes": int(c["V"])} for c in r.get("C", r.get("Candidates", []))]
            if not cands_total_ok(cands, r.get("T")):
                raise ValueError(f"district {k}: candidate votes don't add up to the race total")
            # the feed's timestamp tracks the server clock, so the evidence is a fingerprint of the district's own numbers
            # (as official_senate.Texas does for the Senate race)
            fp = hashlib.sha1(json.dumps(cands, sort_keys=True).encode()).hexdigest()[:12]
            out[k] = {"candidates": cands, "reporting": f"counties reporting {cr.get('CR')}/{cr.get('CT')} (statewide)",
                      "complete": complete, "as_of": f"district numbers {fp}"}
        return {"as_of": None, "url": "https://goelect.txelections.civixapps.com/ivis-enr-ui/races", "contests": out}


@house("MT")
class Montana:
    """The federal results page (saved by official_senate.py) lists each US House race with the race and office ids its
    county JSON service needs; one JSON per district, saved as house_<n>_by_county.json."""
    TITLE = re.compile(r"^UNITED STATES REPRESENTATIVE " + ORDINAL + r" CONGRESSIONAL$")
    PAGE = "resultsSW_FED.html"

    @classmethod
    def races(cls, html):
        """{district: (race id, office id)} from the page: the race name precedes its BuildCounty('FED', ...) button."""
        out = {}
        text = re.sub(r"\s+", " ", html)
        for m in re.finditer(r"BuildCounty\('FED',\s*'(\d+)',\s*'(\d+)'", text):
            before = re.sub(r"<[^>]+>", " ", text[max(0, m.start() - 20000):m.start()]).upper()
            names = re.findall(r"UNITED STATES (?:SENATOR|REPRESENTATIVE \d+(?:ST|ND|RD|TH) CONGRESSIONAL)", before)
            if names and names[-1].startswith("UNITED STATES REPRESENTATIVE"):
                out[int(re.search(r"(\d+)", names[-1]).group(1))] = (m.group(1), m.group(2))
        return out

    @classmethod
    def files_on(cls, day_dir):
        js = sorted(day_dir.glob("house_*_by_county.json"))
        return [day_dir / cls.PAGE] + js if js else []   # a day with only the Senate's copy of the page has no House data

    @classmethod
    def fetch(cls, st):
        page = get(st, cls.PAGE, ADAPTERS[st].PAGE)   # this day's copy, beside the district files it points to
        time.sleep(1.0)
        for k, (race, osn) in cls.races(page.read_text(encoding="utf-8", errors="replace")).items():
            get(st, f"house_{k}_by_county.json", ADAPTERS[st].DATA.format(race=race, osn=osn))
            time.sleep(1.0)

    @classmethod
    def source(cls, st):
        return ADAPTERS[st].name

    @classmethod
    def parse(cls, paths, st):
        html = Path(paths[0]).read_text(encoding="utf-8", errors="replace")
        out = {}
        for p in paths[1:]:
            rows = json.loads(Path(p).read_text(encoding="utf-8"))["d"] or []
            names = {r.get("RaceName", "").upper() for r in rows}
            m = cls.TITLE.match(norm_title(next(iter(names)))) if len(names) == 1 else None
            if not m:
                raise ValueError(f"{Path(p).name}: county rows aren't one US House contest ({sorted(names)[:3]})")
            k = int(m.group(1))
            tot, party = {}, {}
            for r in rows:
                tot[r["calcCandidate"]] = tot.get(r["calcCandidate"], 0) + int(r["calcCandidateVotes"] or 0)
                party[r["calcCandidate"]] = r.get("PartyName") or r.get("PartyCode")
            cnty = {r["CountyID"]: r for r in rows}
            full = sum(int(r.get("PrecinctsReporting") or 0) for r in cnty.values())
            allp = sum(int(r.get("TotalPrecincts") or 0) for r in cnty.values())
            out[k] = {"candidates": [{"name": n.title(), "party": party[n], "votes": v} for n, v in tot.items()],
                      "reporting": f"precincts fully reporting {full}/{allp}", "complete": allp > 0 and full == allp}
        upd = re.search(r"Results last updated:\s*([^<]+)", html)
        return {"as_of": (upd.group(1).strip() + " (Montana time)") if upd else None, "url": ADAPTERS[st].PAGE, "contests": out}


@house("NE")
class Nebraska:
    """Congressional-district CSV export (type=CG); the data time is read from the results page official_senate.py
    saves (the CSV's CurrentDateTime is the export time)."""
    CSV = "https://electionresults.nebraska.gov/resultsCSV.aspx?text=All&type=CG&map=DIST"

    @classmethod
    def files_on(cls, day_dir):
        return [day_dir / "congress.csv", day_dir / "index.html"]

    @classmethod
    def fetch(cls, st):
        get(st, "congress.csv", cls.CSV)
        if not (raw_dir(f"official/{st}") / "index.html").exists():   # official_senate.py normally saved it already
            get(st, "index.html", ADAPTERS[st].PAGE)

    @classmethod
    def source(cls, st):
        return ADAPTERS[st].name

    @classmethod
    def parse(cls, paths, st):
        import csv
        import io
        rows = list(csv.DictReader(io.StringIO(Path(paths[0]).read_text(encoding="utf-8-sig", errors="replace"))))
        out = {}
        for r in rows:
            if "REPRESENTATIVE IN CONGRESS" not in norm_title(r.get("RaceName")):
                continue
            k = int(re.search(r"(\d+)", r["AreaNum"]).group(1))
            c = out.setdefault(k, {"candidates": [], "race": r["RaceID"], "pr": str(r.get("PrecinctsReporting", "")).strip('="')})
            if c["race"] != r["RaceID"]:
                raise ValueError(f"two races for district {k}")
            c["candidates"].append({"name": " ".join(r["CandidateName"].split()), "party": r.get("PartyCode", ""), "votes": int(r["CandidateVotes"])})
        for k, c in out.items():
            a = c.pop("pr").split("/")
            c.pop("race")
            c.update(reporting=f"precincts {'/'.join(a)}", complete=len(a) == 2 and a[0] == a[1])
        html = Path(paths[1]).read_text(encoding="utf-8", errors="replace") if Path(paths[1]).exists() else ""
        upd = re.search(r"Results last updated:\s*(?:</span>\s*<span>)?\s*([^<]+)", html, re.I)
        return {"as_of": upd.group(1).strip() if upd else None, "url": ADAPTERS[st].PAGE, "contests": out}


@house("MN")
class Minnesota:
    """Media text file ushouse.txt, the same semicolon layout as ussenate.txt: office name f[4] ('U.S. Representative
    District 1'), name f[7], party f[10], precincts f[11]/f[12], votes f[13], office total f[15]."""
    URL = "https://electionresultsfiles.sos.mn.gov/20261103/ushouse.txt"
    # the district is in the office name ('U.S. Representative District 1') or, failing that, in the district field f[5]
    TITLE = re.compile(r"^U S REPRESENTATIVE(?:\s+DISTRICT)?(?:\s+(\d+))?$")

    @classmethod
    def files_on(cls, day_dir):
        return [day_dir / "ushouse.txt", day_dir / "ushouse.headers.json"]

    @classmethod
    def fetch(cls, st):
        r = SESSION.get(cls.URL, timeout=60)
        r.raise_for_status()
        d = raw_dir(f"official/{st}")
        (d / "ushouse.txt").write_bytes(r.content)
        (d / "ushouse.headers.json").write_text(json.dumps({"Last-Modified": r.headers.get("Last-Modified"), "url": cls.URL}))

    @classmethod
    def source(cls, st):
        return ADAPTERS[st].name

    @classmethod
    def parse(cls, paths, st):
        lines = [l.split(";") for l in Path(paths[0]).read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        out = {}
        for f in lines:
            m = cls.TITLE.match(norm_title(f[4])) if len(f) >= 16 else None
            if not m:
                continue
            k = m.group(1) or (f[5].strip() if f[5].strip().isdigit() else None)
            if k is None:
                raise ValueError(f"no district number for {f[4]!r}")
            c = out.setdefault(int(k), {"candidates": [], "total": int(f[15]), "reporting": f"precincts {f[11]}/{f[12]}",
                                                 "complete": f[11].strip() == f[12].strip()})
            c["candidates"].append({"name": f[7], "party": f[10], "votes": int(f[13])})
        for k, c in out.items():
            if not cands_total_ok(c["candidates"], c.pop("total")):
                raise ValueError(f"district {k}: candidate votes don't add up to the office total")
        h = json.loads(Path(paths[1]).read_text())
        return {"as_of": h.get("Last-Modified"), "url": cls.URL, "contests": out}


def files_on(cls, st, day_dir):
    return cls.files_on(day_dir) if hasattr(cls, "files_on") else [day_dir / n for n in cls.files]


def day_dirs(st):
    d = RAW / "official" / st
    return sorted(p for p in d.glob("20??-??-??") if p.is_dir()) if d.exists() else []


def parse_day(cls, st, day_dir):
    paths = files_on(cls, st, day_dir)
    if not paths or not paths[0].exists():
        return None
    return cls.parse(paths, st)


# ---------------- margins ----------------
def race_row(key, res, contest):
    rows = [{"candidate": c["name"], "party_code": party_code(c["party"]), "votes_first": float(c["votes"]),
             "votes_final": float(c["votes"])} for c in contest["candidates"]]
    m, d, r, dname, _ = RM.margins_rcv(rows)
    s = float(sum(x["votes_first"] for x in rows))
    return {"race_key": key, "margin": m, "dside_votes": d, "rep_votes": r, "dside_candidate": dname, "cand_sum": s,
            "d_votes_all": sum(x["votes_first"] for x in rows if x["party_code"] == "D"),
            "r_votes_all": sum(x["votes_first"] for x in rows if x["party_code"] == "R"),
            "as_of": str(contest.get("as_of") or res.get("as_of")), "reporting": contest.get("reporting"),
            "complete": bool(contest.get("complete")), "candidates": json.dumps(contest["candidates"])}


def backfill_history(frozen_keys):
    """Every saved day's official count, per district, into margins_history_house.csv (source 'official'), so an
    official count's settledness is judged on its full history. Days already there are replaced (re-parsing is
    deterministic); today's row is written by settledness() itself."""
    rows = []
    for st, cls in HOUSE.items():
        for dd in day_dirs(st):
            try:
                res = parse_day(cls, st, dd)
            except Exception:  # noqa: BLE001  (a malformed old file just leaves that day out)
                continue
            for k, c in (res or {}).get("contests", {}).items():
                key = f"2026|{st}|H|{k}"
                if key in frozen_keys and c["candidates"] and not runoff(st, c):
                    r = race_row(key, res, c)
                    rows.append({"race_key": key, "day": dd.name, "cand_sum": r["cand_sum"], "margin": r["margin"],
                                 "evidence": r["as_of"], "source": "official"})
    if not rows:
        return
    path = OUT / "margins_history_house.csv"
    hist = pd.read_csv(path, dtype={"evidence": str}) if path.exists() else pd.DataFrame(columns=["race_key", "day", "cand_sum", "margin", "evidence", "source"])
    new = pd.DataFrame(rows)
    idx = ["race_key", "source", "day"]
    hist = pd.concat([hist[~hist.set_index(idx).index.isin(new.set_index(idx).index)], new]).sort_values(idx)
    hist.to_csv(path, index=False)


def merge_into_margins(off):
    """Official numbers replace Wikipedia's rows in margins_house.csv (Wikipedia's margin kept as wiki_margin), then
    each race's settledness is re-judged on its own source."""
    wpath = OUT / "margins_house_wiki.csv"
    if not wpath.exists():
        return
    m = pd.read_csv(wpath)
    m = m[[c for c in m.columns if c not in ("prev_day", "prev_cand_sum", "growth_since_prev", "count_flag", "count_stable",
                                              "held_days", "settled")]].copy()
    m["wiki_margin"] = m.margin.where(m.source.eq("wikipedia"))
    m["complete"] = False
    # revision ids come back as floats when some rows (California's) have none: keep them whole, or settledness would
    # read "1384824070.0" as new evidence against the history's "1384824070"
    m["revision"] = pd.Series([int(x) if pd.notna(x) else None for x in pd.to_numeric(m.revision, errors="coerce")], index=m.index, dtype=object)
    for c in ("source", "revision", "page_modified", "snapshot", "caption", "dside_candidate", "issues", "reporting", "box_error"):
        m[c] = m[c].astype(object) if c in m else None
    ok = off[(off.status == "ok") & off.margin.notna()] if len(off) else off
    for _, o in ok.iterrows():
        i = m.index[m.race_key == o.race_key]
        diff = o.margin_diff_vs_wiki
        issue = "" if not np.isfinite(diff) or abs(diff) <= DIFF_REVIEW else f"official margin differs from Wikipedia by {diff:+.2f}"
        vals = {"source": f"official ({o.source})", "revision": None, "page_modified": o.as_of, "snapshot": o.snapshot,
                "caption": o.url, "reporting": o.reporting, "margin": o.margin, "margin_first_choice": o.margin,
                "dside_votes": o.dside_votes, "rep_votes": o.rep_votes, "dside_candidate": o.dside_candidate,
                "total": o.cand_sum, "cand_sum": o.cand_sum, "n_rounds": 1, "margin_round": 1, "margin_type": "two-party",
                "d_votes_all": o.d_votes_all, "r_votes_all": o.r_votes_all, "complete": bool(o.complete), "issues": issue,
                "box_error": ""}   # the official count replaces the Wikipedia box, and its errors with it
        if len(i):
            m.loc[i, list(vals)] = list(vals.values())
        else:   # no Wikipedia box for this district (an unopposed race Wikipedia lists without a box, say)
            m = pd.concat([m, pd.DataFrame([{"race_key": o.race_key, **vals}])], ignore_index=True)
    m = RM.settledness(m, "house")
    m.to_csv(OUT / "margins_house.csv", index=False)


def main(parse_only=False):
    frozen = pd.read_csv(FINAL / "house_polls_fundamentals.csv")
    keys = set(frozen.race_key)
    wp = OUT / "margins_house_wiki.csv"
    wiki = pd.read_csv(wp).set_index("race_key") if wp.exists() else pd.DataFrame()
    rows = []
    for st, cls in HOUSE.items():
        err = None
        if not parse_only:
            try:
                cls.fetch(st)
            except Exception as e:  # noqa: BLE001  (one state's site failing must not stop the rest)
                err = f"fetch failed: {type(e).__name__}: {str(e)[:160]}"
        # the newest day with the state's House files (a failed fetch today leaves an earlier day's copy in use)
        dd = [d for d in day_dirs(st) if files_on(cls, st, d) and files_on(cls, st, d)[0].exists()]
        res = None
        if not dd:
            err = err or "no saved House file yet"
        else:
            try:
                res = parse_day(cls, st, dd[-1])
            except Exception as e:  # noqa: BLE001
                err = f"error: {type(e).__name__}: {str(e)[:160]}"
        st_keys = sorted((k for k in keys if k.split("|")[1] == st), key=lambda k: int(k.split("|")[3]))
        for key in st_keys:
            dist = int(key.split("|")[3])
            c = (res or {}).get("contests", {}).get(dist)
            if res is None or c is None or not c["candidates"]:
                rows.append({"race_key": key, "state": st, "status": err or "no contest for this district in the state's file"})
                continue
            if runoff(st, c):
                rows.append({"race_key": key, "state": st, "status": "no majority on November 3: goes to a runoff, not scored from this count"})
                continue
            r = race_row(key, res, c)
            w = wiki.loc[key] if key in wiki.index else None
            wm = float(w["margin"]) if w is not None and pd.notna(w.get("margin")) and w.get("source") == "wikipedia" else np.nan
            snap = files_on(cls, st, dd[-1])[0]
            rows.append({"state": st, "status": "ok", "source": cls.source(st), "url": res.get("url"),
                         "certified": res.get("certified"), "snapshot": snap.relative_to(ROOT).as_posix(), **r,
                         "wiki_margin": wm, "wiki_cand_sum": float(w["cand_sum"]) if w is not None and pd.notna(w.get("cand_sum")) else np.nan,
                         "margin_diff_vs_wiki": (r["margin"] - wm) if np.isfinite(r["margin"]) and np.isfinite(wm) else np.nan})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "official_house.csv", index=False)
    backfill_history(keys)
    merge_into_margins(df)
    ok = df[df.status == "ok"]
    print(f"official House: {len(ok)} of {len(df)} districts in {df.state.nunique()} states")
    for st, g in df.groupby("state", sort=False):
        bad = g[g.status != "ok"]
        print(f"  {st}: {(g.status == 'ok').sum()}/{len(g)} districts" + (f"; {bad.status.iloc[0]}" if len(bad) else ""))
    big = ok[ok.margin_diff_vs_wiki.abs() > DIFF_REVIEW]
    for _, r in big.iterrows():
        print(f"  [review] {r.race_key}: official {r.margin:+.2f} vs Wikipedia {r.wiki_margin:+.2f} "
              f"({r.cand_sum:,.0f} vs {r.wiki_cand_sum:,.0f} votes)")
    return df


if __name__ == "__main__":
    main(parse_only="parse" in sys.argv[1:])
