# Clone from JoinQuant
# postId: 4e138766f6ebd06c405713df33bc4ebd
# backtestId: 72c9c7ac1aa92cbe3c06bf4adeb20a87
# title: 修改

# 克隆自聚宽文章：https://www.joinquant.com/post/27454
# 标题：策略：多因子打分法选股+双均线+择时卖出
# 作者：好名字smurf

# 作者：蓝精灵smurf

'''
多因子打分法选股 + 双均线策略 + 择时卖出
'''
# 导入函数库
import numpy as np 
import pandas as pd 
from jqdata import *
from jqlib.technical_analysis import *
import datetime as dt

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    # 排除上市不足45天的股票
    g.count = 45
    # 购买股数
    g.num =15
    # 止盈百分比
    g.stop_win_per = 1.08
    # 与收益率成负相关的升序因子
    g.up_list = ['market_cap'] 
    
    # 盘中运行
    run_monthly(score_select, 1, time='open', reference_security='000300.XSHG')
    # 盘中止盈卖出
    run_daily(sell_stock, time='14:08', reference_security='000300.XSHG')  

def score_select(context):
    # 获取因子数据
    q = query(
        valuation.code,
        valuation.market_cap,
        indicator.roa,  # ROA
        income.operating_profit,  # 营业利润 
        indicator.adjusted_profit, # 净利润（扣非）
        # valuation.pb_ratio,
        # valuation.pe_ratio,
        # valuation.turnover_ratio,  # 换手率
        # indicator.roe,  # ROE
        # income.operating_revenue, # 营业收入
        # # income.net_profit, # 净利润
        # # income.total_operating_revenue,   # 营业总收入
        # indicator.inc_revenue_annual,     #营业收入环比增长率
        # indicator.inc_net_profit_annual,   #净利润环比增长率
        # indicator.gross_profit_margin * income.operating_revenue / balance.total_assets, # 毛利润/总资产
        # income.operating_profit/income.operating_revenue,   # 营业利润率
        # indicator.gross_profit_margin,  # 毛利率
        )
            
    df = get_fundamentals(q).set_index('code')
    factors_data = df.dropna() # 把带有缺失值的行数据全部丢掉
    #factors_data = factors_data[(factors_data['pe_ratio']>0) & (factors_data['pb_ratio']>0)]  # 排除pe,pb为负数的值

    # 2. 定义打分函数，确定股票池
    select_stock_list(context, factors_data)
    
    # 3. 定义调仓买卖函数
    rebalance(context)
    
    
# 打分的具体步骤，返回股票池
# 1）因子与收益率成负相关，值越小越好
# 2）因子与收益率成正相关，值越大越好
def select_stock_list(context, factors_data):
    """
    第一步：打分选股，股票总分越低，越有买入价值
    """
    # 循环处理每个因子
    for name in factors_data.columns:  # columns列名
        # 因子与收益率成负相关，则进行升序排序
        if name in g.up_list:
            print(name)
            factor = factors_data.sort_values(by=name)[name]  # 从小到大排序
        # 因子与收益率成正相关，则进行降序排序
        else:
            factor = factors_data.sort_values(by=name, ascending=False)[name] # 从大到小排序
        
        # factor的类型是Series，需要转换成dataframe，目的是为了增加列分数
        factor = pd.DataFrame(factor)
        # 对单个因子进行打分处理
        factor[name + '_score'] = 0

        # 升序降序都分成10组，先求出每组股票数量，然后根据数量依次给出分数
        stock_groupnum = len(factor) // 10  # 最后一组会多些，要考虑余数
        for i in range(10):
            if i == 9:   # 考虑最后一组股票数可能多些，因为len(factors_data) // 10可能有余数
                factor[name + '_score'][i*stock_groupnum:] = i + 1
            else:
                factor[name + '_score'][i*stock_groupnum:(i+1)*stock_groupnum] = i + 1
        # 拼接每个因子的分数到原始的factors_data数据当中,axis=1表示按列进行拼接
        factors_data = pd.concat([factors_data, factor[name + '_score']], axis=1)
    
    # 对因子的分数进行求和排序找出股票, sum(axis=1)表示按行求和， sort_values()表示按照从小到大排序
    stocks_sorted = list(factors_data.sum(axis=1).sort_values().index)
    
    """
    第二步：排除st股，停牌股，退市股，科创板股，上市不足45天的股票
    """
    stock_list = Get_all_security_list(context, stocks_sorted)
    
    """
    第三步：双均线策略：5日均线突破60日均线则买入
    """
    # 双均线策略
    stock_list = double_equal_line_strategy(context, stock_list)
    # 选出排名最好的前g.num只股票
    g.to_hold = stock_list[:g.num]
    
    # if(g.to_hold is None):
    #     return None
    # else:
    #     return g.to_hold
 
