"""Checks on the primary state model (PP-12; PRIMARIES.md section 3, reading S23).

1. Truncation: the components of a forecast are the same when rebuilt in a world cut off at its date: raw poll rows
   that ended later deleted (and put through the question ladder again), results of the day and later deleted, later
   withdrawals and announcements deleted from the candidate timeline, and every contest not yet held unknown to the
   model except through the calendar as known that day. A sanity case confirms the comparison can fail.
2. The kernel has no negative eigenvalue, in any cycle.
3. A hand-worked case for rules 9 to 12 (three states, two candidates).
4. The baseline corner (beta 0, kappa inf, lambda 0) returns the state average where there is one and the national
   average otherwise, on the result scale (S25: where every share is at least 1 point).
5. The seed rebuilds the same draws, and a contest's draws do not depend on what else is forecast.
   The field holds only candidates in the timeline who had announced by the date (S9 as changed after run 1).
6. Changing a left-out contest's results leaves that fold's fitted values unchanged (run on 300 draws).

Exits non-zero on any failure. `--quick` skips 6.
"""
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/model"))
import primary_avg as pa  # noqa: E402
import primary_state as ps  # noqa: E402

FAIL = []
COLS = ["state", "date_known", "days", "caucus", "polled", "other", "candidate_key", "nat", "level", "W", "pattern",
        "own_r", "own_n"]


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what, flush=True)
    if not ok:
        FAIL.append(what)


# ---------------------------------------------------------------- 1. truncation

def truncated_race(cycle, party, day, results):
    """A Race that can see nothing later than the morning of `day`."""
    raw = pa._rows()
    polls = pa.select_questions(raw[raw["end"] <= day], cycle, party)
    race = ps.Race(cycle, party, polls=polls, results=results[results["date"] < day], cache=False)
    race.held = {s: d for s, d in race.held.items() if d < day}
    return race


def patch_timeline(day):
    """The candidate timeline as it stood on `day`: later withdrawals blank, candidates not yet heard of removed."""
    real = pa._timeline.__wrapped__

    def cut(cycle, party):
        out = {}
        for k, (e, a, s) in real(cycle, party).items():
            dates = [x for x in (e, a) if pd.notna(x)]
            if dates and min(dates) > day:
                continue
            out[k] = (e if pd.notna(e) and e <= day else pd.NaT, a if pd.notna(a) and a <= day else pd.NaT,
                      s if pd.notna(s) and s <= day else pd.NaT)
        return out
    return real, cut


def same(a, b):
    if len(a) != len(b):
        return False
    if not len(a):
        return True
    a, b = a[COLS].reset_index(drop=True), b[COLS].reset_index(drop=True)
    num = a.select_dtypes("number").columns
    return bool(np.allclose(a[num].to_numpy(float), b[num].to_numpy(float), atol=1e-9, equal_nan=True)
                and a.drop(columns=num).equals(b.drop(columns=num)))


def truncation(n=14):
    results = ps.load_results()
    rnd = random.Random(12)
    races = {k: ps.Race(*k) for k in pa.CYCLES}
    cases = []
    for k in pa.CYCLES:
        dates = list(ps.forecast_dates(races[k]))
        cases += [(k, d) for d in rnd.sample(dates, 2)]
    cases = rnd.sample(cases, n)
    bad, rows = 0, 0
    for (cycle, party), day in cases:
        full = races[(cycle, party)].components(day)
        real, cut = patch_timeline(day)
        pa._timeline = cut
        pa.line_end.cache_clear()
        try:
            part = truncated_race(cycle, party, day, results).components(day)
        finally:
            pa._timeline = pa._timeline_real
            pa.line_end.cache_clear()
        rows += len(full)
        if not same(full, part):
            bad += 1
            print(f"     differs: {cycle} {party} {day:%Y-%m-%d} ({len(full)} rows against {len(part)})")
    check(bad == 0 and rows > 0, f"truncation: {len(cases)} forecast dates ({rows} rows) unchanged in a world cut off "
                                 f"at the date")
    # sanity: a world cut off a month early must differ somewhere
    (cycle, party), day = next(c for c in cases if len(races[c[0]].components(c[1])))
    early = truncated_race(cycle, party, day - pd.Timedelta(days=30), results)
    early.held = dict(races[(cycle, party)].held)
    check(not same(races[(cycle, party)].components(day), early.components(day)),
          "truncation: the comparison fails when polls and results stop a month early")
    for r in races.values():
        r.save_cache()
    return races


# ---------------------------------------------------------------- 2. the kernel

