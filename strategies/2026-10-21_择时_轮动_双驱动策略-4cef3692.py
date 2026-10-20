# Clone from JoinQuant
# postId: 4cef3692cf543140be2d972404ae8ac7
# backtestId: 3b54c46047188678020014382f11aeab
# title: 择时 + 轮动 双驱动策略

# 克隆自聚宽文章：https://www.joinquant.com/post/34489
# 标题：8年13倍的ETF动量轮动策略，有滑点，无未来函数，回撤小！
# 作者：萌新王富贵
# 修改：股票池扩充至30只，覆盖宽基/跨境/行业/商品

'''
优化说明:
    1.使用修正标准分
        rsrs_score的算法有：
            仅斜率slope，效果一般；
            仅标准分zscore，效果不错；
            修正标准分 = zscore * r2，效果最佳;
            右偏标准分 = 修正标准分 * slope，效果不错。
    2.将原策略的每次持有两只etf改成只买最优的一个，收益显著提高
    3.将每周调仓换成每日调仓，收益显著提高
    4.因为交易etf，所以手续费设为万分之三，印花税设为零，未设置滑点
    5.修改股票池中候选etf，删除银行，红利等收益较弱品种，增加纳指etf以增加不同国家市场间轮动的可能性
    6.根据研报，默认参数介已设定为最优
    7.加入防未来函数
    8.增加择时与选股模块的打印日志，方便观察每笔操作依据
    9.【新增】股票池扩充至30只，覆盖宽基/跨境/行业/商品
'''

# 导入函数库
from jqdata import *
import numpy as np
import math

# 初始化函数 
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    # set_option("avoid_future_data", True)
    # 将滑点设置为0.001
    set_slippage(FixedSlippage(0.001))
    # 设置交易成本万分之三（ETF免印花税）
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),
                   type='fund')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    
    # ==================== 股票池（扩充至30只） ====================
    g.stock_pool = [
        # === 宽基ETF（8只）===
        '510300.XSHG',  # 沪深300ETF
        '510500.XSHG',  # 中证500ETF
        '510050.XSHG',  # 上证50ETF
        '510180.XSHG',  # 上证180ETF
        '159915.XSHE',  # 创业板ETF
        '159949.XSHE',  # 创业板50ETF
        '588000.XSHG',  # 科创50ETF
        '512100.XSHG',  # 中证1000ETF
        
        # === 跨境ETF（8只）===
        '513100.XSHG',  # 纳指ETF
        '513500.XSHG',  # 标普500ETF
        '513050.XSHG',  # 中概互联ETF
        '513330.XSHG',  # 恒生互联ETF
        '513180.XSHG',  # 恒生科技ETF
        '159941.XSHE',  # 纳指科技ETF
        '159509.XSHE',  # 标普科技ETF
        '513130.XSHG',  # 恒生科技ETF（备选）
        
        # === 行业ETF（12只）===
        '512880.XSHG',  # 证券ETF
        '512690.XSHG',  # 酒ETF
        '512010.XSHG',  # 医药ETF
        '515790.XSHG',  # 光伏ETF
        '512480.XSHG',  # 半导体ETF
        '516160.XSHG',  # 新能源ETF
        '512660.XSHG',  # 军工ETF
        '512400.XSHG',  # 有色金属ETF
        '515050.XSHG',  # 5G通信ETF
        '159766.XSHE',  # 旅游ETF
        '159928.XSHE',  # 消费ETF
        '512200.XSHG',  # 房地产ETF
        
        # === 商品ETF（2只）===
        '518880.XSHG',  # 黄金ETF
        '159981.XSHE',  # 豆粕ETF
    ]
    
    # ==================== 策略参数 ====================
    # 动量轮动参数
    g.stock_num = 3  # 买入评分最高的前stock_num只股票（原1只，扩充后建议3-5只）
    g.momentum_day = 29  # 最新动量参考最近momentum_day的
    
    # RSRS择时参数
    g.ref_stock = '000300.XSHG'  # 用ref_stock做择时计算的基础数据
    g.N = 18  # 计算最新斜率slope，拟合度r2参考最近N天
    g.M = 600  # 计算最新标准分zscore，rsrs_score参考最近M天
    g.score_threshold = 0.7  # rsrs标准分指标阈值
    
    # MA择时参数
    g.mean_day = 20  # 计算结束ma收盘价，参考最近mean_day
    g.mean_diff_day = 3  # 计算初始ma收盘价，参考(mean_day + mean_diff_day)天前，窗口为mean_diff_day的一段时间
    
    # 斜率序列初始化
    g.slope_series = initial_slope_series()[:-1]  # 除去回测第一天的slope，避免运行时重复加入
    
    # 设置交易时间，每天运行
    run_daily(my_trade, time='11:30', reference_security='000300.XSHG')
    run_daily(check_lose, time='open', reference_security='000300.XSHG')
    run_daily(print_trade_info, time='15:30', reference_security='000300.XSHG')
    
    # 打印策略初始化信息
    log.info("=" * 60)
    log.info("策略初始化完成")
    log.info("股票池数量：%d只" % len(g.stock_pool))
    log.info("持仓数量：%d只" % g.stock_num)
    log.info("动量周期：%d天" % g.momentum_day)
    log.info("RSRS参数：N=%d, M=%d, 阈值=%.1f" % (g.N, g.M, g.score_threshold))
    log.info("=" * 60)


