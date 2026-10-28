# Clone from JoinQuant
# postId: fce37d09e84c16ce0875c138526fae4d
# backtestId: 28aa916562ab1b568f3af613542ae6da
# title: 五因子特征重要性加权综合得分选股

# -*- coding: utf-8 -*-
from jqdata import *
import datetime

def initialize(context):
    # 设置基准
    set_benchmark('000300.XSHG')
    # 开启真实价格（避免未来函数）
    set_option('use_real_price', True)
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    # 每周一调仓（仅在交易日的周一触发）
    run_weekly(rebalance, weekday=1, time='open')

def rebalance(context):
    # 1. 获取当前日期（字符串用于 get_fundamentals）
    today_str = context.current_dt.strftime('%Y-%m-%d')
    today_date = context.current_dt.date()  # 用于日期计算
    
    # 2. 获取所有股票
    stocks = list(get_all_securities(['stock'], context.current_dt).index)
    
    # 3. 批量获取 ST 状态
    try:
        st_data = get_extras('is_st', stocks, start_date=today_str, end_date=today_str, df=True)
        is_st_dict = st_data.iloc[0].to_dict()
    except:
        is_st_dict = {stock: False for stock in stocks}
    
    # 4. 过滤有效股票
    valid_stocks = []
    current_data = get_current_data()
    
    for stock in stocks:
        # 剔除ST
        if is_st_dict.get(stock, True):
            continue
        # 剔除新股（上市<180天）
        info = get_security_info(stock)
        if (today_date - info.start_date).days < 180:
            continue
        # 剔除停牌
        if current_data[stock].paused:
            continue
        valid_stocks.append(stock)
    
    # 5. 计算因子和综合得分
    scored_stocks = []
    for stock in valid_stocks:
        try:
            # --- 因子1: PE ---
            q_pe = query(valuation.pe_ratio).filter(valuation.code == stock)
            pe_df = get_fundamentals(q_pe, date=today_str)
            if pe_df.empty:
                continue
            pe = pe_df.iloc[0, 0]
            if pe is None or pe <= 0 or pe > 100:
                continue
            
            # --- 因子2: PB ---
            q_pb = query(valuation.pb_ratio).filter(valuation.code == stock)
            pb_df = get_fundamentals(q_pb, date=today_str)
            if pb_df.empty:
                continue
            pb = pb_df.iloc[0, 0]
            if pb is None or pb <= 0 or pb > 10:
                continue
            
            # --- 因子3: ROE ---
            q_roe = query(indicator.roe).filter(indicator.code == stock)
            roe_df = get_fundamentals(q_roe, date=today_str)
            if roe_df.empty:
                continue
            roe = roe_df.iloc[0, 0]
            if roe is None or roe < 0:
                continue
            
            # --- 因子4: 20日动量 mom_20 ---
            prices_mom = attribute_history(stock, 21, '1d', ['close'])
            if len(prices_mom) < 21:
                continue
            mom_20 = prices_mom['close'][-1] / prices_mom['close'][0] - 1
            
            # --- 因子5: 20日波动率 vol_20 ---
            returns = prices_mom['close'].pct_change().dropna()
            if len(returns) < 2:
                continue
            vol_20 = returns.std() * (250 ** 0.5)
            
            # 6. 综合得分（权重参考XGBoost特征重要性）
            score = (
                (-pe) * 0.2 +      # PE 越低越好
                (-pb) * 0.1 +      # PB 越低越好
                (roe) * 0.25 +     # ROE 越高越好
                (mom_20) * 0.35 +   # 动量最重要
                (-vol_20) * 0.10   # 波动越低越好
            )
            
            scored_stocks.append((stock, score))
            
        except Exception as e:
            continue
    
    # 7. 排序并选前50只
    scored_stocks.sort(key=lambda x: x[1], reverse=True)
    selected = [stock for stock, score in scored_stocks[:5]]
    
    # 8. 调仓
    current_holdings = list(context.portfolio.positions.keys())
    
    # 卖出不在列表中的股票
    for stock in current_holdings:
        if stock not in selected:
            order_target_value(stock, 0)
    
    # 买入新入选的股票
    if selected:
        cash_per_stock = context.portfolio.available_cash / len(selected)
        for stock in selected:
            order_target_value(stock, cash_per_stock)