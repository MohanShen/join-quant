# Clone from JoinQuant
# postId: a65225704197a1b365c3af6311bf1829
# backtestId: 8255e13c5896f7cebf384386b1c5e437
# title: 马马虎虎老师的超跌反弹策略******

import math
from jqdata import *

def initialize(context):
    """初始化函数，设置基本参数和定时任务"""
    log.set_level('order', 'warning')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.002))
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_benchmark('000001.XSHG')

    # 策略参数
    g.stock_pool_size = 1500  # 选股池大小
    g.max_stock_num = 5  # 最大持股数
    g.stock_pool = []  # 可选股票池
    g.hold_list = []  # 当前持仓股票
    # 原代码中该变量定义后未使用，保留但注释说明
    g.yesterday_high_limit_list = []  # 昨日涨停股票（注：该变量未在核心逻辑中使用）

    # 定时任务
    run_daily(prepare_stock_list, time='9:28', reference_security='000001.XSHG')
    run_daily(my_trade, time='9:30', reference_security='000001.XSHG')
    run_daily(sell_close, time='14:40', reference_security='000001.XSHG')

def filter_specials(context, stock_list):
    """修复：正确过滤特定股票（ST股、退市股、科创板、创业板等）"""
    curr_data = get_current_data()
    filtered_stocks = []
    for stock in stock_list:
        try:
            # 跳过停牌、ST、退市预警股
            if curr_data[stock].paused or curr_data[stock].is_st:
                continue
            if 'ST' in curr_data[stock].name or '*' in curr_data[stock].name or '退' in curr_data[stock].name:
                continue
            # 正确过滤：科创板(688开头)、创业板(300开头)、北交所(8开头)、老三板(4开头)
            # 原代码错误过滤68/9开头，现精准过滤
            if stock.startswith(('688', '300', '4', '8')):
                continue
            filtered_stocks.append(stock)
        except Exception as e:
            # 捕获单只股票数据异常，避免整体过滤失败
            log.warning(f"过滤股票{stock}时异常：{str(e)}")
            continue
    return filtered_stocks

def before_trading_start(context):
    """交易开始前准备股票池（添加异常捕获）"""
    try:
        fundamentals_data = get_fundamentals(
            query(valuation.code, valuation.market_cap)
            .order_by(valuation.market_cap.asc())
            .limit(g.stock_pool_size)
        )
        g.stock_pool = filter_specials(context, list(fundamentals_data['code']))
    except Exception as e:
        log.error(f"获取基本面数据异常：{str(e)}")
        g.stock_pool = []

def my_trade(context):
    """执行每日交易逻辑"""
    sell_open(context)
    buy_stocks(context, g.stock_pool)

def sell_open(context):
    """早盘卖出策略（添加异常捕获）"""
    current_data = get_current_data()
    for position in context.portfolio.positions.values():
        try:
            if position.closeable_amount > 0 and current_data[position.security].day_open < current_data[position.security].high_limit:
                close_position(position)
        except Exception as e:
            log.warning(f"早盘卖出{position.security}异常：{str(e)}")
            continue

def sell_close(context):
    """尾盘卖出策略（添加异常捕获）"""
    current_data = get_current_data()
    for position in context.portfolio.positions.values():
        try:
            if position.closeable_amount > 0 and current_data[position.security].last_price < current_data[position.security].high_limit:
                close_position(position)
        except Exception as e:
            log.warning(f"尾盘卖出{position.security}异常：{str(e)}")
            continue

