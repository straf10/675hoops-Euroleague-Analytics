"""Live-season commands: project, sim-ungated, predict, odds, injuries, simulate, score."""

import csv
import hashlib
import json
import os
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
import typer

from eurohoops.cli._shared import (
    CompetitionName,
    CompetitionOption,
    Live,
    _live,
    _team_games,
    log,
    utc_now,
)
from eurohoops.cli.backtest import (
    _el_player_ratings,
    _live_names,
    _m2_shots,
    _m5_inputs,
    _m6_inputs,
    _m6_similar,
    _m6_translations,
)
from eurohoops.config import (
    COMPETITIONS,
    ELOC_CV,
    ELOH_FIT,
    ELOH_LIVE_ENABLED,
    ELOR_CV,
    EUROLEAGUE,
    GBL,
    GREEK_EL_CLUBS,
    INJURY_LOG,
    INJURY_RAW_DIR,
    LIVE_SEASON,
    M3_PLAYERS_REPORT,
    M5,
    M5INJ_LIVE_ENABLED,
    M6,
    M6_GBL,
    M6_PROJECTIONS,
    M6_SIMILARITY,
    M7,
    M7_GBL,
    M7_V2,
    MART_PATH,
    ODDS_CALLS,
    ODDS_RAW_DIR,
    ODDS_TEAMS,
    SIM_LATEST,
    SIM_LOGS,
    SIM_UNGATED,
    Competition,
    M6Backtest,
)
from eurohoops.eval.elor_cv import ElorInputs
from eurohoops.eval.m5_backtest import M5Inputs, PlayerPartFn
from eurohoops.eval.m6_backtest import M6Inputs, TargetInputs, World, prepare
from eurohoops.eval.scorecard import build_scorecard
from eurohoops.ingest.bios import el_people_path
from eurohoops.ingest.http import make_client
from eurohoops.injuries import InjuryPaths, probe_report, record_injuries, team_name_map
from eurohoops.inputs import INPUT_COLUMNS, backfill_rows
from eurohoops.live_eloc import eloc_logging_on, load_eloc, predict_upcoming_eloc
from eurohoops.live_eloh import load_eloh, predict_upcoming_eloh
from eurohoops.live_elor import load_elor, predict_upcoming_elor
from eurohoops.live_m1 import load_m1, predict_upcoming_m1
from eurohoops.live_m5 import LiveM5, live_spec, load_m5, predict_upcoming_m5
from eurohoops.live_m5inj import predict_upcoming_m5inj
from eurohoops.live_m6 import (
    inputs_digest,
    live_checkpoint,
    live_people,
    live_projections,
    personal_fields,
    player_rows,
    projections_report,
    similarity_report,
    undervalued,
)
from eurohoops.live_pool import predict_pool
from eurohoops.live_sim import (
    LIVE_SIMS,
    latest_report,
    load_sim,
    log_rows,
    run_live_sim,
    write_live_sim,
)
from eurohoops.logs import append_rows, write_json
from eurohoops.marts import read_games, read_table, read_teams
from eurohoops.models.availability import read_injuries, read_roster_names
from eurohoops.models.box_impact import STAT_COLUMNS
from eurohoops.models.elor import WalkForwardRatings
from eurohoops.models.player_part import ElPlayerRatings, el_player_part
from eurohoops.models.projection import Translation
from eurohoops.models.roster import RosterCacheError, read_rosters
from eurohoops.odds import OddsApiError, OddsPaths, api_key, record_odds
from eurohoops.predict import LatePredictionError, logged_keys, predict_upcoming
from eurohoops.sim.formats import season_format
from eurohoops.tipoff import first_tipoff_on


def _payload_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256((json.dumps(payload, indent=2) + "\n").encode("utf-8")).hexdigest()


