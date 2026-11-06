# Clone from JoinQuant
# postId: b4649f1e2a0c1c2d0a6e38dc75de9b76
# backtestId: 90bc76f05a5e49c5a9790febd2c3645b
# title: 基于均线理论操作ETF，实盘中

# 导入函数库
from jqdata import *

# 初始化函数
def initialize(context):
    # 设定基准
    set_benchmark('159949.XSHE')
    set_option('use_real_price', True)
    log.info('均线交易策略-ETF')
    
    # ETF交易设置
    set_order_cost(OrderCost(
        close_tax=0,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5
    ), type='stock')

    # 运行函数
    run_daily(before_market_open, time='9:00')
    run_daily(market_open, time='9:30')
    run_daily(after_market_close, time='15:00')
    
    # ETF配置字典 - 统一管理股票和参数
    g.etf_config = {
        '159949.XSHE': {'name': '创业板50ETF', 'window_short': 5, 'window_long': 10},
        '159869.XSHE': {'name': '游戏ETF', 'window_short': 5, 'window_long': 10},
        '588000.XSHG': {'name': '科创50ETF', 'window_short': 5, 'window_long': 10},
        '159509.XSHE': {'name': '纳斯达克科技ETF', 'window_short': 5, 'window_long': 10},
        '162719.XSHE': {'name': '石油LOF', 'window_short': 5, 'window_long': 10},
        '159562.XSHE': {'name': '黄金股ETF', 'window_short': 5, 'window_long': 10},
        '515880.XSHG': {'name': '通信ETF', 'window_short': 5, 'window_long': 10},
        '515790.XSHG': {'name': '光伏ETF', 'window_short': 5, 'window_long': 10},
        '159851.XSHE': {'name': '金融科技ETF', 'window_short': 5, 'window_long': 10},
        '159530.XSHE': {'name': '机器人ETF', 'window_short': 5, 'window_long': 10},
        '520500.XSHG': {'name': '恒生创新药ETF', 'window_short': 5, 'window_long': 10},
        '588120.XSHG': {'name': '科创100', 'window_short': 5, 'window_long': 10},
        '512710.XSHG': {'name': '军工龙头', 'window_short': 5, 'window_long': 10},
        '159638.XSHE': {'name': '高端装备', 'window_short': 5, 'window_long': 10},
        '562800.XSHG': {'name': '稀有金属', 'window_short': 5, 'window_long': 10},
  #      '159206.XSHE': {'name': '卫星ETF', 'window_short': 5, 'window_long': 10},
  #      '513980.XSHG': {'name': '港股科技50', 'window_short': 5, 'window_long': 10},
        '159930.XSHE': {'name': '有色大成', 'window_short': 5, 'window_long': 10},
  #      '513330.XSHG': {'name': '恒生互联网', 'window_short': 5, 'window_long': 10},
        '513310.XSHG': {'name': '中韩芯片', 'window_short': 5, 'window_long': 10},
        '512980.XSHG': {'name': '传媒', 'window_short': 5, 'window_long': 10},
  #      '159995.XSHE': {'name': '芯片', 'window_short': 5, 'window_long': 10},
 #       '520600.XSHG': {'name': '港股汽车', 'window_short': 5, 'window_long': 10},
           }
    
    # 从配置中提取股票列表
    g.etf_list = list(g.etf_config.keys())
    
    # 国债ETF作为现金管理工具
    g.cash_management_etf = '511010.XSHG'  # 国债ETF
    
    # 策略参数
    g.stop_loss_threshold = 0.08  # 止损比例8%
    g.max_holdings = 4 # 最大持有数量

    # 状态变量
    g.break_status = {etf: {'up': False, 'down': False} for etf in g.etf_list}
    g.max_position_value = 0

# 开盘前运行函数
def before_market_open(context):
    log.info('='*40)
    log.info('交易日开始：%s' % context.current_dt.date())
    g.max_position_value = max(g.max_position_value, context.portfolio.positions_value)

# 早上提醒函数
def before_market_open(context):
    log.info("早上好！已经做好今日的交易准备。")
    send_message("早上好！已经做好今日的交易准备。")

# 计算均线信号
def check_ma_signal(security, price_data, window_short, window_long):
    if len(price_data) < window_long:
        return None
    
    MA_long = price_data['close'][-window_long:].mean()
    MA_short = price_data['close'][-window_short:].mean()
    current_price = price_data['close'][-1]
    
    condition_up = current_price > 1.015 * MA_long    # 突破长期均线+1.5%
    condition_down = current_price < 0.98 * MA_long   # 跌破长期均线-2%
    condition_short_up = current_price > 1.005 * MA_short  # 突破短期均线+0.5%
    condition_short_down = current_price < 0.995 * MA_short # 跌破短期均线-0.5%
    
    return {
        'price': current_price,
        'MA_long': MA_long,
        'MA_short': MA_short,
        'condition_up': condition_up,
        'condition_down': condition_down,
        'condition_short_up': condition_short_up,
        'condition_short_down': condition_short_down
    }

