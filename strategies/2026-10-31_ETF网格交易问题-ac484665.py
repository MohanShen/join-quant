# Clone from JoinQuant
# postId: ac484665afa9ec23a9d2695bdebfb7f1
# backtestId: 929095cb05e70bc8687e6da70e13fa07
# title: ETF网格交易问题

import numpy
import pandas as pd
from pandas import Series
def initialize(context):
    
    g.starting_cash = context.portfolio.starting_cash
    g.starting_cash_ratio = 0 #全仓买入
    print ['starting_cash', g.starting_cash]
    
    
    #set_commission(PerTrade(buy_cost=0.0002, sell_cost=0.00002, min_cost=5))
    
    #顶格仓位/底格仓位
    
    g.cells_count_total = 20 
    g.cells_count_bottom = 1
    
    #每格涨跌比例，可以设置差异化网格
    g.big_ratio_per_cell = 0.005
    g.small_ratio_per_cell = 0.005
    
    
    #默认为牛市
    g.long = True
    
    #初始价格、基准架构、下一次买入或者卖出价格
    g.is_long = {} # 牛市1 熊市-1 震荡 0
    
    #每格多少手
    g.cell_size = {}
    g.base_price = {}
    g.big_diff_price = {}
    g.small_diff_price = {}
    
    g.is_first_day = True
 
    
    #创业板ETF
    g.buy_stock = ['159915.XSHE']
    set_universe(g.buy_stock)
    
    # 设定创业板作为基准
    set_benchmark('399006.XSHE')
    
    #真实价格交易
    set_option('use_real_price',True)
    
    # 设置日志输出只输出错误信息
    log.set_level('order', 'error')
    
    
    
    
# 取n的倍数
def roundv( init_value, n ):
    return round(init_value/n,0)*n

def init_var( stock, current_price ):
    
    #以当前价设置基准价
    g.base_price[stock] = current_price
    
    #计算每格手数
    g.cell_size[stock] = roundv(g.starting_cash/(g.cells_count_total*current_price),100)
    
    #设置每格价差
    g.big_diff_price[stock] = round(current_price *  g.big_ratio_per_cell,3)
    g.small_diff_price[stock] = round(current_price *  g.small_ratio_per_cell,3)
    
    #牛熊盘点，待完善
    g.is_long[stock] = 1 if(g.long) else -1
    
    print [ 'base_price',g.base_price,\
            'cell_size',g.cell_size,\
            'big_diff_price',g.big_diff_price,\
            'small_diff_price',g.small_diff_price,\
            'is_long',g.is_long\
            ]
    #print '========================================='
    
    return None


