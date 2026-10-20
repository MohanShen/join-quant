# Clone from JoinQuant
# postId: 33622040733fa34e3002bd64c3a08213
# backtestId: e089aa30bb43d80e99eb1ab163f9f8cb
# title: 四大银行轮动P-Trade移植版

# 克隆自聚宽文章：https://www.joinquant.com/post/62562
# 标题：四大行 轮动做T，已实盘
# 作者：fqd1999
# PTrade版在代码后部，庐阳居移植

# 银行股票池：工行、农行、中行、建行
bank_stocks = ['601398.XSHG', '601288.XSHG', '601939.XSHG', '601988.XSHG']


# 回测设置
def set_backtest():
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)

    set_slippage(FixedSlippage(0.0001), type="stock")
    cost_configs = [
        ("stock", 0.0005, 0.85 / 10000, 5),
        ("mmf", 0, 0, 0)
    ]
    for asset_type, close_tax, commission, min_comm in cost_configs:
        set_order_cost(OrderCost(
            open_tax=0, close_tax=close_tax,
            open_commission=commission, close_commission=commission,
            close_today_commission=0, min_commission=min_comm
        ), type=asset_type)


# 初始化参数
def initialize(context):
    # 设置股票池为空（动态调整）
    set_universe([])
    set_backtest()

    # 过滤日志
    log.set_level('order', 'error')
    # log.set_level('system', 'error')
    # log.set_level('strategy', 'error')
    
    g.inter = 0.004  # 价差阈值（0.5%）
    g.is_stop = False
    g.buy_dates = {}  # 记录每只股票的买入日期
    g.df_last = None
    g.cumulative_return_history = {stock: [0.0] for stock in bank_stocks}
    g.dates_history = []


# 每天交易前调用
def before_trading_start(context):
    # 获取前一交易日收盘价（Python 3中history函数返回DataFrame时兼容处理）
    g.df_last = history(
        1,
        unit='1d',
        field='close',
        security_list=bank_stocks,
        df=False,
        skip_paused=True,
        fq='pre'
    )


# 封装实盘下单函数
def my_order_target_value(security, value):
    o = order_target_value(security, value)
    if o:
        stock_show = f"{security} {get_stock_name(security)[:8]}: ".ljust(20)
        if o.is_buy:
            if o.price * o.amount > 0:
                print(f"🚚🚚🚚🚚🚚 {stock_show}  "
                      f"买价{o.price:<7.2f}  "
                      f"买量{o.amount:<7}   "
                      f"价值{o.price * o.amount:.2f}")
                return o
        else:
            if o.price * o.amount > 0:
                print(f"🚛🚛🚛🚛🚛 {stock_show}  "
                      f"卖价{o.price:<7.2f}  "
                      f"成本{o.avg_cost:<7.2f}   "
                      f"卖量{o.amount:<7}   "
                      f"盈亏{(o.price - o.avg_cost) * o.amount:.2f}"
                      f"( {(o.price - o.avg_cost) / o.avg_cost * 100:.2f}% )")
                return o


