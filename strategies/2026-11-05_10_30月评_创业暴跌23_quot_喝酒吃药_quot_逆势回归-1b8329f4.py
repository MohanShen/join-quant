# Clone from JoinQuant
# postId: 1b8329f4cc2925b3a4646633c59d5736
# backtestId: bf3a18fc111e10f3dc43913d20147ba7
# title: 【10.30月评】创业暴跌23%，&quot;喝酒吃药&quot;逆势回归

# 克隆自聚宽文章：https://www.joinquant.com/post/69783
# 标题：适合2026年行情特点的尾盘策略
# 作者：天香膏

from datetime import datetime, timedelta
from jqdata import *
import numpy as np
import pandas as pd

# ===================== 【原版参数完全不变】 =====================
PROFIT_TAKE_RATIO = 1.1
STOP_LOSS_MA5_RATIO = 1.009
SELL_1ST_TIMES = ['09:45', '10:00', '10:30']
SELL_2ND_TIMES = ['11:00', '14:30']

BUY_TIMES = ['14:50']
SELECT_STOCK_NUM = 10
VOL_RATIO_LOW = 1.0
TURN_OVER_LOW = 5.0
TURN_OVER_HIGH = 8.0
MV_LOW = 50 * 10**8
MV_HIGH = 520 * 10**8
RISE_LOW = 0.03
RISE_HIGH = 0.05
MAX_SINGLE_RATIO = 0.90

# ===================== 【10日涨幅过滤 - 保留】 =====================
FILTER_DAYS = 10
FILTER_MAX_RATE = 0.3
ENABLE_FILTER = True

# ===================== 10日涨幅过滤（原版无错） =====================
def filter_10d_rise(context, stock_list):
    if not stock_list:
        return []

    end_dt = context.current_dt.date() - timedelta(days=1)
    
    price_data = get_price(
        stock_list,
        end_date=end_dt,
        frequency='daily',
        fields=['close'],
        count=FILTER_DAYS,
        fq='pre',
        panel=False
    )

    if price_data.empty:
        return stock_list

    hist_df = price_data.pivot(index='time', columns='code', values='close')
    hist_df = hist_df.dropna(axis=1, how='all')
    valid = []

    for code in hist_df.columns:
        try:
            series = hist_df[code].dropna()
            if len(series) < FILTER_DAYS:
                valid.append(code)
                continue
            start = series.iloc[0]
            end = series.iloc[-1]
            rise = (end - start) / start
            if rise <= FILTER_MAX_RATE:
                valid.append(code)
        except:
            valid.append(code)
    return valid

# ===================== 工具函数 =====================
def get_last_trading_day_ultimate(target_date):
    index_code = '000001.XSHG'
    current_date = target_date - timedelta(days=1)
    while True:
        try:
            hist_data = get_price(index_code, start_date=current_date, end_date=current_date,
                                  frequency='daily', fields=['close'], panel=False)
            if not hist_data.empty:
                return current_date
        except:
            pass
        current_date -= timedelta(days=1)
        if (target_date - current_date).days > 30:
            log.error(f"【工具函数】未找到{target_date}的前一交易日")
            return None

# ===================== 卖出模块（彻底修复：次日减半仅一次，当天不再卖出） =====================
def sell_1st(context):
    sell_out(context, times=1)

def sell_2nd(context):
    sell_out(context, times=2)

