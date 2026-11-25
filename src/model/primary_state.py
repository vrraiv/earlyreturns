"""The primary state model (PP-12), built as PRIMARIES.md section 3 sets it out (rules 1-18, readings S1-S23).

    Race(cycle, party)                  one party's contest in one cycle, as of any date
      .components(as_of)                rule 10's pieces for every contest still to come: one row per contest, candidate
      .forecast(as_of, values)          rule 17's table: expected share, 10th and 90th percentiles, chance of winning
      .draws(as_of, values)             the 10,000 draws behind it, contests in calendar order (for PP-7; S3)
    shares(components, beta, kappa, lam)  rules 10-12 for any point values (the baseline is beta 0, kappa inf, lam 0)
    fit()                               rule 16: the six values with each open contest left out, and the baseline's three
    build()                             fits, then writes the values and the forecasts to data/processed

Nothing here reads a poll, result, withdrawal or date change later than `as_of` (rule 4): averages come from
primary_avg.average(), dates from primary_calendar as known on the day, results only from contests already held.
Averages are slow to rebuild, so they are kept in memory and, if PRIMARY_STATE_CACHE names a folder, on disk there.
"""
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import error_structure as ES  # noqa: E402
import primary_avg as pa  # noqa: E402
import primary_calendar as pc  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data/interim"
OUT = ROOT / "data/processed"

OPEN = sorted(pa.OPEN)
MEASURES = ["degree_share", "log_inc", "white_share", "black_share", "latino_share", "rural_share"]   # rule 10
REGION_TERM = 1.0          # rule 10: added to d² across census regions
POLLED_WEIGHT = 0.5        # rule 9
OTHER_DEFAULT = 2.0        # rule 6: before any result
FLOOR = 1.0                # rule 7: points, before the log
CAUCUS = 1.5               # rule 13
N_DRAWS = 10_000           # rule 13
SEED = 2028                # S4
P_FLOOR = 1 / 20_000       # rule 16
SCORED = (30, 7, 0)        # rule 16: days before the contest

GRID_BETA = [round(0.1 * i, 1) for i in range(11)]
GRID_KAPPA = [0, 0.5, 1, 2, 4, 8, 16, 32, np.inf]
GRID_LAMBDA = [0, 0.5, 1, 2, 4, 8, 16, 32, np.inf]
GRID_TAU = [0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.6]
GRID_SIGMA_P = [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.6, 0.8]
GRID_SIGMA_U = [0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0, 1.5]
BASELINE_POINT = (0.0, np.inf, 0.0)   # rule 18

STATES = sorted(ES.STATE_REGION)       # the 50 states and DC


# ---------------------------------------------------------------- the kernel (rule 10)

def kernel(cycle):
    """exp(-d² / 2m²) between the 50 states and DC: six standardized measures plus the region term, m the median
    distance (region term included). Returns a frame indexed and columned by state."""
    v = pd.read_csv(INTERIM / "state_demographics_vintages.csv").set_index("election").loc[cycle]
    d = pd.read_csv(INTERIM / "state_demographics.csv")
    d = d[d["year"] == int(v["year_before"])].set_index("state").loc[STATES].copy()
    d["log_inc"] = np.log(d["median_household_income"])
    u = pd.read_csv(INTERIM / "state_rural_share.csv")
    d["rural_share"] = u[u["census"] == int(v["rural_census"])].set_index("state")["rural_share"].loc[STATES]
    z = ((d[MEASURES] - d[MEASURES].mean()) / d[MEASURES].std(ddof=1)).to_numpy()
    reg = np.array([ES.STATE_REGION[s] for s in STATES])
    d2 = ((z[:, None, :] - z[None, :, :]) ** 2).sum(2) + REGION_TERM * (reg[:, None] != reg[None, :])
    m = float(np.median(np.sqrt(d2[np.triu_indices(len(STATES), 1)])))
    return pd.DataFrame(np.exp(-d2 / (2 * m * m)), index=STATES, columns=STATES)


