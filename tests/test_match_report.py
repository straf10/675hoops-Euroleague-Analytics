"""Match report builders (``api/match_report.py``) on small synthetic frames, and the export
mapping of ``/reports/...`` (``api/export.py``). Expected values are hand-computed from the rows."""

from pathlib import PurePosixPath

import pandas as pd

from eurohoops.api import match_report as mr
from eurohoops.api.export import file_for, route_for
from eurohoops.stats.coach_style import GameStyle, StyleIndex, TeamGame, Totals, coach_style

SHOWN = {"AAA": "PAO", "BBB": "FBT", "CCC": "VBC"}


def show(code: str) -> str:
    return SHOWN.get(code, code)


def _games() -> pd.DataFrame:
    """G1-G3 are played before G4's tip-off (2026-10-22); G5 tips off after it and never leaks."""
    return pd.DataFrame(
        {
            "game_id": ["G1", "G2", "G3", "G4", "G5"],
            "season": [2026, 2026, 2026, 2026, 2026],
            "round": [1, 2, 3, 4, 5],
            "phase": ["RS"] * 5,
            "tipoff_utc": pd.to_datetime(
                [
                    "2026-10-01T18:00:00Z",
                    "2026-10-08T18:00:00Z",
                    "2026-10-15T18:00:00Z",
                    "2026-10-22T18:00:00Z",
                    "2026-10-29T18:00:00Z",
                ],
                utc=True,
            ),
            "home": ["AAA", "BBB", "AAA", "AAA", "AAA"],
            "away": ["BBB", "AAA", "CCC", "BBB", "BBB"],
            "home_score": [80, 70, 90, 0, 100],
            "away_score": [75, 85, 88, 0, 50],
            "played": [True, True, True, False, True],
            "forfeit": [False, False, False, False, False],
        }
    )


TIP = pd.Timestamp("2026-10-22T18:00:00Z")


def _lines(games: pd.DataFrame) -> pd.DataFrame:
    """Two box lines per game: 70 possessions each, the game's points, 2400 seconds."""
    rows = []
    tips = dict(zip(games["game_id"], games["tipoff_utc"], strict=True))
    for g in games.itertuples(index=False):
        for team, opp, pts in ((g.home, g.away, g.home_score), (g.away, g.home, g.away_score)):
            rows.append(
                {
                    "season": 2026,
                    "game_id": g.game_id,
                    "team": team,
                    "opponent": opp,
                    "fg2m": 20,
                    "fg3m": 8,
                    "fg2a": 50,
                    "fg3a": 20,
                    "fta": 20,
                    "oreb": 10,
                    "dreb": 30,
                    "tov": 12,
                    "pts": pts,
                    "poss": 70.0,
                    "game_sec": 2400,
                    "tipoff_utc": tips[g.game_id],
                }
            )
    return pd.DataFrame(rows)


def test_form_is_the_last_games_before_tip_off_newest_first() -> None:
    rows = mr.form(_games(), "AAA", TIP, show)
    assert [r["date"] for r in rows] == ["2026-10-15", "2026-10-08", "2026-10-01"]
    assert [r["opp"] for r in rows] == ["VBC", "FBT", "FBT"]  # display codes
    assert [r["venue"] for r in rows] == ["H", "A", "H"]
    assert rows[0] == {
        "date": "2026-10-15",
        "opp": "VBC",
        "venue": "H",
        "for": 90,
        "against": 88,
        "won": True,
    }
    assert all(r["won"] for r in rows)  # AAA won G1, G2 and G3


def test_form_caps_at_five_and_skips_unplayed_games() -> None:
    games = _games()
    many = pd.concat(
        [
            games.iloc[[0]].assign(
                game_id=f"X{i}",
                tipoff_utc=pd.Timestamp("2026-09-01T18:00:00Z") + pd.Timedelta(days=i),
            )
            for i in range(7)
        ]
        + [games],
        ignore_index=True,
    )
    rows = mr.form(many, "AAA", TIP, show)
    assert len(rows) == 5
    assert rows[0]["date"] == "2026-10-15"


def test_head_to_head_counts_meetings_before_tip_off_only() -> None:
    h2h = mr.head_to_head(_games(), "AAA", "BBB", TIP, show)
    # G1 (AAA at home, won), G2 (BBB at home, AAA won). G5 (AAA home, won 100-50) is later.
    assert h2h["games"] == 2
    assert h2h["home_wins"] == 2
    assert h2h["away_wins"] == 0
    assert h2h["since"] == 2026
    assert [m["date"] for m in h2h["last"]] == ["2026-10-08", "2026-10-01"]  # newest first
    assert h2h["last"][0] == {
        "date": "2026-10-08",
        "season": 2026,
        "home": "FBT",
        "away": "PAO",
        "home_score": 70,
        "away_score": 85,
    }


