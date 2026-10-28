import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { lastmodFor, readDates } from "./scripts/sitemap-lastmod.mjs";

// Each page's <lastmod> is the date its data last changed (scripts/sitemap-lastmod.mjs); static
// pages have none. Without the stats data (before the first data build) there are no dates.
const statsDir = fileURLToPath(new URL("./src/data/stats/", import.meta.url));
const dates = existsSync(statsDir) ? readDates(statsDir) : null;

// Built into ../site, which the daily workflow uploads to Cloudflare.
export default defineConfig({
  site: "https://675hoops.com",
  base: "/",
  outDir: "../site",
  trailingSlash: "ignore",
  integrations: [
    sitemap({
      filter: (page) => !new URL(page).pathname.startsWith("/cards/"),
      serialize: (item) => {
        const day = dates ? lastmodFor(item.url, dates) : undefined;
        return day ? { ...item, lastmod: day } : item;
      },
    }),
  ],
  // The removed Scouting and Shots pages redirect with real 301s in public/_redirects.
  build: { inlineStylesheets: "auto" },
  // Start loading a linked page on hover or tap, so the next page opens almost at once.
  prefetch: { prefetchAll: true, defaultStrategy: "hover" },
  // Scope component styles with an astro-* class rather than a data-astro-cid-* attribute: the
  // same specificity (one class = one attribute), but ~9 bytes shorter on every scoped element.
  scopedStyleStrategy: "class",
});
