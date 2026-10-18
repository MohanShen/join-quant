# Clone from JoinQuant
# postId: decbc72d1336448862dd04f33a09591c
# backtestId: 441b5fb3a2dbba682e6d1aa75752b1ed
# title: FollowBB与RideMood策略研究

from jqdata import *
import pandas as pd
import numpy as np
from pandas import Series, DataFrame
import datetime as datetime
import time as time
import math

def initialize(context):
    g.security = '000014.XSHE'
    set_benchmark('000300.XSHG')
    set_benchmark('000300.XSHG')
    g.algorithm_type = 'RideMood' #'FollowBB'
    
    # 关闭订单提醒
    log.set_level('order', 'error')
    
    # 设定手续费
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, \
                    close_commission=0.0003, min_commission=5), type='stock')
    
    # 运行   
    run_daily(trade, 'open')

def trade(context):
    position = context.portfolio.positions
    cash = context.portfolio.cash
    
    if (get_estimate_a(g.security,g.algorithm_type,'buy')) and (position.has_key(g.security) == False):
        order_target_value(g.security,cash)
        log.info("Buying %s" % (g.security))
    elif (position.has_key(g.security) == True) and (get_estimate_a(g.security,g.algorithm_type,'sell')):
        order_target(g.security, 0)
        log.info("Selling %s" % (g.security))


def get_estimate_a(stock,model,bs):
    '''
    该函数是获取'RideMood' / 'FollowBB'模型的 estimate_a 值
    model: 'RideMood' / 'FollowBB'
    bs: 'buy' / 'sell'
    stock：股票代码
    m: m-day moving averages of the estimated parameters
    '''

    if model == 'RideMood' :
        m = 5
        a6_average, a7_average = compute_estimate_a(stock, m)
        if bs == 'buy' and (a7_average-a6_average)>0:
            return True
        elif bs == 'sell' and (a7_average-a6_average)<0:
            return True
    elif model == 'FollowBB':
        m = 3
        a6_average, a7_average = compute_estimate_a(stock, m)
        if bs == 'buy' and (a7_average>0)and (a6_average<=0):
            return True
        elif bs == 'sell' and (a7_average<0):
            return True

def compute_estimate_a(stock, m):
    '''
    该函数是计算estimate_a
    stock：股票代码
    m: m-day moving averages of the estimated parameters
    '''
    
    #估计a6和a7的值
    df = attribute_history(stock, m+2, '1d', ['close'])
    p = df['close']

    diagonal_matrix = np.zeros((2,2))
    diagonal_matrix[0,0] = 1
    diagonal_matrix[1,1] = 1
    log_ratio = [0]*(len(p))

    #parameters below are determined based on a number of trail-and-error experiments
    omega=0.01
    gama=10
    lambda_=0.95 
    n=3

    P = np.zeros((len(p),2,2))  #P的每一个元素都为一个2*2矩阵
    K = np.zeros((len(p),2,1))  #K的每一个元素都为一个2*1矩阵
    a = np.zeros((len(p),2,1))  #a的每一个元素为一个2*1矩阵
    ed = np.zeros((len(p),2,1))  #ed的每一个元素为一个2*1矩阵
    P[1] = gama*diagonal_matrix
    a[0] = 0
    r = [0]*(len(p))
    #此处与研究中不同，研究中是在每天收盘后，计算log_ratio，现在只能在昨天收盘后计算

    for i in range(2,len(p)):
        log_ratio[i] = math.log(p[i]*n/sum(p[(i-n+1):(i+1)])) 
        if log_ratio[i]<=0:
            x = 0
        elif (log_ratio[i]>0) and (log_ratio[i]<=2*omega):
            x = (-0.1)*log_ratio[i]/omega
        elif (log_ratio[i]>2*omega) and (log_ratio[i]<=3*omega):
            x = (-0.2)*log_ratio[i]/omega+0.2
        else:
            x = -0.4
    
        if log_ratio[i]>=0:
            y = 0
        elif (log_ratio[i]<0) and (log_ratio[i]>=-2*omega):
            y = -0.1*log_ratio[i]/omega
        elif (log_ratio[i]<-2*omega) and (log_ratio[i]>=-3*omega):
            y = -0.2*log_ratio[i]/omega-0.2
        else:
            y = 0.4
        
        ed[i,0] = x
        ed[i,1] = y

        K[i] = np.dot(P[i-1],ed[i])/(np.dot(np.dot(ed[i].T,P[i-1]),ed[i])+lambda_)
        P[i] = np.dot((diagonal_matrix - np.dot(K[i],ed[i].T)),P[i-1])/lambda_
        r[i] = math.log((p[i]/p[i-1]))
        a[i-1] = a[i-2]+K[i-1]*(r[i]-np.dot(ed[i-1].T,a[i-2]))
        
    sum_a6 = 0
    sum_a7 = 0
    for i in range(1,len(p)-1):
        sum_a6 += a[i,0,0]
        sum_a7 += a[i,1,0]
        
    a6_average = sum_a6/m
    a7_average = sum_a7/m
        
    return a6_average,a7_average
    