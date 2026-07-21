# Clone from JoinQuant
# postId: 51f7b3aba0a0b9a2768a47ad82011b7b
# backtestId: 3e978e46e860ed4cfd37fb79021a7bcb
# title: 低位3连阳首板接力-年收益1856%-第3版

# 回测2025-01-01到2026-04-27，策略收益1856.78%，年化收益864.73%，最大回撤13.27%，胜率0.582（盈利次数39，亏损次数28）
# 回测2026-01-01到2026-04-27，策略收益166.91%，年化收益1694.78%，最大回撤5.99%，胜率0.833（盈利次数10，亏损次数2）
from jqdata import *
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date, time

# ========== 初始化设置 ==========
def initialize(context):
    """策略初始化函数，设置各项参数和定时任务"""
    log.set_level('order', 'error')        # 设置日志级别，只记录错误信息
    set_option('use_real_price', True)     # 使用真实价格进行交易
    set_option("avoid_future_data", True)  # 防止使用未来数据
    set_slippage(FixedSlippage(0.005))     # 设置滑点为0.5%
    # 设置交易成本：买入时佣金万分之2元，卖出时佣金万分之2元，加千分之0.5元印花税, 每笔交易最低佣金5元
    set_order_cost(OrderCost(close_tax=0.0005, open_commission=0.0002, close_commission=0.0002, min_commission=5), type='stock')
    set_benchmark('399303.XSHE')           # 设置策略基准是国证2000（399303.XSHE，中小盘股指数），用于绩效比较
    
    # 全局变量存储
    g.information = {}          # 存储股票买入信息 {股票代码: {'buy_date': 买入日期}}
    g.sold_stocks = set()       # 已卖出股票集合（当前未使用）
    g.base_stocks = []          # 基础股票池
    g.today_pick = []           # 今日选股结果
    g.pick_cache_date = ''      # 选股缓存日期
    g.minute_sell_cache = {}    # 分钟止盈缓存数据 {股票代码: {'y_close':昨日收盘, 'prev_close':前日收盘, 'y_day_gain':昨日涨幅, 'date':日期}}
    g.close_sell_cache = {}     # 卖出缓存数据 {股票代码: {'y_close':昨日收盘, 'ma5':5日均价}}
    g.today_high = {}           # 当日最高价记录 {股票代码: 当日最高价}
    
    # 仓位控制参数
    g.max_position_pct = 1      # 单只股票最大仓位比例（100%）
    g.max_hold_count = 10       # 最大持仓数量
    
    # 定时任务配置
    run_weekly(prepare_base_stocks, 1, '09:10')            # 每周一09:10更新基础股票池
    run_daily(before_open, time='09:11')                   # 每日09:11过滤股票
    run_daily(precompute_minute_sell_cache, time='09:11')  # 每日09:11预计算卖出缓存
    run_daily(get_buy, time='09:27')                       # 每日09:27执行买入（集合竞价后）
    run_daily(get_close_sell, time='11:25')                # 每日11:25执行卖出检查
    run_daily(get_close_sell, time='13:30')                # 每日13:30执行卖出检查
    run_daily(get_close_sell, time='14:55')                # 每日14:55执行卖出检查
    run_daily(get_minute_sell, time='every_bar')           # 每分钟执行止盈卖出（仅9:30-11:25）
    
# ========== 开盘前过滤股票 ==========
def before_open(context): 
    t_day = context.current_dt.strftime('%Y%m%d')  # 当前日期
    y_day = context.previous_date.strftime('%Y-%m-%d')  # 前一个交易日
    if not g.base_stocks:
        prepare_base_stocks(context)
    
    # ========== 第1步：首板筛选：昨日涨停，前日未涨停 ==========
    g.target_list = filter_first_board(g.base_stocks, y_day)
    log.info(f"[盘前] 首板筛选: {len(g.target_list)}只")
    
    # ========== 第2步：量价过滤（成交量、成交额、涨跌幅等多条件） ==========
    g.target_list = filter_volume_price(g.target_list, y_day)
    log.info(f"[盘前] 量价过滤: {len(g.target_list)}只")
    
    # ========== 第3步：过滤高波动股票（近5日波动>20%的剔除） ==========
    g.target_list = filter_high_volatility(g.target_list, y_day)
    log.info(f"[盘前] 过滤高波动股票: {len(g.target_list)}只")
    
    # ========== 保存结果 ==========
    g.today_pick = g.target_list.copy()
    g.pick_cache_date = t_day
    
