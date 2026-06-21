# Clone from JoinQuant
# postId: f1253042cf301c2f2f232ec260ff0275
# backtestId: 199ff8b70c2c034318f286c7d0e72b78
# title: 10万本金，我用这个量化策略三年赚了68万

# 聚宽量化策略 - 10万实盘优化版
# ==================================================
# 针对10万本金优化：低频交易 + 严格风控 + 低佣金友好

# ==================== 实盘优化参数 ====================
INDEX = '000300.XSHG'
STOCK_COUNT = 10           # 持仓数量
REBALANCE_CYCLE = 10      # 调仓周期改为10天（减少交易频率）
STOP_LOSS = 0.07          # 止损略微收紧到7%
TAKE_PROFIT = 0.15        # 止盈调整到15%
MAX_POSITION = 0.15       # 单只仓位上限15%（10万建议最多1.5万/只）
MA_SHORT = 20
MA_LONG = 60
MARKET_TIMING = True

# 最小交易金额（避免佣金倒挂）
MIN_TRADE_VALUE = 2000    # 低于2000元的股票不买入，避免佣金不划算

# ==================== 初始化 ====================
def initialize(context):
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013))
    set_slippage(FixedSlippage(0.001))  # 滑点降低到0.1%
    set_benchmark(INDEX)
    
    context.hold_records = {}
    context.last_rebalance_date = None
    
    log.info("=" * 50)
    log.info("10万实盘优化策略初始化")
    log.info("持仓数量: %d" % STOCK_COUNT)
    log.info("调仓周期: %d 天（低频）" % REBALANCE_CYCLE)
    log.info("止损线: %.1f%%" % (STOP_LOSS * 100))
    log.info("止盈线: %.1f%%" % (TAKE_PROFIT * 100))
    log.info("最低交易金额: %d元" % MIN_TRADE_VALUE)
    log.info("=" * 50)

def get_today(context):
    return context.current_dt.strftime('%Y-%m-%d')

def get_universe(date):
    hs300 = get_index_stocks('000300.XSHG', date)
    zz500 = get_index_stocks('000905.XSHG', date)
    universe = list(set(hs300 + zz500))
    
    try:
        st_df = get_extras('is_st', universe, start_date=date, end_date=date, fq='pre')
        if st_df is not None and len(st_df) > 0:
            for stock in universe[:]:
                if stock in st_df.index and st_df.loc[stock].iloc[0] == True:
                    universe.remove(stock)
    except:
        pass
    
    return universe[:80]

def market_timing(date):
    try:
        prices = get_price(INDEX, end_date=date, count=60, frequency='daily', fq='pre')
        if prices is None or len(prices) < 30:
            return True
        
        ma20 = prices['close'][-MA_SHORT:].mean()
        ma60 = prices['close'][-MA_LONG:].mean()
        current = prices['close'][-1]
        
        if current > ma20 > ma60:
            return True
        elif current < ma20 < ma60:
            return False
        return True
    except:
        return True

def calculate_momentum(stock, date):
    try:
        prices = get_price(stock, end_date=date, count=60, frequency='daily', fq='pre')
        if prices is None or len(prices) < 30:
            return 0
        mom = prices['close'][-1] / prices['close'][0] - 1
        return max(min((mom + 0.3) / 0.6, 1), 0)
    except:
        return 0.5

def calculate_volatility(stock, date):
    try:
        prices = get_price(stock, end_date=date, count=60, frequency='daily', fq='pre')
        if prices is None or len(prices) < 30:
            return 0.5
        returns = prices['close'].pct_change().dropna()
        vol = returns.std() * np.sqrt(252)
        return max(min(1 - (vol - 0.1) / 0.4, 1), 0)
    except:
        return 0.5

def select_stocks(context):
    date = get_today(context)
    log.info("开始选股... 日期: %s" % date)
    
    universe = get_universe(date)
    
    if len(universe) < 20:
        log.warn("股票池太小: %d" % len(universe))
        return []
    
    # 过滤价格过低或过高的股票（适合10万资金）
    tradeable = []
    for stock in universe:
        try:
            price = get_price(stock, end_date=date, count=1, frequency='daily', fq='pre')
            if price is not None and len(price) > 0:
                current_price = price['close'][-1]
                if 5 <= current_price <= 200:  # 价格适中
                    tradeable.append(stock)
        except:
            continue
    
    if len(tradeable) < 10:
        tradeable = universe
    
    scores = []
    for stock in tradeable:
        try:
            mom_score = calculate_momentum(stock, date)
            vol_score = calculate_volatility(stock, date)
            total_score = mom_score * 0.5 + vol_score * 0.5
            scores.append((stock, total_score))
        except:
            continue
    
    scores.sort(key=lambda x: x[1], reverse=True)
    selected = [s[0] for s in scores[:STOCK_COUNT]]
    
    log.info("选股完成，选中 %d 只股票" % len(selected))
    return selected

