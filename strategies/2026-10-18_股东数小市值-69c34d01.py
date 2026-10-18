# Clone from JoinQuant
# postId: 69c34d01214f050d116d7b4fa4c07b31
# backtestId: 99fb76916e92f2fe436d63c26dcfbdf0
# title: 股东数小市值

# 股东户数小市值策略
# 
#
# 核心逻辑：小市值池内，按"股东户数"打分排名
#   买入股东户数少的：股东户数少（户均流通市值大）、且户数在下降（筹码集中）
#   卖出股东户数多的：跌出低散户池的（户数激增/户均市值变小）随周度调仓卖出
#
# 打分方式（数据源：finance.STK_HOLDER_NUM 股东户数表，pub_date 对齐防未来函数）：
#   户均流通市值 = 流通市值 / 股东户数        → 分位排名 × 100，越大 = 散户越少 → 分越高
#   户数变化率   = 本期户数 / 上期户数 - 1    → (1 - 分位排名) × 100，降幅大 = 筹码集中 → 分越高
#   综合得分 = 0.4 × 户均分 + 0.6 × 户变分（0-100，户数越少分越高，户数变化为主导）
#   选股流程：
#     候选池(市值5-50亿前150只) → 综合得分排名 → 得分前 retail_pool_pct 进"低散户池"
#     → 池内按市值升序(g.pool_inner_sort='mv') 或 得分降序('score') 取前 N 只
#
# 注意：
# 1. 股东户数只在定期报告中强制披露（部分公司按月披露），数据低频，适合周/月频调仓。
# 2. 查询用 pub_date <= 上一交易日 截断，配合 avoid_future_data，回测无未来函数。
# 3. finance.run_query 单次有行数上限，通过"先选小市值前 candidate_num 只 + 回溯400天"控制行数。

import datetime
import math
import numpy as np
import pandas as pd
from jqdata import *
from prettytable import PrettyTable

""" ====================== 基础设置 ====================== """

def initialize(context):
    set_backtest()  # 设置回测条件
    set_params(context)  # 设置参数

    # 过滤日志
    log.set_level('order', 'error')

    # === 定时任务配置 ===

    # 1. 每日开盘前检测大盘顶背离 (DBL)
    if g.DBL_control:
        run_daily(check_dbl, '9:31')

    # 2. 每周一进行买卖操作（散户持仓因子选股）
    run_weekly(strategy_1_sell, 1, '09:49')
    run_weekly(strategy_1_buy, 1, '09:50')

    # 3. 每日盘中检查
    # 换手率放量/缩量检查
    if g.huanshou_check:
        run_daily(xsz_huanshou_check, '10:30')

    # 止盈止损检查 (10:35)
    run_daily(take_profit_stop_loss, '10:35')

    # 昨日涨停股检查 (14:00)
    run_daily(check_limit_up, '14:00')

    # 4. 打印持仓日报
    run_daily(print_summary, '15:02')

# 回测环境设置
def set_backtest():
    set_option('avoid_future_data', True)
    set_benchmark('000001.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.002), type="stock")

    # 设置手续费
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.85/10000, close_commission=0.85/10000,
        close_today_commission=0, min_commission=5
    ), type="stock")

# 参数设置
def set_params(context):
    # === 策略核心参数 ===
    g.xsz_stock_num = 5        # 持股数量
    g.min_mv = 5               # 最小市值(亿)
    g.max_mv = 50              # 最大市值(亿)
    g.up_price = 20            # 个股价格上限

    # === 散户持仓因子参数 ===
    g.enable_holder_factor = True   # False 则退化为纯小市值轮动（按市值升序）
    g.candidate_num = 150           # 市值最小的前N只进入因子打分
    g.holder_lookback_days = 400    # 股东户数查询回溯窗口(自然日)，需覆盖基准期与最新期
    g.mv_weight = 0.4               # 户均流通市值得分权重（存量散户多少）
    g.chg_weight = 0.6              # 户数变化率得分权重（筹码集中趋势，主导项）
    g.retail_pool_pct = 0.3         # 得分最高的前30%进入"低散户持仓池"（涨停基因取前10%，可收紧）
    g.pool_inner_sort = 'mv'        # 池内排序：'mv'=市值升序(涨停基因风格) / 'score'=散户得分降序
    g.filter_profit = True          # 仅保留净利润>0的小市值股

    # === 状态变量 ===
    g.target_list = []        # 目标持仓股票
    g.yesterday_HL_list = []  # 昨日涨停股票
    g.no_buy_stocks = {}      # 黑名单（止损后短期不买）
    g.check_after_no_buy = True
    g.no_buy_after_day = 3    # 止损后不买入的时间窗口

    # === 风控配置 ===

    # 1. 顶背离(DBL)配置
    g.DBL_control = True      # 开关
    g.dbl = []
    g.check_dbl_days = 10     # 检测窗口

    # 2. 止盈止损配置
    g.run_stoploss = True
    g.use_move_stoploss = False
    g.stoploss_limit = 0.09   # 止损线 9%
    g.stop_loss_tracking = {}

    # 3. 换手率检查配置
    g.huanshou_check = True

