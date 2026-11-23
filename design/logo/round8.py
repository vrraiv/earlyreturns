"""Logo round 8 for Early Returns (SI-9): fixes for R1a's inner line, a smaller check, a staggered start.
F1 outer track only; F2 the infield line dashed; F3 one thicker track with an opening where the check exits;
F4 a smaller check on the outer track; F5 two lanes (dashed divider) with a staggered start; F6 F4 and F5 together.
One colour: #1B4978 light, #C9CFD8 dark. Writes concept-F*.svg and preview-r8.html."""
from itertools import count
from pathlib import Path

ids = count()
A = 'fill="none" stroke-linecap="round" stroke-linejoin="round"'

def outer(w=2.2):
    return f'<rect x="2" y="7" width="28" height="19" rx="9.5" fill="none" stroke="#fff" stroke-width="{w}"/>'

INNER_DASHED = ('<rect x="8" y="13" width="16" height="7" rx="3.5" fill="none" stroke="#fff" stroke-width="1.8" '
                'stroke-dasharray="2.4 1.9" stroke-linecap="round"/>')
DIVIDER = ('<rect x="5" y="10" width="22" height="13" rx="6.5" fill="none" stroke="#fff" stroke-width="1.4" '
           'stroke-dasharray="1.8 1.7" stroke-linecap="round"/>')
INNER_SOLID = '<rect x="8" y="13" width="16" height="7" rx="3.5" fill="none" stroke="#fff" stroke-width="1.8"/>'
STAGGER = ('<line x1="17.5" y1="20.9" x2="17.5" y2="22.1" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>'
           '<line x1="21.5" y1="23.9" x2="21.5" y2="25.1" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>')

BIG = "M8 18.2 L13.2 22.5 L29.6 4"
SMALL = "M10.4 17.6 L14 21 L26.8 5"

def check(d, w=2.8, gap=0.9):
    return (f'<path d="{d}" {A} stroke="#000" stroke-width="{w + 2*gap}"/>'
            f'<path d="{d}" {A} stroke="#fff" stroke-width="{w}"/>')

V = {
  "F1": ("Outer track only", "The inner line dropped: one track and the check leaving it.", outer() + check(BIG)),
  "F2": ("Dashed infield", "The inner line dashed, so it reads as a lane marking rather than a second loop.", outer() + INNER_DASHED + check(BIG)),
  "F3": ("Opening in the loop", "One thicker track; the check exits through a clear opening instead of crossing a line.", outer(3.2) + check(BIG, 2.8, 1.7)),
  "F4": ("Smaller check", "F1 with a smaller check: more track, and the exit is a shorter step out of the loop.", outer() + check(SMALL, 2.6)),
  "F5": ("Staggered start", "Two lanes split by a dashed line, with a staggered start on the bottom straight.", outer() + DIVIDER + INNER_SOLID + STAGGER + check(BIG)),
  "F6": ("Smaller check, staggered start", "F4's smaller check on F5's two lanes and staggered start.", outer() + DIVIDER + INNER_SOLID + STAGGER + check(SMALL, 2.6)),
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
            f'<span>Early Returns</span></a><nav><a>Home</a><a>Election data</a></nav></div>'
            f'<div class="smallrow"><div class="tab"><span style="color:{colour};line-height:0">{mark(body, 16)}</span><span>Early Returns</span></div>'
            f'<div class="tab"><span style="color:{colour};line-height:0">{mark(body, 32)}</span><span>32 px</span></div>'
            f'<div class="big" style="color:{colour}">{mark(body, 96)}</div></div>')

css = Path("preview-r5.html").read_text().split("<style>")[1].split("</style>")[0]
Path("preview-r8.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Early Returns logo, round 8</title>
<style>{css}</style><body>
<div class="mode light"><h1>Light mode</h1>{"".join(block(k, LIGHT) for k in V)}</div>
<div class="mode dark"><h1>Dark mode</h1>{"".join(block(k, DARK) for k in V)}</div>
</body>""")
