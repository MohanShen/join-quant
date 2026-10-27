// q-e9-avoid-off — 部件消融：关掉「走弱期回避 A 股」开关，其余逐字不动。
//
// 被测的后继形式：q-e6-10（stale, e6）关闭的是「A 股走弱就退现金」，其 implication 规定
// 「下一次要在本族做择时，必须是【换到池内另一类资产】而不是退现金」。本书正是那个形式：
// 走弱期持 overseas + commodity，只回避 A 股 ETF。
//
// 单部件核验（逐行）：
//   第 181 行 g.enable_avoid_a_share = True  —— 本次唯一改动
//   第 356 行 `if not g.enable_avoid_a_share: return g.etf_pool` 直接短路整个池切换
//   其余出现处 (215/217/219/332/...) 全是日志；分钟级回撤保护由
//   should_enable_intraday_drawdown() 经 g.enable_intraday_drawdown + g.is_a_share_weak
//   独立管辖，不受本改动影响（行情判断仍然运行、仍然记录日志）。
//
// 建法与 build-e9-inv.js 相同：py2to3(source) + ONE asserted edit + 实时 OVERRIDE。
// strategies/ 永不改动。
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-10-20_该相信癌股还是该相信海外_思考再三_决定将这压轴策略奉上-d9dafab2.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

const FROM = "    g.enable_avoid_a_share = True                    # 走弱期回避A股开关（关闭则走弱期不回避A股）\n";
const TO = "    g.enable_avoid_a_share = False                   # q-e9-avoid-off: 消融——走弱期不回避A股\n";

const HEADER = `# ============================================================================
# q-e9-avoid-off 变体：七星高照 候选 d9dafab2 —— 关闭「走弱期回避A股」开关
#
# 【唯一的改动】第 181 行 g.enable_avoid_a_share = True -> False
#   即：行情判断照常运行并记录，但走弱期不再把池切到「海外+商品」，始终使用完整池。
#
# 【刻意不碰】池（29 只）、排序、滤波栈、分钟级回撤保护（由 is_a_share_weak 独立管辖）、
#   得分阈值、溢价过滤、流动性过滤、成本块 —— 全部逐字不动。
#
# 【对照】台账行 d9dafab2@epoch9: objective 1.2451 / sharpe 4.40 / annual 137.84 / maxDD 13.33
# 【预注册】|Δobjective| < 0.10 => 该部件在 2024 近乎惰性（装饰，不是收益来源）
#           Δobjective >= +0.05 => 净负部件，更简单的书更好
#           Δobjective <= -0.10 => 净正部件（换资产形式的择时），须重开 趋势择时 edge 状态
# ============================================================================
`;

const body = edit(src, FROM, TO);
const out = HEADER + body + OVERRIDE;

// assert the edit landed and nothing else moved
const a = (src + OVERRIDE).split('\n');
const b = out.split('\n');
const hdrLines = HEADER.split('\n').length - 1;
const changed = [];
for (let i = 0; i < a.length; i++) {
  if (a[i] !== b[i + hdrLines]) changed.push({ line: i + 1, before: a[i], after: b[i + hdrLines] });
}
if (changed.length !== 1) throw new Error(`expected exactly 1 changed line, got ${changed.length}`);
if (!/g\.enable_avoid_a_share\s*=\s*False/.test(changed[0].after) || !changed[0].after.includes('q-e9-avoid-off')) {
  throw new Error('the changed line is not the ablation');
}
if (!out.includes('if not g.enable_avoid_a_share:')) throw new Error('short-circuit path missing');

const dest = path.join(__dirname, 'variants', 'q-e9-avoid-off-d9dafab2.py');
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.writeFileSync(dest, out);
console.log('built', path.relative(ROOT, dest));
console.log('changed line', changed[0].line);
console.log('  -', changed[0].before);
console.log('  +', changed[0].after);
