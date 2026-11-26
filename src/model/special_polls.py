"""Polls of past specials (SP-4, SPECIALS.md section 2).

  python src/model/special_polls.py shift    the partisan-sponsor shift re-estimated without special elections

shift: the frozen forecast's estimator (src/model/poll_settings.py, sponsor_shift) on the same FiveThirtyEight rows,
minus every House or Senate race whose election day is not the regular November general-election day of an even year
(specials, runoffs and odd-year House races). Governor races are all kept: off-cycle governors are regular elections.
So no special-election poll is ever compared with its result here. Writes data/processed/special_polls_shift.json.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "collect"))
from common import ROOT  # noqa: E402
import bias_analysis as BA  # noqa: E402
import poll_settings as PS  # noqa: E402

OUT = ROOT / "data" / "processed"


def general_day(year):
    """Tuesday after the first Monday in November."""
    d = pd.Timestamp(f"{year}-11-01")
    first_monday = d + pd.Timedelta(days=(0 - d.weekday()) % 7)
    return first_monday + pd.Timedelta(days=1)


def is_special(r):
    ed = pd.to_datetime(r.electiondate, format="mixed")
    regular = (ed.dt.year % 2 == 0) & (ed == ed.dt.year.map(general_day))
    return r.type_simple.isin(["House-G", "Sen-G"]) & ~regular


def shift():
    r = BA.load()
    sp = is_special(r)
    frozen = PS.sponsor_shift(r)
    clean = PS.sponsor_shift(r[~sp])
    out = {"frozen": frozen, "without_specials": clean,
           "dropped": {"rows": int(sp.sum()), "races": int(r[sp].race_id.nunique())},
           "chosen": {"partisan_shift_house": round(max(clean["house_district"]["shift"], 0.0), 1),
                      "partisan_shift_statewide": round(max(clean["statewide"]["shift"], 0.0), 1)},
           "note": "poll_settings.sponsor_shift on FiveThirtyEight raw_polls 1998-2022, House and Senate races off the "
                   "even-year general-election day removed (SP-4 rule 5, P3)"}
    (OUT / "special_polls_shift.json").write_text(json.dumps(out, indent=1))
    for k in ("house_district", "statewide"):
        f, c = frozen[k], clean[k]
        print(f"{k}: frozen {f['shift']:.2f} ({f['n_polls']} polls, {f['n_races']} races) -> without specials "
              f"{c['shift']:.2f} +/- {c['se']:.2f} ({c['n_polls']} polls, {c['n_races']} races)")
    print("dropped:", out["dropped"], "chosen:", out["chosen"])


if __name__ == "__main__":
    {"shift": shift}[sys.argv[1]]()
