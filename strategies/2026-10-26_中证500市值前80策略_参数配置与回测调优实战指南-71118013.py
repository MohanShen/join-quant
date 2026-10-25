# Clone from JoinQuant
# postId: 71118013a574ee1c45dd1f8fb5934b90
# backtestId: 533ab5493ec17da9467aa7c227ab2e14
# title: 中证500市值前80策略：参数配置与回测调优实战指南

# 克隆自聚宽文章：https://www.joinquant.com/post/72643
# 标题：PT量化实战：一个策略只用10%资金交易，怎么做？
# 作者：开心etf

# 克隆自聚宽文章：https://www.joinquant.com/post/72421
# 标题：一个很稳定的市值策略，请大佬提出改进意见
# 作者：zjj2026888

# -*- coding: utf-8 -*-
# 策略名称：中证500市值前80策略_高资金利用率版_修正版
# 优化点：修复股票池无数据、买入信号过严等问题，确保选股与买入正常执行
# 【修复】使用前一交易日获取价格，避免开盘前取不到当日收盘价
# 【追踪止损】使用过去20日最高价（与原代码一致），而非持仓以来最高价
# 【修复】增加总仓位控制，避免超限
# 【修复】资金管理优化，提高利用率同时控制风险
# 【修复】其他细节：交易日获取、涨停检查、冷却清理等

from jqdata import *
import numpy as np
import pandas as pd
import datetime

def initialize(context):
    # ========== 基础设置 ==========
    set_benchmark('000905.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                             open_commission=0.0003, close_commission=0.0003,
                             min_commission=5), type='stock')
    set_slippage(PriceRelatedSlippage(0.002))

    # ========== 策略参数 ==========
    g.security = []
    g.index_stocks = []
    g.max_price = 100.0
    g.min_price = 3.0

    g.max_positions = 5                     # 最大持仓数
    g.position_ratio = 0.3                # 单只股票目标仓位（占总资产比例）
    g.max_total_position_ratio = 0.95      # 总仓位上限（95%）

    g.initial_stop_loss = 0.08
    # 追踪止损：从过去20日最高点回撤5%触发（与原代码一致）
    g.trailing_stop_retrace = 0.05
    g.max_holding_days = 30
    g.trailing_stop_delay_days = 1

    # 10日均线止损
    g.ma10_break_ratio = 0.98

    # 波动率过滤（放宽阈值，避免过滤太多）
    g.atr_period = 20
    g.atr_threshold = 0.08

    # 黑名单（初始止损后禁止买入天数）
    g.blacklist = {}
    g.blacklist_days = 10

    # 冷却期
    g.cooldown_days = 10
    g.trade_cooldown = {}

    # 流动性过滤（从1亿降低到3000万，适配中证500中小市值）
    g.min_avg_volume_amount = 30_000_000

    # 交易限制
    g.max_buy_per_day = 3
    g.max_trades_per_month = 2
    g.monthly_trade_count = {}

    # 状态变量
    g.holding_days = {}
    g.buy_count_today = 0
    # 注意：highest_prices 变量在原代码中用于记录持仓以来最高价，但追踪止损已改回20日最高价，此变量不再使用（保留但无实际作用）
    g.highest_prices = {}
    g.pending_sell_at_open = set()

    # ========== 定时运行 ==========
    run_daily(update_stock_pool, time='09:00')
    run_daily(sell_check_intraday, time='09:35')
    run_daily(sell_check_intraday, time='10:05')
    run_daily(sell_check_intraday, time='10:35')
    run_daily(sell_check_intraday, time='11:05')
    run_daily(sell_check_intraday, time='13:35')
    run_daily(sell_check_intraday, time='14:05')
    run_daily(sell_check_intraday, time='14:35')
    run_daily(close_check_sell, time='14:50')
    run_daily(buy_check, time='10:00')
    run_daily(process_pending_sells, time='09:25')
    run_daily(after_market_close, time='after_close')
    run_monthly(update_index_stocks, 1, time='09:00')
    run_monthly(reset_monthly_trade_count, 1, time='09:00')

    # 初始化：首次更新股票池
    update_index_stocks(context)
    try:
        update_stock_pool(context)
    except:
        pass

    log.info("策略初始化完成（股票池前80，每日买入上限3只，评分阈值7分，追踪止损基于前一日20日最高价，冷却期20天）")