# 每个单位时间调用（按分钟回测时每分钟触发）
def handle_data(context, data):
    raito = []
    # 计算当前价格与前一日收盘价的比值（涨幅比例）
    for code in bank_stocks:
        # Python 3中列表索引和除法兼容
        raito.append(data[code].close / g.df_last[code][-1])

    # 空仓时的开仓逻辑
    if not context.portfolio.positions:  # Python 3中keys()返回视图，直接判断是否为空更简洁
        if max(raito) - min(raito) > g.inter:
            # 找到涨幅最小的股票索引
            min_index = raito.index(min(raito))
            stocks = bank_stocks[min_index]
            # 满仓买入
            my_order_target_value(stocks, context.portfolio.total_value)
            # 记录买入日期
            g.buy_dates[bank_stocks[min_index]] = context.current_dt.date()
            g.is_stop = True
    # 持仓时的调仓逻辑
    else:
        code = list(context.portfolio.positions.keys())[0]
        index = bank_stocks.index(code)
        # 当前持仓涨幅与最小涨幅的差值超过阈值时调仓
        if raito[index] - min(raito) > g.inter:
            # 检查是否是今天买入的股票
            if code in g.buy_dates and g.buy_dates[code] == context.current_dt.date():
                # 如果是今天买入的，不能卖出，跳过调仓
                # log.info(f"股票{code}是今天买入的，不能卖出，跳过调仓")
                return

            # 清空当前持仓
            my_order_target_value(code, 0)
            # 从买入日期记录中移除
            if code in g.buy_dates:
                del g.buy_dates[code]

            # 买入新的涨幅最小的股票
            min_index = raito.index(min(raito))
            my_order_target_value(bank_stocks[min_index], context.portfolio.total_value)
            # 记录新买入股票的日期
            g.buy_dates[bank_stocks[min_index]] = context.current_dt.date()
            g.is_stop = True


# 获取股票名字
def get_stock_name(security):
    return get_security_info(security).display_name


# 每天交易后调用，计算并记录累计收益率
def after_trading_end(context):
    """
    计算四大银行股的累计收益率
    股票池：工行(601398)、农行(601288)、建行(601939)、中行(601988)
    """

    # 初始化累计收益率历史记录（如果不存在）
    if not hasattr(g, 'cumulative_return_history'):
        g.cumulative_return_history = {stock: [] for stock in bank_stocks}
    if not hasattr(g, 'dates_history'):
        g.dates_history = []

    # 获取历史价格数据（包含当天）
    lookback_days = 1  # 只需要前一天的数据来计算当日收益率
    try:
        hist_data = history(lookback_days, '1d', 'close', bank_stocks, df=True, skip_paused=True, fq='pre')

        # 获取当前价格
        current_data = get_current_data()
        current_prices = {stock: current_data[stock].last_price for stock in bank_stocks}

        # 记录当前日期
        current_date = context.current_dt.strftime('%Y-%m-%d')
        g.dates_history.append(current_date)

        # 计算每个股票的日收益率和更新累计收益率
        for stock in bank_stocks:
            if stock in hist_data.columns and len(hist_data[stock]) >= lookback_days:
                # 计算当日收益率
                prev_close = hist_data[stock].iloc[-1]  # 昨日收盘价
                today_close = current_prices[stock]  # 今日收盘价
                daily_return = (today_close - prev_close) / prev_close

                # 计算累计收益率
                if not g.cumulative_return_history[stock]:  # 第一天
                    cumulative_return = daily_return
                else:
                    prev_cumulative = g.cumulative_return_history[stock][-1]
                    cumulative_return = (1 + prev_cumulative) * (1 + daily_return) - 1

                g.cumulative_return_history[stock].append(cumulative_return)

                # 使用record函数记录累计收益率（用于回测图表）
                if stock == '601398.XSHG':
                    record(工行=round(cumulative_return * 100, 2))
                elif stock == '601288.XSHG':
                    record(农行=round(cumulative_return * 100, 2))
                elif stock == '601939.XSHG':
                    record(建行=round(cumulative_return * 100, 2))
                elif stock == '601988.XSHG':
                    record(中行=round(cumulative_return * 100, 2))
            else:
                # 数据不足时记录0
                cumulative_return = 0
                g.cumulative_return_history[stock].append(cumulative_return)

        # 打印当日累计收益率情况
        log.info("累计收益率报告 " + "*" * 60)
        for stock in bank_stocks:
            stock_name = get_stock_name(stock)
            latest_cumulative = g.cumulative_return_history[stock][-1] if g.cumulative_return_history[stock] else 0
            log.info(f"  {stock} {stock_name}:  {latest_cumulative * 100:.2f}%")

    except Exception as e:
        log.error(f"计算累计收益率失败: {e}")

