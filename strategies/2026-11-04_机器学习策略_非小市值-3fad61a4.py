# Clone from JoinQuant
# postId: 3fad61a41875edbfd4341fba1f5808e1
# backtestId: 7e7db3db4bee4aacf25aab2fe0357063
# title: 机器学习策略（非小市值）

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import pickle
from six import StringIO,BytesIO # py3的环境，使用BytesIO
import talib

# 初始化函数
def initialize(context):
    # 设定基准
    set_benchmark('000985.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    # 初始化全局变量
    g.no_trading_today_signal = False
    g.stock_num = 5
    g.hold_list = []  # 当前持仓的全部股票
    g.yesterday_HL_list = []  # 记录持仓中昨日涨停的股票


    g.model = pickle.loads(read_file('model_v3.0.pkl'))
                
    g.factor_list = list(pd.read_csv(BytesIO(read_file('factors_2.csv')))['0'])

    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    run_monthly(weekly_adjustment, 1, '9:30')
    # run_weekly(weekly_adjustment, 1, '9:30')
    run_daily(check_limit_up, '14:00')  # 检查持仓中的涨停股是否需要卖出
    run_daily(close_account, '14:30')



# 1-1 准备股票池
def prepare_stock_list(context):
    # 获取已持有列表
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    # 获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close', 'high_limit'],
                       count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    # 判断今天是否为账户资金再平衡的日期
    # g.no_trading_today_signal = today_is_between(context, '04-05', '04-30')


# 1-2 选股模块
def get_stock_list(context):
    # 指定日期防止未来数据
    yesterday = context.previous_date
    today = context.current_dt
    # 获取初始列表
    initial_list = get_index_stocks('000985.XSHG', today)
    # initial_list = get_index_stocks('399101.XSHE', today)
    # initial_list = get_index_stocks('000852.XSHG', today)
    initial_list = filter_all_stock2(context, initial_list)
    final_list = []
    # MS
    factor_data1 = get_factor_values(initial_list, g.factor_list[:30], end_date=yesterday, count=1)
    factor_data2 = get_factor_values(initial_list, g.factor_list[30:70], end_date=yesterday, count=1)
    factor_data3 = get_factor_values(initial_list, g.factor_list[70:], end_date=yesterday, count=1)

    
    df_jq_factor_value1 = pd.DataFrame(index=initial_list, columns=g.factor_list[:30])
    for factor in g.factor_list[:30]:
        df_jq_factor_value1[factor] = list(factor_data1[factor].T.iloc[:, 0])
    
    df_jq_factor_value2 = pd.DataFrame(index=initial_list, columns=g.factor_list[30:70])
    for factor in g.factor_list[30:70]:
        df_jq_factor_value2[factor] = list(factor_data2[factor].T.iloc[:, 0])
    
    df_jq_factor_value3 = pd.DataFrame(index=initial_list, columns=g.factor_list[70:])
    for factor in g.factor_list[70:]:
        df_jq_factor_value3[factor] = list(factor_data3[factor].T.iloc[:, 0])
        
    df_jq_factor_value = pd.concat([df_jq_factor_value1, df_jq_factor_value2, df_jq_factor_value3], axis=1)
    
    
    # df_jq_factor_value = data_preprocessing(df_jq_factor_value, initial_list, industry_code, yesterday)

    
    tar = g.model.predict(df_jq_factor_value)

    df = df_jq_factor_value
    df['total_score'] = list(tar)#
    # print(np.mean(tar[:, 1]))
    
    df = df.sort_values(by=['total_score'], ascending=False)  # 分数越高即预测未来收益越高，排序默认降序
    top_20_percent_rows = int(0.2 * len(df))
    df = df.head(top_20_percent_rows)
    
    lst = df.index.tolist()
    lst = filter_paused_stock(lst)
    lst = filter_limitup_stock(context, lst)
    lst = filter_limitdown_stock(context, lst)
    # lst = lst[:len(lst)//5]
    lst = lst[:5]
    print(len(lst))
    
    # lst = GGX_stock(context,lst) #高股息外挂
    # lst = RSI(context,lst)
    # lst = small(context,lst) #小市值外挂
    # lst = get_rank(context,lst) #动量外挂
    # lst= DAMA(context,lst) #大妈外挂
    # lst = check_big_green(context,lst,30)
    # lst = filter_roic(context,lst)
    # lst = _natr(context,lst)
    # lst = filter_shenxiao_stock(context,lst) #玄学字母外挂

        
    
    for stock in lst:
        if stock not in final_list:
            final_list.append(stock)
    return final_list

    
def filter_shenxiao_stock(context, stock_list):
    current_data = get_current_data()
    keywords = ['龙','华', '发', '方', '新', '银', '神', '金', '凤', '鼠', '牛', '虎', '兔', '蛇', '马', '羊', '猴', '鸡', '狗', '猪']
    # keywords = ['龙', '发', '方', '新', '银']
    LIST = []
    for stock in stock_list:
        for KEY in current_data[stock].name:
            if str(KEY) in keywords:
                LIST.append(stock)
    return LIST
    
def check_big_green(context,stock_list,days):#检查前几个交易日是否存在大阴线
    list_check = []
    for stock in stock_list:
        df = get_price(stock, start_date=None, end_date=context.previous_date, frequency='daily', fields=['close', 'open'], skip_paused=True, fq='pre', count=days, panel=False, fill_paused=True)
        if len(df[df['close'] / df['open'] <= 0.97]) <= 2:
            list_check.append(stock)
    return list_check
    
    
def _natr(context,stock_list):
    yesterday = context.previous_date
    df1 = []
    for s in stock_list:
        timeperiod=14
        count=timeperiod+1
        price=get_price(s,end_date=yesterday,count=count,fields=['close','high','low'],panel=False)
        NATR = talib.NATR(price['high'].values.flatten(), price['low'].values.flatten(), price['close'].values.flatten(), timeperiod=14)
        if NATR[-1]<4.5:
            df1.append(s)
    return df1
    
def RSI(context,stock_list):
    yesterday = context.previous_date
    df1=[]
    for s in stock_list:
        period=14
        count=period+1
        price=get_price(s,end_date=yesterday,count=count,fields=['close'])
        price=price['close'].values
        rsi=talib.RSI(price,timeperiod=period)
        if rsi[-1]<50:
            df1.append(s)
    return df1   
            
def filter_roic(context,stock_list):
    yesterday = context.previous_date
    list=[]
    for stock in stock_list:
        roic=get_factor_values(stock, 'roic_ttm', end_date=yesterday,count=1)['roic_ttm'].iloc[0,0]
        if roic>0.08:
            list.append(stock)
            
    return list
    
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365*3)#最近3年分红
    #获取分红数据，由于finance.run_query最多返回4000行，以防未来数据超限，最好把stock_list拆分后查询再组合
    interval = 1000 #某只股票可能一年内多次分红，导致其所占行数大于1，所以interval不要取满4000
    list_len = len(stock_list)
    #截取不超过interval的列表并查询
    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    #对interval的部分分别查询并拼接
    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date,  finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval*(i+1):min(list_len,interval*(i+2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0)#df.fillna() 是一个 Pandas 数据处理库中的函数，它可以用来填充数据框中的空值
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index) #query查询不到无分红信息的股票，所以temp_list长度会小于stock_list
    # #获取市值相关数据
    q = query(valuation.code,valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1)
    cap = cap.set_index('code')
    # #计算股息率
    cap['dividend_ratio']=(dividend['bonus_amount_rmb']/10000)/cap['market_cap']
    # #排序并筛选
    cap = cap.sort_values(by=['dividend_ratio'], ascending=sort)
    final_list = list(cap.index)[int(p1*len(cap)):int(p2*len(cap))]
    # print("近3年累计分红率排名前{0:.2%}的股有{1}只".format(p2,len(final_list)))
    return final_list
    
