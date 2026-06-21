# Clone from JoinQuant
# postId: 390dc094f685120dacd8b6ffdecda66b
# backtestId: 5ecac38625b23917e6adeec534e9f729
# title: 我把 16 条实战血汗语录，写成了量化策略

# 策略名称: 动量趋势日内做T策略
# Python版本: Python3
# PostId: 799999
# 来源: 自研策略
# ==================================================
# 核心逻辑：
# 1. 选股：用多因子动量体系排序选出趋势最强的股票（超额动量+动量加速度+量价动量）
# 2. 做T：对持仓股进行日内高抛低吸（早盘冲高卖半仓，回踩均价线买回）
# 3. 风控：大盘熔断、个股趋势破位、单日做T亏损上限
# ==================================================

from jqdata import *
import numpy as np
import pandas as pd

def initialize(context):
    # ==================== 基础设置 ====================
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.02))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003,
                             close_commission=0.0003, min_commission=5), type='stock')
    log.set_level('order', 'info')

    # ==================== 可调参数 ====================
    # --- 持仓参数 ---
    g.stock_num = 2              # 最大持股数量
    g.t_ratio = 0.4             # 做T仓位比例（卖出底仓的比例）

    # --- 动量选股参数 ---
    g.select_index = '000001.XSHG'   # 基准指数（用于计算超额动量）
    g.momentum_period = 20       # 主动量计算周期（天）
    g.momentum_skip = 3          # 跳过最近N日（规避短期反转效应）
    g.min_momentum = 0.10        # 最低动量门槛（收益率3%以上才有入选资格）
    g.min_price = 13              # 最低股价限制
    g.max_price = 60             # 最高股价限制
    g.min_market_cap = 40        # 最小市值（亿）
    g.max_market_cap = 120       # 最大市值（亿）
    g.new_stock_days = 250       # 过滤次新股天数

    # ---反T(先抛后接)参数 ---
    g.t_sell_gain = 0.03         # 早盘冲高卖出阈值（涨幅超过2.5%卖出T仓）
    g.t_buy_back_drop = -0.04    # 回踩买回阈值（从日内高点回落2.5%精准买回）
    
    # ---正T(先买后抛)参数 ---
    g.fwd_t_buy_drop = -0.03      # 急杀低吸阈值（跌势超3%动用预留现金出击）
    g.fwd_t_sell_gain = 0.03     # 企稳抛出阈值（日内买点反弹2.5%则抛老仓对冲赚差价）

    # --- 底仓风控参数 ---
    g.base_take_profit = 0.8    # 底仓止盈线（从买入价盈利5%强制止盈出局换票）
    g.base_stop_loss = -0.07     # 底仓止损线（从买入价回撤5%清仓）
    g.ma_break_period = 10        # 均线破位周期（跌破MA5清仓）

    # --- 大盘风控参数 ---
    g.market_drop_limit = -0.02  # 大盘单日跌幅熔断阈值（-2%）
    g.market_index = '000300.XSHG'  # 大盘监控指数

    # --- 连续亏损保护 ---
    # （已按要求废除暂停做T机制，确保只要不开仓清退就坚持做T降成本）

    # ==================== 运行时状态 ====================
    g.hold_list = []             # 当前持仓列表
    g.t_sold_today = {}          # (反T)已卖出 {code: {'price': p, 'amount': a}}
    g.t_bought_back = {}         # (反T)已接回 {code: 买回价}
    g.t_bought_first = {}        # (正T)已吸筹 {code: {'price': p, 'amount': a}}
    g.t_sold_back_first = {}     # (正T)已对冲抛售 {code: 卖出价}
    g.day_high = {}              # 今日最高价 {code: price}
    g.day_low = {}               # 今日最低价 {code: price}
    g.yesterday_hl_list = []     # 昨日涨停列表
    g.target_list = []           # 选股目标列表

    # ==================== 定时任务 ====================
    run_daily(prepare_daily, '9:05')                # 每日盘前准备
    run_daily(select_stocks, '9:25')                # 每日更新热门趋势骨血库（以便随时换票）
    run_daily(check_trend_break, '14:40')           # 尾盘趋势破位断板检查
    run_daily(t_force_close, '14:30')               # 做T - 强制平T仓
    run_daily(rebalance_buy, '9:32')                # 底仓填补建仓（有空位时）
    run_daily(after_market, '15:00')                # 盘后统计

