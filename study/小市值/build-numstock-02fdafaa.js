// q-e9-champ-numstock — reverse ablation on the 小市值 epoch-9 champion
// `strategies/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa.py`
// (control: its own epoch-9 row, objective 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63).
//
// The book DEFINES adjust_stock_num (L576-590: 399101 close - MA10 point spread => 3..6 names) and
// never calls it, so it runs at g.stock_num = 6 (L50) throughout. This build turns it on — ONE
// behavioural edit — plus log-only instrumentation, exactly as pre-registered in queue.json.
//
//   EDIT 1  after L145 (inside weekly_adjustment's `if g.no_trading_today_signal == False:`,
//           before close_no_trading_hold):   g.stock_num = adjust_stock_num(context)
//   I-1     same place, next line: NUMSTOCK line via _numstock_probe (a verbatim copy of
//           adjust_stock_num's data fetch; adjust_stock_num itself is untouched)
//   I-2     after L177 (end of that branch): NUMHELD line
//   I-3     after L561 (close_account, after the defensive basket buy): NUMDEF line
//   helper  after L590 (end of adjust_stock_num): def _numstock_probe
//
// ⚠ Insertions are placed by ORIGINAL LINE NUMBER, applied in DESCENDING order, never by string
// match: `if g.no_trading_today_signal == False:` occurs at both L145 and L233.
// ⚠ Assertions test the CODE side of a line only (`codeOf` strips trailing `#` comments) — three
// builders in this directory refused correct builds by matching their own comments.
// ⚠ Undo is by POSITION: the (origLine, count) table maps the variant back to py2to3(raw), which
// must be reproduced byte-for-byte on the pre-OVERRIDE body.
// log.error is used so the lines survive log.set_level (same channel as build-benchsem).

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const OUT = path.join(__dirname, 'variants/02fdafaa-numstock.py');

const codeOf = (l) => {
  const i = l.indexOf('#');
  return (i === -1 ? l : l.slice(0, i)).trimEnd();
};

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /02fdafaa/.test(f));
if (!src) throw new Error('02fdafaa not found in strategies/');
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));
const lines = raw.split('\n');
const L = n => lines[n - 1];

