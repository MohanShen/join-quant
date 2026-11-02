# Clone from JoinQuant
# postId: ed503d5e7466b6720e57a2da21e991c4
# backtestId: 0d5cb146469f8ed0b6d01b3d75cc3be2
# title: 成交量的回测数据有错误？！？！[已解答]

import pandas as pd
# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '300046.XSHE'
    #设定沪深300作为基准
    set_benchmark('000300.XSHG')

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    h_data = attribute_history(security, 2, '1d', 'volume')
    log.info ("[%s(%s)] 成交量数据如下：\n" %(get_security_info(security).display_name,security))
    log.info (h_data)