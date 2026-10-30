# Clone from JoinQuant
# postId: e1053979bd68950e6e09252bbb563f1e
# backtestId: 3f34731dfab1a20b9420c0030036b7e4
# title: 年化68.63%，回撤16.82连板策略

# ===================== 连板涨停策略 V5.8（加入竞价量比过滤） =====================
# 新增：使用 get_call_auction 获取集合竞价成交量，计算竞价量比（竞价量/昨日总成交量）
# 过滤范围：5% ~ 12%（有效主力参与，无异常巨量）
# 保留：宏观择时、情绪、概念、开盘条件、止盈止损、尾盘、防守模式、大盘风控

from jqdata import *
from jqfactor import *
import datetime as dt
import pandas as pd
import numpy as np

# ===================== 全局常量 =====================
PRICE_EPS = 1e-4
MIN_TRADE_AMOUNT = 8000
EXCLUDE_CONCEPT = {'转融券标的', '融资融券', '深股通', '沪股通', '国企改革'}

# ===================== 辅助函数 =====================
def transform_date(date, date_type):
    if isinstance(date, str):
        str_d = date
        dt_d = dt.datetime.strptime(date, '%Y-%m-%d')
        d_d = dt_d.date()
    elif isinstance(date, dt.datetime):
        str_d = date.strftime('%Y-%m-%d')
        dt_d = date
        d_d = date.date()
    elif isinstance(date, dt.date):
        str_d = date.strftime('%Y-%m-%d')
        dt_d = dt.datetime.strptime(str_d, '%Y-%m-%d')
        d_d = date
    else:
        return ""
    res_map = {'str': str_d, 'dt': dt_d, 'd': d_d}
    return res_map[date_type]

def filter_new_stock(stock_list, date, days=50):
    d_date = transform_date(date, 'd')
    res = []
    for s in stock_list:
        try:
            start_date = get_security_info(s).start_date
            if (d_date - start_date) > dt.timedelta(days=days):
                res.append(s)
        except:
            res.append(s)
    return res

def filter_st_stock(stock_list, date):
    str_date = transform_date(date, 'str')
    df = get_extras('is_st', stock_list, start_date=str_date, end_date=str_date, df=True)
    df = df.T
    df.columns = ['is_st']
    df = df[df['is_st'] == False]
    return list(df.index)

def filter_kcbj_stock(stock_list):
    return [s for s in stock_list if s[0] not in ('4', '8') and s[:2] != '68']

def filter_paused_stock(stock_list, date):
    df = get_price(
        stock_list, end_date=date, frequency='daily',
        fields=['paused'], count=1, panel=False, fill_paused=True
    )
    df = df[df['paused'] == 0]
    return list(df.code)

def filter_name_stock(stock_list):
    try:
        current_data = get_current_data()
    except:
        return stock_list
    res = []
    for s in stock_list:
        name = current_data[s].name
        if 'ST' not in name and '※ST' not in name and '退' not in name:
            res.append(s)
    return res

def filter_stock_list(stock_list, date, context):
    if not stock_list:
        return []
    stock_list = filter_kcbj_stock(stock_list)
    stock_list = filter_new_stock(stock_list, date)
    stock_list = filter_st_stock(stock_list, date)
    stock_list = filter_paused_stock(stock_list, date)
    today = context.current_dt.strftime("%Y-%m-%d")
    target_date = transform_date(date, 'str')
    if today == target_date:
        stock_list = filter_name_stock(stock_list)
    return stock_list

def prepare_stock_list(date, context):
    all_stocks = get_all_securities('stock', date).index.tolist()
    all_stocks = filter_stock_list(all_stocks, date, context)
    return all_stocks

def get_hl_stock(stock_list, date):
    df = get_price(
        stock_list, end_date=date, frequency='daily',
        fields=['close', 'high_limit'], count=1,
        panel=False, fill_paused=False, skip_paused=False
    )
    df = df.dropna()
    df = df[abs(df['close'] - df['high_limit']) < PRICE_EPS]
    return list(df.code)

