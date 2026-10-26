# Clone from JoinQuant
# postId: b0c225d40b7e63d8cfa5b49d27d57891
# backtestId: 2aa2ca1a3c49c185b847b588e865d87a
# title: 叠加涨停基因小市值 · 1/4 月五福 178.19%

# 克隆自聚宽文章：https://www.joinquant.com/post/66114
# 标题：年化104%-叠加涨停基因因子的小市值策略
# 作者：流年8888

"""
作者：流年8888
策略：叠加涨停基因因子的小市值策略
策略核心逻辑总结：
==================

1. 策略概述
-----------
本策略是一个基于涨停基因的小市值股池轮动策略，核心思想是：
- 选择具有涨停基因的小市值股票
- 通过历史涨停次数筛选强势股
- 通过启动点分析找到接近启动点的股票
- 按行业分散持仓，降低风险
- 多重止损机制保护资金安全
- 涨停打开和换手率异常时及时卖出

2. 选股逻辑（多维度筛选）
-----------------------
第一步：基础过滤
- 过滤次新股（上市不足375天）
- 过滤科创板、北交所股票（代码以68、4、8开头）
- 过滤ST股、*ST股、退市股
- 过滤停牌股票
- 过滤近期止损黑名单股票（20天内）
- 过滤当前涨停和跌停的股票

第二步：市值筛选
- 按市值升序排序
- 选择前1000只小市值股票

第三步：涨停基因筛选
- 统计过去2年（500个交易日）的涨停次数
- 按涨停次数降序排序
- 选择前10%的股票（约50只）

第四步：启动点分析
- 找到每只股票最近一次涨停的日期
- 向前查找涨停前第一个阴线（收盘价<开盘价）
- 记录该阴线的最低点作为启动点
- 计算当前价格与启动点的偏移量
- 按偏移量升序排序，选择最接近启动点的股票

第五步：行业分散
- 获取每只股票的申万二级行业
- 按顺序选择不同行业的股票
- 最多选择10个不同行业的股票
- 最终选择前12只股票（目标持仓数5只的2倍）

3. 交易逻辑
----------
调仓频率：每周二调仓（10:15卖出，10:30买入）

卖出条件：
- 不在目标列表中
- 昨日未涨停
- 当前未涨停
- 昨日涨停但今日涨停打开（卖出）
- 出现天量（当日成交量 > 0.9 * 过去120天最大成交量）
- 换手率异常（缩量<0.3% 或 放量>10%且倍率>2）
- 止盈：盈利>=100%
- 止损：价格跌破成本价的91%
- 大盘暴跌：大盘平均跌幅>=7%

买入逻辑：
- 按目标持仓数6只等分资金
- 依次买入未持有的股票
- 避免重复买入本周一已买入的股票

4. 风险控制机制
----------------
止损策略（三选一）：
1. 个股止损线：价格跌破成本价的91%时止损
2. 市场趋势止损：大盘平均跌幅>=7%时全部清仓
3. 联合策略：同时使用策略1和策略2

空仓期控制：
- 空仓月份：g.months（默认 [1, 4]，即 1 月、4 月整月）
- 空仓期间：清小市值股票，切换为五福 ETF 轮动（内嵌 joinquant/五福ETF.py）
- 恢复交易：清五福 ETF，重新开始小市值交易

止损黑名单：
- 止损后拉黑20天
- 20天内不再买入该股票

5. 每日任务时间表
----------------
- 09:05 - 准备股票池（更新持仓和昨日涨停列表）
- 10:00 - 执行止盈止损
- 10:15 - 每周二调仓卖出
- 10:30 - 每周二调仓买入
- 14:20 - 检查涨停股和换手率
- 14:50 - 检查是否需要空仓
- 14:55 - 再次检查涨停股和换手率

6. 策略参数说明
----------------
- max_holdings: 6 - 目标持仓股票数量
- max_price: 20 - 股票单价上限
- history_window_days: 500 - 历史涨停参考窗口期（2年）
- initial_pool_size: 1000 - 初始股池数量
- stoploss_mode: 3 - 止损策略（1/2/3）
- stoploss_threshold: 0.91 - 个股止损阈值（-9%）
- market_crash_threshold: 0.93 - 大盘暴跌阈值（-7%）
- volume_check_days: 120 - 放量检查天数
- volume_ratio_threshold: 0.9 - 放量倍率阈值
- enable_no_trading_period: True - 是否启用空仓期
- enable_stoploss: True - 是否启用止损
- enable_loss_blacklist: True - 是否启用止损黑名单
- enable_volume_control: False - 是否启用放量控制

"""

from jqdata import *
from jqfactor import *
import math
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta, time


def initialize(context):
    """
    策略初始化函数，设置交易参数、全局变量和定时任务
    
    参数:
        context: 策略上下文对象，包含账户信息、当前时间等
    
    功能:
        - 设置交易基准、滑点、手续费等交易参数
        - 初始化全局变量，包括持仓列表、止损参数、选股参数等
        - 配置定时任务：每日准备股票池、每周调仓、每日止损等
    """
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设定基准
    set_benchmark('399101.XSHE')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 将滑点设置为0
    set_slippage(PriceRelatedSlippage(0.002), type="stock")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=5,
        ),
        type="stock",
    )
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')

    # 初始化全局变量
    g.months = [1, 4]  # 空仓月份（1月、4月整月不交易小市值）
    # 布尔类型变量
    g.is_no_trading_period = False  # 是否为空仓期间（空仓期间为True）
    g.enable_no_trading_period = True  # 是否启用空仓期（由 g.months 决定）
    g.enable_stoploss = True  # 是否进行止损
    g.enable_loss_blacklist = True  # 止损后短期不再买入
    g.enable_volume_control = False  # 是否启用放量控制（True表示日频判断是否放量）
    g.wufu_mode_active = False  # 空仓月份五福 ETF 轮动开关（09:40 后置 True）
    
    # 列表类型变量
    g.current_holdings = []  # 当前持仓的全部股票
    g.yesterday_limit_up_stocks = []  # 记录持仓中昨日涨停的股票
    g.target_stocks = []  # 目标买入股票列表
    g.bought_this_week = []  # 本周一已买入的股票，避免重复买入
    g.unused_list = []  # 未使用的变量
    
    # 字典类型变量
    g.loss_blacklist = {}  # 止损后拉黑字典 {股票代码: 止损时间}
    
    # 数值类型变量
    g.max_holdings = 5  # 目标持仓股票数量
    g.max_price = 20  # 股票单价上限，过滤高价股
    g.history_window_days = 2 * 250  # 历史涨停的参考窗口期（2年）
    g.initial_pool_size = 500  # 初始股池的数量
    g.stoploss_mode = 3  # 止损策略：1=止损线止损，2=市场趋势止损，3=联合1、2策略
    g.stoploss_threshold = 0.91  # 止损线止损参数（价格跌破成本价的91%时止损）
    g.market_crash_threshold = 0.93  # 市场趋势止损参数（大盘平均跌幅超过7%时清仓）
    g.volume_check_days = 120  # 放量控制的历史数据周期（120天）
    g.volume_ratio_threshold = 0.9  # 放量控制的倍率（当日成交量 > 0.9 * 历史最大成交量时卖出）
    
    # 字符串类型变量
    g.sell_reason = ''  # 卖出理由：'limitup'=涨停打开卖出，'stoploss'=止损卖出，''=无卖出
    
    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')  # 每日9:05准备股票池
    run_weekly(weekly_sell, 1, '10:15')  # 每周五10:15调仓卖出
    run_weekly(weekly_buy, 1, '10:30')  # 每周五10:30调仓买入
    run_daily(sell_stocks, time='10:00')  # 每日10:00执行止损
    run_daily(trade_afternoon, time='14:20')  # 每日14:20检查涨停股和换手率
    run_daily(trade_afternoon, time='14:55')  # 每日14:55再次检查涨停股和换手率
    run_daily(close_account, '14:50')  # 空仓月兜底清小市值股票
    _register_wufu_empty_month_daily(context)
    # run_weekly(print_position_info, 5, time='15:10')  # 每周五15:10打印持仓信息


def handle_data(context, data=None):
    """空仓月份：五福 ETF 分钟级止损。"""
    if _should_run_wufu_minute(context):
        try:
            minute_level_stop_loss(context)
            minute_level_pct_stop_loss(context)
        except Exception as e:
            log.info('[五福ETF] 分钟止损异常: {}'.format(e))


def prepare_stock_list(context):
    """
    准备股票池，获取当前持仓和昨日涨停股票列表
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 更新当前持仓列表g.current_holdings
        - 识别昨日涨停的股票并更新g.yesterday_limit_up_stocks
        - 判断今天是否为可交易日
    """
    # 获取已持有列表
    g.current_holdings = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.current_holdings.append(stock)
    
    # 获取昨日涨停列表
    if g.current_holdings != []:
        df = get_price(g.current_holdings, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_limit_up_stocks = list(df.code)
    else:
        g.yesterday_limit_up_stocks = []
    
    # 判断今天是否为账户资金再平衡的日期
    g.is_no_trading_period = today_is_between(context)


def get_history_highlimit(context, df, p=0.10):
    """
    获取历史涨停次数最多的股票列表
    
    参数:
        context: 策略上下文对象
        df: 包含股票价格数据的DataFrame
        p: 筛选比例，默认选择前10%的股票
    
    返回:
        按历史涨停次数排序后的股票列表
    
    功能:
        - 统计每只股票在指定时间段内的涨停次数
        - 按涨停次数降序排序
        - 返回前p比例的股票
    """

    # 筛选出涨停的交易日
    df = df[df["close"] == df["high_limit"]]
    # 按股票代码分组统计涨停次数
    grouped_result = df.groupby('code').size().reset_index(name='count')
    # 按涨停次数降序排序
    grouped_result = grouped_result.sort_values(by=["count"], ascending=False)
    # 选择前p比例的股票
    result_list = grouped_result["code"].tolist()[:int(len(grouped_result)*p)]
    log.info(f"筛选前合计{len(grouped_result)}个， 筛选后合计{len(result_list)}个")

    return result_list
    
    
def get_start_point(context, df):
    """
    获取股票启动点，按当前价格与启动点的偏移量排序
    
    参数:
        context: 策略上下文对象
        df: 包含股票价格数据的DataFrame
    
    返回:
        按当前价格与启动点偏移量升序排序的股票列表
    
    功能:
        - 找到每只股票最近一次涨停的日期
        - 向前查找涨停前第一个阴线（收盘价<开盘价）的最低点作为启动点
        - 计算当前价格与启动点的偏移量
        - 按偏移量升序排序，偏移量越小表示越接近启动点
    """

    stock_start_point = {}
    stock_price_bias = {}
    current_data = get_current_data()
    
    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        
        # 找到所有close等于high_limit的行（涨停日）
        limit_hit_rows = group[group['close'] == group['high_limit']]

        if not limit_hit_rows.empty:
            # 获取最近的涨停行（时间最大的）
            latest_limit_hit = limit_hit_rows.iloc[-1]
            latest_limit_index = latest_limit_hit.name
            
            # 获取该涨停行之前的所有行（按时间倒序，便于向前查找）
            previous_rows = group[group.index <= latest_limit_index].iloc[::-1]
            
            # 寻找第一个close < open的行（阴线），记录其最低点作为启动点
            target_row = None
            for idx, row in previous_rows.iterrows():
                if row['close'] < row['open']:
                    stock_start_point[code] = row['low']
                    break
    
    # 计算股票当前价格与历史启动点的偏移量
    for code, start_point in stock_start_point.items():
        last_price = current_data[code].last_price
        bias = last_price / start_point
        stock_price_bias[code] = bias
    
    # 按偏移量升序排序，偏移量越小表示越接近启动点
    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)

    return [i[0] for i in sorted_list]

def get_stock_list(context):
    """
    获取目标股票列表，执行完整的选股流程
    
    参数:
        context: 策略上下文对象
    
    返回:
        筛选后的目标股票列表
    
    功能:
        - 获取所有股票并依次过滤：次新股、科创北交、ST股、停牌股、止损黑名单股
        - 按市值升序排序，选取前g.initial_pool_size只股票
        - 过滤当前涨停和跌停的股票
        - 筛选历史涨停次数多的股票
        - 按启动点偏移量排序
        - 按行业分散，选择不同行业的股票
    """
    final_list = []
    yesterday = context.previous_date
    initial_list = get_all_securities("stock", yesterday).index.tolist()    

    # 依次过滤股票
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    
    if g.enable_loss_blacklist:
        initial_list = filter_loss_black(context, initial_list, days=20)
    
    # 按市值升序排序，选取前g.initial_pool_size只股票
    q = query(
        valuation.code,indicator.eps
        ).filter(
            valuation.code.in_(initial_list)
            ).order_by(
                valuation.market_cap.asc()
                )
    df_cap = get_fundamentals(q)
    initial_list = df_cap['code'].tolist()[:g.initial_pool_size]

    # 过滤涨停和跌停的股票
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    
    df = get_price(
        initial_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["open", "low", "close", "high_limit"],
        count=g.history_window_days,
        panel=False,
        fill_paused=False,
    )
        
    # 筛选历史涨停次数多的股票
    initial_list = get_history_highlimit(context, df)
    # 按启动点偏移量排序
    initial_list = get_start_point(context, df)

    # 按行业分散选择股票
    stock_list = get_stock_industry(initial_list)
    final_list = stock_list[:g.max_holdings*2]
    log.info('今日前10:%s' % final_list)
    
    return final_list


def weekly_sell(context):
    """
    每周调仓卖出函数，在周二10:15执行
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 如果是可交易日，先清空空仓月份持有的股票
        - 获取目标股票列表
        - 卖出不在目标列表且昨日未涨停的股票
        - 保留昨日涨停的股票，即使不在目标列表中
    """
    if g.is_no_trading_period == False:
        current_data = get_current_data()
        close_no_trading_hold(context)
        
        # 获取应买入列表 
        g.bought_this_week = []
        g.target_stocks = get_stock_list(context)
        target_list = g.target_stocks[:g.max_holdings*2]
        log.info(str(target_list))

        # 调仓卖出
        for stock in g.current_holdings:
            # 卖出条件：不在目标列表 且 昨日未涨停 且 当前未涨停
            if (stock not in target_list) and (stock not in g.yesterday_limit_up_stocks) and (current_data[stock].last_price < current_data[stock].high_limit):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                pass
                log.info("已持有[%s]" % (stock))

            
            
def weekly_buy(context):
    """
    每周调仓买入函数，在周二10:30执行
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 如果是可交易日，获取目标股票列表
        - 执行买入操作
        - 记录已买入的股票，避免重复买入
    """
    if g.is_no_trading_period == False:
        current_data = get_current_data()
        
        # 获取应买入列表 
        g.bought_this_week = []
        # g.target_stocks = get_stock_list(context)
        target_list = g.target_stocks[:g.max_holdings*2]
        log.info(str(target_list))

        # 调仓买入
        buy_security(context,target_list)
        
        # 记录已买入股票
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.bought_this_week.append(stock)


def check_limit_up(context):
    """
    检查昨日涨停股票的当前状态
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 对昨日涨停的股票进行实时监控
        - 如果涨停打开（当前价格<涨停价），则卖出
        - 如果继续涨停，则继续持有
        - 即使股票不在目标列表中，只要涨停就继续持有
    """
    now_time = context.current_dt
    if g.yesterday_limit_up_stocks != []:
        # 对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_limit_up_stocks:
            if context.portfolio.positions[stock].closeable_amount > -100:
                current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
                # 涨停打开，卖出
                if current_data.iloc[0,0] <    current_data.iloc[0,1]:
                    log.info("[%s]涨停打开，卖出" % (stock))
                    position = context.portfolio.positions[stock]
                    close_position(position)
                    g.sell_reason = 'limitup'
                else:
                    # 继续涨停，继续持有
                    log.info("[%s]涨停，继续持有" % (stock))


def check_remain_amount(context):
    """
    检查并使用剩余资金买入股票
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 如果昨天有股票因为涨停打开而卖出，则今天用剩余资金买入
        - 如果是因为止损而卖出，则不使用剩余资金
        - 避免重复买入本周一已经买入过的股票
    """
    if g.sell_reason == 'limitup':
        # 判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
        g.current_holdings = []
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.current_holdings.append(stock)
        
        # 如果持仓数量不足，则用剩余资金买入
        if len(g.current_holdings) < g.max_holdings:
            target_list = get_stock_list(context)
            # 剔除本周一曾买入的股票，不再买入
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.max_holdings, len(target_list))]
            log.info('有余额可用'+str(round((context.portfolio.cash),2))+'元。'+ str(target_list))
            buy_security(context,target_list)
        g.sell_reason = ''

    else:
        # log.info('虽然有余额（'+str(round((context.portfolio.cash),2))+'元）可用，但是为止损后余额，下周再交易')
        g.sell_reason = ''


def trade_afternoon(context):
    """
    下午交易检查函数，在14:20和14:55执行
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 检查昨日涨停股票是否需要卖出
        - 如果启用放量控制，检查是否出现天量
        - 检查换手率情况
        - 使用剩余资金买入股票
    """
    if g.is_no_trading_period == False:
        check_limit_up(context)
        if g.enable_volume_control == True:
            check_high_volume(context)
        huanshou(context)
        
        check_remain_amount(context)
        
        
def sell_stocks(context):
    """
    止盈止损函数，在每日10:00执行
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 支持三种止损策略：
          1. 止损线止损：个股价格跌破成本价的g.stoploss_threshold倍时止损
          2. 市场趋势止损：大盘平均跌幅超过g.market_crash_threshold时全部清仓
          3. 联合策略：同时使用策略1和策略2
        - 止盈：个股盈利超过100%时卖出
        - 止损后将股票加入黑名单，短期内不再买入
    """
    if g.is_no_trading_period:
        return
    if g.enable_stoploss == True:
        if g.stoploss_mode == 1:
            # 策略1：止损线止损
            for stock in context.portfolio.positions.keys():
                # 股票盈利大于等于100%则卖出
                if context.portfolio.positions[stock].price >= context.portfolio.positions[stock].avg_cost * 2:
                    order_target_value(stock, 0)
                    log.debug("收益100%止盈,卖出{}".format(stock))
                    g.loss_blacklist[stock] = context.current_dt

                # 止损
                elif context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_threshold:
                    order_target_value(stock, 0)
                    log.debug("收益止损,卖出{}".format(stock))
                    g.sell_reason = 'stoploss'
                    g.loss_blacklist[stock] = context.current_dt

        elif g.stoploss_mode == 2:
            # 策略2：市场趋势止损
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            # 计算大盘平均涨跌幅
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.market_crash_threshold:
                g.sell_reason = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
        elif g.stoploss_mode == 3:
            # 策略3：联合策略（策略1 + 策略2）
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            # 计算大盘平均涨跌幅
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.market_crash_threshold:
                # 大盘暴跌，全部清仓
                g.sell_reason = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
            else:
                # 大盘正常，执行个股止损
                for stock in context.portfolio.positions.keys():
                    if context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_threshold:
                        order_target_value(stock, 0)
                        log.debug("收益止损,卖出{}".format(stock))
                        g.sell_reason = 'stoploss'
                        g.loss_blacklist[stock] = context.current_dt

                        

def check_high_volume(context):
    """
    检查持仓股票是否出现天量，如果出现则卖出
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 遍历持仓股票，检查是否出现天量
        - 天量定义：当日成交量 > g.volume_ratio_threshold * 过去g.volume_check_days天的最大成交量
        - 如果出现天量，则卖出该股票
        - 跳过停牌、涨停、不可卖出的股票
    """
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        # 跳过停牌股票
        if current_data[stock].paused == True:
            continue
        # 跳过涨停股票
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        # 跳过不可卖出的股票
        if context.portfolio.positions[stock].closeable_amount ==0:
            continue
        
        # 获取过去g.volume_check_days天的成交量数据
        df_volume = get_bars(stock,count=g.volume_check_days,unit='1d',fields=['volume'],include_now=True, df=True)
        # 判断是否出现天量
        if df_volume['volume'].values[-1] > g.volume_ratio_threshold*df_volume['volume'].values.max():
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"[{stock}]天量，卖出, close_position: {r}")
            g.sell_reason = 'limitup'

            
            
def filter_paused_stock(stock_list):
    """
    过滤停牌股票
    
    参数:
        stock_list: 待过滤的股票列表
    
    返回:
        过滤后的股票列表（不包含停牌股票）
    """
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]



def filter_st_stock(stock_list):
    """
    过滤ST及其他具有退市标签的股票
    
    参数:
        stock_list: 待过滤的股票列表
    
    返回:
        过滤后的股票列表（不包含ST、*ST、退市股票）
    """
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


def filter_kcbj_stock(stock_list):
    """
    过滤科创板、北交所股票
    
    参数:
        stock_list: 待过滤的股票列表
    
    返回:
        过滤后的股票列表（不包含科创板、北交所股票）
    """
    return [stock for stock in stock_list if not (stock[0] in ('4', '8') or stock[:2] == '68')]


def filter_limitup_stock(context, stock_list):
    """
    过滤涨停的股票
    
    参数:
        context: 策略上下文对象
        stock_list: 待过滤的股票列表
    
    返回:
        过滤后的股票列表（不包含当前涨停的股票，已持有的股票除外）
    """
    # last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or current_data[stock].last_price < current_data[stock].high_limit]


def filter_limitdown_stock(context, stock_list):
    """
    过滤跌停的股票
    
    参数:
        context: 策略上下文对象
        stock_list: 待过滤的股票列表
    
    返回:
        过滤后的股票列表（不包含当前跌停的股票，已持有的股票除外）
    """
    # last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in context.portfolio.positions.keys()
            or current_data[stock].last_price > current_data[stock].low_limit) 
            ]


def filter_new_stock(context,stock_list):
    """
    过滤次新股（上市不足375天的股票）
    
    参数:
        context: 策略上下文对象
        stock_list: 待过滤的股票列表
    
    返回:
        过滤后的股票列表（不包含次新股）
    """
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < timedelta(days=375)]


