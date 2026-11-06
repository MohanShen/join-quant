# Clone from JoinQuant
# postId: 91386c0ff887a15bbc69fae9d94d2932
# backtestId: 28a0448847327aad7ee963bb1ba9212e
# title: 5资产动量ETF轮动：8年多增长2200%+(真实无未来)

# 代码作者：Mr_Black

import numpy as np
import pandas as pd
import math


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(PriceRelatedSlippage(0.001))   # 滑点0.1%（按成交价比例）
    
    # 修改点 1：补上 type='fund'，修复聚宽 API 报错
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0, open_commission=0.0005,
                  close_commission=0.0005, close_today_commission=0, min_commission=5),
        type='fund'
    )
    
    g.etf_pool = [
        '518880.XSHG',  # 黄金ETF
        '513100.XSHG',  # 纳指100
        "159985.XSHE",  # 豆粕ETF
        "501018.XSHG",  # 南方原油
        '588060.XSHG',  # 科创50
    ]
    g.m_days = 18   #建议以18为中心，取值17-20（18/19最合适）
    g.accel_w = 0.5  # 修改点 2：聚宽不支持 os.environ，直接写死
    g.min_mom = 0.17  # 修改点 8：弱市资格闸(g.m_days=,81时0.17最优，g.m_days=20时0.15最优) —— 动量分下限，低于此值不纳入候选
    g.trailing_stop = 0.07  # 修改点 7：移动止盈 —— 收盘价较持仓期最高收盘价回撤超 7% 则卖出
    g.high_water = {}  # 记录每只持仓的历史最高收盘价 {etf: price}
    run_daily(trade, '14:30')


def metrics(etf):
    df = attribute_history(etf, g.m_days, '1d', ['close'])
    y = np.log(df['close'].values)
    n = len(y)
    x = np.arange(n)
    w = np.linspace(1, 2, n)
    
    # 线性拟合（加权）
    slope, intercept = np.polyfit(x, y, 1, w=w)
    ann_ret = math.exp(slope) ** 250 - 1
    resid = y - (slope * x + intercept)
    
    # 修改点 3：R² 改用标准加权 R²（分母用加权均值）
    y_mean_w = np.average(y, weights=w)
    ss_res = np.sum(w * resid ** 2)
    ss_tot = np.sum(w * (y - y_mean_w) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
    
    # 修改点 4：二次拟合也加上权重 w，与线性拟合时间敏感度对称
    c = np.polyfit(x, y, 2, w=w)
    accel = c[0]
    
    mom = ann_ret * r2
    return dict(mom=mom, accel=accel, r2=r2, ann_ret=ann_ret)


def get_rank(etf_pool):
    recs = {e: metrics(e) for e in etf_pool}
    
    # 修改点 5：资格闸改为显式过滤逻辑
    # 修改点 8：MOM 下限改为可调参数 g.min_mom（弱市资格闸），上限 10 保持基线兼容
    elig = []
    for e in etf_pool:
        mom = recs[e]['mom']
        r2 = recs[e]['r2']
        ann_ret = recs[e]['ann_ret']
        if g.min_mom < mom <= 10 and r2 > 0 and ann_ret > 0:
            elig.append(e)
    
    if not elig:
        return []
    
    mom_rank = {e: i for i, e in enumerate(sorted(elig, key=lambda e: recs[e]['mom'], reverse=True))}
    acc_rank = {e: i for i, e in enumerate(sorted(elig, key=lambda e: recs[e]['accel'], reverse=True))}
    w = g.accel_w
    key = {e: (1 - w) * mom_rank[e] + w * acc_rank[e] for e in elig}  # 越小越好
    return sorted(elig, key=lambda e: key[e])


def trade(context):
    target_num = 1
    target_list = get_rank(g.etf_pool)[:target_num]
    hold_list = list(context.portfolio.positions)

    # 修改点 7：移动止盈 —— 先更新最高收盘价，回撤超阈值则卖出，且当日不买回
    stopped = set()
    for etf in hold_list:
        c = attribute_history(etf, 1, '1d', ['close'])['close'].values[-1]
        g.high_water[etf] = max(g.high_water.get(etf, c), c)
        if c < g.high_water[etf] * (1 - g.trailing_stop):
            if context.portfolio.positions[etf].closeable_amount == 0:
                continue  # T+1 当日买入不可卖，明日再检查
            log.info('移动止盈 %s：收盘 %.3f 较最高 %.3f 回撤超 %.0f%%，卖出',
                     etf, c, g.high_water[etf], g.trailing_stop * 100)
            order_target_value(etf, 0)
            del g.high_water[etf]
            stopped.add(etf)

    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            if etf in g.high_water:
                del g.high_water[etf]

    hold_list = list(context.portfolio.positions)
    if len(hold_list) < target_num:
        value = context.portfolio.available_cash / (target_num - len(hold_list))
        for etf in target_list:
            if etf in stopped:
                continue  # 当日已止盈卖出，不买回
            # 修改点 6：用 in 判断避免 KeyError
            if etf not in context.portfolio.positions:
                order_target_value(etf, value)