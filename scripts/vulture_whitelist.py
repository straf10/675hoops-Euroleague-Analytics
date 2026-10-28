"""Code built ahead of the pipeline step that will use it; vulture reads this file as usage.

Remove an entry as soon as the pipeline uses the name.
- standings.py: season simulator, PLAN §5.8
- the rest are names only tests or scripts/data_audit.py use today (vulture cannot see them).
"""

from eurohoops.standings import Format

# season simulator, PLAN §5.8: the elimination and relegation formats
Format.eliminated
Format.relegated

# week 9-12 subagent A: D6 convenience snapshot on top of build_minutes_rows, same hook
from eurohoops.models.rapm import fit_decayed_minutes  # noqa: E402

fit_decayed_minutes

# week 9-12 subagent D (H4: models/rapm_posterior.py): ridge_solution is a public entry point,
# not yet called from src
from eurohoops.models.rapm_posterior import ridge_solution  # noqa: E402

ridge_solution

# weeks 12-14 I7: interval fields reach reports/m4_translation.json through fits_report's asdict
from eurohoops.models.translation import StatFit  # noqa: E402

StatFit.delta_lo90
StatFit.delta_hi90

# weeks 14-16 J3: called by eval/m5_backtest.py (J4, wave 2)
from eurohoops.models.m5 import p_cover, p_over  # noqa: E402

p_over
p_cover

# weeks 16-18 C: the over/under board (L3) is called by the report writer and the L9 live run
from eurohoops.models.board import RetentionBacktest, retention_backtest  # noqa: E402

retention_backtest
RetentionBacktest.contrast_z  # read by the report writer and the board test

# weeks 16-18 D: the "plays like" search; self_retrieval_rate is the embedding's own check
from eurohoops.models.similarity import self_retrieval_rate  # noqa: E402

self_retrieval_rate

# weeks 16-18 E: the read-only API; FastAPI calls the response classes' attributes and uvicorn
# calls the factory named in the Dockerfile (`uvicorn --factory eurohoops.api.app:local_app`)
from eurohoops.api.app import CompactJSON, IndentedJSON, local_app  # noqa: E402

CompactJSON.media_type
CompactJSON.render
IndentedJSON.media_type
IndentedJSON.render
local_app

# weeks 16-18 H (L10): route_for is the inverse of file_for, read by the contract check
# (scripts/checks/api_export.py, tests/test_api_contract.py); write_stats is the pre-L10 writer,
# kept as the reference the byte-identical check compares the API export against
from eurohoops.api.export import route_for  # noqa: E402
from eurohoops.stats.export import write_stats  # noqa: E402

route_for
write_stats

# Phase A (GBL off the site): the Undervalued list is no longer published, but live_m6 still
# writes it and tests validate it against this schema
from eurohoops.api.readmodel import UNDERVALUED_ROWS_SCHEMA  # noqa: E402

UNDERVALUED_ROWS_SCHEMA

# validation.json keys: TypedDict fields the site reads, never this package
from eurohoops.stats.validate import SeasonReport  # noqa: E402

SeasonReport.games_scheduled

# playoff result strings: the exporter writes them, tests and docs list them
from eurohoops.stats.export import OTHER_RESULTS, RESULTS  # noqa: E402

RESULTS
OTHER_RESULTS

# R1 promotion verdict: fields are written to reports/promotion_*.json for the owner and site
from eurohoops.eval.promotion import Verdict  # noqa: E402

Verdict.flagship_log_loss
Verdict.elo_log_loss
Verdict.mean_diff
Verdict.ci_lo
Verdict.ci_hi
Verdict.ci_level
Verdict.min_gap
Verdict.ci_upper_below_zero
Verdict.mean_at_most_min_gap
Verdict.promote

# zip members: the metadata set in stats/downloads.py is read by zipfile when it writes the archive
from zipfile import ZipInfo  # noqa: E402

ZipInfo.compress_type
ZipInfo.create_system
ZipInfo.external_attr

# Data audit (scripts/data_audit.py, a read-only CLI over the marts)
from eurohoops.audit import run_audit  # noqa: E402

run_audit

# Data audit: the coach and standings checks (scripts/data_audit.py)
from eurohoops.audit_coaches import coach_findings  # noqa: E402
from eurohoops.audit_standings import standings_findings  # noqa: E402

coach_findings
standings_findings

# Audit: postponed-game reader (scripts/data_audit.py)
from eurohoops.audit_status import POSTPONED_REASON, is_postponed  # noqa: E402

POSTPONED_REASON
is_postponed

# B1 MKT benchmark: the live report entry point (scripts/checks/mkt_benchmark.py), tests only today
from eurohoops.eval.benchmark import benchmark  # noqa: E402

benchmark

# E1: power of the R1 looks, reporting only (scripts/r1_power.py)
from eurohoops.eval.r1_power import normal_cumulative_prob, simulate_promotion  # noqa: E402

normal_cumulative_prob
simulate_promotion

# B2 early-season totals diagnostic (scripts/diag_early_totals.py, research only)
from eurohoops.eval.early_totals import build_report  # noqa: E402

build_report

# POOL-c (docs/models/pool_c.md, draft gate): fit, frozen apply and the paired gap are written ahead
# of their pipeline step; nothing in src calls them until the owner commits the gate
from eurohoops.eval.pool_c import apply_c, fit_c, paired_gap  # noqa: E402

apply_c
fit_c
paired_gap

# POOL3 screen (experiments/pool3.md): diagnostic, run by scripts/diag_pool3.py, not the pipeline
from eurohoops.eval.pool3 import member_rows, screen  # noqa: E402

member_rows
screen
