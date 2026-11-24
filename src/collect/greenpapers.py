"""Delegate rules and delegate counts by state, party and cycle, 2008-2024, from The Green Papers (DA-6).

The Green Papers (thegreenpapers.com) gave leave on 2026-11-24 to use its data, with credit. Its pages are a linked
source (DATA.md): raw copies live in the git-ignored store data/linked/greenpapers/<date>/, each fetch recorded in
data/linked/manifest.json with its URL, the Green Papers page it copies and a checksum; only the tables derived here
are committed, and they credit and link The Green Papers. Back the store up with src/backup_offrepo.py.

Pages: one per state and party per cycle (e.g. /P24/IA-R), and each party's allocation page (/P24/R-Alloc.phtml).
2016, 2020 and 2024 are read from the live site. The live 2008 and 2012 pages no longer load (their scripts are
missing, checked 2026-11-24), so those come from the Internet Archive: for each page, its last capture before the
end of the cycle's year.

The 2008 and 2012 pages also carry a first-stage count before the delegate columns (the popular vote, or caucus-goers'
delegates); it is written to primary_greenpapers_counts.csv under the page's own heading, and primary_results.py checks
the results against it.

Run:  python src/collect/greenpapers.py fetch     (polite: one request every 3 seconds; cached pages are skipped)
      python src/collect/greenpapers.py           (parse the stored pages and write the tables)
"""
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LINKED, SESSION  # noqa: E402

SITE = "https://www.thegreenpapers.com"
SOURCE = "greenpapers"
LIVE = (2016, 2020, 2024)
ARCHIVED = (2008, 2012)
PAUSE = 3.0


def code(cycle):
    return f"P{cycle % 100:02d}"


def live_pages(cycle):
    """State pages and the two allocation pages listed on the cycle's index."""
    r = SESSION.get(f"{SITE}/{code(cycle)}/", timeout=60)
    r.raise_for_status()
    links = sorted(set(re.findall(r'href="(/%s/[A-Z]{2}-[DR])"' % code(cycle), r.text)))
    return links + [f"/{code(cycle)}/D-Alloc.phtml", f"/{code(cycle)}/R-Alloc.phtml"]


def archived_pages(cycle):
    """(page path, capture timestamp): each state page's and allocation page's last capture in the cycle's year."""
    for attempt in range(4):
        try:
            r = SESSION.get("https://web.archive.org/cdx/search/cdx", timeout=180, params={
                "url": f"thegreenpapers.com/{code(cycle)}/", "matchType": "prefix", "output": "json",
                "fl": "original,timestamp", "filter": "statuscode:200", "to": f"{cycle}1231235959"})
            rows = r.json()[1:]
            break
        except Exception:  # noqa: BLE001
            time.sleep(15 * (attempt + 1))
    else:
        raise RuntimeError(f"Internet Archive CDX failed for {cycle}")
    last = {}
    for orig, ts in rows:
        m = re.search(r"/(P\d\d/(?:[A-Z]{2}-[DR]|[DR]-Alloc)(?:\.phtml)?)$", orig)
        if m:
            path = "/" + m.group(1).replace(".phtml", "") if "-Alloc" not in m.group(1) else "/" + m.group(1)
            if path not in last or ts > last[path][1]:
                last[path] = (orig, ts)
    return last


def store_name(path):
    return path.strip("/").replace("/", "_") + ".html"


def check_page(html, path, cycle):
    """The site answers broken pages with status 200 (a CGIWrap error, or its own 404 page): a page counts only if its
    title names the cycle's year and it is not one of those."""
    title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    title = re.sub(r"\s+", " ", title.group(1)).strip() if title else ""
    if re.search(r"CGIWrap|Error 404|Missing URL", title, re.I) or str(cycle) not in title:
        raise ValueError(f"not a Green Papers {cycle} page: {path} (title {title[:80]!r})")
    return title


