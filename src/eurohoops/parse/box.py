"""Cached GBL box-score HTML -> validated ``player_box`` and ``team_box`` staging tables.

Official lines come from ESAKE (``source = "esake"``). For the 2018-19 and 2019-20 gaps ESAKE
cannot fill (decided 2026-09-25), lines rebuilt from the BasketHotel play-by-play are added
with ``source = "pbp"``; they never count toward an official-box claim:

- a game without an ESAKE box gets PBP team totals (``team_box`` rows);
- a team whose ESAKE player lines add up to less than its result gets the one missing
  player's PBP line, but only when exactly one PBP line with stats has no exact match among
  the ESAKE lines and adding it makes the result.
- a team-side whose player seconds are not 5 x game length (within a minute) while its PBP
  on-court seconds are exactly 5 x game length gets each mismatched player's PBP minutes, if
  that closes the gap (``_minutes_from_pbp``); every change is logged in ``BoxTables.minutes``.

Every short game gets a row in the fill log: what was filled, or why not.
"""

import csv
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa

from eurohoops.ingest.cache import read_cached
from eurohoops.parse.esake import BoxLine, TeamBox, parse_box_score
from eurohoops.parse.gbl_pbp import PbpScoreError, parse_export, player_lines
from eurohoops.parse.schemas import validated

COUNTS = ("points", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "seconds")
SIGNATURE = COUNTS[:-1]  # every counting stat except minutes, which ESAKE and PBP round alike
SOURCES = ("esake", "pbp")
FILL_SEASONS = (2018, 2019)
# Owner decision (2026-10-19): these two 2022 games are repaired from PBP too, and no other 2022
# game is. Each must end with filled points equal to its result (tests/test_gbl_box_fix.py).
OWNER_FILL_GAMES = frozenset({"GBL2022_4180233B", "GBL2022_AF0B05AA"})
BOX_CORRECTIONS = Path("corrections/gbl_box.csv")
FILLS = ("team_totals_from_pbp", "missing_player_from_pbp", "not_filled")

PLAYER_BOX_SCHEMA = pa.DataFrameSchema(
    {
        "game_id": pa.Column(str),
        "team": pa.Column(str),
        "player_id": pa.Column(str),
        **{column: pa.Column("int64", pa.Check.ge(0)) for column in COUNTS},
        "source": pa.Column(str, pa.Check.isin(SOURCES)),
    },
    unique=["game_id", "player_id"],
    strict=True,
)

TEAM_BOX_SCHEMA = pa.DataFrameSchema(
    {
        "game_id": pa.Column(str),
        "team": pa.Column(str),
        "total_points": pa.Column("int64", pa.Check.ge(0)),
        "source": pa.Column(str, pa.Check.isin(SOURCES)),
    },
    unique=["game_id", "team", "source"],
    strict=True,
)

FILL_SCHEMA = pa.DataFrameSchema(
    {
        "game_id": pa.Column(str),
        "season": pa.Column("int64"),
        "team": pa.Column(str),
        "fill": pa.Column(str, pa.Check.isin(FILLS)),
        "detail": pa.Column(str),
    },
    unique=["game_id", "team"],
    strict=True,
)


@dataclass(frozen=True)
class BoxTables:
    player_box: pd.DataFrame
    team_box: pd.DataFrame
    fill: pd.DataFrame  # one row per team of a short game
    minutes: pd.DataFrame  # one row per replaced player minute, or unapplied team-side


@dataclass(frozen=True)
class BoxCorrection:
    """One documented per-player correction of an ESAKE line (``corrections/gbl_box.csv``)."""

    raw_value: int  # the value ESAKE printed; a stale row (no longer matching) raises
    value: int
    reason: str


