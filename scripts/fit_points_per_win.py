"""Re-derive EuroLeague points per win from the data, as a comparison only (Win Shares uses the
Basketball-Reference rule, 0.32 x league PPG x pace factor, in stats/win_shares.py).

Fits win % on point differential per game over EuroLeague regular seasons 2007-08..2025-26 (the
season label is the starting year), from the cached schedules only: nothing is fetched or written.
Prints the value, its 95% bootstrap interval and the regression behind it.

Usage: uv run python scripts/fit_points_per_win.py   (run from the checkout that holds data/)
"""

from pathlib import Path

from eurohoops.api.readmodel import Store, _el_games
from eurohoops.stats.win_shares import fit_points_per_win, team_seasons_regular

FIRST_SEASON, LAST_SEASON = 2007, 2025


def main() -> None:
    store = Store(root=Path.cwd(), from_cache=True)
    games, _ = _el_games(store)
    seasons = team_seasons_regular(games)
    seasons = seasons[seasons["season"].between(FIRST_SEASON, LAST_SEASON)]
    fit = fit_points_per_win(seasons)
    print(f"team-seasons: {fit.teams} ({FIRST_SEASON}-{LAST_SEASON} regular seasons)")
    print(f"win % = {fit.intercept:.4f} + {fit.slope:.6f} x point differential per game")
    print(f"points per win: {fit.value:.2f} (95% CI {fit.low:.2f} to {fit.high:.2f})")


if __name__ == "__main__":
    main()