# ========== 波动过滤 ==========
def filter_high_volatility(stock_list, y_day):
    """
    高波动过滤：剔除近5日最大波动超过20%的股票
    参数：
        stock_list: 待过滤的股票列表
        y_day: 查询日期
    返回：波动<=20%的股票代码列表
    """
    if not stock_list:
        return []
    # 获取近5日最高价和最低价
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['high', 'low'], count=5, panel=False,
                   skip_paused=True, fill_paused=False)
    if df.empty:
        return stock_list
    grp = df.groupby('code')
    # 计算波动率：(最高价最大值 - 最低价最小值) / 最低价最小值
    chg = (grp['high'].max() - grp['low'].min()) / grp['low'].min()
    return chg[chg <= 0.2].index.tolist()
    
# ========== 量价过滤（已合并爆量检查） ==========
def filter_volume_price(stock_list, y_day):
    """
    量价过滤：综合成交量、成交额、涨跌幅等多条件筛选
    包含爆量检查逻辑
    参数：
        stock_list: 待过滤的股票列表
        y_day: 查询日期
    返回：符合条件的股票代码列表
    """
    if not stock_list:
        return []
    
    # 批量获取35天历史数据，同时满足量价与爆量检查需求
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['close', 'open', 'high', 'volume', 'money'],
                   count=35, skip_paused=True, fq='pre', panel=False)
    if df.empty:
        log.info(f"[量价过滤] 历史数据不足")
        return []
    
    candidates = []
    for code, group in df.groupby('code'):
        if len(group) < 6:  # 至少需要6天数据
            continue
        
        group = group.sort_values('time').reset_index(drop=True)
        last = group.iloc[-1]      # T-1（昨日）
        d_b1 = group.iloc[-2]      # T-2（前日）
        d_b2 = group.iloc[-3]      # T-3
        d_b3 = group.iloc[-4]      # T-4
        
        # 条件1：成交额 5~30亿
        if last.money < 5e8 or last.money > 30e8:
            continue
        
        # 条件2：放量要求 - 昨日成交量 < 前日成交量 * 2，排除
        if d_b1.volume <= 0 or last.volume < d_b1.volume * 2:
            continue
        
        # 条件3：前日成交量不能超过大前天成交量的2倍（避免前日已经放量）
        if d_b2.volume <= 0 or d_b1.volume > d_b2.volume * 2:
            continue
        
        # 条件4：爆量限制（需要至少30天数据）
        # 如果昨日成交量异常放大且价格创30日新高，则排除
        if len(group) >= 30:
            prev_vols = group.volume.iloc[-6:-1].values  # 前5日成交量
            if len(prev_vols) == 5 and prev_vols.min() > 0:
                avg_vol, min_vol = prev_vols.mean(), prev_vols.min()
                if (last.volume > avg_vol * 8 or last.volume > min_vol * 12) and last.close > group.high.iloc[-30:-1].max():
                    continue
        
        # 条件5：双阳线要求 - T-2和T-3均为阳线（收盘>开盘）
        if not (d_b1.close > d_b1.open and d_b2.close > d_b2.open):
            continue
        
        # 条件6：数据异常检查
        if d_b2.close == 0 or d_b3.close == 0:
            continue
        
        # 条件7：短期涨幅限制 - 前两日涨幅均 < 5%
        g1 = (d_b1.close - d_b2.close) / d_b2.close  # T-2涨幅
        g2 = (d_b2.close - d_b3.close) / d_b3.close  # T-3涨幅
        if g1 >= 0.05 or g2 >= 0.05:
            continue
        
        candidates.append(code)
    
    return candidates
    
# ========== 集合竞价过滤 ==========
def filter_auction(stock_list, y_day, t_day_str):
    """
    集合竞价过滤 - 批量版本（更快）
    """
    if not stock_list:
        return []
    
    # 获取昨日数据
    hist_df = get_price(stock_list, end_date=y_day, frequency='1d',
                        fields=['close', 'volume'], count=1,
                        skip_paused=True, panel=False, fill_paused=False)
    
    if hist_df.empty:
        return []
    
    # 批量获取集合竞价数据
    start = f'{t_day_str} 09:15:00'
    end = f'{t_day_str} 09:26:00'
    
    qualified = []
    for stock in stock_list:
        try:
            auction = get_call_auction(stock, start_date=start, end_date=end, fields=['time', 'volume', 'current'])
            if auction.empty:
                continue
            
            last = auction.iloc[-1]
            hist = hist_df[hist_df['code'] == stock].iloc[0]
            
            # 过滤条件
            if (last.volume / hist['volume'] >= 0.03 and 1.0 < last.current / hist['close'] < 1.06):
                qualified.append(stock)
        except:
            continue
    
    return qualified
    
