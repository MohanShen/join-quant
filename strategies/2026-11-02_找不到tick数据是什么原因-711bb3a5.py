# Clone from JoinQuant
# postId: 711bb3a5d29ddbe0d0c4d3f71ce4b6ae
# backtestId: bfb3e684c5c25b2a2ebf964938014343
# title: 找不到tick数据是什么原因

#tick抓涨停 B1.0    2018-11-11
import jqdata
import json             #一种将数据保存成特殊格式形式的模块
import os,shutil        #用于寻找文件路径、复制文件等操作的模块


def initialize(context):
    set_benchmark('000300.XSHG')        #设置基准指数
    set_option('use_real_price', True)      #设置回测为真实价格
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')         #设置部分交易参数

def before_trading_start(context):      
    subscribe('000001.XSHE','tick')     #订阅一只股票（是运行该tick程序的必要条件）
    g.stockin = []      #用于存储每个tick时刻达到买入条件的股票
    g.temp = []     #用于读取备选股票文件"test1"中的数据，并保存于此

def handle_tick(context, tick):
    
    tSecond = context.current_dt.second     #确定当前的秒数
    
    g.ZongJie = '\n'        #用于发布需要买入操作的股票
    g.JieZong = '\n'        #用于发布需要撤销买入操作的股票
    
    new = get_current_data()    #获取所有股票的当前信息
    
    #当秒数为"3"时，读取test1的备选股票列表数据，并保存于g.temp中
    if tSecond == 3:
        g.temp = json.loads(read_file('test1.json'))

    for i in g.temp:
        stk = get_current_tick(i)       #获取该股票的tick数据
        #判断是否为空，空的话就不进行操作
        if stk is not None:
            #...判断是否满足条件
            if stk.b1_p*stk.b1_v > 500:
                DisName = new[i].name       #获取当前股票的名称
                g.ZongJie = (g.ZongJie + i + "," + DisName + '\n')      #记录日记
                g.stockin.append(i)     #将股票代码加入stockin
    #如果需要通知的股票数不是0，则记录日志
    if g.ZongJie != '\n':
        #log.info('----------------------------------------------------------')
        log.info(g.ZongJie+'以上为要买入的股票+++++')     #记录日志
        #log.info('----------------------------------------------------------')
