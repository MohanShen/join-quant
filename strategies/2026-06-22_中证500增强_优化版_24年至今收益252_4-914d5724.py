# Clone from JoinQuant
# postId: 914d5724487bceb9332af8b3541d8c9c
# backtestId: e8e43efd9aa58e7bf25b49bf9c23b405
# title: 【中证500增强】优化版：24年至今收益252.4%

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import timedelta as td

# 初始化函数
def initialize(context):
    # 设定基准
    set_benchmark('000905.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为价格的0.02%（更贴近实际）
    set_slippage(PriceRelatedSlippage(0.002))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')

    # ============ 核心参数（优化后） ============
    g.no_trading_today_signal = False
    g.stock_num = 2  # 每个因子组合选股数量 -> 适度集中
    g.max_hold_num = 9  # 最大持仓数量（适度集中以提高收益）
    g.top_pct = 0.08  # 因子排名前百分比 -> 更严格的筛选
    g.hold_list = []
    g.yesterday_HL_list = []
    g.limit_up_hold_days = {}  # 记录涨停股持有天数
    g.max_limit_up_days = 1  # 涨停股最大持有天数（从3缩短到1）

    # ============ 风控参数（优化后） ============
    g.max_drawdown = 0.12  # 最大回撤止损阈值
    g.single_stop_loss = -0.05  # 个股止损线
    g.single_take_profit = 0.25  # 个股止盈线
    g.trailing_trigger = 0.12  # 触发跟踪止损的收益率（12%）
    g.trailing_stop = 0.07  # 跟踪止损幅度（7%）
    g.trailing_peaks = {}  # 记录持仓最高价，用于跟踪止损

    g.market_timing = True  # 是否开启大盘择时
    g.timing_position_ratio = 1.0  # 择时仓位比例（1.0=满仓）
    g.peak_value = 0  # 记录账户峰值

    # ============ 因子列表 ============
    g.factor_list = [
        (
            [
                'ARBR',
                'SGAI',
                'net_profit_to_total_operate_revenue_ttm',
                'retained_profit_per_share'
            ],
            [
                -2.3425,
                -694.7936,
                -170.0463,
                -1362.5762
            ]
        ),
        (
            [
                'Price1Y',
                'total_profit_to_cost_ratio',
                'VOL120'
            ],
            [
                -0.0647128120839873,
                -0.006385116279168804,
                -0.0029867925845833217
            ]
        ),
        (
            [
                'price_no_fq',
                'total_profit_to_cost_ratio',
                'inventory_turnover_rate'
            ],
            [
                -6.123355346008858e-05,
                -0.002579342458393642,
                -2.194257357346814e-06
            ]
        ),
        (
            [
                'debt_to_assets',
                'operating_cost_to_operating_revenue_ratio',
                'DAVOL20',
                'price_no_fq',
                'sales_growth'
            ],
            [
                0.04477354820057883,
                0.021636407482421707,
                -0.01864268317469762,
                -0.0004678118383947827,
                0.02884867440332058
            ]
        ),
        (
            [
                'TVSTD6',
                'cashflow_per_share_ttm',
                'sharpe_ratio_120',
                'non_operating_net_profit_ttm'
            ],
            [
                -5.394060941494863e-12,
                4.6306072704138405e-05,
                -0.0030567075906980912,
                1.4227113275455325e-12
            ]
        )
    ]

    # 调仓与检查频率：改为每日调仓（更短冷静期、提高回报）
    run_daily(prepare_stock_list, '9:05')
    run_daily(daily_rebalance, '9:35')
    run_daily(check_limit_up, '14:00')
    run_daily(intraday_risk_check, '10:30')
    run_daily(close_account, '14:30')
    run_daily(print_position_info, '15:10')

# ============ 大盘择时模块 ============
def get_timing_position_ratio(context):
    if not g.market_timing:
        return 1.0

    benchmark = '000905.XSHG'
    prices = attribute_history(benchmark, 70, '1d', ['close'], df=True)
    if len(prices) < 60:
        return 1.0

    ma20 = prices['close'].iloc[-20:].mean()
    ma60 = prices['close'].iloc[-60:].mean()
    current_price = prices['close'].iloc[-1]

    if current_price > ma20 and ma20 > ma60:
        return 1.0
    elif current_price > ma20:
        return 0.8
    elif current_price > ma60:
        return 0.5
    else:
        return 0.3

# ============ 盘中风控检查（包含跟踪止损） ============
def intraday_risk_check(context):
    current_value = context.portfolio.total_value

    if current_value > g.peak_value:
        g.peak_value = current_value

    if g.peak_value > 0:
        drawdown = (g.peak_value - current_value) / g.peak_value
        if drawdown > g.max_drawdown:
            log.info("触发最大回撤止损，回撤: %.2f%%，清仓" % (drawdown * 100))
            for stock in list(context.portfolio.positions.keys()):
                position = context.portfolio.positions[stock]
                if position.total_amount > 0:
                    close_position(position)
            return

    for stock, position in list(context.portfolio.positions.items()):
        if position.total_amount == 0:
            continue
        if position.avg_cost > 0:
            ret = (position.price - position.avg_cost) / position.avg_cost

            if ret < g.single_stop_loss:
                log.info("[%s]触发止损，收益率: %.2f%%，卖出" % (stock, ret * 100))
                close_position(position)
                if stock in g.trailing_peaks:
                    del g.trailing_peaks[stock]
                continue
            elif ret > g.single_take_profit:
                log.info("[%s]触发止盈目标，收益率: %.2f%%，卖出" % (stock, ret * 100))
                close_position(position)
                if stock in g.trailing_peaks:
                    del g.trailing_peaks[stock]
                continue

            if stock not in g.trailing_peaks or position.price > g.trailing_peaks.get(stock, 0):
                g.trailing_peaks[stock] = position.price

            peak_price = g.trailing_peaks.get(stock, position.price)
            if peak_price > 0:
                pullback = (peak_price - position.price) / peak_price
            else:
                pullback = 0

            if (position.price - position.avg_cost) / position.avg_cost >= g.trailing_trigger:
                if pullback >= g.trailing_stop:
                    log.info("[%s]触发跟踪止损（回撤%.2f%%），卖出" % (stock, pullback * 100))
                    close_position(position)
                    if stock in g.trailing_peaks:
                        del g.trailing_peaks[stock]

# 1-1 准备股票池
def prepare_stock_list(context):
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        if position.total_amount > 0:
            g.hold_list.append(stock)

    if g.hold_list != []:
        try:
            df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                        fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
            df = df[df['close'] == df['high_limit']]
            g.yesterday_HL_list = list(df.code)
        except:
            g.yesterday_HL_list = []
    else:
        g.yesterday_HL_list = []

    for stock in g.yesterday_HL_list:
        if stock in g.limit_up_hold_days:
            g.limit_up_hold_days[stock] += 1
        else:
            g.limit_up_hold_days[stock] = 1

    for stock in list(g.limit_up_hold_days.keys()):
        if stock not in g.hold_list:
            del g.limit_up_hold_days[stock]

    g.no_trading_today_signal = (
        today_is_between(context, '04-10', '04-20') or
        today_is_between(context, '08-25', '08-28')
    )

    if g.peak_value == 0:
        g.peak_value = context.portfolio.total_value

# 1-2 选股模块
def get_stock_list(context):
    yesterday = context.previous_date
    today = context.current_dt
    initial_list = get_all_securities('stock', today).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)

    stock_scores = {}

    for factor_list, coef_list in g.factor_list:
        try:
            factor_values = get_factor_values(initial_list, factor_list, end_date=yesterday, count=1)
        except:
            continue

        df = pd.DataFrame(index=initial_list, columns=factor_list)
        for i in range(len(factor_list)):
            try:
                df[factor_list[i]] = list(factor_values[factor_list[i]].T.iloc[:, 0])
            except:
                df[factor_list[i]] = np.nan
        df = df.dropna()

        if df.shape[0] == 0:
            continue

        for col in factor_list:
            mean_val = df[col].mean()
            std_val = df[col].std()
            if std_val > 0:
                df[col] = (df[col] - mean_val) / std_val
            else:
                df[col] = 0

        df['total_score'] = 0
        for i in range(len(factor_list)):
            df['total_score'] += coef_list[i] * df[factor_list[i]]

        df = df.sort_values(by=['total_score'], ascending=False)
        k = max(1, int(g.top_pct * len(df.index)))
        complex_factor_list = list(df.index)[:k]

        for stock in complex_factor_list:
            if stock not in stock_scores:
                stock_scores[stock] = 0
            stock_scores[stock] += 1

    score_df = pd.DataFrame(list(stock_scores.items()), columns=['code', 'score'])
    if score_df.shape[0] == 0:
        candidate_list = []
    else:
        score_df = score_df.sort_values(by='score', ascending=False)
        candidate_list = list(score_df['code'])[: max(len(score_df), g.max_hold_num * 3)]

    final_candidate = []
    if len(candidate_list) > 0:
        try:
            q = query(
                valuation.code,
                valuation.circulating_market_cap,
                indicator.eps,
                indicator.roe
            ).filter(
                valuation.code.in_(candidate_list)
            ).order_by(
                valuation.circulating_market_cap.asc()
            )
            df_f = get_fundamentals(q)
            df_f = df_f[df_f['eps'] > 0]
            df_f = df_f[df_f['roe'] > 3]
            final_candidate = list(df_f.code)
        except:
            final_candidate = candidate_list

    final_candidate = filter_paused_stock(final_candidate)
    final_candidate = filter_limitup_stock(context, final_candidate)
    final_candidate = filter_limitdown_stock(context, final_candidate)

    final_list = industry_diversify(final_candidate, g.max_hold_num, max_industry_num=3)

    if len(final_list) < g.max_hold_num:
        for s in candidate_list:
            if s not in final_list and s in final_candidate:
                final_list.append(s)
            if len(final_list) >= g.max_hold_num:
                break

    return final_list[:g.max_hold_num]

