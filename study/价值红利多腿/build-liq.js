// q-e9-liq-1 (realizability): liquidity feasibility floor at the book's OWN largest order, after
// study/破净价值多因子/build-liq.js. Built from study/价值红利多腿/variants/q-e9-orphan-fix.py (the
// reference after q-e9-orphan-fix) with one helper + exactly FOUR asserted call lines, one per sleeve,
// each on that sleeve's CANDIDATE list BEFORE its top-N cut (an after-cut filter would leave empty
// slots and measure something else).
//
// FLOOR DERIVATION: capital 1,000,000 × 25% per sleeve; s1/s3/s4 hold 1 name ⇒ largest single order
// ≈ ¥250k; order_volume_ratio 0.05 (pinned) ⇒ 250,000 / 0.05 = 5e6 CNY/day, applied uniformly.
// Liquidity = trailing-20-bar MEDIAN daily `money` ending context.previous_date (precedent lookback).
// 511010.XSHG (s3 fallback ETF) is exempt and logged as such; existing holdings are NOT exempt.
//
// CLI (liq-2): --floor <py expr> --gloss <comment> --out <file>. Defaults reproduce liq-1; ONLY the
// LIQ_FLOOR literal + its gloss line move.
// Usage: node study/价值红利多腿/build-liq.js [--floor "1e6 * 0.25 * 5 / 0.05" --out liq-2_floor-2.5e7.py]
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const FLOOR_EXPR = arg('--floor', '1e6 * 0.25 / 0.05');
const GLOSS = arg('--gloss', 'capital 1,000,000 x 25% per sleeve, 1-name sleeves => largest order ~250k / order_volume_ratio 0.05 => 5e6 CNY/day.');
const FNAME = arg('--out', 'liq-1_floor-5e6.py');
const base = fs.readFileSync(path.join(__dirname, 'variants', 'q-e9-orphan-fix.py'), 'utf8');

// [anchor line, inserted line (goes immediately BEFORE the anchor)]
const CALLS = [
  ['    final_list = list(df[\'code\'])[:g.s1_stock_num]\n',
   '    _liq = filter_liquidity_floor(context, list(df[\'code\']), \'s1\'); df = df[df[\'code\'].isin(_liq)]  # liq-1\n'],
  ['    final_list = list(df[\'code\'])[:g.s2_stock_num]\n',
   '    _liq = filter_liquidity_floor(context, list(df[\'code\']), \'s2\'); df = df[df[\'code\'].isin(_liq)]  # liq-1\n'],
  ['    g.s3_check_out_lists = check_out[:g.s3_stock_num]\n',
   '    check_out = filter_liquidity_floor(context, check_out, \'s3\')  # liq-1\n'],
  ['    return list(sdf.head(num).index)\n',
   '    _liq = filter_liquidity_floor(context, list(sdf.index), \'s4\'); sdf = sdf[sdf.index.isin(_liq)]  # liq-1\n'],
];

const HELPER = `
# ----------------- liquidity floor (realizability liq-1) -----------------
# ${GLOSS}
LIQ_FLOOR = ${FLOOR_EXPR}
LIQ_EXEMPT = ['511010.XSHG']

def filter_liquidity_floor(context, stock_list, sid):
    stock_list = list(stock_list)
    n_in = len(stock_list)
    d = str(context.previous_date)
    if n_in == 0:
        log.info('LIQFLOOR %s floor=%.0f date=%s in=0 out=0 removed=' % (sid, LIQ_FLOOR, d))
        return []
    exempt = [s for s in stock_list if s in LIQ_EXEMPT]
    test = [s for s in stock_list if s not in LIQ_EXEMPT]
    try:
        med = {}
        if test:
            df = get_price(test, count=20, end_date=context.previous_date,
                           fields=['money'], frequency='1d', panel=False)
            med = df.groupby('code')['money'].median().to_dict()
        keep = [s for s in stock_list if (s in LIQ_EXEMPT) or (s in med and med[s] >= LIQ_FLOOR)]
    except Exception as e:
        log.info('LIQFLOOR %s ERROR floor=%.0f date=%s in=%d exc=%s' % (sid, LIQ_FLOOR, d, n_in, str(e)))
        return stock_list
    removed = [s for s in stock_list if s not in keep]
    log.info('LIQFLOOR %s floor=%.0f date=%s in=%d out=%d exempt=%s removed=%s' % (
        sid, LIQ_FLOOR, d, n_in, len(keep), ','.join(exempt),
        ','.join(['%s:%.0f' % (s, med.get(s, -1)) for s in removed])))
    return keep
`;

let body = base;
for (const [anchor, ins] of CALLS) {
  const n = body.split(anchor).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 anchor match, got ${n}: ${anchor.trim()}`);
  body = body.replace(anchor, ins + anchor);
}
const OV = '# ===== AUTORESEARCH NORMALIZATION OVERRIDE';
if (body.split(OV).length - 1 !== 1) throw new Error('override marker count');
const k = body.indexOf(OV);
body = body.slice(0, k) + HELPER.trimStart() + '\n\n' + body.slice(k);

// assert: variant = base + helper + exactly the 4 call lines
let restored = body.replace(HELPER.trimStart() + '\n\n', '');
for (const [, ins] of CALLS) restored = restored.replace(ins, '');
if (restored !== base) throw new Error('variant is not base + helper + 4 call lines');
const added = body.split('\n').length - base.split('\n').length;
const helperLines = (HELPER.trimStart() + '\n\n').split('\n').length - 1;
if (added !== helperLines + CALLS.length) throw new Error(`line delta ${added} != ${helperLines}+${CALLS.length}`);
if ((body.match(/[=;] *filter_liquidity_floor\(context,/g) || []).length !== CALLS.length) throw new Error('call count');

const out = path.join(__dirname, 'variants', FNAME);
fs.writeFileSync(out, body);
console.log('built', path.relative(ROOT, out), `(+${added} lines: helper ${helperLines} + ${CALLS.length} calls, floor ${FLOOR_EXPR})`);