# ==================== 分钟级实时监控 ====================
def handle_data(context, data):
    """每分钟运行一次，实时监控涨幅和底仓盈亏"""
    # 核心实战风控 / 防误触隔离：
    # 1. 拦截某些引擎在 9:00/9:05 触发的幽灵调用
    # 2. 避开 9:30 集合竞价刚落地的神仙打架和价格失真期
    h = context.current_dt.hour
    m = context.current_dt.minute
    if h < 9 or (h == 9 and m <= 30) or h == 12 or h >= 15:
        return
        
    # 底仓监控 - 只要盈利达到配置设定(5%)或触发止损，立刻出局！
    check_base_pnl(context)
    # 互斥双向做T引擎
    t_sell_high(context)          # 支线A：反T 起点
    t_buy_back(context)           # 支线A：反T 终点
    forward_t_buy_low(context)    # 支线B：正T 起点
    forward_t_sell_high(context)  # 支线B：正T 终点


# ==================== 每日盘前准备 ====================
def prepare_daily(context):
    """每日开盘前准备工作"""
    # 重置日内状态
    g.t_sold_today = {}
    g.t_bought_back = {}
    g.t_bought_first = {}
    g.t_sold_back_first = {}
    g.day_high = {}
    g.day_low = {}

    # 更新持仓列表
    g.hold_list = list(context.portfolio.positions.keys())

    # 获取昨日涨停列表（持仓中的）
    g.yesterday_hl_list = []
    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_hl_list = list(df.code)


