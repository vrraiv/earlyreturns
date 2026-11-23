"""The header and footer every page shares, and the settings they come from (src/site/site.json).

site.json holds the site's name and address, the top row (an entry with "live": false stays hidden until its page
exists), the list of elections (each one a folder under its year), the landing page's featured item, callout and
section cards, and the footer line. The forecast template, the election data pages and the landing page all call
css(), header() and footer() here, so a change to the top row or the footer is made once.

Links are relative: `prefix` is the way from the page back to the site's root ("" at /, "../" at /history/,
"../../" at /2026/forecast/). Pages served at any depth (404.html) pass "/".
"""
import html
import json
import re
from pathlib import Path

SETTINGS = json.loads(Path(__file__).with_name("site.json").read_text(encoding="utf-8"))

CSS = """
.sitebar { border-bottom: 1px solid var(--border); background: var(--surface); font-size: .84rem; }
.sitebar .wrap { display: flex; align-items: center; gap: 4px 16px; flex-wrap: wrap; padding-top: 7px; padding-bottom: 7px; }
.sitebar .sitename { color: var(--text); font-weight: 600; text-decoration: none; margin-right: auto; }
.sitebar nav { display: flex; gap: 2px 14px; flex-wrap: wrap; align-items: center; }
.sitebar nav a { color: var(--text-2); text-decoration: none; white-space: nowrap; }
.sitebar nav a:hover, .sitebar nav a.on { color: var(--text); }
.sitebar nav .past { color: var(--text-3); border-left: 1px solid var(--border); padding-left: 14px; }
.sitefoot { margin: 8px 0 0; max-width: none; }
"""


def css():
    """Styles for the shared header and footer; they use the colour variables each page already defines."""
    return CSS.strip()


def nav_items():
    """(key, label, path) for the top row: the live pages, then the current elections, then the past ones."""
    live = [(n["key"], n["label"], n["path"]) for n in SETTINGS["nav"] if n.get("live", True)]
    cur = [(e["key"], e["label"], e["path"]) for e in SETTINGS["elections"] if e.get("current")]
    past = [(e["key"], e["label"], e["path"]) for e in SETTINGS["elections"] if not e.get("current")]
    return live[:1] + cur + live[1:], past


def header(prefix, active=None):
    """The top row. `active` is the key of the section the page belongs to ("home", "history", "2026", ...)."""
    def link(key, label, path):
        return f'<a href="{(prefix + path) or "./"}"{" class=on" if key == active else ""}>{html.escape(label)}</a>'
    main, past = nav_items()
    row = "".join(link(*x) for x in main)
    if past:
        row += '<span class="past">Past elections</span>' + "".join(link(*x) for x in past)
    home = prefix or "./"
    return (f'<div class="sitebar"><div class="wrap"><a class="sitename" href="{home}">{html.escape(SETTINGS["name"])}</a>'
            f'<nav aria-label="Site">{row}</nav></div></div>')


def footer():
    """The author line, with each [Label] in the text linked to footer.links[Label]."""
    f = SETTINGS["footer"]
    text = re.sub(r"\[([^\]]+)\]", lambda m: f'<a href="{html.escape(f["links"][m.group(1)])}">{m.group(1)}</a>',
                  html.escape(f["text"]))
    return f'<p class="sitefoot">{text}</p>'
