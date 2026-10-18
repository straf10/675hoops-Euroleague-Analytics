"""T1(c): measure the assist split from player-season WPA (follow-up to wp_prestudy.py).

Seasons 2007-2022 only: the pre-study loader refuses other seasons, and every table here is
filtered to 2007-2022 before use.

Two stages, run in order:
  uv run python scripts/wp_t1c.py linkage   pick the AS-to-make rule on box-score data only
  uv run python scripts/wp_t1c.py measure   WPA by player-season, criterion, bootstrap

Both stages merge a "T1c_measured_split" block into reports/wp_prestudy.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.special import ndtr
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wp_prestudy as wp

SEED = wp.SEED
N_BOOT = 1000
S_GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
MIN_MINUTES = 500.0
CRITERION_SEASONS = tuple(range(2010, 2022))  # s; target season s+1 in 2011..2022
SUB_CODES = ("IN", "OUT", "AS")
CREDIT_DEF = (
    "event-only: dWP = WP(score after e, same clock) - WP(score before e, same clock) on the "
    "baseline line with linear tip-off gap fade; time passage credits nobody"
)
RAPM_PATH = wp.ROOT / "reports" / "m3_players.json"
VARIANTS = ("A_drafted", "B_plus_AS_before_make", "C_plus_pm2_or_same_clock", "D_all")


def merge_report(block: dict[str, Any]) -> None:
    out = json.loads(wp.REPORT.read_text(encoding="utf-8"))
    out.setdefault("T1c_measured_split", {}).update(block)
    wp.REPORT.write_text(json.dumps(wp._jsonable(out), indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------- inputs


def box_players(d: wp.Data) -> pd.DataFrame:
    """Per included game and player: season, team, seconds, plus-minus, assists (raw box score)."""
    inc = d.meta[d.meta["reason"].isna()]
    game_ids = d.G.set_index("gid")["game_id"]
    rows: list[tuple] = []
    for gid, season_raw in zip(inc["gid"], inc["season"], strict=True):
        season = wp.check_season(int(season_raw))
        fnum = str(game_ids.loc[gid]).split("_")[-1]
        obj = wp.read_json(wp.RAW / "boxscore" / f"E{season}" / f"{fnum}.json.gz")
        for block in obj["Stats"]:
            for p in block["PlayersStats"] or []:
                mins = str(p.get("Minutes") or "0:00")
                mm, _, ss = mins.partition(":")
                sec = int(mm) * 60 + int(ss) if mm.isdigit() and ss.isdigit() else 0
                pm = p.get("Plusminus")
                rows.append(
                    (
                        int(gid),
                        season,
                        p["Player_ID"].strip(),
                        p["Team"].strip(),
                        sec,
                        float(pm) if pm is not None else np.nan,
                        int(p.get("Assistances") or 0),
                        str(p.get("Player") or "").strip(),
                    )
                )
    return pd.DataFrame(rows, columns=["gid", "season", "pid", "team", "sec", "pm", "ast", "name"])


def link_variants(EV: pd.DataFrame) -> pd.DataFrame:
    """Per AS row: make number linked under each rule (a = drafted, b = AS before its make,
    c = same team within 2 events or same clock second, nearest first). -1 = unlinked."""
    rows: list[tuple] = []
    for gid, ev in EV.groupby("gid", sort=False):
        pt = ev["pt"].to_numpy()
        team = ev["team"].to_numpy()
        per = ev["period"].to_numpy()
        clk = ev["clock"].to_numpy()
        num = ev["num"].to_numpy()
        pid = ev["pid"].to_numpy()
        season = int(ev["season"].iloc[0])
        n = len(pt)
        makes = np.isin(pt, wp.FG_MAKE)
        last = -1
        cur = -1
        for i in range(n):
            if per[i] != cur:
                cur, last = per[i], -1
            if pt[i] == "AS":
                a = last if (last >= 0 and team[last] == team[i]) else -1
                b = -1
                if a < 0:
                    nx = wp._next_make(pt, per, i)
                    if nx >= 0 and team[nx] == team[i] and clk[nx] == clk[i]:
                        b = nx
                c = -1
                if a < 0:
                    best: tuple[int, int] | None = None
                    for j in range(max(0, i - 10), min(n, i + 11)):
                        if j == i or not makes[j] or per[j] != per[i] or team[j] != team[i]:
                            continue
                        dp = abs(j - i)
                        if (dp <= 2 or clk[j] == clk[i]) and (best is None or dp < best[0]):
                            best = (dp, j)
                    if best is not None:
                        c = best[1]

                rows.append(
                    (
                        gid,
                        season,
                        team[i],
                        pid[i],
                        int(num[a]) if a >= 0 else -1,
                        int(num[b]) if b >= 0 else -1,
                        int(num[c]) if c >= 0 else -1,
                        float(clk[i]),
                    )
                )
            if makes[i]:
                last = i
    return pd.DataFrame(rows, columns=["gid", "season", "team", "pid", "a", "b", "c", "clock"])


def variant_nums(df: pd.DataFrame) -> dict[str, np.ndarray]:
    a = df["a"].to_numpy()
    b = df["b"].to_numpy()
    c = df["c"].to_numpy()
    ab = np.where(a >= 0, a, b)
    ac = np.where(a >= 0, a, c)
    abc = np.where(ab >= 0, ab, c)
    return {VARIANTS[0]: a, VARIANTS[1]: ab, VARIANTS[2]: ac, VARIANTS[3]: abc}


def linkage_report(df: pd.DataFrame, box_team: pd.DataFrame) -> dict[str, Any]:
    res: dict[str, Any] = {}
    seasons = df["season"].to_numpy()
    for name, arr in variant_nums(df).items():
        ok = arr >= 0
        lk = df[ok].assign(make_num=arr[ok]).groupby(["gid", "team"]).size().rename("n")
        bx = box_team.merge(lk.reset_index(), on=["gid", "team"], how="left")
        bx["n"] = bx["n"].fillna(0)
        bx["exact"] = bx["n"] == bx["box_ast"]
        per_season = {}
        for s, g in bx.groupby("season"):
            per_season[str(int(s))] = {
                "as_rows_linked_share": float(ok[seasons == s].mean()),
                "team_game_exact": float(g["exact"].mean()),
                "linked_over_box": float(g["n"].sum() / max(g["box_ast"].sum(), 1)),
            }
        dup = int(df[ok].assign(m=arr[ok]).duplicated(["gid", "m"]).sum())
        res[name] = {
            "as_rows_linked_share": float(ok.mean()),
            "linked_total": int(bx["n"].sum()),
            "box_total": int(bx["box_ast"].sum()),
            "linked_over_box": float(bx["n"].sum() / bx["box_ast"].sum()),
            "team_game_exact_agreement": float(bx["exact"].mean()),
            "team_games": len(bx),
            "make_linked_by_more_than_one_AS": dup,
            "per_season": per_season,
        }
    chosen = max(res, key=lambda k: res[k]["team_game_exact_agreement"])
    return {
        "variants": res,
        "chosen_rule": chosen,
        "choice_rule": "highest team-game exact agreement with box-score assists",
    }


def credits_base(d: wp.Data) -> pd.DataFrame:
    """Per included play: event-only WP change at the same clock, signed for the actor's team."""
    # Plays from 2007-2009 are not used: predictor seasons start in 2010, and the fold scale
    # for a season needs earlier seasons to fit on.
    EV = d.EV[d.EV["season"].isin(wp.EVAL_SEASONS)]
    G = d.G.set_index("gid")
    s_fold = wp.fold_scales(d.G)
    gid = EV["gid"].to_numpy()
    season = EV["season"].to_numpy()
    diff = EV["gid"].map(G["diff"]).to_numpy(float)
    mu = diff / np.array([s_fold[int(s)] for s in season])
    p_pre = EV["gid"].map(G["p_pre"]).to_numpy(float)
    g_gap = p_pre - ndtr(mu / 11.0)  # tip-off gap: P_pre minus the closed-form value at t=2400, m=0
    t = EV["t"].to_numpy(float)
    m_after = EV["m"].to_numpy(float)
    # Score before a play = carried margin after the previous play in the game (0-0 at the start).
    m_before = pd.Series(m_after).groupby(gid).shift(1).fillna(0.0).to_numpy()
    ot = EV["ot"].to_numpy(float)
    tf = t / 2400.0
    tf_gap = np.where(ot == 1, 0.0, tf)  # section 7 intent: the gap is gone in OT

    def line(mm: np.ndarray) -> np.ndarray:
        # Same clock on both sides: time passage cancels, only the score change is credited.
        base = ndtr((mm + mu * tf) / (11.0 * np.sqrt(np.maximum(t, 60.0) / 2400.0)))
        return np.clip(base + g_gap * tf_gap, 0.001, 0.999)

    dwp = line(m_after) - line(m_before)
    home_code = EV["gid"].map(G["home"]).to_numpy()
    sign = np.where(EV["team"].to_numpy() == home_code, 1.0, -1.0)
    out = pd.DataFrame(
        {
            "gid": gid,
            "season": season,
            "pid": EV["pid"].to_numpy(),
            "pt": EV["pt"].to_numpy(),
            "num": EV["num"].to_numpy(),
            "wpa": 100.0 * sign * dwp,
        }
    )
    keep = ~out["pt"].isin((*wp.MARKERS, *SUB_CODES)) & (out["pid"] != "")
    return out.loc[keep].reset_index(drop=True)


