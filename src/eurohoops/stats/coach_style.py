"""Coaching style for the coach pages (EuroLeague): after-timeout possessions, clutch games,
rotation depth and coach challenges.

``game_styles`` reads each played game's cached play-by-play and box score once (never fetched)
and keeps one ``GameStyle`` per game plus league totals per season. ``coach_style`` sums those
team-game figures over one coach's team-games; the league figures are the same sums over every
EuroLeague team-game of the coach's seasons.

Definitions (plain words for the page):
- After timeout: points per possession on the team's first possession after its own timeout
  (``TOUT``; TV timeouts are ignored). A possession ends when the ball goes to the other team.
  The possession is the one the team holds after its timeout, or the next one it receives. Only
  points scored after the timeout count. A timeout called inside the team's own free-throw trip
  is not counted.
- Clutch: the score margin was within 5 points at some moment with 5:00 or less left in the
  fourth quarter, or in any overtime.
- Rotation: players with minutes in the game, and the share of minutes taken by the top 7 players.
- Challenges: coach challenges (``CCH``) from the 2021-22 season on, and the share in the 4th
  quarter or overtime. The data does not say whether a challenge succeeded.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

import pandas as pd

from eurohoops.ingest.cache import read_cached
from eurohoops.parse.stints import QUARTERS
from eurohoops.stats.box import seconds as box_seconds

TIMEOUT = "TOUT"  # the team's own timeout; TOUT_TV (TV timeout) is ignored
CHALLENGE = "CCH"
CHALLENGE_FROM = 2021  # season code: E2021 is 2021-22, the first season with CCH rows
CLUTCH_MARGIN = 5
CLUTCH_SECONDS = 300
TOP_PLAYERS = 7
# Scoring rows by PLAYTYPE (the codes changed over the seasons: LAYUPMD and DUNK in 2008-2014).
# POINTS_A/POINTS_B are running totals and are not needed for the possessions.
MADE_FIELD_GOAL = ("2FGM", "3FGM", "LAYUPMD", "DUNK")
POINTS = {"2FGM": 2, "3FGM": 3, "LAYUPMD": 2, "DUNK": 2, "FTM": 1}
# Missed field goals, blocked ones included (2FGAB, 3FGAB, LAYUPATT): the shooter has the ball.
FIELD_GOAL_ATTEMPT = ("2FGA", "3FGA", "2FGAB", "3FGAB", "LAYUPATT")
FREE_THROW = ("FTA", "FTM")  # FTA is a missed free throw, FTM a made one
PERIOD_END = ("EP", "EG")
# Rows that decide who has the ball next (timeouts, fouls and substitutions do not).
BALL_KINDS = frozenset(
    (*MADE_FIELD_GOAL, *FIELD_GOAL_ATTEMPT, *FREE_THROW, "D", "O", "TO", "ST", *PERIOD_END)
)


class Action(NamedTuple):
    period: int  # 1-4 for the quarters, 5 for overtime
    left: int | None  # seconds left in the period (None when the row has no clock)
    kind: str  # PLAYTYPE
    team: str  # CODETEAM, stripped ("" on period rows)
    score: tuple[int, int] | None  # running score (team A, team B) on scoring rows


@dataclass(frozen=True)
class TeamGame:
    ato_possessions: int
    ato_points: int
    challenges: int
    challenges_late: int
    players_used: int | None  # None without a box score
    top7_share: float | None


@dataclass(frozen=True)
class GameStyle:
    season: int
    clutch: bool
    teams: dict[str, TeamGame] = field(default_factory=dict)


@dataclass
class Totals:
    """Sums over team-games (each game adds two)."""

    team_games: int = 0
    clutch_team_games: int = 0
    ato_possessions: int = 0
    ato_points: int = 0
    rotation_team_games: int = 0
    players_used: int = 0
    top7_share_sum: float = 0.0
    challenge_team_games: int = 0
    challenges: int = 0
    challenges_late: int = 0

    def add_team(self, season: int, clutch: bool, team: TeamGame) -> None:
        self.team_games += 1
        self.clutch_team_games += int(clutch)
        self.ato_possessions += team.ato_possessions
        self.ato_points += team.ato_points
        if team.players_used is not None and team.top7_share is not None:
            self.rotation_team_games += 1
            self.players_used += team.players_used
            self.top7_share_sum += team.top7_share
        if season >= CHALLENGE_FROM:
            self.challenge_team_games += 1
            self.challenges += team.challenges
            self.challenges_late += team.challenges_late


@dataclass(frozen=True)
class StyleIndex:
    games: dict[str, GameStyle]  # game_id -> style, for games with a cached play-by-play
    seasons: dict[int, Totals]  # league totals per season


def _clock(marker: str) -> int | None:
    """``mm:ss`` left in the period -> seconds; None when the text is not a clock."""
    minutes, sep, seconds = marker.partition(":")
    if not sep or not minutes.isdigit() or not seconds.isdigit():
        return None
    return int(minutes) * 60 + int(seconds)


def actions(pbp: dict[str, Any]) -> tuple[list[Action], tuple[str, str]]:
    """Play-by-play rows in log order, and the two team codes (team A, team B)."""
    out: list[Action] = []
    for index, key in enumerate((*QUARTERS, "ExtraTime")):
        period = index + 1 if index < len(QUARTERS) else 5
        for row in pbp.get(key) or []:
            kind = str(row.get("PLAYTYPE") or "").strip()
            marker = str(row.get("MARKERTIME") or "").strip()
            left = _clock(marker) if marker else (0 if kind in PERIOD_END else None)
            points_a, points_b = row.get("POINTS_A"), row.get("POINTS_B")
            score = None if points_a is None or points_b is None else (int(points_a), int(points_b))
            team = str(row.get("CODETEAM") or "").strip()
            out.append(Action(period, left, kind, team, score))
    teams = (str(pbp.get("CodeTeamA") or "").strip(), str(pbp.get("CodeTeamB") or "").strip())
    return out, teams


def _in_clutch_window(act: Action) -> bool:
    if act.period >= 5:
        return True
    return act.period == 4 and act.left is not None and act.left <= CLUTCH_SECONDS


def is_clutch(acts: Sequence[Action]) -> bool:
    """True when the margin was within ``CLUTCH_MARGIN`` at some moment in the clutch window.

    The margin before each row is the score after the rows before it, so the state carried into
    the window counts too; the margin after each scoring row in the window counts as well.
    """
    home = away = 0
    for act in acts:
        window = _in_clutch_window(act)
        if window and abs(home - away) <= CLUTCH_MARGIN:
            return True
        if act.score is not None:
            home, away = act.score
        if window and abs(home - away) <= CLUTCH_MARGIN:
            return True
    return False


def _next_ball_row(acts: Sequence[Action], index: int) -> Action | None:
    for act in acts[index + 1 :]:
        if act.kind in BALL_KINDS:
            return act
    return None


class _Ball:
    """Who has the ball, and the after-timeout possessions of each team.

    A team's own timeout starts an ATO possession: at once when the team holds the ball, or when
    it next receives the ball. The possession closes when the ball goes to the other team (or the
    period ends). Points count only from the timeout on. Waiting timeouts are kept per team
    (``armed`` is a set), so a timeout is not lost when the other team calls one too. Period end
    clears the waiting timeouts.
    """

    def __init__(self, teams: tuple[str, str]) -> None:
        self.teams = teams
        self.totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # team -> [poss, points]
        self.owner: str | None = None
        self.armed: set[str] = set()  # teams whose timeout waits for their next possession
        self.run: str | None = None

    def other(self, team: str) -> str:
        return self.teams[1] if team == self.teams[0] else self.teams[0]

    def close(self) -> None:
        if self.run is not None:
            self.totals[self.run][0] += 1
            self.run = None

    def give(self, team: str) -> None:
        """``team`` has the ball now."""
        if not team:
            return
        if team != self.owner:
            self.owner = team
            if self.run is not None and self.run != team:
                self.close()
        if team in self.armed and self.run is None:
            self.run = team
            self.armed.discard(team)

    def timeout(self, team: str) -> None:
        if self.run == team:  # already inside its own possession
            return
        if self.owner == team:  # the team holds the ball: the possession after the timeout is now
            self.run = team
            self.armed.discard(team)
        else:
            self.armed.add(team)

    def score(self, team: str, points: int) -> None:
        if self.run is not None and self.run == team:
            self.totals[self.run][1] += points


def _prev_ball_row(acts: Sequence[Action], index: int) -> Action | None:
    for act in reversed(acts[:index]):
        if act.kind in BALL_KINDS:
            return act
    return None


def _in_own_free_throw_trip(acts: Sequence[Action], index: int, team: str) -> bool:
    """True when a timeout falls between two free throws of the team's own trip."""
    prev, nxt = _prev_ball_row(acts, index), _next_ball_row(acts, index)
    return (
        prev is not None
        and nxt is not None
        and prev.kind in FREE_THROW
        and nxt.kind in FREE_THROW
        and prev.team == team
        and nxt.team == team
    )


