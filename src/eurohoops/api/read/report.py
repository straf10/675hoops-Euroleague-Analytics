"""The match report's inputs (docs/match_report.md); the builders are in api/match_report.py."""

from typing import Any

import pandas as pd

from eurohoops.api import match_report as mr
from eurohoops.api.read.stats import coach_rows
from eurohoops.api.read.store import NotFound, Store, cached, jsonable
from eurohoops.api.read.teams import schedule_rest
from eurohoops.config import (
    EUROLEAGUE,
    INJURY_LOG,
    LIVE_SEASON,
    Competition,
)
from eurohoops.logs import displayed_rows
from eurohoops.model_catalog import entry
from eurohoops.publish import team_identity
from eurohoops.stats.coach_style import StyleIndex, game_styles
from eurohoops.stats.export import (
    display_name,
    player_slugs,
)


@cached
def _report_games(store: Store, comp: Competition) -> pd.DataFrame:
    """The competition's games with tip-off as UTC datetimes (the builders compare them)."""
    games = store.games(comp)
    return games.assign(tipoff_utc=mr.tip_series(games["tipoff_utc"]))


def report_game_ids(store: Store, competition: str) -> list[str]:
    """The live season's game ids in the competition's Elo log: each gets a report."""
    log = store.log(store.competition(competition).prediction_log)
    live = log[log["season"] == LIVE_SEASON]
    return list(dict.fromkeys(live["game_id"].astype(str)))


@cached
def _inputs_frame(store: Store, comp: Competition) -> pd.DataFrame | None:
    """The model-input snapshot log (``predictions/<comp>_inputs_<season>.csv``), or None."""
    relative = getattr(comp, "inputs_log", None)
    if relative is None or not store.path(relative).exists():
        return None
    return pd.read_csv(store.path(relative), dtype={"game_id": str})


@cached
def _pre_rows(store: Store, comp: Competition, model: str) -> dict[str, dict[str, Any]]:
    """The pre-registered row of each game in one team model's log (empty when not logged)."""
    relative = entry(model).log_path(comp)
    log = displayed_rows(store.log(relative))
    return {str(r["game_id"]): {str(k): v for k, v in r.items()} for r in log.to_dict("records")}


def _el_tipoffs(store: Store) -> dict[str, Any]:
    games = store.games(EUROLEAGUE)
    return dict(zip(games["game_id"].astype(str), games["tipoff_utc"], strict=True))


@cached
def _el_match_lines(store: Store) -> pd.DataFrame:
    """EuroLeague team box lines with each game's tip-off (the team ratios of a report)."""
    teams = store.euroleague_box().teams
    return teams.assign(
        tipoff_utc=mr.tip_series(teams["game_id"].astype(str).map(_el_tipoffs(store)))
    )


@cached
def _el_match_players(store: Store) -> pd.DataFrame:
    """EuroLeague player box lines with each game's tip-off."""
    players = store.euroleague_box().players
    return players.assign(
        tipoff_utc=mr.tip_series(players["game_id"].astype(str).map(_el_tipoffs(store)))
    )


@cached
def _player_names_slugs(store: Store) -> tuple[dict[str, str], dict[str, str]]:
    """Player id -> display name (the stats site's spelling) and -> URL slug (``player_slugs``)."""
    players = store.euroleague_box().players
    latest = players.drop_duplicates("player_id", keep="last")
    names = {
        str(pid): display_name(str(raw))
        for pid, raw in zip(latest["player_id"], latest["player"], strict=True)
    }
    return names, player_slugs(names)


def _injury_snapshots(store: Store) -> pd.DataFrame | None:
    """The injury log (append-only snapshots), or None when no snapshot file exists."""
    if not store.path(INJURY_LOG).exists():
        return None
    return _read_injuries(store)


@cached
def _read_injuries(store: Store) -> pd.DataFrame:
    return pd.read_csv(store.path(INJURY_LOG), dtype=str, keep_default_na=True)


