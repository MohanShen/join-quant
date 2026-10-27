// node study/多因子ML/build-e9-cand.js [--dry]
//
// xp-e9-1 — the COMBINED CANDIDATE for family 多因子ML: the champion book d02cde29
// (高质量稳定上涨策略) with BOTH of the family's two independently-measured, each-improving,
// each-principled edits applied to the same book:
//
//   q-e9-liq-1  a per-sleeve, DYNAMIC, parameter-free fill-feasibility floor at the book's three
//               selection sites (total_value * alloc / n_slots / order_volume_ratio)
//               measured: objective 1.4731 -> 1.5643, sharpe 5.45 -> 5.89
//   q-e9-pit    a POINT-IN-TIME pool cutoff dropping the one pool member that listed inside TRAIN
//               (159525.XSHE 红利低波ETF富国, 上市 2024-05-20)
//               measured: objective 1.4731 -> 1.5943, sharpe 5.90, maxDD unchanged 9.40
//
// ## Why a combined book rather than either single edit
//
// The family's integration exit gate is now blocked on VAL alone, and VAL is ONE per
// (family, bench). A validation must therefore be spent on the book that is not knowingly
// beatable on principle — which is the one carrying both edits, not either side alone.
//
// ## Why this builder REUSES the two existing builders instead of retyping their edits
//
// Retyping an edit is a second source of truth, and the edits here are load-bearing (one is an
// 80-line helper block inserted at 5 call sites; the other is a pool exclusion whose cutoff is
// read from the harness). So this file:
//   1. RE-RUNS study/多因子ML/build-e9-liq.js and study/多因子ML/build-e9-pit.js, which regenerate
//      variants/q-e9-liq-1.py and variants/q-e9-pit.py from the current baseline under their own
//      assertions, and asserts their bytes did not move (⇒ the artifacts on disk are current, and
//      nothing here depends on a stale file).
//   2. Takes each edit from the DIFF of its own builder's output against the shared baseline —
//      so the edit text is literally the other builder's, never retyped.
//   3. Composes them and ASSERTS the changed-line set is exactly the UNION, byte-for-byte in
//      BOTH directions, refusing to write otherwise:
//        reverse(pit edits) applied to the combined body  ==  the liq body, byte-for-byte
//        apply(pit edits) to the baseline                 ==  the pit body, byte-for-byte
//        bag-of-lines(added/removed) of combined          ==  that of liq  (+)  that of pit
//        line count of combined == line count of liq      (pit is a pure replacement)
//
// The TRAIN-start cutoff is read from utils/harness-config.js inside build-e9-pit.js and
// re-derived and cross-checked here; it is never hardcoded in either place.
//
// ## ⚠ Additivity is NOT expected, and that is pre-registered
//
// The two deltas are CONFOUNDED on the same name: 159525 is the most-floored member under liq-1
// (63 rejections, 8 of its 18 rank-1 substitutions) and those 8 days are exactly the 8 days
// 159525 won rank 1 in the pit analysis. 159525 was held just 13 of 242 days, all in October,
// both round trips losing. So a combined objective near 1.56-1.60 is the EXPECTED outcome and
// would mean the edits OVERLAP, not that they "failed to stack".
//
// Pre-registered branches (fixed before the number exists):
//   combined >= max(1.5643, 1.5943) - 0.02  AND sharpe >= 1.0  ⇒ best-justified VAL candidate
//   combined <  1.4731 (worse than the unedited base)          ⇒ destructive interaction; report
//                                                                loudly, because then one edit is
//                                                                doing something other than what
//                                                                it claims
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '../..');
const DRY = process.argv.includes('--dry');

const RAW = path.join(ROOT, 'strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py');
const BASELINE = path.join(__dirname, 'baseline-e6.py');
const LIQ_BUILDER = path.join(__dirname, 'build-e9-liq.js');
const PIT_BUILDER = path.join(__dirname, 'build-e9-pit.js');
const LIQ_VARIANT = path.join(__dirname, 'variants/q-e9-liq-1.py');
const PIT_VARIANT = path.join(__dirname, 'variants/q-e9-pit.py');
const OUTFILE = path.join(ROOT, 'enhance/candidates/xp-e9-1.py');

