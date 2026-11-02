# Clone from JoinQuant
# postId: ec05935a101c1975a308b521447555ef
# backtestId: c525875ed52a07897a1ec8de31e9bed8
# title: 关于大盘择时的问题

from jqdata import *
import numpy as np
import pandas as pd

def initialize(context):
    # -------------------- 系统参数 --------------------
    set_benchmark('000300.XSHG')
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(PriceRelatedSlippage(0.002))
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    # -------------------- 核心参数 --------------------
    g.normal_cycle = 5
    g.cycle = g.normal_cycle
    g.num_stocks = 5
    g.N = 26
    g.day_count = 0
    g.rebalance_flag = False
    g.stock_pool = []

    # ==================== 增强功能开关 ====================
    g.ENABLE_MARKET_FILTER = True   # 关闭大盘择时（不干扰你选股）
    g.ENABLE_CRASH_CYCLE = True      # 保留急跌缩短周期
    g.ENABLE_INTRADAY_STOP = True    # 保留盘中止损，但阈值放宽到-7%
    g.ENABLE_MA20_STOP = False       # 关闭跌破20日均线止损（避免冲突）
    g.ENABLE_TAKE_PROFIT = True      # 保留止盈

    # ----- 急跌参数（放宽阈值） -----
    g.index_code = '000300.XSHG'
    g.trigger_drop_pct = -0.035      # 大盘跌超-3.5%才触发（原-2%）
    g.asset_drop_pct = -0.05         # 资产跌超-5%才触发（原-3%）
    g.prev_total_value = None

    # ----- 止盈记录 -----
    g.first_buy_date = {}
    g.take_profit_state = {}
    g.sold_today = []

    # -------------------- 定时任务 --------------------
    run_daily(select_stocks, time='after_close')
    run_daily(risk_management, time='09:30')
    run_daily(take_profit_check, time='09:30')
    run_daily(execute_rebalance, time='09:31')
    run_daily(after_trading_end, time='after_close')

# ==================== 辅助函数 ====================

def is_st_stock(code):
    info = get_security_info(code)
    name = info.display_name
    return 'ST' in name or '*ST' in name

def check_crash_signal(context):
    """急跌检测（阈值已放宽）"""
    if not g.ENABLE_CRASH_CYCLE:
        g.cycle = g.normal_cycle
        return
        
    try:
        index_data = get_price(g.index_code, count=2, end_date=context.current_dt,
                               frequency='daily', fields=['close'])
        if len(index_data) >= 2:
            today_close = index_data['close'].values[-1]
            yesterday_close = index_data['close'].values[-2]
            index_change = (today_close - yesterday_close) / yesterday_close
        else:
            index_change = 0
    except:
        index_change = 0

    total_now = context.portfolio.total_value
    if g.prev_total_value is None:
        asset_change = 0
    else:
        asset_change = (total_now - g.prev_total_value) / g.prev_total_value
    g.prev_total_value = total_now

    crash = False
    if index_change <= g.trigger_drop_pct:
        log.info(f'大盘急跌：{index_change*100:.2f}% (阈值{g.trigger_drop_pct*100}%)，触发临时调仓')
        crash = True
    if asset_change <= g.asset_drop_pct:
        log.info(f'资产急跌：{asset_change*100:.2f}% (阈值{g.asset_drop_pct*100}%)，触发临时调仓')
        crash = True

    g.cycle = 1 if crash else g.normal_cycle

# ==================== 选股函数（与原策略完全一致） ====================

