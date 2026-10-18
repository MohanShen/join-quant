# Clone from JoinQuant
# postId: fcc8c3efa95ff565f60bb1d1d609c5a7
# backtestId: 1ad853824759b0d15f2c5a12be5da20c
# title: 一个偏重防守的低波动策略，根据MACD底背离策略改写

'''
大盘择时：
    doSafety
    1.沪深300(000300.XSHG)的MACD是红柱则认为大盘是安全的，此时可以选择适合的个股买入
    2.后来发现上述判据在12年回测中回撤过大，又增加了一些判断大盘安全的条件
        a. 如果60日均线向上，则只要沪深300出现红柱即可
        b. 如果60日均线向上，则除了沪深300出现红柱，还要求沪深300的20日均线向上
        
个股买入：
    1.在大盘安全的情况下选择个股
    2.选择条件是底背离 doDecide
    3.如果符合条件的个股数+现有持仓股票数<=g.owning,则全部买入,否则买入(g.owning-现有持仓股票数)只股票
    
个股卖出：
    每天开盘前对持仓的个股作如下判断
    1.跌10%卖出
    2.顶背离卖出
    3.不符合选股条件(0<PE<90,非ST)的股票卖出，例如现在持仓的股票今天变为ST或者PE>90或PE<0，则卖出
'''

# enable_profile()
import talib
import numpy as np
import pandas as pd

def initialize(context):
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))	# 设置手续费
    g.owning = 5                    # 持仓股票数####
    g.muster = []                   # 预选股票池
    g.summit = {}                   # 区间最高价
    g.i = 400
    #g.security='000300.XSHG'
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    
def before_trading_start(context):
    # 取得当前日期
    g.today = context.current_dt.strftime('%Y-%m-%d')
    # 设置预选股票(小市值+0<PE<90，剔除ST)
    g.muster = doSelect(context, g.today)
    set_universe(g.muster)
    # 清理股票峰值信息
    for stock in g.summit.keys():
        if stock not in context.portfolio.positions: del g.summit[stock]

# 每个单位时间调用一次(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)
def handle_data(context, data):
    # H0、取得今天股票价格信息--------------------------------------------------
    grid = get_price(context.universe, g.today, g.today, fields=['paused', 'open', 'high_limit', 'low_limit'])
    # H1、清仓操作--------------------------------------------------遍历持仓股票
    for stock in context.portfolio.positions:
        # SS、记录股票峰值信息
        if g.summit.get(stock, 0)<data[stock].high: 
            g.summit[stock]=data[stock].high
        # SP、跳过停牌股票
        if grid.paused[stock][0]: continue
        # S1、目前持仓不在预选股票池中(g.muster)则清仓
        if stock not in g.muster:
            doLaunch(g.owning, stock, '越界清仓')
        # S2、回撤10%则清仓
        elif grid.open[stock][0]/g.summit[stock]<0.9:####
            doLaunch(g.owning, stock, '回撤清仓')
        # S3、指标卖出信号、止盈清仓
        if doDecide(stock)['dead']:
            doLaunch(g.owning, stock, '死叉清仓')
    # HS、趋势判断--------------------------------------------------判断大盘走势
    if not doSafety(context, data, '000300.XSHG'): return
    # H2、建仓操作--------------------------------------------------遍历预选股票
    for stock in g.muster:
        # BP、跳过停牌股票
        if grid.paused[stock][0]: continue
        # B1、指标买入信号
        if doDecide(stock)['gold']:
            if doLaunch(g.owning, stock, '金叉建仓', context)['enough']: break