const EXPECT_PARENT_SHA = 'fa3e86afc68ce6fe514554c0a4f25f7aa2418edf440fa79ae75fb22445a1dcad';
const EXPECT_PARENT_CHARS = 43002;
const PARENT_CURVE = path.join(ROOT, 'data/series/2026-06-28_高质量稳定上涨策略-d02cde29__train__e9.json');
const LIQ_CURVE = path.join(ROOT, 'data/series/study_多因子ML_variants_q-e9-liq-1__train__e9.json');
const PIT_CURVE = path.join(ROOT, 'data/series/study_多因子ML_variants_q-e9-pit__train__e9.json');

const fail = [];
const A = (ok, msg) => { console.log((ok ? '  OK   ' : '  FAIL ') + msg); if (!ok) fail.push(msg); };
const sha = s => crypto.createHash('sha256').update(s).digest('hex');

// ───────────────────────────────────────────────────────── 1. parent provenance (re-verified)
console.log('=== 1. parent provenance ===');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const base = fs.readFileSync(BASELINE, 'utf8');
const parentSha = sha(base);
console.log(`  parent        : ${path.relative(ROOT, BASELINE)}`);
console.log(`  parent sha256 : ${parentSha}`);
console.log(`  parent chars  : ${base.length} (bytes ${Buffer.byteLength(base)})`);
A(parentSha === EXPECT_PARENT_SHA, `parent sha256 == ${EXPECT_PARENT_SHA.slice(0, 16)}…`);
A(base.length === EXPECT_PARENT_CHARS, `parent is ${EXPECT_PARENT_CHARS} chars`);
const rebuilt = py2to3(fs.readFileSync(RAW, 'utf8')) + OVERRIDE;
A(rebuilt === base, 'parent == py2to3(raw d02cde29) + CURRENT frozen OVERRIDE, byte-for-byte');
A(base.endsWith(OVERRIDE), 'frozen OVERRIDE cost block is the parent tail');

// the three free controls must exist, or a Delta would rest on unmeasured bytes
for (const [tag, f, cum] of [['base', PARENT_CURVE, 156.71], ['liq-1', LIQ_CURVE, null], ['pit', PIT_CURVE, null]]) {
  if (!fs.existsSync(f)) { A(false, `control curve present: ${tag} (${path.basename(f)})`); continue; }
  const c = JSON.parse(fs.readFileSync(f, 'utf8'));
  const fin = c.cum[c.cum.length - 1];
  A(c.epoch === 9 && c.window === 'train', `control curve ${tag}: epoch 9 TRAIN (${c.points} pts, ${c.start}..${c.end}, final cum ${fin})`);
  if (cum != null) A(Math.abs(fin - cum) < 0.005, `control curve ${tag}: final cum ${fin} == ${cum}`);
}

// ───────────────────────────────────────── 2. re-run both builders; their bytes must not move
console.log('\n=== 2. re-run the two source builders (their edit logic, not a retype) ===');
for (const [tag, builder, variant] of [['liq', LIQ_BUILDER, LIQ_VARIANT], ['pit', PIT_BUILDER, PIT_VARIANT]]) {
  const before = fs.existsSync(variant) ? sha(fs.readFileSync(variant, 'utf8')) : null;
  let out = '';
  try {
    out = execFileSync(process.execPath, [builder], { cwd: ROOT, encoding: 'utf8', maxBuffer: 1 << 26 });
  } catch (e) {
    console.error(`  ${tag} builder exited non-zero:\n${(e.stdout || '') + (e.stderr || '')}`);
    throw new Error(`${path.basename(builder)} refused — cannot compose an edit from a builder that will not run`);
  }
  const bad = out.split('\n').filter(l => /FAIL|REFUS/.test(l));
  A(bad.length === 0, `${tag} builder ran clean (${out.split('\n').length} lines, 0 FAIL/REFUSE)`);
  const after = sha(fs.readFileSync(variant, 'utf8'));
  A(before === null || before === after,
    `${tag} variant bytes unchanged by the re-run ⇒ ${path.relative(ROOT, variant)} is CURRENT (sha ${after.slice(0, 12)}…)`);
}

