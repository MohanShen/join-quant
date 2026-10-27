// node -e "require('./study/多因子ML/harvest-e9-liq.js')"
//
// Harvest the q-e9-liq-1 LIQFLOOR census out of the backtest's 日志 tab, and compare its stored
// TRAIN curve against the parent's.
//
// ⚠ `/algorithm/backtest/log` caps a page at 100 lines regardless of `limit`, so
// `utils/backtest-log.js` (one call, limit=2000) returns only the FIRST 100 lines — on this run
// that is 17 LIQFLOOR lines out of a full year. This pages with `offset` and keeps only the
// LIQFLOOR lines, filtering inside the browser so the whole log never crosses the bridge.
//
// Ids are re-minted per request (CLAUDE.md), so the backtestId is resolved and used in the same
// session, never stored.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.join(__dirname, '../..');
const ALG = process.env.LIQ_ALG || '2c066da1f4eadf181fbce95b1fef36c3';
const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';

const PARENT_CURVE = path.join(ROOT, 'data/series/2026-06-28_高质量稳定上涨策略-d02cde29__train__e9.json');
const VARIANT_CURVE = path.join(ROOT, 'data/series/study_多因子ML_variants_q-e9-liq-1__train__e9.json');

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
        // LIQFLOOR = our census. 得分 = the book's own unfiltered momentum ranking print, which
        // runs AFTER the filter and therefore tells us whether the floor overrode its FIRST choice.
        for (const l of arr) if (String(l).includes('LIQFLOOR') || String(l).includes('得分:')) liq.push(String(l));
        offset += arr.length;
        if (arr.length < 100) break;
      }
      return { bid, state, total, pages: pages + 1, liq };
    }, ALG);
  } finally {
    try { await browser.close(); } catch { /* detach only */ }
  }

  if (res.err) { console.error('FATAL', res.err); process.exitCode = 1; return; }
  console.log(`backtestId ${res.bid}  state=${res.state}  ${res.total} log lines over ${res.pages} page(s)`);
  console.log(`LIQFLOOR lines: ${res.liq.length}`);

  // ------------------------------------------------------------------ parse the census
  // rank-1 of the book's own momentum ranking, keyed by the log timestamp (same bar as the census)
  const rank1 = new Map();
  for (const l of res.liq) {
    const m = String(l).match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?\s1\.\s+(\d{6}\.[A-Z]{4})/);
    if (m && !rank1.has(m[1])) rank1.set(m[1], m[2]);
  }

  const rows = [];
  let errLines = 0, emptyLines = 0;
  for (const l of res.liq) {
    if (!l.includes('LIQFLOOR')) continue;
    if (l.includes('LIQFLOOR ERROR')) { errLines++; console.log('  ERROR LINE: ' + l); continue; }
    const ts = (String(l).match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/) || [])[1] || null;
    const f = {};
    for (const m of l.matchAll(/(\w+)=([^\s]+)/g)) f[m[1]] = m[2];
    if (f.status === 'empty') emptyLines++;
    rows.push({
      sleeve: f.sleeve, site: f.site, date: f.date,
      floor: Number(f.floor), in: Number(f.in), out: Number(f.out),
      removedFrac: f.removedFrac === 'NA' ? 0 : Number(f.removedFrac),
      slots: Number(f.slots), removed: f.removed === '-' ? [] : String(f.removed).split(';'),
      status: f.status, ts, rank1: ts ? (rank1.get(ts) || null) : null,
    });
  }
  console.log(`parsed ${rows.length} census rows (${errLines} ERROR, ${emptyLines} empty-input)`);

  const bySleeve = {};
  for (const r of rows) {
    const k = r.sleeve;
    bySleeve[k] = bySleeve[k] || { calls: 0, withRemoval: 0, fullSlots: 0, removedNames: {}, fracs: [], floors: [], ins: [], outs: [], sites: {}, empty: 0 };
    const b = bySleeve[k];
    b.calls++;
    b.sites[r.site] = (b.sites[r.site] || 0) + 1;
    if (r.status === 'empty') { b.empty++; continue; }
    if (r.in > r.out) b.withRemoval++;
    if (r.slots >= Math.min(r.in, { small_cap: 6, etf: 1, white_horse: 20 }[k])) b.fullSlots++;
    for (const n of r.removed) b.removedNames[n] = (b.removedNames[n] || 0) + 1;
    b.fracs.push(r.removedFrac); b.floors.push(r.floor); b.ins.push(r.in); b.outs.push(r.out);
  }
  const q = (a, p) => { if (!a.length) return NaN; const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(p * (s.length - 1)))]; };
  console.log('\n===== per-sleeve LIQFLOOR statistics =====');
  for (const k of ['small_cap', 'etf', 'white_horse']) {
    const b = bySleeve[k];
    if (!b) { console.log(`${k}: NO CALLS — the code path never ran`); continue; }
    console.log(`\n${k}  (sites: ${JSON.stringify(b.sites)})`);
    console.log(`  calls                 : ${b.calls}  (empty-input ${b.empty})`);
    console.log(`  calls removing a name : ${b.withRemoval}  (${(100 * b.withRemoval / Math.max(1, b.calls - b.empty)).toFixed(1)}% of non-empty)`);
    console.log(`  removedFrac           : min ${q(b.fracs, 0).toFixed(4)}  med ${q(b.fracs, 0.5).toFixed(4)}  p90 ${q(b.fracs, 0.9).toFixed(4)}  max ${q(b.fracs, 1).toFixed(4)}  mean ${(b.fracs.reduce((a, c) => a + c, 0) / b.fracs.length).toFixed(4)}`);
    console.log(`  floor (CNY/day)       : min ${q(b.floors, 0).toExponential(3)}  med ${q(b.floors, 0.5).toExponential(3)}  max ${q(b.floors, 1).toExponential(3)}`);
    console.log(`  candidates in -> out  : med ${q(b.ins, 0.5)} -> ${q(b.outs, 0.5)}   (out==0 on ${b.outs.filter(o => o === 0).length} calls)`);
    console.log(`  slots filled          : full on ${b.fullSlots}/${b.calls - b.empty}`);
    const names = Object.entries(b.removedNames).sort((a, c) => c[1] - a[1]);
    console.log(`  names removed (${names.length} distinct): ` + (names.slice(0, 12).map(([n, c]) => `${n}x${c}`).join(' ') || '(none)'));
    if (k === 'etf') {
      const withR1 = rows.filter(r => r.sleeve === 'etf' && r.rank1);
      const overridden = withR1.filter(r => r.removed.includes(r.rank1));
      console.log(`  rank-1 resolved on      : ${withR1.length}/${b.calls} calls`);
      console.log(`  floor REMOVED the book's OWN rank-1 (i.e. changed the holding): ${overridden.length} calls`);
      const byName = {};
      overridden.forEach(r => { byName[r.rank1] = (byName[r.rank1] || 0) + 1; });
      console.log(`    rank-1 overridden by name: ` + (Object.entries(byName).map(([n, c]) => `${n}x${c}`).join(' ') || '(none)'));
      const dates = overridden.map(r => r.ts.slice(0, 10));
      console.log(`    first/last override day  : ${dates[0] || '-'} .. ${dates[dates.length - 1] || '-'}`);
    }
  }

  // ------------------------------------------------------------------ curve delta vs the parent
  console.log('\n===== curve delta vs parent =====');
  if (!fs.existsSync(VARIANT_CURVE)) { console.log('variant curve missing:', VARIANT_CURVE); return; }
  const P = JSON.parse(fs.readFileSync(PARENT_CURVE, 'utf8'));
  const V = JSON.parse(fs.readFileSync(VARIANT_CURVE, 'utf8'));
  console.log(`parent  ${P.points} pts ${P.start}..${P.end} final ${P.cum[P.cum.length - 1]}`);
  console.log(`variant ${V.points} pts ${V.start}..${V.end} final ${V.cum[V.cum.length - 1]}`);
  const pm = new Map(P.dates.map((t, i) => [t, P.cum[i]]));
  let maxAbs = 0, maxAt = null, firstDiff = null, shared = 0;
  V.dates.forEach((t, i) => {
    if (!pm.has(t)) return;
    shared++;
    const d = V.cum[i] - pm.get(t);
    if (Math.abs(d) > 1e-9 && !firstDiff) firstDiff = { t, d };
    if (Math.abs(d) > Math.abs(maxAbs)) { maxAbs = d; maxAt = t; }
  });
  console.log(`shared days ${shared}  max|Δcum| ${Math.abs(maxAbs).toFixed(4)}pp at ${maxAt}`);
  console.log(`first differing day: ${firstDiff ? firstDiff.t + '  Δ' + firstDiff.d.toFixed(4) + 'pp' : 'NONE — curves identical'}`);

  // ------------------------------------------------------------------ the verdict arithmetic
  const ctl = { annual: 156.71, maxdd: 9.40, sharpe: 5.45, obj: 1.4731 };
  const vr = { annual: 165.79, maxdd: 9.36, sharpe: 5.89 };
  vr.obj = Number(((vr.annual - vr.maxdd) / 100).toFixed(4));
  console.log('\n===== scores =====');
  console.log(`control  objective ${ctl.obj.toFixed(4)}  sharpe ${ctl.sharpe}  annual ${ctl.annual}  maxDD ${ctl.maxdd}`);
  console.log(`liq-1    objective ${vr.obj.toFixed(4)}  sharpe ${vr.sharpe}  annual ${vr.annual}  maxDD ${vr.maxdd}`);
  console.log(`Δ        objective ${(vr.obj - ctl.obj >= 0 ? '+' : '') + (vr.obj - ctl.obj).toFixed(4)}  sharpe ${(vr.sharpe - ctl.sharpe >= 0 ? '+' : '') + (vr.sharpe - ctl.sharpe).toFixed(2)}  annual ${(vr.annual - ctl.annual >= 0 ? '+' : '') + (vr.annual - ctl.annual).toFixed(2)}pp  maxDD ${(vr.maxdd - ctl.maxdd >= 0 ? '+' : '') + (vr.maxdd - ctl.maxdd).toFixed(2)}pp`);
  const anyRemoval = rows.some(r => r.in > r.out);
  console.log('\nfalsifier:');
  console.log(`  INERT  (no removal anywhere AND max|Δcum|==0) : ${!anyRemoval && Math.abs(maxAbs) === 0}`);
  console.log(`  BITES  (sharpe < 1.0 OR Δobjective < -0.6)    : ${vr.sharpe < 1.0 || (vr.obj - ctl.obj) < -0.6}`);
})().catch(e => { console.error('FATAL', e.message); process.exitCode = 1; });
