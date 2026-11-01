// u-e9-inv-h: score informativeness on HONEST dividends. Base = variants/u-e9-dypit.py (verbatim,
// already carries py2to3 + OVERRIDE + the a_bonus_date upper bound + RANK/DYZERO/HOLD observation
// lines, all kept as log-only). Two asserted behavioural edits, identical to build-inv.js:
//   L196 sorted(scores...) reverse=True -> reverse=False
//   L210 eligible_stocks.sort(...) reverse=True -> reverse=False
// plus observation only: INV date=<d> n_eligible=<k> order=<codes> after the L210 sort.
// DECISION RULE (queue.json, declared before the run, anchored to dypit):
//   CONFIRM score if Δobj <= -0.08 OR Δsharpe <= -0.55; REFUTE if |Δsharpe| <= 0.3 AND |Δobj| <= 0.03;
//   else partial. Valid only if n_eligible >= 3 in >= 8 weeks.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const base = fs.readFileSync(path.join(__dirname, 'variants/u-e9-dypit.py'), 'utf8');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

const S1 = 'sorted_stocks = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)';
let body = edit(base, S1, S1.replace('reverse=True', 'reverse=False') + '  # u-e9-inv-h: inverted');
const S2 = '    eligible_stocks.sort(key=lambda x: scores.get(x, 0), reverse=True)\n';
body = edit(body, S2,
  '    eligible_stocks.sort(key=lambda x: scores.get(x, 0), reverse=False)  # u-e9-inv-h: inverted\n' +
  '    try:  # u-e9-inv-h INV (observation only)\n' +
  "        log.error('INV date=%s n_eligible=%d order=%s' % (str(context.current_dt.date()), len(eligible_stocks), ','.join(eligible_stocks) or '-'))\n" +
  '    except Exception as _e:\n' +
  "        log.error('INV-ERR %r' % (_e,))\n");

if ((body.match(/reverse=True/g) || []).length !== (base.match(/reverse=True/g) || []).length - 2) throw new Error('reverse count');
for (const k of ['order_target', 'order_value', 'order(']) {
  if (body.split(k).length !== base.split(k).length) throw new Error('order calls changed: ' + k);
}
if (!body.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');
if (!body.includes('a_bonus_date <= context.current_dt.date()')) throw new Error('honest-dy edit missing');

const out = path.join(__dirname, 'variants', 'u-e9-inv-h.py');
fs.writeFileSync(out, body);
console.log('built', path.relative(ROOT, out));