def get_continue_count_df(stock_list, date, watch_days):
    if not stock_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    df = get_price(
        stock_list, end_date=date, frequency='daily',
        fields=['close', 'high_limit', 'low', 'paused'], count=watch_days,
        panel=False, fill_paused=False, skip_paused=False
    )
    if df.empty:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    res = []
    for code in stock_list:
        sub_df = df[df['code'] == code].copy()
        sub_df = sub_df.sort_values('time', ascending=False).reset_index(drop=True)
        continue_hl = 0
        extreme_hl = 0
        for _, row in sub_df.iterrows():
            if row['paused'] == 1:
                break
            if abs(row['close'] - row['high_limit']) < PRICE_EPS:
                continue_hl += 1
                if abs(row['low'] - row['high_limit']) < PRICE_EPS:
                    extreme_hl += 1
            else:
                break
        if continue_hl > 0:
            res.append({'code': code, 'count': continue_hl, 'extreme_count': extreme_hl})
    result_df = pd.DataFrame(res)
    if not result_df.empty:
        result_df.set_index('code', inplace=True)
    return result_df

def extract_concept_data(stock_list, date):
    raw = get_concept(stock_list, date)
    if not raw:
        return {}
    result = {}
    for code in stock_list:
        if code not in raw:
            continue
        data = raw[code]
        concepts = []
        if isinstance(data, list):
            concepts = [str(c) for c in data if isinstance(c, str) and c]
        elif isinstance(data, dict) and 'jq_concept' in data:
            jq_list = data['jq_concept']
            if isinstance(jq_list, list):
                for item in jq_list:
                    if isinstance(item, dict) and 'concept_name' in item:
                        c_name = item['concept_name']
                        if c_name:
                            concepts.append(str(c_name))
        elif isinstance(data, str):
            concepts = [data]
        if concepts:
            result[code] = list(set(concepts))
    return result

def get_hot_concept(concept_dict, lb_df, date):
    concept_count = {}
    for code in concept_dict:
        if code not in lb_df.index:
            continue
        lb_num = lb_df.loc[code, 'count']
        for c_name in concept_dict[code]:
            if not isinstance(c_name, str):
                continue
            if c_name in EXCLUDE_CONCEPT:
                continue
            if c_name in concept_count:
                concept_count[c_name] += lb_num
            else:
                concept_count[c_name] = lb_num
    if not concept_count:
        return []
    df = pd.DataFrame(list(concept_count.items()), columns=['concept_name', 'cnt'])
    df = df.set_index('concept_name').sort_values('cnt', ascending=False)
    return list(df.index)[:5]

def get_stocks_by_concept_name(concept_name):
    df_concept = get_concepts()
    if df_concept.empty:
        return []
    matched = df_concept[df_concept['name'] == concept_name]
    if matched.empty:
        return []
    concept_code = matched.index[0]
    try:
        return get_concept_stocks(str(concept_code))
    except:
        return []

# ===================== 全局变量管理 =====================
def ensure_g_vars():
    if not hasattr(g, 'min_buy_pct'):
        g.min_buy_pct = 0.25
    if not hasattr(g, 'max_buy_pct'):
        g.max_buy_pct = 0.70
    if not hasattr(g, 'high_price_dict'):
        g.high_price_dict = {}
    if not hasattr(g, 'trailing_drawdown_ratio'):
        g.trailing_drawdown_ratio = 0.05
    if not hasattr(g, 'market_cache'):
        g.market_cache = {'date': None, 'cnt': 0, 'avg_h': 0.0}
    if not hasattr(g, 'sort'):
        g.sort = False
    if not hasattr(g, 'mode'):
        g.mode = 'ATTACK'
    if not hasattr(g, 'profit_reduced'):
        g.profit_reduced = {}
    if not hasattr(g, 'forbid_buy'):
        g.forbid_buy = False
    if not hasattr(g, 'emergency_triggered'):
        g.emergency_triggered = False