# ---------------------------------------------------------------- one party's contest in one cycle

def load_results():
    r = pd.read_csv(INTERIM / "primary_results.csv", low_memory=False)
    r = r[r["line"].eq("candidate")]
    r = r[r["rcv_round"].isna() | r["rcv_round"].eq("first")]          # R12: first round
    r = r.assign(date=pd.to_datetime(r["date"]), share=100 * r["share"])
    return r[["cycle", "party", "state", "contest", "date", "candidate_key", "measure", "share"]]


class Race:
    """`polls` and `results` replace the files (for the checks); the candidate timeline and the date changes are
    read through primary_avg and primary_calendar, which the checks patch."""

    def __init__(self, cycle, party, polls=None, results=None, cache=True):
        self.cycle, self.party = cycle, party
        p = pa.polls(cycle, party) if polls is None else polls
        self._polls = {g: x for g, x in p.groupby("geo")}
        r = load_results() if results is None else results
        self._results = r[(r["cycle"] == cycle) & (r["party"] == party)]
        self.K = kernel(cycle)
        held = pc.contests(cycle, party)
        held = held[held["date"].notna() & ~held["cancelled"].fillna(False).astype(bool)]
        self.held = dict(zip(held["state"], held["date"]))             # main contests as held
        self.kind = dict(zip(held["state"], held["contest"]))
        self._avg, self._known, self._other, self._obs = {}, {}, {}, {}
        self._disk = None
        folder = os.environ.get("PRIMARY_STATE_CACHE")
        if cache and polls is None and folder:
            self._disk = Path(folder) / f"primary_state_avg_{cycle}_{party}.pkl"
            if self._disk.exists():
                self._avg = pickle.loads(self._disk.read_bytes())
        self._saved = len(self._avg)

    def save_cache(self):
        if self._disk is not None and len(self._avg) != self._saved:
            self._disk.parent.mkdir(parents=True, exist_ok=True)
            self._disk.write_bytes(pickle.dumps(self._avg))
            self._saved = len(self._avg)

    # ---- inputs as of a date

    def avg(self, place, as_of):
        """{candidate: (average, n_polls)} for a place as of a date; empty where there is none."""
        k = (place, as_of)
        if k not in self._avg:
            rows = self._polls.get(place)
            a = pa.average(self.cycle, self.party, place, as_of, poll_rows=rows) if rows is not None else []
            self._avg[k] = {c: (v, n) for c, v, n in zip(a["candidate_key"], a["avg"], a["n_polls"])} if len(a) else {}
        return self._avg[k]

    def field(self, as_of):
        """Rules 4 and 5, S9 as changed after run 1: the candidates with a live national line that day who are in
        the candidate timeline and had announced, or were exploring, by then (no date counts as announced)."""
        out = {}
        timeline = pa._timeline(self.cycle, self.party)
        for c, v in self.avg("US", as_of).items():
            t = timeline.get(c)
            if t is None:
                continue
            dates = [d for d in t[:2] if pd.notna(d)]
            if not dates or min(dates) <= as_of:
                out[c] = v
        return out

    def known(self, as_of):
        """The main contests as known on a date: {state: (date, cancelled, kind)}."""
        if as_of not in self._known:
            c = pc.contests(self.cycle, self.party, as_of)
            self._known[as_of] = {s: (d, bool(x) if pd.notna(x) else False, k) for s, d, x, k
                                  in zip(c["state"], c["date_known"], c["cancelled_known"], c["contest"])}
        return self._known[as_of]

    def result(self, state):
        """The main contest's result: ({candidate: share}, measure, winner), or None where there is no row (S20)."""
        day = self.held.get(state)
        r = self._results[(self._results["state"] == state) & (self._results["date"] == day)]
        if r["contest"].nunique() > 1:
            r = r[r["contest"].eq(self.kind[state])]
        if r.empty:
            return None
        top = r.loc[r["share"].idxmax(), "candidate_key"]
        named = r[r["candidate_key"].notna()]
        return dict(zip(named["candidate_key"], named["share"])), r["measure"].iat[0], top

    def voted(self, as_of):
        """S6, rule 9: the 50 states and DC whose main contest was held before the date, with a usable result."""
        out = []
        for s in STATES:
            day = self.held.get(s)
            if day is not None and day < as_of:
                res = self.result(s)
                if res is not None and res[1] != "unclear":            # rule 1, S20
                    out.append(s)
        return out

    def other(self, as_of):
        """Rule 6, S10: the mean other share over the voted states so far; 2 points before any result."""
        if as_of not in self._other:
            x = []
            for s in self.voted(as_of):
                field = self.field(self.held[s])
                if field:
                    shares = self.result(s)[0]
                    x.append(100 - sum(shares.get(c, 0.0) for c in field))
            self._other[as_of] = float(np.mean(x)) if x else OTHER_DEFAULT
        return self._other[as_of]

    def scaled(self, place, as_of):
        """S9, S11: a place's average on the result scale, over the field candidates it names."""
        field = self.field(as_of)
        a = {c: v for c, (v, _) in self.avg(place, as_of).items() if c in field}
        total = sum(a.values())
        if not a or total <= 0:
            return {}
        f = (100 - self.other(as_of)) / total
        return {c: v * f for c, v in a.items()}

    def standing(self, place, as_of):
        """Rule 7: r = log(state share / national share) from a place's average, both floored at 1 point."""
        nat, st = self.scaled("US", as_of), self.scaled(place, as_of)
        return {c: float(np.log(max(v, FLOOR) / max(nat[c], FLOOR))) for c, v in st.items()}

    def own(self, state, as_of):
        """Rule 11, S7: a state's own average as ({candidate: r}, {candidate: n_polls}); the last average before a
        non-binding vote where the main contest is still to come."""
        ref = as_of
        if not self.avg(state, as_of):
            first = pa.voting_day(self.cycle, self.party, state)
            if pd.isna(first) or not first < as_of:
                return {}, {}
            ref = first
        r = self.standing(state, ref)
        return r, {c: self.avg(state, ref)[c][1] for c in r}

    def observations(self, as_of):
        """Rule 9: {state: (weight, {candidate: r})} for today's field. Voted states at 1; states with a current
        average that have not voted at a half."""
        if as_of in self._obs:
            return self._obs[as_of]
        field = self.field(as_of)
        voted, obs = set(self.voted(as_of)), {}
        for s in STATES:
            if s in voted:
                day = self.held[s]
                nat, shares = self.scaled("US", day), self.result(s)[0]
                r = {c: float(np.log(max(shares[c], FLOOR) / max(nat[c], FLOOR)))
                     for c in field if c in shares and c in nat}       # S1, S12
                w = 1.0
            elif self.held.get(s) is None or self.held[s] >= as_of:
                r = {c: v for c, v in self.standing(s, as_of).items() if c in field} if self.avg(s, as_of) else {}
                w = POLLED_WEIGHT                                      # S7: a current average only
            else:
                r = {}
            if r:
                obs[s] = (w, r)
        self._obs[as_of] = obs
        return obs

    # ---- rule 10's pieces

    def components(self, as_of, only=None):
        """One row per contest still to come (as known on the date) and field candidate: the national share on the
        result scale, the level, W, the kernel-weighted mean of the pattern, the state's own r and n."""
        as_of = pd.Timestamp(as_of)
        field = sorted(self.field(as_of))
        if not field:
            return pd.DataFrame()
        nat, other, obs = self.scaled("US", as_of), self.other(as_of), self.observations(as_of)
        rows = []
        for state, (day, cancelled, kind) in self.known(as_of).items():
            if only is not None and state not in only:
                continue
            held = self.held.get(state)
            if cancelled or pd.isna(day) or (held is not None and held < as_of):   # S5, S6
                continue
            if day < as_of:                                             # S26: its date as known has passed
                continue
            own_r, own_n = self.own(state, as_of)
            in51 = state in self.K.index
            use = [t for t in obs if t != state]                        # rule 11: not its own average
            for c in field:
                level = W = pm = 0.0
                if in51:
                    t = [x for x in use if c in obs[x][1]]
                    if t:
                        w = np.array([obs[x][0] for x in t])
                        r = np.array([obs[x][1][c] for x in t])
                        level = float(np.average(r, weights=w))
                        kw = self.K.loc[state, t].to_numpy() * w
                        W = float(kw.sum())
                        pm = float((kw * (r - level)).sum() / W)
                rows.append(dict(cycle=self.cycle, party=self.party, as_of=as_of, state=state, date_known=day,
                                 days=max((day - as_of).days, 1), caucus=kind in ("caucus", "convention"),
                                 polled=bool(own_r), in51=in51, other=other, candidate_key=c, nat=nat[c],
                                 level=level, W=W, pattern=pm, own_r=own_r.get(c, np.nan), own_n=own_n.get(c, 0)))
        out = pd.DataFrame(rows)
        return out.sort_values(["date_known", "state", "candidate_key"], kind="stable").reset_index(drop=True) \
            if len(out) else out

    # ---- draws and the table (rules 13, 17)

    def standard_draws(self, as_of, n_candidates):
        """S16, S17: the standard draws for a forecast date, the same whatever is forecast from them. National: one
        per candidate. State: per candidate, correlated across the 50 states and DC by the kernel. Territories:
        independent, drawn as wanted from their own stream."""
        rng = np.random.default_rng([SEED, self.cycle, int(self.party == "R"), pd.Timestamp(as_of).toordinal()])
        z = rng.standard_normal((N_DRAWS, n_candidates), dtype=np.float32)
        L = np.linalg.cholesky(self.K.to_numpy() + 1e-9 * np.eye(len(STATES))).astype(np.float32)
        e = np.einsum("st,ntc->nsc", L, rng.standard_normal((N_DRAWS, len(STATES), n_candidates), dtype=np.float32))
        return z, e

    def territory_draws(self, as_of, state, n_candidates):
        code = [ord(ch) for ch in state]
        rng = np.random.default_rng([SEED, self.cycle, int(self.party == "R"), pd.Timestamp(as_of).toordinal(), *code])
        return rng.standard_normal((N_DRAWS, n_candidates), dtype=np.float32)

    def draws(self, as_of, values, comp=None):
        """(contests, candidates, shares): shares[draw, contest, candidate] in points, contests in calendar order.
        `values` is a dict of the six values."""
        comp = self.components(as_of) if comp is None else comp
        if comp.empty:
            return [], [], np.empty((N_DRAWS, 0, 0), dtype=np.float32)
        comp = comp.assign(share=shares(comp, values["beta"], values["kappa"], values["lambda"]))
        cands = sorted(comp["candidate_key"].unique())
        z, e = self.standard_draws(as_of, len(cands))
        contests, out = [], []
        for state, g in comp.groupby("state", sort=False):
            g = g.set_index("candidate_key").loc[cands]
            first = g.iloc[0]
            sd = (values["sigma_p"] if first["polled"] else values["sigma_u"]) * (CAUCUS if first["caucus"] else 1.0)
            es = e[:, STATES.index(state), :] if first["in51"] else self.territory_draws(as_of, state, len(cands))
            x = np.log(g["share"].to_numpy(dtype=np.float32)) \
                + np.float32(values["tau"] * np.sqrt(first["days"] / 30)) * z + np.float32(sd) * es
            x = np.exp(x - x.max(axis=1, keepdims=True))
            out.append(x / x.sum(axis=1, keepdims=True) * np.float32(100 - first["other"]))
            contests.append(state)
        return contests, cands, np.stack(out, axis=1)

    def forecast(self, as_of, values, only=None):
        """Rule 17: one row per contest and field candidate."""
        comp = self.components(as_of)
        if comp.empty:
            return comp
        contests, cands, d = self.draws(as_of, values, comp)
        comp = comp.assign(share=shares(comp, values["beta"], values["kappa"], values["lambda"]))
        top = d.max(axis=2, keepdims=True)
        win = ((d == top) / (d == top).sum(axis=2, keepdims=True)).mean(axis=0)      # S18: a tie is split
        lo, hi = np.percentile(d, [10, 90], axis=0)
        ix = pd.MultiIndex.from_product([contests, cands], names=["state", "candidate_key"])
        s = pd.DataFrame(dict(p10=lo.ravel(), p90=hi.ravel(), win=win.ravel()), index=ix).reset_index()
        out = comp.merge(s, on=["state", "candidate_key"])
        if only is not None:
            out = out[out["state"].isin(only)]
        return out[["cycle", "party", "as_of", "state", "date_known", "days", "caucus", "polled", "W", "other",
                    "candidate_key", "share", "p10", "p90", "win"]]