def _live_block(  # noqa: PLR0917 -- one competition's live inputs
    inputs: M6Inputs,
    world: World,
    comp: Competition,
    spec: M6Backtest,
    report: dict[str, Any],
    chosen: dict[str, Any],
    translation: Translation,
) -> tuple[float, pd.DataFrame, TargetInputs]:
    """One competition's live checkpoint, projections and inputs."""
    games = inputs.games[comp.name]
    regular = games[(games["season"] == LIVE_SEASON) & (games["phase"] == "RS")]
    rounds = season_format(comp.name, LIVE_SEASON).regular_season_rounds
    checkpoint = live_checkpoint(regular, rounds, spec.checkpoints)
    rows, ti = live_projections(
        inputs,
        comp.name,
        LIVE_SEASON,
        checkpoint,
        live_people(world.complete, comp.name, LIVE_SEASON),
        chosen=chosen,
        scale=report["calibration"]["scale"][f"{checkpoint:g}"],
        spec=spec,
        translation=translation,
        rounds=rounds,
        world=world,
    )
    return checkpoint, rows, ti


def project(
    *,
    dry_run: Annotated[
        bool, typer.Option(help="Compute and print each report's sha256; write nothing")
    ] = False,
    projections_only: Annotated[
        bool,
        typer.Option(
            help="Only reports/m6_projections.json: the comparables need the local M2 shot marts "
            "(the daily workflow)"
        ),
    ] = False,
) -> None:
    """Live M6 (weeks 16-18 L9): the 2026-27 projections and the GBL undervalued list
    (reports/m6_projections.json) and the "plays like" lists (m6_similarity.json). Runs only
    when the EuroLeague M6 gate passed (L-l)."""
    started = time.perf_counter()
    specs = ((EUROLEAGUE, M6), (GBL, M6_GBL))
    if not all(spec.report.exists() for _, spec in specs):
        log.error("no committed M6 reports; run: eurohoops backtest --model m6")
        raise typer.Exit(code=1)
    reports = {c.name: json.loads(s.report.read_text(encoding="utf-8")) for c, s in specs}
    if not reports[EUROLEAGUE.name]["gate"]["passed"]:
        typer.echo("M6 did not pass its validation gate: the committed reports stay (L-l)")
        return
    chosen = reports[EUROLEAGUE.name]["chosen"]
    inputs = _m6_inputs(M6, live=True)
    world = prepare(inputs)
    newest = max(inputs.translations)  # D5: M4's newest fit, pairs strictly before it
    names = _live_names(inputs)
    checkpoints, blocks, players = {}, [], []
    projected = {}
    for comp, spec in specs:
        checkpoint, rows, ti = _live_block(
            inputs, world, comp, spec, reports[comp.name], chosen, inputs.translations[newest]
        )
        checkpoints[comp.name] = checkpoint
        projected[comp.name] = rows
        blocks.append(ti)
        live = world.complete[
            (world.complete["season"] == LIVE_SEASON) & (world.complete["competition"] == comp.name)
        ]
        players += player_rows(rows, live, names)
    gbl = world.complete[
        (world.complete["season"] == LIVE_SEASON) & (world.complete["competition"] == GBL.name)
    ]
    cheap = undervalued(
        projected[GBL.name],
        world.complete,
        LIVE_SEASON,
        translation=_m6_translations(STAT_COLUMNS)[newest],
        spm=inputs.spm,
        names=names,
        teams=dict(zip(gbl["person_id"], gbl["team"], strict=True)),
        min_poss=M6.min_poss,
    )
    payloads = {
        M6_PROJECTIONS: projections_report(
            chosen=chosen,
            gate_passed=True,
            season=LIVE_SEASON,
            checkpoints=checkpoints,
            digest=inputs_digest(blocks),
            players=players,
            undervalued_rows=cheap,
        )
    }
    if not projections_only:
        m3_seasons = json.loads(M3_PLAYERS_REPORT.read_text(encoding="utf-8"))["seasons"]
        season = max(int(s) for s in m3_seasons)  # D23: the newest complete season
        shots, xpts, variant = _m2_shots(season)
        people = sorted({p["person_id"] for p in players})
        similar, pool, shot_features = _m6_similar(world, people, season, shots, xpts, variant)
        payloads[M6_SIMILARITY] = similarity_report(
            similar, LIVE_SEASON, pool, shot_features, names
        )
    for path, payload in payloads.items():
        if found := personal_fields(payload):
            log.error("%s would carry an age or a birth date: %s", path, found[:5])
            raise typer.Exit(code=1)
        typer.echo(f"{path}: sha256 {_payload_sha(payload)}")
        if not dry_run:
            write_json(path, payload)
    typer.echo(
        f"{len(players)} projections (checkpoints {checkpoints}), {len(cheap)} undervalued"
        + ("; dry run, nothing written" if dry_run else "")
    )
    typer.echo(f"RUNTIME project: {time.perf_counter() - started:.0f} s")


