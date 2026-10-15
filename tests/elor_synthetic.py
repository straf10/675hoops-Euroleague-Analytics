"""A small synthetic EuroLeague for the ELOR tests (``models/elor.py``, ``eval/elor_cv.py``).

Four clubs A-D, seasons 2024-2026, four weekly rounds per season, two games per round (every
club plays once per round, the second game an hour after the first). Players ``{club}1`` to
``{club}4`` play every game of their club; ``A4`` moves to B for 2026. Rosters: every player is
registered a month before his season; in 2026 B also signs ``B9`` after round 2 (no box history)
and ``C3`` leaves C during round 3 (his ``endDate`` is between rounds 3 and 4).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.config import ElorCv
from eurohoops.eval.elor_cv import ElorInputs
from eurohoops.models.roster import ROSTER_SCHEMA
from eurohoops.parse.schemas import validated

CLUBS = ("A", "B", "C", "D")
SEASONS = (2024, 2025, 2026)
PAIRINGS = {
    1: (("A", "B"), ("C", "D")),
    2: (("A", "C"), ("B", "D")),
    3: (("A", "D"), ("B", "C")),
    4: (("B", "A"), ("D", "C")),
}
POSSESSIONS = 72.0


def season_start(season: int) -> pd.Timestamp:
    return pd.Timestamp(f"{season}-10-01T18:00:00Z")


def round_start(season: int, rnd: int) -> pd.Timestamp:
    return season_start(season) + pd.Timedelta(days=7 * (rnd - 1))


def club_of(player: str, season: int) -> str:
    return "B" if player == "A4" and season == 2026 else player[0]


def players_of(club: str, season: int) -> list[str]:
    own = [f"{club}{n}" for n in range(1, 5)]
    if season == 2026:
        own = [p for p in own if club_of(p, season) == club]
        if club == "B":
            own.append("A4")
    return own


def games_and_box(seed: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    games: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for season in SEASONS:
        for rnd, pairs in PAIRINGS.items():
            for i, (home, away) in enumerate(pairs):
                game_id = f"E{season}_{rnd}{i}"
                margin = int(rng.integers(-15, 16)) or 3
                games.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "phase": "RS",
                        "round": rnd,
                        "tipoff_utc": round_start(season, rnd) + pd.Timedelta(hours=i),
                        "home": home,
                        "away": away,
                        "home_score": 80 + max(margin, 0),
                        "away_score": 80 + max(-margin, 0),
                        "played": True,
                        "forfeit": False,
                        "neutral": False,
                    }
                )
                for club in (home, away):
                    for player in players_of(club, season):
                        rows.append(
                            {
                                "game_id": game_id,
                                "team": club,
                                "player_id": player,
                                "sec": int(rng.integers(300, 1500)),
                            }
                        )
    frame = pd.DataFrame(games)
    frame["home_score"] = frame["home_score"].astype("int64")
    frame["away_score"] = frame["away_score"].astype("int64")
    return frame, pd.DataFrame(rows)


def roster() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for season in SEASONS:
        start = (season_start(season) - pd.Timedelta(days=30)).timestamp()
        for club in CLUBS:
            for player in players_of(club, season):
                end = float("nan")
                if season == 2026 and player == "C3":
                    end = (round_start(2026, 3) + pd.Timedelta(days=2)).timestamp()
                rows.append(
                    {"season": season, "club": club, "player_id": player}
                    | {"start": start, "end": end}
                )
    signing = (round_start(2026, 2) + pd.Timedelta(days=2)).timestamp()
    rows.append(
        {"season": 2026, "club": "B", "player_id": "B9", "start": signing, "end": float("nan")}
    )
    return validated(pd.DataFrame(rows, columns=list(ROSTER_SCHEMA.columns)), ROSTER_SCHEMA)


def fake_rating(season: int, cutoff: float, player: str, club: str) -> float | None:
    """Deterministic and walk-forward safe by construction (depends on the cutoff only)."""
    del club
    if player.endswith("9"):
        return None
    base = sum(ord(ch) for ch in player) % 11 - 5.0
    return base + 0.5 * (season - 2024) + (cutoff % 7) / 100.0


def inputs(
    games: pd.DataFrame | None = None,
    player_games: pd.DataFrame | None = None,
    rosters: pd.DataFrame | None = None,
) -> ElorInputs:
    base_games, base_box = games_and_box()
    games = base_games if games is None else games
    player_games = base_box if player_games is None else player_games
    rosters = roster() if rosters is None else rosters
    return ElorInputs(
        games=games,
        player_games=player_games,
        roster=rosters,
        rating=fake_rating,
        has_state=lambda season, cutoff: True,
        possessions=pd.Series(POSSESSIONS, index=games["game_id"].astype(str)),
    )


def spec(tmp: Path | None = None, **overrides: object) -> ElorCv:
    root = tmp or Path("unused")
    kw: dict[str, object] = {
        "elo_warmup": (2024,),
        "folds": (2025, 2026),
        "bootstrap_resamples": 200,
        **overrides,
    }
    return ElorCv(root / "elor_cv.json", root / "elor_cv_games.csv", **kw)  # type: ignore[arg-type]
