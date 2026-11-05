# Clone from JoinQuant
# postId: 4abaded824f823675ef9c0e8b72774a0
# backtestId: 0e2aba774abab2897f860d5b1a26280b
# title: 银行股-机器学习选股-中线持有

'''
策略描述： 银行股，中线（60天）持有，随机森林模型选股
止损描述： 无
版权所有： nil0 
'''
# 导入函数库
import jqdata
import numpy as np
import pandas as pd
from prettytable import PrettyTable
import math
import datetime
import mlbkstocks as mbs

    
# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('>>>>>>>>>>>>>>>银行股中线持有策略 开始运行<<<<<<<<<<<<<<<<<')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    #初始化可选股票列表
    g.wlist = set(['600000.XSHG','600016.XSHG','600036.XSHG','601166.XSHG','600015.XSHG','000001.XSHE','002142.XSHE','601169.XSHG','601398.XSHG'])
    
    g.buy_stocks = []
    g.sell_stocks = []
    #持仓记录
    g.holds = pd.DataFrame([],columns=['amount','price','avgcost','pmax','plast','buydate','holddays','fbdays','wvdays','tfbdays','twvdays']) #index直接存股票代码
    g.hold_rate = 0.0 #仓位百分比
    g.hold_period = 60 #持仓天数
    g.buy_count = 2 # 每次买入几只股票
    g.gain_rate = 10.0 * 2.5 #目标获利比率
    g.stop_loss_rate = -5.0 #止损比率
    g.fb_rate = -6.18 # 从高点回落比率，大行情时期用-8.0比较好
    g.hold_rate_min = 95.0 #最低仓位
    g.total_values = 0.0 # 总值 = 现金 + 股票市值
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
## 开盘前运行函数     
def before_market_open(context):
    # 输出运行时间
    #log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    
    date = context.current_dt.strftime('%Y-%m-%d')
    #to_buy_stocks = set(mbs.pick_bank_stocks(date)['stock'].values) & g.wlist
    to_buy_stocks = set(mbs.pick_bank_stocks(date)['stock'].values)
    g.buy_stocks = list(to_buy_stocks - set(g.holds.index.values)) #去掉已经持仓的
    
    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    if(len(g.buy_stocks)>0):
        msg = '今天可买股票：'
        for s in g.buy_stocks:
            msg = msg + show_stock(s) + " "
    else:
        msg = '今天没有可买股票，慢慢享受美好的一天吧~'
    send_message(msg)
    log.info(msg)

def sell_stocks(context):
    for stock in g.holds.index:
        holddays = g.holds.loc[stock,'holddays']
        # 计算回报率
        roe = round(100 * (g.holds.loc[stock,'price'] /g.holds.loc[stock,'avgcost'] -1.0),2)
        # 计算回落率
        fallback = round(100 * (g.holds.loc[stock,'price'] /g.holds.loc[stock,'pmax'] -1.0),2)
        # 计算梯度止损比例，如果收益小于这个止损比例，卖出
        threshold = round(holddays/g.hold_period * g.gain_rate,2)
        fbwvdays = g.holds.loc[stock,'fbdays'] + g.holds.loc[stock,'wvdays']
        # -------------------------止损判断条件--------------------
        if(holddays>= g.hold_period):
            log.info('已经持有%s %d天, ROE=%.2f%% FB=%.2f%% , 卖出...' %(show_stock(stock),holddays,roe,fallback))
            order_target(stock, 0)
        else:
            log.info('%s 持股%d天, ROE=%.2f FB=%.2f , 继续持有...' %(show_stock(stock),holddays,roe,fallback))
    

## 买入股票
def buy_stocks(context):
    
    if(len(g.buy_stocks) < 1): #没有股票可买
        return 
    
    # 可用资金所占仓位比例
    ar = round(100 * context.portfolio.subportfolios[0].available_cash / context.portfolio.subportfolios[0].total_value,0)
    
    if(ar > 100 - g.hold_rate_min): #不到最低仓位，买入
        # 计算最多可买几只股票

        buy_count = g.buy_count - len(g.holds)
        if(buy_count < 1): 
            return
        
        to_buy = g.buy_stocks
        if(buy_count > len(to_buy)):
            buy_count = len(to_buy)
        
        # 每只股票所用资金，只能基本平均
        value = context.portfolio.subportfolios[0].available_cash / (g.buy_count - len(g.holds)) 
        for i in range(buy_count):
            stock = to_buy[i]
            cur_price = get_close_price(stock,1,'1m')
            if(cur_price != np.nan):
                # 通过当前价，四乘五入的计算要买的股票数。
                amount = int(round(value / cur_price / 100) * 100)
                new_value = amount * cur_price
                order = order_value(stock, new_value)
                if(order != None):
                    log.info('成功买入%d股 %s !' %(order.filled,show_stock(stock)))
                else:
                    log.info('买入%s失败...' %show_stock(stock))
        

