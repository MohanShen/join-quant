// u-e9-nobb-h: Bollinger mid-band filter off on HONEST dividends. Base = variants/u-e9-dypit.py
// (verbatim: py2to3 + OVERRIDE + a_bonus_date upper bound + RANK/DYZERO/HOLD log-only lines).
//   (1) ONE asserted behavioural edit, identical to build-nobb.js: L186 `if bb['close'] <= bb['ma']:`
//       -> `if True:` so every scored bank (with a computable band) is eligible.
//   (2) observation only (same lines as build-nobb.js): NBB after the L210 sort; MA after the
//       target_position_ratio block; STOP inside the -12% branch.
// DECISION RULE (queue.json, anchored to dypit): REFUTE filter if Δsharpe >= 0 AND ΔmaxDD <= +2pp;
// CONFIRM if Δsharpe <= -0.3 OR ΔmaxDD >= +3pp; else partial.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const base = fs.readFileSync(path.join(__dirname, 'variants/u-e9-dypit.py'), 'utf8');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

const C = "        if bb['close'] <= bb['ma']:\n            eligible_stocks.append(stock)\n";
let body = edit(base, C, "        if True:  # u-e9-nobb-h: Bollinger filter off\n            eligible_stocks.append(stock)\n");

const S = '    eligible_stocks.sort(key=lambda x: scores.get(x, 0), reverse=True)\n';
body = edit(body, S, S +
  "    log.error('NBB date=%s n_eligible=%d' % (str(context.current_dt.date()), len(eligible_stocks)))  # observation only\n");
const R = '        target_position_ratio = 1.0\n';
body = edit(body, R, R +
  "    log.error('MA date=%s icbc=%s ma250=%s ratio=%s' % (str(context.current_dt.date()), current_price_icbc, ma250, target_position_ratio))  # observation only\n");
const L = '                if loss_pct < -0.12:\n                    order_target(stock, 0)\n';
body = edit(body, L,
  "                if loss_pct < -0.12:\n" +
  "                    log.error('STOP date=%s code=%s loss=%.4f' % (str(context.current_dt.date()), stock, loss_pct))  # observation only\n" +
  "                    order_target(stock, 0)\n");

for (const k of ['order_target', 'order_value', 'order(']) {
  if (body.split(k).length !== base.split(k).length) throw new Error('order calls changed: ' + k);
}
if (body.includes("bb['close'] <= bb['ma']")) throw new Error('filter still present');
if (!body.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');
if (!body.includes('a_bonus_date <= context.current_dt.date()')) throw new Error('honest-dy edit missing');

const out = path.join(__dirname, 'variants', 'u-e9-nobb-h.py');
fs.writeFileSync(out, body);
console.log('built', path.relative(ROOT, out));
