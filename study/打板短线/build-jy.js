// Builds the one-change variants for the 涨停基因 sub-lineage base c9e0451d (带涨停基因的小市值,
// 0xtao, post/64881; forks b3751277 / c658ef98 / d5b83074). Its epoch-6 anchor is the normalizer's
// own row of 2026-10-03 (obj 0.5478 / annual 67.73 / sharpe 2.94 / maxDD 12.95, backtestId
// 9dd79fc3…), measured under the same live OVERRIDE these variants carry — so no anchor re-run.
// Selection (get_stock_list): 1000 smallest caps -> top 10% by 3-year limit-up count
// (get_history_highlimit) -> rank by price / last pre-limit-up start-point low (get_start_point)
// -> one per SW-L2 industry, top 12 -> weekly, 6 names.
//   node -e "require('./study/打板短线/build-jy.js')"
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-07-19_带涨停基因的小市值_附PT迁移版回测结果截图_26年四月战报-c9e0451d.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function editLine(s, needle, make) {
  const lines = s.split('\n');
  const hits = lines.map((l, i) => (l.includes(needle) ? i : -1)).filter(i => i >= 0);
  if (hits.length !== 1) throw new Error(`expected exactly 1 line containing ${JSON.stringify(needle)}, got ${hits.length}`);
  const i = hits[0];
  const indent = lines[i].match(/^[ \t]*/)[0];
  const out = make(indent, lines[i]);
  lines.splice(i, 1, ...(Array.isArray(out) ? out : [out]));
  return lines.join('\n');
}

// jy-u-1 — edge test: NO limit-up information at all. The 3-year limit-up-count screen and the
// start-point ranking become identities, so the list keeps its market_cap-ascending order and
// get_stock_industry picks the smallest cap per industry: the same weekly scaffold as a pure
// 小市值 book. If objective holds, the limit-up history is inert and the sub-lineage is 规模因子.
const noLimitInfo = s => editLine(
  editLine(s, 'initial_list = get_history_highlimit(context, initial_list, g.limit_days_window)',
    ind => `${ind}pass  # jy-u-1: no 涨停基因 screen`),
  'initial_list = get_start_point(context, initial_list, g.limit_days_window)',
  ind => `${ind}pass  # jy-u-1: no start-point ranking (market_cap ascending order kept)`);

// jy-u-2 — mirror: keep the screen and the ranking, apply them to the 1000 LARGEST caps. If this
// collapses, size is necessary for the sub-lineage's return; if it holds, the limit-up history
// earns on its own.
const largestCaps = s => editLine(s, 'valuation.market_cap.asc()',
  ind => `${ind}valuation.market_cap.desc()  # jy-u-2: largest 1000 instead of smallest`);

const V = { 'jy-u-1_no-limit-info': noLimitInfo, 'jy-u-2_largest-caps': largestCaps };
for (const [id, fn] of Object.entries(V)) {
  if (fn(src) === src) throw new Error(`${id}: variant is byte-identical to the source`);
}
if (noLimitInfo(src).includes('= get_history_highlimit(')) throw new Error('jy-u-1: screen still present');
if (!largestCaps(src).includes('market_cap.desc()')) throw new Error('jy-u-2: order not flipped');

fs.mkdirSync(path.join(__dirname, 'variants'), { recursive: true });
fs.writeFileSync(path.join(__dirname, 'jy-base-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(V)) fs.writeFileSync(path.join(__dirname, 'variants', `${id}.py`), fn(src) + OVERRIDE);
console.log('built jy-base-e6 +', Object.keys(V).join(', '));
