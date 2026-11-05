# Clone from JoinQuant
# postId: 209b62044ba5fd5b911d46a6cd382e77
# backtestId: 5317999b6502a91b60361a50a485e8b5
# title: 目前回测收益最高的三连阳首板策略

# 克隆自聚宽文章：https://www.joinquant.com/post/77993
# 标题：目前发现最牛的策略了，年化10倍
# 作者：天天交易

# 克隆自聚宽文章：https://www.joinquant.com/post/77975
# 标题：三连阳首板策略，25年至今的回测46倍是过拟合么？
# 作者：czz-zzc

# 克隆自聚宽文章：https://www.joinquant.com/post/77484
# 标题：调参版低位三连阳首板，近两年1700%（克隆满100删）
# 作者：轶驰

from jqdata import *
from datetime import timedelta


# ========== 策略参数 ==========
MIN_CIRCULATING_MARKET_CAP = 30       # 最小流通市值（亿元）
MAX_CIRCULATING_MARKET_CAP = 300      # 最大流通市值（亿元）
MIN_MONEY = 5e8                       # 昨日最小成交额（元）
MAX_MONEY = 30e8                      # 昨日最大成交额（元）
VOLUME_EXPANSION = 1.7                # 昨日成交量相对前日的放量下限（倍）
PRIOR_VOLUME_LIMIT = 1.5              # 前日成交量相对大前日的放量上限（倍）
MAX_PRIOR_RETURN = 0.05               # 前日及大前日单日涨幅上限
MAX_FIVE_DAY_RANGE = 0.20             # 近 5 日振幅上限：（最高价-最低价）/最低价
MIN_AUCTION_VOLUME_RATIO = 0.03       # 竞价成交量相对昨日成交量的下限
MIN_AUCTION_GAP = -0.01               # 竞价价格相对昨收的最低高开幅度
MAX_AUCTION_GAP = 0.06                # 竞价价格相对昨收的最大高开幅度

# ========== 调试输出 ==========
# 0 表示完整输出；设为正数时，每个阶段仅输出前 N 只，避免日志过长。
DEBUG_PRINT_STOCK_LIST = True
DEBUG_STOCK_LIST_LIMIT = 10


def log_stock_list(stage, stocks):
    """按阶段输出股票列表，供回测和实盘调试使用。"""
    if not DEBUG_PRINT_STOCK_LIST:
        return
    stock_list = list(stocks or [])
    total = len(stock_list)
    if DEBUG_STOCK_LIST_LIMIT > 0 and total > DEBUG_STOCK_LIST_LIMIT:
        shown = stock_list[:DEBUG_STOCK_LIST_LIMIT]
        log.info(f"[{stage}] 股票列表({total}只，仅显示前{len(shown)}只): {shown}")
        return
    log.info(f"[{stage}] 股票列表({total}只): {stock_list}")


# ========== 初始化与调度 ==========
def initialize(context):
    """设置策略状态、交易成本和定时任务。"""
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.005))
    set_order_cost(
        OrderCost(
            close_tax=0.0005,
            open_commission=0.0002,
            close_commission=0.0002,
            min_commission=5,
        ),
        type='stock',
    )
    set_benchmark('399303.XSHE')

    g.information = {}
    g.base_stocks = []
    g.today_pick = []
    g.pick_cache_date = ''
    g.close_sell_cache = {}
    g.max_position_pct = 1
    g.max_hold_count = 1

    run_weekly(prepare_base_stocks, 1, '09:10')
    run_daily(before_open, time='09:11')
    run_daily(precompute_sell_cache, time='09:11')
    run_daily(get_buy, time='09:27')
    run_daily(get_close_sell, time='11:25')
    run_daily(get_close_sell, time='13:30')
    run_daily(get_close_sell, time='14:55')


