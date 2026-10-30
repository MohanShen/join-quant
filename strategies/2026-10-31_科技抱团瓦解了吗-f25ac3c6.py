# Clone from JoinQuant
# postId: f25ac3c62b9cbf06884daa0e1ddeac8f
# backtestId: 5d80f3c060024f7d6698df286f3443b9
# title: 科技抱团瓦解了吗

# 克隆自聚宽文章：https://www.joinquant.com/post/73703
# 标题：六爻八卦-全市场ETF轮动
# 作者：量化小刘总

# -*- coding: utf-8 -*-
"""
聚宽策略：V6.2注意坚果云的密码网址我修改过了 用你自己的 缠论买入 + 顶分型卖出 + 部分止盈（V6 增强版）
—— 资金配置优化版 ——
单只仓位硬上限25%，单只可用现金100%，向上取整买入
盈利≥10%时自动卖出利润部分股数，保留本金继续持仓
09:30 买入 | 09:31 卖出 | 卖出过滤：实时价>昨最高放弃卖出
"""
from jqdata import *
import pandas as pd
import numpy as np
import talib
import json

# ==================== 信号传输配置（坚果云 WebDAV） ====================
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

NUTSTORE_WEBDAV_URL = ""
NUTSTORE_USER = ""
NUTSTORE_PASS = ""
ENABLE_NUTSTORE_SIGNAL = False
  # 改为True恢复信号发送


def _to_qmt_code(code):
    """聚宽代码转QMT代码"""
    if code.endswith(".XSHE"): return code.replace(".XSHE", ".SZ")
    if code.endswith(".XSHG"): return code.replace(".XSHG", ".SH")
    return code

    set_option("avoid_future_data", True)  # 防止未来函数
    
def send_order_to_nutstore(order_data):
    """上传单条订单到坚果云（合并写入，去重）"""
    if not HAS_REQUESTS:
        return
    auth = (NUTSTORE_USER, NUTSTORE_PASS)
    try:
        existing_orders = []
        try:
            resp = requests.get(NUTSTORE_WEBDAV_URL, auth=auth, timeout=10)
            if resp.status_code == 200:
                existing_orders = resp.json().get("orders", [])
            else:
                log.warning("[坚果云] 读取云端订单失败: HTTP %d，使用空列表继续推送" % resp.status_code)
        except:
            log.warning("[坚果云] 读取云端订单异常，使用空列表继续推送")
            existing_orders = []
        existing_ids = {str(o.get("order_id")) for o in existing_orders}
        oid = str(order_data.get("order_id", ""))
        if oid and oid not in existing_ids:
            existing_orders.append(order_data)
        if len(existing_orders) > 50:
            existing_orders = existing_orders[-50:]
        payload = json.dumps({"orders": existing_orders}, ensure_ascii=False)
        resp = requests.put(NUTSTORE_WEBDAV_URL, data=payload.encode("utf-8"), auth=auth, timeout=10)
        if resp.status_code in (200, 201, 204):
            log.info("[坚果云] 推送成功: %s" % oid)
        else:
            log.warning("[坚果云] 推送失败: HTTP %d" % resp.status_code)
    except Exception as e:
        log.warning("[坚果云] 推送异常: " + str(e))

def send_trade_signal(action, stock, price, shares, reason=""):
    """发送交易信号到坚果云 -> QMT"""
    if not HAS_REQUESTS:
        return
    if not ENABLE_NUTSTORE_SIGNAL:
        return
    stock_code = _to_qmt_code(str(stock))
    try:
        ts = str(context.current_dt) if 'context' in dir() else pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    except:
        ts = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    order_id = "%s_%s_%s" % (stock_code, ts, action)
    order_id = order_id.replace(" ", "_").replace(":", "")
    order_data = {
        "order_id": order_id,
        "security": stock_code,
        "is_buy": "True" if action == "买入" else "False",
        "amount": str(int(shares)),
        "price": str(price),
    }
    send_order_to_nutstore(order_data)
# =====================================================

# ==================== 辅助函数 ====================
def get_stock_name(code):
    try: return get_security_info(code).display_name
    except: return code

def format_log_message(date_str, stock_code, action, logic, profit_pct=None, profit_amount=None, extra_info=""):
    stock_name = get_stock_name(stock_code)
    time_short = date_str.split()[-1] if ' ' in date_str else date_str
    action_emoji = "🔴" if "卖出" in action else ("🟢" if "买入" in action else "⚪")
    msg = f"[{time_short}] {action_emoji} [{stock_code}] {stock_name} | {logic}"
    if profit_pct is not None and profit_amount is not None:
        sign = "+" if profit_pct >= 0 else ""
        profit_str = f"{sign}{profit_pct*100:.1f}%/{profit_amount:+.0f}元"
        msg += f" | 💰{profit_str}"
    elif profit_pct is not None:
        sign = "+" if profit_pct >= 0 else ""
        msg += f" | 💰{sign}{profit_pct*100:.1f}%"
    if extra_info:
        msg += f" | {extra_info}"
    return msg

def classify_pct(pct):
    if pct <= -0.041: return "跌幅>4.1%"
    if pct <= -0.031: return "跌幅 3.1-4.0%"
    if pct <= -0.021: return "跌幅 2.1-3.0%"
    if pct <= 0.0:    return "跌幅 0-2.0%"
    if pct <= 0.02:   return "涨幅 0-2.0%"
    if pct <= 0.03:   return "涨幅 2.1-3.0%"
    if pct <= 0.04:   return "涨幅 3.1-4.0%"
    if pct <= 0.05:   return "涨幅 4.1-5.0%"
    if pct <= 0.06:   return "涨幅 5.1-6.0%"
    if pct <= 0.07:   return "涨幅 6.1-7.0%"
    return "涨幅>7.0%"