# ==================== 1-1 选股模块-动量因子轮动 ====================
# 基于股票年化收益和判定系数打分,并按照分数从大到小排名
def get_rank(stock_pool):
    score_list = []
    for stock in stock_pool:
        try:
            data = attribute_history(stock, g.momentum_day, '1d', ['close'])
            if data is None or len(data) < g.momentum_day:
                score_list.append(-9999)  # 数据不足，给最低分
                continue
                
            y = data['log'] = np.log(data.close)
            x = data['num'] = np.arange(data.log.size)
            slope, intercept = np.polyfit(x, y, 1)
            annualized_returns = math.pow(math.exp(slope), 250) - 1
            
            # 计算R²
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            score = annualized_returns * r_squared
            score_list.append(score)
        except Exception as e:
            log.warning("计算股票 %s 动量得分失败: %s" % (stock, str(e)))
            score_list.append(-9999)
    
    # 构建得分字典并排序
    stock_dict = dict(zip(stock_pool, score_list))
    sort_list = sorted(stock_dict.items(), key=lambda item: item[1], reverse=True)
    
    # 打印前10名得分
    log.info("【动量得分排名】")
    for i in range(min(10, len(sort_list))):
        log.info("  %d. %s : %.4f" % (i+1, sort_list[i][0], sort_list[i][1]))
    
    # 返回排名前g.stock_num的股票
    rank_stock = [sort_list[i][0] for i in range(min(g.stock_num, len(sort_list)))]
    log.info("【选股结果】目标买入: %s" % rank_stock)
    return rank_stock


# ==================== 2-1 择时模块-计算线性回归统计值 ====================
# 对输入的自变量每日最低价x(series)和因变量每日最高价y(series)建立OLS回归模型
def get_ols(x, y):
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    return (intercept, slope, r2)


# ==================== 2-2 择时模块-设定初始斜率序列 ====================
# 通过前M日最高最低价的线性回归计算初始的斜率,返回斜率的列表
def initial_slope_series():
    data = attribute_history(g.ref_stock, g.N + g.M, '1d', ['high', 'low'])
    slopes = []
    for i in range(g.M):
        try:
            slope = get_ols(data.low[i:i+g.N], data.high[i:i+g.N])[1]
            slopes.append(slope)
        except:
            slopes.append(0)
    return slopes


# ==================== 2-3 择时模块-计算标准分 ====================
# 通过斜率列表计算并返回截至回测结束日的最新标准分
def get_zscore(slope_series):
    mean = np.mean(slope_series)
    std = np.std(slope_series)
    if std == 0:
        return 0
    return (slope_series[-1] - mean) / std