# ========== 股票池与盘前选股 ==========
def prepare_base_stocks(context):
    """按上市时间、板块、交易状态和流通市值构建基础股票池。"""
    listing_cutoff = context.previous_date - timedelta(days=60)
    all_stocks = list(get_all_securities(['stock'], date=listing_cutoff).index)
    current_data = get_current_data()

    tradable_main_board = [
        code for code in all_stocks
        if not (
            code.startswith(('3', '68', '4', '8', '9'))
            or current_data[code].is_st
            or current_data[code].paused
            or '退' in current_data[code].name
        )
    ]

    fundamentals = get_fundamentals(
        query(valuation.code).filter(
            valuation.code.in_(tradable_main_board),
            valuation.circulating_market_cap.between(
                MIN_CIRCULATING_MARKET_CAP,
                MAX_CIRCULATING_MARKET_CAP,
            ),
        )
    )
    g.base_stocks = fundamentals['code'].tolist()
    log.info(f"[基础股票池] {len(g.base_stocks)}只")
    log_stock_list('基础股票池', g.base_stocks)


def before_open(context):
    """按首板、量价和波动条件生成当日候选股票。"""
    trade_date = context.current_dt.strftime('%Y%m%d')
    previous_date = context.previous_date.strftime('%Y-%m-%d')

    if not g.base_stocks:
        prepare_base_stocks(context)

    first_board = filter_first_board(g.base_stocks, previous_date)
    log.info(f"[盘前] 首板筛选: {len(first_board)}只")
    log_stock_list('首板筛选', first_board)

    volume_price_pass = filter_volume_price(first_board, previous_date)
    log.info(f"[盘前] 量价过滤: {len(volume_price_pass)}只")
    log_stock_list('量价过滤', volume_price_pass)

    selected = filter_high_volatility(volume_price_pass, previous_date)
    log.info(f"[盘前] 过滤高波动股票: {len(selected)}只")
    log_stock_list('波动过滤通过', selected)

    g.today_pick = selected
    g.pick_cache_date = trade_date
    log_before_open_selection(selected, previous_date)
    return selected


def filter_first_board(stock_list, previous_date):
    """筛选昨日涨停、前日未涨停的首板股票。"""
    if not stock_list:
        return []

    df = get_price(
        stock_list,
        end_date=previous_date,
        frequency='daily',
        fields=['close', 'high_limit'],
        count=2,
        panel=False,
        fill_paused=False,
        skip_paused=False,
    )
    if df.empty or len(df['time'].unique()) < 2:
        return []

    limit_up = df[df['close'] == df['high_limit']]
    limit_up_by_day = limit_up.groupby('time')['code'].apply(set)
    if len(limit_up_by_day) < 2:
        return list(limit_up_by_day.iloc[-1]) if len(limit_up_by_day) == 1 else []
    return list(limit_up_by_day.iloc[-1] - limit_up_by_day.iloc[-2])


