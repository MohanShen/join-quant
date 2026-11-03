# Clone from JoinQuant
# postId: 064d79b22145f1987a5921495b5a18f0
# backtestId: ced9b6a38680ef7995ab8582c2848bce
# title: 求解

# 克隆自聚宽文章：https://www.joinquant.com/post/29785
# 标题：六因子商品期货策略
# 作者：dejiangwang

# 导入函数库
from jqdata import *

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
    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF8888.CCFX'或'IH1602.CCFX'是一样的）
    # 注意：before_open/open/close/after_close等相对时间不可用于有夜盘的交易品种，有夜盘的交易品种请指定绝对时间（如9：30）
      # 开盘前运行
    # run_weekly( before_market_open, 1, time='09:00')
    #   # 开盘时运行
    # run_weekly( market_open, 1, time='09:30')
    #   # 收盘后运行
    # run_weekly( after_market_close, 1, time='15:30')
    
    run_weekly( qualify_future, -1, time='09:30')
    
    run_weekly( basis_momentum, -1, time='09:30')
    
    run_weekly( roll_over_yield, -1, time='09:30')
    
    run_weekly( ware_house_factor, -1, time='09:30')
    
    run_weekly( compound_momentum, -1, time='09:30')
    
    run_weekly( pure_long_factor, -1, time='09:30')
    
    run_weekly( skew_factor, -1, time='09:30')
    
    run_weekly( lever, -1, time='09:30')
    
    run_weekly( market_open, -1, time='09:30')
    
      # 收盘后运行
    run_weekly( after_market_close, -1, time='15:30')
    
    
    
    
    

def qualify_future(context):
    # 选取符合流动性期货合约，上市满半年，前20交易日成交量均值大于1万手的主力合约
    all_future = get_all_securities(['futures']).reset_index()['index']
    tran_list = [ i[:-9] for i in all_future if '9999' in i and 'IC' not in i and 'IF' not in i and 'IH' not in i and 'T' not in i and 'TF' not in i and 'TS' not in i and 'SC' not in i and 'NR' not in i and 'LU' not in i]
    today = context.current_dt
    trade_day = get_trade_days(end_date=today, count=20)
    liquity_day = get_trade_days(end_date=today, count=120)
    today_date = trade_day[-1]
    main_tran_list = []
    volume_list = {}
    qualify_list = []
    qualify_main_list = []
    for future in tran_list:
        main_tran_list.append(get_dominant_future(future, date=today_date))
    main_tran_list = [i for i in main_tran_list if i != '']
    
    for future in main_tran_list:
        volume = get_price(future, frequency='daily', fields=['volume'], 
                                  start_date=trade_day[0], end_date=trade_day[-1]).mean()
        day_length = get_price(future, frequency='daily', fields=['volume'], start_date=liquity_day[0], end_date=liquity_day[-1]).dropna().shape[0]
        if volume.values > 10000 and day_length==120:
            volume_list[future] = volume
            qualify_main_list.append(future)
            qualify_list.append(future[:-9])
    g.qualify_main_list = qualify_main_list
    g.qualify_list = qualify_list



def basis_momentum(context):
    today = context.current_dt
    trade_day = get_trade_days(end_date=today, count=1)
    qualify_list = g.qualify_list
    qualify_main_list = g.qualify_main_list
    today_date = trade_day[-1]
    # 获取合格标的中近月合约近120日收益率
    near_ret_contrast_all = None
    for future in qualify_list:
        near_contrast = get_future_contracts(future, today_date)[1]
        near_contrast_price = get_price(near_contrast, frequency='daily', fields=['close'], 
                                  start_date=today_date-datetime.timedelta(days=120), end_date=today_date)
        near_ret_contrast = (near_contrast_price.iloc[-1]-near_contrast_price.iloc[0]) / near_contrast_price.iloc[0]
        near_ret_contrast.index = [future]
        near_ret_contrast_all = near_ret_contrast if near_ret_contrast is None else pd.concat([near_ret_contrast_all, near_ret_contrast], axis=0)
    
    # 获取合格标的主力合约近120日收益率
    main_ret_contrast_all = None
    for future in qualify_list:
        main_contrast = get_dominant_future(future, today_date)
        main_contrast_price = get_price(main_contrast, frequency='daily', fields=['close'], 
                                  start_date=today_date-datetime.timedelta(days=120), end_date=today_date)
        main_ret_contrast = (main_contrast_price.iloc[-1]-main_contrast_price.iloc[0]) / main_contrast_price.iloc[0]
        main_ret_contrast.index = [future]
        main_ret_contrast_all = main_ret_contrast if main_ret_contrast is None else pd.concat([main_ret_contrast_all, main_ret_contrast], axis=0)

    # 基差动量因子
    factor_momentum =  main_ret_contrast_all - near_ret_contrast_all
    factor_momentum.sort_values(ascending=False, inplace=True)
    factor_momentum = factor_momentum.dropna()
    g.factor_momentum = factor_momentum

