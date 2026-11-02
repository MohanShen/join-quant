# Clone from JoinQuant
# postId: b69eb2ed409465cdc5abdb1c096df3fd
# backtestId: 69e2a6ec8e547005508cff7ef318e54a
# title: 为什么回测时账户有现金但显示保证金不足不能购买？

# 导入函数库
from jqdata import *
import re 
import pandas as pd
import numpy as np
pd.set_option('display.max_columns', None)

## 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')

    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 设置期货交易的滑点
    set_slippage(StepRelatedSlippage(2))
    # 设置做多做空方向
    g.flag=0
    g.resultall = {}
    g.targetfuture={}
    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF8888.CCFX'或'IH1602.CCFX'是一样的）
    # 注意：before_open/open/close/after_close等相对时间不可用于有夜盘的交易品种，有夜盘的交易品种请指定绝对时间（如9：30）
      # 开盘前运行
    run_daily( before_market_open, time='09:00', reference_security='IF8888.CCFX')
      # 开盘时运行
    run_daily( market_open, time='09:45', reference_security='IF8888.CCFX')
      # 收盘后运行
    run_daily( after_market_close, time='15:30', reference_security='IF8888.CCFX')


## 开盘前运行函数
def before_market_open(context):
    g.future_Contract_Size = {'A':10, 'AG':15, 'AL':5, 'AU':1000,
                        'B':10, 'BB':500, 'BU':10, 'C':10,
                        'CF':5, 'CS':10, 'CU':5, 'ER':10,
                        'FB':500, 'FG':20, 'FU':50, 'GN':10,
                        'HC':10, 'I':100, 'IC':200, 'IF':300,
                        'IH':300, 'J':100, 'JD':5, 'JM':60,
                        'JR':20, 'L':5, 'LR':10, 'M':10,
                        'MA':10, 'ME':10, 'NI':1, 'OI':10,
                        'P':10, 'PB':5, 'PM':50, 'PP':5,
                        'RB':10, 'RI':20, 'RM':10, 'RO':10,
                        'RS':10, 'RU':10, 'SF':5, 'SM':5,
                        'SN':1, 'SR':10, 'T':10000, 'TA':5,
                        'TC':100, 'TF':10000, 'V':5, 'WH':20,
                        'WR':10, 'WS':50, 'WT':10, 'Y':10,
                        'ZC':100, 'ZN':5,'AP':10}
    g.futrue_bzj={'IF': 0.08, 'IC': 0.08, 'IM': 0.08, 'IH': 0.08, 'TS': 0.005, 'TF': 0.01, 'T': 0.02, 'SA': 0.05, 'AU': 0.04, 'J': 0.05, 'RB': 0.05, \
    'UR': 0.08, 'I': 0.0005, 'ru': 0.1, 'SC': 0.05, 'p': 0.08, 'AG': 0.04, 'TL': 0.035, 'TA': 0.05, 'ZC': 0.05, 'WH': 0.05, 'RI': 0.05, 'LR': 0.05, \
    'PM': 0.05, 'CY': 0.05, 'FG': 0.05, 'MA': 0.05, 'SR': 0.05, 'PF': 0.05, 'SF': 0.05, 'JR': 0.05, 'CJ': 0.07, 'PK': 0.05, 'AP': 0.07, 'OI': 0.05, \
    'RS': 0.05, 'RM': 0.05, 'CF': 0.05, 'SM': 0.05, 'NR': 0.07, 'LU': 0.08, 'BC': 0.05, 'SI': 0.05, 'SS': 0.05, 'RU': 0.05, 'AO': 0.05, 'BU': 0.04,\
    'PB': 0.05, 'CU': 0.05, 'AL': 0.05, 'ZN': 0.05, 'SN': 0.05, 'NI': 0.05, 'HC': 0.04, 'FU': 0.08, 'SP': 0.04, 'WR': 0.07, 'PG': 0.05, 'V': 0.05, \
    'EG': 0.05, 'L': 0.05, 'P': 0.05, 'JM': 0.05, 'C': 0.05, 'CS': 0.05, 'LH': 0.05, 'RR': 0.05, 'FB': 0.05, 'PP': 0.05, 'BB': 0.05, 'EB': 0.05,\
    'A': 0.05, 'B': 0.05, 'Y': 0.05, 'M': 0.05, 'JD': 0.05}
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    
    # 月度四个维度分析,有基比、环比、成交量、震幅
    # 获得所有期货品种
    valution_day=str(context.current_dt.date())
    letterssll=futurehs(valution_day)
    # print('letterssll',letterssll)
    # print('len(letterssll)',len(letterssll))
    # 获取月度数据
    IF9999,IF8888=zlhy36month(['IF'],valution_day)
    g.future8888month=IF8888
    # print('g.future8888month',g.future8888month)
    # 获取周度数据
    IF9999week,IF8888week=zlhy57week(['IF'],valution_day)
    g.future8888week=IF8888week
    # print('g.IF8888week',g.IF8888week)
    # print('IF9999week',IF9999week,'IF8888week',IF8888week)
    # 获取日度数据
    IF9999day,IF8888day=zlhy90day(['IF'],valution_day)
    g.future8888day=IF8888day
    # print('IF9999day',IF9999day,'IF8888day',IF8888day)
    # print('g.IF8888day',g.IF8888day)
    # 获取小时数据
    IF9999hour,IF8888hour=zlhy145hour(['IF'],valution_day)
    g.future8888hour=IF8888hour
    # print('IF9999hour',IF9999hour,'IF8888hour',IF8888hour)
    # 获取半时数据
    IF9999halfhour,IF8888halfhour=zlhy145halfhour(['IF'],valution_day)
    g.future8888halfhour=IF8888halfhour
    # print('IF9999halfhour',IF9999halfhour,'IF8888halfhour',IF8888halfhour)
    # 趋势周期分析，包括异常涨跌幅分析，通过指数合约进行判断
    result=monthzfzb(IF8888)
    print('趋势周期分析',monthzfzb(IF8888))
    # print('趋势周期分析',result)
    # # print('result_num',result_num)
    # 趋势成交量分析
    print('趋势成交量分析',monthcclhs(IF8888))
    # # 趋势基比价格分析
    print('趋势基比价格分析',monthbhs(IF8888))
    # monthbhs(IF8888)
    # 月度投资方向1
    # print('趋势周期分析',monthzfzb(IF8888) == "做多")
    # print('趋势成交量分析',monthcclhs(IF8888) == "做多")
    # print('趋势基比价格分析',monthbhs(IF8888) == "做多")
    if (monthzfzb(IF8888) == "做多") + (monthcclhs(IF8888) == "做多") + (monthbhs(IF8888) == "做多") >= 2:
        invent_result = "做多"
    else:
        invent_result = "做空"
    # print('投资方向1',invent_result)
    # 当前情绪
    print('当前情绪',traderpsy(IF8888))
    # 异常涨跌判断
    print('判断涨幅是否异常', g.pctycpd)
    # 调整后投资方向
    print('调整后投资方向', longshortajust(traderpsy(IF8888),g.pctycpd,invent_result))
    g.resultjustmonth= longshortajust(traderpsy(IF8888),g.pctycpd,invent_result)
    
    #判断最终投资方向
    # 年度
    IF9999_year,IF8888_year=zlhy13year(['IF'],valution_day)
    # print('IF8888_year',IF8888_year)
    # 年度趋势周期分析
    print('年度趋势周期分析',yearzfzb(IF8888_year))
    # # 趋势成交量分析
    print('年度趋势成交量分析',yearcclhs(IF8888_year))
    # # 趋势基比价格分析
    print('年度趋势基比价格分析',yearbhs(IF8888_year))
    # 年度投资方向1
    if (yearzfzb(IF8888_year) == "做多") + (yearcclhs(IF8888_year) == "做多") + (yearbhs(IF8888_year) == "做多") >= 2:
        invent_resultyear = "做多"
    else:
        invent_resultyear = "做空"
    print('年度投资方向1',invent_resultyear)
    # 年度当前情绪
    print('年度当前情绪',traderpsyyear(IF8888_year))
    # 年度异常涨跌判断
    print('年度判断涨幅是否异常', g.pctycpdyear)
    # 年度调整后投资方向
    print('年度调整后投资方向', longshortajustyear(traderpsyyear(IF8888_year),g.pctycpdyear,invent_resultyear))
    result =  longshortajust(traderpsy(IF8888),g.pctycpd,invent_result) if longshortajustyear(traderpsyyear(IF8888_year),g.pctycpdyear,\
    invent_resultyear) ==  longshortajust(traderpsy(IF8888),g.pctycpd,invent_result) else "等待"
    g.resultall['IF'] = result
    print('%s最终投资方向%s'%('IF',result))
    
# 145半时
def zlhy145halfhour(future_list,valution_day):
    df1 = pd.DataFrame()  # DataFrame to store results of '88' suffix
    df2 = pd.DataFrame() 
    
    def year13before (date):
        from datetime import datetime, timedelta

        # 将日期字符串转换为 datetime 对象
        date_str = date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        # 将年份减去13
        new_year = date_obj.year - 12

        # 构造新的 datetime 对象
        new_date_obj = datetime(new_year, date_obj.month, date_obj.day)

        # 将结果转换为字符串并用中文返回
        result = new_date_obj.strftime('%Y-%m-%d')
    #     print(result)
        return result

    def find_last_trading_90day(trade_list):
        return trade_list[-90:]

    trade_day=get_trade_days(year13before(valution_day), valution_day)
