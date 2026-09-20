#!/usr/bin/env node
/**
 * render-doc.js — render a standalone HTML doc to PNG.
 *
 * Why this exists rather than a one-off screenshot: `docs/assets/*.png` show LIVE FIGURES
 * (ledger counts, family/type counts, queue depths). A picture of those numbers goes stale
 * silently — it keeps looking authoritative while the repo moves underneath it. Committing
 * the renderer next to the source means the image can always be regenerated, and the HTML
 * stays the thing under review.
 *
 * ⚠ Uses Playwright's OWN bundled chromium (`chromium.launch()`), never the CDP browser on
 * port 9225. That one holds the logged-in JoinQuant session, and CLAUDE.md is explicit that
 * closing it invalidates the session and forces a re-login.
 *
 * The published artifact is wrapped in a skeleton (charset, viewport, small reset) that the
 * source file does not carry, so the same wrapper is reproduced here — otherwise the PNG
 * shows a page with a different ground and no safe-area padding than the live artifact.
 *
 * Usage:
 *   node scripts/render-doc.js docs/pipeline-map.html docs/assets/pipeline-map.png
 *   node scripts/render-doc.js <src.html> <out.png> [--theme dark] [--width 1200] [--scale 1.5]
 */

const fs = require('fs');
const path = require('path');

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const positional = argv.filter((a, i) => !a.startsWith('--') && !(i > 0 && argv[i - 1].startsWith('--')));

const SRC = positional[0];
const OUT = positional[1];
const THEME = arg('--theme', 'light');
const WIDTH = parseInt(arg('--width', '1200'), 10);
/** 1.5 is the legibility/size knee: identical to 2x on screen, ~29% smaller on disk. */
const SCALE = parseFloat(arg('--scale', '1.5'));

if (!SRC || !OUT) {
  console.error('usage: node scripts/render-doc.js <src.html> <out.png> [--theme light|dark] [--width N] [--scale N]');
  process.exit(2);
}

const skeleton = body => `<!doctype html><html data-theme="${THEME}"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
:root{color-scheme:light dark;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{margin:0;font:14px system-ui,-apple-system,sans-serif;background:#fafaf9}
img{max-width:100%}[hidden]{display:none!important}
</style></head><body>${body}</body></html>`;

(async () => {
  const { chromium } = require('playwright');
  const src = path.resolve(SRC);
  const out = path.resolve(OUT);
  fs.mkdirSync(path.dirname(out), { recursive: true });

  // A sibling temp file, so relative asset paths in the doc still resolve.
  const tmp = path.join(path.dirname(src), `.render-${process.pid}.html`);
  fs.writeFileSync(tmp, skeleton(fs.readFileSync(src, 'utf8')));

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({
      viewport: { width: WIDTH, height: 1000 },
      deviceScaleFactor: SCALE,
    });
    await page.goto('file://' + tmp, { waitUntil: 'networkidle' });
    // Webfonts land after networkidle; screenshotting early bakes in the fallback stack.
    await page.evaluate(() => (document.fonts ? document.fonts.ready : null));
    await page.waitForTimeout(800);
    await page.screenshot({ path: out, fullPage: true });

    const dim = await page.evaluate(() => ({
      w: document.documentElement.scrollWidth,
      h: document.documentElement.scrollHeight,
    }));
    const kb = (fs.statSync(out).size / 1024).toFixed(0);
    console.log(`[render] ${path.relative(process.cwd(), out)}  ${dim.w}x${dim.h} css px @${SCALE}x  ${kb} KB  (${THEME})`);
  } finally {
    try { fs.unlinkSync(tmp); } catch {}
    await browser.close();
  }
})().catch(e => {
  console.error(`[render] ${e.message}`);
  process.exit(1);
});
