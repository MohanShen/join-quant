# Clone from JoinQuant
# postId: 158c3d10ab37f6550c6eb3ac27dd9ca4
# backtestId: 113946560a32c6ba91c4f96119d312e3
# title: 强者恒强策略不行

# 克隆自聚宽文章：https://www.joinquant.com/post/78522
# 标题：改良过的恒者越强策略 0824
# 作者：voidcui

from jqdata import *
import datetime
import random
import pandas as pd
import requests


# ========================== 统一通知配置 ==========================
# 总开关：False 时关闭全部通知。
NOTIFY_ENABLED = False

# Bark 通道开关及地址。
BARK_PUSH_URL = ''
BARK_ENABLED = False

# 企业微信机器人通道开关及 Webhook 地址。
# 在企业微信群中添加机器人后，将 Webhook 地址填到下方引号内。
WECHAT_WORK_WEBHOOK_URL = ''
WECHAT_WORK_ENABLED = True


def get_market_score(context):
    """大盘择时评分(基于昨日收盘数据, T-1语义)"""
    score = 0
    try:
        days = get_trade_days(end_date=context.current_dt.date(), count=2)
        ref_date = days[0] if len(days) >= 2 else context.current_dt.date()
    except:
        ref_date = context.current_dt.date()
    try:
        hs300 = get_price('000300.XSHG', end_date=ref_date, count=20, fields=['close'])
        if len(hs300) >= 20:
            ma5, ma10, ma20 = hs300['close'].iloc[-5:].mean(), hs300['close'].iloc[-10:].mean(), hs300['close'].mean()
            if ma5 > ma10 > ma20:
                score += 4
            elif ma5 < ma10 < ma20:
                score -= 4
    except:
        pass
    try:
        all_stocks = [s for s in get_all_securities(['stock']).index if '.BJ' not in s]
        sample = random.sample(all_stocks, min(500, len(all_stocks)))
        up, total = 0, 0
        for s in sample:
            try:
                h = get_price(s, end_date=ref_date, count=2, fields=['close'], skip_paused=True)
                if len(h) >= 2 and h['close'].iloc[-2] > 0:
                    if h['close'].iloc[-1] > h['close'].iloc[-2]:
                        up += 1
                    total += 1
            except:
                pass
        if total > 0 and up / total > 0.6:
            score += 3
        elif total > 0 and up / total < 0.4:
            score -= 3
    except:
        pass
    # 宽度优先防线: 均线空头(-4)+个股普涨(+3)=-1 → 上修到0, 防系统性踏空
    if score == -1:
        score = 0
    return score


def get_trading_status(context):
    """按择时评分返回(状态, 仓位系数)"""
    score = get_market_score(context)
    g.market_score = score
    if score >= 6:
        return "full", 1.0
    elif score >= 3:
        return "half", 0.6
    elif score >= 0:
        return "light", 0.3
    else:
        return "empty", 0.0

def bark_notify(title, content, level='active', group='A股策略'):
    """Bark 推送；失败只记录日志，绝不中断交易。"""
    if not BARK_ENABLED:
        return False

    if not BARK_PUSH_URL or '替换' in BARK_PUSH_URL:
        log.warn('Bark 推送地址尚未配置')
        return False

    payload = {
        'title': str(title)[:100],
        'body': str(content),
        'markdown': str(content),
        'group': group,
        'level': level,
        'isArchive': '1',
    }

    try:
        response = requests.post(
            BARK_PUSH_URL.rstrip('/'),
            json=payload,
            timeout=3,
        )
        try:
            result = response.json()
        except:
            result = {'raw': response.text[:200]}

        if response.status_code == 200 and result.get('code') in (200, None):
            log.info('Bark推送成功：{}'.format(title))
            return True

        log.warn(
            'Bark推送失败 HTTP{}：{}'.format(
                response.status_code, str(result)[:200]
            )
        )
    except Exception as e:
        log.warn('Bark推送异常：{}'.format(str(e)[:200]))

    return False


def wechat_work_notify(title, content):
    """企业微信机器人推送；失败只记录日志，绝不中断交易。"""
    if not WECHAT_WORK_ENABLED:
        return False

    if (not WECHAT_WORK_WEBHOOK_URL
            or '替换' in WECHAT_WORK_WEBHOOK_URL):
        log.warn('企业微信 Webhook 地址尚未配置')
        return False

    # 与 Bark 共用同一份 Markdown 内容，限制字节数避免超过机器人上限。
    message = '{}\n{}'.format(title, content)
    suffix = '\n……内容过长，已截断'
    max_bytes = 3900
    encoded = message.encode('utf-8')
    if len(encoded) > max_bytes:
        keep_bytes = max_bytes - len(suffix.encode('utf-8'))
        message = encoded[:keep_bytes].decode(
            'utf-8', errors='ignore'
        ) + suffix

    payload = {
        'msgtype': 'markdown',
        'markdown': {
            'content': message,
        },
    }

    try:
        response = requests.post(
            WECHAT_WORK_WEBHOOK_URL,
            json=payload,
            timeout=5,
        )
        try:
            result = response.json()
        except:
            result = {'raw': response.text[:200]}

        if response.status_code == 200 and result.get('errcode') == 0:
            log.info('企业微信推送成功：{}'.format(title))
            return True

        log.warn(
            '企业微信推送失败 HTTP{}：{}'.format(
                response.status_code, str(result)[:200]
            )
        )
    except Exception as e:
        log.warn('企业微信推送异常：{}'.format(str(e)[:200]))

    return False


def notify_all(title, content, level='active', group='A股策略'):
    """将同一份内容发送到所有已开启的通知通道。"""
    if not NOTIFY_ENABLED:
        return False

    results = []
    if BARK_ENABLED:
        results.append(
            bark_notify(title, content, level=level, group=group)
        )
    if WECHAT_WORK_ENABLED:
        results.append(wechat_work_notify(title, content))
    return any(results)


def get_buy_limit_premium():
    """与实际买入委托保持一致的涨价比例。"""
    if g.market_env == 'bull':
        return 1.022
    if g.market_env == 'bear':
        return 1.018
    return 1.019


def push_planned_buy_list(context, buy_candidates, final_buy_num, get_gain_diff):
    """只推送本轮最终计划买入的股票，不推送完整排行榜。"""
    final_buy_num = max(0, int(final_buy_num))
    selected = buy_candidates[:final_buy_num]
    if not selected:
        return False

    buy_signature = tuple(stock for stock, _ in selected)
    last_signature = getattr(g, 'last_buy_push_signature', None)
    last_time = getattr(g, 'last_buy_push_time', None)
    elapsed = None
    if last_time is not None:
        elapsed = (context.current_dt - last_time).total_seconds()

    if buy_signature == last_signature and elapsed is not None and elapsed < 300:
        log.info('Bark买入提醒去重：入选股票未变且距上次推送不足5分钟')
        return False

    lines = [
        '## 🛒 本轮计划买入 {} 只股票'.format(len(selected)),
        '',
        '- 时间：{}'.format(context.current_dt.strftime('%Y-%m-%d %H:%M:%S')),
        '',
    ]

    for i, (stock, reason) in enumerate(selected):
        try:
            stock_name = get_security_info(stock).display_name
        except:
            stock_name = '未知'

        yesterday_close = 0
        open_price = 0
        auction_price = 0
        current_price = 0
        auction_gain = 0
        current_gain = 0
        lift_gain = 0
        expected_amount = 0
        limit_price = 0
        try:
            trade_days = get_trade_days(
                end_date=context.current_dt.date(), count=2
            )

            current_data = get_current_data()[stock]
            open_price = float(current_data.day_open or 0)
            current_price = float(current_data.last_price or 0)
            auction_price = float(current_data.day_open or 0)

            if len(trade_days) >= 2:
                yesterday_data = get_price(
                    stock,
                    end_date=trade_days[0],
                    count=1,
                    fields=['close'],
                    fq='pre',
                )
                if not yesterday_data.empty:
                    yesterday_close = float(yesterday_data['close'].iloc[0])

            if yesterday_close > 0:
                auction_gain = (
                    (auction_price - yesterday_close) / yesterday_close * 100
                )
                current_gain = (
                    (current_price - yesterday_close) / yesterday_close * 100
                )
            lift_gain = float(get_gain_diff(stock, context))

            remain_buy = g.max_stock_num - len(context.portfolio.positions)
            if remain_buy > 0 and current_price > 0:
                target_cash = context.portfolio.available_cash / remain_buy
                expected_amount = int(target_cash / current_price / 100) * 100
                limit_price = min(
                    current_price * get_buy_limit_premium(),
                    float(current_data.high_limit),
                )
        except Exception as e:
            log.warn('Bark买入明细获取异常 {}: {}'.format(stock, str(e)[:50]))

        safe_reason = str(reason).replace('|', '/')
        lines.extend([
            '### {}. {} {}'.format(i + 1, stock, stock_name),
            '- 入选条件：{}'.format(safe_reason),
            '- 昨收：{:.3f}｜开盘：{:.3f}｜竞价：{:.3f}'.format(
                yesterday_close, open_price, auction_price
            ),
            '- 当前：{:.3f}｜竞价涨幅：{:.2f}%｜当前涨幅：{:.2f}%'.format(
                current_price, auction_gain, current_gain
            ),
            '- 盘中拉升：{:.2f}%'.format(lift_gain),
            '- 预计买入：{} 股｜委托限价：{:.3f}'.format(
                expected_amount, limit_price
            ),
            '',
        ])

    pushed = notify_all(
        '计划买入 {} 只股票 {}'.format(
            len(selected), context.current_dt.strftime('%H:%M')
        ),
        '\n'.join(lines),
        level='active',
        group='A股-买入',
    )
    # 无论成功与否都记录本次尝试，防止网络异常引发重试风暴。
    g.last_buy_push_signature = buy_signature
    g.last_buy_push_time = context.current_dt
    return pushed


