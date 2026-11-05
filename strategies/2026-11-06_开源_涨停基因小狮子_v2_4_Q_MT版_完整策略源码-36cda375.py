# Clone from JoinQuant
# postId: 36cda375ab3cc145bab4d393f77bb95e
# backtestId: 4382447a1bf1ae0fb7fa36d8854909c0
# title: 【开源】涨停基因小狮子 v2.4 Q_MT版｜完整策略源码

# 克隆自聚宽文章：https://www.joinquant.com/post/65684
# 标题：涨停基因小狮子v2.4更新626倍收益回撤降低33%
# 作者：tianyubing

# 克隆自聚宽文章：https://www.joinquant.com/post/65621
# 标题：五年达到136倍涨停基因小狮子V2.3优化利润增长100%
# 作者：tianyubing

# 克隆自聚宽文章：https://www.joinquant.com/post/65621
# 标题：五年内达到136倍涨停基因小狮子V2.3优化利润增长100%
# 作者：tianyubing

# 克隆自聚宽文章：https://www.joinquant.com/post/1399
# 标题：【量化课堂】多因子策略入门
# 作者：JoinQuant量化课堂

# 克隆自聚宽文章：https://www.joinquant.com/post/63484
# 标题：【变种小狮子】带涨停基因的股池轮动V2
# 作者：0xtao

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import datetime as dt
from datetime import timedelta

# ========== 调试：002133 筛选过程对比 ==========
DEBUG_STOCK = '002133'

def _is_debug_stock(code):
    if code is None or (isinstance(code, float) and np.isnan(code)):
        return False
    return str(code).startswith(DEBUG_STOCK) or DEBUG_STOCK in str(code)

def _find_debug_in_list(lst):
    if not lst:
        return None
    for c in lst:
        if _is_debug_stock(c):
            return c
    return None

def _debug_log_step(step, stock_list, extra=None):
    found = _find_debug_in_list(stock_list)
    msg = '[DEBUG-002133] %s: ' % step
    if found:
        msg += '通过 (code=%s)' % found
    else:
        msg += '未通过/不在池中'
    if extra:
        msg += ' | %s' % extra
    log.info(msg)


def after_code_changed(context):
    print('{0}替换了代码'.format(context.current_dt))
    # 清除/取消所有原有 run_daily() 运行任务（请注意是所有的定时任务）
    unschedule_all()
    
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设定基准
    set_benchmark('399101.XSHE')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 将滑点设置为0
    set_slippage(PriceRelatedSlippage(0.005), type="stock")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=1,
        ),
        type="stock",
    )
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    #初始化全局变量 bool
    g.no_trading_today_signal = False  # 是否为可交易日
    g.pass_april = True  # 是否四月空仓
    g.run_stoploss = True  # 是否进行止损
    #全局变量list
    g.hold_list = [] #当前持仓的全部股票    
    g.yesterday_HL_list = [] #记录持仓中昨日涨停的股票
    g.target_list = []
    g.not_buy_again = []
    #全局变量

    g.stock_num = 4
    g.max_stock_num = g.stock_num*3
        
    g.up_price = 300 # 设置股票单价 
    g.limit_days_window = 3 * 250 # 历史涨停的参考窗口期
    g.init_stock_count = 1000 # 初始股池的数量
    g.reason_to_sell = ''
    g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    g.stoploss_limit = 0.91  # 止损线
    g.stoploss_market = 0.93  # 市场趋势止损参数
    
    g.HV_control = False #新增，Ture是日频判断是否放量，False则不然
    g.HV_duration = 120 #HV_control用，周期可以是240-120-60，默认比例是0.9
    g.HV_ratio = 0.9    #HV_control用
    g.stockL = []
    # g.no_trading_buy = ['600036.XSHG','518880.XSHG','600900.XSHG']  # 空仓月份持有 
    g.no_trading_buy = []  # 空仓月份持有  TODO
    g.no_trading_hold_signal = False
    # 设置交易运行时间
    run_daily(prepare_stock_list,   time='09:05:00')
    run_weekly(weekly_sell,      2, time='10:26:00')
    run_weekly(weekly_buy,       2, time='10:27:00')
    run_daily(sell_stocks,          time='10:00:00')
    run_daily(trade_sell,           time='14:54:30')
    run_daily(trade_buy,            time='14:55:00')
    run_daily(close_account,        time='14:50:00')
    run_weekly(print_position_info, 5, time='15:10')

#1-1 准备股票池
def prepare_stock_list(context):
    #获取已持有列表
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    #获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    #判断今天是否为账户资金再平衡的日期
    g.no_trading_today_signal = today_is_between(context)


def get_history_highlimit(context, stock_list, days=3*250, p=0.10):
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close", "high_limit"],
        count=days,
        panel=False,
    )
    df = df[df["close"] == df["high_limit"]]
    grouped_result = df.groupby('code').size().reset_index(name='count')
    grouped_result = grouped_result.sort_values(by=["count"], ascending=False)
    result_list = grouped_result["code"].tolist()[:int(len(grouped_result)*p)]
    log.info('[SELECT] 涨停基因筛选: %d -> %d个有涨停 -> %d个(前10%%)' % (len(stock_list), len(grouped_result), len(result_list)))

    return result_list
    
    
def get_start_point(context, stock_list, days=3*250):
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["open", "low", "close", "high_limit"],
        count=days,
        panel=False,
    )
    stock_start_point = {}
    stock_price_bias = {}
    current_data = get_current_data()
    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        
        # 找到所有close等于high_limit的行
        limit_hit_rows = group[group['close'] == group['high_limit']]

        if not limit_hit_rows.empty:
            # 获取最近的涨停行（时间最大的）
            latest_limit_hit = limit_hit_rows.iloc[-1]
            latest_limit_index = latest_limit_hit.name
            
            # 获取该涨停行之前的所有行（按时间倒序，便于向前查找）
            previous_rows = group[group.index <= latest_limit_index].iloc[::-1]
            
            # 寻找第一个close < open的行
            target_row = None
            for idx, row in previous_rows.iterrows():
                if row['close'] < row['open']:
                    # print(code, row['time'], row['close'])
                    stock_start_point[code] = row['low']
                    break
    
    # 计算股票当前价格与历史启动点的偏移量
    for code, start_point in stock_start_point.items():
        last_price = current_data[code].last_price
        bias = last_price / start_point
        stock_price_bias[code] = bias
    
    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)

    return [i[0] for i in sorted_list]