def kernel_case():
    low = {c: float(np.linalg.eigvalsh(ps.kernel(c).to_numpy()).min()) for c in (2008, 2012, 2016, 2020, 2024)}
    check(min(low.values()) > -1e-10, "kernel: smallest eigenvalue " + ", ".join(f"{c} {v:.5f}" for c, v in low.items()))
    K = ps.kernel(2016)
    check(np.allclose(np.diag(K), 1) and np.allclose(K, K.T), "kernel: symmetric, 1 on the diagonal")


# ---------------------------------------------------------------- 3. a hand-worked case

class Toy(ps.Race):
    """Three states and two candidates on 1 March. IA voted (result 60 to 30); NH is polled, not yet voted; OH is the
    contest forecast, with its own average. The national average is 40 to 40 throughout."""

    def __init__(self):
        self.cycle, self.party = 2016, "D"
        self.K = ps.kernel(2016)
        day = pd.Timestamp
        self.held = {"IA": day("2016-02-01"), "NH": day("2016-03-08"), "OH": day("2016-03-15")}
        self.kind = {"IA": "caucus", "NH": "primary", "OH": "primary"}
        self._avg, self._known, self._other, self._obs = {}, {}, {}, {}
        self._disk, self._saved = None, 0
        self.today = day("2016-03-01")

    def avg(self, place, as_of):
        if place == "US":
            return {"a": (40.0, 9), "b": (40.0, 9)}
        if as_of == self.today:
            return {"NH": {"a": (30.0, 3), "b": (50.0, 3)}, "OH": {"a": (48.0, 6), "b": (32.0, 2)}}.get(place, {})
        return {}

    def field(self, as_of):
        return self.avg("US", as_of)

    def known(self, as_of):
        return {s: (d, False, self.kind[s]) for s, d in self.held.items()}

    def result(self, state):
        return ({"a": 60.0, "b": 30.0}, "votes", "a") if state == "IA" else None


def hand_case():
    t = Toy()
    D = t.today
    K = t.K
    c = t.components(D, only=["OH"]).set_index("candidate_key")
    # other: IA's 100 - 90 = 10. Result scale on 1 March: national 45 and 45; NH 33.75 and 56.25; OH 54 and 36.
    # IA's observation is against the national average on the morning it voted, before any result: other 2, so 49.
    r_ia = {"a": np.log(60 / 49), "b": np.log(30 / 49)}
    r_nh = {"a": np.log(33.75 / 45), "b": np.log(56.25 / 45)}
    ok = abs(c["other"].iat[0] - 10) < 1e-9 and abs(c.loc["a", "nat"] - 45) < 1e-9
    want = {}
    for x in ("a", "b"):
        level = (1 * r_ia[x] + 0.5 * r_nh[x]) / 1.5
        k_ia, k_nh = K.loc["OH", "IA"], 0.5 * K.loc["OH", "NH"]
        W = k_ia + k_nh
        pattern = (k_ia * (r_ia[x] - level) + k_nh * (r_nh[x] - level)) / W
        own = np.log((54 if x == "a" else 36) / 45)
        ok &= np.allclose([c.loc[x, "level"], c.loc[x, "W"], c.loc[x, "pattern"], c.loc[x, "own_r"]],
                          [level, W, pattern, own], atol=1e-12)
        n = 6 if x == "a" else 2
        prior = 0.7 * level + W / (W + 4) * pattern
        w = n / (n + 2)
        want[x] = 45 * np.exp(w * own + (1 - w) * prior)
    check(bool(ok), "hand case: other share, national scale, level, W, pattern and own r")
    got = ps.shares(c.reset_index(), 0.7, 4, 2)
    tot = want["a"] + want["b"]
    check(np.allclose(got, [want["a"] * 90 / tot, want["b"] * 90 / tot], atol=1e-9),
          f"hand case: expected shares {got[0]:.3f} and {got[1]:.3f} at beta 0.7, kappa 4, lambda 2")
    check(not t.components(D, only=["IA"]).shape[0] and c["days"].iat[0] == 14 and not c["caucus"].iat[0],
          "hand case: a voted state is not forecast; days to the contest")
    nh = t.components(D, only=["NH"]).set_index("candidate_key")
    r_oh = np.log(54 / 45)                                             # OH is polled too: half-weight evidence for NH
    check(abs(nh.loc["a", "level"] - (r_ia["a"] + 0.5 * r_oh) / 1.5) < 1e-12
          and abs(nh.loc["a", "W"] - (K.loc["NH", "IA"] + 0.5 * K.loc["NH", "OH"])) < 1e-12,
          "hand case: a polled state's own average is in neither its level nor its W (rule 11)")


# ---------------------------------------------------------------- 4. the baseline corner

