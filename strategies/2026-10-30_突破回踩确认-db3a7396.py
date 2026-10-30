# Clone from JoinQuant
# postId: db3a73967dc6325bccfaae4eff54cf2c
# backtestId: 51595abfabd264396352178dfa7f6c8f
# title: 突破回踩确认

# 策略：突破回踩确认
# ==== 核心逻辑 ====
# 买入：放量突破20日高点 → 缩量回踩不破支撑 → 企稳买入
# 卖出：跌破支撑位 / +10%后移动止盈

from jqdata import *
import numpy as np
import pandas as pd
from datetime import time

def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.002))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.00025,
                             close_commission=0.00025, min_commission=5), type='stock')
    set_benchmark('000852.XSHG')

    g.max_hold = 3
    g.cache_date = None

    # 持仓期间记录
    g.entry_price = {}     # {code: 买入价}
    g.peak_price = {}      # {code: 持仓期间最高价}
    g.support = {}         # {code: 支撑位(突破日收盘价)}
    g.buy_date = {}        # {code: 买入日期} 用于跳过买入当天的止损

    run_daily(before_market_open, time='09:00')
    run_daily(check_buy, time='09:35')
    run_daily(check_stop, time='11:25')
    run_daily(check_stop, time='13:30')
    run_daily(check_stop, time='14:50')


def before_market_open(context):
    """
    盘前计算：找出放量突破20日高点后、正在缩量回踩中的股票
    """
    today = context.current_dt.date()
    if g.cache_date == today:
        return
    g.cache_date = today

    y_day = context.previous_date
    end_str = y_day.strftime('%Y-%m-%d') + ' 15:00:00'

    # ====== 大盘环境过滤：中证2000在MA30上方 ======
    try:
        idx_df = get_price('932000.CSI', end_date=end_str, frequency='1d',
                           fields=['close'], count=40, skip_paused=True)
        if idx_df is not None and len(idx_df) >= 20:
            idx_close = idx_df['close'].values
            ma30 = np.mean(idx_close[-30:])
            if idx_close[-1] < ma30:
                log.warn(f'[大盘] 中证2000在MA30下方，今日不开仓')
                g.candidates = []
                return
    except:
        pass

    # 基础池：中证2000，剔除ST
    base = [s for s in get_index_stocks('932000.CSI') if not s.startswith('688')]
    clean = []
    for s in base:
        info = get_security_info(s)
        if info and 'ST' not in info.display_name and '退' not in info.display_name:
            clean.append(s)

    # 获取60日数据：用于计算20日高点、均量、支撑位
    df = get_price(clean, end_date=end_str, frequency='1d',
                   fields=['close', 'volume', 'high', 'low'], count=60,
                   panel=False, skip_paused=True)

    if df is None or df.empty:
        g.candidates = []
        return

    g.candidates = []
    for code, grp in df.groupby('code'):
        grp = grp.sort_values('time')
        closes = grp['close'].values
        highs = grp['high'].values
        lows = grp['low'].values
        vols = grp['volume'].values

        if len(closes) < 30:
            continue

        # ===== 条件1：近5日内出现过放量突破20日高点 =====
        high_20d = np.max(highs[-25:-5])  # 突破前的20日高点（不含近5日）
        vol_ma20 = np.mean(vols[-25:-5])  # 突破前的20日均量

        breakout_day = -1
        breakout_close = 0
        for i in range(-5, 0):
            if highs[i] >= high_20d * 1.01 and vols[i] >= vol_ma20 * 1.5 and closes[i] > closes[i-1]:
                breakout_day = i
                breakout_close = closes[i]
                break

        if breakout_day == -1:
            continue

        # ===== 条件2：突破后正在回踩，回踩不破支撑 =====
        support_level = max(breakout_close, np.mean(closes[breakout_day:]))  # 支撑位=突破日收盘价
        current_close = closes[-1]

        # 回踩幅度 < 6%（跌幅太大可能破位）
        pullback_pct = (max(highs[breakout_day:]) - current_close) / max(highs[breakout_day:])
        if pullback_pct > 0.06:
            continue

        # 回踩量萎缩（最近3日均量 <= 20日均量）
        vol_recent = np.mean(vols[-3:])
        if vol_recent > vol_ma20 * 1.2:
            continue

        # 当前价在支撑位上方（未破位）
        if current_close < support_level * 0.98:
            continue

        # 获取行业分类（API返回格式：{code: {sw_l1: {industry_name: ...}}})
        industry = '未知'
        try:
            ind_info = get_industry(code)
            if ind_info and code in ind_info:
                for key in ['sw_l1', 'jq_l1', 'zjw']:
                    if key in ind_info[code] and ind_info[code][key].get('industry_name'):
                        industry = ind_info[code][key]['industry_name']
                        break
        except:
            pass
        # 通过所有条件
        g.candidates.append({
            'code': code,
            'support': support_level,
            'high_20d': high_20d,
            'pullback': pullback_pct,
            'breakout_vol_ratio': vols[breakout_day] / vol_ma20,
            'prev_close': closes[-1],
            'prev_volume': vols[-1],
            'industry': industry,
        })

    log.info(f'[盘前] 突破回踩候选: {len(g.candidates)} 只')
    for c in g.candidates[:10]:
        log.info(f'  {get_security_info(c["code"]).display_name}({c["code"]}): '
                 f'支撑{c["support"]:.2f} 回撤{c["pullback"]*100:.1f}%')

    # ====== 板块效应统计（同板块候选≥3说明资金集中流入） ======
    ind_count = {}
    for c in g.candidates:
        ind = c['industry']
        ind_count[ind] = ind_count.get(ind, 0) + 1
    active = {ind: cnt for ind, cnt in ind_count.items() if cnt >= 2}
    g.active_industries = active
    if active:
        log.info(f'[板块] 活跃板块: {", ".join([f"{ind}({cnt}只)" for ind, cnt in sorted(active.items(), key=lambda x:-x[1])])}')
    else:
        log.info(f'[板块] 无活跃板块（各板块候选均<2只）')


