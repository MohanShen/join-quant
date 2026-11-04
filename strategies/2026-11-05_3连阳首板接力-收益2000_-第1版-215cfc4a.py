# Clone from JoinQuant
# postId: 215cfc4ac6d82c4ebbbe6dca67f73a46
# backtestId: 7e03eb246ab1d1da0a3f7c994c0c4d35
# title: 3连阳首板接力-收益2000%-第1版

# 3连阳首板-第1版-原创-2026.01.12
from jqdata import *
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date, time

# ========== 初始化设置 ==========
def initialize(context):
    """策略初始化：设置参数、注册定时任务"""
    log.set_level('order', 'error')                  # 只记录错误日志
    set_option('use_real_price', True)               # 使用真实价格交易
    set_option("avoid_future_data", True)            # 防止未来数据
    set_slippage(PriceRelatedSlippage(0.002))        # 滑点 0.2%
    set_benchmark('000300.XSHG')                     # 基准：沪深300
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0002,
                             close_commission=0.0002, min_commission=5), type='stock')

    # 全局变量存储
    g.information = {}           # 存储股票买入信息 {股票代码: {'buy_date': 买入日期, 'max_pp': 最高收益率}}
    g.sold_stocks = set()        # 已卖出股票集合（当前未使用）
    g.base_stocks = []           # 基础股票池
    g.today_pick = []            # 今日选股结果
    g.pick_cache_date = ''       # 选股缓存日期
    g.minute_sell_cache = {}     # 分钟止盈缓存数据
    g.close_sell_cache = {}      # 尾盘卖出缓存数据 {股票代码: {'y_close':昨日收盘, 'ma5':5日均价}}
    g.today_high = {}            # 当日最高价记录 {股票代码: 当日最高价}

    # 仓位控制参数
    g.max_position_pct = 1       # 单只股票最大仓位比例（N%）
    g.max_hold_count = 10        # 最大持仓数量

    # 定时任务配置
    run_weekly(get_base_stocks, 1, '09:11')                # 每周一09:11 刷新主板列表
    run_daily(get_sell_cache, time='09:12')                # 每日09:12 预计算卖出缓存
    run_daily(before_open, time='09:13')                   # 每日09:13 运行选股
    run_daily(get_buy, time='09:26')                       # 每日09:26 执行买入（集合竞价后）
    run_daily(get_close_sell, time='11:25')                # 每日11:25 执行尾盘卖出检查
    run_daily(get_close_sell, time='13:30')                # 每日13:30 执行尾盘卖出检查
    run_daily(get_close_sell, time='14:55')                # 每日14:55 执行尾盘卖出检查
    run_daily(get_minute_sell, time='every_bar')           # 每分钟执行止盈卖出（仅9:30-14:56）
    
# ========== 开盘前过滤股票 ==========
def before_open(context):
    """盘前选股主流程：首板 -> 高波动过滤 -> 量价过滤 -> 保存今日候选"""
    t_day = context.current_dt.strftime('%Y%m%d')        # 当前日期
    y_day = context.previous_date.strftime('%Y-%m-%d')   # 前一个交易日

    # 若基础股票池为空，则先刷新
    if not g.base_stocks:
        get_base_stocks(context)

    log.info("[盘前] 开始选股，T日=%s，T-1日=%s", t_day, y_day)
    log.info("[盘前] 基础股票池=%d只", len(g.base_stocks))

    # ========== 第1步：首板筛选：昨日涨停，前日未涨停 ==========
    g.target_list = filter_first_board(g.base_stocks, y_day)

    # ========== 第2步：过滤高波动股票 ==========
    g.target_list = filter_high_volatility(g.target_list, y_day)

    # ========== 第3步：量价过滤（成交量、成交额、涨跌幅等多条件） ==========
    g.target_list = filter_volume_price(g.target_list, y_day)

    # ========== 保存结果 ==========
    g.today_pick = g.target_list.copy()
    g.pick_cache_date = t_day

    log.info("[盘前] 选股完成，今日候选=%d只，候选列表=%s", len(g.today_pick), g.today_pick)