def clear_high_price(code):
    if hasattr(g, 'high_price_dict') and code in g.high_price_dict:
        del g.high_price_dict[code]

def clear_profit_reduced(code):
    if hasattr(g, 'profit_reduced') and code in g.profit_reduced:
        del g.profit_reduced[code]

# ===================== 情绪计算 =====================
def compute_market_emotion(context):
    date = context.previous_date.strftime("%Y-%m-%d")
    all_stocks = get_all_securities('stock', date).index.tolist()
    all_stocks = [s for s in all_stocks if s[:2] in ('60','00','30')]
    d_date = context.previous_date
    filtered = []
    for s in all_stocks:
        try:
            start_date = get_security_info(s).start_date
            if (d_date - start_date).days > 60:
                filtered.append(s)
        except:
            continue
    if not filtered:
        return 0, 0
    df = get_price(filtered, end_date=date, frequency='daily',
                   fields=['close', 'high_limit'], count=1,
                   panel=False, fill_paused=False, skip_paused=False).dropna()
    if df.empty:
        return 0, 0
    limit_stocks = list(df[abs(df['close'] - df['high_limit']) < PRICE_EPS]['code'])
    cnt = len(limit_stocks)
    if len(limit_stocks) < 5:
        return cnt, 0
    ccd = get_continue_count_df(limit_stocks, date, 20)
    if ccd.empty:
        return cnt, 0
    heights_all = ccd[ccd['count'] >= 2]['count']
    avg_h = heights_all.mean() if not heights_all.empty else 0
    return cnt, avg_h

def check_market_emotion(context):
    ensure_g_vars()
    today = context.current_dt.date()
    cache = g.market_cache
    if cache['date'] != today:
        cnt, avg_h = compute_market_emotion(context)
        cache['date'] = today
        cache['cnt'] = cnt
        cache['avg_h'] = avg_h
    else:
        cnt = cache['cnt']
        avg_h = cache['avg_h']
    log.info(f"【情绪】涨停{cnt}，平均高度{avg_h:.2f}")
    if cnt < 30 or avg_h < 2.2:
        log.info("【情绪】不达标（涨停<30或高度<2.2），暂停开仓")
        return False
    return True

def get_dynamic_buy_pct(context):
    ensure_g_vars()
    cache = g.market_cache
    today = context.current_dt.date()
    if cache['date'] != today:
        cnt, avg_h = compute_market_emotion(context)
        cache['date'] = today
        cache['cnt'] = cnt
        cache['avg_h'] = avg_h
    else:
        cnt = cache['cnt']
        avg_h = cache['avg_h']
    score_cnt = min(cnt, 80) / 80.0
    score_h = min(avg_h, 4.0) / 4.0
    score = score_cnt * 0.6 + score_h * 0.4
    pct = g.min_buy_pct + score * (g.max_buy_pct - g.min_buy_pct)
    pct = max(g.min_buy_pct, min(g.max_buy_pct, pct))
    if g.mode == 'DEFENSE':
        pct = min(pct, 0.20)
    log.info(f"【动态仓位】涨停{cnt}，高度{avg_h:.2f}，仓位{pct:.0%}")
    return pct

# ===================== 宏观择时 =====================
def market_mode_prepare(context):
    g.forbid_buy = False
    g.emergency_triggered = False
    try:
        hs300_data = attribute_history('000300.XSHG', 21, '1d', ['close'], skip_paused=True)
        if len(hs300_data) < 20:
            g.mode = 'ATTACK'
            return
        closes = hs300_data['close'].values
        yesterday_close = closes[-1]
        ma20 = np.mean(closes[-20:])
        g.hs300_close = yesterday_close
        g.hs300_ma20 = ma20
        g.mode = 'ATTACK' if yesterday_close > ma20 else 'DEFENSE'
        log.info(f"【宏观】HS300: {yesterday_close:.2f}, MA20: {ma20:.2f}, 模式: {g.mode}")
    except Exception as e:
        log.error(f"【宏观异常】{e}")
        g.mode = 'ATTACK'

