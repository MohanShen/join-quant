# Clone from JoinQuant
# postId: 2f984f605a383a2b8a261348c1d5c2c6
# backtestId: 1ee920e8b0f4bd0459e8b02852f6f8ee
# title: .ipynb都正常的转换成.py作为头文件策略里导入就出错了

from jqdata import *
import datetime
# 导入批数估值模块
#from untitled import *
from kuanke.user_space_api import *

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    g.security = '000001.XSHE'
    # 运行函数
    run_daily(market_open, time='every_bar')

def market_open(context):
    if g.security not in context.portfolio.positions:
        order(g.security, 1000)
    else:
        order(g.security, -800)
    