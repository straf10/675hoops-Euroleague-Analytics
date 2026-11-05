"""The inputs the models read: the DuckDB marts, the raw box-score cache and the committed reports.

Both CLI commands (``backtest`` and the live ones) load through here. A missing or unusable
input raises ``InputsMissing``, whose message names it and the command that makes it; the CLI
decides what that means (exit 1, or a shadow model that sits the run out).
"""

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.config import (
    EUROLEAGUE,
    LIVE_SEASON,
    M2_REPORT,
    M3,
    M3_PLAYERS_REPORT,
    M7,
    M7_V2,
    MART_PATH,
    PLAYER_BIOS,
    PLAYER_XWALK_FILE,
    Competition,
    M5Backtest,
    M6Backtest,
    M7Backtest,
)
from eurohoops.eval.el_spm import ElSpm, choose_model, el_spm_models
from eurohoops.eval.m5_backtest import M5Inputs
from eurohoops.eval.m6_backtest import M6Inputs, SpmFn
from eurohoops.eval.m7_backtest import M7Inputs
from eurohoops.live_sim import LiveSim, load_sim
from eurohoops.marts import read_games, read_table
from eurohoops.models.box_impact import STAT_COLUMNS
from eurohoops.models.player_part import ElPlayerRatings, PlayerPartError, el_player_ratings
from eurohoops.models.player_seasons import (
    AGES_SCHEMA,
    build_player_seasons,
    person_ids,
    player_ages,
    read_xwalk_file,
)
from eurohoops.parse.schemas import validated
from eurohoops.sim.played import regulation_scores
from eurohoops.stats.box import build_box_games


class InputsMissing(Exception):
    """A model input is missing or unusable; the message names it and how to make it."""


def _m1_report(comp: Competition) -> dict[str, Any]:
    if comp.m1 is None or not comp.m1.report.exists():
        raise InputsMissing(
            f"no committed M1 report for {comp.name}; run: eurohoops backtest --model m1"
        )
    report: dict[str, Any] = json.loads(comp.m1.report.read_text(encoding="utf-8"))
    return report


def _team_games(comp: Competition, games: pd.DataFrame) -> pd.DataFrame:
    """The ``team_games`` mart rows of ``games``."""
    team_games = read_table(MART_PATH, "team_games", comp.name)
    if team_games is None:
        raise InputsMissing("no team_games in the marts; run: eurohoops build")
    return team_games[team_games["game_id"].isin(set(games["game_id"]))].reset_index(drop=True)


def m5_inputs(comp: Competition, spec: M5Backtest) -> tuple[M5Inputs, pd.DataFrame]:
    """M5's inputs for ``comp``: every game up to the last test season (the live season never
    enters, so the daily log cannot move the report), M1's committed parameters and comparison
    Elo. Also returns the backtest frame (M3's order)."""
    m1_report = _m1_report(comp)
    last = spec.test[-1]
    games = read_games(MART_PATH, comp.name)
    games = games[games["season"] <= last].reset_index(drop=True)
    team_games = _team_games(comp, games)
    player_games = build_box_games(comp.raw_dir, games).players
    inputs = M5Inputs(
        games=games,
        team_games=team_games,
        player_games=player_games,
        tuned_m1=m1_report["tuned"],
        elo=m1_report["comparison_elo"],
    )
    frame = (
        games[games["season"].between(spec.warmup[0], last)]
        .sort_values("tipoff_utc")
        .reset_index(drop=True)
    )
    return inputs, frame


def m5_player_ratings(inputs: M5Inputs, frame: pd.DataFrame) -> ElPlayerRatings:
    """M3's committed ``rapm_spm`` (``reports/backtest_m3.json`` ``chosen``, never re-tuned),
    fitted walk-forward once over ``frame``."""
    try:
        return el_player_ratings(
            frame, inputs.player_games, inputs.team_games, m3_report=M3.report, mart_path=MART_PATH
        )
    except PlayerPartError as error:
        raise InputsMissing(str(error)) from error


