# pool3
Idea:      Screen POOL's four members for near-duplicates on live EuroLeague games; if Elo and ELOR are nearly identical, log a three-member pool POOL3 (ELOR, M1, M5) as a new shadow, because ELOR = Elo + a fading roster offset gives Elo double weight (docs/research/IDEAS.md C2, approved as written by the owner 2026-10-28).
Type:      diagnostic screen, then forecaster only if the screen triggers
Baseline:  POOL (live equal-weight logit pool)
Backtest:  none
Live:      yes (shadow from merge) only if the screen triggers; otherwise no
Metric:    log loss on home win
Pass bar:  screen: POOL3 is declared when the Pearson correlation of the Elo and ELOR logits, over the 2026-27 EuroLeague games that both logs scored before this commit, is > 0.98. Also reported, not part of the rule: the correlation matrix of all members' logits and of their per-game log-loss residuals.
           live (only if declared): paired bootstrap of (POOL3 − POOL) log loss on EuroLeague games logged after the merge through season end; pass when the 95% CI upper bound < 0. Replacing the published forecast still needs the standard test (CLAUDE.md rule 4).
Result:    (step 7)
