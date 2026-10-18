# Clone from JoinQuant
# postId: 861a8b7c03bbec6fe0f29b60afaa178a
# backtestId: 7e7ab9ce5c1698862e6800c589076eb6
# title: 美股全细分板块 → A股ETF 隔夜轮动。求优化

def initialize(context):
    """
    美股全细分板块 → A股ETF 隔夜轮动（差额调仓优化版）
    优化：同标的连续选中时不反复买卖，仅差额调仓，节省手续费
    """
    # 1. 回测基础设置
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0,
            open_commission=0.00005, close_commission=0.00005,
            min_commission=5
        ),
        type='fund'
    )

    # 2. 全细分板块映射表
    context.sector_map = {
        # 科技细分
        '513080.XSHG': '512480.XSHG',  # 纳指半导体 → 半导体ETF
        '513380.XSHG': '512720.XSHG',  # 纳指互联网 → 计算机ETF
        '159509.XSHE': '515070.XSHG',  # 纳指科技 → 人工智能ETF
        '513100.XSHG': '159997.XSHE',  # 纳指100 → 电子ETF
        
        # 医药细分
        '513290.XSHG': '159992.XSHE',  # 纳指生物科技 → 创新药ETF
        '513200.XSHG': '159883.XSHE',  # 标普医疗 → 医疗器械ETF
        
        # 消费细分
        '159529.XSHE': '516110.XSHG',  # 标普可选消费 → 汽车ETF
        '159519.XSHE': '515170.XSHG',  # 标普必选消费 → 食品饮料ETF
        
        # 新能源
        '513790.XSHG': '515790.XSHG',  # 标普清洁能源 → 光伏ETF
        
        # 能源与周期
        '159518.XSHE': '561360.XSHG',  # 标普油气上游 → 能源ETF
        '513780.XSHG': '512400.XSHG',  # 标普原材料 → 有色金属ETF
        '513730.XSHG': '512950.XSHG',  # 标普公用事业 → 公用事业ETF
        
        # 金融地产
        '513590.XSHG': '512880.XSHG',  # 标普金融 → 证券ETF
        '513760.XSHG': '512200.XSHG',  # 标普房地产 → 房地产ETF
        
        # 工业制造
        '513770.XSHG': '516360.XSHG',  # 标普工业 → 工业ETF
    }

    # 3. 核心参数
    context.cash_etf = '511880.XSHG'  # 空仓理财：银华日利
    context.top_n = 2                      # 分仓数量
    context.min_pct_threshold = 0.005      # 最低涨幅阈值：0.8%
    context.stop_loss_pct = -0.02          # 日内止损阈值：-2%
    context.use_market_timing = True       # 开启大盘择时
    context.market_index = '000300.XSHG'   # 大盘择时基准：沪深300
    context.ma_period = 20                 # 20日均线判断趋势

    # 全局变量
    context.target_list = []
    context.buy_price_dict = {}
    context.final_position_pct = 0.0
    context.is_full_empty = False

    # 4. 定时任务
    run_daily(select_best_us_sector, '09:00')
    run_daily(trade_etf_position, '09:30')
    run_daily(market_stop_loss, '14:50')
    run_daily(handle_cash_etf, '14:55')


def select_best_us_sector(context):
    """选股：大盘择时 + 板块涨幅筛选 + 仓位分级"""
    market_position = 1.0
    if context.use_market_timing:
        prices = get_price(
            security=context.market_index,
            count=context.ma_period,
            end_date=context.current_dt,
            frequency='daily',
            fields=['close']
        )
        if len(prices) >= context.ma_period:
            ma20 = prices['close'].mean()
            current_price = prices['close'].iloc[-1]
            if current_price < ma20:
                market_position = 0.5
            if current_price < ma20 * 0.95:
                market_position = 0.0

    context.is_full_empty = (market_position <= 0)
    
    if market_position <= 0:
        context.target_list = []
        context.final_position_pct = 0.0
        return

    sector_pct = {}
    for qdii_code in context.sector_map.keys():
        try:
            prices = get_price(
                security=qdii_code,
                count=2,
                end_date=context.current_dt,
                frequency='daily',
                fields=['close']
            )
            if prices is None or len(prices) < 2:
                continue
            close_latest = prices['close'].iloc[-1]
            close_prev = prices['close'].iloc[-2]
            if close_prev <= 0:
                continue
            pct_change = (close_latest - close_prev) / close_prev
            if pct_change > context.min_pct_threshold:
                sector_pct[qdii_code] = pct_change
        except Exception:
            continue

    sorted_sectors = sorted(sector_pct.items(), key=lambda x: x[1], reverse=True)
    top_sectors = sorted_sectors[:context.top_n]

    if not top_sectors:
        context.target_list = []
        context.final_position_pct = 0.0
        context.is_full_empty = True
        return

    avg_pct = sum(pct for _, pct in top_sectors) / len(top_sectors)
    if avg_pct >= 0.02:
        position_factor = 1.0
    elif avg_pct >= 0.01:
        position_factor = 0.7
    else:
        position_factor = 0.4

    final_position = market_position * position_factor
    context.target_list = [context.sector_map[code] for code, pct in top_sectors]
    context.final_position_pct = final_position

    log.info(f"【选股完成】入选{len(context.target_list)}个板块，整体仓位：{final_position:.0%}")


