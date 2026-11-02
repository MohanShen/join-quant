// liq-1: realizability at the book's own feasibility floor, on the REFERENCE BOOK variants/dxpit.py.
//   (1) ONE asserted behavioural edit in main(), right after controlReport:
//         df=filter_liquidity_floor(context, df)  # liq-1: ONLY behavioural change vs dxpit
//       Keeps qualifier rows whose TRAILING-20-BAR MEDIAN daily `money` (end_date=previous_date, so the
//       bar being traded today is never consulted) is >= LIQ_FLOOR = 4e6. Order-preserving, reset_index.
//   (2) observation in the same helper, BEFORE filtering: LIQMIN (every qualifier's median) +
//       LIQFLOOR in/out/slots. On exception: LIQFLOOR ERROR and df returned unchanged (ERROR must be 0).
//   (3) dxpit's DXPRE/DXPOST + after_trading_end P&L logger DROPPED (it crashed every day; pure
//       observation, nothing fed an order). DXMON kept.
// FLOOR DERIVATION: capital 1,000,000 / g.stock_num 5 = 200,000 per slot; / order_volume_ratio 0.05
// = 4e6 CNY/day (1x fill feasibility). Pattern: study/银行股轮动/build-liq.js, study/大小盘轮动/build-liq.js.
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const ref = fs.readFileSync(path.join(__dirname, 'variants', 'dxpit.py'), 'utf8');
if (!ref.endsWith(OVERRIDE)) throw new Error('dxpit.py does not end with the live OVERRIDE');
const raw = ref.slice(0, ref.length - OVERRIDE.length);
let body = raw;

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// ---- strip dxpit's crashing observation layer (keep _dxp_mon / DXMON) ----
const H0 = '\n\n# ===== u-e9-dxpit observation helpers (nothing below feeds an order) =====\n';
const H1 = '# ===== end u-e9-dxpit observation helpers =====\n';
const i0 = body.indexOf(H0), i1 = body.indexOf(H1);
if (i0 < 0 || i1 < 0 || body.split(H0).length !== 2) throw new Error('dxpit helper block not found exactly once');
const block = body.slice(i0, i1 + H1.length);
const mStart = block.indexOf('def _dxp_mon(');
const mEnd = block.indexOf('def _dxp_pos(');
if (mStart < 0 || mEnd < 0) throw new Error('_dxp_mon not found');
const MON = block.slice(mStart, mEnd);
body = body.slice(0, i0) + body.slice(i1 + H1.length);
body = edit(body, "    _dxp_pos(context, 'DXPRE')  # u-e9-dxpit obs\n", '');
body = edit(body, "    _dxp_pos(context, 'DXPOST')  # u-e9-dxpit obs\n", '');
if (/_dxp_pos|after_trading_end|DXPNL/.test(body)) throw new Error('dxpit obs residue');

// ---- (1) the behavioural edit ----
const CR = "    df=controlReport(df, context.current_dt.date())  # u-e9-dxpit: pass d0\n";
body = edit(body, CR, CR + "    df=filter_liquidity_floor(context, df)  # liq-1: ONLY behavioural change vs dxpit\n");

const helper = `

# ===== liq-1 (understand, ${new Date().toISOString().slice(0, 10)}): liquidity floor + kept DXMON =====
# Floor derivation: capital 1,000,000 CNY / g.stock_num (=5) = 200,000 CNY per slot. Epoch 4 pins
# order_volume_ratio = 0.05, so filling one slot inside ONE daily bar needs traded value
# >= 200,000 / 0.05 = 4,000,000 CNY/day (1x fill feasibility).
LIQ_FLOOR = 4e6

def filter_liquidity_floor(context, df):
    """Keep qualifier rows whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: one spike day must not admit a normally-illiquid name.
    end_date=context.previous_date: the bar being traded today is never consulted.
    """
    n_in = df.shape[0]
    if n_in == 0:
        log.info('LIQMIN date=%s n=0' % str(context.previous_date))
        log.info('LIQFLOOR floor=%.0f date=%s in=0 out=0 removedFrac=NA slots=0' % (LIQ_FLOOR, str(context.previous_date)))
        return df
    try:
        codes = list(df['code'])
        px = get_price(codes, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = px.groupby('code')['money'].median()
        log.info('LIQMIN date=%s n=%d ' % (str(context.previous_date), len(codes)) +
                 ' '.join('%s=%.0f' % (s, med[s] if s in med.index else -1) for s in codes))
        mask = [(s in med.index) and (med[s] >= LIQ_FLOOR) for s in codes]
        out = df[mask].reset_index(drop=True)
    except Exception as e:
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return df
    n_out = out.shape[0]
    log.info('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, n_out,
        1.0 - float(n_out) / float(n_in), min(g.stock_num, n_out)))
    return out

${MON}# ===== end liq-1 =====
`;
body = body + helper;

// ---- assertions ----
for (const k of ['order_target_value', 'order_value', 'order(', 'run_monthly', 'run_daily', 'run_weekly']) {
  if (body.split(k).length !== raw.split(k).length) throw new Error('order/schedule calls changed: ' + k);
}
if (!body.includes("run_monthly(main,1,time='9:30')")) throw new Error('schedule changed');
if (!body.includes('_dxp_mon(context, df)  # u-e9-dxpit obs')) throw new Error('DXMON call lost');
if (body.split('def _dxp_mon(').length !== 2) throw new Error('_dxp_mon not defined exactly once');
if (/get_price\([^)]*end_date=context\.current_dt/.test(body)) throw new Error('same-day bar access');

const out = path.join(__dirname, 'variants', 'liq-1.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