def sim_ungated(competition: CompetitionOption = CompetitionName.euroleague) -> None:
    """The live season simulation for the Standings page (owner, D1): ``simulate``'s run written
    to reports/sim_ungated_{competition}.json whatever M7's gate says; labelled gated only for the
    EuroLeague once a gate passed (gate v2 did, 2026-10-09), never for the GBL. Never appends to
    the simulation log; rewritten only when the number of completed rounds changed (its time
    stamp is the cutoff), so a day without a completed round changes nothing."""
    comp = COMPETITIONS[competition]
    model = load_sim(M7.report, M7_V2.report)
    if comp.m1 is None or model is None or not comp.m1.report.exists():
        log.error("no committed M7 or M1 report; run: eurohoops backtest --model m7")
        raise typer.Exit(code=1)
    started = time.perf_counter()
    games = read_games(MART_PATH, comp.name)
    games = games[games["season"] <= LIVE_SEASON].reset_index(drop=True)
    team_games = read_table(MART_PATH, "team_games", comp.name)
    if team_games is None:
        log.error("no team_games in the marts; run: eurohoops build")
        raise typer.Exit(code=1)
    fmt = season_format(comp.name, LIVE_SEASON)
    tuned = json.loads(comp.m1.report.read_text(encoding="utf-8"))["tuned"]
    spec = M7 if comp is EUROLEAGUE else M7_GBL
    run = run_live_sim(
        games, team_games, tuned, model, fmt=fmt, season=LIVE_SEASON, spec=spec, n_sims=LIVE_SIMS
    )
    path = SIM_UNGATED[comp.name]
    if run is None:
        typer.echo(f"{comp.name}: the {LIVE_SEASON} regular season is over; {path} stays")
        return
    gated = model.gate_passed and comp is EUROLEAGUE
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if old is not None and (old["season"], old["after_round"], old.get("gated")) == (
        LIVE_SEASON,
        run.after_round,
        gated,
    ):
        typer.echo(f"{comp.name}: after round {run.after_round} already in {path}")
        return
    report = latest_report(run, model, fmt, LIVE_SEASON, run.cutoff.to_pydatetime())
    if comp is not EUROLEAGUE:
        reason = "the GBL is not gated (M7 gate v2): EuroLeague verdict, GBL rules unverified"
    elif model.gate_passed:
        reason = f"M7 passed its validation gate (gate v2, {M7_V2.report.as_posix()})"
    else:
        reason = f"M7 failed its validation gate ({M7.report.as_posix()}): this run is not gated"
    write_json(path, {**report, "gated": gated, "gate": {"passed": gated, "reason": reason}})
    label = "gated" if gated else "not gated"
    typer.echo(f"wrote {path}: after round {run.after_round}, seed {run.seed} ({label})")
    typer.echo(f"RUNTIME sim-ungated {comp.name}: {time.perf_counter() - started:.0f} s")


