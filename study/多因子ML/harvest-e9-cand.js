// node -e "require('./study/多因子ML/harvest-e9-cand.js')"
//
// Harvest the xp-e9-1 LIQFLOOR census out of its backtest's 日志 tab. Same paging shape as
// harvest-e9-liq.js (`/algorithm/backtest/log` caps a page at 100 lines regardless of `limit`,
// so a single call would return only the first few weeks), filtering inside the browser so the
// whole log never crosses the bridge. The backtestId is resolved in-session, never stored (ids
// are re-minted per request).
//
// What this is for: the combined candidate's TRAIN curve came out BIT-IDENTICAL to q-e9-liq-1's
// (max|Delta cum| = 0.000000pp over 242 days). Two very different things produce that —
//   (a) the pit edit is genuinely subsumed by the floor (the floor already rejected 159525 on
//       every day it would have been selected), or
//   (b) a code path did not run.
// `no-trades` and "the code path never ran" are different things, so this is the control: the
// census must show the floor RUNNING and REMOVING names, and 159525 must appear ZERO times in it
// (it is commented out of the pool, so the floor can never even see it — whereas under liq-1 it
// was the most-removed name, 63 times).
const path = require('path');
const { chromium } = require('playwright');

const ALG = process.env.CAND_ALG || '65a32826920b113d5cf0febf96e1c86b';
const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';
const PIT_CODE = '159525';

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
      if (!bid) return { err: 'no backtest for algorithm ' + alg };
      const err = await txt(`/algorithm/backtest/error?backtestId=${bid}&ajax=1`);

      const liq = [];
      let total = 0, offset = 0, pages = 0, state = null;
      for (; pages < 600; pages++) {
        const raw = await txt(`/algorithm/backtest/log?backtestId=${bid}&offset=${offset}&limit=100&ajax=1`);
        let j;
        try { j = JSON.parse(raw); } catch { return { err: 'unparsed page at offset ' + offset, bid }; }
        const arr = (j.data && j.data.logArr) || [];
        state = (j.data && j.data.state) || state;
        if (!arr.length) break;
        total += arr.length;
        for (const l of arr) if (String(l).includes('LIQFLOOR') || String(l).includes('得分:')) liq.push(String(l));
        offset += arr.length;
        if (arr.length < 100) break;
      }
      return { bid, state, total, pages: pages + 1, liq, errTab: err.slice(0, 600) };
    }, ALG);
  } finally {
    try { await browser.close(); } catch { /* detach only */ }
  }

  if (res.err) { console.error('FATAL', res.err); process.exitCode = 1; return; }
  console.log(`backtestId ${res.bid}  state=${res.state}  ${res.total} log lines over ${res.pages} page(s)`);
  console.log(`LIQFLOOR + 得分 lines kept: ${res.liq.length}`);
  const tracebacks = /Traceback|Error/.test(res.errTab);
  console.log(`错误 tab: ${tracebacks ? 'CARRIES AN ERROR -> ' + res.errTab.slice(0, 300) : 'clean'}`);

  // rank-1 of the book's own momentum print, keyed by the log timestamp (same bar as the census)
  const rank1 = new Map();
  for (const l of res.liq) {
    const m = l.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?\s1\.\s+(\d{6}\.[A-Z]{4})/);
    if (m && !rank1.has(m[1])) rank1.set(m[1], m[2]);
  }

  const rows = [];
  let errLines = 0, emptyLines = 0;
  for (const l of res.liq) {
    if (!l.includes('LIQFLOOR')) continue;
    if (l.includes('LIQFLOOR ERROR')) { errLines++; console.log('  ERROR LINE: ' + l); continue; }
    const ts = (l.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/) || [])[1] || null;
    const f = {};
    for (const m of l.matchAll(/(\w+)=([^\s]+)/g)) f[m[1]] = m[2];
    if (f.status === 'empty') emptyLines++;
    rows.push({
      sleeve: f.sleeve, site: f.site, date: f.date, floor: Number(f.floor),
      in: Number(f.in), out: Number(f.out),
      removedFrac: f.removedFrac === 'NA' ? 0 : Number(f.removedFrac),
      slots: Number(f.slots), removed: f.removed === '-' ? [] : String(f.removed).split(';'),
      status: f.status, ts, rank1: ts ? (rank1.get(ts) || null) : null, raw: l,
    });
  }
  console.log(`parsed ${rows.length} census rows (${errLines} ERROR, ${emptyLines} empty-input)`);

  const bySleeve = {};
  for (const r of rows) {
    const b = bySleeve[r.sleeve] = bySleeve[r.sleeve] || { calls: 0, withRemoval: 0, removedNames: {}, sites: {}, empty: 0, ins: [], outs: [] };
    b.calls++; b.sites[r.site] = (b.sites[r.site] || 0) + 1;
    if (r.status === 'empty') { b.empty++; return; }
    if (r.in > r.out) b.withRemoval++;
    for (const n of r.removed) b.removedNames[n] = (b.removedNames[n] || 0) + 1;
    b.ins.push(r.in); b.outs.push(r.out);
  }
  console.log('\n===== per-sleeve LIQFLOOR census =====');
  for (const k of ['small_cap', 'etf', 'white_horse']) {
    const b = bySleeve[k];
    if (!b) { console.log(`${k}: NO CALLS — the code path never ran`); continue; }
    const names = Object.entries(b.removedNames).sort((a, c) => c[1] - a[1]);
    console.log(`${k}  sites ${JSON.stringify(b.sites)}  calls ${b.calls} (empty ${b.empty})  calls removing a name ${b.withRemoval}`);
    console.log(`  candidates in -> out: med ${b.ins.sort((x, y) => x - y)[b.ins.length >> 1]} -> ${b.outs.slice().sort((x, y) => x - y)[b.outs.length >> 1]}  | out==0 on ${b.outs.filter(o => o === 0).length} calls`);
    console.log(`  names removed (${names.length} distinct): ` + (names.slice(0, 12).map(([n, c]) => `${n}x${c}`).join(' ') || '(none)'));
  }

  // ── THE CONTROL: the pit-excluded code must be invisible to the floor
  const mentions = rows.filter(r => r.raw.includes(PIT_CODE));
  const removedPit = rows.reduce((s, r) => s + r.removed.filter(n => n.includes(PIT_CODE)).length, 0);
  console.log(`\n===== control: ${PIT_CODE} (the pit exclusion) =====`);
  console.log(`  census rows mentioning ${PIT_CODE}        : ${mentions.length}   (liq-1 removed it 63 times)`);
  console.log(`  times the floor REMOVED ${PIT_CODE}       : ${removedPit}`);
  console.log(`  ⇒ ${mentions.length === 0 ? 'the pool edit is LIVE: the floor never sees it, so it cannot be what the floor was removing any more'
    : 'UNEXPECTED: the name is still reaching the floor — the pool edit did not take effect'}`);

  // etf rank-1 overrides, the thing the floor's Delta runs through on this book
  const withR1 = rows.filter(r => r.sleeve === 'etf' && r.rank1);
  const over = withR1.filter(r => r.removed.includes(r.rank1));
  console.log(`\netf rank-1 overrides: ${over.length} of ${withR1.length} calls where the book's own #1 was floored out`);
  for (const r of over.slice(0, 20)) console.log(`  ${r.date}  #1 ${r.rank1} removed  (in ${r.in} -> out ${r.out})`);
})();
