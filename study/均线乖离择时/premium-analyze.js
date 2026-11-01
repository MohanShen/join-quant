// u-premium analysis: page the probe run's log, parse PREM + L110 bias lines, report per-episode
// premium / navBias, 2024 premium distribution, NAV-date lookahead check, and a verbatim
// next_target() replay on navBias.
// Usage: node -e "require('./study/均线乖离择时/premium-analyze.js').main()"
const fs = require('fs');
const path = require('path');
const DIR = __dirname;
const ROOT = path.join(DIR, '..', '..');
const SERIES = path.join(ROOT, 'data/series/study_均线乖离择时_variants_u-premium__train__e9.json');
const RAW = path.join(DIR, 'premium-log-raw.json');
const { nextTarget } = require('./replay.js');
const SELL = 0.085, BUY = 0.045;
const BIAS_RE = /北京时间(\d{4}-\d\d-\d\d)，信号日期(\d{4}-\d\d-\d\d)，ETF收盘([\d.]+)，MA60 ([\d.]+)，乖离([+-]?[\d.]+)%；目标(持仓|空仓)/;
const PREM_RE = /PREM (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\d+) (\S+)/;

function episodes(dates, held) {
  const eps = []; let start = null;
  for (let i = 0; i < dates.length; i++) {
    if (!held[i] && start === null) start = dates[i];
    if (held[i] && start !== null) { eps.push([start, dates[i]]); start = null; }
  }
  if (start !== null) eps.push([start, 'end']);
  return eps;
}

