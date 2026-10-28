"""ELOH step A (experiments/eloh.md): fit the per-team home advantage once, then freeze it.

Fits on EuroLeague games of ``ELOH_FIT_SEASONS`` only, using the live Elo parameters from the
live backtest report. Writes ``reports/eloh_fit.json``, which the live forecaster reads.

Refuses to run when the file already exists: the fit is frozen, so a refit is a new experiment.
Run: ``uv run python scripts/fit_eloh.py``. Reads the games mart; writes only the fit file.
"""

import sys

from eurohoops.config import ELOH_FIT, ELOH_FIT_SEASONS, EUROLEAGUE, MART_PATH
from eurohoops.eval.backtest import load_tuned_model
from eurohoops.logs import write_json
from eurohoops.marts import read_games
from eurohoops.models.eloh import fit_home_effects, fit_to_json


def main() -> None:
    if ELOH_FIT.exists():
        sys.exit(f"refusing to run: {ELOH_FIT} already exists (the ELOH fit is frozen)")
    games = read_games(MART_PATH, EUROLEAGUE.name)
    fit_games = (
        games[games["season"].isin(ELOH_FIT_SEASONS)]
        .sort_values("tipoff_utc", kind="stable")
        .reset_index(drop=True)
    )
    params = load_tuned_model(EUROLEAGUE.live_backtest.report).params
    fit = fit_home_effects(fit_games, params)
    seasons = (min(ELOH_FIT_SEASONS), max(ELOH_FIT_SEASONS))
    write_json(ELOH_FIT, fit_to_json(fit, seasons))

    print(f"fit seasons {seasons[0]}..{seasons[1]}, Elo params {params}")
    print(f"tau2 {fit.tau2:.6f}  var(ebar) {fit.var_residual:.6f}  s2 {fit.mean_sampling_var:.6f}")
    print(f"teams with home games: {len(fit.teams)}")
    if fit.tau2 == 0.0:
        print("tau2 = 0: every delta is 0, ELOH equals Elo. Stop after step A and report it.")
    ranked = sorted(fit.teams.items(), key=lambda kv: -abs(kv[1].delta))
    print(f"{'team':>6} {'n':>5} {'ebar':>9} {'B':>7} {'delta':>9}")
    for team, eff in ranked:
        print(
            f"{team:>6} {eff.n:>5} {eff.mean_residual:>+9.4f} {eff.shrink:>7.4f} {eff.delta:>+9.2f}"
        )
    print(f"wrote {ELOH_FIT}")


if __name__ == "__main__":
    main()
