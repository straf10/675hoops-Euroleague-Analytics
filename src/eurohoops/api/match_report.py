"""Match report builders (``docs/match_report.md`` section 2): pure functions over DataFrames.

``api.readmodel.match_report`` gathers the inputs (memoised per Store) and calls these. Every
builder filters to what was known at the game's tip-off itself, so a later game can never leak in
even when the caller passes the whole season. Codes are shown through ``show`` (the display code),
ratings are rounded to 1 dp, shares to 3 dp and per-game values to 1 dp.
"""

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.stats.coach_style import StyleIndex, coach_style

RECENT = 5  # form games per team, head-to-head meetings listed
TOP_PLAYERS = 5
MIN_PLAYER_GAMES = 2
LABELS = {"m1": "Possession model", "m5": "Player model", "elor": "Elo + roster"}
OTHER_MODELS = ("m1", "m5", "elor")  # order of the comparison list
Show = Callable[[str], str]


def utc(value: Any) -> pd.Timestamp:
    """``value`` as a tz-aware UTC timestamp (naive values are taken as UTC)."""
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _tips(frame: pd.DataFrame, column: str = "tipoff_utc") -> pd.Series:
    values = frame[column]
    if isinstance(values.dtype, pd.DatetimeTZDtype):  # memoised frames: already parsed
        return values
    return pd.to_datetime(values, utc=True)


def tip_series(values: pd.Series) -> pd.Series:
    """Tip-off values as UTC datetimes (parsed once in the memoised frames)."""
    return pd.to_datetime(values, utc=True)


def _flag(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].fillna(False).astype(bool)


def _played_before(games: pd.DataFrame, tipoff: pd.Timestamp) -> pd.DataFrame:
    """Played (not forfeited) games that tipped off before ``tipoff``, newest first."""
    tip = _tips(games)
    done = _flag(games, "played") & ~_flag(games, "forfeit") & (tip < tipoff)
    return games[done].assign(_tip=tip[done]).sort_values("_tip", ascending=False, kind="stable")


def _clean(value: Any) -> Any:
    """A text cell as ``str``, NaN and empty strings as None."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    return text or None


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None or not np.isfinite(value) else round(float(value), digits)


# ---- model ----


def model_block(inputs: pd.DataFrame | None, game_id: str, tipoff: pd.Timestamp) -> dict[str, Any]:
    """The published model's inputs and forecast from the pre-registered snapshot row; never null,
    with ``available`` false and the reason when there is none."""
    absent = {"available": False, "reason": None}
    if inputs is None:
        return {**absent, "reason": "no model-input snapshot is recorded for this competition"}
    rows = inputs[inputs["game_id"].astype(str) == game_id]
    if rows.empty:
        return {**absent, "reason": "the model inputs were not recorded for this game"}
    before = rows[pd.to_datetime(rows["predicted_at_utc"], utc=True) < tipoff]
    if before.empty:
        return {**absent, "reason": "the only model-input snapshot was stamped after tip-off"}
    row = before.iloc[0]
    return {
        "available": True,
        "reason": None,
        "home_rating": _round(float(row["home_rating"]), 1),
        "away_rating": _round(float(row["away_rating"]), 1),
        "hca": _round(float(row["hca"]), 1),
        "neutral": bool(row["neutral"]),
        "diff": _round(float(row["diff"]), 1),
        "margin_scale": _round(float(row["margin_scale"]), 4),
        "p_home": float(row["p_home"]),
        "exp_margin": float(row["exp_margin"]),
        "model_version": str(row["model_version"]),
        "predicted_at_utc": str(row["predicted_at_utc"]),
        "source": str(row["source"]),
    }


def other_models(rows: Mapping[str, Mapping[str, Any] | None]) -> list[dict[str, Any]]:
    """The team models' pre-registered forecasts of the game (``rows``: model key -> log row, or
    None when the model logged nothing for it)."""
    out = []
    for key in OTHER_MODELS:
        row = rows.get(key)
        if row is None:
            continue
        out.append(
            {
                "key": key,
                "label": LABELS[key],
                "p_home": float(row["p_home"]),
                "exp_margin": float(row["exp_margin"]),
            }
        )
    return out


# ---- form, head to head ----


def form(games: pd.DataFrame, team: str, tipoff: pd.Timestamp, show: Show) -> list[dict[str, Any]]:
    """The team's last ``RECENT`` played games before tip-off, newest first."""
    mine = _played_before(games, tipoff)
    mine = mine[(mine["home"] == team) | (mine["away"] == team)].head(RECENT)
    out = []
    for g in mine.to_dict("records"):
        at_home = g["home"] == team
        scored = int(g["home_score"] if at_home else g["away_score"])
        allowed = int(g["away_score"] if at_home else g["home_score"])
        out.append(
            {
                "date": g["_tip"].strftime("%Y-%m-%d"),
                "opp": show(g["away"] if at_home else g["home"]),
                "venue": "H" if at_home else "A",
                "for": scored,
                "against": allowed,
                "won": scored > allowed,
            }
        )
    return out


