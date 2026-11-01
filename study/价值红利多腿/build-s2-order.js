// q-e9-s2-order: base = study/价值红利多腿/variants/q-e9-orphan-fix.py (current reference; already
// py2to3 + OVERRIDE). ONE asserted edit at s2's final cut: first-N -> last-N of the unsorted final
// list, plus one log-only line `S2LEN <date> <n> <full list>` beside it. Full book (sleeves are
// additive; s2's P&L is read by subtraction against the reference's s1+s3+s4).
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const BASE_REL = 'study/价值红利多腿/variants/q-e9-orphan-fix.py';
const baseFull = fs.readFileSync(path.join(ROOT, BASE_REL), 'utf8');
const HDR_LINES = 4;
const lines = baseFull.split('\n');
if (!lines[0].startsWith('# q-e9-orphan-fix') || !lines[3].startsWith('# built:')) throw new Error('unexpected base header');
const raw = lines.slice(HDR_LINES).join('\n');
function once(hay, needle) {
  const n = hay.split(needle).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(needle)}`);
}
const A = "    final_list = list(df['code'])[:g.s2_stock_num]\n";
once(raw, A);
const B =
  "    log.info(\"S2LEN %s %d %s\" % (context.current_dt.date(), len(df), list(df['code'])))\n" +
  "    final_list = list(df['code'])[-g.s2_stock_num:]\n";
const body = raw.replace(A, B);
// diff is exactly: the slice flipped + one log line
const rl = raw.split('\n'), bl = body.split('\n');
if (bl.length !== rl.length + 1) throw new Error('line count');
const changed = bl.filter((l, i) => !rl.includes(l));
if (changed.length !== 2 || !changed[0].includes('S2LEN') || !changed[1].includes('[-g.s2_stock_num:]')) throw new Error('diff not as asserted: ' + JSON.stringify(changed));
if (body.replace(B, A) !== raw) throw new Error('not reversible');
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) if (!body.includes(pin)) throw new Error('missing pin ' + pin);
const header =
  `# q-e9-s2-order — family: 价值红利多腿\n` +
  `# source: ${BASE_REL} (reference: cf1ec5bd + s4 pit + orphan-fix + OVERRIDE)\n` +
  `# construction: base + ONE asserted edit: s2 final cut [:N] -> [-N:] (last-N of unsorted list) + log-only S2LEN line\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/价值红利多腿/build-s2-order.js\n`;
const out = path.join(__dirname, 'variants', 'q-e9-s2-order.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out), 'bytes', (header + body).length);