// ─────────────────────────────── 3. strip each variant's header; the bodies are what we compose
console.log('\n=== 3. recover each builder\'s edited BODY (header stripped) ===');
const ANCHOR = base.slice(0, 200);           // the clone banner — untouched by either edit
function bodyOf(file) {
  const text = fs.readFileSync(file, 'utf8');
  const n = text.split(ANCHOR).length - 1;
  if (n !== 1) throw new Error(`${path.basename(file)}: parent anchor appears ${n} times, expected 1`);
  const i = text.indexOf(ANCHOR);
  const header = text.slice(0, i);
  const stray = header.split('\n').filter(l => l.trim() !== '' && !l.startsWith('#'));
  if (stray.length) throw new Error(`${path.basename(file)}: header carries ${stray.length} non-comment line(s)`);
  return { header, body: text.slice(i), text };
}
const liq = bodyOf(LIQ_VARIANT);
const pit = bodyOf(PIT_VARIANT);
console.log(`  liq-1 body : ${liq.body.length} chars, ${liq.body.split('\n').length} lines (header ${liq.header.split('\n').length - 1} lines)`);
console.log(`  pit   body : ${pit.body.length} chars, ${pit.body.split('\n').length} lines (header ${pit.header.split('\n').length - 1} lines)`);
A(liq.body.endsWith(OVERRIDE) && pit.body.endsWith(OVERRIDE), 'both bodies still end in the frozen OVERRIDE');
A(liq.body !== base, 'liq body differs from the parent (the edit is not a no-op)');
A(pit.body !== base, 'pit body differs from the parent (the edit is not a no-op)');

// ───────────────────────────── 4. the PIT edit, taken from its own builder's output as line pairs
console.log('\n=== 4. the pit edit, read off build-e9-pit.js\'s own output ===');
const harness = require('../../utils/harness-config');
const CUT = harness.window('train').start;      // READ FROM THE HARNESS, never hardcoded
console.log(`  harness epoch ${harness.config().epoch}: TRAIN start = ${CUT} (the pool cutoff)`);

const baseLines = base.split('\n');
const pitLines = pit.body.split('\n');
A(pitLines.length === baseLines.length,
  `pit is a pure line REPLACEMENT: ${pitLines.length} body lines == ${baseLines.length} parent lines`);
const pitOps = [];
for (let i = 0; i < baseLines.length; i++) {
  if (baseLines[i] !== pitLines[i]) pitOps.push({ idx: i, from: baseLines[i], to: pitLines[i] });
}
A(pitOps.length > 0, `pit changes ${pitOps.length} line(s) — a zero-line edit would be inert`);
for (const op of pitOps) {
  const code = (op.to.match(/([0-9]{6}\.(?:XSHG|XSHE))/) || [])[1];
  console.log(`    line ${op.idx + 1}: ${JSON.stringify(op.from.trim())} -> ${JSON.stringify(op.to.trim())}`);
  A(/q-e9-pit:/.test(op.to), `pit line ${op.idx + 1} carries the q-e9-pit marker`);
  A(op.to.trim().startsWith('#'), `pit line ${op.idx + 1} is commented out in place (author's line still visible)`);
  A(op.to.includes(`>= ${CUT}`), `pit line ${op.idx + 1} cites the harness cutoff ${CUT}, not a hardcoded date`);
  A(!!code && op.from.includes(code), `pit line ${op.idx + 1} excludes exactly the code it names (${code})`);
}
// the cutoff must not be a literal anywhere in THIS builder's own edit path
A(!/2024-01-01/.test(JSON.stringify(pitOps.map(o => o.to))) || CUT === '2024-01-01',
  'the date on the excluded line IS the harness cutoff (identity, not coincidence)');

function applyPitOps(text, dir) {
  let out = text;
  for (const op of pitOps) {
    const from = dir === 'fwd' ? op.from : op.to;
    const to = dir === 'fwd' ? op.to : op.from;
    const lines = out.split('\n');
    const hits = lines.reduce((n, l) => n + (l === from ? 1 : 0), 0);
    if (hits !== 1) throw new Error(`pit op ${dir} line ${op.idx + 1}: source line occurs ${hits} times, expected exactly 1`);
    out = lines.map(l => (l === from ? to : l)).join('\n');
  }
  return out;
}
A(applyPitOps(base, 'fwd') === pit.body, 'apply(pit ops) to the PARENT reproduces the pit body BYTE-FOR-BYTE');

