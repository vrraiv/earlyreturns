"""Build the model page, /model/ (work plan card SI-5): one section per model, each drawn two ways.

    python src/site/model.py                      (src/site/landing.py runs this too, and so does build.py)
    python src/site/model.py --preview OUT        writes OUT/model/index.html, leaving site/ alone

Every word and number on the page comes from src/site/model.json; nothing is computed here and nothing is read from
the model outputs, so the page changes only when that file does. It carries no build date: a rebuild writes the same
bytes, and the daily scorecard job leaves it alone.

Each model in model.json has:
  flow      the flow chart: `steps` in order (title, text, `fit` = what is estimated or assumed, `reads` = the inputs
            that step takes; an input marked "past" is history used to set the model's numbers, drawn dashed) and
            `outputs`. Drawn as three columns: what goes in, what the model does, what comes out.
  timeline  the same model through a campaign: `stages` in date order (when, title, what the model `sees`, what it
            `does`). A stage may carry `mix`, the share of the forecast's weight on the polls (`polls`, or a span
            `polls` to `polls_hi`), drawn as a bar; `lock` marks the stages after the forecast is frozen.
  tested    how it was tested: a sentence, a few figures and their caveats.
  stands    where the model stands, and `links` (a `path` inside the site, relative to /model/, or a full `url`).

The numbers in model.json are copied by hand from the notes (BACKTEST.md, ELECTORAL_COLLEGE.md, PRIMARIES.md,
SPECIALS.md, FORECAST.md, the 2026 method tab and the cards' decisions in planning/plan.js); change them there first. The styles are in site/assets/site.css ("the model page").
"""
import json
import sys
from pathlib import Path

import landing
import shell

SITE = landing.SITE
E = landing.E
M = json.loads(Path(__file__).with_name("model.json").read_text(encoding="utf-8"))
ARROW = '<span class="{}" aria-hidden="true"></span>'


def flow(m):
    """Inputs on the left, each beside the step that reads it; the steps in order down the middle; the outputs on the right."""
    F, H = m["flow"], M["heads"]
    n = len(F["steps"])
    cells = [f'<div class="colhead">{E(H["in"])}</div><div class="colhead">{E(H["does"])}</div>'
             f'<div class="colhead">{E(H["out"])}</div>']
    for i, s in enumerate(F["steps"], 1):
        chips = "".join(f'<li{" class=past" if r.get("past") else ""}>{E(r["t"])}</li>' for r in s["reads"])
        cells.append(f'<ul class="ins" style="grid-row:{i + 1}">{chips}</ul>' if chips else "")
        fit = f'<p class="fit">{E(s["fit"])}</p>' if s.get("fit") else ""
        arrows = (ARROW.format("arr-r") if chips else "") + ARROW.format("arr-d" if i < n else "arr-o")
        cells.append(f'<div class="step" style="grid-row:{i + 1}"><h4><span class="n">{i}</span>{E(s["title"])}</h4>'
                     f'<p>{E(s["text"])}</p>{fit}{arrows}</div>')
    outs = "".join(f"<li>{E(o)}</li>" for o in F["outputs"])
    cells.append(f'<div class="outs" style="grid-row:2 / span {n}"><div class="colhead sm">{E(H["out"])}</div><ul>{outs}</ul></div>')
    L = M["legend"]
    legend = (f'<p class="flowkey"><span><i></i>{E(L["now"])}</span><span><i class="past"></i>{E(L["past"])}</span></p>')
    after = f'<p class="small muted">{E(F["after"])}</p>' if F.get("after") else ""
    return f'<div class="flow">{"".join(cells)}</div>{legend}{after}'


def mix(x):
    """The weight on the polls against the starting point, as one bar; a span is drawn in a lighter shade."""
    lo, hi = x["polls"], x.get("polls_hi", x["polls"])
    bar = (f'<i class="po" style="width:{lo}%"></i>' if lo else "") + (f'<i class="pm" style="width:{hi - lo}%"></i>' if hi > lo else "")
    return (f'<div class="mix" role="img" aria-label="{E(x["label"])}">{bar}</div>'
            f'<div class="mixlab"><span>Polls</span><span>Starting point</span></div><p class="mixnote">{E(x["label"])}</p>')


def timeline(m):
    T = m["timeline"]
    stages = "".join(
        f'<li class="stage{" lock" if s.get("lock") else ""}"><div class="when">{E(s["when"])}</div><h4>{E(s["title"])}</h4>'
        f'<p><b>Sees</b> {E(s["sees"])}</p><p><b>Does</b> {E(s["does"])}</p>{mix(s["mix"]) if s.get("mix") else ""}</li>'
        for s in T["stages"])
    note = f'<p class="note">{E(T["note"])}</p>' if T.get("note") else ""
    return f'<ol class="tl" style="--n:{len(T["stages"])}">{stages}</ol>{note}'


def tested(m):
    T = m["tested"]
    stats = "".join(f'<div class="stat"><div class="v">{E(s["v"])}</div><div class="l">{E(s["l"])}</div></div>' for s in T["stats"])
    notes = "".join(f"<li>{E(x)}</li>" for x in T.get("notes", []))
    return f'<p>{E(T["text"])}</p><div class="stats">{stats}</div>' + (f'<ul class="list small muted">{notes}</ul>' if notes else "")


def links(m):
    return " · ".join(f'<a href="{E(x.get("path") or x["url"])}">{E(x["text"])}</a>' for x in m.get("links", []))


def section(m):
    H = M["heads"]
    return f"""<section class="mdl" id="{E(m["key"])}">
<h2>{E(m["name"])} <span class="tag st-{E(m["status"]["kind"])}">{E(m["status"]["label"])}</span></h2>
<p class="lede">{E(m["summary"])}</p>
<h3>{E(H["flow"])}</h3>
{flow(m)}
<h3>{E(H["timeline"])}</h3>
{timeline(m)}
<h3>{E(H["tested"])}</h3>
{tested(m)}
<h3>{E(H["stands"])}</h3>
<p>{E(m["stands"])}</p>
<p class="small">{links(m)}</p>
</section>
"""


def index():
    """One card per model, linking to its section."""
    rows = "".join(f'<a class="sec" href="#{E(m["key"])}"><h3>{E(m["name"])}</h3><p>{E(m["status"]["label"])}</p></a>'
                   for m in M["models"])
    return f'<div class="sections mindex">{rows}</div>'


def page():
    title = f'{M["title"]} · {landing.S["name"]}'
    return landing.head(title, M["description"], "../", landing.og(title, M["description"], "og-home.png", "model/")) + f"""<body class="model">
{shell.header("../", "model")}
<main class="wrap">
<h1>{E(M["title"])}</h1>
<p class="lede">{E(M["lede"])}</p>
<p class="note">{E(M["note"])}</p>
{index()}
{"".join(section(m) for m in M["models"])}</main>
""" + landing.foot()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[1]) if argv[:1] == ["--preview"] else SITE
    out = root / "model" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(), encoding="utf-8")
    print("built", out)
    return out


if __name__ == "__main__":
    main()
