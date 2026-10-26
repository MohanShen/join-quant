# Clone from JoinQuant
# postId: 29048a4fa00b2bec20dffce7385d77fc
# backtestId: 19388dfc5ee53799e954dd2e00d2d1bb
# title: 中小板弱转强，高年化率低回撤修复版

# 克隆自聚宽文章：https://www.joinquant.com/post/61142
# 标题：首发中小板弱转强策略5年百倍年化134%
# 作者：空空儿

# 克隆自聚宽文章：https://www.joinquant.com/post/61142
# 标题：首发中小板弱转强策略5年百倍年化134%
# 作者：空空儿

import pandas as pd
import numpy as np
import datetime as dt
from datetime import datetime
from datetime import timedelta
from jqlib.technical_analysis import *
from jqdata import *

def initialize(context):
    set_option('use_real_price', True)
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0.0001))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0001, close_commission=0.0001,
                             close_today_commission=0, min_commission=1), type='stock')
    #----------------Settings--------------------------------------------------/
    g.stock_num=4
    g.today_list=[]#当日观测股票
    g.down=0.4 #下引线
    g.today_bought_stocks=set()  # 🔧【新增】记录当日买入的股票
    g.today_sold_stocks=set()    # 🔧【新增】记录当日卖出的股票
    g.last_total_value = 0       # 🔧【新增】记录昨日总资产
    #----------------Settings--------------------------------------------------/
    run_daily(perpare,time="09:26")
    run_daily(buy,time="09:27")
    run_daily(sell,time='13:00')
    run_daily(sell,time='14:55')
    #run_daily(sell,time='14:55')
    run_daily(dieting, time="every_bar")
    run_daily(daily_trading_report, time="15:05")  # 🔧【新增】每日交易报告

    # 过滤系统订单日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('order', 'warning')
    
def perpare(context):#筛选
    g.dieting=[]
    current_data = get_current_data()
    g.yesterday_high_dict = {}
    g.today_list=[]
    g.today_bought_stocks=set()  # 🔧【新增】每日重置当日买入股票记录
    g.today_sold_stocks=set()    # 🔧【新增】每日重置当日卖出股票记录
    stk_list=get_st(context)
    #1 4 12月 国九
    singal=today_is_between(context)
    if singal==True:
        print(f'筛选前：{len(stk_list)}')
        stk_list=GJT_filter_stocks(stk_list)
        print(f'筛选后：{len(stk_list)}')
        
    
    stk_list=filter_stocks(context,stk_list)
    if len(stk_list)==0:
        return
    stk_list=rzq_list(context,stk_list)
    if len(stk_list)==0:
        return
        # 低开

    # 获取前一日收盘价
    df = get_price(
        stk_list,
        end_date=context.previous_date,
        frequency='daily',
        fields=['close'],
        count=1,
        panel=False,
        fill_paused=False,
        skip_paused=True
    ).set_index('code')
    
    # 添加当前开盘价，并处理可能的异常
    open_now_values = []
    for s in stk_list:
        try:
            open_now_values.append(current_data[s].day_open)
        except KeyError as e:
            print(f"警告: 股票 {s} 的数据不可用, 错误: {e}")
            open_now_values.append(None)
    
    df['open_now'] = open_now_values
    
    # 移除那些 'open_now' 是 None 的行
    df = df.dropna(subset=['open_now'])
    
    # 筛选开盘价在 0.95 ~ 1.01 倍 close 的股票
    df = df[(df['open_now'] / df['close']) < 1.01]
    df = df[(df['open_now'] / df['close']) > 0.95]
    
    # 更新 stk_list
    stk_list = list(df.index)
    
    # 排除已持仓的股票
    hold_list = list(context.portfolio.positions)
    stk_list = list(set(stk_list) - set(hold_list))
    
    if len(stk_list) == 0:
        return
    
    # 获取估值数据（包括换手率等）
    df_val = get_valuation(
        stk_list,
        start_date=context.previous_date,
        end_date=context.previous_date,
        fields=['turnover_ratio', 'market_cap', 'circulating_market_cap']
    )
    
    # 确保两个DataFrame的code列都是字符串类型
    df.index = df.index.astype(str)
    df_val['code'] = df_val['code'].astype(str)
    
    # 使用 pd.merge 进行合并
    df_combined = pd.merge(df.reset_index(), df_val, on='code')
    
    # 新增因子：换手率 * 开盘/收盘比值
    df_combined['factor'] = df_combined['turnover_ratio'] * (df_combined['open_now'] / df_combined['close'])
    
    # 按照该因子从大到小排序
    df_sorted = df_combined.sort_values(by='factor', ascending=False)
    
    # 更新今日选股列表
    g.today_list = list(df_sorted['code'])
    
    # 打印股池数量
    log.info(f"股池数: {len(stk_list)}")

