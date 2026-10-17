# Clone from JoinQuant
# postId: 9f286ad2417f802d05eaddfa002d9a3b
# backtestId: d1bddf67efb855b9139e68660997e618
# title: 冰点分批买入持有思路必定赚钱对吗？

# ============ 冰点买入·持有不动（极简版）============
# 理念：相信市场长期向上，不做任何择时卖出。热度冰点（市场极度恐慌）= 打折买入机会。
# 规则（全部T日after_close算热度 → T+1 open执行，防未来函数）：
#   1. 每日收盘算"创业板成分股热度因子"（与v11同源：量能/价格/广度/情绪7维分位，0-100）
#   2. 热度 < ICE_HEAT(20) 且 上一交易日不在冰点（即一波冰点只在"首次跌入"当天买一次）
#      → 买入 初始资金 × BUY_PCT(10%) 仓位的 TARGET
#   3. 最多买 MAX_BUYS(10) 次，买满即停；现金不足则跳过
#   4. 永不卖出、不设止盈止损、不看年线、不轮动
#
# 标的：默认 159915 创业板ETF。若想更贴合"全市场长期向上"，可改为：
#       510300.XSHG 沪深300ETF / 588000.XSHG 科创50ETF（热度池仍用创业板池，仅换买入标的；
#       若要热度池也换宽基，把 POOL_NAME 一并改成对应池——当前仅创业板池配置完整）。
#
# 回测建议：2021-01 至今，基准沪深300，初始资金10万+（ETF万3佣金、最低5元）。
# 注意：热度因子需约250个交易日预热，回测第1年信号不稳定属正常。
# ======================================================

import numpy as np
import pandas as pd
import datetime

# ---------------- 可调参数 ----------------
TARGET   = '159915.XSHE'   # 买入标的：创业板ETF
POOL_NAME = '创业板'        # 热度计算池（与标的风格匹配）
ICE_HEAT = 20              # 冰点阈值：热度<20
BUY_PCT  = 0.10            # 每次买入占【初始资金】的比例（10%）
MAX_BUYS = 10              # 最多买入次数（10次→满仓）
LOOKBACK = 300
PCT_WIN, MIN_PCT = 250, 60
MA_SHORT, MA_LONG = 20, 60

# 热度计算池（与v11一致）
POOLS = {
    '创业板': {'prefixes': ('300', '301'), 'index': '399006.XSHE', 'limit_pct': 0.195},
    '科创板': {'prefixes': ('688',),        'index': '000688.XSHG', 'limit_pct': 0.195},
}
WEIGHTS = {'money_pct': 20, 'volratio_pct': 15, 'mom20_pct': 20, 'bias60_pct': 10,
           'up_pct': 15, 'abovema_pct': 10, 'lu_pct': 10}
COL_OF = {'money_pct': 'money', 'volratio_pct': 'vol_ratio', 'mom20_pct': 'mom20',
          'bias60_pct': 'bias60', 'up_pct': 'up_ratio',
          'abovema_pct': 'above_ratio', 'lu_pct': 'limit_up'}


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0003,
                             close_commission=0.0003, close_today_commission=0,
                             min_commission=5), type='fund')

    g.init_cash = context.portfolio.total_value   # 初始资金（买入金额基准）
    g.buy_count = 0          # 已买入次数
    g.prev_ice = False       # 上一交易日是否处于冰点（用于"首次跌入"判定）
    g.pending = False        # T日收盘挂出的买入意图，T+1开盘执行

    g.close, g.volume, g.money, g.idx = {}, {}, {}, {}
    g.metrics, g.stocks = {}, {}

    run_daily(trade, time='open')
    run_daily(daily_heat, time='after_close')


# ---------------- 热度因子（与v11同源） ----------------
def _stock_list(cfg, date):
    prefixes = cfg.get('prefixes', ())
    df = get_all_securities(types=['stock'], date=date)
    cutoff = pd.Timestamp(date).date() - datetime.timedelta(days=90)
    stocks = [c for c in df.index
              if c.startswith(prefixes)
              and pd.Timestamp(df.loc[c, 'start_date']).date() <= cutoff]
    if len(stocks) == 0:
        stocks = [c for c in df.index if c.startswith(prefixes)]
    return stocks


