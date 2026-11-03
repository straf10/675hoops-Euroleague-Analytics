import inspect
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from eurohoops.cli.live import predict as live_predict
from tests.conftest import REPO

DAILY = (REPO / ".github/workflows/daily.yml").read_text(encoding="utf-8")
# On Windows, bash on PATH is often the WSL launcher, which cannot run the step; prefer Git Bash.
GIT_BASH = Path("C:/Program Files/Git/bin/bash.exe")
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash") or "bash"


def test_daily_workflow_runs_every_step() -> None:
    for command in ("ingest", "predict", "score"):
        assert re.search(rf"eurohoops {command}\s*$", DAILY, re.MULTILINE), command


def test_daily_caches_box_scores_before_build() -> None:
    """E7: the team model's box scores are cached (only new games fetched) before the build."""
    build = DAILY.index("eurohoops build")
    el_cache = DAILY.index("path: data/raw/euroleague")
    el_details = DAILY.index("eurohoops ingest --details")
    assert el_cache < el_details < build
    assert DAILY.index("eurohoops predict") > build


def test_daily_stages_el_history_and_stints_for_m5_softly() -> None:
    """M5 needs 2007-on games before the build and the stints mart after it, before predict; a
    failure of either step is a warning so Elo, M1, odds and injuries still run and commit."""
    stage = DAILY.index("eurohoops ingest --from-season 2007")
    build = DAILY.index("eurohoops build")
    stints = DAILY.index("eurohoops stints --mart")
    assert DAILY.index("eurohoops ingest --details") < stage < build < stints
    assert stints < DAILY.index("- name: Predict upcoming games")
    assert DAILY.count("will be skipped") == 2
    for command in ("ingest --from-season 2007", "stints --mart"):
        start = DAILY.index(command)
        assert '|| echo "::warning::' in DAILY[start : DAILY.index("- name:", start)]


def test_daily_keeps_the_committed_stints_report() -> None:
    """The daily stints mart rewrites reports/stints_mart.json with live-season games; the M1
    card quotes that report, so the step restores it before anything is committed."""
    start = DAILY.index("eurohoops stints --mart")
    step = DAILY[start : DAILY.index("- name:", start)]
    assert "git checkout -- reports/stints_mart.json" in step
    assert start < DAILY.index("git add predictions/ reports/")


def test_daily_runs_are_closer_together_than_the_round_lead() -> None:
    """Rounds are logged once their first tip-off is within the round lead (48 h). With one run
    a day, a round is logged on the first run inside that lead: 24 to 48 h before it tips off."""
    (cron,) = re.findall(r'cron: "([^"]+)"', DAILY)
    assert cron.split()[2:] == ["*", "*", "*"]
    assert cron.split()[:2] == ["47", "7"]
    assert "--round-lead-hours" not in DAILY  # predict keeps its 48 h default
    assert "--window-hours" not in DAILY
    assert inspect.signature(live_predict).parameters["round_lead_hours"].default == 48.0


def test_daily_builds_the_site_from_fresh_data() -> None:
    publish = DAILY.index("eurohoops publish")
    build = DAILY.index("npm run build")
    upload = DAILY.index("actions/upload-artifact@", build)
    assert publish < build < upload
    assert "working-directory: web" in DAILY


def test_daily_hands_the_downloads_and_validation_to_the_site_build() -> None:
    export = DAILY.index("eurohoops export-stats --from-cache")
    artifact = DAILY.index("name: site-data")
    paths = DAILY[artifact : DAILY.index("if-no-files-found", artifact)]
    assert export < artifact
    # validation.json is written into web/src/data/stats/; the CSVs and manifest into downloads/
    assert "web/src/data/stats/" in paths and "web/public/downloads/" in paths


def test_a_failed_export_still_commits_the_logs() -> None:
    commit = DAILY.index("name: Commit predictions and reports if changed")
    assert "id: export" in DAILY[: DAILY.index("name: site-data")]
    assert "if: success() || steps.export.outcome == 'failure'" in DAILY[commit : commit + 200]


