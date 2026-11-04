# Clone from JoinQuant
# postId: 8ce4beca2f48142f2e0ff344f569a1db
# backtestId: 81daa17d4b33c20dcbcc63be15fa0f9d
# title: 机器学习笔记014 | 对于因子选股，机器学习可以这样用

# 导入函数库
import jqdata
from datetime import timedelta
import statsmodels.api as sm
import scipy.optimize as optimize
from pandas import DataFrame,Series

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
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
    set_parameters()
    
## 开盘前运行函数     
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    
    factors = ['CMC','MC','CMC/C','TOE/MC','PB','NP/MC','TP/MC','TA/MC','OP/MC','CRF/MC','PS','OR/MC','RP/MC','TL/TA','TCA/TCL','PE','OR*ROA/NP','GPM','IRYOY','IRA','INPYOY','INPA','NPM','OPTTR','C','CC','PR','PRL','ROE','ROA','EPS','ROIC','ZYZY']
    # 因子获得因子参数
    theta,mu,sigma = getThetaByFeatures(context,factors)
    
    # 因子选股
    if sum(theta) == 0:
        return 
        
    stock_list = selectStocks(context,factors,theta,mu,sigma)
    stock_list = unStartWith300(stock_list)
    stock_list = filter_paused_and_st_stock(stock_list)
    stock_list = filter_limitup_stock(context, stock_list)
    stock_list = filter_limitup_stock(context, stock_list)
	
    g.stock_to_buy = stock_list
    
    
## 收盘后运行函数  
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')

# 设置参数
def set_parameters():
    g.period = 10
    g.buyStockCount = 50
    g.stock_to_buy = []
    g.days = 0 
    
# 交易
def trades(context,data,stock_list):
    # 卖出不在列表的股票
    for stock in context.portfolio.positions.keys():
        if stock not in stock_list:
            order_target_value(stock, 0)
            
    # 计算仍然需要购买的数量
    num_to_buy = len(stock_list) - len(context.portfolio.positions.keys())
    
    # 
    if num_to_buy == 0:
        return
    
    # 现金分配
    cash = context.portfolio.available_cash
    cash = 1.0*cash / num_to_buy
    
    for stock in stock_list:
        if stock not in context.portfolio.positions.keys():
            order_target_value(stock, cash)
            
# 每日运行
def dailyRunning(context,data):
    # 过滤涨跌停股票
    stock_list = g.stock_to_buy
    stock_list = filter_limitup_stock(context, stock_list)
    stock_list = filter_limitup_stock(context, stock_list)
    stock_list = stock_list[:g.buyStockCount]
    # 交易
    if g.days % g.period == 0:
        trades(context,data,stock_list)
        
    g.days += 1
    
    pass

## 开盘时运行函数
def handle_data(context, data):
    
    # 获得当前时间
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    
    
    # 每天下午14:50调仓
    if hour == 14 and minute == 50:
        # 每日运行
        dailyRunning(context,data)
        
#----------------------过滤-------------------------
#去除创业板
def unStartWith300(stockspool):
    return [stock for stock in stockspool if stock[0:3] != '300']
    
# 过滤停牌、ST类股票及其他具有退市标签的股票
def filter_paused_and_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused and not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]
    
# 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    # 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys() 
        or last_prices[stock][-1] < current_data[stock].high_limit]

# 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys() 
        or last_prices[stock][-1] > current_data[stock].low_limit]
#----------------------过滤-------------------------

# ----------------因子参数------------------------
# 代价函数
def costFunction(theta, X, y):
    m = len(y)
    tmp_theta = theta.reshape(len(theta),1).copy()
    temp = X.dot(tmp_theta)
    J = sum(np.square(temp-y)) /2.0/m
    return J
    
# 梯度
def gradient(theta, X, y):
    # 样本数量
    m = y.size  
    # 参数的拷贝
    tmp_theta = theta.reshape(len(theta),1).copy()  
    # 预测函数
    h = dot(X,tmp_theta)
    # 梯度计算
    grad = 1.0/m*X.T.dot(h-y)
    grad = grad.flatten()
    return grad

# 代价函数(正则化)
def costFunctionReg(theta, X, y, mylambda):
    m = len(y)
    tmp_theta = theta.reshape(len(theta),1).copy()
    temp = X.dot(tmp_theta)
    J = sum(np.square(temp-y)) /2.0/m +1.0*mylambda/2/m*sum(tmp_theta**2)
    return J
    
# 梯度
def gradientReg(theta, X, y, mylambda):
    # 样本数量
    m = y.size  
    # 参数的拷贝
    tmp_theta = theta.reshape(len(theta),1).copy()  
    # 预测函数
    h = dot(X,tmp_theta)
    # 梯度计算
    grad = 1.0/m*X.T.dot(h-y) + 1.0*mylambda/m*tmp_theta
    grad = grad.flatten()
    return grad
    
