# Clone from JoinQuant
# postId: a0b7e6ebf82aa3446c23ade7e896ef8e
# backtestId: 0199ef76b781357d889b21c6d912a1cb
# title: 新框架-欢迎魔改主力资金确认短线埋伏可接外部新闻聚合AI分析

# -*- coding: utf-8 -*-
"""
聚宽策略：AI 热点板块 + 主力资金确认 + 短线埋伏
============================================================
核心逻辑
  1. 盘前：识别当日热点板块
     - 回测：板块动量(3/5日涨幅) + 板块资金净流入 + 涨停家数 三因子打分
     - 实盘：可接入外部"新闻聚合 + 大模型情绪分析"服务（见 fetch_ai_hot_sectors）
  2. 选股：热点板块内按"爆发潜力分"排序
     - 短期动量、量比、主力净流入、非连板且未触及涨停
  3. 埋伏 1-2 天
     - T日买入；T+1 盘中 14:30 检查主力资金是否净流入 > 阈值
         - 未确认：T+1 尾盘清仓
         - 已确认：延长到 T+2，同样判断
  4. 止盈止损
     - 硬止损：-5%
     - 触发式移动止盈：盈利 >=7% 后，从最高点回撤 3% 止盈
============================================================
"""

import numpy as np
import pandas as pd
from jqdata import *
from jqfactor import get_factor_values


# ----------------------------- 初始化 ----------------------------- #
def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_order_cost(
        OrderCost(close_tax=0.0005, open_commission=0.0001,
                  close_commission=0.0001, min_commission=1),
        type='stock'
    )
    log.set_level('order', 'error')

    # ---------- 策略参数 ----------
    g.max_positions          = 5          # 最大持仓数
    g.position_pct           = 0.18       # 单票目标仓位
    g.hold_days_max          = 2          # 最长持仓天数
    g.stop_loss              = -0.05      # 硬止损
    g.stop_profit_trigger    = 0.07       # 触发移动止盈
    g.trailing_drawdown      = 0.03       # 最高点回撤幅度止盈
    g.main_fund_threshold    = 5_000_000  # 主力净流入阈值（元）
    g.hot_sector_top_n       = 3          # 取前 N 个热点板块
    g.candidates_per_sector  = 3          # 每个板块候选数
    g.min_market_cap         = 30e8       # 最小市值
    g.max_market_cap         = 500e8      # 最大市值（避免大盘股）

    # ---------- 状态容器 ----------
    # position_info[stock] = {
    #   'buy_date', 'buy_price', 'high_after_buy',
    #   'main_fund_confirmed', 'hold_days'
    # }
    g.position_info = {}
    g.hot_sectors = []     # 当日热点板块代码列表
    g.today_candidates = []

    # ---------- 外部 AI/新闻服务（实盘可开） ----------
    g.use_external_ai   = False
    g.news_api_endpoint = ''   # 自建新闻聚合服务
    g.ai_api_endpoint   = ''   # 大模型情绪分析服务

    # ---------- 调度 ----------
    run_daily(pre_market_analysis, time='09:05', reference_security='000300.XSHG')
    run_daily(buy_candidates,      time='09:35', reference_security='000300.XSHG')
    run_daily(intraday_risk_check, time='10:30', reference_security='000300.XSHG')
    run_daily(intraday_risk_check, time='13:30', reference_security='000300.XSHG')
    run_daily(main_fund_check,     time='14:30', reference_security='000300.XSHG')
    run_daily(end_of_day_exit,     time='14:50', reference_security='000300.XSHG')


def before_trading_start(context):
    # 清理已不持仓的状态
    held = set(context.portfolio.positions.keys())
    for s in list(g.position_info.keys()):
        if s not in held:
            del g.position_info[s]
    # 持仓天数 +1
    for s in g.position_info:
        g.position_info[s]['hold_days'] = g.position_info[s].get('hold_days', 0) + 1