def filter_volume_price(stock_list, previous_date):
    """筛选成交额、放量、K 线形态和短期涨幅均符合要求的股票。"""
    if not stock_list:
        return []

    df = get_price(
        stock_list,
        end_date=previous_date,
        frequency='1d',
        fields=['close', 'open', 'volume', 'money'],
        count=35,
        skip_paused=True,
        fq='pre',
        panel=False,
    )
    if df.empty:
        log.info('[量价过滤] 历史数据不足')
        return []

    candidates = []
    stage_counts = {
        '历史数据充足': 0,
        '成交额范围': 0,
        '昨日放量': 0,
        '前日量能约束': 0,
        '前两日阳线': 0,
        '收盘价有效': 0,
        '前两日涨幅约束': 0,
    }
    for code, group in df.groupby('code'):
        if len(group) < 6:
            continue
        stage_counts['历史数据充足'] += 1

        group = group.sort_values('time').reset_index(drop=True)
        yesterday, day_before, two_days_before, three_days_before = (
            group.iloc[-1], group.iloc[-2], group.iloc[-3], group.iloc[-4]
        )

        if not MIN_MONEY <= yesterday.money <= MAX_MONEY:
            continue
        stage_counts['成交额范围'] += 1
        if day_before.volume <= 0 or yesterday.volume < day_before.volume * VOLUME_EXPANSION:
            continue
        stage_counts['昨日放量'] += 1
        if two_days_before.volume <= 0 or day_before.volume > two_days_before.volume * PRIOR_VOLUME_LIMIT:
            continue
        stage_counts['前日量能约束'] += 1
        if not (day_before.close > day_before.open and two_days_before.close > two_days_before.open):
            continue
        stage_counts['前两日阳线'] += 1
        if two_days_before.close == 0 or three_days_before.close == 0:
            continue
        stage_counts['收盘价有效'] += 1

        day_before_return = (day_before.close - two_days_before.close) / two_days_before.close
        two_days_before_return = (
            (two_days_before.close - three_days_before.close) / three_days_before.close
        )
        if day_before_return >= MAX_PRIOR_RETURN or two_days_before_return >= MAX_PRIOR_RETURN:
            continue

        stage_counts['前两日涨幅约束'] += 1
        candidates.append(code)

    previous_count = len(stock_list)
    for stage, passed_count in stage_counts.items():
        log.info(
            f"[量价过滤] {stage}: 通过 {passed_count}只, "
            f"本步过滤 {previous_count - passed_count}只"
        )
        previous_count = passed_count
    return candidates


def filter_high_volatility(stock_list, previous_date):
    """剔除近 5 日振幅超过阈值的股票。"""
    if not stock_list:
        return []

    df = get_price(
        stock_list,
        end_date=previous_date,
        frequency='1d',
        fields=['high', 'low'],
        count=5,
        panel=False,
        skip_paused=True,
        fill_paused=False,
    )
    if df.empty:
        return stock_list

    grouped = df.groupby('code')
    five_day_range = (grouped['high'].max() - grouped['low'].min()) / grouped['low'].min()
    return five_day_range[five_day_range <= MAX_FIVE_DAY_RANGE].index.tolist()


def log_before_open_selection(stock_list, previous_date):
    """输出盘前最终入选股票的关键历史指标。"""
    if not stock_list:
        log.info('[盘前入选明细] 无')
        return

    try:
        df = get_price(
            stock_list,
            end_date=previous_date,
            frequency='1d',
            fields=['close', 'high', 'low', 'volume', 'money'],
            count=5,
            panel=False,
            skip_paused=True,
            fill_paused=False,
        )
        if df is None or df.empty:
            log.info(f"[盘前入选明细] {stock_list}: 历史数据为空")
            return
        if 'code' not in df.columns and len(stock_list) == 1:
            df = df.copy()
            df['code'] = stock_list[0]

        for code, group in df.groupby('code'):
            group = group.sort_values('time')
            yesterday = group.iloc[-1]
            lowest = group['low'].min()
            highest = group['high'].max()
            five_day_range = (highest - lowest) / lowest if lowest > 0 else None
            range_text = f'{five_day_range:.2%}' if five_day_range is not None else '无'
            log.info(
                f"[盘前入选] {code}: 昨收={yesterday.close:.2f}, "
                f"昨成交额={yesterday.money / 1e8:.2f}亿, "
                f"昨成交量={yesterday.volume:.0f}, 近5日振幅={range_text}"
            )
    except Exception as error:
        log.error(f"[盘前入选明细错误] {error}")


