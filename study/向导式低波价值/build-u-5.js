// Builds study/向导式低波价值/variants/u-5.py — u-5, RELATIVE-ATR entry gate in place of yuan-ATR<0.15.
// = baseline.py (py2to3 + live OVERRIDE) + the shared POOL-EW HARNESS (identical to u-7)
// + exactly ONE asserted edit: the L196 entry filter
//     ATR_judge_xiaoyu(security, 0.15, 14)          (wizard, yuan)
//   becomes a local relative test  ATR/close < 0.01646, computed EXACTLY as the u-2 probe computed
//   rel15 (build-u-2.js _probe_atr): attribute_history(c, 60, '1d', [high, low, close]) up to
//   previous_date, talib.ATR(hi[-15:], lo[-15:], cl[-15:], 14)[-1] / cl[-1].
//   k = 0.01646 was fixed on rel15 from the u-2 day-1 log (601319 rel15 0.01638 in, 601318 0.01654 out),
//   so the 15-bar basis is used here even though u-2 found 60-bar Wilder fits the WIZARD's yuan
//   boolean better (98.6% vs 97.4%): rel60 at the same k would admit only 4 day-1 names
//   (601319 rel60 0.01772, 600104 0.01870 fall out) and void the run.
// Logging (inside the same edit block): U5REL per candidate per check date, U5GATE count per date.
// Control = u-7. VALIDITY: day-1 POOL0 must equal {601006 600018 600332 600362 600104 601319}.
const fs = require('fs');
const path = require('path');
const { loadBase, applyHarness, edit } = require('./pool-ew-harness');
const ROOT = path.join(__dirname, '..', '..');

const FROM = '        buy_lists = [security for security in buy_lists if ATR_judge_xiaoyu(security, 0.15, 14)]\n';
const TO = [
  "        _u5_d = context.current_dt.strftime('%Y-%m-%d')",
  '        _u5_n0 = len(buy_lists)',
  '        _u5_keep = []',
  '        for _u5_s in buy_lists:',
  '            try:',
  "                _u5_h = attribute_history(_u5_s, 60, '1d', ['high', 'low', 'close'])",
  "                _u5_hi = np.array(_u5_h['high'].values, dtype=float)",
  "                _u5_lo = np.array(_u5_h['low'].values, dtype=float)",
  "                _u5_cl = np.array(_u5_h['close'].values, dtype=float)",
  '                _u5_a = talib.ATR(_u5_hi[-15:], _u5_lo[-15:], _u5_cl[-15:], 14)[-1]',
  '                _u5_r = _u5_a / _u5_cl[-1]',
  '                _u5_in = bool(_u5_r < 0.01646)',
  '                if _u5_in:',
  '                    _u5_keep.append(_u5_s)',
  "                log.info('U5REL date=%s code=%s close=%.4f atr15=%.5f rel15=%.5f in=%s' % (_u5_d, _u5_s, _u5_cl[-1], _u5_a, _u5_r, _u5_in))",
  '            except Exception as _u5_e:',
  "                log.info('U5ERR date=%s code=%s err=%s' % (_u5_d, _u5_s, _u5_e))",
  "        log.info('U5GATE date=%s n_pre=%d n_in=%d codes=%s' % (_u5_d, _u5_n0, len(_u5_keep), ','.join(_u5_keep)))",
  '        buy_lists = _u5_keep',
].map(l => l + '  # u-5 EDIT (relative ATR/close<0.01646, rel15 basis; was ATR_judge_xiaoyu(security, 0.15, 14) yuan)').join('\n') + '\n';

let src = applyHarness(loadBase());
// THE ONE EDIT
src = edit(src, FROM, TO);
// header (comment only)
src = edit(src, src.split('\n')[0] + '\n',
  '# study variant u-5 — family: 向导式低波价值 — pool-EW harness + entry gate yuan-ATR<0.15 -> relative ATR/close<0.01646 (rel15); control = u-7\n' +
  '# built from study/向导式低波价值/baseline.py by study/向导式低波价值/build-u-5.js via pool-ew-harness.js; harness edits marked # HARNESS, the one variant edit marked # u-5 EDIT\n');

const code = src.split('\n').map(l => l.split('#')[0]).join('\n');
if (code.includes('ATR_judge_xiaoyu(security, 0.15')) throw new Error('yuan entry gate still live');
for (const keep of ['valuation.pe_ratio, (6,11)', "set_option('avoid_future_data', True)", 'high_limit_filter(context, buy_lists)', 'import talib', 'import numpy as np']) {
  if (!src.includes(keep)) throw new Error('lost: ' + keep);
}
// diff vs u-7 outside the header: exactly the one edit (u-7's L196 replaced by the marked block)
const u7 = fs.readFileSync(path.join(__dirname, 'variants', 'u-7.py'), 'utf8').split('\n').slice(2);
const u5 = src.split('\n').slice(2);
const i0 = u7.findIndex(l => l + '\n' === FROM);
if (i0 < 0) throw new Error('u-7 lacks the anchor line');
const nNew = TO.split('\n').length - 1;
const recon = [...u7.slice(0, i0), ...u5.slice(i0, i0 + nNew), ...u7.slice(i0 + 1)];
if (recon.length !== u5.length || recon.some((l, i) => l !== u5[i])) throw new Error('diff vs u-7 is not exactly the one edit');
if (!u5.slice(i0, i0 + nNew).every(l => l.includes('# u-5 EDIT'))) throw new Error('unmarked line in edit block');

const out = path.join(__dirname, 'variants', 'u-5.py');
fs.writeFileSync(out, src);
console.log('built', path.relative(ROOT, out), 'edit-block lines', nNew, 'replacing u-7 line', i0 + 3);
