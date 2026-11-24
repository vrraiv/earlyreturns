"""Build the pages around the elections: the landing page, the coming cycles' pages (/2027/, /2028/), each past election's
opening page, 404.html and _redirects, and the link-preview cards (site/og-home.png, site/<year>/og.png).

    python src/site/landing.py        (src/site/build.py runs this too)

Everything here comes from src/site/site.json and, for the landing page's figures, data/scorecard/scorecard.json;
the 2028 page's board (EC-8) also reads three files in data/interim (`board_data` below). No
page carries a build date, so a rebuild with the same scorecard writes the same bytes; the daily scorecard job changes
the landing page only when the seat counts change, and leaves the preview cards alone (only `landing.py` run by itself
or `build.py --all` draws them, after a change to site.json). build.py passes the scorecard it read for the forecast page, so the
two pages show the same numbers; run alone, this reads the same file.

Each coming cycle's page (previews in site.json: 2027, the governor races; 2028) is the "coming" state SI-1 set out: a
note, what is being built and the dates; 2028's also carries the board before the nominees (EC-8, `board` below). Their tracks and dates are copied from planning/plan.js (the tracks' goals,
`deadlines` and `events`); change them there first. No forecast numbers appear on them until a model is frozen; then
the cycle gets pages of its own (2027: GV-6; 2028: the governors, electoral college and primaries pages).

Old links. Until SI-6 the forecast was the page at `/`, and its tabs were addressed as `/#senate`, `/#senate/<race>`
and so on. A server never sees what follows `#`, so the landing page forwards those itself (FORWARD below).
`/data/*` moved to `/2026/data/*` and is redirected by `_redirects`, which Cloudflare reads from the assets folder.
"""
import html
import json
from pathlib import Path

import shell

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
SCORECARD = ROOT / "data" / "scorecard" / "scorecard.json"
S = shell.SETTINGS
E = html.escape

# The forecast page's tab names (PAGES in template.html) and its two race prefixes. No element on the landing page
# may take one of these as its id, or a link to it would be forwarded.
OLD_TABS = ["overview", "scorecard", "senate", "house", "method", "bias", "backtest", "appendix", "data"]
FORWARD = ("<script>(function(){function f(){var h=location.hash.slice(1),t=" + json.dumps(OLD_TABS, separators=(",", ":")) +
           ";if(t.indexOf(h)>=0||h.indexOf('senate/')===0||h.indexOf('house/')===0)"
           "location.replace('2026/forecast/'+location.hash);}f();addEventListener('hashchange',f);})();</script>")
REDIRECTS = "/data/* /2026/data/:splat 301\n"
# The scorecard page's names for the published versions (MODELS in template.html).
VERSION_NAME = {"polls_only": "polls only", "polls_fundamentals": "polls + fundamentals",
                "polls_fundamentals_biasadj": "bias-adjusted"}


