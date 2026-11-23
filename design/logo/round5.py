"""Logo round 5 for Early Returns (SI-9): a new direction from the name, time ("early") with voting.
E1 a clock whose hands, at 10:10, make a check mark; E2 a calendar with the first day checked;
E3 a ballot box with a ballot going in and the check-mark clock on its front.
One colour: #1B4978 light, #C9CFD8 dark. Writes concept-E*.svg and preview-r5.html."""
import math
from itertools import count
from pathlib import Path

ids = count()

def hand(cx, cy, deg, length, w):
    a = math.radians(deg)
    return (f'<line x1="{cx}" y1="{cy}" x2="{cx + length*math.sin(a):.2f}" y2="{cy - length*math.cos(a):.2f}" '
            f'stroke-width="{w}" stroke-linecap="round"/>')

def clock_hands(cx, cy, r, colour):
    # hour hand toward ~9:45 (short), minute hand toward ~2 (long): a check mark with its vertex at the centre
    return (f'<g stroke="{colour}">{hand(cx, cy, 290, r*0.5, r*0.2)}{hand(cx, cy, 52, r*0.84, r*0.2)}</g>')

def ticks(cx, cy, r, w, colour):
    out = ""
    for deg in (0, 90, 180, 270):
        a = math.radians(deg)
        out += (f'<line x1="{cx + (r-0.4)*math.sin(a):.2f}" y1="{cy - (r-0.4)*math.cos(a):.2f}" '
                f'x2="{cx + (r-2.6)*math.sin(a):.2f}" y2="{cy - (r-2.6)*math.cos(a):.2f}" stroke="{colour}" stroke-width="{w}" stroke-linecap="round"/>')
    return out

E1 = (f'<circle cx="16" cy="16" r="13.2" fill="none" stroke="#fff" stroke-width="2.6"/>'
      + ticks(16, 16, 11.4, 1.6, "#fff") + clock_hands(16, 17, 12.5, "#fff") + '<circle cx="16" cy="17" r="1.9" fill="#fff"/>')

def check(x, y, s, colour, w):
    return (f'<path d="M{x} {y + s*0.5} l{s*0.35} {s*0.38} l{s*0.65} {-s*0.8}" fill="none" stroke="{colour}" '
            f'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>')

cells = ""
for r in range(2):
    for c in range(3):
        if (r, c) == (0, 0):
            continue
        cells += f'<rect x="{8.2 + c*6.2}" y="{15.6 + r*5.8}" width="3.6" height="3.4" rx="0.6" fill="#fff"/>'
E2 = ('<rect x="3.5" y="6" width="25" height="23" rx="2.6" fill="none" stroke="#fff" stroke-width="2.2"/>'
      '<rect x="3.5" y="6" width="25" height="6.2" rx="2.4" fill="#fff"/><rect x="3.5" y="9" width="25" height="3.2" fill="#fff"/>'
      '<rect x="9" y="2.5" width="2.6" height="6.5" rx="1.3" fill="#fff" stroke="#000" stroke-width="1.4"/>'
      '<rect x="20.4" y="2.5" width="2.6" height="6.5" rx="1.3" fill="#fff" stroke="#000" stroke-width="1.4"/>'
      + cells + check(7.0, 14.8, 6.2, "#fff", 1.9))

E3 = ('<path d="M5 15.5 H27 V27.5 a2 2 0 0 1 -2 2 H7 a2 2 0 0 1 -2 -2 Z" fill="#fff"/>'
      '<rect x="9.5" y="17" width="13" height="1.5" rx="0.75" fill="#000"/>'
      '<rect x="12.6" y="2.5" width="6.8" height="15.3" rx="0.9" fill="#fff"/>'
      '<line x1="14.6" y1="6.5" x2="17.4" y2="6.5" stroke="#000" stroke-width="1.1" stroke-linecap="round"/>'
      '<line x1="14.6" y1="9.2" x2="17.4" y2="9.2" stroke="#000" stroke-width="1.1" stroke-linecap="round"/>'
      '<circle cx="16" cy="23.6" r="4.3" fill="#000"/>' + clock_hands(16, 24.2, 4.4, "#fff"))

