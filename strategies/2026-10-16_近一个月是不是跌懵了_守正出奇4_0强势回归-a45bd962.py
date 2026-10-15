# Clone from JoinQuant
# postId: a45bd9625db10f299b789c910a870089
# backtestId: 206218beed6ac7984c3d2e62a03f28a8
# title: 近一个月是不是跌懵了？守正出奇4.0强势回归！

# ============================================================
# 守正出奇 4.0 — 最终版
# 修复日志:
#   2026-06-21 v2.0:
#     [FIX-1] 成交量过滤方向: > avg×2.0 → < avg×0.30
#     [FIX-2] 剔除5只低流动ETF: 159980/159985/513290/513730/511220
#     [FIX-3] 14个回调加 try/except
#     [FIX-4] 滑点校准: fund 0.03% / stock 0.05%
#   2026-06-22 v3.0:
#     [FIX-5] 买卖死锁: sell+buy 合并为 qixing_trade, 去除 to_sell 守卫
#     [FIX-7] 防御ETF 511880不稳定: 无标的时持现金
#     [FIX-10] 日志全英文
#   2026-06-23 v4.0:
#     [FIX-6] T+1资金结算: 买入时按 transferable_cash 控制实际预算
#     [FIX-8] 日NAV持久化: after_close 写入 nav_log.csv
#     [FIX-9] 缓存key稳健: str(date) 替代 date() 对象
# ============================================================
"""
守正出奇4.0 — 实盘最终版
[FIX-6] T+1结算: 买入量按实际可用现金封顶, 不超 transferable_cash
[FIX-8] NAV持久化: 每日收盘写入 nav_log.csv (date,p0_val,p1_val,total)
[FIX-9] 缓存稳健: rankings_cache key 用 str(date) 而非 date 对象

资金配比：白马50% | 七星ETF轮动50%
"""
from jqdata import *
import numpy as np
import pandas as pd
import datetime, math

def initialize(context):
    """守正出奇4.0 初始化"""
    try:
        set_benchmark('000300.XSHG')
        set_option('use_real_price', True)
        set_option('avoid_future_data', True)
        log.set_level('order', 'error')

        init_cash = context.portfolio.starting_cash
        set_subportfolios([
            SubPortfolioConfig(cash=init_cash * 0.50, type='stock'),
            SubPortfolioConfig(cash=init_cash * 0.50, type='stock'),
        ])

        set_order_cost(OrderCost(close_tax=0, close_commission=0.0001, open_commission=0.0001, min_commission=5), type='fund')
        set_order_cost(OrderCost(close_tax=0.001, open_commission=0.00012, close_commission=0.00012, min_commission=5), type='stock')
        set_slippage(PriceRelatedSlippage(0.0003), type="fund")
        set_slippage(PriceRelatedSlippage(0.0005), type="stock")

        # === 白马参数 ===
        g.baima = {
            'pool_depth': 50, 'max_hold': 6,
            'mom_days': 25, 'min_r_sq': 0.4,
            'score_pct_low': 0.70, 'score_pct_high': 0.95,
        }

        # === 七星参数 ===
        g.etf_pool = [
            '518880.XSHG', '501018.XSHG', '161226.XSHE',
            '513100.XSHG', '159509.XSHE', '513500.XSHG', '513520.XSHG',
            '513030.XSHG', '513080.XSHG', '513310.XSHG',
            '513130.XSHG', '513050.XSHG', '159920.XSHE', '513690.XSHG',
            '510300.XSHG', '510500.XSHG', '510050.XSHG', '159915.XSHE', '588080.XSHG',
            '512100.XSHG', '563300.XSHG',
            '512890.XSHG', '159967.XSHE',
            '511380.XSHG', '511010.XSHG',
        ]

        g.lookback_days = 25
        g.holdings_num = 1
        g.min_money = 5000
        g.loss = 0.97
        g.score_min = 0
        g.score_max = 100.0
        # [FIX-9] cache key 用 str(date)
        g.rankings_cache = {'date_str': '', 'data': None}

        # 盈利保护
        g.enable_profit_protection = True
        g.profit_protection_lookback = 1
        g.profit_protection_threshold = 0.05
        g.profit_protection_check_times = ['11:00']

        # 成交量过滤
        g.enable_volume_check = True
        g.volume_lookback = 5
        g.volume_threshold = 0.30

        # 短动量
        g.use_short_momentum = True
        g.short_lookback = 10
        g.short_threshold = 0.0

        # 溢价过滤
        g.enable_premium = True
        g.premium_threshold = 0.20

        # 双滤波器
        g.current_filter = 'normal'
        g.risk_benchmark = '510300.XSHG'
        g.laplace_s = 0.05
        g.laplace_min_slope = 0.001
        g.gaussian_sigma = 1.2
        g.gaussian_min_slope = 0.002

        # 震荡期检测
        g.bias_threshold = 0.10
        g.rsi_overbought = 75
        g.rsi_pullback = 60
        g.low_rise_threshold = 0.03
        g.max_range_days = 15
        g.cooldown = 2
        g.last_switch = None
        g.range_start = None
        g.range_days = 0
        g.stable_days = 0
        g.prev_dd = None
        g.prev_rsi = None

        # [FIX-8] NAV持久化: 写入标头
        try:
            write_file('nav_log.csv', 'date,p0_val,p1_val,total\n', append=False)
        except:
            pass

        # 注册回调
        run_monthly(baima_before_open, 1, time='09:40')
        run_monthly(baima_trade, 1, time='09:45')
        run_daily(qixing_check_positions, '09:10')
        run_daily(qixing_check_range, '13:05')
        run_daily(qixing_trade, '13:10')
        for t in ['11:00']:
            run_daily(qixing_protect_check, time=t)
        run_daily(qixing_reset, '15:10')
        run_daily(after_close, 'after_close')

        log.info("[4.0] init ok")
    except Exception as e:
        log.error(f"[4.0] init error: {e}")

