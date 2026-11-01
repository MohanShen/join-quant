// Builds study/向导式低波价值/variants/u-3.py — u-3, PE 6-11 pool EW with the yuan-ATR<0.15 ENTRY GATE REMOVED.
// = baseline.py (py2to3 + live OVERRIDE) + the shared POOL-EW HARNESS (identical to u-7)
// + exactly ONE asserted edit: the L196 entry filter becomes a pass-through (buy_lists unchanged).
// PE band, universe, industry and the ST/paused/delisted/high-limit filters are unchanged. Control = u-7.
const fs = require('fs');
const path = require('path');
const { loadBase, applyHarness, edit } = require('./pool-ew-harness');
const ROOT = path.join(__dirname, '..', '..');

let src = applyHarness(loadBase());
// THE ONE EDIT
src = edit(src,
  '        buy_lists = [security for security in buy_lists if ATR_judge_xiaoyu(security, 0.15, 14)]\n',
  '        buy_lists = list(buy_lists)  # u-3 EDIT: yuan-ATR<0.15 entry gate removed (was: ATR_judge_xiaoyu(security, 0.15, 14) filter)\n');
// header (comment only)
src = edit(src, src.split('\n')[0] + '\n',
  '# study variant u-3 — family: 向导式低波价值 — pool-EW harness + yuan-ATR<0.15 entry gate REMOVED (PE 6-11 pool EW); control = u-7\n' +
  '# built from study/向导式低波价值/baseline.py by study/向导式低波价值/build-u-3.js via pool-ew-harness.js; harness edits marked # HARNESS, the one variant edit marked # u-3 EDIT\n');

const code = src.split('\n').map(l => l.split('#')[0]).join('\n');
if (code.includes('ATR_judge_xiaoyu(security, 0.15')) throw new Error('entry gate still live');
for (const keep of ['valuation.pe_ratio, (6,11)', "set_option('avoid_future_data', True)", 'high_limit_filter(context, buy_lists)']) {
  if (!src.includes(keep)) throw new Error('lost: ' + keep);
}
// exactly one line differs from u-7 outside the header
const u7 = fs.readFileSync(path.join(__dirname, 'variants', 'u-7.py'), 'utf8').split('\n').slice(2);
const u3 = src.split('\n').slice(2);
if (u7.length !== u3.length) throw new Error('line count differs from u-7');
const diff = u3.map((l, i) => l !== u7[i] ? i : -1).filter(i => i >= 0);
if (diff.length !== 1 || !u3[diff[0]].includes('# u-3 EDIT')) throw new Error('diff vs u-7 is not exactly the one edit: ' + diff.length);

const out = path.join(__dirname, 'variants', 'u-3.py');
fs.writeFileSync(out, src);
console.log('built', path.relative(ROOT, out), 'diff-vs-u-7 lines', diff.length);