def test_daily_deploys_the_built_site_to_a_cloudflare_worker() -> None:
    deploy = DAILY[DAILY.index("  deploy-page:") :]
    assert "needs: build-site" in deploy
    assert "actions/checkout" not in deploy  # the deploy job holds the token, runs no repo code
    assert "CLOUDFLARE_API_TOKEN" in deploy and "CLOUDFLARE_ACCOUNT_ID" in deploy
    assert "command: deploy" in deploy
    # unknown URLs get 404.html, not an empty 404
    assert '"not_found_handling": "404-page"' in deploy
    assert "wranglerVersion:" in deploy  # pinned
    assert "upload-pages-artifact" not in DAILY and "deploy-pages" not in DAILY


def odds_step() -> str:
    start = DAILY.index("- name: Record EuroLeague odds")
    return DAILY[start : DAILY.index("- name:", start + 1)]


def test_daily_records_odds_after_build_and_before_scoring() -> None:
    assert DAILY.index("eurohoops build") < DAILY.index("eurohoops odds")
    assert DAILY.index("eurohoops odds") < DAILY.index("eurohoops score")
    assert "git add predictions/ reports/ odds/" in DAILY
    assert "git add predictions/ reports/ odds/ injuries/" not in DAILY


def test_daily_records_injuries_between_odds_and_prediction() -> None:
    assert DAILY.index("- name: Record EuroLeague odds") < DAILY.index(
        "- name: Record EuroLeague injuries"
    )
    assert DAILY.index("uv run --no-dev eurohoops injuries --probe") < DAILY.index(
        "- name: Predict upcoming games"
    )


def test_injury_refresh_runs_make_no_odds_call() -> None:
    """A PC-triggered run (injury_refresh) skips the odds call and the once-a-day people refresh."""
    assert "injury_refresh:" in DAILY and "type: boolean" in DAILY
    assert DAILY.count("if: ${{ !inputs.injury_refresh }}") == 2
    assert "eurohoops odds" in odds_step()
    people = DAILY[DAILY.index("- name: Refresh the live") :]
    assert "if: ${{ !inputs.injury_refresh }}" in people[: people.index("run:")]


def test_odds_step_is_skipped_with_a_warning_without_the_secret() -> None:
    step = odds_step()
    assert "ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}" in step
    body = step.split("run: |\n", 1)[1]
    script = "\n".join(line.removeprefix("          ") for line in body.splitlines())
    fake_uv = 'uv() { echo "uv $*"; }\n'  # stands in for the real command

    def run_step(secret: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "ODDS_API_KEY": secret}
        return subprocess.run(
            [BASH, "-c", fake_uv + script], env=env, capture_output=True, text=True, check=False
        )

    skipped = run_step("")
    assert skipped.returncode == 0
    assert "::warning::ODDS_API_KEY secret is not set" in skipped.stdout
    assert "uv run" not in skipped.stdout
    ran = run_step("x")
    assert ran.returncode == 0
    assert "uv run --no-dev eurohoops odds" in ran.stdout


