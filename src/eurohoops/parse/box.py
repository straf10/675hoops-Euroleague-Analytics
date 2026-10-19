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
from itertools import combinations
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


def _pbp_only(
    side: pd.DataFrame, players: tuple[BoxLine, ...], filled_ids: set[str]
) -> list[dict[str, Any]]:
    """PBP player lines of a side that no ESAKE line or PBP fill accounts for, each with minutes.

    ESAKE lines consume PBP lines in two passes: first the line with the same counting stats and
    the same seconds, then any line with the same counting stats (for a player whose minutes
    differ). What is left is a player the box score does not list at all.
    """
    rows = [
        {str(key): value for key, value in record.items()}
        for record in side.to_dict("records")
        if f"pbp:{record['number']}:{record['player']}" not in filled_ids
    ]
    pairs = Counter(
        (tuple(getattr(line, c) for c in SIGNATURE), int(line.seconds)) for line in players
    )
    used = [False] * len(rows)
    for index, row in enumerate(rows):
        key = (tuple(int(row[c]) for c in SIGNATURE), int(row["seconds"]))
        if pairs[key] > 0:
            pairs[key] -= 1
            used[index] = True
    stats: Counter[tuple[int, ...]] = Counter()
    for (signature, _), count in pairs.items():
        stats[signature] += count
    for index, row in enumerate(rows):
        signature = tuple(int(row[c]) for c in SIGNATURE)
        if not used[index] and stats[signature] > 0:
            stats[signature] -= 1
            used[index] = True
    return [row for index, row in enumerate(rows) if not used[index] and int(row["seconds"]) > 0]


def _added_players(
    lines: list[dict[str, Any]], gap: int, points_gap: int
) -> list[dict[str, Any]] | None:
    """The one subset of PBP-only lines whose minutes close ``gap`` and points ``points_gap``.

    None when no subset (of up to three players) or more than one subset fits.
    """
    fits: list[list[dict[str, Any]]] = []
    for size in range(1, min(3, len(lines)) + 1):
        for subset in combinations(lines, size):
            seconds = sum(int(row["seconds"]) for row in subset)
            points = sum(int(row["points"]) for row in subset)
            if abs(seconds - gap) <= MINUTES_TOLERANCE and points == points_gap:
                fits.append(list(subset))
    return fits[0] if len(fits) == 1 else None


def _minutes_from_pbp(
    game: _Game,
    boxes: tuple[tuple[BoxLine, ...], ...],
    pbp: pd.DataFrame,
    filled: list[dict[str, object]],
) -> tuple[tuple[tuple[BoxLine, ...], ...], list[dict[str, object]], list[dict[str, object]]]:
    """Make each team-side's minutes match 5 x game length, from the PBP on-court seconds.

    A team-side is checked when its seconds (ESAKE lines plus any PBP-filled player) are not
    5 x game length within a minute, and its PBP on-court seconds are exactly 5 x game length.
    Then, in order:
    1. each ESAKE player whose minutes differ from its unique PBP line takes the PBP minutes;
    2. if the side is still short, the one set of PBP-only players (lines no ESAKE or fill row
       accounts for, up to three) whose minutes close the gap and whose points equal the points
       missing from the score is added with its PBP line.
    A change is kept only if the side then sums to the length; otherwise the side is logged
    unchanged. Returns the boxes, the log, and the added player rows (source ``pbp``).
    """
    new = list(boxes)
    log: list[dict[str, object]] = []
    added_rows: list[dict[str, object]] = []
    filled_ids = {str(row["player_id"]) for row in filled}
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
        base = {"game_id": game.game_id, "season": game.season, "team": team}
        changes = [
            (index, row)
            for index, row in _matched_pbp(players, lines).items()
            if int(row["seconds"]) != players[index].seconds
        ]
        after = total + sum(int(row["seconds"]) - players[i].seconds for i, row in changes)
        replaced = list(players)
        for index, row in changes:
            line = players[index]
            replaced[index] = replace(line, seconds=int(row["seconds"]))
        extra: list[dict[str, Any]] = []
        if abs(after - target) > MINUTES_TOLERANCE:
            points_now = sum(line.points for line in players) + sum(
                int(str(row["points"])) for row in filled if row["team"] == team
            )
            extra_found = _added_players(
                _pbp_only(lines, players, filled_ids),
                target - after,
                game.scores[side] - points_now,
            )
            if extra_found is not None:
                extra = extra_found
                after += sum(int(row["seconds"]) for row in extra)
        if abs(after - target) > MINUTES_TOLERANCE:
            log.append(
                {
                    **base,
                    "player_id": "",
                    "player": "",
                    "raw_seconds": total,
                    "seconds": total,
                    "fix": "not_applied",
                    "detail": f"sum {total} s vs {target} s; no replacement or PBP-only set "
                    f"closes the {target - total} s gap",
                }
            )
            continue
        for index, row in changes:
            line = players[index]
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
        for row in extra:
            player_id = f"pbp:{row['number']}:{row['player']}"
            log.append(
                {
                    **base,
                    "player_id": player_id,
                    "player": f"#{row['number']} {row['player']}",
                    "raw_seconds": 0,
                    "seconds": int(row["seconds"]),
                    "fix": "added_from_pbp",
                    "detail": f"ESAKE box omits this player; team sum {total} s vs {target} s "
                    f"closes with his PBP minutes; {int(row['points'])} points",
                }
            )
            added_rows.append(
                {
                    "game_id": game.game_id,
                    "team": team,
                    "player_id": player_id,
                    **{column: int(row[column]) for column in COUNTS},
                    "source": "pbp",
                }
            )
        new[side] = tuple(replaced)
    return tuple(new), log, added_rows


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
        added: list[dict[str, object]] = []
        if boxes is not None and not isinstance(pbp, str):
            boxes, changes, added = _minutes_from_pbp(game, boxes, pbp, pbp_players)
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
        players += pbp_players + added
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
