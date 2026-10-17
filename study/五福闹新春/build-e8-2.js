// q-e8-2 (epoch 8 round) for 五福闹新春: EXECUTION-MINUTE NOISE FLOOR.
// Move the ordered afternoon block (afternoon_routine -> sell_routine -> buy_routine)
// from time='13:10' to time='13:12'. All THREE together: they are one pipeline
// (score -> sell -> buy) and moving one alone would create a cross-minute state the
// base never has. Nothing else changes -- no pool edit, no filter edit, no log line.
//
// Pre-registered direction discipline (carried verbatim from the queue entry):
//   13:12 coming back BETTER is a FRAGILITY finding, not an improvement. It must not
//   be adopted and must not be taken to VAL.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py');

const HEADER = [
  '# ============================================================================',
  '# q-e8-2 变体：执行分钟噪声地板 —— 13:10 → 13:12',
  '#',
  '# 【唯一改动】initialize 里连续三条 run_daily（baseline-e6.py 第 201-203 行）：',
  "#     run_daily(afternoon_routine, time='13:10') → '13:12'   # 动量计算与排序",
  "#     run_daily(sell_routine,      time='13:10') → '13:12'   # 卖出流水线",
  "#     run_daily(buy_routine,       time='13:10') → '13:12'   # 买入流水线",
  '#   三条必须同时移动：它们是一个有序块（算分→卖→买），单独移一条会制造 base 不存在',
  '#   的跨时点状态，污染本测。',
  '#',
  '# 【刻意不动，逐字】',
  "#   run_daily(morning_routine,        time='09:00')",
  "#   run_daily(check_weak_period_daily, time='09:40')",
  "#   run_daily(reset_daily_flags,      time='15:10')",
  "#   run_daily(minute_level_stop_loss, time='every_bar')",
  '#   以及第 4 行标题注释里的字面「13:10」（它是文件名的一部分，不是代码）。',
  '#   择时触发、R²/MA 滤波、候选系数 0.9、20 日上限、持仓数、止损、防御 ETF 511880、',
  '#   固定池/动态池/全球池、epoch-8 成本块：全部逐字不动。',
  '#',
  '# 【为什么这不是纯粹的成交时点测试】成交分钟进入的是 SIGNAL，不只是 fills：',
  '#   current_price = current_data[etf].last_price 喂给动量分、R²、MA 滤波与 3 日亏损',
  '#   滤波（L716 price_series = np.append(hist_closes, current_price)），而量能滤波',
  '#   用 projected_today_vol = today_vol * (240.0/elapsed_minutes)（L783），13:10 为',
  '#   ×1.846、13:12 为 ×1.875。',
  '#',
  '# ⚠ 预注册方向纪律：13:12 若更好，那是脆弱性发现，不是改进，不得采纳、不得带去 VAL。',
  '# ============================================================================',
  '',
].join('\n');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  console.log(`edit matched exactly once: ${from.trim()}`);
  return s.replace(from, to);
}

const src = py2to3(fs.readFileSync(SRC, 'utf8'));
const baseline = src + OVERRIDE;

// sanity: the generated baseline must equal the committed baseline-e6.py
const committed = fs.readFileSync(path.join(__dirname, 'baseline-e6.py'), 'utf8');
if (committed !== baseline) throw new Error('regenerated baseline != committed baseline-e6.py');
console.log('baseline-e6.py reproduced byte-identically from strategies/ + OVERRIDE');

// ---- the three asserted single-match edits, in source order ----
const SITES = [
  "    run_daily(afternoon_routine, time='13:10')",
  "    run_daily(sell_routine, time='13:10')",
  "    run_daily(buy_routine, time='13:10')",
];
let edited = src;
for (const from of SITES) {
  edited = edit(edited, from, from.replace("time='13:10'", "time='13:12'"));
}

const variant = HEADER + edited + OVERRIDE;

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, 'q-e8-2_trade-1312.py');
fs.writeFileSync(outFile, variant);

// ---- visible diff against the baseline ----
const tmp = path.join(require('os').tmpdir(), 'wufu-e8-2-base.py');
fs.writeFileSync(tmp, baseline);
let diff = '';
try {
  execFileSync('diff', ['-u', tmp, outFile], { encoding: 'utf8' });
} catch (e) { diff = e.stdout; }
console.log('\n===== diff baseline-e6.py -> variants/q-e8-2_trade-1312.py =====');
console.log(diff);

