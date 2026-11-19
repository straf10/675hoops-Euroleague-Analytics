// Pipeline: the six daily steps, each with a small visual built from real sizes in the repository.
window.DURATION = 15;
const P = window.DATA.pipeline;
const REC = window.DATA.record;

const STEPS = [
  ["Ingest", "Every EuroLeague response is saved once. The run never asks for it again."],
  ["Build", "Each table is checked, then loaded into DuckDB. Everything after this reads the marts."],
  ["Backtest", "Replay past seasons in order. Pick settings on earlier seasons, then score later ones."],
  ["Predict", "Each model forecasts every game that starts within 48 hours."],
  ["Score", "Forecasts meet results. Log loss, Brier score and calibration measure every model."],
  ["Publish", "The site data is rebuilt. The Astro site goes live on Cloudflare."],
];
const T0 = 1.2; // first stage starts
const LEN = 2.0; // seconds per stage
const FADE = 0.3;
const stageOf = (t) => Math.floor((t - T0) / LEN);

// ---- persistent frame: title and the six-step strip
function frame(ctx, t) {
  text(ctx, "From raw data to a published forecast", 56, 74, { size: 30, weight: 620 });
  text(ctx, "The daily run, step by step. Sizes are from this repository.", 56, 104, { size: 16, color: C.muted });
  const gap = 30;
  const cw = (1088 - gap * 5) / 6;
  const active = stageOf(t);
  const intro = easeOut(seg(t, 0.2, 1.0));
  STEPS.forEach(([name], i) => {
    const x = 56 + i * (cw + gap);
    const y = 140;
    const state = t >= T0 + LEN * 6 ? "done" : i < active ? "done" : i === active ? "active" : "pending";
    ctx.save();
    ctx.globalAlpha = intro;
    ctx.beginPath();
    ctx.roundRect(x, y, cw, 42, 8);
    if (state === "active") {
      ctx.fillStyle = C.orange;
      ctx.fill();
    } else {
      ctx.strokeStyle = state === "done" ? C.orange : C.ruleStrong;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    text(ctx, name, x + cw / 2, y + 27, {
      size: 16,
      weight: 620,
      align: "center",
      color: state === "active" ? C.bg : state === "done" ? C.ink : C.muted,
    });
    if (i < 5) {
      ctx.strokeStyle = i < active || state === "done" ? C.orange : C.ruleStrong;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x + cw + 8, y + 21);
      ctx.lineTo(x + cw + gap - 8, y + 21);
      ctx.stroke();
    }
    ctx.restore();
  });
}

// ---- stage visuals; u = seconds into the stage (0..LEN), a = fade
function ingest(ctx, u, a) {
  const [ax, ay, aw, ah] = [470, 330, 150, 110];
  const [cx, cy, cw, ch] = [820, 270, 324, 230];
  ctx.save();
  ctx.globalAlpha = a;
  ctx.strokeStyle = C.ruleStrong;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.roundRect(ax, ay, aw, ah, 10);
  ctx.stroke();
  text(ctx, "EuroLeague API", ax + aw / 2, ay + ah / 2 + 5, { size: 15, weight: 600, align: "center", color: C.soft });
  ctx.beginPath();
  ctx.roundRect(cx, cy, cw, ch, 10);
  ctx.stroke();
  text(ctx, "Local cache", cx, cy - 12, { size: 13, color: C.muted });
  // cache fills cell by cell
  const [cols, rows] = [18, 10];
  const total = cols * rows;
  const fill = easeOut(seg(u, 0.2, 1.7));
  const cell = (cw - 24) / cols;
  for (let n = 0; n < total; n++) {
    if (n / total > fill) break;
    const [c, r] = [n % cols, Math.floor(n / cols)];
    ctx.fillStyle = n / total > fill - 0.06 ? C.ink : "rgba(226,105,31,0.85)";
    ctx.fillRect(cx + 12 + c * cell + 1, cy + 12 + r * ((ch - 24) / rows) + 1, cell - 2, (ch - 24) / rows - 2);
  }
  // packets in flight
  for (let k = 0; k < 6; k++) {
    const f = ((u * 1.6 + k / 6) % 1);
    const x = lerp(ax + aw + 8, cx - 8, f);
    const y = lerp(ay + ah / 2, cy + ch / 2, f) + Math.sin(k * 2.3) * 14;
    ctx.fillStyle = C.orange;
    ctx.globalAlpha = a * (1 - Math.abs(f - 0.5) * 0.9);
    ctx.fillRect(x - 6, y - 4, 12, 8);
  }
  ctx.globalAlpha = a;
  text(ctx, fmtInt(P.raw_files * fill), cx, cy + ch + 46, { size: 40, weight: 640 });
  text(ctx, "responses saved", cx, cy + ch + 70, { size: 15, color: C.soft });
  ctx.restore();
}

