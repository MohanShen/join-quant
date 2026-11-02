# Clone from JoinQuant
# postId: 3d393e39d2396dc644341a6323a12c6c
# backtestId: c493edacec1c8aedd5d0f95063765ec3
# title: 【聚宽求助】策略回测正常但虚拟盘无信号，求大佬指点排查方向

# -*- coding: utf-8 -*-
"""
动量+ATR策略 - 完整修复优化版
修复内容：
1. 补全 calculate_momentum_score 函数
2. 补全 calculate_atr 函数
3. 补全 is_suspended 函数
4. 修复 check_market_environment 评分逻辑
5. open_tax=0（买入无印花税）
6. 修复 position.quantity -> position.total_amount（聚宽API）
7. 修复所有 f-string 语法错误（嵌套引号问题）
8. 【P0修复】买入日志改用实际成交价（捕获order.price）
9. 【P1优化】市场评分恶化时清仓所有持仓
10.【P1优化】最大持有天数限制（默认20天）
11.【P2清理】删除 context.previous_date 死代码
12.【P2清理】用聚宽内置 is_st_stock() 替换自定义函数
13.【V2】选股因子优化（2026-05-17）：
    - 评分公式分辨率提升：趋势×1.75(上限0.35) 动量×3(上限0.25) 量能×0.25(上限0.20)
    - 新增年线位置>80%硬过滤
    - 新增低位加分（位置<40%奖励）
14.【V2.1】市场环境优化（2026-05-17）：
    - 从"3指数MA趋势"改为"沪深300+中证500成分股动量情绪"
    - 4档评分对应4档仓位（0/0.33/0.67/1.0）
    - 思路来源：DKX全市场情绪控仓策略
15.【V2.2】市场情绪指标优化（2026-05-17）：
    - 从"20日涨幅>5%"改为"动量加速度"判断
    - 强多头=近20日涨>0 AND 近5日涨>2%（中短期同步）
    - 解决先大跌后反弹也被算作多头的滞后问题
16.【未来函数清理】（2026-05-17）：
    - 【P0修复】14:55卖出检查：get_price(收盘价) → get_current_data(实时价)
    - 09:00选股：end_date=today → end_date=context.current_dt
    - 09:00停牌判断：end_date=today → end_date=context.current_dt
"""

import numpy as np
from datetime import datetime, timedelta

# ========== 初始化 ==========
def initialize(context):
    context.stock_num = 5
    context.market_score_threshold = 0.3
    context.momentum_threshold = 0.3
    context.atr_multiplier = 2.0
    context.take_profit_multiplier = 3.0
    context.MAX_POSITION_RATIO = 0.2
    context.MAX_HOLD_DAYS = 20  # 最大持有天数

    context.SLIPPAGE = 0.001
    context.OPEN_COMMISSION = 0.0003
    context.CLOSE_COMMISSION = 0.0003
    context.OPEN_TAX = 0.0
    context.CLOSE_TAX = 0.001

    # context.previous_date 已删除（死代码）
    g.buy_candidates = []
    g.positions_info = {}
    g.today_bought = set()  # 记录今日新买入的股票，用于日志校正

    run_daily(before_market_open, time='09:00')
    run_daily(open_time_action, time='09:30')
    run_daily(before_close_action, time='14:55')
    run_daily(after_market_close, time='15:05')