# ---------------------------------------------------------------- rules 10 to 12 for any point values

def shares(comp, beta, kappa, lam):
    """Expected shares, in points, for components() rows."""
    W, n = comp["W"].to_numpy(), comp["own_n"].to_numpy(dtype=float)
    shrink = np.zeros(len(comp)) if np.isinf(kappa) else np.divide(W, W + kappa, out=np.zeros(len(comp)), where=W > 0)
    prior = np.where(comp["in51"], beta * comp["level"] + shrink * comp["pattern"], 0.0)
    has = comp["own_r"].notna().to_numpy()
    w = np.zeros(len(comp)) if np.isinf(lam) else np.divide(n, n + lam, out=np.zeros(len(comp)), where=n > 0)
    w = np.where(has, w, 0.0)                                           # S13
    raw = comp["nat"].to_numpy() * np.exp(w * comp["own_r"].fillna(0.0).to_numpy() + (1 - w) * prior)
    key = [comp[c] for c in ("cycle", "party", "as_of", "state")]
    return raw * (100 - comp["other"].to_numpy()) / pd.Series(raw).groupby([k.to_numpy() for k in key]).transform("sum").to_numpy()


# ---------------------------------------------------------------- fitting (rule 16)

def scored_set(races):
    """The forecasts rule 16 scores: every main contest of the open contests in the 50 states and DC with a usable
    result, on the days 30 and 7 before it and on its own day. Returns the components (with `actual`, `winner`,
    `horizon`) and the count of contests left out for want of a result."""
    frames, no_result = [], []
    for (cycle, party), race in races.items():
        for state in STATES:
            day = race.held.get(state)
            if day is None:
                continue
            res = race.result(state)
            if res is None or res[1] == "unclear":
                no_result.append((cycle, party, state, "no result row" if res is None else "measure unclear"))
                continue
            actual, _, winner = res
            for h in SCORED:
                c = race.components(day - pd.Timedelta(days=h), only=[state])
                if c.empty:
                    continue
                c["horizon"], c["actual"] = h, c["candidate_key"].map(actual).fillna(0.0)
                c["winner"] = winner
                frames.append(c)
        race.save_cache()
    return pd.concat(frames, ignore_index=True), no_result