# 获取当月指定日期
def get_delivery_day(str1):
    if str1[:-9] in ['AG','AL','AU','BU','CU','FU','HC','NI','PB','RB','RU','SN','WR','ZN','SP','SS']:
        periods = 11
    if str1[:-9] in ['AP','CF','CY','FG','JR','LR','MA','PM','RI','RM','OI','RS','SF','SM','SR','TA','WH','CJ','UR','SA']:
        periods = 10
    if str1[:-9] in ['A','B','BB','C','CS','FB','I','J','JD','JM','L','M','P','PP','V','Y','EG','EB','PG','RR']:
        periods = 10
    if str1[:-9] in ['ZC']:
        periods = 5
    a = str1[-9:-5]
    str_time = '20' + a + '01'
    now_tran_day = datetime.datetime.strptime(str_time, "%Y%m%d")
    next_year = (datetime.datetime.strptime(str_time, "%Y%m%d") + datetime.timedelta(days=31)).year
    next_month = (datetime.datetime.strptime(str_time, "%Y%m%d") + datetime.timedelta(days=31)).month
    next_tran_day = datetime.datetime.strptime(str(next_year) + str(next_month), "%Y%m")
    day = pd.bdate_range(now_tran_day, next_tran_day).floor('D')[periods-1]
    return day


def roll_over_yield(context):
    # 展期收益率因子
    qualify_list = g.qualify_list
    qualify_main_list = g.qualify_main_list
    today_date = context.current_dt
    trade_day = get_trade_days(end_date=today_date, count=20)
    roll_over = None
    for future in qualify_list:
        near_contrast = get_future_contracts(future, today_date)[0]
        far_contrast = get_future_contracts(future, today_date)[-1]
        near_contrast_price = get_price(near_contrast, frequency='daily', fields=['close'], 
                                start_date=trade_day[-1], end_date=trade_day[-1])
        far_contrast_price = get_price(far_contrast, frequency='daily', fields=['close'], 
                                start_date=trade_day[-1], end_date=trade_day[-1])
        far_day = get_delivery_day(far_contrast)
        near_day = get_delivery_day(near_contrast)
        ret = pd.DataFrame((np.log(near_contrast_price.values) - np.log(far_contrast_price.values))*(365/(far_day - near_day).days), index=[future])
        roll_over = ret if roll_over is None else pd.concat([roll_over, ret], axis=0)
    # 展期收益率因子
    roll_over.sort_values(by=0, ascending=False, inplace=True)
    g.roll_over = roll_over
    
def ware_house_factor(context):
    # 计算仓单因子
    qualify_list = g.qualify_list
    qualify_main_list = g.qualify_main_list
    now_date = context.current_dt
    tran_date_far = get_trade_days(end_date=now_date, count=100)[0]
    tran_date_near = get_trade_days(end_date=now_date, count=100)[-1]
    df_all = None
    for date in [tran_date_far, tran_date_near]:
        for future in qualify_list:
            df=finance.run_query(query(finance.FUT_WAREHOUSE_RECEIPT.day,
                finance.FUT_WAREHOUSE_RECEIPT.underlying_code,
                finance.FUT_WAREHOUSE_RECEIPT.warehouse_receipt_number).filter(finance.FUT_WAREHOUSE_RECEIPT.underlying_code==future,finance.FUT_WAREHOUSE_RECEIPT.day==date).order_by(finance.FUT_WAREHOUSE_RECEIPT.day.desc()))
            df_all = df if df_all is None else pd.concat([df_all, df], axis=0)
    ware_house_near = df_all.groupby(by=['day', 'underlying_code']).sum().loc[df_all['day'].values[-1]]
    ware_house_far = df_all.groupby(by=['day', 'underlying_code']).sum().loc[df_all['day'].values[0]]
    ware_house = ((ware_house_near - ware_house_far) / ware_house_far)
    ware_house = ware_house[ware_house != -1]
    ware_house.sort_values(by='warehouse_receipt_number', inplace=True)
    g.ware_house = ware_house
    
