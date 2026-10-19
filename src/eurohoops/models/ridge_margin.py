"""Walk-forward ridge margin model: team strengths fitted to game margins, decayed in time.

Each game's expected home margin is ``rating[home] - rating[away] + hca`` (``hca`` only at a
non-neutral venue), with the ratings and ``hca`` fitted by ridge regression on the margins of the
rated games. Games are weighted by ``0.5 ** (age / half_life)``, so recent results count more.

The model is refitted once per calendar day (UTC) of the games to forecast, on the rated games
that tipped off on an earlier day. A forecast therefore never sees its own day's results or
anything later. Nothing here is tuned on the games it forecasts; ``RidgeParams`` is chosen on the
warm-up seasons (docs/models/candidate_elo_blend.md).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from eurohoops.models.elo import FloatArray

NS_PER_DAY = 86_400_000_000_000


@dataclass(frozen=True)
class RidgeParams:
    half_life_days: float  # age at which a game's weight halves
    lam: float  # ridge penalty on each team rating
    hca_penalty_scale: float = 0.1  # the home-court column is penalised at lam * this


def design_matrix(
    home: np.ndarray, away: np.ndarray, neutral: np.ndarray, team_index: dict[str, int]
) -> FloatArray:
    """One row per game: +1 home team, -1 away team, and 1 for home court if not neutral."""
    n_teams = len(team_index)
    x = np.zeros((len(home), n_teams + 1), dtype=np.float64)
    rows = np.arange(len(home))
    x[rows, [team_index[t] for t in home]] = 1.0
    x[rows, [team_index[t] for t in away]] = -1.0
    x[:, n_teams] = 1.0 - neutral.astype(np.float64)
    return x


def ridge_margin_forecast(
    games: pd.DataFrame, params: RidgeParams, target: FloatArray | np.ndarray
) -> FloatArray:
    """Expected home margin for each row of ``games`` where ``target`` is True (NaN elsewhere).

    ``games`` must be sorted by ``tipoff_utc`` and carry ``home``, ``away``, ``neutral``, ``rated``
    (played and not a forfeit) and ``margin`` (home minus away; any value where not rated).
    """
    if not games["tipoff_utc"].is_monotonic_increasing:
        raise ValueError("games must be sorted by tipoff_utc")
    tipoff = (
        games["tipoff_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
    )
    day = tipoff.astype("datetime64[D]").astype("datetime64[ns]").astype(np.int64)
    tip_ns = tipoff.astype(np.int64)
    teams = sorted(set(games["home"]) | set(games["away"]))
    team_index = {t: i for i, t in enumerate(teams)}
    x = design_matrix(
        games["home"].to_numpy(), games["away"].to_numpy(), games["neutral"].to_numpy(), team_index
    )
    rated = games["rated"].to_numpy(dtype=bool)
    margin = games["margin"].to_numpy(dtype=np.float64)
    target = np.asarray(target, dtype=bool)
    penalty = np.full(x.shape[1], params.lam)
    penalty[-1] = params.lam * params.hca_penalty_scale
    out = np.full(len(games), np.nan)
    for dte in np.unique(day[target]):
        hist = np.flatnonzero(rated & (tip_ns < dte))
        age_days = (dte - tip_ns[hist]) / NS_PER_DAY
        w = 0.5 ** (age_days / params.half_life_days)
        xh = x[hist]
        gram = xh.T @ (xh * w[:, None]) + np.diag(penalty)
        beta = np.linalg.solve(gram, xh.T @ (w * margin[hist]))
        now = np.flatnonzero(target & (day == dte))
        out[now] = x[now] @ beta
    return out
