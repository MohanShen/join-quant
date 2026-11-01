// u-e9-nobb: Bollinger mid-band filter off. Base 2a323522 + py2to3 + OVERRIDE (== baseline.py) plus:
//   (1) ONE asserted behavioural edit: the L137 condition `if bb['close'] <= bb['ma']:` -> `if True:`
//       so every scored bank (with a computable band) is eligible.
//   (2) observation only: NBB (date, n_eligible) after the L157 sort; MA (ICBC close/ma250/ratio)
//       after the target_position_ratio block; STOP (date/code/loss) inside the -12% branch.
// DECISION RULE (queue.json): REFUTE filter if sharpe >= 2.2 AND maxDD rises <= 2pp;
// CONFIRM if sharpe <= 1.9 OR maxDD rises >= 3pp; between = partial.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-26_自己搭建的一个10年230_收益率的银行股策略-2a323522.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// (1) behavioural
const C = "        if bb['close'] <= bb['ma']:\n            eligible_stocks.append(stock)\n";
let body = edit(raw, C, "        if True:  # u-e9-nobb: Bollinger filter off\n            eligible_stocks.append(stock)\n");

// (2) observation only
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

if ((body.match(/order_target/g) || []).length !== (raw.match(/order_target/g) || []).length) throw new Error('order calls changed');
if (body.includes("bb['close'] <= bb['ma']")) throw new Error('filter still present');
if (!body.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, 'nobb.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
