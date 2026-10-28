# Clone from JoinQuant
# postId: 5a1809d7c35405f0b277ea9673f55b44
# backtestId: 1da67d32c879903361cc1f0deaf48a0b
# title: 魔法公式选股+黄金分割线止盈及重建仓

# 基于魔法公式的价值投资 v0.7

# 计划处理：如果达不到第二个黄金分割点，如何办

# v0.7) 增加基于黄金分割止盈和建仓的机制
#    1）运行的第一天首次建仓
#    2）如果沪深300指数高于建仓的点数50%，那么开始追踪高点
#    3）启动高点追踪后，如果回调到第一个黄金分割点(0.382)，止盈清仓
#    4）如果继续回调第二个黄金分割点（0.618），重新建仓
#    5）如果重新建仓，回到第2）步

import numpy as np
import pandas as pd
import datetime as dt
import pickle

def initialize(context):
    
    # 设置费率
    set_commission(PerTrade(buy_cost=0.00025, sell_cost=0.00125, min_cost=5))
    # 设置基准指数：沪深300指数 '000300.XSHG'
    set_benchmark('000300.XSHG')
    # 使用真实价格回测
    set_option('use_real_price', True)
    
    # 回测环境与否
    g.back_test=None
    
    # 手工调仓文件（目前是在模拟环境中和胜算在握APP操作计划对接）
    # http://www.win9008.com/
    g.file_adjustment = 'magic_formula_adjustment_test.csv'
    write_file(g.file_adjustment,pickle.dumps({}))
    
    # 昨天，防止引入未来数据
    g.yesterday = context.current_dt -dt.timedelta(1)
    
    g.curr_hs300 = 0        # 沪深300当前点位
 
    # 如果从20060101开始回测，采用这组设置   
    g.init_hs300 = 0        # 沪深300建仓点位
    g.high_hs300 = 0        # 沪深300追踪高点
    g.reinit_hs300 = None   # 沪深300建仓的目标点位
    
    # 如果想回测20150101-现在的情况
    # 请先回测20060101-20141231的情况，
    # 然后可从日志中获取最近的状态数据：
    #    2014-10-23 09:30:00 - INFO - 满仓非追踪高点状态：沪深300建仓点2507.877
    # 于是可填写成如下数据
    #g.init_hs300 = 2507.877 # 沪深300建仓点位
    #g.high_hs300 = 0        # 沪深300追踪高点
    #g.reinit_hs300 = None   # 沪深300建仓的目标点位
    
    # 现在我想从20160418开始进入模拟盘（或者实盘跟踪）
    # 请先根据上次回测（20150101-现在），获取最近的状态数据：
    #    2016-04-15 09:30:00 - INFO - 满仓非追踪高点状态：沪深300建仓点3473.254
    # 于是可填写成如下数据。作1天的回测就可以添加到模拟盘
    # 注意：1）满仓非追踪高点状态，只需要填g.init_hs300
    #       2）满仓追踪高点状态，需要填写g.init_hs300和g.high_hs300
    #       3) 空仓等待状态，只需要填g.reinit_hs300
    #g.init_hs300 = 3473.254 # 沪深300建仓点位
    #g.high_hs300 = 0        # 沪深300追踪高点
    #g.reinit_hs300 = None   # 沪深300建仓的目标点位

    # 如果你想开始就建仓，请选择好下面两个数字
    # 设定起始月份
    g.start_month = 4
    run_monthly(stock_trading, 11, time='open')

# 每三个月调仓换股
def stock_trading(context) :
    if g.yesterday.month%3 != g.start_month%3:
        return
    
    # 每三个月记录一次关键参数
    if g.init_hs300 > 0:
        if g.high_hs300 > 0:
            log.info(u"满仓追踪高点状态：沪深300建仓点%s;沪深300高点%s"%(g.init_hs300,g.high_hs300))
        else:
            log.info(u"满仓非追踪高点状态：沪深300建仓点%s"%g.init_hs300)
    elif not g.reinit_hs300 is None:
        log.info(u"空仓等待状态：沪深300目标建仓点位%s"%g.reinit_hs300)
    
    # 清仓后，如果高于第二黄金分割点，不买股票
    if not (g.reinit_hs300 is None) and (g.curr_hs300 > g.reinit_hs300):
        return

    # 清仓后，低于于第二黄金分割点，建仓
    if g.init_hs300 == 0:
        g.init_hs300 = g.curr_hs300
        log.info(u'建仓，当前沪深300点位%s。'%g.curr_hs300)
    
    # 有待买入的20只股票
    buy_stocks = select_stocks(context,20)
    
    # ------ 先清仓 ------
    for _stock in context.portfolio.positions:
        if _stock in buy_stocks:
            buy_stocks = buy_stocks[buy_stocks != _stock]
            continue
        order_target(str(_stock), 0)
    
    # ------ 后买股票 ------
    # 单份金额
    unit_money = context.portfolio.portfolio_value/20
    for _stock in buy_stocks:
        order_value(str(_stock), unit_money)
    print buy_stocks
    
    g.reinit_hs300 = None

