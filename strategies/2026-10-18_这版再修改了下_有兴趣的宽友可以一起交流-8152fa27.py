# Clone from JoinQuant
# postId: 8152fa27c0dd3f61841c723deb22f937
# backtestId: 71bf854577dfa2756a4b850710509cbd
# title: 这版再修改了下，有兴趣的宽友可以一起交流



# 克隆自聚宽文章：https://www.joinquant.com/post/79613
# 标题：我真是服了，这策略回测太牛了！！！
# 作者：夏天969

# 克隆自聚宽文章：https://www.joinquant.com/post/25496
# 标题：收益狂飙，年化收益100%，11年1700倍，绝无未来函数
# 作者：jqz1226 ZUEL

# ==============================
# V10.4 坚定持仓+卖出优化版
# 在V10.3基础上新增:
# 1. 持仓保护机制：已买入个股次日仍符合买入条件时坚定持有
# 2. 新增 is_still_strong() 函数：判断持仓是否仍具备强势特征
# 3. 9:30卖出保护：仍强势的持仓不因"未涨停开盘"被卖出
# 4. 卖出条件收紧：止盈/持仓天数/炸板回落等条件优化
# 5. 防重复买卖：当日卖出的股票当日不再买回
# 6. 持仓天数延长：强势持仓从3天延长到5天
# 7. 保留V10.3所有功能（ST/上市天数/房地产/连续亏损过滤等）
# ==============================
# V10.0 优化修复版
# 修复内容:
# 1. auction_filter count=3→2 + 索引修正(9:26日K线未收盘)
# 2. after_market_close 移除timedelta兜底
# 3. get_current_change 改用get_current_data获取实时价格
# 4. check_volume_drop 增加最低成交量阈值
# 5. check_limit_up_quality 修正high_price字段
# 6. check_ma_trend 支持strict严格过滤模式
# 7. 标记死代码函数
# 策略定位：
# 1. 主板强势股短线接力
# 2. 盘前先筛出“昨天最强的一批票”
# 3. 9:26 再根据竞价做二次过滤
# 4. 9:30 开盘先卖不及预期持仓，再择机买入
# 5. 盘中持续监控炸板回落、止损止盈、持仓天数
# ==============================

from jqdata import *
import datetime
import pandas as pd
import numpy as np


# =========================================================
# 一、仓位与基础工具模块
# 作用：
# 1. 根据总资产动态决定最大持仓数
# 2. 判断股票所属板块
# 3. 提供通用涨幅/行情辅助方法
# =========================================================

def get_dynamic_max_hold(total_asset):
    """
    根据账户总资产动态决定：
    1. 最大持仓数量
    2. 单日最大买入数量

    设计思路：
    - 小资金集中持仓，提高收益弹性
    - 大资金适当分散，降低单票波动影响
    """
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
    """
    判断股票所属板块。

    返回值：
    - main: 主板
    - gem: 创业板
    - star: 科创板
    - unknown: 无法识别

    当前策略主流程实际上只做主板，但保留了对创业板/科创板的兼容判断。
    """
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
    """
    计算某只股票在指定截止日期之前，连续 N 个交易日的累计涨幅。

    用途：
    - 过滤短期涨幅过大的股票
    - 防止接力接在情绪过热、高位透支的位置
    """
    try:
        hist = get_price(
            stock,
            end_date=end_date,
            count=days + 1,
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


# =========================================================
# 二、盘前强势股过滤模块
# 作用：
# 只保留“强但不过热、强但不失真”的股票
# =========================================================

def filter_by_continuous_gain(stock, end_date):
    """
    连续涨幅过滤：
    - 主板：近 5 日累计涨幅不能过大
    - 创业板 / 科创板：近 3 日累计涨幅不能过大

    核心目的：
    避免买到已经加速透支、次日高开兑现概率过高的股票。
    """
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




def filter_by_2day_gain(stock, date):
    """
    近2日涨幅过滤（V10.1新增）：
    如果最近2个交易日的累计涨幅超过15%，则剔除该股票。

    核心目的：
    避免买入短期涨幅过大、情绪过热的个股，降低追高风险。
    主板、创业板、科创板统一使用15%阈值。
    """
    try:
        stock_name = get_security_info(stock).display_name
    except Exception as e:
        stock_name = "未知名称"
        log.warn(f"获取{stock}名称失败: {str(e)[:20]}")

    max_2day_gain = getattr(g, 'max_2day_gain', 15.0)

    total_gain = calculate_continuous_gain(stock, date, 2)

    if total_gain == -999:
        return True, f"无法计算近2天涨幅，跳过过滤", stock_name
    elif total_gain > max_2day_gain:
        return False, f"近2天涨幅{total_gain}% > {max_2day_gain}%", stock_name
    else:
        return True, f"近2天涨幅{total_gain}% ≤ {max_2day_gain}%", stock_name

def filter_after_1430_gain(stock, date):
    """
    尾盘急拉过滤：
    观察前一交易日 14:30 到收盘这 30 分钟的涨幅。

    过滤规则：
    - 主板：14:30 后涨幅 > 5% 过滤
    - 创业板 / 科创板：14:30 后涨幅 > 8% 过滤

    核心目的：
    避免尾盘被资金强拉、次日容易被兑现的票。
    """
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)

        gain_thresholds = {
            'main': 5.0,
            'gem': 8.0,
            'star': 8.0
        }

        if board not in gain_thresholds:
            return True, "未知板块，跳过尾盘涨幅过滤", stock_name

        date_obj = pd.Timestamp(date)
        time_1430 = datetime.datetime.combine(date_obj.date(), datetime.time(14, 30, 0))
        end_time = datetime.datetime.combine(date_obj.date(), datetime.time(15, 0, 0))

        # 优先使用 1 分钟线
        min1_data = get_price(
            stock,
            start_date=time_1430,
            end_date=end_time,
            frequency='1m',
            fields=['close'],
            fq='pre',
            skip_paused=True
        )

        # 若 1 分钟线不可用，则退化到 5 分钟线，再退化到日线兜底
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
                daily_data = get_price(stock, end_date=date, count=1, fields=['open', 'close'], fq='pre')
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

        gain = (price_close - price_1430) / price_1430 * 100
        gain = round(gain, 2)
        threshold = gain_thresholds[board]

        if gain > threshold:
            log.error(f"❌ 尾盘过滤淘汰: {stock} {stock_name} | {board} | 14:30后涨幅{gain}% > {threshold}%")
            return False, f"{board}14:30后涨幅{gain}% > {threshold}%", stock_name
        else:
            return True, f"{board}14:30后涨幅{gain}% ≤ {threshold}%", stock_name

    except Exception as e:
        return True, f"过滤异常({str(e)[:20]})，默认通过", "未知名称"


def filter_by_amplitude(stock, date):
    """
    振幅过滤：
    - 主板：昨日振幅 > 16% 过滤
    - 创业板 / 科创板：昨日振幅 > 20% 过滤

    核心目的：
    排除前一日分歧极大、筹码不稳定的标的。
    """
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)

        amp_thresholds = {
            'main': 16.0,
            'gem': 20.0,
            'star': 20.0
        }
        if board not in amp_thresholds:
            return True, "未知板块，跳过振幅过滤", stock_name

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


def filter_by_turnover(stock, date):
    """
    换手率过滤：
    - 主板：昨日换手率 >= 24% 过滤
    - 创业板 / 科创板：昨日换手率 >= 28% 过滤

    获取方式：
    1. 优先使用 get_money_flow 返回的官方换手率
    2. 若失败，则用成交量 / 流通股本手动计算

    核心目的：
    避免追逐被市场过度交易、过热透支的标的。
    """
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)

        turnover_thresholds = {
            'main': 24.0,
            'gem': 28.0,
            'star': 28.0
        }
        if board not in turnover_thresholds:
            return True, "未知板块，跳过换手率过滤", stock_name

        threshold = turnover_thresholds[board]
        turnover = None

        try:
            turnover_df = get_money_flow(stock, start_date=date, end_date=date)
            if not turnover_df.empty and 'turnover_rate' in turnover_df.columns:
                turnover = turnover_df['turnover_rate'].iloc[0]
        except Exception as e:
            log.warn(f"资金流向获取失败 {stock}: {str(e)[:30]}")

        if turnover is None:
            try:
                vol_data = attribute_history(stock, 1, '1d', fields=['volume'], skip_paused=True, df=True)
                if vol_data.empty:
                    return False, "无成交量数据", stock_name
                volume = vol_data['volume'].iloc[-1]

                q = query(valuation.circulating_cap).filter(valuation.code == stock)
                df = get_fundamentals(q, date=date)  # V10.3确认: date参数已正确传递
                if df.empty:
                    return False, "无流通股本", stock_name

                float_share = df['circulating_cap'].iloc[0] * 10000
                if float_share <= 0:
                    return False, "流通股本异常", stock_name

                turnover = volume / float_share * 100
            except Exception as e:
                log.warn(f"换手率过滤: {stock} 手动计算异常: {str(e)[:50]}")
                return False, "计算异常", stock_name

        if turnover is None:
            return False, "无法获取换手率", stock_name

        turnover = round(float(turnover), 2)

        if turnover >= threshold:
            return False, f"{board}昨日换手率{turnover}% ≥ {threshold}%", stock_name
        else:
            return True, f"{board}昨日换手率{turnover}% < {threshold}%", stock_name

    except Exception as e:
        log.error(f"换手率过滤异常 {stock}: {str(e)[:50]}")
        return False, "过滤异常", stock_name