# ==================== 白马模块 (pindex=0) ====================

def baima_before_open(context):
    try:
        sp = context.subportfolios[0]
        ma100 = np.mean(attribute_history('000300.XSHG', 100, '1d', ['close'], df=False)['close'])
        ma200 = np.mean(attribute_history('000300.XSHG', 200, '1d', ['close'], df=False)['close'])
        hot_th = 0.50 if ma100 > ma200 else 0.90
        idx = attribute_history('000300.XSHG', 220, '1d', ['close'], df=False)['close']
        mh = (np.mean(idx[-5:]) - idx.min()) / (idx.max() - idx.min())
        if mh < 0.20: temp = 'cold'
        elif mh > hot_th: temp = 'hot'
        else: temp = 'warm'
        g.baima_temp = temp
        g.baima_hold_count = 6 if ma100 > ma200 else 4

        all_s = get_index_stocks("000300.XSHG", date=context.previous_date)
        cd = get_current_data()
        all_s = [s for s in all_s if not(
            cd[s].paused or cd[s].is_st or 'ST' in cd[s].name or '*' in cd[s].name or '\u9000' in cd[s].name
            or s.startswith('68') or s.startswith('8') or s.startswith('4'))]

        q = query(valuation.code, valuation.pb_ratio, indicator.roa, indicator.inc_return,
                  indicator.inc_net_profit_year_on_year, cash_flow.subtotal_operate_cash_inflow,
                  indicator.adjusted_profit).filter(valuation.code.in_(all_s))
        df = get_fundamentals(q).set_index('code')
        df = df[(df['pb_ratio'] > 0) & (df['adjusted_profit'] > 0)].copy()
        df['cash_flow_profit_ratio'] = df['subtotal_operate_cash_inflow'] / df['adjusted_profit']
        df['roa_pb_ratio'] = df['roa'] / df['pb_ratio']
        df.dropna(inplace=True)
        if df.empty: g.baima_list = []; return

        if temp == 'cold':
            pq, cq, gq = df['pb_ratio'].quantile(0.30), df['cash_flow_profit_ratio'].quantile(0.70), df['inc_net_profit_year_on_year'].quantile(0.10)
            res = df[(df['pb_ratio'] < pq) & (df['cash_flow_profit_ratio'] > cq) & (df['inc_net_profit_year_on_year'] > gq)]
            sd = res.sort_values('roa_pb_ratio', ascending=False)
        elif temp == 'warm':
            pq, cq, gq = df['pb_ratio'].quantile(0.40), df['cash_flow_profit_ratio'].quantile(0.50), df['inc_net_profit_year_on_year'].quantile(0.50)
            res = df[(df['pb_ratio'] < pq) & (df['cash_flow_profit_ratio'] > cq) & (df['inc_net_profit_year_on_year'] > gq)]
            sd = res.sort_values('roa_pb_ratio', ascending=False)
        else:
            pq, gq, iq = df['pb_ratio'].quantile(0.60), df['inc_net_profit_year_on_year'].quantile(0.80), df['inc_return'].quantile(0.70)
            res = df[(df['pb_ratio'] > pq) & (df['inc_net_profit_year_on_year'] > gq) & (df['inc_return'] > iq)]
            sd = res.sort_values('roa', ascending=False)

        if sd.empty: g.baima_list = []; return
        check = list(sd.head(g.baima['pool_depth']).index)
        final = baima_momentum(check, g.baima['mom_days'],
                               g.baima['score_pct_low'], g.baima['score_pct_high'], g.baima['min_r_sq'])
        g.baima_list = [x for x in check if x in final]
    except Exception as e:
        log.error(f"[4.0] baima_before_open error: {e}")