""" ====================== 散户持仓因子 ====================== """

def get_retail_factor(context, stock_list):
    """
    获取散户持仓因子（截止上一交易日披露的数据）：
      mv_per_holder: 户均流通市值(万元/户)，越大 = 户数越少 = 散户越少
      holder_chg   : 股东户数较上期变化率，越小(负) = 筹码越集中 = 散户在减少
    返回以 code 为索引的 DataFrame；窗口内无户数披露的股票不出现在结果中。
    """
    end_date = context.previous_date
    start_date = end_date - datetime.timedelta(days=g.holder_lookback_days)

    q = query(
        finance.STK_HOLDER_NUM.code,
        finance.STK_HOLDER_NUM.pub_date,
        finance.STK_HOLDER_NUM.share_holders,
    ).filter(
        finance.STK_HOLDER_NUM.code.in_(stock_list),
        finance.STK_HOLDER_NUM.pub_date > start_date,
        finance.STK_HOLDER_NUM.pub_date <= end_date,
        finance.STK_HOLDER_NUM.share_holders > 0,
    ).order_by(
        finance.STK_HOLDER_NUM.pub_date.asc()
    )

    try:
        df = finance.run_query(q)
    except Exception as e:
        # 表结构或平台版本差异导致查询失败时，退化为纯市值选股而不是中断回测
        print(f"⚠️ [散户持仓因子] 股东户数查询失败: {e}")
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    # 户数环比变化率（组内按公告日期升序，即最新一期 vs 上一期披露）
    df['holder_chg'] = df.groupby('code')['share_holders'].pct_change()

    # 每只股票只取"已披露的最近一期"（pub_date <= 上一交易日，防未来函数）
    latest = df.groupby('code').tail(1).set_index('code')

    # 当日流通市值（亿元）
    mv = get_fundamentals(query(
        valuation.code,
        valuation.circulating_market_cap,
    ).filter(
        valuation.code.in_(stock_list)
    ), date=end_date).set_index('code')

    out = latest[['share_holders', 'holder_chg', 'pub_date']].join(
        mv[['circulating_market_cap']], how='inner')
    out = out[out['circulating_market_cap'] > 0]

    # 户均流通市值（万元/户）= 市值(亿)*1e8 / 户数 / 1e4
    out['mv_per_holder'] = out['circulating_market_cap'] * 1e8 / out['share_holders'] / 1e4
    # 窗口内只有一期披露的股票，变化率记为中性 0
    out['holder_chg'] = out['holder_chg'].fillna(0.0)
    return out

def score_by_retail_factor(factor_df):
    """
    散户持仓打分（0-100，越高 = 散户持仓越少）：
      户均分 = 户均流通市值的分位排名 × 100（越大 = 户数越少 = 散户越少）
      户变分 = (1 - 户数变化率的分位排名) × 100（降幅越大 = 筹码越集中 = 散户在减少）
      综合得分 = 0.4 × 户均分 + 0.6 × 户变分（户数变化为主导）
    返回按综合得分降序排列的 DataFrame。
    """
    df = factor_df.copy()
    df['mv_score'] = df['mv_per_holder'].rank(pct=True) * 100
    df['chg_score'] = (1 - df['holder_chg'].rank(pct=True)) * 100
    df['retail_score'] = g.mv_weight * df['mv_score'] + g.chg_weight * df['chg_score']
    return df.sort_values('retail_score', ascending=False)

