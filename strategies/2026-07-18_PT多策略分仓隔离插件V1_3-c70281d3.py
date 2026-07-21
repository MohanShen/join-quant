# Clone from JoinQuant
# postId: c70281d3cb9f773e1888220777f8956c
# backtestId: 4f8717ecb41c4d6847d64e375cb27cef
# title: PT多策略分仓隔离插件V1.3

# 导入必要的库
from jqdata import *


def initialize(context):
    # 设置日志级别
    log.set_level('system', 'error')
    # 避免使用未来数据
    set_option("avoid_future_data", True)
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式（真实价格）
    set_option('use_real_price', True)
    # 设置交易成本
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.00025, close_commission=0.00025, min_commission=5), type='fund')
    # 设置滑点
    set_slippage(FixedSlippage(0.001))  # 设置固定滑点为0.1%
    # 每天09:20运行before_market_open函数
    run_daily(before_market_open, '09:20', reference_security='000300.XSHG')
    # 每天09:30运行market_open函数
    run_daily(market_open, '09:30', reference_security='000300.XSHG')
    # 每天收盘后运行风险管理（收盘后执行风控管理，有隔夜风险）
    # run_daily(handle_risk_management, 'after_close', reference_security='000300.XSHG')
    """我改成了早开盘和下午14：59双触发"""
    # 早盘开盘（9:30）触发风控检查
    run_daily(handle_risk_management, time='9:30', reference_security='000300.XSHG')
    # 下午14:59分触发风控检查
    run_daily(handle_risk_management, time='14:59', reference_security='000300.XSHG')

def handle_risk_management(context):
    try:
        # 确保在交易时段内执行
        if not context.trading_state.is_trading:
            return

        for fund in context.portfolio.positions:
            # 获取实时最新价（根据触发时间点动态选择数据源）
            if context.current_dt.hour == 9 and context.current_dt.minute == 30:
                # 早盘使用开盘价（避免集合竞价波动影响）
                current_price = get_price(fund, end_time=context.current_dt, frequency='1m', fields='open', skip_paused=True).iloc[-1]
            else:
                # 尾盘使用最新分钟线收盘价
                current_price = get_price(fund, end_time=context.current_dt, frequency='1m', fields='close', skip_paused=True).iloc[-1]
            
            cost_basis = context.portfolio.positions[fund].avg_cost

            # 止损逻辑（跌至成本价98%）
            if current_price < cost_basis * 0.95:
                log.info(f"止损触发：{fund} @ {context.current_dt}")
                order_target(fund, 0, style=MarketOrderStyle())  # 市价单确保成交

            # 止盈逻辑（涨至成本价102%）
            elif current_price > cost_basis * 1.10:
                log.info(f"止盈触发：{fund} @ {context.current_dt}")
                order_target(fund, 0)

    except Exception as e:
        log.error(f"风控异常：{e}")
def before_market_open(context):
    try:
        # 获取所有ETF基金
        fund_list = get_all_securities(['etf'], context.previous_date).index.tolist()

        # 获取历史数据
        high_df = history(count=1, unit='1d', field="high", security_list=fund_list).T
        low_df = history(count=1, unit='1d', field="low", security_list=fund_list).T
        volume_df = history(count=1, unit='1d', field="money", security_list=fund_list).T

        # 合并数据
        df = high_df.merge(low_df, left_index=True, right_index=True)
        df = df.merge(volume_df, left_index=True, right_index=True)
        df.columns = ['high_price', 'low_price', 'money']

        # 计算价格波动范围
        df['price_range'] = df['high_price'] - df['low_price']

        # 过滤成交额小于1000万的ETF*******
        """（我这里改为5000万）"""
        # df = df[df['money'] < 1e7]
        df = df[(df['money'] < 2e7)&((df['money'] > 5e6))]

        # 获取单位净值
        df = get_extras('unit_net_value', df.index.tolist(), end_date=context.previous_date, df=True, count=1).T
        df.columns = ['unit_net_value']

        # 存储到全局变量
        g.fund_list = df
    except Exception as e:
        log.error("Error in before_market_open: {}".format(e))

# 开盘时运行函数
def market_open(context):
    try:
        df = g.fund_list
        current = get_current_data()

        # 获取最新价
        df['last_price'] = [current[c].last_price for c in df.index.tolist()]

        # 计算溢价率（实际为折价率）
        df['premium'] = (df['last_price'] / df['unit_net_value'] - 1) * 100

        # 按折价率排序并过滤折价ETF（premium<0）
        df = df.sort_values(['premium'], ascending=True)
        df = df[df['premium'] < 0]

        #选择折价率最大的前5只ETF（premium值最小）
        """这里我改成了10支ETF，以求能够尽可能多地成交*****************************************************************"""
        selected_funds = df.head(10)
        order_fund = selected_funds.index.tolist()
        g.max_position = len(order_fund)

        log.info("Selected funds: {}".format(order_fund))

        # 卖出不在选定列表中的持仓
        for fund in context.portfolio.positions.keys():
            if fund not in order_fund:
                order_target_value(fund, 0)

        # 计算权重分配（使用折价率绝对值作为权重）
        weights = selected_funds['premium'].abs().tolist()  # 取绝对值计算权重
        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = 1e-9  # 防止除零错误

        available_cash = context.portfolio.available_cash

        # 按权重比例分配资金
        for fund, weight in zip(order_fund, weights):
            target_value = available_cash * (weight / total_weight)
            order_target_value(fund, target_value)
    except Exception as e:
        log.error("Error in market_open: {}".format(e))