# 均值归一
def featureNormalize(X):
    mu = mean(X)
    sigma = std(X)
    X_norm = 1.0*(X - mu)/sigma
    return X_norm,mu,sigma
    
# 得到拟合参数
def getThetaByFeatures(context,factors):
    period = g.period
    period = 1
    # 上一个调仓日期
    yesterday = context.previous_date
    daysBefore = yesterday-timedelta(days=period*2) # period * 2
    trade_days = jqdata.get_trade_days(start_date=daysBefore, end_date=yesterday)
    log.info(trade_days)
    log.info(trade_days[-period-1:])
    # 周期
    trade_days = trade_days[-period-1:]
    # 起止日期
    start_date = trade_days[0]
    end_date = trade_days[-1]
    
    # 得到上一个调仓日股票的因子数据，构建特征组合
    x_df = get_factors(start_date,factors)
    # 特征缩放
    
    # 得到上一个调仓日股票的涨幅，构建结果组合
    stock_list = x_df.index.tolist()
    df = get_price(stock_list, start_date=start_date, end_date=end_date, frequency='daily', fields=['close'])['close']
    y_se = df.ix[-1] / df.ix[0] -1
    
    # 数据
    y = y_se[~ np.isnan(y_se)]
    x = x_df.ix[y.index.tolist()]
    
    # 特征数量
    n = len(x_df.columns)
    # 样本数量
    m = len(y)
    
    # 均值归一
    X_norm,mu,sigma = featureNormalize(x)
    
    # 增加一列
    X = sm.add_constant(X_norm)
    for i in X.columns:
        X[i] = np.nan_to_num(X[i])
    
    X = np.c_[X]
    y = np.c_[y]
    
    # 初始化参数
    initial_theta = np.zeros(n+1)
    
    # 正则化参数
    mylambda = 1
    
    #J = costFunctionReg(initial_theta,X, y, mylambda)
    #log.info("J:%s"%J)
    #grad = gradientReg(initial_theta, X, y, mylambda)
    #log.info("grad:%s"%grad)
    
    opts = {'disp': False, 
        'xtol': 1e-05, 
        'eps': 1.4901161193847656e-08, 
        'return_all': False, 
        'maxiter': None}
    result = optimize.minimize(costFunctionReg, initial_theta, args=(X, y, mylambda), method='Newton-CG', jac=gradientReg, hess=None, hessp=None, tol=None, callback=None, options=opts)
    theta = result.x
    
    '''
    print("\n代价函数计算结果1：\n%s"%result.fun)
    print("\n参数theta计算结果1：\n%s"%result.x)
    
    
    opts = {'disp': False, 
        'gtol': 1e-05, 
        'eps': 1.4901161193847656e-08, 
        'return_all': False, 
        'maxiter': None, 
        'norm': inf}
    result = optimize.minimize(costFunctionReg, initial_theta, args=(X, y, mylambda), method='BFGS', jac=None, tol=None, callback=None, options=opts)
    theta = result.x
    print("\n代价函数计算结果2：\n%s"%result.fun)
    print("\n参数theta计算结果2：\n%s"%result.x)
    
    opts = {'disp': False, 
        'gtol': 1e-05, 
        'eps': 1.4901161193847656e-08, 
        'return_all': False, 
        'maxiter': None, 
        'norm': inf}
    result = optimize.minimize(costFunctionReg, initial_theta, args=(X, y, mylambda), method='CG', jac=None, tol=None, callback=None, options=opts)
    theta = result.x
    print("\n代价函数计算结果3：\n%s"%result.fun)
    print("\n参数theta计算结果3：\n%s"%result.x)
    
    opts = {'disp': None, 
        'iprint': -1, 
        'gtol': 1e-05, 
        'eps': 1e-08, 
        'maxiter': 15000, 
        'ftol': 2.220446049250313e-09, 
        'maxcor': 10, 
        'maxfun': 15000}
    result = optimize.minimize(costFunctionReg, initial_theta, args=(X, y, mylambda), method='L-BFGS-B', jac=None, bounds=None, tol=None, callback=None, options=opts)
    theta = result.x
    print("\n代价函数计算结果4：\n%s"%result.fun)
    print("\n参数theta计算结果4：\n%s"%result.x)
    '''
    
    return theta,mu,sigma


