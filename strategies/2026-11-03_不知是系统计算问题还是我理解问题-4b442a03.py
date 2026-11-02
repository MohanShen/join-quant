# Clone from JoinQuant
# postId: 4b442a03e086afae36a50436b07cf46d
# backtestId: 0fc72c91b7ae5de996b4d8ed4fbfbbf3
# title: 不知是系统计算问题还是我理解问题？

def initialize(context):
    run_daily(period, time='every_bar')
    g.security='000001.XSHE'

def period(context):
    order(g.security, 100)