def baima_momentum(pool, days=25, pl=0.70, ph=0.95, mr=0.4):
    try:
        if not pool: return []
        dc = history(days, '1d', 'close', pool, df=True)
        vr = 1 - dc.isna().sum() / len(dc)
        dc = dc.loc[:, vr >= 0.80].dropna(axis=1)
        if dc.empty: return []
        y = np.log(dc.values); n = y.shape[0]; x = np.arange(n)
        w = np.linspace(1, 2, n) ** 2
        sw, sxw, sx2w = np.sum(w), np.sum(x * w), np.sum(x * x * w)
        det = sw * sx2w - sxw * sxw
        syw = np.sum(y * w[:, np.newaxis], axis=0)
        sxyw = np.sum(y * (x * w)[:, np.newaxis], axis=0)
        slope = (sw * sxyw - sxw * syw) / det
        inter = (sx2w * syw - sxw * sxyw) / det
        ar = np.power(np.exp(slope), 250) - 1
        yp = np.outer(x, slope) + inter
        ym = np.sum(y * w[:, np.newaxis], axis=0) / sw
        sse = np.sum(w[:, np.newaxis] * (y - yp)**2, axis=0)
        sst = np.sum(w[:, np.newaxis] * (y - ym)**2, axis=0)
        rsq = np.where(sst > 1e-10, 1 - sse / sst, 0)
        score = ar * rsq
        res = pd.DataFrame({'score': score, 'r': rsq}, index=dc.columns)
        res = res[res['r'] > mr]
        if len(res) < 5: return list(res.index)
        lo, hi = res['score'].quantile(1 - pl), res['score'].quantile(ph)
        return list(res[(res['score'] >= lo) & (res['score'] <= hi)].sort_values('score', ascending=False).index)
    except Exception as e:
        log.error(f"[4.0] baima_momentum error: {e}")
        return []

def baima_trade(context):
    try:
        buys = getattr(g, 'baima_list', [])
        for s in list(context.subportfolios[0].positions.keys()):
            if s not in buys:
                order_target(s, 0, pindex=0)
        n = g.baima_hold_count
        cur = len([p for p in context.subportfolios[0].positions.values() if p.total_amount > 0])
        if cur < n and buys:
            v = context.subportfolios[0].cash / (n - cur)
            for s in buys[:n]:
                if s not in context.subportfolios[0].positions:
                    order_target_value(s, v, pindex=0)
                    if len([p for p in context.subportfolios[0].positions.values() if p.total_amount > 0]) >= n: break
    except Exception as e:
        log.error(f"[4.0] baima_trade error: {e}")