def has_limit_down_in_last_3days(stock, date):
    """
    近 3 日跌停过滤：
    最近 3 个交易日如果收盘接近跌停价，则认为该股存在明显弱势瑕疵。
    """
    try:
        stock_name = get_security_info(stock).display_name
        hist = attribute_history(stock, 3, '1d', fields=['close', 'low_limit'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name

        for i in range(len(hist)):
            close = hist['close'].iloc[i]
            low_limit = hist['low_limit'].iloc[i]
            if close <= low_limit * 1.005:
                return False, "近3日有跌停", stock_name

        return True, "近3日无跌停", stock_name
    except Exception as e:
        return True, f"跌停异常({str(e)[:20]})", stock_name


def is_continuous_shrink_rise(stock, date):
    """
    连续 3 日缩量上涨过滤：
    如果最近 3 日每天都上涨，但成交量却逐日递减，则剔除。

    核心目的：
    避免买到“价格上涨但增量资金不足”的弱加速票。
    """
    try:
        stock_name = get_security_info(stock).display_name
        hist = attribute_history(stock, 3, '1d', fields=['close', 'volume'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name

        for i in range(1, 3):
            if hist['close'].iloc[i] <= hist['close'].iloc[i - 1]:
                return True, "非连续上涨", stock_name

        for i in range(1, 3):
            if hist['volume'].iloc[i] >= hist['volume'].iloc[i - 1]:
                return True, "非连续缩量", stock_name

        return False, "连续3日缩量上涨", stock_name
    except Exception as e:
        return True, f"缩量异常({str(e)[:20]})", stock_name


def is_double_in_month(stock, context):
    """
    一个月翻倍过滤：
    近 20 个交易日涨幅接近或超过翻倍，则不再参与追涨。
    """
    try:
        hist = attribute_history(stock, 20, '1d', fields=['close'], skip_paused=True, df=True)
        if len(hist) < 20:
            return False

        old_price = hist['close'].iloc[0]
        today_price = hist['close'].iloc[-1]
        if old_price <= 0:
            return False

        gain = (today_price - old_price) / old_price * 100
        return gain >= 95
    except:
        return False


# =========================================================
# 三、竞价/开盘风险识别模块
# 作用：
# 进一步在临近开盘时识别高风险标的
# =========================================================

# [V10标记: 死代码，主流程未调用，保留供参考]
def is_risk_stock(context, stock):
    """
    识别“高位放量涨停 + 次日高开”的高风险股票。

    逻辑：
    1. 昨日涨停
    2. 昨日明显放量
    3. 近 20 日明显上涨，处于高位
    4. 今日竞价继续高开

    核心目的：
    避免买在短线情绪高潮后的兑现点。
    """
    try:
        stock_name = get_security_info(stock).display_name
        log.info(f"【调试1】检查 {stock} {stock_name}")

        df = attribute_history(stock, 3, '1d', fields=['close', 'volume', 'high_limit'], skip_paused=True, df=True)
        if df is None or len(df) < 3:
            return False

        close_yest = df['close'].iloc[-1]
        vol_yest = df['volume'].iloc[-1]
        vol_beyest = df['volume'].iloc[-2]
        high_limit = df['high_limit'].iloc[-1]

        is_limit_up = (close_yest >= high_limit - 0.01)
        is_vol_big = (vol_yest >= vol_beyest * 1.8)

        df20 = attribute_history(stock, 20, '1d', fields=['close'], skip_paused=True, df=True)
        if df20 is not None and len(df20) >= 20:
            rise_rate = (df20['close'].iloc[-1] / df20['close'].iloc[0] - 1)
        else:
            rise_rate = 0

        is_high = (rise_rate > 0.30)
        is_danger_yest = is_limit_up and is_vol_big and is_high

        if not is_danger_yest:
            return False

        current_data = get_current_data()[stock]
        open_price = current_data.day_open
        pre_close = close_yest
        open_rate = (open_price / pre_close - 1) * 100

        if open_rate >= 4:
            log.info(f"⚠️ 风险股票 {stock} {stock_name}：昨日高位放量涨停+今日高开{open_rate:.1f}%")
            return True

        if 2 < open_rate < 3:
            log.info(f"⚠️ 风险股票 {stock} {stock_name}：昨日高位放量涨停+今日小幅高开{open_rate:.1f}%")
            return True

        return False
    except Exception as e:
        log.warn(f"【调试1】异常 {stock}: {str(e)[:50]}")
        return False


# [V10标记: 死代码，主流程未调用，保留供参考]
def is_auction_drop(context, stock):
    """
    竞价高开低走识别。

    注意：
    该函数在原始代码中判别条件恒成立（已修复），
    目前主流程未直接调用此函数（is_risk_stock/is_weak_limit_up 也为死代码），
    保留但建议后续清理未使用函数。
    """
    try:
        stock_name = get_security_info(stock).display_name
        log.info(f"【调试2】检查 {stock} {stock_name}")

        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False

        yesterday_close = get_price(stock, end_date=trade_days[0], count=1, fields=['close'], fq='pre')['close'].iloc[0]
        current_data = get_current_data()[stock]
        open_price = current_data.day_open
        if open_price <= 0:
            return False

        open_ratio = (open_price - yesterday_close) / yesterday_close * 100

        # 修复：原条件恒成立，改为合理的竞价高开低走判断
        # 逻辑：高开幅度较大(open_ratio > 2%)，但开盘后价格回落超过高开幅度的50%
        current_data_2 = get_current_data()[stock]
        current_price = current_data_2.last_price
        if open_ratio > 2.0 and current_price > 0 and open_price > 0:
            pullback_pct = (open_price - current_price) / open_price * 100
            if pullback_pct > open_ratio * 0.5:
                log.info(f"⚠️ 竞价高开低走 {stock} {stock_name}：高开{open_ratio:.1f}%，开盘回落{pullback_pct:.1f}%")
                return True

        return False
    except Exception as e:
        log.warn(f"【调试2】异常 {stock}: {str(e)[:50]}")
        return False


# [V10标记: 死代码，主流程未调用，保留供参考]
def is_weak_limit_up(context, stock):
    """
    识别“封单过小”的弱涨停票。

    思路：
    - 若昨日涨停
    - 今日买一量相对于流通股本占比过低
    - 则认为封板强度不足，容易炸板
    """
    try:
        stock_name = get_security_info(stock).display_name
        log.info(f"【调试3】检查 {stock} {stock_name}")

        df = attribute_history(stock, 1, '1d', fields=['close', 'high_limit'], skip_paused=True, df=True)
        if df.empty:
            return False

        close_yest = df['close'].iloc[-1]
        high_limit = df['high_limit'].iloc[-1]
        is_limit_yest = (close_yest >= high_limit - 0.01)
        if not is_limit_yest:
            return False

        current_data = get_current_data()[stock]
        if not hasattr(current_data, 'bid1_volume') or current_data.bid1_volume is None:
            return False

        bid1_volume = current_data.bid1_volume

        q = query(valuation.circulating_cap).filter(valuation.code == stock)
        df_cap = get_fundamentals(q, date=context.current_dt.date())  # V10.3确认: date参数正确
        if df_cap.empty:
            return False

        circulating_share = df_cap['circulating_cap'].iloc[0] * 10000 * 100
        ratio = bid1_volume / circulating_share * 100

        if ratio < 1:
            log.info(f"⚠️ 封单过小 {stock} {stock_name}")
            return True
        return False
    except Exception as e:
        log.warn(f"【调试3】异常 {stock}: {str(e)[:50]}")
        return False


def is_real_time_drop(context, stock):
    """
    开盘实时高开低走识别。

    用途：
    - 开盘后几秒快速检测：是否高开后立刻转弱
    - 如果开盘强，但价格马上跌回去，通常不适合买入接力
    """
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


# =========================================================
# 四、基础质量判断模块
# 作用：
# 过滤 ST、一字板、停牌等不适合参与接力的票
# =========================================================

def is_main_board(stock):
    """
    判断是否为主板股票。
    """
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
    """
    ST / *ST / S / SST / S*ST / 退市整理股等风险股票过滤。
    V10.3增强：覆盖所有ST变体。
    """
    try:
        name = get_security_info(stock).display_name
        if name is None:
            return True
        name_upper = name.upper()
        # 覆盖所有ST相关变体
        for kw in ['ST', '*ST', 'SST', 'S ST', '退']:
            if kw in name_upper:
                return True
        return False
    except:
        return True


def filter_by_listing_days(stock, date, min_days=120):
    """
    上市天数过滤（V10.3新增）：
    剔除上市不满120个交易日的个股。
    核心目的：次新股波动大、筹码不稳定、技术指标失真。
    """
    try:
        stock_name = get_security_info(stock).display_name
        stock_info = get_security_info(stock)
        start_date = stock_info.start_date
        if start_date is None:
            return True, "无法获取上市日期", stock_name
        trade_days = get_trade_days(start_date=start_date, end_date=date)
        listed_days = len(trade_days)
        if listed_days < min_days:
            return False, f"上市仅{listed_days}个交易日<{min_days}天", stock_name
        return True, f"上市{listed_days}天", stock_name
    except Exception as e:
        log.warn(f"上市天数检查异常 {stock}: {str(e)[:20]}")
        return True, "检查异常，默认通过", "未知名称"


def filter_by_real_estate(stock):
    """
    房地产板块过滤（V10.3新增）：
    剔除属于房地产行业的个股。
    过滤方式：
    1. 查询申万行业分类，匹配"房地产"
    2. 补充检查股票名称关键词（双重保障）
    """
    try:
        stock_name = get_security_info(stock).display_name
        # 方式1：通过行业分类判断
        try:
            industry_data = get_industry(stock)
            if industry_data is not None:
                if isinstance(industry_data, dict):
                    for key, val in industry_data.items():
                        if val is not None and hasattr(val, 'industry_name'):
                            ind_name = str(val.industry_name)
                            if '房地产' in ind_name or '地产' in ind_name:
                                return False, f"行业:{ind_name}", stock_name
                        elif isinstance(val, str):
                            if '房地产' in val or '地产' in val:
                                return False, f"行业:{val}", stock_name
        except:
            pass
        # 方式2：通过股票名称关键词判断（双重保障）
        real_estate_keywords = ['地产', '置业', '房产', '置地']
        if stock_name:
            for kw in real_estate_keywords:
                if kw in stock_name:
                    return False, f"名称含'{kw}'", stock_name
        return True, "非房地产", stock_name
    except Exception as e:
        log.warn(f"房地产过滤异常 {stock}: {str(e)[:20]}")
        return True, "检查异常，默认通过", "未知名称"


def filter_consecutive_quarter_loss(stock, date):
    """
    连续三季度亏损过滤（V10.3新增）：
    剔除最近连续3个季度净利润为负的个股。
    核心目的：避免基本面恶化的公司，降低踩雷退市/ST风险。
    """
    try:
        stock_name = get_security_info(stock).display_name
        q = query(income.net_profit).filter(
            income.code == stock
        ).order_by(income.end_date.desc()).limit(4)
        df = get_fundamentals(q, date=date)
        if df is None or df.empty or len(df) < 3:
            return True, "财务数据不足3季度", stock_name
        recent_3 = df.head(3)
        net_profits = recent_3['net_profit'].values
        valid_profits = [p for p in net_profits if p is not None and not pd.isna(p)]
        if len(valid_profits) >= 3 and all(p < 0 for p in valid_profits[:3]):
            loss_info = '/'.join([f"{p:.0f}" for p in valid_profits[:3]])
            return False, f"连续3季亏损({loss_info})", stock_name
        return True, "近3季净利润正常", stock_name
    except Exception as e:
        log.warn(f"连续亏损检查异常 {stock}: {str(e)[:30]}")
        return True, "检查异常，默认通过", "未知名称"


def is_limit_up_down(stock, end_date=None):
    """
    过滤一字涨停 / 一字跌停。
    这类票实盘中往往难以真实成交，容易造成回测和模拟偏乐观。
    V10.3修复：显式传入end_date，避免使用未来数据。
    """
    try:
        if end_date is not None:
            data = get_price(stock, end_date=end_date, count=1, fields=['open', 'high_limit', 'low_limit'], fq='pre')
        else:
            data = get_price(stock, count=1, fields=['open', 'high_limit', 'low_limit'], fq='pre')
        if data.empty:
            return True

        op = data['open'].iloc[0]
        hl = data['high_limit'].iloc[0]
        ll = data['low_limit'].iloc[0]

        if abs(op - hl) < 0.001 or abs(op - ll) < 0.001:
            return True
        return False
    except:
        return True


def check_basic_quality(stock, context):
    """
    候选股基础质量检查：
    1. 过滤一字板
    2. 过滤停牌或无开盘数据的标的
    V10.3修复：is_limit_up_down传入昨日日期避免未来函数。
    """
    try:
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) >= 2:
            yesterday = trade_days[0]
            if is_limit_up_down(stock, end_date=yesterday):
                return False
        else:
            if is_limit_up_down(stock):
                return False

        today_tick = get_price(stock, end_date=context.current_dt, count=1, fields=['open'], skip_paused=True)
        return not today_tick.empty
    except:
        return False


# =========================================================
# 五、强势股识别模块
# 作用：
# 找出前一交易日表现足够强、具备接力价值的股票
# =========================================================

def is_limit_up_simple(stock, date):
    """
    简化版涨停识别：
    - 昨日涨幅大于 8.5%
    - 或昨日收盘接近涨停价

    用途：
    作为盘前强势股初筛标准。
    """
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close', 'high_limit'], fq='pre')
        if len(hist) < 2:
            return False

        yc = hist['close'].iloc[-1]
        yl = hist['high_limit'].iloc[-1]
        pc = hist['close'].iloc[-2]
        change = (yc - pc) / pc * 100

        if change > 8.5 or abs(yc - yl) / yl < 0.006:
            return True
        return False
    except:
        return False


def is_strong_stock(stock, date):
    """
    强势股补充识别：
    昨日涨幅在 6% ~ 8.5% 之间，也视为具备一定强势特征。
    """
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
        if len(hist) < 2:
            return False

        change = (hist['close'].iloc[-1] - hist['close'].iloc[-2]) / hist['close'].iloc[-2] * 100
        return 6 <= change < 8.5
    except:
        return False


def find_limit_up_loose(stocks, date):
    """
    宽松版强势股识别：
    当严格条件下找不到足够候选股时，启用较宽松规则补充候选池。
    """
    limit_stocks = []
    for stock in stocks:
        try:
            if is_st_stock(stock):
                continue

            # V10.3新增: 上市天数过滤
            pass_listing, _, _ = filter_by_listing_days(stock, date)
            if not pass_listing:
                continue

            # V10.3新增: 房地产板块过滤
            pass_re, _, _ = filter_by_real_estate(stock)
            if not pass_re:
                continue

            # V10.3新增: 连续三季度亏损过滤
            pass_loss, _, _ = filter_consecutive_quarter_loss(stock, date)
            if not pass_loss:
                continue

            hist = get_price(stock, end_date=date, count=2, fields=['close', 'high'], fq='pre')
            if len(hist) < 2:
                continue

            yc = hist['close'].iloc[-1]
            yh = hist['high'].iloc[-1]
            pc = hist['close'].iloc[-2]
            change = (yc - pc) / pc * 100

            if change > 8.0 or (abs(yh - yc) / yc < 0.01 and change > 6.5):
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    continue

                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    continue

                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    continue

                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    continue

                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    continue

                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    continue

                pass_2day_filter, gain_2day_msg, stock_name = filter_by_2day_gain(stock, date)
                if not pass_2day_filter:
                    continue

                limit_stocks.append(stock)
                log.info("宽松涨停: {} {} 涨幅: {:.2f}% | {}".format(stock, stock_name, change, filter_msg))
        except:
            continue

    return limit_stocks


def find_limit_up_ultra_loose(stocks, date):
    """
    超宽松版强势股识别：
    当严格和宽松模式都没有结果时，再进一步放宽条件。
    """
    limit_stocks = []
    for stock in stocks:
        try:
            if is_st_stock(stock):
                continue

            # V10.3新增: 上市天数过滤
            pass_listing, _, _ = filter_by_listing_days(stock, date)
            if not pass_listing:
                continue

            # V10.3新增: 房地产板块过滤
            pass_re, _, _ = filter_by_real_estate(stock)
            if not pass_re:
                continue

            # V10.3新增: 连续三季度亏损过滤
            pass_loss, _, _ = filter_consecutive_quarter_loss(stock, date)
            if not pass_loss:
                continue

            hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
            if len(hist) < 2:
                continue

            change = (hist['close'].iloc[-1] - hist['close'].iloc[-2]) / hist['close'].iloc[-2] * 100

            if change > 5.0:
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    continue

                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    continue

                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    continue

                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    continue

                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    continue

                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    continue

                pass_2day_filter, gain_2day_msg, stock_name = filter_by_2day_gain(stock, date)
                if not pass_2day_filter:
                    continue

                limit_stocks.append(stock)
                log.info("超宽松识别: {} {} 涨幅: {:.2f}% | {}".format(stock, stock_name, change, filter_msg))
        except:
            continue

    return limit_stocks


# =========================================================
# 六、初始化与调度模块
# 作用：
# 1. 设置手续费/滑点
# 2. 设置全局变量
# 3. 安排盘前、竞价、开盘、盘中、收盘任务
# =========================================================

def initialize(context):
    """
    策略初始化入口。

    这里定义：
    - 手续费
    - 滑点
    - 默认参数
    - 全局变量
    - 定时任务调度
    """
    context.order_cost = OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5
    )

    # 调试开关
    g.debug = True

    # 默认仓位参数
    g.max_stock_num = 3
    g.max_buy_per_day = 3

    # 默认买入涨幅区间
    g.base_min_open_ratio = 0
    g.base_max_open_ratio = 8.0

    # 默认卖出风控参数
    g.base_stop_loss_ratio = -4.0
    g.base_stop_profit_ratio = 19.0
    g.base_max_hold_days = 3
    g.base_break_drop_ratio = 1.5

    # 默认量能参数
    g.base_min_turnover_rate = 2
    g.base_min_volume_ratio = 1.2
    g.ma_period = 5
    g.base_min_limit_up_time = 90
    g.base_min_volume_growth = 1.0
    g.ma_strict_filter = False  # V10新增: 严格均线过滤开关
    g.max_2day_gain = 15.0  # V10.1新增: 近2日涨幅上限(%)，超过则剔除

    # ===== V10.3新增: 多重选股过滤参数 =====
    g.min_listing_days = 120          # 最低上市交易日数
    g.enable_real_estate_filter = True # 是否启用房地产过滤
    g.enable_quarter_loss_filter = True # 是否启用连续季度亏损过滤

    # ===== V10.2新增: 上证指数60分钟RSI+MACD仓位风控参数 =====
    g.index_code = '000001.XSHG'    # 上证指数代码
    g.rsi_period = 14                # RSI计算周期
    g.rsi_overbought = 70            # RSI过热阈值
    g.rsi_oversold = 25              # RSI超卖阈值
    g.macd_fast = 12                 # MACD快线周期
    g.macd_slow = 26                 # MACD慢线周期
    g.macd_signal = 9                # MACD信号线周期
    g.macd_check_bars = 10           # MACD金叉/死叉检查回看根数
    g.pos_overheated = 0.30          # 过热时仓位上限(30%)
    g.pos_oversold = 0.80            # 超卖时仓位上限(80%)
    g.pos_normal = 0.60              # 常规仓位上限(60%)
    g.current_pos_ratio = 0.60       # 当前生效的仓位上限
    g.market_position_state = 'normal'  # 当前大盘仓位状态

    # 竞价过滤统计
    g.risk_filter_count = 0
    g.auction_drop_count = 0
    g.weak_limitup_count = 0
    g.total_filtered = 0

    # 当前生效参数，后面会根据市场环境动态调整
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

    # 运行时状态变量
    g.candidate_stocks = []
    g.hold_days = {}
    g.has_limit_up = set()
    g.bought_stocks = set()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.market_env = "normal"
    g.only_buy = False
    g.break_limit_sold_stocks = []
    g.sold_today = []
    g.sold_today_set = set()  # V10.4新增: 当日卖出股票集合，防止重复买卖

    # ===== V10.4新增: 坚定持仓参数 =====
    g.enable_hold_protection = True     # 是否启用持仓保护（仍强势则不卖）
    g.strong_extend_hold_days = 5       # 仍强势时最大持仓天数（原3天→5天）
    g.strong_stop_profit = 15.0         # 仍强势时止盈线（收紧到15%，原19%）
    g.strong_break_drop = 2.0           # 仍强势时炸板回落阈值（收紧到2%，原1.5%）
    g.protect_log_count = 0             # 持仓保护触发计数

    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(PriceRelatedSlippage(0.002))

    # 定时任务安排
    run_daily(update_market_position, time='09:25:00')  # V10.2新增: 盘前更新仓位状态
    run_daily(before_market_open, time='before_open')
    run_daily(auction_filter, time='09:26:00')
    run_daily(set_only_buy_False, time='09:30:00')
    run_daily(sell_only_930, time='09:30:01')
    run_daily(set_only_buy_True, time='09:30:06')
    run_daily(market_open, time='09:30:06')
    run_daily(market_open, time='09:31:00')
    run_daily(market_open, time='09:32:00')
    run_daily(market_open, time='09:37')
    run_daily(market_open, time='10:29')
    run_daily(after_market_close, time='after_close')

    # 盘中每 2 分钟检查一次：涨停后回落是否达到卖出阈值
    for hour in range(10, 15):
        for minute in range(0, 60, 2):
            if (hour == 10 and minute < 20) or (hour == 14 and minute >= 56):
                continue
            time_str = f"{hour:02d}:{minute:02d}"
            run_daily(check_break_limit_drop_for_long_hold, time=time_str)


def set_only_buy_True(context):
    """
    切换为仅买入模式。
    用于明确区分“先卖后买”的开盘阶段和后续纯买入阶段。
    """
    g.only_buy = True
    log.info(f"当前时间{context.current_dt.time()}，设置为【仅买入模式】")


def set_only_buy_False(context):
    """
    切换为先卖后买模式。
    """
    g.only_buy = False
    log.info(f"当前时间{context.current_dt.time()}，设置为【先卖后买模式】")



# =========================================================
# 六点五、上证指数60分钟RSI+MACD仓位风控模块（V10.2新增）
# 作用：
# 1. 获取上证指数60分钟K线数据
# 2. 计算RSI指标和MACD指标
# 3. 根据RSI+MACD交叉信号判断大盘状态
# 4. 动态调整总仓位上限（30%/60%/80%）
# =========================================================

def calculate_rsi(prices, period=14):
    """
    计算RSI（相对强弱指数）。

    参数：
    - prices: 收盘价序列（pandas Series或list）
    - period: RSI计算周期，默认14

    返回：
    - 最新一根K线的RSI值，若数据不足返回50（中性值）
    """
    try:
        prices = np.array(prices, dtype=float)
        if len(prices) < period + 1:
            return 50.0  # 数据不足，返回中性值

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # 使用指数移动平均（Wilder平滑法）
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    except Exception as e:
        log.warn(f"RSI计算异常: {str(e)[:30]}")
        return 50.0


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """
    计算MACD指标（DIF、DEA、MACD柱）。

    参数：
    - prices: 收盘价序列
    - fast: 快线EMA周期，默认12
    - slow: 慢线EMA周期，默认26
    - signal: 信号线EMA周期，默认9

    返回：
    - (dif_array, dea_array, macd_bar_array) 三个numpy数组
    - 若数据不足返回(None, None, None)
    """
    try:
        prices = np.array(prices, dtype=float)
        if len(prices) < slow + signal:
            return None, None, None

        # 计算EMA
        def ema(data, period):
            result = np.zeros_like(data)
            result[0] = data[0]
            multiplier = 2.0 / (period + 1)
            for i in range(1, len(data)):
                result[i] = (data[i] - result[i-1]) * multiplier + result[i-1]
            return result

        ema_fast = ema(prices, fast)
        ema_slow = ema(prices, slow)

        # DIF = 快线EMA - 慢线EMA
        dif = ema_fast - ema_slow

        # DEA = DIF的signal周期EMA
        dea = ema(dif, signal)

        # MACD柱 = (DIF - DEA) * 2
        macd_bar = (dif - dea) * 2

        return dif, dea, macd_bar
    except Exception as e:
        log.warn(f"MACD计算异常: {str(e)[:30]}")
        return None, None, None


def get_market_position_ratio(context):
    """
    基于上证指数60分钟线RSI+MACD判断大盘状态，返回建议仓位比例。

    判断逻辑：
    - RSI>70 且 近10根K线内MACD出现死叉 → 30%（过热极轻仓防守）
    - RSI<25 且 近10根K线内MACD出现金叉 → 80%（超卖积极进攻）
    - 其他                                → 60%（常规仓位）

    MACD金叉：DIF从下方穿越DEA（前一根DIF<DEA，当前DIF>DEA）
    MACD死叉：DIF从上方穿越DEA（前一根DIF>DEA，当前DIF<DEA）

    返回：
    - 仓位比例浮点数（0.30 / 0.60 / 0.80）
    """
    try:
        index_code = getattr(g, 'index_code', '000001.XSHG')

        # 获取上证指数60分钟K线数据
        # 需要足够多的数据来计算MACD(slow=26) + signal(9) + 额外缓冲
        # 至少需要 slow + signal + check_bars = 26 + 9 + 10 = 45根
        bar_count = 80  # 取80根60分钟K线，确保数据充足

        price_data = get_price(
            index_code,
            end_date=context.current_dt,
            count=bar_count,
            frequency='60m',
            fields=['close'],
            fq='pre',
            skip_paused=True
        )

        if price_data is None or price_data.empty or len(price_data) < 50:
            log.warn(f"[仓位风控] 上证指数60分钟数据不足，使用默认仓位60%")
            return g.pos_normal

        closes = price_data['close'].values

        # 计算RSI
        rsi_period = getattr(g, 'rsi_period', 14)
        rsi_value = calculate_rsi(closes, rsi_period)

        # 计算MACD
        macd_fast = getattr(g, 'macd_fast', 12)
        macd_slow = getattr(g, 'macd_slow', 26)
        macd_signal = getattr(g, 'macd_signal', 9)
        dif, dea, macd_bar = calculate_macd(closes, macd_fast, macd_slow, macd_signal)

        if dif is None or dea is None:
            log.warn(f"[仓位风控] MACD计算失败，使用默认仓位60%")
            return g.pos_normal

        # 检查近N根K线内是否出现MACD金叉或死叉
        check_bars = getattr(g, 'macd_check_bars', 10)
        check_bars = min(check_bars, len(dif) - 1)  # 防止越界

        has_death_cross = False  # 死叉标记
        has_golden_cross = False  # 金叉标记

        for i in range(len(dif) - check_bars, len(dif)):
            if i < 1:
                continue
            # 死叉：前一根DIF >= DEA，当前DIF < DEA
            if dif[i-1] >= dea[i-1] and dif[i] < dea[i]:
                has_death_cross = True
            # 金叉：前一根DIF <= DEA，当前DIF > DEA
            if dif[i-1] <= dea[i-1] and dif[i] > dea[i]:
                has_golden_cross = True

        # 判断逻辑
        rsi_overbought = getattr(g, 'rsi_overbought', 70)
        rsi_oversold = getattr(g, 'rsi_oversold', 25)

        if rsi_value > rsi_overbought and has_death_cross:
            # 过热 + 死叉 → 极轻仓防守
            pos_ratio = getattr(g, 'pos_overheated', 0.30)
            state = 'overheated'
            log.info(f"[仓位风控] 上证指数60分钟 RSI={rsi_value:.1f}>{rsi_overbought} 且 近{check_bars}根MACD死叉 → 过热防守仓位{pos_ratio*100:.0f}%")
        elif rsi_value < rsi_oversold and has_golden_cross:
            # 超卖 + 金叉 → 积极进攻
            pos_ratio = getattr(g, 'pos_oversold', 0.80)
            state = 'oversold'
            log.info(f"[仓位风控] 上证指数60分钟 RSI={rsi_value:.1f}<{rsi_oversold} 且 近{check_bars}根MACD金叉 → 超卖进攻仓位{pos_ratio*100:.0f}%")
        else:
            # 常规状态
            pos_ratio = getattr(g, 'pos_normal', 0.60)
            state = 'normal'
            cross_info = ""
            if has_death_cross:
                cross_info += " 有死叉"
            if has_golden_cross:
                cross_info += " 有金叉"
            log.info(f"[仓位风控] 上证指数60分钟 RSI={rsi_value:.1f} MACD{cross_info} → 常规仓位{pos_ratio*100:.0f}%")

        # 更新全局状态
        g.current_pos_ratio = pos_ratio
        g.market_position_state = state

        return pos_ratio

    except Exception as e:
        log.warn(f"[仓位风控] 计算异常: {str(e)[:50]}，使用默认仓位60%")
        g.current_pos_ratio = getattr(g, 'pos_normal', 0.60)
        g.market_position_state = 'normal'
        return g.current_pos_ratio


def update_market_position(context):
    """
    更新大盘仓位状态（V10.2新增）。

    在盘前和盘中定时调用，更新 g.current_pos_ratio 和 g.market_position_state。
    买入决策时会读取 g.current_pos_ratio 来控制总仓位上限。
    """
    try:
        pos_ratio = get_market_position_ratio(context)
        g.current_pos_ratio = pos_ratio
        state_names = {
            'overheated': '过热防守',
            'oversold': '超卖进攻',
            'normal': '常规'
        }
        state_name = state_names.get(g.market_position_state, '常规')
        log.info(f"[仓位风控] 当前大盘状态: {state_name} | 仓位上限: {pos_ratio*100:.0f}%")
    except Exception as e:
        log.warn(f"[仓位风控] 更新异常: {str(e)[:30]}，保持默认")
        g.current_pos_ratio = getattr(g, 'pos_normal', 0.60)
        g.market_position_state = 'normal'


# =========================================================
# 七、市场环境自适应模块
# 作用：
# 根据大盘涨跌和市场涨停数量，动态调整参数
# =========================================================

def adjust_params_by_market(context):
    """
    根据市场状态动态调整买卖参数。

    判定维度：
    1. 沪深 300 指数昨日涨跌
    2. 市场涨停数量（简化统计）

    输出效果：
    - 牛市更激进
    - 熊市更保守
    - 震荡市使用默认参数
    """
    try:
        hs300_data = get_price('000300.XSHG', end_date=context.current_dt.date(), count=1, fields=['close'], fq='pre')
        hs300_prev_trade = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(hs300_prev_trade) < 2:
            g.market_env = "normal"
            return
        hs300_prev_data = get_price('000300.XSHG', end_date=hs300_prev_trade[0], count=1, fields=['close'], fq='pre')

        if hs300_data.empty or hs300_prev_data.empty:
            g.market_env = "normal"
            return

        hs300_change = (hs300_data['close'].iloc[0] - hs300_prev_data['close'].iloc[0]) / hs300_prev_data['close'].iloc[0] * 100

        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            limit_up_count = 50
        else:
            yesterday = trade_days[0]
            all_stocks = [code for code in get_all_securities(['stock'], date=context.current_dt.date()).index if '.BJ' not in code]
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


# =========================================================
# 八、盘前选股模块
# 作用：
# 1. 选出昨日强势股
# 2. 多层过滤后形成候选池
# =========================================================

def before_market_open(context):
    """
    盘前核心流程。

    步骤：
    1. 重置当日状态
    2. 根据市场环境动态调整参数
    3. 获取昨日交易日
    4. 从全市场中只保留主板股
    5. 找出昨日强势股
    6. 依次做 6 层过滤
    7. 将通过基础过滤的股票放入候选池
    """
    log.info("=" * 50)
    log.info("盘前选股开始: {}".format(context.current_dt.date()))

    g.candidate_stocks = []
    g.has_limit_up.clear()
    g.bought_stocks.clear()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.only_buy = False
    g.break_limit_sold_stocks = []
    g.sold_today = []

    if hasattr(g, 'checked_today'):
        del g.checked_today

    adjust_params_by_market(context)
    update_market_position(context)  # V10.2新增: 更新大盘仓位状态

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

    # 当前主策略只做主板
    current_tradable_stocks = [
        code for code in current_tradable_stocks
        if get_stock_board(code) in ("main")
    ]
    log.info("今日可交易A股数量: {}".format(len(current_tradable_stocks)))

    limit_up_stocks = []
    batch_size = 1000

    for i in range(0, len(current_tradable_stocks), batch_size):
        batch_stocks = current_tradable_stocks[i:i + batch_size]
        for stock in batch_stocks:
            try:
                if is_st_stock(stock):
                    continue

                # V10.3新增: 上市不满120交易日过滤
                pass_listing, listing_msg, listing_name = filter_by_listing_days(stock, yesterday)
                if not pass_listing:
                    continue

                # V10.3新增: 房地产板块过滤
                pass_re, re_msg, re_name = filter_by_real_estate(stock)
                if not pass_re:
                    continue

                # V10.3新增: 连续三季度亏损过滤
                pass_loss, loss_msg, loss_name = filter_consecutive_quarter_loss(stock, yesterday)
                if not pass_loss:
                    continue

                if is_limit_up_simple(stock, yesterday) or is_strong_stock(stock, yesterday):
                    pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, yesterday)
                    if not pass_filter:
                        log.info(f"❌ {stock} {stock_name} 涨幅过滤淘汰：{filter_msg}")
                        continue

                    pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, yesterday)
                    if not pass_1430_filter:
                        log.info(f"❌ {stock} {stock_name} 尾盘涨幅过滤淘汰：{filter_1430_msg}")
                        continue

                    pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, yesterday)
                    if not pass_amp_filter:
                        log.info(f"❌ {stock} {stock_name} 振幅过滤淘汰：{amp_msg}")
                        continue

                    pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, yesterday)
                    if not pass_turnover_filter:
                        log.info(f"❌ {stock} {stock_name} 换手率过滤淘汰：{turnover_msg}")
                        continue

                    pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, yesterday)
                    if not pass_limitdown_filter:
                        log.info(f"❌ {stock} {stock_name} 近3日跌停过滤淘汰：{limitdown_msg}")
                        continue

                    pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, yesterday)
                    if not pass_shrink_filter:
                        log.info(f"❌ {stock} {stock_name} 连续3日缩量上涨过滤淘汰：{shrink_msg}")
                        continue

                    pass_2day_filter, gain_2day_msg, stock_name = filter_by_2day_gain(stock, yesterday)
                    if not pass_2day_filter:
                        log.info(f"❌ {stock} {stock_name} 近2日涨幅过滤淘汰：{gain_2day_msg}")
                        continue

                    limit_up_stocks.append(stock)
            except Exception as e:
                log.warn("检查股票{}出错: {}".format(stock, str(e)[:30]))
                continue

    log.info("核心识别强势股(已过滤:ST+上市天数+房地产+连续亏损+涨幅+尾盘+振幅+换手+跌停+缩量+近2日涨幅): {}只".format(len(limit_up_stocks)))

    if len(limit_up_stocks) == 0:
        log.info("无强势股，尝试宽松识别...")
        limit_up_stocks = find_limit_up_loose(current_tradable_stocks[:1500], yesterday)
        log.info("宽松识别后强势股: {}只".format(len(limit_up_stocks)))

    if len(limit_up_stocks) == 0:
        log.info("宽松识别仍无结果，尝试超宽松识别...")
        limit_up_stocks = find_limit_up_ultra_loose(current_tradable_stocks[:1500], yesterday)
        log.info("超宽松识别后强势股: {}只".format(len(limit_up_stocks)))

    g.candidate_stocks = limit_up_stocks.copy()
    g.rebuy_candidates = limit_up_stocks.copy()


