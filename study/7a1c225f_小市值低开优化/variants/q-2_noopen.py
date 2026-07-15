# Clone from JoinQuant
# postId: 7a1c225fd35f3d72569a2a9262aba3ae
# backtestId: 330aa01e25785725cf3847d900de2ab3
# title: 小市值低开优化-10年年化近100%，回撤15%

# 克隆自聚宽文章：https://www.joinquant.com/post/65607
# 标题：十年2000倍，小市值策略，无未来（带详细注释）
# 作者：hpkiller

# 克隆自聚宽文章：
# https://www.joinquant.com/post/60436  —— 低开小市值-年化120+增加可交易性筛选（作者：子匀）
# https://www.joinquant.com/post/45324  —— 低开买入小市值策略（剥头皮策略）3.0 总结（作者：langcheng999）

import math
from jqdata import *   # 导入聚宽平台数据接口
import pandas as pd

# ========== 初始化函数 ==========
def initialize(context):
    """
    初始化策略运行环境
    """
    log.set_level('order', 'warning')  # 设置日志级别，仅显示警告及以上级别的订单日志

    # 使用真实价格（避免使用未来数据模拟成交价）
    set_option('use_real_price', True)
    # 避免未来数据（保证回测不会使用未来信息）
    set_option("avoid_future_data", True)
    
    # 设置固定滑点：0.2%（模拟实盘买卖价差）
    set_slippage(PriceRelatedSlippage(0.002))
    # 设置交易佣金：买入0.02%，卖出0.07%，最低5元
    set_commission(PerTrade(buy_cost=0.0002, sell_cost=0.0007, min_cost=5))
    
    # 设置基准指数为国证2000（399303.XSHE），用于绩效比较
    set_benchmark('399303.XSHE')
    
    # 配置参数
    g.avoid_months = [1, 4]        # 可设置跳过某些月份（如财报季避开1月、4月等）
    g.choice = 1000             # 初筛股票池大小（按市值从小到大取前500只）
    g.target_count = 5         # 目标持仓数量（最多同时持有5只股票）

    # 回测中在9:30执行买卖逻辑（先卖后买，提高资金利用率）
    run_daily(buy, time='9:30:30', reference_security='399303.XSHE')
    
    # 检查是否破开盘价，若是则清仓（防止尾盘跳水）
    run_daily(sell, time='11:30', reference_security='399303.XSHE')
    
    # 执行止盈逻辑（盈利≥5%且未涨停则卖出）
    run_daily(stop_profit, time='14:50', reference_security='399303.XSHE')


# ========== 股票池过滤函数 ==========
def filter_specials(context, stock_list):
    """
    过滤掉不适宜交易的股票：
      - ST/*ST/退市股
      - 涨停或跌停开盘
      - 停牌
      - 科创板（688开头）
    """
    curr_data = get_current_data()  # 获取当前所有股票的实时数据
    filtered = []
    for stock in stock_list:
        cd = curr_data[stock]
        # 跳过以下情况：
        if (
            cd.paused or                 # 停牌
            cd.is_st or                  # ST或*ST
            '退' in cd.name or           # 名称含“退”（退市风险）
            stock.startswith('688') or   # 科创板（流动性差、涨跌幅20%）
            stock.startswith('30') or
            cd.day_open == cd.high_limit or  # 涨停开盘（无法买入）
            cd.day_open == cd.low_limit      # 跌停开盘（通常无反弹空间）
        ):
            continue
        filtered.append(stock)
    return filtered


# ========== 获取初筛股票池 ==========
def get_stocks(context):
    """
    从A股中按市值从小到大选取前 g.choice（969）只股票，再过滤掉特殊股票
    """
    # 查询：股票代码 + 市值，按市值升序，取前 g.choice 只
    q = query(valuation.code, valuation.market_cap).order_by(valuation.market_cap.asc()).limit(g.choice)
    df = get_fundamentals(q)  # 获取基本面数据
    stock_pool = df['code'].tolist()
    return filter_specials(context, stock_pool)  # 过滤不合规股票


