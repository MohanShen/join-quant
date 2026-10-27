# Clone from JoinQuant
# postId: 53562455d19fda7b3df239f30a7d468c
# backtestId: b684080c722b6758333e99e159d3576b
# title: 一字千金-小市值轮动策略

# 一字千金 · 汉字玄学小市值轮动策略
from jqdata import *
from kuanke.wizard import *
import math

CHINESE_CHARS = frozenset('爱我中华')
# ══════════════════════════ 一、初始化 ══════════════════════════

def initialize(context):
    # ---- 平台设置 ----
    set_benchmark('000300.XSHG')                      # 基准：沪深300
    set_slippage(FixedSlippage(0.005))                # 滑点：千分之五
    set_option('use_real_price', True)                # 真实价格交易（动态复权）
    set_option('order_volume_ratio', 1)               # 成交量比例
    set_option('avoid_future_data', True)
    # 买入佣金万三，卖出佣金万三 + 千分之一印花税，每笔最低 5 元
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                             open_commission=0.0003, close_commission=0.0003,
                             min_commission=5), type='stock')
    log.set_level('order', 'info')

    set_params()
    init_containers()

    # ---- 定时任务 ----
    run_daily(build_candidate_pool, '9:30')       # 股票池初筛
    run_daily(build_trade_plan, '9:30')           # 选股 → 生成买卖列表
    run_daily(execute_trade_plan, '9:35')         # 先卖后买
    run_daily(sell_if_limit_up_opened, '14:50')   # 涨停开板 → 卖出
    run_daily(report_after_close, 'after_close')  # 收盘统计


# ══════════════════ 二、参数与容器（要改配置看这里） ══════════════════

def set_params():
    
    # ---- 持仓与选股 ----
    g.max_hold_stocknum   = 10     # 最大持仓数
    g.sell_rank_threshold = 11     # 持仓股市值排名跌出前 N 名即卖出
    g.pick_pool_size      = 20     # 候选池大小：按总市值升序取前 N 只
    g.max_market_cap      = 1000   # 候选股总市值上限（亿元）

    # ---- 股票池 ----
    g.security_universe_index = ['all_a_securities']  # 全A；
    g.blacklist = []

    # ---- 初筛开关 ----
    g.filter_paused   = True    # 过滤停牌
    g.filter_delisted = True    # 过滤退市
    g.filter_st       = True    # 过滤 ST
    g.only_st         = False   # True 则只保留 ST（优先级高于 g.filter_st）

    # ---- 交易行为 ----
    g.sell_will_buy = True    # False = 当天要买的股票不卖
    g.filter_holded = False   # False = 已持有的股票不重复买入


def init_containers():
    g.sell_stock_list    = []   # 今日卖出列表
    g.buy_stock_list     = []   # 今日买入列表
    g.yesterday_ZT_list  = []   # 昨日涨停而豁免卖出的持仓，14:50 复查
    g.paused             = []   # 持仓中的停牌股（每轮末尾刷新，供下一轮跳过）
    g.check_out_lists    = []   # 初筛后的股票池


# ══════════════════════════ 三、选股 ══════════════════════════

def build_candidate_pool(context):
    """股票池初筛：全A → 过滤 ST / 停牌 / 退市 / 黑名单"""
    pool = get_security_universe(context, g.security_universe_index)
    pool = st_filter(context, pool)
    pool = paused_filter(context, pool)
    pool = delisted_filter(context, pool)
    if g.blacklist:
        pool = [s for s in pool if s not in g.blacklist]
    g.check_out_lists = pool


def build_trade_plan(context):
    """选股并生成买卖列表 —— 策略核心，改选股条件改这里"""
    g.sell_stock_list = []
    g.buy_stock_list  = []

    # ───────────── 选股区（可自定义编辑） ─────────────
    # 1) 只保留股票简称里含汉字的股票
    curr_data = get_current_data()
    candidates = [s for s in g.check_out_lists
                  if has_chinese_char(curr_data[s].name)]
    # 2) 按总市值升序，取市值最小的 g.pick_pool_size 只
    q = query(valuation.code, valuation.market_cap).filter(
            valuation.code.in_(candidates),
            valuation.market_cap <= g.max_market_cap,
        ).order_by(valuation.market_cap.asc()).limit(g.pick_pool_size)
    stockset = list(get_fundamentals(q)['code'])
    # ───────────── 选股区结束 ─────────────

    # 持仓处理：市值排名掉出前 g.sell_rank_threshold 名 → 卖出；但昨日涨停的豁免
    g.yesterday_ZT_list = []
    for stock in context.portfolio.positions:
        if stock in g.paused:                              # 停牌股不动
            continue
        if stock in stockset[:g.sell_rank_threshold]:      # 仍在持有区间内
            continue
        if _is_limit_up_on_yestoday(context, stock):
            g.yesterday_ZT_list.append(stock)              # 昨日涨停 → 暂缓，14:50 看是否开板
        else:
            g.sell_stock_list.append(stock)

    g.buy_stock_list = [s for s in stockset if s not in g.sell_stock_list]

    # 刷新停牌名单
    g.paused = [s for s in context.portfolio.positions if curr_data[s].paused]

    log.info('卖出列表:', g.sell_stock_list)
    log.info('购买列表:', g.buy_stock_list)


