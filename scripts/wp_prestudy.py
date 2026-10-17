"""WP pre-study for docs/models/wp.md (wave 1): five tasks T1-T5.

Seasons 2007-2022 ONLY. The loader refuses any other season, and no 2023+ file is opened.
Writes reports/wp_prestudy.json. Run: uv run python scripts/wp_prestudy.py
"""

from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from scipy.special import ndtr
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from eurohoops.models.elo import EloParams, fit_margin_scale, prepare, replay

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "euroleague"
MART = ROOT / "data" / "marts" / "eurohoops.duckdb"
REPORT = ROOT / "reports" / "wp_prestudy.json"

SEASONS = tuple(range(2007, 2023))
EVAL_SEASONS = tuple(range(2010, 2023))
COVID = (2019, 2020)
EVAL_NONCOVID = tuple(s for s in EVAL_SEASONS if s not in COVID)
SEED = 20261018
N_BOOT = 10_000
ELO = EloParams(k=20.0, hca=90.0, reversion=0.25)
# 2007-2014 code some 2-point makes as LAYUPMD / DUNK and misses as LAYUPATT (checked against
# the points files). Every field goal is therefore 2FGM/3FGM plus LAYUPMD/DUNK; the drafted
# list (2FGM, 3FGM, FTM) misses these makes.
FG_MAKE = ("2FGM", "3FGM", "LAYUPMD", "DUNK")
SCORING = (*FG_MAKE, "FTM")
FG_ALL = (*FG_MAKE, "2FGA", "3FGA", "2FGAB", "3FGAB", "LAYUPATT")
MARKERS = ("BP", "EP", "EG")
REG_BLOCKS = (
    ("FirstQuarter", 1),
    ("SecondQuarter", 2),
    ("ThirdQuarter", 3),
    ("ForthQuarter", 4),
)
CK_T = np.arange(2340, -1, -60)  # regulation checkpoints, remaining time
OT_T = np.arange(300, -1, -60)  # OT checkpoints per period
LL_CLIP = 1e-6
GAMES_SQL = """
    select game_id, season, phase, tipoff_utc, home, away, home_score, away_score,
           played, forfeit, neutral
    from games
    where competition = 'euroleague' and season between 2007 and 2022
    order by tipoff_utc, game_id
"""


def check_season(season: int) -> int:
    if season not in SEASONS:
        raise AssertionError(f"season {season} is outside the 2007-2022 pre-study scope")
    return season


# ----------------------------------------------------------------------------- parsing


def read_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def read_clock(raw: str, maxc: int, ptype: str) -> tuple[float, str]:
    """Return (clock seconds, status). status: ok, blank, nd. Markers get period bounds if blank."""
    s = (raw or "").strip()
    if s == "":
        if ptype == "BP":
            return float(maxc), "blank"
        if ptype in ("EP", "EG"):
            return 0.0, "blank"
        return float("nan"), "blank"
    if ":" in s:
        mm, _, ss = s.partition(":")
        if mm.isdigit() and ss.isdigit():
            return float(min(int(mm) * 60 + int(ss), maxc)), "ok"
    return float("nan"), "nd"


def parse_play(obj: dict[str, Any], mart_home: str, mart_away: str) -> tuple[list, dict]:  # noqa: PLR0912
    """Event rows in log order, plus per-game meta. Score is carried forward, home-perspective."""
    code_a = obj["CodeTeamA"].strip()
    code_b = obj["CodeTeamB"].strip()
    if (code_a, code_b) == (mart_home, mart_away):
        flip = False
    elif (code_b, code_a) == (mart_home, mart_away):
        flip = True
    else:
        return [], {"code_ok": False}
    items: list[tuple[str, int, dict]] = []
    for name, period in REG_BLOCKS:
        items.extend(("R", period, e) for e in obj[name])
    items.extend(("X", 0, e) for e in (obj.get("ExtraTime") or []))
    rows: list[tuple] = []
    cur_a = cur_b = 0
    nd_play = blank_play = 0
    nd_raw: set[str] = set()
    for kind, period, e in items:
        ptype = e["PLAYTYPE"].strip()
        if kind == "X":
            minute = int(e["MINUTE"])
            k = (minute - 41) // 5 if ptype in ("EP", "EG") else (minute - 41) // 5 + 1
            k = max(k, 1)
            period, maxc, base = 4 + k, 300, 2400 + (k - 1) * 300  # noqa: PLW2901
        else:
            maxc, base = 600, (period - 1) * 600
        clock, status = read_clock(e["MARKERTIME"], maxc, ptype)
        if status != "ok" and ptype not in MARKERS:
            if status == "nd":
                nd_play += 1
                nd_raw.add(e["MARKERTIME"])
            else:
                blank_play += 1
        elapsed = base + maxc - clock
        t_rem = (4 - period) * 600 + clock if kind == "R" else clock
        if e["POINTS_A"] is not None:
            cur_a = int(e["POINTS_A"])
        if e["POINTS_B"] is not None:
            cur_b = int(e["POINTS_B"])
        s_home, s_away = (cur_b, cur_a) if flip else (cur_a, cur_b)
        rows.append(
            (
                period,
                int(kind == "X"),
                clock,
                elapsed,
                t_rem,
                ptype,
                e["CODETEAM"].strip(),
                e["PLAYER_ID"].strip(),
                int(e["NUMBEROFPLAY"]),
                s_home,
                s_away,
            )
        )
    has_ot = any(r[1] == 1 and r[5] not in MARKERS for r in rows)
    if not has_ot:
        rows = [r for r in rows if r[1] == 0]
    meta = {
        "code_ok": True,
        "nd_play": nd_play,
        "blank_play": blank_play,
        "nd_raw": sorted(nd_raw),
        "has_ot": has_ot,
        "final_home": rows[-1][9] if rows else None,
        "final_away": rows[-1][10] if rows else None,
    }
    return rows, meta