# ==================== 2-4 择时模块-计算综合信号 ====================
# 1.获得rsrs与MA信号,rsrs信号算法参考优化说明
# 2.信号同时为True时返回买入信号，同为False时返回卖出信号，其余情况返回持仓不变信号
def get_timing_signal():
    # 计算MA信号
    try:
        close_data = attribute_history(g.ref_stock, g.mean_day + g.mean_diff_day, '1d', ['close'])
        today_MA = close_data.close[g.mean_diff_day:].mean() 
        before_MA = close_data.close[:-g.mean_diff_day].mean()
        ma_signal = today_MA > before_MA
        log.info("【MA信号】今日MA: %.4f, 前期MA: %.4f, 方向: %s" % 
                (today_MA, before_MA, "向上" if ma_signal else "向下"))
    except Exception as e:
        log.warning("计算MA信号失败: %s" % str(e))
        ma_signal = False
    
    # 计算RSRS信号
    try:
        high_low_data = attribute_history(g.ref_stock, g.N, '1d', ['high', 'low'])
        intercept, slope, r2 = get_ols(high_low_data.low, high_low_data.high)
        g.slope_series.append(slope)
        
        # 只保留最近M个斜率
        if len(g.slope_series) > g.M:
            g.slope_series = g.slope_series[-g.M:]
        
        rsrs_score = get_zscore(g.slope_series) * r2
        rsrs_signal = rsrs_score > g.score_threshold
        rsrs_sell_signal = rsrs_score < -g.score_threshold
        log.info("【RSRS信号】斜率: %.6f, R²: %.4f, 标准分: %.4f, 修正得分: %.4f" % 
                (slope, r2, get_zscore(g.slope_series), rsrs_score))
    except Exception as e:
        log.warning("计算RSRS信号失败: %s" % str(e))
        rsrs_signal = False
        rsrs_sell_signal = False
    
    # 综合判断所有信号
    if rsrs_signal and ma_signal:
        log.info("【综合信号】BUY")
        return "BUY"
    elif rsrs_sell_signal and not ma_signal:
        log.info("【综合信号】SELL")
        return "SELL"
    else:
        log.info("【综合信号】KEEP")
        return "KEEP"


# ==================== 3-1 过滤模块-过滤停牌股票 ====================
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    filtered = []
    for stock in stock_list:
        try:
            if not current_data[stock].paused:
                filtered.append(stock)
        except:
            filtered.append(stock)
    return filtered


# ==================== 3-2 过滤模块-过滤ST及其他具有退市标签的股票 ====================
def filter_st_stock(stock_list):
    current_data = get_current_data()
    filtered = []
    for stock in stock_list:
        try:
            if not current_data[stock].is_st:
                name = current_data[stock].name
                if 'ST' not in name and '*' not in name and '退' not in name:
                    filtered.append(stock)
        except:
            filtered.append(stock)
    return filtered


# ==================== 3-3 过滤模块-过滤涨停的股票 ====================
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    filtered = []
    for stock in stock_list:
        try:
            # 已持仓的股票即使涨停也不过滤
            if stock in context.portfolio.positions.keys():
                filtered.append(stock)
            elif last_prices[stock][-1] < current_data[stock].high_limit:
                filtered.append(stock)
        except:
            filtered.append(stock)
    return filtered


# ==================== 3-4 过滤模块-过滤跌停的股票 ====================
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    filtered = []
    for stock in stock_list:
        try:
            # 已持仓的股票跌停也不过滤（想卖也卖不掉）
            if stock in context.portfolio.positions.keys():
                filtered.append(stock)
            elif last_prices[stock][-1] > current_data[stock].low_limit:
                filtered.append(stock)
        except:
            filtered.append(stock)
    return filtered


# ==================== 4-1 交易模块-自定义下单 ====================
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)


# ==================== 4-2 交易模块-开仓 ====================
def open_position(security, value):
    order = order_target_value_(security, value)
    if order is not None and order.filled > 0:
        log.info("【开仓成功】%s, 目标市值: %.2f, 成交数量: %d" % (security, value, order.filled))
        return True
    return False


# ==================== 4-3 交易模块-平仓 ====================
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order is not None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            log.info("【平仓成功】%s, 数量: %d" % (security, order.filled))
            return True
    return False