# 行业分散化
def industry_diversify(stock_list, max_num, max_industry_num=3):
    if len(stock_list) == 0:
        return []

    industry_count = {}
    result = []

    try:
        industry_dict = get_industry(stock_list)
    except:
        industry_dict = {}

    for stock in stock_list:
        try:
            if stock in industry_dict and 'sw_l1' in industry_dict[stock]:
                ind_code = industry_dict[stock]['sw_l1']['industry_code']
            else:
                ind_code = 'unknown'
        except:
            ind_code = 'unknown'

        if ind_code not in industry_count:
            industry_count[ind_code] = 0

        if industry_count[ind_code] < max_industry_num:
            result.append(stock)
            industry_count[ind_code] += 1

        if len(result) >= max_num:
            break

    return result

def compute_mom20(stock_list, end_date):
    """
    计算 20 日动量：close_t / close_{t-20} - 1，返回 pandas.Series，index 为股票代码。
    建议放在工具函数区（如 industry_diversify 之后），供 get_stock_list 调用。
    """
    import numpy as np
    import pandas as pd

    if not stock_list:
        return pd.Series(dtype=float)

    # 尝试一次性批量获取 21 日收盘价（高效优先）
    pivot = pd.DataFrame()
    try:
        price_df = get_price(stock_list, end_date=end_date, frequency='1d', fields=['close'], count=21,
                             panel=False, fill_paused=True)
        if isinstance(price_df, pd.DataFrame):
            if 'code' in price_df.columns and 'close' in price_df.columns:
                pivot = price_df.pivot(index='date', columns='code', values='close')
            else:
                # 有些平台会直接返回以代码为列的 DataFrame
                pivot = price_df
    except Exception:
        pivot = pd.DataFrame()

    mom = {}
    # 如果批量结果有效且行数足够，用向量化计算
    try:
        if isinstance(pivot, pd.DataFrame) and pivot.shape[0] >= 21:
            last = pivot.iloc[-1, :]
            prev = pivot.iloc[0, :]
            mom_series = (last / prev - 1).replace([np.inf, -np.inf], np.nan)
            # 转为标准 Series，index 为代码
            mom = mom_series.to_dict()
        else:
            # 回退到逐只请求（慢，但稳健）
            for s in stock_list:
                try:
                    tmp = attribute_history(s, 21, '1d', ['close'], df=True)
                    if isinstance(tmp, pd.DataFrame) and tmp.shape[0] >= 21:
                        col = tmp['close'].dropna()
                        if len(col) >= 21:
                            mom[s] = (col.iloc[-1] / col.iloc[0]) - 1
                        else:
                            mom[s] = np.nan
                    else:
                        mom[s] = np.nan
                except Exception:
                    mom[s] = np.nan
    except Exception:
        # 万一矢量化异常，全部置 NaN
        for s in stock_list:
            mom[s] = np.nan

    return pd.Series(mom)