# ========== 集合竞价与买入 ==========
def filter_auction(stock_list, previous_date, trade_date):
    """按竞价量比和高开幅度筛选股票，并打印入选明细。"""
    if not stock_list:
        return []

    history = get_price(
        stock_list,
        end_date=previous_date,
        frequency='1d',
        fields=['close', 'volume'],
        count=1,
        skip_paused=True,
        panel=False,
        fill_paused=False,
    )
    if history.empty:
        return []

    start = f'{trade_date} 09:15:00'
    end = f'{trade_date} 09:26:00'
    qualified = []
    for stock in stock_list:
        try:
            auction = get_call_auction(
                stock,
                start_date=start,
                end_date=end,
                fields=['time', 'volume', 'current'],
            )
            if auction.empty:
                log.info(f"[竞价淘汰] {stock}: 竞价数据为空")
                continue

            last_auction = auction.iloc[-1]
            yesterday = history[history['code'] == stock].iloc[0]
            if yesterday['volume'] <= 0 or yesterday['close'] <= 0:
                log.info(
                    f"[竞价淘汰] {stock}: 昨日数据无效, "
                    f"昨成交量={yesterday['volume']:.0f}, 昨收={yesterday['close']:.2f}"
                )
                continue

            volume_ratio = last_auction.volume / yesterday['volume']
            gap = last_auction.current / yesterday['close'] - 1
            if volume_ratio < MIN_AUCTION_VOLUME_RATIO:
                log.info(
                    f"[竞价淘汰] {stock}: 量比不足, "
                    f"竞价量={last_auction.volume:.0f}, 昨成交量={yesterday['volume']:.0f}, "
                    f"量比={volume_ratio:.2%} < {MIN_AUCTION_VOLUME_RATIO:.2%}"
                )
                continue
            if gap <= MIN_AUCTION_GAP:
                log.info(
                    f"[竞价淘汰] {stock}: 高开幅度不足, "
                    f"竞价价={last_auction.current:.2f}, 昨收={yesterday['close']:.2f}, "
                    f"高开={gap:.2%} <= {MIN_AUCTION_GAP:.2%}"
                )
                continue
            if gap >= MAX_AUCTION_GAP:
                log.info(
                    f"[竞价淘汰] {stock}: 高开过高, "
                    f"竞价价={last_auction.current:.2f}, 昨收={yesterday['close']:.2f}, "
                    f"高开={gap:.2%} >= {MAX_AUCTION_GAP:.2%}"
                )
                continue

            qualified.append((stock, volume_ratio))
            log.info(
                f"[竞价入选] {stock}: 竞价价={last_auction.current:.2f}, "
                f"昨收={yesterday['close']:.2f}, 竞价量={last_auction.volume:.0f}, "
                f"量比={volume_ratio:.2%}, 高开={gap:.2%}"
            )
        except Exception as error:
            log.info(f"[竞价读取失败] {stock}: {error}")
    qualified.sort(key=lambda item: item[1], reverse=True)
    ordered_stocks = [stock for stock, _ in qualified]
    if ordered_stocks:
        log.info(f"[集合竞价排序] 按量比从高到低: {ordered_stocks}")
    return ordered_stocks


def get_buy(context):
    """在 09:27 根据竞价结果下单买入。"""
    trade_date = context.current_dt.strftime('%Y%m%d')
    trade_date_str = context.current_dt.strftime('%Y-%m-%d')
    previous_date = context.previous_date.strftime('%Y-%m-%d')
    current_data = get_current_data()

    holdings = [
        stock for stock, position in context.portfolio.positions.items()
        if position.total_amount > 0
    ]
    if len(holdings) >= g.max_hold_count:
        log.info(f"[持仓已达上限] {g.max_hold_count}只")
        return

    if g.pick_cache_date != trade_date:
        before_open(context)

    candidates = [stock for stock in g.today_pick if stock not in holdings]
    log.info(f"[排除持仓后] {candidates}")
    log_stock_list('排除持仓后', candidates)
    if not candidates:
        return

    qualified = filter_auction(candidates, previous_date, trade_date_str)
    log.info(f"[集合竞价过滤后] {qualified}")
    log_stock_list('集合竞价通过', qualified)
    if not qualified:
        return

    slots = g.max_hold_count - len(holdings)
    to_buy = qualified[:slots]
    log_stock_list('最终拟买', to_buy)
    max_per_stock = context.portfolio.total_value * g.max_position_pct
    per_stock = min(context.portfolio.available_cash / len(to_buy), max_per_stock)
    log.info(
        f"[分配资金] 当前持仓{len(holdings)}只, 可再买{slots}只, "
        f"每只分配{per_stock:.2f}"
    )

    for stock in to_buy:
        try:
            open_price = current_data[stock].day_open
            shares = int(per_stock / open_price / 100) * 100
            log.info(
                f"[买入计划] {stock}: 开盘价={open_price:.2f}, "
                f"计划金额={per_stock:.2f}, 预计={shares}股"
            )
            if shares < 100:
                log.info(f"[买入跳过] {stock}: 资金不足1手")
                continue

            order_value(stock, per_stock, MarketOrderStyle(open_price))
            log.info(f"[买入下单] {stock}: 开盘价={open_price:.2f}, 计划金额={per_stock:.2f}")
            g.information[stock] = {'buy_date': trade_date}
        except Exception as error:
            log.info(f"[买入错误] {stock}: {error}")


