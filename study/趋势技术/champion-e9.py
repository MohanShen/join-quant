# Clone from JoinQuant
# postId: 9befa9b8dee359408631307f021fed6c
# backtestId: 048448df645ff8c2737c7214d3bd4e5c
# title: 十日均线策略

# 克隆自聚宽文章：https://www.joinquant.com/post/664
# 标题：单均线10日策略 中信证券 06----16
# 作者：Trafalgar2018

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:中信证券)
    g.security = '600030.XSHG'
    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe([g.security])
    #这里添加一个上证指数作为基准方便回测后比较收益回撤
    set_benchmark('000001.XSHG')
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    # 取得过去十天的平均价格
    average_price = data[security].mavg(10)
    # 取得上一时间点价格
    current_price = data[security].price
    # 取得当前的现金
    cash = context.portfolio.cash

    # 如果上一时间点价格高出十天平均价, 则全仓买入
    if current_price > average_price:
        # 计算可以买多少只股票
        number_of_shares = int(cash/current_price)
        # 购买量大于0时，下单
        if number_of_shares > 0:
            # 买入股票
            order(security, +number_of_shares)
            # 记录这次买入
            log.info("Buying %s" % (security))
    # 如果上一时间点价格低于十天平均价, 则空仓卖出
    elif current_price < average_price and context.portfolio.positions[security].amount > 0:
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security))
    # 画出上一时间点的价格
    record(stock_price=data[security].price)


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
