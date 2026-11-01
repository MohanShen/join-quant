// bank-imp-eqw: base = variants/u-e9-dypit.py (NOT baseline.py). ONE asserted logic edit:
//   per-name target = total_value * target_position_ratio / max(1, len(target_holdings)), computed
//   AFTER target_holdings is final, replacing `/ g.min_holdings` at L221. The 40% cap in the 调仓
//   loop is unchanged.
// Observation only (try/except -> log.error):
//   EXPO date=<d> pre=<positions_value/total_value>   at the top of every rebalance (all 51 Fridays)
//   EQW  date=<d> n_target=<k> ratio=<r> base_per=<..> eqw_per=<..> base_intended=<..> invested=<..>
//        after the order loop (only on paths that reach 调仓)
// base_intended = min(1, k * min(base_per, 0.4*tv)/tv) — what dypit's sizing would have aimed at.
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const BASE = path.join(__dirname, 'variants', 'u-e9-dypit.py');
const full = fs.readFileSync(BASE, 'utf8');
if (!full.endsWith(OVERRIDE)) throw new Error('dypit does not end with the current OVERRIDE');
const raw = full.slice(0, full.length - OVERRIDE.length);

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// (1) the logic edit: L221 no longer sets the per-name target (kept as a logging-only value)
const L221 = "    target_per_stock_value = (total_value * target_position_ratio) / g.min_holdings\n";
let body = edit(raw, L221,
  "    _eqw_base_per = (total_value * target_position_ratio) / g.min_holdings  # bank-imp-eqw: dypit's sizing, logging only\n");
const T = "    # ----- 调仓 -----\n";
body = edit(body, T,
  "    target_per_stock_value = (total_value * target_position_ratio) / max(1, len(target_holdings))  # bank-imp-eqw\n" + T);

// (2a) EXPO at top of rebalance
const R = "def rebalance(context):\n";
body = edit(body, R, R +
  "    try:  # bank-imp-eqw EXPO (observation only)\n" +
  "        log.error('EXPO date=%s pre=%.6f' % (str(context.current_dt.date()), context.portfolio.positions_value / context.portfolio.total_value))\n" +
  "    except Exception as _e:\n" +
  "        log.error('EXPO-ERR %r' % (_e,))\n");

// (2b) EQW after the order loop (end of file body)
const E = "        order_target_value(stock, target_value)\n";
if (!body.replace(/\s*$/, '\n').endsWith(E)) throw new Error('rebalance order loop is not at the end');
body = body.replace(/\n*$/, '\n') +
  "    try:  # bank-imp-eqw EQW (observation only)\n" +
  "        _k = len(target_holdings)\n" +
  "        _bi = min(1.0, _k * min(_eqw_base_per, total_value * 0.4) / total_value)\n" +
  "        log.error('EQW date=%s n_target=%d ratio=%.2f base_per=%.2f eqw_per=%.2f base_intended=%.6f invested=%.6f' % (str(context.current_dt.date()), _k, target_position_ratio, _eqw_base_per, target_per_stock_value, _bi, context.portfolio.positions_value / context.portfolio.total_value))\n" +
  "    except Exception as _e:\n" +
  "        log.error('EQW-ERR %r' % (_e,))\n\n";

for (const k of ['order_target(', 'order_target_value(', 'order(']) {
  if (body.split(k).length !== raw.split(k).length) throw new Error('order calls changed: ' + k);
}
if (!body.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');
if (!body.includes('max_single = total_value * 0.4')) throw new Error('40% cap missing');
if ((body.match(/target_per_stock_value =/g) || []).length !== 1) throw new Error('per-name target assigned != once');
// purely additive apart from the one edit: strip observation blocks + revert the edit -> raw
let back = body
  .replace(/ *try:  # bank-imp-eqw (EXPO|EQW) \(observation only\)\n(?:        .*\n)+?    except Exception as _e:\n        log.error\('(EXPO|EQW)-ERR %r' % \(_e,\)\)\n\n?/g, '')
  .replace("    target_per_stock_value = (total_value * target_position_ratio) / max(1, len(target_holdings))  # bank-imp-eqw\n", '')
  .replace("    _eqw_base_per = (total_value * target_position_ratio) / g.min_holdings  # bank-imp-eqw: dypit's sizing, logging only\n", L221);
if (back.replace(/\n*$/, '') !== raw.replace(/\n*$/, '')) throw new Error('variant is not dypit + one edit + observation');

const out = path.join(__dirname, 'variants', 'bank-imp-eqw.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built study/银行股轮动/variants/bank-imp-eqw.py');