# ========== 盘前选股 ==========
def before_market_open(context):
    today = context.current_dt.date()
    # context.previous_date 已删除（死代码，从未被读取）

    # 1. 市场环境检查
    market_score = check_market_environment(context)
    log.info('市场环境评分: %.2f' % market_score)

    # 【P1优化】市场评分低于阈值时，清仓所有已有持仓
    if market_score < context.market_score_threshold:
        log.info('市场环境评分低于阈值，今日清仓')
        for stock in list(context.portfolio.positions.keys()):
            position = context.portfolio.positions[stock]
            if position.total_amount > 0:
                order_target(stock, 0)
                log.info('市场恶化，清仓 %s' % stock)
                if stock in g.positions_info:
                    del g.positions_info[stock]
        g.buy_candidates = []
        g.today_bought = set()
        return

    # 2. 获取股票池（沪深300成分股，取前300只）
    try:
        universe = get_index_stocks('000300.XSHG')
    except:
        universe = []

    if len(universe) == 0:
        log.info('获取沪深300失败，使用全市场')
        universe = get_all_securities(['stock']).index.tolist()

    if len(universe) > 300:
        universe = universe[:300]

    log.info('股票池数量: %d' % len(universe))

    # 3. 过滤+评分（排除已持仓股票）
    held_stocks = set(context.portfolio.positions.keys())
    filtered_count = {'ipo': 0, 'price': 0, 'momentum': 0, 'pass': 0}
    candidates = []

    for stock in universe:
        # 已持有的股票不再重复买入
        if stock in held_stocks:
            continue
        try:
            # 新股过滤（上市<60天）
            stock_info = get_security_info(stock)
            if stock_info and stock_info.start_date:
                ipo_days = (today - stock_info.start_date).days
                if ipo_days < 60:
                    filtered_count['ipo'] += 1
                    continue

            # 判断ST股
            if is_st_stock(stock):
                filtered_count['price'] += 1
                continue

            # 停牌过滤
            if is_suspended(stock, context.current_dt):
                filtered_count['price'] += 1
                continue

            # 价格和成交量过滤（用context.current_dt，避免end_date=today可能误读当日数据）
            price_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close', 'volume'])
            if price_data is None or len(price_data) == 0:
                filtered_count['price'] += 1
                continue
            current_price = price_data['close'].iloc[-1]
            volume = price_data['volume'].iloc[-1]
            if current_price < 1.0 or volume <= 0:
                filtered_count['price'] += 1
                continue

            # 动量评分
            momentum_score = calculate_momentum_score(stock, context)
            if momentum_score <= context.momentum_threshold:
                filtered_count['momentum'] += 1
                continue

            # ATR计算
            atr = calculate_atr(stock, context)
            if atr <= 0:
                filtered_count['price'] += 1
                continue

            filtered_count['pass'] += 1
            candidates.append({
                'stock': stock,
                'price': current_price,
                'momentum_score': momentum_score,
                'atr': atr
            })

        except Exception as e:
            log.info('Exception on %s: %s' % (stock, str(e)))
            filtered_count['price'] += 1
            continue

    log.info('过滤统计: 新股=%d, 价格/量=%d, 动量不足=%d, 通过=%d' %
             (filtered_count['ipo'], filtered_count['price'],
              filtered_count['momentum'], filtered_count['pass']))

    if len(candidates) == 0:
        log.info('今日无符合条件的候选股')
        g.buy_candidates = []
        g.today_bought = set()
        return

    # 按动量评分排序，取前N只
    candidates.sort(key=lambda x: x['momentum_score'], reverse=True)
    g.buy_candidates = candidates[:context.stock_num]
    log.info('今日候选股: %s' % str([c['stock'] for c in g.buy_candidates]))
    g.today_bought = set()


# ========== 市场环境检查 ==========
# 【V2.1】2026-05-17 改进：从"3指数MA"改为"成分股动量情绪"
# 思路来源：DKX策略的全市场情绪控仓
# 数据范围：沪深300+中证500共约800只，与选股池一致
# 【V2.2】2026-05-17 改进：从"20日涨幅>5%"改为"动量加速度"
#   旧：ret_20d > 0.05 → 先跌后反弹也算多头（滞后）
#   新：ret_5d > 0.02 AND ret_20d > 0 → 短期在涨+中期趋势向上，才是真多头
def check_market_environment(context):
    """
    返回0-1评分，越高越好
    
    基于成分股"动量加速度"的情绪统计：
    强多头 = 近20日涨幅>0 AND 近5日涨幅>2%（中短期趋势同步向上）
    强空头 = 近20日涨幅<0 AND 近5日跌幅>2%（中短期趋势同步向下）
    
    4档评分：
    - >30%成分股强多头 → 市场强（1.0）
    - >20%成分股强多头 → 市场偏强（0.67）
    - >10%成分股强多头 → 市场偏弱（0.33）
    - <10%成分股强多头 → 市场差（0.0）
    """
    try:
        # 沪深300+中证500 = 约800只
        hs300 = get_index_stocks('000300.XSHG')
        zz500 = get_index_stocks('000905.XSHG')
        universe = hs300 + zz500
        
        if len(universe) > 800:
            universe = universe[:800]
        
        bull_count = 0
        bear_count = 0
        total_valid = 0
        
        for stock in universe:
            try:
                prices = get_price(stock, end_date=context.current_dt, count=20, fields=['close'])
                if prices is None or len(prices) < 20:
                    continue
                
                close = prices['close'].values
                ret_20d = (close[-1] - close[0]) / close[0]
                ret_5d = (close[-1] - close[-5]) / close[-5]
                
                # 强多头：中期趋势向上 + 短期加速涨
                if ret_20d > 0 and ret_5d > 0.02:
                    bull_count += 1
                # 强空头：中期趋势向下 + 短期加速跌
                elif ret_20d < 0 and ret_5d < -0.02:
                    bear_count += 1
                
                total_valid += 1
            except:
                continue
        
        if total_valid == 0:
            return 0.33
        
        bull_ratio = bull_count / total_valid
        
        # 4档仓位（加速度指标更严格，所以阈值适当降低）
        if bull_ratio > 0.30:
            score = 1.0
        elif bull_ratio > 0.20:
            score = 0.67
        elif bull_ratio > 0.10:
            score = 0.33
        else:
            score = 0.0
        
        log.info('市场环境详情: 有效%d只, 多头%d(%.1f%%), 空头%d(%.1f%%), 最终评分%.2f' %
                 (total_valid, bull_count, bull_ratio*100, bear_count, bear_count/total_valid*100, score))
        return score
        
    except Exception as e:
        log.info('市场环境检查异常: %s' % str(e))
        return 0.33  # 出错时默认中性


