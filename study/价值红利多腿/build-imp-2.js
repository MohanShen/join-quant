// dvl-imp-2: base = study/价值红利多腿/variants/q-e9-orphan-fix.py (reference; already py2to3 +
// OVERRIDE). ONE asserted edit before s2's final cut: order df by the position of each code in the
// dividend-ranked stock_list (_s2_dividend_filter returns DR sorted by dividend_ratio DESCENDING —
// sort=False => ascending=False — and the PEG / industry filters preserve that order), then keep
// the first N. Log-only `S2LEN <date> <n> <list in yield order>` beside it (as q-e9-s2-order).
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const BASE_REL = 'study/价值红利多腿/variants/q-e9-orphan-fix.py';
const baseFull = fs.readFileSync(path.join(ROOT, BASE_REL), 'utf8');
const lines = baseFull.split('\n');
if (!lines[0].startsWith('# q-e9-orphan-fix') || !lines[3].startsWith('# built:')) throw new Error('unexpected base header');
const raw = lines.slice(4).join('\n');
function once(hay, needle) {
  const n = hay.split(needle).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(needle)}`);
}
// stock_list must still be the yield-ordered list at the cut (no reassignment after the industry filter)
once(raw, '    stock_list = _s2_filter_excluded_industries(stock_list)\n');
once(raw, "DR = DR.sort_values(by=['dividend_ratio'], ascending=sort)\n");
once(raw, 'stock_list = _s2_dividend_filter(context, choice, False, 0, 0.1)\n');
const A = "    final_list = list(df['code'])[:g.s2_stock_num]\n";
once(raw, A);
const B =
  "    df['_r'] = df['code'].map({c: i for i, c in enumerate(stock_list)})\n" +
  "    df = df.sort_values('_r')\n" +
  "    log.info(\"S2LEN %s %d %s\" % (context.current_dt.date(), len(df), list(df['code'])))\n" +
  "    final_list = list(df['code'])[:g.s2_stock_num]\n";
const body = raw.replace(A, B);
const rl = raw.split('\n'), bl = body.split('\n');
if (bl.length !== rl.length + 3) throw new Error('line count');
if (body.replace(B, A) !== raw) throw new Error('not reversible');
const after = body.slice(body.indexOf("stock_list = _s2_filter_excluded_industries"), body.indexOf("df['_r']"));
if (/\n\s+stock_list\s*=/.test(after)) throw new Error('stock_list reassigned before the cut');
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) if (!body.includes(pin)) throw new Error('missing pin ' + pin);
const header =
  `# dvl-imp-2 — family: 价值红利多腿\n` +
  `# source: ${BASE_REL} (reference: cf1ec5bd + s4 pit + orphan-fix + OVERRIDE)\n` +
  `# construction: base + ONE asserted edit: s2 df ordered by dividend-yield rank before the [:N] cut + log-only S2LEN line\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/价值红利多腿/build-imp-2.js\n`;
const out = path.join(__dirname, 'variants', 'dvl-imp-2.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out), 'bytes', (header + body).length);