# ===================== 盘中止损/止盈 =====================
def sell_check_realtime(context):
    ensure_g_vars()
    current_dt = context.current_dt
    if current_dt.hour < 9 or (current_dt.hour == 9 and current_dt.minute < 30) or current_dt.hour >= 15:
        return
    if not hasattr(g, '_last_minute_checked'):
        g._last_minute_checked = -1
    if g._last_minute_checked == current_dt.minute:
        return
    g._last_minute_checked = current_dt.minute

    # 大盘跌幅监控
    try:
        hs300_hist = attribute_history('000300.XSHG', 1, '1d', ['close'], skip_paused=True)
        if len(hs300_hist) > 0:
            pre_close = hs300_hist['close'][0]
            curr_price = get_current_data()['000300.XSHG'].last_price
            if pre_close > 0:
                drop = (curr_price - pre_close) / pre_close
                if drop <= -0.02 and not g.emergency_triggered:
                    g.emergency_triggered = True
                    g.forbid_buy = True
                    log.info(f"【紧急】HS300跌{drop:.2%}，执行风控")
                    for code in list(context.portfolio.positions.keys()):
                        pos = context.portfolio.positions[code]
                        if pos.closeable_amount <= 0:
                            continue
                        curr_price_stock = get_current_data()[code].last_price
                        cost = pos.avg_cost
                        if cost <= 0:
                            continue
                        profit_ratio = (curr_price_stock - cost) / cost
                        if profit_ratio < 0:
                            order_target(code, 0)
                            clear_high_price(code)
                            clear_profit_reduced(code)
                        else:
                            target_amount = int(pos.total_amount * 0.5)
                            if target_amount > 0 and target_amount < pos.total_amount:
                                order_target(code, target_amount)
                            else:
                                order_target(code, 0)
                                clear_high_price(code)
                                clear_profit_reduced(code)
    except:
        pass

    # 持仓遍历
    try:
        current_data = get_current_data()
        for code in list(context.portfolio.positions.keys()):
            pos = context.portfolio.positions[code]
            if pos.closeable_amount <= 0:
                continue
            curr_price = current_data[code].last_price
            cost = pos.avg_cost
            if cost <= 0:
                continue
            profit_ratio = (curr_price - cost) / cost
            if code not in g.high_price_dict:
                g.high_price_dict[code] = curr_price
            else:
                g.high_price_dict[code] = max(g.high_price_dict[code], curr_price)
            highest = g.high_price_dict[code]

            # 20%减仓
            if profit_ratio >= 0.20 and not g.profit_reduced.get(code, False):
                target_amount = int(pos.total_amount * 0.6)
                if target_amount > 0 and target_amount < pos.total_amount:
                    order_target(code, target_amount)
                    g.profit_reduced[code] = True

            # 保本止损
            if profit_ratio < 0.05:
                if curr_price <= cost * (1 + PRICE_EPS):
                    order_target(code, 0)
                    clear_high_price(code)
                    clear_profit_reduced(code)
                    continue
            # 回撤止盈
            elif profit_ratio > 0.10:
                drawdown = (highest - curr_price) / highest
                if drawdown > 0.05:
                    order_target(code, 0)
                    clear_high_price(code)
                    clear_profit_reduced(code)
                    continue
    except Exception as e:
        log.error(f"【止损异常】{e}")

# ===================== 竞价卖出 =====================
def sell_check_open(context):
    ensure_g_vars()
    try:
        current_data = get_current_data()
        for code in list(context.portfolio.positions.keys()):
            pos = context.portfolio.positions[code]
            if pos.closeable_amount <= 0:
                continue
            open_price = current_data[code].day_open
            low_limit = current_data[code].low_limit
            hist = attribute_history(code, 1, '1d', ['close'], skip_paused=False)
            if len(hist) == 0:
                continue
            pre_close = hist['close'][0]
            if abs(open_price - low_limit) < PRICE_EPS:
                continue
            if open_price < (pre_close - PRICE_EPS):
                log.info(f"【竞价止损】{code} 低开清仓")
                order_target(code, 0)
                clear_high_price(code)
                clear_profit_reduced(code)
    except Exception as e:
        log.error(f"【竞价异常】{e}")