# ========== 动量评分 ==========
# 【V1旧版】注释保留，用于对比回测
# def calculate_momentum_score(stock, context):
#     """
#     计算动量评分（0-1之间，越高越好）
#     基于：价格趋势(0.4) + 短期动量(0.3) + 成交量放大(0.3)
#     """
#     try:
#         prices = get_price(stock, end_date=context.current_dt, count=20, fields=['close', 'volume'])
#         if prices is None or len(prices) < 20:
#             return 0.0
#
#         close_prices = prices['close'].values
#         volumes = prices['volume'].values
#
#         # 1. 价格趋势得分（0-0.4）：20日涨幅
#         price_return = (close_prices[-1] - close_prices[0]) / close_prices[0]
#         trend_score = min(max(price_return * 5, 0), 0.4)
#
#         # 2. 短期动量得分（0-0.3）：5日涨幅
#         short_return = (close_prices[-1] - close_prices[-5]) / close_prices[-5]
#         momentum_score = min(max(short_return * 10, 0), 0.3)
#
#         # 3. 成交量得分（0-0.3）：近期成交量放大
#         vol_ma5 = np.mean(volumes[-5:])
#         vol_ma20 = np.mean(volumes)
#         vol_score = min(max((vol_ma5 / vol_ma20 - 1) * 0.5, 0), 0.3) if vol_ma20 > 0 else 0
#
#         total_score = trend_score + momentum_score + vol_score
#         return min(total_score, 1.0)
#
#     except Exception as e:
#         return 0.0

# 【V2新版】2026-05-17 因子优化版本
# 改动：降低因子上限提高分辨率 + 年线位置>80%硬过滤 + 低位加分
def calculate_momentum_score(stock, context):
    """
    V2_FINAL 改进版动量评分
    1. 分辨率优化：趋势×1.75(上限0.35) 动量×3(上限0.25) 量能×0.25(上限0.20)
    2. 年线位置>80%硬过滤（极高位置不买入）
    3. 低位加分（位置<40%奖励）
    """
    try:
        # 需要250+数据点算年线位置
        prices = get_price(stock, end_date=context.current_dt, count=300,
                          fields=['close', 'volume', 'high', 'low'])
        if prices is None or len(prices) < 250:
            return 0.0

        close = prices['close'].values
        volume = prices['volume'].values
        high = prices['high'].values
        low = prices['low'].values

        # ===== 硬性过滤：年线位置 > 80% 不买入 =====
        year_high = np.max(high[-250:])
        year_low = np.min(low[-250:])
        
        # 【fix】处理NaN（新股上市不足250天时可能出现）
        if np.isnan(year_high) or np.isnan(year_low) or year_high <= year_low:
            return 0.0
        
        year_pos = (close[-1] - year_low) / (year_high - year_low) * 100
        if year_pos > 80:
            return 0.0  # 极高位置，不买入

        # ===== 评分计算 =====
        # 1. 价格趋势得分（0-0.35）：20日涨幅 × 1.75
        price_return = (close[-1] - close[-20]) / close[-20]
        trend_score = min(max(price_return * 1.75, 0), 0.35)

        # 2. 短期动量得分（0-0.25）：5日涨幅 × 3
        short_return = (close[-1] - close[-5]) / close[-5]
        momentum_score = min(max(short_return * 3, 0), 0.25)

        # 3. 成交量得分（0-0.20）：5/20均量比 × 0.25
        vol_ma5 = np.mean(volume[-5:])
        vol_ma20 = np.mean(volume[-20:])
        vol_ratio = vol_ma5 / vol_ma20 - 1 if vol_ma20 > 0 else 0
        volume_score = min(max(vol_ratio * 0.25, 0), 0.20)

        total = trend_score + momentum_score + volume_score

        # 低位加分：位置越低越安全
        if year_pos < 20:
            total += 0.10  # 深低位大幅加分
        elif year_pos < 40:
            total += 0.05  # 中低位小幅加分

        return min(max(total, 0), 1.0)

    except Exception as e:
        return 0.0


# ========== ATR计算 ==========
def calculate_atr(stock, context, period=14):
    """计算ATR（Average True Range）"""
    try:
        prices = get_price(stock, end_date=context.current_dt, count=period+1, fields=['high', 'low', 'close'])
        if prices is None or len(prices) < period + 1:
            return 0.0

        high = prices['high'].values
        low = prices['low'].values
        close = prices['close'].values

        true_ranges = []
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
            true_ranges.append(tr)

        atr = np.mean(true_ranges[-period:])
        return atr

    except Exception as e:
        return 0.0


