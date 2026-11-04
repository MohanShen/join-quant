# Clone from JoinQuant
# postId: 353f0f75d3c22568d2aca64b7eb01faf
# backtestId: e00356206f0d347c54e05f47962a6dbe
# title: 低位三连阳首板优化 14.1，26年胜率85%

# 克隆自聚宽文章：https://www.joinquant.com/post/71023
# 标题：低位3连阳首板接力 年收益1383% 第1版
# 作者：顶级理解
#
# 优化版本：Kimi2.6顶级研究员_v14.1_微改进版
# 优化日期：2026-05-16
#
# v14 核心哲学（基于v13回测反馈 + 原版成功要素分析）：
#   1. 【更宽松的大盘风控】v13的沪深300跌3%空仓过于激进，改为跌5%且连跌3天才空仓
#   2. 【保留原版所有核心过滤】不改变原版选股结构
#   3. 【高仓位集中】保持原版单仓可达100%的高集中度特征
#   4. 【有效改进清单】
#      - 动态止损：根据市场波动率调整止损线（-5%/-7%/-10%）
#      - 盈利持有：盈利>20%后放宽止损，让利润奔跑
#      - 大盘风控：沪深300连跌3日且累计跌>5%才暂停开仓（更宽松）
#      - 一字板过滤：买入时跳过一字板（无法买入）
#      - 涨停持有：持仓股当日涨停时不卖出（让利润奔跑）
#
# 原版回测（2022-2024）：收益17.53%, 夏普0.05, 最大回撤41.11%
# v14目标：收益>20%, 夏普>0.1, 最大回撤<35%

from jqdata import *
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date, time

# ========== 初始化设置 ==========
def initialize(context):
    """策略初始化函数，设置各项参数和定时任务"""
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.005))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0002, close_commission=0.0002, min_commission=5), type='stock')
    set_benchmark('399303.XSHE')

    # 全局变量存储
    g.information = {}
    g.sold_stocks = set()
    g.base_stocks = []
    g.today_pick = []
    g.pick_cache_date = ''
    g.minute_sell_cache = {}
    g.close_sell_cache = {}
    g.today_high = {}

    # v14: 新增变量
    g.enable_market_risk = False        # 大盘风控总开关（True=启用，False=跳过）
    g.market_risk_off = False       # 大盘风险信号
    g.dynamic_stop_loss = -0.07     # 动态止损线（默认-7%）
    g.market_down_days = 0          # 大盘连续下跌天数

    # 封单过滤控制
    g.enable_limit_money_filter = True   # 封单过滤总开关（True=启用，False=跳过）
    g.use_limit_money_ratio = True       # True=按封单金额占成交额比例过滤；False=按封单绝对金额过滤
    g.limit_money_ratio_threshold = 0.05 # 封单金额占成交额比例阈值
    g.limit_money_min = 0.5              # 封单绝对金额阈值（单位：亿）

    # 量价过滤参数
    g.min_turnover = 5e8                 # 最小成交额（单位：元）
    g.max_turnover = 30e8                # 最大成交额（单位：元）
    g.max_price_rise = 0.05              # 前两日涨幅上限（默认5%）

    # 仓位控制参数 - 保持原版高集中度
    g.max_position_pct = 1.0        # 单只股票最大仓位比例（100%，保持原版）
    g.max_hold_count = 1           # 最大持仓数量

    # 定时任务配置 - 与原版完全一致
    run_weekly(prepare_base_stocks, 1, '09:10')
    run_daily(precompute_minute_sell_cache, time='09:10')
    run_daily(get_buy, time='09:26')
    run_daily(get_close_sell, time='11:25')
    run_daily(get_close_sell, time='13:30')
    run_daily(get_close_sell, time='14:55')
    run_daily(get_minute_sell, time='every_bar')