# ========== 单只股票买入条件判断 ==========
def is_eligible_for_buy(context, stock, data_today, history):
    """
    判断某只股票是否满足买入条件（剥头皮策略核心逻辑）
    参数：
      - stock: 股票代码
      - data_today: get_current_data() 返回的当日数据
      - history: attribute_history 返回的15日历史数据（numpy.ndarray，非DataFrame）
    返回：True/False
    """
    # 条件1：近5日有任意一天停牌，则跳过
    if max(history['paused'][-5:]) != 0:
        return False

    # 条件2：昨日涨停（可能一字板无法买入），跳过
    if history['close'][-1] == history['high_limit'][-1]:
        return False

    # 条件3：昨日跌停，跳过
    if history['close'][-1] == history['low_limit'][-1]:
        return False

    # 提取关键价格
    today_open = data_today[stock].day_open        # 今日开盘价
    prev_close = history['close'][-1]              # 昨日收盘价
    prev_low = history['low'][-1]                  # 昨日最低价

    # 计算今日开盘涨跌幅（%）
    chg = (today_open - prev_close) / prev_close * 100

    # 条件4：[q-2_noopen ABLATION] 低开入场条件被禁用——不再要求今日开盘 < 昨日最低价 且开盘跌幅>1%。
    # 原逻辑（保留供参考）：if not (today_open < prev_low and chg < -1): return False
    # 现在恒真通过，其它买入条件（停牌/涨跌停/振幅/MA5/未持仓）不变。
    pass

    # 条件5：近4日振幅 ≤ 20%（避免高波动股）
    low4 = min(history['low'][-4:])      # 近4日最低价
    high4 = max(history['high'][-4:])    # 近4日最高价
    amplitude = (high4 - low4) / low4 * 100
    if amplitude > 10:
        return False

    # 条件6：昨日收盘价 > 5日均线（趋势向上） 且 当前未持仓
    ma5 = history['close'][-5:].mean()
    if not (prev_close > ma5) or stock in context.portfolio.positions:
        return False

    return True  # 所有条件满足，可买入


# ========== 买入主函数 ==========
def buy(context):
    """
    执行买入逻辑
    """
    # 跳过指定月份
    if context.current_dt.month in g.avoid_months:
        return

    total_value = context.portfolio.total_value      # 总资产
    available_cash = context.portfolio.available_cash  # 可用现金
    position_count = len(context.portfolio.positions)  # 当前持仓数

    # 资金不足判断：至少要能买1只股票（预留50%总资金用于本策略）
    min_cash_per_stock = total_value * 0.5 / g.target_count
    if available_cash < min_cash_per_stock:
        log.info("可用资金不足，跳过买入")
        return

    # 获取初筛股票池（小市值 + 过滤特殊股）
    stock_pool = get_stocks(context)
    data_today = get_current_data()

    buy_candidates = []  # 初步符合买入条件的股票列表
    # 最多预选：(目标持仓数 - 当前持仓数) * 5，提高候选池多样性
    preselect_limit = (g.target_count - position_count) * 5

    # 遍历股票池，筛选符合条件的标的
    for stock in stock_pool:
        if len(buy_candidates) >= preselect_limit:
            break
        try:
            # 获取最近15日历史数据（关闭df以提升速度）
            hist = attribute_history(
                security=stock,
                count=15,
                unit='1d',
                fields=('close', 'low', 'high', 'paused', 'high_limit', 'low_limit'),
                skip_paused=False,
                df=False,   # 返回numpy.ndarray而非DataFrame，速度更快
                fq='pre'    # 前复权
            )
        except:
            continue  # 数据获取失败则跳过

        # 判断是否满足买入条件
        if is_eligible_for_buy(context, stock, data_today, hist):
            buy_candidates.append(stock)

    if not buy_candidates:
        return

    # ========== 流动性筛选（防止滑点过大） ==========
    try:
        ticks = get_current_tick(security=buy_candidates)  # 获取当前买一档口数据
    except Exception as e:
        log.warn(f"获取 tick 失败: {e}")
        return

    valid_stocks = []
    for stock in buy_candidates:
        tick = ticks.get(stock)
        if not tick:
            continue
        # 安全获取买一价格(a1_p)和买一量(a1_v)
        a1_p = getattr(tick, 'b1_p', None)
        a1_v = getattr(tick, 'b1_v', None)

        # 打印买一档数据信息
        log.info(f"股票: {stock}, 买一价: {a1_p}, 买一量: {a1_v}")

        if a1_p is None or a1_v is None:
            continue
        # 买一档金额 = 价格 × 手数 × 100（1手=100股）
        money = a1_p * a1_v * 100
        log.info(f"9:30:30 买一金额 - {stock}: {money:.2f}")
        if money > 5e4:  # 要求买一档金额 > 5万元（可据资金量调整）
            valid_stocks.append((stock, money))

    if not valid_stocks:
        return

    # 获取候选股的总市值（单位：亿元）
    candidate_codes = [s for s, m in valid_stocks]
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(candidate_codes))
    df_cap = get_fundamentals(q)
    # 转为字典 {code: market_cap}
    cap_dict = df_cap.set_index('code')['market_cap'].to_dict()

    def get_ratio(item):
        stock_code, buy1_money = item
        # 获取市值（亿元），转为元
        m_cap = cap_dict.get(stock_code, 0) * 1e8
        if m_cap <= 0:
            return -1
        # 返回 买一金额 / 总市值
        return buy1_money / m_cap

    # 按 (买一档金额 / 总市值) 降序排序
    valid_stocks.sort(key=get_ratio, reverse=True)

    # 计算还需买入几只
    needed = g.target_count - position_count
    final_buy_list = [s for s, _ in valid_stocks[:needed]]

    if not final_buy_list:
        return

    # ========== 分配资金并下单 ==========
    cash_per_stock = available_cash / len(final_buy_list)
    for stock in final_buy_list:
        if open_position(context, stock, cash_per_stock):
            pass  # 成功下单


