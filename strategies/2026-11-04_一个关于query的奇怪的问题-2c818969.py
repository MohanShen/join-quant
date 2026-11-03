# Clone from JoinQuant
# postId: 2c8189693329e254384907895bc6a073
# backtestId: 8468ec2a9fbda6f5c835dfb886a36e55
# title: 一个关于query的奇怪的问题

def initialize(context):
    run_daily(period,time='every_bar')
    g.security = '000001.XSHE'
    # 打印可用资金
    print(context.portfolio.available_cash)
    # 打印运行频率
    print(context.run_params.frequency)
    # 打印当前单位时间的开始时间
    print(context.current_dt)    
    #打印时间
 #   写一个策略，内容为在20180301买入一个股票，在20180321卖出一个股票。股票可以自己定。
def period(context):
    datetime=context.current_dt.strftime("%Y%m%d")
    if datetime=='20180301':
          order('000001.XSHE',100)
    if datetime=='20180321':
          order('000001.XSHE',0)
