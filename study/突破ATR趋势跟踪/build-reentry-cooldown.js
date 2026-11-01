// q-e9-atr-reentry-cooldown: q-e9-atr-bb-ablate (cond4-only entry) + a 1-trading-day re-entry
// cooldown. Built from the SAME source as build-bb-ablate.js (py2to3(src) + OVERRIDE) with the
// ablation's one edit, then ONE logical insertion in two asserted places:
//   (a) sell path: record the exit date per symbol, just before `del g.state[symbol]`;
//   (b) entry loop: right after the cond4 gate, skip a symbol whose last exit is within 1 trading
//       day — exit on day D blocks entry on D and D+1 (get_trade_days(end=today, count=2)[0] <= exit).
// Exits / sizing / regime / pool / schedule verbatim. Never edits strategies/.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'strategies', '2026-10-27_基于上一版本进行了适当调整_增加其攻击性-e79e9884.py');
const raw = py2to3(fs.readFileSync(SRC, 'utf8'));

function once(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match of ${JSON.stringify(from)}, got ${n}`);
  return s.replace(from, to);
}

// ablation edit (identical to build-bb-ablate.js)
const abl = once(raw, 'if not (cond1 and cond2 and cond3 and cond4):', 'if not cond4:');

// (a) record exit
const SELL = '        del g.state[symbol]\n';
const SELL_INS =
  "        if not hasattr(g, 'last_exit'):\n" +
  '            g.last_exit = {}\n' +
  '        g.last_exit[symbol] = current_date\n';
let body = once(abl, SELL, SELL_INS + SELL);

// (b) cooldown skip
const GATE = '        if not cond4:\n            continue\n';
const GATE_INS =
  "        _lx = getattr(g, 'last_exit', {}).get(symbol)\n" +
  '        if _lx is not None and _lx >= get_trade_days(end_date=current_date, count=2)[0]:\n' +
  "            log.info('COOLDOWN [%s] skip %s last_exit=%s' % (current_date, symbol, _lx))\n" +
  '            continue\n';
body = once(body, GATE, GATE + GATE_INS);

// assert: the diff vs the ablation is exactly the inserted lines, nothing else changed
const a = abl.split('\n'), b = body.split('\n');
const added = SELL_INS.split('\n').length - 1 + GATE_INS.split('\n').length - 1;
if (b.length - a.length !== added) throw new Error('unexpected line delta');
// positional: removing the two inserted blocks from the output must give back the ablation exactly
const strip = (s, ins) => { const n = s.split(ins).length - 1; if (n !== 1) throw new Error('inserted block not unique'); return s.replace(ins, ''); };
if (strip(strip(body, SELL_INS), GATE_INS) !== abl) throw new Error('non-inserted lines differ from the ablation');

const out = path.join(__dirname, 'variants', 'q-e9-atr-reentry-cooldown.py');
fs.writeFileSync(out, body + OVERRIDE);
// cross-check: the ablation part equals the shipped ablation variant
const shipped = fs.readFileSync(path.join(__dirname, 'variants', 'q-e9-atr-bb-ablate.py'), 'utf8');
if (shipped !== abl + OVERRIDE) throw new Error('ablation base differs from variants/q-e9-atr-bb-ablate.py');
console.log('built', path.relative(ROOT, out), `+${added} lines over q-e9-atr-bb-ablate`);
