# Clone from JoinQuant
# postId: cda77f383a590bbf413fffb2cb1b04ab
# backtestId: c4e5cb3734112f3785be6387daeeb7d3
# title: 行业概念的资金净流入数据计算问题

from jqdata import *
import numpy as np
import pandas as pd

def initialize(context):
    """
    初始化函数，策略启动时执行一次
    设置基准、滑点、手续费
    注册定时任务
    初始化全局变量
    """
    set_benchmark('000300.XSHG')
    set_slippage(FixedSlippage(0.02))
    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0.001,
            open_commission=0.0003, close_commission=0.0003,
            close_today_commission=0, min_commission=5
        ),
        type='stock'
    )
    # 每天 9:40 执行选股和更新持仓天数、卖出满6天持仓
    run_daily(market_open, time='9:40')
    # 每分钟检查跌停、止盈、止损卖出条件
    run_daily(check_sell_conditions, time='every_bar')

    # 初始化全局变量
    g.hold_days = {}   # 记录持仓天数 {股票: 天数}
    g.concept_list = []   # 记录选中的概念板块代码列表
    g.stock_list = []   # 今日买入股票列表
    g.hist_pe_data = {}   # 记录历史PE数据，计算分位用
    g.buy_time = {}  # 记录买入时间，格式 {股票代码: datetime}

def market_open(context):
    """
    每日开盘时运行
    1. 更新持仓天数，满6天的股票卖出
    2. 选出前一日资金净流入Top3概念板块
    3. 从Top3概念筛选符合条件的股票
    4. 按因子排序，取前5买入
    """
    today = context.current_dt.strftime('%Y-%m-%d')
    log.info("="*50)
    log.info(f"===== {today} 开盘：更新持仓天数 & 卖出满6天持仓 =====")

    # 1）更新持仓天数，并卖出持仓≥6天股票
    for stock in list(context.portfolio.positions.keys()):
        g.hold_days[stock] = g.hold_days.get(stock, 0) + 1
        log.info(f"{stock} 持仓天数更新为 {g.hold_days[stock]}")
        if g.hold_days[stock] >= 6:
            log.info(f"{stock} 持仓已满6天，执行卖出")
            order_target(stock, 0)
            del g.hold_days[stock]

    log.info(f"===== 开始执行选股策略，当前日期: {context.current_dt} =====")

    # —— 步骤1: 筛选前一日资金净流入 Top3 概念板块 —— 
    concepts = get_concepts()
    codes = list(concepts.index)
    prev_date = get_trade_days(end_date=context.current_dt, count=2)[0]  # 前一个交易日
    flows = []
    for code in codes:
        stocks = get_concept_stocks(code)
        df = get_money_flow(stocks, end_date=prev_date, count=1)
        if df is None or df.empty:
            continue
        amt = df['net_amount_main'].sum()
        flows.append((code, concepts.loc[code, 'name'], amt))
    flows.sort(key=lambda x: x[2], reverse=True)
    top3 = flows[:3]
    g.concept_list = [c[0] for c in top3]
    log.info(f"选出资金流入Top3概念板块: {[(c[1], c[2]) for c in top3]}")

    # —— 步骤2: 在 Top3 概念中筛选符合条件的个股 —— 
    cand, seen = [], set()
    for c in g.concept_list:
        stocks = get_concept_stocks(c)
        for stock in stocks:
            if stock in seen:
                continue
            seen.add(stock)
            # 排除 ST 及北交所
            if is_st_stock(stock, context.current_dt) or stock.endswith('.BJ'):
                continue
            # 获取市值和估值
            q = query(valuation).filter(valuation.code == stock)
            dfv = get_fundamentals(q, date=context.current_dt)
            if dfv.empty:
                log.info(f"{stock} 获取基本面数据为空，跳过")
                continue
            mcap = dfv['circulating_market_cap'][0]
            if mcap >= 80:
                continue
            # 量比大于1.8
            volrat = calculate_volume_ratio(stock, prev_date)
            if volrat <= 1.8:
                continue
            # 过去一个月跌幅15%-20%区间筛选
            if not check_monthly_decline(stock, context.current_dt, low=15, high=20):
                continue
            # 开盘溢价 -2% ~ +5%
            if not check_open_premium(stock, context.current_dt):
                continue
            # 计算其他排序因子
            pe = dfv['pe_ratio'][0]
            pe_percentile = calculate_pe_percentile(stock, pe, prev_date)
            turnover = calculate_turnover(stock, prev_date, mcap)
            
            log.info(f"符合条件股票: {stock}, 流通市值: {mcap:.2f} 亿元, 量比: {volrat:.2f}, PE分位: {pe_percentile:.2f}, 换手率: {turnover:.2f}%")
            cand.append((stock, volrat, pe_percentile, turnover, mcap))

    if not cand:
        log.info("无符合条件股票，今日不交易")
        return
    # —— 步骤3+4: 排序 & 取前5 —— 
    # 按量比(降)、PE分位(降)、换手率(降)、市值(降)排序
    cand.sort(key=lambda x: (-x[1], -x[2], -x[3]))
    g.stock_list = [s for s, *_ in cand][:5]
    for s in g.stock_list:
        name = get_security_info(s).display_name
        log.info(f"选中买入: {name}({s})")

    # —— 步骤5: 买入 —— 
    execute_buy(context)