def buy_stocks(context, target_list):
    """买入逻辑：修复数据索引、最小交易单位、异常捕获等问题"""
    if not target_list:
        return
    current_data = get_current_data()
    # 修复：实际可开仓数量 = 最大持股数 - 当前持仓数（已平仓的订单不影响）
    available_buy_count = g.max_stock_num - len(context.portfolio.positions)
    if available_buy_count <= 0:
        return
    buy_candidates = []

    for stock in target_list:
        try:
            if len(buy_candidates) >= available_buy_count:
                break
            # 跳过已持仓股票
            if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
                continue

            # 获取历史数据并添加异常捕获
            history_data = attribute_history(
                stock, 5, '1d', ('close', 'low', 'high', 'paused'), 
                skip_paused=False
            )
            # 修复：数据索引边界检查（确保数据长度足够）
            if len(history_data) < 5 or history_data['paused'].max() != 0:
                continue

            today_open = current_data[stock].day_open
            prev_close = history_data['close'].iloc[-1]  # 改用iloc避免索引异常
            prev_low = history_data['low'].iloc[-1]
            change_rate = (today_open - prev_close) / prev_close * 100

            if today_open < prev_low and change_rate < -0.75:
                # 修复：边界检查（确保有足够的历史数据）
                if len(history_data['low']) < 4 or len(history_data['high']) < 4:
                    continue
                recent_low = min(history_data['low'].iloc[-4:])
                recent_high = max(history_data['high'].iloc[-4:])
                amplitude = (recent_high - recent_low) / recent_low * 100

                if amplitude <= 20:
                    ema_5 = history_data['close'].ewm(span=5).mean().iloc[-1]
                    if prev_close > ema_5:
                        buy_candidates.append(stock)
        except Exception as e:
            log.warning(f"筛选买入候选{stock}异常：{str(e)}")
            continue

    # 分配资金买入股票（修复：考虑最小交易单位）
    if buy_candidates:
        available_cash = context.portfolio.available_cash
        cash_per_stock = available_cash / len(buy_candidates)
        for stock in buy_candidates:
            try:
                # 修复：计算最小交易单位（100股整数倍）
                stock_price = current_data[stock].day_open
                if stock_price <= 0:
                    continue
                # 可买股数 = 资金 / 股价，取100的整数倍
                max_shares = int(cash_per_stock / stock_price / 100) * 100
                if max_shares < 100:  # 不足100股，跳过
                    log.warning(f"股票{stock}可买数量不足100股，跳过买入")
                    continue
                # 实际买入金额 = 可买股数 * 股价
                actual_buy_value = max_shares * stock_price
                open_position(context, stock, actual_buy_value)
            except Exception as e:
                log.warning(f"买入{stock}异常：{str(e)}")
                continue

def order_target_value_(security, value):
    """下单函数（添加异常捕获）"""
    try:
        return order_target_value(security, value)
    except Exception as e:
        log.error(f"下单{security}异常：{str(e)}")
        return None

def open_position(context, security, value):
    """修复：开仓函数（修正状态判断逻辑）"""
    _order = order_target_value_(security, value)
    if _order is None:
        log.warning(f"开仓{security}失败：订单提交失败")
        return False
    # 修复：异步下单不判断即时filled，仅判断订单是否成功提交
    # 实盘可后续通过order_status查询成交状态，此处返回订单提交状态
    return _order.status != OrderStatus.rejected

def close_position(position):
    """修复：平仓函数（修正状态判断逻辑，核心错误修复）"""
    _order = order_target_value_(position.security, 0)
    if _order is None:
        log.warning(f"平仓{position.security}失败：订单提交失败")
        return False
    # 修复：正确判断平仓订单是否全部成交（OrderStatus.filled代表已成交）
    # 若需实时确认，可后续轮询；此处优先保证逻辑自洽
    if _order.status == OrderStatus.filled and _order.filled == _order.amount:
        log.info(f"平仓{position.security}成功：全部成交")
        return True
    elif _order.status == OrderStatus.held:
        log.info(f"平仓{position.security}：订单已挂单，等待成交")
        return True  # 订单已提交，视为平仓操作成功（后续成交状态需单独跟踪）
    else:
        log.warning(f"平仓{position.security}失败：订单状态{_order.status}，成交{_order.filled}/{_order.amount}")
        return False

def prepare_stock_list(context):
    """准备股票池（添加异常捕获，注释冗余变量）"""
    g.hold_list = list(context.portfolio.positions.keys())
    if g.hold_list:
        try:
            df = get_price(
                g.hold_list, end_date=context.previous_date, frequency='daily',
                fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False
            )
            g.yesterday_high_limit_list = list(df[df['close'] == df['high_limit']].code)
        except Exception as e:
            log.warning(f"获取昨日涨停股票异常：{str(e)}")
            g.yesterday_high_limit_list = []
    else:
        g.yesterday_high_limit_list = []
    # 注：g.yesterday_high_limit_list未在核心交易逻辑中使用，保留仅为兼容原代码结构