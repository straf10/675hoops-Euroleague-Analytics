"""A small synthetic EuroLeague world for the M6 harness (weeks 16-18 L6).

Reused by ``test_m6_backtest.py`` and the leakage suite: ``build_inputs`` returns an
``M6Inputs`` (``seed`` fixes every random draw), ``small_spec`` the matching ``M6Backtest`` and
``synthetic_rounds`` the injectable ``rounds`` callable of ``run_m6_backtest``. The module-level
``linear_spm`` is the known SPM the world plants.

The world. Eight EuroLeague teams (``E01``...) play ``LEGS`` legs of a round robin each season
(28 weekly rounds, tip-offs 15 minutes apart within a round), plus one playoff game (phase ``PO``)
with absurd box lines that a regular-season-only harness must ignore. Rosters hold 19 players;
careers last 2-8 seasons. Each player has latent log-rate offsets, a random walk of true talent
(``DRIFT_SD`` per season on the log scale of the counts, ``PCT_DRIFT_SD`` on the logit of the
percentages) and a planted aging curve: the log rate of a count is
``scale_k * strength * -0.006 * (age - 26)^2`` (``AGING_SCALE``), so players decline after 26
(``aging_strength`` 0 plants none). Box lines are drawn from the true rates: Poisson counts per
100 possessions, binomial makes; possessions = team possessions x seconds / 2400.

Impact. ``linear_spm`` is the known SPM: a linear function of the per-100 rates (``SPM_COEF``).
A player-season's BRAPM snapshot (from ``brapm_from``) is the SPM of his true rates plus a
persistent player effect plus noise with sd ``BRAPM_SD * sqrt(1000 / poss)``.

Ages are synthetic (age at 1 October = ``offset + season``). Source ids: ``P000001``...; the
person id is ``P:P000001``.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.config import M6Backtest
from eurohoops.eval.m6_backtest import M6Inputs
from eurohoops.models.player_seasons import COUNT_COLUMNS

COMPETITION = "euroleague"
N_TEAMS = 8
ROSTER = 19
TEAM_POSS = 72.0
LEGS = 4
SEASONS = tuple(range(2010, 2020))
DRIFT_SD = 0.04
PCT_DRIFT_SD = 0.06
# EuroLeague league means per 100 possessions, and the sd of the player offsets on the log scale.
MU = {
    "fg2a": 22.0,
    "fg3a": 9.0,
    "fta": 8.0,
    "ast": 6.0,
    "tov": 4.5,
    "oreb": 3.0,
    "dreb": 8.0,
    "stl": 2.0,
    "blk": 1.0,
    "pf": 5.0,
}
OFFSET_SD = 0.3
P_MEAN = {"fg2": 0.5, "fg3": 0.35, "ft": 0.75}
P_SD = {"fg2": 0.25, "fg3": 0.3, "ft": 0.35}  # on the logit scale
AGING_SCALE = {
    "fg2a": 1.0,
    "fg3a": 1.0,
    "fta": 0.5,
    "ast": 0.5,
    "tov": -0.5,
    "oreb": 0.5,
    "dreb": 0.0,
    "stl": 1.0,
    "blk": 0.5,
    "pf": 0.0,
}
SPM_COEF = {
    "pts": 0.05,
    "fta": 0.02,
    "ast": 0.08,
    "oreb": 0.06,
    "dreb": 0.04,
    "stl": 0.15,
    "blk": 0.08,
    "tov": -0.12,
}
SPM_INTERCEPT = -3.0
BRAPM_SD = 2.5
BRAPM_EFFECT_SD = 0.8


def linear_spm(frame: pd.DataFrame, before_season: int) -> "pd.Series[float]":
    """The planted SPM of ``spm_frame`` rows: ``SPM_INTERCEPT`` plus ``SPM_COEF`` times the
    per-100 rates; it does not depend on ``before_season``."""
    value = np.full(len(frame), SPM_INTERCEPT)
    for stat, coef in SPM_COEF.items():
        value = value + coef * frame[stat].to_numpy(dtype=np.float64)
    return pd.Series(value, index=frame.index)


def small_spec() -> M6Backtest:
    """Two tuning seasons, one validation, two test and one checkpoint."""
    return M6Backtest(
        report=Path("unused.json"),
        players_report=Path("unused.csv"),
        tuning=(2015, 2016),
        validation=(2017,),
        test=(2018, 2019),
        half_lives=(1.0, 2.0, 3.0),
        checkpoints=(0.5,),
        bootstrap_resamples=200,
    )


def synthetic_rounds(competition: str, season: int) -> int:
    """R of the synthetic format: ``LEGS`` legs of the round robin."""
    return LEGS * (N_TEAMS - 1)


def team_codes(competition: str = COMPETITION) -> tuple[str, ...]:
    return tuple(f"E{i:02d}" for i in range(1, N_TEAMS + 1))


def _legs(teams: tuple[str, ...]) -> list[list[tuple[str, str]]]:
    """The rounds of ``LEGS`` legs of a round robin by the circle method; every team plays once
    per round and the venue alternates between legs."""
    rotation = list(teams)
    half = len(teams) // 2
    first = []
    for r in range(len(teams) - 1):
        pairs = [(rotation[i], rotation[-1 - i]) for i in range(half)]
        first.append(pairs if r % 2 == 0 else [(b, a) for a, b in pairs])
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
    swapped = [[(b, a) for a, b in pairs] for pairs in first]
    legs = [first, swapped] * (LEGS // 2)
    return [round_ for leg in legs for round_ in leg]


def _schedule(season: int, *, playoff: bool) -> pd.DataFrame:
    """The season's games: regular season rounds, then optionally one playoff game."""
    start = pd.Timestamp(f"{season}-10-01T18:00:00Z")
    teams = team_codes()
    rows = []
    for r, pairs in enumerate(_legs(teams), start=1):
        for slot, (home, away) in enumerate(pairs):
            rows.append(
                (r, "RS", start + pd.Timedelta(days=7 * (r - 1), minutes=15 * slot), home, away)
            )
    if playoff:
        last = len(_legs(teams)) + 1
        rows.append((last, "PO", start + pd.Timedelta(days=7 * last), teams[0], teams[1]))
    frame = pd.DataFrame(rows, columns=["round", "phase", "tipoff_utc", "home", "away"])
    frame["game_code"] = np.arange(1, len(frame) + 1)
    frame["game_id"] = [f"E{season}_{c}" for c in frame["game_code"]]
    frame["season"] = season
    frame["played"] = True
    frame["tipoff_utc"] = pd.to_datetime(frame["tipoff_utc"], utc=True)
    return frame[
        ["game_id", "season", "game_code", "phase", "round", "tipoff_utc", "home", "away", "played"]
    ]


