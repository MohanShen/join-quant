# Clone from JoinQuant
# postId: f120a0673eefc9f6699b1c102867e78f
# backtestId: e103d41543c509a347bbe2cf7b19dcfb
# title: 分享-中证500趋势跟踪策略

# 中证500趋势跟踪策略（优化版）- 20日线空仓 + 10日线减仓至30%
import jqdata
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ==================== 初始化 ====================
def initialize(context):
    # ---------- 策略参数 ----------
    g.stock_num = 3
    g.index_code = '000905.XSHG'
    g.lookback_days = 60
    g.ma_short = 5
    g.ma_mid = 20
    g.ma_long = 60
    g.volume_ratio = 2.5         # 不缩量即可
    
    g.roc_period = 10
    g.stop_loss = -0.3
    g.take_profit = 0.15
    g.trailing_retreat = 0.04
    g.hold_days_limit = 5
    g.max_volatility = 0.80

    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.001))
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))

    run_daily(select_stocks, time='09:40')
    run_daily(trade, time='10:00')
    run_daily(risk_control, time='14:30')

    g.buy_date = {}
    g.highest_price = {}

    log.set_level('order', 'info')
    log.set_level('strategy', 'info')


# ==================== 大盘仓位控制（综合20日线和10日线） ====================
def get_target_ratio(context, date):
    """
    返回目标仓位比例：
      0.0  -> 空仓（跌破20日线）
      0.3  -> 30%仓位（20日线上但跌破10日线）
      1.0  -> 满仓（20日线上且10日线上）
    """
    data = get_price(g.index_code, end_date=date, frequency='daily',
                     fields=['close'], skip_paused=True, count=21)  # 至少21个数据计算MA20和MA10
    if data is None or len(data) < 20:
        log.warning('无法获取足够指数数据，默认满仓')
        return 1.0
    closes = data['close'].values
    ma20 = np.mean(closes[-20:])
    ma10 = np.mean(closes[-10:])
    current = closes[-1]

    if current <= ma20:
        ratio = 0.0
    elif current <= ma10:   # 在20日线上但跌破10日线
        ratio = 0.3
    else:
        ratio = 1.0

    log.info('指数收盘%.2f, MA20=%.2f, MA10=%.2f, 目标仓位: %.0f%%' % (current, ma20, ma10, ratio*100))
    return ratio


# ==================== 09:40 选股（大盘空仓时不选股） ====================
def select_stocks(context):
    date = context.previous_date
    log.info('========== 选股开始 (数据基准日: %s) ==========' % date)

    # 先判断大盘，若目标仓位为0则直接清空候选
    target_ratio = get_target_ratio(context, date)
    if target_ratio == 0.0:
        log.info('指数跌破20日均线，今日空仓，不选股')
        g.candidate_stocks = []
        return

    index_stocks = get_index_stocks(g.index_code)
    if not index_stocks:
        log.warning('未获取到中证500成分股')
        g.candidate_stocks = []
        return
    log.info('成分股数量: %d' % len(index_stocks))

    df = get_price(index_stocks, end_date=date, frequency='daily',
                   fields=['close', 'high', 'volume'], skip_paused=False,
                   count=g.lookback_days + g.roc_period + 1, panel=False)
    if df is None or df.empty:
        log.warning('获取行情数据为空')
        g.candidate_stocks = []
        return

    if 'code' not in df.columns:
        log.warning('数据中没有 code 列，无法识别股票')
        g.candidate_stocks = []
        return

    stock_list = df['code'].unique()
    log.info('实际股票数: %d' % len(stock_list))
    if len(stock_list) < 10:
        log.warning('股票数过少，可能数据获取异常')

    cnt_total = 0
    cnt_ma = 0
    cnt_volatility = 0
    cnt_volume = 0
    cnt_roc = 0
    cnt_macd = 0
    candidates = []

    for stock in stock_list:
        cnt_total += 1
        stock_df = df[df['code'] == stock].sort_values('time')
        if len(stock_df) < g.lookback_days:
            continue

        stock_df = stock_df.set_index('time')
        closes = stock_df['close'].values.astype(float)
        highs = stock_df['high'].values.astype(float)
        volumes = stock_df['volume'].values.astype(float)

        if np.isnan(closes[-1]) or np.isnan(volumes[-1]) or volumes[-1] <= 0:
            continue

        if is_st_stock(stock):
            continue

        # 均线多头
        ma5 = np.mean(closes[-g.ma_short:])
        ma20 = np.mean(closes[-g.ma_mid:])
        ma60 = np.mean(closes[-g.ma_long:])
        if not (ma5 > ma20 > ma60):
            continue
        if closes[-1] <= ma5:
            continue
        cnt_ma += 1

        # 波动率
        if len(closes) >= 20:
            vol = np.std(closes[-20:]) / np.mean(closes[-20:])
            if vol > g.max_volatility:
                continue
        cnt_volatility += 1

        # 成交量
        if len(volumes) >= 21:
            avg_vol_20 = np.mean(volumes[-21:-1])
            if volumes[-1] < avg_vol_20 * g.volume_ratio:
                continue
        cnt_volume += 1

        # ROC
        if len(closes) >= g.roc_period + 1:
            roc_cur = (closes[-1] / closes[-1-g.roc_period] - 1)
            if roc_cur <= 0:
                continue
        cnt_roc += 1

        # MACD金叉
        if len(closes) >= 26:
            ema12_series = pd.Series(closes).ewm(span=12, adjust=False).mean()
            ema26_series = pd.Series(closes).ewm(span=26, adjust=False).mean()
            dif_series = ema12_series - ema26_series
            dea_series = dif_series.ewm(span=9, adjust=False).mean()
            dif = dif_series.values[-1]
            dea = dea_series.values[-1]
            if dif <= dea:
                continue
        cnt_macd += 1

        candidates.append(stock)

    log.info('总股票数: %d, 通过均线: %d, 波动率: %d, 成交量: %d, ROC: %d, MACD: %d, 最终候选: %d' %
             (cnt_total, cnt_ma, cnt_volatility, cnt_volume, cnt_roc, cnt_macd, len(candidates)))

    g.candidate_stocks = candidates
    log.info('选股结果数量: %d' % len(candidates))


