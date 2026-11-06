# Clone from JoinQuant
# postId: 75df4f9ec84338a71b8d00ba615f0379
# backtestId: d55129ae1e29129be30c888ceb74e926
# title: 自用做t策略 自定义标的

# 克隆自聚宽文章：https://www.joinquant.com/post/73551
# 标题：神奇九转做T升级版：双创板自适应+ATR趋势过滤
# 作者：小野牛

# 克隆自聚宽文章：日内九转做T多股策略（加入双创板20%波幅自适应 + 1.5%/3.5%差异化止盈止损 + ATR信号过滤 + MA20单边趋势过滤 + 微信推送）
# 适用于：5分钟/15分钟周期的日内股票回测与模拟交易

import jqdata
import numpy as np

def initialize(context):
    # ---------------- 1. 股票池及理想底仓数量配置 ----------------
    g.target_stocks = {
        '301526.XSHE': 900,    # 国际复材 (创业板)
        '601677.XSHG': 1000,   # 明泰铝业 (主板)
        '300483.XSHE': 1000,   # 首华燃气 (创业板)
        '600309.XSHG': 300,    # 万华化学 (主板)
        '002028.XSHE': 100,    # 思源电气 (主板)
        '600188.XSHG': 800,    # 兖矿能源 (主板)
        '300776.XSHE': 100,    # 帝尔激光 (创业板)
        '000338.XSHE': 600,    # 潍柴动力 (主板)
        '002384.XSHE': 100,    # 东山精密 (主板)
        '300308.XSHE': 100     # 中际旭创 (创业板，迈威尔/AI核心标的)
    }
    
    # ---------------- 2. 策略核心参数 ----------------
    g.time_frame = '5m'         
    
    # 【新增】主板基础止盈止损参数（10%涨跌幅限制）
    g.main_tp_rate = 0.015  
    g.main_sl_rate = 0.015  
    
    # 【新增】双创板高弹性止盈止损参数（20%涨跌幅限制，放宽止盈防卖飞）
    g.gem_kc_tp_rate = 0.035  
    g.gem_kc_sl_rate = 0.025  
    
    # 趋势过滤参数（20日均线）
    g.trend_period = 20
    g.daily_ma20 = {stock: 0.0 for stock in g.target_stocks.keys()}
    
    # 【新增】ATR 自适应波动率过滤参数容器
    g.daily_atr = {stock: 0.0 for stock in g.target_stocks.keys()}
    
    # 初始化日内净敞口、开仓价格、日内开盘价字典
    g.intraday_net_pos = {stock: 0 for stock in g.target_stocks.keys()}
    g.t_open_price = {stock: 0.0 for stock in g.target_stocks.keys()}
    g.day_start_price = {stock: 0.0 for stock in g.target_stocks.keys()}
    
    # 标记是否已经执行过启动检查
    g.has_checked_position = False 
    
    # ---------------- 3. 环境与交易成本设置 ----------------
    set_benchmark('000300.XSHG')  
    set_option('use_real_price', True) 
    
    set_slippage(FixedSlippage(0.02))
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, 
                             close_commission=0.0003, min_commission=5), type='stock')
    
    # ---------------- 4. 定时任务 ----------------
    run_daily(before_market_open, time='09:00')
    run_daily(close_intraday_position, time='14:55')


def get_name(stock):
    """ 安全获取股票中文名称的辅助函数（懒加载模式） """
    if not hasattr(g, 'stock_names'):
        g.stock_names = {}
    if stock not in g.stock_names:
        info = get_security_info(stock)
        g.stock_names[stock] = info.display_name if info else stock
    return g.stock_names[stock]


def get_stock_thresholds(stock):
    """
    【核心新增】根据板块20%振幅特性懒加载不同的买卖点与止盈止损阈值
    返回: (止盈比例, 止损比例, 板块描述)
    """
    code = stock.split('.')[0]
    # 创业板(300xxx, 301xxx) 或 科创板(688xxx)
    if code.startswith('30') or code.startswith('68'):
        return g.gem_kc_tp_rate, g.gem_kc_sl_rate, "双创板(20%)"
    else:
        return g.main_tp_rate, g.main_sl_rate, "主板(10%)"