class _LiveFrame:
    """M5's live inputs, frame and M3 walk-forward fit, built once per ``predict`` run on first
    use and shared by the M5 and ELOR shadow logs (the fit is the slow part)."""

    def __init__(self, comp: Competition) -> None:
        self._comp = comp
        self._built: tuple[M5Inputs, ElPlayerRatings] | None = None

    def get(self) -> tuple[M5Inputs, ElPlayerRatings]:
        if self._built is None:
            spec = live_spec(M5, LIVE_SEASON)
            inputs, frame = _m5_inputs(self._comp, GBL, spec, dict(GREEK_EL_CLUBS))
            self._built = (inputs, _el_player_ratings(inputs, frame))
        return self._built

    def m5(self) -> tuple[M5Inputs, PlayerPartFn]:
        """The live M5 harness inputs and EuroLeague player part (``live_spec``)."""
        inputs, ratings = self.get()
        return inputs, el_player_part(ratings)

    def elor(self) -> ElorInputs:
        """ELOR's live inputs: the same fit, and the live season's cached roster list."""
        inputs, ratings = self.get()
        try:
            roster = read_rosters(EUROLEAGUE.raw_dir, (LIVE_SEASON,))
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


def _predict_m5inj(
    games: pd.DataFrame,
    *,
    m5: LiveM5 | None,
    frame: _LiveFrame,
    comp: Competition,
    season: int,
    round_lead_hours: float,
) -> None:
    """The M5-INJ shadow log: off unless M5INJ_LIVE_ENABLED (config.py) is set. It needs M5's
    report and the injury and roster caches. A shadow model never blocks the other logs."""
    if not M5INJ_LIVE_ENABLED or m5 is None or comp.m5inj_prediction_log is None:
        return
    try:
        added = predict_upcoming_m5inj(
            games,
            m5,
            frame.m5,
            injuries=read_injuries(INJURY_LOG),
            roster=read_roster_names(el_people_path(EUROLEAGUE.raw_dir, LIVE_SEASON)),
            log_path=comp.m5inj_prediction_log,
            season=season,
            round_lead=timedelta(hours=round_lead_hours),
            clock=utc_now,
        )
        typer.echo(f"{added} M5-INJ predictions appended to {comp.m5inj_prediction_log}")
    except LatePredictionError:
        raise
    except Exception:
        log.exception("M5-INJ skipped: its forecast failed; nothing appended to its log")


def _predict_eloc(
    games: pd.DataFrame, season: int, comp: Competition, round_lead_hours: float
) -> None:
    """The ELOC shadow log: off unless ELOC_LIVE_ENABLED (config.py) is set, and then it needs
    its CV report. A shadow model never blocks the Elo and M1 logs."""
    eloc = load_eloc(ELOC_CV.report) if eloc_logging_on(comp) else None
    if eloc is None or comp.eloc_prediction_log is None:
        return
    try:
        added = predict_upcoming_eloc(
            games,
            eloc,
            log_path=comp.eloc_prediction_log,
            season=season,
            round_lead=timedelta(hours=round_lead_hours),
            clock=utc_now,
        )
        typer.echo(f"{added} ELOC predictions appended to {comp.eloc_prediction_log}")
    except LatePredictionError:
        raise
    except Exception:
        log.exception("ELOC skipped: its forecast failed; nothing appended to its log")


def _predict_eloh(live: Live, comp: Competition, round_lead_hours: float) -> None:
    """The ELOH shadow log: off unless ELOH_LIVE_ENABLED (config.py) is set, and then it needs
    the frozen fit (reports/eloh_fit.json). A shadow model never blocks the Elo and M1 logs."""
    if not ELOH_LIVE_ENABLED or comp.eloh_prediction_log is None:
        return
    eloh = load_eloh(ELOH_FIT, live.model, live.replay_from)
    if eloh is None:
        log.warning("ELOH skipped: %s is missing", ELOH_FIT)
        return
    try:
        added = predict_upcoming_eloh(
            live.games,
            eloh,
            log_path=comp.eloh_prediction_log,
            season=live.season,
            round_lead=timedelta(hours=round_lead_hours),
            clock=utc_now,
        )
        typer.echo(f"{added} ELOH predictions appended to {comp.eloh_prediction_log}")
    except LatePredictionError:
        raise
    except Exception:
        log.exception("ELOH skipped: its forecast failed; nothing appended to its log")