# ============ 替换后的 daily_rebalance（修复 sum_inv 计算并增强历史数据兼容性） ============
def daily_rebalance(context):
    """
    每日调仓（修复 sum_inv 计算并增强历史数据兼容性）
    """
    if g.no_trading_today_signal:
        return

    # 获取择时仓位比例
    g.timing_position_ratio = get_timing_position_ratio(context)
    log.info("当前择时仓位比例: %.2f" % g.timing_position_ratio)

    # 获取应买入列表
    target_list = get_stock_list(context)
    if len(target_list) == 0:
        log.info("选股列表为空，不操作")
        return

    # 卖出不在目标列表且非昨日涨停的股票
    for stock in list(g.hold_list):
        if (stock not in target_list) and (stock not in g.yesterday_HL_list):
            log.info("卖出[%s]（不在目标列表）" % (stock))
            if stock in context.portfolio.positions:
                position = context.portfolio.positions[stock]
                close_position(position)
                if stock in g.trailing_peaks:
                    del g.trailing_peaks[stock]
        else:
            log.info("保留已持有[%s]" % (stock))

    # 计算目标仓位
    target_num = len(target_list)
    total_value = context.portfolio.total_value * g.timing_position_ratio

    # 已持有目标股票市值
    held_value = 0
    for s in target_list:
        if s in context.portfolio.positions and context.portfolio.positions[s].total_amount > 0:
            held_value += context.portfolio.positions[s].value

    available_value = total_value - held_value
    if available_value <= 0:
        log.info("无可用资金用于新买入")
        return

    # 新买入列表（不在当前持仓或持仓为0）
    new_buy_list = [stock for stock in target_list
                    if (stock not in context.portfolio.positions) or (context.portfolio.positions[stock].total_amount == 0)]

    if len(new_buy_list) == 0:
        log.info("无新股需要买入")
        return

    # 波动率加权：使用过去60日收益率std做逆波动权重
    inv_vols = {}
    for stock in new_buy_list:
        vol = None
        try:
            hist = history(61, unit='1d', field='close', security_list=[stock])
            if isinstance(hist, pd.DataFrame):
                if stock in hist.columns:
                    s = hist[stock].dropna().pct_change().dropna()
                else:
                    if hist.shape[1] >= 1:
                        s = hist.iloc[:, 0].dropna().pct_change().dropna()
                    else:
                        s = pd.Series([], dtype=float)
            else:
                tmp = attribute_history(stock, 61, '1d', ['close'], df=True)
                s = tmp['close'].pct_change().dropna()
            vol = s.std()
            if vol is None or vol <= 0:
                vol = 0.04
        except Exception:
            vol = 0.04
        inv_vols[stock] = 1.0 / vol

    # 正确计算 sum_inv（修复 bug）
    sum_inv = sum(list(inv_vols.values())) if len(inv_vols) > 0 else 0.0

    # 防止除0，使用等权分配
    if sum_inv == 0:
        equal_value = available_value / len(new_buy_list)
        for stock in new_buy_list:
            if equal_value > 5000:
                if open_position(stock, equal_value):
                    log.info("买入[%s], 均等目标金额: %.0f" % (stock, equal_value))
        return

    # 根据 inv_vol 分配资金并下单
    for stock in new_buy_list:
        alloc = available_value * (inv_vols[stock] / sum_inv)
        if alloc > 5000:  # 最小买入金额
            if open_position(stock, alloc):
                log.info("买入[%s], 目标金额: %.0f (波动率加权)" % (stock, alloc))
                try:
                    pos = context.portfolio.positions.get(stock, None)
                    if pos is not None and pos.total_amount > 0:
                        g.trailing_peaks[stock] = pos.price
                except:
                    pass

