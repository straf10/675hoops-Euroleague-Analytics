# residuals
Idea:      Residual and reliability diagnostics: do pre-game features the models do not use explain their out-of-sample errors?
Type:      diagnostic
Baseline:  Elo (live params k 20, hca 90, reversion 0.25); M5 (live variant)
Backtest:  Elo 2015-16..2025-26 walk-forward replay (scored seasons 2015..2025, non-neutral, played, not forfeit); M5 per-game backtest rows (reports/backtest_m5_games.csv, live variant); live 2026-27 logs (all shown models + MKT) as a small extra section
Live:      no
Metric:    per-feature encompassing test: logistic regression of home_won on offset logit(p_model) + standardized feature; margin: OLS of (actual_margin - exp_margin) on the standardized feature
Pass bar:  A feature is flagged "candidate evidence" only when BOTH: (1) its coefficient's Holm-corrected p-value < 0.05 across all features tested for that model (pooled scored seasons), and (2) the coefficient has the same sign in at least 2/3 of the scored seasons that have the feature. Everything else is "no evidence". Per-team and per-season reliability tables are descriptive only (no flag). Live 2026 section is descriptive only.
Result:    no candidate evidence. 0 of 25 features flagged (Elo 12, M5 13); every Holm-adjusted win p is 1.0 (smallest raw p 0.165, Elo confidence). Pooled 2015-2025, n = 3260: Elo log loss 0.609433, gap (mean p - actual home rate) -0.0110; M5 log loss 0.602072, gap -0.0086. Live 2026 (descriptive, n = 98 Elo): gap +0.098. Details: docs/models/diag_residuals.md.
