# Clone from JoinQuant
# postId: 1c96e06b0292c5880cac1ac24b38468a
# backtestId: 34b815a24e8cba33a6fe3d6608c7dab1
# title: 10年14倍！最大可容500w资金etf轮动策略

# 克隆自聚宽文章：https://www.joinquant.com/post/49263
# 标题：安全摸狗策略
# 作者：MarioC

# 克隆自聚宽文章：https://www.joinquant.com/post/42673
# 标题：【回顾3】ETF策略之核心资产轮动
# 作者：wywy1995

import numpy as np
import pandas as pd
import math

# 初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 设置滑点
    set_slippage(FixedSlippage(0.001))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0, min_commission=5), type='fund')
    # 过滤一定级别的日志
    log.set_level('system', 'error')
    # 参数
    g.etf_pool = [
        '159934.XSHE', #黄金ETF（大宗商品）
        '159941.XSHE', #纳指100（海外资产）
        '159915.XSHE', #创业板100（成长股，科技股，中小盘）
        '510180.XSHG', #上证180（价值股，蓝筹股，中大盘）
    ]
    g.etf_names = {
        '159934.XSHE': '黄金ETF',
        '159941.XSHE': '纳指ETF',
        '159915.XSHE': '创业板ETF',
        '510180.XSHG': '上证180ETF'
    }
    g.m_days = 25 #动量参考天数
    g.latest_rank = None  # 存储最新的排名数据
    
    run_daily(pre_market_report, '14:50') # 14:50更新排名（使用当天最新数据）
    run_daily(trade, '14:55') # 14:55使用最新排名数据进行交易

def MOM(etf):
    # 获取前24天的历史收盘价
    df = attribute_history(etf, g.m_days - 1, '1d', ['close'])
    # 获取当天的最新价格
    current_data = get_current_data()
    current_price = current_data[etf].last_price
    # 将当天价格加入到历史数据中
    close_prices = list(df['close'].values)
    close_prices.append(current_price)

    y = np.log(close_prices)
    n = len(y)
    x = np.arange(n)
    weights = np.linspace(1,2, n)  # 线性增加权重
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    annualized_returns = math.pow(math.exp(slope), 250) - 1
    residuals = y - (slope * x + intercept)
    weighted_residuals = weights * residuals**2
    r_squared = 1 - (np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y))**2))
    score = annualized_returns * r_squared
    return score

def get_rank(etf_pool):
    score_list = []
    for etf in etf_pool:
        score = MOM(etf)
        score_list.append(score)
    df = pd.DataFrame(index=etf_pool, data={'score':score_list})
    df = df.sort_values(by='score', ascending=False)
    df = df[(df['score'] > 0) & (df['score'] <= 5)] #安全区间，动量过高过低都不好
    return df

def print_rank_report(context, time_str):
    df = get_rank(g.etf_pool)
    g.latest_rank = df  # 更新最新排名数据
    log.info(f'【动量排名报告 {time_str}】')
    
    for etf in g.etf_pool:
        score = df.loc[etf, 'score'] if etf in df.index else 0
        etf_name = g.etf_names[etf]
        status = "可投资" if score > 0 and score <= 5 else "不投资"
        log.info(f'{etf_name}: 得分{score:.4f} {status}')
    
    if len(df) > 0:
        top_etf = df.index[0]
        if top_etf == '510180.XSHG':  # 上证180ETF
            log.info(f'今日推荐: 空仓（信号为{g.etf_names[top_etf]}）')
        else:
            log.info(f'今日推荐: {g.etf_names[top_etf]}')
    else:
        log.info('今日推荐: 无推荐标的，建议空仓或避险')

def morning_report(context):
    print_rank_report(context, "早间")

def pre_market_report(context):
    print_rank_report(context, "盘前")

# 交易
def trade(context):
    # 使用9:00生成的排名数据进行交易
    if g.latest_rank is None:
        log.error("没有可用的排名数据，跳过本次交易")
        return

    target_num = 1
    target_list = list(g.latest_rank.index)[:target_num]

    # 策略替换：如果信号是上证180ETF，则空仓
    actual_target_list = []
    for etf in target_list:
        if etf == '510180.XSHG':  # 上证180ETF
            log.info(f'策略替换: 信号为{g.etf_names[etf]}，选择空仓')
            # 不添加到actual_target_list，即空仓
        else:
            actual_target_list.append(etf)

    # 卖出
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in actual_target_list:
            order_target_value(etf, 0)
            log.info('卖出' + g.etf_names[etf])
        else:
            log.info('继续持有' + g.etf_names[etf])

    # 买入
    hold_list = list(context.portfolio.positions)
    if len(hold_list) < target_num and len(actual_target_list) > 0:
        value = context.portfolio.available_cash / (target_num - len(hold_list))
        for etf in actual_target_list:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, value)
                log.info('买入' + g.etf_names[etf])