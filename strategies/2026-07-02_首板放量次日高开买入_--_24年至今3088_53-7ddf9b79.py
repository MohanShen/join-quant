# Clone from JoinQuant
# postId: 7ddf9b7989a0853509756ccd49826206
# backtestId: d5e595a08b0bb537ae85558990c2827e
# title: 首板放量次日高开买入 -- 24年至今3088.53%

from jqdata import *
import pandas as pd

# ========== 初始化策略环境 ==========
def initialize(context):
    log.set_level('order', 'error')
    set_option('use_real_price', True)  # 用真实价格交易
    set_option('avoid_future_data', True)  # 开启防未来函数
    set_slippage(FixedSlippage(0.005))  # 设置滑点为0.5%
    # 设置交易成本（万2元，不免5元）
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0002, close_commission=0.0002, min_commission=5), type='stock')
    set_benchmark('399303.XSHE')
    
    g.information = {}
    g.drop_percent = 0.05  # 最大亏损5%
    g.condition_stats = {}
    g.name_cache = {}  # 新增：名称缓存
    context.debug_compare = True
    context.debug_buy_detail = True
    context.debug_list_limit = 120
    context.debug_buy_symbols = []
    context.enable_index_filter = True
    context.index_code = '399303.XSHE'
    context.market_regime = 'neutral'
    context.prev_market_regime = 'neutral'
    context.regime_changed_to_weak = False
    
    run_daily(before_market_open, time='09:10')
    run_daily(get_buy, '09:26')
    run_daily(get_close_sell, time='11:25')
    run_daily(get_close_sell, time='13:30')
    # run_daily(get_close_sell, time='14:50')
    
# ========== 开盘前过滤股票 ==========
def before_market_open(context): 
    update_market_regime(context)
    y_day = context.previous_date.strftime('%Y-%m-%d')

    initial_list = prepare_stock_list(context)
    log.info(f"[选股] 初始股票池: {len(initial_list)}只")
    log_stage_list(context, '初始股票池', initial_list)
    
    g.target_list = get_stocks_with_high_increase(initial_list, y_day)
    log.info(f"[选股] 昨日涨幅>7%: {len(g.target_list)}只")
    log_stage_list(context, '昨日涨幅>7%', g.target_list)
    
    g.target_list = filter_excessive_limit_up(g.target_list, y_day)
    log.info(f"[选股] 过滤一字/T字涨停后: {len(g.target_list)}只")
    log_stage_list(context, '过滤一字/T字涨停后', g.target_list)
    
    g.target_list = filter_excessive_increase(g.target_list, y_day)
    log.info(f"[选股] 过滤近5日波动>40%后: {len(g.target_list)}只")
    log_stage_list(context, '过滤近5日波动>40%后', g.target_list)
    
    g.target_list = filter_excessive_limit_days(g.target_list, y_day)
    log.info(f"[选股] 过滤近5日涨停>=4天后: {len(g.target_list)}只")
    log_stage_list(context, '过滤近5日涨停>=4天后', g.target_list)
    
    g.target_list = filter_below_n_high(g.target_list, y_day, days=100)
    log.info(f"[选股] 过滤低于100日高点后: {len(g.target_list)}只")
    log_stage_list(context, '过滤低于100日高点后', g.target_list)
    
    # 批量缓存名称，避免盘中重复查询
    g.name_cache = {}
    if g.target_list:
        for s in g.target_list:
            try:
                g.name_cache[s] = get_security_info(s).display_name
            except:
                g.name_cache[s] = '未知'
        stock_info = [f"{s}({g.name_cache[s]})" for s in g.target_list]
        log.info(f"今日选股结果 ({len(g.target_list)}只):\n" + "\n".join(stock_info))
        send_message(f"今日选股: {len(g.target_list)}只, 涨幅>7%")
    else:
        log.info("今日无符合条件的股票")
        send_message("今日无符合条件的股票")

