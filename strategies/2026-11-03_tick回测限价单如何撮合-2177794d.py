# Clone from JoinQuant
# postId: 2177794db35d6e60e3f3e2de4152b436
# backtestId: a6aed37a396494ad8f552f1e2575a0b0
# title: tick回测限价单如何撮合？

# 导入函数库
import jqdata
enable_profile()
# 初始化函数，设定基准等等
def initialize(context):
    # 设定基准
    
    subscribe(['300033.XSHE','000002.XSHE'],'tick')


def handle_tick(context,tick):
    now=tick.datetime   
    if now.hour==9 and now.minute==31 and now.second==12:
        #log.info(context.portfolio.positions['300033.SZ'])
        order('300033.XSHE',10000,LimitOrderStyle(48.6))