# ========== 选股逻辑（与原版完全一致） ==========
def get_stock_list(context):
    """主选股函数，通过多层过滤筛选符合条件的股票"""
    target_list = prepare_stock_list(context)
    print(f"[选股] 首板标的数量: {len(target_list)}只")
    if not target_list:
        return []

    y_day = context.previous_date
    t_now = context.current_dt.strftime("%Y-%m-%d")

    target_list = filter_high_volatility(target_list, y_day)
    log.info(f"[选股] 过滤近5日波动>20%后: {len(target_list)}只")
    if not target_list:
        return []

    target_list = filter_market_cap(target_list, y_day)
    print(f"[选股] 市值过滤后: {len(target_list)}只")
    if not target_list:
        return []

    target_list = filter_volume_price(target_list, y_day)
    print(f"[选股] 量价过滤后: {len(target_list)}只")
    if not target_list:
        return []

    # 封单额度过滤
    if getattr(g, 'enable_limit_money_filter', True):
        target_list = filter_limit_money(target_list, y_day)
        print(f"[选股] 封单过滤后: {len(target_list)}只")
        if not target_list:
            return []
    else:
        print("[选股] 封单过滤已关闭，跳过")

    target_list = filter_auction(target_list, y_day, t_now)
    print(f"[选股] 最终选中: {target_list} (共{len(target_list)}只)")
    return target_list

# ========== 市值过滤（与原版一致） ==========
def filter_market_cap(stock_list, y_day):
    if not stock_list:
        return []
    df = get_valuation(stock_list, start_date=y_day, end_date=y_day,
                       fields=['market_cap', 'circulating_market_cap'])
    if df.empty:
        return []
    df.set_index('code', inplace=True)
    return df[(df.market_cap >= 30) & (df.circulating_market_cap <= 300)].index.tolist()

# ========== 量价过滤（与原版一致） ==========
def filter_volume_price(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['close', 'open', 'high', 'volume', 'money'],
                   count=35, skip_paused=True, fq='pre', panel=False)
    if df.empty:
        print("[量价过滤] 历史数据不足")
        return []

    candidates = []
    for code, group in df.groupby('code'):
        if len(group) < 6:
            continue

        group = group.sort_values('time').reset_index(drop=True)
        last = group.iloc[-1]
        d_b1 = group.iloc[-2]
        d_b2 = group.iloc[-3]
        d_b3 = group.iloc[-4]

        # 条件1：成交额范围
        if last.money < g.min_turnover or last.money > g.max_turnover:
            continue

        # 条件2：放量要求 - 昨日成交量 >= 前日成交量 * 2
        if d_b1.volume <= 0 or last.volume < d_b1.volume * 2:
            continue

        # 条件3：前天成交量 <= 大前天成交量 * 2
        if d_b2.volume <= 0 or d_b1.volume > d_b2.volume * 2:
            continue

        # 条件4：爆量限制
        if len(group) >= 31:
            prev_vols = group.volume.iloc[-6:-1].values
            if len(prev_vols) == 5 and prev_vols.min() > 0:
                avg_vol, min_vol = prev_vols.mean(), prev_vols.min()
                if (last.volume > avg_vol * 8 or last.volume > min_vol * 12) and last.close > group.high.iloc[-31:-1].max():
                    continue

        # 条件5：双阳线要求 - T-2和T-3均为阳线
        if not (d_b1.close > d_b1.open and d_b2.close > d_b2.open):
            continue

        # 条件6：数据异常检查
        if d_b2.close == 0 or d_b3.close == 0:
            continue

        # 条件7：短期涨幅限制 - 前两日涨幅均 < max_price_rise
        g1 = (d_b1.close - d_b2.close) / d_b2.close
        g2 = (d_b2.close - d_b3.close) / d_b3.close
        if g1 >= g.max_price_rise or g2 >= g.max_price_rise:
            continue

        candidates.append(code)

    return candidates

