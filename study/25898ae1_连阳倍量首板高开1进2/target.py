# Clone from JoinQuant
# postId: 25898ae1accce575fb6a443ab0990293
# backtestId: ea4e5e216f5b17570091576cfc4755a6
# title: 连阳倍量首板高开 1进2 收益823% 回撤13%

from jqdata import *
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date, time

# ========== 初始化设置 ==========
def initialize(context):
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    g.information = {}          # 记录每只股票买入日期，用于判断T+1（当日买入不可卖出）
    g.sold_stocks = set()
    g.base_stocks = []          # 经过基础过滤的可交易股票池
    g.today_pick = []           # 缓存当日选股结果，避免盘中重复计算
    g.pick_cache_date = ''
    run_weekly(before_market_open, 1, '09:10')
    run_daily(get_buy, '09:26')
    run_daily(get_close_sell, time='11:25')
    run_daily(get_close_sell, time='13:30')
    run_daily(get_close_sell, time='14:55')
    
# ========== 选股逻辑 ==========
# 目标：昨日首板涨停后，波动率/市值/量价/集合竞价筛选，找出次日高开的接力标的
def get_stock_list(context):
    target_list = prepare_stock_list(context)
    print(f"[选股] 首板标的数量: {len(target_list)}只")
    if not target_list:
        print("[选股] 无首板标的，结束选股")
        return []
    
    y_day = context.previous_date
    t_now = context.current_dt.strftime("%Y-%m-%d")
    
    # 波动过滤
    target_list = filter_high_volatility(target_list, y_day)
    log.info(f"[选股] 过滤近5日波动>20%后: {len(target_list)}只")
    if not target_list:
        print("[选股] 波动过滤后无标的，结束")
        return []
    
    # 市值过滤
    valuation_df = get_valuation(target_list, start_date=y_day, end_date=y_day, fields=['market_cap', 'circulating_market_cap'])
    valuation_df.set_index('code', inplace=True)
    mask = (valuation_df['market_cap'] >= 30) & (valuation_df['circulating_market_cap'] <= 300)
    filtered = valuation_df[mask].index.tolist()
    print(f"[选股] 市值过滤结果: {len(target_list)} -> {len(filtered)}只")
    
    if not filtered:
        print("[选股] 市值过滤后无标的，结束")
        return []
    
    # 获取近4日日线数据
    df = get_price(filtered, end_date=y_day, frequency='1d', 
                   fields=['close', 'open', 'volume', 'money', 'high', 'low'], 
                   count=4, panel=False, skip_paused=True, fill_paused=False)
    hist_dict = {
        code: group.sort_values('time').reset_index(drop=True)
        for code, group in df.groupby('code')
        if len(group) >= 4
    }
    print(f"[选股] 成功获取近4日数据: {len(hist_dict)}只")
    candidates = []
    for s, hist in hist_dict.items():
        last = hist.iloc[-1]   # 昨日（涨停日）数据
        d_b1 = hist.iloc[-2]   # 涨停前一日（T-2）
        d_b2 = hist.iloc[-3]   # 涨停前两日（T-3）
        d_b3 = hist.iloc[-4]   # 涨停前三日（T-4）
        # 成交额过滤：昨日成交额需在5亿~30亿之间
        money_y = last['money'] / 1e8
        if last['money'] < 5e8 or last['money'] > 30e8:
            print(f"  [过滤-成交额] {s}: 昨日成交{money_y:.2f}亿，不在5~30亿区间")
            continue
        # 放量要求：昨日成交量 >= 前日成交量的2倍
        vol_ratio = last['volume'] / d_b1['volume'] if d_b1['volume'] > 0 else 0
        if last['volume'] < d_b1['volume'] * 2:
            print(f"  [过滤-放量] {s}: 量比{vol_ratio:.2f}倍，不足2倍 (昨日量{last['volume']}, 前日量{d_b1['volume']})")
            continue
        # 趋势过滤：涨停前两日（T-2、T-3）必须收阳线
        t2_yang = d_b1['close'] > d_b1['open']
        t3_yang = d_b2['close'] > d_b2['open']
        if not (t2_yang and t3_yang):
            print(f"  [过滤-趋势] {s}: T-2阳线{t2_yang}, T-3阳线{t3_yang}，不满足双阳线")
            continue
        # 防御性处理：避免除零错误（处理长期停牌后复牌等异常数据）
        if d_b2['close'] == 0 or d_b3['close'] == 0:
            print(f"  [过滤-数据异常] {s}: T-3或T-4收盘价为0，疑似异常数据")
            continue
        # 计算涨停前两日（T-2、T-3）的涨幅
        gain1 = (d_b1['close'] - d_b2['close']) / d_b2['close']
        gain2 = (d_b2['close'] - d_b3['close']) / d_b3['close']
        # 短期涨幅过滤：前两日涨幅均不得超过5%
        if gain1 >= 0.05 or gain2 >= 0.05:
            print(f"  [过滤-涨幅] {s}: T-2涨幅{gain1*100:.2f}%, T-3涨幅{gain2*100:.2f}%，超过5%")
            continue
        print(f"  [通过-量价] {s}: 成交{money_y:.2f}亿, 量比{vol_ratio:.2f}, T-2涨{gain1*100:.2f}%, T-3涨{gain2*100:.2f}%")
        candidates.append(s)
    print(f"[选股] 量价过滤通过: {len(candidates)}只 {candidates}")
    if not candidates:
        print("[选股] 量价过滤后无标的，结束")
        return []
    # 集合竞价过滤（9:15~9:26）：通过早盘竞价数据筛选高开但不过分高的标的
    start = t_now + ' 09:15:00'
    end = t_now + ' 09:26:00'
    sbgk_stocks = []
    for s in candidates:
        auction = get_call_auction(s, start_date=start, end_date=end, fields=['time', 'volume', 'current'])
        if auction.empty:
            print(f"  [过滤-竞价无数据] {s}: 未获取到集合竞价数据")
            continue
        auction = auction.iloc[-1]  # 取集合竞价结束前的最后一笔撮合数据
        hist = hist_dict[s]
        last = hist.iloc[-1]
        # 集合竞价量比：早盘竞价成交量 >= 昨日全天成交量的3%
        auction_vol_ratio = auction['volume'] / last['volume'] if last['volume'] > 0 else 0
        if auction['volume'] / last['volume'] < 0.03:
            print(f"  [过滤-竞价量] {s}: 竞价量/昨日量={auction_vol_ratio:.4f}，不足3% (竞价量{auction['volume']}, 昨日量{last['volume']})")
            continue
        # 高开幅度过滤：仅保留高开1%~6%的标的
        current_ratio = auction['current'] / last['close']
        if current_ratio <= 1 or current_ratio >= 1.06:
            print(f"  [过滤-高开] {s}: 竞价价{auction['current']:.2f}/昨收{last['close']:.2f}={(current_ratio-1)*100:.2f}%，不在1%~6%区间")
            continue
        print(f"  [通过-竞价] {s}: 竞价量比{auction_vol_ratio:.4f}, 高开{(current_ratio-1)*100:.2f}%")
        sbgk_stocks.append(s)
    print(f"[选股] 最终选中: {sbgk_stocks}")
    return sbgk_stocks
    
