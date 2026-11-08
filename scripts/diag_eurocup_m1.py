"""EuroCup M1 diagnostic: M1 vs Elo vs B0 on the test seasons (spec addendum).

Team box lines come from the cached EuroCup box scores (U{season} folders). They are written to the
marts as ``team_games_eurocup`` and ``team_games_missing_eurocup``; M1 reads them back from there.
Run after ``eurohoops ingest --competition eurocup --details --box-and-pbp-only``.
Writes reports/diag_eurocup_m1.json (the path in EUROCUP.m1.report).
"""

from typing import Any

from eurohoops.config import EUROCUP, MART_PATH
from eurohoops.eval.eurocup import m1_vs_elo_b0
from eurohoops.logs import write_json
from eurohoops.marts import read_games, read_table, write_tables
from eurohoops.parse.team_box import build_team_games


def _team_games_coverage(missing: Any) -> dict[str, int]:
    return {str(k): int(v) for k, v in missing["season"].value_counts().sort_index().items()}


def main() -> None:
    games = read_games(MART_PATH, EUROCUP.name)
    built = build_team_games(games, EUROCUP.raw_dir, competition=EUROCUP.name, code=EUROCUP.code)
    write_tables(
        MART_PATH,
        {"team_games_eurocup": built.table, "team_games_missing_eurocup": built.missing},
    )
    team_games = read_table(MART_PATH, "team_games_eurocup")
    missing = read_table(MART_PATH, "team_games_missing_eurocup")
    assert team_games is not None and missing is not None
    assert EUROCUP.m1 is not None
    result = m1_vs_elo_b0(games, team_games, EUROCUP.m1)
    report = {
        "experiment": "eurocup",
        "model": "m1",
        "seasons": {
            "warmup": list(EUROCUP.m1.warmup),
            "tuning": list(EUROCUP.m1.tuning),
            "test": list(EUROCUP.m1.test),
        },
        "validation": "none (no gate for EuroCup; spec addendum)",
        "team_games_missing_by_season": _team_games_coverage(missing),
        **result,
    }
    write_json(EUROCUP.m1.report, report)
    print(
        f"EuroCup M1 shared test games {report['n_shared_test_games']}; "
        f"log loss {report['log_loss_shared_test']}; "
        f"M1-Elo {report['pairwise']['m1_minus_elo']}; M1-B0 {report['pairwise']['m1_minus_b0']}"
    )
    print(f"wrote {EUROCUP.m1.report}")


if __name__ == "__main__":
    main()