def trade_etf_position(context):
    """
    9:30差额调仓：
    1. 先卖出货币基金，释放全额资金
    2. 卖出不在今日名单里的旧持仓
    3. 对今日选中的标的，调整到目标仓位
    4. 同标的连续选中时不反复买卖，仅补仓/减仓
    """
    # 第一步：先全部卖出货币基金，释放资金
    if context.cash_etf in context.portfolio.positions:
        order_target(context.cash_etf, 0)

    # 第二步：卖出不在今日名单里的旧持仓
    old_positions = list(context.portfolio.positions.keys())
    for etf_code in old_positions:
        if etf_code == context.cash_etf:
            continue
        if etf_code not in context.target_list:
            position = context.portfolio.positions[etf_code]
            if position.total_amount > 0:
                order_target(etf_code, 0)
                log.info(f"【卖出清仓】{etf_code}，调出今日组合")
    
    # 清空旧成本记录
    context.buy_price_dict.clear()

    # 第三步：调整今日标的到目标仓位
    if not context.target_list:
        log.info("【无买入计划】今日空仓")
        return

    total_target_value = context.portfolio.total_value * context.final_position_pct
    per_target_value = total_target_value / len(context.target_list)

    current_data = get_current_data()
    for etf_code in context.target_list:
        if current_data[etf_code].paused:
            log.warning(f"【调仓跳过】{etf_code} 停牌")
            continue
            
        # 当前持仓市值
        current_pos = context.portfolio.positions[etf_code]
        current_value = current_pos.total_amount * current_data[etf_code].last_price
        
        # 计算差额
        diff_value = per_target_value - current_value
        
        # 差额大于100元才交易，避免零碎仓手续费
        if abs(diff_value) > 100:
            if diff_value > 0:
                # 需要补仓
                order_value(etf_code, diff_value)
                log.info(f"【补仓】{etf_code}，补仓金额：{diff_value:.2f}元")
            else:
                # 需要减仓
                order_target_value(etf_code, per_target_value)
                log.info(f"【减仓】{etf_code}，目标市值：{per_target_value:.2f}元")
        
        # 记录当日成本价（用于日内止损）
        context.buy_price_dict[etf_code] = current_data[etf_code].last_price


def market_stop_loss(context):
    """日内止损：14:50检查"""
    if not context.buy_price_dict:
        return

    current_data = get_current_data()
    for etf_code in list(context.buy_price_dict.keys()):
        if etf_code not in context.portfolio.positions:
            continue
        current_price = current_data[etf_code].last_price
        buy_price = context.buy_price_dict[etf_code]
        profit_pct = (current_price - buy_price) / buy_price

        if profit_pct <= context.stop_loss_pct:
            order_target(etf_code, 0)
            log.warning(f"【触发止损】{etf_code}，浮亏：{profit_pct:.2%}")
            del context.buy_price_dict[etf_code]


def handle_cash_etf(context):
    """14:55空仓理财：仅完全空仓时买入货币基金"""
    if not context.is_full_empty:
        return

    available_cash = context.portfolio.available_cash
    if available_cash < 1000:
        return

    current_data = get_current_data()
    if current_data[context.cash_etf].paused:
        return

    order_value(context.cash_etf, available_cash)


def after_trading(context):
    log.info(f"【收盘】持仓：{list(context.portfolio.positions.keys())}，净值：{context.portfolio.total_value:.2f}元")
