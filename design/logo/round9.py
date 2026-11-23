"""Logo round 9 for Early Returns (SI-9): the pair. Main mark F6 (two lanes, staggered start, smaller check);
favicon F2 (dashed infield), and F2s, F2 with F6's smaller check and longer dashes so the two cuts match.
Writes mark.svg (F6), favicon.svg (F2), concept-F2s.svg and preview-r9.html."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("r8", Path(__file__).with_name("round8.py"))
r8 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r8)

F2S = (r8.outer() + '<rect x="8" y="13" width="16" height="7" rx="3.5" fill="none" stroke="#fff" stroke-width="2" '
       'stroke-dasharray="3.4 2.4" stroke-linecap="round"/>' + r8.check(r8.SMALL, 2.6))
V = {"F6": r8.V["F6"][2], "F2": r8.V["F2"][2], "F2s": F2S}

def standalone(body):
    return r8.mark(body).replace('fill="currentColor" ', '').replace('aria-hidden="true">', 'aria-hidden="true">' + r8.STYLE, 1) + "\n"

Path("mark.svg").write_text(standalone(V["F6"]))
Path("favicon.svg").write_text(standalone(V["F2"]))
Path("concept-F2s.svg").write_text(standalone(V["F2s"]))

def pair(fav, colour, label):
    m = r8.mark
    return (f'<h2>{label}</h2>'
            f'<div class="sitebar"><a class="sitename"><span style="color:{colour};line-height:0">{m(V["F6"], 24)}</span>'
            f'<span>Early Returns</span></a><nav><a>Home</a><a>Election data</a></nav></div>'
            f'<div class="smallrow"><div class="tab"><span style="color:{colour};line-height:0">{m(V[fav], 16)}</span><span>Early Returns</span></div>'
            f'<div class="tab"><span style="color:{colour};line-height:0">{m(V[fav], 32)}</span><span>favicon 32 px</span></div>'
            f'<div class="big" style="color:{colour};display:flex;gap:10px">{m(V["F6"], 96)}{m(V[fav], 96)}</div></div>')

css = Path("preview-r5.html").read_text().split("<style>")[1].split("</style>")[0]
L, D = "#1B4978", "#C9CFD8"
Path("preview-r9.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Early Returns logo, round 9</title>
<style>{css}</style><body>
<div class="mode light"><h1>Light mode</h1>{pair("F2", L, "F6 mark + F2 favicon (as chosen)")}{pair("F2s", L, "F6 mark + F2s favicon (smaller check, longer dashes)")}</div>
<div class="mode dark"><h1>Dark mode</h1>{pair("F2", D, "F6 mark + F2 favicon (as chosen)")}{pair("F2s", D, "F6 mark + F2s favicon (smaller check, longer dashes)")}</div>
</body>""")