V = {
  "E1": ("Check o'clock", "A clock at about ten past ten: the two hands make a check mark. Early, and a vote cast.", E1),
  "E2": ("First day checked", "A calendar whose first day is checked off: the earliest date, marked as a vote.", E2),
  "E3": ("Box and clock", "V1's ballot box with a ballot going in; its front carries the check-mark clock.", E3),
}

def mark(body, size=None):
    i = next(ids)
    wh = f' width="{size}" height="{size}"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"{wh} aria-hidden="true">'
            f'<mask id="er{i}"><rect width="32" height="32" fill="#000"/>{body}</mask>'
            f'<rect class="ink" width="32" height="32" fill="currentColor" mask="url(#er{i})"/></svg>')

STYLE = '<style>.ink{fill:#1B4978}@media (prefers-color-scheme: dark){.ink{fill:#C9CFD8}}</style>'
for k, (_, _, body) in V.items():
    Path(f"concept-{k}.svg").write_text(mark(body).replace('fill="currentColor" ', '').replace('aria-hidden="true">', 'aria-hidden="true">' + STYLE, 1) + "\n")

LIGHT, DARK = "#1B4978", "#C9CFD8"
def block(k, colour):
    title, desc, body = V[k]
    return (f'<h2>{k} · {title}</h2><p class="lab">{desc}</p>'
            f'<div class="sitebar"><a class="sitename"><span style="color:{colour};line-height:0">{mark(body, 24)}</span>'
            f'<span>Early Returns</span></a><nav><a>Home</a><a>Election data</a><a>2026</a></nav></div>'
            f'<div class="smallrow"><div class="tab"><span style="color:{colour};line-height:0">{mark(body, 16)}</span><span>Early Returns</span></div>'
            f'<div class="tab"><span style="color:{colour};line-height:0">{mark(body, 32)}</span><span>32 px</span></div>'
            f'<div class="big" style="color:{colour}">{mark(body, 112)}</div></div>')

Path("preview-r5.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Early Returns logo, round 5</title>
<style>
@font-face{{font-family:"IBM Plex Sans";font-weight:400;src:url(../../site/assets/fonts/IBMPlexSans-Regular.woff2)}}
@font-face{{font-family:"IBM Plex Sans";font-weight:600;src:url(../../site/assets/fonts/IBMPlexSans-SemiBold.woff2)}}
body{{margin:0;font-family:"IBM Plex Sans",sans-serif;display:flex}}
.mode{{flex:1;padding:20px 24px;background:var(--bg);color:var(--text-2)}}
.light{{--bg:#FAF8F4;--surface:#fff;--border:#CFDDEE;--title:#0A1D37;--text-2:#505B6A;--tab:#E6EDF6}}
.dark{{--bg:#131519;--surface:#1B1E24;--border:#263B57;--title:#A9C8EC;--text-2:#B3BBC7;--tab:#2B3649}}
h1{{color:var(--title);font-size:1.1rem;margin:0 0 4px}} h2{{color:var(--title);font-size:1rem;margin:16px 0 0}}
.sitebar{{display:flex;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-size:.95rem}}
.sitename{{display:flex;align-items:center;gap:8px;color:var(--title);font-weight:600;margin-right:auto}}
nav{{display:flex;gap:14px}} .lab{{margin:2px 0 8px;font-size:.8rem}}
.smallrow{{display:flex;gap:14px;align-items:center;margin:10px 0 4px}}
.tab{{display:flex;align-items:center;gap:6px;background:var(--tab);color:var(--text-2);border-radius:6px 6px 0 0;padding:5px 10px;font-size:.78rem}}
.big{{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px;line-height:0;margin-left:auto}}
</style><body>
<div class="mode light"><h1>Light mode</h1>{"".join(block(k, LIGHT) for k in V)}</div>
<div class="mode dark"><h1>Dark mode</h1>{"".join(block(k, DARK) for k in V)}</div>
</body>""")