def head_to_head(
    games: pd.DataFrame, home: str, away: str, tipoff: pd.Timestamp, show: Show
) -> dict[str, Any]:
    """Meetings of the two clubs before tip-off (all seasons in ``games``); the last five newest
    first. Win counts are for this game's home and away side."""
    played = _played_before(games, tipoff)
    meet = played[played["home"].isin([home, away]) & played["away"].isin([home, away])]
    own = np.where(meet["home"] == home, meet["home_score"], meet["away_score"]).astype(int)
    opp = np.where(meet["home"] == home, meet["away_score"], meet["home_score"]).astype(int)
    last = []
    for g in meet.head(RECENT).to_dict("records"):
        last.append(
            {
                "date": g["_tip"].strftime("%Y-%m-%d"),
                "season": int(g["season"]),
                "home": show(g["home"]),
                "away": show(g["away"]),
                "home_score": int(g["home_score"]),
                "away_score": int(g["away_score"]),
            }
        )
    return {
        "since": int(games["season"].min()) if not games.empty else None,
        "games": len(meet),
        "home_wins": int((own > opp).sum()),
        "away_wins": int((opp > own).sum()),
        "last": last,
    }


# ---- team stats ----

TEAM_ROWS = (
    ("net_rtg", "Net rating", "signed1", "high"),
    ("off_rtg", "Offensive rating", "num1", "high"),
    ("def_rtg", "Defensive rating", "num1", "low"),
    ("pace", "Pace", "num1", None),
    ("efg_pct", "Effective FG%", "pct1", "high"),
    ("tov_pct", "Turnover rate", "pct1", "low"),
    ("orb_pct", "Offensive rebound rate", "pct1", "high"),
    ("ft_rate", "Free-throw rate", "pct1", "high"),
    ("rest_days", "Days of rest", "num0", "high"),
)


def _ratings(lines: pd.DataFrame, team: str, tipoff: pd.Timestamp, season: int) -> dict[str, Any]:
    """Season ratios of ``team`` over its box lines before tip-off; the opponent's line of each
    game gives points allowed and the defensive rebounds for the rebound rate."""
    before = lines[(lines["season"] == season) & (_tips(lines) < tipoff)]
    mine = before[before["team"] == team]
    opponents = before[["game_id", "team", "pts", "dreb"]].rename(
        columns={"team": "opponent", "pts": "opp_pts", "dreb": "opp_dreb"}
    )
    paired = mine.merge(opponents, on=["game_id", "opponent"], how="inner")
    if paired.empty:
        return {"games": 0}
    s = paired[
        ["fg2m", "fg3m", "fg2a", "fg3a", "fta", "oreb", "tov", "pts", "opp_pts", "poss", "game_sec"]
    ].sum()
    fga = s["fg2a"] + s["fg3a"]
    poss = float(s["poss"])
    return {
        "games": len(paired),
        "net_rtg": 100 * (s["pts"] - s["opp_pts"]) / poss,
        "off_rtg": 100 * s["pts"] / poss,
        "def_rtg": 100 * s["opp_pts"] / poss,
        "pace": 2400 * poss / float(s["game_sec"]),
        "efg_pct": (s["fg2m"] + 1.5 * s["fg3m"]) / fga,
        "tov_pct": s["tov"] / poss,
        "orb_pct": s["oreb"] / (s["oreb"] + paired["opp_dreb"].sum()),
        "ft_rate": s["fta"] / fga,
    }


