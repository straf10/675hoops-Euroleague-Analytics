"""``eurohoops backtest`` and the model-specific backtest wiring (Elo, M3, M5, M6, M7)."""

import json
import subprocess
import time
from functools import partial
from pathlib import Path
from typing import Annotated

import numpy as np
import pandas as pd
import typer

from eurohoops import research
from eurohoops.cli._shared import CompetitionName, CompetitionOption, ModelName, _live, log
from eurohoops.config import (
    COMPETITIONS,
    ELOC_CV,
    ELOR_CV,
    EUROLEAGUE,
    GBL,
    GREEK_EL_CLUBS,
    LIVE_SEASON,
    M2_REPORT,
    M3,
    M3_GBL,
    M3_PLAYERS_REPORT,
    M4,
    M5,
    M5_GBL,
    M5_RETUNE,
    M6,
    M6_GBL,
    M7,
    M7_GBL,
    M7_V2,
    MART_PATH,
    PLAYER_BIOS,
    PLAYER_XWALK_FILE,
    Competition,
    M5Backtest,
    M6Backtest,
    M7Backtest,
)
from eurohoops.eval import eloc_cv
from eurohoops.eval.backtest import format_table, run_backtest
from eurohoops.eval.elor_cv import ElorInputs, cv_check, run_cv
from eurohoops.eval.m1_backtest import format_m1_table, run_m1_backtest
from eurohoops.eval.m3_backtest import format_m3_table, run_m3_backtest
from eurohoops.eval.m3_gbl_backtest import (
    ElSpm,
    choose_model,
    el_spm_models,
    format_m3_gbl_table,
    run_m3_gbl_backtest,
)
from eurohoops.eval.m5_backtest import (
    Choice,
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
from eurohoops.eval.m6_backtest import M6Inputs, SpmFn, World, format_m6_table, run_m6_backtest
from eurohoops.eval.m7_backtest import M7Inputs, format_m7_table, run_m7_backtest, scored_splits
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
from eurohoops.live_m6 import person_names, query_rows
from eurohoops.logs import write_json
from eurohoops.marts import read_games, read_table
from eurohoops.models.board import (
    DIMENSIONS,
    Stability,
    board,
    derive_n_min,
    fg3_observations,
    fg3_rotation_n,
    on_off_observations,
    rotation_n,
    rotation_player_seasons,
    shot_making_observations,
    stability,
)
from eurohoops.models.box_impact import STAT_COLUMNS, BoxGrid, box_only_margins, pir_margins
from eurohoops.models.elo import EloParams, FloatArray
from eurohoops.models.elor import Appearances, NewcomerPrior, WalkForwardRatings, newcomer_priors
from eurohoops.models.minutes import expected_possessions
from eurohoops.models.player_part import (
    ElPlayerRatings,
    PlayerPartError,
    el_player_part,
    el_player_ratings,
    same_frame,
)
from eurohoops.models.player_seasons import (
    AGES_SCHEMA,
    COUNT_STATS,
    build_player_seasons,
    person_ids,
    player_ages,
    read_xwalk_file,
)
from eurohoops.models.projection import Translation
from eurohoops.models.roster import RosterCacheError, read_rosters
from eurohoops.models.similarity import BOX_FEATURES, embed, neighbours, raw_features
from eurohoops.parse.gbl_box_lines import build_gbl_player_games
from eurohoops.parse.player_names import gbl_names
from eurohoops.parse.schemas import validated
from eurohoops.sim.played import regulation_scores
from eurohoops.stats.box import build_box_games


def _backtest_m3_gbl(score_test: bool, tuning_only: bool) -> None:
    """``backtest --model m3 --competition gbl`` (week 9-12 H8): EL SPM transfer to GBL.

    Requires the committed EuroLeague M3 verdict (``reports/backtest_m3.json``) and GBL M1
    parameters. No MLflow logging for GBL."""
    if tuning_only:
        log.error("m3 GBL backtest has no variant choice; --tuning-only is not supported")
        raise typer.Exit(code=1)
    if not M3.report.exists():
        log.error("no committed M3 report; run: eurohoops backtest --model m3")
        raise typer.Exit(code=1)
    m3_report = json.loads(M3.report.read_text(encoding="utf-8"))
    chosen = m3_report.get("chosen")
    if not chosen or chosen.get("variant") != "rapm_spm":
        log.error("M3 chosen variant must be rapm_spm (see reports/backtest_m3.json)")
        raise typer.Exit(code=1)
    if GBL.m1 is None or not GBL.m1.report.exists():
        log.error(
            "no committed GBL M1 report; run: eurohoops backtest --model m1 --competition gbl"
        )
        raise typer.Exit(code=1)
    tuned_m1 = json.loads(GBL.m1.report.read_text(encoding="utf-8"))["tuned"]
    el_games = read_games(MART_PATH, EUROLEAGUE.name)
    stints = read_table(MART_PATH, "stints")
    checks = read_table(MART_PATH, "stint_game_checks")
    if stints is None or checks is None:
        log.error("stints/stint_game_checks missing; run: eurohoops stints --mart")
        raise typer.Exit(code=1)
    el_player_games = build_box_games(EUROLEAGUE.raw_dir, el_games).players
    gbl_games = read_games(MART_PATH, GBL.name)
    gbl_team_games = read_table(MART_PATH, "team_games", GBL.name)
    if gbl_team_games is None:
        log.error("no GBL team_games in the marts; run: eurohoops build")
        raise typer.Exit(code=1)
    gbl_box = build_gbl_player_games(GBL.raw_dir, gbl_games, gbl_team_games)
    el = el_spm_models(el_games, el_player_games, stints, checks, chosen)
    report = run_m3_gbl_backtest(
        gbl_games,
        gbl_team_games,
        gbl_box.table,
        spec=M3_GBL,
        el=el,
        tuned_m1=tuned_m1,
        box_only_fn=partial(box_only_margins, grid=BoxGrid()),
        pir_fn=pir_margins,
        box_pages_skipped=gbl_box.skipped,
        score_test=score_test,
    )
    write_json(M3_GBL.report, report)
    typer.echo(f"{M3_GBL.report}\n{format_m3_gbl_table(report)}")


def _backtest_m3(
    competition: CompetitionName, score_test: bool, tuning_only: bool, tracking_uri: str
) -> None:
    """``backtest --model m3`` (week 9-12 H1/H8): EuroLeague or GBL SPM transfer."""
    if competition is CompetitionName.gbl:
        _backtest_m3_gbl(score_test, tuning_only)
        return
    if competition is not CompetitionName.euroleague:
        log.error("m3 backtest supports EuroLeague and GBL only")
        raise typer.Exit(code=1)
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


def _m5_inputs(
    comp: Competition, other: Competition, spec: M5Backtest, club_map: dict[str, str]
) -> tuple[M5Inputs, pd.DataFrame]:
    """M5's inputs for ``comp``: every game up to the last test season (the live season never
    enters, so the daily log cannot move the report), the other competition's games for rest,
    M1's committed parameters and comparison Elo. Also returns the backtest frame (M3's order)."""
    if comp.m1 is None or not comp.m1.report.exists():
        log.error("no committed M1 report for %s; run: eurohoops backtest --model m1", comp.name)
        raise typer.Exit(code=1)
    m1_report = json.loads(comp.m1.report.read_text(encoding="utf-8"))
    last = spec.test[-1]
    games = read_games(MART_PATH, comp.name)
    games = games[games["season"] <= last].reset_index(drop=True)
    other_games = read_games(MART_PATH, other.name)
    other_games = other_games[other_games["season"] <= last].reset_index(drop=True)
    team_games = read_table(MART_PATH, "team_games", comp.name)
    if team_games is None:
        log.error("no team_games in the marts; run: eurohoops build")
        raise typer.Exit(code=1)
    team_games = team_games[team_games["game_id"].isin(set(games["game_id"]))]
    if comp is EUROLEAGUE:
        player_games = build_box_games(comp.raw_dir, games).players
    else:
        player_games = build_gbl_player_games(comp.raw_dir, games, team_games).table
    inputs = M5Inputs(
        games=games,
        team_games=team_games.reset_index(drop=True),
        player_games=player_games,
        other_games=other_games,
        club_map=club_map,
        tuned_m1=m1_report["tuned"],
        elo=m1_report["comparison_elo"],
    )
    frame = (
        games[games["season"].between(spec.warmup[0], last)]
        .sort_values("tipoff_utc")
        .reset_index(drop=True)
    )
    return inputs, frame


def _m5_player_part_el(inputs: M5Inputs, frame: pd.DataFrame) -> PlayerPartFn:
    """M3's committed ``rapm_spm`` (``reports/backtest_m3.json`` ``chosen``, never re-tuned),
    fitted walk-forward once over the frame; the player part is H-c's ``rapm_margins``."""
    return el_player_part(_el_player_ratings(inputs, frame))


def _el_player_ratings(inputs: M5Inputs, frame: pd.DataFrame) -> ElPlayerRatings:
    try:
        return el_player_ratings(
            frame, inputs.player_games, inputs.team_games, m3_report=M3.report, mart_path=MART_PATH
        )
    except PlayerPartError as error:
        log.error("%s", error)
        raise typer.Exit(code=1) from error


def _m5_player_part_gbl(inputs: M5Inputs, frame: pd.DataFrame, spec: M5Backtest) -> PlayerPartFn:
    """GBL box-only player ratings (J-g: no GBL RAPM), tuned on the tuning seasons per call."""
    possessions = expected_possessions(frame, inputs.team_games)
    rated = (frame["played"] & ~frame["forfeit"]).to_numpy()
    tuning = rated & frame["season"].isin(spec.tuning).to_numpy()

    def player_part(games: pd.DataFrame, shares: pd.DataFrame) -> FloatArray:
        same_frame(frame, games)
        result = box_only_margins(
            games, inputs.player_games, shares, possessions, tuning, grid=BoxGrid()
        )
        return result.margin

    return player_part


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
    inputs, frame = _m5_inputs(EUROLEAGUE, GBL, retune_spec, dict(GREEK_EL_CLUBS))
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


def _elor_inputs() -> ElorInputs:
    """ELOR's inputs: every EuroLeague game up to the last fold, the M5 retune frame's M3
    walk-forward fit (warm-up 2011) and the cached roster lists of the fold seasons."""
    inputs, frame = _m5_inputs(
        EUROLEAGUE, GBL, retune_backtest_spec(M5_RETUNE), dict(GREEK_EL_CLUBS)
    )
    ratings = _el_player_ratings(inputs, frame)
    try:
        roster = read_rosters(EUROLEAGUE.raw_dir, ELOR_CV.folds)
    except RosterCacheError as error:
        log.error("%s", error)
        raise typer.Exit(code=1) from error
    source = WalkForwardRatings(ratings.frame, ratings.wf.lookups, inputs.player_games)
    return ElorInputs(
        games=inputs.games,
        player_games=inputs.player_games,
        roster=roster,
        rating=source,
        has_state=source.has_state,
        possessions=ratings.possessions,
        season_end_rating=source.at_season_end,
    )


def _elor_live_priors() -> dict[int, NewcomerPrior]:
    """The live season's newcomer prior (reported by ``--cv-check`` only): M5's frame up to its
    last test season, so every season before the live one, and its own M3 walk-forward fit."""
    inputs, frame = _m5_inputs(EUROLEAGUE, GBL, M5, dict(GREEK_EL_CLUBS))
    ratings = _el_player_ratings(inputs, frame)
    source = WalkForwardRatings(ratings.frame, ratings.wf.lookups, inputs.player_games)
    appearances = Appearances(inputs.games, inputs.player_games)
    # The fold seasons too: a cross-check that this fit gives the CV frame's fold priors.
    return newcomer_priors(appearances, source.at_season_end, [*ELOR_CV.folds, LIVE_SEASON])


def _live_elo_params_match(params: EloParams = ELOR_CV.elo_params) -> bool:
    report = EUROLEAGUE.live_backtest.report
    if not report.exists():
        return False
    tuned = json.loads(report.read_text(encoding="utf-8"))["tuned"]
    live = (float(tuned["k"]), float(tuned["hca"]), float(tuned["reversion"]))
    return live == (params.k, params.hca, params.reversion)


def _eloc_games() -> pd.DataFrame:
    """ELOC's input: the EuroLeague games mart (Elo's replay and the calibration seasons)."""
    return read_games(MART_PATH, EUROLEAGUE.name)


def _cv_backtest(
    model: ModelName, competition: CompetitionName, cv: bool, check_only: bool
) -> None:
    """ELOR and ELOC: exactly one of --cv or --cv-check, EuroLeague only."""
    if model not in (ModelName.elor, ModelName.eloc) or cv == check_only:
        log.error("%s runs as --model %s with exactly one of --cv or --cv-check", model, model)
        raise typer.Exit(code=1)
    if competition is not CompetitionName.euroleague:
        log.error("%s is the EuroLeague's", model.upper())
        raise typer.Exit(code=1)
    if model is ModelName.eloc:
        _backtest_eloc(check_only=check_only)
    else:
        _backtest_elor(check_only=check_only)


def _backtest_eloc(check_only: bool) -> None:
    """``backtest --model eloc --cv`` or ``--cv-check`` (docs/models/elo_calibrated.md)."""
    if not _live_elo_params_match(ELOC_CV.elo_params):
        log.error("ELOC's fixed Elo parameters differ from %s", EUROLEAGUE.live_backtest.report)
        raise typer.Exit(code=1)
    if not check_only:
        if ELOC_CV.report.exists():
            log.error("refusing to run: %s already exists", ELOC_CV.report)
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
    report, detail = eloc_cv.run_cv(games, spec=ELOC_CV, git_head=git_head_sha())
    write_json(ELOC_CV.report, report)
    detail.to_csv(ELOC_CV.games_report, index=False, lineterminator="\n")
    typer.echo(f"{ELOC_CV.report}\n{json.dumps(report['shadow_criteria'], indent=2)}")
    typer.echo(f"RUNTIME backtest eloc cv: {time.perf_counter() - started:.0f} s")


def _backtest_elor(check_only: bool) -> None:
    """``backtest --model elor --cv`` or ``--cv-check`` (docs/models/elo_roster_prior.md)."""
    if not _live_elo_params_match():
        log.error("ELOR's fixed Elo parameters differ from %s", EUROLEAGUE.live_backtest.report)
        raise typer.Exit(code=1)
    if not check_only:
        if ELOR_CV.report.exists():
            log.error("refusing to run: %s already exists", ELOR_CV.report)
            raise typer.Exit(code=1)
        if not is_clean_tree():
            log.error("refusing to run: the working tree is not clean")
            raise typer.Exit(code=1)
        if not _on_origin_main():
            log.error("refusing to run: HEAD is not the same as origin/main")
            raise typer.Exit(code=1)
    started = time.perf_counter()
    inputs = _elor_inputs()
    if check_only:
        live = _elor_live_priors()
        typer.echo(json.dumps(cv_check(inputs, spec=ELOR_CV, live_priors=live), indent=2))
        typer.echo(f"RUNTIME backtest elor cv-check: {time.perf_counter() - started:.0f} s")
        return
    report, detail = run_cv(inputs, spec=ELOR_CV, git_head=git_head_sha())
    write_json(ELOR_CV.report, report)
    detail.to_csv(ELOR_CV.games_report, index=False, lineterminator="\n")
    typer.echo(f"{ELOR_CV.report}\n{json.dumps(report['selected'], indent=2)}")
    typer.echo(json.dumps(report["shadow_criteria"], indent=2))
    typer.echo(f"RUNTIME backtest elor cv: {time.perf_counter() - started:.0f} s")


def _backtest_m5(
    competition: CompetitionName, score_test: bool, tuning_only: bool, tracking_uri: str
) -> None:
    """``backtest --model m5`` (week 14-16 J4): the roster-aware predictor vs M1, Elo and B0."""
    if competition is CompetitionName.euroleague:
        spec, comp, other, club_map = M5, EUROLEAGUE, GBL, dict(GREEK_EL_CLUBS)
    else:
        spec, comp, other = M5_GBL, GBL, EUROLEAGUE
        club_map = {el: gbl_id for gbl_id, el in GREEK_EL_CLUBS.items()}
    fixed = None
    if comp is GBL:  # J-g: the EuroLeague verdict's choice, no GBL-specific choice
        if tuning_only or not M5.report.exists():
            log.error("GBL M5 scores the committed EuroLeague verdict; run the EuroLeague first")
            raise typer.Exit(code=1)
        fixed = Choice(**json.loads(M5.report.read_text(encoding="utf-8"))["chosen"]["choice"])
    started = time.perf_counter()
    inputs, frame = _m5_inputs(comp, other, spec, club_map)
    if comp is EUROLEAGUE:
        player_part = _m5_player_part_el(inputs, frame)
    else:
        player_part = _m5_player_part_gbl(inputs, frame, spec)
    report, predictions = run_m5_backtest(
        inputs,
        spec=spec,
        player_part=player_part,
        tuning_only=tuning_only,
        score_test=score_test,
        fixed=fixed,
    )
    write_json(spec.report, report)
    predictions.to_csv(spec.games_report, index=False, lineterminator="\n")
    typer.echo(f"{spec.report}\n{format_m5_table(report)}")
    typer.echo(f"RUNTIME backtest m5 {comp.name}: {time.perf_counter() - started:.0f} s")
    run_id = log_m5_backtest(report, comp.name, tracking_uri)
    if run_id is not None:
        typer.echo(f"MLflow run {run_id}")


def _m7_inputs(comp: Competition, spec: M7Backtest, seasons: tuple[int, ...]) -> M7Inputs:
    """M7's inputs for ``comp``: every game up to the last test season (the live season never
    enters, so the daily log cannot move the report), M1's committed parameters and comparison
    Elo, and the EuroLeague's regulation scores of the scored regular seasons."""
    if comp.m1 is None or not comp.m1.report.exists():
        log.error("no committed M1 report for %s; run: eurohoops backtest --model m1", comp.name)
        raise typer.Exit(code=1)
    m1_report = json.loads(comp.m1.report.read_text(encoding="utf-8"))
    games = read_games(MART_PATH, comp.name)
    games = games[games["season"] <= spec.test[-1]].reset_index(drop=True)
    team_games = read_table(MART_PATH, "team_games", comp.name)
    if team_games is None:
        log.error("no team_games in the marts; run: eurohoops build")
        raise typer.Exit(code=1)
    team_games = team_games[team_games["game_id"].isin(set(games["game_id"]))]
    scored = games[(games["phase"] == "RS") & games["season"].isin(seasons)]
    return M7Inputs(
        competition=comp.name,
        games=games,
        team_games=team_games.reset_index(drop=True),
        regulation=regulation_scores(comp.raw_dir, scored) if comp is EUROLEAGUE else {},
        tuned_m1=m1_report["tuned"],
        elo=m1_report["comparison_elo"],
    )


def _backtest_m7(
    competition: CompetitionName, score_test: bool, tuning_only: bool, tracking_uri: str
) -> None:
    """``backtest --model m7`` (week 14-16 K4): season simulation vs the real final tables."""
    spec, comp = (M7, EUROLEAGUE) if competition is CompetitionName.euroleague else (M7_GBL, GBL)
    fixed = None
    if comp is GBL:  # K-a: the EuroLeague verdict, no GBL-specific choice
        if tuning_only or not M7.report.exists():
            log.error("GBL M7 scores the committed EuroLeague verdict; run the EuroLeague first")
            raise typer.Exit(code=1)
        fixed = json.loads(M7.report.read_text(encoding="utf-8"))["chosen"]["key"]
    started = time.perf_counter()
    inputs = _m7_inputs(comp, spec, tuple(scored_splits(spec, tuning_only, score_test)))
    report, rows = run_m7_backtest(
        inputs, spec=spec, tuning_only=tuning_only, score_test=score_test, fixed=fixed
    )
    write_json(spec.report, report)
    rows.to_csv(spec.teams_report, index=False, lineterminator="\n")
    typer.echo(f"{spec.report}\n{format_m7_table(report)}")
    typer.echo(f"RUNTIME backtest m7 {comp.name}: {time.perf_counter() - started:.0f} s")
    run_id = log_m7_backtest(report, comp.name, tracking_uri)
    if run_id is not None:
        typer.echo(f"MLflow run {run_id}")


def _backtest_m7_v2(competition: CompetitionName) -> None:
    """``backtest --model m7 --gate-v2``: the rolling-origin gate v2 (docs/models/m7.md), run once;
    EuroLeague only (the GBL is not gated)."""
    if competition is not CompetitionName.euroleague:
        log.error("M7 gate v2 is the EuroLeague's; the GBL is not gated")
        raise typer.Exit(code=1)
    started = time.perf_counter()
    # every season, the selection one included: its overtime games need their regulation scores
    inputs = _m7_inputs(EUROLEAGUE, M7, M7_V2.tuning)
    report, rows = run_gate_v2(inputs, spec=M7_V2)
    write_json(M7_V2.report, report)
    rows.to_csv(M7_V2.teams_report, index=False, lineterminator="\n")
    typer.echo(f"{M7_V2.report}\n{format_gate_v2(report)}")
    typer.echo(f"RUNTIME backtest m7 gate v2: {time.perf_counter() - started:.0f} s")


def _m6_brapm(xwalk: pd.DataFrame) -> pd.DataFrame:
    """The season-end BRAPM snapshots of ``reports/m3_players.json`` as ``IMPACT_SCHEMA`` rows
    (``total`` and ``sd_total`` of the players the snapshot saw, mapped to persons)."""
    report = json.loads(M3_PLAYERS_REPORT.read_text(encoding="utf-8"))
    frames = []
    for season, block in report["seasons"].items():
        players = pd.DataFrame(block["players"])
        players = players[players["seen"]]
        ids = person_ids(players["player_id"], EUROLEAGUE.name, xwalk)
        frames.append(
            pd.DataFrame(
                {
                    "person_id": ids["person_id"].to_numpy(),
                    "competition": EUROLEAGUE.name,
                    "season": int(season),
                    "stat": "brapm",
                    "value": players["total"].to_numpy(dtype="float64"),
                    "sd": players["sd_total"].to_numpy(dtype="float64"),
                }
            )
        )
    rows = pd.concat(frames, ignore_index=True)
    rows = rows.drop_duplicates(["person_id", "competition", "season", "stat"])
    return rows.sort_values(["season", "person_id"]).reset_index(drop=True)


def _m6_translations(stats: tuple[str, ...] = COUNT_STATS) -> dict[int, Translation]:
    """M4's fit for each target season (``reports/m4_translation.json``) for ``stats``: the count
    stats, or SPM's eleven for the undervalued list."""
    fits = json.loads(M4.translation_report.read_text(encoding="utf-8"))["fits_by_target_season"]
    return {
        int(season): Translation(
            delta={s: float(fit["translate"][s]["delta"]) for s in stats},
            c={s: float(fit["translate"][s]["c"]) for s in stats},
            target_season=int(season),
        )
        for season, fit in fits.items()
    }


def _league_rates(player_games: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per competition and season the league's per-100 rate of each SPM stat (all lines with
    seconds played, possession-weighted), indexed by (competition, season)."""
    frames = []
    for competition, all_lines in player_games.items():
        lines = all_lines[all_lines["sec"] > 0]
        sums = lines.groupby("season")[[*STAT_COLUMNS, "poss"]].sum()
        rates = 100.0 * sums[list(STAT_COLUMNS)].div(sums["poss"], axis=0)
        frames.append(rates.assign(competition=competition).set_index("competition", append=True))
    return pd.concat(frames).reorder_levels(["competition", "season"]).sort_index()


def _m6_spm(el: ElSpm, league: pd.DataFrame) -> SpmFn:
    """The injected SPM: ``before_season``'s EuroLeague SPM model (fitted on data before that
    season; the latest one when there is none for it) applied to each row's per-100 box rates
    minus the league rate of the row's previous season (never the row's own season: at a
    checkpoint that would read games after the cutoff; the first season has none and uses
    its own, which no checkpoint reads); SPM = O + D. Unshrunk rates. A season without its own
    model raises: falling back to a later model would read data after the season's start."""

    def spm(frame: pd.DataFrame, before_season: int) -> "pd.Series[float]":
        if before_season not in el.fit_time:
            raise ValueError(f"no EuroLeague SPM model for season {before_season}")
        model = choose_model(el, el.fit_time[before_season])
        if model is None:
            raise ValueError(f"no EuroLeague SPM model for season {before_season}")
        base = []
        for competition, season in zip(frame["competition"], frame["season"], strict=True):
            rates = league.loc[competition]
            earlier = rates.loc[: int(season) - 1]
            base.append((earlier if len(earlier) else rates).iloc[-1].to_numpy(dtype="float64"))
        features = frame[list(model.stats)].to_numpy(dtype="float64") - np.array(base)
        o, d = model.predict(features)
        return pd.Series(o + d, index=frame.index)

    return spm


