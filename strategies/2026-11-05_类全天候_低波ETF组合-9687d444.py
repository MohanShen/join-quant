# Clone from JoinQuant
# postId: 9687d444b47af9f536374a3c75eff34c
# backtestId: 6bdd996fb2abf4983cd89c7f9be6e051
# title: 【类全天候】低波ETF组合

import numpy as np
import pandas as pd
import talib
import math

def REF(S, N=1):          #对序列整体下移动N,返回序列(shift后会产生NAN)    
    return pd.Series(S).shift(N).values 
    
def ABS(S):      return np.abs(S)            #返回N的绝对值

def MAX(S1,S2):  return np.maximum(S1,S2)    #序列max

def MA(S,N):              #求序列的N日简单移动平均值，返回序列                    
    return pd.Series(S).rolling(N).mean().values  
    
def ATR(CLOSE,HIGH,LOW, N=20):                    #真实波动N日平均值
    TR = MAX(MAX((HIGH - LOW), ABS(REF(CLOSE, 1) - HIGH)), ABS(REF(CLOSE, 1) - LOW))
    return MA(TR, N)

#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 设置滑点
    set_slippage(PriceRelatedSlippage(0.002),type='fund')
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001, close_commission=0.0001, close_today_commission=0, min_commission=0), type='fund')
    # 过滤一定级别的日志
    log.set_level('strategy', 'info')
    log.set_level('order', 'error')
    log.set_level('system', 'error')

    # 参数
    g.etf_pool = [
            # 商品
            "518880.XSHG",  # 黄金
            # 境外
            "513100.XSHG",  # 纳指
            # 国内
            '512890.XSHG',  # 红利低波
            "159915.XSHE",  # 创业板
            # 债券
            "511010.XSHG",  # 国债ETF
    ]
    
    g.m_days = 60 # 默认波动率参考天数
    g.target_count = 3
    
    run_daily(trade, '13:12')


def get_rank(context,etf_pool):
    crows = []
    for etf in etf_pool:
        # 获取数据
        his_df = attribute_history(etf, 100, "1d", ["close", "low", "high"])
        atr = ATR(his_df['close'],his_df['high'],his_df['low'], N=g.m_days)[-1]

        crows.append({
            'etf': etf,
            'atr': atr
        })
    
    df = pd.DataFrame(crows)
    df = df.dropna(subset=['atr'])

    # print(df)
    
    if df.empty:
        return []
    df["atr_rank"] = df["atr"].rank(ascending=True)  
    df.sort_values(by="atr_rank", inplace=True, ascending=True)
    rank_list = df["etf"].tolist()
    
    return rank_list[:g.target_count]


def trade(context):
    
    target_list = get_rank(context,g.etf_pool)
    
    if not target_list:
        log.error(f"目标持仓列表为空：{target_list}")
        return

    # 卖出    
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            log.info('卖出' + str(etf)+get_security_info(etf).display_name)
            
    # 买入
    for target in target_list:
        if context.portfolio.positions[target].total_amount == 0:
            target_value = context.portfolio.available_cash / (g.target_count - len(list(context.portfolio.positions.keys())))
            
            order_target_value(target, target_value)
            log.info('买入' + str(target)+get_security_info(target).display_name)
