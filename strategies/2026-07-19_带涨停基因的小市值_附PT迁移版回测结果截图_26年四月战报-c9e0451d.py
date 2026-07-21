# Clone from JoinQuant
# postId: c9e0451d0787df9f3427f051c6073210
# backtestId: 7e9973f3eb8a0de269eef29980041e7b
# title: 带涨停基因的小市值 附PT迁移版回测结果截图 26年四月战报

# 克隆自聚宽文章：https://www.joinquant.com/post/64881
# 标题：【变种小狮子】带涨停基因的股池轮动V2.2(BUGFIX)
# 作者：0xtao

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time


#初始化函数 
def initialize(context):
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
    g.filter_loss_black = True
    g.loss_black = {} # 止损后拉黑
    #全局变量
    g.stock_num = 6
    g.up_price = 20  # 设置股票单价 
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
    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_sell,2,'10:15')
    run_weekly(weekly_buy,2,'10:30')
    run_daily(sell_stocks, time='10:00') # 止损函数
    run_daily(trade_afternoon, time='14:20') #检查持仓中的涨停股是否需要卖出
    run_daily(trade_afternoon, time='14:55') #检查持仓中的涨停股是否需要卖出
    run_daily(close_account, '14:50')
    # run_weekly(print_position_info, 5, time='15:10')


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
        fill_paused=False,
    )
    df = df[df["close"] == df["high_limit"]]
    grouped_result = df.groupby('code').size().reset_index(name='count')
    grouped_result = grouped_result.sort_values(by=["count"], ascending=False)
    result_list = grouped_result["code"].tolist()[:int(len(grouped_result)*p)]
    log.info(f"筛选前合计{len(grouped_result)}个， 筛选后合计{len(result_list)}个")

    return result_list
    
    
def get_start_point(context, stock_list, days=3*250):
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["open", "low", "close", "high_limit"],
        count=days,
        panel=False,
        fill_paused=False,
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
    final_list = []
    yesterday = context.previous_date
    initial_list = get_all_securities("stock", yesterday).index.tolist()    

    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    
    if g.filter_loss_black:
        initial_list = filter_loss_black(context, initial_list, days=20) # 过滤最近20天被止损的股票
    
    q = query(
        valuation.code,indicator.eps
        ).filter(
            valuation.code.in_(initial_list)
            ).order_by(
                valuation.market_cap.asc()
                )
    df = get_fundamentals(q)
    initial_list = df['code'].tolist()[:g.init_stock_count]

    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    
    initial_list = get_history_highlimit(context, initial_list, g.limit_days_window)
    initial_list = get_start_point(context, initial_list, g.limit_days_window)

    stock_list = get_stock_industry(initial_list)
    final_list = stock_list[:g.stock_num*2]
    log.info('今日前10:%s' % final_list)
    
    return final_list


#1-3 整体调整持仓
def weekly_sell(context):
    if g.no_trading_today_signal == False:
        current_data = get_current_data()
        close_no_trading_hold(context)
        #获取应买入列表 
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.stock_num*2]
        log.info(str(target_list))

        #调仓卖出
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list) and (current_data[stock].last_price < current_data[stock].high_limit):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                pass
                log.info("已持有[%s]" % (stock))

            
            
#1-3 整体调整持仓
def weekly_buy(context):
    if g.no_trading_today_signal == False:
        current_data = get_current_data()
        #获取应买入列表 
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.stock_num*2]
        log.info(str(target_list))

        #调仓买入
        buy_security(context,target_list)
        #记录已买入股票
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.not_buy_again.append(stock)


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


#1-5 如果昨天有股票卖出或者买入失败，剩余的金额今天早上买入
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
def trade_afternoon(context):
    if g.no_trading_today_signal == False:
        check_limit_up(context)
        if g.HV_control == True:
            check_high_volume(context)
        huanshou(context)
        
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
                    g.loss_black[stock] = context.current_dt

                # 止损
                elif context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                    order_target_value(stock, 0)
                    log.debug("收益止损,卖出{}".format(stock))
                    g.reason_to_sell = 'stoploss'
                    g.loss_black[stock] = context.current_dt

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
                        g.loss_black[stock] = context.current_dt

                        

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
            or last_prices[stock][-1] < current_data[stock].high_limit]


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
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date <  datetime.timedelta(days=375)]


#2-6.5 过滤股价
def filter_highprice_stock(context,stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] <= g.up_price]


#2-7 删除本周一买入的股票
def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]
    
# 过滤最近被止损的股票
def filter_loss_black(context, stock_list, days=20):
    result_list = []
    for stock in stock_list:
        if (
            stock in g.loss_black.keys()
            and context.current_dt - g.loss_black[stock]
            < datetime.timedelta(days=days)
        ):
            log.info(
                f"{stock}由于近期止损被过滤, 止损时间：{g.loss_black[stock]}"
            )
            continue
        result_list.append(stock)
    return result_list
    
    
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
        start_date = context.current_dt - datetime.timedelta(days=20)
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
    

        