# ========== 买入股票 ==========
def get_buy(context):
    c_data = get_current_data()
    t_date = context.current_dt.strftime('%Y%m%d')
    # 日线级别缓存：仅在日期变化时重新选股，避免盘中重复调用
    if not hasattr(g, 'pick_cache_date') or g.pick_cache_date != t_date:
        print(f"[买入] 日期变更，重新选股")
        g.today_pick = get_stock_list(context)
        g.pick_cache_date = t_date
    qualified_stocks = g.today_pick
    print(f"[买入] 今日候选标的: {qualified_stocks}")
    if qualified_stocks:
        # 等权分配：将当前可用资金平均分配给所有选中标的
        value = context.portfolio.available_cash / len(qualified_stocks)
        print(f"[买入] 可用资金: {context.portfolio.available_cash:.2f}, 标的数: {len(qualified_stocks)}, 每只理论分配: {value:.2f}")
        for s in qualified_stocks:
            day_open = c_data[s].day_open
            can_buy_shares = int(context.portfolio.available_cash / day_open / 100) * 100
            if can_buy_shares >= 100:
                order = order_value(s, value, MarketOrderStyle(day_open))
                print(f"  [买入下单] {s}: 开盘价{day_open:.2f}, 金额{value:.2f}, 预计可买{can_buy_shares}股, 订单对象{order}")
                g.information[s] = {'buy_date': t_date}
            else:
                print(f"  [买入跳过] {s}: 资金不足买入1手, 可用{context.portfolio.available_cash:.2f}, 开盘价{day_open:.2f}, 可买{can_buy_shares}股")
    else:
        print("[买入] 今日无候选标的，不操作")
        
