"""What every page shares: the head (stylesheet, icons, the site name for link previews, light or dark mode), the top row (the Early Returns mark
and name, src/site/brand/, then the links and the mode switch), and the footer line. The settings come from src/site/site.json.

site.json holds the site's name and address, the top row (an entry with "live": false stays hidden until its page
exists), the list of elections (each one a folder under its year), the landing page's featured item, callout and
section cards, and the footer line. The forecast template, the election data pages and the landing page all call
head(), header(), footer() and script() here, so a change to any of them is made once. The styles are one file,
site/assets/site.css.

Links are relative: `prefix` is the way from the page back to the site's root ("" at /, "../" at /history/,
"../../" at /2026/forecast/). Pages served at any depth (404.html) pass "/".

Light and dark. Light is the default. MODE below runs in the head, before anything is drawn: it sets
<html data-theme> from the reader's saved choice or, without one, from the device's setting. SWITCH runs at the end of
the page: the button in the top row flips the mode, saves the choice, and fires a "themechange" event on window, which
the page scripts that draw charts listen for (they read their colours from the stylesheet's variables).

The intro. Once per visit (a sessionStorage flag, "intro"), the first page a reader opens plays one short animation:
the landing page plays its terminal (landing.py), any other page types the site name in the top row (TYPE below).
MODE marks the page for it (<html data-intro>) before anything is drawn, so the stylesheet can hold the name back
until the typing starts; readers who ask for reduced motion, and browsers without sessionStorage, never get the mark
and see the still page. The return-key mark beside the name (RETURN) is on every page, still.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).with_name("brand")))
import brand  # noqa: E402  (the Early Returns mark, SI-9)

SETTINGS = json.loads(Path(__file__).with_name("site.json").read_text(encoding="utf-8"))

THEME_COLOR = {"light": "#FAF8F4", "dark": "#131519"}   # --bg in site.css, for the browser's own bars
MODE = ('<script>(function(){var t;try{t=localStorage.getItem("theme")}catch(e){}'
        'if(t!=="light"&&t!=="dark")t=window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";'
        'document.documentElement.setAttribute("data-theme",t);'
        'try{if(!sessionStorage.getItem("intro")&&!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches))'
        'document.documentElement.setAttribute("data-intro","")}catch(e){}})();</script>')
SWITCH = ('<script>(function(){var r=document.documentElement,q=window.matchMedia&&matchMedia("(prefers-color-scheme: dark)");'
          'function set(t){r.setAttribute("data-theme",t);window.dispatchEvent(new Event("themechange"))}'
          'var b=document.getElementById("modeswitch");'
          'if(b)b.addEventListener("click",function(){var t=r.getAttribute("data-theme")==="dark"?"light":"dark";'
          'try{localStorage.setItem("theme",t)}catch(e){}set(t)});'
          'if(q&&q.addEventListener)q.addEventListener("change",function(e){var s;try{s=localStorage.getItem("theme")}catch(x){}'
          'if(s!=="light"&&s!=="dark")set(e.matches?"dark":"light")})})();</script>')

RETURN = ('<svg class="ret" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M13 3v5a2 2 0 0 1-2 2H4M7 7l-3 3 3 3" '
          'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')
# Types the site name, then shows the return mark. Skipped where the landing page's terminal plays (#term) and on a
# page that only forwards (a past election's stub), so the visit's one intro is not spent there.
TYPE = ('<script>(function(){var r=document.documentElement;if(!r.hasAttribute("data-intro")||document.getElementById("term")'
        '||document.querySelector("meta[http-equiv=refresh]"))return;'
        'var n=document.querySelector(".sitename .nm");if(!n){r.removeAttribute("data-intro");return}'
        'try{sessionStorage.setItem("intro","1")}catch(e){}'
        'var s=n.textContent,i=0;n.innerHTML="<span class=typed></span><i class=cur></i><span class=ghost></span>";'
        'var t=n.firstChild,g=n.lastChild;g.textContent=s;r.setAttribute("data-typing","");r.removeAttribute("data-intro");'
        'function step(){i++;t.textContent=s.slice(0,i);g.textContent=s.slice(i);'
        'if(i<s.length)setTimeout(step,55+Math.random()*55);'
        'else setTimeout(function(){n.textContent=s;r.removeAttribute("data-typing");'
        'var k=n.parentNode.querySelector(".ret");if(k)k.classList.add("pop")},260)}'
        'setTimeout(step,450)})();</script>')


def head(prefix):
    """The lines every page's <head> carries after its own title and description."""
    return (f'<meta name="theme-color" content="{THEME_COLOR["light"]}" media="(prefers-color-scheme: light)">\n'
            f'<meta name="theme-color" content="{THEME_COLOR["dark"]}" media="(prefers-color-scheme: dark)">\n'
            f'<link rel="icon" href="{prefix}favicon.ico" sizes="32x32">\n'
            f'<link rel="icon" type="image/svg+xml" href="{prefix}favicon.svg">\n'
            f'<link rel="apple-touch-icon" href="{prefix}apple-touch-icon.png">\n'
            f'<meta property="og:site_name" content="{html.escape(SETTINGS["name"])}">\n'
            f'<link rel="stylesheet" href="{prefix}assets/site.css">\n'
            f'{MODE}')


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
    row += ('<button type="button" class="modeswitch" id="modeswitch" aria-label="Switch between light and dark mode">'
            '<span class="ml">Light</span><span class="md">Dark</span></button>')
    home = prefix or "./"
    return (f'<div class="sitebar"><div class="wrap"><a class="sitename" href="{home}" aria-label="{html.escape(SETTINGS["name"])}">{brand.mark_inline(22)}<span><span class="nm">{html.escape(SETTINGS["name"])}</span>{RETURN}</span></a>'
            f'<nav aria-label="Site">{row}</nav></div></div>')


def footer():
    """The author line, with each [Label] in the text linked to footer.links[Label]."""
    f = SETTINGS["footer"]
    text = re.sub(r"\[([^\]]+)\]", lambda m: f'<a href="{html.escape(f["links"][m.group(1)])}">{m.group(1)}</a>',
                  html.escape(f["text"]))
    return f'<p class="sitefoot">{text}</p>'


def script():
    """The mode switch's script and the site name's typing; goes at the end of <body>, before a page's own scripts."""
    return SWITCH + TYPE
