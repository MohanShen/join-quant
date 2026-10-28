// Free realizability evidence for wg-e9-9498 (= 9498d93f pinned): page the WHOLE 日志 tab of the
// book's TRAIN and VAL runs and count what the engine and the strategy said about fills.
// backtest-log.js fetches a single page (the endpoint serves 100 lines regardless of `limit`), so
// this pages by offset until a short page. Backtest ids come from the stored curves — JQ re-mints
// ids per request but old ids still dereference.
// Usage: node -e "require('./study/网格/log-scan-e9.js')"
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const ROOT = path.join(__dirname, '../..');
const KEY = '2026-07-01_多ETF网格交易策略-年化10_61-9498d93f';

const PATTERNS = {
  gridBuy: /网格买入 -/,
  gridSell: /网格卖出 -/,
  initial: /初始建仓完成/,
  cashShort: /资金不足/,
  posShort: /持仓不足|可卖出数量不足/,
  orderFail: /失败/,
  // engine-side fill warnings: volume cap, partial fill, suspended, limit price
  engine: /成交量|部分成交|停牌|涨停|跌停|order_volume_ratio|not filled|未成交|撤单/,
  error: /ERROR|Traceback|异常/,
};

async function scan(page, bid) {
  const counts = Object.fromEntries(Object.keys(PATTERNS).map(k => [k, 0]));
  const samples = Object.fromEntries(Object.keys(PATTERNS).map(k => [k, []]));
  let offset = 0, total = 0;
  for (;;) {
    const arr = await page.evaluate(async ({ bid, offset }) => {
      const r = await fetch(`/algorithm/backtest/log?backtestId=${bid}&offset=${offset}&limit=100&ajax=1`,
        { credentials: 'include' });
      const t = await r.text();
      try { const j = JSON.parse(t); return (j.data && j.data.logArr) || []; } catch { return null; }
    }, { bid, offset });
    if (arr === null) throw new Error(`unparseable log page at offset ${offset}`);
    for (const l of arr) {
      for (const [k, re] of Object.entries(PATTERNS)) {
        if (re.test(String(l))) { counts[k]++; if (samples[k].length < 3) samples[k].push(String(l).slice(0, 200)); }
      }
    }
    total += arr.length;
    offset += arr.length;
    if (arr.length < 100) break;
  }
  return { lines: total, counts, samples };
}

(async () => {
  const browser = await chromium.connectOverCDP(process.env.JQ_CDP_URL || 'http://localhost:9225');
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    const out = {};
    for (const w of ['train', 'val']) {
      const s = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series', `${KEY}__${w}__e9.json`), 'utf8'));
      out[w] = { backtestId: s.backtestId, ...(await scan(page, s.backtestId)) };
    }
    console.log(JSON.stringify(out, null, 1));
  } finally {
    try { await browser.close(); } catch { /* detach only */ }
  }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