def sell(context):
    hold_list = list(context.portfolio.positions)
    if not hold_list:
        return
        
    current_data = get_current_data()
    yesterday = context.previous_date
    
    # 🔧【修复】过滤掉当日买入的股票（T+1限制）
    sellable_list = []
    for s in hold_list:
        pos = context.portfolio.positions[s]
        closeable_amount = getattr(pos, 'closeable_amount', 0)
        
        # 优先使用当日买入记录判断
        if s in g.today_bought_stocks:
            # log.info(f'跳过卖出 {s}: 当日买入，T+1限制')  # 🔧【屏蔽】T+1限制提示
            continue
        elif closeable_amount > 0:  # 只处理可卖数量大于0的股票
            sellable_list.append(s)
        else:
            # 可卖数量为0的股票，跳过卖出
            # log.info(f'跳过卖出 {s}: 可卖数量不足: {closeable_amount}')  # 🔧【屏蔽】可卖数量不足提示
            continue
    
    if not sellable_list:
        log.info('没有可卖出的股票（全部为当日买入）')
        return
    
    # 批量获取持仓股票的历史数据（包括7日均线）
    # 获取过去8天的数据（计算7日均线需要7个数据点，多取一天用于计算）
    hist_data = get_price(
        sellable_list,
        end_date=yesterday,
        frequency='daily',
        fields=['close'],
        count=8,
        panel=False
    )
    
    # 计算7日均线
    ma7_data = hist_data.groupby('code')['close'].apply(lambda x: x.rolling(7).mean().iloc[-1]).to_dict()
    
    # 批量获取昨日涨停数据
    df_history = get_price(
        sellable_list,
        end_date=yesterday,
        frequency='daily',
        fields=['close', 'high_limit'],
        count=1,
        panel=False
    )
    
    df_history['avg_cost'] = [context.portfolio.positions[s].avg_cost for s in sellable_list]
    df_history['price'] = [context.portfolio.positions[s].price for s in sellable_list]
    df_history['high_limit'] = [current_data[s].high_limit for s in sellable_list]
    df_history['low_limit'] = [current_data[s].low_limit for s in sellable_list]
    df_history['last_price'] = [current_data[s].last_price for s in sellable_list]
    df_history['ma7'] = [ma7_data.get(s, 0) for s in sellable_list]  # 添加7日均线数据
    df_history['closeable_amount'] = [context.portfolio.positions[s].closeable_amount for s in sellable_list]  # 添加可卖数量
    
    # 条件1：未涨停
    cond1 = (df_history['last_price'] != df_history['high_limit'])
    
    # 条件2.1：价格跌破7日均线
    cond2_1 = df_history['last_price'] < df_history['ma7']
    
    # 条件2.2：盈利超过0%
    ret_matrix = (df_history['price'] / df_history['avg_cost'] - 1) * 100
    cond2_2 = ret_matrix > 0
    
    # 条件2.3：昨日涨停
    cond2_3 = (df_history['close'] == df_history['high_limit'])
    
    # 组合卖出条件（逻辑或运算）
    sell_condition = cond1 & (cond2_1 | cond2_2 | cond2_3)
    
    # 🔧【修复】生成卖出列表（增加可卖数量检查）
    sell_list = df_history[
        sell_condition & 
        (df_history['last_price'] > df_history['low_limit']) &
        (df_history['closeable_amount'] > 0)  # 确保可卖数量大于0
    ].code.tolist()
    
    # 批量下单
    for s in sell_list:
        pos = context.portfolio.positions[s]
        closeable_amount = pos.closeable_amount
        
        # 🔧【修复】再次检查可卖数量
        if closeable_amount <= 0:
            log.warn(f'跳过卖出 {s}: 可卖数量不足: {closeable_amount}')
            continue
            
        # 🔧【修复】检查股票是否停牌
        if current_data[s].paused:
            log.warn(f'跳过卖出 {s}: 股票停牌')
            continue
        
        # 执行卖出订单
        order = order_target_value(s, 0)
        if order and order.filled > 0:
            g.today_sold_stocks.add(s)  # 🔧【新增】记录当日卖出的股票
            log.info(f'卖出 {s} | 成本价:{pos.avg_cost:.2f} 现价:{pos.price:.2f} 可卖:{closeable_amount}股 成交:{order.filled}股')
        else:
            log.warn(f'卖出失败 {s} | 成本价:{pos.avg_cost:.2f} 现价:{pos.price:.2f} 可卖:{closeable_amount}股')
        print('-'*50)

