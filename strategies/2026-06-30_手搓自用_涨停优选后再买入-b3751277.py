# Clone from JoinQuant
# postId: b37512770de081208c7e95b59b727e7e
# backtestId: 57bae63af0196f1cfc95972c6063d042
# title: 【手搓自用】涨停优选后再买入

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time

from scipy.stats import linregress
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import BayesianRidge

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
    g.stock_num = 5
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
    
    # 在全局变量中定义自定义因子参数
    g.custom_factor_params = {
        'momentum_window': 14,
        'slope_window': 10,
        'ma_window': 10,
        'rsrs_window': 14,
        'volatility_window': 10
    }
    
    g.factor_list = [
                'circulating_market_cap',
                'liquidity', 
                'VDIFF', 
                'VEMA26', 
                'WVAD', 
                'Rank1M',
                'money_flow_20',
                'price_no_fq', #技术指标因子 不复权价格因子
                'total_profit_to_cost_ratio', #质量类因子 成本费用利润率
                'debt_to_assets', #风格因子 资产负债率
                'operating_cost_to_operating_revenue_ratio', #质量类因子 销售成本率
                'DAVOL20', #情绪类因子 20日平均换手率与120日平均换手率之比
                'sales_growth', #风格因子 5年营业收入增长率
                # 新增自定义技术因子
                'momentum_14',
                'slope_r2_10',
                'ma_cross_10',
                'rsrs_14',
                'volatility_10',
                'turnover_rate',
                'industry_momentum',  # 新增行业动量因子
                'industry_strength'   # 新增行业强度因子
            ]

def calculate_custom_factors_batch(stock_list, end_date):
    """批量计算自定义技术因子（优化：单次API调用替代逐股调用）"""
    max_window = max(g.custom_factor_params.values())
    
    prices_df = get_price(stock_list, 
                         count=max_window + 10,
                         end_date=end_date, 
                         frequency='daily',
                         fields=['close', 'high', 'low', 'volume'],
                         skip_paused=True,
                         panel=False)
    
    cap_data = get_fundamentals(
        query(valuation.code, valuation.circulating_cap)
        .filter(valuation.code.in_(stock_list)),
        date=end_date
    ).set_index('code')
    
    result = {}
    grouped = prices_df.groupby('code')
    for stock, group in grouped:
        try:
            group = group.sort_values('time')
            if len(group) < max_window + 1:
                continue
            
            close = group['close'].values
            high = group['high'].values
            low = group['low'].values
            volume = group['volume'].values
            
            factors = {}
            factors['momentum_14'] = (close[-1] / close[-g.custom_factor_params['momentum_window']-1] - 1) * 100
            
            x = np.arange(g.custom_factor_params['slope_window'])
            y = close[-g.custom_factor_params['slope_window']:]
            slope, _, r_value, _, _ = linregress(x, y)
            factors['slope_r2_10'] = slope * (r_value ** 2)
            
            ma = np.mean(close[-g.custom_factor_params['ma_window']:])
            factors['ma_cross_10'] = 1 if close[-1] > ma else 0
            
            beta_list = []
            for i in range(g.custom_factor_params['rsrs_window']):
                h = high[-(g.custom_factor_params['rsrs_window'] - i)]
                l = low[-(g.custom_factor_params['rsrs_window'] - i)]
                s, _, r, _, _ = linregress([0, 1], [l, h])
                beta_list.append(s * r)
            factors['rsrs_14'] = np.mean(beta_list)
            
            returns = np.diff(close[-g.custom_factor_params['volatility_window']:]) / close[-g.custom_factor_params['volatility_window']:-1]
            factors['volatility_10'] = np.std(returns) if len(returns) > 0 else 0
            
            if stock in cap_data.index and cap_data.loc[stock, 'circulating_cap'] > 0:
                avg_volume = np.mean(volume[-20:])
                factors['turnover_rate'] = avg_volume / cap_data.loc[stock, 'circulating_cap'] * 100
            else:
                factors['turnover_rate'] = np.nan
            
            result[stock] = factors
        except Exception as e:
            continue
    
    return result