def select_stocks(context):
    check_crash_signal(context)

    g.day_count += 1
    if g.day_count % g.cycle != 0:
        g.rebalance_flag = False
        return

    log.info(f'========== 选股 (周期={g.cycle}) ==========')

    # 大盘择时（默认关闭）
    if g.ENABLE_MARKET_FILTER:
        try:
            price_data = get_price(g.index_code, count=20, end_date=context.current_dt,
                                   frequency='daily', fields=['close'])
            if len(price_data) >= 20:
                ma20 = np.mean(price_data['close'].values[-20:])
                if price_data['close'].values[-1] < ma20:
                    log.info('大盘在20日均线下方，空仓')
                    g.stock_pool = []
                    g.rebalance_flag = False
                    return
        except:
            pass

    # 1. 全A股，剔除科创板、ST
    all_stocks = get_all_securities(['stock']).index.tolist()
    stocks = [s for s in all_stocks if not s.startswith('688')]
    stocks = [s for s in stocks if not is_st_stock(s)]
    if not stocks:
        g.stock_pool = []
        g.rebalance_flag = False
        return

    # 2. 基本面筛选
    q = query(
        valuation.code,
        valuation.pe_ratio,
        valuation.market_cap,
        valuation.turnover_ratio
    ).filter(
        valuation.code.in_(stocks),
        valuation.pe_ratio > 0,
        valuation.market_cap >= 20,
        valuation.turnover_ratio >= 5,
        valuation.turnover_ratio <= 10
    )
    df = get_fundamentals(q, date=context.current_dt)
    if df.empty:
        g.stock_pool = []
        g.rebalance_flag = False
        return

    candidate_stocks = list(df['code'])
    log.info(f'初步筛选后剩 {len(candidate_stocks)} 只')

    # 3. 技术指标
    qualified = []
    for stock in candidate_stocks:
        try:
            price_data = get_price(stock, count=g.N + 21, end_date=context.current_dt,
                                   frequency='daily', fields=['open', 'high', 'low', 'close'])
            if len(price_data) < g.N + 20:
                continue
        except:
            continue

        close = price_data['close'].values
        if pd.isna(close[-1]) or close[-1] == 0:
            continue

        # AR
        high_open = (price_data['high'] - price_data['open']).values
        open_low = (price_data['open'] - price_data['low']).values
        sum_high_open = high_open[-g.N:].sum()
        sum_open_low = open_low[-g.N:].sum()
        ar = 100 if sum_open_low == 0 else (sum_high_open / sum_open_low * 100)

        # BR
        prev_close = price_data['close'].shift(1)
        high_prev = price_data['high'] - prev_close
        prev_low = prev_close - price_data['low']
        high_prev_valid = high_prev[1:][-g.N:].values
        prev_low_valid = prev_low[1:][-g.N:].values
        sum_high_prev = high_prev_valid.sum()
        sum_prev_low = prev_low_valid.sum()
        br = 100 if sum_prev_low == 0 else (sum_high_prev / sum_prev_low * 100)

        if not (100 <= ar <= 200 and 100 <= br <= 400):
            continue

        # 均线突破
        ma5 = np.mean(close[-5:])
        ma10 = np.mean(close[-10:])
        ma20 = np.mean(close[-20:])
        last_close = close[-1]
        if last_close <= ma20:
            continue

        break_5 = last_close > ma5
        break_10 = last_close > ma10
        score = int(break_5) + int(break_10)

        market_cap = df[df['code'] == stock]['market_cap'].iloc[0]
        qualified.append({
            'code': stock,
            'score': score,
            'market_cap': market_cap
        })

    if not qualified:
        g.stock_pool = []
        g.rebalance_flag = False
        return

    qualified_sorted = sorted(qualified, key=lambda x: (-x['score'], x['market_cap']))
    selected = [item['code'] for item in qualified_sorted[:g.num_stocks]]
    g.stock_pool = selected
    g.rebalance_flag = True
    log.info(f'选股完成：{g.stock_pool}')

# ==================== 风险控制（温和版） ====================

def risk_management(context):
    """盘中止损：仅保留亏损7%止损（更温和）"""
    if not g.ENABLE_INTRADAY_STOP:
        return
        
    g.sold_today = []
    positions = list(context.portfolio.positions.keys())
    if not positions:
        return

    for stock in positions:
        current_price = get_current_data()[stock].last_price
        if not current_price or current_price <= 0:
            continue

        avg_cost = context.portfolio.positions[stock].avg_cost
        if avg_cost <= 0:
            continue

        loss_rate = (current_price - avg_cost) / avg_cost
        # 止损阈值从-5%放宽到-7%
        if loss_rate < -0.07:
            order_target(stock, 0)
            log.info(f'止损卖出 {stock}：亏损{loss_rate*100:.2f}%')
            if stock in g.first_buy_date:
                del g.first_buy_date[stock]
            if stock in g.take_profit_state:
                del g.take_profit_state[stock]
            continue

        # 跌破20日均线止损（默认关闭）
        if g.ENABLE_MA20_STOP:
            try:
                price_data = get_price(stock, count=20, end_date=context.current_dt,
                                       frequency='daily', fields=['close'])
                if len(price_data) >= 20:
                    ma20 = np.mean(price_data['close'].values[-20:])
                    if current_price < ma20:
                        order_target(stock, 0)
                        log.info(f'止损卖出 {stock}：跌破20日均线')
                        if stock in g.first_buy_date:
                            del g.first_buy_date[stock]
                        if stock in g.take_profit_state:
                            del g.take_profit_state[stock]
            except:
                pass

# ==================== 止盈（不变） ====================

