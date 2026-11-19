// Hero: tune the model (loss surface), check its spread against reality, then call one game.
window.DURATION = 17;
const D = window.DATA;

// ---- beat windows (seconds)
const B1 = [0, 5.6];
const B2 = [5.6, 9.6];
const B3 = [9.6, 17];
const FADE = 0.45;
const vis = (t, [a, b]) => seg(t, a, a + FADE) * (1 - seg(t, b - FADE, b));

function head(ctx, title, sub, alpha) {
  text(ctx, title, 56, 74, { size: 30, weight: 620, alpha });
  text(ctx, sub, 56, 104, { size: 16, color: C.muted, alpha });
}

// ================= beat 1: loss surface =================
const S = D.surface;
const NK = S.k.length;
const NH = S.hca.length;
const zmin = Math.min(...S.z.flat());
const zmax = Math.max(...S.z.flat());
const zn = (i, j) => (S.z[i][j] - zmin) / (zmax - zmin);
const rank = (() => {
  const r = rng(5);
  const m = new Map();
  for (let i = 0; i < NK - 1; i++) {
    for (let j = 0; j < NH - 1; j++) m.set(i * NH + j, 0.8 * (i / NK) + 0.2 * (j / NH) + 0.04 * r());
  }
  return m;
})();

function project(x, y, z, th, ph, sc, cx, cy) {
  const xr = x * Math.cos(th) - y * Math.sin(th);
  const yr = x * Math.sin(th) + y * Math.cos(th);
  return [cx + sc * xr * 1.18, cy + sc * (yr * Math.sin(ph) - z * Math.cos(ph) * 0.95)];
}