function build(ctx, u, a) {
  const rows = [
    ["Games", P.games],
    ["Shots", P.shots],
    ["Lineup stints", P.stints],
  ];
  ctx.save();
  text(ctx, "Checked tables", 470, 250, { size: 13, color: C.muted, alpha: a });
  text(ctx, "DuckDB marts", 880, 250, { size: 13, color: C.muted, alpha: a });
  rows.forEach(([label, n], i) => {
    const y = 290 + i * 100;
    const k = easeOut(seg(u, 0.1 + i * 0.35, 1.0 + i * 0.35));
    ctx.globalAlpha = a;
    text(ctx, label, 470, y + 26, { size: 20, weight: 600 });
    // rows stream through the check, left to right
    ctx.strokeStyle = C.rule;
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.moveTo(640, y + 20);
    ctx.lineTo(850, y + 20);
    ctx.stroke();
    ctx.strokeStyle = C.orange;
    ctx.beginPath();
    ctx.moveTo(640, y + 20);
    ctx.lineTo(640 + 210 * k, y + 20);
    ctx.stroke();
    if (k > 0.98) {
      ctx.strokeStyle = C.up;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(858, y + 20);
      ctx.lineTo(866, y + 28);
      ctx.lineTo(880, y + 10);
      ctx.stroke();
    }
    text(ctx, fmtInt(n * k), 900, y + 32, { size: 36, weight: 640, alpha: a });
  });
  text(ctx, "Each table passes a schema check (pandera) before it is loaded.", 470, 600, { size: 14, color: C.muted, alpha: a });
  ctx.restore();
}

function backtest(ctx, u, a) {
  const [s0, s1] = [P.seasons[0], P.live_season];
  const n = s1 - s0 + 1;
  const [x0, x1, y0] = [470, 1130, 330];
  const bw = (x1 - x0) / n;
  const spans = [
    ["Warm-up", P.split.warmup, C.ruleStrong, C.soft],
    ["Tuning", P.split.tuning, "#6a6862", C.ink],
    ["Check", P.split.validation, C.blue, C.ink],
    ["Test", P.split.test, C.orange, C.ink],
    ["Live", [P.live_season, P.live_season], C.ink, C.bg],
  ];
  ctx.save();
  ctx.globalAlpha = a;
  const reveal = easeOut(seg(u, 0.0, 0.9)) * n;
  for (let i = 0; i < n; i++) {
    if (i > reveal) break;
    const yr = s0 + i;
    const sp = spans.find(([, [lo, hi]]) => yr >= lo && yr <= hi);
    ctx.fillStyle = sp ? sp[2] : C.ruleStrong;
    ctx.fillRect(x0 + i * bw + 1, y0, bw - 2, 46);
  }
  spans.forEach(([name, [lo, hi], , ]) => {
    const xa = x0 + (lo - s0) * bw;
    const xb = x0 + (hi - s0 + 1) * bw;
    if ((hi - s0) > reveal) return;
    text(ctx, name, (xa + xb) / 2, y0 + 72, { size: 14, weight: 600, align: "center", color: C.soft });
    text(ctx, lo === hi ? `${lo}` : `${lo}-${String(hi).slice(2)}`, (xa + xb) / 2, y0 + 92, { size: 12, color: C.muted, align: "center" });
  });
  // walk-forward pointer across the tuning seasons: learn from the past, score the next season
  const [ta, tb] = P.split.tuning;
  const walk = seg(u, 0.9, 1.8);
  if (walk > 0) {
    const cur = ta + Math.min(tb - ta, Math.floor(walk * (tb - ta + 1)));
    const xl = x0;
    const xr = x0 + (cur - s0) * bw;
    ctx.strokeStyle = C.soft;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(xl, y0 - 14);
    ctx.lineTo(xr, y0 - 14);
    ctx.stroke();
    ctx.fillStyle = C.ink;
    ctx.fillRect(x0 + (cur - s0) * bw + 1, y0 - 24, bw - 2, 8);
    text(ctx, "learn from earlier seasons", xl, y0 - 34, { size: 13, color: C.soft });
    text(ctx, `score ${cur}`, Math.min(xr + bw + 6, x1 - 60), y0 - 34, { size: 13, weight: 620, color: C.ink });
  }
  const ga = easeOut(seg(u, 1.5, 2.0));
  text(ctx, `Elo tries ${P.elo_grid} settings. M1 tries ${P.m1_grid}.`, 470, 520, { size: 18, weight: 600, alpha: a * ga });
  text(ctx, "The best settings are fixed before the live season starts.", 470, 548, { size: 15, color: C.soft, alpha: a * ga });
  ctx.restore();
}