def _m6_bios() -> pd.DataFrame:
    if not PLAYER_BIOS.exists():
        log.error("no player bios; run: eurohoops bios")
        raise typer.Exit(code=1)
    return pd.read_parquet(PLAYER_BIOS)


def _m6_inputs(spec: M6Backtest, *, live: bool = False) -> M6Inputs:
    """M6's inputs: both competitions' games and player games up to the last test season (the live
    season never enters, so the daily log cannot move the report), the crosswalk, in-memory ages,
    the BRAPM snapshots, M4's translations and the SPM wired from M3's EuroLeague models.
    ``live`` (``eurohoops project``): up to the live season, the committed crosswalk file (D25)
    and no ages (the chosen variant does not age, and the daily workflow has no bios)."""
    last = LIVE_SEASON if live else spec.test[-1]
    games = {c.name: read_games(MART_PATH, c.name) for c in (EUROLEAGUE, GBL)}
    games = {name: g[g["season"] <= last].reset_index(drop=True) for name, g in games.items()}
    team_games = read_table(MART_PATH, "team_games", GBL.name)
    xwalk = read_xwalk_file(PLAYER_XWALK_FILE) if live else read_table(MART_PATH, "player_xwalk")
    stints = read_table(MART_PATH, "stints")
    checks = read_table(MART_PATH, "stint_game_checks")
    if team_games is None or xwalk is None or stints is None or checks is None:
        log.error("team_games/player_xwalk/stints missing; run: eurohoops build / entity / stints")
        raise typer.Exit(code=1)
    team_games = team_games[team_games["game_id"].isin(set(games[GBL.name]["game_id"]))]
    player_games = {
        EUROLEAGUE.name: build_box_games(EUROLEAGUE.raw_dir, games[EUROLEAGUE.name]).players,
        GBL.name: build_gbl_player_games(GBL.raw_dir, games[GBL.name], team_games).table,
    }
    ages = (
        validated(pd.DataFrame({"person_id": [], "season": [], "age": []}), AGES_SCHEMA)
        if live
        else player_ages(_m6_bios(), xwalk, build_player_seasons(player_games, xwalk))
    )
    chosen = json.loads(M3.report.read_text(encoding="utf-8"))["chosen"]
    if chosen["variant"] != "rapm_spm":
        log.error("M3 chosen variant must be rapm_spm (see reports/backtest_m3.json)")
        raise typer.Exit(code=1)
    el_games = read_games(MART_PATH, EUROLEAGUE.name)
    el = el_spm_models(
        el_games[el_games["played"]] if live else el_games,
        player_games[EUROLEAGUE.name],
        stints,
        checks,
        chosen,
        last=LIVE_SEASON if live else M3.test[-1],
    )
    return M6Inputs(
        games=games,
        player_games=player_games,
        xwalk=xwalk,
        ages=ages,
        brapm=_m6_brapm(xwalk),
        spm=_m6_spm(el, _league_rates(player_games)),
        translations=_m6_translations(),
    )