@dataclass
class _Person:
    """A synthetic player: latent log-rate offsets ``z``, the random-walk state ``walk`` (both
    per count stat and, on the logit scale, per percentage), age offset and base minutes."""

    league: str
    offset: float
    left: int
    minutes: float
    z: dict[str, float]
    walk: dict[str, float]


def _entrant(rng: np.random.Generator, season: int) -> _Person:
    return _Person(
        league=COMPETITION,
        offset=float(rng.uniform(19.0, 31.0)) - season,
        left=int(rng.integers(2, 9)),
        minutes=float(rng.uniform(10.0, 32.0)),
        z={
            **{k: float(rng.normal(0.0, OFFSET_SD)) for k in MU},
            **{k: float(rng.normal(0.0, P_SD[k])) for k in P_SD},
        },
        walk=dict.fromkeys([*MU, *P_SD], 0.0),
    )


def _population(rng: np.random.Generator, seasons: tuple[int, ...]) -> pd.DataFrame:
    """One row per (player, season, team): the rosters of every season with the player's latent
    offsets (``z_*``), age offset (age = offset + season), base minutes and random-walk state
    (``walk_*``) at that season."""
    people: list[_Person] = []
    active: list[int] = []
    rows = []
    teams = team_codes()
    for season in seasons:
        roster = rng.permutation(active).tolist()[: N_TEAMS * ROSTER]
        while len(roster) < N_TEAMS * ROSTER:
            people.append(_entrant(rng, season))
            roster.append(len(people) - 1)
        active = []
        for i, pid in enumerate(rng.permutation(roster).tolist()):
            person = people[pid]
            for k in person.walk:
                person.walk[k] += float(rng.normal(0.0, DRIFT_SD if k in MU else PCT_DRIFT_SD))
            rows.append(
                {
                    "pid": pid,
                    "season": season,
                    "competition": COMPETITION,
                    "team": teams[i % len(teams)],
                    "offset": person.offset,
                    "minutes": person.minutes,
                    **{f"z_{k}": v for k, v in person.z.items()},
                    **{f"walk_{k}": v for k, v in person.walk.items()},
                }
            )
            person.left -= 1
            if person.left > 0:
                active.append(pid)
    return pd.DataFrame(rows)