// ──────────────────────────────────────────────────── 5. compose, then assert the UNION property
console.log('\n=== 5. compose: pit ops applied on top of the liq body ===');
const combined = applyPitOps(liq.body, 'fwd');
console.log(`  combined body: ${combined.length} chars, ${combined.split('\n').length} lines`);

// (a) byte-for-byte in BOTH directions ⇒ the combined body is EXACTLY liq's edits plus pit's,
//     with nothing else moved.
A(applyPitOps(combined, 'rev') === liq.body,
  'reverse(pit ops) on the combined body restores the LIQ body BYTE-FOR-BYTE');
A(combined.split('\n').length === liq.body.split('\n').length,
  'combined line count == liq line count (pit adds no lines)');
A(combined !== liq.body && combined !== pit.body && combined !== base,
  'the combined body is a third, distinct book');

// (b) the changed-line SET is exactly the union, as a multiset of line texts against the parent.
function bag(text) { const m = new Map(); for (const l of text.split('\n')) m.set(l, (m.get(l) || 0) + 1); return m; }
function delta(text) {                                   // {added, removed} multisets vs the parent
  const a = bag(base), b = bag(text), added = new Map(), removed = new Map();
  for (const [l, n] of b) { const d = n - (a.get(l) || 0); if (d > 0) added.set(l, d); }
  for (const [l, n] of a) { const d = n - (b.get(l) || 0); if (d > 0) removed.set(l, d); }
  return { added, removed };
}
const merge = (x, y) => { const m = new Map(x); for (const [l, n] of y) m.set(l, (m.get(l) || 0) + n); return m; };
const eq = (x, y) => x.size === y.size && [...x].every(([l, n]) => y.get(l) === n);
const dL = delta(liq.body), dP = delta(pit.body), dC = delta(combined);
const size = m => [...m.values()].reduce((s, n) => s + n, 0);
console.log(`  added  lines vs parent: liq ${size(dL.added)}  pit ${size(dP.added)}  combined ${size(dC.added)}`);
console.log(`  removed lines vs parent: liq ${size(dL.removed)}  pit ${size(dP.removed)}  combined ${size(dC.removed)}`);
A(eq(dC.added, merge(dL.added, dP.added)),
  'ADDED-line multiset of the combined body == liq\'s (+) pit\'s, exactly');
A(eq(dC.removed, merge(dL.removed, dP.removed)),
  'REMOVED-line multiset of the combined body == liq\'s (+) pit\'s, exactly');