def after_timeout(acts: Sequence[Action], teams: tuple[str, str]) -> dict[str, tuple[int, int]]:
    """Team -> (possessions, points) on its possessions right after its own timeouts."""
    ball = _Ball(teams)
    for index, act in enumerate(acts):
        kind, team = act.kind, act.team
        if kind in PERIOD_END:
            ball.close()
            ball.owner = None
            ball.armed.clear()
        elif kind == TIMEOUT:
            if not _in_own_free_throw_trip(acts, index, team):
                ball.timeout(team)
        elif kind in MADE_FIELD_GOAL:
            ball.give(team)  # the shooter has the ball
            ball.score(team, POINTS[kind])
            nxt = _next_ball_row(acts, index)
            and_one = nxt is not None and nxt.kind in FREE_THROW and nxt.team == team
            if not and_one:
                ball.give(ball.other(team))
        elif kind in FIELD_GOAL_ATTEMPT:
            ball.give(team)  # a miss or a block: the shooter keeps the ball until a rebound
        elif kind == "TO":
            ball.give(team)  # a turnover: the team had the ball, then the other team gets it
            ball.give(ball.other(team))
        elif kind == "FTM":
            ball.give(team)  # the shooter has the ball during the trip
            ball.score(team, POINTS[kind])
            nxt = _next_ball_row(acts, index)
            if nxt is None or nxt.kind not in FREE_THROW or nxt.team != team:
                ball.give(ball.other(team))  # the last free throw hands the ball over
        elif kind == "FTA":
            ball.give(team)  # a missed free throw: a rebound (or the next free throw) follows
        elif kind in ("D", "O", "ST"):
            ball.give(team)
    ball.close()
    return {team: (ball.totals[team][0], ball.totals[team][1]) for team in teams if team}


