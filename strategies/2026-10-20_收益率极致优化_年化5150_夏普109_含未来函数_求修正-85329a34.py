# Clone from JoinQuant
# postId: 85329a34c66d23c318425f9d7cd9c577
# backtestId: 54734d5a5063d6c8e6da036d44e955d9
# title: 收益率极致优化！年化5150%夏普109（含未来函数，求修正

# 克隆自聚宽文章：https://www.joinquant.com/post/570
# 标题：【简单的多均线择时策略】那个天台排队的孩子，我给你讲个故事
# 作者：陈小米。

from jqdata import *
import talib
import numpy as np
import pandas as pd

def initialize(context):
    # ==================== 基础设置 ====================
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('order_volume_ratio', 1)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                             open_commission=0.00025, close_commission=0.00025,
                             min_commission=5), type='stock')
    set_slippage(FixedSlippage(0.1))

    # ==================== 策略参数 ====================
    g.stock_pool_index = '000300.XSHG'
    g.update_pool_freq = 20
    g.max_hold_count = 1
    g.min_price = 8
    g.min_avg_volume = 20e6
    g.base_max_position = 0.90
    g.weak_max_position = 0.50
    g.max_single_position = 0.90

    g.sar_acc = 0.02
    g.sar_max = 0.2
    g.macd_fast = 12
    g.macd_slow = 26
    g.macd_signal = 9
    g.stop_profit = 0.10
    g.stop_loss = 0.05
    g.data_count = 100

    # ==================== 全局变量 ====================
    g.last_pool_update = None
    g.stock_pool = []
    g.current_max_position = g.base_max_position

    # ==================== 定时任务 ====================
    run_daily(check_market_regime, time='9:32')
    run_daily(trade_logic, time='9:35')
    run_daily(after_market_close, time='15:10')

    log.info('══════════════════════════════════════')
    log.info('  SAR+MACD 趋势跟踪策略 初始化完成')
    log.info(f'  基准: {g.stock_pool_index} | 持股上限: {g.max_hold_count}只')
    log.info(f'  仓位: 强势{g.base_max_position:.0%} / 弱势{g.weak_max_position:.0%}')
    log.info(f'  止盈: {g.stop_profit:.0%} | 止损: {g.stop_loss:.0%}')
    log.info('══════════════════════════════════════')

# ==================== 大盘择时 ====================
def check_market_regime(context):
    current_date = context.current_dt.date()
    try:
        df = get_price(g.stock_pool_index, end_date=current_date,
                       count=21, frequency='daily', fields=['close'])
        if df is None or len(df) < 20:
            g.current_max_position = g.base_max_position
            return
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        current_close = df['close'].iloc[-1]
        if current_close > ma20:
            g.current_max_position = g.base_max_position
            log.info(f'[大盘] 强势 | 指数 {current_close:.2f} > MA20 {ma20:.2f} | 仓位上限 {g.base_max_position:.0%}')
        else:
            g.current_max_position = g.weak_max_position
            log.info(f'[大盘] 弱势 | 指数 {current_close:.2f} ≤ MA20 {ma20:.2f} | 仓位上限 {g.weak_max_position:.0%}')
    except Exception as e:
        log.error(f'[大盘] 择时异常: {e}')
        g.current_max_position = g.base_max_position

# ==================== 主交易逻辑 ====================
def trade_logic(context):
    current_date = context.current_dt.date()
    current_data = get_current_data()

    stock_pool = get_current_stock_pool(context, current_date, current_data)
    if not stock_pool:
        log.info('[选股] 股票池为空，跳过交易')
        return

    target_list = select_by_sar_macd(context, stock_pool)
    log.info(f'[选股] 目标持仓: {target_list if target_list else "无"}')

    adjust_positions(context, target_list, current_data)

