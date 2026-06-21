# Clone from JoinQuant
# postId: b8a7451f9f7dd98789e3e98d565d244c
# backtestId: 84562ddd7bd018f1434f0b290a0a215c
# title: 首次将实战模型转化为量化策略年化468.07%&amp;11.92%

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003,
                             close_commission=0.0003, min_commission=5), type='stock')
    g.selected_stocks = []
    g.stock_info = {}
    run_daily(select_and_buy, time='09:30')
    run_daily(check_sell, time='09:31')
    run_daily(check_sell, time='14:50')

def get_today_open_daily(stock, today):
    try:
        df = get_price(stock, end_date=today, count=1,
                       frequency='daily', fields=['open'], fq='pre')
        if len(df) > 0:
            return df['open'].iloc[0]
    except:
        pass
    return None

def count_rolling(cond, window):
    s = pd.Series(cond)
    return s.rolling(window, min_periods=1).sum().values

def rolling_every(cond, window):
    s = pd.Series(cond)
    return s.rolling(window, min_periods=window).min().values == 1

def select_and_buy(context):
    yesterday = context.previous_date
    today = context.current_dt.date()
    stocks = get_all_securities(['stock']).index.tolist()
    t2_count = 0
    ta_count = 0
    tb_count = 0
    tjp1_count = 0
    tjdk_count = 0
    candidates = []

    for stock in stocks:
        today_open = get_today_open_daily(stock, today)
        if today_open is None or today_open <= 0:
            continue

        try:
            df = get_price(stock, end_date=yesterday, count=70,
                           frequency='daily', fields=['open','high','low','close','volume'], fq='pre')
            if len(df) < 60:
                continue
        except:
            continue

        c = df['close'].values
        h = df['high'].values
        l = df['low'].values
        o = df['open'].values
        v = df['volume'].values
        n = len(c) - 1
        if n < 10:
            continue

        code = stock[:6]
        if code.startswith('60') or code.startswith('00'):
            limit = 0.1
        elif code.startswith('30') or code.startswith('68'):
            limit = 0.2
        else:
            limit = 0.1
        fw = (code.startswith('00') or code.startswith('60')) or code.startswith('30')

        def ztj_price(close_ref):
            return round(close_ref * (1 + limit), 2)

        ztj_arr = np.array([ztj_price(c[i-1]) if i>0 else np.nan for i in range(len(c))])
        zt = (np.abs(c-h) < 0.001) & (c >= ztj_arr - 0.001)
        zb = (c < h) & (h >= ztj_arr - 0.001)

        count_zt_10 = count_rolling(zt, 10)
        sb = zt & (count_zt_10 == 1)

        ref_c1 = np.roll(c, 1); ref_c1[0] = np.nan
        ref_h1 = np.roll(h, 1); ref_h1[0] = np.nan
        ref_o1 = np.roll(o, 1); ref_o1[0] = np.nan
        ref_c1_safe = np.where(ref_c1 == 0, np.nan, ref_c1)

        syx = np.where(np.isnan(ref_c1_safe), 0, 100 * (h - np.maximum(c, o)) / ref_c1_safe)
        st  = np.where(np.isnan(ref_c1_safe), 0, 100 * np.abs(c - o) / ref_c1_safe)
        xyx = np.where(np.isnan(ref_c1_safe), 0, 100 * (np.minimum(c, o) - l) / ref_c1_safe)
        jzf = np.where(np.isnan(ref_c1_safe), 0, 100 * (o - ref_c1_safe) / ref_c1_safe)
        zf  = np.where(np.isnan(ref_c1_safe), 0, 100 * (c - ref_c1_safe) / ref_c1_safe)
        vj  = v < np.roll(v, 1); vj[0] = False

        syx = np.nan_to_num(syx)
        st  = np.nan_to_num(st)
        xyx = np.nan_to_num(xyx)
        jzf = np.nan_to_num(jzf)
        zf  = np.nan_to_num(zf)

        # T2
        t1 = count_rolling(zt, 2) > 0
        t2a = (syx > 5) & (c > o) & (xyx < 3) & (syx > st)

        cond_b = np.roll(zt & (jzf > 5) & (st > 3) & (l / ref_h1 > 1.03), 1)
        cond_b = np.where(np.isnan(cond_b), False, cond_b)
        expr_b = (zb == False) & (code.startswith('30') or code.startswith('68')) & np.roll(zt, 2) & (l / ref_h1 < 1.03)
        t2b = np.where(cond_b, expr_b, True)

        cond_c = np.roll(zt & (count_rolling(zt, 20) == 1) & (l / ref_h1 > 1.01), 2)
        cond_c = np.where(np.isnan(cond_c), False, cond_c)
        expr_c = np.roll(((jzf < 5) & (jzf > 0) & (zf < 0)) | ((xyx > 4) & (c > o)), 1)
        t2c = np.where(cond_c, ~expr_c, True)

        t2 = np.roll(t1, 1) & fw & t2a & t2b & t2c

        if not t2[n]:
            continue
        t2_count += 1

        # P1~P11
        ref_max_co = np.roll(np.maximum(c, o), 1)
        ref_min_co = np.roll(np.minimum(c, o), 1)
        p1 = (np.maximum(c, o) <= ref_max_co) & (np.minimum(c, o) >= ref_min_co) & np.roll(zt, 2) & np.roll((c < o) & (c > ref_c1), 1)
        p2 = (syx > 5) & (st > 5) & (jzf < -2) & np.roll(sb, 1)
        p3 = np.roll(sb, 2) & rolling_every((c > o) & (syx > 3) & (c > ref_c1) & (h > np.roll(h, 1)) & (st < 2), 2)
        p4 = (st > 3) & (st < 4) & (h / ref_c1_safe > 1.09) & (xyx < 1.3) & np.roll(sb & (count_rolling(zt, 20) == 1) & (jzf < 3), 1)
        p5 = (st > 3) & (st < 4) & (h / ref_c1_safe > 1.09) & (xyx < 1.3) & np.roll(zt & (st > 10) & (code.startswith('30') or code.startswith('68')), 1)
        p6 = (syx > 2) & (xyx > 2) & (syx > xyx)
        p7 = (np.maximum(c, o) <= ref_max_co) & (np.minimum(c, o) >= ref_min_co) & np.roll(zt, 2) & (v > np.roll(v, 1)) & (count_rolling(zt, 10) < 2)
        p8 = rolling_every(vj, 2) & np.roll(zt, 2)
        p9 = np.roll(sb, 1) & (jzf > 0) & (jzf < 2) & (st < 2) & (st > 1) & (zb == False)
        p10 = (st > 4) & (jzf < -2) & np.roll(sb & (jzf > 2), 1)
        p11 = (count_rolling(t2, 10) > 1) & np.roll(zt, 1)

        tj1 = np.where(zb, jzf >= 0, zb == False) & (st > 0.4)
        tj2 = np.where(xyx == 0, st > 6, xyx > 0)
        tj3 = np.where(zb, jzf > 9.5, zb == False) & (count_rolling(rolling_every(zb, 2), 5) == 0) & ~(zt & (c == o))

        ta_arr = np.roll(tj1 & tj2 & (p1 == 0) & (p2 == 0) & (p3 == 0) & (p4 == 0) & (p5 == 0) & (p7 == 0) & (p8 == 0) & (p9 == 0) & (p10 == 0) & (p11 == 0), 1)
        if not ta_arr[n]:
            continue
        ta_count += 1

        tb_arr = np.roll(tj3 & (p6 == 0), 2)
        if not tb_arr[n]:
            continue
        tb_count += 1

        close_yesterday = c[n]
        jzf_today = 100 * (today_open - close_yesterday) / close_yesterday
        p12a_today = (jzf_today < -4.1) and (today_open < o[n]) and (zb[n] and c[n] > o[n] and o[n] / c[n-1] > 1.01)
        p12_today = p12a_today and (n >= 2 and zt[n-1] and o[n-1] / c[n-2] > 1.01) and (n >= 3 and c[n-2] > o[n-2])
        count_zt_20 = count_rolling(zt, 20)
        p13_today = (n >= 2 and st[n-1] > 10 and count_zt_20[n-1] == 1) and (n >= 1 and syx[n] > 9) and (code.startswith('00') or code.startswith('60'))
        if p12_today or p13_today:
            continue
        tjp1_count += 1

        if jzf_today >= 0:
            continue

        lbts = np.zeros_like(zt, dtype=int)
        cnt = 0
        for i in range(len(zt)):
            if zt[i]: cnt += 1
            else: cnt = 0
            lbts[i] = cnt
        if n >= 60 and np.sum(lbts[-60:] == 5) >= 2:
            continue

        tjdk_count += 1
        candidates.append((stock, today_open))

    log.info(f"T2:{t2_count} TA:{ta_count} TB:{tb_count} TJP1:{tjp1_count} TJDK:{tjdk_count} 候选:{len(candidates)}")

    if not candidates:
        log.info("无符合条件股票，不买入")
        return

    # 过滤掉资金不足以买1手的股票
    cash = context.portfolio.available_cash
    valid = []
    for stock, open_price in candidates:
        if open_price * 100 <= cash * 0.95:  # 预留一点手续费空间
            valid.append((stock, open_price))
    if not valid:
        log.info("可用资金不足以买入任何1手，不买入")
        return

    per_amount = cash / len(valid)
    # 再次过滤，确保每只分到的钱至少能买1手
    final_buy = []
    for stock, open_price in valid:
        if per_amount >= open_price * 100:
            final_buy.append((stock, open_price))
    if not final_buy:
        log.info("均分金额不足1手，不买入")
        return

    for stock, open_price in final_buy:
        limit_price = round(open_price * 1.02, 2)
        order_target_value(stock, per_amount, LimitOrderStyle(limit_price))

    log.info(f"买入{len(final_buy)}只，每只约{per_amount:.0f}元")
    g.selected_stocks = [s for s, _ in final_buy]