def sell_out(context, times=1):
    previous_date = context.previous_date
    current_data = get_current_data()
    hold_stocks = list(context.portfolio.positions.keys())
    
    # 初始化当日已减半标记
    if not hasattr(context, 'half_sold_today'):
        context.half_sold_today = {}
    
    for stock_code in hold_stocks:
        try:
            position = context.portfolio.positions[stock_code]
            if position.closeable_amount <= 0:
                continue
            
            # 检查是否已经在当天执行过减半
            if stock_code in context.half_sold_today and context.half_sold_today[stock_code] == context.current_dt.date():
                continue
            
            # 获取当前价格
            bars = get_bars(stock_code, count=1, fields=['close'], include_now=True)
            if len(bars) > 0:
                current_price = bars['close'][0]
            else:
                current_price = current_data[stock_code].last_price
                
            high_limit = current_data[stock_code].high_limit
            avg_cost = position.avg_cost
            total_amount = position.total_amount

            # 1. 止盈：直接全额卖出
            if current_price > PROFIT_TAKE_RATIO * avg_cost and current_price < high_limit:
                order_target(stock_code, 0)
                log.info(f'【止盈卖出】{stock_code} | 成本:{avg_cost:.2f} | 现价:{current_price:.2f}')
                continue
            
            # 2. 止损逻辑
            if times == 2:
                bars_ma5 = get_bars(stock_code, count=5, fields=['close'], include_now=True)
                if len(bars_ma5) >= 5:
                    ma5 = bars_ma5['close'].mean()
                    if current_price < STOP_LOSS_MA5_RATIO * ma5 and current_price < high_limit:
                        
                        # 【核心修复】仅在买入后的第2个交易日的11:00执行一次减半
                        buy_date = position.init_time.date()
                        today = context.current_dt.date()
                        hold_days = (today - buy_date).days
                        is_1100 = context.current_dt.hour == 11 and context.current_dt.minute == 0
                        
                        if hold_days == 1 and current_price < avg_cost and is_1100:
                            # 计算减半数量，取整为100股的倍数
                            half_amount = (total_amount // 2) // 100 * 100
                            if half_amount > 0:
                                order_target(stock_code, half_amount)
                                log.info(f'【次日亏损减半】{stock_code} | 成本:{avg_cost:.2f} | 现价:{current_price:.2f} | 卖出50%')
                                # 标记已减半，当天不再处理
                                context.half_sold_today[stock_code] = today
                            else:
                                # 不足100股直接清仓
                                order_target(stock_code, 0)
                                log.info(f'【清仓】{stock_code} | 剩余不足100股，全部卖出')
                        else:
                            # 非次日11:00的止损，正常全额卖出
                            order_target(stock_code, 0)
                            log.info(f'【止损卖出】{stock_code} | MA5:{ma5:.2f} | 现价:{current_price:.2f}')
        except Exception as e:
            log.error(f'【卖出异常】{stock_code} | 错误:{str(e)}')
            continue

# ===================== 买入模块（100%原版，已修复不足100股下单问题） =====================
def get_stock_volume_ratio(stock_list, current_dt):
    vol_ratio_dict = {}
    for code in stock_list:
        try:
            minute_data = get_price(code, start_date=current_dt.replace(hour=9, minute=30),
                                    end_date=current_dt, frequency='minute', fields=['volume'], panel=False)
            today_vol = minute_data['volume'].sum()
            trade_minutes = (current_dt.hour - 9) * 60 + (current_dt.minute - 30)
            if trade_minutes <= 0:
                vol_ratio_dict[code] = 0
                continue
            hist_data = get_price(code, start_date=current_dt - timedelta(days=6),
                                  end_date=current_dt - timedelta(days=1), frequency='daily', fields=['volume'], panel=False)
            avg_min_vol = hist_data['volume'].mean() / 240 if not hist_data.empty else 0
            vol_ratio = (today_vol / trade_minutes) / avg_min_vol if avg_min_vol > 0 else 0
            vol_ratio_dict[code] = vol_ratio
        except Exception as e:
            vol_ratio_dict[code] = 0
    return vol_ratio_dict

def get_stock_rise_pct(stock_list, current_dt):
    rise_pct_dict = {}
    current_data = get_current_data()
    target_date = current_dt.date()
    last_trade_day = get_last_trading_day_ultimate(target_date)
    
    if not last_trade_day:
        return {code: 0 for code in stock_list}
        
    pre_close_df = get_price(stock_list, start_date=last_trade_day, end_date=last_trade_day,
                             frequency='daily', fields=['close'], panel=False)
    
    pre_close_dict = {}
    if not pre_close_df.empty:
        if 'code' in pre_close_df.columns:
            for idx, row in pre_close_df.iterrows():
                pre_close_dict[row['code']] = row['close']
        else:
            if len(stock_list) == 1:
                pre_close_dict[stock_list[0]] = pre_close_df['close'].iloc[0]

    for code in stock_list:
        try:
            bars = get_bars(code, count=1, fields=['close'], include_now=True)
            if len(bars) == 0:
                rise_pct_dict[code] = 0
                continue
            last_price = bars['close'][0]
            
            if code in pre_close_dict:
                pre_close = pre_close_dict[code]
            else:
                pre_close = current_data[code].pre_close
            
            if pre_close and pre_close > 0:
                rise_pct = (last_price - pre_close) / pre_close
                rise_pct_dict[code] = rise_pct
            else:
                rise_pct_dict[code] = 0
                
        except Exception as e:
            rise_pct_dict[code] = 0
    return rise_pct_dict

def get_historical_mv_and_turnover(stock_list, current_dt):
    target_date = current_dt.date()
    query_date = get_last_trading_day_ultimate(target_date)
    if query_date is None:
        return pd.DataFrame()
    q = query(valuation.code, valuation.circulating_market_cap, valuation.turnover_ratio)\
          .filter(valuation.code.in_(stock_list))
    df = get_fundamentals(q, date=query_date)
    return df

def select_stock(context):
    current_dt = context.current_dt
    current_data = get_current_data()
    
    stock_list = get_all_securities(['stock']).index
    stock_list = [code for code in stock_list if not current_data[code].paused and not current_data[code].is_st]
    log.info(f'【选股】基础股票池：{len(stock_list)}只')
    if not stock_list:
        return []
    
    df = get_historical_mv_and_turnover(stock_list, current_dt)
    if df.empty:
        return []
    df = df[(df['turnover_ratio'] >= TURN_OVER_LOW) & (df['turnover_ratio'] <= TURN_OVER_HIGH)]
    df = df[(df['circulating_market_cap'] >= MV_LOW/10**8) & (df['circulating_market_cap'] <= MV_HIGH/10**8)]
    
    rise_pct_dict = get_stock_rise_pct(df['code'].tolist(), current_dt)
    df['rise_pct'] = df['code'].map(rise_pct_dict)
    df = df[(df['rise_pct'] >= RISE_LOW) & (df['rise_pct'] <= RISE_HIGH)]
    
    vol_ratio_dict = get_stock_volume_ratio(df['code'].tolist(), current_dt)
    df['volume_ratio'] = df['code'].map(vol_ratio_dict)
    df = df[df['volume_ratio'] >= VOL_RATIO_LOW]
    
    final_stock = []
    for code in df['code'].tolist():
        try:
            minute_data = get_price(
                code,
                start_date=current_dt - timedelta(minutes=60),
                end_date=current_dt,
                frequency='minute',
                fields=['close', 'avg'],
                panel=False
            )
            if len(minute_data) < 5 or (minute_data['close'] >= minute_data['avg']).mean() >= 0.8:
                final_stock.append(code)
                if len(final_stock) >= SELECT_STOCK_NUM:
                    break
        except Exception as e:
            continue

    final_stock = filter_10d_rise(context, final_stock)
    log.info(f'【选股】最终结果：{len(final_stock)}只 | {final_stock}')
    return final_stock[:SELECT_STOCK_NUM]

# ====================== ✅【最终修复】头部股见顶预警 ======================
def calc_top_stock_warning(context):
    today = context.current_dt
    yesterday = today - timedelta(days=1)

    # 获取全市场股票
    all_stocks = get_all_securities(types=['stock'], date=yesterday)
    stock_list = all_stocks.index.tolist()

    data_list = []
    for stock in stock_list:
        try:
            bar = get_bars(stock, count=1, end_dt=yesterday, fields=['money'])
            if len(bar) > 0:
                data_list.append({
                    'code': stock,
                    'money': bar['money'][0]
                })
        except:
            continue

    df = pd.DataFrame(data_list).dropna()
    total_count = len(df)

    # 取 成交额 最大的前 5% 股票
    df_sorted = df.sort_values('money', ascending=False)
    top_n = max(1, int(total_count * 0.05))
    df_top = df_sorted.head(top_n)

    # 计算比例
    total_money = df['money'].sum()
    top_money = df_top['money'].sum()
    ratio = top_money / total_money * 100

    # 连续3天判断 —— ✅【这里彻底修复，不再出现生成器】
    context.ratio_history.append(ratio)
    if len(context.ratio_history) > 3:
        context.ratio_history.pop(0)

    is_warning = ratio > 45

    # ==============================================
    # ✅【核心修复：强制转布尔值，绝对不出现生成器】
    # ==============================================
    count = 0
    for r in context.ratio_history:
        if r > 45:
            count += 1
    forbid_buy = count >= 3

    # 日志输出
    log.info("=" * 60)
    log.info(f"【头部股见顶预警】日期：{yesterday.strftime('%Y-%m-%d')}")

    if is_warning:
        log.warn(f"✅ 成交集中度：{ratio:.2f}%  —— 超过45%，进入高危预警！")
    else:
        log.info(f"成交集中度：{ratio:.2f}%")

    log.info(f"有效股票数：{total_count} 只")
    log.info(f"前5%股票数：{top_n} 只")
    log.info(f"前5%成交额：{top_money/100000000:.2f} 亿")
    log.info(f"全市场成交额：{total_money/100000000:.2f} 亿")
    log.info(f"预警(>45%)：{is_warning}")
    log.info(f"禁止开仓(连续3天)：{forbid_buy}")
    log.info("=" * 60)

    context.forbid_buy = forbid_buy
    context.warning_ratio = ratio

# ===================== ✅ 买入策略（加入风险控制）=====================
def buy_strategy(context):
    # ===================== 🚫 核心：高危预警 → 禁止买入 =====================
    if context.forbid_buy:
        log.warning("⚠️ 连续3天头部股高危预警，【全天禁止开仓】")
        return

    if context.portfolio.positions:
        return
    
    target_stocks = select_stock(context)
    if not target_stocks:
        return
    
    available_cash = context.portfolio.available_cash
    if available_cash < 1000:
        return
    
    for code in target_stocks:
        try:
            current_price = get_current_data()[code].last_price
            if current_price <= 0:
                continue
            
            target_cash = available_cash * MAX_SINGLE_RATIO
            max_shares = int(target_cash / current_price)
            tradable_shares = (max_shares // 100) * 100

            if tradable_shares < 100:
                log.info(f"【跳过买入】{code} 可买股数不足100，资金不足")
                continue
            
            order(code, tradable_shares)
            log.info(f'【买入】{code} | 成交{tradable_shares}股')
        except Exception as e:
            log.error(f'【买入异常】{code} | 错误:{str(e)}')
            continue

# ===================== 策略初始化 =====================
def initialize(context):
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    set_option('avoid_future_data', True)
    set_slippage(PriceRelatedSlippage(0.001))
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0001, close_commission=0.0001,
        min_commission=5
    ), type='stock')

    # ✅ 初始化预警历史
    context.ratio_history = []
    context.forbid_buy = False

    # ✅ 每天 09:05 运行预警
    run_daily(calc_top_stock_warning, time='09:05')

    run_daily(buy_strategy, '14:50')
    run_daily(sell_1st, '09:45')
    run_daily(sell_1st, '10:00')
    run_daily(sell_1st, '10:30')
    run_daily(sell_2nd, '11:00')
    run_daily(sell_2nd, '14:30')

def before_trading_start(context):
    context.previous_date = context.current_dt.date()