# 初始底仓选择，判断没有initial_price，则建立基准价
def order_stock(context,data, stock):
    current_price = data[stock].price
    
    
    #第一次时，g.base_price没有stock属性
    if stock not in g.base_price:
        init_var( stock, current_price )
        
        if g.is_first_day:
            #第一天买入1%作为底仓
            order_target(stock, g.starting_cash*0.1)
            g.is_first_day = False
            return
        
        return
        
    else:
        # 根据牛熊判断买卖的比率
        if g.is_long[stock] == -1:
            #熊市大笔卖，小笔买
            diff_price_sell = g.big_diff_price[stock]
            diff_price_buy = g.small_diff_price[stock]
        elif g.is_long[stock] == 1:
            #牛市小笔慢慢卖，大笔买
            diff_price_sell = g.small_diff_price[stock]
            diff_price_buy = g.big_diff_price[stock]
        else:
            #震荡市场小笔卖买参与
            diff_price_sell = g.small_diff_price[stock]
            diff_price_buy = g.small_diff_price[stock]
        
        #基准价、差价
        base_price = g.base_price[stock]
        
        #计算差价
        diff_price = round(current_price - base_price,3)
        
        #买/卖的格子数
        if diff_price > 0:
            cells_count = abs(int(diff_price/diff_price_sell))
        elif diff_price < 0:
            cells_count = abs(int(diff_price/diff_price_buy))
        else:
            cells_count = 0


        
        #如果差价达不到一格，退出
        if cells_count < 1:
            #打印分析为啥没有成交
            print ['#####',\
                'current_price', current_price,\
                'base_price', base_price,\
                'diff_price', diff_price,\
                'cells_count', cells_count]
            return
        
        '''
        print [\
            'current_price', current_price,\
            'base_price', base_price,\
            'diff_price', diff_price,\
            'cells_count', cells_count,\
            'diff_price_sell', diff_price_sell,\
            'diff_price_buy', diff_price_buy]
        '''
        
        ############################################
        # 超出一格价格范围

        #每格下单数量
        cell_size = g.cell_size[stock]
        
        #上涨卖出到底仓，则调整当前仓位为中仓位
        bottom_amount = g.cells_count_bottom * cell_size
        #下跌买入到 定格仓位-底仓仓位，则调整到中仓位
        max_amount = (g.cells_count_total-g.cells_count_bottom) * cell_size
        #中间仓位
        middle_amount = g.cells_count_total* cell_size / 2 
        
        
        #下单数量
        order_amount = cells_count*cell_size
        
        #下单后的持仓数量
        if context.portfolio.positions.has_key(stock):
            position_amount = context.portfolio.positions[stock].total_amount
        else:
            position_amount = 0
        
        #下单到目标
        order_target_amount = 0

        #根据网格、最低持仓量、满仓下单
        if diff_price > 0: #卖出
            
            #下单到目标仓位
            order_target_amount = position_amount - order_amount
            
            #设置新的基准价，实际的系统，应按照基准价下订单
            new_base_price = round(base_price + cells_count * diff_price_sell,3)
            
            #最低持仓量保障
            if order_target_amount < bottom_amount:
                #上涨卖出后如果低于底仓，则买满80%仓位
                order_target_amount = middle_amount
            
        else: #  diff_price < 0
            
            #下单到目标仓位
            order_target_amount = position_amount + order_amount
            
            #设置新的基准价，实际的系统，应按照基准价下订单
            new_base_price = round(base_price - cells_count * diff_price_sell,3)

            #卖出时，如果满仓了，则调整到底仓水平
            if order_target_amount > max_amount:
                #下单数量
                order_target_amount = middle_amount
            
        order_target_amount = roundv(order_target_amount,100)

        '''
        print [\
            'order_amount', order_amount,\
            'order_target', order_target_amount,\
            'position', position_amount,\
            'cells_count',cells_count,\
            'cell_size',cell_size, \
            'bottom_amount',bottom_amount,\
            'max_amount',max_amount,\
            'current_price',current_price, \
            'base_price',base_price, \
            'new_base_price',new_base_price]  
        '''
      
        
      
        #下单
        order_target( stock, order_target_amount )
        
        new_position = context.portfolio.positions[stock].total_amount
        
        
        record( position = position_amount, newPos = new_position, p =new_base_price )
        print ['****',
            'price_Cur_NBase_Obase', current_price, new_base_price,base_price,\
            'diff,cells',diff_price,cells_count,\
            'amount-now-new',new_position-position_amount,position_amount,new_position,\
            'bot-m-max',bottom_amount,middle_amount,max_amount,\
            ]
            
        #print '========================================='
            
        #设置新的基准价格
        g.base_price[stock] = new_base_price
       
    
    
    return None


# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    
    """
    # 上证指数止损，前一天跌幅大于3%
    if conduct_nday_stoploss(context, '000001.XSHG', 2,-0.03):
        return
    """
    
    for stock in g.buy_stock:
        order_stock(context,data, stock)
    	

# 计算股票前n日收益率
def security_return(days,security_code):
    hist1 = attribute_history(security_code, days + 1, '1d', 'close',df=False)
    security_returns = (hist1['close'][-1]-hist1['close'][0])/hist1['close'][0]
    return security_returns

# 止损，根据前n日收益率
def conduct_nday_stoploss(context,security_code,days,bench):
    if  security_return(days,security_code)<= bench:
        for stock in g.buy_stock:
            order_target_value(stock,0)
            log.info("Sell %s for stoploss" %stock)
        return True
    else:
        return False
        
# 计算股票累计收益率（从建仓至今）
def security_accumulate_return(context,data,stock):
    current_price = data[stock].price
    cost = 0;
    
    if stock  in context.portfolio.positions:
        cost = context.portfolio.positions[stock].avg_cost
        
    if cost != 0:
        return (current_price-cost)/cost
    else:
        return None

# 个股止损，根据累计收益
def conduct_accumulate_stoploss(context,data,stock,bench):
    if security_accumulate_return(context,data,stock) != None\
    and security_accumulate_return(context,data,stock) < bench:
        order_target_value(stock,0)
        log.info("Sell %s for stoploss" %stock)
        return True
    else:
        return False

# 选股：连续N日下跌
def is_fall_nday(days,stock):
    his = history(days+1,'1d','close',[stock],df =False)
    cnt = 0
    for i in range(days):
    	daily_returns = (his[stock][i+1] - his[stock][i])/his[stock][i]
    	if daily_returns <0:
    	    cnt += 1
    if cnt == 5:
    	return True
    else:
        return False

# 比较现价与N日均价
def compare_current_nmoveavg(data,stock,days,multi):
    current_price = data[stock].price
    moveavg = data[stock].mavg(days)
    if current_price > multi * moveavg:
        return True
    else:
        return False