# ========== 买入股票 ==========
def get_buy(context):
    """
    买入函数：在09:27执行，根据选股结果和持仓情况买入
    包含集合竞价实时过滤：竞价成交量、竞价涨幅
    """
    t_day = context.current_dt.strftime('%Y%m%d')  # 当前日期
    t_day_str = context.current_dt.strftime('%Y-%m-%d')  # 当前日期，拼接竞价时间
    y_day = context.previous_date.strftime('%Y-%m-%d')  # 前一个交易日
    c_data = get_current_data()
    
    # 获取当前持仓列表
    holdings = [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]
    if len(holdings) >= g.max_hold_count:
        log.info(f"[持仓已达上限]: {g.max_hold_count} 只")
        return
    
    # 如果今日还未选股，则执行选股（缓存机制，一天只选一次）
    if g.pick_cache_date != t_day:
        g.today_pick = before_open(context)
        g.pick_cache_date = t_day
    
    # 排除已持有的股票
    candidates = [s for s in g.today_pick if s not in holdings]
    log.info(f"[排除持仓后]: {candidates}")
    if not candidates:
        return
    
    # ========== 集合竞价过滤 ==========
    qualified = filter_auction(candidates, y_day, t_day_str)
    log.info(f"[集合竞价过滤后]: {qualified}")
    
    if not qualified:
        return
    
    # 计算可买入数量（不超过仓位上限）
    slots = g.max_hold_count - len(holdings)
    to_buy = qualified[:slots]
    
    # 计算每只股票分配资金
    total = context.portfolio.total_value
    max_per = total * g.max_position_pct
    per_stock = min(context.portfolio.available_cash / len(to_buy), max_per) if to_buy else 0
    log.info(f"[分配资金]: 当前持仓{len(holdings)}只，可再买{slots}只，每只分配{per_stock:.2f}")
    
    # 执行买入
    for s in to_buy:
        try:
            op = c_data[s].day_open  # 当日开盘价
            # 计算可买股数（100股整数倍）
            shares = int(per_stock / op / 100) * 100
            if shares >= 100:
                # 以开盘价买入
                order = order_value(s, per_stock, MarketOrderStyle(op))
                log.info(f"[买入下单] {s}: 开盘价{op:.2f}, 计划金额{per_stock:.2f}, 预计{shares}股")
                # 记录买入日期
                if not hasattr(g, 'information'):
                    g.information = {}
                g.information[s] = {'buy_date': t_day}
            else:
                log.info(f"[买入跳过] {s}: 资金不足1手")
        except Exception as e:
            log.info(f"[买入错误] {s}: {e}")

# ========== 止盈止损（使用盘前缓存，零API调用） ==========
def get_close_sell(context):
    """
    卖出函数：在11:25、13:30、14:55执行
    检查止盈止损条件，触发则清仓
    使用预计算的缓存数据，避免重复API调用
    """
    t_day = context.current_dt.strftime("%Y%m%d")  # 当前日期
    # 获取非今日买入的持仓（今日买入的不卖）
    hold = [s for s, p in context.portfolio.positions.items()
            if p.total_amount > 0 and g.information.get(s, {}).get('buy_date') != t_day]
    if not hold:
        return
    
    metrics = g.close_sell_cache  # 预计算的缓存数据
    c_data = get_current_data()
    
    for s in hold:
        if s not in metrics:
            continue
        pos = context.portfolio.positions[s]
        cd = c_data[s]
        cp = cd.last_price  # 当前价格
        yc = metrics[s]['y_close']  # 昨日收盘价
        ma5 = metrics[s]['ma5']     # 5日均价
        dg = (cp - yc) / yc         # 当日涨跌幅
        pp = (cp - pos.avg_cost) / pos.avg_cost  # 持仓收益率
        
        log.info(f"[持仓检查] {s}: 现价{cp:.2f}, 成本{pos.avg_cost:.2f}, 收益{pp*100:.2f}%, 当日涨跌{dg*100:.2f}%, MA5={ma5:.2f}")
        
        # 接近涨停时继续持有（价格>=涨停价的98.5%）
        if cp >= cd.high_limit * 0.985:
            log.info(f"[持有] {s}: 接近涨停，继续持有")
            continue
        
        # 卖出条件判断
        sell, reason = False, ""
        # 条件1：盈利超过50%
        if pp > 0.5:
            sell, reason = True, "收益>50%"
        # 条件2：当日跌幅超过-2%
        if dg < -0.02:
            sell, reason = True, f"当日涨幅<-2% ({dg*100:.2f}%)"
        # 条件3：当前价跌破开盘价的-4%
        elif cp < cd.day_open * 0.96:
            sell, reason = True, f"当前价<开盘价的-4% ({cp:.2f}<{cd.day_open*0.96:.2f})"
        # 条件4：持仓亏损超过-7%
        elif pp <= -0.07:
            sell, reason = True, f"收益<=-7% ({pp*100:.2f}%)"
        # 条件5：跌破5日均线的-3%
        elif cp < ma5 * 0.97:
            sell, reason = True, f"跌破5日均线-3% ({cp:.2f}<{ma5*0.97:.2f})"
        
        if sell:
            order = order_target_value(s, 0)  # 清仓
            log.info(f"[卖出] {s}: {reason}，清仓")
        else:
            log.info(f"[持有] {s}: 无卖出条件触发")