def m7_inputs(comp: Competition, spec: M7Backtest, seasons: tuple[int, ...]) -> M7Inputs:
    """M7's inputs for ``comp``: every game up to the last test season (the live season never
    enters, so the daily log cannot move the report), M1's committed parameters and comparison
    Elo, and the EuroLeague's regulation scores of the scored regular seasons."""
    m1_report = _m1_report(comp)
    games = read_games(MART_PATH, comp.name)
    games = games[games["season"] <= spec.test[-1]].reset_index(drop=True)
    team_games = _team_games(comp, games)
    scored = games[(games["phase"] == "RS") & games["season"].isin(seasons)]
    return M7Inputs(
        competition=comp.name,
        games=games,
        team_games=team_games,
        regulation=regulation_scores(comp.raw_dir, scored),
        tuned_m1=m1_report["tuned"],
        elo=m1_report["comparison_elo"],
    )


@dataclass(frozen=True)
class SimInputs:
    """The live season simulation's inputs: M7's verdict, the games up to the live season, their
    team games and M1's committed parameters."""

    model: LiveSim
    games: pd.DataFrame
    team_games: pd.DataFrame
    tuned_m1: dict[str, Any]


def sim_inputs(comp: Competition, season: int) -> SimInputs:
    """The live simulation's inputs for ``comp`` up to ``season``; the gate verdict counts gate v2
    (``live_sim.load_sim``)."""
    model = load_sim(M7.report, M7_V2.report)
    if comp.m1 is None or model is None or not comp.m1.report.exists():
        raise InputsMissing("no committed M7 or M1 report; run: eurohoops backtest --model m7")
    games = read_games(MART_PATH, comp.name)
    games = games[games["season"] <= season].reset_index(drop=True)
    team_games = read_table(MART_PATH, "team_games", comp.name)
    if team_games is None:
        raise InputsMissing("no team_games in the marts; run: eurohoops build")
    tuned = json.loads(comp.m1.report.read_text(encoding="utf-8"))["tuned"]
    return SimInputs(model, games, team_games, tuned)


def _m6_brapm(xwalk: pd.DataFrame) -> pd.DataFrame:
    """The season-end BRAPM snapshots of ``reports/m3_players.json`` as ``IMPACT_SCHEMA`` rows
    (``total`` and ``sd_total`` of the players the snapshot saw, mapped to persons)."""
    report = json.loads(M3_PLAYERS_REPORT.read_text(encoding="utf-8"))
    frames = []
    for season, block in report["seasons"].items():
        players = pd.DataFrame(block["players"])
        players = players[players["seen"]]
        ids = person_ids(players["player_id"], EUROLEAGUE.name, xwalk)
        frames.append(
            pd.DataFrame(
                {
                    "person_id": ids["person_id"].to_numpy(),
                    "competition": EUROLEAGUE.name,
                    "season": int(season),
                    "stat": "brapm",
                    "value": players["total"].to_numpy(dtype="float64"),
                    "sd": players["sd_total"].to_numpy(dtype="float64"),
                }
            )
        )
    rows = pd.concat(frames, ignore_index=True)
    rows = rows.drop_duplicates(["person_id", "competition", "season", "stat"])
    return rows.sort_values(["season", "person_id"]).reset_index(drop=True)


