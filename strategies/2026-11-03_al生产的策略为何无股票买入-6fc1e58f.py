# Clone from JoinQuant
# postId: 6fc1e58f04e1bb374bdfe3766af9c660
# backtestId: 62dc4b742cd5d51629e30c374fac127a
# title: al生产的策略为何无股票买入

# 初始化函数，设置策略参数
def initialize(context):
    # 设置基准
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.info('策略初始化')

    # 设置手续费
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    # 股票池：上证所有股票
    g.stock_pool = get_index_stocks('000001.XSHG')  # 上证所有股票
    g.holding_days = 20  # 持仓周期（天）
    g.turnover_threshold = 0.5  # 两个月总换手率50%
    g.positions = {}  # 记录持仓时间

    # 每天运行 market_open 函数
    run_daily(market_open, time='open')

# 开盘时运行
def market_open(context):
    log.info('运行时间：' + str(context.current_dt.time()))

    for stock in g.stock_pool:
        try:
            # 获取最近40天数据
            data = get_bars(stock, count=40, unit='1d', fields=['close', 'volume', 'high', 'low'])
            if len(data) < 40:
                continue  # 数据不足，跳过

            # 计算过去40天的换手率总和
            shares_outstanding = 100000000  # 假设流通股本为1亿股，需要实际替换
            total_turnover = sum(data['volume'][-40:]) / shares_outstanding
            log.info(f"股票 {stock} 过去两个月的总换手率 {total_turnover}")

            if total_turnover < g.turnover_threshold:
                log.info(f"股票 {stock} 过去两个月的总换手率 {total_turnover} 小于50%，跳过")
                continue  # 未达到50%换手，跳过

            # 检查最近三天涨幅
            last_3_days = data['close'][-3:]
            log.info(f"股票 {stock} 最近三天价格: {last_3_days}")
            if not (last_3_days[-1] > last_3_days[-2] > last_3_days[-3]):
                log.info(f"股票 {stock} 最近三天没有连续上涨，跳过")
                continue  # 最近三天未连续上涨，跳过

            # 新增条件：检查当前价格是否小于过去30天的最高价的90%
            max_30_days = max(data['high'][-30:])
            log.info(f"股票 {stock} 当前价格: {data['close'][-1]}，最大30天价格: {max_30_days}")
            if data['close'][-1] < max_30_days * 0.90:
                log.info(f"股票 {stock} 当前价格小于过去30天的最高价的90%，跳过")
                continue  # 当前价格小于最高价的90%，跳过

            # 计算买入股票的数量，确保是100的整数倍
            cash_per_stock = context.portfolio.available_cash / len(g.stock_pool)
            price = data['close'][-1]
            qty = cash_per_stock // price  # 计算买入数量
            qty = (qty // 100) * 100  # 确保是100的倍数
            log.info(f"股票 {stock} 计算买入数量为: {qty}，价格为: {price}")

            if qty > 0:
                order(stock, qty)  # 进行买入操作
                g.positions[stock] = 0  # 持仓第0天
                log.info(f"买入 {stock}，当前价格 {data['close'][-1]}，买入数量 {qty}")

        except Exception as e:
            log.error(f"股票 {stock} 数据处理失败: {e}")

    # 检查持仓周期
    to_sell = []
    for stock, days in g.positions.items():
        if days >= g.holding_days:
            order_target(stock, 0)  # 平仓
            to_sell.append(stock)
            log.info(f"平仓 {stock}，持仓 {days} 天")
    # 更新持仓时间
    for stock in g.positions:
        g.positions[stock] += 1
    for stock in to_sell:
        del g.positions[stock]