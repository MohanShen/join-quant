# Clone from JoinQuant
# postId: 9ca7f4936e068afaa01be14d7a52d14f
# backtestId: 0916e428e1c218225c2b4cb3f5bd157f
# title: 基于RSRS策略的改进年化20%

'''
策略思路：
选股：财务指标选股
择时：RSRS择时
持仓：有开仓信号时持有每个行业 eps 预期涨幅最高的企业

'''
# 导入函数库
from jqdata import *
import statsmodels.api as sm
from pandas.stats.api import ols

# 初始化函数，设定基准等等
def initialize(context):
    
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
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    set_parameter(context)
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时运行
    run_daily(market_open, time='14:40', reference_security='000300.XSHG')
      # 收盘后运行
    #run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
'''
==============================参数设置部分================================
'''
def set_parameter(context):
    # 设置RSRS指标中N, M的值
    #统计周期
    g.N = 20
    #统计样本长度
    g.M = 1100
    #首次运行判断
    g.init = True
    #持仓股票数
    g.stock_num = 20
    #风险参考基准
    g.security = '000300.XSHG'
    # 设定策略运行基准
    set_benchmark(g.security)
    #记录策略运行天数
    g.days = 0
    #set_benchmark(g.stock)
    # 买入阈值
    g.buy = 0.6
    g.sell = -0.8
    #用于记录回归后的beta值，即斜率
    g.ans = []
    #用于计算被决定系数加权修正后的贝塔值
    g.ans_rightdev= []
    
    # 计算2005年1月5日至回测开始日期的RSRS斜率指标
    prices = get_price(g.security, '2005-01-05', context.previous_date, '1d', ['high', 'low'])
    highs = prices.high
    lows = prices.low
    g.ans = []
    #log.info('RSRS斜率指标'+str(prices))
    #log.info('RSRS斜率指标g.N：'+str(g.N))
    for i in range(len(highs))[g.N:]:
        data_high = highs.iloc[i-g.N+1:i+1]
        data_low = lows.iloc[i-g.N+1:i+1]
        X = sm.add_constant(data_low)
        model = sm.OLS(data_high,X)
        results = model.fit()
        g.ans.append(results.params[1])
        #计算r2
        g.ans_rightdev.append(results.rsquared)
        #log.info('计算过程data_high：'+str(data_high))
        #log.info('计算过程data_low：'+str(data_low))
        #log.info('计算过程X：'+str(X))
        #log.info('计算过程model：'+str(results.params[1]))
        #log.info('计算过程results：'+str(results.rsquared))
    
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
        #prices = attribute_history(security, g.N, '1d', ['high', 'low'])
        #prices = pd.DataFrame(columns=['high', 'low'])
        current_datas = get_bars(security, g.N, unit='1d',fields= ['high', 'low'],include_now=True, end_dt=None, fq_ref_date=None)
        # columns
        columns_new = ['high', 'low']
        
        # pass in array and columns
        prices = pd.DataFrame(current_datas, columns=columns_new)
        #log.info(str(prices))
        
        highs = prices.high
        lows = prices.low
        X = sm.add_constant(lows)
        model = sm.OLS(highs, X)
        beta = model.fit().params[1]
        g.ans.append(beta)
        #计算r2
        r2=model.fit().rsquared
        g.ans_rightdev.append(r2)
    
    #log.info('全局对象N：'+str(g.N))
    #log.info('全局对象ans：'+str(g.ans))
    #log.info('全局对象ans_rightdev：'+str(g.ans_rightdev))
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
    
    #log.error("市场风险:"+str(zscore_rightdev))
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
    
    stock_lst = get_my_industry_stocks(context)
    
    #log.info('股票：'+ str(stock_lst))
    #得到每只股票应该分配的资金
    cash = context.portfolio.total_value
    if len(stock_lst) > 0:
        cash = context.portfolio.total_value/len(stock_lst)
    
    #获取已经持仓列表
    hold_stock = context.portfolio.positions.keys() 
    #卖出不在持仓中的股票
    for s in hold_stock:
        if s not in stock_lst:
            order_target(s,0)
    #买入股票
    for s in stock_lst:
        if s not in hold_stock:
            order_target_value(s,cash)
#打分工具
def f_sum(x):
    return sum(x)
        
def get_my_industry_stocks(context):
    stock_lst = []
    df = get_industries(name='zjw')
    
    for industry in df.itertuples():
        #stock_lst = stock_lst.append(get_industries_min_rate_stock(industry[0],context))
        industry_code = industry[0]
        # 过滤公共事业及农业股
        if industry_code.find('A') == 0 or industry_code.find('E48') == 0 or industry_code.find('O') == 0 or industry_code.find('N') == 0 or industry_code.find('P') == 0 or industry_code.find('Q') == 0 :
            continue
        
        
        stocks = get_industry_stocks(industry[0])
        stcode = get_industries_max_eps_stock(stocks, 0.5 ,1,context)
        
        if stcode != None:
            stock_lst.extend(stcode)
    
    ## 过滤ST股票
    current_data = get_current_data()
    security_list = [stock for stock in stock_lst if not current_data[stock].is_st]
    
    return security_list


# 获取预期涨幅最大的股票
def get_industries_max_eps_stock(stocks, pre_grouth,max_size ,context):
    
    
    q = query(indicator.code, indicator.eps, indicator.ocf_to_revenue,indicator.adjusted_profit_to_profit, indicator.pubDate).filter(indicator.code.in_(stocks),indicator.eps > 0)

    eps_df = get_fundamentals(q)
    
    stocks_5list = []
    
    
    if eps_df.size > 0 :
        
        price_df = get_stock_pre_close_price(stocks)
        filter_df = pd.DataFrame(columns=['code', 'eps', 'cur_price','grouth','adjusted_profit_to_profit', 'ocf_to_revenue'])
        
        #log.info('行业初始化股票的收益：'+str(eps_df))
        for stock_code in stocks:
            #log.info('遍历股票：'+ stock_code)
            for eps_item in eps_df.iterrows():
                #log.info('22遍历股票00::：'+ str(eps_item[0]) )
                #log.info('22遍历股票11::：' + str(eps_item[1]['eps']))
                if eps_item[1]['code']  == stock_code :
                    #log.info('过滤股票的收益：'+str(price_df[stock_code][0]))
                    #log.info('过滤股票的收益：'+str(eps_item))
                    growth = (eps_item[1]['eps'] * 16.5 ) / price_df[stock_code][0]
                    
                    #if growth > pre_grouth :
                    if growth > pre_grouth :
                        filter_df = filter_df.append({
                            'code':stock_code, 
                            'eps':eps_item[1]['eps'], 
                            'cur_price':price_df[stock_code][0],
                            'grouth':growth },ignore_index=True)
                        
                    
        filter_df = filter_df.sort(['grouth'],ascending=False)
        #log.info('高预期收益的股票：'+str(filter_df))
   
        if filter_df.size > 0 :
            index = 0
            for f_item in filter_df.iterrows():
                if index < max_size:
                    index = index + 1
                    stocks_5list.append(f_item[1]['code'])
                    
            return stocks_5list
    
    
    return None


    
#获取股票的收盘价
def get_stock_pre_close_price(codelst):
    his_price = history(1,'1d','close',codelst)
   
    return his_price
    
    
## 收盘后运行函数  
def after_market_close(context):
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    #打印账户总资产
    log.info('今日账户总资产：%s'%round(context.portfolio.total_value,2))
    #log.info('##############################################################')