# ============ 替换后的 open_position（更稳健的判定） ============
def open_position(security, value):
    """
    下单到目标市值并返回布尔：下单尝试是否成功（更稳健的判定）
    """
    try:
        order = order_target_value_(security, value)
    except Exception as e:
        log.error("下单异常: %s, %s" % (security, str(e)))
        return False

    if order is None:
        return False

    try:
        if hasattr(order, 'filled') and getattr(order, 'filled') is not None:
            if getattr(order, 'filled') > 0:
                return True
        if hasattr(order, 'status'):
            status = getattr(order, 'status')
            if status == OrderStatus.filled or str(status).lower() == 'filled':
                return True
    except:
        pass

    return True

# ============ close_position 与订单包装 ============
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)

def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order is not None:
        try:
            if hasattr(order, 'status') and order.status == OrderStatus.filled:
                return True
            if hasattr(order, 'filled') and order.filled == order.amount:
                return True
        except:
            pass
    return False

# ============ 替换后的 check_limit_up（更稳健的涨停检查） ============
def check_limit_up(context):
    """
    强化版 `check_limit_up`：
    - 对多种行情获取接口做兼容性处理（优先 try `get_price`，失败回退到 `get_current_data` 或 `attribute_history`）
    - 在无法明确判断时采取保守策略：保留持仓并记录日志
    - 若涨停打开则卖出；若持有天数超过 g.max_limit_up_days 则强制卖出
    """
    now_time = context.current_dt

    if not g.yesterday_HL_list:
        return

    for stock in list(g.yesterday_HL_list):
        try:
            pos = context.portfolio.positions.get(stock, None)
            if pos is None or getattr(pos, 'total_amount', 0) == 0:
                continue

            close_price = None
            high_limit = None

            try:
                df = get_price(stock, end_date=now_time, frequency='1m',
                               fields=['close', 'high_limit'], count=1, panel=False, fill_paused=True)
                if isinstance(df, pd.DataFrame) and len(df) > 0:
                    if 'close' in df.columns:
                        close_price = float(df['close'].iloc[0])
                    else:
                        close_price = float(df.iloc[0, 0])
                    if 'high_limit' in df.columns:
                        high_limit = float(df['high_limit'].iloc[0])
            except Exception:
                pass

            if close_price is None or high_limit is None:
                try:
                    cur = get_current_data()
                    if stock in cur:
                        cd = cur[stock]
                        close_price = close_price or getattr(cd, 'last_price', None) or getattr(cd, 'close', None) or getattr(cd, 'last', None)
                        high_limit = high_limit or getattr(cd, 'high_limit', None)
                except Exception:
                    pass

            if close_price is None:
                try:
                    tmp = attribute_history(stock, 1, '1m', ['close'], df=True)
                    if isinstance(tmp, pd.DataFrame) and len(tmp) > 0:
                        close_price = float(tmp['close'].iloc[-1])
                except Exception:
                    try:
                        hist = history(1, unit='1m', field='close', security_list=[stock])
                        if isinstance(hist, pd.DataFrame):
                            if stock in hist.columns:
                                close_price = float(hist[stock].iloc[-1])
                            else:
                                close_price = float(hist.iloc[-1, 0])
                    except Exception:
                        pass

            if high_limit is None:
                try:
                    cur = get_current_data()
                    if stock in cur:
                        cd = cur[stock]
                        high_limit = getattr(cd, 'high_limit', None)
                except:
                    pass

            if close_price is None or high_limit is None:
                log.info("无法获取[%s]的实时价或涨停价，保留持仓（close:%s high_limit:%s）" % (stock, str(close_price), str(high_limit)))
                continue

            if close_price < high_limit:
                log.info("[%s] 涨停打开（实时价 %.4f < 涨停 %.4f），卖出" % (stock, close_price, high_limit))
                close_position(pos)
                if stock in g.trailing_peaks:
                    del g.trailing_peaks[stock]
                continue

            days = g.limit_up_hold_days.get(stock, 0)
            if days >= g.max_limit_up_days:
                log.info("[%s] 涨停持有超过 %d 天（%d），强制卖出" % (stock, g.max_limit_up_days, days))
                close_position(pos)
                if stock in g.trailing_peaks:
                    del g.trailing_peaks[stock]
            else:
                log.info("[%s] 仍为涨停，继续持有（天数:%d）" % (stock, days))

        except Exception as e:
            log.info("检查[%s]涨停状态时发生异常: %s，保留持仓" % (stock, str(e)))
            continue