# 止盈卖出函数
def sell_stock(context):
    if(len(context.portfolio.positions.keys())>0):
        for stock in context.portfolio.positions.keys():
            stock_data = get_current_data()
            current_price = stock_data[stock].last_price
            high_limit_price = stock_data[stock].high_limit  # 涨停价
            average_cost = context.portfolio.positions[stock].avg_cost 
            closeable_amount = context.portfolio.positions[stock].closeable_amount
            # df = get_price(stock, end_date=context.previous_date, frequency='daily', fields=['close'], skip_paused=True, fq='pre', count=1)
            # if df.empty:
            #     continue
            # pre_close_price = df['close'][0]
            if (closeable_amount>0 and current_price<high_limit_price and current_price>g.stop_win_per*average_cost):
                order_target(stock,0)
                
# 调仓函数,先卖后买
def rebalance(context):
    
    # 卖出
    for stock in context.portfolio.positions.keys():
        if stock not in g.to_hold:
            order_target_value(stock,0)
    
    # 买入
    cash = context.portfolio.total_value / len(g.to_hold)
    for stock in g.to_hold:
        if stock not in context.portfolio.positions.keys():
            order_target_value(stock,cash)
    
def Get_all_security_list(context, stocks_sorted):
    security_list=[]
    for stock in stocks_sorted:
         security_obj = get_security_info(stock)
         if(str(security_obj.type) == 'stock'):
             if(context.current_dt.date()<security_obj.end_date and security_obj.start_date<context.current_dt.date()):#过滤掉退市的公司和相关新股
                     security_list.append(stock)
             else:
                     pass
         else:
             log.info('不是股票类型') 
             
    #log.info('包括停牌在内所有公司数量 = ',len(security_list))
    ####
    security_list = filter_st_and_paused(security_list)
    
    #log.info('去除ST和停牌的公司数量： ',len(security_list)) 
    
    security_list = filter_kc_ban(security_list)
    
    #log.info('去除科创板的公司数量： ',len(security_list)) 
    
    #security_list = filter_gem_stock(security_list)
    
    #log.info('去除创业板的公司数量： ',len(security_list)) 
    
    security_list =filter_new(context,security_list,g.count)
    
    #log.info('去除上市不足45天的数量： ',len(security_list)) 
    
    return security_list

    
def filter_new(context, equity, deltaday):
    deltaDate = context.current_dt.date() - dt.timedelta(deltaday)

    tmpList = []
    for stock in equity:
        if get_security_info(stock).start_date < deltaDate:
            tmpList.append(stock)

    return tmpList  
    
def filter_st_and_paused(stock_list):
     current_data = get_current_data()
     retult_list=[]
     for stock in stock_list:
         if( not current_data[stock].is_st and not current_data[stock].paused):
             retult_list.append(stock)
     return retult_list

def filter_kc_ban(stock_list):
    #过滤科技板
    return [stock for stock in stock_list if stock[0:3] != '688']
    
# 双均线策略
def double_equal_line_strategy(context, stock_list):
    
    stock_to_buy = []
    for stock in stock_list:
        # 金叉：如果5日均线大于10日均线并且不持仓
        # 死叉：如果5日均线小于如果5日均线大于10日均线并且持仓
        df = attribute_history(stock, 61) # 获取最近61日的历史数据
        pre_ma60 = df['close'][:60].mean()
        pre_ma5 = df['close'][:5].mean()
        today_ma60 = df['close'][-60:].mean()
        today_ma5 = df['close'][-5:].mean()
        
        # 5日均线上穿60日均线，该股票值得拥有
        if (today_ma60 < today_ma5) and (pre_ma60 > pre_ma5):
            stock_to_buy.append(stock)
            
    return stock_to_buy