#1-2 选股模块
def get_stock_list(context):
    log.info('[SELECT] ==> 开始选股流程')
    yesterday = context.previous_date
    initial_list = get_all_securities().index.tolist()
    log.info('[SELECT-01] 初始股票池: %d' % len(initial_list))
    _debug_log_step('SELECT-01', initial_list)
    initial_list = filter_new_stock(context, initial_list)
    log.info('[SELECT-02] 过滤次新股(<375天): %d' % len(initial_list))
    _debug_log_step('SELECT-02', initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    log.info('[SELECT-03] 过滤科创北交: %d' % len(initial_list))
    _debug_log_step('SELECT-03', initial_list)
    initial_list = filter_st_stock(initial_list)
    log.info('[SELECT-04] 过滤ST: %d' % len(initial_list))
    _debug_log_step('SELECT-04', initial_list)
    initial_list = filter_paused_stock(initial_list)
    log.info('[SELECT-05] 过滤停牌: %d' % len(initial_list))
    _debug_log_step('SELECT-05', initial_list)
    g.factor_list = [
        'price_no_fq',  # 技术指标因子 不复权价格因子
        'total_profit_to_cost_ratio',  # 质量类因子 成本费用利润率
        'inventory_turnover_rate'  # 质量类因子 存货周转率
    ]
    factor_values = get_factor_values(initial_list, [
        g.factor_list[0],
        g.factor_list[1],
        g.factor_list[2],
    ], end_date=yesterday, count=1)
    df = pd.DataFrame(index=initial_list, columns=factor_values.keys())
    df[g.factor_list[0]] = list(factor_values[g.factor_list[0]].T.iloc[:, 0])
    df[g.factor_list[1]] = list(factor_values[g.factor_list[1]].T.iloc[:, 0])
    df[g.factor_list[2]] = list(factor_values[g.factor_list[2]].T.iloc[:, 0])
    df = df.dropna()
    coef_list = [
        -6.123355346008858e-05,
        -0.002579342458393642,
        -2.194257357346814e-06
    ]  # 策略E的因子权重
    df['total_score'] = coef_list[0] * df[g.factor_list[0]] + coef_list[1] * df[g.factor_list[1]] + coef_list[2] * df[
        g.factor_list[2]]
    df = df.sort_values(by=['total_score'], ascending=False)
    complex_factor_list = list(df.index)[:int(0.1 * len(list(df.index)))]
    log.info('[SELECT-06a] 三因子打分取前10%%: %d只 (共%d只有效)' % (len(complex_factor_list), len(df)))
    # DEBUG 002133: 三因子及排名（df即将被get_fundamentals覆盖，先保存）
    factor_df = df.copy()
    debug_idx = next((i for i, c in enumerate(factor_df.index) if _is_debug_stock(c)), None)
    if debug_idx is not None:
        row = factor_df.iloc[debug_idx]
        rank_pct = (debug_idx + 1) / len(factor_df) * 100
        in_top10 = factor_df.index[debug_idx] in complex_factor_list
        log.info('[DEBUG-002133] SELECT-06a 三因子: price_no_fq=%.6f total_profit_to_cost_ratio=%.6f inventory_turnover_rate=%.6f total_score=%.6f 排名=%d/%d (%.2f%%) 入前10%%=%s' % (
            row[g.factor_list[0]], row[g.factor_list[1]], row[g.factor_list[2]], row['total_score'],
            debug_idx+1, len(factor_df), rank_pct, in_top10))
    else:
        log.info('[DEBUG-002133] SELECT-06a: 不在三因子有效池中(dropna后)')
    _debug_log_step('SELECT-06a', complex_factor_list)
    q = query(valuation.code, valuation.circulating_market_cap, indicator.eps).filter(
        valuation.code.in_(complex_factor_list)).order_by(valuation.circulating_market_cap.asc())
    df = get_fundamentals(q)
    df = df[df['eps'] > 0]
    initial_list = df['code'].tolist()[:g.init_stock_count]
    # DEBUG 002133: 流通市值+eps
    debug_mask = df['code'].apply(lambda c: _is_debug_stock(c) if pd.notna(c) else False)
    if debug_mask.any():
        r = df[debug_mask].iloc[0]
        rank = list(debug_mask).index(True) + 1
        log.info('[DEBUG-002133] SELECT-06b: eps=%.6f circulating_market_cap=%.2f 排名=%d/%d 入前1000=%s' % (
            r['eps'], r['circulating_market_cap'], rank, len(df), r['code'] in initial_list))
    else:
        log.info('[DEBUG-002133] SELECT-06b: 不在df中(可能eps<=0被过滤或不在complex_factor_list)')
    log.info('[SELECT-06b] 流通市值+eps>0取前%d只: %d' % (g.init_stock_count, len(initial_list)))
    _debug_log_step('SELECT-06b', initial_list)

    initial_list = filter_limitup_stock(context, initial_list)
    _debug_log_step('filter_limitup', initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    _debug_log_step('filter_limitdown', initial_list)
    
    initial_list = get_history_highlimit(context, initial_list, g.limit_days_window)
    log.info('[SELECT] 涨停基因筛选后: %d只' % len(initial_list))
    _debug_log_step('涨停基因筛选', initial_list)
    initial_list = get_start_point(context, initial_list, g.limit_days_window)
    log.info('[SELECT] 启动点筛选后: %d只' % len(initial_list))
    _debug_log_step('启动点筛选', initial_list)

    stock_list = get_stock_industry(initial_list)
    final_list = stock_list[:g.max_stock_num]
    final_list = list(df.code)
    _debug_log_step('最终列表', final_list)
    log.info('[SELECT] 聚宽bug：返回list(df.code)即流通市值排序列表（%d只），无行业分散' % len(final_list))
    log.info('今日前10:%s' % final_list)
    
    return final_list


#1-3 整体调整持仓
def weekly_sell(context):
    if g.no_trading_today_signal == False:
        close_no_trading_hold(context)
        log.info('=' * 80)
        log.info('[ADJUST-SELL] ===== 周二10:26 调仓-仅卖出 (%s) =====' % context.current_dt.date())
        log.info('[ADJUST-SELL] 当前持仓数量: %d' % len(g.hold_list))
        #获取应买入列表 
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.max_stock_num]
        log.info('[ADJUST-SELL] 目标池(前%d只): %s' % (len(target_list), target_list))

        #调仓卖出
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                pass
                log.info("已持有[%s]" % (stock))
        log.info('=' * 80)
        #调仓买入
        #buy_security(context,target_list)
        #记录已买入股票
        #for position in list(context.portfolio.positions.values()):
        #    stock = position.security
        #    g.not_buy_again.append(stock)

#1-3 整体调整持仓
def weekly_buy(context):
    if g.no_trading_today_signal == False:
        close_no_trading_hold(context)
        log.info('=' * 80)
        log.info('[ADJUST-BUY] ===== 周二10:27 调仓-仅买入 (%s) =====' % context.current_dt.date())
        #获取应买入列表 
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.max_stock_num]
        log.info('[ADJUST-BUY] 目标池(前%d只): %s' % (len(target_list), target_list))

        #调仓卖出
        #for stock in g.hold_list:
        #    if (stock not in target_list) and (stock not in g.yesterday_HL_list):
        #        log.info("卖出[%s]" % (stock))
        #        position = context.portfolio.positions[stock]
        #        close_position(position)
        #    else:
        #        pass
        #        log.info("已持有[%s]" % (stock))
        #调仓买入
        buy_security(context,target_list)
        #记录已买入股票
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.not_buy_again.append(stock)
        log.info('=' * 80)
            

#1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            if context.portfolio.positions[stock].closeable_amount > -100:
                current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
                if current_data.iloc[0,0] <    current_data.iloc[0,1]:
                    log.info("[%s]涨停打开，卖出" % (stock))
                    position = context.portfolio.positions[stock]
                    close_position(position)
                    g.reason_to_sell = 'limitup'
                    # g.limitup_cash += context.portfolio.positions[stock].total_amount
                    # g.limitup_number += 1
                else:
                    log.info("[%s]涨停，继续持有" % (stock))


#1-5 如果昨天有股票卖出或者买入失败，剩余的金额今天买入
def check_remain_amount(context):
    if g.reason_to_sell is 'limitup': #判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
        g.hold_list= []
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.hold_list.append(stock)
        if len(g.hold_list) < g.stock_num:
            target_list = get_stock_list(context)
            #剔除本周一曾买入的股票，不再买入
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            log.info('有余额可用'+str(round((context.portfolio.cash),2))+'元。'+ str(target_list))
            buy_security(context,target_list)
        g.reason_to_sell = ''

    else:
        # log.info('虽然有余额（'+str(round((context.portfolio.cash),2))+'元）可用，但是为止损后余额，下周再交易')
        g.reason_to_sell = ''


#1-6 下午检查交易
def trade_sell(context):
    if g.no_trading_today_signal == False:
        check_limit_up(context)
        if g.HV_control == True:
            check_high_volume(context)
        huanshou(context)
        #check_remain_amount(context)
        
        
#1-6 下午检查交易
def trade_buy(context):
    if g.no_trading_today_signal == False:
        check_limit_up(context)
        #if g.HV_control == True:
        #check_high_volume(context)
        #huanshou(context)
        check_remain_amount(context)
        
#1-7 止盈止损
def sell_stocks(context):
    if g.run_stoploss == True:
        if g.stoploss_strategy == 1:
            for stock in context.portfolio.positions.keys():
                # 股票盈利大于等于100%则卖出
                if context.portfolio.positions[stock].price >= context.portfolio.positions[stock].avg_cost * 2:
                    order_target_value(stock, 0)
                    log.debug("收益100%止盈,卖出{}".format(stock))
                # 止损
                elif context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                    order_target_value(stock, 0)
                    log.debug("收益止损,卖出{}".format(stock))
                    g.reason_to_sell = 'stoploss'
        elif g.stoploss_strategy == 2:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            #down_ratio = (stock_df['close'] / stock_df['open'] < 1).sum() / len(stock_df)
            #down_ratio = abs((stock_df['close'] / stock_df['open'] - 1).mean())
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
        elif g.stoploss_strategy == 3:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            #down_ratio = abs((stock_df['close'] / stock_df['open'] - 1).mean())
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
            else:
                for stock in context.portfolio.positions.keys():
                    if context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                        order_target_value(stock, 0)
                        log.debug("收益止损,卖出{}".format(stock))
                        g.reason_to_sell = 'stoploss'
                        

# 3-2 调整放量股票
def check_high_volume(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        if context.portfolio.positions[stock].closeable_amount ==0:
            continue
        df_volume = get_bars(stock,count=g.HV_duration,unit='1d',fields=['volume'],include_now=True, df=True)
        if df_volume['volume'].values[-1] > g.HV_ratio*df_volume['volume'].values.max():
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"[{stock}]天量，卖出, close_position: {r}")
            g.reason_to_sell is 'limitup' # TODO

            
            
#2-1 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]



#2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


#2-3 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list


#2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] <    current_data[stock].high_limit]


#2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit) 
            ]


#2-6 过滤次新股
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date <  dt.timedelta(days=375)]


#2-6.5 过滤股价
def filter_highprice_stock(context,stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] <= g.up_price]


