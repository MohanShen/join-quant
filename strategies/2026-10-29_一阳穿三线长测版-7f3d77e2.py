# Clone from JoinQuant
# postId: 7f3d77e29be106cd254e16d1ef9acca1
# backtestId: 18b6d02730b0a02f0836935d2b2069aa
# title: 一阳穿三线长测版

from jqdata import *
from jqlib.technical_analysis import *

def initialize(context):
    # 设置交易参数
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    set_option('avoid_future_data', True)
    # 新增：初始化字典存储买入日开盘价
    context.buy_day_open = {}  # key: 股票代码, value: 买入日开盘价
    # 可配置参数
    g.params = {
        'min_market_cap': 50,  # 最小流通市值(亿)
        'max_market_cap': 520,  # 最大流通市值(亿)
        'min_change': 2,       # 最小涨幅(%)
        'max_change': 8,       # 最大涨幅(%)
        'min_turnover': 3,     # 最小换手率(%)
        'max_turnover': 10,    # 最大换手率(%)
        'min_volume_ratio': 2.5, # 最小量比
        'profit_threshold': 15,  # 盈利卖出阈值(%)
        'loss_threshold': 8,    # 新增亏损卖出阈值(%)
        'max_high_price_diff': 0.02,  # 最高价与当前价最大允许差值比例
        'enable_volume_trend_filter': False,  # 成交量趋势筛选开关
        'enable_high_price_filter': False,  # 最高价筛选开关
        'enable_ma_filter': True,        # 均线多头筛选开关
        'enable_low_start': False,        # 低位启动筛选开关
        'enable_market_cap_filter': False,  # 市值筛选开关
        'enable_three_line_breakout': True,  # 一阳穿三线筛选开关
    }
    
    # 定时任务设置
    run_daily(market_open, time='14:40')  # 下午2:40准备股票池
    run_daily(check_sell, time='every_bar')  # 每个交易时段检查卖出
    run_daily(buy_stocks, time='14:50')  # 下午2:50买入