def compound_momentum(context):
    # 复合动量因子
    qualify_list = g.qualify_list
    qualify_main_list = g.qualify_main_list
    today_date = context.current_dt
    trade_day = get_trade_days(end_date=today_date, count=20)
    today_date = trade_day[-1]
    judge_list = None
    for future in qualify_list:
        main_contrast = get_dominant_future(future, today_date)
        main_contrast_price = get_price(main_contrast, frequency='daily', fields=['close'], 
                                  start_date=today_date-datetime.timedelta(days=60), end_date=today_date)
        main_contrast_return = main_contrast_price.rolling(2).apply(lambda x:(x[1]-x[0])/x[0]).dropna()
        main_contrast_return.columns = ['return']
        up_days = np.sum(main_contrast_return.values>0)
        down_days = np.sum(main_contrast_return.values<0)
        main_contrast_return_all = main_contrast_return.sum()
        judge = pd.DataFrame({main_contrast:up_days /(up_days + down_days) * (main_contrast_return_all)})
        judge_list = judge.T if judge_list is None else pd.concat([judge_list, judge.T], axis=0)
    judge_list.sort_values(by=['return'], ascending=False, inplace=True)
    g.judge_list = judge_list

def pure_long_factor(context):
    #净多头持仓变化率
    short_list = None
    long_list = None
    qualify_list = g.qualify_list
    qualify_main_list = g.qualify_main_list
    today_date = context.current_dt
    trade_day = get_trade_days(end_date=today_date, count=10)
    for future in qualify_main_list:
        q=query(finance.FUT_MEMBER_POSITION_RANK.day,
                finance.FUT_MEMBER_POSITION_RANK.code,
                finance.FUT_MEMBER_POSITION_RANK.rank_type,
                finance.FUT_MEMBER_POSITION_RANK.rank,
                finance.FUT_MEMBER_POSITION_RANK.member_name,
        finance.FUT_MEMBER_POSITION_RANK.indicator,)
        long_filter1 = q.filter(finance.FUT_MEMBER_POSITION_RANK.day==trade_day[-1], finance.FUT_MEMBER_POSITION_RANK.code==future, finance.FUT_MEMBER_POSITION_RANK.rank_type_ID==501002).order_by(finance.FUT_MEMBER_POSITION_RANK.day.desc()).limit(20)
        long1=finance.run_query(long_filter1)
        long1 = pd.DataFrame([long1['indicator'].sum()], index=[future], columns=[trade_day[-1]])
        long_filter2 = q.filter(finance.FUT_MEMBER_POSITION_RANK.day==trade_day[-10], finance.FUT_MEMBER_POSITION_RANK.code==future, finance.FUT_MEMBER_POSITION_RANK.rank_type_ID==501002).order_by(finance.FUT_MEMBER_POSITION_RANK.day.desc()).limit(20)
        long2=finance.run_query(long_filter2)
        long2 = pd.DataFrame([long2['indicator'].sum()], index=[future], columns=[trade_day[-10]])
        long = pd.concat([long1, long2], axis=1)
        long_list = long if long_list is None else pd.concat([long_list, long])
        short_filter1 = q.filter(finance.FUT_MEMBER_POSITION_RANK.day==trade_day[-1], finance.FUT_MEMBER_POSITION_RANK.code==future, finance.FUT_MEMBER_POSITION_RANK.rank_type_ID==501003).order_by(finance.FUT_MEMBER_POSITION_RANK.day.desc()).limit(20)
        short1=finance.run_query(short_filter1)
        short1 = pd.DataFrame([short1['indicator'].sum()], index=[future], columns=[trade_day[-1]])
        short_filter2 = q.filter(finance.FUT_MEMBER_POSITION_RANK.day==trade_day[-10], finance.FUT_MEMBER_POSITION_RANK.code==future, finance.FUT_MEMBER_POSITION_RANK.rank_type_ID==501003).order_by(finance.FUT_MEMBER_POSITION_RANK.day.desc()).limit(20)
        short2=finance.run_query(short_filter2)
        short2 = pd.DataFrame([short2['indicator'].sum()], index=[future], columns=[trade_day[-10]])
        short = pd.concat([short1, short2], axis=1)
        short_list = short if short_list is None else pd.concat([short_list, short])
    factor_pure_long = ((long_list.iloc[:, 0] - short_list.iloc[:, 0]) - (long_list.iloc[:, 1] - short_list.iloc[:, 1])) / (long_list.iloc[:, 0] + short_list.iloc[:, 0])
    factor_pure_long.sort_values(ascending=False, inplace=True)
    g.factor_pure_long = factor_pure_long