def filter_highprice_stock(context,stock_list):
    """
    过滤高价股（股价超过g.max_price的股票）
    
    参数:
        context: 策略上下文对象
        stock_list: 待过滤的股票列表
    
    返回:
        过滤后的股票列表（不包含高价股，已持有的股票除外）
    """
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] <= g.max_price]


def filter_not_buy_again(stock_list):
    """
    过滤本周一已经买入过的股票
    
    参数:
        stock_list: 待过滤的股票列表
    
    返回:
        过滤后的股票列表（不包含本周一已买入的股票）
    """
    return [stock for stock in stock_list if stock not in g.bought_this_week]
    
def filter_loss_black(context, stock_list, days=20):
    """
    过滤最近被止损的股票
    
    参数:
        context: 策略上下文对象
        stock_list: 待过滤的股票列表
        days: 止损黑名单天数，默认20天
    
    返回:
        过滤后的股票列表（不包含最近days天内被止损的股票）
    """
    result_list = []
    for stock in stock_list:
        if (
            stock in g.loss_blacklist.keys()
            and context.current_dt - g.loss_blacklist[stock]
            < timedelta(days=days)
        ):
            log.info(
                f"{stock}由于近期止损被过滤, 止损时间：{g.loss_blacklist[stock]}"
            )
            continue
        result_list.append(stock)
    return result_list
    
    
def get_stock_industry(stock):
    """
    获取股票所属行业，并选择不同行业的股票
    
    参数:
        stock: 待筛选的股票列表
    
    返回:
        按行业分散选择的股票列表（最多10个不同行业的股票）
    
    功能:
        - 获取每只股票的申万二级行业分类
        - 按顺序选择不同行业的股票
        - 最多选择10个不同行业的股票，实现行业分散
    """
    result = get_industry(security=stock)
    selected_stocks = []
    industry_list = []

    for stock_code, info in result.items():
        industry_name = info['sw_l2']['industry_name']
        if industry_name not in industry_list:
            industry_list.append(industry_name)
            selected_stocks.append(stock_code)
            # 选取了 10 个不同行业的股票
            if len(industry_list) == 10 :
                break
    return selected_stocks

            
def huanshoulv(context, stock, is_avg=False):
    """
    计算股票换手率
    
    参数:
        context: 策略上下文对象
        stock: 股票代码
        is_avg: 是否计算平均换手率，True为计算20日平均换手率，False为计算实时换手率
    
    返回:
        换手率（小数形式）
    
    功能:
        - 计算实时换手率：当日成交量 / 流通股本
        - 计算平均换手率：过去20日平均换手率
    """
    if is_avg:
        # 计算平均换手率
        start_date = context.current_dt - timedelta(days=20)
        end_date = context.previous_date
        df_volume = get_price(stock,end_date=end_date, frequency='daily', fields=['volume'],count=20)
        df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        # 计算实时换手率
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now, frequency='1m', fields=['volume'],
                           skip_paused=False, fq='pre', panel=True, fill_paused=False)
        volume = df_vol['volume'].sum()
        date_pre = context.previous_date
        df_circulating_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        circulating_cap = df_circulating_cap['circulating_cap'].iloc[0]  if not df_circulating_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        turnover_ratio = volume / (circulating_cap * 10000)
        return turnover_ratio            


def huanshou(context):
    """
    换手率检测，根据换手率情况决定是否卖出
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 遍历持仓股票，计算实时换手率和平均换手率
        - 判断是否缩量或放量：
          - 缩量：平均换手率 < 0.3%
          - 放量：实时换手率 > 10% 且 实时换手率 / 平均换手率 > 2
        - 如果出现缩量或放量，则卖出该股票
        - 跳过停牌、接近涨停、不可卖出的股票
    """
    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    
    for stock in context.portfolio.positions:
        # 跳过停牌股票
        if current_data[stock].paused == True:
            continue
        # 跳过接近涨停的股票（价格 >= 涨停价 * 0.97）
        if current_data[stock].last_price >= current_data[stock].high_limit*0.97:
            continue
        # 跳过不可卖出的股票
        if context.portfolio.positions[stock].closeable_amount ==0:
            continue
        
        # 计算实时换手率和平均换手率
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0: continue
        
        # 计算换手率倍率
        r = rt / avg
        action, icon = '', ''
        
        # 判断缩量或放量
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        
        # 如果出现缩量或放量，则卖出
        if action:
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"{action} {stock} {get_security_info(stock).display_name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon} close_position: {r}")
            g.sell_reason = 'limitup'
            
            
def order_target_value_(security, value):
    """
    自定义下单函数，封装order_target_value
    
    参数:
        security: 股票代码
        value: 目标市值，0表示清仓
    
    返回:
        订单对象
    """
    if value == 0:
        pass
    else:
        pass
    return order_target_value(security, value)

def open_position(security, value):
    """
    开仓函数，买入指定市值的股票
    
    参数:
        security: 股票代码
        value: 目标市值
    
    返回:
        bool: 成功买入返回True，否则返回False
    """
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False

def close_position(position):
    """
    平仓函数，卖出指定持仓
    
    参数:
        position: 持仓对象
    
    返回:
        bool: 成功卖出返回True，否则返回False
    """
    security = position.security
    order = order_target_value_(security, 0)
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False

def buy_security(context,target_list,cash=0,buy_number=0):
    """
    买入模块，批量买入目标股票
    
    参数:
        context: 策略上下文对象
        target_list: 目标股票列表
        cash: 可用资金，默认为0时使用总资产
        buy_number: 本次买入数量，默认为0时买入目标数量
    
    功能:
        - 计算每只股票的目标市值
        - 遍历目标列表，依次买入未持有的股票
        - 记录已买入的股票，避免重复买入
        - 达到目标持仓数量后停止买入
    """
    # 调仓买入
    position_count = len(context.portfolio.positions)
    target_num = g.max_holdings
    if cash == 0:
        cash = context.portfolio.total_value
    if buy_number == 0:
        buy_number = target_num
    bought_num = 0
    log.info(f"---------------------buy_number：{buy_number}")
    
    # 如果当前持仓数量小于目标数量，则买入
    if target_num > position_count:
        # 计算每只股票的目标市值
        value = cash / (target_num)
        for stock in target_list:
            # 只买入未持有的股票
            if context.portfolio.positions[stock].total_amount == 0:
                if bought_num < buy_number:
                    if open_position(stock, value):
                        g.bought_this_week.append(stock)
                        bought_num += 1
                        if len(context.portfolio.positions) == target_num:
                            break


def today_is_between(context):
    """
    判断今天是否为空仓期间
    
    参数:
        context: 策略上下文对象
    
    返回:
        bool: 如果是空仓期间返回True，否则返回False
    
    功能:
        - 若 g.enable_no_trading_period 为 True，且当前月份在 g.months 内，则为空仓期
        - 用于避开市场风险较高的时期
    """
    if not g.enable_no_trading_period:
        return False
    months = getattr(g, 'months', None) or []
    return context.current_dt.month in months


def close_account(context):
    """空仓月份兜底：清掉残留小市值股票（五福 ETF 由 13:09 午盘流水线负责）。"""
    if g.is_no_trading_period:
        _wufu_liquidate_stocks(context)


def close_no_trading_hold(context):
    """退出空仓月份：清五福 ETF，恢复小市值交易。"""
    _sell_all_wufu_etfs(context)
    g.wufu_mode_active = False



def print_position_info(context):
    """
    打印持仓信息
    
    参数:
        context: 策略上下文对象
    
    功能:
        - 打印每只持仓股票的代码、收益率、持仓数量、市值
        - 打印账户余额
        - 用于监控和调试
    """
    log.info('—————————————————————— 周总结 开始 ——————————————————————')
    for position in list(context.portfolio.positions.values()):
        securities=position.security
        cost=position.avg_cost
        price=position.price
        ret=100*(price/cost-1)
        value=position.value
        amount=position.total_amount    
        log.info(f"代码:{securities}, 收益率:{ret:.2f}%, 持仓(股):{amount}, 市值:{value:.2f}")
        log.info('———————————————————————————————————')
    log.info(f"余额:{context.portfolio.cash:.2f}")
    log.info('—————————————————————— 周总结 结束 ——————————————————————')


# ========================================================================
# 空仓月份 · 五福 ETF 协调层（逻辑来自 joinquant/五福ETF.py，空仓月 g.months 内启用）
# ========================================================================
WUFU_MORNING_TIME = '09:00'
WUFU_POOL_UPDATE_TIME = '09:40'
WUFU_DRAWDOWN_TIME = '10:31'
WUFU_AFTERNOON_TRADE_TIME = '13:09'
_WUFU_ETF_CODES = None


def _build_wufu_etf_codes():
    global _WUFU_ETF_CODES
    if _WUFU_ETF_CODES is not None:
        return _WUFU_ETF_CODES
    codes = set()
    for attr in ('global_etf_pool', 'china_etf_pool'):
        for raw in getattr(g, attr, []) or []:
            codes.add(raw)
    codes.add(getattr(g, 'defensive_etf', '511880.XSHG'))
    _WUFU_ETF_CODES = codes
    return _WUFU_ETF_CODES


def _is_wufu_etf(code):
    return code in _build_wufu_etf_codes()


def _wufu_etf_positions(context):
    return [
        s for s, p in context.portfolio.positions.items()
        if p.total_amount > 0 and _is_wufu_etf(s)
    ]


def _wufu_empty_month_active(context):
    return bool(
        getattr(g, 'enable_no_trading_period', False)
        and getattr(g, 'is_no_trading_period', False)
    )


def _wufu_liquidate_stocks(context):
    """空仓月：清小市值股票，保留五福 ETF。"""
    if not _wufu_empty_month_active(context):
        return
    for stock, pos in list(context.portfolio.positions.items()):
        if pos.total_amount <= 0 or _is_wufu_etf(stock):
            continue
        try:
            if close_position(pos):
                log.info('[空仓月] 卖出小市值 %s' % stock)
            else:
                order_target_value(stock, 0)
                log.info('[空仓月] order_target_value 卖出 %s' % stock)
        except Exception as e:
            log.info('[空仓月] 卖出 %s 失败: %s' % (stock, e))


def _sell_all_wufu_etfs(context):
    for stock in _wufu_etf_positions(context):
        try:
            order_target_value(stock, 0)
            log.info('[空仓月结束] 卖出五福 ETF %s' % stock)
        except Exception as e:
            log.info('[空仓月结束] 卖出 %s 失败: %s' % (stock, e))


def _refresh_wufu_mode_flag(context):
    if not _wufu_empty_month_active(context):
        g.wufu_mode_active = False
        return
    g.wufu_mode_active = True
    log.info('[五福ETF] 空仓月份 %s，%s 执行五福轮动' % (
        context.current_dt.strftime('%Y-%m'), WUFU_AFTERNOON_TRADE_TIME
    ))


def _should_run_wufu_minute(context):
    if not _wufu_empty_month_active(context):
        return False
    return bool(getattr(g, 'wufu_mode_active', False) or _wufu_etf_positions(context))


def _wufu_liquidate_stocks_schedule(context):
    _wufu_liquidate_stocks(context)


def _wufu_morning_schedule(context):
    if not _wufu_empty_month_active(context):
        return
    try:
        morning_routine(context)
    except Exception as e:
        log.info('[五福ETF] 晨间异常: {}'.format(e))


def _wufu_drawdown_schedule(context):
    if not _wufu_empty_month_active(context):
        return
    drawdown_monitor_routine(context)


def _wufu_pool_update_schedule(context):
    if not _wufu_empty_month_active(context):
        g.wufu_mode_active = False
        return
    try:
        check_weak_period_daily(context)
        _refresh_wufu_mode_flag(context)
    except Exception as e:
        log.info('[五福ETF] 09:40 池更新异常: {}'.format(e))


def _wufu_afternoon_schedule(context):
    if not _wufu_empty_month_active(context):
        return
    if not getattr(g, 'wufu_mode_active', False):
        return
    afternoon_routine(context)


def _wufu_eod_schedule(context):
    if not _wufu_empty_month_active(context):
        return
    try:
        reset_daily_flags(context)
    except Exception as e:
        log.info('[五福ETF] 收盘任务异常: {}'.format(e))


def _register_wufu_empty_month_daily(context):
    wufu_setup(context, register_schedules=False)
    _build_wufu_etf_codes()
    dd_t = str(getattr(g, 'dd_monitor_time', WUFU_DRAWDOWN_TIME))
    run_daily(_wufu_liquidate_stocks_schedule, '08:55')
    run_daily(_wufu_morning_schedule, WUFU_MORNING_TIME)
    run_daily(_wufu_drawdown_schedule, dd_t)
    run_daily(_wufu_pool_update_schedule, WUFU_POOL_UPDATE_TIME)
    run_daily(_wufu_afternoon_schedule, WUFU_AFTERNOON_TRADE_TIME)
    run_daily(_wufu_eod_schedule, '15:10')
    log.info(
        '[五福ETF] 空仓月已注册: 08:55清股 / %s / %s / %s / %s'
        % (WUFU_MORNING_TIME, WUFU_POOL_UPDATE_TIME, dd_t, WUFU_AFTERNOON_TRADE_TIME)
    )
# __WUFU_MODULE_BEGIN__

# ========================================================================
# 五福 ETF 模块（源自 joinquant/五福ETF.py；独立运行请用原文件）
# ========================================================================
dt_time = time  # 五福内部别名