def push_before_sell_batch(sell_reasons, context):
    """合并推送本轮全部卖出标的；同一股票当日只提醒一次。"""
    if not hasattr(g, 'sell_notified_today'):
        g.sell_notified_today = set()

    pending = [
        (stock, reason) for stock, reason in sell_reasons.items()
        if stock not in g.sell_notified_today
        and stock in context.portfolio.positions
    ]
    if not pending:
        return False

    lines = [
        '## 📤 即将卖出 {} 只股票'.format(len(pending)),
        '',
        '- 时间：{}'.format(context.current_dt.strftime('%Y-%m-%d %H:%M:%S')),
        '',
    ]
    for i, (stock, reason) in enumerate(pending):
        pos = context.portfolio.positions.get(stock)
        try:
            stock_name = get_security_info(stock).display_name
        except:
            stock_name = '未知'
        current_price = getattr(pos, 'price', 0) or 0
        avg_cost = getattr(pos, 'avg_cost', 0) or 0
        amount = getattr(pos, 'closeable_amount', getattr(pos, 'total_amount', 0))
        profit_ratio = (
            (current_price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
        )
        lines.extend([
            '### {}. {} {}'.format(i + 1, stock, stock_name),
            '- 原因：{}'.format(reason or '策略卖出信号'),
            '- 数量：{} 股｜参考价：{:.3f}｜收益：{:.2f}%'.format(
                amount, current_price, profit_ratio
            ),
            '',
        ])

    pushed = notify_all(
        '即将卖出 {} 只股票'.format(len(pending)),
        '\n'.join(lines),
        level='timeSensitive',
        group='A股-卖出',
    )
    # 无论通知结果如何，本轮均不再重复请求，避免异常重试风暴。
    for stock, _ in pending:
        g.sell_notified_today.add(stock)
    return pushed

def get_dynamic_max_hold(total_asset):
    if total_asset < 100000:
        return 2, 2
    elif 100000 <= total_asset < 300000:
        return 3, 3
    elif 300000 <= total_asset < 1000000:
        return 4, 4
    elif 1000000 <= total_asset < 5000000:
        return 5, 5
    else:
        return 8, 8

def get_stock_board(stock):
    try:
        code = stock.split('.')[0]
        suffix = stock.split('.')[1] if '.' in stock else ''
        if (code.startswith('60') and suffix == 'XSHG') or \
           ((code.startswith('000') or code.startswith('001')) and suffix == 'XSHE'):
            return 'main'
        elif code.startswith(('300', '301', '302')) and suffix == 'XSHE':
            return 'gem'
        elif code.startswith('688') and suffix == 'XSHG':
            return 'star'
        else:
            return 'unknown'
    except Exception as e:
        log.warn(f"判断{stock}板块失败: {str(e)[:20]}")
        return 'unknown'

def calculate_continuous_gain(stock, end_date, days):
    try:
        hist = get_price(
            stock,
            end_date=end_date,
            count=days+1,
            fields=['close'],
            fq='pre',
            skip_paused=True
        )
        if len(hist) < days + 1:
            return -999
        start_price = hist['close'].iloc[0]
        end_price = hist['close'].iloc[-1]
        total_gain = (end_price - start_price) / start_price * 100
        return round(total_gain, 2)
    except Exception as e:
        log.warn(f"计算{stock}连续{days}天涨幅失败: {str(e)[:20]}")
        return -999

def filter_by_continuous_gain(stock, end_date):
    try:
        stock_name = get_security_info(stock).display_name
    except Exception as e:
        stock_name = "未知名称"
        log.warn(f"获取{stock}名称失败: {str(e)[:20]}")
    board = get_stock_board(stock)
    if board == 'main':
        check_days = 5
        max_gain = 60.0
    elif board in ['gem', 'star']:
        check_days = 3
        max_gain = 72.0
    else:
        return True, "未知板块，跳过涨幅过滤", stock_name
    total_gain = calculate_continuous_gain(stock, end_date, check_days)
    if total_gain == -999:
        return True, f"无法计算{check_days}天涨幅，跳过过滤", stock_name
    elif total_gain > max_gain:
        return False, f"{board}连续{check_days}天涨幅{total_gain}% > {max_gain}%", stock_name
    else:
        return True, f"{board}连续{check_days}天涨幅{total_gain}% ≤ {max_gain}%", stock_name

# ==================== 尾盘急拉过滤函数（核心） ====================
def filter_after_1430_gain(stock, date):
    """
    过滤前一日14:30后涨幅超标的股票（仅输出被过滤的票）
    - 主板：14:30后涨幅 > 5% 过滤
    - 创业板/科创板：14:30后涨幅 > 8% 过滤
    """
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        # 定义各板块涨幅阈值
        gain_thresholds = {
            'main': 5.0,   # 主板
            'gem': 8.0,    # 创业板
            'star': 8.0    # 科创板
        }
        if board not in gain_thresholds:
            return True, "未知板块，跳过尾盘涨幅过滤", stock_name

        # 构造14:30的时间点
        date_obj = pd.Timestamp(date)
        time_1430 = pd.Timestamp.combine(date_obj.date(), pd.Timestamp('14:30:00').time())
        end_time = pd.Timestamp.combine(date_obj.date(), pd.Timestamp('15:00:00').time())

        # 兜底机制：1分钟线 → 5分钟线 → 日线兜底
        min1_data = get_price(
            stock,
            start_date=time_1430,
            end_date=end_time,
            frequency='1m',
            fields=['close'],
            fq='pre',
            skip_paused=True
        )
        if min1_data.empty or len(min1_data) < 2:
            min5_data = get_price(
                stock,
                start_date=time_1430,
                end_date=end_time,
                frequency='5m',
                fields=['close'],
                fq='pre',
                skip_paused=True
            )
            if min5_data.empty or len(min5_data) < 2:
                daily_data = get_price(stock, end_date=date, count=1, fields=['open','close'], fq='pre')
                if daily_data.empty:
                    return True, "无尾盘数据，默认通过", stock_name
                price_1430 = daily_data['open'].iloc[0]
                price_close = daily_data['close'].iloc[0]
            else:
                price_1430 = min5_data['close'].iloc[0]
                price_close = min5_data['close'].iloc[-1]
        else:
            price_1430 = min1_data['close'].iloc[0]
            price_close = min1_data['close'].iloc[-1]

        # 计算涨幅
        gain = (price_close - price_1430) / price_1430 * 100
        gain = round(gain, 2)
        threshold = gain_thresholds[board]

        # 仅在过滤淘汰时输出日志
        if gain > threshold:
            log.error(f"❌ 尾盘过滤淘汰: {stock} {stock_name} | {board} | 14:30后涨幅{gain}% > {threshold}%")
            return False, f"{board}14:30后涨幅{gain}% > {threshold}%", stock_name
        else:
            return True, f"{board}14:30后涨幅{gain}% ≤ {threshold}%", stock_name
    except Exception as e:
        # 异常时不输出日志，直接默认通过
        return True, f"过滤异常({str(e)[:20]})，默认通过", "未知名称"
# ==============================
# 高位放量涨停 + 竞价风险识别（聚宽专用）
# 用于：开盘前过滤掉“明天大概率大跌”的票
# ==============================
def is_risk_stock(context, stock):
    try:
        stock_name = get_security_info(stock).display_name
        log.info(f"【调试1】检查 {stock} {stock_name}")
        
        # 获取昨日及前日数据
        df = attribute_history(stock, 3, '1d', fields=['close', 'volume', 'high_limit'], skip_paused=True, df=True)
        if df is None or len(df) < 3:
            log.info(f"【调试1】{stock} 数据不足")
            return False

        close_yest = df['close'].iloc[-1]
        vol_yest = df['volume'].iloc[-1]
        vol_beyest = df['volume'].iloc[-2]
        high_limit = df['high_limit'].iloc[-1]
        
        log.info(f"【调试1】{stock} 昨日收盘:{close_yest:.2f}, 涨停价:{high_limit:.2f}, 昨日量:{vol_yest}, 前日量:{vol_beyest}")

        # 昨日是否涨停
        is_limit_up = (close_yest >= high_limit - 0.01)
        log.info(f"【调试1】{stock} 是否涨停: {is_limit_up}")

        # 昨日放量
        is_vol_big = (vol_yest >= vol_beyest * 1.8)
        log.info(f"【调试1】{stock} 是否放量1.8倍: {is_vol_big}, 实际倍数: {vol_yest/vol_beyest:.2f}")

        # 近期高位
        df20 = attribute_history(stock, 20, '1d', fields=['close'], skip_paused=True, df=True)
        if df20 is not None and len(df20) >= 20:
            rise_rate = (df20['close'].iloc[-1] / df20['close'].iloc[0] - 1)
        else:
            rise_rate = 0
        is_high = (rise_rate > 0.30)
        log.info(f"【调试1】{stock} 20日涨幅: {rise_rate*100:.2f}%, 是否高位: {is_high}")

        is_danger_yest = is_limit_up and is_vol_big and is_high
        log.info(f"【调试1】{stock} 是否高位放量涨停: {is_danger_yest}")
        
        if not is_danger_yest:
            return False

        # 今日竞价
        current_data = get_current_data()[stock]
        open_price = current_data.day_open
        pre_close = close_yest
        open_rate = (open_price / pre_close - 1) * 100
        log.info(f"【调试1】{stock} 今日开盘:{open_price:.2f}, 昨日收盘:{pre_close:.2f}, 开盘涨幅:{open_rate:.2f}%")

        if open_rate >= 4:
            log.info(f"⚠️ 风险股票 {stock} {stock_name}：昨日高位放量涨停+今日高开{open_rate:.1f}%")
            return True

        if 2 < open_rate < 3:
            log.info(f"⚠️ 风险股票 {stock} {stock_name}：昨日高位放量涨停+今日小幅高开{open_rate:.1f}%")
            return True

        log.info(f"【调试1】{stock} 未触发风险条件")
        return False
    except Exception as e:
        log.warn(f"【调试1】异常 {stock}: {str(e)[:50]}")
        return False

def is_auction_drop(context, stock):
    try:
        stock_name = get_security_info(stock).display_name
        log.info(f"【调试2】检查 {stock} {stock_name}")
        
        # 1. 获取昨日收盘价
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False
        yesterday_close = get_price(stock, end_date=trade_days[0], count=1, fields=['close'], fq='pre')['close'].iloc[0]
        
        # 2. 获取今日竞价数据（关键：用 get_current_data）
        current_data = get_current_data()[stock]
        open_price = current_data.day_open
        if open_price <= 0:
            return False
        
        # 3. 判断高开低走：
        open_ratio = (open_price - yesterday_close) / yesterday_close * 100
        if open_ratio > 0 and open_ratio < (open_ratio + 1) * 0.98:
            log.info(f"⚠️ 竞价高开低走 {stock} {stock_name}：高开{open_ratio:.1f}%，但开盘回落")
            return True
        
        return False
    except Exception as e:
        log.warn(f"【调试2】异常 {stock}: {str(e)[:50]}")
        return False
    
def is_weak_limit_up(context, stock):
    try:
        stock_name = get_security_info(stock).display_name
        log.info(f"【调试3】检查 {stock} {stock_name}")
        
        df = attribute_history(stock, 1, '1d', fields=['close', 'high_limit'], skip_paused=True, df=True)
        if df.empty:
            log.info(f"【调试3】{stock} 无昨日数据")
            return False
        
        close_yest = df['close'].iloc[-1]
        high_limit = df['high_limit'].iloc[-1]
        is_limit_yest = (close_yest >= high_limit - 0.01)
        log.info(f"【调试3】{stock} 昨日是否涨停: {is_limit_yest}")
        
        if not is_limit_yest:
            return False

        current_data = get_current_data()[stock]
        if not hasattr(current_data, 'bid1_volume') or current_data.bid1_volume is None:
            log.info(f"【调试3】{stock} 无 bid1_volume 数据")
            return False
        
        bid1_volume = current_data.bid1_volume
        log.info(f"【调试3】{stock} 买一量: {bid1_volume}")

        q = query(valuation.circulating_cap).filter(valuation.code == stock)
        df_cap = get_fundamentals(q, date=context.current_dt.date())
        if df_cap.empty:
            log.info(f"【调试3】{stock} 无流通股本数据")
            return False
        
        # 修复：流通股本单位错误（万股→股需要×10000×100）
        circulating_share = df_cap['circulating_cap'].iloc[0] * 10000 * 100
        log.info(f"【调试3】{stock} 流通股本: {circulating_share}")

        ratio = bid1_volume / circulating_share * 100
        log.info(f"【调试3】{stock} 封单占比: {ratio:.2f}%")

        if ratio < 1:
            log.info(f"⚠️ 封单过小 {stock} {stock_name}")
            return True
        return False
    except Exception as e:
        log.warn(f"【调试3】异常 {stock}: {str(e)[:50]}")
        return False
        
# ==================== 振幅过滤函数 ====================
def filter_by_amplitude(stock, date):
    """
    按板块过滤昨日振幅：
    - 主板：振幅 > 16% 过滤
    - 创业板/科创板：振幅 > 20% 过滤
    返回 (是否通过, 消息, 股票名称)
    """
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        # 定义各板块振幅阈值
        amp_thresholds = {
            'main': 16.0,   # 主板
            'gem': 20.0,    # 创业板
            'star': 20.0    # 科创板
        }
        if board not in amp_thresholds:
            return True, "未知板块，跳过振幅过滤", stock_name

        # 获取昨日日线数据
        hist = attribute_history(stock, 1, '1d', fields=['high', 'low', 'close'], skip_paused=True, df=True)
        if hist.empty:
            return True, "无振幅数据", stock_name
        high = hist['high'].iloc[-1]
        low = hist['low'].iloc[-1]
        close = hist['close'].iloc[-1]
        if close == 0:
            return True, "昨日收盘价为0", stock_name
        amplitude = (high - low) / close * 100
        amplitude = round(amplitude, 2)
        threshold = amp_thresholds[board]
        if amplitude >= threshold:
            return False, f"{board}昨日振幅{amplitude}% ≥ {threshold}%", stock_name
        else:
            return True, f"{board}昨日振幅{amplitude}% < {threshold}%", stock_name
    except Exception as e:
        return True, f"振幅异常({str(e)[:20]})", stock_name
# ==================== 换手率过滤 ====================
def filter_by_turnover(stock, date):
    """
    按板块过滤前一交易日换手率：
    - 主板：换手率 > 24% 过滤
    - 创业板/科创板：换手率 > 28% 过滤
    参数 date：前一交易日（必须是交易日）
    返回 (是否通过, 消息, 股票名称)
    """
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        # 定义各板块换手率阈值
        turnover_thresholds = {
            'main': 24.0,
            'gem': 28.0,
            'star': 28.0
        }
        if board not in turnover_thresholds:
            return True, "未知板块，跳过换手率过滤", stock_name

        threshold = turnover_thresholds[board]
        turnover = None

        # 方法1：从资金流向获取换手率（官方接口，最准确）
        try:
            turnover_df = get_money_flow(stock, start_date=date, end_date=date)
            if not turnover_df.empty and 'turnover_rate' in turnover_df.columns:
                turnover = turnover_df['turnover_rate'].iloc[0]
        except Exception as e:
            log.warn(f"资金流向获取失败 {stock}: {str(e)[:30]}")

        # 方法2：手动计算（使用 valuation 表的流通股本）
        if turnover is None:
            try:
                # 获取昨日成交量（单位：股）
                vol_data = attribute_history(stock, 1, '1d', fields=['volume'], skip_paused=True, df=True)
                if vol_data.empty:
                    log.warn(f"换手率过滤: {stock} 无成交量数据")
                    return False, "无成交量数据", stock_name
                volume = vol_data['volume'].iloc[-1]

                # 从 valuation 表获取流通股本（单位：万股）
                q = query(valuation.circulating_cap).filter(valuation.code == stock)
                df = get_fundamentals(q, date=date)
                if df.empty:
                    log.warn(f"换手率过滤: {stock} 无法获取流通股本")
                    return False, "无流通股本", stock_name

                # 转为股
                float_share = df['circulating_cap'].iloc[0] * 10000
                if float_share <= 0:
                    log.warn(f"换手率过滤: {stock} 流通股本为0")
                    return False, "流通股本异常", stock_name

                turnover = volume / float_share * 100
            except Exception as e:
                log.warn(f"换手率过滤: {stock} 手动计算异常: {str(e)[:50]}")
                return False, f"计算异常", stock_name

        # 统一处理结果
        if turnover is None:
            return False, "无法获取换手率", stock_name

        turnover = round(float(turnover), 2)

        if turnover >= threshold:
            return False, f"{board}昨日换手率{turnover}% ≥ {threshold}%", stock_name
        else:
            return True, f"{board}昨日换手率{turnover}% < {threshold}%", stock_name

    except Exception as e:
        log.error(f"换手率过滤异常 {stock}: {str(e)[:50]}")
        return False, f"过滤异常", stock_name
# ==================== 一个月翻倍过滤 ====================
def is_double_in_month(stock, context):
    """判断股票是否在一个月内翻倍"""
    try:
        # 获取一个月前的收盘价（约20个交易日）
        hist = attribute_history(stock, 20, '1d', fields=['close'], skip_paused=True, df=True)
        if len(hist) < 20:
            return False
        # 一个月前收盘价，今日收盘价
        old_price = hist['close'].iloc[0]
        today_price = hist['close'].iloc[-1]
        if old_price <= 0:
            return False
        # 计算涨幅
        gain = (today_price - old_price) / old_price * 100
        # 涨幅超过100%则过滤
        return gain >= 95
    except:
        return False
# ==================== 近3日跌停过滤 ====================
def has_limit_down_in_last_3days(stock, date):
    """
    过滤近3个交易日有过跌停的股票
    返回 (是否通过, 消息, 股票名称)
    """
    try:
        stock_name = get_security_info(stock).display_name
        # 获取最近3个交易日（不包括date当天，date是昨天）
        hist = attribute_history(stock, 3, '1d', fields=['close', 'low_limit'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name
        for i in range(len(hist)):
            close = hist['close'].iloc[i]
            low_limit = hist['low_limit'].iloc[i]
            # 跌停判断：收盘价接近跌停价（允许千分之五误差）
            if close <= low_limit * 1.005:
                return False, f"近3日有跌停", stock_name
        return True, "近3日无跌停", stock_name
    except Exception as e:
        return True, f"跌停异常({str(e)[:20]})", stock_name
# ==================== 连续3日缩量上涨过滤 ====================
def is_continuous_shrink_rise(stock, date):
    """
    过滤近连续3个交易日缩量上涨（每日收盘上涨，成交量逐日萎缩）
    返回 (是否通过, 消息, 股票名称)
    """
    try:
        stock_name = get_security_info(stock).display_name
        # 获取最近3个交易日（不包括date当天，date是昨天），需要收盘价和成交量
        hist = attribute_history(stock, 3, '1d', fields=['close', 'volume'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name
        # 检查是否连续上涨
        for i in range(1, 3):
            if hist['close'].iloc[i] <= hist['close'].iloc[i-1]:
                return True, "非连续上涨", stock_name  # 不是连续上涨，不触发过滤
        # 检查成交量是否连续萎缩
        for i in range(1, 3):
            if hist['volume'].iloc[i] >= hist['volume'].iloc[i-1]:
                return True, "非连续缩量", stock_name  # 不是连续缩量，不触发过滤
        # 如果连续上涨且连续缩量，则过滤掉
        return False, "连续3日缩量上涨", stock_name
    except Exception as e:
        return True, f"缩量异常({str(e)[:20]})", stock_name
# ===================== 9:30 纯卖出函数（带资金日志） =====================
def sell_only_930(context):
    log.info("=== 9:30 专属卖出开始 ===")
    log.info(f"💵 卖出前可用资金：{context.portfolio.available_cash:.2f}")
    total_asset = context.portfolio.total_value
    g.max_stock_num, g.max_buy_per_day = get_dynamic_max_hold(total_asset)

    # 先收集本轮所有卖出原因，只发一条 Bark 合并提醒。
    sell_reasons = collect_break_limit_sell_reasons(context)
    for stock in list(context.portfolio.positions.keys()):
        # ========== 修复 T+1：今日买的不卖出 ==========
        if stock in g.bought_stocks:
            continue
        try:
            cd = get_current_data()[stock]
            hl = cd.high_limit
            op = cd.day_open
            if abs(op - hl) / hl > 0.005:
                log.info("📤 9:30 开盘未涨停卖出：" + stock)
                sell_reasons.setdefault(stock, '9:30开盘未涨停')
        except:
            continue

    for stock, reason in collect_sell_decision_reasons(context).items():
        sell_reasons.setdefault(stock, reason)
    execute_sell_batch(sell_reasons, context)

    log.info(f"💵 卖出后可用资金：{context.portfolio.available_cash:.2f}")
    log.info("=== 9:30 卖出全部完成 ===")


def collect_break_limit_sell_reasons(context, long_hold_only=False):
    """收集炸板回落卖出信号，不在此函数内下单。"""
    sell_reasons = {}
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        if long_hold_only and g.hold_days.get(stock, 0) <= 1:
            continue
        try:
            cd = get_current_data()[stock]
            current_price = cd.last_price
            today_high = cd.high
            high_limit = cd.high_limit
            if today_high >= high_limit * 0.995:
                g.has_limit_up.add(stock)
            if stock in g.has_limit_up:
                drop_ratio = (today_high - current_price) / today_high * 100
                if drop_ratio >= g.break_drop_ratio:
                    sell_reasons[stock] = (
                        '涨停后回落{:.2f}% ≥ {:.2f}%'.format(
                            drop_ratio, g.break_drop_ratio
                        )
                    )
                    if stock not in g.break_limit_sold_stocks:
                        g.break_limit_sold_stocks.append(stock)
        except:
            continue
    return sell_reasons


def check_break_limit_drop_for_long_hold(context):
    sell_reasons = collect_break_limit_sell_reasons(context, long_hold_only=True)
    execute_sell_batch(sell_reasons, context)


def check_break_limit_drop(context):
    sell_reasons = collect_break_limit_sell_reasons(context)
    execute_sell_batch(sell_reasons, context)

def initialize(context):
    context.order_cost = OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5
    )
    g.debug = True
    g.max_stock_num = 3
    g.max_buy_per_day = 3
    g.base_min_open_ratio = 0
    g.base_max_open_ratio = 8.0
    g.base_stop_loss_ratio = -4.0
    g.base_stop_profit_ratio = 19.0
    g.base_max_hold_days = 3
    g.base_break_drop_ratio = 1.5
    # ========== 修复：放宽换手率 ==========
    g.base_min_turnover_rate = 2
    g.base_min_volume_ratio = 1.2
    g.ma_period = 5
    g.base_min_limit_up_time = 90
    g.base_min_volume_growth = 1.0
    # ========== 新增：竞价过滤统计变量 ==========
    g.risk_filter_count = 0      # 风险股票过滤数量
    g.auction_drop_count = 0     # 竞价高开低走过滤数量
    g.weak_limitup_count = 0     # 封单过小过滤数量
    g.total_filtered = 0         # 总过滤数量

    g.min_open_ratio = g.base_min_open_ratio
    g.max_open_ratio = g.base_max_open_ratio
    g.stop_loss_ratio = g.base_stop_loss_ratio
    g.stop_profit_ratio = g.base_stop_profit_ratio
    g.max_hold_days = g.base_max_hold_days
    g.break_drop_ratio = g.base_break_drop_ratio
    g.min_turnover_rate = g.base_min_turnover_rate
    g.min_volume_ratio = g.base_min_volume_ratio
    g.min_limit_up_time = g.base_min_limit_up_time
    g.min_volume_growth = g.base_min_volume_growth

    g.candidate_stocks = []
    g.hold_days = {}
    g.has_limit_up = set()
    g.bought_stocks = set()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.market_env = "normal"
    g.only_buy = False
    g.break_limit_sold_stocks = []
    # ========== 记录当日卖出明细 ==========
    g.sold_today = []
    # 卖出前提醒去重：同一只股票当日只推送一次
    g.sell_notified_today = set()
    g.last_buy_push_signature = None
    g.last_buy_push_time = None

    g.market_score = 0
    g.market_cap = 1.0
    g.market_status = "normal"
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(PriceRelatedSlippage(0.002))
    # 成交量约束：单笔下单量不超过当日成交量的比例，防滑点过大/流动性不足
    g.max_volume_ratio = 0.10
    set_option('order_volume_ratio', g.max_volume_ratio)

    run_daily(before_market_open, time='before_open')
    # ========== 严格区分卖出/买入时间，9:30只卖，9:30:10才开始买 ==========
    run_daily(auction_filter, time='09:26:00')
    run_daily(set_only_buy_False, time='09:30:00')
    run_daily(sell_only_930, time='09:30:01')
    run_daily(set_only_buy_True, time='09:30:06')   # 延迟到9:30:10才开启买入
    run_daily(market_open, time='09:30:06')         # 首次买入延迟到9:30:10
    run_daily(market_open, time='09:31:00')
    run_daily(market_open, time='09:32:00')
    run_daily(market_open, time='09:37')
    run_daily(market_open, time='10:29')
    run_daily(after_market_close, time='after_close')
    

    for hour in range(10, 15):
        for minute in range(0, 60, 2):
            if (hour == 10 and minute < 20) or (hour == 14 and minute >= 56):
                continue
            time_str = f"{hour:02d}:{minute:02d}"
            run_daily(check_break_limit_drop_for_long_hold, time=time_str)

# ==================== 实时高开低走检测（9:30:05专用）====================
def is_real_time_drop(context, stock):
    try:
        stock_name = get_security_info(stock).display_name
        current_data = get_current_data()[stock]
        
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False, "无昨日数据"
            
        yesterday_close = get_price(stock, end_date=trade_days[0], count=1, fields=['close'], fq='pre')['close'].iloc[0]
        open_price = current_data.day_open
        current_price = current_data.last_price  
        
        if open_price <= 0 or current_price <= 0:
            return False, "价格异常"

        open_ratio = (open_price - yesterday_close) / yesterday_close * 100
        drop_ratio = (open_price - current_price) / open_price * 100

        if open_ratio > 0 and current_price < open_price and drop_ratio > 0.3:
            log.info(f"❌ 实时高开低走：{stock} {stock_name} 高开{open_ratio:.1f}%，开盘回落{drop_ratio:.1f}%")
            return True, f"回落{drop_ratio:.1f}%"
            
        return False, f"高开{open_ratio:.1f}%"
    except:
        return False, "检测异常"

def set_only_buy_True(context):
    g.only_buy = True
    log.info(f"当前时间{context.current_dt.time()}，设置为【仅买入模式】")

def set_only_buy_False(context):
    g.only_buy = False
    log.info(f"当前时间{context.current_dt.time()}，设置为【先卖后买模式】")

def adjust_params_by_market(context):
    try:
        trade_days = get_trade_days(end_date=context.previous_date, count=2)
        if len(trade_days) < 2:
            g.market_env = "normal"
            return
        hs300_data = get_price('000300.XSHG', end_date=trade_days[1], count=1, fields=['close'], fq='pre')
        hs300_prev_data = get_price('000300.XSHG', end_date=trade_days[0], count=1, fields=['close'], fq='pre')
        if hs300_data.empty or hs300_prev_data.empty:
            g.market_env = "normal"
            return
        hs300_change = (hs300_data['close'].iloc[0] - hs300_prev_data['close'].iloc[0]) / hs300_prev_data['close'].iloc[0] * 100

        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            limit_up_count = 50
        else:
            yesterday = trade_days[0]
            all_stocks = [code for code in get_all_securities(['stock']).index if '.BJ' not in code]
            limit_up_count = 0
            for stock in all_stocks[:500]:
                if is_limit_up_simple(stock, yesterday):
                    limit_up_count += 1

        if hs300_change > 1 and limit_up_count > 80:
            g.market_env = "bull"
            g.min_open_ratio = g.base_min_open_ratio + 1
            g.max_open_ratio = g.base_max_open_ratio - 1
            g.min_turnover_rate = g.base_min_turnover_rate + 1
            g.stop_profit_ratio = g.base_stop_profit_ratio + 2
        elif hs300_change < -1 and limit_up_count < 30:
            g.market_env = "bear"
            g.min_open_ratio = g.base_min_open_ratio - 0.5
            g.max_open_ratio = g.base_max_open_ratio + 1
            g.min_turnover_rate = g.base_min_turnover_rate - 0.5
            g.stop_loss_ratio = g.base_stop_loss_ratio + 1
        else:
            g.market_env = "normal"
            g.min_open_ratio = g.base_min_open_ratio
            g.max_open_ratio = g.base_max_open_ratio
            g.stop_loss_ratio = g.base_stop_loss_ratio
            g.stop_profit_ratio = g.base_stop_profit_ratio
            g.min_turnover_rate = g.base_min_turnover_rate

        log.info(f"市场环境：{g.market_env} | 开盘涨幅：{g.min_open_ratio}%~{g.max_open_ratio}% | 换手率：{g.min_turnover_rate}%")
    except Exception as e:
        log.warn(f"动态参数调整失败：{str(e)[:30]}")
        g.market_env = "normal"
        g.min_open_ratio = g.base_min_open_ratio
        g.max_open_ratio = g.base_max_open_ratio

def before_market_open(context):
    log.info("="*50)
    log.info("盘前选股开始: {}".format(context.current_dt.date()))
    g.candidate_stocks = []
    g.has_limit_up.clear()
    g.bought_stocks.clear()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.only_buy = False
    g.break_limit_sold_stocks = []
    # ========== 清空昨日卖出记录 ==========
    g.sold_today = []
    g.sell_notified_today = set()
    g.last_buy_push_signature = None
    g.last_buy_push_time = None
    if hasattr(g, 'checked_today'):
        del g.checked_today

    adjust_params_by_market(context)
    total_asset = context.portfolio.total_value
    g.max_stock_num, g.max_buy_per_day = get_dynamic_max_hold(total_asset)
    log.info(f"盘前动态配置：总资产{total_asset:.2f} → 最大持仓{g.max_stock_num}只，单日买入{g.max_buy_per_day}只")

    trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
    if len(trade_days) < 2:
        log.info("无昨日交易日，今日跳过选股")
        return
    yesterday = trade_days[0]

    current_tradable_stocks = [
        code for code in get_all_securities(['stock'], date=context.current_dt.date()).index
        if '.BJ' not in code
    ]
    # 主板main - 创业板gem - 科创板star，排除其余所有
    current_tradable_stocks = [
        code for code in current_tradable_stocks
        if get_stock_board(code) in ("main")
    ]
    log.info("今日可交易A股数量: {}".format(len(current_tradable_stocks)))

    limit_up_stocks = []
    batch_size = 1000
    for i in range(0, len(current_tradable_stocks), batch_size):
        batch_stocks = current_tradable_stocks[i:i+batch_size]
        for stock in batch_stocks:
            try:
                if is_st_stock(stock):
                    continue
                if is_limit_up_simple(stock, yesterday) or is_strong_stock(stock, yesterday):
                    # 1. 连续涨幅过滤
                    pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, yesterday)
                    if not pass_filter:
                        log.info(f"❌ {stock} {stock_name} 涨幅过滤淘汰：{filter_msg}")
                        continue
                    # 2. 尾盘急拉过滤
                    pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, yesterday)
                    if not pass_1430_filter:
                        log.info(f"❌ {stock} {stock_name} 尾盘涨幅过滤淘汰：{filter_1430_msg}")
                        continue
                    # 3. 振幅过滤
                    pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, yesterday)
                    if not pass_amp_filter:
                        log.info(f"❌ {stock} {stock_name} 振幅过滤淘汰：{amp_msg}")
                        continue
                    # 4. 换手率过滤
                    pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, yesterday)
                    if not pass_turnover_filter:
                        log.info(f"❌ {stock} {stock_name} 换手率过滤淘汰：{turnover_msg}")
                        continue
                    # 5. 近3日跌停过滤
                    pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, yesterday)
                    if not pass_limitdown_filter:
                        log.info(f"❌ {stock} {stock_name} 近3日跌停过滤淘汰：{limitdown_msg}")
                        continue
                    # 6. 连续3日缩量上涨过滤
                    pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, yesterday)
                    if not pass_shrink_filter:
                        log.info(f"❌ {stock} {stock_name} 连续3日缩量上涨过滤淘汰：{shrink_msg}")
                        continue
                    limit_up_stocks.append(stock)
            except Exception as e:
                log.warn("检查股票{}出错: {}".format(stock, str(e)[:30]))
                continue

    log.info("核心识别强势股(已过滤涨幅+尾盘急拉+振幅+换手+跌停+缩量): {}只".format(len(limit_up_stocks)))
    if len(limit_up_stocks) > 0:
        log.info("前30只强势股：")
        for stock in limit_up_stocks[:30]:
            try:
                stock_name = get_security_info(stock).display_name
                hist = get_price(stock, end_date=yesterday, count=2, fields=['close','high_limit'], fq='pre')
                if len(hist)>=2:
                    change = (hist['close'].iloc[-1] - hist['close'].iloc[-2]) / hist['close'].iloc[-2] * 100
                    log.info(f"  {stock} {stock_name} | 昨日涨幅: {change:.2f}%")
            except:
                log.info(f"  {stock}（名称获取失败）")

    if len(limit_up_stocks) == 0:
        log.info("无强势股，尝试宽松识别...")
        limit_up_stocks = find_limit_up_loose(current_tradable_stocks[:1500], yesterday)
        log.info("宽松识别后强势股: {}只".format(len(limit_up_stocks)))
        if len(limit_up_stocks) > 0:
            log.info("前30只强势股：")
            for stock in limit_up_stocks[:30]:
                try:
                    stock_name = get_security_info(stock).display_name
                    log.info(f"  {stock} {stock_name}")
                except:
                    log.info(f"  {stock}（名称获取失败）")

    if len(limit_up_stocks) == 0:
        log.info("宽松识别仍无结果，尝试超宽松识别...")
        limit_up_stocks = find_limit_up_ultra_loose(current_tradable_stocks[:1500], yesterday)
        log.info("超宽松识别后强势股: {}只".format(len(limit_up_stocks)))
        if len(limit_up_stocks) > 0:
            log.info("前30只强势股：")
            for stock in limit_up_stocks[:30]:
                try:
                    stock_name = get_security_info(stock).display_name
                    log.info(f"  {stock} {stock_name}")
                except:
                    log.info(f"  {stock}（名称获取失败）")

    # 先将所有通过基础过滤的股票加入候选池，竞价过滤将在9:25后执行
    g.candidate_stocks = limit_up_stocks.copy()
    g.rebuy_candidates = limit_up_stocks.copy()

