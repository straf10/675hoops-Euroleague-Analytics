"""Player, team and shot tables -> the JSON files the stats pages read (``web/src/data/stats``).

Layout (every number a raw total; the site derives per-game, per-36 and per-100 rates):

- ``meta.json``: seasons with their coverage, field lists, distance bands, hex size, team names,
  and every club since 2007-08 with the seasons it played (all seasons, not only the published).
- ``players.json``: every player once (id, display name, URL slug, seasons played).
- ``splits.json``: one row per player, season and club (the number he wore most there and his
  totals), for career, best-season and club views.
- ``seasons/{season}/players.json``: one row per player-season: totals for the season and for
  his last 5/10/20 games (a window is left out when he played no more games than it holds),
  and attempts/makes per distance band.
- ``seasons/{season}/teams.json``: team and opponent totals, record, bands taken and allowed, and
  each club's returning minutes (``continuity``: last season's seconds, the share still on the
  roster, the top departures and returners; null with no roster list or no last season).
- ``seasons/{season}/games.json``: the games and every player's game log.
- ``seasons/{season}/shots.json``: hex bins for the league, each team (taken and allowed) and
  each player.
- ``seasons/{season}/attempts.json``: every located attempt (court centimetres, packed flags for
  make, value, fastbreak, second chance, band and period, player and team indices) for the
  Shots explorer's filters.
- ``seasons/{season}/runs.json``: each game's top scoring runs per team (``stats/runs.py``).
- ``seasons/{season}/wp.json``: each game's in-game win-probability line, top swings and control
  parts (``stats/wp.py``, the frozen WP v1 model).
- ``seasons/{season}/units.json``: each club's best duos and five-man units, only in the seasons
  that pass the stint checks (``stats/units.py``).
- ``seasons/{season}/assists.json``: per club, AS rows linked to their made basket, passer-to-scorer
  pairs and per-passer totals (``stats/assists.py``).

Team codes are the source codes up to here; ``codes`` renames them for display (DISPLAY_CODES).
"""

import json
import re
import shutil
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eurohoops.config import SITE_SEASONS
from eurohoops.ingest.cache import read_cached
from eurohoops.ingest.euroleague import RawGame
from eurohoops.models.continuity import club_share, player_continuity, season_start_roster
from eurohoops.parse.games import ATHENS, build_games_table, build_teams_table
from eurohoops.standings import Result, rank
from eurohoops.stats.achievements import achievements_payload
from eurohoops.stats.assists import AssistRow, assists_payload
from eurohoops.stats.box import STATS, BoxGames
from eurohoops.stats.runs import runs_payload
from eurohoops.stats.shots import BANDS, HEX_RADIUS_M, Shots, band_counts, band_table, hexbins
from eurohoops.stats.wp import WpLines, wp_payload

STATS_DIR = Path("web/src/data/stats")  # read by the Astro build in web/
WINDOWS = (5, 10, 20)
TEAM_TOTALS = ("tm_fga", "tm_fgm", "tm_fta", "tm_tov", "tm_poss", "tm_oreb", "tm_dreb")
OPP_TOTALS = ("opp_oreb", "opp_dreb")
PLAYER_FIELDS = ("gp", "gs", "sec", *STATS, "pm", "poss", "game_sec", *TEAM_TOTALS, *OPP_TOTALS)
TEAM_FIELDS = ("gp", *STATS, "poss", "game_sec")
LOG_FIELDS = ("game_id", "team", "starter", "sec", *STATS, "pm")
GAME_FIELDS = (
    "date",
    "round",
    "phase",
    "home",
    "away",
    "home_score",
    "away_score",
    "tipoff_utc",
    "venue",
    "venue_address",
)
# attempts.json ``flags``: bit -> meaning (``band`` takes three bits, ``period`` the rest)
ATTEMPT_BITS = {"made": 0, "three": 1, "fastbreak": 2, "second_chance": 3, "band": 4, "period": 7}