def head(title, desc, prefix, extra=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
{shell.head(prefix)}
{extra}</head>
"""


def og(title, desc, image, path):
    return (f'<meta property="og:title" content="{E(title)}">\n'
            f'<meta property="og:description" content="{E(desc)}">\n'
            f'<meta property="og:image" content="{S["base_url"]}/{image}">\n'
            f'<meta property="og:url" content="{S["base_url"]}/{path}">\n'
            '<meta name="twitter:card" content="summary_large_image">\n')


def foot():
    return f"""<footer><div class="wrap">
{shell.footer()}
</div></footer>
{shell.script()}
</body>
</html>
"""


def card(c, cls="sec", inner=""):
    label = f'<div class="kicker">{E(c["label"])}</div>' if c.get("label") else ""
    return (f'<a class="{cls}" href="{E(c["path"])}">{label}<h3>{E(c["title"])}</h3>'
            f'<p>{E(c["text"])}</p>{inner}</a>')


def seat_lines(sc, version):
    """The scorecard's seat cards in two lines, as the scorecard tab words them (seatCard in template.html)."""
    if not sc:
        return ""
    rows = []
    for ch, lab in (("senate", "Senate"), ("house", "House")):
        s = sc[ch]["seats"]
        lo = s["dem_seats_called"]
        hi = s.get("dem_seats_max", lo + s.get("n_pending", 0))
        pend = len(s.get("pending", [])) if ch == "senate" else s.get("n_pending", 0)
        if hi - lo > 25:      # too many races uncalled for a range to say anything (the scorecard tab's rule)
            res = f'{lo} D, {s["rep_seats_called"]} R called so far'
        else:
            res = f'{lo if lo == hi else f"{lo}–{hi}"} Democratic seats{"" if lo == hi else " so far"}'
        if pend:
            res += f' ({pend} uncalled)'
        v = s["versions"][version]
        rows.append(f'<div class="seatline"><span class="ch">{lab}</span><span class="res">{E(res)}</span>'
                    f'<span class="fc">Forecast: {v["mean"]:.1f} on average, 80% range {v["p10"]:.0f}–{v["p90"]:.0f}</span></div>')
    label = ("Provisional: counting continues, and races still being counted are left out." if sc.get("provisional")
             else "Final.")
    return (f'<div class="seatlines">{"".join(rows)}</div>'
            f'<p class="tiny">{E(label)} Forecast version: {E(VERSION_NAME[version])}.</p>')


# The tile map: one square per state at (column, row). The forecast page's layout (TILES in template.html); keep the
# two the same. 50 states; DC has no senators.
TILES = {
    "AK": (0, 0), "ME": (11, 0),
    "WI": (6, 1), "VT": (10, 1), "NH": (11, 1),
    "WA": (1, 2), "ID": (2, 2), "MT": (3, 2), "ND": (4, 2), "MN": (5, 2), "IL": (6, 2), "MI": (7, 2), "NY": (9, 2),
    "MA": (10, 2),
    "OR": (1, 3), "NV": (2, 3), "WY": (3, 3), "SD": (4, 3), "IA": (5, 3), "IN": (6, 3), "OH": (7, 3), "PA": (8, 3),
    "NJ": (9, 3), "CT": (10, 3), "RI": (11, 3),
    "CA": (1, 4), "UT": (2, 4), "CO": (3, 4), "NE": (4, 4), "MO": (5, 4), "KY": (6, 4), "WV": (7, 4), "VA": (8, 4),
    "MD": (9, 4), "DE": (10, 4),
    "AZ": (2, 5), "NM": (3, 5), "KS": (4, 5), "AR": (5, 5), "TN": (6, 5), "NC": (7, 5), "SC": (8, 5),
    "OK": (4, 6), "LA": (5, 6), "MS": (6, 6), "AL": (7, 6), "GA": (8, 6),
    "HI": (0, 7), "TX": (4, 7), "FL": (9, 7),
}
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}
assert len(TILES) == 50 == len(set(TILES.values())) and set(TILES) == set(STATE_NAMES)
PARTY = {"D": ("dem", "D"), "R": ("rep", "R"), "I": ("ind", "independent")}