def log_retail_table(context, scored_df, target_list, pool_num):
    """打印本次调仓的因子明细表，便于核对买卖方向"""
    table = PrettyTable(["名称", "代码", "市值(亿)", "户数(万)", "户均市值(万)",
                         "户数变化", "户均分", "户变分", "综合分", "方向"])
    for stock in target_list:
        if stock not in scored_df.index:
            continue
        row = scored_df.loc[stock]
        try:
            name = get_security_info(stock).display_name
        except Exception:
            name = stock[:6]
        table.add_row([
            name, stock[:6],
            f"{row['circulating_market_cap']:.1f}",
            f"{row['share_holders'] / 1e4:.2f}",
            f"{row['mv_per_holder']:.1f}",
            f"{row['holder_chg']:+.1%}",
            f"{row['mv_score']:.0f}",
            f"{row['chg_score']:.0f}",
            f"{row['retail_score']:.1f}",
            "买入/持有",
        ])
    print(f"[散户持仓因子] 候选{len(scored_df)}只 → 低散户池{pool_num}只"
          f"（得分前{g.retail_pool_pct:.0%}，散户越少分越高，户变权重{g.chg_weight:.1f}） → 最终{len(target_list)}只")
    print(table)

""" ====================== 选股与交易逻辑 ====================== """

# 选股核心模块
def xsz_get_stock_list(context):
    initial_list = filter_stocks(context, get_index_stocks('399101.XSHE'))

    # 基本面筛选：小市值优先，取前 candidate_num 只进入因子打分
    q = query(
        valuation.code,
        valuation.market_cap,
    )
    if g.filter_profit:
        q = q.filter(income.np_parent_company_owners > 0)
    q = q.filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(g.min_mv, g.max_mv),
    ).order_by(valuation.market_cap.asc()).limit(g.candidate_num)

    df = get_fundamentals(q)
    if df.empty:
        return []
    candidates = list(df.code)

    # 散户持仓因子打分
    if g.enable_holder_factor:
        factor_df = get_retail_factor(context, candidates)
        if factor_df.empty:
            print("⚠️ [散户持仓因子] 未取到股东户数数据，本次退化为按市值升序选股")
            final_list = candidates
        else:
            dropped = len(candidates) - len(factor_df)
            if dropped > 0:
                print(f"[散户持仓因子] {dropped}只候选股窗口内无户数披露，已剔除")
            scored_df = score_by_retail_factor(factor_df)

            # 参考涨停基因的选股结构：得分最高的前 retail_pool_pct 进入"低散户持仓池"
            pool_num = max(g.xsz_stock_num, int(len(scored_df) * g.retail_pool_pct))
            pool_df = scored_df.head(pool_num)

            # 池内排序：'mv' = 按市值升序（涨停基因小市值同款，散户因子做门槛）；'score' = 按散户得分降序
            if g.pool_inner_sort == 'score':
                final_list = list(pool_df.index)
            else:
                final_list = list(pool_df.sort_values('circulating_market_cap').index)

            log_retail_table(context, scored_df, final_list[:g.xsz_stock_num], pool_num)
    else:
        final_list = candidates

    # 价格过滤（已持仓股保留，避免因涨价被直接调出）
    last_prices = history(1, '1d', 'close', final_list, df=False)
    return [stock for stock in final_list
            if stock in context.portfolio.positions or last_prices[stock] <= g.up_price][:g.xsz_stock_num]

# 卖出逻辑
def strategy_1_sell(context):
    g.target_list = []

    # 1. 大盘顶背离风控
    if g.DBL_control:
        # 首次运行检测最近10日顶背离
        if len(g.dbl) < 10:
            for i in range(9, -1, -1):
                check_dbl(context, end_days=0 - i)

        # 如果近10天有触发顶背离，暂停交易并清仓（非涨停）
        if 1 in g.dbl[-g.check_dbl_days:]:
            print(f"近{g.check_dbl_days}日检测到大盘顶背离，暂停调仓以控制风险")
            return

    current_data = get_current_data()

    # 2. 获取最新选股目标（散户持仓少的优先）
    g.target_list = xsz_get_stock_list(context)[:g.xsz_stock_num]
    print(f'目标持仓(散户少): {g.target_list}')

    # 3. 卖出不在目标列表中的股票（除昨日涨停股）
    #    散户持仓升高（排名跌出目标池）的股票在此处被换出
    sell_list = [s for s in context.portfolio.positions.keys()
                 if s not in g.target_list and s not in g.yesterday_HL_list]
    for stock in sell_list:
        if current_data[stock].paused:
            print(f"{stock} 停牌, 无法卖出")
        else:
            close_position(context, stock)
            print(f"卖出(散户持仓偏高/调出目标池): {stock}")