function predict(ctx, u, a) {
  const [x0, y0, rowH] = [470, 290, 52];
  const colW = 104;
  ctx.save();
  ctx.globalAlpha = a;
  text(ctx, "Chance that the home side wins", 470, 250, { size: 13, color: C.muted });
  P.models.forEach((m, j) => text(ctx, m, x0 + 130 + j * colW + colW / 2 - 8, y0 - 12, { size: 14, weight: 620, color: C.soft, align: "center" }));
  P.rows.forEach((r, i) => {
    const y = y0 + i * rowH;
    text(ctx, `${r.home} v ${r.away}`, x0, y + 30, { size: 16, weight: 600 });
    P.models.forEach((m, j) => {
      const k = easeOut(seg(u, 0.1 + (i * 5 + j) * 0.045, 0.45 + (i * 5 + j) * 0.045));
      const p = r.p[m];
      const x = x0 + 130 + j * colW;
      ctx.globalAlpha = a * k;
      ctx.fillStyle = C.panel;
      ctx.fillRect(x, y + 8, colW - 16, 34);
      ctx.fillStyle = C.orange;
      ctx.fillRect(x, y + 8, (colW - 16) * p * k, 34);
      text(ctx, `${Math.round(p * 100)}%`, x + 10, y + 31, { size: 16, weight: 620, color: C.ink, alpha: a * k });
    });
  });
  ctx.restore();
}

function score(ctx, u, a) {
  const [x0, x1, y0, y1] = [470, 1100, 280, 520];
  const [lo, hi] = [0.58, 0.76];
  const S = REC.series;
  const n0 = S[0][0];
  const n1 = S[S.length - 1][0];
  const px = (n) => lerp(x0, x1, (n - n0) / (n1 - n0));
  const py = (v) => lerp(y1, y0, (v - lo) / (hi - lo));
  ctx.save();
  ctx.globalAlpha = a;
  text(ctx, `Log loss over the last ${REC.window} games`, x0, 250, { size: 13, color: C.muted });
  ctx.strokeStyle = C.rule;
  ctx.lineWidth = 1;
  for (let v = 0.6; v <= 0.7601; v += 0.04) {
    ctx.beginPath();
    ctx.moveTo(x0, py(v));
    ctx.lineTo(x1, py(v));
    ctx.stroke();
    text(ctx, v.toFixed(2), x0 - 10, py(v) + 4, { size: 12, color: C.muted, align: "right" });
  }
  const g = easeInOut(seg(u, 0.1, 1.5));
  const upto = Math.max(1, Math.floor(g * S.length));
  for (const [col, c, w] of [[2, C.muted, 2], [1, C.orange, 3.5]]) {
    ctx.strokeStyle = c;
    ctx.lineWidth = w;
    ctx.lineJoin = "round";
    ctx.beginPath();
    for (let i = 0; i < upto; i++) (i ? ctx.lineTo(px(S[i][0]), py(S[i][col])) : ctx.moveTo(px(S[i][0]), py(S[i][col])));
    ctx.stroke();
  }
  const ra = easeOut(seg(u, 1.3, 1.9));
  text(ctx, "Log loss", x0, 575, { size: 14, color: C.muted, alpha: a * ra });
  text(ctx, REC.elo.log_loss.toFixed(3), x0 + 100, 580, { size: 28, weight: 640, color: C.orange, alpha: a * ra });
  text(ctx, REC.b0.log_loss.toFixed(3), x0 + 200, 580, { size: 22, weight: 560, color: C.muted, alpha: a * ra });
  text(ctx, "Brier", x0 + 330, 575, { size: 14, color: C.muted, alpha: a * ra });
  text(ctx, REC.elo.brier.toFixed(3), x0 + 400, 580, { size: 28, weight: 640, color: C.orange, alpha: a * ra });
  text(ctx, REC.b0.brier.toFixed(3), x0 + 500, 580, { size: 22, weight: 560, color: C.muted, alpha: a * ra });
  text(ctx, "Elo (orange) against always the home side", x1, 250, { size: 13, color: C.soft, align: "right", alpha: a });
  ctx.restore();
}

