/**
 * replay.js — u-replay: offline hysteresis replay of next_target() on the base's logged daily bias.
 *
 * ZERO backtest cost. Reads the epoch-9 TRAIN run log of base 648c2da3 (backtestId from the stored
 * series), pages it by offset (study/小市值/pagelog.js — 100 lines/request), parses the source-L110
 * line 「北京时间…信号日期…ETF收盘…MA60…乖离±x%；目标…，实际…份」, and replays
 * next_target(prev, bias, buy_bias, sell_bias) verbatim for several sell_bias values.
 *
 * ⚠ APPROXIMATION: P&L is close-to-close from the stored curve's benchCum (513500 B&H; the base
 * benchmarks itself). The state decided at day T's 09:30 is credited with day T's FULL
 * close-to-close return, whereas the book trades at T's OPEN — so the open gap on every
 * transition day is misattributed. No fund costs. Report as episode sets + Δ, never as a level.
 *
 * Usage: node -e "require('./study/均线乖离择时/replay.js').main()"
 * Outputs (beside this file): replay-log-raw.json (cached log), replay-bias.tsv, replay-result.json
 */
const fs = require('fs');
const path = require('path');
const DIR = __dirname;
const ROOT = path.join(DIR, '..', '..');
const SERIES = path.join(ROOT, 'data/series/2026-10-28_使用标普500_60日均线乖离度增加超额收益的策略-648c2da3__train__e9.json');
const RAW = path.join(DIR, 'replay-log-raw.json');
const BUY = 0.045;
const SELLS = [0.06, 0.07, 0.085, 0.10, 0.11];
const BASE_EPISODES = [['2024-02-20', '2024-04-08'], ['2024-07-05', '2024-07-23'], ['2024-11-27', '2024-12-20']];

function nextTarget(previous, bias, buy, sell) {   // verbatim port of source L72-78
  if (bias >= sell) return false;
  if (bias <= buy) return true;
  return previous;
}

const RE = /北京时间(\d{4}-\d\d-\d\d)，信号日期(\d{4}-\d\d-\d\d)，ETF收盘([\d.]+)，MA60 ([\d.]+)，乖离([+-]?[\d.]+)%；目标(持仓|空仓)，实际(\d+)份/;

async function getLines(series) {
  if (fs.existsSync(RAW)) return JSON.parse(fs.readFileSync(RAW, 'utf8'));
  const { pageAll } = require('../小市值/pagelog.js');
  const r = await pageAll(series.backtestId);
  const out = { backtestId: series.backtestId, state: r.state, pages: r.pages, raw: r.raw,
                lines: r.lines.map(l => (typeof l === 'string' ? l : JSON.stringify(l))) };
  fs.writeFileSync(RAW, JSON.stringify(out));
  return out;
}

function episodes(dates, held) {
  // flat episode = [first flat day, re-entry day (first held day after) or 'end']
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
  const log = await getLines(series);
  console.log(`log: backtestId=${log.backtestId} state=${log.state} pages=${log.pages} lines=${log.lines.length}` + (log.raw ? ' RAW=' + log.raw : ''));
  const rows = [];
  for (const l of log.lines) {
    const m = RE.exec(l);
    if (m) rows.push({ date: m[1], sigDate: m[2], close: +m[3], ma: +m[4], bias: +m[5] / 100, target: m[6], amount: +m[7] });
  }
  const seen = new Set(); const bias = rows.filter(r => !seen.has(r.date) && seen.add(r.date));
  console.log(`parsed bias lines=${rows.length} unique days=${bias.length}`);
  if (bias.length === 0) { console.log('NO BIAS LINES — replay void'); process.exitCode = 2; return; }
  fs.writeFileSync(path.join(DIR, 'replay-bias.tsv'),
    'date\tsignal_date\tclose\tma60\tbias_pct\tlogged_target\tlogged_amount\n' +
    bias.map(r => [r.date, r.sigDate, r.close, r.ma, (r.bias * 100).toFixed(4), r.target, r.amount].join('\t')).join('\n') + '\n');

  // align to curve dates
  const idx = new Map(series.dates.map((d, i) => [d, i]));
  const missing = series.dates.filter(d => !bias.find(b => b.date === d));
  console.log(`curve days=${series.dates.length} missing bias on ${missing.length}` + (missing.length ? ': ' + missing.slice(0, 10).join(',') : ''));
  const bmap = new Map(bias.map(b => [b.date, b]));
  const bc = series.benchCum, cum = series.cum;
  const r = bc.map((c, i) => (1 + c / 100) / (i ? 1 + bc[i - 1] / 100 : 1) - 1);
  const bhTotal = (bc[bc.length - 1]);
  const baseTotal = cum[cum.length - 1];

  // base's actual flat days from its own curve (zero daily return) for cross-check
  const baseR = cum.map((c, i) => (1 + c / 100) / (i ? 1 + cum[i - 1] / 100 : 1) - 1);

  const max = bias.reduce((a, b) => (b.bias > a.bias ? b : a));
  const ge06 = bias.filter(b => b.bias >= 0.06).map(b => `${b.date}(${(b.bias * 100).toFixed(2)})`);

  const results = {};
  for (const sell of SELLS) {
    let prev = false; // g.target_invested None -> amount>0 is False on day 1
    const held = [];
    let mismatchLogged = 0;
    for (const d of series.dates) {
      const b = bmap.get(d);
      if (b) prev = nextTarget(prev, b.bias, BUY, sell);
      held.push(prev);
      if (sell === 0.085 && b && ((b.target === '持仓') !== prev)) mismatchLogged++;
    }
    let eq = 1;
    for (let i = 0; i < r.length; i++) eq *= held[i] ? 1 + r[i] : 1;
    const total = (eq - 1) * 100;
    const eps = episodes(series.dates, held);
    results[sell] = { episodes: eps, exits: eps.length, flatDays: held.filter(h => !h).length,
                      approxTotalPct: +total.toFixed(2), approxDeltaVsBH_pp: +(total - bhTotal).toFixed(2),
                      ...(sell === 0.085 ? { dayMismatchVsLoggedTarget: mismatchLogged } : {}) };
  }
  const v = results[0.085];
  const valid = JSON.stringify(v.episodes) === JSON.stringify(BASE_EPISODES);
  const out = { backtestId: series.backtestId, buyBias: BUY, bhTotalPct: bhTotal, baseTotalPct: baseTotal,
                baseZeroReturnDays: baseR.filter(x => Math.abs(x) < 1e-12).length,
                maxBias: { date: max.date, pct: +(max.bias * 100).toFixed(4) }, daysBiasGe06: ge06,
                validity: { expected: BASE_EPISODES, got: v.episodes, reproduces: valid }, results,
                approximation: 'close-to-close benchCum; day-T decision credited with T full close-to-close return (book trades at T open); no fund costs' };
  fs.writeFileSync(path.join(DIR, 'replay-result.json'), JSON.stringify(out, null, 1));
  console.log(JSON.stringify(out, null, 1));
}

module.exports = { main, nextTarget };