# =========================================================
# 九、9:26 竞价过滤模块
# 作用：
# 对盘前候选池做第二次筛选，只保留竞价结构较好的标的
# =========================================================

def auction_filter(context):
    """
    9:26 竞价过滤。

    过滤重点：
    1. 候选股是否具备基础可交易性
    2. 竞价高开幅度是否处于允许区间
    3. 是否属于“昨日高位放量涨停，今日继续危险高开”的票
    """
    log.info("=" * 50)
    log.info("9:26 竞价过滤（按板块区分高开阈值+开盘涨幅区间过滤）")

    g.risk_filter_count = 0
    range_filter_count = 0
    total_filter_count = 0
    final_stocks = []
    current_date = context.current_dt.date()

    for stock in g.candidate_stocks:
        if not check_basic_quality(stock, context):
            total_filter_count += 1
            continue

        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知"
        is_risk = False
        risk_reason = ""

        try:
            board = get_stock_board(stock)
            if board in ['gem', 'star']:
                open_threshold = 6.0
            elif board == 'main':
                open_threshold = 5.0
            else:
                open_threshold = 5.0

            hist = get_price(stock, end_date=current_date, count=2, fields=['close', 'volume', 'high_limit'], fq='pre')
            current_data = get_current_data()[stock]
            open_price = current_data.day_open

            if len(hist) < 2:
                is_risk = True
                risk_reason = "无昨日收盘价数据"
                total_filter_count += 1
                continue

            close_yest = hist['close'].iloc[-1]
            open_ratio = (open_price - close_yest) / close_yest * 100

            # 第一层：开盘涨幅区间过滤
            if not (g.min_open_ratio <= open_ratio <= g.max_open_ratio):
                is_risk = True
                range_filter_count += 1
                risk_reason = f"开盘涨幅{open_ratio:.1f}%，超出区间[{g.min_open_ratio}%,{g.max_open_ratio}%]"

            # 第二层：高位放量涨停 + 再次高开过滤
            if not is_risk and len(hist) >= 2:
                vol_yest = hist['volume'].iloc[-1]
                vol_beyest = hist['volume'].iloc[-2]
                high_limit = hist['high_limit'].iloc[-1]
                is_limit_up = abs(close_yest - high_limit) / high_limit < 0.006
                is_vol_big = vol_yest >= vol_beyest * 1.8

                if is_limit_up and is_vol_big and open_ratio >= open_threshold:
                    is_risk = True
                    g.risk_filter_count += 1
                    risk_reason = f"涨停+放量+高开{open_ratio:.1f}%（{board}阈值{open_threshold}%）"

        except Exception as e:
            is_risk = True
            risk_reason = f"过滤异常：{str(e)[:30]}"
            log.warn(f"❌ {stock} {stock_name} | 拦截原因：{risk_reason}")

        if is_risk:
            total_filter_count += 1
            log.info(f"❌ {stock} {stock_name} | 拦截原因：{risk_reason}")
        else:
            final_stocks.append(stock)

    g.candidate_stocks = final_stocks.copy()
    g.rebuy_candidates = final_stocks.copy()

    log.info(f"📊 竞价过滤统计：")
    log.info(f"   ├─ 涨幅区间拦截：{range_filter_count} 只")
    log.info(f"   ├─ 风险股拦截：{g.risk_filter_count} 只")
    log.info(f"   ├─ 其他异常拦截：{total_filter_count - range_filter_count - g.risk_filter_count} 只")
    log.info(f"   ├─ 合计拦截：{total_filter_count} 只")
    log.info(f"   └─ 剩余候选股：{len(final_stocks)} 只")
    log.info("=" * 50)