# ========== 每分钟执行：线性止盈 ==========
def get_minute_sell(context):
    """
    分钟级止盈函数：在9:30-11:25每分钟执行
    实现冲高回落的线性止盈策略 + 基于买入价的止盈条件
    """
    t_day_time = context.current_dt.time()  # 当前时间
    # 仅在上午交易时段执行
    if t_day_time < time(9, 30) or t_day_time > time(11, 25):
        return
    y_day = context.previous_date  # 前一个交易日
    t_day = context.current_dt.strftime("%Y%m%d")  # 当前日期
    # 获取非今日买入的持仓
    hold = [s for s, p in context.portfolio.positions.items()
            if p.total_amount > 0 and g.information.get(s, {}).get('buy_date') != t_day]
    if not hold:
        return
    
    c_data = get_current_data()
    for s in hold:
        cd = c_data[s]
        cp = cd.last_price
        
        # ========== 条件1：涨停不卖 ==========
        if cp >= cd.high_limit * 0.985:
            log.info(f"[分钟止盈] {s}: 接近涨停，继续持有")
            continue
        
        pos = context.portfolio.positions[s]
        buy_price = pos.avg_cost  # 买入成本价
        
        # ========== 新增条件2：昨天买入价格到昨天收盘亏-2%，当前价>买入价2% 卖出 ==========
        cache = g.minute_sell_cache.get(s)
        if cache and cache['date'] == y_day:
            y_close = cache['y_close']  # 昨日收盘价
            if y_close > 0:
                yesterday_loss = (y_close - buy_price) / buy_price
                profit_ratio = (cp - buy_price) / buy_price
                if yesterday_loss < -0.02 and profit_ratio > 0.02:
                    order = order_target_value(s, 0)
                    log.info(f"[分钟止盈-条件2] {s}: 昨日亏损{yesterday_loss*100:.2f}%, 当前盈利{profit_ratio*100:.2f}%>2%, 清仓")
                    g.today_high.pop(s, None)
                    continue
        
        # ========== 新增条件3：昨天买入价格到今天开盘亏-2%，当前价>买入价2% 卖出 ==========
        today_open = cd.day_open
        if today_open > 0:
            open_loss = (today_open - buy_price) / buy_price
            profit_ratio = (cp - buy_price) / buy_price
            if open_loss < -0.02 and profit_ratio > 0.02:
                order = order_target_value(s, 0)
                log.info(f"[分钟止盈-条件3] {s}: 开盘亏损{open_loss*100:.2f}%, 当前盈利{profit_ratio*100:.2f}%>2%, 清仓")
                g.today_high.pop(s, None)
                continue
        
        # ========== 原线性止盈逻辑 ==========
        # 检查缓存数据有效性
        if not cache or cache['date'] != y_day:
            continue
        
        # 接近涨停或昨日已上涨的股票不执行止盈（已在上面判断涨停，这里保留原逻辑的昨日上涨判断）
        if cache['y_day_gain'] >= 0:
            continue
        
        # 更新当日最高价
        th = g.today_high.get(s, 0)
        if cp > th:
            g.today_high[s] = cp
            th = cp
        
        # 计算从昨日收盘价起的最大涨幅
        chr = (th - cache['y_close']) / cache['y_close'] if cache['y_close'] > 0 else 0
        # 如果最大涨幅超过3%，触发线性止盈
        if chr > 0.03:
            # 计算动态回撤容忍度：涨幅越大，容忍回撤越小
            # 公式：max(0.5%, 3% - (超额涨幅)*0.5)
            lt = max(0.005, 0.03 - (chr - 0.01) * 0.5)
            # 如果当前价格回撤超过容忍度，则卖出
            if cp < th * (1 - lt):
                order = order_target_value(s, 0)
                log.info(f"[线性止盈] {s}: 昨日跌幅{cache['y_day_gain']*100:.2f}%, 冲高{chr*100:.2f}%, 回撤{(1-cp/th)*100:.2f}% > {lt*100:.2f}%, 清仓")
                g.today_high.pop(s, None)
                