# ==================== EMA均线排列筛选工具 ====================
def calculate_ema_trend(prices_df, fast=8, mid=21, slow=55):
    close = prices_df['close']
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_mid = close.ewm(span=mid, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    ema_fast_current = ema_fast.iloc[-1]
    ema_mid_current = ema_mid.iloc[-1]
    ema_slow_current = ema_slow.iloc[-1]
    is_bullish = ema_fast_current > ema_mid_current > ema_slow_current
    is_bearish = ema_fast_current < ema_mid_current < ema_slow_current
    short_bullish = ema_fast_current > ema_mid_current
    trend_strength = abs(ema_fast_current - ema_slow_current) / ema_slow_current if ema_slow_current > 0 else 0
    return {
        'ema_fast': ema_fast_current,
        'ema_mid': ema_mid_current,
        'ema_slow': ema_slow_current,
        'is_bullish': is_bullish,
        'is_bearish': is_bearish,
        'short_bullish': short_bullish,
        'trend_strength': trend_strength
    }

def get_ma_alignment_score(prices_df, weights=None):
    if weights is None:
        weights = {'fast': 0.5, 'mid': 0.3, 'slow': 0.2}
    close = prices_df['close']
    ema_8 = close.ewm(span=8, adjust=False).mean().iloc[-1]
    ema_21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
    ema_55 = close.ewm(span=55, adjust=False).mean().iloc[-1]
    current_price = close.iloc[-1]
    score = 0
    details = {}
    if current_price > ema_8:
        details['price_above_fast'] = weights['fast'] * 100
        score += details['price_above_fast']
    else:
        details['price_above_fast'] = 0
    if ema_8 > ema_21:
        details['fast_above_mid'] = weights['mid'] * 100
        score += details['fast_above_mid']
    else:
        details['fast_above_mid'] = 0
    if ema_21 > ema_55:
        details['mid_above_slow'] = weights['slow'] * 100
        score += details['mid_above_slow']
    else:
        details['mid_above_slow'] = 0
    details['total_score'] = score
    details['alignment'] = 'bullish' if score >= 70 else 'neutral' if score >= 40 else 'bearish'
    return details

def filter_by_ma_alignment(stock_list, date, min_score=60, max_stocks=100):
    scored_stocks = []
    for stock in stock_list:
        try:
            prices = get_price(stock, end_date=date, frequency='daily',
                             fields=['close'], count=60, skip_paused=True, fq='pre')
            if len(prices) < 55:
                continue
            score_info = get_ma_alignment_score(prices)
            if score_info['total_score'] >= min_score:
                scored_stocks.append({
                    'code': stock,
                    'score': score_info['total_score'],
                    'alignment': score_info['alignment']
                })
        except:
            continue
    scored_stocks.sort(key=lambda x: x['score'], reverse=True)
    result = [s['code'] for s in scored_stocks[:max_stocks]]
    log.info(f"[EMA筛选] 原始{len(stock_list)}只 → 评分≥{min_score}分: {len(scored_stocks)}只 → 取前{min(max_stocks, len(result))}只")
    return result

# ==================== 初始化 ====================
def initialize(context):
    log.set_level('order', 'error')
    log.set_level('strategy', 'info')
    set_benchmark('399005.XSHE')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0001, close_commission=0.0001, min_commission=5), type='stock')

    # ========== 添加滑点设置（固定15bp，适用于中小板） ==========
    set_slippage(FixedSlippage(0.0015))

    # ---------- 资金安全上限 ----------
    g.max_single_position_ratio = 0.25   # 单只股票最高占总资产25%
    g.max_use_cash_ratio = 1.0           # 允许使用全部现金
    # ---------------------------------

    # ==================== 信号传输初始化 ====================
    log.info("=" * 60)
    log.info("策略初始化 - 坚果云 WebDAV 信号传输检查")
    if not HAS_REQUESTS:
        log.warning("❌ requests 模块未安装，将无法推送信号")
    else:
        log.info("✅ requests 模块已加载")
        try:
            test_resp = requests.get(NUTSTORE_WEBDAV_URL, auth=(NUTSTORE_USER, NUTSTORE_PASS), timeout=10)
            if test_resp.status_code == 200:
                log.info("✅ 坚果云 WebDAV 连通性测试通过")
            else:
                log.warning("⚠️ WebDAV 返回状态码 %d" % test_resp.status_code)
        except Exception as e:
            log.warning("⚠️ WebDAV 连通性测试失败: %s" % str(e))
    log.info("=" * 60)

    g.lookback = 600
    g.min_fill_ratio = 0.7
    g.cash_reserve = 0
    g.price_threshold = 50
    g.max_positions = 5

    g.sell_config = {
        'seller': TopFractalSellSystem(strict=True, confirmation_bars=1),
        'sell_records': [],
        'profit_target': 0.50,
        'loss_limit': -0.08,
        'weak_exit_days': 5,
        'buy_records': {}
    }

    g.pool_bought = []
    g.pool_filtered = []
    g.trade_day_count = 0
    g.categories = ["跌幅>4.1%", "跌幅 3.1-4.0%", "跌幅 2.1-3.0%", "跌幅 0-2.0%",
                    "涨幅 0-2.0%", "涨幅 2.1-3.0%", "涨幅 3.1-4.0%", "涨幅 4.1-5.0%",
                    "涨幅 5.1-6.0%", "涨幅 6.1-7.0%", "涨幅>7.0%"]

    g.enable_intraday_sell = False

    run_daily(update_stock_pool, time='before_open')
    
    # ========== 时间拆分：9:30买入，9:31卖出 ==========
    run_daily(trade, time='09:30')               # 9:30 执行买入
    run_daily(check_sell_signals, time='09:31')  # 9:31 执行卖出
    run_daily(check_next_day_exit, time='09:38') # 9:38 次日保护检查
    # =================================================

    if g.enable_intraday_sell:
        run_daily(check_sell_signals, time='10:30')
        run_daily(check_sell_signals, time='11:30')
        run_daily(check_sell_signals, time='13:30')
        run_daily(check_sell_signals, time='14:30')
        log.info('🔔 盘中卖出检查已开启：10:30/11:30/13:30/14:30')
    else:
        log.info('🔕 盘中卖出检查已关闭（默认），仅09:31开盘卖出')

    run_daily(after_market_close, time='15:05')
    run_daily(update_and_log_pools, time='14:58')

    log.info('✅ V6.2 资金优化+部分止盈版初始化完成 | 单只上限25% | 现金100% | 09:30买入/09:31卖出 | 卖过滤:实时价>昨最高不卖 | 滑点15bp')

# ==================== 股票池 ====================
def update_stock_pool(context):
    date = context.current_dt.date()
    g.stock_pool = get_top50_stocks(date)
    log.info(f'📦 股票池更新：{len(g.stock_pool)} 只')