def point_losses(sc):
    """Mean squared error of candidate shares for every point of the grid: [contest, point], each contest's dates
    weighted equally (rule 16)."""
    fk = ["cycle", "party", "state", "horizon"]
    fid = sc.groupby(fk, sort=False).ngroup().to_numpy()
    grid = [(b, k, lam) for b in GRID_BETA for k in GRID_KAPPA for lam in GRID_LAMBDA]
    per = np.empty((fid.max() + 1, len(grid)))
    for j, (b, k, lam) in enumerate(grid):
        err = (shares(sc, b, k, lam) - sc["actual"].to_numpy()) ** 2
        per[:, j] = np.bincount(fid, err) / np.bincount(fid)
    f = sc.drop_duplicates(fk)[fk].reset_index(drop=True)
    return grid, _by_contest(f, per)


def _by_contest(f, per):
    """Forecast-level losses to contest level: the mean over each contest's scored dates."""
    cid = f.groupby(["cycle", "party", "state"], sort=False).ngroup().to_numpy()
    out = np.stack([per[cid == i].mean(axis=0) for i in range(cid.max() + 1)])
    return f.drop_duplicates(["cycle", "party", "state"])[["cycle", "party", "state"]].reset_index(drop=True), out


def win_chances(races, sc, points):
    """The winner's chance in every scored forecast, for each point setting and every (tau, sigma) pair, from the
    forecast date's own standard draws. Returns {point: array [forecast, tau, sigma]} where sigma runs over the
    grid that applies (polled or unpolled), and the forecast key frame."""
    fk = ["cycle", "party", "state", "horizon"]
    f = sc.drop_duplicates(fk)[fk + ["as_of", "polled"]].reset_index(drop=True)
    pos = {tuple(r): i for i, r in enumerate(f[fk].itertuples(index=False, name=None))}
    out = {p: np.full((len(f), len(GRID_TAU), len(GRID_SIGMA_P)), np.nan) for p in points}
    mu = {p: shares(sc, *p) for p in points}
    for (cycle, party, as_of), idx in sc.groupby(["cycle", "party", "as_of"], sort=False).indices.items():
        race, g = races[(cycle, party)], sc.iloc[idx]
        cands = sorted(g["candidate_key"].unique())
        z, e = race.standard_draws(as_of, len(cands))
        for (state, h), gi in g.groupby(["state", "horizon"], sort=False).indices.items():
            rows = g.iloc[gi].set_index("candidate_key").loc[cands]
            first = rows.iloc[0]
            es = e[:, STATES.index(state), :]
            mult = CAUCUS if first["caucus"] else 1.0
            sig = GRID_SIGMA_P if first["polled"] else GRID_SIGMA_U
            win = cands.index(first["winner"]) if first["winner"] in cands else None
            i = pos[(cycle, party, state, h)]
            order = idx[gi][np.argsort(g.iloc[gi]["candidate_key"].to_numpy(), kind="stable")]
            for p in points:
                if win is None:                                         # S19
                    out[p][i] = 0.0
                    continue
                lm = np.log(mu[p][order]).astype(np.float32)
                for a, tau in enumerate(GRID_TAU):
                    base = lm + np.float32(tau * np.sqrt(first["days"] / 30)) * z
                    for b, s in enumerate(sig):
                        out[p][i, a, b] = float(((base + np.float32(s * mult) * es).argmax(axis=1) == win).mean())
    return f, out