# The 2028 page's board before the nominees (EC-8; ELECTORAL_COLLEGE.md, section 17). There is no forecast until both
# nominees are presumptive; until then the page shows each contest's 2028 electoral votes and how it voted in the seven
# elections 2000 to 2024, as grey tiles with a strip of seven bars. Nothing on it comes from a model.
# Electoral votes: data/interim/electoral_votes.csv, election 2028 (the 2020 census, as in 2024). States' results:
# state_presidential.csv (2024 collected by the governors track). Districts' results 1996 to 2020:
# district_presidential.csv. The electoral college collector never opens the 2024 results page (the holdout), so the
# five districts' 2024 winners are written here, for display only; nothing in src/model reads them.
BOARD_YEARS = (2000, 2004, 2008, 2012, 2016, 2020, 2024)
BOARD_TILES = {**TILES, "DC": (9, 5)}            # DC beside Maryland; the districts go in a strip under the map
BOARD_DISTRICTS = ("ME-1", "ME-2", "NE-1", "NE-2", "NE-3")
# The five districts' 2024 winners, from NBC News's results pages (data: the National Election Pool), read 2026-11-24:
# nbcnews.com/politics/2024-elections/maine-president-results and .../nebraska-president-results. Two-candidate shares:
# ME-1 Harris 59.5 Trump 38.3; ME-2 Trump 53.6 Harris 44.3; NE-1 Trump 55.5 Harris 42.5; NE-2 Harris 51.3 Trump 46.7;
# NE-3 Trump 76.0 Harris 22.4. The pages' statewide splits agree (Harris 3 of Maine's 4, Trump 4 of Nebraska's 5).
# When the design freeze (EC-9) collects the 2024 district results, the assert in board_data stops the build: then
# delete this table.
DISTRICTS_2024 = {"ME-1": "D", "ME-2": "R", "NE-1": "R", "NE-2": "D", "NE-3": "R"}
BOARD_NAMES = {**STATE_NAMES, "DC": "District of Columbia", "ME-1": "Maine's 1st district",
               "ME-2": "Maine's 2nd district", "NE-1": "Nebraska's 1st district", "NE-2": "Nebraska's 2nd district",
               "NE-3": "Nebraska's 3rd district"}
INTERIM = ROOT / "data" / "interim"


def board_data():
    """[(contest, column, row, electoral votes, {year: "D" or "R"})] for the 2028 board, in drawing order: states and
    DC on the tile grid, then the districts in a strip two rows under it (Maine's two, a gap, Nebraska's three)."""
    import csv
    ev = {r["contest"]: int(r["ev"]) for r in csv.DictReader(open(INTERIM / "electoral_votes.csv", encoding="utf-8"))
          if r["election"] == "2028"}
    won = {}
    for name, key in (("state_presidential.csv", "state"), ("district_presidential.csv", "contest")):
        for r in csv.DictReader(open(INTERIM / name, encoding="utf-8")):
            if int(r["year"]) in BOARD_YEARS:
                won.setdefault(r[key], {})[int(r["year"])] = "D" if float(r["d_votes"]) > float(r["r_votes"]) else "R"
    for k, w in DISTRICTS_2024.items():
        assert 2024 not in won.get(k, {}), "2024 district results now in the data: drop DISTRICTS_2024"
        won.setdefault(k, {})[2024] = w
    out = [(k, c, r, ev[k], won[k]) for k, (c, r) in BOARD_TILES.items()]
    out += [(k, i + (0.25 if i >= 2 else 0), 9, ev[k], won[k]) for i, k in enumerate(BOARD_DISTRICTS)]
    assert sum(x[3] for x in out) == 538 and set(ev) == {x[0] for x in out}, "the board must hold all 538 votes"
    assert all(set(x[4]) == set(BOARD_YEARS) for x in out), "a contest is missing a year"
    return out


# The elephant and the donkey, drawn for the site in the mark's manner (rounded single-weight strokes, one colour).
ELEPHANT = ('<svg viewBox="0 0 64 48" class="mascot rep" aria-hidden="true" focusable="false"><g fill="none" '
            'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M8 27 C8 16 18 10 32 10 C40 10 45 9 50 9 C56 9 60 14 59 21 C60 28 61 33 62 37 C62.5 40 59.5 41 '
            '58 38 C57 34 56 30 54 26 L50 28"/><path d="M52 28 C53 31 55 32 57 31"/>'
            '<path d="M47 12 C41 12 38 19 39 25 C40 30 46 31 48 27"/>'
            '<path d="M8 27 C8 31 10 34 13 35 L13 43 L19 43 L19 37 L37 37 L37 43 L43 43 L43 35 C45 33 46 31 47 29"/>'
            '<path d="M8 25 C5 27 4 30 4 33"/></g><circle cx="52" cy="16" r="1.5" fill="currentColor"/></svg>')