def buy(context):
    #1 4 12月空仓
    
    #target=g.today_list
    target=filter_stocks_by_b_s(context,g.today_list)
    
    hold_list = list(context.portfolio.positions)
    num=g.stock_num-len(hold_list)
    if num==0:
        return
    target=[x for x in target  if x not in  hold_list][:num]
    if len(target) > 0:
        # 分配资金（等权重买入）
        value=context.portfolio.available_cash
        cash_per_stock = value / num
        current_data = get_current_data()  # 实时数据对象
        for stock in target:
            # 排除停牌和涨跌停无法交易的股票
            if current_data[stock].paused or \
            current_data[stock].last_price==current_data[stock].low_limit or \
            current_data[stock].last_price==current_data[stock].high_limit:
                continue
            order = order_value(stock, cash_per_stock)  # 按金额买入[6](@ref)
            if order and order.filled > 0:
                g.today_bought_stocks.add(stock)  # 🔧【新增】记录当日买入的股票
                log.info (f"买入 {stock} 成交:{order.filled}股")
            # else:
            #     log.warn(f"买入失败 {stock}")  # 🔧【屏蔽】买入失败提示
                
#----------------函数群--------------------------------------------------/    
def filter_stocks_by_b_s(context,stock_list):
    """
    根据集合竞价买卖力量差(b_s)过滤股票列表，只返回b_s>0的股票
    """
    date= context.current_dt.strftime("%Y-%m-%d")
    
    valid_stocks = []  # 符合条件的股票列表
    auction_data = {}   # 存储股票对应的b_s值
    
    for stock in stock_list:

        # 获取当日集合竞价数据
        auction_df = get_call_auction(stock, start_date=date, end_date=date)
        
        if auction_df is None or auction_df.empty:
            continue
            
        # 使用.assign()避免链式赋值警告
        auction_df = auction_df.assign(
            sellmoney=lambda df: 
                df['a1_p']*df['a1_v'] + 
                df['a2_p']*df['a2_v'] + 
                df['a3_p']*df['a3_v'] + 
                df['a4_p']*df['a4_v'] + 
                df['a5_p']*df['a5_v'],
            
            buymoney=lambda df: 
                df['b1_p']*df['b1_v'] + 
                df['b2_p']*df['b2_v'] + 
                df['b3_p']*df['b3_v'] + 
                df['b4_p']*df['b4_v'] + 
                df['b5_p']*df['b5_v']
        )
        
        # 计算b_s值
        auction_df = auction_df.assign(
            b_s=lambda df: (df['buymoney'] - df['sellmoney']) / df['sellmoney']
        )
        
        # 只保留b_s > 0的股票
        if not auction_df.empty and auction_df['b_s'].iloc[0] > 0:
            valid_stocks.append(stock)
            auction_data[stock] = auction_df['b_s'].iloc[0]
        
    return valid_stocks