// ---- assertions: exactly three code lines moved, nothing else ----
const bl = baseline.split('\n'), vl = variant.split('\n');
const removed = bl.filter(l => !vl.includes(l));
const added = vl.filter(l => !bl.includes(l));
const codeAdded = added.filter(l => !/^#/.test(l) && l.trim() !== '');
console.log('lines present in baseline and absent from variant:', removed.length);
removed.forEach(l => console.log('  -', JSON.stringify(l)));
console.log('code lines added (header comments excluded):', codeAdded.length);
codeAdded.forEach(l => console.log('  +', JSON.stringify(l)));
if (removed.length !== 3) throw new Error(`expected exactly 3 removed lines, got ${removed.length}`);
if (codeAdded.length !== 3) throw new Error(`expected exactly 3 added code lines, got ${codeAdded.length}`);
for (const l of removed) {
  if (!/^\s*run_daily\((afternoon_routine|sell_routine|buy_routine), time='13:10'\)/.test(l)) {
    throw new Error('unexpected removed line: ' + l);
  }
}
for (const l of codeAdded) {
  if (!/^\s*run_daily\((afternoon_routine|sell_routine|buy_routine), time='13:12'\)/.test(l)) {
    throw new Error('unexpected added code line: ' + l);
  }
}
console.log('exactly the three afternoon run_daily lines moved 13:10 -> 13:12');

// ---- literal clock-time census ----
const count = (s, t) => s.split(t).length - 1;
// '13:10' survives ONLY in the title comment (line 4); '13:12' appears 3x in code + header echo
const codeOnly = (s) => s.split('\n').filter(l => !/^\s*#/.test(l)).join('\n');
const bc = codeOnly(baseline), vc = codeOnly(variant);
console.log(`code-only '13:10' count: baseline ${count(bc, "13:10")} -> variant ${count(vc, "13:10")}`);
console.log(`code-only '13:12' count: baseline ${count(bc, "13:12")} -> variant ${count(vc, "13:12")}`);
if (count(vc, "13:10") !== 0) throw new Error("a code line still says 13:10");
if (count(vc, "13:12") !== 3) throw new Error("expected exactly 3 code lines saying 13:12");
if (count(variant, '# title: 【五福闹新春】v5.2-已解密。别再被13:10狙击了，快跑') !== 1) {
  throw new Error('the title comment must keep its literal 13:10');
}
console.log("title comment keeps its literal 13:10 (it is prose, not code)");

// ---- every other run_daily line byte-identical ----
const UNTOUCHED = [
  "    run_daily(morning_routine, time='09:00')",
  "    run_daily(check_weak_period_daily, time='09:40')",
  "    run_daily(reset_daily_flags, time='15:10')",
  "    run_daily(minute_level_stop_loss, time='every_bar')",
];
for (const l of UNTOUCHED) {
  const a = count(baseline, l), b = count(variant, l);
  if (a !== 1 || b !== 1) throw new Error(`untouched run_daily changed: ${l} (${a} -> ${b})`);
}
console.log('09:00 morning / 09:40 weak-check / 15:10 reset / every_bar stop all unchanged');
// count CODE lines only -- this script's own header echoes the run_daily block in comments
const isCode = (l) => !/^\s*#/.test(l);
const rdB = bl.filter(l => isCode(l) && l.includes('run_daily(')).length;
const rdV = vl.filter(l => isCode(l) && l.includes('run_daily(')).length;
if (rdB !== rdV || rdB !== 7) throw new Error(`run_daily line count moved: ${rdB} -> ${rdV}`);
console.log(`run_daily line count unchanged (${rdB})`);

// ---- mechanism markers: nothing about the strategy's logic may move ----
for (const marker of [
  'g.enable_r2_filter = True',
  'weak_condition_met = (below_count >= 3)',
  'g.max_weak_days = 20',
  'g.score_threshold_ratio = 0.9',
  'g.defensive_etf = "511880.XSHG"',
  'g.holdings_num',
  "g.merged_etf_pool = list(set(g.filtered_global_pool))",
  'projected_today_vol',
  'price_series = np.append(hist_closes, current_price)',
  // the frozen cost block (epoch 8 OVERRIDE) -- real markers, verified present
  "set_option('order_volume_ratio', 0.05)",
  "set_option('avoid_future_data', True)",
  "close_tax=0.001, min_commission=5), type='stock'",
]) {
  // code-only: this script's own header quotes several of these markers in prose, and a
  // guard that reads prose as code fails precisely on the right answer
  const a = count(bc, marker), b = count(vc, marker);
  if (a !== b) throw new Error(`marker count changed for ${marker}: ${a} -> ${b}`);
  if (a === 0) throw new Error(`marker not found in baseline code: ${marker}`);
}
console.log('mechanism markers verified unchanged (breadth gate, 20d cap, 0.9 band, holdings, haven pool, vol projection, signal price, OVERRIDE)');

console.log('\nwrote', path.relative(ROOT, outFile));
