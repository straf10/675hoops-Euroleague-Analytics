"""A small synthetic EuroLeague for the ELOR tests (``models/elor.py``, ``eval/elor_cv.py``).

Four clubs A-D, seasons 2023-2026, four weekly rounds per season, two games per round (every
club plays once per round, the second game an hour after the first). Players ``{club}1`` to
``{club}4`` play every game of their club; ``A4`` moves to B for 2026. Newcomers: ``C5`` first
plays in 2024 (every C game from then on), ``A5`` plays 2025 only, ``D5`` is registered before
2026 and first plays in 2026 round 3. Rosters: every player is registered a month before his
season; in 2026 B also signs ``B9`` after round 2 (never plays, never rated) and ``C3``
leaves C during round 3 (his ``endDate`` is between rounds 3 and 4).

Ratings come through the real ``WalkForwardRatings`` over fake lookups: every player except
``*9`` has a value at every cutoff, so availability is decided only by having played before the
cutoff, as in the real fit.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from eurohoops.config import ElorCv
from eurohoops.eval.elor_cv import ElorInputs
from eurohoops.models.elor import WalkForwardRatings
from eurohoops.models.minutes import round_cutoffs
from eurohoops.models.rapm import RatingLookup
from eurohoops.models.roster import ROSTER_SCHEMA
from eurohoops.parse.schemas import validated

CLUBS = ("A", "B", "C", "D")
SEASONS = (2023, 2024, 2025, 2026)
PAIRINGS = {
    1: (("A", "B"), ("C", "D")),
    2: (("A", "C"), ("B", "D")),
    3: (("A", "D"), ("B", "C")),
    4: (("B", "A"), ("D", "C")),
}
POSSESSIONS = 72.0
D5_DEBUT_ROUND = 3


def season_start(season: int) -> pd.Timestamp:
    return pd.Timestamp(f"{season}-10-01T18:00:00Z")


def round_start(season: int, rnd: int) -> pd.Timestamp:
    return season_start(season) + pd.Timedelta(days=7 * (rnd - 1))


def players_of(club: str, season: int) -> list[str]:
    """The club's registered players for the season."""
    own = [f"{club}{n}" for n in range(1, 5)]
    if season == 2026:
        own = [p for p in own if p != "A4"]
        if club == "B":
            own.append("A4")
        if club == "D":
            own.append("D5")
    if club == "C" and season >= 2024:
        own.append("C5")
    if club == "A" and season == 2025:
        own.append("A5")
    return own


def playing(club: str, season: int, rnd: int) -> list[str]:
    return [
        p
        for p in players_of(club, season)
        if not (p == "D5" and season == 2026 and rnd < D5_DEBUT_ROUND)
    ]


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
                    for player in playing(club, season, rnd):
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


def fake_value(season: int, cutoff: float, player: str) -> float:
    base = sum(ord(ch) for ch in player) % 11 - 5.0
    return base + 0.5 * (season - 2024) + (cutoff % 7) / 100.0


def fake_rating(season: int, cutoff: float, player: str, club: str) -> float | None:
    """Ungated fake (``*9`` players unrated); the unit tests of ``club_strength`` use it."""
    del club
    return None if player.endswith("9") else fake_value(season, cutoff, player)


def ratings(games: pd.DataFrame, player_games: pd.DataFrame) -> WalkForwardRatings:
    """The real ``WalkForwardRatings`` over fake per-cutoff lookups (depend on the cutoff only)."""
    ordered = games.sort_values("tipoff_utc").reset_index(drop=True)
    return WalkForwardRatings(ordered, fake_lookups(ordered), player_games)


def fake_lookups(ordered: pd.DataFrame) -> list[RatingLookup | None]:
    """One fake lookup per game of a tip-off ordered frame (every player but ``*9``)."""
    everyone = sorted({p for c in CLUBS for s in SEASONS for p in players_of(c, s)} | {"B9"})
    lookups: list[RatingLookup | None] = []
    for season, cutoff in zip(
        ordered["season"].astype(int), round_cutoffs(ordered).astype(float), strict=True
    ):
        values = {p: fake_value(season, cutoff, p) for p in everyone if not p.endswith("9")}
        lookups.append(RatingLookup(values, {}))
    return lookups


def inputs(
    games: pd.DataFrame | None = None,
    player_games: pd.DataFrame | None = None,
    rosters: pd.DataFrame | None = None,
) -> ElorInputs:
    base_games, base_box = games_and_box()
    games = base_games if games is None else games
    player_games = base_box if player_games is None else player_games
    rosters = roster() if rosters is None else rosters
    source = ratings(games, player_games)
    return ElorInputs(
        games=games,
        player_games=player_games,
        roster=rosters,
        rating=source,
        has_state=source.has_state,
        possessions=pd.Series(POSSESSIONS, index=games["game_id"].astype(str)),
        season_end_rating=source.at_season_end,
    )


def spec(tmp: Path | None = None, **overrides: object) -> ElorCv:
    root = tmp or Path("unused")
    kw: dict[str, object] = {
        "elo_warmup": (2023, 2024),
        "folds": (2025, 2026),
        "bootstrap_resamples": 200,
        **overrides,
    }
    return ElorCv(root / "elor_cv.json", root / "elor_cv_games.csv", **kw)  # type: ignore[arg-type]
