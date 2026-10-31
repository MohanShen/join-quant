// Builds u-6 / liq-3 from study/资产配置/variants/u-4-textbook-pool.py by asserted edits only.
// u-6: u-4 + the u-2 DECOMP previous-close log line (log-only, no trading change) for the 5 u-4 codes.
// liq-3: u-4 + the liq-1 4e6/day liquidity floor, copied verbatim from build-u1-u3-liq1.js / liq-1-floor.py.
const fs = require('fs');
const path = require('path');
const D = __dirname + '/';
const u4 = fs.readFileSync(D + 'variants/u-4-textbook-pool.py', 'utf8');
const liq1 = fs.readFileSync(D + 'variants/liq-1-floor.py', 'utf8');
function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error('expected 1 match, got ' + n + ': ' + from.slice(0, 80));
  return s.replace(from, to);
}
const HDR = '# u-4 variant of study/资产配置/baseline.py\n';

// ---------- u-6 ----------
let u6 = edit(u4, HDR, '# u-6 variant of study/资产配置/variants/u-4-textbook-pool.py (DECOMP log only)\n');
u6 = edit(u6, `    g.trade_day_count += 1
`, `    g.trade_day_count += 1
    # u-6 DECOMP probe: previous closes (attribute_history at 09:00 => through previous_date)
    _codes = ['518880.XSHG', '513100.XSHG', '510300.XSHG', '511260.XSHG', '159985.XSHE']
    _vals = []
    for _s in _codes:
        try:
            _h = attribute_history(_s, 1, '1d', ['close'])
            _vals.append('%.4f' % float(_h['close'].iloc[-1]))
        except Exception as _e:
            _vals.append('nan')
    log.info('DECOMP %s %s' % (context.current_dt.date(), ' '.join(_vals)))
`);
fs.writeFileSync(D + 'variants/u-6-textbook-decomp.py', u6);

// ---------- liq-3 ----------
const FN_START = liq1.indexOf('# ---------------- liquidity floor');
const FN_END = liq1.indexOf('def order_target_by_lot(context, security, target_value, current_data):');
if (FN_START < 0 || FN_END < 0 || FN_END <= FN_START) throw new Error('liq-1 floor block not found');
const FLOOR_BLOCK = liq1.slice(FN_START, FN_END);
if (!FLOOR_BLOCK.includes('LIQ_FLOOR = 4000000\n')) throw new Error('liq-1 floor value not 4e6');
let l3 = edit(u4, HDR, '# liq-3 variant of study/资产配置/variants/u-4-textbook-pool.py (liq-1 4e6/day floor)\n');
l3 = edit(l3, `    target_values = {}
    for etf, weight in g.etf_weights.items():`, `    weights = liq_floor_weights(context)  # liq-3: ONLY change vs u-4-textbook-pool.py
    target_values = {}
    for etf, weight in weights.items():`);
l3 = edit(l3, `        if stock not in g.etf_weights:`, `        if stock not in weights:`);
l3 = edit(l3, `def order_target_by_lot(context, security, target_value, current_data):`,
  FLOOR_BLOCK + `def order_target_by_lot(context, security, target_value, current_data):`);
fs.writeFileSync(D + 'variants/liq-3-textbook-floor.py', l3);
console.log('built 2: variants/u-6-textbook-decomp.py variants/liq-3-textbook-floor.py');