# ========== 持仓管理与收盘清理 ==========
def precompute_sell_cache(context):
    """盘前缓存昨收和 MA5，避免卖出时重复请求日线数据。"""
    positions = list(context.portfolio.positions.keys())
    g.close_sell_cache = {}
    if not positions:
        return

    df = get_price(
        positions,
        end_date=context.previous_date,
        frequency='1d',
        fields=['close'],
        count=5,
        panel=False,
        skip_paused=False,
        fill_paused=True,
    )
    for stock, closes in df.groupby('code')['close']:
        if len(closes) >= 2:
            g.close_sell_cache[stock] = {
                'y_close': closes.iloc[-1],
                'ma5': closes.mean(),
            }


def get_close_sell(context):
    """在固定时点检查持仓的止盈、止损和均线破位条件。"""
    trade_date = context.current_dt.strftime('%Y%m%d')
    holdings = [
        stock for stock, position in context.portfolio.positions.items()
        if position.total_amount > 0
        and g.information.get(stock, {}).get('buy_date') != trade_date
    ]
    if not holdings:
        return

    log_stock_list('卖出检查持仓', holdings)

    current_data = get_current_data()
    for stock in holdings:
        metrics = g.close_sell_cache.get(stock)
        if metrics is None:
            continue

        position = context.portfolio.positions[stock]
        current = current_data[stock]
        current_price = current.last_price
        day_change = (current_price - metrics['y_close']) / metrics['y_close']
        position_return = (current_price - position.avg_cost) / position.avg_cost
        ma5 = metrics['ma5']

        log.info(
            f"[持仓检查] {stock}: 现价={current_price:.2f}, 成本={position.avg_cost:.2f}, "
            f"收益={position_return:.2%}, 当日涨跌={day_change:.2%}, MA5={ma5:.2f}"
        )
        if current_price >= current.high_limit * 0.985:
            log.info(f"[持有] {stock}: 接近涨停，继续持有")
            continue

        sell, reason = False, ''
        if position_return > 0.5:
            sell, reason = True, '收益>50%'
        if day_change < -0.02:
            sell, reason = True, f"当日涨幅<-2% ({day_change:.2%})"
        elif current_price < current.day_open * 0.96:
            sell, reason = True, f"当前价<开盘价的-4% ({current_price:.2f}<{current.day_open * 0.96:.2f})"
        elif position_return <= -0.07:
            sell, reason = True, f"收益<=-7% ({position_return:.2%})"
        elif current_price < ma5 * 0.97:
            sell, reason = True, f"跌破5日均线-3% ({current_price:.2f}<{ma5 * 0.97:.2f})"

        if sell:
            order_target_value(stock, 0)
            log.info(f"[卖出] {stock}: {reason}，清仓")
        else:
            log.info(f"[持有] {stock}: 无卖出条件触发")


def after_trading_end(context):
    """收盘后只保留仍在持仓中的状态和卖出缓存。"""
    holdings = set(context.portfolio.positions.keys())
    g.information = {
        stock: info for stock, info in g.information.items() if stock in holdings
    }
    g.close_sell_cache = {
        stock: metrics for stock, metrics in g.close_sell_cache.items() if stock in holdings
    }
