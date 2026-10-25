# Clone from JoinQuant
# postId: 4a67a7b0442764e0d7643831ff08abb6
# backtestId: 974e1227cc1a3c668adb7dcfe6d54dd2
# title: 多仓位再平衡22.77%年化，最大回撤11.17%

from jqdata import *


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    log.set_level('order', 'error')

    # ETF交易成本
    set_slippage(FixedSlippage(0.001))
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5
        ),
        type='fund'
    )

    # 目标ETF及权重
    g.etf_weights = {
        '515450.XSHG': 0.2,   # 红利低波ETF
        '513630.XSHG': 0.2,   # 香港红利低波ETF
        '513100.XSHG': 0.20,   # 纳指ETF
        '518880.XSHG': 0.20,   # 黄金ETF
        '513650.XSHG': 0.20,  # 标普ETF
    }

    g.etf_names = {
        '515450.XSHG': '红利低波ETF',
        '513630.XSHG': '港股红利低波ETF',
        '513100.XSHG': '纳指ETF',
        '518880.XSHG': '黄金ETF',
        '513650.XSHG': '标普ETF',
    }

    # 每10个交易日再平衡一次，近似等于每两周
    g.trade_day_count = 0
    g.rebalance_interval = 10
    g.need_rebalance = False

    run_daily(before_market_open, time='09:00')
    run_daily(rebalance, time='09:40')


def before_market_open(context):
    """
    判断今天是否需要再平衡。
    第一个交易日会直接再平衡，之后每10个交易日再平衡一次。
    """
    if g.trade_day_count % g.rebalance_interval == 0:
        g.need_rebalance = True
        log.info('====== 今日为两周一次ETF再平衡日 ======')
    else:
        g.need_rebalance = False

    g.trade_day_count += 1


def rebalance(context):
    if not g.need_rebalance:
        return

    current_data = get_current_data()
    total_value = context.portfolio.total_value

    log.info('====== 开始ETF再平衡 ======')
    log.info('当前组合总资产：%.2f' % total_value)

    target_values = {}
    for etf, weight in g.etf_weights.items():
        target_values[etf] = total_value * weight

    # 1，先清理非目标持仓
    for stock in list(context.portfolio.positions.keys()):
        if stock not in g.etf_weights:
            log.info('清理非目标持仓：%s' % stock)
            order_target_by_lot(context, stock, 0, current_data)

    # 2，先卖出超配ETF
    for etf, target_value in target_values.items():
        current_value = context.portfolio.positions[etf].value
        if current_value > target_value:
            order_target_by_lot(context, etf, target_value, current_data)

    # 3，再买入低配ETF
    for etf, target_value in target_values.items():
        current_value = context.portfolio.positions[etf].value
        if current_value < target_value:
            order_target_by_lot(context, etf, target_value, current_data)

    log.info('====== ETF再平衡结束 ======')


def order_target_by_lot(context, security, target_value, current_data):
    """
    按目标市值调仓，但买入强制按照100股整数手处理。
    重点解决：
    1，买入数量不能小于100股；
    2，资金不足时，不能让聚宽自动缩单成不足100股；
    3，清仓时允许卖出尾数。
    """

    try:
        data = current_data[security]
    except:
        log.info('无法获取当前数据，跳过：%s' % security)
        return

    if data.paused:
        log.info('%s 停牌，跳过' % security)
        return

    price = data.last_price
    if price is None or price <= 0:
        log.info('%s 当前价格异常，跳过' % security)
        return

    position = context.portfolio.positions[security]
    current_amount = position.total_amount
    closeable_amount = position.closeable_amount

    # 目标股数，买入目标必须向下取整到100股整数手
    if target_value <= 0:
        target_amount = 0
    else:
        target_amount = int(target_value / price / 100) * 100

    diff_amount = target_amount - current_amount

    name = g.etf_names.get(security, security)

    if diff_amount == 0:
        log.info('%s 当前股数 %s，已经接近目标，无需交易' % (name, current_amount))
        return

    # =========================
    # 卖出逻辑
    # =========================
    if diff_amount < 0:
        need_sell_amount = current_amount - target_amount

        if closeable_amount <= 0:
            log.info('%s 当前无可卖数量，跳过卖出' % name)
            return

        sell_amount = min(need_sell_amount, closeable_amount)

        # 如果是清仓，允许不足100股的尾数卖出
        if target_amount == 0:
            final_target_amount = current_amount - sell_amount
            if final_target_amount < 0:
                final_target_amount = 0

            log.info(
                '%s 清仓/减仓：当前股数 %s，目标股数 %s，卖出股数 %s' %
                (name, current_amount, final_target_amount, sell_amount)
            )
            order_target(security, final_target_amount)
            return

        # 如果不是清仓，普通减仓按100股整数手卖
        sell_amount = int(sell_amount / 100) * 100

        if sell_amount < 100:
            log.info('%s 本次减仓不足100股，跳过' % name)
            return

        final_target_amount = current_amount - sell_amount

        log.info(
            '%s 减仓：当前股数 %s，目标股数 %s，卖出股数 %s' %
            (name, current_amount, final_target_amount, sell_amount)
        )
        order_target(security, final_target_amount)
        return

    # =========================
    # 买入逻辑
    # =========================
    if diff_amount > 0:
        # 理论需要买入的股数，已经是100股整数手
        need_buy_amount = diff_amount

        if need_buy_amount < 100:
            log.info('%s 目标买入不足100股，跳过' % name)
            return

        available_cash = context.portfolio.available_cash

        # 预留一点手续费和滑点空间，避免聚宽因为现金不足自动缩成不足100股
        cash_buffer = 1.005
        max_buy_amount = int(available_cash / (price * cash_buffer) / 100) * 100

        if max_buy_amount < 100:
            log.info(
                '%s 可用现金不足以买入100股，跳过。可用现金 %.2f，当前价格 %.3f' %
                (name, available_cash, price)
            )
            return

        buy_amount = min(need_buy_amount, max_buy_amount)
        buy_amount = int(buy_amount / 100) * 100

        if buy_amount < 100:
            log.info('%s 实际买入不足100股，跳过' % name)
            return

        final_target_amount = current_amount + buy_amount

        log.info(
            '%s 买入/补仓：当前股数 %s，目标股数 %s，买入股数 %s，目标市值 %.2f' %
            (name, current_amount, final_target_amount, buy_amount, target_value)
        )
        order_target(security, final_target_amount)
        return