# ==================== 股票池相关（前80名，修复数据获取） ====================
def update_index_stocks(context):
    g.index_stocks = get_index_stocks('000905.XSHG', date=context.current_dt)
    log.info(f"更新中证500成分股，数量：{len(g.index_stocks)}")
    update_stock_pool(context)

def get_prev_trade_date(context):
    """获取上一个交易日（确保是交易日）"""
    trade_days = get_trade_days(end_date=context.current_dt, count=2)
    return trade_days[0] if len(trade_days) > 0 else None

def update_stock_pool(context):
    """修复：使用上一个交易日获取市值和价格，避免非交易日问题"""
    try:
        if not g.index_stocks:
            g.index_stocks = get_index_stocks('000905.XSHG', date=context.current_dt)
        stocks_to_check = g.index_stocks
        market_caps = {}
        valid_stocks = []

        prev_date = get_prev_trade_date(context)
        if prev_date is None:
            log.warn("无法获取上一个交易日，使用当前日期")
            prev_date = context.current_dt.date()

        for stock in stocks_to_check:
            try:
                price_data = get_price(stock, count=1, end_date=prev_date,
                                       frequency='daily', fields=['close'])
                if price_data is None or price_data.empty:
                    continue
                current_price = price_data['close'].iloc[-1]
                if not (g.min_price <= current_price <= g.max_price):
                    continue

                q = query(valuation.code, valuation.market_cap).filter(valuation.code == stock)
                df = get_fundamentals(q, date=prev_date)
                if df.empty:
                    df = get_fundamentals(q, date=context.current_dt)
                if df.empty:
                    continue
                market_cap = df['market_cap'].iloc[0]
                market_caps[stock] = market_cap
                valid_stocks.append(stock)
            except Exception as e:
                continue

        if market_caps:
            valid_stocks.sort(key=lambda x: market_caps.get(x, 0), reverse=True)
            g.security = valid_stocks[:80]
            log.info(f"股票池更新完成，共{len(g.security)}只股票（前80），市值区间：{market_caps.get(g.security[0],0):.0f}~{market_caps.get(g.security[-1],0):.0f}")
        else:
            log.warn("市值数据获取失败，使用中证500前80只成分股作为备选池")
            g.security = g.index_stocks[:80] if g.index_stocks else []
            if not g.security:
                g.security = get_index_stocks('000300.XSHG')[:50]
                log.warn("中证500无数据，启用沪深300前50只备选")
            log.info(f"应急股票池数量：{len(g.security)}")

    except Exception as e:
        log.error(f"更新股票池失败：{e}")
        if g.index_stocks:
            g.security = g.index_stocks[:30]
        else:
            g.security = get_index_stocks('000300.XSHG')[:30]
        log.info(f"应急股票池数量：{len(g.security)}")


# ==================== 卖出信号（追踪止损改回20日最高价） ====================
def sell_check_intraday(context):
    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]
        if position.total_amount == 0:
            continue
        current_data = get_current_data()
        if stock in current_data:
            current_price = current_data[stock].last_price
        else:
            price_data = get_price(stock, count=1, end_date=context.current_dt, frequency='daily', fields=['close'])
            if price_data.empty:
                continue
            current_price = price_data['close'].iloc[-1]

        cost = position.avg_cost
        if cost <= 0:
            continue
        profit_ratio = (current_price - cost) / cost

        # 初始止损
        if profit_ratio <= -g.initial_stop_loss:
            log.info(f"【初始止损】{stock} 亏损{profit_ratio*100:.2f}%")
            sell_stock(context, stock, is_initial_stop=True)
            continue

        # 追踪止损（需要延迟启用，基于前一交易日的过去20日最高价，避免当日盘中新高抬高阈值）
        holding_days = g.holding_days.get(stock, 0)
        if holding_days >= g.trailing_stop_delay_days:
            # 使用前一交易日，避免包含当日未完成K线的最高价
            prev_date = get_prev_trade_date(context)
            if prev_date is None:
                continue
            high_data = get_price(stock, count=20, end_date=prev_date,
                                  frequency='daily', fields=['high'])
            if high_data.empty or len(high_data) < 20:
                continue
            highest_20 = high_data['high'].max()
            if check_trailing_stop(stock, current_price, cost, highest_20):
                sell_stock(context, stock)


