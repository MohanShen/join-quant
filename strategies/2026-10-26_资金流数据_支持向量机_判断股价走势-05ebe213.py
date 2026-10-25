# Clone from JoinQuant
# postId: 05ebe213bd6e7f2c4a42a2686f663a3c
# backtestId: 6a815be6dd120ad296564fac4b1152cb
# title: 资金流数据+支持向量机——判断股价走势

# 导入聚宽函数库
import jqdata 
from sklearn import svm

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

    ## 创建字典
    g.predict_to_rise = {'aaa':0}
   
    # 开盘时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
   
   
   
'''-------给定一支股票的代码，判断它第二天的涨跌-------'''     
def predict(Code,context):
    predict_result = 0
    
    money_flow = jqdata.get_money_flow(Code,end_date = context.current_dt.date(),count=50)
    
    if len(money_flow)<25:
        return 0
    
    ####训练
    #print(money_flow)

    n_a_m_max = money_flow['net_amount_main'].max()
    n_a_m_min = money_flow['net_amount_main'].min()
    n_a_m_spread = n_a_m_max - n_a_m_min

    n_p_m_max = money_flow['net_pct_main'].max()
    n_p_m_min = money_flow['net_pct_main'].min()
    n_p_m_spread = n_p_m_max - n_p_m_min

    n_a_m_mean = money_flow['net_amount_main'].mean()
    n_a_m_std = money_flow['net_amount_main'].std()
    n_p_m_mean = money_flow['net_pct_main'].mean()    
    n_p_m_std = money_flow['net_pct_main'].std()
    
    X = []
    Y = []
    
    i = 4
    
    # 用前面的数据做训练
    while i < len(money_flow) - 5:
        
        if money_flow['change_pct'][i] > 0.5:
            Y.append(1)
        else:
            Y.append(0)

        x1 = (money_flow['net_amount_main'][i-1] - n_a_m_min) / n_a_m_spread
        x2 = (money_flow['net_amount_main'][i-2] - n_a_m_min) / n_a_m_spread
        x3 = money_flow['change_pct'][i-1] / 10
        x4 = (money_flow['net_pct_main'][i-1] - n_p_m_min) / n_p_m_spread

        X.append([x1,x2,x3,x4])
        
        i = i + 1

    clf = svm.SVC()
    clf.fit(X, Y)  
    
    ####预测
    x1 = (money_flow['net_amount_main'][len(money_flow)-1] - n_a_m_min) / n_a_m_spread
    x2 = (money_flow['net_amount_main'][len(money_flow)-2] - n_a_m_min) / n_a_m_spread
    x3 = money_flow['change_pct'][len(money_flow)-1] / 10
    x4 = (money_flow['net_pct_main'][len(money_flow)-1] - n_p_m_min) / n_p_m_spread

    predict_result = clf.predict([x1,x2,x3,x4])

    return predict_result
'''------------------------------------------------------'''     


'''-----------------------选取股票-----------------------'''     
#过滤停盘、涨跌停等股票
def filter_paused_and_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused 
    and not current_data[stock].is_st and 'ST' not in current_data[stock].
    name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]
    
def filter_gem_stock(context, stock_list):
    return [stock for stock in stock_list  if stock[0:3] != '300']

def filter_old_stock(context, stock_list):
    tmpList = []
    for stock in stock_list :
        days_public=(context.current_dt.date() - get_security_info(stock).start_date).days
        # 上市超过1年
        if days_public > 365:
            tmpList.append(stock)
    return tmpList
    
def filter_limit_stock(context, data, stock_list):
    tmpList = []
    curr_data = get_current_data()
    for stock in stock_list:
        # 未涨停，也未跌停
        if curr_data[stock].low_limit < data[stock].close < curr_data[stock].high_limit:
            tmpList.append(stock)
    return tmpList


#大盘止损
def stop(context):
    Code = '000300.XSHG'
    MyPrice = attribute_history(Code,60,'1d', ['close'])
    ma_60 = MyPrice['close'][-60].mean()
    ma_30 = MyPrice['close'][-30].mean()
    if ma_30<ma_60:
        return False;
    else:
        return True



# 选取流通市值小于100亿的30只股票
def select_stocks(context):
    # 选取流通市值小于100亿的100只股票
    q = query(valuation.code, valuation.circulating_market_cap).order_by(
            valuation.circulating_market_cap.asc()).filter(
            valuation.circulating_market_cap <=100).limit(50)
    df = get_fundamentals(q)
    stock_list = list(df['code'])
    
    # 过滤掉停牌的和ST的
    stock_list = filter_paused_and_st_stock(stock_list)
    #过滤掉创业板
    stock_list = filter_gem_stock(context, stock_list)
    # 过滤掉上市小于1年的
    stock_list = filter_old_stock(context, stock_list)
    # 选取前N只股票放入“目标池”
    stock_list = stock_list[:30]  
    return stock_list
'''------------------------------------------------------'''     


## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    ## 止损与清仓，对于有了的股票，判断要不要止损且止损之后不再买（维护一个止损股票的list）
    if stop(context)==False:
        #卖掉所有股票
        for key in context.portfolio.positions:
            order_target(key, amount = 0)
        return 
        
    ## 选取股票池
    g.stock_list = select_stocks(context)    
    
    ## 清空字典
    g.predict_to_rise.clear()
    
    for s in g.stock_list:
        predict_result = predict(s,context)
        #如果预测上涨，则在字典中记录这个股票的代码与价格
        if predict_result == 1:
            MyPrice = attribute_history(s,20,'1d', ['close'])
            ma_5 = MyPrice['close'][-5].mean()
            ma_20 = MyPrice['close'][-20].mean()
            
            if ma_5 > ma_20:
                price = MyPrice['close'][-1]
                #print s, price
                g.predict_to_rise[s] = price
        #如果持有且预测下跌，则卖出
        if predict_result == 0 and context.portfolio.positions[s].closeable_amount > 0:
            order_target(s, 0)
    
    # 取得当前的现金，计算购买量
    cash = context.portfolio.available_cash
    total_price = sum(g.predict_to_rise.values())
    volume = cash/total_price

    # 下单
    for s in g.predict_to_rise.keys(): #s是代码
        order_target(s, volume)
        
    