# 要求按天回测
def handle_data(context, data):
    # 上个交易日
    g.yesterday = context.current_dt -dt.timedelta(1)
    
    # 记录沪深300上个交易日的收盘点位
    g.curr_hs300 = data['000300.XSHG'].close
    
    # 在已建仓的情况下，止盈判定
    if g.init_hs300 > 0 :
        if g.high_hs300 > 0:  # 追踪高点的状态
            # 追踪高点
            if g.curr_hs300 > g.high_hs300:
                g.high_hs300 = g.curr_hs300
            # 如果回调到第一个黄金分割点,清仓
            if g.curr_hs300 <  g.high_hs300 - 0.382*(g.high_hs300-g.init_hs300):
                for _stock in context.portfolio.positions:
                    order_target(str(_stock), 0)
                # 第二个黄金分割点
                g.reinit_hs300 = g.high_hs300 - 0.618*(g.high_hs300-g.init_hs300)
                log.info(u'清仓,当前沪深300点位%s。上次建仓点位%s，上次区间高点%s，本次建仓目标点位%s。'%(g.curr_hs300,g.init_hs300,g.high_hs300,g.reinit_hs300))
                g.high_hs300 = 0
                g.init_hs300 = 0
        else:
            # 如果涨50%,那么开始追踪高点
            if g.curr_hs300 > g.init_hs300*1.5:
                g.high_hs300 = g.curr_hs300
                log.info(u'开始跟踪高点,当前沪深300点位%s。本次建仓点位%s。'%(g.curr_hs300,g.init_hs300))
            
    
    # 仅在模拟环境中和胜算在握APP操作计划对接
    # http://www.win9008.com/
    if not is_back_test():
        manual_position_adjustment(context, data)
    
    # 画出上一时间点沪深300点位
    record(hs300=g.curr_hs300)

# 根据魔法公式计算的结果进行选股
def select_stocks(context,num):
    ROC,EY = cal_magic_formula(context)

    # 按ROC 和 EY 构建表格
    ROC_EY = pd.DataFrame({'ROC': ROC,'EY': EY})

    # 对 ROC进行降序排序, 记录序号
    ROC_EY = ROC_EY.sort('ROC',ascending=False)
    idx = pd.Series(np.arange(1,len(ROC)+1), index=ROC_EY['ROC'].index.values)
    ROC_I = pd.DataFrame({'ROC_I': idx})
    ROC_EY = pd.concat([ROC_EY, ROC_I], axis=1)

    # 对 EY进行降序排序, 记录序号
    ROC_EY = ROC_EY.sort('EY',ascending=False)
    idx = pd.Series(np.arange(1,len(EY)+1), index=ROC_EY['EY'].index.values)
    EY_I = pd.DataFrame({'EY_I': idx})
    ROC_EY = pd.concat([ROC_EY, EY_I], axis=1)

    # 对序号求和，并记录之
    roci = ROC_EY['ROC_I']
    eyi = ROC_EY['EY_I']
    idx = roci + eyi
    SUM_I = pd.DataFrame({'SUM_I': idx})
    ROC_EY = pd.concat([ROC_EY, SUM_I], axis=1)

    # 按序号和，进行升序排序，然后选出排名靠前的20只股票
    ROC_EY = ROC_EY.sort('SUM_I')
    ROC_EY = ROC_EY.head(num)
    
    return ROC_EY.index.values
    