# ========== 获取前几日的涨停次数 ==========
def get_hl_count_df(hl_list, y_day, watch_days):
    if not hl_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    df = get_price(hl_list, end_date=y_day, frequency='daily',
                   fields=['close', 'high_limit', 'low', 'open'],
                   count=watch_days, panel=False, fill_paused=False, skip_paused=False)
    if df.empty:
        return pd.DataFrame(index=hl_list, data={'count': 0, 'extreme_count': 0})

    df['is_limit']   = df['close'] == df['high_limit']
    df['is_yizi']    = (df['low'] == df['high_limit']) & df['is_limit']
    df['is_tzi']     = (df['open'] == df['high_limit']) & df['is_limit'] & (df['low'] < df['high_limit'])
    df['is_extreme'] = df['is_yizi'] | df['is_tzi']

    counts = df.groupby('code')[['is_limit', 'is_extreme']].sum().astype(int)
    counts.columns = ['count', 'extreme_count']
    # 优化：用reindex替代concat
    counts = counts.reindex(hl_list, fill_value=0)
    return counts

# ========== 过滤涨停天数过多 ==========
def filter_excessive_limit_days(stock_list, y_day):
    limit_up_df = get_hl_count_df(stock_list, y_day, 5)
    qualified_stocks = limit_up_df[limit_up_df['count'] < 4].index.tolist()
    
    excluded = set(stock_list) - set(qualified_stocks)
    if excluded:
        log.info(f"因近5日涨停天数大于等于4被排除的股票: {len(excluded)}只")
        excluded_info = []
        for stock in excluded:
            count = limit_up_df.loc[stock, 'count']
            name = g.name_cache.get(stock, '未知')
            excluded_info.append(f"{stock}({name}): {count}次涨停")
        log.info("被排除股票详情:\n" + "\n".join(excluded_info))
    
    return qualified_stocks

# ========== 过滤波动过大 ==========
def filter_excessive_increase(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='daily',
                   fields=['high', 'low'], count=5, panel=False,
                   fill_paused=False, skip_paused=True)
    if df.empty:
        return stock_list
    grp = df.groupby('code')
    max_h = grp['high'].max()
    min_l = grp['low'].min()
    chg = (max_h - min_l) / min_l
    qualified = chg[chg <= 0.4].index.tolist()
    excluded_n = len(stock_list) - len(qualified)
    if excluded_n:
        log.info(f"因近5日波动超过40%被排除: {excluded_n}只")
    return qualified

# ========== 过滤低于N日高点 ==========
# 删除price_df参数，所有调用都传None，从未真正使用
def filter_below_n_high(stock_list, y_day, days=100, min_ratio=0.9):
    if not stock_list:
        return []
    total_days = days + 1

    raw = get_price(stock_list, end_date=y_day, frequency='daily',
                    fields=['high', 'close'], count=total_days,
                    panel=False, fill_paused=False, skip_paused=True, fq='pre')

    if raw.empty:
        return []

    qualified = []
    for stock in stock_list:
        sub = raw[raw['code'] == stock]
        if len(sub) < total_days:
            continue
        sub = sub.tail(total_days)
        max_high = sub['high'].iloc[:-1].max()
        yesterday_close = sub['close'].iloc[-1]
        if yesterday_close >= max_high * min_ratio:
            qualified.append(stock)

    log.info(f"前{days}日最高价过滤: 保留{len(qualified)}/{len(stock_list)}只")
    return qualified
    
# ========== 计算左压天数 ==========
def calculate_zyts(s, context):
    high_prices = attribute_history(s, 101, '1d', fields=['high'], skip_paused=True)['high']
    prev_high = high_prices.iloc[-1]
    zyts_0 = next((i-1 for i, high in enumerate(high_prices[-3::-1], 2) if high >= prev_high), 100)
    zyts = zyts_0 + 5
    return zyts


def log_stage_list(context, stage_name, stock_list):
    if not getattr(context, 'debug_compare', False):
        return
    limit = getattr(context, 'debug_list_limit', 120)
    shown = stock_list[:limit] if stock_list else []
    log.info(f"[对账-阶段] {stage_name} count={len(stock_list) if stock_list else 0} shown={len(shown)} list={','.join(shown)}")


def log_buy_reject(context, stock, name, reason, detail):
    if not getattr(context, 'debug_buy_detail', False):
        return
    debug_symbols = getattr(context, 'debug_buy_symbols', [])
    if debug_symbols and stock not in debug_symbols:
        return
    log.info(f"[买入排除] {stock}({name}) 原因={reason} {detail}")