def take_profit_check(context):
    if not g.ENABLE_TAKE_PROFIT:
        return
        
    positions = list(context.portfolio.positions.keys())
    if not positions:
        return

    current_date = context.current_dt.date()

    for stock in positions:
        try:
            price_data = get_price(stock, count=1, end_date=context.current_dt,
                                   frequency='daily', fields=['close'])
            current_price = price_data['close'][-1]
        except:
            continue
        if pd.isna(current_price) or current_price == 0:
            continue

        if stock not in g.first_buy_date:
            g.first_buy_date[stock] = current_date
        if stock not in g.take_profit_state:
            g.take_profit_state[stock] = {'short': 0, 'mid': 0}

        buy_date = g.first_buy_date[stock]
        trade_days = get_trade_days(buy_date, current_date)
        holding_days = len(trade_days) - 1
        if holding_days < 0:
            holding_days = 0

        avg_cost = context.portfolio.positions[stock].avg_cost
        if avg_cost <= 0:
            continue
        profit_rate = (current_price - avg_cost) / avg_cost
        total_amount = context.portfolio.positions[stock].total_amount
        if total_amount == 0:
            continue

        # 超短线
        if 5 <= holding_days <= 10:
            state = g.take_profit_state[stock]['short']
            if state == 3:
                continue
            if profit_rate >= 0.12:
                order_target(stock, 0)
                log.info(f'止盈清仓 {stock}：超短线 {profit_rate*100:.2f}%，{holding_days}天')
                g.take_profit_state[stock]['short'] = 3
                g.sold_today.append(stock)
                del g.first_buy_date[stock]
                del g.take_profit_state[stock]
                continue
            elif profit_rate >= 0.10 and state < 2:
                sell_amount = int(total_amount * 0.30)
                if sell_amount > 0:
                    order(stock, -sell_amount)
                    log.info(f'止盈卖出 {stock}：超短线 {profit_rate*100:.2f}%，卖30%')
                    g.take_profit_state[stock]['short'] = 2
                    g.sold_today.append(stock)
            elif profit_rate >= 0.08 and state < 1:
                sell_amount = int(total_amount * 0.30)
                if sell_amount > 0:
                    order(stock, -sell_amount)
                    log.info(f'止盈卖出 {stock}：超短线 {profit_rate*100:.2f}%，卖30%')
                    g.take_profit_state[stock]['short'] = 1
                    g.sold_today.append(stock)

        # 中线
        elif 20 <= holding_days <= 40:
            state = g.take_profit_state[stock]['mid']
            if state == 3:
                continue
            if profit_rate >= 0.25:
                order_target(stock, 0)
                log.info(f'止盈清仓 {stock}：中线 {profit_rate*100:.2f}%，{holding_days}天')
                g.take_profit_state[stock]['mid'] = 3
                g.sold_today.append(stock)
                del g.first_buy_date[stock]
                del g.take_profit_state[stock]
                continue
            elif profit_rate >= 0.22 and state < 2:
                sell_amount = int(total_amount * 0.30)
                if sell_amount > 0:
                    order(stock, -sell_amount)
                    log.info(f'止盈卖出 {stock}：中线 {profit_rate*100:.2f}%，卖30%')
                    g.take_profit_state[stock]['mid'] = 2
                    g.sold_today.append(stock)
            elif profit_rate >= 0.18 and state < 1:
                sell_amount = int(total_amount * 0.30)
                if sell_amount > 0:
                    order(stock, -sell_amount)
                    log.info(f'止盈卖出 {stock}：中线 {profit_rate*100:.2f}%，卖30%')
                    g.take_profit_state[stock]['mid'] = 1
                    g.sold_today.append(stock)

# ==================== 调仓执行 ====================

def execute_rebalance(context):
    if not g.rebalance_flag or not g.stock_pool:
        return

    log.info('========== 调仓 ==========')
    total_assets = context.portfolio.total_value
    target_value = total_assets / len(g.stock_pool)

    for stock in list(context.portfolio.positions.keys()):
        if stock not in g.stock_pool:
            order_target(stock, 0)
            log.info(f'卖出 {stock}（不在池中）')
            if stock in g.first_buy_date:
                del g.first_buy_date[stock]
            if stock in g.take_profit_state:
                del g.take_profit_state[stock]

    for stock in g.stock_pool:
        if stock in g.sold_today:
            continue

        current_price = get_current_data()[stock].last_price
        if not current_price or current_price <= 0:
            continue

        cur_position = context.portfolio.positions[stock].total_amount
        cur_value = cur_position * current_price

        if cur_position == 0:
            g.first_buy_date[stock] = context.current_dt.date()
            g.take_profit_state[stock] = {'short': 0, 'mid': 0}

        if cur_value < target_value:
            buy_value = target_value - cur_value
            order_value(stock, buy_value)
            log.info(f'买入 {stock}，金额 {buy_value:.2f}')

    g.day_count = 0
    g.rebalance_flag = False

def after_trading_end(context):
    log.info(f'总资产: {context.portfolio.total_value:.2f}')