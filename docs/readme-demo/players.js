// Players: every EuroLeague player on an offence/defence map (M3), then how sure each rating is.
window.DURATION = 12;
const D = window.DATA.players;
const ROWS = D.rows;
const A = [0, 6.7];
const B = [6.3, 12];
const FADE = 0.45;
const vis = (t, [a, b]) => seg(t, a, a + FADE) * (1 - seg(t, b - FADE, b));
const seasonLabel = `${D.season}-${String(D.season + 1).slice(2)}`;

// ================= beat A: offence / defence map =================
const R = 9; // axis range, points per 100 possessions
const order = (() => {
  const r = rng(3);
  return ROWS.map((p) => [p, r()]);
})();
const named = [...ROWS].filter((p) => p.min >= 500).sort((a, b) => b.net - a.net);
const labelled = named.slice(0, 6);

function map(ctx, t, alpha) {
  const k = t - A[0];
  const [x0, x1, y0, y1] = [110, 740, 150, 600];
  const px = (o) => lerp(x0, x1, (o + R) / (2 * R));
  const py = (d) => lerp(y1, y0, (d + R) / (2 * R));
  ctx.save();
  ctx.globalAlpha = alpha;
  text(ctx, "Who moves the scoreboard?", 56, 74, { size: 30, weight: 620, alpha });
  text(ctx, `Every EuroLeague player, ${seasonLabel}. Points per 100 possessions, above or below average.`, 56, 104, { size: 16, color: C.muted, alpha });

  // grid and axes
  ctx.lineWidth = 1;
  for (let v = -8; v <= 8; v += 4) {
    ctx.strokeStyle = v === 0 ? C.ruleStrong : C.rule;
    ctx.beginPath();
    ctx.moveTo(px(v), y0);
    ctx.lineTo(px(v), y1);
    ctx.moveTo(x0, py(v));
    ctx.lineTo(x1, py(v));
    ctx.stroke();
    text(ctx, (v > 0 ? "+" : "") + v, px(v), y1 + 22, { size: 12, color: C.muted, align: "center" });
    text(ctx, (v > 0 ? "+" : "") + v, x0 - 12, py(v) + 4, { size: 12, color: C.muted, align: "right" });
  }
  text(ctx, "Offence: better scoring when he plays", (x0 + x1) / 2, y1 + 48, { size: 13, color: C.soft, align: "center" });
  ctx.save();
  ctx.translate(x0 - 52, (y0 + y1) / 2);
  ctx.rotate(-Math.PI / 2);
  text(ctx, "Defence: fewer points allowed", 0, 0, { size: 13, color: C.soft, align: "center" });
  ctx.restore();

  // lines of equal net rating (offence + defence)
  const ia = easeOut(seg(k, 0.2, 1.0));
  ctx.save();
  ctx.setLineDash([5, 6]);
  ctx.strokeStyle = C.ruleStrong;
  ctx.globalAlpha = alpha * ia;
  for (const n of [-6, 0, 6]) {
    ctx.beginPath();
    ctx.moveTo(px(n - R), py(R));
    ctx.lineTo(px(n + R), py(-R));
    ctx.stroke();
  }
  ctx.restore();

  // players, appearing in a seeded random order
  for (const [p, r] of order) {
    const a = easeOut(seg(k, 0.5 + r * 2.4, 0.9 + r * 2.4));
    if (a <= 0 || Math.abs(p.o) > R || Math.abs(p.d) > R) continue;
    const rad = lerp(3, 9, clamp(p.min / 1400)) * a;
    ctx.fillStyle = rampAt(0.2 + 0.8 * clamp((p.net + 4) / 12));
    ctx.globalAlpha = alpha * 0.8;
    ctx.beginPath();
    ctx.arc(px(p.o), py(p.d), rad, 0, 7);
    ctx.fill();
  }
  ctx.globalAlpha = alpha;

  // the best six get a name; labels keep 20 px apart so the cluster stays readable
  const ys = labelled.map((p) => py(p.d)).map((y, i) => [y, i]).sort((a, b) => a[0] - b[0]);
  for (let i = 1; i < ys.length; i++) ys[i][0] = Math.max(ys[i][0], ys[i - 1][0] + 21);
  const labelY = [];
  ys.forEach(([y, i]) => (labelY[i] = y));
  labelled.forEach((p, i) => {
    const a = easeOut(seg(k, 3.2 + i * 0.25, 3.7 + i * 0.25));
    if (a <= 0) return;
    const [x, y] = [px(p.o), py(p.d)];
    ctx.strokeStyle = C.ink;
    ctx.lineWidth = 2;
    ctx.globalAlpha = alpha * a;
    ctx.beginPath();
    ctx.arc(x, y, 11, 0, 7);
    ctx.stroke();
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x + 11, y);
    ctx.lineTo(x + 24, labelY[i] - 5);
    ctx.stroke();
    ctx.globalAlpha = alpha;
    text(ctx, `${p.name}, ${p.team}`, x + 28, labelY[i], { size: 14, weight: 600, alpha: alpha * a });
  });

  // right column: how a rating is made
  const lines = [
    ["How a rating is made", 22, 620, C.ink],
    ["Start with the score while he is on court.", 16, 500, C.soft],
    ["Adjust for the nine other players and for home court.", 16, 500, C.soft],
    ["Pull the result toward a box-score estimate, so a small sample cannot fool the model.", 16, 500, C.soft],
  ];
  const wrap = (s, w) => {
    ctx.font = `500 16px ${FONT}`;
    const out = [];
    let cur = "";
    for (const word of s.split(" ")) {
      const next = cur ? `${cur} ${word}` : word;
      if (ctx.measureText(next).width > w && cur) {
        out.push(cur);
        cur = word;
      } else cur = next;
    }
    out.push(cur);
    return out;
  };
  let y = 200;
  lines.forEach(([s, size, weight, color], i) => {
    const a = easeOut(seg(k, 1.2 + i * 0.7, 1.9 + i * 0.7));
    for (const ln of i === 0 ? [s] : wrap(s, 330)) {
      text(ctx, ln, 800, y, { size, weight, color, alpha: alpha * a });
      y += size + 8;
    }
    y += i === 0 ? 8 : 12;
  });
  const na = easeOut(seg(k, 4.2, 4.9));
  text(ctx, "Dashed lines mark equal net rating (offence plus defence).", 800, 560, { size: 13, color: C.muted, alpha: alpha * na });
  text(ctx, "Dot size shows minutes played.", 800, 580, { size: 13, color: C.muted, alpha: alpha * na });
  ctx.restore();
}