function surface(ctx, t, alpha) {
  const k = t - B1[0];
  const spin = easeInOut(seg(k, 0.1, 4.9));
  const th = lerp(0.95, 0, spin); // one steady orbit that ends axis-aligned for the top view
  const flat = easeInOut(seg(k, 3.7, 5.0));
  const ph = lerp(0.56, Math.PI / 2, flat);
  const sc = lerp(215, 245, flat);
  const cx = 790;
  const cy = lerp(405, 372, flat);
  const X = (i) => lerp(-1, 1, i / (NK - 1));
  const Y = (j) => lerp(-1, 1, j / (NH - 1));
  const proj = (x, y, z) => project(x, y, z, th, ph, sc, cx, cy);
  const P = (i, j, lift = 0) => proj(X(i), Y(j), zn(i, j) + lift);
  ctx.save();
  ctx.globalAlpha = alpha;

  // floor outline
  ctx.strokeStyle = C.ruleStrong;
  ctx.lineWidth = 1;
  ctx.beginPath();
  [[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]].forEach(([x, y], n) => {
    const [px, py] = proj(x, y, 0);
    n ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
  });
  ctx.stroke();

  // quads, far to near, lit from the upper left
  const quads = [];
  for (let i = 0; i < NK - 1; i++) {
    for (let j = 0; j < NH - 1; j++) {
      const born = rank.get(i * NH + j) * 2.3 + 0.3;
      const a = easeOut(seg(k, born, born + 0.35));
      if (a <= 0) continue;
      const depth = -(X(i) * Math.sin(th) + Y(j) * Math.cos(th));
      quads.push({ i, j, a, depth });
    }
  }
  quads.sort((p, q) => q.depth - p.depth);
  for (const { i, j, a } of quads) {
    const lift = (1 - a) * 0.35;
    const pts = [P(i, j, lift), P(i + 1, j, lift), P(i + 1, j + 1, lift), P(i, j + 1, lift)];
    const zc = (zn(i, j) + zn(i + 1, j) + zn(i + 1, j + 1) + zn(i, j + 1)) / 4;
    const gx = zn(i + 1, j) - zn(i, j);
    const gy = zn(i, j + 1) - zn(i, j);
    const lit = clamp(0.5 - (gx * 1.6 + gy * 1.6) * 3.2, 0.05, 0.95) * (1 - flat) + 0.5 * flat;
    ctx.globalAlpha = alpha * a;
    ctx.fillStyle = rampAt(1 - Math.pow(zc, 0.8));
    ctx.beginPath();
    pts.forEach(([px, py], n) => (n ? ctx.lineTo(px, py) : ctx.moveTo(px, py)));
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = lit < 0.5 ? `rgba(14,14,13,${(0.5 - lit) * 1.1})` : `rgba(255,240,225,${(lit - 0.5) * 0.7})`;
    ctx.fill();
    ctx.strokeStyle = "rgba(14,14,13,0.4)";
    ctx.lineWidth = 0.6;
    ctx.stroke();
  }
  ctx.globalAlpha = alpha;

  // contour lines (marching squares on the same grid), fade in while the camera goes top-down
  const ca = seg(k, 4.1, 5.2);
  if (ca > 0) {
    ctx.strokeStyle = `rgba(14,14,13,${0.8 * ca})`;
    ctx.lineWidth = 1.3;
    const levels = [0.62, 0.625, 0.63, 0.635, 0.64, 0.645, 0.65];
    for (const lv of levels) {
      const z = (lv - zmin) / (zmax - zmin);
      let tag = null;
      ctx.beginPath();
      for (let i = 0; i < NK - 1; i++) {
        for (let j = 0; j < NH - 1; j++) {
          const c = [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]];
          const v = c.map(([a, b]) => zn(a, b));
          const pts = [];
          for (let e = 0; e < 4; e++) {
            const [a, b] = [c[e], c[(e + 1) % 4]];
            const [va, vb] = [v[e], v[(e + 1) % 4]];
            if (va < z !== vb < z) {
              const f = (z - va) / (vb - va);
              pts.push(proj(lerp(X(a[0]), X(b[0]), f), lerp(Y(a[1]), Y(b[1]), f), z));
            }
          }
          if (pts.length >= 2) {
            ctx.moveTo(...pts[0]);
            ctx.lineTo(...pts[1]);
            if (!tag || pts[0][0] > tag[0]) tag = pts[0];
          }
        }
      }
      ctx.stroke();
      if (tag && [0.62, 0.63, 0.64, 0.65].includes(lv)) {
        text(ctx, lv.toFixed(3), tag[0] + 5, tag[1] + 4, { size: 12, weight: 560, color: C.ink, alpha: alpha * ca });
      }
    }
  }

  // axis ticks and titles (K runs along the bottom edge, home edge along the right edge)
  const ticks = (arr, isK) => {
    arr.forEach((v, n) => {
      if (n % 3) return;
      const f = n / (arr.length - 1);
      const [x, y] = isK ? [lerp(-1, 1, f), 1.07] : [1.07, lerp(-1, 1, f)];
      const [px, py] = proj(x, y, 0);
      text(ctx, String(v), px + (isK ? 0 : 12), py + (isK ? 16 : 4), { size: 12, color: C.muted, align: isK ? "center" : "left" });
    });
  };
  ticks(S.k, true);
  ticks(S.hca, false);
  const [kx, ky] = proj(0, 1.07, 0);
  text(ctx, "K (how fast ratings move)", kx, ky + 58, { size: 13, color: C.soft, align: "center" });
  const [hx, hy] = proj(1.07, 0, 0);
  ctx.save();
  ctx.translate(hx + 84, hy);
  ctx.rotate(-Math.PI / 2);
  text(ctx, "Home-court edge (Elo points)", 0, 0, { size: 13, color: C.soft, align: "center" });
  ctx.restore();

  // best cell marker
  const bi = (S.best[0] - S.k[0]) / (S.k[1] - S.k[0]);
  const bj = (S.best[1] - S.hca[0]) / (S.hca[1] - S.hca[0]);
  const drop = easeOut(seg(k, 3.2, 3.8));
  if (drop > 0) {
    const zz = zn(Math.round(bi), Math.round(bj));
    const [mx, my] = proj(lerp(-1, 1, bi / (NK - 1)), lerp(-1, 1, bj / (NH - 1)), zz + (1 - drop) * 0.7);
    ctx.globalAlpha = alpha * drop;
    ctx.fillStyle = C.ink;
    ctx.beginPath();
    ctx.arc(mx, my, 7, 0, 7);
    ctx.fill();
    ctx.strokeStyle = C.ink;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(mx, my, 14 + (1 - drop) * 10, 0, 7);
    ctx.stroke();
  }
  ctx.restore();

  // readout, left column
  const ra = easeOut(seg(k, 3.6, 4.4));
  text(ctx, "Chosen setting", 56, 330, { size: 13, color: C.muted, alpha: alpha * ra });
  text(ctx, "K 20, home edge 90", 56, 362, { size: 24, weight: 600, alpha: alpha * ra });
  text(ctx, "Log loss 0.6183 on the tuning games.", 56, 390, { size: 15, color: C.soft, alpha: alpha * ra });
  text(ctx, "Lower is better. Brighter means lower.", 56, 414, { size: 15, color: C.muted, alpha: alpha * ra });
}

