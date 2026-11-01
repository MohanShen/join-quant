// liq-1: realizability test for 向导式低波价值. Base = baseline.py (py2to3(8b9cb8e2) + OVERRIDE) plus:
//   (1) ONE asserted behavioural edit: filter_liquidity_floor applied to buy_lists in trade() right
//       after the ATR entry filter (L196), order-preserving, LIQ_FLOOR = 4e7.
//   (2) observation only: one LIQMIN log line per trading day (after_close counter) with every HELD
//       name's 20-bar MEDIAN money as of previous_date. Read-only.
// filter_liquidity_floor + LIQFLOOR format copied from study/银行股轮动/build-liq.js (itself from
// study/大小盘轮动/build-liq.js). The ONLY deviation: `slots` uses g.max_hold_stocknum (=5) because
// this book has no g.stock_num — referencing it would raise AttributeError and the except would
// silently reproduce the base.
//
// FLOOR DERIVATION: capital 1,000,000 / 5 names = 200,000 per position; / order_volume_ratio 0.05 =
// 4e6 CNY/day = 1x feasibility. 4e7 = 10x.
// DECISION RULE (queue.json, declared before the run): R=3 iff max|Δcum| = 0 vs base AND every held
// name's min LIQMIN over 2024 >= 4e7; R=2 if any LIQFLOOR out<in but sharpe >= 1.0; if it bites and
// sharpe < 1.0, re-run at 1x (4e6) before scoring.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const raw = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// (1) the behavioural edit
const ATR = '        buy_lists = [security for security in buy_lists if ATR_judge_xiaoyu(security, 0.15, 14)]\n';
let body = edit(raw, ATR, ATR +
  '        buy_lists = filter_liquidity_floor(context, buy_lists)  # liq-1: ONLY behavioural change vs baseline\n');

// (2) observation line, first statement of the after_close counter
const HEAD = '\ndef selled_security_list_count(context):\n';
body = edit(body, HEAD, HEAD + '    log_liq_min(context)  # liq-1: observation only\n');

const helper = `

# ----------------- liquidity floor (understand experiment liq-1, ${new Date().toISOString().slice(0, 10)}) -----------------
# Floor derivation: capital 1,000,000 CNY / 5 names = 200,000 CNY per full position.
# Epoch 4 pins order_volume_ratio = 0.05, so filling it inside one daily bar needs traded value
# >= 200,000 / 0.05 = 4,000,000 CNY (1x feasibility). LIQ_FLOOR = 4e7 is 10x that.
LIQ_FLOOR = 4e7

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: a single spike day must not admit a name that is normally illiquid.
    Evaluated on context.previous_date, so the bar being traded today is never consulted.
    """
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
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(g.max_hold_stocknum, len(keep))))
    return keep

def log_liq_min(context):
    try:
        held = list(context.portfolio.positions.keys())
        if len(held) == 0:
            log.error('LIQMIN date=%s none' % str(context.previous_date))
            return
        df = get_price(held, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        log.error('LIQMIN date=%s ' % str(context.previous_date) +
                  ' '.join('%s=%.0f' % (s, med[s] if s in med.index else -1) for s in held))
    except Exception as e:
        log.error('LIQMIN ERROR exc=%s' % str(e))
`;

// insert the helper BEFORE the OVERRIDE block so it sits in strategy scope (the OVERRIDE wraps initialize)
const MARK = '\ndef set_slippage(*a, **k):\n';
body = edit(body, MARK, helper + MARK);
const cnt = (s, re) => (s.match(re) || []).length;
if (cnt(body, /\border\(/g) !== cnt(raw, /\border\(/g)) throw new Error('order calls changed');
if (cnt(body, /order_target_value/g) !== cnt(raw, /order_target_value/g)) throw new Error('order calls changed');
if (/g\.stock_num/.test(body)) throw new Error('g.stock_num leaked in');
if (!body.includes("run_daily(trade, 'open')")) throw new Error('schedule changed');
const header = `# liq-1 variant — family: 向导式低波价值 — base study/向导式低波价值/baseline.py + LIQ_FLOOR 4e7 (10x)\n`;
const out = path.join(__dirname, 'variants', 'liq-1.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out));
