# Clone from JoinQuant
# postId: 554587175886848fe6e9476cbe77111d
# backtestId: 42572f97dcd52b77ef70b0d514b34a72
# title: 【创业板掘金】小市值轮动策略——年化收益超50%

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time, date, timedelta
from jqdata import finance
import traceback  # 导入traceback模块
 
def after_code_changed(context):
    now = context.current_dt.time()
    print("{0}替换了代码".format(now))
    unschedule_all()    
    # 设定基准
    set_benchmark('399101.XSHE')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(3/10000))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000, close_commission=2.5/10000, close_today_commission=0, min_commission=5), type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
     
    # 初始化全局变量 bool
    g.run_stoploss = True  # 是否进行止损
    g.filter_audit = False  # 是否筛选审计意见
    g.adjust_num = True  # 是否调整持仓数量
     
    # 全局变量list
    g.hold_list = [] # 当前持仓的全部股票    
    g.yesterday_HL_list = [] # 记录持仓中昨日涨停的股票
    g.target_list = []
    g.limitup_stocks = []   # 记录涨停的股票避免再次买入
     
    # 全局变量float/str
    g.min_mv = 10  # 股票最小市值要求
    g.max_mv = 100  # 股票最大市值要求
    g.stock_num = 4  # 持股数量
    g.stoploss_list = []  # 止损卖出列表
    g.other_sale    = []  # 其他卖出列表
    g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    g.stoploss_limit = 0.09  # 止损线
    g.stoploss_market = 0.05  # 市场趋势止损参数
    g.highest = 50  # 股票单价上限设置
     
    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    run_daily(trade_afternoon, time='14:20', reference_security='399101.XSHE') # 检查持仓中的涨停股是否需要卖出
    run_daily(stop_loss, time='10:00') # 止损函数
    run_weekly(weekly_adjustment, 3, '09:35') # 每周三:31调仓
 
# 1-1 准备股票池
def prepare_stock_list(context):
    try:
        # 获取已持有列表
        g.limitup_stocks = []
        g.hold_list = list(context.portfolio.positions.keys())
        log.info(f"当前持仓: {g.hold_list}")
        # 获取昨日涨停列表
        if g.hold_list:
            df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
            df = df[df['close'] == df['high_limit']]
            g.yesterday_HL_list = df['code'].tolist()
            log.info(f"昨日涨停股: {g.yesterday_HL_list}")
        else:
            g.yesterday_HL_list = []
    except Exception as e:
        log.error(f"prepare_stock_list error: {e}")
        traceback.print_exc()
 
# 1-2 选股模块
def get_stock_list(context):
    try:
        final_list = []
        MKT_index = '399102.XSHE'
        initial_list = filter_stocks(context, get_index_stocks(MKT_index))
        q = query(
            valuation.code,
        ).filter(
            valuation.code.in_(initial_list),
            valuation.market_cap.between(g.min_mv, g.max_mv),  # 总市值 circulating_market_cap/market_cap 单位：亿元
            income.np_parent_company_owners > 0,   # 归属于母公司所有者的净利润(元)
            income.net_profit > 0,  # 净利润(元)
            income.operating_revenue > 1e8  # 营业收入 (元)
        ).order_by(valuation.circulating_market_cap.asc()).limit(g.stock_num*3)
        df = get_fundamentals(q)
        if g.filter_audit:
            before_audit_filter = len(df)
            df['audit'] = df['code'].apply(lambda x: filter_audit(context, x))
            df_audit = df[df['audit'] == True]
            log.info(f'去除掉了存在审计问题的股票{len(df)-before_audit_filter}只')
        final_list = df['code'].tolist()
 
        if final_list:
            last_prices = history(1, unit='1d', field='close', security_list=final_list)
            return [stock for stock in final_list if stock in g.hold_list or last_prices[stock][-1] <= g.highest]
        else:
            log.info('无适合股票')
            return []
    except Exception as e:
        log.error(f"get_stock_list error: {e}")
        traceback.print_exc()
 
