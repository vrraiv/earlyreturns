"""Vote and delegate tables from TheGreenPapers.com, 2016-2024 (DA-6, reopened 2026-11-24).

greenpapers.py reads each state page's rules, hard delegate totals and events. The same pages also carry the tables
the site computes delegates from, which it did not read; this module reads them, and two further sources the site's
webmaster pointed us to by email on 2026-11-24, with leave to use the data attributed to TheGreenPapers.com:

1. The state pages already in the store (data/linked/greenpapers/<date>/P16_*, P20_*, P24_*; no new requests).
   - Tally tables (anchors such as AL-R-STATEWIDE): each candidate's statewide count under the table's own heading
     ("Pop Vote", "State Delegate Equivalents", ...), the table's Total, and its caption (contest, source, status,
     retrieved date). -> primary_greenpapers_tallies.csv
   - Delegate tables (anchors such as AL-R-DEL_PRIMARY): by unit (congressional district, at-large, county, ...): the
     unit's vote, its qualifying vote, its delegates, and for each candidate the vote, listed share and delegates. The
     pages list only candidates who won delegates somewhere in the state. Cells the site greys are kept as a flag
     (`greyed`); what grey means is not stated. -> primary_delegate_units.csv
     Slate tables (delegate candidates elected by name: Colorado, Illinois, Pennsylvania, West Virginia and Virgin
     Islands Republicans) are not read: they list individual delegate candidates, and the hard totals already cover
     them.
2. The download pages (/P16/download.phtml, /P20/, /P24/), which link a Dropbox folder per cycle of .xls files.
   Each folder is stored as a zip (data/linked/greenpapers_downloads/<date>/P16.zip ...). Read: the delegate count
   (soft pledged, soft unpledged, hard total, first and last floor votes), the Democratic and Republican delegate
   allocation breakdowns, and the 2024 events file (with polling hours and the selection and eligibility labels).
   The general-election files in the same folders (G-*.xls) are stored but not read.
   -> primary_delegate_count.csv, primary_delegate_allocation_d.csv, primary_delegate_allocation_r.csv,
      primary_greenpapers_events.csv
3. The 2016 computation tables: a directory the webmaster pointed us to that is not a public page. Its "-1" files
   are the delegate tables above with every candidate; only those are fetched (the "-0" files are the pages' version,
   and the tally files are on the pages too). Its address is read from .env (greenpapers_2016full_url) and is never
   written to the repo: the manifest records each file's name, size and checksum without a URL, and the derived rows
   cite the public state page. Where a -1 file exists it replaces the page's table in primary_delegate_units.csv
   (`candidates_listed` = "all"); the shared candidates are checked equal to the page's. Files with no table on the
   page (six) are stored but not read: the webmaster said the directory holds unused data.

Raw copies stay in the git-ignored store and are backed up off-repo by src/backup_offrepo.py; only the derived
tables are committed, attributed to TheGreenPapers.com and linked to its pages.

Run:  python src/collect/greenpapers_tables.py fetch   (downloads and 2016 files; one request every 3 seconds)
      python src/collect/greenpapers_tables.py         (parse the store and write the tables)
"""
import datetime as dt
import hashlib
import html as htmllib
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LINKED, ROOT, SESSION, TODAY, env_key, fetch_linked  # noqa: E402

SITE = "https://www.thegreenpapers.com"
CYCLES = (2016, 2020, 2024)
PAUSE = 3.0
PAGES = "greenpapers"
DOWNLOADS = "greenpapers_downloads"
RESULTS = "greenpapers_2016full"
INTERIM = ROOT / "data" / "interim"


def code(cycle):
    return f"P{cycle % 100:02d}"


# ---------------- fetching ----------------
def fetch_downloads():
    for cycle in CYCLES:
        page = f"{SITE}/{code(cycle)}/download.phtml"
        r = SESSION.get(page, timeout=60)
        r.raise_for_status()
        m = re.search(r'href="(https://www\.dropbox\.com/[^"]+)"', r.text)
        if not m:
            raise RuntimeError(f"no Dropbox link on {page}")
        url = re.sub(r"dl=0$", "dl=1", htmllib.unescape(m.group(1)))   # dl=1: the folder as a zip
        out = fetch_linked(DOWNLOADS, f"{code(cycle)}.zip", url, page, meta={"cycle": cycle}, timeout=300)
        names = zipfile.ZipFile(out).namelist()
        print(cycle, out.stat().st_size, "bytes:", [n for n in names if not n.endswith("/")])
        time.sleep(PAUSE)