'''


#导入函数库
# from jqdata import *
# from jqfactor import *
import numpy as np
import pandas as pd
from datetime import datetime,timedelta
import time
import json
# import multi_strategy
from collections import defaultdict
import platform

#初始化函数 
def initialize(context):
    g.signal = ''
    # 开启防未来函数
    # set_option('avoid_future_data', True)
    # 设定基准
    
    g.MKT_index = '880823.SZ' # 微盘股 , 通达信指数， PT中没有这个指数
    g.MKT_index = '399852.SZ' # 中证1000 
    g.MKT_index = '399303.SZ' # 国证2000
    g.MKT_index = '399101.SZ' # 深证中小板指数

    set_benchmark(g.MKT_index)
    # 用真实价格交易
    # set_option('use_real_price', True)
    # 将滑点设置为0
    if not is_trade():
        # set_slippage(FixedSlippage(3/10000))
        set_slippage(0.0003)
        # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
        # set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000, close_commission=2.5/10000, close_today_commission=0, min_commission=5),type='stock')
        set_commission(commission_ratio=0.0001, min_commission=5, type="STOCK")
        # PT 强制设置交易印花税, 强制设置没用,  盘中打印还是0.001
        context.commission.tax = 0.0005

        #回测中不限制成交数量
        set_limit_mode('UNLIMITED')
        # 过滤order中低于error级别的日志
        # log.set_level('order', 'error')
        # log.set_level('system', 'error')
        # log.set_level('strategy', 'debug')
        # log.set_log_level('order', 'error')
        # log.set_log_level('system', 'error')
        # log.set_log_level('strategy', 'debug')
    #初始化全局变量 bool
    g.no_trading_today_signal = False   # 不交易的日期
    g.no_trading_date_list = [ ["03-25", "04-28"], ["01-01", "01-31"]]   # 不交易的日子，  格式： ["开始日期", "结束日期"]

    g.configuration = {
        'xsz_version': "v1",    ## 市值选用版本 可选值: v1/v2/v3 具体逻辑自己看代码吧, v1: 双低小市值， v2: 国九小市值，  
        'triger_weekday': 2,    # 星期几触发， 缺省星期二触发。
        }  
    g.run_stoploss = True  # 是否进行止损
    #全局变量list
    g.hold_list = [] #当前持仓的全部股票    
    g.yesterday_HL_list = [] #记录持仓中昨日涨停的股票
    g.target_list = []
    g.not_buy_again = []
    #全局变量
    g.min_cap = 5      # 股票最小市值
    g.stock_num = 6     # 持股个数
    
    g.lowest_price = 1.2       # 股票的允许的最低价
    g.up_price = None       # 经测试， 不超过10元价最优， 100    # 设置股票单价 ， 最高不超过这个价格。
    g.reason_to_sell = ''
    g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    g.stoploss_limit = 0.98  # 止损线
    g.stoploss_market = 0.93  # 市场趋势止损参数
    
    g.HV_control = False #新增，Ture是日频判断是否放量，False则不然
    g.HV_duration = 120 #HV_control用，周期可以是240-120-60，默认比例是0.9
    g.HV_ratio = 0.9    #HV_control用
    g.stockL = []
    #空仓月份持有
    g.no_trading_buy = ['600036.SS',  # 招商银行
                        # '518880.SS',  # 黄金ETF
                        '600900.SS']  # 长江电力
    
    g.no_trading_hold_signal = False

    # 小市值黑名单
    g.black_list = [
                    # '002188.SZ',    # 中天服务 
                    # '002193.SZ',    # 如意集团
                    # '002719.SZ',    # 麦趣尔
                    '002856.SZ',    # 美芝股份
                    # '002883.SZ',    # 中设股份
                    # '002809.SZ',    # 红墙股份
                    # '002652.SZ',    # 扬子新材
                    # '002316.SZ',    # 亚联发展
                    # '002360.SZ',    # 同德化工
                    # '002910.SZ',    # 庄园牧场
                    # '002207.SZ'     # 准油股份
                    ]
    
    g.live_exchange = False  #是否实盘交易买入。

        
    #### PT多策略隔离初始化开始...
    # 配置Pandas显示参数（关键）, 便于打印显示对齐
    # 解决中文 打印对齐问题
    pd.set_option('display.unicode.ambiguous_as_wide', True)
    pd.set_option('display.unicode.east_asian_width', True)
    # 显示所有列
    pd.set_option('display.width', None)                      # 自动适配终端宽度
    pd.set_option('display.max_columns', None)                # 显示所有列
    pd.set_option('display.max_colwidth', None)               # 显示列内容完整宽度
    # # 防止列名折叠
    pd.set_option('display.expand_frame_repr', False)
    
    # Python 简洁版本字符串， 不同版本API有差异。
    g.python_version = platform.python_version()
    if g.python_version.startswith('3.5'):
        log.info("Python版本={}".format(g.python_version))
    else:
        log.info("Python版本={}".format(g.python_version))
    
    g.strategy_name = "小市值策略A"       # 手工配置，   策略名称。
    g.use_orig_portfolio_data = False    # 手工配置，   是否使用原始总仓数据,  True表示使用总仓数据，  False 表示使用分仓数据。 
    
    g.fq_type = 'dypre'                  # fq：数据复权选项，支持包括，pre-前复权，post-后复权，dypre-动态前复权，None-不复权；选填参数，默认为None；入参类型：str；
    g.order_api_type = None              # 手工配置： 买入调用哪个order接口,  
    g.sell_api_type = None               # 手工配置： 卖出调用哪个order接口,
                                         # "order_market_five_dealed" - 按市价进行委托(五档即时成交),    
                                         # "order_market_peer_price" - 按市价进行委托(对手最优价成交),  
                                         # "order_target_value"--调整股票持仓市值到value价值 (多策略同标的时不能用)
                                         # "order" - 按数量买卖, 同None， 缺省值调用order接口。
                                         # "observe_not_buy" - 只观察， 不买入。
    
                                        # 买卖队列，   如果买入标的 要等 卖队列中标的成交才可以买入， 需要增加这个队列。  
    g.sell_queue = []                   # 卖出队列，   格式： ["002222.SZ","601111.SZ"]
    g.buy_queue = {}                    # 买入队列,    格式： {'001654.SZ': {"symbol": '001654.SZ', "buy_value": 10000, "limit_price": 10.1, "callback": None}}
    g.auto_append_sell_queue = True     # 缺省所有卖操作自动入卖方队列， 这样需要等所有卖操作完成才自动执行买操作。 如果买入操作不要等卖出操作完成，需要将这个标志设置成False

    
    g.re_order_interval = 150            # 轮询任务间隔：如果订单 下单后超过这个时间间隔没有成交， 就撤单重新提交。 单位：秒, 建议至少60S以上。 
    if is_trade() and g.re_order_interval > 60:                       # 实盘场景的周期任务， 注意是多线程。 
        run_interval(context, sub_interval_job_re_order_handle, seconds=g.re_order_interval) #1、订单超时重新下单的任务。

    # 每个策略都有需要持久化的参数， 这里设置需要持久化的全局变量, 只支持JSON格式。 如：g.black_list, 
    g.need_persistent_list = ["black_list", 'target_list', 'no_trading_date_list', 'configuration', 'no_trading_buy']
    
    # 设置本策略可以使用的资金， 本策略所有持仓， 资金数据都保存在g.__sub_portfolio 
    g.__sub_portfolio = sub_init_strategy_portfolio(context, init_cash=100000)
    #初始资金 {g.__sub_portfolio.init_cash}, 
    log.info("策略初始化成功， 可用资金{}".format(g.__sub_portfolio.cash))

    #### PT多策略隔离初始化结束...

    # # 设置交易运行时间
    # run_daily(prepare_stock_list, '9:05')
    # run_weekly(weekly_adjustment,2,'10:30')     # 每周2 调仓。
    # run_daily(sell_stocks, time='10:00') # 止损函数
    # run_daily(trade_afternoon, time='14:20') #检查持仓中的涨停股是否需要卖出
    # run_daily(trade_afternoon, time='14:55') #检查持仓中的涨停股是否需要卖出
    # run_daily(close_account, '14:50')
    # # run_weekly(print_position_info, 5, time='15:10')
    # PTrade 设置交易运行时间  #  运行时间不要定在9:10之前， PT有时候会自动重启策略在9:10之前
    run_daily(context, prepare_stock_list, '09:12')
    # run_weekly(context, weekly_adjustment,2,'10:30')     # 每周2 调仓。
    run_daily(context, ptrade_run_weekly_adjustment, '10:29')
    run_daily(context, sell_stocks, time='10:00') # 止损函数
    run_daily(context, trade_afternoon, time='14:20') #检查持仓中的涨停股是否需要卖出
    run_daily(context, trade_afternoon, time='14:55') #检查持仓中的涨停股是否需要卖出
    run_daily(context, close_account, '14:50')

    return

def run_monthly_function(context):
    """_summary_
    月度调度函数
    Args:
        context (_type_): _description_
    """
    preday_month = context.previous_date.month 
    current_month = context.blotter.current_dt.month

    # # 获取当前日期,  检查是本月第几个交易日。
    # current_date = context.blotter.current_dt.strftime('%Y-%m-%d')
    # start_date = context.blotter.current_dt.strftime('%Y-%m') + "-01"
    # trade_days = get_trade_days(start_date, current_date)

    # 不是第一天， 直接退出。  如果是第n天， 还需要计算交易日期。
    if preday_month == current_month:
        return

    prepare_black_list(context)
    
    return    

def prepare_black_list(context):
    """_summary_
    准备小市值黑名单
    Args:
        context (_type_): _description_
    """

    # 每月第一天， 动态刷新黑名单
    log.info('生成小市值策略黑名单:')
    g.black_list = get_stock_list(context)

    return

def ptrade_run_weekly_adjustment(context):
    """_summary_
    # 每周的第N个交易日 调仓， N大于0。
    run_weekly函数在PTrade中没有,  使用 run_daily 实现。  在这个函数中检查一下是不是每周的第N个交易日即可。
    weekday    每周的第几个交易日, 必须>0。开始策略的那一周第一个交易日是从策略开始的那一天 计算的。    
        如果是春节， 五一, 十一假期， 哪么交易日可能会顺延。
    Args:
        context (_type_): _description_
        func (_type_): _description_
        time (_type_): _description_
    """

    # weekday() 结果是 0~6, 0是周一。

    weekday_num = context.blotter.current_dt.weekday() 
    # 得到周一的日期
    start_date = context.blotter.current_dt - timedelta(days=weekday_num)
    start_date_str = start_date.strftime('%Y-%m-%d')
    
    #本周的第几个交易日
    exchanged_days = get_trade_days(start_date = start_date_str)

    # print("exchanged_days = ",now_time,  exchanged_days)
    if len(exchanged_days) == g.configuration['triger_weekday']:
        # 刷新持久化数据
        weekly_adjustment(context)
    elif is_trade():
        # 观察今天的小市值排名。
        log.info("双低小市值排名观察")
        get_stock_list(context)
        # 观察今天的小市值排名。
        log.info("国九小市值排名观察")
        get_stock_list_gjl(context)
        pass
        
    return 

#1-1 准备股票池
def prepare_stock_list(context):
    """_summary_
    检查持仓票是不是有涨停票，  检查是不是交易日期（4月为排除的交易日）。
    Args:
        context (_type_): _description_
    """
    
    #获取已持有列表
    g.hold_list= []
    # 清空买卖队列, 
    sub_clear_buy_sell_queue(context)
    
    # 每天更新持久化数据；
    if is_trade():
        temp_sub_portfolio = load_strategy_persistent_data()
        if temp_sub_portfolio is not None:
            g.__sub_portfolio = temp_sub_portfolio

    positions = sub_get_strategy_positions(context)
    # for position in list(context.portfolio.positions.values()):
    g.hold_list = list(positions.keys())
        
    #获取昨日涨停列表
    if g.hold_list != []:
        # df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
        df = get_price(g.hold_list, end_date=str(context.previous_date), frequency='daily', fields=['close','high_limit','low_limit'], count=1)

        # 低版本的Ptrade格式转换。
        if g.python_version.startswith('3.5'):
            # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
            df_flat = df.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
            df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

            df_flat.columns = ['date', 'code', 'close','high_limit','low_limit']
            df = df_flat 
        
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    #判断今天是否为账户资金再平衡的日期
    g.no_trading_today_signal = today_is_between(context)

# v2 选股模块 (国九+roa+roe)
def get_stock_list_gjl(context):
    # initial_list = filter_stocks(context, get_index_stocks('399101.XSHE'))

    initial_list = get_index_stocks(g.MKT_index) # get_index_stocks(index_code,date) 获取指数成分股。
    initial_list = filter_new_stock(context, initial_list) # 过滤新股， 检查上市日期
    initial_list = filter_kcbj_stock(initial_list)  # 过滤 科创板， 创业板， 北交所
    initial_list = filter_st_paused_delisting_stock(context, initial_list)
    
    # 聚宽版本
    """
    # 修复：正确使用聚宽基本面表查询方式
    q = query(
        valuation.code,
        valuation.market_cap,
        income.np_parent_company_owners,
        income.net_profit,
        income.operating_revenue,
        valuation.turnover_ratio
    ).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(5, 50),
        income.np_parent_company_owners > 0,
        income.net_profit > 0,
        income.operating_revenue > 1e8,
        fundamentals.indicator.roe > 0.15,
        fundamentals.indicator.roa > 0.10,
    ).order_by(valuation.market_cap.asc()).limit(50)
    df = get_fundamentals(q)
    """
    # 估值表：市值、换手率，market_cap，turnover_ratio
    # ptrade：total_value，turnover_rate

    # 利润表：归属母公司净利润np_parent_company_owners、净利润net_profit、营业收入operating_revenue
    # ptrade：np_parent_company_owners， net_profit， operating_revenue

    # 财务指标数据，取roe、roa
    # ptrade： profit_ability-盈利能力表，roe，roa


    # ptrade 版本
    # 替换原始 query(...) + get_fundamentals(q) 的聚宽写法，ptrade 需要按表分别拉取并合并后再过滤
    # 注意：字段名与单位需依据 ptrade 实际返回调整（market_cap 单位可能不同）
    # 1) 拉 valuation 表
    df_val = get_fundamentals(
        security=initial_list,
        table='valuation',
        fields=['total_value', 'float_value',  'turnover_rate'],
        date=context.previous_date
    )
    df_val = df_val.reset_index()
    # 2) 拉 income 表
    # np_parent_company_owners	numpy.float64	归属于母公司所有者的净利润
    # net_profit	numpy.float64	净利润
    # operating_revenue	numpy.float64	营业收入
    # operating_profit	numpy.float64	营业利润
    df_inc = get_fundamentals(
        security=initial_list,
        table='income_statement',
        fields=['np_parent_company_owners', 'net_profit','operating_revenue'],
        date=context.previous_date
    )
    
    df_inc = df_inc.reset_index()
    # 3) 拉 indicator / fundamentals 表（取 roe/roa）
    # roa	numpy.float64	总资产净利率（%）
    # roe	numpy.float64	净资产收益率%摊薄公布值（%）
    df_ind = get_fundamentals(
        security=initial_list,
        table='profit_ability',
        fields=['roe', 'roa'],
        date=context.previous_date
    )
    df_ind = df_ind.reset_index()

    # 合并表格
    if df_val is None or df_val.empty:
        df = pd.DataFrame()
    else:
        df = df_val.copy()
        if df_inc is not None and not df_inc.empty:
            df = df.merge(df_inc, on='secu_code', how='left')
        if df_ind is not None and not df_ind.empty:
            df = df.merge(df_ind, on='secu_code', how='left')

    # 过滤与排序（与原 query 中的条件等价）
    if df.empty:
        df = pd.DataFrame(columns=['secu_code'])
    else:
        # 强制数值类型并去掉缺失
        for col in ['total_value', 'float_value', 'np_parent_company_owners', 'net_profit', 'operating_revenue', 'roe', 'roa']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df['total_value'] = df['total_value'] / 100000000 # 转为亿元单位
        df['float_value'] = df['float_value'] / 100000000 # 转为亿元单位
        df = df.dropna(subset=['total_value', 'float_value', 'net_profit', 'operating_revenue', 'roe', 'roa'])

        # 应用条件： total_value.between(5,50)、归属母公司净利润>0、净利润>0、营收>1e8、roe>0.15、roa>0.10
        df = df[
            (df['total_value'] >= g.min_cap)    # 总市值  
            &(df['np_parent_company_owners'] > 0) #归属于母公司所有者的净利润
            &(df['net_profit'] > 0)     #净利润
            &(df['operating_revenue'] > 1e8) #营业收入
            # &(df['roe'] > 0.15) #总资产净利率（%） 
            # &(df['roa'] > 0.10) #净资产收益率%摊薄公布值（%）
        ]

        # 按 total_value 升序并取前 50
        df = df.sort_values(by='total_value', ascending=True).head(50)

    if df.empty:
        return []

    df = df.set_index('secu_code', drop=False)

    initial_list = df.index.tolist()
    initial_list = initial_list[:100]
        
    if is_trade():
        # 实盘 再排除非本策略的持仓票
        all_positions_symbols = list(get_positions().keys())
        this_positions_symbols = list(sub_get_strategy_positions(context).keys())
        other_positions_symbols = list(set(all_positions_symbols) - set(this_positions_symbols))
        # 列表推导式过滤元素，保留原顺序
        initial_list = [x for x in initial_list if x not in other_positions_symbols]
        # SET 会让List乱序，而且乱序每次都不一样； 不能用。
        # initial_list = list(set(initial_list)  - set(other_positions_symbols)) 
            
    # 过滤昨天， 与今天 涨停， 与跌停股
    initial_list = filter_yesterday_limitup_and_limitdown_stock(context, initial_list)
    initial_list = filter_today_limitup_and_limitdown_stock(context, initial_list)

    # print(initial_list)
    stock_list = initial_list[:100]
            
    stock_list = get_stock_industry(stock_list, df)
    final_list = stock_list[:g.stock_num*2]
    log.info('今日前10:%s' % final_list)    
    
    return final_list

    # last_prices = get_history(1, '1d', 'close', final_list,fq='pre')
    # # 价格过滤
    # return [stock for stock in final_list if stock in get_positions() or last_prices.query(f'code in ["{stock}"]')['close'][-1] <= 20][
    #        :g.xsz_stock_num]

#1-2 选股模块
def get_stock_list(context):
    final_list = []
    # MKT_index = '399101.XSHE'
    initial_list = get_index_stocks(g.MKT_index) # get_index_stocks(index_code,date) 获取指数成分股。
    initial_list = filter_new_stock(context, initial_list) # 过滤新股， 检查上市日期
    initial_list = filter_kcbj_stock(initial_list)  # 过滤 科创板， 创业板， 北交所
    initial_list = filter_st_paused_delisting_stock(context, initial_list)
    
    # 查询流通市值，最小的前200值。 circulating_market_cap ： 流通市值 market_cap |总市值(亿元)| |circulating_market_cap| 流通市值(亿元)
    # q = query(valuation.code).filter(valuation.code.in_(initial_list)).order_by(valuation.circulating_market_cap.asc()).limit(200)
    # initial_list = list(get_fundamentals(q).code)
    # 场景二：date字段入参日期。回测和交易中若date为非交易日，将返回字段为NAN的数据；研究中若date为非交易日，将返回往前最近一个交易日的数据，注意回测和交易中是可以取到未来的数据，需要规避。
    previous_date = context.previous_date
    
    # indicator.eps 财务指标数据  eps 每股收益EPS(元)，  PTrade 使用 get_fundamentals-获取财务数据
    # ? 这里为什么又用 市值 排升序呢？          # 按总市值排序取前100，再进行行业分散
    # q = query(valuation.code,indicator.eps).filter(valuation.code.in_(initial_list)).order_by(valuation.market_cap.asc())
    # df = get_fundamentals(q)
    # stock_list = list(df.code)
    # stock_list = stock_list[:100]
    
    #'basic_eps','diluted_eps', eps 是每股收益， 
    # df_eps = get_fundamentals(initial_list, 'eps', fields=['eps'], date=previous_date)
    # df_eps = df_eps.sort_values(by='eps', ascending=False)
    # stock_list = df_eps.index.tolist()[:100]
    
    # 按总市值排序取前100，再进行行业分散
    # df_total_value = get_fundamentals(initial_list, 'valuation', fields=['total_value'], date=previous_date)
    # df_total_value = df_total_value.sort_values(by='total_value', ascending=False)
    # stock_list = df_total_value.index.tolist()[:100]
    # print("SSSSSSSSSSS", stock_list)
    
    df_float_value = get_fundamentals(initial_list, 'valuation', fields=['float_value','total_value','a_floats'], date=previous_date)
    df_float_value = df_float_value.sort_values(by='float_value', ascending=True).head(100)

    # 确保列是数值类型
    df_float_value['total_value'] = pd.to_numeric(df_float_value['total_value'], errors='coerce')
    df_float_value['float_value'] = pd.to_numeric(df_float_value['float_value'], errors='coerce')
    # 使用astype转换为float后再进行运算和四舍五入
    df_float_value['total_value'] = (df_float_value['total_value'] / 10000 / 10000).astype(float).round(2)
    df_float_value['float_value'] = (df_float_value['float_value'] / 10000 / 10000).astype(float).round(2)
    
    df_float_value = df_float_value[ df_float_value['total_value'] > g.min_cap] 

    df_float_value = df_float_value.sort_values(by='total_value', ascending=True)
    initial_list = df_float_value.index.tolist()

    if is_trade():
        # 实盘 再排除非本策略的持仓票
        all_positions_symbols = list(get_positions().keys())
        this_positions_symbols = list(sub_get_strategy_positions(context).keys())
        other_positions_symbols = list(set(all_positions_symbols) - set(this_positions_symbols))
        # 列表推导式过滤元素，保留原顺序
        initial_list = [x for x in initial_list if x not in other_positions_symbols]
        # SET 会让List乱序，而且乱序每次都不一样； 不能用。
        # initial_list = list(set(initial_list)  - set(other_positions_symbols)) 
            
    # 过滤昨天， 与今天 涨停， 与跌停股
    initial_list = filter_yesterday_limitup_and_limitdown_stock(context, initial_list)
    initial_list = filter_today_limitup_and_limitdown_stock(context, initial_list)

    # print(initial_list)
    stock_list = initial_list[:100]
            
    stock_list = get_stock_industry(stock_list, df_float_value)
    final_list = stock_list[:g.stock_num*2]
    log.info('今日前10:%s' % final_list)
    
    return final_list


#1-3 整体调整持仓
def weekly_adjustment(context):
    if g.no_trading_today_signal is False:
        close_no_trading_hold(context)
        #获取应买入列表 
        g.not_buy_again = []
        if g.configuration['xsz_version'] == 'v1':
            g.target_list = get_stock_list(context)
        elif g.configuration['xsz_version'] == 'v2':
            g.target_list = get_stock_list_gjl(context)

        """
        target_list = filter_not_buy_again(g.target_list)
        target_list = filter_paused_stock(target_list)
        target_list = filter_limitup_stock(context, target_list)
        target_list = filter_limitdown_stock(context, target_list)
        target_list = filter_highprice_stock(context, target_list)
        """

        target_list = g.target_list[:g.stock_num*2]
        log.info(str(target_list))

        positions = sub_get_strategy_positions(context)
        g.hold_list = list(positions.keys())
        
        current_data_dict = pt_get_current_data(context, g.hold_list)
        #调仓卖出
        for stock in g.hold_list:
            
            current_data = current_data_dict[stock]
            
            if current_data.last_price == current_data.high_limit:
                log.info("继续持有今日涨停票: [{}, {}]".format(stock, sub_get_stock_name(stock))) 
                continue
            
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[{}, {}]".format(stock, sub_get_stock_name(stock)))
                # position = context.portfolio.positions[stock]
                position = positions[stock]

                close_position(position, context)

            else:
                log.info("已持有[{}, {}]".format(stock, sub_get_stock_name(stock))) 
                pass
            
        #调仓买入
        buy_security(context,target_list)

        #记录已买入股票
        # 有买卖操作， 需要重新获取持仓数
        positions = sub_get_strategy_positions(context)
        # for position in list(context.portfolio.positions.values()):
        for position in list(positions.values()):
            stock = position.sid
            g.not_buy_again.append(stock)

    elif is_trade():
        #实盘获取一个当前的小市值标的，但于观察。
        if g.configuration['xsz_version'] == 'v1':
            g.target_list = get_stock_list(context)
        elif g.configuration['xsz_version'] == 'v2':
            g.target_list = get_stock_list_gjl(context)
            
   
#1-4 调整昨日涨停股票
def check_limit_up(context):
    # now_time = context.current_dt
    now_time = context.blotter.current_dt.strftime('%Y-%m-%d %H:%M')
    if g.yesterday_HL_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        positions = sub_get_strategy_positions(context)
        for stock in g.yesterday_HL_list:
            # if context.portfolio.positions[stock].enable_amount > -100:
            ## 增加校验， g.yesterday_HL_list 是早上9:05的数据， 可能上午， 下午检查，涨停打开， 大跌场景下，  股票已经卖出了。
            if stock not in positions:
                continue
            # if positions[stock].enable_amount > -100:
            if positions[stock].enable_amount > 0:
                # PTrade在 get_price在分时线时，不支持返回涨停价，需要合并。
                # current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq=g.fq_type, count=1, panel=False, fill_paused=True)

                # get_price 数据获取错误， end_date：结束时间，默认为空，回测中输入请小于回测日期， 为什么获取的是前一天的数据呢？
                # minute_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close'],  count=1, is_dict=False)
                # daily_data = get_price(stock, end_date=now_time, frequency='1d', fields=['close','high_limit'],  count=1, is_dict=False)
                # current_data = pd.merge(minute_data, daily_data[['code', 'high_limit']], on='code', how='left')

                minute_data = get_history(count=1, frequency='1m',  field=['close'], security_list=stock,  include = True)
                daily_data = get_history(count=1, frequency='1d', field=['close','high_limit'],  security_list=stock, include = True)

                minute_data['high_limit'] = 0
                minute_data['high_limit'].iloc[0] = daily_data['high_limit'].iloc[0] 
                current_data = minute_data 
                    
                if current_data.iloc[0,0] < current_data.iloc[0,1]:
                    log.info("[{}, {}] 涨停打开，卖出".format(stock, sub_get_stock_name(stock)))
                    # position = context.portfolio.positions[stock]
                    position = positions[stock]
                    close_position(position, context)
                    g.reason_to_sell = 'limitup'
                    # g.limitup_cash += context.portfolio.positions[stock].amount
                    # g.limitup_number += 1
                else:
                    log.info("[{}, {}] 涨停，继续持有".format(stock, sub_get_stock_name(stock)))


#1-5 如果昨天有股票卖出或者买入失败，剩余的金额今天早上买入
def check_remain_amount(context):
    if g.reason_to_sell == 'limitup': #判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
        g.hold_list= []
        # Fix Bug： 
        # 1、PTrade 当天卖出后， positions 还是有值的， 只是amount为0, 晚上结算后Position列表才会将卖出票清空。 
        # 2、同一个函数中卖出后，马上买入， 实盘中可能没有成交， 待改进。 
        positions = sub_get_strategy_positions(context)
        # for position in list(context.portfolio.positions.values()):
        for position in list(positions.values()):
            stock = position.sid
            if position.amount > 0:
                g.hold_list.append(stock)
                
        if len(g.hold_list) < g.stock_num:
            # 前面已取过这周的 最小市值 标的， 没必要再取一遍。
            # target_list = get_stock_list(context)
            target_list = g.target_list
            #剔除本周一曾买入的股票，不再买入
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            availbable_cash = sub_get_strategy_available_cash(context)
            # log.info('有余额可用'+str(round((context.portfolio.cash),2))+'元。'+ str(target_list))
            log.info('有余额可用'+str(custom_round((availbable_cash),2))+'元。'+ str(target_list))
            buy_security(context,target_list)
        g.reason_to_sell = ''

    else:
        # log.info('虽然有余额（'+str(custom_round((context.portfolio.cash),2))+'元）可用，但是为止损后余额，下周再交易')
        g.reason_to_sell = ''

#1-6 下午检查交易
def trade_afternoon(context):
    if g.no_trading_today_signal is False:
        check_limit_up(context) #检查涨停票次日是再涨停，不涨停再卖出。
        if g.HV_control is True:
            check_high_volume(context)
        huanshou(context)
        
        check_remain_amount(context)

        
#1-7 止盈止损
def sell_stocks(context):
    if g.run_stoploss == True:
        positions = sub_get_strategy_positions(context)
        if g.stoploss_strategy == 1:
            # for stock in context.portfolio.positions.keys():
            holding_list = list(positions.keys())
            for stock in holding_list:
                # 股票盈利大于等于100%则卖出
                # PTrade 参数不一样。
                # if context.portfolio.positions[stock].last_sale_price >= context.portfolio.positions[stock].cost_basis * 2:
                if positions[stock].last_sale_price >= positions[stock].cost_basis * 2:
                    # order_target_value(stock, 0)
                    
                    sub_order_target_value(stock, 0, context)
                    log.debug("收益100%止盈,卖出{}, {}".format(stock, sub_get_stock_name(stock)))
                # 止损
                # elif context.portfolio.positions[stock].last_sale_price < context.portfolio.positions[stock].cost_basis * g.stoploss_limit:
                elif positions[stock].last_sale_price < positions[stock].cost_basis * g.stoploss_limit:
                    # order_target_value(stock, 0)
                    sub_order_target_value(stock, 0, context)
                    log.debug("1收益止损,卖出{}, {}".format(stock, sub_get_stock_name(stock)))
                    g.reason_to_sell = 'stoploss'
        elif g.stoploss_strategy == 2:
            # stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            #  
            stock_df = get_price(security=get_index_stocks(g.MKT_index), end_date=str(context.previous_date), frequency='daily', fields=['close', 'open'], count=1)
            #down_ratio = (stock_df['close'] / stock_df['open'] < 1).sum() / len(stock_df)
            #down_ratio = abs((stock_df['close'] / stock_df['open'] - 1).mean())
            if g.python_version.startswith('3.5'):

                # 2. 通用 Panel 转平铺 DataFrame（核心步骤）
                # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
                df_flat = stock_df.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
                df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

                # 3. 重命名列（明确含义，与数据对应）
                # 关键：根据 Panel 维度定义映射列名
                # - items 对应 price_type（close/open）
                # - major_axis 对应 date（日期）
                # - minor_axis 对应 stock_code（股票代码）
                df_flat.columns = ['date', 'stock_code', 'close', 'open']
                stock_df = df_flat

            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            # 所有股票跌幅 超过stoploss_market 则清仓。 
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("1大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                # for stock in context.portfolio.positions.keys():
                holding_list = list(positions.keys())
                for stock in holding_list:
                    # order_target_value(stock, 0)
                    sub_order_target_value(stock, 0, context)
        elif g.stoploss_strategy == 3:
            # stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            stock_df = get_price(security=get_index_stocks(g.MKT_index), end_date=str(context.previous_date), frequency='daily', fields=['close', 'open'], count=1)
            if g.python_version.startswith('3.5'):
                # 2. 通用 Panel 转平铺 DataFrame（核心步骤）
                # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
                df_flat = stock_df.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
                df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）
                df_flat.columns = ['date', 'stock_code', 'close', 'open']
                stock_df = df_flat

            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("2大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                # for stock in context.portfolio.positions.keys():
                holding_list = list(positions.keys())
                for stock in holding_list:
                    # order_target_value(stock, 0)
                    sub_order_target_value(stock, 0, context)
            else:
                # for stock in context.portfolio.positions.keys():
                holding_list = list(positions.keys())
                for stock in holding_list:
                    # if context.portfolio.positions[stock].last_sale_price < context.portfolio.positions[stock].cost_basis * g.stoploss_limit:
                    if positions[stock].last_sale_price < positions[stock].cost_basis * g.stoploss_limit:
                        # order_target_value(stock, 0)
                        sub_order_target_value(stock, 0, context)
                        log.debug("2收益止损,卖出{}, {}".format(stock, sub_get_stock_name(stock)))
                        g.reason_to_sell = 'stoploss'

    
# 3-2 调整放量股票
def check_high_volume(context):
    # current_data = get_current_data()
    positions = sub_get_strategy_positions(context)
    hold_list = list(positions.keys())
    current_data = pt_get_current_data(context, hold_list)
    for stock in hold_list:
        if current_data[stock].paused is True:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        if positions[stock].enable_amount ==0:
            continue
        # df_volume = get_bars(stock,count=g.HV_duration,unit='1d',fields=['volume'],include_now=True, df=True)
        # PTrade get_histry 有未来数据。
        df_volume = get_history(g.HV_duration, frequency='1d', field=['volume'], security_list=stock, include=True)

        # 大于前N天最大成交量的  HV_ratio%？
        if df_volume['volume'].values[-1] > g.HV_ratio*df_volume['volume'].values.max():
            log.info("[%s]天量，卖出" % stock)
            # position = context.portfolio.positions[stock]
            positions = sub_get_strategy_positions(g , context)
            position = positions[stock]
            close_position(position, context)

#2-3 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68' or stock[:2] == '30':
            stock_list.remove(stock)
    return stock_list

#2-4 过滤今天的涨停， 跌停的股票
def filter_today_limitup_and_limitdown_stock(context, stock_list):
    # last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    # current_data = get_current_data()
    # return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
    #         or last_prices[stock][-1] <    current_data[stock].high_limit]

    df_history = pt_get_history(count=1,frequency="1d",
        field=["open", "high", "low", "close", "preclose","high_limit", "low_limit"], security_list=stock_list, include=True)

    # 低版本的Ptrade格式转换。
    if g.python_version.startswith('3.5'):
        # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
        df_flat = df_history.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
        df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

        df_flat.columns = ['date', 'code', "open", "high", "low", "close", "preclose","high_limit", "low_limit"]
        df_history = df_flat
        
    # 排除涨停票,  close 等于 high_limit 的行
    df_history = df_history[df_history['close'] != df_history['high_limit']]

    # 排除跌停票,  
    df_history = df_history[df_history['close'] != df_history['low_limit']]

    # 排除最低价票, PT的退市数据 有问题， 很多退市票的价格都很低， 低于1元。
    # ['002336.SZ', '002750.SZ', '600804.SS', '603003.SS'] 
    lowest_price = getattr(g, "lowest_price", 1.2)
    if lowest_price is not None:
        df_history = df_history[df_history['close'] > lowest_price]


    return df_history['code'].tolist()


#2-4 过滤昨天涨停的股票
def filter_yesterday_limitup_and_limitdown_stock(context, stock_list):
    # last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    # current_data = get_current_data()
    # return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
    #         or last_prices[stock][-1] <    current_data[stock].high_limit]

    df_history = get_history(count=1,frequency="1d",
        field=["open", "high", "low", "close", "preclose","high_limit", "low_limit"], security_list=stock_list, include=False)

    # 低版本的Ptrade格式转换。
    if g.python_version.startswith('3.5'):
        # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
        df_flat = df_history.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
        df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

        df_flat.columns = ['date', 'code', "open", "high", "low", "close", "preclose","high_limit", "low_limit"]
        df_history = df_flat
        
    # 排除涨停票,  close 等于 high_limit 的行
    df_history = df_history[df_history['close'] != df_history['high_limit']]

    # 排除跌停票,  
    df_history = df_history[df_history['close'] != df_history['low_limit']]

    # 排除最低价票, PT的退市数据 有问题， 很多退市票的价格都很低， 低于1元。
    # ['002336.SZ', '002750.SZ', '600804.SS', '603003.SS'] 
    lowest_price = getattr(g, "lowest_price", 1.2)
    if lowest_price is not None:
        df_history = df_history[df_history['close'] > lowest_price]

    return df_history['code'].tolist()


#2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    # last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    # current_data = get_current_data()
    # return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
    #         or last_prices[stock][-1] <    current_data[stock].high_limit]

    df_history = get_history(count=2,frequency="1d",
        field=["open", "high", "low", "close", "preclose","high_limit", "low_limit"],
        security_list=stock_list)

    # 低版本的Ptrade格式转换。
    if g.python_version.startswith('3.5'):
        # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
        df_flat = df_history.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
        df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

        df_flat.columns = ['date', 'code', "open", "high", "low", "close", "preclose","high_limit", "low_limit"]
        df_history = df_flat

    # holding_list = list(context.portfolio.positions.keys())
    new_stock_list = []

    for symbol in stock_list:
        df_stock_history = df_history[df_history['code']==symbol]
        #symbol in holding_list or 
        if df_stock_history['close'].iloc[-1] >= df_stock_history['high_limit'].iloc[-1]:
            continue
        new_stock_list.append(symbol)

    return new_stock_list



#2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    # last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    # current_data = get_current_data()
    # return [stock for stock in stock_list if (stock in context.portfolio.positions.keys()
    #         or last_prices[stock][-1] > current_data[stock].low_limit) 
    #         ]

    df_history = get_history(count=2,frequency="1d",
        field=["open", "high", "low", "close", "preclose","high_limit", "low_limit"],
        security_list=stock_list)

    # 低版本的Ptrade格式转换。
    if g.python_version.startswith('3.5'):
        # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
        df_flat = df_history.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
        df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

        df_flat.columns = ['date', 'code', "open", "high", "low", "close", "preclose","high_limit", "low_limit"]
        df_history = df_flat
            
    # holding_list = list(context.portfolio.positions.keys())
    positions = sub_get_strategy_positions(context)
    holding_list = list(positions.keys())
    new_stock_list = []

    for symbol in stock_list:
        df_stock_history = df_history[df_history['code']==symbol]
        #symbol in holding_list or 
        if df_stock_history['close'].iloc[-1] <= df_stock_history['low_limit'].iloc[-1]:
            continue

        new_stock_list.append(symbol)

    return new_stock_list




#2-6 过滤次新股
# Ptrade get_stock_info 
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    # return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date <  datetime.timedelta(days=375)]
    #     stock_info_dict = get_stock_info(market_code,field=['listed_date'])
    return [stock for stock in stock_list if not yesterday - datetime.strptime(get_stock_info(stock,['listed_date'])[stock]['listed_date'], "%Y-%m-%d").date() <  timedelta(days=375)]


#2-6.5 过滤股价
def filter_highprice_stock(context,stock_list):
    # last_prices = history(1, unit='1m', field='close', security_list=stock_list) 
    # #  排除高价股， 这里不要复权。

    if g.up_price is None:
        return

    last_prices = get_history(1, unit='1d', field='close', security_list=stock_list)
    
    # 低版本的Ptrade格式转换。
    if g.python_version.startswith('3.5'):
        # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
        df_flat = last_prices.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
        df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

        df_flat.columns = ['date', 'code', "open", "high", "low", "close", "preclose","high_limit", "low_limit"]
        last_prices = df_flat
            
    positions = sub_get_strategy_positions(context)
    return [stock for stock in stock_list if stock in positions.keys()
            or last_prices[stock][-1] <= g.up_price]


#2-7 删除本周一买入的股票
def filter_not_buy_again(stock_list):
    target_list = [stock for stock in stock_list if stock not in g.not_buy_again]
    return target_list

# 获取股票所属行业
def get_stock_industry(stock, stock_df):
    """_summary_
    #    blocks = get_stock_blocks(g.security)
    获取股票所属行业， 证监会行业， 概念， 地域， 所属指数 。 按行业对 小市值股票进行 打散。
    
    Args:
        symbol_list (_type_): _description_

    Returns:
        _type_: _description_
    """

    #{'ZS': [['399100.HSZS', '新指数'], ['399101.HSZS', '中小综指'], ['399106.HSZS', '深证综指'], ['399107.HSZS', '深证A指'], ['399233.HSZS', '制造指数'], 
    # ['399303.HSZS', '国证2000'], ['399317.HSZS', '国证A指'], ['399696.HSZS', '深证创投']], 
    # 'GN': [['003631.XBHS', '转融券标的'], ['003669.XBHS', '生态农业'], 
    # ['003712.XBHS', '一带一路'], ['011294.XBHS', '工业大麻'], ['011309.XBHS', '烟草'], ['011388.XBHS', '电子烟'], ['101374.XBHS', '包装印刷概念'], ['GN2006.XBHS', '东数西算/算力'],
    # ['GN2007.XBHS', '土壤修复'], ['GN2169.XBHS', '业绩反转'], ['GN2306.XBHS', '商业航天'], ['GN2391.XBHS', '龙头股'], ['GN2414.XBHS', '太空算力']], 
    # 'HY': [['360200.XBHS', '包装印刷']], 
    # 'ZJHHY': [['C22000.XBHS', '造纸和纸制品业']], 
    # 'DY': [['DY1145.XBHS', '上海板块']]}
    
    selected_stocks = []
    industry_list = []
    zjh_industry_list = []
    today_stock_df = None 

    for stock_code in stock:
        
        # 排除黑名单的票。
        if stock_code in g.black_list:
            continue
        
        blocks = get_stock_blocks(stock_code)
        if blocks is None:
            HY_name = "None"
            ZJHHY_name = "None"
            pass
        else:
            HY_name = blocks['HY'][0][1]
            ZJHHY_name = blocks['ZJHHY'][0][1]
        
        single_stock_df = stock_df.loc[stock_code] # 'total_value',  'float_value', 'a_floats'

        # if HY_name not in industry_list and ZJHHY_name not in zjh_industry_list:
        if HY_name not in industry_list:
            selected_stocks.append(stock_code)
            industry_list.append(HY_name)
            zjh_industry_list.append(ZJHHY_name)

            # log.info("行业信息: {}, {} (股票: {}, {}) (总市值: {}, 流通市值: {})".format(HY_name, ZJHHY_name, stock_code, sub_get_stock_name(stock_code), single_stock_df['total_value'], single_stock_df['float_value']))
            price_df = get_history(1, frequency='1m', field='close', security_list=stock_code, include=True)
            price = None
            if price_df is None or price_df.empty:
                price = None
            else:
                price = price_df['close'].iloc[0]
                
            # 逐条追加数据
            stock_dict = {
                    '代码': stock_code, 
                    '名称': sub_get_stock_name(stock_code),  
                    '行业': HY_name, 
                    '证监会行业': ZJHHY_name, 
                    '总市值': single_stock_df['total_value'], 
                    '流通市值': single_stock_df['float_value'], 
                    '价格': price  # round(position.last_sale_price * position.amount, 2)
                    }
            if today_stock_df is None : #or len(today_stock_df) > 0
                today_stock_df = pd.DataFrame([stock_dict])  # 转成DataFrame
            else:
                new_row = pd.DataFrame([stock_dict])  # 转成DataFrame
                today_stock_df = pd.concat([today_stock_df, new_row], ignore_index=True)

            # 选取了  个不同行业的股票
            if len(selected_stocks) == (g.stock_num*2):
                break
            
    log.info(f"今日小市值排名: \n{today_stock_df}")

    return selected_stocks

def calculate_minutes_between(time1_str, time2_str):
    """
    计算两个时间字符串之间的分钟数（支持跨天）
    
    参数:
        time1_str: 第一个时间，格式如 "10:12"
        time2_str: 第二个时间，格式如 "09:30"
2026-01-16 15:00:00  5472200.0
2026-01-17 09:31:00        NaN
2026-01-17 09:32:00        NaN        
2026-01-17 11:30:00     NaN
2026-01-17 13:01:00     NaN
2026-01-17 13:02:00     NaN
    
    返回:
        两个时间的分钟差值（正数，跨天则计算实际间隔）
    """
    # 解析时间字符串为time对象
    def parse_time(time_str):
        hours, minutes = map(int, time_str.split(':'))
        return time(hour=hours, minute=minutes)
    
    t1 = parse_time(time1_str)
    t2 = parse_time(time2_str)
    
    # 计算每个时间的总分钟数（从0点开始）
    t1_total_min = t1.hour * 60 + t1.minute
    t2_total_min = t2.hour * 60 + t2.minute
    
    # 计算差值（如果t2 < t1，说明跨天，加1440分钟（一天））
    diff_min = t1_total_min - t2_total_min 
    # if diff_min < 0:
    #     diff_min += 24 * 60  # 跨天的情况，加上一天的分钟数
  
    return diff_min
            
#换手率计算
def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        # 计算平均换手率
        # start_date = context.current_dt - datetime.timedelta(days=20)
        start_date = context.current_dt - timedelta(days=20)
        end_date = str(context.previous_date)
        df_volume = get_price(stock,end_date=end_date, frequency='daily', fields=['volume'],count=20)
        
        # get_valuation 获取多个标的在指定交易日范围内的市值表数据， circulating_cap| 流通股本(万股) ，
        # 回测没法取历史的 流通股本？
        # PTrade get_snapshot - 取行情快照， circulation_amount:流通股本(str:int)； 或者data 中的数据。
        # 只能通过 get_fundamentals-获取财务数据 来反推 流通市值吗？
        # df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        df_cap = get_fundamentals(stock, 'valuation', fields=['a_floats'], date=end_date)
        circulating_cap = df_cap['a_floats'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        # 计算实时换手率
        # date_now = context.current_dt
        
        # df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now, frequency='1m', fields=['volume'],
        #                    skip_paused=False, fq=g.fq_type, panel=True, fill_paused=False)
        start_date = context.blotter.current_dt.strftime('%Y-%m-%d') + ' 09:25:00'
        # 获取当前日期
        end_date = context.blotter.current_dt.strftime('%Y-%m-%d %H:%M:%S')
        current_minute = context.blotter.current_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # end_date：结束时间，默认为空，回测中输入请小于回测日期， 为什么研究可取到数据， 回测不可以呢？ 
        # 该接口与get_price接口不支持多线程同时调用，即在run_daily或run_interval等函数中不要与handle_data等框架模块同一时刻调用get_history或get_price接口，否则会偶现获取数据为空的现象
        # df_vol = get_price(stock, start_date=start_date, end_date=end_date, frequency='1m', fields=['volume'])
        minutes_count = 60*4 + 3 # 每天交易的分钟数
        df_vol = get_history(minutes_count, frequency='1m', field=['volume'], security_list=stock, include=True) #,is_dict=False
        # 方法1：使用布尔索引
        df_vol = df_vol[(df_vol.index >= start_date) & (df_vol.index <= end_date)]
        # print("DDDDDDDDDd", df_vol, stock, end_date, start_date)
        volume = df_vol['volume'].sum()
        # print("volume sum ", volume)
        # date_pre = context.previous_date
        # df_circulating_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        # circulating_cap = df_circulating_cap['circulating_cap'].iloc[0]  if not df_circulating_cap.empty else 0
        end_date = str(context.previous_date)
        df_cap = get_fundamentals(stock, 'valuation', fields=['a_floats'], date=end_date)
        circulating_cap = df_cap['a_floats'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        turnover_ratio = volume / (circulating_cap * 10000)
        return turnover_ratio            
            


# 换手检测
def huanshou(context):
    ss = []
    # current_data = get_current_data()
    positions = sub_get_strategy_positions(context)
    holding_list = list(positions.keys())

    if len(holding_list) == 0:
        return 

    current_data = pt_get_current_data(context, holding_list)
    shrink, expand = 0.003, 0.1

    for stock in holding_list:
        # print("XXXX", current_data)
        if current_data[stock].paused is True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit*0.97:
            continue
        if positions[stock].enable_amount == 0:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0: continue
        r = rt / avg
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        ### ？？？？ 大涨 而不是涨停时， 放量 与  缩量为啥要卖出呢？######### ### To be doing...........暂不卖出。
        # if action: 
        #     # log.info(f"{action} {stock} {get_security_info(stock).display_name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon}")
        #     log.info(
        #         "{action} {stock} {stock_name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon}".format(
        #             action=action,
        #             stock=stock,
        #             stock_name=sub_get_stock_name(stock), 
        #             rt=rt,
        #             avg=avg,
        #             r=r,
        #             icon=icon
        #         )
        #     )            
        #     position = positions[stock]
        #     close_position(position, context)
        #     g.reason_to_sell = 'limitup'
            
            
#3-2 交易模块-开仓,  如果不能马上成交，怎么办呢？
def open_position(security, value, context):
    # order_id = order_target_value_(security, value)
    # strategy_name, symbol, value, context, g
    order_id = sub_order_target_value(security, value, context)        
    if order_id == "None" and  order_id is None:
        log.error("买入出错: sid ={}, money = {},  order_id = {} ".format(security, value, order_id))
        return False

    # current_order = get_order(order_id)
    # if len(current_order) == 0:
    #     log.error("买入出错: sid ={}, money = {},  order_id = {}, order_list = {} ".format(security,value, order_id, current_order))
    #     return False
    # # 下单后 未必能马上成交， 这里的成交检查注释掉。
    # # if current_order[0].filled > 0:
    # #     return True
    
    return True

#3-3 交易模块-平仓
def close_position(position, context):
    security = position.sid
    
    if position.enable_amount == 0:
        # 已经卖出了。
        return True
    
    # order_id = order_target_value_(security, 0)  # 可能会因停牌失败
    order_id = sub_order_target_value(security, 0, context) # 可能会因停牌失败        

    if order_id == "None" and  order_id is None:
        return False

    return True

#3-4 买入模块； 计算持仓还没有卖出的标的。 已经挂单卖出的标的不算。
def ptrade_get_position_count_can_sell(context):
    """_summary_
    统计现在可以卖出股票的数量
    Args:
        context (_type_): _description_

    Returns:
        _type_: _description_
    """
    
    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')
    
    position_count = 0
    positions = sub_get_strategy_positions(context)
    for symbol, position in positions.items():
        
        # 当天买入的票不算。
        if position.buy_date == current_date:
            continue
        
        # if position.amount > 0:
        if position.enable_amount > 0:
            position_count = position_count + 1
                
    return position_count
    
def buy_security(context,target_list,cash=0,buy_number=0):
    #调仓买入, 
    # Fix 实盘Bug: 当天卖出，再马上买入存在两个问题：  
    # 1、 卖出未必能马上成交，就存在资金不到位的问题。  
    # 2、 卖出后contex.postions还是有数据， 在晚上结算完成后数据才会清空。  
    # 3、 卖出是异步操作， 如果卖单还没有成交， 立马进行买入操作， 可用资金数可能不对， 如何更新呢 ？
    # position_count = len(context.portfolio.positions)
    position_count = ptrade_get_position_count_can_sell(context)
    target_num = g.stock_num
    if cash == 0:
        # cash = context.portfolio.total_value #cash  total_value是聚宽的格式
        # cash = context.portfolio.cash #cash  # PTrade的格式
        cash = sub_get_strategy_available_cash(context) #cash  # PTrade的格式
    if buy_number == 0:
        # buy_number = target_num  买入标的太多， 需要减去持仓数量
        buy_number = target_num - position_count
    bought_num = 0
    print('---------------------buy_number:{}, target_num = {}, position_count={}'.format( buy_number, target_list ,  position_count))
    if target_num > position_count:
        # value = cash / (target_num) # - position_count
        #保留两位小数
        value = int(((cash*0.99) / buy_number)*100)/100 #(target_num) - position_count
        
        # 卖出标的还没有成交， 这样检查持仓个数会有问题？
        positions = sub_get_strategy_positions(context)
        for stock in target_list:
            if stock not in positions : #or positions[stock].amount == 0
            #if stock not in context.portfolio.positions:
                if bought_num < buy_number:
                    open_position(stock, value, context)
                        # log.info("买入[%s]（%s元）" % (stock,value))
                    g.not_buy_again.append(stock) #持仓清单，后续不希望再买入
                    bought_num = bought_num + 1
                else:
                    log.info("已经达到最大持仓数， {target_num} , 买数{bought_num} , 可买数 = {buy_number}".format(
                        target_num=target_num,
                        bought_num=bought_num,
                        buy_number=buy_number
                    ))   
                    break                    
    # else:
    #     value = cash / target_num
    #     for stock in target_list:
    #         if context.portfolio.positions[stock].amount == 0:
    #             if bought_num < buy_number:
    #                 if open_position(stock, value):
    #                     log.info("买入[%s]（%s元）" % (stock,value))
    #                     g.not_buy_again.append(stock) #持仓清单，后续不希望再买入
    #                     bought_num += 1
    #                     if len(context.portfolio.positions) == target_num:
    #                         break


#4-1 判断今天是否为四月 or (today > '12-20')
def today_is_between(context):
    
    if len(g.no_trading_date_list) == 0:
        return False

    today = context.blotter.current_dt.strftime('%m-%d')
    
    for date_list in g.no_trading_date_list:
        if today >= date_list[0] and today <= date_list[1]:
            return True
    # if (('03-25' < today) and (today <= '04-30')) or (('01-01' <= today) and (today <= '01-30')):
    
    return False

#4-2 清仓后次日资金可转
def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0 and g.no_trading_hold_signal == False:

            positions = sub_get_strategy_positions(context)
            g.hold_list = list(positions.keys())
            for stock in g.hold_list:
                position = positions[stock]
                if close_position(position, context):
                    log.info("卖出[{}, {}]".format(stock, sub_get_stock_name(stock))) #
                else:
                    log.info("卖出[{}, {}]错误！！！！！".format(stock, sub_get_stock_name(stock))) #
            buy_security(context, g.no_trading_buy)  
            g.no_trading_hold_signal = True   
            

#4-3 清仓小市值不交易期间股票
def close_no_trading_hold(context):
    if g.no_trading_hold_signal == True:
        positions = sub_get_strategy_positions(context)
        holding_list = list(positions.keys())
        for stock in holding_list:
            position = positions[stock]
            close_position(position, context)
            log.info("卖出[{}, {}]".format(stock, sub_get_stock_name(stock))) #
        g.no_trading_hold_signal = False


#1-8 动态调仓代码
def adjust_stock_num(context):
    ma_para = 10  # 设置MA参数
    today = str(context.previous_date)
    # start_date = today - datetime.timedelta(days = ma_para*2)
    start_date = today - timedelta(days = ma_para*2)
    index_df = get_price(g.MKT_index, start_date=start_date, end_date=today, frequency='daily')
    index_df['ma'] = index_df['close'].rolling(window=ma_para).mean()
    last_row = index_df.iloc[-1]
    diff = last_row['close'] - last_row['ma']
    # 根据差值结果返回数字
    result = 3 if diff >= 500 else \
             3 if 200 <= diff < 500 else \
             4 if -200 <= diff < 200 else \
             5 if -500 <= diff < -200 else \
             6
    return result



###########################################################################################################################################################################################
"""
以下是PT支持多策略分仓隔离功能。 Powered By 山红 
V1.0功能列表:
2025-10-20: PT支持多策略分仓隔离功能, 多策略运行互不干扰。
2025-10-25: 初步调试通过
2025-11-10: 实盘增加买卖队列功能,  只有卖出标的成交后，才执行买入标的。实盘场景卖出操作有时延， 卖出后不能马上执行买入操作。 回测场景不存在这个问题。
2025-11-15: 增加功能：超时没有成交订单支持撤单重新下单。
2025-11-18: 增加扣除佣金。
2025-11-20: 支持分红配送股, 除权功能。
2025-12-02: 支持order_tick函数, 便于打板操作。
2025-12-10: Fix Bug: 卖出成交后, PT(Portfolio, Position全局变量)资金到账会有几秒时间延迟(大概6秒延迟), 需等待几秒再买入, 另外个股买入资金需要重新计算。
2025-12-20: 增加 每日操作，每日持仓，策略资产 保存至Excel表格, 便于单策略复盘
2025-12-25: 支持order_market接口, 便于抢单，以便适配不同策略风格。
V1.1功能列表:
2026-03-25: Fix Bug: 1. 修正订单超时未重新提交。   2. 修正全天未成交时持仓资金错误。
2026-04-03: 支持不同策略购买相同标的。 
2026-04-03: 实盘时缺省所有卖出操作自动加入卖方队列，只有卖出操作全部完成才自动执行买入操作。 并增加控制标志 g.auto_append_sell_queue = True。
对于不用等卖出操作完成就可以执行买入操作的策略， 需要设置g.auto_append_sell_queue = False
V1.2功能列表：
2026-05-21: 支持记录最近最高收益， 以及最近回撤百分比。  
V1.3功能列表：
2026-06-27: Fix Bug: 修正 缩股时 股票数量计算不对的Bug。  
2026-06-27: Fix Bug: 修正 order_target_value 调整股票持仓数量的Bug, 如现持股10000元, 可调整为持仓为8000元, 或15000元。 原来只支持 全仓卖出买入。  
"""    
#####################################################################################################################################

class subPortfolio():
    """_summary_
    分仓类定义，  与PT的总仓类结构定义完全相同。 并增加几个必要变量。
    """
    def __init__(self, strategy_name:str, init_cash:int, date:str):
        self.strategy_name = strategy_name  # 策略名称
        self.init_cash = init_cash          # 初始资金, 添加资金时， init_cash 与 cash都要添加
        self.cash = init_cash               # 当前可用资金（不包含冻结资金）
        self.positions = {}                 # 当前持有的标的(包含不可卖出的标的), dict类型，key是标的代码，value是Position对象
        self.portfolio_value = init_cash    # 当前持有的标的和现金的总价值
        self.positions_value = 0            # 持仓价值
        self.capital_used = 0               # 已使用的现金
        self.returns = 0                    # 当前的收益比例, 相对于初始资金
        self.pnl = 0                        # 浮动盈亏
        self.start_date = date              # 开始时间  
        self.pre_portfolio_value = init_cash # 昨日总价值  
        self.pre_max_value = None           # 最近的最高市值  
        self.pre_max_value_date = None      # 最近的最高市值的日期。 格式： 2026-05-21  
        self.drawdown_rate = None           # 回撤百分比  
        
        
    def __str__(self):
        # {'002193.SZ': <IQEngine.user_module.subPosition object at 0x7f7cf03f2010>, '002719.SZ': <IQEngine.user_module.subPosition object at 0x7f7d2446df90>, '002856.SZ': <IQEngine.user_module.subPosition object at 0x7f7d2112d050>, '002883.SZ': <IQEngine.user_module.subPosition object at 0x7f7cf03f2050>, '002188.SZ': <IQEngine.user_module.subPosition object at 0x7f7cf03f2090>, '002652.SZ': <IQEngine.user_module.subPosition object at 0x7f7cf03f20d0>}
        postion_str = "{"
        for symbol, position in self.positions.items():
            postion_str = postion_str + "\n{}: {}".format(symbol, position)
        postion_str = postion_str + "}\n"
             
        """字符串表示"""
        return "subPortfolio(strategy_name={strategy_name}, init_cash={init_cash}, cash={cash}, positions={postion_str}, portfolio_value={portfolio_value}, positions_value={positions_value}, capital_used={capital_used}, returns={returns}, pnl={pnl}, start_date={start_date}, pre_portfolio_value={pre_portfolio_value}, pre_max_value={pre_max_value}, pre_max_value_date={pre_max_value_date}, drawdown_rate={drawdown_rate}); ".format(
                    strategy_name=self.strategy_name,
                    init_cash=self.init_cash,
                    cash=self.cash,
                    postion_str=postion_str,
                    portfolio_value=self.portfolio_value,
                    positions_value=self.positions_value,
                    capital_used=self.capital_used,
                    returns=self.returns,
                    pnl=self.pnl,
                    start_date=self.start_date,
                    pre_portfolio_value=self.pre_portfolio_value,
                    pre_max_value=self.pre_max_value,
                    pre_max_value_date=self.pre_max_value_date,
                    drawdown_rate=self.drawdown_rate,
                )

class subPosition():
    """_summary_
    分仓持仓定义，  与PT的持仓类结构定义完全相同。 并增加几个必要变量。
    """
    def __init__(self):
        self.buy_date = None    # 买入日期
        self.buy_time = None    # 买入时间
        self.sell_date = None   # 卖出日期
        self.sid = None         # 股票代码
        self.name = None        # 股票名称
        self.enable_amount = 0  # 可用数量
        self.amount = 0         # 总持仓数量
        self.last_sale_price = None # 最新价格
        self.cost_basis = None      # 持仓成本价格
        self.reorder_timeout = False # 超时重新下单标志
        self.order_dict =  {}       # 订单情况。 KEY 为order_id, Value为subOrder对象。

    def __str__(self):
        """字符串表示"""
        return "subPosition: buy_date: {buy_date}, buy_time: {buy_time}, sell_date: {sell_date}, sid:{sid},name:{name}, enable_amount:{enable_amount}, amount:{amount}, last_sale_price:{last_sale_price}, cost_basis: {cost_basis}, reorder_timeout: {reorder_timeout}, order_dict: {order_dict}; ".format(
                buy_date=self.buy_date,
                buy_time=self.buy_time,
                sell_date=self.sell_date,
                sid=self.sid,
                name=self.name,
                enable_amount=self.enable_amount,
                amount=self.amount,
                last_sale_price=self.last_sale_price,
                cost_basis=self.cost_basis,
                reorder_timeout=self.reorder_timeout,
                order_dict=list(self.order_dict.keys())
            )

class subOrder():
    """_summary_
    订单对象
    """
    def __init__(self):
        # self.id = None,          # 本次下单ID
        self.dt = None,        # 本次下单时间
        self.symbol = None,            # 本次下单代码
        self.order_amount = 0       # 本次下单数量
        self.order_price  = 0        # 本次下单价格        
        self.order_cash = 0          # 本次买入锁定金额
        self.business_price = 0      # 本订单成交价              
        self.business_amount = 0     # 本订单累计成交数量              
        self.business_balance = 0    # 本订单累计成交金额
        self.settlemented = False    # 订单是否完成结算
        self.tax_commission = None   # 手续费
        self.entrust_no = None       # 委托编号
        self.orig_order_money = None # 记录本次下单原始金额,  用于超时再次下单
        self.trade_response = []     # 本订单的的响应列表, 一条或多条。  返回的成交资金已经包含费用了。
    def __str__(self):
        """字符串表示"""
        return "subOrder: dt: {dt}, symbol: {symbol}, name: {name},order_amount: {order_amount}, order_price: {order_price}, order_cash: {order_cash}, business_amount:{business_amount}, business_balance:{business_balance}, settlemented:{settlemented}, tax_commission:{tax_commission}, entrust_no:{entrust_no}; ".format(
                dt=self.dt,
                symbol=self.symbol,
                name=sub_get_stock_name(self.symbol),
                order_amount=self.order_amount,
                order_price=self.order_price,
                order_cash=self.order_cash,
                business_amount=self.business_amount,
                business_balance=self.business_balance,
                settlemented=self.settlemented,
                tax_commission=self.tax_commission,
                entrust_no=self.entrust_no,
            )        

class StockCurrentData:
    """
    股票信息类，包含股票的各种属性信息。 与聚宽的类定义完成全一样, 为了在PT中实现聚宽的get_current_data函数
    
    属性说明：
    - last_price: 最新价，09:30之前获取返回昨日收盘价
    - high_limit: 涨停价
    - low_limit: 跌停价
    - paused: 是否停止或暂停交易（停牌、未上市或退市返回True）
    - is_st: 是否为ST股（包括ST、*ST，是则返回True）
    - day_open: 当天开盘价（09:27分之后才可获取）
    - name: 股票当前名称（可用于判断ST状态和退市风险），   PT没有历史名称API, 不支持历史名称。
    - industry_code: 股票所属行业代码， 使用的PT的行业数据，  行业划分与聚宽不一样
    """
    
    def __init__(self, last_price: float, high_limit: float, low_limit: float,
                 paused: bool, is_st: bool, day_open: float, name: str, industry_code: str):
        """
        初始化股票信息对象
        
        参数：
            last_price: 最新价
            high_limit: 涨停价
            low_limit: 跌停价
            paused: 是否停止交易
            day_open: 当天开盘价
            name: 股票名称
            industry_code: 行业代码
        """
        self.last_price = last_price
        self.high_limit = high_limit
        self.low_limit = low_limit
        self.paused = paused
        self.is_st = is_st
        self.day_open = day_open
        self.name = name
        self.industry_code = industry_code
        
    
    def _judge_st_status(self) -> bool:
        """根据股票名称判断是否为ST股（包括ST、*ST）"""
        if not self.name:
            return False
        # 检查股票名称是否以ST或*ST开头
        return self.name.startswith(('ST', '*ST'))
    
    def __repr__(self) -> str:
        """返回股票信息的字符串表示"""
        return "StockInfo(name={!r}, last_price={}, high_limit={}, low_limit={}, paused={}, is_st={}, day_open={}, industry_code={!r})".format(
            self.name,
            self.last_price,
            self.high_limit,
            self.low_limit,
            self.paused,
            self.is_st,
            self.day_open,
            self.industry_code
        )


def pt_get_current_data(context, symbol_list):
    """_summary_
    用于替换 聚宽API get_current_data,     # https://www.joinquant.com/help/api/help#name:api

    Args:
        context (_type_): _description_
        symbol_list (_type_): _description_

    Returns:
        _type_: _description_
    """
    
    # 获取当前时间
    current_time = context.blotter.current_dt.strftime('%H:%M')
    
    # 获取市场数据并计算目标持仓
    daily_data = get_history(
        count=1,
        frequency="1d",
        field=['open', 'close','is_open','preclose','high_limit','low_limit','unlimited'],
        security_list=symbol_list,
        fq=g.fq_type,
        #include：是否包含当前周期，True -包含，False-不包含；选填参数，默认为False；入参类型：bool；
        #include = True 一定要修正当天价， 否则包含未来函数。  
        include=True
    )

    # 低版本的Ptrade格式转换。
    if g.python_version.startswith('3.5'):
        # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
        df_flat = daily_data.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
        df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

        df_flat.columns = ['date', 'code', 'open', 'close','is_open','preclose','high_limit','low_limit','unlimited']
        daily_data = df_flat
        
    minute_data = get_history(
        count=1,
        frequency='1m',
        field=['open', 'close', 'high', 'low'],
        security_list=symbol_list,
        fq=g.fq_type,
        include=True
        )
    
    # 低版本的Ptrade格式转换。
    if g.python_version.startswith('3.5'):
        # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
        df_flat = minute_data.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
        df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

        df_flat.columns = ['date', 'code', 'open','close', 'high', 'low']
        minute_data = df_flat

        # 国盛PT的烂接口， 有时候get_history返回的数据不全， 再获取一次。
        if len(minute_data) < len(symbol_list):
            current_minute = context.blotter.current_dt.strftime('%Y-%m-%d %H:%M')  # YYYY-mm-dd HH:MM start_date=current_minute, 
            minute_data = get_price(symbol_list, end_date=current_minute, frequency='1m', fields=['open', 'close'], fq=g.fq_type, count=1)
            df_flat = minute_data.to_frame() 
            df_flat.reset_index(inplace=True)
            df_flat.columns = ['date', 'code', 'open','close', 'high', 'low']
            minute_data = df_flat
            
    # 合并两份数据， 清除未来数据。
    
    # 判断股票是否为ST、停牌或者退市的股票, （回测为回测当前周期，研究与交易则取系统当前时间）(str)；
    st_status = get_stock_status(symbol_list, 'ST')
        
    result_dict = {}
    for symbol in symbol_list:
        
        daily_df = daily_data[daily_data['code'].isin([symbol])]
        latest_minute_df = minute_data[minute_data['code'].isin([symbol])]
        
        last_price = None
        if is_trade():
            snapshot_dict = get_snapshot(symbol)
            last_price = snapshot_dict[symbol]["last_px"]
        else:
            last_price=latest_minute_df['close'].iloc[-1]
        # result_dict[symbol] = {
        #     'last_price' : latest_minute_df['close'].iloc[-1] , #最新价,09:30之前获取返回昨日收盘价
        #     'high_limit':  daily_df['high_limit'].iloc[-1], #涨停价
        #     'low_limit':  daily_df['low_limit'].iloc[-1],  #跌停价
        #     'paused': daily_df['is_open'].iloc[-1], # 是否停止或者暂停了交易, 当停牌、未上市或者退市后返回 True
        #     'is_st': st_status[symbol] , #是否是 ST(包括ST, *ST)，是则返回 True，否则返回 False
        #     'day_open': daily_df['open'].iloc[-1] ,  #当天开盘价,当天的开盘价至少09:27分之后才可获取
        #     #name: 股票现在的名称, 可以用这个来判断股票当天是否是 ST, *ST, 是否快要退市
        #     # industry_code: 股票现在所属行业代码, 参见 行业概念数据  blocks = get_stock_blocks(stock_code)
        # }

        result_dict[symbol] = StockCurrentData(last_price=last_price, 
                                                high_limit=daily_df['high_limit'].iloc[-1], 
                                                low_limit= daily_df['low_limit'].iloc[-1],  #跌停价
                                                paused= (daily_df['is_open'].iloc[-1] == 0), # 是否停止或者暂停了交易, 当停牌、未上市或者退市后返回 True
                                                is_st = st_status[symbol] , #是否是 ST(包括ST, *ST)，是则返回 True，否则返回 False
                                                day_open = daily_df['open'].iloc[-1] ,  #当天开盘价,当天的开盘价至少09:27分之后才可获取
                                                name = sub_get_stock_name(symbol),    # 股票现在的名称,  聚宽回测可以用这个来判断股票当天是否是 ST, *ST, 是否快要退市。 在PT中不能用这个字段判断ST，退市。
                                                industry_code = None  #get_stock_blocks(symbol)  #股票现在所属行业代码,  参见 行业概念数据。  PT中行业数据与聚宽不一样。
                                               )

    return result_dict    

def pt_get_history(count, frequency='1d', field='close', security_list=None, fq=None, include=False, fill='nan', is_dict=False):
    """_summary_
    pt_get_history 解决ptrade的接口get_history的问题：
    1、 统一所有Python版本返回为dataFrame格式。 python 3.5版本，原函数返回Pannel格式, Python 3.11原函数返回dataFrame格式。 本函数统一转换成 pandas.DataFrame格式。 
    2、 解决未来函数问题： 原函数frequency='1d'时， 并且include = True时,  获取的'close', 'volume' 是当天收盘价, 收盘成交量，这是未来数据。使用'1m'替换掉。
    3、 本接口只支持 frequency='1d', '1m'两种
    Args:
        count (_type_): _description_
        frequency (str, optional): _description_. Defaults to '1d'.
        field (str, optional): _description_. Defaults to 'close'.
        security_list (_type_, optional): _description_. Defaults to None.
        fq (_type_, optional): _description_. Defaults to None.
        include (bool, optional): _description_. Defaults to False.
        fill (str, optional): _description_. Defaults to 'nan'.
        is_dict (bool, optional): _description_. Defaults to False.
    """
    #统一格式
    if frequency == 'daily':
        frequency = '1d'
    
    history_df = None
    if isinstance(security_list, str):
        #当获取单支股票的数据
        history_df = get_history(count, frequency=frequency, field=field, security_list=security_list, fq=fq, include=include, fill=fill)

        # 解决未来函数问题。
        if frequency == '1d' and (include is True) and ('close' in field):
            minute_df = get_history(1, frequency='1m', field='close', security_list=security_list, fq=fq, include=include)
            history_df['close'].iloc[-1] = minute_df['close'].iloc[-1]
    
    elif isinstance(security_list, list) and isinstance(field, list):
        #当获取多支股票, 
        history_temp = get_history(count, frequency=frequency, field=field, security_list=security_list, fq=fq, include=include, fill=fill)

        # 老版本
        if g.python_version.startswith('3.5'):
            # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
            df_flat = history_temp.to_frame()  
            df_flat.reset_index(inplace=True)  
            columns_list = ['date', 'code'] + field
            df_flat.columns = columns_list
            history_temp = df_flat
        elif g.python_version.startswith('3.11'):
             # 将索引转换为'date'列
            history_temp['date'] = history_temp.index
        else:
            log.error("不支持Python Version ={}".format(g.python_version))
            return None            

        # 日线需要, 解决未来函数问题。
        if frequency == '1d' and (include is True) and ('close' in field):
            for symbol in security_list:
                minute_df = get_history(1, frequency='1m', field='close', security_list=symbol, fq=fq, include=include)
                stock_df = history_temp[history_temp['code'] == symbol]
                current_date = stock_df['date'].iloc[-1]
                # 最近日期为 current_date（日期格式，如 '2025-11-26'）和 symbol   # 修改目标行的 close 列为 minute_df的值。
                history_temp.loc[(history_temp['date'] == current_date) & (history_temp['code'] == symbol), 'close'] = minute_df['close'].iloc[-1]

        history_df = history_temp
    # 多支股票， 只获取单个字段。 返回格式是dataFrame
    elif isinstance(security_list, list) and (isinstance(field, str) or len(field) == 1) :

        #解决未来函数
        if field == 'close' and frequency == '1d' and include is True:
            frequency = '1m'
            
        history_df = get_history(count, frequency=frequency, field=field, security_list=security_list, fq=fq, include=include, fill=fill)

        pass
    else:
        log.error("请输入正确的参数格式,  security_list={} , field={}".format(security_list, field))
        pass
        
    return history_df
def filter_st_paused_delisting_stock(context, stock_list):
    """_summary_
    股票列表（该列表已剔除符合任一指定状态的标的）(list)
    过滤停牌股票  PTrade filter_stock_by_status 或者 # get_price 检查is_open字段,  

    'ST' - 查询是否属于ST股票
    'HALT' - 查询是否停牌
    'DELISTING' - 查询是否退市
    'DELISTING_SORTING' - 查询是否退市整理期(只过滤交易当日数据)

    Args:
        context (_type_): _description_
        stock_list (_type_): _description_

    Returns:
        _type_: _description_
    """

    current_date_tight = context.blotter.current_dt.strftime('%Y%m%d')

    # 过滤ST， 停牌， 退市， 退市整理期的票
    filter_stock = []
    if g.python_version.startswith('3.5'):
        filter_stock = []
        st_status = get_stock_status(stock_list, 'ST')
        # 将不是ST的股票筛选出来
        for i in stock_list:
            if st_status[i] is not True:
                filter_stock.append(i)

        stock_list = filter_stock
        filter_stock = []
        halt_status = get_stock_status(stock_list, 'HALT')
        # 将不是ST的股票筛选出来
        for i in stock_list:
            if halt_status[i] is not True:
                filter_stock.append(i)

        stock_list = filter_stock
        filter_stock = []
        delist_status = get_stock_status(stock_list, 'DELISTING')
        # 将不是ST的股票筛选出来
        for i in stock_list:
            if delist_status[i] is not True:
                filter_stock.append(i)
                
    else:
        filter_stock = filter_stock_by_status(stock_list, ["ST", "HALT", "DELISTING", "DELISTING_SORTING"],current_date_tight)            

    # PTrade上ST等数据有些不准， 进行双重过滤。  # 回测发现， 小市值有些票过段时候会被ST
    if is_trade():
        current_name_dict = get_stock_name(filter_stock)
        filter_stock =  [stock for stock in filter_stock 
                if current_name_dict[stock] is not None
                and 'ST' not in current_name_dict[stock]
                and '*' not in current_name_dict[stock]
                and '退' not in current_name_dict[stock]]

    return filter_stock

# position
def ParseJsonToObj(jsonStr:dict, objClass):
    """_summary_
    定义JSON Dict 与 class 对象互转函数
    Args:
        jsonStr (_type_): _description_ JSON String
        objClass (_type_): _description_  class对象名称

    Returns:
        _type_: _description_
    """
    # parseData = json.loads(jsonStr.strip('\t\r\n'))
    parseData = jsonStr

    if objClass.__name__ == "subPortfolio":
        result = objClass(parseData["strategy_name"],  parseData["cash"],  parseData["start_date"])
    elif objClass.__name__ == "subPosition":
        result = objClass()
    else:
        log.error("请输入正确的类名")
        return None
    
    result.__dict__.update(parseData)
 
    return result

def load_strategy_persistent_data() -> subPortfolio:
    """_summary_
    本策略持仓信息的持���化函数。 为了防止冲突，  每个策略的仓位信息需要持久化, 各自保存在一个JSON文件中。 
    不使用pkl格式, 使用JSON文件是为了提高盘后的阅读性。
    Args:
        strategy_name (_type_): _description_

    Returns:
        _type_: _description_
    """
    # # 回测场景 交易状态数据不进行持久化
    # if not is_trade():
    #     return None
    
    # 回测场景， 不用加载数据， 从头开始
    if not is_trade():
        return None

    # 实盘场景
    NOTEBOOK_PATH = get_research_path()
    
    filename =  NOTEBOOK_PATH + "running_info_"+g.strategy_name + '.json'

    saved_json = None
    sub_portfolio = None
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            saved_json = json.load(file)

        # 加载  持久化的全局参数。只支持JSON格式。
        for saved_item in g.need_persistent_list:
            # 如果变量是list ， 以持久化数据为准直接覆盖。
            if saved_item in saved_json and isinstance(getattr(g, saved_item, None), list):
                setattr(g, saved_item, saved_json[saved_item])
            # 如果变量是dict， 以持久化数据 与 程序中变量合并， dict中的相同变量名以持久化数据为准覆盖。
            elif saved_item in saved_json and isinstance(saved_json[saved_item], dict) and isinstance(getattr(g, saved_item, None), dict):
                setattr(g, saved_item, {**getattr(g, saved_item, {}),  **saved_json[saved_item]} )
            elif saved_item in saved_json:
            # 其他类型直接覆盖
                setattr(g, saved_item, saved_json[saved_item])

        # 加载资产数据
        sub_portfolio_json = saved_json['sub_portfolio']
        if sub_portfolio_json['strategy_name'] != g.strategy_name:
            log.error("策略名字不一样, {} , {} ".format(sub_portfolio_json['strategy_name'],  g.strategy_name))
            return None
        
        sub_portfolio = ParseJsonToObj(sub_portfolio_json, subPortfolio)

        positions_json_str = sub_portfolio.positions
        # 将持仓的JSON转换成Class对象
        if len(list(positions_json_str.keys())) > 0:
            positions_obj_dict = {}
            for symbol, position_str in positions_json_str.items():
                position_obj = ParseJsonToObj(position_str, subPosition)
                positions_obj_dict[symbol] = position_obj
        
            sub_portfolio.positions = positions_obj_dict            
        log.info("策略资产持久数据={} , 导入成功, Portfolio = {}".format(filename, sub_portfolio))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.error("错误: 文件 {} 未找到 {}".format(filename, e))    
        
    return sub_portfolio

def save_strategy_persistent_data(context):
    """_summary_
    保存 策略的 仓位的数据
    Args:
        g (_type_): _description_

    Returns:
        _type_: _description_
    """
    # # 回测场景 交易状态数据不进行持久化
    # if not is_trade():
    #     return

    # 回测场景不要进行数据持久化。
    if not is_trade():
        return None
    
    NOTEBOOK_PATH = "./"
    NOTEBOOK_PATH = get_research_path()
    
    filename =  NOTEBOOK_PATH + "running_info_"+g.strategy_name + '.json'

    ## 准备好备份数###
    portfolio_obj = sub_get_strategy_portfolio(context)

    # 先保存对象的链接，  持久化后需要恢复链接
    old_positions_class = portfolio_obj.positions
    
    positions = portfolio_obj.positions
    if len(list(positions.keys()))> 0:
        positions_dict = {}
        for symbol, position_obj in positions.items():
            position_dict = position_obj.__dict__
            positions_dict[symbol] = position_dict
            
            portfolio_obj.positions = positions_dict

    #JSON保存 策略的资产组合
    saved_json = {
        'sub_portfolio': portfolio_obj.__dict__,
        }
    
    # 保存需要  持久化的全局参数
    for saved_item in g.need_persistent_list:
        if hasattr(g, saved_item):
            saved_json[saved_item] = getattr(g, saved_item)
        
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(saved_json, file, ensure_ascii=False, indent=4)
        log.info("策略资产数据保存成功: {}, saved_json = {}".format(filename, saved_json))
    except Exception as e:
        log.error("策略资产数据保存失败{}, Reason= {}, json={}".format(filename, e, saved_json))

    ## 恢复持仓对象链接。
    portfolio_obj.positions = old_positions_class

    return

def inner_append_portfolio_to_excel(new_df,sheet_name="Sheet1"):
    """
    读取 Excel 并追加一行数据（支持更新/去重）
    :param new_row: 新行数据（字典格式，key=列名，value=值）
    :param sheet_name: 工作表名称
    :param index: 是否保留 pandas 索引列（默认不保留）
    """
    # 回测场景不要进行数据持久化。
    if not is_trade():
        return None
    
    NOTEBOOK_PATH = get_research_path()

    filename =  NOTEBOOK_PATH     
    if g.python_version.startswith('3.11'):
        filename =  filename + "策略资产_"+g.strategy_name + '_data.xlsx'
    elif g.python_version.startswith('3.5'):
        filename =  filename + "策略资产_"+g.strategy_name + '_data.xls'
    else:
        log.error("错误环境：{}".format(g.python_version))
        return

    try:
        # 1. 读取现有 Excel 数据（若文件不存在，会抛出 FileNotFoundError）
        df = pd.read_excel(filename, sheet_name=sheet_name)
    except FileNotFoundError as e:
        log.warning("文件不存在: {}, 异常提示={}".format(filename, e))
        # 2. 若文件不存在，创建新 DataFrame（以新行的键为列名）
        df = new_df
    except ValueError as e:
        log.warning("sheet页面 {} 不存在, 异常提示={}".format(sheet_name, e))
        # 2. 若文件不存在，创建新 DataFrame（以新行的键为列名）
        df = new_df       
    else:
        # 3. 若文件存在，追加新行（先转为 DataFrame 再合并）
        # 可选：去重（根据关键列判断，避免重复追加，例如按 "ID" 列去重）
        df = pd.concat([df, new_df], ignore_index=True)
    

    # 4. 保存回 Excel（index=False 表示不写入索引列）
    # 关键：用ExcelWriter打开文件，mode='a'（追加模式），engine='openpyxl'
    try:
        with pd.ExcelWriter(filename, mode='a', engine='openpyxl', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            log.info("成功追加页面: {} 到文件：{}".format(sheet_name, filename))
    except FileNotFoundError:
        df.to_excel(filename, sheet_name=sheet_name, index=False)
        log.info(f"成功新建文件{filename}并写入sheet【{sheet_name}】")
    except Exception as e:
        # 捕获其他未知错误，打印详细信息
        log.error(f"写入Excel文件{filename}失败，未知错误：{str(e)}")
        
    return

def sub_init_strategy_portfolio(context, init_cash=0):
    """_summary_
    initialize(context)
    1、 第一次运行： 注册运行策略，   只设置本策略的数据， 策略名称 + 可用资金 即可。
    2、 第N次运行:   读取存盘的策略运行数据，  

    Args:
        strategy_name (_type_): _description_
        g (_type_): _description_
        context (_type_): _description_
        init_cash (_type_): _description_, 初始资金
    """
    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        return context.portfolio
   
    # 读取 持久化的策略数据。
    load_strategy_data = load_strategy_persistent_data()

    # 持久化数据中没有这个策略数据， 初始注册
    if load_strategy_data is None:

        # 初始资金必须小于账户的可用资金
        # 实盘会有现金宝业务，  可用资金会少点。
        available_cash = context.portfolio.cash
        if is_trade():
            available_cash = context.portfolio.portfolio_value - context.portfolio.positions_value
        
        if init_cash > available_cash:
            log.error("输入初始资金太大, 调整为账户可用资金。初始资金{},  账户可用资金{}".format(init_cash, available_cash))
            init_cash = available_cash
                   
        # 获取当前日期
        current_date = context.blotter.current_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        sub_portfolio = subPortfolio(g.strategy_name, init_cash, current_date)
    else:
        # 读取 持久化数据， 赋值完成。 
        sub_portfolio = load_strategy_data

    return sub_portfolio
def sub_get_strategy_portfolio(context):
    """_summary_
    获取本策略的 运行有标的操作仓位的信息汇总，
    Args:
        strategy_name (_type_): _description_ 策略名称
        g (_type_): _description_   全局变量
        context (_type_): _description_ 运行环境上下文

    Returns:
        _type_: _description_ 可用资金
    """
    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        return context.portfolio

    # 刷新与校验分仓持股数据
    sub_refresh_position_data(context)
   
    sub_portfolio = g.__sub_portfolio

    return sub_portfolio

def inner_sub_get_strategy_portfolio(context):
    """_summary_
    获取本策略的 运行有标的操作仓位的信息汇总，
    Args:
        strategy_name (_type_): _description_ 策略名称
        g (_type_): _description_   全局变量
        context (_type_): _description_ 运行环境上下文

    Returns:
        _type_: _description_ 可用资金
    """

    sub_portfolio = g.__sub_portfolio

    return sub_portfolio

def sub_get_strategy_available_cash(context):
    """_summary_
    获取本策略的可用资金，
    Args:
        strategy_name (_type_): _description_ 策略名称
        g (_type_): _description_   全局变量
        context (_type_): _description_ 运行环境上下文

    Returns:
        _type_: _description_ 可用资金
    """
    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        return context.portfolio.cash
    
    sub_portfolio = g.__sub_portfolio
    if sub_portfolio.cash > context.portfolio.cash:
        #2025-02-11 10:30:00 - WARNING - 本策略可用资金大于总仓位可用资金, 本策略可用资金=18628.988400000002, 总仓可用资金=18606.445766664725
        # 回测时：总仓卖出成交扣除佣金时机,  收到卖出已成成交通知就扣除了佣金。 会造成盘中分仓可用资金大于总仓可用资金 
        # Fix Bug： 实盘场景, 如果卖出票后， 不能马上调用 sub_get_strategy_available_cash API， 会造成可用资金不足。 
        # 因为总仓的context.portfolio.cash的数据更新有近6秒延迟。 
# 2026-02-26 14:20:00 - INFO - 卖出盘后结算: symbol=002725.SZ, 跃岭股份, 下单数=-1100.0, 成本价=15.361元, 成交数=-1100, 成交均价=16.872725, 成交额=18535.0, 手续费=24.998, 利润=1612.9019999999978, 利润率=9.84%
# 2026-02-26 14:20:00 - WARNING - 本策略可用资金大于总仓位可用资金,  本策略可用资金=20726.339,  总仓可用资金=14065.07        
        log.warning("本策略可用资金大于总仓位可用资金,  本策略可用资金={},  总仓可用资金={}".format(sub_portfolio.cash, context.portfolio.cash))
        sub_portfolio.cash = context.portfolio.cash  
        pass
    
    return sub_portfolio.cash
    
def inner_del_strategy_positions(symbol): #->List[subPosition] Python 3.5 之前版本不支持指定List 类型返回值。
    """_summary_
    删除分仓策略 持仓股票
    Args:
        symbol (_type_): _description_
    """

    sub_portfolio = g.__sub_portfolio
    positions = sub_portfolio.positions

    if symbol in positions:
        del positions[symbol]

    return    

def sub_get_strategy_positions(context, symbol=None): #->List[subPosition] Python 3.5 之前版本不支持指定List 类型返回值。
    """_summary_
    获取本策略的所有持仓标的
    Args:
        strategy_name (_type_): _description_ 策略名称
        g (_type_): _description_   全局变量
        context (_type_): _description_ 运行环境上下文
    Returns:
        _type_: _description_      #如果传入的symbol,  不在持仓列表中， 返回amount=0的持仓subPosition对象
    """
    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        return context.portfolio.positions

    # 刷新最新价
    sub_portfolio = g.__sub_portfolio
    positions = sub_portfolio.positions

    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')

    hold_list = list(positions.keys())
    
    result_list = {}

    for index, holding_symbol in enumerate(hold_list):
        position = positions[holding_symbol]
        # 持仓已经卖出了。
        if position.amount == 0 and current_date > position.buy_date:
            # # 在dict枚举时，不能删除,  在尾盘结算时再删除。
            continue    
        
        position.last_sale_price = sub_get_current_price(holding_symbol, context)
    
        # 检查是否查询特定代码的持仓, 持仓会返回真实持仓。  不是持仓会返回amount=0的持仓Position对象
        # {'002188.XSHE': <Position {'sid': '002188.SZ', 'enable_amount': 2500, 'amount': 2500.0, 'last_sale_price': 6.12, 'cost_basis': 6.392, 'business_type': 'stock', 'today_amount': 0.0, 'update_time': '2025-11-24 10:21:50'}>}
        # {'601869.XSHG': <Position {'sid': '601869.SS', 'enable_amount': 0, 'amount': 0, 'last_sale_price': 73.74, 'cost_basis': 0, 'business_type': 'stock', 'today_amount': 0, 'update_time': None}>}
        if symbol is not None: 
            #传入symbol 有效并且存在
            if isinstance(symbol, str) and holding_symbol == symbol:
                return position
            #传入symbol 有效并且不存在
            elif isinstance(symbol, str) and index == (len(hold_list) - 1):
                no_position = subPosition()
                no_position.sid = symbol         # sid 标的代码
                no_position.enable_amount = 0  # 可用数量
                no_position.amount = 0         # 总持仓数量 
                return no_position
            #传入symbol 有效并且还没有轮询完成。
            elif isinstance(symbol, str):
                continue
            #传入symbol 是List， 有效并且有效
            elif isinstance(symbol, list) and holding_symbol in symbol:
                result_list[holding_symbol] = position

            #传入symbol 是List， 有效 轮询完成
            elif isinstance(symbol, list) and holding_symbol not in symbol and index == (len(hold_list) - 1):
                for query_symbol  in symbol:
                    if query_symbol not in hold_list :
                        no_position = subPosition()
                        no_position.sid = symbol         # sid 标的代码
                        no_position.enable_amount = 0  # 可用数量
                        no_position.amount = 0         # 总持仓数量
                        result_list[symbol] = no_position                    
            #传入symbol 是List有效，  轮询还没有完成
            elif isinstance(symbol, list) and holding_symbol not in symbol and index < (len(hold_list) - 1):
                continue
            
        else:
            result_list[holding_symbol] = position
            
    # 获取所有持仓。
    if symbol is None:
        return positions
    
    return result_list


def sub_get_current_price(symbol, context):
    """_summary_
    获取股票现在价格
    Args:
        symbol (_type_): _description_

    Returns:
        _type_: _description_
    """
    
    price = None
    
    if is_trade():
        snapshot = get_snapshot(symbol)
        
        price = snapshot[symbol]["last_px"]
    else:
        
        df_minute = get_history(1, frequency='1m', field=['close'], security_list=symbol, fq=g.fq_type, include=True)

        # 获取单只股票的一个，或多个字段时， 没有code这一列。 此时的dataframe列，是没有code这一列的
        # PT烂问题 ,  国盛的PT get_history接口 有时候返回数为空。 
        current_minute = context.blotter.current_dt.strftime('%Y-%m-%d %H:%M')  # YYYY-mm-dd HH:MM start_date=current_minute, 
        if len(df_minute) == 0:
            df_minute = get_price(symbol, end_date=current_minute, frequency='1m', fields=['close'], fq=g.fq_type, count=1)

        if len(df_minute) > 0:
            price = df_minute['close'].iloc[-1]
        else:
            log.error(f"获取价格失败{symbol},{sub_get_stock_name(symbol)}, time = {current_minute}")
            
    return price


def sub_interval_job_re_order_handle(context):
    """_summary_
    订单超时没成交， 撤单重新提交。
    Args:
        context (_type_): _description_
    """
    
    if not is_trade():
        return

    current_time = context.blotter.current_dt.strftime("%H:%M:%S")

    # 非交易时间退出
    if current_time < "09:30:00" or current_time > "15:00:00":
        return
    
    # order_list = get_all_orders() 
    order_list = get_orders()   # 只获取本策略订单。

    # [{'price': 135.777, 'entrust_no': '65313', 'filled_amount': 0, 'entrust_bs': 2, 'status': '6', 'symbol': '113601.SS', 'amount': -50, 'entrust_time': '2025-06-10 09:48:40'}
    # entrust_bs -- 成交方向，1-买，2-卖；
    for order_obj in order_list:
        
        symbol = order_obj.symbol

        # 只处理未成交的订单，     '2' -- "已报"，  '7' -- "部成"
        if order_obj.status == '2' or order_obj.status == '7':
            pass
        else:
            continue

        # PT有时候代码后缀会变化。
        if symbol.endswith(".XSHG"):
            # 替换后缀为 .SS
            symbol = symbol.replace(".XSHG", ".SS")
        elif symbol.endswith(".XSHE"):
            # 替换后缀为 .SZ
            symbol = symbol.replace(".XSHE", ".SZ")
        elif symbol.endswith(".SS") or symbol.endswith(".SZ"):
            # 正确代码
            pass
        else:
            log.error("错误的代码 {}".format(symbol))
            continue

        # 标的隔离， 不在本策略持仓中订单忽略。
        holding_dict = sub_get_strategy_positions(context)
        if symbol not in  holding_dict:
            log.error("错误的代码 {}".format(symbol))
            continue
        
        # 获取持仓
        position = holding_dict[symbol]
        
        # 卖单持仓应该大于0
        if order_obj.amount < 0 and position.amount <= 0: 
            log.warning("校验数据不一致, 卖出标的持仓数量为0,  order={}, position={}".format(order_obj, position))
            continue

        # 检查订单是否提交太久， 没有成交  entrust_time
        current_timestamp = int(datetime.now().timestamp())

        # 订单提交时间, 转换为秒级时间戳（浮点数，含小数部分）
        # delivered_dt = datetime.strptime(order_dict['entrust_time'], "%Y-%m-%d %H:%M:%S")
        delivered_timestamp = int(order_obj.dt.timestamp())

        if (current_timestamp - delivered_timestamp) < g.re_order_interval:
            continue
       
        # 买入时：需要检查是不是打板涨停价， 涨停价买入不撤单。
        if order_obj.amount > 0:
            df_history = get_history(1, '1d', 'high_limit', symbol, fq=None, include=True)
            high_limit = df_history['high_limit'].iloc[0]
            order_id = order_obj.id
            if order_id in position.order_dict:
                sub_order = position.order_dict[order_id]
                if sub_order.order_price == high_limit:
                    log.info("打板买入不撤单:symbol={}:{}, price={}".format(symbol, sub_get_stock_name(),sub_order.order_price))
                    continue
            else:
                log.warning("subPosition没有记录订单:symbol={}, order_id={}, order={}, position={}".format(symbol, order_id, order_obj, position))
                pass
       
        # 卖单已报， 或部成。 超时没有成交， 撤单重新提交订单。
        if order_obj.status == '2' or order_obj.status == '7':
            # 设置标志，发展订单超时重新下单。
            position.reorder_timeout = True
            cancel_order(order_obj.id)
            log.info("超时未成交, 撤单order_id={}, order={}".format(order_obj.id, order_obj))
        elif order_obj.status == '8' or order_obj.status == '6' or order_obj.status == '5':
            # 订单已成  或 已撤 就忽略
            pass
        else:
            log.warning('FF未知订单状态,  {}'.format(order_obj))
   
    return

def sub_on_order_response(context, order_list):
    """_summary_
    撤单成功， 就要重新下单。
    Args:
        context (_type_): _description_
        order_list (_type_): _description_

    Returns:
        _type_: _description_
    """

# 本交易产生的主推：[{'business_amount': 0.0, 'order_id': 'e71d1684c8a74b4ca00b3326c9eb8614', 'order_time': '2022-05-10 15:52:10.780', 'entrust_prop': '0', 'status': '2', 'price': 36.95, 
# 'entrust_no': 700006, 'error_info': '', 'amount': 200, 'stock_code': '600570.SS', 'entrust_type': '0'}]

    for order in order_list:
        symbol = order['stock_code']
        
        
        if order['entrust_type'] == '2' and order['status'] == '8':
            log.warning("撤单已成{}".format(order))
            # 是买单撤单成功， 还是卖单撤单成功？
            symbol =  order['stock_code']
            business_amount =  order['business_amount'] #(成交数量)
            order_id = order['order_id']    # 这个是被撤单的订单编号吗？
            #order_id
           
    
    return

def inner_remove_symbol_from_sell_queue(sell_symbol, context):
    """_summary_
    由于卖出标的后，持仓信息更新有几秒的时延， 需等待一下。     
    
    Args:
        sell_symbol (_type_): _description_
        context (_type_): _description_
    """

    # 最大待待10秒
    loop = 10
    
    while loop > 0:
        # 如果多策略买了相同的股票， 这里就不能调用get_position 接口 检查PT的信息有没有更新。         # 账户持仓， 与可用资金已更新。
        # position = get_position(sell_symbol)
        # if position.amount == 0: 
        #     g.sell_queue.remove(sell_symbol) 
        #     return 
        
        time.sleep(1)
        loop = loop -1 
        pass

    g.sell_queue.remove(sell_symbol) 
    log.warning("卖出成交, 删除卖出队列中股票: {},{};  卖出队列: {}".format(sell_symbol, sub_get_stock_name(sell_symbol), g.sell_queue))

    return 

def inner_callback_sell_dealed(sell_symbol, context):
    """_summary_
    用于卖出标的全部成交时的回调。 如果卖出队列全部成交，   就可以执行买入了。 
    实盘验证： on_trade_response 回调 比 全局持仓对象的Portfolio.cash 与Position 会早1~~6秒左右,  这导致可用资金没有及时到位。
    order_target_value 测试3次: 分别延时6秒, 1秒, 3秒。 order 也有时延， 测试一次时延3秒。
    order_value("518880.SS", 0) 2026-01-16 14:47:00 - WARNING - 股票委托数量为0, 委托取消
    
    Args:
        sell_symbol (_type_): _description_
        context (_type_): _description_
    """
    # 回测场景马上成交， 不用买卖队列； 实盘才需要买卖队列。 
    if not is_trade():
        return

    if sell_symbol not in g.sell_queue or len(g.sell_queue) == 0:
        return

    if len(g.sell_queue) > 1:
        # 还有 2个， 及以上标的， 买入操作还需要再等待
        # 删除 卖出标的
        inner_remove_symbol_from_sell_queue(sell_symbol, context)
        return

    # 删除 卖出标的
    inner_remove_symbol_from_sell_queue(sell_symbol, context)

    buy_list = list(g.buy_queue.keys())
    buy_number = len(list(buy_list))

    if buy_number == 0:
        log.warning("卖出队列已全部成交, 买入队列没有标的: {} ".format(g.buy_queue))
        return

    # 由于所有卖出股票已经成交，  可用资金增加，需要重新计算每支股票的可用资金。
    # 这里PTrade还有问题， 根据实盘验证： 
    # on_trade_response回调 比PT的Position全局变量更新更早, Portfolio 中的可用资金没有 还没有更新？
    available_cash = sub_get_strategy_available_cash(context)

    single_value = available_cash/buy_number
    
    for buy_symbol in buy_list:
        buy_dict = g.buy_queue[buy_symbol]
        if buy_dict['callback'] is not None:
            # buy_dict['callback'] 保存的函数字符串名称， 必须转换成函数。
            callback_func = globals()[buy_dict['callback']]
            callback_func(context)
            pass
        else:
            log.info("重新调整股票 ({}:{}) 买入金额,  原买入金额={:.2f}元， 调整后资金={:.2f} 元".format(buy_symbol, sub_get_stock_name(buy_symbol), buy_dict['value'], single_value))
            sub_order_target_value(buy_symbol, single_value, context)
            
        # 买入完成， 删除买入队列中标的
        del g.buy_queue[buy_symbol]
    
    return

def sub_add_sell_stock_into_queue(sell_symbol, context):
    """_summary_
    往卖方队列增加卖出标的

    Args:
        sell_symbol (_type_): _description_
        context (_type_): _description_
    """
    # 回测场景会马上成交， 不用卖方队列。
    if not is_trade():
        return
    
    # 非字符串
    if isinstance(sell_symbol, str) is False:
        log.error(f"输入参数错误: {sell_symbol}")
        return
    
    if sell_symbol not in g.sell_queue:
        g.sell_queue.append(sell_symbol)
    
    return

def sub_remove_sell_stock_from_queue(sell_symbol, context):
    """_summary_
    往卖方队列删除卖出标的

    Args:
        sell_symbol (_type_): _description_
        context (_type_): _description_
    """
    if sell_symbol in g.sell_queue:
        g.sell_queue.remove(sell_symbol)
    
    return

def sub_add_buy_stock_into_queue(buy_symbol, value, price, context, sell_list=None, callback=None):
    """_summary_
    如果有买操作（买入标的），  紧跟在卖操作之后, 需要等卖操作成交后才能执行买操作,  
    需要增加买卖操作队列,  sub_add_buy_stock_into_queue 放在

    Args:
        buy_symbol (_type_): _description_
        value (_type_): _description_
        price (_type_): _description_
        context (_type_): _description_
        sell_list (_type_, optional): _description_. Defaults to None.
        callback (_type_, optional): _description_. Defaults to None. 如果定义了回调函数， 使用回调函数买入, 否则使用sub_order_target_value买入。
                                    call_back 传入函数名称， 内部保存函数名称字符串， 因为在JSON中函数指针不能持久化。
    """

    all_buy_symbol_list = list(g.buy_queue.keys())
        
    # 防止重入
    if buy_symbol not in all_buy_symbol_list:
        if callback is not None:
            callback = callback.__name__
        buy_dict = {'symbol': buy_symbol, "value": value, "limit_price": price, 'callback': callback}
        g.buy_queue[buy_symbol] = buy_dict  

    # 增加卖方队列
    if sell_list is not None and len(sell_list) > 0:
        for sell_symbol in sell_list:
            sub_add_sell_stock_into_queue(sell_symbol, context)
        
    return

def sub_clear_buy_sell_queue(context):
    """_summary_
    清空所有买卖队列
    """

    current_time = context.blotter.current_dt.strftime("%H:%M:%S")

    if current_time > "15:01:00" and (len(g.sell_queue) > 0 or len(list(g.buy_queue.keys())) > 0):
        log.warning("今天交易已结束, 还有卖队列没有成交, sell queue = {}, buy queue = {}".format(g.sell_queue, g.buy_queue))
    
    # 买卖队列，   如果买入标的 要等 卖队列中标的成交才可以买入， 可增加这个队列。  
    g.sell_queue = []                # 卖出队列，   格式： ["002222.SZ","601111.SZ"]
    g.buy_queue = {}                  # 买入队列,    格式： {'001654.SZ':{"symbol": '001654.SZ', "buy_value": 10000, "limit_price": 10.1, "callback": None}}
    
    return

def inner_check_sell_queue_dealed(context):
    """_summary_
    检查是否所标的都已卖出。
    如果有多策略 有相同标的。 如何检查呢？
    Args:
        stocks (_type_): _description_
        context (_type_): _description_
        g (_type_): _description_

    Returns:
        _type_: _description_  False 有标的没成交， True 所有标的都成交
    """
    stocks = g.sell_queue
    
    # 卖出队列没有标的
    if len(stocks) == 0:
        return True
    
    # holding_dict = get_positions(stocks)
    
    # all_dealed_flag = True
    # for symbol, position in holding_dict.items():
    #     # 有标的还没有成交。 如何多策略有相同标的， 不能检查持仓数量， 必须检查卖出票的订单状态,  或者直接检查卖方队列有没有清空。 
    #     if position.amount > 0:
    #         all_dealed_flag = False
    #         break
 
    return False

def sub_order_tick(symbol, amount, context, priceGear='1', limit_price=None):
    """_summary_

    返回一个委托流水编号(str)
    Args:
        symbol (_type_): _description_
        amount (_type_): _description_
        context (_type_): _description_
        priceGear (str, optional): _description_. Defaults to '1'.
        limit_price (_type_, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """

    if sub_use_orig_portfolio_data():
        order_number = order_tick(symbol, amount, priceGear=priceGear, limit_price=limit_price)
        return order_number

    # 交易场景， 获取 标的的即时价格
    price = limit_price
    if price is None:
        price = sub_get_current_price(symbol, context)

    # 获取当前日期
    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')
    current_time = context.blotter.current_dt.strftime("%H:%M:%S")
    
    # 检查是否全部卖出
    if amount == 0:
        position = sub_get_strategy_positions(context, symbol=symbol)

        #是否已卖出。
        if position.enable_amount == 0:
            log.error("{}, {} 已全部卖出".format(symbol, sub_get_stock_name(symbol)))
            return None

        amount = 0 - abs(position.enable_amount)
    
    if amount < 0:
        positions = sub_get_strategy_positions(context)
        if symbol not in positions:
            log.error("卖出操作失败, 持仓数据错误， 不存在的持仓{}".format(symbol))
            return None

        position = positions[symbol]

        position.sell_date = current_date
        # 可用数量变成0
        position.enable_amount = position.enable_amount - abs(amount)

        sub_order = subOrder()

        # 本次卖出总量
        sub_order.order_amount = 0 - abs(amount)
        sub_order.dt = current_date + " " + current_time
        sub_order.symbol = symbol
        sub_order.order_price = price

        # 卖出操作, 回测场景： order_target_value 先回调 on_trade_response, 再
        if not is_trade():
            position.order_dict["bt_order_id"] = sub_order

        order_id = order_tick(symbol, amount)

        if order_id is None:
            log.error("卖出错误, 卖出票={}, {}, order_flow_no={}".format(symbol, sub_get_stock_name(symbol) , order_id))
            return None

        position.order_dict[order_id] = sub_order 

        if not is_trade():
            del position.order_dict["bt_order_id"]

    else:
        # 校验是否已经持有 买入的股票,   避免多策略冲突。
        holding_dict = get_positions()
        holding_list = list(holding_dict.keys())
        if symbol in holding_list:
            hold_position = holding_dict[symbol]
            if hold_position.amount > 0:
                log.warning("已经持有买入标的, 不再买入: {symbol}, {name}".format(symbol=symbol, name=sub_get_stock_name(symbol)))
                return None
            
        # 买入操作
        portfolio = inner_sub_get_strategy_portfolio(context)    
        # 可用资金
        used_money = amount * price 
        value = used_money
        if value > portfolio.cash:
            value = portfolio.cash*0.999    # 留出手续费
            new_amount = int(value/100/price)*100
            if new_amount < 100:
                log.error("买入金额太小, 股数小于100. 买入金额={},  买入票={}".format(value, symbol))
                return None
            log.error("买入 {symbol}, 金额大于可用金额.  买入金额={value} > 可用金额{available_cash}, 重新调整买入数量={new_amount}".format(symbol=symbol, value=value, available_cash=portfolio.cash, new_amount = new_amount))
            amount = new_amount
        
        if value > context.portfolio.cash:
            value = portfolio.cash*0.999    # 留出手续费
            new_amount = int(value/100/price)*100
            if new_amount < 100:
                log.error("买入金额太小, 股数小于100. 买入金额={},  买入票={}".format(value, symbol))
                return None
            log.error("买入金额大于总仓可用金额.  买入金额={value} > 可用金额{available_cash}。 买入票={symbol}, 重新调整买入数量={new_amount}".format(value=value, available_cash=context.portfolio.cash, symbol=symbol, new_amount = new_amount))
            amount = new_amount
        
        # 可用资金
        used_money = amount * price 
        portfolio.cash = portfolio.cash - used_money 
       
        sub_position = subPosition() 
        sub_order = subOrder()
        sub_order.dt = current_date + " " + current_time
        sub_order.symbol = symbol
        sub_order.order_amount = amount
        sub_order.order_price = price
        sub_order.order_cash = used_money
        sub_order.business_amount = 0
        sub_order.business_balance = 0

        position_dict = {
                'buy_date':  current_date,    # 买入日期
                'buy_time':  current_time ,   # 买入时间
                'sell_date':  None,   # 卖出日期
                'sid':  symbol ,        # sid 标的代码
                'name': sub_get_stock_name(symbol),
                'enable_amount':  0,  # 可用数量
                'amount': 0,         # 总持仓数量
                'last_sale_price': None, # 最新价格
                'cost_basis': price,      # 持仓成本价格
                'order_dict': {}         # 这个标的订单
            }
        sub_position.__dict__.update(position_dict)

    
        portfolio.positions[symbol] = sub_position

        #Fix BUG: 回测场景中, on_trade_response - 交易主推(可选)  函数先回调， order函数才会返回。 这时order_id 还 没生成。 收盘校验就会出错的。
        # 这里需要检查  on_trade_response 有没有 回调成功。
        if not is_trade():
            sub_position.order_dict["bt_order_id"] = sub_order
            
        # order_id = order(symbol, amount, limit_price=price)
        # order_id = order_target_value(symbol, value, limit_price=price)
        order_id = order_tick(symbol, amount, limit_price=limit_price)

        if order_id == "None" and  order_id is None:
            log.error("order_id买入出错, 买入金额={},  买入票={}:{}, 数量 = {}, 价格 = {}, order_id={}".format(used_money, symbol, sub_get_stock_name(symbol), amount, price, order_id))
            return None

        # 回测场景
        if not is_trade():
            del sub_position.order_dict["bt_order_id"]
        else: 
            sub_position.order_dict[order_id] = sub_order
            pass

    return order_id

def sub_order_target_value(symbol, value, context, sell_list = None, limit_price = None):
    """_summary_
    买卖操作
    
    PT的API说明：  
    实盘验证： order_target_value(security, value, limit_price=None) 有时延问题。
    柜台返回持仓数据体现当日变化(由柜台配置决定)：交易场景中持仓信息同步有时滞，一般在6秒左右。 
    
    Args:
        strategy_name (_type_): _description_
        symbol (_type_): _description_
        value (_type_): _description_
        context (_type_): _description_
        g (_type_): _description_

    Returns:
        _type_: _description_
        None:   买入失败
        True:   进入买入队列
        order_id: 买入id
    """

    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        order_id = order_target_value(symbol, value)
        return order_id

    # 检测 卖出，还是买入股票。
    positions = sub_get_strategy_positions(context)
    operated_amount = 0
    if symbol in positions and value > 0:
        position = positions[symbol]
        price = position.last_sale_price
        position_value = position.amount * position.last_sale_price 

        buy_in_value = value - position_value
        # operated_amount 大于0表示买入股票数量，  小于0表示卖出股票数量。
        operated_amount = int(buy_in_value/100/price)*100
        if operated_amount < 100 and operated_amount > -100:
            # 调整数量不足100， 不买入,  也不卖出。
            log.info(f"调整数量不足100。 {symbol}:{sub_get_stock_name(symbol)}, 市值 = {position_value}, 目标金额 = {value}, 价格={price}, 数量={operated_amount}")
            return True
 
    # 实盘场景： 如果买入的标的symbol， 必须在sell_list成交后才能买入， 先入队列。
    # 回测场景的买卖操作没有时延。
    if is_trade() and value > 0 and (sell_list is not None):
        sub_add_buy_stock_into_queue(symbol, value, limit_price, context, sell_list) 
        log.info("买入标的入队等待={}, {},  卖出队列={}".format(symbol, sub_get_stock_name(symbol), g.sell_queue))
        
    
    # 实盘场景： 买操作必须检查， 检查相关的卖队列是否标的有没有成交。
    if is_trade() and value > 0 and (sell_list is not None or len(g.sell_queue) > 0):
        if inner_check_sell_queue_dealed(context) is False:
            log.warning("买入标的={}, {},  还有卖队列没有成交={}".format(symbol, sub_get_stock_name(symbol), g.sell_queue))
            sub_add_buy_stock_into_queue(symbol, value, limit_price, context, sell_list) 
            return True
        else:
            # 所有卖队列都已成交， 可以买入了。 删除买队列中的 待买入标的
            if symbol in g.buy_queue:
                del g.buy_queue[symbol]

    # 交易场景， 获取 标的的即时价格
    price = limit_price
    if price is None:
        price = sub_get_current_price(symbol, context)

    # 获取当前日期
    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')
    current_time = context.blotter.current_dt.strftime("%H:%M:%S")
            
    if value == 0 or operated_amount < 0:
        if symbol not in positions:
            log.error("卖出操作失败, 持仓数据错误， 不存在的持仓{}".format(symbol))
            return None

        position = positions[symbol]

        # 持仓数量检验， 可能与其他策略持有相同股票。 不能卖出其他策略股票。
        main_position = get_position(symbol)
        if position.enable_amount < main_position.enable_amount:
            log.warning("本策略股票({}, {}): 可用持仓数量{}小于 总仓股票持仓可用数量{}; 可能与其他策略持仓相同股票。".format(symbol, sub_get_stock_name(symbol), position.enable_amount , main_position.enable_amount))
            # position.enable_amount = real_position.enable_amount
            # position.amount = real_position.amount
        elif position.enable_amount > main_position.enable_amount:
            lost_market_value = price * (position.enable_amount - main_position.enable_amount) 
            # FFFFFFFFixed 分仓发现了 损失金额， 是否程序恢复， 还是手动恢复？ 暂时手动恢复吧。
            # sub_portfolio = sub_get_strategy_portfolio(context)
            # sub_portfolio.cash = sub_portfolio.cash + lost_market_value
            if position.reorder_timeout is True:
                log.error("可能重新下单时总仓持仓数据还没有恢复: 股票({}, {}): 分仓持仓数量{}大于总仓股票持仓数量{}; 恢复损失金额:{}".format(symbol, sub_get_stock_name(symbol), position.enable_amount , main_position.enable_amount, lost_market_value))
            else:
                log.error("总分仓数据错误: 本策略股票({}, {}): 分仓持仓数量{}大于总仓股票持仓数量{}; 恢复损失金额:{}".format(symbol, sub_get_stock_name(symbol), position.enable_amount , main_position.enable_amount, lost_market_value))
                position.enable_amount = main_position.enable_amount
                position.amount = main_position.amount

        if position.enable_amount != position.amount:
            log.error("分仓持仓数据错误11: 本策略股票({}, {}): 持仓可用数量{} 不等于 总数量{}".format(symbol, sub_get_stock_name(symbol), position.enable_amount, position.amount))

        if position.enable_amount == 0 :
            log.error("分仓可卖数量为0: 股票({}, {}):  可用数={}".format(symbol, sub_get_stock_name(symbol), position.enable_amount))
            return None

        if main_position.enable_amount == 0:
            log.error("总仓可卖数量为0: 股票({}, {}): 可用数={}, position = {}".format(symbol, sub_get_stock_name(symbol), main_position.enable_amount, position))
            # 暂时不返回， 可能重新下单时总仓持仓数据还没有恢复, 此时可能 main_position.enable_amount 为0 
            # return None

        sub_order = subOrder()

        sub_order.dt = current_date + " " + current_time
        sub_order.symbol = symbol
        sub_order.order_price = price
        # 本次卖出总量
        sub_order.order_amount = 0 - abs(position.enable_amount)
        if operated_amount < 0:
            sub_order.order_amount = operated_amount
        # 记录本次下单原始金额
        sub_order.orig_order_money = value

        # 可用数量变成0
        position.enable_amount = position.enable_amount + operated_amount
        position.sell_date = current_date
        

        # 卖出操作, 回测场景： order_target_value 先回调 on_trade_response, 再
        if not is_trade():
            position.order_dict["bt_order_id"] = sub_order

        # order_id = order(symbol, sub_order.order_amount, limit_price=price)
        order_api_type = getattr(g, "order_api_type", None)
        order_api_type = getattr(g, "sell_api_type", None)  #兼容处理
        
        order_id = None

        #  "order_market_five_dealed" - 按市价进行委托(五档即时成交),    
        if order_api_type == 'order_market_five_dealed':
            market_type = 1  #1：最优五档即时成交剩余转限价(上海)
            if symbol.endswith('SZ'):
                market_type = 4  # 4：最优五档即时成交剩余撤销；(深圳)

            order_id = order_market(symbol, sub_order.order_amount, market_type, limit_price=price)
        ## "order_market_peer_price" - 按市价进行委托(对手最优价成交),  
        elif order_api_type == 'order_market_peer_price':
            market_type = 0 # 0：对手方最优价格；
            order_id = order_market(symbol, sub_order.order_amount, market_type, limit_price=price)

        # "order_target_value"--调整股票持仓市值到value价值 (多策略同标的时不能用, 否则会将其他策略标的也处理掉)
        elif order_api_type == 'order_target_value':
            ## 如何有多策略买卖相同的标的？ 就不能使用 order_target_value 接口， 必须使用 order 接口， 指定买卖数量， 与价格。
            order_id = order_target_value(symbol, value, limit_price=limit_price)
            
        # "order"-按数量买卖
        else:
            order_id = order(symbol, sub_order.order_amount, limit_price=limit_price)
        

        position.order_dict[order_id] = sub_order 

        if not is_trade():
            del position.order_dict["bt_order_id"]
        elif getattr(g, "auto_append_sell_queue", True):
            #检查是否 所有卖出标的， 统一入卖方队列。 不管后面有没有买入股票。
            sub_add_sell_stock_into_queue(symbol, context)

    else:
        ## 如何有多策略买卖相同的标的？ 就不能使用 order_target_value 接口， 必须使用 order 接口， 指定买卖数量， 与价格。
        order_api_type = getattr(g, "order_api_type", None)
        if order_api_type == "observe_not_buy":
            log.info(f"配置只观察不买入。 放弃买入={symbol}:{sub_get_stock_name(symbol)}")
            return None
        
        # 买入操作
        portfolio = inner_sub_get_strategy_portfolio(context)    
        if value > portfolio.cash and operated_amount == 0:
            log.error("买入金额大于可用金额.  买入金额={value} > 可用金额{available_cash}。 买入票={symbol}:{name}".format(value=value, available_cash=portfolio.cash, symbol=symbol, name=sub_get_stock_name(symbol)))
            value = portfolio.cash*0.999    # 留出手续费
        
        if value > context.portfolio.cash and operated_amount == 0:
            log.error("买入金额大于总仓可用金额.  买入金额={value} > 可用金额{available_cash}。 买入票={symbol}:{name}".format(value=value, available_cash=context.portfolio.cash, symbol=symbol, name=sub_get_stock_name(symbol)))
            value = portfolio.cash*0.999    # 留出手续费

        # 校验是否已经持有 买入的股票,   避免多策略冲突。
        holding_dict = get_positions()
        holding_list = list(holding_dict.keys())
        if symbol in holding_list:
            hold_position = holding_dict[symbol]
            if hold_position.amount > 0 and is_etf_lof_fund(symbol):
                # 不同策略可以持有相同ETF
                log.warning("请注意其他策略已经持有相同的ETF: {symbol}, {name}".format(symbol=symbol, name=sub_get_stock_name(symbol)))
            elif hold_position.amount > 0:
                # 不同策略 暂时不允许持有相同股票。 
                log.warning("请注意其他策略已经持有相同股票: {symbol}, {name}".format(symbol=symbol, name=sub_get_stock_name(symbol)))
                # return                            
        
        amount = int(value/100/price)*100
        if amount < 100:
            log.error("买入金额太小, 股数小于100. 买入金额={},  买入票={}".format(value, symbol))
            return None
        
        # 检查��不是调整买入更多数量。
        if operated_amount > 0:
            amount = operated_amount
        
        #order(security, amount, limit_price=None) 该接口用于买卖指定数量为amount的股票，同时支持国债逆回购
        # order_id = order_target(symbol, amount, limit_price=price)
        # 可用资金减少。
        used_money = amount * price 
        portfolio.cash = portfolio.cash - used_money 
       
        sub_position = subPosition() 
        sub_order = subOrder()
        sub_order.dt = current_date + " " + current_time
        sub_order.symbol = symbol
        sub_order.order_amount = amount
        sub_order.order_price = price
        sub_order.order_cash = used_money
        sub_order.business_amount = 0
        sub_order.business_balance = 0
        # 记录本次下单原始金额
        sub_order.orig_order_money = value


        sub_position.buy_date = current_date
        sub_position.buy_time = current_time
        sub_position.sid = symbol
        sub_position.name = sub_get_stock_name(symbol)
        sub_position.enable_amount = 0
        sub_position.amount = 0
        sub_position.cost_basis = price
        sub_position.last_sale_price = price
    
        # 检查是否已经有这个股票的持仓
        if symbol in portfolio.positions:
            # 已经这支股票的持仓,  新旧持仓进行合并；
            old_sub_position = portfolio.positions[symbol]
            
            if old_sub_position.amount > 0 or old_sub_position.enable_amount > 0:
                log.info(f"新增持仓, 还有旧持仓. old position = {old_sub_position}")
                #持仓数量进行合并
                sub_position.amount = sub_position.amount + old_sub_position.amount
                sub_position.enable_amount = sub_position.enable_amount + old_sub_position.enable_amount
            #合并订单
            sub_position.order_dict.update(old_sub_position.order_dict) 

            portfolio.positions[symbol] = sub_position
            pass
        else:
            portfolio.positions[symbol] = sub_position

        #Fix BUG: 回测场景中, on_trade_response - 交易主推(可选)  函数先回调， order函数才会返回。 
        # 这时order_id 还 没生成。 收盘校验就会出错的。
        # 这里需要检查  on_trade_response 有没有 回调成功。
        if not is_trade():
            sub_position.order_dict["bt_order_id"] = sub_order

        order_id = None
        
        #  "order_market_five_dealed" - 按市价进行委托(五档即时成交),    
        if order_api_type == 'order_market_five_dealed':
            market_type = 1  #1：最优五档即时成交剩余转限价(上海)
            if symbol.endswith('SZ'):
                market_type = 4  # 4：最优五档即时成交剩余撤销；(深圳)

            order_id = order_market(symbol, amount, market_type, limit_price=price)
        ## "order_market_peer_price" - 按市价进行委托(对手最优价成交),  
        elif order_api_type == 'order_market_peer_price':
            market_type = 0 # 0：对手方最优价格；
            order_id = order_market(symbol, amount, market_type, limit_price=price)

        # "order_target_value"--调整股票持仓市值到value价值 (多策略同标的时不能用, 否则会将其他策略标的也处理掉)
        elif order_api_type == 'order_target_value':
            ## 如何有多策略买卖相同的标的？ 就不能使用 order_target_value 接口， 必须使用 order 接口， 指定买卖数量， 与价格。
            order_id = order_target_value(symbol, value, limit_price=limit_price)
        else:
            order_id = order(symbol, amount, limit_price=limit_price)
            

        if order_id == "None" or order_id is None:
            log.error("sub买入出错, 买入票={}:{}, 买入金额={}, price = {}, order_id={}".format(value, symbol, sub_get_stock_name(symbol), limit_price, order_id))

            # 买入错误,  恢复可用资金。 并删除持仓。
            portfolio.cash = portfolio.cash + sub_order.order_cash
            if sub_position.amount == 0:
                inner_del_strategy_positions(symbol)
            return order_id

        sub_position.order_dict[order_id] = sub_order
        # 回测场景, 已返回真实的order_id, 删除暂时的回测 bt_order_id
        if not is_trade():
            del sub_position.order_dict["bt_order_id"]
            pass
        else: 
            # 实盘场景买入数量，价格可能不一致，同步刷新一下。 
            # PT接口的问题：get_order 取不到委托价格, ## limit -- 指定价格, 为limit_price=price， 不传入为None，这个不是委托价格，不能取这个字段。
            current_order_obj = get_order(order_id)[0]
            # get_all_orders(security=None) 返回为dict list,可以取得委托价格。 
            current_order_list = get_all_orders(security=symbol)  

            current_order = None
            
            # 通过委托编号， 查到匹配的订单号
            for order_loop in current_order_list:
                if order_loop['entrust_no'] == current_order_obj.entrust_no:
                    current_order = order_loop
                    break

            sub_order.entrust_no = current_order_obj.entrust_no
            #找到相应的订单
            if current_order is not None:
                log.info(current_order)
                sub_order.order_price = current_order['price']  ## limit -- 指定价格为None，这个不是委托价格，不能取这个字段。
                real_order_cash = abs(current_order['amount']*current_order['price'])
                sub_order.order_cash = real_order_cash
                sub_order.order_amount = current_order['amount']
                sub_order.order_price = current_order['price']

                # 按真实锁定金额 修改 可用资金
                portfolio.cash = portfolio.cash + used_money - real_order_cash 
            pass
       
    return order_id
    
def inner_after_trading_settlement(position:subPosition, sub_order:subOrder, context):
    """_summary_
    盘后结算： 扣除佣金， 恢复未成交金额
    Args:
        position (subPosition): _description_
        sub_order (subOrder): _description_
        g (_type_): _description_
        context (_type_): _description_
    """
    
    # 买入已成: symbol=002890.SZ, name=弘宇股份, 下单数价=1100, 14.98元, 成交数=1100, 成交价=14.982247000000001
    # 为什么买入价总是比 下单价大了一点？

    current_time = context.blotter.current_dt.strftime("%H:%M:%S")
    
    # 结算只能是一次, # 已完成结算，直接退出。
    if sub_order.settlemented is True:
        if current_time > '15:10:00':
            #盘后结算， 可用数量 与总量一致。
            position.enable_amount = position.amount 
        return
    else:
        # 未完成结算
        sub_order.settlemented = True

    # 部成的结算在算后。
    if current_time > '15:10:00':
        #盘后结算， 可用数量 与总量一致。
        position.enable_amount = position.amount 

    symbol = position.sid 

    # 计算成交总金额,
    used_money = sub_order.business_balance
    business_amount = sub_order.business_amount
    business_balance = sub_order.business_balance
        
                    
    # 印花税 + 佣金 trade_response的响应已经扣除了费用。
    tax_commission = sub_calculate_commission_and_tax(symbol, sub_order, used_money, context) 
    #2025-02-11 10:30:00 - WARNING - 本策略可用资金大于总仓位可用资金, 本策略可用资金=18628.988400000002, 总仓可用资金=18606.445766664725
    # 卖出成交扣除佣金时机： 收到成交通知就扣除了佣金。

    # 计算成交均价。
    if business_amount == 0:
        log.error(f"错误成交数量 business_amount = {business_amount}, position={position}, order={sub_order}")    
    business_price = abs(custom_round((abs(used_money) + tax_commission)/abs(business_amount), 6))
    #记录本次订单成交均价， 与手续费。
    sub_order.business_price = business_price
    sub_order.tax_commission = tax_commission
    
    portfolio = inner_sub_get_strategy_portfolio(context)
    
    # 应该最后再算佣金吧， 这里算佣金会不会双算呢？  减去佣金, 不应该 
    portfolio.cash = portfolio.cash - tax_commission 
    
    #盘中买入已成， 盘后不再处理。 盘后可用数量需要与全部数量相等。 
    direction = "卖出"
    benefit_selled = None
    benefit_rate = 0
    
    if sub_order.order_amount > 0:
        direction = "买入"
        # 按成交价， 算出成本价。
        position.cost_basis = business_price
    else:
        # 如果是卖出， 计算盈利金额,  利润率。
        benefit_selled =  abs(business_balance) - abs(business_amount* position.cost_basis) - abs(tax_commission) 
        benefit_rate = (business_price - abs(position.cost_basis))/abs(position.cost_basis) 
        
        
    log.info("{direction}盘后结算: symbol={stock_code}, {stock_name}, 下单数={order_amount}, 成本价={cost_basis}元, 成交数={business_amount}, 成交均价={business_price}, 成交额={business_balance}, 手续费={tax_commission}, 利润={benefit_selled}, 利润率={benefit_rate:.2%}".format(
        direction=direction,
        stock_code=symbol,
        stock_name=sub_get_stock_name(symbol),
        order_amount=sub_order.order_amount,
        cost_basis = position.cost_basis,
        # order_price=sub_order.order_price,
        business_amount=business_amount,
        business_price=business_price,
        business_balance=abs(business_balance),
        tax_commission=tax_commission,
        benefit_selled = benefit_selled,
        benefit_rate = benefit_rate
    ))

    # 校验： 买入已成， 但是 买入总数量，  与累计成交数量不一致。 
    if abs(sub_order.order_amount) != abs(business_amount) and (not is_trade()):
        # 2025-11-20 09:33:50 - INFO - 买入累计已成: symbol=000586.SZ, name=汇源通信, 下单数价=7600, 12.99元, 成交数=1200/7600, 成交价=12.97                
        # 2025-11-20 15:30:00 - INFO - 盘后买入已成结算: symbol=000586.SZ, 汇源通信, 下单数价==7600, 12.99元, 成交数=6900, 成交价=12.978, 手续费=31.23                
        log.warning("下单总数量 与 累计成交数量不一致。symbol ={}; sub_order={};  business_amount={} ".format(symbol, sub_order, business_amount))
        
    # 买入时： 恢复未成交的资金。
    no_dealed_amount = abs(sub_order.order_amount) - abs(business_amount)
    if sub_order.order_amount > 0:
        
        # 1、计算未成交的股数，  需要恢复金额。
        no_dealed_money = no_dealed_amount * sub_order.order_price
        
        # 2、比较锁定金额  与  已成交的金额。  成交金额可能比锁定金额 多， 或者少，也要恢复。
        no_order_cash = (business_amount)*sub_order.order_price - abs(business_balance)
        portfolio.cash = custom_round(portfolio.cash + no_dealed_money + no_order_cash, 2) 

    return

def inner_update_sub_position(trade, position:subPosition, sub_order:subOrder, context):
    """_summary_
    更新持仓信息。
    Args:
        order (_type_): _description_ 订单对象，
        position (_type_): _description_ 持仓对象
        strategy_name (_type_): _description_ 策略名，唯一
        g (_type_): _description_  全局变量
        context (_type_): _description_ 运行上下文
    """
    current_time = context.blotter.current_dt.strftime("%H:%M:%S")

  
    #  trade_list
    # [{'entrust_no': '9538', 'business_time': '2025-10-28 10:31:01', 'stock_code': '002193.SZ', 'entrust_bs': '1', 'business_amount': 3000, 'business_price': 5.49, 
    # 'business_balance': 16470.0, 'business_id': '1010000432942590', 'status': '8', 'cancel_info': ' ', 'withdraw_no': '0', 'real_type': '0', 'real_status': '0', 
    # 'order_id': 'c78bcb3375c344c3937df76358b6892d'}]
    symbol = trade["stock_code"] 

    # 注意： 已成与部成的消息可能乱序。
    if trade["entrust_bs"] == '1' and trade["status"] == '8':

        if current_time < "15:10:00":
            # print("SSSSSSS", sub_order, trade)
            # 买入已成
            log.info("买入已成: symbol={stock_code}, name={stock_name}, 下单数价={order_amount}, {order_price}元, 成交数={business_amount}, 成交价={business_price}".format(
                stock_code=trade['stock_code'],
                stock_name=sub_get_stock_name(symbol),
                order_amount=sub_order.order_amount,
                order_price=sub_order.order_price,
                business_amount=trade['business_amount'],
                business_price=trade['business_price']
            ))
            position.amount =  position.amount + trade["business_amount"]      # 成交数量 倒底是哪个字段？
            sub_order.business_amount = sub_order.business_amount + trade["business_amount"]   # 本次买入累计成交数量
            sub_order.business_balance = sub_order.business_balance + trade["business_balance"]   # 本次买入累计成交金额
            sub_order.business_price = trade["business_price"]                 # 本次买入累计成交价
            
            # 已全部成交，可以进行结算了。
            if sub_order.business_amount >= sub_order.order_amount:
                inner_after_trading_settlement(position, sub_order, context)

        else:
            # 买入已成盘后结算
            inner_after_trading_settlement(position, sub_order, context)

        return
    elif trade["entrust_bs"] == '1' and trade["status"] == '7':
        # 部成 怎么处量： 盘中只打印信息， 盘后统一计算佣金。 
        # position["amount"] = position["amount"] + order.filled
        
        # 收盘前的部成会有多条消息，  部成在收盘后统一处理。  
        if current_time < "15:10:00":
            position.amount =  position.amount + trade["business_amount"]      # 成交数量 倒底是哪个字段？

            sub_order.business_amount = sub_order.business_amount + trade["business_amount"]   # 本次买入累计成交数量
            sub_order.business_balance = sub_order.business_balance + trade["business_balance"]   # 本次买入累计成交金额, 
            sub_order.business_price = trade["business_price"]      # 本次部成价格, 

            # 全部成交， 
            if sub_order.business_amount >= sub_order.order_amount: 
                log.info("买入累计已成: symbol={stock_code}, name={stock_name}, 下单数={order_amount},  下单价={order_price}元, 累计成交数={total_business_amount}, 本次成交数={business_amount}, 本次成交价={business_price}".format(
                    stock_code=trade['stock_code'],
                    stock_name=sub_get_stock_name(symbol),
                    order_amount=sub_order.order_amount,
                    order_price=sub_order.order_price,
                    total_business_amount=sub_order.business_amount,
                    business_amount=trade['business_amount'],
                    business_price=trade['business_price']
                ))            
                inner_after_trading_settlement(position, sub_order, context)
            else:
                log.info("买入部成: symbol={stock_code}, name={stock_name}, 下单数={order_amount},  下单价={order_price}元, 累计成交数={total_business_amount}, 本次成交数={business_amount}, 本次成交价={business_price}".format(
                    stock_code=trade['stock_code'],
                    stock_name=sub_get_stock_name(symbol),
                    order_amount=sub_order.order_amount,
                    order_price=sub_order.order_price,
                    total_business_amount=sub_order.business_amount,
                    business_amount=trade['business_amount'],
                    business_price=trade['business_price']
                ))     
                       
        else:
            # 买入部成， 盘后结算。
            inner_after_trading_settlement(position, sub_order, context)
        
        return            
    # elif trade["entrust_bs"] == '1' and (trade["status"] == '9'):
    # # 废单， 价格笼子没过。  
        # pass
    #                                              订单状态: 废单                    状态：已撤,         5是部撤
    elif trade["entrust_bs"] == '1' and (trade["status"] == '9' or trade["status"] == '6' or trade["status"] == '5'):
# 2025-11-24 11:16:00 - INFO - 后端服务 操作账户股票代码：【002264.SZ】 委托号：【19487】 发起撤单
# 2025-11-24 11:16:00 - INFO - on_trade_response [{'entrust_no': '19487', 'business_time': '2025-11-24 11:16:00', 'stock_code': '002264.SZ', 'entrust_bs': '1', 'business_amount': -1100, 
# 'business_price': 8.92, 'business_balance': -9812.0, 'business_id': '1010000581572195', 'status': '6', 'cancel_info': ' ', 'withdraw_no': '19487', 'real_type': '2', 'real_status': '0', 
# 'order_id': '76c109e6fbbd428185050a0adcf6948a'}]        
        # 盘中交易通知： 买入 撤单， 删除持仓。
        # del my_positions[symbol]??
        if current_time < "15:10:00":
            log.warning("买单{}, Trade={}, sub_order = {}".format(get_order_status_name(trade['status']), trade, sub_order))
            
            sub_portfolio = inner_sub_get_strategy_portfolio(context)

            # 买入撤单， 恢复撤单的可用资金。 两种情况： 1、买入全部撤单，   2、 买入已经部成， 部分撤单。
            if trade["status"] == '6':
                used_money = sub_order.order_cash
                # 校验一下： 理论上，锁定金额需要大于等于撤单金额
                if abs(used_money) < abs(trade["business_balance"]):
                    log.warning("撤单金额小于锁定金额.  锁定={},  撤单={}".format(used_money, trade["business_balance"]))
            # 买入废单， 价格错误
            elif trade["status"] == '9':
                used_money = sub_order.order_cash
            else:
                #部撤的订单。
                used_money = abs(trade['business_balance'])
                
            sub_portfolio.cash = sub_portfolio.cash + used_money
            
            # 订单完成结算。
            sub_order.settlemented = True 
        # 价格超笼子的废单响应。
# 2026-02-04 09:26:00 - WARNING - 买单废单, order={'entrust_no': '2', 'business_time': '2026-02-04 09:25:59', 'stock_code': '000880.SZ', 
# 'entrust_bs': '1', 'business_amount': 600, 'business_price': 0.0, 'business_balance': 0.0, 'business_id': '8888000649236805', 'status': '9', 
# 'cancel_info': '价格错误', 'withdraw_no': '0', 'real_type': '0', 'real_status': '2', 'order_id': 'b447f97119d640f1b305fd633134d84d', 'amount': 600}
# 2026-02-04 09:26:00 - INFO - 超时未成交撤单，重新下单.  标的=000880.SZ, 潍柴重机;  金额 = 0.0
            # 获取重新下单金额， 使用本次下单的原始金额。
            order_money = used_money
            if sub_order.orig_order_money is not None and trade["status"] == '6':
                order_money = sub_order.orig_order_money

            # 买单撤单成功, 重新下单。  如果是超时未成交的撤单，需要重新下单。
            if position.reorder_timeout is True and (trade["status"] == '6'  or trade["status"] == '5'):  
                log.info("超时未成交撤单，重新下单.  标的={}, {};  金额 = {}".format(symbol, sub_get_stock_name(symbol), order_money))
                # 实盘由于总仓的资金数据更新有延迟几秒， 撤单资金还没有到账。 需要等待一会再下单。  实盘测试延迟： 5秒，4秒，6秒，5秒，
                time.sleep(10) 
                position.reorder_timeout = False
                sub_order_target_value(symbol, order_money, context)
            else:
                log.info("错误委托, 标的={}, {};  金额 = {}".format(symbol, sub_get_stock_name(symbol), order_money))
                pass
        else:
            log.warning("错误状态订单11, 买单{}, Trade={}, sub_order = {}".format(get_order_status_name(trade['status']), trade, sub_order))

            #如果订单没有完成结算,  并且订单是废单， 需要恢复买入金额。
            if sub_order.settlemented is False and trade["status"] == '9':
                used_money = sub_order.order_cash
                sub_portfolio = inner_sub_get_strategy_portfolio(context)
                used_money = sub_order.order_cash
                sub_portfolio.cash = sub_portfolio.cash + used_money
                sub_order.settlemented = True
            pass
        return
    elif trade["entrust_bs"] == '1' and (trade["status"] == '2'):
        # 买入已报， 还未成交
        
        # 买单收盘后仍未成交
        if current_time > "15:01:00":
            log.warning("买单收盘后仍未成交{}".format(trade))
            
            used_money = sub_order.order_cash  
            sub_portfolio = inner_sub_get_strategy_portfolio(context)
            # 没有买入成功， 恢复可用资金。
            sub_portfolio.cash = sub_portfolio.cash + used_money 
            # 订单完成结算。
            sub_order.settlemented = True 
        else:
            log.warning("错误状态订单22, 买单{}, Trade={}, sub_order = {}".format(get_order_status_name(trade['status']), trade, sub_order))
            pass

        return
    # 卖单 可能多条已成， 部成消息， 还可能乱序。
    elif trade["entrust_bs"] == '2' and trade["status"] == '8':
        # 卖出已成, 删除持仓

        # 收盘前的部成会有多条消息，  部成在收盘后统一处理。  
        if current_time < "15:05:00":
        
            position.amount =  position.amount - abs(trade["business_amount"]) 

            # 成交数量累计
            sub_order.business_amount = sub_order.business_amount - abs(trade["business_amount"])
            sub_order.business_balance = sub_order.business_balance - abs(trade["business_balance"])

            # 盘后结算只减去佣金， 盘中增加可用资金
            used_money = abs(trade["business_balance"]) 
            sub_portfolio = inner_sub_get_strategy_portfolio(context)
            sub_portfolio.cash = sub_portfolio.cash + used_money

            log.info("盘中卖出已成, symbol={symbol}, name={stock_name}, 下单数={order_amount}, 成交数={business_amount},  成交价={business_price}, 成交金额={business_balance}, 可用金额={av_cash};".format(
                symbol=symbol,
                stock_name=sub_get_stock_name(symbol),
                order_amount=sub_order.order_amount,
                business_amount=trade['business_amount'],
                business_price=trade['business_price'],
                business_balance=trade['business_balance'],
                av_cash=sub_portfolio.cash,
            ))

            # 检查买卖队列有没有等待买入的标的。
            # 异常场景：如果是  多个部成消息 + 一个已成消息。 并且是消息乱序了？
            if abs(sub_order.order_amount) == abs(sub_order.business_amount):
                # 卖出已成，检查是否有标的正在等待买入
                inner_after_trading_settlement(position, sub_order, context)
                inner_callback_sell_dealed(symbol, context)
            else:
                log.warning("卖出已成但成交数量不足, 可能多个部成消息乱序了。symbol={symbol}, name={stock_name}, 未成交数={no_deal_amount}, 成交数={business_amount}".format(
                    symbol=symbol,
                    stock_name=sub_get_stock_name(symbol),
                    no_deal_amount=position.amount,
                    business_amount=trade['business_amount'],
                ))
        else:
            #  卖出已成,  盘后结算
            inner_after_trading_settlement(position, sub_order, context)
            
        return
    elif trade["entrust_bs"] == '2' and trade["status"] == '7':
        # 卖出部成， 部成的成交通知在收盘后统一计算。 如查部成全部成交呢？
        # print(f"卖出部成{trade}")
        # log.info(f"卖出部成, {symbol}, 下单数={trade['amount']}, 成交数{trade['business_price']}")

        # 收盘前的部成会有多条消息，  部成在收盘后统一处理。  
        if current_time < "15:10:00":
            position.amount = position.amount - abs(trade["business_amount"])

            # 成交数量累计,  成交金额累计, 
            sub_order.business_amount = sub_order.business_amount - abs(trade["business_amount"])
            sub_order.business_balance = sub_order.business_balance - abs(trade["business_balance"])

            
            # 盘后结算只减去佣金， 盘中增加可用资金
            # used_money = abs(trade["business_amount"] * trade["business_price"]) 
            used_money = abs(trade["business_balance"])
            sub_portfolio = inner_sub_get_strategy_portfolio(context)
            sub_portfolio.cash = sub_portfolio.cash + used_money
            
            # 卖出累计已全部成交， 就需要恢复 可用资金。 否则可用资金留到盘后再统一恢复。
            if abs(sub_order.business_amount) >= abs(sub_order.order_amount):

                log.info("卖出累计已成, symbol={symbol}, name={stock_name}, 下单数={order_amount}, 累计成交数={total_order_amount}, 本次成交数={business_amount}, 本次成交价={business_price}, 本次成交金额={business_balance}, 可用金额={av_cash}; ".format(
                    symbol=symbol,
                    stock_name=sub_get_stock_name(symbol),
                    order_amount=sub_order.order_amount,
                    total_order_amount=sub_order.business_amount,
                    business_amount=trade['business_amount'],
                    business_price=trade['business_price'],
                    business_balance=trade['business_balance'],
                    av_cash=sub_portfolio.cash
                ))

                # 检查买卖队列有没有等待买入的标的
                inner_callback_sell_dealed(symbol, context)
                inner_after_trading_settlement(position, sub_order, context)
            else:
                log.info("卖出部成, symbol={symbol}, name={stock_name}, 下单数={order_amount}, 成交数={business_amount}, 成交价={business_price}, 成交金额={business_balance}".format(
                    symbol=symbol,
                    stock_name=sub_get_stock_name(symbol),
                    order_amount=sub_order.order_amount,
                    business_amount=trade['business_amount'],
                    business_price=trade['business_price'],
                    business_balance=trade['business_balance'],
                ))
            pass
        else:
            # 佣金如何计算, 对于部成通知， 盘后统计计算佣金。
            #  卖出部成,  盘后结算
            inner_after_trading_settlement(position, sub_order, context)

        return
    #                                              订单状态: 废单                    状态：已撤,         5是部撤
    elif trade["entrust_bs"] == '2' and (trade["status"] == '9' or trade["status"] == '6' or trade["status"] == '5'):
# WARNING - 卖单已撤, order={'entrust_no': '38', 'business_time': '2026-03-19 10:27:52', 'stock_code': '518880.SS', 'entrust_bs': '2', 'business_amount': 900, 
# 'business_price': 10.9, 'business_balance': 9810.0, 'business_id': '0000000050004261', 'status': '6', 'cancel_info': ' ', 'withdraw_no': '38', 
# 'real_type': '2', 'real_status': '0', 'order_id': '36732f0c2aca44709025444100f7cb76', 'amount': 900.0}
        # 盘中通知： 卖出 成废单， 或者 卖单已撤 恢复可用数量
        if current_time < "15:10:00":
            position.enable_amount = position.enable_amount + abs(trade["business_amount"])

            used_money = abs(trade["business_balance"])
            log.warning("卖单{}, order={}".format(get_order_status_name(trade['status']), trade))
            position.order_id = None             
            # 数据保护
            if position.enable_amount > position.amount:
                position.enable_amount = position.amount

            # 卖单撤单成功, 重新下单。  如果是超时未成交的撤单，需要重新下单。
            # 实盘由于总仓的资金数据更新有延迟几秒， 撤单资金, 或股份还没有到账。 需要等待一会再下单。  实盘测试延迟： 5秒，4秒，6秒，5秒，
            if position.reorder_timeout is True and (trade["status"] == '6' or trade["status"] == '5'):  
                log.info("卖单超时未成交撤单，重新下单.  标的={}, {};  数量 = {}".format(symbol, sub_get_stock_name(symbol), position.enable_amount))
                time.sleep(10) 
                ##卖单撤单成功， 重新下单卖出。
                sub_order_target_value(symbol, 0, context)
                position.reorder_timeout = False
            else:
                log.info("错误委托, 标的={}, {};  金额 = {}".format(symbol, sub_get_stock_name(symbol), used_money))
                pass

            # 废单在盘中没见回调。
        else:
            # 废单在盘中没见回调。
            log.warning("卖单{},trade = {},  order={}".format(get_order_status_name(trade['status']), trade, sub_order))
            position.enable_amount = position.amount # 卖单已撤，恢复持仓。
            pass

    elif trade["entrust_bs"] == '2' and (trade["status"] == '2'):
        # 卖单收盘后仍为成交
        if current_time > "15:10:00":
            position.enable_amount = position.enable_amount + abs(trade["amount"])
            log.warning("卖单收盘仍未成交{}".format(trade))

            # 数据保护
            if position.enable_amount > position.amount:
                log.warning("持仓可用数量 大于持仓数. position = {}".format(position))
                position.enable_amount = position.amount

        return
    else:
# 2025-11-18 14:50:00 - INFO - 生成订单，订单号：5dbebfe6661d4b9e9866932da71b3548 股票代码：513520.XSHG 数量：卖出51200
# 2025-11-18 14:50:30 - WARNING - 异常下单响应 = {'entrust_no': '11556', 'business_time': '2025-11-18 14:50:30', 'stock_code': '513520.SS', 'entrust_bs': '2', 'business_amount': -31400, 
# 'business_price': 1.796, 'business_balance': -56394.4, 'business_id': '50026834', 'status': '7', 'cancel_info': ' ', 'withdraw_no': '0', 'real_type': '0', 'real_status': '0', 'order_id': '5dbebfe6661d4b9e9866932da71b3548', 'amount': 0}
# 2025-11-18 14:50:30 - WARNING - 异常下单响应 = {'entrust_no': '11556', 'business_time': '2025-11-18 14:50:30', 'stock_code': '513520.SS', 'entrust_bs': '2', 'business_amount': -19800, 
# 'business_price': 1.795, 'business_balance': -35541.0, 'business_id': '50026835', 'status': '8', 'cancel_info': ' ', 'withdraw_no': '0', 'real_type': '0', 'real_status': '0', 'order_id': '5dbebfe6661d4b9e9866932da71b3548', 'amount': 0}
# 2025-11-18 15:30:00 - INFO - 卖出已成, symbol=513520.SS, name=日经ETF , 下单数=-51200, 成交数=0, 成交价=0, 手续费=5.0
        log.warning("异常下单响应. Trade = {}, position={}, order={}".format(trade, position, sub_order))
            
    return 

def sub_use_orig_portfolio_data():
    """_summary_
    封装 交易， 回测检测函数。  用于 判断 交易， 回测使用是否使用原始仓位数据 ,     
    回测时使用分仓数据， 看不到回测曲线， 需要看每日收盘打印。
    Returns:
        _type_: _description_ True : 使用原始仓位数据， False:  使用自定义的分仓数据
    """
    use_orig_portfolio_data = True
    use_orig_portfolio_data = g.use_orig_portfolio_data
    
    if use_orig_portfolio_data is True:
        return True

    return False



def on_trade_response (context, trade_list):
    """_summary_
    1. 该函数会在成交主推回调时响应，比引擎和get_trades()函数更新Order状态的速度更快，适合对速度要求比较高的策略。
    2. 撤单成功也在这个函数中回调。
    
    这个函数好像在order 函数返回前进行回调的。
    Args:
        context (_type_): _description_
        trade_list：一个列表，当前成交单发生变化时，发生变化的成交单列表。成交单以字典形式展现，内容包括：'entrust_no'(委托编号), 'business_time'(成交时间), 
        'stock_code'(股票代码), 'entrust_bs'(成交方向), 'business_amount'(成交数量), 'business_price'(成交价格), 'business_balance'(成交额), 
        'business_id'(成交编号), 'status'(委托状态), 'order_id'(Order订单编号)；
    """

    # 回测场景
    if sub_use_orig_portfolio_data():
        return
   
    # print("TTTTTTTTTTTT", trade_list)
    # trade_list =  [{'entrust_no': '9538', 'business_time': '2025-10-28 10:31:01', 'stock_code': '002193.SZ', 'entrust_bs': '1', 'business_amount': 3000, 'business_price': 5.49, 
    # 'business_balance': 16470.0, 'business_id': '1010000432942590', 'status': '8', 'cancel_info': ' ', 'withdraw_no': '0', 'real_type': '0', 'real_status': '0', 
    # 'order_id': 'c78bcb3375c344c3937df76358b6892d'}]

    ## 回测时的 回调数据
    # 2025-09-02 10:30:00 - INFO - TTTTTTTTTTTT <Trade {'datetime': datetime.datetime(2025, 9, 2, 10, 30), 'trading_datetime': datetime.datetime(2025, 9, 2, 10, 30), 
    # 'order_id': '5feb864f053f458a99176292b4d33fae', 'price': 10.361554, 'amount': 1500, 'commission': 5.7569115197, 'tax': 0, 'transaction_cost': 5.7569115197, 'entrust_direction': 'BUY', 
    # 'asset': <StockAsset {'symbol': '002856.XSHE', 'name': '美芝股份', 'exchange': 'XSHE', 'type': 'STOCK', 'listed_date': datetime.datetime(2017, 3, 20, 0, 0), 'trade_unit': 100, 
    # 'trading_time': '09:30-11:30, 13:00-15:00', 'delisted_date': datetime.datetime(2900, 1, 1, 0, 0), 'precision': 2}>, 'futures_direction': 'OPEN', 'id': '7ac253ac1d5c45a88330cea55adbc3ac', 
    # 'symbol': '002856.XSHE', 'entrust_no': None, 'hedge_type': 'SPECULATION', 'status': None}>
    
    
    if not is_trade():
        # 回测场景 的参数格式是Class,  实盘场景的参数格式是Dict,  需要进行格式转换。
        trade_obj = trade_list
        business_time = trade_obj.trading_datetime.strftime("%Y-%m-%d %H:%M")
        symbol = trade_obj.symbol
        if symbol.endswith('.XSHE') or symbol.endswith('.SZ'):
            symbol = symbol.split(".")[0] + ".SZ"
        elif symbol.endswith('.XSHG') or symbol.endswith('.SS'):
            symbol = symbol.split(".")[0] + ".SS"
        else:
            log.error("Error code = {}, trade = {}".format(symbol, trade_obj))
            return
        
        entrust_bs = '1'
        # log.info("DDDDDDDDDDdirection={}".format(trade_obj.entrust_direction))
        if trade_obj.entrust_direction == EntrustDirection.BUY:
            entrust_bs = '1'
        elif trade_obj.entrust_direction == EntrustDirection.SELL:
            entrust_bs = '2'
        else:
            #2025-09-02 10:30:00 - ERROR - Error direction=EntrustDirection.BUY
            log.error("Error direction={}".format(trade_obj.entrust_direction))
            return

# 2025-09-02 10:30:00 - INFO - DDDDDDDDDDDD {'_trade_id': 'b165a4a79e46439abf161615fa520e78', '_order_id': 'f9efb19379a044bfbe772c75e80beb25', '_calendar_dt': datetime.datetime(2025, 9, 2, 10, 30), 
# '_trading_dt': datetime.datetime(2025, 9, 2, 10, 30), '_price': 10.361554, '_amount': 1500, '_commission': 5.7569115197, '_tax': 0, '_close_today_amount': 0, '_entrust_direction': 'BUY', 
# '_futures_direction': 'OPEN', '_asset': <StockAsset {'symbol': '002856.XSHE', 'name': '美芝股份', 'exchange': 'XSHE', 'type': 'STOCK', 'listed_date': datetime.datetime(2017, 3, 20, 0, 0), 
# 'trade_unit': 100, 'trading_time': '09:30-11:30, 13:00-15:00', 'delisted_date': datetime.datetime(2900, 1, 1, 0, 0), 'precision': 2}>, '_frozen_price': 10.36, '_hedge_type': 'SPECULATION', 
# '_status': None}
# 2025-09-02 10:30:00 - INFO - 222222222222 ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__getstate__', 
# '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', 
# '__str__', '__subclasshook__', '__weakref__', '_amount', '_asset', '_calendar_dt', '_close_today_amount', '_commission', '_entrust_direction', '_frozen_price', '_futures_direction', 
# '_hedge_type', '_make_id', '_order_id', '_price', '_repr_attr_list', '_status', '_tax', '_trade_id', '_trading_dt', 'amount', 'asset', 'close_today_amount', 'commission', 'create_trade', 
# 'datetime', 'entrust_direction', 'frozen_price', 'futures_direction', 'hedge_type', 'id', 'order_id', 'price', 'status', 'symbol', 'tax', 'trading_datetime', 'transaction_cost']
# 2025-09-02 10:30:00 - INFO - TTTTTTTTTTTT <Trade {'datetime': datetime.datetime(2025, 9, 2, 10, 30), 'trading_datetime': datetime.datetime(2025, 9, 2, 10, 30), 
# 'order_id': 'f9efb19379a044bfbe772c75e80beb25', 'price': 10.361554, 'amount': 1500, 'commission': 5.7569115197, 'tax': 0, 'transaction_cost': 5.7569115197, 
# 'entrust_direction': 'BUY', 'asset': <StockAsset {'symbol': '002856.XSHE', 'name': '美芝股份', 'exchange': 'XSHE', 'type': 'STOCK', 'listed_date': datetime.datetime(2017, 3, 20, 0, 0), 
# 'trade_unit': 100, 'trading_time': '09:30-11:30, 13:00-15:00', 'delisted_date': datetime.datetime(2900, 1, 1, 0, 0), 'precision': 2}>, 'futures_direction': 'OPEN', 
# 'id': 'b165a4a79e46439abf161615fa520e78', 'symbol': '002856.XSHE', 'entrust_no': None, 'hedge_type': 'SPECULATION', 'status': None}>
# 2025-09-02 10:30:00 - INFO - DDDDDDDDDDdirection=EntrustDirection.BUY
        #trade_obj.entrust_no
        business_balance = trade_obj.amount * trade_obj.price
        new_trade_list = [{'entrust_no': None, 'business_time': business_time, 'stock_code': symbol, 'entrust_bs': entrust_bs, 'business_amount': trade_obj.amount, 
                        'business_price': trade_obj.price, 'business_balance': business_balance, 'business_id': '1010000432942590', 'status': '8', 'cancel_info': ' ', 'withdraw_no': '0',  'real_type': '0', 
                        'real_status': '0',  'order_id': "bt_order_id", 'bt_real_order_id': trade_obj.order_id}] # trade_obj.order_id,  trade_obj.order_id , 
    else:
        new_trade_list = trade_list
        
    sub_positions = sub_get_strategy_positions(context)

    for trade in new_trade_list:
        # print("BBBBBBBBBBBBBB", trade)
        symbol = trade["stock_code"]
        
        # 股票不在本策略持仓
        if symbol not in sub_positions:
            log.warning("股票不在本策略持仓,  symbol = {}, position={}".format(symbol, sub_positions))
            continue
        
        position = sub_positions[symbol]

        # 在Order函数返回前进行回调的。 此时还没有取得order_id
        order_id = None  
        bt_real_order_id = None  # 回测模式的order 返回的真实id
        #实盘模式
        if is_trade():
            order_id = trade["order_id"]
        # 回测模式， 有时候on_trade_response 在order前回调， 有时候又在order后回调。
        else:
            bt_real_order_id = trade["bt_real_order_id"]
            
        sub_order = None
        # 实盘模式
        if is_trade() and order_id in position.order_dict:
           sub_order = position.order_dict[order_id]
        # 回测模式
        elif (not is_trade()) and "bt_order_id" in position.order_dict:
           sub_order = position.order_dict["bt_order_id"]
        elif (not is_trade()) and bt_real_order_id in position.order_dict:
           sub_order = position.order_dict[bt_real_order_id]
        else:
            log.error("错误消息: symbol = {}, position={}, trade={}, 原始Trade={}".format(symbol, position, trade, trade_list))
            return                     
                     
        #entrust_bs -- 成交方向(注意：str类型)，'1'-买，'2'-卖；
        if trade['entrust_bs'] == '1':
            trade['amount'] = sub_order.order_amount # 买入数量
        elif trade['entrust_bs'] == '2':
            trade['amount'] = 0 - sub_order.order_amount   # 卖出数量
        else:
            log.error("不匹配的消息类型, trade = {}".format(trade))
            return
        #  根据订单的成交情况， 更新策略的仓位数据。
        # print("AAAAAAAAAAAAAA", trade)
        inner_update_sub_position(trade, position, sub_order, context)

        # 订单响应先保存， 盘后结算还需要使用。
        sub_order.trade_response.append(trade)
   
    return

def sub_refresh_position_data(context):
    """_summary_
    ###### 刷新持仓收益，  市值等数据 
    # #校验分仓库资金 与 股票 与总仓的 资金 ， 持仓是否一致，  本策略可用资金必须小于总仓位资金， 
    # 本策略持仓股票数必须在总仓也存在， 股数必须小于总仓持股数

    Args:
        context (_type_): _description_
    """
    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')
    current_time = context.blotter.current_dt.strftime("%H:%M:%S")
    
    sub_positions = sub_get_strategy_positions(context)
    sub_holding_list = list(sub_positions.keys())

    # 总仓的实际持股
    main_positions = context.portfolio.positions
    main_holding_list = list(main_positions.keys())
    
    # 这里刷新分仓数据，  直接用全局变量， 否则死循环。
    sub_portfolio = g.__sub_portfolio 

    total_market_value = 0
    for symbol in sub_holding_list:
        
        position = sub_positions[symbol]
        ####校验持仓
        #  当天收盘后持股数为0
        # Fix BUG: 回测场景：当天Bar交易量不足， 订单撤消却没有回调通知。
        # if position.amount == 0 and current_date > position.buy_date and current_time > "15:00:00": 
        #     # 2024-02-06 10:30:00 - WARNING - 订单撤销:  当前bar交易量不足  003033.XSHE  bar.volume 0.0
        #     # 2024-02-06 10:30:00 - INFO - 生成订单，订单号:c0dc52f6f1af4518b1cad6e3522cb851，股票代码：003033.XSHE，数量：买入700股
        #     log.error("数据错误: {}, {}持股数量为0".format(symbol, sub_get_stock_name(symbol)))
        #     continue                
        
        market_value = position.last_sale_price * position.amount 

        # 2、 分仓持股在总仓数据存在。 
        if symbol not in main_holding_list:
            log.error("分仓策略持股在总仓不存在，请检查计算分仓可用金额。 ={}: {}, 在总仓不存在={}, 分仓数据= {}".format(symbol, sub_get_stock_name(symbol), main_holding_list, sub_positions[symbol]))
            # 2025-02-20 15:30:00 - ERROR - 分仓持股=003011.SZ, 在总仓不存在=['002058.SZ', '002188.SZ', '002207.SZ', '002719.SZ', '002789.SZ', '002910.SZ']
            # 2025-02-20 15:30:00 - WARNING - Order Rejected: 003011.XSHE can not match. Market close.
            # FIX BUG: TO DO: 订单买单没有成交， 或者是废单， 总仓就会没有数据， 这时需要, 删除分仓数据, 恢复分仓可用资金
            # 计算这支票的占用资金
            log.error("分仓策略持股 {}: {}, 恢复占用资金 = {}, 持仓={}".format(symbol, sub_get_stock_name(symbol), market_value, position.amount))
            sub_portfolio.cash = sub_portfolio.cash  + market_value
            inner_del_strategy_positions(symbol)
            continue
        
        if position.amount > 0 and main_positions[symbol].amount == 0:
            log.error("分仓策略持股与总仓不一致, 请检查计算分仓可用金额。 分仓标的={}:{}, 总仓已卖出={}, 分仓数据= {}".format(symbol, sub_get_stock_name(symbol), main_holding_list, sub_positions[symbol]))
            # 2025-02-20 15:30:00 - ERROR - 分仓持股=003011.SZ, 在总仓不存在=['002058.SZ', '002188.SZ', '002207.SZ', '002719.SZ', '002789.SZ', '002910.SZ']
            # 2025-02-20 15:30:00 - WARNING - Order Rejected: 003011.XSHE can not match. Market close.
            # FIX BUG: TO DO: 订单买单没有成交， 或者是废单， 总仓就会没有数据， 这时需要, 删除分仓数据, 恢复分仓可用资金
            # current_order = get_order(sub_positions[symbol].order_id)
            # print("current_order", current_order)
            # 计算这支票的占用资金
            log.error("分仓策略持股 {}: {}, 恢复占用资金 =  {}, 持仓={}".format(symbol, sub_get_stock_name(symbol), market_value, position.amount))
            sub_portfolio.cash = sub_portfolio.cash  + market_value
            inner_del_strategy_positions(symbol)
            continue

        #3、 分仓 持股数必须小于等于 总仓 持仓数 . 如何不同策略买入的票怎么算？
        if position.amount != main_positions[symbol].amount:
            log.warning("{symbol}, {name}分仓持股数量不等总仓持股数量不一致,  请检查多策略是否购买同一股票。 分仓持股数{sub_amount}, 总仓持股数{main_amount}".format(
                symbol=symbol,
                name=sub_get_stock_name(symbol),
                sub_amount=position.amount,
                main_amount=main_positions[symbol].amount
            ))

        market_value = position.last_sale_price * position.amount 
        total_market_value = total_market_value + market_value
            
            
    # 这里刷新分仓数据，  直接用全局变量， 否则死循环。
    sub_portfolio = g.__sub_portfolio 
    
    # 策略可用资金必须小于  总仓可用资金
    if custom_round(sub_portfolio.cash, 2)  > custom_round(context.portfolio.cash, 2) :
        log.warning("分仓可用资金: {}元 > 总仓资金: {}".format(sub_portfolio.cash, context.portfolio.cash))
        sub_portfolio.cash = context.portfolio.cash

    sub_portfolio.positions_value = total_market_value       #   持仓价值
    sub_portfolio.portfolio_value = total_market_value  + sub_portfolio.cash     #   当前持有的标的和现金的总价值
    #当前的收益比例, 相对于初始资金
    sub_portfolio.returns = round((sub_portfolio.portfolio_value - sub_portfolio.init_cash)*100/sub_portfolio.init_cash, 2)

    return

def after_trading_end(context, data):
    """_summary_
    该函数会在每天交易结束之后调用， 扣除税费， 校验并同步订单与资金状态。
    收益率统一采用 %格式， 打印出来%省略了， 并保留2位小数。 

    Args:
        context (_type_): _description_
        strategy_name (_type_): _description_
        g (_type_): _description_
    """
    # 使用原始仓位数据， 直接返回。
    if sub_use_orig_portfolio_data():
        return

    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')

    # 结算要用原始数据。
    sub_portfolio = inner_sub_get_strategy_portfolio(context) 
    sub_positions = sub_portfolio.positions

    holding_list = list(sub_positions.keys())

    # 将每日交易操作 转换成DF保存到本地
    sub_order_columns = list(subOrder().__dict__.keys())
    today_order_df = pd.DataFrame(columns=sub_order_columns)

    for symbol in holding_list:
        
        position = sub_positions[symbol]
        order_id_list = list(position.order_dict.keys()) 
        
        if len(order_id_list) == 0:
            continue
        
        # 遍历每个订单， 完成盘后结算。
        for order_id in order_id_list:
            
            sub_order = position.order_dict[order_id]

            #回测场景
            if order_id == "bt_order_id":
                continue
            else:
                #实盘场景
                order_list = get_order(order_id)
    # 买入订单号=59629bf875f240b6b2fa5d3963eb7d72, result=[<Order {'id': '59629bf875f240b6b2fa5d3963eb7d72', 'dt': datetime.datetime(2025, 2, 6, 10, 30), 'priceGear': 0, 'limit': None, 
    # 'symbol': '002848.XSHE', 'amount': 2700, 'created': datetime.datetime(2025, 2, 6, 10, 30), 'filled': 2700, 'status': '8', 'entrust_no': None, 'cancel_entrust_no': None}>],  2700, None
    # 卖出订单号=8315600670cf4517a319a3440f599a9b, result=[<Order {'id': '8315600670cf4517a319a3440f599a9b', 'dt': datetime.datetime(2025, 2, 18, 14, 20), 'priceGear': 0, 'limit': None, 
    # 'symbol': '002848.XSHE', 'amount': -2700.0, 'created': datetime.datetime(2025, 2, 18, 14, 20), 'filled': -2700.0, 'status': '8', 'entrust_no': None, 'cancel_entrust_no': None}>],  -2700.0, None

                if order_list is None or len(order_list) == 0:
                    log.error("获取订单错误{},  订单号={}, order_list={}, position={}".format(symbol, order_id, order_list, position))
                    if position.amount == 0:
                        inner_del_strategy_positions(symbol)
                    continue

                var_order = order_list[0]

            # '6' -- "已撤", 已经撤消，没有成交的订单不处理。
            if var_order.status == '6':
                log.warning("订单已撤={}, 订单号={}, sub_order = {}".format(symbol, order_id, sub_order))
                continue
            
            entrust_bs = "1"  #entrust_bs -- 成交方向(str)，1-买，2-卖；
            entrust_bs_text = "买入"
            if var_order.amount > 0:
                entrust_bs = "1"
            else: 
                entrust_bs = "2"
                entrust_bs_text = "卖出"
                sub_order.order_price = var_order.limit
            # log.error("获取订单{},  订单号={}, result={},  {}, {}".format(symbol, order_id, order_list, var_order.amount, var_order.limit))
            # 统一处理： 构建盘后成交消息。
            trade_dict = {'entrust_bs': entrust_bs, 'business_amount': sub_order.business_amount, 'business_balance': sub_order.business_balance, 'business_price': var_order.limit, 'order_id': order_id, 
                        'order_time': var_order.dt, 'entrust_prop': '0', 'status': var_order.status, 'price': var_order.limit, 'entrust_no': var_order.entrust_no, 
                        'error_info': None, 'amount': var_order.amount, 'stock_code': symbol, 'entrust_type': '0'}
            # 每天收盘后， 根据订单的成交情况， 更新策略的仓位数据。
            inner_update_sub_position(trade_dict, position, sub_order, context)

            # 可能出现BUG, 校验一下。  
            if position.enable_amount == 0 and position.amount > 0:
                log.warning("XXX订单处理出错 pt_order={}, sub_order={}, trade={}".format(var_order, sub_order, trade_dict))  #涨停卖出没成交时有BUG？
        
            # 计算卖出的利润率 与 利润总钱数
            profit_rate = None
            profit_money = None
            if entrust_bs == "2" and sub_order.business_price > 0:
                profit_rate = custom_round((sub_order.business_price - position.cost_basis)*100/position.cost_basis, 2)  
                profit_money = custom_round((sub_order.business_price - position.cost_basis)*abs(sub_order.business_amount), 2)  

            # 盘后结算， 记录今日操作到excel表格
            sub_order_dict = {
                "订单号": order_id,
                "时间": sub_order.dt,
                "方向": entrust_bs_text,
                '代码': sub_order.symbol, 
                '名称': sub_get_stock_name(sub_order.symbol),  
                '下单数量': sub_order.order_amount,
                '下单价格': sub_order.order_price,
                '买入锁定金额': sub_order.order_cash,
                '成本价': custom_round(position.cost_basis, 3),
                '成交均价': custom_round(sub_order.business_price, 2),
                '成交总数': sub_order.business_amount,
                '成交金额': sub_order.business_balance,
                '卖出利润': profit_money,
                '利润率': profit_rate,
                '是否结算': sub_order.settlemented,
                '手续费': sub_order.tax_commission,
                '委托编号': sub_order.entrust_no                
            }
            
            if len(today_order_df) > 0:
                new_row = pd.DataFrame([sub_order_dict])  # 转成DataFrame
                today_order_df = pd.concat([today_order_df, new_row], ignore_index=True)
            else:
                today_order_df = pd.DataFrame([sub_order_dict])  # 转成DataFrame
            
        # 清除 订单 信息
        position.order_dict = {}
        position.reorder_timeout = False

        # 持仓数量为0, 标的可能已卖出，或者买入失败,  则删除持仓对象。
        if position.amount == 0:
            inner_del_strategy_positions(symbol)
            continue

    # 增加分红除权的收益
    inner_calculate_exrights(context)

    # 刷新与校验分仓持股数据
    sub_refresh_position_data(context)


    # 实盘打印 持仓 数据， 并对交易记录持久化
    if is_trade():
        sub_portfolio = inner_sub_get_strategy_portfolio(context)
        sub_positions = sub_get_strategy_positions(context)

        # 方法1：先创建空DataFrame，然后使用append()
        # 创建空DataFrame并指定列名
        today_stock_df = pd.DataFrame(columns=['日期', '代码', '名称', '可用数', '总数', '最新价', '成本价', '市值', '利润', '利润率%', '买入日期', '持仓天'])

        holding_list = list(sub_positions.keys())

        for symbol in holding_list:
            position = sub_positions[symbol]
            
            # 持仓数量为0, 标的可能已卖出，或者买入失败,  则删除持仓对象。
            if position.amount == 0 :
                inner_del_strategy_positions(symbol)
                continue
            
            rate = custom_round((position.last_sale_price - position.cost_basis)/position.cost_basis, 4)
            # 逐条追加数据
            stock_dict = {
                    '日期': current_date,
                    '代码': symbol, 
                    '名称': sub_get_stock_name(symbol),  
                    '可用数': position.enable_amount, 
                    '总数': position.amount, 
                    '最新价': custom_round(position.last_sale_price, 3), 
                    '成本价': custom_round(position.cost_basis, 3), 
                    '市值':  custom_round(position.last_sale_price * position.amount, 2),
                    '利润': custom_round(position.cost_basis*position.amount*rate, 2),
                    '利润率%': rate*100,
                    '买入日期': position.buy_date,
                    '持仓天': len(get_trade_days(start_date=position.buy_date, end_date=current_date)),
                    }
            if len(today_stock_df) > 0:
                new_row = pd.DataFrame([stock_dict])  # 转成DataFrame
                today_stock_df = pd.concat([today_stock_df, new_row], ignore_index=True)
            else:
                today_stock_df = pd.DataFrame([stock_dict])  # 转成DataFrame

        # 计算当天本策略的收益
        today_benefit = sub_portfolio.portfolio_value - sub_portfolio.pre_portfolio_value
        today_rate = custom_round(today_benefit*100/sub_portfolio.pre_portfolio_value, 2) 
        sub_portfolio.pre_portfolio_value = sub_portfolio.portfolio_value

        # 记录最近最高市值，便于计算最近的最大回撤。
        # 1、 收益创新高， 或者第一次记录 最近最高市值。
        if sub_portfolio.pre_max_value is None or sub_portfolio.pre_max_value <= sub_portfolio.portfolio_value:
            sub_portfolio.pre_max_value = sub_portfolio.portfolio_value
            sub_portfolio.pre_max_value_date = current_date
            sub_portfolio.drawdown_rate = 0
        
        # 当天发生回撤， 记算回撤百分比。
        elif sub_portfolio.pre_max_value > sub_portfolio.portfolio_value:
            sub_portfolio.drawdown_rate = (sub_portfolio.portfolio_value - sub_portfolio.pre_max_value)/sub_portfolio.pre_max_value*100
            sub_portfolio.drawdown_rate = custom_round(sub_portfolio.drawdown_rate, 2)
            
        # 2. 配置显示参数（关键）
        # 解决中文 打印对齐问题
        pd.set_option('display.unicode.ambiguous_as_wide', True)
        pd.set_option('display.unicode.east_asian_width', True)
        # # 防止列名折叠
        pd.set_option('display.expand_frame_repr', False)
        # 显示所有列
        pd.set_option('display.width', None)                      # 自动适配终端宽度
        pd.set_option('display.max_columns', None)                # 显示所有列
        pd.set_option('display.max_colwidth', None)               # 显示列内容完整宽度

        if len(today_order_df) > 0:
            inner_append_portfolio_to_excel(today_order_df, sheet_name = '每日操作')
            log.info("每日操作：\n {}".format(today_order_df))

        if len(today_stock_df) > 0:
            inner_append_portfolio_to_excel(today_stock_df, sheet_name = '每日持仓')
        log.info("每日持股：\n {}".format(today_stock_df))

        # 逐条追加数据
        daily_portfolio = {
                '日期': current_date, 
                '日收益': today_benefit,  
                '日收益率': today_rate,  
                '可用资金': sub_portfolio.cash, 
                '持仓市值': sub_portfolio.positions_value, 
                '总资金': sub_portfolio.portfolio_value, 
                '初始资金': sub_portfolio.init_cash, 
                '总收益率': sub_portfolio.returns, 
                '最高市值': sub_portfolio.pre_max_value, 
                '最高日期': sub_portfolio.pre_max_value_date, 
                '回撤比率': sub_portfolio.drawdown_rate, 
                }        
        # log.info("本策略收盘：日收益={today_benefit}元, 日收益率={today_rate:.2%}, 可用资金={available_cash}, 持仓市值={position_value}元, 总资金={total_value}元, 初始资金={init_cash}元, 总收益率={total_rate:.2%}".format(
        #     today_benefit=today_benefit,
        #     today_rate=today_rate,
        #     available_cash=sub_portfolio.cash,
        #     position_value=sub_portfolio.positions_value,
        #     total_value=sub_portfolio.portfolio_value,
        #     init_cash=sub_portfolio.init_cash, 
        #     total_rate=sub_portfolio.returns
        # ))

        daily_portfolio_df = pd.DataFrame([daily_portfolio])
        log.info("本策略每日收益:\n {}".format(daily_portfolio_df))

        # 策略资产追加到本地Excel， 便于复盘。     sheet_name = '策略资产'
        inner_append_portfolio_to_excel(daily_portfolio_df, sheet_name = '策略资产')
        # log.info("总仓数据, 总资金={}, 持仓市值={}, 可用资金={}, 收益率={}", context.portfolio.portfolio_value, context.portfolio.positions_value, context.portfolio.cash,  context.portfolio.returns)


        ########## 每天收盘后， 需要保存策略仓位数据。
        # 实盘场景， 为了保持数据一致性， 每天收盘后都对数据持久化
        save_strategy_persistent_data(context)
            
    # 清空买卖队列,  卖方队列
    sub_clear_buy_sell_queue(context)
        
    return
def inner_calculate_exrights(context):
    """_summary_
    计算除权， 分红,  配送股等数据。 如： 长江电力在 20250124 日： 每10股派现金2.100元。
2025-01-23 15:30:00 - INFO - 每日收盘资金：日收益=38.0元, 日收益率=0.04%, 可用资金=73054.69, 持仓市值=31668.0元, 总资金=104722.69元, 初始资金=100000元, 总收益率=4.72%
2025-01-23 15:30:00 - INFO - 总仓数据, 总资金=106086.69206878523, 持仓市值=33032.0, 可用资金=73054.69206878523, 收益率=0.060866920687852266
2025-01-24 15:30:00 - INFO - XFFFFFFfff 600900.SS           
date       allotted_ps  bonus_ps  exer_backward_a  exer_backward_b   exer_forward_a  exer_forward_b  rationed_ps  rationed_px                                                           
20250124          0.0      0.21           1.7508           16.325         1.0          -0.943          0.0          0.0  
2025-01-24 15:30:00 - INFO - XXXX 44
2025-01-24 15:30:00 - INFO - 账户现金分红（税前）：126.00 元,  税后：113.40 元  ,  PT 在回测时都按20%交税。
2025-01-24 15:30:00 - INFO - 每日收盘持股：
            代码         名称         可用数        总数          最新价        成本价        市值         利润         利润率%      买入日期        持仓天       
1           600900.SS  长江电力       600        600        27.47      27.25      16482.0    132.44     0.81       2024-12-11  32       
2025-01-24 15:30:00 - INFO - 每日收盘资金：日收益=118.0元, 日收益率=0.11%, 可用资金=73168.09, 持仓市值=31786.0元, 总资金=104840.69元, 初始资金=100000元, 总收益率=4.84%
2025-01-24 15:30:00 - INFO - 总仓数据, 总资金=106179.49206878523, 持仓市值=33024.0, 可用资金=73155.49206878523, 收益率=0.061794920687852306    

stock_exrights = get_stock_exrights('515980.SS', date='20250930'): 1拆2股。 
date        allotted_ps  rationed_ps  rationed_px  bonus_ps  exer_forward_a  exer_forward_b  exer_backward_a  exer_backward_b   
20250930          1.0          0.0          0.0       0.0             0.5    0.0              2.0              0.0  
    Args:
        context (_type_): _description_
    """

    #get_stock_exrights(stock_code, date=None)
    current_date = context.blotter.current_dt.strftime('%Y%m%d')
    current_date_line = context.blotter.current_dt.strftime('%Y-%m-%d')

    sub_portfolio = inner_sub_get_strategy_portfolio(context)
    sub_positions = sub_get_strategy_positions(context)

    holding_list = list(sub_positions.keys())

    for symbol in holding_list:
        position = sub_positions[symbol]
        
        # 持仓数量为0, 标的可能已卖出，或者买入失败,  则删除持仓对象。
        if position.amount == 0 :
            continue    

        # 当天刚买入的票不进行 除权除息操作。
        if position.buy_date == current_date_line:
            continue

        fq_data = get_stock_exrights(symbol, date=current_date)

        # 当天没有分红，除权等数据。
        if fq_data is None:
            continue

        # 返回结果字段介绍：
        # date -- 日期(索引列，类型为int64)；
        # allotted_ps -- 每股送股(str:numpy.float64)；
        # rationed_ps -- 每股配股(str:numpy.float64)；
        # rationed_px -- 配股价(str:numpy.float64)；
        # bonus_ps -- 每股分红(str:numpy.float64)；
        # exer_forward_a -- 前复权除权因子A；用于计算前复权价格(前复权价格=A*价格+B)(str:numpy.float64)
        # exer_forward_b -- 前复权除权因子B；用于计算前复权价格(前复权价格=A*价格+B)(str:numpy.float64)
        # exer_backward_a -- 后复权除权因子A；用于计算后复权价格(后复权价格=A*价格+B)(str:numpy.float64)
        # exer_backward_b -- 后复权���权因子B；用于计算后复权价格(后复权价格=A*价格+B)(str:numpy.float64)
        
        # ===================== 2. 计算账户维度数据 =====================
        # 除权数据（转为浮点数，模拟实际值）
        fq_data_columns = fq_data.columns.tolist()
        allotted_ps = 0
        if 'allotted_ps' in fq_data_columns:
            allotted_ps = np.float64(fq_data['allotted_ps'].iloc[-1])    # 每股送0.1股（10送1）

        rationed_ps = 0
        if 'rationed_ps' in fq_data_columns:
            rationed_ps = np.float64(fq_data['rationed_ps'].iloc[-1])    # 每股配0.2股（10配2）

        rationed_px = 0
        if 'rationed_px' in fq_data_columns:
            rationed_px = np.float64(fq_data['rationed_px'].iloc[-1])    # 配股价5元/股

        bonus_ps = 0
        if 'bonus_ps' in fq_data_columns:
            bonus_ps = np.float64(fq_data['bonus_ps'].iloc[-1])      # 每股分红0.05元        

        # （1）送股。 由于总额不能变，  送股后股票价格要降权 变低。 如果是送股， allotted_ps 是大于0， 如果是 缩股： allotted_ps 是小于0
        if allotted_ps > 0 or allotted_ps < 0:
            total_allotted = int(position.amount * allotted_ps)
            log.info("{symbol}-{name}, 送股数：{total_allotted:.0f} 股".format(symbol=symbol, name=sub_get_stock_name(symbol), total_allotted=total_allotted))
            position.amount = position.amount + total_allotted
            position.enable_amount = position.enable_amount + total_allotted
            
        # （2）配股（全额参与）
        if rationed_ps > 0 and rationed_px > 0:
            total_rationed = int(position.amount * rationed_ps)
            rationed_amount = custom_round(total_rationed * rationed_px) 
            log.info("{symbol}-{name}, 配股数：{total_rationed:.0f} 股，需缴款：{rationed_amount:.2f} 元".format(symbol=symbol, name=sub_get_stock_name(symbol), total_rationed=total_rationed, rationed_amount=rationed_amount))
            position.amount = position.amount + total_allotted
            position.enable_amount = position.enable_amount + total_allotted
            sub_portfolio.cash = sub_portfolio.cash - rationed_amount

        # （3）现金分红（税前）
        if bonus_ps > 0:
            total_bonus = position.amount * bonus_ps
            #分红扣税：≤30 天 20%、31 天～1 年 10%、>1 年 0%；
            # 3. 计算天数差（取绝对值，避免顺序影响）
            days_diff = abs((datetime.strptime(current_date_line, "%Y-%m-%d") - datetime.strptime(position.buy_date, "%Y-%m-%d")).days) - 1
            tax = 0
            if days_diff > 0:   # PT好像都按20%缴税
                tax = total_bonus * 0.2                
            # if days_diff <= 30:
            #     tax = total_bonus * 0.2
            # elif days_diff > 30 and days_diff <= 365:
            #     tax = total_bonus * 0.1
            # else:
            #     tax = 0                
            total_bonus_taxed =  total_bonus - tax
            sub_portfolio.cash = sub_portfolio.cash + total_bonus_taxed
            log.info("{symbol}-{name}, 现金分红, {bonus_ps:.4f}/股 （税前）：{total_bonus:.2f} 元,  税后：{total_bonus_taxed:.2f} 元".format(symbol=symbol, name=sub_get_stock_name(symbol), bonus_ps=bonus_ps,total_bonus=total_bonus, total_bonus_taxed=total_bonus_taxed))   

            
        # 计算定点除权价,   除权价直接取数股票最新价即可， 不用计算。
        # pre_close = (pre_close - fq_data['bonus_ps'].iloc[0] + fq_data['rationed_ps'].iloc[0]*fq_data['rationed_px'].iloc[0])/(1+fq_data['allotted_ps'].iloc[0]+fq_data['rationed_ps'].iloc[0])
        # pre_close = custom_round(pre_close, 2)
   
    return 

def sub_calculate_commission_and_tax(symbol, sub_order, total_money, context):
    """_summary_
    计算买卖所需的费用， 含 印花税， 佣金， 经手费
    Args:
        symbol (_type_): _description_
        trade (_type_): _description_
        total_money (_type_): _description_ 买入， 卖出总金额
        context (_type_): _description_

    Returns:
        _type_: _description_
    """
    tax = context.commission.tax
    
    # ETF 不收印花税
    if symbol.startswith('1') or symbol.startswith('5'):
        tax = 0
    
    # 买入不收印花税 trade["entrust_bs"] == '1'
    if sub_order.order_amount > 0: 
        tax = 0
    else:
        # 回测时 印花税固定为0.001,
        # log.info("XXXXX 印花税= {}, {}, {}, {}".format(tax, context.commission.tax, total_money, sub_order))
        pass

    # 关于回测手续费计算：手续费=佣金费+经手费

    # 佣金费=佣金费率*交易总金额(若佣金费计算后小于设置的最低佣金，则佣金费取最小佣金)
    # 经手费=经手费率(万分之0.487)*交易总金额
    # 卖出再加上印花税
    # 总费用 = 印花税 + 经手费 + MAX(佣金费, 最小佣金)
    total_money = abs(total_money)
    commission_and_tax = total_money * (tax + 0.0000487) + max(total_money*context.commission.cost, context.commission.min_trade_cost)

    return custom_round(commission_and_tax, 3)

def sub_get_stock_name(symbol):
    """_summary_

    Args:
        stocks (_type_): _description_  {'600570.SS': '恒生电子'}

    """

    name_dict = get_stock_name(symbol)
        
    return name_dict[symbol]

def get_order_direction_name(entrust_bs):
    
    direction = ""
    if entrust_bs  == "1":
        direction = "买入"
    else:
        direction = "卖出"
        
    return direction


def get_order_status_name(status):
    """_summary_
    获取订单状态的中文解释
    Args:
        status (_type_): _description_

    Returns:
        _type_: _description_
    """
    name = ""
    # status -- 订单状态(str)，该字段取值范围：
    if status == '0': #    '0' -- "未报"
        name = "未报"
    elif status == '1':     #    '1' -- "待报"
        name = "待报"
    elif status == '2': # # '2' -- "已报"
        name = "已报"
    elif status == '3': #     # '3' -- "已报待撤"
        name = "已报待撤"
    elif status == '4':     #    # '4' -- "部成待撤"
        name = "部成待撤"
    elif status == '5': #    # '5' -- "部撤"
        name = "部撤"
    elif status == '6':     # '6' -- "已撤"
        name = "已撤"
    elif status == '7':     # '7' -- "部成"
        name = "部成"
    elif status == '8':     # '8' -- "已成"
        name = "已成"       
    elif status == '9': #    # '9' -- "废单"
        name = "废单"
    elif status == '+':     # '+' -- "已受理"
        name = "已受理"
    elif status == '-':         # '-' -- "已确认"
        name = "已确认"
    elif status == 'V':         # 'V' -- "已确认"
        name = "已确认"
        
    return name
def is_etf_lof_fund(symbol):
    """_summary_
    检查标的是否是ETF,  或LOF基金
    
    Args:
        symbol (_type_): _description_

    Returns:
        _type_: _description_
    """
    if symbol.startswith('5') or symbol.startswith('1'):
        return True
    return False

def custom_round(num, ndigits=0):
    """
    解决python 四舍五入特殊情况的处理

    在Python中，当小数的尾数是5时，round()函数会根据5前面的数字是奇数还是偶数来决定是进位还是舍去。如果前一位是奇数，则进位；如果是偶数，则舍去。这种方法称为“银行家舍入法”。

    例如：

    print(round(0.5)) # 输出: 0
    print(round(1.5)) # 输出: 2

    Args:
        num (_type_): _description_
        ndigits (int, optional): _description_. Defaults to 0.

    Returns:
        _type_: _description_
    """
    temp = num * 10 ** ndigits
    if temp >= 0:
        return int(temp + 0.5) / (10 ** ndigits)
    else:
        return int(temp - 0.5) / (10 ** ndigits)
    


'''


