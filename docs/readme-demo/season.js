// Season: 10,000 simulated seasons for one team (fan chart), then title odds for every team.
window.DURATION = 12;
const D = window.DATA.sim;
const TEAM = "OLY";
const T = D.cum[TEAM];
const ROUNDS = T.p50.length;
const DONE = T.done;
const WMAX = 36;

const A = [0, 8.3];
const B = [7.9, 12];
const FADE = 0.45;
const vis = (t, [a, b]) => seg(t, a, a + FADE) * (1 - seg(t, b - FADE, b));

const finalHist = T.final_hist;
const HMAX = Math.max(...finalHist);

// ---- smooth density image: kernel-smoothed wins distribution per round, interpolated between rounds
const PLOT = { x0: 96, x1: 760, y0: 150, y1: 590 };
const HW = PLOT.x1 - PLOT.x0;
const HH = PLOT.y1 - PLOT.y0;
const PXW = HH / WMAX;
const LUT = (() => {
  const out = [];
  for (let i = 0; i < 256; i++) out.push(rampAt(0.1 + 0.9 * (i / 255)).match(/\d+/g).map(Number));
  return out;
})();
const HEAT = (() => {
  const rows = [];
  for (let r = 1; r <= ROUNDS; r++) {
    const col = T.density[r - 1];
    const h = new Float32Array(HH);
    let top = 0;
    for (let yi = 0; yi < HH; yi++) {
      const ww = yi / PXW;
      let v = 0;
      for (let w = Math.max(0, Math.floor(ww - 3)); w <= Math.min(col.length - 1, Math.ceil(ww + 3)); w++) {
        v += col[w] * Math.exp(-0.5 * ((ww - w) / 0.55) ** 2);
      }
      h[yi] = v;
      if (v > top) top = v;
    }
    for (let yi = 0; yi < HH; yi++) h[yi] = Math.sqrt(h[yi] / top);
    rows.push(h);
  }
  return rows;
})();
const heatCanvas = document.createElement("canvas");
heatCanvas.width = HW;
heatCanvas.height = HH;
function paintHeat(reach) {
  const hctx = heatCanvas.getContext("2d");
  const img = hctx.createImageData(HW, HH);
  const d = img.data;
  for (let xi = 0; xi < HW; xi++) {
    const r = 1 + (xi / HW) * (ROUNDS - 1);
    if (r < DONE || r > reach) continue;
    const r0 = Math.floor(r);
    const r1 = Math.min(ROUNDS, r0 + 1);
    const fr = r - r0;
    const edge = clamp((reach - r) / 0.6); // soft leading edge while the fan grows
    for (let yi = 0; yi < HH; yi++) {
      const v = HEAT[r0 - 1][yi] * (1 - fr) + HEAT[r1 - 1][yi] * fr;
      if (v < 0.04) continue;
      const c = LUT[Math.min(255, Math.round(v * 255))];
      const o = ((HH - 1 - yi) * HW + xi) * 4;
      d[o] = c[0];
      d[o + 1] = c[1];
      d[o + 2] = c[2];
      d[o + 3] = Math.min(255, v * 1.5 * 255) * edge;
    }
  }
  hctx.putImageData(img, 0, 0);
}