def test_head_to_head_lists_the_last_five_of_many_meetings() -> None:
    meetings = pd.DataFrame(
        {
            "game_id": [f"M{i}" for i in range(8)],
            "season": [2025] * 8,
            "round": list(range(1, 9)),
            "phase": ["RS"] * 8,
            "tipoff_utc": pd.to_datetime(
                [f"2026-0{i + 1}-01T18:00:00Z" for i in range(8)], utc=True
            ),
            "home": ["AAA", "BBB"] * 4,
            "away": ["BBB", "AAA"] * 4,
            "home_score": [60 + i for i in range(8)],
            "away_score": [50] * 8,
            "played": [True] * 8,
            "forfeit": [False] * 8,
        }
    )
    h2h = mr.head_to_head(meetings, "AAA", "BBB", pd.Timestamp("2026-12-01T00:00:00Z"), show)
    assert h2h["games"] == 8
    assert len(h2h["last"]) == 5
    assert [m["home_score"] for m in h2h["last"]] == [67, 66, 65, 64, 63]  # newest first


def test_team_ratings_use_only_lines_before_tip_off() -> None:
    games = _games()
    lines = _lines(games)
    # A huge later line for AAA must not move any rating
    later = lines.iloc[[0]].assign(game_id="G5", pts=200, opponent="BBB", team="AAA", poss=70.0)
    later["tipoff_utc"] = pd.Timestamp("2026-10-29T18:00:00Z")
    stats = mr.team_stats(
        pd.concat([lines, later], ignore_index=True),
        "AAA",
        "BBB",
        TIP,
        season=2026,
        rest={"home": 2.0, "away": None},
    )
    assert stats is not None
    assert stats["games"] == {"home": 3, "away": 2}
    rows = {r["key"]: r for r in stats["rows"]}
    # AAA scored 255 in 3 games on 210 possessions; allowed 233 (G1 75, G2 70, G3 88)
    assert rows["off_rtg"]["home"] == 121.4
    assert rows["def_rtg"]["home"] == 111.0
    assert rows["net_rtg"]["home"] == 10.5  # 22 points over 210 possessions
    assert rows["pace"]["home"] == 70.0  # 70 possessions per 40 minutes
    assert rows["efg_pct"]["home"] == round((3 * 20 + 1.5 * 3 * 8) / 210, 3)  # 0.457
    assert rows["rest_days"] == {
        "key": "rest_days",
        "label": "Days of rest",
        "home": 2.0,
        "away": None,
        "better": "high",
        "format": "num0",
    }


def test_team_stats_without_lines_is_null() -> None:
    assert mr.team_stats(None, "AAA", "BBB", TIP, season=2026, rest={}) is None


def test_top_players_by_minutes_with_at_least_two_games_before_tip_off() -> None:
    def line(pid: str, game: str, sec: int, pts: int, tip: str) -> dict[str, object]:
        return {
            "season": 2026,
            "game_id": game,
            "team": "AAA",
            "player_id": pid,
            "sec": sec,
            "pts": pts,
            "oreb": 1,
            "dreb": 2,
            "ast": 3,
            "pir": 10,
            "tipoff_utc": pd.Timestamp(tip),
        }

    rows = [
        line("P1", "G1", 1800, 10, "2026-10-01T18:00:00Z"),
        line("P1", "G2", 1800, 20, "2026-10-08T18:00:00Z"),
        line("P2", "G1", 2400, 30, "2026-10-01T18:00:00Z"),  # one game: excluded
        line("P3", "G1", 600, 4, "2026-10-01T18:00:00Z"),
        line("P3", "G2", 600, 4, "2026-10-08T18:00:00Z"),
        line("P3", "G3", 600, 4, "2026-10-15T18:00:00Z"),
        line("P1", "G5", 2400, 99, "2026-10-29T18:00:00Z"),  # after tip-off
    ]
    players = pd.DataFrame(rows)
    top = mr.top_players(
        players,
        "AAA",
        TIP,
        2026,
        names={"P1": "Ada Lovelace", "P3": "Bo Bench"},
        slugs={"P1": "ada-lovelace", "P3": "bo-bench"},
    )
    assert [p["name"] for p in top] == ["Ada Lovelace", "Bo Bench"]
    assert top[0] == {
        "name": "Ada Lovelace",
        "slug": "ada-lovelace",
        "gp": 2,
        "min": 30.0,
        "pts": 15.0,
        "reb": 3.0,
        "ast": 3.0,
        "pir": 10.0,
    }
    assert top[1]["gp"] == 3 and top[1]["min"] == 10.0