def today_is_between(context):
        today = context.current_dt.strftime('%m-%d')
        if ('01-15' <= today) and (today <= '01-31'):
            return True
        elif ('04-15' <= today) and (today <= '04-31'):
            return True     
        elif ('12-15' <= today) and (today <= '12-31'):
            return True 
        else:
            return False
##获取中小综指399101成分股并过滤ST股##               
def get_st(context):
    # 获取中小综指399101.XSHE成分股
    stocks = get_index_stocks('399101.XSHE', date=context.previous_date)
    
    # 过滤ST股
    st_data = get_extras('is_st', stocks, count=1, end_date=context.previous_date)
    st_data = st_data.T
    st_data.columns = ['is_st']
    # 保留非ST股
    st_data = st_data[st_data['is_st'] == False]
    filtered_stocks = st_data.index.tolist()
    
    return filtered_stocks    

##处理日期相关函数##
def get_shifted_date(date, days, days_type='T'):
    #获取上一个自然日
    d_date = transform_date(date, 'd')
    yesterday = d_date + dt.timedelta(-1)
    #移动days个自然日
    if days_type == 'N':
        shifted_date = yesterday + dt.timedelta(days+1)
    #移动days个交易日
    if days_type == 'T':
        all_trade_days = [i.strftime('%Y-%m-%d') for i in list(get_all_trade_days())]
        #如果上一个自然日是交易日，根据其在交易日列表中的index计算平移后的交易日        
        if str(yesterday) in all_trade_days:
            shifted_date = all_trade_days[all_trade_days.index(str(yesterday)) + days + 1]
        #否则，从上一个自然日向前数，先找到最近一个交易日，再开始平移
        else:
            for i in range(100):
                last_trade_date = yesterday - dt.timedelta(i)
                if str(last_trade_date) in all_trade_days:
                    shifted_date = all_trade_days[all_trade_days.index(str(last_trade_date)) + days + 1]
                    break
                
    return str(shifted_date)
##处理日期相关函数##
def transform_date(date, date_type):
    if type(date) == str:
        str_date = date
        dt_date = dt.datetime.strptime(date, '%Y-%m-%d')
        d_date = dt_date.date()
    elif type(date) == dt.datetime:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = date
        d_date = dt_date.date()
    elif type(date) == dt.date:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = dt.datetime.strptime(str_date, '%Y-%m-%d')
        d_date = date
    dct = {'str':str_date, 'dt':dt_date, 'd':d_date}
    return dct[date_type]    
##筛选不涨停##   
def get_ever_hl_stock(initial_list, date):#
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','high','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna() #去除停牌
    cd2 = df['close'] != df['high_limit']
    df = df[cd2]
    hl_list = list(df.code)
    return hl_list        
##筛选出涨停的股票##
def get_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','low','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna() #去除停牌
    df = df[df['close'] == df['high_limit']]
    hl_list = list(df.code)
    return hl_list

##筛选昨日不涨停的股票##
def rzq_list(context,initial_list): 
    # 文本日期
    date = context.previous_date #昨日
    date = transform_date(date, 'str')
    date_1=get_shifted_date(date, -1, 'T')#前日
    date_2=get_shifted_date(date, -2, 'T')#大前日
    # 昨日不涨停
    h1_list = get_ever_hl_stock(initial_list, date)
    # 前日涨停过滤
    elements_to_remove = get_hl_stock(initial_list, date_1)
    zb_list = [stock for stock in h1_list if stock  in elements_to_remove]

    return zb_list
    