def league_rates(player_games: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per competition and season the league's per-100 rate of each SPM stat (all lines with
    seconds played, possession-weighted), indexed by (competition, season)."""
    frames = []
    for competition, all_lines in player_games.items():
        lines = all_lines[all_lines["sec"] > 0]
        sums = lines.groupby("season")[[*STAT_COLUMNS, "poss"]].sum()
        rates = 100.0 * sums[list(STAT_COLUMNS)].div(sums["poss"], axis=0)
        frames.append(rates.assign(competition=competition).set_index("competition", append=True))
    return pd.concat(frames).reorder_levels(["competition", "season"]).sort_index()


def m6_spm(el: ElSpm, league: pd.DataFrame) -> SpmFn:
    """The injected SPM: ``before_season``'s EuroLeague SPM model (fitted on data before that
    season; the latest one when there is none for it) applied to each row's per-100 box rates
    minus the league rate of the row's previous season (never the row's own season: at a
    checkpoint that would read games after the cutoff; the first season has none and uses
    its own, which no checkpoint reads); SPM = O + D. Unshrunk rates. A season without its own
    model raises: falling back to a later model would read data after the season's start."""

    def spm(frame: pd.DataFrame, before_season: int) -> "pd.Series[float]":
        if before_season not in el.fit_time:
            raise ValueError(f"no EuroLeague SPM model for season {before_season}")
        model = choose_model(el, el.fit_time[before_season])
        if model is None:
            raise ValueError(f"no EuroLeague SPM model for season {before_season}")
        base = []
        cache: dict[tuple[str, int], np.ndarray] = {}  # the base row depends on this pair only
        for competition, season in zip(frame["competition"], frame["season"], strict=True):
            key = (competition, int(season))
            if key not in cache:
                rates = league.loc[competition]
                earlier = rates.loc[: key[1] - 1]
                cache[key] = (earlier if len(earlier) else rates).iloc[-1].to_numpy(dtype="float64")
            base.append(cache[key])
        features = frame[list(model.stats)].to_numpy(dtype="float64") - np.array(base)
        o, d = model.predict(features)
        return pd.Series(o + d, index=frame.index)

    return spm


def _m6_bios() -> pd.DataFrame:
    if not PLAYER_BIOS.exists():
        raise InputsMissing("no player bios; run: eurohoops bios")
    return pd.read_parquet(PLAYER_BIOS)


def m6_inputs(spec: M6Backtest, *, live: bool = False) -> M6Inputs:
    """M6's inputs: the EuroLeague games and player games up to the last test season (the live
    season never enters, so the daily log cannot move the report), the crosswalk, in-memory ages,
    the BRAPM snapshots and the SPM wired from M3's EuroLeague models.
    ``live`` (``eurohoops project``): up to the live season, the committed crosswalk file (D25)
    and no ages (the chosen variant does not age, and the daily workflow has no bios)."""
    last = LIVE_SEASON if live else spec.test[-1]
    el_games = read_games(MART_PATH, EUROLEAGUE.name)
    games = {EUROLEAGUE.name: el_games[el_games["season"] <= last].reset_index(drop=True)}
    xwalk = read_xwalk_file(PLAYER_XWALK_FILE) if live else read_table(MART_PATH, "player_xwalk")
    stints = read_table(MART_PATH, "stints")
    checks = read_table(MART_PATH, "stint_game_checks")
    if xwalk is None or stints is None or checks is None:
        raise InputsMissing("player_xwalk/stints missing; run: eurohoops entity / stints")
    player_games = {
        EUROLEAGUE.name: build_box_games(EUROLEAGUE.raw_dir, games[EUROLEAGUE.name]).players,
    }
    ages = (
        validated(pd.DataFrame({"person_id": [], "season": [], "age": []}), AGES_SCHEMA)
        if live
        else player_ages(_m6_bios(), xwalk, build_player_seasons(player_games, xwalk))
    )
    chosen = json.loads(M3.report.read_text(encoding="utf-8"))["chosen"]
    if chosen["variant"] != "rapm_spm":
        raise InputsMissing("M3 chosen variant must be rapm_spm (see reports/backtest_m3.json)")
    el = el_spm_models(
        el_games[el_games["played"]] if live else el_games,
        player_games[EUROLEAGUE.name],
        stints,
        checks,
        chosen,
        last=LIVE_SEASON if live else M3.test[-1],
    )
    return M6Inputs(
        games=games,
        player_games=player_games,
        xwalk=xwalk,
        ages=ages,
        brapm=_m6_brapm(xwalk),
        spm=m6_spm(el, league_rates(player_games)),
    )


def m2_shots(season: int) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """The ``shots`` and ``shot_xpts`` marts up to ``season`` and M2's chosen xPTS variant."""
    shots, xpts = read_table(MART_PATH, "shots"), read_table(MART_PATH, "shot_xpts")
    if shots is None or xpts is None:
        raise InputsMissing("shots/shot_xpts missing; run: eurohoops shots, backtest --model m2")
    variant = str(json.loads(M2_REPORT.read_text(encoding="utf-8"))["gate"]["chosen"])
    return shots[shots["season"] <= season], xpts, variant
