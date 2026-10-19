// Browser smoke test for the client-side scripts of the Players, Player, Team, Compare and Leaders
// pages. It drives a real Microsoft Edge (or Chrome) through Playwright, clicks through each
// interaction and checks the DOM afterwards, then checks each page at a 390 px phone width and in
// dark mode for horizontal scroll. It also records console errors and uncaught exceptions.
//
// NOT part of CI and not a dependency of web/package.json. Run it by hand against a built site:
//
//   1. Build the data and the site (from the repo root):
//        uv run eurohoops publish
//        uv run eurohoops export-stats --from-cache
//        cd web && npx astro build && cd ..
//   2. Serve the build. The preview server prints its URL (default port 4321):
//        cd web && npx astro preview --port 4321
//   3. Install playwright-core once, OUTSIDE the repo (no browser download is needed: it drives
//      the Microsoft Edge that is already installed):
//        mkdir %TEMP%\pw-smoke && cd %TEMP%\pw-smoke && npm init -y && npm i -D playwright-core@1
//   4. Run from the repo, pointing PLAYWRIGHT_CORE at the installed package entry as a file URL:
//        set PLAYWRIGHT_CORE=file:///C:/Users/<you>/AppData/Local/Temp/pw-smoke/node_modules/playwright-core/index.js
//        node web/scripts/smoke.mjs
//      Without PLAYWRIGHT_CORE the script imports the bare name "playwright-core", which resolves
//      only from a node_modules folder on the path to web/scripts.
//
// Environment: SMOKE_BASE (default http://127.0.0.1:4321), SMOKE_CHANNEL (default msedge; use
// "chrome" for Chrome). Exit code 1 if any check fails. Prints one PASS/FAIL line per check and
// the console errors per page.

const BASE = (process.env.SMOKE_BASE ?? "http://127.0.0.1:4321").replace(/\/$/, "");
const CHANNEL = process.env.SMOKE_CHANNEL ?? "msedge";
const pw = await import(process.env.PLAYWRIGHT_CORE ?? "playwright-core");
const { chromium } = pw.chromium ? pw : pw.default; // CommonJS entries expose chromium on default

const results = [];
const consoleErrors = [];

