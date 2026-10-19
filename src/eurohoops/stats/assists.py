"""Assist network: each ``AS`` (assist) play-by-play row paired with the made basket it belongs to.

Linking is a one-to-one matching per game. ``AS`` rows and made field goals are the two sides,
and an edge joins an ``AS`` row to a make when all of these hold:

- the make is the passer's team's, and it is not the passer's own basket (a player cannot assist
  his own make; such a link is a feed error);
- no made field goal of the other team lies between the two rows in the log (a possession that
  ended in an opponent's basket cannot have produced the make that follows it);
- the clocks are at most ``CLOCK_WINDOW`` seconds apart and the rows at most ``EVENT_WINDOW``
  events apart; when a row has no clock (``ND`` markers), the rows must be at most
  ``NO_CLOCK_WINDOW`` events apart.

Edges are chosen by maximum matching, so each made field goal is credited at most once and each
``AS`` row links at most one make. Among equal matchings the closest pairs (clock, then events)
are tried first. Rows without an edge stay unlinked (``scorer`` None).

Measured on the cached EuroLeague play-by-play, 2007-2026: 92.9% of AS rows link (see the
"Linkage, production rule (revised)" paragraph of ``docs/models/wp_prestudy.md``). The 98% target
is not reached: the rows left
unlinked have no same-possession make in the feed; the wider windows that would link them pair
them with makes minutes away or past an opposing basket, and a hand-check of such pairs found
them wrong.

Raw facts only: passer, scorer and the points the scorer's basket was worth (2 or 3).
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
# Made field goals only: the free throws (FTM) are not an assisted basket.
MAKES = frozenset({"2FGM", "3FGM", "LAYUPMD", "DUNK"})
CLOCK_WINDOW = 60  # seconds between an AS row and its make
EVENT_WINDOW = 30  # events between an AS row and its make
NO_CLOCK_WINDOW = 3  # events, when either row has no clock
SCHEMA = ("passer", "scorer", "assists", "points")  # pairs in assists.json
PASSER_SCHEMA = ("passer", "as_rows", "linked", "points")  # passers in assists.json


@dataclass(frozen=True)
class AssistRow:
    """One ``AS`` row: the club, the passer, the scorer of the linked make (None when unlinked)
    and that basket's points (0 when unlinked)."""

    team: str
    passer: str
    scorer: str | None
    points: int


def _gap(log: Sequence[Event], i: int, j: int) -> tuple[int, int]:
    """(clock gap in seconds, or a large number when a clock is missing; event gap)."""
    a, m = log[i], log[j]
    if a.elapsed is None or m.elapsed is None:
        return 10**9, abs(j - i)
    return abs(m.elapsed - a.elapsed), abs(j - i)


def _opposing_make_between(log: Sequence[Event], i: int, j: int) -> bool:
    """Whether an opposing made field goal lies strictly between log rows ``i`` and ``j``."""
    lo, hi = min(i, j), max(i, j)
    team = log[i].team
    return any(log[k].kind in MAKES and log[k].team != team for k in range(lo + 1, hi))


def _candidates(log: Sequence[Event], i: int) -> list[tuple[tuple[int, int], int]]:
    """Makes that may be the basket of the ``AS`` row at ``i``, closest first."""
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


def assist_rows(log: Sequence[Event]) -> list[AssistRow]:
    """Every ``AS`` row of one game's play-by-play (log order) with its linked make."""
    edges: dict[int, list[tuple[tuple[int, int], int]]] = {}
    for i, event in enumerate(log):
        if event.kind != ASSIST:
            continue
        cands = _candidates(log, i)
        if cands:
            edges[i] = cands
    links = _match(edges) if edges else {}
    rows: list[AssistRow] = []
    for i, event in enumerate(log):
        if event.kind != ASSIST:
            continue
        made = links.get(i)
        if made is None:
            rows.append(AssistRow(event.team, event.player, None, 0))
            continue
        rows.append(AssistRow(event.team, event.player, log[made].player, POINTS[log[made].kind]))
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
    ``linked`` (those with a make), ``box`` (box-score assists), ``pairs`` (``SCHEMA`` rows, most
    assists first) and ``passers`` (``PASSER_SCHEMA`` rows, most points first). Team and player
    ids are source codes.
    """
    pairs: dict[str, dict[tuple[str, str], list[int]]] = {}
    passers: dict[str, dict[str, list[int]]] = {}
    clubs: dict[str, dict[str, int]] = {}
    for game_id in sorted(game_ids):
        for row in rows_by_game.get(game_id, ()):
            club = clubs.setdefault(row.team, {"as_rows": 0, "linked": 0})
            club["as_rows"] += 1
            stat = passers.setdefault(row.team, {}).setdefault(row.passer, [0, 0, 0])
            stat[0] += 1
            if row.scorer is None:
                continue
            club["linked"] += 1
            stat[1] += 1
            stat[2] += row.points
            pair = pairs.setdefault(row.team, {}).setdefault((row.passer, row.scorer), [0, 0])
            pair[0] += 1
            pair[1] += row.points
    out: dict[str, object] = {}
    for team in sorted(clubs):
        club_pairs = sorted(
            pairs.get(team, {}).items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0])
        )
        club_passers = sorted(
            passers.get(team, {}).items(), key=lambda kv: (-kv[1][2], -kv[1][1], kv[0])
        )
        out[team] = {
            "as_rows": clubs[team]["as_rows"],
            "linked": clubs[team]["linked"],
            "box": int(box_assists.get(team, 0)),
            "pairs": [[p, s, a, pts] for (p, s), (a, pts) in club_pairs],
            "passers": [[p, *stat] for p, stat in club_passers],
        }
    return {
        "season": season,
        "schema": list(SCHEMA),
        "passer_schema": list(PASSER_SCHEMA),
        "clubs": out,
    }