"""
# 银行轮动_最终完美版.py
"
银行股网格轮动策略 · 最终完美版

- 实盘：10万虚拟池 + 每分钟同步 + 防重复 + 自动纠偏

庐阳居移植
"

import numpy as np

bank_stocks = ['601398.SS', '601288.SS', '601939.SS', '601988.SS']


def initialize(context):
    set_benchmark("000300.XSHG")

    # ---------- 真实交易成本 ----------
    #set_commission(commission_ratio=0.00015, min_commission=5.0)   # 佣金万1.5，最低5元
    #set_slippage(0.001)    # 滑点0.1%

    g.inter = 0.004
    g.position_ratio = 1.0
    g.buy_dates = {}

    g.df_last = None

    g.virtual_cash = 0.0
    g.virtual_holdings = {stock: 0 for stock in bank_stocks}
    g.virtual_initialized = False

    g.order_locked = False
    g.last_buy_minute = None
    g.force_correct = False

    if not is_trade():
        set_limit_mode('UNLIMITED')
        log.info("回测模式启动（佣金万1.5 + 滑点0.1%）")
    else:
        log.info("实盘模式启动（10万虚拟池）")


def before_trading_start(context, data):
    try:
        hist_data = get_history(1, '1d', field=['close'],
                                security_list=bank_stocks,
                                fq='dypre', include=False)
        g.df_last = {}
        for code in bank_stocks:
            if code in hist_data and hist_data[code] is not None and len(hist_data[code]) > 0:
                g.df_last[code] = float(hist_data[code].iloc[-1])
            else:
                g.df_last[code] = None
        log.info("昨收: {}".format(g.df_last))
    except Exception as e:
        log.error("昨收获取失败: {}".format(e))
        g.df_last = None

    g.order_locked = False

    if is_trade() and not g.virtual_initialized:
        pos = get_positions()
        held_count = 0
        for code in bank_stocks:
            xshg = code.replace('SS', 'XSHG')
            if xshg in pos and pos[xshg].amount > 0:
                held_count += 1
        if held_count > 1:
            g.force_correct = True
            log.warning("检测到持有多只银行股，开盘后将强制清仓纠偏")
        else:
            g.force_correct = False

        sync_virtual_from_real(context, data)
        g.virtual_initialized = True


def sync_virtual_from_real(context, data):
    pos = get_positions()
    total_value = 0.0
    for code in bank_stocks:
        xshg = code.replace('SS', 'XSHG')
        real_amt = pos[xshg].amount if xshg in pos else 0
        g.virtual_holdings[code] = real_amt
        if real_amt > 0:
            total_value += real_amt * data[code].price
    g.virtual_cash = max(0.0, 100000.0 - total_value)
    log.info("虚拟池同步: 持仓 {}，现金 {:.2f}".format(g.virtual_holdings, g.virtual_cash))


def handle_data(context, data):
    if g.df_last is None or len(g.df_last) == 0:
        return

    # 仅实盘启用：当日已买入则全天停止判断
    if is_trade():
        today = context.blotter.current_dt.date()
        for stock, date in g.buy_dates.items():
            if date == today and g.virtual_holdings.get(stock, 0) > 0:
                return

    if is_trade():
        sync_virtual_from_real(context, data)

    # 强制纠偏（仅实盘）
    if g.force_correct and is_trade():
        pos = get_positions()
        held_stocks = []
        for code in bank_stocks:
            xshg = code.replace('SS', 'XSHG')
            if xshg in pos and pos[xshg].amount > 0:
                held_stocks.append(code)
        if len(held_stocks) > 1:
            log.info("强制纠偏：清仓所有银行股")
            for code in held_stocks:
                order_target_value(code, 0)
            sync_virtual_from_real(context, data)
            ratio, valid = [], []
            for code in bank_stocks:
                try:
                    if g.df_last.get(code) and g.df_last[code] > 0:
                        cp = data[code].close
                        if cp > 0:
                            ratio.append(cp / g.df_last[code])
                            valid.append(code)
                except:
                    pass
            if len(ratio) >= 2:
                min_idx = ratio.index(min(ratio))
                target = valid[min_idx]
                total_value = g.virtual_cash + sum(g.virtual_holdings[s] * data[s].price for s in bank_stocks)
                tv = total_value * g.position_ratio
                if tv >= data[target].price * 100:
                    log.info("强制纠偏：买入 {}".format(target))
                    order_target_value(target, tv)
                    g.buy_dates[target] = today
                    g.last_buy_minute = context.blotter.current_dt.strftime('%Y%m%d%H%M')
            g.force_correct = False
            return
        else:
            g.force_correct = False

    # 订单锁（仅实盘）
    if is_trade() and g.order_locked:
        pos = get_positions()
        real_total = 0.0
        for code in bank_stocks:
            xshg = code.replace('SS', 'XSHG')
            if xshg in pos:
                real_total += pos[xshg].amount * data[code].price
        virt_total = sum(g.virtual_holdings[code] * data[code].price for code in bank_stocks)
        if abs(real_total - virt_total) < 100:
            g.order_locked = False
        else:
            return

    # 买入冷却（仅实盘）
    if is_trade() and g.last_buy_minute is not None:
        curr = context.blotter.current_dt.strftime('%Y%m%d%H%M')
        if int(curr) - int(g.last_buy_minute) < 5:
            return

    # 计算涨幅
    ratio, valid = [], []
    for code in bank_stocks:
        try:
            if g.df_last.get(code) and g.df_last[code] > 0:
                cp = data[code].close
                if cp > 0:
                    ratio.append(cp / g.df_last[code])
                    valid.append(code)
        except:
            pass
    if len(ratio) < 2:
        return

    # 持仓判定
    if is_trade():
        held_code = None
        for code in bank_stocks:
            if g.virtual_holdings[code] > 0:
                held_code = code
                break
        total_value = g.virtual_cash + sum(g.virtual_holdings[s] * data[s].price for s in bank_stocks)
    else:
        pos = get_positions()
        held_code = None
        for code in bank_stocks:
            xshg = code.replace('SS', 'XSHG')
            if xshg in pos and pos[xshg].amount > 0:
                held_code = code
                break
        total_value = context.portfolio.total_value

    current_date = context.blotter.current_dt.date()

    # 空仓开仓
    if held_code is None:
        max_r, min_r = max(ratio), min(ratio)
        if max_r - min_r > g.inter:
            idx = ratio.index(min_r)
            target = valid[idx]
            tv = total_value * g.position_ratio
            if tv < data[target].price * 100:
                return
            log.info("空仓开仓: {}, 价差{:.2f}%".format(target, (max_r-min_r)*100))
            order_target_value(target, tv)
            g.buy_dates[target] = current_date
            if is_trade():
                g.order_locked = True
                g.last_buy_minute = context.blotter.current_dt.strftime('%Y%m%d%H%M')

    # 持仓调仓
    else:
        held_idx = valid.index(held_code)
        held_r = ratio[held_idx]
        min_r = min(ratio)
        if held_r - min_r > g.inter:
            if g.buy_dates.get(held_code) == current_date:
                return
            min_idx = ratio.index(min_r)
            target = valid[min_idx]
            if target == held_code:
                return
            log.info("调仓: 卖{} 买{}".format(held_code, target))
            order_target_value(held_code, 0)
            if held_code in g.buy_dates:
                del g.buy_dates[held_code]
            if is_trade():
                sync_virtual_from_real(context, data)
                total_value = g.virtual_cash + sum(g.virtual_holdings[s] * data[s].price for s in bank_stocks)
            else:
                total_value = context.portfolio.total_value
            tv = total_value * g.position_ratio
            if tv < data[target].price * 100:
                return
            order_target_value(target, tv)
            g.buy_dates[target] = current_date
            if is_trade():
                g.order_locked = True
                g.last_buy_minute = context.blotter.current_dt.strftime('%Y%m%d%H%M')
"""