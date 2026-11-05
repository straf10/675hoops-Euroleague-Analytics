"""``eurohoops backtest`` and the model-specific backtest wiring (Elo, M3, M5, M6, M7)."""

import json
import subprocess
import time
from functools import partial
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from eurohoops import research
from eurohoops.cli._shared import ModelName, _live, exit_on_missing_inputs, log
from eurohoops.config import (
    BLEND_REPORT,
    ELOC_CV,
    ELOR_BASELINE_REPORT,
    EUROLEAGUE,
    M3,
    M5,
    M5_RETUNE,
    M6,
    M7,
    M7_V2,
    MART_PATH,
    WP_GAMES_REPORT,
    WP_REPORT,
)
from eurohoops.eval import eloc_cv
from eurohoops.eval.backtest import format_table, run_backtest
from eurohoops.eval.blend_backtest import FOLDS as BLEND_FOLDS
from eurohoops.eval.blend_backtest import WARMUP_FOLDS as BLEND_WARMUP_FOLDS
from eurohoops.eval.blend_backtest import run_blend
from eurohoops.eval.m1_backtest import format_m1_table, run_m1_backtest
from eurohoops.eval.m3_backtest import format_m3_table, run_m3_backtest
from eurohoops.eval.m5_backtest import (
    M5Inputs,
    PlayerPartFn,
    format_m5_table,
    run_m5_backtest,
)
from eurohoops.eval.m5_retune import (
    git_head_sha,
    is_clean_tree,
    retune_backtest_spec,
    retune_check,
    run_retune,
)
from eurohoops.eval.m6_backtest import format_m6_table, run_m6_backtest
from eurohoops.eval.m7_backtest import format_m7_table, run_m7_backtest, scored_splits
from eurohoops.eval.m7_gate_v2 import format_gate_v2, run_gate_v2
from eurohoops.eval.promotion import LookNotDueError, run_look
from eurohoops.eval.tracking import (
    default_tracking_uri,
    log_backtest,
    log_m3_backtest,
    log_m5_backtest,
    log_m6_backtest,
    log_m7_backtest,
)
from eurohoops.eval.wp_backtest import format_table as format_wp_table
from eurohoops.eval.wp_backtest import run as run_wp_backtest
from eurohoops.logs import write_json
from eurohoops.marts import read_games, read_table
from eurohoops.model_catalog import active_shadows
from eurohoops.model_inputs import m5_inputs, m5_player_ratings, m6_inputs, m7_inputs
from eurohoops.models.box_impact import BoxGrid, box_only_margins, pir_margins
from eurohoops.models.elo import EloParams
from eurohoops.models.player_part import (
    el_player_part,
)
from eurohoops.models.roster import read_rosters
from eurohoops.stats.box import build_box_games


def _backtest_m3(score_test: bool, tuning_only: bool, tracking_uri: str) -> None:
    """``backtest --model m3`` (week 9-12 H1): the EuroLeague player-impact backtest."""
    if EUROLEAGUE.m1 is None or not EUROLEAGUE.m1.report.exists():
        log.error("no committed M1 report; run: eurohoops backtest --model m1")
        raise typer.Exit(code=1)
    tuned_m1 = json.loads(EUROLEAGUE.m1.report.read_text(encoding="utf-8"))["tuned"]
    games = read_games(MART_PATH, EUROLEAGUE.name)
    team_games = read_table(MART_PATH, "team_games", EUROLEAGUE.name)
    stints = read_table(MART_PATH, "stints")
    checks = read_table(MART_PATH, "stint_game_checks")
    if team_games is None or stints is None or checks is None:
        log.error(
            "stints/stint_game_checks/team_games missing; run: eurohoops build / stints --mart"
        )
        raise typer.Exit(code=1)
    player_games = build_box_games(EUROLEAGUE.raw_dir, games).players
    report = run_m3_backtest(
        games,
        team_games,
        player_games,
        stints,
        checks,
        spec=M3,
        tuned_m1=tuned_m1,
        box_only_fn=partial(box_only_margins, grid=BoxGrid()),
        pir_fn=pir_margins,
        tuning_only=tuning_only,
        score_test=score_test,
    )
    write_json(M3.report, report)
    typer.echo(f"{M3.report}\n{format_m3_table(report)}")
    run_id = log_m3_backtest(report, tracking_uri)
    if run_id is not None:
        typer.echo(f"MLflow parent run {run_id}")