def _backtest_m6(
    competition: CompetitionName, score_test: bool, tuning_only: bool, tracking_uri: str
) -> None:
    """``backtest --model m6`` (weeks 16-18 L6): player projections vs Marcel and the naive
    baselines, next-season and rest-of-season."""
    spec, comp = (M6, EUROLEAGUE) if competition is CompetitionName.euroleague else (M6_GBL, GBL)
    fixed = None
    if comp is GBL:  # L-a: the EuroLeague verdict, no GBL-specific choice
        if tuning_only or not M6.report.exists():
            log.error("GBL M6 scores the committed EuroLeague verdict; run the EuroLeague first")
            raise typer.Exit(code=1)
        chosen = json.loads(M6.report.read_text(encoding="utf-8"))["chosen"]
        fixed = {"variant": chosen["variant"], "half_life": chosen["half_life"]}
    started = time.perf_counter()
    inputs = _m6_inputs(spec)
    report, players = run_m6_backtest(
        inputs,
        spec=spec,
        competition=comp.name,
        tuning_only=tuning_only,
        score_test=score_test,
        fixed=fixed,
    )
    write_json(spec.report, report)
    spec.players_report.parent.mkdir(parents=True, exist_ok=True)
    players.to_csv(spec.players_report, index=False, lineterminator="\n")
    typer.echo(f"{spec.report}\n{format_m6_table(report)}")
    typer.echo(f"RUNTIME backtest m6 {comp.name}: {time.perf_counter() - started:.0f} s")
    run_id = log_m6_backtest(report, comp.name, tracking_uri)
    if run_id is not None:
        typer.echo(f"MLflow run {run_id}")


