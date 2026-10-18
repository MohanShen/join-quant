# Clone from JoinQuant
# postId: 5f2f36a917c700fa7f8c7954a46761e0
# backtestId: 6e1d667b302e844112e901aa7b070a7a
# title: 趋势捕捉加点低关联的ETF，烧token搞的换点分回测

# -*- coding: utf-8 -*-
"""
Trend Leader Holding + ETF Momentum Rotation
============================================
Sleeve A (~70%): 趋势龙头持仓
    选股 (周一 09:25):
        - 中证全指成分, 排除 ST/科创/创业/北交/次新(<375天)
        - 价格 > MA20 > MA60 (中长期多头)
        - 收盘价 = 近20日新高 或 接近 (>= 20日高 * 0.985)
        - 60日动量分位排名前 60
        - 量价: 近20日均额 >= 1亿, 近5日均额/前20日均额 >= 1.1 (温和放量)
        - 基本面: ROE > 8, 市值 50~500亿
        - 行业去重: 同 SW1 仅取动量最高 1 只
        - 综合得分 = 60d动量(0.5) + 20d动量(0.3) + R²(0.2)
    持仓:
        - 持 4 只, 等权
    卖出 (日频 14:50):
        - 跌破 MA20 * 0.97
        - 持仓收益 <= -8% 止损
        - 当日跌幅 <= -7%
        - 持仓收益 >= +30% 触发分钟级 5% 追踪止盈 (next bar 实现)
    周一 09:30 调仓: 卖出不在新名单且非昨涨停的, 补足至 4 只

Sleeve B (~30%): ETF 低相关动量轮动
    - 16 只 ETF, 25日加权 log 回归 ann*R² 评分, 10日动量正
    - 持 1 只, 无候选切货币ETF (511880)
    - 11:00 检查并轮动

基准: 399303.XSHE
"""
from jqdata import *
from jqfactor import get_factor_values
import numpy as np
import pandas as pd
import math
from datetime import datetime, timedelta, time


# ============================== 初始化 ==============================
def initialize(context):
    log.set_level('order', 'error')
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.002), type='stock')
    set_slippage(PriceRelatedSlippage(0.001), type='fund')
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0.001,
                  open_commission=0.0003, close_commission=0.0003,
                  close_today_commission=0, min_commission=5),
        type='stock')
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0.0,
                  open_commission=0.0001, close_commission=0.0001,
                  close_today_commission=0, min_commission=5),
        type='fund')
    set_benchmark('399303.XSHE')

    # ===== 资金分配 =====
    g.sleeve_ratio = {'trend': 0.70, 'etf': 0.30}

    # ===== Sleeve A: 趋势龙头参数 =====
    g.hold_num = 5
    g.universe_index = '000985.XSHG'      # 中证全指
    g.lookback_long = 40                  # 中期动量 40日 (原 60)
    g.lookback_mid = 20
    g.high_breakout_tol = 0.88            # 远离 20日高 <=12%, 允许回踩突破后仍入选
    g.min_avg_money = 4e7
    g.vol_ratio_min = 0.80
    g.max_5d_volatility = 0.45            # 允许较高波动 (主升必然快)
    g.allow_ret_long_min = -0.05          # 中期动量只要不大亏即可 (揖取刚动股)
    g.market_cap_min = 30
    g.market_cap_max = 800
    g.roe_min = 4.0
    g.score_w_long = 0.10                 # 中期动量 (40d)
    g.score_w_mid = 0.10                  # 短期动量 (20d)
    g.score_w_r2 = 0.05                   # 趋势纯净度
    g.score_w_accel = 0.15                # 加速度
    g.score_w_macd = 0.08                 # MACD 柱上行
    g.score_w_ma_stack = 0.07             # 均线多头排列
    g.score_w_pos60 = 0.06                # 60日位置甜蜜区
    g.score_w_obv = 0.04                  # OBV 上行
    g.score_w_squeeze = 0.10              # BBands squeeze 释放
    g.score_w_rps = 0.10                  # 横截面 RPS 排名
    g.score_w_pullback = 0.07             # 回调质量 (越低越强)
    g.score_w_alpha101_6 = 0.04           # Alpha101 #6
    g.score_w_cap_focus = 0.04            # 资金集中度 (涨日量能占比)
    g.score_w_monthly = 0.05              # 月线共振软打分
    g.score_w_jq_factor = 0.05            # jqfactor 官方因子 (volatility_60 低波)
    g.pos60_sweet_low = 0.45
    g.pos60_sweet_high = 0.90
    g.candidate_top_n = 200
    g.industry_dedup = True               # 仅对 score前最优去重, 保留多赛道

    # 主线板块 + 多周期共振
    g.sector_top_n = 6                    # SW1 宽度 Top6 行业 (原 5)
    g.sector_min_universe = 15            # 主线过滤后不足则不收敛 (原 25)
    g.sector_breadth_window = 20
    g.weekly_resonance = True
    g.weekly_lookback = 10
    g.monthly_resonance_soft = True       # 月线改为软评分加成
    g.monthly_lookback = 3
    g.market_filter_enable = True

    # ===== 大盘 Regime 风控 (000300 vs 长短均线 → 仓位&持仓数动态) =====
    g.regime_enable = True
    g.regime_index = '000300.XSHG'
    g.regime_ma_short = 60                # 中期均线
    g.regime_ma_long = 120                # 长期均线 (半年线)
    g.regime_ratio_agg = 0.70             # 双均线之上: 趋势 70%
    g.regime_ratio_neu = 0.55             # 单均线之上: 55%
    g.regime_ratio_def = 0.40             # 双均线之下: 40% (降仓加现金)
    g.regime_hold_agg = 5
    g.regime_hold_neu = 4
    g.regime_hold_def = 3
    # 各 regime 仅调整仓位/持仓数; 止损与 MA 破位保留原值, 避免过度抛售影响 Sharpe
    g.regime_kick_rank_agg = 40
    g.regime_kick_rank_neu = 40
    g.regime_kick_rank_def = 40
    g.regime_stop_hold_agg = -0.08
    g.regime_stop_hold_neu = -0.08
    g.regime_stop_hold_def = -0.08
    g.regime_ma20_break_agg = 0.03
    g.regime_ma20_break_neu = 0.03
    g.regime_ma20_break_def = 0.03
    g.market_regime = 'AGG'                # 运行时

    # 卖出参数
    g.stop_loss_hold = -0.08              # 持仓 -8% 清
    g.stop_day_drop = -0.06
    g.ma20_break = 0.03
    g.profit_trail_trigger = 0.22         # 22%起追踪止盈 (保留主升空间)
    g.profit_trail_pullback = 0.07
    g.peak_giveback_trigger = 0.15        # 盈利曾>=15%后, 若回吐至 <= 40% 触发清仓
    g.peak_giveback_ratio = 0.40
    g.rebalance_kick_rank = 40
    g.rebalance_day_of_week = 1

    # 暴跌反弹博弈 (Sleeve C, 复用 ETF 现金)
    g.rebound_enable = True               # 暴跌反弹博弈开启
    g.rebound_bench = '399303.XSHE'
    g.rebound_window = 3                  # 监控基准近3日累跌
    g.rebound_threshold = -0.06           # 累跌 <= -6% 才触发 (避免假信号)
    g.rebound_etf = '159915.XSHE'
    g.rebound_cash_ratio = 0.40           # 用可用现金的 40%
    g.rebound_hold_max_days = 4
    g.rebound_stop_loss = -0.035          # -3.5% 止损
    g.rebound_take_profit = 0.04          # +4% 止盈 (反弹快走)
    g.rebound_cooldown_days = 3           # 冷静期, 防止连续下跌中重复追买
    g.rebound_state = {'active': False, 'entry_date': None, 'entry_price': 0.0, 'last_exit': None}

    # ===== Sleeve B: ETF 轮动参数 =====
    # 注: 实证发现 H1 2024 大幅 alpha 主要来自海外 ETF (纳指/标普/黄金) 在 A 股深熊期的负相关对冲
    # 因此保留完整池(含海外ETF), Regime 不切换 ETF 池, 防止移除关键 alpha 源
    g.etf_pool = [
        '510300.XSHG', '510500.XSHG', '159915.XSHE', '588000.XSHG',
        '512100.XSHG', '518880.XSHG',
        '513100.XSHG', '513500.XSHG', '513050.XSHG', '512690.XSHG',
        '512170.XSHG', '512760.XSHG', '512660.XSHG', '512880.XSHG',
    ]
    g.etf_defensive = '511880.XSHG'
    g.etf_lookback = 25
    g.etf_short_lookback = 10
    g.etf_holdings_num = 1
    g.etf_loss_floor = 0.97
    g.etf_min_score = 0.0
    g.etf_min_money = 5000
    g.etf_rebalance_tolerance = 0.05
    g.etf_defensive = '511880.XSHG'
    g.etf_lookback = 25
    g.etf_short_lookback = 10
    g.etf_holdings_num = 1
    g.etf_loss_floor = 0.97
    g.etf_min_score = 0.0
    g.etf_min_money = 5000
    g.etf_rebalance_tolerance = 0.05
    # ETF 黏性: 挑战者 score 需高于现持仓 score * (1 + margin) 才触发换仓, 抑制日内/相近分排序抖动
    g.etf_switch_margin = 0.10

    # ===== Sleeve D V2: 情绪龙头狙击 (A严选+B紧风控+C风格切换) =====
    # 长窗口回测验证 A+B+C 整套均不能稳定增厚: V1=104%, V2=66% vs 基线 116%
    # 暂时禁用, 保留代码以便后续 (例如加竞价数据/连板梯队识别) 再启
    g.emotion_enable = False
    g.emotion_lookback_days = 10           # 监控近 10 日
    g.emotion_min_limit_ups = 4            # A: 连扳 ≥4 (V1=3 → 伪龙头多, 提到 4 进一步过滤)
    g.emotion_min_turnover = 0.08          # 昨日换手率 ≥8% (情绪票特征)
    g.emotion_max_recent_gain = 1.00       # A: 近 10 日累涨 ≤100% (顶部不接)
    g.emotion_min_recent_gain = 0.30       # A: 近 10 日累涨 ≥30% (确认热门)
    g.emotion_cap_min = 30                 # A: 流通市值 30 亿起 (避免微盘妖股骗线)
    g.emotion_cap_max = 150                # A: 流通市值 ≤150 亿
    g.emotion_div_open_low = -0.02         # A: 首次分歧 (低开/平开) 严格 [-2%, +2%]
    g.emotion_div_open_high = 0.02
    g.emotion_div_morning_low = -0.03      # A: 09:40 现价 [-3%, +3%]
    g.emotion_div_morning_high = 0.03
    g.emotion_cash_ratio_boom = 0.25       # C: BOOM 期仓位 25%
    g.emotion_cash_ratio_normal = 0.12     # C: NORMAL 期 12%
    g.emotion_cash_ratio = 0.12            # 当日生效仓位 (phase 设置)
    g.emotion_holdings_num = 1             # 持 1 只
    g.emotion_hold_max_days = 5            # B: 最长 5 日 (V1=6)
    g.emotion_take_profit = 0.18           # +18% 止盈
    g.emotion_stop_loss = -0.045           # B: 止损 -4.5% (V1=-7% 太宽)
    g.emotion_intraday_kill = -0.03        # B: 首日 14:55 若 day_pct ≤-3% 直接平 (深度阴线撤退)
    g.emotion_distribution_drop = -0.04    # B: 放量退潮 日跌 ≤-4%
    g.emotion_distribution_vol = 1.3       # B: 量比 ≥1.3 (V1=1.5)
    g.emotion_cooldown_days = 5            # 平仓后冷静期
    g.emotion_state = {'code': None, 'entry_date': None, 'entry_price': 0.0,
                       'day_high': 0.0, 'last_exit': None}
    # C: 市场情绪风格 (每日 09:25 评估)
    g.market_phase = 'NORMAL'              # BOOM / NORMAL / CHILL / FROZEN
    g.phase_boom_lu = 60                   # 昨日涨停 ≥60 → BOOM
    g.phase_chill_lu = 25                  # 昨涨停 ≤25 → CHILL
    g.phase_frozen_lu = 15                 # 昨涨停 ≤15 → FROZEN (空仓)

    # ===== 运行时状态 =====
    g.target_list = []
    g.target_rank_cache = {}              # code -> rank 用于持仓评估
    g.stop_cooldown = {}                  # code -> 解禁日期 (止损后冷静期, 防止周一选股反复买入近期被止损的票)
    g.stop_cooldown_days = 10             # 止损/破MA20 后该股 10 个自然日内不入候选
    g.trend_meta = {}                     # code -> {entry_price, entry_date, day_high}
    g.yesterday_HL = []
    g.etf_rank_cache = {'date': None, 'data': None}

    # ===== 任务调度 =====
    run_daily(prepare_stocks_for_sell, '09:05')      # 收集昨涨停名单
    run_weekly(detect_market_phase, 1, '09:20')      # C: 每周一评估市场情绪风格 (减少全市场扫描开销)
    run_weekly(weekly_select_and_rebalance, g.rebalance_day_of_week, '09:30')
    run_daily(rebound_check, '09:35')                # 暴跌反弹博弈
    run_daily(emotion_leader_scan, '09:40')          # 情绪龙头狙击 (首次分歧介入)
    run_daily(etf_rebalance, '11:00')
    run_daily(daily_sell_check, '14:50')
    run_daily(emotion_leader_exit, '14:55')          # 情绪龙头退潮检测
    run_daily(after_close, '15:10')