def _m5_player_part_el(inputs: M5Inputs, frame: pd.DataFrame) -> PlayerPartFn:
    """M3's committed ``rapm_spm`` (``reports/backtest_m3.json`` ``chosen``, never re-tuned),
    fitted walk-forward once over the frame; the player part is H-c's ``rapm_margins``."""
    with exit_on_missing_inputs():
        return el_player_part(m5_player_ratings(inputs, frame))


def _on_origin_main() -> bool:
    local = git_head_sha()
    try:
        remote = subprocess.check_output(["git", "rev-parse", "origin/main"], text=True).strip()
    except subprocess.CalledProcessError:
        return False
    return local == remote


def _backtest_m5_retune(check_only: bool) -> None:
    """``backtest --model m5 --retune`` or ``--retune-check`` (docs/models/m5.md)."""
    if M5_RETUNE.report.exists() and not check_only:
        log.error("refusing to run: %s already exists", M5_RETUNE.report)
        raise typer.Exit(code=1)
    if not check_only:
        if not is_clean_tree():
            log.error("refusing to run: the working tree is not clean")
            raise typer.Exit(code=1)
        if not _on_origin_main():
            log.error("refusing to run: HEAD is not the same as origin/main")
            raise typer.Exit(code=1)
    retune_spec = retune_backtest_spec(M5_RETUNE)
    with exit_on_missing_inputs():
        inputs, frame = m5_inputs(EUROLEAGUE, retune_spec)
    player_part = _m5_player_part_el(inputs, frame)
    if check_only:
        if not M5.games_report.exists():
            log.error("missing %s for the baseline check", M5.games_report)
            raise typer.Exit(code=1)
        baseline = pd.read_csv(M5.games_report)
        summary = retune_check(
            inputs, retune=M5_RETUNE, player_part=player_part, baseline_games=baseline
        )
        typer.echo(json.dumps(summary, indent=2))
        return
    started = time.perf_counter()
    report, detail = run_retune(
        inputs, retune=M5_RETUNE, player_part=player_part, git_head=git_head_sha()
    )
    write_json(M5_RETUNE.report, report)
    detail.to_csv(M5_RETUNE.games_report, index=False, lineterminator="\n")
    typer.echo(f"{M5_RETUNE.report}\n{json.dumps(report['selected'], indent=2)}")
    typer.echo(f"RUNTIME backtest m5 retune: {time.perf_counter() - started:.0f} s")


def _live_elo_params_match(params: EloParams) -> bool:
    report = EUROLEAGUE.live_backtest.report
    if not report.exists():
        return False
    tuned = json.loads(report.read_text(encoding="utf-8"))["tuned"]
    live = (float(tuned["k"]), float(tuned["hca"]), float(tuned["reversion"]))
    return live == (params.k, params.hca, params.reversion)


def _eloc_games() -> pd.DataFrame:
    """ELOC's input: the EuroLeague games mart (Elo's replay and the calibration seasons)."""
    return read_games(MART_PATH, EUROLEAGUE.name)


def _backtest_blend() -> None:
    """``backtest --model blend``: the candidate (docs/models/candidate_elo_blend.md).

    Writes reports/backtest_blend.json: the scored folds and the same protocol on the warm-up
    seasons. Read-only for the live log: nothing in predict or publish reads this report."""
    games = read_games(MART_PATH, "euroleague")
    minutes = build_box_games(EUROLEAGUE.raw_dir, games).players
    roster = read_rosters(EUROLEAGUE.raw_dir, range(2007, max(BLEND_FOLDS) + 1))
    _, report = run_blend(games, BLEND_FOLDS, minutes, roster)
    _, warmup = run_blend(games, BLEND_WARMUP_FOLDS, minutes, roster)
    write_json(BLEND_REPORT, {"folds": report, "warmup": warmup})
    log.info("wrote %s", BLEND_REPORT)


def _cv_backtest(model: ModelName, cv: bool, check_only: bool) -> None:
    """ELOC: exactly one of --cv or --cv-check."""
    if model is not ModelName.eloc or cv == check_only:
        log.error("%s runs as --model %s with exactly one of --cv or --cv-check", model, model)
        raise typer.Exit(code=1)
    _backtest_eloc(check_only=check_only)