def _live_names(inputs: M6Inputs) -> dict[str, str]:
    """Display names: EuroLeague box spellings, the GBL live season's box pages and, locally, the
    ``player_names`` mart for the older GBL seasons."""
    live = inputs.player_games[GBL.name]
    live = live[live["season"] == LIVE_SEASON]
    box = live[["game_id", "team", "player_id", "sec"]].rename(columns={"sec": "seconds"})
    frames = [gbl_names(GBL.raw_dir, box)]
    mart = read_table(MART_PATH, "player_names", GBL.name) if MART_PATH.exists() else None
    if mart is not None:
        frames.insert(0, mart[mart["season"] < LIVE_SEASON])
    gbl = pd.concat(frames, ignore_index=True)
    return person_names(inputs.player_games[EUROLEAGUE.name], gbl, inputs.xwalk)


def _m2_shots(season: int) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """The ``shots`` and ``shot_xpts`` marts up to ``season`` and M2's chosen xPTS variant."""
    shots, xpts = read_table(MART_PATH, "shots"), read_table(MART_PATH, "shot_xpts")
    if shots is None or xpts is None:
        log.error("shots/shot_xpts missing; run: eurohoops shots, backtest --model m2")
        raise typer.Exit(code=1)
    variant = str(json.loads(M2_REPORT.read_text(encoding="utf-8"))["gate"]["chosen"])
    return shots[shots["season"] <= season], xpts, variant


