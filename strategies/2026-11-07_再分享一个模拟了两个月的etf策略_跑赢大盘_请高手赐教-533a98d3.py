# Clone from JoinQuant
# postId: 533a98d3307e0fadbc9196e50923bee3
# backtestId: ca8b981a22006cc80705ec891f3c9f23
# title: 再分享一个模拟了两个月的etf策略，跑赢大盘，请高手赐教！

from jqdata import *
def initialize(context):
    log.set_level('system', 'error')
    set_option("avoid_future_data", True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.00025,
                            close_commission=0.00025, min_commission=5),
                  type='fund')
    set_slippage(FixedSlippage(0.004))

    run_daily(before_market_open, '09:20', reference_security='000300.XSHG')
    run_daily(process_after_auction, '09:25', reference_security='000300.XSHG')
    run_daily(market_open, '09:30', reference_security='000300.XSHG')

    g.selected_funds_data = None
    g.hold_list = []
    g.buy_list = []
    g.sell_list = []
    g.target_values = {}
    g.trading_plan = None

    g.min_discount = -0.1       # 最低参与折价阈值
    g.max_abs_discount = -5.0   # 折价小于‑5%视为异常，直接过滤
    g.min_money = 6e6           # 成交额下限600万
    g.max_money = 25e6
    g.pick_num = 2              # 【方案B核心】选折价最优2只ETF

def before_market_open(context):
    try:
        fund_list = get_all_securities(['etf'], context.previous_date).index.tolist()
        high_df = history(count=1, unit='1d', field="high", security_list=fund_list).T
        low_df = history(count=1, unit='1d', field="low", security_list=fund_list).T
        volume_df = history(count=1, unit='1d', field="money", security_list=fund_list).T
        df = high_df.merge(low_df, left_index=True, right_index=True)
        df = df.merge(volume_df, left_index=True, right_index=True)
        df.columns = ['high_price', 'low_price', 'money']
        df = df[(df['money'] < g.max_money) & (df['money'] > g.min_money)]
        if df.empty:
            log.warning("before_market_open：没有符合成交额条件ETF")
            g.selected_funds_data = None
            return
        unit_net_df = get_extras('unit_net_value', df.index.tolist(),
                                end_date=context.previous_date, df=True, count=1).T
        unit_net_df.columns = ['unit_net_value']
        df = df.merge(unit_net_df, left_index=True, right_index=True)
        g.selected_funds_data = df
        log.info(f"before_market_open筛选完成：{len(df)}只ETF")
    except Exception as e:
        log.error(f"before_market_open异常: {e}")
        g.selected_funds_data = None

def process_after_auction(context):
    try:
        g.hold_list = []
        g.buy_list = []
        g.sell_list = []
        g.target_values = {}
        if g.selected_funds_data is None or g.selected_funds_data.empty:
            log.warning("无基金数据，跳过今日信号")
            g.trading_plan = None
            return
        df = g.selected_funds_data.copy()
        current_data = get_current_data()
        current_positions = list(context.portfolio.positions.keys())

        valid_funds = []
        open_prices = []
        for fund in df.index.tolist():
            if not current_data[fund].paused:
                open_price = current_data[fund].day_open
                if open_price is not None and open_price > 0:
                    valid_funds.append(fund)
                    open_prices.append(open_price)
        if len(valid_funds) == 0:
            log.warning("无有效可交易ETF")
            g.trading_plan = None
            return
        df = df.loc[valid_funds].copy()
        df['open_price'] = open_prices

        df['premium'] = (df['open_price'] / df['unit_net_value'] - 1) * 100

        log.info(f"候选ETF折价预览:\n{df[['open_price','unit_net_value','premium']].sort_values('premium').head(10)}")

        # 过滤：折价在 [g.max_abs_discount , g.min_discount] 区间
        df = df.sort_values(['premium'], ascending=True)
        df = df[(df['premium'] < 0) &
                (df['premium'] <= g.min_discount) &
                (df['premium'] >= g.max_abs_discount)]

        if df.shape[0] < 1:
            log.warning(f"没有满足折价阈值的ETF，今日不交易")
            g.trading_plan = None
            return

        # 取Top N只
        selected_funds = df.head(g.pick_num)
        order_fund = selected_funds.index.tolist()
        log.info(f"✅生成交易信号，选中:{order_fund}，折价：{list(round(v,2) for v in selected_funds['premium'].values)}")

        hold_list = []
        buy_list = []
        sell_list = []
        # 需要卖出：持仓不在本次选中列表全部清掉
        for fund in current_positions:
            if fund not in order_fund:
                sell_list.append(fund)
        # 区分持有/新建
        for fund in order_fund:
            if fund in current_positions:
                hold_list.append(fund)
            else:
                buy_list.append(fund)

        current_cash = context.portfolio.available_cash
        # 双票：资金平均分配
        target_values = {}
        per_alloc = current_cash / len(order_fund)
        for fund in order_fund:
            target_values[fund] = per_alloc

        g.hold_list = hold_list
        g.buy_list = buy_list
        g.sell_list = sell_list
        g.target_values = target_values
        g.trading_plan = {
            'signal_time': context.current_dt,
            'selected_funds': order_fund,
            'sell_list': sell_list,
            'buy_list': buy_list,
            'hold_list': hold_list,
            'target_values': target_values,
            'selected_funds_df': selected_funds[['open_price','unit_net_value','premium']],
            'current_cash': current_cash,
        }
    except Exception as e:
        log.error(f"process_after_auction异常: {e}")
        g.trading_plan = None

def market_open(context):
    try:
        if g.trading_plan is None:
            return
        current_data = get_current_data()
        sell_list = g.trading_plan['sell_list']
        if sell_list:
            log.info(f"📤执行卖出 {sell_list}")
            for fund in sell_list:
                if current_data[fund].paused:
                    log.warning(f"{fund}停牌跳过卖出")
                    continue
                pos = context.portfolio.positions[fund]
                if pos.total_amount > 0:
                    order(fund, -pos.total_amount)

        buy_list = g.trading_plan['buy_list']
        if buy_list:
            available_cash = context.portfolio.available_cash
            log.info(f"📥卖出后真实可用现金：{available_cash:.2f}")
            if available_cash < 1000:
                log.warning("现金不足，跳过买入")
                g.trading_plan = None
                return
            target_values = g.trading_plan['target_values']
            for fund in buy_list:
                if current_data[fund].paused:
                    log.warning(f"{fund}停牌跳过买入")
                    continue
                price = current_data[fund].last_price
                if price <= 0:
                    continue
                target_val = target_values[fund]
                buy_amt = int(target_val / price /100)*100
                if buy_amt < 100:
                    buy_amt = 100
                if buy_amt * price <= available_cash:
                    order(fund, buy_amt)
                    log.info(f"下单买入 {fund} 数量 {buy_amt}")
                else:
                    log.warning(f"{fund}资金不足买1手，跳过")
        g.trading_plan = None
    except Exception as e:
        log.error(f"market_open异常:{e}")