function publish(ctx, u, a) {
  const nodes = ["Scores and forecasts", "Site data", "Astro site", "675hoops.com"];
  const [x0, bw, gap, y] = [470, 136, 36, 360];
  ctx.save();
  ctx.globalAlpha = a;
  nodes.forEach((name, i) => {
    const x = x0 + i * (bw + gap);
    const k = easeOut(seg(u, 0.1 + i * 0.35, 0.6 + i * 0.35));
    ctx.globalAlpha = a * k;
    ctx.beginPath();
    ctx.roundRect(x, y, bw, 90, 10);
    if (i === nodes.length - 1) {
      ctx.fillStyle = C.orange;
      ctx.fill();
    } else {
      ctx.strokeStyle = C.orange;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    const lines = wrap(ctx, name, bw - 20, 15, 620);
    lines.forEach((line, n) => {
      text(ctx, line, x + bw / 2, y + 50 + (n - (lines.length - 1) / 2) * 20, { size: 15, weight: 620, align: "center", color: i === nodes.length - 1 ? C.bg : C.ink });
    });
    if (i < nodes.length - 1) {
      ctx.strokeStyle = C.orange;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x + bw + 6, y + 45);
      ctx.lineTo(x + bw + gap - 6, y + 45);
      ctx.stroke();
    }
  });
  text(ctx, "Static site on Cloudflare.", 470, 500, { size: 16, color: C.soft, alpha: a * easeOut(seg(u, 1.3, 1.9)) });
  ctx.restore();
}
const VIS = [ingest, build, backtest, predict, score, publish];

start((ctx, t) => {
  frame(ctx, t);
  text(ctx, "675hoops.com", W - 40, H - 22, { size: 13, color: C.muted, align: "right", alpha: 0.7 });
  const i = stageOf(t);
  const end = T0 + LEN * 6;
  if (i >= 0 && t < end) {
    const u = t - (T0 + i * LEN);
    const a = seg(u, 0, FADE) * (1 - seg(u, LEN - FADE, LEN));
    // caption column
    text(ctx, STEPS[i][0], 56, 262, { size: 34, weight: 640, alpha: a });
    let y = 300;
    for (const line of wrap(ctx, STEPS[i][1], 330, 18)) {
      text(ctx, line, 56, y, { size: 18, color: C.soft, alpha: a });
      y += 28;
    }
    VIS[i](ctx, u, a);
  }
  if (t >= end) {
    const o = easeOut(seg(t, end, end + 0.5)) * (1 - seg(t, window.DURATION - 0.45, window.DURATION));
    text(ctx, "Every day, 05:17 UTC.", 56, 340, { size: 44, weight: 640, alpha: o });
    text(ctx, "A Cloudflare Worker starts the run. It ends with the published site.", 56, 384, { size: 18, color: C.soft, alpha: o });
  }
});