DONKEY = ('<svg viewBox="0 0 64 48" class="mascot dem" aria-hidden="true" focusable="false"><g fill="none" '
          'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
          '<path d="M18 22 L40 22 C44 22 45 19 46 16"/>'
          '<path d="M18 22 C14 23 13 27 14 31 L16 33 L16 43 L21 43 L21 34 L35 34 L35 43 L40 43 L40 33 C42 31 43 28 43 24"/>'
          '<path d="M46 16 L44 4 L49 13"/><path d="M50 14 L52 3 L54 14"/>'
          '<path d="M49 13 C55 14 59 18 59 23 C59 26 56 27 53 26 L46 22"/>'
          '<path d="M14 25 C10 27 9 31 10 35"/><path d="M10 35 L8 38 M10 35 L11 38.5"/></g>'
          '<circle cx="53" cy="18.5" r="1.4" fill="currentColor"/></svg>')


def board(B):
    """The board as a static SVG block (site.json previews.2028.board holds the words)."""
    U, T = 34, 31                    # grid step and tile size
    sw = (T - 6) / 7
    tiles = []
    for k, c, r, ev, won in board_data():
        x, y = c * U, r * U - (4 if r == 9 else 0)
        nd = sum(v == "D" for v in won.values())
        seq = ", ".join(f"{yr} {'D' if won[yr] == 'D' else 'R'}" for yr in BOARD_YEARS)
        tip = (f"{BOARD_NAMES[k]}: {ev} electoral vote{'s' if ev != 1 else ''} in 2028. Voted Democratic {nd} of 7 "
               f"times since 2000, Republican {7 - nd} ({seq}).")
        bars = "".join(f'<rect class="{"d" if won[yr] == "D" else "r"}" x="{x + 3 + i * sw + .4:.2f}" y="{y + T - 8}" '
                       f'width="{sw - .8:.2f}" height="5" rx="1"/>' for i, yr in enumerate(BOARD_YEARS))
        tiles.append(f'<g><title>{E(tip)}</title><rect class="t" x="{x:g}" y="{y}" width="{T}" height="{T}" rx="3"/>'
                     f'<text class="st" x="{x + T / 2:g}" y="{y + 10}">{k}</text>'
                     f'<text class="ev" x="{x + T / 2:g}" y="{y + 20.5}">{ev}</text>{bars}</g>')
    tiles.append(f'<text class="cap" x="0" y="{9 * U - 10}">{E(B["districts"])}</text>')
    W, H = 12 * U, 9 * U - 4 + T
    always = lambda p: sum(1 for x in board_data() if all(v == p for v in x[4].values()))
    summary = (f"Map of the 2028 electoral votes: 538 in all, 270 to win, by state, with Maine's and Nebraska's "
               f"districts. For each, how it voted in the seven elections from 2000 to 2024. "
               f"Of the 56, {always('D')} voted Democratic every time and {always('R')} Republican every time.")
    legend = (f'<div class="maplegend" aria-hidden="true"><span><i class="dem"></i>Democratic</span>'
              f'<span><i class="rep"></i>Republican</span><span class="how">{E(B["legend"])}</span></div>')
    return (f'<section class="board"><div class="boardhead">{ELEPHANT}<div><h2>{E(B["title"])}</h2>'
            f'<p>{E(B["text"])}</p></div>{DONKEY}</div>'
            f'<figure class="ecboard"><svg viewBox="-1 -1 {W + 2} {H + 2}" role="img" aria-label="{E(summary)}">'
            f'{"".join(tiles)}</svg>{legend}</figure><p class="tiny">{E(B["note"])}</p></section>')


def pct(p):
    return "under 1%" if p < 0.005 else "over 99%" if p > 0.995 else f"{p:.0%}"


