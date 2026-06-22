# Clone from JoinQuant
# postId: 452ee8589f480e5aec91fd4ee7e1264a
# backtestId: 8a4253fe46a31f059ad132ab1e13d214
# title: 龙虎榜选股--尾盘买入法 - 年化243.25%

from datetime import datetime, timedelta
from jqdata import *
import numpy as np
import pandas as pd

# ===================== 【核心参数配置区】 =====================
PROFIT_TAKE_RATIO = 1.1                        # 止盈比例：盈利超过10%触发止盈
STOP_LOSS_MA5_RATIO = 1.0097                   # MA5止损比例
SELL_1ST_TIMES = ['09:45', '10:00', '10:30']   # 第一阶段卖出时间（仅止盈）
SELL_2ND_TIMES = ['11:00', '14:30']            # 第二阶段卖出时间（止盈+止损）
BUY_TIMES = ['14:50']                          # 买入时间（尾盘）
SELECT_STOCK_NUM = 2                           # 每日最多买入股票数量
VOL_RATIO_LOW = 1.0                            # 量比下限
TURN_OVER_LOW = 5.0                            # 换手率下限（%）
TURN_OVER_HIGH = 7.0                           # 换手率上限（%）
MV_LOW = 50 * 10**8                            # 流通市值下限（50亿）
MV_HIGH = 520 * 10**8                          # 流通市值上限（520亿）
RISE_LOW = 0.028                               # 涨幅下限（2.8%）
RISE_HIGH = 0.048                              # 涨幅上限（4.8%）
MAX_SINGLE_RATIO = 0.90                        # 单只股票最大资金占比
LIMIT_UP_LOOKBACK = 30                         # 涨停回溯天数
BILLBOARD_LOOKBACK_DAYS = 30                   # 龙虎榜回溯天数

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
    
    # ==================== 收盘总结相关变量 ====================
    g.initial_total_value = context.portfolio.total_value   # 初始总资产
    g.max_total_value = context.portfolio.total_value       # 历史最高总资产
    g.prev_total_value = context.portfolio.total_value      # 前一日总资产
    g.prev_benchmark = None                                  # 前一日基准值
    g.initial_benchmark = None                               # 初始基准值
    g.daily_trades = []                                      # 记录当日交易
    g.total_sold_count = 0                                   # 累计卖出次数
    g.total_buy_count = 0                                    # 累计买入次数
    
    # ==================== 记录股票买入日期 ====================
    g.stock_buy_date = {}                                    # {股票代码: 买入日期}
    
    # 注册交易任务
    for sell_time in SELL_1ST_TIMES:
        run_daily(sell_1st, time=sell_time)
    for sell_time in SELL_2ND_TIMES:
        run_daily(sell_2nd, time=sell_time)
    for buy_time in BUY_TIMES:
        run_daily(buy_strategy, time=buy_time)
    
    # 注册收盘总结任务（15:05执行）
    run_daily(after_market_close_summary, time='15:05')


# ===================== 工具函数 =====================
def get_last_trading_day_ultimate(target_date):
    """获取最近的一个交易日"""
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
            return None


# ===================== 龙虎榜历史检测 =====================
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
        df = get_billboard_list(stock_list, start_date=start_date, end_date=end_date)
        if df.empty:
            return {code: False for code in stock_list}
        listed_codes = set(df['code'].unique())
    except Exception as e:
        log.error(f'【龙虎榜查询失败】{str(e)}')
        return {code: False for code in stock_list}
    
    return {code: (code in listed_codes) for code in stock_list}


# ===================== 涨停历史检测 =====================
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


# ===================== 卖出模块 =====================
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
    """卖出逻辑"""
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
                g.total_sold_count += 1
                
                if hasattr(g, 'stock_buy_date') and stock_code in g.stock_buy_date:
                    del g.stock_buy_date[stock_code]
                
                g.daily_trades.append({
                    'time': context.current_dt.strftime('%H:%M'),
                    'code': stock_code,
                    'name': stock_name,
                    'type': '止盈卖出',
                    'price': current_price,
                    'cost': position.avg_cost,
                    'pnl': (current_price - position.avg_cost) / position.avg_cost
                })
                log.info(f'💰【止盈卖出】{stock_code}-{stock_name} | 成本:{position.avg_cost:.2f} | 现价:{current_price:.2f} | 盈亏:+{(current_price - position.avg_cost) / position.avg_cost:.2%}')
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
                        g.total_sold_count += 1
                        
                        if hasattr(g, 'stock_buy_date') and stock_code in g.stock_buy_date:
                            del g.stock_buy_date[stock_code]
                        
                        g.daily_trades.append({
                            'time': context.current_dt.strftime('%H:%M'),
                            'code': stock_code,
                            'name': stock_name,
                            'type': '止损卖出',
                            'price': current_price,
                            'cost': position.avg_cost,
                            'pnl': (current_price - position.avg_cost) / position.avg_cost
                        })
                        log.info(f'⚠️【止损卖出】{stock_code}-{stock_name} | MA5:{ma5:.2f} | 现价:{current_price:.2f} | 成本:{position.avg_cost:.2f} | 盈亏:{(current_price - position.avg_cost) / position.avg_cost:.2%}')
                        continue
        except Exception as e:
            log.error(f'【卖出异常】{stock_code} | 错误:{str(e)}')
            continue


