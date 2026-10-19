"""Coach checks of the audit: coach team-game rows (``stats.coaches.coach_games``) vs the games.

The rows come from the cached EuroLeague box scores. A side's ``won`` must equal the game result,
each game has one winner, a coach never sits on both sides of a game, and a coach's name and slug
map one to one. A coach at two clubs in one season is explained when the two stints do not overlap
in time (a mid-season change); overlapping stints are unexplained.

An unnamed side is judged game by game against its cached box score: when the raw box has no
coach field for that side the source has none (explained); when the raw box names a coach that the
rows do not carry, that is a parser fault (unexplained). A box that is missing or not matched to
its game is unexplained too.
"""

from collections.abc import Mapping

import pandas as pd

from eurohoops.audit import Finding
from eurohoops.parse.coach_names import EXCLUDED

COACH_CHANGE = "mid-season change: the two club stints do not overlap in time"
NO_SOURCE = "source has no coach: the cached box score names no coach for this side"
PLACEHOLDER = "source placeholder: the cached box names XX or SSS, which name no coach"


def _finding(name: str, bad: list[str], explained: dict[str, int]) -> Finding:
    """A finding from its unexplained labels and its explained counts by reason."""
    return Finding(
        name=name,
        count=len(bad) + sum(explained.values()),
        unexplained=len(bad),
        examples=bad[:5],
        reasons=explained,
    )


def _result_mismatches(rows: pd.DataFrame, games: pd.DataFrame) -> list[str]:
    result = games.set_index("game_id")
    home_won = rows["game_id"].map(result["home_score"] > result["away_score"])
    is_home = rows["team"] == rows["game_id"].map(result["home"])
    wrong = rows[rows["won"].to_numpy() != (is_home == home_won).to_numpy()]
    return [f"{row['game_id']} {row['team']}" for _, row in wrong.iterrows()]


def _unnamed(
    rows: pd.DataFrame, raw_coach: Mapping[tuple[str, str], str]
) -> tuple[list[str], dict[str, int]]:
    """Unnamed sides, judged against the raw box score of their game (``raw_coach``: game, team
    -> the coach field as printed, empty when the box has none)."""
    bad: list[str] = []
    explained: dict[str, int] = {}
    for row in rows[rows["slug"].isna()].itertuples():
        label = f"{row.game_id} {row.team}"
        raw = raw_coach.get((str(row.game_id), str(row.team)))
        if raw is None:
            bad.append(f"{label} (no cached box score for this side)")
        elif raw in EXCLUDED:
            explained[PLACEHOLDER] = explained.get(PLACEHOLDER, 0) + 1
        elif raw:
            bad.append(f"{label} (box names '{raw}'; the rows carry no coach: parser fault)")
        else:
            explained[NO_SOURCE] = explained.get(NO_SOURCE, 0) + 1
    return bad, explained


def _two_clubs(named: pd.DataFrame) -> tuple[list[str], int]:
    bad: list[str] = []
    explained = 0
    for (season, slug), stints in named.groupby(["season", "slug"]):
        if stints["team"].nunique() < 2:
            continue
        spans = stints.groupby("team")["tipoff_utc"].agg(["min", "max"]).sort_values("min")
        overlap = (spans["min"].iloc[1:].to_numpy() < spans["max"].iloc[:-1].to_numpy()).any()
        if overlap:
            bad.append(f"{season} {slug}")
        else:
            explained += 1
    return bad, explained


def coach_findings(
    rows: pd.DataFrame,
    games: pd.DataFrame,
    raw_coach: Mapping[tuple[str, str], str] | None = None,
) -> list[Finding]:
    """One finding per coach check, for the coach rows of ``games``.

    ``raw_coach`` maps (game_id, team) to the raw coach field of every cached box score side;
    without it every unnamed side is unexplained.
    """
    raw = dict(raw_coach or {})
    named = rows.dropna(subset=["slug"])
    sides = rows.groupby("game_id").size()
    winners = rows.groupby("game_id")["won"].sum()
    bad_games = [str(g) for g in winners.index[(winners != 1) | (sides != 2)]]
    per_game = named.groupby("game_id")["slug"].agg(["size", "nunique"])
    both_sides = [
        str(g) for g in per_game.index[(per_game["size"] == 2) & (per_game["nunique"] == 1)]
    ]
    unnamed_bad, unnamed_explained = _unnamed(rows, raw)
    change_bad, change_explained = _two_clubs(named)
    name_slug = named.groupby("slug")["name"].nunique()
    slug_name = named.groupby("name")["slug"].nunique()
    clashes = [f"slug {s}" for s in name_slug.index[name_slug > 1]]
    clashes += [f"name {n}" for n in slug_name.index[slug_name > 1]]
    uncovered = sorted({game for game, _ in raw} - set(rows["game_id"].astype(str)))
    return [
        _finding("coach_result_mismatch", _result_mismatches(rows, games), {}),
        _finding("coach_one_winner_per_game", bad_games, {}),
        _finding("coach_on_both_sides", both_sides, {}),
        _finding("coach_side_unnamed", unnamed_bad, unnamed_explained),
        _finding("coach_two_clubs_same_season", change_bad, {COACH_CHANGE: change_explained}),
        _finding("coach_name_slug_clash", sorted(clashes), {}),
        _finding(
            "coach_game_without_rows", [f"{g} (box cached, no coach rows)" for g in uncovered], {}
        ),
    ]