def parse_box(obj: dict[str, Any]) -> tuple[dict[str, int], int]:
    assists: dict[str, int] = {}
    for block in obj["Stats"]:
        ps = block["PlayersStats"]
        if not ps:
            continue
        code = ps[0]["Team"].strip()
        assists[code] = sum(int(p["Assistances"] or 0) for p in ps)
    return assists, int(obj.get("Attendance") or 0)


def parse_points(obj: dict[str, Any]) -> pd.DataFrame:
    rows = [
        (
            int(r["NUM_ANOT"]),
            r["ID_ACTION"].strip(),
            r["ID_PLAYER"].strip(),
            r["TEAM"].strip(),
            r["ZONE"].strip() if r["ZONE"] else "",
            r["COORD_X"],
            r["COORD_Y"],
        )
        for r in obj["Rows"]
        if r["ID_ACTION"].strip() in FG_ALL
    ]
    return pd.DataFrame(rows, columns=["num", "action", "pid", "team", "zone", "x", "y"])


# ----------------------------------------------------------------------------- data build


@dataclass
class Data:
    G: pd.DataFrame  # one row per mart game (all seasons 2007-2022)
    EV: pd.DataFrame  # event rows, included games only
    C: pd.DataFrame  # checkpoint rows (kind ck) and tip-off rows (kind tip), included games
    S: pd.DataFrame  # scoring-event rows (training), included games
    as_recs: pd.DataFrame  # one row per AS event
    linked: set  # (gid, NUMBEROFPLAY) of made field goals with a linked AS
    box: pd.DataFrame  # per included team-game: code, assists, attendance
    points: pd.DataFrame  # FG rows from the points files, included games
    meta: pd.DataFrame  # per mart game: parse status and counts


def build(games: pd.DataFrame) -> Data:  # noqa: PLR0915
    games = games.reset_index(drop=True).copy()
    games["gid"] = np.arange(len(games))
    games["margin"] = (games["home_score"] - games["away_score"]).fillna(0).astype(int)
    games["diff"] = replay(prepare(games), ELO)
    games["p_pre"] = np.clip(1.0 / (1.0 + 10.0 ** (-games["diff"] / 400.0)), LL_CLIP, 1 - LL_CLIP)
    games["logit_pre"] = np.log(games["p_pre"] / (1 - games["p_pre"]))
    games["rated"] = games["played"].astype(bool) & ~games["forfeit"].astype(bool)

    meta_rows: list[dict] = []
    ev_parts: list[pd.DataFrame] = []
    box_rows: list[dict] = []
    pts_parts: list[pd.DataFrame] = []
    for r in games.itertuples(index=False):
        season = check_season(int(r.season))
        fnum = str(r.game_id).split("_")[-1]
        path = RAW / "playbyplay" / f"E{season}" / f"{fnum}.json.gz"
        m: dict[str, Any] = {"gid": int(r.gid), "season": season, "phase": r.phase}
        reason = None
        if not bool(r.played) or bool(r.forfeit):
            reason = "not_played"
        elif not path.exists():
            reason = "no_file"
        else:
            rows, pm = parse_play(read_json(path), r.home, r.away)
            m.update({k: v for k, v in pm.items() if k not in {"final_home", "final_away"}})
            if not pm.get("code_ok", False):
                reason = "code_mismatch"
            elif pm["nd_play"] > 0:
                reason = "nd_clock"
            elif (pm["final_home"], pm["final_away"]) != (int(r.home_score), int(r.away_score)):
                reason = "score_mismatch"
        m["reason"] = reason
        meta_rows.append(m)
        if reason is not None:
            continue
        ev = pd.DataFrame(
            rows,
            columns=[
                "period",
                "ot",
                "clock",
                "elapsed",
                "t",
                "pt",
                "team",
                "pid",
                "num",
                "sH",
                "sA",
            ],
        )
        ev.insert(0, "gid", int(r.gid))
        ev.insert(1, "season", season)
        ev["m"] = ev["sH"] - ev["sA"]
        ev_parts.append(ev)
        bpath = RAW / "boxscore" / f"E{season}" / f"{fnum}.json.gz"
        assists, att = parse_box(read_json(bpath))
        for code, val in assists.items():
            box_rows.append(
                {"gid": int(r.gid), "season": season, "team": code, "box_ast": val, "att": att}
            )
        ppath = RAW / "points" / f"E{season}" / f"{fnum}.json.gz"
        pdf = parse_points(read_json(ppath))
        pdf.insert(0, "gid", int(r.gid))
        pdf.insert(1, "season", season)
        pts_parts.append(pdf)

    meta = pd.DataFrame(meta_rows)
    EV = pd.concat(ev_parts, ignore_index=True)
    EV["pos"] = EV.groupby("gid").cumcount()

    as_recs, linked = link_assists(EV)
    C, S = checkpoints(EV, games)
    return Data(
        G=games,
        EV=EV,
        C=C,
        S=S,
        as_recs=as_recs,
        linked=linked,
        box=pd.DataFrame(box_rows),
        points=pd.concat(pts_parts, ignore_index=True),
        meta=meta,
    )