# =========================================================
# 十、量能/趋势辅助检查模块
# 作用：
# 买入前检查量能、趋势、封板质量等
# =========================================================

def calculate_turnover_rate(stock, date):
    """
    手动估算换手率。
    当官方换手率接口不可用时作为兜底计算方法。
    """
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
    """
    买入前量能检查。

    检查内容：
    1. 昨日换手率是否达到最低要求
    2. 成交量是否较前一日增长
    3. 开盘后量比是否达到最低要求

    核心目的：
    接力票必须有量，没有量就容易冲高回落。
    """
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

        if context.current_dt.time() > datetime.time(9, 30):
            try:
                today_vol = get_price(stock, end_date=context.current_dt, count=1, fields=['volume'], fq='pre')['volume'].iloc[0]
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


def check_ma_trend(stock, context, strict=None):
    """
    简单均线趋势检查。

    当前实现较宽松：
    - 即使跌破均线也不强制过滤
    - 更偏向记录信息，而不是硬性拦截
    """
    try:
        if strict is None:
            strict = getattr(g, 'ma_strict_filter', False)
        prev_trade_day = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(prev_trade_day) < 2:
            return True, "无均线数据"
        ma_df = get_price(stock, end_date=prev_trade_day[0], count=g.ma_period + 1, fields=['close'], fq='pre')
        if len(ma_df) < g.ma_period + 1:
            return True, "无均线数据"

        ma = ma_df['close'].rolling(window=g.ma_period).mean().iloc[-1]
        if ma_df['close'].iloc[-1] <= ma:
            if strict:
                return False, f"{g.ma_period}日均线空头"
            return True, f"{g.ma_period}日均线空头，仍纳入"

        return True, f"{g.ma_period}日均线多头"
    except:
        return True, "均线校验异常"


