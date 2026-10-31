// Builds u-6 (规模因子 registered test: leg A market_cap asc -> desc) and u-4 (leg A bear branch
// forced at L305 only) from variants/u-1a.py. ONE asserted edit each; everything else byte-identical.
// L277 (`if self.isbull:` in get_bull_bear_signal_minute, the state machine) must NOT change.
//
// Usage (repo root):
//   node -e "require('./study/多策略分仓组合/build-u6u4.js').build('all')"
const fs = require('fs');
const path = require('path');
const DIR = __dirname;

const SPECS = {
  'u-6': { line: 321,
    old: '        ).order_by(valuation.market_cap.asc()).limit(self.stock_num*3)',
    neu: '        ).order_by(valuation.market_cap.desc()).limit(self.stock_num*3)  # u-6: was asc()' },
  'u-4': { line: 305,
    old: '        if self.isbull:',
    neu: '        if False:  # u-4: was `if self.isbull:` (bear branch forced; L277 state machine untouched)' },
};

function buildOne(id) {
  const s = SPECS[id];
  const src = fs.readFileSync(path.join(DIR, 'variants/u-1a.py'), 'utf8');
  const a = src.split('\n');
  if (a[s.line - 1] !== s.old) throw new Error(`${id}: L${s.line} is not the expected text: ${a[s.line - 1]}`);
  if (a[276] !== '        if self.isbull:') throw new Error('L277 is not the state-machine line');
  const b = a.slice(); b[s.line - 1] = s.neu;
  const changed = [];
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) changed.push(i + 1);
  if (changed.length !== 1 || changed[0] !== s.line) throw new Error(`${id}: changed ${changed}`);
  if (b[276] !== a[276]) throw new Error('L277 changed');
  const dst = path.join(DIR, 'variants', `${id}.py`);
  fs.writeFileSync(dst, b.join('\n'));
  console.log(`built ${id} from variants/u-1a.py: L${changed[0]} only`);
  return dst;
}

function build(id) { return id === 'all' ? Object.keys(SPECS).map(buildOne) : buildOne(id); }
module.exports = { build, SPECS };
