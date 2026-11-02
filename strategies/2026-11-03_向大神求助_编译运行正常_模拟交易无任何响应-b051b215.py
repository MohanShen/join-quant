# Clone from JoinQuant
# postId: b051b21587324b0c779874ae99b2cfa8
# backtestId: d964565a1527558f3eb4a4d974c94863
# title: 向大神求助：编译运行正常，模拟交易无任何响应

#import numpy as np
#import pandas as pd
#import traceback
import datetime as dt
import scipy.optimize as sco
from RunTimePoint import *

def initialize(context):
    # 设置手续费费率
    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0.001, 
            open_commission=0.00015, close_commission=0.00015, 
            close_today_commission=0, min_commission=5
        ),  type='stock')
        
    # 设置基准指数：沪深300指数'000300.XSHG'
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.set_level('order','error')
    

def process_initialize(context):
    timepoint = RunTimePoint().set_runtimepoint()
    run_monthly(stock_trading, timepoint, time='open')#
    
def stock_trading(context) :
    # 昨天，防止引入未来数据
    g.yesterday = context.current_dt -dt.timedelta(1)
    #if g.yesterday.month%3!=2: #每三个月调仓换股
    #    return
    # 有待买入的5只股票
    buy_stocks = list(select_stocks(context,5))
    #print(buy_stocks)
    
    n_assets = len(buy_stocks)
    adj_dic, reb_dic = {}, {}
    # 获取股票的收盘价
    prices = get_price(buy_stocks, count = 20, frequency='daily', fields=['close'])
    # 获取股票的收益率
    g.returns = prices['close'].pct_change().dropna()
    g.cov = g.returns.cov()
    g.returns_means = np.mean(g.returns, axis=0)

    #约束是所有参数(权重)的总和为1。这可以用minimize函数的约定表达如下
    cons = ({'type':'eq', 'fun':lambda x: np.sum(x)-1})
    
    #我们还将参数值(权重)限制在0和1之间。这些值以多个元组组成的一个元组形式提供给最小化函数
    bnds = tuple((0,1) for x in range(n_assets))
    
    maxmum_shape_ratio = sco.minimize(max_sharpe, n_assets*[1./n_assets,], method = 'SLSQP', 
                        bounds = bnds, constraints = cons)
    minimum_variance = sco.minimize(min_variance, n_assets*[1./n_assets,], method = 'SLSQP', 
                        bounds = bnds, constraints = cons)
    print(maxmum_shape_ratio['x'].round(2))
    print(minimum_variance['x'].round(2))
    weights = minimum_variance['x'].round(2)
    if np.var(maxmum_shape_ratio['x'])<np.var(minimum_variance['x']):
        
        weights = maxmum_shape_ratio['x'].round(2)
    else: 
        weights = minimum_variance['x'].round(2)
        
    # 如果权重压在某只股票上的比例过于集中，则采用资金平均比例分摊
    if max(weights) > 0.7:
        weights = n_assets*[1./n_assets,]
        #print(weights)
    #weights = optv['x'].round(4)
    log.info('Final weights：',weights)
    print(buy_stocks)
    # ------先清仓------
    for _stock in context.portfolio.positions:
        if _stock not in buy_stocks:
            print('SELL')
            #buy_stocks.remove(_stock)
            
            #continue
            order_target(str(_stock), 0)
    #print(context.portfolio.positions.keys())
    # ------再买股票------
    try:
        total_value = context.portfolio.total_value
        for stock, weight in zip(g.returns.columns, weights):
            if stock in context.portfolio.positions:
                adj_dic[stock] = weight
            else:
                reb_dic[stock] = weight
        print('REBALANCE')    
        for (k, v) in adj_dic.items():
            order_target_value(k, total_value * v)
        for (k, v) in reb_dic.items():
            order_target_value(k, total_value * v)
    except ValueError as e:
        # Sometimes this error is thrown
        # ValueError: Rank(A) < p or Rank([P; A; G]) < n
        pass

# 
def handle_data(context, data):
    pass

# 根据魔法公式计算的结果进行选股
def select_stocks(context,num):
    ROC,EY = cal_magic_formula(context)

    # 按ROC 和 EY 构建Data
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
        balance.total_liability,                # 负债合计(元)
        cash_flow.cash_and_equivalents_at_end,  # 期末现金及现金等价物余额(元)
        indicator.inc_net_profit_to_shareholders_year_on_year,
        valuation.market_cap,
        valuation.pe_ratio,
        valuation.pb_ratio,
        balance.total_current_assets,           # 流动资产合计
        balance.total_current_liability,         # 流动负债合计
        balance.inventories,
        balance.advance_payment
    ).filter(
        income.net_profit > 0,
        valuation.market_cap > 50,
        valuation.pe_ratio < 15,
        valuation.pb_ratio < 1.5,
        # 流动比率
        #balance.total_current_assets/balance.total_current_liability>2,
        #(balance.total_current_assets-balance.inventories-balance.advance_payment)/balance.total_current_liability>1,
        indicator.inc_net_profit_to_shareholders_year_on_year>0,
        valuation.code.in_(stocks)
    )

    df = get_fundamentals(q, date=g.yesterday.strftime('%Y-%m-%d')).fillna(value=0).set_index('code')
    
    # 息税前利润(EBIT) = 净利润 + 财务费用 + 所得税费用
    NP,FE,TE = df['net_profit'],df['financial_expense'],df['income_tax_expense']
    EBIT = NP + FE + TE

    # 固定资产净额(Net Fixed Assets) = 固定资产 - 工程物资 - 在建工程 - 固定资产清理
    FA,CM,CP,FAL = df['fixed_assets'],df['construction_materials'],df['constru_in_process'],df['fixed_assets_liquidation']
    NFA = FA - CM - CP - FAL

    # 净营运资本(Net Working Capital)= 流动资产合计－流动负债合计
    TCA,TCL = df['total_current_assets'],df['total_current_liability']
    NWC = TCA - TCL

    # 企业价值(Enterprise Value) = 总市值 + 负债合计 – 期末现金及现金等价物余额
    MC,TL,TC = df['market_cap']*100000000,df['total_liability'],df['cash_and_equivalents_at_end']
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
    tmp = set(df.index.values)\
         -set(get_industry_stocks('J66'))\
         -set(get_industry_stocks('J67'))\
         -set(get_industry_stocks('J68'))\
         -set(get_industry_stocks('J69'))\
         -set(get_industry_stocks('N78'))
    df = df.select(lambda stock: stock in tmp)
    #  剔除创业板
    df = df.select(lambda st: not st.startswith('300'))
    #  新股次新股
    one_year = dt.timedelta(365)
    df = df[df.start_date < g.yesterday.date() - one_year]
    # 剔除ST
    df = df[map(lambda s: not "ST" in s ,df.display_name)]
    #print(df)
    # 剔除停牌
    df = df.select(lambda st: not get_current_data()[st].paused)
    #[stock for stock in stock_list if not current_data[stock].paused]
    return df.index.values
#但是我们定义一个函数对 方差进行最小化
def min_variance(weights):
    return create_portfolio(weights)[1]
#最小化夏普指数的负值
def max_sharpe(weights):
    return -create_portfolio(weights)[2]

# 按权重生成投资组合
def create_portfolio(weights):
    weights = np.array(weights)
    port_returns = np.dot(weights.T, g.returns_means)
    port_variance = np.sqrt(np.dot(weights.T, np.dot(g.cov, weights)))
    return np.array([port_returns, port_variance, port_returns/port_variance])