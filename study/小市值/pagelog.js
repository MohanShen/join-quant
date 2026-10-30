/**
 * pagelog.js — read a backtest's 日志 tab IN FULL, by paging.
 *
 * ⚠ Why this exists: `/algorithm/backtest/log` serves **100 lines per request regardless of
 * `limit`** (it answers `max: false`), and `utils/backtest-log.js` fetches exactly one page. On a
 * chatty book that is the first few weeks only — the documented 2026-10-27 trap that made an
 * 886-line year read as seven weeks. This pages by `offset` in steps of the returned length until
 * a short page.
 *
 * Usage (from the repo root):
 *   node -e "require('./study/小市值/pagelog.js').main()" -- <backtestId> ['<grep re>']
 */
const { chromium } = require('playwright');
const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';

async function pageAll(bid) {
  const browser = await chromium.connectOverCDP(CDP);
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    let offset = 0, all = [], state = null, pages = 0, raw = null;
    for (;;) {
      const r = await page.evaluate(async (a) => {
        const u = '/algorithm/backtest/log?backtestId=' + a.bid +
                  '&offset=' + a.offset + '&limit=2000&ajax=1';
        const resp = await fetch(u, { credentials: 'include' });
        const t = await resp.text();
        try { return JSON.parse(t); } catch (e) { return { __raw: t.slice(0, 300) }; }
      }, { bid, offset });
      if (r.__raw) { raw = r.__raw; break; }
      const arr = (r.data && r.data.logArr) || [];
      state = (r.data && r.data.state) != null ? r.data.state : state;
      all = all.concat(arr);
      pages++;
      if (arr.length === 0) break;
      offset += arr.length;
      if (pages > 400) break;
    }
    return { state, pages, lines: all, raw };
  } finally {
    // NEVER close the page — it holds the CDP cookie context. Detach only.
    try { await browser.close(); } catch (e) { /* best effort */ }
  }
}

async function main() {
  const argv = process.argv.slice(1).filter(a => a !== '--');
  const bid = argv.find(a => /^[a-f0-9]{32}$/.test(a));
  const reStr = argv.find(a => a !== bid);
  if (!bid) { console.error('usage: pagelog.js <backtestId> [grep]'); process.exitCode = 1; return; }
  const r = await pageAll(bid);
  if (r.raw) console.error('UNPARSED ' + r.raw);
  console.log('state=' + r.state + ' pages=' + r.pages + ' lines=' + r.lines.length);
  const re = reStr ? new RegExp(reStr) : null;
  const out = re ? r.lines.filter(l => re.test(String(l))) : r.lines;
  console.log('matched=' + out.length);
  for (const l of out) console.log(String(l));
}

module.exports = { pageAll, main };