##技术指标筛选##
def filter_stocks(context, stocks):
    yesterday = context.previous_date
    df = get_price(
        stocks,
        count=11,
        frequency='1d',
        fields=['close', 'low', 'volume'],
        end_date=yesterday,
        panel=False
    ).reset_index()
    
    # 按股票分组处理
    valid_stocks = []
    for code, group in df.groupby('code'):
        if len(group) < 11:  # 确保有足够的数据
            continue
            
        # 计算技术指标
        group = group.copy()
        group['ma10'] = group['close'].rolling(10).mean()
        group['prev_low'] = group['low'].shift(1)
        group['prev_volume'] = group['volume'].shift(1)
        
        # 获取最后一行数据
        last_row = group.iloc[-1]
        
        # 检查条件
        conditions_met = (
            not pd.isna(last_row['ma10']) and
            not pd.isna(last_row['prev_low']) and
            not pd.isna(last_row['prev_volume']) and
            last_row['close'] > last_row['prev_low'] and
            last_row['close'] > last_row['ma10'] and
            last_row['volume'] > last_row['prev_volume'] and
            last_row['volume'] < 10 * last_row['prev_volume'] and
            last_row['close'] > 1
        )
        
        if conditions_met:
            valid_stocks.append(code)
    
    return valid_stocks
            


##国九条筛选##
def GJT_filter_stocks(stocks):
    # 国九更新：过滤近一年净利润为负且营业收入小于1亿的
    # 国九更新：过滤近一年期末净资产为负的 (经查询没有为负数的，所以直接pass这条)
    q = query(
        valuation.code,
        valuation.market_cap,  # 总市值 circulating_market_cap/market_cap
        income.np_parent_company_owners,  # 归属于母公司所有者的净利润
        income.net_profit,  # 净利润
        income.operating_revenue  # 营业收入
        #security_indicator.net_assets
    ).filter(
        valuation.code.in_(stocks),
        income.np_parent_company_owners > 0,
        income.net_profit > 0,
        income.operating_revenue > 1e8,
        indicator.roe>0,
        indicator.roa>0,
    )
    df = get_fundamentals(q)

    final_list=list(df.code)
            
    return final_list

def dieting(context):
    current_data = get_current_data()
    for s in list(context.portfolio.positions) :
        if s not in  g.dieting:
            dtj=current_data[s].low_limit
            zxj=current_data[s].last_price
            if zxj==dtj and (context.portfolio.positions[s].closeable_amount != 0):
                if s not in g.dieting:
                    g.dieting.append(s)
    g.dieting=list(set(g.dieting))
    if len(g.dieting)>0:
        #print(g.dieting)
        for s in g.dieting[:]:  # 遍历副本以安全移除元素
            dtj=current_data[s].low_limit
            zxj=current_data[s].last_price
            if zxj>dtj:
                # 🔧【修复】检查可卖数量和停牌状态
                pos = context.portfolio.positions[s]
                closeable_amount = pos.closeable_amount
                
                if closeable_amount <= 0:
                    log.warn(f'跌停打开跳过卖出 {s}: 可卖数量不足: {closeable_amount}')
                    g.dieting.remove(s)  # 移除不可卖的股票
                    continue
                    
                if current_data[s].paused:
                    log.warn(f'跌停打开跳过卖出 {s}: 股票停牌')
                    continue
                
                # 执行卖出订单
                order = order_target_value(s, 0)
                if order and order.filled > 0:
                    g.today_sold_stocks.add(s)  # 🔧【新增】记录当日卖出的股票
                    log.info(f"跌停打开卖出:{s} 成交:{order.filled}股")
                else:
                    log.warn(f"跌停打开卖出失败:{s} 可卖:{closeable_amount}股")
                g.dieting.remove(s)  # 卖出后移除

