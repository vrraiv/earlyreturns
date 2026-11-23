"""Build the pages around the elections: the landing page, each past election's opening page, 404.html and _redirects.

    python src/site/landing.py        (src/site/build.py runs this too)

Everything here comes from src/site/site.json and carries no date, so a rebuild writes the same bytes.

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
S = shell.SETTINGS

# The forecast page's tab names (PAGES in template.html) and its two race prefixes. No element on the landing page
# may take one of these as its id, or a link to it would be forwarded.
OLD_TABS = ["overview", "scorecard", "senate", "house", "method", "bias", "backtest", "appendix", "data"]
FORWARD = ("<script>(function(){function f(){var h=location.hash.slice(1),t=" + json.dumps(OLD_TABS, separators=(",", ":")) +
           ";if(t.indexOf(h)>=0||h.indexOf('senate/')===0||h.indexOf('house/')===0)"
           "location.replace('2026/forecast/'+location.hash);}f();addEventListener('hashchange',f);})();</script>")
REDIRECTS = "/data/* /2026/data/:splat 301\n"


def head(title, desc, prefix, extra=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="theme-color" content="#1d1e22">
<link rel="icon" type="image/svg+xml" href="{prefix}favicon.svg">
<link rel="stylesheet" href="{prefix}assets/history.css">
<style>
{shell.css()}
</style>
{extra}</head>
"""


def card(c, cls="sec"):
    label = f'<div class="tiny">{html.escape(c["label"])}</div>' if c.get("label") else ""
    return (f'<a class="{cls}" href="{html.escape(c["path"])}">{label}<h3>{html.escape(c["title"])}</h3>'
            f'<p>{html.escape(c["text"])}</p></a>')


def landing():
    og = (f'<meta property="og:title" content="{html.escape(S["name"])}">\n'
          f'<meta property="og:description" content="{html.escape(S["description"])}">\n'
          f'<meta property="og:image" content="{S["base_url"]}/og.png">\n'
          '<meta name="twitter:card" content="summary_large_image">\n' + FORWARD + "\n")
    callout = f'<p class="note">{S["callout"]["text"]}</p>\n' if S.get("callout") else ""
    return head(S["name"], S["description"], "", og) + f"""<body>
{shell.header("", "home")}
<main class="wrap">
<h1>{html.escape(S["name"])}</h1>
<p class="lede">{html.escape(S["intro"])}</p>
{callout}<div class="sections">{card(S["featured"])}</div>
<div class="sections">{"".join(card(c) for c in S["sections"])}</div>
</main>
<footer><div class="wrap">
{shell.footer()}
</div></footer>
</body>
</html>
"""


def election_stub(e):
    """A past election's address opens on one of its pages (2026: the scorecard) until it has a page of its own."""
    to = e["opens"]
    extra = (f'<meta http-equiv="refresh" content="0; url={html.escape(to)}">\n'
             f'<script>location.replace({json.dumps(to)});</script>\n')
    return head(e["label"], f'{e["label"]} elections', "../", extra) + f"""<body>
{shell.header("../", e["key"])}
<main class="wrap"><p>Continue to <a href="{html.escape(to)}">the {html.escape(e["label"])} pages</a>.</p></main>
</body>
</html>
"""


def not_found():
    return head("Not found", "Page not found", "/") + f"""<body>
{shell.header("/")}
<main class="wrap"><p>Not found. <a href="/">Back to the home page</a></p></main>
<footer><div class="wrap">
{shell.footer()}
</div></footer>
</body>
</html>
"""


def main():
    out = {SITE / "index.html": landing(), SITE / "404.html": not_found(), SITE / "_redirects": REDIRECTS}
    for e in S["elections"]:
        if e.get("opens"):
            out[SITE / e["path"] / "index.html"] = election_stub(e)
    for path, text in out.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print("built", ", ".join(str(p.relative_to(SITE)).replace("\\", "/") for p in out))


if __name__ == "__main__":
    main()
