# Clone from JoinQuant
# postId: 9106ccaf1d8f2f25bffdc8d9ffaca3c6
# backtestId: 258dd108882be1c92b9ea56d464d6d29
# title: 首板炸板回封买入策略

# -*- coding: utf-8 -*-
"""
Created on Sun Jul  3 12:08:58 2022

@author: yangjiaer
"""

# 该版本核心：
# 首板须突破前高，且没有太高
# 前四日均无涨停才能叫作首板
# 加入情绪周期与市场模式识别，三天回撤达4%就休息5天（参数可以再改）
# 当日涨停股票池十五分钟更新一次
# 三种卖出类型：炸板次日开盘卖；几连板次日开盘70分钟后，涨幅低于8.5%就卖；普通模式次日两点后，涨幅低于8.5%就卖
# 连板用的是多日累计涨幅大于一定值这种方法来识别
# 打板打到下午2；40为止

###------------------------------------------------------------------------------
# 导入聚宽函数库
#enable_profile()
from jqlib.alpha101 import *
import jqdata
import pandas as pd
from six import BytesIO
from pandas import DataFrame,Series
import numpy as np 
import csv
import os
import xlrd
import math


###------------------------------------------------------------------------------
# 初始化程序, 整个回测只运行一次
def initialize(context):
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    #设置滑点
    set_slippage(PriceRelatedSlippage(0.0003),type='stock')
    # 每天买入股票数量
    g.daily_buy_count  = 5
    
###------------------------------------------------------------------------------    
# 过滤器，过滤停牌，ST，科创，新股        
def filter_special(context,stock_list):
    curr_data = get_current_data()
    
    # 过滤科创板'688'，st，停牌
    stock_list= [stock for stock in stock_list if stock[0:3] != '688']  
    stock_list = [stock for stock in stock_list if not curr_data[stock].is_st]
    stock_list = [stock for stock in stock_list if not curr_data[stock].paused] 
    stock_list = [stock for stock in stock_list if 'ST' not in curr_data[stock].name]
    stock_list = [stock for stock in stock_list if '*'  not in curr_data[stock].name]
    stock_list = [stock for stock in stock_list if '退' not in curr_data[stock].name]
    stock_list = [stock for stock in stock_list if  curr_data[stock].day_open>1]
    stock_list = [stock for stock in stock_list if  (context.current_dt.date()-get_security_info(stock).start_date).days>150]

    return   stock_list  

###------------------------------------------------------------------------------
# 创建四个存储器，用于存储前四天结束时资产量（全局变量）（用情绪周期可选部分）

g.store_former20 = 200000
g.store_former19 = 200000
g.store_former18 = 200000
g.store_former17 = 200000
g.store_former16 = 200000
g.store_former15 = 200000
g.store_former14 = 200000
g.store_former13 = 200000
g.store_former12 = 200000
g.store_former11 = 200000
g.store_former10 = 200000
g.store_former9 = 200000
g.store_former8 = 200000
g.store_former7 = 200000
g.store_former6 = 200000
g.store_former5 = 200000
g.store_former4 = 200000
g.store_former3 = 200000
g.store_former2 = 200000
g.store_former1 = 200000
g.standard=200000
g.rest_day = 0

###------------------------------------------------------------------------------
###盘前粗筛、选票（前日未涨停）、定计划模块###

