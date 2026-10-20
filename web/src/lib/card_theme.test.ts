// Unit tests for the card themes: the dark recolour, the route and file names of a theme, and the
// palettes against the site's own tokens in global.css (so the cards cannot drift from the page).

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DARK, LIGHT, cardNames, recolour, splitTheme, themedName } from "./cards/theme.ts";

const css = readFileSync(new URL("../styles/global.css", import.meta.url), "utf8");

/** The `--token: value` pairs in the first block that starts with `selector {`. */
function tokens(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  assert.ok(start >= 0, `no ${selector} block in global.css`);
  const body = css.slice(start, css.indexOf("}", start));
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) out[m[1]] = m[2].toLowerCase();
  return out;
}

// Each card colour and the page token it stands for.
const TOKEN = {
  paper: "page",
  surface: "surface",
  ink: "ink",
  inkSoft: "ink-2",
  muted: "muted",
  axis: "axis",
  rule: "rule",
  ruleStrong: "rule-strong",
  orange: "data-1",
  gray: "data-2",
  blue: "data-neg",
} as const;

test("light palette matches the :root tokens of global.css", () => {
  const t = tokens(":root");
  for (const [key, token] of Object.entries(TOKEN)) {
    assert.equal(LIGHT[key as keyof typeof LIGHT].toLowerCase(), t[token], `light ${key} vs --${token}`);
  }
});

test("dark palette matches the night tokens of global.css", () => {
  const t = tokens(':root[data-theme="dark"]');
  for (const [key, token] of Object.entries(TOKEN)) {
    assert.equal(DARK[key as keyof typeof DARK].toLowerCase(), t[token], `dark ${key} vs --${token}`);
  }
});

test("every light colour has a distinct dark counterpart", () => {
  const light = Object.values(LIGHT).map((c) => c.toLowerCase());
  assert.equal(new Set(light).size, light.length, "light colours must be distinct");
  for (const k of Object.keys(LIGHT) as (keyof typeof LIGHT)[]) {
    assert.match(DARK[k], /^#[0-9a-f]{6}$/);
  }
  // The axis grey is the same in both themes on the site (--axis), so it is the one colour that may match.
  for (const k of Object.keys(LIGHT) as (keyof typeof LIGHT)[]) {
    if (k !== "axis") assert.notEqual(DARK[k], LIGHT[k], `${k} should differ between themes`);
  }
});

test("recolour leaves the light SVG unchanged", () => {
  const svg = `<svg><rect fill="${LIGHT.paper}"/><path fill="${LIGHT.ink}" stroke="${LIGHT.ink}"/></svg>`;
  assert.equal(recolour(svg, "light"), svg);
});

test("recolour swaps each light palette colour for its dark one", () => {
  const svg =
    `<svg><rect fill="${LIGHT.paper}"/><path fill="${LIGHT.orange}" d="M0 0"/>` +
    `<line stroke="${LIGHT.rule}" stroke-width="1"/><path fill="${LIGHT.blue}"/></svg>`;
  const out = recolour(svg, "dark");
  assert.equal(
    out,
    `<svg><rect fill="${DARK.paper}"/><path fill="${DARK.orange}" d="M0 0"/>` +
      `<line stroke="${DARK.rule}" stroke-width="1"/><path fill="${DARK.blue}"/></svg>`,
  );
});

test("recolour leaves colours outside the palette and non-colour digits alone", () => {
  const svg = `<svg width="1080" height="1350"><path fill="#123456" d="M1.5 2.25 L100 200"/><text>#f9f9f7 is ours</text></svg>`;
  const out = recolour(svg, "dark");
  assert.ok(out.includes('fill="#123456"'));
  assert.ok(out.includes('width="1080" height="1350"'));
  assert.ok(out.includes(`${DARK.paper} is ours`));
});

test("recolour matches hex case-insensitively", () => {
  assert.ok(recolour(`<path fill="#D9590B"/>`, "dark").includes(`fill="${DARK.orange}"`));
});

test("themedName adds the dark suffix only to the dark theme", () => {
  assert.equal(themedName("round-4", "light"), "round-4");
  assert.equal(themedName("round-4", "dark"), "round-4-dark");
  assert.equal(themedName("round-4-recap", "dark"), "round-4-recap-dark");
});

test("cardNames gives the light and the dark route name", () => {
  assert.deepEqual(cardNames("round-4-recap"), ["round-4-recap", "round-4-recap-dark"]);
  assert.deepEqual(cardNames("ana-lopez"), ["ana-lopez", "ana-lopez-dark"]);
});

test("splitTheme reads the theme back from a route name", () => {
  assert.deepEqual(splitTheme("round-4"), { base: "round-4", theme: "light" });
  assert.deepEqual(splitTheme("round-4-dark"), { base: "round-4", theme: "dark" });
  assert.deepEqual(splitTheme("round-4-recap-dark"), { base: "round-4-recap", theme: "dark" });
  assert.deepEqual(splitTheme("1234567"), { base: "1234567", theme: "light" });
});

test("splitTheme and themedName round-trip", () => {
  for (const base of ["round-1", "round-12-recap", "game-id-9"]) {
    for (const theme of ["light", "dark"] as const) {
      assert.deepEqual(splitTheme(themedName(base, theme)), { base, theme });
    }
  }
});