# ========== 尾盘止盈止损 ==========
def get_close_sell(context):
    y_day = context.previous_date
    t_date = context.current_dt.strftime("%Y%m%d")
    # 构建可卖持仓列表：剔除当日买入的标的（A股T+1制度）
    hold_stocks = []
    for stock, pos in context.portfolio.positions.items():
        if pos.total_amount == 0:
            continue
        info = g.information.get(stock)
        if info and info.get('buy_date') == t_date:
            continue
        hold_stocks.append(stock)
    print(f"[尾盘] 开始检查持仓，可卖标的: {hold_stocks}")
    if not hold_stocks:
        print("[尾盘] 无持仓可卖")
        return
    # 获取近5日收盘价：用于计算昨日收盘及5日均线（MA5）
    df = get_price(hold_stocks, end_date=y_day, frequency='1d', 
               fields=['close'], count=5, panel=False, 
               skip_paused=False, fill_paused=True)
    metrics = {}
    for s in hold_stocks:
        sub = df[df['code'] == s]['close']
        if len(sub) >= 2:
            metrics[s] = {
                'y_close': sub.iloc[-1],  # 昨日收盘价，用于计算当日涨跌幅
                'ma5': sub.mean()         # 5日均价，作为短期趋势支撑/压力位
            }
    c_data = get_current_data()
    for stock in hold_stocks:
        if stock not in metrics:
            print(f"  [卖出跳过] {stock}: 未获取到价格数据")
            continue
        pos = context.portfolio.positions[stock]
        cd = c_data[stock]
        current_price = cd.last_price
        day_open = cd.day_open
        y_close = metrics[stock]['y_close']
        ma5 = metrics[stock]['ma5']
        # 计算当日涨跌幅（相对于昨日收盘）及持仓收益率
        day_gain = (current_price - y_close) / y_close
        cost = pos.avg_cost
        profit_pct = (current_price - cost) / cost
        print(f"  [持仓检查] {stock}: 现价{current_price:.2f}, 成本{cost:.2f}, 持仓收益{profit_pct*100:.2f}%, 当日涨跌{day_gain*100:.2f}%, MA5={ma5:.2f}, 涨停价{cd.high_limit:.2f}")
        # 涨停持有策略：若价格接近涨停价（>=涨停价*0.99），继续持有博次日溢价
        if current_price >= cd.high_limit * 0.99:
            print(f"[持有] {stock}: 接近涨停({current_price:.2f}>={cd.high_limit*0.99:.2f})，继续持有博溢价")
            continue
        sell = False
        reason = ""
        # 止盈条件：浮盈超过50%，主动锁定大幅利润
        if profit_pct > 0.5:
            sell = True
            reason = "收益>50%"
        # 以下为止损/风控条件，采用if-elif链保证只触发一个卖出理由
        # 日内风控：当日跌幅超过2%（相对于昨日收盘），无条件减仓
        if day_gain < -0.02:
            sell = True
            reason = f"当日涨幅<-2% ({day_gain*100:.2f}%)"
        # 开盘弱势：当前价跌破开盘价4%，说明开盘冲高后资金出逃
        elif current_price < day_open * 0.96:
            sell = True
            reason = f"当前价<开盘价的-4% ({current_price:.2f}<{day_open*0.96:.2f})"
        # 硬性止损：亏损达到7%，强制割肉防止深套
        elif profit_pct <= -0.07:
            sell = True
            reason = f"收益<=-7% ({profit_pct*100:.2f}%)"
        # 趋势止损：收盘价跌破5日均线3%，短期上升趋势被破坏
        elif current_price < ma5 * 0.97:
            sell = True
            reason = f"跌破5日均线-3% ({current_price:.2f}<{ma5*0.97:.2f})"
        if sell:
            order = order_target_value(stock, 0)  # 清仓该标的
            print(f"    [卖出] {stock}: {reason}，清仓，订单对象{order}")
        else:
            print(f"    [持有] {stock}: 无卖出条件触发，继续持有")
            