def GGX_stock(context, stock_list):
    current_data = get_current_data()
    LIST = get_dividend_ratio_filter_list(context, stock_list, False, 0, 0.2)
    return LIST
    
def small(context,stocks):
    # 获取基本面数据
    q = query(valuation.code,
                valuation.pe_ratio,
                indicator.inc_net_profit_year_on_year,
                valuation.pe_ratio / indicator.inc_net_profit_year_on_year,# PEG
                indicator.roe / valuation.pb_ratio, # 收益率指标：ROE/PB特别适合于周期类、成长性一般企业的估值分析
                indicator.roe,
                indicator.roa,
                valuation.pb_ratio
                ).filter(
                    # valuation.pe_ratio > 0,
                    # indicator.inc_net_profit_year_on_year > 0,
                    # valuation.pe_ratio / indicator.inc_net_profit_year_on_year<1,
                    # valuation.pb_ratio < 3,
                    # indicator.roe / valuation.pb_ratio > 3.2,   #国债收益率
                    indicator.roe > 0.15,
                    indicator.roa > 0.10,
                    valuation.code.in_(stocks))
    df_fundamentals = get_fundamentals(q, date = None)       
    stocks = list(df_fundamentals.code)
    # fuandamental data
    df = get_fundamentals(query(valuation.code).filter(valuation.code.in_(stocks)).order_by(valuation.market_cap.asc()))
    choice = list(df.code)
    return choice[:10]