# ==================== 动量因子选股模块 ====================
def select_stocks(context):
    """每日用多因子动量体系排序选出趋势最强的股票"""
    dt_last = context.previous_date
    log.info("=" * 60)
    log.info("[选股] 开始动量因子选股...")

    # 1. 获取全市场股票
    all_stocks = get_all_securities('stock', dt_last).index.tolist()

    # 2. 基础过滤
    all_stocks = filter_kcbj_stock(all_stocks)
    all_stocks = filter_st_stock(all_stocks)
    all_stocks = filter_new_stock(context, all_stocks)
    all_stocks = filter_paused_stock(all_stocks)

    # 3. 市值和价格过滤
    q = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.code.in_(all_stocks),
        valuation.market_cap.between(g.min_market_cap, g.max_market_cap)
    ).order_by(valuation.market_cap.asc())
    df_val = get_fundamentals(q, date=dt_last)
    candidates = list(df_val.code) if not df_val.empty else []

    # 价格过滤
    if candidates:
        last_prices = history(1, unit='1d', field='close', security_list=candidates)
        candidates = [s for s in candidates if g.min_price <= last_prices[s][-1] <= g.max_price]

    # 【新增风控】：最近两天不能出现大跌超6% 或 冲高回落超过5%的股票
    if candidates:
        # 获取过去3个交易日收盘价和最高价 [T-3, T-2, T-1(昨天)]
        df_close = history(3, unit='1d', field='close', security_list=candidates)
        df_high = history(3, unit='1d', field='high', security_list=candidates)
        valid_candidates = []
        for s in candidates:
            if s in df_close and len(df_close[s]) >= 3 and s in df_high:
                closes = df_close[s].dropna()
                highs = df_high[s].dropna()
                if len(closes) >= 3 and len(highs) >= 3:
                    pct_yesterday = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2]  # 昨天跌幅
                    pct_day_before = (closes.iloc[-2] - closes.iloc[-3]) / closes.iloc[-3] # 前天跌幅
                    if pct_yesterday <= -0.06 or pct_day_before <= -0.06:
                        continue # 两天内任一天出现大跌超6%即淘汰
                        
                    # 计算冲高回落：(当日最高价 - 当日收盘价) / 昨收价
                    retreat_yesterday = (highs.iloc[-1] - closes.iloc[-1]) / closes.iloc[-2]
                    retreat_day_before = (highs.iloc[-2] - closes.iloc[-2]) / closes.iloc[-3]
                    if retreat_yesterday >= 0.05 or retreat_day_before >= 0.05:
                        continue # 两天内任一天出现最高价回落占比超过 5% 即淘汰
            valid_candidates.append(s)
        candidates = valid_candidates

    log.info("[选股] 基础及强险过滤后剩余 %d 只" % len(candidates))

    if not candidates:
        return

    # 4. 动量因子计算
    # 拉取足够长的历史数据（动量周期 + 跳过天数 + 缓冲）
    need_days = g.momentum_period + g.momentum_skip + 5
    df_all = get_price(candidates, end_date=dt_last, frequency='daily',
                       fields=['close', 'volume', 'high_limit'],
                       count=need_days, panel=False, skip_paused=True)
    if df_all.empty:
        return
    grouped = df_all.groupby('code')

    # 获取基准指数数据（用于计算超额动量）
    index_price = get_price(g.select_index, end_date=dt_last, frequency='daily',
                            fields=['close'], count=need_days, panel=False)
    idx_closes = index_price['close'].values if not index_price.empty else None

    scored_stocks = []
    for stock in candidates:
        try:
            if stock not in grouped.groups:
                continue
            df = grouped.get_group(stock)

            min_len = g.momentum_period + g.momentum_skip
            if len(df) < min_len:
                continue

            closes = df['close'].values
            volumes = df['volume'].values

            # ========== 核心因子1: 区间动量（跳过最近skip天，规避短期反转）==========
            # 动量 = close[-skip] / close[-(period+skip)] - 1
            if g.momentum_skip > 0:
                raw_momentum = closes[-g.momentum_skip] / closes[-(g.momentum_period + g.momentum_skip)] - 1
            else:
                raw_momentum = closes[-1] / closes[-g.momentum_period] - 1

            # 最低动量门槛：没涨到3%的不要
            if raw_momentum < g.min_momentum:
                continue

            # ========== 硬性过滤: 10日相对强度 > 5% ==========
            # 个股10日涨幅必须领先指数涨幅5个百分点以上
            stock_10d_ret = (closes[-1] / closes[-10] - 1) * 100 if len(closes) >= 10 else 0
            if idx_closes is not None and len(idx_closes) >= 10:
                idx_10d_ret = (idx_closes[-1] / idx_closes[-10] - 1) * 100
            else:
                idx_10d_ret = 0
            if stock_10d_ret - idx_10d_ret < 5.0:
                continue

            # ========== 核心因子2: 动量加速度（近期涨速 vs 远期涨速）==========
            # 近5日涨速 > 前期涨速 → 动量在加速，趋势健康
            recent_5d_ret = closes[-1] / closes[-6] - 1
            prior_ret = closes[-6] / closes[-g.momentum_period - 1] - 1 if len(closes) > g.momentum_period else 0
            acceleration = recent_5d_ret - prior_ret

            # ========== 核心因子4: 超额动量（跑赢大盘的部分才是真本事）==========
            if idx_closes is not None and len(idx_closes) >= min_len:
                if g.momentum_skip > 0:
                    idx_ret = idx_closes[-g.momentum_skip] / idx_closes[-(g.momentum_period + g.momentum_skip)] - 1
                else:
                    idx_ret = idx_closes[-1] / idx_closes[-g.momentum_period] - 1
                excess_momentum = raw_momentum - idx_ret
            else:
                excess_momentum = raw_momentum

            # ========== 核心因子5: 波动率调整动量（涨得稳 > 涨得猛）==========
            daily_returns = np.diff(closes[-21:]) / closes[-21:-1]
            volatility = np.std(daily_returns)
            risk_adj_momentum = raw_momentum / max(volatility, 0.001)

            # ========== 核心因子6: 动量一致性（上涨天数占比，越均匀越持久）==========
            up_days = np.sum(np.diff(closes[-21:]) > 0)
            consistency = up_days / 20.0

            # 硬性过滤：一致性低于50%说明涨势不稳，剔除
            if consistency < 0.5:
                continue

            # ========== 过热防护: 连板股排除 ==========
            recent_10 = df.tail(10)
            hl_count = sum(np.round(recent_10['close'].values, 2) >= np.round(recent_10['high_limit'].values, 2))
            if hl_count > 2:
                continue

            # ========== 综合打分 ==========
            # 权重: 风险调整动量50% + 动量加速度25% + 动量一致性25%
            score = risk_adj_momentum * 0.5 + acceleration * 0.25 + consistency * 0.25

            scored_stocks.append((stock, score, raw_momentum * 100, excess_momentum * 100))

        except Exception as e:
            continue

    # 5. 按综合动量得分排序，取前N只
    scored_stocks.sort(key=lambda x: x[1], reverse=True)
    g.target_list = [s[0] for s in scored_stocks[:g.stock_num]]

    log.info("[选股] 动量选股完成，目标 %d 只" % len(g.target_list))
    for s, score, mom, excess in scored_stocks[:g.stock_num]:
        log.info("  ✓ %s | 综合得分: %.4f | 动量: %.1f%% | 超额: %.1f%%" % (s, score, mom, excess))