# ==================== 七星ETF轮动模块 (pindex=1) ====================

def qixing_check_positions(context):
    try:
        for s in context.subportfolios[1].positions:
            p = context.subportfolios[1].positions[s]
            if p.total_amount > 0:
                log.info(f"[4.0] hold {s} {p.total_amount}sh avg_cost{p.avg_cost:.3f}")
    except Exception as e:
        log.error(f"[4.0] check_positions error: {e}")

def qixing_protect_check(context):
    try:
        if not g.enable_profit_protection: return
        for s in list(context.subportfolios[1].positions.keys()):
            if s not in g.etf_pool: continue
            p = context.subportfolios[1].positions[s]
            if p.total_amount <= 0: continue
            hist = attribute_history(s, g.profit_protection_lookback, '1d', ['high'])
            if hist.empty: continue
            mh = hist['high'].max()
            cp = get_current_data()[s].last_price
            if cp <= mh * (1 - g.profit_protection_threshold):
                order_target(s, 0, pindex=1)
                log.info(f"[4.0] profit_protect sell {s}")
    except Exception as e:
        log.error(f"[4.0] profit_protect error: {e}")

# [FIX-9] 缓存key用 str(date)
def qixing_get_rankings(context):
    try:
        today_str = str(context.current_dt.date())
        if g.rankings_cache['date_str'] == today_str:
            return g.rankings_cache['data']
        results = []
        for etf in g.etf_pool:
            cd = get_current_data()
            if cd[etf].paused: continue
            m = qixing_calc_metrics(context, etf)
            if m and g.score_min < m['score'] < g.score_max:
                results.append(m)
        results.sort(key=lambda x: x['score'], reverse=True)
        g.rankings_cache = {'date_str': today_str, 'data': results}
        return results
    except Exception as e:
        log.error(f"[4.0] get_rankings error: {e}")
        return []

def qixing_calc_metrics(context, etf):
    try:
        lb = max(g.lookback_days, g.short_lookback) + 20
        prices = attribute_history(etf, lb, '1d', ['close'])
        if len(prices) < g.lookback_days: return None
        cp = get_current_data()[etf].last_price
        ps = np.append(prices['close'].values, cp)
        name = get_security_info(etf).display_name

        if g.enable_profit_protection:
            hist = attribute_history(etf, g.profit_protection_lookback, '1d', ['high'])
            if not hist.empty:
                mh = hist['high'].max()
                if cp <= mh * (1 - g.profit_protection_threshold):
                    return None

        # volume check: filter shrinkage
        if g.enable_volume_check:
            hist_v = attribute_history(etf, g.volume_lookback + 1, '1d', ['volume'])
            if len(hist_v) >= g.volume_lookback:
                avg = hist_v['volume'].iloc[:g.volume_lookback].mean()
                prev_vol = hist_v['volume'].iloc[-1]
                if avg > 0 and prev_vol < avg * g.volume_threshold:
                    return None

        # short momentum
        if g.use_short_momentum and len(ps) >= g.short_lookback + 1:
            sr = ps[-1] / ps[-(g.short_lookback + 1)] - 1
            if sr < g.short_threshold: return None

        # long-term momentum
        recent = ps[-(g.lookback_days + 1):]
        y = np.log(recent); x = np.arange(len(y))
        w = np.linspace(1, 2, len(y))
        slope, inter = np.polyfit(x, y, 1, w=w)
        ar = math.exp(slope * 250) - 1
        ssr = np.sum(w * (y - (slope * x + inter))**2)
        sst = np.sum(w * (y - np.mean(y))**2)
        r2 = 1 - ssr / sst if sst != 0 else 0
        score = ar * r2

        # single-day loss gate
        if len(ps) >= 4:
            if min(ps[-1]/ps[-2], ps[-2]/ps[-3], ps[-3]/ps[-4]) < g.loss:
                return None

        # dual filters
        if len(ps) >= 10:
            L = np.zeros(len(ps))
            L[0] = ps[0]
            a = 1 - np.exp(-g.laplace_s)
            for t in range(1, len(ps)):
                L[t] = a * ps[t] + (1 - a) * L[t-1]
            lp_slope = L[-1] - L[-2] if len(L) >= 2 else 0
            passed_lp = cp > L[-1] and lp_slope > g.laplace_min_slope

            n2 = len(ps)
            i1 = np.arange(n2)
            w1 = np.exp(-((i1 + 1)**2) / (2 * g.gaussian_sigma**2))[::-1]
            w1 /= np.sum(w1)
            g1 = np.sum(ps * w1)
            ps2 = ps[:-1]; n2_2 = len(ps2)
            i2 = np.arange(n2_2)
            w2 = np.exp(-((i2 + 1)**2) / (2 * g.gaussian_sigma**2))[::-1]
            w2 /= np.sum(w2)
            g2 = np.sum(ps2 * w2)
            gs = g1 - g2
            passed_gs = cp > g1 and gs > g.gaussian_min_slope

            if g.current_filter == 'normal':
                if not passed_lp: return None
            else:
                if not passed_gs: return None

        return {'etf': etf, 'name': name, 'score': score, 'ar': ar, 'r2': r2, 'price': cp}
    except Exception as e:
        log.error(f"[4.0] calc_metrics error {etf}: {e}")
        return None