def _is_etf(code):
    return code in g.etf_pool or code == g.etf_defensive


def _format(s):
    try:
        return f"{s}({get_security_info(s).display_name})"
    except Exception:
        return s


# ============================== 持仓侧每日准备 ==============================
def prepare_stocks_for_sell(context):
    pos = [s for s in context.portfolio.positions if not _is_etf(s)]
    if not pos:
        g.yesterday_HL = []
        return
    try:
        df = get_price(pos, end_date=context.previous_date, frequency='1d',
                       fields=['close', 'high_limit'], count=1, panel=False,
                       fill_paused=False)
        if df is not None and not df.empty:
            df = df[np.isclose(df.close, df.high_limit, rtol=0.0015, atol=0.01)]
            g.yesterday_HL = list(df.code)
        else:
            g.yesterday_HL = []
    except Exception:
        g.yesterday_HL = []


# ============================== 选股: 趋势龙头 ==============================
def _get_universe(context):
    today = context.current_dt.date()
    initial = get_index_stocks(g.universe_index, today)
    c_data = get_current_data()
    out = []
    y_day = context.previous_date
    # 清理过期冷静期
    cd_map = getattr(g, 'stop_cooldown', {})
    if cd_map:
        g.stop_cooldown = {k: v for k, v in cd_map.items() if v >= today}
        cd_map = g.stop_cooldown
    for s in initial:
        if s[0] in '348' or s[:2] == '68':
            continue
        # 止损冷静期内的票直接跳过
        if s in cd_map and cd_map[s] >= today:
            continue
        info = get_security_info(s)
        if info is None:
            continue
        if (y_day - info.start_date).days < 375:
            continue
        cd = c_data[s]
        if cd.is_st or cd.paused:
            continue
        nm = cd.name or ''
        dn = info.display_name or ''
        if 'ST' in nm or '*' in nm or '退' in nm or 'ST' in dn or '*' in dn or '退' in dn:
            continue
        out.append(s)
    return out


# ============================== 主线板块 (借鉴搅屎棍 SW1 宽度) ==============================
def _get_top_sectors(context, universe):
    """计算 SW1 各行业内『收盘价 > MA20』的占比, 返回 Top N 行业代码集合。"""
    y_day = context.previous_date
    try:
        h = get_price(universe, end_date=y_day, frequency='1d',
                      fields=['close'], count=g.sector_breadth_window,
                      panel=False, skip_paused=False, fill_paused=True)
        if h is None or h.empty:
            log.warn('[主线] 取价为空')
            return None
        # 不使用 pivot+dropna 会清空, 改用 groupby 计算 MA20 与 last
        h_sorted = h.sort_values(['code', 'time'])
        grp = h_sorted.groupby('code')['close']
        last_close = grp.last()
        ma20 = grp.mean()
        df = pd.DataFrame({'last': last_close, 'ma20': ma20})
        df = df.dropna()
        df['above'] = (df['last'] > df['ma20']).astype(float)
        if df.empty:
            log.warn('[主线] 价格表为空')
            return None
        ind_map = get_industry(df.index.tolist(), date=y_day)
        df['sw1'] = [ind_map.get(s, {}).get('sw_l1', {}).get('industry_code', None) for s in df.index]
        df = df.dropna(subset=['sw1'])
        if df.empty:
            log.warn('[主线] 行业映射空')
            return None
        ratio = df.groupby('sw1')['above'].mean()
        cnt = df.groupby('sw1').size()
        ratio = ratio[cnt >= 5]
        if ratio.empty:
            log.warn('[主线] 有效行业空')
            return None
        top = ratio.nlargest(g.sector_top_n)
        mkt_breadth = ratio.mean()
        log.info(f"[主线] 全市宽度={mkt_breadth:.2%} Top{g.sector_top_n}行业={dict((k, round(v,3)) for k,v in top.items())}")
        return {'top_codes': set(top.index.tolist()), 'market_breadth': mkt_breadth}
    except Exception as e:
        log.warn(f"[主线] 计算异常: {e}")
        return None