# ══════════════════════════ 四、交易 ══════════════════════════

def execute_trade_plan(context):
    """先卖后买"""
    buy_lists = high_limit_filter(context, g.buy_stock_list)  # 已涨停的不买
    log.info('购买列表最终', buy_lists)
    sell_positions(context, buy_lists)
    buy_positions(context, buy_lists)


def sell_positions(context, buy_lists):
    """按卖出列表清仓（只对真实持仓下单）"""
    held = set(context.portfolio.positions)
    sell_lists = [s for s in g.sell_stock_list if s in held]
    if not g.sell_will_buy:
        sell_lists = [s for s in sell_lists if s not in buy_lists]
    for stock in sell_lists:
        order_target_value(stock, 0)


def buy_positions(context, buy_lists):
    """等权买入，持有上限 g.max_hold_stocknum"""
    if not g.filter_holded:      # 已持有的不重复买
        buy_lists = [s for s in buy_lists if s not in context.portfolio.positions]
    buy_lists = buy_lists[:g.max_hold_stocknum - len(context.portfolio.positions)]

    for stock in buy_lists:
        position_count = len(context.portfolio.positions)
        if g.max_hold_stocknum > position_count:
            value = context.portfolio.cash / (g.max_hold_stocknum - position_count)
            if context.portfolio.positions[stock].total_amount == 0:
                order_target_value(stock, value)


# ══════════════════════ 五、涨停股的处理 ══════════════════════

def sell_if_limit_up_opened(context):
    """14:50：昨日涨停而豁免卖出的持仓，若今日未封在涨停板则卖出"""
    for stock in g.yesterday_ZT_list:
        if not _is_limit_up_now(stock):
            order_target_value(stock, 0)
            log.info('涨停打开，卖出:', stock)


# ══════════════════════════ 六、收盘统计 ══════════════════════════

def report_after_close(context):
    for _trade in get_trades().values():
        log.info('成交记录：' + str(_trade))
    log.info('今日账户总资产：%s' % round(context.portfolio.total_value, 2))
    # 记录当前仓位百分比
    record(P=(100 - math.ceil(context.portfolio.available_cash / context.portfolio.total_value * 100)))


# ═══════════════════════ 七、公用函数 ═══════════════════════




def has_chinese_char(name):
    """股票简称里是否含汉字"""
    return not CHINESE_CHARS.isdisjoint(name)


def _is_limit_up_on_yestoday(context, stock):
    """昨日是否涨停：昨收 == 昨日涨停价"""
    df = get_price(stock, end_date=context.previous_date, frequency='daily',
                   fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
    return df['close'].iloc[0] == df['high_limit'].iloc[0]


def _is_limit_up_now(stock):
    """当前时点：是否仍封在涨停板"""
    bar = attribute_history(stock, count=1, unit='1m',
                            fields=['close', 'high_limit'], fq='pre')
    return bar['close'][-1] == bar['high_limit'][-1]


## 过滤停牌股票
def paused_filter(context, security_list):
    if g.filter_paused:
        current_data = get_current_data()
        security_list = [s for s in security_list if not current_data[s].paused]
    return security_list


## 过滤退市股票
def delisted_filter(context, security_list):
    if g.filter_delisted:
        current_data = get_current_data()
        security_list = [s for s in security_list
                         if not (('退' in current_data[s].name) or ('*' in current_data[s].name))]
    return security_list


## 过滤 ST 股票
def st_filter(context, security_list):
    current_data = get_current_data()
    if g.only_st:
        security_list = [s for s in security_list if current_data[s].is_st]
    elif g.filter_st:
        security_list = [s for s in security_list if not current_data[s].is_st]
    return security_list


## 过滤开盘即涨停的股票（买不到）
def high_limit_filter(context, security_list):
    current_data = get_current_data()
    # return [s for s in security_list if not (current_data[s].day_open >= current_data[s].high_limit)]
    return [s for s in security_list if not (current_data[s].last_price >= current_data[s].high_limit)]


## 获取股票池
def get_security_universe(context, index_list):
    pool = []
    for s in index_list:
        if s == 'all_a_securities':
            pool += list(get_all_securities(['stock'], context.current_dt.date()).index)
        else:
            pool += get_index_stocks(s)
    return sorted(set(pool))