def select_by_sar_macd(context, stock_pool):
    qualified = []
    for stock in stock_pool:
        try:
            df = get_price(stock, end_date=context.current_dt.date(),
                           count=g.data_count, frequency='daily',
                           fields=['high', 'low', 'close'], fq='post')
            if df is None or len(df) < 30:
                continue
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values

            sar = talib.SAR(high, low, acceleration=g.sar_acc, maximum=g.sar_max)
            macd, signal, hist = talib.MACD(close,
                                           fastperiod=g.macd_fast,
                                           slowperiod=g.macd_slow,
                                           signalperiod=g.macd_signal)
            if np.isnan(sar[-1]) or np.isnan(macd[-1]) or np.isnan(signal[-1]):
                continue

            if close[-1] > sar[-1] and macd[-2] < signal[-2] and macd[-1] > signal[-1]:
                qualified.append(stock)
        except:
            continue

    if qualified:
        rets = {}
        for s in qualified:
            try:
                df_ret = get_price(s, end_date=context.current_dt.date(),
                                   count=6, frequency='daily', fields=['close'], fq='post')
                if len(df_ret) >= 6:
                    rets[s] = (df_ret['close'].iloc[-1] / df_ret['close'].iloc[-6] - 1)
                else:
                    rets[s] = 0
            except:
                rets[s] = 0
        qualified = sorted(qualified, key=lambda x: rets.get(x, 0), reverse=True)
    return qualified[:g.max_hold_count]

