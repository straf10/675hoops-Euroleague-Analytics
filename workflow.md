# Experiment workflow

Every experiment runs this pipeline. One **orchestrator** agent owns the experiment and does each step through a subagent. Rules are in `CLAUDE.md`; this file only says what to do, in what order.

Input: an experiment id (`<id>`, short, lowercase, e.g. `m5inj`) and a one-line idea.

---

## Step 1 — Spec (orchestrator)
Create a worktree on branch `exp/<id>` from main, and write `experiments/<id>.md`:

```
# <id>
Idea:      <what changes and why, one sentence>
Type:      forecaster | diagnostic
Baseline:  <the model it must beat, e.g. M5>
Backtest:  <seasons scored, e.g. 2023-24..2025-26 walk-forward>  | none
Live:      yes (shadow from merge) | no
Metric:    log loss on home win (default) | <other>
Pass bar:  backtest: mean gap vs baseline < 0 on the scored seasons
           live: standard test (CLAUDE.md rule 4) | <other, stated as a number>
Result:    (step 7)
```

Commit it on the branch. This commit is the record of the pass bar (rule 3).

## Step 2 — Build (subagent: implementer)
Give it the spec and the worktree path. It must:
- **Forecaster:** follow the M5-INJ change (`git show 837fecd --stat`) as the template. Touch:
  - `src/eurohoops/live_<id>.py`: builds the forecast rows.
  - `config.py`: log path `predictions/<comp>_<id>_<season>.csv` and `<ID>_LIVE_ENABLED = False`.
  - `cli/live.py`: a `_predict_<id>` call from `predict`.
  - `eval/scorecard.py`: a scorecard section.
  - `api/readmodel.py`: a `FORECAST_MODELS` label.
  - `scripts/checks/api_export.py`: a `legacy_site` entry.
  - If backtested: `eval/<id>_backtest.py` plus a `--model <id>` branch in `cli/backtest.py` that writes `reports/backtest_<id>.json`.
- **Diagnostic:** `scripts/diag_<id>.py` plus `src/eurohoops/eval/<id>.py`, writing `reports/diag_<id>.json`.
- Add `tests/test_<id>.py` with fixtures under `tests/fixtures/<id>/`, covering the forecast on a small fixture and the no-lookahead case (a later game changes no earlier forecast).
- Run the checklist (`CLAUDE.md`) until it passes, then commit on `exp/<id>`.
- Return: the files changed, the checklist exit code, and anything it couldn't do.

## Step 3 — Review (subagent: reviewer, fresh context)
Give it the spec and `git diff main...exp/<id>`. It checks only:
1. Does the code do what the spec says?
2. Can any forecast see its own game or a later one?
3. Does it break rules 1, 5, 6, 7 or 8?
4. Do the checklist and tests pass (it reruns the checklist itself)?

Return: PASS, or a numbered list of defects with file:line.
On FAIL, send the defects back to the implementer (step 2) and review again. Allow at most **2 rounds**; after that, stop and report to the owner.

## Step 4 — Backtest (subagent: runner)
Skip this step if the spec says `Backtest: none`.
- Run `uv run eurohoops backtest --model <id>` (or the diagnostic script) in the worktree.
- Compare the result with the baseline **on the same games**, using `eval/promotion.py` `bootstrap_ci` on the per-game log-loss differences.
- Return: n games, mean gap, 95% CI, and the path of the report JSON.

Then the orchestrator decides:
- **Spec's backtest bar passed** → go to step 5.
- **Failed** → fill in `Result:` (fail, plus the numbers), commit, merge **only** `experiments/<id>.md` to main, and delete the branch and worktree. Stop.
- **Diagnostic** → fill in `Result:`, merge (script, report and spec), and stop. Diagnostics never go live.

## Step 5 — Go live (orchestrator)
- Set `<ID>_LIVE_ENABLED = True`.
- Run the checklist on the branch.
- Merge `exp/<id>` into main and run the checklist on main.
- Remove the worktree and delete the branch. Push only if the task says so.

From the next daily run, the shadow logs and is scored automatically. Nothing else to do until a checkpoint.

## Step 6 — Checkpoint (orchestrator, at each checkpoint in rule 4)
Spawn one runner per live shadow, in parallel. Each one:
- pairs the shadow's log with the published model's log on the shared finished games (`eval/promotion.py` `paired_log_losses`);
- computes the standard test (`bootstrap_ci`, `promotion_verdict`);
- writes `reports/checkpoint_<id>_<comp>_look<N>.json`.

For the flagship (M5 for EuroLeague, M1 for GBL), use `uv run eurohoops promote-check --competition <comp> --look <N>`.

Then the orchestrator decides:
- **Pass** → promote. Point `publish.py` and the site at the shadow, and keep the old model as a shadow. Commit.
- **Fail at look 1** → leave it running.
- **Fail at season end** → set its flag to False and delete its live code; keep its log. Commit.

## Step 7 — Close (orchestrator)
- Fill in `Result:` in `experiments/<id>.md`: pass, fail or inconclusive, with n, mean gap and CI. Commit to main.
- Update the model's card in `docs/models/` (what it is, results, status) when the model is new or changed status.
- Report to the owner in 3–5 lines: outcome first, then the numbers.

---

## Running several experiments
- Each experiment gets its own worktree and branch. Run at most **2** at once on this machine (memory), with tests on `-n 4`.
- Merge one at a time. After each merge, rerun the checklist on main before the next one.
- Shared files (`config.py`, `readmodel.py`, `api_export.py`, `vulture_whitelist.py`, `cli/live.py`) conflict only by adding lines. Resolve by keeping both sides.

## Subagent brief (copy for each spawn)
```
Experiment <id>. Worktree: <path>, branch exp/<id>. Spec: experiments/<id>.md.
Your step: <2 build | 3 review | 4 backtest | 6 checkpoint>, as written in workflow.md.
Rules: CLAUDE.md. Do not merge, push or touch main.
Return: <the step's return list>.
```
