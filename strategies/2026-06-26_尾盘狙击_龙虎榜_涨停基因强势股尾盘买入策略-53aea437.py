# Clone from JoinQuant
# postId: 53aea4379c1d68810c0d213f7c789e02
# backtestId: 7d44bf844532deee1fb0e69cee2bada3
# title: 尾盘狙击 — 龙虎榜+涨停基因强势股尾盘买入策略

# 克隆自聚宽文章：https://www.joinquant.com/post/70033
# 标题：连阳倍量首板高开 1进2 收益823% 回撤13%
# 作者：顶级理解

# 克隆自聚宽文章：https://www.joinquant.com/post/69783
# 标题：适合2026年行情特点的尾盘策略
# 作者：天香膏
# 修改：增加30日内涨停优先买入规则 + 修复未来数据错误 + 日志优化
# 再次修改：增加30天内龙虎榜优先第一位

from datetime import datetime, timedelta
from jqdata import *
import numpy as np
import pandas as pd

# ===================== 【核心参数配置区】 =====================
PROFIT_TAKE_RATIO = 1.1
STOP_LOSS_MA5_RATIO = 1.009
SELL_1ST_TIMES = ['09:45', '10:00', '10:30']
SELL_2ND_TIMES = ['11:00', '14:30']
BUY_TIMES = ['14:50']
SELECT_STOCK_NUM = 2
VOL_RATIO_LOW = 1.0
TURN_OVER_LOW = 5.0
TURN_OVER_HIGH = 8.0
MV_LOW = 50 * 10**8
MV_HIGH = 520 * 10**8
RISE_LOW = 0.028
RISE_HIGH = 0.048
MAX_SINGLE_RATIO = 0.90
LIMIT_UP_LOOKBACK = 30          # 涨停回溯天数
BILLBOARD_LOOKBACK_DAYS = 30    # 龙虎榜回溯天数

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

# ===================== 龙虎榜历史检测（新增） =====================
def get_billboard_history(stock_list, end_date, lookback_days=30):
    """
    批量判断股票在回溯期内是否有龙虎榜记录
    end_date: 历史日期，不能是当日
    返回字典 {stock_code: has_billboard (bool)}
    """
    if not stock_list:
        return {}
    
    start_date = end_date - timedelta(days=lookback_days)
    try:
        # 获取指定时间段内的所有龙虎榜记录
        df = get_billboard_list(stock_list, start_date=start_date, end_date=end_date)
        if df.empty:
            return {code: False for code in stock_list}
        # 上榜股票列表
        listed_codes = set(df['code'].unique())
    except Exception as e:
        log.error(f"【龙虎榜查询失败】{str(e)}")
        return {code: False for code in stock_list}
    
    return {code: (code in listed_codes) for code in stock_list}

# ===================== 涨停历史检测（修复未来数据） =====================
def get_limit_up_history(stock_list, end_date, lookback_days=30):
    """
    批量判断股票在回溯期内是否有涨停记录
    end_date: 历史日期，不能是当日
    返回字典 {stock_code: has_limit_up (bool)}
    """
    if not stock_list:
        return {}
    
    df = get_price(
        stock_list,
        end_date=end_date,
        count=lookback_days,
        frequency='daily',
        fields=['close', 'high_limit'],
        panel=False,
        skip_paused=False,
        fq='pre'
    )
    
    df['is_limit_up'] = (df['close'] == df['high_limit'])
    limit_up_flags = df.groupby('code')['is_limit_up'].any().to_dict()
    return limit_up_flags

# ===================== 卖出模块（已修复未来数据） =====================
def register_sell_tasks():
    for sell_time in SELL_1ST_TIMES:
        run_daily(sell_1st, time=sell_time)
    for sell_time in SELL_2ND_TIMES:
        run_daily(sell_2nd, time=sell_time)

def sell_1st(context):
    sell_out(context, times=1)