#     trade_dayall=last_trade_day(trade_day)
    trade_day_90day=find_last_trading_90day(trade_day)
#     print('trade_day_jd',trade_day_jd)
#     return trade_day_jd

    letterssll=future_list
    
    # 获得期货品种的后缀
    def future_hz(future):
        string=get_dominant_future(future)
        string = string.split('.')[1]
        return string

    def process_data(j, suffix):
#         mm=get_price(j+suffix, start_date=trade_day_90day[-40], end_date=trade_day_90day[-1],frequency='30m')
        mm=get_price(j+suffix+'.'+future_hz(j), start_date=trade_day_90day[-40],\
                              end_date=str(trade_day_90day[-1])+' 15:00:00',frequency='30m', \
                              fields=['open', 'close', 'high', 'low', 'volume', 'money','open_interest'])
        ff = pd.DataFrame()
        ff['开盘价'] = mm['open']
        ff['最高价'] = mm['high']
        ff['最低价'] = mm['low']
        ff['收盘价'] = mm['close']
        ff['145半时持仓量'] = mm['open_interest'].rolling(145).sum()
        ff['145半时成交量'] = mm['volume'].rolling(145).sum()
        ff['145半时成交金额'] = mm['money'].rolling(145).sum()
        # Set the index of ff to be the 'datetime' level of mm's MultiIndex
#         ff.index = mm.index.get_level_values('datetime')
        ff.index = mm.index
        ff = ff.sort_index(ascending=False)
        ff=ff.iloc[:145]
        ff.insert(0, '品种时间', [j+str(time) for time in ff.index])
#         print(j+suffix',ff)
#         print(j + suffix, ff)
        return ff

    # 连续合约前复权平滑处理
    for j in letterssll:
#         process_data(j, '88')
#         df1 = process_data(j, '88')
        df1 = process_data(j, '9999')#主力连续合约
        df1.replace(0, float('nan'), inplace=True)

    # 指数全部连续合约
    for j in letterssll:
#         process_data(j, '99')
#         df2 = process_data(j, '99')
        df2 = process_data(j, '8888')#指数合约
        df2.replace(0, float('nan'), inplace=True)
    return df1, df2

# 145时
def zlhy145hour(future_list,valution_day):
    df1 = pd.DataFrame()  # DataFrame to store results of '88' suffix
    df2 = pd.DataFrame() 
    
    def year13before (date):
        from datetime import datetime, timedelta

        # 将日期字符串转换为 datetime 对象
        date_str = date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        # 将年份减去13
        new_year = date_obj.year - 12

        # 构造新的 datetime 对象
        new_date_obj = datetime(new_year, date_obj.month, date_obj.day)

        # 将结果转换为字符串并用中文返回
        result = new_date_obj.strftime('%Y-%m-%d')
    #     print(result)
        return result

    def find_last_trading_90day(trade_list):
        return trade_list[-90:]

    trade_day=get_trade_days(year13before(valution_day), valution_day)
#     trade_dayall=last_trade_day(trade_day)
    trade_day_90day=find_last_trading_90day(trade_day)
#     print('trade_day_jd',trade_day_jd)
#     return trade_day_jd

    letterssll=future_list
    # 获得期货品种的后缀
    def future_hz(future):
        string=get_dominant_future(future)
        string = string.split('.')[1]
        return string

    def process_data(j, suffix):
#         mm=get_price(j+suffix, start_date=trade_day_90day[-60], end_date=trade_day_90day[-1],frequency='60m')
        mm=get_price(j+suffix+'.'+future_hz(j), start_date=trade_day_90day[-60],\
                              end_date=str(trade_day_90day[-1])+' 15:00:00',frequency='60m', \
                              fields=['open', 'close', 'high', 'low', 'volume', 'money','open_interest'])
#         print('trade_day_90day1',trade_day_90day[-60])
#         print('trade_day_90day2',trade_day_90day[-1])
        ff = pd.DataFrame()
#         ff['品种时间']=[j+str(time)[:10] for time in mm.index.get_level_values('datetime')]
        ff['开盘价'] = mm['open']
        ff['最高价'] = mm['high']
        ff['最低价'] = mm['low']
        ff['收盘价'] = mm['close']
        ff['145时持仓量'] = mm['open_interest'].rolling(145).sum()
        ff['145时成交量'] = mm['volume'].rolling(145).sum()
        ff['145时成交金额'] = mm['money'].rolling(145).sum()
        # Set the index of ff to be the 'datetime' level of mm's MultiIndex
#         ff.index = mm.index.get_level_values('datetime')
        ff.index = mm.index
        ff = ff.sort_index(ascending=False)
        ff=ff.iloc[:145]
        # 假设你要添加的列名为'品种时间'，并且你的数据框名为tt_year88
        ff.insert(0, '品种时间', [j+str(time) for time in ff.index])
#         print(j+suffix',ff)
#         print(j + suffix, ff)
        return ff

    # 连续合约前复权平滑处理
    for j in letterssll:
#         process_data(j, '88')
#         df1 = process_data(j, '88')
        df1 = process_data(j, '9999')#主力连续合约
        df1.replace(0, float('nan'), inplace=True)

    # 指数全部连续合约
    for j in letterssll:
#         process_data(j, '99')
#         df2 = process_data(j, '99')
        df2 = process_data(j, '8888')#指数合约
        df2.replace(0, float('nan'), inplace=True)
    return df1, df2

# 90日
def zlhy90day(future_list,valution_day):
    df1 = pd.DataFrame()  # DataFrame to store results of '88' suffix
    df2 = pd.DataFrame() 
    
    def year13before (date):
        from datetime import datetime, timedelta

        # 将日期字符串转换为 datetime 对象
        date_str = date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        # 将年份减去13
        new_year = date_obj.year - 12

        # 构造新的 datetime 对象
        new_date_obj = datetime(new_year, date_obj.month, date_obj.day)

        # 将结果转换为字符串并用中文返回
        result = new_date_obj.strftime('%Y-%m-%d')
    #     print(result)
        return result

    def find_last_trading_90day(trade_list):
        return trade_list[-90:]
    
    def day90star(date):
        import datetime

        # 指定日期
        specified_date = date

        # 找到指定日期在trade_day列表中的位置a
        a = trade_day.index(specified_date)

        # 获取trade_day[a-90:a]的子列表
        sub_list = trade_day[max(0, a-90):a]

        # 打印子列表
    #     print(sub_list)
        return sub_list[0]

    trade_day=list(get_trade_days(year13before(valution_day), valution_day))
#     trade_dayall=last_trade_day(trade_day)
    trade_day_90day=find_last_trading_90day(trade_day)
#     print('trade_day_jd',trade_day_jd)
#     return trade_day_jd

    letterssll=future_list
    # 获得期货品种的后缀
    def future_hz(future):
        string=get_dominant_future(future)
        string = string.split('.')[1]
        return string

    def process_data(j, suffix):
#         ff = pd.DataFrame(columns=['开盘价', '最高价', '最低价', '收盘价', '周持仓量', '周成交量', '周成交金额'])
        ff = pd.DataFrame(columns=['品种时间','开盘价', '最高价', '最低价', '收盘价', '90日持仓量', '90日成交量', '90日成交金额'])
        for i in range(len(trade_day_90day)-1, -1, -1):
#             mm_year=get_price(j+suffix, start_date=get_week_start(find_last_trading_week[i]), end_date=find_last_trading_week[i],frequency='1d')
#             mm_year=get_price(j+suffix, start_date=trade_day_90day[0], end_date=trade_day_90day[-1],frequency='1d')
#             mm=get_price(j+suffix, start_date=trade_day_90day[i], end_date=trade_day_90day[i],frequency='1d')
            mm=get_price(j+suffix+'.'+future_hz(j), start_date=trade_day_90day[i],end_date=trade_day_90day[i],\
                         frequency='1d', fields=['open', 'close', 'high', 'low'])
            try:
                open_year = list(mm.open)[0]
            except:
                open_year = 0
            try:
                high_year = list(mm.high)[0]
            except:
                high_year = 0
            try:
                low_year=list(mm.low)[0]
            except:
                low_year = 0
            try:
                close_year=list(mm.close)[0]
            except:
                close_year = 0
#             mm_year = get_price(j + suffix, start_date=get_quarter_start(trade_day_jd[i]), end_date=trade_day_jd[i], frequency='1d')
#             mm_year=get_price(j+suffix, start_date=day90star(trade_day_90day[i]), end_date=trade_day_90day[i],\
#                               frequency='1d')
            mm_year=get_price(j+suffix+'.'+future_hz(j), start_date=day90star(trade_day_90day[i]),\
                              end_date=trade_day_90day[i],frequency='1d', fields=['volume', 'money','open_interest'])
            try:
                open_interest_year = sum(mm_year.open_interest)
            except:
                open_interest_year = 0
            try:
                volume_year = sum(mm_year.volume)
            except:
                volume_year = 0
            try:
                total_turnover_year = sum(mm_year.money)
            except:
                total_turnover_year = 0
            series = pd.Series({
                '品种时间': j+str(trade_day_90day[i]),
                '开盘价': open_year,
                '最高价': high_year,
                '最低价': low_year,
                '收盘价': close_year,
                '90日持仓量': open_interest_year,
                '90日成交量': volume_year,
                '90日成交金额': total_turnover_year
            })
            ff.loc[trade_day_90day[i]] = series