CI = (REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def test_ci_builds_the_site_from_the_committed_fixture() -> None:
    web = CI[CI.index("\n  web:") :]
    assert "node-version: 24" in web
    assert "cp tests/fixtures/site.json web/src/data/site.json" in web
    assert web.index("site.json web/src/data") < web.index("npm ci") < web.index("npm run build")
    assert "working-directory: web" in web
    assert (REPO / "tests/fixtures/site.json").exists()


def daily_jobs() -> dict[str, Any]:
    jobs: dict[str, Any] = yaml.safe_load(DAILY)["jobs"]
    return jobs


def test_npm_never_runs_while_the_job_can_write_to_the_repository() -> None:
    """Third-party npm packages run in ``npm ci``: that job gets no write token."""
    top = yaml.safe_load(DAILY).get("permissions", {})
    assert top in ({}, None) or top.get("contents") != "write"
    npm_jobs = [
        name
        for name, job in daily_jobs().items()
        if any("npm ci" in str(step.get("run", "")) for step in job["steps"])
    ]
    assert npm_jobs
    for name in npm_jobs:
        assert daily_jobs()[name].get("permissions", {}).get("contents") != "write", name


def test_the_write_job_keeps_its_token_out_of_the_checkout() -> None:
    for name, job in daily_jobs().items():
        if job.get("permissions", {}).get("contents") != "write":
            continue
        checkout = next(
            s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout")
        )
        assert checkout.get("with", {}).get("persist-credentials") is False, name


def commit_step() -> dict[str, Any]:
    steps = [s for job in daily_jobs().values() for s in job["steps"]]
    return next(s for s in steps if s.get("name") == "Commit predictions and reports if changed")


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout


def sandbox(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """A bare 'GitHub' remote, the runner's clone, and an env that routes the step's
    https://x-access-token URL to the bare remote."""
    bare, runner, other = tmp_path / "remote.git", tmp_path / "runner", tmp_path / "other"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    git(tmp_path, "clone", "-q", str(bare), str(other))
    for key, value in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false")):
        git(other, "config", key, value)
    (other / "predictions").mkdir()
    (other / "predictions/log.csv").write_text("game_id,p\nG1,0.5\n", newline="\n")
    for folder in ("reports", "odds"):  # the step adds predictions plus these folders
        (other / folder).mkdir()
        (other / folder / "keep.txt").write_text("x\n", newline="\n")
    git(other, "add", ".")
    git(other, "commit", "-qm", "base")
    git(other, "push", "-q", "origin", "main")
    git(tmp_path, "clone", "-q", str(bare), str(runner))
    url = "https://x-access-token:tok@github.com/o/r.git"
    env = {
        **os.environ,
        "GH_TOKEN": "tok",
        "REPO": "o/r",
        "BRANCH": "main",
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": f"url.{bare.as_posix()}.insteadOf",
        "GIT_CONFIG_VALUE_0": url,
        "GIT_CONFIG_KEY_1": "commit.gpgsign",
        "GIT_CONFIG_VALUE_1": "false",
    }
    return other, runner, env


def run_commit_step(runner: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    step = commit_step()
    assert set(step["env"]) >= {"GH_TOKEN", "REPO", "BRANCH"}
    return subprocess.run(
        [BASH, "-e", "-c", step["run"]],
        cwd=runner,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_push_replays_the_run_on_a_main_that_moved(tmp_path: Path) -> None:
    other, runner, env = sandbox(tmp_path)
    (other / "README").write_text("moved\n")
    git(other, "add", ".")
    git(other, "commit", "-qm", "owner commit during the run")
    git(other, "push", "-q", "origin", "main")
    with (runner / "predictions/log.csv").open("a", newline="\n") as fh:
        fh.write("G2,0.6\n")
    done = run_commit_step(runner, env)
    assert done.returncode == 0, done.stderr
    git(other, "pull", "-q", "origin", "main")
    assert (other / "predictions/log.csv").read_text() == "game_id,p\nG1,0.5\nG2,0.6\n"
    assert (other / "README").exists()


def move_remote_before_each_push(runner: Path, other: Path, times: int) -> None:
    """A pre-push hook in the runner: the first `times` pushes find main moved by another commit."""
    counter = runner / ".git/moves"
    hook = runner / ".git/hooks/pre-push"
    hook.write_text(
        "#!/bin/sh\n"
        f'n=$(cat "{counter.as_posix()}" 2>/dev/null || echo 0)\n'
        f'if [ "$n" -lt {times} ]; then\n'
        f'  echo $((n+1)) > "{counter.as_posix()}"\n'
        f'  cd "{other.as_posix()}" && echo "owner $n" >> README && git add README'
        ' && git -c user.name=t -c user.email=t@t commit -qm "owner $n"'
        " && git push -q origin main || exit 1\n"
        "fi\nexit 0\n",
        newline="\n",
    )
    hook.chmod(0o755)


def test_a_main_that_moves_once_during_the_push_is_replayed_once_more(tmp_path: Path) -> None:
    other, runner, env = sandbox(tmp_path)
    move_remote_before_each_push(runner, other, times=1)
    with (runner / "predictions/log.csv").open("a", newline="\n") as fh:
        fh.write("G2,0.6\n")
    done = run_commit_step(runner, env)
    assert done.returncode == 0, done.stdout + done.stderr
    git(other, "pull", "-q", "origin", "main")
    assert (other / "predictions/log.csv").read_text() == "game_id,p\nG1,0.5\nG2,0.6\n"
    assert "owner 0" in (other / "README").read_text()


def test_a_main_that_moves_twice_fails_the_job_without_a_loop_or_a_force(tmp_path: Path) -> None:
    other, runner, env = sandbox(tmp_path)
    move_remote_before_each_push(runner, other, times=2)
    with (runner / "predictions/log.csv").open("a", newline="\n") as fh:
        fh.write("G2,0.6\n")
    done = run_commit_step(runner, env)
    assert done.returncode != 0
    assert (runner / ".git/moves").read_text().strip() == "2"  # exactly two pushes attempted
    git(other, "pull", "-q", "origin", "main")
    assert "G2" not in (other / "predictions/log.csv").read_text()  # nothing of ours was pushed
    assert "owner 1" in (other / "README").read_text()  # the remote's commits were not overwritten


def test_a_conflict_on_an_append_only_log_fails_without_rewriting_rows(tmp_path: Path) -> None:
    other, runner, env = sandbox(tmp_path)
    with (other / "predictions/log.csv").open("a", newline="\n") as fh:
        fh.write("G9,0.1\n")  # a row pushed while the run was going
    git(other, "commit", "-qam", "hand-logged row")
    git(other, "push", "-q", "origin", "main")
    with (runner / "predictions/log.csv").open("a", newline="\n") as fh:
        fh.write("G2,0.6\n")
    done = run_commit_step(runner, env)
    assert done.returncode != 0
    assert "::error::" in done.stdout
    git(other, "pull", "-q", "origin", "main")
    assert (other / "predictions/log.csv").read_text() == "game_id,p\nG1,0.5\nG9,0.1\n"
    assert not (runner / ".git/rebase-merge").exists()  # the rebase was aborted, not resolved


def test_an_unreachable_remote_fails_with_the_error_annotation(tmp_path: Path) -> None:
    """A pull that fails before any rebase starts (network, auth) still reports ::error::."""
    _, runner, env = sandbox(tmp_path)
    with (runner / "predictions/log.csv").open("a", newline="\n") as fh:
        fh.write("G2,0.6\n")
    env["GIT_CONFIG_KEY_0"] = f"url.{(tmp_path / 'missing.git').as_posix()}.insteadOf"
    done = run_commit_step(runner, env)
    assert done.returncode != 0
    assert "::error::" in done.stdout


def test_deploy_site_takes_only_a_daily_run_of_this_repo_on_main() -> None:
    """Artifact poisoning: the site data must come from this repository's daily-predictions run on
    main. A fork's run on a branch named main, or any other workflow, must be refused."""
    deploy = (REPO / ".github/workflows/deploy-site.yml").read_text(encoding="utf-8")
    find = deploy[deploy.index("- name: Find the latest site data") :]
    find = find[: find.index("- uses: actions/download-artifact")]
    assert ".workflow_run.head_repository_id == $REPO_ID" in find
    assert "REPO_ID: ${{ github.repository_id }}" in find
    assert "actions/runs/$run_id" in find
    assert ".github/workflows/daily.yml schedule" in find
    assert ".github/workflows/daily.yml workflow_dispatch" in find


def setup_uv_pins() -> list[tuple[str, object]]:
    """(workflow file, version input) of every astral-sh/setup-uv step in the repository."""
    pins = []
    for path in sorted((REPO / ".github/workflows").glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in (data.get("jobs") or {}).values():
            for step in job.get("steps") or []:
                if str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
                    pins.append((path.name, (step.get("with") or {}).get("version")))
    return pins


def test_every_setup_uv_step_pins_the_uv_the_dockerfile_installs() -> None:
    # Pinned so that CI, the daily job and the API image run one uv (F-02); the Dockerfile's
    # version is the reference, so the two cannot drift apart.
    pins = setup_uv_pins()
    assert len(pins) == 4, pins
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    pinned = re.search(r'pip install --no-cache-dir "uv==([0-9.]+)"', dockerfile)
    assert pinned is not None, "the Dockerfile must pin uv"
    assert {version for _, version in pins} == {pinned.group(1)}, pins