def stints_net(d: wp.Data, duck: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, float]:
    """Per included game and player: on-court point margin and possessions (mart stints)."""
    st = duck.sql(
        """select game_id, season, home_players, away_players, home_points, away_points,
                  home_poss, away_poss
           from stints where season between 2011 and 2022 and game_id like 'E%'"""
    ).df()
    gid_of = d.G.set_index("game_id")["gid"]
    included = set(d.meta.loc[d.meta["reason"].isna(), "gid"].astype(int))
    st = st[st["game_id"].isin(gid_of.index)].copy()
    st["gid"] = st["game_id"].map(gid_of).astype(int)
    st = st[st["gid"].isin(included)]
    # Points check: stint points should sum to the final score of the game.
    tot = st.groupby("gid")[["home_points", "away_points"]].sum()
    final = d.G.set_index("gid").loc[tot.index, ["home_score", "away_score"]]
    check = float(
        (
            (tot["home_points"].to_numpy() == final["home_score"].to_numpy())
            & (tot["away_points"].to_numpy() == final["away_score"].to_numpy())
        ).mean()
    )
    h = st[["gid", "season", "home_players", "home_points", "away_points", "home_poss"]].explode(
        "home_players"
    )
    h = h.rename(
        columns={
            "home_players": "pid",
            "home_points": "pf",
            "away_points": "pa",
            "home_poss": "poss",
        }
    )
    h["net"] = h["pf"] - h["pa"]
    a = st[["gid", "season", "away_players", "home_points", "away_points", "away_poss"]].explode(
        "away_players"
    )
    a = a.rename(
        columns={
            "away_players": "pid",
            "home_points": "pa",
            "away_points": "pf",
            "away_poss": "poss",
        }
    )
    a["net"] = a["pf"] - a["pa"]
    allp = pd.concat(
        [h[["gid", "season", "pid", "net", "poss"]], a[["gid", "season", "pid", "net", "poss"]]]
    )
    return allp.groupby(["gid", "season", "pid"], as_index=False)[["net", "poss"]].sum(), check


