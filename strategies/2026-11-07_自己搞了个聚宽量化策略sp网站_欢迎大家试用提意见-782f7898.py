# Clone from JoinQuant
# postId: 782f7898b691f6ead637b5bfe2474bd1
# backtestId: c6977da24fa2b6cf65f63a5b5082a0d4
# title: 自己搞了个聚宽量化策略sp网站，欢迎大家试用提意见

# 克隆自聚宽文章：https://www.joinquant.com/post/60657
# 标题：上半年用的好好的二进三策略最近不太行了
# 作者：拐爹

from jqdata import *
from jqfactor import *
from jqlib.technical_analysis import *
import datetime as dt
import pandas as pd
from datetime import datetime
from datetime import timedelta


def initialize(context):
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    set_option('avoid_future_data', True)
    
    # 初始化全局变量
    g.target_stocks = []
    g.trading_day_count = 0  # 记录交易天数
    g.new_high_days = 250    # 可修改参数：创新高的天数（可改为120、60等）
    
    # 修改后的策略
    run_daily(get_stock_list, '9:25')      # 9:25选股
    run_daily(buy_stocks, '09:27')         # 9:27下单
    run_daily(sell_low_gain, '10:30')      # 次日10:30卖出涨幅低于5%的
    run_daily(sell_non_limit_up, '14:50')  # 14:50卖出没涨停的


# 选股函数
def get_stock_list(context):
    """9:25选股"""
    date = context.previous_date
    
    # 获取基础股票池
    initial_list = prepare_stock_list(date)
    
    # 条件1: 前2日涨停
    recent_zt = get_recent_zt_stocks(initial_list, date, days=2)
    
    if not recent_zt:
        g.target_stocks = []
        print("近2日无涨停股票")
        return
    
    print(f"近2日涨停股票数量: {len(recent_zt)}")
    print(f"当前使用创{g.new_high_days}日新高条件")
    
    # 获取当前数据用于后续筛选
    current_data = get_current_data()
    date_now = context.current_dt.strftime("%Y-%m-%d")
    
    qualified_stocks = []
    
    for stock in recent_zt:
        try:
            # 条件1: 检查是否创指定天数新高
            if not is_n_day_high(stock, date, g.new_high_days):
                print(f"股票 {stock} 未创{g.new_high_days}日新高")
                continue
            
            # 条件2: 前一日成交量大于前5日平均成交量，且成交额在1-100亿之间
            volume_data = attribute_history(stock, 6, '1d', 
                                          fields=['volume', 'money'], 
                                          skip_paused=True)
            if volume_data.empty or len(volume_data) < 6:
                print(f"股票 {stock} 成交量数据不足")
                continue
            
            # 昨日成交量和成交额
            yesterday_volume = volume_data['volume'][-1]
            yesterday_money = volume_data['money'][-1]
            # 前5日平均成交量
            avg_volume_5d = volume_data['volume'][:-1].mean()
            
            # 成交量条件：昨日成交量 > 前5日平均成交量
            if yesterday_volume <= avg_volume_5d:
                print(f"股票 {stock} 未放量，昨日成交量: {yesterday_volume/1e8:.2f}亿股，前5日平均: {avg_volume_5d/1e8:.2f}亿股")
                continue
            
            # 成交额条件：1亿 < 成交额 < 100亿
            if yesterday_money < 5e8 or yesterday_money > 100e8:
                print(f"股票 {stock} 成交额不符合条件: {yesterday_money/1e8:.2f}亿")
                continue
            
            # 新增条件：流通市值在10亿到200亿之间
            valuation_data = get_valuation(stock, 
                                         start_date=context.previous_date, 
                                         end_date=context.previous_date, 
                                         fields=['circulating_market_cap'])
            if valuation_data.empty:
                print(f"股票 {stock} 无估值数据")
                continue
                
            circulating_cap = valuation_data['circulating_market_cap'][0]
            if circulating_cap < 10 or circulating_cap > 200:
                print(f"股票 {stock} 流通市值不符合条件: {circulating_cap:.2f}亿")
                continue
            
            # 条件3: 今日9:25分涨幅在3%到8%之间
            try:
                auction_data = get_call_auction(stock, start_date=date_now, end_date=date_now, 
                                              fields=['time', 'volume', 'current'])
                
                if auction_data.empty:
                    print(f"股票 {stock} 无集合竞价数据")
                    continue
                
                # 获取集合竞价价格
                current_price = auction_data['current'][0]
                
                # 如果集合竞价价格为0或无效，跳过
                if current_price <= 0:
                    print(f"股票 {stock} 集合竞价价格无效: {current_price}")
                    continue
                    
            except Exception as e:
                print(f"股票 {stock} 集合竞价数据获取失败: {e}")
                continue
            
            # 计算涨幅
            yesterday_close_data = attribute_history(stock, 1, '1d', 
                                                   fields=['close'], 
                                                   skip_paused=True)
            if yesterday_close_data.empty:
                print(f"股票 {stock} 无昨日收盘价数据")
                continue
                
            yesterday_close = yesterday_close_data['close'][0]
            increase_ratio = (current_price - yesterday_close) / yesterday_close
            
            # 涨幅条件：3%-8%
            if increase_ratio < 0.03 or increase_ratio > 0.08:
                print(f"股票 {stock} 涨幅不符合条件: {increase_ratio*100:.2f}%")
                continue
            
            # 所有条件都满足，加入候选列表
            qualified_stocks.append({
                'stock': stock,
                'current_price': current_price,
                'increase_ratio': increase_ratio,
                'yesterday_money': yesterday_money,
                'volume_ratio': yesterday_volume / avg_volume_5d,
                'circulating_cap': circulating_cap
            })
            
            print(f"股票 {stock} 符合所有条件")
            
        except Exception as e:
            print(f"处理股票 {stock} 时出错: {e}")
            continue
    
    if not qualified_stocks:
        g.target_stocks = []
        print("今日无符合所有条件的股票")
        return
    
    # 按价格从低到高排序，选择前5只
    qualified_stocks.sort(key=lambda x: x['current_price'])
    g.target_stocks = [item['stock'] for item in qualified_stocks[:5]]
    
    # 打印选股结果
    print('———————————————————————————————————')
    print(f'选股结果（共{len(g.target_stocks)}只，按价格从低到高排序）:')
    print(f'筛选条件：近2日涨停 + 创{g.new_high_days}日新高')
    for i, item in enumerate(qualified_stocks[:5]):
        try:
            stock_info = get_security_info(item['stock'])
            print(f'{i+1}. {item["stock"]} {stock_info.display_name}')
            print(f'   集合竞价: {item["current_price"]:.2f}')
            print(f'   今日涨幅: {item["increase_ratio"]*100:.2f}%')
            print(f'   成交金额: {item["yesterday_money"]/1e8:.2f}亿')
            print(f'   放量倍数: {item["volume_ratio"]:.2f}')
            print(f'   流通市值: {item["circulating_cap"]:.2f}亿')
        except Exception as e:
            print(f'打印股票信息时出错: {e}')
    print('———————————————————————————————————')


