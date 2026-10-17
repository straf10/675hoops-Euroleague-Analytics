"""Helpers shared by the command modules: competition and model enums, live-season readers."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

import pandas as pd
import typer

from eurohoops.config import EUROLEAGUE, GBL, GBL_PBP, LIVE_SEASON, MART_PATH, Competition
from eurohoops.eval.backtest import TunedModel, load_tuned_model
from eurohoops.marts import read_games, read_table
from eurohoops.parse.team_box import TEAM_GAMES_SCHEMA

log = logging.getLogger("eurohoops")


class CompetitionName(StrEnum):
    euroleague = "euroleague"
    gbl = "gbl"


class ModelName(StrEnum):
    elo = "elo"
    elor = "elor"
    eloc = "eloc"
    m1 = "m1"
    m2 = "m2"
    m3 = "m3"
    m4 = "m4"
    m5 = "m5"
    m6 = "m6"
    m7 = "m7"
    pool = "pool"


CompetitionOption = Annotated[
    CompetitionName, typer.Option("--competition", help="Which competition")
]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _gbl_pbp() -> pd.DataFrame | None:
    return pd.read_parquet(GBL_PBP) if GBL_PBP.exists() else None


def _both_games() -> pd.DataFrame:
    return pd.concat(
        [read_games(MART_PATH, c.name).assign(competition=c.name) for c in (EUROLEAGUE, GBL)],
        ignore_index=True,
    )


@dataclass(frozen=True)
class Live:
    """What predict, score and publish read for a competition's live season."""

    games: pd.DataFrame  # the competition's games mart
    model: TunedModel  # the live Elo parameters (its live backtest report)
    season: int
    replay_from: int  # Elo replays from the live backtest's first warm-up season


def _live(comp: Competition) -> Live:
    return Live(
        read_games(MART_PATH, comp.name),
        load_tuned_model(comp.live_backtest.report),
        LIVE_SEASON,
        comp.live_backtest.warmup[0],
    )


def _team_games(competition: str) -> pd.DataFrame:
    """The competition's ``team_games`` rows (none before the first ``build``)."""
    table = read_table(MART_PATH, "team_games", competition)
    return pd.DataFrame(columns=list(TEAM_GAMES_SCHEMA.columns)) if table is None else table