// ---- anchors on ORIGINAL line numbers (code side) ----
const expect = (n, code) => {
  if (codeOf(L(n)) !== code) throw new Error(`L${n} is not what the design says: ${JSON.stringify(L(n))}`);
};
expect(144, 'def weekly_adjustment(context):');
expect(145, '    if g.no_trading_today_signal == False:');
expect(146, '        close_no_trading_hold(context)');
expect(177, '            g.not_buy_again.append(stock)');
expect(178, '');                                   // whitespace-only line, branch ends at 177
expect(233, '    if g.no_trading_today_signal == False:');   // the second occurrence — must NOT be touched
expect(552, 'def close_account(context):');
expect(561, '            buy_security(context, g.no_trading_buy)');
expect(562, '            g.no_trading_hold_signal = True');
expect(576, 'def adjust_stock_num(context):');
expect(590, '    return result');
expect(50, '    g.stock_num = 6');
const callsOf = ls => ls.filter(l => /adjust_stock_num\(/.test(codeOf(l)) && !/^def adjust_stock_num\(/.test(codeOf(l))).length;
if (callsOf(lines) !== 0) throw new Error('raw already calls adjust_stock_num — refusing');
if (/_numstock_probe|NUMSTOCK/.test(raw)) throw new Error('raw already carries numstock instrumentation');
const adjBody = lines.slice(575, 590).join('\n');

const EDIT1 = '        g.stock_num = adjust_stock_num(context)  # numstock EDIT 1: the ONLY behavioural change';
const I1 = "        _ns = _numstock_probe(context); log.error('NUMSTOCK date=%s close=%.4f ma=%.4f diff=%.4f pct=%.6f n=%d probe=%d held_before=%d%s' % (str(context.previous_date), _ns[0], _ns[1], _ns[2], _ns[2] / _ns[1], g.stock_num, _ns[3], len(context.portfolio.positions), (' MISMATCH=1' if g.stock_num != _ns[3] else '')))  # numstock I-1 (log only)";
const I2 = "        log.error('NUMHELD date=%s n=%d held_after=%d' % (str(context.current_dt.date()), g.stock_num, len(context.portfolio.positions)))  # numstock I-2 (log only)";
const I3 = "            log.error('NUMDEF date=%s n=%d invested_frac=%.4f' % (str(context.current_dt.date()), g.stock_num, 3.0 / g.stock_num))  # numstock I-3 (log only)";
const HELPER = [
  '',
  '',
  '# numstock I-1 helper (log only): a VERBATIM copy of adjust_stock_num\'s data fetch and banding,',
  '# returning (close, ma, diff, n_probe). adjust_stock_num itself is not modified.',
  'def _numstock_probe(context):',
  '    try:',
  '        ma_para = 10',
  '        today = context.previous_date',
  '        start_date = today - datetime.timedelta(days = ma_para*2)',
  "        index_df = get_price('399101.XSHE', start_date=start_date, end_date=today, frequency='daily')",
  "        index_df['ma'] = index_df['close'].rolling(window=ma_para).mean()",
  '        last_row = index_df.iloc[-1]',
  "        diff = last_row['close'] - last_row['ma']",
  '        result = 3 if diff >= 500 else \\',
  '                 3 if 200 <= diff < 500 else \\',
  '                 4 if -200 <= diff < 200 else \\',
  '                 5 if -500 <= diff < -200 else \\',
  '                 6',
  "        return (float(last_row['close']), float(last_row['ma']), float(diff), result)",
  '    except Exception as e:',
  "        log.error('NUMSTOCK-FAIL date=%s err=%s' % (str(context.previous_date), e))",
  "        return (float('nan'), float('nan'), float('nan'), -1)",
];

// (afterOrigLine, insertedLines). Applied in DESCENDING order so no insertion shifts a later anchor.
const PLAN = [
  [590, HELPER],
  [561, [I3]],
  [177, [I2]],
  [145, [EDIT1, I1]],
].sort((a, b) => b[0] - a[0]);

const out = lines.slice();
for (const [after, ins] of PLAN) out.splice(after, 0, ...ins);
const body = out.join('\n');

// ---- assertions on the built body (code side) ----
const bl = body.split('\n');
// map orig line -> new index via the position table
const shift = n => PLAN.filter(([a]) => a < n).reduce((s, [, ins]) => s + ins.length, 0);
const at = n => bl[n - 1 + shift(n)];
if (codeOf(bl[145]) !== '        g.stock_num = adjust_stock_num(context)') {   // bl[145] = new line 146
  throw new Error('EDIT 1 is not the first line inside the L145 branch');
}
if (codeOf(at(145)) !== '    if g.no_trading_today_signal == False:' || codeOf(at(146)) !== '        close_no_trading_hold(context)') {
  throw new Error('L145/L146 anchors moved');
}
if (bl.indexOf(EDIT1) + 2 !== bl.indexOf(at(146))) throw new Error('EDIT1 + I-1 do not sit directly before close_no_trading_hold');
if (callsOf(bl) !== 1) throw new Error(`expected exactly 1 call of adjust_stock_num, got ${callsOf(bl)}`);
if (bl.slice(575 + shift(576), 590 + shift(576)).join('\n') !== adjBody) throw new Error('adjust_stock_num body changed');
if (codeOf(at(233)) !== '    if g.no_trading_today_signal == False:' || /numstock/.test(bl[233 - 1 + shift(233) + 1])) {
  throw new Error('L233 branch was touched');
}
// undo by POSITION, descending positions in the NEW file
const undone = bl.slice();
const asc = PLAN.slice().sort((a, b) => a[0] - b[0]);
let off = 0; const spans = [];
for (const [after, ins] of asc) { spans.push([after + off, ins.length]); off += ins.length; }
for (const [pos, cnt] of spans.sort((a, b) => b[0] - a[0])) undone.splice(pos, cnt);
if (undone.join('\n') !== raw) {
  const first = undone.findIndex((l, i) => l !== lines[i]);
  throw new Error(`undo does not reproduce py2to3(raw) byte-for-byte (first diff line ${first + 1}) — refusing`);
}

fs.writeFileSync(OUT, body + OVERRIDE);
console.log('[numstock] built', path.relative(ROOT, OUT));
console.log('[numstock] insertions (origLine:count):', asc.map(([a, i]) => `${a}:${i.length}`).join(' '));
console.log('[numstock] adjust_stock_num calls 0 -> 1; body verbatim; L233 untouched; undo byte-identical');