def link_assists(EV: pd.DataFrame) -> tuple[pd.DataFrame, set]:
    """Rule: nearest preceding made FG (any team) in the same period must be the AS team's own."""
    recs: list[tuple] = []
    linked: set = set()
    for gid, ev in EV.groupby("gid", sort=False):
        pt = ev["pt"].to_numpy()
        team = ev["team"].to_numpy()
        per = ev["period"].to_numpy()
        clk = ev["clock"].to_numpy()
        num = ev["num"].to_numpy()
        season = int(ev["season"].iloc[0])
        last = -1
        cur = -1
        for i in range(len(pt)):
            if per[i] != cur:
                cur, last = per[i], -1
            if pt[i] == "AS":
                ok = last >= 0 and team[last] == team[i]
                gap = abs(clk[i] - clk[last]) if ok else np.nan
                adjacent = i > 0 and pt[i - 1] in FG_MAKE and team[i - 1] == team[i]
                # Variant B (not the drafted rule): AS logged just before its own make. Link to the
                # next make in the period if it is the same team's, at the same clock, and no other
                # make comes first.
                linked_b = ok
                if not ok:
                    nxt = _next_make(pt, per, i)
                    linked_b = nxt >= 0 and team[nxt] == team[i] and clk[nxt] == clk[i]
                recs.append((gid, season, team[i], bool(ok), gap, bool(adjacent), bool(linked_b)))
                if ok:
                    linked.add((gid, int(num[last])))
            if pt[i] in FG_MAKE:
                last = i
    as_recs = pd.DataFrame(
        recs, columns=["gid", "season", "team", "linked", "gap", "adjacent", "linked_b"]
    )
    return as_recs, linked


def _next_make(pt: np.ndarray, per: np.ndarray, i: int) -> int:
    """Index of the first made FG after position i in the same period, or -1."""
    for j in range(i + 1, len(pt)):
        if per[j] != per[i]:
            return -1
        if pt[j] in FG_MAKE:
            return j
    return -1


def _tip_row(  # noqa: PLR0917
    gid: int, season: int, phase: str, neutral: int, lp: float, y: int, diff: float
) -> tuple:
    return (gid, season, phase, "tip", 2400.0, 0.0, 0, neutral, lp, y, diff)