def execute_buy(context):
    """
    等权买入策略，每只股票买入总资产20%仓位
    跳过涨停股，买入时日志打印
    """
    cash_per = context.portfolio.total_value * 0.2
    for stock in g.stock_list:
        if stock in context.portfolio.positions:
            log.info(f"{stock} 已持仓，跳过买入")
            continue
        data = get_price(stock, end_date=context.current_dt, count=1,
                        fields=['close', 'high_limit'])
        if data.empty:
            log.info(f"{stock} 获取价格数据为空，跳过买入")
            continue
        price, uplim = data['close'][0], data['high_limit'][0]
        # 若涨停，跳过买入
        if price >= uplim * 0.995:
            log.info(f"{stock} 价格接近涨停 {price:.2f}，跳过买入")
            continue
        amt = int(cash_per / price / 100) * 100
        if amt > 0:
            log.info(f"买入 {stock} 数量 {amt}，价格 {price:.2f}")
            order_target(stock, amt)
            g.hold_days[stock] = 0
            g.buy_time[stock] = context.current_dt  # 记录买入时间
        else:
            log.info(f"{stock} 计算买入数量为0，跳过买入")

def is_st_stock(stock, date):
    """检查是否为ST股票"""
    df = get_extras('is_st', [stock], end_date=date, count=1, df=True)
    return bool(df.iloc[0,0]) if df is not None and not df.empty else False

def calculate_volume_ratio(stock, date):
    """
    3日量比 = 近3日均量 / 前2日均量
    防止前2日均量为0导致除零，返回0并打印日志
    """
    d = get_price(stock, end_date=date, count=5, fields=['volume'])
    if d is None or len(d) < 5:
        log.info(f"{stock} 成交量数据不足，无法计算量比")
        return 0
    prev2_avg = d['volume'][:2].mean()
    recent3_avg = d['volume'][-3:].mean()
    if prev2_avg == 0:
        log.info(f"{stock} 前两日成交量均值为0，量比设为0")
        return 0
    vol_ratio = recent3_avg / prev2_avg
    return float(vol_ratio)

def calculate_pe_percentile(stock, current_pe, date):
    """
    计算股票当前PE相对过去250个交易日PE的分位数
    """
    if stock in g.hist_pe_data:
        hist = g.hist_pe_data[stock]
    else:
        q = query(valuation.pe_ratio).filter(valuation.code == stock)
        dates = get_trade_days(end_date=date, count=250)
        hist = []
        for d in dates:
            df = get_fundamentals(q, date=d)
            if not df.empty:
                hist.append(df['pe_ratio'][0])
        g.hist_pe_data[stock] = hist
    arr = np.array([x for x in hist if x > 0 and not np.isnan(x)])
    if len(arr) == 0:
        return 0
    percentile = float((arr <= current_pe).sum() / len(arr))
    return percentile

def calculate_turnover(stock, date, mcap):
    """
    近3日平均换手率 = avg(volume) / 流通股本 * 100%
    """
    hist = get_price(stock, end_date=date, count=3, fields=['volume'])
    price_df = get_price(stock, end_date=date, count=1, fields=['close'])
    if hist is None or price_df.empty:
        log.info(f"{stock} 换手率数据不足，返回0")
        return 0
    avg_vol = hist['volume'].mean()
    close_price = price_df['close'][0]
    if mcap == 0 or close_price == 0:
        return 0
    turnover = (avg_vol * close_price) / (mcap * 1e8) * 100  # mcap单位是亿元，转化成股数
    return turnover

def calculate_monthly_drop(stock, date):
    """
    计算过去20个交易日的月跌幅（收盘价跌幅%）
    """
    hist = get_price(stock, end_date=date, count=20, fields=['close'])
    if hist is None or len(hist) < 20:
        log.info(f"{stock} 月跌幅数据不足，返回0")
        return 0
    start, end = hist['close'][0], hist['close'][-1]
    drop_pct = (end - start) / start * 100
    return drop_pct

