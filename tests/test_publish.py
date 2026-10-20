import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from pytest import MonkeyPatch

from eurohoops.eval.backtest import TunedModel
from eurohoops.models.elo import EloParams
from eurohoops.predict import LOG_COLUMNS
from eurohoops.publish import (
    DISPLAY_CODES,
    SHORT_NAMES,
    Section,
    section_data,
    short_name,
    site_data,
)
from tests.conftest import make_games

NOW = datetime(2026, 10, 8, 8, 0, tzinfo=UTC)
CARD = {
    "elo": {"n": 3, "log_loss": 0.61, "brier": 0.21, "accuracy": 2 / 3, "margin_mae": 9.5},
    "b0": {"n": 3, "log_loss": 0.66, "brier": 0.23, "accuracy": 0.6, "margin_mae": 9.9},
    "rolling": {"window": 50, "series": []},
}
REPORT = {
    "seasons": {"warmup": [2024], "tuning": [2025], "test": [2025]},
    "tuned": {"k": 20.0, "hca": 90.0, "reversion": 0.25},
    "metrics": {"test": CARD},
    "test_log_loss_diff_elo_minus_b0": {"mean": -0.05, "ci95": [-0.08, -0.02]},
}
MODEL = TunedModel(EloParams(k=20.0, hca=90.0, reversion=0.25), 25.0, 0.63, 3.7)


def stamp_of(ts: pd.Timestamp) -> str:
    return str(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))


def section(card: dict[str, object] = CARD, logged_rounds: int = 2) -> Section:
    games = make_games({2025: True, 2026: False})
    played = (games["season"] == 2026) & (games["round"] == 1)
    games.loc[played, ["home_score", "away_score", "played"]] = [90, 80, True]
    live = games[(games["season"] == 2026) & (games["round"] <= logged_rounds)]
    log = pd.DataFrame(
        [
            [
                *(g.game_id, 2026, g.round, "RS", stamp_of(g.tipoff_utc), g.home, g.away),
                *(0.4, -2.0, "elo", "v1", stamp),
            ]
            for g in live.itertuples()
            for stamp in ("2026-09-30T08:00:00Z", "2026-09-30T09:00:00Z")  # a re-log
        ],
        columns=list(LOG_COLUMNS),
    )
    names = {"AAA": "Ολυμπιακός & <Co>"}
    return Section("gbl", "Greek Basket League", log, card, REPORT, games, names, MODEL, 2026, 2025)


def test_upcoming_results_and_scorecard() -> None:
    data = section_data(section(), NOW)
    assert data["season"] == "2026-27"
    assert data["logged"] == 6  # one row per game: the latest before tip-off
    assert len(data["upcoming"]) == 3
    assert len(data["results"]) == 3
    result = data["results"][0]
    assert (result["home_score"], result["away_score"]) == (90, 80)
    assert not result["hit"]  # p_home 0.4 but the home team won
    assert result["provable"]
    assert result["predicted_at_utc"] == "2026-09-30T09:00:00Z"
    assert data["scorecard"]["elo"]["log_loss"] == 0.61
    assert data["scorecard"]["not_provable"] == 0
    assert data["backtest"]["params"] == {"k": 20.0, "hca": 90.0, "reversion": 0.25}
    assert data["backtest"]["log_loss_diff"]["ci95"] == [-0.08, -0.02]
    assert data["next_tipoff_utc"] == data["upcoming"][0]["tipoff_utc"]


def test_ratings_cover_the_live_season_and_keep_raw_names() -> None:
    ratings = section_data(section(), NOW)["ratings"]
    assert len(ratings) == 6
    assert [r["rating"] for r in ratings] == sorted((r["rating"] for r in ratings), reverse=True)
    assert any(r["name"] == "Ολυμπιακός & <Co>" for r in ratings)  # escaping is the page's job
    assert all(isinstance(r["change"], float) for r in ratings)


def test_unprovable_games_are_flagged() -> None:
    plain = section()
    first = plain.games.loc[
        (plain.games["season"] == 2026) & (plain.games["round"] == 1), "game_id"
    ].iloc[0]
    data = section_data(section({**CARD, "games_not_provable": [first]}), NOW)
    assert data["scorecard"]["not_provable"] == 1
    assert [r["provable"] for r in data["results"]].count(False) == 1