# ===================== 尾盘清仓 =====================
def sell_check_afternoon(context):
    ensure_g_vars()
    try:
        current_data = get_current_data()
        for code in list(context.portfolio.positions.keys()):
            pos = context.portfolio.positions[code]
            if pos.closeable_amount <= 0:
                continue
            curr_price = current_data[code].last_price
            high_limit = current_data[code].high_limit
            low_limit = current_data[code].low_limit
            if abs(curr_price - low_limit) < PRICE_EPS:
                continue
            if curr_price >= (high_limit - 0.01):
                log.info(f"【尾盘持仓】{code} 封板过夜")
            else:
                log.info(f"【尾盘清仓】{code} 未封板")
                order_target(code, 0)
                clear_high_price(code)
                clear_profit_reduced(code)
    except Exception as e:
        log.error(f"【尾盘异常】{e}")

# ===================== 收盘打印 =====================
def print_position_info(context):
    ensure_g_vars()
    if context.portfolio.total_value < PRICE_EPS:
        return
    for pos in context.portfolio.positions.values():
        code = pos.security
        cost = pos.avg_cost
        price = pos.price
        if cost > PRICE_EPS:
            profit = 100 * (price / cost - 1)
        else:
            profit = 0
        log.info(f"【持仓】{code} 成本{cost:.2f} 现价{price:.2f} 盈亏{profit:.2f}% 股数{pos.total_amount}")

# ===================== 新增：获取竞价量比 =====================
def get_auction_volume_ratio(code, date_str):
    """
    获取股票的竞价量比 = 集合竞价成交量 / 昨日总成交量
    使用 get_call_auction 获取9:25的累计成交量
    返回：比例值（如0.08表示8%），若获取失败返回None
    """
    try:
        # 获取集合竞价数据
        df = get_call_auction(code, date_str, date_str)
        if df is None or df.empty:
            return None
        
        # 筛选9:25时刻的数据（精确到分钟）
        df_925 = df[df['time'].dt.hour == 9]
        if df_925.empty:
            return None
        
        # 取最后一笔（即9:25的最终撮合量）
        auction_volume = df_925['volume'].iloc[-1]
        if auction_volume <= 0:
            return None
        
        # 获取昨日总成交量
        hist_data = attribute_history(code, 1, '1d', ['volume'], skip_paused=False)
        if len(hist_data) == 0 or hist_data['volume'][0] <= 0:
            return None
        
        yesterday_volume = hist_data['volume'][0]
        ratio = auction_volume / yesterday_volume
        return ratio
    except Exception as e:
        return None