def _fetch(stocks, start, end, chunk_size=300):
    frames = []
    for i in range(0, len(stocks), chunk_size):
        chunk = stocks[i:i + chunk_size]
        try:
            d = get_price(chunk, start_date=start, end_date=end, frequency='daily',
                          fields=['close', 'volume', 'money'], fq=None,
                          panel=False, skip_paused=False)
            if d is not None and len(d):
                frames.append(d)
        except Exception as e:
            log.warn('取数异常(%d只)：%s' % (len(chunk), e))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _calc_all(c, v, m, idx, limit_pct=0.195):
    traded = v > 0
    n_traded = traded.sum(axis=1).replace(0, np.nan)
    pct = c.pct_change()
    money = m.where(traded).sum(axis=1)
    if money.notna().sum() < MIN_PCT or (money.dropna() <= 0).all():
        money = (c * v).where(traded).sum(axis=1)
    if idx.notna().sum() < MIN_PCT:
        idx = c.where(traded).mean(axis=1)
    up = (pct.where(traded) > 0).sum(axis=1) / n_traded
    above = (c > c.rolling(MA_SHORT).mean()).where(traded).sum(axis=1) / n_traded
    lu = ((pct >= limit_pct - 0.005) & (pct <= limit_pct + 0.015) & traded).sum(axis=1)
    vr = money / money.rolling(MA_SHORT).mean()
    mom = idx / idx.shift(MA_SHORT) - 1
    bias = idx / idx.rolling(MA_LONG).mean() - 1
    return pd.DataFrame({'money': money, 'up_ratio': up, 'above_ratio': above,
                         'limit_up': lu, 'vol_ratio': vr, 'mom20': mom, 'bias60': bias})


def _heat(met):
    p = {}
    for k in WEIGHTS:
        s = met[COL_OF[k]].dropna().tail(PCT_WIN)
        if len(s) >= MIN_PCT:
            p[k] = (s <= s.iloc[-1]).mean()
        else:
            return np.nan
    return sum(p[k] * w for k, w in WEIGHTS.items())


# ---------------- 每日收盘：算热度，冰点挂买单 ----------------
def daily_heat(context):
    cfg = POOLS[POOL_NAME]
    end = context.current_dt.date()
    start = end - datetime.timedelta(days=LOOKBACK * 2)

    # 股票池（每日刷新，含新上市）
    try:
        stocks = _stock_list(cfg, end)
    except Exception as e:
        log.warn('股票池获取失败：%s' % e)
        stocks = g.stocks.get(POOL_NAME, [])
    g.stocks[POOL_NAME] = stocks

    bars = _fetch(stocks, start, end)
    if bars is None or len(bars) == 0:
        log.warn('热度数据不足，今日无操作')
        return
    tidx = sorted(bars['time'].unique())
    c = bars.pivot(index='time', columns='code', values='close').sort_index().reindex(tidx)
    v = bars.pivot(index='time', columns='code', values='volume').sort_index().reindex(tidx)
    m = bars.pivot(index='time', columns='code', values='money').sort_index().reindex(tidx)
    try:
        idx = get_price(cfg['index'], start_date=start, end_date=end,
                        frequency='daily', fields=['close'], fq=None)['close']
    except Exception:
        idx = pd.Series(dtype=float)

    met = _calc_all(c, v, m, idx, cfg['limit_pct']).tail(PCT_WIN + 10)
    heat = _heat(met)
    ts = tidx[-1]

    if pd.isna(heat):
        log.info('[热度] 数据不足，无操作')
        g.prev_ice = False
        return

    is_ice = heat < ICE_HEAT
    # 首次跌入冰点（上一交易日不在冰点）且还有买入额度 → 挂买单
    if is_ice and (not g.prev_ice) and g.buy_count < MAX_BUYS:
        g.pending = True
        g.buy_count += 1
        log.info('❄️ 冰点买入信号 #%d：热度%.1f<%d → 明日开盘买入 %.0f%% 初始资金（%s）'
                 % (g.buy_count, heat, ICE_HEAT, BUY_PCT * 100, TARGET))
    elif is_ice:
        if g.buy_count >= MAX_BUYS:
            log.info('❄️ 冰点(热度%.1f)但已买满%d次，不再加仓' % (heat, MAX_BUYS))
        else:
            log.info('❄️ 冰点持续中(热度%.1f)，同一波只买一次，等待' % heat)
    else:
        log.info('热度%.1f（%s），持有不动' % (heat, _zone(heat)))

    g.prev_ice = is_ice
    record(heat=heat)


def _zone(h):
    if h < 20:  return '冰点'
    if h < 40:  return '偏冷'
    if h < 60:  return '中性'
    if h < 80:  return '偏热'
    return '过热'


# ---------------- 次日开盘：执行买单 ----------------
def trade(context):
    if not g.pending:
        return
    g.pending = False

    target_value = g.init_cash * BUY_PCT
    cash = context.portfolio.available_cash
    if cash < target_value * 0.5:   # 现金不足（含最低佣金摩擦），跳过
        log.info('💰 现金不足(可用%.0f < 需%.0f)，本次买入跳过' % (cash, target_value))
        g.buy_count -= 1            # 未成交，不计入次数
        return

    order_value(TARGET, min(target_value, cash))
    pos = context.portfolio.positions.get(TARGET)
    held = pos.value if pos is not None else 0
    log.info('✅ 已买入 %s，金额约%.0f，累计持仓市值%.0f（第%d/10笔）'
             % (TARGET, min(target_value, cash), held, g.buy_count))
