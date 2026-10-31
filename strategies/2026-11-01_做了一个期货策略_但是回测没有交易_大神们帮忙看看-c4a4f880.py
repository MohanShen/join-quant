# Clone from JoinQuant
# postId: c4a4f8806351b884dc5c25cf8d7c9589
# backtestId: 2ad9c5d0ce8cbe8f27e460d221c57f5d
# title: 做了一个期货策略，但是回测没有交易，大神们帮忙看看

# 导入函数库
import jqdata
import os
    
def initialize(context):
    # 设定大豆油期货作为基准标的
    set_benchmark('OI9999.XZCE')
    
    Trade.price=0
    set_option('use_real_price', True)

    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)
    log.set_level('order', 'error')
    
    run_daily(market_open, time='open', reference_security = 'OI9999.XZCE')
def market_open(context):
    lever1=attribute_history('OI9999.XZCE', 2, '1d', ['low'])
    lever=lever1['low'].min()
    liver1=attribute_history('OI9999.XZCE', 2, '1d', ['high'])
    liver=liver1['high'].max()
    p1=attribute_history('OI9999.XZCE', 5, '1m', ['close'])
    p=p1['close'][-1]
    zsd0=0
    zsdy=0
    zsds=0
    zsk=0
    zsks=0
    zsky=0
    if p<lever:
        order('OI9999.XZCE',10,side='long',pindex=0)
        zsd=Trade.price
        zsdy=zsd+50
        zsds=zsd-10
    elif p>liver:
        order('OI9999.XZCE', 10, side = 'short', pindex = 0)
        zsk=Trade.price
        zsky=zsk-50
        zsks=zsk+10
    #如果该指数比较平稳，那么平仓，赚取之前策略的收益
    elif p>zsks and p>zsdy:
        order_target('OI9999.XZCE', 0)
    elif p<zsky and p>zsds:
        order_target('OI9999.XZCE', 0)
        
    
   