"""Build docs/readme-demo/data.js from the local marts and reports (manual run).

The README demo scenes read only data.js, so a render needs no marts. Every number comes from
the repo's own code (Elo replay, M1 test residuals, the M7 season simulation) on the local
snapshot. Run `uv run eurohoops ingest && uv run eurohoops build` first for fresh data.

    uv run python docs/readme-demo/make_data.py
"""

from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

import eurohoops.sim.season as season_mod
from eurohoops.config import EUROLEAGUE, LIVE_SEASON, M7, MART_PATH
from eurohoops.eval.backtest import _log_loss
from eurohoops.live_sim import run_live_sim
from eurohoops.marts import read_games
from eurohoops.model_inputs import sim_inputs
from eurohoops.models.elo import EloParams, prepare, replay
from eurohoops.publish import DISPLAY_CODES, SHORT_NAMES
from eurohoops.sim.formats import season_format

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name("data.js")
N_DRAWN = 500  # simulated paths drawn in the fan chart; the bands use every simulation


def surface(games: pd.DataFrame) -> dict:
    """Elo tuning log loss on a fine K x home-court grid (reversion at the chosen 0.25)."""
    spec = EUROLEAGUE.live_backtest
    rated = games[
        (games.played & ~games.forfeit) & games.season.between(spec.warmup[0], spec.test[-1])
    ]
    arrays = prepare(rated)
    margin = (rated.home_score - rated.away_score).to_numpy(dtype=np.float64)
    won = (margin > 0).astype(np.float64)
    tuning = np.isin(rated.season.to_numpy(), spec.tuning)

    def loss(k: float, hca: float) -> float:
        return float(_log_loss(replay(arrays, EloParams(k, hca, 0.25))[tuning], won[tuning]))

    check = loss(20, 90)
    assert abs(check - 0.618331) < 1e-5, check  # the committed backtest's best cell
    ks = [float(k) for k in range(6, 62, 2)]
    hcas = [float(h) for h in range(20, 172, 6)]
    z = [[round(loss(k, h), 6) for h in hcas] for k in ks]
    grid_cells = [[k, h] for k, h in product(spec.grid.k, spec.grid.hca)]
    return {"k": ks, "hca": hcas, "z": z, "best": [20, 90, check], "grid_cells": grid_cells}


def fit() -> dict:
    """Real test-season margin residuals against M1's predicted spread."""
    g = pd.read_csv(ROOT / "reports" / "backtest_m5_games.csv")
    t = g[(g.model == "m1") & (g.split == "test")]
    resid = (t.actual_margin - t.exp_margin).round(1).tolist()
    row = t.iloc[0]
    return {"resid": resid, "scale": float(row.margin_sigma), "df": float(row.margin_df)}


def sim(games: pd.DataFrame) -> dict:
    """Replay the live M7 run, keeping the per-game draws the simulator normally discards."""
    captured: dict = {}
    original = season_mod._play_regular_season

    def spy(**kw):
        hp, ap = original(**kw)
        captured.update(hp=hp, ap=ap, home=kw["home_idx"], away=kw["away_idx"])
        return hp, ap

    season_mod._play_regular_season = spy
    try:
        inputs = sim_inputs(EUROLEAGUE, LIVE_SEASON)
        run = run_live_sim(
            inputs.games,
            inputs.team_games,
            inputs.tuned_m1,
            inputs.model,
            fmt=season_format(EUROLEAGUE.name, LIVE_SEASON),
            season=LIVE_SEASON,
            spec=M7,
        )
    finally:
        season_mod._play_regular_season = original
    assert run is not None
    reg = games[(games.season == LIVE_SEASON) & (games.phase == "RS")]
    teams = sorted({*reg.home, *reg.away})
    played = reg[reg.played & ~reg.forfeit].sort_values("tipoff_utc")
    win = np.where(played.home_score > played.away_score, played.home, played.away)
    real = pd.Series(win).value_counts()

    # The simulator's fixtures are the unplayed rows, in the order of the sorted schedule.
    rounds = (
        reg.sort_values("tipoff_utc", kind="stable").set_index(["home", "away"])["round"].to_dict()
    )
    h_idx, a_idx = captured["home"], captured["away"]
    fixture_round = np.array(
        [rounds[(teams[h], teams[a])] for h, a in zip(h_idx, a_idx, strict=True)]
    )
    home_win = captured["hp"] > captured["ap"]
    n_sims = home_win.shape[0]
    rng = np.random.default_rng(7)
    pick = rng.choice(n_sims, size=N_DRAWN, replace=False)
    round_ids = np.arange(1, int(reg["round"].max()) + 1)

    def cumulative(team: str) -> dict:
        """Cumulative wins by round over all sims (bands) and a sample (paths)."""
        i = teams.index(team)
        # wins per sim per remaining fixture of this team
        mine = (h_idx == i) | (a_idx == i)
        won = np.where(h_idx[mine] == i, home_win[:, mine], ~home_win[:, mine])
        rnd = fixture_round[mine]
        per_round = np.zeros((n_sims, len(round_ids)), dtype=np.int16)
        for col, r in enumerate(rnd):
            per_round[:, r - 1] += won[:, col]
        played_team = played[(played.home == team) | (played.away == team)]
        for _, row in played_team.iterrows():
            w = (row.home == team) == (row.home_score > row.away_score)
            per_round[:, int(row["round"]) - 1] += int(w)
        cum = per_round.cumsum(axis=1)
        done = int(played_team["round"].max())
        return {
            "team": team,
            "done": done,
            "real": cum[0, :done].tolist(),  # identical in every sim: the played rounds
            "p10": np.percentile(cum, 10, axis=0).tolist(),
            "p50": np.percentile(cum, 50, axis=0).tolist(),
            "p90": np.percentile(cum, 90, axis=0).tolist(),
            "paths": cum[pick[:40]].tolist(),
            "density": [
                np.bincount(cum[:, r], minlength=len(round_ids) + 1).tolist()
                for r in range(len(round_ids))
            ],
            "final_hist": np.bincount(cum[:, -1], minlength=len(round_ids) + 1).tolist(),
        }

    out = run.out
    return {
        "after_round": run.after_round,
        "n_sims": n_sims,
        "seed": run.seed,
        "teams": teams,
        "display": {t: DISPLAY_CODES["euroleague"].get(t, t) for t in teams},
        "names": {t: SHORT_NAMES["euroleague"].get(t, t) for t in teams},
        "real_wins": {t: int(real.get(t, 0)) for t in teams},
        "cum": {t: cumulative(t) for t in ("OLY", "PAM", "MAD")},
        "exp_wins": {t: round(float(w), 2) for t, w in zip(out.teams, out.wins, strict=True)},
        "p_direct": {t: round(float(p), 4) for t, p in zip(out.teams, out.p_direct, strict=True)},
        "p_title": {t: round(float(p), 4) for t, p in zip(out.teams, out.p_title, strict=True)},
    }