def challenges(acts: Sequence[Action]) -> dict[str, tuple[int, int]]:
    """Team -> (coach challenges, those in the 4th quarter or overtime)."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for act in acts:
        if act.kind == CHALLENGE and act.team:
            counts[act.team][0] += 1
            counts[act.team][1] += int(act.period >= 4)
    return {team: (total, late) for team, (total, late) in counts.items()}


def rotation(box: dict[str, Any]) -> dict[str, tuple[int, float | None]]:
    """Team -> (players with minutes, minutes share of its top 7 players) from a box score."""
    out: dict[str, tuple[int, float | None]] = {}
    for side in box.get("Stats", []):
        players = side.get("PlayersStats") or []
        if not players:
            continue
        team = str(players[0]["Team"]).strip()
        minutes = sorted(
            (box_seconds(str(p.get("Minutes") or "")) or 0 for p in players), reverse=True
        )
        total = sum(minutes)
        used = sum(1 for m in minutes if m > 0)
        out[team] = (used, sum(minutes[:TOP_PLAYERS]) / total if total else None)
    return out


def game_style(raw_dir: Path, season: int, game_code: str) -> GameStyle | None:
    """One game's style from the cache; None without a cached play-by-play."""
    path = raw_dir / "playbyplay" / f"E{season}" / f"{game_code}.json.gz"
    if not path.exists():
        return None
    acts, teams = actions(json.loads(read_cached(path)))
    ato = after_timeout(acts, teams)
    counted = challenges(acts)
    box_path = raw_dir / "boxscore" / f"E{season}" / f"{game_code}.json.gz"
    rot = rotation(json.loads(read_cached(box_path))) if box_path.exists() else {}
    team_games: dict[str, TeamGame] = {}
    for team in teams:
        if not team:
            continue
        poss, points = ato.get(team, (0, 0))
        total, late = counted.get(team, (0, 0))
        used, top7 = rot.get(team, (None, None))
        team_games[team] = TeamGame(poss, points, total, late, used, top7)
    return GameStyle(season=season, clutch=is_clutch(acts), teams=team_games)