# ===================== 核心选股（加入竞价量比过滤） =====================
def get_stock_list(context):
    ensure_g_vars()
    pre_date = transform_date(context.previous_date, 'str')
    curr_date = context.current_dt.strftime("%Y-%m-%d")
    
    if not check_market_emotion(context):
        g.target_list = []
        return

    initial_list = prepare_stock_list(pre_date, context)
    if not initial_list:
        g.target_list = []
        return

    hl_list = get_hl_stock(initial_list, pre_date)
    if not hl_list:
        g.target_list = []
        return

    ccd_hl = get_continue_count_df(hl_list, pre_date, 20)
    if ccd_hl.empty:
        g.target_list = []
        return

    ccd_lb = ccd_hl[ccd_hl['count'] >= 2]
    if ccd_lb.empty:
        g.target_list = []
        return
    stock_lb_list = list(ccd_lb.index)

    stock_concept_dict = extract_concept_data(stock_lb_list, pre_date)
    if not stock_concept_dict:
        g.target_list = []
        return

    hot_concepts = get_hot_concept(stock_concept_dict, ccd_lb, pre_date)
    if not hot_concepts:
        g.target_list = []
        return

    combined_df = pd.DataFrame(columns=['count', 'extreme_count'])
    stock_concept_occurrence = {}
    for concept in hot_concepts:
        concept_stocks = get_stocks_by_concept_name(concept)
        concept_stocks = filter_stock_list(concept_stocks, pre_date, context)
        cross_stocks = list(set(hl_list) & set(concept_stocks))
        if not cross_stocks:
            continue
        temp_df = ccd_hl[ccd_hl.index.isin(cross_stocks)]
        combined_df = pd.concat([combined_df, temp_df], ignore_index=False)
        for code in cross_stocks:
            stock_concept_occurrence[code] = stock_concept_occurrence.get(code, 0) + 1

    if combined_df.empty:
        g.target_list = []
        return

    stock_occur = combined_df.groupby(combined_df.index).size()
    final_df = combined_df[~combined_df.index.duplicated(keep='last')].copy()
    final_df['occurrence'] = final_df.index.map(stock_occur)
    final_df = final_df[
        (final_df['occurrence'] >= 2) &
        (final_df['count'] > 0) &
        (final_df['extreme_count'] / final_df['count'] <= 0.66)
    ].copy()

    candidate_list = list(final_df.index)
    valid_stock = {}
    current_data = get_current_data()

    for code in candidate_list:
        try:
            hist_data = attribute_history(
                security=code,
                count=1,
                unit='1d',
                fields=('close', 'high_limit'),
                skip_paused=False,
                df=False,
                fq='pre'
            )
            pre_close = hist_data['close'][-1]
            open_price = current_data[code].day_open
            high_limit = current_data[code].high_limit
            rise_rate = (open_price - pre_close) / pre_close
            if not (0.02 <= rise_rate <= 0.08 and open_price < (high_limit - 0.01)):
                continue

            # ===== 第三层：竞价量比过滤（5%~12%） =====
            auction_ratio = get_auction_volume_ratio(code, curr_date)
            if auction_ratio is not None:
                if auction_ratio < 0.05:
                    log.info(f"【竞价量比】{code} {auction_ratio:.2%} < 5%，放弃")
                    continue
                elif auction_ratio > 0.12:
                    log.info(f"【竞价量比】{code} {auction_ratio:.2%} > 12%，异常巨量，放弃")
                    continue
                else:
                    log.info(f"【竞价量比】{code} {auction_ratio:.2%} 符合5%~12%区间")
            else:
                # 无法获取数据时，放行（避免误杀）
                log.info(f"【竞价量比】{code} 无法获取数据，放行")

            stock_name = get_security_info(code, pre_date).display_name
            valid_stock[code] = f"{stock_name} 量比{auction_ratio:.2%}" if auction_ratio else f"{stock_name}"

        except Exception as e:
            continue

    temp_list = list(valid_stock.keys())
    if not temp_list:
        g.target_list = []
        log.info("【选股】过滤后无标的")
        return

    custom_scores = {}
    for code in temp_list:
        count_val = final_df.loc[code, 'count']
        occur = stock_concept_occurrence.get(code, 1)
        custom_scores[code] = count_val * occur

    factor_df = pd.DataFrame(list(custom_scores.items()), columns=['code', 'score'])
    factor_df.set_index('code', inplace=True)
    factor_df = factor_df.sort_values('score', ascending=False)
    final_buy_list = list(factor_df.index)
    hold_stocks = list(context.portfolio.positions)
    g.target_list = [s for s in final_buy_list if s not in hold_stocks]
    log.info(f"【选股】最终买入池: {g.target_list}")