function record(page, check, ok, detail = "") {
  results.push({ page, check, ok: Boolean(ok), detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${page} | ${check}${detail ? `  (${detail})` : ""}`);
}

/** Runs one check; an exception counts as a failure with its message. */
async function check(page, name, fn) {
  try {
    const r = await fn();
    record(page, name, r?.ok ?? r, r?.detail ?? "");
  } catch (err) {
    record(page, name, false, String(err.message ?? err).split("\n")[0]);
  }
}

/** Polls a predicate in the page until it is true, or throws after `ms`. */
async function until(page, fn, arg, ms = 8000) {
  await page.waitForFunction(fn, arg, { timeout: ms, polling: 100 });
}

/** Opens a page, watching for console errors and uncaught exceptions on it. */
async function open(browser, path, { width = 1280, dark = false } = {}) {
  const context = await browser.newContext({
    viewport: { width, height: 900 },
    colorScheme: dark ? "dark" : "light",
  });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(`uncaught: ${e.message}`));
  await page.goto(BASE + path, { waitUntil: "load" });
  return { context, page, errors };
}

/** Phone width and dark mode: no horizontal page scroll. */
async function layoutCheck(browser, label, path) {
  for (const dark of [false, true]) {
    const { context, page, errors } = await open(browser, path, { width: 390, dark });
    const name = `390 px${dark ? ", dark" : ""}: no horizontal scroll`;
    await check(label, name, async () => {
      const { sw, cw } = await page.evaluate(() => ({
        sw: document.documentElement.scrollWidth,
        cw: document.documentElement.clientWidth,
      }));
      return { ok: sw <= cw, detail: `scrollWidth ${sw}, clientWidth ${cw}` };
    });
    consoleErrors.push({ page: `${label} (390${dark ? " dark" : ""})`, errors });
    await context.close();
  }
}

/** Errors are checked at the end of each page's run, so a late script failure is caught. */
function errorCheck(label, errors) {
  record(label, "no console errors or uncaught exceptions", errors.length === 0, errors.slice(0, 2).join(" | "));
}

// Shared discovery: one player slug and one club code, read from the built site.
async function discover(browser) {
  const { context, page, errors } = await open(browser, "/players/");
  const slug = await page.locator("#tbody tr a").first().getAttribute("href");
  const firstPlayer = slug ? slug.replace(/\/$/, "").split("/").pop() : null;
  await context.close();
  return { firstPlayer, errors };
}

async function playersPage(browser) {
  const L = "Players";
  const { context, page, errors } = await open(browser, "/players/");

  await check(L, "strip plot renders dots", async () => {
    const n = await page.locator("#plot a.dot").count();
    return { ok: n > 0, detail: `${n} dots` };
  });

  await check(L, "dot hover highlights its row", async () => {
    const dot = page.locator("#plot a.dot.top").first();
    const id = await dot.getAttribute("data-id");
    await dot.hover();
    await until(page, (id) => document.querySelector(`#tbody tr[data-id="${id}"]`)?.classList.contains("hot"), id);
    return { ok: true };
  });

  await check(L, "row hover highlights its dot", async () => {
    const row = page.locator("#tbody tr[data-id]").nth(1);
    const id = await row.getAttribute("data-id");
    await row.hover();
    await until(page, (id) => document.querySelector(`#plot a.dot[data-id="${id}"]`)?.classList.contains("hot"), id);
    return { ok: true };
  });

  await check(L, "dot click opens the player page", async () => {
    await page.locator("#plot a.dot.top").first().click();
    await page.waitForURL(/\/players\/[^/?#]+\/?$/, { timeout: 8000 });
    const h1 = await page.locator("h1").first().textContent();
    return { ok: true, detail: `now at ${new URL(page.url()).pathname}, h1 "${h1.trim()}"` };
  });
  await page.goBack();
  await page.waitForSelector("#plot a.dot");

  await check(L, "Min/game preset changes the list and the dots", async () => {
    const before = await page.locator("#count").textContent();
    const dotsBefore = await page.locator("#plot a.dot").count();
    await page.locator('label[for="mp-25"]').click();
    await until(page, (t) => document.querySelector("#count")?.textContent !== t, before);
    const after = await page.locator("#count").textContent();
    const checked = await page.locator('input[name="minPreset"]:checked').getAttribute("value");
    const dotsAfter = await page.locator("#plot a.dot").count();
    return {
      ok: checked === "25" && dotsAfter <= dotsBefore,
      detail: `"${before.trim()}" -> "${after.trim()}", dots ${dotsBefore} -> ${dotsAfter}`,
    };
  });

  await check(L, "?min= snaps to a preset (min=12 -> 10)", async () => {
    const p2 = await open(browser, "/players/?min=12");
    const checked = await p2.page.locator('input[name="minPreset"]:checked').getAttribute("value");
    errorCheck("Players ?min=12", p2.errors);
    await p2.context.close();
    return { ok: checked === "10", detail: `checked ${checked}` };
  });

  await check(L, "season switch moves the dots", async () => {
    const sel = page.locator('select[name="season"]');
    const options = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value));
    const current = await sel.inputValue();
    const other = options.find((v) => v !== current);
    if (!other) return { ok: true, detail: "only one season, skipped" };
    const ids = (await page.locator("#plot a.dot").evaluateAll((as) => as.map((a) => a.dataset.id).join(",")));
    await sel.selectOption(other);
    await until(page, (old) => [...document.querySelectorAll("#plot a.dot")].map((a) => a.dataset.id).join(",") !== old, ids);
    return { ok: true, detail: `${current} -> ${other}` };
  });

  await check(L, "metric switch changes the strip title and rows", async () => {
    const title = await page.locator("#rank-title").textContent();
    await page.locator('select[name="metric"]').selectOption("ast");
    await until(page, (t) => document.querySelector("#rank-title")?.textContent !== t, title);
    const after = await page.locator("#rank-title").textContent();
    const q = new URL(page.url()).search;
    return { ok: q.includes("metric=ast"), detail: `"${title.trim()}" -> "${after.trim()}"` };
  });

  await check(L, "Show top changes the count", async () => {
    await page.locator('select[name="top"]').selectOption("10");
    await until(page, () => document.querySelector("#top-text")?.textContent === "Top 10");
    return { ok: true };
  });

  await check(L, "rate switch (per 36) changes the title", async () => {
    const before = await page.locator("#rank-title").textContent();
    await page.locator('label[for="rate-36"]').click();
    await until(page, (t) => document.querySelector("#rank-title")?.textContent !== t, before);
    return { ok: true };
  });

  await check(L, "column header sort sets the metric", async () => {
    await page.locator('#thead button[data-sort="reb"]').click();
    await until(page, () => location.search.includes("metric=reb"));
    return { ok: true };
  });

  await check(L, "RAPM is offered only for its season (a RAPM view falls back on another season)", async () => {
    const seasons = await page.locator('select[name="season"] option').evaluateAll((os) => os.map((o) => o.value));
    if (seasons.length < 2) return { ok: true, detail: "one season only, skipped" };
    await page.locator('select[name="metric"]').selectOption("rapm").catch(() => {});
    const hasRapm = await page.locator('select[name="metric"] option[value="rapm"]').count();
    if (!hasRapm) return { ok: true, detail: "no RAPM board in the data, skipped" };
    const current = await page.locator('select[name="season"]').inputValue();
    const other = seasons.find((s) => s !== current);
    await page.locator('select[name="season"]').selectOption(other);
    await until(page, () => document.querySelector('select[name="metric"]')?.value !== "rapm", undefined, 8000);
    const metric = await page.locator('select[name="metric"]').inputValue();
    return { ok: metric !== "rapm", detail: `metric now ${metric} in ${other}` };
  });

  await check(L, "phone: Show all reveals the full list", async () => {
    const p2 = await open(browser, "/players/?top=0", { width: 390 }); // all ranked: more than 50 rows
    const more = p2.page.locator("#more");
    if (!(await more.isVisible())) {
      await p2.context.close();
      return { ok: true, detail: "fewer rows than the phone cut, skipped" };
    }
    const label = await more.textContent();
    await more.click();
    const hidden = !(await p2.page.locator("#more").isVisible());
    errorCheck("Players 390 Show all", p2.errors);
    await p2.context.close();
    return { ok: hidden, detail: label.trim() };
  });

  await check(L, "phone: column group radio switches the columns", async () => {
    const p2 = await open(browser, "/players/", { width: 390 });
    const before = await p2.page.locator("#players").getAttribute("data-set");
    // Group 2 is the first Shooting group (groups 0 and 1 are Box score). Click it by its label.
    // The radios sit inside their labels and are visually hidden: click the input itself.
    await p2.page.locator('input[name="cols"]').nth(2).evaluate((el) => el.click());
    await until(p2.page, () => document.getElementById("players")?.dataset.set === "shooting", undefined, 8000);
    const after = await p2.page.locator("#players").getAttribute("data-set");
    errorCheck("Players 390 cols", p2.errors);
    await p2.context.close();
    return { ok: after === "shooting", detail: `set ${before} -> ${after}` };
  });

  errorCheck(L, errors);
  await context.close();
  await layoutCheck(browser, L, "/players/");
}

