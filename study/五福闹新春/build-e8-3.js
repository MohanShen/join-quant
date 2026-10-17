// q-e8-3 for 五福闹新春: absolute daily-turnover FLOOR (¥2e7) on the weak-period haven pool.
//
// PARENT IS NOT baseline-e6. It is study/五福闹新春/variants/q-e8-7_weak-pit9.py — the exact
// bytes that were measured as objective 0.3962 / sharpe 2.04 / maxDD 13.07 / annual 52.69.
// We print its sha256 and assert its stored TRAIN curve exists, so the Δ rests on a measured
// parent rather than on a re-derivation.
//
// Four edits, exactly as the gatekeeper fixed them. The floor value, the pool, the divisor and
// the weak-period trigger are NOT ours to choose.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '../..');
const PARENT = path.join(__dirname, 'variants/q-e8-7_weak-pit9.py');
const PARENT_CURVE = path.join(ROOT, 'data/series/study_五福闹新春_variants_q-e8-7_weak-pit9__train__e8.json');

// ---------------------------------------------------------------- parent provenance
const parentBytes = fs.readFileSync(PARENT);
const parentSha = crypto.createHash('sha256').update(parentBytes).digest('hex');
console.log('parent        :', path.relative(ROOT, PARENT));
console.log('parent sha256 :', parentSha);
console.log('parent bytes  :', parentBytes.length);
if (!fs.existsSync(PARENT_CURVE)) {
  throw new Error('parent TRAIN curve missing — the Δ would rest on unmeasured bytes: ' + PARENT_CURVE);
}
const pc = JSON.parse(fs.readFileSync(PARENT_CURVE, 'utf8'));
console.log(`parent curve  : ${path.basename(PARENT_CURVE)} (${pc.points} pts, ${pc.start}..${pc.end}, epoch ${pc.epoch})`);

const src = parentBytes.toString('utf8');

// ---------------------------------------------------------------- the 9 names, frozen from q-e8-7
const POOL = [
  '518880.XSHG', '513100.XSHG', '513500.XSHG', '513030.XSHG', '161226.XSHE',
  '501018.XSHG', '513520.XSHG', '159985.XSHE', '159980.XSHE',
];
const PIT9_LITERAL_ONELINE = `[${POOL.map(s => `'${s}'`).join(',')}]`;
if (POOL.length !== 9 || new Set(POOL).size !== 9) throw new Error('pool must be 9 distinct names');

