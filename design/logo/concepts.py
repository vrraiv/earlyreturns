"""Logo concepts for Early Returns (SI-9). Writes one SVG per concept and preview.html.
Colours come from CSS variables so a mark follows the site's light and dark modes:
--lg-ink (outline / box), --lg-bit (chart bits), --lg-vote (the ballot), --lg-on (mark on the ballot)."""
from pathlib import Path

def bits(x, base, n, w=4, gap=1, cls="bit"):
    return "".join(f'<rect class="{cls}" x="{x}" y="{base - (i + 1) * w - i * gap}" width="{w}" height="{w}" rx="0.6"/>' for i in range(n))

def tick(cx, cy, s=1.0):
    return (f'<path class="on" d="M{cx-1.6*s} {cy} l{1.2*s} {1.2*s} l{2.2*s} {-2.6*s}" fill="none" '
            f'stroke-width="{1.1*s}" stroke-linecap="round" stroke-linejoin="round"/>')

C = {}
# A: ballot box in outline, a ballot going into the slot, a column chart of bits on its face.
C["A"] = ("Box face", "A ballot box with a ballot going in; its face is a column chart built from bits.",
  '<rect class="ink-s" x="4" y="14" width="24" height="15" rx="2" fill="none" stroke-width="2"/>'
  '<path class="ink-s" d="M2 14 H12.5 M19.5 14 H30" stroke-width="2.4" stroke-linecap="round"/>'
  '<rect class="vote" x="13" y="2.5" width="6" height="12" rx="0.8"/>' + tick(16, 7.2, 0.8) +
  bits(8.5, 26.5, 1, w=3.4, gap=0.9) + bits(14.3, 26.5, 2, w=3.4, gap=0.9) + bits(20.1, 26.5, 3, w=3.4, gap=0.9))
# B: a vote goes in at the slot, the chart is assembled on the lid.
C["B"] = ("In and up", "A vote goes in at the slot; the chart is built on the box's lid, one bit at a time.",
  '<rect class="ink" x="2" y="22" width="28" height="8" rx="1.6"/>'
  '<rect class="slot" x="4.5" y="22" width="7" height="1.6"/>'
  '<rect class="vote" x="5.5" y="11" width="5" height="12" rx="0.7" transform="rotate(-8 8 17)"/>' + tick(8, 15.5, 0.7) +
  bits(14, 21, 2) + bits(19, 21, 3) + bits(24, 21, 4) +
  '<rect class="bit ghost" x="24" y="0.5" width="4" height="4" rx="0.6"/>')
# C: solid box; the columns are cut out of it and rise through the lid; the tallest one is the ballot.
C["C"] = ("Solid box", "A solid ballot box; columns of bits rise through the slot, and the newest is the ballot.",
  '<path class="ink" d="M3 15 H29 V27.5 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 Z"/>'
  '<rect class="slot" x="6" y="15" width="20" height="1.8"/>'
  + bits(7, 15, 1) + bits(12.5, 15, 2) + bits(18, 15, 3) +
  '<rect class="vote" x="22.5" y="1" width="5" height="13.5" rx="0.7" transform="rotate(6 25 8)"/>' + tick(25, 6, 0.7)
  + '<rect class="knock" x="7" y="20" width="18" height="1.4" rx="0.7"/>')

STYLE = """.ink{fill:var(--lg-ink)} .ink-s{stroke:var(--lg-ink)} .bit{fill:var(--lg-bit)} .ghost{opacity:.35}
.vote{fill:var(--lg-vote)} .on{stroke:var(--lg-on)} .slot{fill:var(--lg-slot)} .knock{fill:var(--lg-slot);opacity:.5}"""

def svg(k, size):
    return f'<svg class="mark" viewBox="0 0 32 32" width="{size}" height="{size}" aria-hidden="true">{C[k][2]}</svg>'

for k in C:
    Path(f"concept-{k}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><style>:root{{--lg-ink:#0A1D37;--lg-bit:#1B4978;'
        f'--lg-vote:#A8551A;--lg-on:#fff;--lg-slot:#FAF8F4}}{STYLE}</style>{C[k][2]}</svg>\n')

def mode(name):
    rows = ""
    for k, (title, desc, _) in C.items():
        rows += f"""<section><h2>{k} · {title}</h2><p>{desc}</p>
<div class="sitebar"><a class="sitename">{svg(k, 22)}<span>Early Returns</span></a><nav><a>Home</a><a>Election data</a><a>2026</a></nav></div>
<div class="row"><div class="big">{svg(k, 128)}</div>
<div class="small"><div class="tab">{svg(k, 16)}<span>Early Returns</span></div>
<div class="tab">{svg(k, 32)}<span>32 px</span></div>
<div class="sizes">{svg(k, 16)}{svg(k, 24)}{svg(k, 48)}</div></div></div></section>"""
    return f'<div class="mode {name}"><h1>{"Light" if name == "light" else "Dark"} mode</h1>{rows}</div>'

Path("preview.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Early Returns logo concepts</title>
<style>
@font-face{{font-family:"IBM Plex Sans";font-weight:400;src:url(../../site/assets/fonts/IBMPlexSans-Regular.woff2)}}
@font-face{{font-family:"IBM Plex Sans";font-weight:600;src:url(../../site/assets/fonts/IBMPlexSans-SemiBold.woff2)}}
body{{margin:0;font-family:"IBM Plex Sans",sans-serif;display:flex}}
.mode{{flex:1;padding:20px 24px}}
.light{{--bg:#FAF8F4;--surface:#fff;--border:#CFDDEE;--title:#0A1D37;--text-2:#505B6A;--tab:#E6EDF6;
 --lg-ink:#0A1D37;--lg-bit:#1B4978;--lg-vote:#A8551A;--lg-on:#fff;--lg-slot:#FAF8F4}}
.dark{{--bg:#131519;--surface:#1B1E24;--border:#263B57;--title:#A9C8EC;--text-2:#B3BBC7;--tab:#2B3649;
 --lg-ink:#A9C8EC;--lg-bit:#7FB0E6;--lg-vote:#F2A65A;--lg-on:#10151C;--lg-slot:#131519}}
.mode{{background:var(--bg);color:var(--text-2)}} h1{{color:var(--title);font-size:1.1rem;margin:0 0 8px}}
h2{{color:var(--title);font-size:1rem;margin:18px 0 2px}} p{{margin:0 0 8px;font-size:.85rem}}
.sitebar{{display:flex;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-size:.9rem}}
.sitename{{display:flex;align-items:center;gap:7px;color:var(--title);font-weight:600;margin-right:auto}}
nav{{display:flex;gap:14px}} .row{{display:flex;gap:20px;align-items:center;margin-top:10px}}
.big{{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px;line-height:0}}
.tab{{display:flex;align-items:center;gap:6px;background:var(--tab);border-radius:6px 6px 0 0;padding:5px 10px;font-size:.78rem;margin-bottom:8px;width:max-content}}
.sizes{{display:flex;gap:12px;align-items:end}}
{STYLE}
</style><body>{mode("light")}{mode("dark")}</body>""")