#2-7 删除本周一买入的股票
def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]
    
    
# 获取股票所属行业
def get_stock_industry(stock):
    result = get_industry(security=stock)
    selected_stocks = []
    industry_list = []

    for stock_code, info in result.items():
        industry_name = info['sw_l2']['industry_name']
        if industry_name not in industry_list:
            industry_list.append(industry_name)
            selected_stocks.append(stock_code)
            # print(f"行业信息: {industry_name} (股票: {stock_code})")
            # 选取了 10 个不同行业的股票
            if len(industry_list) == 10 :
                break
    return selected_stocks

            
#换手率计算
def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        # 计算平均换手率
        start_date = context.current_dt - dt.timedelta(days=20)
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


# 换手检测
def huanshou(context):
    ss = []
    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit*0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount ==0:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0: continue
        r = rt / avg
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        if action:
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"{action} {stock} {get_security_info(stock).display_name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon} close_position: {r}")
            g.reason_to_sell = 'limitup'
            
            
#3-1 交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        pass
        #log.debug("Selling out %s" % (security))
    else:
        pass
        # log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)

#3-2 交易模块-开仓
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False

#3-3 交易模块-平仓
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False

#3-4 买入模块
def buy_security(context,target_list,cash=0,buy_number=0):
    #调仓买入
    position_count = len(context.portfolio.positions)
    target_num = g.stock_num
    if cash == 0:
        cash = context.portfolio.total_value #cash
    if buy_number == 0:
        buy_number = target_num
    bought_num = 0
    print('---------------------buy_number：%s'%buy_number)
    if target_num > position_count:
        value = cash / (target_num) # - position_count
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
            #if stock not in context.portfolio.positions:
                if bought_num < buy_number:
                    if open_position(stock, value):
                        # log.info("买入[%s]（%s元）" % (stock,value))
                        g.not_buy_again.append(stock) #持仓清单，后续不希望再买入
                        bought_num += 1
                        if len(context.portfolio.positions) == target_num:
                            break
    # else:
    #     value = cash / target_num
    #     for stock in target_list:
    #         if context.portfolio.positions[stock].total_amount == 0:
    #             if bought_num < buy_number:
    #                 if open_position(stock, value):
    #                     log.info("买入[%s]（%s元）" % (stock,value))
    #                     g.not_buy_again.append(stock) #持仓清单，后续不希望再买入
    #                     bought_num += 1
    #                     if len(context.portfolio.positions) == target_num:
    #                         break




#4-1 判断今天是否为四月
def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if g.pass_april is True:
        if (('04-01' <= today) and (today <= '04-30')) or (('01-01' <= today) and (today <= '01-30')):
            return True
        else:
           return False
    else:
        return False


#4-2 清仓后次日资金可转
def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0 and g.no_trading_hold_signal == False:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                if close_position(position):
                    log.info("卖出[%s]" % (stock))
                else:
                    log.info("卖出[%s]错误！！！！！" % (stock))
            buy_security(context, g.no_trading_buy)
            g.no_trading_hold_signal = True   
            

#4-3 清仓小市值不交易期间股票
def close_no_trading_hold(context):
    if g.no_trading_hold_signal == True:
        for stock in g.hold_list:
            position = context.portfolio.positions[stock]
            close_position(position)
            log.info("卖出[%s]" % (stock))
        g.no_trading_hold_signal = False



