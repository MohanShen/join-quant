# Clone from JoinQuant
# postId: 9478e83f4974e439b4d8b6de97f75a8b
# backtestId: 418ccdf7bd6dbdc54e07c4b7792a04e2
# title: [已解决]基金分拆打你个措手不及？

# 克隆自聚宽文章：https://www.joinquant.com/post/50213
# 标题：核心资产轮动-每日盘前交易预测-v1.1-摸狗
# 作者：openresearch

# 克隆自聚宽文章：https://www.joinquant.com/post/49263
# 标题：安全摸狗策略
# 作者：MarioC

# 克隆自聚宽文章：https://www.joinquant.com/post/42673
# 标题：【回顾3】ETF策略之核心资产轮动
# 作者：wywy1995

import numpy as np
import pandas as pd
#自动低相关ETF池
from jqdata import *
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from datetime import datetime, timedelta
import warnings
from tqdm import tqdm
import torch 
import torch.nn as nn
import matplotlib.pyplot as plt
import torch.nn.functional as F
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
from torch.utils.data import random_split
from torch.utils.data import TensorDataset
#使用KMeans聚类
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 设置滑点 https://www.joinquant.com/view/community/detail/a31a822d1cfa7e83b1dda228d4562a70
    set_slippage(FixedSlippage(0.001))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0005, close_commission=0.0005, close_today_commission=0, min_commission=5), type='fund')
    # 过滤一定级别的日志
    log.set_level('system', 'error')
    # 参数
    # ETF池和动量参考天数参数
    g.etf_name = {
        '518880.XSHG': '黄金ETF',
        '513100.XSHG': '纳指100',
        #'161125.XSHE': '标普500',
        '159915.XSHE': '创业板100',
        #'510050.XSHG': '上证50',
        #'510300.XSHG': '沪深300',
        '510500.XSHG': '中证500',
        #'512100.XSHG': '中证1000',
        '515080.XSHG': '中证红利',
        '159905.XSHE': '深证红利',
        #'511360.XSHG': '短融ETF',
        #'512160.XSHG': 'MSCI-A',
        '511880.XSHG': '银华日利',
    }
    g.etf_pool = g.etf_name.keys()
    g.m_days = 25 #动量参考天数
    g.m_rate = 0  #持股比例
    # run_daily(trade, '9:30') #每天运行确保即时捕捉动量变化
    run_daily(trade, '9:45') #每天运行确保即时捕捉动量变化
    
    run_weekly(UpdatePool, 5, '18:00')

def UpdatePool(context):
    etf_name = GetEtfPool(context.current_dt)
    if etf_name is not None:
        for etf in etf_name:
            g.etf_name[etf] = etf_name[etf]
        g.etf_pool = etf_name.keys()