# ===================== 买入逻辑 =====================
def buy(context):
    ensure_g_vars()
    if g.forbid_buy:
        log.info("【买入】禁止开仓")
        return

    try:
        current_data = get_current_data()
        buy_list = g.target_list
        if not buy_list:
            return

        total_cap = context.portfolio.total_value
        buy_pct = get_dynamic_buy_pct(context)
        if g.mode == 'DEFENSE':
            single_stock_max_pct = 0.05
        else:
            single_stock_max_pct = 1.0

        cash = context.portfolio.available_cash
        total_alloc_cap = min(cash, total_cap * buy_pct)
        if total_alloc_cap < MIN_TRADE_AMOUNT:
            return

        pre_filter_list = []
        for code in buy_list:
            info = current_data[code]
            if info.paused or 'ST' in info.name or '退' in info.name:
                continue
            if abs(info.day_open - info.high_limit) < PRICE_EPS or abs(info.day_open - info.low_limit) < PRICE_EPS:
                continue
            pre_filter_list.append(code)

        if not pre_filter_list:
            return

        total_valid = len(pre_filter_list)
        per_stock_pct = 1.0 / total_valid
        if g.mode == 'DEFENSE':
            per_stock_pct = min(per_stock_pct, 0.05)
        single_amount = total_alloc_cap * per_stock_pct

        if single_amount < MIN_TRADE_AMOUNT:
            max_support_num = int(total_alloc_cap // MIN_TRADE_AMOUNT)
            if max_support_num <= 0:
                return
            final_buy_list = pre_filter_list[:max_support_num]
            per_stock_pct = 1.0 / max_support_num
            if g.mode == 'DEFENSE':
                per_stock_pct = min(per_stock_pct, 0.05)
            single_amount = total_alloc_cap * per_stock_pct
        else:
            final_buy_list = pre_filter_list

        if g.mode == 'DEFENSE':
            max_single = total_cap * 0.05
            single_amount = min(single_amount, max_single)

        for code in final_buy_list:
            info = current_data[code]
            min_1hand = info.last_price * 100
            if single_amount < min_1hand:
                max_shares = int(single_amount // info.last_price)
                max_shares = (max_shares // 100) * 100
                if max_shares <= 0:
                    continue
                order(code, max_shares, MarketOrderStyle())
                log.info(f"【买入】{code} {max_shares}股 市价")
            else:
                order_value(code, single_amount, MarketOrderStyle())
                log.info(f"【买入】{code} {single_amount:.2f}元 市价")
    except Exception as e:
        log.error(f"【买入异常】{e}")

# ===================== 初始化 =====================
def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option("match_by_signal", True)
    log.set_level('system', 'error')

    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5
        ),
        type='stock'
    )

    set_slippage(PriceRelatedSlippage(0.006))

    g.sort = False
    g.target_list = []
    g.min_buy_pct = 0.25
    g.max_buy_pct = 0.70
    g.mode = 'ATTACK'
    g.hs300_close = None
    g.hs300_ma20 = None
    g.high_price_dict = {}
    g.trailing_drawdown_ratio = 0.05
    g.profit_reduced = {}
    g.market_cache = {'date': None, 'cnt': 0, 'avg_h': 0.0}
    g.forbid_buy = False
    g.emergency_triggered = False

    log.info("【初始化】V5.8 启动 - 加入竞价量比过滤（5%~12%）")
    log.info("【滑点】双向0.6%")
    log.info("【竞价量比】集合竞价成交量/昨日总成交量，范围5%~12%")
    log.info("【选股】连板+热门概念+高开2%~8%未涨停+竞价量比健康")
    log.info("【情绪】涨停≥30 且 高度≥2.2")
    log.info("【宏观】HS300 > MA20 进攻，否则防守")

    run_daily(market_mode_prepare, '09:00')
    run_daily(sell_check_open, '09:27')
    run_daily(get_stock_list, '09:25:45')
    run_daily(buy, '09:30:00')
    run_daily(sell_check_afternoon, '14:50')
    run_daily(print_position_info, '15:02')
    run_daily(sell_check_realtime, 'every_bar')