# ===================== 买入模块 =====================
def get_stock_volume_ratio(stock_list, current_dt):
    """计算股票量比"""
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
    """计算股票当日涨幅"""
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
    """获取历史市值和换手率"""
    target_date = current_dt.date()
    query_date = get_last_trading_day_ultimate(target_date)
    if query_date is None:
        return pd.DataFrame()
    q = query(valuation.code, valuation.circulating_market_cap, valuation.turnover_ratio)\
          .filter(valuation.code.in_(stock_list))
    df = get_fundamentals(q, date=query_date)
    return df


def select_stock(context):
    """核心选股函数"""
    current_dt = context.current_dt
    current_data = get_current_data()
    
    log.info(f'🔍━━━━━━━━━━ 开始选股 {current_dt.strftime("%Y-%m-%d %H:%M")} ━━━━━━━━━━')
    
    stock_list = get_all_securities(['stock']).index
    stock_list = [code for code in stock_list if not current_data[code].paused and not current_data[code].is_st]
    log.info(f'📊【选股-基础池】{len(stock_list)}只（剔除ST/停牌）')
    if not stock_list:
        return []
    
    df = get_historical_mv_and_turnover(stock_list, current_dt)
    if df.empty:
        return []
    df = df[(df['turnover_ratio'] >= TURN_OVER_LOW) & (df['turnover_ratio'] <= TURN_OVER_HIGH)]
    df = df[(df['circulating_market_cap'] >= MV_LOW/10**8) & (df['circulating_market_cap'] <= MV_HIGH/10**8)]
    log.info(f'📊【选股-市值/换手】{len(df)}只 | 换手{TURN_OVER_LOW}~{TURN_OVER_HIGH}% | 市值{MV_LOW/10**8:.0f}~{MV_HIGH/10**8:.0f}亿')
    if df.empty:
        return []
    
    rise_pct_dict = get_stock_rise_pct(df['code'].tolist(), current_dt)
    df['rise_pct'] = df['code'].map(rise_pct_dict)
    
    df = df[(df['rise_pct'] >= RISE_LOW) & (df['rise_pct'] <= RISE_HIGH)]
    log.info(f'📊【选股-涨幅筛选】{len(df)}只 | 涨幅{RISE_LOW*100:.1f}~{RISE_HIGH*100:.1f}%')
    if df.empty:
        return []
    
    vol_ratio_dict = get_stock_volume_ratio(df['code'].tolist(), current_dt)
    df['volume_ratio'] = df['code'].map(vol_ratio_dict)
    df = df[df['volume_ratio'] >= VOL_RATIO_LOW]
    log.info(f'📊【选股-量比筛选】{len(df)}只 | 量比≥{VOL_RATIO_LOW}')
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
    
    log.info(f'📊【选股-分时强度】{len(final_stock)}只 | 价格≥均价占比≥80%')
    if not final_stock:
        return []
    
    last_trade_day = get_last_trading_day_ultimate(current_dt.date())
    if last_trade_day is None:
        log.error("无法获取前一交易日，跳过优先排序")
        return final_stock[:SELECT_STOCK_NUM]
    
    # 获取龙虎榜记录
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
    
    # 输出详细选股结果
    log.info(f'⭐【选股-最终结果】共{len(selected)}只')
    for idx, code in enumerate(selected, 1):
        name = get_security_info(code).display_name
        is_billboard = billboard_flags.get(code, False)
        is_limit_up = limit_up_flags.get(code, False)
        rank_tag = '🥇' if idx == 1 else '🥈'
        tag = []
        if is_billboard:
            tag.append('📋龙虎榜')
        if is_limit_up:
            tag.append('🚀涨停基因')
        tag_str = f'({",".join(tag)})' if tag else ''
        log.info(f'   {rank_tag} {idx}. {code}({name}) {tag_str}')
    
    return selected


