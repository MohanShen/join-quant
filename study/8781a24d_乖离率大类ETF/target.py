# Clone from JoinQuant
# postId: 8781a24d18da17e82c146e8487932ec3
# backtestId: d994deb8eae09665c489ffce1039d4e9
# title: 基于乖离率的大类ETF策略（ETF复现之五）

import pandas as pd

# ==================== 策略初始化（所有可调参数100%集中在此处，一键调参） ====================
def initialize(context):
    # ========== 1. 基础运行设置 ==========
    set_option('avoid_future_data', True)  # 避免未来数据
    set_option('use_real_price', True)     # 使用真实价格
    # 日志级别设置
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('history', 'error')

    # ========== 2. 交易成本&滑点设置 ==========
    # 滑点：千分之一
    set_slippage(FixedSlippage(0.001))  
    # 交易手续费：万二双边，最低5元（ETF无印花税）
    set_order_cost(OrderCost(
    open_tax=0,                # 买入印花税：ETF无印花税，固定0
    close_tax=0,               # 卖出印花税：ETF无印花税，固定0
    open_commission=0.0002,     # 买入佣金：万二（0.02%）
    close_commission=0.0002,    # 卖出佣金：万二（0.02%）
    close_today_commission=0,   # 平今仓佣金：ETF无特殊规则，固定0
    min_commission=5            # 最低佣金：5元
    ), type='stock')

    # ========== 3. 核心运行&选股参数 ==========
    g.run_time = "11:29"              # 策略每日运行时间
    g.etf_list = [                   # 交易标的列表
        '162411.XSHE',  # 华宝油气
        '513100.XSHG',  # 纳指100
        '515450.XSHG',  # 红利
        '159915.XSHE',  # 创业板
        '159920.XSHE'   # 恒生
    ]

    # ========== 4. 指标周期参数（核心N日参数，全可调） ==========
    g.data_fetch_days = 22           # 获取历史数据的总天数
    g.rise_calc_days = 21            # 涨幅计算周期（21日涨幅）
    g.ma_calc_days = 20              # 均线计算周期（20日均线）

    # ========== 5. 买入规则参数（可调） ==========
    g.buy_rise_threshold = 3         # 买入：21日涨幅 大于 该值(%)
    g.buy_bias_threshold = 10        # 买入：20日乖离率 小于等于 该值(%)

    # ========== 6. 卖出规则参数（可调） ==========
    g.sell_rise_threshold = -3       # 卖出：21日涨幅 小于 该值(%)
    g.sell_bias_threshold = 20       # 卖出：20日乖离率 大于等于 该值(%)
    g.sell_profit_ratio = 1.09       # 卖出：止盈比例（收盘价/买入价≥该值）

    # ========== 7. 全局变量 ==========
    g.buy_price = {}                 # 记录持仓买入成本

    # 启动策略每日运行
    run_daily(strategy_main, time=g.run_time)

# ==================== 指标计算（无硬编码，全部调用全局参数） ====================
def get_etf_indicators(context):
    metrics = []
    for etf in g.etf_list:
        # ==================== 修复点1：校验标的有效性，无效直接跳过 ====================
        sec_info = get_security_info(etf)
        if not sec_info:
            log.warn(f"标的 {etf} 不存在，已跳过")
            continue
        
        # 取数天数使用全局参数
        df = attribute_history(etf, g.data_fetch_days, '1d', ['close'], skip_paused=True, df=True, fq='pre')
        name = sec_info.display_name
        
        if len(df) < g.data_fetch_days:
            metrics.append([etf, name, 0.00000, 0.00000, 0.00000, 0.00000])
            continue
        
        # 所有数值统一保留5位小数
        close_1d = round(df['close'].iloc[-1], 5)        
        # 涨幅计算：使用全局周期参数
        close_rise_ago = round(df['close'].iloc[-g.rise_calc_days], 5)
        change_rise = round((close_1d / close_rise_ago - 1) * 100, 5)
        # 均线+乖离率：使用全局周期参数
        ma_line = round(df['close'].iloc[-g.ma_calc_days:].mean(), 5)
        bias_line = round((close_1d - ma_line) / ma_line * 100, 5)            
        
        metrics.append([etf, name, close_1d, ma_line, change_rise, bias_line])
    
    return pd.DataFrame(metrics, columns=['代码', '名称', '收盘价', f'{g.ma_calc_days}日均线', f'{g.rise_calc_days}日涨幅(%)', f'{g.ma_calc_days}日乖离率(%)'])

# ==================== 策略主逻辑（无硬编码数字，全部调用初始化参数） ====================
def strategy_main(context):
    # 1. 获取指标 + 按N日涨幅降序排序，取第一名
    df = get_etf_indicators(context)
    df_sorted = df.sort_values(by=f'{g.rise_calc_days}日涨幅(%)', ascending=False).reset_index(drop=True)
    if df_sorted.empty:
        return
    top_code = df_sorted.iloc[0]['代码']
    top_data = df_sorted.iloc[0]

    # 2. 获取当前持仓
    holdings = {code: pos for code, pos in context.portfolio.positions.items() if pos.total_amount > 0}

    # ==================== 卖出逻辑 ====================
    for code in list(holdings.keys()):
        stock_data = df[df['代码'] == code].iloc[0]
        rise_value = stock_data[f'{g.rise_calc_days}日涨幅(%)']
        bias_value = stock_data[f'{g.ma_calc_days}日乖离率(%)']
        current_close = stock_data['收盘价']
        buy_cost = g.buy_price.get(code, 0)

        # 调用全局参数
        cond1 = rise_value < g.sell_rise_threshold
        cond2 = bias_value >= g.sell_bias_threshold
        cond3 = (current_close / buy_cost) >= g.sell_profit_ratio if buy_cost > 0 else False
        cond4 = code != top_code

        # 满足任一条件卖出
        if cond1 or cond2 or cond3 or cond4:
            order_target_value(code, 0)
            if code in g.buy_price:
                del g.buy_price[code]

    # ==================== 买入逻辑 ====================
    if top_code not in holdings:
        # 调用全局参数
        buy_condition = (top_data[f'{g.rise_calc_days}日涨幅(%)'] > g.buy_rise_threshold) and (top_data[f'{g.ma_calc_days}日乖离率(%)'] <= g.buy_bias_threshold)
        if buy_condition:
            order_target_value(top_code, context.portfolio.available_cash)
            g.buy_price[top_code] = round(top_data['收盘价'], 5)

def handle_data(context, data):
    pass