def get_top50_stocks(date):
    sme100_stocks = get_index_stocks('399005.XSHE', date)
    ma_filtered_stocks = filter_by_ma_alignment(sme100_stocks, date, min_score=60, max_stocks=150)
    if not ma_filtered_stocks:
        log.warning(f"[{date}] EMA筛选后无符合条件的股票")
        return []
    all_stocks = get_all_securities(types=['stock'], date=date)
    q = query(
        valuation.code,
        indicator.roe,
        indicator.roa,
        indicator.gross_profit_margin,
        indicator.net_profit_to_total_revenue
    ).filter(
        valuation.code.in_(ma_filtered_stocks)
    )
    df = get_fundamentals(q, date=date)
    if df.empty:
        log.warning(f"[{date}] 财务数据查询为空")
        return []
    required_cols = ['roe', 'roa', 'gross_profit_margin', 'net_profit_to_total_revenue']
    df = df.dropna(subset=required_cols)
    st_stocks = []
    for code in df['code']:
        try:
            name = all_stocks.loc[code, 'display_name']
            if name.startswith('*ST') or name.startswith('ST'):
                st_stocks.append(code)
        except KeyError:
            continue
    if st_stocks:
        df = df[~df['code'].isin(st_stocks)]
    current_data = get_current_data()
    paused_stocks = [code for code in df['code'] if current_data[code].paused]
    if paused_stocks:
        df = df[~df['code'].isin(paused_stocks)]
    if df.empty:
        return []
    for col in required_cols:
        df[col + '_pct'] = df[col].rank(pct=True, ascending=True)
    df['score'] = (
        0.3 * df['roe_pct'] +
        0.2 * df['roa_pct'] +
        0.2 * df['gross_profit_margin_pct'] +
        0.3 * df['net_profit_to_total_revenue_pct']
    )
    top50 = df.sort_values('score', ascending=False).head(50)['code'].tolist()
    log.info(f"[{date}] 股票池筛选：中小板100 → EMA → TOP50")
    return top50

# ==================== 9:38 次日保护 ====================
def check_next_day_exit(context):
    current_data = get_current_data()
    date_str = context.current_dt.strftime('%Y-%m-%d %H:%M')
    current_date = context.current_dt.date()
    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]
        if position.total_amount == 0: continue
        buy_record = g.sell_config['buy_records'].get(stock, {})
        buy_time = buy_record.get('time')
        if not buy_time or buy_time.date() == current_date: continue
        if buy_record.get('next_day_checked', False): continue
        try:
            hist = get_price(stock, count=3, end_date=context.previous_date, frequency='daily', fields=['low'], skip_paused=True, fq=None)
            if len(hist) < 2:
                g.sell_config['buy_records'][stock]['next_day_checked'] = True
                continue
            lowest_2days = min(hist['low'].iloc[-1], hist['low'].iloc[-2])
            current_price = current_data[stock].last_price
            g.sell_config['buy_records'][stock]['next_day_checked'] = True
            if current_price < lowest_2days * 0.999:
                total_amount = position.total_amount; cost = position.avg_cost
                order_obj = order_target(stock, 0)
                if order_obj and order_obj.filled > 0:
                    actual_price = order_obj.price if order_obj.price > 0 else current_price
                    profit_pct = (actual_price - cost) / cost if cost > 0 else 0
                    profit_amount = (actual_price - cost) * total_amount
                    log.info(format_log_message(date_str, stock, "卖出", "次日保护(跌破昨前最低)", profit_pct, profit_amount, f"最低{lowest_2days:.2f} 现价{actual_price:.2f}"))
                    send_trade_signal("卖出", stock, actual_price, total_amount, "次日保护(跌破昨前最低)")
                    if stock in g.sell_config['buy_records']: del g.sell_config['buy_records'][stock]
                    for r in g.pool_bought:
                        if r['code'] == stock and not r.get('sold', False):
                            r['sold'] = True
                            r['sell_date'] = date_str.split()[0] if ' ' in date_str else date_str
                            r['sell_price'] = actual_price
                            r['sell_reason'] = "次日保护(跌破昨前最低)"
                            r['sell_profit_pct'] = profit_pct
                            break
            else:
                log.info(f"[{date_str.split()[-1]}] ✅ [{stock}] 次日保护检查完成: 未跌破昨前最低(最低{lowest_2days:.2f} 现价{current_price:.2f})，后续不再检查")
        except Exception as e:
            log.error(f"[{date_str}] [{stock}] [次日保护检查出错] [{str(e)}]")
            if stock in g.sell_config['buy_records']:
                g.sell_config['buy_records'][stock]['next_day_checked'] = True