# ==================== 底仓建仓买入 ====================
def rebalance_buy(context):
    """有空闲头寸时，每日开盘从目标池填补新的趋势股"""
    if not g.target_list:
        return

    current_data = get_current_data()

    # 买入目标列表中的股票
    position_count = len(context.portfolio.positions)
    if position_count < g.stock_num:
        # 过滤涨停和跌停
        buy_list = [s for s in g.target_list
                    if s not in context.portfolio.positions
                    and current_data[s].last_price < current_data[s].high_limit
                    and current_data[s].last_price > current_data[s].low_limit
                    and not current_data[s].paused]

        slots = g.stock_num - position_count
        # 恢复预留资金机制：单只股票目标占用资金为 target_per，但建仓只买 (1 - g.t_ratio) 比例，剩下留作现金备用
        target_per = context.portfolio.total_value / g.stock_num
        base_per = target_per * (1 - g.t_ratio)
        for stock in buy_list[:slots]:
            buy_value = min(base_per, context.portfolio.available_cash * 0.95)
            order_value(stock, buy_value)
            log.info("[底仓] 买入: %s %s | 建仓金额: %.0f (预留了此股 %d%% 的资金备用做T)" %
                     (stock, current_data[stock].name, buy_value, g.t_ratio * 100))


# ==================== 做T - 盘中冲高卖出 ====================
def t_sell_high(context):
    """实时监控持仓，只要涨幅达到阈值则卖出T仓"""
    # 检查大盘是否熔断
    if is_market_crash(context):
        log.info("[做T] 大盘异常下跌，今日暂停做T")
        return

    current_data = get_current_data()

    for stock in g.hold_list:
        if stock in g.t_sold_today or stock in g.t_bought_first:
            continue  # 一只股一天只做一个方向的波段，避免混乱
        if stock not in context.portfolio.positions:
            continue

        pos = context.portfolio.positions[stock]
        if pos.closeable_amount <= 0:
            continue

        # 获取昨收价和现价计算今日涨幅
        # 【关键修复】：分钟级回测中 history(1, '1d') 获取的是包含了今天的K线，等于当前价。
        # 必须获取 count=2，取它的倒数第二根才是真的昨日收盘价。
        prev_data = history(2, unit='1d', field='close', security_list=[stock])
        if stock not in prev_data or len(prev_data[stock]) < 2:
            continue
            
        pre_close = prev_data[stock].iloc[-2]
        current_price = current_data[stock].last_price
        if pre_close <= 0:
            continue

        # 按昨收价计算真实的当日涨幅
        gain = (current_price - pre_close) / pre_close

        # 涨停不卖
        if round(current_price, 2) >= round(current_data[stock].high_limit, 2):
            log.info("[做T] %s 涨停中，不卖出" % stock)
            continue

        if gain >= g.t_sell_gain:
            # 达到冲高阈值，卖出T仓
            t_amount = int(pos.closeable_amount * g.t_ratio / 100) * 100  # 取整百
            if t_amount >= 100:
                order(stock, -t_amount)
                # 优化点2：精确记录卖出股数实现防加减仓精确匹配
                g.t_sold_today[stock] = {'price': current_price, 'amount': t_amount}
                g.day_high[stock] = current_price
                log.info("[做T卖出] %s %s | 涨幅: %.2f%% | 卖出%d股 @ %.2f" %
                         (stock, current_data[stock].name, gain * 100, t_amount, current_price))


