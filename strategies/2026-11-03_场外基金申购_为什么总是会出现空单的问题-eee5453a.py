# Clone from JoinQuant
# postId: eee5453a5a3684309bc3af31468a6b38
# backtestId: b0b840f67dfb8fec3cda20c2031477e1
# title: 场外基金申购，为什么总是会出现空单的问题

# 克隆自聚宽文章：https://www.joinquant.com/post/21004
# 标题：场外基金定投
# 作者：怡情

def initialize(context):
    set_option('use_real_price', True)
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'open_fund')])
    run_daily(market_open, time='10:30', reference_security='000300.XSHG')
    
    g.days = 0
    g.hold_day = 40
    
def market_open(context):
    available_cash = context.portfolio.available_cash
    week = context.current_dt.isoweekday()
    
    if week == 2:
        if g.days % g.hold_day == 0:
            for position in list(context.subportfolios[0].long_positions.values()):
                redeem(position.security, position.closeable_amount)
    else:
        if available_cash > 10:
            if week == 1:
                purchase('002190.OF', available_cash/4)
            elif week == 3:
                purchase('001487.OF', available_cash/4)
            elif week == 4:
                purchase('000689.OF', available_cash/4)
                purchase('003567.OF', available_cash/4)
                
    g.days += 1
    log.info('='*50)


        
    
    
    
