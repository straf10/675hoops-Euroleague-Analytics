# injstatus
Idea:      Measure how often a player with each BasketNews status played in his club's next game.
Type:      diagnostic
Baseline:  none
Backtest:  none. Live 2026-27 EuroLeague: every finished, non-forfeit game of a club, and every matched player listed for that club in the latest injury snapshot stamped strictly before the game's tip-off and at most 24 hours before it.
Live:      no
Metric:    played rate per status = share of those player-games with more than 0 seconds played, with n and a 95% Wilson interval.
Pass bar:  none (descriptive). A status is reported with its rate only when it has at least 30 player-games; below that only n is given. No model changes from this result.
Result:    2026-11-11, rounds 1-10 (100 games, 200 club sides; 92 sides had a snapshot in the 24 hours before tip-off, 108 had none; no game without a box score). 405 matched player-games, 65 unmatched. Played rate: Out 1 of 154 (0.6%, 95% CI 0.1-3.6%); Uncertain 35 of 167 (21.0%, CI 15.5-27.7%); Expected 31 of 37 (83.8%, CI 68.9-92.3%). Below 30 player-games, n only: Doubtful 18, Game-time 18, Ready 11. Descriptive; no model changes from this result. Report: reports/diag_injstatus.json.