async function playerPage(browser, slug) {
  const L = "Player";
  const path = `/players/${slug}/`;
  const { context, page, errors } = await open(browser, path);

  await check(L, "zone chip filters the shot charts", async () => {
    const chip = page.locator("#shots .chip[data-zone]:not([data-zone=''])").first();
    const zone = await chip.getAttribute("data-zone");
    const count0 = await page.locator('#shots [data-f="count"]').textContent();
    const dots0 = await page.locator("#court-dots").innerHTML();
    const freq0 = await page.locator("#court-freq").innerHTML();
    await chip.click();
    await until(page, (a) => document.querySelector("#court-dots")?.innerHTML !== a, dots0);
    const pressed = await chip.getAttribute("aria-pressed");
    const zoneLine = await page.locator('#shots [data-f="zone"]').isVisible();
    const freq1 = await page.locator("#court-freq").innerHTML();
    const count1 = await page.locator('#shots [data-f="count"]').textContent();
    return {
      ok: pressed === "true" && zoneLine && freq1 !== freq0,
      detail: `${zone}: count "${count0.trim()}" -> "${count1.trim()}"`,
    };
  });
  await page.locator('#shots .chip[data-zone=""]').click();

  await check(L, "2PT / 3PT filter narrows the attempts", async () => {
    const before = await page.locator('#shots [data-f="count"]').textContent();
    await page.locator('label[for="sf-3"]').click();
    await until(page, (b) => document.querySelector('#shots [data-f="count"]')?.textContent !== b, before);
    const after = await page.locator('#shots [data-f="count"]').textContent();
    await page.locator('label[for="sf-all"]').click();
    return { ok: true, detail: `"${before.trim()}" -> "${after.trim()}"` };
  });

  await check(L, "shot season switch redraws the charts", async () => {
    const sel = page.locator('#shots select[data-view="shots"]').first();
    const options = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value));
    const current = await sel.inputValue();
    const other = options.find((v) => v !== current);
    if (!other) return { ok: true, detail: "one season only, skipped" };
    const before = await page.locator("#court-dots").innerHTML();
    await sel.selectOption(other);
    await until(page, (b) => document.querySelector("#court-dots")?.innerHTML !== b, before);
    return { ok: true, detail: `${current} -> ${other}` };
  });

  await check(L, "League / Position switch changes the rail", async () => {
    if (!(await page.locator("#lg-pos").count())) return { ok: true, detail: "no position pool, skipped" };
    await page.locator('label[for="lg-pos"]').click();
    const shown = await page.locator(".lg-rows .pos-only").first().isVisible();
    const hidden = !(await page.locator(".lg-rows .league-only").first().isVisible());
    await page.locator('label[for="lg-league"]').click();
    return { ok: shown && hidden, detail: `pos visible ${shown}, league hidden ${hidden}` };
  });

  await check(L, "On/off and Clutch season panels switch", async () => {
    const sel = page.locator('select[data-view="stint"]').first();
    const options = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value));
    const pick = options[options.length - 1];
    await sel.selectOption(pick);
    const visible = await page.locator("[data-stint]:visible").evaluateAll((els) => [...new Set(els.map((e) => e.dataset.stint))]);
    return { ok: visible.length === 1 && visible[0] === pick, detail: `season ${pick} visible: ${visible.join(",")}` };
  });

  await check(L, "game log season switch redraws the log", async () => {
    const sel = page.locator('select[data-view="log"]').first();
    if (!(await sel.count())) return { ok: true, detail: "no log select, skipped" };
    // The log picker sits inside the closed "Full game log" disclosure.
    await page.locator("#full-log > summary").click();
    const options = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value));
    const current = await sel.inputValue();
    const other = options.find((v) => v !== current);
    if (!other) return { ok: true, detail: "one season only, skipped" };
    const before = await page.locator("#log-body").innerHTML();
    await sel.selectOption(other);
    await until(page, (b) => document.querySelector("#log-body")?.innerHTML !== b, before);
    return { ok: true };
  });

  record(L, "tabs: not applicable (the player page has no tabs)", true, "N/A");

  errorCheck(L, errors);
  await context.close();
  await layoutCheck(browser, L, path);
}

