// e9-u2 probe: LOGGING ONLY on the base 2f5bc859. No logic change — the curve must be bit-identical
// to the stored e9 base curve (control). Same build rule as build-e6.js: py2to3 + asserted edits + OVERRIDE.
//  (1) uncomment the author's signal-change log line (baseline-e6.py:452) verbatim;
//  (2) a daily SIGDAY line with the RAW s1/s2/s3 (enabled_strategies drops empty/neutral voters);
//  (3) a MONTHLY line at monthly_adjustment entry (signal + trade-allowed at the rebalance);
//  (4) a DAPAN line when top_divergence fires (the liquidation route).
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

// sanity: the source this builds from is the one baseline-e6.py was built from
const base = fs.readFileSync(path.join(__dirname, 'baseline-e6.py'), 'utf8');
if (base !== src + OVERRIDE) throw new Error('baseline-e6.py != py2to3(src)+OVERRIDE — rebuild base first');

let s = src;
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

const out = path.join(__dirname, 'variants', 'u2-e9_signal-log.py');
fs.writeFileSync(out, s + OVERRIDE);
console.log('built', out);
