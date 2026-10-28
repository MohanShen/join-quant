# Clone from JoinQuant
# postId: e999b7ed7ce5435e26959b98004ee053
# backtestId: 1c265681acbfa2f38330259432212519
# title: 为什么几个最强的多因子小市值跑出来是一坨屎啊

# 克隆自聚宽文章：https://www.joinquant.com/post/40407
# 标题：wywy1995大侠的小市值AI因子选股 5组参数50股测试
# 作者：Bruce_Lee
# 因子组合：因子2(DtA-OCtORR) + 因子4(ORGR-SRFps-VSTD20-NOCFtOI) + 因子5(ARBR-SGAI-NPTTOR-RPPS) + 因子8(Liquidity-VCPttm-ROAttm) + 因子13(VSTD20-ARTR-LTDtAR-OC)

#https://www.joinquant.com/view/community/detail/30684f8d65a74eef0d704239f0eec8be?type=1&page=2
#导入函数库
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd



#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000905.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    #初始化全局变量
    g.no_trading_today_signal = False
    g.stock_num = 1
    g.stop_loss_pct = -0.08  # 止损线：亏损8%强制卖出
    g.hold_list = [] #当前持仓的全部股票    
    g.yesterday_HL_list = [] #记录持仓中昨日涨停的股票
    g.factor_list = [
        (#因子2 DtA-OCtORR-DAVOL20-PNF-SG（资产负债率+销售成本率+换手率比+不复权价格+营收增长）
            [
                'debt_to_assets', #风格因子 资产负债率
                'operating_cost_to_operating_revenue_ratio', #质量类因子 销售成本率
                'DAVOL20', #情绪类因子 20日平均换手率与120日平均换手率之比
                'price_no_fq', #技术指标因子 不复权价格因子
                'sales_growth' #风格因子 5年营业收入增长率
            ],
            [
                0.04477354820057883,
                0.021636407482421707,
                -0.01864268317469762,
                -0.0004678118383947827,
                0.02884867440332058
            ]
        ),
        (#因子4 ORGR-SRFps-VSTD20-NOCFtOI（营收增长率+每股公积金+20日量标准差+经营现金流/营业收入）
            [
                'operating_revenue_growth_rate', #成长类因子 营业收入增长率
                'surplus_reserve_fund_per_share', #每股指标因子 每股盈余公积
                'VSTD20', #情绪类因子 20日成交量标准差
                'net_operate_cash_flow_to_operate_income' #基础科目及衍生类因子 经营活动净现金流/营业收入
            ],
            [
                -2.2611191074512323e-05,
                -0.007031472339507336,
                -2.2140446594154373e-10,
                6.483698165689134e-05
            ]
        ),
        (#因子5 ARBR-SGAI-NPTTOR-RPPS（情绪ARBR+销售管理费用指数+净利润营收比+每股未分配利润）
            [
                'ARBR', #情绪类因子 ARBR
                'SGAI', #质量类因子 销售管理费用指数
                'net_profit_to_total_operate_revenue_ttm', #质量类因子 净利润与营业总收入之比
                'retained_profit_per_share' #每股指标因子 每股未分配利润
            ],
            [
                -2.3425,
                -694.7936,
                -170.0463,
                -1362.5762
            ]
        ),
        (#因子8 Liquidity-VCPttm-ROAttm（流动性+价值变动盈利+ROA）
            [
                'liquidity', #质量类因子 流动比率
                'value_change_profit_ttm', #基础科目及衍生类因子 公允价值变动损益TTM
                'roa_ttm' #基础科目及衍生类因子 ROA TTM
            ],
            [
                -0.04963427582597701,
                6.451436607157746e-13,
                -0.04698060391789672
            ]
        ),
        (#因子13 VSTD20-ARTR-LTDtAR-OC（量标差+应收周转率+长期债务资产比+营业周期）
            [
                'VSTD20', #情绪类因子 20日成交量标准差
                'account_receivable_turnover_rate', #质量类因子 应收账款周转率
                'long_term_debt_to_asset_ratio', #风格因子 长期债务与总资产之比
                'OperatingCycle' #质量类因子 营业周期
            ],
            [
                -1.3783e-09,
                -4.8282e-16,
                -4.6013e-02,
                2.4878e-09
            ]
        )
    ]
    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_adjustment, 1, '9:30')
    run_daily(check_limit_up, '14:00') #检查持仓中的涨停股是否需要卖出
    #run_daily(check_stop_loss, '10:00')   #早盘止损检查
    #run_daily(check_stop_loss, '14:50')   #尾盘止损检查
    run_daily(close_account, '14:30')
    run_daily(print_position_info, '15:10')