def _elo_baseline() -> tuple[float, int]:
    """The frozen Elo baseline (``ELOR_BASELINE_REPORT``, written by the retired ELOR protocol):
    Elo's pooled log loss and scored games, the ELOC sanity check's baseline."""
    report = json.loads(ELOR_BASELINE_REPORT.read_text(encoding="utf-8"))
    return float(report["elo"]["log_loss"]), int(report["scored_games"])


def _backtest_eloc(check_only: bool) -> None:
    """``backtest --model eloc --cv`` or ``--cv-check`` (docs/models/elo_calibrated.md)."""
    if not _live_elo_params_match(ELOC_CV.elo_params):
        log.error("ELOC's fixed Elo parameters differ from %s", EUROLEAGUE.live_backtest.report)
        raise typer.Exit(code=1)
    if not check_only:
        if ELOC_CV.report.exists():
            log.error("refusing to run: %s already exists", ELOC_CV.report)
            raise typer.Exit(code=1)
        if not ELOR_BASELINE_REPORT.exists():
            log.error("refusing to run: the baseline report %s is missing", ELOR_BASELINE_REPORT)
            raise typer.Exit(code=1)
        if not is_clean_tree():
            log.error("refusing to run: the working tree is not clean")
            raise typer.Exit(code=1)
        if not _on_origin_main():
            log.error("refusing to run: HEAD is not the same as origin/main")
            raise typer.Exit(code=1)
    started = time.perf_counter()
    games = _eloc_games()
    if check_only:
        typer.echo(json.dumps(eloc_cv.cv_check(games, ELOC_CV), indent=2))
        typer.echo(f"RUNTIME backtest eloc cv-check: {time.perf_counter() - started:.0f} s")
        return
    baseline_log_loss, baseline_games = _elo_baseline()
    report, detail = eloc_cv.run_cv(
        games,
        spec=ELOC_CV,
        git_head=git_head_sha(),
        baseline_log_loss=baseline_log_loss,
        baseline_games=baseline_games,
    )
    write_json(ELOC_CV.report, report)
    detail.to_csv(ELOC_CV.games_report, index=False, lineterminator="\n")
    typer.echo(f"{ELOC_CV.report}\n{json.dumps(report['shadow_criteria'], indent=2)}")
    typer.echo(f"RUNTIME backtest eloc cv: {time.perf_counter() - started:.0f} s")


def _backtest_m5(score_test: bool, tuning_only: bool, tracking_uri: str) -> None:
    """``backtest --model m5`` (week 14-16 J4): the roster-aware predictor vs M1, Elo and B0."""
    spec, comp = M5, EUROLEAGUE
    started = time.perf_counter()
    with exit_on_missing_inputs():
        inputs, frame = m5_inputs(comp, spec)
    player_part = _m5_player_part_el(inputs, frame)
    report, predictions = run_m5_backtest(
        inputs,
        spec=spec,
        player_part=player_part,
        tuning_only=tuning_only,
        score_test=score_test,
    )
    write_json(spec.report, report)
    predictions.to_csv(spec.games_report, index=False, lineterminator="\n")
    typer.echo(f"{spec.report}\n{format_m5_table(report)}")
    typer.echo(f"RUNTIME backtest m5 {comp.name}: {time.perf_counter() - started:.0f} s")
    run_id = log_m5_backtest(report, comp.name, tracking_uri)
    if run_id is not None:
        typer.echo(f"MLflow run {run_id}")


def _backtest_m7(score_test: bool, tuning_only: bool, tracking_uri: str) -> None:
    """``backtest --model m7`` (week 14-16 K4): season simulation vs the real final tables."""
    spec, comp = M7, EUROLEAGUE
    started = time.perf_counter()
    with exit_on_missing_inputs():
        inputs = m7_inputs(comp, spec, tuple(scored_splits(spec, tuning_only, score_test)))
    report, rows = run_m7_backtest(
        inputs, spec=spec, tuning_only=tuning_only, score_test=score_test
    )
    write_json(spec.report, report)
    rows.to_csv(spec.teams_report, index=False, lineterminator="\n")
    typer.echo(f"{spec.report}\n{format_m7_table(report)}")
    typer.echo(f"RUNTIME backtest m7 {comp.name}: {time.perf_counter() - started:.0f} s")
    run_id = log_m7_backtest(report, comp.name, tracking_uri)
    if run_id is not None:
        typer.echo(f"MLflow run {run_id}")