# ========== 波动过滤 ==========
def filter_high_volatility(stock_list, y_day):
    """
    高波动过滤：剔除近N日最大波动超过N%的股票，非核心条件，贡献5%
    参数：
        stock_list: 待过滤的股票列表
        y_day: 查询日期
    返回：波动<=N%的股票代码列表
    """
    if not stock_list:
        return []

    # 获取近5日最高价和最低价
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['high', 'low'], count=5, panel=False,
                   skip_paused=True, fill_paused=False)
    if df.empty:
        log.info("[波动过滤] 历史数据为空，返回原列表")
        return stock_list

    grp = df.groupby('code')
    # 计算波动率：(最高价最大值 - 最低价最小值) / 最低价最小值
    chg = (grp['high'].max() - grp['low'].min()) / grp['low'].min()

    kept = []
    for code in stock_list:
        if code not in chg.index:
            log.info("[波动过滤] %s 淘汰 原因=无5日高低数据", code)
            continue
        v = chg[code]
        if v <= 0.2:
            kept.append(code)
        else:
            log.info("[波动过滤] %s 淘汰 原因=波动率%.2f%%>20%%", code, v * 100)

    log.info("[波动过滤] 输入=%d只，保留=%d只，剔除=%d只", len(stock_list), len(kept), len(stock_list) - len(kept))
    return kept