# ==================== 4-4 交易模块-调仓 ====================
def adjust_position(context, buy_stocks):
    # 卖出不在买入列表中的持仓
    for stock in list(context.portfolio.positions.keys()):
        if stock not in buy_stocks:
            log.info("[%s] 已不在买入列表中，准备卖出" % stock)
            position = context.portfolio.positions[stock]
            close_position(position)
        else:
            log.info("[%s] 已经持有，无需重复买入" % stock)
    
    # 计算需要买入的数量
    current_position_count = len(context.portfolio.positions)
    need_buy_count = g.stock_num - current_position_count
    
    if need_buy_count > 0 and context.portfolio.cash > 0:
        # 等额分配资金
        value_per_stock = context.portfolio.cash / need_buy_count
        
        for stock in buy_stocks:
            # 只买入尚未持仓的股票
            if context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value_per_stock):
                    current_position_count += 1
                    if current_position_count >= g.stock_num:
                        break


# ==================== 4-5 交易模块-择时交易 ====================
def my_trade(context):
    log.info("=" * 60)
    log.info("【开始交易】时间: %s" % context.current_dt.strftime('%Y-%m-%d %H:%M'))
    
    # 获取选股列表并过滤
    buy_stocks = get_rank(g.stock_pool)
    buy_stocks = filter_st_stock(buy_stocks)
    buy_stocks = filter_limitup_stock(context, buy_stocks)
    buy_stocks = filter_limitdown_stock(context, buy_stocks)
    buy_stocks = filter_paused_stock(buy_stocks)
    
    log.info("【过滤后买入列表】%s" % buy_stocks)
    
    # 获取综合择时信号
    timing_signal = get_timing_signal()
    log.info("【最终择时信号】%s" % timing_signal)
    
    # 执行交易
    if timing_signal == 'SELL':
        log.info("【执行操作】卖出所有持仓")
        for stock in list(context.portfolio.positions.keys()):
            position = context.portfolio.positions[stock]
            close_position(position)
    elif timing_signal == 'BUY' or timing_signal == 'KEEP':
        log.info("【执行操作】调仓")
        adjust_position(context, buy_stocks)
    else:
        log.info("【执行操作】无操作")
    
    log.info("【交易完成】持仓数量: %d, 可用现金: %.2f" % 
             (len(context.portfolio.positions), context.portfolio.cash))
    log.info("=" * 60)


# ==================== 4-6 交易模块-止损 ====================
def check_lose(context):
    for position in list(context.portfolio.positions.values()):
        try:
            security = position.security
            cost = position.avg_cost
            price = position.price
            ret = 100 * (price / cost - 1)
            value = position.value
            amount = position.total_amount
            
            # 止损线设为-20%（原策略-80%太宽松）
            if ret <= -20:
                order_target_value(security, 0)
                log.info("【止损触发】标的: %s, 成本: %.2f, 现价: %.2f, 亏损: %.2f%%" % 
                        (security, cost, price, ret))
        except Exception as e:
            log.warning("止损检查异常: %s" % str(e))


# ==================== 5-1 复盘模块-打印持仓信息 ====================
def print_trade_info(context):
    log.info("=" * 60)
    log.info("【收盘持仓】日期: %s" % context.current_dt.strftime('%Y-%m-%d'))
    
    # 打印当天成交记录
    trades = get_trades()
    if trades:
        log.info("【今日成交】")
        for _trade in trades.values():
            log.info("  %s" % str(_trade))
    
    # 打印持仓信息
    total_value = 0
    for position in list(context.portfolio.positions.values()):
        security = position.security
        cost = position.avg_cost
        price = position.price
        ret = 100 * (price / cost - 1) if cost > 0 else 0
        value = position.value
        amount = position.total_amount
        total_value += value
        
        log.info("【持仓】%s" % security)
        log.info("  成本价: %.3f, 现价: %.3f" % (cost, price))
        log.info("  收益率: %.2f%%, 持仓股数: %d, 市值: %.2f" % (ret, amount, value))
    
    log.info("【账户汇总】总市值: %.2f, 可用现金: %.2f, 总资产: %.2f" % 
             (total_value, context.portfolio.cash, context.portfolio.portfolio_value))
    log.info("=" * 60)