def senate_map(sc, version):
    """The 2026 Senate races as a tile map: each state's winner, with upsets outlined as on the forecast page (won by
    the side the forecast gave under 50%). A race's probability is the non-Republican side's chance, so the winner's
    chance is p, or 1 - p for a Republican. Static SVG (the card is a link, so nothing in it is interactive); each
    tile's <title> gives the details on hover. Returns "" if the scorecard lacks what it needs."""
    races = {}
    for r in sc.get("senate", {}).get("races", []):
        st = r["race_key"].split("|")[1]
        if st in races:          # two races in one state (a regular and a special) would need a split tile
            return ""
        races[st] = r
    if not races or any(version not in r or r["winner_party"] not in PARTY for r in races.values() if r.get("called")):
        return ""
    U, T = 30, 27                # grid step and tile size
    tiles, won, upsets = [], {"dem": 0, "rep": 0, "ind": 0}, []
    for st, (c, rw) in TILES.items():
        x, y, name = c * U, rw * U, STATE_NAMES[st]
        r = races.get(st)
        ring = ""
        if r is None:
            cls, tip = "none", f"{name}: no Senate race in 2026"
        elif not r.get("called"):
            cls, tip = "pend", f"{name}: not yet called"
        else:
            cls, pname = PARTY[r["winner_party"]]
            won[cls] += 1
            pw = 1 - r[version] if r["winner_party"] == "R" else r[version]
            tip = f"{name}: {r['winner']} ({pname}) won. The forecast gave the winner a {pct(pw)} chance."
            if pw < 0.5:
                upsets.append(name)
                tip += " An upset."
                ring = f'<rect class="upset" x="{x + 1}" y="{y + 1}" width="{T - 2}" height="{T - 2}" rx="2.5"/>'
        tiles.append(f'<g class="{cls}"><title>{E(tip)}</title><rect x="{x}" y="{y}" width="{T}" height="{T}" rx="3"/>{ring}'
                     f'<text x="{x + T / 2}" y="{y + T / 2 + 3.5}">{st}</text></g>')
    summary = (f"Map of the 2026 Senate races by state. Democrats won {won['dem']}, Republicans {won['rep']}"
               + (f", independents {won['ind']}" if won["ind"] else "")
               + (f". Upsets, won by the side the forecast gave under 50%: {', '.join(upsets)}." if upsets else "."))
    W, H = 11 * U + T, 7 * U + T
    legend = ('<div class="maplegend" aria-hidden="true"><span><i class="dem"></i>Democrat won</span>'
              '<span><i class="rep"></i>Republican won</span>'
              + ('<span><i class="ind"></i>Independent won</span>' if won["ind"] else "")
              + '<span><i class="none"></i>Not up</span>'
              + ('<span><i class="ring"></i>Upset: the forecast gave the winner under 50%</span>' if upsets else "")
              + '</div>')
    return (f'<figure class="senmap"><figcaption>2026 Senate races, by state</figcaption>'
            f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{E(summary)}">{"".join(tiles)}</svg>{legend}</figure>')


def landing(sc):
    F = S["featured"]
    inner = seat_lines(sc, F["scorecard"]) if F.get("scorecard") else ""
    smap = senate_map(sc, F["scorecard"]) if inner else ""
    callout = f'<p class="note">{S["callout"]["text"]}</p>\n' if S.get("callout") else ""
    return head(S["name"], S["description"], "", og(S["name"], S["description"], "og-home.png", "") + FORWARD + "\n") + \
        f"""<body class="home">
{shell.header("", "home")}
<main class="wrap">
<h1>{E(S["name"])}</h1>
<p class="lede">{E(S["intro"])}</p>
{callout}<div class="sections featured">{card(F, "sec hasmap" if smap else "sec", inner + smap)}</div>
<div class="sections">{"".join(card(c) for c in S["sections"])}</div>
</main>
""" + foot()


def preview(key):
    """A cycle's page in its "coming" state: a note, what is being built, and the dates (previews[key] in site.json)."""
    P = S["previews"][key]
    tracks = "".join(f'<div class="sec"><h3>{E(t["name"])}</h3><p>{E(t["text"])}</p><p class="target">{E(t["target"])}</p></div>'
                     for t in P["tracks"])
    dates = "".join(f'<li{" class=target" if d.get("target") else ""}><span class="when">{E(d["when"])}</span>'
                    f'<span>{E(d["text"])}</span></li>' for d in P["dates"])
    see = f'<p><a href="{E(P["see_also"]["path"])}">{E(P["see_also"]["text"])}</a></p>\n' if P.get("see_also") else ""
    img = f'<img class="preview" src="og.png" width="1200" height="630" alt="{E(P["image_alt"])}">'
    return head(f'{P["title"]} · {S["name"]}', P["description"], "../",
                og(f'{P["title"]} · {S["name"]}', P["description"], f"{key}/og.png", f"{key}/")) + f"""<body class="home">
{shell.header("../", key)}
<main class="wrap">
<h1>{E(P["title"])}</h1>
<p class="lede">{E(P["lede"])}</p>
{board(P["board"]) if P.get("board") else img}
<p class="note">{E(P["note"])}</p>
<h2>What is being built</h2>
<div class="sections tracks">{tracks}</div>
<h2>Key dates</h2>
<ul class="dates">{dates}</ul>
<p class="tiny">{"Targets are this site's own, not fixed dates. " if any(d.get("target") for d in P["dates"]) else ""}Dates are added as they become known.</p>
{see}</main>
""" + foot()


def election_stub(e):
    """A past election's address opens on one of its pages (2026: the scorecard) until it has a page of its own."""
    to = e["opens"]
    extra = (f'<meta http-equiv="refresh" content="0; url={E(to)}">\n'
             f'<script>location.replace({json.dumps(to)});</script>\n')
    return head(e["label"], f'{e["label"]} elections', "../", extra) + f"""<body>
{shell.header("../", e["key"])}
<main class="wrap"><p>Continue to <a href="{E(to)}">the {E(e["label"])} pages</a>.</p></main>
{shell.script()}
</body>
</html>
"""


def not_found():
    return head("Not found", "Page not found", "/") + f"""<body>
{shell.header("/")}
<main class="wrap"><p>Not found. <a href="/">Back to the home page</a></p></main>
""" + foot()


def main(scorecard=None, cards=True):
    """cards=False (the daily build) leaves the preview cards as committed: they depend on site.json (and the 2028
    card on the board's data files, which the daily job does not change), and a
    machine with another font renderer (the scorecard job runs on Linux) would redraw them with different pixels."""
    if scorecard is None and SCORECARD.exists():
        scorecard = json.loads(SCORECARD.read_text())
    out = {SITE / "index.html": landing(scorecard), SITE / "404.html": not_found(), SITE / "_redirects": REDIRECTS}
    for key in S["previews"]:
        out[SITE / key / "index.html"] = preview(key)
    for e in S["elections"]:
        if e.get("opens"):
            out[SITE / e["path"] / "index.html"] = election_stub(e)
    for path, text in out.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    try:
        if not cards:
            raise RuntimeError("left as committed (run landing.py or build.py --all to redraw)")
        import og_image
        og_image.make_home(S, SITE / "og-home.png")
        out[SITE / "og-home.png"] = None
        for key in S["previews"]:
            og_image.make_preview(S, key, SITE / key / "og.png",
                                  board_data() if S["previews"][key].get("board") else None)
            out[SITE / key / "og.png"] = None
    except Exception as ex:  # noqa: BLE001  (no Pillow: the pages still build, without new cards)
        print("preview cards skipped:", ex)
    print("built", ", ".join(str(p.relative_to(SITE)).replace("\\", "/") for p in out))


if __name__ == "__main__":
    main()