def test_site_without_a_log_is_json_ready() -> None:
    empty = Section(
        "euroleague",
        "EuroLeague",
        pd.DataFrame(),
        CARD,
        REPORT,
        make_games({2026: False}),
        {},
        MODEL,
        2026,
        2026,
    )
    data = site_data([empty], NOW, {"games": 0, "seasons": 0, "shots_with_coordinates": 0})
    json.dumps(data)
    comp = data["competitions"][0]
    assert comp["upcoming"] == comp["results"] == []
    assert comp["logged"] == 0
    assert data["generated_at_utc"] == "2026-10-08T08:00:00Z"


def test_display_codes_rename_only_what_the_site_shows(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setitem(DISPLAY_CODES, "gbl", {"AAA": "OLY"})
    data = section_data(section(), NOW)
    rated = {r["code"]: r["name"] for r in data["ratings"]}
    assert rated["OLY"] == "Ολυμπιακός & <Co>"  # the name is still looked up by the source code
    assert "AAA" not in rated
    teams = {t["code"] for g in data["upcoming"] + data["results"] for t in (g["home"], g["away"])}
    assert "AAA" not in teams


def test_display_codes_are_unique_per_competition() -> None:
    for codes in DISPLAY_CODES.values():
        assert len(set(codes.values())) == len(codes)


def test_rows_logged_after_tip_off_are_shown_apart_and_never_scored() -> None:
    """A game whose only rows were stamped at or after tip-off (a hand-logged row) is late: it
    is flagged apart from the unprovable games and never counted as a hit or a miss."""
    plain = section()
    first_round = plain.games[(plain.games["season"] == 2026) & (plain.games["round"] == 1)]
    late_id, late_tip = first_round["game_id"].iloc[0], first_round["tipoff_utc"].iloc[0]
    log = plain.log.copy()
    log.loc[log["game_id"] == late_id, "predicted_at_utc"] = stamp_of(late_tip)
    data = section_data(dataclasses.replace(plain, log=log), NOW)
    late = next(r for r in data["results"] if r["game_id"] == late_id)
    assert late["late"] and not late["provable"]
    assert [r["late"] for r in data["results"]].count(True) == 1
    assert data["scorecard"]["late"] == 1
    assert data["scorecard"]["not_provable"] == 0


def test_an_on_time_row_wins_over_an_earlier_listed_late_one() -> None:
    """If a game has both, the pick is its latest row stamped before tip-off.

    A row stamped after tip-off never counts.
    """
    plain = section()
    game = plain.games[(plain.games["season"] == 2026) & (plain.games["round"] == 1)].iloc[0]
    late = (
        plain.log[plain.log["game_id"] == game["game_id"]]
        .iloc[:1]
        .assign(
            predicted_at_utc="2026-09-29T08:00:00Z", tipoff_utc="2026-09-29T07:00:00Z", p_home=0.9
        )
    )
    data = section_data(dataclasses.replace(plain, log=pd.concat([late, plain.log])), NOW)
    row = next(r for r in data["results"] if r["game_id"] == game["game_id"])
    assert not row["late"] and row["provable"]
    assert row["p_home"] == 0.4


def test_next_tip_off_skips_games_without_a_confirmed_time() -> None:
    """A GBL game without a confirmed time sits at 00:00 Athens; it is never the next tip-off."""
    plain = section()
    games = plain.games.copy()
    ahead = games[(games["season"] == 2026) & ~games["played"]].index
    games.loc[ahead[0], "confirmed_date"] = False
    data = section_data(dataclasses.replace(plain, games=games), NOW)
    assert data["next_tipoff_utc"] == stamp_of(games.loc[ahead[1], "tipoff_utc"])
    assert data["next_tipoff_time_tbc"] is False


def test_next_tip_off_is_a_date_with_time_tbc_when_no_time_is_confirmed() -> None:
    plain = section()
    games = plain.games.assign(confirmed_date=False)
    data = section_data(dataclasses.replace(plain, games=games), NOW)
    first = games[(games["season"] == 2026) & ~games["played"]]["tipoff_utc"].min()
    assert data["next_tipoff_utc"] == stamp_of(first)
    assert data["next_tipoff_time_tbc"] is True


def test_matchday_lists_every_round_of_the_live_season_with_its_window() -> None:
    rounds = section_data(section(), NOW)["matchday"]["rounds"]
    assert [r["round"] for r in rounds] == sorted(
        {g.round for g in make_games({2026: False}).itertuples()}
    )
    first = rounds[0]
    assert first["start_utc"] <= min(g["tipoff_utc"] for g in first["games"])
    assert first["end_utc"] > max(g["tipoff_utc"] for g in first["games"])
    played = first["games"][0]
    assert played["played"] and (played["home_score"], played["away_score"]) == (90, 80)
    assert played["p_home"] == 0.4 and played["hit"] is False  # the pick was away; home won
    assert all(g["hit"] is None for g in rounds[1]["games"] if not g["played"])
    assert rounds[1]["games"][0]["p_home"] is not None  # logged before tip-off
    assert rounds[-1]["games"][0]["p_home"] is None  # not logged yet


def test_short_name_is_the_source_code_entry_or_the_full_name() -> None:
    assert short_name("euroleague", "PAN", "Panathinaikos AKTOR Athens") == "Panathinaikos"
    assert short_name("euroleague", "XXX", "Some Club") == "Some Club"  # no entry: full name


def test_every_club_in_the_data_has_a_short_name() -> None:
    # The club list of the built stats (display codes); the short names are keyed by source code.
    meta = Path("web/src/data/stats/meta.json")
    if not meta.exists():
        pytest.skip("no built stats data (run export-stats first)")
    shown = [club["code"] for club in json.loads(meta.read_text(encoding="utf-8"))["clubs"]]
    source = {v: k for k, v in DISPLAY_CODES["euroleague"].items()}
    missing = [code for code in shown if source.get(code, code) not in SHORT_NAMES["euroleague"]]
    assert missing == [], f"clubs without a short name: {missing}"


def _round_games(data: dict[str, object], number: int) -> list[dict[str, object]]:
    rounds = {r["round"]: r["games"] for r in data["open_rounds"]}  # type: ignore[index]
    return rounds.get(number, [])  # type: ignore[return-value]


def test_every_open_round_is_listed_in_round_order() -> None:
    """Rounds with a logged forecast and a game left to play are open, earliest round first. A
    round with every game played is not open (it is a recap)."""
    data = section_data(section(logged_rounds=3), NOW)
    assert [r["round"] for r in data["open_rounds"]] == [2, 3]
    assert [g["played"] for g in _round_games(data, 2)] == [False, False, False]


def test_a_round_with_every_game_played_is_not_open() -> None:
    data = section_data(section(logged_rounds=2), NOW)
    assert [r["round"] for r in data["open_rounds"]] == [2]  # round 1 was played in full


def test_an_open_round_shows_played_games_with_score_and_hit() -> None:
    plain = section(logged_rounds=2)
    games = plain.games.copy()
    round_two = games[(games["season"] == 2026) & (games["round"] == 2)].index
    games.loc[round_two[0], ["home_score", "away_score", "played"]] = [70, 85, True]
    data = section_data(dataclasses.replace(plain, games=games), NOW)
    rows = _round_games(data, 2)
    done = rows[0]
    assert done["played"] and (done["home_score"], done["away_score"]) == (70, 85)
    assert done["hit"] is True  # the pick favoured away (0.4 home) and away won
    assert all(not g["played"] and g["hit"] is None and g["home_score"] is None for g in rows[1:])
    assert all(g["p_home"] == 0.4 and g["exp_margin"] == -2.0 for g in rows)


def test_a_round_is_open_while_one_of_its_games_is_unfinished() -> None:
    plain = section(logged_rounds=2)
    games = plain.games.copy()
    round_two = games[(games["season"] == 2026) & (games["round"] == 2)]
    games.loc[round_two.index, ["home_score", "away_score", "played"]] = [80, 79, True]
    games.loc[round_two.index[-1], ["home_score", "away_score", "played"]] = [None, None, False]
    data = section_data(dataclasses.replace(plain, games=games), NOW)
    assert [r["round"] for r in data["open_rounds"]] == [2]


def test_the_pick_is_the_latest_row_stamped_before_tip_off() -> None:
    """A game re-logged before tip-off shows its newest pick, not the first one logged."""
    plain = section(logged_rounds=2)
    game_id = _round_games(section_data(plain, NOW), 2)[0]["game_id"]
    log = plain.log.copy()
    mine = log["game_id"] == game_id
    log.loc[mine, "p_home"] = 0.4
    log.loc[mine & (log["predicted_at_utc"] == "2026-09-30T09:00:00Z"), "p_home"] = 0.7
    log.loc[mine & (log["predicted_at_utc"] == "2026-09-30T08:00:00Z"), "p_home"] = 0.2
    data = section_data(dataclasses.replace(plain, log=log), NOW)
    row = next(g for g in _round_games(data, 2) if g["game_id"] == game_id)
    assert row["p_home"] == 0.7
    assert row["predicted_at_utc"] == "2026-09-30T09:00:00Z"
    assert data["matchday"]["rounds"][1]["games"][0]["p_home"] == 0.7
