# Clone from JoinQuant
# postId: e70f8129608b88fea6b49313779eb1fa
# backtestId: 2b5fda543ae8769ab84529a55920a0dc
# title: ETF小回撤优化，稳定！

# 克隆自聚宽文章：https://www.joinquant.com/post/63147
# 标题：ETF套利，年化45-266%，回撤小于7%
# 作者：通常
# 修改版：整合流动性约束+限价单+折价收敛退出+资金逐只扣减

from jqdata import *
import datetime


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
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.00025,
                             close_commission=0.00025, min_commission=5), type='fund')
    # 设置滑点（实盘摩擦 0.3%）
    set_slippage(FixedSlippage(0.003))

    # 每天09:20运行before_market_open函数
    run_daily(before_market_open, '09:20', reference_security='000300.XSHG')
    # 每天09:30运行market_open函数
    run_daily(market_open, '09:30', reference_security='000300.XSHG')
    # 早盘开盘（9:30）触发风控检查
    run_daily(handle_risk_management, time='9:30', reference_security='000300.XSHG')
    # 下午14:59分触发风控检查
    run_daily(handle_risk_management, time='14:59', reference_security='000300.XSHG')


def before_market_open(context):
    try:
        # 获取所有ETF基金
        fund_list = get_all_securities(['etf'], context.previous_date).index.tolist()

        # 获取历史数据（3日）
        high_df = history(count=1, unit='3d', field="high", security_list=fund_list).T
        low_df = history(count=1, unit='3d', field="low", security_list=fund_list).T
        volume_df = history(count=1, unit='3d', field="money", security_list=fund_list).T

        # 合并数据
        df = high_df.merge(low_df, left_index=True, right_index=True)
        df = df.merge(volume_df, left_index=True, right_index=True)
        df.columns = ['high_price', 'low_price', 'money']

        # 计算价格波动范围
        df['price_range'] = df['high_price'] - df['low_price']

        # 流动性过滤：成交额 500万~2000万
        df = df[(df['money'] > 5e6) & (df['money'] < 2e7)]

        # 获取单位净值（T-1）
        df = get_extras('unit_net_value', df.index.tolist(),
                        end_date=context.previous_date, df=True, count=1).T
        df.columns = ['unit_net_value']

        # 存储到全局变量
        g.fund_list = df
    except Exception as e:
        log.error("Error in before_market_open: {}".format(e))


def market_open(context):
    try:
        df = g.fund_list
        current = get_current_data()

        # 获取最新价
        df['last_price'] = [current[c].last_price for c in df.index.tolist()]

        # 计算折价率
        df['premium'] = (df['last_price'] / df['unit_net_value'] - 1) * 100

        # 按折价率排序，选折价最大的
        df = df.sort_values(['premium'], ascending=True)
        df = df[df['premium'] < 0]

        # 选前8只
        selected_funds = df.head(8)
        order_fund = selected_funds.index.tolist()
        g.max_position = len(order_fund)

        log.info("Selected funds: {}".format(order_fund))

        # 卖出不在选定列表中的持仓
        for fund in list(context.portfolio.positions.keys()):
            if fund not in order_fund:
                order_target_value(fund, 0)

        if not order_fund:
            return

        # 计算权重（折价率绝对值）
        weights = selected_funds['premium'].abs().tolist()
        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = 1e-9

        # ---------- 流动性约束参数 ----------
        available_cash = context.portfolio.available_cash
        max_single_pct = 0.15          # 单只最多占总资金15%
        max_adv_pct = 0.05            # 单笔最多占日均成交额5%
        max_total_utilization = 0.90  # 最多用90%可用资金

        # 获取选中ETF的5日日均成交额
        adv_df = history(
            count=5, unit='1d', field='money',
            security_list=order_fund
        )
        adv = adv_df.mean()

        total_allocated = 0.0
        max_total_cash = available_cash * max_total_utilization

        for fund, weight in zip(order_fund, weights):
            if total_allocated >= max_total_cash:
                break

            # 基础权重分配
            raw_alloc = available_cash * (weight / total_weight)

            # 约束1：单只不超过总资金15%
            cap_by_position = available_cash * max_single_pct

            # 约束2：单只不超过日均成交额5%
            adv_value = adv.get(fund, 0)
            if adv_value > 0:
                cap_by_liquidity = adv_value * max_adv_pct
            else:
                cap_by_liquidity = 5e6  # 无数据默认500万上限

            # 约束3：剩余可用额度
            cap_by_remaining = max_total_cash - total_allocated

            # 取最小值
            alloc = min(raw_alloc, cap_by_position, cap_by_liquidity, cap_by_remaining)

            if alloc < 10000:  # 低于1万不买
                continue

            order_target_value(fund, alloc)
            total_allocated += alloc

            log.info("买入 {}: 分配 {:.0f} / 权重 {:.2f} / 日均成交 {:.0f}".format(
                fund, alloc, weight, adv_value))

    except Exception as e:
        log.error("Error in market_open: {}".format(e))


