"""M5-INJ (docs/models/m5_inj.md): player matching, the Out status at the information cutoff, the
renormalised shares, and the shadow log on the synthetic league. Fixtures only, no data/ or
predictions/ paths."""

import csv
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from eurohoops.live_m5 import LiveM5, predict_upcoming_m5
from eurohoops.live_m5inj import m5inj_version, predict_upcoming_m5inj
from eurohoops.models.availability import (
    AMBIGUOUS,
    MATCHED,
    NO_MATCH,
    RosterPlayer,
    apply_out,
    match_injuries,
    out_players,
    parse_roster_names,
    read_injuries,
)
from tests.m5_synthetic import PLAYERS_PER_TEAM, TARGET_TEAMS, fake_player_part
from tests.test_live_m5 import CHOICE, NOW, ROUND_LEAD, SEASON, SPEC, live

FIXTURES = Path(__file__).parent / "fixtures" / "m5inj"
CUTOFF = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)


@pytest.fixture
def roster() -> list[RosterPlayer]:
    return parse_roster_names((FIXTURES / "people_sample.json").read_bytes())


@pytest.fixture
def injuries() -> pd.DataFrame:
    return read_injuries(FIXTURES / "injuries_sample.csv")


@pytest.fixture
def matched(injuries: pd.DataFrame, roster: list[RosterPlayer]) -> pd.DataFrame:
    return match_injuries(injuries, roster)


def _row(matched: pd.DataFrame, team: str, player: str, snapshot: str) -> pd.Series:
    rows = matched[
        (matched["team"] == team)
        & (matched["player"] == player)
        & (matched["snapshot_utc"] == snapshot)
    ]
    assert len(rows) == 1
    return rows.iloc[0]


# --- roster and matching ----------------------------------------------------------------------


def test_roster_keeps_players_only_with_box_score_ids(roster: list[RosterPlayer]) -> None:
    ids = {p.player_id for p in roster}
    assert "P1001" in ids and "P1006" not in ids  # type E (not a player) is left out
    assert len(roster) == 6


def test_accents_case_and_name_order_are_folded(matched: pd.DataFrame) -> None:
    row = _row(matched, "ULK", "Nemanja Dangubic", "2026-10-08T09:00:00Z")
    assert row["match"] == MATCHED and row["player_id"] == "P1001"


def test_generational_suffix_is_dropped(matched: pd.DataFrame) -> None:
    row = _row(matched, "ULK", "Lonnie Walker", "2026-10-08T09:00:00Z")
    assert row["match"] == MATCHED and row["player_id"] == "P1007"


def test_a_name_shared_by_two_players_of_one_club_is_ambiguous(matched: pd.DataFrame) -> None:
    row = _row(matched, "DUB", "John Smith", "2026-10-08T09:00:00Z")
    assert row["match"] == AMBIGUOUS and row["player_id"] == ""


def test_matching_is_team_scoped(matched: pd.DataFrame) -> None:
    # The name exists for ULK, but the row says PAN: no match, not a guess.
    row = _row(matched, "ULK", "Nemanja Dangubic", "2026-10-08T09:00:00Z")
    assert row["match"] == MATCHED
    wrong_club = matched[(matched["team"] == "PAN") & (matched["player"] == "Nemanja Dangubic")]
    assert wrong_club["match"].tolist() == [NO_MATCH]


# --- Out at the information cutoff --------------------------------------------------------------


def test_out_is_the_latest_status_before_the_cutoff(matched: pd.DataFrame) -> None:
    # Dangubic: Out on 10-08, Ready on 10-14. Walker and Mills: Out on 10-08, Uncertain on 10-11.
    assert out_players(matched, CUTOFF) == set()
    assert out_players(matched, datetime(2026, 10, 9, tzinfo=UTC)) == {"P1001", "P1002", "P1007"}


def test_a_snapshot_at_or_after_the_cutoff_is_ignored(matched: pd.DataFrame) -> None:
    # Rogkavopoulos is Out only in the 10-20 snapshot: nothing before that stamp may see it.
    before = datetime(2026, 10, 20, 8, 59, 59, tzinfo=UTC)
    at = datetime(2026, 10, 20, 9, 0, 0, tzinfo=UTC)
    after = datetime(2026, 10, 20, 9, 0, 1, tzinfo=UTC)
    assert "P1003" not in out_players(matched, before)
    assert "P1003" not in out_players(matched, at)
    assert "P1003" in out_players(matched, after)