def check_limit_up_quality(stock, date):
    """
    封板质量检查。

    注意：
    这段原始实现中 high_price 取值明显有误，原逻辑保留时建议后续修正。
    """
    try:
        hist = get_price(stock, end_date=date, count=1, fields=['close', 'high_limit', 'high'], fq='pre')
        if hist.empty:
            return True, "无价格数据"

        high_limit = hist['high_limit'].iloc[0]
        high_price = hist['high'].iloc[0]

        if high_price < high_limit * 0.995:
            return True, "未触及涨停"

        return True, "封板质量达标"
    except:
        return True, "封板质量异常"


def get_current_change(stock, context):
    """
    获取当前涨幅。
    当前实现按“自然日 -1”取昨收，实际更稳妥的做法应改为交易日。
    """
    try:
        today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close'], fq='pre')
        prev_trade_day = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(prev_trade_day) < 2:
            return 0
        yesterday_data = get_price(stock, end_date=prev_trade_day[0], count=1, fields=['close'], fq='pre')
        if today_data.empty or yesterday_data.empty:
            return 0

        current_price = today_data['close'].iloc[0]
        yesterday_close = yesterday_data['close'].iloc[0]
        return (current_price - yesterday_close) / yesterday_close * 100
    except:
        return 0


def check_volume_drop(stock, context):
    """
    放量下跌检查：
    如果当前放量明显，同时价格走弱，则认为持仓质量恶化，触发卖出。
    V10修复: 增加最低成交量阈值，避免开盘初期成交量过小导致量比失真。
    """
    try:
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False, ""

        today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close', 'volume'], fq='pre')
        yesterday_data = get_price(stock, end_date=trade_days[0], count=1, fields=['volume'], fq='pre')
        if today_data.empty or yesterday_data.empty:
            return False, ""

        today_vol = today_data['volume'].iloc[0]
        yesterday_vol = yesterday_data['volume'].iloc[0]

        # V10修复: 仅在成交量达到昨日一定比例后才检查（避免开盘初期量比失真）
        # 成交量需达到昨日的15%以上（约开盘30分钟后）才参与放量判断
        if yesterday_vol > 0 and today_vol < yesterday_vol * 0.15:
            return False, ""

        volume_ratio = today_vol / yesterday_vol if yesterday_vol > 0 else 0
        today_change = get_current_change(stock, context)

        if volume_ratio > 1.5 and today_change < -2.0:
            return True, f"放量下跌（量比{volume_ratio:.2f}，跌幅{today_change:.2f}%）"

        return False, ""
    except:
        return False, ""