def get_factor_data(securities_list, date):
    """获取因子数据，包含基础因子和自定义技术因子（优化：批量API调用）"""
    factor_data = get_factor_values(securities=securities_list,
                                    factors=g.factor_list[:13],
                                    count=1,
                                    end_date=date)
    df_jq_factor = pd.DataFrame(index=securities_list)
    for i in factor_data.keys():
        df_jq_factor[i] = factor_data[i].iloc[0, :]
    
    # 批量计算自定义技术因子（单次API调用）
    custom_factors = ['momentum_14', 'slope_r2_10', 'ma_cross_10', 'rsrs_14', 'volatility_10', 'turnover_rate']
    for factor in custom_factors:
        df_jq_factor[factor] = np.nan
    
    custom_results = calculate_custom_factors_batch(securities_list, date)
    for stock, factors in custom_results.items():
        for factor, value in factors.items():
            df_jq_factor.at[stock, factor] = value
    
    # 批量获取行业分类（单次API调用替代逐股调用）
    industry_raw = get_industry(securities_list, date=date)
    industry_map = {}
    industry_stocks = {}
    for stock in securities_list:
        info = industry_raw.get(stock, {})
        industry_code = info.get('jq_l1', {}).get('industry_code', 'Unknown') if isinstance(info.get('jq_l1'), dict) else 'Unknown'
        industry_map[stock] = industry_code
        if industry_code not in industry_stocks:
            industry_stocks[industry_code] = []
        industry_stocks[industry_code].append(stock)
    
    # 一次性获取所有股票20日价格用于行业动量计算
    all_prices_df = get_price(securities_list, end_date=date, count=21, fields=['close'], panel=False)
    all_prices = all_prices_df.pivot(index='time', columns='code', values='close')
    all_returns = all_prices.iloc[-1] / all_prices.iloc[0] - 1
    
    industry_momentum = {}
    for industry_code, stocks in industry_stocks.items():
        valid_stocks = [s for s in stocks if s in all_returns.index]
        industry_momentum[industry_code] = all_returns[valid_stocks].mean() if valid_stocks else 0
    
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(securities_list))
    cap_df = get_fundamentals(q, date=date)
    if cap_df is not None and not cap_df.empty:
        cap_df = cap_df.set_index('code')
        top_30pct = cap_df.sort_values('market_cap', ascending=False).iloc[:int(len(cap_df)*0.3)]
    else:
        top_30pct = pd.DataFrame()
    
    industry_strength = {}
    for industry_code, stocks in industry_stocks.items():
        if not top_30pct.empty:
            industry_top_count = len(set(stocks) & set(top_30pct.index))
            industry_strength[industry_code] = industry_top_count / len(stocks) if len(stocks) > 0 else 0
        else:
            industry_strength[industry_code] = 0
    
    for stock in securities_list:
        industry_code = industry_map.get(stock, 'Unknown')
        df_jq_factor.at[stock, 'industry_momentum'] = industry_momentum.get(industry_code, 0)
        df_jq_factor.at[stock, 'industry_strength'] = industry_strength.get(industry_code, 0)
    
    return df_jq_factor, industry_map

def preprocess_factors(df, date, industry_map=None):
    """因子预处理：缺失值填充、去极值、标准化（优化：复用行业数据）"""
    if industry_map is None:
        industry_raw = get_industry(list(df.index), date=date)
        industry_map = {}
        for stock in df.index:
            info = industry_raw.get(stock, {})
            industry_map[stock] = info.get('jq_l1', {}).get('industry_code', 'Unknown') if isinstance(info.get('jq_l1'), dict) else 'Unknown'
    
    for factor in g.factor_list:
        # 按行业分组填充
        df[factor] = df.groupby(industry_map)[factor].transform(
            lambda x: x.fillna(x.median()))
        
        # 全局填充
        df[factor].fillna(df[factor].median(), inplace=True)
    
    # 2. 去极值 - MAD方法
    for factor in g.factor_list:
        median = df[factor].median()
        mad = (df[factor] - median).abs().median()
        # 如果mad为0（比如因子值全部相同），则跳过去极值
        if mad > 0:
            upper_bound = median + 3 * 1.4826 * mad
            lower_bound = median - 3 * 1.4826 * mad
            df[factor] = df[factor].clip(lower_bound, upper_bound)
    
    # 3. 标准化
    scaler = StandardScaler()
    scaled_values = scaler.fit_transform(df[g.factor_list])
    df[g.factor_list] = scaled_values
    
    return df

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