def before_market_open(context):
    for stock in g.target_stocks.keys():
        g.intraday_net_pos[stock] = 0
        g.t_open_price[stock] = 0.0 
        g.day_start_price[stock] = 0.0
        
        # 1. 每天盘前计算一次前20天的日线MA20，作为当日大趋势基准
        prices = attribute_history(stock, g.trend_period, '1d', ['close'], skip_paused=True)
        if len(prices) == g.trend_period:
            g.daily_ma20[stock] = prices['close'].mean()
        else:
            g.daily_ma20[stock] = 0.0 
            
        # 2. 【核心新增】计算日线ATR，用于动态过滤日内无序震荡
        atr_data = attribute_history(stock, g.trend_period + 1, '1d', ['high', 'low', 'close'], skip_paused=True)
        if len(atr_data) >= g.trend_period:
            highs = atr_data['high'].values[1:]
            lows = atr_data['low'].values[1:]
            prev_closes = atr_data['close'].values[:-1]
            
            # 计算真实波幅 TR
            tr1 = highs - lows
            tr2 = np.abs(highs - prev_closes)
            tr3 = np.abs(lows - prev_closes)
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            g.daily_atr[stock] = np.mean(tr[-g.trend_period:])
        else:
            g.daily_atr[stock] = 0.0


def get_td_signal(closes):
    if len(closes) < 13:
        return 0
        
    is_buy_9 = True
    is_sell_9 = True
    
    for i in range(1, 10):
        if closes[-i] >= closes[-i-4]:
            is_buy_9 = False
        if closes[-i] <= closes[-i-4]:
            is_sell_9 = False
            
    if is_buy_9:
        return 1
    elif is_sell_9:
        return -1
    else:
        return 0