#         print(j + suffix, ff)
        return ff

    # 连续合约前复权平滑处理
    for j in letterssll:
#         process_data(j, '88')
#         df1 = process_data(j, '88')
        df1 = process_data(j, '9999')#主力连续合约
        df1.index = pd.to_datetime(df1.index)
        chinese_indices=df1.index.strftime('%Y-%m-%d')
        # tt_month88.index = pd.to_datetime(tt_month88.index)
        # chinese_indices = tt_season88.index.strftime('%Y-%m-%d').tolist()
        df1.index = chinese_indices
        df1.replace(0, float('nan'), inplace=True)

    # 指数全部连续合约
    for j in letterssll:
#         process_data(j, '99')
#         df2 = process_data(j, '99')
        df2 = process_data(j, '8888')#指数合约
        df2.index = pd.to_datetime(df2.index)
        chinese_indices=df2.index.strftime('%Y-%m-%d')
        # tt_month88.index = pd.to_datetime(tt_month88.index)
        # chinese_indices = tt_season88.index.strftime('%Y-%m-%d').tolist()
        df2.index = chinese_indices
        df2.replace(0, float('nan'), inplace=True)
    return df1, df2
    
# 周线
def zlhy57week(future_list,valution_day):
    df1 = pd.DataFrame()  # DataFrame to store results of '88' suffix
    df2 = pd.DataFrame() 
    
    def year13before (date):
        from datetime import datetime, timedelta

        # 将日期字符串转换为 datetime 对象
        date_str = date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        # 将年份减去13
        new_year = date_obj.year - 12

        # 构造新的 datetime 对象
        new_date_obj = datetime(new_year, date_obj.month, date_obj.day)

        # 将结果转换为字符串并用中文返回
        result = new_date_obj.strftime('%Y-%m-%d')
    #     print(result)
        return result
    
    def get_month_start(date_time):
        import datetime
        return date_time.strftime('%Y-%m') + '-01'

    def find_last_trading_week(trade_list):
        import datetime
        friday_trading_days = []

        for trade_day in trade_list:
            if trade_day.weekday() == 4:  # Check if the day is a Friday
                friday_trading_days.append(trade_day)

        # Add the last element of trade_list to friday_trading_days
        friday_trading_days.append(trade_list[-1])

        #     print(friday_trading_days)
        return friday_trading_days[-57:]

    
    trade_day=get_trade_days(year13before(valution_day), valution_day)
#     trade_dayall=last_trade_day(trade_day)
    find_last_trading_week=find_last_trading_week(trade_day)
#     print('trade_day_jd',trade_day_jd)
#     return trade_day_jd

    letterssll=future_list
    
    def get_week_start(date):
        import datetime
        days_to_subtract = date.weekday()
    #     print('days_to_subtract',days_to_subtract)
        # Subtract the number of days to get to Monday
        monday_date = date - datetime.timedelta(days=days_to_subtract)
        return monday_date
    
    # 获得期货品种的后缀
    def future_hz(future):
        string=get_dominant_future(future)
        string = string.split('.')[1]
        return string

    def process_data(j, suffix):
#         ff = pd.DataFrame(columns=['开盘价', '最高价', '最低价', '收盘价', '季持仓量', '季成交量', '季成交金额'])
#         ff = pd.DataFrame(columns=['开盘价', '最高价', '最低价', '收盘价', '月持仓量', '月成交量', '月成交金额'])
        ff = pd.DataFrame(columns=['品种时间','开盘价', '最高价', '最低价', '收盘价', '周持仓量', '周成交量', '周成交金额'])
        for i in range(len(find_last_trading_week)-1, -1, -1):
#             mm_year=get_price(j+suffix, start_date=get_week_start(find_last_trading_week[i]), end_date=find_last_trading_week[i],frequency='1d')
            mm_year=get_price(j+suffix+'.'+future_hz(j), start_date=get_week_start(find_last_trading_week[i]),\
                              end_date=find_last_trading_week[i],frequency='1d', \
                              fields=['open', 'close', 'high', 'low', 'volume', 'money','open_interest'])
            try:
                open_year = list(mm_year.open)[0]
            except:
                open_year = 0
            try:
                high_year = max(list(mm_year.high))
            except:
                high_year = 0
            try:
                low_year = min(list(mm_year.low))
            except:
                low_year = 0
            try:
                close_year = list(mm_year.close)[-1]
            except:
                close_year = 0
#             mm_year = get_price(j + suffix, start_date=get_quarter_start(trade_day_jd[i]), end_date=trade_day_jd[i], frequency='1d')
            try:
                open_interest_year = sum(mm_year.open_interest)
            except:
                open_interest_year = 0
            try:
                volume_year = sum(mm_year.volume)
            except:
                volume_year = 0
            try:
                total_turnover_year = sum(mm_year.money)
            except:
                total_turnover_year = 0
            series = pd.Series({
                '品种时间': j+str(find_last_trading_week[i]),
                '开盘价': open_year,
                '最高价': high_year,
                '最低价': low_year,
                '收盘价': close_year,
                '周持仓量': open_interest_year,
                '周成交量': volume_year,
                '周成交金额': total_turnover_year
            })
            ff.loc[find_last_trading_week[i]] = series
#         print(j + suffix, ff)
        return ff

    # 连续合约前复权平滑处理
    for j in letterssll:
#         process_data(j, '88')
#         df1 = process_data(j, '88')
        df1 = process_data(j, '9999')#主力连续合约
        df1.index = pd.to_datetime(df1.index)
        chinese_indices=df1.index.strftime('%Y-%m-%d')
        # tt_month88.index = pd.to_datetime(tt_month88.index)
        # chinese_indices = tt_season88.index.strftime('%Y-%m-%d').tolist()
        df1.index = chinese_indices
        df1.replace(0, float('nan'), inplace=True)

    # 指数全部连续合约
    for j in letterssll:
#         process_data(j, '99')
#         df2 = process_data(j, '99')
        df2 = process_data(j, '8888')#指数合约
        df2.index = pd.to_datetime(df2.index)
        chinese_indices=df2.index.strftime('%Y-%m-%d')
        # tt_month88.index = pd.to_datetime(tt_month88.index)
        # chinese_indices = tt_season88.index.strftime('%Y-%m-%d').tolist()
        df2.index = chinese_indices
        df2.replace(0, float('nan'), inplace=True)
    return df1, df2

def longshortajustyear(G14,G15,G13):
    if (G14 == "绝望" or G14 == "地狱") and G15 == "异常跌幅":
        result = "做多"
    elif (G14 == "狂欢" or G14 == "疯狂") and G15 == "异常涨幅":
        result = "做空"
    else:
        result = G13
    return result

def traderpsyyear(df):
    # 当前位置
    I13=df['收盘价'].tolist()[0]/df['收盘价'].tolist()[1]-1 
    # 地狱
    I12=min(df['收盘价'].pct_change(periods=-1)[1:7])*(1+0.191)
    # 绝望
    I11=min(df['收盘价'].pct_change(periods=-1)[1:7])
    # print('月度收益个股',len(df['收盘价'].pct_change(periods=-1)[1:7]))
    # 痛苦
    I10=mean(df['收盘价'].pct_change(periods=-1)[1:7][df['收盘价'].pct_change(periods=-1)[1:7] < 0])
    # 失落
    I9=mean(df['收盘价'].pct_change(periods=-1)[1:7][df['收盘价'].pct_change(periods=-1)[1:7] < 0])*0.6
    # 高兴
    I7=mean(df['收盘价'].pct_change(periods=-1)[1:7][df['收盘价'].pct_change(periods=-1)[1:7] > 0])*0.6
    # 兴奋
    I6=mean(df['收盘价'].pct_change(periods=-1)[1:7][df['收盘价'].pct_change(periods=-1)[1:7] > 0])
    # 狂欢
    I5=max(df['收盘价'].pct_change(periods=-1)[1:7][df['收盘价'].pct_change(periods=-1)[1:7] > 0])
    # 狂欢
    I4=max(df['收盘价'].pct_change(periods=-1)[1:7][df['收盘价'].pct_change(periods=-1)[1:7] > 0])


    if I13< 0 and abs(I13) > abs(I12):
        result = "地狱"
    elif I13 < 0 and abs(I13) > abs(I11):
        result = "绝望"
    elif I13 < 0 and abs(I13) > abs(I10):
        result = "痛苦"
    elif I13 < 0 and abs(I13) > abs(I9):
        result = "失落"
    elif I13 > 0 and I13 > I4:
        result = "疯狂"
    elif I13 > 0 and I13 > I5:
        result = "狂欢"
    elif I13 > 0 and I13 > I6:
        result = "兴奋"
    elif I13 > 0 and I13 > I7:
        result = "高兴"
    else:
        result = "一般"
#     print('result',result)
    return result
    