// ================= beat B: how sure is the rating =================
const best10 = named.slice(0, 10);

function forest(ctx, t, alpha) {
  const k = t - B[0];
  text(ctx, "How sure is each rating?", 56, 74, { size: 30, weight: 620, alpha });
  text(ctx, "The ten best players with 500 or more minutes. The bar is the 90% range.", 56, 104, { size: 16, color: C.muted, alpha });
  const [x0, x1, y0, step] = [380, 1090, 160, 42];
  const [lo, hi] = [0, 14];
  const px = (v) => lerp(x0, x1, (v - lo) / (hi - lo));
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.lineWidth = 1;
  for (let v = 0; v <= 14; v += 2) {
    ctx.strokeStyle = v === 0 ? C.ruleStrong : C.rule;
    ctx.beginPath();
    ctx.moveTo(px(v), y0 - 14);
    ctx.lineTo(px(v), y0 + step * 10 - 8);
    ctx.stroke();
    text(ctx, (v > 0 ? "+" : "") + v, px(v), y0 + step * 10 + 14, { size: 12, color: C.muted, align: "center" });
  }
  text(ctx, "Net rating, points per 100 possessions", (x0 + x1) / 2, y0 + step * 10 + 42, { size: 13, color: C.soft, align: "center" });
  best10.forEach((p, i) => {
    const y = y0 + i * step + 14;
    const a = easeOut(seg(k, 0.3 + i * 0.12, 0.9 + i * 0.12));
    const grow = easeInOut(seg(k, 1.4 + i * 0.1, 2.4 + i * 0.1));
    text(ctx, p.name, 56, y + 5, { size: 17, weight: 600, alpha: alpha * a });
    text(ctx, p.team, 230, y + 5, { size: 15, color: C.muted, alpha: alpha * a });
    ctx.globalAlpha = alpha * a;
    ctx.fillStyle = "rgba(226,105,31,0.35)";
    const l = px(lerp(p.net, p.lo, grow));
    const h = px(lerp(p.net, p.hi, grow));
    ctx.fillRect(l, y - 6, h - l, 12);
    ctx.fillStyle = C.orange;
    ctx.beginPath();
    ctx.arc(px(p.net), y, 7 * a, 0, 7);
    ctx.fill();
    ctx.globalAlpha = alpha;
    text(ctx, `+${p.net.toFixed(1)}`, 330, y + 5, { size: 16, weight: 620, align: "right", alpha: alpha * a });
  });
  const na = easeOut(seg(k, 3.0, 3.7));
  const half = (1.645 * D.median_sd).toFixed(1);
  text(ctx, `For a typical player the 90% range is about plus or minus ${half}. Ranges overlap, so the model treats ratings as estimates, not facts.`, 56, 640, { size: 14, color: C.soft, alpha: alpha * na });
  ctx.restore();
}

start((ctx, t) => {
  text(ctx, "675hoops.com", W - 40, H - 22, { size: 13, color: C.muted, align: "right", alpha: 0.7 });
  const a = vis(t, A);
  const b = vis(t, B);
  if (a > 0) map(ctx, t, a);
  if (b > 0) forest(ctx, t, b);
});
