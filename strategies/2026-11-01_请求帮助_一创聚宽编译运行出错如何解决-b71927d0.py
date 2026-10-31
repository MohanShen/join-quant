# Clone from JoinQuant
# postId: b71927d041ae8873e09c919177efb757
# backtestId: b8fb8c6ca857c6345f3072c719a769b8
# title: 请求帮助：一创聚宽编译运行出错如何解决

# 克隆自聚宽文章：https://www.joinquant.com/post/31971
# 标题：价投与小市值两不误！7年年化43.59% 回撤27.96%
# 作者：皮皮量化

# 克隆自聚宽文章： 
# 标题：7年年化 41.73% 最大回撤22.29%
# 作者：回测时间长一点

# 克隆自聚宽文章：https://www.joinquant.com/post/15002
# 标题：价值选股与RSRS择时
# 作者：K线放荡不羁

'''
策略思路：
选股：财务指标选股
择时：RSRS择时
持仓：有开仓信号时持有10只股票，不满足时保持空仓

'''
from jqdata import *
from kuanke.wizard import *
import statsmodels.api as sm
import pandas as pd
import numpy as np

# 导入函数库
import statsmodels.api as sm
# import sklearn.linear_model as ols

# 初始化函数，设定基准等等
def initialize(context):
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    g.stockIndex = '000300.XSHG'
    # 股票池
    g.security_universe_index = "399101.XSHE"  # 中小板
    g.buy_stock_count = 5
    g.kpi = "roe"
    
    g.large_cap_percent = 0.5 # 大盘股仓位
    g.small_cap_percent = 0.5 # 小盘股仓位
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    set_parameter(context)
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='14:50', reference_security='000300.XSHG')
      # 收盘后运行
    #run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
'''
==============================参数设置部分================================
'''
def set_parameter(context):
    # 设置RSRS指标中N, M的值
    #统计周期
    g.N = 18
    #统计样本长度
    g.M = 600
    #首次运行判断
    g.init = True
    #持仓股票数
    g.stock_num = 10
    #风险参考基准
    g.security = '000300.XSHG'
    # 设定策略运行基准
    set_benchmark(g.security)
    #记录策略运行天数
    g.days = 0
    #set_benchmark(g.stock)
    # 买入阈值
    g.buy = -0.1
    g.sell = -0.7
    #用于记录回归后的beta值，即斜率
    g.ans = []
    #用于计算被决定系数加权修正后的贝塔值
    g.ans_rightdev= []
    
    # 每次每只股票总资金允许的损失比率（该值建议设置0.05~0.1）
    g.risk_ratio = 0.1     
    # set ATR 周期
    g.ATR_timeperiod = 14   
    
    # 计算2005年1月5日至回测开始日期的RSRS斜率指标
    prices = get_price(g.security, '2005-01-05', context.previous_date, '1d', ['high', 'low'])
    highs = prices.high
    lows = prices.low
    g.ans = []
    for i in range(len(highs))[g.N:]:
        data_high = highs.iloc[i-g.N+1:i+1]
        data_low = lows.iloc[i-g.N+1:i+1]
        X = sm.add_constant(data_low)
        model = sm.OLS(data_high,X)
        results = model.fit()
        g.ans.append(results.params[1])
        #计算r2
        g.ans_rightdev.append(results.rsquared)
    
## 开盘前运行函数     
def before_market_open(context):
    # 输出运行时间
    #log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    g.days += 1
    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    send_message('策略正常，运行第%s天~'%g.days)

## 开盘时运行函数
def market_open(context):
    security = g.security
    # 填入各个日期的RSRS斜率值
    beta=0
    r2=0
    if g.init:
        g.init = False
    else:
        #RSRS斜率指标定义
        prices = attribute_history(security, g.N, '1d', ['high', 'low'])
        highs = prices.high
        lows = prices.low
        X = sm.add_constant(lows)
        model = sm.OLS(highs, X)
        beta = model.fit().params[1]
        g.ans.append(beta)
        #计算r2
        r2=model.fit().rsquared
        g.ans_rightdev.append(r2)
    
    # 计算标准化的RSRS指标
    # 计算均值序列    
    section = g.ans[-g.M:]
    # 计算均值序列
    mu = np.mean(section)
    # 计算标准化RSRS指标序列
    sigma = np.std(section)
    zscore = (section[-1]-mu)/sigma  
    #计算右偏RSRS标准分
    zscore_rightdev= zscore*beta*r2
    log.info("zscore_rightdev%s"%zscore_rightdev)
    # 如果上一时间点的RSRS斜率大于买入阈值, 则全仓买入
    if zscore_rightdev > g.buy:
        # 记录这次买入
        log.info("市场风险在合理范围")
        #满足条件运行交易
        trade_func(context)
    # 如果上一时间点的RSRS斜率小于卖出阈值, 则空仓卖出
    elif (zscore_rightdev < g.sell) and (len(context.portfolio.positions.keys()) > 0):
        # 记录这次卖出
        log.info("市场风险过大，保持空仓状态")
        # 卖出所有股票,使这只股票的最终持有量为0
        for s in context.portfolio.positions.keys():
            order_target(s, 0)
            