# ========== 开盘买入 ==========
def open_time_action(context):
    if len(g.buy_candidates) == 0:
        log.info('无买入候选股，跳过买入')
        return

    log.info('开始买入检查，候选数: %d' % len(g.buy_candidates))
    check_and_buy_positions(context)


def check_and_buy_positions(context):
    if len(g.buy_candidates) == 0:
        return

    available_cash = context.portfolio.available_cash
    position_count = len([p for p in context.portfolio.positions.values() if p.total_amount > 0])
    can_buy_count = context.stock_num - position_count

    if can_buy_count <= 0:
        log.info('已达最大持仓数，跳过买入')
        return

    today = context.current_dt.date()

    for candidate in g.buy_candidates[:can_buy_count]:
        stock = candidate['stock']
        price = candidate['price']
        atr = candidate['atr']

        # 每只股票分配 MAX_POSITION_RATIO 比例的资金（如20%）
        target_value = available_cash * context.MAX_POSITION_RATIO
        shares = int(target_value / price / 100) * 100

        if shares > 0:
            order = order_target(stock, shares)

            # 【P0修复】用实际成交价记录日志
            actual_price = price
            actual_shares = shares
            if order and order.filled > 0:
                actual_price = order.price
                actual_shares = order.filled

            g.positions_info[stock] = {
                'buy_price': actual_price,
                'buy_date': today,  # 【P1优化】记录买入日期，用于最大持有天数检查
                'highest_price': actual_price,
                'atr': atr,
                'stop_loss_price': actual_price - atr * context.atr_multiplier,
                'take_profit_price': actual_price + atr * context.take_profit_multiplier
            }
            g.today_bought.add(stock)
            log.info('买入 %s, 实际成交价%.2f, 数量%d' % (stock, actual_price, actual_shares))


# ========== 收盘前卖出检查 ==========
def before_close_action(context):
    check_and_sell_positions(context)


def check_and_sell_positions(context):
    today = context.current_dt.date()

    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]
        if position.total_amount == 0:
            continue

        try:
            # 【防未来函数】14:55只用get_current_data获取实时价，不能用get_price(日线收盘价提前泄露)
            current_data = get_current_data()
            if stock not in current_data:
                continue
            current_price = current_data[stock].close  # 14:55的实时价格（不是日线收盘价）

            # 【P1优化】最大持有天数检查
            if stock in g.positions_info and 'buy_date' in g.positions_info[stock]:
                buy_date = g.positions_info[stock]['buy_date']
                hold_days = (today - buy_date).days
                if hold_days >= context.MAX_HOLD_DAYS:
                    order_target(stock, 0)
                    log.info('持有天数超限卖出 %s, 持有%d天, 当前价%.2f' %
                             (stock, hold_days, current_price))
                    del g.positions_info[stock]
                    continue

            # 更新最高价和移动止损
            if stock in g.positions_info:
                info = g.positions_info[stock]
                if current_price > info['highest_price']:
                    info['highest_price'] = current_price
                    info['stop_loss_price'] = max(
                        info['stop_loss_price'],
                        current_price - info['atr'] * context.atr_multiplier
                    )

                # 止损
                if current_price <= info['stop_loss_price']:
                    order_target(stock, 0)
                    log.info('止损卖出 %s, 当前价%.2f, 止损价%.2f' %
                             (stock, current_price, info['stop_loss_price']))
                    del g.positions_info[stock]
                    continue

                # 止盈
                if current_price >= info['take_profit_price']:
                    order_target(stock, 0)
                    log.info('止盈卖出 %s, 当前价%.2f, 止盈价%.2f' %
                             (stock, current_price, info['take_profit_price']))
                    del g.positions_info[stock]
                    continue

        except Exception as e:
            log.info('卖出检查异常 %s: %s' % (stock, str(e)))
            continue


# ========== 盘后 ==========
def after_market_close(context):
    total_value = context.portfolio.total_value
    cash = context.portfolio.available_cash
    log.info('今日结束: 总资产%.2f, 现金%.2f' % (total_value, cash))


# ========== 辅助函数 ==========
def is_suspended(stock, date):
    """判断股票是否停牌"""
    try:
        data = get_price(stock, end_date=date, count=1, fields=['volume'])
        if data is None or len(data) == 0:
            return True
        if data['volume'].iloc[-1] == 0:
            return True
        return False
    except:
        return True


def is_st_stock(stock):
    """判断是否为ST股（聚宽环境无内置is_st_stock函数）"""
    try:
        info = get_security_info(stock)
        if info and info.display_name:
            name = info.display_name
            return 'ST' in name or '*' in name
        return False
    except:
        return False
