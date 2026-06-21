# Clone from JoinQuant
# postId: 8bafb7652f737f5b4d4bc8259a22f062
# backtestId: 43a6c603bfc03e5278b80930b71fafc2
# title: 20260202万得微盘股指数868008

from jqdata import *
import pandas as pd
import numpy as np

def initialize(context):
    # 初始化函数，设定基准等等
    set_benchmark('000300.XSHG')  # 沪深300指数
    set_option('use_real_price', True)
    log.info('策略开始运行')
    
    # 设置策略参数
    g.stock_num = 40  # 成份股数量（已从400改为40）
    g.exclude_st = True  # 是否排除ST股票
    g.rebalance_period = 'monthly'  # 调仓频率：每月
    
    # 设置交易时间（每月第一个交易日9:40调仓）
    run_monthly(rebalance, 1, time='9:40')
    
    # 设置手续费和滑点
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, 
                            close_commission=0.0003, min_commission=5), type='stock')
    set_slippage(PriceRelatedSlippage(0.00246))

def before_trading_start(context):
    # 盘前运行
    pass

def rebalance(context):
    """
    调仓函数，每月第一个交易日执行
    """
    # 获取当前日期
    current_date = context.current_dt.date()
    
    # 1. 获取所有A股股票
    all_stocks = get_all_securities(types=['stock'], date=current_date).index.tolist()
    
    # 2. 剔除ST、*ST及退市警示标的
    if g.exclude_st:
        # 获取ST股票列表
        st_stocks = get_extras('is_st', all_stocks, start_date=current_date, end_date=current_date, df=True)
        
        # 筛选非ST股票
        normal_stocks = []
        for stock in all_stocks:
            # 检查是否ST
            is_st = False
            try:
                # 获取ST状态
                st_status = st_stocks.loc[current_date, stock]
                if pd.isna(st_status):
                    is_st = False
                else:
                    is_st = bool(st_status)
            except:
                is_st = False
            
            # 检查股票名称是否包含ST或退市
            stock_info = get_security_info(stock)
            stock_name = stock_info.display_name
            if stock_name is None:
                continue
                
            name_contains_st = ('ST' in stock_name or '*ST' in stock_name or 
                               '退市' in stock_name or 'SST' in stock_name)
            
            if not is_st and not name_contains_st:
                normal_stocks.append(stock)
    else:
        normal_stocks = all_stocks
    
    # 3. 获取股票市值并排序
    if len(normal_stocks) == 0:
        log.warning('没有符合条件的股票')
        return
    
    # 获取市值数据（使用前一日收盘后的市值）
    prev_date = get_trade_days(end_date=current_date, count=2)[0]
    
    # 批量查询市值，提高效率
    q = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.code.in_(normal_stocks)
    )
    
    df_market_cap = get_fundamentals(q, date=prev_date)
    
    if df_market_cap is None or len(df_market_cap) == 0:
        log.warning('没有获取到市值数据')
        return
    
    # 4. 按市值排序，选取最小的40只（已从400改为40）
    df_market_cap = df_market_cap.sort_values('market_cap', ascending=True)
    selected_stocks = df_market_cap['code'].head(g.stock_num).tolist()
    
    log.info(f'本次调仓选中{len(selected_stocks)}只股票，日期：{current_date}')
    
    # 5. 等权重分配资金
    total_value = context.portfolio.total_value
    cash = context.portfolio.cash
    
    # 计算每只股票的目标市值
    target_value_per_stock = total_value / len(selected_stocks) if selected_stocks else 0
    
    # 6. 调整持仓
    adjust_position(context, selected_stocks, target_value_per_stock)

def adjust_position(context, target_stocks, target_value_per_stock):
    """
    调整持仓到目标股票列表
    """
    # 卖出不在目标列表中的股票
    for stock in context.portfolio.positions:
        if stock not in target_stocks:
            order_target_value(stock, 0)
    
    # 调整目标股票的持仓
    for stock in target_stocks:
        # 获取当前持仓市值
        current_value = context.portfolio.positions[stock].total_amount * \
                       context.portfolio.positions[stock].price if stock in context.portfolio.positions else 0
        
        # 计算需要调整的金额
        delta_value = target_value_per_stock - current_value
        
        if abs(delta_value) > 0:
            # 计算委托数量（按当前价格）
            current_price = get_current_data()[stock].last_price
            
            if current_price > 0:
                # 计算委托股数（100股的整数倍）
                amount = int(delta_value / current_price / 100) * 100
                
                if amount > 0:
                    order(stock, amount)
                elif amount < 0:
                    order(stock, amount)
            else:
                log.warning(f'股票{stock}当前无价格数据')

def handle_data(context, data):
    """
    每分钟运行（在实盘模拟中）
    """
    pass

def after_trading_end(context):
    """
    盘后运行函数
    """
    # 记录当日持仓
    pass