# ========== 市场状态判断 ==========
def update_market_regime(context):
    if not getattr(context, 'enable_index_filter', True):
        context.market_regime = 'neutral'
        context.regime_changed_to_weak = False
        return

    index_code = getattr(context, 'index_code', '399303.XSHE')
    index_df = get_index_close_df(context, index_code, 160)
    prev_regime = getattr(context, 'prev_market_regime', getattr(context, 'market_regime', 'neutral'))
    context.market_regime, regime_info = calc_market_regime(index_df)
    context.regime_changed_to_weak = (context.market_regime == 'weak' and prev_regime != 'weak')
    context.prev_market_regime = context.market_regime

    log.info(f"市场状态: {context.market_regime}")
    if context.regime_changed_to_weak:
        log.info(f"市场状态由 {prev_regime} 转为 weak，今日禁止新买入")
    if len(regime_info) > 0:
        log.info(
            f"指数{index_code} close={regime_info['index_close']:.2f} "
            f"ma20={regime_info['index_ma20']:.2f} ma60={regime_info['index_ma60']:.2f}"
        )


def is_weak_market(context):
    return getattr(context, 'enable_index_filter', True) and getattr(context, 'market_regime', 'neutral') == 'weak'


def calc_market_regime(index_df):
    if index_df is None or len(index_df) < 80:
        return 'neutral', {}

    close = index_df['close']
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    close_y = close.iloc[-1]
    ma20_y = ma20.iloc[-1]
    ma60_y = ma60.iloc[-1]
    ma20_prev = ma20.iloc[-2]

    info = {
        'index_close': close_y,
        'index_ma20': ma20_y,
        'index_ma60': ma60_y,
    }

    if close_y >= ma20_y and ma20_y >= ma60_y * 0.99 and ma20_y >= ma20_prev:
        return 'strong', info
    if close_y >= ma60_y:
        return 'neutral', info
    return 'weak', info


def get_index_close_df(context, index_code, count=160):
    try:
        df = get_price(
            index_code,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close'],
            count=count,
            panel=False,
            fill_paused=False,
            skip_paused=False,
            fq='pre'
        )
        if df is not None and not df.empty and 'close' in df.columns:
            df = df[['close']].dropna()
            if len(df) >= 80:
                return df
    except Exception as e:
        log.info(f"指数行情获取失败 {index_code}: {e}")

    return None