@cached
def _coach_rows(store: Store) -> pd.DataFrame | None:
    """EuroLeague team-game coach rows with the walk-forward Elo (None without its history), tip-off
    as UTC datetimes."""
    rows = coach_rows(store, store.games(EUROLEAGUE))
    if rows is None:
        return None
    return rows.assign(tipoff_utc=mr.tip_series(rows["tipoff_utc"]))


def _live_style_index(store: Store) -> StyleIndex | None:
    """The live season's EuroLeague games' style, built by ``coach_style.game_styles`` (the coach
    pages' own per-game records); None without the coach history (no coach pages)."""
    if _coach_rows(store) is None:
        return None
    return _live_styles(store)


@cached
def _live_styles(store: Store) -> StyleIndex:
    games = store.games(EUROLEAGUE)
    return game_styles(store.path(EUROLEAGUE.raw_dir), games[games["season"] == LIVE_SEASON])


def _side(comp: Competition, code: str, names: dict[str, str]) -> dict[str, str]:
    """A team of a match report: the display code the page shows, and its name."""
    team = team_identity(comp.name, code, names)
    return {"code": team.display_code, "name": team.name}


def match_report(store: Store, competition: str, game_id: str) -> dict[str, Any]:
    """One game's match report (``docs/match_report.md`` section 2): the published model's inputs
    and forecast, the other models, and the context known before tip-off."""
    comp = store.competition(competition)
    games = _report_games(store, comp)
    found = games[games["game_id"].astype(str) == game_id]
    if found.empty:
        raise NotFound(f"no game '{game_id}' in {comp.name}")
    game = found.iloc[0]
    season, home, away = int(game["season"]), str(game["home"]), str(game["away"])
    tipoff = mr.utc(game["tipoff_utc"])
    names = store.team_names(comp)

    def show(code: str) -> str:
        return team_identity(comp.name, code).display_code

    played = bool(game["played"]) and not bool(game["forfeit"])
    result = {"home": int(game["home_score"]), "away": int(game["away_score"])} if played else None
    is_el = comp is EUROLEAGUE
    rest = schedule_rest(store, comp)
    team_stats = (
        mr.team_stats(
            _el_match_lines(store),
            home,
            away,
            tipoff,
            season=season,
            rest={"home": rest.get((game_id, home)), "away": rest.get((game_id, away))},
        )
        if is_el
        else None
    )
    player_names, slugs = _player_names_slugs(store) if is_el else ({}, {})
    players = (
        {
            side: mr.top_players(
                _el_match_players(store), team, tipoff, season, names=player_names, slugs=slugs
            )
            for side, team in (("home", home), ("away", away))
        }
        if is_el
        else None
    )
    coaches = (
        mr.coaches(
            _coach_rows(store),
            home,
            away,
            tipoff,
            season=season,
            style_index=_live_style_index(store),
        )
        if is_el
        else None
    )
    out: dict[str, Any] = jsonable(
        {
            "game_id": game_id,
            "competition": comp.name,
            "season": season,
            "round": int(game["round"]),
            "phase": game["phase"],
            "tipoff_utc": game["tipoff_utc"],
            "home": _side(comp, home, names),
            "away": _side(comp, away, names),
            "result": result,
            "model": mr.model_block(_inputs_frame(store, comp), game_id),
            "other_models": mr.other_models(
                {model: _pre_rows(store, comp, model).get(game_id) for model in mr.OTHER_MODELS}
            ),
            "form": {
                "home": mr.form(games, home, tipoff, show),
                "away": mr.form(games, away, tipoff, show),
            },
            "h2h": mr.head_to_head(games, home, away, tipoff, show),
            "team_stats": team_stats,
            "players": players,
            "injuries": (
                mr.injuries(_injury_snapshots(store), home, away, tipoff) if is_el else None
            ),
            "coaches": coaches,
        }
    )
    return out
