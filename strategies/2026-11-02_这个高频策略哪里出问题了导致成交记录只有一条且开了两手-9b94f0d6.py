# Clone from JoinQuant
# postId: 9b94f0d6dbfbe84d583b42fb0502a637
# backtestId: 7ad4a9ebe65fef620e3db7b0dacb0cd3
# title: 这个高频策略哪里出问题了导致成交记录只有一条且开了两手？

from jqdata import *
import datetime

## 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
   
    #设置初始账户#
    init_cash=context.portfolio.starting_cash
    #设置期货账户#
    set_subportfolios([SubPortfolioConfig(cash=init_cash,type='futures')])
    #设置手续费#
    set_order_cost(OrderCost(open_commission=0, 	close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)
   
    run_daily(before_market_open,time='08:30',reference_security='M9999.XDCE')
    run_daily(after_market_open,time='23:30',reference_security='M9999.XDCE')
   
def before_market_open(context):
    #定义空列表

    #建立吃单价格列表
    g.list_eating=[]
    #建立基点列表
    g.list_base=[]
    #建立开多仓价格列表
    g.list_long_open=[]
    #建立开空仓价格列表
    g.list_short_open=[]
   
    #设置交易期货代码#
    g.code = 'M2009.XDCE'
    #订阅标的的tick事件，必须在频率为tick的回测、模拟中使用
    subscribe(g.code,'tick')
   
def handle_tick(context,tick):

    #获取盘口数据    
    tick_data=get_ticks(g.code,count=1,end_dt=context.current_dt,fields=['time','a1_p','a1_v',	'b1_p','b1_v'],skip=True)


    current_a1_v=tick_data['a1_v']
    current_a1_p=tick_data['a1_p']
    current_b1_v=tick_data['b1_v']
    current_b1_p=tick_data['b1_p']

    long_closeable_amount=0
    short_closeable_amount=0
    if g.code in context.portfolio.long_positions.keys():
        long_closeable_amount=context.portfolio.long_positions[g.code].closeable_amount
    if g.code in context.portfolio.short_positions.keys():
       short_closeable_amount=context.portfolio.short_positions[g.code].closeable_amount
    
  
    #筛选符合条件的单量及其对应的价格数据进行存储
    #如果a1_v单量小于40
    if current_a1_v<40:
        #把相应的a1_p数据存储至list_eating列表
        g.list_eating.append(current_a1_p)
        #如果最新价格数据与列表最新价格数据重复，不操作
        #print(int(current_a1_p),g.list_eating[-1])
        if int(current_a1_p)==g.list_eating[-1]:
            pass

    #如果b1_v单量小于40
    if current_b1_v<40:
        #把相应的b1_v数据存储至list_eating列表
        g.list_eating.append(current_b1_p)
        #如果最新价格数据与列表最新价格数据重复，不操作
        if current_b1_p==g.list_eating[-1]:
            pass

    #如果a1_v和b1_v单量同时小于40，不操作
    if current_a1_v<40 and current_b1_v<40:
        pass

    #利用list_eating元素判断基点，并将基点存储至空的列表list_base
    #如果列表里有三个元素
    if len(g.list_eating)==3:
        #如果元素[-1]等于[-3]
        if g.list_eating[-1]==[-3]:
            #把列表list_eating的最新元素[-1]添加到列表list_base
            g.list_base.append(g.list_eating[-1])
        
        #如果元素[-1]不等于[-3]
        if g.list_eating[-1]!=[-3]:
            #把列表list_eating的最新元素[-2]添加到列表list_base
            g.list_base.append(g.list_eating[-2])

    #如果列表里有四个及以上元素
    if len(g.list_eating)>=4:
        #如果列表list_eating[-1]等于[-3]且list_eating[-2]等于[-4]
        if g.list_eating[-1]==[-3] and list_eating[-2]==[-4]:
            #基点为list_eating[-2]
            base=[-2]
            #把list_eating[-2]添加到列表list_base里
            g.list_base.append(g.list_eating[-2])

    #如果列表list_eating[-1]等于[-3]且list_eating[-2]不等于[-4]
        if g.list_eating[-1]==[-3] and list_eating[-2]!=[-4]:
            #基点为list_eating[-1]
            base=[-1]
            #把list_eating[-1]添加到列表list_base里
            g.list_base.append(g.list_eating[-1])

    ##如果列表list_eating[-1]不等于[-3]
        if g.list_eating[-1]!=[-3]:
            #基点为list_eating[-2]
            base=[-2]
            #把list_eating[-2]添加到列表list_base里
            g.list_base.append(g.list_eating[-2])

    #利用list_eating[-1]和list_base[-1]作比较，判断是否回找
    #如果list_eating[-1]等于list_base[-1]
    if len(g.list_eating) > 0 and len(g.list_base) > 0:
        if g.list_eating[-1]==g.list_base[-1]:
            #回找
            #如果没有仓位
            if (long_closeable_amount)==0 and (short_closeable_amount)==0:
    
                #如果列表list_eating[-1]小于[-2]
                print(g.list_eating[-1])
                if int(g.list_eating[-1]) < -2:
                    #在a1_p=list_eating[-1]时开多
                    order(g.code,1,style=LimitOrderStyle(g.list_eating[-1]),side='long',pindex=0)
                    #检查order里是否有订单，如果有，记录成交价格，存储至list_long_open
                    orders=order(g.code,1,style=LimitOrderStyle(g.list_eating[-1]),side='long',pindex=0)
                    
                    #如果没有成交
                    if orders is none:
                        print('创建订单失效')
                    #如果成交，存储成交价格至列表list_long_open
                    else:
                        g.list_long_open.append(orders.price)
    
    
                #如果列表list_eating[-1]大于[-2]
                if g.list_eating[-1]>[-2]:
                    #在b1_p=list_eating[-1]时开空
                    order(g.code,1,style=LimitOrderStyle(g.list_eating[-1]),side='short',pindex=0)
                    #检查order里是否有订单，如果有，记录成交价格，存储至list_short_open
                    orders=order(g.code,1,style=LimitOrderStyle(g.list_eating[-1]),side='short',pindex=0)
    
                    #如果没有成交
                    if orders is 'none':
                        print('创建订单失效')
                    #如果成交，存储成交价格至列表list_short_open
                    else:
                        try:
                            g.list_short_open.append(orders.price)
                        except:
                            pass
    
    
            #如果有仓位
    
            #如果有多仓
            if long_closeable_amount>0 and len(g.list_long_open) > 0:
                #执行平仓逻辑
                #有多仓则平多仓
                #多仓在b1_p平仓
    
                #如果b1_p价格比list_long_open[-1]多1个点，止盈
                if current_b1_p - g.list_long_open[-1]==1:
                    order_target(g.code,LimitOrderStyle(list_long_open[-1]+1),0)
    
                #如果b1_p价格比list_long_open[-1]多0个点，不操作，除非保持一分钟不动，平仓
                if current_b1_p - g.list_long_open[-1]==0:
                    order_target(g.code,LimitOrderStyle(list_long_open[-1]+0),0)
                
    
                #如果b1_p价格比list_long_open[-1]少1个点，不操作，除非保持一分钟不动，平仓
                if current_b1_p - g.list_long_open[-1]==-1:
                    order_target(g.code,LimitOrderStyle(list_long_open[-1]-1),0)
    
    
                #如果b1_p价格比list_long_open[-1]少2个点，止损
                if current_b1_p - g.list_long_open[-1]==-2:
                    order_target(g.code,LimitOrderStyle(list_long_open[-1]-2),0)
    
            #如果有空仓
            if short_closeable_amount>0 :
                #有空仓则平空仓
                #空仓在a1_p平仓
                if len(g.list_short_open) > 0:
                    #如果a1_p价格比list_short_open[-1]多2个点，止损
                    if current_a1_p - g.list_short_open[-1]==2:
                        order_target(g.code,LimitOrderStyle(list_short_open[-1]+2),0)
                if len(g.list_long_open) > 0:
                    #如果a1_p价格比list_long_open[-1]多1个点，不操作，除非保持一分钟不动，平仓
                    if current_a1_p - g.list_long_open[-1]==1:
                        order_target(g.code,LimitOrderStyle(list_long_open[-1]+1),0)
        
        
                    #如果a1_p价格比list_long_open[-1]少0个点，不操作，除非保持一分钟不动，平仓
                    if current_a1_p - list_long_open[-1]==0:
                        order_target(g.code,LimitOrderStyle(list_long_open[-1]-0),0)
        
        
                    #如果a1_p价格比list_long_open[-1]少1个点，止盈
                    if current_a1_p - g.list_long_open[-1]==-1:
                        order_target(g.code,LimitOrderStyle(list_long_open[-1]-1),0)

def after_market_open(context):
    unsubscribe_all()
