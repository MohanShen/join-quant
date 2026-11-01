// q-e9-sleeve-attrib: per-sleeve, per-name net P&L of the reference run (q-e9-s4-pit), ZERO backtests.
// Inputs (saved by dump-log.js / dump-pos.js from the run's own tabs):
//   log-q-e9-s4-pit.txt   — the [sN][买入]/[卖出] lines (sleeve tag = attribution key)
//   tx-q-e9-s4-pit.json   — 交易 tab: the real fills + real commissions
//   pos-q-e9-s4-pit.json  — 持仓 tab: each day's per-name close/value + the Cash row
// Method
//   name P&L (per sleeve) = Σ sell proceeds − Σ buy cost − Σ commission (real, from the 交易 tab)
//                           + 2024-12-31 close value of what the sleeve still holds
//                           + cash events not explained by fills (dividends; dividend tax at sale)
//   The unexplained cash on a day is Δcash − (sells − buys − commission). It is attributed to the
//   name(s) held that day, pro rata by prior-day value when more than one; that allocation is
//   reported separately so the fills-only reconstruction stays visible.
// Usage: node -e "require('./study/价值红利多腿/attrib.js').main()"
const fs = require('fs');
const path = require('path');
const D = __dirname;
const INIT = 1e6;

function codeOf(s) { const m = String(s).match(/(\d{6}\.XS\w\w)/); return m ? m[1] : null; }
function nameOf(s) { return String(s).replace(/\(.*$/, ''); }
const num = s => parseFloat(String(s).replace(/[^\d.\-]/g, ''));

function load() {
  const log = fs.readFileSync(path.join(D, 'log-q-e9-s4-pit.txt'), 'utf8').split('\n');
  const fills = [];
  for (const l of log) {
    const m = l.match(/^(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d) - INFO\s+- \[(s\d)\]\[(买入|卖出)\] (\S+) amt=(\d+) px=([\d.]+) val=([\d.]+)/);
    if (m) fills.push({ d: m[1], t: m[2], sid: m[3], side: m[4] === '买入' ? 'B' : 'S', code: m[5], amt: +m[6], px: +m[7], val: +m[8] });
  }
  const T = JSON.parse(fs.readFileSync(path.join(D, 'tx-q-e9-s4-pit.json'), 'utf8'));
  const P = JSON.parse(fs.readFileSync(path.join(D, 'pos-q-e9-s4-pit.json'), 'utf8'));
  return { log, fills, T, P };
}

function main() {
  const { log, fills, T, P } = load();
  // ---- match each log fill to exactly one 交易 row (same date, time, code, side, amount) ----
  const used = new Set();
  for (const f of fills) {
    const i = T.findIndex((t, k) => !used.has(k) && t.date === f.d && t.time === f.t && codeOf(t.stock) === f.code &&
      (t.transaction === '买') === (f.side === 'B') && Math.abs(num(t.amount)) === f.amt);
    if (i < 0) throw new Error('log fill with no 交易 row: ' + JSON.stringify(f));
    used.add(i); f.comm = +T[i].commission; f.total = Math.abs(+T[i].total); f.name = nameOf(T[i].stock);
    if (Math.abs(f.total - f.val) > 0.01) throw new Error('value mismatch ' + JSON.stringify(f));
  }
  const unmatchedTx = T.filter((t, k) => !used.has(k));

  // ---- daily book: positions + cash ----
  const days = new Map();
  for (const r of P) {
    const d = days.get(r.date) || { pos: {}, cash: null, tv: null }; days.set(r.date, d);
    const c = codeOf(r.stock);
    if (c) { d.pos[c] = { a: num(r.amount), v: +r.value, p: num(r.price), ac: num(r.avgCost), name: nameOf(r.stock) }; d.tv = +r.totalValue; }
    else if (/Cash/.test(r.stock)) d.cash = +r.value;
  }
  const ds = [...days.keys()].sort();
  const curve = JSON.parse(fs.readFileSync(path.join(D, '..', '..', 'data', 'series',
    'study_价值红利多腿_variants_q-e9-s4-pit__train__e9.json'), 'utf8'));
  // tv check against the stored curve, every day
  let maxTvErr = 0;
  curve.dates.forEach((d, i) => {
    const b = days.get(d); if (!b) throw new Error('no 持仓 day ' + d);
    const tv = b.cash + Object.values(b.pos).reduce((s, x) => s + x.v, 0);
    maxTvErr = Math.max(maxTvErr, Math.abs(tv / INIT - 1 - curve.cum[i] / 100) * 100);
  });

  // ---- sleeve ledgers from the log (sleeve tag decides ownership) ----
  const key = (sid, code) => sid + '|' + code;
  const L = {}; // key -> {sid, code, name, buy, sell, comm, held, other, nbuy}
  const get = (sid, code, name) => (L[key(sid, code)] = L[key(sid, code)] || { sid, code, name, buy: 0, sell: 0, comm: 0, held: 0, other: 0, nbuy: 0 });
  for (const f of fills) {
    const e = get(f.sid, f.code, f.name);
    if (f.side === 'B') { e.buy += f.total; e.held += f.amt; e.nbuy++; } else { e.sell += f.total; e.held -= f.amt; }
    e.comm += f.comm;
  }

  // ---- unexplained cash per day -> dividend / tax events, and share-count changes with no fill ----
  const events = []; const shareEvents = [];
  let prev = { pos: {}, cash: INIT };
  for (const d of ds) {
    const cur = days.get(d);
    const fl = fills.filter(f => f.d === d);
    const flow = fl.reduce((s, f) => s + (f.side === 'S' ? f.total : -f.total) - f.comm, 0);
    const resid = (cur.cash - prev.cash) - flow;
    if (Math.abs(resid) > 0.5) events.push({ d, resid, held: Object.keys(prev.pos), sold: fl.filter(f => f.side === 'S').map(f => f.code) });
    // shares that appear without a fill (送转 / 配股)
    const codes = new Set([...Object.keys(prev.pos), ...Object.keys(cur.pos)]);
    for (const c of codes) {
      const a0 = prev.pos[c] ? prev.pos[c].a : 0, a1 = cur.pos[c] ? cur.pos[c].a : 0;
      const net = fl.filter(f => f.code === c).reduce((s, f) => s + (f.side === 'B' ? f.amt : -f.amt), 0);
      if (a1 - a0 !== net) shareEvents.push({ d, code: c, a0, a1, fillNet: net, extra: a1 - a0 - net });
    }
    prev = cur;
  }

  // ---- which sleeve owned a code on a given day (from the log fills, by tag) ----
  function ownersOn(d, code) {
    const own = {};
    for (const f of fills) { if (f.code !== code || f.d > d) continue; own[f.sid] = (own[f.sid] || 0) + (f.side === 'B' ? f.amt : -f.amt); }
    return Object.entries(own).filter(([, a]) => a > 0);
  }
  // attribute each cash event: on a sale day to the sold code (dividend-tax at sale), else to held codes by prior value
  const evAlloc = [];
  for (const ev of events) {
    const pd = ds[ds.indexOf(ev.d) - 1];
    const prior = pd ? days.get(pd).pos : {};
    // JQ lowers a position's avgCost by the GROSS cash dividend on the day it credits the (taxed) cash,
    // so the name is identified exactly: the held code whose cost basis (amount x avgCost) fell with no fill.
    const cur = days.get(ev.d).pos;
    const traded = new Set(fills.filter(f => f.d === ev.d).map(f => f.code));
    const exact = Object.keys(cur).filter(c => prior[c] && !traded.has(c) && cur[c].a * cur[c].ac < prior[c].a * prior[c].ac - 1);
    ev.exact = exact.length === 1 ? exact[0] : null;
    if (ev.exact) ev.gross = prior[ev.exact].a * prior[ev.exact].ac - cur[ev.exact].a * cur[ev.exact].ac;
    const targets = ev.exact ? [ev.exact] : (ev.sold.length && ev.resid < 0 ? ev.sold : ev.held);
    const W = targets.reduce((s, c) => s + (prior[c] ? prior[c].v : 0), 0) || 1;
    for (const c of targets) {
      const share = ev.exact ? ev.resid : ev.resid * (prior[c] ? prior[c].v : 0) / W;
      let own = ownersOn(pd || ev.d, c);
      // shares no sleeve ledger knows of (送转 orphans): credit the only sleeve that ever traded the code
      if (!own.length) { const s = [...new Set(fills.filter(f => f.code === c).map(f => f.sid))]; if (s.length === 1) own = [[s[0], 1]]; }
      const A = own.reduce((s, [, a]) => s + a, 0) || 1;
      for (const [sid, a] of own) { get(sid, c, (prior[c] || {}).name || c).other += share * a / A; }
      evAlloc.push({ d: ev.d, code: c, amt: share, ambiguous: targets.length > 1 });
    }
  }

  // ---- end-of-year marks ----
  const last = days.get(ds[ds.length - 1]);
  const endPx = c => (last.pos[c] ? last.pos[c].p : 0);
  // shares in the real book that no sleeve ledger accounts for (e.g. 送转 shares a sleeve never knew of)
  const sleeveHeld = {};
  for (const e of Object.values(L)) sleeveHeld[e.code] = (sleeveHeld[e.code] || 0) + e.held;
  const orphans = Object.entries(last.pos).map(([c, p]) => ({ code: c, name: p.name, real: p.a, sleeve: sleeveHeld[c] || 0, px: p.p }))
    .filter(o => o.real !== o.sleeve);
  // orphan shares: credit to the sleeve that bought the parent lot (the only sleeve that ever held the code)
  for (const o of orphans) {
    const sids = [...new Set(fills.filter(f => f.code === o.code).map(f => f.sid))];
    if (sids.length !== 1) throw new Error('orphan shares on a multi-sleeve code ' + o.code);
    const e = get(sids[0], o.code, o.name); e.orphan = (o.real - o.sleeve); e.orphanVal = e.orphan * o.px;
  }
  for (const e of Object.values(L)) { e.endVal = e.held * endPx(e.code); e.fillsPnl = e.sell - e.buy - e.comm + e.endVal; e.net = e.fillsPnl + (e.orphanVal || 0) + e.other; }

  // ---- reconstruction ----
  const net = last.cash + Object.values(last.pos).reduce((s, x) => s + x.v, 0) - INIT;
  const sumFills = Object.values(L).reduce((s, e) => s + e.fillsPnl, 0);
  const sumOrph = Object.values(L).reduce((s, e) => s + (e.orphanVal || 0), 0);
  const sumOther = Object.values(L).reduce((s, e) => s + e.other, 0);
  const sumNet = sumFills + sumOrph + sumOther;
  const ledgerTotal = 32.93;

  // ---- s3 days in 511010 ----
  const in511 = ds.filter(d => days.get(d).pos['511010.XSHG']);
  // ---- 订单委托失败 ----
  const failed = log.filter(l => /订单委托失败/.test(l));
  const failVals = [...new Set(failed.map(l => (l.match(/_value=([\d.]+)/) || [])[1]))];

  const rows = Object.values(L).sort((a, b) => b.net - a.net);
  const pct = x => (100 * x / INIT).toFixed(2);
  console.log('fills in log', fills.length, '| 交易 rows', T.length, '| unmatched 交易 rows', unmatchedTx.length);
  console.log('持仓 days', ds.length, '| max |tv - curve| (pp)', maxTvErr.toFixed(4));
  console.log('\nshare-count changes with no fill:'); for (const s of shareEvents) console.log('  ', JSON.stringify(s));
  console.log('\nunexplained cash events (dividends / tax):'); for (const e of events) console.log('  ', e.d, e.resid.toFixed(2), e.exact ? ('-> ' + e.exact + ' gross ' + e.gross.toFixed(1) + ' net/gross ' + (e.resid / e.gross).toFixed(3)) : ('AMBIGUOUS held ' + e.held.join(',')));
  console.log('\norphan shares at 2024-12-31 (real book vs sleeve ledgers):'); for (const o of orphans) console.log('  ', JSON.stringify(o));
  console.log('\nRECONSTRUCTION (pp of initial capital)');
  console.log('  fills + 12-31 marks only      ', pct(sumFills), '  err vs 32.93:', (pct(sumFills) - ledgerTotal).toFixed(2));
  console.log('  + orphan 送转 shares           ', pct(sumFills + sumOrph), '  err:', (pct(sumFills + sumOrph) - ledgerTotal).toFixed(2));
  console.log('  + dividend/tax cash events    ', pct(sumNet), '  err:', (pct(sumNet) - ledgerTotal).toFixed(2), '| run net', pct(net));
  console.log('\nPER NAME (sleeve|code name: net = fills/marks + orphan + div/tax, in CNY; %net)');
  const gross = rows.reduce((s, e) => s + Math.abs(e.net), 0);
  for (const e of rows) console.log(`  ${e.sid} ${e.code} ${e.name.padEnd(6)} net ${e.net.toFixed(0).padStart(8)} (${(100 * e.net / sumNet).toFixed(1)}% of net, ${(100 * Math.abs(e.net) / gross).toFixed(1)}% of gross) fills ${e.fillsPnl.toFixed(0)} orphan ${(e.orphanVal || 0).toFixed(0)} div ${e.other.toFixed(0)} held@end ${e.held}`);
  // per name across sleeves (a code held by two sleeves is still one name)
  const byName = {}; for (const e of rows) byName[e.code] = (byName[e.code] || 0) + e.net;
  const nm = Object.entries(byName).sort((a, b) => b[1] - a[1]);
  const grossN = nm.reduce((s, [, v]) => s + Math.abs(v), 0);
  console.log('\nTOP NAMES (summed over sleeves):');
  nm.slice(0, 5).forEach(([c, v], i) => console.log(`  #${i + 1} ${c} ${v.toFixed(0)}  ${(100 * v / sumNet).toFixed(1)}% of net  ${(100 * Math.abs(v) / grossN).toFixed(1)}% of gross`));
  const top2 = nm[0][1] + nm[1][1];
  console.log(`  top-1 ${(100 * nm[0][1] / sumNet).toFixed(1)}% net / ${(100 * Math.abs(nm[0][1]) / grossN).toFixed(1)}% gross; top-2 ${(100 * top2 / sumNet).toFixed(1)}% net / ${(100 * (Math.abs(nm[0][1]) + Math.abs(nm[1][1])) / grossN).toFixed(1)}% gross`);
  console.log('\nPER SLEEVE:');
  for (const sid of ['s1', 's2', 's3', 's4']) {
    const v = rows.filter(e => e.sid === sid).reduce((s, e) => s + e.net, 0);
    const names = rows.filter(e => e.sid === sid).length;
    console.log(`  ${sid} net ${v.toFixed(0).padStart(8)}  ${(100 * v / sumNet).toFixed(1)}% of net  (${pct(v)}pp of capital, ${(100 * v / 250000).toFixed(1)}% on its 250k)  names ${names}`);
  }
  console.log(`\ns3 days holding 511010: ${in511.length} of ${ds.length} (${(100 * in511.length / ds.length).toFixed(1)}%) — ${in511[0]}..${in511[in511.length - 1]}`);
  console.log(`511010 订单委托失败 lines: ${failed.length}, order values ${failVals.join(' / ')}`);
}
module.exports = { main };