# 1-3 整体调整持仓
def weekly_adjustment(context):
    try:
        if g.adjust_num:
            new_num = adjust_stock_num(context)
            g.stock_num = new_num
            log.info(f'持仓数量修改为{new_num}')
        g.target_list = get_stock_list(context)[:g.stock_num]
        log.info(f"目标股票池: {g.target_list}")
 
        sell_list = [stock for stock in g.hold_list if stock not in g.target_list and stock not in g.yesterday_HL_list]
        hold_list = [stock for stock in g.hold_list if stock in g.target_list or stock in g.yesterday_HL_list]
        log.info(f"卖出: {sell_list}")
        log.info(f"已持有: {hold_list}")
 
        for stock in sell_list:
            order_target_value(stock, 0)
 
        buy_list = [stock for stock in g.target_list if stock not in g.hold_list]
        buy_security(context, buy_list, len(buy_list))
 
    except Exception as e:
        log.error(f"weekly_adjustment error: {e}")
        traceback.print_exc()
 
# 1-4 调整昨日涨停股票
def check_limit_up(context):
    try:
        now_time = context.current_dt
        if g.yesterday_HL_list != []:
            for stock in g.yesterday_HL_list:
                current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
                if current_data.iloc[0,0] < current_data.iloc[0,1]:
                    log.info(f"[{stock}]涨停打开，卖出")
                    order_target_value(stock, 0)
                    g.other_sale.append(stock)
                    g.limitup_stocks.append(stock)
                else:
                    log.info(f"[{stock}]涨停，继续持有")
    except Exception as e:
        log.error(f"check_limit_up error: {e}")
        traceback.print_exc()
 
# 1-5 如果昨天有股票卖出或者买入失败造成空仓，剩余的金额当日买入
def check_remain_amount(context):
    try:
        addstock_num = len(g.other_sale)
        loss_num = len(g.stoploss_list)
        empty_num = addstock_num + loss_num
 
        g.hold_list = list(context.portfolio.positions.keys())
        if len(g.hold_list) < g.stock_num:   
            num_stocks_to_buy = min(addstock_num, g.stock_num - len(g.hold_list))
            target_list = [stock for stock in g.target_list if stock not in g.limitup_stocks][:num_stocks_to_buy]
            log.info(f'有余额可用{round((context.portfolio.cash),2)}元。买入{target_list}')
            buy_security(context, target_list, len(target_list))
            if loss_num != 0:
                log.info(f'有余额可用{round((context.portfolio.cash),2)}元')
 
        g.stoploss_list = []
        g.other_sale    = []
    except Exception as e:
        log.error(f"check_remain_amount error: {e}")
        traceback.print_exc()
 
# 1-6 下午检查交易
def trade_afternoon(context):
    try:
        check_limit_up(context)
        check_remain_amount(context)
    except Exception as e:
        log.error(f"trade_afternoon error: {e}")
        traceback.print_exc()
 
# 1-7 止盈止损
def stop_loss(context):
    try:
        if g.run_stoploss:
            current_positions = context.portfolio.positions
            if g.stoploss_strategy == 1 or g.stoploss_strategy == 3:
                for stock in current_positions.keys():
                    price = current_positions[stock].price
                    avg_cost = current_positions[stock].avg_cost
                    if price >= avg_cost * 2:
                        order_target_value(stock, 0)
                        log.debug(f"收益100%止盈,卖出{stock}")
                        g.other_sale.append(stock)
                    elif price < avg_cost * (1 - g.stoploss_limit):
                        order_target_value(stock, 0)
                        log.debug(f"收益止损,卖出{stock}")
                        g.stoploss_list.append(stock)
 
            if g.stoploss_strategy == 2 or g.stoploss_strategy == 3:
                stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1, panel=False)
                down_ratio = (1 - stock_df['close'] / stock_df['open']).mean()
                if down_ratio >= g.stoploss_market:
                    log.debug(f"大盘惨跌,平均降幅{down_ratio:.2%}")
                    for stock in current_positions.keys():
                        order_target_value(stock, 0)
                        g.stoploss_list.append(stock)
    except Exception as e:
        log.error(f"stop_loss error: {e}")
        traceback.print_exc()
 