# ==================== 做T - 回踩买回 ====================
def t_buy_back(context):
    """实时监控已卖出T仓的股票，只要回踩阈值到位立刻买回"""
    current_data = get_current_data()

    for stock, sell_info in list(g.t_sold_today.items()):
        if stock in g.t_bought_back:
            continue  # 已经买回了

        sell_price = sell_info['price']
        sell_amount = sell_info['amount']
        current_price = current_data[stock].last_price
        if current_price <= 0:
            continue

        # 更新日内最高价
        if stock in g.day_high:
            g.day_high[stock] = max(g.day_high[stock], current_price)
        else:
            g.day_high[stock] = current_price

        # 计算从卖出价（或日内高点）的回撤幅度
        high = g.day_high.get(stock, sell_price)
        drop = (current_price - high) / high

        # 跌停不买
        if round(current_price, 2) <= round(current_data[stock].low_limit, 2):
            continue

        # 【重点防守】：如果全天股票被核按钮大跌（跌破放弃阈值），拒绝接回飞刀
        try:
            prev_data = history(2, unit='1d', field='close', security_list=[stock])
            if stock in prev_data and len(prev_data[stock]) >= 2:
                pre_close = prev_data[stock].iloc[-2]
                if pre_close > 0:
                    real_drop = (current_price - pre_close) / pre_close
                    if real_drop <= getattr(g, 't_give_up_drop', -0.04):
                        continue  # 跌幅太深，盘中直接忽略接回信号
        except Exception:
            pass

        if drop <= g.t_buy_back_drop:
            # 优化点2：精确用股数下单，买回刚才抛出的同样筹码
            buy_cash_needed = current_price * sell_amount
            # 确保现金足够，不够则降档买入能买得起的股数
            if context.portfolio.available_cash < buy_cash_needed:
                sell_amount = int(context.portfolio.available_cash / current_price / 100) * 100
                
            if sell_amount >= 100:
                order(stock, sell_amount)
                g.t_bought_back[stock] = current_price
                log.info("[做T买回] %s %s | 回撤: %.2f%% | 准确补回 %d股 @ %.2f" %
                         (stock, current_data[stock].name, drop * 100, sell_amount, current_price))