# 计算魔法公式
def cal_magic_formula(context):
    stocks = filter_stocks(context)
    
    q = query(    
        valuation.code,                         # 股票代码
        income.net_profit,                      # 净利润(元)
        income.financial_expense,               # 财务费用(元)
        income.income_tax_expense,              # 所得税费用(元)
        balance.fixed_assets,                   # 固定资产(元)
        balance.construction_materials,         # 工程物资(元)
        balance.constru_in_process,             # 在建工程(元)
        balance.fixed_assets_liquidation,       # 固定资产清理(元)
        balance.total_current_assets,           # 流动资产合计(元)
        balance.total_current_liability,        # 流动负债合计(元)
        valuation.market_cap,                   # 总市值(亿元)
        #valuation.circulating_cap,              # 流通股本(万股)  110000  160000
        balance.total_liability,                # 负债合计(元)
        cash_flow.cash_and_equivalents_at_end   # 期末现金及现金等价物余额(元)
    ).filter(
        income.net_profit > 0,
        #valuation.circulating_cap < 110000,     
        valuation.code.in_(stocks)
    )

    df = get_fundamentals(q, date=g.yesterday.strftime('%Y-%m-%d')).fillna(value=0).set_index('code')
    
    # 息税前利润(EBIT) = 净利润 + 财务费用 + 所得税费用
    NP = df['net_profit']
    FE = df['financial_expense']
    TE = df['income_tax_expense']
    EBIT = NP + FE + TE

    # 固定资产净额(Net Fixed Assets) = 固定资产 - 工程物资 - 在建工程 - 固定资产清理
    FA = df['fixed_assets']
    CM = df['construction_materials']
    CP = df['constru_in_process']
    FAL = df['fixed_assets_liquidation']
    NFA = FA - CM - CP - FAL

    # 净营运资本(Net Working Capital)= 流动资产合计－流动负债合计
    TCA = df['total_current_assets']
    TCL = df['total_current_liability']
    NWC = TCA - TCL

    # 企业价值(Enterprise Value) = 总市值 + 负债合计 – 期末现金及现金等价物余额
    MC = df['market_cap']*100000000
    TL = df['total_liability']
    TC = df['cash_and_equivalents_at_end']
    EV = MC + TL - TC

    # Net Working Capital + Net Fixed Assets
    NCA = NWC + NFA

    # 剔除 NCA 和 EV 非正的股票
    tmp = set(df.index.values)-set(EBIT[EBIT<=0].index.values)-set(EV[EV<=0].index.values)-set(NCA[NCA<=0].index.values)
    EBIT = EBIT[tmp]
    NCA = NCA[tmp]
    EV = EV[tmp]

    # 计算魔法公式
    ROC = EBIT / NCA
    EY = EBIT / EV
    
    return [ROC,EY]
    
# 从所有A股中过滤掉：金融服务，公用事业，创业板，新股次新股，ST  
def filter_stocks(context):
    # 获取所有A股
    df = get_all_securities('stock')
    # 剔除金融服务，公用事业
    tmp = set(df.index.values)-set(get_industry_stocks('J66'))\
            -set(get_industry_stocks('J67'))\
            -set(get_industry_stocks('J68'))\
            -set(get_industry_stocks('J69'))\
            -set(get_industry_stocks('N78')) 
    tmp = np.array(list(tmp))
    df = df.select(lambda code: code in tmp)
    #  剔除创业板
    df = df.select(lambda code: not code.startswith('300'))
    #  剔除新股次新股
    one_year = dt.timedelta(365)
    df = df[df.start_date < g.yesterday.date() - one_year]
    # 剔除ST
    df = df[map(lambda s: not s.startswith("ST") and not s.startswith("*ST") ,df.display_name)]
    
    return df.index.values

# 通过发微信消息来判定是否回测环境(必须启动微信通知才有效)
#     用g.back_test记录结果
def is_back_test():
    if g.back_test is None:
        g.back_test = not send_message(u"开始模拟盘...", channel='weixin')
    return g.back_test
    
# 手动调仓，回测环境中不执行
# 仅在模拟环境中和胜算在握APP操作计划对接
# http://www.win9008.com/
def manual_position_adjustment(context, data):
    # 到 投资研究中 执行设置交易计划
    # import pickle
    # plans={}
    # plans['000785.XSHE']=[200,1,12.8]  
    # write_file('magic_formula_adjustment.csv',pickle.dumps(plans))
    
    # 获取操作计划后清空文件
    f=read_file(g.file_adjustment)  
    plans = pickle.loads(f)
    write_file(g.file_adjustment,pickle.dumps({}))
    
    # 按计划操作
    for _stock in plans :
        _amount,is_limit,_price = plans[_stock]
        if is_limit:
            if not _price :
                _price = data[_stock].close
            order(str(_stock), _amount,LimitOrderStyle(_price))
        else:
            order(str(_stock), _amount)
