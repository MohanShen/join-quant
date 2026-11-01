// u-e9-inv: score informativeness. Base 2a323522 + py2to3 + OVERRIDE (== baseline.py) plus:
//   (1) TWO asserted behavioural edits: reverse=True -> reverse=False at the fallback
//       sorted(scores...) (baseline L147) and at eligible_stocks.sort (baseline L157).
//   (2) observation only: INVTICK at top of rebalance(), INV after the L157 sort with
//       date, n_eligible and the full chosen order (first g.max_holdings are the targets).
// DECISION RULE (queue.json, declared before the run): CONFIRM score if inverted sharpe <= 1.8
// OR Δobjective <= -0.08; REFUTE if sharpe within ±0.3 of 2.37 — only if BINDING weeks
// (n_eligible >= 3) >= ~8, else 'untested on this bench'.
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

const S1 = 'sorted_stocks = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)';
let body = edit(raw, S1, S1.replace('reverse=True', 'reverse=False') + '  # u-e9-inv: inverted');
const S2 = '    eligible_stocks.sort(key=lambda x: scores.get(x, 0), reverse=True)\n';
body = edit(body, S2,
  '    eligible_stocks.sort(key=lambda x: scores.get(x, 0), reverse=False)  # u-e9-inv: inverted\n' +
  "    log.error('INV date=%s n_eligible=%d order=%s' % (str(context.current_dt.date()), len(eligible_stocks), ','.join(eligible_stocks)))  # observation only\n");
const HEAD = '\ndef rebalance(context):\n';
body = edit(body, HEAD, HEAD + "    log.error('INVTICK date=%s' % str(context.current_dt.date()))  # observation only\n");

if ((body.match(/reverse=True/g) || []).length !== (raw.match(/reverse=True/g) || []).length - 2) throw new Error('reverse count');
if ((body.match(/order_target/g) || []).length !== (raw.match(/order_target/g) || []).length) throw new Error('order calls changed');
if (!body.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, 'inv.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
