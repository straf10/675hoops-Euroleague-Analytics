// Live record card (static picture): Elo against always picking the home side.
window.DURATION = 1;
const R = window.DATA.record;
const H2 = 540;

function fmtDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  return `${d} ${months[m - 1]} ${y}`;
}

function draw(ctx) {
  text(ctx, "Elo against always picking the home side", 56, 74, { size: 30, weight: 620 });
  text(ctx, `EuroLeague 2026-27: ${R.elo.n} games scored, through ${fmtDate(R.through)}. Lower log loss is better.`, 56, 104, { size: 16, color: C.muted });

  // rolling log loss
  const [x0, x1, y0, y1] = [96, 700, 190, 440];
  const [lo, hi] = [0.58, 0.76];
  const n0 = R.series[0][0];
  const n1 = R.series[R.series.length - 1][0];
  const px = (n) => lerp(x0, x1, (n - n0) / (n1 - n0));
  const py = (v) => lerp(y1, y0, (v - lo) / (hi - lo));
  ctx.lineWidth = 1;
  for (let v = 0.6; v <= 0.7601; v += 0.02) {
    ctx.strokeStyle = C.rule;
    ctx.beginPath();
    ctx.moveTo(x0, py(v));
    ctx.lineTo(x1, py(v));
    ctx.stroke();
    text(ctx, v.toFixed(2), x0 - 12, py(v) + 4, { size: 12, color: C.muted, align: "right" });
  }
  for (const n of [50, 70, 90, 110]) {
    if (n > n1) continue;
    text(ctx, String(n), px(n), y1 + 24, { size: 12, color: C.muted, align: "center" });
  }
  text(ctx, "Games scored", (x0 + x1) / 2, y1 + 48, { size: 13, color: C.soft, align: "center" });
  text(ctx, `Log loss over the last ${R.window} games`, x0 - 40, y0 - 22, { size: 13, color: C.soft, align: "left" });

  // gap between the two lines
  ctx.fillStyle = "rgba(226,105,31,0.16)";
  ctx.beginPath();
  R.series.forEach(([n, e]) => ctx.lineTo(px(n), py(e)));
  for (let i = R.series.length - 1; i >= 0; i--) ctx.lineTo(px(R.series[i][0]), py(R.series[i][2]));
  ctx.closePath();
  ctx.fill();
  for (const [col, c, w] of [[2, C.muted, 2], [1, C.orange, 3.5]]) {
    ctx.strokeStyle = c;
    ctx.lineWidth = w;
    ctx.lineJoin = "round";
    ctx.beginPath();
    R.series.forEach((p, i) => (i ? ctx.lineTo(px(p[0]), py(p[col])) : ctx.moveTo(px(p[0]), py(p[col]))));
    ctx.stroke();
  }
  const first = R.series[0];
  text(ctx, "Elo", x0 + 6, py(first[1]) + 28, { size: 15, weight: 620, color: C.orange });
  text(ctx, "Always the home side", x0 + 6, py(first[2]) + 26, { size: 15, weight: 620, color: C.soft });

  // season totals
  const tiles = [
    ["Log loss", R.elo.log_loss.toFixed(3), R.b0.log_loss.toFixed(3)],
    ["Brier score", R.elo.brier.toFixed(3), R.b0.brier.toFixed(3)],
    ["Called right", `${Math.round(R.elo.accuracy * 100)}%`, `${Math.round(R.b0.accuracy * 100)}%`],
  ];
  const tx = 770;
  text(ctx, "Elo", tx + 140, 168, { size: 14, weight: 620, color: C.orange });
  text(ctx, "Home side", tx + 275, 168, { size: 14, weight: 620, color: C.soft });
  tiles.forEach(([label, a, b], i) => {
    const y = 200 + i * 86;
    ctx.strokeStyle = C.rule;
    ctx.beginPath();
    ctx.moveTo(tx, y - 14);
    ctx.lineTo(1144, y - 14);
    ctx.stroke();
    text(ctx, label, tx, y + 28, { size: 16, color: C.soft });
    text(ctx, a, tx + 140, y + 34, { size: 36, weight: 640, color: C.orange });
    text(ctx, b, tx + 275, y + 34, { size: 26, weight: 560, color: C.muted });
  });
  text(ctx, `${R.not_scored} games are not scored: their forecast was not public before tip-off.`, 56, H2 - 22, { size: 13, color: C.muted });
  text(ctx, "675hoops.com", 1144, H2 - 22, { size: 13, color: C.muted, align: "right" });
}

// static card: 1200 x 540
(() => {
  const canvas = document.getElementById("c");
  canvas.width = W;
  canvas.height = H2;
  const ctx = canvas.getContext("2d");
  window.seek = () => {
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, W, H2);
    draw(ctx);
  };
  document.fonts.load(`600 16px ${FONT}`).then(() => {
    window.seek();
    window.ready = true;
  });
})();
