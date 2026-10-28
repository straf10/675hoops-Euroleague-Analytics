"""Week 14-16 §3 facts, re-checked on the local data (part of checklist item 43).

1. Every EuroLeague tip-off is a real time: none sits at 00:00 UTC.
2. No EuroLeague game (2015-2025) comes <= 1.5 days after the team's previous game (why J-e's
   ``b2b`` became ``short_rest``, decision D1).
3. M1's committed replay inputs are the ones M5 reads (``tuned`` and ``comparison_elo``).

Since 2026-10-28 rest is EuroLeague only: the other-competition count (item 3 of the 2026-10-22
version) no longer applies and is not checked.
"""

import json
import sys

import pandas as pd

from eurohoops.config import EUROLEAGUE, MART_PATH
from eurohoops.marts import read_games

ok = True
el = read_games(MART_PATH, EUROLEAGUE.name)

t = el["tipoff_utc"].dt.tz_convert("UTC")
midnight = int(((t.dt.hour == 0) & (t.dt.minute == 0)).sum())
print(f"1 EL: {midnight} tip-offs at 00:00 UTC of {len(el)}")
ok &= midnight == 0

played = el[el["played"]]
rows = pd.concat(
    [
        played[["game_id", "season", "tipoff_utc", side]].rename(columns={side: "team"})
        for side in ("home", "away")
    ]
).sort_values(["team", "tipoff_utc", "game_id"])
rows["days"] = rows.groupby("team")["tipoff_utc"].diff().dt.total_seconds() / 86400
recent = rows[rows["season"].between(2015, 2025)]
short = int((recent["days"] <= 1.5).sum())
print(f"2 games <= 1.5 days after the previous one (2015-2025): {short}")
ok &= short == 0

assert EUROLEAGUE.m1 is not None
m1 = json.loads(EUROLEAGUE.m1.report.read_text(encoding="utf-8"))
margin = m1["tuned"]["margin"]
elo = m1["comparison_elo"]
inputs_ok = (
    margin["variant"] == "student_t_const"
    and margin["df"] == 7.0
    and (elo["k"], elo["hca"], elo["reversion"]) == (20.0, 90.0, 0.25)
    and m1["metrics"]["validation"]["m1"]["log_loss"] == 0.587714
)
print(f"3 M1 replay inputs as recorded: {inputs_ok}")
ok &= inputs_ok

print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