# 1-8 动态调仓代码
def adjust_stock_num(context):
    try:
        ma_para = 10  # 设置MA参数
        today = context.previous_date
        index_df = get_price('399101.XSHE', end_date=today, count=ma_para, fields='close', frequency='daily')
        ma = index_df['close'].mean()
        last_row = index_df['close'].iloc[-1]
        diff = last_row - ma
        result = 3 if diff >= 500 else \
                 3 if 200 <= diff < 500 else \
                 4 if -200 <= diff < 200 else \
                 5 if -500 <= diff < -200 else \
                 6
        log.info(f"diff: {diff}, num: {result}")
        return result
    except Exception as e:
        log.error(f"adjust_stock_num error: {e}")
        traceback.print_exc()
 
# 2 过滤各种股票
def filter_stocks(context, stock_list):
    try:
        current_data = get_current_data()
        last_prices = history(1, unit='1d', field='close', security_list=stock_list)  # 定义last_prices
        filtered_stocks = []
        for stock in stock_list:
            if current_data[stock].paused:
                continue
            if current_data[stock].is_st:
                continue
            if '退' in current_data[stock].name:
                continue
            if stock.startswith('68') or stock.startswith('8') or stock.startswith('4'):
                continue
            if not (stock in context.portfolio.positions or last_prices[stock][-1] < current_data[stock].high_limit):
                continue
            if not (stock in context.portfolio.positions or last_prices[stock][-1] > current_data[stock].low_limit):
                continue
            start_date = get_security_info(stock).start_date
            if context.previous_date - start_date < timedelta(days=375):
                continue
            filtered_stocks.append(stock)
        return filtered_stocks
    except Exception as e:
        log.error(f"filter_stocks error: {e}")
        traceback.print_exc()
 
# 2.1 筛选审计意见
def filter_audit(context, code):
    try:
        lstd = context.previous_date
        last_year = lstd.replace(year=lstd.year - 3, month=1, day=1)
        q = query(finance.STK_AUDIT_OPINION.code, finance.STK_AUDIT_OPINION.report_type).filter(finance.STK_AUDIT_OPINION.code==code, finance.STK_AUDIT_OPINION.pub_date>=last_year)
        df = finance.run_query(q)
        df['report_type'] = df['report_type'].astype(str)
        contains_nums = df['report_type'].str.contains(r'2|3|4|5')
        return not contains_nums.any()
    except Exception as e:
        log.error(f"filter_audit error: {e}")
        traceback.print_exc()
 
# 3-4 买入模块
def buy_security(context, target_list, num):
    try:
        position_count = len(context.portfolio.positions)
        target_num = num
        if target_num != 0:
            value = context.portfolio.cash / target_num
            for stock in target_list:
                order_target_value(stock, value)
                log.info(f"买入[{stock}]（{value}元）")
                if len(context.portfolio.positions) == g.stock_num:
                    break
    except Exception as e:
        log.error(f"buy_security error: {e}")
        traceback.print_exc()
 
def print_position_info(context):
    try:
        for position in list(context.portfolio.positions.values()):
            securities = position.security
            cost = position.avg_cost
            price = position.price
            ret = 100 * (price / cost - 1)
            value = position.value
            amount = position.total_amount    
            log.info(f'代码:{securities}')
            log.info(f'成本价:{cost:.2f}')
            log.info(f'现价:{price}')
            log.info(f'收益率:{ret:.2f}%')
            log.info(f'持仓(股):{amount}')
            log.info(f'市值:{value:.2f}')
        log.info('———————————————————————————————————————分割线————————————————————————————————')
    except Exception as e:
        log.error(f"print_position_info error: {e}")
        traceback.print_exc()