# ========== 买入逻辑 ==========
def get_buy(context):
    qualified_stocks = []
    current_data = get_current_data()
    y_day = context.previous_date.strftime('%Y-%m-%d')
    t_day = context.current_dt.strftime("%Y-%m-%d")
    start = t_day + ' 09:15:00'
    end = t_day + ' 09:26:00'
    DTJiner = context.portfolio.available_cash

    if is_weak_market(context):
        log.info(f"市场状态=weak，禁止新买入，target={len(g.target_list) if hasattr(g, 'target_list') else 0}")
        return

    if not g.target_list:
        return

    print(f"初始筛选结果: {len(g.target_list)}只股票")

    prev_df = get_price(
        g.target_list, end_date=y_day, frequency='daily',
        fields=['close', 'volume', 'money'], count=1, panel=False,
        fill_paused=False, skip_paused=True
    )
    prev_map = {row['code']: row for _, row in prev_df.iterrows()}

    val_df = get_fundamentals(
        query(valuation.code, valuation.market_cap, valuation.circulating_market_cap)
        .filter(valuation.code.in_(g.target_list)),
        date=str(y_day)[:10]
    )
    val_map = {row['code']: row for _, row in val_df.iterrows()} if not val_df.empty else {}

    # 预计算涨停价基准
    hl_base = {s: current_data[s].high_limit / 1.1 for s in g.target_list}
    if getattr(context, 'debug_compare', False):
        log.info(f"[对账-买入数据] target={len(g.target_list)} prev_rows={len(prev_df)} prev_cols={list(prev_df.columns) if not prev_df.empty else []} val_rows={len(val_df)} val_cols={list(val_df.columns) if not val_df.empty else []} current_rows={len(g.target_list)}")

    for s in g.target_list:
        name = g.name_cache.get(s, '未知')

        # 条件一：均价>7%、成交额、股价、市值
        try:
            prev = prev_map.get(s)
            if prev is None:
                log_buy_reject(context, s, name, '昨日行情缺失', f'date={y_day}')
                continue
            avg_chg = prev['money'] / prev['volume'] / prev['close'] * 1.1 - 1
            money = prev['money']
            open_price = current_data[s].day_open
            val = val_map.get(s)
            market_cap = val['market_cap'] if val is not None else 0
            circ_cap = val['circulating_market_cap'] if val is not None else 0
            if getattr(context, 'debug_compare', False):
                log.info(f"[对账-买入基础] {s}({name}) prev_close={prev['close']:.4f} prev_volume={prev['volume']:.0f} money={money/1e8:.2f}亿 avg_chg={avg_chg*100:.2f}% open={open_price:.4f} open_src=current_data.day_open market={market_cap:.2f}亿 circ={circ_cap:.2f}亿 high_base={hl_base.get(s)} high_src=current_data.high_limit")

            if avg_chg < 0.07:
                log_buy_reject(context, s, name, '均价涨幅不足', f"avg_chg={avg_chg*100:.2f}% money={money/1e8:.2f}亿 volume={prev['volume']:.0f} close={prev['close']:.2f}")
                continue
            if open_price <= 3:
                log_buy_reject(context, s, name, '股价不足', f'open={open_price:.4f}')
                continue
            if val is None or val['market_cap'] < 10 or val['circulating_market_cap'] > 520:
                log_buy_reject(context, s, name, '市值过滤', f'market={market_cap:.2f}亿 circ={circ_cap:.2f}亿')
                continue
            if money < 1e8 or money > 15e8:
                log_buy_reject(context, s, name, '成交额范围', f'money={money/1e8:.2f}亿')
                continue
            is_1_5 = money < 5e8
            is_5_15 = not is_1_5
        except Exception as e:
            log_buy_reject(context, s, name, '买入基础条件异常', str(e))
            continue

        # 条件二：左压（量能）
        try:
            zyts = calculate_zyts(s, context)
            vol_data = attribute_history(s, zyts, '1d', fields=['volume'], skip_paused=True)
            if len(vol_data) < 2:
                log_buy_reject(context, s, name, '左压量能数据不足', f'zyts={zyts} len={len(vol_data)}')
                continue
            if vol_data['volume'][-1] <= max(vol_data['volume'][:-1]) * 0.9:
                log_buy_reject(context, s, name, '左压量能未过', f"zyts={zyts} last={vol_data['volume'][-1]:.0f} max_prev={max(vol_data['volume'][:-1]):.0f}")
                continue
            if getattr(context, 'debug_compare', False):
                log.info(f"[对账-左压] {s}({name}) zyts={zyts} len={len(vol_data)} last_volume={vol_data['volume'][-1]:.0f} max_prev_volume={max(vol_data['volume'][:-1]):.0f} threshold={max(vol_data['volume'][:-1]) * 0.9:.0f}")
        except Exception as e:
            log_buy_reject(context, s, name, '左压量能异常', str(e))
            continue

        # 条件三：竞价数据，匹配6个条件组合
        try:
            auction = get_call_auction(s, start_date=start, end_date=end, fields=['time', 'volume', 'current'])
            if auction.empty:
                log_buy_reject(context, s, name, '竞价缺失', f'start={start} end={end}')
                continue
            cur_ratio = auction['current'][0] / hl_base[s]
            auction_ratio = auction['volume'][0] / vol_data['volume'][-1]
            if getattr(context, 'debug_compare', False):
                log.info(f"[对账-竞价] {s}({name}) cur_ratio={cur_ratio:.4f} auction_ratio={auction_ratio:.4f} auction_price={auction['current'][0]:.4f} auction_volume={auction['volume'][0]:.0f} last_volume={vol_data['volume'][-1]:.0f} high_base={hl_base.get(s)} money_bucket={'1-5亿' if is_1_5 else '5-15亿'} auction_cols={list(auction.columns)}")

            matched_condition = None
            for cond_name, open_lo, open_hi, auc_lo, auc_hi in CONDITION_RULES:
                if cond_name.startswith('A') and not is_1_5:
                    continue
                if not cond_name.startswith('A') and not is_5_15:
                    continue
                if open_lo < cur_ratio <= open_hi and auc_lo <= auction_ratio <= auc_hi:
                    matched_condition = cond_name
                    break

            if matched_condition is None:
                log_buy_reject(context, s, name, '竞价规则未过', f"money={money/1e8:.2f}亿 cur_ratio={cur_ratio:.4f} auction_ratio={auction_ratio:.4f} auction_price={auction['current'][0]:.2f} auction_volume={auction['volume'][0]:.0f}")
                continue
        except Exception as e:
            log_buy_reject(context, s, name, '竞价条件异常', str(e))
            continue

        qualified_stocks.append(s)
        g.information[s] = matched_condition
        print(f"✅ {s}({name}) 通过筛选，命中: {matched_condition}")

    print(f"最终符合条件: {len(qualified_stocks)}只")

    if qualified_stocks and context.portfolio.available_cash / context.portfolio.total_value > 0.3:
        value_per_stock = DTJiner / len(qualified_stocks)
        for s in qualified_stocks:
            price = current_data[s].last_price
            shares = int(value_per_stock / price / 100) * 100
            if shares >= 100:
                order_value(s, value_per_stock, MarketOrderStyle(current_data[s].day_open))
                print(f"买入 {s}: 价格={price}, 数量={shares}, 条件={g.information.get(s,'未知')}")
                