def initial_stock_motion(stock_pool):
    stock_motion = {}
    for stock in stock_pool:
        motion_que = []
        data = attribute_history(stock, g.biasN + g.momentum_day + 1, '1d', ['close'])
        data = data[:-1]
        bias = (data.close/data.close.rolling(g.biasN).mean())[-g.momentum_day:] # 乖离因子
        score = np.polyfit(np.arange(g.momentum_day),bias/bias[0],1)[0].real*10000 # 乖离动量拟合
        motion_que.append(score)
        stock_motion[stock] = motion_que
    return(stock_motion)
    
def get_rank(context,stock_pool):
    rank = []
    stock_motion = initial_stock_motion(stock_pool) # 除去回测第一天的动量
    for stock in stock_pool:
        data = attribute_history(stock, g.biasN + g.momentum_day, '1d', ['close'])
        bias = (data.close/data.close.rolling(g.biasN).mean())[-g.momentum_day:] # 乖离因子
        score = np.polyfit(np.arange(g.momentum_day),bias/bias[0],1)[0].real*10000 # 乖离动量拟合
        adr = 100*(data.close[-1] - data.close[-2])/data.close[-2] #股票的涨跌幅度
        if(stock == g.hold_stock): raise_x = g.SwitchFactor
        else: raise_x = 1
        rank.append([stock, score*raise_x, adr])
        stock_motion[stock].append(score)
        if(len(stock_motion[stock])>5):stock_motion[stock].pop(0)
    df = pd.DataFrame(rank)
    print()
    df['S'] = df[[1, 2]].apply(lambda x: (x - x.min()) / (x.max() - x.min())).sum(axis=1)
    result_list = df.nlargest(10, 'S')[0].tolist()
    return result_list

# 1-3 整体调整持仓
def weekly_adjustment(context):
    if g.no_trading_today_signal == False:
        # 获取应买入列表
        target_list = get_stock_list(context)
        # 调仓卖出
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("已持有[%s]" % (stock))
        # 调仓买入
        position_count = len(context.portfolio.positions)
        print(position_count)
        target_num = len(target_list)
        print(target_num)
        if target_num > position_count:
            print(context.portfolio.cash)
            value = context.portfolio.cash / (target_num - position_count)
            for stock in target_list:
                if context.portfolio.positions[stock].total_amount == 0:
                    if open_position(stock, value):
                        if len(context.portfolio.positions) == target_num:
                            break
 



# 1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        # 对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'],
                                     skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("[%s]涨停，继续持有" % (stock))