def fetch_page(name, url, page, cycle, meta=None):
    """fetch_linked's store and manifest entry, for HTML pages (fetch_linked refuses HTML: for its other sources an HTML
    answer means a sign-in page)."""
    import datetime as dt
    import hashlib
    from common import TODAY
    r = SESSION.get(url, timeout=120)
    r.raise_for_status()
    title = check_page(r.content.decode("utf-8", errors="replace"), page, cycle)
    d = LINKED / SOURCE / TODAY
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(r.content)
    mf = LINKED / "manifest.json"
    m = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
    m.setdefault(SOURCE, {})[f"{TODAY}/{name}"] = {
        "url": url, "page": page, "cycle": cycle, "title": title, **(meta or {}),
        "retrieved": dt.datetime.now().isoformat(timespec="seconds"), "bytes": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest()}
    mf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch():
    have = {p.name for p in (LINKED / SOURCE).glob("*/*.html")}
    failed = []
    n = 0
    for cycle in LIVE:
        for path in live_pages(cycle):
            name = store_name(path)
            if name in have:
                continue
            try:
                fetch_page(name, SITE + path, SITE + path, cycle)
                n += 1
            except Exception as e:  # noqa: BLE001
                failed.append((path, str(e)[:120]))
            time.sleep(PAUSE)
        time.sleep(PAUSE)
    for cycle in ARCHIVED:
        for path, (orig, ts) in sorted(archived_pages(cycle).items()):
            name = store_name(path)
            if name in have:
                continue
            url = f"https://web.archive.org/web/{ts}id_/{orig}"
            for attempt in range(3):
                try:
                    fetch_page(name, url, orig.replace(":80/", "/"), cycle, meta={"archive_capture": ts})
                    n += 1
                    break
                except ValueError as e:              # a captured error page: no use retrying
                    failed.append((path, str(e)[:120]))
                    break
                except Exception as e:  # noqa: BLE001
                    if attempt == 2:
                        failed.append((path, str(e)[:120]))
                    time.sleep(20 * (attempt + 1))
            time.sleep(PAUSE)
    print(f"fetched {n} pages; failed {len(failed)}")
    for f in failed:
        print("  ", *f)


# ---------------- parsing ----------------
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
THRESHOLD = [  # sentences giving a qualifying share; the number is captured
    r"(?<![\d.])(\d{1,2})\s*(?:%|percent)\s+threshold",     # not the tail of '3.846%' (Nevada 2024)
    r"threshold of (\d{1,2})\s*(?:%|percent)",
    r"(?:receiv\w*|win\w*|obtain\w*|garner\w*|get\w*)\s+(?:at least\s+)?(\d{1,2})\s*(?:%|percent)\s+(?:or more|of the)",
    r"at least (\d{1,2})\s*(?:%|percent) of the (?:statewide |state-wide |total |popular |district |congressional district )?vote",
]
WTA_TRIGGER = r"(?:receiv\w*|win\w*)\s+(?:a majority|more than (\d{1,2})\s*(?:%|percent)|(\d{1,2})\s*(?:%|percent) or more)[^.]{0,80}?(?:all|winner[- ]take[- ]all)"


def text_of(html):
    t = BeautifulSoup(html, "html.parser").get_text("\n")
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t)


def label(t, key, stops):
    """The page's own label after 'key:' (e.g. 'Delegate Selection:'), up to the first stop phrase."""
    m = re.search(re.escape(key) + r":\s*(.*?)(?=" + "|".join(stops) + r"|\n\s*\d+(?:\.\d+)? total delegate|$)",
                  t, re.S)
    if not m:
        return None
    v = re.sub(r"\s+", " ", m.group(1)).strip(" .,;|")
    return v or None


def delegates_table(soup):
    """(candidate, hard-total delegates) from the page's delegate table, and its Total."""
    t = next((x for x in soup.find_all("table") if "Hard Total" in x.get_text() and x.find("table") is None), None)
    if t is None:
        return [], None
    trs = t.find_all("tr")
    rows = [[c.get_text(" ", strip=True).replace("\xa0", " ") for c in tr.find_all(["td", "th"])] for tr in trs]
    # the hard-total column: where the 'Delegate Votes' heading starts, counting the spans of the headings before it
    # (caucus pages put popular-vote and caucus-count columns first)
    col = 0
    for c in trs[0].find_all(["td", "th"]) if trs else []:
        if re.sub(r"\s+", " ", c.get_text(" ", strip=True)) == "Delegate Votes":   # not 'County Convention Delegates'
            break
        col += int(re.sub(r"\D", "", c.get("colspan", "1")) or 1)
    out, total = [], None
    for r in rows[2:]:
        if len(r) <= col:
            continue
        m = re.match(r"([\d.]+)", r[col])
        v = float(m.group(1)) if m else None
        if r[0] == "Total":
            total = v
        elif v is not None:
            out.append((r[0], v))
    return out, total


