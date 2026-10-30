# Clone from JoinQuant
# postId: e903174f00a8b78a19e463f0a06db480
# backtestId: 0fc322f448ab374beadcbeb31f428bd9
# title: pytorch cnn_seq deep learning

 
#https://github.com/tomcat123a/-chanlun/blob/master/README.md
from jqdata import *
from jqlib.technical_analysis import *
import torch.nn as nn
import torch
# 初始化函数，设定基准等等
def initialize(context):
    # 设定指数
    class TheModelClass(nn.Module):
        def __init__(self):
            super(TheModelClass, self).__init__()
            self.conv1 = nn.Conv2d(5, 1,1)
            self.pool = nn.AdaptiveMaxPool2d(120, 4)
            self.conv2 = nn.Conv2d(5, 1, 1)
            self.fc1 = nn.Linear(120, 120)
            self.fc2 = nn.Linear(120, 84)
            self.fc3 = nn.Linear(84, 1)
    
        def forward(self, x):
            x = self.pool(F.relu(self.conv1(x)))
            x = self.pool(F.relu(self.conv2(x)))
            x = x.view(-1,250)
            x = F.relu(self.fc1(x))
            x = F.relu(self.fc2(x))
            x = self.fc3(x)
            return x

    model = TheModelClass()
    model.load_state_dict(torch.load('a.pt'))
    model=model.eval()
    g.stocknum = 5
        
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0005, close_commission=0.0005, min_commission=5), type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open')
      # 开盘时运行
    #run_daily(market_open, time='open')
    run_daily(market_open, time='09:31')
      # 收盘后运行
    run_daily(after_market_close, time='after_close')
    ### 进行交易

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('--------------盘前--------------')  
        # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    print("当前可用资金:{0}, 持有股票数量:{1}".format(context.portfolio.available_cash, len(context.portfolio.positions)))
   
## 开盘时运行函数
def market_open(context): 
    log.info('--------------盘中--------------')     
    trade(context)

## 收盘后运行函数
def after_market_close(context):
    log.info('--------------盘后--------------')   
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
    
def trade(context): 
	## 卖出
    if len(context.portfolio.positions) > 0:
        for stock in context.portfolio.positions.keys():
            if stock_has_short_signal(context, stock):
                order_target(stock, 0)
    
    vacation = g.stocknum - len(context.portfolio.positions)
    if vacation > 0:  
        ## 获得Buylist
        candidatelist = get_stocks_buy_candidates(context)
        if len(candidatelist) > 0: 
            ## 分配资金 
            Cash = context.portfolio.cash/vacation
             ## 买入 
            for stock in candidatelist:
                if (g.stocknum - len(context.portfolio.positions)) > 0 and stock not in context.portfolio.positions.keys():
                    order_value(stock,Cash) 
    
## 选股函数
def get_stocks_buy_candidates(context):
    # 设定查询条件
    q = query(valuation.code)
    df = get_fundamentals(q)
    securities =list(df['code'])
    # 去掉停牌股
    current_data = get_current_data()
    securities = [stock for stock in securities if not current_data[stock].paused]

    _list = []
    for security in securities:
        if stock_has_long_signal(context, security): 
            #print("股票达到做多点：{0}".format(security))
            _list.append(security)
    
    return sorted_stocks_list(context, _list)
	
## 选股函数
def stock_has_short_signal(context, security): 
    if isMACDDeath(context, security):
        return True
     
    return False
 
## 开盘时运行函数
def stock_has_long_signal(context, security):
    close_data = get_bars(security, count=200, unit='1d', fields=['close'])['close']
    if(len(close_data) < 200):
        return False

    if not (isMACDGold(context, security)):
        return False
    
    return True
        
def sorted_stocks_list(context, stock_list):
	# 记录涨幅的字典
    stock_dict = {}    
    for stock in stock_list:
        h = attribute_history(stock, 120, unit = '1d', fields = ('close'), skip_paused = True)
        rise = ((h.close)[-1] / (h.close)[0] - 1) * 100 
        if (rise > 0):
            stock_dict[stock] = rise
    
	# 根据涨幅进行排序
    sort_lists = sorted(stock_dict.items(), key=lambda e:e[1], reverse=True)
    target_list = [key for key,value in sort_lists]
    for key,value in sort_lists:
        #print("股票：[{0}] 涨幅：[{1}]".format(key, value))
        pass
    return target_list 

		# 定义MACD函数  
def isMACDGold(context,security):

     
    h = attribute_history(stock, 250, unit = '1d', fields = ('open','high','low','close'), skip_paused = True).T
    if g.model( torch.from_numpy(h).unsqueeze(0) ).detach().numpy()[0]>0.2:
         return True
    else:
        return False
def isMACDDeath(context,security):

    h = attribute_history(stock, 250, unit = '1d', fields = ('open','high','low','close'), skip_paused = True).T
    if g.model( torch.from_numpy(h).unsqueeze(0) ).detach().numpy()[0]<0:
         return True
    else:
        return False