// u-5 ROE/ROA unit probe: base 0d1bbe83 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them)
// LOGGING ONLY — no trading-logic edit. Two asserted insertions in get_peg:
//   (1) snapshot the input candidate list before get_peg reassigns `stocks`;
//   (2) before `return stocks`, call an appended helper that re-queries the SAME candidates with
//       date=<the date get_peg already receives> (= context.previous_date) and log.error's counts and
//       raw indicator.roe / indicator.roa. The helper never touches `stocks`; any exception is logged.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-12_年化51_的晴雨双轨_小盘游击_ETF防御-0d1bbe83.py';
function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));
const INS1 = '    _u5_in = list(stocks)  # u-5 probe: logging only\n';
const INS2 = '    try:\n        _u5_probe(_u5_in, stocks, date)  # u-5 probe: logging only\n' +
             "    except Exception as e:\n        log.error('U5 ERROR %s' % e)  # u-5 probe\n";
let v = edit(raw, 'def get_peg(stocks, date):\n', 'def get_peg(stocks, date):\n' + INS1);
v = edit(v,
  "        date=date\n    )['code'].tolist()\n    return stocks\n",
  "        date=date\n    )['code'].tolist()\n" + INS2 + '    return stocks\n');

const HELPER = [
  '',
  '',
  '# --- u-5 probe helper (logging only; reads, never alters, get_peg result) ---',
  'def _u5_fmt(df):',
  "    return ' '.join('%s|mc=%.2f|roe=%s|roa=%s' % (r['code'], r['market_cap'], r['roe'], r['roa']) for _, r in df.iterrows())",
  '',
  '',
  'def _u5_q(x):',
  '    x = x.dropna()',
  '    if len(x) == 0:',
  "        return 'n=0'",
  "    return 'n=%d min=%.4f p10=%.4f p50=%.4f p90=%.4f max=%.4f' % (",
  '        len(x), x.min(), x.quantile(0.1), x.median(), x.quantile(0.9), x.max())',
  '',
  '',
  'def _u5_probe(cands, kept, date):',
  '    df = get_fundamentals(',
  '        query(valuation.code, valuation.market_cap, indicator.roe, indicator.roa',
  '              ).filter(valuation.code.in_(cands)',
  '              ).order_by(valuation.market_cap.asc()),',
  '        date=date)',
  '    n_in = len(cands)',
  '    n_out = len(kept)',
  "    log.error('U5 COUNT date=%s in=%d withFund=%d out=%d removed=%d removedFrac=%.4f min_roe=%s min_roa=%s' % (",
  '        date, n_in, len(df), n_out, n_in - n_out, (n_in - n_out) / float(max(n_in, 1)), g.min_roe, g.min_roa))',
  '    ks = set(kept)',
  "    kdf = df[df['code'].isin(ks)]",
  "    rdf = df[~df['code'].isin(ks)]",
  "    log.error('U5 REASON date=%s removed_withFund=%d roeFail=%d roaFail=%d bothFail=%d roeNaN=%d roaNaN=%d' % (",
  "        date, len(rdf), int((rdf['roe'] <= g.min_roe).sum()), int((rdf['roa'] <= g.min_roa).sum()),",
  "        int(((rdf['roe'] <= g.min_roe) & (rdf['roa'] <= g.min_roa)).sum()),",
  "        int(rdf['roe'].isnull().sum()), int(rdf['roa'].isnull().sum())))",
  "    log.error('U5 DIST date=%s ALL roe %s' % (date, _u5_q(df['roe'])))",
  "    log.error('U5 DIST date=%s ALL roa %s' % (date, _u5_q(df['roa'])))",
  "    log.error('U5 DIST date=%s KEPT roe %s' % (date, _u5_q(kdf['roe'])))",
  "    log.error('U5 DIST date=%s KEPT roa %s' % (date, _u5_q(kdf['roa'])))",
  "    log.error('U5 DIST date=%s REMOVED roe %s' % (date, _u5_q(rdf['roe'])))",
  "    log.error('U5 DIST date=%s REMOVED roa %s' % (date, _u5_q(rdf['roa'])))",
  '    pick = list(kept[:g.stock_num])',
  "    pdf = df[df['code'].isin(pick)]",
  "    log.error('U5 PICK date=%s %s' % (date, _u5_fmt(pdf)))",
  "    log.error('U5 DROP date=%s %s' % (date, _u5_fmt(rdf.head(10))))",
  '',
].join('\n');

// assert: deleting exactly the inserted text recovers the base byte-for-byte
if (v.replace(INS1, '').replace(INS2, '') !== raw) throw new Error('probe changed more than its own lines');
const out = path.join(__dirname, 'variants/u-5-roe-probe.py');
fs.writeFileSync(out, v + HELPER + OVERRIDE);
console.log('built', path.relative(ROOT, out));
