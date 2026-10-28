"""``eurohoops`` command line: ingest -> build -> backtest -> predict -> score -> publish."""

import logging

import typer

from eurohoops import research
from eurohoops.cli import backtest, build, ingest, live, publish
from eurohoops.cli._shared import ModelName

__all__ = ["ModelName", "app", "main"]

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)


# Commands are registered here, in the order ``--help`` lists them.
app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})(
    ingest.ingest
)
app.command("ingest-bios")(ingest.ingest_bios_command)
app.command()(ingest.people)
app.command()(build.build)
app.command()(build.continuity)
app.command()(build.stints)
app.command()(research.shots)
app.command(name="free-throws")(research.free_throws)
app.command(name="entity")(research.entity)
app.command()(build.possessions)
app.command()(live.project)
app.command("sim-ungated")(live.sim_ungated)
app.command()(backtest.backtest)
app.command(name="shot-quality")(research.shot_quality)
app.command(name="m3-players")(research.m3_players)
app.command(name="shot-charts")(research.shot_charts)
app.command()(live.predict)
app.command(name="backfill-inputs")(live.backfill_inputs)
app.command()(live.odds)
app.command()(live.injuries)
app.command("first-tipoff")(live.first_tipoff)
app.command()(live.simulate)
app.command()(live.score)
app.command("promote-check")(backtest.promote_check)
app.command()(publish.publish)
app.command("export-stats")(publish.export_stats)
