# Clone from JoinQuant
# postId: 6b83a761968fcca4da7a9567030a661a
# backtestId: 778e812c094a3c6414d3aaaad7bee2c8
# title: 因子分析结果与实际回测差异

from jqfactor import Factor, calc_factors
import jqdata
def initialize(context):
    set_option('use_real_price',True)
    set_benchmark('000001.XSHG')
    run_daily(func,'every_bar')
    g.hold=10
   
class minclose(Factor):
    name='min_factor'
    max_window=1
    dependencies=['eps']
    def calc(self,data):
        min_factor=data['eps']
        return min_factor.mean()
        
def before_trading_start(context):
    indexs = get_index_stocks('000300.XSHG')
    factors = calc_factors(indexs, [minclose()], start_date=context.previous_date, end_date=context.previous_date)
    df=factors['min_factor'].T
    df.columns=['eps']
    df=df.sort(columns=['eps'],ascending=False)
    df=df[df['eps']>=0]
    g.stock_buy=df.index[:g.hold]
    

def func(context):
    
    minute=context.current_dt.minute
    hour=context.current_dt.hour
    
    if hour==14 and minute==55:
        keys=context.portfolio.positions.keys()
        buy_list=set(g.stock_buy)-set(keys)
        sell_list=set(keys)-set(g.stock_buy)
        
        for stock in sell_list:
            order_target(stock,0)
        for stock in buy_list:
            try:
                cash=context.portfolio.available_cash/len(buy_list) 
            except:
                cash=0 
            order_target_value(stock,cash) 
       
  
 
    