def filter_all_stock2(context, stock_list):
    # 过滤次新股（新股、老股的分界日期，两种指定方法）
    # 新老股的分界日期, 自然日180天
    # by_date = context.previous_date - datetime.timedelta(days=180)
    # 新老股的分界日期，120个交易日
    by_date = get_trade_days(end_date=context.previous_date, count=375)[0]
    all_stocks = get_all_securities(date=by_date).index.tolist()
    stock_list = list(set(stock_list).intersection(set(all_stocks)))

    curr_data = get_current_data()
    return [stock for stock in stock_list if not (
            stock.startswith(( '3','68', '4', '8')) or  # 创业，科创，北交所
            curr_data[stock].paused or
            curr_data[stock].is_st or  # ST
            ('ST' in curr_data[stock].name) or
            ('*' in curr_data[stock].name) or
            ('退' in curr_data[stock].name) or
            (curr_data[stock].day_open == curr_data[stock].high_limit) or  # 涨停开盘, 其它时间用last_price
            (curr_data[stock].day_open == curr_data[stock].low_limit)  # 跌停开盘, 其它时间用last_price
    )]
# 3-1 交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)


# 3-2 交易模块-开仓
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False


# 3-3 交易模块-平仓
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False


# 4-1 判断今天是否为账户资金再平衡的日期
def today_is_between(context, start_date, end_date):
    today = context.current_dt.strftime('%m-%d')
    if (start_date <= today) and (today <= end_date):
        return True
    else:
        return False


# 4-2 清仓后次日资金可转
def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                close_position(position)
                log.info("卖出[%s]" % (stock))

# 2-1 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


# 2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


# 2-3 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68' or stock[0] == '3':
            stock_list.remove(stock)
    return stock_list


# 2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


# 2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]


# 2-6 过滤次新股
def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if
            not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=375)]



def get_industry_name(i_Constituent_Stocks, value):
    return [k for k, v in i_Constituent_Stocks.items() if value in v]

#缺失值处理
def replace_nan_indu(factor_data,stockList,industry_code,date):
    #把nan用行业平均值代替，依然会有nan，此时用所有股票平均值代替
    i_Constituent_Stocks={}
    data_temp=pd.DataFrame(index=industry_code,columns=factor_data.columns)
    for i in industry_code:
        temp = get_industry_stocks(i, date)
        i_Constituent_Stocks[i] = list(set(temp).intersection(set(stockList)))
        data_temp.loc[i]=mean(factor_data.loc[i_Constituent_Stocks[i],:])
    for factor in data_temp.columns:
        #行业缺失值用所有行业平均值代替
        null_industry=list(data_temp.loc[pd.isnull(data_temp[factor]),factor].keys())
        for i in null_industry:
            data_temp.loc[i,factor]=mean(data_temp[factor])
        null_stock=list(factor_data.loc[pd.isnull(factor_data[factor]),factor].keys())
        for i in null_stock:
            industry=get_industry_name(i_Constituent_Stocks, i)
            if industry:
                factor_data.loc[i,factor]=data_temp.loc[industry[0],factor] 
            else:
                factor_data.loc[i,factor]=mean(factor_data[factor])
    return factor_data
industry_code = ['801010','801020','801030','801040','801050','801080','801110','801120','801130','801140','801150',\
                    '801160','801170','801180','801200','801210','801230','801710','801720','801730','801740','801750',\
                   '801760','801770','801780','801790','801880','801890']
def data_preprocessing(factor_data,stockList,industry_code,date):
    #去极值
    factor_data=winsorize_med(factor_data, scale=5, inf2nan=False,axis=0)
    #缺失值处理
    factor_data=replace_nan_indu(factor_data,stockList,industry_code,date)
    #中性化处理
    # factor_data=neutralize(factor_data, how=['sw_l1', 'market_cap'], date=date, axis=0)
    #标准化处理
    factor_data=standardlize(factor_data,axis=0)
    return factor_data