const HEADER = [
  '# ============================================================================',
  '# q-e8-3 变体：在 q-e8-7 的 pit9 之上叠加一个绝对可成交下限（¥2e7/日）',
  '#',
  '# 【父本 —— 不是 baseline-e6】',
  `#   study/五福闹新春/variants/q-e8-7_weak-pit9.py  sha256 ${parentSha}`,
  '#   父本实测（epoch 8, TRAIN）：objective 0.3962 / sharpe 2.04 / maxDD 13.07 / annual 52.69',
  '#   曲线：data/series/study_五福闹新春_variants_q-e8-7_weak-pit9__train__e8.json',
  '#   本变体与父本只差「流动性约束」一个维度。',
  '#',
  '# 【池 —— 冻结自 q-e8-7，零自由度，不增不减不排序】',
  '#   池 = base 自己的 g.global_etf_pool（17 只）∩ { 上市日 < 2022-01-01 } = 9 只：',
  ...POOL.map(s => `#     '${s}'`),
  '#   被排除的 8 只（上市 ≥ 2022-01-01）一只都不得放回。',
  '#',
  '# 【地板算术 —— 由 harness 推出，不是我们挑的】',
  '#   harness 本金 ¥1,000,000 × order_volume_ratio 0.05 ÷ g.holdings_num 1',
  '#     ⇒ 单名可行性下限 = 1e6 / 0.05 = ¥2e7/日',
  '#   形式固定为 threshold = max(dynamic_threshold, 2e7)：恒 ≥ base 自己的相对门槛，',
  '#   所以本测的剔除集恒为 base 相对过滤剔除集的超集。',
  '#   ⚠ g.global_threshold_divisor = 20000 逐字不动（该旋钮由 q-e6-3 关闭）。',
  '#   作为尺度参照（仅参照，不得改）：作者在除数处自注「资金大建议改为3000」≈ ¥6.7e7。',
  '#',
  '# 【跑前零成本预检（data/autostudy-logs/wufu-q-e8-7.full.txt，已做）】',
  '#   base 的相对门槛 = 全市场 ETF 近 3 日日均总成交额 / 20000，实测落在',
  '#   ¥1.97M–¥6.65M（全 484 日；294 个走弱日 ¥2.07M–¥6.01M，中位 ¥3.70M）。',
  '#   **294 个走弱日中 dynamic_threshold > 2e7 的天数 = 0。**',
  '#   ⇒ max() 在每一天都取 2e7，地板从不被动态门槛吞掉；本测测的是我们的 ¥2e7 地板本身，',
  '#     而 dynout/dynremoved 同时免费给出 base 相对门槛那一条腿。',
  '#   （队列条目里「除数 20000 ≈ ¥1e7」是一个高估约 3–5 倍的估计，实测如上。）',
  '#',
  '# 【四处改动，别无其他】',
  '#   (1) initialize：g.global_threshold_divisor 之后加 g.weak_liquidity_floor = 2e7 与 g.pit9_pool',
  '#   (2) filter_global_pool_by_volume：qualified 用 max(dynamic_threshold, floor)，并每走弱日打一条',
  '#       LIQFLOOR ... status=ok（含 out/removed 与 dynout/dynremoved 与 per-name money=）',
  '#   (3) 同函数三条 bypass 路径各打一条 status=bypass-<tag>（静默绕过必须可数）',
  '#   (4) afternoon_routine 走弱分支：pit9 的 9 元素字面量 → 保序交集',
  '#       [s for s in g.pit9_pool if s in (g.filtered_global_pool or [])]',
  '#   ⚠ 明确不走的路：不得把 g.global_etf_pool 换成这 9 只 —— L182',
  '#     g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool 会把它漏进**正常期**固定池，',
  '#     悄悄删掉 8 只正常期名字并重开 q-e6-3 已关闭的方向。',
  '#   其余逐字不动：择时触发 below_count>=3、R²/MA 滤波、候选系数 0.9、20 日上限、',
  '#     13:10 三条 run_daily、分钟止损、防御 ETF 511880、holdings_num 1、epoch-8 成本块。',
  '#',
  '# 【判据（跑前固定）】',
  '#   (A) 结构判据（主判据，与 objective 无关）：294 条 LIQFLOOR 是否全为 in=9 out=9、0 条 bypass、',
  '#       且与父本曲线 max|Δcum| = 0 ⇒ 惰性。惰性是真答案（大小盘轮动 liq-1 判例）。',
  '#   (B) 水平判据：Δobjective 对 pit9 的 0.3962（唯一正确参照；baseline-e6 0.3755 只作并列报告）。',
  '#       Δobj ≥ −0.02 ⇒ pit9 这本书 realizability = 2；Δobj ≤ −0.10 ⇒ pit9 原样 R = 1；',
  '#       中间 ⇒ partial，realizability 保持未设（未知即 BLOCK）。',
  '#   (C) 免费结构对照：294 个走弱日里落到防御货币 ETF 511880 的天数（父本 46/294），须与 (A) 的 removed 一致。',
  '#   ⚠ 本测不得主张 realizability = 3（容量≠到闸余量），也只测「日成交量够不够填 ¥1M 的单」，',
  '#     不测 QDII 溢价/折价、申赎额度、部分成交。scope = pit9 这本书，不是家族候选。',
  '# ============================================================================',
  '',
].join('\n');

function edit(s, from, to, tag) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`[${tag}] expected exactly 1 match, got ${n}: ${JSON.stringify(from.slice(0, 120))}`);
  console.log(`edit ${tag}: FROM matched exactly once`);
  return s.replace(from, to);
}

let out = src;

// ------------------------------------------------------------------ edit (1) initialize
const FROM1 = '    g.global_threshold_divisor = 20000  # 全市场ETF流动性阈值除数，资金大建议改为3000避免买到盘子小的etf\n';
const TO1 = FROM1 + [
  '    # q-e8-3: 走弱期绝对可成交下限。harness 本金 1e6 x order_volume_ratio 0.05 / holdings_num 1 = 2e7。',
  '    g.weak_liquidity_floor = 2e7',
  '    # q-e8-3: 池 = q-e8-7 的 pit9（base 自己的 17 只 ∩ 上市日 < 2022-01-01），逐字冻结，顺序不变。',
  "    g.pit9_pool = ['518880.XSHG', '513100.XSHG', '513500.XSHG', '513030.XSHG', '161226.XSHE',",
  "                   '501018.XSHG', '513520.XSHG', '159985.XSHE', '159980.XSHE']",
  '',
].join('\n');
out = edit(out, FROM1, TO1, '1-initialize');

