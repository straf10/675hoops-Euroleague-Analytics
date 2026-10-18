"""Play-by-play parsing for the WP model (docs/models/wp.md, sections 2 and 4): clocks, overtime
blocks, carried scores, team orientation and the exclusion flags. Synthetic games only."""

from typing import Any

from eurohoops.parse.wp_pbp import CLOCK_BLANK, CLOCK_ND, CLOCK_OK, parse_game, read_clock


def _ev(ptype: str, clock: str, a: str = "", b: str = "", minute: int = 1) -> dict[str, Any]:
    return {"PLAYTYPE": ptype, "MARKERTIME": clock, "MINUTE": minute, "POINTS_A": a, "POINTS_B": b}


def _game(
    *,
    blocks: dict[str, list[dict[str, Any]]] | None = None,
    extra: list[dict[str, Any]] | None = None,
    code_a: str = "H",
    code_b: str = "A",
) -> dict[str, Any]:
    names = ("FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter")
    obj: dict[str, Any] = {"CodeTeamA": code_a, "CodeTeamB": code_b}
    for name in names:
        obj[name] = (blocks or {}).get(name, [])
    obj["ExtraTime"] = extra or []
    return obj


def test_clock_parses_minutes_and_seconds_and_clamps_to_period() -> None:
    assert read_clock("07:30", 600, "2FGM") == (450.0, CLOCK_OK)
    assert read_clock("11:00", 600, "SUB") == (600.0, CLOCK_OK)  # 2015 rows stamped 11:00
    assert read_clock("06:00", 300, "SUB") == (300.0, CLOCK_OK)  # OT rows stamped 06:00


def test_clock_flags_nd_and_sentinel_and_blank() -> None:
    assert read_clock("ND", 600, "2FGM")[1] == CLOCK_ND
    assert read_clock("00:-1", 600, "2FGM")[1] == CLOCK_ND
    assert read_clock("-1:00", 600, "2FGM")[1] == CLOCK_ND
    assert read_clock("", 600, "BP") == (600.0, CLOCK_BLANK)
    assert read_clock("", 600, "EG") == (0.0, CLOCK_BLANK)


def test_game_decided_at_the_buzzer_has_t_zero_and_the_final_score() -> None:
    q4 = [_ev("2FGM", "00:04", "70", "72", 31), _ev("2FGM", "00:00", "80", "72", 31)]
    game = _game(blocks={"ForthQuarter": q4})
    parsed = parse_game(game, "H", "A")
    assert parsed.code_ok and not parsed.has_ot
    last = parsed.rows[-1]
    assert last.t == 0.0
    assert last.elapsed == 2400.0
    assert (parsed.final_home, parsed.final_away) == (80, 72)


def test_scores_carry_forward_when_one_side_is_blank() -> None:
    q1 = [_ev("2FGM", "09:00", "2", "", 1), _ev("FTM", "08:00", "", "1", 2)]
    parsed = parse_game(_game(blocks={"FirstQuarter": q1}), "H", "A")
    assert [(r.s_home, r.s_away) for r in parsed.rows] == [(2, 0), (2, 1)]


def test_regulation_time_remaining_counts_later_periods_as_less() -> None:
    q2 = [_ev("2FGM", "05:00", "10", "8", 15)]
    parsed = parse_game(_game(blocks={"SecondQuarter": q2}), "H", "A")
    assert parsed.rows[0].t == 2 * 600 + 300  # two full quarters plus 5:00 of the second


def test_overtime_block_uses_five_minute_periods_and_offsets() -> None:
    extra = [_ev("2FGM", "04:58", "60", "60", 41), _ev("2FGM", "00:00", "62", "60", 45)]
    parsed = parse_game(_game(extra=extra), "H", "A")
    assert parsed.has_ot
    first, last = parsed.rows[0], parsed.rows[-1]
    assert (first.ot, first.period, first.t) == (1, 5, 298.0)
    assert first.elapsed == 2400.0 + 300.0 - 298.0
    assert last.t == 0.0 and last.elapsed == 2700.0
    assert (parsed.final_home, parsed.final_away) == (62, 60)


def test_marker_only_overtime_block_is_regulation() -> None:
    extra = [_ev("BP", "", "", "", 41), _ev("EG", "", "", "", 46)]
    parsed = parse_game(_game(extra=extra), "H", "A")
    assert not parsed.has_ot
    assert all(r.ot == 0 for r in parsed.rows)


def test_team_codes_in_the_other_order_flip_the_score_to_home_side() -> None:
    q1 = [_ev("2FGM", "09:00", "2", "5", 1)]  # file's team A is the mart's away team
    parsed = parse_game(_game(blocks={"FirstQuarter": q1}, code_a="A", code_b="H"), "H", "A")
    assert parsed.code_ok
    assert (parsed.rows[0].s_home, parsed.rows[0].s_away) == (5, 2)


def test_unknown_team_codes_are_a_code_mismatch() -> None:
    parsed = parse_game(_game(code_a="N/D", code_b="N/D"), "H", "A")
    assert not parsed.code_ok and parsed.rows == ()


def test_nd_clock_on_a_play_is_counted_as_bad() -> None:
    q1 = [_ev("2FGM", "ND", "2", "0", 1), _ev("BP", "", "", "", 1)]
    parsed = parse_game(_game(blocks={"FirstQuarter": q1}), "H", "A")
    assert parsed.bad_clock_events == 1  # the marker's blank clock is not a bad play clock