def before_trading_start(context):
    g.drzt_stock = set()
    
    #----------------------------------------------------------------------------
    # 创建计时器，用于计算每天开盘后过了几分钟，后续的handle_data模块对此加以迭代
    # 时间大于一定值后不再打炸板票（尾盘炸板很容易雪崩）
    # 时间大于一定值后手中国持仓再不涨停就跑，不要格局。具体格局多久，取决于该股票类型（例如连板与否）
    global time_counter
    time_counter=0
    
    #----------------------------------------------------------------------------
    # 创建第一层股票池，池中为目标行业内剔除st、科创、停牌后的所有股票
    # 主观选定行业，例如HY001是石油
    g.stocks_exsit = get_industry_stocks('HY001') + get_industry_stocks('HY002') \
            + get_industry_stocks('HY003') + get_industry_stocks('HY004') \
            + get_industry_stocks('HY005') + get_industry_stocks('HY006') \
            + get_industry_stocks('HY007') + get_industry_stocks('HY008') \
            + get_industry_stocks('HY009') + get_industry_stocks('HY010') \
            + get_industry_stocks('HY011') 
    g.stocks_exsit = set(g.stocks_exsit)
    # 第一层股票池中过滤掉ST等
    g.stocks_exsit = set(filter_special(context,g.stocks_exsit)) 
    
    #----------------------------------------------------------------------------
    # 定义过滤器，用于过滤今天已经建仓的股票，当天不会再买 
    g.today_bought_stocks = set()
    # 另一个过滤器，原策略中用于过滤炸板但仍>9%的票，对我们这策略没用
    # g.today_filter_stocks = []
    
    #----------------------------------------------------------------------------
    # 取前日涨停价，最高价，收盘价，最低价，成交量
    # 注意数据类型为dataframe，调用时需要用g.high_limit[security][0]的格式！
    g.high_limit = history(1,'1d','high_limit',g.stocks_exsit)
    g.high = history(1,'1d','high',g.stocks_exsit)
    g.close = history(1,'1d','close',g.stocks_exsit)
    g.low = history(1,'1d','low',g.stocks_exsit)
    g.volume = history(1,'1d','volume',g.stocks_exsit)

    
    #----------------------------------------------------------------------------
    # 可选部分-判断前五日是否有涨停要用到的模块
    # 这些值我原来是直接在循环里调用的，但是这样要一次次调用，查找，很耗算力
    # 只能用笨办法，放在外面了
    g.high_limitformer2 = history(2,'1d','high_limit',g.stocks_exsit)
    g.high_limitformer3 = history(3,'1d','high_limit',g.stocks_exsit)
    g.high_limitformer4 = history(4,'1d','high_limit',g.stocks_exsit)
    g.closeformer2 = history(2,'1d','close',g.stocks_exsit)
    g.closeformer3 = history(3,'1d','close',g.stocks_exsit)
    g.closeformer4 = history(4,'1d','close',g.stocks_exsit)
    
    #----------------------------------------------------------------------------
    # 创建第二层股票池，筛选出前日未涨停，且当日涨停能创新高，\
    # 且前期涨幅不大（涨停不是趋势股的最后一波高潮），\
    # 且前四日无涨停的股票（潜在的首板）
    g.qrwzt_stock = set()
    # print(g.qrwzt_stock)
    for security in g.stocks_exsit:
        
        #------------------------------------------------------------------------
        # 可选部分-high25，用于筛选当日如果涨停就能突破前高的股票，不一定要用
        # 可选部分-MA25，用于筛选前期涨幅不大的股票
        # 获取股票的前二十五日收盘价
        close_data25 = attribute_history(security, 25, '1d', ['close'])
        # 计算前25日最高价
        high25 = close_data25['close'].max()
        # 计算前25日均价
        MA25 = close_data25['close'].mean()
        # 判定是否满足要求
        flag1 = 0
        if (g.close[security][0] > 0.92 * high25)\
        and (g.close[security][0] < 1.1 * MA25):
            flag1 = 0
        else:
            flag1 = 1
        
        #------------------------------------------------------------------------
        # 可选部分-检测前四日是否涨停
        flag2 = 0
        # 判定是否满足要求
        # 用的是笨办法，没办法，history函数的调用与查找不能放在循环内，不然会很耗算力
        if (g.high_limitformer2[security][0] == g.closeformer2[security][0])\
        or (g.high_limitformer3[security][0] == g.closeformer3[security][0])\
        or (g.high_limitformer4[security][0] == g.closeformer4[security][0]):
            flag2 = 1
        else:
            flag2 = 0
        
        #------------------------------------------------------------------------
        # 判定，筛选股票池
        if (g.high[security][0] < g.high_limit[security][0])\
        and (flag1 == 0)\
        and (flag2 == 0):
            g.qrwzt_stock.add(security)
    
    #----------------------------------------------------------------------------
    # 创建买入计数器，预设好买入股票数量以及单位买入量
    # 注意此处不是执行买入的程序！只是预设！
    g.number=0
    for security in context.portfolio.positions:
        g.number+=1
    if(g.daily_buy_count-g.number >0):
        g.buy_cash = context.portfolio.available_cash/(g.daily_buy_count-g.number)
    else:
        g.buy_cash = 0
        
    #----------------------------------------------------------------------------
    # 可选部分-情绪周期，市场模式识别
    # 迭代赋值
    g.store_former16 = g.store_former15
    g.store_former15 = g.store_former14
    g.store_former14 = g.store_former13
    g.store_former13 = g.store_former12
    g.store_former12 = g.store_former11
    g.store_former11 = g.store_former10
    g.store_former10 = g.store_former9
    g.store_former9 = g.store_former8
    g.store_former8 = g.store_former7
    g.store_former7 = g.store_former6
    g.store_former6 = g.store_former5
    g.store_former5 = g.store_former4
    g.store_former4 = g.store_former3
    g.store_former3 = g.store_former2
    g.store_former2 = g.store_former1
    g.store_former1 = context.portfolio.total_value
    
    g.store_max15 = 0
    g.store_min15 = 1000000000
    for each in [g.store_former1, g.store_former2, g.store_former3, g.store_former4,\
                 g.store_former5, g.store_former6, g.store_former7, g.store_former8,\
                 g.store_former9, g.store_former10, g.store_former11, g.store_former12,\
                 g.store_former13, g.store_former14, g.store_former15, g.store_former16]:
        # if each > g.store_max15:
        #    g.store_max15 = each
        if each < g.store_min15:
            g.store_min15 = each
    for each in [g.store_former1, g.store_former2, g.store_former3, g.store_former4, g.store_former5, g.store_former6]:
        if each > g.store_max15:
            g.store_max15 = each
            
            
    