# 买入逻辑
def strategy_1_buy(context):
    # 计算可用资金 (全仓模式)
    current_value = context.portfolio.total_value

    # 买入新标的
    buy_list = [s for s in g.target_list if s not in context.portfolio.positions]

    if buy_list and context.portfolio.available_cash > 0:
        # 简单均分资金，实际交易时可能会有剩余
        cash_per_stock = context.portfolio.available_cash / len(buy_list)
        for stock in buy_list:
            open_position(context, stock, cash_per_stock)
            print(f"买入(散户持仓少): {stock}, 金额: {cash_per_stock:.2f}")

""" ====================== 风控模块 ====================== """

# 大盘顶背离检测 (DBL)
def check_dbl(context, market_index='399101.XSHE', end_days=0):
    # 避免第一次9:31造成的干扰
    if not g.dbl and "9:31" in str(context.current_dt.time()):
        return

    def detect_divergence():
        fast, slow, sign = 12, 26, 9
        rows = (fast + slow + sign) * 5
        grid = attribute_history(market_index, rows + 10, fields=['close']).dropna()
        if end_days < 0:
            grid = grid.iloc[:end_days]

        if len(grid) < rows:
            return False

        try:
            grid['dif'], grid['dea'], grid['macd'] = mcad(grid.close, fast, slow, sign)
            mask = (grid['macd'] < 0) & (grid['macd'].shift(1) >= 0)
            if mask.sum() < 2:
                return False

            key2, key1 = mask[mask].index[-2], mask[mask].index[-1]
            price_cond = grid.close[key2] < grid.close[key1]
            dif_cond = grid.dif[key2] > grid.dif[key1] > 0
            macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]

            if len(grid['dif']) > 20:
                recent_avg = grid['dif'].iloc[-10:].mean()
                prev_avg = grid['dif'].iloc[-20:-10].mean()
                trend_cond = recent_avg < prev_avg
            else:
                trend_cond = False

            return price_cond and dif_cond and macd_cond and trend_cond

        except Exception as e:
            print(f"顶背离检测错误: {e}")
            return False

    if detect_divergence():
        g.dbl.append(1)
        print(f"⚠️⚠️⚠️⚠️ 检测到{market_index}顶背离信号，清仓非涨停股票")
        current_data = get_current_data()
        for stock in list(context.portfolio.positions.keys()):
            if current_data[stock].last_price < current_data[stock].high_limit:
                print(f"{stock} 因大盘顶背离清仓（非涨停股）")
                close_position(context, stock)
    else:
        g.dbl.append(0)

# 换手率检查
def xsz_huanshou_check(context):
    def huanshoulv(_stock, is_avg=False):
        if is_avg:
            end_date = context.previous_date
            df_volume = get_price(_stock, end_date=end_date, frequency='daily', fields=['volume'], count=20)
            df_cap = get_valuation(_stock, end_date=end_date, fields=['circulating_cap'], count=1)
            circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
            if circulating_cap == 0:
                return 0.0
            df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
            return df_volume['turnover_ratio'].mean()
        else:
            date_now = context.current_dt
            df_vol = get_price(_stock, start_date=date_now.date(), end_date=date_now, frequency='1m', fields=['volume'],
                               skip_paused=False, fq='pre', panel=True, fill_paused=False)
            volume = df_vol['volume'].sum()
            date_pre = context.previous_date
            df_circulating_cap = get_valuation(_stock, end_date=date_pre, fields=['circulating_cap'], count=1)
            circulating_cap = df_circulating_cap['circulating_cap'].iloc[0] if not df_circulating_cap.empty else 0
            if circulating_cap == 0:
                return 0.0
            turnover_ratio = volume / (circulating_cap * 10000)
            return turnover_ratio

    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in list(context.portfolio.positions.keys()):
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue

        rt = huanshoulv(stock, False)
        avg = huanshoulv(stock, True)
        if avg == 0:
            continue
        r = rt / avg
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        if action:
            print(f"{action} {stock} {get_stock_name(stock)}  换手率:{rt:.2%}  均:{avg:.2%} 倍率:x{r:.1f} {icon}")
            close_position(context, stock)

