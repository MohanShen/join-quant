// liq-cap: realizability test for 银行股轮动. Base 2a323522 + py2to3 + OVERRIDE (== baseline.py) plus:
//   (1) ONE asserted behavioural edit: filter_liquidity_floor applied to eligible_stocks right after
//       the L157 score sort (order-preserving), LIQ_FLOOR = 8e7.
//   (2) observation only: one LIQMIN log line per rebalance (top of rebalance, before any early
//       return) with every g.stocks name's 20-bar MEDIAN money as of previous_date. Read-only.
// filter_liquidity_floor + LIQFLOOR format copied from study/大小盘轮动/build-liq.js. The ONLY
// deviation: `slots` uses g.max_holdings (=3) because this book has no g.stock_num — referencing it
// would raise AttributeError, the except would swallow it and silently reproduce the base.
//
// FLOOR DERIVATION: capital 1,000,000 x 40% single-name cap (max_single = total_value*0.4) = 400,000;
// / order_volume_ratio 0.05 = 8e6 CNY/day = 1x fill feasibility. 8e7 = 10x.
// DECISION RULE (declared in queue.json before the run): R=3 iff max|Δcum| = 0 vs base AND every
// name's min LIQMIN over 2024 >= 8e7; R=2 if any LIQFLOOR out<in but sharpe >= 1.0.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-26_自己搭建的一个10年230_收益率的银行股策略-2a323522.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// (1) the behavioural edit
const SORT = '    eligible_stocks.sort(key=lambda x: scores.get(x, 0), reverse=True)\n';
let body = edit(raw, SORT, SORT +
  '    eligible_stocks = filter_liquidity_floor(context, eligible_stocks)  # liq-cap: ONLY behavioural change vs baseline\n');

// (2) observation line, first statement of rebalance()
const HEAD = '\ndef rebalance(context):\n';
body = edit(body, HEAD, HEAD + '    log_liq_min(context)  # liq-cap: observation only\n');

const helper = `

# ----------------- liquidity floor (understand experiment liq-cap, ${new Date().toISOString().slice(0, 10)}) -----------------
# Floor derivation: capital 1,000,000 CNY x 40% single-name cap = 400,000 CNY per full position.
# Epoch 4 pins order_volume_ratio = 0.05, so filling it inside one daily bar needs traded value
# >= 400,000 / 0.05 = 8,000,000 CNY (1x feasibility). LIQ_FLOOR = 8e7 is 10x that.
LIQ_FLOOR = 8e7

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: a single spike day must not admit a name that is normally illiquid.
    Evaluated on context.previous_date, so the bar being traded today is never consulted.
    """
    n_in = len(stock_list)
    if n_in == 0:
        log.error('LIQFLOOR floor=%.0f in=0 out=0 removedFrac=NA slots=0' % LIQ_FLOOR)
        return []
    try:
        df = get_price(stock_list, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [s for s in stock_list if (s in med.index) and (med[s] >= LIQ_FLOOR)]
    except Exception as e:
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return stock_list
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(g.max_holdings, len(keep))))
    return keep

def log_liq_min(context):
    try:
        df = get_price(g.stocks, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        log.error('LIQMIN date=%s ' % str(context.previous_date) +
                  ' '.join('%s=%.0f' % (s, med[s] if s in med.index else -1) for s in g.stocks))
    except Exception as e:
        log.error('LIQMIN ERROR exc=%s' % str(e))
`;

body = body + helper;
if ((body.match(/order_target_value/g) || []).length !== (raw.match(/order_target_value/g) || []).length) throw new Error('order calls changed');
if (!body.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');
if (/g\.stock_num/.test(body)) throw new Error('g.stock_num leaked in');

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, 'liq-cap.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