def skew_factor(context):
    # 收益率偏度
    skew_list = None
    qualify_list = g.qualify_list
    qualify_main_list = g.qualify_main_list
    today_date = context.current_dt
    trade_day = get_trade_days(end_date=today_date, count=10)
    for future in qualify_list:
        main_contrast = get_dominant_future(future, today_date)
        main_contrast_price = get_price(main_contrast, frequency='daily', fields=['close'], 
                                  start_date=trade_day[-1]-datetime.timedelta(days=60), end_date=trade_day[-1])
        main_contrast_ret = main_contrast_price.rolling(2).apply(lambda x:np.log(x[1]/x[0]))
        main_contrast_ret = main_contrast_ret.dropna()
        main_contrast_ret.columns = [future]
        main_contrast_ret_skew = main_contrast_ret.skew()
        skew_list = main_contrast_ret_skew if skew_list is None else pd.concat([skew_list, main_contrast_ret_skew], axis=0)
    skew_list.sort_values(ascending=False, inplace=True)
    g.skew_list = skew_list

def lever(context):
    # 获取商品期货合约的年化历史波动率
    qualify_list = g.qualify_list
    qualify_main_list = g.qualify_main_list
    main_contrast_std_all = None
    today_date = context.current_dt
    for future in qualify_list:
        main_contrast = get_dominant_future(future, today_date)
        main_contrast_price = get_price(main_contrast, frequency='daily', fields=['close'], 
                                  start_date=today_date-datetime.timedelta(days=60), end_date=today_date)
        main_contrast_std = main_contrast_price.rolling(2).apply(lambda x:np.log(x[1]/x[0])).dropna().std()/(1/np.sqrt(252))
        main_contrast_std.index = [future]
        main_contrast_std_all = main_contrast_std if main_contrast_std_all is None else pd.concat([main_contrast_std_all, main_contrast_std], axis=0)
        main_contrast_std_all.sort_values(ascending=False, inplace=True)
    # 计算所有品种相关系数，以过去60交易日为基础
    main_contrast_ret_all = None
    for future in qualify_list:
        main_contrast = get_dominant_future(future, today_date)
        main_contrast_price = get_price(main_contrast, frequency='daily', fields=['close'], 
                                  start_date=today_date-datetime.timedelta(days=60), end_date=today_date)
        main_contrast_price.columns = [future]
        main_contrast_ret = main_contrast_price.rolling(2).apply(lambda x:np.log(x[1]/x[0])).dropna()
        main_contrast_ret_all = main_contrast_ret if main_contrast_ret_all is None else pd.concat([main_contrast_ret_all, main_contrast_ret], axis=1)
    corr_all = main_contrast_ret_all.corr()
    corr_all_triu = pd.DataFrame(np.triu(main_contrast_ret_all.corr(), 1), index=corr_all.index, columns=corr_all.columns)
    corr_all_triu = corr_all_triu[corr_all_triu != 0]
    mean_corr = np.nanmean(np.mean(corr_all_triu))
    CF = np.sqrt(45/(1+44*mean_corr))
    # 策略组合波动率为10%，求各个品种的杠杆
    lever = CF*10/(main_contrast_std_all*100)
    g.lever = lever



## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    qualify_list = g.qualify_list
    qualify_main_list = g.qualify_main_list
    lever = g.lever
    roll_over = g.roll_over
    factor_momentum = g.factor_momentum
    ware_house = g.ware_house
    factor_pure_long = g.factor_pure_long
    judge_list = g.judge_list
    skew_list = g.skew_list
    #展期收益率
    roll_over.columns = ['展期收益率']
    roll_over.iloc[:8]=1
    roll_over.iloc[8:-8]=0
    roll_over.iloc[-8:]=-1
    roll_over = roll_over*2.120
    #基差动量
    factor_momentum = pd.DataFrame(factor_momentum)
    factor_momentum.columns = ['基差动量']
    factor_momentum.iloc[:8]=1
    factor_momentum.iloc[8:-8]=0
    factor_momentum.iloc[-8:]=-1
    factor_momentum = factor_momentum*1.257
    #仓单因子
    ware_house.columns = ['仓单因子']
    ware_house = ware_house.dropna()
    ware_house.iloc[:8]=1
    ware_house.iloc[8:-8]=0
    ware_house.iloc[-8:]=-1
    ware_house = ware_house*1.251
    #净多头变化率
    factor_pure_long = pd.DataFrame(factor_pure_long)
    factor_pure_long.columns = ['净多头变化率']
    factor_pure_long['future'] = factor_pure_long.index.values
    factor_pure_long['future'] = factor_pure_long['future'].apply(lambda x:x[:-9])
    factor_pure_long.set_index(['future'], inplace=True)
    factor_pure_long.iloc[:8]=1
    factor_pure_long.iloc[8:-8]=0
    factor_pure_long.iloc[-8:]=-1
    factor_pure_long = factor_pure_long*1.662
    #复合动量
    judge_list.columns = ['复合动量']
    judge_list['future'] = judge_list.index.values
    judge_list['future'] = judge_list['future'].apply(lambda x:x[:-9])
    judge_list.set_index(['future'], inplace=True)
    judge_list.iloc[:8]=1
    judge_list.iloc[8:-8]=0
    judge_list.iloc[-8:]=-1
    judge_list = judge_list*0.689
    # 偏度因子
    skew_list = pd.DataFrame(skew_list)
    skew_list.columns = ['峰度']
    skew_list.iloc[:8]=1
    skew_list.iloc[8:-8]=0
    skew_list.iloc[-8:]=-1
    skew_list = skew_list*1.662
    result = pd.concat([factor_momentum, roll_over, ware_house, factor_pure_long, judge_list, skew_list], axis=1)
    result = result.sum(axis=1).sort_values(ascending=False)
    result.iloc[:8] = 1
    result.iloc[8:-8] = 0
    result.iloc[-8:] = -1
    order1 = lever*result*(100/12)
    last = order1[order1!=0].sort_values(ascending=False)
    order_last = last * 100/sum(abs(last))
    today_date = context.current_dt
    s = {}
    for future in order_last.index.values:
        s[get_dominant_future(future, today_date)] = order_last[future]
    rr = pd.DataFrame(s, index=[0])
    rr = rr*70000
    rr_long = rr[rr>0]
    rr_long.dropna(axis=1, inplace=True)
    rr_short = rr[rr<0]
    rr_short = abs(rr_short)
    rr_short.dropna(axis=1, inplace=True)
    print(rr_short)
    for i in range(8):
        future_long = rr_long.columns[i]
        cash_long = rr_long.values[0][i]
        # print(future_long, cash_long)
        if future_long in context.portfolio.long_positions.keys():
            continue
        else:
            order_value(future_long, int(cash_long), side='long')
            
    
    for i in range(8):
        future_short = rr_short.columns[i]
        cash_short = rr_short.values[0][i]
        if future_short in context.portfolio.short_positions.keys():
            continue
        else:
            order_value(future_short, int(cash_short), side='short')
    
            
    for future in context.portfolio.long_positions.keys():
        if future not in rr_long.columns:
            order_target_value(future, 0, side='long')
    for future in context.portfolio.short_positions.keys():
        if future not in rr_short.columns:
            order_target_value(future, 0, side='short')

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
                for p in (subportfolio.long_positions.get(symbol, None), subportfolio.short_positions.get(symbol, None)):
                    if p is None:
                        continue
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
