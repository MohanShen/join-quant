# Clone from JoinQuant
# postId: 17c0ac1a2052db60ce5d9c1595b62af1
# backtestId: d973ee6d2b5494f3960e49e751db9f3a
# title: 3年前的老策略依然能打，10年30倍、年年正收益

# 克隆自聚宽文章：https://www.joinquant.com/post/42673
# 标题：【回顾3】ETF策略之核心资产轮动
# 作者：wywy1995

import numpy as np
import pandas as pd
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('expand_frame_repr', False)
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)


#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    set_option("avoid_future_data", True)  # 打开防未来函数
    set_option("use_real_price", True)  # 开启动态复权模式(真实价格)
    set_option('match_with_order_book', True)
    # 固定滑点设置ETF 0.001(即交易对手方一档价)
    set_slippage(FixedSlippage(0.004), type="fund")
    set_slippage(PriceRelatedSlippage(0.003), type='stock')
    set_order_cost(OrderCost(open_tax=0, close_tax=5/10000, open_commission=1 / 10000, close_commission=1 / 10000,
                             close_today_commission=0, min_commission=5), type="stock")
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.5 / 10000, close_commission=0.5 / 10000,
                             close_today_commission=0, min_commission=5), type='fund')
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0, close_commission=0, close_today_commission=0,
                             min_commission=0), type="mmf")
    log.info("初始函数开始运行且全局只运行一次")  # 输出内容到日志 log.info()
    # 过滤一定级别的日志
    log.set_level('system', 'error')
    log.set_level('order', 'error')
    log.set_level('strategy', 'info')
    # 参数
    g.etf_pool = [
        '518880.XSHG', #黄金ETF（大宗商品）成立日：2013-07-18 成交额：36.03亿
        '513100.XSHG', #纳指100（海外资产）成立日：2013-04-25 成交额：4.62亿
        '159915.XSHE', #创业板（成长股，科技股，中小盘）成立日：2011-09-20 成交额：27.45亿
        "510180.XSHG",  # 180ETF 成立日：2006-05-18 成交额：1.44亿
    ]

    g.m_days = 25 #动量参考天数
    run_daily(trade, '09:30') #每天运行确保即时捕捉动量变化


def get_rank(context,etf_pool):
    current_data = get_current_data()
    scores_data = pd.DataFrame(index=etf_pool,
                               columns=["current_price", "annualized_return", "r2", "score", "name"])
    for etf in etf_pool:
        cd = current_data[etf]
        df = attribute_history(etf, g.m_days, '1d', ['close'])
        current_data = get_current_data()
        # prices = np.append(df["close"].values, current_data[etf].last_price)
        prices = df.close
        # log.info("{} prices: {}".format(etf, prices))
        y = np.log(prices)
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        annualized_return = math.pow(math.exp(slope), 250) - 1
        r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
        score = annualized_return * r_squared

        scores_data.loc[etf, ["current_price", "annualized_return", "r2", "score", "name"]] = [
            cd.last_price, annualized_return, r_squared, score, cd.name]

    df = scores_data.sort_values(by='score', ascending=False)

    rank_list = list(df.index)
    return rank_list
    

# 交易
def trade(context):
    # 获取动量最高的一只ETF
    target_num = 1    
    target_list = get_rank(context,g.etf_pool)[:target_num]
    # print(f"初选股票池 {target_list}")
    # 卖出    
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            print('卖出' + str(etf))
        else:
            print('继续持有' + str(etf))
            pass
    # 买入
    hold_list = list(context.portfolio.positions)
    if len(hold_list) < target_num:
        value = context.portfolio.available_cash / (target_num - len(hold_list))
        for etf in target_list:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, value)
                print('买入' + str(etf))
                