def check_open_premium(stock, date):
    """开盘溢价 -2% ~ +5%"""
    # 获取前一个交易日收盘价
    prev_trade_day = get_trade_days(end_date=date, count=2)[0]
    prev_close = get_price(stock, start_date=prev_trade_day, end_date=prev_trade_day, fields=['close'])
    if prev_close.empty:
        log.info(f"{stock} 前一交易日收盘价获取失败")
        return False
    prev_close_price = prev_close['close'][0]

    # 获取当天开盘价
    open_price = get_price(stock, start_date=date, end_date=date, frequency='1m', fields=['open'])
    if open_price.empty:
        log.info(f"{stock} 当天开盘价获取失败")
        return False
    open_price_value = open_price['open'][0]

    # 计算溢价
    premium = (open_price_value - prev_close_price) / prev_close_price * 100
    # 检查溢价区间
    if -2 <= premium <= 5:
        log.info(f"{stock} 开盘溢价符合要求，前收盘价: {prev_close_price:.2f}, 开盘价: {open_price_value:.2f}, 溢价: {premium:.2f}%")
        return True
    return False

def check_sell_conditions(context):
    """
    优化后的止盈策略：
    遍历买入后每个分钟收盘价，按时间顺序计算涨跌幅，
    一旦某分钟涨幅满足止盈条件即卖出。
    其他止盈、止损逻辑保持不变。
    """
    for stock in list(context.portfolio.positions.keys()):
        if stock not in g.buy_time:
            log.info(f"{stock} 未记录买入时间，跳过止盈止损检查")
            continue

        buy_time = g.buy_time[stock]
        cost = context.portfolio.positions[stock].avg_cost
        hold_days = g.hold_days.get(stock, 0)

        # 获取买入时间到当前时间的分钟级价格
        prices = get_price(stock, start_date=buy_time, end_date=context.current_dt,
                          frequency='1m', fields=['close', 'low_limit'])
        if prices.empty:
            log.info(f"{stock} 买入后分钟线数据为空，跳过止盈止损检查")
            continue

        buy_price = cost
        sold = False  # 标记是否已卖出

        # 遍历每个分钟收盘价，计算涨跌幅
        for idx, (price, low_lim) in enumerate(zip(prices['close'], prices['low_limit'])):
            pct_change = (price - buy_price) / buy_price * 100
            
            # 跌停卖出
            if price <= low_lim * 1.005:
                log.info(f"{stock} 在 {idx+1} 分钟接近跌停（{price:.2f}），卖出")
                order_target(stock, 0)
                log.info(f"{stock} 成功跌停卖出")
                g.hold_days.pop(stock, None)
                g.buy_time.pop(stock, None)
                sold = True
                break

            # 5日涨幅 > 25%，立即全额止盈卖出
            if pct_change > 25:
                log.info(f"{stock} 在第{idx+1}分钟涨幅超过25%，立即全额止盈，涨幅: {pct_change:.2f}%")
                order_target(stock, 0)
                g.hold_days.pop(stock, None)
                g.buy_time.pop(stock, None)
                sold = True
                break

            # 3日涨幅 > 15%，持仓满3日，止盈50%
            if pct_change > 15 and hold_days >= 3:
                log.info(f"{stock} 在第{idx+1}分钟涨幅超过15%，持仓满3日，止盈50%，涨幅: {pct_change:.2f}%")
                amount_to_sell = context.portfolio.positions[stock].total_amount * 0.5
                order_target(stock, amount_to_sell)
                sold = True
                break

        if sold:
            continue

        # 回撤超过3%，全部止损（回撤基于最高价）
        highest_price = prices['close'].max()
        current_price = prices['close'][-1]
        drawdown = (current_price - highest_price) / highest_price * 100 if highest_price > 0 else 0
        if drawdown < -3:
            log.info(f"{stock} 回撤超过3%，强制止损，当前回撤: {drawdown:.2f}%")
            order_target(stock, 0)
            g.hold_days.pop(stock, None)
            g.buy_time.pop(stock, None)

def check_monthly_decline(stock, date, low=15, high=20):
    """
    过去一个月跌幅是否在 low%-high% 区间（绝对值）
    """
    trade_days = get_trade_days(end_date=date, count=21)
    if len(trade_days) < 21:
        log.info(f"{stock} 交易日不足21天，无法计算一个月跌幅")
        return False
    start_price = get_price(stock, start_date=trade_days[0], end_date=trade_days[0], fields=['close'])
    end_price = get_price(stock, start_date=date, end_date=date, fields=['close'])
    if start_price.empty or end_price.empty:
        log.info(f"{stock} 开始或结束价格获取失败，无法计算一个月跌幅")
        return False
    start = start_price['close'][0]
    end = end_price['close'][0]
    decline_pct = (start - end) / start * 100
    if low <= decline_pct <= high:
        log.info(f"{stock} 过去一个月跌幅为 {decline_pct:.2f}%")
        return low <= decline_pct <= high