def _predict_pool(log_path: Path | None) -> None:
    """POOL: reads the four component logs only; off while POOL_LIVE_ENABLED is False."""
    if log_path is None:
        return
    try:
        added = predict_pool(log_path=log_path)
        if added:
            typer.echo(f"{added} POOL predictions appended to {log_path}")
    except Exception:  # a shadow model never blocks the Elo, M1 or ELOR logs
        log.exception("POOL skipped: nothing appended to its log")


def predict(
    competition: CompetitionOption = CompetitionName.euroleague,
    round_lead_hours: Annotated[
        float, typer.Option(help="Log every round whose first tip-off is within this many hours")
    ] = 48.0,
) -> None:
    """Append pre-tip-off predictions for upcoming live-season games to the public log."""
    comp = COMPETITIONS[competition]
    live = _live(comp)
    try:
        added = predict_upcoming(
            live.games,
            live.model,
            log_path=comp.prediction_log,
            season=live.season,
            replay_from=live.replay_from,
            round_lead=timedelta(hours=round_lead_hours),
            clock=utc_now,
            inputs_log=comp.inputs_log,
        )
        typer.echo(f"{added} predictions appended to {comp.prediction_log}")
        m1 = None if comp.m1 is None else load_m1(comp.m1.report)
        if m1 is not None and comp.m1_prediction_log is not None:
            added = predict_upcoming_m1(
                live.games,
                _team_games(comp.name),
                m1,
                log_path=comp.m1_prediction_log,
                season=live.season,
                replay_from=live.replay_from,
                round_lead=timedelta(hours=round_lead_hours),
                clock=utc_now,
            )
            typer.echo(f"{added} M1 predictions appended to {comp.m1_prediction_log}")
        frame = _LiveFrame(comp)
        m5 = load_m5(M5.report) if comp.m5_prediction_log is not None else None
        if m5 is not None and comp.m5_prediction_log is not None:
            try:
                added = predict_upcoming_m5(
                    live.games,
                    m5,
                    frame.m5,
                    log_path=comp.m5_prediction_log,
                    season=live.season,
                    round_lead=timedelta(hours=round_lead_hours),
                    clock=utc_now,
                )
                typer.echo(f"{added} M5 predictions appended to {comp.m5_prediction_log}")
            except typer.Exit:  # a shadow model never blocks the Elo and M1 logs
                log.warning("M5 skipped: its marts, stints or reports are missing here")
            except LatePredictionError:
                raise
            except Exception:  # e.g. marts without the tuning seasons: still never blocks
                log.exception("M5 skipped: its forecast failed; nothing appended to its log")
        elor = load_elor(ELOR_CV.report) if comp.elor_prediction_log is not None else None
        if elor is not None and comp.elor_prediction_log is not None:
            try:
                added = predict_upcoming_elor(
                    live.games,
                    elor,
                    frame.elor,
                    log_path=comp.elor_prediction_log,
                    season=live.season,
                    round_lead=timedelta(hours=round_lead_hours),
                    clock=utc_now,
                )
                typer.echo(f"{added} ELOR predictions appended to {comp.elor_prediction_log}")
            except typer.Exit:  # a shadow model never blocks the Elo and M1 logs
                log.warning("ELOR skipped: its marts, stints, roster list or reports are missing")
            except LatePredictionError:
                raise
            except Exception:
                log.exception("ELOR skipped: its forecast failed; nothing appended to its log")
        _predict_m5inj(
            live.games,
            m5=m5,
            frame=frame,
            comp=comp,
            season=live.season,
            round_lead_hours=round_lead_hours,
        )
        _predict_eloc(live.games, live.season, comp, round_lead_hours)
        _predict_eloh(live, comp, round_lead_hours)
        _predict_pool(comp.pool_prediction_log)
    except LatePredictionError as exc:
        log.error("refusing to log: %s", exc)
        raise typer.Exit(code=1) from exc


