// liq-1 (realizability): liquidity feasibility floor at the book's OWN size, after
// study/大小盘轮动/build-liq.js. Built from study/破净价值多因子/baseline.py with ONE asserted insertion.
//
// FLOOR DERIVATION: capital 1,000,000 CNY; the book holds up to 6 names (6 rankers × g.top_n=1,
// deduplicated), so a full position is ~166,667 CNY. order_volume_ratio = 0.05 (pinned) ⇒ filling one
// position inside one daily bar needs >= 166,667 / 0.05 ≈ 3.33e6 CNY/day traded value.
// Liquidity = TRAILING-20-BAR MEDIAN of daily `money` on context.previous_date (same lookback as
// build-liq.js). Applied to the 破净 candidate list (output of the fundamentals screen) BEFORE the
// six rankers, so every ranker sees only fillable names.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
// CLI (liq-2+): --floor <py expr> --gloss <comment> --out <file>. Defaults reproduce liq-1
// byte-identically; ONLY the LIQ_FLOOR literal + its comment line move.
const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const FLOOR_EXPR = arg('--floor', '1e6 / 6 / 0.05');
const GLOSS = arg('--gloss', 'capital 1,000,000 / up to 6 names / order_volume_ratio 0.05 => 1e6/6/0.05 = 3.33e6 CNY/day.');
const FNAME = arg('--out', 'liq-1_floor-3.33e6.py');
const base = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');

const ANCHOR = '    stock_list = get_fundamentals(q, date=previous_date).code.tolist()\n';
const n = base.split(ANCHOR).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 anchor match, got ${n}`);
const INSERT = '    stock_list = filter_liquidity_floor(context, stock_list)  # liq-1: ONLY change vs baseline\n';

const HELPER = `

# ----------------- liquidity floor (realizability liq-1) -----------------
# ${GLOSS}
LIQ_FLOOR = ${FLOOR_EXPR}
LIQ_SLOTS = 6

def filter_liquidity_floor(context, stock_list):
    n_in = len(stock_list)
    if n_in == 0:
        log.error('LIQFLOOR floor=%.0f date=%s in=0 out=0 removedFrac=NA slots=0' % (LIQ_FLOOR, str(context.previous_date)))
        return []
    try:
        df = get_price(stock_list, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [s for s in stock_list if (s in med.index) and (med[s] >= LIQ_FLOOR)]
    except Exception as e:
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return stock_list
    removed = [s for s in stock_list if s not in keep]
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d removed=%s' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(LIQ_SLOTS, len(keep)), ','.join(removed)))
    return keep
`;

// insert the helper before the OVERRIDE block so the OVERRIDE stays the file's tail
const OV = '# ===== AUTORESEARCH NORMALIZATION OVERRIDE';
if (base.split(OV).length - 1 !== 1) throw new Error('override marker count');
let body = base.replace(ANCHOR, ANCHOR + INSERT);
const k = body.indexOf(OV);
body = body.slice(0, k) + HELPER.trimStart() + '\n\n' + body.slice(k);

// assert: removing exactly the insertion + helper gives back the baseline
const restored = body.replace(INSERT, '').replace(HELPER.trimStart() + '\n\n', '');
if (restored !== base) throw new Error('variant is not baseline + one insertion + helper');

const out = path.join(__dirname, 'variants', FNAME);
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, body);
console.log('built', path.relative(ROOT, out));