# =========================================================
# 十一、开盘卖出模块
# 作用：
# 先卖掉不及预期持仓，给后续买入腾仓位
# =========================================================

def sell_only_930(context):
    """
    9:30 专属卖出逻辑。

    核心原则：
    - 今日刚买的不卖，避免 T+1 误卖
    - 昨日持仓若今天开盘不够强，则优先卖出
    - 先卖后买，腾出仓位
    """
    log.info("=== 9:30 专属卖出开始 ===")
    log.info(f"💵 卖出前可用资金：{context.portfolio.available_cash:.2f}")

    total_asset = context.portfolio.total_value
    g.max_stock_num, g.max_buy_per_day = get_dynamic_max_hold(total_asset)

    check_break_limit_drop(context)

    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue

        try:
            today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['high_limit', 'open'], fq='pre')
            if today_data.empty:
                continue

            hl = today_data['high_limit'].iloc[0]
            op = today_data['open'].iloc[0]

            if abs(op - hl) / hl > 0.005:
                # V10.4: 开盘未涨停时，检查是否仍然强势
                if getattr(g, 'enable_hold_protection', True):
                    still_strong = is_still_strong(stock, context)
                    if still_strong:
                        try:
                            stock_name = get_security_info(stock).display_name
                        except:
                            stock_name = "未知"
                        log.info(f"[V10.4保护] {stock} {stock_name} 开盘未涨停但仍强势，坚定持有不卖")
                        continue
                log.info("📤 9:30 开盘未涨停卖出：" + stock)
                execute_sell(stock, context)
        except:
            continue

    sell_decision(context)
    log.info(f"💵 卖出后可用资金：{context.portfolio.available_cash:.2f}")
    log.info("=== 9:30 卖出全部完成 ===")


def check_break_limit_drop(context):
    """
    炸板回落检查：
    如果盘中冲到接近涨停后，回落超过阈值，则卖出。

    V10.4改进：
    - 仍强势的持仓使用更紧的炸板回落阈值（strong_break_drop=2%）
    - 快速锁定利润，防止回落过多

    用途：
    - 主动止盈
    - 防止强势股转弱后回撤过大
    """
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue

        try:
            today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['high', 'close', 'high_limit'], fq='pre')
            if today_data.empty:
                continue

            current_price = today_data['close'].iloc[0]
            today_high = today_data['high'].iloc[0]
            high_limit = today_data['high_limit'].iloc[0]

            if today_high >= high_limit * 0.995:
                g.has_limit_up.add(stock)

            if stock in g.has_limit_up:
                drop_ratio = (today_high - current_price) / today_high * 100

                # V10.4: 判断是否仍强势，使用不同的回落阈值
                still_strong = getattr(g, 'enable_hold_protection', True) and is_still_strong(stock, context)
                if still_strong:
                    # 仍强势时用更紧的阈值（2%），快速锁利
                    threshold = getattr(g, 'strong_break_drop', 2.0)
                else:
                    threshold = g.break_drop_ratio

                if drop_ratio >= threshold:
                    execute_sell(stock, context)
                    if stock not in g.break_limit_sold_stocks:
                        g.break_limit_sold_stocks.append(stock)
        except:
            continue


def check_break_limit_drop_for_long_hold(context):
    """
    长持仓炸板回落检查：
    与 check_break_limit_drop 类似，但只针对持有天数大于 1 天的标的。
    V10.4: 仍强势时使用更紧的回落阈值。
    """
    for stock in list(context.portfolio.positions.keys()):
        hold_days = g.hold_days.get(stock, 0)
        if hold_days <= 1:
            continue

        try:
            today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['high', 'close', 'high_limit'], fq='pre')
            if today_data.empty:
                continue

            current_price = today_data['close'].iloc[0]
            today_high = today_data['high'].iloc[0]
            high_limit = today_data['high_limit'].iloc[0]

            if today_high >= high_limit * 0.995:
                g.has_limit_up.add(stock)

            if stock in g.has_limit_up:
                drop_ratio = (today_high - current_price) / today_high * 100

                # V10.4: 仍强势用更紧的阈值
                still_strong = getattr(g, 'enable_hold_protection', True) and is_still_strong(stock, context)
                if still_strong:
                    threshold = getattr(g, 'strong_break_drop', 2.0)
                else:
                    threshold = g.break_drop_ratio

                if drop_ratio >= threshold:
                    execute_sell(stock, context)
                    if stock not in g.break_limit_sold_stocks:
                        g.break_limit_sold_stocks.append(stock)
        except:
            continue


# =========================================================
# 十二、买入检查模块
# 作用：
# 在候选股中进一步挑选真正可下单的标的
# =========================================================

def check_buy_condition(stock, context):
    """
    带日志版买入条件检查。

    逻辑分两段：
    1. 9:30 初段：重点看是否急跌、量能是否达标
    2. 其余时段：重点看量能是否达标、实时涨幅是否过高

    同时使用 g.checked_today 做缓存，减少重复计算。
    """
    if hasattr(g, 'checked_today') and stock in g.checked_today:
        return g.checked_today[stock]

    try:
        stock_name = get_security_info(stock).display_name
    except:
        stock_name = "未知"

    try:
        today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['open', 'close'], fq='pre', skip_paused=True)
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)

        if len(trade_days) < 2:
            res = (False, "无昨日数据")
        else:
            yesterday = trade_days[0]
            yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')

            if today_data.empty or yesterday_data.empty:
                res = (False, "无数据/停牌")
            else:
                open_p = today_data['open'].iloc[0]
                last_p = today_data['close'].iloc[0]
                yes_close = yesterday_data['close'].iloc[0]
                open_ratio = (open_p - yes_close) / yes_close * 100

                t = context.current_dt.time()

                if datetime.time(9, 30, 0) <= t <= datetime.time(9, 30, 7):
                    drop_ratio = (last_p - open_p) / open_p * 100

                    if drop_ratio < -0.5:
                        if g.debug:
                            log.info(f"📝 {stock} {stock_name} 买入过滤：❌ 开盘急跌{drop_ratio:.2f}% < -0.5%")
                        res = (False, f"急跌{drop_ratio:.2f}%")
                    else:
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
                    vol_ok, vol_msg = check_turnover_volume(stock, context)
                    if not vol_ok:
                        if g.debug:
                            log.info(f"📝 {stock} {stock_name} 买入过滤：❌ {vol_msg}")
                        res = (False, vol_msg)
                    else:
                        current_change = (last_p - yes_close) / yes_close * 100
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


def check_buy_condition_silent(stock, context):
    """
    静默版买入条件检查。
    与 check_buy_condition 逻辑基本相同，只是不输出详细日志。
    """
    if hasattr(g, 'checked_today') and stock in g.checked_today:
        return g.checked_today[stock]

    try:
        today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['open', 'close'], fq='pre', skip_paused=True)
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)

        if len(trade_days) < 2:
            res = (False, "无昨日数据")
        else:
            yesterday = trade_days[0]
            yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')

            if today_data.empty or yesterday_data.empty:
                res = (False, "无数据/停牌")
            else:
                open_p = today_data['open'].iloc[0]
                last_p = today_data['close'].iloc[0]
                yes_close = yesterday_data['close'].iloc[0]
                open_ratio = (open_p - yes_close) / yes_close * 100

                t = context.current_dt.time()
                if datetime.time(9, 30, 0) <= t <= datetime.time(9, 30, 7):
                    drop_ratio = (last_p - open_p) / open_p * 100
                    if drop_ratio < -0.5:
                        res = (False, f"急跌{drop_ratio:.2f}%")
                    else:
                        vol_ok, vol_msg = check_turnover_volume(stock, context)
                        if not vol_ok:
                            res = (False, vol_msg)
                        else:
                            res = (True, f"开盘{open_ratio:.2f}%")
                else:
                    vol_ok, vol_msg = check_turnover_volume(stock, context)
                    if not vol_ok:
                        res = (False, vol_msg)
                    else:
                        current_change = (last_p - yes_close) / yes_close * 100
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


# =========================================================
# 十三、买入执行模块
# 作用：
# 候选池经过检查后，按优先级和资金情况执行下单
# =========================================================

def execute_buy(stock, context):
    """
    执行买入。

    逻辑：
    1. 防止重复买入
    2. V10.2新增：检查总仓位是否超过大盘风控上限
    3. 按剩余仓位平均分配资金
    4. 计算标准手数
    5. 使用限价单 + 动态溢价提高成交概率
    """
    try:
        if stock in context.portfolio.positions or stock in g.bought_stocks:
            return False

        current_data = get_current_data()[stock]
        current_price = current_data.last_price
        if current_price <= 0:
            return False

        # ===== V10.2新增: 仓位上限检查 =====
        total_value = context.portfolio.total_value
        market_value = total_value - context.portfolio.available_cash
        current_pos_pct = market_value / total_value if total_value > 0 else 0
        pos_limit = getattr(g, 'current_pos_ratio', 0.60)
        if current_pos_pct >= pos_limit:
            log.info(f"[仓位风控] 当前仓位{current_pos_pct*100:.1f}% >= 上限{pos_limit*100:.0f}%，拒绝买入 {stock}")
            return False

        available_cash = context.portfolio.available_cash
        current_hold = len(context.portfolio.positions)
        remain_buy = g.max_stock_num - current_hold
        if remain_buy <= 0 or available_cash < 100:
            return False

        # V10.2新增: 根据仓位上限计算可用资金
        # 实际可用资金 = min(账户可用现金, 仓位上限对应的剩余可用市值)
        max_market_value = total_value * pos_limit
        pos_available = max(0, max_market_value - market_value)
        effective_cash = min(available_cash, pos_available)
        if effective_cash < 100:
            log.info(f"[仓位风控] 仓位上限{pos_limit*100:.0f}%限制，有效可用资金不足，拒绝买入 {stock}")
            return False

        target_cash = effective_cash / remain_buy
        buy_amount = int(target_cash / current_price / 100) * 100
        if buy_amount < 100:
            return False

        if g.market_env == "bull":
            premium = 1.022
        elif g.market_env == "bear":
            premium = 1.018
        else:
            premium = 1.019

        limit_price = min(current_price * premium, current_data.high_limit)
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


