"""Logo round 3 for Early Returns (SI-9): concept C, one colour.
From round 2: the arriving bits are dropped; the ballot is taller, thinner and leans further, like a slash, with no
tick; columns move left to make room. Light mode compares round 1's bit blue with a shade darker; dark mode is the
light grey chosen in round 2. Writes mark.svg, favicon.svg and preview-r3.html."""
from itertools import count
from pathlib import Path

ids = count()

def column(x, base, n, w=4, gap=1):
    return "".join(f'<rect x="{x}" y="{base - (i + 1)*w - i*gap:.2f}" width="{w}" height="{w}" rx="0.64"/>' for i in range(n))

BOX = '<path d="M3 20.5 H29 V26.5 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 Z"/>'
SLOT = '<rect x="7" y="22.2" width="18" height="1.5" rx="0.75"/>'
COLS = column(6.5, 19.7, 1) + column(11.5, 19.7, 2) + column(16.5, 19.7, 3)
BALLOT = '<rect x="22.4" y="1.6" width="3.2" height="18.4" rx="0.8" transform="rotate(17 24 20)"/>'

def mark(size=None):
    i = next(ids)
    wh = f' width="{size}" height="{size}"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"{wh} aria-hidden="true">'
            f'<mask id="er{i}"><g fill="#fff">{BOX}{COLS}{BALLOT}</g><g fill="#000">{SLOT}</g></mask>'
            f'<rect class="ink" width="32" height="32" fill="currentColor" mask="url(#er{i})"/></svg>')

LIGHTS = [("#1B4978", "Light 1 · round 1's bit blue (the site's heading blue)"), ("#153A62", "Light 2 · one shade darker")]
DARK = ("#C9CFD8", "Dark · light grey (round 2's middle option)")

solo = mark().replace('<svg ', '<svg ', 1)
style = ('<style>.ink{fill:#1B4978}@media (prefers-color-scheme: dark){.ink{fill:#C9CFD8}}</style>')
standalone = solo.replace('fill="currentColor" ', '').replace('aria-hidden="true">', 'aria-hidden="true">' + style, 1)
Path("mark.svg").write_text(standalone + "\n")
Path("favicon.svg").write_text(standalone + "\n")

def block(colour, label):
    return (f'<div class="sitebar"><a class="sitename"><span style="color:{colour};line-height:0">{mark(24)}</span>'
            f'<span>Early Returns</span></a><nav><a>Home</a><a>Election data</a><a>2026</a></nav></div>'
            f'<p class="lab">{label}</p><div class="smallrow" style="color:{colour}">'
            f'<div class="tab"><span style="color:{colour};line-height:0">{mark(16)}</span><span>Early Returns</span></div>'
            f'<div class="tab"><span style="color:{colour};line-height:0">{mark(32)}</span><span>32 px</span></div>'
            f'<div class="big">{mark(120)}</div></div>')

Path("preview-r3.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Early Returns logo, round 3</title>
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
.smallrow{{display:flex;gap:14px;align-items:center;margin:0 0 22px}}
.tab{{display:flex;align-items:center;gap:6px;background:var(--tab);color:var(--text-2);border-radius:6px 6px 0 0;padding:5px 10px;font-size:.78rem}}
.big{{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px;line-height:0;margin-left:auto}}
</style><body>
<div class="mode light"><h1>Light mode: two blues</h1>{"".join(block(c, l) for c, l in LIGHTS)}</div>
<div class="mode dark"><h1>Dark mode</h1>{block(*DARK)}</div>
</body>""")
