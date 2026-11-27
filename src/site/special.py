"""A live special's page, /specials/<race>/ (SP-7; rules in SPECIALS.md section 5).

    python src/site/special.py                      every record in data/specials/*.json -> site/specials/<race>/
    python src/site/special.py --preview OUT REC..  the given records (dry runs) -> OUT/specials/<race>/, never site/

landing.py runs the first form, so the daily build rebuilds these pages with the rest. One page per record,
data/specials/<race>.json; every word on the page that is not a number comes from the record, the settings in
site.json, or the branch text below. No page carries a build date.

States (rule 3): coming (no runs: the race, its dates and what the forecast waits on, no numbers); forecast (the
latest run, every earlier run as a line, and the polls entered); result (the locked last run beside the certified
result, the miss, and which intervals held it). A record marked "dry_run" is a past race run as if live; its page
says so at the top and is built only with --preview.
"""
import html
import json
import sys
from pathlib import Path

import shell

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
RECORDS = ROOT / "data" / "specials"
E = html.escape
NOTE = "https://github.com/vrraiv/earlyreturns/blob/main/SPECIALS.md"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
BRANCH = {
    "house": ("The forecast is the single-race path for a House special: the district's lean on the lines in force "
              "(twice its Cook PVI), the national environment on the date with the recent-specials term, and the "
              "frozen House district model as the prior; polls, when there are any, are weighed against it by "
              "precision. The error is normal, with the spread of earlier specials' own forecast misses, measured "
              "on races before this one."),
    "senate": ("The forecast is the single-race path for a Senate special: the state's lean in the last federal "
               "election before the date, the off-cycle national environment, and twice the incumbency term; polls, "
               "when there are any, are weighed against it by precision. The error is a t distribution with an SD of "
               "18 points. That SD was measured on the 13 past Senate specials the path was checked on, so it was "
               "chosen from the same races, not tested on new ones."),
}


def day(s):
    """'2027-11-02' -> 'November 2, 2027'; '2027-11' -> 'November 2027'."""
    p = str(s).split("-")
    if len(p) == 1:
        return p[0]
    if len(p) == 2:
        return f"{MONTHS[int(p[1]) - 1]} {p[0]}"
    return f"{MONTHS[int(p[1]) - 1]} {int(p[2])}, {p[0]}"


def margin(x):
    return "even" if round(x, 1) == 0 else f"{'D' if x > 0 else 'R'}+{abs(x):.1f}"


def names(rec):
    d = next((c["name"] for c in rec.get("candidates", []) if c["party"].startswith("Dem")), None)
    r = next((c["name"] for c in rec.get("candidates", []) if c["party"].startswith("Rep")), None)
    return (d or "The Democrat"), (r or "The Republican")


def state(rec):
    return "result" if rec.get("result") else "forecast" if rec.get("runs") else "coming"


def last_run(rec):
    runs = rec.get("runs", [])
    locked = [r for r in runs if r.get("locked")]
    return (locked or runs)[-1] if runs else None