# ============ 替换后的 filter_limitup_stock（更稳健的过滤） ============
def filter_limitup_stock(context, stock_list):
    """
    强化版 `filter_limitup_stock`：
    - 逐只兼容使用 `get_current_data` / `history` / `attribute_history` 获取最新价与涨停价
    - 若为已持仓股票则放行（以避免误杀已有仓位）
    - 对停牌股票进行过滤（若 current_data 标记为 paused 则排除）
    - 在无法明确判断时采取宽松放行（避免误删优质候选），但记录日志供排查
    """
    if not stock_list:
        return []

    out = []
    try:
        current_data = get_current_data()
    except:
        current_data = {}

    for stock in stock_list:
        try:
            pos = context.portfolio.positions.get(stock, None)
            if pos is not None and getattr(pos, 'total_amount', 0) > 0:
                out.append(stock)
                continue

            cd = None
            try:
                cd = current_data.get(stock, None) if isinstance(current_data, dict) else None
            except:
                cd = None

            try:
                if cd is not None and getattr(cd, 'paused', False):
                    log.debug("排除停牌股票: %s" % stock)
                    continue
            except:
                pass

            last_price = None
            high_limit = None

            if cd is not None:
                last_price = getattr(cd, 'last_price', None) or getattr(cd, 'close', None) or getattr(cd, 'last', None)
                high_limit = getattr(cd, 'high_limit', None)

            if last_price is None:
                try:
                    hist = history(1, unit='1m', field='close', security_list=[stock])
                    if isinstance(hist, pd.DataFrame):
                        if stock in hist.columns:
                            last_price = float(hist[stock].iloc[-1])
                        else:
                            last_price = float(hist.iloc[-1, 0])
                except Exception:
                    try:
                        tmp = attribute_history(stock, 1, '1m', ['close'], df=True)
                        if isinstance(tmp, pd.DataFrame) and len(tmp) > 0:
                            last_price = float(tmp['close'].iloc[-1])
                    except:
                        last_price = None

            if high_limit is None:
                try:
                    df = get_price(stock, end_date=context.current_dt, frequency='1m', fields=['high_limit'], count=1, panel=False, fill_paused=True)
                    if isinstance(df, pd.DataFrame) and len(df) > 0 and 'high_limit' in df.columns:
                        high_limit = float(df['high_limit'].iloc[0])
                except Exception:
                    if cd is not None:
                        high_limit = getattr(cd, 'high_limit', None)

            if last_price is None or high_limit is None:
                log.debug("无法确定[%s]的实时价或涨停价（last_price:%s high_limit:%s），宽松放行" % (stock, str(last_price), str(high_limit)))
                out.append(stock)
                continue

            try:
                if float(last_price) < float(high_limit):
                    out.append(stock)
                else:
                    log.debug("过滤涨停股票: %s (last: %.4f >= high_limit: %.4f)" % (stock, float(last_price), float(high_limit)))
            except Exception:
                out.append(stock)

        except Exception as e:
            log.debug("filter_limitup_stock 处理 [%s] 时异常: %s，放行该股" % (stock, str(e)))
            out.append(stock)

    return out