def _true_rates(pop: pd.DataFrame, aging_strength: float) -> pd.DataFrame:
    """The true per-100 rates and percentages of each roster row."""
    age = pop["offset"].to_numpy() + pop["season"].to_numpy()
    curve = -0.006 * (age - 26.0) ** 2 * aging_strength
    out = pop[["pid", "season", "competition", "team"]].copy()
    for k, mu in MU.items():
        out[k] = mu * np.exp(pop[f"z_{k}"] + pop[f"walk_{k}"] + AGING_SCALE[k] * curve)
    for k, mean in P_MEAN.items():
        logit = np.log(mean / (1.0 - mean)) + pop[f"z_{k}"] + pop[f"walk_{k}"]
        out[k] = 1.0 / (1.0 + np.exp(-logit))
    out["pts"] = (
        2.0 * out["fg2a"] * out["fg2"] + 3.0 * out["fg3a"] * out["fg3"] + out["fta"] * out["ft"]
    )
    return out


def _lines(
    rng: np.random.Generator, rates: pd.DataFrame, pop: pd.DataFrame, schedule: pd.DataFrame
) -> pd.DataFrame:
    """The player lines of the regular-season games: every roster row against its team's games."""
    roster = rates.assign(minutes=pop["minutes"].to_numpy())
    sides = pd.concat(
        [
            schedule.rename(columns={"home": "team"})[["game_id", "season", "team", "phase"]],
            schedule.rename(columns={"away": "team"})[["game_id", "season", "team", "phase"]],
        ]
    )
    lines = roster.merge(sides, on=["season", "team"])
    lines = lines[lines["phase"] == "RS"].reset_index(drop=True)
    n = len(lines)
    sec = np.rint(lines["minutes"].to_numpy() * 60.0 * rng.uniform(0.85, 1.15, n)).astype("int64")
    sec[rng.random(n) < 0.04] = 0  # did not play
    lines["sec"] = sec
    poss = TEAM_POSS * sec / 2400.0
    lines["poss"] = poss

    def poisson(rate: str) -> np.ndarray:
        return rng.poisson(lines[rate].to_numpy() * poss / 100.0).astype("int64")

    fg2a, fg3a, fta = poisson("fg2a"), poisson("fg3a"), poisson("fta")
    fg2m = rng.binomial(fg2a, lines["fg2"].to_numpy()).astype("int64")
    fg3m = rng.binomial(fg3a, lines["fg3"].to_numpy()).astype("int64")
    ftm = rng.binomial(fta, lines["ft"].to_numpy()).astype("int64")
    counts = {
        "pts": 2 * fg2m + 3 * fg3m + ftm,
        "fg2m": fg2m,
        "fg2a": fg2a,
        "fg3m": fg3m,
        "fg3a": fg3a,
        "ftm": ftm,
        "fta": fta,
        **{k: poisson(k) for k in ("oreb", "dreb", "ast", "stl", "blk", "tov", "pf")},
    }
    for column in COUNT_COLUMNS:
        lines[column] = counts[column]
    return lines


