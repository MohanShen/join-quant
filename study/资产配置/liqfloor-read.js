// Reads LIQFLOOR lines of a run (paged) and compares its curve with a control curve.
// Usage: node -e "require('./study/资产配置/liqfloor-read.js').main()" -- <backtestId> <seriesKey> <controlKey>
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const { pageAll } = require('../小市值/pagelog.js');
async function main() {
  const [bid, key, ctrlKey] = process.argv.slice(1).filter(a => a !== '--');
  const r = await pageAll(bid);
  const L = r.lines.map(String);
  const liq = L.filter(l => /LIQFLOOR \d{4}/.test(l));
  const errs = L.filter(l => /LIQFLOOR ERROR/.test(l));
  const excl = {}, minM = {}, inOut = {};
  for (const l of liq) {
    const m = l.match(/LIQFLOOR (\S+) in=(\d+) out=(\d+) excluded=(\S+) (.*)$/);
    if (!m) continue;
    inOut[m[2] + '->' + m[3]] = (inOut[m[2] + '->' + m[3]] || 0) + 1;
    for (const kv of m[5].trim().split(/\s+/)) {
      const [s, v] = kv.split('=');
      const x = Number(v);
      if (!(s in minM) || x < minM[s].money) minM[s] = { money: x, date: m[1] };
      if (!(s in excl)) excl[s] = 0;
    }
    if (m[4] !== '-') for (const s of m[4].split(',')) excl[s] = (excl[s] || 0) + 1;
  }
  const a = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series', key + '.json'), 'utf8'));
  const b = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series', ctrlKey + '.json'), 'utf8'));
  let maxd = 0;
  for (let i = 0; i < Math.min(a.cum.length, b.cum.length); i++) maxd = Math.max(maxd, Math.abs(a.cum[i] - b.cum[i]));
  console.log(JSON.stringify({ state: r.state, pages: r.pages, lines: L.length, liqfloorLines: liq.length,
    liqfloorErrors: errs.length, inOut, exclusionsPerName: excl, min20dMeanMoney: minM,
    firstLine: liq[0], lastLine: liq[liq.length - 1],
    curve: { points: [a.cum.length, b.cum.length], sameDates: a.dates.join() === b.dates.join(), maxAbsDiffCumPct: maxd } }, null, 1));
}
module.exports = { main };