def check_buy(context):
    """
    09:35执行：确认今日开盘后企稳→买入
    """
    if not g.candidates:
        return

    holdings = [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]
    if len(holdings) >= g.max_hold:
        return

    slots = g.max_hold - len(holdings)
    today_str = context.current_dt.strftime('%Y-%m-%d')

    # 获取1分钟线确认企稳
    codes = [c['code'] for c in g.candidates if c['code'] not in holdings]
    m1 = get_price(codes, start_date=today_str, end_date=context.current_dt,
                   frequency='1m', fields=['close'], skip_paused=True, panel=False)

    if m1 is None or m1.empty:
        return

    qualified = []
    t_date = context.current_dt.date()
    for c in g.candidates:
        code = c['code']
        if code in holdings:
            continue
        support = c['support']

        sub = m1[m1['code'] == code].sort_values('time')
        closes = sub['close'].values
        if len(closes) < 3:
            continue

        # 条件A：当前价 > 支撑位（未破位）
        if closes[-1] < support:
            continue

        # 条件B：1分钟斜率 > 0（开盘后企稳）
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]
        if slope <= 0:
            continue

        # 条件C：最新价不低于开盘价（今日没跌）
        if closes[-1] < closes[0] * 0.995:
            continue

        # 条件D：今日上涨（当前价 > 昨收，确认回踩结束）
        prev_close = c['prev_close']
        if prev_close > 0 and closes[-1] <= prev_close * 1.001:
            continue

        # 条件E：集合竞价确认（竞价量/昨量 > 0.05%）
        prev_volume = c.get('prev_volume', 0)
        try:
            auction = get_call_auction(code,
                start_date=today_str + ' 09:15:00',
                end_date=today_str + ' 09:25:00',
                fields=['volume', 'current'])
            if auction is not None and not auction.empty:
                al = auction.iloc[-1]
                vol_ratio = al.volume / prev_volume if prev_volume > 0 else 0
                if vol_ratio <= 0.0005:  # 竞价量太低 = 无人关注
                    continue
        except:
            pass

        # 条件F：跳过涨停板
        try:
            cd = get_current_data()[code]
            if cd is not None and cd.last_price >= cd.high_limit * 0.99:
                name = get_security_info(code).display_name
                log.info(f'  [跳过涨停] {name}({code}): 接近涨停，不追')
                continue
        except:
            pass

        qualified.append(code)

    if not qualified:
        log.info('[买入] 无企稳确认标的')
        return

    # 按板块强度+回踩幅度排序
    # 优先选活跃板块（同板块候选≥3只）的股票，同板块内再按回踩幅度
    def sort_key(code):
        c = next(c for c in g.candidates if c['code'] == code)
        ind_strength = g.active_industries.get(c['industry'], 0)  # 板块候选数
        return (-ind_strength, c['pullback'])  # 板块越强越优先，同板块回踩越小越优先
    qualified.sort(key=sort_key)
    to_buy = qualified[:slots]

    total = context.portfolio.total_value
    # 98%资金利用率：1只时重仓，多只时分散
    per_stock = min(
        context.portfolio.available_cash / len(to_buy),
        total * 0.98 / len(to_buy),
        total * 0.6   # 单只上限60%，防止过度集中
    )
    t_date = context.current_dt.date()

    for code in to_buy:
        info = next(c for c in g.candidates if c['code'] == code)
        name = get_security_info(code).display_name
        log.info(f'[买入] {name}({code}): 支撑{info["support"]:.2f} 回踩{info["pullback"]*100:.1f}% 金额{per_stock:.0f}')
        order_value(code, per_stock)
        g.entry_price[code] = per_stock / (per_stock / get_current_data()[code].last_price)
        g.peak_price[code] = None
        g.buy_date[code] = t_date


def check_stop(context):
    """
    止损止盈：
    1. +10%后移动止盈（回落3%即卖）
    2. -7%固定止损（给股价足够波动空间，避免频繁小亏）
    """
    positions = context.portfolio.positions
    if not positions:
        return

    t_date = context.current_dt.date()
    c_data = get_current_data()
    for code in list(positions.keys()):
        pos = positions[code]
        if pos.total_amount <= 0:
            continue

        # 买入当天不触发止损
        if g.buy_date.get(code) == t_date:
            continue

        cp = c_data[code].last_price
        if cp is None or cp <= 0:
            continue

        cost = pos.avg_cost
        pnl = (cp - cost) / cost

        # 更新最高价
        if g.peak_price.get(code) is None or cp > g.peak_price[code]:
            g.peak_price[code] = cp

        peak = g.peak_price[code]

        # ===== 条件1：+10%后移动止盈 =====
        if peak >= cost * 1.10:
            drawdown = (peak - cp) / peak
            if drawdown > 0.03:
                log.info(f'[止盈] {code}: 最高{peak:.2f}回落{drawdown*100:.1f}%>3%, 盈利{pnl*100:.1f}%')
                order_target_value(code, 0)
                clean_up(code)
                continue
            else:
                continue  # 移动止盈模式

        # ===== 条件2：-7%固定止损（唯一止损，给股价足够波动空间） =====
        if pnl < -0.07:
            log.info(f'[止损-7%] {code}: 亏损{pnl*100:.1f}%<=-7%')
            order_target_value(code, 0)
            clean_up(code)
            continue


def clean_up(code):
    g.entry_price.pop(code, None)
    g.peak_price.pop(code, None)
    g.support.pop(code, None)
    g.buy_date.pop(code, None)