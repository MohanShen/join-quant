# Clone from JoinQuant
# postId: a1560e04d7263583797c7ed0f41edcd8
# backtestId: cb13e859965b73032e1af7bddbcb55ed
# title: 发现平台API的bug?还是？

# 导入函数库
import jqdata
from jqlib.technical_analysis import *
# 初始化函数，设定基准等等
def initialize(context):
    g.security='000001.XSHE'
    
def handle_data(context, data):
    now=context.current_dt
    now=datetime.date(now.year,now.month,now.day)
    dif,dea,macd=MACD(g.security,now,SHORT = 12, LONG = 26, MID = 9)
    record(diff=dif[g.security])
    record(dea=dea[g.security])   
    record(macd=macd[g.security])