async function teamPage(browser, code) {
  const L = "Team";
  const path = `/teams/${code}/`;
  const { context, page, errors } = await open(browser, path);

  await check(L, "tab click shows its panel and sets the hash", async () => {
    await page.locator("#tab-shots").click();
    const shown = await page.locator("#panel-shots").isVisible();
    const hidden = await page.locator("#panel-overview").isHidden();
    const hash = await page.evaluate(() => location.hash);
    return { ok: shown && hidden && hash === "#shots", detail: `hash ${hash}` };
  });

  await check(L, "tabs: arrow keys move between tabs", async () => {
    await page.locator("#tab-overview").click(); // start from Overview, whatever the last check left selected
    await page.keyboard.press("ArrowRight");
    const shots = await page.locator("#panel-shots").isVisible();
    const focused = await page.evaluate(() => document.activeElement?.id);
    // End goes to the last visible tab (Schedule on the live season, Passing on a past one).
    await page.keyboard.press("End");
    const last = await page.locator('[role="tab"]:not([hidden])').last();
    const lastOn = (await last.getAttribute("aria-selected")) === "true" && (await page.locator(`#${await last.getAttribute("aria-controls")}`).isVisible());
    await page.keyboard.press("Home");
    const overview = await page.locator("#panel-overview").isVisible();
    return { ok: shots && focused === "tab-shots" && lastOn && overview, detail: `focus ${focused}, End selects last tab: ${lastOn}` };
  });

  await check(L, "deep link #passing opens the Passing tab", async () => {
    const p2 = await open(browser, `${path}#passing`);
    const shown = await p2.page.locator("#panel-passing").isVisible();
    const over = await p2.page.locator("#panel-overview").isHidden();
    const sel = await p2.page.locator("#tab-passing").getAttribute("aria-selected");
    errorCheck("Team #passing", p2.errors);
    await p2.context.close();
    return { ok: shown && over && sel === "true" };
  });

  await check(L, "zone chips filter the attempts chart, zone table and heatmaps", async () => {
    await page.locator("#tab-shots").click();
    await until(page, () => document.querySelector("#attempts-court")?.innerHTML.length > 0, undefined, 15000);
    const court0 = await page.locator("#attempts-court").innerHTML();
    const heat0 = await page.locator("#court-taken").innerHTML();
    const zone0 = await page.locator("#zone-body").innerHTML();
    await page.locator('#panel-shots .chip[data-zone]:not([data-zone=""])').first().click();
    await until(page, (c) => document.querySelector("#attempts-court")?.innerHTML !== c, court0);
    await until(page, (h) => document.querySelector("#court-taken")?.innerHTML !== h, heat0, 8000).catch(() => {});
    const heat1 = await page.locator("#court-taken").innerHTML();
    const zone1 = await page.locator("#zone-body").innerHTML();
    await page.locator('#panel-shots .chip[data-zone=""]').click();
    return {
      ok: heat1 !== heat0 && zone1 !== zone0,
      detail: `heatmap ${heat1 !== heat0 ? "changed" : "UNCHANGED"}, zone table ${zone1 !== zone0 ? "changed" : "UNCHANGED"}`,
    };
  });

  await check(L, "season select redraws the club header", async () => {
    const sel = page.locator("#season");
    if (!(await sel.count())) return { ok: true, detail: "one season only, skipped" };
    const options = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value));
    const current = await sel.inputValue();
    const other = options.find((v) => v !== current);
    if (!other) return { ok: true, detail: "one season only, skipped" };
    const before = await page.locator("#c-record").innerHTML();
    await sel.selectOption(other);
    await until(page, (b) => document.querySelector("#c-record")?.innerHTML !== b, before, 10000);
    await until(page, () => location.search.includes("season="), undefined);
    return { ok: true, detail: `${current} -> ${other}` };
  });

  await check(L, "Lineups tab: sort buttons re-order the duos", async () => {
    await page.locator("#tab-lineups").click();
    if (await page.locator("#lineups-note").isVisible()) return { ok: true, detail: "no lineups this season, skipped" };
    const btn = page.locator('button.sort[data-table="duos"][data-by="minutes"]');
    await btn.click();
    const pressed = await btn.getAttribute("aria-pressed");
    return { ok: pressed === "true" };
  });

  await check(L, "Passing tab renders the assist network (a past season with data)", async () => {
    // The live season has no assist file yet, so the tab says so; use a finished season.
    // (The club must play in that season: OLY is in every EuroLeague season.)
    await page.goto(`${BASE}${path}?season=2025#passing`, { waitUntil: "load" });
    await page.locator("#tab-passing").click();
    const visible = await page.locator("#passing").isVisible();
    const drawn = await page.locator("#passing svg, #passing table").count();
    return { ok: visible && drawn > 0, detail: `${drawn} svg/table nodes` };
  });

  errorCheck(L, errors);
  await context.close();
  await layoutCheck(browser, L, path);
}

