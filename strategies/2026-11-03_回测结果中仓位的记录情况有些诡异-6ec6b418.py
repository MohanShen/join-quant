# Clone from JoinQuant
# postId: 6ec6b418c23122478f8e88ab58413e06
# backtestId: c20122e34fe0decc5c7bcd04d995f903
# title: 回测结果中仓位的记录情况有些诡异

from jqdata import *
from datetime import datetime, timedelta
import statsmodels.api as sm
import numpy as np

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 融资融券相关设定 ###
    # 设置账户类型: 融资融券账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.cash, type='stock_margin')])

    # 设定融资利率: 年化8%, 默认8%
    set_option('margincash_interest_rate', 0.08)
    # 设置融资保证金比率: 150%, 默认100%
    set_option('margincash_margin_rate', 1.0)

    # 设定融券利率: 年化10%, 默认10%
    set_option('marginsec_interest_rate', 0.10)
    # 设定融券保证金比率: 150%, 默认100%
    set_option('marginsec_margin_rate', 1.0)
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
    # 策略参数
    # 获取回测期内全部的交易日
    g.trading_dates = get_trade_days(start_date=context.run_params.start_date, 
    end_date=context.run_params.end_date)
    
    # 股票对调整日
    g.pair_rebalance_interval = 30
    g.pair_rebalance_dates = []
    for i in range(0, len(g.trading_dates)):
        g.pair_rebalance_dates.append(g.trading_dates[i])
    
    # 选择股票使用的窗口长度
    g.sel_win = 45
    
    # 计算股票对收益差使用的历史数据长度
    g.ew = 60
    # 产生交易信号的临界值
    g.threshold = 1.67
    # 出场临界值
    g.stopprofit = 0.5
    
    # 其他
    g.last_phase_pairs = []
    g.this_phase_pairs = [['000626.XSHE', '000972.XSHE']]
    g.out_codes = []
    g.out_pairs = []
    g.discount = 0.9 
    
    g.position_limit = 900000
    g.position_error = 0.85

def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))