def market_open(context):
    # 清空前一天的股票池
    context.stock_pool = []
    
    # 1. 获取全部股票列表并筛选(增加开关判断)
    if g.params['enable_market_cap_filter']:
        df = get_fundamentals(
            query(
                valuation.code,
                valuation.circulating_market_cap
            ).filter(
                valuation.circulating_market_cap >= g.params['min_market_cap'],
                valuation.circulating_market_cap <= g.params['max_market_cap']
            ), date=context.previous_date
        )
    else:
        df = get_fundamentals(
            query(
                valuation.code
            ), date=context.previous_date
        )
    if df is not None and not df.empty:
        context.stock_pool = df['code'].tolist()
    else:
        context.stock_pool = []
        log.warning("未找到符合流通市值要求的股票")

    log.info(f"初始股票池数量: {len(context.stock_pool)}")
    
    # 使用remove方式剔除不符合条件的股票
    all_stocks = get_all_securities(types=['stock'], date=context.current_dt)
    # 修改为兼容旧Python版本的写法
    context.stock_pool = [
        stock for stock in context.stock_pool 
        if (stock in all_stocks.index and 
            '*' not in all_stocks.loc[stock, 'display_name'] and 
            'ST' not in all_stocks.loc[stock, 'display_name'] and 
            '退' not in all_stocks.loc[stock, 'display_name'] and 
            not stock.startswith('688'))
    ]
    log.info(f"ST和科创板筛选后剩余股票数量: {len(context.stock_pool)}")
    # 3. 筛选量比大于阈值的股票(去掉开关判断)
    for stock in context.stock_pool[:]:            
        try:
            # 使用LB函数计算量比
            lb_dict = LB([stock], check_date=context.current_dt, N=6)
            volume_ratio = lb_dict[stock]
            
            if volume_ratio < g.params['min_volume_ratio']:
                context.stock_pool.remove(stock)
                
        except Exception as e:
            log.error(f"计算股票 {stock} 量比失败: {str(e)}")
            context.stock_pool.remove(stock)
    
    log.info(f"量比筛选后剩余股票数量: {len(context.stock_pool)}")
    # 9 新增一阳穿三线筛选条件
    if g.params['enable_three_line_breakout']:
        current_data = get_current_data()  # 提前获取current_data避免重复调用
        for stock in context.stock_pool[:]:
            try:
                # 检查是否停牌（原涨幅筛选中的停牌判断移至此）
                if current_data[stock].paused:
                    context.stock_pool.remove(stock)
                    continue

                # 获取当前K线数据
                current_price = current_data[stock].last_price
                open_price = current_data[stock].day_open  # 保留用于阳线判断
                
                # 确保是阳线（保留原有逻辑）
                if current_price <= open_price:
                    context.stock_pool.remove(stock)
                    continue
                
                # 获取三条均线值（保持原有逻辑）
                ma5_dict = MA([stock], check_date=context.current_dt, timeperiod=5)
                ma10_dict = MA([stock], check_date=context.current_dt, timeperiod=10)
                ma20_dict = MA([stock], check_date=context.current_dt, timeperiod=20)
                
                ma5 = ma5_dict[stock]
                ma10 = ma10_dict[stock]
                ma20 = ma20_dict[stock]
                
                # 判断一阳穿三线条件
                if not (open_price <= ma5 and open_price <= ma10 and open_price <= ma20 and 
                       current_price > ma5 and current_price > ma10 and current_price > ma20):
                    context.stock_pool.remove(stock)
                    
            except Exception as e:
                log.error(f"检查股票 {stock} 一阳穿三线条件失败: {str(e)}")
                context.stock_pool.remove(stock)
    log.info(f"一阳穿三线筛选后剩余股票数量: {len(context.stock_pool)}")
    
    # 2. 筛选当日涨幅3%-5%且未停牌的股票(去掉开关判断)
    current_data = get_current_data()
    for stock in context.stock_pool[:]:
        # 移除原停牌判断（已移至一阳穿三线筛选）
        prev_close = attribute_history(stock, count=1, unit='1d', fields=['close'])['close'][0]
        change_percent = (current_data[stock].last_price / prev_close - 1) * 100
        if not (g.params['min_change'] <= change_percent <= g.params['max_change']):
            #stock_name = get_security_info(stock).display_name
            #log.info(f"涨幅筛选剔除 - 股票: {stock_name}({stock}), 涨幅: {change_percent:.2f}% (要求: {g.params['min_change']}%-{g.params['max_change']}%)")
            context.stock_pool.remove(stock)
    log.info(f"涨幅筛选后剩余股票数量: {len(context.stock_pool)}")

    # 4. 筛选换手率5%-10%的股票(去掉开关判断)
    for stock in context.stock_pool[:]:
        try:
            total_shares = get_fundamentals(query(
                valuation.circulating_cap
            ).filter(
                valuation.code == stock
            ), date=context.previous_date)['circulating_cap'][0] 
            
            vol_result = VOL([stock], check_date=context.current_dt, M1=1, unit='1d', include_now=True)
            current_volume = vol_result[0][stock] if isinstance(vol_result, tuple) else vol_result[stock]
            
            turnover = current_volume / total_shares  # 转换为百分比
            if not (g.params['min_turnover'] <= turnover <= g.params['max_turnover']):
                context.stock_pool.remove(stock)
                
        except Exception as e:
            log.error(f"计算股票 {stock} 换手率失败: {str(e)}")
            context.stock_pool.remove(stock)
    
    log.info(f"换手率筛选后剩余股票数量: {len(context.stock_pool)}")
    
    '''
    # 5. 筛选3日内成交量递增但增幅不大的股票(包含当天tick数据)
    if g.params['enable_volume_trend_filter']:
        for stock in context.stock_pool[:]:
            try:
                # 获取最近2日历史成交量数据
                hist_data = attribute_history(stock, count=2, unit='1d', fields=['volume'])
                if hist_data is None or hist_data.empty:
                    log.error(f"股票 {stock} 历史数据获取失败")
                    context.stock_pool.remove(stock)
                    continue
                
                # 获取当天tick成交量
                current_volume = tick_data[stock]['volume']
                
                # 检查成交量是否连续3天递增(前2天+当天)
                volumes = hist_data['volume'].values
                if not (volumes[0] < volumes[1] < current_volume):
                    context.stock_pool.remove(stock)
                    continue

            except Exception as e:
                log.error(f"检查股票 {stock} 成交量趋势失败: {str(e)}")
                context.stock_pool.remove(stock)
    
    log.info(f"成交量趋势筛选后剩余股票数量: {len(context.stock_pool)}")
    
    # 6. 剔除当天最高点远大于当前价格的股票
    if g.params['enable_high_price_filter']:
        for stock in context.stock_pool[:]:
            try:
                current_tick = get_current_tick([stock])[stock]
                current_high = current_tick['high']
                current_price = current_tick['current']
                
                # 使用配置参数判断最高价是否远大于当前价
                if (current_high - current_price) / current_price > g.params['max_high_price_diff']:
                    context.stock_pool.remove(stock)
                    
            except Exception as e:
                log.error(f"检查股票 {stock} 最高价失败: {str(e)}")
                context.stock_pool.remove(stock)
    
    log.info(f"最高价筛选后剩余股票数量: {len(context.stock_pool)}")
    '''
    # 7. 新增均线多头排列筛选条件
    if g.params['enable_ma_filter']:
        # 获取最近11个交易日（当前日+前10日）
        trade_days = get_trade_days(end_date=context.current_dt, count=11)
        if len(trade_days) < 11:
            log.error("获取最近11个交易日失败，跳过均线多头筛选")
            return
        ma60_prev_date = trade_days[5]  # 5天前的交易日（trade_days[10]是当前日，trade_days[5]是5天前）
        ma60_prev_10_date = trade_days[0]  # 10天前的交易日（trade_days[0]是10天前）
        
        for stock in context.stock_pool[:]:
            try:
                # 获取5日、10日、20日、60日均线值（保持原有周期）
                ma5_dict = MA([stock], check_date=context.current_dt, timeperiod=5)
                ma10_dict = MA([stock], check_date=context.current_dt, timeperiod=10)
                ma20_dict = MA([stock], check_date=context.current_dt, timeperiod=20)
                ma60_current_dict = MA([stock], check_date=context.current_dt, timeperiod=60)  # 当日60日均线
                ma60_prev_dict = MA([stock], check_date=ma60_prev_date, timeperiod=60)  # 5天前的60日均线
                ma60_prev_10_dict = MA([stock], check_date=ma60_prev_10_date, timeperiod=60)  # 10天前的60日均线
                
                ma5 = ma5_dict[stock]
                ma10 = ma10_dict[stock]
                ma20 = ma20_dict[stock]
                ma60_current = ma60_current_dict[stock]
                ma60_prev = ma60_prev_dict[stock]
                ma60_prev_10 = ma60_prev_10_dict[stock]
     
                # 剔除不符合条件的股票：需同时满足 
                # 1. MA5>MA10>MA20 
                # 2. MA5/MA10/MA20均>MA60 
                # 3. 60日线强势（当日MA60 > 5天前MA60 > 10天前MA60）
                if not (ma5 > ma60_current and ma10 > ma60_current and ma20 > ma60_current and 
                        ma60_current > ma60_prev and  # 当日>5天前
                        ma60_prev > ma60_prev_10):  # 5天前>10天前
                    stock_name = get_security_info(stock).display_name
                    log.info(f"均线多头筛选剔除 - 股票: {stock_name}({stock}), 均线排列: MA5={ma5:.2f}, MA10={ma10:.2f}, MA20={ma20:.2f}, MA60(当日)={ma60_current:.2f}, MA60(5天前)={ma60_prev:.2f}, MA60(10天前)={ma60_prev_10:.2f}（要求MA5>MA10>MA20、三线均在MA60上方且MA60趋势：当日>5天前>10天前）")
                    context.stock_pool.remove(stock)
                    
            except Exception as e:
                log.error(f"检查股票 {stock} 均线排列失败: {str(e)}")
                context.stock_pool.remove(stock)
    log.info(f"均线多头筛选后剩余股票数量: {len(context.stock_pool)}")

    # 8. 新增MACD筛选条件（dif>dea且dif<0且macd>0）
    if g.params['enable_low_start']:
        for stock in context.stock_pool[:]:
            try:
                # 获取当天MACD数据（移除昨日数据获取，仅保留当日）
                today_date = context.current_dt
                dif_today, dea_today, macd_today = MACD([stock], check_date=today_date)
                today_macd = {
                    'macd': macd_today[stock],
                    'dif': dif_today[stock],
                    'dea': dea_today[stock]
                }

                # 检查条件：
                # 1. dif>dea（DIF上穿DEA）
                # 2. dif<0（DIF在0轴下方）
                # 3. macd>0（MACD柱状线为红柱）
                if not (today_macd['dif'] > today_macd['dea'] and 
                        today_macd['dif'] > 0 and 
                        today_macd['macd'] > 0):
                    stock_name = get_security_info(stock).display_name
                    log.info(f"MACD筛选剔除 - 股票: {stock_name}({stock}), DIF={today_macd['dif']:.2f}, DEA={today_macd['dea']:.2f}, MACD={today_macd['macd']:.2f}（要求DIF>DEA、DIF<0且MACD>0）")
                    context.stock_pool.remove(stock)
                    
            except Exception as e:
                log.error(f"MACD筛选 - 检查股票 {stock} 失败: {str(e)}")
                context.stock_pool.remove(stock)
    
    log.info(f"MACD筛选后剩余股票数量: {len(context.stock_pool)}")

    # 最终输出符合条件的股票代码和名称
    log.info("最终符合条件的股票列表:")
    for stock in context.stock_pool:
        stock_name = get_security_info(stock).display_name
        log.info(f"股票代码: {stock}, 股票名称: {stock_name}")

    log.info(f"最终符合条件的股票池数量: {len(context.stock_pool)}")