// (c) both mechanisms are actually present and intact in the composed book
const codeOnly = combined.split('\n').filter(l => !/^\s*#/.test(l)).join('\n');
A((codeOnly.match(/filter_liquidity_floor\(context, '/g) || []).length === 5,
  'liq edit intact: exactly 5 filter_liquidity_floor call sites (small_cap 1 + etf 2 + white_horse 2)');
for (const [sl, st] of [['small_cap', 'get_stocks'], ['etf', 'rank_auto'], ['etf', 'rank_fixed'],
  ['white_horse', 'select_big'], ['white_horse', 'select_small']]) {
  A((codeOnly.match(new RegExp(`filter_liquidity_floor\\(context, '${sl}', '${st}'`, 'g')) || []).length === 1,
    `liq edit intact: one call site sleeve=${sl} site=${st}`);
}
A((codeOnly.match(/def filter_liquidity_floor\(/g) || []).length === 1
  && (codeOnly.match(/def liq_floor_for\(/g) || []).length === 1, 'liq edit intact: each helper defined exactly once');
A(/return pos \/ float\(LIQ_ORDER_VOLUME_RATIO\) \* float\(LIQ_FLOOR_MULT\)/.test(codeOnly),
  'liq edit intact: the floor divides by order_volume_ratio (feasibility minimum, no free parameter)');
A(/^LIQ_FLOOR_MULT = 1\.0/m.test(combined), 'liq edit intact: LIQ_FLOOR_MULT = 1.0 (the 1x floor, not a capacity probe)');
A(/^LIQ_ORDER_VOLUME_RATIO = 0\.05/m.test(combined), 'liq edit intact: LIQ_ORDER_VOLUME_RATIO = 0.05 (harness pin)');
for (const op of pitOps) {
  const code = (op.to.match(/([0-9]{6}\.(?:XSHG|XSHE))/) || [])[1];
  const live = codeOnly.split('\n').filter(l => l.includes(`'${code}'`)).length;
  A(live === 0, `pit edit intact: ${code} appears on NO active code line in the combined book`);
  A(combined.split(op.to).length - 1 === 1, `pit edit intact: the commented-out ${code} line appears exactly once`);
}

// (d) the bench is untouched
A(combined.endsWith(OVERRIDE), 'frozen OVERRIDE cost block is the combined tail, byte-identical');
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  A(combined.includes(pin), `pin present: ${pin}`);
}
A((combined.match(/__jq_orig_initialize/g) || []).length === (base.match(/__jq_orig_initialize/g) || []).length,
  'OVERRIDE marker count unchanged vs the parent');
// mechanism knobs carried through untouched, counted on CODE LINES ONLY in both texts (a check that
// reads our own prose as code fails on the right answer — the build-siblings.js lesson)
const codeText = s => s.split('\n').filter(l => !/^\s*#/.test(l)).map(l => l.replace(/\s+#\s.*$/, '')).join('\n');
const baseCode = codeText(base), combCode = codeText(combined);
for (const knob of ["'target_num': 1", "'stock_num': 6", "'stock_num': 20", "'m25_days': 25",
  "'premium_threshold': 5.0", "'stoploss_limit': 0.91", "'max_stock_price': 50",
  "'etf': 0.4", "'small_cap': 0.35", "'white_horse': 0.25", 'target_num', 'max_stock_price']) {
  const a = baseCode.split(knob).length - 1, b = combCode.split(knob).length - 1;
  A(a === b && a > 0, `knob carried through unchanged (code lines only): ${knob} (${a} -> ${b})`);
}
const sched = s => s.split('\n').map(l => l.trim()).filter(l => /^run_(daily|weekly|monthly)\(/.test(l));
const sA = sched(base), sB = sched(combined);
A(sA.length === sB.length && sA.every((l, i) => l === sB[i]),
  `run_daily/weekly/monthly schedule byte-identical (${sA.length} lines)`);

// ───────────────────────────────────────────────────────────────────── 6. header, then write
const HEADER = [
  '# ============================================================================',
  '# xp-e9-1 候选：多因子ML 冠军 d02cde29（高质量稳定上涨策略）—— 两条独立改动同加',
  '#',
  '# family: 多因子ML',
  '# expId: xp-e9-1',
  `# harness_epoch: ${harness.config().epoch}`,
  `# base: strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py (parent sha256 ${parentSha})`,
  '# from: q-e9-liq-1, q-e9-pit',
  '#',
  '# 【这本书是什么】',
  '#   父本 study/多因子ML/baseline-e6.py（== py2to3(raw d02cde29) + 当前 frozen OVERRIDE，',
  `#   ${EXPECT_PARENT_CHARS} chars，sha256 已断言）上，同时加上本家族两条各自已测、各自提升、`,
  '#   各自有原则依据的改动，别无其他：',
  '#',
  '#   (1) q-e9-liq-1  逐仓、DYNAMIC、零自由参数的「可成交下限」，作用于本书三处选股点：',
  '#       floor = total_value * STRATEGY_ALLOCATION[sleeve] / n_slots / order_volume_ratio',
  '#       capital 与 order_volume_ratio 由 harness 读出并断言，绝不手抄。',
  '#       实测（单独）：objective 1.4731 -> 1.5643，sharpe 5.45 -> 5.89',
  `#   (2) q-e9-pit    点时池截止：池 ∩ { 上市日期 < ${CUT} }，截止日由`,
  "#       harness.window('train').start 现读。本书唯一命中的名字是",
  ...pitOps.map(o => `#         ${(o.to.match(/([0-9]{6}\.(?:XSHG|XSHE))/) || [])[1]}  ${(o.to.match(/上市 ([0-9-]+)/) || [])[1]}  —— TRAIN 窗口内上市`),
  '#       实测（单独）：objective -> 1.5943，sharpe 5.90，maxDD 不动 9.40',
  '#',
  '# 【为什么是组合书而不是任一单边】',
  '#   本家族在 integrate-eligible 的唯一阻断已只剩 VAL，而 VAL 是每 (family, bench) 一次。',
  '#   既然两条改动各自都是原则性的、各自都提升了 objective，那么值得花掉那一次验证的书，',
  '#   就是同时带这两条的那一本——而不是任何一个在原则上已知可被击败的单边。',
  '#',
  '# 【构建方式 —— 复用而非重打】',
  '#   study/多因子ML/build-e9-cand.js：重跑 build-e9-liq.js 与 build-e9-pit.js（断言其产物字节',
  '#   未变 ⇒ 盘上变体是当前的），从「各自变体 vs 同一父本」的 diff 取出各自的编辑，合成后断言',
  '#   改动行集合恰好等于两者之并，双向逐字：',
  '#     reverse(pit ops)(combined) == liq body 逐字相同',
  '#     apply(pit ops)(parent)     == pit body 逐字相同',
  '#     combined 的 added/removed 行多重集 == liq 的 (+) pit 的，恰好相等',
  '#   否则拒写文件。',
  '#',
  '# 【刻意不碰】动量窗口(m25_days=25 / auto_day / min_days / max_days)、target_num=1、溢价阈值',
  '#   (premium_threshold=5.0)、三腿权重(etf 0.4 / small_cap 0.35 / white_horse 0.25)、小市值腿的',
  '#   市值排序与行业分散、白马腿的三档市场温度与因子筛、止损(0.91)、空仓月、调度表、三条 pin 与',
  '#   文件尾部 frozen OVERRIDE —— 全部逐字不动（已逐项断言）。',
  '#',
  '# 【对照（三条全部免费，零回测成本）】',
  '#   base   账本行 epoch 9：objective 1.4731 / sharpe 5.45 / annual 156.71 / maxDD 9.40',
  `#          曲线 data/series/${path.basename(PARENT_CURVE)}`,
  '#   liq-1  objective 1.5643 / sharpe 5.89',
  `#          曲线 data/series/${path.basename(LIQ_CURVE)}`,
  '#   pit    objective 1.5943 / sharpe 5.90 / maxDD 9.40',
  `#          曲线 data/series/${path.basename(PIT_CURVE)}`,
  '#',
  '# ⚠⚠ 【预注册：不期待可加性】（数字出现之前写定）',
  '#   两个 Δ 是混淆的，混淆在同一只名字上：159525 是 liq-1 里被地板剔得最多的成员（63 次剔除、',
  '#   18 次 rank-1 替换中的 8 次），而那 8 天正是 pit 分析里 159525 赢得 rank 1 的 8 天；它全年',
  '#   只被持有 13/242 天，全在 10 月，两次往返都亏。所以 combined objective 落在 1.56–1.60',
  '#   就是预期结果，它不意味着两条改动「没有叠加」，而是意味着它们重叠。',
  '#',
  '# 【预注册判据（两个方向都已写死）】',
  '#   combined objective >= max(1.5643, 1.5943) − 0.02 且 sharpe >= 1.0',
  '#     ⇒ 本书是本家族最有论据的 VAL 候选',
  '#   combined objective < 1.4731（比未改动的 base 还差）',
  '#     ⇒ 两条改动破坏性互作：其中至少一条做的事与它声称的不同，必须大声报告',
  '#   无论哪一支，候选都必须过 epoch 9 的 1.0 闸门才谈得上 VAL。',
  '# ============================================================================',
  '',
].join('\n');

const text = HEADER + combined;
console.log('\n=== 6. result ===');
if (fail.length) {
  console.error(`\n${fail.length} ASSERTION(S) FAILED — REFUSING to write ${path.relative(ROOT, OUTFILE)}`);
  fail.forEach(m => console.error('  - ' + m));
  process.exitCode = 1;
} else if (DRY) {
  console.log(`  --dry: nothing written (${text.length} chars would be written to ${path.relative(ROOT, OUTFILE)})`);
} else {
  fs.mkdirSync(path.dirname(OUTFILE), { recursive: true });
  fs.writeFileSync(OUTFILE, text);
  console.log(`  wrote ${path.relative(ROOT, OUTFILE)} (${Buffer.byteLength(text)} bytes, ${text.length} chars)`);
  console.log(`  sha256 ${sha(text)}`);
  console.log(`  all ${0} assertions failed; header ${HEADER.split('\n').length - 1} lines + body ${combined.split('\n').length} lines`);
}
