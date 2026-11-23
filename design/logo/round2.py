"""Logo round 2 for Early Returns (SI-9): concept C, one colour.
Changes from round 1: a shorter box; bits of different sizes arriving from the upper left and settling into the
columns; everything one colour, with the slot and the ballot's tick cut out (a mask), so the mark is transparent
and takes `color` from the page. Writes mark.svg, favicon.svg and preview-r2.html."""
from itertools import count
from pathlib import Path

ids = count()

def sq(x, y, s, r=None):
    return f'<rect x="{x - s/2:.2f}" y="{y - s/2:.2f}" width="{s:.2f}" height="{s:.2f}" rx="{r if r is not None else s*0.16:.2f}"/>'

def column(x, base, n, w=4, gap=1):
    return "".join(sq(x + w/2, base - w/2 - i*(w + gap), w) for i in range(n))

BOX = '<path d="M3 20.5 H29 V26.5 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 Z"/>'
SLOT = '<rect x="7" y="22.2" width="18" height="1.5" rx="0.75"/>'
COLS = column(9, 19.7, 1) + column(14, 19.7, 2) + column(19, 19.7, 3)
BALLOT = '<rect x="24" y="7.2" width="5" height="12.5" rx="0.7" transform="rotate(7 26.5 13.5)"/>'
TICK = '<path d="M25.1 11.6 l1.1 1.2 l2 -2.5" fill="none" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" transform="rotate(7 26.5 13.5)"/>'
# arriving bits: largest nearest the first column's next place, smaller and sparser further away
STREAM_FULL = sq(10.6, 12.2, 2.9) + sq(7.0, 10.4, 2.3) + sq(9.6, 7.2, 1.8) + sq(4.4, 6.9, 1.6) + sq(6.9, 4.0, 1.25) + sq(3.0, 3.2, 1.0)
STREAM_FAV = sq(10.6, 12.2, 2.9) + sq(6.6, 8.6, 2.2) + sq(3.6, 4.8, 1.6)

def mark(stream=STREAM_FULL, tick=True, size=None, cls="mark"):
    i = next(ids)
    wh = f' width="{size}" height="{size}"' if size else ""
    return (f'<svg class="{cls}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"{wh} aria-hidden="true">'
            f'<mask id="er{i}"><g fill="#fff">{BOX}{COLS}{BALLOT}{stream}</g>'
            f'<g fill="#000" stroke="#000">{SLOT}</g>{"<g stroke=" + chr(34) + "#000" + chr(34) + ">" + TICK + "</g>" if tick else ""}</mask>'
            f'<rect width="32" height="32" fill="currentColor" mask="url(#er{i})"/></svg>')

Path("mark.svg").write_text(mark().replace('<svg class="mark" ', '<svg style="color:#0A1D37" ') + "\n")
Path("favicon.svg").write_text(
    mark(STREAM_FAV, tick=False).replace('<svg class="mark" ', '<svg ')
    .replace('<rect width="32" height="32" fill="currentColor"', '<style>rect.ink{fill:#0A1D37}@media (prefers-color-scheme: dark){rect.ink{fill:#E9ECF0}}</style><rect class="ink" width="32" height="32"') + "\n")

def header(colour, label):
    return (f'<div class="sitebar"><a class="sitename"><span style="color:{colour};line-height:0">{mark(size=24)}</span>'
            f'<span>Early Returns</span></a><nav><a>Home</a><a>Election data</a><a>2026</a></nav></div>'
            f'<p class="lab">{label}</p>')

def smalls(colour):
    return (f'<div class="smallrow" style="color:{colour}"><div class="tab">{mark(STREAM_FAV, False, 16)}<span>Early Returns</span></div>'
            f'<div class="tab">{mark(STREAM_FAV, False, 32)}<span>favicon, 32 px</span></div>'
            f'{mark(size=24)}{mark(size=48)}</div>')

LIGHT = "#0A1D37"
DARKS = [("#E9ECF0", "Dark 1 · off-white (the body text colour)"), ("#C9CFD8", "Dark 2 · light grey (the trend-line ink)"),
         ("#A9C8EC", "Dark 3 · pale blue (the site name's colour; round 1 used this for the box)")]

Path("preview-r2.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Early Returns logo, round 2</title>
<style>
@font-face{{font-family:"IBM Plex Sans";font-weight:400;src:url(../../site/assets/fonts/IBMPlexSans-Regular.woff2)}}
@font-face{{font-family:"IBM Plex Sans";font-weight:600;src:url(../../site/assets/fonts/IBMPlexSans-SemiBold.woff2)}}
body{{margin:0;font-family:"IBM Plex Sans",sans-serif;display:flex}}
.mode{{flex:1;padding:20px 24px;background:var(--bg);color:var(--text-2)}}
.light{{--bg:#FAF8F4;--surface:#fff;--border:#CFDDEE;--title:#0A1D37;--text-2:#505B6A;--tab:#E6EDF6}}
.dark{{--bg:#131519;--surface:#1B1E24;--border:#263B57;--title:#A9C8EC;--text-2:#B3BBC7;--tab:#2B3649}}
h1{{color:var(--title);font-size:1.1rem;margin:0 0 12px}}
.sitebar{{display:flex;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-size:.95rem}}
.sitename{{display:flex;align-items:center;gap:8px;color:var(--title);font-weight:600;margin-right:auto}}
nav{{display:flex;gap:14px}} .lab{{margin:4px 0 10px;font-size:.8rem}}
.big{{display:flex;gap:16px;margin:4px 0 16px}} .big>div{{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:10px;line-height:0}}
.smallrow{{display:flex;gap:14px;align-items:center;margin:0 0 18px}}
.tab{{display:flex;align-items:center;gap:6px;background:var(--tab);color:var(--text-2);border-radius:6px 6px 0 0;padding:5px 10px;font-size:.78rem}}
.tab svg{{color:inherit}}
</style><body>
<div class="mode light"><h1>Light mode</h1>{header(LIGHT, "Ink: navy, the site name's colour")}
<div class="big" style="color:{LIGHT}"><div>{mark(size=160)}</div><div>{mark(STREAM_FAV, False, 160)}</div></div>
<p class="lab">Left: the full mark (header, link previews). Right: the favicon cut, fewer bits and no tick, for 16–32 px.</p>
{smalls(LIGHT)}</div>
<div class="mode dark"><h1>Dark mode: three quieter options</h1>
{"".join(header(c, l) + smalls(c) for c, l in DARKS)}
<div class="big">{"".join(f'<div style="color:{c}">{mark(size=96)}</div>' for c, _ in DARKS)}</div></div>
</body>""")