def _m6_board(
    world: World, season: int, shots: pd.DataFrame, xpts: pd.DataFrame, variant: str
) -> tuple[pd.DataFrame, dict[str, Stability]]:
    """The over/under board of ``season`` (D23), stabilities from the M6 tuning seasons."""
    stints, checks = read_table(MART_PATH, "stints"), read_table(MART_PATH, "stint_game_checks")
    if stints is None or checks is None:
        log.error("no stints mart; run: eurohoops stints --mart")
        raise typer.Exit(code=1)
    xwalk = world.inputs.xwalk
    seasons = json.loads(M3_PLAYERS_REPORT.read_text(encoding="utf-8"))["seasons"]
    brapm = pd.concat(
        [
            pd.DataFrame(block["players"])[["player_id", "total", "sd_total"]].assign(season=int(s))
            for s, block in seasons.items()
        ],
        ignore_index=True,
    )
    complete = world.complete[~world.complete["partial"]]
    # N_MIN per dimension (rule v2): median n of EuroLeague rotation player-seasons, tuning only.
    rotation = rotation_player_seasons(complete, M6.tuning)
    tuned = {
        "shot_making": pd.concat(
            [shot_making_observations(shots, xpts, xwalk, s, variant) for s in M6.tuning]
        ),
        "on_off": pd.concat(
            [on_off_observations(stints, checks, brapm, xwalk, s) for s in M6.tuning]
        ),
    }
    n_min = {
        "shot_making": derive_n_min(rotation_n(tuned["shot_making"], rotation)),
        "fg3_pct": derive_n_min(fg3_rotation_n(complete, rotation)),
        "on_off": derive_n_min(rotation_n(tuned["on_off"], rotation)),
    }
    found: dict[str, dict[int, pd.DataFrame]] = {d: {} for d in DIMENSIONS}
    for s in (*M6.tuning, season):
        found["shot_making"][s] = shot_making_observations(shots, xpts, xwalk, s, variant)
        found["fg3_pct"][s] = fg3_observations(complete, s, n_min["fg3_pct"])
        found["on_off"][s] = on_off_observations(stints, checks, brapm, xwalk, s)
    stabilities = {
        d: stability(pd.concat([found[d][s] for s in M6.tuning]), d, M6.tuning, n_min[d])
        for d in DIMENSIONS
    }
    return board({d: found[d][season] for d in DIMENSIONS}, stabilities), stabilities