def checkpoints(EV: pd.DataFrame, games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    gi = games.set_index("gid")
    ck_rows: list[tuple] = []
    for gid, ev in EV.groupby("gid", sort=False):
        g = gi.loc[gid]
        neutral = int(bool(g["neutral"]))
        lp = float(g["logit_pre"])
        y = int(g["home_score"] > g["away_score"])
        diff = float(g["diff"])
        phase = g["phase"]
        season = int(ev["season"].iloc[0])
        elapsed = ev["elapsed"].to_numpy()
        m_arr = ev["m"].to_numpy()
        run = np.maximum.accumulate(elapsed)
        has_ot_play = ((ev["ot"] == 1) & ~ev["pt"].isin(MARKERS)).any()
        n_ot = int(ev.loc[ev["ot"] == 1, "period"].max() - 4) if has_ot_play else 0
        ck_t = [CK_T.astype(float)]
        ck_e = [2400.0 - CK_T]
        ck_ot = [np.zeros(len(CK_T))]
        for k in range(1, n_ot + 1):
            ck_t.append(OT_T.astype(float))
            ck_e.append(2400.0 + (k - 1) * 300.0 + (300.0 - OT_T))
            ck_ot.append(np.ones(len(OT_T)))
        t_all = np.concatenate(ck_t)
        e_all = np.concatenate(ck_e)
        ot_all = np.concatenate(ck_ot)
        idx = np.searchsorted(run, e_all, side="right") - 1
        m_all = np.where(idx >= 0, m_arr[np.clip(idx, 0, None)], 0)
        for t_v, m_v, o_v in zip(t_all, m_all, ot_all, strict=True):
            ck_rows.append(
                (gid, season, phase, "ck", float(t_v), float(m_v), int(o_v), neutral, lp, y, diff)
            )
        ck_rows.append(_tip_row(gid, season, phase, neutral, lp, y, diff))
    cols = ["gid", "season", "phase", "kind", "t", "m", "ot", "neutral", "logit_pre", "y", "diff"]
    C = pd.DataFrame(ck_rows, columns=cols)
    S = EV.loc[EV["pt"].isin(SCORING), ["gid", "season", "t", "m", "ot"]].copy()
    S = S.merge(
        games[["gid", "phase", "neutral", "logit_pre", "home_score", "away_score"]], on="gid"
    )
    S["y"] = (S["home_score"] > S["away_score"]).astype(int)
    S = S.drop(columns=["home_score", "away_score"]).reset_index(drop=True)
    S["neutral"] = S["neutral"].astype(int)
    return C, S


# ----------------------------------------------------------------------------- models


def design(df: pd.DataFrame) -> np.ndarray:
    m = df["m"].to_numpy(float)
    t = df["t"].to_numpy(float)
    ot = df["ot"].to_numpy(float)
    lp = df["logit_pre"].to_numpy(float)
    nt = df["neutral"].to_numpy(float)
    tf = t / 2400.0
    z = m / np.sqrt(np.maximum(t, 60.0) / 2400.0)
    return np.column_stack([m, tf, ot, m * tf, z, lp, nt, m * lp * tf])


def fit_logit(train: pd.DataFrame) -> Any:
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
    model.fit(design(train), train["y"].to_numpy(int))
    return model


def expanding_oof(S: pd.DataFrame, C: pd.DataFrame, exclude: tuple = ()) -> np.ndarray:
    """Out-of-fold P(home) for every row of C in EVAL_SEASONS; train = seasons 2007..s-1."""
    out = np.full(len(C), np.nan)
    seasons = C["season"].to_numpy()
    for s in EVAL_SEASONS:
        train = S[(S["season"] < s) & ~S["season"].isin(exclude)]
        model = fit_logit(train)
        mask = seasons == s
        out[mask] = model.predict_proba(design(C[mask]))[:, 1]
    return out


def baseline_p(C: pd.DataFrame, s_fold: dict[int, float]) -> np.ndarray:
    s = C["season"].map(s_fold).to_numpy(float)
    mu = C["diff"].to_numpy(float) / s
    t = C["t"].to_numpy(float)
    m = C["m"].to_numpy(float)
    tf = t / 2400.0
    return ndtr((m + mu * tf) / (11.0 * np.sqrt(np.maximum(t, 60.0) / 2400.0)))


def ll(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(p, LL_CLIP, 1 - LL_CLIP)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def per_game(ck: pd.DataFrame) -> pd.DataFrame:
    """Checkpoint-averaged per game (section 6): mean p, mean loss, observed y."""
    return ck.groupby("gid").agg(
        season=("season", "first"),
        phase=("phase", "first"),
        y=("y", "first"),
        p=("p", "mean"),
        l=("l", "mean"),
    )


def boot_means(mats: list[np.ndarray], rng: np.random.Generator) -> list[np.ndarray]:
    """Bootstrap over games: each (n_games, k) matrix is resampled on its own rows."""
    outs = [np.empty((N_BOOT, m.shape[1])) for m in mats]
    for start in range(0, N_BOOT, 500):
        b = min(500, N_BOOT - start)
        for j, mat in enumerate(mats):
            idx = rng.integers(0, mat.shape[0], size=(b, mat.shape[0]))
            outs[j][start : start + b] = mat[idx].mean(axis=1)
    return outs


def ci(vals: np.ndarray) -> list[float]:
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return [float(lo), float(hi)]


# ----------------------------------------------------------------------------- tasks


def t1_assists(d: Data) -> dict[str, Any]:  # noqa: PLR0915
    rng = np.random.default_rng(SEED)
    out: dict[str, Any] = {}
    a = d.as_recs.copy()
    per_season = []
    for s, sub in a.groupby("season"):
        lk = sub[sub["linked"]]
        per_season.append(
            {
                "season": int(s),
                "as_rows": len(sub),
                "share_linked": float(sub["linked"].mean()),
                "share_linked_variant_B": float(sub["linked_b"].mean()),
                "share_linked_gap0": float((lk["gap"] == 0).mean()) if len(lk) else None,
                "share_linked_gap_le5": float((lk["gap"] <= 5).mean()) if len(lk) else None,
                "share_prev_event_same_team_make": float(sub["adjacent"].mean()),
            }
        )
    out["linkage_by_season"] = per_season
    lk_all = a[a["linked"]]
    out["linkage_all"] = {
        "as_rows": len(a),
        "share_linked": float(a["linked"].mean()),
        "share_linked_variant_B": float(a["linked_b"].mean()),
        "share_linked_gap0": float((lk_all["gap"] == 0).mean()),
        "share_linked_gap_le5": float((lk_all["gap"] <= 5).mean()),
        "share_prev_event_same_team_make": float(a["adjacent"].mean()),
        "make_linked_twice": int(len(lk_all) - len(d.linked)),
    }
    # Box-score validation per team-game (included games only).
    lk_counts = lk_all.groupby(["gid", "team"]).size().rename("linked_n").reset_index()
    all_counts = a.groupby(["gid", "team"]).size().rename("all_n").reset_index()
    bx = d.box.merge(lk_counts, on=["gid", "team"], how="left").merge(
        all_counts, on=["gid", "team"], how="left"
    )
    bx = bx.fillna({"linked_n": 0, "all_n": 0})
    bx["ok_linked"] = bx["linked_n"] == bx["box_ast"]
    bx["ok_all"] = bx["all_n"] == bx["box_ast"]
    lkb = a[a["linked_b"]].groupby(["gid", "team"]).size().rename("linked_b_n").reset_index()
    bx = bx.merge(lkb, on=["gid", "team"], how="left").fillna({"linked_b_n": 0})
    bx["ok_linked_b"] = bx["linked_b_n"] == bx["box_ast"]
    out["box_validation"] = {
        "team_games": len(bx),
        "agree_linked_exact": float(bx["ok_linked"].mean()),
        "agree_all_AS_rows_exact": float(bx["ok_all"].mean()),
        "variant_B_agree_exact": float(bx["ok_linked_b"].mean()),
        "variant_B_linked_total": int(bx["linked_b_n"].sum()),
        "linked_total": int(bx["linked_n"].sum()),
        "box_total": int(bx["box_ast"].sum()),
        "all_AS_total": int(bx["all_n"].sum()),
        "agree_linked_by_season": {
            int(s): float(g["ok_linked"].mean()) for s, g in bx.groupby("season")
        },
    }

    # (b) identification problem and passer-share bounds.
    P = d.points.copy()
    P["is_make"] = P["action"].isin(FG_MAKE)
    P["is3"] = P["action"].str.startswith("3")
    P["linked"] = [(g, n) in d.linked for g, n in zip(P["gid"], P["num"], strict=True)]
    attempts = P.groupby("gid").size().rename("N")
    makes = P[P["is_make"]]
    am = makes[makes["linked"]].groupby("gid").size().rename("Nam")
    um = makes[~makes["linked"]].groupby("gid").size().rename("Num")
    included_gids = d.EV["gid"].drop_duplicates().to_numpy()
    per_game_counts = pd.concat([attempts, am, um], axis=1).reindex(included_gids).fillna(0)
    # Coverage of the points file vs pbp makes, and join check.
    pb = d.EV[d.EV["pt"].isin(FG_ALL)][["gid", "num", "pt", "pid"]].rename(
        columns={"pt": "pt_pbp", "pid": "pid_pbp"}
    )
    j = P.merge(pb, on=["gid", "num"], how="left")
    out["points_join"] = {
        "fg_points_rows": len(P),
        "matched_to_pbp_event": float(j["pt_pbp"].notna().mean()),
        "action_agrees": float((j["action"] == j["pt_pbp"]).mean()),
        "shooter_agrees": float((j["pid"] == j["pid_pbp"]).mean()),
    }
    zone_share = P.groupby("season")["zone"].apply(lambda z: float((z != "").mean()))
    out["zone_nonempty_share_by_season"] = {int(k): float(v) for k, v in zone_share.items()}
    coord_share = P.groupby("season")["x"].apply(lambda x: float(x.notna().mean()))
    out["coord_nonnull_share_by_season"] = {int(k): float(v) for k, v in coord_share.items()}

    n_am = int(makes["linked"].sum())
    n_um = int((~makes["linked"]).sum())
    n_att = len(P)
    n_miss = int((~P["is_make"]).sum())
    R = n_um / n_am
    f_min = n_am / n_att
    f0 = 1.0 / (1.0 + R)
    out["assist_counts"] = {
        "fg_attempts_with_coords": n_att,
        "fg_makes": len(makes),
        "fg_misses": n_miss,
        "assisted_makes_linked": n_am,
        "unassisted_makes": n_um,
        "assisted_makes_share_of_makes": n_am / len(makes),
        "assisted_misses_by_construction": 0,
    }

    def s_of_f(f: float, r: float) -> float:
        return 1.0 - r * f / (1.0 - f)

    def f_for_share(sh: float, r: float) -> float:
        return (1.0 - sh) / (r + 1.0 - sh)

    out["passer_share_identification"] = {
        "R_unassisted_over_assisted_makes": R,
        "f_min_feasible_assisted_attempt_share": f_min,
        "f_at_S0_assisted_equals_unassisted_make_rate": f0,
        "S_at_f_min": s_of_f(f_min, R),
        "S_grid": {
            str(f): s_of_f(f, R) for f in (0.3, 0.4, 0.5, 0.6) if f_min <= f <= 1 - n_um / n_att
        },
        "f_implied_by_proposed_70_30": f_for_share(0.3, R),
        "f_implied_by_50_50": f_for_share(0.5, R),
        "f_implied_by_100_0": f_for_share(0.0, R),
    }
    # Bootstrap over games for R, f_min and f at S=0.
    gc = per_game_counts[["N", "Nam", "Num"]].to_numpy(float)
    boots = boot_means([gc], rng)[0]
    Rb = boots[:, 2] / boots[:, 1]
    fminb = boots[:, 1] / boots[:, 0]
    out["passer_share_identification"]["bootstrap_95ci"] = {
        "R": ci(Rb),
        "f_min": ci(fminb),
        "f_at_S0": ci(1.0 / (1.0 + Rb)),
    }
    # 2pt vs 3pt split of R (to check whether the identification gap is shot-type specific).
    out["R_by_shot_type"] = {}
    for is3, label in ((False, "2pt"), (True, "3pt")):
        sub = makes[makes["is3"] == is3]
        nm = int(sub["linked"].sum())
        nu = int((~sub["linked"]).sum())
        out["R_by_shot_type"][label] = {
            "assisted": nm,
            "unassisted": nu,
            "R": nu / nm if nm else None,
        }

    # Makes-only logistic model: what the data can identify (assisted share by zone, 3pt, shooter).
    mk = makes[makes["zone"] != ""].copy()
    y = mk["linked"].to_numpy(int)
    zone_d = pd.get_dummies(mk["zone"], drop_first=True).to_numpy(float)
    shooter = (mk["pid"] + "_" + mk["season"].astype(str)).to_numpy()
    codes, uniques = pd.factorize(shooter)
    fe = csr_matrix(
        (np.ones(len(codes)), (np.arange(len(codes)), codes)), shape=(len(codes), len(uniques))
    )
    X = hstack([csr_matrix(np.column_stack([zone_d, mk["is3"].to_numpy(float)])), fe]).tocsr()
    clf = LogisticRegression(C=1.0, max_iter=5000).fit(X, y)
    coef_names = [f"zone_{c}" for c in pd.get_dummies(mk["zone"], drop_first=True).columns] + [
        "is3"
    ]
    out["makes_only_logit"] = {
        "n_makes": len(mk),
        "assisted_share": float(y.mean()),
        "shooter_season_levels": len(uniques),
        "coef": {
            n: float(c) for n, c in zip(coef_names, clf.coef_[0][: len(coef_names)], strict=True)
        },
        "note": "Assisted is defined only on makes; the make ~ assisted model is not identified.",
    }
    out["c_proxy_wpa"] = "not run (optional; not done in this pre-study)"
    return out


def t2_clock_repair(d: Data) -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    m = d.meta
    m16 = m[m["season"] == 2016]
    nd_games = m16[m16["nd_play"] > 0]
    out: dict[str, Any] = {
        "games_2016_files": int((m16["reason"] != "no_file").sum()),
        "games_2016_with_nd_play_event": len(nd_games),
        "nd_play_events_2016": int(nd_games["nd_play"].sum()),
        "nd_raw_values": sorted({v for lst in nd_games["nd_raw"] for v in lst}),
        "games_2016_excluded_by_reason": m16["reason"].fillna("included").value_counts().to_dict(),
    }
    counts = nd_games["nd_play"].to_numpy(int)
    p_aff = len(nd_games) / max(out["games_2016_files"], 1)
    val = d.EV[d.EV["season"].isin([2015, 2017])]
    errs: list[np.ndarray] = []
    by_season: dict[str, list[np.ndarray]] = {"2015": [], "2017": []}
    replicates = 5
    for _rep in range(replicates):
        for _gid, ev in val.groupby("gid", sort=False):
            k = int(rng.choice(counts)) if rng.random() < p_aff else 0
            if k == 0:
                continue
            period = ev["period"].to_numpy()
            clock_true = ev["clock"].to_numpy(float)
            is_play = ~ev["pt"].isin(MARKERS).to_numpy()
            cand = np.flatnonzero(is_play & ~np.isnan(clock_true))
            if len(cand) == 0:
                continue
            pick = rng.choice(cand, size=min(k, len(cand)), replace=False)
            blank = np.zeros(len(ev), dtype=bool)
            blank[pick] = True
            rep = repair(period, clock_true, blank)
            err = np.abs(rep[pick] - clock_true[pick])
            errs.append(err)
            by_season[str(int(ev["season"].iloc[0]))].append(err)
    allerr = np.concatenate(errs)
    out["validation"] = {
        "seasons": ["2015", "2017"],
        "replicates": replicates,
        "blanked_events": len(allerr),
        "MAE_seconds": float(allerr.mean()),
        "P50_seconds": float(np.percentile(allerr, 50)),
        "P95_seconds": float(np.percentile(allerr, 95)),
        "P95_by_season": {
            k: float(np.percentile(np.concatenate(v), 95)) for k, v in by_season.items() if v
        },
        "recommend_repair": bool(np.percentile(allerr, 95) <= 15.0),
    }
    return out


def repair(period: np.ndarray, clock: np.ndarray, blank: np.ndarray) -> np.ndarray:
    """Linear interpolation in log position between nearest valid clocks of the same period.

    Period start (max clock) and end (0) act as anchors when no valid neighbour exists.
    """
    work = clock.copy()
    work[blank] = np.nan
    out = clock.copy()
    for i in np.flatnonzero(blank):
        same = period == period[i]
        valid = same & ~np.isnan(work)
        left = np.flatnonzero(valid[:i])
        right = np.flatnonzero(valid[i + 1 :]) + i + 1
        pos = np.flatnonzero(same)
        maxc = 600.0 if period[i] <= 4 else 300.0
        if left.size:
            il, vl = int(left[-1]), float(work[left[-1]])
        else:
            il, vl = int(pos[0]) - 1, maxc
        if right.size:
            ir, vr = int(right[0]), float(work[right[0]])
        else:
            ir, vr = int(pos[-1]) + 1, 0.0
        out[i] = np.interp(i, [il, ir], [vl, vr])
    return out


def t3_playoffs(d: Data, base: np.ndarray) -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    C = d.C.assign(p=base)
    ck = C[(C["kind"] == "ck") & C["season"].isin(EVAL_SEASONS)].copy()
    ck["l"] = ll(ck["y"].to_numpy(float), ck["p"].to_numpy(float))
    g = per_game(ck)
    g["gap"] = g["p"] - g["y"]
    rs = g[g["phase"].isin(["RS", "TS"])]
    po = g[g["phase"].isin(["PO", "FF", "PI"])]

    def summarise(x: pd.DataFrame) -> dict[str, Any]:
        bins = pd.cut(x["p"], np.linspace(0, 1, 11), include_lowest=True)
        table = (
            x.groupby(bins, observed=False)
            .agg(n=("y", "size"), mean_pred=("p", "mean"), observed=("y", "mean"))
            .reset_index(drop=True)
        )
        return {
            "games": len(x),
            "mean_pred": float(x["p"].mean()),
            "observed_home_win": float(x["y"].mean()),
            "gap_pred_minus_obs": float(x["gap"].mean()),
            "log_loss": float(x["l"].mean()),
            "bins": [
                {k: (None if pd.isna(v) else float(v)) for k, v in row.items()}
                for row in table.to_dict(orient="records")
            ],
        }

    bs = boot_means([rs[["gap", "l"]].to_numpy(), po[["gap", "l"]].to_numpy()], rng)
    gap_diff = bs[1][:, 0] - bs[0][:, 0]
    ll_diff = bs[1][:, 1] - bs[0][:, 1]
    res = {
        "regular_season_incl_TS": summarise(rs),
        "playoffs_PO_PI_FF": summarise(po),
        "playoff_minus_rs_gap_ci95": ci(gap_diff),
        "playoff_gap_ci95": ci(bs[1][:, 0]),
        "playoff_minus_rs_logloss_ci95": ci(ll_diff),
        "playoff_minus_rs_logloss": float(po["l"].mean() - rs["l"].mean()),
        "by_phase_n": ck.groupby("phase")["gid"].nunique().to_dict(),
    }
    res["recommend_phase_flag"] = bool(not (ci(gap_diff)[0] <= 0 <= ci(gap_diff)[1]))
    res["by_phase_n"] = {str(k): int(v) for k, v in res["by_phase_n"].items()}
    return res


def t4_covid(d: Data, base: np.ndarray, S: pd.DataFrame, C: pd.DataFrame) -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    C = C.assign(p=base)
    per_season = []
    for s in EVAL_SEASONS:
        cs = C[(C["season"] == s) & (C["kind"] == "ck")]
        tip = C[(C["season"] == s) & (C["kind"] == "tip")]
        g = per_game(cs.assign(l=ll(cs["y"].to_numpy(float), cs["p"].to_numpy(float))))
        per_season.append(
            {
                "season": s,
                "games": len(g),
                "observed_home_win": float(g["y"].mean()),
                "mean_pred_ck": float(g["p"].mean()),
                "mean_pred_tip": float(tip["p"].mean()),
                "home_win_rate_tip_obs": float(tip["y"].mean()),
                "log_loss_ck": float(g["l"].mean()),
            }
        )
    covid = {r["season"]: r for r in per_season if r["season"] in COVID}
    p_ex = expanding_oof(S, C, exclude=COVID)
    ck_mask = (C["kind"] == "ck") & C["season"].isin(EVAL_NONCOVID)
    sub = C[ck_mask].assign(p_base=base[ck_mask.to_numpy()], p_ex=p_ex[ck_mask.to_numpy()])
    sub["l_base"] = ll(sub["y"].to_numpy(float), sub["p_base"].to_numpy(float))
    sub["l_ex"] = ll(sub["y"].to_numpy(float), sub["p_ex"].to_numpy(float))
    gg = sub.groupby("gid").agg(
        lb=("l_base", "mean"), le=("l_ex", "mean"), pb=("p_base", "mean"), pe=("p_ex", "mean")
    )
    diff = gg["le"].to_numpy() - gg["lb"].to_numpy()
    (boot,) = boot_means([diff.reshape(-1, 1)], rng)
    ci_d = ci(boot[:, 0])
    return {
        "per_season_oof": per_season,
        "covid_seasons": {str(k): v for k, v in covid.items()},
        "other_seasons": list(EVAL_NONCOVID),
        "logloss_base_incl_covid_training": float(gg["lb"].mean()),
        "logloss_excl_covid_training": float(gg["le"].mean()),
        "delta_excl_minus_base": float(diff.mean()),
        "delta_ci95": ci_d,
        "games_other_seasons": len(gg),
        "recommend": "drop COVID seasons from training" if ci_d[1] < 0 else "keep",
    }


def t5_tipoff(d: Data, base: np.ndarray, C: pd.DataFrame) -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    C = C.assign(p=base)
    tip = C[(C["kind"] == "tip") & C["season"].isin(EVAL_SEASONS)].set_index("gid")
    G = d.G.set_index("gid")
    g_gap = G.loc[tip.index, "p_pre"].to_numpy() - tip["p"].to_numpy()
    ag = np.abs(g_gap)
    out: dict[str, Any] = {
        "games": len(tip),
        "g_mean": float(g_gap.mean()),
        "abs_g": {
            "mean": float(ag.mean()),
            "sd": float(ag.std(ddof=1)),
            "p05": float(np.percentile(ag, 5)),
            "p95": float(np.percentile(ag, 95)),
        },
    }
    # Baseline start check: closed form at tip-off vs P_pre.
    s_fold = fold_scales(d.G)
    mu_tip = G.loc[tip.index, "diff"].to_numpy() / np.array([s_fold[int(s)] for s in tip["season"]])
    base_tip = ndtr(mu_tip / 11.0)
    out["baseline_tipoff"] = {
        "mean_abs_Pprepre_minus_baseline": float(
            np.abs(G.loc[tip.index, "p_pre"].to_numpy() - base_tip).mean()
        ),
        "mean_Pprepre_minus_baseline": float(
            (G.loc[tip.index, "p_pre"].to_numpy() - base_tip).mean()
        ),
    }
    if np.percentile(ag, 95) < 0.01:
        out["recommend"] = "linear"
        out["fade_comparison"] = "skipped (95th percentile |g| < 0.01)"
        return out

    gmap = pd.Series(g_gap, index=tip.index)
    ck = C[(C["kind"] == "ck") & C["season"].isin(EVAL_SEASONS)].copy()
    gvals = gmap.reindex(ck["gid"]).to_numpy()
    tf = ck["t"].to_numpy(float) / 2400.0
    y = ck["y"].to_numpy(float)
    shapes = {
        "none": np.zeros_like(tf),
        "constant": np.ones_like(tf),
        "linear_tf": tf,
        "quadratic_tf2": tf**2,
        "exp_minus3_1mtf": np.exp(-3.0 * (1.0 - tf)),
    }
    pm = ck["p"].to_numpy()
    ll_by = {}
    per_game_mat = {}
    gids = ck["gid"].to_numpy()
    for name, f in shapes.items():
        p_adj = np.clip(pm + gvals * f, 0.001, 0.999)
        lo = ll(y, p_adj)
        frame = pd.DataFrame({"gid": gids, "l": lo}).groupby("gid")["l"].mean()
        ll_by[name] = float(frame.mean())
        per_game_mat[name] = frame.to_numpy().reshape(-1, 1)
    best = min(ll_by, key=ll_by.get)
    diff_vs_linear = per_game_mat[best] - per_game_mat["linear_tf"]
    (boot_d,) = boot_means([diff_vs_linear], rng)
    out["fade_comparison"] = {
        "logloss_by_shape": ll_by,
        "best_shape": best,
        "best_minus_linear_mean": float(diff_vs_linear.mean()),
        "best_minus_linear_ci95": ci(boot_d[:, 0]),
        "note": "OT checkpoints use t = clock (section 4); tf is not 0 in OT as section 7 states.",
    }
    out["recommend"] = best
    return out


def fold_scales(G: pd.DataFrame) -> dict[int, float]:
    rated = G[G["rated"]]
    scales = {}
    for s in EVAL_SEASONS:
        sub = rated[rated["season"] < s]
        scales[s] = fit_margin_scale(sub["diff"].to_numpy(float), sub["margin"].to_numpy(float))
    return scales


# ----------------------------------------------------------------------------- main


def shot_code_table(d: Data) -> list[dict]:
    """Made and missed field-goal codes per season (shows the 2008-2014 layup and dunk coding)."""
    codes = ["2FGM", "LAYUPMD", "DUNK", "3FGM", "2FGA", "LAYUPATT", "2FGAB", "3FGA"]
    cnt = d.EV[d.EV["pt"].isin(codes)].pivot_table(
        index="season", columns="pt", aggfunc="size", fill_value=0
    )
    cnt = cnt.reindex(columns=codes, fill_value=0)
    return [{"season": int(s), **{c: int(cnt.loc[s, c]) for c in codes}} for s in cnt.index]


def season_table(d: Data) -> list[dict]:
    rows = []
    G = d.G
    m = d.meta.set_index("gid")
    for s, sub in G.groupby("season"):
        mm = m.loc[sub["gid"]]
        rows.append(
            {
                "season": int(s),
                "mart_games": len(sub),
                "mart_played": int(sub["rated"].sum()),
                "files_with_pbp": int((mm["reason"] != "no_file").sum()),
                "included": int(mm["reason"].isna().sum()),
                "excluded_by_reason": {
                    str(k): int(v) for k, v in mm["reason"].dropna().value_counts().items()
                },
                "phases": {str(k): int(v) for k, v in sub["phase"].value_counts().items()},
            }
        )
    return rows


def attendance_table(d: Data) -> list[dict]:
    b = d.box.drop_duplicates(subset=["gid"])
    rows = []
    for s, sub in b.groupby("season"):
        rows.append(
            {
                "season": int(s),
                "games": len(sub),
                "share_attendance_zero": float((sub["att"] == 0).mean()),
                "median_attendance": float(sub["att"].median()),
            }
        )
    return rows


def main() -> None:
    t0 = time.time()
    con = duckdb.connect(str(MART), read_only=True)
    games = con.sql(GAMES_SQL).df()
    con.close()
    assert games["season"].between(SEASONS[0], SEASONS[-1]).all()
    d = build(games)
    print(
        f"built data in {time.time() - t0:.1f}s; games={len(d.G)} "
        f"included={int(d.meta['reason'].isna().sum())}"
    )

    included = d.G[d.G["gid"].isin(d.meta.loc[d.meta["reason"].isna(), "gid"])]
    S = d.S
    C = d.C
    ck_mask = (C["kind"] == "ck") & C["season"].isin(EVAL_SEASONS)
    base_oof = expanding_oof(S, C)
    print(f"OOF fitted in {time.time() - t0:.1f}s")
    s_fold = fold_scales(d.G)
    # Baseline is computed for the same rows as the model.
    base_closed = baseline_p(C, s_fold)

    results: dict[str, Any] = {
        "scope": "Seasons 2007-2022 only. No validation or test season was read.",
        "counts": {
            "mart_games_2007_2022": len(d.G),
            "included_games": len(included),
            "scoring_rows": len(S),
            "checkpoint_rows_eval": int(ck_mask.sum()),
            "exclusion_reasons": {
                str(k): int(v) for k, v in d.meta["reason"].dropna().value_counts().items()
            },
        },
        "season_table": season_table(d),
        "shot_codes_by_season": shot_code_table(d),
        "attendance_by_season": attendance_table(d),
        "elo": {
            "k": ELO.k,
            "hca": ELO.hca,
            "reversion": ELO.reversion,
            "s_fold_by_eval_season": {str(k): float(v) for k, v in s_fold.items()},
        },
    }
    cs = C.assign(p_model=base_oof, p_base=base_closed)
    cs_ck = cs[ck_mask].copy()
    lm = ll(cs_ck["y"].to_numpy(float), cs_ck["p_model"].to_numpy(float))
    lb = ll(cs_ck["y"].to_numpy(float), cs_ck["p_base"].to_numpy(float))
    cs_ck["lm"] = lm
    cs_ck["lb"] = lb
    gg = cs_ck.groupby("gid").agg(lm=("lm", "mean"), lb=("lb", "mean"))
    results["oof_logloss"] = {
        "model_logit_ck": float(gg["lm"].mean()),
        "baseline_closed_form_ck": float(gg["lb"].mean()),
        "model_minus_baseline": float((gg["lm"] - gg["lb"]).mean()),
    }

    print("T1")
    results["T1_assists"] = t1_assists(d)
    print(f"T1 done {time.time() - t0:.1f}s")
    results["T2_clock_2016"] = t2_clock_repair(d)
    results["T3_playoffs"] = t3_playoffs(d, base_oof)
    print(f"T3 done {time.time() - t0:.1f}s")
    results["T4_covid"] = t4_covid(d, base_oof, S, C)
    print(f"T4 done {time.time() - t0:.1f}s")
    results["T5_tipoff"] = t5_tipoff(d, base_oof, C)
    print(f"T5 done {time.time() - t0:.1f}s")

    results["runtime_seconds"] = round(time.time() - t0, 1)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(_jsonable(results), indent=2), encoding="utf-8")
    print(f"wrote {REPORT} in {time.time() - t0:.1f}s")


def _jsonable(obj: Any) -> Any:  # noqa: PLR0911
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(obj) else None
    return obj


if __name__ == "__main__":
    main()
