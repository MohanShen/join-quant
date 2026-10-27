// q-e9-inv-d9dafab2 — the 动量 edge's OWN registered test, on the epoch-9 bench and on the book
// that now carries the family's level (d9dafab2, ledger epoch 9: 1.2451 / 4.40 / 137.84 / 13.33).
//
// The registered test: "只把排序方向反过来（在通过全部滤波的 ETF 里持得分最低者），其余不动；
// 若 edge 成立，TRAIN 年化应损失过半；反排年化 >= base 的 75% 即证伪".
//
// Same single-line shape as study/七星高照/variants/q-1_invert-rank.py (which ran that test on the
// 7-name base at epoch 6). Built the way this family's variants are built: py2to3(source) + ONE
// asserted edit + the live OVERRIDE. strategies/ is never touched.
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

const FROM = "    etf_metrics.sort(key=lambda x: x['score'], reverse=True)\n";
const TO = "    etf_metrics.sort(key=lambda x: x['score'], reverse=False)  # q-e9-inv: rank inverted\n";

const HEADER = `# ============================================================================
# q-e9-inv 变体：七星高照 候选 d9dafab2 —— 排序方向反转（edge「动量」的注册 test）
#
# 【唯一的改动】第 545 行 etf_metrics.sort(..., reverse=True) -> reverse=False
#   即：在通过全部滤波的 ETF 里持【得分最低】者，而不是最高者。
#
# 【刻意不碰】池（29 只）、滤波栈、行情判断 / 走弱期回避、分钟级回撤保护、得分阈值、
#   溢价过滤、流动性过滤、成本块 —— 全部逐字不动。
#
# 【对照】台账行 d9dafab2@epoch9: objective 1.2451 / sharpe 4.40 / annual 137.84 / maxDD 13.33
# 【预注册】反排年化 >= 103.38 (= 137.84 的 75%) => 动量 edge 在本书上证伪
#           反排年化 <  68.92 (= 137.84 的 50%) => 排序携带真实信息
# ============================================================================
`;

const out = HEADER + edit(src, FROM, TO) + OVERRIDE;

// assert the edit landed and nothing else moved
const base = src + OVERRIDE;
const a = base.split('\n');
const b = (HEADER + edit(src, FROM, TO) + OVERRIDE).split('\n');
const hdrLines = HEADER.split('\n').length - 1;
const changed = [];
for (let i = 0; i < a.length; i++) {
  if (a[i] !== b[i + hdrLines]) changed.push({ line: i + 1, before: a[i], after: b[i + hdrLines] });
}
if (changed.length !== 1) throw new Error(`expected exactly 1 changed line, got ${changed.length}`);
if (!changed[0].after.includes('reverse=False') || !changed[0].after.includes('q-e9-inv')) {
  throw new Error('the changed line is not the inversion');
}

const dest = path.join(__dirname, 'variants', 'q-e9-inv-d9dafab2.py');
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.writeFileSync(dest, out);
console.log('built', path.relative(ROOT, dest));
console.log('changed line', changed[0].line);
console.log('  -', changed[0].before);
console.log('  +', changed[0].after);
