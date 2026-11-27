"""Watch list of House and Senate vacancies and special elections (SP-8; SPECIALS.md, section 4).

Two sources, checked weekly:
  - the House Clerk's vacancy page (official; House vacancies that have happened, with "Special Election Date TBD"
    or the successor and oath date);
  - Wikipedia's "<n>th United States Congress" pages, section "Changes in membership" (Senate and House tables;
    announced resignations, appointments and special election dates, the dates read from the prose).
Rows are kept for the current Congress and the next once its page exists; rows of earlier Congresses already in the
file are kept as they are. Where the Clerk and Wikipedia disagree, both are reported in `note` and nothing is decided.

Statuses (rule 3): announced, vacant_no_date, special_scheduled, appointed, held, filled, no_special; and gone, for a
row of a watched Congress that is no longer in either source (kept, so the change trips the check once).
A live special (rule 4): a special election with a date found, not yet held, not on a regular general-election day,
seat not filled. A trip is any new row or any change to a row (rule 5); the changes go to ci_out/specials_watch.md.
A source that fails to load or parse raises, so the run fails instead of writing an empty list.

Run:  python src/collect/specials_watch.py            (writes data/interim/specials_watch.csv and ci_out/specials_watch.md)
      python src/collect/specials_watch.py --dry-run  (prints the changes, writes nothing)
"""
import datetime as dt
import html as htmllib
import io
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, fetch  # noqa: E402

OUT = ROOT / "data/interim/specials_watch.csv"
CI = ROOT / "ci_out"
CLERK = "https://clerk.house.gov/Members/ViewVacancies"
WIKI_API = "https://en.wikipedia.org/w/api.php"
COLS = ["congress", "chamber", "state", "seat", "vacated_by", "party", "reason", "vacancy_date", "successor",
        "seated_date", "special_dates", "status", "live_special", "clerk", "note"]
KEY = ["congress", "chamber", "state", "seat", "vacated_by"]

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
FULL_DATE = rf"(?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}}"
MONTH_YEAR = rf"(?:{MONTHS})\s+\d{{4}}"
MONTH_DAY = rf"(?:{MONTHS})\s+\d{{1,2}}(?!\d)(?!,?\s*\d{{4}})"   # "August 18", year left out after an earlier date
STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
          "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
          "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
          "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
          "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
          "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"]
STATE_RE = "|".join(sorted(STATES, key=len, reverse=True))


def iso(text):
    """'April 21, 2026' -> '2026-04-21'; 'November 2027' -> '2027-11'; else ''."""
    text = re.sub(r"\s+", " ", text or "").strip()
    for fmt in ("%B %d, %Y", "%B %Y"):
        try:
            d = dt.datetime.strptime(text, fmt)
            return d.strftime("%Y-%m-%d" if "%d" in fmt else "%Y-%m")
        except ValueError:
            pass
    return ""


def general_day(year):
    """The regular November general-election day of an even year (Tuesday after the first Monday)."""
    d = dt.date(year, 11, 2)
    while d.weekday() != 1:
        d += dt.timedelta(days=1)
    return d


def is_general_day(date_str):
    """True for a full date on an even year's general-election day; a bare 'November <even year>' counts too."""
    if re.fullmatch(r"\d{4}-11", date_str):
        return int(date_str[:4]) % 2 == 0
    try:
        d = dt.date.fromisoformat(date_str)
    except ValueError:
        return False
    return d.year % 2 == 0 and d == general_day(d.year)


