// Builds variants/liq-i3-e9_floor-2e6.py = variants/i3-e9_no-s2.py (shelf product dxp-e9-i3)
// + EXACTLY the liquidity-floor edit build-liq.js applied to make variants/liq-1_floor-2e6.py.
//
// "Exactly the same" is enforced by LIFTING the floor text out of liq-1_floor-2e6.py rather than
// re-generating it (build-liq.js has top-level code and stamps today's date into the helper, so
// requiring or re-running it would write files and change the text). The chain insertion point
// (CHAIN) and the edit() rule are build-liq.js's, verbatim.
//
// The floor sits inside daily_my_trader_1, which is called by BOTH monthly_adjustment (month-start)
// AND check_limit_up_and_buy (the 14:00 refill, `elif g.signal == 'small': daily_my_trader_1(context)`),
// so the floor applies on the refill path with no further edit.
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { OVERRIDE } = require('../../utils/strategy-normalize');

const V = path.join(__dirname, 'variants');
const base = fs.readFileSync(path.join(V, 'i3-e9_no-s2.py'), 'utf8');
const liq1 = fs.readFileSync(path.join(V, 'liq-1_floor-2e6.py'), 'utf8');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}
const CHAIN = '    stocks = filter_highprice_stock(context, stocks)\n';

// floor lines as liq-1 carries them
const callLine = '    stocks = filter_liquidity_floor(context, stocks)  # liq-1_floor-2e6: ONLY change vs baseline-e6\n';
assert(liq1.includes(CHAIN + callLine), 'liq-1 does not carry the expected call line');
assert(liq1.endsWith(OVERRIDE), 'liq-1 does not end with the live OVERRIDE');
const hStart = liq1.indexOf('\n\n# ----------------- liquidity floor');
assert(hStart > 0, 'helper not found in liq-1');
const helper = liq1.slice(hStart, liq1.length - OVERRIDE.length);
assert(/^LIQ_FLOOR = 2e6$/m.test(helper), 'floor literal is not 2e6');
assert.strictEqual(eval(helper.match(/^LIQ_FLOOR = (\S+)$/m)[1]), 2000000);

// apply to the i3 product
assert(base.endsWith(OVERRIDE), 'i3-e9_no-s2.py does not end with the live OVERRIDE');
const body = base.slice(0, base.length - OVERRIDE.length);
const out = edit(body, CHAIN, CHAIN + callLine) + helper + OVERRIDE;

// diff check: removing exactly the floor lines must give back the base byte-for-byte
const restored = out.replace(callLine, '').replace(helper, '');
assert.strictEqual(restored, base, 'variant differs from i3-e9_no-s2.py by more than the floor lines');
assert.strictEqual(out.split('filter_liquidity_floor(context, stocks)').length - 1, 1);

// the refill path reaches the floored function
const refill = out.slice(out.indexOf('def check_limit_up_and_buy'), out.indexOf('def order_target_value_'));
assert(/g\.signal == 'small':\s*\n\s*daily_my_trader_1\(context\)/.test(refill), 'refill does not call daily_my_trader_1');

fs.writeFileSync(path.join(V, 'liq-i3-e9_floor-2e6.py'), out);
console.log('built liq-i3-e9_floor-2e6.py; added', out.length - base.length, 'chars; refill path calls daily_my_trader_1: yes');
