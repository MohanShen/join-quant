# Clone from JoinQuant
# postId: be2b51926ff88bab03f73a61ac948a97
# backtestId: ce2809051bfbc593628eb4fa34407f57
# title: 大盘蓝筹股均值回归策略（升级版）

# coding: utf-8
from jqdata import *
import json

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    set_slippage(FixedSlippage(0))

    # 加载信号数据并存入 context
    load_signal_table(context)

    log.info("=== INIT DONE === dt={}, dates_cnt={}, range={}~{}".format(
        context.current_dt,
        len(context.all_signal_dates),
        context.all_signal_dates[0] if context.all_signal_dates else None,
        context.all_signal_dates[-1] if context.all_signal_dates else None
    ))

    run_daily(rebalance, time='open')

def load_signal_table(context):
    content = read_file('csi300_final_signal_corrected.json')
    raw = json.loads(content)

    # 解析 historical_holdings
    historical = raw.get('historical_holdings', {})
    signal_table = {}
    for date, holdings in historical.items():
        if not isinstance(holdings, dict):
            continue
        converted = {}
        for code, info in holdings.items():
            if isinstance(info, dict) and 'weight' in info:
                weight = info['weight']
            else:
                try:
                    weight = float(info)
                except:
                    continue
            jq_code = convert_code_to_jq(code)
            if jq_code and weight > 0:
                converted[jq_code] = weight
        if converted:
            signal_table[date] = converted

    all_signal_dates = sorted(signal_table.keys())

    # 解析 next_day_target
    next_day_target_raw = raw.get('next_day_target', {})
    next_day_target = {}
    for date, holdings in next_day_target_raw.items():
        if not isinstance(holdings, dict):
            continue
        converted = {}
        for code, info in holdings.items():
            if isinstance(info, dict) and 'weight' in info:
                weight = info['weight']
            else:
                continue
            jq_code = convert_code_to_jq(code)
            if jq_code and weight > 0:
                converted[jq_code] = weight
        if converted:
            next_day_target[date] = converted

    # 存入 context
    context.signal_table = signal_table
    context.all_signal_dates = all_signal_dates
    context.next_day_target = next_day_target

    log.info("historical_holdings 加载完成，共 {} 个交易日，最后日期: {}".format(
        len(all_signal_dates), all_signal_dates[-1] if all_signal_dates else "无"
    ))
    log.info("next_day_target 加载完成，包含日期: {}".format(list(next_day_target.keys())))

def convert_code_to_jq(raw_code):
    if not isinstance(raw_code, str):
        return None
    s = raw_code.strip().upper()
    if s.endswith('.XSHG') or s.endswith('.XSHE'):
        return s
    if s.startswith('SH') and len(s) >= 8:
        return s[2:] + '.XSHG'
    if s.startswith('SZ') and len(s) >= 8:
        return s[2:] + '.XSHE'
    log.warn("convert_code_to_jq: unrecognized code={}".format(raw_code))
    return None

def is_kechuang(stock):
    return isinstance(stock, str) and stock.startswith('688') and stock.endswith('.XSHG')

def get_ref_price(stock):
    try:
        h = attribute_history(stock, 1, '1d', ['close'], df=False)
        price = h['close'][0]
        if price is None or price <= 0:
            return None
        return price
    except Exception as e:
        log.warn("get_ref_price fail: stock={}, err={}".format(stock, e))
        return None

def order_target_value_smart(context, stock, target_value):
    if not is_kechuang(stock):
        o = order_target_value(stock, target_value)
        if o is None:
            log.warn("order None: stock={}, target_value={:.2f}".format(stock, target_value))
        return
    price = get_ref_price(stock)
    if price is None:
        log.warn("KC skip: stock={}, reason=no_ref_price".format(stock))
        return
    pos = context.portfolio.positions.get(stock, None)
    cur_amount = pos.total_amount if pos is not None else 0
    cur_value = cur_amount * price
    protect_price = price * (1.02 if target_value > cur_value else 0.98)
    protect_price = max(min(protect_price, 9999), 0.01)
    o = order_target_value(stock, target_value, style=LimitOrderStyle(protect_price))
    if o is None:
        log.warn("KC order None: stock={}, target_value={:.2f}, protect_price={:.3f}".format(
            stock, target_value, protect_price
        ))

def _clear_all_positions(context, reason):
    if len(context.portfolio.positions) == 0:
        log.info("{}: already empty, skip clear".format(reason))
        return
    log.info("{}: clearing all positions, cnt={}".format(reason, len(context.portfolio.positions)))
    for stock in list(context.portfolio.positions.keys()):
        order_target_value_smart(context, stock, 0)

def rebalance(context):
    log.info("=== rebalance fired === dt={}".format(context.current_dt))

    # 每日首次运行时重新加载信号文件（确保使用最新信号）
    current_date = context.current_dt.strftime('%Y-%m-%d')
    if not hasattr(context, 'last_loaded_date') or context.last_loaded_date != current_date:
        load_signal_table(context)   # 重新加载信号
        context.last_loaded_date = current_date
        log.info("每日重新加载信号文件完成")

    use_date = current_date
    log.info("use_date = {}".format(use_date))

    # 优先从 next_day_target 获取当天信号（用于模拟盘）
    target_weights = context.next_day_target.get(use_date, {})
    if target_weights:
        log.info("从 next_day_target 获取日期 {} 的持仓，共 {} 只".format(use_date, len(target_weights)))
    else:
        # 如果 next_day_target 没有，则从 historical_holdings 获取（用于回测）
        target_weights = context.signal_table.get(use_date, {})
        if target_weights:
            log.info("从 historical_holdings 获取日期 {} 的持仓，共 {} 只".format(use_date, len(target_weights)))

    log.info("target_cnt={}, weights: {}".format(len(target_weights), list(target_weights.keys())[:3] if target_weights else []))

    if not target_weights:
        _clear_all_positions(context, "empty signal for {}".format(use_date))
        return

    total_value = context.portfolio.total_value
    log.info("total_value for allocation: {:.2f}".format(total_value))

    current_positions = list(context.portfolio.positions.keys())
    log.info("current_positions: {}".format(current_positions))

    sell_cnt = 0
    for stock in current_positions:
        if stock not in target_weights:
            log.info("selling stock not in target: {}".format(stock))
            order_target_value_smart(context, stock, 0)
            sell_cnt += 1

    buy_cnt = 0
    for stock, w in target_weights.items():
        target_value = total_value * w
        log.info("buying stock: {}, weight={:.6f}, target_value={:.2f}".format(stock, w, target_value))
        order_target_value_smart(context, stock, target_value)
        buy_cnt += 1

    log.info("rebalance done: use_date={}, target_cnt={}, sold_out={}, ordered={}".format(
        use_date, len(target_weights), sell_cnt, buy_cnt
    ))