def team_stats(
    lines: pd.DataFrame | None,
    home: str,
    away: str,
    tipoff: pd.Timestamp,
    *,
    season: int,
    rest: Mapping[str, float | None],
) -> dict[str, Any] | None:
    """The live season's team ratios before tip-off, and each side's rest for this game; None
    without box lines (the rest rows are not published alone). ``rest``: side -> days of rest."""
    if lines is None or lines.empty:
        return None
    sides = {"home": home, "away": away}
    ratings = {side: _ratings(lines, team, tipoff, season) for side, team in sides.items()}
    rows = []
    for key, label, fmt, better in TEAM_ROWS:
        values = {}
        for side in sides:
            if key == "rest_days":
                values[side] = _round(rest.get(side), 1)
            else:
                value = ratings[side].get(key)
                values[side] = None if value is None else _round(value, _digits(fmt))
        rows.append({"key": key, "label": label, **values, "better": better, "format": fmt})
    games = {side: ratings[side]["games"] for side in sides}
    if not any(games.values()):  # no game before tip-off for either side: nothing to compare
        return None
    return {"games": games, "rows": rows}


def _digits(fmt: str) -> int:
    return 3 if fmt.startswith("pct") else 1


# ---- players ----


def top_players(
    players: pd.DataFrame,
    team: str,
    tipoff: pd.Timestamp,
    season: int,
    *,
    names: Mapping[str, str],
    slugs: Mapping[str, str],
) -> list[dict[str, Any]]:
    """The team's top ``TOP_PLAYERS`` by minutes per game before tip-off (at least
    ``MIN_PLAYER_GAMES`` games), with per-game points, rebounds, assists and PIR."""
    before = players[
        (players["season"] == season) & (players["team"] == team) & (_tips(players) < tipoff)
    ]
    if before.empty:
        return []
    grouped = before.groupby("player_id").agg(
        gp=("game_id", "size"),
        sec=("sec", "sum"),
        pts=("pts", "sum"),
        reb=("oreb", "sum"),
        dreb=("dreb", "sum"),
        ast=("ast", "sum"),
        pir=("pir", "sum"),
    )
    grouped["reb"] = grouped["reb"] + grouped["dreb"]
    grouped = grouped[grouped["gp"] >= MIN_PLAYER_GAMES]
    grouped = grouped.assign(min_pg=grouped["sec"] / 60 / grouped["gp"]).sort_values(
        ["min_pg"], ascending=False, kind="stable"
    )
    out = []
    for pid, row in grouped.head(TOP_PLAYERS).iterrows():
        gp = int(row["gp"])
        out.append(
            {
                "name": names.get(str(pid), str(pid)),
                "slug": slugs.get(str(pid), str(pid).lower()),
                "gp": gp,
                "min": _round(row["min_pg"], 1),
                "pts": _round(row["pts"] / gp, 1),
                "reb": _round(row["reb"] / gp, 1),
                "ast": _round(row["ast"] / gp, 1),
                "pir": _round(row["pir"] / gp, 1),
            }
        )
    return out


# ---- injuries ----


def injuries(
    snapshots: pd.DataFrame | None, home: str, away: str, tipoff: pd.Timestamp
) -> dict[str, Any] | None:
    """The latest injury snapshot stamped at or before tip-off, for the two teams; None when no
    snapshot is that early."""
    if snapshots is None or snapshots.empty:
        return None
    stamps = pd.to_datetime(snapshots["snapshot_utc"], utc=True)
    earlier = snapshots[stamps <= tipoff]
    if earlier.empty:
        return None
    latest = pd.to_datetime(earlier["snapshot_utc"], utc=True)
    current = earlier[latest == latest.max()]
    block: dict[str, Any] = {"snapshot_utc": str(current["snapshot_utc"].iloc[0])}
    for side, team in (("home", home), ("away", away)):
        rows = current[current["team"] == team]
        block[side] = [
            {
                "player": _clean(r["player"]),
                "status": _clean(r["status"]),
                "return": _clean(r["return_round"]),
                "comment": _clean(r["comment"]),
            }
            for r in rows.to_dict("records")
        ]
    return block


# ---- coaches ----

# The coach page's definitions (stats/coach_style.coach_style), over the live season's games.
COACH_STYLE = (
    ("ato_ppp", "Points per possession after timeout", "num2"),
    ("clutch_win", "Clutch win %", "pct0"),
    ("challenges", "Challenges per game", "num1"),
)