# =========================================================
# 1. 热点板块识别
# =========================================================
def pre_market_analysis(context):
    """盘前识别热点板块，AI 优先，失败回退到技术面。
    注意：09:05 时当日行情不可得，所有数据以"上一交易日"为准。
    """
    today = context.current_dt.date()
    prev_td = get_trade_days(end_date=today, count=2)[0]  # 上一交易日

    sectors = None
    if g.use_external_ai and g.ai_api_endpoint:
        try:
            sectors = fetch_ai_hot_sectors(today)
        except Exception as e:
            log.warn('AI 热点获取失败，回退技术面: %s' % e)

    if not sectors:
        sectors = detect_hot_sectors_by_technical(prev_td)

    g.hot_sectors = sectors[:g.hot_sector_top_n]
    log.info('今日热点板块(基于 %s): %s' % (prev_td, g.hot_sectors))

    # 选股也基于上一交易日
    g.today_candidates = pick_candidates(context, g.hot_sectors, prev_td)
    log.info('候选股: %s' % g.today_candidates)


def fetch_ai_hot_sectors(date):
    """实盘外接：新闻聚合 + 大模型情绪分析，返回按发酵空间排序的板块代码列表。

    期望外部服务返回 JSON:
      [{"sector_code": "801780", "sector_name": "银行", "score": 0.87, "reason": "..."}]

    回测环境禁网，此函数只在 use_external_ai=True 的实盘下生效。
    """
    import requests
    resp = requests.post(
        g.ai_api_endpoint,
        json={'date': str(date), 'top_k': 10},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return [item['sector_code'] for item in sorted(data, key=lambda x: -x['score'])]


def detect_hot_sectors_by_technical(date):
    """技术面代理：板块动量 + 资金流 + 涨停家数三因子打分。"""
    industries = get_industries(name='sw_l1').index.tolist()
    end = date
    start_5 = end - pd.Timedelta(days=10)  # 取 10 日自然日以保证 5 个交易日

    scores = []
    for ind in industries:
        try:
            stocks = get_industry_stocks(ind, date=end)
            if len(stocks) < 5:
                continue

            # --- 因子1: 板块 3/5 日动量 ---
            px = get_price(stocks, end_date=end, count=6, frequency='daily',
                           fields=['close'], panel=False)
            if px.empty:
                continue
            px = px.pivot(index='time', columns='code', values='close').dropna(axis=1)
            if px.shape[0] < 6 or px.shape[1] == 0:
                continue
            ret_3 = (px.iloc[-1] / px.iloc[-4] - 1).mean()
            ret_5 = (px.iloc[-1] / px.iloc[0] - 1).mean()

            # --- 因子2: 板块主力净流入（近3日均值） ---
            mf = get_money_flow(stocks, end_date=end, count=3,
                                fields=['sec_code', 'date', 'net_amount_main'])
            mf_score = mf['net_amount_main'].mean() if not mf.empty else 0

            # --- 因子3: 涨停家数 ---
            last_close = px.iloc[-1]
            prev_close = px.iloc[-2]
            limit_up_count = ((last_close / prev_close - 1) > 0.095).sum()

            # 标准化打分
            score = (
                ret_3 * 40 +
                ret_5 * 20 +
                (mf_score / 1e8) * 0.3 +
                limit_up_count * 0.5
            )
            scores.append((ind, score))
        except Exception as e:
            log.info('板块 %s 跳过: %s' % (ind, e))
            continue

    scores.sort(key=lambda x: -x[1])
    return [s[0] for s in scores[:g.hot_sector_top_n * 2]]  # 多返回一些做储备


# =========================================================
# 2. 选股
# =========================================================
def pick_candidates(context, sectors, date=None):
    """从热点板块中挑选爆发潜力个股。date 默认取上一交易日。"""
    if date is None:
        today = context.current_dt.date()
        date = get_trade_days(end_date=today, count=2)[0]
    all_candidates = []

    for sec in sectors:
        try:
            stocks = get_industry_stocks(sec, date=date)
            stocks = filter_tradable(stocks, date)
            if not stocks:
                continue

            # 基本面/市值过滤
            fdmt = get_fundamentals(
                query(valuation.code, valuation.market_cap)
                .filter(valuation.code.in_(stocks)),
                date=date,
            )
            fdmt = fdmt[
                (fdmt['market_cap'] * 1e8 >= g.min_market_cap) &
                (fdmt['market_cap'] * 1e8 <= g.max_market_cap)
            ]
            stocks = fdmt['code'].tolist()
            if not stocks:
                continue

            # 打分
            scored = score_stocks(stocks, date)
            scored = scored.sort_values('score', ascending=False)
            all_candidates.extend(scored.head(g.candidates_per_sector)['code'].tolist())
        except Exception as e:
            log.warn('板块 %s 选股异常: %s' % (sec, e))

    # 去重，限制总数
    seen, result = set(), []
    for s in all_candidates:
        if s not in seen:
            seen.add(s)
            result.append(s)
        if len(result) >= g.max_positions * 2:
            break
    return result


def score_stocks(stocks, date):
    """个股爆发潜力打分：动量 + 量比 + 主力净流入。"""
    px = get_price(stocks, end_date=date, count=6, frequency='daily',
                   fields=['close', 'volume'], panel=False)
    if px.empty:
        return pd.DataFrame(columns=['code', 'score'])
    close = px.pivot(index='time', columns='code', values='close').dropna(axis=1)
    vol   = px.pivot(index='time', columns='code', values='volume').dropna(axis=1)
    common = close.columns.intersection(vol.columns)
    close, vol = close[common], vol[common]
    if close.shape[0] < 6:
        return pd.DataFrame(columns=['code', 'score'])

    ret3 = close.iloc[-1] / close.iloc[-4] - 1
    vol_ratio = vol.iloc[-1] / vol.iloc[:-1].mean()

    mf = get_money_flow(list(common), end_date=date, count=3,
                        fields=['sec_code', 'net_amount_main'])
    mf_mean = mf.groupby('sec_code')['net_amount_main'].mean() if not mf.empty else pd.Series(dtype=float)

    df = pd.DataFrame({
        'ret3': ret3,
        'vol_ratio': vol_ratio,
        'main_fund': mf_mean.reindex(common).fillna(0),
    })
    # 排除已经连板或处于高位过热的票
    df = df[df['ret3'] < 0.20]
    df['score'] = (
        df['ret3'].rank(pct=True) * 0.4 +
        df['vol_ratio'].rank(pct=True) * 0.3 +
        df['main_fund'].rank(pct=True) * 0.3
    )
    df = df.reset_index().rename(columns={'index': 'code'})
    return df[['code', 'score']]


def filter_tradable(stocks, date):
    """过滤 ST / 停牌 / 次新 / 今日涨停或一字板不可买。"""
    stocks = [s for s in stocks if not (s.startswith('68') or s.startswith('30'))]  # 可按需保留创业板
    st = get_extras('is_st', stocks, start_date=date, end_date=date, df=True)
    stocks = [s for s in stocks if s in st.columns and not st.iloc[-1][s]]
    # 上市满 60 天
    stocks = [s for s in stocks
              if (date - get_security_info(s).start_date).days > 60]
    # 非停牌
    paused = get_price(stocks, end_date=date, count=1, fields=['paused'], panel=False)
    if not paused.empty:
        paused = paused.pivot(index='time', columns='code', values='paused')
        stocks = [s for s in stocks if s in paused.columns and paused.iloc[-1][s] == 0]
    return stocks


# =========================================================
# 3. 买入
# =========================================================
def buy_candidates(context):
    """09:35 埋伏买入。"""
    available_slots = g.max_positions - len(context.portfolio.positions)
    if available_slots <= 0 or not g.today_candidates:
        return

    cash_per = context.portfolio.total_value * g.position_pct
    current_prices = get_current_data()

    for stock in g.today_candidates:
        if available_slots <= 0:
            break
        if stock in context.portfolio.positions:
            continue

        cd = current_prices[stock]
        # 涨停/一字板不追
        if cd.last_price >= cd.high_limit * 0.995:
            continue
        # 跌停不接
        if cd.last_price <= cd.low_limit * 1.005:
            continue
        # 开盘大涨幅 >5% 不追
        if cd.day_open > 0 and cd.last_price / cd.day_open - 1 > 0.05:
            continue

        order_value(stock, cash_per)
        pos = context.portfolio.positions.get(stock)
        if pos and pos.total_amount > 0:
            g.position_info[stock] = {
                'buy_date': context.current_dt.date(),
                'buy_price': pos.avg_cost,
                'high_after_buy': pos.avg_cost,
                'main_fund_confirmed': False,
                'hold_days': 0,
            }
            available_slots -= 1
            log.info('买入 %s @ %.2f' % (stock, pos.avg_cost))


# =========================================================
# 4. 风控：止盈止损
# =========================================================
def intraday_risk_check(context):
    """盘中止盈止损巡检。"""
    cd = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.total_amount == 0:
            continue
        info = g.position_info.get(stock)
        if not info:
            continue

        price = cd[stock].last_price
        info['high_after_buy'] = max(info['high_after_buy'], price)

        ret = price / info['buy_price'] - 1
        # 硬止损
        if ret <= g.stop_loss:
            close_position(stock, '止损')
            continue
        # 触发式移动止盈
        if info['high_after_buy'] / info['buy_price'] - 1 >= g.stop_profit_trigger:
            drawdown = price / info['high_after_buy'] - 1
            if drawdown <= -g.trailing_drawdown:
                close_position(stock, '移动止盈')


# =========================================================
# 5. 主力资金确认（盘中仅用分钟大单代理）
# =========================================================
def main_fund_check(context):
    """14:30 主力资金确认。
    聚宽无 L2，且 get_money_flow 只能 15:00 之后取，
    所以盘中仅使用"分钟阳线大单"代理：
      当日 1 分钟 bar 中 成交额 >= big_bar_money 且 close > open，
      这些分钟成交额累计 >= big_up_threshold 视为主力确认。
    """
    now = context.current_dt
    stocks = list(context.portfolio.positions.keys())
    if not stocks:
        return

    big_bar_money    = 5_000_000   # 单分钟成交额门槛（元）
    big_up_threshold = 2e7         # 阳线大单累计门槛（元）

    today_open = now.replace(hour=9, minute=30, second=0, microsecond=0)

    for s in stocks:
        info = g.position_info.get(s)
        if not info:
            continue
        try:
            bars = get_price(
                s, start_date=today_open, end_date=now,
                frequency='1m', fields=['open', 'close', 'money'],
                skip_paused=True, panel=False,
            )
        except Exception as e:
            log.info('%s 分钟数据获取失败: %s' % (s, e))
            continue

        if bars is None or bars.empty:
            continue

        big = bars[(bars['money'] >= big_bar_money) &
                   (bars['close'] > bars['open'])]
        big_up = float(big['money'].sum())

        if big_up >= big_up_threshold and not info['main_fund_confirmed']:
            log.info('%s 主力确认：阳线大单累计 %.0f 万' % (s, big_up / 1e4))
        if big_up >= big_up_threshold:
            info['main_fund_confirmed'] = True


# =========================================================
# 6. 日终：根据确认情况 + 持仓天数决定去留
# =========================================================
def end_of_day_exit(context):
    """14:50 清理：主力未确认的 T+1 清仓；持仓超 hold_days_max 一律清。"""
    for stock in list(context.portfolio.positions.keys()):
        info = g.position_info.get(stock)
        if not info:
            continue
        hold_days = info['hold_days']

        # 超出最大持仓天数，无条件清
        if hold_days >= g.hold_days_max:
            close_position(stock, '到期')
            continue

        # 持仓满 1 天（即 T+1 尾盘）仍未被主力确认：清
        if hold_days >= 1 and not info['main_fund_confirmed']:
            close_position(stock, '主力未进场')
            continue


# =========================================================
# 工具函数
# =========================================================
def close_position(stock, reason):
    if stock in g.position_info:
        pos = get_current_data()[stock]
        order_target(stock, 0)
        log.info('清仓 %s 原因=%s 现价=%.2f' % (stock, reason, pos.last_price))
        g.position_info.pop(stock, None)