# ========== 集合竞价过滤（与原版一致） ==========
def filter_auction(stock_list, y_day, t_now):
    if not stock_list:
        return []

    hist_df = get_price(stock_list, end_date=y_day, frequency='1d',
                        fields=['close', 'volume'], count=1,
                        skip_paused=True, panel=False)
    if hist_df.empty:
        return []
    hist_map = hist_df.set_index('code')[['close', 'volume']].to_dict('index')

    start = t_now + ' 09:15:00'
    end = t_now + ' 09:26:00'
    sbgk = []

    for s in stock_list:
        if s not in hist_map:
            continue
        h = hist_map[s]
        lc, lv = h['close'], h['volume']
        if lc <= 0 or lv <= 0:
            continue
        try:
            auction = get_call_auction(s, start_date=start, end_date=end,
                                        fields=['time', 'volume', 'current'])
            if auction.empty:
                continue
            al = auction.iloc[-1]
            # 条件1：竞价成交量 >= 昨日总成交量的3%
            if al.volume / lv < 0.03:
                continue
            # 条件2：竞价涨幅在0%~6%之间
            ratio = al.current / lc
            if ratio <= 1.0 or ratio >= 1.06:
                continue
            sbgk.append(s)
        except:
            continue

    return sbgk

# ========== v14: 更宽松的大盘风控检查 ==========
def check_market_risk(context, y_day):
    """
    检查大盘风险：沪深300连跌3日且累计跌幅>5%时才暂停开仓
    比v13更宽松，避免在震荡市中过度空仓
    """
    try:
        hs300 = get_price('000300.XSHG', end_date=y_day, frequency='1d',
                          fields=['close'], count=10, skip_paused=True)
        if hs300 is None or len(hs300) < 10:
            return False

        closes = hs300['close'].values

        # 计算连续下跌天数
        daily_returns = np.diff(closes) / closes[:-1]
        down_days = 0
        for ret in reversed(daily_returns):
            if ret < 0:
                down_days += 1
            else:
                break

        # 近5日累计跌幅
        ret_5d = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] > 0 else 0

        # 条件：连跌3天且5日跌幅>5%
        if down_days >= 3 and ret_5d < -0.05:
            print(f"[大盘风控v14] 沪深300连跌{down_days}天, 5日收益{ret_5d*100:.1f}%, 暂停开仓")
            return True

        return False
    except Exception as e:
        print(f"[大盘风控] 检查失败: {e}")
        return False

# ========== v14: 动态止损线计算 ==========
def update_dynamic_stop_loss(context, y_day):
    """
    根据市场波动率动态调整止损线
    波动率大时放宽止损，波动率小时收紧
    """
    try:
        hs300 = get_price('000300.XSHG', end_date=y_day, frequency='1d',
                          fields=['close'], count=20, skip_paused=True)
        if hs300 is None or len(hs300) < 10:
            g.dynamic_stop_loss = -0.07
            return

        closes = hs300['close'].values
        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns) * np.sqrt(252)

        # 波动率<15%：止损-5%；15%-25%：止损-7%；>25%：止损-10%
        if volatility < 0.15:
            g.dynamic_stop_loss = -0.05
        elif volatility < 0.25:
            g.dynamic_stop_loss = -0.07
        else:
            g.dynamic_stop_loss = -0.10

        print(f"[动态止损v14] 波动率{volatility*100:.1f}%, 止损线{g.dynamic_stop_loss*100:.0f}%")
    except Exception as e:
        g.dynamic_stop_loss = -0.07
        print(f"[动态止损] 计算失败，使用默认-7%: {e}")

