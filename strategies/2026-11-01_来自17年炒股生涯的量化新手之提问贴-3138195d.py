# Clone from JoinQuant
# postId: 3138195d202ab64be847f2a9ff59da63
# backtestId: 06e50da4429ab55fec6a2ef1a43c2b43
# title: 来自17年炒股生涯的量化新手之提问贴

# coding=utf-8
from jqdata import *
import csv
import os

def initialize(context):
    # ---- 大盘择时 ----
    g.market_up_count = 0
    g.market_index_up = False
    g.market_level = 'L3'
    g.buy_multiplier = 1

    # ---- 仓位风控 ----
    g.max_single_position_base = 150000  # 默认单票上限
    g.stock_num = 2

    # ---- 选股参数 ----
    g.open_low = 0.01
    g.open_high = 0.05
    g.amount_thresh = 20e8
    g.turnover_thresh = 0.10
    g.rise_thresh = 0.01
    g.amount_ratio_low = 1.8
    g.amount_ratio_high = 3.0
    g.mcap_low = 150e8
    g.mcap_high = 500e8

    # ---- 交易控制 ----
    g.stop_loss = -0.05
    g.take_profit = 0.7

    g.candidates = []

    # ---- 定时任务 ----
    
    run_daily(before_trading, time='09:25')
    run_daily(trade, time='09:30')
    run_daily(early_sell, time='09:35')
    run_daily(early_sell, time='09:59')
    run_daily(sell, time='09:45', kwargs={'check_point': 'open'})
    run_daily(sell, time='10:30', kwargs={'check_point': 'mid1'})
    run_daily(sell, time='11:25', kwargs={'check_point': 'mid2'})
    run_daily(sell, time='14:40', kwargs={'check_point': 'late'})
    run_daily(sell, time='10:45', kwargs={'check_point': 'final'})

    log.info("策略初始化完成")
    
    
def get_market_status(context):
    """
    9:25 终极稳定版（无 Panel / 无 loc）
    返回：
    up_count   : 开盘上涨家数
    index_up   : 上证指数是否上涨
    """
    today = context.current_dt.date()
    yesterday = context.previous_date

    stocks = list(get_all_securities(types=['stock']).index)
    current_data = get_current_data()

    # ✅ 用 panel=False，返回 DataFrame
    prev_close_df = get_price(
        stocks,
        end_date=yesterday,
        count=1,
        fields=['close'],
        panel=False
    )

    up_count = 0
    for _, row in prev_close_df.iterrows():
        stock = row['code']
        try:
            prev_close = row['close']
            today_open = current_data[stock].day_open
            if today_open > prev_close:
                up_count += 1
        except:
            continue

    # ✅ 单独取指数昨收（最稳）
    index_prev_df = get_price(
        '000001.XSHG',
        end_date=yesterday,
        count=1,
        fields=['close'],
        panel=False
    )

    index_prev = index_prev_df.iloc[0]['close']
    index_open = current_data['000001.XSHG'].day_open
    index_up = index_open / index_prev - 1 > 0.002

    return up_count, index_up