async function main() {
  const series = JSON.parse(fs.readFileSync(SERIES, 'utf8'));
  let log;
  if (fs.existsSync(RAW)) log = JSON.parse(fs.readFileSync(RAW, 'utf8'));
  else {
    const { pageAll } = require('../小市值/pagelog.js');
    const r = await pageAll(series.backtestId);
    log = { backtestId: series.backtestId, state: r.state, pages: r.pages, raw: r.raw,
            lines: r.lines.map(l => (typeof l === 'string' ? l : JSON.stringify(l))) };
    fs.writeFileSync(RAW, JSON.stringify(log));
  }
  console.log(`log bid=${log.backtestId} state=${log.state} pages=${log.pages} lines=${log.lines.length}${log.raw ? ' RAW ' + log.raw : ''}`);
  const bias = new Map(), prem = new Map(); const errs = [];
  for (const l of log.lines) {
    let m = BIAS_RE.exec(l);
    if (m) bias.set(m[1], { sig: m[2], close: +m[3], bias: +m[5] / 100, target: m[6] });
    if (/PREM \S+ (ERR|NONAV)/.test(l)) errs.push(l.slice(0, 200));
    m = PREM_RE.exec(l);
    if (m) prem.set(m[1], { sig: m[2], close: +m[3], navDate: m[4], nav: +m[5], premium: +m[6], navMa: +m[7], navBias: +m[8], n: +m[9], pbias: +m[10] });
  }
  console.log(`bias days=${bias.size} prem days=${prem.size} errs=${errs.length}`, errs.slice(0, 3));
  const dates = series.dates;
  const P = dates.map(d => prem.get(d)).filter(Boolean);
  // NAV-date lag
  const lag = {}; let navGeToday = 0, navGtSig = 0, navEqSig = 0;
  for (const d of dates) {
    const p = prem.get(d); if (!p) continue;
    if (p.navDate >= d) navGeToday++;
    if (p.navDate > p.sig) navGtSig++;
    if (p.navDate === p.sig) navEqSig++;
    const k = p.navDate === p.sig ? 'nav=sig(T-1)' : p.navDate < p.sig ? 'nav<sig' : 'nav>sig';
    lag[k] = (lag[k] || 0) + 1;
  }
  const pr = P.map(p => p.premium);
  const mean = pr.reduce((a, b) => a + b, 0) / pr.length;
  const sd = Math.sqrt(pr.reduce((a, b) => a + (b - mean) ** 2, 0) / (pr.length - 1));
  const sorted = [...pr].sort((a, b) => a - b);
  const q = f => sorted[Math.floor(f * (sorted.length - 1))];
  const nb = P.map(p => p.navBias);
  console.log(`NAV dating: ${JSON.stringify(lag)} navDate>=today: ${navGeToday} navDate>sigDate: ${navGtSig}`);
  console.log(`premium 2024 n=${pr.length} mean=${(mean * 100).toFixed(2)}% sd=${(sd * 100).toFixed(2)}pp min=${(sorted[0] * 100).toFixed(2)} p10=${(q(.1) * 100).toFixed(2)} med=${(q(.5) * 100).toFixed(2)} p90=${(q(.9) * 100).toFixed(2)} max=${(sorted[sorted.length - 1] * 100).toFixed(2)}`);
  console.log(`navBias max=${(Math.max(...nb) * 100).toFixed(2)}% min=${(Math.min(...nb) * 100).toFixed(2)}%  priceBias max=${(Math.max(...[...bias.values()].map(b => b.bias)) * 100).toFixed(2)}%`);
  const max = P.reduce((a, b) => (b.premium > a.premium ? b : a));
  console.log(`premium max on ${[...prem.entries()].find(e => e[1] === max)[0]}`);

  const show = ['2024-02-19', '2024-02-20', '2024-04-08', '2024-07-04', '2024-07-05', '2024-07-23', '2024-11-26', '2024-11-27', '2024-12-20'];
  console.log('\ndate        sig         priceBias  navBias  premium  z(prem)  navDate  close/nav');
  for (const d of show) {
    const p = prem.get(d), b = bias.get(d);
    if (!p) { console.log(d, 'NO PREM'); continue; }
    console.log(`${d} ${p.sig} ${(p.pbias * 100).toFixed(2).padStart(7)}% ${(p.navBias * 100).toFixed(2).padStart(6)}% ${(p.premium * 100).toFixed(2).padStart(6)}% ${((p.premium - mean) / sd).toFixed(2).padStart(6)} ${p.navDate} ${p.close}/${p.nav} target=${b && b.target}`);
  }
  // windows around exits: max navBias within ±3 trading days of signal
  for (const d of ['2024-02-20', '2024-07-05', '2024-11-27']) {
    const i = dates.indexOf(d);
    const win = dates.slice(Math.max(0, i - 3), i + 4).map(x => prem.get(x)).filter(Boolean);
    console.log(`±3d of ${d}: navBias max ${(Math.max(...win.map(w => w.navBias)) * 100).toFixed(2)}%, premium max ${(Math.max(...win.map(w => w.premium)) * 100).toFixed(2)}%`);
  }

  // replay
  const replay = (key) => {
    let prev = false; const held = [];
    for (const d of dates) { const p = prem.get(d); if (p) prev = nextTarget(prev, p[key], BUY, SELL); held.push(prev); }
    return held;
  };
  const hP = replay('pbias'), hN = replay('navBias');
  const loggedHeld = dates.map(d => (bias.get(d) ? bias.get(d).target === '持仓' : null));
  const mism = dates.filter((d, i) => loggedHeld[i] !== null && loggedHeld[i] !== hP[i]).length;
  console.log(`\nreplay price-bias episodes: ${JSON.stringify(episodes(dates, hP))} (mismatch vs logged target ${mism} days)`);
  console.log(`replay NAV-bias  episodes: ${JSON.stringify(episodes(dates, hN))} flatDays=${hN.filter(h => !h).length}`);
  const bc = series.benchCum; const r = bc.map((c, i) => (1 + c / 100) / (i ? 1 + bc[i - 1] / 100 : 1) - 1);
  const tot = h => { let e = 1; for (let i = 0; i < r.length; i++) e *= h[i] ? 1 + r[i] : 1; return ((e - 1) * 100).toFixed(2); };
  console.log(`close-to-close approx total: B&H ${bc[bc.length - 1].toFixed(2)}%  priceBias ${tot(hP)}%  navBias ${tot(hN)}%`);
  // also NAV-bias with a 1-day-lagged NAV (navBias of the previous day), the realistic version
  let prev = false; const hL = [];
  for (let i = 0; i < dates.length; i++) { const p = i ? prem.get(dates[i - 1]) : null; if (p) prev = nextTarget(prev, p.navBias, BUY, SELL); hL.push(prev); }
  console.log(`replay NAV-bias lagged 1d episodes: ${JSON.stringify(episodes(dates, hL))} total ${tot(hL)}%`);
}
module.exports = { main };
