// q-e9-pit — POINT-IN-TIME POOL test for 多因子ML's base book (d02cde29, 高质量稳定上涨策略).
//
// ## Why
//
// q-audit Finding A recorded that the 14 hardcoded `ETF_CONFIG['etf_pool']` codes (lines 34-49)
// and the 4 `WHITE_HORSE_CONFIG['foreign_etfs']` codes (lines 76-81) are a pool assembled from a
// ≥2023 (really 2026) vantage point, and that line 397's length guard silently `continue`s past a
// code that is not yet listed — so the book quietly runs on a hindsight-pruned pool. Under epoch 9
// the window is TRAIN 2024, ~2 years from the authoring date, and the base scores objective
// 1.4731 / sharpe 5.45. The question this file answers is how much of that is the pool.
//
// The cross-family split this test is being checked against was measured on four books
// (CLAUDE.md): the two 小市值 × ETF HYBRIDS lost nothing (bba95a11 +0.0015, b50e4387 +0.0183)
// while the two PURE ETF-momentum books lost 19% and 33% (1cc495be −0.1886, 73b13d92 −0.4901).
// This book is a hybrid (40% etf / 35% small_cap / 25% white_horse), so the hybrid half of that
// split predicts |Δobjective| < 0.05. That prediction is registered BEFORE the run.
//
// ## The rule — fixed before the run, zero free parameters
//
//   pool = the book's OWN hardcoded codes (etf_pool ∪ foreign_etfs ∪ no_trading_buy)
//          ∩ { 上市日期 < harness.window('train').start }
//
// The cutoff is READ FROM THE HARNESS, never written down, so this builder stays correct when the
// window moves again — the same precedent as study/五福闹新春/build-e9-pit.js.
//
// ## Provenance of the dates — and why this builder no longer has to refuse
//
// This book carries NO inline listing-date comments, so the primary rule of the 五福 builder (read
// the author's own comment) finds nothing, and 6 of the 17 codes are undated anywhere in the
// corpus. Under the repo's rule — refuse rather than guess a date — q-e9-pit was BLOCKED, with its
// clearing condition named as the q-e9-pool probe.
//
// That probe has now run (study/_probes/probe-e9-pool-listdates.py, backtest log state=2, 81 log
// lines, 0 errors) and resolved all 17 codes on THREE agreeing channels:
//   INIT  get_security_info(c).start_date, taken in initialize before the OVERRIDE pins
//         avoid_future_data=True — the true start_date including post-window listings
//   FUT   get_all_securities(date='2025-12-31') and date='2026-10-20' — a second, frame-based route
//   DAY   get_all_securities(date=<each backtest day>) membership — "listed by <day>" / "not yet"
// Its two CONTROL codes reproduced their corpus-documented dates exactly (588120 → 2023-09-15,
// 513130 → 2021-06-01), so the channel is trustworthy. A listing date is a security attribute, not
// performance data, so citing it uses no 2024 price, return, volume or ranking.
//
// ## What it found
//
// EXACTLY ONE pool member lists on or after the TRAIN start:
//   159525.XSHE 红利低波ETF富国, 上市 2024-05-20  — INSIDE the TRAIN window
// The next latest is 588120 (2023-09-15); `foreign_etfs` (4 names) and `no_trading_buy` (600036,
// 2002-04-09) are untouched. So `etf_pool` goes 14 → 13 and nothing else in the file moves.
//
// ⚠ The honest bound on what this can measure: the edit can only bite on days where 159525 would
// have won the momentum rank, and with `m25_days`=25 it is unrankable until ~late June 2024
// anyway, so the realistic exposure is roughly H2-2024. A near-zero Δ is therefore consistent with
// BOTH "the pool is not hindsight" and "this particular name never mattered" — see the report.
//
//   node study/多因子ML/build-e9-pit.js --dry
//   node study/多因子ML/build-e9-pit.js

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const DRY = process.argv.includes('--dry');

// Read from the harness. NEVER hardcoded — the precedent exists so the rule survives a window move.
const CUT = harness.window('train').start;

