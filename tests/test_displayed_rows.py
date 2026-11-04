"""``displayed_rows``: the one log row shown for each game, shared by the site build and the API.

The reference functions are frozen copies of the two implementations it replaced, in
``publish._logged`` and ``api.readmodel._ordered``: the new rule must equal the first everywhere
and the second everywhere except a game with several late rows and no on-time one, where the
second kept the latest late row against its own docstring."""

import numpy as np
import pandas as pd
import pytest

from eurohoops.logs import displayed_rows
from eurohoops.predict import LOG_COLUMNS

TIP = "2026-10-01T18:00:00Z"


def row(game_id: str, stamp: str, p_home: str, tipoff: str = TIP) -> dict[str, str]:
    return {
        "game_id": game_id,
        "season": "2026",
        "round": "1",
        "phase": "RS",
        "tipoff_utc": tipoff,
        "home": "AAA",
        "away": "BBB",
        "p_home": p_home,
        "exp_margin": "1.00",
        "model": "elo",
        "model_version": "v1",
        "predicted_at_utc": stamp,
    }


def log_of(rows: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=list(LOG_COLUMNS))


def pick(log: pd.DataFrame) -> dict[str, tuple[str, bool]]:
    shown = displayed_rows(log)
    assert shown["game_id"].is_unique
    return {r["game_id"]: (r["p_home"], bool(r["late"])) for r in shown.to_dict("records")}


def test_the_latest_row_before_tipoff_is_shown() -> None:
    log = log_of(
        [
            row("G1", "2026-10-01T10:00:00Z", "0.6000"),
            row("G1", "2026-10-01T17:30:00Z", "0.7000"),
            row("G1", "2026-10-01T11:00:00Z", "0.5000"),
        ]
    )
    assert pick(log) == {"G1": ("0.7000", False)}


def test_an_on_time_row_beats_any_late_one() -> None:
    log = log_of(
        [
            row("G1", "2026-10-01T10:00:00Z", "0.6000"),
            row("G1", "2026-10-01T19:00:00Z", "0.9000"),  # late
        ]
    )
    assert pick(log) == {"G1": ("0.6000", False)}


def test_a_game_with_only_late_rows_shows_the_first_one_logged() -> None:
    log = log_of(
        [
            row("G1", "2026-10-01T20:00:00Z", "0.8000"),
            row("G1", "2026-10-01T19:00:00Z", "0.9000"),  # the earliest late row
            row("G1", "2026-10-01T21:00:00Z", "0.7000"),
        ]
    )
    assert pick(log) == {"G1": ("0.9000", True)}


def test_a_stamp_exactly_at_tipoff_is_late() -> None:
    assert pick(log_of([row("G1", TIP, "0.5000")])) == {"G1": ("0.5000", True)}


def test_each_game_is_judged_on_its_own_tipoff() -> None:
    log = log_of(
        [
            row("G1", "2026-10-01T10:00:00Z", "0.6000"),
            row("G2", "2026-10-01T10:00:00Z", "0.4000", tipoff="2026-10-01T09:00:00Z"),
        ]
    )
    assert pick(log) == {"G1": ("0.6000", False), "G2": ("0.4000", True)}


def test_the_columns_are_the_log_plus_late() -> None:
    shown = displayed_rows(log_of([row("G1", "2026-10-01T10:00:00Z", "0.6000")]))
    assert list(shown.columns) == [*LOG_COLUMNS, "late"]


# --- against the implementations it replaced -------------------------------------------------


def old_publish(log: pd.DataFrame) -> pd.DataFrame:
    stamps = pd.to_datetime(log["predicted_at_utc"], utc=True)
    tips = pd.to_datetime(log["tipoff_utc"], utc=True)
    marked = log.assign(late=stamps >= tips, _stamp=stamps)
    on_time = marked[~marked["late"]].sort_values("_stamp").drop_duplicates("game_id", keep="last")
    after = marked[marked["late"]].sort_values("_stamp").drop_duplicates("game_id", keep="first")
    after = after[~after["game_id"].isin(on_time["game_id"])]
    return pd.concat([on_time, after]).drop(columns="_stamp")


def old_readmodel(log: pd.DataFrame) -> pd.DataFrame:
    late = pd.to_datetime(log["predicted_at_utc"], utc=True) >= pd.to_datetime(
        log["tipoff_utc"], utc=True
    )
    stamped = pd.to_datetime(log["predicted_at_utc"], utc=True)
    ordered = log.assign(late=late, _stamped=stamped).sort_values(
        ["late", "_stamped"], ascending=[True, False], kind="stable"
    )
    return ordered.drop(columns="_stamped").drop_duplicates("game_id", keep="first")


def random_log(seed: int, games: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    tip = pd.Timestamp(TIP)
    rows = []
    for g in range(games):
        for _ in range(int(rng.integers(1, 5))):
            stamp = tip + pd.Timedelta(minutes=int(rng.integers(-600, 120)))
            rows.append(row(f"G{g}", stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), f"{rng.uniform():.4f}"))
    return pd.DataFrame(rows)


def several_late_only(log: pd.DataFrame) -> list[str]:
    """Games with two or more rows, all stamped at or after tip-off."""
    late = pd.to_datetime(log["predicted_at_utc"], utc=True) >= pd.to_datetime(
        log["tipoff_utc"], utc=True
    )
    counts = log.assign(late=late).groupby("game_id")["late"].agg(["sum", "size"])
    edge = counts[(counts["sum"] == counts["size"]) & (counts["size"] > 1)]
    return list(edge.index)


@pytest.mark.parametrize("seed", range(6))
def test_it_is_the_old_publish_selection_everywhere(seed: int) -> None:
    log = random_log(seed)
    new = displayed_rows(log).sort_values("game_id").reset_index(drop=True)
    old = old_publish(log).sort_values("game_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(new, old)


@pytest.mark.parametrize("seed", range(6))
def test_it_is_the_old_readmodel_selection_except_for_several_late_rows(seed: int) -> None:
    log = random_log(seed)
    new = displayed_rows(log).set_index("game_id").sort_index()
    old = old_readmodel(log).set_index("game_id").sort_index()
    edge = several_late_only(log)
    same = new.index.difference(edge)
    pd.testing.assert_frame_equal(new.loc[same], old.loc[same])


def test_the_old_readmodel_really_differed_on_several_late_rows() -> None:
    log = random_log(0, games=200)
    edge = several_late_only(log)
    assert edge, "the random log should contain the edge case"
    new = displayed_rows(log).set_index("game_id")
    old = old_readmodel(log).set_index("game_id")
    stamp = "predicted_at_utc"
    differing = [g for g in edge if new.loc[g, stamp] != old.loc[g, stamp]]
    assert differing  # it kept the latest late row; the shared rule keeps the earliest
    for g in differing:
        assert new.loc[g, stamp] < old.loc[g, stamp]