def test_injuries_take_the_latest_snapshot_at_or_before_tip_off() -> None:
    snapshots = pd.DataFrame(
        {
            "snapshot_utc": [
                "2026-10-10T09:00:00Z",
                "2026-10-20T09:00:00Z",
                "2026-10-20T09:00:00Z",
                "2026-10-23T09:00:00Z",
            ],
            "page_updated_utc": ["x"] * 4,
            "team": ["AAA", "AAA", "BBB", "AAA"],
            "team_name_bn": ["n"] * 4,
            "player": ["Old Hurt", "New Hurt", "Away Hurt", "After Hurt"],
            "bn_player_id": ["1", "2", "3", "4"],
            "position": ["G"] * 4,
            "status": ["Out", "Doubtful", "Out", "Out"],
            "return_round": ["Round 9", None, "Round 7", "Round 12"],
            "comment": ["Ankle", "Knee", None, "Back"],
        }
    )
    block = mr.injuries(snapshots, "AAA", "BBB", TIP)
    assert block is not None
    assert block["snapshot_utc"] == "2026-10-20T09:00:00Z"
    assert block["home"] == [
        {"player": "New Hurt", "status": "Doubtful", "return": None, "comment": "Knee"}
    ]
    assert block["away"] == [
        {"player": "Away Hurt", "status": "Out", "return": "Round 7", "comment": None}
    ]


def test_injuries_without_an_early_enough_snapshot_are_null() -> None:
    snapshots = pd.DataFrame(
        {
            "snapshot_utc": ["2026-10-23T09:00:00Z"],
            "page_updated_utc": ["x"],
            "team": ["AAA"],
            "team_name_bn": ["n"],
            "player": ["Late"],
            "bn_player_id": ["1"],
            "position": ["G"],
            "status": ["Out"],
            "return_round": [None],
            "comment": [None],
        }
    )
    assert mr.injuries(snapshots, "AAA", "BBB", TIP) is None
    assert mr.injuries(None, "AAA", "BBB", TIP) is None