def congress_for(day):
    """The Congress in session on a date (terms begin 3 January of odd years)."""
    y = day.year if (day.month, day.day) >= (1, 3) else day.year - 1
    return (y - 1789) // 2 + 1


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def text_of(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", htmllib.unescape(t)).strip()


def clean(s):
    s = "" if s is None or (isinstance(s, float) and pd.isna(s)) else str(s)
    s = re.sub(r"\[[^\]]*\]", "", s)           # footnote markers
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


# ---------- House Clerk ----------

def clerk_rows():
    path = fetch("specials_watch", "clerk_vacancies.html", CLERK, skip_existing=False)
    t = text_of(path.read_text(encoding="utf-8"))
    m = re.search(r"Vacancies of the (\d+)\w\w Congress", t)
    if not m:
        raise RuntimeError("Clerk page: no 'Vacancies of the <n>th Congress' heading")
    congress = int(m.group(1))
    parts = re.split(rf"({STATE_RE}) [–-] (\d+\w\w|At Large) District", t)
    rows = []
    for i in range(1, len(parts) - 2, 3):
        state, dist, body = parts[i], parts[i + 1], parts[i + 2]
        body = re.split(r"\bSession \d\b", body)[0]
        seat = "AL" if dist == "At Large" else str(int(re.match(r"\d+", dist).group()))
        how = re.search(rf"(Passed Away|Resigned|Expelled|Died|Vacated)\s+({FULL_DATE})", body)
        rep = re.search(r"Rep\. (.+?)(?= Succeeded| Special| Office| Oath|$)", body)
        succ = re.search(rf"Succeeded ({FULL_DATE}) Rep\. (.+?) Oath of Office on ({FULL_DATE})", body)
        tbd = re.search(rf"Special Election Date (TBD|{FULL_DATE})", body)
        if succ:
            clerk = f"filled: elected {iso(succ.group(1))}, sworn {iso(succ.group(3))}"
        elif tbd:
            clerk = "special date TBD" if tbd.group(1) == "TBD" else f"special {iso(tbd.group(1))}"
        else:
            clerk = "listed"
        rows.append({"congress": congress, "state": state, "seat": seat,
                     "vacated_by": clean(rep.group(1)) if rep else "",
                     "vacancy_date": iso(how.group(2)) if how else "",
                     "reason_clerk": (how.group(1).lower() if how else ""),
                     "successor": clean(succ.group(2)) if succ else "",
                     "seated_date": iso(succ.group(3)) if succ else "",
                     "special_clerk": iso(tbd.group(1)) if tbd and tbd.group(1) != "TBD" else "",
                     "clerk": clerk})
    # an empty list is legitimate (a new Congress opens with none); a missing heading is not, and raised above
    return congress, rows


# ---------- Wikipedia ----------

def wiki_api(params, name):
    q = "&".join(f"{k}={v}" for k, v in {**params, "format": "json", "formatversion": 2}.items())
    path = fetch("specials_watch", name, f"{WIKI_API}?{q}", skip_existing=False)
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def wiki_tables(congress):
    """{'Senate': DataFrame, 'House': DataFrame} from the page's membership-change sections, or None if no page."""
    page = f"{ordinal(congress)}_United_States_Congress"
    d = wiki_api({"action": "parse", "page": page, "prop": "sections|revid"}, f"wiki_{congress}_sections.json")
    if "error" in d:
        if d["error"].get("code") == "missingtitle":
            return None, None
        raise RuntimeError(f"Wikipedia {page}: {d['error']}")
    rev = d["parse"]["revid"]
    out = {}
    for s in d["parse"]["sections"]:
        line = s["line"].lower()
        for chamber in ("Senate", "House"):
            if line == f"{chamber.lower()} membership changes":
                h = wiki_api({"action": "parse", "page": page, "section": s["index"], "prop": "text"},
                             f"wiki_{congress}_{chamber.lower()}.json")["parse"]["text"]
                if "<table" not in h:
                    continue
                tabs = pd.read_html(io.StringIO(h))
                tab = max(tabs, key=len)
                if not any("Vacated" in str(c) for c in tab.columns):
                    raise RuntimeError(f"Wikipedia {page} {chamber}: unexpected columns {list(tab.columns)}")
                out[chamber] = tab
    return out, rev


def parse_party(name):
    m = re.search(r"\(([A-Z]{1,3})\)\s*$", name)
    return (name[:m.start()].strip(), m.group(1)) if m else (name.strip(), "")


def reason_of(text):
    t = text.lower()
    if "changed part" in t:
        return "party change"
    if re.search(r"\bdie[ds]?\b|\bdeath\b|passed away", t):
        return "died"
    if "resign" in t:
        return "resigned"
    if "expel" in t:
        return "expelled"
    if "lost" in t and "election" in t:
        return "appointee lost special"
    if "chose to wait" in t or "senator-elect" in t:
        return "seat not taken up"
    return "other"


def special_dates(text):
    """Dates tied to a special election in the reason prose, in order; 'runoff' dates marked."""
    out = []
    for sent in re.split(r"(?<=\.)\s+", text):
        if not re.search(r"special election|runoff|special primary|elected .*to finish the term", sent, re.I):
            continue
        last = None
        for m in re.finditer(rf"({FULL_DATE}|{MONTH_YEAR}|{MONTH_DAY})", sent):
            d = iso(m.group(1))
            if not d and last:                      # no year: the year of the sentence's previous date, or the next
                d = iso(f"{m.group(1)}, {last[:4]}")
                if d and d < last:
                    d = iso(f"{m.group(1)}, {int(last[:4]) + 1}")
            if d:
                last = d
            before = sent[:m.start()].lower()
            if not d or re.search(r"(ending|ends|expir\w*|through|until)\s*$", before):   # a term's end, not an election
                continue
            tag = "runoff " if before.rfind("runoff") > before.rfind("special election") else ""
            if (tag + d) not in out:
                out.append(tag + d)
    return out


def wiki_rows(congress, today):
    tabs, rev = wiki_tables(congress)
    if tabs is None:
        return [], None
    rows = []
    for chamber, tab in tabs.items():
        tab.columns = [clean(c) for c in tab.columns]
        c_seat = tab.columns[0]
        c_vac = next(c for c in tab.columns if c.startswith("Vacated"))
        c_why = next(c for c in tab.columns if c.startswith("Reason"))
        c_succ = next(c for c in tab.columns if c.startswith("Successor"))
        c_date = next(c for c in tab.columns if c.startswith("Date"))
        for _, r in tab.iterrows():
            where, why = clean(r[c_seat]), clean(r[c_why])
            vac_name, vac_party = parse_party(clean(r[c_vac]))
            succ_name, _ = parse_party(clean(r[c_succ]))
            seated_txt = clean(r[c_date])
            reason = reason_of(why)
            if reason == "party change":
                continue                                    # not a vacancy
            if chamber == "House":
                m = re.match(rf"({STATE_RE})\s*(at-large|\d+)", where, re.I)
                if not m:
                    raise RuntimeError(f"Wikipedia House row not understood: {where!r}")
                state, seat = m.group(1), ("AL" if m.group(2).lower() == "at-large" else str(int(m.group(2))))
            else:
                m = re.match(rf"({STATE_RE})\s*\((\d)\)", where)
                if not m:
                    raise RuntimeError(f"Wikipedia Senate row not understood: {where!r}")
                state, seat = m.group(1), f"class {m.group(2)}"
            dates = re.findall(FULL_DATE, why)
            vac_m = re.search(rf"(?:died|resigned|resigning(?: on)?|resign(?:s|ing)? effective|expelled)\s+(?:on\s+)?({FULL_DATE}|{MONTH_YEAR})",
                              why, re.I)
            eff = re.search(rf"effective\s+(?:on\s+)?({FULL_DATE})", why, re.I)   # an announced resignation's date
            vacancy_date = iso(eff.group(1)) if eff else iso(vac_m.group(1)) if vac_m else (iso(dates[0]) if dates else "")
            vacant_later = "vacant until the next congress" in succ_name.lower() or "vacant until" in seated_txt.lower()
            seated = iso(seated_txt)
            successor = "" if vacant_later or succ_name.upper() in ("TBD", "") or succ_name.lower().startswith("vacant") else succ_name
            sp = special_dates(why)
            rows.append({"congress": congress, "chamber": chamber, "state": state, "seat": seat,
                         "vacated_by": vac_name, "party": vac_party, "reason": reason,
                         "vacancy_date": vacancy_date, "successor": successor, "seated_date": seated,
                         "special_dates": "; ".join(sp), "why": why, "vacant_later": vacant_later})
    return rows, rev


# ---------- status ----------

def status_of(r, today):
    why = r.get("why", "").lower()
    sp = [s.replace("runoff ", "") for s in r["special_dates"].split("; ") if s]
    last_sp = max(sp) if sp else ""
    vd = r["vacancy_date"]
    if vd and vd > today.isoformat() and not (r["seated_date"] and r["seated_date"] <= today.isoformat()):
        return "announced"
    if r["successor"] and r["seated_date"] and r["seated_date"] <= today.isoformat():
        if r["chamber"] == "Senate" and "appoint" in why and last_sp and last_sp >= today.isoformat()[:len(last_sp)]:
            return "appointed"
        return "filled"
    if r.get("vacant_later") and not sp:
        return "no_special"
    if last_sp:
        if last_sp < today.isoformat()[:len(last_sp)]:
            return "held"
        return "special_scheduled"
    if r["chamber"] == "Senate" and "appoint" in why:
        return "appointed"
    return "vacant_no_date"


def live(r, today):
    if r["status"] not in ("special_scheduled", "appointed", "announced"):
        return False
    # the next round still to come, first round or runoff; live unless it falls on a general-election day
    ahead = [s.replace("runoff ", "") for s in r["special_dates"].split("; ") if s]
    ahead = [d for d in ahead if d >= today.isoformat()[:len(d)]]
    return bool(ahead) and not is_general_day(min(ahead))


# ---------- build ----------

def build(today):
    cur = congress_for(today)
    clerk_cong, clerk = clerk_rows()
    wiki = []
    revs = {}
    for c in (cur, cur + 1):
        rows, rev = wiki_rows(c, today)
        if c == cur and not rows:
            raise RuntimeError(f"Wikipedia: no membership-change rows for the {ordinal(c)} Congress")
        wiki += rows
        if rev:
            revs[c] = rev
    # Clerk rows are matched to Wikipedia's House rows by seat; where Wikipedia has more than one row for a seat in a
    # Congress, the one with the nearest vacancy date (Wikipedia names a seat empty at the start as "Vacant")
    by_seat = {(r["congress"], r["state"], r["seat"], i): r for i, r in enumerate(clerk)}
    match = {}
    for k, cl in by_seat.items():
        cands = [j for j, r in enumerate(wiki) if r["chamber"] == "House" and (r["congress"], r["state"], r["seat"]) == k[:3]
                 and j not in match.values()]
        if cands:
            gap = lambda j: abs((dt.date.fromisoformat(wiki[j]["vacancy_date"][:10]) - dt.date.fromisoformat(cl["vacancy_date"])).days)                 if len(wiki[j]["vacancy_date"]) == 10 and cl["vacancy_date"] else 10 ** 6
            match[k] = min(cands, key=gap)
    by_row = {j: k for k, j in match.items()}
    out, used = [], set()
    for j, r in enumerate(wiki):
        k = by_row.get(j)
        cl = by_seat[k] if k else None
        notes = []
        r["clerk"] = ""
        if cl:
            used.add(k)
            r["clerk"] = cl["clerk"]
            if cl["vacancy_date"] and r["vacancy_date"] and cl["vacancy_date"] != r["vacancy_date"]:
                notes.append(f"vacancy date: Clerk {cl['vacancy_date']}, Wikipedia {r['vacancy_date']}")
            r["vacancy_date"] = cl["vacancy_date"] or r["vacancy_date"]      # the Clerk is official once it lists it
            if cl["clerk"] == "special date TBD" and r["vacant_later"]:
                notes.append("Clerk: special date TBD; Wikipedia: vacant until the next Congress")
            if cl["special_clerk"] and cl["special_clerk"] not in r["special_dates"]:
                r["special_dates"] = "; ".join(x for x in (r["special_dates"], cl["special_clerk"]) if x)
        if re.search(r"special election|special primary", r["why"], re.I) and not r["special_dates"] \
                and not r["successor"]:
            notes.append("Wikipedia mentions a special election with no date the check can read")
        r["status"] = status_of(r, today)
        r["live_special"] = "yes" if live(r, today) else ""
        r["note"] = "; ".join(notes)
        out.append(r)
    for k, cl in by_seat.items():
        if k in used or cl["congress"] not in (cur, cur + 1):
            continue
        r = {"congress": cl["congress"], "chamber": "House", "state": cl["state"], "seat": cl["seat"],
             "vacated_by": cl["vacated_by"], "party": "", "reason": cl["reason_clerk"].replace("passed away", "died"),
             "vacancy_date": cl["vacancy_date"], "successor": cl["successor"], "seated_date": cl["seated_date"],
             "special_dates": cl["special_clerk"], "why": "", "vacant_later": False, "clerk": cl["clerk"]}
        r["status"] = status_of(r, today)
        r["live_special"] = "yes" if live(r, today) else ""
        r["note"] = "on the Clerk's list, not in Wikipedia's table"
        out.append(r)
    df = pd.DataFrame(out)[COLS].astype(str)
    return df, clerk_cong, revs, len(clerk)


def changes(old, new):
    """Markdown lines: new rows, changed fields, rows gone (rule 5)."""
    lines = []
    o = {tuple(r[k] for k in KEY): r for r in old.to_dict("records")}
    n = {tuple(r[k] for k in KEY): r for r in new.to_dict("records")}
    label = lambda r: (f"{r['state']} {r['seat']}" if r["chamber"] == "House" else f"{r['state']} Senate ({r['seat']})") \
        + f", {r['vacated_by']} ({r['congress']}th Congress)"
    for k, r in n.items():
        if k not in o:
            lines.append(f"- **New:** {label(r)}: {r['reason']}, {r['status']}"
                         + (f", special {r['special_dates']}" if r["special_dates"] else "")
                         + (" — **LIVE SPECIAL**" if r["live_special"] == "yes" else ""))
        elif r["status"] == "gone" and o[k]["status"] != "gone":
            lines.append(f"- **Gone from the sources:** {label(r)} (was {o[k]['status']}; kept in the file as gone; "
                         "a renamed row in Wikipedia shows up as new beside it)")
        else:
            diff = [f"{c} `{o[k][c] or '-'}` → `{r[c] or '-'}`" for c in COLS if c not in KEY and o[k][c] != r[c]]
            if diff:
                lines.append(f"- **Changed:** {label(r)}: " + "; ".join(diff)
                             + (" — **LIVE SPECIAL**" if r["live_special"] == "yes" and o[k]["live_special"] != "yes" else ""))
    return lines


def main(dry=False):
    today = dt.date.today()
    new, clerk_cong, revs, n_clerk = build(today)
    old = pd.read_csv(OUT, dtype=str, keep_default_na=False) if OUT.exists() else pd.DataFrame(columns=COLS)
    cur = congress_for(today)
    keep_old = old[~old["congress"].astype(int).isin([cur, cur + 1])] if len(old) else old
    # rows of the watched Congresses that vanish from both sources are kept, flagged in the change list
    gone = old[old["congress"].astype(int).isin([cur, cur + 1])] if len(old) else old
    if len(gone):
        newkeys = set(map(tuple, new[KEY].values))
        gone = gone[[tuple(x) not in newkeys for x in gone[KEY].values]].copy()
        fresh = gone["status"] != "gone"
        gone.loc[fresh, "note"] = gone.loc[fresh, "note"].where(gone.loc[fresh, "note"] == "", gone.loc[fresh, "note"] + "; ")             + f"gone from the sources {today}"
        gone["status"], gone["live_special"] = "gone", ""
    merged = pd.concat([keep_old, new, gone], ignore_index=True)[COLS]
    merged = merged.sort_values(["congress", "chamber", "vacancy_date", "state", "seat"], ignore_index=True)
    lines = changes(old, merged)
    lives = merged[merged["live_special"] == "yes"]
    summary = [f"Specials watch, {today}: Clerk list for the {ordinal(clerk_cong)} Congress ({n_clerk} vacancies listed); "
               "Wikipedia revisions " + ", ".join(f"{ordinal(c)} Congress {r}" for c, r in revs.items()) + ".", ""]
    summary += (["**Changes since the last check**", ""] + lines) if lines else ["No changes since the last check."]
    if len(lives):
        summary += ["", "**Live specials** (ready for the SP-7 steps: race details, lean on the lines in force, polls, run, page):", ""]
        summary += [f"- {r.state} {r.seat if r.chamber == 'House' else 'Senate (' + r.seat + ')'}: special {r.special_dates}"
                    for r in lives.itertuples()]
    notes = merged[(merged["note"] != "") & merged["congress"].astype(int).isin([cur, cur + 1])]
    if len(notes):
        summary += ["", "**For a person to check**", ""]
        summary += [f"- {r.state} {r.seat}: {r.note}" for r in notes.itertuples()]
    text = "\n".join(summary) + "\n"
    print(text)
    if dry:
        return
    merged.to_csv(OUT, index=False)
    CI.mkdir(exist_ok=True)
    (CI / "specials_watch.md").write_text(text, encoding="utf-8")
    (CI / "specials_watch_changed").write_text("yes" if lines else "no", encoding="utf-8")


if __name__ == "__main__":
    main(dry="--dry-run" in sys.argv)