def load_box_corrections(path: Path) -> dict[tuple[str, str, str], BoxCorrection]:
    """The corrections file keyed by (game_id, team, player_id); missing file means none."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            (row["game_id"], row["team"], row["player_id"]): BoxCorrection(
                int(row["raw_seconds"]), int(row["seconds"]), row["reason"]
            )
            for row in csv.DictReader(handle)
        }


def _apply_corrections(
    game_id: str,
    team: str,
    lines: tuple[BoxLine, ...],
    corrections: Mapping[tuple[str, str, str], BoxCorrection],
) -> tuple[BoxLine, ...]:
    """Lines with their documented seconds; raises if a correction no longer matches ESAKE."""
    out: list[BoxLine] = []
    for line in lines:
        fix = corrections.get((game_id, team, line.player_id))
        if fix is None:
            out.append(line)
            continue
        if fix.raw_value != line.seconds:
            raise ValueError(
                f"stale correction for {game_id} {line.player_id}: ESAKE says {line.seconds} s, "
                f"the file says {fix.raw_value} s"
            )
        out.append(replace(line, seconds=fix.value))
    return tuple(out)


def _corrected(
    game_id: str,
    teams: tuple[str, str],
    parsed: tuple[TeamBox, TeamBox],
    corrections: Mapping[tuple[str, str, str], BoxCorrection],
) -> tuple[TeamBox, TeamBox]:
    home, away = (
        replace(side, players=_apply_corrections(game_id, team, side.players, corrections))
        for team, side in zip(teams, parsed, strict=True)
    )
    return home, away


def _player_row(game_id: str, team: str, line: BoxLine) -> dict[str, object]:
    return {
        "game_id": game_id,
        "team": team,
        "player_id": line.player_id,
        **{column: getattr(line, column) for column in COUNTS},
        "source": "esake",
    }


@dataclass(frozen=True)
class _Game:
    game_id: str
    season: int
    idgame: str
    teams: tuple[str, str]  # home, away
    scores: tuple[int, int]


def _pbp(root: Path, game: _Game) -> pd.DataFrame | str:
    """PBP player lines of the game, or why there are none."""
    path = root / "pbp" / str(game.season) / f"{game.idgame}.xlsx.gz"
    if not path.exists():
        return "no cached PBP export (run: eurohoops ingest --competition gbl --pbp)"
    try:
        events = parse_export(read_cached(path), game.game_id, *game.scores)
    except PbpScoreError as exc:
        return f"PBP not usable: {exc}"
    return player_lines(events)


def _missing_player(
    official: tuple[BoxLine, ...], pbp: pd.DataFrame, score: int
) -> dict[str, Any] | str:
    """The single PBP line absent from the ESAKE lines that closes the gap, or why not."""
    known = Counter(tuple(getattr(line, c) for c in SIGNATURE) for line in official)
    unmatched: list[dict[str, Any]] = []
    for record in pbp.to_dict("records"):
        line = {str(key): value for key, value in record.items()}
        signature = tuple(line[c] for c in SIGNATURE)
        if known[signature]:
            known[signature] -= 1
        elif any(signature):
            unmatched.append(line)
    gap = score - sum(line.points for line in official)
    if len(unmatched) != 1 or unmatched[0]["points"] != gap:
        found = ", ".join(f"#{u['number']} {u['player']} ({u['points']} pts)" for u in unmatched)
        return f"{len(unmatched)} unmatched PBP lines [{found}] for a {gap}-point gap"
    return unmatched[0]


MINUTES_TOLERANCE = 60  # seconds: "5 x game length, plus or minus one minute"
MINUTES_COLUMNS = [
    "game_id",
    "season",
    "team",
    "player_id",
    "player",
    "raw_seconds",
    "seconds",
    "fix",
    "detail",
]


def _pbp_length(seconds: int) -> int | None:
    """The game length (s) whose five-man total the PBP on-court seconds equal exactly."""
    for overtimes in range(5):
        length = 2400 + 300 * overtimes
        if seconds == 5 * length:
            return length
    return None


def _matched_pbp(lines: tuple[BoxLine, ...], side: pd.DataFrame) -> dict[int, dict[str, Any]]:
    """ESAKE line index -> the PBP line of the side it equals; only one-to-one matches count."""
    esake = Counter(tuple(getattr(line, c) for c in SIGNATURE) for line in lines)
    pbp: dict[tuple[int, ...], list[dict[str, Any]]] = {}
    for record in side.to_dict("records"):
        key = tuple(int(record[c]) for c in SIGNATURE)
        pbp.setdefault(key, []).append({str(k): v for k, v in record.items()})
    out: dict[int, dict[str, Any]] = {}
    for index, line in enumerate(lines):
        key = tuple(getattr(line, c) for c in SIGNATURE)
        if esake[key] == 1 and len(pbp.get(key, ())) == 1:
            out[index] = pbp[key][0]
    return out


def _minutes_from_pbp(
    game: _Game,
    boxes: tuple[tuple[BoxLine, ...], ...],
    pbp: pd.DataFrame,
    filled: list[dict[str, object]],
) -> tuple[tuple[tuple[BoxLine, ...], ...], list[dict[str, object]]]:
    """Replace mismatched ESAKE minutes with the PBP on-court seconds of the same player.

    A team-side is checked when its seconds (ESAKE lines plus any PBP-filled player) are not
    5 x game length within a minute, and its PBP on-court seconds are exactly 5 x game length.
    Only players whose ESAKE minutes differ from a unique PBP line are replaced. The change is
    kept only if the side then sums to 5 x game length; otherwise the side is logged unchanged.
    """
    new = list(boxes)
    log: list[dict[str, object]] = []
    for side in (0, 1):
        team, name = game.teams[side], ("home", "away")[side]
        lines = pbp[pbp["side"] == name]
        length = _pbp_length(int(lines["seconds"].sum()))
        if length is None:
            continue
        target = 5 * length
        players = boxes[side]
        added = sum(int(str(row["seconds"])) for row in filled if row["team"] == team)
        total = sum(line.seconds for line in players) + added
        if abs(total - target) <= MINUTES_TOLERANCE:
            continue
        changes = [
            (index, row)
            for index, row in _matched_pbp(players, lines).items()
            if int(row["seconds"]) != players[index].seconds
        ]
        after = total + sum(int(row["seconds"]) - players[i].seconds for i, row in changes)
        base = {"game_id": game.game_id, "season": game.season, "team": team}
        if abs(after - target) > MINUTES_TOLERANCE:
            log.append(
                {
                    **base,
                    "player_id": "",
                    "player": "",
                    "raw_seconds": total,
                    "seconds": total,
                    "fix": "not_applied",
                    "detail": f"sum {total} s vs {target} s; no unique PBP replacement closes "
                    f"the {target - total} s gap",
                }
            )
            continue
        replaced = list(players)
        for index, row in changes:
            line = players[index]
            replaced[index] = replace(line, seconds=int(row["seconds"]))
            log.append(
                {
                    **base,
                    "player_id": line.player_id,
                    "player": f"#{row['number']} {row['player']}",
                    "raw_seconds": line.seconds,
                    "seconds": int(row["seconds"]),
                    "fix": "replaced_from_pbp",
                    "detail": f"team sum {total} s vs {target} s; PBP on-court sums exactly",
                }
            )
        new[side] = tuple(replaced)
    return tuple(new), log


def _fill(
    game: _Game, boxes: tuple[tuple[BoxLine, ...], ...] | None, pbp: pd.DataFrame | str
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """PBP player rows, PBP team rows and fill-log rows for one game's short teams."""
    short = [
        side
        for side in (0, 1)
        if boxes is None or sum(line.points for line in boxes[side]) != game.scores[side]
    ]
    if not short:
        return [], [], []
    log = [
        {"game_id": game.game_id, "season": game.season, "team": game.teams[side]} for side in short
    ]
    if game.season not in FILL_SEASONS and game.game_id not in OWNER_FILL_GAMES:
        reason = "outside the 2018-19/2019-20 fill scope (user decision 2026-09-25)"
        return [], [], [{**row, "fill": "not_filled", "detail": reason} for row in log]
    if isinstance(pbp, str):
        return [], [], [{**row, "fill": "not_filled", "detail": pbp} for row in log]
    players: list[dict[str, object]] = []
    teams: list[dict[str, object]] = []
    for row, side in zip(log, short, strict=True):
        lines = pbp[pbp["side"] == ("home", "away")[side]]
        points = int(lines["points"].sum())
        team, score = game.teams[side], game.scores[side]
        if points != score:
            row |= {"fill": "not_filled", "detail": f"PBP events sum to {points}, result {score}"}
        elif boxes is None:
            teams.append(
                {"game_id": game.game_id, "team": team, "total_points": points, "source": "pbp"}
            )
            row |= {"fill": "team_totals_from_pbp", "detail": f"{points} points from PBP events"}
        else:
            found = _missing_player(boxes[side], lines, score)
            if isinstance(found, str):
                row |= {"fill": "not_filled", "detail": found}
            else:
                player_id = f"pbp:{found['number']}:{found['player']}"
                players.append(
                    {
                        "game_id": game.game_id,
                        "team": team,
                        "player_id": player_id,
                        **{column: int(found[column]) for column in COUNTS},
                        "source": "pbp",
                    }
                )
                row |= {
                    "fill": "missing_player_from_pbp",
                    "detail": f"#{found['number']} {found['player']}: {found['points']} points",
                }
    return players, teams, log


