# Clone from JoinQuant
# postId: 0cfea7689a041aaf1e3fa08c7bd1ccb4
# backtestId: 751291fd20e03c906bf0ac881b45cac4
# title: 期货配对交易_小尝试

import scipy.stats as stats
import numpy as np
import pandas as pd
from pandas import DataFrame, Series
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint
from datetime import timedelta
import matplotlib.pyplot as plt
import re


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    # day count
    g.count = -1
    # wrt to mv std
    g.threshold = 1
    # for symbol (correspond to dominant contract)
    g.category_pair = ['', '']
    # for actual contract
    g.contract_pair = ['', '']
    # number of contracts to take in account every period
    g.size_of_universe = 10
    # max position size
    g.max_num_contracts = 3
    # mv std
    g.sigma = 0.0
    g.stop_loss = 0.98
    # period window size
    g.T = 15
    g.total_value = 0
    g.close_position_flag = False
    g.reg_param = [0.0, 0.0]
    g.pattern = ''
    g.margin_rate = 0.15

    set_subportfolios(
        [SubPortfolioConfig(cash=context.portfolio.starting_cash, type='futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', g.margin_rate)
    set_slippage(PriceRelatedSlippage(0.002))
    # actually run every 15 days
    run_daily(before_market_open, time='before_open')
    run_daily(market_open, time='10:00')
    # run_daily(stop_loss, time='open')


def get_high_volume_contracts(num_days):
    contract_list = get_all_securities(['futures']).index.tolist()
    dominant_contract_list = [
        x for x in contract_list if re.search(r'9999', x)]
    volume_panel = history(count=num_days, field='volume',
                           security_list=dominant_contract_list, df=False)
    volume_rank = [(x, volume_panel[x].mean())
                   for x in volume_panel if not any(np.isnan(volume_panel[x]))]
    volume_rank = sorted(volume_rank, key=lambda x: x[1], reverse=True)
    rank_high = np.array(
        [x[0] for x in volume_rank[0: min(len(volume_rank), g.size_of_universe)]])
    return rank_high

# helper function for transforming dominant contract to its category
def get_category(dominant_name):
    category = re.findall(r'^([A-Z]*)', dominant_name)[0]
    return category


def Find_cointegrated_pairs(securities_panel, keys):
    n = len(keys)
    #原假设是股票间不存在协整关系，如果Pvalue<0.05则拒绝原假设
    pvalue_matrix = np.ones((n, n))
    #循环，计算两两股票间的协整关系，并将结果保存在矩阵中
    for i in range(n):
        for j in range(i + 1, n):
            S1 = securities_panel[keys[i]]
            S2 = securities_panel[keys[j]]
            result = coint(S1, S2)
            #score用来判断股价是否是非平稳的，代表对股价进行单位根检定的t统计量
            score = abs(result[0])
            pvalue = result[1]
            if score > 3:
                pvalue_matrix[i, j] = pvalue
            else:
                pvalue_matrix[i, j] = 1
    result_list = [(keys[i], keys[j], pvalue_matrix[i][j]) for i in range(n)
                   for j in range(i, n) if pvalue_matrix[i][j] < 0.05]
    return result_list


def get_dominant_contract_pair(symbol_list):
    try:
        symbol_list = [get_category(x) for x in symbol_list]
        return [get_dominant_future(x) for x in symbol_list]
    except:
        return ['', '']


def sell_out_close(context):
    if len(context.portfolio.long_positions):
        for x in context.portfolio.long_positions.keys():
            order_target(x, 0, side='long', pindex=0)
    if len(context.portfolio.short_positions):
        for x in context.portfolio.short_positions.keys():
            order_target(x, 0, side='short', pindex=0)

def get_mv_std(security1, security2, size):
    y = attribute_history(security1, size, '1d', 'close', df = False).values()[0]
    x = attribute_history(security2, size, '1d', 'close', df = False).values()[0]
    error = y - g.reg_param[0] * x - g.reg_param[1]
    return std(error)

# def get_all_positions(context):
#     return sum([x.total_amount for x in context.portfolio.long_positions.values()])
            
# actually run every T (period)
def before_market_open(context):
    g.count += 1
    if g.count % g.T != 0:
        return
    # every T reopen position
    if g.close_position_flag:
        g.close_position_flag = False

    # like ('A', 'B', 0.05)
    # get highest volume contracts as condidates
    dominant_contract_list = get_high_volume_contracts(g.T)
    price_panel = history(count=g.T, field='close',
                          security_list=dominant_contract_list, df=False)
    # resolve inconsistent length....
    min_length = np.min([len(price_panel[x]) for x in price_panel.keys()])
    for k in price_panel:
        if len(price_panel[k]) > min_length:
            price_panel[k] = price_panel[k][0: min_length]
    # get min p-value pair
    p_value_m = Find_cointegrated_pairs(price_panel, dominant_contract_list)
    if len(p_value_m) == 0:
        # no contracts to trade this month...
        g.category_pair = ['', '']
        g.contract_pair = ['', '']
        return
    min_p_pair = min(p_value_m, key=lambda x: x[2])
    if min_p_pair[2] > 0.3:
        g.category_pair = ['', '']
        g.contract_pair = ['', '']
        log.info("Month:" + str(g.count) + ': {}'.format('No Ideal Contract'))
        return
    else:
        # Treat 0: y, 1: x
        # if have a diffrent pair from the previous T
        g.category_pair = min_p_pair[0: 2]
        # get the actual contract
        g.contract_pair = get_dominant_contract_pair(min_p_pair[0: 2])
        g.close_position_flag = False
        y = price_panel[min_p_pair[0]]
        x = price_panel[min_p_pair[1]]
        X = sm.add_constant(x)
        result = (sm.OLS(y, X)).fit()
        g.reg_param = result.params
        print('*' * 30)
        print('Rebalance y: {} x:{}'.format(min_p_pair[0], min_p_pair[1]))
        

def market_open(context):
    if any([x == '' for x in g.category_pair]) or g.close_position_flag:
        return
    if context.portfolio.positions_value < g.total_value * g.stop_loss:
        sell_out_close(context)
        log.info('Stop Loss!')
        g.close_position_flag = True
        g.total_value = context.portfolio.positions_value
        
    current_data = get_current_data()
    y = g.contract_pair[0]
    x = g.contract_pair[1]
    try:
        price_y = current_data[y].last_price
        price_x = current_data[x].last_price
    except:
        print('Error!')
        print(g.contract_pair)
    new_error = price_y - price_x * g.reg_param[0] - g.reg_param[1]
    g.sigma = get_mv_std(y, x, g.T)
    delta = new_error / g.sigma
    if delta > 2 * g.threshold and context.portfolio.short_positions[y].total_amount < g.max_num_contracts \
    and not context.subportfolios[0].is_dangerous(g.margin_rate + 0.1):
        order(y, 1, side='short', pindex=0)
        order(x, 1, side='long', pindex=0)
        g.pattern = 'short'
        log.info('long {}, short {}'.format(
            x, y))
    # short x, long y; long the discrepancy
    elif delta < -2 * g.threshold and context.portfolio.short_positions[x].total_amount < g.max_num_contracts \
    and not context.subportfolios[0].is_dangerous(g.margin_rate + 0.1):
        order(y, 1, side='long', pindex=0)
        order(x, 1, side='short', pindex=0)
        log.info('long {}, short {}'.format(
            y, x))
        g.pattern = 'long'

    g.total_value = context.portfolio.positions_value