#1-1 准备股票池
def prepare_stock_list(context):
    #获取已持有列表
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    #获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    #判断今天是否为账户资金再平衡的日期
    g.no_trading_today_signal = today_is_between(context, '04-05', '04-30')
    
#1-2 选股模块
def get_stock_list(context):
    #指定日期防止未来数据
    yesterday = context.previous_date
    today = context.current_dt
    #获取初始列表
    initial_list = get_all_securities('stock', today).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    final_list = []
    #MS
    for factor_list,coef_list in g.factor_list:
        factor_values = get_factor_values(initial_list,factor_list, end_date=yesterday, count=1)
        df = pd.DataFrame(index=initial_list, columns=factor_values.keys())
        for i in range(len(factor_list)):
            df[factor_list[i]] = list(factor_values[factor_list[i]].T.iloc[:,0])
        df = df.dropna()
        df['total_score'] = 0
        for i in range(len(factor_list)):
            df['total_score'] += coef_list[i]*df[factor_list[i]]
        df = df.sort_values(by=['total_score'], ascending=False) #分数越高即预测未来收益越高，排序默认降序
        complex_factor_list = list(df.index)[:int(0.1*len(list(df.index)))]
        q = query(valuation.code,valuation.circulating_market_cap,indicator.eps).filter(valuation.code.in_(complex_factor_list)).order_by(valuation.circulating_market_cap.asc())
        df = get_fundamentals(q)
        df = df[df['eps']>0]
        lst  = list(df.code)
        lst = filter_paused_stock(lst)
        lst = filter_limitup_stock(context, lst)
        lst = filter_limitdown_stock(context, lst)
        lst = lst[:min(g.stock_num, len(lst))]
        for stock in lst:
            if stock not in final_list:
                final_list.append(stock)
    return final_list

#1-3 整体调整持仓
def weekly_adjustment(context):
    if g.no_trading_today_signal == False:
        #获取应买入列表 
        target_list = get_stock_list(context)
        #调仓卖出
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("已持有[%s]" % (stock))
        #调仓买入
        position_count = len(context.portfolio.positions)
        target_num = len(target_list)
        if target_num > position_count:
            value = context.portfolio.cash / (target_num - position_count)
            for stock in target_list:
                if context.portfolio.positions[stock].total_amount == 0:
                    if open_position(stock, value):
                        if len(context.portfolio.positions) == target_num:
                            break


#1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0,0] <    current_data.iloc[0,1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("[%s]涨停，继续持有" % (stock))



#1-5 止损检查
def check_stop_loss(context):
    """检查持仓是否触发止损：现价跌破成本价×(1+止损线)即卖出"""
    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]
        current_price = get_current_data()[stock].last_price
        cost = position.avg_cost
        if cost <= 0 or current_price <= 0:
            continue
        pnl_pct = (current_price - cost) / cost
        if pnl_pct <= g.stop_loss_pct:
            log.info("[止损触发] %s 成本:%.2f 现价:%.2f 亏损:%.2f%%" % (stock, cost, current_price, pnl_pct * 100))
            if position.closeable_amount > 0:
                order_target_value(stock, 0)


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
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]

#2-6 过滤次新股
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date <    datetime.timedelta(days=375)]



#3-1 交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
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



#4-1 判断今天是否为账户资金再平衡的日期
def today_is_between(context, start_date, end_date):
    today = context.current_dt.strftime('%m-%d')
    if (start_date <= today) and (today <= end_date):
        return True
    else:
        return False

#4-2 清仓后次日资金可转
def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                close_position(position)
                log.info("卖出[%s]" % (stock))

#4-3 打印每日持仓信息
def print_position_info(context):
    #打印当天成交记录
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：'+str(_trade))
    #打印账户信息
    for position in list(context.portfolio.positions.values()):
        securities=position.security
        cost=position.avg_cost
        price=position.price
        ret=100*(price/cost-1)
        value=position.value
        amount=position.total_amount    
        print('代码:{}'.format(securities))
        print('成本价:{}'.format(format(cost,'.2f')))
        print('现价:{}'.format(price))
        print('收益率:{}%'.format(format(ret,'.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value,'.2f')))
        print('———————————————————————————————————')
    print('———————————————————————————————————————分割线————————————————————————————————————————')
