"""Print the cross-table data audit of the marts: counts split into explained and unexplained.

Usage: uv run python scripts/data_audit.py [path/to/eurohoops.duckdb]
Run from the checkout that holds data/ (the raw cache and marts are read relative to it).
Reads only; it changes no data. The headline number is the total of unexplained failures.
The coach checks read the cached EuroLeague box scores; their win probabilities are not used by
any check, so they are computed with a flat 0.5 here.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import duckdb
import pandas as pd

from eurohoops.audit import Finding, run_audit
from eurohoops.audit_coaches import coach_findings
from eurohoops.audit_standings import Standing, standings_findings
from eurohoops.audit_status import POSTPONED_REASON, is_postponed
from eurohoops.config import EUROLEAGUE, GBL, MART_PATH
from eurohoops.ingest.cache import read_cached
from eurohoops.parse.box import load_box_corrections
from eurohoops.stats.coaches import coach_games

STANDINGS_DIR = EUROLEAGUE.raw_dir / "standings"


def _standings(path: str) -> list[Finding]:
    """EuroLeague standings files vs the regular-season games, with overtime points from boxes."""
    with duckdb.connect(path, read_only=True) as con:
        games = con.execute("SELECT * FROM games WHERE competition = 'euroleague'").df()
    tables: list[Standing] = []
    present: set[int] = set()
    for xml in sorted(STANDINGS_DIR.glob("E*_r*.xml")):
        season = int(xml.name[1:5])
        present.add(season)
        for team in ET.parse(xml).getroot().iter("team"):
            tables.append(
                Standing(
                    season=season,
                    team=str(team.findtext("code")),
                    wins=int(team.findtext("wins") or 0),
                    losses=int(team.findtext("losses") or 0),
                    games=int(team.findtext("totalgames") or 0),
                    points_for=int(team.findtext("ptsfavour") or 0),
                    points_against=int(team.findtext("ptsagainst") or 0),
                )
            )
    overtime = _overtime(games, sorted(present))
    expected = sorted(set(games["season"].astype(int)))
    played = games[(games["phase"] == "RS") & games["played"] & ~games["forfeit"]]
    game_rows = [
        (
            int(r["season"]),
            str(r["home"]),
            str(r["away"]),
            int(r["home_score"]),
            int(r["away_score"]),
        )
        for r in played.to_dict("records")
    ]
    return standings_findings(tables, game_rows, overtime, expected, present)


def _overtime(games: pd.DataFrame, seasons: list[int]) -> dict[tuple[int, str], tuple[int, int]]:
    """(season, team) -> points for and against scored after the 40 regulation minutes."""
    out: dict[tuple[int, str], tuple[int, int]] = {}
    rs = games[
        games["season"].isin(seasons)
        & (games["phase"] == "RS")
        & games["played"]
        & ~games["forfeit"]
    ]
    for game in rs.to_dict("records"):
        path = EUROLEAGUE.raw_dir / "boxscore" / f"E{int(game['season'])}"
        path = path / f"{game['game_code']}.json.gz"
        if not path.exists():
            continue
        box = json.loads(read_cached(path))
        quarters = box.get("EndOfQuarter") or []
        scored: dict[str, int] = {}
        for index, side in enumerate(box.get("Stats", [])):
            players = side.get("PlayersStats") or []
            if not players or index >= len(quarters):
                break
            team = str(players[0]["Team"]).strip()
            final = int(game["home_score"] if team == game["home"] else game["away_score"])
            scored[team] = final - int(quarters[index].get("Quarter4") or 0)
        if len(scored) != 2:
            continue
        (a, ot_a), (b, ot_b) = scored.items()
        season = int(game["season"])
        for team, own, other in ((a, ot_a, ot_b), (b, ot_b, ot_a)):
            ot_for, ot_against = out.get((season, team), (0, 0))
            out[(season, team)] = (ot_for + own, ot_against + other)
    return out


REPO = Path(__file__).resolve().parents[1]
CORRECTIONS = REPO / "corrections" / "gbl_box.csv"  # repo files: read from the checkout
SCHEDULE = REPO / "corrections" / "gbl_schedule.csv"  # documented source schedule items
OVERRIDES = REPO / "entity" / "overrides.csv"


def _documented_matches(path: str) -> dict[str, str]:
    """``person competition`` -> reason, for every ``match`` decision in entity/overrides.csv."""
    decisions = pd.read_csv(OVERRIDES, dtype=str).fillna("")
    decisions = decisions[decisions["decision"] == "match"]
    with duckdb.connect(path, read_only=True) as con:
        xwalk = con.execute("SELECT person_id, competition, source_id FROM player_xwalk").df()
    out: dict[str, str] = {}
    for _, row in decisions.iterrows():
        for competition, source in (
            (row["competition_a"], row["source_a"]),
            (row["competition_b"], row["source_b"]),
        ):
            hit = xwalk[(xwalk["competition"] == competition) & (xwalk["source_id"] == source)]
            for person in hit["person_id"]:
                out[f"{person} {competition}"] = row["reason"]
    return out


def _raw_coaches(games: pd.DataFrame) -> dict[tuple[str, str], str]:
    """(game_id, team) -> the Coach field of that side in the cached box score, '' when none."""
    out: dict[tuple[str, str], str] = {}
    played = games[games["played"] & ~games["forfeit"]]
    for game in played.to_dict("records"):
        path = EUROLEAGUE.raw_dir / "boxscore" / f"E{int(game['season'])}"
        path = path / f"{game['game_code']}.json.gz"
        if not path.exists():
            continue
        box = json.loads(read_cached(path))
        for side in box.get("Stats", []):
            players = side.get("PlayersStats") or []
            if players:
                team = str(players[0]["Team"]).strip()
                out[(str(game["game_id"]), team)] = str(side.get("Coach") or "").strip()
    return out


def _schedule() -> dict[str, str]:
    """game_id -> reason, for source schedule items documented in corrections/gbl_schedule.csv."""
    frame = pd.read_csv(SCHEDULE, dtype=str, keep_default_na=False)
    return dict(zip(frame["game_id"], frame["reason"], strict=True))


def _postponed(path: str) -> dict[str, str]:
    """game_id -> reason, for unplayed GBL games whose cached ESAKE schedule says postponed."""
    with duckdb.connect(path, read_only=True) as con:
        unplayed = con.execute(
            "SELECT game_id, game_code FROM games WHERE competition = 'gbl' AND NOT played "
            "AND NOT forfeit AND tipoff_utc < now()"
        ).fetchall()
    codes = {f"{int(code):08X}": game_id for game_id, code in unplayed}
    out: dict[str, str] = {}
    for page in sorted((GBL.raw_dir / "results").rglob("*.html.gz")):
        text = read_cached(page).decode("utf-8", "replace")
        for code, game_id in codes.items():
            if is_postponed(text, code):
                out[game_id] = POSTPONED_REASON
    return out


def _coach(path: str) -> list[Finding]:
    with duckdb.connect(path, read_only=True) as con:
        games = con.execute("SELECT * FROM games WHERE competition = 'euroleague'").df()
    rows = coach_games(EUROLEAGUE.raw_dir, games.assign(p_home=0.5))
    return coach_findings(rows, games, _raw_coaches(games))


def _print(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.count:>6} failing  {finding.unexplained:>5} unexplained  {finding.name}")
        if finding.note:
            print(f"        note: {finding.note}")
        for reason, n in sorted(finding.reasons.items()):
            print(f"        explained {n:>5}: {reason}")
        for example in finding.examples:
            print(f"        UNEXPLAINED: {example}")


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else MART_PATH
    corrections = {
        " ".join(key): fix.reason for key, fix in load_box_corrections(CORRECTIONS).items()
    }
    corrections.update(_documented_matches(str(path)))
    corrections.update(_postponed(str(path)))
    corrections.update(_schedule())
    findings = run_audit(str(path), corrections) + _coach(str(path)) + _standings(str(path))
    print(f"UNEXPLAINED FAILURES: {sum(f.unexplained for f in findings)}")
    _print(findings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
