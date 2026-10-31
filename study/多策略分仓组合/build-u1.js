// Builds the u-1 single-leg variants from study/多策略分仓组合/baseline.py with ONE asserted edit:
// the four-line weight block (STRATEGY_A/B/ETF2/ETF3_WEIGHT). Everything else is byte-identical.
//
// Usage (repo root):
//   node -e "require('./study/多策略分仓组合/build-u1.js').build('u-1b')"
//   node -e "require('./study/多策略分仓组合/build-u1.js').build('all')"
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const BASE = path.join(DIR, 'baseline.py');

const ORIGINAL = [
  'STRATEGY_A_WEIGHT = 0.35',
  'STRATEGY_B_WEIGHT = 0.35',
  'STRATEGY_ETF2_WEIGHT = 0.1',
  'STRATEGY_ETF3_WEIGHT = 0.2',
].join('\n');

// Each leg alone at its ORIGINAL weight; the other three set to 0.
const VARIANTS = {
  'u-1b':  { A: 0,    B: 0.35, ETF2: 0,    ETF3: 0 },
  'u-1a':  { A: 0.35, B: 0,    ETF2: 0,    ETF3: 0 },
  'u-1e3': { A: 0,    B: 0,    ETF2: 0,    ETF3: 0.2 },
  'u-1e2': { A: 0,    B: 0,    ETF2: 0.1,  ETF3: 0 },
};

function block(w) {
  return [
    `STRATEGY_A_WEIGHT = ${w.A}`,
    `STRATEGY_B_WEIGHT = ${w.B}`,
    `STRATEGY_ETF2_WEIGHT = ${w.ETF2}`,
    `STRATEGY_ETF3_WEIGHT = ${w.ETF3}`,
  ].join('\n');
}

function buildOne(id) {
  const w = VARIANTS[id];
  if (!w) throw new Error(`unknown variant ${id}`);
  const src = fs.readFileSync(BASE, 'utf8');
  const hits = src.split(ORIGINAL).length - 1;
  if (hits !== 1) throw new Error(`weight block found ${hits} times in baseline.py (expected 1)`);
  const out = src.replace(ORIGINAL, block(w));
  // Assert: exactly the weight lines changed, nothing else.
  const a = src.split('\n'), b = out.split('\n');
  if (a.length !== b.length) throw new Error('line count changed');
  const changed = [];
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) changed.push(i);
  for (const i of changed) {
    if (!/^STRATEGY_(A|B|ETF2|ETF3)_WEIGHT = /.test(b[i])) throw new Error(`unexpected change at L${i + 1}: ${b[i]}`);
  }
  const expectChanged = ['A', 'B', 'ETF2', 'ETF3'].filter(k => String(w[k]) !== ORIGINAL.match(new RegExp(`STRATEGY_${k}_WEIGHT = (\\S+)`))[1]).length;
  if (changed.length !== expectChanged) throw new Error(`changed ${changed.length} lines, expected ${expectChanged}`);
  const dst = path.join(DIR, 'variants', `${id}.py`);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.writeFileSync(dst, out);
  console.log(`built ${path.relative(path.join(DIR, '../..'), dst)} (${changed.length} line(s) changed: ${changed.map(i => 'L' + (i + 1)).join(',')})`);
  return dst;
}

function build(id) {
  if (id === 'all') return Object.keys(VARIANTS).map(buildOne);
  return buildOne(id);
}

module.exports = { build, VARIANTS };