# first-stage column headings (2008 and 2012 pages only) -> measure; mapped only where the heading is unambiguous
FIRST_STAGE_MEASURE = {
    "Popular Vote": "votes", "Caucus Popular Vote": "votes", "Precinct Popular Vote": "votes",
    "Popular Vote (Supporters)": "votes",
    "State Convention Delegates Selected": "state delegates", "State Delegates": "state delegates",
    "County Convention Delegates Elected": "county delegates", "County Delegates": "county delegates",
    "Precinct Delegates Selected": "precinct delegates",
    "Delegates to the District Convention": "district convention delegates",
    "Percentage Vote": "unclear",   # Washington Republicans: counts under a heading that doesn't say what they count
}


def first_stage(soup):
    """(heading, candidate, count, listed share) for each column before 'Delegate Votes' in the delegate table (the
    popular vote, or caucus-goers' delegates), and {heading: the column's Total}. Cells read '2,079  59.43%': the
    count is the leading number, the share the one before '%'."""
    t = next((x for x in soup.find_all("table") if "Hard Total" in x.get_text() and x.find("table") is None), None)
    if t is None:
        return [], {}
    trs = t.find_all("tr")
    heads, col = [], 0
    for c in trs[0].find_all(["td", "th"]):
        h = re.sub(r"\s+", " ", c.get_text(" ", strip=True))
        if h == "Delegate Votes":
            break
        if col > 0:
            heads.append((col, h))
        col += int(re.sub(r"\D", "", c.get("colspan", "1")) or 1)
    out, totals = [], {}
    for tr in trs[2:]:
        r = [c.get_text(" ", strip=True).replace("\xa0", " ") for c in tr.find_all(["td", "th"])]
        for i, h in heads:
            if len(r) <= i:
                continue
            m = re.match(r"([\d,]+(?:\.\d+)?)", r[i])
            if not m:
                continue
            n = float(m.group(1).replace(",", ""))
            s = re.search(r"([\d.]+)%", r[i][m.end():])
            if r[0] == "Total":
                totals[h] = n
            else:
                out.append((h, r[0], n, float(s.group(1)) / 100 if s else None))
    return out, totals


def events(t, cycle):
    """(event, first day) for each line of the 'Presidential Nominating Process' list."""
    i = t.find("Presidential Nominating Process")
    j = t.find("\nCandidate\n", i)
    seg = t[i:j if j > 0 else i + 3000]
    out = []
    for m in re.finditer(rf"\n([^\n:]{{3,120}}):\s*(?:\w+day\s+)?(\d{{1,2}})\s+({MONTHS})(?:\s+(\d{{4}}))?", seg):
        mo = m.group(3)
        yr = m.group(4) or str(cycle)
        try:
            day = pd.Timestamp(f"{m.group(2)} {mo} {yr}").date()
        except ValueError:
            continue
        out.append((m.group(1).strip(), day))
    return out


def rule_sentences(t):
    """Sentences about qualifying for or allocating national delegates; not those about convention ballots, binding,
    sanctions or penalties (South Carolina Republicans 2008: 30% on the first ballot binds delegates for the second)."""
    out = []
    for s in re.findall(r"[^.\n]*(?:threshold|qualif|winner[- ]take|allocat|awarded|eligible for)[^.\n]*\.", t, re.I):
        if not re.search(r"ballot|bound|binding|sanction|penalt|bonus|alternate", s, re.I):
            out.append(s)
    return out