def wufu_setup(context, register_schedules=True):
    """五福参数初始化；register_schedules=False 时由小市值策略注册带门禁的 run_daily。"""

    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001,
                              close_commission=0.0001, close_today_commission=0.0001,
                              min_commission=5), type="fund")
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    log.info("【五福闹新春】v5.1启动！")

    # ==================== ETF池定义 ====================
    # 全球/海外ETF池（含大宗商品和海外市场ETF）
    g.global_etf_pool = [
#大宗商品ETF：
        '518880.XSHG',  # (黄金ETF) [ETF]-日均成交额：51.35亿元-上市日期：2013-07-29
        '501018.XSHG',  # (南方原油) [LOF]-日均成交额：24.38亿元-上市日期：2016-06-28
        '161226.XSHE',  # (国投白银LOF) [LOF]-日均成交额：5.44亿元-上市日期：2015-08-17
        '159985.XSHE',  # (豆粕ETF华夏) [ETF]-日均成交额：4.63亿元-上市日期：2019-12-05
        '159980.XSHE',  # (有色ETF大成) [ETF]-日均成交额：3.84亿元-上市日期：2019-12-24
#海外ETF：       
        '513310.XSHG',  # (中韩芯片) [ETF]-日均成交额：59.37亿元-上市日期：2022-12-22
        '159518.XSHE',  # (标普油气ETF嘉实) [ETF]-日均成交额：27.93亿元-上市日期：2023-11-15
        '159509.XSHE',  # (纳指科技ETF景顺) [ETF]-日均成交额：7.24亿元-上市日期：2023-08-08
        '513100.XSHG',  # (纳指ETF) [ETF]-日均成交额：5.02亿元-上市日期：2013-05-15
        '513520.XSHG',  # (日经ETF) [ETF]-日均成交额：3.72亿元-上市日期：2019-06-25
        '513500.XSHG',  # (标普500) [ETF]-日均成交额：2.89亿元-上市日期：2014-01-15
        '159502.XSHE',  # (标普生物科技ETF嘉实) [ETF]-日均成交额：1.80亿元-上市日期：2024-01-10
        '513400.XSHG',  # (道琼斯) [ETF]-日均成交额：1.70亿元-上市日期：2024-02-02
        '513030.XSHG',  # (德国ETF) [ETF]-日均成交额：0.95亿元-上市日期：2014-09-05
        '513290.XSHG',  # (纳指生物) [ETF]-日均成交额：0.78亿元-上市日期：2022-08-29
        '520830.XSHG',  # (沙特ETF) [ETF]-日均成交额：0.62亿元-上市日期：2024-07-16
        '159529.XSHE',  # (标普消费ETF景顺) [ETF]-日均成交额：0.50亿元-上市日期：2024-02-02
        '513400.XSHG',  # (道琼斯ETF) [ETF]-日均成交额：0.2亿元-上市日期：2024-02-29
        '164824.XSHE',  # (印度基金LOF) [ETF]-日均成交额：0.50亿元-上市日期：2018-08-31
        "513080.XSHG",  # 法国ETF
        "513730.XSHG",  # 东南亚ETF
        "511380.XSHG",  # 可转债ETF
        "511010.XSHG",  # 国债ETF
        "511220.XSHG",  # 城投债E
]
    # 中国ETF池（含港股、指数、行业ETF）
    g.china_etf_pool = [
#港股ETF：
        '513090.XSHG',  # (香港证券) [ETF]-日均成交额：54.24亿元-上市日期：2020-03-26
        '513120.XSHG',  # (HK创新药) [ETF]-日均成交额：52.34亿元-上市日期：2022-07-12
        '513180.XSHG',  # (恒指科技) [ETF]-日均成交额：36.66亿元-上市日期：2021-05-25
        '513330.XSHG',  # (恒生互联) [ETF]-日均成交额：20.45亿元-上市日期：2021-02-08
        '513750.XSHG',  # (港股非银) [ETF]-日均成交额：9.55亿元-上市日期：2023-11-27
        '159892.XSHE',  # (恒生医药ETF华夏) [ETF]-日均成交额：7.90亿元-上市日期：2021-10-19
        '513190.XSHG',  # (H股金融) [ETF]-日均成交额：3.74亿元-上市日期：2023-10-11
        '159605.XSHE',  # (中概互联ETF广发) [ETF]-日均成交额：3.19亿元-上市日期：2021-12-02
        '513630.XSHG',  # (香港红利) [ETF]-日均成交额：2.84亿元-上市日期：2023-12-08
        '159323.XSHE',  # (港股通汽车ETF华夏) [ETF]-日均成交额：1.98亿元-上市日期：2025-01-08
        '510900.XSHG',  # (恒生中国) [ETF]-日均成交额：1.46亿元-上市日期：2012-10-22
        '513920.XSHG',  # (央企40) [ETF]-日均成交额：1.38亿元-上市日期：2024-01-05
        '513970.XSHG',  # (恒生消费) [ETF]-日均成交额：0.82亿元-上市日期：2023-04-21
#指数ETF：        
        '511380.XSHG',  # (转债ETF) [ETF]-日均成交额：115.92亿元-上市日期：2020-04-07
        '512050.XSHG',  # (A500E) [ETF]-日均成交额：48.05亿元-上市日期：2024-11-15
        '510500.XSHG',  # (500ETF) [ETF]-日均成交额：45.45亿元-上市日期：2013-03-15
        '159915.XSHE',  # (创业板ETF易方达) [ETF]-日均成交额：43.55亿元-上市日期：2011-12-09
        '510300.XSHG',  # (300ETF) [ETF]-日均成交额：34.60亿元-上市日期：2012-05-28
        '512100.XSHG',  # (1000ETF) [ETF]-日均成交额：25.26亿元-上市日期：2016-11-04
        '159949.XSHE',  # (创业板50ETF华安) [ETF]-日均成交额：16.52亿元-上市日期：2016-07-22
        '588080.XSHG',  # (科创板50) [ETF]-日均成交额：13.32亿元-上市日期：2020-11-16
        '159967.XSHE',  # (创业板成长ETF华夏) [ETF]-日均成交额：5.29亿元-上市日期：2019-07-15
        '588220.XSHG',  # (科创100F) [ETF]-日均成交额：5.01亿元-上市日期：2023-09-15
        '563300.XSHG',  # (中证2000) [ETF]-日均成交额：4.13亿元-上市日期：2023-09-14
        '510760.XSHG',  # (上证ETF) [ETF]-日均成交额：1.45亿元-上市日期：2020-09-09
#行业ETF：
        '588200.XSHG',  # (科创芯片) [ETF]-日均成交额：28.07亿元-上市日期：2022-10-26
        '515880.XSHG',  # (通信ETF) [ETF]-日均成交额：22.39亿元-上市日期：2019-09-06
        '159981.XSHE',  # (能源化工ETF建信) [ETF]-日均成交额：21.63亿元-上市日期：2020-01-17
        '512880.XSHG',  # (证券ETF) [ETF]-日均成交额：16.21亿元-上市日期：2016-08-08
        '513350.XSHG',  # (油气ETF) [ETF]-日均成交额：15.66亿元-上市日期：2023-11-28
        '159326.XSHE',  # (电网设备ETF华夏) [ETF]-日均成交额：14.86亿元-上市日期：2024-09-09
        '159516.XSHE',  # (半导体设备ETF国泰) [ETF]-日均成交额：14.23亿元-上市日期：2023-07-27
        '159206.XSHE',  # (卫星ETF永赢) [ETF]-日均成交额：13.87亿元-上市日期：2025-03-14
        '512480.XSHG',  # (半导体) [ETF]-日均成交额：13.07亿元-上市日期：2019-06-12
        '159363.XSHE',  # (创业板人工智能ETF华宝) [ETF]-日均成交额：10.50亿元-上市日期：2024-12-16
        '159870.XSHE',  # (化工ETF鹏华) [ETF]-日均成交额：10.03亿元-上市日期：2021-03-03
        '512400.XSHG',  # (有色ETF) [ETF]-日均成交额：9.97亿元-上市日期：2017-09-01
        '159755.XSHE',  # (电池ETF广发) [ETF]-日均成交额：8.58亿元-上市日期：2021-06-24
        '588170.XSHG',  # (科创半导) [ETF]-日均成交额：7.74亿元-上市日期：2025-04-08
        '159992.XSHE',  # (创新药ETF银华) [ETF]-日均成交额：7.59亿元-上市日期：2020-04-10
        '159995.XSHE',  # (芯片ETF华夏) [ETF]-日均成交额：7.51亿元-上市日期：2020-02-10
        '512890.XSHG',  # (红利低波) [ETF]-日均成交额：6.79亿元-上市日期：2019-01-18
        '515220.XSHG',  # (煤炭ETF) [ETF]-日均成交额：6.44亿元-上市日期：2020-03-02
        '159566.XSHE',  # (储能电池ETF易方达) [ETF]-日均成交额：6.31亿元-上市日期：2024-02-08
        '159819.XSHE',  # (人工智能ETF易方达) [ETF]-日均成交额：6.26亿元-上市日期：2020-09-23
        '512800.XSHG',  # (银行ETF) [ETF]-日均成交额：6.13亿元-上市日期：2017-08-03
        '512690.XSHG',  # (酒ETF) [ETF]-日均成交额：5.99亿元-上市日期：2019-05-06
        '515050.XSHG',  # (5GETF) [ETF]-日均成交额：5.93亿元-上市日期：2019-10-16
        '562500.XSHG',  # (机器人) [ETF]-日均成交额：5.83亿元-上市日期：2021-12-29
        '512170.XSHG',  # (医疗ETF) [ETF]-日均成交额：5.63亿元-上市日期：2019-06-17
        '517520.XSHG',  # (黄金股) [ETF]-日均成交额：5.01亿元-上市日期：2023-11-01
        '159869.XSHE',  # (游戏ETF华夏) [ETF]-日均成交额：4.77亿元-上市日期：2021-03-05
        '512070.XSHG',  # (证券保险) [ETF]-日均成交额：4.61亿元-上市日期：2014-07-18
        '159611.XSHE',  # (电力ETF广发) [ETF]-日均成交额：4.42亿元-上市日期：2022-01-07
        '562800.XSHG',  # (稀有金属) [ETF]-日均成交额：4.39亿元-上市日期：2021-09-27
        '515120.XSHG',  # (创新药) [ETF]-日均成交额：4.34亿元-上市日期：2021-01-04
        '512010.XSHG',  # (医药ETF) [ETF]-日均成交额：4.27亿元-上市日期：2013-10-28
        '510880.XSHG',  # (红利ETF) [ETF]-日均成交额：3.97亿元-上市日期：2007-01-18
        '515790.XSHG',  # (光伏ETF) [ETF]-日均成交额：3.87亿元-上市日期：2020-12-18
        '515980.XSHG',  # (人工智能) [ETF]-日均成交额：3.78亿元-上市日期：2020-02-10
        '512660.XSHG',  # (军工ETF) [ETF]-日均成交额：3.75亿元-上市日期：2016-08-08
        '159928.XSHE',  # (消费ETF汇添富) [ETF]-日均成交额：3.66亿元-上市日期：2013-09-16
        '512710.XSHG',  # (军工龙头) [ETF]-日均成交额：3.60亿元-上市日期：2019-08-26
        '560860.XSHG',  # (工业有色) [ETF]-日均成交额：3.57亿元-上市日期：2023-03-13
        '515030.XSHG',  # (新汽车) [ETF]-日均成交额：3.33亿元-上市日期：2020-03-04
        '159766.XSHE',  # (旅游ETF富国) [ETF]-日均成交额：3.30亿元-上市日期：2021-07-23
        '159218.XSHE',  # (卫星ETF招商) [ETF]-日均成交额：3.21亿元-上市日期：2025-05-22
        '159852.XSHE',  # (软件ETF嘉实) [ETF]-日均成交额：3.19亿元-上市日期：2021-02-09
        '516160.XSHG',  # (新能源) [ETF]-日均成交额：3.07亿元-上市日期：2021-02-04
        '516150.XSHG',  # (稀土基金) [ETF]-日均成交额：3.03亿元-上市日期：2021-03-17
        '159227.XSHE',  # (航空航天ETF华夏) [ETF]-日均成交额：2.98亿元-上市日期：2025-05-16
        '159583.XSHE',  # (通信ETF富国) [ETF]-日均成交额：2.93亿元-上市日期：2024-07-08
        '588790.XSHG',  # (科创智能) [ETF]-日均成交额：2.62亿元-上市日期：2025-01-09
        '159865.XSHE',  # (养殖ETF国泰) [ETF]-日均成交额：2.44亿元-上市日期：2021-03-08
        '512980.XSHG',  # (传媒ETF) [ETF]-日均成交额：2.43亿元-上市日期：2018-01-19
        '159851.XSHE',  # (金融科技ETF华宝) [ETF]-日均成交额：2.27亿元-上市日期：2021-03-19
        '561360.XSHG',  # (石油ETF) [ETF]-日均成交额：2.04亿元-上市日期：2023-10-31
        '561980.XSHG',  # (芯片设备) [ETF]-日均成交额：2.01亿元-上市日期：2023-09-01
        '562590.XSHG',  # (半导材料) [ETF]-日均成交额：1.76亿元-上市日期：2023-10-18
        '512200.XSHG',  # (地产ETF) [ETF]-日均成交额：1.71亿元-上市日期：2017-09-25
        '159732.XSHE',  # (消费电子ETF华夏) [ETF]-日均成交额：1.62亿元-上市日期：2021-08-23
        '159667.XSHE',  # (工业母机ETF国泰) [ETF]-日均成交额：1.58亿元-上市日期：2022-10-26
        '516510.XSHG',  # (云计算) [ETF]-日均成交额：1.49亿元-上市日期：2021-04-07
        '159840.XSHE',  # (锂电池ETF工银) [ETF]-日均成交额：1.42亿元-上市日期：2021-08-20
        '159998.XSHE',  # (计算机ETF天弘) [ETF]-日均成交额：1.30亿元-上市日期：2020-04-13
        '159825.XSHE',  # (农业ETF富国) [ETF]-日均成交额：1.15亿元-上市日期：2020-12-29
        '512670.XSHG',  # (国防ETF) [ETF]-日均成交额：1.12亿元-上市日期：2019-08-01
        '159883.XSHE',  # (医疗器械ETF永赢) [ETF]-日均成交额：1.05亿元-上市日期：2021-04-30
        '515210.XSHG',  # (钢铁ETF) [ETF]-日均成交额：1.01亿元-上市日期：2020-03-02
        '515400.XSHG',  # (大数据) [ETF]-日均成交额：0.94亿元-上市日期：2021-01-20
        '159256.XSHE',  # (创业板软件ETF华夏) [ETF]-日均成交额：0.83亿元-上市日期：2025-08-04
        '561330.XSHG',  # (矿业ETF) [ETF]-日均成交额：0.83亿元-上市日期：2022-11-01
        '515170.XSHG',  # (食品饮料) [ETF]-日均成交额：0.67亿元-上市日期：2021-01-13
        '159638.XSHE',  # (高端装备ETF嘉实) [ETF]-日均成交额：0.56亿元-上市日期：2022-08-12
        '516520.XSHG',  # (智能驾驶) [ETF]-日均成交额：0.47亿元-上市日期：2021-03-01
        '513360.XSHG',  # (教育ETF) [ETF]-日均成交额：0.43亿元-上市日期：2021-06-17
        '516190.XSHG',  # (文娱ETF) [ETF]-日均成交额：0.18亿元-上市日期：2021-09-17
    ]
    # 固定ETF池 = 全球池 + 中国池（正常期使用）
    g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool

    g.avg_etf_money_threshold = None
    # 全市场近3日 ETF 日均总成交额 avg_total_money；门槛 = avg_total_money / 分母（原硬编码 20000）
    g.global_liquidity_threshold_divisor = 20000
    g.filtered_fixed_pool = []
    g.dynamic_etf_pool = []
    g.merged_etf_pool = []
    g.ranked_etfs_result = []
    g.filtered_global_pool = []
    
    # 三态市场：走弱期 / 正常期 / 震荡期（每日 09:40 判定，全日有效）
    g.market_regime = '震荡期'
    g.is_a_share_weak = False  # 等价于 market_regime == '走弱期'，便于旧逻辑阅读
    g.regime_prev_day = None           # 上一交易日早盘判定结果（用于切换/反复跳跃日志）
    g.regime_prev_prev_day = None      # 上上交易日早盘判定结果
    g.regime_flip_flop_count = 0       # 「隔日跳回」A→B→A 累计次数（整个回测）
    # 指标与生效不一致时：需连续 N 个交易日指标均为「目标状态」才真正切换（默认 2，减轻一日游/死猫跳）
    g.regime_switch_confirm_days = 2
    g.regime_switch_pending_raw = None    # 待确认的指标状态
    g.regime_switch_pending_streak = 0    # 已连续多少个交易日指标均为 pending_raw
    g.regime_last_change_date = None      # 最近一次生效状态切换日
    g.normal_ma_lookback = 10          # 正常期广度：站上 MA10 的指数个数
    g.regime_ma20_lookback = 20        # 走弱判定用的 MA20 周期（日）
    g.weak_period_ma_lookback = 10     # 保留变量名，与 normal_ma_lookback 一致
    # 六指数齐备时：below_ma20 计数 ≥ 此值 → 走弱期；above_ma10 计数 ≥ 此值 → 正常期（且未触发走弱）
    g.regime_weak_below_ma20_min = 4   # 默认 6 即「六指均跌破 MA20」
    g.regime_normal_above_ma10_min = 4

    # 震荡期高斯滤波（对齐五福35）
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002

    # 回测全周期：各状态累计交易日与当日净值复利因子（收盘 after_close 更新）
    g.regime_day_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_return_factors = {'正常期': 1.0, '震荡期': 1.0, '走弱期': 1.0}
    # 有上一日净值可比时：各状态下日收益为正/负/平的天数，及日收益率算术累加（不含首日）
    g.regime_win_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_loss_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_flat_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_sum_pos_daily_ret = {'正常期': 0.0, '震荡期': 0.0, '走弱期': 0.0}
    g.regime_sum_neg_daily_ret = {'正常期': 0.0, '震荡期': 0.0, '走弱期': 0.0}
    g.prev_eod_portfolio_value = None

    g.holdings_num = 1
    g.holdings_num_normal = 1
    g.holdings_num_oscillation = 1
    g.holdings_num_weak = 1
    g.defensive_etf = "511880.XSHG"
    g.min_money = 10
    g.target_etfs_list = []
    g.trade_entry_open = {}
    g.trade_roundtrip_history = []
    # 卖出时短动量近「三个交易日」为「增增增」的标的：下一交易日 13:10 打印区间收益与动量复盘
    g.pending_sm3up_sell_followups = []
    g.last_metrics_by_etf_code = {}

    g.etf_names_dict = {}
    g.cache_date = None
    g.yesterday_close_cache = {}

    g.lookback_days = 25
    g.min_score_threshold = 0.2
    g.max_score_threshold = 5
    g.score_threshold_ratio = 0.9
    g.short_momentum_lookback = 21
    g.short_momentum_min_score = 0
    g.short_momentum_max_score = 6

    # ==================== 震荡收割 / Whipsaw（参照五福35warmup，默认与震荡期联动）====================
    g.enable_smoothed_momentum_input = False
    g.smoothed_ma_window = 5
    g.smoothed_momentum_only_in_range = True
    g.enable_range_r2_veto = False
    g.r2_threshold_range_bound = 0.9
    g.enable_range_momentum_floor = False
    g.range_momentum_min = 0.0
    g.range_momentum_max = 2.0
    g.enable_range_short_momentum_limits = True
    g.range_short_momentum_min = 0.0
    g.range_short_momentum_max = 6.0
    g.enable_switch_hysteresis = False
    g.switch_buffer_normal = 0.10
    g.switch_buffer_range = 0.40
    g.enable_dual_positive_momentum = True
    g.dual_positive_only_in_range = True
    g.whipsaw_options_only_in_range = True
    g.log_whipsaw_filter_detail = True
    # 详细日志开关（默认关闭）
    g.log_pool_update_details = False      # 阈值/池更新相关详细日志
    g.log_first_step_ranking = False       # 动量第一步全量排序日志

    g.enable_r2_filter = True
    g.r2_threshold = 0.4
    g.enable_ma_filter = True
    g.ma_lookback = 10
    g.ma_threshold = 1.0
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 1.8
    # 量比阈值缓冲带（默认关闭；开启后在 [threshold, threshold+buffer) 内仍视为通过）
    g.enable_volume_threshold_buffer = True
    g.volume_threshold_buffer = 0.1
    g.enable_loss_filter = True
    g.loss = 0.97
    g.enable_premium_filter = False
    g.max_premium_rate = 30
    g.enable_laplace_filter = True
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.002

    # 正常/震荡/走弱期防频换：当前持仓连续未重返「当日目标持仓数 TopK」达到阈值后才强制换股
    # 兼容 holdings_num=1 与 holdings_num>1（多持仓时按每只ETF分别累计 streak）
    g.normal_max_days_not_rank1 = 5
    # 多持仓(holdings_num>1)时，正常/震荡期分别使用独立阈值，默认与单持仓阈值一致
    g.normal_max_days_not_topk = 5
    g.oscillation_max_days_not_topk = 5
    g.normal_not_rank1_streak = 0       # 当前持仓连续「在候选池但非全表第1名」的交易日数
    g.normal_streak_hold_code = None    # streak 绑定的持仓代码
    g.normal_not_topk_streaks = {}      # 多持仓防频换：{etf: 连续未进TopK天数}
    # True：震荡期启用与正常期相同的防频换逻辑（共用 streak、normal_max_days_not_rank1）
    g.oscillation_anti_churn_enabled = True
    # True：走弱期启用与正常期相同的防频换逻辑（共用 streak、normal_max_days_not_rank1）
    g.weak_anti_churn_enabled = True

    g.max_portfolio_value = 0
    g.drawdown_threshold = 0.03
    g.drawdown_records = []
    # ---------- 组合回撤分级动作（在 monitor_drawdown 中，默认关闭，与旧回测一致）----------
    # 总开关：True 时，在已有「≥drawdown_threshold 预警日志」之外，按阈值执行减仓/切防御/清仓
    g.enable_drawdown_risk_actions = True
    # 分级阈值（相对历史最高净值 g.max_portfolio_value 的回撤比例）；须满足 high > mid > low > drawdown_threshold
    g.dd_half_position_threshold = 0.10      # ≥此：按可卖数量保留 dd_partial_close_keep_fraction，其余卖出
    g.dd_switch_defensive_threshold = 0.12 # ≥此：清仓非防御标的（防御可用时）；否则仅打日志
    g.dd_flat_threshold = 0.20               # ≥此：全部可卖标的清仓
    g.dd_partial_close_keep_fraction = 0.50  # 减半仓时保留「可卖股数」的比例（0~1）
    # 同一自然日最多触发一档组合回撤动作（避免与其它定时任务重复冲击）
    g.dd_action_cooldown_date = None
    # 执行任意一档动作后，是否将 g.max_portfolio_value 重置为当前净值（避免空仓后仍相对历史峰值天天触发高档）
    g.dd_reset_peak_after_action = True
    # 回撤监控触发时刻（聚宽 run_daily）：勿用 09:00——尚未连续竞价，QDII/LOF 常见 10:30 起才有场内成交价
    g.dd_monitor_time = '10:31'
    # True：用 get_current_data().last_price×持仓数量 + 现金 重估组合市值算回撤（场内成交价口径，避免盘前/净值错觉）
    g.dd_valuation_use_mtm_last_price = True

    g.use_fixed_stop_loss = True
    g.fixedStopLossThreshold = 0.92
    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95
    # 当日 13:10 午盘买入前发生的「分钟止损」成功后，若干交易日内禁止买回同一标的（可调）
    g.enable_stop_loss_rebuy_cooldown = True
    # 止损日期的次一交易日起计，连续 N 个交易日不得买入（默认 2：约等价于「两天内不接」）
    g.stop_loss_rebuy_cooldown_trade_days = 2
    # 仅统计此时刻之前的止损（应与 afternoon_routine 时间一致，默认 13:10）
    g.stop_loss_rebuy_cutoff_time = '13:10'
    g.stop_loss_rebuy_first_allowed_date = {}  # code -> 首个允许再买回的交易日 date
    # 动量上限软处理（默认关闭）：
    # 当动量分超过 max_score_threshold 时，不直接剔除，而是用“排序分”降权参与排序
    g.enable_momentum_soft_cap = False
    g.momentum_soft_cap_penalty = 0.05  # 排序分=max + (raw-max)*penalty
    g.momentum_soft_cap_normal_only = True
    # 防御切换确认（默认关闭）：
    # 当日无排名结果且目标为防御ETF时，需要连续 N 个交易日信号成立才切换
    g.enable_defensive_switch_confirm = False
    g.defensive_switch_confirm_days = 2
    g.defensive_switch_pending_streak = 0
    g.defensive_switch_last_signal_date = None
    
    # 市场状态逐指数明细日志开关（默认关闭，避免 log.txt 过长）
    g.log_market_status_details = False

    if register_schedules:
        set_benchmark("510300.XSHG")
        run_daily(morning_routine, time='09:00')
        run_daily(drawdown_monitor_routine, time=getattr(g, 'dd_monitor_time', '10:31'))
        run_daily(check_weak_period_daily, time='09:40')
        run_daily(afternoon_routine, time='13:09')
        run_daily(reset_daily_flags, time='15:10')
        run_daily(minute_level_stop_loss, time='every_bar')
        run_daily(minute_level_pct_stop_loss, time='every_bar')
# 注册：在回测最后一天收盘后执行
        run_daily(record_daily_positions_to_storage, time='15:30')  # 每天记录到缓存
        run_daily(after_close_regime_statistics, time='after_close')  # 收盘后更新状态累计天数与收益（收盘净值）
        run_daily(output_all_positions_summary, time='after_close')  # 最后一天汇总输出

def check_weak_period_daily(context):
    resolve_market_regime(context)
    midday_routine(context)


def drawdown_monitor_routine(context):
    """组合回撤：在连续竞价后执行，用场内 last_price 估值（见 g.dd_valuation_use_mtm_last_price）。"""
    log.info("★" * 40)
    log.info(f"▶️ 【回撤监控·盘中】{context.current_dt.strftime('%H:%M')} 启动…")
    monitor_drawdown(context)
    log.info("⏸️ 【回撤监控·盘中】执行完毕！")


