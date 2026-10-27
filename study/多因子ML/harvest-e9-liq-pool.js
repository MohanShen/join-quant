// node -e "require('./study/多因子ML/harvest-e9-liq-pool.js')"
//
// Companion to harvest-e9-liq.js: the census logs candidate COUNTS, not the kept NAMES, so
// "never removed" means "never below the floor WHEN PRESENT" and says nothing about a pool member
// that never became a candidate. The book's own `得分` print (top-5 of the unfiltered ranking)
// is the free way to see which pool members ever ranked at all — which is what the dispatch's
// watchlist (161226 国投白银, 501018 南方原油, 159985 豆粕, 159652) needs answering.
const { chromium } = require('playwright');

const ALG = process.env.LIQ_ALG || '2c066da1f4eadf181fbce95b1fef36c3';
const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';
const POOL = ['513100.XSHG', '159525.XSHE', '513130.XSHG', '159915.XSHE', '159628.XSHE',
  '588120.XSHG', '513520.XSHG', '513030.XSHG', '518880.XSHG', '161226.XSHE',
  '159985.XSHE', '501018.XSHG', '159652.XSHE', '511090.XSHG'];

(async () => {
  const browser = await chromium.connectOverCDP(CDP);
  let res;
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    res = await page.evaluate(async (alg) => {
      const txt = async u => (await fetch(u, { credentials: 'include' })).text();
      const t = await txt(`/algorithm/backtest/buildList?algorithmId=${alg}`);
      const ids = [...new Set([...t.matchAll(/backtestId[=":\s]+([a-f0-9]{32})/g)].map(m => m[1]))];
      const bid = ids[0];
      if (!bid) return { err: 'no backtest for ' + alg };
      const keep = [];
      let offset = 0;
      for (let p = 0; p < 600; p++) {
        const j = JSON.parse(await txt(`/algorithm/backtest/log?backtestId=${bid}&offset=${offset}&limit=100&ajax=1`));
        const arr = (j.data && j.data.logArr) || [];
        if (!arr.length) break;
        for (const l of arr) if (String(l).includes('得分:') || String(l).includes('LIQFLOOR sleeve=etf')) keep.push(String(l));
        offset += arr.length;
        if (arr.length < 100) break;
      }
      return { bid, keep };
    }, ALG);
  } finally { try { await browser.close(); } catch { /* detach */ } }

  if (res.err) { console.error('FATAL', res.err); process.exitCode = 1; return; }

  const ranked = {}, rankPos = {}, removedCount = {};
  for (const l of res.keep) {
    const m = l.match(/\s(\d)\.\s+(\d{6}\.[A-Z]{4})/);
    if (m) {
      ranked[m[2]] = (ranked[m[2]] || 0) + 1;
      rankPos[m[2]] = rankPos[m[2]] || {};
      rankPos[m[2]][m[1]] = (rankPos[m[2]][m[1]] || 0) + 1;
    }
    const r = l.match(/LIQFLOOR sleeve=etf .* removed=([^\s]+)/);
    if (r && r[1] !== '-') for (const n of r[1].split(';')) removedCount[n] = (removedCount[n] || 0) + 1;
  }
  console.log(`backtestId ${res.bid}  ${res.keep.length} relevant lines\n`);
  console.log('ETF pool member        | days in the book\'s printed top-5 | days removed by the floor | rank histogram');
  for (const c of POOL) {
    console.log(`${c}  ${String(ranked[c] || 0).padStart(5)}  ${String(removedCount[c] || 0).padStart(10)}   ` +
      JSON.stringify(rankPos[c] || {}));
  }
  const never = POOL.filter(c => !ranked[c] && !removedCount[c]);
  console.log(`\nnever seen in a top-5 print NOR in a removal (⇒ this run says nothing about them): ${never.join(' ') || '(none)'}`);
})().catch(e => { console.error('FATAL', e.message); process.exitCode = 1; });