def handle_data(context, data):
    # ---------------- 【智能对齐底仓 & 清理非底仓】 ----------------
    if not g.has_checked_position:
        print(f"\n=========== {context.current_dt} 策略启动：开始盘点底仓并清理杂鱼持仓 ===========")
        
        current_positions = list(context.portfolio.positions.keys())
        for stock in current_positions:
            if stock not in g.target_stocks:
                position_amount = context.portfolio.positions[stock].total_amount
                if position_amount > 0:
                    order_target(stock, 0)
                    stock_name = get_name(stock)
                    msg = f"【⚠️特异持仓清理】股票 [{stock} {stock_name}] 不在目标底仓列表中，已执行一键平仓 {position_amount} 股！"
                    print(msg)
                    send_message(msg, channel='weixin') 

        for stock, target_amount in g.target_stocks.items():
            if target_amount <= 0 or data[stock].paused:
                continue
                
            stock_name = get_name(stock)
            
            if stock in context.portfolio.positions:
                actual_amount = context.portfolio.positions[stock].total_amount
            else:
                actual_amount = 0
                
            needed_amount = target_amount - actual_amount
            
            if needed_amount > 0:
                required_cash = data[stock].price * needed_amount
                if context.portfolio.available_cash >= required_cash:
                    order(stock, needed_amount)
                    msg = f"【底仓买入】[{stock} {stock_name}] 目标 {target_amount} 股，已有 {actual_amount} 股，买入补齐 {needed_amount} 股。"
                    print(msg)
                    send_message(msg, channel='weixin') 
                else:
                    print(f"[{stock} {stock_name}] 需买入初始底仓 {needed_amount} 股，但现金不足！")
            elif needed_amount == 0:
                print(f"[{stock} {stock_name}] 当前持仓 {actual_amount} 股，已达理想底仓。")
            else:
                print(f"[{stock} {stock_name}] 当前持仓 {actual_amount} 股，超过设定，暂不买入。")
                
        print("========================================================================================\n")
        g.has_checked_position = True
    # -------------------------------------------------------------

    current_time = context.current_dt.strftime('%H:%M')
    
    if current_time >= '14:29':
        return
        
    if g.time_frame == '5m' and context.current_dt.minute % 5 != 0:
        return
    elif g.time_frame == '15m' and context.current_dt.minute % 15 != 0:
        return
        
    current_data = get_current_data()
        
    for stock, base_amount in g.target_stocks.items():
        if base_amount <= 0 or data[stock].paused:
            continue
            
        stock_name = get_name(stock)
        net_pos = g.intraday_net_pos[stock]
        trade_amount = base_amount  
        current_price = data[stock].price 
        
        # 【新增逻辑】记录开盘首个周期的价格作为日内基准参考价
        if g.day_start_price[stock] == 0.0:
            g.day_start_price[stock] = current_price
            
        # 【核心新增】获取当前股票定制化的动态盈亏阈值
        tp_rate, sl_rate, board_desc = get_stock_thresholds(stock)
        
        # ---------------- 动态止盈止损风控模块 ----------------
        if net_pos != 0:
            entry_price = g.t_open_price[stock]
            if entry_price > 0:
                if net_pos > 0:  
                    pnl_ratio = (current_price - entry_price) / entry_price
                    if pnl_ratio >= tp_rate:
                        order(stock, -net_pos)
                        profit = (current_price - entry_price) * net_pos
                        msg = f"【✅动态止盈】[{stock} {stock_name}({board_desc})] 做多T涨幅达 {pnl_ratio*100:.2f}%(阈值:{tp_rate*100:.1f}%)，获利抛出 {net_pos} 股。盈亏: {profit:.2f} 元。"
                        log.warn(msg)
                        send_message(msg, channel='weixin')
                        g.intraday_net_pos[stock] = 0
                        g.t_open_price[stock] = 0.0
                        continue  
                        
                    elif pnl_ratio <= -sl_rate:
                        order(stock, -net_pos)
                        profit = (current_price - entry_price) * net_pos
                        msg = f"【❌动态止损】[{stock} {stock_name}({board_desc})] 做多T跌幅达 {pnl_ratio*100:.2f}%(阈值:{-sl_rate*100:.1f}%)，断臂止损 {net_pos} 股。盈亏: {profit:.2f} 元。"
                        log.warn(msg)
                        send_message(msg, channel='weixin')
                        g.intraday_net_pos[stock] = 0
                        g.t_open_price[stock] = 0.0
                        continue
                        
                elif net_pos < 0:  
                    pnl_ratio = (entry_price - current_price) / entry_price
                    abs_pos = abs(net_pos)
                    
                    if pnl_ratio >= tp_rate:
                        required_cash = current_price * abs_pos
                        if context.portfolio.available_cash >= required_cash:
                            order(stock, abs_pos)
                            profit = (entry_price - current_price) * abs_pos
                            msg = f"【✅动态止盈】[{stock} {stock_name}({board_desc})] 做空T跌幅达 {pnl_ratio*100:.2f}%(阈值:{tp_rate*100:.1f}%)，获利接回 {abs_pos} 股。盈亏: {profit:.2f} 元。"
                            log.warn(msg)
                            send_message(msg, channel='weixin')
                            g.intraday_net_pos[stock] = 0
                            g.t_open_price[stock] = 0.0
                            continue
                            
                    elif pnl_ratio <= -sl_rate:
                        required_cash = current_price * abs_pos
                        if context.portfolio.available_cash >= required_cash:
                            order(stock, abs_pos)
                            profit = (entry_price - current_price) * abs_pos
                            msg = f"【❌动态止损】[{stock} {stock_name}({board_desc})] 做空T反弹达 {-pnl_ratio*100:.2f}%(阈值:{-sl_rate*100:.1f}%)，认亏接回 {abs_pos} 股。盈亏: {profit:.2f} 元。"
                            log.warn(msg)
                            send_message(msg, channel='weixin')
                            g.intraday_net_pos[stock] = 0
                            g.t_open_price[stock] = 0.0
                            continue
        # -------------------------------------------------------------
            
        bars = get_bars(stock, count=14, unit=g.time_frame, fields=['close'])
        if len(bars) < 13:
            continue
            
        closes = bars['close']
        td_signal = get_td_signal(closes)
        
        if stock in context.portfolio.positions:
            actual_total_amount = context.portfolio.positions[stock].total_amount
            closeable_amount = context.portfolio.positions[stock].closeable_amount
        else:
            actual_total_amount = 0
            closeable_amount = 0
            
        # 【核心新增】计算当前价格偏离日内开盘价的绝对距离
        intraday_deviation = abs(current_price - g.day_start_price[stock])
        # 设定偏离阈值：偏离需大于 0.5 倍日线 ATR，否则视为噪音
        atr_filter_threshold = 0.5 * g.daily_atr[stock]
            
        # ---------------- 触发买入九转（超跌点） ----------------
        if td_signal == 1:
            # 过滤判定
            if g.daily_atr[stock] > 0 and intraday_deviation < atr_filter_threshold:
                print(f"【⚡信号过滤】[{stock} {stock_name}] 触发买入9转，但日内波幅 {intraday_deviation:.2f} 未达 ATR过滤线({atr_filter_threshold:.2f})，判定为窄幅无序震荡，放弃执行。")
                continue

            # 平做空T的敞口
            if net_pos < 0:
                required_cash = current_price * trade_amount
                if context.portfolio.available_cash >= required_cash:
                    order(stock, trade_amount)
                    g.intraday_net_pos[stock] += trade_amount
                    
                    profit = (g.t_open_price[stock] - current_price) * trade_amount
                    msg = f"【信号平仓】[{stock} {stock_name}] 现买入9转，平仓做空T，低位接回 {trade_amount} 股。单笔盈亏: {profit:.2f} 元。"
                    log.warn(msg)
                    send_message(msg, channel='weixin')
                    g.t_open_price[stock] = 0.0 
                else:
                    msg = f"【⚠️信号拦截】[{stock} {stock_name}] 触发买入9转，本需低位平空接回，但资金不足！"
                    print(msg)
                    send_message(msg, channel='weixin')
                    
            # 发起做多T（开新仓）
            elif net_pos == 0:
                stock_ma20 = g.daily_ma20[stock]
                if stock_ma20 > 0 and current_price < stock_ma20:
                    msg = f"【⚠️趋势拦截】[{stock} {stock_name}] 触发买入9转 -> 股价低于MA20({stock_ma20:.2f})，大趋势看空，防暴跌拒接飞刀！"
                    print(msg)
                    send_message(msg, channel='weixin')
                    continue
                    
                if closeable_amount >= trade_amount:
                    if actual_total_amount + trade_amount <= 2 * base_amount:
                        required_cash = current_price * trade_amount
                        if context.portfolio.available_cash >= required_cash:
                            order(stock, trade_amount)
                            g.intraday_net_pos[stock] += trade_amount
                            g.t_open_price[stock] = current_price 
                            msg = f"【信号开仓】[{stock} {stock_name}] 买入9转且大趋势向上，做多T买入 {trade_amount} 股。开仓价: {current_price:.2f} 元。"
                            print(msg)
                            send_message(msg, channel='weixin')
                        else:
                            msg = f"【⚠️信号拦截】[{stock} {stock_name}] 触发买入9转，准备做多T，但账户可用资金不足！"
                            print(msg)
                            send_message(msg, channel='weixin')
                    else:
                        msg = f"【⚠️信号拦截】[{stock} {stock_name}] 触发买入9转 -> 拟开仓量超出限制（当前持仓已达上限，不执行重复买多）。"
                        print(msg)
                        send_message(msg, channel='weixin')
                else:
                    msg = f"【⚠️信号拦截】[{stock} {stock_name}] 触发买入9转 -> 可用底仓不足（底仓已被冻结或清空，无法实施日内多T）。"
                    print(msg)
                    send_message(msg, channel='weixin')
            else:
                msg = f"【🔔信号提示】[{stock} {stock_name}] 触发买入9转信号，但当前已有做多T净敞口({net_pos}股)，不进行重复开仓。"
                print(msg)
                send_message(msg, channel='weixin')
                    
        # ---------------- 触发卖出九转（超涨点） ----------------
        elif td_signal == -1:
            # 过滤判定
            if g.daily_atr[stock] > 0 and intraday_deviation < atr_filter_threshold:
                print(f"【⚡信号过滤】[{stock} {stock_name}] 触发卖出9转，但日内波幅 {intraday_deviation:.2f} 未达 ATR过滤线({atr_filter_threshold:.2f})，判定为窄幅无序震荡，放弃执行。")
                continue

            # 平做多T的敞口
            if net_pos > 0:
                order(stock, -trade_amount)
                g.intraday_net_pos[stock] -= trade_amount
                
                profit = (current_price - g.t_open_price[stock]) * trade_amount
                msg = f"【信号平仓】[{stock} {stock_name}] 现卖出9转，平仓做多T，高位抛出 {trade_amount} 股。单笔盈亏: {profit:.2f} 元。"
                log.warn(msg)
                send_message(msg, channel='weixin')
                g.t_open_price[stock] = 0.0 
                
            # 发起做空T（开新仓）
            elif net_pos == 0:
                today_bars = get_bars(stock, count=1, unit='1d', fields=['high'], include_now=True)
                if len(today_bars) > 0:
                    today_high = today_bars['high'][0]
                    if today_high >= current_data[stock].high_limit - 0.01:
                        msg = f"【⚠️涨停拦截】[{stock} {stock_name}] 触发卖出9转 -> 今日已触及涨停价，多头极度强势，防卖飞拒做空T！"
                        print(msg)
                        send_message(msg, channel='weixin')
                        continue

                stock_ma20 = g.daily_ma20[stock]
                if stock_ma20 > 0 and current_price >= stock_ma20:
                    msg = f"【⚠️趋势拦截】[{stock} {stock_name}] 触发卖出9转 -> 股价高于MA20({stock_ma20:.2f})，大趋势看多，防逼空拒摸高顶！"
                    print(msg)
                    send_message(msg, channel='weixin')
                    continue
                    
                if closeable_amount >= trade_amount:
                    order(stock, -trade_amount)
                    g.intraday_net_pos[stock] -= trade_amount
                    g.t_open_price[stock] = current_price 
                    msg = f"【信号开仓】[{stock} {stock_name}] 卖出9转且大趋势向下，做空T卖出 {trade_amount} 股。开仓价: {current_price:.2f} 元。"
                    print(msg)
                    send_message(msg, channel='weixin')
                else:
                    msg = f"【⚠️信号拦截】[{stock} {stock_name}] 触发卖出9转 -> 账户可用底仓不足（无法高位卖出做空T）。"
                    print(msg)
                    send_message(msg, channel='weixin')
            else:
                msg = f"【🔔信号提示】[{stock} {stock_name}] 触发卖出9转信号，但当前已有做空T净敞口({net_pos}股)，不进行重复开仓。"
                print(msg)
                send_message(msg, channel='weixin')


