# Clone from JoinQuant
# postId: 7cf56e569c507f9d0a1a449381042597
# backtestId: 913a3999a590823f4b9856ab963245f8
# title: 超短线“快刀手”：1万本金单票满仓，极致止盈损

# 导入函数库
from jqdata import *

def initialize(context):
    # 1. 基础设置
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.info('>>> 超短线“快刀手”策略启动，目标：吃一口就跑')
    
    # 2. 只有1万本金，手续费影响很大
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    
    # 3. 核心参数
    g.stock_num = 1          # 极度集中
    g.hold_limit_days = 4    # 【新增】最长持股天数，超过4天不涨强制换股
    
    # 每天早盘运行
    run_daily(market_trade, time='09:35') 

# 选股与交易主逻辑
def market_trade(context):
    current_date = context.current_dt.strftime("%Y-%m-%d")
    
    # --- 1. 卖出逻辑：收紧止盈，缩短周期 ---
    holdings = list(context.portfolio.positions.keys())
    
    for stock in holdings:
        # 获取持仓对象
        position = context.portfolio.positions[stock]
        
        # 计算持仓天数 (通过当前时间 - 建仓时间)
        # 注意：这里简单用天数差，实际交易日可能需更复杂计算，但够用了
        held_days = (context.current_dt.date() - position.transact_time.date()).days
        
        # 获取该股过去数据
        hist = get_price(stock, count=20, end_date=current_date, frequency='daily', fields=['close', 'high'])
        if len(hist) < 20: continue
        
        close_price = hist['close'][-1]
        ma5 = hist['close'][-5:].mean()   # 【修改】从MA10改为MA5，反应更快
        avg_cost = position.avg_cost
        current_ret = (close_price - avg_cost) / avg_cost
        
        # --- 卖出条件 A: 止损 (亏损超6%就跑，比原来更紧) ---
        if current_ret < -0.06:
            order_target(stock, 0)
            log.info(f"止损离场：{stock} 亏损{current_ret*100:.2f}%")
            continue
            
        # --- 卖出条件 B: 硬止盈 (赚够了就跑) ---
        # 如果你也想吃到大妖股，可以把这个15%调高，或者配合回撤止盈
        if current_ret > 0.15: 
            # 这里做一个回撤止盈：如果今日收盘价比最高点回撤超过3%，且盈利>15%，则卖出
            # 简单处理：大赚15%且跌破5日线，或者直接落袋为安
            # 这里为了“不想持股太久”，选择赚15%后，只要稍微走弱(破MA5)或者不板就走
            pass # 往下走统一用MA5判断，或者你可以直接 order_target(stock, 0)
            
        # --- 卖出条件 C: 趋势破坏 (核心修改) ---
        # 原来是MA10，现在改为：跌破MA5 必须走
        if close_price < ma5:
            order_target(stock, 0)
            log.info(f"破位止盈：{stock} 跌破5日线，当前盈利{current_ret*100:.2f}%，快速离场")
            continue

        # --- 卖出条件 D: 时间止损 (磨叽就走) ---
        # 如果持股超过3天，且盈利不足5%，说明不是龙一，换车
        if held_days >= 3 and current_ret < 0.05:
            order_target(stock, 0)
            log.info(f"时间止损：{stock} 持股3天无大涨，换股")
            continue
            
        # --- 卖出条件 E: 强制换股周期 ---
        # 如果你绝对不想拿超过一周，这里强制卖出
        if held_days >= g.hold_limit_days:
            order_target(stock, 0)
            log.info(f"到期轮动：{stock} 持股达上限天数，强制卖出")

    # --- 2. 选股逻辑：保持原有凶悍逻辑 ---
    # 如果卖出后还有持仓，则不买
    if len(context.portfolio.positions) >= g.stock_num:
        return

    # 获取所有股票
    all_stocks = list(get_all_securities(['stock']).index)
    
    # 基础过滤
    target_list = [
        s for s in all_stocks 
        if not is_st(s) 
        and not s.startswith('688') 
        and not s.startswith('300') 
        and not s.startswith('301')
        and '退' not in get_security_info(s).display_name
        and not get_current_data()[s].paused
    ]
    
    # 选股逻辑不变，依然找最强的
    q = query(valuation.code).filter(valuation.code.in_(target_list))
    df = get_fundamentals(q)
    
    candidates = []
    
    for code in df['code']:
        # 获取数据（增加open字段用于计算开盘涨幅）
        data = get_price(code, count=10, end_date=current_date, frequency='daily', fields=['close', 'volume', 'open'])
        if len(data) < 10: continue
        
        close = data['close'][-1]
        vol = data['volume'][-1]
        ma5 = data['close'][-5:].mean()
        ma10 = data['close'].mean()
        vol_ma5 = data['volume'][-5:].mean()
        
        # 必须是极强形态：P > MA5 > MA10
        if not (close > ma5 and ma5 > ma10): continue
        if not (vol > vol_ma5): continue
            
        # 计算3日涨幅
        ret_3d = (data['close'][-1] - data['close'][-3]) / data['close'][-3]
        # 计算开盘涨幅（用于日志，避免pre_close属性不存在）
        open_pct = (data['open'][-1] - data['close'][-2]) / data['close'][-2] if data['close'][-2] != 0 else 0
        
        # 选股条件：
        # 1. 股价低（适合小资金）
        # 2. 3日涨幅大（说明有资金运作）
        if close < 60 and ret_3d > 0.12: # 提高了一点门槛，找更强的
             candidates.append((code, ret_3d, open_pct))
    
    # 排序取龙头
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    # 买入
    cash = context.portfolio.available_cash
    if len(candidates) > 0 and cash > 2000:
        target, ret_3d, open_pct = candidates[0]
        
        curr_data = get_current_data()[target]
        # 没涨停才能买
        if curr_data.last_price < curr_data.high_limit:
            order_value(target, cash)
            log.info(f"超短突击：买入 {target}，3日涨幅：{ret_3d*100:.2f}%，开盘涨幅：{open_pct*100:.2f}%")

def is_st(stock):
    info = get_security_info(stock)
    return 'ST' in info.display_name or '*' in info.display_name