def _inputs(**overrides: object) -> pd.DataFrame:
    row = {
        "game_id": "G4",
        "season": 2026,
        "round": 4,
        "phase": "RS",
        "tipoff_utc": "2026-10-22T18:00:00Z",
        "home": "AAA",
        "away": "BBB",
        "home_rating": 1612.44,
        "away_rating": 1588.0,
        "hca": 90.0,
        "neutral": False,
        "diff": 114.44,
        "margin_scale": 28.1234,
        "p_home": "0.6573",
        "exp_margin": "4.07",
        "model": "elo",
        "model_version": "0.2.0+425e6393",
        "predicted_at_utc": "2026-10-20T08:12:00Z",
        "source": "logged",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_model_block_is_the_pre_registered_snapshot() -> None:
    block = mr.model_block(_inputs(), "G4", TIP)
    assert block["available"] is True and block["reason"] is None
    assert block["home_rating"] == 1612.4
    assert block["diff"] == 114.4
    assert block["margin_scale"] == 28.1234
    assert block["p_home"] == 0.6573
    assert block["exp_margin"] == 4.07
    assert block["source"] == "logged"


def test_missing_snapshot_is_unavailable_with_a_reason() -> None:
    no_file = mr.model_block(None, "G4", TIP)
    assert no_file["available"] is False and "no model-input snapshot" in no_file["reason"]
    other = mr.model_block(_inputs(game_id="G9"), "G4", TIP)
    assert other["available"] is False and other["reason"]
    late = mr.model_block(_inputs(predicted_at_utc="2026-10-23T08:00:00Z"), "G4", TIP)
    assert late["available"] is False and "after tip-off" in late["reason"]


def test_other_models_list_only_the_models_that_logged_the_game() -> None:
    rows = {
        "m1": {"p_home": 0.61, "exp_margin": 3.2},
        "m5": None,
        "elor": {"p_home": 0.64, "exp_margin": 3.9},
    }
    out = mr.other_models(rows)
    assert [m["key"] for m in out] == ["m1", "elor"]
    assert out[0]["label"] == "Possession model"
    assert out[1]["label"] == "Elo + roster"


def _coach_rows() -> pd.DataFrame:
    games = _games()
    rows = []
    coach = {"AAA": "coach-a", "BBB": "coach-b", "CCC": "coach-c"}
    for g in games[games["played"] & (games["game_id"] != "G5")].itertuples(index=False):
        home_won = g.home_score > g.away_score
        for team, opp, won in ((g.home, g.away, home_won), (g.away, g.home, not home_won)):
            rows.append(
                {
                    "season": 2026,
                    "game_id": g.game_id,
                    "team": team,
                    "opponent": opp,
                    "won": won,
                    "slug": coach[team],
                    "name": coach[team].upper(),
                    "tipoff_utc": g.tipoff_utc,
                }
            )
    # a later game of coach-a's team, after tip-off: must not count
    rows.append(
        {
            "season": 2026,
            "game_id": "G5",
            "team": "AAA",
            "opponent": "BBB",
            "won": True,
            "slug": "coach-a",
            "name": "COACH-A",
            "tipoff_utc": pd.Timestamp("2026-10-29T18:00:00Z"),
        }
    )
    return pd.DataFrame(rows)


def test_coaches_use_the_latest_game_before_tip_off_and_count_each_meeting_once() -> None:
    block = mr.coaches(_coach_rows(), "AAA", "BBB", TIP, season=2026, style_index=None)
    assert block is not None
    assert block["home"]["slug"] == "coach-a"
    assert block["home"]["season"] == {"wins": 3, "losses": 0}  # G1, G2, G3 only
    assert block["away"]["slug"] == "coach-b"
    assert block["away"]["career"] == {"wins": 0, "losses": 2}
    assert block["h2h"] == {"games": 2, "home_wins": 2, "away_wins": 0}
    assert block["style"] is None  # no play-by-play index


def _index(styles: dict[str, GameStyle]) -> StyleIndex:
    """A style index as ``coach_style.game_styles`` builds it (league totals per season)."""
    totals = Totals()
    for style in styles.values():
        for team in style.teams.values():
            totals.add_team(style.season, style.clutch, team)
    return StyleIndex(games=styles, seasons={2026: totals})


def _styles(clutch: bool) -> dict[str, GameStyle]:
    return {
        "G1": GameStyle(
            season=2026,
            clutch=clutch,
            teams={
                "AAA": TeamGame(4, 6, 1, 1, None, None),
                "BBB": TeamGame(2, 1, 0, 0, None, None),
            },
        ),
        "G2": GameStyle(
            season=2026,
            clutch=False,
            teams={
                "AAA": TeamGame(6, 6, 0, 0, None, None),
                "BBB": TeamGame(2, 2, 0, 0, None, None),
            },
        ),
    }


def test_coach_style_is_the_coach_page_aggregation_over_the_same_games() -> None:
    index = _index(_styles(clutch=True))
    block = mr.coaches(_coach_rows(), "AAA", "BBB", TIP, season=2026, style_index=index)
    assert block is not None
    style = {r["key"]: r for r in block["style"]}
    # the coach page's own code over coach-a's two games before tip-off
    rows = _coach_rows()
    mine = rows[(rows["slug"] == "coach-a") & (rows["game_id"].isin(["G1", "G2"]))]
    page = coach_style(mine[["season", "game_id", "team", "won"]], index)
    assert style["ato_ppp"]["home"] == round(page["ato"]["ppp"], 2) == 1.2  # 12 pts / 10 poss
    assert style["challenges"]["home"] == round(page["challenges"]["per_game"], 1) == 0.5
    assert style["clutch_win"]["home"] == 1.0  # the one clutch game was won
    assert style["ato_ppp"]["away"] == 0.75  # coach-b: 3 pts / 4 poss
    assert style["clutch_win"]["away"] == 0.0  # coach-b lost his one clutch game
    assert style["challenges"]["away"] == 0.0


def test_style_is_null_not_zero_without_qualifying_games() -> None:
    no_clutch = mr.coaches(
        _coach_rows(), "AAA", "BBB", TIP, season=2026, style_index=_index(_styles(clutch=False))
    )
    assert no_clutch is not None
    assert {r["key"]: r for r in no_clutch["style"]}["clutch_win"]["home"] is None
    empty = mr.coaches(_coach_rows(), "AAA", "BBB", TIP, season=2026, style_index=_index({}))
    assert empty is not None
    assert all(r["home"] is None and r["away"] is None for r in empty["style"])


def test_style_counts_only_games_before_tip_off() -> None:
    styles = _styles(clutch=True)
    styles["G5"] = GameStyle(
        season=2026, clutch=True, teams={"AAA": TeamGame(50, 90, 0, 0, None, None)}
    )
    block = mr.coaches(_coach_rows(), "AAA", "BBB", TIP, season=2026, style_index=_index(styles))
    assert block is not None
    assert {r["key"]: r for r in block["style"]}["ato_ppp"]["home"] == 1.2


def test_a_report_builder_never_reads_a_later_game() -> None:
    # The same frames with every game after the tip-off removed give the same context.
    games = _games()
    full = mr.head_to_head(games, "AAA", "BBB", TIP, show)
    cut = mr.head_to_head(games[games["game_id"] != "G5"], "AAA", "BBB", TIP, show)
    assert full == cut


def test_export_maps_a_report_to_its_file_and_back() -> None:
    route = "/reports/euroleague/E2026_61"
    file = file_for(route)
    assert file == PurePosixPath("src/data/api/reports/euroleague/E2026_61.json")
    assert route_for(file) == route