# ==================== 10:00 调仓（执行仓位控制） ====================
def trade(context):
    current_date = context.current_dt.date()
    log.info('========== 调仓执行 (%s) ==========' % current_date)

    # 获取目标仓位比例（基于前一交易日）
    target_ratio = get_target_ratio(context, context.previous_date)
    total_assets = context.portfolio.portfolio_value
    target_position_value = total_assets * target_ratio

    positions = context.portfolio.positions
    hold_stocks = [s for s, p in positions.items() if p.total_amount > 0]
    candidates = g.candidate_stocks if hasattr(g, 'candidate_stocks') else []

    # ----- 第一步：卖出不在候选的持仓（若目标仓位为0，则全部清仓） -----
    for stock in hold_stocks:
        if stock not in candidates or target_ratio == 0.0:
            order_target(stock, 0)
            log.info('清仓 %s (原因: %s)' % (stock, '空仓' if target_ratio==0.0 else '不在候选'))
            if stock in g.buy_date: del g.buy_date[stock]
            if stock in g.highest_price: del g.highest_price[stock]

    # 重新计算当前持仓
    hold_stocks = [s for s, p in positions.items() if p.total_amount > 0]
    current_position_value = sum(p.total_amount * p.last_sale_price for s, p in positions.items() if p.total_amount > 0)

    # 若目标仓位为0，则不再买入
    if target_ratio == 0.0:
        return

    # ----- 第二步：若当前仓位高于目标，等比减仓 -----
    if current_position_value > target_position_value and hold_stocks:
        ratio = target_position_value / current_position_value if current_position_value > 0 else 0
        for stock in hold_stocks:
            pos = positions[stock]
            target_amount = pos.total_amount * ratio
            if target_amount < 1:
                target_amount = 0
            order_target(stock, target_amount)
            if target_amount == 0:
                log.info('【减仓】%s 因仓位控制清仓' % stock)
                if stock in g.buy_date: del g.buy_date[stock]
                if stock in g.highest_price: del g.highest_price[stock]
            else:
                log.info('【减仓】%s 持仓调整至%.0f股' % (stock, target_amount))
        # 更新持仓
        hold_stocks = [s for s, p in positions.items() if p.total_amount > 0]
        current_position_value = sum(p.total_amount * p.last_sale_price for s, p in positions.items() if p.total_amount > 0)

    # ----- 第三步：若当前仓位低于目标，买入候选 -----
    available_slots = g.stock_num - len(hold_stocks)
    if available_slots <= 0:
        return

    cash = context.portfolio.available_cash
    if cash <= 0:
        return
    max_buy_value = target_position_value - current_position_value
    if max_buy_value <= 0:
        return
    buy_cash = min(cash, max_buy_value)
    if buy_cash < 1000:
        return

    buy_list = [s for s in candidates if s not in hold_stocks][:available_slots]
    if not buy_list:
        return

    cash_per = buy_cash / len(buy_list)
    if cash_per < 1000:
        return

    for stock in buy_list:
        order_value(stock, cash_per)
        log.info('买入 %s 金额 %.2f' % (stock, cash_per))
        g.buy_date[stock] = current_date
        g.highest_price[stock] = 0.0


# ==================== 14:30 风控（不变） ====================
def risk_control(context):
    current_date = context.current_dt.date()
    positions = context.portfolio.positions

    for stock, pos in positions.items():
        if pos.total_amount == 0:
            continue

        current_price = pos.last_sale_price
        avg_cost = pos.avg_cost
        if avg_cost == 0:
            continue
        profit = (current_price / avg_cost) - 1

        if profit <= g.stop_loss:
            order_target(stock, 0)
            log.info('【止损】%s 亏损%.2f%%' % (stock, profit*100))
            if stock in g.buy_date: del g.buy_date[stock]
            if stock in g.highest_price: del g.highest_price[stock]
            continue

        if stock in g.highest_price:
            if current_price > g.highest_price[stock]:
                g.highest_price[stock] = current_price
        else:
            g.highest_price[stock] = current_price

        if profit >= g.take_profit:
            highest = g.highest_price[stock]
            retreat = (highest - current_price) / highest
            if retreat >= g.trailing_retreat:
                order_target(stock, 0)
                log.info('【动态止盈】%s 盈利%.2f%%，回撤%.2f%%' % (stock, profit*100, retreat*100))
                if stock in g.buy_date: del g.buy_date[stock]
                if stock in g.highest_price: del g.highest_price[stock]
                continue

        if stock in g.buy_date:
            hold_days = (current_date - g.buy_date[stock]).days
            if hold_days >= g.hold_days_limit and profit < g.take_profit:
                order_target(stock, 0)
                log.info('【时间平仓】%s 持仓%d天 盈利%.2f%%' % (stock, hold_days, profit*100))
                if stock in g.buy_date: del g.buy_date[stock]
                if stock in g.highest_price: del g.highest_price[stock]


# ==================== 辅助函数 ====================
def is_st_stock(stock):
    try:
        info = get_security_info(stock)
        if info is None:
            return False
        name = info.display_name
        return name and (name.startswith('ST') or name.startswith('*ST'))
    except:
        return False