# ========== 卖出逻辑 ==========
def get_close_sell(context):
    y_day = context.previous_date.strftime('%Y-%m-%d')
    current_data = get_current_data()
    positions = context.portfolio.positions
    
    t = context.current_dt
    h, m = t.hour, t.minute
    
    # 批量获取持仓昨日收盘价，避免逐股查询
    yst_close_map = {}
    if positions:
        try:
            yst_df = get_price(
                list(positions.keys()), end_date=y_day,
                frequency='daily', fields=['close'], count=1,
                panel=False, skip_paused=True
            )
            yst_close_map = dict(zip(yst_df['code'], yst_df['close']))
        except:
            pass
    
    # 预缓存持仓名称
    for s in positions:
        if s not in g.name_cache:
            try:
                g.name_cache[s] = get_security_info(s).display_name
            except:
                g.name_cache[s] = '未知'
                
    # 定时卖出检查
    if (h == 11 and m == 25) or (h == 13 and m == 30) or (h == 14 and m == 50):
        for s in list(positions):
            pos = positions[s]
            last_price = current_data[s].last_price
            high_limit = current_data[s].high_limit
            avg_cost = pos.avg_cost
            closeable = pos.closeable_amount
            
            try:
                close_data2 = attribute_history(s, 4, '1d', ['close'])
                M4 = close_data2['close'].mean()
                MA5 = (M4 * 4 + last_price) / 5
            except:
                continue
            
            # 止盈
            if closeable != 0 and last_price < high_limit and last_price > avg_cost:
                get_record_sell(context, s, '未涨停止盈')
                order_target_value(s, 0)
                print('止盈卖出', [s, g.name_cache[s]])
                print('———————————————————————————————————')
            
            # 跌破5日线止损
            elif closeable != 0 and last_price < (MA5 + MA5 * 0.05):
                get_record_sell(context, s, '跌破5日线止损')
                order_target_value(s, 0)
                print('价格跌破5日线+5%止损卖出', [s, g.name_cache[s]])
                print('———————————————————————————————————')
            
            # 跌幅止损（使用批量获取的昨日收盘价）
            elif closeable != 0:
                yst_close = yst_close_map.get(s)
                if yst_close and yst_close > 0:
                    drop_ratio = (yst_close - last_price) / yst_close
                    if drop_ratio >= g.drop_percent:
                        get_record_sell(context, s, '跌幅止损')
                        order_target_value(s, 0)
                        print(f'跌幅止损卖出: {s}({g.name_cache[s]}) 跌幅{-drop_ratio:.2%}')
                        print('———————————————————————————————————')
                
# ========== 卖出记录统计 ==========
def get_record_sell(context, stock, reason):
    try:
        pos = context.portfolio.positions.get(stock)
        if pos is None or pos.avg_cost <= 0:
            return
        current_data = get_current_data()
        price = current_data[stock].last_price
        cost = pos.avg_cost
        pct = (price - cost) / cost
        cond = g.information.get(stock, '未知条件')
        
        if cond not in g.condition_stats:
            g.condition_stats[cond] = {'win': 0, 'loss': 0, 'win_pct': 0.0, 'loss_pct': 0.0}
        
        st = g.condition_stats[cond]
        if pct >= 0:
            st['win'] += 1
            st['win_pct'] += pct
        else:
            st['loss'] += 1
            st['loss_pct'] += pct
        
        name = g.name_cache.get(stock, '未知')
        log.info(f"[卖出统计] {stock}({name}) 条件={cond} 收益={pct:.2%} 原因={reason}")
        
        lines = ['[条件盈亏汇总]']
        for c, st in g.condition_stats.items():
            total = st['win'] + st['loss']
            avg_win = st['win_pct'] / st['win'] if st['win'] > 0 else 0
            avg_loss = st['loss_pct'] / st['loss'] if st['loss'] > 0 else 0
            lines.append(f"  {c}: 盈{st['win']}笔(均{avg_win:.2%}) 亏{st['loss']}笔(均{avg_loss:.2%}) 共{total}笔")
        log.info('\n'.join(lines))
    except Exception as e:
        log.error(f"get_record_sell出错: {e}")
        