# ========== 首板筛选：昨日涨停，前日未涨停 ==========
def filter_first_board(stock_list, y_day):
    """
    首板选股：昨日涨停，前日未涨停
    返回：符合条件的股票列表
    """
    # panel=False 返回DataFrame（pandas 0.25+兼容）
    # fill_paused=False 停牌用NaN填充，避免错误判断（停牌股票不算涨停）
    df = get_price(stock_list, end_date=y_day, frequency='daily',
                   fields=['close', 'high_limit'], count=2, 
                   panel=False, fill_paused=False, skip_paused=False)
    
    if df.empty or len(df['time'].unique()) < 2:
        return []
    
    # 停牌股票 close 为 NaN，不会等于 high_limit
    df['is_limit'] = df['close'] == df['high_limit']
    
    # 按日期分组获取涨停股票集合
    groups = df[df['is_limit']].groupby('time')['code'].apply(set)
    
    if len(groups) >= 2:
        return list(groups.iloc[-1] - groups.iloc[-2])
    elif len(groups) == 1:
        return list(groups.iloc[-1])
    return []
    
# ========== 盘前预计算缓存（分钟止盈 + 卖出） ==========
def precompute_minute_sell_cache(context):
    """
    盘前预计算缓存：在09:10执行，预先计算今日卖出所需数据
    避免在交易时段重复调用API，提高运行效率
    """
    y_day = context.previous_date  # 前一个交易日
    pos = list(context.portfolio.positions.keys())
    if not pos:
        g.minute_sell_cache = {}
        g.close_sell_cache = {}
        return
    
    # 计算分钟止盈所需的2日数据
    df2 = get_price(pos, end_date=y_day, frequency='1d',
                    fields=['close'], count=2, panel=False,
                    skip_paused=False, fill_paused=True)
    for s, sub in df2.groupby('code')['close']:
        if len(sub) >= 2:
            yc, pc = sub.iloc[-1], sub.iloc[-2]  # 昨日收盘、前日收盘
            g.minute_sell_cache[s] = {
                'y_close': yc,
                'prev_close': pc,
                'y_day_gain': (yc - pc) / pc if pc > 0 else 0,  # 昨日涨幅
                'date': y_day
            }
    
    # 计算卖出所需的5日数据（5日均线）
    df5 = get_price(pos, end_date=y_day, frequency='1d',
                    fields=['close'], count=5, panel=False,
                    skip_paused=False, fill_paused=True)
    g.close_sell_cache = {}
    for s, sub in df5.groupby('code')['close']:
        if len(sub) >= 2:
            g.close_sell_cache[s] = {
                'y_close': sub.iloc[-1],  # 昨日收盘
                'ma5': sub.mean()         # 5日均价
            }
    
    # 清空当日最高价记录
    g.today_high.clear()
    
# ========== 基础股票池：流通市值30-300亿元，剔除新股ST退市科创北证 ==========
def prepare_base_stocks(context):
    by_date = context.previous_date - timedelta(days=60)
    stock_list = list(get_all_securities(['stock'], date=by_date).index)
    current_data = get_current_data()
    stock_list = [code for code in stock_list if not (
        code.startswith(('3', '68', '4', '8', '9'))
        or current_data[code].is_st
        or current_data[code].paused
        or '退' in current_data[code].name
    )]
    g.base_stocks = get_fundamentals(
        query(valuation.code).filter(
            valuation.code.in_(stock_list),
            valuation.circulating_market_cap.between(30, 300)
        )
    )['code'].tolist()
    log.info(f"[基础股票池]：{len(g.base_stocks)}只")
    
# ========== 收盘后清理 ==========
def after_trading_end(context):
    """
    收盘后执行：清理无效数据，同步持仓信息
    """
    # 清空已卖出股票集合
    g.sold_stocks.clear()
    # 获取当前持仓
    cur = set(context.portfolio.positions.keys())
    # 只保留当前持仓的信息
    g.information = {k: v for k, v in g.information.items() if k in cur}
    g.minute_sell_cache = {k: v for k, v in g.minute_sell_cache.items() if k in cur}
    g.close_sell_cache = {k: v for k, v in g.close_sell_cache.items() if k in cur}
    # 清空当日最高价记录
    g.today_high.clear()