// ------------------------------------------------------------------ edit (2) the floor + LIQFLOOR log
const FROM2 = [
  '        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]',
  '        new_global_pool = qualified.index.tolist()',
].join('\n');
const TO2 = [
  '        threshold = max(dynamic_threshold, g.weak_liquidity_floor)            # q-e8-3',
  '        qualified = avg_daily_money[avg_daily_money > threshold]              # q-e8-3: was > dynamic_threshold',
  '        new_global_pool = qualified.index.tolist()',
  '        _p9 = g.pit9_pool                                                     # q-e8-3 观测，不参与任何决策',
  '        _keep = [s for s in _p9 if s in new_global_pool]',
  '        _dyn = [s for s in _p9 if float(avg_daily_money.get(s, 0)) > dynamic_threshold]',
  '        log.info("LIQFLOOR %s floor=%.0f dyn=%.0f in=%d out=%d removed=%s dynout=%d dynremoved=%s money=%s status=ok" % (',
  '            context.previous_date, g.weak_liquidity_floor, dynamic_threshold, len(_p9), len(_keep),',
  "            ';'.join([s for s in _p9 if s not in _keep]) or '-', len(_dyn),",
  "            ';'.join([s for s in _p9 if s not in _dyn]) or '-',",
  "            ';'.join(['%s:%.0f' % (s, float(avg_daily_money.get(s, 0))) for s in _p9])))",
].join('\n');
out = edit(out, FROM2, TO2, '2-floor');

// ------------------------------------------------------------------ edit (3) three bypass paths
function bypassLog(indent, tag, outExpr) {
  return [
    `${indent}log.info("LIQFLOOR %s floor=%.0f dyn=-1 in=%d out=%d removed=- dynout=-1 dynremoved=- money=- status=bypass-${tag}" % (`,
    `${indent}    context.previous_date, g.weak_liquidity_floor, len(g.pit9_pool), ${outExpr}))`,
  ].join('\n');
}

const FROM3a = [
  '    if not g.global_etf_pool:',
  '        log.info("【全球池过滤】全球池为空，跳过过滤")',
  '        g.filtered_global_pool = []',
  '        return',
].join('\n');
const TO3a = [
  '    if not g.global_etf_pool:',
  '        log.info("【全球池过滤】全球池为空，跳过过滤")',
  '        g.filtered_global_pool = []',
  bypassLog('        ', 'emptypool', '0'),
  '        return',
].join('\n');
out = edit(out, FROM3a, TO3a, '3a-bypass-emptypool');

const FROM3b = [
  '        if price_data is None or price_data.empty:',
  '            log.warning("【全球池过滤】无法获取成交额数据，使用原始全球池")',
  '            g.filtered_global_pool = g.global_etf_pool[:]',
  '            return',
].join('\n');
const TO3b = [
  '        if price_data is None or price_data.empty:',
  '            log.warning("【全球池过滤】无法获取成交额数据，使用原始全球池")',
  '            g.filtered_global_pool = g.global_etf_pool[:]',
  bypassLog('            ', 'nodata', 'len(g.pit9_pool)'),
  '            return',
].join('\n');
out = edit(out, FROM3b, TO3b, '3b-bypass-nodata');

const FROM3c = [
  '    except Exception as e:',
  '        log.warning(f"【全球池过滤】异常: {e}")',
  '        g.filtered_global_pool = g.global_etf_pool[:]',
].join('\n');
const TO3c = [
  '    except Exception as e:',
  '        log.warning(f"【全球池过滤】异常: {e}")',
  '        g.filtered_global_pool = g.global_etf_pool[:]',
  bypassLog('        ', 'exception', 'len(g.pit9_pool)'),
].join('\n');
out = edit(out, FROM3c, TO3c, '3c-bypass-exception');

// ------------------------------------------------------------------ edit (4) weak branch -> order-preserving intersection
const FROM4 = `        g.merged_etf_pool = ${PIT9_LITERAL_ONELINE}  # q-e8-7: weak period -> 9 point-in-time havens (base's own 17 listed before 2022-01-01)`;
const TO4 = "        g.merged_etf_pool = [s for s in g.pit9_pool if s in (getattr(g, 'filtered_global_pool', None) or [])]  # q-e8-3";
out = edit(out, FROM4, TO4, '4-weak-branch');

const variant = HEADER + out;
const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, 'q-e8-3_pit9-liqfloor-2e7.py');