# ==================== 买入系统 ====================
def trade(context):
    date_str = context.current_dt.strftime('%Y-%m-%d %H:%M')
    current_holdings = len(context.portfolio.positions)
    if current_holdings >= g.max_positions: return
    available_cash = context.portfolio.available_cash
    if available_cash < 1000: return

    target_value = compute_target_value(context, current_holdings, g.max_positions)
    buy_list = []

    for stock in g.stock_pool:
        if stock in context.portfolio.positions: continue
        try:
            buy_signal, reason, cur_price, macd_last = get_buy_signal(stock, context,
                {'lookback': g.lookback, 'beichi_ratio': 0.9, 'macd_hist_min': -0.01, 'enable_price_filter': True})
            if buy_signal and cur_price > 0:
                try:
                    prev_close = get_price(stock, count=1, end_date=context.previous_date, frequency='daily', fields=['close'], skip_paused=True, fq='pre')['close'].iloc[0]
                except: prev_close = cur_price
                t0_pct = (cur_price - prev_close) / prev_close
                buy_list.append({
                    'stock': stock, 'price': cur_price, 'reason': reason,
                    'macd': macd_last, 't0_pct': t0_pct,
                    'category': classify_pct(t0_pct), 'prev_close': prev_close
                })
        except: continue

    buy_list.sort(key=lambda x: x['macd'] if x['macd'] is not None else -999, reverse=True)
    slots_left = g.max_positions - current_holdings
    bought_codes = set()

    for item in buy_list[:slots_left]:
        stock = item['stock']; cur_price = item['price']; buy_reason = item['reason']

        try:
            price_hist = get_price(stock, count=1, end_date=context.previous_date, frequency='daily', fields=['low'], skip_paused=True, fq=None)
            if len(price_hist) >= 1:
                yesterday_low = price_hist['low'].iloc[-1]
                if cur_price < yesterday_low:
                    log.info(f"[买入过滤] {stock} 当前价{cur_price:.2f} < 昨日最低{yesterday_low:.2f}，放弃买入")
                    item['filtered_reason'] = f"价格过滤(实时价{cur_price:.2f} < 昨日最低{yesterday_low:.2f})"
                    continue
        except Exception as e:
            log.warn(f"[价格过滤检查异常] {stock}: {str(e)}")

        shares, actual_amount, fill_ratio = calculate_buy_amount(context, target_value, cur_price,
            min_fill_ratio=g.min_fill_ratio, cash_reserve=g.cash_reserve, price_threshold=g.price_threshold)

        if shares < 100 or actual_amount > available_cash * (1 - g.cash_reserve): continue

        order_obj = order_value(stock, actual_amount)
        if order_obj and order_obj.filled > 0:
            actual_price = order_obj.price if order_obj.price > 0 else cur_price
            filled_amount = order_obj.filled
            log.info(format_log_message(date_str=date_str, stock_code=stock, action="买入",
                                        logic=f"缠论{buy_reason}",
                                        extra_info=f"价{actual_price:.2f} 量{filled_amount}股 金额{actual_amount:.0f}元"))
            send_trade_signal("买入", stock, actual_price, filled_amount, buy_reason)

            g.sell_config['buy_records'][stock] = {
                'time': context.current_dt,
                'price': actual_price,
                'amount': filled_amount,
                'idx': len(get_price(stock, end_date=context.current_dt, count=1, frequency='daily', fields=['close'])) - 1
            }
            available_cash -= actual_amount
            bought_codes.add(stock)
            if available_cash < 1000: break
        else:
            log.warn(f"[{date_str}] [{stock}] [买入失败] [缠论{buy_reason}] [订单未成交]")

    for item in buy_list:
        if item['stock'] in bought_codes:
            actual_p = g.sell_config['buy_records'][item['stock']]['price']
            actual_t0_pct = (actual_p - item['prev_close']) / item['prev_close']
            g.pool_bought.append({
                'code': item['stock'],
                'name': get_stock_name(item['stock']),
                't0_date': context.current_dt.strftime('%Y-%m-%d'),
                't0_price': actual_p,
                't0_pct': actual_t0_pct,
                'category': classify_pct(actual_t0_pct),
                'buy_reason': item['reason'],
                'macd_value': item['macd'],
                'prices': [actual_p],
                'price_dates': [context.current_dt.strftime('%Y-%m-%d')],
                'sold': False,
                'sell_date': None,
                'sell_price': None
            })
        else:
            g.pool_filtered.append({
                'code': item['stock'],
                'name': get_stock_name(item['stock']),
                't0_date': context.current_dt.strftime('%Y-%m-%d'),
                't0_price': item['price'],
                't0_pct': item['t0_pct'],
                'category': item['category'],
                'buy_reason': item['reason'],
                'macd_value': item['macd'],
                'filtered_reason': '资金不足/仓位已满/订单失败',
                'prices': [item['price']],
                'price_dates': [context.current_dt.strftime('%Y-%m-%d')],
                'track_only': True
            })

# ==================== 缠论核心算法 ====================
def handle_inclusion(df):
    if len(df) < 2: return df
    new_data, direction = [], 'up'
    last_h, last_l = df['high'].iloc[0], df['low'].iloc[0]
    new_data.append({'high': last_h, 'low': last_l})
    for i in range(1, len(df)):
        curr_h, curr_l = df['high'].iloc[i], df['low'].iloc[i]
        if (curr_h <= last_h and curr_l >= last_l) or (curr_h >= last_h and curr_l <= last_l):
            if direction == 'up': last_h, last_l = max(last_h, curr_h), max(last_l, curr_l)
            else: last_h, last_l = min(last_h, curr_h), min(last_l, curr_l)
            new_data[-1] = {'high': last_h, 'low': last_l}
        else:
            direction = 'up' if curr_h > last_h else 'down'
            last_h, last_l = curr_h, curr_l
            new_data.append({'high': last_h, 'low': last_l})
    return pd.DataFrame(new_data)

def get_chan_elements(df):
    fractals = []
    for i in range(1, len(df) - 1):
        if df['high'].iloc[i] > df['high'].iloc[i-1] and df['high'].iloc[i] > df['high'].iloc[i+1]: fractals.append({'type': 'top', 'idx': i, 'price': df['high'].iloc[i]})
        elif df['low'].iloc[i] < df['low'].iloc[i-1] and df['low'].iloc[i] < df['low'].iloc[i+1]: fractals.append({'type': 'bottom', 'idx': i, 'price': df['low'].iloc[i]})
    strokes, last_f = [], fractals[0] if fractals else None
    if len(fractals) < 2: return strokes
    for i in range(1, len(fractals)):
        curr_f = fractals[i]
        if curr_f['type'] != last_f['type'] and (curr_f['idx'] - last_f['idx'] >= 4):
            strokes.append({'start_idx': last_f['idx'], 'end_idx': curr_f['idx'], 'start_price': last_f['price'], 'end_price': curr_f['price'], 'direction': 'up' if curr_f['type'] == 'top' else 'down'})
            last_f = curr_f
    return strokes

def get_zhongshu(strokes):
    if len(strokes) < 3: return []
    zs_list = []
    for i in range(len(strokes) - 2):
        s1, s2, s3 = strokes[i], strokes[i+1], strokes[i+2]
        zg = min(max(s1['start_price'], s1['end_price']), max(s2['start_price'], s2['end_price']), max(s3['start_price'], s3['end_price']))
        zd = max(min(s1['start_price'], s1['end_price']), min(s2['start_price'], s2['end_price']), min(s3['start_price'], s3['end_price']))
        if zg > zd: zs_list.append({'zg': zg, 'zd': zd, 'start': i, 'end': i+2})
    return zs_list

def is_beichi(strokes, zs, macd_hist, beichi_ratio=0.9):
    if not zs or len(strokes) <= zs['end'] + 1: return False
    s_in, s_out = strokes[zs['start']], strokes[zs['end'] + 1]
    area_in = np.nansum(np.abs(macd_hist[s_in['start_idx'] : s_in['end_idx']]))
    area_out = np.nansum(np.abs(macd_hist[s_out['start_idx'] : s_out['end_idx']]))
    return area_out < area_in * beichi_ratio if area_in > 0 else False