# 盘中交易函数
def market_open(context):
    current_position_value = context.portfolio.positions_value
    g.max_position_value = max(g.max_position_value, current_position_value)
    
    # ========== 止损逻辑 ==========
    if current_position_value > 0 and g.max_position_value > 0:
        drawdown = (g.max_position_value - current_position_value) / g.max_position_value
        if drawdown > g.stop_loss_threshold:
            for security in context.portfolio.positions:
                position = context.portfolio.positions[security]
                log.info("‼️ 触发止损(8%%)：当前回撤%.2f%%，清仓 %s %d股" % 
                       (drawdown*100, security, position.closeable_amount))
                order_target(security, 0)  # 全仓卖出
            g.max_position_value = 0
            return
    
    # ========== 轮动交易逻辑 ==========
    signals = {}
    cash = context.portfolio.available_cash
    
    # 1. 检查所有ETF信号
    for security in g.etf_list:
        try:
            config = g.etf_config[security]
            price_data = get_price(security,
                                 end_date=context.current_dt,
                                 frequency='daily',
                                 fields=['close'],
                                 count=config['window_long']+5,
                                 skip_paused=True)
            
            ma_signal = check_ma_signal(security, price_data,
                                      config['window_short'],
                                      config['window_long'])
            if ma_signal:
                signals[security] = ma_signal
                if ma_signal['condition_up'] and not g.break_status[security]['up']:
                    g.break_status[security]['up'] = True
                    log.info("[%s] %s 突破长期均线上轨(+2.5%%) %.4f > %.4f" % (
                        security, config['name'], ma_signal['price'], 1.025*ma_signal['MA_long']))
                
                if ma_signal['condition_down'] and not g.break_status[security]['down']:
                    g.break_status[security]['down'] = True
                    log.info("[%s] %s 跌破长期均线下轨(-3%%) %.4f < %.4f" % (
                        security, config['name'], ma_signal['price'], 0.97*ma_signal['MA_long']))
        except Exception as e:
            log.warning("获取 %s 数据失败：%s" % (security, str(e)))
    
    current_holding = list(context.portfolio.positions.keys())
    
    # 2. 找出所有符合条件的买入ETF
    buy_candidates = []
    for security in g.etf_list:
        if security in signals:
            signal = signals[security]
            # 买入条件：先跌破长期下轨，再突破短期上轨
            if (g.break_status[security]['down'] and signal['condition_short_up']):
                buy_candidates.append(security)
    
    # 3. 卖出不符合条件的持仓
    for security in current_holding:
        if security not in buy_candidates and security in signals:
            signal = signals[security]
            # 卖出条件：先突破长期上轨，再跌破短期下轨
            if (g.break_status[security]['up'] and signal['condition_short_down']):
                position = context.portfolio.positions[security]
                config = g.etf_config[security]
                log.info("🚨 卖出信号触发 [%s] %s，清仓 %d股" % (security, config['name'], position.closeable_amount))
                log.info("价格：%.4f | 长期MA：%.4f(+%.2f%%) | 短期MA：%.4f(-%.2f%%)" % (
                    signal['price'],
                    signal['MA_long'],
                    (signal['price']/signal['MA_long']-1)*100,
                    signal['MA_short'],
                    (1-signal['price']/signal['MA_short'])*100))
                order_target(security, 0)  # 全仓卖出
                g.break_status[security]['up'] = False
                g.max_position_value = 0
    
    # 4. 重新计算当前持仓（卖出后可能变化）
    current_holding = list(context.portfolio.positions.keys())
    
    # 5. 买入符合条件的ETF（资金平均分配到所有持仓）
    if len(buy_candidates) > 0:
        # 将新买入候选加入当前持仓
        all_holdings = list(set(current_holding + [etf for etf in buy_candidates if etf not in current_holding]))
        
        # 限制最大持仓数量
        if len(all_holdings) > g.max_holdings:
            # 优先保留当前持仓，然后按买入候选顺序保留
            all_holdings = current_holding[:g.max_holdings]
            if len(all_holdings) < g.max_holdings:
                available_slots = g.max_holdings - len(all_holdings)
                new_candidates = [etf for etf in buy_candidates if etf not in all_holdings]
                all_holdings.extend(new_candidates[:available_slots])
        
        # 计算总资金（当前持仓市值 + 可用现金）
        total_portfolio_value = context.portfolio.total_value
        
        # 计算每只股票的目标市值（平均分配）
        target_value_per_stock = total_portfolio_value / len(all_holdings) if len(all_holdings) > 0 else 0
        
        log.info("💰 资金分配：总资产%.2f元，持仓%d只，每只目标市值%.2f元" % 
                (total_portfolio_value, len(all_holdings), target_value_per_stock))
        
        # 调整每只股票的持仓到目标市值
        for security in all_holdings:
            current_position = context.portfolio.positions.get(security)
            current_value = current_position.value if current_position else 0
            
            # 计算需要调整的金额
            adjust_value = target_value_per_stock - current_value
            
            if adjust_value > 0 and security in buy_candidates:
                # 买入
                config = g.etf_config[security]
                signal = signals.get(security)
                if signal:
                    log.info("🚨 买入信号触发 [%s] %s，买入金额 %.2f元" % (security, config['name'], adjust_value))
                    log.info("价格：%.4f | 长期MA：%.4f(-%.2f%%) | 短期MA：%.4f(+%.2f%%)" % (
                        signal['price'],
                        signal['MA_long'],
                        (1-signal['price']/signal['MA_long'])*100,
                        signal['MA_short'],
                        (signal['price']/signal['MA_short']-1)*100))
                    order_value(security, adjust_value)
                    g.break_status[security]['down'] = False
            elif adjust_value < 0:
                # 卖出（只卖出超出目标的部分）
                config = g.etf_config[security]
                log.info("📉 调整持仓 [%s] %s，卖出金额 %.2f元" % (security, config['name'], -adjust_value))
                order_value(security, adjust_value)  # adjust_value为负值
    
    # 6. 重置无效的突破状态
    for security in g.etf_list:
        if security in signals:
            if not signals[security]['condition_up']:
                g.break_status[security]['up'] = False
            if not signals[security]['condition_down']:
                g.break_status[security]['down'] = False
    
    # ========== 现金管理逻辑 ==========
    # 检查当前是否有现金且没有持有其他ETF
    current_holding_after_trade = list(context.portfolio.positions.keys())
    if (context.portfolio.available_cash > 0 and 
        not any(etf in current_holding_after_trade for etf in g.etf_list)):
        
        # 检查是否已经持有国债ETF
        if g.cash_management_etf in context.portfolio.positions:
            # 如果已有国债ETF持仓，检查是否需要追加
            current_position = context.portfolio.positions[g.cash_management_etf]
            if context.portfolio.available_cash > current_position.price * 100:  # 至少够买1手
                log.info("💰 追加买入国债ETF(511010)作为现金管理，金额: %.2f元" % context.portfolio.available_cash)
                order_value(g.cash_management_etf, context.portfolio.available_cash)
        else:
            # 如果没有国债ETF持仓，买入国债ETF
            if context.portfolio.available_cash > 100 * get_price(g.cash_management_etf, end_date=context.current_dt, count=1, fields='close')['close'][-1]:  # 确保资金足够买1手
                log.info("💰 买入国债ETF(511010)作为现金管理，金额: %.2f元" % context.portfolio.available_cash)
                order_value(g.cash_management_etf, context.portfolio.available_cash)
    
    # 如果持有国债ETF但需要买入其他ETF，先卖出国债ETF
    if (g.cash_management_etf in context.portfolio.positions and
        any(etf in signals for etf in g.etf_list if signals[etf]['condition_short_up'] and g.break_status[etf]['down'])):
        
        position = context.portfolio.positions[g.cash_management_etf]
        log.info("🔄 卖出国债ETF(511010)准备买入其他ETF，卖出 %d股" % position.closeable_amount)
        order_target(g.cash_management_etf, 0)

