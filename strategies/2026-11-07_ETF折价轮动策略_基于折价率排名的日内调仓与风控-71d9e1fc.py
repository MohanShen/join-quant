# Clone from JoinQuant
# postId: 71d9e1fc28c1b45498c8d624a80a634a
# backtestId: 8f31c3cc7abfb089e93fa4f9f119e221
# title: ETF折价轮动策略：基于折价率排名的日内调仓与风控

from jqdata import *



def initialize(context):
    # 设置日志级别
    log.set_level('system', 'error')
    # 避免使用未来数据
    set_option("avoid_future_data", True)
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式（真实价格）
    set_option('use_real_price', True)
    # 设置交易成本
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.00025, close_commission=0.00025, min_commission=5), type='fund')
    # 设置滑点
    set_slippage(FixedSlippage(0.001))  # 设置固定滑点为0.1%
    # 每天09:20运行before_market_open函数
    run_daily(before_market_open, '09:20', reference_security='000300.XSHG')
    # 每天09:30运行market_open函数
    run_daily(market_open, '09:30', reference_security='000300.XSHG')
    # 每天收盘后运行风险管理（收盘后执行风控管理，有隔夜风险）
    # run_daily(handle_risk_management, 'after_close', reference_security='000300.XSHG')
    """我改成了早开盘和下午14：59双触发"""
    # 早盘开盘（9:30）触发风控检查
    run_daily(handle_risk_management, time='9:30', reference_security='000300.XSHG')
    # 下午14:59分触发风控检查
    run_daily(handle_risk_management, time='14:59', reference_security='000300.XSHG')

def handle_risk_management(context):
    try:
        # 确保在交易时段内执行
        if not context.trading_state.is_trading:
            return

        for fund in context.portfolio.positions:
            # 获取实时最新价（根据触发时间点动态选择数据源）
            if context.current_dt.hour == 9 and context.current_dt.minute == 30:
                # 早盘使用开盘价（避免集合竞价波动影响）
                current_price = get_price(fund, end_time=context.current_dt, frequency='1m', fields='open', skip_paused=True).iloc[-1]
            else:
                # 尾盘使用最新分钟线收盘价
                current_price = get_price(fund, end_time=context.current_dt, frequency='1m', fields='close', skip_paused=True).iloc[-1]
            
            cost_basis = context.portfolio.positions[fund].avg_cost

            # 止损逻辑（跌至成本价98%）
            if current_price < cost_basis * 0.95:
                log.info(f"止损触发：{fund} @ {context.current_dt}")
                order_target(fund, 0, style=MarketOrderStyle())  # 市价单确保成交

            # 止盈逻辑（涨至成本价102%）
            elif current_price > cost_basis * 1.10:
                log.info(f"止盈触发：{fund} @ {context.current_dt}")
                order_target(fund, 0)

    except Exception as e:
        log.error(f"风控异常：{e}")
def before_market_open(context):
    try:
        # 获取所有ETF基金
        fund_list = get_all_securities(['etf'], context.previous_date).index.tolist()

        # 获取历史数据
        high_df = history(count=1, unit='1d', field="high", security_list=fund_list).T
        low_df = history(count=1, unit='1d', field="low", security_list=fund_list).T
        volume_df = history(count=1, unit='1d', field="money", security_list=fund_list).T

        # 合并数据
        df = high_df.merge(low_df, left_index=True, right_index=True)
        df = df.merge(volume_df, left_index=True, right_index=True)
        df.columns = ['high_price', 'low_price', 'money']

        # 计算价格波动范围
        df['price_range'] = df['high_price'] - df['low_price']

        # 过滤成交额小于1000万的ETF*******
        """（我这里改为5000万）"""
        # df = df[df['money'] < 1e7]
        df = df[(df['money'] < 2e7)&((df['money'] > 5e6))]

        # 获取单位净值
        df = get_extras('unit_net_value', df.index.tolist(), end_date=context.previous_date, df=True, count=1).T
        df.columns = ['unit_net_value']

        # 存储到全局变量
        g.fund_list = df
    except Exception as e:
        log.error("Error in before_market_open: {}".format(e))

# 开盘时运行函数
def market_open(context):
    try:
        df = g.fund_list
        current = get_current_data()

        # 获取最新价
        df['last_price'] = [current[c].last_price for c in df.index.tolist()]

        # 计算溢价率（实际为折价率）
        df['premium'] = (df['last_price'] / df['unit_net_value'] - 1) * 100

        # 按折价率排序并过滤折价ETF（premium<0）
        df = df.sort_values(['premium'], ascending=True)
        df = df[df['premium'] < 0]

        #选择折价率最大的前5只ETF（premium值最小）
        """这里我改成了10支ETF，以求能够尽可能多地成交*****************************************************************"""
        selected_funds = df.head(10)
        order_fund = selected_funds.index.tolist()
        g.max_position = len(order_fund)

        log.info("Selected funds: {}".format(order_fund))

        # 卖出不在选定列表中的持仓
        for fund in context.portfolio.positions.keys():
            if fund not in order_fund:
                order_target_value(fund, 0)

        # 计算权重分配（使用折价率绝对值作为权重）
        weights = selected_funds['premium'].abs().tolist()  # 取绝对值计算权重
        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = 1e-9  # 防止除零错误

        available_cash = context.portfolio.available_cash

        # 按权重比例分配资金
        for fund, weight in zip(order_fund, weights):
            target_value = available_cash * (weight / total_weight)
            order_target_value(fund, target_value)
    except Exception as e:
        log.error("Error in market_open: {}".format(e))
# 风险管理：设置止损和止盈
# def handle_risk_management(context):
#     try:
#         for fund in context.portfolio.positions.keys():
#             current_price = context.portfolio.positions[fund].price
#             cost_basis = context.portfolio.positions[fund].avg_cost

#             # 设置止损线：例如，当价格跌破成本价的98%时止损
#             if current_price < cost_basis * 0.98:
#                 log.info(f"Stop loss triggered for {fund}")
#                 order_target_value(fund, 0)

#             # 设置止盈线：例如，当价格涨到成本价的102%时止盈
#             if current_price > cost_basis * 1.02:
#                 log.info(f"Take profit triggered for {fund}")
#                 order_target_value(fund, 0)
#     except Exception as e:
#         log.error("Error in handle_risk_management: {}".format(e))