def GetEtfPool(today : datetime):
    #获得etf基金列表
    df = get_all_securities(['etf'])
    df = df.reset_index().rename(columns={'index':'code'})
    df = df[df['start_date'] < (today + timedelta(-450)).date()]
    df = df[df['end_date'] >= datetime.today().date()]

    # 剔除成交额过低（流动性差）的etf
    codes = []
    for code in df.code:
        #price = get_price(code, end_date=today, count=300).dropna()
        price = attribute_history(code, 300, '1d').dropna()
        price['pchg'] = price['close'].pct_change()
        if price['money'].mean() > 1e7: # 日均低于5000w成交额
            codes.append([code, price['money'].mean()/1e8, price['pchg'].mean(), price['pchg'].std()])
        else:
            #print(f"排除{code} {df[df['code']==code]['display_name'].iloc[0]}, 成交额均值 {round(price['money'].mean()/1e7, 2)}kw")
            pass
    codes = pd.DataFrame(codes, columns=['code', 'money','pchg_mean','pchg_std'])
    df = df.merge(codes, how='inner', on='code')    #融合以便过滤
    raw_codes = df.sort_values('pchg_std')

    prices = []
    for code in df.code:
    #     price = get_price(code, fields='close',end_date='2024-06-26', count=240)
        #price = get_price(code, fields='close',end_date=datetime.today().date(), count=450)
        price = attribute_history(code, 450, '1d', ['close'])
        price['pchg'] = price['close'].pct_change()
        prices.append(price['pchg'].values)
    prices = np.array(prices).T
    if (len(prices) == 0):
        print('初步没能筛出标的')
        return None
    prices = pd.DataFrame(prices, columns=df.code).dropna().iloc[1:]
    #prices

    #执行聚类
    x = prices.T
    n_clusters = 24
    cluster = KMeans(n_clusters=n_clusters,random_state=42)
    y_pred = cluster.fit_predict(x)   ## 每个样本所对应的簇的标签
    x['cluster_id'] = y_pred
    rate = silhouette_score(x, y_pred)
    if (rate > 1.0 or rate < 0.8):
        print('聚类失败了。')
        return None

    x = x.reset_index().rename(columns={'index':'code'})
    # df = df.merge(x[['code','cluster_id']]).sort_values(['cluster_id', 'start_date'])
    dff = df.merge(x[['code','cluster_id']]).sort_values(['cluster_id', 'start_date'])

    #pd.set_option('display.max_rows', None)#显示全部行
    #pd.set_option('display.max_columns', None)#显示全部列
    #dff

    # 每个簇里面选 成立最早的
    df = dff
    df = df.groupby('cluster_id').first()

    # 再用相关系数聚类一遍
    corr = prices[df.code].corr()
    codes = df.code.tolist()
    union = []
    for i in codes:
        for j in codes:
            if i == j:
                continue
            if corr.loc[i, j] > 0.85:
                find = False
                for k in range(len(union)):
                    if i in union[k] or j in union[k]:
                        union[k].add(i)
                        union[k].add(j)
                        find = True
                if not find:
                    union.append(set([i, j]))

    # 同理，仅保留成立最早的
    remove = []
    for i in union:
        remove += df[df['code'].isin(i)].sort_values('start_date').iloc[1:]['code'].tolist()
    #print('corr 剔除: ', remove)
    df = df[~df['code'].isin(remove)]

    # 去掉较晚成立的
    remove = df[df['start_date'] > today.date() + timedelta(-450)]['code'].tolist()
    #print('成立时间：剔除2020后成立的', remove)
    df = df[~df['code'].isin(remove)]
    #df
    
    funds = df.code.unique().tolist()
    names = {}
    for etf in funds:
        eobj = get_security_info(etf)
        if (eobj is not None):
            names[etf] = eobj.display_name
    
    print('最终筛出标的%d个。'%(len(funds)))
    return names

def MOM(etf):
    df = attribute_history(etf, g.m_days, '1d', ['close'])
    y = np.log(df['close'].values)
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

# 计算指定日期之前一个交易日的波动率
def VOL(etf):
    #start_date = datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=1)
    #data = get_price(security, start_date=start_date, end_date=target_date, frequency='minute', fields=['close'], skip_paused=False)
    sval = attribute_history(etf, 240, '1m', ['close']) #全天240分钟
    rets=np.diff(np.log(sval['close']),axis=0)
    sstd=rets.std()*sqrt(250)
    lval = attribute_history(etf, g.m_days, '1d', ['close']) #全天240分钟
    rets=np.diff(np.log(lval['close']),axis=0)
    lstd=rets.std()*sqrt(250)
    return sqrt(abs(sstd/lstd))
    
# 基于年化收益和判定系数打分的动量因子轮动 https://www.joinquant.com/post/26142
def get_rank(etf_pool):
    score_list = []
    vixs = []
    for etf in etf_pool:
        score_list.append(MOM(etf))
        vixs.append(VOL(etf))
    df = pd.DataFrame(index=etf_pool, data={'score':score_list,'VIX':vixs})
    df = df.sort_values(by='score', ascending=False)
    df = df.dropna(axis=0)
    #print("所有ETF动量")
    #print(df)
    #total_score = df['score'].sum() 不告诉你这个怎么用
    #df = df[(df['score'] > 0) & (df['score'] <= 5)] #安全区间，动量过高过低都不好
    
    df = df[(df['score'] > 0) & (df['score'] <= 5)]
    #df = df.sort_values(by='VIX', ascending=False).tail(int(len(etf_pool) / 2))
    df = df.sort_values(by='score', ascending=False)
    g.m_rate = 1 - df.head(1)['VIX']
    
    rank_list = list(df.index)
    if len(rank_list) == 0:
        rank_list=[] #如果全部都小于0，那么空仓或者买《国债、银华日历、黄金》避险
    return rank_list

# 交易
def trade(context):
    # 获取动量最高的一只ETF
    target_num = 1  
    target_list = get_rank(g.etf_pool)[:target_num]
    # 卖出    
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            print('卖出' + str(etf) + '[' + g.etf_name[etf] + ']')
        else:
            print('继续持有' + str(etf) + '[' + g.etf_name[etf] + ']')

    # 买入
    hold_list = list(context.portfolio.positions)
    if len(hold_list) < target_num:
        value = context.portfolio.available_cash / (target_num - len(hold_list))
        for etf in target_list:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, value)
                print('买入' + str(etf) + '[' + g.etf_name[etf] + ']')