def parse_page(path):
    """One stored state page -> (rules row, delegate rows, event rows)."""
    m = re.match(r"P(\d\d)_([A-Z]{2})-([DR])\.html$", path.name)
    cycle, st, party = 2000 + int(m.group(1)), m.group(2), m.group(3)
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    t = text_of(html)
    stops = [r"Voter Eligibility", r"Polling hours", r"\n[A-Z][a-z]+ [A-Z]"]
    # Democratic pages from 2016 say "Delegate Pledging"
    sel = label(t, "Delegate Selection", stops) or label(t, "Delegate Pledging", stops)
    elig = label(t, "Voter Eligibility", [r"Voter Participation", r"Voter Affiliation", r"\n\d", r"Primary\.", r"Caucus\.",
                                          r"Convention\.", r"States Chronologically"])
    tot = re.search(r"([\d.]+) total delegate(?: vote)?s\b(.{0,160})", t)
    rules_txt = " ".join(rule_sentences(t))
    thr = sorted({int(x) for p in THRESHOLD for x in re.findall(p, rules_txt, re.I) if 5 <= int(x) <= 50})
    wta = re.search(WTA_TRIGGER, rules_txt, re.I)
    dels, dtotal = delegates_table(soup)
    fs, fs_tot = first_stage(soup)
    ev = events(t, cycle)
    rule = {
        "cycle": cycle, "party": party, "state": st,
        "selection": sel, "eligibility": elig,
        "total_delegates": float(tot.group(1)) if tot else None,
        "delegate_breakdown": re.sub(r"\s+", " ", tot.group(2)).split("States Chronologically")[0].strip(" -") if tot else None,
        "penalty": bool(tot and re.search(r"penalty", tot.group(2), re.I)),
        "threshold_pct": "/".join(map(str, thr)) or None,
        "wta_trigger": ("majority" if wta and "majority" in wta.group(0).lower() else
                        f"{wta.group(1) or wta.group(2)}%" if wta else None),
        "winner_take_all_named": bool(re.search(r"winner[- ]take[- ]all", sel or "", re.I)),
        "proportional_named": bool(re.search(r"proportional", sel or "", re.I)),
        "first_event": ev[0][0] if ev else None, "first_event_date": ev[0][1] if ev else None,
        "delegates_listed": sum(v for _, v in dels) if dels else None, "delegates_table_total": dtotal,
    }
    counts = [{"cycle": cycle, "party": party, "state": st, "heading": h, "measure": FIRST_STAGE_MEASURE.get(h, "unclear"),
               "candidate_name": n, "count": v, "share_listed": s, "column_total": fs_tot.get(h)} for h, n, v, s in fs]
    return rule, [{"cycle": cycle, "party": party, "state": st, "candidate_name": n, "delegates": v} for n, v in dels], \
        [{"cycle": cycle, "party": party, "state": st, "event": e, "date": d} for e, d in ev], counts


def parse():
    rules, dels, evs, cnts = [], [], [], []
    man_all = json.loads((LINKED / "manifest.json").read_text(encoding="utf-8"))[SOURCE]
    for p in sorted((LINKED / SOURCE).glob("*/P*_??-?.html")):
        a, b, c, f = parse_page(p)
        man = man_all.get(f"{p.parent.name}/{p.name}", {})
        for x in [a] + b + c + f:
            x["green_papers_page"] = man.get("page")
            x["archive_capture"] = man.get("archive_capture")
        rules.append(a)
        dels += b
        evs += c
        cnts += f
    return pd.DataFrame(rules), pd.DataFrame(dels), pd.DataFrame(evs), pd.DataFrame(cnts)


def gp_name(n):
    """'Haley, Nimarata Randhaw "Nikki"' -> 'Nikki Haley'; 'Trump, Donald John, Sr.' -> 'Donald Trump'."""
    if "," not in n:
        return n
    last, rest = [x.strip() for x in n.split(",", 1)]
    nick = re.search(r'"([^"]+)"?', rest)
    first = nick.group(1) if nick else rest.split()[0].rstrip(",") if rest.split() else ""
    return f"{first} {last}".strip()


