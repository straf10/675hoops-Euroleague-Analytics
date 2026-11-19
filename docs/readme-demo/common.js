// Shared helpers for the README demo scenes. Night palette from docs/DESIGN.md.
// A scene draws frame t (seconds) with seek(t). The render script calls seek for every frame;
// open a scene with ?play to watch it live.
const C = {
  bg: "#0e0e0d",
  panel: "#1a1a19",
  rule: "#2c2c2a",
  ruleStrong: "#45453f",
  ink: "#f2f1ec",
  soft: "#c3c2b7",
  muted: "#9c9a92",
  orange: "#e2691f",
  blue: "#3987e5",
  up: "#3fae6a",
  down: "#e66767",
  // sequential ramp, dark to light (night-freq-1..5)
  ramp: ["#8c3a0c", "#b44c10", "#e2691f", "#f29a5e", "#f8c9a2"],
};
const W = 1200;
const H = 675;
const FONT = '"Geist", "Segoe UI", system-ui, sans-serif';

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const seg = (t, a, b) => clamp((t - a) / (b - a)); // progress of t inside [a, b]
const easeOut = (k) => 1 - Math.pow(1 - k, 3);
const easeInOut = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

function rng(seed) {
  // mulberry32: small seeded generator, so a frame is the same on every render
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function normal(r) {
  return Math.sqrt(-2 * Math.log(r() + 1e-12)) * Math.cos(2 * Math.PI * r());
}

function mix(c1, c2, k) {
  const p = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  const a = p(c1);
  const b = p(c2);
  return `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], k))).join(",")})`;
}
function rampAt(k) {
  // k in 0..1 -> colour along C.ramp
  const n = C.ramp.length - 1;
  const x = clamp(k) * n;
  const i = Math.min(n - 1, Math.floor(x));
  return mix(C.ramp[i], C.ramp[i + 1], x - i);
}

function text(ctx, s, x, y, o = {}) {
  ctx.save();
  ctx.globalAlpha = o.alpha ?? 1;
  ctx.fillStyle = o.color ?? C.ink;
  ctx.font = `${o.weight ?? 500} ${o.size ?? 16}px ${FONT}`;
  ctx.textAlign = o.align ?? "left";
  ctx.textBaseline = o.base ?? "alphabetic";
  ctx.fillText(s, x, y);
  ctx.restore();
}

function start(draw) {
  const canvas = document.getElementById("c");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  const seek = (t) => {
    ctx.save();
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, W, H);
    draw(ctx, t);
    ctx.restore();
  };
  window.seek = seek;
  document.fonts.load(`600 16px ${FONT}`).then(() => {
    seek(0);
    window.ready = true;
    if (location.search.includes("play")) {
      const t0 = performance.now();
      const loop = () => {
        seek(((performance.now() - t0) / 1000) % (window.DURATION || 12));
        requestAnimationFrame(loop);
      };
      loop();
    }
  });
}
