import json
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from eurohoops.config import Backtest
from eurohoops.eval.eurocup import (
    B0_ABOVE_ELO,
    ELO_ABOVE_B0,
    NO_RANKING,
    elo_vs_b0,
    ranking_verdict,
)
from eurohoops.ingest.euroleague import (
    MIN_INTERVAL_S,
    PastSeasonNotCachedError,
    ingest_seasons,
)
from eurohoops.ingest.http import Fetcher
from eurohoops.parse.games import parse_schedule
from tests.conftest import FIXTURES


@pytest.mark.usefixtures("no_sleep")
def test_eurocup_uses_code_u_and_its_own_cache_and_refuses_unseeded_past(tmp_path: Path) -> None:
    urls: list[str] = []
    body = (FIXTURES / "schedule_E2024.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, content=body)

    fetcher = Fetcher(httpx.Client(transport=httpx.MockTransport(handler)), MIN_INTERVAL_S)
    with pytest.raises(PastSeasonNotCachedError, match="U2024 schedule"):
        ingest_seasons(fetcher, tmp_path, [2024], False, 2026, code="U")
    assert urls == []

    ingest_seasons(fetcher, tmp_path, [2024], False, 2026, code="U", fetch_missing=True)
    assert urls == ["https://api-live.euroleague.net/v2/competitions/U/seasons/U2024/games"]
    assert (tmp_path / "schedule" / "U2024.json.gz").exists()
    assert not (tmp_path / "schedule" / "E2024.json.gz").exists()

    ingest_seasons(fetcher, tmp_path, [2024], False, 2026, code="U")
    assert len(urls) == 1  # cached: never refetched


def _raw_game(game_code: int, phase: str, home: int, away: int) -> dict:
    games = json.loads((FIXTURES / "schedule_E2024.json").read_text(encoding="utf-8"))["data"]
    game = next(g for g in games if g["played"])
    game["gameCode"], game["identifier"] = game_code, f"E2024_{game_code}"
    game["phaseType"] = {**game["phaseType"], "code": phase}
    game["local"]["score"], game["road"]["score"] = home, away
    return game


def test_eurocup_knockout_codes_read_as_playoffs_and_20_0_is_a_forfeit() -> None:
    frame = parse_schedule(2024, [_raw_game(1, "L16", 80, 75), _raw_game(2, "Final", 20, 0)])
    assert list(frame["phase"]) == ["PO", "PO"]
    assert list(frame["forfeit"]) == [False, True]


def _synthetic_games(seasons: range, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(8)]
    rows = []
    tip = 0
    for season in seasons:
        for _ in range(120):
            home, away = rng.choice(teams, size=2, replace=False)
            strength = 6.0 if home < away else -6.0
            margin = round(rng.normal(strength, 12.0))
            home_score = 80 + max(margin, 0)
            away_score = 80 + max(-margin, 0)
            if home_score == away_score:
                home_score += 1
            rows.append(
                {
                    "game_id": f"U{season}_{tip}",
                    "season": season,
                    "game_code": tip,
                    "phase": "RS",
                    "round": 1,
                    "round_label": "Round 1",
                    "tipoff_utc": pd.Timestamp("2000-01-01", tz="UTC") + pd.Timedelta(hours=tip),
                    "home": str(home),
                    "away": str(away),
                    "home_score": home_score,
                    "away_score": away_score,
                    "played": True,
                    "forfeit": False,
                    "neutral": False,
                }
            )
            tip += 1
    return pd.DataFrame(rows)


def test_elo_vs_b0_scores_only_test_seasons_and_names_a_verdict() -> None:
    games = _synthetic_games(range(2007, 2012))
    spec = Backtest(Path("unused.json"), warmup=(2007,), tuning=(2008, 2009), test=(2010, 2011))
    result = elo_vs_b0(games, spec)
    assert result["games"]["test"] == int(games["season"].isin([2010, 2011]).sum())
    assert result["games"]["tuning"] == int(games["season"].isin([2008, 2009]).sum())
    assert result["gap_elo_minus_b0"]["test"]["n"] == result["games"]["test"]
    assert result["verdict"] in {ELO_ABOVE_B0, B0_ABOVE_ELO, NO_RANKING}


@pytest.mark.parametrize(
    ("mean", "lower", "upper", "verdict"),
    [
        (-0.02, -0.03, -0.005, ELO_ABOVE_B0),  # mean far enough and CI below zero
        (-0.02, -0.03, 0.001, NO_RANKING),  # CI reaches zero
        (-0.005, -0.02, -0.001, NO_RANKING),  # mean smaller than the bar
        (0.02, 0.003, 0.04, B0_ABOVE_ELO),
        (0.02, -0.003, 0.04, NO_RANKING),
    ],
)
def test_pass_bar(mean: float, lower: float, upper: float, verdict: str) -> None:
    assert ranking_verdict(mean, lower, upper) == verdict
