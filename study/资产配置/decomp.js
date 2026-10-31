// Per-asset decomposition from DECOMP log lines (previous closes logged at 09:00), same convention
// as study/资产配置/u-2-decomp.json: rf 4%, annualize 250, annual=(1+total)^(250/n)-1,
// vol=sd(daily,n-1)*sqrt(250), sharpe=(annual-rf)/vol. Equal 0.2 weights.
// Usage: node -e "require('./study/资产配置/decomp.js').main()" -- <backtestId> <codesCsv> <seriesKey> [<controlSeriesKey>] [<outJson>] [<expId>]
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const { pageAll } = require('../小市值/pagelog.js');
const RF = 0.04, AD = 250;
const r4 = x => Math.round(x * 1e4) / 1e4;
const r3 = x => Math.round(x * 1e3) / 1e3;
function sd(a) { const m = a.reduce((s, x) => s + x, 0) / a.length; return Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1)); }
function stats(rets) {
  let v = 1, pk = 1, mdd = 0;
  for (const r of rets) { v *= 1 + r; pk = Math.max(pk, v); mdd = Math.max(mdd, 1 - v / pk); }
  const total = v - 1, n = rets.length;
  const annual = Math.pow(1 + total, AD / n) - 1, vol = sd(rets) * Math.sqrt(AD);
  return { total: r4(total), annual: r4(annual), vol: r4(vol), sharpe: r3((annual - RF) / vol), maxdd: r4(mdd), _vol: vol, _sh: (annual - RF) / vol };
}
function pub(s) { const { _vol, _sh, ...o } = s; return o; }
function corr(a, b) {
  const ma = a.reduce((s, x) => s + x, 0) / a.length, mb = b.reduce((s, x) => s + x, 0) / b.length;
  let sab = 0, saa = 0, sbb = 0;
  for (let i = 0; i < a.length; i++) { sab += (a[i] - ma) * (b[i] - mb); saa += (a[i] - ma) ** 2; sbb += (b[i] - mb) ** 2; }
  return sab / Math.sqrt(saa * sbb);
}
function cov(a, b) {
  const ma = a.reduce((s, x) => s + x, 0) / a.length, mb = b.reduce((s, x) => s + x, 0) / b.length;
  let s = 0; for (let i = 0; i < a.length; i++) s += (a[i] - ma) * (b[i] - mb); return s / (a.length - 1);
}
function curveRets(rec) {
  const out = {}; let prev = 0;
  rec.dates.forEach((d, i) => { out[d] = (1 + rec.cum[i] / 100) / (1 + prev / 100) - 1; prev = rec.cum[i]; });
  return out;
}
async function main() {
  const argv = process.argv.slice(1).filter(a => a !== '--');
  const [bid, codesCsv, key, ctrlKey, outJson, expId] = argv;
  const codes = codesCsv.split(',');
  const r = await pageAll(bid);
  const lines = r.lines.map(String).filter(l => /DECOMP \d{4}-\d\d-\d\d/.test(l));
  const rows = lines.map(l => { const m = l.match(/DECOMP (\d{4}-\d\d-\d\d) (.*)$/); return { d: m[1], v: m[2].trim().split(/\s+/).map(Number) }; });
  rows.sort((a, b) => a.d < b.d ? -1 : 1);
  const nanCount = rows.reduce((s, x) => s + x.v.filter(z => !isFinite(z)).length, 0);
  // the close logged on trading day rows[i].d belongs to trading day rows[i-1].d; return date = rows[i-1].d
  const retDates = [], A = codes.map(() => []);
  for (let i = 1; i < rows.length; i++) {
    retDates.push(rows[i - 1].d);
    codes.forEach((c, j) => A[j].push(rows[i].v[j] / rows[i - 1].v[j] - 1));
  }
  const rec = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series', key + '.json'), 'utf8'));
  const cr = curveRets(rec);
  const base = retDates.map(d => cr[d]);
  if (base.some(x => x == null)) throw new Error('curve missing a return date');
  const res = {};
  res.log = { backtestId: bid, state: r.state, pages: r.pages, lines: r.lines.length, decompLines: rows.length, nanCount, firstDecomp: rows[0].d, lastDecomp: rows[rows.length - 1].d };
  if (ctrlKey) {
    const ctl = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series', ctrlKey + '.json'), 'utf8'));
    let maxd = 0, same = ctl.dates.length === rec.dates.length && ctl.dates.every((d, i) => d === rec.dates[i]);
    for (let i = 0; i < Math.min(ctl.cum.length, rec.cum.length); i++) maxd = Math.max(maxd, Math.abs(ctl.cum[i] - rec.cum[i]));
    res.control = { controlKey: ctrlKey, sameDates: same, points: [ctl.cum.length, rec.cum.length], curveMaxAbsDiffCumPct: maxd };
  }
  res.convention = { rf: RF, annualizeDays: AD, returnDates: retDates[0] + '..' + retDates[retDates.length - 1] + ' (' + retDates.length + ' days)' };
  const S = A.map(stats);
  res.perAsset = {}; codes.forEach((c, j) => { res.perAsset[c] = pub(S[j]); });
  const bs = stats(base);
  res.base_sameDates = pub(bs);
  const full = rec.dates.map(d => cr[d]);
  res.base_fullCurve = pub(stats(full));
  const w = 1 / codes.length;
  const ew = retDates.map((_, i) => A.reduce((s, a) => s + w * a[i], 0));
  res.exPostEqualWeightDailyRebal = pub(stats(ew));
  res.corr = { codes, matrix: codes.map((_, i) => codes.map((_, j) => r3(corr(A[i], A[j])))) };
  const sumWSigma = S.reduce((s, x) => s + w * x._vol, 0);
  let v = 0; for (let i = 0; i < codes.length; i++) for (let j = 0; j < codes.length; j++) v += w * w * cov(A[i], A[j]);
  res.sumWSigma = r4(sumWSigma);
  res.sigmaPort = r4(bs._vol);
  res.DR = r4(bs._vol / sumWSigma);
  res.sigmaEW_fromCov = r4(Math.sqrt(v * AD));
  const wavg = S.reduce((s, x) => s + w * x._sh, 0);
  res.weightedAvgSharpe = r3(wavg);
  res.ratioBaseSharpeOverWavg = r3(bs._sh / wavg);
  let bj = 0; S.forEach((x, j) => { if (x._sh > S[bj]._sh) bj = j; });
  res.bestSharpeAsset = codes[bj];
  res.bestSharpe = r3(S[bj]._sh);
  if (outJson) {
    const o = Object.assign({ expId: expId || null, family: '资产配置', epoch: 9, window: 'train 2024-01-01..2024-12-31' }, res);
    fs.writeFileSync(path.join(ROOT, outJson), JSON.stringify(o, null, 1));
  }
  console.log(JSON.stringify(res, null, 1));
}
module.exports = { main };