def doSelect(context,stamp, scale=0.14):###
    """
    stock_to_choose = get_fundamentals(query(
        valuation.code, valuation.pe_ratio, 
        valuation.pb_ratio,valuation.market_cap, 
        indicator.eps, indicator.inc_net_profit_annual
    ).filter(
        valuation.pe_ratio < 40,
        valuation.pe_ratio > 0,#30,
        indicator.eps > 0.2,
        indicator.inc_net_profit_annual > 0.20,
        indicator.roe > 0.20
    ).order_by(
        valuation.pb_ratio.asc()
    ).limit(
        50), date=None)
    """
    #399649.XSHE	中小红利
    #000015.XSHG    红利指数
    
    #000826.XSHG	民企红利 OK
    
    #399324.XSHE    深圳红利
    #399411.XSHE    国证红利
    
    #000035.XSHG	上证可选 OK
    #000036.XSHG	上证消费
    
    #000937.XSHG	中证公用
    
    #399006.XSHE	创业板指
    
    #399409.XSHE	小盘高贝
    
    #399405.XSHE	大盘高贝
    
    #000134.XSHG	上证银行 OK
    
    #000849.XSHG	沪深300非银行金融指数
    
    #399966.XSHE	800非银
    
    #HY493	多元化银行	1991-04-04
    #HY494	区域性银行	2007-07-20
    #HY004	可选消费指	1999-12-30
    
    stockpool = get_industry_stocks('HY493') + get_industry_stocks('HY494') + get_index_stocks('000826.XSHG')   # list(stock_to_choose['code'])  #将筛选出的股票代码存入list中
    #stockpool = get_industry_stocks('HY493') + get_industry_stocks('HY494') # get_industry_stocks('HY004') 
    stockpool = paused_filter(stockpool)
    stockpool = delisted_filter(stockpool)
    stockpool = st_filter(stockpool)
    
    stock_to_choose = get_fundamentals(query(
        valuation.code, valuation.pe_ratio, 
        valuation.pb_ratio,valuation.market_cap, 
        indicator.eps, indicator.inc_net_profit_annual
    ).filter(
        #valuation.pe_ratio < 40,
        valuation.pe_ratio > 0,#30,
        indicator.eps > 0,
        #indicator.inc_net_profit_annual > 0.05,
        #indicator.roe > 0.20,
        valuation.code.in_(stockpool)
    ).order_by(
        valuation.pb_ratio.desc() #asc()valuation.market_cap.asc()
    ).limit(
        550), date=None)
        
    stockpool=list(stock_to_choose['code'])
    
    return stockpool
    
# 过滤停牌、退市、ST股票
def paused_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].paused]
    return security_list


def delisted_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not '退' in current_data[stock].name]
    return security_list

def st_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].is_st]
    return security_list


# 大盘趋势======================================================================
def doSafety(context, data, index='000300.XSHG'):
    fast = 11
    slow = 26
    sign =  5
    rows = (fast + slow + sign) * 5
    suit = {'dif':0, 'dea':0, 'macd':0, 'safe':False, 'gold':False, 'dead':False}
    grid = attribute_history(index, rows, fields=['open', 'high', 'low', 'close', 'high_limit', 'low_limit']).dropna()
    try:
        #MA_Type: 0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA, 5=TRIMA, 6=KAMA, 7=MAMA, 8=T3 (Default=SMA)
        C_SMA=0
        C_WMA=2
        C_DEMA=3
        
        dif, dea, macd = talib.MACD(grid['close'].values, fastperiod=fast, slowperiod=slow, signalperiod=sign)
        MA60=talib.MA(grid['close'].values,60,matype=C_SMA)
        WMA20=talib.MA(grid['close'].values,20,matype=C_WMA)
        
        """
        #根据大盘好坏决定是否可以做个股###
        if MA60[-1]>=MA60[-2]:
            #60日均线向上，则判断大盘好坏的条件宽松
            suit['safe'] = macd[-1]>0
        elif dif[-1]<-100:
            #60日均线向下，但是dif<-100属于超跌反弹，则此时有利可图，放宽条件
            suit['safe'] = macd[-1]>0  
        else:
            #60日均线向下，且不属于超跌反弹，则判断大盘好坏的条件苛刻
            suit['safe'] = macd[-1]>0 and (WMA20[-1]>WMA20[-2])
        """
        
    except:
        pass
        
    suit['safe'] = macd[-1]>0 and grid['close'].values[-1] > WMA20[-1]
    
    return suit['safe']

