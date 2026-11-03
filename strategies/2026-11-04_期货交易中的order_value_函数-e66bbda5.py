# Clone from JoinQuant
# postId: e66bbda5af95932fb4a453659b651ba4
# backtestId: 5755ad43f339dbc3c5b61047fe3949ed
# title: 期货交易中的order_value()函数

# 克隆自聚宽文章：https://www.joinquant.com/post/15477
# 标题：【策略研发】期货双均线策略
# 作者：东南有大树

# 导入函数库
from jqdata import *

## 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('RB2110.XSGE')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # 输出内容到日志 log.info()
    log.info('策略开始运行，祝君愉快！')

    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 设置期货交易的滑点
    set_slippage(FixedSlippage(0.2))
    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF1512.CCFX'或'IH1602.CCFX'是一样的）
    # 开盘前运行
    run_daily( before_market_open, time='before_open', reference_security='IF1512.CCFX')
    # 开盘时运行
    run_daily( market_open, time='open', reference_security='IF1512.CCFX')
    # 收盘前运行
    run_daily( before_market_close, time='14:45', reference_security='IF1512.CCFX')
    # 收盘后运行
    run_daily( after_market_close, time='after_close', reference_security='IF1512.CCFX')
    
    # 期货代码 
    g.future_code=''
    # 当日可买入代码
    g.buy_code = []
    # 当日可卖出代码
    g.sell_code = []
    # 短均线
    g.ma_short = 5
    # 长均线
    g.ma_long = 10


## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    
    # 清空代码列表 
    g.buy_code = []
    g.sell_code = []
    
    # 获取RB合约对应的期货代码
    g.future_code = 'RB2110.XSGE'
    log.info('RB对应期货为',g.future_code)
    
    # 获取期货对应的历史价格
    price = get_price(security=g.future_code, 
              end_date=context.previous_date, 
              frequency='daily', 
              fields=['close'], 
              skip_paused=False, 
              fq='pre', 
              count=100)
    
    # 求出上一个交易日的m5均线值与ma60值
    last_ma5 = price.iloc[-g.ma_short:]['close'].mean()
    last_ma60 = price.iloc[-g.ma_long:]['close'].mean()
    # 求出三个交易日之前的ma5与ma60值
    old_ma5 = price.iloc[-g.ma_short-1:-1]['close'].mean()
    old_ma60 = price.iloc[-g.ma_long-1:-1]['close'].mean()
    
    # 判断ma5与ma60的交叉情况
    last_value = (last_ma5-last_ma60) / last_ma60
    old_value = (old_ma5-old_ma60) / old_ma60
    
    # 在回测中画出ma5与ma60的交叉情况
    record(ma5=last_ma5)
    record(ma60=last_ma60)
    
    if (old_ma5-old_ma60) <= 0 and (last_ma5-last_ma60) > 0: # 判断是否出现金叉
        log.info('出现金叉，请注意')
        log.info('ma5大于m60百分点{0}%'.format(round(last_value*100,2)))
        
        # if last_value >= 0.01:
        g.buy_code.append(g.future_code)
        log.info('金叉条件，可买入的标的',g.buy_code)
    elif (old_ma5-old_ma60) >= 0 and (last_ma5-last_ma60) < 0: # 判断是否出现死叉
        log.info('出现死叉，请注意')
        log.info('ma5小于m60百分点{0}%'.format(round(last_value*100,2)))
        
        # if last_value <= -0.01:
        g.sell_code.append(g.future_code)
        log.info('死叉条件，可卖入的标的',g.buy_code)
    else:
        log.info('均线未发生情况',last_value,old_value)
        

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    # 获得当前资金的一半
    cash = context.portfolio.total_value*0.15
    # 对可买入的标的进行下单，这里使用资金的一半交易，可自行调整
    for code in g.buy_code:
        order_target_value(code, cash , side='long', pindex=0)
        log.info('做多',code)
    
def before_market_close(context):
    log.info('函数运行时间(before_market_close):'+str(context.current_dt.time()))
    # 对可卖出的标的进行操作，在这里可以调整是做空、平仓、移仓等操作
    for code in g.sell_code:
        if code not in context.portfolio.positions.keys():  # 不在持仓范围的不交易
            continue
        order_target(code, 0, side='long', pindex=0)
        log.info('平仓',code)


## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')