def _m6_similar(  # noqa: PLR0917 -- the live inputs, passed through
    world: World,
    people: list[str],
    season: int,
    shots: pd.DataFrame,
    xpts: pd.DataFrame,
    variant: str,
) -> tuple[pd.DataFrame, list[int], bool]:
    """Each live person's "plays like" list: his newest complete season with ``min_poss``
    possessions against every complete season up to ``season``."""
    joined = shots.merge(
        xpts.loc[xpts["variant"] == variant, ["game_id", "event", "p_make"]],
        on=["game_id", "event"],
    )
    mapped = person_ids(joined["shooter"], EUROLEAGUE.name, world.inputs.xwalk)["person_id"]
    frame = joined.assign(person_id=mapped.to_numpy(), xpts=joined["p_make"] * joined["value"])
    frame = frame[["person_id", "season", "made", "value", "x", "y", "band", "xpts"]]
    done = world.complete[~world.complete["partial"] & (world.complete["season"] <= season)]
    pool = sorted(int(s) for s in done["season"].unique())
    emb = embed(done, frame, pool_seasons=pool, min_poss=M6.min_poss)
    query = query_rows(world.complete, people, LIVE_SEASON, M6.min_poss)
    features = raw_features(query, frame[frame["person_id"].isin(set(query["person_id"]))])
    return neighbours(features, emb), pool, len(emb.features) > len(BOX_FEATURES)