def get_buy_signal(stock, context, params=None):
    if params is None: params = {}
    lookback = params.get('lookback', 600); beichi_ratio = params.get('beichi_ratio', 0.9)
    macd_hist_min = params.get('macd_hist_min', -0.01); enable_price_filter = params.get('enable_price_filter', True)
    hist = get_price(stock, count=lookback, end_date=context.current_dt, frequency='daily', fields=['high', 'low', 'close'], skip_paused=True, fq='pre')
    if len(hist) < 100: return False, "", 0, None
    processed = handle_inclusion(hist); strokes = get_chan_elements(processed); zs_list = get_zhongshu(strokes)
    macd_dif, macd_dea, macd_hist = talib.MACD(hist['close'].values, 12, 26, 9)
    cur_price = hist['close'].iloc[-1]; macd_last = macd_hist[-1] if not np.isnan(macd_hist[-1]) else None
    buy_signal, reason = False, ""
    if len(strokes) > 0 and len(zs_list) > 0:
        last_s, last_zs = strokes[-1], zs_list[-1]
        if last_s['direction'] == 'down':
            if is_beichi(strokes, last_zs, macd_hist, beichi_ratio): buy_signal, reason = True, "背驰"
            elif cur_price > last_zs['zg']: buy_signal, reason = True, "突破"
    if buy_signal:
        if macd_last is None or macd_last <= macd_hist_min: return False, "", cur_price, macd_last
        if enable_price_filter:
            try:
                price_hist = get_price(stock, count=2, end_date=context.previous_date, frequency='daily', fields=['low'], skip_paused=True, fq=None)
                if len(price_hist) >= 2 and (cur_price < price_hist['low'].iloc[-1] or cur_price < price_hist['low'].iloc[-2]): return False, "", cur_price, macd_last
            except: pass
    return buy_signal, reason, cur_price, macd_last

# ==================== 部分止盈函数 ====================
def partial_profit_take(context, stock, avg_cost, total_shares, current_price, profit_pct, date_str):
    """
    部分止盈：卖出利润部分对应的股数，保留本金。
    返回 True 表示执行了卖出，False 表示未执行（如股数不足或会卖到本金）
    """
    profit_amount = (current_price - avg_cost) * total_shares
    if profit_amount <= 0:
        return False

    ideal_sell_shares = profit_amount / current_price
    sell_shares = int(ideal_sell_shares / 100) * 100
    if sell_shares <= 0:
        log.info(f"[{date_str.split()[-1]}] 📈 [{stock}] 部分止盈触发但利润不足100股，放弃。利润{profit_amount:.0f}元，股价{current_price:.2f}")
        return False

    cost_total = avg_cost * total_shares
    remaining_shares = total_shares - sell_shares
    if remaining_shares * current_price < cost_total:
        while sell_shares > 0 and (total_shares - sell_shares) * current_price < cost_total:
            sell_shares -= 100
        if sell_shares <= 0:
            log.info(f"[{date_str.split()[-1]}] ⚠️ [{stock}] 部分止盈会触及本金，放弃卖出。")
            return False

    order_obj = order(stock, -sell_shares)
    if order_obj and order_obj.filled > 0:
        actual_sell_shares = order_obj.filled
        actual_amount = actual_sell_shares * order_obj.price
        log.info(f"[{date_str.split()[-1]}] 🟡 [{stock}] 部分止盈卖出 {actual_sell_shares}股，金额{actual_amount:.0f}元，"
                 f"成本{avg_cost:.2f}，现价{current_price:.2f}，盈利{profit_pct*100:.1f}%，剩余{total_shares - actual_sell_shares}股")
        send_trade_signal("卖出", stock, order_obj.price, actual_sell_shares, f"部分止盈(盈利{profit_pct*100:.1f}%)")
        return True
    else:
        log.warn(f"[{date_str.split()[-1]}] ⚠️ [{stock}] 部分止盈卖出失败")
        return False