def _backtest_m7_v2() -> None:
    """``backtest --model m7 --gate-v2``: the rolling-origin gate v2 (docs/models/m7.md), run
    once."""
    started = time.perf_counter()
    # every season, the selection one included: its overtime games need their regulation scores
    with exit_on_missing_inputs():
        inputs = m7_inputs(EUROLEAGUE, M7, M7_V2.tuning)
    report, rows = run_gate_v2(inputs, spec=M7_V2)
    write_json(M7_V2.report, report)
    rows.to_csv(M7_V2.teams_report, index=False, lineterminator="\n")
    typer.echo(f"{M7_V2.report}\n{format_gate_v2(report)}")
    typer.echo(f"RUNTIME backtest m7 gate v2: {time.perf_counter() - started:.0f} s")


def _backtest_wp(raw_dir: Path | None) -> None:
    """``backtest --model wp`` (docs/models/wp.md, protocol v1): the in-game WP gate, run once.
    EuroLeague only. Reads the raw play-by-play cache; writes the two reports and nothing else."""
    if WP_REPORT.exists():
        log.error("refusing to run: %s already exists (the gate is reported once)", WP_REPORT)
        raise typer.Exit(code=1)
    started = time.perf_counter()
    report, rows = run_wp_backtest(
        read_games(MART_PATH, EUROLEAGUE.name),
        raw_dir or EUROLEAGUE.raw_dir,
        progress=log.info,
    )
    write_json(WP_REPORT, report)
    rows.to_csv(WP_GAMES_REPORT, index=False, lineterminator="\n")
    typer.echo(f"{WP_REPORT}\n{format_wp_table(report)}")
    typer.echo(f"RUNTIME backtest wp: {time.perf_counter() - started:.0f} s")


def _backtest_m6(score_test: bool, tuning_only: bool, tracking_uri: str) -> None:
    """``backtest --model m6`` (weeks 16-18 L6): player projections vs Marcel and the naive
    baselines, next-season and rest-of-season."""
    spec, comp = M6, EUROLEAGUE
    started = time.perf_counter()
    with exit_on_missing_inputs():
        inputs = m6_inputs(spec)
    report, players = run_m6_backtest(
        inputs,
        spec=spec,
        competition=comp.name,
        tuning_only=tuning_only,
        score_test=score_test,
    )
    write_json(spec.report, report)
    spec.players_report.parent.mkdir(parents=True, exist_ok=True)
    players.to_csv(spec.players_report, index=False, lineterminator="\n")
    typer.echo(f"{spec.report}\n{format_m6_table(report)}")
    typer.echo(f"RUNTIME backtest m6 {comp.name}: {time.perf_counter() - started:.0f} s")
    run_id = log_m6_backtest(report, comp.name, tracking_uri)
    if run_id is not None:
        typer.echo(f"MLflow run {run_id}")