# ==================== 9:26 极简竞价过滤（只拦风险股）====================
def auction_filter(context):
    log.info("="*50)
    log.info("9:26 竞价过滤（按板块区分高开阈值+开盘涨幅区间过滤）")
    
    # 初始化统计变量
    g.risk_filter_count = 0  # 风险股拦截数
    range_filter_count = 0   # 涨幅区间拦截数
    total_filter_count = 0   # 总拦截数
    final_stocks = []
    current_date = context.current_dt.date()
    
    for stock in g.candidate_stocks:
        # 基础质量检查（如停牌、退市等）
        if not check_basic_quality(stock, context):
            total_filter_count += 1
            continue
            
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知"
        is_risk = False
        risk_reason = ""
        
        try:
            # 获取板块信息
            board = get_stock_board(stock)
            
            # 设置不同板块的风险高开阈值（原逻辑保留）
            if board in ['gem', 'star']:  # 创业板/科创板
                open_threshold = 6.0
            elif board == 'main':          # 主板
                open_threshold = 5.0       
            else:
                open_threshold = 5.0  

            # 获取竞价开盘价和昨日收盘价，计算开盘涨幅
            trade_days = get_trade_days(end_date=context.previous_date, count=2)
            if len(trade_days) < 2:
                is_risk = True
                risk_reason = "无昨日交易日历数据"
                total_filter_count += 1
                continue
            yesterday_date = trade_days[1]
            day_before_yesterday = trade_days[0]
            hist = get_price(stock, start_date=day_before_yesterday, end_date=yesterday_date,
                             fields=['close','volume','high_limit'], fq='pre')
            current_data = get_current_data()[stock]
            open_price = current_data.day_open  # 竞价开盘价
            
            # 异常值处理：无数据则标记为异常，触发过滤
            if len(hist) < 2:
                is_risk = True
                risk_reason = "无昨日收盘价数据"
                log.info(f"❌ {stock} {stock_name} | 拦截原因：{risk_reason}")
                total_filter_count += 1
                continue
            
            # 计算开盘涨幅
            close_yest  = hist['close'].iloc[-1]   # 昨日收盘价
            open_ratio  = (open_price - close_yest) / close_yest * 100  # 开盘涨幅

            # ========== 核心修复：优先判断涨幅区间过滤 ==========
            if not (g.min_open_ratio <= open_ratio <= g.max_open_ratio):
                is_risk = True
                range_filter_count += 1  # 涨幅区间拦截数+1
                risk_reason = f"开盘涨幅{open_ratio:.1f}%，超出区间[{g.min_open_ratio}%,{g.max_open_ratio}%]"
                log.info(f"❌ {stock} {stock_name} | 拦截原因：{risk_reason}")
            
            # ========== 再判断风险股（仅未被区间过滤时执行） ==========
            if not is_risk and len(hist) >= 2:
                vol_yest    = hist['volume'].iloc[-1]   # 昨日成交量
                vol_beyest  = hist['volume'].iloc[-2]   # 前日成交量
                high_limit  = hist['high_limit'].iloc[-1]   # 昨日涨停价（昨收定的）
                is_limit_up = abs(close_yest - high_limit) / high_limit < 0.006
                is_vol_big  = vol_yest >= vol_beyest * 1.8

                if is_limit_up and is_vol_big and open_ratio >= open_threshold:
                    is_risk = True
                    g.risk_filter_count += 1  # 风险股拦截数+1
                    risk_reason = f"涨停+放量+高开{open_ratio:.1f}%（{board}阈值{open_threshold}%）"
                    log.info(f"❌ {stock} {stock_name} | 拦截原因：{risk_reason}")

        except Exception as e:
            is_risk = True  # 异常直接过滤
            risk_reason = f"过滤异常：{str(e)[:30]}"
            log.warn(f"❌ {stock} {stock_name} | 拦截原因：{risk_reason}")
        
        # 统计总拦截数 & 筛选最终候选股
        if is_risk:
            total_filter_count += 1
        else:
            final_stocks.append(stock)

    # 更新全局候选股列表
    g.candidate_stocks = final_stocks.copy()
    g.rebuy_candidates = final_stocks.copy()
    
    # ========== 输出准确的明细统计 ==========
    log.info(f"📊 竞价过滤统计：")
    log.info(f"   ├─ 涨幅区间拦截：{range_filter_count} 只")
    log.info(f"   ├─ 风险股拦截：{g.risk_filter_count} 只")
    log.info(f"   ├─ 其他异常拦截：{total_filter_count - range_filter_count - g.risk_filter_count} 只")
    log.info(f"   ├─ 合计拦截：{total_filter_count} 只")
    log.info(f"   └─ 剩余候选股：{len(final_stocks)} 只")
    log.info("="*50)