def morning_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【晨间流水线】启动...")
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)
    log.info(
        f"【回撤监控】已移至盘中定时任务（默认 {getattr(g, 'dd_monitor_time', '10:31')}），"
        "避免开盘前无连续竞价价；QDII/LOF 请以该时点场内价口径为准。"
    )
    if getattr(g, 'log_pool_update_details', False):
        log.info("【流动性阈值】计算全市场ETF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("⏸️ 【晨间流水线】执行完毕！")


def refresh_holdings_num_by_regime(context):
    regime = getattr(g, 'market_regime', '震荡期')
    prev = int(getattr(g, 'holdings_num', 1))
    target_map = {
        '正常期': int(getattr(g, 'holdings_num_normal', prev)),
        '震荡期': int(getattr(g, 'holdings_num_oscillation', prev)),
        '走弱期': int(getattr(g, 'holdings_num_weak', prev)),
    }
    new_holdings = max(1, target_map.get(regime, prev))
    g.holdings_num = new_holdings
    if new_holdings != prev:
        log.info(f"🧭 【持仓数切换】状态={regime}，holdings_num: {prev} → {new_holdings}")
    else:
        log.info(f"🧭 【持仓数】状态={regime}，holdings_num={new_holdings}")


def midday_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【早盘流水线】启动...")
    
    if g.market_regime == '走弱期':
        log.info(f"🔴 【走弱期池更新】仅对全球/海外ETF池进行流动性过滤...")
        filter_global_pool_by_volume(context)
        log.info(f"【走弱期池更新完成】过滤后全球池: {len(g.filtered_global_pool)}只")
    else:
        log.info(f"🟢 【{g.market_regime}池更新】执行动态池更新、固定池过滤、合并池...")
        if getattr(g, 'log_pool_update_details', False):
            log.info("【动态池更新】更新行业ETF动态池（各行业流动性最佳ETF）...")
        update_sector_pool(context)
        if getattr(g, 'log_pool_update_details', False):
            log.info("【固定池过滤】过滤固定ETF池流动性...")
        filter_fixed_pool_by_volume(context)
        if getattr(g, 'log_pool_update_details', False):
            log.info("【合并池】合并固定池与动态池...")
        daily_merge_etf_pools(context)
        log.info(f"【{g.market_regime}池更新完成】合并池: {len(g.merged_etf_pool)}只")
    
    log.info("⏸️ 【早盘流水线】执行完毕！")


def afternoon_routine(context):
    log.info("▶️ 【午盘流水线】启动...")
    log_pending_short_momentum_3up_followups(context)

    if g.market_regime == '走弱期':
        if hasattr(g, 'filtered_global_pool') and g.filtered_global_pool:
            g.merged_etf_pool = list(set(g.filtered_global_pool))
        else:
            g.merged_etf_pool = list(set(g.global_etf_pool))
        g.merged_etf_pool.sort()
        log.info(f"🔴 【走弱期】使用过滤后全球/海外ETF池，共{len(g.merged_etf_pool)}只")
    else:
        log.info(f"🟢 【{g.market_regime}】使用合并池，共{len(g.merged_etf_pool)}只")
    refresh_holdings_num_by_regime(context)
    log.info("【动量计算】计算ETF动量得分与排序...")
    calculate_and_log_ranked_etfs(context)
    log.info("【卖出执行】执行卖出操作...")
    execute_sell_trades(context)
    log.info("【买入执行】执行买入操作...")
    execute_buy_trades(context)
    log.info("⏸️ 【午盘流水线】执行完毕！")


def reset_daily_flags(context):
    g.cache_date = None
    g.yesterday_close_cache = {}
    log.info("🔄 收盘缓存重置完成")


def after_close_regime_statistics(context):
    """收盘后统计：当日归属早盘判定的市场状态，累计天数与日收益（复利因子）。"""
    update_regime_performance_stats(context)
    log_regime_performance_dashboard(context, full=False)


def check_positions(context):
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 【持仓检查】{security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")


def _drawdown_sell_closeable_keep_fraction(context, keep_fraction, exit_reason):
    """
    各持仓按「可卖股数 closeable_amount」保留 keep_fraction（0~1），其余按 100 股步长卖出。
    遵守停牌、涨跌停、T+1（仅用 closeable）。返回是否至少成交一笔。
    """
    try:
        keep_fraction = float(keep_fraction)
    except Exception:
        keep_fraction = 0.5
    keep_fraction = max(0.0, min(1.0, keep_fraction))
    current_data = get_current_data()
    any_trade = False
    for sec in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions.get(sec)
        if not pos or pos.closeable_amount <= 0:
            continue
        ca = int(pos.closeable_amount)
        if ca < 100:
            continue
        keep = int(ca * keep_fraction)
        keep = max(0, (keep // 100) * 100)
        if keep >= ca:
            keep = ca - 100
        sell_amt = ca - keep
        sell_amt = (sell_amt // 100) * 100
        if sell_amt < 100:
            continue
        try:
            cd = current_data[sec]
            if cd.paused:
                log.info(f"【组合回撤减仓】{sec} 停牌，跳过")
                continue
            lp = cd.last_price
            if lp <= 0:
                continue
            if lp >= cd.high_limit:
                log.info(f"【组合回撤减仓】{sec} 涨停，跳过")
                continue
            if lp <= cd.low_limit:
                log.info(f"【组合回撤减仓】{sec} 跌停，跳过")
                continue
        except Exception:
            continue
        order_result = order(sec, -sell_amt)
        if order_result:
            any_trade = True
            nm = get_security_name(sec)
            log.info(
                f"📉 【组合回撤减仓】{sec} {nm} 卖出 {sell_amt} 股（可卖{ca}股中保留≈{keep_fraction:.0%}），原因: {exit_reason}"
            )
    return any_trade


def _portfolio_mtm_total_value(context):
    """
    按场内 last_price 重估账户总资产（现金 + Σ last_price×股数）。
    QDII/LOF 回测里 portfolio.total_value 在盘前时点可能仍贴近昨收；连续竞价后用成交价口径更贴近真实盘中回撤。
    """
    if not getattr(g, 'dd_valuation_use_mtm_last_price', True):
        try:
            return float(context.portfolio.total_value)
        except Exception:
            return 0.0
    cd = get_current_data()
    try:
        tv_legacy = float(context.portfolio.total_value)
    except Exception:
        tv_legacy = 0.0
    stock_legacy_sum = 0.0
    repriced = 0.0
    for sec, pos in context.portfolio.positions.items():
        ta = int(getattr(pos, 'total_amount', 0) or 0)
        if ta <= 0:
            continue
        leg = float(getattr(pos, 'value', 0) or 0)
        stock_legacy_sum += leg
        try:
            lp = float(cd[sec].last_price or 0)
            if lp > 0:
                repriced += lp * ta
            else:
                repriced += leg
        except Exception:
            repriced += leg
    cash_equiv = max(0.0, tv_legacy - stock_legacy_sum)
    return cash_equiv + repriced


def monitor_drawdown(context):
    try:
        current_value = _portfolio_mtm_total_value(context)
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value <= 0:
            return
        current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
        if current_drawdown < g.drawdown_threshold:
            return

        record = {
            'date': context.current_dt.strftime('%Y-%m-%d'),
            'drawdown': current_drawdown,
            'portfolio_value': current_value,
            'max_value': g.max_portfolio_value,
            'market_regime': getattr(g, 'market_regime', ''),
        }
        positions_info = []
        for security in context.portfolio.positions:
            position = context.portfolio.positions[security]
            if position.total_amount > 0:
                security_name = get_security_name(security)
                positions_info.append(f"{security_name}:{position.total_amount}股")
        record['positions'] = positions_info
        g.drawdown_records.append(record)
        log.info(f"【回撤预警】回撤达到 {current_drawdown:.2%} (阈值: {g.drawdown_threshold:.0%})")
        log.info(f"  当前净值: {current_value:,.0f}  |  最高净值: {g.max_portfolio_value:,.0f}")
        log.info(f"  市场状态: {getattr(g, 'market_regime', '')}")
        log.info(f"  持仓: {', '.join(positions_info) if positions_info else '空仓'}")

        # ---------- 组合回撤分级动作（可选，默认关闭）----------
        if not getattr(g, 'enable_drawdown_risk_actions', False):
            return

        today = context.current_dt.date()
        if getattr(g, 'dd_action_cooldown_date', None) == today:
            return

        th_flat = float(getattr(g, 'dd_flat_threshold', 0.20))
        th_def = float(getattr(g, 'dd_switch_defensive_threshold', 0.15))
        th_half = float(getattr(g, 'dd_half_position_threshold', 0.10))
        warn = float(getattr(g, 'drawdown_threshold', 0.03))
        # 阈值链：必须 flat > defend > half > warn（half 须严格大于预警阈值，否则与「仅日志」的 3% 线重叠）
        if not (th_flat > th_def > th_half > warn):
            log.warning(
                "【组合回撤动作】阈值链不合法（需 flat>defend>half>drawdown_threshold），已跳过动作；请检查 "
                "g.dd_flat_threshold / g.dd_switch_defensive_threshold / g.dd_half_position_threshold / g.drawdown_threshold"
            )
            return

        acted = False
        exit_tag = f"组合回撤{current_drawdown:.2%}"

        if current_drawdown >= th_flat:
            log.warning(f"🛑 【组合回撤·全部清仓】{current_drawdown:.2%} ≥ {th_flat:.0%}")
            ok_any = False
            for sec in list(context.portfolio.positions.keys()):
                pos = context.portfolio.positions.get(sec)
                if pos and pos.total_amount > 0:
                    if smart_order_target_value(sec, 0, context, exit_reason=f"{exit_tag}全部清仓"):
                        ok_any = True
            acted = ok_any
        elif current_drawdown >= th_def:
            if check_defensive_etf_available(context):
                log.warning(f"🛡️ 【组合回撤·切防御清仓】{current_drawdown:.2%} ≥ {th_def:.0%}")
                def_etf = getattr(g, 'defensive_etf', None)
                ok_any = False
                for sec in list(context.portfolio.positions.keys()):
                    if sec == def_etf:
                        continue
                    pos = context.portfolio.positions.get(sec)
                    if pos and pos.total_amount > 0:
                        if smart_order_target_value(sec, 0, context, exit_reason=f"{exit_tag}切防御清仓"):
                            ok_any = True
                acted = ok_any
            else:
                log.warning(
                    f"🛡️ 【组合回撤·切防御】{current_drawdown:.2%} ≥ {th_def:.0%}，但防御ETF不可用，未执行清仓"
                )
        elif current_drawdown >= th_half:
            keep_frac = float(getattr(g, 'dd_partial_close_keep_fraction', 0.5))
            log.warning(f"⚠️ 【组合回撤·减仓】{current_drawdown:.2%} ≥ {th_half:.0%}，可卖部分保留 {keep_frac:.0%}")
            if _drawdown_sell_closeable_keep_fraction(context, keep_frac, f"{exit_tag}减仓"):
                acted = True

        if acted:
            g.dd_action_cooldown_date = today
            if getattr(g, 'dd_reset_peak_after_action', True):
                nv = _portfolio_mtm_total_value(context)
                g.max_portfolio_value = max(nv, 1.0)
                log.info(f"【组合回撤动作】已执行，冷却至次日；峰值已重置为当前净值≈{g.max_portfolio_value:,.0f}")
    except Exception as e:
        log.error(f"【回撤监控】计算异常: {e}")


def calculate_global_etf_threshold(context):
    if getattr(g, 'log_pool_update_details', False):
        log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            log.warning("未找到任何场内ETF，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        if getattr(g, 'log_pool_update_details', False):
            log.info(f"全市场ETF总数: {len(etf_list)}只")
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date, frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            log.warning("无法获取历史成交额数据，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        daily_totals = df.groupby('time')['money'].sum()
        daily_counts = df[df['money'] > 0].groupby('time')['code'].nunique()
        if getattr(g, 'log_pool_update_details', False):
            for day, money in daily_totals.items():
                count = daily_counts.get(day, 0)
                log.info(f"  {day.date()} 全市场ETF总成交额: {money/1e8:.2f}亿元 ({count}只ETF有成交)")
        if len(daily_totals) < 3:
            log.warning(f"仅有{len(daily_totals)}个有效交易日，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        div = float(getattr(g, 'global_liquidity_threshold_divisor', 20000))
        if div <= 0:
            div = 20000
        threshold = avg_total_money / div
        g.avg_etf_money_threshold = threshold
        if getattr(g, 'log_pool_update_details', False):
            log.info(
                f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF日均总成交额={avg_total_money/1e8:.2f}亿元，"
                f"分母={div:g}，阈值={threshold/1e4:.0f}万元({threshold:,.0f}元)"
            )
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000


def filter_global_pool_by_volume(context):
    log.info("【全球池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        log.info("【全球池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.global_etf_pool:
        log.info("【全球池过滤】全球池为空，跳过过滤")
        g.filtered_global_pool = []
        return
    dynamic_threshold = g.avg_etf_money_threshold
    log.info(f"【全球池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.global_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【全球池过滤】无法获取成交额数据，使用原始全球池")
            g.filtered_global_pool = g.global_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_global_pool = qualified.index.tolist()
        removed = set(g.global_etf_pool) - set(new_global_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            log.info(f"【全球池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_global_pool = new_global_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        log.info(f"【全球池过滤】保留高流动性ETF({len(new_global_pool)}只)")
    except Exception as e:
        log.warning(f"【全球池过滤】异常: {e}")
        g.filtered_global_pool = g.global_etf_pool[:]


def update_sector_pool(context):
    if getattr(g, 'log_pool_update_details', False):
        log.info("【动态池更新】开始执行")
    if g.avg_etf_money_threshold is None:
        if getattr(g, 'log_pool_update_details', False):
            log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    
    FUND_COMPANIES = sorted(list(set([
        '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华', '南方', '汇添富', '国泰', '平安',
        '银华', '天弘', '建信', '工银', '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
        '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银', '东方红', '财通', '华商',
        '国联', '永赢', '金鹰', '德邦', '创金合信', '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海',
        '华润元大', '大成', '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城', '中金', '浙商证券',
        '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航', '中融', '中邮', '中庚', '中信保诚', '中信建投',
        '中银国际', '中银证券', '九泰', '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林',
        '国联安', '国金', '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛', '长江证券', '鹏扬'
    ])), key=len, reverse=True)
    
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)
    
    SPECIAL_GROUPS = sorted([
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS科技'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创', '债券', '债汇', '债指', '债沪', '债易', '债基', '债兴', '债摩', '债', 'AAA'], key=len, reverse=True)},
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)
    
    exclude_keywords = sorted(list(set([
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ])), key=len, reverse=True)
    
    try:
        df_etf = get_all_securities(['etf'])
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"获取全市场ETF列表失败: {e}")
        return
    
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新】全市场ETF总数: {len(etf_list)}只")
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0
    
    for code in etf_list:
        try:
            name = g.etf_names_dict.get(code, str(code))
            is_special = False
            matched_group = None
            for group in SPECIAL_GROUPS:
                for kw in group['keywords']:
                    if kw in name:
                        is_special = True
                        matched_group = group['name']
                        break
                if is_special:
                    break
            is_excluded = False
            for k in exclude_keywords:
                if k in name:
                    is_excluded = True
                    excluded_count += 1
                    break
            if not is_excluded:
                if is_special:
                    special_etfs.append(code)
                    special_group_map[code] = matched_group
                else:
                    normal_etfs.append(code)
        except Exception:
            continue
    
    group_counts = {}
    for code in special_etfs:
        group_name = special_group_map.get(code, '未知')
        group_counts[group_name] = group_counts.get(group_name, 0) + 1
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新】特别组分布: {group_counts}")
        log.info(f"【动态池更新】进入特别组: {len(special_etfs)}只")
        log.info(f"【动态池更新】进入普通组: {len(normal_etfs)}只")
        log.info(f"【动态池更新】排除ETF: {excluded_count}只")
    
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold
    
    def filter_by_liquidity(etf_codes, group_name):
        if not etf_codes:
            return pd.Series(dtype=float), 0
        try:
            price_data = get_price(etf_codes, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                return pd.Series(dtype=float), len(etf_codes)
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            qualified_series = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
            filtered_out = len(etf_codes) - len(qualified_series)
            return qualified_series, filtered_out
        except Exception:
            return pd.Series(dtype=float), len(etf_codes)
    
    normal_qualified, normal_filtered_out = filter_by_liquidity(normal_etfs, "普通组")
    special_qualified, special_filtered_out = filter_by_liquidity(special_etfs, "特别组")
    normal_sorted = normal_qualified.index.tolist()
    special_sorted = special_qualified.index.tolist()
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新】特别组流动性过滤: {len(special_etfs)}→{len(special_sorted)}只")
        log.info(f"【动态池更新】普通组流动性过滤: {len(normal_etfs)}→{len(normal_sorted)}只")
    
    if not normal_sorted and not special_sorted:
        log.warning("【动态池更新】无ETF通过流动性过滤")
        g.dynamic_etf_pool = []
        return
    
    def get_remove_words_for_etf(_, is_special, matched_group_name):
        if not is_special:
            return []
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                return group['remove_words']
        return []
    
    def clean_name(original_name, is_special=False, matched_group_name=None):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        if is_special and matched_group_name:
            for word in get_remove_words_for_etf(original_name, is_special, matched_group_name):
                cleaned = cleaned.replace(word, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()
    
    normal_industry_groups = {}
    for code in normal_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            money = normal_qualified[code]
            cleaned = clean_name(original_name, is_special=False)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            if industry_key not in normal_industry_groups:
                normal_industry_groups[industry_key] = []
            normal_industry_groups[industry_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': '普通'
            })
        except Exception:
            continue
    
    special_industry_groups = {}
    for code in special_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified[code]
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = f"{matched_group}_{industry_key}"
            if group_key not in special_industry_groups:
                special_industry_groups[group_key] = []
            special_industry_groups[group_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': matched_group, 'display_group': matched_group
            })
        except Exception:
            continue
    
    final_pool_info = []
    for industry_key, items in normal_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    for group_key, items in special_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    
    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    top_100 = final_pool_info_sorted[:100]
    g.dynamic_etf_pool = [item['code'] for item in top_100]
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF")
    if getattr(g, 'log_pool_update_details', False) and len(g.dynamic_etf_pool) <= 10:
        for item in top_100[:10]:
            log.info(f"  {item['code']} {item['original_name']} 日均成交额: {item['money']/1e8:.2f}亿")


def filter_fixed_pool_by_volume(context):
    if getattr(g, 'log_pool_update_details', False):
        log.info("【固定池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        if getattr(g, 'log_pool_update_details', False):
            log.info("【固定池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.fixed_etf_pool:
        if getattr(g, 'log_pool_update_details', False):
            log.info("【固定池过滤】固定池为空，跳过过滤")
        return
    dynamic_threshold = g.avg_etf_money_threshold
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【固定池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.fixed_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【固定池过滤】无法获取成交额数据，跳过过滤")
            g.filtered_fixed_pool = g.fixed_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_fixed_pool = qualified.index.tolist()
        removed = set(g.fixed_etf_pool) - set(new_fixed_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            if getattr(g, 'log_pool_update_details', False):
                log.info(f"【固定池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_fixed_pool = new_fixed_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        if getattr(g, 'log_pool_update_details', False):
            log.info(f"【固定池过滤】保留高流动性ETF({len(new_fixed_pool)}只)")
    except Exception as e:
        log.warning(f"【固定池过滤】异常: {e}")
        g.filtered_fixed_pool = g.fixed_etf_pool[:]


def daily_merge_etf_pools(context):
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    if getattr(g, 'log_pool_update_details', False):
        log.info("【合并ETF池】开始执行")
        log.info(f"【合并池统计】固定池: {len(g.filtered_fixed_pool)}只, 动态池: {len(g.dynamic_etf_pool)}只, 合并后: {len(merged)}只")
    g.merged_etf_pool = merged


def calculate_and_log_ranked_etfs(context):
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        g.last_metrics_by_etf_code = {}
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list


def calculate_momentum_score(price_series, lookback_days):
    if len(price_series) < lookback_days + 1:
        return None, None, None
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2
    W_sum = np.sum(W)
    x_bar = np.sum(W * x) / W_sum
    y_bar = np.sum(W * y) / W_sum
    dx = x - x_bar
    dy = y - y_bar
    variance_x = np.sum(W * dx**2)
    if variance_x == 0:
        return 0, 0, 0
    slope = np.sum(W * dx * dy) / variance_x
    intercept = y_bar - slope * x_bar
    annualized_returns = math.exp(slope * 250) - 1
    y_pred = slope * x + intercept
    ss_res = np.sum(weights * (y - y_pred) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2) 
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    momentum_score = annualized_returns * r_squared
    return momentum_score, annualized_returns, r_squared


def _whipsaw_global_period_ok():
    if not getattr(g, 'whipsaw_options_only_in_range', True):
        return True
    return getattr(g, 'market_regime', '震荡期') == '震荡期'


def _use_smoothed_momentum_prices():
    if not getattr(g, 'enable_smoothed_momentum_input', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    if getattr(g, 'smoothed_momentum_only_in_range', True):
        return getattr(g, 'market_regime', '震荡期') == '震荡期'
    return True


def _use_range_long_momentum_limits():
    if not getattr(g, 'enable_range_momentum_floor', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    return getattr(g, 'market_regime', '震荡期') == '震荡期'


def _use_range_short_momentum_limits():
    if not getattr(g, 'enable_range_short_momentum_limits', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    return getattr(g, 'market_regime', '震荡期') == '震荡期'


def _dual_positive_filter_should_apply():
    if not getattr(g, 'enable_dual_positive_momentum', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    if getattr(g, 'dual_positive_only_in_range', True):
        return getattr(g, 'market_regime', '震荡期') == '震荡期'
    return True


def _effective_r2_threshold_whipsaw():
    base = float(getattr(g, 'r2_threshold', 0.4))
    if not getattr(g, 'enable_range_r2_veto', False):
        return base
    if not _whipsaw_global_period_ok():
        return base
    if getattr(g, 'market_regime', '震荡期') != '震荡期':
        return base
    return float(getattr(g, 'r2_threshold_range_bound', 0.9))


def _coerce_scalar_price(x):
    if x is None:
        return None
    try:
        arr = np.asarray(x, dtype=float).ravel()
        if arr.size == 0:
            return None
        return float(arr[0])
    except Exception:
        return None


def _get_intraday_price_with_fallback(context, security):
    """
    获取当前时点价格：
    1) 优先 get_current_data().last_price
    2) 回退到 1 分钟 get_price 的 close（覆盖已卖出且不在当前订阅集合的标的）
    """
    # 1) 优先 current_data
    try:
        cd = get_current_data()
        if security in cd:
            cur = _coerce_scalar_price(cd[security].last_price)
            if cur is not None and cur > 0:
                return cur
    except Exception:
        pass
    # 2) 回退到分钟收盘价
    try:
        dt = getattr(context, 'current_dt', None)
        dfm = get_price(
            security,
            end_date=dt,
            count=1,
            frequency='1m',
            fields=['close'],
            panel=False,
            skip_paused=False
        )
        if dfm is not None and not dfm.empty:
            if 'close' in dfm.columns:
                cur = _coerce_scalar_price(dfm['close'].iloc[-1])
            else:
                cur = _coerce_scalar_price(dfm.iloc[-1, -1])
            if cur is not None and cur > 0:
                return cur
    except Exception:
        pass
    return None


def _scalar_momentum_finite(v):
    """动量得分是否为有限数值（统一转为 float + math.isfinite，避免 np.isfinite 与 not 在非标量上的异常）。"""
    if v is None:
        return False
    try:
        x = float(np.asarray(v, dtype=float).ravel()[0])
        return math.isfinite(x)
    except Exception:
        return False


def build_short_momentum_3day_pattern_str(vals, eps=1e-12):
    """
    由三个递进端点上的短期动量得分生成三位模式（与 get_short_momentum_3day_pattern 约定一致：p1 p2 p2）。
    """
    if not vals or len(vals) != 3:
        return "N/A"
    if not all(_scalar_momentum_finite(v) for v in vals):
        return "N/A"
    try:
        v0 = float(np.asarray(vals[0], dtype=float).ravel()[0])
        v1 = float(np.asarray(vals[1], dtype=float).ravel()[0])
        v2 = float(np.asarray(vals[2], dtype=float).ravel()[0])
    except Exception:
        return "N/A"
    d1, d2 = v1 - v0, v2 - v1

    def _dir(d):
        if d > eps:
            return "增"
        if d < -eps:
            return "减"
        return "平"

    p1, p2 = _dir(d1), _dir(d2)
    return f"{p1}{p2}{p2}"


def snapshot_momentum_for_security(context, security):
    """卖出复盘：与持仓当日框架一致的长/短动量快照（attribute_history + 当前价）。"""
    try:
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return None
        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        need = max(g.lookback_days, short_lb)
        bars = max(need + 25, 35)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < need:
            return None
        hist = df['close'].values.astype(float)
        price_series = np.append(hist, cur)
        price_for = price_series
        if _use_smoothed_momentum_prices():
            w = max(1, int(getattr(g, 'smoothed_ma_window', 5)))
            price_for = pd.Series(price_series).rolling(window=w, min_periods=1).mean().values
        lm, lar, lr2 = calculate_momentum_score(price_for, g.lookback_days)
        sm, sar, sr2 = calculate_momentum_score(price_for, short_lb)
        return {
            'momentum_score': lm,
            'short_momentum_score': sm,
            'annualized_returns': lar,
            'short_annualized_returns': sar,
            'r_squared': lr2,
            'short_r_squared': sr2,
            'price': cur,
            'market_regime': getattr(g, 'market_regime', ''),
        }
    except Exception:
        return None


def get_short_momentum_3day_pattern(context, security):
    """
    返回短期动量近三个交易日的方向模式（如：增增增/增减增）及三个动量值。
    价格序列为日 K（仅交易日）收盘价 + 当日当前价；三个端点为连续三个交易日递进，非自然日。
    """
    try:
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return "N/A", []

        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        # 需要保证可构造「前交易日、昨交易日、今交易日(当前价)」三组短期动量输入（日 K 仅含交易日）
        bars = max(short_lb + 10, 40)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < short_lb + 4:
            return "N/A", []

        hist = df['close'].values.astype(float)
        price_series = np.append(hist, cur)

        # 三个观测点：前交易日、昨交易日、今交易日（按交易日递进；最后一根为当日盘中价）
        ends = [len(price_series) - 3, len(price_series) - 2, len(price_series) - 1]
        vals = []
        for end in ends:
            sub = price_series[:end + 1]
            if len(sub) < short_lb + 1:
                vals.append(None)
                continue
            sm, _, _ = calculate_momentum_score(sub, short_lb)
            vals.append(sm)

        if len(vals) != 3 or any(v is None for v in vals):
            return "N/A", vals
        if not all(_scalar_momentum_finite(v) for v in vals):
            return "N/A", vals
        pattern = build_short_momentum_3day_pattern_str(vals)
        return pattern, vals
    except Exception:
        return "N/A", []


def _first_trading_day_after(d):
    """严格晚于 d 的第一个交易日（d 为卖出当日）。"""
    try:
        tds = get_trade_days(start_date=d, count=60)
        if tds is None or len(tds) == 0:
            return None
        for x in tds:
            xd = x.date() if hasattr(x, 'date') else x
            if xd > d:
                return xd
        return None
    except Exception:
        return None


def get_short_momentum_last_n_endpoint_scores(context, security, n=4):
    """
    与 get_short_momentum_3day_pattern 相同口径：在最近 n 个「交易日」递进端点上计算短期动量得分。
    数据为日 K（attribute_history 1d，仅交易日）+ 当日当前价；共 n 个端点，非自然日。
    """
    try:
        n = int(n)
        if n < 1:
            return None
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return None
        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        bars = max(short_lb + n + 10, 40)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < short_lb + n + 1:
            return None
        hist = df['close'].values.astype(float)
        price_series = np.append(hist, cur)
        if len(price_series) < short_lb + n:
            return None
        vals = []
        for k in range(n):
            end = len(price_series) - n + k
            sub = price_series[:end + 1]
            if len(sub) < short_lb + 1:
                vals.append(None)
                continue
            sm, _, _ = calculate_momentum_score(sub, short_lb)
            vals.append(sm)
        if any(v is None or not _scalar_momentum_finite(v) for v in vals):
            return None
        return vals
    except Exception:
        return None


def get_long_short_momentum_last_n_endpoint_scores(context, security, n=4):
    """
    最近 n 个交易日递进端点上的长/短动量序列（与卖出复盘口径一致）：
    - 价格序列：日K收盘（交易日）+ 当日当前价
    - 每个端点都分别计算 long(lookback_days) 与 short(short_momentum_lookback)
    """
    try:
        n = int(n)
        if n < 1:
            return None
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return None
        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        long_lb = int(getattr(g, 'lookback_days', 25))
        need = max(long_lb, short_lb)
        # 放大窗口，避免因停牌/脏数据导致可用样本不足
        bars = max(need + n + 60, 120)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < need + 2:
            return None
        hist_raw = pd.to_numeric(df['close'], errors='coerce').values.astype(float)
        # 去掉非数值/非正价格点，提升序列健壮性
        hist = hist_raw[np.isfinite(hist_raw) & (hist_raw > 0)]
        if len(hist) < need + 2:
            return None
        price_series = np.append(hist, cur)
        if len(price_series) < need + 1:
            return None

        long_vals = []
        short_vals = []
        for k in range(n):
            end = len(price_series) - n + k
            sub = price_series[:end + 1]
            if len(sub) < need + 1:
                long_vals.append(None)
                short_vals.append(None)
                continue
            lm, _, _ = calculate_momentum_score(sub, long_lb)
            sm, _, _ = calculate_momentum_score(sub, short_lb)
            long_vals.append(float(np.asarray(lm).ravel()[0]) if _scalar_momentum_finite(lm) else None)
            short_vals.append(float(np.asarray(sm).ravel()[0]) if _scalar_momentum_finite(sm) else None)
        # 至少保证各自有两个可用点，便于观察趋势
        if sum(v is not None for v in long_vals) < 2 and sum(v is not None for v in short_vals) < 2:
            return None
        return {'long': long_vals, 'short': short_vals}
    except Exception:
        return None


def log_pending_short_momentum_3up_followups(context):
    """下一交易日 13:10：卖出价至本日 13:10 区间收益 + 近4个交易日端点短动量 + 当前长/短动量等。"""
    pending = getattr(g, 'pending_sm3up_sell_followups', None)
    if not pending:
        return
    today = context.current_dt.date()
    keep = []

    def _fmt_m(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v):.4f}"

    def _fmt_pct(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v) * 100:.2f}%"

    def _fmt_nvals(vals):
        if not vals:
            return "N/A"
        return " -> ".join(_fmt_m(v) for v in vals)

    def _slope(vals):
        if not vals or len(vals) < 2:
            return None
        try:
            arr = []
            for v in vals:
                if v is None:
                    continue
                x = float(np.asarray(v, dtype=float).ravel()[0])
                if np.isfinite(x):
                    arr.append(x)
            if len(arr) < 2:
                return None
            return (arr[-1] - arr[0]) / float(len(arr) - 1)
        except Exception:
            return None

    def _risk_label(ret_pct, long_vals, short_vals):
        """
        放强追弱风险标签（经验规则）：
        - 高：次日收益显著为正，且短/长动量斜率至少一项明显上行
        - 低：次日收益显著为负，且短/长动量斜率至少一项下行
        - 其余：中
        """
        sl = _slope(short_vals)
        ll = _slope(long_vals)
        if ret_pct is None or not np.isfinite(ret_pct):
            return "未知", sl, ll, "收益缺失"
        up = (sl is not None and sl > 0.01) or (ll is not None and ll > 0.005)
        down = (sl is not None and sl < -0.01) or (ll is not None and ll < -0.005)
        if ret_pct >= 1.0 and up:
            return "高", sl, ll, "次日继续走强且动量延续上行"
        if ret_pct <= -1.0 and down:
            return "低", sl, ll, "次日回落且动量转弱"
        if ret_pct >= 1.5:
            return "高", sl, ll, "次日收益显著为正"
        if ret_pct <= -1.5:
            return "低", sl, ll, "次日收益显著为负"
        return "中", sl, ll, "信号分化或幅度不显著"

    for item in pending:
        fu = item.get('followup_date')
        if fu is None:
            continue
        if fu < today:
            log.warning(
                f"【短动量三连涨-卖出跟踪】跳过过期项 {item.get('name')}({item.get('code')})，"
                f"计划复盘日={fu} 当前={today}"
            )
            continue
        if fu > today:
            keep.append(item)
            continue
        # fu == today，在午盘 13:10 流水线中复盘
        code = item.get('code')
        name = item.get('name') or get_security_name(code)
        px0 = item.get('sell_price_1310')
        px1 = _get_intraday_price_with_fallback(context, code)
        ret_pct = float('nan')
        if px0 and px0 > 0 and px1 and px1 > 0:
            ret_pct = (px1 / float(px0) - 1.0) * 100.0
        snap = snapshot_momentum_for_security(context, code) or {}
        mom4 = get_long_short_momentum_last_n_endpoint_scores(context, code, 4) or {}
        lm4 = mom4.get('long')
        sm4 = mom4.get('short')
        sm_pat_now, sm_vals_now = get_short_momentum_3day_pattern(context, code)
        if sm_pat_now == "N/A" and isinstance(sm_vals_now, (list, tuple)) and len(sm_vals_now) == 3:
            if all(_scalar_momentum_finite(v) for v in sm_vals_now):
                _sp = build_short_momentum_3day_pattern_str(sm_vals_now)
                if _sp != "N/A":
                    sm_pat_now = _sp
        # 若三日模式函数失败，则退化为使用近4短动量末3点构造模式
        if sm_pat_now == "N/A" and sm4 and len(sm4) >= 3:
            sm_pat_now = build_short_momentum_3day_pattern_str(sm4[-3:])
            sm_vals_now = sm4[-3:]
        lm4_line = _fmt_nvals(lm4) if lm4 else "N/A"
        sm4_line = _fmt_nvals(sm4) if sm4 else "N/A"
        ret_line = f"{ret_pct:.4f}%" if np.isfinite(ret_pct) else "N/A"
        risk, slp_s, slp_l, risk_reason = _risk_label(ret_pct, lm4, sm4)
        slp_s_line = "N/A" if slp_s is None else f"{slp_s:.4f}"
        slp_l_line = "N/A" if slp_l is None else f"{slp_l:.4f}"
        log.info(
            f"\n{'=' * 72}\n"
            f"📈 【短动量三连涨-卖出跟踪】下一交易日 13:10 复盘  {name}({code})\n"
            f"  卖出日: {item.get('sell_date')} 13:10  卖出价≈{_fmt_m(px0)}  原因: {item.get('exit_reason', '—')}\n"
            f"  本日 13:10 价≈{_fmt_m(px1)}  "
            f"区间收益(卖后→今13:10): {ret_line}\n"
            f"  当前 长动量={_fmt_m(snap.get('momentum_score'))}  短动量={_fmt_m(snap.get('short_momentum_score'))}  "
            f"R²={_fmt_m(snap.get('r_squared'))}  短R²={_fmt_m(snap.get('short_r_squared'))}\n"
            f"  当前 年化收益≈{_fmt_pct(snap.get('annualized_returns'))}  短期年化≈{_fmt_pct(snap.get('short_annualized_returns'))}  "
            f"市场状态={snap.get('market_regime', getattr(g, 'market_regime', '—'))}\n"
            f"  近4日(均为交易日)端点长期动量得分: {lm4_line}\n"
            f"  近4日(均为交易日)端点短期动量得分: {sm4_line}\n"
            f"  近3日(均为交易日)短期动量模式(当日视角): {sm_pat_now}  ({_fmt_nvals(sm_vals_now)})\n"
            f"  放强追弱风险标签: {risk}  |  短斜率={slp_s_line}  长斜率={slp_l_line}  |  依据: {risk_reason}\n"
            f"{'=' * 72}"
        )
    g.pending_sm3up_sell_followups = keep


def record_buy_trade_entry(context, etf_code):
    """买入成功后记录开仓快照，供卖出复盘配对。"""
    try:
        cd = get_current_data()
        px = _coerce_scalar_price(cd[etf_code].last_price) if etf_code in cd else None
        pos = context.portfolio.positions.get(etf_code)
        met = getattr(g, 'last_metrics_by_etf_code', {}).get(etf_code)
        if met is None:
            met = snapshot_momentum_for_security(context, etf_code) or {}
        g.trade_entry_open[etf_code] = {
            'code': etf_code,
            'name': get_security_name(etf_code),
            'buy_datetime': context.current_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'buy_date': str(context.current_dt.date()),
            'buy_price_last': px,
            'buy_avg_cost': float(pos.avg_cost) if pos and pos.avg_cost else None,
            'buy_amount': int(pos.total_amount) if pos else None,
            'buy_long_m': met.get('momentum_score'),
            'buy_short_m': met.get('short_momentum_score'),
            'buy_r2': met.get('r_squared'),
            'buy_regime': getattr(g, 'market_regime', ''),
            'buy_annual_ret': met.get('annualized_returns'),
        }
    except Exception as e:
        log.warning(f"【交易记录】买入快照异常 {etf_code}: {e}")


def record_etf_roundtrip_on_sell(context, security, sold_amount, avg_cost_before, sell_price, exit_reason):
    """清仓后：复盘日志 + 写入 trade_roundtrip_history。"""
    name = get_security_name(security)
    entry = getattr(g, 'trade_entry_open', {}).pop(security, None) or {}
    sell_snap = snapshot_momentum_for_security(context, security) or {}
    sell_fee = 0.0001
    cost_basis = sold_amount * avg_cost_before if avg_cost_before and sold_amount else 0.0
    proceeds = sold_amount * sell_price * (1.0 - sell_fee) if sold_amount and sell_price else 0.0
    pnl_abs = proceeds - cost_basis
    pnl_pct = (pnl_abs / cost_basis * 100.0) if cost_basis > 1e-9 else float('nan')

    buy_dt = entry.get('buy_datetime', '—')
    sell_dt = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    bl = entry.get('buy_long_m')
    bs = entry.get('buy_short_m')
    sl = sell_snap.get('momentum_score')
    ss = sell_snap.get('short_momentum_score')
    # 年化收益等额外参数（便于卖出复盘）
    buy_annual_ret = entry.get('buy_annual_ret')
    sell_annual_ret = sell_snap.get('annualized_returns')
    sell_short_annual_ret = sell_snap.get('short_annualized_returns')
    sell_sm_pattern, sell_sm_vals = get_short_momentum_3day_pattern(context, security)
    if sell_sm_pattern == "N/A" and isinstance(sell_sm_vals, (list, tuple)) and len(sell_sm_vals) == 3:
        if all(_scalar_momentum_finite(v) for v in sell_sm_vals):
            _fix_pat = build_short_momentum_3day_pattern_str(sell_sm_vals)
            if _fix_pat != "N/A":
                sell_sm_pattern = _fix_pat

    # 短动量近三个交易日连续走强（与 get_short_momentum_3day_pattern 中「增增增」一致）→ 下一交易日 13:10 复盘区间收益
    if sell_sm_pattern == "增增增":
        fu = _first_trading_day_after(context.current_dt.date())
        if fu:
            g.pending_sm3up_sell_followups.append({
                'code': security,
                'name': name,
                'sell_date': str(context.current_dt.date()),
                'sell_price_1310': float(sell_price),
                'followup_date': fu,
                'exit_reason': exit_reason,
            })
            log.info(
                f"【短动量三连涨卖出】{name}({security}) 已纳入下一交易日 13:10 区间收益跟踪 "
                f"(卖价≈{float(sell_price):.4f} 复盘日={fu})"
            )

    rec = {
        'code': security,
        'name': name,
        'buy_datetime': buy_dt,
        'sell_datetime': sell_dt,
        'buy_date': entry.get('buy_date', ''),
        'exit_reason': exit_reason,
        'buy_long_m': bl,
        'buy_short_m': bs,
        'sell_long_m': sl,
        'sell_short_m': ss,
        'buy_r2': entry.get('buy_r2'),
        'sell_r2': sell_snap.get('r_squared'),
        'buy_regime': entry.get('buy_regime'),
        'sell_regime': sell_snap.get('market_regime', getattr(g, 'market_regime', '')),
        'buy_annual_ret': buy_annual_ret,
        'sell_annual_ret': sell_annual_ret,
        'sell_short_annual_ret': sell_short_annual_ret,
        'avg_cost': avg_cost_before,
        'sell_price': sell_price,
        'sold_amount': sold_amount,
        'pnl_abs': pnl_abs,
        'pnl_pct': pnl_pct,
    }
    if not hasattr(g, 'trade_roundtrip_history'):
        g.trade_roundtrip_history = []
    g.trade_roundtrip_history.append(rec)

    def _fmt_m(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v):.4f}"

    def _fmt_pct(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v) * 100:.2f}%"

    def _fmt_3vals(vals):
        if not vals or len(vals) != 3:
            return "N/A"
        out = []
        for v in vals:
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                out.append("N/A")
            else:
                out.append(f"{float(v):.4f}")
        return " -> ".join(out)

    def _label_sm_pattern(pattern):
        """将短动量模式粗略归类为：持续走强 / 持续走弱 / 震荡。"""
        if not pattern or pattern == "N/A":
            return "未知"
        # 典型强/弱趋势：全增或全减
        if pattern.count("增") == len(pattern) and "增" in pattern:
            return "持续走强"
        if pattern.count("减") == len(pattern) and "减" in pattern:
            return "持续走弱"
        # 其他混合情况统一视为震荡
        return "震荡"

    # 当天计划买入的目标标的（用于对比：卖出标的 vs 今日买入标的）
    target_lines = []
    try:
        today_targets = list(getattr(g, 'target_etfs_list', []) or [])
    except Exception:
        today_targets = []
    if today_targets:
        ranked = getattr(g, 'ranked_etfs_result', []) or []
        ranked_map = {}
        try:
            ranked_map = {m.get('etf'): m for m in ranked if isinstance(m, dict) and m.get('etf')}
        except Exception:
            ranked_map = {}
        for t in today_targets[:max(1, int(getattr(g, 'holdings_num', 1)))]:
            t_name = get_security_name(t)
            met = ranked_map.get(t) or getattr(g, 'last_metrics_by_etf_code', {}).get(t)
            if met is None:
                met = snapshot_momentum_for_security(context, t) or {}
            # 兼容两种键名：momentum_score / short_momentum_score 与 sell_xxx 使用的 annualized_returns / r_squared
            t_lm = met.get('momentum_score')
            t_sm = met.get('short_momentum_score')
            t_r2 = met.get('r_squared')
            t_ar = met.get('annualized_returns')
            t_sar = met.get('short_annualized_returns')
            t_reg = met.get('market_regime', getattr(g, 'market_regime', ''))
            t_sm_pattern, t_sm_vals = get_short_momentum_3day_pattern(context, t)
            if t_sm_pattern == "N/A" and isinstance(t_sm_vals, (list, tuple)) and len(t_sm_vals) == 3:
                if all(_scalar_momentum_finite(v) for v in t_sm_vals):
                    _tp = build_short_momentum_3day_pattern_str(t_sm_vals)
                    if _tp != "N/A":
                        t_sm_pattern = _tp
            target_lines.append(
                f"  今日买入标的(目标): {t_name}({t})  |  长动量={_fmt_m(t_lm)}  短动量={_fmt_m(t_sm)}  "
                f"R²={_fmt_m(t_r2)}  市场状态={t_reg or '—'}  年化≈{_fmt_pct(t_ar)}  短期年化≈{_fmt_pct(t_sar)}  "
                f"短动量近三日(均为交易日)={t_sm_pattern} [{_label_sm_pattern(t_sm_pattern)}] "
                f"({_fmt_3vals(t_sm_vals)})"
            )
    else:
        target_lines.append("  今日买入标的(目标): 无（空仓/无目标）")

    log.info(
        f"\n{'=' * 72}\n"
        f"📋 【卖出复盘】{name}({security})  |  原因: {exit_reason}  |  卖出市场状态: {rec['sell_regime']}\n"
        f"  买入时间: {buy_dt}  →  卖出时间: {sell_dt}\n"
        f"  买入时 长动量={_fmt_m(bl)}  短动量={_fmt_m(bs)}  R²={_fmt_m(entry.get('buy_r2'))}  市场状态={entry.get('buy_regime', '—')}\n"
        f"  卖出时 长动量={_fmt_m(sl)}  短动量={_fmt_m(ss)}  R²={_fmt_m(sell_snap.get('r_squared'))}  市场状态={rec['sell_regime']}\n"
        f"  卖出标的短动量近三日(均为交易日): {sell_sm_pattern} [{_label_sm_pattern(sell_sm_pattern)}] "
        f"({_fmt_3vals(sell_sm_vals)})\n"
        f"{chr(10).join(target_lines)}\n"
        f"  买入时 年化收益≈{_fmt_pct(buy_annual_ret)}  卖出时 年化收益≈{_fmt_pct(sell_annual_ret)}  卖出时 短期年化≈{_fmt_pct(sell_short_annual_ret)}\n"
        f"  数量={sold_amount:.0f}  成本均价≈{avg_cost_before:.4f}  卖出价≈{sell_price:.4f}\n"
        f"  本次估算盈亏: {pnl_abs:,.2f} 元 ({pnl_pct:.2f}%)\n"
        f"  单次往返收益总结: 代码={security}, 名称={name}, 收益={pnl_abs:,.2f}元, 收益率={pnl_pct:.2f}%, "
        f"原因={exit_reason}, 买入状态={entry.get('buy_regime', '—')}, 卖出状态={rec['sell_regime']}, "
        f"买入长/短动量={_fmt_m(bl)}/{_fmt_m(bs)}, 卖出长/短动量={_fmt_m(sl)}/{_fmt_m(ss)}\n"
        f"{'=' * 72}"
    )


def log_trade_roundtrip_leaderboard(context, top_n=20):
    """单次买卖往返盈亏榜：盈利前N / 亏损前N（按估算 pnl_abs）。"""
    hist = getattr(g, 'trade_roundtrip_history', []) or []
    if not hist:
        log.info("【往返盈亏看板】尚无已完成清仓记录")
        return
    valid = [h for h in hist if h.get('pnl_abs') is not None and np.isfinite(h.get('pnl_abs', float('nan')))]
    if not valid:
        log.info("【往返盈亏看板】无有效盈亏样本")
        return
    gainers = sorted(valid, key=lambda x: x['pnl_abs'], reverse=True)[:top_n]
    losers = sorted(valid, key=lambda x: x['pnl_abs'])[:top_n]
    lines = []
    lines.append("")
    lines.append("=" * 80)
    lines.append(f"【往返盈亏看板】单次买卖一轮（共 {len(hist)} 笔），估算盈利/亏损各前 {top_n} 名")
    lines.append("-" * 80)
    lines.append(f"{'排名':<4} {'标的':<22} {'买入时间':<20} {'卖出时间':<20} {'盈亏(元)':>12} {'收益率%':>10}")
    lines.append("-" * 80)
    for i, h in enumerate(gainers, 1):
        nm = (h.get('name') or '')[:10]
        lines.append(
            f"{i:<4} {nm:<12} {str(h.get('code','')):<10} "
            f"{str(h.get('buy_datetime','')):<20} {str(h.get('sell_datetime','')):<20} "
            f"{h.get('pnl_abs', 0):>12,.2f} {h.get('pnl_pct', 0):>10.2f}"
        )
    lines.append("-" * 80)
    lines.append(f"{'排名':<4} {'标的':<22} {'买入时间':<20} {'卖出时间':<20} {'盈亏(元)':>12} {'收益率%':>10}")
    lines.append("-" * 80)
    for i, h in enumerate(losers, 1):
        nm = (h.get('name') or '')[:10]
        lines.append(
            f"{i:<4} {nm:<12} {str(h.get('code','')):<10} "
            f"{str(h.get('buy_datetime','')):<20} {str(h.get('sell_datetime','')):<20} "
            f"{h.get('pnl_abs', 0):>12,.2f} {h.get('pnl_pct', 0):>10.2f}"
        )
    lines.append("=" * 80)
    lines.append("")
    log.info("\n".join(lines))


def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    try:
        current_price = _coerce_scalar_price(current_price)
        if current_price is None or current_price <= 0:
            return None
        price_series = np.append(hist_closes, current_price)
        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        need_len = max(g.lookback_days, short_lb)
        if len(price_series) < need_len * 0.8:
            return None
        smoothed_used = False
        price_for_momentum = price_series
        if _use_smoothed_momentum_prices():
            w = max(1, int(getattr(g, 'smoothed_ma_window', 5)))
            price_for_momentum = pd.Series(price_series).rolling(window=w, min_periods=1).mean().values
            smoothed_used = True
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_for_momentum, g.lookback_days)
        if momentum_score is None:
            return None
        short_momentum_score, _, _ = calculate_momentum_score(price_for_momentum, short_lb)
        effective_r2_threshold = _effective_r2_threshold_whipsaw()
        passed_r2 = r_squared > effective_r2_threshold

        effective_min_score = float(getattr(g, 'min_score_threshold', 0))
        effective_max_score = float(getattr(g, 'max_score_threshold', 5))
        effective_short_min = float(getattr(g, 'short_momentum_min_score', 0))
        effective_short_max = float(getattr(g, 'short_momentum_max_score', 6))
        if _use_range_long_momentum_limits():
            r_lo = float(getattr(g, 'range_momentum_min', 0))
            r_hi = float(getattr(g, 'range_momentum_max', effective_max_score))
            effective_min_score = max(effective_min_score, r_lo)
            effective_max_score = min(effective_max_score, r_hi)
        if _use_range_short_momentum_limits():
            rs_lo = float(getattr(g, 'range_short_momentum_min', 0))
            rs_hi = float(getattr(g, 'range_short_momentum_max', effective_short_max))
            effective_short_min = max(effective_short_min, rs_lo)
            effective_short_max = min(effective_short_max, rs_hi)
        momentum_rank_score = momentum_score
        momentum_soft_capped = False
        soft_cap_enabled = bool(getattr(g, 'enable_momentum_soft_cap', False))
        soft_cap_normal_only = bool(getattr(g, 'momentum_soft_cap_normal_only', True))
        regime = getattr(g, 'market_regime', '震荡期')
        apply_soft_cap = soft_cap_enabled and ((not soft_cap_normal_only) or regime == '正常期')
        if apply_soft_cap and momentum_score > effective_max_score:
            penalty = float(getattr(g, 'momentum_soft_cap_penalty', 0.2))
            penalty = max(0.0, min(1.0, penalty))
            momentum_rank_score = effective_max_score + (momentum_score - effective_max_score) * penalty
            momentum_soft_capped = True
            passed_momentum = (momentum_score >= effective_min_score)
        else:
            passed_momentum = (effective_min_score <= momentum_score <= effective_max_score)
        passed_short_momentum = (
            effective_short_min <= short_momentum_score <= effective_short_max
            if short_momentum_score is not None else False)
        if _use_range_short_momentum_limits():
            passed_whipsaw_short_band = passed_short_momentum
        else:
            passed_whipsaw_short_band = True
        dual_pos_active = _dual_positive_filter_should_apply()
        passed_dual_positive = (
            (momentum_score > 0 and short_momentum_score > 0)
            if short_momentum_score is not None else False)

        volume_ratio = get_volume_ratio(hist_volumes, today_vol, context, g.volume_lookback)
        effective_volume_threshold = float(getattr(g, 'volume_threshold', 0))
        if getattr(g, 'enable_volume_threshold_buffer', False):
            effective_volume_threshold += max(0.0, float(getattr(g, 'volume_threshold_buffer', 0.0)))
        passed_volume = (volume_ratio is not None and volume_ratio < effective_volume_threshold)
        
        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False
        
        passed_ma = True
        ma_value = None
        if len(price_series) >= g.ma_lookback:
            ma_value = np.mean(price_series[-g.ma_lookback:])
            passed_ma = current_price > ma_value * g.ma_threshold
        else:
            passed_ma = False
        
        premium_rate, passed_premium = calculate_premium_rate(etf, context)
        
        laplace_value = 0
        laplace_slope = 0
        passed_laplace = False
        gaussian_value = 0.0
        gaussian_slope = 0.0
        passed_gaussian = False
        if len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                if len(laplace_values) >= 2:
                    laplace_value = laplace_values[-1]
                    laplace_slope = laplace_values[-1] - laplace_values[-2]
                    passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
                g1, g2 = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
                gaussian_value = g1
                gaussian_slope = g1 - g2
                passed_gaussian = (current_price > g1 and gaussian_slope > g.gaussian_min_slope)
            except Exception:
                pass
        
        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'momentum_rank_score': momentum_rank_score,
            'momentum_soft_capped': momentum_soft_capped,
            'short_momentum_score': short_momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'effective_r2_threshold': effective_r2_threshold,
            'effective_min_score_threshold': effective_min_score,
            'effective_max_score_threshold': effective_max_score,
            'effective_short_min_score_threshold': effective_short_min,
            'effective_short_max_score_threshold': effective_short_max,
            'passed_whipsaw_short_band': passed_whipsaw_short_band,
            'smoothed_momentum_used': smoothed_used,
            'passed_dual_positive': passed_dual_positive,
            'dual_positive_filter_active': dual_pos_active,
            'passed_short_momentum': passed_short_momentum,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'effective_volume_threshold': effective_volume_threshold,
            'day_ratios': day_ratios,
            'premium_rate': premium_rate,
            'passed_momentum': passed_momentum,
            'passed_r2': passed_r2,
            'passed_ma': passed_ma,
            'passed_volume': passed_volume,
            'passed_loss': passed_loss_filter,
            'passed_premium': passed_premium,
            'ma_value': ma_value,
            'laplace_value': laplace_value,
            'laplace_slope': laplace_slope,
            'passed_laplace': passed_laplace,
            'gaussian_value': gaussian_value,
            'gaussian_slope': gaussian_slope,
            'passed_gaussian': passed_gaussian,
        }
    except Exception as e:
        log.debug(f"【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None


def get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
    if lookback_days is None:
        lookback_days = g.volume_lookback
    try:
        if hist_volumes is None or len(hist_volumes) < lookback_days:
            return None
        past_n_days_vol = hist_volumes[-lookback_days:]
        if np.any(np.isnan(past_n_days_vol)) or np.any(past_n_days_vol == 0):
            return None
        avg_volume = np.mean(past_n_days_vol)
        if avg_volume == 0:
            return None
        now = context.current_dt
        elapsed_minutes = (now.hour - 9) * 60 + now.minute - 30
        if now.hour >= 13:
            elapsed_minutes -= 90
        elapsed_minutes = max(1, min(elapsed_minutes, 240))
        projected_today_vol = today_vol * (240.0 / elapsed_minutes)
        return projected_today_vol / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None


def calculate_premium_rate(etf, context):
    try:
        etf_price = getattr(g, 'etf_yesterday_close_batch', {}).get(etf)
        if etf_price is None or pd.isna(etf_price):
            etf_price_df = get_price(etf, start_date=context.previous_date, end_date=context.previous_date, fields=['close'])
            if etf_price_df is None or len(etf_price_df) == 0:
                return None, False
            etf_price = etf_price_df['close'].iloc[-1]
        nav = getattr(g, 'etf_yesterday_nav_batch', {}).get(etf)
        if nav is None or pd.isna(nav):
            nav_df = get_extras('unit_net_value', etf, start_date=context.previous_date, end_date=context.previous_date)
            if nav_df is None or len(nav_df) == 0:
                return None, False
            nav = nav_df.iloc[-1].values[0]
        if nav <= 0 or pd.isna(nav):
            return None, False
        premium_rate = (etf_price - nav) / nav * 100
        passed_premium = premium_rate <= g.max_premium_rate
        return premium_rate, passed_premium
    except Exception as e:
        return None, True


def laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def gaussian_filter_last_two(price, sigma=1.2):
    """震荡期高斯滤波末两点（对齐五福35）"""
    n = len(price)
    if n < 2:
        return 0.0, 0.0
    idx_1 = np.arange(n)
    weights_1 = np.exp(-((idx_1 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    weights_1 /= np.sum(weights_1)
    g1 = np.sum(price * weights_1)
    price_2 = price[:-1]
    idx_2 = np.arange(n - 1)
    weights_2 = np.exp(-((idx_2 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    weights_2 /= np.sum(weights_2)
    g2 = np.sum(price_2 * weights_2)
    return g1, g2


def resolve_market_regime(context):
    """三态判定（六指数）：①below_ma20 计数≥weak_min→走弱；②否则 above_ma10≥normal_min→正常；③其余→震荡。
    生效状态切换：指标与生效不一致时，需连续 regime_switch_confirm_days 个交易日指标口径一致才切换。

    数据口径（避免前视）：指数日线取 get_price(..., end_date=context.previous_date)，
    「当前价」= 上一交易日收盘；MA10/MA20 亦仅含完整历史日 K，不包含当日未收盘 bar。"""
    # 中证2000 官方为 932000；聚宽 convert_security 报「找不到标的」，故第六条改用国证2000 399303.XSHE（小盘广度近似）。
    indexes = {
        '沪深300': '000300.XSHG',
        '深证综指(399101)': '399101.XSHE',
        '创业板': '399006.XSHE',
        '中证A500': '000510.XSHG',
        '中证1000': '000852.XSHG',
        '国证2000(代中证2000)': '399303.XSHE',
    }
    n_index = len(indexes)
    bars_need = max(g.regime_ma20_lookback, g.normal_ma_lookback) + 1
    below_ma20 = 0
    above_ma10 = 0
    n_ok = 0
    log_details = bool(getattr(g, 'log_market_status_details', False))
    end_d = context.previous_date
    for name, code in indexes.items():
        try:
            df = get_price(
                code,
                count=bars_need,
                end_date=end_d,
                frequency='daily',
                fields=['close'],
                skip_paused=False,
            )
        except Exception as e:
            if log_details:
                log.warning(f"📊 【市场状态】{name}({code}) get_price 异常: {e}")
            df = None
        if df is None or len(df) < g.regime_ma20_lookback:
            if log_details:
                log.warning(f"📊 【市场状态】{name}({code})数据不足，跳过")
            continue
        closes = df['close'].values.astype(float)
        cur = float(closes[-1])
        ma10 = float(np.mean(closes[-g.normal_ma_lookback:]))
        ma20 = float(np.mean(closes[-g.regime_ma20_lookback:]))
        if cur < ma20:
            below_ma20 += 1
        if cur > ma10:
            above_ma10 += 1
        n_ok += 1
        st_m10 = "⬆️" if cur > ma10 else ("⬇️" if cur < ma10 else "➡️")
        st_m20 = "⬇️" if cur < ma20 else ("⬆️" if cur > ma20 else "➡️")
        if log_details:
            log.info(
                f"📊 【市场状态】{name}({code}): 昨收{cur:.2f} / MA{g.normal_ma_lookback}={ma10:.2f}{st_m10} "
                f"/ MA{g.regime_ma20_lookback}={ma20:.2f}{st_m20} (截止{end_d})"
            )
    weak_min = int(getattr(g, 'regime_weak_below_ma20_min', 6))
    normal_min = int(getattr(g, 'regime_normal_above_ma10_min', 3))
    if n_ok < n_index:
        raw_regime = '震荡期'
        if log_details:
            log.warning(f"📊 【市场状态】六指数未齐({n_ok}/{n_index})，指标口径默认震荡期")
    elif below_ma20 >= weak_min:
        raw_regime = '走弱期'
    elif above_ma10 >= normal_min:
        raw_regime = '正常期'
    else:
        raw_regime = '震荡期'

    today = context.current_dt.date()
    effective_before = getattr(g, 'market_regime', '震荡期')
    last_change = getattr(g, 'regime_last_change_date', None)
    n_need = int(getattr(g, 'regime_switch_confirm_days', 2))
    if n_need < 1:
        n_need = 1

    log.info(
        f"📊 【市场状态·指标】below_ma20={below_ma20}/{n_ok} (走弱阈值≥{weak_min}), "
        f"above_ma10={above_ma10}/{n_ok} (正常阈值≥{normal_min}) → 【{raw_regime}】"
    )

    if last_change is None:
        g.market_regime = raw_regime
        g.regime_last_change_date = today
        g.is_a_share_weak = raw_regime == '走弱期'
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
        log.info(f"📌 【状态切换】回测首日/首次：生效【{g.market_regime}】")
    elif raw_regime == effective_before:
        g.market_regime = raw_regime
        g.is_a_share_weak = raw_regime == '走弱期'
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
    elif n_need <= 1:
        g.market_regime = raw_regime
        g.regime_last_change_date = today
        g.is_a_share_weak = raw_regime == '走弱期'
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
        log.info(f"✅ 【状态切换】确认天数=1，指标切换立即生效 【{effective_before}】→【{raw_regime}】")
    else:
        pending = getattr(g, 'regime_switch_pending_raw', None)
        streak = int(getattr(g, 'regime_switch_pending_streak', 0))
        if pending == raw_regime:
            streak += 1
            g.regime_switch_pending_streak = streak
            g.regime_switch_pending_raw = raw_regime
        else:
            streak = 1
            g.regime_switch_pending_streak = 1
            g.regime_switch_pending_raw = raw_regime
            log.info(
                f"🔔 【状态切换·待确认】指标【{raw_regime}】≠ 生效【{effective_before}】，"
                f"已连续 1/{n_need} 个交易日为该指标（需连续{n_need}日一致才切换）"
            )
        if streak >= n_need:
            g.market_regime = raw_regime
            g.regime_last_change_date = today
            g.is_a_share_weak = raw_regime == '走弱期'
            g.regime_switch_pending_raw = None
            g.regime_switch_pending_streak = 0
            log.info(
                f"✅ 【状态切换·已确认】指标连续{streak}个交易日为【{raw_regime}】，"
                f"生效切换 【{effective_before}】→【{raw_regime}】"
            )
        else:
            g.market_regime = effective_before
            g.is_a_share_weak = effective_before == '走弱期'
            log.info(
                f"⏳ 【状态切换·待确认】指标【{raw_regime}】，生效仍为【{effective_before}】"
                f"（进度 {streak}/{n_need} 个交易日）"
            )

    log.info(f"📊 【市场状态·生效】→ 【{g.market_regime}】")
    record(
        正常期标记=1 if g.market_regime == '正常期' else 0,
        震荡期标记=1 if g.market_regime == '震荡期' else 0,
        走弱期标记=1 if g.market_regime == '走弱期' else 0,
    )
    log_regime_transition_chain(context)
    return g.market_regime


def log_regime_transition_chain(context):
    """打印相邻交易日状态切换；检测「隔日跳回」如 正常→震荡→正常。"""
    new = g.market_regime
    day_str = context.current_dt.strftime('%Y-%m-%d')
    prev = getattr(g, 'regime_prev_day', None)
    prev2 = getattr(g, 'regime_prev_prev_day', None)

    if prev is not None and prev2 is not None:
        if new == prev2 and new != prev:
            if not hasattr(g, 'regime_flip_flop_count'):
                g.regime_flip_flop_count = 0
            g.regime_flip_flop_count = int(g.regime_flip_flop_count) + 1
            n = g.regime_flip_flop_count
            log.info(
                f"🔀 【状态反复·隔日跳回】第{n}次（回测累计）{day_str}: {prev2} → {prev} → {new} "
                f"（首尾同为【{new}】，中间为【{prev}】）"
            )

    if prev is not None:
        if new != prev:
            log.info(f"🔁 【状态切换】{day_str}: {prev} → {new}")
        else:
            log.info(f"⏺ 【状态延续】{day_str}: 连续【{new}】")
    else:
        log.info(f"📌 【状态首日】{day_str}: 【{new}】")

    g.regime_prev_prev_day = prev
    g.regime_prev_day = new


REGIME_LABELS = ('正常期', '震荡期', '走弱期')


def _ensure_regime_stats_structures():
    """聚宽 g 上部分字段可能非原生 dict，统一为可数字累加的结构。"""
    if not isinstance(getattr(g, 'regime_day_counts', None), dict):
        g.regime_day_counts = {k: 0 for k in REGIME_LABELS}
    else:
        for k in REGIME_LABELS:
            g.regime_day_counts.setdefault(k, 0)
    if not isinstance(getattr(g, 'regime_return_factors', None), dict):
        g.regime_return_factors = {k: 1.0 for k in REGIME_LABELS}
    else:
        for k in REGIME_LABELS:
            g.regime_return_factors.setdefault(k, 1.0)
    for attr, default in (
        ('regime_win_counts', 0),
        ('regime_loss_counts', 0),
        ('regime_flat_counts', 0),
    ):
        if not isinstance(getattr(g, attr, None), dict):
            setattr(g, attr, {k: default for k in REGIME_LABELS})
        else:
            for k in REGIME_LABELS:
                getattr(g, attr).setdefault(k, default)
    for attr in ('regime_sum_pos_daily_ret', 'regime_sum_neg_daily_ret'):
        if not isinstance(getattr(g, attr, None), dict):
            setattr(g, attr, {k: 0.0 for k in REGIME_LABELS})
        else:
            for k in REGIME_LABELS:
                getattr(g, attr).setdefault(k, 0.0)


def update_regime_performance_stats(context):
    """收盘统计：本交易日归属早盘判定的市场状态，累计天数与净值复利因子。"""
    _ensure_regime_stats_structures()
    reg = getattr(g, 'market_regime', '震荡期')
    if reg not in g.regime_day_counts:
        reg = '震荡期'
    g.regime_day_counts[reg] = int(g.regime_day_counts.get(reg, 0)) + 1
    v = context.portfolio.total_value
    prev = getattr(g, 'prev_eod_portfolio_value', None)
    if prev is not None and prev > 0:
        daily_ret = (v - prev) / prev
        g.regime_return_factors[reg] = g.regime_return_factors.get(reg, 1.0) * (1.0 + daily_ret)
        if daily_ret > 0:
            g.regime_win_counts[reg] = int(g.regime_win_counts.get(reg, 0)) + 1
            g.regime_sum_pos_daily_ret[reg] = float(g.regime_sum_pos_daily_ret.get(reg, 0.0)) + daily_ret
        elif daily_ret < 0:
            g.regime_loss_counts[reg] = int(g.regime_loss_counts.get(reg, 0)) + 1
            g.regime_sum_neg_daily_ret[reg] = float(g.regime_sum_neg_daily_ret.get(reg, 0.0)) + daily_ret
        else:
            g.regime_flat_counts[reg] = int(g.regime_flat_counts.get(reg, 0)) + 1
    g.prev_eod_portfolio_value = v


def log_regime_performance_dashboard(context, full=False):
    """累计天数、复利收益、各状态日收益胜负统计与胜率（日收益仅统计有上日净值可比时）。"""
    _ensure_regime_stats_structures()
    lines = []
    total_days = sum(int(g.regime_day_counts.get(k, 0)) for k in REGIME_LABELS)
    lines.append("")
    lines.append("=" * 80)
    lines.append("【市场状态累计看板】累计交易日与各状态下策略净值复利（自回测起）")
    lines.append("=" * 80)
    lines.append(f"{'状态':<10} {'累计天数':>10} {'占比':>10} {'复利因子':>14} {'累计收益率':>14}")
    lines.append("-" * 80)
    for label in REGIME_LABELS:
        cnt = int(g.regime_day_counts.get(label, 0))
        fac = g.regime_return_factors.get(label, 1.0)
        pct = (cnt / total_days * 100) if total_days else 0.0
        cum_r = (fac - 1.0) * 100
        lines.append(f"{label:<10} {cnt:>10} {pct:>9.2f}% {fac:>14.6f} {cum_r:>13.2f}%")
    lines.append("=" * 80)
    lines.append("【日收益胜负明细】仅统计「当日相对昨日收盘净值」可比的交易日（不含回测首日）")
    lines.append(
        f"{'状态':<8} {'赢(+)':>8} {'输(-)':>8} {'平(0)':>8} "
        f"{'胜率①':>10} {'胜率②':>10} {'正日收益累加':>14} {'负日收益累加':>14}"
    )
    lines.append("-" * 80)
    lines.append("① 胜率=赢/(赢+输)  ② 胜率=赢/(赢+输+平)")
    lines.append("-" * 80)
    for label in REGIME_LABELS:
        w = int(g.regime_win_counts.get(label, 0))
        el = int(g.regime_loss_counts.get(label, 0))
        z = int(g.regime_flat_counts.get(label, 0))
        wl = w + el
        wlf = w + el + z
        rate1 = (100.0 * w / wl) if wl else float('nan')
        rate2 = (100.0 * w / wlf) if wlf else float('nan')
        sp = float(g.regime_sum_pos_daily_ret.get(label, 0.0)) * 100
        sn = float(g.regime_sum_neg_daily_ret.get(label, 0.0)) * 100
        r1s = f"{rate1:.2f}%" if wl else "  —  "
        r2s = f"{rate2:.2f}%" if wlf else "  —  "
        lines.append(
            f"{label:<8} {w:>8} {el:>8} {z:>8} {r1s:>10} {r2s:>10} {sp:>13.2f}% {sn:>13.2f}%"
        )
    flip_n = int(getattr(g, 'regime_flip_flop_count', 0))
    lines.append("-" * 80)
    lines.append(
        f"【状态切换】隔日跳回(A→B→A，首尾状态相同、中间不同) 累计次数: {flip_n}"
    )
    lines.append("=" * 80)
    lines.append(f"总交易日(状态归因): {total_days}  |  当前净值: {context.portfolio.total_value:,.2f}")
    lines.append("")
    text = "\n".join(lines)
    if full:
        log.info(text)
    else:
        parts = []
        for label in REGIME_LABELS:
            fac = g.regime_return_factors.get(label, 1.0)
            cn = int(g.regime_day_counts.get(label, 0))
            w = int(g.regime_win_counts.get(label, 0))
            el = int(g.regime_loss_counts.get(label, 0))
            zc = int(g.regime_flat_counts.get(label, 0))
            wl = w + el
            rate1 = (100.0 * w / wl) if wl else 0.0
            sp = float(g.regime_sum_pos_daily_ret.get(label, 0.0)) * 100
            sn = float(g.regime_sum_neg_daily_ret.get(label, 0.0)) * 100
            short = f"{label}(含{cn}天 复利{(fac-1)*100:.2f}% 胜{rate1:.0f}% {w}+/{el}-/{zc}0 正累{sp:.2f}% 负累{sn:.2f}%)"
            parts.append(short)
        flip_n = int(getattr(g, 'regime_flip_flop_count', 0))
        log.info("📈 【状态看板】" + " | ".join(parts) + f" || 隔日跳回累计{flip_n}次")


def apply_filters(metrics_list):
    regime = getattr(g, 'market_regime', '震荡期')
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter and regime != '走弱期'),
        ('均线', lambda m: m['passed_ma'], g.enable_ma_filter and regime == '走弱期'),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
        ('溢价率', lambda m: m['passed_premium'], g.enable_premium_filter),
        ('拉普拉斯滤波', lambda m: m['passed_laplace'], g.enable_laplace_filter and regime == '正常期'),
        ('高斯滤波', lambda m: m['passed_gaussian'], regime == '震荡期'),
        ('震荡期短期动量区间(Whipsaw)', lambda m: m.get('passed_whipsaw_short_band', True), True),
        ('长短动量双正(Whipsaw)', lambda m: (not m.get('dual_positive_filter_active', False)) or m.get('passed_dual_positive', False), True),
    ]
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered


def explain_filter_failures_for_etf(etf_code, metrics=None):
    """返回该ETF在当日过滤步骤中未通过的真实原因（含阈值与数值）。"""
    try:
        m = metrics or getattr(g, 'last_metrics_by_etf_code', {}).get(etf_code)
        if not isinstance(m, dict):
            return "无指标记录"
        regime = getattr(g, 'market_regime', '震荡期')
        reasons = []

        # 1) 动量得分区间
        if not m.get('passed_momentum', True):
            sc = m.get('momentum_score')
            lo = m.get('effective_min_score_threshold')
            hi = m.get('effective_max_score_threshold')
            reasons.append(f"动量得分不在区间[{lo:.4f},{hi:.4f}] (score={sc:.4f})" if sc is not None else "动量得分不达标")

        # 2) R² 过滤（走弱期默认不启用）
        if getattr(g, 'enable_r2_filter', False) and regime != '走弱期':
            if not m.get('passed_r2', True):
                r2 = m.get('r_squared')
                th = m.get('effective_r2_threshold', getattr(g, 'r2_threshold', None))
                if r2 is None or (isinstance(r2, float) and (np.isnan(r2) or np.isinf(r2))):
                    reasons.append("R²无效/缺失")
                else:
                    reasons.append(f"R²不足 (r2={float(r2):.3f} ≤ 阈值{float(th):.3f})" if th is not None else f"R²不足 (r2={float(r2):.3f})")

        # 3) 走弱期均线过滤
        if getattr(g, 'enable_ma_filter', False) and regime == '走弱期':
            if not m.get('passed_ma', True):
                px = m.get('current_price')
                ma = m.get('ma_value')
                th = float(getattr(g, 'ma_threshold', 1.0))
                if px is not None and ma is not None:
                    reasons.append(f"均线过滤未过 (现价{px:.3f} ≤ MA×{th:.2f}={ma*th:.3f})")
                else:
                    reasons.append("均线过滤未过")

        # 4) 成交量过滤
        if getattr(g, 'enable_volume_check', False):
            if not m.get('passed_volume', True):
                vr = m.get('volume_ratio')
                thr = float(m.get('effective_volume_threshold', getattr(g, 'volume_threshold', 0)))
                if vr is None:
                    reasons.append("成交量比值缺失/不可算")
                else:
                    reasons.append(f"成交量比值未过 (量比{float(vr):.2f} ≥ 阈值{thr:.2f}，需<{thr:.2f})")

        # 5) 短期风控（三日单日跌幅）
        if getattr(g, 'enable_loss_filter', False):
            if not m.get('passed_loss', True):
                ratios = m.get('day_ratios') or []
                min_ratio = min(ratios) if ratios else None
                loss_th = float(getattr(g, 'loss', 0))
                if min_ratio is not None:
                    reasons.append(f"短期风控未过 (近3日最差日涨跌比{float(min_ratio):.4f} < 阈值{loss_th:.4f})")
                else:
                    reasons.append("短期风控未过")

        # 6) 溢价率过滤
        if getattr(g, 'enable_premium_filter', False):
            if not m.get('passed_premium', True):
                pr = m.get('premium_rate')
                max_pr = float(getattr(g, 'max_premium_rate', 0))
                if pr is None:
                    reasons.append("溢价率缺失/不可算")
                else:
                    reasons.append(f"溢价率超阈值 (溢价{float(pr):.2f}% > {max_pr:.2f}%)")

        # 7) 正常期拉普拉斯
        if getattr(g, 'enable_laplace_filter', False) and regime == '正常期':
            if not m.get('passed_laplace', True):
                slope = m.get('laplace_slope')
                min_s = float(getattr(g, 'laplace_min_slope', 0))
                if slope is not None:
                    reasons.append(f"拉普拉斯滤波未过 (斜率{slope:.4f} ≤ 最小{min_s:.4f} 或 现价≤滤波值)")
                else:
                    reasons.append("拉普拉斯滤波未过")

        # 8) 震荡期高斯
        if regime == '震荡期':
            if not m.get('passed_gaussian', True):
                slope = m.get('gaussian_slope')
                min_s = float(getattr(g, 'gaussian_min_slope', 0))
                if slope is not None:
                    reasons.append(f"高斯滤波未过 (斜率{slope:.4f} ≤ 最小{min_s:.4f} 或 现价≤滤波值)")
                else:
                    reasons.append("高斯滤波未过")

        # 9) 震荡期短动量区间（如启用）
        if not m.get('passed_whipsaw_short_band', True):
            sms = m.get('short_momentum_score')
            lo = m.get('effective_short_min_score_threshold')
            hi = m.get('effective_short_max_score_threshold')
            if sms is not None and lo is not None and hi is not None:
                reasons.append(f"短期动量不在区间[{lo:.4f},{hi:.4f}] (short={sms:.4f})")
            else:
                reasons.append("短期动量区间未过")

        # 10) 长短动量双正（如启用）
        if m.get('dual_positive_filter_active', False) and (not m.get('passed_dual_positive', True)):
            lm = m.get('momentum_score')
            sm = m.get('short_momentum_score')
            reasons.append(f"长短动量双正未过 (长={lm:.4f} 短={sm:.4f} 需均>0)" if lm is not None and sm is not None else "长短动量双正未过")

        return "；".join(reasons) if reasons else "通过全部过滤条件"
    except Exception:
        return "过滤原因解析失败"


def _rank_in_filtered_list(filtered_list, etf_code):
    """在 filtered_list 中 1-based 名次，不在则 None。"""
    for i, m in enumerate(filtered_list):
        if m.get('etf') == etf_code:
            return i + 1
    return None


def get_final_ranked_etfs(context):
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = context.previous_date
    log.info(f"【动量得分计算】使用合并池，合计{len(etf_set)}只ETF")
    regime = getattr(g, 'market_regime', '震荡期')
    regime_show = {'正常期': '🟢 正常期', '震荡期': '🟡 震荡期', '走弱期': '🔴 走弱期'}.get(regime, regime)
    log.info(f"【当前状态】{regime_show}")
    short_lb = int(getattr(g, 'short_momentum_lookback', 21))
    lookback = max(g.lookback_days, short_lb, g.volume_lookback, g.ma_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
    safe_lookback = lookback + 20
    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        log.warning("【动量计算】无法获取历史价格数据")
        g.last_metrics_by_etf_code = {}
        return []
    g.etf_yesterday_close_batch = {}
    g.etf_yesterday_nav_batch = {}
    try:
        y_price_df = get_price(etf_set, start_date=end_date, end_date=end_date, fields=['close'], panel=False)
        if y_price_df is not None and not y_price_df.empty:
            g.etf_yesterday_close_batch = y_price_df.groupby('code')['close'].last().to_dict()
        nav_df = get_extras('unit_net_value', etf_set, start_date=end_date, end_date=end_date)
        if nav_df is not None and not nav_df.empty:
            g.etf_yesterday_nav_batch = nav_df.iloc[-1].to_dict()
    except Exception as e:
        log.warning(f"【动量计算】批量获取溢价率数据异常: {e}")
    today_vols = today_vol_df.groupby('code')['volume'].sum() if (today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)
    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')
    for etf in etf_set:
        if current_data[etf].paused:
            continue
        if etf not in close_pivot.columns:
            continue
        raw_closes = close_pivot[etf].values
        raw_volumes = volume_pivot[etf].values
        valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
        hist_closes = raw_closes[valid_mask]
        hist_volumes = raw_volumes[valid_mask]
        hist_closes = hist_closes[-lookback:]
        hist_volumes = hist_volumes[-lookback:]
        if len(hist_closes) < max(g.lookback_days, short_lb):
            continue
        etf_name = get_security_name(etf)
        current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        metrics = calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)
    g.last_metrics_by_etf_code = {m['etf']: m for m in all_metrics}
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
        rscore = item.get('momentum_rank_score', score)
        if pd.isna(rscore) or (isinstance(rscore, float) and np.isnan(rscore)):
            item['momentum_rank_score'] = float('-inf')
    all_metrics.sort(key=lambda x: x.get('momentum_rank_score', float('-inf')), reverse=True)
    log_buffer = []
    if getattr(g, 'log_first_step_ranking', False):
        log_buffer.append("")
        log_buffer.append(">>> 第一步：所有ETF按动量得分从大到小排序 <<<")
        for m in all_metrics[:100]:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
            ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
            if regime == '震荡期':
                filt_extra = f"高斯斜率: {m.get('gaussian_slope', 0):.4f} {fmt_status('', m.get('passed_gaussian', False))}"
                if getattr(g, 'log_whipsaw_filter_detail', True):
                    sms = m.get('short_momentum_score')
                    sms_s = f"{sms:.4f}" if sms is not None and not (isinstance(sms, float) and np.isnan(sms)) else "nan"
                    dp_ok = (not m.get('dual_positive_filter_active')) or m.get('passed_dual_positive', False)
                    filt_extra += f" | Whipsaw短动量:{sms_s} 双正{'✅' if dp_ok else '❌'}"
            elif regime == '正常期':
                filt_extra = f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}"
            else:
                filt_extra = f"走弱期形态滤波: 未启用（参见均线）"
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
                f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
                f"{filt_extra}"
            )
            log_buffer.append(line)
    # 先整体记录一遍「原始合并池」在各过滤条件下的通过情况，便于后续追溯某只ETF为何不在候选池
    log_buffer.append(">>> 第二步前检查：合并池中各ETF在过滤条件下的通过情况（一览） <<<")
    tmp_all = apply_filters(all_metrics, return_all=True) if 'return_all' in apply_filters.__code__.co_varnames else apply_filters(all_metrics)
    # 如果 apply_filters 支持 return_all=True，则 tmp_all 中会包含所有ETF及各 passed_xx 标记；
    # 否则退化为 filtered_list，仅能看到“已通过”的部分。
    debug_metrics = tmp_all if isinstance(tmp_all, list) else all_metrics
    for m in debug_metrics:
        try:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m.get('momentum_score', float('-inf')):.4f}" if m.get('momentum_score', float('-inf')) != float('-inf') else "nan"
            r2_v = m.get('r_squared')
            r2_str = f"{r2_v:.3f}" if r2_v is not None and not pd.isna(r2_v) else "nan"
            vol_val = f"{m.get('volume_ratio', 0):.2f}" if m.get('volume_ratio') is not None else "N/A"
            day_ratios = m.get('day_ratios') or []
            min_ratio = min(day_ratios) if day_ratios else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_v = m.get('premium_rate')
            premium_str = f"{premium_v:.2f}%" if premium_v is not None else "N/A"
            ma_val = m.get('ma_value')
            ma_str = f"MA{g.ma_lookback}: {ma_val:.2f}" if ma_val is not None else "MA:N/A"
            regime = getattr(g, 'market_regime', '震荡期')
            if regime == '震荡期':
                filt_extra = f"高斯斜率: {m.get('gaussian_slope', 0):.4f} {fmt_status('', m.get('passed_gaussian', False))}"
                if getattr(g, 'log_whipsaw_filter_detail', True):
                    sms = m.get('short_momentum_score')
                    sms_s = f"{sms:.4f}" if sms is not None and not (isinstance(sms, float) and np.isnan(sms)) else "nan"
                    dp_ok = (not m.get('dual_positive_filter_active')) or m.get('passed_dual_positive', False)
                    filt_extra += f" | Whipsaw短动量:{sms_s} 双正{'✅' if dp_ok else '❌'}"
            elif regime == '正常期':
                filt_extra = f"拉普拉斯斜率: {m.get('laplace_slope', 0):.4f} {fmt_status('', m.get('passed_laplace', False))}"
            else:
                filt_extra = f"走弱期形态滤波: 未启用（参见均线）"
            line = (
                f"{m.get('etf')} {m.get('etf_name')}: "
                f"动量得分: {fmt_status(score_str, m.get('passed_momentum', True))}，"
                f"R²: {fmt_status(r2_str, m.get('passed_r2', True))}，"
                f"均线: {fmt_status(ma_str, m.get('passed_ma', True))}，"
                f"成交量比值: {fmt_status(vol_val, m.get('passed_volume', True))}，"
                f"短期风控: {fmt_status(loss_val, m.get('passed_loss', True))}，"
                f"溢价率: {fmt_status(premium_str, m.get('passed_premium', True))}，"
                f"{filt_extra}"
            )
            log_buffer.append(line)
        except Exception:
            continue

    # 真正用于后续排序/候选池的列表仍然是 filtered_list
    filtered_list = tmp_all if isinstance(tmp_all, list) and all('passed_momentum' in d for d in tmp_all) else apply_filters(all_metrics)
    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    # 记录当日通过过滤的列表（用于卖出时精确判断“是否被过滤掉”）
    try:
        g.today_filtered_codes = [m.get('etf') for m in filtered_list if isinstance(m, dict) and m.get('etf')]
        g.today_filtered_rank_map = {m.get('etf'): (i + 1) for i, m in enumerate(filtered_list) if isinstance(m, dict) and m.get('etf')}
    except Exception:
        g.today_filtered_codes = []
        g.today_filtered_rank_map = {}
    top_10 = filtered_list[:10]
    log_buffer.append("")
    log_buffer.append(">>> 第二步：符合全部过滤条件的ETF按动量得分从大到小排序(前10名) <<<")
    if top_10:
        for m in top_10:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
            ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
            if regime == '震荡期':
                filt_extra = f"高斯斜率: {m.get('gaussian_slope', 0):.4f} {fmt_status('', m.get('passed_gaussian', False))}"
                if getattr(g, 'log_whipsaw_filter_detail', True):
                    sms = m.get('short_momentum_score')
                    sms_s = f"{sms:.4f}" if sms is not None and not (isinstance(sms, float) and np.isnan(sms)) else "nan"
                    dp_ok = (not m.get('dual_positive_filter_active')) or m.get('passed_dual_positive', False)
                    filt_extra += f" | Whipsaw短动量:{sms_s} 双正{'✅' if dp_ok else '❌'}"
            elif regime == '正常期':
                filt_extra = f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}"
            else:
                filt_extra = f"走弱期形态滤波: 未启用（参见均线）"
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
                f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
                f"{filt_extra}"
            )
            log_buffer.append(line)
    else:
        log_buffer.append("（无符合条件的ETF）")
        full_log = "\n".join(log_buffer)
        log.info(full_log)
        g.last_metrics_by_etf_code = {m['etf']: m for m in all_metrics}
        return []
    score_key = 'momentum_rank_score'
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        ratio = g.score_threshold_ratio if regime != '走弱期' else 1.0
        score_threshold = reference_score * ratio
        log_buffer.append("")
        log_buffer.append(
            f">>> 第三步：选取动量得分≥第{g.holdings_num}名({top_10[g.holdings_num - 1]['etf_name']})得分{reference_score:.4f}×{ratio}={score_threshold:.4f}的ETF <<<"
        )
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<")
        candidate_pool = top_10[:]
    # 记录当日候选池（用于卖出时精确判断“掉出候选池”）
    try:
        g.today_candidate_pool_codes = [m.get('etf') for m in candidate_pool if isinstance(m, dict) and m.get('etf')]
        g.today_candidate_score_threshold = score_threshold if 'score_threshold' in locals() else None
        g.today_candidate_reference_score = reference_score if 'reference_score' in locals() else None
        g.today_candidate_ratio = ratio if 'ratio' in locals() else None
    except Exception:
        g.today_candidate_pool_codes = []
        g.today_candidate_score_threshold = None
        g.today_candidate_reference_score = None
        g.today_candidate_ratio = None
    log_buffer.append(f"【候选池】共{len(candidate_pool)}只ETF（按动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")
    log_buffer.append("")
    log_buffer.append(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    log_buffer.append(f"当前持仓ETF：{current_holdings}")
    candidate_dict = {item['etf']: item for item in candidate_pool}

    # 注意：不在此因「非防频换适用状态」清空 streak。否则指数+冷却下常日不适用，streak 永无法累加。
    # streak 仅在防频换分支内：重返第1/换股/出池/无仓/候选池空 时清零；不适用日仅「暂停累加」。

    regime_allows_anti_churn = (
        regime == '正常期'
        or (regime == '震荡期' and getattr(g, 'oscillation_anti_churn_enabled', False))
        or (regime == '走弱期' and getattr(g, 'weak_anti_churn_enabled', False))
    )
    use_regime_anti_churn = (
        regime_allows_anti_churn and g.holdings_num >= 1 and len(candidate_pool) > 0
    )
    if not use_regime_anti_churn:
        _nr = int(getattr(g, 'normal_not_rank1_streak', 0))
        why = []
        if not regime_allows_anti_churn:
            if regime == '震荡期':
                why.append("震荡期防频换关闭(g.oscillation_anti_churn_enabled=False)")
            elif regime == '走弱期':
                why.append("走弱期防频换关闭(g.weak_anti_churn_enabled=False)")
            else:
                why.append(f"状态【{regime}】不适用防频换")
        if g.holdings_num < 1:
            why.append(f"holdings_num={g.holdings_num}")
        if len(candidate_pool) == 0:
            why.append("候选池为空")
        if why:
            log.info(
                f"【防频换】本日不执行: {'; '.join(why)}。streak 保持不重置(当前={_nr})，走原合并逻辑。"
            )
    if use_regime_anti_churn:
        max_days_single = int(getattr(g, 'normal_max_days_not_rank1', 5))
        AC = (
            '【震荡期防频换】'
            if regime == '震荡期'
            else ('【走弱期防频换】' if regime == '走弱期' else '【正常期防频换】')
        )
        rank1_etf = filtered_list[0]['etf']
        rank1_name = filtered_list[0]['etf_name']
        new_first = candidate_pool[0]
        pool_codes = set(candidate_dict.keys())
        topk = max(1, int(getattr(g, 'holdings_num', 1)))

        if g.holdings_num > 1:
            # 多持仓模式：候选池内且排名进入TopK则保留；候选池外立即替换；
            # 候选池内但排名未进TopK时，达到max_days再替换，防止频繁抖动。
            if regime == '震荡期':
                max_days = int(getattr(g, 'oscillation_max_days_not_topk', max_days_single))
            else:
                max_days = int(getattr(g, 'normal_max_days_not_topk', max_days_single))
            streaks = dict(getattr(g, 'normal_not_topk_streaks', {}) or {})
            ranked_codes = [item['etf'] for item in filtered_list]
            rank_map = {code: idx + 1 for idx, code in enumerate(ranked_codes)}
            retained = []
            must_replace = []
            watch_replace = []

            for h in current_holdings:
                if h not in pool_codes:
                    must_replace.append((h, "掉出候选池"))
                    streaks.pop(h, None)
                    continue
                r = rank_map.get(h)
                if r is None:
                    must_replace.append((h, "不在过筛排序表"))
                    streaks.pop(h, None)
                    continue
                if r <= topk:
                    retained.append(candidate_dict[h])
                    streaks[h] = 0
                else:
                    streaks[h] = int(streaks.get(h, 0)) + 1
                    watch_replace.append((h, r, streaks[h]))

            # 先保留应保留，再按规则把超出TopK且达阈值的持仓替换
            for h, r, s in watch_replace:
                if s >= max_days:
                    must_replace.append((h, f"连续{s}日未进Top{topk}"))
                    streaks.pop(h, None)
                else:
                    retained.append(candidate_dict[h])
                    log_buffer.append(
                        f"{AC}{h} 名次={r} 未进Top{topk} streak={s}/{max_days}，暂继续持有"
                    )

            if must_replace:
                rs = "；".join([f"{h}({reason})" for h, reason in must_replace])
                log_buffer.append(f"{AC}触发替换: {rs}")
                log.info(f"{AC}多持仓替换触发: {rs}")

            target_count = max(1, int(g.holdings_num))
            retained_codes = {item['etf'] for item in retained}
            fill_pool = [item for item in candidate_pool if item['etf'] not in retained_codes]
            final_result = retained + fill_pool[:max(0, target_count - len(retained))]
            final_result = final_result[:target_count]

            for item in final_result:
                streaks.setdefault(item['etf'], 0)

            # 清理不在当前持仓目标中的旧键，避免字典无限增长
            active_codes = {item['etf'] for item in final_result}
            streaks = {k: v for k, v in streaks.items() if k in active_codes}
            g.normal_not_topk_streaks = streaks
            # 单持仓变量在多持仓场景不再使用，清零避免混淆日志
            g.normal_not_rank1_streak = 0
            g.normal_streak_hold_code = None

            log_buffer.append(
                f"{AC}多持仓防频换完成：保留{len(retained)}只，最终目标{len(final_result)}/{target_count}只，TopK={topk}"
            )
            log.info(
                f"{AC}多持仓防频换: 保留{len(retained)} 目标{len(final_result)}/{target_count} TopK={topk}"
            )
        else:
            max_days = max_days_single
            H = current_holdings[0] if len(current_holdings) == 1 else (current_holdings[0] if current_holdings else None)
            rH = _rank_in_filtered_list(filtered_list, H) if H else None

            if not H:
                final_result = [new_first]
                g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = new_first['etf']
                t = f"{AC}无持仓 → 目标为候选池第1名"
                log_buffer.append(t)
                log.info(f"{t}: {new_first['etf']} {new_first['etf_name']}")
            elif H not in pool_codes or rH is None:
                reason = "掉出候选池" if H not in pool_codes else "不在过筛排序表"
                final_result = [new_first]
                g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = new_first['etf']
                t = f"{AC}立即换股({reason})：{H} → 候选池第1 {new_first['etf']} {new_first['etf_name']}"
                log_buffer.append(t)
                log.info(t)
            elif rH == 1:
                g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = H
                final_result = [candidate_dict[H]]
                t = (
                    f"{AC}持仓即为过筛动量第1名 → 继续持有 streak已清零 | "
                    f"持仓 {H} {candidate_dict[H]['etf_name']}"
                )
                log_buffer.append(t)
                log.info(t)
            else:
                if g.normal_streak_hold_code != H:
                    g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = H
                g.normal_not_rank1_streak = int(getattr(g, 'normal_not_rank1_streak', 0)) + 1
                streak = g.normal_not_rank1_streak
                log_buffer.append(
                    f"{AC}持仓在候选池内，过筛名次={rH}/第1名={rank1_etf}({rank1_name})，"
                    f"连续未登首 streak={streak}/{max_days}"
                )
                log.info(
                    f"{AC} {H} {candidate_dict[H]['etf_name']} "
                    f"名次{rH} 未登首{streak}/{max_days}天 候选池内 | 今日第1名 {rank1_etf}"
                )
                if streak >= max_days:
                    final_result = [new_first]
                    g.normal_not_rank1_streak = 0
                    g.normal_streak_hold_code = new_first['etf']
                    t = (
                        f"{AC}⭐已满{max_days}个交易日未重返第1名 → 换股为候选池第1 "
                        f"{new_first['etf']} {new_first['etf_name']}"
                    )
                    log_buffer.append(t)
                    log.info(t)
                else:
                    final_result = [candidate_dict[H]]
                    t = (
                        f"{AC}继续持有 {H} {candidate_dict[H]['etf_name']} "
                        f"（streak {streak}/{max_days}，未满不换）"
                    )
                    log_buffer.append(t)
                    log.info(t)
    else:
        anti_churn_candidate_pool_empty = (
            g.holdings_num == 1
            and len(candidate_pool) == 0
            and (
                regime == '正常期'
                or (regime == '震荡期' and getattr(g, 'oscillation_anti_churn_enabled', False))
                or (regime == '走弱期' and getattr(g, 'weak_anti_churn_enabled', False))
            )
        )
        if anti_churn_candidate_pool_empty:
            g.normal_not_rank1_streak = 0
            g.normal_streak_hold_code = None
            g.normal_not_topk_streaks = {}
            msg = "【防频换】候选池为空，回退原合并逻辑，streak已清零"
            log_buffer.append(msg)
            log.info(msg)
        retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
        log_buffer.append(f"其中存在于候选池中的持仓ETF：{[item['etf'] for item in retained]}")
        if len(retained) >= g.holdings_num:
            retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
            final_result = retained_sorted[:g.holdings_num]
            log_buffer.append(f"保留的持仓ETF数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的ETF中按动量得分取前{g.holdings_num}只作为最终目标。")
        else:
            need = g.holdings_num - len(retained)
            remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
            additional = remaining_pool[:need]
            final_result = retained + additional
            log_buffer.append(f"保留持仓ETF {len(retained)}只，还需补充{need}只。")
            if retained:
                log_buffer.append("保留的ETF（按原有顺序）：")
                for item in retained:
                    log_buffer.append(f"  {item['etf_name']}({item['etf']})")
            if additional:
                log_buffer.append("补充的ETF（按动量得分排序）：")
                for i, item in enumerate(additional):
                    log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")
    if getattr(g, 'enable_switch_hysteresis', False) and g.holdings_num == 1 and final_result:
        hs_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
        if hs_holdings:
            hs_current = hs_holdings[0]
            hs_target = final_result[0]['etf']
            if hs_current != hs_target:
                in_range = regime == '震荡期'
                hbuf = float(getattr(g, 'switch_buffer_range', 0.40)) if in_range else float(getattr(g, 'switch_buffer_normal', 0.10))
                hs_cur_metric = next((m for m in filtered_list if m['etf'] == hs_current), None)
                if hs_cur_metric is None:
                    hs_cur_metric = next((m for m in all_metrics if m['etf'] == hs_current), None)
                if hs_cur_metric is not None:
                    t_sc = final_result[0].get(score_key, float('-inf'))
                    c_sc = hs_cur_metric.get(score_key, float('-inf'))
                    hurdle = c_sc * (1.0 + hbuf)
                    t_nm = final_result[0].get('etf_name', hs_target)
                    c_nm = hs_cur_metric.get('etf_name', hs_current)
                    log_buffer.append(
                        f"🔎 【Whipsaw·滞回】缓冲={hbuf:.0%}({'震荡期' if in_range else '正常期'}), "
                        f"要求 {score_key}(目标)>{hurdle:.4f} (=持仓{c_sc:.4f}×(1+{hbuf:.0%}))"
                    )
                    if np.isfinite(t_sc) and np.isfinite(c_sc):
                        if t_sc <= hurdle:
                            log_buffer.append(
                                f"⏸️ 【Whipsaw·滞回】拦截换仓 → 保留 {c_nm}({hs_current})"
                            )
                            if getattr(g, 'log_whipsaw_filter_detail', True):
                                log.info(
                                    f"【Whipsaw·滞回】拦截换仓: 目标 {hs_target} {score_key}={t_sc:.4f} ≤ 门槛 {hurdle:.4f} "
                                    f"(持仓 {hs_current} {score_key}={c_sc:.4f})"
                                )
                            final_result = [hs_cur_metric]
                        else:
                            log_buffer.append(f"✅ 【Whipsaw·滞回】通过: {t_nm} {score_key}={t_sc:.4f} > {hurdle:.4f}")
                    else:
                        log_buffer.append("ℹ️ 【Whipsaw·滞回】跳过: 评分非有限值")
                else:
                    log_buffer.append(f"ℹ️ 【Whipsaw·滞回】跳过: 持仓 {hs_current} 无指标记录")
    log_buffer.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']})")
    log_buffer.append("==================================================")
    full_log = "\n".join(log_buffer)
    log.info(full_log)
    return final_result


def execute_sell_trades(context):
    log.info("========== 卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    current_positions = list(context.portfolio.positions.keys())
    current_holdings_nonzero = [s for s in current_positions if context.portfolio.positions[s].total_amount > 0]
    target_etfs = []
    # 注意：ranked_etfs_result 是“最终目标结果”，不是候选池本身；候选池与过滤名单需单独保存
    filtered_codes_today = list(getattr(g, 'today_filtered_codes', []) or [])
    candidate_codes_today = list(getattr(g, 'today_candidate_pool_codes', []) or [])
    
    if ranked_etfs:
        g.defensive_switch_pending_streak = 0
        g.defensive_switch_last_signal_date = None
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}")
    else:
        if check_defensive_etf_available(context):
            # 防御切换确认：避免单日噪声导致立刻从风险资产切防御
            if getattr(g, 'enable_defensive_switch_confirm', False):
                today = context.current_dt.date()
                if g.defensive_switch_last_signal_date != today:
                    g.defensive_switch_pending_streak = int(getattr(g, 'defensive_switch_pending_streak', 0)) + 1
                    g.defensive_switch_last_signal_date = today
                need_days = max(1, int(getattr(g, 'defensive_switch_confirm_days', 1)))
                already_defensive = (len(current_holdings_nonzero) == 1 and current_holdings_nonzero[0] == g.defensive_etf)
                if already_defensive or g.defensive_switch_pending_streak >= need_days:
                    target_etfs = [g.defensive_etf]
                    etf_name = get_security_name(g.defensive_etf)
                    log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
                else:
                    target_etfs = current_holdings_nonzero[:]
                    log.info(
                        f"🕒 防御切换确认中：{g.defensive_switch_pending_streak}/{need_days}，"
                        f"暂不切换防御ETF，维持当前持仓"
                    )
            else:
                target_etfs = [g.defensive_etf]
                etf_name = get_security_name(g.defensive_etf)
                log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
        else:
            g.defensive_switch_pending_streak = 0
            g.defensive_switch_last_signal_date = None
            log.info("💤 无最终目标(空仓模式)")
            target_etfs = []
    
    # 非动量排行场景（防御模式 / 策略空仓）的统一卖出原因前缀
    if (not ranked_etfs) and target_etfs:
        # 无排名结果但有防御标的 → 切换到防御ETF
        etf_name = get_security_name(target_etfs[0])
        base_exit_reason = f"防御模式卖出：腾出仓位切换至防御ETF {target_etfs[0]} {etf_name}（午盘清仓）"
    elif (not ranked_etfs) and (not target_etfs):
        # 今日无任何目标 → 策略选择空仓
        base_exit_reason = "策略空仓卖出：今日无目标ETF，全部持仓午盘清仓"
    else:
        base_exit_reason = ""
    
    g.target_etfs_list = target_etfs
    target_set = set(target_etfs)
    sell_count = 0
    
    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            # 针对不同场景生成更细化的卖出原因
            if ranked_etfs:
                # 正常动量调仓场景：进一步区分几种情况
                try:
                    target_desc = ", ".join(target_etfs) if target_etfs else "无"
                except Exception:
                    target_desc = "—"
                if security not in candidate_codes_today:
                    # 1) 已不在今日候选池：要进一步区分是“被过滤掉”还是“过筛但未达候选门槛/未入Top10”
                    if security not in filtered_codes_today:
                        met = getattr(g, 'last_metrics_by_etf_code', {}).get(security)
                        fail_detail = explain_filter_failures_for_etf(security, met)
                        exit_reason = (
                            "动量调仓卖出：已被第二步过滤剔除，真实原因="
                            f"{fail_detail}；不在今日目标ETF列表（今日目标: {target_desc}），且午盘清仓"
                        )
                    else:
                        met = getattr(g, 'last_metrics_by_etf_code', {}).get(security) or {}
                        sc = met.get('momentum_rank_score', met.get('momentum_score'))
                        rk = (getattr(g, 'today_filtered_rank_map', {}) or {}).get(security)
                        th = getattr(g, 'today_candidate_score_threshold', None)
                        if th is not None and sc is not None:
                            detail = f"通过过滤但未入候选池：排序分{sc:.4f} < 候选门槛{th:.4f}"
                        elif rk is not None:
                            detail = f"通过过滤但未入候选池：过滤后排名第{rk}（仅Top10参与候选池）"
                        else:
                            detail = "通过过滤但未入候选池：未达到候选池入选规则"
                        exit_reason = (
                            f"动量调仓卖出：{detail}；不在今日目标ETF列表（今日目标: {target_desc}），且午盘清仓"
                        )
                else:
                    # 2) 仍在候选池，但动量排名落后，没进入前N名目标
                    exit_reason = (
                        f"动量调仓卖出：仍在今日候选池但未进入前{g.holdings_num}名目标ETF，"
                        f"今日目标: {target_desc}，且午盘清仓"
                    )
            else:
                # 防御模式 / 策略空仓 等统一使用 base_exit_reason
                exit_reason = base_exit_reason or "午盘清仓"

            success = smart_order_target_value(security, 0, context, exit_reason=exit_reason)
            if success:
                sell_count += 1
                log.info(f"✅ 已成功卖出: {security} {security_name}")
    
    log.info(f"本次共计划卖出{sell_count}只ETF。")
    log.info("========== 卖出操作完成 ==========")


def execute_buy_trades(context):
    log.info("========== 买入操作开始 ==========")
    target_etfs = g.target_etfs_list
    
    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return
    
    current_positions = set(context.portfolio.positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    etfs_to_buy = _filter_stop_loss_rebuy_cooldown(context, etfs_to_buy)
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    
    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("========== 买入操作完成 ==========")
        return
    
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标持仓: {g.holdings_num}只, 本次计划买入: {num_etfs_to_buy}只")
    
    # 修复：动态分配资金，避免可用现金为负
    for i, etf in enumerate(etfs_to_buy):
        remaining_cash = context.portfolio.available_cash
        if remaining_cash < g.min_money:
            log.info(f"可用现金 {remaining_cash:.2f} 不足最小交易额 {g.min_money:.2f}，停止买入")
            break
        
        remaining_to_buy = len(etfs_to_buy) - i
        target_value_for_this_etf = remaining_cash // remaining_to_buy
        
        # 最后一笔可使用剩余全部现金，但确保不小于最小交易额
        if target_value_for_this_etf < g.min_money and remaining_cash >= g.min_money:
            target_value_for_this_etf = remaining_cash
        
        log.info(f"为 {etf} 分配目标金额: {target_value_for_this_etf:.2f} 元 (剩余现金 {remaining_cash:.2f}, 待买数量 {remaining_to_buy})")
        
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
            record_buy_trade_entry(context, etf)
        else:
            log.info(f"❌ ETF {etf} 下单失败")
    
    log.info("========== 买入操作完成 ==========")

def smart_order_target_value(security, target_value, context, exit_reason='午盘清仓'):
    current_data = get_current_data()
    security_name = get_security_name(security)

    # ========== 1. 买入初步资金检查（仅对买入操作） ==========
    if target_value > 0:
        available_cash = context.portfolio.available_cash
        if target_value > available_cash:
            target_value = available_cash
        if target_value < g.min_money:
            log.info(f"{security} {security_name}: 目标金额{target_value:.2f}小于最小交易额{g.min_money}，跳过")
            return False

    # ========== 2. 通用交易限制 ==========
    if current_data[security].paused:
        log.info(f"{security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {security_name}: 当前涨停，跳过交易")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {security_name}: 当前跌停，跳过交易")
        return False

    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {security_name}: 当前价格为0，跳过交易")
        return False

    # ========== 3. 买入时使用预估成交价（包含佣金+滑点）计算股数 ==========
    # 佣金和滑点费率（买入方向）
    buy_commission_rate = 0.0001   # 买入佣金
    slippage_rate = 0.0001         # 滑点（价格相关滑点）
    estimated_price = current_price * (1 + buy_commission_rate + slippage_rate)
    
    if target_value > 0:
        # 用预估价格计算可买股数，确保实际花费不超可用现金
        target_amount = int(target_value / estimated_price)
        target_amount = (target_amount // 100) * 100
        if target_amount <= 0 and target_value > 0:
            target_amount = 100
        # 二次校验：用实时可用现金和当前价格严格限制（兜底）
        max_shares = int(context.portfolio.available_cash / current_price)
        max_shares = (max_shares // 100) * 100
        if max_shares < target_amount:
            log.info(f"{security} {security_name}: 现金可买{max_shares}股，原计划{target_amount}股，已调低")
            target_amount = max_shares
        if target_amount <= 0:
            log.info(f"{security} {security_name}: 现金不足买100股，跳过")
            return False
    else:
        # 卖出时不需要考虑资金，直接按目标数量0计算
        target_amount = 0

    # ========== 4. 获取当前持仓 ==========
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price

    # 小额交易过滤
    if 0 < trade_value < g.min_money:
        log.info(f"{security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过")
        return False

    # 卖出时检查可卖股数
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {security_name}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    avg_cost_before = 0.0
    if current_position and getattr(current_position, 'avg_cost', None):
        try:
            avg_cost_before = float(current_position.avg_cost)
        except Exception:
            avg_cost_before = 0.0

    # ========== 5. 执行下单 ==========
    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            if amount_diff > 0:
                log.info(f"📦 买入{security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f} (预估含成本价: {estimated_price:.3f})")
            else:
                regime_now = getattr(g, 'market_regime', '')
                regime_str = f"{regime_now}" if regime_now else "—"
                log.info(
                    f"📤 卖出{security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}，"
                    f"原因: {exit_reason}，市场状态: {regime_str}"
                )
                pos_after = context.portfolio.positions.get(security)
                amt_after = pos_after.total_amount if pos_after else 0
                if amt_after <= 0:
                    record_etf_roundtrip_on_sell(
                        context, security, float(abs(amount_diff)),
                        avg_cost_before, float(current_price), exit_reason
                    )
            return True
        else:
            log.warning(f"下单失败: {security} {security_name}，数量: {amount_diff}")
            return False
    return False


def _stop_loss_rebuy_cutoff_dt():
    s = getattr(g, 'stop_loss_rebuy_cutoff_time', '13:10')
    try:
        parts = str(s).strip().split(':')
        return dt_time(int(parts[0]), int(parts[1]))
    except Exception:
        return dt_time(13, 10)


def _first_allowed_buy_date_after_stop_loss(stop_date, cooldown_trade_days):
    """
    止损所在交易日为 D；从 D 的次一交易日起连续 cooldown_trade_days 个交易日禁止买入。
    返回首个允许买入的交易日（date）。
    """
    n = max(0, int(cooldown_trade_days))
    arr = get_trade_days(start_date=stop_date, count=n + 10)
    if len(arr) < n + 2:
        return stop_date
    first_allow = arr[n + 1]
    return first_allow.date() if hasattr(first_allow, 'date') else first_allow


def _record_stop_loss_rebuy_cooldown(context, security):
    """在分钟止损下单成功后调用：仅统计 cutoff 时间之前的止损。"""
    if not getattr(g, 'enable_stop_loss_rebuy_cooldown', False):
        return
    if context.current_dt.time() >= _stop_loss_rebuy_cutoff_dt():
        return
    stop_day = context.current_dt.date()
    n = int(getattr(g, 'stop_loss_rebuy_cooldown_trade_days', 2))
    first_allow = _first_allowed_buy_date_after_stop_loss(stop_day, n)
    if not hasattr(g, 'stop_loss_rebuy_first_allowed_date'):
        g.stop_loss_rebuy_first_allowed_date = {}
    g.stop_loss_rebuy_first_allowed_date[security] = first_allow
    log.info(
        f"📌 【止损买回冷却】登记 {security} {get_security_name(security)} "
        f"最早可买回日 {first_allow}（止损日 {stop_day}，随后禁买 {n} 个交易日）"
    )


def _filter_stop_loss_rebuy_cooldown(context, candidate_etfs):
    """买入候选中剔除仍在冷却内的标的。"""
    if not getattr(g, 'enable_stop_loss_rebuy_cooldown', False):
        return list(candidate_etfs)
    fa_map = getattr(g, 'stop_loss_rebuy_first_allowed_date', None) or {}
    today = context.current_dt.date()
    out = []
    for c in candidate_etfs:
        fa = fa_map.get(c)
        if fa is None:
            out.append(c)
            continue
        fd = fa.date() if hasattr(fa, 'date') else fa
        if today < fd:
            log.info(
                f"⏸️ 【止损买回冷却】跳过买入 {c} {get_security_name(c)}，最早允许 {fd}"
            )
            continue
        out.append(c)
    return out


def minute_level_stop_loss(context):
    if not g.use_fixed_stop_loss:
        return
    
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    
    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 【分钟级固定止损】{security} {security_name} 触发止损，亏损: {loss_percent:.2f}%")
            ok = smart_order_target_value(security, 0, context, exit_reason='分钟固定止损')
            if ok:
                _record_stop_loss_rebuy_cooldown(context, security)


def minute_level_pct_stop_loss(context):
    if not g.use_pct_stop_loss:
        return
    
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    
    current_data = get_current_data()
    current_date = context.current_dt.date()
    
    if not hasattr(g, 'cache_date') or g.cache_date != current_date:
        g.yesterday_close_cache = {}
        g.cache_date = current_date
    
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        
        yesterday_close = getattr(g, 'yesterday_close_cache', {}).get(security)
        if yesterday_close is None:
            try:
                close_series = attribute_history(security, 1, '1d', ['close'], skip_paused=False)
                if len(close_series['close']) == 0:
                    continue
                yesterday_close = close_series['close'][-1]
                if yesterday_close <= 0:
                    continue
                g.yesterday_close_cache[security] = yesterday_close
            except Exception:
                continue
        
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        
        stop_price = yesterday_close * g.pct_stop_loss_threshold
        if current_price <= stop_price:
            security_name = get_security_name(security)
            daily_loss = (current_price / yesterday_close - 1) * 100
            log.info(f"🚨 【分钟级跌幅止损】{security} {security_name} 触发止损，当日跌幅: {daily_loss:.2f}%")
            ok = smart_order_target_value(security, 0, context, exit_reason='分钟跌幅止损')
            if ok:
                _record_stop_loss_rebuy_cooldown(context, security)


def get_security_name(security):
    try:
        if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"


def check_defensive_etf_available(context):
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    if current_data[defensive_etf].paused:
        log.info(f"防御性ETF {defensive_etf} 今日停牌")
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        log.info(f"防御性ETF {defensive_etf} 当前涨停")
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        log.info(f"防御性ETF {defensive_etf} 当前跌停")
        return False
    return True


# ==================== 每日持仓成交金额（仅打印当日）====================
def record_daily_positions_to_storage(context):
    """每天15:30：仅打印当日持仓ETF的成交金额（不累积多日汇总）"""
    current_date = context.current_dt.strftime('%Y-%m-%d')
    holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    if not holdings:
        log.info(f"【持仓成交】{current_date} 无持仓")
        return
    try:
        df = get_price(holdings, start_date=current_date, end_date=current_date,
                       frequency='daily', fields=['money'], panel=False, skip_paused=True)
        for sec in holdings:
            etf_data = df[df['code'] == sec]
            turnover = etf_data['money'].iloc[-1] if not etf_data.empty else 0
            etf_name = get_security_name(sec)
            turnover_yi = turnover / 100000000
            turnover_str = f"{turnover_yi:.2f}亿"
            log.info(f"【持仓成交】{current_date} {sec} {etf_name} 当日成交金额 {turnover_str}")
    except Exception as e:
        log.error(f"【持仓成交】查询失败: {e}")


def output_all_positions_summary(context):
    """回测最后一天仅输出市场状态累计看板（不再打印多日持仓成交汇总表）"""
    end_date = context.run_params.end_date
    today = context.current_dt.date()
    if today != end_date:
        return
    log_regime_performance_dashboard(context, full=True)
    log_trade_roundtrip_leaderboard(context, top_n=20)