# ==================== 做T - 强制防卖飞接回底仓 ====================
def t_force_close(context):
    """14:50 如果早上抛了底仓做T，但下午没跌下来没触发接回判定，尾盘强制买回防底仓丢失"""
    current_data = get_current_data()

    for stock, sell_info in list(g.t_sold_today.items()):
        if stock in g.t_bought_back:
            continue
            
        sell_amount = sell_info['amount']
        current_price = current_data[stock].last_price
        
        # 跌停买不进
        if round(current_price, 2) <= round(current_data[stock].low_limit, 2):
            log.info("[做T买回失败] %s 跌停封板中，无法强制接回" % stock)
            continue
            
        # 【重点防守】：尾盘结账时，如果此票仍处深水位，主动放弃接回留待明日验证
        try:
            prev_data = history(2, unit='1d', field='close', security_list=[stock])
            if stock in prev_data and len(prev_data[stock]) >= 2:
                pre_close = prev_data[stock].iloc[-2]
                if pre_close > 0:
                    real_drop = (current_price - pre_close) / pre_close
                    if real_drop <= getattr(g, 't_give_up_drop', -0.04):
                        log.info("[防接飞刀] %s %s 跌幅极深(%.2f%%)！防止明日惯性下杀，今日截断并取消尾盘强接！" % 
                                 (stock, current_data[stock].name, real_drop * 100))
                        g.t_bought_back[stock] = current_price # 虚假拉结，移出扫描序列
                        continue
        except Exception:
            pass
            
        # 【摩擦防守】：如果尾盘现价与高抛卖出价过于接近（如盈亏在1%之内），不接回给券商打工
        sell_price = sell_info['price']
        diff_ratio = abs((current_price - sell_price) / sell_price)
        if diff_ratio <= 0.01:
            log.info("[放弃底仓接回] %s %s 尾盘现价与卖出价无明显差价(相距仅%.2f%%)，取消强接避免干耗手续费！" %
                     (stock, current_data[stock].name, diff_ratio * 100))
            g.t_bought_back[stock] = current_price
            continue
            
        # 根据可用资金强制买回
        buy_cash_needed = current_price * sell_amount
        if context.portfolio.available_cash < buy_cash_needed:
            sell_amount = int(context.portfolio.available_cash / current_price / 100) * 100
            
        if sell_amount >= 100:
            order(stock, sell_amount)
            g.t_bought_back[stock] = current_price
            log.info("[防卖飞最后通牒] %s %s 强制接回 %d 股维持底仓配置 @ %.2f" % 
                     (stock, current_data[stock].name, sell_amount, current_price))

    # 2. 正T防满仓强制减持：如果早上急跌吸筹买了由于太弱没弹上去对冲掉
    for stock, buy_info in list(g.t_bought_first.items()):
        if stock in g.t_sold_back_first:
            continue
            
        sell_amount = buy_info['amount']
        current_price = current_data[stock].last_price
        
        # 涨停封板不抛（多占多得）
        if round(current_price, 2) >= round(current_data[stock].high_limit, 2):
            log.info("[吸筹暴涨延期] %s 死封涨停，低吸筹码延期保留！" % stock)
            continue
            
        pos = context.portfolio.positions.get(stock, None)
        if pos and pos.closeable_amount >= sell_amount:
            order(stock, -sell_amount)
            g.t_sold_back_first[stock] = current_price
            log.info("[防超买最后通牒] %s %s 强平 %d 股还原仓位与资金 @ %.2f" % 
                     (stock, current_data[stock].name, sell_amount, current_price))


# ==================== 正T - 急杀先买低吸 ====================
def forward_t_buy_low(context):
    """实时监控持仓，未冲高反而先急跌时，用备用金逆势买入"""
    if is_market_crash(context):
        return

    current_data = get_current_data()

    for stock in g.hold_list:
        if stock not in context.portfolio.positions:
            continue
        
        # 互斥锁：只要这票今天做了反T，就不允许做正T；做过正T也不再重新做
        if stock in g.t_sold_today or stock in g.t_bought_first:
            continue
            
        pos = context.portfolio.positions[stock]
        
        # 正T需要有可用底仓可以在反弹时抛出冲销（T+0闭环的物理需求）
        # 也就是昨天买的老仓，否则今天买的新仓反弹了也没法卖
        if pos.closeable_amount <= 0:
            continue

        # history(2, unit='1d') 获取昨收价
        prev_data = history(2, unit='1d', field='close', security_list=[stock])
        if stock not in prev_data or len(prev_data[stock]) < 2:
            continue
            
        pre_close = prev_data[stock].iloc[-2]
        current_price = current_data[stock].last_price
        if pre_close <= 0:
            continue

        # 跌停不买（警惕单边闷杀）
        if round(current_price, 2) <= round(current_data[stock].low_limit, 2):
            continue

        gain = (current_price - pre_close) / pre_close
        if gain <= g.fwd_t_buy_drop:
            # 严格根据配比金测算火力
            target_cash = (context.portfolio.total_value / g.stock_num) * g.t_ratio
            buy_cash_needed = min(target_cash, context.portfolio.available_cash * 0.95)
            
            buy_amount = int(buy_cash_needed / current_price / 100) * 100
            
            # 为了防止尾盘卖不出去导致第二天重仓挨打，买入量不能超过今天可卖出的老仓数目
            buy_amount = min(buy_amount, pos.closeable_amount)
            
            if buy_amount >= 100:
                order(stock, buy_amount)
                g.t_bought_first[stock] = {'price': current_price, 'amount': buy_amount}
                g.day_low[stock] = current_price
                log.info("[正T低吸出击] %s %s | 跌幅: %.2f%% | 抄底加仓 %d股 @ %.2f" % 
                         (stock, current_data[stock].name, gain * 100, buy_amount, current_price))