def fetch_results():
    """The 2016 "-1" delegate tables from the directory in .env. Manifest entries carry no URL (see the docstring)."""
    base = env_key("greenpapers_2016full_url")
    if not base:
        raise SystemExit("greenpapers_2016full_url is not set in .env; the 2016 computation tables are skipped")
    base = base.rstrip("/") + "/"
    d = LINKED / RESULTS / TODAY
    d.mkdir(parents=True, exist_ok=True)
    have = {p.name for p in (LINKED / RESULTS).glob("*/*.html")}
    r = SESSION.get(base, timeout=60)
    r.raise_for_status()
    names = sorted(set(re.findall(r'href="([A-Z]{2}-[DR]-DEL_[A-Z_0-9]+-1)"', r.text)))
    print(len(names), "files listed with every candidate (-1)")
    mf = LINKED / "manifest.json"
    n = 0
    for name in names:
        fn = name + ".html"
        if fn in have:
            continue
        x = SESSION.get(base + name, timeout=60)
        x.raise_for_status()
        if not x.content.lstrip().startswith((b"<a name=", b"<table")):   # some files have no anchor
            raise RuntimeError(f"unexpected content for {name}: {x.content[:60]!r}")
        (d / fn).write_bytes(x.content)
        m = json.loads(mf.read_text(encoding="utf-8"))
        m.setdefault(RESULTS, {})[f"{TODAY}/{fn}"] = {
            "file": name, "cycle": 2016,
            "source": "TheGreenPapers.com 2016 computation tables, a directory its webmaster pointed us to by email "
                      "(2026-11-24); not a public page, so its address is kept out of the repo",
            "retrieved": dt.datetime.now().isoformat(timespec="seconds"), "bytes": len(x.content),
            "sha256": hashlib.sha256(x.content).hexdigest()}
        mf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        n += 1
        time.sleep(PAUSE)
    print("fetched", n)


# ---------------- parsing the HTML tables ----------------
TABLE = re.compile(r'<a name="([A-Z]{2})-([DR])-([A-Z_0-9]+)"></a>(<table.*?</table>)', re.S)
CELL = re.compile(r"<td([^>]*)>(.*?)</td>", re.S)


def text(h):
    h = re.sub(r"<br\s*/?>", " ", h)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", h))).replace("\xa0", " ").strip()


def num(s):
    s = text(s).replace(",", "")
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", s)
    return float(s) if m else None


def share(s):
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)%", text(s))
    return float(m.group(1)) / 100 if m else None


def gp_id(h):
    m = re.search(r"candidates\.phtml#P(\d+)", h)
    return int(m.group(1)) if m else None


def caption(t):
    """Contest description, source, status, retrieved date and any estimate note from the table's caption."""
    m = re.search(r'<(?:p|caption) id="capc">(.*?)</(?:p|caption)>', t, re.S)
    if not m:
        return {}
    parts = [text(p) for p in re.split(r"<br\s*/?>", m.group(1))]
    parts = [p for p in parts if p]
    out = {"contest_caption": None if not parts or parts[0].startswith("$") else parts[0],
           "source_named": None, "status": None, "retrieved": None, "caption_note": None}
    notes = []
    for p in parts[1:]:
        if p.startswith("Source:"):
            out["source_named"] = p[7:].strip(" .") or None
        elif "Status:" in p or "Retrieved:" in p:
            s = re.search(r"Status:\s*([^.]+)", p)
            rd = re.search(r"Retrieved:\s*(?:\w+day\s+)?(\d{1,2} \w+ \d{4})", p)
            out["status"] = s.group(1).strip() if s else out["status"]
            if rd:
                out["retrieved"] = pd.Timestamp(rd.group(1)).date()
        elif not p.startswith("Included in"):
            notes.append(p.strip(" ."))
    out["caption_note"] = "; ".join(n for n in notes if n) or None
    return out


def name_line(name):
    n = name.lower()
    if re.search(r"uncommit|noncommit|no preference|uninstructed|undeclared|unpledged", n):
        return "uncommitted"
    if re.search(r"scattering|blank|write-in|^others?$|none of these|void|misc|over ?votes|under ?votes", n):
        return "other"
    return "candidate"