# ==================== 主策略 ====================
def handle_data(context, data):
    today = get_today(context)
    
    need_rebalance = False
    if context.last_rebalance_date is None:
        need_rebalance = True
    else:
        days = (context.current_dt.date() - context.last_rebalance_date).days
        if days >= REBALANCE_CYCLE:
            need_rebalance = True
    
    if MARKET_TIMING:
        is_bull = market_timing(today)
        if not is_bull:
            log.info("检测到空头市场，清仓...")
            for stock in context.portfolio.positions.keys():
                order_target_value(stock, 0)
            context.hold_records = {}
            return
    
    # 风控检查（每日执行）
    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]
        try:
            price = data[stock].close
        except:
            continue
        if price is None or price <= 0:
            continue
        
        cost = context.hold_records.get(stock, {}).get('cost', position.avg_cost)
        
        if cost and cost > 0:
            ret = (price - cost) / cost
            
            # 止损（7%触发）
            if ret <= -STOP_LOSS:
                log.info("触发止损: %s, 亏损 %.2f%%" % (stock, ret * 100))
                order_target_value(stock, 0)
                context.hold_records.pop(stock, None)
            
            # 止盈（15%后回撤10%止盈）
            elif ret >= TAKE_PROFIT:
                high = context.hold_records.get(stock, {}).get('high', price)
                if high > 0:
                    drawdown = (price - high) / high
                    if drawdown <= -0.10:
                        log.info("触发止盈: %s, 收益 %.2f%%" % (stock, ret * 100))
                        order_target_value(stock, 0)
                        context.hold_records.pop(stock, None)
            
            if stock in context.hold_records:
                if price > context.hold_records[stock].get('high', 0):
                    context.hold_records[stock]['high'] = price
    
    # 执行调仓（每10天一次）
    if need_rebalance:
        log.info("=" * 40)
        log.info("执行调仓... 日期: %s" % today)
        
        selected = select_stocks(context)
        
        if not selected:
            log.info("未选出股票，跳过本次调仓")
            return
        
        for stock in list(context.portfolio.positions.keys()):
            if stock not in selected:
                order_target_value(stock, 0)
                context.hold_records.pop(stock, None)
        
        # 10万资金，预留10%现金（1万）应对
        available_cash = context.portfolio.total_value * 0.90
        target_value = available_cash / len(selected)
        max_value = context.portfolio.total_value * MAX_POSITION
        target_value = min(target_value, max_value)
        
        if target_value < MIN_TRADE_VALUE:
            log.info("目标金额 %d 元低于最低交易金额" % target_value)
            return
        
        for stock in selected:
            if stock not in context.portfolio.positions:
                if context.portfolio.cash >= target_value:
                    order_target_value(stock, target_value)
                    try:
                        price = data[stock].close
                        if price and price > 0:
                            context.hold_records[stock] = {'cost': price, 'high': price}
                            log.info("买入 %s: %d元 @ %.2f" % (stock, target_value, price))
                    except:
                        pass
        
        context.last_rebalance_date = context.current_dt.date()
        log.info("调仓完成，持仓 %d 只，现金 %.2f 元" % (len(context.portfolio.positions), context.portfolio.cash))
        log.info("=" * 40)

def after_trading_end(context):
    today = get_today(context)
    
    log.info("=" * 50)
    log.info("收盘持仓摘要 - %s" % today)
    
    if len(context.portfolio.positions) > 0:
        total_value = context.portfolio.total_value
        cash = context.portfolio.cash
        log.info("总资产: %.2f 元" % total_value)
        log.info("现金: %.2f 元 (%.1f%%)" % (cash, cash/total_value*100))
        log.info("持仓数量: %d" % len(context.portfolio.positions))
        
        positions = sorted(context.portfolio.positions.items(), key=lambda x: x[1].value, reverse=True)
        for i, (stock, pos) in enumerate(positions[:5], 1):
            cost = context.hold_records.get(stock, {}).get('cost', pos.avg_cost)
            if cost and cost > 0:
                ret = (pos.price - cost) / cost * 100
                log.info("%d. %s: 成本 %.2f, 现价 %.2f, 收益 %.2f%%" % (i, stock, cost, pos.price, ret))
    else:
        log.info("当前空仓")
    
    log.info("=" * 50)
