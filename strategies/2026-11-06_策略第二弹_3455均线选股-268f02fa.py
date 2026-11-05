# Clone from JoinQuant
# postId: 268f02fae9a0c8dec7d499eefc4fa386
# backtestId: 6c026a9ada49c2d501358058ed040970
# title: 策略第二弹：3455均线选股

#石奔的第二个策略
#初始化函数，设定基准
def initialize(context):
    #选取股票
    df=get_fundamentals(query(valuation.code))  #默认选择的是全市场的股票
    #选择df基本面表格中，列名为code的一列
    g.stocklist=list(df['code'])  #取全市场股票的列表
    #设定沪深300为基准
    set_benchmark('000300.XSHG')
    #开启动态复权模式
    set_option('use_real_price',True)
    #设置滑点
    set_slippage(FixedSlippage(0))
    #输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    #过滤掉order系列API产生的比error级别低的log
    log.set_level('order','error')
    g.top={} #记录top值
    #股票相关设定，如手续费，买入时佣金万分之三，卖出时万分之三加上千分之一印花税，每笔交易佣金最低5元
    set_order_cost(OrderCost(close_tax=0.0003,open_commission=0.001,close_commission=0.0007,min_commission=5),type='stock')
    #将滑点设置为千分之2
    set_slippage(FixedSlippage(0))
    
    #短期均线、长期均线、股票数量
    g.fast=34
    g.slow=55
    g.lag=13
    g.stocknum=20

def handle_data(context,data):
    g.stocklist=paused_filter(g.stocklist)  #过滤掉停盘、st、以及退市的股票
    g.stocklist=delisted_filter(g.stocklist)
    g.stocklist=st_filter(g.stocklist)
    buylist=[]
    closeby2=get_fundamentals(query(valuation.code,valuation.pe_ratio).filter(valuation.code.in_(g.stocklist),valuation.pe_ratio<50,valuation.pe_ratio>2).order_by(valuation.pe_ratio.asc()))
    g.stocklist=list(closeby2['code'])
    for stock in g.stocklist:
        closeby=attribute_history(stock,60,unit='1d',fields=['close'],skip_paused=True,fq='pre')
        pct_10=closeby['close'][-1]/closeby['close'][-10]-1  #10日内涨幅
        #今日均线，55日和34日
        ma_13_1=closeby['close'][-g.lag:].mean()
        ma_34_1=closeby['close'][-g.fast:].mean()
        ma_55_1=closeby['close'][-g.slow:].mean()
        #昨日均线，55日和34日
        ma_34_2=closeby['close'][-(g.fast+1):-1].mean()
        ma_55_2=closeby['close'][-(g.slow+1):-1].mean()
        if ma_34_1>ma_55_1 and ma_55_1>ma_55_2 and ma_34_2<=ma_55_2 and (pct_10>-0.10 and pct_10<0.1) and closeby['close'][-1]>1.02*ma_55_1:
            buylist.append(stock)
    #得到将要买入的股票池，数量限制在50个以内
    #当前可用资金        
    cash=context.portfolio.available_cash
    current_position=context.portfolio.positions.keys()
    for stock in buylist:
        if len(current_position)>=g.stocknum:
            break
        else:
            num=len(buylist)
            cash=cash/num
            order_target_value(stock,cash)
            log.info("买入%s"%stock)
    #对不满足条件的个股，止损离场
    for stock in context.portfolio.positions.keys():
        closeby3=attribute_history(stock,60,unit='1d',fields=['close'],skip_paused=True,fq='pre')
        #今日均线，13日和34日
        ma_13_1_1=closeby['close'][-g.lag:].mean()
        ma_34_1_1=closeby['close'][-g.fast:].mean()
        ma_55_1_1=closeby['close'][-g.slow:].mean()
        if ma_13_1_1<ma_34_1_1 or closeby['close'][-1]<=0.95*ma_55_1_1:
            order_target_value(stock,0)
            log.info("卖出%s"%stock)
# 过滤停牌、退市和ST股票
def paused_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].paused]
    return security_list


def delisted_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not '退' in current_data[stock].name]
    return security_list

def st_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].is_st]
    return security_list
   

    