#     if context.portfolio.total_value>g.store_max15:
#         g.store_max=context.portfolio.total_value
    
    # 计算三天的累计回撤/收益，出现大幅偏离就休息几天
    max_profit15 = g.store_former1 / g.store_min15 - 1
    
    min_profit15 = g.store_former1/g.store_max15-1
    print("max_profit15 =", max_profit15)
    
    if min_profit15 < -0.05:
        g.rest_day=15
        g.store_max=g.store_former1
    
    if max_profit15 >= 0.15:
        g.rest_day=15

        
    
    
    # 清仓，休息休息
    if g.rest_day != 0:
        g.rest_day -= 1
        return
    
    
    





###------------------------------------------------------------------------------  
###执行买卖操作模块###    
   
# 在每分钟的第一秒运行, data 是上一分钟的切片数据
def handle_data(context, data):
    
    # 情绪周期到了，就清仓休息休息
    if g.rest_day != 0:
        for security in context.portfolio.positions:
            # 卖出
            order_target(security, 0)
            # 记录这次卖出
            log.info("Selling %s" % (security))
        return
    
    #----------------------------------------------------------------------------
    current_data = get_current_data()
    
    #----------------------------------------------------------------------------
    # 记录时间，每次循环时间（分钟）+1，每日重置
    global time_counter
    time_counter += 1
    
    #----------------------------------------------------------------------------
    # 从每天开盘前筛好的第二层池子里（g.qrwzt_stock），\
    # 选出当日涨停过的股票，放入drzt池子里，每15分钟执行一次
    if time_counter % 15 == 0:
        for security in g.qrwzt_stock:
            if current_data[security].last_price == current_data[security].high_limit:
                g.drzt_stock.add(security)
   
    #----------------------------------------------------------------------------
    # 定义变量；前一分钟价格
    # last_min_price = history(1,'1m','close',g.drzt_stock)
    
    #----------------------------------------------------------------------------
    # 可选部分-烂板后第二天未涨停，开盘走
    if(time_counter >= 0):
       for security in context.portfolio.positions:
           # 前一天烂板，开盘就卖出
           if (history(1,'1d','close',[security])[security][0] \
            < history(1,'1d','high_limit',[security])[security][0])\
           and (data[security].close < current_data[security].high_limit)\
           and (context.portfolio.positions[security].closeable_amount > 0):
                # 卖出
                order_target(security, 0)
                # 记录这次卖出
                log.info("Selling %s" % (security))
    
    #----------------------------------------------------------------------------
    
    # 可选部分-连板70分钟仍未涨停，卖出
    if(time_counter >= 70):
        for security in context.portfolio.positions:
            # 连板且未涨停，不格局，早点卖出
            # 注意此处用1日前收盘价与5日前收盘价之比来判断前期涨幅，从而识别高位风险
            # 并不一定是连板，也可能是高位加速
            # 这里改了一下，70分钟后不能维持在+8.5%以上，卖出
            if (data[security].close< 0.985 * current_data[security].high_limit)\
            and (history(5,'1d','close',[security])[security][0] * 1.23 \
            < history(1,'1d','close',[security])[security][0])\
            and (context.portfolio.positions[security].closeable_amount > 0):
                # 卖出
                order_target(security, 0)
                # 记录这次卖出
                log.info("Selling %s" % (security))
    
    #----------------------------------------------------------------------------
    
    # 对于一般情况，下午两点仍未涨停，不格局，卖出
    # 这里改了一下，下午两点后不在+8.5%以上，卖出
    if(time_counter >= 182):
        for security in context.portfolio.positions:
            if(data[security].close< 0.985 * current_data[security].high_limit)\
            and (context.portfolio.positions[security].closeable_amount > 0):
                # 卖出
                order_target(security, 0)
                # 记录这次卖出
                log.info("Selling %s" % (security))
    
    #----------------------------------------------------------------------------
    # 买入
    if(len(g.today_bought_stocks)+g.number >= g.daily_buy_count):
        # print(len(g.today_bought_stocks)+g.number)
        return  
    if(g.buy_cash == 0):
        return  
    # 打板，打到2:40为止
    if (time_counter<220):
        for security in ([i for i in g.drzt_stock]):
            if ((security in context.portfolio.positions)==0\
            and 1.093 < data[security].close/g.close[security][0] < 1.0988 ):
#           and current_data[security].last_price/last_min_price[security][0] >= 1.01):
#           and current_data[security].last_price/last_min_price[security][0] >= 1.01):
                # 仓位控制
                if(len(g.today_bought_stocks)+g.number >= g.daily_buy_count):
                    return  
                cash_before=context.portfolio.available_cash
                # 买入这么多现金的股票
                order_value(security, g.buy_cash)
                # 放入今日已买股票的集合
                if(cash_before>context.portfolio.available_cash):
                    # 成功买进
                    g.today_bought_stocks.add(security)
                    # 记录这次买入
                    log.info("Buying %s" % (security))

###----------------------------------------------------------------------------
# 检测未来函数
set_option("avoid_future_data", True)




