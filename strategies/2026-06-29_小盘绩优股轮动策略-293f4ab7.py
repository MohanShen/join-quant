# Clone from JoinQuant
# postId: 293f4ab774f84ea330e578e2c7dce828
# backtestId: 8b8d79deed7d1779cf7ef00c755d7d4c
# title: 小盘绩优股轮动策略

# 导入函数库
from jqdata import *

def initialize(context):
    # 1. 设定基准
    set_benchmark('000300.XSHG')
    
    # 2. 开启动态复权
    set_option('use_real_price', True)
    
    # 3. 设定交易成本
    set_order_cost(OrderCost(
        open_commission=0.0003,
        close_commission=0.0003,
        close_tax=0.001,
        min_commission=5
    ), type='stock')
    
    # 4. 全局变量设定
    g.stock_num = 5      # 持仓数量
    
    # 5. 设定定时任务：每天收盘前调仓
    run_daily(rebalance, time='14:50')

def get_qualified_stocks(context):
    """
    选股逻辑：过滤股票并按策略排序
    """
    # 1. 获取所有A股代码
    all_stocks = get_all_securities(['stock'], date=context.previous_date).index.tolist()
    
    # 2. 过滤函数（剔除ST、次新、科创板、停牌）
    filtered_stocks = filter_stocks(context, all_stocks)
    if not filtered_stocks:
        return []

    # 3. 查询基本面数据
    q = query(
        valuation.code,
        valuation.market_cap,
        indicator.roe
    ).filter(
        valuation.code.in_(filtered_stocks),
        indicator.roe > 0,
        valuation.market_cap > 0
    )
    
    # 4. 获取数据并排序
    df = get_fundamentals(q, date=context.previous_date)
    
    if not df.empty:
        # 按ROE降序，市值升序
        df = df.sort_values(by=['roe', 'market_cap'], ascending=[False, True])
        return df.head(g.stock_num)['code'].tolist()
    else:
        return []

def filter_stocks(context, stock_list):
    """
    增强型过滤：剔除ST、次新、科创板、停牌
    """
    filtered_list = []
    current_date = context.current_dt.date()
    
    for stock in stock_list:
        # 1. 获取股票基本信息
        stock_info = get_security_info(stock)
        if not stock_info:
            continue
            
        # 2. 过滤ST
        if stock_info.display_name.startswith('ST') or 'ST' in stock_info.display_name:
            continue
            
        # 3. 过滤科创板(688)和北交所(8)
        if stock.startswith('688') or stock.startswith('8'):
            continue
            
        # 4. 过滤上市不满一年的次新股
        days_since_ipo = (current_date - stock_info.start_date).days
        if days_since_ipo < 365:
            continue
            
        # 5. 过滤停牌 (获取前一天的交易数据)
        try:
            price_data = get_price(stock, 
                                 end_date=context.previous_date, 
                                 frequency='daily', 
                                 fields=['paused'], 
                                 count=1)
            if not price_data.empty and price_data['paused'][0] == True:
                continue # 跳过停牌股票
        except:
            continue # 如果获取数据出错，也跳过该股票
            
        filtered_list.append(stock)
        
    return filtered_list

def rebalance(context):
    """
    修复后的交易逻辑：强制满仓，解决资金闲置问题
    """
    # 1. 获取目标股票池
    target_stocks = get_qualified_stocks(context)
    log.info(f"【调仓日】{context.current_dt.date()} 目标选股: {target_stocks}")
    
    # 2. 获取当前持仓
    current_holdings = set(context.portfolio.positions.keys())
    
    # 3. 卖出：卖出持仓中不在目标池的股票
    for stock in list(current_holdings):
        if stock not in target_stocks:
            log.info(f"卖出剔除股: {stock}")
            order_target_value(stock, 0) # 清仓

    # 4. 买入逻辑：计算可用资金，对目标池中的每一只股票进行买入/加仓
    # 无论是否持有，都重新计算买入量，以确保资金充分利用
    if not target_stocks:
        return
        
    # 获取当前可用现金
    cash = context.portfolio.available_cash
    log.info(f"可用现金: {cash:.2f}")
    
    # 计算每只股票应分配的资金 (平均分配)
    cash_per_stock = cash / len(target_stocks)
    
    # 如果资金太少，直接返回
    if cash_per_stock < 5000:
        log.info("资金过少，暂不买入")
        return

    # 5. 遍历目标股票池，强制买入或加仓
    # 注意：这里不再判断 if s not in current_holdings，目的是为了补足仓位
    for stock in target_stocks:
        try:
            # 获取当前价格
            price_data = get_price(stock, end_date=context.previous_date, fields=['close'], count=1)
            if price_data.empty:
                continue
            price = price_data['close'][0]
            
            # 计算理论股数 (扣除手续费预留)
            estimated_shares = int((cash_per_stock / (price * 1.001)) // 100) * 100
            
            if estimated_shares >= 100:
                log.info(f"准备买入/加仓 {stock} {estimated_shares}股")
                order(stock, estimated_shares)
            else:
                log.info(f"资金不足买入一手 {stock}")
                
        except Exception as e:
            log.info(f"下单失败 {stock}: {e}")