# 下单函数======================================================================
def doLaunch(total, stock, title, context=None):
    assign = 0
    direct = None
    result = {'enough': False}
    # 判断买单还是卖单----------------------------------------------------------
    if context: # 买单
        assign = doAssign(total, context)
        if assign>0: direct = order_value(stock, assign)
        else:        result['enough'] = True
    else:       # 卖单
        direct = order_target(stock, 0)
    # 记录日志------------------------------------------------------------------
    if direct: 
        print '%s：stock=%s,下单数量=%d,成交数量=%d,成交价格=%.2f,成交金额=%.2f,目标金额=%.2f' % (title, stock, direct.amount, direct.filled, direct.price, direct.filled*direct.price, assign)
    else:
        print '%s：stock=%s,目标金额=%.2f,下单失败!' % (title, stock, assign)
    # 返回结果------------------------------------------------------------------
    return result

# 资金分配======================================================================
def doAssign(total, context):
    # 计算持仓股票数量、差额股票数量--------------------------------------------
    remain = 0
    for stock in context.portfolio.positions:
        if context.portfolio.positions[stock].amount>0: remain+=1
    for stock in context.portfolio.unsell_positions:
        if context.portfolio.unsell_positions[stock].amount>0: remain+=1
    margin = total - remain
    # 按差额股票数量平均分配剩余现金--------------------------------------------
    if context.portfolio.cash>0 and margin>0: 
        result = context.portfolio.cash/margin
    else:
        result = 0
    # 返回结果------------------------------------------------------------------
    return result

# 决策函数======================================================================
def doDecide(stock):
    fast = 11
    slow = 26
    sign =  5
    rows = (fast + slow + sign) * 5
    suit = {'dif':0, 'dea':0, 'macd':0, 'gold':False, 'dead':False}
    grid = attribute_history(stock, rows, fields=['close']).dropna()
    try:
        grid['dif'], grid['dea'], grid['macd'] = talib.MACD(grid['close'].values, fast, slow, sign)
        grid = grid.dropna()
        # 底背离----------------------------------------------------------------
        mask = grid['macd']>0 #金叉
        mask = mask[mask==True][mask.shift(1)==False]
        key2 = mask.keys()[-2]
        key1 = mask.keys()[-1]
        #1.本次(key1指定的日期)金叉股价低于上一次(不是昨天，是key2指定的日期)金叉股价
        #2.本次(key1指定的日期)金叉Dif值大于上一次(不是昨天，是key2指定的日期)金叉Dif值
        #3.金叉出现，即MACD由前天的负值变为昨天的正值
        suit['gold'] = grid.close[key2]>grid.close[key1] and \
                           grid.dif[key2]<grid.dif[key1]<0   and \
                       grid.macd[-2]<0<grid.macd[-1]
        # 顶背离----------------------------------------------------------------
        mask = grid['macd']<0 #死叉
        mask = mask[mask==True][mask.shift(1)==False]
        key2 = mask.keys()[-2]
        key1 = mask.keys()[-1]
        suit['dead'] = grid.close[key2]<grid.close[key1] and \
                       grid.dif[key2]>grid.dif[key1]>0   and \
                       grid.macd[-2]>0>grid.macd[-1]
        
    except:
        #如果找不到金叉,则执行key2 = mask.keys()[-2]或会抛出异常，
        #说明这么多行【rows = (fast + slow + sign) * 5】数据中找不到金叉
        #直接返回suit
        pass
    return suit
    
    
# ======================================================================
# 选股函数1
# 三一投资公司价值选股法
# 莫邪的救赎
# https://www.joinquant.com/post/556
# ======================================================================
def Check_PE(context):
    PE = get_fundamentals(query(
            valuation.code,
            valuation.day,
            valuation.pe_ratio
        ).filter(
            valuation.pe_ratio > 0,
        ).order_by(
            # 按PE升序排列
            valuation.pe_ratio.asc()
        ).limit(
            g.i
        ))
    return list(PE.code)

def Check_PB(context):
    PB = get_fundamentals(query(
            valuation.code,
            valuation.day,
            valuation.pb_ratio
        ).filter(
            valuation.pb_ratio > 0,
        ).order_by(
            # 按PB升序排列
            valuation.pb_ratio.asc()
        ).limit(
            g.i
        ))
    return list(PB.code)