## 开盘时运行函数
def market_open(context):
    
    # 调取仓位情况
    L = context.subportfolios[0].long_positions
    S = context.subportfolios[0].short_positions
    # 卖出调出的股票，使用正常买卖API操作融资融券账户
    for code in g.out_codes:
        if code in L.keys():
            order_target_value(code, 0)
        elif code in S.keys():
            Q = S[code].closeable_amount
            marginsec_close(code, Q)
        else:
            continue
    g.out_codes.clear()
    
    for pair in g.this_phase_pairs:
        A = pair[0]
        B = pair[1]
        
        # if len(filter_paused([A, B], context.current_dt)) != 2:
        #     continue
        
        try: 
            windowdataA = attribute_history(A, count=g.ew, skip_paused=False, df=False)['close']
            windowdataB = attribute_history(B, count=g.ew, skip_paused=False, df=False)['close']
        except:
            continue
        
        # 处理缺失值，如果有
        temp = pd.DataFrame({'A': windowdataA, 'B': windowdataB})
        temp.dropna(inplace=True)
        windowdataA = temp['A'].values
        windowdataB = temp['B'].values
        
        
        latest_priceA = windowdataA[-1]
        latest_priceB = windowdataB[-1]
        
        long_stocks = list(context.subportfolios[0].long_positions.keys())
        short_stocks = list(context.subportfolios[0].short_positions.keys())
        log.info("Simple Long and Short")
        log.info(long_stocks)
        log.info("A: "+A)
        log.info(short_stocks)
        log.info("B: "+B)
        LONG = context.subportfolios[0].long_positions
        SHORT = context.subportfolios[0].short_positions
        log.info("The whole position information")
        log.info("LONG: ")
        log.info(LONG)
        log,info("SHORT: ")
        log.info(SHORT)
        log.info("information the end")
        if A in long_stocks:
            log.info("COMELONG")
            QA = LONG[A].total_amount
            VA = LONG[A].value
            sideA = LONG[A].side
        elif A in short_stocks:
            log.info("COMESHORT")
            QA = SHORT[A].total_amount
            VA = SHORT[A].value
            sideA = SHORT[A].side
            
        else:
            log.info("COMEZERO")
            QA = 0
            VA = 0
            sideA = None
        
        if B in long_stocks:
            QB = LONG[B].total_amount
            VB = LONG[B].value
            sideB = LONG[B].side
        elif B in short_stocks:
            QB = SHORT[B].total_amount
            VB = SHORT[B].value
            sideB = SHORT[B].side
        else:
            QB = 0
            VB = 0
            sideB = None
        log.info('QA: QB: VA: VB: '+str(QA)+' '+str(QB)+' '+str(VA)+' '+str(VB))
        
        current_data = get_current_data()
        priceA = current_data[A].last_price
        priceB = current_data[B].last_price
        
        ols_model = sm.OLS(windowdataA, sm.add_constant(windowdataB))
        ols_result = ols_model.fit()
        _diff = ols_result.resid
        if len(ols_result.params) == 2:
            beta = ols_result.params[1]
        else:
            beta = priceA/priceB
        
        rolling_std = np.std(_diff)
        rolling_mean = np.mean(_diff)
        last_signal_diff = _diff[-2]
        signal_diff = _diff[-1]
        
        upper = rolling_mean + g.threshold * rolling_std
        lower = rolling_mean - g.threshold * rolling_std
        
        current_data = get_current_data()
        priceA = current_data[A].last_price
        priceB = current_data[B].last_price
        
        
        if signal_diff > upper and abs(VA) <= g.position_limit*g.position_error and abs(VB) <= g.position_limit*g.position_error:
            gapA = g.position_limit - abs(VA)
            gapB = g.position_limit - abs(VB)
            
            numA = gapA / priceA
            numB = numA * beta

            marginsec_open(A, numA)
            order2 = order(B, numB)

        if signal_diff < lower and abs(VA) <= g.position_limit*g.position_error and abs(VB) <= g.position_limit*g.position_error:
            gapA = g.position_limit - abs(VA)
            gapB = g.position_limit - abs(VB)
            
            numA = gapA / priceA
            numB = numA * beta
            
            marginsec_open(B, numB)
            order4 = order(A, numA)
            
        upper_stopprofit = rolling_mean + g.stopprofit*rolling_std
        lower_stopprofit = rolling_mean - g.stopprofit*rolling_std

        if last_signal_diff > upper_stopprofit and signal_diff < lower_stopprofit and sideA == 'short' and sideB == 'long':
            order5 = order_target_value(B, 0)
            marginsec_close(A, QA)

        if last_signal_diff < lower_stopprofit and signal_diff > upper_stopprofit and sideA == 'long' and sideB == 'short':
            order7 = order_target_value(A, 0)
            marginsec_close(B, QB)
        log.info("end of one loop")
        log.info("##########################################")

## 收盘后运行函数
def after_market_close(context):
    
    # 查看融资融券账户相关相关信息(更多请见API-对象-SubPortfolio)
    p = context.portfolio.subportfolios[0]
    log.info('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')
    log.info('查看融资融券账户相关相关信息(更多请见API-对象-SubPortfolio)：')
    log.info('总资产：',p.total_value)
    log.info('净资产：',p.net_value)
    log.info('总负债：',p.total_liability)
    log.info('融资负债：',p.cash_liability)
    log.info('融券负债：',p.sec_liability)
    log.info('利息总负债：',p.interest)
    log.info('可用保证金：',p.available_margin)
    log.info('维持担保比例：',p.maintenance_margin_rate)
    log.info('账户所属类型：',p.type)
    log.info('##############################################################')

def filter_paused(stocks,end_date,day=1,x=1):
    '''stocks:股票池     end_date:查询日期
    day : 过滤最近多少天(包括今天)停牌过的股票,默认只过滤今天
    x : 过滤最近day日停牌数>=x日的股票,默认1次
    返回 :过滤后的股票池 '''
    s = get_price(stocks,end_date=end_date,count =day,fields='paused').paused.sum()
    return s[s< x].index.tolist()
    

    
    
    
    