def parse_tally(t):
    head = [text(c) for a, c in CELL.findall(t)[:3]]
    rows = []
    for m in re.finditer(r'<td id="dlg?\d">(.*?)</td><td id="drg?\d">(.*?)</td><td id="drg?\d">(.*?)</td>', t, re.S):
        nm = re.sub(r"\s*\(write-in\)$", "", text(m.group(1)))
        rows.append({"gp_id": gp_id(m.group(1)), "candidate_name_listed": nm, "count": num(m.group(2)),
                     "share_listed": share(m.group(3)), "write_in": "(write-in)" in m.group(1)})
    tot = re.search(r'<td id="dcb">Total</td><td id="drb">(.*?)</td>', t)
    return (head[1] if len(head) > 1 else None), rows, (num(tot.group(1)) if tot else None)


def parse_grid(t):
    """Unit-by-candidate delegate table -> (rows, problem). Header row 1: 'Contest' over the unit columns, then each
    candidate over its columns; row 2 labels every column."""
    trs = [CELL.findall(x) for x in re.split(r"</tr>", t) if "<td" in x]
    if len(trs) < 2:
        return [], "no rows"
    h1, h2 = trs[0], trs[1]
    labels2 = [text(c) for a, c in h2]
    labels1 = [text(c) for a, c in h1]
    if any("Delegate" in x and "Preference" in x for x in (labels1, labels2)):   # delegates elected by name
        return [], "slate"
    if text(h1[0][1]) != "Contest":
        return [], "other layout"
    span = lambda a: int(re.search(r'colspan="(\d+)"', a).group(1)) if "colspan" in a else 1  # noqa: E731
    groups = []                     # (candidate header html or None for the unit block, width)
    for i, (a, c) in enumerate(h1):
        groups.append((None if i == 0 else c, span(a)))
    width = sum(w for _, w in groups)
    if len(labels2) != width:
        return [], f"header widths differ ({len(labels2)} labels, {width} columns)"
    cols, k = [], 0
    for g, w in groups:
        for j in range(w):
            cols.append((g, labels2[k]))
            k += 1
    out = []
    for r in trs[2:]:
        if len(r) != width:
            return out, f"a row with {len(r)} cells for {width} columns"
        unit = text(r[0][1])
        base = {"unit": unit, "unit_votes": None, "unit_votes_heading": None, "unit_qualifying": None,
                "unit_qualifying_heading": None, "unit_delegates": None}
        cand = {}
        for (g, lab), (a, c) in zip(cols[1:], r[1:]):
            grey = bool(re.search(r'id="d[a-z]*g', a))
            if g is None:
                if lab == "Del":
                    base["unit_delegates"] = num(c)
                elif re.search(r"Qual", lab):
                    base["unit_qualifying"], base["unit_qualifying_heading"] = num(c), lab
                else:
                    base["unit_votes"], base["unit_votes_heading"] = num(c), lab
                continue
            x = cand.setdefault(g, {"votes": None, "share_listed": None, "allocation": None, "delegates": None,
                                    "greyed": False})
            x["greyed"] |= grey
            if lab == "Del":
                x["delegates"] = num(c)
            elif "%" in lab:
                x["share_listed"] = share(c)
            elif lab == "Alloc":            # Massachusetts: the unrounded allocation before rounding to delegates
                x["allocation"] = num(c)
            else:
                x["votes"] = num(c)
        for g, x in cand.items():
            nm = text(g)
            out.append({**base, "gp_id": gp_id(g), "candidate_header": nm, **x})
        if not cand:
            out.append({**base, "gp_id": None, "candidate_header": None, "votes": None, "share_listed": None,
                        "allocation": None, "delegates": None, "greyed": False})
    return out, None


def page_tables():
    man = json.loads((LINKED / "manifest.json").read_text(encoding="utf-8"))[PAGES]
    for p in sorted((LINKED / PAGES).glob("*/P[12][0-9]_??-?.html")):
        cycle = 2000 + int(p.name[1:3])
        if cycle not in CYCLES:
            continue
        page = man.get(f"{p.parent.name}/{p.name}", {}).get("page")
        h = p.read_text(encoding="utf-8", errors="replace")
        for st, party, kind, t in TABLE.findall(h):
            yield cycle, st, party, kind, t, page


def results_files():
    """{(state, party, kind): table html} for the stored 2016 -1 files (latest copy of each)."""
    out = {}
    for p in sorted((LINKED / RESULTS).glob("*/*-1.html")):
        h = p.read_text(encoding="utf-8", errors="replace")
        m = TABLE.search(h)
        if m:
            out[(m.group(1), m.group(2), m.group(3))] = (m.group(4), p.stem)
        else:                       # files without an anchor: the key is in the file name
            f = re.fullmatch(r"([A-Z]{2})-([DR])-(DEL_[A-Z_0-9]+)-1", p.stem)
            tb = re.search(r"<table.*?</table>", h, re.S)
            if f and tb:
                out[(f.group(1), f.group(2), f.group(3))] = (tb.group(0), p.stem)
    return out