def backtest(  # noqa: PLR0911, PLR0912 -- one dispatch return per model
    *,
    model: Annotated[
        ModelName,
        typer.Option(
            help=(
                "elo (live), m1, m2, m3 (players), m5 (roster), "
                "m6 (projections), m7 (season), wp (in-game win probability, run once), "
                "eloc (calibrated Elo CV: --cv or --cv-check), "
                "blend (candidate: Elo + ridge margin, walk-forward; not live)"
            )
        ),
    ] = ModelName.elo,
    score_test: Annotated[
        bool,
        typer.Option(help="M1/M2/M3: also score the test seasons (only after the gate verdict)"),
    ] = False,
    tuning_only: Annotated[
        bool,
        typer.Option(help="M3: only the tuning grid and chosen variant (the verdict commit)"),
    ] = False,
    search: Annotated[
        bool,
        typer.Option(help="M2: run the declared Optuna study first (only when F4 changes)"),
    ] = False,
    tracking_uri: Annotated[
        str | None,
        typer.Option(help="M1/M3: MLflow tracking URI (default: SQLite store under ./mlruns)"),
    ] = None,
    gate_v2: Annotated[
        bool,
        typer.Option(
            help="M7: the rolling-origin gate v2 (docs/models/m7.md), EuroLeague, run once"
        ),
    ] = False,
    retune: Annotated[
        bool,
        typer.Option(help="M5: retune protocol v1 (docs/models/m5.md), EuroLeague, run once"),
    ] = False,
    retune_check: Annotated[
        bool,
        typer.Option(help="M5: retune harness check vs the committed M5 backtest margins"),
    ] = False,
    cv: Annotated[
        bool,
        typer.Option(help="ELOC: protocol v1 CV (docs/models/elo_calibrated.md), run once"),
    ] = False,
    cv_check_only: Annotated[
        bool,
        typer.Option("--cv-check", help="ELOC: read-only inputs check; writes nothing"),
    ] = False,
    raw_dir: Annotated[
        Path | None,
        typer.Option(help="WP: EuroLeague raw cache (read only; default data/raw/euroleague)"),
    ] = None,
) -> None:
    """Tune and score a model vs its baselines; the Elo live report holds the live parameters."""
    if cv or cv_check_only or model is ModelName.eloc:
        _cv_backtest(model, cv, cv_check_only)
        return
    if retune or retune_check:
        if model is not ModelName.m5:
            log.error("--retune and --retune-check belong to --model m5")
            raise typer.Exit(code=1)
        _backtest_m5_retune(check_only=retune_check)
        return
    if gate_v2:
        if model is not ModelName.m7:
            log.error("--gate-v2 belongs to --model m7")
            raise typer.Exit(code=1)
        _backtest_m7_v2()
        return
    if model is ModelName.blend:
        _backtest_blend()
        return
    if model is ModelName.wp:
        _backtest_wp(raw_dir)
        return
    if model is ModelName.m2:
        research.backtest_m2(score_test, search, tracking_uri or default_tracking_uri())
        return
    if model is ModelName.m3:
        _backtest_m3(score_test, tuning_only, tracking_uri or default_tracking_uri())
        return
    if model is ModelName.m5:
        _backtest_m5(score_test, tuning_only, tracking_uri or default_tracking_uri())
        return
    if model is ModelName.m6:
        _backtest_m6(score_test, tuning_only, tracking_uri or default_tracking_uri())
        return
    if model is ModelName.m7:
        _backtest_m7(score_test, tuning_only, tracking_uri or default_tracking_uri())
        return
    comp = EUROLEAGUE
    games = read_games(MART_PATH, comp.name)
    if model is ModelName.m1:
        team_games = read_table(MART_PATH, "team_games", comp.name)
        if team_games is None or comp.m1 is None:
            log.error("no team_games in the marts; run: eurohoops build")
            raise typer.Exit(code=1)
        report = run_m1_backtest(
            games, team_games, comp.m1, score_test=score_test, progress=log.info
        )
        write_json(comp.m1.report, report)
        typer.echo(f"{comp.m1.report}\n{format_m1_table(report)}")
        run_id = log_backtest(
            report, comp.name, report["data_sha256"], tracking_uri or default_tracking_uri()
        )
        if run_id is not None:
            typer.echo(f"MLflow parent run {run_id}")
        return
    for spec in (comp.live_backtest, *comp.history_backtests):
        report = run_backtest(games, spec)
        write_json(spec.report, report)
        typer.echo(f"{spec.report}\n{format_table(report)}")


def promote_check(
    look: Annotated[
        int, typer.Option(help="Pre-registered look: 1 (mid-season), 2 (season end)")
    ] = 1,
) -> None:
    """Promotion test of every active shadow (CLAUDE.md rule 4); refuses before the look's
    checkpoint is complete."""
    comp = EUROLEAGUE
    if look not in (1, 2):
        raise typer.BadParameter("look must be 1 or 2")
    live = _live(comp)
    try:
        result = run_look(
            comp.name,
            look,
            live.games,
            live.season,
            active_shadows(comp),
            comp.prediction_log,
            comp.manual_pushes,
            Path("reports"),
        )
    except LookNotDueError as exc:
        typer.echo(f"{exc}. Nothing computed.", err=True)
        raise typer.Exit(1) from exc
    for verdict, out in result.verdicts.values():
        typer.echo(f"{out}\n{json.dumps(verdict.as_dict(), indent=2)}")
    for tag, why in result.not_tested.items():
        typer.echo(f"{tag}: not tested: {why}")