def calendar_check(e):
    """Each primary_calendar.csv primary or caucus date against the page's event dates for that state and party."""
    from common import ROOT
    cal = pd.read_csv(ROOT / "data" / "interim" / "primary_calendar.csv", parse_dates=["date"])
    cal = cal[cal.contest.isin(["primary", "caucus"])].copy()
    cal["date"] = cal.date.dt.date
    ev = e.groupby(["cycle", "party", "state"])
    dates, names = ev.date.apply(set), ev.apply(lambda g: "; ".join(f"{a} {b}" for a, b in zip(g.event, g.date)),
                                                 include_groups=False)
    cal = cal[[k in dates.index for k in zip(cal.cycle, cal.party, cal.state)]]
    cal["green_papers_has_date"] = [d in dates[(y, p, s)] for y, p, s, d in zip(cal.cycle, cal.party, cal.state, cal.date)]
    cal["green_papers_events"] = [names[(y, p, s)] for y, p, s in zip(cal.cycle, cal.party, cal.state)]
    return cal[["cycle", "party", "state", "contest", "date", "green_papers_has_date", "green_papers_events"]]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    from common import ROOT
    from primary_polls import match_keys
    out = ROOT / "data" / "interim"
    r, d, e, f = parse()
    cands = pd.read_csv(out / "primary_candidates.csv")
    for x in (d, f):
        x["candidate_name"] = x.candidate_name.map(gp_name)
        x["line"] = ["uncommitted" if re.search(r"uncommit", n, re.I) else
                     "available" if re.search(r"available", n, re.I) else
                     "other" if re.match(r"others?$|\(|not announced", n, re.I) else "candidate" for n in x.candidate_name]
        keys = match_keys(x[x.line == "candidate"], cands)
        x["candidate_key"] = [keys.get((y, p, n)) if ln == "candidate" else None
                              for y, p, n, ln in zip(x.cycle, x.party, x.candidate_name, x.line)]
        x["candidate_key"] = x.candidate_key.where(~x.candidate_key.astype(str).str.startswith("AMBIGUOUS"))
    r.to_csv(out / "primary_delegate_rules.csv", index=False)
    d.to_csv(out / "primary_delegates.csv", index=False)
    f.to_csv(out / "primary_greenpapers_counts.csv", index=False)
    e.to_csv(out / "primary_delegate_events.csv", index=False)
    c = calendar_check(e)
    c.to_csv(out / "primary_calendar_check.csv", index=False)
    # checks, all on the pages' own numbers
    x = r[r.delegates_table_total.notna()]
    print("States and parties by cycle:", r.groupby(["cycle", "party"]).size().to_dict())
    print("Delegate tables whose candidate rows don't sum to their Total:",
          int(((x.delegates_listed.fillna(0) - x.delegates_table_total).abs() > 0.51).sum()), "of", len(x))
    y = x[x.total_delegates.notna()]
    print("Tables whose Total differs from the page's delegate count:",
          int(((y.delegates_table_total - y.total_delegates).abs() > 0.51).sum()), "of", len(y))
    print("Convention size (sum of the state pages):")
    print(r.groupby(["cycle", "party"]).total_delegates.sum().unstack().to_string())
    print("Field coverage by cycle and party:")
    print(r.groupby(["cycle", "party"])[["selection", "eligibility", "total_delegates", "threshold_pct",
                                         "first_event_date"]].agg(lambda s: round(s.notna().mean(), 2)).to_string())
    odd = r[(r.party == "D") & r.threshold_pct.notna() & (r.threshold_pct != "15")]
    print("Democratic thresholds other than 15% (a likely parse error):", odd[["cycle", "state", "threshold_pct"]].values.tolist() or "none")
    um = d[(d.line == "candidate") & d.candidate_key.isna()].groupby(["cycle", "party", "candidate_name"]).delegates.sum()
    print("Candidates with delegates not matched to the timeline:", um[um > 0].sort_values(ascending=False).head(10).to_dict())
    g = f.groupby(["cycle", "party", "state", "heading"]).agg(listed=("count", "sum"), total=("column_total", "first"))
    print("First-stage columns (popular vote or caucus delegates) by cycle and heading:")
    print(f.groupby(["cycle", "heading"]).state.nunique().to_string())
    bad = g[(g.listed - g.total).abs() > 0.51]
    print("First-stage columns whose rows don't sum to their Total:", len(bad), "of", len(g))
    if len(bad):
        print(bad.to_string())
    print("Calendar dates not among the page's event dates:", int((~c.green_papers_has_date).sum()), "of", len(c))
    print(c[~c.green_papers_has_date][["cycle", "party", "state", "contest", "date"]].to_string(index=False))


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        fetch()
    else:
        main()
