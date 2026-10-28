"""Play-by-play rows for the in-game WP model (docs/models/wp.md, sections 2 and 4).

One raw EuroLeague play-by-play file (already decoded to a dict) becomes a list of play rows in log
order: the period, the clock, the game time remaining ``t``, the score after the play (carried
forward, home perspective). The file is never fetched here; the caller reads the cache.
"""

from dataclasses import dataclass
from typing import Any, NamedTuple

# Section 2: every made field goal and made free throw. LAYUPMD and DUNK are the 2008-2014 coding
# of two-point makes; a model without them drops 41,164 makes.
SCORING_CODES = ("2FGM", "3FGM", "LAYUPMD", "DUNK", "FTM")
MARKERS = ("BP", "EP", "EG")
REG_BLOCKS = (
    ("FirstQuarter", 1),
    ("SecondQuarter", 2),
    ("ThirdQuarter", 3),
    ("ForthQuarter", 4),  # spelled this way in the source
)
REG_PERIOD_SECONDS = 600
OT_PERIOD_SECONDS = 300
OT_FIRST_MINUTE = 41  # OT period k covers MINUTE 41 + 5(k - 1) to 45 + 5(k - 1)
OT_MINUTES = 5
GAME_SECONDS = 2400

CLOCK_OK = "ok"
CLOCK_BLANK = "blank"
CLOCK_ND = "nd"


class PlayRow(NamedTuple):
    """One play. A NamedTuple, not a frozen dataclass: a game has ~500 rows and the export parses
    every game twice, so construction speed matters."""

    period: int  # 1-4 regulation; 4 + k in overtime period k
    ot: int  # 1 in overtime
    clock: float  # seconds left in the period, clamped to the period maximum
    elapsed: float  # seconds of game time elapsed at the play
    t: float  # seconds remaining in the game (regulation) or in the OT period (overtime)
    ptype: str
    s_home: int  # carried score after the play
    s_away: int


@dataclass(frozen=True)
class ParsedGame:
    code_ok: bool  # the file's two team codes are the mart's home and away codes
    rows: tuple[PlayRow, ...]  # empty when code_ok is False
    has_ot: bool  # the ExtraTime block holds play other than the markers
    bad_clock_events: int  # play events whose clock is ND, a sentinel or blank
    final_home: int | None
    final_away: int | None


def read_clock(raw: str, maxc: int, ptype: str) -> tuple[float, str]:
    """Clock seconds and its status. Markers with a blank clock get the period bounds."""
    text = (raw or "").strip()
    if text == "":
        if ptype == "BP":
            return float(maxc), CLOCK_BLANK
        if ptype in ("EP", "EG"):
            return 0.0, CLOCK_BLANK
        return float("nan"), CLOCK_BLANK
    if ":" in text:
        mm, _, ss = text.partition(":")
        if mm.isdigit() and ss.isdigit():
            return float(min(int(mm) * 60 + int(ss), maxc)), CLOCK_OK
    return float("nan"), CLOCK_ND


def _overtime_index(minute: int, ptype: str) -> int:
    """OT period index k (1, 2, ...). Period-end markers carry the next minute, so they map back."""
    if ptype in ("EP", "EG"):
        return max((minute - OT_FIRST_MINUTE) // OT_MINUTES, 1)
    return (minute - OT_FIRST_MINUTE) // OT_MINUTES + 1


def _score(value: Any, current: int) -> int:
    return current if value in (None, "") else int(value)


def parse_game(obj: dict[str, Any], mart_home: str, mart_away: str) -> ParsedGame:
    """Play rows of one game, score carried forward and taken from the home side."""
    code_a = obj["CodeTeamA"].strip()
    code_b = obj["CodeTeamB"].strip()
    if (code_a, code_b) == (mart_home, mart_away):
        flip = False
    elif (code_b, code_a) == (mart_home, mart_away):
        flip = True
    else:
        return ParsedGame(False, (), False, 0, None, None)

    items: list[tuple[str, int, dict[str, Any]]] = []
    for name, period in REG_BLOCKS:
        items.extend(("R", period, e) for e in obj[name])
    items.extend(("X", 0, e) for e in (obj.get("ExtraTime") or []))

    rows: list[PlayRow] = []
    cur_a = cur_b = 0
    bad = 0
    for kind, block, event in items:
        ptype = event["PLAYTYPE"].strip()
        if kind == "X":
            k = max(_overtime_index(int(event["MINUTE"]), ptype), 1)
            period, maxc, base = (
                4 + k,
                OT_PERIOD_SECONDS,
                GAME_SECONDS + (k - 1) * OT_PERIOD_SECONDS,
            )
        else:
            period, maxc, base = block, REG_PERIOD_SECONDS, (block - 1) * REG_PERIOD_SECONDS
        clock, status = read_clock(event["MARKERTIME"], maxc, ptype)
        if status != CLOCK_OK and ptype not in MARKERS:
            bad += 1
        elapsed = base + maxc - clock
        t_rem = (4 - period) * REG_PERIOD_SECONDS + clock if kind == "R" else clock
        cur_a = _score(event["POINTS_A"], cur_a)
        cur_b = _score(event["POINTS_B"], cur_b)
        s_home, s_away = (cur_b, cur_a) if flip else (cur_a, cur_b)
        rows.append(
            PlayRow(
                period=period,
                ot=int(kind == "X"),
                clock=clock,
                elapsed=elapsed,
                t=t_rem,
                ptype=ptype,
                s_home=s_home,
                s_away=s_away,
            )
        )
    has_ot = any(r.ot == 1 and r.ptype not in MARKERS for r in rows)
    if not has_ot:
        rows = [r for r in rows if r.ot == 0]
    last = rows[-1] if rows else None
    return ParsedGame(
        code_ok=True,
        rows=tuple(rows),
        has_ot=has_ot,
        bad_clock_events=bad,
        final_home=last.s_home if last else None,
        final_away=last.s_away if last else None,
    )
