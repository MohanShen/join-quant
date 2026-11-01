// Builds study/向导式低波价值/variants/u-4.py — u-4, yuan-ATR<0.15 gate on the full HS300 with the
// PE 6-11 band REMOVED, under the shared pool-EW harness. Control = u-7.
// = baseline.py (py2to3 + live OVERRIDE) + applyHarness() (identical to u-7)
// + exactly ONE asserted functional edit: financial_statements_filter's
//     financial_data_filter_qujian(security_list, valuation.pe_ratio, (6,11))
//   becomes a pass-through (security_list unchanged).
// + a LOGGING-ONLY block right after the (unchanged) yuan-ATR entry line, marked # u-4 LOG:
//     U4CNT date n_checkout n_b_atr          (= CNT stage=b_atr, every one of the 25 buy dates)
//     U4PE  date code pe close inband        (every gate admission; PE at previous_date, close = previous close)
//   Nothing in the log block assigns buy_lists or touches orders.
// Decision rule (queue u-4): NON-BINDING if day-1 POOL0 == u-7's 6 codes.
const fs = require('fs');
const path = require('path');
const { loadBase, applyHarness, edit } = require('./pool-ew-harness');
const ROOT = path.join(__dirname, '..', '..');

const PE_FROM = '    security_list = financial_data_filter_qujian(security_list, valuation.pe_ratio, (6,11))\n';
const PE_TO = '    security_list = list(security_list)  # u-4 EDIT: PE 6-11 band removed (was: financial_data_filter_qujian(security_list, valuation.pe_ratio, (6,11)))\n';

const ATR_LINE = '        buy_lists = [security for security in buy_lists if ATR_judge_xiaoyu(security, 0.15, 14)]\n';
const LOG = [
  '        try:',
  "            _u4_d = context.current_dt.strftime('%Y-%m-%d')",
  "            log.info('U4CNT date=%s n_checkout=%d stage=b_atr n=%d' % (_u4_d, len(g.check_out_lists), len(buy_lists)))",
  '            _u4_pe = {}',
  '            if len(buy_lists) > 0:',
  '                _u4_df = get_fundamentals(query(valuation.code, valuation.pe_ratio).filter(valuation.code.in_(list(buy_lists))), date=context.previous_date)',
  '                for _u4_i in range(len(_u4_df)):',
  "                    _u4_pe[_u4_df['code'].iloc[_u4_i]] = _u4_df['pe_ratio'].iloc[_u4_i]",
  '            for _u4_c in buy_lists:',
  '                try:',
  "                    _u4_cl = attribute_history(_u4_c, 1, '1d', ['close'])['close'].values[-1]",
  '                except Exception:',
  '                    _u4_cl = float(\'nan\')',
  '                _u4_p = _u4_pe.get(_u4_c, None)',
  '                _u4_in = (_u4_p is not None) and (_u4_p >= 6) and (_u4_p <= 11)',
  "                log.info('U4PE date=%s code=%s pe=%s close=%.4f inband=%s' % (_u4_d, _u4_c, ('%.4f' % _u4_p) if _u4_p is not None else 'NA', _u4_cl, _u4_in))",
  '        except Exception as _u4_e:',
  "            log.info('U4ERR %s' % _u4_e)",
].map(l => l + '  # u-4 LOG').join('\n') + '\n';

let src = applyHarness(loadBase());
src = edit(src, PE_FROM, PE_TO);                 // THE ONE FUNCTIONAL EDIT
src = edit(src, ATR_LINE, ATR_LINE + LOG);       // logging only
src = edit(src, src.split('\n')[0] + '\n',
  '# study variant u-4 — family: 向导式低波价值 — pool-EW harness + PE 6-11 band REMOVED (yuan-ATR<0.15 gate kept, full HS300); control = u-7\n' +
  '# built from study/向导式低波价值/baseline.py by study/向导式低波价值/build-u-4.js via pool-ew-harness.js; harness edits # HARNESS, the one variant edit # u-4 EDIT, logging # u-4 LOG\n');

const code = src.split('\n').map(l => l.split('#')[0]).join('\n');
if (code.includes('financial_data_filter_qujian(security_list, valuation.pe_ratio')) throw new Error('PE band still live');
for (const keep of [ATR_LINE.trim(), "set_option('avoid_future_data', True)", 'high_limit_filter(context, buy_lists)']) {
  if (!src.includes(keep)) throw new Error('lost: ' + keep);
}
// diff vs u-7 outside the header: exactly the PE line replaced + the inserted log block
const u7 = fs.readFileSync(path.join(__dirname, 'variants', 'u-7.py'), 'utf8').split('\n').slice(2);
const u4 = src.split('\n').slice(2);
const iA = u7.findIndex(l => l + '\n' === ATR_LINE);
const iP = u7.findIndex(l => l + '\n' === PE_FROM);
if (iA < 0 || iP < 0 || !(iA < iP)) throw new Error('anchors');
const logLines = LOG.split('\n').slice(0, -1);
const recon = [...u7.slice(0, iA + 1), ...logLines, ...u7.slice(iA + 1)];
recon[iP + logLines.length] = PE_TO.replace(/\n$/, '');
if (recon.length !== u4.length || recon.some((l, i) => l !== u4[i])) throw new Error('diff vs u-7 is not exactly edit + log block');
// log block must not assign buy_lists or order
for (const l of logLines) if (/buy_lists\s*=|order\(/.test(l.split('#')[0])) throw new Error('log block is not logging-only: ' + l);

const out = path.join(__dirname, 'variants', 'u-4.py');
fs.writeFileSync(out, src);
console.log('built', path.relative(ROOT, out), 'log lines', logLines.length, 'functional edit at u-7 line', iP + 3);