# ==================== 正T - 企稳对冲抛出 ====================
def forward_t_sell_high(context):
    """正T出击之后，只要从日内深坑反弹2.5%赚出差价，则将匹配的旧底仓抛售变现"""
    current_data = get_current_data()
    
    for stock, buy_info in list(g.t_bought_first.items()):
        if stock in g.t_sold_back_first:
            continue
            
        buy_price = buy_info['price']
        sell_amount = buy_info['amount']
        current_price = current_data[stock].last_price
        
        # 更新记录这轮暴跌的极值底
        if stock in g.day_low:
            g.day_low[stock] = min(g.day_low[stock], current_price)
        else:
            g.day_low[stock] = current_price
            
        low = g.day_low.get(stock, buy_price)
        rebound = (current_price - low) / low
        
        # 涨停封板不差钱，继续留持
        if round(current_price, 2) >= round(current_data[stock].high_limit, 2):
            continue
            
        if rebound >= g.fwd_t_sell_gain:
            order(stock, -sell_amount)
            g.t_sold_back_first[stock] = current_price
            log.info("[正T对冲兑现] %s %s | V型反弹: %.2f%% | 卖出 %d股 套现 @ %.2f" %
                     (stock, current_data[stock].name, rebound * 100, sell_amount, current_price))

# ==================== 底仓止盈止损秒杀监控 ====================
def check_base_pnl(context):
    """分钟级监控底仓，触发5%即刻获利了结准备换票"""
    current_data = get_current_data()

    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.closeable_amount <= 0:
            continue

        current_price = current_data[stock].last_price
        avg_cost = pos.avg_cost

        # 涨停坚决不卖
        if round(current_price, 2) >= round(current_data[stock].high_limit, 2):
            continue

        pnl = (current_price - avg_cost) / avg_cost
        
        # 条件1：连根拔起极限界限止盈（已调整为 80%）
        if pnl >= getattr(g, 'base_take_profit', 0.8):
            order_target_value(stock, 0)
            g.t_sold_today.pop(stock, None) # 停止对此股后续做T买回的干扰
            log.info("[绝世妖股终点] %s %s | 跨日狂飙盈利: %.2f%% 触发终极止盈出局！" %
                     (stock, current_data[stock].name, pnl * 100))
            continue
            
        # 条件1.05：稳健强制止盈（盈利达10%即刻止盈保利润）
        if pnl >= 0.1:
            order_target_value(stock, 0)
            g.t_sold_today.pop(stock, None)
            log.info("[稳健止盈] %s %s | 盈利已达: %.2f%% 触发10%%强制止盈出局！" %
                     (stock, current_data[stock].name, pnl * 100))
            continue
            
        # 条件1.1：短线冲天炮快刀斩乱麻（次日立刻盈利超5%直接落袋）
        try:
            init_d = None
            if hasattr(pos, 'init_time'):
                import datetime
                if isinstance(pos.init_time, str):
                    init_d = datetime.datetime.strptime(pos.init_time, "%Y-%m-%d %H:%M:%S").date()
                else:
                    init_d = pos.init_time.date()
            if init_d is not None:
                # 条件1.1：短线冲天炮快刀斩乱麻
                if init_d == context.previous_date and pnl >= 0.05:
                    order_target_value(stock, 0)
                    g.t_sold_today.pop(stock, None) 
                    log.info("[次日暴利抢跑] %s %s | 昨天刚进，今天爆赚: %.2f%%, 触及次日5%%红线直接清仓！" %
                             (stock, current_data[stock].name, pnl * 100))
                    continue
                    
                # 条件1.2：时间止损（5个交易日未盈利直接斩仓出局）
                trade_days_list = get_trade_days(start_date=init_d, end_date=context.current_dt.date())
                held_trade_days = len(trade_days_list) - 1
                if held_trade_days >= getattr(g, 'max_hold_days', 5) and pnl <= 0.00:
                    order_target_value(stock, 0)
                    g.t_sold_today.pop(stock, None)
                    log.info("[时间止损] %s %s | 持仓已达 %d 天且未实现盈利(盈亏: %.2f%%)，钝刀割肉直接出局！" %
                             (stock, current_data[stock].name, held_trade_days, pnl * 100))
                    continue

        except Exception as e:
            pass
            
        # 条件2：雷霆止损
        if pnl <= g.base_stop_loss:
            order_target_value(stock, 0)
            g.t_sold_today.pop(stock, None)
            log.info("[触底斩仓] %s %s | 亏损: %.2f%% 触发清仓止损线" %
                     (stock, current_data[stock].name, pnl * 100))
            continue

