"""Logo round 7 for Early Returns (SI-9): developing R1 (a check mark leaving a race track's loop early).
A wider track with two equal lane lines, and a tighter cut where the check crosses them.
R1a a straight check; R1b with a chequered finish line on the bottom straight (the check leaves before it);
R1c the check's short arm runs the track's bend into the straight, then turns up and out; R1d R1c with the finish.
One colour: #1B4978 light, #C9CFD8 dark. Writes concept-R1*.svg and preview-r7.html."""
from itertools import count
from pathlib import Path

ids = count()
LINE, STROKE, GAP = 2.0, 2.7, 0.9

TRACK = (f'<rect x="2" y="7" width="28" height="19" rx="9.5" fill="none" stroke="#fff" stroke-width="{LINE}"/>'
         f'<rect x="9" y="14" width="14" height="5" rx="2.5" fill="none" stroke="#fff" stroke-width="{LINE}"/>')
FINISH = "".join(f'<rect x="{18.4 + c*1.7:.1f}" y="{20.2 + r*1.7:.1f}" width="1.7" height="1.7" fill="#fff"/>'
                 for r in range(3) for c in range(2) if (r + c) % 2 == 0)
STRAIGHT = "M8 18.2 L13.2 22.5 L29.6 4"
CURVED = "M5.5 16 A6 6 0 0 0 11.5 22.5 L14.2 22.5 L29.6 4"

def check(d):
    a = 'fill="none" stroke-linecap="round" stroke-linejoin="round"'
    return (f'<path d="{d}" {a} stroke="#000" stroke-width="{STROKE + 2*GAP}"/>'
            f'<path d="{d}" {a} stroke="#fff" stroke-width="{STROKE}"/>')

V = {
  "R1a": ("Straight check", "Round 6's R1 on a wider track with two equal lanes and a tighter cut at each crossing.", TRACK + check(STRAIGHT)),
  "R1b": ("Straight check, finish line", "R1a with a chequered finish on the bottom straight; the check leaves the loop before it.", TRACK + FINISH + check(STRAIGHT)),
  "R1c": ("Runs the bend", "The check's short arm runs the track's bend into the straight, then turns up and out of the loop.", TRACK + check(CURVED)),
  "R1d": ("Runs the bend, finish line", "R1c with the chequered finish it never reaches.", TRACK + FINISH + check(CURVED)),
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
            f'<div class="big" style="color:{colour}">{mark(body, 104)}</div></div>')

css = Path("preview-r5.html").read_text().split("<style>")[1].split("</style>")[0]
Path("preview-r7.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Early Returns logo, round 7</title>
<style>{css}</style><body>
<div class="mode light"><h1>Light mode</h1>{"".join(block(k, LIGHT) for k in V)}</div>
<div class="mode dark"><h1>Dark mode</h1>{"".join(block(k, DARK) for k in V)}</div>
</body>""")