def print_position_info(context):
    print('———————————————————————————————————')
    for position in list(context.portfolio.positions.values()):
        securities=position.security
        cost=position.avg_cost
        price=position.price
        ret=100*(price/cost-1)
        value=position.value
        amount=position.total_amount    
        print('代码:{}'.format(securities))
        print('收益率:{}%'.format(format(ret,'.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value,'.2f')))
        print('———————————————————————————————————')
    print('余额:{}'.format(format(context.portfolio.cash,'.2f')))
    print('———————————————————————————————————————分割线————————————————————————————————————————')
'''#coding:gbk
"""
QMT 涨停基因小市值策略（聚宽转换版）

策略说明（与聚宽 涨停基因小市值.py 逻辑参数一致）：
1. 选股：全市场 -> 次新/科创北交/ST/停牌/止损黑名单 -> 市值排序前1000
       -> 过滤涨跌停 -> 历史涨停次数前10% -> 启动点排序 -> 行业分散取10只
2. 调仓：每周二 10:15 卖出、10:30 买入
3. 昨日涨停：下午14:20/14:55 检查，破板则卖出
4. 止损：策略3（大盘+个股联合）
5. 空仓：1月和4月空仓
6. 换手率：缩量/放量检测（可选）

版本：v1.0 (QMT转换版)
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

class G:
    pass
g = G()

def _my_hold_path():
    """策略隔离持仓文件路径"""
    try:
        base = os.path.join(_lab_root(), 'books')
        if not os.path.isdir(base):
            os.makedirs(base)
        return os.path.join(base, 'limit_gene_hold.json')
    except Exception:
        return 'limit_gene_hold.json'

def _first_run_flag_path():
    """首次实盘买入完成标志文件路径"""
    try:
        base = os.path.join(_lab_root(), 'books')
        if not os.path.isdir(base):
            os.makedirs(base)
        return os.path.join(base, 'limit_gene_first_run.json')
    except Exception:
        return 'limit_gene_first_run.json'

def load_first_run_done():
    """是否已完成首次实盘买入"""
    path = _first_run_flag_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('done', False)
        except:
            pass
    return False

def save_first_run_done():
    """标记首次实盘买入已完成"""
    path = _first_run_flag_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'done': True}, f, ensure_ascii=False)
    except Exception as e:
        print(f"[首次买入] 保存标志失败: {e}")

def load_my_hold_list():
    """加载本策略持仓 {stock: shares}"""
    path = _my_hold_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {k: int(v) for k, v in data.items() if v > 0}
        except Exception as e:
            print(f"[策略隔离] 加载持仓失败: {e}")
    return {}

def save_my_hold_list():
    """保存本策略持仓到本地"""
    path = _my_hold_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(g.my_hold_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[策略隔离] 保存持仓失败: {e}")

def get_holding_volume(C, stock):
    """本策略可认领股数，不含同账户其他策略。"""
    try:
        bm, book = _lab_book()
        _cash, real_pos = bm.account_map(g.accountid, g.acct_type)
        info = real_pos.get(stock) or {}
        if not info:
            key = str(stock or '').split('.')[0][:6]
            for k, v in real_pos.items():
                if k.split('.')[0] == key:
                    info = v
                    stock = k
                    break
        return bm.claimed_qty(book, stock, info.get('qty'))
    except Exception:
        return int((getattr(g, 'my_hold_list', {}) or {}).get(stock, 0) or 0)

def timetag_to_datetime(timetag, format='%Y%m%d'):
    """将时间戳转换为日期时间字符串"""
    try:
        if timetag:
            dt_obj = datetime.fromtimestamp(timetag / 1000)
            return dt_obj.strftime(format)
    except:
        pass
    return datetime.now().strftime(format)

def init(C):
    """策略初始化"""
    print("=" * 80)
    print("=== 涨停基因小市值策略启动 ===")
    print("=" * 80)
    
    try:
        g.accountid = account
        g.acct_type = accountType
    except:
        g.accountid = '62275766'
        g.acct_type = 'STOCK'
    
    g.buy_code = 23 if g.acct_type == 'STOCK' else 33
    g.sell_code = 24 if g.acct_type == 'STOCK' else 34
    # 策略ID（用于跟单上传，passorder 的 userOrderId 传入，主账号据此识别策略）
    g.strategy_id = '涨停基因组合'
    
    # ========== 与聚宽一致的参数 ==========
    g.no_trading_today_signal = False
    g.pass_april = True
    g.run_stoploss = True
    g.capital_pct = 0.01  # 兼容旧逻辑；实验室同账户隔离改用 10 万账本
    g.lab_capital = 100000.0
    g.hold_list = []  # 当前持仓（来自 g.my_hold_list，策略隔离）
    g.my_hold_list = {}  # 本策略持仓 {stock: shares}，持久化隔离
    g.yesterday_HL_list = []
    g.target_list = []
    g.not_buy_again = []
    g.filter_loss_black = True
    g.loss_black = {}
    g.reason_to_sell = ''
    
    g.stock_num = 6
    g.up_price = 20
    g.limit_days_window = 3 * 250
    g.init_stock_count = 1000  # 与聚宽一致，市值排序后取前N只
    g.stoploss_strategy = 3
    g.stoploss_limit = 0.91
    g.stoploss_market = 0.93
    
    g.HV_control = False
    g.HV_duration = 120
    g.HV_ratio = 0.9
    g.no_trading_buy = []
    g.no_trading_hold_signal = False
    
    # 申万二级行业（用于行业分散）
    g.sw2_industries = [
        'SW2物流', 'SW2航空机场', 'SW2航运港口', 'SW2铁路公路', 'SW2广告营销', 'SW2社交',
        'SW2电视广播', 'SW2游戏', 'SW2数字媒体', 'SW2影视院线', 'SW2出版', 'SW2燃气',
        'SW2电力', 'SW2种植业', 'SW2动物保健', 'SW2饲料', 'SW2农产品加工', 'SW2农业综合',
        'SW2渔业', 'SW2林业', 'SW2养殖业', 'SW2生物制品', 'SW2医疗器械', 'SW2医疗服务',
        'SW2中药', 'SW2医药商业', 'SW2化学制药', 'SW2航天装备', 'SW2地面兵装', 'SW2航空装备',
        'SW2军工电子', 'SW2航海装备', 'SW2白色家电', 'SW2家电零部件', 'SW2小家电', 'SW2其他家电',
        'SW2厨卫电器', 'SW2黑色家电', 'SW2照明设备', 'SW2工业金属', 'SW2能源金属', 'SW2小金属',
        'SW2贵金属', 'SW2金属新材料', 'SW2专用设备', 'SW2工程机械', 'SW2自动化设备', 'SW2通用设备',
        'SW2轨交设备', 'SW2汽车零部件', 'SW2汽车服务', 'SW2乘用车', 'SW2商用车', 'SW2摩托车及其他',
        'SW2其他电子', 'SW2元件', 'SW2光学光电子', 'SW2半导体', 'SW2消费电子', 'SW2电子化学品',
        'SW2综合', 'SW2计算机设备', 'SW2软件开发', 'SW2IT服务', 'SW2造纸', 'SW2包装印刷',
        'SW2家居用品', 'SW2文娱用品', 'SW2通信设备', 'SW2通信服务', 'SW2冶钢原料', 'SW2特钢',
        'SW2普钢', 'SW2食品加工', 'SW2白酒', 'SW2非白酒', 'SW2饮料乳品', 'SW2休闲食品',
        'SW2调味发酵品', 'SW2焦炭', 'SW2煤炭开采', 'SW2个护用品', 'SW2医疗美容', 'SW2化妆品',
        'SW2饰品', 'SW2纺织制造', 'SW2服装家纺', 'SW2酒店餐饮', 'SW2旅游及景区', 'SW2教育',
        'SW2体育', 'SW2专业服务', 'SW2本地生活服务', 'SW2油服工程', 'SW2油气开采', 'SW2炼化及贸易',
        'SW2电网设备', 'SW2电池', 'SW2光伏设备', 'SW2其他电源设备', 'SW2风电设备', 'SW2电机',
        'SW2环境治理', 'SW2环保设备', 'SW2旅游零售', 'SW2互联网电商', 'SW2专业连锁', 'SW2贸易',
        'SW2一般零售', 'SW2农化制品', 'SW2非金属材料', 'SW2化学原料', 'SW2橡胶', 'SW2化学制品',
        'SW2塑料', 'SW2化学纤维'
    ]
    
    g.last_prepare_date = None
    g.last_weekly_sell_date = None
    g.last_weekly_buy_date = None
    g.last_sell_date = None
    g.last_afternoon_1420 = None
    g.last_afternoon_1455 = None
    g.last_close_date = None
    g.current_date = None
    
    print(f"\n=== 策略配置 ===")
    print(f"持股数量: {g.stock_num}只")
    print(f"股票单价上限: {g.up_price}元")
    print(f"涨停基因窗口: {g.limit_days_window}天")
    print(f"初始股池: {g.init_stock_count}只")
    print(f"止损策略: {g.stoploss_strategy} (3=大盘+个股联合)")
    print(f"个股止损: {(1-g.stoploss_limit)*100:.0f}%")
    print(f"大盘止损: {(1-g.stoploss_market)*100:.0f}%")
    print(f"空仓月份: 1月、4月")
    print(f"调仓: 每周二 10:15卖出 10:30买入")
    print(f"策略可用资金: 同账户隔离账本 {getattr(g,'lab_capital',100000):.0f}元")
    # 策略隔离：加载本策略持仓，仅操作本策略买入的股票
    g.my_hold_list = load_my_hold_list()
    try:
        _sync_hold_from_book()
    except Exception:
        pass
    if g.my_hold_list:
        print(f"[策略隔离] 已加载本策略持仓 {len(g.my_hold_list)} 只: {list(g.my_hold_list.keys())}")
    print(f"[策略隔离] 持久化: {_my_hold_path()}")
    # 首次实盘买入：空仓时直接选股买入（与小市值买三支票一致）
    g.first_run_buy_done = load_first_run_done()
    print("\n策略初始化完成\n")
    if not getattr(C, 'do_back_test', False):
        try:
            st = (datetime.now() - timedelta(seconds=5)).strftime('%Y-%m-%d %H:%M:%S')
            C.run_time('kimi_lab_timer', '60nSecond', st)
            print('[kimi-lab] 已注册导出定时器')
        except Exception as e:
            print('[kimi-lab] 注册定时器失败', e)


LAB_QMT_DIR = 'C:\\Users\\91501\\Desktop\\\u7b56\u7565\u5e93\\\u81ea\u5a92\u4f53\\\u516c\u4f17\u53f7\\kimi-quant-lab\\qmt'


def _lab_root():
    import sys
    candidates = []
    try:
        candidates.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
    except Exception:
        pass
    candidates.append(LAB_QMT_DIR)
    try:
        cwd = os.getcwd()
        candidates.append(os.path.abspath(os.path.join(cwd, 'qmt')))
        candidates.append(os.path.abspath(cwd))
    except Exception:
        pass
    for root in candidates:
        if root and os.path.isfile(os.path.join(root, 'kimi_lab_export.py')):
            if root not in sys.path:
                sys.path.insert(0, root)
            return root
    if LAB_QMT_DIR not in sys.path:
        sys.path.insert(0, LAB_QMT_DIR)
    return LAB_QMT_DIR



_book_ns = None
_book_cache = None
_book_cache_ts = 0.0


def _inject_lab_book():
    global _book_ns
    if _book_ns is not None:
        return _book_ns
    import time as _t
    root = _lab_root()
    path = os.path.join(root, 'kimi_lab_book.py')
    print('[lab-book] exec path=%s exists=%s' % (path, os.path.isfile(path)))
    raw = ''
    last = None
    for enc in ('utf-8', 'gbk'):
        try:
            with open(path, 'r', encoding=enc) as f:
                raw = f.read()
            break
        except Exception as e:
            last = e
            raw = ''
    if not raw:
        raise RuntimeError('read kimi_lab_book.py fail: %s' % last)
    exec(compile(raw, path, 'exec'), globals())
    class _NS(object):
        pass
    ns = _NS()
    names = (
        'load', 'save', 'reconcile', 'account_map', 'hold_map',
        'claimed_qty', 'sellable_qty', 'usable_cash', 'equity',
        'apply_buy', 'apply_sell', 'position_cost', 'export_payload',
        'seed_from_holds',
    )
    gdict = globals()
    for name in names:
        if name in gdict:
            setattr(ns, name, gdict[name])
    _book_ns = ns
    print('[lab-book] exec ok')
    return ns


def _lab_book():
    global _book_cache, _book_cache_ts
    import time as _t
    now = _t.time()
    ns = _inject_lab_book()
    if _book_cache is not None and (now - _book_cache_ts) < 2:
        return ns, _book_cache
    book = ns.load('limit_gene', '涨停基因小市值')
    ns.reconcile(book, getattr(g, 'accountid', ''), getattr(g, 'acct_type', 'STOCK'))
    _book_cache = book
    _book_cache_ts = now
    return ns, book


def _sync_hold_from_book():
    try:
        bm, book = _lab_book()
        if not book.get('positions'):
            legacy = load_my_hold_list()
            _cash, real_pos = bm.account_map(getattr(g, 'accountid', ''), getattr(g, 'acct_type', 'STOCK'))
            bm.seed_from_holds(book, legacy, real_pos)
        g.my_hold_list = bm.hold_map(book)
        save_my_hold_list()
    except Exception:
        pass


def _kimi_lab_export(C):
    try:
        _inject_lab_book()
        from kimi_lab_export import maybe_export
        maybe_export(
            C,
            strategy_id='limit_gene',
            strategy_name='涨停基因小市值',
            account=getattr(g, 'accountid', ''),
            account_type=getattr(g, 'acct_type', 'STOCK'),
            hold_codes=list((getattr(g, 'my_hold_list', {}) or {}).keys()),
        )
    except Exception as e:
        print('[kimi-lab]', e)


def kimi_lab_timer(C):
    if getattr(C, 'do_back_test', False):
        return
    _kimi_lab_export(C)

def handlebar(C):
    """主策略逻辑"""
    try:
        c_date = timetag_to_datetime(C.get_bar_timetag(C.barpos), '%Y%m%d')
        s_date = timetag_to_datetime(C.get_bar_timetag(C.barpos), '%Y%m%d%H%M%S')
        bar_time = timetag_to_datetime(C.get_bar_timetag(C.barpos), '%H%M%S')
        now = datetime.now().date().strftime('%Y%m%d')
        
        if c_date != now and not C.do_back_test:
            return
        
        hour = int(bar_time[:2]) if len(bar_time) >= 2 else 0
        minute = int(bar_time[2:4]) if len(bar_time) >= 4 else 0
        if hour < 9 or hour > 15:
            return
        
        if g.current_date != c_date:
            g.current_date = c_date
            g.last_prepare_date = None
            g.last_weekly_sell_date = None
            g.last_weekly_buy_date = None
            g.last_sell_date = None
            g.last_afternoon_1420 = None
            g.last_afternoon_1455 = None
            g.last_close_date = None
            print(f"\n{'='*80}\n=== {c_date} 新交易日 ===\n{'='*80}\n")
            # 新交易日首bar即执行准备（QMT回测可能无9:05 bar，导致空仓信号未设置）
            g.last_prepare_date = c_date
            prepare_stock_list(C, s_date, c_date)
        
        date_obj = datetime.strptime(c_date, '%Y%m%d')
        weekday = date_obj.weekday()  # 0=周一 1=周二
        
        # 9:05 准备股票列表
        if hour == 9 and minute == 5 and g.last_prepare_date != c_date:
            g.last_prepare_date = c_date
            prepare_stock_list(C, s_date, c_date)
        
        # 10:00 止损
        if hour == 10 and minute == 0 and g.last_sell_date != c_date:
            g.last_sell_date = c_date
            sell_stocks(C, s_date, c_date)
        
        # 10:15 周二卖出
        if hour == 10 and minute == 15 and weekday == 1 and g.last_weekly_sell_date != c_date:
            g.last_weekly_sell_date = c_date
            weekly_sell(C, s_date, c_date)
        
        # 10:30 周二买入
        if hour == 10 and minute == 30 and weekday == 1 and g.last_weekly_buy_date != c_date:
            g.last_weekly_buy_date = c_date
            weekly_buy(C, s_date, c_date)
        
        # 首次实盘运行：空仓时直接选股买入（不限于周二，与小市值买三支票一致）
        if (hour == 10 and minute == 30 and not C.do_back_test and len(g.my_hold_list) == 0
                and not today_is_between(c_date) and not g.first_run_buy_done
                and g.last_weekly_buy_date != c_date):
            g.last_weekly_buy_date = c_date
            print("[首次实盘] 空仓，直接选股买入")
            weekly_buy(C, s_date, c_date)
            if g.my_hold_list:
                save_first_run_done()
                g.first_run_buy_done = True
                print("[首次实盘] 买入完成，已标记")
        
        # 14:20 下午检查
        if hour == 14 and minute == 20 and g.last_afternoon_1420 != c_date:
            g.last_afternoon_1420 = c_date
            trade_afternoon(C, s_date, c_date)
        
        # 14:55 下午检查
        if hour == 14 and minute == 55 and g.last_afternoon_1455 != c_date:
            g.last_afternoon_1455 = c_date
            trade_afternoon(C, s_date, c_date)
        
        # 14:50 收盘处理
        if hour == 14 and minute == 50 and g.last_close_date != c_date:
            g.last_close_date = c_date
            close_account(C, s_date, c_date)
        if not C.do_back_test:
            _kimi_lab_export(C)
            
    except Exception as e:
        print(f"? handlebar异常: {e}")
        import traceback
        traceback.print_exc()

# ====================== 准备函数 ======================
def prepare_stock_list(C, s_date, c_date):
    """准备持仓、昨日涨停（策略隔离：仅操作 g.my_hold_list）"""
    try:
        g.hold_list = []
        # 策略隔离：hold_list 来自本策略自维护持仓
        _sync_hold_from_book()
        g.hold_list = list(g.my_hold_list.keys())
        
        if g.hold_list:
            yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
            data = C.get_market_data_ex(['close', 'high'], g.hold_list,
                end_time=yesterday + '150000', period='1d', count=1, subscribe=False)
            g.yesterday_HL_list = []
            for stock in g.hold_list:
                try:
                    if stock in data and not data[stock].empty:
                        df = data[stock]
                        close_price = float(df['close'].iloc[-1])
                        high_price = float(df['high'].iloc[-1])
                        if close_price > 0 and high_price / close_price > 1.09:
                            g.yesterday_HL_list.append(stock)
                except:
                    continue
            if g.yesterday_HL_list:
                print(f"昨日涨停: {g.yesterday_HL_list}")
        else:
            g.yesterday_HL_list = []
        
        g.no_trading_today_signal = today_is_between(c_date)
        if g.no_trading_today_signal:
            print("?? 今日为空仓月份（1月或4月）")
    except Exception as e:
        print(f"? prepare_stock_list: {e}")

def today_is_between(c_date):
    """1月或4月空仓"""
    try:
        date_obj = datetime.strptime(c_date, '%Y%m%d')
        month_day = date_obj.strftime('%m-%d')
        if g.pass_april:
            if ('04-01' <= month_day <= '04-30') or ('01-01' <= month_day <= '01-31'):
                return True
        return False
    except:
        return False

# ====================== 选股核心 ======================
def get_history_highlimit(C, stock_list, c_date, days=750, p=0.10):
    """历史涨停次数前p比例（聚宽：close==high_limit 为涨停日）"""
    try:
        yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
        end_time = yesterday + '150000'
        
        limit_counts = {}
        for i in range(0, len(stock_list), 200):
            batch = stock_list[i:i+200]
            data = C.get_market_data_ex(['close', 'open'], batch, end_time=end_time,
                period='1d', count=days, subscribe=False)
            for stock in batch:
                if stock not in data or data[stock].empty or len(data[stock]) < 2:
                    continue
                close_arr = np.asarray(data[stock].sort_index()['close'].values, dtype=float)
                rate = 1.2 if (stock.startswith('300') or stock.startswith('688')) else 1.1
                prev_close = close_arr[:-1]
                curr_close = close_arr[1:]
                valid = (curr_close > 0) & (prev_close > 0)
                high_limit = prev_close * rate
                is_limit = valid & (np.abs(curr_close - high_limit) < 0.02)
                count = int(np.sum(is_limit))
                if count > 0:
                    limit_counts[stock] = count
        
        sorted_stocks = sorted(limit_counts.keys(), key=lambda x: limit_counts[x], reverse=True)
        n = max(1, int(len(sorted_stocks) * p))
        result = sorted_stocks[:n]
        print(f"涨停基因: {len(limit_counts)}只有涨停 -> 前{p:.0%}取{len(result)}只")
        return result
    except Exception as e:
        print(f"? get_history_highlimit: {e}")
        return stock_list[:max(1, int(len(stock_list)*p))]

def get_start_point(C, stock_list, s_date, c_date, days=750):
    """启动点排序：最近涨停前第一个阴线低点，按价格偏移升序（聚宽逻辑）"""
    try:
        yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
        end_time = yesterday + '150000'
        
        stock_start_point = {}
        stock_price_bias = {}
        
        for i in range(0, len(stock_list), 100):
            batch = stock_list[i:i+100]
            data = C.get_market_data_ex(['open', 'low', 'close'], batch, end_time=end_time,
                period='1d', count=days, subscribe=False)
            for stock in batch:
                if stock not in data or data[stock].empty or len(data[stock]) < 2:
                    continue
                df = data[stock].sort_index()
                close_arr = df['close'].values
                open_arr = df['open'].values
                low_arr = df['low'].values
                rate = 1.2 if (stock.startswith('300') or stock.startswith('688')) else 1.1
                for j in range(len(close_arr)-1, 0, -1):
                    if close_arr[j] <= 0:
                        continue
                    prev_close = close_arr[j-1]
                    high_limit = prev_close * rate
                    if abs(close_arr[j] - high_limit) < 0.02:
                        for k in range(j-1, -1, -1):
                            if close_arr[k] < open_arr[k]:
                                stock_start_point[stock] = low_arr[k]
                                break
                        break
        
        # 当前价/启动点（批量获取，实盘用s_date取实时价，回测用昨日收盘）
        stocks_to_price = list(stock_start_point.keys())
        if stocks_to_price:
            try:
                if s_date and len(s_date) >= 14:
                    price_data = C.get_market_data_ex(['close'], stocks_to_price, end_time=s_date, period='1m', count=1, subscribe=False)
                else:
                    yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
                    price_data = C.get_market_data_ex(['close'], stocks_to_price, end_time=yesterday+'150000', period='1d', count=1, subscribe=False)
                for stock in stocks_to_price:
                    if stock in price_data and not price_data[stock].empty:
                        price = float(price_data[stock]['close'].iloc[-1])
                        if price > 0 and stock_start_point[stock] > 0:
                            stock_price_bias[stock] = price / stock_start_point[stock]
            except:
                for stock in stocks_to_price:
                    price = get_current_price(C, stock, s_date, c_date)
                    if price and price > 0 and stock_start_point[stock] > 0:
                        stock_price_bias[stock] = price / stock_start_point[stock]
        
        sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)
        return [s[0] for s in sorted_list]
    except Exception as e:
        print(f"? get_start_point: {e}")
        return stock_list

def get_stock_industry_diversify(C, stock_list, max_industries=10):
    """行业分散：从已排序列表中每行业取1只，最多max_industries只（使用get_industry_name_of_stock，O(1)每只）"""
    selected = []
    industry_seen = set()
    for stock in stock_list:
        ind = get_stock_industry(C, stock)
        if ind and ind not in industry_seen:
            industry_seen.add(ind)
            selected.append(stock)
            if len(selected) >= max_industries:
                break
    return selected

def get_stock_industry(C, stock):
    """获取股票所属申万行业（优先用get_industry_name_of_stock，避免遍历100+板块）"""
    try:
        if hasattr(C, 'get_industry_name_of_stock'):
            return C.get_industry_name_of_stock('SW', stock) or None
        try:
            return get_industry_name_of_stock('SW', stock) or None
        except NameError:
            pass
        # 回退：遍历申万行业（慢）
        for industry in g.sw2_industries:
            try:
                stocks = C.get_stock_list_in_sector(industry)
                if stocks and stock in stocks:
                    return industry
            except:
                continue
    except:
        pass
    return None

def get_stock_list(C, s_date, c_date):
    """选股主函数（与聚宽版顺序一致：先过滤再市值排序）"""
    try:
        try:
            initial_list = C.get_stock_list_in_sector('沪深A股')
        except:
            initial_list = []
            print("?? 无法获取股票列表")
            return []
        
        if not initial_list:
            return []
        
        # 聚宽顺序：次新/科创/ST/停牌/止损黑名单 -> 市值排序前1000 -> 涨跌停 -> 涨停基因 -> 启动点 -> 行业分散
        initial_list = filter_kcbj_stock(initial_list)
        initial_list = filter_new_stock(C, initial_list, c_date)
        initial_list = filter_st_stock(C, initial_list)
        initial_list = filter_paused_stock(C, initial_list, s_date)
        if g.filter_loss_black:
            initial_list = filter_loss_black(C, initial_list, c_date, days=20)
        
        if len(initial_list) < 10:
            return []
        
        # 市值排序取前1000（在过滤后的列表上，与聚宽 valuation.market_cap.asc 一致）
        yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
        start_date = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=90)).strftime('%Y%m%d')
        process_list = initial_list[:min(5000, len(initial_list))]
        
        price_data = C.get_market_data_ex(['close'], process_list,
            end_time=yesterday + '150000', period='1d', count=1, subscribe=False)
        financial_data = C.get_financial_data(['CAPITALSTRUCTURE.total_capital'], process_list,
            start_date, yesterday, report_type='announce_time')
        
        market_caps = {}
        for stock in process_list:
            try:
                if stock in price_data and stock in financial_data:
                    close_price = price_data[stock]['close'].iloc[-1]
                    total_capital = financial_data[stock]['total_capital'].iloc[-1] if 'total_capital' in financial_data[stock].columns else None
                    if total_capital and total_capital > 0:
                        market_caps[stock] = close_price * total_capital
            except:
                continue
        
        if market_caps:
            df = pd.DataFrame.from_dict(market_caps, orient='index')
            df.columns = ['cap']
            df = df.dropna().sort_values(by='cap', ascending=True)
            initial_list = df.index.tolist()[:g.init_stock_count]
        else:
            initial_list = initial_list[:g.init_stock_count]
        
        if len(initial_list) < 10:
            return []
        
        initial_list = filter_limitup_stock(C, initial_list, s_date, c_date)
        initial_list = filter_limitdown_stock(C, initial_list, s_date, c_date)
        
        initial_list = get_history_highlimit(C, initial_list, c_date, g.limit_days_window, 0.10)
        initial_list = get_start_point(C, initial_list, s_date, c_date, g.limit_days_window)
        
        final_list = get_stock_industry_diversify(C, initial_list, 10)
        final_list = final_list[:g.stock_num * 2]
        print(f"选股结果: {final_list[:10]}...")
        return final_list
    except Exception as e:
        print(f"? get_stock_list: {e}")
        import traceback
        traceback.print_exc()
        return []

# ====================== 调仓 ======================
def weekly_sell(C, s_date, c_date):
    """周二10:15卖出（仅卖本策略持仓）"""
    if g.no_trading_today_signal or today_is_between(c_date):
        return
    try:
        g.not_buy_again = []
        g.target_list = get_stock_list(C, s_date, c_date)
        target_list = g.target_list[:g.stock_num * 2]
        
        for stock in list(g.my_hold_list.keys()):
            vol = min(g.my_hold_list.get(stock, 0), get_holding_volume(C, stock))
            if vol <= 0:
                continue
            if stock in target_list or stock in g.yesterday_HL_list:
                print(f"持有: {stock}")
                continue
            current_price = get_current_price(C, stock, s_date, c_date)
            if not current_price:
                continue
            yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
            prev_close = get_prev_close(C, stock, yesterday)
            if prev_close and prev_close > 0:
                rate = 1.2 if (stock.startswith('300') or stock.startswith('688')) else 1.1
                high_limit = prev_close * rate
                if current_price < high_limit * 0.99:
                    vol = int(vol / 100) * 100
                    if vol >= 100 and execute_sell(C, stock, vol):
                        g.my_hold_list.pop(stock, None)
                        save_my_hold_list()
                        print(f"卖出: {stock}")
    except Exception as e:
        print(f"? weekly_sell: {e}")

def weekly_buy(C, s_date, c_date):
    """周二10:30买入（策略可用总资产上限、策略隔离）"""
    if g.no_trading_today_signal or today_is_between(c_date):
        return
    try:
        g.not_buy_again = []
        g.target_list = get_stock_list(C, s_date, c_date)
        target_list = g.target_list[:g.stock_num * 2]
        
        holdings_dict = dict(g.my_hold_list)
        
        account = get_trade_detail_data(g.accountid, g.acct_type, 'ACCOUNT')
        if not account:
            return
        bm, book = _lab_book()
        real_cash = float(account[0].m_dAvailable or 0)
        total, _cash, _mv, _nav = bm.equity(book)
        available = bm.usable_cash(book, real_cash)
        if total <= 0:
            total = getattr(g, 'lab_capital', 100000)
        
        to_buy = [s for s in target_list if s not in holdings_dict or holdings_dict[s] == 0]
        to_buy = to_buy[:g.stock_num]
        
        if not to_buy:
            return
        
        value_per = total / g.stock_num
        for stock in to_buy:
            price = get_current_price(C, stock, s_date, c_date)
            if not price or price <= 0:
                continue
            shares = int(value_per / price / 100) * 100
            if shares < 100:
                continue
            if available < shares * price:
                break
            try:
                passorder(g.buy_code, 1101, g.accountid, stock, 5, -1, shares, '涨停基因小市值', 2, g.strategy_id, C)
                available -= shares * price
                try:
                    bm, book = _lab_book()
                    bm.apply_buy(book, stock, shares, price)
                    g.my_hold_list = bm.hold_map(book)
                except Exception:
                    g.my_hold_list[stock] = g.my_hold_list.get(stock, 0) + shares
                save_my_hold_list()
                g.not_buy_again.append(stock)
                print(f"买入: {stock} {shares}股")
            except Exception as e:
                print(f"买入失败 {stock}: {e}")
    except Exception as e:
        print(f"? weekly_buy: {e}")

# ====================== 下午交易 ======================
def trade_afternoon(C, s_date, c_date):
    """14:20/14:55 昨日涨停检查、换手率、余额买入"""
    if g.no_trading_today_signal or today_is_between(c_date):
        return
    try:
        check_limit_up(C, s_date, c_date)
        if g.HV_control:
            check_high_volume(C, s_date, c_date)
        huanshou(C, s_date, c_date)
        check_remain_amount(C, s_date, c_date)
    except Exception as e:
        print(f"? trade_afternoon: {e}")

def check_limit_up(C, s_date, c_date):
    """昨日涨停股：今日破板则卖出（仅本策略持仓）"""
    if not g.yesterday_HL_list:
        return
    try:
        for stock in list(g.yesterday_HL_list):
            if stock not in g.my_hold_list:
                continue
            vol = min(g.my_hold_list.get(stock, 0), get_holding_volume(C, stock))
            if vol <= 0:
                continue
            current_price = get_current_price(C, stock, s_date, c_date)
            yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
            prev_close = get_prev_close(C, stock, yesterday)
            if prev_close and prev_close > 0:
                rate = 1.2 if (stock.startswith('300') or stock.startswith('688')) else 1.1
                high_limit = prev_close * rate
                if current_price < high_limit * 0.99:
                    vol = int(vol / 100) * 100
                    if vol >= 100 and execute_sell(C, stock, vol):
                        g.my_hold_list.pop(stock, None)
                        save_my_hold_list()
                        print(f"[{stock}]涨停打开，卖出")
                        g.reason_to_sell = 'limitup'
    except Exception as e:
        print(f"? check_limit_up: {e}")

def check_high_volume(C, s_date, c_date):
    """放量检测：当日成交量>HV_ratio*近HV_duration日最大量则卖出（仅本策略持仓）"""
    if not g.HV_control:
        return
    try:
        stock_list = [s for s in g.my_hold_list if get_holding_volume(C, s) > 0]
        if not stock_list:
            return
        yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
        data = C.get_market_data_ex(['volume'], stock_list, end_time=s_date, period='1d',
            count=g.HV_duration, subscribe=False)
        for stock in stock_list:
            vol = min(g.my_hold_list.get(stock, 0), get_holding_volume(C, stock))
            if vol <= 0:
                continue
            if C.is_suspended_stock(stock):
                continue
            if stock not in data or data[stock].empty or len(data[stock]) < 2:
                continue
            df = data[stock].sort_index()
            vol_arr = df['volume'].values
            today_vol = float(vol_arr[-1]) if len(vol_arr) > 0 else 0
            max_vol = float(np.max(vol_arr)) if len(vol_arr) > 0 else 0
            if max_vol <= 0:
                continue
            if today_vol > g.HV_ratio * max_vol:
                vol = int(vol / 100) * 100
                if vol >= 100 and execute_sell(C, stock, vol):
                    g.my_hold_list.pop(stock, None)
                    save_my_hold_list()
                    print(f"[{stock}]天量，卖出 (当日量{today_vol:.0f} > {g.HV_ratio:.0%}*最大{max_vol:.0f})")
                    g.reason_to_sell = 'limitup'
    except Exception as e:
        print(f"? check_high_volume: {e}")

def _get_circulating_cap(C, stock, end_date):
    """获取流通股本（万股），用于换手率计算"""
    try:
        start = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=90)).strftime('%Y%m%d')
        fd = C.get_financial_data(['CAPITALSTRUCTURE.circulating_capital'], [stock], start, end_date, report_type='report_time')
        if fd is not None and stock in fd and not fd[stock].empty:
            cols = [c for c in fd[stock].columns if 'circulating' in str(c).lower()]
            if cols:
                val = fd[stock][cols[0]].iloc[-1]
                if not pd.isna(val) and val > 0:
                    return float(val)
        d = C.get_instrumentdetail(stock)
        if d and d.get('FloatVolumn', 0) > 0:
            return float(d['FloatVolumn'])
        if d and d.get('FloatVolume', 0) > 0:
            return float(d['FloatVolume'])
    except:
        pass
    return 0

def _huanshoulv_avg(C, stock, c_date):
    """20日平均换手率"""
    try:
        yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
        start = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=25)).strftime('%Y%m%d')
        if hasattr(C, 'get_turnover_rate'):
            df = C.get_turnover_rate([stock], start, yesterday)
            if df is not None and not df.empty:
                if stock in df.columns:
                    vals = df[stock].dropna()
                else:
                    col = [c for c in df.columns if '换手' in str(c) or 'turnover' in str(c).lower()]
                    vals = df[col[0]].dropna() if col else pd.Series()
                if len(vals) >= 5:
                    return float(vals.tail(20).mean())
        cap = _get_circulating_cap(C, stock, yesterday)
        if cap <= 0:
            return 0.0
        data = C.get_market_data_ex(['volume'], [stock], end_time=yesterday+'150000', period='1d', count=21, subscribe=False)
        if stock not in data or data[stock].empty or len(data[stock]) < 5:
            return 0.0
        df = data[stock].sort_index()
        vol = df['volume'].tail(20).sum() * 100  # QMT volume单位：手，转股
        return float(vol) / (cap * 10000) if cap > 0 else 0.0
    except:
        return 0.0

def _huanshoulv_rt(C, stock, s_date, c_date):
    """当日实时换手率 = 今日成交量/流通股本。实盘用get_full_tick，回测用1m或日线或get_turnover_rate"""
    try:
        yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
        cap = _get_circulating_cap(C, stock, yesterday)
        if cap <= 0:
            return 0.0
        cap_gu = cap * 10000  # 万股转股
        vol = 0
        # 实盘：get_full_tick 直接取当日成交量
        if not getattr(C, 'do_back_test', False):
            try:
                tick = C.get_full_tick([stock])
                if tick and stock in tick:
                    t = tick[stock]
                    vol = (t.get('volume', 0) if isinstance(t, dict) else getattr(t, 'volume', 0)) or 0
                    vol = float(vol) * 100  # 手转股
            except:
                pass
        # 回测：优先 get_turnover_rate 当日（部分QMT支持盘中），其次1m，最后日线
        if vol <= 0 and hasattr(C, 'get_turnover_rate'):
            try:
                df = C.get_turnover_rate([stock], c_date, c_date)
                if df is not None and not df.empty and stock in df.columns:
                    v = df[stock].dropna()
                    if len(v) > 0:
                        tr = float(v.iloc[-1])
                        if tr > 0:
                            return tr / 100.0 if tr > 1 else tr
            except:
                pass
        # 回测：1m 今日分钟线（需QMT回测勾选1分钟数据并订阅）
        if vol <= 0:
            try:
                data = C.get_market_data_ex(['volume'], [stock], start_time=c_date+'093000', end_time=s_date, period='1m', subscribe=False, dividend_type='none')
                if stock in data and not data[stock].empty:
                    vol = float(data[stock]['volume'].sum()) * 100  # 手转股
            except:
                pass
        if vol <= 0:
            try:
                data = C.get_market_data_ex(['volume'], [stock], end_time=s_date, period='1m', count=240, subscribe=False, dividend_type='none')
                if stock in data and not data[stock].empty:
                    vol = float(data[stock]['volume'].sum()) * 100  # 手转股
            except:
                pass
        return vol / cap_gu if cap_gu > 0 else 0.0
    except:
        return 0.0

def huanshou(C, s_date, c_date):
    """换手率检测：缩量(均<0.3%)/放量(实时>10%且>2倍均)则卖出（仅本策略持仓）"""
    try:
        shrink, expand = 0.003, 0.1
        hold_list = [s for s in g.my_hold_list if get_holding_volume(C, s) > 0]
        if hold_list:
            print(f"[换手调试] {c_date} 开始检查 {len(hold_list)} 只持仓")
        for stock in hold_list:
            can_sell = min(g.my_hold_list.get(stock, 0), get_holding_volume(C, stock))
            if can_sell <= 0:
                continue
            if C.is_suspended_stock(stock):
                continue
            yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
            prev_close = get_prev_close(C, stock, yesterday)
            curr_price = get_current_price(C, stock, s_date, c_date)
            if prev_close and prev_close > 0:
                rate = 1.2 if (stock.startswith('300') or stock.startswith('688')) else 1.1
                high_limit = prev_close * rate
                if curr_price >= high_limit * 0.97:
                    continue
            rt = _huanshoulv_rt(C, stock, s_date, c_date)
            avg = _huanshoulv_avg(C, stock, c_date)
            # [调试] 换手率：rt=当日实时 avg=20日均 缩量<0.3% 放量>10%且>2倍均
            r_str = f"{rt/avg:.2f}x" if avg > 0 else "N/A"
            tag = (" 缩量!" if avg < 0.003 else "") + (" 放量!" if avg >= 0.003 and rt > 0.1 and (rt/avg > 2 if avg > 0 else False) else "")
            rt_note = " (rt=0请检查1m数据)" if rt == 0 and avg > 0 else ""
            print(f"[换手调试] {stock} rt={rt:.4f}({rt:.2%}) avg={avg:.4f}({avg:.2%}) 倍率={r_str}{tag}{rt_note}")
            if avg <= 0:
                continue
            r = rt / avg
            action, icon = '', ''
            if avg < shrink:
                action, icon = '缩量', ''
            elif rt > expand and r > 2:
                action, icon = '放量', ''
            if action:
                try:
                    name = C.get_stock_name(stock) if hasattr(C, 'get_stock_name') else stock
                except:
                    name = stock
                print(f"{action} {stock} {name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon}")
                can_sell = int(can_sell / 100) * 100
                if can_sell >= 100 and execute_sell(C, stock, can_sell):
                    g.my_hold_list.pop(stock, None)
                    save_my_hold_list()
                    g.reason_to_sell = 'limitup'
    except Exception as e:
        print(f"? huanshou: {e}")

def check_remain_amount(C, s_date, c_date):
    """昨日涨停卖出后余额买入（仅本策略持仓计数）"""
    if g.reason_to_sell != 'limitup':
        g.reason_to_sell = ''
        return
    g.reason_to_sell = ''
    try:
        hold_count = len(g.my_hold_list)
        if hold_count < g.stock_num:
            target_list = get_stock_list(C, s_date, c_date)
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            if target_list:
                weekly_buy(C, s_date, c_date)
    except:
        pass

# ====================== 止损 ======================
def sell_stocks(C, s_date, c_date):
    """止损：策略3 大盘+个股"""
    if not g.run_stoploss:
        return
    try:
        if g.stoploss_strategy == 3:
            # 大盘检测
            try:
                index_stocks = C.get_stock_list_in_sector('399101.SZ')[:100]
                if index_stocks:
                    data = C.get_market_data_ex(['open', 'close'], index_stocks,
                        end_time=c_date + '150000', period='1d', count=1, subscribe=False)
                    ratios = []
                    for s in index_stocks:
                        if s in data and not data[s].empty:
                            o = data[s]['open'].iloc[-1]
                            c = data[s]['close'].iloc[-1]
                            if o and o > 0:
                                ratios.append(c / o)
                    if ratios and np.mean(ratios) <= g.stoploss_market:
                        g.reason_to_sell = 'stoploss'
                        print("大盘惨跌，清仓")
                        for stock in list(g.my_hold_list.keys()):
                            vol = min(g.my_hold_list.get(stock, 0), get_holding_volume(C, stock))
                            if vol > 0:
                                vol = int(vol / 100) * 100
                                if vol >= 100 and execute_sell(C, stock, vol):
                                    g.my_hold_list.pop(stock, None)
                                    save_my_hold_list()
                                    g.loss_black[stock] = c_date
                        return
            except:
                pass
            
            # 个股止损（仅本策略持仓）
            for stock in list(g.my_hold_list.keys()):
                vol = min(g.my_hold_list.get(stock, 0), get_holding_volume(C, stock))
                if vol <= 0:
                    continue
                cost = 0
                try:
                    bm, book = _lab_book()
                    cost = bm.position_cost(book, stock)
                except Exception:
                    cost = 0
                if cost <= 0:
                    continue
                price = get_current_price(C, stock, s_date, c_date)
                if price and price < cost * g.stoploss_limit:
                    vol = int(vol / 100) * 100
                    if vol >= 100 and execute_sell(C, stock, vol):
                        g.my_hold_list.pop(stock, None)
                        save_my_hold_list()
                        print(f"止损: {stock}")
                        g.reason_to_sell = 'stoploss'
                        g.loss_black[stock] = c_date
    except Exception as e:
        print(f"? sell_stocks: {e}")

# ====================== 收盘 ======================
def close_account(C, s_date, c_date):
    """空仓月份清仓（仅本策略持仓）"""
    if not (g.no_trading_today_signal or today_is_between(c_date)):
        return
    try:
        if g.my_hold_list and not g.no_trading_hold_signal:
            for stock in list(g.my_hold_list.keys()):
                vol = min(g.my_hold_list.get(stock, 0), get_holding_volume(C, stock))
                if vol > 0:
                    vol = int(vol / 100) * 100
                    if vol >= 100 and execute_sell(C, stock, vol):
                        g.my_hold_list.pop(stock, None)
                        save_my_hold_list()
                        print(f"空仓卖出: {stock}")
            g.no_trading_hold_signal = True
    except Exception as e:
        print(f"? close_account: {e}")

# ====================== 过滤器 ======================
def filter_new_stock(C, stock_list, c_date):
    """过滤次新股：上市>=375天（聚宽用previous_date）"""
    yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
    cutoff = (datetime.strptime(yesterday, '%Y%m%d') - timedelta(days=375)).strftime('%Y%m%d')
    cutoff_int = int(cutoff)
    out = []
    for stock in stock_list:
        try:
            d = C.get_instrumentdetail(stock)
            if d and d.get('OpenDate', 99999999) <= cutoff_int:
                out.append(stock)
        except:
            continue
    return out

def filter_kcbj_stock(stock_list):
    return [s for s in stock_list if s[0] not in ('4','8') and not s.startswith('688')]

def filter_st_stock(C, stock_list):
    out = []
    for s in stock_list:
        try:
            name = C.get_stock_name(s)
            if 'ST' not in name and '*' not in name and '退' not in name:
                out.append(s)
        except:
            continue
    return out

def filter_paused_stock(C, stock_list, s_date):
    return [s for s in stock_list if not C.is_suspended_stock(s)]

def filter_loss_black(C, stock_list, c_date, days=20):
    out = []
    for s in stock_list:
        if s not in g.loss_black:
            out.append(s)
            continue
        try:
            loss_date = g.loss_black[s]
            if isinstance(loss_date, str):
                loss_dt = datetime.strptime(loss_date, '%Y%m%d')
            else:
                loss_dt = loss_date
            curr_dt = datetime.strptime(c_date, '%Y%m%d')
            if (curr_dt - loss_dt).days >= days:
                out.append(s)
        except:
            out.append(s)
    return out

def filter_limitup_stock(C, stock_list, s_date, c_date):
    """批量获取昨日收盘+当前价，过滤涨停股（非涨停才保留，本策略持仓保留）"""
    out = []
    hold_set = set(g.my_hold_list.keys())
    yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
    check_list = [s for s in stock_list[:500] if s not in hold_set]
    if not check_list:
        out = list(stock_list[:500])
        out.extend(stock_list[500:])
        return out
    try:
        price_data = C.get_market_data_ex(['close'], check_list, end_time=yesterday+'150000', period='1d', count=1, subscribe=False)
        curr_data = C.get_market_data_ex(['close'], check_list, end_time=s_date, period='1m', count=1, subscribe=False)
        for stock in stock_list[:500]:
            if stock in hold_set:
                out.append(stock)
                continue
            try:
                if stock in price_data and stock in curr_data and not price_data[stock].empty and not curr_data[stock].empty:
                    prev_close = float(price_data[stock]['close'].iloc[-1])
                    curr_price = float(curr_data[stock]['close'].iloc[-1])
                    rate = 1.2 if (stock.startswith('300') or stock.startswith('688')) else 1.1
                    if curr_price < prev_close * rate:
                        out.append(stock)
                else:
                    out.append(stock)
            except:
                out.append(stock)
    except:
        out.extend(stock_list[:500])
    out.extend(stock_list[500:])
    return out

def filter_limitdown_stock(C, stock_list, s_date, c_date):
    """批量获取昨日收盘+当前价，过滤跌停股（本策略持仓保留）"""
    out = []
    hold_set = set(g.my_hold_list.keys())
    yesterday = (datetime.strptime(c_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
    check_list = [s for s in stock_list[:500] if s not in hold_set]
    if not check_list:
        out = list(stock_list[:500])
        out.extend(stock_list[500:])
        return out
    try:
        price_data = C.get_market_data_ex(['close'], check_list, end_time=yesterday+'150000', period='1d', count=1, subscribe=False)
        curr_data = C.get_market_data_ex(['close'], check_list, end_time=s_date, period='1m', count=1, subscribe=False)
        for stock in stock_list[:500]:
            if stock in hold_set:
                out.append(stock)
                continue
            try:
                if stock in price_data and stock in curr_data and not price_data[stock].empty and not curr_data[stock].empty:
                    prev_close = float(price_data[stock]['close'].iloc[-1])
                    curr_price = float(curr_data[stock]['close'].iloc[-1])
                    rate = 0.8 if (stock.startswith('300') or stock.startswith('688')) else 0.9
                    if curr_price > prev_close * rate:
                        out.append(stock)
                else:
                    out.append(stock)
            except:
                out.append(stock)
    except:
        out.extend(stock_list[:500])
    out.extend(stock_list[500:])
    return out

def filter_not_buy_again(stock_list):
    return [s for s in stock_list if s not in g.not_buy_again]

# ====================== 辅助 ======================
def get_current_price(C, stock, s_date=None, c_date=None):
    """获取当前价：实盘用get_full_tick，回测用分钟线/日线"""
    try:
        if not getattr(C, 'do_back_test', False):
            tick = C.get_full_tick([stock])
            if tick and stock in tick:
                t = tick[stock]
                p = t.get('lastPrice', 0) if isinstance(t, dict) else getattr(t, 'lastPrice', 0)
                if p and float(p) > 0:
                    return float(p)
        if s_date and len(s_date) >= 14:
            data = C.get_market_data_ex(['close'], [stock], end_time=s_date, period='1m', count=1, subscribe=False)
        elif c_date:
            data = C.get_market_data_ex(['close'], [stock], end_time=c_date+'150000', period='1d', count=1, subscribe=False)
        else:
            return 0
        if stock in data and not data[stock].empty:
            return float(data[stock]['close'].iloc[-1])
    except:
        pass
    return 0

def get_prev_close(C, stock, date_str):
    try:
        data = C.get_market_data_ex(['close'], [stock], end_time=date_str+'150000', period='1d', count=1, subscribe=False)
        if stock in data and not data[stock].empty:
            return float(data[stock]['close'].iloc[-1])
    except:
        pass
    return 0

def execute_sell(C, stock, volume):
    try:
        try:
            bm, book = _lab_book()
            _cash, real_pos = bm.account_map(g.accountid, g.acct_type)
            info = real_pos.get(stock) or {}
            volume = bm.sellable_qty(book, stock, info.get('can_use') or 0, info.get('qty') or 0)
        except Exception:
            pass
        if int(volume or 0) <= 0:
            return False
        passorder(g.sell_code, 1101, g.accountid, stock, 5, -1, volume, '涨停基因小市值', 2, g.strategy_id, C)
        try:
            bm, book = _lab_book()
            bm.apply_sell(book, stock, volume)
            g.my_hold_list = bm.hold_map(book)
            save_my_hold_list()
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"卖出失败 {stock}: {e}")
        return False

'''