def get_highlimit_and_startpoint(context, stock_list, days=3*250, p=0.10):
    """合并涨停筛选和启动点计算（优化：共享同一次API调用）"""
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["open", "low", "close", "high_limit"],
        count=days,
        panel=False,
        fill_paused=False,
    )
    
    # --- 第一步：涨停频率筛选 ---
    limit_df = df[df["close"] == df["high_limit"]]
    grouped_result = limit_df.groupby('code').size().reset_index(name='count')
    grouped_result = grouped_result.sort_values(by=["count"], ascending=False)
    highlimit_list = grouped_result["code"].tolist()[:int(len(grouped_result)*p)]
    log.info(f"筛选前合计{len(grouped_result)}个， 筛选后合计{len(highlimit_list)}个")
    
    # --- 第二步：在筛选后的股票中计算启动点 ---
    filtered_df = df[df['code'].isin(highlimit_list)]
    stock_start_point = {}
    stock_price_bias = {}
    current_data = get_current_data()
    
    for code, group in filtered_df.groupby('code'):
        group = group.sort_values('time')
        limit_hit_rows = group[group['close'] == group['high_limit']]
        if not limit_hit_rows.empty:
            latest_limit_hit = limit_hit_rows.iloc[-1]
            latest_limit_index = latest_limit_hit.name
            previous_rows = group[group.index <= latest_limit_index].iloc[::-1]
            for idx, row in previous_rows.iterrows():
                if row['close'] < row['open']:
                    stock_start_point[code] = row['low']
                    break
    
    for code, start_point in stock_start_point.items():
        last_price = current_data[code].last_price
        stock_price_bias[code] = last_price / start_point
    
    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)
    return [i[0] for i in sorted_list]
    
