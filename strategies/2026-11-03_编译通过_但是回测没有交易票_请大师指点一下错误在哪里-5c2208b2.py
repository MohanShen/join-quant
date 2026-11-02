# Clone from JoinQuant
# postId: 5c2208b21c710c90e1c8b918fe15dd4f
# backtestId: 888c57635af0fd291711183ba36d409d
# title: 编译通过，但是回测没有交易票，请大师指点一下错误在哪里。

# -*- coding: utf-8 -*-
"""
聚宽 · Tick级「前日真实涨停+竞价涨幅>5%+9.87%触发」
（取消竞价换手，复制即可跑）
"""
from jqdata import *

g.selected = []       # 自选股票池
g.holding = {}        # 持仓股票池
g.done_buy = False    # 是否已完成买入标志

def initialize(context):
    """
    初始化函数，在策略开始时调用一次。
    设置基准、手续费、滑点等参数，并设置定时任务在9:26执行选股逻辑。
    """
    log.set_level('strategy', 'debug')  # 设置日志级别为 debug
    set_benchmark('000001.XSHG')      # 设置基准指数为上证指数
    set_option('use_real_price', True)  # 使用实时价格
    
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                             open_commission=0.0003, close_commission=0.0003,
                             min_commission=5), type='stock')
    
    set_slippage(FixedSlippage(0))  # 滑点归零
    
    # 设置定时任务在9:26执行选股逻辑
    run_daily(select_stocks, time='09:26')

def select_stocks(context):
    """
    选股逻辑，在每天的9:26执行。
    1. 获取所有A股股票列表并筛选出主板非ST股票。
    2. 筛选出前一日涨幅大于9.93%的股票。
    3. 根据开盘价涨幅筛选符合条件的股票加入自选股票池。
    """
    log.info('>>> 选股逻辑入口')
    
    # 1. 主板非 ST
    stocks = get_all_securities(['stock'], date=context.previous_date).index.tolist()  # 获取前一天的所有A股股票代码
    stocks = [s for s in stocks if s[:3] in ('600', '601', '603', '000')]  # 过滤出主板股票（600, 601, 603, 000开头的股票）
    st_map = get_extras('is_st', stocks, count=1, end_date=context.previous_date)  # 获取前一天的ST股票信息
    stocks = [s for s in stocks if not st_map[s][0]]  # 排除ST股票
    
    log.info(f'主板非ST股票数量: {len(stocks)}')
    
    # 2. 前一交易日涨幅大于9.93%
    pre_close = history(1, '1d', 'close', stocks, df=False)  # 获取前一天的收盘价
    curr = get_current_data()  # 获取当前Tick数据
    yes_limit = []
    for s in stocks:
        pre = pre_close[s][0]  # 获取前一天的收盘价
        open_p = curr[s].day_open  # 获取当天的开盘价
        if pre <= 0:
            continue  # 如果前一天的收盘价小于等于0，则跳过
        change = (open_p - pre) / pre * 100  # 计算开盘价涨幅百分比
        log.info(f'{s} 前收 {pre:.2f} 开盘 {open_p:.2f} 涨幅 {change:.2f}%')
        if change > 9.93:
            yes_limit.append(s)
    
    log.info(f'前日涨幅大于9.93% {len(yes_limit)} 只')
    
    # 3. 仅保留「竞价涨幅 >5%」（取消换手）
    for code in yes_limit:
        pre = pre_close[code][0]  # 获取前一天的收盘价
        open_p = curr[code].day_open  # 获取当天的开盘价
        if pre <= 0:
            continue  # 如果前一天的收盘价小于等于0，则跳过
        change = (open_p - pre) / pre * 100  # 计算开盘价涨幅百分比
        log.info(f'{code} 前收 {pre:.2f} 开盘 {open_p:.2f} 涨幅 {change:.2f}%')
        if change > 5.0:
            g.selected.append(code)  # 如果涨幅大于5%，则加入自选股票池
    
    log.info(f'最终候选：{g.selected}')  # 打印最终候选股票池

def before_trading_start(context):
    """
    开盘前执行的任务。
    1. 清空自选股票池和持仓状态。
    """
    log.info('>>> before_trading_start 入口')  # 打印日志，表示进入开盘前任务
    g.done_buy = False  # 重置买入标志
    g.selected = []     # 清空自选股票池

def handle_tick(context, tick):
    """
    处理每个Tick数据。
    1. 检查当前Tick是否在自选股票池中。
    2. 检查可用资金是否充足。
    3. 如果当前Tick的价格达到涨停价的9.87%，则以涨停价下单购买一定数量的股票。
    """
    if tick.code not in g.selected:
        return  # 如果当前Tick不在自选股票池中，则跳过
    
    cash = context.portfolio.available_cash  # 获取可用资金
    if cash <= 0:
        return  # 如果可用资金不足，则跳过
    
    curr = get_current_data()[tick.code]  # 获取当前Tick数据
    limit_price = curr.high_limit  # 获取涨停价
    
    # 9.87% 触发（距离涨停 ≤0.13%）
    if tick.price >= limit_price * 0.9987:
        amount = int(cash * 3 / 5 / limit_price / 100) * 100  # 计算买入数量
        if amount > 0:
            order(tick.code, amount, style=LimitOrderStyle(limit_price))  # 以涨停价下单购买股票
            g.selected.remove(tick.code)  # 移除已买入的股票，防止重复
            log.info('>>> Tick 9.87% 抢板 %s 价 %.2f 量 %d' % (tick.code, limit_price, amount))  # 打印买入信息

def after_trading_end(context):
    """
    收盘后执行的任务。
    打印当天结束后的持仓情况。
    """
    log.info('收盘持仓：%s' % list(context.portfolio.positions.keys()))  # 打印当天结束后的持仓股票代码


