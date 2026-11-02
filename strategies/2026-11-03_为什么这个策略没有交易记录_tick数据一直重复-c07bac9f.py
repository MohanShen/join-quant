# Clone from JoinQuant
# postId: c07bac9f64b5cbbc9a77c38ce7908d46
# backtestId: 8cdacc2c687b4e133a922aebb3a636ad
# title: 为什么这个策略没有交易记录？tick数据一直重复

# 导入函数库
from jqdata import *
import datetime

## 初始化函数，设定基准等等
def initialize(context):
    #设置交易期货代码#
    g.code1='M2001.XDCE'
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
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)
    
    run_daily(before_market_open,time='08:30',reference_security='M9999.XDCE')
    run_daily(after_market_open,time='15:30',reference_security='M9999.XDCE')
    
def before_market_open(context):
    subscribe(g.code1,'tick')
    
def handle_tick(context,tick):
    print('go')
    tick_data=get_ticks(g.code1,count=100,end_dt='2019-10-30 21:00:00',fields=['time','current','a1_v','a1_p','b1_v','b1_p'],skip=True)
    print(tick_data)
    
    current_a1_v=tick_data['a1_v'][-1]
    current_a1_p=tick_data['a1_p'][-1]
    current_b1_v=tick_data['b1_v'][-1]
    current_b1_p=tick_data['b1_p'][-1]
    
    current_price=tick_data['current'][-1]

    if abs(current_a1_p-current_b1_p)==2 and g.code1 not in context.portfolio.short_positions:
        order(g.code1,5,style=None,side='short',pindex=0)
        print('开空五手豆粕合约')
       
        if abs(current_a1_p-current_b1_p)==1 and g.code1 in context.portfolio.short_positions:
            order_target(g.code1,0,style=None,side='short',pindex=0)
            print('平五手豆粕空仓')
           
    
def after_market_open(context):
    unsubscribe_all()
