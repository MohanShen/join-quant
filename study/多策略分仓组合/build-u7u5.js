// Builds u-7 (leg B entry time ablation, from baseline.py) and u-5 (leg B alone without rzq_list,
// from variants/u-1b.py). ONE asserted edit each; everything else byte-identical.
//
// Usage (repo root):
//   node -e "require('./study/多策略分仓组合/build-u7u5.js').build('all')"
const fs = require('fs');
const path = require('path');
const DIR = __dirname;

const SPECS = {
  'u-7-0935': { from: 'baseline.py',
    old: '        run_daily(strategy_b_buy, time="09:30:05")',
    neu: '        run_daily(strategy_b_buy, time="09:35:00")  # u-7: was 09:30:05' },
  'u-7-1000': { from: 'baseline.py',
    old: '        run_daily(strategy_b_buy, time="09:30:05")',
    neu: '        run_daily(strategy_b_buy, time="10:00:00")  # u-7: was 09:30:05' },
  'u-5': { from: 'variants/u-1b.py',
    old: '        stk_list = self.rzq_list(stk_list)',
    neu: '        # stk_list = self.rzq_list(stk_list)  # u-5: rzq_list removed (identity)' },
};

function buildOne(id) {
  const s = SPECS[id];
  const src = fs.readFileSync(path.join(DIR, s.from), 'utf8');
  const hits = src.split(s.old).length - 1;
  if (hits !== 1) throw new Error(`${id}: target line found ${hits} times`);
  const out = src.replace(s.old, s.neu);
  const a = src.split('\n'), b = out.split('\n');
  if (a.length !== b.length) throw new Error('line count changed');
  const changed = [];
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) changed.push(i);
  if (changed.length !== 1 || b[changed[0]] !== s.neu) throw new Error(`${id}: expected exactly 1 changed line, got ${changed.length}`);
  const dst = path.join(DIR, 'variants', `${id}.py`);
  fs.writeFileSync(dst, out);
  console.log(`built ${id} from ${s.from}: L${changed[0] + 1}`);
  return dst;
}

function build(id) { return id === 'all' ? Object.keys(SPECS).map(buildOne) : buildOne(id); }
module.exports = { build, SPECS };