def backtest(  # noqa: PLR0911, PLR0912 -- one dispatch return per model
    *,
    competition: CompetitionOption = CompetitionName.euroleague,
    model: Annotated[
        ModelName,
        typer.Option(
            help=(
                "elo (live), elor (roster prior CV), m1, m2, m3 (players), m4, m5 (roster), "
                "m6 (projections), m7 (season), eloc (calibrated Elo CV: --cv or --cv-check)"
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
        typer.Option(help="ELOR: protocol v1 CV (docs/models/elo_roster_prior.md), run once"),
    ] = False,
    cv_check_only: Annotated[
        bool,
        typer.Option("--cv-check", help="ELOR: read-only inputs check; writes nothing"),
    ] = False,
) -> None:
    """Tune and score a model vs its baselines; the Elo live report holds the live parameters."""
    if cv or cv_check_only or model in (ModelName.elor, ModelName.eloc):
        _cv_backtest(model, competition, cv, cv_check_only)
        return
    if retune or retune_check:
        if model is not ModelName.m5:
            log.error("--retune and --retune-check belong to --model m5")
            raise typer.Exit(code=1)
        if competition is not CompetitionName.euroleague:
            log.error("M5 retune is the EuroLeague's")
            raise typer.Exit(code=1)
        _backtest_m5_retune(check_only=retune_check)
        return
    if gate_v2:
        if model is not ModelName.m7:
            log.error("--gate-v2 belongs to --model m7")
            raise typer.Exit(code=1)
        _backtest_m7_v2(competition)
        return
    if model is ModelName.m2:
        research.backtest_m2(score_test, search, tracking_uri or default_tracking_uri())
        return
    if model is ModelName.m3:
        _backtest_m3(competition, score_test, tuning_only, tracking_uri or default_tracking_uri())
        return
    if model is ModelName.m4:
        research.backtest_m4(score_test=score_test, tuning_only=tuning_only)
        return
    if model is ModelName.m5:
        _backtest_m5(competition, score_test, tuning_only, tracking_uri or default_tracking_uri())
        return
    if model is ModelName.m6:
        _backtest_m6(competition, score_test, tuning_only, tracking_uri or default_tracking_uri())
        return
    if model is ModelName.m7:
        _backtest_m7(competition, score_test, tuning_only, tracking_uri or default_tracking_uri())
        return
    comp = COMPETITIONS[competition]
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
    competition: CompetitionOption = CompetitionName.euroleague,
    look: Annotated[
        int, typer.Option(help="Pre-registered look: 1 (mid-season), 2 (season end)")
    ] = 1,
) -> None:
    """Flagship promotion test (PLAN R1); refuses before the look's checkpoint is complete."""
    comp = COMPETITIONS[competition]
    flagship_log = comp.m5_prediction_log if competition == "euroleague" else comp.m1_prediction_log
    if look not in (1, 2) or flagship_log is None:
        raise typer.BadParameter("look must be 1 or 2")
    live = _live(comp)
    try:
        verdict, _ = run_look(
            competition,
            look,
            live.games,
            live.season,
            flagship_log,
            comp.prediction_log,
            comp.manual_pushes,
            Path("reports"),
            elor_log=comp.elor_prediction_log,
        )
    except LookNotDueError as exc:
        typer.echo(f"{exc}. Nothing computed.", err=True)
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(verdict.as_dict(), indent=2))