# ============================== 月线共振 ==============================
def _get_monthly_resonance(context, codes):
    """月线 close > MA3(月) 且本月 close > 上月 close 才返回 True"""
    if not getattr(g, 'monthly_resonance_soft', False) or not codes:
        return set(codes) if codes else set()
    y_day = context.previous_date
    try:
        df = get_price(codes, end_date=y_day, frequency='1d',
                       fields=['close'], count=g.monthly_lookback * 22 + 30,
                       panel=False, skip_paused=True)
        if df is None or df.empty:
            return set(codes)
    except Exception:
        return set(codes)
    out = set()
    for code, sub in df.groupby('code'):
        sub = sub.sort_values('time').set_index('time')
        try:
            mo = sub['close'].resample('M').last().dropna()
        except Exception:
            continue
        if len(mo) < g.monthly_lookback + 1:
            continue
        ma_m = mo.iloc[-g.monthly_lookback:].mean()
        if mo.iloc[-1] > ma_m and mo.iloc[-1] > mo.iloc[-2]:
            out.add(code)
    return out


# ============================== 大盘环境过滤 ==============================
def _market_ok(context):
    """基准 close > MA20 才允许加仓; 否则只持不补。"""
    if not g.market_filter_enable:
        return True
    try:
        h = attribute_history('000300.XSHG', 25, '1d', ['close'])
        if h is None or len(h) < 21:
            return True
        return h['close'].iloc[-1] > h['close'].iloc[-20:].mean()
    except Exception:
        return True


def _update_regime(context):
    """根据基准 close 与 MA60/MA120 计算 regime, 调整 sleeve_ratio['trend'] 与 hold_num.
    AGG: close 同时 > MA60 且 > MA120 → 进攻 (70% / 5仓)
    NEU: close 仅高于一条                → 平衡 (55% / 4仓)
    DEF: close 双均线之下                → 防守 (40% / 3仓, 多余资金停泊 ETF)
    """
    if not getattr(g, 'regime_enable', True):
        return
    try:
        n = max(g.regime_ma_long, g.regime_ma_short) + 5
        h = attribute_history(g.regime_index, n, '1d', ['close'])
        if h is None or len(h) < g.regime_ma_long:
            return
        c = h['close'].iloc[-1]
        ma_s = h['close'].iloc[-g.regime_ma_short:].mean()
        ma_l = h['close'].iloc[-g.regime_ma_long:].mean()
    except Exception:
        return
    above_s = c > ma_s
    above_l = c > ma_l
    if above_s and above_l:
        regime, ratio, hold_n = 'AGG', g.regime_ratio_agg, g.regime_hold_agg
        kick, sh, mb = g.regime_kick_rank_agg, g.regime_stop_hold_agg, g.regime_ma20_break_agg
    elif above_s or above_l:
        regime, ratio, hold_n = 'NEU', g.regime_ratio_neu, g.regime_hold_neu
        kick, sh, mb = g.regime_kick_rank_neu, g.regime_stop_hold_neu, g.regime_ma20_break_neu
    else:
        regime, ratio, hold_n = 'DEF', g.regime_ratio_def, g.regime_hold_def
        kick, sh, mb = g.regime_kick_rank_def, g.regime_stop_hold_def, g.regime_ma20_break_def
    g.market_regime = regime
    g.sleeve_ratio['trend'] = ratio
    g.sleeve_ratio['etf'] = 1.0 - ratio
    g.hold_num = hold_n
    g.rebalance_kick_rank = kick
    g.stop_loss_hold = sh
    g.ma20_break = mb
    log.info(f"[Regime] {regime} close={c:.2f} MA{g.regime_ma_short}={ma_s:.2f} "
             f"MA{g.regime_ma_long}={ma_l:.2f} → trend={ratio:.0%}/{hold_n}仓 "
             f"kick={kick} sh={sh:.0%} mb={mb:.0%}")


# ============================== 周线共振 ==============================
def _get_weekly_resonance(context, codes):
    """周线 close > MA10(weekly) 才返回 True。返回 set(code)"""
    if not g.weekly_resonance or not codes:
        return set(codes) if codes else set()
    y_day = context.previous_date
    # 取约 (10 周 * 5) + 5 日, 然后转周线
    try:
        df = get_price(codes, end_date=y_day, frequency='1d',
                       fields=['close'], count=g.weekly_lookback * 5 + 10,
                       panel=False, skip_paused=True)
        if df is None or df.empty:
            return set(codes)
    except Exception:
        return set(codes)
    out = set()
    for code, sub in df.groupby('code'):
        sub = sub.sort_values('time').set_index('time')
        try:
            wk = sub['close'].resample('W-FRI').last().dropna()
        except Exception:
            continue
        if len(wk) < g.weekly_lookback + 1:
            continue
        ma_w = wk.iloc[-g.weekly_lookback:].mean()
        if wk.iloc[-1] > ma_w:
            out.add(code)
    return out