def buy_strategy(context):
    """尾盘买入策略"""
    current_dt = context.current_dt
    current_data = get_current_data()
    
    log.info(f'🟢━━━━━━━━ 尾盘买入开始 {current_dt.strftime("%Y-%m-%d %H:%M")} ━━━━━━━━')
    
    if hasattr(context, 'stop_trading_remaining_days') and context.stop_trading_remaining_days > 0:
        log.info(f'⏸️【买入】暂停交易中，剩余{context.stop_trading_remaining_days}天')
        return
    
    if context.portfolio.positions:
        hold_list = [f'{get_security_info(s).display_name}({s})' for s in context.portfolio.positions.keys()]
        log.info(f'📦【买入】已有持仓 {len(context.portfolio.positions)}只：{" | ".join(hold_list)}，跳过买入')
        return
    
    target_stocks = select_stock(context)
    if not target_stocks:
        log.info(f'❌【买入】无符合条件股票，跳过')
        return
    
    available_cash = context.portfolio.available_cash
    if available_cash < 1000:
        log.info(f'💸【买入】可用资金不足({available_cash:.2f}元)，跳过')
        return
    
    billboard_flags = getattr(context, 'billboard_flags_cache', {})
    limit_up_flags = getattr(context, 'limit_up_flags_cache', {})
    
    log.info(f'💰【买入】可用资金：{available_cash:,.2f}元 | 目标买入：{len(target_stocks)}只')
    
    for code in target_stocks:
        try:
            current_price = current_data[code].last_price
            if current_price <= 0:
                continue
            
            current_available = context.portfolio.available_cash
            if current_available < 1000:
                log.info(f'⏹️【买入】资金不足，停止买入')
                break
            
            target_cash = current_available * MAX_SINGLE_RATIO
            max_shares = int(target_cash / current_price)
            tradable_shares = (max_shares // 100) * 100
            
            if tradable_shares < 100:
                log.info(f'⚠️【买入】{code} 可买数量不足100股，跳过')
                continue
            
            order_result = order(code, tradable_shares)
            
            if order_result:
                stock_name = get_security_info(code).display_name
                is_billboard = billboard_flags.get(code, False)
                is_limit_up = limit_up_flags.get(code, False)
                g.total_buy_count += 1
                
                if not hasattr(g, 'stock_buy_date'):
                    g.stock_buy_date = {}
                g.stock_buy_date[code] = current_dt.date()
                
                if is_billboard:
                    reason_tag = "📋【龙虎榜优先】"
                elif is_limit_up:
                    reason_tag = "🚀【涨停基因】"
                else:
                    reason_tag = "🎯【常规尾盘】"
                
                g.daily_trades.append({
                    'time': current_dt.strftime('%H:%M'),
                    'code': code,
                    'name': stock_name,
                    'type': '买入',
                    'price': current_price,
                    'shares': tradable_shares,
                    'amount': tradable_shares * current_price
                })
                
                log.info(f'✅ {reason_tag}买入 {code}({stock_name}) | 成交{tradable_shares}股 | 价格:{current_price:.2f} | 金额:{tradable_shares*current_price:,.2f}元 | 龙虎榜:{is_billboard} | 涨停记录:{is_limit_up}')
            else:
                log.info(f'❌【买入失败】{code} 订单未成交')
                
        except Exception as e:
            log.error(f'【买入异常】{code} | {str(e)}')
            continue


# ===================== 收盘总结模块 =====================
def after_market_close_summary(context):
    """
    收盘总结：每日15:05输出完整交易总结
    包含：资产变化、收益率、回撤、当日交易明细、持仓情况（含持仓天数）
    """
    try:
        current_date = context.current_dt.strftime("%Y-%m-%d")
        total_value = context.portfolio.total_value
        cash = context.portfolio.cash
        positions_value = context.portfolio.positions_value
        
        # ==================== 策略收益率计算 ====================
        cumulative_return = (total_value - g.initial_total_value) / g.initial_total_value if g.initial_total_value > 0 else 0
        daily_return = (total_value - g.prev_total_value) / g.prev_total_value if g.prev_total_value > 0 else 0
        
        # ==================== 基准收益率（沪深300） ====================
        benchmark_code = '000300.XSHG'
        benchmark_data = get_price(benchmark_code, start_date=current_date, end_date=current_date, fields=['close'])
        if not benchmark_data.empty:
            current_benchmark = benchmark_data['close'].iloc[-1]
            if g.prev_benchmark is not None:
                benchmark_daily_return = (current_benchmark - g.prev_benchmark) / g.prev_benchmark if g.prev_benchmark > 0 else 0
            else:
                benchmark_daily_return = 0.0
                g.prev_benchmark = current_benchmark
            
            if g.initial_benchmark is None:
                g.initial_benchmark = current_benchmark
            benchmark_cumulative = (current_benchmark - g.initial_benchmark) / g.initial_benchmark if g.initial_benchmark > 0 else 0
        else:
            benchmark_daily_return = 0.0
            benchmark_cumulative = 0.0
        
        # ==================== 最大回撤计算 ====================
        g.max_total_value = max(g.max_total_value, total_value)
        drawdown = (g.max_total_value - total_value) / g.max_total_value if g.max_total_value > 0 else 0
        
        holdings = []
        total_unrealized = 0.0
        current_dt = context.current_dt
        
        for sec, pos in context.portfolio.positions.items():
            if pos.total_amount > 0:
                try:
                    sec_name = get_security_info(sec).display_name
                except:
                    sec_name = sec
                current_price = get_current_data()[sec].last_price
                cost = pos.avg_cost
                
                holding_days = 1
                if hasattr(g, 'stock_buy_date') and sec in g.stock_buy_date:
                    buy_date = g.stock_buy_date[sec]
                    holding_days = (current_dt.date() - buy_date).days
                    holding_days = max(1, holding_days)
                
                pnl_ratio = (current_price - cost) / cost if cost > 0 else 0
                pnl_amount = pos.total_amount * (current_price - cost)
                total_unrealized += pnl_amount
                pnl_icon = '📈' if pnl_ratio > 0 else '📉' if pnl_ratio < 0 else '➖'
                
                holdings.append(f"{pnl_icon} {sec_name}({sec})：{pos.total_amount}股，成本{cost:.2f}，现价{current_price:.2f}，盈亏{pnl_ratio:+.2%}({pnl_amount:+,.0f}元)，📅持仓{holding_days}天")
        
        # ==================== 输出精美总结 ====================
        log.info("")
        log.info("█" * 70)
        log.info(f"█{'【收盘总结】' + current_date:^60}█")
        log.info("█" * 70)
        
        # 资产概览
        log.info(f"├─ 💰 总资产：{total_value:,.2f} 元")
        log.info(f"├─ 💵 现金：{cash:,.2f} 元")
        log.info(f"├─ 📦 持仓市值：{positions_value:,.2f} 元")
        
        # 收益率
        daily_icon = '🟢' if daily_return >= 0 else '🔴'
        cum_icon = '🟢' if cumulative_return >= 0 else '🔴'
        log.info(f"├─ 📊 当日收益率：{daily_icon} {daily_return:+.2%}")
        log.info(f"├─ 📈 累计收益率：{cum_icon} {cumulative_return:+.2%}")
        
        # 基准对比
        benchmark_icon = '🏆' if cumulative_return - benchmark_cumulative >= 0 else '⚠️'
        log.info(f"├─ 📉 基准累计收益：{benchmark_cumulative:+.2%} (沪深300)")
        log.info(f"├─ {benchmark_icon} 超额收益：{cumulative_return - benchmark_cumulative:+.2%}")
        
        # 风险指标
        log.info(f"├─ 📉 当前最大回撤：{drawdown:.2%}")
        log.info(f"├─ 💹 持仓浮动盈亏：{total_unrealized:+,.2f} 元")
        
        # 交易统计
        log.info(f"├─ 🔄 累计交易：买入{g.total_buy_count}次 | 卖出{g.total_sold_count}次")
        
        # 当日交易明细
        if g.daily_trades:
            log.info("├─ 📋 今日交易明细：")
            for trade in g.daily_trades:
                if trade['type'] == '买入':
                    log.info(f"│   🟢 {trade['time']} 【买入】{trade['name']}({trade['code']}) | {trade['shares']}股@{trade['price']:.2f} | 金额:{trade['amount']:,.2f}元")
                elif trade['type'] == '止盈卖出':
                    log.info(f"│   💰 {trade['time']} 【止盈卖出】{trade['name']}({trade['code']}) | 盈利:{trade['pnl']:+.2%} | 价格:{trade['price']:.2f}")
                elif trade['type'] == '止损卖出':
                    log.info(f"│   ⚠️ {trade['time']} 【止损卖出】{trade['name']}({trade['code']}) | 亏损:{trade['pnl']:.2%} | 价格:{trade['price']:.2f}")
        else:
            log.info("├─ 📋 今日交易明细：无交易")
        
        if holdings:
            log.info("├─ 📦 当前持仓明细：")
            for h in holdings:
                log.info(f"│   {h}")
        else:
            log.info("├─ 📦 当前持仓：空仓")
        
        log.info("█" * 70)
        log.info("")
        
        # ==================== 重置当日交易记录 ====================
        g.daily_trades = []
        
        # ==================== 更新前值 ====================
        g.prev_total_value = total_value
        if not benchmark_data.empty:
            g.prev_benchmark = current_benchmark
        
    except Exception as e:
        log.error(f'【收盘总结异常】{str(e)}')
        import traceback
        log.error(traceback.format_exc())