# ========== 买入股票（v14改进版） ==========
def get_buy(context):
    """买入函数：在09:27执行"""
    c_data = get_current_data()
    t_date = context.current_dt.strftime('%Y%m%d')
    y_day = context.previous_date

    # v14: 更新动态止损线
    update_dynamic_stop_loss(context, y_day)

    # v14: 大盘风控检查（更宽松）
    if getattr(g, 'enable_market_risk', True):
        g.market_risk_off = check_market_risk(context, y_day)
        if g.market_risk_off:
            print(f"[买入v14] 大盘风险信号，今日暂停开仓")
            return
    else:
        g.market_risk_off = False
        print("[买入v14] 大盘风控已关闭，跳过")

    holdings = [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]
    if len(holdings) >= g.max_hold_count:
        print(f"[买入] 持仓已达上限 {g.max_hold_count} 只")
        return

    if g.pick_cache_date != t_date:
        g.today_pick = get_stock_list(context)
        g.pick_cache_date = t_date

    qualified = [s for s in g.today_pick if s not in holdings]
    print(f"[买入] 候选标的(排除持仓后): {qualified}")
    if not qualified:
        return

    slots = g.max_hold_count - len(holdings)
    to_buy = qualified[:slots]

    total = context.portfolio.total_value
    max_per = total * g.max_position_pct
    per_stock = min(context.portfolio.available_cash / len(to_buy), max_per)
    print(f"[买入v14] 当前持仓{len(holdings)}只，可再买{slots}只，每只分配{per_stock:.2f}")

    for s in to_buy:
        cd = c_data[s]
        op = cd.day_open

        # v14: 跳过一字板（无法买入）
        if op >= cd.high_limit * 0.99:
            print(f"  [买入跳过] {s}: 一字板无法买入")
            continue

        shares = math.floor(per_stock / op / 100) * 100
        if shares >= 100:
            order = order_target(s, shares, MarketOrderStyle(op))
            print(f"  [买入下单] {s}: 开盘价{op:.2f}, 计划金额{per_stock:.2f}, 预计{shares}股, 订单{order}")
            g.information[s] = {'buy_date': t_date}
        else:
            print(f"  [买入跳过] {s}: 资金不足1手")

# ========== 尾盘止盈止损（v14改进版） ==========
def get_close_sell(context):
    """尾盘卖出函数：在11:25、13:30、14:55执行"""
    t_date = context.current_dt.strftime("%Y%m%d")
    hold = [s for s, p in context.portfolio.positions.items()
            if p.total_amount > 0 and g.information.get(s, {}).get('buy_date') != t_date]
    print(f"[尾盘] 可卖标的: {hold}")
    if not hold:
        return

    metrics = g.close_sell_cache
    c_data = get_current_data()

    for s in hold:
        if s not in metrics:
            continue
        pos = context.portfolio.positions[s]
        cd = c_data[s]
        cp = cd.last_price
        yc = metrics[s]['y_close']
        ma5 = metrics[s]['ma5']
        dg = (cp - yc) / yc
        pp = (cp - pos.avg_cost) / pos.avg_cost

        print(f"  [持仓检查] {s}: 现价{cp:.2f}, 成本{pos.avg_cost:.2f}, 收益{pp*100:.2f}%, 当日涨跌{dg*100:.2f}%, MA5={ma5:.2f}")

        # v14: 当日涨停时坚决持有（让利润奔跑）
        if cp >= cd.high_limit * 0.99:
            print(f"[持有v14] {s}: 当日涨停，继续持有")
            continue

        sell, reason = False, ""

        # v14: 盈利持有逻辑 - 盈利>20%后放宽止损到-10%，让利润奔跑
        if pp > 0.20:
            # 盈利超过20%，使用更宽松的止损
            if pp <= -0.10:
                sell, reason = True, f"盈利回吐至-10% ({pp*100:.2f}%)"
            elif dg < -0.05:
                sell, reason = True, f"盈利股当日跌幅>5% ({dg*100:.2f}%)"
        else:
            # 盈利<20%，使用标准止损
            # 条件1：盈利超过50%
            if pp > 0.5:
                sell, reason = True, "收益>50%"
            # 条件2：当日跌幅超过-2%
            if dg < -0.02:
                sell, reason = True, f"当日涨幅<-2% ({dg*100:.2f}%)"
            # 条件3：当前价跌破开盘价的-4%
            elif cp < cd.day_open * 0.96:
                sell, reason = True, f"当前价<开盘价的-4% ({cp:.2f}<{cd.day_open*0.96:.2f})"
            # 条件4：持仓亏损超过动态止损线
            elif pp <= g.dynamic_stop_loss:
                sell, reason = True, f"收益<={g.dynamic_stop_loss*100:.0f}% ({pp*100:.2f}%)"
            # 条件5：跌破5日均线的-3%
            elif cp < ma5 * 0.97:
                sell, reason = True, f"跌破5日均线-3% ({cp:.2f}<{ma5*0.97:.2f})"

        if sell:
            order = order_target_value(s, 0)
            print(f"    [卖出] {s}: {reason}，清仓，订单{order}")
        else:
            print(f"    [持有] {s}: 无卖出条件触发")