def build_box_tables(
    root: Path,
    games: pd.DataFrame,
    corrections: Mapping[tuple[str, str, str], BoxCorrection] | None = None,
) -> BoxTables:
    """Parse every cached box score of a played, non-forfeit game in ``games``, then fill.

    Order per game: documented corrections, the PBP fill of short teams, then the minutes rule
    (``_minutes_from_pbp``). Games without a cached or published box score get no ESAKE rows;
    the invariant report flags them as ``missing_box`` whatever the PBP fill adds.
    """
    players: list[dict[str, object]] = []
    teams: list[dict[str, object]] = []
    fills: list[dict[str, object]] = []
    minutes: list[dict[str, object]] = []
    rated = games[games["played"] & ~games["forfeit"]]
    if corrections is None:
        corrections = load_box_corrections(BOX_CORRECTIONS)
    for game_id, season, code, home, away, home_score, away_score in zip(
        rated["game_id"],
        rated["season"],
        rated["game_code"],
        rated["home"],
        rated["away"],
        rated["home_score"],
        rated["away_score"],
        strict=True,
    ):
        game = _Game(
            game_id, int(season), f"{code:08X}", (home, away), (int(home_score), int(away_score))
        )
        path = root / "boxscore" / str(season) / f"{game.idgame}.html.gz"
        parsed = parse_box_score(read_cached(path).decode()) if path.exists() else None
        if parsed is not None:
            parsed = _corrected(game_id, game.teams, parsed, corrections)
        boxes: tuple[tuple[BoxLine, ...], ...] | None = (
            None if parsed is None else (parsed[0].players, parsed[1].players)
        )
        pbp = _pbp(root, game)
        pbp_players, pbp_teams, log = _fill(game, boxes, pbp)
        if boxes is not None and not isinstance(pbp, str):
            boxes, changes = _minutes_from_pbp(game, boxes, pbp, pbp_players)
            minutes += changes
        for side, (team, box) in enumerate(zip(game.teams, parsed or (), strict=False)):
            teams.append(
                {
                    "game_id": game_id,
                    "team": team,
                    "total_points": box.total_points,
                    "source": "esake",
                }
            )
            current = boxes if boxes is not None else ((), ())
            players.extend(_player_row(game_id, team, line) for line in current[side])
        players += pbp_players
        teams += pbp_teams
        fills += log
    player_box = pd.DataFrame(players, columns=list(PLAYER_BOX_SCHEMA.columns))
    team_box = pd.DataFrame(teams, columns=list(TEAM_BOX_SCHEMA.columns))
    fill = pd.DataFrame(fills, columns=list(FILL_SCHEMA.columns))
    return BoxTables(
        validated(player_box, PLAYER_BOX_SCHEMA),
        validated(team_box, TEAM_BOX_SCHEMA),
        validated(fill, FILL_SCHEMA),
        pd.DataFrame(minutes, columns=MINUTES_COLUMNS),
    )