# ==================== 卖出系统 ====================
def check_sell_signals(context):
    positions = context.portfolio.positions
    date_str = context.current_dt.strftime('%Y-%m-%d %H:%M')
    current_date = context.current_dt.date()
    if not positions: return
    sellable_stocks, skipped_stocks = [], []
    for stock, position in positions.items():
        if position.total_amount == 0: continue
        buy_record = g.sell_config['buy_records'].get(stock, {})
        buy_time = buy_record.get('time')
        if buy_time and buy_time.date() == current_date:
            skipped_stocks.append((stock, position.total_amount))
        else:
            sellable_stocks.append(stock)
    for stock, amount in skipped_stocks:
        log.info(f"[{date_str.split()[-1]}] ⏭️ [{stock}] 跳过卖出(T+1今日买入) 持仓{amount}股")
    if not sellable_stocks:
        if skipped_stocks:
            log.info(f"[{date_str.split()[-1]}] ⏭️ 无可卖持仓，{len(skipped_stocks)}只T+1今日买入")
        return
    time_str = date_str.split()[-1]
    is_intraday = time_str != '09:31'       
    if is_intraday and not getattr(g, 'enable_intraday_sell', False):
        return
    log.info(f'[{time_str}] 🔍 卖出扫描（部分止盈+顶分型） {len(sellable_stocks)}只可卖持仓')
    for stock in sellable_stocks:
        position = positions.get(stock)
        if not position or position.total_amount == 0: continue
        total_amount, cost = position.total_amount, position.avg_cost
        current_price = position.price

        # 实时价 > 昨日最高价 → 放弃卖出（强势不卖）
        try:
            yest_high = get_price(stock, count=1, end_date=context.previous_date,
                                  frequency='daily', fields=['high'], skip_paused=True, fq=None)
            if len(yest_high) > 0 and current_price > yest_high['high'].iloc[-1]:
                log.info(f"[{time_str}] 🚫 [{stock}] 实时价{current_price:.2f} > 昨最高{yest_high['high'].iloc[-1]:.2f}，强势放弃卖出")
                continue
        except:
            pass

        try:
            hist = get_price(stock, end_date=context.current_dt, frequency='daily', fields=['high','low','open','close'], count=g.lookback, skip_paused=True, fq='pre')
            if len(hist) < 20: continue
            profit_pct = (current_price - cost) / cost if cost > 0 else 0

            # ========== 部分止盈（盈利超过10%） ==========
            if profit_pct >= 0.10:
                sold = partial_profit_take(context, stock, cost, total_amount, current_price, profit_pct, date_str)
                if sold:
                    new_position = context.portfolio.positions.get(stock)
                    if not new_position or new_position.total_amount == 0:
                        continue
                    total_amount = new_position.total_amount
                    current_price = new_position.price
                    profit_pct = (current_price - cost) / cost if cost > 0 else 0

            # 原有的卖出逻辑（硬性止损止盈、弱市退出、顶分型）
            buy_record = g.sell_config['buy_records'].get(stock, {})
            buy_time = buy_record.get('time')
            hold_days = 0
            if buy_time:
                trade_days = get_trade_days(start_date=buy_time.strftime('%Y-%m-%d'), end_date=current_date.strftime('%Y-%m-%d'))
                hold_days = len(trade_days) - 1 if len(trade_days) > 0 else 0
            if profit_pct <= g.sell_config['loss_limit']:
                _execute_sell(context, stock, cost, total_amount, current_price, f'硬性止损 -8% 实际{profit_pct*100:.1f}%')
                continue
            if profit_pct >= g.sell_config['profit_target']:
                _execute_sell(context, stock, cost, total_amount, current_price, f'硬性止盈 50% 实际{profit_pct*100:.1f}%')
                continue
            if hold_days >= g.sell_config['weak_exit_days'] and 0 < profit_pct < 0.05:
                _execute_sell(context, stock, cost, total_amount, current_price, f'持仓 5 天盈利仅{profit_pct*100:.1f}%<5%，资金腾挪')
                continue
            if hold_days >= g.sell_config['weak_exit_days'] and profit_pct < 0:
                _execute_sell(context, stock, cost, total_amount, current_price, f'持仓 5 天被套{profit_pct*100:.1f}%，及时止损')
                continue
            position_info = {'buy_time': buy_time} if buy_time is not None else None
            decision = g.sell_config['seller'].should_sell(hist, position_info, current_date)
            if decision['should_sell']:
                _execute_sell(context, stock, cost, total_amount, decision['price'], f'顶分型卖出 (优先级{decision["priority"]}) {decision["reason"]}')
                continue
        except Exception as e:
            log.error(f"[{date_str}] [{stock}] [卖出检查出错] [{str(e)}]")

def _execute_sell(context, stock, cost, total_amount, price, reason):
    date_str = context.current_dt.strftime('%Y-%m-%d %H:%M')
    if total_amount == 0: return
    order_obj = order_target(stock, 0)
    if order_obj and order_obj.filled > 0:
        actual_price = order_obj.price if order_obj.price > 0 else price; filled_amount = order_obj.filled
        profit_pct = (actual_price - cost) / cost if cost > 0 else 0; profit_amount = (actual_price - cost) * total_amount
        g.sell_config['sell_records'].append({
            'time': date_str, 'stock': stock, 'price': actual_price, 'amount': filled_amount,
            'profit_pct': profit_pct, 'profit_amount': profit_amount, 'reason': reason
        })
        for r in g.pool_bought:
            if r['code'] == stock and not r.get('sold', False):
                r['sold'] = True
                r['sell_date'] = date_str.split()[0] if ' ' in date_str else date_str
                r['sell_price'] = actual_price
                r['sell_reason'] = reason
                r['sell_profit_pct'] = profit_pct
                break
        send_trade_signal("卖出", stock, actual_price, filled_amount, reason)
        if stock in g.sell_config['buy_records']: del g.sell_config['buy_records'][stock]
        log.info(format_log_message(date_str, stock, "卖出", reason, profit_pct, profit_amount, f"卖价{actual_price:.2f} 数量{filled_amount}股"))
    else: log.warn(f"[{date_str.split()[-1]}] ⚠️ [{stock}] 卖出失败: {reason}")

# ==================== 仓位计算（资金优化版） ====================
def compute_target_value(context, current_holdings, max_positions):
    """每只股票固定分配：总资产的 1/max_positions，硬上限 25%"""
    base_pct = 1.0 / max_positions
    slots_left = max_positions - current_holdings
    if slots_left > 0:
        pct = min(0.25, base_pct * (1 + (slots_left - 1) * 0.05))
    else:
        pct = base_pct
    return context.portfolio.total_value * pct

def calculate_buy_amount(context, target_value, cur_price,
                        min_fill_ratio=0.7, cash_reserve=0.02, price_threshold=50):
    total_value = context.portfolio.total_value
    available_cash = context.portfolio.available_cash

    min_target_amount = total_value * 0.10
    max_by_total = total_value * g.max_single_position_ratio
    max_by_cash = available_cash * g.max_use_cash_ratio

    base_shares = int(target_value / cur_price / 100) * 100
    if base_shares < 100:
        return 0, 0, 0
    base_amount = base_shares * cur_price

    ceil_shares = base_shares + 100
    ceil_amount = ceil_shares * cur_price

    use_ceil = False
    if ceil_shares >= 100 and ceil_amount <= max_by_total and ceil_amount <= max_by_cash:
        if (abs(ceil_amount - target_value) < abs(base_amount - target_value)) or (base_amount < 0.8 * min_target_amount):
            use_ceil = True

    if use_ceil:
        final_shares = ceil_shares
        final_amount = ceil_amount
    else:
        final_shares = base_shares
        final_amount = base_amount

    if final_amount > max_by_cash or final_amount > max_by_total:
        final_shares = base_shares
        final_amount = base_amount
        while final_shares >= 100 and (final_amount > max_by_cash or final_amount > max_by_total):
            final_shares -= 100
            final_amount = final_shares * cur_price

    if final_shares < 100:
        return 0, 0, 0

    return final_shares, final_amount, 1.0