def check_trailing_stop(stock, current_price, cost, highest_20):
    """使用过去20日最高价计算回撤，若超过阈值则触发止损（与原代码逻辑一致）"""
    if highest_20 <= 0:
        return False
    profit_ratio = (current_price - cost) / cost if cost > 0 else 0
    retrace = (highest_20 - current_price) / highest_20
    if retrace >= g.trailing_stop_retrace:
        log.info(f"【追踪止损】{stock} 浮盈{profit_ratio*100:.1f}% 从20日最高{highest_20:.2f}回撤{retrace*100:.2f}% ≥ {g.trailing_stop_retrace*100:.0f}%")
        return True
    return False


def close_check_sell(context):
    current_pool = set(g.security)
    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]
        if position.total_amount == 0:
            continue

        days = g.holding_days.get(stock, 0)
        if days >= g.max_holding_days:
            log.info(f"【时间止损】{stock} 持仓{days}天")
            sell_stock(context, stock)
            continue

        close_data = get_price(stock, count=11, end_date=context.current_dt, frequency='daily', fields=['close'])
        if len(close_data) >= 11:
            current_close = close_data['close'].iloc[-1]
            ma10 = close_data['close'].rolling(10).mean().iloc[-1]
            if current_close < ma10 * g.ma10_break_ratio:
                log.info(f"【均线止损】{stock} 收盘{current_close:.2f}跌破MA10{ma10:.2f}的98%")
                sell_stock(context, stock)
                continue

        if stock not in current_pool:
            score = check_buy_signal(stock, context)
            if score < 7:
                log.info(f"【池外调仓】{stock} 不在最新前80股票池，且评分{score:.1f}<7，卖出")
                sell_stock(context, stock)


def sell_stock(context, stock, is_initial_stop=False):
    try:
        if stock not in context.portfolio.positions:
            return False
        pos = context.portfolio.positions[stock]
        if pos.total_amount == 0:
            return False

        current_data = get_current_data()
        if stock in current_data and current_data[stock].low_limit > 0:
            current_price = current_data[stock].last_price
            if current_price <= current_data[stock].low_limit * 1.001:
                g.pending_sell_at_open.add(stock)
                stock_name = get_security_info(stock).display_name
                log.warn(f"【跌停锁仓】{stock_name} 触及跌停，加入次日集合竞价卖出队列")
                return False

        order_target(stock, 0)
        if stock in g.holding_days:
            del g.holding_days[stock]
        if stock in g.highest_prices:
            del g.highest_prices[stock]
        g.trade_cooldown[stock] = context.current_dt.date()

        if is_initial_stop:
            expire_date = context.current_dt.date() + datetime.timedelta(days=g.blacklist_days)
            g.blacklist[stock] = expire_date
            log.info(f"【黑名单】{stock} 因初始止损，{g.blacklist_days}天内禁止买入")

        stock_name = get_security_info(stock).display_name
        log.info(f"【卖出】{stock_name} 成本{pos.avg_cost:.2f} 现价{pos.price:.2f} 盈利{(pos.price/pos.avg_cost-1)*100:.2f}%")
        return True
    except Exception as e:
        log.error(f"卖出{stock}异常：{e}")
        return False


def process_pending_sells(context):
    if not g.pending_sell_at_open:
        return
    for stock in list(g.pending_sell_at_open):
        if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
            order_target(stock, 0)
            stock_name = get_security_info(stock).display_name
            log.info(f"【跌停延后卖出】{stock_name} 在开盘集合竞价卖出")
        g.pending_sell_at_open.discard(stock)


# ==================== 买入相关（选股因子与源文件一致） ====================
def reset_monthly_trade_count(context):
    g.monthly_trade_count = {}
    log.info("已重置月度交易计数")

