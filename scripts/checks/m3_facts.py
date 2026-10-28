"""Week 9-12 §3 facts, re-checked on the local data (part of checklist item 33).

1. Distinct EuroLeague players with stints 2011-2025 (a dense posterior inverse needs 2 columns
   per player: it must stay under 5,000 players).
2. Player ids are stable across seasons: each id may have several spellings (transliteration),
   and a name has more than one id only in the known cases below.
3. Box minutes and the stints' on-court seconds agree within 60 s for >= 99.9% of player-games
   of games passing the stint checks.
"""

import sys

import duckdb
import pandas as pd

from eurohoops.config import EUROLEAGUE, MART_PATH
from eurohoops.stats.box import build_box_games

# Names with two ids: Omer Yurtseven (ULK 2014 and 2015, one player given a new id) and two
# different players called Marko Simonovic (RED 2013, RED 2023).
KNOWN_SPLIT_NAMES = {"YURTSEVEN, OMER", "SIMONOVIC, MARKO"}

ok = True
with duckdb.connect(str(MART_PATH), read_only=True) as con:
    stints = con.execute("SELECT * FROM stints WHERE season BETWEEN 2011 AND 2025").df()
    checks = con.execute("SELECT * FROM stint_game_checks").df()
    games = con.execute("SELECT * FROM games WHERE competition = 'euroleague'").df()

sides = []
for side in ("home", "away"):
    rows = stints[["game_id", "start_s", "end_s", f"{side}_players"]].explode(f"{side}_players")
    sides.append(
        pd.DataFrame(
            {
                "game_id": rows["game_id"],
                "player_id": rows[f"{side}_players"],
                "sec": rows["end_s"] - rows["start_s"],
            }
        )
    )
on_court = pd.concat(sides)
players = on_court["player_id"].nunique()
print(f"1. players with stints 2011-2025: {players} (< 5,000 for a dense posterior)")
ok &= 1_000 < players < 5_000

played = games[games["season"].between(2011, 2025) & games["played"] & ~games["forfeit"]]
box = build_box_games(EUROLEAGUE.raw_dir, played).players
spellings = box.groupby("player_id")["player"].nunique()
ids = box.groupby("player")["player_id"].nunique()
split = set(ids[ids > 1].index)
print(
    f"2. ids with several spellings: {(spellings > 1).sum()} of {len(spellings)}; "
    f"names with several ids: {sorted(split)}"
)
ok &= split <= KNOWN_SPLIT_NAMES

passing = set(checks.loc[checks["passed"], "game_id"])
stint_sec = on_court.groupby(["game_id", "player_id"])["sec"].sum().rename("stint")
box_sec = box.set_index(["game_id", "player_id"])["sec"].rename("box")
both = pd.concat([stint_sec, box_sec], axis=1).fillna(0)
both = both[both.index.get_level_values(0).isin(passing)]
share = float(((both["stint"] - both["box"]).abs() <= 60).mean())
print(f"3. player-games of passing games within 60 s: {share:.5f} of {len(both)} (>= 0.999)")
ok &= share >= 0.999

print("m3 facts:", "hold" if ok else "BROKEN")
sys.exit(0 if ok else 1)