def spread_losses(f, chance):
    """Log loss of the winner for every (tau, sigma_p, sigma_u): [contest, point]."""
    ll = -np.log(np.maximum(chance, P_FLOOR))                           # [forecast, tau, sigma]
    polled = f["polled"].to_numpy()[:, None, None, None]
    full = np.where(polled, ll[:, :, :, None], ll[:, :, None, :])       # [forecast, tau, sigma_p, sigma_u]
    grid = [(t, p, u) for t in GRID_TAU for p in GRID_SIGMA_P for u in GRID_SIGMA_U]
    return grid, _by_contest(f, full.reshape(len(f), -1))


def _argmin(loss, keep):
    """The first grid point with the least mean loss over the kept contests (ties: grid order, S4)."""
    m = loss[keep].mean(axis=0)
    j = int(np.argmin(m))
    return j, float(m[j])


def _edges(point, spread):
    """The fitted values that sit on an end of their grid (S4). The baseline's point values are not fitted."""
    fitted = [("tau", GRID_TAU, spread[0]), ("sigma_p", GRID_SIGMA_P, spread[1]), ("sigma_u", GRID_SIGMA_U, spread[2])]
    if point is not None:
        fitted = [("beta", GRID_BETA, point[0]), ("kappa", GRID_KAPPA, point[1]), ("lambda", GRID_LAMBDA, point[2])] \
            + fitted
    return " ".join(n for n, g, v in fitted if v in (g[0], g[-1]))


