# Clone from JoinQuant
# postId: 6abe1fbb91a3167b9668120ea7f1d6b0
# backtestId: b4f25e8c4d98b21d1a3271d9e30fb9a6
# title: 开源一个年化超25%的ETF策略

import math
import pandas as pd
import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt
import talib
 
import warnings
warnings.filterwarnings('ignore')

from jqdata import *

#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 设置滑点 
    set_slippage(FixedSlippage(0.0001))
    # 设置交易成本
    # 每笔交易时的手续费是：买入时佣金万分之二，卖出时佣金万分之二，无印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0, min_commission=5), type='fund')
    # 过滤一定级别的日志
    log.set_level('system', 'error')

    g.num = 1
    g.all_etfs = {
        "159915.XSHE": "创业板ETF",
        '510880.XSHG': "红利ETF",
        "518880.XSHG": "黄金ETF",
        "513100.XSHG": "纳指ETF",
        "159985.XSHE": "豆粕ETF",
        '510050.XSHG': '50ETF',
        '512100.XSHG': '1000ETF',
        '159768.XSHE': '房地产ETF银华',
        '515220.XSHG': '煤炭ETF',
        '159928.XSHE': '消费ETF',
        '512800.XSHG': '银行ETF',
        '159995.XSHE':'芯片ETF',
        '159870.XSHE':'化工ETF',
        '513090.XSHG':'香港证券ETF', 
    }
    
    g.stop_stocks = []
    
    run_weekly(rebalance_trade, 1, '09:35') 
    

def select_low_vol_etfs(context,  n=3, lookback=60):
    """
    从ETF池中选择过去 lookback 个交易日波动率最低的 N 只ETF。
    """
    etfs = list(g.all_etfs.keys())
    df = get_price(
        etfs,
        end_date=context.previous_date,
        count=lookback + 1,
        frequency='daily',
        fields=['close'],
        panel=False
    )
 

    df['log_ret'] = df.groupby('code')['close'].transform(
        lambda x: np.log(x / x.shift(1))
    )

    # 年化波动率
    volatility = (
        df.groupby('code')['log_ret']
        .std()
        .mul(np.sqrt(252))
        .dropna()
        .sort_values()
    )
    print(volatility)

    return volatility.head(n).index.tolist()

def rebalance_trade(context):
    total_value = context.portfolio.total_value
    d_today = (context.current_dt).strftime("%Y%m%d")
    
    target_list  = select_low_vol_etfs(context, g.num)
    weight = 1.0 / len(target_list)
    result = dict(zip(target_list, [weight] * len(target_list)))
    print(f'Target: {result}')

    current_data = get_current_data()

    current_holdings = context.portfolio.positions
    for code in list(current_holdings):
        if code not in target_list:
            order_target_value(code, 0)
            print(f"清仓（不在目标）: {code}")
        elif code in g.stop_stocks:
            continue
        else:
            target_value = total_value * result[code]
            last_price = current_data[code].last_price
            current_value = context.portfolio.positions[code].closeable_amount * last_price
            if current_value > target_value * 1.05:  # 允许5%容差，避免频繁微调
                order_target_value(code, target_value)
                print(f"减仓: {code} → 目标价值 {target_value:,.0f}")
            else:
                # 加仓
                if current_value < target_value * 0.95:  # 允许5%容差，避免频繁微调
                    order_target_value(code, target_value)
                    print(f"加仓: {code} → 目标价值 {target_value:,.0f}")

    # 买入
    hold_list = list(context.portfolio.positions)
    for code in target_list:
        if code in g.stop_stocks:
            continue
        target_weight  = result.get(code)
        if code not in hold_list:
            target_value = total_value * target_weight
            
            if context.portfolio.positions[code].total_amount == 0:
                order_target_value(code, target_value)
                print(f'买入: {str(code)}, {target_value}')