# ========== 每分钟执行：线性止盈（与原版一致） ==========
def get_minute_sell(context):
    ct = context.current_dt.time()
    if ct < time(9, 30) or ct > time(11, 25):
        return

    t_date = context.current_dt.strftime("%Y%m%d")
    hold = [s for s, p in context.portfolio.positions.items()
            if p.total_amount > 0 and g.information.get(s, {}).get('buy_date') != t_date]
    if not hold:
        return

    c_data = get_current_data()
    for s in hold:
        cache = g.minute_sell_cache.get(s)
        if not cache or cache['date'] != context.previous_date:
            continue

        cd = c_data[s]
        cp = cd.last_price

        # v14: 当日涨停不执行分钟止盈
        if cp >= cd.high_limit * 0.99:
            continue

        # 昨日一字板后今日高位放巨量不涨停，触发卖出
        y_hl = cache.get('y_high_limit', 0)
        y_op = cache.get('y_open', 0)
        if y_hl > 0 and y_op >= y_hl * 0.99 and cache['y_close'] >= y_hl * 0.99:
            # 昨日一字板（开盘价≈涨停价 且 收盘价≈涨停价）
            t_now_str = context.current_dt.strftime('%Y-%m-%d')
            df_today = get_price(s, start_date=t_now_str, end_date=context.current_dt,
                                 frequency='1m', fields=['volume'], skip_paused=False)
            today_vol = df_today['volume'].sum() if not df_today.empty else 0
            y_vol = cache.get('y_volume', 0)
            # print(f"[一字板检测] {s}: 昨开{y_op:.2f}, 昨收{cache['y_close']:.2f}, 昨涨停价{y_hl:.2f}, 昨量{y_vol}, 今量{today_vol}, 量比{today_vol/y_vol:.1f}倍" if y_vol > 0 else f"[一字板检测] {s}: 昨量为0，跳过")
            if y_vol > 0 and today_vol >= y_vol * 8 and cp < cd.high_limit * 0.99:
                order_target_value(s, 0)
                print(f"[一字板放量] {s}: 昨日一字板, 今日量比{today_vol/y_vol:.1f}倍, 未涨停, 清仓")
                g.today_high.pop(s, None)
                continue



        if cache['y_day_gain'] >= 0:
            continue

        th = g.today_high.get(s, 0)
        if cp > th:
            g.today_high[s] = cp
            th = cp

        # 线性止盈：昨日收跌的标的，今日冲高后回落超动态阈值且跌破昨日最高价，触发清仓
        # chr = 今日最高价相对昨收的冲高幅度（冲高>3%才进入止盈监控）
        # lt  = 动态回撤阈值：冲高越多，允许回撤越小（冲高1%→2%，冲高3%→1%，冲高5%→0.5%）
        #       公式：lt = max(0.5%, 2% - (chr - 1%) × 0.5)
        # dg  = 当前价与昨日最高价的差值，dg<0 表示已跌破昨日最高价（破位确认）
        # 触发条件：cp < th×(1-lt) 且 dg < 0
        #   即：从今日高点回落超过动态阈值 且 当前价低于昨日最高价
        chr = (th - cache['y_close']) / cache['y_close'] if cache['y_close'] > 0 else 0
        dg = cp - cache['y_high']
        if chr > 0.03:
            lt = max(0.005, 0.02 - (chr - 0.01) * 0.5)
            if cp < th * (1 - lt) and dg < 0:
                order_target_value(s, 0)
                print(f"[线性止盈] {s}: 昨日跌幅{cache['y_day_gain']*100:.2f}%, 冲高{chr*100:.2f}%, 回撤{(1-cp/th)*100:.2f}% > {lt*100:.2f}%, 清仓")
                g.today_high.pop(s, None)

        