def rapm_targets() -> dict[tuple[str, int], float]:
    data = json.loads(RAPM_PATH.read_text(encoding="utf-8"))
    out: dict[tuple[str, int], float] = {}
    for s_key, block in data["seasons"].items():
        s = int(s_key)
        if not (wp.SEASONS[0] <= s <= wp.SEASONS[-1]):
            continue  # seasons outside 2007-2022 are never used
        for p in block["players"]:
            out[(p["player_id"].strip(), s)] = float(p["total"])
    return out


# ----------------------------------------------------------------------------- stages


def stage_linkage(d: wp.Data) -> None:
    box_team = d.box.rename(columns={"box_ast": "box_ast"})
    df = link_variants(d.EV)
    rep = linkage_report(df, box_team)
    merge_report({"linkage": rep})
    print("linkage chosen:", rep["chosen_rule"])
    for k, v in rep["variants"].items():
        print(
            k,
            round(v["team_game_exact_agreement"], 4),
            round(v["linked_over_box"], 4),
            round(v["as_rows_linked_share"], 4),
        )


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    if np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    return pearson(rankdata(x), rankdata(y))


def stage_measure(d: wp.Data, duck: duckdb.DuckDBPyConnection) -> None:  # noqa: PLR0912, PLR0915
    t0 = time.time()
    block = json.loads(wp.REPORT.read_text(encoding="utf-8"))["T1c_measured_split"]
    chosen = block["linkage"]["chosen_rule"]
    as_df = link_variants(d.EV)
    nums = variant_nums(as_df)[chosen]
    sel = nums >= 0
    links = pd.DataFrame(
        {
            "gid": as_df["gid"].to_numpy()[sel],
            "num": nums[sel],
            "passer": as_df["pid"].to_numpy()[sel],
        }
    ).drop_duplicates(["gid", "num"])

    cred = credits_base(d)
    m = cred.merge(links, on=["gid", "num"], how="left", validate="many_to_one")
    is_make = m["pt"].isin(wp.FG_MAKE).to_numpy()
    linked = (m["passer"].notna() & is_make).to_numpy()
    W = m["wpa"].to_numpy(float)
    bx = box_players_cache(d)
    keys = bx[["pid", "season"]].drop_duplicates().reset_index(drop=True)
    keys["k"] = np.arange(len(keys))
    gids = np.sort(d.meta.loc[d.meta["reason"].isna(), "gid"].to_numpy().astype(int))
    gpos = {g: i for i, g in enumerate(gids)}
    kmap = {(p, s): k for p, s, k in zip(keys["pid"], keys["season"], keys["k"], strict=True)}
    n_g, n_k = len(gids), len(keys)

    def mat(rows_g: np.ndarray, rows_k: np.ndarray, vals: np.ndarray) -> Any:
        return coo_matrix((vals, (rows_g, rows_k)), shape=(n_g, n_k)).tocsr()

    # Per-play credit arrays with the key index of the actor (or passer).
    actor_k = np.array(
        [kmap.get((p, int(s)), -1) for p, s in zip(m["pid"], m["season"], strict=True)]
    )
    pass_k = np.array(
        [
            kmap.get((p, int(s)), -1) if isinstance(p, str) else -1
            for p, s in zip(m["passer"], m["season"], strict=True)
        ]
    )
    gi = np.array([gpos[int(g)] for g in m["gid"]])
    unknown_actor = int((actor_k < 0).sum())
    mats_wpa: dict[float, Any] = {}
    for S in S_GRID:
        val_scorer = W - S * W * linked
        ok = actor_k >= 0
        mats_wpa[S] = mat(gi[ok], actor_k[ok], val_scorer[ok])
        pl = linked & (pass_k >= 0)
        mats_wpa[S] = mats_wpa[S] + mat(gi[pl], pass_k[pl], S * W[pl])
    bi = np.array([gpos[int(g)] for g in bx["gid"]])
    bk = np.array([kmap[(p, int(s))] for p, s in zip(bx["pid"], bx["season"], strict=True)])
    mat_min = mat(bi, bk, bx["sec"].to_numpy(float) / 60.0)
    mat_pm = mat(bi, bk, np.nan_to_num(bx["pm"].to_numpy(float)))
    net, check = stints_net(d, duck)
    ni = np.array([gpos[int(g)] for g in net["gid"]])
    nk = np.array(
        [kmap.get((p, int(s)), -1) for p, s in zip(net["pid"], net["season"], strict=True)]
    )
    ok = nk >= 0
    mat_net = mat(ni[ok], nk[ok], net["net"].to_numpy(float)[ok])
    mat_poss = mat(ni[ok], nk[ok], net["poss"].to_numpy(float)[ok])

    # Criterion sample (observed minutes, fixed through the bootstrap).
    minutes = pd.Series(np.asarray(mat_min.sum(axis=0)).ravel(), index=keys.index)
    keys["min"] = minutes.to_numpy()
    rap = rapm_targets()
    sample_idx: list[int] = []
    next_idx: list[int] = []
    for k, (p, s) in enumerate(zip(keys["pid"], keys["season"], strict=True)):
        if s not in CRITERION_SEASONS:
            continue
        nxt = kmap.get((p, s + 1))
        if nxt is None:
            continue
        if keys.loc[k, "min"] < MIN_MINUTES or keys.loc[nxt, "min"] < MIN_MINUTES:
            continue
        sample_idx.append(k)
        next_idx.append(nxt)
    sidx = np.array(sample_idx)
    nidx = np.array(next_idx)
    pid_next = keys.loc[nidx, "pid"].to_numpy()
    season_next = keys.loc[sidx, "season"].to_numpy() + 1
    rapm_y = np.array(
        [rap.get((p, int(s)), np.nan) for p, s in zip(pid_next, season_next, strict=True)]
    )
    rapm_ok = ~np.isnan(rapm_y)

    def sample_stats(w: np.ndarray) -> dict[str, np.ndarray]:
        out: dict[str, np.ndarray] = {}
        vec_min = np.asarray(mat_min.T @ w).ravel()
        vec_pm = np.asarray(mat_pm.T @ w).ravel()
        vec_net = np.asarray(mat_net.T @ w).ravel()
        vec_poss = np.asarray(mat_poss.T @ w).ravel()
        mins_s = vec_min[sidx]
        out["ref_pm"] = 40.0 * vec_pm[sidx] / mins_s
        out["target_net"] = (
            100.0 * vec_net[nidx] / np.where(vec_poss[nidx] > 0, vec_poss[nidx], np.nan)
        )
        for S in S_GRID:
            vec_w = np.asarray(mats_wpa[S].T @ w).ravel()
            out[f"wpa_{S}"] = 40.0 * vec_w[sidx] / mins_s
        return out

    ones = np.ones(n_g)
    point = sample_stats(ones)
    poss_ok = ~np.isnan(point["target_net"])
    target_sets = {
        "net_rating_next_season": (poss_ok, "target_net"),
        "rapm_next_season": (rapm_ok, None),
    }

    def corr_block(stats: dict[str, np.ndarray]) -> dict[str, dict[str, dict[str, float]]]:
        res: dict[str, dict[str, dict[str, float]]] = {}
        for tname, (mask, key) in target_sets.items():
            y = stats[key][mask] if key else rapm_y[mask]
            res[tname] = {}
            for pname in [f"wpa_{S}" for S in S_GRID] + ["ref_pm"]:
                x = stats[pname][mask]
                res[tname][pname] = {"pearson": pearson(x, y), "spearman": spearman(x, y)}
        return res

    # Validity gate first: same-season WPA per 40 vs plus-minus per 40, S = 0 (pre-declared).
    gate_point = pearson(point["wpa_0.0"], point["ref_pm"])
    gate_rng = np.random.default_rng(SEED)
    gate_boot = np.empty(N_BOOT)
    for b in range(N_BOOT):
        wg = np.bincount(gate_rng.integers(0, n_g, n_g), minlength=n_g).astype(float)
        sg = sample_stats(wg)
        gate_boot[b] = pearson(sg["wpa_0.0"], sg["ref_pm"])
    gate_ci = [float(np.nanpercentile(gate_boot, 2.5)), float(np.nanpercentile(gate_boot, 97.5))]
    gate = {
        "same_season_pearson_wpa0_vs_pm40": gate_point,
        "ci95": gate_ci,
        "rule": "point > 0.3 and CI lower bound > 0",
        "passed": bool(gate_point > 0.3 and gate_ci[0] > 0),
        "sample_n": len(sidx),
    }
    if not gate["passed"]:
        merge_report(
            {
                "credit_definition": CREDIT_DEF,
                "validity_gate": gate,
                "measure": {"stopped_at_gate": True, "validity_gate": gate},
            }
        )
        print("VALIDITY GATE FAILED", gate)
        return

    point_corr = corr_block(point)
    # Bootstrap over games: resample games with replacement, recompute aggregates.
    rng = np.random.default_rng(SEED)
    boot: dict[str, list[float]] = {}
    for _ in range(N_BOOT):
        w = np.bincount(rng.integers(0, n_g, n_g), minlength=n_g).astype(float)
        st_b = sample_stats(w)
        boot.setdefault("diag|ref_pm_mean", []).append(float(np.mean(st_b["ref_pm"])))
        boot.setdefault("diag|wpa0_mean", []).append(float(np.mean(st_b["wpa_0.0"])))
        boot.setdefault("diag|net_mean", []).append(float(np.nanmean(st_b["target_net"])))
        bc = corr_block(st_b)
        for tname in bc:
            for pname in bc[tname]:
                for met in ("pearson", "spearman"):
                    boot.setdefault(f"{tname}|{pname}|{met}", []).append(bc[tname][pname][met])

    def ci(name: str) -> list[float]:
        arr = np.array(boot[name], dtype=float)
        return [float(np.nanpercentile(arr, 2.5)), float(np.nanpercentile(arr, 97.5))]

    def score_of(corr: dict, pname: str) -> float:
        vals = [(corr[t][pname]["pearson"] + corr[t][pname]["spearman"]) / 2 for t in corr]
        return float(np.mean(vals))

    score_boot: dict[str, np.ndarray] = {}
    for pname in [f"wpa_{S}" for S in S_GRID] + ["ref_pm"]:
        arr = []
        for b in range(N_BOOT):
            parts = []
            for tname in target_sets:
                parts.append(boot[f"{tname}|{pname}|pearson"][b])
                parts.append(boot[f"{tname}|{pname}|spearman"][b])
            arr.append(float(np.mean(parts)))
        score_boot[pname] = np.array(arr)

    scores = {p: score_of(point_corr, p) for p in score_boot}
    score_ci = {
        p: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]
        for p, v in score_boot.items()
    }
    wpa_names = [f"wpa_{S}" for S in S_GRID]
    best = max(wpa_names, key=lambda p: scores[p])
    zero_val = scores["wpa_0.0"]
    all_overlap_zero = all(score_ci[p][0] <= zero_val <= score_ci[p][1] for p in wpa_names)
    if all_overlap_zero:
        lo = score_ci[best][0]
        hi = score_ci[best][1]
        inside = [S for S in S_GRID if lo <= scores[f"wpa_{S}"] <= hi]
        rec_S = min(inside) if inside else float(best.split("_")[1])
        verdict = "cannot separate; smallest S inside best S's CI"
    else:
        rec_S = float(best.split("_")[1])
        verdict = "best S by mean correlation"

    per_target = {}
    for tname in target_sets:
        per_target[tname] = {
            "n": int(target_sets[tname][0].sum()),
            "by_S": {
                pname: {
                    met: {
                        "point": point_corr[tname][pname][met],
                        "ci95": ci(f"{tname}|{pname}|{met}"),
                        "boot_mean": float(np.nanmean(boot[f"{tname}|{pname}|{met}"])),
                    }
                    for met in ("pearson", "spearman")
                }
                for pname in [f"wpa_{S}" for S in S_GRID] + ["ref_pm"]
            },
        }

    def top10(S: float) -> list[dict[str, Any]]:
        wpa_tot = np.asarray(mats_wpa[S].sum(axis=0)).ravel()
        table = keys.assign(wpa=wpa_tot, minutes=keys["min"].to_numpy())
        table = table[(table["season"] == 2022) & (table["minutes"] >= 500)]
        table = table.sort_values("wpa", ascending=False).head(10)
        names = bx.drop_duplicates("pid").set_index("pid")["name"]
        teams = bx.drop_duplicates(["pid", "season"]).set_index(["pid", "season"])["team"]
        return [
            {
                "player": str(names.get(r.pid, r.pid)),
                "pid": r.pid,
                "team": str(teams.get((r.pid, r.season), "")),
                "minutes": round(float(r.minutes), 1),
                "wpa_total": round(float(r.wpa), 2),
                "wpa_per40": round(40.0 * float(r.wpa) / float(r.minutes), 2),
            }
            for r in table.itertuples(index=False)
        ]

    sanity = {
        "diag_point_vs_boot_mean": {
            "ref_pm_mean_point": float(np.mean(point["ref_pm"])),
            "ref_pm_mean_boot": float(np.mean(boot["diag|ref_pm_mean"])),
            "wpa0_mean_point": float(np.mean(point["wpa_0.0"])),
            "wpa0_mean_boot": float(np.mean(boot["diag|wpa0_mean"])),
            "net_mean_point": float(np.nanmean(point["target_net"])),
            "net_mean_boot": float(np.mean(boot["diag|net_mean"])),
        },
        "same_season_wpa0_vs_pm_pearson": pearson(point["wpa_0.0"], point["ref_pm"]),
        "same_season_wpa0_vs_pm_spearman": spearman(point["wpa_0.0"], point["ref_pm"]),
    }
    result = {
        "credit_definition": CREDIT_DEF,
        "validity_gate": gate,
        "face_validity_2022_top10": {"S_0.0": top10(0.0), f"S_{rec_S}": top10(rec_S)},
        "sanity_check": sanity,
        "criterion_predeclared_in": "docs/models/wp_prestudy.md (T1(c) criterion section)",
        "linkage_rule_used": chosen,
        "sample": {
            "player_seasons_min500_both_seasons": len(sidx),
            "seasons_s": list(CRITERION_SEASONS),
            "target_season_coverage_note": "2016 games with ND clocks excluded (as in all splits)",
        },
        "stints_points_check_share_games": check,
        "unknown_actor_credit_rows": unknown_actor,
        "per_target": per_target,
        "score_by_S": {p: {"point": scores[p], "ci95": score_ci[p]} for p in scores},
        "best_S_by_score": float(best.split("_")[1]) if best.startswith("wpa") else None,
        "all_S_ci_overlap_S0": bool(all_overlap_zero),
        "recommended_S": rec_S,
        "verdict": verdict,
        "bootstrap": {
            "resamples": N_BOOT,
            "seed": SEED,
            "unit": "game (whole games)",
            "note": "criterion sample fixed to observed >=500-min player-seasons; "
            "RAPM target fixed (not refit per resample)",
        },
        "runtime_seconds_measure": round(time.time() - t0, 1),
    }
    merge_report({"measure": result})
    print("measure done", result["recommended_S"], result["verdict"])


_BOX_CACHE: dict[str, pd.DataFrame] = {}


def box_players_cache(d: wp.Data) -> pd.DataFrame:
    if "bx" not in _BOX_CACHE:
        _BOX_CACHE["bx"] = box_players(d)
    return _BOX_CACHE["bx"]


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage not in ("linkage", "measure"):
        raise SystemExit("usage: wp_t1c.py linkage|measure")
    t0 = time.time()
    con = duckdb.connect(str(wp.MART), read_only=True)
    games = con.sql(wp.GAMES_SQL).df()
    d = wp.build(games)
    print(f"built in {time.time() - t0:.1f}s")
    if stage == "linkage":
        stage_linkage(d)
    else:
        stage_measure(d, con)
    con.close()
    print(f"total {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