def sell_2nd(context):
    sell_out(context, times=2)

def sell_out(context, times=1):
    current_data = get_current_data()
    hold_stocks = list(context.portfolio.positions.keys())
    
    for stock_code in hold_stocks:
        try:
            position = context.portfolio.positions[stock_code]
            if position.closeable_amount <= 0:
                continue
            
            current_price = current_data[stock_code].last_price
            high_limit = current_data[stock_code].high_limit
            stock_name = get_security_info(stock_code).display_name
            
            # 止盈（涨停不卖）
            if current_price > PROFIT_TAKE_RATIO * position.avg_cost and current_price < high_limit:
                order_target(stock_code, 0)
                log.info(f'【止盈卖出】{stock_code}-{stock_name} | 成本:{position.avg_cost:.2f} | 现价:{current_price:.2f}')
                continue
            
            # 止损（仅第二阶段，涨停不卖）
            if times == 2:
                bars_past = get_bars(stock_code, count=4, unit='1d', fields=['close'], include_now=False)
                if len(bars_past) >= 4:
                    closes_list = list(bars_past['close'])
                    closes_list.append(current_price)
                    ma5 = np.mean(closes_list)
                    
                    if current_price < STOP_LOSS_MA5_RATIO * ma5 and current_price < high_limit:
                        order_target(stock_code, 0)
                        log.info(f'【止损卖出】{stock_code}-{stock_name} | MA5:{ma5:.2f} | 现价:{current_price:.2f} | 成本:{position.avg_cost:.2f}')
        except Exception as e:
            log.error(f'【卖出异常】{stock_code} | 错误:{str(e)}')
            continue

# ===================== 买入模块 =====================
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
            log.debug(f'【量比计算】{code} 失败：{str(e)}')
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
            last_price = current_data[code].last_price
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
    log.info(f'【选股】市值/换手率筛选后：{len(df)}只')
    if df.empty:
        return []
    
    rise_pct_dict = get_stock_rise_pct(df['code'].tolist(), current_dt)
    df['rise_pct'] = df['code'].map(rise_pct_dict)
    
    df = df[(df['rise_pct'] >= RISE_LOW) & (df['rise_pct'] <= RISE_HIGH)]
    log.info(f'【选股】涨幅筛选后：{len(df)}只')
    if df.empty:
        return []
    
    vol_ratio_dict = get_stock_volume_ratio(df['code'].tolist(), current_dt)
    df['volume_ratio'] = df['code'].map(vol_ratio_dict)
    df = df[df['volume_ratio'] >= VOL_RATIO_LOW]
    log.info(f'【选股】量比筛选后：{len(df)}只')
    if df.empty:
        return []
    
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
        except Exception as e:
            log.debug(f'【选股】{code} 分时异常：{str(e)}')
            continue
    
    log.info(f'【选股】分时强度筛选后候选：{len(final_stock)}只')
    if not final_stock:
        return []
    
    last_trade_day = get_last_trading_day_ultimate(current_dt.date())
    if last_trade_day is None:
        log.error("无法获取前一交易日，跳过优先排序")
        return final_stock[:SELECT_STOCK_NUM]
    
    # 获取龙虎榜记录（新增）
    billboard_flags = get_billboard_history(final_stock, last_trade_day, BILLBOARD_LOOKBACK_DAYS)
    context.billboard_flags_cache = billboard_flags
    
    # 获取涨停记录
    limit_up_flags = get_limit_up_history(final_stock, last_trade_day, LIMIT_UP_LOOKBACK)
    context.limit_up_flags_cache = limit_up_flags
    
    # 排序优先级：龙虎榜 > 涨停记录
    sorted_final = sorted(
        final_stock,
        key=lambda x: (billboard_flags.get(x, False), limit_up_flags.get(x, False)),
        reverse=True
    )
    
    selected = sorted_final[:SELECT_STOCK_NUM]
    log.info(f'【选股】最终结果（龙虎榜优先→涨停优先）：{selected}')
    return selected