async function comparePage(browser) {
  const L = "Compare";
  const { context, page, errors } = await open(browser, "/compare/");

  await check(L, "three curated presets show at random", async () => {
    const n = await page.locator("#presets > li:not([hidden])").count();
    return { ok: n === 3, detail: `${n} visible` };
  });

  await check(L, "season with no pool (2021-22) is named, the 2022 player still draws", async () => {
    // Moustapha Fall has player totals for 2021-22 but the site has no pool file for that season.
    const p2 = await open(browser, "/compare/?p=moustapha-fall:2021,sasha-vezenkov:2022");
    await p2.page.waitForSelector("#board:not([hidden]) tbody tr", { timeout: 15000 });
    await p2.page.waitForFunction(() => document.querySelector("#profile-status")?.textContent?.includes("No percentile pool"), undefined, { timeout: 15000 });
    const status = await p2.page.locator("#profile-status").textContent();
    const shapes = await p2.page.locator("#profile-figure .shape").count(); // one per drawn player (rings are not shapes)
    errorCheck("Compare no-pool season", p2.errors);
    await p2.context.close();
    return { ok: shapes === 1 && status.includes("Moustapha Fall"), detail: `${shapes} shape(s); "${status.trim()}"` };
  });

  await check(L, "remove (x) drops a player from the board", async () => {
    const p2 = await open(browser, "/compare/");
    await p2.page.locator("#presets li:not([hidden]) a").first().click();
    await p2.page.waitForSelector("#board:not([hidden]) tbody tr", { timeout: 15000 });
    const before = await p2.page.locator("#board thead th").count();
    await p2.page.locator("#board button[data-drop]").first().click();
    await until(p2.page, (n) => document.querySelectorAll("#board thead th").length !== n, before, 10000);
    const after = await p2.page.locator("#board thead th").count();
    errorCheck("Compare remove", p2.errors);
    await p2.context.close();
    return { ok: after < before, detail: `header cells ${before} -> ${after}` };
  });

  await check(L, "per-player season select changes that column", async () => {
    const p2 = await open(browser, "/compare/");
    await p2.page.locator("#add").focus();
    await p2.page.waitForFunction(() => document.querySelectorAll("#names option").length > 0, undefined, { timeout: 10000 });
    // A player with several seasons: try the first few names until one has a season select.
    const names = await p2.page.locator("#names option").evaluateAll((os) => os.slice(0, 40).map((o) => o.value));
    let found = false;
    for (const name of names) {
      await p2.page.locator("#add").fill(name);
      await p2.page.locator("#add").press("Enter");
      await p2.page.waitForSelector("#board:not([hidden]) tbody tr", { timeout: 15000 });
      if (await p2.page.locator('#board select[data-col="0"]').count()) {
        found = true;
        break;
      }
      await p2.page.locator("#board button[data-drop]").first().click();
      await p2.page.waitForTimeout(300);
    }
    if (!found) {
      errorCheck("Compare season select", p2.errors);
      await p2.context.close();
      return { ok: true, detail: "no multi-season player among the first 40 names, skipped" };
    }
    const sel = p2.page.locator('#board select[data-col="0"]');
    const opts = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value));
    const current = await sel.inputValue();
    const other = opts.find((v) => v !== current);
    const before = await p2.page.locator("#board").innerHTML();
    await sel.selectOption(other);
    await until(p2.page, (b) => document.querySelector("#board")?.innerHTML !== b, before, 10000);
    errorCheck("Compare season select", p2.errors);
    await p2.context.close();
    return { ok: true, detail: `${current} -> ${other}` };
  });

  await check(L, "preset link opens the comparison board", async () => {
    const p2 = await open(browser, "/compare/");
    await p2.page.locator("#presets li:not([hidden]) a").first().click();
    await p2.page.waitForURL(/[?&]p=/, { timeout: 10000 });
    await p2.page.waitForSelector("#board:not([hidden]) tbody tr", { timeout: 15000 });
    const cols = await p2.page.locator("#board thead th").count();
    errorCheck("Compare preset", p2.errors);
    await p2.context.close();
    return { ok: cols > 1, detail: `${cols} header cells` };
  });

  await check(L, "add a player by name shows a board", async () => {
    await page.locator("#add").focus();
    await page.waitForFunction(() => document.querySelectorAll("#names option").length > 0, undefined, { timeout: 10000 });
    const name = await page.locator("#names option").nth(3).evaluate((o) => o.value);
    await page.locator("#add").fill(name);
    await page.locator("#add").press("Enter");
    await page.waitForSelector("#board:not([hidden]) tbody tr", { timeout: 15000 });
    return { ok: true, detail: name };
  });

  await check(L, "percentile polygon renders for the picked player", async () => {
    await page.waitForFunction(() => !document.getElementById("profile")?.hasAttribute("hidden"), undefined, { timeout: 15000 });
    const shapes = await page.locator("#profile-figure .shape").count(); // one per drawn player (rings are not shapes)
    return { ok: shapes > 0, detail: `${shapes} shape(s)` };
  });

  await check(L, "axis checkbox redraws the polygon", async () => {
    const before = await page.locator("#profile-figure").innerHTML();
    const box = page.locator('input[name="profile-axis"]:checked').first();
    await box.uncheck({ force: true });
    await until(page, (b) => document.querySelector("#profile-figure")?.innerHTML !== b, before, 8000);
    await box.check({ force: true });
    return { ok: true };
  });

  errorCheck(L, errors);
  await context.close();
  await layoutCheck(browser, L, "/compare/");
}

