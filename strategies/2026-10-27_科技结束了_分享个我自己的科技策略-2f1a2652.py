# Clone from JoinQuant
# postId: 2f1a26528a6dd6846ade35478d1eecf2
# backtestId: e3052d4c31a69430a9dab08522a70258
# title: 科技结束了？分享个我自己的科技策略。

# ==================================================
# 策略名称：3日调仓·收益增强版（午盘13:10交易优化）
# 交易时间：13:10，过滤早盘假突破，提升胜率
# ==================================================

from jqdata import *

# ============== 核心参数 ==============
g.hold_num = 1                  # 单只全仓
g.rebalance_days = 3            # 3日调仓
g.trade_time = '9:31'          # 【修改】交易时间改为午盘13:10

# ============== 止盈止损 ==============
g.stop_loss = -0.05             # 科技标的初始止损 -7%
g.gold_stop_loss = -0.03        # 黄金标的止损收紧至 -3%
g.trailing_start = 0.20         # 科技标的盈利20%启动移动止盈
g.gold_trailing_start = 0.05    # 黄金标的盈利5%启动跟踪止盈
g.trailing_drawdown = 0.05      # 科技标的回撤8%止盈
g.gold_trailing_drawdown = 0.03 # 黄金标的回撤3%止盈

# ============== ETF标的池 ==============
g.etf_pool = [
    '588000.XSHG',  # 科创50ETF
    '512480.XSHG',  # 半导体ETF
    '515070.XSHG',  # 人工智能ETF
    '516630.XSHG',  # 算力ETF
    '515880.XSHG',  # 通信ETF
    '512720.XSHG',  # 计算机ETF
    '515260.XSHG',  # 电子ETF
    '518880.XSHG',  # 黄金ETF
]

# ============== 风控参数 ==============
g.sector_index = '000300.XSHG'
g.ma_short = 20
g.ma_long = 60

g.max_drawdown_stop = -0.20     # 总回撤20%触发清仓暂停
g.pause_days = 5               # 暂停10个交易日
g.max_continuous_loss = 3       # 连续亏损3次暂停一期


# ==================================================
# 初始化
# ==================================================
def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    
    # 交易成本
    set_order_cost(OrderCost(
        close_tax=0,
        open_commission=0.0001,
        close_commission=0.0001,
        min_commission=5
    ), type='fund')
    
    # 滑点
    set_slippage(PriceRelatedSlippage(0.001), type='fund')
    
    # 全局变量
    g.trade_day_count = 0
    g.buy_list = []
    g.is_rebalance_day = False
    g.position_high = {}
    g.highest_net_value = context.portfolio.total_value
    g.pause_remain_days = 0
    g.continuous_loss_count = 0
    g.last_trade_profit = 0
    
    # 定时任务
    run_daily(before_market_open, time='before_open')
    run_daily(daily_trade, time=g.trade_time)


# ==================================================
# 盘前预处理
# ==================================================
def before_market_open(context):
    g.trade_day_count += 1
    g.is_rebalance_day = (g.trade_day_count % g.rebalance_days == 0)
    
    # 更新账户净值高点
    current_value = context.portfolio.total_value
    if current_value > g.highest_net_value:
        g.highest_net_value = current_value
    
    # 熔断倒计时
    if g.pause_remain_days > 0:
        g.pause_remain_days -= 1
        log.info('策略暂停中，剩余{}个交易日'.format(g.pause_remain_days))
        g.buy_list = []
        return
    
    # 大盘双均线择时
    market_trend = check_market_trend(context)
    if not market_trend and not g.is_rebalance_day:
        g.buy_list = []
        return
    
    # 连续亏损保护
    if g.continuous_loss_count >= g.max_continuous_loss:
        log.info('连续亏损{}次，暂停本期调仓'.format(g.continuous_loss_count))
        g.buy_list = []
        if g.is_rebalance_day:
            g.continuous_loss_count = 0
        return
    
    # 调仓日选股（盘前算好，午盘直接执行）
    if g.is_rebalance_day:
        rank_etf_by_momentum(context)
    else:
        g.buy_list = []


# ==================================================
# 双均线择时
# ==================================================
def check_market_trend(context):
    df = get_price(
        g.sector_index,
        end_date=context.previous_date,
        count=g.ma_long,
        frequency='1d',
        fields=['close'],
        fq='pre'
    )
    if df is None or len(df) < g.ma_long:
        return True
    
    closes = df['close']
    ma20 = closes.iloc[-g.ma_short:].mean()
    ma60 = closes.mean()
    latest = closes.iloc[-1]
    
    return latest > ma20 and ma20 > ma60