def baseline_case(races):
    race, day = races[(2016, "R")], pd.Timestamp("2016-03-01")
    c = race.components(day)
    c = c.assign(share=ps.shares(c, *ps.BASELINE_POINT))
    nat, n_state, n_nat, ok = race.scaled("US", day), 0, 0, True
    for state, g in c.groupby("state"):
        g = g.set_index("candidate_key")
        if not g["polled"].iat[0]:
            ok &= np.allclose(g["share"], [nat[k] for k in g.index], atol=1e-9)
            n_nat += 1
            continue
        st = race.scaled(state, day)
        if set(st) != set(g.index) or min(st.values()) < 1 or min(nat.values()) < 1:
            continue                                                   # S25, S13
        ok &= np.allclose(g["share"], [st[k] for k in g.index], atol=1e-9)
        n_state += 1
    check(bool(ok) and n_state > 0 and n_nat > 0, f"baseline corner: the state average in {n_state} polled states, "
                                                  f"the national average in {n_nat} unpolled places (2016 R, 1 March)")


# ---------------------------------------------------------------- 5. draws

def draws_case(races):
    race, day = races[(2020, "D")], pd.Timestamp("2020-03-03")
    v = dict(beta=0.5, kappa=4, tau=0.1, sigma_p=0.2, sigma_u=0.4)
    v["lambda"] = 4
    s1, k1, d1 = race.draws(day, v)
    s2, k2, d2 = race.draws(day, v)
    check(s1 == s2 and k1 == k2 and np.array_equal(d1, d2) and d1.shape[0] == ps.N_DRAWS,
          f"draws: the seed rebuilds them ({d1.shape[1]} contests, {d1.shape[2]} candidates, {d1.shape[0]} draws)")
    comp = race.components(day)
    days = [race.known(day)[s][0] for s in s1]
    check(days == sorted(days) and np.allclose(d1.sum(axis=2), 100 - comp["other"].iat[0], atol=1e-3),
          "draws: contests in calendar order; every draw sums to 100 less the other share")
    one = s1[len(s1) // 2]
    _, _, d3 = race.draws(day, v, comp[comp["state"].eq(one)])
    check(np.allclose(d3[:, 0, :], d1[:, s1.index(one), :], atol=1e-4), f"draws: {one}'s are the same forecast alone")
    f = race.forecast(day, v)
    check(np.allclose(f.groupby("state")["win"].sum(), 1, atol=1e-9) and (f["p10"] <= f["p90"]).all(),
          "table: chances of winning sum to 1 in every contest")


# ---------------------------------------------------------------- 6. the left-out contest

def fold_case():
    ps.N_DRAWS = 300
    left = (2012, "R")
    races = {k: ps.Race(*k) for k in ps.OPEN}
    v1, sc1, _ = ps.fit(races)
    res = ps.load_results()
    hit = (res["cycle"] == left[0]) & (res["party"] == left[1])
    rng = np.random.default_rng(1)
    res.loc[hit, "share"] = rng.permutation(res.loc[hit, "share"].to_numpy())
    races[left] = ps.Race(*left, results=res)
    v2, sc2, _ = ps.fit(races)
    key = f"{left[0]} {left[1]}"
    a, b = v1[v1["left_out"] == key].reset_index(drop=True), v2[v2["left_out"] == key].reset_index(drop=True)
    check(a.equals(b), f"left-out contest: {key}'s results shuffled, its fold's fitted values and losses unchanged")
    moved = not np.allclose(sc1.loc[(sc1["cycle"] == left[0]) & (sc1["party"] == left[1]), "actual"].to_numpy(),
                            sc2.loc[(sc2["cycle"] == left[0]) & (sc2["party"] == left[1]), "actual"].to_numpy())
    other = not v1[v1["left_out"] != key].reset_index(drop=True)[["fit_mse", "fit_log_loss"]].equals(
        v2[v2["left_out"] != key].reset_index(drop=True)[["fit_mse", "fit_log_loss"]])
    check(moved and other, "left-out contest: the shuffle did change the results, and the other folds' losses")


def field_case(races):
    bad = []
    for (cycle, party), day in (((2008, "D"), "2007-12-04"), ((2016, "D"), "2016-01-25"), ((2020, "D"), "2020-01-04")):
        f = set(races[(cycle, party)].field(pd.Timestamp(day)))
        bad += sorted(f & {"al-gore", "biden", "warren", "hillary-rodham-clinton", "john-kerry"})
        if not f:
            bad.append(f"empty field {cycle} {party}")
    check(not bad, "field: no polled non-candidate before the first contest (Gore 2008, Biden 2016, Clinton 2020)")


if __name__ == "__main__":
    pa._timeline_real = pa._timeline
    kernel_case()
    hand_case()
    races = truncation()
    baseline_case(races)
    field_case(races)
    draws_case(races)
    if "--quick" not in sys.argv:
        fold_case()
    print("\n" + ("all checks passed" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
    sys.exit(1 if FAIL else 0)