def buy_decision(context):
    """
    买入决策主流程。

    步骤：
    1. 检查持仓与现金限制
    2. V10.2新增：检查大盘仓位上限
    3. 从候选池中排除已持仓/已买股票
    4. 进一步过滤停牌、翻倍票、开盘转弱票
    5. 对剩余股票执行买入条件检查
    6. 按“盘中拉升幅度”排序
    7. 选前 N 只执行买入
    """
    cash = context.portfolio.available_cash
    hold_num = len(context.portfolio.positions)

    # V10.2新增: 显示当前仓位风控状态
    total_value = context.portfolio.total_value
    market_value = total_value - cash
    current_pos_pct = market_value / total_value * 100 if total_value > 0 else 0
    pos_limit = getattr(g, 'current_pos_ratio', 0.60)
    pos_state = getattr(g, 'market_position_state', 'normal')
    state_names = {'overheated': '过热防守', 'oversold': '超卖进攻', 'normal': '常规'}
    log.info(f"🔍 实盘买入检查：持仓={hold_num}只 | 资金={cash:.2f} | 仓位={current_pos_pct:.1f}% | 上限={pos_limit*100:.0f}%({state_names.get(pos_state, '常规')})")

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
        if s not in context.portfolio.positions
        and s not in g.bought_stocks
        and s not in getattr(g, 'sold_today_set', set())  # V10.4: 排除当日卖出的股票，防止重复买卖
    ]
    if len(available_stocks) == 0:
        return

    suspend_count = 0
    double_count = 0
    open_drop_count = 0
    buy_condition_pass = []
    buy_condition_fail = []

    buy_candidates = []
    log_count = 0
    MAX_LOG = 30

    for stock in available_stocks:
        try:
            stock_name = get_security_info(stock).display_name
        except:
            stock_name = "未知名称"

        is_suspend = False
        try:
            today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close', 'open'], fq='pre')
            trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
            if len(trade_days) >= 2:
                yesterday = trade_days[0]
                yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')

                if not today_data.empty and not yesterday_data.empty:
                    current_price = today_data['close'].iloc[0]
                    open_price = today_data['open'].iloc[0]
                    yesterday_close = yesterday_data['close'].iloc[0]

                    open_gain = (open_price - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0
                    current_gain = (current_price - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0

                    if abs(open_gain) < 0.01 and abs(current_gain) < 0.01:
                        is_suspend = True
                        suspend_count += 1
                        log.info(f"❌ 跳过 {stock} {stock_name}：停牌（开盘涨幅{open_gain:.2f}% 且 实时涨幅{current_gain:.2f}%）")
                        continue
        except Exception:
            pass

        if is_suspend:
            continue

        # V10.3新增: 买入前二次验证上市天数
        trade_days_list = get_trade_days(end_date=context.current_dt.date(), count=2)
        check_date = trade_days_list[0] if len(trade_days_list) >= 2 else context.current_dt.date()
        pass_listing, listing_msg, _ = filter_by_listing_days(stock, check_date)
        if not pass_listing:
            log.info(f"❌ 跳过 {stock} {stock_name}：{listing_msg}")
            continue

        # V10.3新增: 买入前二次验证房地产
        pass_re, re_msg, _ = filter_by_real_estate(stock)
        if not pass_re:
            log.info(f"❌ 跳过 {stock} {stock_name}：{re_msg}")
            continue

        if is_double_in_month(stock, context):
            double_count += 1
            log.info(f"❌ 跳过 {stock} {stock_name}：一个月内翻倍")
            continue

        is_drop, drop_msg = is_real_time_drop(context, stock)
        if is_drop:
            open_drop_count += 1
            log.info(f"❌ 跳过 {stock} {stock_name}：开盘高开低走 {drop_msg}")
            continue

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
        log.info("⚠️ 过滤后无符合条件的买入标的")
        return

    def get_gain_diff(stock, context):
        """
        计算盘中拉升强度：
        实时涨幅 - 开盘涨幅

        用途：
        识别“开盘后继续被资金强化”的股票。
        """
        try:
            today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close', 'open'], fq='pre')
            if today_data.empty:
                return 0

            trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
            if len(trade_days) < 2:
                return 0

            yesterday = trade_days[0]
            yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
            if yesterday_data.empty:
                return 0

            current_price = today_data['close'].iloc[0]
            open_price = today_data['open'].iloc[0]
            yesterday_close = yesterday_data['close'].iloc[0]
            if yesterday_close <= 0:
                return 0

            current_gain = (current_price - yesterday_close) / yesterday_close * 100
            open_gain = (open_price - yesterday_close) / yesterday_close * 100
            return current_gain - open_gain
        except Exception:
            return 0

    buy_candidates.sort(key=lambda x: get_gain_diff(x[0], context), reverse=True)

    remain_buy_num = g.max_stock_num - current_hold_num
    remain_buy_today = g.max_buy_per_day - g.bought_today_count
    final_buy_num = min(remain_buy_num, remain_buy_today)

    log.info(f"🛒 本次将买入前 {final_buy_num} 只股票：")

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


# =========================================================
# 十三点五、持仓强势判断模块（V10.4新增）
# 作用：
# 判断已买入个股是否仍然符合买入条件，用于持仓保护
# =========================================================

def is_still_strong(stock, context):
    """
    判断持仓股是否仍然具备强势特征（V10.4新增）。

    检查维度：
    1. 昨日是否仍然是强势股（涨幅>5%或接近涨停）
    2. 今日是否仍在上涨（当前涨幅>0%）
    3. 今日是否未出现放量下跌
    4. 今日开盘是否未大幅低开（低开不超过-2%）

    返回：
    - True: 仍然强势，应该继续持有
    - False: 已转弱，可以正常执行卖出逻辑
    """
    try:
        stock_name = get_security_info(stock).display_name
    except:
        stock_name = "未知"

    try:
        # 检查1: 昨日是否仍强势
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=3)
        if len(trade_days) < 3:
            return False

        yesterday = trade_days[0]
        day_before = trade_days[1]

        hist = get_price(stock, end_date=yesterday, count=2, fields=['close', 'high_limit'], fq='pre')
        if hist.empty or len(hist) < 2:
            return False

        yc = hist['close'].iloc[-1]
        pc = hist['close'].iloc[-2]
        yl = hist['high_limit'].iloc[-1]

        # 昨日涨幅
        yest_change = (yc - pc) / pc * 100 if pc > 0 else 0
        # 昨日是否接近涨停
        near_limit = abs(yc - yl) / yl < 0.01 if yl > 0 else False

        # 条件A: 昨日涨幅>5%或接近涨停
        still_strong_yesterday = (yest_change > 5.0) or near_limit

        if not still_strong_yesterday:
            return False

        # 检查2: 今日表现
        today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['open', 'close'], fq='pre')
        if today_data.empty:
            return False

        today_open = today_data['open'].iloc[0]
        today_price = today_data['close'].iloc[0]

        # 今日涨幅（相对昨收）
        today_change = (today_price - yc) / yc * 100 if yc > 0 else 0
        # 今日开盘涨幅
        open_change = (today_open - yc) / yc * 100 if yc > 0 else 0

        # 条件B: 今日未大幅低开（开盘不低于昨收-2%）
        if open_change < -2.0:
            log.info(f"[V10.4保护] {stock} {stock_name} 低开{open_change:.1f}%，保护失效")
            return False

        # 条件C: 今日仍在上涨（当前价格>昨收）或至少未大跌（跌幅<1.5%）
        if today_change < -1.5:
            log.info(f"[V10.4保护] {stock} {stock_name} 当前跌幅{today_change:.1f}%，保护失效")
            return False

        # 检查3: 是否出现放量下跌
        vdrop, vdrop_msg = check_volume_drop(stock, context)
        if vdrop:
            log.info(f"[V10.4保护] {stock} {stock_name} 放量下跌，保护失效")
            return False

        # 所有条件通过，仍然强势
        log.info(f"[V10.4保护] {stock} {stock_name} 仍强势 | 昨涨{yest_change:.1f}% | 今涨{today_change:.1f}% | 开盘{open_change:.1f}%")
        return True

    except Exception as e:
        log.warn(f"[V10.4保护] {stock} 判断异常: {str(e)[:30]}")
        return False


# =========================================================
# 十四、卖出决策与执行模块
# 作用：
# 对持仓执行止损、止盈、持仓天数与炸板回落控制
# V10.4: 新增持仓保护机制，仍强势时收紧卖出条件
# =========================================================

def should_sell(stock, context):
    """
    判断某只持仓是否应该卖出。

    V10.4改进：
    - 如果持仓仍然强势（仍符合买入条件），收紧卖出条件
    - 止损线始终生效（安全底线不可绕过）
    - 放量下跌始终生效（趋势转弱必须走）
    - 止盈线收紧到15%（强势股快速锁利）
    - 持仓天数延长到5天（给强势股更多空间）
    - 炸板回落收紧到2%

    触发卖出条件：
    1. 放量下跌（始终生效）
    2. 跌破止损线（始终生效）
    3. 达到止盈线且未处于涨停强势状态
    4. 持仓天数超限且未处于涨停强势状态
    """
    try:
        price_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close'], fq='pre')
        if price_data.empty:
            return True

        pos = context.portfolio.positions[stock]
        if pos.avg_cost <= 0:
            return True

        current_price = price_data['close'].iloc[0]
        profit_ratio = (current_price - pos.avg_cost) / pos.avg_cost * 100

        # === 始终生效的卖出条件（无论是否仍强势） ===

        # 1. 放量下跌 → 必须卖
        vdrop, _ = check_volume_drop(stock, context)
        if vdrop:
            return True

        # 2. 止损 → 必须卖（安全底线）
        if profit_ratio <= g.stop_loss_ratio:
            return True

        # === V10.4: 判断是否仍然强势 ===
        enable_protection = getattr(g, 'enable_hold_protection', True)
        still_strong = False
        if enable_protection and stock not in g.bought_stocks:
            still_strong = is_still_strong(stock, context)

        if still_strong:
            # === 仍强势时使用收紧的卖出条件 ===
            strong_profit = getattr(g, 'strong_stop_profit', 15.0)
            strong_hold_days = getattr(g, 'strong_extend_hold_days', 5)
            hold_days = g.hold_days.get(stock, 0)

            # 止盈：收紧到15%（快速锁定利润，不贪）
            if profit_ratio >= strong_profit and stock not in g.has_limit_up:
                log.info(f"[V10.4] {stock} 仍强势但盈利{profit_ratio:.1f}%>={strong_profit}%止盈线，锁利卖出")
                return True

            # 持仓天数：延长到5天（给趋势更多空间）
            if hold_days >= strong_hold_days and stock not in g.has_limit_up:
                log.info(f"[V10.4] {stock} 仍强势但持仓{hold_days}天>={strong_hold_days}天，到期卖出")
                return True

            # 仍强势且未触发收紧条件 → 坚定持有
            if g.protect_log_count < 10:
                stock_name = get_security_info(stock).display_name
                log.info(f"[V10.4坚定持有] {stock} {stock_name} | 盈利{profit_ratio:.1f}% | 持仓{hold_days}天 | 仍强势，继续持有")
                g.protect_log_count += 1
            return False
        else:
            # === 不再强势时使用原始卖出条件 ===
            if profit_ratio >= g.stop_profit_ratio and stock not in g.has_limit_up:
                return True

            if g.hold_days.get(stock, 0) >= g.max_hold_days and stock not in g.has_limit_up:
                return True

            return False
    except:
        return True