def rank_stocks(context, initial_list):
    # === 新增：每月训练判断 ===
    # 获取当前月份和上个月份
    current_month = context.current_dt.month
    previous_month = context.previous_date.month if hasattr(context, 'previous_date') else current_month
    
    # 如果是每月第一个交易日且月份发生变化，或者尚未初始化，则进行训练
    if not hasattr(g, 'last_training_month') or g.last_training_month != current_month:
        # 更新最后训练月份
        g.last_training_month = current_month
        should_train = True
    else:
        should_train = False
    
    # 使用更长的历史数据
    N = 60  # 使用60天数据
    trade_days = get_trade_days(end_date=context.previous_date, count=6*N)
    dateList = trade_days[::N][-6:].tolist()  # 转换为列表
    
    # 使用更稳健的标签定义
    train_data = pd.DataFrame()
    
    # === 修改：只有需要训练时才执行数据准备和模型训练 ===
    if should_train:
        log.info(f"本月首次训练，当前月份：{current_month}")
        for i in range(len(dateList)-1):
            date = dateList[i]
            
            # 获取未来30个自然日后的日期
            from datetime import timedelta
            future_date = date + timedelta(days=7)  # 30个自然日后
            
            # 获取future_date之后最近的交易日
            future_trade_days = get_trade_days(start_date=date, end_date=future_date)
            if len(future_trade_days) == 0:
                continue
            
            # 找到距离future_date最近的交易日
            target_date = None
            for d in future_trade_days:
                if d > date:  # 确保是未来的交易日
                    if target_date is None or abs((d - future_date).days) < abs((target_date - future_date).days):
                        target_date = d
            
            if target_date is None:
                continue
            
            # 确保目标日期在当前日期之后
            if target_date <= date:
                continue
                
            factor_data, ind_map = get_factor_data(initial_list, date)
            factor_data = preprocess_factors(factor_data, date, ind_map)
            
            # 计算未来30个自然日（最近交易日）的收益率
            try:
                price_start_df = get_price(initial_list, start_date=date, end_date=date, frequency='1d', fields=['close'], panel=False)
                price_start = price_start_df.set_index('code')['close']
                price_end_df = get_price(initial_list, start_date=target_date, end_date=target_date, frequency='1d', fields=['close'], panel=False)
                price_end = price_end_df.set_index('code')['close']
                
                returns = (price_end / price_start - 1).rename('return')
                
                # 合并因子和收益率
                data = factor_data.join(returns)
                train_data = pd.concat([train_data, data])
            except Exception as e:
                log.warning(f"计算未来30天收益率失败 {date}: {str(e)}")
                continue
        
        if train_data.empty:
            log.warning("训练数据为空，使用原始股票列表")
            return initial_list
        
        # 使用分位数定义标签
        train_data['label'] = (train_data['return'] > 0.05).astype(int)
        
        # 模型训练
        X_train = train_data[g.factor_list]
        y_train = train_data['label']
        
        # 处理可能的NaN值
        X_train = X_train.fillna(0)
        
        if X_train.empty or len(X_train) < 5:
            log.warning("训练数据不足，使用原始股票列表")
            return initial_list
        
        # 使用贝叶斯岭回归
        model = BayesianRidge()
        model.fit(X_train, y_train)
        
        # 保存模型到全局变量
        g.trained_model = model
        log.info("模型训练完成并保存")
    
    # === 修改：使用保存的模型或新训练的模型 ===
    if hasattr(g, 'trained_model'):
        model = g.trained_model
        log.info("使用已保存的模型进行预测")
    else:
        log.warning("无可用模型，使用原始股票列表")
        return initial_list
    
    # 获取当前因子数据
    current_data, cur_ind_map = get_factor_data(initial_list, context.previous_date)
    if current_data.empty:
        return initial_list
    
    current_data = preprocess_factors(current_data, context.previous_date, cur_ind_map)
    current_data = current_data.fillna(0)
    
    # 预测
    predictions, std_dev = model.predict(current_data[g.factor_list], return_std=True)
    confidence_intervals = 1.96 * std_dev

    current_data['total_score'] = predictions
    current_data['confidence_interval'] = confidence_intervals
    current_data['confidence_interval'] = current_data['confidence_interval'].clip(upper=1).fillna(1)
    
    # 标准化
    scaler = StandardScaler()
    if len(current_data) > 1:  # 需要至少2个样本进行标准化
        current_data['normalized_score'] = scaler.fit_transform(current_data[['total_score']])
        current_data['normalized_confidence'] = scaler.fit_transform(current_data[['confidence_interval']])
        
        # 计算 AI_score
        current_data['AI_score'] = current_data['normalized_score'] - current_data['normalized_confidence']
    else:
        # 如果只有一个股票，直接使用原始分数
        current_data['AI_score'] = current_data['total_score']
    
    # 结合基本面过滤
    roic = get_factor_values(initial_list, 'roic_ttm', 
                           end_date=context.previous_date,
                           count=1)['roic_ttm'].iloc[0]
    current_data.loc[roic < 0.1, 'AI_score'] = -10  # ROIC低于8%的排除
    
    # 生成最终排序
    current_data = current_data.sort_values('AI_score', ascending=False)
    return current_data.index.tolist()

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
    
    initial_list = get_highlimit_and_startpoint(context, initial_list, g.limit_days_window)

    stock_list = get_stock_industry(initial_list)
    stock_list = rank_stocks(context, stock_list)
    final_list = stock_list[:g.stock_num]
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
        target_list = g.target_list[:g.stock_num]
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

            
# 换手检测（优化：批量获取数据，减少API调用）
def huanshou(context):
    current_data = get_current_data()
    date_now = context.current_dt
    date_pre = context.previous_date
    shrink, expand = 0.003, 0.1
    
    check_stocks = []
    for stock in context.portfolio.positions:
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        check_stocks.append(stock)
    
    if not check_stocks:
        return
    
    # 批量获取20日历史成交量
    df_hist_vol = get_price(check_stocks, end_date=date_pre, frequency='daily',
                            fields=['volume'], count=20, panel=False)
    # 批量获取当日分钟成交量
    df_today_vol = get_price(check_stocks, start_date=date_now.date(), end_date=date_now,
                             frequency='1m', fields=['volume'], skip_paused=False, fq='pre',
                             panel=False, fill_paused=False)
    # 批量获取流通股本
    df_cap = get_fundamentals(
        query(valuation.code, valuation.circulating_cap).filter(valuation.code.in_(check_stocks)),
        date=date_pre
    ).set_index('code')
    
    for stock in check_stocks:
        cap = df_cap.loc[stock, 'circulating_cap'] if stock in df_cap.index else 0
        if cap == 0:
            continue
        
        stock_hist = df_hist_vol[df_hist_vol['code'] == stock]['volume']
        avg_vol = stock_hist.mean() if len(stock_hist) > 0 else 0
        avg = avg_vol / (cap * 10000) if cap > 0 else 0
        
        stock_today = df_today_vol[df_today_vol['code'] == stock]['volume']
        today_vol = stock_today.sum() if len(stock_today) > 0 else 0
        rt = today_vol / (cap * 10000) if cap > 0 else 0
        
        if avg == 0:
            continue
        r = rt / avg
        action, icon = '', ''
        if avg < shrink:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        if action:
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"{action} {stock} {get_security_info(stock).display_name} 换手率:{rt:.2%}→均:{avg:.2%} {icon} close_position: {r}")
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
    

        