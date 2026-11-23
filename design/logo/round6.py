"""Logo round 6 for Early Returns (SI-9): ballot and race track; the pun is an early return out of a loop (a race
condition), and an election as a race.
R1 an oval track whose lane a check mark leaves early; R2 a ballot whose rows are race lanes, the leader checked at
the finish; R3 a track with a ballot in its infield and a chequered finish line.
One colour: #1B4978 light, #C9CFD8 dark. Writes concept-R*.svg and preview-r6.html."""
from itertools import count
from pathlib import Path

ids = count()

CHECK1 = "M8.6 17.4 L13 21.8 L28.8 3.4"
R1 = ('<rect x="3" y="8" width="26" height="16.5" rx="8.25" fill="none" stroke="#fff" stroke-width="2.3"/>'
      '<rect x="7.6" y="12.6" width="16.8" height="7.3" rx="3.65" fill="none" stroke="#fff" stroke-width="1.5"/>'
      f'<path d="{CHECK1}" fill="none" stroke="#000" stroke-width="6.4" stroke-linecap="round" stroke-linejoin="round"/>'
      f'<path d="{CHECK1}" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')

lanes = ""
for y, end in ((10.5, 15.5), (16, 21), (21.5, 12.5)):
    lanes += f'<line x1="9" y1="{y}" x2="{end}" y2="{y}" stroke="#fff" stroke-width="2" stroke-linecap="round"/>'
    lanes += f'<circle cx="{end}" cy="{y}" r="1.9" fill="#fff"/>'
finish = "".join(f'<rect x="{22.6 + (i % 2) * 1.3}" y="{6.8 + i * 1.3:.1f}" width="1.3" height="1.3" fill="#fff"/>' for i in range(14))
R2 = ('<path d="M6 3.5 H21.5 L26 8 V27 a1.8 1.8 0 0 1 -1.8 1.8 H6 a1.8 1.8 0 0 1 -1.8 -1.8 V5.3 a1.8 1.8 0 0 1 1.8 -1.8 Z" '
      'fill="none" stroke="#fff" stroke-width="2"/>' + lanes + finish +
      '<path d="M22.5 16 l1.3 1.4 l2.3 -3" fill="none" stroke="#000" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
      '<path d="M22.5 16 l1.3 1.4 l2.3 -3" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>')

cheq = "".join(f'<rect x="{15 + c*1.4}" y="{22.4 + r*1.4}" width="1.4" height="1.4" fill="#{"000" if (r + c) % 2 else "fff"}"/>'
               for r in range(3) for c in range(2))
R3 = ('<rect x="2.5" y="6.5" width="27" height="19" rx="9.5" fill="none" stroke="#fff" stroke-width="3.6"/>' + cheq +
      '<g transform="rotate(-8 16 16)"><rect x="12" y="9.6" width="8" height="12.6" rx="0.9" fill="#fff"/>'
      '<path d="M14 15.6 l1.6 1.7 l2.6 -3.4" fill="none" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></g>')

V = {
  "R1": ("Early exit", "An oval track, two lanes; a check mark runs the bottom straight and leaves the loop early, up and out.", R1),
  "R2": ("Ballot lanes", "A ballot whose candidate rows are race lanes; the leader reaches the chequered finish and is checked.", R2),
  "R3": ("Ballot in the infield", "A race track with a chequered finish line on the bottom straight, a checked ballot in its infield.", R3),
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

css = Path("preview-r5.html").read_text().split("<style>")[1].split("</style>")[0]
Path("preview-r6.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Early Returns logo, round 6</title>
<style>{css}</style><body>
<div class="mode light"><h1>Light mode</h1>{"".join(block(k, LIGHT) for k in V)}</div>
<div class="mode dark"><h1>Dark mode</h1>{"".join(block(k, DARK) for k in V)}</div>
</body>""")