def get_recent_zt_stocks(stock_list, date, days=2):
    """获取最近N日内涨停的股票"""
    if not stock_list:
        return []
    
    zt_stocks = set()
    
    try:
        # 获取最近N天的数据
        df = get_price(stock_list, end_date=date, frequency='daily', 
                      fields=['close', 'high_limit'], count=days, 
                      panel=False, fill_paused=False, skip_paused=False)
        
        if df.empty:
            print("获取价格数据为空")
            return []
        
        # 重置索引，将时间索引转换为列
        df_reset = df.reset_index()
        
        # 按日期分组检查每一天的涨停股票
        for trade_date in df_reset['time'].unique():
            day_data = df_reset[df_reset['time'] == trade_date]
            
            if day_data.empty:
                continue
                
            # 删除NaN值
            day_data = day_data.dropna(subset=['close', 'high_limit'])
            
            if day_data.empty:
                continue
            
            # 涨停判断：收盘价等于涨停价（允许0.01的误差）
            day_zt = day_data[abs(day_data['close'] - day_data['high_limit']) < 0.01]
            
            # 将当天涨停的股票加入集合
            if not day_zt.empty:
                zt_stocks.update(day_zt['code'].tolist())
                print(f"{trade_date.strftime('%Y-%m-%d')} 涨停股票数量: {len(day_zt)}")
            else:
                print(f"{trade_date.strftime('%Y-%m-%d')} 涨停股票数量: 0")
        
        result = list(zt_stocks)
        print(f"近{days}日涨停股票总数（去重后）: {len(result)}")
        return result
        
    except Exception as e:
        print(f"获取近{days}日涨停股票时出错: {e}")
        # 如果出错，尝试逐日获取
        return get_recent_zt_stocks_fallback(stock_list, date, days)


