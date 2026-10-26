# Clone from JoinQuant
# postId: 0b7e8583af8b615a1ff4b7c9c75767d9
# backtestId: 32041503b4fd73aff379cb8afe46eb9f
# title: 牛市衰减函数控仓策略-对比KAMA策略

from jqdata import *
import numpy as np

# ====================== 全局参数 ======================
def initialize(context):
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003, min_commission=5
    ), type='stock')

    g.max_hold = 4
    g.industry_limit = 2
    g.sold_today = set()
    g.decay_cnt = {}  # 每只股票连续衰减天数
    g.hold_info = {}
    g.peak_capital = context.portfolio.total_value
    g.attained_profit = False

    run_daily(sell_strategy, time='14:29:30')
    run_daily(buy_strategy, time='14:30:00')

# ====================== ✅ 核心：1:1复刻你的通达信「牛市衰减函数」 ======================
def get_decay_signal(stock):
    """
    完全对应你的通达信公式：
    收益修复率 > 80  → 衰减触发
    连续3天 → 清仓
    """
    try:
        df = attribute_history(stock, 60, '1d', ['low', 'close', 'high'], fq='post')
        if len(df) < 30:
            return False

        # === 1. 30日阶段起点（通达信：LLVBARS(L,30)）
        low_list = df['low'].values
        min_idx = np.argmin(low_list)
        phase_start_idx = len(df) - 1 - min_idx

        phase_start_price = df['close'].iloc[-phase_start_idx-1]
        current_close = df['close'].iloc[-1]

        # === 2. 阶段最高价
        high_phase = df['high'].iloc[-phase_start_idx-1:].max()

        # === 3. 涨幅 & 回撤
        rise_pct = (current_close - phase_start_price) / phase_start_price * 100
        retrace_pct = (high_phase - current_close) / high_phase * 100

        # === 4. 收益修复率（你的核心公式）
        if retrace_pct <= 0 or phase_start_idx <= 0:
            repair_rate = 99.0
        else:
            repair_rate = rise_pct / retrace_pct

        # === 5. 触发条件：收益修复率 > 80 且 收盘价>起点价
        trigger = (repair_rate > 80) and (current_close > phase_start_price)
        return trigger

    except:
        return False

# ====================== 卖出规则：完全按你的牛市衰减函数 ======================
def sell_strategy(context):
    g.sold_today.clear()
    holds = {}
    for s, p in context.portfolio.positions.items():
        if p.total_amount > 0:
            holds[s] = {
                'cost': p.avg_cost,
                'price': p.price,
                'amount': p.total_amount
            }
            if s not in g.decay_cnt:
                g.decay_cnt[s] = 0

    for s in list(holds.keys()):
        cost = holds[s]['cost']
        price = holds[s]['price']
        amount = holds[s]['amount']
        if cost <= 0 or amount < 100:
            continue

        profit = (price - cost) / cost

        # --------------------------
        # 1. 更新连续衰减天数
        # --------------------------
        decay_today = get_decay_signal(s)
        if decay_today:
            g.decay_cnt[s] += 1
        else:
            g.decay_cnt[s] = 0  # 断一天 → 立刻重置

        cnt = g.decay_cnt[s]

        # --------------------------
        # 2. 安全兜底：盈利破10日线清仓
        # --------------------------
        if profit > 0:
            df = attribute_history(s, 15, '1d', ['close'], fq='post')
            if len(df) >= 10:
                ma10 = df['close'].rolling(10).mean().iloc[-1]
                if price < ma10:
                    order_target(s, 0)
                    g.sold_today.add(s)
                    g.hold_info.pop(s, None)
                    g.decay_cnt.pop(s, None)
                    log.info(f"【清仓】{s} 盈利跌破10日线")
                    continue

        # --------------------------
        # 3. 牛市衰减仓位控制
        # --------------------------
        if cnt == 0:
            # 无衰减 → 全仓不动
            continue

        elif cnt == 1:
            target = int(amount * 0.7 // 100 * 100)
            if target >= 100 and target < amount:
                order_target(s, target)
                log.info(f"【衰减1天】{s} → 7成仓")

        elif cnt == 2:
            target = int(amount * 0.49 // 100 * 100)
            if target >= 100 and target < amount:
                order_target(s, target)
                log.info(f"【衰减2天】{s} → 4.9成仓")

        elif cnt >= 3:
            order_target(s, 0)
            g.sold_today.add(s)
            g.hold_info.pop(s, None)
            g.decay_cnt.pop(s, None)
            log.info(f"【衰减3天→清仓】{s}")

# ====================== 买入逻辑（已修复BUG） ======================
def buy_strategy(context):
    holds = [s for s in context.portfolio.positions.keys()
             if context.portfolio.positions[s].total_amount > 0]
    if len(holds) >= g.max_hold:
        return

    ratio = 1.0
    cash = context.portfolio.total_value * 0.3 / g.max_hold * ratio
    dt = get_current_data()
    stocks = get_all_securities(['stock']).index.tolist()
    pool = []

    for s in stocks:
        if dt[s].paused or dt[s].is_st or '退' in dt[s].name:
            continue
        if s in holds or s in g.sold_today:
            continue
        if basic_filter(s) and check_buy_strong(s):
            pool.append(s)

    ind_cnt = {}
    for s in pool:
        if len(holds) >= g.max_hold:
            break
        try:
            ind = get_industry(s)
            ind = ind[next(iter(ind))]['industry_name'] if ind else '其他行业'
        except:
            ind = '其他行业'

        if ind not in ind_cnt:
            ind_cnt[ind] = 0
        if ind_cnt[ind] >= g.industry_limit:
            continue

        p = dt[s].last_price
        if p <= 0:
            continue
        vol = int(cash / p // 100 * 100)
        if vol < 100:
            continue

        order(s, vol)
        holds.append(s)
        ind_cnt[ind] += 1
        g.decay_cnt[s] = 0
        g.hold_info[s] = {'cost': p, 'amount': vol}
        log.info(f"【买入】{s}")

# ====================== 强势选股 ======================
def check_buy_strong(stock):
    try:
        df = attribute_history(stock, 60, '1d', ['open','close','high','low','volume'], fq='post')
        if len(df) < 30:
            return False

        close = df['close']
        high = df['high']
        vol = df['volume']

        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()

        trend_up = (ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1])
        hold_ma = (close.iloc[-1] > ma5.iloc[-1] > ma10.iloc[-1])
        new_high = high.iloc[-1] >= high.iloc[-20:].max() * 0.99
        vol_ok = vol.iloc[-1] > vol.rolling(5).mean().iloc[-1] * 1.1
        upward = close.iloc[-1] > close.iloc[-20]

        return all([trend_up, hold_ma, new_high, vol_ok, upward])
    except:
        return False

# ====================== 基本面过滤 ======================
def basic_filter(stock):
    try:
        q = query(valuation.code).filter(
            valuation.code == stock,
            valuation.circulating_market_cap.between(30, 800),
            valuation.pe_ratio > 0, valuation.pe_ratio < 50
        )
        return len(get_fundamentals(q)) > 0
    except:
        return False