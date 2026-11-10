# injstatus
Idea:      Measure how often a player with each BasketNews status played in his club's next game.
Type:      diagnostic
Baseline:  none
Backtest:  none. Live 2026-27 EuroLeague: every finished, non-forfeit game of a club, and every matched player listed for that club in the latest injury snapshot stamped strictly before the game's tip-off and at most 24 hours before it.
Live:      no
Metric:    played rate per status = share of those player-games with more than 0 seconds played, with n and a 95% Wilson interval.
Pass bar:  none (descriptive). A status is reported with its rate only when it has at least 30 player-games; below that only n is given. No model changes from this result.
Result:    (step 7)
