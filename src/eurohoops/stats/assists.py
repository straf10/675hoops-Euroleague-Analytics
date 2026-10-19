"""Assist network: each ``AS`` (assist) play-by-play row paired with what it created.

An ``AS`` row is linked in two tiers, tried in this order:

- ``fg``: a one-to-one maximum matching of AS rows to made field goals. An edge needs the
  passer's team's make, not the passer's own; no opposing make between the two rows; the clocks at
  most ``CLOCK_WINDOW`` seconds apart and the rows at most ``EVENT_WINDOW`` events apart
  (``NO_CLOCK_WINDOW`` events when a row has no clock).
- ``ft``: the assist credits a free throw. The pass led to a foul on a teammate (not the passer)
  who made at least one free throw in the same trip: a made free throw (FTM) of that teammate
  within ``FT_WINDOW`` events and ``FT_CLOCK`` seconds of the row, with his foul received (``RV``)
  within ``FOUL_WINDOW`` events before it. One foul credits at most one assist.

Every make and every foul is credited at most once. A row that fits neither tier stays unlinked
(``scorer`` None). The payload's ``pairs``, ``passers`` and ``linked`` count both tiers (an assist
is an assist); ``fg_pairs`` and ``ft_pairs`` keep the tiers apart.

Raw facts only: passer, scorer (the field-goal or free-throw shooter), and the points that
basket was worth (2 or 3 for a field goal, 1 for a free throw).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from eurohoops.ingest.cache import read_cached
from eurohoops.parse.stints import POINTS, Event, events

ASSIST = "AS"
# Made field goals only for the field-goal tier; free throws (FTM) are used by the FT tier.
MAKES = frozenset({"2FGM", "3FGM", "LAYUPMD", "DUNK"})
CLOCK_WINDOW = 60  # seconds between an AS row and its field goal (fg tier)
EVENT_WINDOW = 30  # events between an AS row and its field goal (fg tier)
NO_CLOCK_WINDOW = 3  # events, when either row has no clock (fg tier)
FT_WINDOW = 4  # events between an AS row and the made free throw (ft tier)
FT_CLOCK = 2  # seconds between an AS row and the made free throw (ft tier)
FOUL_WINDOW = 6  # events before the made free throw that hold the foul received (ft tier)
TIERS = ("fg", "ft")
SCHEMA = ("passer", "scorer", "assists", "points")  # pairs in assists.json
PASSER_SCHEMA = ("passer", "as_rows", "linked", "points")  # passers in assists.json


@dataclass(frozen=True)
class AssistRow:
    """One ``AS`` row: the club, the passer, the scorer of what it created (None when unlinked),
    that basket's points (0 when unlinked) and the tier that linked it (``fg`` or ``ft``; None when
    unlinked; a linked row without a tier is a field-goal link)."""

    team: str
    passer: str
    scorer: str | None
    points: int
    tier: str | None = None


def _opposing_make_between(log: Sequence[Event], i: int, j: int) -> bool:
    """Whether an opposing made field goal lies strictly between log rows ``i`` and ``j``."""
    lo, hi = min(i, j), max(i, j)
    team = log[i].team
    return any(log[k].kind in MAKES and log[k].team != team for k in range(lo + 1, hi))


def _gap(log: Sequence[Event], i: int, j: int) -> tuple[int, int]:
    """(clock gap in seconds, or a large number when a clock is missing; event gap)."""
    a, m = log[i], log[j]
    if a.elapsed is None or m.elapsed is None:
        return 10**9, abs(j - i)
    return abs(m.elapsed - a.elapsed), abs(j - i)


def _fg_candidates(log: Sequence[Event], i: int) -> list[tuple[tuple[int, int], int]]:
    """Field goals that may be the basket of the ``AS`` row at ``i``, closest first."""
    row = log[i]
    out: list[tuple[tuple[int, int], int]] = []
    lo, hi = max(0, i - EVENT_WINDOW), min(len(log), i + EVENT_WINDOW + 1)
    for j in range(lo, hi):
        make = log[j]
        if j == i or make.kind not in MAKES or make.team != row.team:
            continue
        if row.player and make.player == row.player:
            continue
        clock, events_apart = _gap(log, i, j)
        if clock == 10**9:
            if events_apart > NO_CLOCK_WINDOW:
                continue
        elif clock > CLOCK_WINDOW:
            continue
        if _opposing_make_between(log, i, j):
            continue
        out.append(((clock, events_apart), j))
    out.sort()
    return out


def _match(edges: dict[int, list[tuple[tuple[int, int], int]]]) -> dict[int, int]:
    """Maximum matching of AS rows to makes (Kuhn's augmenting paths). Rows are tried closest
    pair first, so a tight pair is kept whenever a maximum matching allows it."""
    match_make: dict[int, int] = {}

    def augment(row: int, seen: set[int]) -> bool:
        for _, make in edges[row]:
            if make in seen:
                continue
            seen.add(make)
            if make not in match_make or augment(match_make[make], seen):
                match_make[make] = row
                return True
        return False

    for row in sorted(edges, key=lambda r: edges[r][0][0]):
        augment(row, set())
    return {row: make for make, row in match_make.items()}


def _foul_index(log: Sequence[Event], j: int) -> int | None:
    """Index of the foul received (``RV``) by the free-throw shooter of row ``j``, within
    ``FOUL_WINDOW`` events before it, or None."""
    shooter, team = log[j].player, log[j].team
    for k in range(j, max(-1, j - FOUL_WINDOW - 1), -1):
        if log[k].kind == "RV" and log[k].player == shooter and log[k].team == team:
            return k
    return None


def _ft_candidates(log: Sequence[Event], i: int) -> list[tuple[tuple[int, int], int, int]]:
    """Made free throws that may credit the ``AS`` row at ``i``: a teammate's, not the passer's,
    within the windows, with a foul received in the same trip. Closest first; (gap, FTM, RV)."""
    row = log[i]
    out: list[tuple[tuple[int, int], int, int]] = []
    for j in range(max(0, i - FT_WINDOW), min(len(log), i + FT_WINDOW + 1)):
        ft = log[j]
        if ft.kind != "FTM" or ft.team != row.team or not ft.player or ft.player == row.player:
            continue
        if (
            row.elapsed is not None
            and ft.elapsed is not None
            and abs(ft.elapsed - row.elapsed) > FT_CLOCK
        ):
            continue
        rv = _foul_index(log, j)
        if rv is None:
            continue
        out.append(((abs(j - i), rv), j, rv))
    out.sort()
    return out


def _linked(log: Sequence[Event]) -> dict[int, tuple[int, str]]:
    """AS row index -> (credited index: the make or the free throw, tier), both tiers."""
    as_idx = [i for i, e in enumerate(log) if e.kind == ASSIST]
    out: dict[int, tuple[int, str]] = {}
    edges = {i: c for i in as_idx if (c := _fg_candidates(log, i))}
    for i, j in _match(edges).items():
        out[i] = (j, "fg")
    # ft tier: one foul credits at most one assist; AS rows in log order take their closest trip
    claimed_rv: set[int] = set()
    for i in as_idx:
        if i in out:
            continue
        for _, ft, rv in _ft_candidates(log, i):
            if rv in claimed_rv:
                continue
            claimed_rv.add(rv)
            out[i] = (ft, "ft")
            break
    return out


def assist_rows(log: Sequence[Event]) -> list[AssistRow]:
    """Every ``AS`` row of one game's play-by-play (log order) with what it created and the tier."""
    links = _linked(log)
    rows: list[AssistRow] = []
    for i, event in enumerate(log):
        if event.kind != ASSIST:
            continue
        link = links.get(i)
        if link is None:
            rows.append(AssistRow(event.team, event.player, None, 0))
            continue
        made, tier = link
        rows.append(
            AssistRow(
                event.team,
                event.player,
                log[made].player,
                POINTS[log[made].kind],
                tier,
            )
        )
    return rows


def game_assists(raw_dir: Path, games: pd.DataFrame) -> dict[str, list[AssistRow]]:
    """Game id -> its assist rows, for every game of ``games`` (game_id, season, game_code) with a
    cached play-by-play. Other games have no entry."""
    out: dict[str, list[AssistRow]] = {}
    for game_id, season, code in zip(
        games["game_id"], games["season"], games["game_code"], strict=True
    ):
        path = raw_dir / "playbyplay" / f"E{int(season)}" / f"{int(code)}.json.gz"
        if not path.exists():
            continue
        out[str(game_id)] = assist_rows(events(json.loads(read_cached(path))))
    return out


def assists_payload(
    season: int,
    game_ids: Sequence[str],
    rows_by_game: Mapping[str, Sequence[AssistRow]],
    box_assists: Mapping[str, int],
) -> dict[str, object]:
    """``seasons/{season}/assists.json``: per club, the assist counts and the pairs.

    ``box_assists`` is the club's box-score assist total over the same games (the check that the
    pairing covers the official count). Each club holds ``as_rows`` (AS rows in the play-by-play),
    ``linked`` (field-goal and free-throw links), ``linked_fg`` / ``linked_ft`` (per tier), ``box``
    (box-score assists), ``pairs`` (``SCHEMA`` rows over both tiers, most assists first),
    ``fg_pairs`` and ``ft_pairs`` (the same schema per tier) and ``passers`` (``PASSER_SCHEMA`` rows
    over both tiers, most points first). Team and player ids are source codes.
    """
    pairs: dict[str, dict[str, dict[tuple[str, str], list[int]]]] = {}
    passers: dict[str, dict[str, list[int]]] = {}
    clubs: dict[str, dict[str, int]] = {}
    for game_id in sorted(game_ids):
        for row in rows_by_game.get(game_id, ()):
            club = clubs.setdefault(row.team, {"as_rows": 0, "linked": 0, "fg": 0, "ft": 0})
            club["as_rows"] += 1
            stat = passers.setdefault(row.team, {}).setdefault(row.passer, [0, 0, 0])
            stat[0] += 1
            if row.scorer is None:
                continue
            tier = row.tier or "fg"
            club["linked"] += 1
            club[tier] += 1
            stat[1] += 1
            stat[2] += row.points
            for key in ("all", tier):
                by_key = pairs.setdefault(row.team, {}).setdefault(key, {})
                pair = by_key.setdefault((row.passer, row.scorer), [0, 0])
                pair[0] += 1
                pair[1] += row.points
    out: dict[str, object] = {}
    for team in sorted(clubs):
        tiered: dict[str, list[list[object]]] = {}
        for key in ("all", *TIERS):
            club_pairs = sorted(
                pairs.get(team, {}).get(key, {}).items(),
                key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]),
            )
            tiered[key] = [[p, s, a, pts] for (p, s), (a, pts) in club_pairs]
        club_passers = sorted(
            passers.get(team, {}).items(), key=lambda kv: (-kv[1][2], -kv[1][1], kv[0])
        )
        out[team] = {
            "as_rows": clubs[team]["as_rows"],
            "linked": clubs[team]["linked"],
            "linked_fg": clubs[team]["fg"],
            "linked_ft": clubs[team]["ft"],
            "box": int(box_assists.get(team, 0)),
            "pairs": tiered["all"],
            "fg_pairs": tiered["fg"],
            "ft_pairs": tiered["ft"],
            "passers": [[p, *stat] for p, stat in club_passers],
        }
    return {
        "season": season,
        "schema": list(SCHEMA),
        "passer_schema": list(PASSER_SCHEMA),
        "clubs": out,
    }