# 收盘后处理
def after_market_close(context):
    trades = get_trades()
    if trades:
        log.info("当日成交汇总：")
        for trade in trades.values():
            log.info("%s %s %d股 @%.4f" % (
                '买入' if trade.amount > 0 else '卖出',
                trade.security,
                abs(trade.amount),
                trade.price))
    
    total = context.portfolio.total_value
    position = context.portfolio.positions_value
    cash = context.portfolio.available_cash
    
    drawdown = 0
    if position > 0 and g.max_position_value > 0:
        drawdown = (g.max_position_value - position) / g.max_position_value
    
    log.info("账户状态：总资产：%.2f | 持仓市值：%.2f | 可用现金：%.2f | 当前回撤：%.2f%%" % (
        total, position, cash, drawdown*100))
    
    for security in context.portfolio.positions:
        pos = context.portfolio.positions[security]
        profit_pct = (pos.price/pos.avg_cost-1)*100 if pos.price >= pos.avg_cost else (1-pos.price/pos.avg_cost)*100
        status = "浮盈%.2f%%" % profit_pct if pos.price >= pos.avg_cost else "浮亏%.2f%%" % profit_pct
        # 显示股票名称
        stock_name = g.etf_config[security]['name'] if security in g.etf_config else security
        log.info("持仓：%s %s %d股 成本%.4f 当前%.4f %s" % (
            security,
            stock_name,
            pos.total_amount,
            pos.avg_cost,
            pos.price,
            status))
    
    log.info('='*40)