// Builds liq-1 (K=1, + LIQAUCT readout) / liq-2 (K=10) from study/多策略分仓组合/baseline.py
// with asserted edits only (each anchor must match exactly once, else throw):
//   (0) helper liq_ok() + liq_flush() inserted before class BaseStrategy
//   (1) BaseStrategy.order_target_value_ buy branch: floor check before order_target_value  -> covers 腿A / ETF2 / ETF3
//   (2) StrategyB.buy(): floor check before order_value, batch log after the loop             -> 腿B
//   (3) liq-1 only: StrategyB.filter_stocks_by_b_s keeps auction money; buy() logs LIQAUCT (read-only)
// Floor = K * order_value / 0.05 against PREVIOUS-day money (attribute_history 1d, intraday => ends previous_date).
// Sells are never floored. Exceptions log LIQFLOOR ERROR and let the order through.
//
// Usage: node -e "require('./study/多策略分仓组合/build-liq.js').build('liq-1')"
const fs = require('fs');
const path = require('path');
const DIR = __dirname;
const VARIANTS = { 'liq-1': { K: 1, auct: true }, 'liq-2': { K: 10, auct: false } };

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error('expected 1 match, got ' + n + ': ' + from.slice(0, 80));
  return s.replace(from, to);
}

function helper(K) {
  return `# ---------------- liquidity floor (realizability measurement, epoch 9) ----------------
# per-order floor: previous-day money >= LIQ_K * order value / 0.05 (order_volume_ratio pinned 0.05)
LIQ_K = ${K}

def liq_ok(leg, s, value, batch=None):
    """True if previous-day money clears LIQ_K*value/0.05. batch=None => log a one-order batch now."""
    try:
        h = attribute_history(s, 1, '1d', ['money'])
        m = float(h['money'].iloc[-1])
        floor = LIQ_K * float(value) / 0.05
        ok = bool(m >= floor)
        rec = (s, m, floor, ok)
    except Exception as e:
        log.error('LIQFLOOR ERROR %s %s %s exc=%s' % (str(_LIQ_CTX[0].current_dt.date()) if _LIQ_CTX else '?', leg, s, str(e)))
        return True
    if batch is None:
        liq_flush(leg, [rec])
    else:
        batch.append(rec)
    return ok


def liq_flush(leg, batch):
    if not batch:
        return
    try:
        import datetime as _d
        excl = [r[0] for r in batch if not r[3]]
        info = ' '.join('%s=%.0f/%.0f' % (r[0], r[1], r[2]) for r in batch)
        log.error('LIQFLOOR %s %s in=%d out=%d excluded=%s %s' % (str(_LIQ_CTX[0].current_dt.date()) if _LIQ_CTX else '?',
                  leg.replace(' ', '_'), len(batch), len(batch) - len(excl), ','.join(excl) if excl else '-', info))
    except Exception as e:
        log.error('LIQFLOOR ERROR flush %s exc=%s' % (leg, str(e)))

_LIQ_CTX = []


`;
}

function build(id) {
  if (id === 'all') return Object.keys(VARIANTS).forEach(build);
  const v = VARIANTS[id];
  if (!v) throw new Error('unknown variant ' + id);
  const base = fs.readFileSync(path.join(DIR, 'baseline.py'), 'utf8');
  let s = base;
  // (0) helper
  s = edit(s, `class BaseStrategy:\n    def __init__(self, name, weight):`,
    helper(v.K) + `class BaseStrategy:\n    def __init__(self, name, weight):`);
  // context capture for the date stamp (initialize of the base class)
  s = edit(s, `        self.context = context\n        # 使用策略自身权重计算初始资金`,
    `        self.context = context\n        if not _LIQ_CTX: _LIQ_CTX.append(context)  # liq: date stamp only\n        # 使用策略自身权重计算初始资金`);
  // (1) base buy branch
  s = edit(s, `            # 执行买入订单并更新虚拟账户\n            order = order_target_value(security, value)`,
    `            if not liq_ok(self.name, security, value):  # liq: floor on buys only\n                return None\n            # 执行买入订单并更新虚拟账户\n            order = order_target_value(security, value)`);
  // (2) leg B buy loop
  s = edit(s, `            cash_per_stock = strategy_cash / num\n            current_data = get_current_data()\n            for stock in target:`,
    `            cash_per_stock = strategy_cash / num\n            current_data = get_current_data()\n            _lb = []  # liq batch\n            for stock in target:`);
  const auctLine = v.auct
    ? `\n                _am = getattr(self, '_liq_auct', {}).get(stock)\n                log.error('LIQAUCT %s %s auctmoney=%s posvalue=%.2f' % (self.context.current_dt.date(), stock, ('%.0f' % _am) if _am is not None else 'NA', shares * price))`
    : '';
  s = edit(s, `                if shares <= 0:\n                    continue\n                    \n                order_value(stock, shares * price)`,
    `                if shares <= 0:\n                    continue\n                    ${auctLine}\n                if not liq_ok(self.name, stock, shares * price, _lb):  # liq: floor\n                    continue\n                order_value(stock, shares * price)`);
  s = edit(s, `                log.debug(f'[{self.name}] 虚拟账户买入 {stock} {shares}股，花费 {shares * price:.2f}，剩余现金 {self.cash:.2f}')\n\n    def is_avoid_period(self):`,
    `                log.debug(f'[{self.name}] 虚拟账户买入 {stock} {shares}股，花费 {shares * price:.2f}，剩余现金 {self.cash:.2f}')\n            liq_flush(self.name, _lb)\n\n    def is_avoid_period(self):`);
  // (3) auction money readout (liq-1)
  if (v.auct) {
    s = edit(s, `        stocks = df[df['buymoney'] > df['sellmoney']].code.tolist()`,
      `        try:\n            self._liq_auct = dict(zip(df['code'], df['money']))  # LIQAUCT readout only\n        except Exception as e:\n            log.error('LIQAUCT ERROR exc=%s' % str(e))\n        stocks = df[df['buymoney'] > df['sellmoney']].code.tolist()`);
  }
  // assertion: every removed baseline line is gone only where intended -> baseline lines all still present in order
  const bl = base.split('\n'), nl = s.split('\n');
  let j = 0;
  for (const line of bl) { while (j < nl.length && nl[j] !== line) j++; if (j >= nl.length) throw new Error('baseline line lost: ' + line); j++; }
  const out = path.join(DIR, 'variants', id + '.py');
  fs.writeFileSync(out, `# ${id} variant of study/多策略分仓组合/baseline.py — liquidity floor K=${v.K}${v.auct ? ' + LIQAUCT readout' : ''}; additions only\n` + s);
  console.log('built', out, 'added lines', nl.length - bl.length);
}
module.exports = { build };