## 开盘时运行函数
def market_open(context):

    sell_stocks(context)
    update_holds(context,0)

    buy_stocks(context)
    

 
## 收盘后运行函数  
def after_market_close(context):

    update_holds(context)
    
    log.info(show_holds(context))
    
    log.info('========================>>无聊的一天结束<<============================')

## 更新持仓数据
def update_holds(context, days=1):
    cash = context.subportfolios[0].cash
    p_value = context.subportfolios[0].positions_value
    g.total_values = p_value + cash
    g.hold_rate = p_value * 100 / (cash + p_value)
    
    #更新当天成交的持仓数据
    for stock in context.subportfolios[0].long_positions.keys():
        pos = context.subportfolios[0].long_positions[stock]
        if(stock in g.holds.index):
            pmax = g.holds.loc[stock,'pmax']
            plast = g.holds.loc[stock,'plast']
            g.holds.loc[stock,'plast'] = g.holds.loc[stock,'price']
            g.holds.loc[stock,'price'] = pos.price
            g.holds.loc[stock,'pmax'] = max(pmax,pos.price)
            if(pos.price <= pmax):
                if(pos.price < plast):
                    g.holds.loc[stock,'fbdays'] = days + g.holds.loc[stock,'fbdays']
                    g.holds.loc[stock,'tfbdays'] = days + g.holds.loc[stock,'tfbdays']
                else:
                    g.holds.loc[stock,'wvdays'] = days + g.holds.loc[stock,'wvdays']
                    g.holds.loc[stock,'twvdays'] = days + g.holds.loc[stock,'twvdays'] 
            else:
                
                g.holds.loc[stock,'fbdays'] = 0
                g.holds.loc[stock,'wvdays'] = 0
            g.holds.loc[stock,'holddays'] = days + g.holds.loc[stock,'holddays']
            g.holds.loc[stock,'amount'] = pos.total_amount
            ocost = g.holds.loc[stock,'avgcost']
            g.holds.loc[stock,'avgcost'] = pos.avg_cost
            #发生了分红配股
            if(ocost > pos.avg_cost):
                g.holds.loc[stock,'pmax'] = round((pmax * pos.avg_cost/ocost),2)
            
        else:
            g.holds.loc[stock] = {  'amount':pos.total_amount,
                                    'price':pos.price,
                                    'avgcost':pos.avg_cost,
                                    'pmax':pos.price,
                                    'plast':pos.price,
                                    'buydate':pos.init_time,
                                    'holddays':1,
                                    'fbdays':0,
                                    'wvdays':0,
                                    'tfbdays':0,
                                    'twvdays':0
                                 }
    #去掉已经卖掉的
    hstocks  = context.subportfolios[0].long_positions.keys()
    for stock in g.holds.index.values:
        if(stock not in hstocks):
            g.holds = g.holds.drop(stock)
    
def show_holds(context):
    sub_str = ''
    table = PrettyTable([ "代码   名称", "持仓量", "成本价","上日价", "当前价","最高价","盈亏", "持仓比","仓龄"])
    
    for stock in g.holds.index:
        stock_str = show_stock(stock)
        stock_raite = (g.holds.loc[stock,'amount'] * g.holds.loc[stock,'price']) / g.total_values * 100
        table.add_row([
                       stock_str,
                       g.holds.loc[stock,'amount'],
                       g.holds.loc[stock,'avgcost'],
                       g.holds.loc[stock,'plast'],
                       g.holds.loc[stock,'price'],
                       g.holds.loc[stock,'pmax'],
                       "%.2f%%" % ((g.holds.loc[stock,'price'] - g.holds.loc[stock,'avgcost']) / g.holds.loc[stock,'avgcost'] * 100),
                       "%.2f%%" % (stock_raite),
                       "%d" %(g.holds.loc[stock,'holddays'])
                       ]
                      )
    
    sub_str += '[仓号: %d] [总值:%d] [持股数:%d] [仓位:%.2f%%] \n' % (0,
                                                                     g.total_values,
                                                                     len(g.holds)
                                                                     , g.hold_rate)
    if len(g.holds) == 0:
        return '子仓详情:\n' + sub_str
    else:
        return '子仓详情:\n' + sub_str + str(table)
        


  
def get_close_price(security, n, unit='1d'):
    '''
    获取前n个单位时间当时的收盘价
    为防止取不到收盘价，试3遍
    :param security: 
    :param n: 
    :param unit: '1d'/'1m'
    :return: float
    '''
    cur_price = np.nan
    for i in range(3):
        cur_price = attribute_history(security, n, unit, 'close', True)['close'][0]
        if not math.isnan(cur_price):
            break
    return cur_price
  
def show_stock(stock):
    '''
    获取股票代码的显示信息    
    :param stock: 股票代码，例如: '603822.SH'
    :return: str，例如：'603822 嘉澳环保'
    '''
    return u"%s %s" % (stock[:6], get_security_info(stock).display_name)
  