def parse_pages():
    tallies, units, skipped, compare = [], [], [], []
    full = results_files()
    for cycle, st, party, kind, t, page in page_tables():
        key = {"cycle": cycle, "party": party, "state": st, "table": kind}
        cap = caption(t)
        if not kind.startswith("DEL"):
            heading, rows, total = parse_tally(t)
            for i, r in enumerate(rows):
                tallies.append({**key, **cap, "heading": heading, "order": i + 1, **r, "table_total": total,
                                "green_papers_page": page})
            continue
        rows, problem = parse_grid(t)
        src, version = "page", "delegate winners"
        if cycle == 2016 and (st, party, kind) in full:
            t1, fname = full[(st, party, kind)]
            rows1, problem1 = parse_grid(t1)
            if problem1 is None:
                compare.append((key, rows, rows1))
                rows, problem, src, version = rows1, None, fname, "all"
        if problem:
            skipped.append({**key, "problem": problem})
            continue
        for r in rows:
            units.append({**key, **cap, **r, "candidates_listed": version, "table_source": src,
                          "green_papers_page": page})
    # 2016 files with no table on the page (five, with no status or retrieved date; New Hampshire Republicans' second
    # primary table gives other delegate counts than the page): the webmaster said the directory holds unused data, so
    # they are stored but not read
    done = {u["table_source"] for u in units}
    for (st, party, kind), (t1, fname) in sorted(full.items()):
        if fname not in done and (st, party, kind) not in {(s["state"], s["party"], s["table"]) for s in skipped}:
            skipped.append({"cycle": 2016, "party": party, "state": st, "table": kind,
                            "problem": "2016 file with no table on the page (not read)"})
    return pd.DataFrame(tallies), pd.DataFrame(units), pd.DataFrame(skipped), compare


# ---------------- the downloaded spreadsheets ----------------
def snake(c):
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(c).lower())).strip("_")


def read_zip_xls(cycle, member):
    from common import latest_linked
    z = zipfile.ZipFile(latest_linked(DOWNLOADS, f"{code(cycle)}.zip"))
    if member not in z.namelist():
        return None, None
    b = z.read(member)
    sheets = pd.read_excel(io.BytesIO(b), sheet_name=None)
    first = next(iter(sheets))
    df = sheets[first]
    df.columns = [snake(c) for c in df.columns]
    updated = None
    if "Manifest" in sheets:
        mm = sheets["Manifest"]
        for k, v in zip(mm.iloc[:, 0], mm.iloc[:, 1]):
            if str(k).startswith("Last update"):
                updated = str(v)
    return df, updated


def parse_downloads():
    count, alloc_d, alloc_r, events = [], [], [], []
    for cycle in CYCLES:
        page = f"{SITE}/{code(cycle)}/download.phtml"
        for member, sink in (("P-delegate-count.xls", count), ("P-democratic-delegate-allocation.xls", alloc_d),
                             ("P-republican-delegate-allocation.xls", alloc_r), ("P-events.xls", events)):
            df, upd = read_zip_xls(cycle, member)
            if df is None:
                continue
            df.insert(0, "cycle", cycle)
            df["file"] = member
            df["file_updated"] = upd
            df["download_page"] = page
            sink.append(df)
    cat = lambda xs: pd.concat(xs, ignore_index=True) if xs else pd.DataFrame()  # noqa: E731
    return cat(count), cat(alloc_d), cat(alloc_r), cat(events)


# ---------------- names ----------------
def plain_name(n):
    """'Rafael Edward "Ted" Cruz' -> 'Ted Cruz'; 'Donald John Trump, Sr.' -> 'Donald Trump'; 'Williamson,M' ->
    'M Williamson'."""
    n = str(n).strip()
    m = re.fullmatch(r"([^,\s]+),\s*([A-Z])\.?", n)
    if m:
        return f"{m.group(2)} {m.group(1)}"
    n = re.sub(r",\s*(?:Sr|Jr|I{1,3}|IV)\.?$", "", n)
    nick = re.search(r'"([^"]+)"', n)
    toks = re.sub(r'"[^"]*"', " ", n).split()
    if not toks:
        return n
    parts = ("de", "la", "del", "van", "von")
    p = next((k for k in range(1, len(toks) - 1) if toks[k].lower() in parts), None)
    if p is not None:               # 'Roque "Rocky" De La Fuente Guerra' -> surname 'De La Fuente'
        q = p
        while q < len(toks) - 1 and toks[q].lower() in parts:
            q += 1
        last = " ".join(toks[p:q + 1])
    else:
        last = toks[-1]
    first = nick.group(1) if nick else toks[0]
    return f"{first} {last}" if len(toks) > 1 or nick else last