def _compute_trend_scores(context, universe):
    y_day = context.previous_date
    if not universe:
        return pd.DataFrame()
    n_bars = max(g.lookback_long, 65) + 35  # 需为 MACD(26+9) 与 60日位置预留
    df = get_price(universe, end_date=y_day, frequency='1d',
                   fields=['close', 'high', 'low', 'volume', 'money'], count=n_bars,
                   panel=False, skip_paused=True, fq='pre')
    if df is None or df.empty:
        return pd.DataFrame()

    rows = []
    for code, group in df.groupby('code'):
        if len(group) < g.lookback_long + 1:
            continue
        g_sorted = group.sort_values('time').reset_index(drop=True)
        close = g_sorted['close'].values
        high = g_sorted['high'].values
        low = g_sorted['low'].values
        money = g_sorted['money'].values
        volume = g_sorted['volume'].values
        last = close[-1]
        if last <= 0:
            continue
        # 均线
        ma5 = close[-5:].mean()
        ma10 = close[-10:].mean()
        ma20 = close[-g.lookback_mid:].mean()
        ma60 = close[-g.lookback_long:].mean()
        if not (last > ma20 > ma60):
            continue
        high20 = high[-g.lookback_mid:].max()
        if last < high20 * g.high_breakout_tol:
            continue
        # 5日波动过滤
        try:
            low5_arr = close[-5:]
            vol5 = (high[-5:].max() - low5_arr.min()) / low5_arr.min() if low5_arr.min() > 0 else 1
            if vol5 > g.max_5d_volatility:
                continue
        except Exception:
            pass
        ret_long = last / close[-(g.lookback_long + 1)] - 1
        ret_mid = last / close[-(g.lookback_mid + 1)] - 1
        if ret_long <= g.allow_ret_long_min or ret_mid <= 0:
            continue
        avg_money_long = money[-g.lookback_mid:].mean()
        if avg_money_long < g.min_avg_money:
            continue
        avg_money_short = money[-5:].mean()
        if avg_money_long > 0 and avg_money_short / avg_money_long < g.vol_ratio_min:
            continue
        # 独立趋势 R²
        y = np.log(close[-g.lookback_long:])
        x = np.arange(len(y))
        try:
            slope, intercept = np.polyfit(x, y, 1)
        except Exception:
            continue
        if slope <= 0:
            continue
        ss_res = np.sum((y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 1e-9 else 0

        # 主升因子 ============================================
        # 1. 加速度: 短期5日均速度 / 长期20日均速度
        ret_5 = last / close[-6] - 1 if len(close) >= 6 else 0
        accel = (ret_5 * 4) / max(ret_mid, 1e-6) - 1

        # 2. MACD 柱 (12,26,9)
        if len(close) >= 35:
            close_ser = pd.Series(close)
            ema12 = close_ser.ewm(span=12, adjust=False).mean()
            ema26 = close_ser.ewm(span=26, adjust=False).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9, adjust=False).mean()
            macd_hist = (dif - dea) * 2
            macd_last = macd_hist.iloc[-1]
            macd_prev = macd_hist.iloc[-4] if len(macd_hist) >= 4 else 0
            macd_score = max(0.0, macd_last) + max(0.0, macd_last - macd_prev)
        else:
            macd_score = 0

        # 3. 均线多头排列
        ma_stack = 1.0 if (last > ma5 > ma10 > ma20 > ma60) else (
            0.6 if (last > ma5 and ma5 > ma20 > ma60) else 0.0)

        # 4. 60日位置甜蜜区 (避免顶部追高)
        win60 = min(len(close), 60)
        h60 = high[-win60:].max()
        l60 = low[-win60:].min()
        if h60 > l60:
            pos60 = (last - l60) / (h60 - l60)
        else:
            pos60 = 0.5
        if g.pos60_sweet_low <= pos60 <= g.pos60_sweet_high:
            pos60_score = 1.0
        elif pos60 < g.pos60_sweet_low:
            pos60_score = max(0.0, pos60 / g.pos60_sweet_low)
        else:
            pos60_score = max(0.0, 1 - (pos60 - g.pos60_sweet_high) * 5)

        # 5. OBV 上行斜率 (近 20日)
        if len(close) >= 22 and len(volume) >= 22:
            sign = np.sign(np.diff(close[-22:]))
            obv = np.cumsum(sign * volume[-21:])
            if len(obv) >= 10:
                obv_x = np.arange(len(obv))
                try:
                    obv_slope = np.polyfit(obv_x, obv, 1)[0]
                except Exception:
                    obv_slope = 0
            else:
                obv_slope = 0
        else:
            obv_slope = 0

        # 6. BBands squeeze 释放
        if len(close) >= 60:
            std5 = close[-5:].std()
            std60 = close[-60:].std()
            if std60 > 0:
                ratio_now = std5 / std60
                hist_ratio = []
                for k in range(5, min(35, len(close))):
                    s5 = close[-k - 5:-k].std() if k + 5 <= len(close) else None
                    if s5 is not None:
                        hist_ratio.append(s5 / std60)
                squeeze_score = 0.0
                if hist_ratio:
                    min_hist = min(hist_ratio)
                    if min_hist < 0.6 and ratio_now > min_hist * 1.3:
                        squeeze_score = min(1.0, (ratio_now - min_hist) / max(min_hist, 0.1))
            else:
                squeeze_score = 0
        else:
            squeeze_score = 0

        # 7. 回调质量: 近 20日 max drawdown / max gain, 越小越表示主升中调整浅
        if len(close) >= 21:
            seg = close[-20:]
            run_max = np.maximum.accumulate(seg)
            dd = (seg - run_max) / run_max
            max_dd = abs(dd.min()) if len(dd) else 0
            gain20 = seg[-1] / seg[0] - 1 if seg[0] > 0 else 0
            pullback_quality = 1.0 - min(1.0, max_dd / max(gain20, 0.03))
        else:
            pullback_quality = 0.5

        # 8. Alpha101 #6: -correlation(open, volume, 10)
        if len(close) >= 11 and len(volume) >= 11:
            try:
                opens = g_sorted['close'].values[-11:]  # 未取 open 字段, 用 close 代替
                vols = volume[-11:]
                if opens.std() > 0 and vols.std() > 0:
                    corr = np.corrcoef(opens, vols)[0, 1]
                    alpha101_6 = -corr
                else:
                    alpha101_6 = 0
            except Exception:
                alpha101_6 = 0
        else:
            alpha101_6 = 0

        # 9. 资金集中度: 近 5日 涨日 money / 总 money
        if len(close) >= 6 and len(money) >= 5:
            up_mask = np.diff(close[-6:]) > 0
            sum_money = money[-5:].sum()
            cap_focus = (money[-5:][up_mask].sum() / sum_money) if sum_money > 0 else 0
        else:
            cap_focus = 0.5

        # 10. 量价同向性 (5日 close/volume Pearson corr; 高=放量上行健康, 低=量价背离)
        if len(close) >= 6 and len(volume) >= 6:
            c5 = close[-5:]
            v5 = volume[-5:]
            if c5.std() > 0 and v5.std() > 0:
                try:
                    pv_corr5 = float(np.corrcoef(c5, v5)[0, 1])
                except Exception:
                    pv_corr5 = 0.0
            else:
                pv_corr5 = 0.0
        else:
            pv_corr5 = 0.0

        # 11. 强势天数: 近 20日 close > MA5 的比例
        if len(close) >= 25:
            ser_c = pd.Series(close[-25:])
            ma5_ser = ser_c.rolling(5).mean()
            tail = (ser_c.iloc[-20:] > ma5_ser.iloc[-20:]).sum()
            strong_days = float(tail) / 20.0
        else:
            strong_days = 0.5

        # 12. 新高密度: 近 20日中创 60日新高的天数 (高=持续强势)
        if len(close) >= 80:
            ser_c2 = pd.Series(close[-80:])
            roll_max = ser_c2.rolling(60).max()
            recent = ser_c2.iloc[-20:]
            roll_max_recent = roll_max.iloc[-20:]
            high_density = float((recent >= roll_max_recent * 0.999).sum()) / 20.0
        else:
            high_density = 0.0

        # 13. 缩量回踩: 近 3 日累计跌幅 in [-6%, 0%] 且 3日均量/前 20日均量 < 0.75 -> 健康洗盘
        quiet_pullback = 0.0
        if len(close) >= 24 and len(volume) >= 24:
            ret3 = close[-1] / close[-4] - 1 if close[-4] > 0 else 0
            v3 = volume[-3:].mean()
            v20p = volume[-23:-3].mean() if len(volume) >= 23 else volume[:-3].mean()
            if v20p > 0:
                v_ratio = v3 / v20p
                if -0.06 <= ret3 <= 0.0 and v_ratio < 0.75:
                    quiet_pullback = 1.0
                elif -0.08 <= ret3 <= 0.02 and v_ratio < 0.9:
                    quiet_pullback = 0.5

        # 14. 二阶加速度: 最近 5日均速 - 前 5日均速 (动量再次提速)
        if len(close) >= 11:
            ret5_now = close[-1] / close[-6] - 1 if close[-6] > 0 else 0
            ret5_prev = close[-6] / close[-11] - 1 if close[-11] > 0 else 0
            accel2 = ret5_now - ret5_prev
        else:
            accel2 = 0.0

        # 15. amihud_20: 流动性溢价因子 (Iter11 因子分析: IR +0.52, t +4.84, 与 VOL5 corr 0.04)
        # log(1 + mean(|ret_1d| / (money/1e8), 20)); 直觉: 流动性低的股 → 风险溢价 → 后续正 alpha
        if len(close) >= 22 and len(money) >= 22:
            r1 = np.abs(np.diff(close[-22:]) / close[-22:-1])
            mn = money[-21:] / 1e8
            mn_safe = np.where(mn > 1e-6, mn, 1e-6)
            amihud_raw = np.mean(r1 / mn_safe)
            amihud_20 = np.log1p(amihud_raw) if amihud_raw > 0 else 0.0
        else:
            amihud_20 = 0.0

        # 16. vol_pulse_neg: 量能脉冲反向 (Iter11 因子分析: 放量 IR -0.66, 反方向后 +0.66 强 alpha)
        # -(amount_5d_mean / amount_20d_mean - 1); 直觉: 短期放量股短期跑输, 取负号后 +1 方向
        if len(close) >= 22 and len(money) >= 22:
            m5 = money[-5:].mean()
            m20 = money[-20:].mean()
            if m20 > 0:
                vol_pulse_neg = -((m5 / m20) - 1.0)
            else:
                vol_pulse_neg = 0.0
        else:
            vol_pulse_neg = 0.0

        rows.append({'code': code, 'last': last, 'ma20': ma20,
                     'ret_long': ret_long, 'ret_mid': ret_mid, 'r2': r2,
                     'accel': accel, 'macd': macd_score,
                     'ma_stack': ma_stack, 'pos60': pos60_score,
                     'obv': obv_slope, 'squeeze': squeeze_score,
                     'pullback_q': pullback_quality,
                     'alpha101_6': alpha101_6,
                     'cap_focus': cap_focus,
                     'pv_corr5': pv_corr5,
                     'strong_days': strong_days,
                     'high_density': high_density,
                     'quiet_pullback': quiet_pullback,
                     'accel2': accel2,
                     'amihud_20': amihud_20,
                     'vol_pulse_neg': vol_pulse_neg})
    if not rows:
        return pd.DataFrame()
    df_score = pd.DataFrame(rows)

    # 基本面过滤: ROE & 市值
    try:
        fdf = get_fundamentals(query(
            valuation.code, valuation.market_cap, indicator.roe
        ).filter(
            valuation.code.in_(df_score.code.tolist())
        ), date=y_day)
        if fdf is not None and not fdf.empty:
            fdf = fdf[(fdf.market_cap >= g.market_cap_min) &
                      (fdf.market_cap <= g.market_cap_max) &
                      (fdf.roe >= g.roe_min)]
            df_score = df_score[df_score.code.isin(fdf.code.tolist())]
    except Exception as e:
        log.warn(f"[选股] 基本面过滤失败: {e}")

    if df_score.empty:
        return df_score

    # Top N by ret_long
    df_score = df_score.nlargest(min(g.candidate_top_n, len(df_score)), 'ret_long').reset_index(drop=True)

    # 归一化分数
    def _norm(s):
        rng = s.max() - s.min()
        if rng == 0:
            return pd.Series([0.5] * len(s), index=s.index)
        return (s - s.min()) / rng

    # ====== 抗过拟合 rank-fusion 评分 ======
    # 所有因子按横截面排名百分位 (高分=优), 等权平均. 不再使用人工权重.
    # 反向因子 (越低越好) 取 1 - rank_pct.

    df_score['rps'] = df_score['ret_long'].rank(pct=True)

    # 板块内相对强度: ret_mid - 同 SW1 行业 ret_mid 均值 (基于 y_day, 无未来数据)
    try:
        ind_map_rs = get_industry(df_score['code'].tolist(), date=y_day)
        sw1_codes = {c: ind_map_rs.get(c, {}).get('sw_l1', {}).get('industry_code', None)
                     for c in df_score['code'].tolist()}
        df_score['sw1'] = df_score['code'].map(sw1_codes)
        ind_mean = df_score.groupby('sw1')['ret_mid'].transform('mean')
        df_score['rs_industry'] = df_score['ret_mid'] - ind_mean
        df_score['rs_industry'] = df_score['rs_industry'].fillna(0.0)
    except Exception:
        df_score['rs_industry'] = 0.0

    # jqfactor 官方因子库 (逐个拉取避免单个名错导致全 batch 失败)
    # Iter11: 88周 RankIC 实证, 仅保留 IR 显著且互不冗余的 2 个 (删 VOL60/VOL20/sharpe_ratio_60(BUG)/roe_ttm/npg)
    jq_factor_names = ['VOL5', 'turnover_volatility']
    jq_factor_data = {}
    for fn in jq_factor_names:
        try:
            fv = get_factor_values(securities=df_score['code'].tolist(),
                                   factors=[fn], end_date=y_day, count=1)
            fdf = fv.get(fn)
            if fdf is not None and not fdf.empty:
                ser = fdf.iloc[-1]
                if ser.notna().any():
                    jq_factor_data[fn] = df_score['code'].map(ser).fillna(ser.median())
        except Exception:
            continue

    # 将所有信号归集到 (因子名, 方向) 字典.
    # Iter12: 基于 84 周 Cell 10 IC 分析 (h=10d 截面 Spearman), 在 universe 预过滤后的强股池里,
    # 长中期动量/位置/OBV/均线多头度/R² 的 IC 显著为负 → 翻方向 (均值回归占优).
    #   ret_long IR=-0.57, ret_mid IR=-0.57, pos60 IR=-0.47, ma_stack_count IR=-0.42,
    #   obv IR=-0.41, r2 IR=-0.21, pullback_q IR=+0.15 (策略原 -1 反了, 改成 +1 弱权重)
    # 保留 +1 的: accel(IR +0.38), amihud_20(IR +0.52), vol_pulse_neg(IR +0.66)
    feats = {
        'ret_long': (df_score['ret_long'], -1),        # Iter12: 翻向 (-)
        'ret_mid': (df_score['ret_mid'], -1),          # Iter12: 翻向 (-)
        'r2': (df_score['r2'], -1),                    # Iter12: 翻向 (-)
        'accel': (df_score['accel'], +1),              # 保留 (+), 唯一动量正 alpha
        'macd': (df_score['macd'], +1),                # Iter13 翻向 (-) 回测劣化 11pp, 回滚 (+); 单因子 IC 与组合协同存在背离
        'ma_stack': (df_score['ma_stack'], -1),        # Iter12: 翻向 (-)
        'pos60': (df_score['pos60'], -1),              # Iter12: 翻向 (-)
        'obv': (df_score['obv'], -1),                  # Iter12: 翻向 (-)
        'squeeze': (df_score['squeeze'], +1),          # Iter13 翻向 (-) 回测劣化, 回滚 (+)
        'rps': (df_score['rps'], -1),                  # rps 即 ret_long pct, 与 ret_long 同方向 → -1
        'pullback_q': (df_score['pullback_q'], +1),    # Iter12: 翻向 (+)
        'alpha101_6_local': (df_score['alpha101_6'], +1),  # Cell 11 IC IR=+0.60 验证, 保留 (+)
        'cap_focus': (df_score['cap_focus'], +1),       # Iter13 翻向 (-) 回测劣化, 回滚 (+)
        'amihud_20': (df_score['amihud_20'], +1),       # IR +0.52, 流动性溢价
        'vol_pulse_neg': (df_score['vol_pulse_neg'], +1), # IR +0.66 (反向后), 量能脉冲反转
    }
    # jqfactor 官方因子方向 (Iter11: 仅保留 2 个 IR 显著且独立的)
    direction_map = {
        'VOL5': -1,                  # 低波动溢价 (IR +0.30)
        'turnover_volatility': -1,   # 换手波动低的更稳健 (IR +0.32)
    }
    for fn, ser in jq_factor_data.items():
        sign = direction_map.get(fn, +1)
        feats[f'jq_{fn}'] = (ser, sign)

    # 计算每个因子的 rank_pct, 反向因子翻转, 简单等权融合
    rank_cols = []
    for name, tup in feats.items():
        if len(tup) == 3:
            ser, sign, _grp = tup
        else:
            ser, sign = tup
        try:
            rk = ser.rank(pct=True, method='average').fillna(0.5)
        except Exception:
            continue
        if sign < 0:
            rk = 1.0 - rk
        col = f'rk_{name}'
        df_score[col] = rk.values
        rank_cols.append(col)
    df_score['score'] = df_score[rank_cols].mean(axis=1) if rank_cols else 0.5
    jq_names_loaded = list(jq_factor_data.keys())
    log.info(f"[评分] {len(rank_cols)} 因子 (jqfactor {len(jq_names_loaded)}); 候选={len(df_score)}")

    df_score.sort_values('score', ascending=False, inplace=True)
    df_score.reset_index(drop=True, inplace=True)

    # 行业去重: 同 SW1 仅保留 score 最高的 2 只 (原 1 只), 保留赛道型广度
    if g.industry_dedup:
        try:
            ind_map = get_industry(df_score.code.tolist(), date=y_day)
            df_score['sw1'] = [
                ind_map.get(c, {}).get('sw_l1', {}).get('industry_code', c) for c in df_score['code']
            ]
            df_score = df_score.groupby('sw1', group_keys=False).head(2)
        except Exception as e:
            log.warn(f"[选股] 行业去重失败: {e}")
    df_score.reset_index(drop=True, inplace=True)
    return df_score


def weekly_select_and_rebalance(context):
    _update_regime(context)
    y_day = context.previous_date
    universe = _get_universe(context)
    # 主线行业筛选
    g.top_sectors = None
    sector_info = _get_top_sectors(context, universe)
    if sector_info:
        g.top_sectors = sector_info['top_codes']
        # 将 universe 收敛到 Top 行业
        try:
            ind_map = get_industry(universe, date=y_day)
            universe_filtered = [s for s in universe
                                 if ind_map.get(s, {}).get('sw_l1', {}).get('industry_code') in g.top_sectors]
            log.info(f"[主线] universe {len(universe)} -> {len(universe_filtered)} (Top{g.sector_top_n}行业)")
            if len(universe_filtered) >= g.sector_min_universe:
                universe = universe_filtered
        except Exception as e:
            log.warn(f"[主线] 行业映射失败: {e}")

    df_score = _compute_trend_scores(context, universe)
    if df_score.empty:
        log.info('[趋势] 无候选, 跳过调仓')
        g.target_list = []
        g.target_rank_cache = {}
        return

    # 周线共振过滤
    if g.weekly_resonance:
        wk_ok = _get_weekly_resonance(context, df_score['code'].tolist())
        before = len(df_score)
        df_score = df_score[df_score['code'].isin(wk_ok)].reset_index(drop=True)
        log.info(f"[周共振] {before} -> {len(df_score)}")
        if df_score.empty:
            log.info('[趋势] 周线共振后无候选')
            g.target_list = []
            g.target_rank_cache = {}
            return

    # 月线共振: 软评分加成 (不过滤)
    if g.monthly_resonance_soft:
        mo_ok = _get_monthly_resonance(context, df_score['code'].tolist())
        df_score['monthly_bonus'] = df_score['code'].isin(mo_ok).astype(float)
        df_score['score'] = df_score['score'] + g.score_w_monthly * df_score['monthly_bonus']
        df_score.sort_values('score', ascending=False, inplace=True)
        df_score.reset_index(drop=True, inplace=True)
        log.info(f"[月共振软] 命中 {int(df_score['monthly_bonus'].sum())}/{len(df_score)}")

    g.target_rank_cache = {row.code: i + 1 for i, row in df_score.iterrows()}
    target = df_score.head(g.hold_num)['code'].tolist()
    g.target_list = target
    log.info(f"[趋势] 候选={len(df_score)} 目标={[_format(s) for s in target]}")

    # 卖出: 持仓跌出 kick_rank 且非昨涨停 才卖出 (降低换手); 情绪持仓由 Sleeve D 单独管理
    em_code = g.emotion_state.get('code') if hasattr(g, 'emotion_state') else None
    cur_hold = [s for s in context.portfolio.positions if not _is_etf(s) and s != em_code
                and context.portfolio.positions[s].total_amount > 0]
    keep_set = set()
    for s in cur_hold:
        rk = g.target_rank_cache.get(s, 9999)
        if rk <= g.rebalance_kick_rank or s in g.yesterday_HL:
            keep_set.add(s)
        else:
            order_target_value(s, 0)
            log.info(f"[趋势卖] {_format(s)} 排名跌出{rk}")
            g.trend_meta.pop(s, None)

    # 买入: 缺仓位的等权补足
    cur_hold = [s for s in context.portfolio.positions if not _is_etf(s) and s != em_code
                and context.portfolio.positions[s].total_amount > 0]
    need_slots = max(0, g.hold_num - len(cur_hold))
    need_buy = [s for s in target if s not in cur_hold][:need_slots]
    if need_buy and not _market_ok(context):
        log.info('[趋势] 大盘走弱(收盘<MA20), 只持不补')
        need_buy = []
    total = context.portfolio.total_value
    sleeve_val = total * g.sleeve_ratio['trend']
    per_value = sleeve_val / float(g.hold_num)
    c_data = get_current_data()
    for s in need_buy:
        cd = c_data[s]
        if cd.paused:
            continue
        if pd.notna(cd.high_limit) and cd.last_price >= cd.high_limit * 0.995:
            log.info(f"[趋势买跳过] {_format(s)} 涨停")
            continue
        o = order_target_value(s, per_value)
        if o is not None:
            g.trend_meta[s] = {
                'entry_price': cd.last_price,
                'entry_date': context.current_dt.strftime('%Y%m%d'),
                'day_high': cd.last_price,
            }
            log.info(f"[趋势买] {_format(s)} 目标={per_value:.0f}")


# ============================== 卖出: 趋势止损/止盈/排名 ==============================
def daily_sell_check(context):
    em_code = g.emotion_state.get('code') if hasattr(g, 'emotion_state') else None
    cur_hold = [s for s in context.portfolio.positions if not _is_etf(s) and s != em_code
                and context.portfolio.positions[s].total_amount > 0]
    if not cur_hold:
        return
    y_day = context.previous_date
    try:
        df = get_price(cur_hold, end_date=y_day, frequency='1d',
                       fields=['close'], count=g.lookback_mid, panel=False,
                       skip_paused=True)
    except Exception:
        df = None
    ma20_map = {}
    if df is not None and not df.empty:
        for code, sub in df.groupby('code'):
            if len(sub) >= 5:
                ma20_map[code] = sub['close'].mean()

    c_data = get_current_data()
    for s in cur_hold:
        pos = context.portfolio.positions[s]
        cd = c_data[s]
        cp = cd.last_price
        if cp <= 0 or pos.avg_cost <= 0:
            continue
        # 涨停不卖
        if pd.notna(cd.high_limit) and cp >= cd.high_limit * 0.995:
            continue
        meta = g.trend_meta.setdefault(s, {'entry_price': pos.avg_cost,
                                            'entry_date': '',
                                            'day_high': cp})
        meta['day_high'] = max(meta.get('day_high', cp), cp)
        pp = (cp - pos.avg_cost) / pos.avg_cost
        ma20 = ma20_map.get(s)
        # 当日跌幅
        if cd.day_open > 0:
            dg = (cp - cd.day_open) / cd.day_open
        else:
            dg = 0
        reason = ''
        if pp <= g.stop_loss_hold:
            reason = f'止损{pp:.2%}'
        elif pp > 0 and dg <= g.stop_day_drop:
            # 仅在盈利时保护利润
            reason = f'盈利中日跌{dg:.2%}'
        elif ma20 and cp < ma20 * (1 - g.ma20_break):
            reason = f'破MA20'
        elif pp >= g.profit_trail_trigger:
            # 自当日高点回撤 5%
            if cp < meta['day_high'] * (1 - g.profit_trail_pullback):
                reason = f'追踪止盈{pp:.2%}'
        # 峰值回吐保护: 持仓曾盈利 >=20%, 当前回吐到峰值 50% 以下 -> 清仓锁利
        if not reason and pos.avg_cost > 0:
            peak_p = (meta['day_high'] - pos.avg_cost) / pos.avg_cost
            if peak_p >= g.peak_giveback_trigger and pp < peak_p * g.peak_giveback_ratio:
                reason = f'峰值回吐 峰{peak_p:.2%}->现{pp:.2%}'
        if not reason:
            # 排名跌出 kick_rank
            rk = g.target_rank_cache.get(s)
            if rk and rk > g.rebalance_kick_rank:
                reason = f'排名跌出{rk}'
        if reason:
            order_target_value(s, 0)
            log.info(f"[趋势卖] {_format(s)} {reason} 收益={pp:.2%}")
            g.trend_meta.pop(s, None)
            # 加入止损/破位冷静期 (反弹和小亏在 reason 中体现; 仅对负面退出加冷静期)
            if ('止损' in reason or '破MA20' in reason or '日跌' in reason or '回吐' in reason):
                g.stop_cooldown[s] = context.current_dt.date() + timedelta(days=g.stop_cooldown_days)


# ============================== 暴跌反弹博弈 (Sleeve C) ==============================
def rebound_check(context):
    """基准近 N 日累跌 <= 阈值时, 用部分现金买入弹性 ETF; 持仓期内止盈止损或到期强平."""
    if not getattr(g, 'rebound_enable', False):
        return
    state = g.rebound_state
    etf = g.rebound_etf
    today = context.current_dt.date()
    cur = get_current_data()
    # ---- 1. 持仓中: 检查止盈/止损/到期 ----
    if state.get('active'):
        try:
            pos = context.portfolio.positions.get(etf)
        except Exception:
            pos = None
        if pos and pos.total_amount > 0:
            cp = cur[etf].last_price
            ep = state.get('entry_price', pos.avg_cost) or pos.avg_cost
            if ep <= 0:
                ep = pos.avg_cost
            ret = (cp - ep) / ep if ep > 0 else 0
            days_held = (today - state['entry_date']).days if state.get('entry_date') else 99
            exit_reason = ''
            if ret >= g.rebound_take_profit:
                exit_reason = f'反弹止盈{ret:.2%}'
            elif ret <= g.rebound_stop_loss:
                exit_reason = f'反弹止损{ret:.2%}'
            elif days_held >= g.rebound_hold_max_days:
                exit_reason = f'反弹到期{ret:.2%}'
            if exit_reason:
                order_target_value(etf, 0)
                log.info(f"[反弹平] {etf} {exit_reason}")
                g.rebound_state = {'active': False, 'entry_date': None,
                                   'entry_price': 0.0, 'last_exit': today}
            return
        else:
            # 未持仓但 active=True -> 清状态
            g.rebound_state['active'] = False

    # ---- 2. 未持仓: 检测暴跌触发 ----
    # 冷静期: 上次平仓后 N 日内不再触发
    last_exit = g.rebound_state.get('last_exit')
    if last_exit and (today - last_exit).days < g.rebound_cooldown_days:
        return
    try:
        bench_px = attribute_history(g.rebound_bench, max(g.rebound_window, 10) + 5,
                                     '1d', ['close'])
    except Exception:
        return
    if bench_px is None or len(bench_px) < g.rebound_window + 1:
        return
    closes = bench_px['close'].values
    cum_ret = closes[-1] / closes[-g.rebound_window - 1] - 1 if closes[-g.rebound_window - 1] > 0 else 0
    if cum_ret > g.rebound_threshold:
        return
    # 额外条件: 最近 1 日跌幅 <= -2% (确认是急跌而非缓跌)
    day1 = closes[-1] / closes[-2] - 1 if len(closes) >= 2 and closes[-2] > 0 else 0
    if day1 > -0.015:
        return
    # 额外条件: 基准未跌破 60 日线超过 8% (避免熊市深度下跌中"接刀")
    if len(closes) >= 60:
        ma60_bench = closes[-60:].mean()
        if closes[-1] < ma60_bench * 0.92:
            return
    # 触发条件: 累跌 <= -4%
    cash_avail = context.portfolio.available_cash
    if cash_avail < 5000:
        return
    cp = cur[etf].last_price
    if cp <= 0:
        return
    # 防止在 ETF 涨停时追买
    if pd.notna(cur[etf].high_limit) and cp >= cur[etf].high_limit * 0.995:
        return
    target_value = cash_avail * g.rebound_cash_ratio
    target_shares = int(target_value / cp / 100) * 100
    if target_shares < 100:
        return
    try:
        order(etf, target_shares)
        g.rebound_state = {'active': True, 'entry_date': today, 'entry_price': cp,
                           'last_exit': g.rebound_state.get('last_exit')}
        log.info(f"[反弹买] {etf} {target_shares}股 @ {cp:.3f} 基准{g.rebound_window}日累跌{cum_ret:.2%} 日跌{day1:.2%}")
    except Exception as e:
        log.warn(f"[反弹买失败] {e}")


# ============================== Sleeve D: 情绪龙头狙击 ==============================
def detect_market_phase(context):
    """C: 每周一 09:20 评估市场情绪风格 (轻量版).
    BOOM   : 昨涨停 ≥60 → 25%
    NORMAL : 中间         → 12%
    CHILL  : 昨涨停 ≤25 → 6%
    FROZEN : 昨涨停 ≤15 → 0% 并强平
    注: 为减少开销, 仅周一检测一次, 全周复用 g.market_phase.
    """
    if not getattr(g, 'emotion_enable', False):
        return
    y_day = context.previous_date
    try:
        stocks = get_index_stocks('000985.XSHG', date=y_day)
    except Exception:
        try:
            stocks = list(get_all_securities(types=['stock'], date=y_day).index)
        except Exception:
            stocks = []
    n_lu = 0
    if stocks:
        try:
            df = get_price(stocks, end_date=y_day, frequency='1d',
                           fields=['close', 'high_limit'],
                           count=1, panel=False, skip_paused=True)
            if df is not None and not df.empty:
                n_lu = int((df['close'] >= df['high_limit'] * 0.998).sum())
        except Exception:
            pass
    if n_lu >= g.phase_boom_lu:
        phase = 'BOOM'
        ratio = g.emotion_cash_ratio_boom
    elif n_lu <= g.phase_frozen_lu:
        phase = 'FROZEN'
        ratio = 0.0
    elif n_lu <= g.phase_chill_lu:
        phase = 'CHILL'
        ratio = g.emotion_cash_ratio_normal * 0.5
    else:
        phase = 'NORMAL'
        ratio = g.emotion_cash_ratio_normal
    g.market_phase = phase
    g.emotion_cash_ratio = ratio
    log.info(f"[情绪相] phase={phase} 昨涨停={n_lu} Sleeve_D仓位={ratio:.0%}")
    if phase == 'FROZEN':
        code = g.emotion_state.get('code')
        if code and code in context.portfolio.positions:
            try:
                order_target_value(code, 0)
                log.info(f"[情绪卖] {_format(code)} 退潮冰点强平")
                g.emotion_state = {'code': None, 'entry_date': None, 'entry_price': 0.0,
                                   'day_high': 0.0, 'last_exit': context.current_dt.date()}
            except Exception as e:
                log.warn(f"[情绪冰点平仓失败] {e}")


def _scan_emotion_candidates(context):
    """扫描全市场, 找符合连扳条件的情绪龙头候选 (基于昨日及更早数据, 无未来数据)."""
    y_day = context.previous_date
    today = context.current_dt.date()
    # 用中证全指 + 主板宽口径池子, 排除 ST/科创/创业/北交/次新
    universe = _get_universe(context)
    if not universe:
        return []
    n = g.emotion_lookback_days + 2
    try:
        df = get_price(universe, end_date=y_day, frequency='1d',
                       fields=['close', 'open', 'high', 'low', 'volume',
                               'money', 'high_limit', 'pre_close'],
                       count=n, panel=False, skip_paused=True, fq='pre')
    except Exception as e:
        log.warn(f"[情绪] 取价失败: {e}")
        return []
    if df is None or df.empty:
        return []
    # 取流通市值用于计算换手率
    try:
        fund = get_fundamentals(query(
            valuation.code, valuation.circulating_market_cap, valuation.turnover_ratio
        ).filter(valuation.code.in_(universe)), date=y_day)
        if fund is not None and not fund.empty:
            cap_map = dict(zip(fund.code, fund.circulating_market_cap))
            tr_map = dict(zip(fund.code, fund.turnover_ratio / 100.0))
        else:
            cap_map, tr_map = {}, {}
    except Exception:
        cap_map, tr_map = {}, {}

    rows = []
    for code, grp in df.groupby('code'):
        grp_s = grp.sort_values('time').reset_index(drop=True)
        if len(grp_s) < g.emotion_lookback_days + 1:
            continue
        close = grp_s['close'].values
        hi_lim = grp_s['high_limit'].values
        pre_c = grp_s['pre_close'].values
        # 计算近 N 日涨停板数 (close >= high_limit * 0.998)
        recent = grp_s.iloc[-g.emotion_lookback_days:]
        lu_mask = (recent['close'] >= recent['high_limit'] * 0.998).values
        n_lu = int(lu_mask.sum())
        if n_lu < g.emotion_min_limit_ups:
            continue
        # 近 N 日累涨
        if close[-g.emotion_lookback_days - 1] <= 0:
            continue
        recent_ret = close[-1] / close[-g.emotion_lookback_days - 1] - 1
        if recent_ret < g.emotion_min_recent_gain or recent_ret > g.emotion_max_recent_gain:
            continue
        # 昨日换手率 (实盘可直接取 turnover_ratio; 这里用全局 tr_map 备份)
        tr_y = tr_map.get(code, 0.0)
        # 也用日 volume / 流通股数估算, 但 tr_map 已经基本可用
        if tr_y < g.emotion_min_turnover:
            continue
        # 昨日是否涨停 — 涨停后第二天反而最容易"首次分歧"; 也允许昨日未涨停 (高位震荡)
        last_lu = bool(lu_mask[-1])
        # 昨日"未一字" — 一字板没法买入次日开盘也容易高开, 我们要昨日有过开板/震荡才算分歧
        # 简化: 若昨日 high == low (一字板) 跳过
        y_high = grp_s['high'].iloc[-1]
        y_low = grp_s['low'].iloc[-1]
        if y_high == y_low:
            continue
        # 流通市值 范围 (A: V2 默认 30~150 亿)
        cap = cap_map.get(code, 0)
        if cap <= 0 or cap < g.emotion_cap_min or cap > g.emotion_cap_max:
            continue
        # 综合评分: 连扳数 × 0.6 + (涨幅 越接近 60% 越好) × 0.4
        gain_score = 1.0 - abs(recent_ret - 0.6) / 0.8
        score = n_lu * 0.6 + max(0.0, gain_score) * 0.4 + (0.2 if last_lu else 0.0)
        rows.append({'code': code, 'score': score, 'n_lu': n_lu,
                     'recent_ret': recent_ret, 'tr_y': tr_y, 'last_lu': last_lu,
                     'cap': cap})
    rows.sort(key=lambda r: r['score'], reverse=True)
    return rows


def emotion_leader_scan(context):
    """09:40 扫描 + 介入. 若已持情绪票, 跳过. 检查首次分歧开盘条件."""
    if not getattr(g, 'emotion_enable', False):
        return
    # C: 风格闸门 — FROZEN/仓位=0 不入入
    if g.emotion_cash_ratio <= 0 or g.market_phase == 'FROZEN':
        return
    state = g.emotion_state
    today = context.current_dt.date()
    # 冷静期
    if state.get('last_exit') and (today - state['last_exit']).days < g.emotion_cooldown_days:
        return
    # 已持有则跳过
    if state.get('code'):
        pos = context.portfolio.positions.get(state['code'])
        if pos and pos.total_amount > 0:
            return
        # 状态残留, 清空
        g.emotion_state['code'] = None

    candidates = _scan_emotion_candidates(context)
    if not candidates:
        return
    cur_data = get_current_data()
    picked = None
    for cand in candidates[:10]:
        code = cand['code']
        cd = cur_data[code]
        if cd.paused or cd.is_st:
            continue
        cp = cd.last_price
        op = cd.day_open
        if cp <= 0 or op <= 0 or pre_close_zero(cd):
            continue
        # 首次分歧: 开盘 in [-3%, +3%]
        open_ret = (op - cd.last_price) if False else 0  # 占位
        # 用 pre_close 计算昨收基础涨幅
        try:
            yc = attribute_history(code, 1, '1d', ['close']).iloc[-1, 0]
        except Exception:
            continue
        if yc <= 0:
            continue
        op_pct = op / yc - 1
        cur_pct = cp / yc - 1
        if not (g.emotion_div_open_low <= op_pct <= g.emotion_div_open_high):
            continue
        if not (g.emotion_div_morning_low <= cur_pct <= g.emotion_div_morning_high):
            continue
        # 不在涨停 / 跌停
        if pd.notna(cd.high_limit) and cp >= cd.high_limit * 0.998:
            continue
        if pd.notna(cd.low_limit) and cp <= cd.low_limit * 1.002:
            continue
        picked = (code, cand, cp, op_pct, cur_pct, yc)
        break
    if not picked:
        return
    code, cand, cp, op_pct, cur_pct, yc = picked
    # 仓位计算
    target_value = context.portfolio.total_value * g.emotion_cash_ratio
    cash_avail = context.portfolio.available_cash
    target_value = min(target_value, cash_avail * 0.95)
    if target_value < 3000:
        return
    target_shares = int(target_value / cp / 100) * 100
    if target_shares < 100:
        return
    try:
        order(code, target_shares)
        g.emotion_state = {'code': code, 'entry_date': today, 'entry_price': cp,
                           'day_high': cp,
                           'last_exit': g.emotion_state.get('last_exit')}
        log.info(f"[情绪买] {_format(code)} {target_shares}股 @ {cp:.2f} "
                 f"连扳={cand['n_lu']} 10d涨={cand['recent_ret']:.0%} "
                 f"开盘={op_pct:.2%} 现={cur_pct:.2%}")
    except Exception as e:
        log.warn(f"[情绪买失败] {code} {e}")


def pre_close_zero(cd):
    try:
        return cd.pre_close is None or cd.pre_close <= 0
    except Exception:
        return False


def emotion_leader_exit(context):
    """14:55 检查情绪龙头退潮: 放量阴线 / 止盈 / 止损 / 到期."""
    if not getattr(g, 'emotion_enable', False):
        return
    state = g.emotion_state
    code = state.get('code')
    if not code:
        return
    pos = context.portfolio.positions.get(code)
    if not pos or pos.total_amount <= 0:
        g.emotion_state['code'] = None
        return
    today = context.current_dt.date()
    cur = get_current_data()[code]
    cp = cur.last_price
    if cp <= 0:
        return
    ep = state.get('entry_price', pos.avg_cost) or pos.avg_cost
    ret = (cp - ep) / ep if ep > 0 else 0
    # 更新当日高点
    state['day_high'] = max(state.get('day_high', cp), cp)
    days_held = (today - state['entry_date']).days if state.get('entry_date') else 99
    # 当日涨跌幅 / 放量识别
    try:
        hist = attribute_history(code, 6, '1d', ['close', 'volume'])
    except Exception:
        hist = None
    day_pct = 0.0
    vol_ratio = 0.0
    if hist is not None and len(hist) >= 2:
        yc = hist['close'].iloc[-1]
        if yc > 0:
            day_pct = cp / yc - 1
        if len(hist) >= 6:
            ma_vol = hist['volume'].iloc[-5:].mean()
            # 当日 volume 用 minute 数据估算太重, 这里粗略用最新一根 volume
            try:
                v_today = attribute_history(code, 1, '1d', ['volume']).iloc[-1, 0]
            except Exception:
                v_today = 0
            if ma_vol > 0 and v_today > 0:
                vol_ratio = v_today / ma_vol
    # 涨停不卖
    if pd.notna(cur.high_limit) and cp >= cur.high_limit * 0.998:
        return
    reason = ''
    if ret >= g.emotion_take_profit:
        reason = f'情绪止盈{ret:.2%}'
    elif ret <= g.emotion_stop_loss:
        reason = f'情绪止损{ret:.2%}'
    elif days_held <= 1 and day_pct <= g.emotion_intraday_kill:
        reason = f'首日深阴强平 日跌{day_pct:.2%}'
    elif day_pct <= g.emotion_distribution_drop and vol_ratio >= g.emotion_distribution_vol:
        reason = f'放量退潮 日跌{day_pct:.2%} 量比{vol_ratio:.2f}'
    elif days_held >= g.emotion_hold_max_days:
        reason = f'情绪到期{ret:.2%}'
    elif g.market_phase in ('CHILL', 'FROZEN') and days_held >= 1:
        reason = f'风格转弱({g.market_phase}) {ret:.2%}'
    if reason:
        order_target_value(code, 0)
        log.info(f"[情绪卖] {_format(code)} {reason}")
        g.emotion_state = {'code': None, 'entry_date': None, 'entry_price': 0.0,
                           'day_high': 0.0, 'last_exit': today}


# ============================== ETF 轮动 ==============================
def _etf_score(context, etf):
    try:
        prices = attribute_history(etf, g.etf_lookback + 5, '1d', ['close'])
    except Exception:
        return None
    if prices is None or len(prices) < g.etf_lookback + 1:
        return None
    close = prices['close'].values
    cur = get_current_data()[etf].last_price
    if cur and cur > 0:
        close = np.append(close, cur)
    if len(close) >= 4:
        for i in (-2, -3, -4):
            if close[i] > 0 and close[i+1] / close[i] < g.etf_loss_floor:
                return None
    y = np.log(close[-(g.etf_lookback + 1):])
    x = np.arange(len(y))
    w = np.linspace(1, 2, len(y))
    try:
        slope, intercept = np.polyfit(x, y, 1, w=w)
    except Exception:
        return None
    ann = math.exp(slope * 250) - 1
    ss_res = np.sum(w * (y - (slope * x + intercept)) ** 2)
    ss_tot = np.sum(w * (y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 1e-9 else 0
    if len(close) > g.etf_short_lookback:
        ret_s = close[-1] / close[-(g.etf_short_lookback + 1)] - 1
        if ret_s < 0:
            return None
    return {'etf': etf, 'ann': ann, 'r2': r2, 'score': ann * r2}


def _rank_etfs(context):
    today = context.current_dt.date()
    if g.etf_rank_cache.get('date') == today and g.etf_rank_cache.get('data') is not None:
        return g.etf_rank_cache['data']
    c_data = get_current_data()
    ranked = []
    for etf in g.etf_pool:
        try:
            if c_data[etf].paused:
                continue
        except Exception:
            continue
        m = _etf_score(context, etf)
        if m and m['score'] > g.etf_min_score:
            ranked.append(m)
    ranked.sort(key=lambda x: x['score'], reverse=True)
    g.etf_rank_cache = {'date': today, 'data': ranked}
    return ranked


def _smart_etf_order(context, etf, target_value):
    c_data = get_current_data()
    try:
        cd = c_data[etf]
    except Exception:
        return False
    if cd.paused or cd.last_price <= 0:
        return False
    pos = context.portfolio.positions.get(etf)
    cur_val = pos.value if pos and pos.total_amount > 0 else 0
    if target_value > 0:
        shares = int(target_value / cd.last_price / 100) * 100
        if shares < 100:
            return False
        if pd.notna(cd.high_limit) and cd.high_limit > 0 and cd.last_price >= cd.high_limit:
            return False
        if abs(cur_val - target_value) < max(g.etf_min_money, target_value * g.etf_rebalance_tolerance):
            return False
        # 使用 order_target 按股数下单, 避免«开仓<100»错误
        o = order_target(etf, shares)
        return o is not None
    else:
        if pd.notna(cd.low_limit) and cd.low_limit > 0 and cd.last_price <= cd.low_limit:
            return False
        if cur_val <= 0:
            return False
        o = order_target(etf, 0)
        return o is not None


def etf_rebalance(context):
    ranked = _rank_etfs(context)
    # Sleeve C 反弹 ETF 不计入 ETF sleeve 持仓决策
    rebound_active = getattr(g, 'rebound_state', {}).get('active', False)
    rebound_etf = getattr(g, 'rebound_etf', None)
    current_etfs = [s for s, p in context.portfolio.positions.items()
                    if p.total_amount > 0 and _is_etf(s)
                    and not (rebound_active and s == rebound_etf)]
    n = g.etf_holdings_num
    if not ranked:
        target_list = [g.etf_defensive]
    else:
        score_map = {m['etf']: m['score'] for m in ranked}
        default_top = [m['etf'] for m in ranked[:n]]
        default_min_score = min(score_map[e] for e in default_top)
        margin = getattr(g, 'etf_switch_margin', 0.0)
        # 黏性: 当前持仓若仍在 ranked 内且其 score >= default_min_score * (1 - margin), 优先保留
        sticky_threshold = default_min_score * (1.0 - margin) if default_min_score > 0 \
                           else default_min_score - abs(default_min_score) * margin
        kept = [e for e in current_etfs
                if e in score_map and score_map[e] >= sticky_threshold]
        kept = kept[:n]
        target_list = list(kept)
        for m in ranked:
            if len(target_list) >= n:
                break
            if m['etf'] not in target_list:
                target_list.append(m['etf'])
    target_set = set(target_list)
    total = context.portfolio.total_value
    sleeve_val = total * g.sleeve_ratio['etf']
    if rebound_active and rebound_etf:
        rb_pos = context.portfolio.positions.get(rebound_etf)
        if rb_pos is not None:
            sleeve_val = max(0.0, sleeve_val - rb_pos.value)

    for s in current_etfs:
        if s not in target_set:
            if _smart_etf_order(context, s, 0):
                log.info(f"[ETF卖] {_format(s)}")

    per = sleeve_val / float(len(target_list)) if target_list else 0
    for etf in target_list:
        if rebound_active and etf == rebound_etf:
            continue
        if _smart_etf_order(context, etf, per):
            log.info(f"[ETF调] {_format(etf)} 目标={per:.0f}")


# ============================== 收盘清理 ==============================
def after_close(context):
    cur = set(context.portfolio.positions.keys())
    g.trend_meta = {k: v for k, v in g.trend_meta.items() if k in cur}
    em_code = g.emotion_state.get('code') if hasattr(g, 'emotion_state') else None
    holds_t = [s for s in cur if not _is_etf(s) and s != em_code]
    holds_e = [s for s in cur if _is_etf(s)]
    holds_em = [s for s in cur if s == em_code]
    log.info(f"[收盘] 总值={context.portfolio.total_value:.0f} "
             f"趋势={[_format(s) for s in holds_t]} ETF={holds_e} "
             f"情绪={[_format(s) for s in holds_em]}")