#策略选股买卖部分    
def trade_func(context):
    #获取股票池
    today = context.current_dt
    date1 = today - datetime.timedelta(days=120* 1)
    date2 = today - datetime.timedelta(days=120* 2)
    date3 = today - datetime.timedelta(days=120* 3)
    date4 = today - datetime.timedelta(days=120* 4)
    date5 = today - datetime.timedelta(days=120* 5)
    date6 = today - datetime.timedelta(days=120* 6)
    date7 = today - datetime.timedelta(days=120* 7)
    date8 = today - datetime.timedelta(days=120* 8)
    date9 = today - datetime.timedelta(days=120* 9)
    date10 = today - datetime.timedelta(days=120* 10)
    date11 = today - datetime.timedelta(days=120* 11)
    date12 = today - datetime.timedelta(days=120* 12)
    date13 = today - datetime.timedelta(days=120* 13)
    date14 = today - datetime.timedelta(days=120* 14)
    date15 = today - datetime.timedelta(days=120* 15)
    # date16 = today - datetime.timedelta(days=120* 16)
    # date17 = today - datetime.timedelta(days=120* 17)
    # date18 = today - datetime.timedelta(days=120* 18)
    # date19 = today - datetime.timedelta(days=120* 19)
    dateList = [today,date1,date2,date3,date4,date5,date6,date7,date8,date9,date10,date11,date12,date13,date14,date15]
   
    
    All = get_index_stocks(g.stockIndex,	today)
    stocksBank = get_index_stocks('399986.XSHE',today)
    innercode = jy.run_query(query(jy.SecuMain.InnerCode).filter(jy.SecuMain.SecuCode == '931265'))['InnerCode']
    mqList = jy.run_query(query( jy.LC_IndexComponent.SecuInnerCode).filter(jy.LC_IndexComponent.IndexInnerCode.in_(innercode)))
    mqList = jy.run_query(query(jy.SecuMain.SecuCode).filter(jy.SecuMain.InnerCode.in_(mqList['SecuInnerCode'])))
    def getCode(secID):
        code = normalize_code(secID)
        return code


    mqList = mqList['SecuCode'].apply(getCode)
    # print("mqList%s"%mqList)
    stocksAll0 = list(set(All).difference(set(stocksBank))) # 排除银行股
    stocksAll = list(set(stocksAll0).intersection(set(mqList))) 
  
    # print(len(stocksAll))
    query_object = query(indicator.code,indicator.roe).filter(
            indicator.code.in_(stocksAll)
            )
    # 要操作的股票：平安银行（g.为全局变量）
    res = [get_fundamentals(query_object, date=date, statDate=None) for date in dateList]
    del today,date1,date2,date3,date4,date5,date6,date7,date8,date9,date10,date11,date12,date13,date14,date15
    import pandas as pd
    dataAll  = pd.concat(res)
    dataMean = dataAll.groupby(["code"]).mean()
    dataMeanMax = dataMean[g.kpi].max()
    dataMeanMin = dataMean[g.kpi].min()
    dataMeanNorm =2* (dataMean-(dataMeanMax+dataMeanMin)*0.5) / (dataMeanMax - dataMeanMin)
   
    # dataMeanSort =  dataMean.sort_values(by = [ g.kpi],ascending = False,na_position='last').head(30)
    # print("dataMeanNorm%s"%dataMeanNorm)
    dataStd  =   dataAll.groupby(["code"]).std()
    dataStdMax = dataStd[g.kpi].max()
    dataStdMin = dataStd[g.kpi].min()
    dataStdNorm  = (dataStd-dataStdMin)/ (dataStdMax - dataStdMin)
    # dataVar = dataAll.groupby(["code"]).var().sort_values(by = [ g.kpi],ascending = True,na_position='last').head(30)
    # print("dataStdNorm%s"%dataStdNorm)
    # dataSum = dataMeanNorm * dataMeanNorm * dataMeanNorm* 1000  - dataStdNorm
    
    # dataVar  =   dataAll.groupby(["code"]).var()
    # dataVarMax = dataVar[g.kpi].max()
    # dataVarMin = dataVar[g.kpi].min()
    # dataVarNorm = (dataVar-dataVarMin)/ (dataVarMax - dataVarMin)
    # # dataVar = dataAll.groupby(["code"]).var().sort_values(by = [ g.kpi],ascending = True,na_position='last').head(30)
    # print("dataVarNorm%s"%dataVarNorm)
    # dataSum =  dataMeanNorm - dataVarNorm 
    dataTobuy1 = dataMeanNorm.sort(columns = [g.kpi],ascending = False,na_position='last').head(45)
    dataTobuy2 = dataStdNorm.sort(columns = [g.kpi],ascending = True,na_position='last').head(10)
    dataTobuy = list(set(dataTobuy1.index).intersection(set(dataTobuy2.index)))

    del dataMeanNorm,dataMean,dataAll,dataTobuy1,dataTobuy2
    small_cap_pool = dataTobuy # 小盘股列表
    log.info(small_cap_pool)
    # g.security = dataTobuy
    #得到每只股票应该分配的资金
    # security = g.security
    large_cap_pool = my_trade(context) # 大盘股列表
    log.info(large_cap_pool)
     
    small_cap_total_value = 0 
    large_cap_total_value = 0
    # 分配资金
    if len(large_cap_pool) > 0 and len(small_cap_pool) > 0 :
        small_cap_total_value = context.portfolio.total_value * g.small_cap_percent
        large_cap_total_value = context.portfolio.total_value * g.large_cap_percent
    elif len(large_cap_pool) == 0 and len(small_cap_pool) > 0:
        small_cap_total_value = context.portfolio.total_value
    
    #获取已经持仓列表
    hold_stock = context.portfolio.positions.keys()     
    #卖出不在持仓中的股票
    for s in hold_stock:
        if (s not in small_cap_pool) and (s not in large_cap_pool):
            order_target(s,0)
    
    # 买入小盘股股票
    open_position_pool(small_cap_pool, small_cap_total_value)
    
    # 买入大盘股股票
    open_position_pool(large_cap_pool, large_cap_total_value)

