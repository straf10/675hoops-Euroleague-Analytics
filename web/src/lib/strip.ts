// The strip plot: one dot per item on a vertical value axis, jittered so that dots with the same
// value do not sit on top of each other. Pure, so the build and the page script place dots the same
// way (the same pattern as lib/scatter.ts). No runtime imports, so Node can run it directly.

/** The plot's height in px. The dots' y is a px offset from its top. */
export const STRIP_HEIGHT = 360;
/** Dots whose centres fall in the same band of this many px share one jitter row. */
export const BIN = 6;
/** Each step a dot takes out from the centre in its band, to the right then the left. */
export const STEP = 6;

export interface StripItem {
  key: string;
  value: number;
  top: boolean;
}

export interface StripDot {
  key: string;
  /** Horizontal offset from the centre of the strip, px. */
  dx: number;
  /** Vertical position from the top of the plot, px. */
  y: number;
  top: boolean;
}

export interface StripTick {
  value: number;
  y: number;
}

/** "Nice" tick values across [lo, hi]: a 1, 2, 2.5, 5 or 10 step, about `count` of them. */
export function niceTicks(lo: number, hi: number, count = 6): number[] {
  const span = hi - lo || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((s) => s * mag).find((s) => span / s <= count) ?? 10 * mag;
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(Number(v.toFixed(6)));
  return ticks;
}

/** The axis domain of a set of values, padded by 8%. An empty set reads as [0, 1]. Non-negative
 *  measures (`floorAtZero`) never start below zero. */
export function domainOf(values: number[], floorAtZero: boolean): [number, number] {
  if (!values.length) return [0, 1];
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.08;
  lo -= pad;
  hi += pad;
  if (floorAtZero && lo < 0) lo = 0;
  return [lo, hi];
}

/** Px from the top of the plot for a value: the highest value sits at the top. */
export function valueY(value: number, lo: number, hi: number, height = STRIP_HEIGHT): number {
  return (height * (hi - value)) / (hi - lo || 1);
}

/** Show top: whether the item at `index` (in ranked order) is one of the first `top`; 0 is all. */
export const isTop = (index: number, top: number): boolean => top === 0 || index < top;

/** Places every item. Items are sorted by value (ties by key, so the result never depends on input
 *  order). Within each 6 px band the first dot sits on the centre line, then the dots step out to the
 *  right and the left in turn: 0, +6, -6, +12, -12 px. */
export function stripLayout(items: StripItem[], lo: number, hi: number, height = STRIP_HEIGHT) {
  const placed = items
    .map((it) => ({ ...it, y: valueY(it.value, lo, hi, height) }))
    .sort((a, b) => a.y - b.y || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  const inBand = new Map<number, number>();
  const dots: StripDot[] = placed.map((p) => {
    const band = Math.floor(p.y / BIN);
    const k = inBand.get(band) ?? 0;
    inBand.set(band, k + 1);
    const dx = k === 0 ? 0 : (k % 2 ? 1 : -1) * STEP * Math.ceil(k / 2);
    return { key: p.key, dx, y: Math.round(p.y * 100) / 100, top: p.top };
  });
  const ticks: StripTick[] = niceTicks(lo, hi).map((value) => ({ value, y: valueY(value, lo, hi, height) }));
  return { dots, ticks };
}
