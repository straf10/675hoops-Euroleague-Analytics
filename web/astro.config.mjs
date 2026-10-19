import { readFileSync } from "node:fs";
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

// The day the stats were last built (site.json's generated_at_utc, YYYY-MM-DD): every page's
// <lastmod>, since the pages change when the data does. Absent before the first data build.
const dataDate = (() => {
  try {
    const at = JSON.parse(readFileSync(new URL("./src/data/site.json", import.meta.url), "utf8")).generated_at_utc;
    return typeof at === "string" ? at.slice(0, 10) : undefined;
  } catch {
    return undefined;
  }
})();

// Built into ../site, which the daily workflow uploads to Cloudflare.
export default defineConfig({
  site: "https://675hoops.com",
  base: "/",
  outDir: "../site",
  trailingSlash: "ignore",
  integrations: [
    sitemap({
      filter: (page) => !new URL(page).pathname.startsWith("/cards/"),
      serialize: (item) => (dataDate ? { ...item, lastmod: dataDate } : item),
    }),
  ],
  // The removed Scouting and Shots pages redirect with real 301s in public/_redirects.
  build: { inlineStylesheets: "auto" },
  // Scope component styles with an astro-* class rather than a data-astro-cid-* attribute: the
  // same specificity (one class = one attribute), but ~9 bytes shorter on every scoped element.
  scopedStyleStrategy: "class",
});