# ========== 尾盘清仓逻辑 ==========
def sell(context):
    """
    若当前价 < 今日开盘价，则清仓（防止日内亏损扩大）
    """
    data_today = get_current_data()
    for stock, pos in list(context.portfolio.positions.items()):
        # 仅对可卖数量大于0的股票进行判断（满足T+1）
        if pos.sellable_amount <= 0:
            continue
            
        today_open = data_today[stock].day_open
        last_price = data_today[stock].last_price
        if last_price == data_today[stock].low_limit:
            log.info(f"{stock} 跌停卖出失败")
            continue
        if last_price < today_open:
            close_position(stock)


# ========== 止盈逻辑 ==========
def stop_profit(context):
    """
    若盈利 ≥5% 且 股票未涨停，则止盈卖出
    """
    data_today = get_current_data()
    for stock, pos in context.portfolio.positions.items():
        # 仅对可卖数量大于0的股票进行判断（满足T+1）
        if pos.sellable_amount <= 0:
            continue
            
        curr = data_today[stock]
        # 涨停则保留（可能继续冲高）
        if curr.last_price == curr.high_limit:
            continue
        # 计算浮盈百分比
        profit_pct = (curr.last_price - pos.avg_cost) / pos.avg_cost * 100
        if profit_pct >= 5:
            close_position(stock)


# ========== 交易辅助函数 ==========
def order_target_value_(security, value):
    """
    封装 order_target_value，增加日志输出
    """
    if value == 0:
        log.debug(f"Selling out {security} {get_security_info(security).display_name}")
    else:
        log.debug(f"Order {security} to value {value:.2f}")
    return order_target_value(security, value)


def open_position(context, security, value):
    """
    下单买入指定市值的股票，返回是否成功成交
    """
    order = order_target_value_(security, value)
    return order is not None and order.filled > 0


def close_position(security):
    """
    清仓某只股票，返回是否成功（完全成交）
    """
    order = order_target_value_(security, 0)
    return order is not None and order.status == OrderStatus.held and order.filled == order.amount

# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# research/harness.md §2 — force zero slippage + frozen commission regardless of
# what the raw strategy sets, even if it re-sets costs every bar.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
except NameError:
    pass
# ===== END OVERRIDE =====