def before_trading(context):

    today = context.current_dt.date()
    yesterday = context.previous_date

    # ====================
    # ① 大盘状态
    # ====================
    g.market_up_count, g.market_index_up = get_market_status(context)

    log.info(
        f"{today} 开盘上涨家数:{g.market_up_count} "
        f"上证上涨:{g.market_index_up}"
    )

    # ====================
    # ② 大盘四级风控（最终稳定版）
    # ====================
    g.max_single_position = g.max_single_position_base
    g.stock_num = 2
    g.buy_multiplier = 1.0
    g.max_single_position = 100000
    g.market_level = 'L3'
    

    if g.market_up_count <= 1500:
        g.market_level = 'L1'
        g.buy_multiplier = 0.0
        log.warning("【L1 极弱市】禁止开仓")
    
    elif g.market_up_count < 3000:
        g.market_level = 'L2'
        g.buy_multiplier = 0.8
        g.max_single_position = 50000
        g.stock_num = 3
        
        log.warning("【L2 弱市】限制开仓")
    
    # ✅ 修改后的逻辑 (拉高资金利用率)
    elif g.market_up_count >= 3500 and g.market_index_up:
        g.market_level = 'L4'
        g.buy_multiplier = 1.0  # 不再虚增资金感知
        g.max_single_position = 200000  # 单票上限直接翻倍
        g.stock_num = 4
        
    else:
        g.market_level = 'L3'
        g.buy_multiplier = 1.5
        g.max_single_position = 100000
        g.stock_num = 3
        
        log.info("【L3 正常市】按原策略")
    
    # ====================
    # ✅ 参数自检机制（最终稳定版）
    # ====================
    
    if g.market_level == 'L4':
        expected_max = 200000
    elif g.market_level in ['L3', 'L2', 'L1']:
        expected_max = 150000
    else:
        expected_max = 0
    
    # ✅ 允许 L1 / L2 持有旧仓
    if g.market_level in ['L1', 'L2'] and g.max_single_position > 150000:
        log.error(
            f"❌ 参数异常：{g.market_level} "
            f"max_single_position={g.max_single_position} "
            f"expected≤150000"
        )
        raise RuntimeError("大盘风控参数异常，策略强制停止")
    
    log.warning(
        f"⚠️ 实际生效：【{g.market_level}】 "
        f"单票上限={g.max_single_position} 只数={g.stock_num} "
        f"乘数={g.buy_multiplier}"
    )
    
    
    # ====================
    # ③ 选股逻辑（最终版）
    # ====================
    current_data = get_current_data()
    g.candidates = []

    # ✅ 股票池（不再依赖 g.security）
    all_stocks = get_all_securities(types=['stock']).index.tolist()
    stocks = [
        s for s in all_stocks
        if not s.startswith('688')
        and not s.startswith('8')
        and not current_data[s].is_st
        and not current_data[s].paused
    ]

    fundamentals = get_fundamentals(
        query(valuation.code, valuation.circulating_market_cap)
        .filter(valuation.code.in_(stocks)),
        date=yesterday
    )
    fundamentals['circulating_market_cap'] *= 1e8

    stocks = fundamentals[
        (fundamentals['circulating_market_cap'] >= g.mcap_low) &
        (fundamentals['circulating_market_cap'] <= g.mcap_high)
    ]['code'].tolist()

    # ✅ 关键修正：回归版本3的2日行情，避免引入大前日的噪声
    price_df = get_price(stocks, end_date=yesterday, count=2, fields=['open', 'close', 'money', 'volume'], skip_paused=True, panel=False)

    for stock in stocks:
        df = price_df[price_df['code'] == stock]
        if len(df) < 2: continue
        df = df.sort_index()
        prev_day = df.iloc[-2]
        last_day = df.iloc[-1]

        rise = last_day['close'] / prev_day['close'] - 1
        if rise <= g.rise_thresh: continue

        market_cap = fundamentals.loc[fundamentals['code'] == stock, 'circulating_market_cap'].values[0]
        turnover = last_day['money'] / market_cap
        if turnover <= g.turnover_thresh: continue
        if last_day['money'] <= g.amount_thresh: continue

        amount_ratio = last_day['money'] / prev_day['money']
        if amount_ratio < g.amount_ratio_low or amount_ratio > g.amount_ratio_high: continue

        # ---------- 防“连续放量高开坑” ----------
        # 逻辑：如果昨天和前天都明显放量，今天高开
        #      极大概率是主力派发末端，直接剔除
        try:
            big_prev_day = price_df[price_df['code'] == stock].iloc[-3]
        
            prev_amount_ratio = prev_day['money'] / big_prev_day['money']
        
            if amount_ratio >= 1.8 and prev_amount_ratio >= 1.3:
                continue
        
        except Exception:
            pass

        today_open = get_price(
            stock, end_date=today, count=1, fields=['open']
        ).iloc[0]['open']

        open_change = today_open / last_day['close'] - 1
        if not (g.open_low <= open_change <= g.open_high):
            continue

        g.candidates.append({
            'code': stock,
            'name': current_data[stock].name,
            'open_change': open_change,
            'amount_ratio': amount_ratio,
            'turnover': turnover,
            'rise': rise
        })

    # ====================
    # ④ 选股日志
    # ====================
    if g.candidates:
        log.info(
            f"[{today} 09:00] 选股: 数量{len(g.candidates)}只\n"
            + "\n".join([
                f"  {c['name']}({c['code']}) 高开{c['open_change']:.2%} "
                f"量比{c['amount_ratio']:.2f} 换手{c['turnover']:.2%}"
                for c in g.candidates
            ])
        )

