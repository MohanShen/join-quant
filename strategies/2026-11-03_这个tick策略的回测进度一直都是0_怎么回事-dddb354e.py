# Clone from JoinQuant
# postId: dddb354e642c922d5ecec578c10c19b4
# backtestId: ec22b9a2369aa6979376ddcfbe9b5166
# title: 这个tick策略的回测进度一直都是0%，怎么回事？

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
    tick_data=get_ticks(g.code1,start_dt='2019-10-28 09:00:00',end_dt='2019-10-29 15:30:00',fields=['time','current','a1_v','a1_p','b1_v','b1_p'],skip=False)
    
    current_a1_v=tick_data['a1_v'][-1]
    current_a1_p=tick_data['a1_p'][-1]
    current_b1_v=tick_data['b1_v'][-1]
    current_b1_p=tick_data['b1_p'][-1]
    
    current_price=tick_data['current'][-1]

    if current_a1_v < current_b1_v and current_price==current_b1_p:
        order(security,5,style=None,side='long',pindex=0)
        print('开多五手豆粕2001合约')
        if current_price==current_a1_p or current_price<current_b1_p:
            order_target(security,0,style=None,side='long',pindex=0)
            print('卖出五手豆粕2001合约')
            
    elif current_b1_v<current_a1_v and current_price==current_a1_p:
        order(security,5,style=None,side='short',pindex=0)
        print('开空五手豆粕2001合约')
        if current_price==current_b1_p or current_price>current_a1_p:
            order_target(security,0,style=None,side='short',pindex=0)
            print('卖空五手豆粕2001合约')
            
def after_market_open(context):
    unsubscribe_all()
            