def Check_Dividend_Yield(context):
    EPS = get_fundamentals(query(
        income.code,
        income.day,
        income.basic_eps
    ))
    L = list(EPS.code)
    h = history(1, '1d', 'price', security_list=L, df=False)
    DY_stock = dict(zip(EPS['code'],EPS['basic_eps']))
    for stock in L:
        DY_stock[stock] = DY_stock[stock]/h[stock][0]
    DY_stock = sorted(DY_stock.iteritems(),key=lambda t:t[1],reverse=True)
    return DY_stock[:g.i]

# ======================================================================
# 选股函数2
# 克隆自聚宽文章：https://www.joinquant.com/post/708
# 标题：【量化选股专题】在稳定增长中寻找超额收益
# 作者：莫邪的救赎# 克隆自聚宽文章：https://www.joinquant.com/post/708
# 标题：【量化选股专题】在稳定增长中寻找超额收益
# 作者：莫邪的救赎
# ======================================================================

def Check_Stocks(context):
    '''
    为防止亏损公司或财务指标异常公司的影响。
    剔除资产报酬率、毛利率、权益报酬率等异常的公司。
    即要求 ROA>0.5%、 adj-ROE>2%、利润总额>0、毛利率>0。
    选取投资收益率 > 0；
    根据PB升序排列，取前30%；
    根据三费占比升序排列，取前30%；
    根据收入现金率降序排列，取前30%；
    '''

    ## 获取财务数据
    df = get_fundamentals(query(
            valuation.code, #股票代码
            valuation.pb_ratio, #市净率
            income.total_profit, #利润总额
            income.total_operating_revenue, #营业总收入
            income.total_operating_cost, #营业总成本
            income.sale_expense,  #销售费用
            income.administration_expense, #管理费用
            income.financial_expense, #财务费用
            income.operating_revenue, #主营业务收入 
            balance.total_assets, #资产总计
            balance.total_liability, #负债合计
            balance.account_receivable, #应收账款
            balance.accounts_payable,  #应付账款
            income.investment_income, #投资收益
            cash_flow.goods_sale_and_service_render_cash, #销售商品、提供劳务收到的现金(
        ).filter(
            #ROA>0.5% (资产报酬率=利润总额/总资产)
            income.total_profit/balance.total_assets > 0.005, 
            #adj-ROE>2% (调整的净资产报酬率=利润总额/净资产)
            income.total_profit/(balance.total_assets-balance.total_liability) > 0.02, 
            #利润总额>0
            income.total_profit>0, 
            #毛利率>0 (（主营业务收入-主营业务成本） / 主营业务收入)
            (income.total_operating_revenue-income.total_operating_cost)/income.total_operating_revenue>0, 
        )).dropna() #去除NaN值
    
    ## 指标计算    
        # 三费占比=（销售费用＋管理费用＋财务费用） /主营业务收入
    df['3'] = (df.sale_expense+df.administration_expense+df.financial_expense)/df.operating_revenue
        # 投资收益率 = 投资收益/总资产
    df['tzsy'] = df.investment_income / df.total_assets
        # 收入现金率 = 销售商品提供劳务收到的现金/主营业务收入
    df['srxj'] = df.goods_sale_and_service_render_cash / df.operating_revenue
    #     # 应收账款占比=应收账款/主营业务收入
    # df['ys'] = df.account_receivable / df.operating_revenue
    #     # 应付账款占比=应付账款/主营业务收入
    # df['yf'] = df.accounts_payable / df.operating_revenue

    ## 股票筛选
        # 投资收益率 > 0
    df = df[df.tzsy > 0]
        # 根据PB升序排列，取前30%
    df = df.sort_index(by=['pb_ratio'],ascending=True)
    code1 = list(df.code.head(int(len(df)*0.3)))
        # 根据三费占比升序排列，取前30%
    df2 = df[df.code.isin(code1)]
    df2 = df2.sort_index(by=['3'],ascending=True)
    code2 = list(df2.code.head(int(len(df2)*0.3)))
    print len(code2)
        # 根据收入现金率降序排列，取前30%
    df3 = df2[df2.code.isin(code2)]
    df3 = df3.sort_index(by=['srxj'],ascending=False )
    code3 = list(df3.code.head(int(len(df3)*0.3)))
    print len(code3)
    
    return code3
# ======================================================================