def strip(lo, hi, mu, iv, actual=None):
    """The latest run as one strip: 95% and 80% intervals, the forecast margin, and the result when there is one."""
    w, pad, y = 640, 20, 30
    xs = [iv["95"][0], iv["95"][1], 0] + ([actual] if actual is not None else [])
    a, b = min(xs + [lo]) - 3, max(xs + [hi]) + 3
    X = lambda v: pad + (v - a) / (b - a) * (w - 2 * pad)
    ticks = [t for t in range(int(a // 10 * 10), int(b) + 1, 10) if a <= t <= b]
    out = [f'<svg class="strip" viewBox="0 0 {w} 74" role="img" aria-label="Forecast margin {E(margin(mu))}, '
           f'80% interval {E(margin(iv["80"][0]))} to {E(margin(iv["80"][1]))}" style="width:100%;max-width:{w}px">']
    for t in ticks:
        out.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{y - 16}" y2="{y + 16}" style="stroke:var(--border)"/>'
                   f'<text x="{X(t):.1f}" y="{y + 32}" text-anchor="middle" style="fill:var(--text-3);font-size:11px">'
                   f'{"even" if t == 0 else ("D+" if t > 0 else "R+") + str(abs(t))}</text>')
    out.append(f'<rect x="{X(iv["95"][0]):.1f}" y="{y - 6}" width="{X(iv["95"][1]) - X(iv["95"][0]):.1f}" height="12" '
               f'rx="2" style="fill:var(--neutral);opacity:.3"/>')
    out.append(f'<rect x="{X(iv["80"][0]):.1f}" y="{y - 6}" width="{X(iv["80"][1]) - X(iv["80"][0]):.1f}" height="12" '
               f'rx="2" style="fill:var(--neutral);opacity:.85"/>')
    out.append(f'<line x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{y - 18}" y2="{y + 18}" style="stroke:var(--text-2)"/>')
    col = "var(--dem)" if mu > 0 else "var(--rep)"
    out.append(f'<circle cx="{X(mu):.1f}" cy="{y}" r="6" style="fill:{col};stroke:var(--surface);stroke-width:2"/>')
    if actual is not None:
        out.append(f'<path d="M{X(actual):.1f} {y - 15} l-6 -9 h12 z" style="fill:var(--ink)"/>')
    out.append("</svg>")
    return "".join(out)


def head_part(rec, prefix, title, desc):
    import landing
    return landing.head(title, desc, prefix, landing.og(title, desc, "og-home.png", f"specials/{rec['race']}/"))


def page(rec):
    prefix = "../../"
    st = state(rec)
    d_name, r_name = names(rec)
    final = rec["rounds"][-1]["date"]
    title = f'{rec["title"]} · {shell.SETTINGS["name"]}'
    desc = (f'{rec["title"]}, {day(final)}: ' +
            ("the forecast, how it has moved, and the polls." if st == "forecast" else
             "the forecast against the result." if st == "result" else "no forecast yet; what it waits on and the dates."))
    v = rec.get("vacancy", {})
    lede = (f'{rec["state_name"]}, {rec["seat"]}: a special election {"on" if len(final) == 10 else "in"} {day(final)}. ' +
            (f'{v["vacated_by"]} ({v["party"]}) leaves the seat in {day(v["date"])}.' if v.get("reason") == "announced" else
             f'{v["vacated_by"]} ({v["party"]}) {v["reason"]}, {day(v["date"])}.' if v else ""))
    parts = []
    if rec.get("dry_run"):
        parts.append('<p class="note"><strong>Dry run.</strong> A past race, run as if it were live, to check this '
                     'page and the steps behind it. It is not published on the site.</p>')
    if v.get("note"):
        parts.append(f'<p>{E(v["note"])}</p>')

    if st == "coming":
        parts.append('<p class="note">No forecast yet. The numbers appear once the inputs below are in; until then '
                     'this page holds the race and its dates.</p>')
        if rec.get("waits_on"):
            parts.append("<h2>What the forecast waits on</h2><ul>" +
                         "".join(f"<li>{E(w)}</li>" for w in rec["waits_on"]) + "</ul>")
    else:
        run = last_run(rec)
        res = rec.get("result")
        p = run["p_dem"]
        lead, lp = (d_name, p) if p >= 0.5 else (r_name, 1 - p)
        when = "Last forecast before election day" if run.get("locked") else f'Forecast of {day(run["run_date"])}'
        parts.append(f"<h2>{E(when)}</h2>")
        stats = [(margin(run["margin"]), "forecast margin"),
                 (f'{margin(run["intervals"]["80"][0])} to {margin(run["intervals"]["80"][1])}', "80% interval"),
                 (f"{lp:.0%}", f"chance {lead} wins")]
        if res:
            stats.append((margin(res["margin"]), "result"))
        parts.append('<div class="stats">' + "".join(f'<div class="stat"><div class="v">{E(a)}</div>'
                                                     f'<div class="l">{E(b)}</div></div>' for a, b in stats) + "</div>")
        parts.append(strip(-10, 10, run["margin"], run["intervals"], res["margin"] if res else None))
        parts.append('<p class="tiny">Dot: the forecast margin. Dark band: the 80% interval; light band: 95%.' +
                     (" Triangle: the result." if res else "") + "</p>")
        if res:
            miss = res["margin"] - run["margin"]
            held = [q for q in ("50", "80", "95") if run["intervals"][q][0] <= res["margin"] <= run["intervals"][q][1]]
            won = (res["margin"] > 0) == (p >= 0.5)
            parts.append(f'<p>The result was {E(margin(res["margin"]))}, a miss of {abs(miss):.1f} points '
                         f'({"toward the Democrat" if miss > 0 else "toward the Republican"} of the forecast). '
                         f'The forecast {"had" if won else "did not have"} the winner, and the result fell '
                         + (f'inside the {", ".join(q + "%" for q in held)} interval{"s" if len(held) > 1 else ""}.'
                            if held else "outside every interval.") + "</p>")
        rows = "".join(f'<tr><td>{E(day(r["run_date"]))}{" (last)" if r.get("locked") else ""}</td>'
                       f'<td>{len(r["polls_used"])}</td><td>{E(margin(r["margin"]))}</td>'
                       f'<td>{E(margin(r["intervals"]["80"][0]))} to {E(margin(r["intervals"]["80"][1]))}</td>'
                       f'<td>{r["p_dem"]:.0%}</td></tr>' for r in reversed(rec["runs"]))
        parts.append("<h2>Every run</h2><div class='tbl-wrap'><table><thead><tr><th>Run</th><th>Polls used</th><th>Margin</th>"
                     f"<th>80% interval</th><th>Chance {E(d_name)} wins</th></tr></thead><tbody>{rows}</tbody></table></div>")
        parts.append(f'<p class="tiny">Last run: lean {run["lean"]:+.1f} ({E(run["lean_source"])}), environment '
                     f'{margin(run["environment"])}, prior {margin(run["prior"])}' +
                     (f', poll average {margin(run["poll_avg"])} with weight {run["poll_weight"]:.2f} '
                      f'({E(run["poll_window"])} before election day)' if run["poll_avg"] is not None else ", no polls") +
                     f'. Model commit {E(run["commit"])}.</p>')
        if rec.get("polls"):
            prow = "".join(f'<tr><td>{E(q["pollster"])}{" (" + E(q["partisan"]) + ")" if q.get("partisan") else ""}</td>'
                           f'<td>{E(day(q["end"]))}</td><td>{q["dem"]:g}</td><td>{q["rep"]:g}</td>'
                           f'<td>{E(margin(100 * (q["dem"] - q["rep"]) / (q["dem"] + q["rep"])))}</td></tr>'
                           for q in sorted(rec["polls"], key=lambda q: q["end"], reverse=True))
            parts.append(f"<h2>Polls</h2><div class='tbl-wrap scroll'><table><thead><tr><th>Pollster</th><th>Field ended</th><th>{E(d_name)}</th>"
                         f"<th>{E(r_name)}</th><th>Two-party margin</th></tr></thead><tbody>{prow}</tbody></table></div>")
            parts.append('<p class="tiny">Every poll entered, none dropped for its numbers. A run averages those that '
                         'ended in the 21 days before election day, or, with none, 22 to 60 days before. Partisan '
                         'polls are marked and used unshifted.</p>')

    dates = [(day(r["date"]), r["round"].capitalize()) for r in rec["rounds"]]
    if v.get("date"):
        dates.insert(0, (day(v["date"]), "Seat vacated" if v.get("reason") != "announced" else "Seat to be vacated"))
    parts.append("<h2>Key dates</h2><ul class=\"dates\">" + "".join(
        f'<li><span class="when">{E(a)}</span><span>{E(b)}</span></li>' for a, b in dates) + "</ul>")
    if rec.get("candidates"):
        parts.append("<h2>Candidates</h2><ul>" + "".join(f'<li>{E(c["name"])} ({E(c["party"])})</li>'
                                                          for c in rec["candidates"]) + "</ul>")
    parts.append(f'<h2>How this is made</h2><p>{E(BRANCH[rec["branch"]])}</p>'
                 f'<p>The steps and the rules are in the <a href="{NOTE}">design note on special elections</a>, '
                 'sections 1, 2 and 5. Probabilities appear only from a branch whose design was settled before '
                 'this race.</p>')
    return head_part(rec, prefix, title, desc) + f"""<body>
{shell.header(prefix)}
<main class="wrap">
<h1>{E(rec["title"])}</h1>
<p class="lede">{E(lede)}</p>
{chr(10).join(parts)}
</main>
""" + footer()


def footer():
    import landing
    return landing.foot()


def build(records, out_root):
    built = []
    for p in records:
        rec = json.loads(Path(p).read_text(encoding="utf-8"))
        out = out_root / "specials" / rec["race"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(rec), encoding="utf-8")
        built.append(out)
    return built


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--preview":
        out = build(argv[2:], Path(argv[1]))
    else:
        live = sorted(RECORDS.glob("*.json"))
        bad = [p.name for p in live if json.loads(p.read_text(encoding="utf-8")).get("dry_run")]
        if bad:
            raise SystemExit(f"dry-run records belong in data/specials/dry_runs/, not {bad}")
        out = build(live, SITE)
    print("built", ", ".join(str(p) for p in out) or "no special pages")
    return out


if __name__ == "__main__":
    main()
