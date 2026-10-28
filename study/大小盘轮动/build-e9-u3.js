// e9-u3: base 2f5bc859 with TWO logic edits g.enable_strategy_one True->False and
// g.enable_strategy_two True->False (only 择时三 votes), plus the four LOGGING-ONLY lines of e9-u2
// (u2-e9_signal-log.py). py2to3 + asserted edits + OVERRIDE.
// Assertion: the output differs from variants/u2-e9_signal-log.py in exactly the two enable lines.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-05-20_四择时高息低价小市值和白马大市值轮动-2f5bc859.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

const base = fs.readFileSync(path.join(__dirname, 'baseline-e6.py'), 'utf8');
if (base !== src + OVERRIDE) throw new Error('baseline-e6.py != py2to3(src)+OVERRIDE — rebuild base first');

let s = src;
// the TWO logic edits
s = edit(s, '    g.enable_strategy_one = True\n', '    g.enable_strategy_one = False  # e9-u3: only 择时三 votes\n');
s = edit(s, '    g.enable_strategy_two = True\n', '    g.enable_strategy_two = False  # e9-u3: only 择时三 votes\n');
// logging-only lines, verbatim from build-e9-u2.js
s = edit(s,
  '#        log.info(f"启用择时的信号：{enabled_strategies}，最终信号={final_signal}，理由={decision_reason}")\n',
  '        log.info(f"启用择时的信号：{enabled_strategies}，最终信号={final_signal}，理由={decision_reason}")\n');
s = edit(s,
  '    if not hasattr(g, \'signal\') or g.signal != final_signal:\n',
  '    log.info(f"SIGDAY s1={s1_signal} s2={s2_signal} s3={s3_signal} final={final_signal} prev={getattr(g, \'signal\', None)} reason={decision_reason}")  # e9-u2 probe\n' +
  '    if not hasattr(g, \'signal\') or g.signal != final_signal:\n');
s = edit(s,
  '    """月度调仓主函数"""\n',
  '    """月度调仓主函数"""\n    log.info(f"MONTHLY signal={g.signal} trade_allowed={g.today_trade_allowed} n_pos={len(context.portfolio.positions)}")  # e9-u2 probe\n');
s = edit(s,
  '    if top_divergence:\n        g.dbl.append(True)\n',
  '    if top_divergence:\n        log.info(f"DAPAN top_divergence signal={g.signal} n_pos={len(context.portfolio.positions)}")  # e9-u2 probe\n        g.dbl.append(True)\n');

const outText = s + OVERRIDE;
const u2 = fs.readFileSync(path.join(__dirname, 'variants', 'u2-e9_signal-log.py'), 'utf8').split('\n');
const mine = outText.split('\n');
if (u2.length !== mine.length) throw new Error('line count differs from u2');
const diff = mine.map((l, i) => (l !== u2[i] ? i : -1)).filter(i => i >= 0);
if (diff.length !== 2
    || !mine[diff[0]].includes('enable_strategy_one = False')
    || !mine[diff[1]].includes('enable_strategy_two = False')) throw new Error('diff vs u2: ' + diff);

const out = path.join(__dirname, 'variants', 'u3-e9_s3-only.py');
fs.writeFileSync(out, outText);
console.log('built', out, '| differs from u2 only at lines', diff.map(i => i + 1).join(','));