# 得到因子数据
def get_factors(fdate,factors):
    #stock_set = get_index_stocks('000300.XSHG',fdate)
    q = query(
        valuation.code, # 股票代码
        valuation.circulating_market_cap, # CMC 流通市值
        valuation.market_cap, # MC 总市值 
        valuation.circulating_market_cap/valuation.capitalization*10000, # CMC/C 流通市值（亿）/总股本(万) （收盘价） 
        balance.total_owner_equities/valuation.market_cap/100000000, # TOE/MC 每元所有者权益
        valuation.pb_ratio, # PB 市净率
        income.net_profit/valuation.market_cap/100000000, # NP/MC 每元所有者净利润
        income.total_profit/valuation.market_cap/100000000, # TP/MC 每元利润总额
        balance.total_assets/valuation.market_cap/100000000, # TA/MC 每元资产总额
        income.operating_profit/valuation.market_cap/100000000, # OP/MC 每元营业利润
        balance.capital_reserve_fund/valuation.market_cap/100000000, # CRF/MC 每元资本公积
        valuation.ps_ratio, # PS 市销率
        income.operating_revenue/valuation.market_cap/100000000, # OR/MC 每元营业收入
        balance.retained_profit/valuation.market_cap/100000000, # RP/MC 每元未分配利润
        balance.total_liability/balance.total_sheet_owner_equities,# TL/TA 资产负债率
        
        balance.total_current_assets/balance.total_current_liability, # TCA/TCL  流动比率
        valuation.pe_ratio, # PE 市盈率
        income.operating_revenue*indicator.roa/income.net_profit, # OR*ROA/NP  总资产周转率        
        indicator.gross_profit_margin, # GPM 销售毛利率
        
        indicator.inc_revenue_year_on_year, # IRYOY  营业收入同比增长率(%) 
        indicator.inc_revenue_annual, # IRA 营业收入环比增长率(%)
        indicator.inc_net_profit_year_on_year, # INPYOY 净利润同比增长率(%)
        indicator.inc_net_profit_annual, # INPA  净利润环比增长率(%) 
        indicator.net_profit_margin, # NPM  销售净利率(%) 
        indicator.operation_profit_to_total_revenue, # OPTTR  营业利润/营业总收入(%) 
        valuation.capitalization,# C 总股本
        valuation.circulating_cap, # CC 流通股本(万股)
        valuation.pcf_ratio, # PR 市现率
        valuation.pe_ratio_lyr, # PRL 市盈率LYR
        indicator.roe, # ROE  净资产收益率ROE(%) 
        indicator.roa, # ROA  总资产净利率ROA(%) 
        
        indicator.eps, # EPS 每股盈余
        
        # ROIC
        # EBIT = 净利润 + 利息 + 税
        # ROIC
        (income.net_profit+income.financial_expense+income.income_tax_expense)/(balance.total_owner_equities+balance.shortterm_loan+balance.non_current_liability_in_one_year+balance.longterm_loan+balance.bonds_payable+balance.longterm_account_payable),
        
        # 资源占用情况 = 占用资金 / 投入资本
        # 占用资金 = （应付账款accounts_payable+预收款项advance_peceipts+其他应付款other_payable）-（应收账款account_receivable+预付款项advance_payment+其他应收款other_receivable）
        # 投入资本 = 股东权益 + 有息负债
        # 有息负债 = 短期借款shortterm_loan + 1年内到期的长期负债non_current_liability_in_one_year + 长期借款longterm_loan + 应付债券bonds_payable + 长期应付款longterm_account_payable
        (balance.accounts_payable+balance.advance_peceipts+balance.other_payable-balance.account_receivable-balance.advance_payment-balance.other_receivable)/(balance.total_owner_equities+balance.shortterm_loan+balance.non_current_liability_in_one_year+balance.longterm_loan+balance.bonds_payable+balance.longterm_account_payable)
        
        
        ).filter(
        #valuation.code.in_(stock_set),
        valuation.circulating_market_cap
    )
    fdf = get_fundamentals(q, date=fdate)
    fdf.index = fdf['code']
    fdf.columns = ['code'] + factors
    # 行：选择全部，列，返回除了股票代码所有因子
    return fdf.iloc[:,1:]
# ----------------因子参数------------------------

# 选股方法
def selectStocks(context, factors,theta,mu,sigma):
    
    x_df = get_factors(context.current_dt,factors)
    
    X_norm = (x_df-mu)/sigma
    X = sm.add_constant(X_norm)
    
    for i in X.columns:
        X[i] = np.nan_to_num(X[i])
		
	# 参数的拷贝
    tmp_theta = theta.reshape(len(theta),1).copy()  
    # 预测函数
    h = dot(X,tmp_theta)
    
    # 结果赋值,预测的涨幅
    X['predict'] = h
    
    X = X.sort(columns=['predict'],ascending=[False])
	
    return X.index.tolist()
    
    
    
    