def test_uncertain_is_not_out(matched: pd.DataFrame) -> None:
    assert "P1002" not in out_players(matched, CUTOFF)


def test_unmatched_rows_never_make_anyone_out(matched: pd.DataFrame) -> None:
    # John Smith (ambiguous) and Dangubic at PAN (no match) are Out in the feed: no effect.
    unmatched = matched[matched["match"] != MATCHED]
    assert out_players(unmatched, datetime(2026, 10, 9, tzinfo=UTC)) == set()


def test_an_empty_log_gives_no_statuses(roster: list[RosterPlayer], tmp_path: Path) -> None:
    empty = read_injuries(tmp_path / "missing.csv")
    assert out_players(match_injuries(empty, roster), CUTOFF) == set()


# --- the renormalised shares --------------------------------------------------------------------


def _shares() -> pd.DataFrame:
    rows = []
    for game in ("G1", "G2"):
        for side, team, players in (
            ("home", "ULK", {"P1001": 0.7, "P1002": 0.6, "P1003": 0.5, "P1004": 0.4, "P1005": 0.2}),
            ("away", "PAN", {"P2001": 0.8, "P2002": 0.7, "P2003": 0.3}),
        ):
            rows += [
                {"game_id": game, "side": side, "team": team, "player_id": p, "share": s}
                for p, s in players.items()
            ]
    return pd.DataFrame(rows)


def _side(shares: pd.DataFrame, game: str, side: str) -> pd.DataFrame:
    return shares[(shares["game_id"] == game) & (shares["side"] == side)]


def test_out_player_is_zeroed_and_the_side_renormalised() -> None:
    shares = _shares()
    result = apply_out(shares, {"G1"}, {"P1001"})
    home = _side(result, "G1", "home").set_index("player_id")["share"]
    assert "P1001" not in home.index
    assert home.sum() == pytest.approx(2.4)  # the team total of the side is unchanged
    assert home["P1002"] == pytest.approx(0.6 * 2.4 / 1.7)
    assert home["P1005"] == pytest.approx(0.2 * 2.4 / 1.7)


def test_renormalisation_keeps_the_team_total_for_every_out_set() -> None:
    # Single absences only: the cap at 1 binds when a remaining share is large (then the total
    # drops, as in rotation._drop_absent), and that case is not what this test checks.
    shares = _shares()
    total = _side(shares, "G1", "home")["share"].sum()
    for out in ({"P1001"}, {"P1002"}, {"P1003"}, {"P1004"}, {"P1005"}):
        result = apply_out(shares, {"G1"}, out)
        assert _side(result, "G1", "home")["share"].sum() == pytest.approx(total)


def test_uncertain_players_keep_their_shares_when_nobody_is_out() -> None:
    shares = _shares()
    pd.testing.assert_frame_equal(apply_out(shares, {"G1", "G2"}, set()), shares)


def test_other_games_and_the_other_side_are_untouched() -> None:
    shares = _shares()
    result = apply_out(shares, {"G1"}, {"P1001"})
    for game, side in (("G2", "home"), ("G1", "away")):
        kept = _side(result, game, side).reset_index(drop=True)
        pd.testing.assert_frame_equal(kept, _side(shares, game, side).reset_index(drop=True))


def test_a_side_with_everybody_out_is_left_unchanged() -> None:
    shares = _shares()
    everyone = {"P1001", "P1002", "P1003", "P1004", "P1005"}
    pd.testing.assert_frame_equal(apply_out(shares, {"G1"}, everyone), shares)


def test_an_unmatched_player_has_no_effect() -> None:
    shares = _shares()
    pd.testing.assert_frame_equal(apply_out(shares, {"G1", "G2"}, {"P9999"}), shares)


# --- the shadow log on the synthetic league -----------------------------------------------------

NAMES = ("ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL", "INDIA")


def _synthetic_roster() -> list[RosterPlayer]:
    return [
        RosterPlayer(f"{team}_{k}", team, f"{NAMES[k]}, TESTER")
        for team in TARGET_TEAMS
        for k in range(PLAYERS_PER_TEAM)
    ]


def _injury_log(rows: list[tuple[str, str, str, str]]) -> pd.DataFrame:
    """(snapshot, team, name, status) rows in the injury log's columns."""
    return pd.DataFrame(
        {
            "snapshot_utc": [r[0] for r in rows],
            "team": [r[1] for r in rows],
            "player": [r[2] for r in rows],
            "bn_player_id": ["0"] * len(rows),
            "status": [r[3] for r in rows],
        }
    )