def buy_check(context):
    g.buy_count_today = 0

    total_value = context.portfolio.total_value
    current_position_value = sum(pos.total_amount * pos.price for pos in context.portfolio.positions.values() if pos.total_amount > 0)
    current_total_ratio = current_position_value / total_value if total_value > 0 else 0
    if current_total_ratio >= g.max_total_position_ratio:
        log.info(f"总仓位已达{current_total_ratio*100:.1f}%，超过上限{g.max_total_position_ratio*100:.0f}%，停止买入")
        return

    current_holdings = sum(1 for pos in context.portfolio.positions.values() if pos.total_amount > 0)
    if current_holdings >= g.max_positions:
        return
    available_slots = g.max_positions - current_holdings
    if available_slots <= 0:
        return

    buy_candidates = []
    for stock in g.security:
        if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
            continue
        if stock in g.trade_cooldown:
            days_since = (context.current_dt.date() - g.trade_cooldown[stock]).days
            if days_since < g.cooldown_days:
                continue
        if stock in g.blacklist and context.current_dt.date() < g.blacklist[stock]:
            continue
        if g.monthly_trade_count.get(stock, 0) >= g.max_trades_per_month:
            continue
        if not check_liquidity(stock, context):
            continue
        score = check_buy_signal(stock, context)
        if score >= 7:
            buy_candidates.append((stock, score))

    buy_candidates.sort(key=lambda x: x[1], reverse=True)
    buy_limit = min(available_slots, g.max_buy_per_day)
    bought = 0
    for i in range(min(buy_limit, len(buy_candidates))):
        stock, score = buy_candidates[i]
        if buy_stock(context, stock):
            g.buy_count_today += 1
            bought += 1
            log.info(f"买入股票：{stock}，评分：{score:.2f}，今日已买入{g.buy_count_today}只")
            if g.buy_count_today >= g.max_buy_per_day:
                break
    if bought > 0:
        log.info(f"今日共买入{bought}只股票")

def check_liquidity(stock, context):
    try:
        df = get_price(stock, count=20, end_date=context.current_dt, frequency='daily', fields=['money'])
        if df.empty or len(df) < 20:
            return False
        avg_amount = df['money'].mean()
        return avg_amount >= g.min_avg_volume_amount
    except:
        return False