def qixing_calc_rsi(close, period=14):
    if len(close) < period + 1: return None
    d = np.diff(close)
    ag = np.mean(np.where(d > 0, d, 0)[-period:])
    al = np.mean(np.where(d < 0, -d, 0)[-period:])
    if al == 0: return 100
    return 100 - 100 / (1 + ag / al)

def qixing_check_range(context):
    try:
        if not hasattr(g, 'current_filter'): return
        bm = g.risk_benchmark
        end_d = getattr(context, 'previous_date', None)
        if end_d is None: return
        df = get_price(bm, end_date=end_d, count=50, frequency='daily', fields=['close', 'high', 'low'])
        if df is None or len(df) < 20: return
        close = df['close'].values; high = df['high'].values; low = df['low'].values
        cp = close[-1]
        try:
            cd = get_current_data()
            lp = cd[bm].last_price
            if lp and lp > 0:
                cp = float(lp)
        except: pass
        rh = np.max(high[-20:]); rl = np.min(low[-20:])
        ma = np.mean(close[-20:])
        bias = (cp - ma) / ma if ma > 0 else 0
        rsi = qixing_calc_rsi(close, 14)
        prsi = qixing_calc_rsi(close[:-1], 14) if len(close) > 15 else None
        dd = (rh - cp) / rh if rh > 0 else 0

        if g.current_filter == 'oscillating':
            rise = (cp - rl) / rl if rl > 0 else 0
            exited = False
            if rise >= g.low_rise_threshold: exited = True
            if dd < 0.03:
                g.stable_days += 1
            else:
                g.stable_days = 0
            if g.stable_days >= 2: exited = True
            if g.range_start:
                td = get_trade_days(start_date=g.range_start, end_date=context.current_dt.date())
                if len(td) - 1 >= g.max_range_days: exited = True
            if exited:
                can = True
                if g.last_switch:
                    td2 = get_trade_days(start_date=g.last_switch, end_date=context.current_dt.date())
                    if len(td2) - 1 < g.cooldown: can = False
                if can:
                    g.current_filter = 'normal'
                    g.range_start = None; g.stable_days = 0
                    g.rankings_cache = {'date_str': '', 'data': None}
                    log.info("[4.0] exit oscillating -> normal")
                    return

        if g.current_filter == 'normal':
            enter = False
            if bias > g.bias_threshold:
                enter = True
            if rsi is not None and prsi is not None and prsi > g.rsi_overbought and rsi < g.rsi_pullback:
                enter = True
            if enter:
                if g.last_switch:
                    td3 = get_trade_days(start_date=g.last_switch, end_date=context.current_dt.date())
                    if len(td3) - 1 < g.cooldown: enter = False
                if enter:
                    g.current_filter = 'oscillating'
                    g.range_start = context.current_dt.date()
                    g.stable_days = 0
                    g.rankings_cache = {'date_str': '', 'data': None}
                    log.info("[4.0] enter oscillating -> gaussian filter")
    except Exception as e:
        log.error(f"[4.0] check_range error: {e}")

