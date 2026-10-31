// Builds u-1 / u-3 / liq-1 from study/资产配置/baseline.py, one asserted edit each
// (u-1 adds one log-only daily handler for the cash-fraction readout).
const fs = require('fs');
const path = require('path');
const D = __dirname + '/';
const base = fs.readFileSync(D + 'baseline.py', 'utf8');
function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error('expected 1 match, got ' + n + ': ' + from);
  return s.replace(from, to);
}
const W = `    g.etf_weights = {
        '515450.XSHG': 0.2,   # 红利低波ETF
        '513630.XSHG': 0.2,   # 香港红利低波ETF
        '513100.XSHG': 0.20,   # 纳指ETF
        '518880.XSHG': 0.20,   # 黄金ETF
        '513650.XSHG': 0.20,  # 标普ETF
    }`;

// u-1
let u1 = edit(base, W, `    # u-1: ONLY trading change vs baseline.py — single asset X=518880 (u-2: best 2024 single sharpe 1.79)
    g.etf_weights = {'518880.XSHG': 1.0}`);
u1 = edit(u1, `    run_daily(rebalance, time='09:40')`, `    run_daily(rebalance, time='09:40')
    run_daily(u1_cashfrac, time='14:59')  # log-only`);
u1 = edit(u1, `def before_market_open(context):`, `def u1_cashfrac(context):
    # log-only: invested fraction = positions value / total value
    _tv = context.portfolio.total_value
    _pv = context.portfolio.positions_value
    log.error('CASHFRAC %s pv=%.2f tv=%.2f cash=%.2f frac_inv=%.6f' % (context.current_dt.date(), _pv, _tv, context.portfolio.available_cash, _pv / _tv if _tv else 0))


def before_market_open(context):`);
fs.writeFileSync(D + 'variants/u-1-single-gold.py', '# u-1 variant of study/资产配置/baseline.py\n' + u1);

// u-3
const u3 = edit(base, `    g.rebalance_interval = 10`, `    g.rebalance_interval = 100000  # u-3: ONLY change — buy on day 1 then hold`);
fs.writeFileSync(D + 'variants/u-3-buyhold.py', '# u-3 variant of study/资产配置/baseline.py\n' + u3);

// liq-1
let l = edit(base, `    target_values = {}
    for etf, weight in g.etf_weights.items():`, `    weights = liq_floor_weights(context)  # liq-1: ONLY change vs baseline.py
    target_values = {}
    for etf, weight in weights.items():`);
l = edit(l, `        if stock not in g.etf_weights:`, `        if stock not in weights:`);
l = edit(l, `def order_target_by_lot(context, security, target_value, current_data):`, `# ---------------- liquidity floor (realizability measurement, epoch 9) ----------------
# capital 1000000 / 5 sleeves = 200000 per sleeve; order_volume_ratio 0.05 pinned (epoch 4)
# => one sleeve fills in a single daily bar only if that bar's money >= 200000/0.05 = 4000000.
LIQ_FLOOR = 4000000

def liq_floor_weights(context):
    """20-bar MEAN daily money through previous_date (attribute_history at 09:40 never
    includes today's bar). Names below LIQ_FLOOR are excluded; their weight is
    redistributed equally among the rest. Loud on failure (falls back to full weights)."""
    w = dict(g.etf_weights)
    info = []
    excluded = []
    try:
        for s in list(w.keys()):
            h = attribute_history(s, 20, '1d', ['money'])
            m = float(h['money'].mean())
            info.append('%s=%.0f' % (s, m))
            if not (m >= LIQ_FLOOR):
                excluded.append(s)
    except Exception as e:
        log.error('LIQFLOOR ERROR %s exc=%s' % (context.current_dt.date(), str(e)))
        return dict(g.etf_weights)
    n_in = len(w)
    keep = [s for s in w if s not in excluded]
    if excluded and keep:
        extra = sum(w[s] for s in excluded) / float(len(keep))
        w = dict((s, w[s] + extra) for s in keep)
    log.error('LIQFLOOR %s in=%d out=%d excluded=%s %s' % (context.current_dt.date(), n_in, len(w),
              ','.join(excluded) if excluded else '-', ' '.join(info)))
    return w


def order_target_by_lot(context, security, target_value, current_data):`);
fs.writeFileSync(D + 'variants/liq-1-floor.py', '# liq-1 variant of study/资产配置/baseline.py\n' + l);
console.log('built 3');