# ========== 判断昨日涨幅 ==========
def get_stocks_with_high_increase(initial_list, y_day):
    price_data = get_price(
        initial_list, end_date=y_day, frequency='1d',
        fields=['close'], count=2, panel=False,
        fill_paused=False, skip_paused=True
    )
    if price_data.empty:
        return []
    
    # 向量化计算涨幅
    df = price_data.pivot(index='time', columns='code', values='close')
    if len(df) < 2:
        return []
    pct = df.pct_change().iloc[-1]
    result = pct[pct > 0.07].index.tolist()
    return result
    
# ========== 初始化股票池 ==========
def prepare_stock_list(context):
    by_date = get_trade_days(end_date=context.previous_date, count=50)[0]
    all_s = get_all_securities(['stock'], date=by_date).index
    c_data = get_current_data()

    base_stocks = []
    filter_stats = {
        'total': len(all_s),
        'prefix': 0,
        'st': 0,
        'paused': 0,
        'name': 0,
        'kept': 0,
    }
    for s in all_s:
        if s[0] in ('3', '4', '8', '9') or s.startswith('68'):
            filter_stats['prefix'] += 1
            continue
        try:
            current = c_data[s]
            name = current.name
            if current.is_st:
                filter_stats['st'] += 1
                continue
            if current.paused:
                filter_stats['paused'] += 1
                continue
            if '退' in name or 'ST' in name:
                filter_stats['name'] += 1
                continue
        except Exception as e:
            filter_stats['name'] += 1
            continue
        base_stocks.append(s)
        filter_stats['kept'] += 1

    if getattr(context, 'debug_compare', False):
        log.info(f"[对账-股票池过滤] by_date={by_date} total={filter_stats['total']} prefix={filter_stats['prefix']} st={filter_stats['st']} paused={filter_stats['paused']} name={filter_stats['name']} kept={filter_stats['kept']}")
    return base_stocks
    
# ========== 过滤掉前10个交易日有3个以上一字或者T字涨停的股票 ==========
def filter_excessive_limit_up(stock_list, y_day):
    extreme_hl_df = get_hl_count_df(stock_list, y_day, 10)
    qualified_stocks = extreme_hl_df[extreme_hl_df['extreme_count'] < 3].index.tolist()
    
    excluded = set(stock_list) - set(qualified_stocks)
    if excluded:
        log.info(f"因前10个交易日有3个以上一字或T字涨停被排除的股票: {len(excluded)}只")
        excluded_info = []
        for stock in excluded:
            count = extreme_hl_df.loc[stock, 'extreme_count']
            name = g.name_cache.get(stock, '未知')
            excluded_info.append(f"{stock}({name}): {count}次一字/T字涨停")
        log.info("被排除股票详情:\n" + "\n".join(excluded_info))
    
    return qualified_stocks
    
# ========== 条件组合定义（全局常量）==========
CONDITION_RULES = [
    ('A: 昨日成交额1~5亿 | 竞价涨幅7~9% | 竞昨比10~20%',  1.07, 1.09, 0.10, 0.20),
    ('B: 昨日成交额5~15亿 | 竞价涨幅7~9% | 竞昨比10~20%', 1.07, 1.09, 0.10, 0.20),
    ('C: 昨日成交额5~15亿 | 竞价涨幅4~7% | 竞昨比3~7%',   1.04, 1.07, 0.03, 0.07),
    ('D: 昨日成交额5~15亿 | 竞价涨幅4~7% | 竞昨比10~20%', 1.04, 1.07, 0.10, 0.20),
    ('E: 昨日成交额5~15亿 | 竞价涨幅0~4% | 竞昨比3~7%',   1.00, 1.04, 0.03, 0.07),
    ('F: 昨日成交额5~15亿 | 竞价涨幅0~4% | 竞昨比7~10%',  1.00, 1.04, 0.07, 0.10),
]