# ========== 波动过滤 ==========
# 逻辑：过滤掉近5日最高价到最低价涨幅超过20%的股票
def filter_high_volatility(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='1d', 
               fields=['high', 'low'], count=5, panel=False, 
               skip_paused=True, fill_paused=False)
    if df.empty:
        log.warning("[波动过滤] 未获取到价格数据，跳过过滤")
        return stock_list
    grp = df.groupby('code')
    max_h = grp['high'].max()
    min_l = grp['low'].min()
    chg = (max_h - min_l) / min_l
    qualified = chg[chg <= 0.2].index.tolist()
    excluded = len(stock_list) - len(qualified)
    if excluded > 0:
        # 打印被过滤的股票详情（可选调试用）
        filtered_out = chg[chg > 0.2].index.tolist()
        for s in filtered_out[:5]:  # 只打印前5个避免日志过长
            print(f"  [过滤-波动] {s}: 5日波动{(chg[s])*100:.1f}% > 20%")
        log.info(f"[波动过滤] 排除{excluded}只（波动>20%），剩余{len(qualified)}只")
    return qualified
    
# ========== 首板过滤 ==========
# 逻辑：从基础股票池中找出"昨日首板"标的（昨日涨停，但前一日未涨停）
def prepare_stock_list(context):
    y_day = context.previous_date
    if not hasattr(g, 'base_stocks'):
        before_market_open(context)
    # 获取近2日数据，包含收盘价与涨停价（复权）
    df = get_price(g.base_stocks, end_date=y_day, frequency='1d', 
               fields=['close', 'high_limit'], count=2, panel=False, 
               skip_paused=True, fill_paused=False, fq='pre')
    if len(df) < 2:
        return []
    # 判断是否涨停：收盘价接近涨停价（容差rtol=0.005, atol=0.01处理复权精度问题）
    df['is_limit'] = np.isclose(df['close'], df['high_limit'], rtol=0.005, atol=0.01)
    # 按日期分组，获取每日涨停股票集合
    groups = df[df['is_limit']].groupby('time')['code'].agg(set)
    # 集合差运算：groups.iloc[-1]为昨日涨停股，groups.iloc[-2]为前日涨停股
    # 结果即为"昨日涨停且前日未涨停"的首板标的
    if len(groups) >= 2:
        yest_limit = groups.iloc[-1]
        prev_limit = groups.iloc[-2]
        result = list(yest_limit - prev_limit)
        print(f"[首板过滤] 昨日涨停{len(yest_limit)}只, 前日涨停{len(prev_limit)}只, 首板标的{len(result)}只")
    elif len(groups) == 1:
        result = list(groups.iloc[-1])
        print(f"[首板过滤] 仅昨日有涨停{len(result)}只，前日无涨停，全部视为首板")
    else:
        result = []
        print(f"[首板过滤] 近2日无涨停标的")
    if result:
        print(f"[首板过滤] 首板列表: {result}")
    return result
    
# ========== 初始化股票池 ==========
def before_market_open(context):
    by_date = get_trade_days(end_date=context.previous_date, count=50)[0]
    all_s = get_all_securities(['stock'], date=by_date).index
    c_data = get_current_data()
    g.base_stocks = [s for s in all_s if not (
        s[0] in ('3', '4', '8', '9') or 
        s[:2] == '68' or 
        c_data[s].is_st or 
        c_data[s].paused or 
        '退' in c_data[s].name or 
        'ST' in c_data[s].name
    )]
    
# ========== 收盘后清理 ==========
def after_trading_end(context):
    g.sold_stocks.clear()
    current_positions = set(context.portfolio.positions.keys())
    removed = 0
    for stock in list(g.information.keys()):
        if stock not in current_positions:
            del g.information[stock]
            removed += 1
# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
except NameError:
    pass
# ===== END OVERRIDE =====