@dataclass(frozen=True)
class Inputs:
    games: pd.DataFrame  # games table (one competition)
    names: Mapping[str, str]  # source team code -> club name
    box: BoxGames
    shots: Shots
    codes: Mapping[str, str]  # source team code -> display code
    live_season: int
    # Official final regular-season tables from the cached standings feed: season -> code -> place
    official_standings: Mapping[int, Mapping[str, int]] = field(default_factory=dict)
    positions: Mapping[str, Mapping[int, str]] = field(
        default_factory=dict
    )  # id -> season -> G/F/C
    # game id -> top scoring runs per side (stats/runs.py); no entry without a cached play-by-play
    runs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    # EuroLeague season roster lists (models/roster.py); None: no returning-minutes values
    roster: pd.DataFrame | None = None
    # season -> best duos and units (stats/units.py); only the seasons that pass the stint checks
    units: Mapping[int, Mapping[str, Any]] = field(default_factory=dict)
    # game id -> the assist rows of its play-by-play (stats/assists.py); no entry without one
    assists: Mapping[str, Sequence[AssistRow]] = field(default_factory=dict)
    # in-game WP lines of the frozen v1 model (stats/wp.py); None: no seasons.wp files
    wp: WpLines | None = None


def load_cached_games(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Games and teams tables from the cached schedules (no marts; nothing is fetched)."""
    schedules: dict[int, list[RawGame]] = {
        int(path.name.removeprefix("E").split(".")[0]): json.loads(read_cached(path))["data"]
        for path in sorted((raw_dir / "schedule").glob("E*.json.gz"))
    }
    return build_games_table(schedules), build_teams_table(schedules)


def load_cached_standings(raw_dir: Path) -> dict[int, dict[str, int]]:
    """Season -> source team code -> place, from the latest cached regular-season standings."""
    latest: dict[int, tuple[int, Path]] = {}
    for path in sorted((raw_dir / "standings").glob("E*_r*.xml")):
        year, _, rounds = path.stem.removeprefix("E").partition("_r")
        if int(year) not in latest or int(rounds) > latest[int(year)][0]:
            latest[int(year)] = (int(rounds), path)
    out: dict[int, dict[str, int]] = {}
    for year_at, (_, path) in latest.items():
        group = ET.fromstring(path.read_text(encoding="utf-8")).find("group")
        if group is not None:
            places = {str(t.findtext("code")): int(t.findtext("ranking") or 0) for t in group}
            out[year_at] = {code: place for code, place in places.items() if place > 0}
    return out


def display_name(raw: str) -> str:
    """``"DE COLO, NANDO"`` -> ``"Nando De Colo"``; ``Mc``, ``O'``, ``II``-``IV`` stay capital.

    Two-letter words without a vowel are initials (``TJ``, ``DJ``, ``KC``), bar ``Jr`` and ``Mc``.
    """
    last, _, first = raw.partition(",")
    name = " ".join(part.strip() for part in (first, last) if part.strip()).title()
    name = re.sub(r"\b(Ii|Iii|Iv)\b", lambda m: m.group(1).upper(), name)
    name = re.sub(r"\b(?!Jr\b|Mc\b)[^\W\daeiouy]{2}\b", lambda m: m[0].upper(), name, flags=re.I)
    return re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), name)


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def player_slugs(names: Mapping[str, str]) -> dict[str, str]:
    """Player id -> URL slug from the display name; ids sharing a name all get the id appended."""
    base = {pid: slugify(name) or pid.lower() for pid, name in names.items()}
    taken = pd.Series(base).value_counts()
    return {
        pid: slug if taken[slug] == 1 else f"{slug}-{pid.lower()}" for pid, slug in base.items()
    }


def site_window(seasons: Iterable[Any]) -> list[int]:
    """The seasons the site publishes: the latest ``SITE_SEASONS`` of those with box lines."""
    return sorted({int(s) for s in seasons})[-SITE_SEASONS:]


def season_label(season: int) -> str:
    return f"{season}-{(season + 1) % 100:02d}"


def _num(value: Any) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else round(number, 1)


def _row(values: np.ndarray[Any, Any]) -> list[int | float]:
    return [_num(v) for v in values]


def _player_frame(inputs: Inputs) -> pd.DataFrame:
    """Player game lines with tip-off, starter flag and his team's totals, in game order."""
    teams = inputs.box.teams.assign(
        tm_fga=lambda t: t["fg2a"] + t["fg3a"], tm_fgm=lambda t: t["fg2m"] + t["fg3m"]
    ).rename(
        columns={
            "fta": "tm_fta",
            "tov": "tm_tov",
            "poss": "tm_poss",
            "oreb": "tm_oreb",
            "dreb": "tm_dreb",
        }
    )[["game_id", "team", *TEAM_TOTALS]]
    opponents = inputs.box.teams[["game_id", "team", "oreb", "dreb"]].rename(
        columns={"team": "opponent", "oreb": "opp_oreb", "dreb": "opp_dreb"}
    )
    frame = inputs.box.players.merge(teams, on=["game_id", "team"], validate="many_to_one")
    frame = frame.merge(opponents, on=["game_id", "opponent"], validate="many_to_one")
    frame = frame.merge(
        inputs.games[["game_id", "tipoff_utc"]], on="game_id", validate="many_to_one"
    )
    return frame.assign(gp=1, gs=frame["starter"].astype(int)).sort_values(
        ["tipoff_utc", "game_id"], kind="stable"
    )


def _windows(values: np.ndarray[Any, Any]) -> dict[str, list[int | float]]:
    out = {"season": _row(values.sum(axis=0))}
    for n in WINDOWS:
        if len(values) > n:
            out[f"last{n}"] = _row(values[-n:].sum(axis=0))
    return out


def _players_payload(
    season: int, frame: pd.DataFrame, shots: pd.DataFrame, inputs: Inputs, slugs: Mapping[str, str]
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    bands = band_table(shots, "player_id")
    for key, lines in frame.groupby("player_id", sort=False):
        pid = str(key)
        pos = inputs.positions.get(pid, {}).get(season)
        rows.append(
            {
                "id": pid,
                "name": display_name(str(lines["player"].iloc[-1])),
                "slug": slugs[pid],
                "teams": [inputs.codes.get(t, t) for t in dict.fromkeys(lines["team"])],
                "dorsal": str(lines["dorsal"].iloc[-1]),
                "totals": _windows(lines[list(PLAYER_FIELDS)].to_numpy(dtype=float)),
                "bands": bands.get(pid, {b: [0, 0] for b in BANDS}),
                **({"pos": pos} if pos else {}),
            }
        )
    rows.sort(key=lambda r: (-r["totals"]["season"][PLAYER_FIELDS.index("pts")], r["id"]))
    return {"season": season, "fields": list(PLAYER_FIELDS), "bands": list(BANDS), "players": rows}


def _splits_payload(frame: pd.DataFrame, inputs: Inputs) -> dict[str, Any]:
    """One row per player, season and club: the number he wore most there, and his totals."""
    rows: list[list[Any]] = []
    for (pid, season, team), lines in frame.groupby(["player_id", "season", "team"], sort=False):
        worn = lines["dorsal"].value_counts(sort=False)  # first-worn order breaks ties
        rows.append(
            [
                str(pid),
                int(str(season)),
                inputs.codes.get(str(team), str(team)),
                str(worn.idxmax()),
                _row(lines[list(PLAYER_FIELDS)].to_numpy(dtype=float).sum(axis=0)),
            ]
        )
    rows.sort(key=lambda r: (r[0], r[1]))  # stable: clubs stay in the order he joined them
    return {"fields": list(PLAYER_FIELDS), "rows": rows}


RESULTS = (
    "Champions",
    "Runners-up",
    "Third place",
    "Fourth place",
    "Lost in the playoffs",
    "Lost in the play-in",
    "Did not qualify",
)
# Not in RESULTS because the data cannot tell: a Final Four without its third-place game, a
# Top 16 exit (2007-08 to 2015-16) and a season with no playoff games at all (2019-20).
OTHER_RESULTS = ("Lost in the semifinals", "Lost in the Top 16", "Season cancelled")


def regular_season_standings(
    games: pd.DataFrame, official: Mapping[str, int] | None
) -> dict[str, int]:
    """Team -> place (1 = top): the official final table when it matches the games' records,
    else ``standings.rank`` (wins, then head-to-head, point difference...) on the played games."""
    played = games[(games["phase"] == "RS") & games["played"]]
    results = [
        Result(str(g["home"]), str(g["away"]), int(g["home_score"]), int(g["away_score"]))
        for g in played.to_dict("records")
    ]
    order = rank(results)
    computed = {team: place for place, team in enumerate(order, start=1)}
    if official and set(official) == set(computed):
        wins: dict[str, int] = {}
        for r in results:
            wins[r.winner] = wins.get(r.winner, 0) + 1
        # a stale or partial table is rejected: places must be consistent with the wins
        by_place = sorted(official, key=lambda t: official[t])
        if all(wins.get(a, 0) >= wins.get(b, 0) for a, b in pairwise(by_place)):
            return dict(official)
    return computed


def playoff_results(games: pd.DataFrame, teams: Iterable[str]) -> dict[str, str]:
    """Team -> how its season ended, from the games' phases (PI play-in, PO playoffs, FF Final
    Four; TS is the old Top 16). The Final Four's two earliest games are the semifinals; of the
    rest the later is the final and the earlier the third-place game."""
    played = games[games["played"]].sort_values(["tipoff_utc", "game_id"], kind="stable")
    phases = {p: played[played["phase"] == p] for p in ("PI", "PO", "FF", "TS")}
    in_phase = {p: {str(t) for t in (*df["home"], *df["away"])} for p, df in phases.items()}
    out = {t: "Did not qualify" for t in teams}
    if not in_phase["PO"] and not in_phase["FF"]:
        return dict.fromkeys(out, "Season cancelled")
    for team in in_phase["TS"]:
        out[team] = "Lost in the Top 16"
    for team in in_phase["PI"]:
        out[team] = "Lost in the play-in"
    for team in in_phase["PO"]:
        out[team] = "Lost in the playoffs"
    final_four = phases["FF"]
    if len(final_four) >= 3:
        semis, rest = final_four.iloc[:2], final_four.iloc[2:]

        def loser(g: Any) -> str:
            return str(g.away if g.home_score > g.away_score else g.home)

        def winner(g: Any) -> str:
            return str(g.home if g.home_score > g.away_score else g.away)

        for g in semis.itertuples(index=False):
            out[loser(g)] = "Lost in the semifinals"
        final = rest.iloc[-1]
        out[winner(final)], out[loser(final)] = "Champions", "Runners-up"
        if len(rest) > 1:
            third = rest.iloc[0]
            out[winner(third)], out[loser(third)] = "Third place", "Fourth place"
    return out


def seasons_played(games: pd.DataFrame, season: int) -> dict[str, int]:
    """Team -> number of seasons up to ``season`` in which it played a game (data from 2007-08)."""
    played = games[games["played"] & (games["season"] <= season)]
    pairs = pd.concat(
        [
            played[["season", "home"]].set_axis(["season", "team"], axis=1),
            played[["season", "away"]].set_axis(["season", "team"], axis=1),
        ]
    ).drop_duplicates()
    return {str(t): int(n) for t, n in pairs.groupby("team")["season"].nunique().items()}


def clubs_payload(
    games: pd.DataFrame, codes: Mapping[str, str], names: Mapping[str, str]
) -> list[dict[str, Any]]:
    """Every club that played a game since 2007-08, in every season, not only the published ones.

    The club list keeps clubs whose last season is outside the published window; their season
    files are not published, so the site lists them without a page.
    """
    played = games[games["played"].astype(bool)]
    pairs = pd.concat(
        [
            played[["season", "home"]].set_axis(["season", "team"], axis=1),
            played[["season", "away"]].set_axis(["season", "team"], axis=1),
        ]
    ).drop_duplicates()
    clubs = [
        {
            "code": codes.get(str(team), str(team)),
            "name": names.get(str(team), str(team)),
            "seasons": sorted(int(s) for s in grp["season"].unique()),
        }
        for team, grp in pairs.groupby("team")
    ]
    return sorted(clubs, key=lambda c: c["code"])


def _continuity_by_club(season: int, inputs: Inputs) -> dict[str, dict[str, Any]]:
    """Per source club code: last season's minutes, the share on this season's roster, and the
    three biggest returning and departing players by last season's seconds (IDEAS #17).

    Empty when there is no roster list for the season or no previous season.
    """
    if inputs.roster is None or not (inputs.roster["season"] == season).any():
        return {}
    players = player_continuity(
        inputs.box.players, season_start_roster(inputs.roster, inputs.games, season), season
    )
    if players.empty:
        return {}
    lines = inputs.box.players[["player_id", "player"]].drop_duplicates("player_id", keep="last")
    names = {str(pid): display_name(str(name)) for pid, name in lines.itertuples(index=False)}

    def top(part: pd.DataFrame) -> list[dict[str, Any]]:
        ranked = part.sort_values(["last_sec", "player_id"], ascending=[False, True]).head(3)
        return [
            {"id": str(pid), "name": names.get(str(pid), str(pid)), "sec": int(sec)}
            for pid, sec in zip(ranked["player_id"], ranked["last_sec"], strict=True)
        ]

    out: dict[str, dict[str, Any]] = {}
    clubs = club_share(players)
    for team, last, returned, share in zip(
        clubs["team"], clubs["last_sec"], clubs["returning_sec"], clubs["share"], strict=True
    ):
        mine = players[players["team"] == team]
        out[str(team)] = {
            "last_sec": int(last),
            "returning_sec": int(returned),
            "share": float(share),
            "returning": top(mine[mine["returning"]]),
            "departures": top(mine[~mine["returning"]]),
        }
    return out


# A team's strength-of-schedule figures in a season (source code, season -> figures), from the same
# computation as the team page (api/readmodel.py); the export holds no second definition of it.
SosOf = Callable[[str, int], Mapping[str, float | None]]


def _teams_payload(
    season: int,
    teams: pd.DataFrame,
    shots: pd.DataFrame,
    inputs: Inputs,
    sos: SosOf | None = None,
) -> dict[str, Any]:
    continuity = _continuity_by_club(season, inputs)
    table = teams.assign(gp=1)
    opp = table[["game_id", "team", *TEAM_FIELDS]].rename(columns={"team": "opponent"})
    paired = table.merge(
        opp, on=["game_id", "opponent"], suffixes=("", "_opp"), validate="one_to_one"
    )
    rows: list[dict[str, Any]] = []
    taken, allowed = band_table(shots, "team"), band_table(shots, "opponent")
    zero = {b: [0, 0] for b in BANDS}
    # The W-L is the regular-season record; the totals below still cover every game played.
    season_games = inputs.games[inputs.games["season"] == season]
    regular_ids = set(season_games.loc[season_games["phase"] == "RS", "game_id"])
    places = regular_season_standings(season_games, inputs.official_standings.get(season))
    ended = None if season == inputs.live_season else playoff_results(season_games, places)
    seasons_in = seasons_played(inputs.games, season)
    for key, lines in paired.groupby("team"):
        code = str(key)
        regular = lines[lines["game_id"].isin(regular_ids)]
        rows.append(
            {
                "code": inputs.codes.get(code, code),
                "name": inputs.names.get(code, code),
                "w": int(regular["won"].sum()),
                "l": int((~regular["won"]).sum()),
                "standing": places.get(code, len(places) + 1),
                "playoff": None
                if ended is None
                else {"result": ended.get(code, "Did not qualify")},
                "el_seasons": seasons_in.get(code, 1),
                "totals": _row(lines[list(TEAM_FIELDS)].to_numpy(dtype=float).sum(axis=0)),
                "opp": _row(
                    lines[[f"{f}_opp" for f in TEAM_FIELDS]].to_numpy(dtype=float).sum(axis=0)
                ),
                "bands": taken.get(code, zero),
                "bands_allowed": allowed.get(code, zero),
                "continuity": continuity.get(code),
            }
        )
        if sos is not None:
            rows[-1]["sos"] = dict(sos(code, season))
    rows.sort(key=lambda r: (-r["w"], r["l"], r["code"]))
    league = _row(table[list(TEAM_FIELDS)].to_numpy(dtype=float).sum(axis=0))
    return {
        "season": season,
        "fields": list(TEAM_FIELDS),
        "bands": list(BANDS),
        "league": {"totals": league, "bands": band_counts(shots)},
        "teams": rows,
    }


def _text_or_none(value: Any) -> str | None:
    """A text column's value, or None for a missing one (NaN is not JSON)."""
    return None if pd.isna(value) else str(value)


def _games_payload(
    season: int, frame: pd.DataFrame, games: pd.DataFrame, inputs: Inputs
) -> dict[str, Any]:
    played = games[games["played"]]
    index = {
        str(g["game_id"]): [
            g["tipoff_utc"].tz_convert(ATHENS).strftime("%Y-%m-%d"),
            int(g["round"]),
            str(g["phase"]),
            inputs.codes.get(str(g["home"]), str(g["home"])),
            inputs.codes.get(str(g["away"]), str(g["away"])),
            int(g["home_score"]),
            int(g["away_score"]),
            g["tipoff_utc"].tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            _text_or_none(g["venue"]),
            _text_or_none(g["venue_address"]),
        ]
        for g in played.to_dict("records")
    }
    logs: dict[str, list[list[Any]]] = {}
    lines = frame.assign(
        team=frame["team"].map(lambda t: inputs.codes.get(t, t)),
        starter=frame["starter"].astype(int),
    )
    for pid, game_id, team, *numbers in lines[["player_id", *LOG_FIELDS]].itertuples(index=False):
        logs.setdefault(str(pid), []).append([game_id, team, *(int(v) for v in numbers)])
    return {
        "season": season,
        "game_fields": list(GAME_FIELDS),
        "log_fields": list(LOG_FIELDS),
        "games": index,
        "logs": logs,
    }


def _shots_payload(season: int, shots: pd.DataFrame, inputs: Inputs) -> dict[str, Any]:
    taken, allowed = hexbins(shots, "team"), hexbins(shots, "opponent")
    return {
        "season": season,
        "hex_radius_m": HEX_RADIUS_M,
        "cell_fields": ["q", "r", "att", "made", "pts"],
        "league": hexbins(shots).get("", []),
        "teams": {
            inputs.codes.get(t, t): {"taken": taken[t], "allowed": allowed.get(t, [])}
            for t in sorted(taken)
        },
        "players": hexbins(shots, "player_id"),
    }


def attempt_flags(shots: pd.DataFrame) -> pd.Series:
    """Each shot packed into one integer (``ATTEMPT_BITS``), so the explorer can filter it."""
    parts = {
        "made": shots["made"],
        "three": shots["value"] == 3,
        "fastbreak": shots["fastbreak"],
        "second_chance": shots["second_chance"],
        "band": shots["band"].map({b: i for i, b in enumerate(BANDS)}),
        "period": shots["period"],
    }
    packed = pd.Series(0, index=shots.index, dtype="int64")
    for name, values in parts.items():
        packed += values.astype("int64") * 2 ** ATTEMPT_BITS[name]
    return packed


def _attempts_payload(season: int, shots: pd.DataFrame, inputs: Inputs) -> dict[str, Any]:
    """Every located attempt as parallel columns: coordinates in centimetres, flags, indices."""
    players = sorted(set(shots["player_id"]))
    teams = sorted({inputs.codes.get(t, t) for t in (*shots["team"], *shots["opponent"])})
    player_at = {p: i for i, p in enumerate(players)}
    team_at = {t: i for i, t in enumerate(teams)}

    def team_index(codes: pd.Series) -> list[int]:
        return [team_at[inputs.codes.get(t, t)] for t in codes]

    return {
        "season": season,
        "bits": ATTEMPT_BITS,
        "players": players,
        "teams": teams,
        "x": [int(v) for v in (shots["x"] * 100).round()],
        "y": [int(v) for v in (shots["y"] * 100).round()],
        "flags": [int(v) for v in attempt_flags(shots)],
        "player": [player_at[p] for p in shots["player_id"]],
        "team": team_index(shots["team"]),
        "opp": team_index(shots["opponent"]),
    }


def build_payloads(
    inputs: Inputs, now: datetime, sos: SosOf | None = None
) -> dict[str, dict[str, Any]]:
    """Relative path -> JSON payload of every file in the stats directory.

    Only the latest ``SITE_SEASONS`` seasons are published: the season files, the player and
    team lists, the twin pool. ``splits.json`` alone keeps the full careers of the players who
    played in those seasons, so career totals and best seasons stay all-time.
    """
    career = _player_frame(inputs)
    window = site_window(career["season"].unique())
    frame = career[career["season"].isin(window)]
    shots_table = inputs.shots.table[inputs.shots.table["season"].isin(window)]
    names = dict(zip(frame["player_id"], frame["player"].map(display_name), strict=True))
    slugs = player_slugs(names)  # the last spelling of a name wins, as in the season rows
    files: dict[str, dict[str, Any]] = {}
    seasons: list[dict[str, Any]] = []
    missing = inputs.box.missing.groupby("season").size()
    coverage = {int(r["season"]): r for r in inputs.shots.coverage.to_dict("records")}
    for season in window:
        lines = frame[frame["season"] == season]
        shots = shots_table[shots_table["season"] == season]
        games = inputs.games[inputs.games["season"] == season]
        base = f"seasons/{season}"
        files[f"{base}/players.json"] = _players_payload(season, lines, shots, inputs, slugs)
        files[f"{base}/teams.json"] = _teams_payload(
            season, inputs.box.teams[inputs.box.teams["season"] == season], shots, inputs, sos
        )
        files[f"{base}/games.json"] = _games_payload(season, lines, games, inputs)
        files[f"{base}/shots.json"] = _shots_payload(season, shots, inputs)
        files[f"{base}/attempts.json"] = _attempts_payload(season, shots, inputs)
        files[f"{base}/runs.json"] = runs_payload(
            season, games.loc[games["played"], "game_id"].astype(str), inputs.runs
        )
        if inputs.wp is not None:
            files[f"{base}/wp.json"] = wp_payload(
                season, games.loc[games["played"], "game_id"].astype(str), inputs.wp
            )
        if season in inputs.units:
            files[f"{base}/units.json"] = dict(inputs.units[season])
        team_season = inputs.box.teams[inputs.box.teams["season"] == season]
        played_ids = games.loc[games["played"], "game_id"].astype(str)
        with_pbp = [
            gid for gid in played_ids if gid in inputs.assists
        ]  # box totals of the same games
        team_with_pbp = team_season[team_season["game_id"].isin(with_pbp)]
        files[f"{base}/assists.json"] = assists_payload(
            season,
            played_ids,
            inputs.assists,
            {
                str(team): int(total)
                for team, total in team_with_pbp.groupby("team")["ast"].sum().items()
            },
        )
        cover = coverage.get(season)
        seasons.append(
            {
                "season": season,
                "label": season_label(season),
                "live": season == inputs.live_season,
                "games": int(lines["game_id"].nunique()),
                "games_without_box": int(missing.get(season, 0)),
                "games_with_shots": 0 if cover is None else int(cover["games"]),
                "shots": 0 if cover is None else int(cover["shots"]),
                "shots_unplaced": 0 if cover is None else int(cover["unplaced"]),
                "coords_validated": bool(cover is not None and cover["validated"]),
                "players": int(lines["player_id"].nunique()),
            }
        )
    played = frame.groupby("player_id", sort=False)["season"].unique()
    files["players.json"] = {
        "players": sorted(
            (
                {
                    "id": str(pid),
                    "name": names[str(pid)],
                    "slug": slugs[str(pid)],
                    "seasons": [int(s) for s in ss],
                }
                for pid, ss in played.items()
            ),
            key=lambda p: (p["slug"], p["id"]),
        )
    }
    files["splits.json"] = _splits_payload(career[career["player_id"].isin(names)], inputs)
    files["achievements.json"] = achievements_payload(
        inputs.games, inputs.box.players, inputs.live_season
    )
    codes = sorted(set(inputs.box.teams[inputs.box.teams["season"].isin(window)]["team"]))
    files["meta.json"] = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%MZ"),
        "hex_radius_m": HEX_RADIUS_M,
        "bands": list(BANDS),
        "windows": [f"last{n}" for n in WINDOWS],
        "player_fields": list(PLAYER_FIELDS),
        "team_fields": list(TEAM_FIELDS),
        "teams": {inputs.codes.get(c, c): inputs.names.get(c, c) for c in codes},
        "clubs": clubs_payload(inputs.games, inputs.codes, inputs.names),
        "seasons": seasons,
    }
    return files


def write_stats(out_dir: Path, files: Mapping[str, Mapping[str, Any]]) -> None:
    """Replace the stats directory's contents with ``files`` (compact JSON, LF endings)."""
    if (out_dir / "seasons").exists():
        shutil.rmtree(out_dir / "seasons")
    for relative, payload in files.items():
        path = out_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        path.write_text(text + "\n", encoding="utf-8", newline="\n")