def _playoff_lines(season: int, schedule: pd.DataFrame, rosters: pd.DataFrame) -> pd.DataFrame:
    """Absurd lines of the playoff game: a harness that reads them is wrong by a mile."""
    game = schedule[schedule["phase"] == "PO"].iloc[0]
    rows = rosters[
        (rosters["season"] == season)
        & (rosters["competition"] == COMPETITION)
        & rosters["team"].isin([game["home"], game["away"]])
    ].copy()
    rows["game_id"] = game["game_id"]
    rows["sec"] = 1500
    rows["poss"] = 45.0
    for column in COUNT_COLUMNS:
        rows[column] = 40
    return rows


def build_inputs(
    *,
    seasons: tuple[int, ...] = SEASONS,
    seed: int = 0,
    aging_strength: float = 1.0,
    brapm_from: int = 2012,
    playoffs: bool = True,
) -> M6Inputs:
    """The synthetic world of the module docstring, deterministic in ``seed``."""
    rng = np.random.default_rng(seed)
    pop = _population(rng, seasons)
    rates = _true_rates(pop, aging_strength)
    schedule = pd.concat([_schedule(s, playoff=playoffs) for s in seasons], ignore_index=True)
    regular = _lines(rng, rates, pop, schedule)
    lines = regular
    if playoffs:
        extra = pd.concat([_playoff_lines(s, schedule, rates) for s in seasons])
        lines = pd.concat([lines, extra], ignore_index=True)
    lines["player_id"] = [f"P{p:06d}" for p in lines["pid"]]
    player_games = {
        COMPETITION: lines[
            ["season", "game_id", "team", "player_id", "sec", "poss", *COUNT_COLUMNS]
        ].reset_index(drop=True)
    }
    return M6Inputs(
        games={COMPETITION: schedule},
        player_games=player_games,
        xwalk=_xwalk(pop),
        ages=_ages(pop),
        brapm=_brapm(rng, rates, pop, regular, brapm_from),
        spm=linear_spm,
    )


def _xwalk(pop: pd.DataFrame) -> pd.DataFrame:
    """One crosswalk row per source id."""
    rows = [(COMPETITION, f"P{pid:06d}", f"P:P{pid:06d}") for pid in sorted(set(pop["pid"]))]
    return pd.DataFrame(rows, columns=["competition", "source_id", "person_id"])


def _ages(pop: pd.DataFrame) -> pd.DataFrame:
    ages = pd.DataFrame(
        {
            "person_id": pop["pid"].map(lambda pid: f"P:P{pid:06d}").to_numpy(),
            "season": pop["season"].astype("int64").to_numpy(),
            "age": (pop["offset"] + pop["season"]).round(3).to_numpy(),
        }
    )
    return ages.drop_duplicates(["person_id", "season"]).reset_index(drop=True)


def _brapm(
    rng: np.random.Generator,
    rates: pd.DataFrame,
    pop: pd.DataFrame,
    lines: pd.DataFrame,
    brapm_from: int,
) -> pd.DataFrame:
    """Season-end BRAPM snapshots of the EuroLeague player-seasons: the planted SPM of the true
    rates, a persistent player effect and noise shrinking with the regular-season possessions."""
    el = rates[rates["season"] >= brapm_from]
    poss = lines[lines["sec"] > 0].groupby(["pid", "season"])["poss"].sum()
    exposure = pd.Series(
        [poss.get((p, s), 0.0) for p, s in zip(el["pid"], el["season"], strict=True)],
        index=el.index,
    )
    keep = (exposure > 0).to_numpy()
    el, exposure = el[keep], exposure[keep]
    effect = {pid: float(rng.normal(0.0, BRAPM_EFFECT_SD)) for pid in sorted(set(pop["pid"]))}
    truth = linear_spm(el, 0).to_numpy()
    sd = BRAPM_SD * np.sqrt(1000.0 / exposure.to_numpy())
    value = truth + el["pid"].map(effect).to_numpy() + rng.normal(0.0, 1.0, len(el)) * sd
    return pd.DataFrame(
        {
            "person_id": el["pid"].map(lambda pid: f"P:P{pid:06d}").to_numpy(),
            "competition": COMPETITION,
            "season": el["season"].astype("int64").to_numpy(),
            "stat": "brapm",
            "value": value,
            "sd": sd,
        }
    )