def daily_trading_report(context):
    """🔧【新增】每日交易报告：股票买卖和持仓情况、收益率"""
    try:
        # 获取当前日期
        current_date = context.current_dt.strftime('%Y-%m-%d')
        
        # 计算总资产和现金
        total_value = context.portfolio.total_value
        cash = context.portfolio.cash
        invested_value = total_value - cash
        
        # 计算当日收益
        if g.last_total_value > 0:
            daily_return = total_value - g.last_total_value
            daily_return_pct = (daily_return / g.last_total_value * 100) if g.last_total_value > 0 else 0
        else:
            daily_return = 0
            daily_return_pct = 0
        
        # 更新昨日总资产记录
        g.last_total_value = total_value
        
        # 输出总体情况
        log.info(f"📊【{current_date} 交易报告】")
        log.info(f"💰 总资产: {total_value:,.2f}元 | 现金: {cash:,.2f}元 | 已投资: {invested_value:,.2f}元")
        log.info(f"📈 当日收益: {daily_return:+,.2f}元 ({daily_return_pct:+.2f}%)")
        
        # 输出当日买卖情况
        if g.today_bought_stocks:
            log.info(f"📈【当日买入】{len(g.today_bought_stocks)}只: {', '.join(g.today_bought_stocks)}")
        else:
            log.info("📈【当日买入】无")
            
        if g.today_sold_stocks:
            log.info(f"📉【当日卖出】{len(g.today_sold_stocks)}只: {', '.join(g.today_sold_stocks)}")
        else:
            log.info("📉【当日卖出】无")
        
        # 计算持仓股票信息
        positions_info = []
        total_position_value = 0
        
        for code, pos in context.portfolio.positions.items():
            if pos.total_amount > 0:  # 只统计有持仓的股票
                try:
                    # 获取股票名称
                    stock_info = get_security_info(code)
                    stock_name = stock_info.display_name if stock_info else code
                    
                    # 计算持仓信息
                    position_value = pos.value
                    position_shares = pos.total_amount
                    avg_cost = pos.avg_cost
                    current_price = pos.price
                    
                    # 计算盈亏
                    if avg_cost > 0:
                        profit_loss = (current_price - avg_cost) * position_shares
                        profit_loss_pct = (current_price / avg_cost - 1) * 100
                    else:
                        profit_loss = 0
                        profit_loss_pct = 0
                    
                    positions_info.append({
                        'code': code,
                        'name': stock_name,
                        'shares': position_shares,
                        'avg_cost': avg_cost,
                        'current_price': current_price,
                        'value': position_value,
                        'profit_loss': profit_loss,
                        'profit_loss_pct': profit_loss_pct
                    })
                    
                    total_position_value += position_value
                    
                except Exception as e:
                    log.warn(f"获取股票{code}信息失败: {e}")
                    continue
        
        # 输出持仓详情
        if positions_info:
            log.info(f"📋【持仓详情】共{len(positions_info)}只股票")
            for pos in positions_info:
                profit_loss_str = f"{pos['profit_loss']:+,.2f}元 ({pos['profit_loss_pct']:+.2f}%)"
                log.info(f"  {pos['name']}({pos['code']}): {pos['shares']}股 | 成本:{pos['avg_cost']:.2f} | 现价:{pos['current_price']:.2f} | 市值:{pos['value']:,.2f}元 | 盈亏:{profit_loss_str}")
        else:
            log.info("📋【持仓详情】当前无持仓")
        
        # 输出跌停监控情况
        if g.dieting:
            log.info(f"⚠️【跌停监控】{len(g.dieting)}只股票跌停: {', '.join(g.dieting)}")
        else:
            log.info("✅【跌停监控】无跌停股票")
        
        log.info("=" * 80)  # 分隔线
        
    except Exception as e:
        log.error(f"生成每日交易报告失败: {e}")