def get_recent_zt_stocks_fallback(stock_list, date, days=2):
    """备用方案：逐日获取涨停股票"""
    if not stock_list:
        return []
    
    zt_stocks = set()
    
    try:
        # 获取交易日历
        trade_days = get_trade_days(end_date=date, count=days)
        
        for trade_date in trade_days:
            try:
                # 逐日获取涨停股票
                day_zt = get_zt_stocks(stock_list, trade_date)
                if day_zt:
                    zt_stocks.update(day_zt)
                    print(f"{trade_date.strftime('%Y-%m-%d')} 涨停股票数量: {len(day_zt)}")
                else:
                    print(f"{trade_date.strftime('%Y-%m-%d')} 涨停股票数量: 0")
            except Exception as e:
                print(f"获取{trade_date}涨停股票时出错: {e}")
                continue
        
        result = list(zt_stocks)
        print(f"近{days}日涨停股票总数（去重后）: {len(result)}")
        return result
        
    except Exception as e:
        print(f"备用方案获取近{days}日涨停股票时出错: {e}")
        return []


def get_zt_stocks(stock_list, date):
    """获取指定日期涨停的股票"""
    if not stock_list:
        return []
        
    try:
        df = get_price(stock_list, end_date=date, frequency='daily', 
                      fields=['close', 'high_limit'], count=1, 
                      panel=False, fill_paused=False, skip_paused=False)
        
        if df.empty:
            return []
            
        # 重置索引处理多级索引问题
        if isinstance(df.index, pd.MultiIndex):
            df = df.reset_index()
        
        # 删除NaN值
        df = df.dropna(subset=['close', 'high_limit'])
        
        if df.empty:
            return []
        
        # 涨停判断：收盘价等于涨停价（允许0.01的误差）
        zt_df = df[abs(df['close'] - df['high_limit']) < 0.01]
        
        if 'code' in zt_df.columns:
            return list(zt_df['code'])
        else:
            # 如果没有code列，从索引中获取
            return list(zt_df.index)
            
    except Exception as e:
        print(f"获取涨停股票时出错: {e}")
        return []


# 其他函数保持不变...
def buy_stocks(context):
    """9:27下单，第一天用50%资金，从第二天开始用剩余资金等额买入"""
    if not g.target_stocks:
        print("无目标股票，不进行买入操作")
        return
    
    # 增加交易天数计数
    g.trading_day_count += 1
    
    # 计算可用资金
    available_cash = context.portfolio.available_cash
    
    # 第一天只用50%资金，从第二天开始用全部剩余资金
    if g.trading_day_count == 1:
        usable_cash = available_cash * 0.5
        print(f"第一个交易日，使用50%资金: {usable_cash/10000:.2f}万元（总资金: {available_cash/10000:.2f}万元）")
    else:
        usable_cash = available_cash
        print(f"第{g.trading_day_count}个交易日，使用全部剩余资金: {usable_cash/10000:.2f}万元")
    
    # 平均分配给每只股票
    cash_per_stock = usable_cash / len(g.target_stocks)
    
    current_data = get_current_data()
    
    print(f"准备买入 {len(g.target_stocks)} 只股票，每只分配资金: {cash_per_stock/10000:.2f}万元")
    
    for stock in g.target_stocks:
        try:
            # 检查是否有足够资金买入至少100股
            current_price = current_data[stock].last_price
            if cash_per_stock / current_price >= 100:
                order_value(stock, cash_per_stock)
                print(f'买入 {stock} {get_security_info(stock).display_name}')
                print(f'买入金额: {cash_per_stock/10000:.2f}万元，价格: {current_price:.2f}')
            else:
                print(f'资金不足，无法买入 {stock}，需要资金: {current_price*100:.0f}元')
        except Exception as e:
            print(f"买入股票 {stock} 时出错: {e}")
    
    print('———————————————————————————————————')