# ==================================================
# 双动量因子排名
# ==================================================
def rank_etf_by_momentum(context):
    current_data = get_current_data()
    valid_etfs = [etf for etf in g.etf_pool if not current_data[etf].paused]
    
    if len(valid_etfs) == 0:
        g.buy_list = []
        return
    
    df = get_price(
        valid_etfs,
        end_date=context.previous_date,
        count=11,
        frequency='1d',
        fields=['close'],
        fq='pre'
    )
    if df is None or len(df) == 0:
        g.buy_list = []
        return
    
    rank_list = []
    for etf in valid_etfs:
        try:
            closes = df['close'][etf].dropna()
            if len(closes) < 11:
                continue
            
            gain_5 = (closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6]
            gain_10 = (closes.iloc[-1] - closes.iloc[-11]) / closes.iloc[-11]
            
            # 加权动量得分
            momentum_score = gain_5 * 0.4 + gain_10 * 0.6
            rank_list.append((etf, momentum_score, gain_10))
        except:
            continue
    
    if len(rank_list) == 0:
        g.buy_list = []
        log.info('无符合条件标的，空仓观望')
        return
    
    rank_list.sort(key=lambda x: x[1], reverse=True)
    g.buy_list = [etf for etf, _, _ in rank_list[:g.hold_num]]
    log.info('调仓日最强标的：{}，10日涨幅{:.2%}'.format(g.buy_list[0], rank_list[0][2]))


# ==================================================
# 盘中交易函数（13:10执行）
# ==================================================
def daily_trade(context):
    current_data = get_current_data()
    
    # ========== 第一步：持仓风控 ==========
    for etf in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[etf]
        if position.total_amount == 0:
            continue
        
        price = current_data[etf].last_price
        if price is None or price == 0:
            continue
        
        # 更新阶段最高价
        if etf not in g.position_high or price > g.position_high[etf]:
            g.position_high[etf] = price
        
        profit_rate = (price - position.avg_cost) / position.avg_cost
        
        # 区分黄金和科技标的
        is_gold = (etf == '518880.XSHG')
        stop_loss = g.gold_stop_loss if is_gold else g.stop_loss
        trail_start = g.gold_trailing_start if is_gold else g.trailing_start
        trail_dd = g.gold_trailing_drawdown if is_gold else g.trailing_drawdown
        
        # 1. 固定止损
        if profit_rate <= stop_loss:
            order_target(etf, 0)
            log.info('止损卖出 {}，收益{:.2%}'.format(etf, profit_rate))
            if not is_gold:
                record_trade_result(profit_rate)
            if etf in g.position_high:
                del g.position_high[etf]
            
            # 熔断检查
            current_value = context.portfolio.total_value
            drawdown = (current_value - g.highest_net_value) / g.highest_net_value
            if drawdown <= g.max_drawdown_stop and g.pause_remain_days == 0:
                log.warning('总回撤{:.2%}触发熔断，暂停{}个交易日'.format(drawdown, g.pause_days))
                g.pause_remain_days = g.pause_days
            continue
        
        # 2. 移动止盈
        if profit_rate >= trail_start:
            high = g.position_high[etf]
            drawdown = (high - price) / high
            if drawdown >= trail_dd:
                order_target(etf, 0)
                log.info('移动止盈卖出 {}，最高收益{:.2%}，当前收益{:.2%}'.format(
                    etf, (high - position.avg_cost)/position.avg_cost, profit_rate))
                if not is_gold:
                    record_trade_result(profit_rate)
                if etf in g.position_high:
                    del g.position_high[etf]
            continue
    
    # ========== 第二步：调仓换股 ==========
    if g.is_rebalance_day and g.pause_remain_days == 0 and len(g.buy_list) > 0:
        target_etf = g.buy_list[0]
        for etf in list(context.portfolio.positions.keys()):
            if context.portfolio.positions[etf].total_amount == 0:
                continue
            if etf != target_etf:
                pos = context.portfolio.positions[etf]
                profit = (current_data[etf].last_price - pos.avg_cost) / pos.avg_cost
                if etf != '518880.XSHG':
                    record_trade_result(profit)
                
                order_target(etf, 0)
                log.info('调仓换股卖出 {}'.format(etf))
                if etf in g.position_high:
                    del g.position_high[etf]
    
    # ========== 第三步：全仓买入 ==========
    if g.pause_remain_days > 0 or len(g.buy_list) == 0:
        return
    
    target_etf = g.buy_list[0]
    if target_etf in context.portfolio.positions and context.portfolio.positions[target_etf].total_amount > 0:
        return
    
    if current_data[target_etf].paused:
        return
    
    price = current_data[target_etf].last_price
    if price is None or price == 0:
        return
    
    # 全仓买入，预留3%手续费
    available_cash = context.portfolio.available_cash
    buy_cash = available_cash * 0.97
    
    share = int(buy_cash / price / 100) * 100
    if share < 100:
        return
    
    result = order(target_etf, share)
    if result and result.filled > 0:
        log.info('买入成功：{}，数量{}，成交价{:.2f}'.format(target_etf, share, result.price))
        if target_etf not in g.position_high:
            g.position_high[target_etf] = result.price


# ==================================================
# 记录交易盈亏
# ==================================================
def record_trade_result(profit_rate):
    if profit_rate < 0:
        g.continuous_loss_count += 1
    else:
        g.continuous_loss_count = 0
    g.last_trade_profit = profit_rate