const RAW = 'strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py';
const BASELINE = path.join(__dirname, 'baseline-e6.py');
const OUTFILE = path.join(__dirname, 'variants', 'q-e9-pit.py');

/**
 * Listing dates, every one of them a PRE-RUN FACT resolved by the q-e9-pool probe.
 * `via` records the provenance per code, because probe evidence and an author's own inline comment
 * are not the same strength of evidence and the variant header must say which is which.
 *   probe  = probe-e9-pool-listdates.py, agreeing on INIT + FUT(2025-12-31) + FUT(2026-10-20)
 *   probe+ = the same, AND independently documented by another author's inline comment in the
 *            corpus (the probe's two control codes — the channel's own validation)
 */
const DATES = {
  '513100.XSHG': { date: '2013-05-15', name: '纳指ETF',            via: 'probe' },
  '159525.XSHE': { date: '2024-05-20', name: '红利低波ETF富国',    via: 'probe' },
  '513130.XSHG': { date: '2021-06-01', name: '恒生科技',            via: 'probe+' },
  '159915.XSHE': { date: '2011-12-09', name: '创业板ETF易方达',    via: 'probe' },
  '159628.XSHE': { date: '2022-07-18', name: '国证2000ETF万家',    via: 'probe' },
  '588120.XSHG': { date: '2023-09-15', name: '科100ETF',            via: 'probe+' },
  '513520.XSHG': { date: '2019-06-25', name: '日经ETF',            via: 'probe' },
  '513030.XSHG': { date: '2014-09-05', name: '德国ETF',            via: 'probe' },
  '518880.XSHG': { date: '2013-07-29', name: '黄金ETF',            via: 'probe' },
  '161226.XSHE': { date: '2015-08-17', name: '国投白银LOF',        via: 'probe' },
  '159985.XSHE': { date: '2019-12-05', name: '豆粕ETF华夏',        via: 'probe' },
  '501018.XSHG': { date: '2016-06-28', name: '南方原油',            via: 'probe' },
  '159652.XSHE': { date: '2023-02-08', name: '有色ETF汇添富',      via: 'probe' },
  '511090.XSHG': { date: '2023-06-13', name: '30年国债',            via: 'probe' },
  '159934.XSHE': { date: '2013-12-16', name: '黄金ETF易方达',      via: 'probe' },
  '515180.XSHG': { date: '2019-12-20', name: '100红利',             via: 'probe' },
  '600036.XSHG': { date: '2002-04-09', name: '招商银行',            via: 'probe' },
};

// ── Build the baseline from the raw file and verify it is byte-identical to the committed copy.
//    The committed baseline is what every other variant in this family was built from; rebuilding
//    it here means the pit variant cannot silently diverge from its own control.
const rebuilt = py2to3(fs.readFileSync(path.join(ROOT, RAW), 'utf8')) + OVERRIDE;
const committed = fs.readFileSync(BASELINE, 'utf8');
if (rebuilt !== committed) {
  throw new Error(`baseline-e6.py is not py2to3(raw)+OVERRIDE (${committed.length} vs ${rebuilt.length} chars) — refusing`);
}
const base = committed;