# ==================== 七星交易 ====================

def qixing_trade(context):
    """
    [FIX-5] sell+buy 合并, 无 to_sell 守卫
    [FIX-6] T+1结算: 买入量按 transferable_cash 封顶, 不超可用现金
    [FIX-7] 无标的时持现金
    """
    try:
        ranked = qixing_get_rankings(context)
        if not ranked:
            log.info("[4.0] no ranking targets, hold cash")
            for s in list(context.subportfolios[1].positions.keys()):
                if s in g.etf_pool:
                    order_target(s, 0, pindex=1)
            return

        # build target set
        targets = []
        for m in ranked[:g.holdings_num]:
            if m['score'] >= g.score_min:
                targets.append(m['etf'])
                log.info(f"[4.0] target #{len(targets)}: {m['etf']} {m['name']} score={m['score']:.4f}")

        if not targets:
            log.info("[4.0] no qualifying targets, hold cash")
            for s in list(context.subportfolios[1].positions.keys()):
                if s in g.etf_pool:
                    order_target(s, 0, pindex=1)
            return

        target_set = set(targets)

        # --- STEP 1: sell non-targets ---
        for s in list(context.subportfolios[1].positions.keys()):
            if s in g.etf_pool and s not in target_set:
                order_target(s, 0, pindex=1)
                log.info(f"[4.0] sell {s}")

        # --- STEP 2: buy targets ---
        # [FIX-6] 用 transferable_cash 控制实际预算
        #   - 对于新标的(持仓为0): 投入 min(per_target, 可用现金/新标个数)
        #   - 对于已有标的: 用 order_target_value 维持目标仓位(不额外消耗现金)
        tv = context.subportfolios[1].total_value
        per = tv / len(targets)
        # [FIX-6] 获取实际可用现金(T+1结算后)
        avail_cash = context.subportfolios[1].transferable_cash
        new_targets = [etf for etf in targets
                       if etf not in context.subportfolios[1].positions
                       or context.subportfolios[1].positions[etf].total_amount <= 0]
        cash_per_new = avail_cash / len(new_targets) if new_targets else 0

        for etf in targets:
            cv = 0
            if etf in context.subportfolios[1].positions:
                p = context.subportfolios[1].positions[etf]
                if p.total_amount > 0:
                    cv = p.total_amount * p.price

            if cv == 0:
                # [FIX-6] 新标的: 投入不超过可用现金
                target_val = cash_per_new
                if target_val > 0:
                    order_target_value(etf, target_val, pindex=1)
                    log.info(f"[4.0] buy {etf} target_value={target_val:.0f} (avail={avail_cash:.0f})")
            elif abs(cv - per) > per * 0.05:
                # 已有持仓微调: 用 order_target_value 维持
                order_target_value(etf, per, pindex=1)
                log.info(f"[4.0] rebalance {etf} target_value={per:.0f}")
    except Exception as e:
        log.error(f"[4.0] trade error: {e}")

def qixing_reset(context):
    try:
        g.rankings_cache = {'date_str': '', 'data': None}
    except Exception as e:
        log.error(f"[4.0] reset error: {e}")

def after_close(context):
    try:
        p0_val = context.subportfolios[0].total_value
        p1_val = context.subportfolios[1].total_value
        total = p0_val + p1_val
        date_str = str(context.current_dt.date())
        log.info(f"[4.0] p0={p0_val:.0f} p1={p1_val:.0f} total={total:.0f}")
        # [FIX-8] NAV持久化到 nav_log.csv
        try:
            line = f"{date_str},{p0_val:.2f},{p1_val:.2f},{total:.2f}\n"
            write_file('nav_log.csv', line, append=True)
        except:
            pass
    except Exception as e:
        log.error(f"[4.0] after_close error: {e}")
