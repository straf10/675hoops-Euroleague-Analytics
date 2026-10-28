# eloh
Idea:      Elo with a per-team home advantage: hca_team = 90 + δ_team, where δ_team is estimated from home-minus-expected results on EuroLeague seasons 2007-08..2023-24 only and shrunk toward 0 by an empirical Bayes factor; everything else is frozen live Elo (k 20, hca 90, reversion 0.25) (docs/research/IDEAS.md D2, approved as written by the owner 2026-10-28).
Type:      forecaster
Baseline:  Elo (live, published EuroLeague forecast)
Backtest:  none (δ fitted on 2007-08..2023-24; the Elo tuning and test seasons 2024-25 and 2025-26 are not used)
Live:      yes (shadow from merge)
Metric:    log loss on home win
Pass bar:  live: paired bootstrap of (ELOH − Elo) log loss on EuroLeague games logged after the merge through the end of 2026-27, plus 2027-28; pass when the 95% CI upper bound < 0. Replacing the published forecast still needs the standard test (CLAUDE.md rule 4).
Result:    (step 7)
