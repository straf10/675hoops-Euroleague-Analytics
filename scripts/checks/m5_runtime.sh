#!/usr/bin/env bash
# Checklist item 46: `backtest --model m5` under 1,800 s for the EuroLeague, and the last RUNTIME line recorded in the progress file within the same limit.
# Reuses item 45's timed runs when it ran in the same checklist.
cd "$ROOT" || exit 1
export MLFLOW_DISABLE_AGENT_HINT=1
flag=$(uv run python -c "import json;print('--score-test' if json.load(open('reports/backtest_m5.json')).get('test_scored') else '')")
timed() {  # $1 = cache file
  if [ -s "$SCRATCH/$1" ]; then cat "$SCRATCH/$1"; return; fi
  start=$(date +%s)
  uv run eurohoops backtest --model m5 $flag \
    --tracking-uri "sqlite:///$(cygpath -m "$SCRATCH")/mlflow_m5.db" >/dev/null 2>&1 || { echo 99999; return; }
  echo $(( $(date +%s) - start ))
}
el=$(timed m5_runtime_s)
git checkout -q -- reports/backtest_m5.json reports/backtest_m5_games.csv 2>/dev/null
echo "RUNTIME euroleague $el s (limit 1800 s)"
[ "$el" -lt 1800 ]
