"""ELOR: live Elo with a fading roster prior (docs/models/elo_roster_prior.md, protocol v1).

For team t in season s at round r (r = 1 is the season's first round cutoff)::

    w(r)   = w0 * max(0, 1 - (r - 1) / N)
    B_t(r) = R_t(r) + w(r) * (P_t - R_t(start))
    d_g    = B_home - B_away + (0 if neutral else hca)

``R_t(r)`` and ``R_t(start)`` are live Elo's own pre-game and season-start ratings (``elo.replay``,
``elo.season_ratings``), so ``d_g = elo_diff_g + w(r) * (off_home - off_away)`` with
``off_t = P_t - R_t(start)``. ``w0 = 0`` is live Elo exactly.

**Roster rating ``P_t`` at a game's cutoff** (``minutes.round_cutoffs``). The roster is the
club's roster-list rows in force at the cutoff (``models/roster.py``). Each rostered player gets a
projected on-court share from box scores before the cutoff, by H-c's rule (``proj_hc``, the
protocol's minute-share default) applied to the club he last played for:

* his last appearance (seconds > 0) before the cutoff, in season s or s - 1, sets the club X;
* in season s the window is X's last ``n_games`` rated games up to that appearance; in season
  s - 1 it is all of X's rated games that season (H-c's previous-season fallback);
* share = min(1, 5 x his seconds / X's recorded seconds) over the window.

For a player who played his club's last game this is exactly ``minutes.projected_shares``.
``r_p = O + D`` comes from M3's walk-forward fit at the cutoff (``rapm_spm``, as M5), available
only once the player has played before the cutoff (``WalkForwardRatings``).

**Newcomers (owner decision 6).** A rostered player with no share gets the season's prior share,
one with no available rating the prior rating, separately (``newcomer_priors``: what EuroLeague
first-season newcomers posted in earlier seasons). As soon as the rules above give him a share
or a rating, his own value replaces the prior. If the shares then add up to more than 5 they
are scaled down to 5. The team's per-100 rating is ``Q_t = sum share_p * r_p``; in margin
points ``Q_t * poss_g / 100`` (the
game's expected possessions, as M5), in Elo points times the margin scale ``s``
(``elo.fit_margin_scale`` on live-Elo differences and margins of earlier seasons only).

**Centring.** At each cutoff, ``Q`` and ``R(start)`` are centred on their means over the
season's clubs with at least one rostered player, so ``off_t = s * poss/100 * (Q_t - mean Q)
- (R_t(start) - mean R(start))``: the blend moves teams relative to each other, never the league
level. (Both sides of a game share the cutoff and the centre, so the centre cancels in ``d_g``.)

A game whose prior is not available (no M3 state at the cutoff, no possessions, no earlier
season for the scale, or a side with no rostered player) keeps ``off = 0``: it is live Elo.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd

from eurohoops.models import elo
from eurohoops.models.elo import FloatArray
from eurohoops.models.minutes import ON_COURT, _team_games, round_cutoffs
from eurohoops.models.rapm import RatingLookup
from eurohoops.models.roster import on_roster

PROJ_N_GAMES = 5  # H-c's window, ``minutes.projected_shares``' default

# (season, cutoff, player_id, club) -> rating O + D, or None for a player with no rating
RatingFn = Callable[[int, float, str, str], float | None]
# (season, player_id) -> rating O + D in the fit at that season's end, or None
SeasonEndRating = Callable[[int, str], float | None]


@dataclass(frozen=True)
class ElorSetting:
    w0: float
    n_rounds: int

    def key(self) -> str:
        return f"w{self.w0:g}|n{self.n_rounds}"


def fade_weight(r: int | np.ndarray, w0: float, n_rounds: int) -> np.ndarray:
    """``w0 * max(0, 1 - (r - 1) / N)`` for round index ``r`` (1 = first round)."""
    rounds = np.asarray(r, dtype=np.float64)
    out: np.ndarray = w0 * np.maximum(0.0, 1.0 - (rounds - 1.0) / n_rounds)
    return out


def round_index(games: pd.DataFrame) -> np.ndarray:
    """Each game's round index in its season: 1 + the number of distinct earlier round cutoffs
    of that season (postponed games keep their round's cutoff and index)."""
    cutoff = round_cutoffs(games).to_numpy(dtype=np.float64)
    season = games["season"].astype(int).to_numpy()
    out = np.zeros(len(games), dtype=np.int64)
    for s in np.unique(season):
        mask = season == s
        distinct = np.unique(cutoff[mask])
        out[mask] = np.searchsorted(distinct, cutoff[mask], side="left") + 1
    return out


class WalkForwardRatings:
    """``RatingFn`` from a walk-forward fit aligned with ``frame`` (state just before each
    round), and ``has_state`` false before the fit has any stint.

    A player's rating is available at a cutoff only if the lookup holds him **and** he has
    played (seconds > 0 in a rated game of ``frame``) before that cutoff. The lookup alone is not
    enough: its columns span the whole frame, so a player who first plays later has a column
    (filled with the SPM prior) whose existence would leak that future. ``at_season_end`` is
    the fit at the season's last round cutoff (state before its final round), with the same
    condition at that cutoff."""

    def __init__(
        self,
        frame: pd.DataFrame,
        lookups: list[RatingLookup | None],
        player_games: pd.DataFrame,
    ) -> None:
        cutoffs = round_cutoffs(frame).to_numpy(dtype=np.float64)
        seasons = frame["season"].astype(int).to_numpy()
        self._by: dict[tuple[int, float], RatingLookup] = {}
        self._last: dict[int, float] = {}
        for s, c, lookup in zip(seasons, cutoffs, lookups, strict=True):
            self._last[int(s)] = max(self._last.get(int(s), -math.inf), float(c))
            if lookup is not None:
                self._by[(int(s), float(c))] = lookup
        rated = frame[frame["played"] & ~frame["forfeit"]][["game_id", "tipoff_utc"]]
        rows = player_games[player_games["sec"] > 0][["game_id", "player_id"]]
        rows = rows.merge(rated, on="game_id")
        first = rows.groupby("player_id")["tipoff_utc"].min()
        self._first: dict[str, float] = {str(p): float(t.timestamp()) for p, t in first.items()}

    def has_state(self, season: int, cutoff: float) -> bool:
        return (season, cutoff) in self._by

    def __call__(self, season: int, cutoff: float, player_id: str, club: str) -> float | None:
        lookup = self._by.get((season, cutoff))
        if lookup is None or player_id not in lookup.o:
            return None
        if not self._first.get(player_id, math.inf) < cutoff:
            return None
        o, d = lookup.rating(player_id, club, season)
        return float(o + d)

    def at_season_end(self, season: int, player_id: str) -> float | None:
        cutoff = self._last.get(season)
        if cutoff is None:
            return None
        return self(season, cutoff, player_id, "")


class Appearances:
    """Box-score history for projected shares: team-games and per-player appearances."""

    def __init__(self, games: pd.DataFrame, player_games: pd.DataFrame) -> None:
        team_games = _team_games(games, player_games)
        self.team: dict[tuple[str, int], tuple[np.ndarray, list[str], np.ndarray]] = {}
        for (team, season), part in team_games.groupby(["team", "season"]):
            self.team[(str(team), cast(int, season))] = (
                part["time"].to_numpy(dtype=np.float64),
                part["game_id"].astype(str).tolist(),
                part["team_sec"].to_numpy(dtype=np.float64),
            )
        known = team_games[["game_id", "team", "season", "time"]]
        rows = player_games[player_games["sec"] > 0][["game_id", "team", "player_id", "sec"]]
        rows = rows.merge(known, on=["game_id", "team"]).sort_values(["time", "game_id"])
        self.sec: dict[tuple[str, str, str], float] = {
            (str(g), str(t), str(p)): float(v)
            for g, t, p, v in zip(
                rows["game_id"], rows["team"], rows["player_id"], rows["sec"], strict=True
            )
        }
        self.player: dict[str, tuple[np.ndarray, list[str], np.ndarray]] = {}
        self.player_sec: dict[str, np.ndarray] = {}
        for player, part in rows.groupby("player_id"):
            self.player[str(player)] = (
                part["time"].to_numpy(dtype=np.float64),
                part["team"].astype(str).tolist(),
                part["season"].astype(int).to_numpy(),
            )
            self.player_sec[str(player)] = part["sec"].to_numpy(dtype=np.float64)
        # Newcomer history: each player's first season with seconds, the first season with any
        # box data (nobody can be called a newcomer in it) and each season's last round cutoff.
        self.first_season = {p: int(found[2][0]) for p, found in self.player.items()}
        self.data_first_season = int(team_games["season"].min()) if len(team_games) else 0
        cutoffs = round_cutoffs(games)
        self.last_cutoff = {
            int(s): float(c.max()) for s, c in cutoffs.groupby(games["season"].astype(int))
        }

    def share(
        self, player_id: str, season: int, cutoff: float, n_games: int = PROJ_N_GAMES
    ) -> float:
        """The player's projected share at ``cutoff`` (module docstring); 0 without one."""
        found = self.player.get(player_id)
        if found is None:
            return 0.0
        times, teams, seasons = found
        j = int(np.searchsorted(times, cutoff, side="left")) - 1
        while j >= 0 and seasons[j] > season:
            j -= 1
        if j < 0 or seasons[j] < season - 1:
            return 0.0
        club, sigma, last = teams[j], int(seasons[j]), float(times[j])
        t_times, t_ids, t_sec = self.team[(club, sigma)]
        if sigma == season:
            k = int(np.searchsorted(t_times, last, side="right"))
            window = range(max(0, k - n_games), k)
        else:
            window = range(len(t_ids))
        denominator = float(sum(t_sec[i] for i in window))
        if denominator <= 0:
            return 0.0
        seconds = sum(self.sec.get((t_ids[i], club, player_id), 0.0) for i in window)
        return min(1.0, ON_COURT * seconds / denominator)


@dataclass(frozen=True)
class NewcomerPrior:
    """The typical-newcomer prior for one target season (owner decision 6), from seasons
    before it only: ``rating`` (O + D per 100, minutes-weighted) and ``share`` (per game)."""

    season: int
    rating: float
    share: float
    rating_players: int
    rating_seconds: float
    share_player_games: int
    history: tuple[int, ...]  # the earlier seasons that had newcomers


def _newcomer_season(
    appearances: Appearances, sigma: int, season_end_rating: SeasonEndRating
) -> tuple[float, float, int, float, int]:
    """One season's newcomer sums: (sum w*r, sum w, rated players, sum of shares, games)."""
    wr = w_sum = share_sum = 0.0
    rated = games = 0
    last_cutoff = appearances.last_cutoff.get(sigma, math.inf)
    for player, first in appearances.first_season.items():
        if first != sigma:
            continue
        times, teams, seasons = appearances.player[player]
        secs = appearances.player_sec[player]
        in_season = seasons == sigma
        weight = float(secs[in_season & (times < last_cutoff)].sum())
        value = season_end_rating(sigma, player)
        if value is not None and weight > 0:
            wr += weight * value
            w_sum += weight
            rated += 1
        for club in sorted({t for t, s in zip(teams, seasons, strict=True) if s == sigma}):
            mine = in_season & (np.asarray(teams) == club)
            start, end = float(times[mine].min()), float(times[mine].max())
            t_times, t_ids, t_sec = appearances.team[(club, sigma)]
            for i in np.flatnonzero((t_times >= start) & (t_times <= end)):
                if t_sec[i] <= 0:
                    continue
                sec = appearances.sec.get((t_ids[i], club, player), 0.0)
                share_sum += min(1.0, ON_COURT * sec / float(t_sec[i]))
                games += 1
    return wr, w_sum, rated, share_sum, games


def newcomer_priors(
    appearances: Appearances, season_end_rating: SeasonEndRating, targets: list[int]
) -> dict[int, NewcomerPrior]:
    """Each target season's typical-newcomer prior (owner decision 6, Build addendum).

    A first-season newcomer of season sigma is a player whose first seconds in the box data are
    in sigma; the first season with box data has none (no history to tell). Over every sigma
    before the target:

    * rating: the minutes-weighted mean of the newcomers' O + D in the walk-forward fit at
      sigma's last round cutoff (``season_end_rating``), weighted by their seconds in sigma
      before that cutoff (players without a rating there are left out);
    * share: the mean, over newcomer team-games, of min(1, 5 x his seconds / the team's seconds)
      in every game of his club from his first to his last appearance with it in sigma (a game
      he sat out counts 0, as in the projected shares).

    NaN when no earlier season has newcomers (the caller decides)."""
    out: dict[int, NewcomerPrior] = {}
    sums: dict[int, tuple[float, float, int, float, int]] = {}
    first = appearances.data_first_season
    for target in targets:
        wr = w = share = 0.0
        rated = games = 0
        history: list[int] = []
        for sigma in range(first + 1, target):
            if sigma not in sums:
                sums[sigma] = _newcomer_season(appearances, sigma, season_end_rating)
            s_wr, s_w, s_rated, s_share, s_games = sums[sigma]
            if s_games or s_rated:
                history.append(sigma)
            wr += s_wr
            w += s_w
            rated += s_rated
            share += s_share
            games += s_games
        out[target] = NewcomerPrior(
            season=target,
            rating=wr / w if w > 0 else math.nan,
            share=share / games if games else math.nan,
            rating_players=rated,
            rating_seconds=w,
            share_player_games=games,
            history=tuple(history),
        )
    return out


@dataclass(frozen=True)
class ClubStrength:
    q: float  # per-100 roster rating
    rostered: int
    share_prior: int  # rostered players on the newcomer share prior
    rating_prior: int  # rostered players on the newcomer rating prior


def club_strength(
    players: list[str],
    club: str,
    season: int,
    cutoff: float,
    *,
    appearances: Appearances,
    rating: RatingFn,
    prior: NewcomerPrior,
) -> ClubStrength:
    """``Q_t`` with the newcomer prior: a player without a projected share gets the prior share,
    one without an available rating the prior rating (separately); then the cap at 5."""
    shares: dict[str, float] = {}
    values: dict[str, float] = {}
    share_prior = rating_prior = 0
    for player in players:
        share = appearances.share(player, season, cutoff)
        if share <= 0:
            share = prior.share
            share_prior += 1
        value = rating(season, cutoff, player, club)
        if value is None:
            value = prior.rating
            rating_prior += 1
        shares[player], values[player] = share, value
    total = sum(shares.values())
    scale = min(1.0, ON_COURT / total) if total > 0 else 0.0
    q = sum(scale * shares[p] * values[p] for p in players)
    return ClubStrength(q, len(players), share_prior, rating_prior)


STRENGTH_COLUMNS = ["season", "cutoff", "club", "q", "rostered", "share_prior", "rating_prior"]


def roster_strengths(
    games: pd.DataFrame,
    roster: pd.DataFrame,
    appearances: Appearances,
    rating: RatingFn,
    *,
    priors: dict[int, NewcomerPrior],
    has_state: Callable[[int, float], bool] | None = None,
) -> pd.DataFrame:
    """Every club's ``ClubStrength`` at every round cutoff of ``games`` (``STRENGTH_COLUMNS``):
    the clubs with at least one roster row in force at that cutoff. Cutoffs without M3 state
    (``has_state`` false) are skipped."""
    cutoffs = round_cutoffs(games).to_numpy(dtype=np.float64)
    seasons = games["season"].astype(int).to_numpy()
    out: list[dict[str, object]] = []
    for season, cutoff in sorted(
        {(int(s), float(c)) for s, c in zip(seasons, cutoffs, strict=True)}
    ):
        if has_state is not None and not has_state(season, cutoff):
            continue
        part = on_roster(roster, cutoff, season)
        if part.empty:
            continue
        prior = priors[season]
        for club, rows in part.groupby("club"):
            players = sorted(set(rows["player_id"].astype(str)))
            st = club_strength(
                players,
                str(club),
                season,
                cutoff,
                appearances=appearances,
                rating=rating,
                prior=prior,
            )
            out.append(
                {
                    "season": season,
                    "cutoff": cutoff,
                    "club": str(club),
                    "q": st.q,
                    "rostered": st.rostered,
                    "share_prior": st.share_prior,
                    "rating_prior": st.rating_prior,
                }
            )
    return pd.DataFrame(out, columns=STRENGTH_COLUMNS)


def margin_scales(games: pd.DataFrame, elo_diff: FloatArray) -> dict[int, float]:
    """Per season s, ``elo.fit_margin_scale`` on rated games of seasons before s (NaN for the
    first season)."""
    rated = (games["played"] & ~games["forfeit"]).to_numpy(dtype=bool)
    season = games["season"].astype(int).to_numpy()
    margin = (games["home_score"] - games["away_score"]).to_numpy(dtype=np.float64)
    out: dict[int, float] = {}
    for s in np.unique(season):
        train = rated & (season < s)
        out[int(s)] = (
            elo.fit_margin_scale(elo_diff[train], margin[train]) if train.any() else math.nan
        )
    return out


def season_starts(
    arrays: elo.GameArrays, params: elo.EloParams, seasons: list[int]
) -> dict[int, dict[str, float]]:
    """Each season's ``R_t(start)`` (live Elo, after reversion; 1500 for a new team)."""
    return {
        s: {team: start for team, (_, start) in elo.season_ratings(arrays, params, s).items()}
        for s in seasons
    }


@dataclass(frozen=True)
class Offsets:
    home: FloatArray  # P - R(start) of the home side, Elo points (0 where not available)
    away: FloatArray
    available: np.ndarray  # bool


def offsets(
    games: pd.DataFrame,
    strengths: pd.DataFrame,
    starts: dict[int, dict[str, float]],
    scales: dict[int, float],
    possessions: pd.Series,
) -> Offsets:
    """``off_t = s * poss/100 * (Q_t - mean Q) - (R_t(start) - mean R(start))`` per side."""
    n = len(games)
    home = np.zeros(n)
    away = np.zeros(n)
    available = np.zeros(n, dtype=bool)
    cutoffs = round_cutoffs(games).to_numpy(dtype=np.float64)
    centred: dict[tuple[int, float], dict[str, tuple[float, float, int]]] = {}
    for (season, cutoff), part in strengths.groupby(["season", "cutoff"]):
        start = starts.get(cast(int, season), {})
        r_start = np.array([start.get(c, elo.INITIAL_RATING) for c in part["club"]])
        q = part["q"].to_numpy(dtype=np.float64)
        centred[(cast(int, season), cast(float, cutoff))] = {
            str(c): (float(dq), float(dr), int(k))
            for c, dq, dr, k in zip(
                part["club"], q - q.mean(), r_start - r_start.mean(), part["rostered"], strict=True
            )
        }
    poss = possessions.reindex(games["game_id"].astype(str)).to_numpy(dtype=np.float64)
    for i, (season, h, a) in enumerate(
        zip(
            games["season"].astype(int),
            games["home"].astype(str),
            games["away"].astype(str),
            strict=True,
        )
    ):
        table = centred.get((int(season), float(cutoffs[i])))
        scale = scales.get(int(season), math.nan)
        if table is None or h not in table or a not in table:
            continue
        if not (math.isfinite(scale) and math.isfinite(poss[i])):
            continue
        factor = scale * poss[i] / 100.0
        dq_h, dr_h, _ = table[h]
        dq_a, dr_a, _ = table[a]
        home[i] = factor * dq_h - dr_h
        away[i] = factor * dq_a - dr_a
        available[i] = True
    return Offsets(home, away, available)


def elor_diff(
    elo_diff: FloatArray, rounds: np.ndarray, offs: Offsets, setting: ElorSetting
) -> FloatArray:
    """``d_g = elo_diff + w(r) * (off_home - off_away)``; ``w0 = 0`` returns ``elo_diff``."""
    weight = fade_weight(rounds, setting.w0, setting.n_rounds)
    out: FloatArray = elo_diff + weight * (offs.home - offs.away)
    return out


def win_probabilities(diff: FloatArray) -> FloatArray:
    """``elo.win_probability`` on every element."""
    return np.array([elo.win_probability(float(d)) for d in diff], dtype=np.float64)