def game_styles(raw_dir: Path, games: pd.DataFrame) -> StyleIndex:
    """Every played EuroLeague game's style (one read per game) and the league totals per season."""
    by_game: dict[str, GameStyle] = {}
    seasons: dict[int, Totals] = defaultdict(Totals)
    played = games[games["played"] & ~games["forfeit"]]
    for game in played.itertuples(index=False):
        season = int(str(game.season))
        style = game_style(raw_dir, season, str(game.game_code))
        if style is None:
            continue
        by_game[str(game.game_id)] = style
        for team in style.teams.values():
            seasons[season].add_team(season, style.clutch, team)
    return StyleIndex(games=by_game, seasons=dict(seasons))


def _rate(numerator: float, denominator: float, digits: int = 3) -> float | None:
    return round(numerator / denominator, digits) if denominator else None


def coach_style(rows: pd.DataFrame, index: StyleIndex) -> dict[str, Any]:
    """The coach's four stats, each with the league figure over the same seasons.

    ``rows`` are the coach's team-game rows (``season``, ``game_id``, ``team``, ``won``).
    """
    mine = Totals()
    clutch_wins = clutch_losses = 0
    seasons: set[int] = set()
    for row in rows.itertuples(index=False):
        style = index.games.get(str(row.game_id))
        if style is None or str(row.team) not in style.teams:
            continue
        season = int(str(row.season))
        seasons.add(season)
        mine.add_team(season, style.clutch, style.teams[str(row.team)])
        if style.clutch:
            clutch_wins += int(bool(row.won))
            clutch_losses += int(not row.won)
    league = Totals()
    for season in seasons:
        part = index.seasons.get(season)
        if part is None:
            continue
        for name in vars(league):
            setattr(league, name, getattr(league, name) + getattr(part, name))
    challenge_block: dict[str, Any] | None = None
    if mine.challenge_team_games:
        challenge_block = {
            "from_season": CHALLENGE_FROM,
            "games": mine.challenge_team_games,
            "per_game": _rate(mine.challenges, mine.challenge_team_games, 2),
            "late_share": _rate(mine.challenges_late, mine.challenges),
            "league_per_game": _rate(league.challenges, league.challenge_team_games, 2),
            "league_late_share": _rate(league.challenges_late, league.challenges),
        }
    return {
        "ato": {
            "possessions": mine.ato_possessions,
            "points": mine.ato_points,
            "ppp": _rate(mine.ato_points, mine.ato_possessions),
            "league_ppp": _rate(league.ato_points, league.ato_possessions),
        },
        "clutch": {
            "games": mine.clutch_team_games,
            "team_games": mine.team_games,
            "wins": clutch_wins,
            "losses": clutch_losses,
            "league_share": _rate(league.clutch_team_games, league.team_games),
        },
        "rotation": {
            "games": mine.rotation_team_games,
            "players_per_game": _rate(mine.players_used, mine.rotation_team_games, 2),
            "top7_share": _rate(mine.top7_share_sum, mine.rotation_team_games),
            "league_players_per_game": _rate(league.players_used, league.rotation_team_games, 2),
            "league_top7_share": _rate(league.top7_share_sum, league.rotation_team_games),
        },
        "challenges": challenge_block,
    }