# ============ 其它过滤与工具函数 ============
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in current_data) and (not current_data[stock].paused)]

def filter_st_stock(stock_list):
    current_data = get_current_data()
    res = []
    for stock in stock_list:
        try:
            cd = current_data[stock]
            if (not cd.is_st) and ('ST' not in cd.name) and ('*' not in cd.name) and ('退' not in cd.name):
                res.append(stock)
        except:
            continue
    return res

def filter_kcbj_stock(stock_list):
    return [stock for stock in stock_list
            if stock[0] != '4' and stock[0] != '8' and stock[:2] != '68']

def filter_limitdown_stock(context, stock_list):
    try:
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    except:
        last_prices = {}
    current_data = get_current_data()
    out = []
    for stock in stock_list:
        try:
            if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
                out.append(stock)
            else:
                lp = None
                if isinstance(last_prices, pd.DataFrame) and stock in last_prices:
                    lp = last_prices[stock].iloc[-1]
                if lp is None:
                    out.append(stock)
                else:
                    if lp > current_data[stock].low_limit:
                        out.append(stock)
        except:
            out.append(stock)
    return out

def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    res = []
    for stock in stock_list:
        try:
            info = get_security_info(stock)
            if info is None:
                continue
            if (yesterday - info.start_date).days >= 375:
                res.append(stock)
        except:
            continue
    return res

# 交易模块中剩余工具函数
def today_is_between(context, start_date, end_date):
    today = context.current_dt.strftime('%m-%d')
    return (start_date <= today) and (today <= end_date)

def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0:
            for stock in g.hold_list:
                if stock in context.portfolio.positions:
                    position = context.portfolio.positions[stock]
                    close_position(position)
                    log.info("清仓卖出[%s]" % (stock))

def print_position_info(context):
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：' + str(_trade))
    for position in list(context.portfolio.positions.values()):
        if position.total_amount == 0:
            continue
        securities = position.security
        cost = position.avg_cost
        price = position.price
        ret = 100 * (price / cost - 1) if cost > 0 else 0
        value = position.value
        amount = position.total_amount
        print('代码:{}'.format(securities))
        print('成本价:{}'.format(format(cost, '.2f')))
        print('现价:{}'.format(price))
        print('收益率:{}%'.format(format(ret, '.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value, '.2f')))
        print('———————————————————————————————————')
    print('———————————————————————————————————————分割线————————————————————————————————————————')