# ========== 量价过滤（已合并爆量检查） ==========
def filter_volume_price(stock_list, y_day):
    """
    量价过滤：综合成交量、成交额、涨跌幅等多条件筛选
    包含爆量检查逻辑
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
            log.info("[量价过滤] %s 淘汰 原因=数据不足6天 len=%d", code, len(group))
            continue
        
        group = group.sort_values('time').reset_index(drop=True)
        last = group.iloc[-1]      # T-1（昨日）
        d_b1 = group.iloc[-2]      # T-2（前日）
        d_b2 = group.iloc[-3]      # T-3（大前日）
        d_b3 = group.iloc[-4]      # T-4（为了算涨幅）
        
        # 条件1（核心条件，贡献80%）：双阳线要求 - T-2和T-3均为阳线（收盘>开盘）
        cond_d_b1_yang = d_b1.close > d_b1.open
        cond_d_b2_yang = d_b2.close > d_b2.open
        if not (cond_d_b1_yang and cond_d_b2_yang):
            log.info("[量价过滤] %s 淘汰 原因=非双阳线 d_b1_close=%.2f d_b1_open=%.2f "
                     "d_b2_close=%.2f d_b2_open=%.2f d_b1_yang=%s d_b2_yang=%s",
                     code, d_b1.close, d_b1.open, d_b2.close, d_b2.open,
                     cond_d_b1_yang, cond_d_b2_yang)
            continue
        
        # 条件2（核心条件，贡献20%）：放量要求 - 昨日成交量 >= 前日成交量 * 2
        if d_b1.volume <= 0:
            continue
        if d_b2.volume <= 0:
            continue
        ratio2 = last.volume / d_b1.volume
        if last.volume < d_b1.volume * 2:
            log.info("[量价过滤] %s 淘汰 原因=昨日量未达前日2倍 last_vol=%.0f d_b1_vol=%.0f ratio=%.2f",
                     code, last.volume, d_b1.volume, ratio2)
            continue
        
        # 条件3（核心条件，贡献10%）：成交额 5~40亿
        if last.money < 5e8 or last.money > 40e8:
            log.info("[量价过滤] %s 淘汰 原因=成交额不在5~40亿 money=%.2f亿",
                     code, last.money / 1e8)
            continue
        
        # 条件4（拟合条件，贡献1%）：已经放量要排除 - 前日量 > 大前天量 × 2
        ratio3 = d_b1.volume / d_b2.volume
        if d_b1.volume > d_b2.volume * 2:
            log.info("[量价过滤] %s 淘汰 原因=前日量超过大前日2倍 d_b1_vol=%.0f d_b2_vol=%.0f ratio=%.2f",
                     code, d_b1.volume, d_b2.volume, ratio3)
            continue
        
        # 条件5（拟合条件，贡献1%）：短期涨幅限制 - 前两日涨幅均 < 5%
        if d_b2.close == 0 or d_b3.close == 0:
            continue
        g1 = (d_b1.close - d_b2.close) / d_b2.close  # T-2 前日涨幅
        g2 = (d_b2.close - d_b3.close) / d_b3.close  # T-3 大前日涨幅
        if g1 >= 0.05 or g2 >= 0.05:
            log.info("[量价过滤] %s 淘汰 原因=前两日涨幅>=5%% g1=%.2f%% g2=%.2f%% "
                     "d_b1_close=%.2f d_b2_close=%.2f d_b3_close=%.2f",
                     code, g1 * 100, g2 * 100, d_b1.close, d_b2.close, d_b3.close)
            continue
        
        # 条件6：爆量限制（拟合条件，负贡献-1%）
        if len(group) >= 30:
            prev_vols = group.volume.iloc[-6:-1].values  # 前5日成交量
            if len(prev_vols) == 5 and prev_vols.min() > 0:
                avg_vol, min_vol = prev_vols.mean(), prev_vols.min()
                high_30 = group.high.iloc[-30:-1].max()
                cond_a = last.volume > avg_vol * 8
                cond_b = last.volume > min_vol * 12
                cond_c = last.close > high_30
                if (cond_a or cond_b) and cond_c:
                    log.info("[量价过滤] %s 淘汰 原因=爆量限制 last_vol=%.0f avg5=%.0f min5=%.0f "
                             "ratio_avg=%.2f ratio_min=%.2f close=%.2f high30=%.2f",
                             code, last.volume, avg_vol, min_vol,
                             last.volume / avg_vol, last.volume / min_vol,
                             last.close, high_30)
                    continue
                
        candidates.append(code)

    log.info("[量价过滤] 输入=%d只，保留=%d只，剔除=%d只", len(stock_list), len(candidates), len(stock_list) - len(candidates))
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
        log.info("[竞价过滤] 昨日历史数据为空，返回空")
        return []

    # 批量获取集合竞价数据
    start = f'{t_day_str} 09:15:00'
    end = f'{t_day_str} 09:26:00'

    qualified = []
    for stock in stock_list:
        try:
            auction = get_call_auction(stock, start_date=start, end_date=end, fields=['time', 'volume', 'current'])
            if auction.empty:
                log.info("[竞价过滤] %s 淘汰 原因=无集合竞价数据", stock)
                continue

            last = auction.iloc[-1]
            hist_rows = hist_df[hist_df['code'] == stock]
            if hist_rows.empty:
                log.info("[竞价过滤] %s 淘汰 原因=无昨日历史数据", stock)
                continue
            hist = hist_rows.iloc[0]

            vol_ratio = last.volume / hist['volume'] if hist['volume'] > 0 else 0
            price_ratio = last.current / hist['close'] if hist['close'] > 0 else 0

            cond_vol = vol_ratio >= 0.03
            cond_price = 1.0 < price_ratio < 1.06

            if cond_vol and cond_price:
                qualified.append(stock)
            else:
                reasons = []
                if not cond_vol:
                    reasons.append(f"量比不足 vol_ratio={vol_ratio*100:.2f}%<3%")
                if not cond_price:
                    reasons.append(f"涨幅不在1%~6% price_ratio={price_ratio*100:.2f}%")
                log.info("[竞价过滤] %s 淘汰 原因=%s auction_vol=%.0f hist_vol=%.0f auction_price=%.2f hist_close=%.2f",
                         stock, "; ".join(reasons),
                         last.volume, hist['volume'], last.current, hist['close'])
        except Exception as e:
            log.info("[竞价过滤] %s 淘汰 原因=异常 %s", stock, str(e))
            continue

    log.info("[竞价过滤] 输入=%d只，合格=%d只，合格列表=%s",
             len(stock_list), len(qualified), qualified)
    return qualified

# ========== 买入股票 ==========
def get_buy(context):
    """09:26 执行买入：先做集合竞价过滤，再按槽位与资金分配下单"""
    t_day = context.current_dt.strftime('%Y%m%d')
    t_day_str = context.current_dt.strftime('%Y-%m-%d')
    y_day = context.previous_date.strftime('%Y-%m-%d')
    c_data = get_current_data()

    holdings = [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]
    log.info(f"[买入] 当前持仓 {len(holdings)} 只: {holdings}")

    # 持仓已达上限，直接跳过
    if len(holdings) >= g.max_hold_count:
        log.info(f"[买入] 持仓已达上限 {g.max_hold_count} 只，跳过")
        return

    # 若今日尚未选股，则补跑一次盘前选股
    if g.pick_cache_date != t_day:
        log.info("[买入] 今日尚未选股，补跑 before_open")
        g.today_pick = before_open(context)
        g.pick_cache_date = t_day

    # 排除已持仓股票
    candidates = [s for s in g.today_pick if s not in holdings]
    log.info(f"[买入] 候选标的(排除持仓后) {len(candidates)} 只: {candidates}")
    if not candidates:
        return

    # 集合竞价过滤
    qualified = filter_auction(candidates, y_day, t_day_str)
    log.info(f"[买入] 集合竞价过滤后 {len(qualified)} 只: {qualified}")

    if not qualified:
        return

    # 计算可买槽位与每只分配资金
    slots = g.max_hold_count - len(holdings)
    to_buy = qualified[:slots]
    log.info(f"[买入] 可买槽位={slots} 实际下单={to_buy}")

    total = context.portfolio.total_value
    max_per = total * g.max_position_pct
    per_stock = min(context.portfolio.available_cash / len(to_buy), max_per) if to_buy else 0
    log.info(f"[买入] 总资产={total:.2f} 每只分配={per_stock:.2f}")

    # 判断当前是否已到连续竞价（09:30之后）
    now = context.current_dt
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    is_continuous = now >= market_open  # True=09:30后

    for s in to_buy:
        cd = c_data[s]
        op = cd.day_open

        # 核心：09:30后用最新价，09:30前用开盘价
        if is_continuous:
            cp = cd.last_price      # 真实当前价
        else:
            cp = cd.day_open        # 09:27集合竞价刚出的开盘价

        # v14: 跳过一字板（无法买入）
        if op >= cd.high_limit * 0.99:
            log.info(f"[买入跳过] {s}: 一字板无法买入")
            continue

        shares = int(per_stock / cp / 100) * 100
        if shares >= 100:
            order = order_target(s, shares, MarketOrderStyle(cp))
            log.info(f"[买入下单] {s}: 开盘价{op:.2f},当前价{cp:.2f}, 金额{per_stock:.2f}, 预计{shares}股")

            # 记录买入信息，供后续卖出逻辑使用
            if not hasattr(g, 'information'):
                g.information = {}
            g.information[s] = {'buy_date': t_day, 'max_pp': 0.0}
        else:
            log.info(f"[买入跳过] {s}: 资金不足1手")

# ========== 尾盘止盈止损 ==========
def get_close_sell(context):
    """
    尾盘止盈止损：11:25 / 13:30 / 14:55 执行
    依赖缓存：g.close_sell_cache = {code: {y_close, ma5}}
    """
    hhmm = context.current_dt.strftime("%H:%M")
    if hhmm not in ('11:25', '13:30', '14:55'):
        return

    t_day = context.current_dt.strftime("%Y%m%d")

    # ---------- 获取非今日买入的持仓 ----------
    info = getattr(g, 'information', {}) or {}
    hold = []
    for s, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        buy_date = info.get(s, {}).get('buy_date')
        if buy_date is None or buy_date == t_day:
            continue
        hold.append(s)

    log.info(f"[尾盘] 可卖标的: {hold}")
    if not hold:
        return

    metrics = getattr(g, 'close_sell_cache', {}) or {}
    c_data = get_current_data()

    for s in hold:
        # ---------- 缓存缺失保护 ----------
        if s not in metrics:
            log.info(f"[跳过] {s}: 缓存缺失，无法判断")
            continue

        pos = context.portfolio.positions[s]
        cd = c_data[s]

        # ---------- 停牌保护 ----------
        if cd.paused:
            log.info(f"[跳过] {s}: 停牌")
            continue

        cp = cd.last_price
        yc = metrics[s]['y_close']
        ma5 = metrics[s]['ma5']

        if not yc or not pos.avg_cost:
            log.info(f"[跳过] {s}: 缓存或成本异常 yc={yc} cost={pos.avg_cost}")
            continue

        dg = (cp - yc) / yc
        pp = (cp - pos.avg_cost) / pos.avg_cost

        # ---------- 更新历史最高收益率 ----------
        max_pp = info[s].get('max_pp', pp)
        info[s]['max_pp'] = max(max_pp, pp)
        max_pp = info[s]['max_pp']

        log.info(
            f"[持仓检查] {s}: 现价{cp:.2f}, 成本{pos.avg_cost:.2f}, "
            f"当前收益{pp*100:.2f}%, 最高收益{max_pp*100:.2f}%, "
            f"当日涨跌{dg*100:.2f}%, MA5={ma5:.2f}"
        )

        # ---------- 接近涨停继续持有 ----------
        if cp >= cd.high_limit * 0.99:
            log.info(f"[持有] {s}: 接近涨停，继续持有")
            continue

        # ---------- 汇总卖出条件 ----------
        reasons = []

        # 5.1 盈利曾超30%，宽松止损
        if max_pp > 0.30:
            if pp <= max_pp - 0.10:
                reasons.append(f"盈利曾超30%，从最高点回撤10% ({pp*100:.2f}%)")
            elif dg < -0.05:
                reasons.append(f"盈利曾超30%，当日跌幅>5% ({dg*100:.2f}%)")

        # 5.2 收益>50% 止盈
        if pp > 0.50:
            reasons.append(f"收益>50% ({pp*100:.2f}%)")

        # 5.3 当日跌幅>2%
        if dg < -0.02:
            reasons.append(f"当日跌幅>2% ({dg*100:.2f}%)")

        # 5.4 当前价跌破开盘价4%
        if cd.day_open and cp < cd.day_open * 0.96:
            reasons.append(f"当前价<开盘价-4% ({cp:.2f}<{cd.day_open*0.96:.2f})")

        # 5.5 普通止损：亏损>7%
        if pp <= -0.07 and not (max_pp > 0.20 and pp <= -0.10):
            reasons.append(f"亏损>7% ({pp*100:.2f}%)")

        # 5.6 跌破5日均线3%
        if ma5 and cp < ma5 * 0.97:
            reasons.append(f"跌破5日均线-3% ({cp:.2f}<{ma5*0.97:.2f})")

        # ---------- 执行卖出 ----------
        if reasons:
            order_target_value(s, 0)
            log.info(f"[卖出] {s}: {'; '.join(reasons)}，清仓")
        else:
            log.info(f"[持有] {s}: 无卖出条件触发")

# ========== 每分钟执行：线性止盈 ==========
def get_minute_sell(context):
    """
    分钟级止盈：9:30-14:56 每分钟执行
    优先级：条件1(涨停不卖) > 条件2(昨收亏/现价赚) > 条件3(今开亏/现价赚) > 线性止盈
    """
    t_day_time = context.current_dt.time()
    if t_day_time < time(9, 30) or t_day_time > time(14, 56):
        return

    y_day = context.previous_date
    t_day = context.current_dt.strftime("%Y%m%d")

    # ---------- 获取非今日买入的持仓 ----------
    info = getattr(g, 'information', {}) or {}
    hold = []
    for s, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        buy_date = info.get(s, {}).get('buy_date')
        if buy_date is None or buy_date == t_day:
            continue
        hold.append(s)

    if not hold:
        return

    c_data = get_current_data()
    for s in hold:
        cd = c_data[s]

        # ---------- 停牌保护 ----------
        if cd.paused:
            log.info(f"[跳过] {s}: 停牌")
            continue

        cp = cd.last_price

        # ---------- 条件1：涨停不卖 ----------
        if cp >= cd.high_limit * 0.99:
            log.info(f"[分钟止盈] {s}: 接近涨停，继续持有")
            continue

        pos = context.portfolio.positions[s]
        buy_price = pos.avg_cost
        cache = g.minute_sell_cache.get(s)

        # ---------- 条件2：昨收亏 -2%，现价赚 >2% ----------
        if cache and cache['date'] == y_day and cache['y_close'] > 0:
            yesterday_loss = (cache['y_close'] - buy_price) / buy_price
            profit_ratio = (cp - buy_price) / buy_price
            if yesterday_loss < -0.02 and profit_ratio > 0.02:
                order_target_value(s, 0)
                log.info(f"[分钟止盈-条件2] {s}: 昨日亏损{yesterday_loss*100:.2f}%, "
                         f"当前盈利{profit_ratio*100:.2f}%>2%, 清仓")
                g.today_high.pop(s, None)
                continue

        # ---------- 条件3：今开亏 -2%，现价赚 >2% ----------
        today_open = cd.day_open
        if today_open > 0:
            open_loss = (today_open - buy_price) / buy_price
            profit_ratio = (cp - buy_price) / buy_price
            if open_loss < -0.02 and profit_ratio > 0.02:
                order_target_value(s, 0)
                log.info(f"[分钟止盈-条件3] {s}: 开盘亏损{open_loss*100:.2f}%, "
                         f"当前盈利{profit_ratio*100:.2f}%>2%, 清仓")
                g.today_high.pop(s, None)
                continue

        # ---------- 线性止盈 ----------
        if not cache or cache['date'] != y_day:
            continue
        if cache['y_day_gain'] >= 0:
            continue

        # 更新当日最高价
        th = g.today_high.get(s, 0)
        if cp > th:
            g.today_high[s] = cp
            th = cp

        # 冲高幅度
        chr = (th - cache['y_close']) / cache['y_close'] if cache['y_close'] > 0 else 0
        if chr > 0.03:
            lt = max(0.005, 0.03 - (chr - 0.01) * 0.5)
            if cp < th * (1 - lt):
                order_target_value(s, 0)
                log.info(f"[线性止盈] {s}: 昨日跌幅{cache['y_day_gain']*100:.2f}%, "
                         f"冲高{chr*100:.2f}%, 回撤{(1-cp/th)*100:.2f}% > {lt*100:.2f}%, 清仓")
                g.today_high.pop(s, None)

# ========== 盘前预计算缓存 ==========
def get_sell_cache(context):
    """09:12 预计算卖出相关缓存：分钟止盈缓存 + 尾盘均线缓存"""
    y_day = context.previous_date
    pos = list(context.portfolio.positions.keys())
    if not pos:
        g.minute_sell_cache = {}
        g.close_sell_cache = {}
        log.info("[缓存] 当前无持仓，卖出缓存已清空")
        return

    # 分钟止盈缓存：昨日收盘、前日收盘、昨日涨跌幅
    df2 = get_price(pos, end_date=y_day, frequency='1d',
                    fields=['close'], count=2, panel=False,
                    skip_paused=False, fill_paused=True)
    for s, sub in df2.groupby('code')['close']:
        if len(sub) >= 2:
            yc, pc = sub.iloc[-1], sub.iloc[-2]
            g.minute_sell_cache[s] = {
                'y_close': yc,
                'prev_close': pc,
                'y_day_gain': (yc - pc) / pc if pc > 0 else 0,
                'date': y_day
            }

    # 尾盘卖出缓存：昨日收盘、5日均价
    df5 = get_price(pos, end_date=y_day, frequency='1d',
                    fields=['close'], count=5, panel=False,
                    skip_paused=False, fill_paused=True)
    g.close_sell_cache = {}
    for s, sub in df5.groupby('code')['close']:
        if len(sub) >= 2:
            g.close_sell_cache[s] = {
                'y_close': sub.iloc[-1],
                'ma5': sub.mean()
            }

    g.today_high.clear()
    log.info(f"[缓存] 尾盘卖出缓存已更新，持仓{len(pos)}只")

# ========== 主板股票列表 ==========
def get_base_stocks(context):
    """每周一09:11 刷新主板股票池：剔除创业板、科创板、北交所、B股等"""
    by_date = context.previous_date - timedelta(days=60)
    all_codes = list(get_all_securities(['stock'], date=by_date).index)
    g.base_stocks = [c for c in all_codes
                     if not c.startswith(('3', '68', '4', '8', '9'))]
    log.info(f"[主板列表刷新]：{len(g.base_stocks)}只")
    return g.base_stocks

# ========== 首板筛选 ==========
def filter_first_board(stock_list, y_day):
    """首板筛选：昨日涨停且前日未涨停，并过滤ST/退市/一字/跌停/市值"""
    if not stock_list:
        return []

    # 取最近2日收盘价与涨停价
    df = get_price(
        stock_list, end_date=y_day, frequency='daily',
        fields=['close', 'high_limit'], count=2,
        panel=False, fill_paused=False, skip_paused=True
    )
    if df.empty:
        log.info("[首板] 历史数据为空")
        return []

    # 标记是否涨停
    df['is_limit'] = df['close'] == df['high_limit']

    times = sorted(df['time'].unique())
    if len(times) < 2:
        log.info("[首板] 交易日不足2天")
        return []

    # 昨日涨停集合 - 前日涨停集合 = 首板候选
    grp = df[df['is_limit']].groupby('time')['code'].agg(set)
    candidates = list(grp.get(times[-1], set())
                      - grp.get(times[-2], set()))
    log.info(f"[首板] 昨日涨停且前日未涨停: {len(candidates)}只，列表={candidates}")
    if not candidates:
        return []

    # 实时数据过滤：停牌、ST、退市、一字板、跌停开盘
    cd = get_current_data()
    after_st = []
    for c in candidates:
        reason = None
        if cd[c].paused:
            reason = "停牌"
        elif cd[c].is_st:
            reason = "ST"
        elif 'ST' in cd[c].name:
            reason = "名称含ST"
        elif '*' in cd[c].name:
            reason = "名称含*"
        elif '退' in cd[c].name:
            reason = "退市整理"
        elif cd[c].day_open == cd[c].high_limit:
            reason = "涨停开盘(一字板)"
        elif cd[c].day_open == cd[c].low_limit:
            reason = "跌停开盘"
        if reason:
            log.info(f"[首板-淘汰] {c} 原因={reason}")
        else:
            after_st.append(c)

    log.info(f"[首板] ST/退市 过滤后: {len(after_st)}只")
    if not after_st:
        return []

    # 市值过滤：流通市值 30~300 亿
    q = query(valuation.code).filter(
        valuation.code.in_(after_st),
        valuation.circulating_market_cap.between(30, 300)
    )
    result = get_fundamentals(q)['code'].tolist()

    # 记录被市值淘汰的
    passed_set = set(result)
    for c in after_st:
        if c not in passed_set:
            log.info(f"[首板-淘汰] {c} 原因=市值不在30~300亿")

    log.info(f"[首板] 市值过滤后: {len(result)}只")
    return result

# ========== 收盘后清理 ==========
def after_trading_end(context):
    """收盘后清理：移除已清仓股票的缓存与信息，清空当日最高价"""
    g.sold_stocks.clear()
    cur = set(context.portfolio.positions.keys())
    g.information = {k: v for k, v in g.information.items() if k in cur}
    g.minute_sell_cache = {k: v for k, v in g.minute_sell_cache.items() if k in cur}
    g.close_sell_cache = {k: v for k, v in g.close_sell_cache.items() if k in cur}
    g.today_high.clear()
    log.info("[收盘清理] 完成，当前持仓=%d只", len(cur))