def handle_risk_management(context):
    try:
        if not context.trading_state.is_trading:
            return

        # 获取5日日均成交额（用于流动性再平衡）
        positions_list = list(context.portfolio.positions.keys())
        if positions_list:
            adv_df = history(
                count=5, unit='1d', field='money',
                security_list=positions_list
            )
            adv = adv_df.mean()
        else:
            adv = {}

        for fund in list(context.portfolio.positions.keys()):
            pos = context.portfolio.positions[fund]
            cost_basis = pos.avg_cost

            if cost_basis <= 0:
                continue

            # 获取当前价格
            if context.current_dt.hour == 9 and context.current_dt.minute == 30:
                price_series = get_price(fund, end_time=context.current_dt,
                                         frequency='1m', fields='open', skip_paused=True)
                current_price = price_series.iloc[-1] if len(price_series) > 0 else cost_basis
            else:
                price_series = get_price(fund, end_time=context.current_dt,
                                         frequency='1m', fields='close', skip_paused=True)
                current_price = price_series.iloc[-1] if len(price_series) > 0 else cost_basis

            holding_ret = current_price / cost_basis - 1

            # ---- 退出逻辑 ----
            # 优先级1：折价收敛（收益≥0 即走）
            if holding_ret >= 0:
                log.info("折价收敛离场：{} 收益 {:.2%} @ {}".format(
                    fund, holding_ret, context.current_dt))
                limit_price = current_price * 0.997
                order_target(fund, 0, style=LimitOrderStyle(limit_price))

            # 优先级2：止损 5%（兜底）
            elif current_price < cost_basis * 0.95:
                log.info("止损触发：{} @ {} 亏损 {:.2%}".format(
                    fund, context.current_dt, holding_ret))
                limit_price = current_price * 0.997
                order_target(fund, 0, style=LimitOrderStyle(limit_price))

            # 优先级3：止盈 10%（兜底）
            elif current_price > cost_basis * 1.10:
                log.info("止盈触发：{} @ {} 盈利 {:.2%}".format(
                    fund, context.current_dt, holding_ret))
                limit_price = current_price * 0.997
                order_target(fund, 0, style=LimitOrderStyle(limit_price))

            # ---- 流动性再平衡：持仓超日均成交额10%减半仓 ----
            else:
                adv_value = adv.get(fund, 0)
                pos_value = pos.value
                if adv_value > 0 and pos_value > adv_value * 0.10:
                    log.info("流动性再平衡：{} 持仓 {:.0f} 超日均 {:.0f} 的10%，减半".format(
                        fund, pos_value, adv_value))
                    limit_price = current_price * 0.997
                    order_target_value(fund, pos_value * 0.5,
                                       style=LimitOrderStyle(limit_price))

    except Exception as e:
        log.error("风控异常：{}".format(e))