def add_keys(df, name_col):
    from primary_polls import match_keys
    cands = pd.read_csv(INTERIM / "primary_candidates.csv")
    df["line"] = df[name_col].map(lambda n: name_line(str(n)) if pd.notna(n) else None)
    df["candidate_name"] = [plain_name(n) if ln == "candidate" else n for n, ln in zip(df[name_col], df.line)]
    c = df[df.line == "candidate"]
    keys = match_keys(c, cands) if len(c) else {}
    df["candidate_key"] = [keys.get((y, p, n)) if ln == "candidate" else None
                           for y, p, n, ln in zip(df.cycle, df.party, df.candidate_name, df.line)]
    df["candidate_key"] = df.candidate_key.where(~df.candidate_key.astype(str).str.startswith("AMBIGUOUS"))
    return df


# ---------------- main ----------------
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tal, uni, skipped, compare = parse_pages()
    # candidate names for the delegate tables: the tally tables' full names, by site id within a cycle
    ids = tal.dropna(subset=["gp_id"]).drop_duplicates(["cycle", "gp_id"]).set_index(["cycle", "gp_id"]).candidate_name_listed
    uni["candidate_name_listed"] = [ids.get((y, i), h) if pd.notna(i) else h
                                    for y, i, h in zip(uni.cycle, uni.gp_id, uni.candidate_header)]
    tal = add_keys(tal, "candidate_name_listed")
    uni = add_keys(uni, "candidate_name_listed")
    for x in (tal, uni):
        x["gp_id"] = x.gp_id.astype("Int64")
    cnt, ad, ar, ev = parse_downloads()
    cnt["name_listed"] = [" ".join(str(v) for v in (f, l) if pd.notna(v)) for f, l in zip(cnt.first_middle_nick, cnt["last"])]
    cnt = cnt.rename(columns={"state_abbreviation": "state"})
    cnt = add_keys(cnt, "name_listed")
    cnt.loc[cnt["last"].eq("(available)"), "line"] = "available"
    cnt.loc[cnt.line.eq("available"), "candidate_name"] = "(available)"
    cnt = cnt.drop(columns=["state_name", "first_middle_nick", "last", "suffix", "name_listed"])
    ev = ev.rename(columns={"state_abbreviation": "state"})
    for x in (ad, ar):
        x.rename(columns={"state_abbreviation": "state"}, inplace=True)

    tal.to_csv(INTERIM / "primary_greenpapers_tallies.csv", index=False)
    uni.to_csv(INTERIM / "primary_delegate_units.csv", index=False)
    cnt.to_csv(INTERIM / "primary_delegate_count.csv", index=False)
    ad.to_csv(INTERIM / "primary_delegate_allocation_d.csv", index=False)
    ar.to_csv(INTERIM / "primary_delegate_allocation_r.csv", index=False)
    ev.to_csv(INTERIM / "primary_greenpapers_events.csv", index=False)
    checks(tal, uni, skipped, compare, cnt, ad, ar, ev)