function fan(ctx, t, alpha) {
  const k = t - A[0];
  const [x0, x1, y0, y1] = [96, 760, 150, 590];
  const [hx0, hx1] = [800, 1140];
  const px = (r) => lerp(x0, x1, (r - 1) / (ROUNDS - 1));
  const py = (w) => lerp(y1, y0, w / WMAX);
  ctx.save();
  ctx.globalAlpha = alpha;

  text(ctx, "10,000 simulated seasons", 56, 74, { size: 30, weight: 620, alpha });
  text(ctx, `${D.names[TEAM]}. White: the real record. Orange: every way the rest of the season can go.`, 56, 104, { size: 16, color: C.muted, alpha });

  // grid
  ctx.lineWidth = 1;
  for (let w = 0; w <= 35; w += 5) {
    ctx.strokeStyle = w === 0 ? C.ruleStrong : C.rule;
    ctx.beginPath();
    ctx.moveTo(x0, py(w));
    ctx.lineTo(hx1, py(w));
    ctx.stroke();
    text(ctx, String(w), x0 - 12, py(w) + 4, { size: 12, color: C.muted, align: "right" });
  }
  for (const r of [1, 10, 20, 30, 38]) {
    text(ctx, String(r), px(r), y1 + 24, { size: 12, color: C.muted, align: "center" });
  }
  text(ctx, "Round", (x0 + x1) / 2, y1 + 48, { size: 13, color: C.soft, align: "center" });
  text(ctx, "Wins", x0 - 12, y0 - 14, { size: 13, color: C.soft, align: "right" });

  // density fan: shaded by the share of the 10,000 seasons that sit at each number of wins
  const g = easeInOut(seg(k, 1.0, 4.6));
  const reach = DONE + g * (ROUNDS - DONE);
  paintHeat(reach);
  ctx.globalAlpha = alpha;
  ctx.drawImage(heatCanvas, x0, y0);
  // a few of the simulated seasons as thin paths, so the 10,000 futures stay visible
  ctx.lineWidth = 1;
  ctx.strokeStyle = "rgba(248,201,162,0.28)";
  for (const path of T.paths) {
    ctx.beginPath();
    ctx.moveTo(px(DONE), py(path[DONE - 1]));
    for (let r = DONE + 1; r <= Math.floor(reach); r++) ctx.lineTo(px(r), py(path[r - 1]));
    ctx.stroke();
  }

  // 10th to 90th percentile band and the median
  const ba = easeOut(seg(k, 4.4, 5.4));
  if (ba > 0) {
    ctx.fillStyle = "rgba(226,105,31,0.16)";
    ctx.beginPath();
    for (let r = DONE; r <= ROUNDS; r++) ctx.lineTo(px(r), py(lerp(T.p50[r - 1], T.p90[r - 1], ba)));
    for (let r = ROUNDS; r >= DONE; r--) ctx.lineTo(px(r), py(lerp(T.p50[r - 1], T.p10[r - 1], ba)));
    ctx.closePath();
    ctx.fill();
    ctx.save();
    ctx.setLineDash([6, 5]);
    ctx.lineWidth = 1.5;
    for (const [arr, c] of [[T.p10, C.soft], [T.p50, C.ink], [T.p90, C.soft]]) {
      ctx.strokeStyle = c;
      ctx.globalAlpha = alpha * ba;
      ctx.beginPath();
      for (let r = DONE; r <= ROUNDS; r++) {
        const y = py(lerp(T.p50[r - 1], arr[r - 1], ba));
        r === DONE ? ctx.moveTo(px(r), y) : ctx.lineTo(px(r), y);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  // the real record so far
  const rr = easeInOut(seg(k, 0.1, 1.1));
  ctx.strokeStyle = C.ink;
  ctx.lineWidth = 3;
  ctx.lineJoin = "round";
  ctx.beginPath();
  const upto = Math.max(1, Math.floor(rr * DONE));
  for (let r = 1; r <= upto; r++) {
    const y = py(T.real[r - 1]);
    r === 1 ? ctx.moveTo(px(r), y) : ctx.lineTo(px(r), y);
  }
  ctx.stroke();
  if (rr > 0.95) {
    ctx.fillStyle = C.ink;
    ctx.beginPath();
    ctx.arc(px(DONE), py(T.real[DONE - 1]), 6, 0, 7);
    ctx.fill();
  }

  // histogram of final wins (right panel, same wins axis)
  const hg = easeOut(seg(k, 3.2, 5.0));
  const span = (y1 - y0) / WMAX;
  for (let w = 0; w < finalHist.length; w++) {
    const len = (finalHist[w] / HMAX) * (hx1 - hx0) * hg;
    if (len < 0.5) continue;
    ctx.fillStyle = "rgba(226,105,31,0.85)";
    ctx.fillRect(hx0, py(w) - span + 0.5, len, span - 1);
  }
  text(ctx, "Final wins", hx0, y0 - 14, { size: 13, color: C.soft });

  // readouts
  const n = Math.round(g * 10000);
  text(ctx, "Simulated seasons", 120, 196, { size: 13, color: C.muted, alpha });
  text(ctx, n.toLocaleString("en-US"), 120, 240, { size: 44, weight: 640, alpha });
  const ra = easeOut(seg(k, 5.4, 6.2));
  const direct = Math.round(D.p_direct[TEAM] * 100);
  const title = (D.p_title[TEAM] * 100).toFixed(1);
  text(ctx, `Expected wins  ${D.exp_wins[TEAM].toFixed(1)}`, 120, 286, { size: 18, weight: 560, color: C.soft, alpha: alpha * ra });
  text(ctx, `Top 6 finish  ${direct}%`, 120, 314, { size: 18, weight: 560, color: C.soft, alpha: alpha * ra });
  text(ctx, `Title  ${title}%`, 120, 342, { size: 18, weight: 620, color: C.orange, alpha: alpha * ra });
  ctx.restore();
}

function board(ctx, t, alpha) {
  const k = t - B[0];
  text(ctx, "Title odds, every team", 56, 74, { size: 30, weight: 620, alpha });
  text(ctx, `Each team gets its own 10,000 seasons from the same model. Round ${D.after_round}.`, 56, 104, { size: 16, color: C.muted, alpha });
  const rows = Object.entries(D.p_title).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const top = rows[0][1];
  const [lx, bx, bw, y0, step] = [56, 330, 740, 160, 56];
  rows.forEach(([team, p], i) => {
    const y = y0 + i * step;
    const a = easeOut(seg(k, 0.5 + i * 0.12, 1.2 + i * 0.12));
    text(ctx, D.display[team], lx, y + 26, { size: 22, weight: 620, alpha: alpha * a });
    text(ctx, D.names[team], lx + 70, y + 26, { size: 16, color: C.muted, alpha: alpha * a });
    ctx.save();
    ctx.globalAlpha = alpha * a;
    ctx.fillStyle = C.panel;
    ctx.fillRect(bx, y + 6, bw, 28);
    ctx.fillStyle = i === 0 ? C.orange : "rgba(226,105,31,0.6)";
    ctx.fillRect(bx, y + 6, (p / (top * 1.15)) * bw * a, 28);
    ctx.restore();
    text(ctx, `${(p * 100).toFixed(1)}%`, bx + (p / (top * 1.15)) * bw * a + 12, y + 27, { size: 17, weight: 600, alpha: alpha * a });
  });
}

start((ctx, t) => {
  text(ctx, "675hoops.com", W - 40, H - 22, { size: 13, color: C.muted, align: "right", alpha: 0.7 });
  const a = vis(t, A);
  const b = vis(t, B);
  if (a > 0) fan(ctx, t, a);
  if (b > 0) board(ctx, t, b);
});