def backfill_inputs(
    competition: Annotated[
        CompetitionName | None,
        typer.Option("--competition", help="Only this competition (default: all)"),
    ] = None,
) -> None:
    """Backfill the model-input snapshots (docs/match_report.md, section 1) for Elo rows logged
    before they existed: Elo is replayed over the games known at each row's predicted_at_utc, and
    a snapshot is appended only where the recomputed p_home and exp_margin equal the logged ones.
    Rows already in the inputs log are left alone; nothing else is written."""
    names = [competition] if competition is not None else list(CompetitionName)
    for name in names:
        comp = COMPETITIONS[name]
        if comp.inputs_log is None or comp.prediction_log is None:
            continue
        if not comp.prediction_log.exists():
            typer.echo(f"{comp.name}: no Elo log at {comp.prediction_log}; nothing to backfill")
            continue
        live = _live(comp)
        with comp.prediction_log.open(newline="", encoding="utf-8") as fh:
            elo_rows = list(csv.DictReader(fh))
        rows, report = backfill_rows(
            live.games,
            elo_rows,
            logged_keys(comp.inputs_log),
            live.model,
            live.replay_from,
        )
        append_rows(comp.inputs_log, INPUT_COLUMNS, rows)
        typer.echo(
            f"{comp.name}: {report.matched} matched and appended to {comp.inputs_log}, "
            f"{report.already} already present, {len(report.skipped)} skipped "
            f"(see warnings above)"
        )


def odds() -> None:
    """Record EuroLeague market odds: one The Odds API call, consensus rows appended."""
    key = api_key(os.environ, Path(".env"))
    if key is None:
        log.error("ODDS_API_KEY is not set (environment or .env); no call made")
        raise typer.Exit(code=1)
    assert EUROLEAGUE.odds_log is not None
    paths = OddsPaths(EUROLEAGUE.odds_log, ODDS_CALLS, ODDS_TEAMS, ODDS_RAW_DIR)
    try:
        with make_client() as client:
            summary = record_odds(
                client, key, read_games(MART_PATH, EUROLEAGUE.name), paths, utc_now
            )
    except OddsApiError as exc:
        log.error("odds: %s", exc)
        raise typer.Exit(code=1) from None
    typer.echo(
        f"{summary['rows_written']} consensus rows from {summary['events']} events appended to "
        f"{paths.log}; {len(summary['unmatched'])} unmatched; "
        f"requests remaining {summary['requests_remaining'] or '?'}"
    )


def injuries(
    probe: Annotated[
        bool,
        typer.Option("--probe", help="One fetch; print ok or failed; write nothing."),
    ] = False,
) -> None:
    """Record the BasketNews EuroLeague injury report: one request, a snapshot appended.

    A failed fetch, an unparseable page or a torn log is a warning, never a non-zero exit.
    ``--probe`` checks reachability only (for CI); it never writes the cache or the log.
    """
    if probe:
        with make_client() as client:
            summary = probe_report(client)
        if summary["status"] == "ok":
            typer.echo(
                f"injuries: probe ok; {summary['rows']} rows, {summary['teams']} teams"
                f" (page updated {summary.get('page_updated_utc') or '?'})"
            )
        else:
            typer.echo(f"injuries: probe failed; {summary['detail']}")
        return
    names = team_name_map(
        read_teams(MART_PATH, EUROLEAGUE.name), read_games(MART_PATH, EUROLEAGUE.name), LIVE_SEASON
    )
    paths = InjuryPaths(INJURY_LOG, INJURY_RAW_DIR)
    try:
        with make_client() as client:
            summary = record_injuries(client, names, paths, utc_now)
    except ValueError as exc:
        log.warning("injuries: %s; nothing recorded", exc)
        return
    typer.echo(
        f"injuries: {summary['status']}; {summary['rows']} rows, {summary['teams']} teams"
        f" (page updated {summary.get('page_updated_utc') or '?'}); log {paths.log}; "
        f"unmapped teams: {', '.join(summary['unmapped']) or 'none'}"
    )