def check_buy_signal(stock, context):
    """【完全保留源文件逻辑】评分因子和计算方法不变"""
    try:
        data = get_price(stock, count=30, end_date=context.current_dt,
                         frequency='daily', fields=['close', 'volume', 'high', 'low'])
        if len(data) < 20:
            return 0
        current_close = data['close'].iloc[-1]
        ma10 = data['close'].rolling(10).mean().iloc[-1]
        ma20 = data['close'].rolling(20).mean().iloc[-1]

        if current_close < ma10 * 0.98:
            return 0
        if current_close < ma20 * 0.98:
            return 0

        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift())
        low_close = abs(data['low'] - data['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(g.atr_period).mean().iloc[-1]
        if atr / current_close > g.atr_threshold:
            return 0

        score = 0
        # 成交量放大（+2）
        current_vol = data['volume'].iloc[-1]
        avg_vol = data['volume'].rolling(10).mean().iloc[-1]
        if current_vol > avg_vol * 1.2:
            score += 2
        # 突破近期高点（+2）
        recent_high = data['close'].iloc[-10:-1].max()
        if current_close > recent_high:
            score += 2
        # 最近3天至少2天上涨（+2）
        up_days = 0
        for i in range(1, 4):
            if data['close'].iloc[-i] > data['close'].iloc[-i-1]:
                up_days += 1
        if up_days >= 2:
            score += 2
        # RSI（30-70区间加分）
        delta = data['close'].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        if loss.iloc[-1] == 0:
            rsi = 100
        else:
            rsi = 100 - 100 / (1 + rs.iloc[-1])
        if 30 < rsi < 70:
            score += 1
        # MACD金叉（+1）
        exp12 = data['close'].ewm(span=12, adjust=False).mean()
        exp26 = data['close'].ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal = macd.ewm(span=9, adjust=False).mean()
        if macd.iloc[-1] > signal.iloc[-1]:
            score += 1
        return score
    except Exception as e:
        log.error(f"评分异常{stock}:{e}")
        return 0

def buy_stock(context, stock):
    try:
        current_data = get_current_data()
        if stock in current_data and current_data[stock].paused:
            log.warn(f"{stock} 停牌，放弃买入")
            return False
        # 检查涨停
        if stock in current_data and current_data[stock].high_limit is not None:
            if current_data[stock].last_price >= current_data[stock].high_limit * 0.99:
                log.warn(f"{stock} 已涨停或接近涨停，放弃买入")
                return False

        if stock in current_data and current_data[stock].last_price is not None:
            current_price = current_data[stock].last_price
        else:
            price_data = get_price(stock, count=1, end_date=context.current_dt, frequency='daily', fields=['close'])
            if price_data.empty:
                return False
            current_price = price_data['close'].iloc[-1]

        net_asset = context.portfolio.total_value
        cash = context.portfolio.available_cash
        current_position_value = sum(pos.total_amount * pos.price for pos in context.portfolio.positions.values() if pos.total_amount > 0)
        remaining_ratio = g.max_total_position_ratio - (current_position_value / net_asset if net_asset > 0 else 0)
        if remaining_ratio <= 0:
            log.info("总仓位已达上限，放弃买入")
            return False

        target_value_by_ratio = net_asset * g.position_ratio
        max_allowed_by_remaining = net_asset * remaining_ratio
        target_value = min(target_value_by_ratio, max_allowed_by_remaining, cash * 0.8)
        if target_value < max(10000, net_asset * 0.01):
            log.info(f"买入金额{target_value:.0f}过小，放弃买入{stock}")
            return False

        amount = int(target_value / current_price / 100) * 100
        if amount < 100:
            amount = 100
        order_result = order(stock, amount)
        if order_result is not None:
            g.holding_days[stock] = 0
            # 注意：追踪止损已改为20日最高价，此处不再需要记录持仓以来最高价，但保留变量以防其他逻辑依赖
            g.highest_prices[stock] = current_price  # 仅作占位，实际不使用
            g.monthly_trade_count[stock] = g.monthly_trade_count.get(stock, 0) + 1
            stock_name = get_security_info(stock).display_name
            log.info(f"【买入】{stock_name} 价格{current_price:.2f} 数量{amount} 仓位{amount*current_price/net_asset*100:.2f}%")
            return True
        else:
            return False
    except Exception as e:
        log.error(f"买入{stock}异常：{e}")
        return False


# ==================== 收盘后维护 ====================
def update_holding_days(context):
    for stock in list(context.portfolio.positions.keys()):
        if context.portfolio.positions[stock].total_amount > 0:
            g.holding_days[stock] = g.holding_days.get(stock, 0) + 1

def after_market_close(context):
    update_holding_days(context)

    current_date = context.current_dt.date()
    to_remove_cooldown = [stock for stock, sell_date in g.trade_cooldown.items() if (current_date - sell_date).days > g.cooldown_days]
    for stock in to_remove_cooldown:
        del g.trade_cooldown[stock]

    expired = [stock for stock, expire_date in g.blacklist.items() if current_date >= expire_date]
    for stock in expired:
        del g.blacklist[stock]

    total_val = context.portfolio.total_value
    cash_val = context.portfolio.available_cash
    holdings = sum(1 for pos in context.portfolio.positions.values() if pos.total_amount > 0)
    log.info(f"收盘: 总资产{total_val:.2f} 现金{cash_val:.2f} 持仓{holdings}只")

    if holdings > 0:
        log.info("=" * 70)
        log.info("【持仓明细】")
        for stock, pos in context.portfolio.positions.items():
            if pos.total_amount == 0:
                continue
            try:
                price_data = get_price(stock, count=1, end_date=context.current_dt, frequency='daily', fields=['close'])
                if price_data.empty:
                    continue
                current_price = price_data['close'].iloc[-1]
                cost = pos.avg_cost
                profit_ratio = (current_price - cost) / cost * 100 if cost > 0 else 0
                hold_days = g.holding_days.get(stock, 0)
                amount = pos.total_amount
                stock_name = get_security_info(stock).display_name
                log.info(f"  {stock_name}({stock}) | 持股:{amount} | 成本:{cost:.2f} | 现价:{current_price:.2f} | 盈亏:{profit_ratio:+.2f}% | 持仓天数:{hold_days}")
            except Exception as e:
                log.warn(f"获取{stock}持仓信息失败: {e}")
        log.info("=" * 70)

def analyze(context, perf):
    print("策略回测完成（股票池前80，每日买入上限3只，评分阈值7分，流动性门槛降至3000万，追踪止损基于前一日20日最高价，冷却期20天）")