def is_main_board(stock):
    try:
        code = stock.split('.')[0]
        suffix = stock.split('.')[1] if '.' in stock else ''
        if code.startswith('60') and suffix == 'XSHG':
            return True
        if (code.startswith('000') or code.startswith('001')) and suffix == 'XSHE':
            return True
        return False
    except:
        return False

def is_st_stock(stock):
    try:
        name = get_security_info(stock).display_name
        return 'ST' in name or '*ST' in name or '退' in name
    except:
        return True

# ========== 过滤一字涨停/跌停 ==========
def is_limit_up_down(stock):
    try:
        data = get_price(stock, count=1, fields=['open','high_limit','low_limit'])
        if data.empty:
            return True
        op = data['open'][0]
        hl = data['high_limit'][0]
        ll = data['low_limit'][0]
        if abs(op - hl) < 0.001 or abs(op - ll) < 0.001:
            return True
        return False
    except:
        return True

def is_limit_up_simple(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close','high_limit'], fq='pre')
        if len(hist) < 2:
            return False
        yc = hist['close'].iloc[-1]
        yl = hist['high_limit'].iloc[-1]
        pc = hist['close'].iloc[-2]
        change = (yc - pc)/pc*100
        if change > 8.5 or abs(yc - yl)/yl < 0.006:
            return True
        return False
    except:
        return False

def is_strong_stock(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
        if len(hist) < 2:
            return False
        change = (hist['close'].iloc[-1] - hist['close'].iloc[-2])/hist['close'].iloc[-2] * 100
        return 6 <= change < 8.5
    except:
        return False

def find_limit_up_loose(stocks, date):
    limit_stocks = []
    for stock in stocks:
        try:
            if is_st_stock(stock):
                continue
            hist = get_price(stock, end_date=date, count=2, fields=['close','high'], fq='pre')
            if len(hist) < 2:
                continue
            yc = hist['close'].iloc[-1]
            yh = hist['high'].iloc[-1]
            pc = hist['close'].iloc[-2]
            change = (yc - pc)/pc*100
            if change > 8.0 or (abs(yh - yc)/yc < 0.01 and change > 6.5):
                # 1. 连续涨幅过滤
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    log.info(f"❌ {stock} {stock_name} 宽松选股涨幅过滤淘汰：{filter_msg}")
                    continue
                # 2. 尾盘急拉过滤
                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    log.info(f"❌ {stock} {stock_name} 宽松选股尾盘过滤淘汰：{filter_1430_msg}")
                    continue
                # 3. 振幅过滤
                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    log.info(f"❌ {stock} {stock_name} 宽松选股振幅过滤淘汰：{amp_msg}")
                    continue
                # 4. 换手率过滤
                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    log.info(f"❌ {stock} {stock_name} 宽松选股换手率过滤淘汰：{turnover_msg}")
                    continue
                # 5. 近3日跌停过滤
                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    log.info(f"❌ {stock} {stock_name} 宽松选股近3日跌停过滤淘汰：{limitdown_msg}")
                    continue
                # 6. 连续3日缩量上涨过滤
                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    log.info(f"❌ {stock} {stock_name} 宽松选股连续3日缩量上涨过滤淘汰：{shrink_msg}")
                    continue
                limit_stocks.append(stock)
                log.info("宽松涨停: {} {} 涨幅: {:.2f}% | {}".format(stock, stock_name, change, filter_msg))
        except:
            continue
    return limit_stocks

def find_limit_up_ultra_loose(stocks, date):
    limit_stocks = []
    for stock in stocks:
        try:
            if is_st_stock(stock):
                continue
            hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
            if len(hist) < 2:
                continue
            change = (hist['close'].iloc[-1] - hist['close'].iloc[-2])/hist['close'].iloc[-2] * 100
            if change > 5.0:
                # 1. 连续涨幅过滤
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    log.info(f"❌ {stock} {stock_name} 超宽松选股涨幅过滤淘汰：{filter_msg}")
                    continue
                # 2. 尾盘急拉过滤
                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    log.info(f"❌ {stock} {stock_name} 超宽松选股尾盘过滤淘汰：{filter_1430_msg}")
                    continue
                # 3. 振幅过滤
                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    log.info(f"❌ {stock} {stock_name} 超宽松选股振幅过滤淘汰：{amp_msg}")
                    continue
                # 4. 换手率过滤
                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    log.info(f"❌ {stock} {stock_name} 超宽松选股换手率过滤淘汰：{turnover_msg}")
                    continue
                # 5. 近3日跌停过滤
                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    log.info(f"❌ {stock} {stock_name} 超宽松选股近3日跌停过滤淘汰：{limitdown_msg}")
                    continue
                # 6. 连续3日缩量上涨过滤
                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    log.info(f"❌ {stock} {stock_name} 超宽松选股连续3日缩量上涨过滤淘汰：{shrink_msg}")
                    continue
                limit_stocks.append(stock)
                log.info("超宽松识别: {} {} 涨幅: {:.2f}% | {}".format(stock, stock_name, change, filter_msg))
        except:
            continue
    return limit_stocks

def check_basic_quality(stock, context):
    try:
        # ========== 过滤一字板 & 停牌 ==========
        if is_limit_up_down(stock):
            return False
        return get_current_data()[stock].day_open > 0
    except:
        return False

def calculate_turnover_rate(stock, date):
    try:
        vol_data = get_price(stock, end_date=date, count=1, fields=['volume'], fq='pre')
        if vol_data.empty:
            return 0.0
        volume = vol_data['volume'].iloc[0]
        stock_info = get_security_info(stock)
        float_share = stock_info.float_share if hasattr(stock_info, 'float_share') else 0
        if float_share == 0:
            return 0.0
        return (volume / (float_share * 10000)) * 100
    except:
        return 0.0

def check_turnover_volume(stock, context):
    try:
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=3)
        if len(trade_days) < 3:
            return True, "无足够数据"
        yesterday = trade_days[0]
        day_before_yesterday = trade_days[1]

        turnover_df = get_money_flow(stock, start_date=yesterday, end_date=yesterday)
        if turnover_df.empty or 'turnover_rate' not in turnover_df.columns:
            turnover_rate = calculate_turnover_rate(stock, yesterday)
        else:
            turnover_rate = turnover_df['turnover_rate'].iloc[0]

        if 0 < turnover_rate < g.min_turnover_rate:
            return False, f"换手率{turnover_rate:.2f}% < {g.min_turnover_rate}%"

        vol_df = get_price(stock, start_date=day_before_yesterday, end_date=yesterday, fields=['volume'], fq='pre')
        if len(vol_df) < 2:
            return True, "无成交量数据"
        vol_growth = vol_df['volume'].iloc[-1] / vol_df['volume'].iloc[-2]
        if vol_growth < g.min_volume_growth:
            return False, f"成交量增长{vol_growth:.2f} < {g.min_volume_growth}"

        if context.current_dt.time() > datetime.time(9,30):
            try:
                today_vol = get_current_data()[stock].volume
                avg_vol = get_price(stock, end_date=yesterday, count=5, fields=['volume'], fq='pre')['volume'].mean()
                if avg_vol > 0:
                    volume_ratio = today_vol / avg_vol
                    if 0 < volume_ratio < g.min_volume_ratio:
                        return False, f"量比{volume_ratio:.2f} < {g.min_volume_ratio}"
            except:
                pass

        return True, "量能达标"
    except:
        return True, "量能校验异常"

def check_ma_trend(stock, context):
    try:
        ma_df = get_price(stock, end_date=context.previous_date, count=g.ma_period+1, fields=['close'], fq='pre')
        if len(ma_df) < g.ma_period+1:
            return True, "无均线数据"
        ma = ma_df['close'].rolling(window=g.ma_period).mean().iloc[-1]
        if ma_df['close'].iloc[-1] <= ma:
            return True, f"{g.ma_period}日均线空头，仍纳入"
        return True, f"{g.ma_period}日均线多头"
    except:
        return True, "均线校验异常"

def check_limit_up_quality(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=1, fields=['close','high_limit','high'], fq='pre')
        if hist.empty:
            return True, "无价格数据"
        high_limit = hist['high_limit'].iloc[0]
        high_price = hist['high_limit'].iloc[0]
        if high_price < high_limit * 0.995:
            return True, "未触及涨停"
        return True, "封板质量达标"
    except:
        return True, "封板质量异常"

def check_volume_drop(stock, context):
    try:
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False, ""
        cd = get_current_data()[stock]
        yesterday_data = get_price(stock, end_date=trade_days[0], count=1, fields=['volume'], fq='pre')
        if yesterday_data.empty:
            return False, ""
        volume_ratio = cd.volume / yesterday_data['volume'].iloc[0]
        today_change = get_current_change(stock, context)
        if volume_ratio > 1.5 and today_change < -2.0:
            return True, f"放量下跌（量比{volume_ratio:.2f}，跌幅{today_change:.2f}%）"
        return False, ""
    except:
        return False, ""

def market_open(context):
    log.info(f"💵 {context.current_dt.time()} 买入前可用资金：{context.portfolio.available_cash:.2f}")
    total_asset = context.portfolio.total_value
    g.max_stock_num, g.max_buy_per_day = get_dynamic_max_hold(total_asset)

    if not g.only_buy:
        sell_reasons = collect_break_limit_sell_reasons(context)
        for stock in list(context.portfolio.positions.keys()):
            if stock in g.bought_stocks:
                continue
            try:
                cd = get_current_data()[stock]
                hl = cd.high_limit
                op = cd.day_open
                if abs(op - hl) / hl > 0.005:
                    log.info("📤 开盘未涨停卖出: {}".format(stock))
                    sell_reasons.setdefault(stock, '开盘未涨停')
            except:
                continue
        for stock, reason in collect_sell_decision_reasons(context).items():
            sell_reasons.setdefault(stock, reason)
        execute_sell_batch(sell_reasons, context)
    buy_decision(context)
    update_hold_status(context)


def collect_sell_decision_reasons(context):
    sell_reasons = {}
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        sell_reason = get_sell_reason(stock, context)
        if sell_reason:
            sell_reasons[stock] = sell_reason
    return sell_reasons


def sell_decision(context):
    execute_sell_batch(collect_sell_decision_reasons(context), context)

def should_sell(stock, context):
    return bool(get_sell_reason(stock, context))


def get_sell_reason(stock, context):
    try:
        current_price = get_current_data()[stock].last_price
        pos = context.portfolio.positions[stock]
        if pos.avg_cost <= 0:
            return '持仓成本异常'
        profit_ratio = (current_price - pos.avg_cost) / pos.avg_cost * 100

        vdrop, vdrop_reason = check_volume_drop(stock, context)
        if vdrop:
            return vdrop_reason or '放量下跌'

        if profit_ratio <= g.stop_loss_ratio:
            return '触发止损：收益{:.2f}% ≤ {:.2f}%'.format(
                profit_ratio, g.stop_loss_ratio
            )
        if profit_ratio >= g.stop_profit_ratio and stock not in g.has_limit_up:
            return '触发止盈：收益{:.2f}% ≥ {:.2f}%'.format(
                profit_ratio, g.stop_profit_ratio
            )
        if g.hold_days.get(stock,0) >= g.max_hold_days and stock not in g.has_limit_up:
            return '达到最长持有天数：{} 天'.format(
                g.hold_days.get(stock, 0)
            )
        return ''
    except Exception as e:
        log.warn('卖出条件检查异常 {}: {}'.format(stock, str(e)[:50]))
        return '卖出条件检查异常'

def execute_sell_batch(sell_reasons, context):
    """单次合并提醒后再逐只卖出，避免多只股票造成推送风暴。"""
    if not sell_reasons:
        return 0

    # 通知必须发生在首个卖出委托之前。
    push_before_sell_batch(sell_reasons, context)

    sold_count = 0
    for stock, sell_reason in sell_reasons.items():
        if execute_sell(stock, context, sell_reason, send_notification=False):
            sold_count += 1
    return sold_count


# ========== execute_sell ==========
def execute_sell(stock, context, sell_reason='策略卖出信号', send_notification=True):
    # 先撤单，避免重复委托
    try:
        for od in get_open_orders():
            if od.security == stock and od.status == OrderStatus.NOT_FILLED:
                cancel_order(od.order_id)
    except:
        pass
    try:
        current_price = get_current_data()[stock].last_price
        pos = context.portfolio.positions.get(stock)
        if pos is None:
            return False
        avg_cost = pos.avg_cost
        # 卖出当天也算持有，所以用当前持股天数+1
        hold_days = g.hold_days.get(stock, 0) + 1
        profit_ratio = (current_price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
        stock_name = get_security_info(stock).display_name
        sell_time = context.current_dt.strftime('%H:%M:%S')

        # 兼容单只调用；批量卖出时已在 execute_sell_batch 中合并提醒。
        if send_notification:
            push_before_sell_batch({stock: sell_reason}, context)
        order_target(stock, 0)
        # 记录卖出明细
        g.sold_today.append({
            'code': stock,
            'name': stock_name,
            'cost': avg_cost,
            'sell_price': current_price,
            'profit_ratio': profit_ratio,
            'hold_days': hold_days,
            'sell_time': sell_time,
            'reason': sell_reason,
        })
        log.info("📤 卖出成功: {} {} @ {:.3f} 收益:{:.2f}% 持有{}天 | {}".format(stock, stock_name, current_price, profit_ratio, hold_days, sell_reason))
        if stock in g.hold_days:
            del g.hold_days[stock]
        if stock not in g.rebuy_candidates:
            g.rebuy_candidates.append(stock)
        return True
    except Exception as e:
        log.error("❌ 卖出失败{}: {}".format(stock, str(e)[:30]))
        return False
        
def buy_decision(context):
    # ========== 择时闸门 ==========
    status, cap = get_trading_status(context)
    if status == "empty":
        log.info(f"📉 市场评分{g.market_score}，择时空仓")
        return
    g.market_status = status
    g.market_cap = cap
    cash = context.portfolio.available_cash
    hold_num = len(context.portfolio.positions)
    log.info(f"🔍 实盘买入检查：持仓={hold_num} 只 | 资金={cash:.2f}")

    if hold_num >= g.max_stock_num or cash < 1000:
        log.info("⚠️ 持仓已满或资金不足，今日停止买入")
        return

    current_hold_num = len(context.portfolio.positions)
    if g.bought_today_count >= g.max_buy_per_day:
        return
    if current_hold_num >= g.max_stock_num:
        return
    if len(g.rebuy_candidates) == 0:
        return

    available_stocks = [
        s for s in g.rebuy_candidates
        if s not in context.portfolio.positions and s not in g.bought_stocks
    ]
    if len(available_stocks) == 0:
        return

    # ========== 统计变量 ==========
    suspend_count = 0           # 停牌过滤
    double_count = 0            # 一个月翻倍过滤
    open_drop_count = 0         # 开盘急跌过滤
    buy_condition_pass = []     # 通过买入条件的股票
    buy_condition_fail = []     # 未通过买入条件的股票
    
    buy_candidates = []
    log_count = 0
    MAX_LOG = 30
    
    for stock in available_stocks:
        # 获取股票名称
        try:
            stock_name = get_security_info(stock).display_name
        except:
            stock_name = "未知名称"

        # 停牌过滤（开盘涨幅=0% 且 实时涨幅=0%）
        is_suspend = False
        try:
            cd = get_current_data()[stock]
            trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
            if len(trade_days) >= 2:
                yesterday = trade_days[0]
                yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
                
                if not yesterday_data.empty:
                    current_price = cd.last_price
                    open_price = cd.day_open
                    yesterday_close = yesterday_data['close'].iloc[0]
                    
                    open_gain = (open_price - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0
                    current_gain = (current_price - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0
                    
                    if abs(open_gain) < 0.01 and abs(current_gain) < 0.01:
                        is_suspend = True
                        suspend_count += 1
                        log.info(f"❌ 跳过 {stock} {stock_name}：停牌（开盘涨幅{open_gain:.2f}% 且 实时涨幅{current_gain:.2f}%）")
                        continue
        except Exception as e:
            pass
        
        if is_suspend:
            continue

        # 一个月翻倍过滤
        if is_double_in_month(stock, context):
            double_count += 1
            log.info(f"❌ 跳过 {stock} {stock_name}：一个月内翻倍")
            continue

        # 实时高开低走过滤
        is_drop, drop_msg = is_real_time_drop(context, stock)
        if is_drop:
            open_drop_count += 1
            log.info(f"❌ 跳过 {stock} {stock_name}：开盘高开低走 {drop_msg}")
            continue  

        # 买入条件检查
        if log_count < MAX_LOG:
            buy_signal, reason = check_buy_condition(stock, context)
            log_count += 1
        else:
            buy_signal, reason = check_buy_condition_silent(stock, context)
        
        if buy_signal:
            buy_candidates.append((stock, reason))
            buy_condition_pass.append((stock, stock_name, reason))
        else:
            buy_condition_fail.append((stock, stock_name, reason))
            
    # ========== 输出统计表（放在明细后面） ==========
    log.info("")
    log.info("=" * 80)
    log.info("📊 【买入过滤统计表】")
    log.info("=" * 80)
    log.info(f"  总候选股票数：{len(available_stocks)} 只")
    log.info(f"  ├─ 停牌过滤：{suspend_count} 只")
    log.info(f"  ├─ 一个月翻倍过滤：{double_count} 只")
    log.info(f"  ├─ 开盘急跌过滤：{open_drop_count} 只")
    log.info(f"  ├─ 买入条件未通过：{len(buy_condition_fail)} 只")
    log.info(f"  └─ 买入条件通过：{len(buy_condition_pass)} 只")
    log.info("=" * 80)

    if len(buy_candidates) == 0:
        log.info("")
        log.info("⚠️ 过滤后无符合条件的买入标的 ")
        log.info("=" * 80)
        return

    # 计算涨幅与开盘涨幅的差值
    def get_gain_diff(stock, context):
        """计算实时涨幅与开盘涨幅的差值"""
        try:
            cd = get_current_data()[stock]
            yesterday_data = get_price(stock, end_date=context.previous_date, count=1, fields=['close'], fq='pre')
            if yesterday_data.empty:
                return 0
            current_price = cd.last_price
            open_price = cd.day_open
            yesterday_close = yesterday_data['close'].iloc[0]
            if yesterday_close <= 0:
                return 0
            current_gain = (current_price - yesterday_close) / yesterday_close * 100
            open_gain = (open_price - yesterday_close) / yesterday_close * 100
            diff = current_gain - open_gain
            return diff
        except Exception as e:
            return 0
    
    # 按涨幅与开盘涨幅的差值降序排序
    buy_candidates.sort(key=lambda x: get_gain_diff(x[0], context), reverse=True)

    # 打印排序后的详细列表
    log.info("")
    log.info("=" * 80)
    log.info(f"✅ 本次满足买入条件股票总数：{len(buy_candidates)} 只")
    log.info("✅ 排序后股票列表（按盘中拉升幅度降序）：")
    log.info("-" * 80)
    display_count = min(30, len(buy_candidates))
    for i, (stock, reason) in enumerate(buy_candidates[:display_count]):
        try:
            s_name = get_security_info(stock).display_name
        except:
            s_name = "未知"
        change = get_current_change(stock, context)
        diff = get_gain_diff(stock, context)
        log.info(f"  {i+1:>2}. {stock:<12} {s_name:<10} | 涨幅:{change:>6.2f}% | 拉升:{diff:>6.2f}% | {reason}")
    if display_count < len(buy_candidates):
        log.info(f"  ... 剩余 {len(buy_candidates) - display_count} 只未显示")
    log.info("=" * 80)

    remain_buy_num = g.max_stock_num - current_hold_num
    remain_buy_today = g.max_buy_per_day - g.bought_today_count
    final_buy_num = min(remain_buy_num, remain_buy_today)

    # 只合并提醒本轮最终计划买入的股票，不推送完整排行榜。
    push_planned_buy_list(
        context, buy_candidates, final_buy_num, get_gain_diff
    )

    log.info("")
    log.info(f"🛒 本次将买入前 {final_buy_num} 只股票：")
    log.info("-" * 60)
    
    bought_count = 0
    for i, (stock, reason) in enumerate(buy_candidates[:final_buy_num]):
        if execute_buy(stock, context):
            bought_count += 1
            g.bought_stocks.add(stock)
            g.bought_today_count += 1
            try:
                name = get_security_info(stock).display_name
            except:
                name = "未知"
            diff = get_gain_diff(stock, context)
            log.info(f" ✅ 已买入 {i+1:>2}. {stock:<15} {name:<12} | 拉升:{diff:>6.2f}%")
        else:
            log.info(f" ❌ 买入失败 {i+1:>2}. {stock:<15}")
    
    if bought_count < final_buy_num:
        log.info(f"⚠️ 本次实际买入 {bought_count} 只，剩余 {final_buy_num - bought_count} 只因资金或买入失败未成交")
    
    log.info("=" * 80)

def check_buy_condition(stock, context):
    if hasattr(g, 'checked_today') and stock in g.checked_today:
        return g.checked_today[stock]
    try:
        stock_name = get_security_info(stock).display_name
    except:
        stock_name = "未知"
    try:
        cd = get_current_data()[stock]
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            res = (False, "无昨日数据")
        else:
            yesterday = trade_days[0]
            yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
            if yesterday_data.empty:
                res = (False, "无数据/停牌")
            else:
                open_p = cd.day_open
                last_p = cd.last_price
                yes_close = yesterday_data['close'].iloc[0]
                open_ratio = (open_p - yes_close) / yes_close * 100

                t = context.current_dt.time()
                if datetime.time(9,30,00) <= t <= datetime.time(9,30,7):
                    drop_ratio = (last_p - open_p) / open_p * 100
                    # 仅过滤开盘急跌（≤-0.5%），无涨幅区间检查
                    if drop_ratio < -0.5:
                        if g.debug:
                            log.info(f"📝 {stock} {stock_name} 买入过滤：❌ 开盘急跌{drop_ratio:.2f}% < -0.5%")
                        res = (False, f"急跌{drop_ratio:.2f}%")
                    else:
                        # 仅检查量能，无涨幅区间判断
                        vol_ok, vol_msg = check_turnover_volume(stock, context)
                        if not vol_ok:
                            if g.debug:
                                log.info(f"📝 {stock} {stock_name} 买入过滤：❌ {vol_msg}")
                            res = (False, vol_msg)
                        else:
                            ma_ok, ma_msg = check_ma_trend(stock, context)
                            lu_ok, lu_msg = check_limit_up_quality(stock, yesterday)
                            if g.debug:
                                log.info(f"📝 {stock} {stock_name} 买入条件：✅ 通过")
                            res = (True, f"开盘{open_ratio:.2f}%")
                else:
                    # 非9:30:05时段，完全移除涨幅区间过滤
                    # 仅检查量能+实时涨幅过高（可根据需求删除实时涨幅检查）
                    vol_ok, vol_msg = check_turnover_volume(stock, context)
                    if not vol_ok:
                        if g.debug:
                            log.info(f"📝 {stock} {stock_name} 买入过滤：❌ {vol_msg}")
                        res = (False, vol_msg)
                    else:
                        current_change = (last_p - yes_close) / yes_close * 100
                        # 可选：保留实时涨幅过高过滤（如需移除，删除以下3行）
                        if current_change > g.max_open_ratio + 2:
                            if g.debug:
                                log.info(f"📝 {stock} {stock_name} 买入过滤：❌ 实时涨幅{current_change:.2f}% 过高")
                            res = (False, f"实时涨幅{current_change:.2f}%过高")
                        else:
                            ma_ok, ma_msg = check_ma_trend(stock, context)
                            lu_ok, lu_msg = check_limit_up_quality(stock, yesterday)
                            if g.debug:
                                log.info(f"📝 {stock} {stock_name} 买入条件：✅ 通过")
                            res = (True, f"实时{current_change:.2f}%")
        # 缓存检查结果
        if not hasattr(g, 'checked_today'):
            g.checked_today = {}
        g.checked_today[stock] = res
        return res
    except Exception as e:
        log.error(f"📝 {stock} {stock_name} 买入条件检查异常：{str(e)[:50]}")
        res = (False, f"检查异常:{str(e)[:20]}")
        if hasattr(g, 'checked_today'):
            g.checked_today[stock] = res
        return res

# 静默版检查（不输出日志，提升性能）
def check_buy_condition_silent(stock, context):
    if hasattr(g, 'checked_today') and stock in g.checked_today:
        return g.checked_today[stock]
    try:
        cd = get_current_data()[stock]
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            res = (False, "无昨日数据")
        else:
            yesterday = trade_days[0]
            yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
            if yesterday_data.empty:
                res = (False, "无数据/停牌")
            else:
                open_p = cd.day_open
                last_p = cd.last_price
                yes_close = yesterday_data['close'].iloc[0]
                open_ratio = (open_p - yes_close) / yes_close * 100

                t = context.current_dt.time()
                if datetime.time(9,30,00) <= t <= datetime.time(9,30,7):
                    drop_ratio = (last_p - open_p) / open_p * 100
                    # 仅过滤开盘急跌
                    if drop_ratio < -0.5:
                        res = (False, f"急跌{drop_ratio:.2f}%")
                    else:
                        # 仅检查量能
                        vol_ok, vol_msg = check_turnover_volume(stock, context)
                        if not vol_ok:
                            res = (False, vol_msg)
                        else:
                            res = (True, f"开盘{open_ratio:.2f}%")
                else:
                    # 非9:30:05时段，无涨幅过滤
                    vol_ok, vol_msg = check_turnover_volume(stock, context)
                    if not vol_ok:
                        res = (False, vol_msg)
                    else:
                        current_change = (last_p - yes_close) / yes_close * 100
                        # 可选：保留实时涨幅过高过滤（如需移除，删除以下3行）
                        if current_change > g.max_open_ratio + 2:
                            res = (False, f"实时涨幅{current_change:.2f}%过高")
                        else:
                            res = (True, f"实时{current_change:.2f}%")
        if not hasattr(g, 'checked_today'):
            g.checked_today = {}
        g.checked_today[stock] = res
        return res
    except:
        res = (False, "检查异常")
        if hasattr(g, 'checked_today'):
            g.checked_today[stock] = res
        return res

# 辅助函数：获取当前涨幅
def get_current_change(stock, context):
    try:
        current_price = get_current_data()[stock].last_price
        yesterday_data = get_price(stock, end_date=context.previous_date, count=1, fields=['close'], fq='pre')
        if yesterday_data.empty:
            return 0
        yesterday_close = yesterday_data['close'].iloc[0]
        return (current_price - yesterday_close) / yesterday_close * 100
    except:
        return 0

# 买入执行函数
def execute_buy(stock, context):
    try:
        if stock in context.portfolio.positions or stock in g.bought_stocks:
            return False

        current_data = get_current_data()[stock]
        current_price = current_data.last_price
        if current_price <= 0:
            return False

        log.info(f"【买入调试】{stock} 最新价: {current_price}, 时间: {context.current_dt.time()}")

        available_cash = context.portfolio.available_cash

        # ========== 择时仓位缩放 ==========
        cap = getattr(g, "market_cap", 1.0)
        if cap <= 0:
            return False
        available_cash = available_cash * cap
        if available_cash < 1000:
            log.info(f"⏸️ 择时仓位系数{cap:.2f}，可用资金不足1000，跳过买入")
            return False
        current_hold = len(context.portfolio.positions)
        remain_buy = g.max_stock_num - current_hold
        if remain_buy <= 0 or available_cash < 100:
            return False

        target_cash = available_cash / remain_buy
        buy_amount = int(target_cash / current_price / 100) * 100
        if buy_amount < 100:
            return False

        # ===== 限价单 + 动态溢价 =====
        # 与 Bark 买入提醒使用同一计算函数，避免展示与下单不一致。
        premium = get_buy_limit_premium()

        # 限价 = 最新价 * 溢价，但不能超过涨停价
        limit_price = min(current_price * premium, current_data.high_limit)
        
        # 使用限价单
        order_id = order(stock, buy_amount, LimitOrderStyle(limit_price))
        
        if order_id:
            stock_name = get_security_info(stock).display_name
            log.info(f"📥 买入: {stock} {stock_name} | {buy_amount}股 @ 限价{limit_price:.3f} (最新价{current_price:.3f})")
            g.hold_days[stock] = 0
            return True
        return False
    except Exception as e:
        log.error(f"❌ 买入失败{stock}: {str(e)[:30]}")
        return False
# 更新持仓状态
def update_hold_status(context):
    """
    只更新涨停标记，不累加天数（天数在收盘后统一处理）
    """
    for stock in context.portfolio.positions:
        try:
            cd = get_current_data()[stock]
            high = cd.high
            high_limit = cd.high_limit
            if high >= high_limit * 0.995 and stock not in g.has_limit_up:
                g.has_limit_up.add(stock)
                stock_name = get_security_info(stock).display_name
                log.info("✅ 标记涨停: {} {}".format(stock, stock_name))
        except:
            continue

# 收盘后处理
def after_market_close(context):
    log.info("="*50)
    # 获取正确的当天日期
    trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
    if len(trade_days) >= 2:
        today = trade_days[0]
    else:
        today = context.current_dt.date() - datetime.timedelta(days=1)
    
    log.info("收盘总结: {}".format(today))
    
    # ========== 统一更新持股天数 ==========
    # 所有持仓股票天数+1（非当日买入的已经持有过夜）
    for stock in context.portfolio.positions:
        if stock not in g.bought_stocks:  # 不是今日买入
            g.hold_days[stock] = g.hold_days.get(stock, 0) + 1
    
    # 卖出明细
    if len(g.sold_today) > 0:
        log.info(f"📤 今日卖出：{len(g.sold_today)}只")
        for sell in g.sold_today:
            log.info(f"  {sell['code']} {sell['name']} | 成本:{sell['cost']:.3f} | 卖出:{sell['sell_price']:.3f} | 收益:{sell['profit_ratio']:.2f}% | 持有{sell['hold_days']}天 | 时间:{sell['sell_time']}")
    
    # 持仓总结
    hold_stocks = list(context.portfolio.positions.keys())
    log.info(f"📈 最终持仓：{len(hold_stocks)}只")
    for stock in hold_stocks:
        try:
            pos = context.portfolio.positions[stock]
            stock_name = get_security_info(stock).display_name
            profit_ratio = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0
            days = g.hold_days.get(stock, 0)
            flag = "✅" if stock in g.has_limit_up else "❌"
            log.info(f"  {stock} {stock_name} | 成本:{pos.avg_cost:.3f} | 当前:{pos.price:.3f} | 收益:{profit_ratio:.2f}% | 持有{days}天 | 涨停:{flag}")
        except:
            log.info(f"  {stock} | 持仓信息获取失败")
    
    # 资金总结
    total_asset = context.portfolio.total_value
    cash = context.portfolio.available_cash
    market_value = total_asset - cash
    log.info(f"💵 总资产：{total_asset:.2f} | 可用资金：{cash:.2f} | 持仓市值：{market_value:.2f}")
    log.info("="*50)