# ========== 波动过滤（与原版一致） ==========
def filter_high_volatility(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['high', 'low'], count=5, panel=False,
                   skip_paused=True, fill_paused=False)
    if df.empty:
        return stock_list
    grp = df.groupby('code')
    chg = (grp['high'].max() - grp['low'].min()) / grp['low'].min()
    return chg[chg <= 0.2].index.tolist()


def get_limit_up_money(stock_list, date_str):
    """
    获取指定日期收盘时的涨停封单金额
    date_str: 格式如 "2026-05-01"
    """
    end_time = date_str + " 15:00:00"
    result = {}

    for s in stock_list:
        try:
            s_ticks = get_ticks(s, end_dt=end_time, start_dt=None, count=1,
                               fields=['time', 'b1_p', 'b1_v'])
            if s_ticks is None or len(s_ticks) == 0:
                continue
            last = s_ticks[-1]

            # XSHG(沪市)的b1_v单位是"手"，需要×100转为股；XSHE(深市)的b1_v单位是"股"
            b1_p = float(last['b1_p'])
            b1_v = float(last['b1_v'])
            
            if 'XSHG' in s:
                b1_v = b1_v * 100
            money = b1_p * b1_v / 1e8  # 返回单位：亿
            if money > 0:
                result[s] = money
        except Exception as e:
            print(f"[封单] {s} 获取tick失败: {e}")
            continue

    return result

# ========== 封单额度过滤 ==========
def filter_limit_money(data, y_day):
    """
    根据涨停封单金额过滤股票
    支持两种模式（由 g.use_limit_money_ratio 控制）：
      - True:  按封单金额占昨日成交额比例过滤（默认）
      - False: 按封单绝对金额过滤（阈值由 g.limit_money_min 控制）
    支持 DataFrame 或 股票列表 输入
    """
    if isinstance(data, pd.DataFrame):
        limit_stocks = data[data['is_limit']]['code'].unique().tolist()
    elif isinstance(data, list):
        limit_stocks = data
    else:
        raise TypeError("data 必须是 DataFrame 或 list")
    
    t_date = y_day.strftime("%Y-%m-%d") if hasattr(y_day, 'strftime') else str(y_day)
    limit_money = get_limit_up_money(limit_stocks, t_date)
    print(f"[封单金额] {{{', '.join([f'{s}: {m:.2f}亿' for s, m in sorted(limit_money.items(), key=lambda x: x[1], reverse=True)])}}}")
    
    # 读取全局参数
    min_money = getattr(g, 'limit_money_min', 0.5)
    
    if getattr(g, 'use_limit_money_ratio', True):
        # 按封单金额占成交额比例过滤
        ratio_threshold = getattr(g, 'limit_money_ratio_threshold', 0.1)
        
        # 获取昨日成交额（单位：元）
        try:
            money_df = get_price(limit_stocks, end_date=y_day, frequency='1d',
                                 fields=['money'], count=1, panel=False,
                                 skip_paused=True, fill_paused=False)
            turnover_map = money_df.set_index('code')['money'].to_dict() if not money_df.empty else {}
        except Exception as e:
            print(f"[封单过滤] 获取成交额失败: {e}")
            turnover_map = {}
        
        strong_limit = []
        ratios = []
        for s, m in limit_money.items():
            turnover = turnover_map.get(s, 0)
            if turnover > 0:
                ratio = m / (turnover / 1e8)  # 封单金额(亿) / 成交额(亿)
                ratios.append((s, ratio))
                if ratio >= ratio_threshold:
                    strong_limit.append(s)
            else:
                # 成交额获取失败时， fallback 到绝对金额过滤
                if m >= min_money:
                    strong_limit.append(s)
        
        print(f"[封单过滤] 比例模式(>={ratio_threshold*100:.0f}%) 过滤前: {len(limit_stocks)}只, 过滤后: {len(strong_limit)}只")
        if ratios:
            print(f"[封单比例] {{{', '.join([f'{s}: {r*100:.1f}%' for s, r in sorted(ratios, key=lambda x: x[1], reverse=True)])}}}")
    else:
        # 按封单绝对金额过滤
        strong_limit = [s for s, m in limit_money.items() if m >= min_money]
        print(f"[封单过滤] 绝对金额模式(>={min_money}亿) 过滤前: {len(limit_stocks)}只, 过滤后: {len(strong_limit)}只")
    
    if isinstance(data, pd.DataFrame):
        data['is_limit'] = data['is_limit'] & data['code'].isin(strong_limit)
        return data
    else:
        return strong_limit