def fit(races=None, results=None):
    """Rule 16. Returns (values, scored set): one row per model (state model, baseline) and fold (each open contest
    left out, and all seven)."""
    races = races or {k: Race(*k, results=results) for k in OPEN}
    sc, no_result = scored_set(races)
    pgrid, (contests, ploss) = point_losses(sc)
    folds = [k for k in OPEN] + ["all"]
    keep = {k: ~((contests["cycle"] == k[0]) & (contests["party"] == k[1])).to_numpy() if k != "all"
            else np.ones(len(contests), bool) for k in folds}
    fitted = {k: _argmin(ploss, keep[k]) for k in folds}
    points = sorted({pgrid[j] for j, _ in fitted.values()} | {BASELINE_POINT})
    f, chance = win_chances(races, sc, points)
    rows = []
    for model in ("state_model", "baseline"):
        for k in folds:
            j, mse = fitted[k]
            point = pgrid[j] if model == "state_model" else BASELINE_POINT
            if model == "baseline":
                mse = float(ploss[keep[k], pgrid.index(BASELINE_POINT)].mean())
            sgrid, (_, sloss) = spread_losses(f, chance[point])
            js, ll = _argmin(sloss, keep[k])
            rows.append(dict(model=model, left_out="all" if k == "all" else f"{k[0]} {k[1]}",
                             beta=point[0], kappa=point[1], **{"lambda": point[2]}, tau=sgrid[js][0],
                             sigma_p=sgrid[js][1], sigma_u=sgrid[js][2], fit_mse=mse, fit_log_loss=ll,
                             contests_fitted=int(keep[k].sum()),
                             on_grid_edge=_edges(point if model == "state_model" else None, sgrid[js])))
    return pd.DataFrame(rows), sc, no_result