def sell_low_gain(context):
    """次日10:30卖出涨幅低于5%的股票"""
    current_data = get_current_data()
    
    positions = list(context.portfolio.positions.keys())
    if not positions:
        print("当前无持仓")
        return
    
    print(f"10:30检查 {len(positions)} 只持仓股票涨幅")
    
    for stock in positions:
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
            
        try:
            # 获取昨日收盘价
            yesterday_close_data = attribute_history(stock, 1, '1d', 
                                                   fields=['close'], 
                                                   skip_paused=True)
            if yesterday_close_data.empty:
                continue
                
            yesterday_close = yesterday_close_data['close'][0]
            current_price = current_data[stock].last_price
            
            # 计算涨幅
            increase_ratio = (current_price - yesterday_close) / yesterday_close
            
            # 如果涨幅低于5%，则卖出
            if increase_ratio < 0.05:
                order_target_value(stock, 0)
                print(f'卖出涨幅不足股票: {stock} {get_security_info(stock).display_name}')
                print(f'当前涨幅: {increase_ratio*100:.2f}%')
            else:
                print(f'保留涨幅充足股票: {stock} {get_security_info(stock).display_name}')
                print(f'当前涨幅: {increase_ratio*100:.2f}%')
                
        except Exception as e:
            print(f"处理股票 {stock} 时出错: {e}")
    
    print('———————————————————————————————————')


def sell_non_limit_up(context):
    """14:50卖出没有涨停的股票"""
    current_data = get_current_data()
    
    positions = list(context.portfolio.positions.keys())
    if not positions:
        print("当前无持仓")
        return
    
    print(f"14:50检查 {len(positions)} 只持仓股票是否涨停")
    
    for stock in positions:
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
            
        try:
            # 检查是否涨停
            current_price = current_data[stock].last_price
            high_limit = current_data[stock].high_limit
            
            # 如果没有涨停，则卖出
            if current_price < high_limit * 0.995:  # 给一点容错空间
                order_target_value(stock, 0)
                print(f'卖出未涨停股票: {stock} {get_security_info(stock).display_name}')
                print(f'当前价格: {current_price:.2f}, 涨停价: {high_limit:.2f}')
            else:
                print(f'持有涨停股票: {stock} {get_security_info(stock).display_name}')
                print(f'当前价格: {current_price:.2f}, 涨停价: {high_limit:.2f}')
                
        except Exception as e:
            print(f"处理股票 {stock} 时出错: {e}")
    
    print('———————————————————————————————————')


def is_n_day_high(stock, date, n_days):
    """检查是否创N日新高"""
    try:
        # 获取N+1天的价格数据（包含当前日期）
        price_data = attribute_history(stock, n_days + 1, '1d', 
                                     fields=['high'], 
                                     skip_paused=True)
        if price_data.empty or len(price_data) < n_days + 1:
            return False
        
        # 昨日最高价（倒数第二天，因为当前还没收盘）
        yesterday_high = price_data['high'][-2]
        # 前N天的最高价（除了昨日）
        historical_highs = price_data['high'][:-2]  # 排除昨日和今日
        
        if len(historical_highs) < n_days - 1:  # 至少需要N-1天的历史数据
            return False
            
        max_high_n_days = historical_highs.max()
        
        # 判断是否创新高
        return yesterday_high > max_high_n_days
        
    except Exception as e:
        print(f"检查股票 {stock} 是否创{n_days}日新高时出错: {e}")
        return False


def prepare_stock_list(date):
    """准备基础股票池"""
    initial_list = get_all_securities('stock', date).index.tolist()
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_new_stock(initial_list, date)
    initial_list = filter_st_paused_stock(initial_list)
    return initial_list


def filter_kcbj_stock(initial_list):
    """过滤科创板和北交所股票"""
    return [stock for stock in initial_list if stock[:2] in ('60', '00', '30')]


def filter_new_stock(initial_list, date, days=60):
    """过滤新股"""
    d_date = transform_date(date, 'd')
    return [stock for stock in initial_list 
            if d_date - get_security_info(stock).start_date > dt.timedelta(days=days)]


def filter_st_paused_stock(initial_list):
    """过滤ST股和停牌股"""
    current_data = get_current_data()
    return [stock for stock in initial_list 
            if not any([
                current_data[stock].is_st,
                current_data[stock].paused,
                '退' in current_data[stock].name
            ])]


def transform_date(date, date_type):
    """日期格式转换"""
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
    dct = {'str': str_date, 'dt': dt_date, 'd': d_date}
    return dct[date_type]