def _run_m5(log: Path, at: datetime, model: LiveM5) -> int:
    chosen = live()
    return predict_upcoming_m5(
        chosen.games,
        model,
        lambda: (chosen, fake_player_part),
        log_path=log,
        season=SEASON,
        round_lead=ROUND_LEAD,
        clock=lambda: at,
        spec=SPEC,
    )


def _run_m5inj(log: Path, at: datetime, model: LiveM5, injuries: pd.DataFrame) -> int:
    chosen = live()
    return predict_upcoming_m5inj(
        chosen.games,
        model,
        lambda: (chosen, fake_player_part),
        injuries=injuries,
        roster=_synthetic_roster(),
        log_path=log,
        season=SEASON,
        round_lead=ROUND_LEAD,
        clock=lambda: at,
        spec=SPEC,
    )


def _rows(log: Path) -> dict[str, dict[str, str]]:
    with log.open(newline="", encoding="utf-8") as fh:
        return {
            r["game_id"]: {k: v for k, v in r.items() if k != "predicted_at_utc"}
            for r in csv.DictReader(fh)
        }


@pytest.fixture
def model() -> LiveM5:
    return LiveM5(CHOICE, "0.0.0+m5.test", gate_passed=True)


def test_a_failed_m5_gate_logs_nothing(model: LiveM5, tmp_path: Path) -> None:
    log = tmp_path / "m5inj.csv"
    assert _run_m5inj(log, NOW, replace(model, gate_passed=False), _injury_log([])) == 0
    assert not log.exists()


def test_no_injuries_gives_the_m5_forecasts(model: LiveM5, tmp_path: Path) -> None:
    m5_log, inj_log = tmp_path / "m5.csv", tmp_path / "m5inj.csv"
    assert _run_m5(m5_log, NOW, model) > 0
    assert _run_m5inj(inj_log, NOW, model, _injury_log([])) == len(_rows(m5_log))
    m5, inj = _rows(m5_log), _rows(inj_log)
    assert m5.keys() == inj.keys()
    for game in m5:
        forecast = ("model", "model_version")
        assert {k: v for k, v in inj[game].items() if k not in forecast} == {
            k: v for k, v in m5[game].items() if k not in forecast
        }


def test_an_out_player_moves_only_his_teams_games(model: LiveM5, tmp_path: Path) -> None:
    m5_log, inj_log = tmp_path / "m5.csv", tmp_path / "m5inj.csv"
    _run_m5(m5_log, NOW, model)
    m5 = _rows(m5_log)
    team = next(iter(m5.values()))["home"]
    injured = _injury_log([("2022-10-28T09:00:00Z", team, "Alpha Tester", "Out")])
    assert _run_m5inj(inj_log, NOW, model, injured) == len(m5)
    inj = _rows(inj_log)
    moved = {g for g in m5 if m5[g]["p_home"] != inj[g]["p_home"]}
    team_games = {g for g, r in m5.items() if team in (r["home"], r["away"])}
    assert moved and moved <= team_games
    assert all(inj[g]["model"] == "m5inj" for g in inj)
    assert {r["model_version"] for r in inj.values()} == {m5inj_version(model.version)}


def test_a_status_stamped_after_the_cutoff_changes_nothing(model: LiveM5, tmp_path: Path) -> None:
    m5_log, inj_log = tmp_path / "m5.csv", tmp_path / "m5inj.csv"
    _run_m5(m5_log, NOW, model)
    later = _injury_log([("2022-10-29T09:00:00Z", "GRE", "Alpha Tester", "Out")])
    _run_m5inj(inj_log, NOW, model, later)  # NOW is 2022-10-29T08:00Z; the snapshot is after it
    m5, inj = _rows(m5_log), _rows(inj_log)
    assert {g: r["p_home"] for g, r in inj.items()} == {g: r["p_home"] for g, r in m5.items()}


def test_the_version_pins_m5_and_the_rule() -> None:
    assert m5inj_version("0.2.0+m5.d4848a7e").startswith("0.")
    assert "+m5inj." in m5inj_version("0.2.0+m5.d4848a7e")
    assert m5inj_version("0.2.0+m5.d4848a7e") != m5inj_version("0.2.0+m5.other")
