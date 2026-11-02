# Clone from JoinQuant
# postId: bce47523c927b3587cd99452d0bd6cc8
# backtestId: 07f91a14afeff131059a9522ce06d50d
# title: 聚宽研究环境中上传文件有什么限制？

# 聚宽布林带+RSI反转策略（带止损止盈）
# 策略说明：
# 1. 当收盘价跌破布林带下轨且14日RSI<30（超卖）时，全仓买入
# 2. 当收盘价升破布林带上轨且14日RSI>70（超买）时，全部卖出
# 3. 持仓期间若亏损超过5%立即止损，盈利超过15%则止盈
# 4. 每日14:00执行，避免未来函数

import numpy as np

def initialize(context):
    """初始化策略参数"""
    set_benchmark('000300.XSHG')               # 沪深300基准
    set_option('use_real_price', True)         # 使用复权价格
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5
    ), type='stock')
    set_slippage(FixedSlippage(0.00))

    # 策略参数（可根据需要调整）
    g.stock = '510300.XSHG'          # 标的：沪深300ETF
    g.boll_period = 20               # 布林带周期
    g.boll_std = 2                   # 布林带标准差倍数
    g.rsi_period = 14                # RSI周期
    g.rsi_oversold = 30              # RSI超卖阈值
    g.rsi_overbought = 70            # RSI超买阈值
    g.stop_loss = 0.05               # 止损比例5%
    g.stop_profit = 0.15             # 止盈比例15%

    # 记录买入价格用于止损止盈
    g.buy_price = 0

    # 每天14:00执行交易逻辑
    run_daily(trade, time='14:00')


def calc_rsi(closes, period=14):
    """手动计算RSI（使用简单移动平均）"""
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.maximum(deltas, 0)
    losses = np.abs(np.minimum(deltas, 0))

    # 取最近period个差值计算平均（简单移动平均）
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def trade(context):
    """每日交易逻辑"""
    stock = g.stock

    # 获取当前价格（用于止损止盈的实时判断）
    current_data = get_current_data()
    if stock not in current_data:
        return
    current_price = current_data[stock].last_price
    if current_price is None:
        return

    # 获取足够长的历史收盘价（至少 max(boll_period, rsi_period) + 2）
    need_len = max(g.boll_period, g.rsi_period) + 2
    hist = attribute_history(stock, need_len, '1d', ['close'], df=False)
    closes = hist['close']
    if len(closes) < g.boll_period + 1 or len(closes) < g.rsi_period + 1:
        log.info("数据不足，跳过交易")
        return

    # 计算布林带（基于前一日数据，使用 closes[:-1] 是除去最新一日，closes[-1]为昨日）
    # 这里使用最近 boll_period 根K线计算均值和标准差
    boll_period = g.boll_period
    middle = np.mean(closes[-(boll_period + 1):-1])   # 昨日中轨
    std = np.std(closes[-(boll_period + 1):-1])
    upper = middle + g.boll_std * std
    lower = middle - g.boll_std * std

    # 计算RSI（基于前一日数据，需要 period+1 个收盘价计算差值）
    rsi = calc_rsi(closes[-(g.rsi_period + 1):-1], g.rsi_period)

    # 昨日收盘价
    yesterday_close = closes[-1]

    # 当前持仓
    position = context.portfolio.positions[stock]
    hold_shares = position.total_amount
    cash = context.portfolio.available_cash

    # -------- 止损止盈逻辑 --------
    if hold_shares > 0 and g.buy_price > 0:
        profit_ratio = (current_price - g.buy_price) / g.buy_price
        if profit_ratio <= -g.stop_loss:
            order_target(stock, 0)
            log.info(f"止损卖出 {stock}，亏损 {profit_ratio:.2%}")
            g.buy_price = 0
            return
        elif profit_ratio >= g.stop_profit:
            order_target(stock, 0)
            log.info(f"止盈卖出 {stock}，盈利 {profit_ratio:.2%}")
            g.buy_price = 0
            return

    # -------- 反转信号逻辑 --------
    # 买入条件：昨日收盘价 <= 下轨 且 RSI < 超卖阈值
    if hold_shares == 0 and yesterday_close <= lower and rsi < g.rsi_oversold:
        order_value(stock, cash)
        g.buy_price = current_price
        log.info(f"超卖买入 {stock}，价格 {current_price:.2f}，RSI: {rsi:.1f}")

    # 卖出条件：昨日收盘价 >= 上轨 且 RSI > 超买阈值
    elif hold_shares > 0 and yesterday_close >= upper and rsi > g.rsi_overbought:
        order_target(stock, 0)
        log.info(f"超买卖出 {stock}，价格 {current_price:.2f}，RSI: {rsi:.1f}")
        g.buy_price = 0