// ================================================================== ASSERTIONS
// NOTE: every count is taken on `out` — the variant MINUS our own header comment block.
// The header quotes several of these markers in prose, and counting the whole file made
// four assertions fail on their own documentation. A check that reads prose as code fails
// precisely on the right answer (the build-siblings.js lesson in CLAUDE.md).
const fail = [];
const A = (ok, msg) => { console.log((ok ? 'OK   ' : 'FAIL ') + msg); if (!ok) fail.push(msg); };

// (b) g.global_etf_pool untouched: still 17 entries, and L182 present verbatim
const gpBlock = out.split('g.global_etf_pool = [')[1].split('\n    ]')[0];
const gpNames = gpBlock.match(/'\d{6}\.XSH[GE]'/g) || [];
A(out.split('g.global_etf_pool = [').length - 1 === 1, 'g.global_etf_pool assigned exactly once');
A(gpNames.length === 17, `g.global_etf_pool still holds 17 entries (got ${gpNames.length})`);
A(out.includes('    g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool'),
  'L182 g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool present verbatim');
A((out.split('g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool').length - 1) === 1,
  'that line appears exactly once in code');

// (c) the 9-name list appears exactly once in CODE (g.pit9_pool), and not as a weak-branch literal
const codeLines = out.split('\n').filter(l => !/^\s*#/.test(l));
const code = codeLines.join('\n');
A(!code.includes(PIT9_LITERAL_ONELINE), 'q-e8-7 one-line 9-name literal is gone from code');
A((code.match(/g\.pit9_pool = \[/g) || []).length === 1, 'g.pit9_pool defined exactly once');
// no code line other than the pit9_pool definition may carry >=4 of the 9 tickers inline
const pit9DefLines = new Set();
codeLines.forEach((l, i) => { if (l.includes('g.pit9_pool = [') || /^\s+'501018\.XSHG', '513520/.test(l)) pit9DefLines.add(i); });
const stray = codeLines.filter((l, i) => !pit9DefLines.has(i) && POOL.filter(s => l.includes(s)).length >= 4);
A(stray.length === 0, `no other code line carries >=4 of the 9 tickers (found ${stray.length})`);
stray.forEach(l => console.log('     stray:', l.trim().slice(0, 100)));
// the weak branch itself holds no list literal of tickers
const afternoon = out.split('def afternoon_routine(context):')[1].split('\ndef sell_routine')[0];
A(out.split('def afternoon_routine(context):').length - 1 === 1, 'afternoon_routine defined once');
const weakBranch = afternoon.split('    if g.is_a_share_weak:\n')[1].split('\n    else:')[0];
A(!/\['\d{6}\.XSH/.test(weakBranch), 'weak branch holds no ticker list literal');
A(weakBranch.includes("g.merged_etf_pool = [s for s in g.pit9_pool if s in (getattr(g, 'filtered_global_pool', None) or [])]"),
  'weak branch uses the order-preserving intersection');
A(/WEAKHOLD \{context\.current_dt\.date\(\)\} \{sorted\(context\.portfolio\.positions\.keys\(\)\)\}/.test(weakBranch),
  'WEAKHOLD line preserved verbatim');
A(weakBranch.includes('🔴 【大A走弱期】使用过滤后全球/海外ETF池，共{len(g.merged_etf_pool)}只'),
  '🔴 log line preserved verbatim');

// (d) marker counts unchanged vs parent
for (const marker of [
  'g.enable_r2_filter = True',
  'weak_condition_met = (below_count >= 3)',
  'g.max_weak_days = 20',
  'g.score_threshold_ratio = 0.9',
  'g.defensive_etf = "511880.XSHG"',
  'g.holdings_num = 1',
  'g.global_threshold_divisor = 20000',
  '__jq_set_order_cost',
  'g.lookback_days',
  "run_daily(afternoon_routine, time='13:10')",
  "run_daily(sell_routine, time='13:10')",
  "run_daily(buy_routine, time='13:10')",
]) {
  const a = src.split(marker).length - 1, b = out.split(marker).length - 1;
  A(a === b && a > 0, `marker count unchanged: ${marker} (${a} -> ${b})`);
}
// the dispatched marker list named `_ORIG_SET_ORDER_COST`; the live OVERRIDE calls it
// `__jq_set_order_cost` (asserted above). Record that the legacy name is absent from BOTH.
A((src.split('_ORIG_SET_ORDER_COST').length - 1) === (out.split('_ORIG_SET_ORDER_COST').length - 1),
  `_ORIG_SET_ORDER_COST count unchanged (${src.split('_ORIG_SET_ORDER_COST').length - 1}; legacy alias, not in the live OVERRIDE)`);
A((out.match(/run_daily\([a-z_]+, time='13:10'\)/g) || []).length === 3, "exactly three 13:10 run_daily lines");

// (e) log lines are bare log.info and cannot influence decisions
const liqStmts = out.split('\n').filter(l => l.includes('"LIQFLOOR '));
A(liqStmts.length === 4, `4 LIQFLOOR log statements (1 ok + 3 bypass), got ${liqStmts.length}`);
A(liqStmts.every(l => /^\s*log\.info\("LIQFLOOR /.test(l)), 'every LIQFLOOR statement starts as a bare log.info(');
// the full LIQFLOOR expressions (statement + continuation lines) must not mutate state
const vlines = variant.split('\n');
for (let i = 0; i < vlines.length; i++) {
  if (!/^\s*log\.info\("LIQFLOOR /.test(vlines[i])) continue;
  let j = i, expr = '';
  // consume until parens balance
  let bal = 0;
  do { expr += vlines[j] + '\n'; for (const ch of vlines[j]) { if (ch === '(') bal++; if (ch === ')') bal--; } j++; }
  while (bal > 0 && j < vlines.length);
  A(!/\bg\.\w+\s*=[^=]/.test(expr), `LIQFLOOR stmt at line ~${i + 1} assigns no g.*`);
  A(!/\.sort\(|\.append\(|\.pop\(|\bdel\s/.test(expr), `LIQFLOOR stmt at line ~${i + 1} has no sort/append/pop/del`);
  A(!expr.includes('g.merged_etf_pool'), `LIQFLOOR stmt at line ~${i + 1} does not mention g.merged_etf_pool`);
}
A(!variant.split('"LIQFLOOR').slice(1).join('').includes('g.merged_etf_pool') || true, 'checked above');
const whLine = vlines.filter(l => l.includes('WEAKHOLD'));
A(whLine.length === 1 && /^\s*log\.info\(f"WEAKHOLD /.test(whLine[0]), 'WEAKHOLD is one bare log.info');

// floor value and form
A((out.match(/g\.weak_liquidity_floor = 2e7/g) || []).length === 1, 'floor is 2e7, assigned once');
A(out.includes('threshold = max(dynamic_threshold, g.weak_liquidity_floor)'), 'floor form is max(dynamic, floor)');
A((out.match(/avg_daily_money\[avg_daily_money > threshold\]/g) || []).length === 1, 'qualified uses the max() threshold');
// the relative-only filter survives in the OTHER two pool functions (fixed pool, sector pool)
// and MUST — this test touches only the weak/global pool. Assert it is gone from
// filter_global_pool_by_volume and unchanged in count elsewhere.
const fgp = out.split('def filter_global_pool_by_volume(context):')[1].split('\ndef ')[0];
A(!fgp.includes('avg_daily_money[avg_daily_money > dynamic_threshold]'),
  'relative-only filter gone from filter_global_pool_by_volume');
A((src.match(/avg_daily_money\[avg_daily_money > dynamic_threshold\]/g) || []).length - 1
  === (out.match(/avg_daily_money\[avg_daily_money > dynamic_threshold\]/g) || []).length,
  'exactly ONE relative-only filter replaced repo-wide; the other pool functions untouched');

// OVERRIDE cost block intact (byte-identical tail)
const { OVERRIDE } = require('../../utils/strategy-normalize');
A(variant.endsWith(OVERRIDE), 'frozen OVERRIDE cost block is the file tail, byte-identical');

if (fail.length) {
  console.error('\n' + fail.length + ' ASSERTION(S) FAILED — not writing the variant');
  fail.forEach(m => console.error('  - ' + m));
  process.exitCode = 1;
} else {
  fs.writeFileSync(outFile, variant);
  console.log('\nwrote', path.relative(ROOT, outFile), `(${Buffer.byteLength(variant)} bytes)`);
  console.log('sha256', crypto.createHash('sha256').update(variant).digest('hex'));

  let diff = '';
  try { execFileSync('diff', ['-u', PARENT, outFile], { encoding: 'utf8' }); }
  catch (e) { diff = e.stdout; }
  console.log('\n===== diff variants/q-e8-7_weak-pit9.py -> variants/q-e8-3_pit9-liqfloor-2e7.py =====');
  console.log(diff);
}
