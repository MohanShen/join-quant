# Clone from JoinQuant
# postId: 8d39ca441805993c9b765dedffb08356
# backtestId: f4c69c3f5ef8ebe7e127466361d26b04
# title: 请问，复刻上涨突破5日均价1%策略，但收益率为0，错在哪里？

import jqdata


def initalize(context):
    g.security='600570.XSHG (HSDZ)'
    set_option('use_real_price',True)
    set_benchmark('000300.XSHG (HS300)')
    run_daily(market_open,time='every_bar')
    
def market_open(context):
    security=g.security
    cash=context.portfolio.availabie_cash
    
    close_data=attribute.history(security,count=5,unit='1d',fields=['close'])
    MA5=close_data['close'].mean()
    current_price=close_data['close'][-1]
    
    if  current_price>MA5*1.01:
        order_value(security,cash)
        
    elif current_price<MA5 and context.portfolio.positions[security].closeable_amount>0:
        order_target(security,0)
        

