// Local copy of study/资产配置/liqfloor-read.js with a LEG field (per-leg in/out/exclusions, tightest
// prevmoney/floor ratios) and the LIQAUCT readout (auction money / position value).
// Usage: node -e "require('./study/多策略分仓组合/liqfloor-read.js').main()" -- <algorithmId> <seriesKey> <controlKey>
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const { pageAll } = require('../小市值/pagelog.js');
const { forAlgorithm } = require('../../utils/backtest-log.js');

async function main() {
  const [alg, key, ctrlKey] = process.argv.slice(1).filter(a => a !== '--');
  const fa = await forAlgorithm(alg, { limit: 1 });
  if (!fa.backtestId) throw new Error(fa.err);
  const r = await pageAll(fa.backtestId);
  const L = r.lines.map(String);
  const liq = L.filter(l => /LIQFLOOR \d{4}/.test(l));
  const errs = L.filter(l => /LIQFLOOR ERROR|LIQAUCT ERROR/.test(l));
  const legs = {};
  for (const l of liq) {
    const m = l.match(/LIQFLOOR (\S+) (\S+) in=(\d+) out=(\d+) excluded=(\S+) (.*)$/);
    if (!m) continue;
    const g = legs[m[2]] || (legs[m[2]] = { batches: 0, in: 0, out: 0, batchesBound: 0, excludedOrders: 0, excludedNames: {}, ratios: [], dates: new Set() });
    g.batches++; g.in += +m[3]; g.out += +m[4]; g.dates.add(m[1]);
    if (+m[3] !== +m[4]) g.batchesBound++;
    if (m[5] !== '-') for (const s of m[5].split(',')) { g.excludedOrders++; g.excludedNames[s] = (g.excludedNames[s] || 0) + 1; }
    for (const kv of m[6].trim().split(/\s+/)) {
      const mm = kv.match(/^(.+)=([\d.]+)\/([\d.]+)$/);
      if (mm) g.ratios.push({ code: mm[1], date: m[1], prev: +mm[2], floor: +mm[3], x: +mm[2] / +mm[3] });
    }
  }
  const out = {};
  for (const [k, g] of Object.entries(legs)) {
    g.ratios.sort((a, b) => a.x - b.x);
    out[k] = { batches: g.batches, days: g.dates.size, in: g.in, out: g.out, batchesBound: g.batchesBound,
      excludedOrders: g.excludedOrders, excludedNames: g.excludedNames,
      medianRatio: g.ratios.length ? +g.ratios[Math.floor(g.ratios.length / 2)].x.toFixed(2) : null,
      tightest: g.ratios.slice(0, 5).map(x => `${x.date} ${x.code} ${x.prev.toFixed(0)}/${x.floor.toFixed(0)}=${x.x.toFixed(2)}x`) };
  }
  const auct = L.map(l => l.match(/LIQAUCT (\S+) (\S+) auctmoney=(\S+) posvalue=([\d.]+)/)).filter(Boolean);
  const ar = auct.filter(m => m[3] !== 'NA').map(m => ({ d: m[1], c: m[2], x: +m[3] / +m[4], am: +m[3], pv: +m[4] })).sort((a, b) => a.x - b.x);
  const q = p => ar.length ? +ar[Math.min(ar.length - 1, Math.floor(p * ar.length))].x.toFixed(2) : null;
  let curve = null;
  try {
    const a = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series', key + '.json'), 'utf8'));
    const b = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series', ctrlKey + '.json'), 'utf8'));
    let maxd = 0;
    for (let i = 0; i < Math.min(a.cum.length, b.cum.length); i++) maxd = Math.max(maxd, Math.abs(a.cum[i] - b.cum[i]));
    curve = { points: [a.cum.length, b.cum.length], sameDates: a.dates.join() === b.dates.join(), maxAbsDiffCumPct: maxd, finalCum: [a.cum[a.cum.length - 1], b.cum[b.cum.length - 1]] };
  } catch (e) { curve = { err: e.message }; }
  console.log(JSON.stringify({ backtestId: fa.backtestId, state: r.state, pages: r.pages, lines: L.length,
    liqfloorLines: liq.length, errorLines: errs.length, errorSample: errs.slice(0, 3), legs: out,
    liqauct: { n: auct.length, na: auct.length - ar.length, min: q(0), p10: q(0.1), median: q(0.5), max: ar.length ? +ar[ar.length - 1].x.toFixed(2) : null,
      lowest: ar.slice(0, 5).map(x => `${x.d} ${x.c} ${x.am.toFixed(0)}/${x.pv.toFixed(0)}=${x.x.toFixed(2)}`) },
    firstLine: liq[0], lastLine: liq[liq.length - 1], curve }, null, 1));
}
module.exports = { main };