// ================= beat 2: spread vs reality =================
function lgamma(x) {
  const g = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
  let y = x;
  let tmp = x + 5.5;
  tmp -= (x + 0.5) * Math.log(tmp);
  let ser = 1.000000000190015;
  for (const c of g) ser += c / ++y;
  return -tmp + Math.log((2.5066282746310005 * ser) / x);
}
const F = D.fit;
const tpdf = (x) => {
  const nu = F.df;
  const z = x / F.scale;
  const c = Math.exp(lgamma((nu + 1) / 2) - lgamma(nu / 2)) / Math.sqrt(nu * Math.PI) / F.scale;
  return c * Math.pow(1 + (z * z) / nu, -(nu + 1) / 2);
};
const mean = F.resid.reduce((a, b) => a + b, 0) / F.resid.length;
const realSd = Math.sqrt(F.resid.reduce((a, b) => a + (b - mean) ** 2, 0) / F.resid.length);
const modelSd = F.scale * Math.sqrt(F.df / (F.df - 2));
const kde = (x, bw = 2.1) => {
  let s = 0;
  for (const r of F.resid) s += Math.exp(-0.5 * ((x - r) / bw) ** 2);
  return s / (F.resid.length * bw * Math.sqrt(2 * Math.PI));
};
const RANGE = 42;
const KDE_Y = (() => {
  const a = [];
  for (let x = -RANGE; x <= RANGE; x += 0.5) a.push([x, kde(x), tpdf(x)]);
  return a;
})();
const YMAX = Math.max(...KDE_Y.map((p) => Math.max(p[1], p[2]))) * 1.12;
const rugOrder = (() => {
  const r = rng(9);
  return F.resid.map((v) => [v, r()]);
})();

function spread(ctx, t, alpha) {
  const k = t - B2[0];
  const [x0, x1, y0, y1] = [120, 1080, 190, 560];
  const px = (x) => lerp(x0, x1, (x + RANGE) / (2 * RANGE));
  const py = (d) => y1 - (d / YMAX) * (y1 - y0);
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = C.rule;
  ctx.lineWidth = 1;
  for (let x = -40; x <= 40; x += 10) {
    ctx.beginPath();
    ctx.moveTo(px(x), y0 - 10);
    ctx.lineTo(px(x), y1);
    ctx.stroke();
    text(ctx, (x > 0 ? "+" : "") + x, px(x), y1 + 24, { size: 13, color: C.muted, align: "center" });
  }
  ctx.strokeStyle = C.ruleStrong;
  ctx.beginPath();
  ctx.moveTo(x0, y1);
  ctx.lineTo(x1, y1);
  ctx.stroke();
  text(ctx, "Real margin minus the model's expected margin (points)", (x0 + x1) / 2, y1 + 52, { size: 14, color: C.soft, align: "center" });

  // rug: one tick per real game
  ctx.strokeStyle = C.soft;
  ctx.lineWidth = 1;
  for (const [v, r] of rugOrder) {
    const a = seg(k, 0.3 + r * 1.2, 0.5 + r * 1.2);
    if (!a || Math.abs(v) > RANGE) continue;
    ctx.globalAlpha = alpha * 0.45 * a;
    ctx.beginPath();
    ctx.moveTo(px(v), y1);
    ctx.lineTo(px(v), y1 - 12 * a);
    ctx.stroke();
  }
  ctx.globalAlpha = alpha;

  // real density (rises)
  const rise = easeOut(seg(k, 0.7, 1.7));
  ctx.beginPath();
  KDE_Y.forEach(([x, d], n) => (n ? ctx.lineTo(px(x), py(d * rise)) : ctx.moveTo(px(x), py(d * rise))));
  ctx.lineTo(px(RANGE), y1);
  ctx.lineTo(px(-RANGE), y1);
  ctx.closePath();
  ctx.fillStyle = "rgba(195,194,183,0.20)";
  ctx.fill();
  ctx.strokeStyle = C.soft;
  ctx.lineWidth = 2;
  ctx.stroke();

  // model density (draws left to right)
  const draw = easeInOut(seg(k, 1.3, 2.4));
  const upto = lerp(-RANGE, RANGE, draw);
  ctx.beginPath();
  let first = true;
  for (const [x, , d] of KDE_Y) {
    if (x > upto) break;
    first ? ctx.moveTo(px(x), py(d)) : ctx.lineTo(px(x), py(d));
    first = false;
  }
  ctx.strokeStyle = C.orange;
  ctx.lineWidth = 3;
  ctx.stroke();

  // legend + numbers
  const la = easeOut(seg(k, 2.3, 2.9));
  ctx.globalAlpha = alpha * la;
  ctx.fillStyle = C.soft;
  ctx.fillRect(x0 + 8, 214, 14, 14);
  text(ctx, `Real: 732 test games, spread ${realSd.toFixed(1)} points`, x0 + 32, 227, { size: 16, color: C.ink, alpha: alpha * la });
  ctx.fillStyle = C.orange;
  ctx.fillRect(x0 + 8, 244, 14, 14);
  text(ctx, `Model M1: Student-t, spread ${modelSd.toFixed(1)} points`, x0 + 32, 257, { size: 16, color: C.ink, alpha: alpha * la });
  ctx.restore();
}