// ── The ONE edit: comment out, in place, every pool-list line whose code lists >= CUT.
//    Shape required: a line that is nothing but a quoted code and an optional comma. That is the
//    author's actual layout for both pools (one code per line, no comments), and restricting the
//    match to it is what keeps `'market_index': '399100.XSHE',`, `set_benchmark(...)` and the
//    `get_index_stocks(...)` calls structurally out of reach.
const POOL_LINE = /^(\s*)(["'])([0-9]{6}\.(?:XSHG|XSHE))\2(,?)\s*$/;

const dropped = [];
const kept = [];
const outLines = base.split('\n').map((l) => {
  if (/^\s*#/.test(l)) return l;                   // already inactive in the author's source
  const m = l.match(POOL_LINE);
  if (!m) return l;
  const code = m[3];
  const info = DATES[code];
  // Refuse rather than guess: an undated pool code is exactly the state that BLOCKED this idea.
  if (!info) throw new Error(`${code} has no resolved listing date — refusing (run q-e9-pool first)`);
  if (info.date < CUT) { kept.push({ code, ...info }); return l; }
  dropped.push({ code, ...info });
  return `${m[1]}#${l.trim()}   # q-e9-pit: 上市 ${info.date} >= ${CUT}（TRAIN 开始前未上市）`;
});
const out = outLines.join('\n');

// ── ASSERT the edit is exactly the exclusion set, and refuse otherwise.
const bl = base.split('\n');
const changed = bl.map((l, i) => [i + 1, l, outLines[i]]).filter(([, a, b]) => a !== b);
if (!dropped.length) throw new Error('nothing to exclude — the test would be inert; refusing');
if (changed.length !== dropped.length) {
  throw new Error(`${changed.length} line(s) changed but ${dropped.length} excluded — refusing`);
}
for (const [ln, , after] of changed) {
  if (!/q-e9-pit:/.test(after)) throw new Error(`line ${ln} changed without the marker — refusing`);
  const code = (after.match(/([0-9]{6}\.(?:XSHG|XSHE))/) || [])[1];
  if (!dropped.some(d => d.code === code)) throw new Error(`line ${ln} changed for ${code}, not in the exclusion set — refusing`);
}
// Length invariant: the only textual difference is the comment prefix + marker on those lines.
if (out.split('\n').length !== bl.length) throw new Error('line count moved — refusing');
// The pins must survive verbatim (they live in the appended OVERRIDE, which was not touched).
for (const marker of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!out.includes(marker)) throw new Error(`missing pin ${marker} — refusing`);
}
if ((out.match(/__jq_orig_initialize/g) || []).length !== (base.match(/__jq_orig_initialize/g) || []).length) {
  throw new Error('OVERRIDE count moved — refusing');
}

const header = [
  '# ============================================================================',
  '# q-e9-pit 变体：高质量稳定上涨策略(d02cde29) —— 「点时」池（POINT-IN-TIME POOL）',
  '#',
  '# 【成员资格规则 —— 跑前固定，零自由度】',
  "#   池 = 本书硬编码的 ETF_CONFIG['etf_pool'](14) ∪ WHITE_HORSE_CONFIG['foreign_etfs'](4)",
  "#        ∪ SMALL_CAP_CONFIG['no_trading_buy'](1)，共 17 只唯一代码",
  `#        ∩ { 上市日期 < ${CUT} }`,
  `#   ${CUT} 是 harness.window('train').start，由 utils/harness-config.js 现读，绝不写死`,
  '#   —— 这条先例存在的理由就是让规则在下一次窗口移动后依然正确。',
  '#   上市日是证券属性而非业绩数据，所以本规则不引用任何 2024 年的价格、收益、成交额或排名。',
  '#',
  '# 【日期来源 —— 逐条标注，因为探针日期与作者自注的证据强度不同】',
  '#   本书全文没有任何行内上市日期注释，语料库里也有 6 只代码（159525 159628 159652',
  '#   511090 159934 515180）查不到日期 —— 所以按 build-e9-pit 的规矩（宁可拒绝也不猜日期）',
  '#   本变体一度 BLOCKED。清除条件已满足：',
  '#     study/_probes/probe-e9-pool-listdates.py（finding q-e9-pool，日志 state=2 / 81 行 / 0 错误）',
  '#     三条互相独立的通道全部一致：',
  '#       INIT  initialize 内 get_security_info(c).start_date（在 OVERRIDE pin avoid_future_data 之前）',
  '#       FUT   get_all_securities(date=2025-12-31) 与 date=2026-10-20 的 start_date',
  '#       DAY   get_all_securities(date=<每个回测日>) 成员资格（159525 在 2024-01-02..01-05 全部 OUT）',
  '#     探针自带的两只对照码复现了语料库里别的作者自注的日期（588120 → 2023-09-15、',
  '#     513130 → 2021-06-01），故该通道可信。',
  '#',
  `# 【被排除的 ${dropped.length} 只 —— 一只都不得放回】`,
  ...dropped.map(d => `#   ${d.code}  ${d.name}  上市 ${d.date}  [来源: ${d.via === 'probe+' ? 'q-e9-pool 探针 + 语料库他人行内注释交叉确认' : 'q-e9-pool 探针（INIT + FUT×2 + DAY 四读一致）'}]` +
    (d.date >= '2025-01-01' ? '   ← 2025 才上市：TRAIN 完全不可交易，但 VAL(2025) 可交易' : '   ← TRAIN 窗口内上市，TRAIN 开始时尚不存在')),
  `#   留下的 ${new Set(kept.map(k => k.code)).size} 只（${kept.length} 行，513100/513520 两池各出现一次）全部 pre-${CUT}，最晚的是 588120（2023-09-15）。`,
  `#   etf_pool 14 -> 13；foreign_etfs 与 no_trading_buy 一只未动。`,
  '#',
  '# 【刻意不碰】动量窗口(m25_days=25 / auto_day / min_days / max_days)、target_num、溢价阈值',
  '#   (premium_threshold=5.0)、三条腿的权重(0.4/0.35/0.25)、小市值腿、白马腿、择时、止损、',
  '#   成本块与三条 pin —— 全部逐字不动。唯一的改动是把上面那只名字在池中就地注释掉，',
  '#   作者原行完整可见，旁边标注上市日与截止日。builder 断言「改动行集合恰好等于排除集」，',
  '#   否则拒绝写文件。',
  '#',
  '# 【对照（零回测成本）】账本行 strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py，epoch 9：',
  '#   objective 1.4731 / sharpe 5.45 / annual 156.71 / maxDD 9.40',
  '#   曲线 data/series/2026-06-28_高质量稳定上涨策略-d02cde29__train__e9.json',
  '#',
  '# 【预注册证伪（数字出现之前就定下）】已测得的跨家族分裂：小市值×ETF 混合书几乎不掉',
  '#   (bba95a11 +0.0015、b50e4387 +0.0183)，纯 ETF 动量书掉 19–33%(1cc495be −0.1886、',
  '#   73b13d92 −0.4901)。本书是混合书，故预测 |Δobjective| < 0.05。',
  '#   Δobjective < −0.20 ⇒ 混合/纯 的分裂在本家族不成立，1.4731 带有实质池红利，',
  '#   此后本家族 headline 必须像五福那样成对引用（unrestricted / point-in-time）。',
  '#',
  '# 【读数的诚实边界】这条改动只可能在 159525 赢得动量排名的日子上起作用，而 m25_days=25 意味着',
  '#   它在约 2024 年 6 月底之前根本无法进入排名，所以真实暴露大致只有 2024 下半年。因此接近零的',
  '#   Δ 同时与「池不含事后性」和「这只名字从来没赢过排名」相容 —— 两者必须在报告里分开说。',
  '# ============================================================================',
  '',
].join('\n');

const text = header + out;
if (!DRY) {
  fs.mkdirSync(path.dirname(OUTFILE), { recursive: true });
  fs.writeFileSync(OUTFILE, text);
}

console.log(`[pit] cutoff ${CUT} (active TRAIN start, read from the harness)`);
console.log(`[pit] baseline verified byte-identical to py2to3(raw)+OVERRIDE (${base.length} chars)`);
console.log(`[pit] excluded ${dropped.length}: ${dropped.map(d => `${d.code} ${d.name} ${d.date}`).join(', ')}`);
console.log(`[pit] kept ${new Set(kept.map(k => k.code)).size} unique code(s) across ${kept.length} pool line(s), latest ${kept.slice().sort((a, b) => a.date < b.date ? 1 : -1)[0].date}`);
console.log(`[pit] changed lines: ${changed.map(c => c[0]).join(', ')} (asserted == exclusion set)`);
console.log(DRY ? '[pit] --dry: nothing written' : `[pit] wrote ${path.relative(ROOT, OUTFILE)} (${text.length} chars)`);
