# Clone from JoinQuant
# postId: 46524c381c909fcf899d9ec9cdcb4b3e
# backtestId: d5901eaf5e1ef29bfd2233799903acb5
# title: get_current_data在morning的使用问题

enable_profile()

import pandas as pd

def initialize(context):
    g.days=0 # 已持仓天数
    g.cycle=20 # 调仓周期
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.00025,
            close_commission=0.00025,
            close_today_commission=0,
            min_commission=5),
        type='stock'
    )
    set_benchmark('000300.XSHG') # 基准沪深300
    set_option('use_real_price',True) # 使用真实价格
    set_slippage(FixedSlippage(0)) # 无滑点
    run_daily(morning,'morning')
    
def morning(context):
    g.days=g.days+1
    print 'Day {}'.format(g.days)
    if(g.days>1):
        return
    
    today=context.current_dt
    stocks=list(get_all_securities(['stock'],date=today).index)
    print 'Total stocks number of ({}): {}'.format(today,len(stocks))
    
    current_data=get_current_data()
    stocks=[s for s in stocks if not current_data[s].paused and not current_data[s].is_st]
    print 'Total unpaused non-ST stocks number: {}'.format(len(stocks))
    send_message('Pool size: {}'.format(len(stocks)), channel='weixin')
    
def handle_data(context,data):
    if g.days==g.cycle:
        g.days=0