// ================= beat 3: one game =================
const G = D.game;
const gEnds = G.ends;
const walks = (() => {
  const r = rng(21);
  return gEnds.map((e) => {
    const w = [0];
    for (let i = 1; i <= 40; i++) w.push(w[i - 1] + normal(r) * 1.5);
    const last = w[40];
    return w.map((v, i) => (i / 40) * e + (v - (i / 40) * last));
  });
})();
const HMAX = Math.max(...G.hist);

function game(ctx, t, alpha) {
  const k = t - B3[0];
  const [x0, x1, y0, y1] = [96, 760, 150, 600];
  const [hx0, hx1] = [800, 1140];
  const M = 36;
  const py = (m) => lerp(y1, y0, (m + M) / (2 * M));
  const px = (u) => lerp(x0, x1, u);
  ctx.save();
  ctx.globalAlpha = alpha;

  // grid
  ctx.lineWidth = 1;
  for (let m = -30; m <= 30; m += 10) {
    ctx.strokeStyle = m === 0 ? C.ruleStrong : C.rule;
    ctx.beginPath();
    ctx.moveTo(x0, py(m));
    ctx.lineTo(hx1, py(m));
    ctx.stroke();
    text(ctx, (m > 0 ? "+" : "") + m, x0 - 12, py(m) + 4, { size: 12, color: C.muted, align: "right" });
  }
  text(ctx, "tip-off", x0, y1 + 28, { size: 13, color: C.muted });
  text(ctx, "final buzzer", x1, y1 + 28, { size: 13, color: C.muted, align: "right" });
  text(ctx, `${G.away} ahead`, x1 - 8, py(M) + 18, { size: 13, color: C.soft, align: "right" });
  text(ctx, `${G.home} ahead`, x1 - 8, py(-M) - 8, { size: 13, color: C.soft, align: "right" });

  // 10,000 draws: paths fan out from tip-off
  const grow = easeInOut(seg(k, 0.6, 2.6));
  ctx.globalCompositeOperation = "lighter";
  ctx.lineWidth = 1;
  for (let n = 0; n < walks.length; n++) {
    const w = walks[n];
    if (w.some((v) => Math.abs(v) > M)) continue;
    ctx.strokeStyle = gEnds[n] > 0 ? "rgba(226,105,31,0.10)" : "rgba(156,154,146,0.10)";
    ctx.beginPath();
    const steps = Math.max(1, Math.floor(grow * 40));
    for (let i = 0; i <= steps; i++) {
      const [x, y] = [px(i / 40), py(clamp(w[i], -M, M))];
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.stroke();
  }
  ctx.globalCompositeOperation = "source-over";

  // histogram of the final margin (right panel)
  const hg = easeOut(seg(k, 1.2, 3.0));
  for (let b = 0; b <= 80; b++) {
    const m = b - 40;
    const len = (G.hist[b] / HMAX) * (hx1 - hx0) * hg;
    if (len < 0.5 || Math.abs(m) > M) continue;
    ctx.fillStyle = m > 0 ? "rgba(226,105,31,0.85)" : "rgba(156,154,146,0.55)";
    ctx.fillRect(hx0, py(m + 0.5), len, (y1 - y0) / (2 * M) - 0.6);
  }

  // percentile lines
  const ba = easeOut(seg(k, 3.2, 3.9));
  if (ba > 0) {
    ctx.save();
    ctx.globalAlpha = alpha * ba;
    ctx.setLineDash([6, 5]);
    ctx.lineWidth = 1.5;
    for (const [m, name, c] of [[G.p10, "10th", C.soft], [G.p50, "median", C.ink], [G.p90, "90th", C.soft]]) {
      ctx.strokeStyle = c;
      ctx.beginPath();
      ctx.moveTo(x0, py(m));
      ctx.lineTo(hx1, py(m));
      ctx.stroke();
      text(ctx, `${name} ${m > 0 ? "+" : ""}${m}`, hx0 - 8, py(m) + (name === "90th" ? -6 : 16), { size: 13, color: c, align: "right" });
    }
    ctx.restore();
  }

  // probability readout
  const pa = easeOut(seg(k, 3.4, 4.1));
  text(ctx, `${Math.round(G.p_away * 100)}%`, 150, 220, { size: 64, weight: 640, color: C.orange, alpha: alpha * pa });
  text(ctx, `chance that ${G.away} wins`, 150, 248, { size: 16, color: C.soft, alpha: alpha * pa });

  // the real result lands
  const ra = easeOut(seg(k, 4.6, 5.3));
  if (ra > 0) {
    const m = G.away_score - G.home_score;
    ctx.save();
    ctx.globalAlpha = alpha * ra;
    ctx.strokeStyle = C.ink;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(x0, py(m));
    ctx.lineTo(hx1, py(m));
    ctx.stroke();
    ctx.fillStyle = C.ink;
    ctx.beginPath();
    ctx.arc(px(1), py(m), 8 + (1 - ra) * 8, 0, 7);
    ctx.fill();
    ctx.restore();
    const label = `Final: ${G.home} ${G.home_score}, ${G.away} ${G.away_score}  (+${m})`;
    ctx.save();
    ctx.font = `620 16px ${FONT}`;
    const tw = ctx.measureText(label).width;
    ctx.globalAlpha = alpha * ra * 0.9;
    ctx.fillStyle = C.bg;
    ctx.fillRect(x1 - 16 - tw - 10, py(m) - 38, tw + 20, 26);
    ctx.restore();
    text(ctx, label, x1 - 16, py(m) - 19, { size: 16, weight: 620, align: "right", alpha: alpha * ra });
  }
  const ca = easeOut(seg(k, 5.2, 5.7));
  text(ctx, `Called: ${G.away}`, 150, 282, { size: 20, weight: 620, color: C.up, alpha: alpha * ca });
  text(ctx, `Live, this model: ${G.live.hits} of ${G.live.n} games called right`, 150, 308, { size: 14, color: C.muted, alpha: alpha * ca });
  text(ctx, "Illustration: each line is one possible game flow. The end points are the model's 10,000 draws.", 56, 652, { size: 13, color: C.muted, alpha });
  ctx.restore();
}

function game_head(ctx, alpha) {
  head(ctx, `${D.game.home} vs ${D.game.away}: 10,000 simulated games`, "One game, one model. Each line is a possible game. Together they give the odds.", alpha);
}

start((ctx, t) => {
  text(ctx, "675hoops.com", W - 40, H - 22, { size: 13, color: C.muted, align: "right", alpha: 0.7 });
  const a1 = vis(t, B1);
  const a2 = vis(t, B2);
  const a3 = vis(t, B3);
  if (a1 > 0) {
    head(ctx, "Which settings predict best?", "Elo log loss for every K and home-court value. Lower is better.", a1);
    surface(ctx, t, a1);
  }
  if (a2 > 0) {
    head(ctx, "Does the model's spread match reality?", "Real misses in points, against what the model says is likely.", a2);
    spread(ctx, t, a2);
  }
  if (a3 > 0) {
    game_head(ctx, a3);
    game(ctx, t, a3);
  }
});