def first_tipoff(
    today: Annotated[
        bool, typer.Option("--today", help="Today's games, by UTC date (required).")
    ] = False,
) -> None:
    """Print the UTC tip-off (ISO 8601, Z) of today's first confirmed, unplayed EuroLeague game;
    print nothing when there is none. Reads the games mart only: no network, no writes."""
    if not today:
        log.error("first-tipoff: pass --today")
        raise typer.Exit(code=2)
    found = first_tipoff_on(read_games(MART_PATH, EUROLEAGUE.name), utc_now().date())
    if found is not None:
        typer.echo(found.strftime("%Y-%m-%dT%H:%M:%SZ"))


def simulate(
    *,
    competition: CompetitionOption = CompetitionName.euroleague,
    dry_run: Annotated[
        bool, typer.Option(help="Compute and print the simulation; write nothing")
    ] = False,
) -> None:
    """Simulate the rest of the live regular season (M7, K8) after the completed rounds; the log
    is appended only when the EuroLeague M7 gate (v1 or v2) passed and the round is not logged
    yet. The GBL is not gated (gate v2, docs/models/m7.md): its log is never appended."""
    comp = COMPETITIONS[competition]
    model = load_sim(M7.report, M7_V2.report)
    if model is not None and comp is not EUROLEAGUE:
        model = replace(model, gate_passed=False)
    if comp.m1 is None or model is None or not comp.m1.report.exists():
        log.error("no committed M7 or M1 report; run: eurohoops backtest --model m7")
        raise typer.Exit(code=1)
    started = time.perf_counter()
    games = read_games(MART_PATH, comp.name)
    games = games[games["season"] <= LIVE_SEASON].reset_index(drop=True)
    team_games = read_table(MART_PATH, "team_games", comp.name)
    if team_games is None:
        log.error("no team_games in the marts; run: eurohoops build")
        raise typer.Exit(code=1)
    fmt = season_format(comp.name, LIVE_SEASON)
    tuned = json.loads(comp.m1.report.read_text(encoding="utf-8"))["tuned"]
    spec = M7 if comp is EUROLEAGUE else M7_GBL
    run = run_live_sim(
        games, team_games, tuned, model, fmt=fmt, season=LIVE_SEASON, spec=spec, n_sims=LIVE_SIMS
    )
    if run is None:
        typer.echo(f"{comp.name}: the {LIVE_SEASON} regular season is over; nothing to simulate")
        return
    now = datetime.now(UTC)
    for row in log_rows(run, model, LIVE_SEASON, now):
        typer.echo(
            f"{row['team']:<10}{row['p_direct_playoffs']:>8}{row['p_play_in']:>8}"
            f"{row['p_final_four']:>8}{row['p_title']:>8}{row['expected_wins']:>7}"
            f"  {row['rank_p10']}-{row['rank_p50']}-{row['rank_p90']}"
        )
    typer.echo(f"after round {run.after_round}, seed {run.seed}, gate passed {model.gate_passed}")
    if not dry_run:
        n = write_live_sim(
            run,
            model,
            fmt=fmt,
            season=LIVE_SEASON,
            at=now,
            log_path=SIM_LOGS[comp.name],
            report_path=SIM_LATEST[comp.name],
        )
        typer.echo(f"{n} rows appended to {SIM_LOGS[comp.name]}")
    typer.echo(f"RUNTIME simulate {comp.name}: {time.perf_counter() - started:.0f} s")


def score(competition: CompetitionOption = CompetitionName.euroleague) -> None:
    """Score the prediction log against results and write the competition's scorecard."""
    comp = COMPETITIONS[competition]
    live = _live(comp)
    card = build_scorecard(
        comp.prediction_log,
        live.games,
        live.model,
        utc_now(),
        manual_pushes=comp.manual_pushes,
        odds_path=comp.odds_log,
        m1_log_path=comp.m1_prediction_log,
        m5_log_path=comp.m5_prediction_log,
        elor_log_path=comp.elor_prediction_log,
        m5inj_log_path=comp.m5inj_prediction_log if M5INJ_LIVE_ENABLED else None,
        eloh_log_path=comp.eloh_prediction_log if ELOH_LIVE_ENABLED else None,
    )
    write_json(comp.scorecard, card)
    typer.echo(json.dumps(card, indent=2))