def early_sell(context):
    """
    9:25 竞价阶段对持仓进行极端处理
    """
    if g.market_level not in ['L1', 'L2']:
        return

    current_data = get_current_data()
    today = context.current_dt.date()

    for stock, position in list(context.portfolio.positions.items()):
        # ✅ 9:25 只能用 day_open
        price = current_data[stock].day_open
        cost = position.avg_cost
        ret = price / cost - 1

        try:
            ma10 = get_MA(10, stock)
        except:
            ma10 = cost

        # ✅ 新增：只要不低于10日线，就不急着在竞价阶段卖出
        if price >= ma10*0.99:
            continue

        # L1：仅在跌破10日线时，亏损清仓 + 微利减仓
        if g.market_level == 'L1':
            if ret < 0:
                order_target(stock, 0)
                log.warning(f"{stock} L1 亏损股竞价清仓")
            elif ret < 0.05:
                qty = position.total_amount // 2
                order(stock, -qty)
                log.warning(f"{stock} L1 微利股减仓1/2")

        # L2：微利减半（同样需跌破10日线）
        elif g.market_level == 'L2' and ret < 0.05:
            qty = position.total_amount // 2
            order(stock, -qty)
            log.warning(f"{stock} L2 微利股减半仓")


  
def trade(context):
    today = context.current_dt.date()
    if not g.candidates:
        log.info(f"{today} 没有选股结果，跳过买入")
        return

    current_data = get_current_data()
    
    # 1.   # ✅ 用“真实可用现金”
    base_cash = context.portfolio.cash
    daily_total_cash = base_cash * g.buy_multiplier
    daily_total_cash = min(daily_total_cash, base_cash)
    
    
    # 引入大盘风控后下面的不变
    if daily_total_cash <= 0:
        log.info(f"{today} 可用资金不足，跳过买入")
        return

    # 2. 确定当日计划买入的股票数量
    target_stock_count = min(len(g.candidates), g.stock_num)
    
    
    # 3. 计算每只股票的平均预算（L4 资金利用率优化版）
    # 不再使用 total_value * ratio 的限制，直接使用 L4 设定的硬上限
    
    per_stock_budget = daily_total_cash / target_stock_count
    per_stock_budget = min(per_stock_budget, g.max_single_position)
    
    log.info(
        f"[{today}] 计划买入 {target_stock_count} 只，"
        f"总资金 {daily_total_cash:,.2f}，"
        f"单只预算 {per_stock_budget:,.2f}"
    )

    for idx, stock_info in enumerate(g.candidates[:target_stock_count]):
        stock = stock_info['code']
        
        # 如果已经持仓，则跳过
        if stock in context.portfolio.positions:
            continue

        # 获取9点25分产生的开盘价
        open_price = current_data[stock].day_open
        if open_price is None or open_price <= 0:
            continue

        # 【核心修改】计算委托价格
        # 1. 计算1%的滑点价格
        slippage_price = open_price * 0.015
        
        # 2. 计算交易所允许的2%最高限价（价格笼子上限）
        price_ceiling_2pct = open_price * 1.02
        
        # 3. 计算交易所允许的0.1元最低限价（价格笼子补充）
        # 规则：取2%与0.1元的孰高值 [2,6](@ref)
        exchange_limit = max(price_ceiling_2pct, open_price + 0.10)
        
        # 4. 计算初步委托价：开盘价 + 1%滑点
        tentative_price = open_price + slippage_price
        
        # 5. 确保委托价不超过交易所限制，且高于开盘价
        # 使用 min 限制上限，使用 max 确保不会低于开盘价（防止极端情况）
        order_price = min(tentative_price, exchange_limit)
        order_price = max(order_price, open_price + 0.01) # 至少高一分钱
        
        # 确保价格符合最小变动单位（A股是0.01元）
        order_price = round(order_price, 2)

        # 4. 根据预算和委托价计算可买股数（取整百股）
        # 注意：这里要用 order_price 计算，确保不超过预算
        shares = int(per_stock_budget / order_price / 100) * 100
        
        if shares <= 0:
            log.info(f"  {stock}：预算不足购买至少100股，跳过")
            continue

        # 【核心修改】下单
        # 使用 LimitOrderStyle 并设置计算好的 order_price
        order(stock, shares, LimitOrderStyle(order_price))
        
        log.info(f"[{today} 09:25] 买入: {stock} {shares}股 @委托价{order_price:.2f} (开盘价:{open_price:.2f})")

        # 5. 动态扣减资金，防止在循环中超支
        daily_total_cash -= shares * order_price
        if daily_total_cash <= 0:
            break


