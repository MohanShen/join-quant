/**
 * jq-budget.js — read the JoinQuant daily backtest budget via the CDP-authenticated
 * Chrome session (same auth path as strategy-post-backtest.js). Plain curl can't read it
 * because JQ's session cookies are httpOnly inside Chrome.
 *
 * Prints one line to stdout: `used=<min> free=<min>` (integers), or `used= free=` on failure.
 * Exit 0 = got a reading, 2 = could not read (CDP down / no logged-in page). Never throws.
 *
 * Used by scripts/autoresearch-loop.sh to skip a fire cheaply when the JQ budget is already
 * exhausted (so we don't spend Anthropic quota on a run that can't backtest anyway).
 */
const { chromium } = require('playwright');

async function main() {
  const CDP_URL = process.env.JQ_CDP_URL || 'http://localhost:9225';
  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP_URL);
    const ctx = browser.contexts()[0];
    const pages = await ctx.pages();
    const page = pages.find(p =>
      !p.url().startsWith('chrome://') &&
      !p.url().startsWith('about:') &&
      !p.url().includes('/user/login') &&
      p.url().includes('joinquant.com')
    ) || pages.find(p =>
      !p.url().startsWith('chrome://') &&
      !p.url().startsWith('about:') &&
      !p.url().includes('/user/login')
    );
    if (!page) { console.log('used= free='); process.exitCode = 2; return; }
    const d = await page.evaluate(async () => {
      try {
        const r = await fetch('/algorithm/index/statistics', { credentials: 'include' });
        const j = await r.json();
        return (j && j.data && j.data.duration) || null;
      } catch { return null; }
    });
    if (!d) { console.log('used= free='); process.exitCode = 2; return; }
    console.log(`used=${Math.round(d.used || 0)} free=${Math.round(d.free || 0)}`);
  } catch {
    console.log('used= free=');
    process.exitCode = 2;
  } finally {
    // NEVER close pages (destroys the CDP cookie context); just detach the connection.
    if (browser) { try { await browser.close(); } catch {} }
  }
}

main();