def buy_stocks(context):
    # 新增：检查当前是否已有持仓
    if len(context.portfolio.positions) > 0:
        log.info("当前已有持仓，不执行新买入操作")
        return

    # 检查候选股票池是否为空
    if len(context.stock_pool) == 0:
        log.info("候选股票池为空，不进行买入")
        return

    # 新增：计算候选股票池的量比并排序
    try:
        # 复用market_open中的量比计算方法
        lb_dict = LB(context.stock_pool, check_date=context.current_dt, N=6)
        # 按量比降序排序，取量比最大的股票
        sorted_stocks = sorted(context.stock_pool, key=lambda s: lb_dict[s], reverse=True)
        target_stock = sorted_stocks[0]
    except Exception as e:
        log.error(f"筛选量比最大股票失败: {str(e)}")
        return

    # 执行全仓买入（仅买入1只）
    try:
        current_data = get_current_data()
        current_price = current_data[target_stock].last_price
        buy_day_open = current_data[target_stock].day_open
        # 使用账户可用资金全仓买入
        available_cash = context.portfolio.available_cash
        order_target_value(target_stock, available_cash)
        context.buy_day_open[target_stock] = buy_day_open
        log.info(f"全仓买入量比最大股票: {target_stock}, 买入价: {current_price:.2f}, 买入金额: {available_cash:.2f}元")
    except Exception as e:
        log.error(f"买入股票 {target_stock} 失败: {str(e)}")

def check_sell(context):
    # 检查持仓股票是否需要卖出
    for stock in context.portfolio.positions:
        position = context.portfolio.positions[stock]
        current_data = get_current_data()  # 提前获取current_data避免重复调用
        current_price = current_data[stock].last_price
        cost_price = position.avg_cost
        profit_percent = (current_price - cost_price) / cost_price * 100
        buy_day_open = context.buy_day_open.get(stock, None)
        
        sell_reason = ""
        if current_price > cost_price and profit_percent >= g.params['profit_threshold']:
            # 获取当日涨停价并判断是否涨停
            high_limit = current_data[stock].high_limit
            if current_price < high_limit:  # 未涨停才触发卖出
                sell_reason = "盈利达标"
        elif buy_day_open is not None and current_price < buy_day_open:
            sell_reason = "跌破买入日开盘价"
        
        if sell_reason:
            order_target(stock, 0)
            log.info(f"卖出 {stock}, 收益率: {profit_percent:.2f}%, 当前价: {current_price:.2f}, 原因: {sell_reason}")
            if stock in context.buy_day_open:
                del context.buy_day_open[stock]