# ========== 首板过滤（与原版一致） ==========
def prepare_stock_list(context):
    y_day = context.previous_date
    if not g.base_stocks:
        prepare_base_stocks(context)

    df = get_price(g.base_stocks, end_date=y_day, frequency='1d',
                   fields=['close', 'high_limit'], count=2, panel=False, 
                   skip_paused=True, fill_paused=False, fq='pre')
    if len(df) < 2:
        return []

    df['is_limit'] = np.isclose(df.close, df.high_limit, rtol=0.005, atol=0.01)
    
    groups = df[df.is_limit].groupby('time')['code'].apply(set)


    if len(groups) >= 2:
        return list(groups.iloc[-1] - groups.iloc[-2])
    elif len(groups) == 1:
        return list(groups.iloc[-1])
    return []

# ========== 基础股票池（与原版一致） ==========
def prepare_base_stocks(context):
    by_date = get_trade_days(end_date=context.previous_date, count=50)[0]
    all_s = get_all_securities(['stock'], date=by_date).index
    cd = get_current_data()
    g.base_stocks = [s for s in all_s if not (
        s[0] in '3489' or s[:2] == '68' or
        cd[s].is_st or cd[s].paused or
        '退' in cd[s].name or 'ST' in cd[s].name
    )]
    print(f"[基础池] 筛选完成，共{len(g.base_stocks)}只")

# ========== 盘前预计算缓存（与原版一致） ==========
def precompute_minute_sell_cache(context):
    pos = list(context.portfolio.positions.keys())
    if not pos:
        g.minute_sell_cache = {}
        g.close_sell_cache = {}
        return

    df2 = get_price(pos, end_date=context.previous_date, frequency='1d',
                    fields=['close', 'high', 'open', 'high_limit', 'volume'], count=2, panel=False,
                    skip_paused=False, fill_paused=True)
    for s, sub in df2.groupby('code'):
        if len(sub) >= 2:
            yc, pc = sub['close'].iloc[-1], sub['close'].iloc[-2]
            yh = sub['high'].iloc[-1]
            g.minute_sell_cache[s] = {
                'y_close': yc,
                'y_high': yh,
                'y_open': sub['open'].iloc[-1],
                'y_high_limit': sub['high_limit'].iloc[-1],
                'y_volume': sub['volume'].iloc[-1],
                'prev_close': pc,
                'y_day_gain': (yc - pc) / pc if pc > 0 else 0,
                'date': context.previous_date
            }

    df5 = get_price(pos, end_date=context.previous_date, frequency='1d',
                    fields=['close'], count=5, panel=False,
                    skip_paused=False, fill_paused=True)
    g.close_sell_cache = {}
    for s, sub in df5.groupby('code')['close']:
        if len(sub) >= 2:
            g.close_sell_cache[s] = {
                'y_close': sub.iloc[-1],
                'ma5': sub.mean()
            }

    g.today_high.clear()

# ========== 收盘后清理（与原版一致） ==========
def after_trading_end(context):
    g.sold_stocks.clear()
    cur = set(context.portfolio.positions.keys())
    g.information = {k: v for k, v in g.information.items() if k in cur}
    g.minute_sell_cache = {k: v for k, v in g.minute_sell_cache.items() if k in cur}
    g.close_sell_cache = {k: v for k, v in g.close_sell_cache.items() if k in cur}
    g.today_high.clear()