# 年度趋势基比价格分析
def yearbhs(df):
    def calculate_pct_hball(future_close, num):
        pct_hball = []
        if len(future_close) != num + 1:
            pct_hball = [np.nan] * (num + 1)
        else:
            for i in future_close[:num].tolist():
                pct_hball.append((i - future_close[-1]) / future_close[-1])
        return pct_hball

    def calculate_percentage(Y5, num):
        try:
            result = (1 + Y5) ** (1 / num) - 1
            return result * 100
        except:
            return np.nan
            
    def calculate_result(final_resultall):
        total_score = (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125
        )

        if total_score < 0.125:
            return "做多"
        elif total_score >= 0.5 and total_score < 0.875:
            return "做多"
        else:
            return "做空"

    final_resultall = []

    future_close = df['收盘价']
    future_pcthbfh = [calculate_percentage(i, 11) for i in calculate_pct_hball(future_close, 11)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    future_close = df['收盘价'][:9]
    future_pcthbfh = [calculate_percentage(i, 8) for i in calculate_pct_hball(future_close, 8)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    future_close = df['收盘价'][:6]
    future_pcthbfh = [calculate_percentage(i, 5) for i in calculate_pct_hball(future_close, 5)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    future_close = df['收盘价'][:4]
    future_pcthbfh = [calculate_percentage(i, 3) for i in calculate_pct_hball(future_close, 3)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    future_close = df['收盘价'][:3]
    future_pcthbfh = [calculate_percentage(i, 2) for i in calculate_pct_hball(future_close, 2)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    # print(final_resultall)
    return calculate_result(final_resultall)
    
# 年度趋势成交量分析
def yearcclhs(df):
    def calculate_result(final_resultall):
        if (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 < 0.125
        ):
            return "做多"
        elif (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 >= 0.5 and
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 < 0.875
        ):
            return "做多"
        else:
            return "做空"
    
    final_resultall = []
    months = [11, 8, 5, 3, 2]
    
    for month in months:
        future_pct = df['年持仓量'].pct_change(periods=-1)
        future_pct = future_pct[:month]
        monthzfzb = (future_pct >= 0).sum() / len(future_pct)
        
        if (monthzfzb >= 0.5 and monthzfzb <= 0.9) or monthzfzb <= 0.1:
            result = "做多"
        else:
            result = "做空"
        
        rounded_value = round(monthzfzb, 2)
        final_result = result + str(rounded_value)
        # print(f'{month}月', final_result)
        final_resultall.append(final_result)
    
    return calculate_result(final_resultall)
    
def zlhy13year(future_list,valution_day):
    df1 = pd.DataFrame()  # DataFrame to store results of '88' suffix
    df2 = pd.DataFrame() 
    
    def year13before (date):
        from datetime import datetime, timedelta

        # 将日期字符串转换为 datetime 对象
        date_str = date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        # 将年份减去13
        new_year = date_obj.year - 12

        # 构造新的 datetime 对象
        new_date_obj = datetime(new_year, date_obj.month, date_obj.day)

        # 将结果转换为字符串并用中文返回
        result = new_date_obj.strftime('%Y-%m-%d')
    #     print(result)
        return result

    def last_trade_day(trade_day):
        import datetime
        # 创建一个空的列表，用于存储每年的最后一个交易日
        result = []
        # 遍历trade_day列表
        for i in range(len(trade_day)):
            # 检查每个元素的类型，如果是datetime.date类型的，就用strftime()函数将其转换为字符串类型的
            if isinstance(trade_day[i], datetime.date):
                formatted_date = trade_day[i].strftime("%Y-%m-%d")
            else:
                formatted_date = trade_day[i]
            # 将每个元素转换为datetime对象，并获取其年份
            date = datetime.datetime.strptime(formatted_date, "%Y-%m-%d")
            year = date.year
            # 判断当前元素的年份是否与下一个元素的年份相同
            if i == len(trade_day) - 1:
                # 如果是最后一个元素，则直接添加到结果列表中
                result.append(formatted_date)
            else:
                # 如果不是最后一个元素，则检查下一个元素的类型，如果是datetime.date类型的，就用strftime()函数将其转换为字符串类型的
                if isinstance(trade_day[i+1], datetime.date):
                    formatted_next_date = trade_day[i+1].strftime("%Y-%m-%d")
                else:
                    formatted_next_date = trade_day[i+1]
                # 然后用strptime()函数解析下一个元素，并比较其年份与当前元素的年份是否相同
                if year != datetime.datetime.strptime(formatted_next_date, "%Y-%m-%d").year:
                    # 如果不同，则说明当前元素是该年份的最后一个交易日，将其添加到结果列表中
                    result.append(formatted_date)
        # 返回结果列表
        return result
#     trade_day=get_trading_dates(year13before(valution_day), valution_day)
    trade_day=get_trade_days(year13before(valution_day), valution_day)
    trade_dayall=last_trade_day(trade_day)
#     return trade_day

    letterssll=future_list
    def yearstart(date):
        date_str = date
        new_date_str = date_str[:5] + '01' +'-01'
        # print(new_date_str)
        return new_date_str
    
    # 获得期货品种的后缀
    def future_hz(future):
        string=get_dominant_future(future)
        string = string.split('.')[1]
        return string

    def process_data(j, suffix):
        ff = pd.DataFrame(columns=['品种时间','开盘价', '最高价', '最低价', '收盘价', '年持仓量', '年成交量', '年成交金额'])
#         futrue_timeall=[]
        for i in range(len(trade_dayall)-1, -1, -1):
            mm_year=get_price(j+suffix+'.'+future_hz(j), start_date=yearstart(trade_dayall[i]), end_date=trade_dayall[i],\
                              frequency='1d', fields=['open', 'close', 'high', 'low', 'volume', 'money','open_interest'])
            try:
#                 open_year = list(mm.open)[0]
                open_year = list(mm_year.open)[0]
            except:
                open_year = 0
            try:
                high_year = max(list(mm_year.high))
            except:
                high_year = 0
            try:
                low_year = min(list(mm_year.low))
            except:
                low_year = 0
            try:
                close_year = list(mm_year.close)[-1]
            except:
                close_year = 0
#             mm_year = get_price(j + suffix, start_date=yearstart(trade_dayall[i]), end_date=trade_dayall[i], frequency='1d')
            try:
                open_interest_year = sum(mm_year.open_interest)
            except:
                open_interest_year = 0
            try:
                volume_year = sum(mm_year.volume)
            except:
                volume_year = 0
            try:
                total_turnover_year = sum(mm_year.money)
            except:
                total_turnover_year = 0
            series = pd.Series({
                '品种时间': j+str(trade_dayall[i]),
                '开盘价': open_year,
                '最高价': high_year,
                '最低价': low_year,
                '收盘价': close_year,
                '年持仓量': open_interest_year,
                '年成交量': volume_year,
                '年成交金额': total_turnover_year
            })
            ff.loc[trade_dayall[i]] = series
#         print(j + suffix, ff)
        return ff

    # 连续合约前复权平滑处理
    for j in letterssll:
#         process_data(j, '88')
#         df1 = df1.append(process_data(j, '88'))
        df1 = process_data(j, '9999')
        df1.replace(0, float('nan'), inplace=True)

    # 指数全部连续合约
    for j in letterssll:
#         process_data(j, '99')
#         df2 = df2.append(process_data(j, '99'))
        df2=process_data(j, '8888')
        df2.replace(0, float('nan'), inplace=True)
    return df1, df2
    
    
def yearzfzb(df):
    def calculate_result(final_resultall):
        if (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 < 0.125
        ):
            return "做多"
        elif (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 >= 0.5 and
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 < 0.875
        ):
            return "做多"
        else:
            return "做空"   
    def zfychs(future_pct, threshol_zf, threshol_df):
        if pd.isna(future_pct[0]):
            return np.nan
        elif future_pct[0] > 0: 
            if future_pct[0] - threshol_zf > 0:
                return '异常涨幅'
            else:
                return '正常区间'
        elif future_pct[0] < 0:
            if abs(future_pct[0]) - abs(threshol_df) > 0:
                return '异常跌幅'
            else:
                return '正常区间'
        else:
            return np.nan
            
    final_resultall = []
    months = [11, 8, 5, 3, 2]
    
    for month in months:
        future_pct = df['收盘价'].pct_change(periods=-1)
        future_pct = future_pct[:month]
        monthzfzb = (future_pct >= 0).sum() / len(future_pct)
        
        if (monthzfzb >= 0.5 and monthzfzb <= 0.9) or monthzfzb <= 0.1:
            result = "做多"
        else:
            result = "做空"
        
        rounded_value = round(monthzfzb, 2)
        final_result = result + str(rounded_value)
        # print(f'{month}年', final_result)
        final_resultall.append(final_result)
        
    #   判断是否异常
        if month==11:
#             print('future_pct',future_pct)
#             print('type(future_pct)',type(future_pct))
            # 计算阈值
            threshol_df = future_pct.quantile(0.2)#取20%上的数
            threshol_zf = future_pct.quantile(0.8)#取80%上的数
            # 当前涨幅
            # print('future_pctall',future_pct)
            # month_pctnow=future_pct[1]
            # print('month_pctnow',month_pctnow)

            # 判断跌幅阈值是否小于等于0
            if threshol_df <= 0:
                result_df = 0
            else:
                result_df = threshold

            # print('判断跌幅是否异常',result_df)
            
            # 判断涨幅阈值是否小于等于0
            if threshol_zf <= 0:
                result_zf = 0
            else:
                result_zf = threshol_zf
            g.pctycpdyear=zfychs(future_pct, threshol_zf, threshol_df)
        else:
#             print('not34')
            continue
    return calculate_result(final_resultall)
    
    
def longshortajust(G14,G15,G13):
    if (G14 == "绝望" or G14 == "地狱") and G15 == "异常跌幅":
        result = "做多"
    elif (G14 == "狂欢" or G14 == "疯狂") and G15 == "异常涨幅":
        result = "做空"
    else:
        result = G13
    return result
    
def traderpsy(df):
    # 当前位置
    I13=df['收盘价'].tolist()[0]/df['收盘价'].tolist()[1]-1 
    # 地狱
    I12=min(df['收盘价'].pct_change(periods=-1)[1:23])*(1+0.191)
    # 绝望
    I11=min(df['收盘价'].pct_change(periods=-1)[1:23])
    # 痛苦
    I10=mean(df['收盘价'].pct_change(periods=-1)[1:23][df['收盘价'].pct_change(periods=-1)[1:23] < 0])
    # 失落
    I9=mean(df['收盘价'].pct_change(periods=-1)[1:23][df['收盘价'].pct_change(periods=-1)[1:23] < 0])*0.6
    # 高兴
    I7=mean(df['收盘价'].pct_change(periods=-1)[1:23][df['收盘价'].pct_change(periods=-1)[1:23] > 0])*0.6
    # 兴奋
    I6=mean(df['收盘价'].pct_change(periods=-1)[1:23][df['收盘价'].pct_change(periods=-1)[1:23] > 0])
    # 狂欢
    I5=max(df['收盘价'].pct_change(periods=-1)[1:23][df['收盘价'].pct_change(periods=-1)[1:23] > 0])
    # 狂欢
    I4=max(df['收盘价'].pct_change(periods=-1)[1:23][df['收盘价'].pct_change(periods=-1)[1:23] > 0])


    if I13< 0 and abs(I13) > abs(I12):
        result = "地狱"
    elif I13 < 0 and abs(I13) > abs(I11):
        result = "绝望"
    elif I13 < 0 and abs(I13) > abs(I10):
        result = "痛苦"
    elif I13 < 0 and abs(I13) > abs(I9):
        result = "失落"
    elif I13 > 0 and I13 > I4:
        result = "疯狂"
    elif I13 > 0 and I13 > I5:
        result = "狂欢"
    elif I13 > 0 and I13 > I6:
        result = "兴奋"
    elif I13 > 0 and I13 > I7:
        result = "高兴"
    else:
        result = "一般"
#     print('result',result)
    return result
    
# 月度趋势基比价格分析
def monthbhs(df):
    def calculate_pct_hball(future_close, num):
        pct_hball = []
        if len(future_close) != num + 1:
            pct_hball = [np.nan] * (num + 1)
        else:
            for i in future_close[:num].tolist():
                pct_hball.append((i - future_close[-1]) / future_close[-1])
        return pct_hball

    def calculate_percentage(Y5, num):
        try:
            result = (1 + Y5) ** (1 / num) - 1
            return result * 100
        except:
            return np.nan

    def calculate_result(final_resultall):
        total_score = (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125
        )

        if total_score < 0.125:
            return "做多"
        elif total_score >= 0.5 and total_score < 0.875:
            return "做多"
        else:
            return "做空"

    final_resultall = []

    future_close = df['收盘价']
    future_pcthbfh = [calculate_percentage(i, 34) for i in calculate_pct_hball(future_close, 34)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    future_close = df['收盘价'][:26]
    future_pcthbfh = [calculate_percentage(i, 25) for i in calculate_pct_hball(future_close, 25)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    future_close = df['收盘价'][:14]
    future_pcthbfh = [calculate_percentage(i, 13) for i in calculate_pct_hball(future_close, 13)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    future_close = df['收盘价'][:8]
    future_pcthbfh = [calculate_percentage(i, 7) for i in calculate_pct_hball(future_close, 7)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    future_close = df['收盘价'][:4]
    future_pcthbfh = [calculate_percentage(i, 3) for i in calculate_pct_hball(future_close, 3)]
    result = '做多' if mean(future_pcthbfh) < future_pcthbfh[0] else '做空'
    final_resultall.append(result)

    # print(final_resultall)
    return calculate_result(final_resultall)
    
# 趋势成交量分析
def monthcclhs(df):
    def calculate_result(final_resultall):
        if (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 < 0.125
        ):
            return "做多"
        elif (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 >= 0.5 and
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 < 0.875
        ):
            return "做多"
        else:
            return "做空"
    # def zfychs(future_pct, threshol_zf, threshol_df):
    #     if pd.isna(future_pct[0]):
    #         return np.nan
    #     elif future_pct[0] > 0 and future_pct[0] - threshol_zf > 0:
    #         return '异常涨幅'
    #     elif future_pct[0] < 0 and abs(future_pct[0]) - abs(threshol_df) > 0:
    #         return '异常跌幅'
    #     else:
    #         return np.nan
    
    final_resultall = []
    months = [34, 25, 13, 7, 3]
    
    for month in months:
        future_pct = df['月持仓量'].pct_change(periods=-1)
        future_pct = future_pct[:month]
        monthzfzb = (future_pct >= 0).sum() / len(future_pct)
        
        if (monthzfzb >= 0.5 and monthzfzb <= 0.9) or monthzfzb <= 0.1:
            result = "做多"
        else:
            result = "做空"
        
        rounded_value = round(monthzfzb, 2)
        final_result = result + str(rounded_value)
        # print(f'{month}月', final_result)
        final_resultall.append(final_result)
    
    return calculate_result(final_resultall)

def monthzfzb(df):
    def calculate_result(final_resultall):
        if (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 < 0.125
        ):
            return "做多"
        elif (
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 >= 0.5 and
        (final_resultall[0][:2] == "做多") * 0.35 +
        (final_resultall[1][:2] == "做多") * 0.25 +
        (final_resultall[2][:2] == "做多") * 0.15 +
        (final_resultall[3][:2] == "做多") * 0.125 +
        (final_resultall[4][:2] == "做多") * 0.125 < 0.875
        ):
            return "做多"
        else:
            return "做空"   
    def zfychs(future_pct, threshol_zf, threshol_df):
        if pd.isna(future_pct[0]):
            return np.nan
        elif future_pct[0] > 0: 
            if future_pct[0] - threshol_zf > 0:
                return '异常涨幅'
            else:
                return '正常区间'
        elif future_pct[0] < 0:
            if abs(future_pct[0]) - abs(threshol_df) > 0:
                return '异常跌幅'
            else:
                return '正常区间'
        else:
            return np.nan
            
    final_resultall = []
    months = [34, 25, 13, 7, 3]
    
    for month in months:
        future_pct = df['收盘价'].pct_change(periods=-1)
        future_pct = future_pct[:month]
        monthzfzb = (future_pct >= 0).sum() / len(future_pct)
        
        if (monthzfzb >= 0.5 and monthzfzb <= 0.9) or monthzfzb <= 0.1:
            result = "做多"
        else:
            result = "做空"
        
        rounded_value = round(monthzfzb, 2)
        final_result = result + str(rounded_value)
        # print(f'{month}月', final_result)
        final_resultall.append(final_result)
        
    #   判断是否异常
        if month==34:
#             print('future_pct',future_pct)
#             print('type(future_pct)',type(future_pct))
            # 计算阈值
            threshol_df = future_pct.quantile(0.2)#取20%上的数
            threshol_zf = future_pct.quantile(0.8)#取80%上的数
            # 当前涨幅
            # print('future_pctall',future_pct)
            # month_pctnow=future_pct[1]
            # print('month_pctnow',month_pctnow)

            # 判断跌幅阈值是否小于等于0
            if threshol_df <= 0:
                result_df = 0
            else:
                result_df = threshold

            # print('判断跌幅是否异常',result_df)
            
            # 判断涨幅阈值是否小于等于0
            if threshol_zf <= 0:
                result_zf = 0
            else:
                result_zf = threshol_zf

            # print('判断涨幅是否异常',result_zf)
            # print('判断涨幅是否异常',zfychs(future_pct, threshol_zf, threshol_df))
            g.pctycpd=zfychs(future_pct, threshol_zf, threshol_df)
            # df_yc=pd.DataFrame(future_pct)
            # df_yc = pd.DataFrame({'pct': future_pct})
            # df_yc['zfyz'] = df_yc['pct'].apply(lambda x: np.nan if pd.isna(x) else '异常涨幅' if x > 0 and x - threshol_zf > 0 \
            #                              else '异常跌幅' if x < 0 and abs(x) - abs(threshol_df) > 0 else np.nan)
            # print('df_yc',df_yc)
        else:
#             print('not34')
            continue
    # print('calculate_result(final_resultall)',calculate_result(final_resultall))
    # print('type(calculate_result(final_resultall))',type(calculate_result(final_resultall)))
    # if calculate_result(final_resultall) == "做多":
    #     print('趋势周期分析总结：做多')
    #     g.flag = 1
    # else:
    #     print('趋势周期分析总结：做空')
    #     g.flag = -1
    # print('g.flag',g.flag)
    
    return calculate_result(final_resultall)
    
def futurehs(date):
    import datetime
    valution_day=date
    # 获得13年价格开盘价、最高价、最低价、收盘价、成交量
    # df=all_instruments('Future')
    df=get_all_securities(types=['futures'])
    # 获得当前可交易的品种
    # df=df[df.end_date>valution_day]
    df['end_date'] = df['end_date'].apply(lambda x: x.strftime('%Y-%m-%d'))
    df=df[df.end_date>valution_day]
    df
    my_list = list(df.index)
    letterssll = []
    for string in my_list:
    #     print('word',word)
        string = string.split('.')[0]
        letters = ''.join(re.findall(r'[a-zA-Z]', string))
        letterssll.append(letters)
    #     letterssll=set(letterssll)
        letterssll = list(set(letterssll))
    return letterssll

# 获取月度数据
# 月线
def zlhy36month(future_list,valution_day):
    df1 = pd.DataFrame()  # DataFrame to store results of '88' suffix
    df2 = pd.DataFrame() 
    
    def year13before (date):
        from datetime import datetime, timedelta

        # 将日期字符串转换为 datetime 对象
        date_str = date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')

        # 将年份减去13
        new_year = date_obj.year - 12

        # 构造新的 datetime 对象
        new_date_obj = datetime(new_year, date_obj.month, date_obj.day)

        # 将结果转换为字符串并用中文返回
        result = new_date_obj.strftime('%Y-%m-%d')
    #     print(result)
        return result
    
    def get_month_start(date_time):
        import datetime
        return date_time.strftime('%Y-%m') + '-01'

   # 23季价格
    def last_trade_day_month(trade_list):
        # 第一步：创建一个新的列表，其中包含每个月的最后一个交易日
        last_trading_days = []
        current_month = None
        for date in trade_list:
            if current_month is None:
                current_month = date.month
                last_trading_day = date
            elif date.month != current_month:
                last_trading_days.append(last_trading_day)
                current_month = date.month
                last_trading_day = date
            else:
                last_trading_day = date

        # 添加最后一个月的最后一个交易日
        last_trading_days.append(last_trading_day)

        # 第二步：从新列表中提取最近的48个元素
        recent_48_days = last_trading_days[-36:]
        return recent_48_days
    
#     trade_day=get_trading_dates(year13before(valution_day), valution_day, market='cn')
    trade_day=get_trade_days(year13before(valution_day), valution_day)
#     trade_dayall=last_trade_day(trade_day)
    last_trade_day_month=last_trade_day_month(trade_day)
#     print('trade_day_jd',trade_day_jd)
#     return trade_day_jd

    letterssll=future_list
    def yearstart(date):
        date_str = date
        new_date_str = date_str[:5] + '01' +'-01'
        # print(new_date_str)
        return new_date_str
    
    # 获得期货品种的后缀
    def future_hz(future):
        string=get_dominant_future(future)
        string = string.split('.')[1]
        return string

    def process_data(j, suffix):
#         ff = pd.DataFrame(columns=['开盘价', '最高价', '最低价', '收盘价', '季持仓量', '季成交量', '季成交金额'])
        ff = pd.DataFrame(columns=['品种时间','开盘价', '最高价', '最低价', '收盘价', '月持仓量', '月成交量', '月成交金额'])
        for i in range(len(last_trade_day_month)-1, -1, -1):
#             mm = get_price(j + suffix, start_date=trade_day_jd[i], end_date=trade_day_jd[i], frequency='1d')
#             mm_year = get_price(j + suffix, start_date=get_quarter_start(trade_day_jd[i]), end_date=trade_day_jd[i], frequency='1d')
            mm_year=get_price(j+suffix+'.'+future_hz(j), start_date=get_month_start(last_trade_day_month[i]),\
                              end_date=last_trade_day_month[i],frequency='1d', \
                              fields=['open', 'close', 'high', 'low', 'volume', 'money','open_interest'])
            try:
                open_year = list(mm_year.open)[0]
            except:
                open_year = 0
            try:
                high_year = max(list(mm_year.high))
            except:
                high_year = 0
            try:
                low_year = min(list(mm_year.low))
            except:
                low_year = 0
            try:
                close_year = list(mm_year.close)[-1]
            except:
                close_year = 0
#             mm_year = get_price(j + suffix, start_date=get_quarter_start(trade_day_jd[i]), end_date=trade_day_jd[i], frequency='1d')
            try:
                open_interest_year = sum(mm_year.open_interest)
            except:
                open_interest_year = 0
            try:
                volume_year = sum(mm_year.volume)
            except:
                volume_year = 0
            try:
                total_turnover_year = sum(mm_year.money)
            except:
                total_turnover_year = 0
            series = pd.Series({
                '品种时间': j+str(last_trade_day_month[i]),
                '开盘价': open_year,
                '最高价': high_year,
                '最低价': low_year,
                '收盘价': close_year,
                '月持仓量': open_interest_year,
                '月成交量': volume_year,
                '月成交金额': total_turnover_year
            })
            ff.loc[last_trade_day_month[i]] = series
#         print(j + suffix, ff)
        return ff

    # 连续合约前复权平滑处理
    for j in letterssll:
#         process_data(j, '88')
        df1 = process_data(j, '9999')#主力连续合约
        df1.index = pd.to_datetime(df1.index)
        chinese_indices=df1.index.strftime('%Y-%m-%d')
        # tt_month88.index = pd.to_datetime(tt_month88.index)
        # chinese_indices = tt_season88.index.strftime('%Y-%m-%d').tolist()
        df1.index = chinese_indices
        df1.replace(0, float('nan'), inplace=True)

    # 指数全部连续合约
    for j in letterssll:
#         process_data(j, '99')
        df2 = process_data(j, '8888')#指数合约
        df2.index = pd.to_datetime(df2.index)
        chinese_indices=df2.index.strftime('%Y-%m-%d')
        # tt_month88.index = pd.to_datetime(tt_month88.index)
        # chinese_indices = tt_season88.index.strftime('%Y-%m-%d').tolist()
        df2.index = chinese_indices
        df2.replace(0, float('nan'), inplace=True)
    return df1, df2
    
## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    # 判断是否建仓
    # 三分之一法
    # 获得主力合约
    f1=get_dominant_future('IF')
    log.info('IF对应期货主力合约为',f1)
    # df_01=attribute_history(f1,1,'1m',fields='close')['close'][0]
    df_01=get_close_price(f1, 1, '1m')
    print('现价',df_01)
    # print('现价',type(df_01))
    # 目标价
    # 1.先获得月度支撑位压力位
    # 支撑位
    # print('g.future8888month',g.future8888month)
    monthzzw=calculate_monthzzw(df_01,g.future8888month,14,\
                  calculate_weekzzw(df_01,g.future8888week,22,\
                 calculate_dayzzw(df_01,g.future8888day,55,\
                calculate_hourzzw(df_01,g.future8888hour,89,\
                 calculate_halfhourzzw(df_01,g.future8888halfhour,145)),\
                calculate_halfhourzzw(df_01,g.future8888halfhour,145)),\
                 calculate_hourzzw(df_01,g.future8888hour,89,\
                 calculate_halfhourzzw(df_01,g.future8888halfhour,145)),\
                 calculate_halfhourzzw(df_01,g.future8888halfhour,145)),\
                  calculate_dayzzw(df_01,g.future8888day,55,\
                calculate_hourzzw(df_01,g.future8888hour,89,\
                 calculate_halfhourzzw(df_01,g.future8888halfhour,145)),\
                calculate_halfhourzzw(df_01,g.future8888halfhour,145)),\
                  calculate_hourzzw(df_01,g.future8888hour,89,\
                 calculate_halfhourzzw(df_01,g.future8888halfhour,145)),\
                  calculate_halfhourzzw(df_01,g.future8888halfhour,145))
    print('monthzzw',monthzzw)
    
    # 阻力位
    # print('g.future8888month',g.future8888month)
    monthzlw=calculate_monthzlw(df_01,g.future8888month,14,\
                  calculate_weekzlw(df_01,g.future8888week,22,\
                 calculate_dayzlw(df_01,g.future8888day,55,\
                calculate_hourzlw(df_01,g.future8888hour,89,\
                 calculate_halfhourzlw(df_01,g.future8888halfhour,145)),\
                calculate_halfhourzlw(df_01,g.future8888halfhour,145)),\
                 calculate_hourzlw(df_01,g.future8888hour,89,\
                 calculate_halfhourzlw(df_01,g.future8888halfhour,145)),\
                 calculate_halfhourzlw(df_01,g.future8888halfhour,145)),\
                  calculate_dayzlw(df_01,g.future8888day,55,\
                calculate_hourzlw(df_01,g.future8888hour,89,\
                 calculate_halfhourzlw(df_01,g.future8888halfhour,145)),\
                calculate_halfhourzlw(df_01,g.future8888halfhour,145)),\
                  calculate_hourzlw(df_01,g.future8888hour,89,\
                 calculate_halfhourzlw(df_01,g.future8888halfhour,145)),\
                  calculate_halfhourzlw(df_01,g.future8888halfhour,145))
    print('monthzlw',monthzlw)
    
    # 判断是否建仓
    result=g.resultjustmonth
    if result=='做多':
        zyw=monthzlw
        print('做多当前价',df_01)
        print('做多止盈位(目标位)',zyw)
        zsw=df_01+df_01*zsbfblong(g.future8888month,str(context.previous_date))
        print('做多止损位',zsw)
    if result=='做空':
        zyw=monthzzw
        print('做空当前价',df_01)
        print('做空止盈位（目标位）',zyw)
        # zsw=df_01+df_01*zsbfbshort(g.future8888month,str(context.previous_date.date()))
        zsw=df_01+df_01*zsbfbshort(g.future8888month,str(context.previous_date))
        print('做空止损位',zsw)
        print('单位目标盈利额',abs((zyw-df_01)*g.future_Contract_Size['IF']))
        print('单位目标盈利百分比',abs((zyw-df_01)*g.future_Contract_Size['IF'])/(df_01*g.future_Contract_Size['IF']*g.futrue_bzj['IF']))
        print('单位最大亏损额',abs((zsw-df_01)*g.future_Contract_Size['IF']))
        print('单位止损亏损百分比',abs((zsw-df_01)*g.future_Contract_Size['IF'])/(df_01*g.future_Contract_Size['IF']*g.futrue_bzj['IF']))
        # print("建议开仓") if (abs((zyw-df_01)*future_Contract_Size['IF'])/(df_01*future_Contract_Size['IF']*futrue_bzj['IF']) / (abs((zsw-df_01)*future_Contract_Size['IF'])/(df_01*future_Contract_Size['IF']*futrue_bzj['IF']))) >= (3 / 1) else print("不合格")
        if (abs((zyw-df_01)*g.future_Contract_Size['IF'])/(df_01*g.future_Contract_Size['IF']*g.futrue_bzj['IF']) / (abs((zsw-df_01)*\
        g.future_Contract_Size['IF'])/(df_01*g.future_Contract_Size['IF']*g.futrue_bzj['IF']))) >= (3 / 1):
            print("建议开仓") 
            g.targetfuture['IF']=result
            print('g.targetfuture',g.targetfuture)
        else:
            print("不合格")
        #  g.targetfuture
    ## 交易
    trade(context)
    
def trade(context):
    g.targetfuture={'IF':'做多','AU':'做空','RB':'做多'}
    cash_limit = context.portfolio.total_value /len(g.targetfuture)#g.risk_factor = 0.0002
    # print('cash_limit',cash_limit)
    hold_future_s = context.portfolio.short_positions.keys()
    hold_future_l = context.portfolio.long_positions.keys()
    # dom_code = get_dominant_future('IF', date=context.current_dt)
    # print('dom_code',dom_code)
    # if dom_code not in hold_future_l:
    #     try:
            
    #         # num_h = math.floor(cash_limit / atr)
    #         #cash_limit = context.portfolio.total_value * g.risk_factor
    #         # atr = np.mean(np.max(np.vstack((atr_high, atr_close)), axis=0) - np.min(np.vstack((atr_close, atr_low)), axis=0))
    #         #vstack 按垂直方向（行顺序）堆叠数组构成一个新的数组
    #         # print('long', atr, num_h, dom_code)
    #         order_target(dom_code,1,side='long')
    #         # g.high[dom_code] = close_prices[-1]
    #     except:
    #         print('some went wrong')
    for v, k in g.targetfuture.items():
        print(v)
        print(k)
        dom_code = get_dominant_future(v, date=context.current_dt)
        pricenow=get_close_price(dom_code, 1, '1m')
        print('pricenow1',pricenow)
        if k=='做多':
            # order_target(dom_code,1,side='long')
            # tradenum=
            # order_target_value(dom_code,cash_limit, side='long')
            order_target(dom_code,get_amount(pricenow,cash_limit,v),side='long')
        if k=='做空':
            # print('pricenow1',pricenow)
            if dom_code in hold_future_l:
                order_target_value(dom_code,0,side='long')
            else:
                if dom_code not in hold_future_s:
                       
                    # num_h = math.floor(cash_limit / atr)
                    # print('short', atr, num_h, dom_code)
                    order_target(dom_code,get_amount(pricenow,cash_limit,v),side='short')
            
def get_amount(price,money,future_symbol):
    future_coef_list = {'A':10, 'AG':15, 'AL':5, 'AU':1000,
                        'B':10, 'BB':500, 'BU':10, 'C':10, 
                        'CF':5, 'CS':10, 'CU':5, 'ER':10, 
                        'FB':500, 'FG':20, 'FU':50, 'GN':10, 
                        'HC':10, 'I':100, 'IC':200, 'IF':300, 
                        'IH':300, 'J':100, 'JD':5, 'JM':60, 
                        'JR':20, 'L':5, 'LR':10, 'M':10, 
                        'MA':10, 'ME':10, 'NI':1, 'OI':10, 
                        'P':10, 'PB':5, 'PM':50, 'PP':5, 
                        'RB':10, 'RI':20, 'RM':10, 'RO':10, 
                        'RS':10, 'RU':10, 'SF':5, 'SM':5, 
                        'SN':1, 'SR':10, 'T':10000, 'TA':5, 
                        'TC':100, 'TF':10000, 'V':5, 'WH':20, 
                        'WR':10, 'WS':50, 'WT':10, 'Y':10, 
                        'ZC':100, 'ZN':5}
    futrue_bzj={'IF': 0.08, 'IC': 0.08, 'IM': 0.08, 'IH': 0.08, 'TS': 0.005, 'TF': 0.01, 'T': 0.02, 'SA': 0.05, 'AU': 0.04, 'J': 0.05, 'RB': 0.05, \
    'UR': 0.08, 'I': 0.0005, 'ru': 0.1, 'SC': 0.05, 'p': 0.08, 'AG': 0.04, 'TL': 0.035, 'TA': 0.05, 'ZC': 0.05, 'WH': 0.05, 'RI': 0.05, 'LR': 0.05, \
    'PM': 0.05, 'CY': 0.05, 'FG': 0.05, 'MA': 0.05, 'SR': 0.05, 'PF': 0.05, 'SF': 0.05, 'JR': 0.05, 'CJ': 0.07, 'PK': 0.05, 'AP': 0.07, 'OI': 0.05, \
    'RS': 0.05, 'RM': 0.05, 'CF': 0.05, 'SM': 0.05, 'NR': 0.07, 'LU': 0.08, 'BC': 0.05, 'SI': 0.05, 'SS': 0.05, 'RU': 0.05, 'AO': 0.05, 'BU': 0.04,\
    'PB': 0.05, 'CU': 0.05, 'AL': 0.05, 'ZN': 0.05, 'SN': 0.05, 'NI': 0.05, 'HC': 0.04, 'FU': 0.08, 'SP': 0.04, 'WR': 0.07, 'PG': 0.05, 'V': 0.05, \
    'EG': 0.05, 'L': 0.05, 'P': 0.05, 'JM': 0.05, 'C': 0.05, 'CS': 0.05, 'LH': 0.05, 'RR': 0.05, 'FB': 0.05, 'PP': 0.05, 'BB': 0.05, 'EB': 0.05,\
    'A': 0.05, 'B': 0.05, 'Y': 0.05, 'M': 0.05, 'JD': 0.05}
    return floor(money/(futrue_bzj[future_symbol]*future_coef_list[future_symbol]*price))            

def is_last_monthday(date):
    import datetime

    valuation_day1 = date
    valuation_day1 = datetime.datetime.strptime(valuation_day1, '%Y-%m-%d')
    new_day = valuation_day1 + datetime.timedelta(days=50)

    new_day.strftime('%Y-%m-%d')
    # new_day
    trade_day=get_trade_days(datetime.datetime.strptime(date[:7]+ '-01', '%Y-%m-%d'), new_day)
#     print('first',date[:7]+ '-01')
#     print('trade_day',trade_day)

    # 获取valuation_day所在月份
    valuation_month = pd.to_datetime(valuation_day1).strftime('%Y-%m')

    # 获取当月的所有交易日
    monthly_trade_day = trade_day[pd.to_datetime(trade_day).strftime('%Y-%m') == valuation_month]
#     print('monthly_trade_day',monthly_trade_day)

    # 判断valuation_day是否是当月的最后一个交易日
    is_last_trade_day = valuation_day1.strftime('%Y-%m-%d') == monthly_trade_day.max().strftime('%Y-%m-%d')
#     print('valuation_day1',valuation_day1)
#     print('type(valuation_day1)',type(valuation_day1))
#     print('valuation_day2',monthly_trade_day.max().strftime('%Y-%m-%d'))
#     print('typevaluation_day2',type(monthly_trade_day.max().strftime('%Y-%m-%d')))

    return is_last_trade_day

# 简洁版
def zsbfblong(df,date):
    resultall = []
#     判断评估日是否是当月的最后一个交易日
    if is_last_monthday(date):
         # 计算不同周期的均值
        for window in [3, 5, 8]:
            diff = df['最高价'] - df['最高价'].shift(1)
            rolling_mean = diff.rolling(window=window).mean()
            result = rolling_mean.shift(-window) / df['最高价']
            resultall.append(result[result < 0].mean())
    #         print(f'{window}周期均值', result[result < 0].mean())

        # 计算所有周期的平均值
        average = np.mean(np.array(resultall))
    #     print('resultall', resultall)
    #     print(average)

        # 计算止损百分比
    #     print('止损百分比', average * 0.7)
        return average * 0.7
    else:
        # 计算不同周期的均值
        for window in [3, 5, 8]:
            diff = df[1:]['最高价'] - df[1:]['最高价'].shift(1)
            rolling_mean = diff.rolling(window=window).mean()
            result = rolling_mean.shift(-window) / df[1:]['最高价']
            resultall.append(result[result < 0].mean())
    #         print(f'{window}周期均值', result[result < 0].mean())

        # 计算所有周期的平均值
        average = np.mean(np.array(resultall))
    #     print('resultall', resultall)
    #     print(average)

        # 计算止损百分比
    #     print('止损百分比', average * 0.7)
        return average * 0.7

def zsbfbshort(df,date):
    resultall = []
#     判断评估日是否是当月的最后一个交易日
    if is_last_monthday(date):
        # 计算不同周期的均值
        for window in [3, 5, 8]:
    #         print('window',window)
            diff = df['最低价'] - df['最低价'].shift(1)
            rolling_mean = diff.rolling(window=window).mean()
            result = rolling_mean.shift(-window) / df['最低价']
    #         print('result',result)
            resultall.append(result[result > 0].mean())
    #         print(f'{window}周期均值', result[result > 0].mean())

        # 计算所有周期的平均值
        average = np.mean(np.array(resultall))
    #     print('resultall', resultall)
    #     print(average)

        # 计算止损百分比
    #     print('止损百分比', average * 0.7)
        return average * 0.7
    else:
        # 计算不同周期的均值
        for window in [3, 5, 8]:
    #         print('window',window)
            diff = df[1:]['最低价'] - df[1:]['最低价'].shift(1)
            rolling_mean = diff.rolling(window=window).mean()
            result = rolling_mean.shift(-window) / df[1:]['最低价']
    #         print('result',result)
            resultall.append(result[result > 0].mean())
    #         print(f'{window}周期均值', result[result > 0].mean())

        # 计算所有周期的平均值
        average = np.mean(np.array(resultall))
    #     print('resultall', resultall)
    #     print(average)

        # 计算止损百分比
    #     print('止损百分比', average * 0.7)
        return average * 0.7
        
# def zsbfblong(df):
#     resultall = []
# #     判断评估日是否是当月的最后一个交易日

#     # 计算不同周期的均值
#     for window in [3, 5, 8]:
#         diff = df[1:]['最高价'] - df[1:]['最高价'].shift(1)
#         rolling_mean = diff.rolling(window=window).mean()
#         result = rolling_mean.shift(-window) / df[1:]['最高价']
#         resultall.append(result[result < 0].mean())
# #         print(f'{window}周期均值', result[result < 0].mean())

#     # 计算所有周期的平均值
#     average = np.mean(np.array(resultall))
# #     print('resultall', resultall)
# #     print(average)

#     # 计算止损百分比
# #     print('止损百分比', average * 0.7)
#     return average * 0.7

# def zsbfbshort(df):
#     resultall = []
# #     判断评估日是否是当月的最后一个交易日

#     # 计算不同周期的均值
#     for window in [3, 5, 8]:
# #         print('window',window)
#         diff = df[1:]['最低价'] - df[1:]['最低价'].shift(1)
#         rolling_mean = diff.rolling(window=window).mean()
#         result = rolling_mean.shift(-window) / df[1:]['最低价']
# #         print('result',result)
#         resultall.append(result[result > 0].mean())
# #         print(f'{window}周期均值', result[result > 0].mean())

#     # 计算所有周期的平均值
#     average = np.mean(np.array(resultall))
# #     print('resultall', resultall)
# #     print(average)

#     # 计算止损百分比
# #     print('止损百分比', average * 0.7)
#     return average * 0.7
    
def calculate_zlw(price, df, num, max_values):
    value = 0
    high = max(df['最高价'][:num])
    low = min(df['最低价'][:num])
    diff = high - low
    T_values = [high + 0.191 * diff,
                high,
                high - 0.191 * diff,
                high - 0.382 * diff,
                high - 0.5 * diff,
                high - 0.618 * diff,
                high - 0.809 * diff,
                low,
                low - 0.191 * diff]
    for i in range(len(T_values) - 1):
        if price > T_values[i+1] and price < T_values[i]:
            value = round(T_values[i], 2)
            break
    else:
        value = np.nan
    return max([value] + max_values[:num])

def calculate_monthzlw(price, df, num, value2, value3, value4, value5):
    return calculate_zlw(price, df, num, [value2, value3, value4, value5])

def calculate_weekzlw(price, df, num, value2, value3, value4):
    return calculate_zlw(price, df, num, [value2, value3, value4])

def calculate_dayzlw(price, df, num, value2, value3):
    return calculate_zlw(price, df, num, [value2, value3])

def calculate_hourzlw(price, df, num, value2):
    return calculate_zlw(price, df, num, [value2])

def calculate_halfhourzlw(price, df, num):
    return calculate_zlw(price, df, num, [])

def calculate_zzw(price, df, num, min_values):
#     print('price',price)
    value = 0
    high = max(df['最高价'][:num])
    low = min(df['最低价'][:num])
    diff = high - low
    T_values = [high + 0.191 * diff,
                high,
                high - 0.191 * diff,
                high - 0.382 * diff,
                high - 0.5 * diff,
                high - 0.618 * diff,
                high - 0.809 * diff,
                low,
                low - 0.191 * diff]
#     print('T_values',T_values)
    for i in range(len(T_values) - 1):
        if price > T_values[i+1] and price < T_values[i]:
            value = round(T_values[i+1], 2)
            break
    else:
        value = np.nan
    return min([value] + min_values[:num])

def calculate_monthzzw(price, df, num, value2, value3, value4, value5):
    return calculate_zzw(price, df, num, [value2, value3, value4, value5])

def calculate_weekzzw(price, df, num, value2, value3, value4):
    return calculate_zzw(price, df, num, [value2, value3, value4])

def calculate_dayzzw(price, df, num, value2, value3):
    return calculate_zzw(price, df, num, [value2, value3])

def calculate_hourzzw(price, df, num, value2):
    return calculate_zzw(price, df, num, [value2])

def calculate_halfhourzzw(price, df, num):
    return calculate_zzw(price, df, num, [])
    
# 获取前n个单位时间当时的收盘价
def get_close_price(security, n, unit='1d'):
    return attribute_history(security, n, unit, 'close')['close'][0]
    
## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')

########################## 获取期货合约信息，请保留 #################################
# 获取金融期货合约到期日
def get_CCFX_end_date(future_code):
    # 获取金融期货合约到期日
    return get_security_info(future_code).end_date


########################## 自动移仓换月函数 #################################
def position_auto_switch(context,pindex=0,switch_func=None, callback=None):
    """
    期货自动移仓换月。默认使用市价单进行开平仓。
    :param context: 上下文对象
    :param pindex: 子仓对象
    :param switch_func: 用户自定义的移仓换月函数.
        函数原型必须满足：func(context, pindex, previous_dominant_future_position, current_dominant_future_symbol)
    :param callback: 移仓换月完成后的回调函数。
        函数原型必须满足：func(context, pindex, previous_dominant_future_position, current_dominant_future_symbol)
    :return: 发生移仓换月的标的。类型为列表。
    """
    import re
    subportfolio = context.subportfolios[pindex]
    symbols = set(subportfolio.long_positions.keys()) | set(subportfolio.short_positions.keys())
    switch_result = []
    for symbol in symbols:
        match = re.match(r"(?P<underlying_symbol>[A-Z]{1,})", symbol)
        if not match:
            raise ValueError("未知期货标的：{}".format(symbol))
        else:
            dominant = get_dominant_future(match.groupdict()["underlying_symbol"])
            cur = get_current_data()
            symbol_last_price = cur[symbol].last_price
            dominant_last_price = cur[dominant].last_price
            if dominant > symbol:
                for positions_ in (subportfolio.long_positions, subportfolio.short_positions):
                    if symbol not in positions_.keys():
                        continue
                    else :
                        p = positions_[symbol]

                    if switch_func is not None:
                        switch_func(context, pindex, p, dominant)
                    else:
                        amount = p.total_amount
                        # 跌停不能开空和平多，涨停不能开多和平空。
                        if p.side == "long":
                            symbol_low_limit = cur[symbol].low_limit
                            dominant_high_limit = cur[dominant].high_limit
                            if symbol_last_price <= symbol_low_limit:
                                log.warning("标的{}跌停，无法平仓。移仓换月取消。".format(symbol))
                                continue
                            elif dominant_last_price >= dominant_high_limit:
                                log.warning("标的{}涨停，无法开仓。移仓换月取消。".format(symbol))
                                continue
                            else:
                                log.info("进行移仓换月：({0},long) -> ({1},long)".format(symbol, dominant))
                                order_target(symbol,0,side='long')
                                order_target(dominant,amount,side='long')
                                switch_result.append({"before": symbol, "after":dominant, "side": "long"})
                            if callback:
                                callback(context, pindex, p, dominant)
                        if p.side == "short":
                            symbol_high_limit = cur[symbol].high_limit
                            dominant_low_limit = cur[dominant].low_limit
                            if symbol_last_price >= symbol_high_limit:
                                log.warning("标的{}涨停，无法平仓。移仓换月取消。".format(symbol))
                                continue
                            elif dominant_last_price <= dominant_low_limit:
                                log.warning("标的{}跌停，无法开仓。移仓换月取消。".format(symbol))
                                continue
                            else:
                                log.info("进行移仓换月：({0},short) -> ({1},short)".format(symbol, dominant))
                                order_target(symbol,0,side='short')
                                order_target(dominant,amount,side='short')
                                switch_result.append({"before": symbol, "after": dominant, "side": "short"})
                                if callback:
                                    callback(context, pindex, p, dominant)
    return switch_result