async function leadersPage(browser) {
  const L = "Leaders";
  const { context, page, errors } = await open(browser, "/leaders/");

  await check(L, "boards render", async () => {
    const n = await page.locator("#boards").evaluateAll((els) => els.length ? els[0].querySelectorAll("a").length : 0);
    return { ok: n > 0, detail: `${n} links in boards` };
  });

  await check(L, "season select redraws the boards", async () => {
    const sel = page.locator('#filters select[name="season"]');
    const opts = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value));
    const current = await sel.inputValue();
    const other = opts.find((v) => v !== current);
    const before = await page.locator("#boards").innerHTML();
    await sel.selectOption(other);
    await until(page, (b) => document.querySelector("#boards")?.innerHTML !== b, before, 10000);
    return { ok: true, detail: `${current} -> ${other}` };
  });

  await check(L, "Career scope redraws the boards", async () => {
    const before = await page.locator("#boards").innerHTML();
    await page.locator('#filters input[name="scope"][value="career"]').evaluate((el) => el.click());
    await until(page, (b) => document.querySelector("#boards")?.innerHTML !== b, before, 10000);
    await page.locator('#filters input[name="scope"][value="season"]').evaluate((el) => el.click());
    return { ok: true };
  });

  await check(L, "each board's Full list link opens Players with its metric", async () => {
    const hrefs = await page.locator('#boards a:text("Full list")').evaluateAll((as) => as.map((a) => a.getAttribute("href")));
    const bad = [];
    for (const href of hrefs) {
      const m = new URL(href, BASE).searchParams.get("metric");
      const p2 = await open(browser, href.replace(/^https?:\/\/[^/]+/, ""));
      const got = await p2.page.locator('select[name="metric"]').inputValue();
      if (got !== m) bad.push(`${m}->${got}`);
      errorCheck(`Leaders link ${m}`, p2.errors);
      await p2.context.close();
    }
    return { ok: hrefs.length > 0 && bad.length === 0, detail: `${hrefs.length} links${bad.length ? `, wrong: ${bad.join(" ")}` : ""}` };
  });

  errorCheck(L, errors);
  await context.close();
  await layoutCheck(browser, L, "/leaders/");
}

const browser = await chromium.launch({ channel: CHANNEL });
try {
  const { firstPlayer, errors } = await discover(browser);
  errorCheck("Players (discovery)", errors);
  await playersPage(browser);
  if (firstPlayer) await playerPage(browser, firstPlayer);
  else record("Player", "a player page to open", false, "no player link found on /players/");
  await teamPage(browser, "oly");
  await comparePage(browser);
  await leadersPage(browser);
} finally {
  await browser.close();
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
for (const r of failed) console.log(`  FAILED: ${r.page} | ${r.check}${r.detail ? ` (${r.detail})` : ""}`);
process.exit(failed.length ? 1 : 0);
