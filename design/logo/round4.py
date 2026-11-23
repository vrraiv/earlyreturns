"""Logo round 4 for Early Returns (SI-9): remedies for the boat reading of round 3.
V1 a deeper, narrower box; V2 round 3's box with the ballot going into the slot; V3 both.
Light mode #1B4978 (chosen in round 3), dark mode #C9CFD8. Writes concept-V*.svg and preview-r4.html."""
import math
from itertools import count
from pathlib import Path

ids = count()
ANGLE, BW = 17, 3.2

def column(x, base, n, w=4, gap=1):
    return "".join(f'<rect x="{x}" y="{base - (i + 1)*w - i*gap:.2f}" width="{w}" height="{w}" rx="0.64"/>' for i in range(n))

def box(x0, x1, top, bot, r=2):
    return f'<path d="M{x0} {top} H{x1} V{bot - r} a{r} {r} 0 0 1 -{r} {r} H{x0 + r} a{r} {r} 0 0 1 -{r} -{r} Z"/>'

def design(x0, x1, top, bot, slot_y, slot_x0, slot_x1, cols_x, bx, by, length, into):
    """bx, by: the ballot's bottom centre. into: the ballot ends inside the slot, cut free of the lid."""
    slot = f'<rect x="{slot_x0}" y="{slot_y}" width="{slot_x1 - slot_x0}" height="1.5" rx="0.75"/>'
    ballot = (f'<rect x="{bx - BW/2:.2f}" y="{by - length:.2f}" width="{BW}" height="{length:.2f}" rx="0.8" '
              f'transform="rotate({ANGLE} {bx} {by})"/>')
    halo = ballot.replace('<rect ', '<rect stroke="#000" stroke-width="2.2" ') if into else ""
    cols = "".join(column(x, top - 0.8, n) for x, n in zip(cols_x, (1, 2, 3)))
    return f'<g fill="#fff">{box(x0, x1, top, bot)}{cols}</g><g fill="#000">{slot}{halo}</g><g fill="#fff">{ballot}</g>'

V = {
  "V1": ("Deeper, narrower box", "The box is 10 units deep instead of 8 and 22 wide instead of 26; the ballot stands on the lid.",
         design(5, 27, 19, 29.5, 21.6, 8.5, 23.5, (6.5, 11.5, 16.5), 23.6, 19, 17, False)),
  "V2": ("Into the slot", "Round 3's box; the ballot's foot goes down into the slot, cut free of the lid around it.",
         design(3, 29, 20.5, 28.5, 22.2, 7, 25, (6.5, 11.5, 16.5), 23.2, 23.7, 21, True)),
  "V3": ("Both", "The deeper, narrower box, and the ballot going into the slot.",
         design(5, 27, 19, 29.5, 21.4, 8.5, 23.5, (6, 11, 16), 22.6, 22.9, 20.5, True)),
}

def mark(body, size=None):
    i = next(ids)
    wh = f' width="{size}" height="{size}"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"{wh} aria-hidden="true">'
            f'<mask id="er{i}">{body}</mask><rect class="ink" width="32" height="32" fill="currentColor" mask="url(#er{i})"/></svg>')

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

Path("preview-r4.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Early Returns logo, round 4</title>
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