def check_sell(context):
    positions = context.portfolio.positions
    if not positions:
        return
    today = context.current_dt.date()
    for stock in list(positions.keys()):
        pos = positions[stock]
        if pos.total_amount == 0:
            continue
        # T+1：当日买入的跳过
        if stock in g.stock_info and g.stock_info[stock]['buy_date'] == today:
            continue
        try:
            price_df = get_price(stock, end_date=today, count=1, frequency='daily', fields=['close'], fq='pre')
            if len(price_df) == 0:
                continue
            price = price_df['close'].iloc[-1]
        except:
            continue

        if stock not in g.stock_info:
            g.stock_info[stock] = {'buy_date': today, 'cost': pos.avg_cost, 'highest': pos.avg_cost}
        info = g.stock_info[stock]
        if price > info['highest']:
            info['highest'] = price

        # 计算止损/止盈条件
        if price <= info['cost'] * 0.95:
            order_target(stock, 0)
            log.info(f"止损 {stock}")
            del g.stock_info[stock]
        elif (today - info['buy_date']).days >= 3 and price <= info['cost']:
            order_target(stock, 0)
            log.info(f"3日不涨止损 {stock}")
            del g.stock_info[stock]
        elif price >= info['cost'] * 1.3:
            order_target(stock, 0)
            log.info(f"止盈 {stock}")
            del g.stock_info[stock]
        elif info['highest'] > info['cost'] and price <= info['highest'] * 0.95:
            order_target(stock, 0)
            log.info(f"回撤止盈 {stock}")
            del g.stock_info[stock]