def coaches(
    coach_rows: pd.DataFrame | None,
    home: str,
    away: str,
    tipoff: pd.Timestamp,
    *,
    season: int,
    style_index: StyleIndex | None,
) -> dict[str, Any] | None:
    """Each side's coach in its latest game before tip-off (name, slug, record of the live season
    and career before tip-off), the two coaches' head-to-head and their live-season style.

    ``coach_rows``: team-game rows with season, game_id, team, opponent, won, slug, name,
    tipoff_utc.
    ``style_index``: the live season's games as ``coach_style.game_styles`` builds them (None
    without the play-by-play cache).
    """
    if coach_rows is None or coach_rows.empty:
        return None
    before = coach_rows[_tips(coach_rows) < tipoff]
    out: dict[str, Any] = {}
    slugs: dict[str, str | None] = {}
    styles: dict[str, dict[str, float | None] | None] = {}
    for side, team in (("home", home), ("away", away)):
        last = before[before["team"] == team].assign(_t=_tips(before)).sort_values("_t")
        if last.empty or _clean(last["slug"].iloc[-1]) is None:
            out[side], slugs[side], styles[side] = None, None, None
            continue
        coach = last.iloc[-1]
        slug = str(coach["slug"])
        slugs[side] = slug
        out[side] = {
            "name": _clean(coach["name"]),
            "slug": slug,
            **_coach_record(before, slug, season, tipoff),
        }
        styles[side] = _style_values(before, slug, season, style_index)
    out["h2h"] = _coach_h2h(before, slugs["home"], slugs["away"])
    out["style"] = _style_rows(styles["home"], styles["away"])
    return out


def _coach_record(
    before: pd.DataFrame, slug: str, season: int, tipoff: pd.Timestamp
) -> dict[str, Any]:
    mine = before[before["slug"] == slug]

    def record(part: pd.DataFrame) -> dict[str, int]:
        wins = int(part["won"].astype(bool).sum())
        return {"wins": wins, "losses": len(part) - wins}

    return {"season": record(mine[mine["season"] == season]), "career": record(mine)}


def _coach_h2h(
    before: pd.DataFrame, home_slug: str | None, away_slug: str | None
) -> dict[str, int]:
    if home_slug is None or away_slug is None or home_slug == away_slug:
        return {"games": 0, "home_wins": 0, "away_wins": 0}
    opposite = before[["game_id", "team", "slug"]].rename(
        columns={"team": "opponent", "slug": "opp_slug"}
    )
    paired = before.merge(opposite, on=["game_id", "opponent"], how="inner")
    # one row per game of the home coach against the away coach: each game counted once
    meetings = paired[(paired["slug"] == home_slug) & (paired["opp_slug"] == away_slug)]
    home_wins = int(meetings["won"].astype(bool).sum())
    return {
        "games": len(meetings),
        "home_wins": home_wins,
        "away_wins": len(meetings) - home_wins,
    }


def _style_values(
    before: pd.DataFrame, slug: str, season: int, index: StyleIndex | None
) -> dict[str, float | None] | None:
    """The coach's style over his games before tip-off, aggregated by the coach page's own code
    (``coach_style.coach_style``); a figure is null when the coach has no qualifying games."""
    if index is None:
        return None
    mine = before[(before["slug"] == slug) & (before["season"] == season)]
    block = coach_style(mine[["season", "game_id", "team", "won"]], index)
    clutch = block["clutch"]
    decided = clutch["wins"] + clutch["losses"]
    challenges = block["challenges"]
    return {
        "ato_ppp": block["ato"]["ppp"],
        "clutch_win": clutch["wins"] / decided if decided else None,
        "challenges": None if challenges is None else challenges["per_game"],
    }


def _style_rows(
    home: dict[str, float | None] | None, away: dict[str, float | None] | None
) -> list[dict[str, Any]] | None:
    if home is None and away is None:
        return None
    digits = {"ato_ppp": 2, "clutch_win": 3, "challenges": 1}
    rows = []
    for key, label, fmt in COACH_STYLE:
        values = {
            side: None if block is None else _round(block[key], digits[key])
            for side, block in (("home", home), ("away", away))
        }
        rows.append({"key": key, "label": label, **values, "format": fmt})
    return rows
