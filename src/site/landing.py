"""Build the pages around the elections: the landing page, the coming cycles' pages (/2027/, /2028/), each past election's
opening page, 404.html and _redirects, and the link-preview cards (site/og-home.png, site/<year>/og.png).

    python src/site/landing.py        (src/site/build.py runs this too)

Everything here comes from src/site/site.json and, for the landing page's figures, data/scorecard/scorecard.json. No
page carries a build date, so a rebuild with the same scorecard writes the same bytes; the daily scorecard job changes
the landing page only when the seat counts change. build.py passes the scorecard it read for the forecast page, so the
two pages show the same numbers; run alone, this reads the same file.

Each coming cycle's page (previews in site.json: 2027, the governor races; 2028) is the "coming" state SI-1 set out: a
note, what is being built and the dates. Their tracks and dates are copied from planning/plan.js (the tracks' goals,
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


def landing(sc):
    F = S["featured"]
    inner = seat_lines(sc, F["scorecard"]) if F.get("scorecard") else ""
    callout = f'<p class="note">{S["callout"]["text"]}</p>\n' if S.get("callout") else ""
    return head(S["name"], S["description"], "", og(S["name"], S["description"], "og-home.png", "") + FORWARD + "\n") + \
        f"""<body class="home">
{shell.header("", "home")}
<main class="wrap">
<h1>{E(S["name"])}</h1>
<p class="lede">{E(S["intro"])}</p>
{callout}<div class="sections featured">{card(F, inner=inner)}</div>
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
    return head(f'{P["title"]} · {S["name"]}', P["description"], "../",
                og(f'{P["title"]} · {S["name"]}', P["description"], f"{key}/og.png", f"{key}/")) + f"""<body class="home">
{shell.header("../", key)}
<main class="wrap">
<h1>{E(P["title"])}</h1>
<p class="lede">{E(P["lede"])}</p>
<img class="preview" src="og.png" width="1200" height="630" alt="{E(P["image_alt"])}">
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


def main(scorecard=None):
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
        import og_image
        og_image.make_home(S, SITE / "og-home.png")
        out[SITE / "og-home.png"] = None
        for key in S["previews"]:
            og_image.make_preview(S, key, SITE / key / "og.png")
            out[SITE / key / "og.png"] = None
    except Exception as ex:  # noqa: BLE001  (no Pillow: the pages still build, without new cards)
        print("preview cards skipped:", ex)
    print("built", ", ".join(str(p.relative_to(SITE)).replace("\\", "/") for p in out))


if __name__ == "__main__":
    main()