def close_intraday_position(context):
    print(f"\n=================== {context.current_dt} 触发14:55未出信号强平风控 ===================")
    current_data = get_current_data() 
    
    for stock, net_pos in g.intraday_net_pos.items():
        if net_pos != 0:
            stock_name = get_name(stock)
            close_price = current_data[stock].last_price
            
            if net_pos > 0:
                order(stock, -net_pos)
                profit = (close_price - g.t_open_price[stock]) * net_pos
                msg = f"【⚠️尾盘强平】[{stock} {stock_name}] 做多T未触发高抛，强制卖出 {net_pos} 股。平仓盈亏: {profit:.2f} 元。"
                log.warn(msg)
                send_message(msg, channel='weixin')
            elif net_pos < 0:
                order(stock, -net_pos) 
                abs_pos = abs(net_pos)
                profit = (g.t_open_price[stock] - close_price) * abs_pos
                msg = f"【⚠️尾盘强平】[{stock} {stock_name}] 做空T未触发低吸，强制买回 {abs_pos} 股。平仓盈亏: {profit:.2f} 元。"
                log.warn(msg)
                send_message(msg, channel='weixin')
                
            g.intraday_net_pos[stock] = 0
            g.t_open_price[stock] = 0.0 
            
    print("========================================================================================\n")