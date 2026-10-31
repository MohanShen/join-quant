# u-4 variant of study/资产配置/baseline.py
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
    # u-4: ONLY trading change vs baseline.py — textbook 5-class pool, 20% each
    g.etf_weights = {
        '518880.XSHG': 0.2,   # 黄金ETF
        '513100.XSHG': 0.2,   # 纳指ETF
        '510300.XSHG': 0.2,   # 沪深300ETF
        '511260.XSHG': 0.2,   # 十年国债ETF
        '159985.XSHE': 0.2,   # 豆粕ETF
    }

    g.etf_names = {
        '518880.XSHG': '黄金ETF',
        '513100.XSHG': '纳指ETF',
        '510300.XSHG': '沪深300ETF',
        '511260.XSHG': '十年国债ETF',
        '159985.XSHE': '豆粕ETF',
    }

    # listing-date check (pre-run fact): every pool name must list before the TRAIN start
    g.listcheck_fail = []
    for _s in g.etf_weights:
        try:
            _sd = get_security_info(_s).start_date
        except Exception as _e:
            _sd = None
        log.error('LISTCHECK %s start_date=%s' % (_s, _sd))
        if _sd is None or str(_sd) >= '2024-01-01':
            g.listcheck_fail.append(_s)
    if g.listcheck_fail:
        log.error('LISTCHECK FAIL %s -- run will not trade' % ','.join(g.listcheck_fail))


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
    if g.listcheck_fail:
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

# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