# 买入股票列表
def open_position_pool(pool, total_value):
    if len(pool) > 0 and total_value > 0:
        cash = total_value / len(pool)
        for s in pool:
            order_target_value(s, cash)

## 开盘时运行函数
def my_trade(context):
    # 选取中小板中市值最小的若干只
    check_out_lists = get_index_stocks(g.security_universe_index)
    q = query(valuation.code).filter(
    valuation.code.in_(check_out_lists),
        # valuation.pe_ratio > 0,
#    not valuation.code.startswith('300')
    ).order_by(
        valuation.circulating_market_cap.asc()
    ).limit(
        g.buy_stock_count * 3
    )
    check_out_lists = list(get_fundamentals(q).code)
    # 过滤: 创业板、三停（停牌、涨停、跌停）及st,*st,退市
    check_out_lists = filter_gem_stock(context, check_out_lists)
    check_out_lists = filter_st_stock(check_out_lists)
    check_out_lists = filter_limitup_stock(context, check_out_lists)
    check_out_lists = filter_limitdown_stock(context, check_out_lists)
    check_out_lists = filter_paused_stock(check_out_lists)
    # 取需要的只数
    check_out_lists = check_out_lists[:g.buy_stock_count]
    return check_out_lists
    # 买卖
    # adjust_position(context, check_out_lists)

# 交易
def adjust_position(context, buy_stocks):
    for stock in context.portfolio.positions:
        if stock not in buy_stocks:
            log.info("stock [%s] in position is not buyable" % (stock))
            position = context.portfolio.positions[stock]
            close_position(position)
        else:
            log.info("stock [%s] is already in position" % (stock))
    
    # 根据股票数量分仓
    # 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配
    position_count = len(context.portfolio.positions)
    if g.buy_stock_count > position_count:
        value = context.portfolio.cash / (g.buy_stock_count - position_count)
        
        for stock in buy_stocks:
            if context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value):
                    if len(context.portfolio.positions) == g.buy_stock_count:
                        break

# 开仓，买入指定价值的证券
# 报单成功并成交（包括全部成交或部分成交，此时成交量大于0），返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），返回False
def open_position(security, value):
    # order =order_target_value(security, value)
    order = order_value(security, value)
    if order != None and order.filled > 0:
        return True
    return False
    
# 自定义下单
# 根据Joinquant文档，当前报单函数都是阻塞执行，报单函数（如order_target_value）返回即表示报单完成
# 报单成功返回报单（不代表一定会成交），否则返回None
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    
    # 如果股票停牌，创建报单会失败，order_target_value 返回None
    # 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
    # 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
    return order_target_value(security, value)



# 平仓，卖出指定持仓
# 平仓成功并全部成交，返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），或者报单非全部成交，返回False
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    
    return False

#打分工具
def f_sum(x):
    return sum(x)

# 过滤创业板股票
def filter_gem_stock(context, stock_list):
    return [stock for stock in stock_list if stock[0:3] != '300']

# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


# 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


# 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    # 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


# return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
#    or last_prices[stock][-1] < current_data[stock].high_limit * 0.995]

# 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]
    
   
## 收盘后运行函数  
def after_market_close(context):
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    #打印账户总资产
    log.info('今日账户总资产：%s'%round(context.portfolio.total_value,2))
    #log.info('##############################################################')