# ==================== 顶分型卖出类 ====================
class TopFractalSellSystem:
    def __init__(self, strict=True, confirmation_bars=1): self.strict, self.confirmation_bars = strict, confirmation_bars
    def process_inclusion(self, highs, lows):
        if len(highs) < 2: return pd.DataFrame({'high': highs, 'low': lows, 'orig_idx': range(len(highs))})
        result, direction, i = [], None, 0
        while i < len(highs):
            if i == 0: result.append({'high': highs[i], 'low': lows[i], 'orig_idx': [i]}); i += 1; continue
            last = result[-1]; curr_h, curr_l = highs[i], lows[i]
            contained = (last['high'] >= curr_h and last['low'] <= curr_l) or (curr_h >= last['high'] and curr_l <= last['low'])
            if contained:
                if direction is None: direction = 'up' if (len(result) >= 2 and last['high'] > result[-2]['high']) else ('down' if len(result) >= 2 else 'up')
                if direction == 'up': last['high'], last['low'] = max(last['high'], curr_h), max(last['low'], curr_l)
                else: last['high'], last['low'] = min(last['high'], curr_h), min(last['low'], curr_l)
                last['orig_idx'].append(i)
            else:
                if curr_h > last['high'] and curr_l > last['low']: direction = 'up'
                elif curr_h < last['high'] and curr_l < last['low']: direction = 'down'
                result.append({'high': curr_h, 'low': curr_l, 'orig_idx': [i]})
            i += 1
        df = pd.DataFrame(result); df['orig_idx'] = df['orig_idx'].apply(lambda x: x[-1]); return df
    def detect_top_fractal(self, klines):
        highs, lows = klines['high'].values, klines['low'].values; processed = self.process_inclusion(highs, lows); n = len(processed)
        if n < 3: return []
        tops = []
        for i in range(1, n - 1):
            prev, curr, next_b = processed.iloc[i-1], processed.iloc[i], processed.iloc[i+1]
            is_top = curr['high'] > prev['high'] and curr['high'] > next_b['high'] if self.strict else (curr['high'] >= prev['high'] and curr['high'] >= next_b['high'] and (curr['high'] > prev['high'] or curr['high'] > next_b['high']))
            if not is_top: continue
            orig_idx = int(curr['orig_idx']); high_gap = min(curr['high'] - prev['high'], curr['high'] - next_b['high'])
            confirmed = False
            if i + self.confirmation_bars < n: confirmed = all(processed.iloc[i+1:i+1+self.confirmation_bars]['high'].values < curr['high'])
            tops.append({'orig_idx': orig_idx, 'processed_idx': i, 'high': curr['high'], 'low': curr['low'], 'high_gap': high_gap, 'confirmed': confirmed, 'date': klines.index[orig_idx] if hasattr(klines, 'index') else orig_idx})
        return tops
    def should_sell(self, klines, position_info=None, current_date=None):
        if len(klines) < 5: return {'should_sell': False, 'reason': '数据不足'}
        current_price = klines['close'].iloc[-1]; current_idx = len(klines) - 1
        tops = self.detect_top_fractal(klines); recent_tops = [t for t in tops if current_idx - t['orig_idx'] <= 15]
        active_top = recent_tops[-1] if recent_tops else None
        if active_top:
            top_high, top_low, top_idx = active_top['high'], active_top['low'], active_top['orig_idx']
            confirmed, bars_since = active_top['confirmed'], current_idx - top_idx
            strength_score = active_top['high_gap'] / top_high * 100 if top_high > 0 else 0
            if strength_score > 5 and bars_since <= 2: return {'should_sell': True, 'reason': f'极强顶分型 强度:{strength_score:.1f}% 高点:{top_high:.2f}', 'price': current_price, 'priority': 1}
            if confirmed and current_price < top_low * 1.001: return {'should_sell': True, 'reason': f'跌破顶分型低点 顶:{top_high:.2f} 低:{top_low:.2f} 现:{current_price:.2f}', 'price': current_price, 'priority': 2}
            if bars_since >= 1 and bars_since <= 5:
                drop_pct = (top_high - current_price) / top_high * 100
                if drop_pct >= 3.0: return {'should_sell': True, 'reason': f'顶分型后回落{drop_pct:.1f}% 保护卖出', 'price': current_price, 'priority': 3}
            if bars_since == 2 and not confirmed:
                last_2 = klines.iloc[-2:]
                if (last_2['close'].values < last_2['open'].values).all() and (last_2['high'].values < top_high).all():
                    return {'should_sell': True, 'reason': '顶分型后连续双阴未创新高', 'price': current_price, 'priority': 4}
        return {'should_sell': False, 'reason': f'持有监控'}

