"""Assist network: each ``AS`` (assist) play-by-play row paired with the made basket it belongs to.

The linking rule is rule D of the WP pre-study (``wave1/wp-prestudy``, ``scripts/wp_t1c.py``,
``link_variants``), with one addition: a make by the passer himself is never a candidate (a
player cannot assist his own basket; the feed's order sometimes puts the make first). For each
``AS`` row, the first rule that finds a make wins:

- A. the nearest preceding made field goal in the same period, if it is the passer's team's;
- B. else the next made field goal in the period, if it is the passer's team's and at the same
  clock second;
- C. else the nearest same-team made field goal within 10 events in the period, if it is within
  2 events of the row or at the same clock second.

A made field goal is credited once: the first ``AS`` row (in log order) that links to it is kept,
and later rows that link to the same make stay unlinked. The pre-study measured rule D at 94.9% of
``AS`` rows linked. A game is skipped when an ``AS`` or made-basket row has no clock (period markers
have none and are not used; the pre-study also skipped games with unreadable clocks).

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
WINDOW = 10  # rule C searches this many events either side
NEAR = 2  # rule C: a make within this many events links without a clock match
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


def _next_make(events_: Sequence[Event], i: int) -> int:
    """Index of the first made field goal after ``i`` in the same period, or -1."""
    period = events_[i].period
    for j in range(i + 1, len(events_)):
        if events_[j].period != period:
            return -1
        if events_[j].kind in MAKES:
            return j
    return -1


def _credited(make: Event, row: Event) -> bool:
    """Whether ``make`` can be the basket of the ``AS`` row ``row``: the passer's team's, and not
    the passer's own (a player cannot assist his own basket, so such a link is a feed error)."""
    return make.team == row.team and (not row.player or make.player != row.player)


def _rule_d(events_: Sequence[Event], i: int, last: int) -> int | None:
    """The make linked to the ``AS`` row at ``i`` by rules A, B, C in turn; ``last`` is the most
    recent made field goal (any team) in the same period before ``i``, or -1."""
    row = events_[i]
    if last >= 0 and _credited(events_[last], row):  # A
        return last
    nxt = _next_make(events_, i)  # B
    if nxt >= 0 and _credited(events_[nxt], row) and events_[nxt].elapsed == row.elapsed:
        return nxt
    best: tuple[int, int] | None = None  # C: nearest, earliest on a tie
    for j in range(max(0, i - WINDOW), min(len(events_), i + WINDOW + 1)):
        other = events_[j]
        if j == i or other.kind not in MAKES or other.period != row.period:
            continue
        if not _credited(other, row):
            continue
        gap = abs(j - i)
        if (gap <= NEAR or other.elapsed == row.elapsed) and (best is None or gap < best[0]):
            best = (gap, j)
    return None if best is None else best[1]


def assist_rows(log: Sequence[Event]) -> list[AssistRow]:
    """Every ``AS`` row of one game's play-by-play (log order) with its linked make, rule D.

    Every ``AS`` row and made basket of ``log`` must have a clock (``Event.elapsed`` set).
    """
    links: dict[int, int] = {}
    last = -1
    period: int | None = None
    for i, event in enumerate(log):
        if event.period != period:
            period, last = event.period, -1
        if event.kind == ASSIST:
            made = _rule_d(log, i, last)
            if made is not None:
                links[i] = made
        if event.kind in MAKES:
            last = i
    taken: set[int] = set()
    rows: list[AssistRow] = []
    for i, event in enumerate(log):
        if event.kind != ASSIST:
            continue
        made = links.get(i)
        if made is not None and made in taken:
            made = None  # the first AS row keeps the make
        if made is None:
            rows.append(AssistRow(event.team, event.player, None, 0))
            continue
        taken.add(made)
        rows.append(AssistRow(event.team, event.player, log[made].player, POINTS[log[made].kind]))
    return rows


def game_assists(raw_dir: Path, games: pd.DataFrame) -> dict[str, list[AssistRow]]:
    """Game id -> its assist rows, for every game of ``games`` (game_id, season, game_code) with a
    cached play-by-play and a clock on every AS and made-basket row. Other games have no entry."""
    out: dict[str, list[AssistRow]] = {}
    for game_id, season, code in zip(
        games["game_id"], games["season"], games["game_code"], strict=True
    ):
        path = raw_dir / "playbyplay" / f"E{int(season)}" / f"{int(code)}.json.gz"
        if not path.exists():
            continue
        log = events(json.loads(read_cached(path)))
        if any(e.elapsed is None for e in log if e.kind == ASSIST or e.kind in MAKES):
            continue
        out[str(game_id)] = assist_rows(log)
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