def buy_strategy(context):
    current_dt = context.current_dt
    current_data = get_current_data()
    
    if hasattr(context, 'stop_trading_remaining_days') and context.stop_trading_remaining_days > 0:
        return
    
    if context.portfolio.positions:
        log.info(f'【买入】已有持仓，跳过')
        return
    
    target_stocks = select_stock(context)
    if not target_stocks:
        log.info(f'【买入】无符合条件股票，跳过')
        return
    
    available_cash = context.portfolio.available_cash
    if available_cash < 1000:
        return
    
    billboard_flags = getattr(context, 'billboard_flags_cache', {})
    limit_up_flags = getattr(context, 'limit_up_flags_cache', {})
    
    for code in target_stocks:
        try:
            current_price = current_data[code].last_price
            if current_price <= 0:
                continue
            
            current_available = context.portfolio.available_cash
            if current_available < 1000:
                break
            
            target_cash = current_available * MAX_SINGLE_RATIO
            max_shares = int(target_cash / current_price)
            tradable_shares = (max_shares // 100) * 100
            
            if tradable_shares < 100:
                continue
            
            order_result = order(code, tradable_shares)
            
            if order_result:
                stock_name = get_security_info(code).display_name
                is_billboard = billboard_flags.get(code, False)
                is_limit_up = limit_up_flags.get(code, False)
                
                if is_billboard:
                    reason_tag = "【龙虎榜优先】"
                elif is_limit_up:
                    reason_tag = "【涨停基因】"
                else:
                    reason_tag = "【常规尾盘】"
                
                log.info(f'{reason_tag}买入 {code}-{stock_name} | 成交{tradable_shares}股 | 价格:{current_price:.2f} | 龙虎榜:{is_billboard} | 涨停记录:{is_limit_up}')
        except Exception as e:
            log.error(f'【买入异常】{code} | {str(e)}')
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
        close_today_commission=0, min_commission=5
    ), type='stock')
    
    # 注册交易任务
    for sell_time in SELL_1ST_TIMES:
        run_daily(sell_1st, time=sell_time)
    for sell_time in SELL_2ND_TIMES:
        run_daily(sell_2nd, time=sell_time)
    for buy_time in BUY_TIMES:
        run_daily(buy_strategy, time=buy_time)

def before_trading_start(context):
    # 交易日开始分隔线
    current_date = context.current_dt.strftime('%Y-%m-%d')
    log.info('=' * 50)
    log.info(f'【新交易日开始】{current_date}')
    log.info('=' * 50)

def after_trading_end(context):
    # 交易日结束总结
    current_date = context.current_dt.strftime('%Y-%m-%d')
    log.info('=' * 50)
    log.info(f'【交易日结束】{current_date}')
    
    # 持仓情况
    positions = context.portfolio.positions
    if positions:
        log.info('--- 今日持仓 ---')
        for code, pos in positions.items():
            if pos.total_amount > 0:
                stock_name = get_security_info(code).display_name
                pnl = (pos.price - pos.avg_cost) * pos.total_amount
                pnl_pct = (pos.price / pos.avg_cost - 1) * 100
                log.info(f'  {code} {stock_name} | 持仓{pos.total_amount}股 | 成本{pos.avg_cost:.2f} | 现价{pos.price:.2f} | 浮动盈亏{pnl:.2f} ({pnl_pct:.2f}%)')
    else:
        log.info('--- 今日无持仓 ---')
    
    # 当日交易总结
    daily_pnl = context.portfolio.portfolio_value - context.portfolio.starting_cash
    log.info(f'--- 今日总结 ---')
    log.info(f'  当日盈亏: {daily_pnl:.2f} 元')
    log.info(f'  累计净值: {context.portfolio.portfolio_value / context.portfolio.starting_cash:.4f}')
    log.info('=' * 50)