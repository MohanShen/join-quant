// q-e9-beta510880 — buy-and-hold 510880.XSHG (红利ETF): full investment on day 1, hold to end.
// Frozen pins come from the live OVERRIDE (require, never hand-copied); the strategy body also
// sets them in initialize (template style) and the OVERRIDE re-applies them after initialize.
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const body = `# q-e9-beta510880 — 红利质量 understand probe: buy-and-hold 510880.XSHG, TRAIN.
# Question: how much of d0a149b1's 2024 result is dividend-style beta an ETF sells directly.
# Built by study/红利质量/build-q-e9-beta510880.js. Pins: OVERRIDE from utils/strategy-normalize.js.

def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option('order_volume_ratio', 0.05)
    log.set_level('order', 'error')
    set_benchmark('000300.XSHG')
    g.etf = '510880.XSHG'
    run_daily(buy_hold, '09:31')


def buy_hold(context):
    # Top up while idle cash remains (order_volume_ratio may cap the day-1 fill).
    cash = context.portfolio.available_cash
    if cash > 0.01 * context.portfolio.total_value:
        o = order_value(g.etf, cash)
        log.info('BAH buy cash=%.0f filled=%s' % (cash, (o.filled if o is not None else None)))
`;
const out = path.join(__dirname, 'variants/q-e9-beta510880.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