def game(games: pd.DataFrame) -> dict:
    """One live M1 call: 10,000 draws of the final margin from the model's own distribution."""
    gid = "E2026_79"
    row = (
        pd.read_csv(ROOT / "predictions" / "euroleague_m1_2026-27.csv")
        .set_index("game_id")
        .loc[gid]
    )
    res = games.set_index("game_id").loc[gid]
    pred = pd.read_csv(ROOT / "predictions" / "euroleague_m1_2026-27.csv")
    played = games[(games.season == LIVE_SEASON) & (games.phase == "RS") & games.played]
    scored = pred.merge(played[["game_id", "home_score", "away_score"]], on="game_id")
    hits = int(((scored.p_home > 0.5) == (scored.home_score > scored.away_score)).sum())
    rng = np.random.default_rng(11)
    # Margin from the away side's view (OLY): the model's expected margin plus Student-t noise.
    mu = -float(row.exp_margin)
    draws = np.rint(mu + row.margin_sigma * rng.standard_t(row.margin_df, 10_000)).astype(int)
    draws = np.where(draws == 0, rng.choice([-1, 1], 10_000), draws)
    clip = np.clip(draws, -40, 40)
    return {
        "id": gid,
        "live": {"n": len(scored), "hits": hits},
        "home": DISPLAY_CODES["euroleague"].get(str(res.home), str(res.home)),
        "away": DISPLAY_CODES["euroleague"].get(str(res.away), str(res.away)),
        "home_score": int(res.home_score),
        "away_score": int(res.away_score),
        "p_away": round(float(1 - row.p_home), 4),
        "exp_margin_away": round(mu, 2),
        "sigma": float(row.margin_sigma),
        "df": float(row.margin_df),
        "p_draws_away": round(float((draws > 0).mean()), 4),
        "p10": float(np.percentile(draws, 10)),
        "p50": float(np.percentile(draws, 50)),
        "p90": float(np.percentile(draws, 90)),
        "hist": np.bincount(clip + 40, minlength=81).tolist(),
        "ends": draws[:600].tolist(),
    }


def players() -> dict:
    """M3 ratings (points per 100 possessions) at the end of the latest rated season."""
    rep = json.loads((ROOT / "reports" / "m3_players.json").read_text(encoding="utf-8"))
    season = max(rep["seasons"], key=int)
    block = rep["seasons"][season]
    con = duckdb.connect(str(MART_PATH), read_only=True)
    names = con.execute(
        "select source_id, any_value(first_raw), any_value(surname_raw) from player_names "
        "where competition = 'euroleague' and season = ? group by source_id",
        [int(season)],
    ).fetchall()
    label = {sid: f"{(f or '')[:1]}. {(sn or '').title()}".strip(". ") for sid, f, sn in names}
    rows = []
    for p in block["players"]:
        team = p["teams"][-1] if p["teams"] else ""
        rows.append(
            {
                "id": p["player_id"],
                "name": label.get(p["player_id"], ""),
                "team": DISPLAY_CODES["euroleague"].get(team, team),
                "o": round(p["o"], 2),
                "d": round(p["d"], 2),
                "net": round(p["total"], 2),
                "lo": round(p["ci90_total"][0], 2),
                "hi": round(p["ci90_total"][1], 2),
                "min": int(p["minutes"]),
            }
        )
    return {"season": int(season), "median_sd": block["median_sd_total"], "rows": rows}


def main() -> None:
    games = read_games(MART_PATH, EUROLEAGUE.name)
    data = {
        "surface": surface(games),
        "fit": fit(),
        "game": game(games),
        "players": players(),
        "sim": sim(games),
    }
    OUT.write_text(
        "window.DATA = " + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8"
    )
    sys.stdout.write(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} kB)\n")


if __name__ == "__main__":
    main()