def sell(context, check_point='10:45'):
    today = context.current_dt.date()
    current_data = get_current_data()

    positions = list(context.portfolio.positions.keys())
    if not positions:
        log.info(f"\n[{today} {check_point}] 卖出检查: 持仓0只")
        return

    log.info(f"\n[{today} {check_point}] 卖出检查: 持仓{len(positions)}只")
    sold_count = 0

    for stock in positions:
        position = context.portfolio.positions[stock]
        price = current_data[stock].last_price
        cost = position.avg_cost
        ret = price / cost - 1

        # ====================
        # ✅ 新增：僵尸仓兜底清理（最重要）
        # ====================
        if position.total_amount < 100:
            order_target(stock, 0)
            log.warning(f"{stock} 持仓不足100股，强制清仓")
            sold_count += 1
            continue

        # ====================
        # ✅ T+1 保护
        # ====================
        if today == position.init_time.date():
            log.info(f"  {stock} | T+1 当日买入，跳过卖出")
            continue

        high_limit = current_data[stock].high_limit
        low_limit = current_data[stock].low_limit
        is_limit_up = (price >= high_limit * 0.995) and (price > low_limit)

        # ====================
        # ✅ 涨停锁仓
        # ====================
        if is_limit_up:
            log.info(f"  {stock} 封死涨停，锁仓")
            continue

        # ====================
        # ✅ 炸板即卖
        # ====================
        try:
            prev_price = get_price(
                stock, end_date=context.previous_date,
                count=1, fields=['close']
            ).iloc[0]['close']
        except:
            prev_price = price

        was_limit_up_yesterday = (
            prev_price >= current_data[stock].high_limit * 0.995
        )

        if was_limit_up_yesterday and not is_limit_up:
            log.warning(f"{stock} 炸板，紧急卖出")
            order_target(stock, 0)
            sold_count += 1
            continue

        # ====================
        # ✅ 开盘跳空止损
        # ====================
        if check_point == 'open':
            open_gap = price / cost - 1
            if open_gap < -0.02:
                log.warning(f"{stock} 开盘跳空低开 {open_gap:.2%}，紧急止损")
                order_target(stock, 0)
                sold_count += 1
                continue

        # ====================
        # ✅ 均线减半（安全版）
        # ====================
        try:
            ma5 = get_MA(5, stock)
        except:
            ma5 = price

        if (
            check_point in ['mid1', 'mid2', 'late', 'final']
            and not is_limit_up
            and ret < 0.20
            and price < ma5
        ):
            half_qty = position.total_amount // 2
            half_qty = (half_qty // 100) * 100

            if half_qty < 100:
                order_target(stock, 0)
            else:
                order(stock, -half_qty)

            sold_count += 1
            continue

        # ====================
        # ✅ 最终清仓
        # ====================
        if check_point != 'final':
            continue

        should_sell = False
        reason = ""

        if ret <= g.stop_loss:
            should_sell = True
            reason = "硬止损"
        elif ret >= g.take_profit:
            should_sell = True
            reason = "阶梯止盈"

        if should_sell:
            order_target(stock, 0)
            sold_count += 1

    log.info(f"[{today} {check_point}] 卖出完成: 卖{sold_count}只 剩{len(context.portfolio.positions)}只\n")


def save_trade_log(trade_log, context):
    today = context.current_dt.strftime('%Y%m%d')
    file_path = os.path.join(g.log_dir, f'trade_log_{today}.csv')

    fieldnames = [
        '买入日期', '股票名称', '股票代码',
        '买入价格', '买入数量', '买入金额',
        '仓位占比', '买入时间点',
        '当日收盘盈亏比例', '当日收盘盈亏金额'
    ]

    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trade_log)


def after_trading(context):
    today = context.current_dt.date()
    
    if g.positions_info:
        log.info(f"\n[{today} 15:30] 收盘持仓: 共{len(g.positions_info)}只")
        
        total_cost = 0       # 剩余持仓成本
        total_value = 0      # 剩余持仓市值
        total_pnl = 0        # 总盈亏（包含已卖出）
        
        for stock, info in g.positions_info.items():
            current_price = get_current_data()[stock].last_price
            
            # 剩余持仓的真实成本
            real_cost = info['buy_price'] * info['shares']
            real_value = current_price * info['shares']
            pnl = real_value - real_cost
            ret = real_value / real_cost - 1 if real_cost > 0 else 0
            
            total_cost += real_cost
            total_value += real_value
            total_pnl += pnl
            
            log.info(
                f"  {stock} | 成本{info['buy_price']:.2f}→{current_price:.2f} "
                f"盈亏{ret:+.2%} 金额{pnl:+.0f}"
            )
        
        # ✅✅✅ 加上已卖出部分的盈亏 ✅✅✅
        sold_pnl = g.total_sold_revenue - g.total_sold_cost - g.total_commission_paid
        total_pnl += sold_pnl
        
        # 总投入 = 原始买入总成本
        original_cost = total_cost + g.total_sold_cost
        total_ret = total_pnl / original_cost if original_cost > 0 else 0
        
        log.info(f"\n  总投入:{original_cost:,.0f} 市值:{total_value:,.0f} 已卖收入:{g.total_sold_revenue:,.0f}")
        log.info(f"  总盈亏:{total_pnl:+.0f} 收益率:{total_ret:+.2%}\n")



