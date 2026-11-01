// pool-ew-harness.js — the POOL-EW HARNESS shared by u-7 / u-3 / u-4 / u-5 (queue.json, u-7 design).
// Every one of those four builds MUST go through applyHarness(), so H1/H2/H3 and the logging are
// byte-identical across them; each dependant then adds exactly ONE asserted edit of its own.
//
//   H1  exit off: the sell filter (L289, yuan ATR_judge_dayu 0.35) becomes  sell_lists = []
//   H2  g.max_hold_stocknum 5 -> 1000 (L38)
//   H3  buy(): explicit equal cash split, computed ONCE before the order loop:
//         _ew_cash = context.portfolio.available_cash / len(buy_lists)
//       replacing the hidden wizard order_style(...) result[stock].
//   LOG EWDEPLOY date n_buy cash_before cash_after total_value (every buy() call that reaches the
//       split, incl. n_buy=0), POOL0 code=<c> for every day-1 buy, EWFILL per order (price/filled),
//       EWFINAL per held name on the final trading day (logging only).
//
// Usage:  const { loadBase, applyHarness, edit } = require('./pool-ew-harness');
//         let src = applyHarness(loadBase());   // then one asserted edit(src, from, to)
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');

function edit(src, from, to) {
  const n = src.split(from).length - 1;
  if (n !== 1) throw new Error(`anchor matched ${n}x: ${JSON.stringify(from.slice(0, 80))}`);
  return src.replace(from, () => to);
}

function loadBase() {
  const src = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');
  // The cost block must be the live module's, never a stale copy.
  if (!src.includes(OVERRIDE)) throw new Error('baseline.py OVERRIDE != utils/strategy-normalize OVERRIDE; rebuild baseline');
  return src;
}

function applyHarness(src) {
  // H2
  src = edit(src, '    g.max_hold_stocknum = 5\n',
    '    g.max_hold_stocknum = 1000  # HARNESS H2 (was 5)\n');
  // H1
  src = edit(src, '    sell_lists = [security for security in sell_lists if ATR_judge_dayu(security, 0.35, 14)]\n',
    '    sell_lists = []  # HARNESS H1 exit off (was: yuan dayu 0.35 filter)\n');
  // H3 + EWDEPLOY / POOL0
  src = edit(src,
    '    # 买入股票\n' +
    '    if len(buy_lists)>0:\n' +
    '        # 分配资金\n' +
    '        result = order_style(context,buy_lists,g.max_hold_stocknum, g.order_style_str, g.order_style_value)\n' +
    '        for stock in buy_lists:\n' +
    '            if len(context.portfolio.positions) < g.max_hold_stocknum:\n' +
    '                # 获取资金\n' +
    '                Cash = result[stock]\n',
    '    # 买入股票\n' +
    '    _ew_d = context.current_dt.strftime(\'%Y-%m-%d\')  # HARNESS log\n' +
    '    _ew_before = context.portfolio.available_cash  # HARNESS log\n' +
    '    _ew_first = (_EW[\'day1\'] is None)  # HARNESS log\n' +
    '    if _ew_first:  # HARNESS log\n' +
    '        _EW[\'day1\'] = _ew_d  # HARNESS log\n' +
    '        for _c in buy_lists:  # HARNESS log\n' +
    '            log.info(\'POOL0 date=%s code=%s\' % (_ew_d, _c))  # HARNESS log\n' +
    '    if len(buy_lists)>0:\n' +
    '        # 分配资金\n' +
    '        _ew_cash = context.portfolio.available_cash / len(buy_lists)  # HARNESS H3 equal cash split (was order_style result[stock])\n' +
    '        for stock in buy_lists:\n' +
    '            if len(context.portfolio.positions) < g.max_hold_stocknum:\n' +
    '                # 获取资金\n' +
    '                Cash = _ew_cash  # HARNESS H3\n');
  src = edit(src,
    '                # 下单\n' +
    '                order(stock, amount, MarketOrderStyle())\n' +
    '    return\n',
    '                # 下单\n' +
    '                _ew_o = order(stock, amount, MarketOrderStyle())\n' +
    '                try:  # HARNESS log\n' +
    '                    log.info(\'EWFILL date=%s code=%s cash=%.2f amount=%s filled=%s price=%.4f\' % (_ew_d, stock, Cash, amount, (_ew_o.filled if _ew_o is not None else 0), (_ew_o.price if _ew_o is not None else 0.0)))  # HARNESS log\n' +
    '                except Exception as _e:  # HARNESS log\n' +
    '                    log.info(\'EWFILL date=%s code=%s err=%s\' % (_ew_d, stock, _e))  # HARNESS log\n' +
    '    log.info(\'EWDEPLOY date=%s n_buy=%d cash_before=%.2f cash_after=%.2f total_value=%.2f first=%s\' % (_ew_d, len(buy_lists), _ew_before, context.portfolio.available_cash, context.portfolio.total_value, _ew_first))  # HARNESS log\n' +
    '    return\n');
  // final-day handler
  src = edit(src, "    run_daily(selled_security_list_count, 'after_close') #卖出股票日期计数 \n",
    "    run_daily(selled_security_list_count, 'after_close') #卖出股票日期计数 \n" +
    "    run_daily(_ew_final, 'after_close')  # HARNESS log\n");
  const helpers = `
# ===== POOL-EW HARNESS helpers (study/向导式低波价值/pool-ew-harness.js; logging only) =====
_EW = {'day1': None}

def _ew_final(context):
    d = context.current_dt.strftime('%Y-%m-%d')
    try:
        end = context.run_params.end_date
        end = end.strftime('%Y-%m-%d') if hasattr(end, 'strftime') else str(end)[:10]
    except Exception:
        end = '2024-12-31'
    if d != end:
        return
    for c, p in context.portfolio.positions.items():
        try:
            log.info('EWFINAL date=%s code=%s amount=%s avg_cost=%.4f price=%.4f value=%.2f' % (d, c, p.total_amount, p.avg_cost, p.price, p.value))
        except Exception as e:
            log.info('EWFINAL date=%s code=%s err=%s' % (d, c, e))
    log.info('EWFINALTOT date=%s total_value=%.2f cash=%.2f' % (d, context.portfolio.total_value, context.portfolio.available_cash))
`;
  // insert helpers BEFORE the OVERRIDE so the override stays the file's tail
  src = edit(src, OVERRIDE, helpers + OVERRIDE);
  // code side only (a comment naming the old call must not trip the guard)
  const code = src.split('\n').map(l => l.split('#')[0]).join('\n');
  for (const bad of ['order_style(context', 'ATR_judge_dayu(security, 0.35']) {
    if (code.includes(bad)) throw new Error(`harness left a live call: ${bad}`);
  }
  return src;
}

module.exports = { edit, loadBase, applyHarness };