# ==================== 追踪 & 日志 ====================
def update_and_log_pools(context):
    g.trade_day_count += 1
    today_str = context.current_dt.strftime('%Y-%m-%d')
    all_pools = {'✅已买入': g.pool_bought, '⛔未买入/过滤': g.pool_filtered}

    for r in g.pool_bought:
        if not r['sold']:
            stock = r['code']
            if stock not in context.portfolio.positions:
                sell_records = [rec for rec in g.sell_config.get('sell_records', []) if rec['stock'] == stock]
                if sell_records:
                    last_sell = sell_records[-1]
                    r['sold'] = True
                    r['sell_date'] = last_sell['time'].split()[0] if ' ' in last_sell['time'] else today_str
                    r['sell_price'] = last_sell['price']

    active_codes = set()
    for pool in all_pools.values():
        for r in pool:
            if len(r['prices']) <= 5 and not r.get('sold', False):
                active_codes.add(r['code'])

    if active_codes:
        try:
            closes_df = get_price(list(active_codes), count=1, end_date=context.current_dt, frequency='daily', fields=['close'], skip_paused=False, fq='pre', panel=False)
            close_map = {}
            if isinstance(closes_df, pd.DataFrame) and len(closes_df) > 0:
                if isinstance(closes_df.columns, pd.MultiIndex):
                    for col in closes_df.columns:
                        if col[1] == 'close':
                            val = closes_df[col].iloc[0]
                            if not pd.isna(val): close_map[col[0]] = val
                else:
                    for col in closes_df.columns:
                        val = closes_df[col].iloc[0]
                        if not pd.isna(val): close_map[col] = val
            for pool in all_pools.values():
                for r in pool:
                    code = r['code']
                    if code in close_map and len(r['prices']) <= 5:
                        if today_str not in r.get('price_dates', []):
                            r['prices'].append(close_map[code])
                            r['price_dates'].append(today_str)
        except Exception as e:
            log.warn(f"[更新价格失败] {str(e)}")

    log.info("")
    log.info("📊" + "="*52)
    log.info(f"📊 每日信号分类统计 (第{g.trade_day_count}个交易日)")
    log.info("📊" + "="*52)
    log.info(f"| {'涨跌幅区间':<14} | {'已买入':>6} | {'未买入':>6} | {'合计':>6} |")
    log.info("-" * 52)
    bought_counts = {cat: 0 for cat in g.categories}
    filtered_counts = {cat: 0 for cat in g.categories}
    for r in g.pool_bought: bought_counts[r['category']] = bought_counts.get(r['category'], 0) + 1
    for r in g.pool_filtered: filtered_counts[r['category']] = filtered_counts.get(r['category'], 0) + 1
    total_b, total_f = 0, 0
    for cat in g.categories:
        b, f = bought_counts[cat], filtered_counts[cat]
        t = b + f
        if t > 0:
            log.info(f"| {cat:<14} | {b:>6} | {f:>6} | {t:>6} |")
        total_b += b
        total_f += f
    log.info("-" * 52)
    log.info(f"| {'总计':<14} | {total_b:>6} | {total_f:>6} | {total_b+total_f:>6} |")
    log.info("📊" + "="*52)

    if g.trade_day_count % 5 == 0 and g.trade_day_count > 0:
        log.info("")
        log.info("🔍" + "="*90)
        log.info(f"🔍 T+1 ~ T+5 跟踪涨跌幅分析 (周期汇总)")
        log.info("🔍" + "="*90)
        log.info(f"| {'涨跌幅区间':<14} | {'状态':<8} | {'样本':>6} | {'T+1':>8} | {'T+2':>8} | {'T+3':>8} | {'T+4':>8} | {'T+5':>8} |")
        log.info("-" * 90)
        for status_name, pool in [("已买入", g.pool_bought), ("未买入", g.pool_filtered)]:
            for cat in g.categories:
                group = [r for r in pool if r['category'] == cat and len(r['prices']) > 1]
                if not group: continue
                avgs = []
                for d in range(1, 6):
                    valid_rets = []
                    for r in group:
                        if len(r['prices']) > d and not pd.isna(r['prices'][d]):
                            ret = (r['prices'][d] - r['prices'][0]) / r['prices'][0]
                            valid_rets.append(ret)
                    if valid_rets:
                        avg_ret = np.mean(valid_rets)
                        avgs.append(f"{avg_ret*100:+.2f}%")
                    else:
                        avgs.append("---")
                log.info(f"| {cat:<14} | {status_name:<8} | {len(group):>6} | {avgs[0]:>8} | {avgs[1]:>8} | {avgs[2]:>8} | {avgs[3]:>8} | {avgs[4]:>8} |")
        log.info("🔍" + "="*90)

        sold_stocks = [r for r in g.pool_bought if r.get('sold', False)]
        if sold_stocks:
            show_list = sold_stocks[-10:]
            hold_cache = {}
            try:
                all_t0 = [r.get('t0_date', '') for r in show_list]
                all_sd = [r.get('sell_date', today_str) for r in show_list]
                valid_dates = [(t, s) for t, s in zip(all_t0, all_sd) if t and s]
                if valid_dates:
                    min_d = min(d[0] for d in valid_dates)
                    max_d = max(d[1] for d in valid_dates)
                    td_list = get_trade_days(start_date=min_d, end_date=max_d)
                    td_set = set(str(d.date()) for d in td_list)
                    for t, s in valid_dates:
                        hold_cache[(t, s)] = sum(1 for d in td_set if t <= d <= s) - 1
            except: pass

            log.info("")
            log.info("📈 已卖出股票回顾:")
            log.info("-" * 80)
            log.info(f"| {'代码':<12} | {'买入价':>8} | {'卖出价':>8} | {'持有天数':>8} | {'收益率':>10} | {'卖出原因':<16} |")
            log.info("-" * 80)
            for r in show_list:
                buy_price = r['t0_price']
                sell_price = r.get('sell_price', buy_price)
                ret = (sell_price - buy_price) / buy_price * 100
                t0 = r.get('t0_date', '')
                sd = r.get('sell_date', '')
                hold_days = hold_cache.get((t0, sd), len(r.get('price_dates', [])))
                if hold_days < 1: hold_days = 1
                reason = r.get('sell_reason', '顶分型卖出')[:14]
                log.info(f"| {r['code']:<12} | {buy_price:>8.2f} | {sell_price:>8.2f} | {hold_days:>8}天 | {ret:>+9.1f}% | {reason:<16} |")
            log.info("-" * 80)

def after_market_close(context):
    date_str = context.current_dt.strftime('%Y-%m-%d %H:%M')
    today = context.current_dt.strftime('%Y-%m-%d')
    log.info(f'\n{"="*60}')
    log.info(f'📊 [{today}] 收盘统计')
    log.info(f'{"="*60}')
    total_value = context.portfolio.total_value
    available_cash = context.portfolio.available_cash
    positions_value = context.portfolio.positions_value
    log.info(f"💰 账户: 总{total_value:,.0f}元 | 现金{available_cash:,.0f}元 | 持仓{positions_value:,.0f}元")
    if context.portfolio.positions:
        log.info(f"\n📋 持仓明细:")
        for stock, pos in context.portfolio.positions.items():
            profit_pct = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0
            sign = "+" if profit_pct >= 0 else ""
            log.info(f"   [{stock}] 成本{pos.avg_cost:.2f} 现价{pos.price:.2f} 盈亏{sign}{profit_pct:.1f}%")
    else:
        log.info("📋 持仓: 无")
    records = g.sell_config.get('sell_records', [])
    today_sells = [r for r in records if r['time'].startswith(today)]
    if today_sells:
        total_profit = sum(r['profit_amount'] for r in today_sells)
        profit_count = len([r for r in today_sells if r['profit_amount'] >= 0])
        loss_count = len([r for r in today_sells if r['profit_amount'] < 0])
        sign = "+" if total_profit >= 0 else ""
        log.info(f"\n📈 今日卖出: {len(today_sells)}笔 | 总盈亏{sign}{total_profit:.0f}元 | ✅{profit_count}笔 ❌{loss_count}笔")
    else:
        log.info("📈 今日卖出: 无")
    log.info(f'{"="*60}\n')

# ==================== 结束 ====================