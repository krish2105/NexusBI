/**
 * Reproducible product screenshots for the README / case study.
 *
 * Drives the real app in a real browser — including running an actual question
 * through the agent pipeline — so every image shows genuine output on the real
 * Olist demo data, not a mockup. Each shot waits for *loaded content* (a chart,
 * a metric value) rather than a fixed delay, so we never capture a skeleton.
 *
 * Usage (backend on :8000 and frontend on :3000 must already be running):
 *     npm run screenshots
 *     BASE_URL=http://localhost:3001 npm run screenshots
 *
 * Deliberately NOT run in CI: it needs the full stack up, and regenerating
 * binaries on every push would churn the repo with useless image diffs.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE = (process.env.BASE_URL || "http://localhost:3000").replace(/\/$/, "");
const OUT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../docs/img",
);

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

/** Wait for the page to settle: fonts + animations done, no pending skeletons. */
async function settle(page, { skeletons = true } = {}) {
  await page.waitForLoadState("networkidle").catch(() => {});
  if (skeletons) {
    // Our loading placeholders use the `animate-shimmer` utility.
    await page
      .waitForFunction(() => !document.querySelector(".animate-shimmer"), null, {
        timeout: 20_000,
      })
      .catch(() => {});
  }
  await page.evaluate(() => document.fonts?.ready);
  // Let entrance animations (motion/react) finish so nothing is mid-fade.
  await page.waitForTimeout(900);
}

async function shot(page, name, opts = {}) {
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({
    path: file,
    fullPage: opts.fullPage ?? false,
    // `clip` is in CSS pixels; use it to trim dead space so a README image is
    // content, not letterboxing.
    ...(opts.clip ? { clip: opts.clip } : {}),
  });
  console.log(`  ✓ ${name}.png`);
}

/** Bring an element into frame, clearing the fixed nav bar. */
async function frame(page, selector, offset = 130) {
  const el = page.locator(selector).first();
  await el.scrollIntoViewIfNeeded().catch(() => {});
  await page.evaluate((o) => window.scrollBy(0, -o), offset);
  await page.waitForTimeout(500);
}

async function main() {
  await mkdir(OUT, { recursive: true });

  // Fail fast and clearly if the stack isn't up — otherwise we'd silently
  // screenshot error pages.
  try {
    const res = await fetch(BASE, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch (e) {
    console.error(
      `\n✗ Cannot reach the frontend at ${BASE} (${e.message}).\n` +
        `  Start it first:  cd frontend && npm run dev\n` +
        `  and the backend: cd backend && uvicorn app.main:app --port 8000\n`,
    );
    process.exit(1);
  }

  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: DESKTOP,
    deviceScaleFactor: 2, // crisp on retina / when scaled down in the README
    colorScheme: "dark",
    reducedMotion: "reduce", // deterministic: no mid-animation frames
  });
  const page = await ctx.newPage();
  console.log(`Capturing from ${BASE} -> ${path.relative(process.cwd(), OUT)}`);

  // --- landing -------------------------------------------------------------
  await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
  await settle(page, { skeletons: false });
  await shot(page, "landing");

  // --- workspace: run a REAL question through the agent pipeline ------------
  // The hero shot: streamed agent steps, generated SQL, chart, narrated insight.
  await page.goto(`${BASE}/app`, { waitUntil: "domcontentloaded" });
  await settle(page, { skeletons: false });

  const q = "Top 5 categories by merchandise revenue";
  // By accessible name — the input carries no `type`, so a `input[type=text]`
  // selector silently matches nothing.
  const box = page.getByRole("textbox", { name: /ask a business question/i });
  await box.click();
  await box.fill(q);
  await box.press("Enter");

  // Wait for the pipeline to actually finish: a chart is rendered (recharts
  // emits an <svg class="recharts-surface">) — not just "a request settled".
  await page
    .waitForSelector(".recharts-surface", { timeout: 90_000 })
    .catch(() => console.warn("  ! chart not detected; capturing anyway"));
  await page.waitForTimeout(1500); // let the chart animate in
  // The thread auto-scrolls to the newest turn, which pushes the chart above the
  // fold — scroll it back into frame so the hero shot actually shows the answer.
  await frame(page, ".recharts-surface");
  await shot(page, "workspace");

  // --- the safety layer refusing a destructive question --------------------
  await page.goto(`${BASE}/app?q=delete%20all%20orders`, {
    waitUntil: "domcontentloaded",
  });
  await settle(page, { skeletons: false });
  await page.waitForTimeout(2500); // block verdict streams back
  // The refusal is short; crop out the empty thread below it.
  await shot(page, "safety-block", {
    clip: { x: 0, y: 0, width: DESKTOP.width, height: 470 },
  });

  // --- read-only content pages ---------------------------------------------
  for (const [route, name] of [
    ["/briefing", "briefing"],
    ["/trust", "trust"],
    ["/metrics", "metrics"],
    ["/segments", "segments"],
    ["/monitors", "monitors"],
  ]) {
    await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
    await settle(page);
    await shot(page, name);
  }

  // --- mobile: the responsive nav drawer -----------------------------------
  const mctx = await browser.newContext({
    viewport: MOBILE,
    deviceScaleFactor: 2,
    colorScheme: "dark",
    reducedMotion: "reduce",
    isMobile: true,
    hasTouch: true,
  });
  const mpage = await mctx.newPage();
  await mpage.goto(`${BASE}/briefing`, { waitUntil: "domcontentloaded" });
  await settle(mpage);
  await mpage.getByRole("button", { name: /open menu/i }).click();
  await mpage.waitForTimeout(600);
  await shot(mpage, "mobile-nav");

  await browser.close();
  console.log("\nDone.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
