"""Weeks 16-18 M6 §3 facts, re-checked on the local data (part of checklist item 54).

1. Possessions: every EuroLeague player game with seconds has a possession count (EuroLeague
   2007+).
2. Scored-set sizes per season (``models.player_seasons``: >= 500 possessions in the season and a
   senior season before it) and the >= 500 counts equal ``tests/fixtures/m6_facts.json``.
3. Birth-date coverage among the scored player-seasons equals the fixture: a plausible date
   (``player_ages``, D16; 2026-10-08).
   Only the share is printed: no date or age is.
4. M3 walk-forward: ``m3_players.json`` holds a season-end BRAPM snapshot for 2011-2025, each
   cut at its own season's last round, so a target's projection reads only earlier snapshots.
5. Four factors: the EuroLeague player box carries every input (FGM/FGA by type, FTA, OREB, DREB,
   TOV, possessions), so team four factors are derivable from the marts' sources.
"""

import json
import sys
from pathlib import Path

import pandas as pd

from eurohoops.config import EUROLEAGUE, MART_PATH, PLAYER_BIOS
from eurohoops.marts import read_games, read_table
from eurohoops.models.player_seasons import build_player_seasons, player_ages
from eurohoops.stats.box import build_box_games

FACTS = json.loads(Path("tests/fixtures/m6_facts.json").read_text(encoding="utf-8"))
FOUR_FACTOR_INPUTS = ("fg2m", "fg2a", "fg3m", "fg3a", "fta", "oreb", "dreb", "tov", "poss")

results: list[bool] = []


def check(label: str, passed: bool) -> None:
    results.append(passed)
    print(f"{'PASS' if passed else 'FAIL'}  {label}")


el_games = read_games(MART_PATH, EUROLEAGUE.name)
xwalk = read_table(MART_PATH, "player_xwalk")
if xwalk is None:
    sys.exit("marts missing player_xwalk; run: eurohoops build")
games = {"euroleague": build_box_games(EUROLEAGUE.raw_dir, el_games).players}

# 1. possessions
for comp, lines in games.items():
    played = lines[lines["sec"] > 0]
    bad = int((played["poss"].isna() | (played["poss"] <= 0)).sum())
    check(f"1 {comp}: {len(played)} player games with seconds, {bad} without possessions", bad == 0)

# 2-3. scored sets and birth-date coverage
seasons = build_player_seasons(games, xwalk)
seasons = seasons[seasons["season"] < FACTS["live_season"]]
# A person counts as dated only if his date gives a plausible age in every season he played
# (player_ages drops the others, D16): the share the projections can actually use.
dated_persons = set(player_ages(pd.read_parquet(PLAYER_BIOS), xwalk, seasons)["person_id"])
found: dict[str, dict[str, dict[str, float]]] = {}
for (comp, season), rows in seasons.groupby(["competition", "season"]):
    scored = rows[(rows["poss"] >= FACTS["min_poss"]) & (rows["season"] > rows["debut_season"])]
    birth = float(scored["person_id"].isin(dated_persons).mean()) if len(scored) else None
    found.setdefault(str(comp), {})[str(season)] = {
        "ge_min_poss": int((rows["poss"] >= FACTS["min_poss"]).sum()),
        "scored": len(scored),
        "birth_share": None if birth is None else round(birth, 3),
    }
for comp, expected in FACTS["scored"].items():
    for season, want in expected.items():
        got = found.get(comp, {}).get(season)
        check(f"2-3 {comp} {season}: {got} (fixture {want})", got == want)

# 4. M3 snapshots
m3 = json.loads(Path("reports/m3_players.json").read_text(encoding="utf-8"))
snaps = sorted(int(s) for s in m3["seasons"])
check(f"4 M3 BRAPM snapshots {snaps[0]}-{snaps[-1]}", snaps == FACTS["m3_snapshot_seasons"])
late = [
    s
    for s in snaps
    if pd.Timestamp(m3["seasons"][str(s)]["cutoff_utc"])
    > pd.Timestamp(el_games.loc[el_games["season"] == s, "tipoff_utc"].max())
]
check(f"4 snapshots cut after their own season's last game (must be none): {late}", not late)

# 5. four-factor inputs
for comp, lines in games.items():
    missing = [c for c in FOUR_FACTOR_INPUTS if c not in lines.columns]
    check(f"5 {comp}: four-factor inputs missing {missing}", not missing)

ok = all(results)
print("m6 facts:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