# ==================== 尾盘日线趋势防线 ====================
def check_trend_break(context):
    """14:40 检查趋势是否已经走坏（给日内洗盘留出机会）"""
    current_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.closeable_amount <= 0:
            continue
            
        current_price = current_data[stock].last_price
        
        # 跌破均线导致趋势死亡
        df = get_price(stock, end_date=context.previous_date, frequency='daily',
                       fields=['close'], count=g.ma_break_period, panel=False, skip_paused=True)
        if len(df) >= g.ma_break_period:
            ma = df['close'].mean()
            if current_price < ma:
                order_target_value(stock, 0)
                g.t_sold_today.pop(stock, None)
                log.info("[趋势死亡] %s %s | 现价 %.2f 跌破 MA%d 线 %.2f | 尾盘清仓认输" %
                         (stock, current_data[stock].name, current_price, g.ma_break_period, ma))

    # 断板清洗：昨日涨停，今天不连板尾盘无情杀掉
    if g.yesterday_hl_list:
        for stock in g.yesterday_hl_list:
            if stock in context.portfolio.positions:
                if current_data[stock].last_price < current_data[stock].high_limit:
                    order_target_value(stock, 0)
                    g.t_sold_today.pop(stock, None)
                    log.info("[连板失败] %s 断板动能衰减，移出持仓" % stock)


# ==================== 盘后统计 ====================
def after_market(context):
    """15:00 盘后统计做T盈亏"""
    if g.t_sold_today:
        total_t_pnl = 0
        for stock, sell_info in g.t_sold_today.items():
            sell_price = sell_info['price']
            if stock in g.t_bought_back:
                buy_back_price = g.t_bought_back[stock]
                pnl = (sell_price - buy_back_price) / buy_back_price * 100
                total_t_pnl += pnl
                log.info("[做T日报] %s | 卖: %.2f → 买: %.2f | 盈亏: %.2f%%" %
                         (stock, sell_price, buy_back_price, pnl))
            else:
                log.info("[做T日报] %s | 卖: %.2f | 未买回（等待明日低吸机会）" %
                         (stock, sell_price))



    # 更新持仓列表
    g.hold_list = list(context.portfolio.positions.keys())
    log.info("[盘后] 当前持仓 %d 只 | 总资产: %.2f" %
             (len(g.hold_list), context.portfolio.total_value))


# ==================== 大盘熔断判断 ====================
def is_market_crash(context):
    """判断大盘是否异常下跌"""
    current_data = get_current_data()
    try:
        index_open = current_data[g.market_index].day_open
        index_price = current_data[g.market_index].last_price
        if index_open > 0:
            drop = (index_price - index_open) / index_open
            return drop <= g.market_drop_limit
    except:
        pass
    return False


# ==================== 过滤函数 ====================
def filter_kcbj_stock(stock_list):
    """过滤科创板、北交所、创业板股票"""
    return [s for s in stock_list
            if not (s.startswith('68') or s.startswith('4') or s.startswith('8') or s.startswith('3'))]

def filter_st_stock(stock_list):
    """过滤ST及退市标签股票"""
    current_data = get_current_data()
    return [s for s in stock_list
            if not current_data[s].is_st
            and 'ST' not in current_data[s].name
            and '*' not in current_data[s].name
            and '退' not in current_data[s].name]

def filter_new_stock(context, stock_list):
    """过滤次新股"""
    yesterday = context.previous_date
    return [s for s in stock_list
            if not yesterday - get_security_info(s).start_date < datetime.timedelta(days=g.new_stock_days)]

def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].paused]