def adjust_positions(context, target_list, current_data):
    total_value = context.portfolio.total_value
    positions = context.portfolio.positions

    sell_count = 0
    buy_count = 0

    # ------------------- 卖出逻辑 -------------------
    for stock in list(positions.keys()):
        pos = positions[stock]
        if pos.total_amount == 0:
            continue
        need_sell = False
        reason = ''

        if stock not in target_list:
            need_sell = True
            reason = '调出目标池'

        if not need_sell:
            cost = pos.avg_cost
            price = current_data[stock].day_open
            if np.isnan(price) or price <= 0:
                price = current_data[stock].last_price
            pnl_pct = (price - cost) / cost
            if pnl_pct >= g.stop_profit:
                need_sell = True
                reason = f'止盈({pnl_pct:.2%})'
            elif pnl_pct <= -g.stop_loss:
                need_sell = True
                reason = f'止损({pnl_pct:.2%})'

        if not need_sell and can_trade(stock, current_data):
            try:
                df = get_price(stock, end_date=context.current_dt.date(),
                               count=g.data_count, frequency='daily',
                               fields=['high', 'low', 'close'], fq='post')
                if len(df) >= 30:
                    high = df['high'].values
                    low = df['low'].values
                    close = df['close'].values
                    sar = talib.SAR(high, low, acceleration=g.sar_acc, maximum=g.sar_max)
                    macd, signal, hist = talib.MACD(close,
                                                   fastperiod=g.macd_fast,
                                                   slowperiod=g.macd_slow,
                                                   signalperiod=g.macd_signal)
                    if close[-1] < sar[-1]:
                        need_sell = True
                        reason = 'SAR转跌'
                    elif macd[-2] > signal[-2] and macd[-1] < signal[-1]:
                        need_sell = True
                        reason = 'MACD死叉'
            except Exception as e:
                log.debug(f'技术出场判断异常 {stock}: {e}')

        if need_sell:
            sell_price = current_data[stock].day_open
            if np.isnan(sell_price) or sell_price <= 0:
                sell_price = current_data[stock].last_price
            order_target(stock, 0)
            # 计算盈亏
            cost = pos.avg_cost
            pnl = (sell_price - cost) / cost if cost > 0 else 0
            log.info(f'[卖出] {stock} | {pos.total_amount}股 | 成本{cost:.2f} | 卖出价{sell_price:.2f} | 盈亏{pnl:.2%} | 原因:{reason}')
            sell_count += 1

    # ------------------- 买入逻辑 -------------------
    current_position_value = sum([p.value for p in positions.values() if p.total_amount > 0])
    max_allowed_value = total_value * g.current_max_position
    if current_position_value >= max_allowed_value:
        if target_list:
            log.info(f'[仓位] 已达上限 {g.current_max_position:.0%}，不买入')
        return

    stocks_to_buy = [s for s in target_list if s not in positions or positions[s].total_amount == 0]
    if not stocks_to_buy:
        return

    available_cash = context.portfolio.available_cash
    num_to_buy = len(stocks_to_buy)
    ideal_per_stock = min(available_cash / num_to_buy, total_value * g.max_single_position)

    for stock in stocks_to_buy:
        if not can_trade(stock, current_data):
            continue
        price = current_data[stock].day_open
        if np.isnan(price) or price <= 0:
            continue

        # 计算可买股数（100股整数倍）
        max_shares = int(ideal_per_stock // price // 100) * 100
        # 受可用资金限制
        max_by_cash = int(available_cash // price // 100) * 100
        shares = min(max_shares, max_by_cash)

        if shares < 100:
            continue

        order(stock, shares)
        cost_value = shares * price
        log.info(f'[买入] {stock} | {shares}股 | 价格{price:.2f} | 金额{cost_value:.2f} | 占总资产{cost_value/total_value:.2%}')
        available_cash -= cost_value
        buy_count += 1

    if sell_count > 0 or buy_count > 0:
        log.info(f'[调仓] 卖出 {sell_count} 只 / 买入 {buy_count} 只')

def can_trade(stock, current_data):
    if current_data[stock].paused:
        return False
    if current_data[stock].high_limit <= current_data[stock].day_open:
        return False
    if current_data[stock].low_limit >= current_data[stock].day_open:
        return False
    return True

# ==================== 股票池管理 ====================
def get_current_stock_pool(context, current_date, current_data):
    if g.last_pool_update is None:
        days_passed = 999
    else:
        days_passed = (current_date - g.last_pool_update).days

    if days_passed >= g.update_pool_freq:
        log.info(f'[股票池] 更新基准: {g.stock_pool_index}')
        try:
            pool = get_index_stocks(g.stock_pool_index, date=current_date)
            st_df = get_extras('is_st', pool, start_date=current_date, end_date=current_date, df=True)
            filtered = []
            skip_300_688 = 0
            for s in pool:
                # 过滤创业板和科创板
                if s.startswith('300') or s.startswith('688'):
                    skip_300_688 += 1
                    continue
                if current_data[s].paused:
                    continue
                if s in st_df.columns and st_df.iloc[0][s]:
                    continue
                try:
                    sec_info = get_security_info(s)
                    days_listed = len(get_trade_days(sec_info.start_date, current_date))
                    if days_listed < 250:
                        continue
                except:
                    pass
                if current_data[s].day_open < g.min_price:
                    continue
                try:
                    df_vol = get_price(s, end_date=current_date, count=20, frequency='daily',
                                       fields=['volume', 'close'], skip_paused=False, fq=None)
                    if df_vol is not None and len(df_vol) >= 10:
                        df_vol['money'] = df_vol['volume'] * df_vol['close']
                        if df_vol['money'].mean() < g.min_avg_volume:
                            continue
                except:
                    pass
                filtered.append(s)
            g.stock_pool = filtered
            g.last_pool_update = current_date
            log.info(f'[股票池] 原始 {len(pool)}只 → 过滤后 {len(filtered)}只 (已剔除创业板/科创板 {skip_300_688}只)')
        except Exception as e:
            log.error(f'[股票池] 更新失败: {e}')
            if not hasattr(g, 'stock_pool'):
                g.stock_pool = []
    return g.stock_pool

# ==================== 盘后记录 ====================
def after_market_close(context):
    total_value = context.portfolio.total_value
    position_value = context.portfolio.positions_value
    position_ratio = position_value / total_value if total_value > 0 else 0
    log.info(f'[收盘] 总资产: {total_value:,.2f} | 持仓市值: {position_value:,.2f} | 仓位: {position_ratio:.2%}')

    positions = context.portfolio.positions
    hold_list = [s for s in positions if positions[s].total_amount > 0]
    if hold_list:
        detail = []
        for s in hold_list:
            p = positions[s]
            cost = p.avg_cost
            price = p.price
            pnl = (price - cost) / cost if cost > 0 else 0
            detail.append(f'{s}({p.total_amount}股, 成本{cost:.2f}, 现价{price:.2f}, 盈亏{pnl:.2%})')
        log.info(f'[持仓] {"; ".join(detail)}')
    else:
        log.info('[持仓] 空仓')