# 止盈止损
def take_profit_stop_loss(context):
    if not g.run_stoploss:
        return

    # 更新黑名单计数
    no_buy_stocks = {}
    for k, v in g.no_buy_stocks.items():
        v += 1
        if v <= g.no_buy_after_day:
            no_buy_stocks[k] = v
    g.no_buy_stocks = no_buy_stocks

    current_data = get_current_data()

    # 移动止损逻辑
    if g.use_move_stoploss:
        for stock, position in context.portfolio.positions.items():
            if current_data[stock].paused: continue
            current_price = current_data[stock].last_price
            if stock not in g.stop_loss_tracking:
                g.stop_loss_tracking[stock] = max(position.avg_cost, current_price)
            else:
                g.stop_loss_tracking[stock] = max(g.stop_loss_tracking[stock], current_price)

            highest_price = g.stop_loss_tracking[stock]
            if current_price <= highest_price * (1 - g.stoploss_limit):
                close_position(context, stock)
                g.no_buy_stocks[stock] = 1
                print(f"移动止损卖出 {stock}, 亏损:{(1 - position.price / position.avg_cost):.2%}")

    # 固定止盈止损逻辑
    for stock, pos in context.portfolio.positions.items():
        if current_data[stock].paused: continue

        # 止盈：100%
        if pos.price >= pos.avg_cost * 2:
            close_position(context, stock)
            g.no_buy_stocks[stock] = 1
            print(f"止盈卖出 {stock}, 收益率:{(pos.price / pos.avg_cost - 1):.2%}")

        # 止损：9%
        if not g.use_move_stoploss and pos.price <= pos.avg_cost * (1 - g.stoploss_limit):
            close_position(context, stock)
            g.no_buy_stocks[stock] = 1
            print(f"止损卖出 {stock}, 亏损:{(1 - pos.price / pos.avg_cost):.2%}")

# 检查昨日涨停
def check_limit_up(context):
    holdings = list(context.portfolio.positions.keys())
    g.yesterday_HL_list = []
    if holdings:
        valid_holdings = [s for s in holdings if isinstance(s, str) and '.' in s]
        if valid_holdings:
            df = get_price(valid_holdings, end_date=context.previous_date,
                           frequency='daily', fields=['close', 'high_limit'],
                           count=1, panel=False)
            if not df.empty:
                g.yesterday_HL_list = list(df[df['close'] >= df['high_limit'] * 0.997].index)

    for stock in g.yesterday_HL_list:
        try:
            current_data = get_current_data()[stock]
            if current_data.last_price < current_data.high_limit * 0.99:
                print(f"涨停打开卖出 {stock}")
                close_position(context, stock)
                g.no_buy_stocks[stock] = 1
        except Exception:
            pass

""" ====================== 工具函数 ====================== """

def filter_stocks(context, stock_list):
    current_data = get_current_data()
    filtered = []
    for stock in stock_list:
        if current_data[stock].paused: continue
        if current_data[stock].is_st: continue
        if '退' in current_data[stock].name: continue
        if stock.startswith(('30', '68', '8', '4')): continue

        ipo_date = get_security_info(stock).start_date
        if (context.current_dt.date() - ipo_date).days < 365: continue

        last_price = current_data[stock].last_price
        if last_price >= current_data[stock].high_limit: continue
        if last_price <= current_data[stock].low_limit: continue

        if g.check_after_no_buy:
            if stock in g.no_buy_stocks:
                continue
        filtered.append(stock)
    return filtered

def mcad(close, short=12, long=26, m=9):
    def ema(series, n):
        return pd.Series.ewm(series, span=n, min_periods=n - 1, adjust=False).mean()
    dif = ema(close, short) - ema(close, long)
    dea = ema(dif, m)
    return dif, dea, (dif - dea) * 2

def get_stock_name(security):
    try:
        return get_security_info(security).display_name
    except:
        return "Unknown"

def open_position(context, security, value):
    return order_target_value(security, value)

def close_position(context, security):
    return order_target_value(security, 0)

def print_summary(context):
    table = PrettyTable(["股票名称", "代码", "持仓", "成本", "现价", "盈亏", "市值"])
    total_val = 0
    for stock, pos in context.portfolio.positions.items():
        pnl = (pos.price - pos.avg_cost) * pos.total_amount
        table.add_row([get_stock_name(stock), stock[:6], pos.total_amount, f"{pos.avg_cost:.2f}",
                       f"{pos.price:.2f}", f"{pnl:.2f}", f"{pos.value:.2f}"])
        total_val += pos.value
    print(f"总资产: {context.portfolio.total_value:.2f} 持仓市值: {total_val:.2f}")
    print(table)