def checks(tal, uni, skipped, compare, cnt, ad, ar, ev):
    pd.set_option("display.width", 200)
    print("Tally tables by cycle:", tal.groupby("cycle").apply(lambda g: g[["party", "state", "table"]].drop_duplicates().shape[0],
                                                              include_groups=False).to_dict())
    g = tal.groupby(["cycle", "party", "state", "table"]).agg(listed=("count", "sum"), total=("table_total", "first"))
    bad = g[(g.listed - g.total).abs() > 0.51]
    print("Tally tables whose rows don't sum to their Total:", len(bad), "of", len(g))
    if len(bad):
        print(bad.to_string())
    print("Tally headings:", tal.drop_duplicates(["cycle", "party", "state", "table"]).heading.value_counts().to_dict())
    print("\nDelegate tables read, by cycle and version:")
    print(uni.drop_duplicates(["cycle", "party", "state", "table"]).groupby(["cycle", "candidates_listed"]).size().to_string())
    skipped = skipped.drop_duplicates() if len(skipped) else skipped
    print("Delegate tables not read:", skipped.groupby("problem").size().to_dict() if len(skipped) else "none")
    if len(skipped):
        print(skipped[skipped.problem != "slate"].drop_duplicates().to_string(index=False))
    # within each table: units' delegates sum to the Total Delegates row, by candidate and for the unit column
    body = uni[~uni.unit.str.startswith("Total")]
    tot = uni[uni.unit.str.startswith("Total")]
    k = ["cycle", "party", "state", "table", "candidate_header"]
    a = body.groupby(k, dropna=False).delegates.sum(min_count=1)
    b = tot.groupby(k, dropna=False).delegates.sum(min_count=1)
    j = pd.concat([a.rename("units"), b.rename("total")], axis=1).dropna(subset=["total"])
    off = j[(j.units.fillna(0) - j.total).abs() > 0.51]
    print("Candidate columns whose units don't sum to the table's Total Delegates row:", len(off), "of", len(j))
    if len(off):
        print(off.head(15).to_string())
    # 2016 -1 files against the page tables, candidate by candidate and unit by unit
    diff = n = 0
    for key, r0, r1 in compare:
        f1 = {(r["unit"], r["candidate_header"]): (r["votes"], r["delegates"]) for r in r1}
        for r in r0:
            n += 1
            v = f1.get((r["unit"], r["candidate_header"]))
            if v is None or any((p is None) != (q is None) or (p is not None and abs(p - q) > 1e-9)
                                for p, q in zip(v, (r["votes"], r["delegates"]))):
                diff += 1
    print(f"2016 full tables against the pages' tables: {len(compare)} tables, {diff} of {n} page cells differ")
    # greyed cells: what share do they carry and do they ever hold delegates?
    c = body[body.line.eq("candidate") & body.share_listed.notna()]
    print("Greyed candidate cells: with delegates", int((c.greyed & c.delegates.gt(0)).sum()),
          "; median listed share greyed", round(c[c.greyed].share_listed.median(), 3),
          "vs not greyed", round(c[~c.greyed].share_listed.median(), 3))
    print("Unmatched candidates with delegates (units):",
          body[body.line.eq("candidate") & body.candidate_key.isna() & body.delegates.gt(0)].candidate_name.unique().tolist()[:15])
    print("Unmatched candidates with votes (tallies, top 10 by count):",
          tal[tal.line.eq("candidate") & tal.candidate_key.isna()].groupby(["cycle", "candidate_name"])["count"].sum()
          .sort_values(ascending=False).head(10).to_dict())
    # downloads
    print("\nDelegate count rows by cycle and party:", cnt.groupby(["cycle", "party"]).size().to_dict())
    d = pd.read_csv(INTERIM / "primary_delegates.csv")
    d = d[d.cycle.isin(CYCLES) & d.line.eq("candidate")].groupby(["cycle", "party", "state", "candidate_key"]).delegates.sum()
    h = cnt[cnt.line.eq("candidate")].groupby(["cycle", "party", "state", "candidate_key"]).hard_total.sum()
    jj = pd.concat([d.rename("pages"), h.rename("spreadsheet")], axis=1).fillna(0)
    off = jj[(jj.pages - jj.spreadsheet).abs() > 0.51]
    print("Hard totals, spreadsheet against the state pages (state, candidate):", len(off), "differ of", len(jj))
    if len(off):
        print(off.head(20).to_string())
    print("Unmatched names with hard delegates:",
          cnt[cnt.line.eq("candidate") & cnt.candidate_key.isna() & cnt.hard_total.gt(0)].candidate_name.unique().tolist())
    r = pd.read_csv(INTERIM / "primary_delegate_rules.csv")
    r = r[r.cycle.isin(CYCLES)].set_index(["cycle", "party", "state"]).total_delegates
    for party, x in (("D", ad), ("R", ar)):
        y = x.assign(party=party).set_index(["cycle", "party", "state"]).total_delegates
        z = pd.concat([r.rename("pages"), y.rename("spreadsheet")], axis=1, join="inner")
        off = z[(z.pages - z.spreadsheet).abs() > 0.51]
        print(f"{party} allocation totals against the pages: {len(off)} of {len(z)} differ;",
              "convention size", x.groupby("cycle").total_delegates.sum().to_dict())
        if len(off):
            print(off.to_string())
    print("Events rows by cycle:", ev.groupby("cycle").size().to_dict() if len(ev) else "none")


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        fetch_downloads()
        fetch_results()
    elif sys.argv[1:] == ["fetch-downloads"]:
        fetch_downloads()
    else:
        main()
