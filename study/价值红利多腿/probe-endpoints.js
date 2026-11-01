// q-e9-sleeve-attrib helper (read-only, no backtest): find which /algorithm/backtest/* endpoints the
// result page uses, so the 2024-12-31 positions/close prices can be read from the run itself.
// Usage: node -e "require('./study/价值红利多腿/probe-endpoints.js').main()" -- <backtestId> [path...]
const { chromium } = require('playwright');
const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';

async function main() {
  const argv = process.argv.slice(1).filter(a => a !== '--');
  const bid = argv.find(a => /^[a-f0-9]{32}$/.test(a));
  const paths = argv.filter(a => a !== bid && a.startsWith('/'));
  const browser = await chromium.connectOverCDP(CDP);
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    if (!paths.length) {
      // Scan the summary page + its scripts for endpoint strings.
      const r = await page.evaluate(async (bid) => {
        const t = await (await fetch('/algorithm/backtest/detail?backtestId=' + bid, { credentials: 'include' })).text();
        const srcs = [...t.matchAll(/<script[^>]+src="([^"]+)"/g)].map(m => m[1]);
        const found = new Set();
        const scan = s => { for (const m of s.matchAll(/["'](\/algorithm\/[a-zA-Z\/]+)/g)) found.add(m[1]); };
        scan(t);
        for (const s of srcs) { try { scan(await (await fetch(s)).text()); } catch (e) {} }
        return { len: t.length, srcs, found: [...found].sort() };
      }, bid);
      console.log(JSON.stringify(r, null, 1));
    } else {
      for (const p of paths) {
        const u = p.replace('{bid}', bid);
        const t = await page.evaluate(async (u) => {
          const r = await fetch(u, { credentials: 'include' });
          return r.status + ' ' + (await r.text());
        }, u);
        console.log('== ' + u + '\n' + t.slice(0, 3000));
      }
    }
  } finally {
    try { await browser.close(); } catch (e) { /* detach only */ }
  }
}
module.exports = { main };