# ---------------------------------------------------------------- outputs (rule 17; S21)

def values_for(values, model, cycle, party):
    """S21: an open contest's forecasts use the values fitted without it; the incumbents' use all seven."""
    key = f"{cycle} {party}" if (cycle, party) in pa.OPEN else "all"
    return values[(values["model"] == model) & (values["left_out"] == key)].iloc[0]


def forecast_dates(race):
    """Rule 3, S5, S6: {date: None (every contest still to come) or the set of contests forecast that day}."""
    ev = pc.events(race.cycle, race.party)
    ev = ev[ev["flag"].isin(pc.VOTE_FLAGS) & ~ev["cancelled"].astype(bool) & ev["date"].notna()]
    dates = {d: None for d in sorted(ev["date"].unique())}
    for state, day in race.held.items():
        for h in (30, 7):
            d = day - pd.Timedelta(days=h)
            if d not in dates:
                dates[d] = {state}
            elif dates[d] is not None:
                dates[d].add(state)
    return dict(sorted(dates.items()))


def build():
    races = {k: Race(*k) for k in pa.CYCLES}
    values, sc, no_result = fit({k: races[k] for k in OPEN})
    fmt = dict(index=False, date_format="%Y-%m-%d")
    values.to_csv(OUT / "primary_state_values.csv", float_format="%.4f", **fmt)
    print(values.to_string(index=False))
    print(f"scored: {sc.groupby(['cycle', 'party', 'state']).ngroups} contests, "
          f"{sc.groupby(['cycle', 'party', 'state', 'horizon']).ngroups} forecasts; left out: {no_result}")
    out = []
    for (cycle, party), race in races.items():
        print(cycle, party, flush=True)
        for model in ("state_model", "baseline"):
            v = values_for(values, model, cycle, party)
            for d, only in forecast_dates(race).items():
                fc = race.forecast(d, v.to_dict(), only)
                if len(fc):
                    out.append(fc.assign(model=model, values=v["left_out"]))
        race.save_cache()
    out = pd.concat(out, ignore_index=True)
    for col, places in (("W", 2), ("other", 2), ("share", 2), ("p10", 2), ("p90", 2), ("win", 4)):
        out[col] = out[col].astype(float).round(places)
    out.to_csv(OUT / "primary_state_forecasts.csv", **fmt)
    print(len(out), "forecast rows")


if __name__ == "__main__":
    build()