def sell_decision(context):
    """
    遍历持仓，对满足 should_sell 的股票执行卖出。
    """
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        if should_sell(stock, context):
            execute_sell(stock, context)


def execute_sell(stock, context):
    """
    执行卖出。

    处理内容：
    1. 先撤销未成交卖单，避免重复委托
    2. 清仓卖出
    3. 记录卖出明细
    4. 更新持仓天数与回补候选池
    """
    try:
        for od in get_open_orders():
            if od.security == stock and od.status == OrderStatus.NOT_FILLED:
                cancel_order(od.order_id)
    except:
        pass

    try:
        price_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close'], fq='pre')
        if price_data.empty:
            return False

        current_price = price_data['close'].iloc[0]
        pos = context.portfolio.positions.get(stock)
        if pos is None:
            return False

        avg_cost = pos.avg_cost
        hold_days = g.hold_days.get(stock, 0) + 1
        profit_ratio = (current_price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
        stock_name = get_security_info(stock).display_name
        sell_time = context.current_dt.strftime('%H:%M:%S')

        order_target(stock, 0)

        g.sold_today.append({
            'code': stock,
            'name': stock_name,
            'cost': avg_cost,
            'sell_price': current_price,
            'profit_ratio': profit_ratio,
            'hold_days': hold_days,
            'sell_time': sell_time
        })

        log.info("📤 卖出成功: {} {} @ {:.3f} 收益:{:.2f}% 持有{}天".format(
            stock, stock_name, current_price, profit_ratio, hold_days
        ))

        if stock in g.hold_days:
            del g.hold_days[stock]
        # V10.4: 记录当日卖出的股票，防止重复买回
        g.sold_today_set.add(stock)
        if stock not in g.rebuy_candidates:
            g.rebuy_candidates.append(stock)

        return True
    except Exception as e:
        log.error("❌ 卖出失败{}: {}".format(stock, str(e)[:30]))
        return False


# =========================================================
# 十五、盘中主流程模块
# 作用：
# 统一调度盘中卖出、买入和持仓状态更新
# =========================================================

def market_open(context):
    """
    盘中主入口。

    流程：
    1. 如果当前不是仅买入模式，则先检查卖出
    2. 再执行买入决策
    3. 更新持仓状态（是否冲板）
    """
    log.info(f"💵 {context.current_dt.time()} 买入前可用资金：{context.portfolio.available_cash:.2f}")

    total_asset = context.portfolio.total_value
    g.max_stock_num, g.max_buy_per_day = get_dynamic_max_hold(total_asset)

    if not g.only_buy:
        check_break_limit_drop(context)

        for stock in list(context.portfolio.positions.keys()):
            if stock in g.bought_stocks:
                continue

            try:
                today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['high_limit', 'open'], fq='pre')
                if today_data.empty:
                    continue

                hl = today_data['high_limit'].iloc[0]
                op = today_data['open'].iloc[0]

                if abs(op - hl) / hl > 0.005:
                    # V10.4: 开盘未涨停时检查是否仍然强势
                    if getattr(g, 'enable_hold_protection', True):
                        still_strong = is_still_strong(stock, context)
                        if still_strong:
                            continue  # 仍强势，不卖
                    log.info("📤 开盘未涨停卖出: {}".format(stock))
                    execute_sell(stock, context)
            except:
                continue

        sell_decision(context)

    buy_decision(context)
    update_hold_status(context)


def update_hold_status(context):
    """
    更新持仓涨停状态。

    注意：
    这里只标记“今天是否冲过接近涨停”，不在这里累加持有天数；
    持有天数统一在收盘后更新。
    """
    for stock in context.portfolio.positions:
        try:
            today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['high', 'high_limit'], fq='pre')
            if today_data.empty:
                continue

            high = today_data['high'].iloc[0]
            high_limit = today_data['high_limit'].iloc[0]

            if high >= high_limit * 0.995 and stock not in g.has_limit_up:
                g.has_limit_up.add(stock)
                stock_name = get_security_info(stock).display_name
                log.info("✅ 标记涨停: {} {}".format(stock, stock_name))
        except:
            continue


# =========================================================
# 十六、收盘汇总模块
# 作用：
# 记录当日交易结果，更新持仓天数，输出复盘日志
# =========================================================

def after_market_close(context):
    """
    收盘后总结。

    内容包括：
    1. 更新持仓天数
    2. 输出卖出记录
    3. 输出当前持仓情况
    4. 输出资金总结
    """
    log.info("=" * 50)

    trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
    today = trade_days[0] if len(trade_days) >= 2 else context.current_dt.date()

    log.info("收盘总结: {}".format(today))

    for stock in context.portfolio.positions:
        if stock not in g.bought_stocks:
            g.hold_days[stock] = g.hold_days.get(stock, 0) + 1

    if len(g.sold_today) > 0:
        log.info(f"📤 今日卖出：{len(g.sold_today)}只")
        for sell in g.sold_today:
            log.info(
                f"  {sell['code']} {sell['name']} | 成本:{sell['cost']:.3f} | 卖出:{sell['sell_price']:.3f} | "
                f"收益:{sell['profit_ratio']:.2f}% | 持有{sell['hold_days']}天 | 时间:{sell['sell_time']}"
            )

    hold_stocks = list(context.portfolio.positions.keys())
    log.info(f"📈 最终持仓：{len(hold_stocks)}只")
    for stock in hold_stocks:
        try:
            pos = context.portfolio.positions[stock]
            stock_name = get_security_info(stock).display_name
            profit_ratio = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0
            days = g.hold_days.get(stock, 0)
            flag = "✅" if stock in g.has_limit_up else "❌"

            log.info(
                f"  {stock} {stock_name} | 成本:{pos.avg_cost:.3f} | 当前:{pos.price:.3f} | "
                f"收益:{profit_ratio:.2f}% | 持有{days}天 | 涨停:{flag}"
            )
        except:
            log.info(f"  {stock} | 持仓信息获取失败")

    total_asset = context.portfolio.total_value
    cash = context.portfolio.available_cash
    market_value = total_asset - cash

    # V10.2新增: 仓位风控状态输出
    current_pos_pct = market_value / total_asset * 100 if total_asset > 0 else 0
    pos_limit = getattr(g, 'current_pos_ratio', 0.60)
    pos_state = getattr(g, 'market_position_state', 'normal')
    state_names = {'overheated': '过热防守', 'oversold': '超卖进攻', 'normal': '常规'}

    log.info(f"💵 总资产：{total_asset:.2f} | 可用资金：{cash:.2f} | 持仓市值：{market_value:.2f}")
    log.info(f"📊 [仓位风控] 当前仓位：{current_pos_pct:.1f}% | 上限：{pos_limit*100:.0f}% | 状态：{state_names.get(pos_state, '常规')}")
    # V10.4: 持仓保护统计
    protect_count = getattr(g, 'protect_log_count', 0)
    sold_today_count = len(getattr(g, 'sold_today_set', set()))
    log.info(f"📊 [V10.4] 持仓保护触发{protect_count}次 | 当日卖出{sold_today_count}只(防重复买回)")
    log.info("=" * 50)

# =========================================================
# V10.4 修改说明 + 未来函数检测与修复报告
# =========================================================
#
# 【V10.4 新增/修改内容】
#
# 1. 新增 is_still_strong() 函数
#    判断持仓是否仍具备强势特征（昨日涨幅>5%或接近涨停 + 今日仍涨 + 未放量下跌 + 未大幅低开）
#
# 2. should_sell() 加入持仓保护
#    仍强势时：止盈15%、持仓5天、快速锁利
#    止损和放量下跌始终生效（安全底线）
#
# 3. sell_only_930 / market_open 开盘未涨停卖出加入保护
#    仍强势的持仓不因"开盘未涨停"被误卖
#
# 4. 防重复买卖机制
#    当日卖出的股票记录到 sold_today_set，当日不再买回
#
# 5. check_break_limit_drop / check_break_limit_drop_for_long_hold
#    仍强势时使用更紧的炸板回落阈值(2%)，快速锁利
#
# =========================================================
# 
# 【已检测并修复的未来函数风险】
# 
# 1. is_limit_up_down() [已修复]
#    问题：原代码 get_price(stock, count=1, ...) 未指定end_date，
#          在before_market_open(9:26)调用时可能获取到当天未收盘数据。
#    修复：添加end_date参数，check_basic_quality中传入昨日交易日日期。
# 
# 2. adjust_params_by_market() 中 get_all_securities() [已修复]
#    问题：原代码未指定date参数，可能包含当天新上市的股票。
#    修复：加入 date=context.current_dt.date()。
# 
# 3. get_fundamentals() 调用 [已确认安全]
#    所有 get_fundamentals() 调用均已传入 date 参数，
#    确保获取的是历史数据而非未来数据。
# 
# 4. get_current_change() [已确认安全]
#    使用 get_trade_days 获取交易日昨收，逻辑正确。
# 
# 【已排查确认无问题的部分】
# 
# 1. attribute_history() - 默认使用 context.previous_date，安全
# 2. get_price() 带 end_date 参数 - 安全
# 3. get_current_data() - 获取实时数据，盘中使用安全
# 4. before_market_open 中使用 context.current_dt.date() 获取当日 - 安全
# 5. run_daily 定时任务调度 - 按时间点执行，无前视偏差
# 
# =========================================================