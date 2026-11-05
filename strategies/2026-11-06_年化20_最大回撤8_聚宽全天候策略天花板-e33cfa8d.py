# Clone from JoinQuant
# postId: e33cfa8d5f88b093b5941e3b32b4f85a
# backtestId: b423c71befbd15c7b06b53cafc4fa759
# title: 年化20%、最大回撤8%：聚宽全天候策略天花板

# -*- coding: utf-8 -*-
"""
三合一_永久全天候：3个全天候/永久策略独立运行
每个策略使用独立子账户（SubPortfolioConfig），互不影响。
回测时可单独查看每个子策略的表现。

子策略列表：
  0 - 红利低波全天候（MA250偏离度驱动A/B模式，B模式=MACD全天候4仓位）
  1 - 永久投资优化（3资产等权+±18%价格触发再平衡+估值评分）
  2 - 全天候策略微调（5仓位MACD+RSI+市场趋势，半月调仓）
"""

from jqdata import *
from jqlib.technical_analysis import *
import numpy as np
import pandas as pd
import math
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from collections import defaultdict

# =================================================================
# Section 0: 全局配置
# =================================================================

# 策略名称
STRATEGY_NAMES = [
    '红利低波全天候',
    '永久投资优化',
    '全天候策略微调',
]

# 策略简称（用于通知中的紧凑展示）
STRATEGY_SHORT = ['红利低波', '永久优化', '微调']

# 三个子策略的资金分配权重，各1/3，与权重修复版的有效资金一致。
ALLOCATION_WEIGHTS = [1.0 / 3, 1.0 / 3, 1.0 / 3]

# ---- 统一调度时间配置（修改这里即可调整所有策略的执行时间）----
SCHEDULE = {
    'pre_market': '9:10',           # 盘前：年度清仓等准备工作
    'daily_trade': '11:00',         # 每日交易：策略1/2 每日检查
    'monthly_trade': '11:00',       # 月度交易：策略3以及策略1的B模式月调仓
    'weekly_monitor': '14:30',      # 每周市场监控：策略3
    'post_market': '15:10',         # 盘后：每日收盘报告

    # --- 月度交易日参数（本月第几个交易日）---
    's1_monthly_day': 1,            # 策略1：B模式月度调仓日
    's3_monthly_day1': 1,           # 策略3：上半月调仓日
    's3_monthly_day2': 15,          # 策略3：下半月调仓日

    # --- 每周交易日参数（周几，1=周一...5=周五）---
    's3_weekly_day': 1,             # 策略3：每周市场监控日（1=周一）
}

# 邮件配置
EMAIL_CONFIG = {
    'enabled': True,
    'smtp_server': 'smtp.qq.com',
    'smtp_port': 587,
    'sender_email': '11111111111111111111111111111@qq.com',
    'sender_name': '三合一永久全天候策略通知',
    'password': '1111111111111111111111111111111111',
    'recipients': ['1111111111111111111111111111@qq.com'],
}

# ETF代码→中文名称映射（兜底用，防止聚宽接口偶尔返回代码本身）
ETF_NAME_MAP = {
    '511260.XSHG': '十年国债ETF',
    '511520.XSHG': '30年国债ETF活跃',
    '511880.XSHG': '银华日利',
    '511360.XSHG': '短融ETF',
    '511010.XSHG': '国债ETF',
    '512890.XSHG': '红利低波ETF',
    '518880.XSHG': '黄金ETF',
    '513100.XSHG': '纳指ETF',
    '159949.XSHE': '创业板50ETF',
    '159985.XSHE': '豆粕ETF',
    '159915.XSHE': '创业板ETF',
    '510300.XSHG': '沪深300ETF',
    '000300.XSHG': '沪深300指数',
}


# =================================================================
# Section 1: 通用工具函数
# =================================================================

def get_name(code):
    """获取证券名称，优先实时接口，兜底用映射表"""
    try:
        cd = get_current_data()
        name = cd[code].name
        if name and name != code and not name.startswith('5') and not name.startswith('1'):
            return name
    except:
        pass
    if code in ETF_NAME_MAP:
        return ETF_NAME_MAP[code]
    try:
        info = get_security_info(code)
        if info and info.display_name:
            return info.display_name
    except:
        pass
    return code


def send_email(context, subject, content):
    """发送邮件+微信通知（仅模拟交易模式）"""
    log.info(content)
    if context.run_params.type != 'sim_trade':
        return
    if not EMAIL_CONFIG['enabled']:
        return
    try:
        send_message(content, channel='weixin')
    except:
        pass
    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr((Header(EMAIL_CONFIG['sender_name'], 'utf-8').encode(),
                                  EMAIL_CONFIG['sender_email']))
        msg['To'] = ", ".join(EMAIL_CONFIG['recipients'])
        msg['Subject'] = Header(subject, 'utf-8')
        msg.attach(MIMEText(content, 'plain', 'utf-8'))
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['password'])
        server.sendmail(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['recipients'], msg.as_string())
        server.quit()
    except Exception as e:
        log.warn('邮件发送失败: %s' % str(e))


def snapshot_positions(context, pindex):
    """快照指定子账户持仓"""
    positions = context.subportfolios[pindex].long_positions
    snap = {}
    for code, pos in positions.items():
        if pos.total_amount > 0:
            snap[code] = {
                'amount': pos.total_amount,
                'avg_cost': pos.avg_cost,
                'price': pos.price,
                'value': pos.value,
            }
    return snap


def detect_trades(before, after, current_data):
    """对比快照前后，检测实际成交"""
    trades = []
    all_codes = set(list(before.keys()) + list(after.keys()))
    for code in all_codes:
        amt_before = before.get(code, {}).get('amount', 0)
        amt_after = after.get(code, {}).get('amount', 0)
        if amt_before == amt_after:
            continue
        name = get_name(code)
        if amt_after > amt_before:
            cost = after[code]['avg_cost'] if code in after else 0
            trades.append({
                'action': '买入',
                'code': code,
                'name': name,
                'amount': amt_after - amt_before,
                'price': cost,
                'value': (amt_after - amt_before) * cost,
            })
        else:
            cost = before[code]['avg_cost'] if code in before else 0
            price = current_data[code].last_price if code in current_data else 0
            trades.append({
                'action': '卖出',
                'code': code,
                'name': name,
                'amount': amt_before - amt_after,
                'price': price,
                'cost': cost,
                'value': (amt_before - amt_after) * price,
            })
    return trades


def execute_strategy_with_notify(context, pindex, trade_func, reason='调仓'):
    """执行单个策略，快照前后对比，有实际成交则发送通知"""
    # 空账户不发零金额订单；持仓账户仍可正常处理卖出。
    # 已有持仓的账户继续处理，不能因为可用现金为0而跳过卖出。
    sub = context.subportfolios[pindex]
    if sub.total_value <= 0 and len(sub.long_positions) == 0:
        return []
    current_data = get_current_data()
    before = snapshot_positions(context, pindex)

    try:
        trade_func(context)
    except Exception as e:
        import traceback as _tb
        log.error("AW_AUDIT_TRADE_FAILURE strategy=%s reason=%s\n%s" % (pindex + 1, reason, _tb.format_exc()))
        raise


    after = snapshot_positions(context, pindex)
    trades = detect_trades(before, after, current_data)

    if trades:
        notify_strategy_trades(context, pindex, trades, reason)
    return trades


def notify_strategy_trades(context, pindex, trades, reason='调仓'):
    """发送单策略调仓通知"""
    dt_str = context.current_dt.strftime('%Y-%m-%d %H:%M')
    name = STRATEGY_NAMES[pindex]
    short = STRATEGY_SHORT[pindex]
    sub = context.subportfolios[pindex]

    lines = []
    lines.append('')
    lines.append('=' * 55)
    lines.append('  %s通知 | 策略%d-%s | %s' % (reason, pindex + 1, name, dt_str))
    lines.append('=' * 55)
    lines.append('')
    lines.append('  子账户资产: {:,.0f} | 现金: {:,.0f}'.format(sub.total_value, sub.available_cash))
    lines.append('')
    lines.append('  {:6s} {:12s} {:8s} {:>8s} {:>8s} {:>10s}'.format(
        '方向', '代码', '名称', '数量', '价格', '金额'))
    lines.append('  ' + '-' * 58)

    for t in trades:
        if t['action'] == '买入':
            lines.append('  {:6s} {:12s} {:8s} {:>8d} {:>8.4f} {:>10,.0f}'.format(
                '买入', t['code'], t['name'][:8], t['amount'], t['price'], t.get('value', 0)))
        else:
            pnl = (t['price'] - t['cost']) * t['amount'] if t.get('cost', 0) > 0 else 0
            pnl_pct = (t['price'] / t['cost'] - 1) * 100 if t.get('cost', 0) > 0 else 0
            lines.append('  {:6s} {:12s} {:8s} {:>8d} {:>8.4f} {:>10,.0f}  盈亏:{:+.0f}({:+.2f}%)'.format(
                '卖出', t['code'], t['name'][:8], t['amount'], t['price'],
                t.get('value', 0), pnl, pnl_pct))

    # 调仓后持仓快照
    lines.append('')
    lines.append('  调仓后持仓:')
    positions = sub.long_positions
    if positions:
        for code, pos in positions.items():
            if pos.total_amount > 0:
                lines.append('    %s(%s) 数量:%d 成本:%.4f 现价:%.4f 市值:%.0f' % (
                    get_name(code), code, pos.total_amount, pos.avg_cost, pos.price, pos.value))
    else:
        lines.append('    空仓')

    lines.append('')
    lines.append('=' * 55)
    content = '\n'.join(lines)
    subject = '%s-%s-%s' % (reason, short, context.current_dt.strftime('%m-%d %H:%M'))
    send_email(context, subject, content)


# =================================================================
# Section 2: 每日收盘报告
# =================================================================

def daily_report(context):
    """盘后收盘报告：总览+各策略详情+持仓明细"""
    dt_str = context.current_dt.strftime('%Y-%m-%d')
    current_data = get_current_data()
    lines = []
    lines.append('')
    lines.append('=' * 65)
    lines.append('  三合一永久全天候 每日报告 | %s' % dt_str)
    lines.append('=' * 65)

    # --- 组合总览 ---
    # 定档加固：内建 sum() 在聚宽会被 star import 覆盖成 numpy.sum（09-28 IV 版腰斩根因），
    # 这三行是基准原文既有写法，只影响盘后报告的合计展示，不进撮合与净值，故可安全改为显式累加。
    _tv = 0.0
    for _i in range(3):
        _tv += context.subportfolios[_i].total_value
    total_value_all = _tv
    _iv = 0.0
    for _v in g.initial_values:
        _iv += _v
    total_starting = _iv
    _tc = 0.0
    for _i in range(3):
        _tc += context.subportfolios[_i].available_cash
    total_cash = _tc
    total_position_value = total_value_all - total_cash
    total_return = (total_value_all / total_starting - 1) * 100 if total_starting > 0 else 0

    lines.append('')
    lines.append('【组合总览】起始日期: %s' % g.start_date_str)
    lines.append('  总资产: {:,.0f} | 持仓市值: {:,.0f} | 现金: {:,.0f} | 总收益: {:+.2f}%'.format(
        total_value_all, total_position_value, total_cash, total_return))

    # 汇总所有子账户持仓
    holding_agg = {}
    for i in range(3):
        sub = context.subportfolios[i]
        short_name = '%d-%s' % (i + 1, STRATEGY_SHORT[i])
        for code, pos in sub.long_positions.items():
            if pos.total_amount <= 0:
                continue
            if code not in holding_agg:
                holding_agg[code] = {'name': get_name(code), 'total_amount': 0,
                                     'total_value': 0, 'price': pos.price, 'strategies': []}
            holding_agg[code]['total_amount'] += pos.total_amount
            holding_agg[code]['total_value'] += pos.value
            holding_agg[code]['strategies'].append((short_name, pos.total_amount, pos.value))

    if holding_agg:
        lines.append('')
        lines.append('  持仓汇总:')
        lines.append('  {:12s} {:10s} {:>8s} {:>8s} {:>10s}   {}'.format(
            '代码', '名称', '总数量', '现价', '总市值', '各策略(数量/市值)'))
        lines.append('  ' + '-' * 72)
        for code, info in sorted(holding_agg.items(), key=lambda x: x[1]['total_value'], reverse=True):
            detail_str = ' | '.join(['%s:%d/%.0f' % (s[0], s[1], s[2]) for s in info['strategies']])
            lines.append('  {:12s} {:10s} {:>8d} {:>8.4f} {:>10,.0f}   {}'.format(
                code, info['name'][:10], info['total_amount'], info['price'],
                info['total_value'], detail_str))
    else:
        lines.append('  当前持仓: 空仓')

    # --- 各策略详情 ---
    lines.append('')
    lines.append('-' * 65)
    lines.append('【各策略收益概览】')
    lines.append('  {:4s} {:8s} {:>10s} {:>10s} {:>8s} {:>8s} {:>8s} {:>8s}'.format(
        '编号', '策略', '当前资产', '初始资金', '总收益', '年收益', '月收益', '日收益'))
    lines.append('  ' + '-' * 68)

    for i in range(3):
        sub = context.subportfolios[i]
        current_val = sub.total_value
        starting = g.initial_values[i]
        total_ret = (current_val / starting - 1) * 100 if starting > 0 else 0
        ytd = (current_val / g.year_start_values[i] - 1) * 100 if g.year_start_values[i] > 0 else 0
        mtd = (current_val / g.month_start_values[i] - 1) * 100 if g.month_start_values[i] > 0 else 0
        daily = (current_val / g.prev_day_values[i] - 1) * 100 if g.prev_day_values[i] > 0 else 0
        lines.append('  {:4s} {:8s} {:>10,.0f} {:>10,.0f} {:>+8.2f}% {:>+8.2f}% {:>+8.2f}% {:>+8.2f}%'.format(
            '%d' % (i + 1), STRATEGY_SHORT[i], current_val, starting, total_ret, ytd, mtd, daily))

    # --- 各策略持仓明细 ---
    for i in range(3):
        sub = context.subportfolios[i]
        name = STRATEGY_NAMES[i]
        lines.append('')
        lines.append('-' * 65)
        lines.append('【策略%d - %s】' % (i + 1, name))
        lines.append('  资产: {:,.0f} | 现金: {:,.0f}'.format(sub.total_value, sub.available_cash))

        positions = sub.long_positions
        if positions:
            lines.append('  {:12s} {:10s} {:>6s} {:>8s} {:>8s} {:>7s} {:>10s}'.format(
                '代码', '名称', '数量', '成本', '现价', '涨跌%', '市值'))
            for code, pos in positions.items():
                if pos.total_amount <= 0:
                    continue
                sec_name = get_name(code)[:10]
                cur_price = pos.price
                cost = pos.avg_cost
                pnl_pct = (cur_price / cost - 1) * 100 if cost > 0 else 0
                lines.append('  {:12s} {:10s} {:>6d} {:>8.4f} {:>8.4f} {:>+7.2f} {:>10,.0f}'.format(
                    code, sec_name, pos.total_amount, cost, cur_price, pnl_pct, pos.value))
        else:
            lines.append('  持仓: 空仓')

    lines.append('')
    lines.append('=' * 65)
    content = '\n'.join(lines)
    subject = '每日报告-%s' % dt_str
    send_email(context, subject, content)

    # 更新前日值（用于计算次日日收益）
    for i in range(3):
        g.prev_day_values[i] = context.subportfolios[i].total_value

    # 回测图表：record() 画3条策略收益率曲线
    ret_dict = {}
    for i in range(3):
        cap = context.subportfolios[i].total_value
        init = g.initial_values[i]
        ret_dict[STRATEGY_SHORT[i]] = round((cap / init - 1) * 100, 2) if init > 0 else 0
    record(**ret_dict)


def update_period_values(context):
    """年初/月初更新基准值（用于计算年/月收益）"""
    today = context.current_dt.date()
    if g.last_recorded_year != today.year:
        for i in range(3):
            g.year_start_values[i] = context.subportfolios[i].total_value
        g.last_recorded_year = today.year
    if g.last_recorded_month != today.month:
        for i in range(3):
            g.month_start_values[i] = context.subportfolios[i].total_value
        g.last_recorded_month = today.month


# =================================================================
# Section 3: 策略1 - 红利低波全天候（MA250偏离度驱动A/B模式）
# =================================================================
# A模式：全仓持有512890（红利低波ETF）
# B模式：MACD驱动的全天候4仓位（创业板50/纳指/红利低波/黄金/30年国债）
# 触发：512890前日最低价/MA250 < 0.985 → 买入(切A)
#       512890前日最高价/MA250 > 1.095 → 卖出(切B)

# 策略1使用的ETF
S1_ETF_GROWTH = '159949.XSHE'    # 创业板50ETF
S1_ETF_OVERSEAS = '513100.XSHG'  # 纳指ETF
S1_ETF_DIVIDEND = '512890.XSHG'  # 红利低波ETF
S1_ETF_GOLD = '518880.XSHG'      # 黄金ETF
S1_ETF_BOND = '511520.XSHG'      # 30年国债ETF活跃


def s1_trade_logic(context):
    """策略1每日检查：MA250偏离度决定A/B模式切换"""
    pindex = 0
    sub = context.subportfolios[pindex]
    current_data = get_current_data()

    etf = g.s1_etf  # 512890.XSHG（红利低波）
    if current_data[etf].paused:
        return

    # 获取250日均线
    hist_close = attribute_history(etf, g.s1_ma_length, '1d', ['close'], skip_paused=True)
    if len(hist_close) < g.s1_ma_length:
        return
    ma250 = hist_close['close'].mean()

    # 上一交易日最高/最低价
    hist_hl = attribute_history(etf, 1, '1d', ['high', 'low'], skip_paused=True)
    if hist_hl.empty:
        return
    prev_low = hist_hl['low'].iloc[0]
    prev_high = hist_hl['high'].iloc[0]

    ratio_low = prev_low / ma250
    ratio_high = prev_high / ma250

    total_assets = sub.total_value

    # --- 买入信号：切换至A模式，全仓512890 ---
    if ratio_low < g.s1_buy_threshold:
        if g.s1_mode == 'B':
            for sec in list(sub.long_positions.keys()):
                order_target(sec, 0, pindex=pindex)
            order_target_value(etf, total_assets, pindex=pindex)
            g.s1_mode = 'A'
            g.s1_stock_fund = []
        elif g.s1_mode == 'A':
            etf_amount = sub.long_positions[etf].total_amount if etf in sub.long_positions else 0
            if etf_amount == 0:
                order_target_value(etf, total_assets, pindex=pindex)

    # --- 卖出信号：切换至B模式，执行全天候配置 ---
    elif ratio_high > g.s1_sell_threshold:
        if g.s1_mode == 'A':
            etf_amount = sub.long_positions[etf].total_amount if etf in sub.long_positions else 0
            if etf_amount > 0:
                order_target(etf, 0, pindex=pindex)
                g.s1_mode = 'B'
                g.s1_stock_fund = []
                s1_rebalance_b(context)



def s1_rebalance_b(context):
    """策略1 B模式：全天候4仓位配置（MACD信号驱动）"""
    pindex = 0
    sub = context.subportfolios[pindex]
    check_date = context.current_dt

    # 年度首日清仓重建
    if s1_is_year_first_trade(context):
        for s in list(sub.long_positions.keys()):
            order_target(s, 0, pindex=pindex)

    # MACD月线信号
    macd_cyb = s1_get_macd_M(S1_ETF_GROWTH, check_date)
    macd_nz = s1_get_macd_M(S1_ETF_OVERSEAS, check_date)
    macd_gold = s1_get_macd_M(S1_ETF_GOLD, check_date)
    macd_300 = s1_get_macd_M('000300.XSHG', check_date)
    zf = s1_get_zf(context)

    # 仓位1 (30%)：创业板50 > 纳指 > 红利低波 > 国债
    if macd_cyb > 0:
        slot1 = S1_ETF_GROWTH
    elif macd_nz > 0:
        slot1 = S1_ETF_OVERSEAS
    elif zf > -6:
        slot1 = S1_ETF_DIVIDEND
    else:
        slot1 = S1_ETF_BOND

    # 仓位2 (20%)：红利低波 > 国债
    if zf > -6:
        slot2 = S1_ETF_DIVIDEND
    else:
        slot2 = S1_ETF_BOND

    # 仓位3 (20%)：黄金（准永久），沪深300+红利低波信号替代
    if macd_gold > 0:
        slot3 = S1_ETF_GOLD
    else:
        slot3 = S1_ETF_GOLD
        if macd_300 > 0 and zf > -6:
            slot3 = S1_ETF_DIVIDEND

    # 仓位4 (30%)：国债
    slot4 = S1_ETF_BOND

    stocks = [slot1, slot2, slot3, slot4]
    base_w = [0.30, 0.20, 0.20, 0.30]
    weights = _hrp_slot_weights(stocks, base_w, HRP_WINDOW, HRP_CASH)
    # 合并同标的权重
    target = defaultdict(float)
    for i in range(4):
        target[stocks[i]] += weights[i]

    total_value = sub.total_value

    # 卖出不在新目标中的持仓
    for s in list(sub.long_positions.keys()):
        if s not in target:
            order_target(s, 0, pindex=pindex)

    # 按目标权重下单
    for ticker, weight in target.items():
        order_target_value(ticker, total_value * weight, pindex=pindex)

    g.s1_stock_fund = stocks


def s1_get_macd_M(stock, check_date):
    """获取月线MACD柱值"""
    macd_dif, macd_dea, macd_macd = MACD(stock, check_date=check_date,
                                          SHORT=12, LONG=26, MID=9,
                                          unit='1M', include_now=False)
    return macd_macd[stock]


def s1_is_year_first_trade(context):
    """判断是否为当年第一个交易日"""
    year = context.current_dt.year
    trade_days = get_trade_days(start_date='%d-01-01' % year, end_date='%d-12-31' % year)
    if len(trade_days) == 0:
        return False
    return context.current_dt.day == trade_days[0].day and context.current_dt.month == 1


def s1_get_zf(context):
    """获取512890（红利低波）年初至今涨跌幅"""
    etf = S1_ETF_DIVIDEND
    year = context.current_dt.year
    start_date_old = datetime.datetime(year - 1, 12, 20).strftime('%Y-%m-%d')
    end_date_old = datetime.datetime(year - 1, 12, 31).strftime('%Y-%m-%d')
    try:
        df_all = attribute_history(etf, 25, '1d', ['close'])
        today_close = df_all.close.iloc[-1]
        df_old = get_price(etf, start_date=start_date_old, end_date=end_date_old,
                           frequency='1d', panel=False)
        if df_old is None or len(df_old) == 0:
            return 0
        old_close = df_old.close.iloc[-1]
        if old_close <= 0:
            return 0
        return round((today_close - old_close) * 100 / old_close, 2)
    except:
        return 0


# =================================================================
# Section 4: 策略2 - 永久投资优化（3资产等权+估值评分+价格触发再平衡）
# =================================================================
# 3资产：纳指ETF、黄金ETF、豆粕ETF
# ±18%价格触发再平衡；再平衡时0分(高估)清仓，1分和2分资产等权买入
# 估值评分：价格/MA250 > 1.30高估(0分)，< 0.70低估(2分)，其他正常(1分)

def s2_trade_logic(context):
    """策略2每日检查：首次建仓 or 价格触发再平衡"""
    pindex = 1
    sub = context.subportfolios[pindex]
    total_value = sub.total_value
    investable = total_value * (1 - g.s2_cash_buffer)

    # 首次建仓/补仓
    missing = [sec for sec in g.s2_risk_assets if sec not in g.s2_last_rebalance_prices]
    if not g.s2_initialized or missing:
        s2_rebalance_default(context, investable)
        for sec in g.s2_risk_assets:
            p = s2_get_usable_price(sec)
            if p:
                g.s2_last_rebalance_prices[sec] = p
        g.s2_initialized = True
        return

    # 价格触发检查：任一资产涨跌超±18%触发再平衡
    trigger = False
    for sec in g.s2_risk_assets:
        base = g.s2_last_rebalance_prices.get(sec)
        cur = s2_get_usable_price(sec)
        if base is None or cur is None:
            continue
        change = (cur - base) / base
        if abs(change) >= g.s2_price_threshold:
            trigger = True
            break

    if trigger:
        g.s2_rebalance_count += 1
        s2_rebalance_with_score(context, investable)
        for sec in g.s2_risk_assets:
            p = s2_get_usable_price(sec)
            if p:
                g.s2_last_rebalance_prices[sec] = p


def s2_get_usable_price(security, max_lookback=5):
    """获取可用价格：实时价优先，无效则回溯最近收盘价"""
    try:
        cd = get_current_data()
        if security in cd:
            price = cd[security].last_price
            if price is not None and not math.isnan(price) and price > 0:
                return price
    except:
        pass
    try:
        df = attribute_history(security, max_lookback, '1d', ['close'], skip_paused=True)
        if df is not None and not df.empty:
            for i in range(len(df) - 1, -1, -1):
                price = df['close'].iloc[i]
                if not math.isnan(price) and price > 0:
                    return price
    except:
        pass
    return None


def s2_get_valuation_score(security):
    """估值评分：0=高估(价格/MA250>1.30), 1=正常, 2=低估(价格/MA250<0.70)"""
    try:
        df = attribute_history(security, g.s2_ma_period, '1d', ['close'], skip_paused=True)
        if df is not None and len(df) == g.s2_ma_period:
            ma = df['close'].mean()
            price = s2_get_usable_price(security)
            if price is None:
                return 1
            ratio = price / ma
            if ratio > g.s2_overvalued_ratio:
                return 0
            elif ratio < g.s2_undervalued_ratio:
                return 2
            else:
                return 1
    except:
        pass
    return 1


def s2_rebalance_default(context, investable):
    """策略2默认等权建仓"""
    pindex = 1
    sub = context.subportfolios[pindex]
    equal_weight = 1.0 / len(g.s2_risk_assets)
    target_per = investable * equal_weight

    # 清理非目标持仓
    for sec in list(sub.long_positions.keys()):
        if sec not in g.s2_risk_assets and sub.long_positions[sec].total_amount > 0:
            order_target(sec, 0, pindex=pindex)

    for sec in g.s2_risk_assets:
        price = s2_get_usable_price(sec)
        if price is None or price <= 0:
            continue
        target_shares = int(target_per / price / 100) * 100
        if target_shares <= 0:
            continue
        order_target(sec, target_shares, pindex=pindex)


def s2_rebalance_with_score(context, investable):
    """策略2估值评分再平衡：0分清仓，1/2分等权"""
    pindex = 1
    sub = context.subportfolios[pindex]

    # 计算评分
    scores = {}
    for sec in g.s2_risk_assets:
        scores[sec] = s2_get_valuation_score(sec)

    # 0分资产清仓
    for sec in g.s2_risk_assets:
        if scores[sec] == 0:
            order_target(sec, 0, pindex=pindex)

    # 保留资产（1分或2分）
    retained = [sec for sec in g.s2_risk_assets if scores[sec] > 0]

    if len(retained) == 0:
        # 全部高估，全仓国债
        for sec in g.s2_risk_assets:
            order_target(sec, 0, pindex=pindex)
        order_target_value(g.s2_bond_etf, investable, pindex=pindex)
        return

    # 清空国债（如有）
    if g.s2_bond_etf in sub.long_positions and sub.long_positions[g.s2_bond_etf].total_amount > 0:
        order_target(g.s2_bond_etf, 0, pindex=pindex)

    # 等权分配
    weight = 1.0 / len(retained)
    for sec in retained:
        target_value = investable * weight
        price = s2_get_usable_price(sec)
        if price is None or price <= 0:
            continue
        target_shares = int(target_value / price / 100) * 100
        if target_shares <= 0:
            continue
        order_target(sec, target_shares, pindex=pindex)


# =================================================================
# Section 5: 策略3 - 全天候策略微调（5仓位MACD+RSI+市场趋势）
# =================================================================
# 5个内部仓位：stock(40%) / hl(0%) / hj(30%) / gz(20%) / xj(10%)
# 使用MACD月线、RSI、市场趋势（MA20/MA60）综合决策
# 每月第1和第15个交易日调仓，每周一监控市场

# 策略3使用的ETF
S3_ETF_MAP = {
    'GW': '513100.XSHG',    # 纳指ETF（海外成长）
    'CZ': '159949.XSHE',    # 创业板50ETF（成长）
    'HL': '512890.XSHG',    # 红利低波ETF（红利）
    'HJ': '518880.XSHG',    # 黄金ETF（黄金）
    'GZ': '511260.XSHG',    # 十年国债ETF（国债）
    'XJ': '511360.XSHG',    # 短融ETF（白皮书E1.2 现金升级；2020-09 前由 511880 收益拼接）
}


def s3_trade_logic(context):
    """策略3月度调仓：5仓位综合配置"""
    pindex = 2
    sub = context.subportfolios[pindex]
    today = context.current_dt
    etf_dict = S3_ETF_MAP

    # MACD月线信号
    macd_gw = s3_get_macd_M(etf_dict['GW'], today)
    macd_cz = s3_get_macd_M(etf_dict['CZ'], today)
    macd_hj = s3_get_macd_M(etf_dict['HJ'], today)
    macd_300 = s3_get_macd_M('000300.XSHG', today)

    # RSI & 年度涨跌幅
    prev_trading_day = context.previous_date
    rsi_hl = s3_get_rsi(etf_dict['HL'], prev_trading_day)
    zf_hl = s3_get_zf(context, etf_dict['HL'])

    # 仓位分配比例
    fc = g.s3_internal_weights
    total_value = sub.total_value

    # --- slot0: stock (40%) ---
    if macd_cz > 0 and rsi_hl < 70:
        slot0_etf = etf_dict['CZ']      # 创业板50
    elif macd_gw > 0 and g.s3_market_trend != 'strong_down':
        slot0_etf = etf_dict['GW']      # 纳指
    elif zf_hl > -8:
        slot0_etf = etf_dict['HL']      # 红利低波
    else:
        slot0_etf = etf_dict['GZ']      # 国债

    # --- slot1: hl (0%) ---
    if zf_hl > -8 or g.s3_market_trend == 'strong_up':
        slot1_etf = etf_dict['HL']
    else:
        slot1_etf = etf_dict['GZ']

    # --- slot2: hj (30%) ---
    if macd_hj > 0 or g.s3_market_status == 'high_volatility':
        slot2_etf = etf_dict['HJ']      # 黄金
    else:
        if macd_300 > 0 and zf_hl > -8:
            slot2_etf = etf_dict['HL']  # 红利低波
        else:
            slot2_etf = etf_dict['HJ']  # 黄金

    # --- slot3: gz (20%) ---
    if g.s3_market_trend == 'strong_down':
        slot3_etf = etf_dict['GZ']      # 国债
    elif rsi_hl < 30:
        slot3_etf = etf_dict['HL']      # 红利低波
    else:
        slot3_etf = etf_dict['GZ']      # 国债

    # --- slot4: xj (10%) ---
    # 定档 E1.2：现金槽 511880 → 511360 短融；_s3_cash_code() 负责「有数据才用」，
    # 上市前（聚宽侧 2020-09-25 之前）自动退回 511880，避免对不存在标的下单后被静默吞掉。
    slot4_etf = _s3_cash_code()

    # 合并同标的权重
    slots = [slot0_etf, slot1_etf, slot2_etf, slot3_etf, slot4_etf]
    slot_weights = _hrp_slot_weights(slots, [fc['stock'], fc['hl'], fc['hj'], fc['gz'], fc['xj']], HRP_WINDOW, HRP_CASH)
    target = defaultdict(float)
    for i in range(5):
        if slot_weights[i] > 0:
            target[slots[i]] += slot_weights[i]

    # 卖出不在新目标的持仓（含止损判断）
    for s in list(sub.long_positions.keys()):
        if s not in target:
            pos = sub.long_positions[s]
            if pos.total_amount > 0:
                order_target(s, 0, pindex=pindex)
        else:
            pass  # 白皮书E3.3：移除单标的 -8%% 硬止损

    # 按目标权重下单
    current_data = get_current_data()
    for etf, w in target.items():
        tv = total_value * w
        if current_data[etf].paused:
            continue
        cur_val = sub.long_positions[etf].value if etf in sub.long_positions and sub.long_positions[etf].total_amount > 0 else 0
        # 定档加固：两参 max() 换成等价条件表达式（数值逐位不变，见上条注释）
        _band = tv * 0.05
        if abs(cur_val - tv) > (500.0 if _band < 500.0 else _band) or cur_val == 0:
            order_target_value(etf, tv, pindex=pindex)


def s3_pre_market(context):
    """策略3年末平仓 & 年初重分配"""
    pindex = 2
    sub = context.subportfolios[pindex]
    today = context.current_dt.date()
    month = today.month

    # 白皮书E1.1：年末暴力清仓已移除（原12月最后交易日全清，徒增摩擦且无读方依赖）
    if False:
        pass


def s3_monitor_market(context):
    """策略3每周市场监控：更新波动率和趋势状态"""
    # 波动率
    hist_data = attribute_history('000300.XSHG', 20, '1d', ['close'])
    returns = hist_data['close'].pct_change().dropna()
    g.s3_volatility = returns.std() * np.sqrt(252) * 100

    if g.s3_volatility > 25:
        g.s3_market_status = 'high_volatility'
    elif g.s3_volatility < 15:
        g.s3_market_status = 'low_volatility'
    else:
        g.s3_market_status = 'neutral'

    # 趋势
    hist_data_long = attribute_history('000300.XSHG', 60, '1d', ['close'])
    ma20 = hist_data['close'].mean()
    ma60 = hist_data_long['close'].mean()
    current_price = hist_data['close'].iloc[-1]

    if current_price > ma20 and ma20 > ma60:
        g.s3_market_trend = 'strong_up'
    elif current_price < ma20 and ma20 < ma60:
        g.s3_market_trend = 'strong_down'
    else:
        g.s3_market_trend = 'sideways'


def s3_get_macd_M(stock, check_date):
    """策略3：获取MACD月线柱值"""
    macd_dif, macd_dea, macd_macd = MACD(stock, check_date=check_date,
                                          SHORT=12, LONG=26, MID=9,
                                          unit='1M', include_now=False)
    return macd_macd[stock]


def s3_get_rsi(stock, check_date):
    """策略3：计算14日RSI"""
    hist_data = get_price(stock, end_date=check_date, count=15, frequency='1d', fields=['close'])
    close_prices = hist_data['close'].values
    if len(close_prices) < 2:
        return 50
    deltas = np.diff(close_prices)
    gain = np.sum(deltas[deltas > 0]) / len(deltas)
    loss = -np.sum(deltas[deltas < 0]) / len(deltas)
    if loss == 0:
        return 100
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def s3_get_zf(context, etf):
    """策略3：计算ETF年初至今涨跌幅"""
    current_year = context.current_dt.year
    last_year_start = datetime.datetime(current_year - 1, 12, 20).strftime('%Y-%m-%d')
    last_year_end = datetime.datetime(current_year - 1, 12, 31).strftime('%Y-%m-%d')
    try:
        price_data = attribute_history(etf, 1, '1d', ['close'])
        previous_close_price = price_data.close.iloc[-1]
        last_year_prices = get_price(etf, start_date=last_year_start, end_date=last_year_end,
                                     frequency='1d', panel=False)
        if len(last_year_prices) == 0:
            last_year_prices = get_price(etf,
                                         start_date=datetime.datetime(current_year - 1, 12, 1).strftime('%Y-%m-%d'),
                                         end_date=last_year_end, frequency='1d', panel=False)
        if len(last_year_prices) == 0:
            return 0
        last_year_close = last_year_prices.close.iloc[-1]
        return round((previous_close_price - last_year_close) * 100 / last_year_close, 2)
    except:
        return 0


# =================================================================
# Section 6: 调度入口函数
# =================================================================

def pre_market_tasks(context):
    """盘前任务：策略3年末/年初处理"""
    s3_pre_market(context)
    update_period_values(context)


def daily_trade(context):
    """每日交易：策略1每日检查 + 策略2每日检查 + 策略1 B模式月度调仓"""
    # 策略1：MA250偏离度检查
    execute_strategy_with_notify(context, 0, s1_trade_logic, '调仓')

    # 策略2：价格触发再平衡检查
    execute_strategy_with_notify(context, 1, s2_trade_logic, '调仓')

    # 策略1 B模式月度调仓（仅月度特定日触发）
    if g.s1_mode == 'B':
        today = context.current_dt.date()
        month_start = datetime.date(today.year, today.month, 1)
        trade_days = get_trade_days(start_date=month_start, end_date=today)
        if len(trade_days) == SCHEDULE['s1_monthly_day']:
            execute_strategy_with_notify(context, 0, s1_rebalance_b, 'B模式月调仓')


def monthly_trade_s3(context):
    """策略3月度调仓（第1/15个交易日触发）"""
    today = context.current_dt.date()
    month_start = datetime.date(today.year, today.month, 1)
    trade_days = get_trade_days(start_date=month_start, end_date=today)
    day_num = len(trade_days)

    if day_num == SCHEDULE['s3_monthly_day1'] or day_num == SCHEDULE['s3_monthly_day2']:
        execute_strategy_with_notify(context, 2, s3_trade_logic, '调仓')


# =================================================================
# Section 7: 初始化
# =================================================================

def initialize(context):
    import sys as _sys
    import numpy as _np
    import pandas as _pd
    log.info("AW_AUDIT variant=永久全天候三合一_HRP_R_NS_权重修复_精简版.py python=%s numpy=%s pandas=%s" % (_sys.version, _np.__version__, _pd.__version__))
    # --- 基础设置 ---
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_benchmark('000300.XSHG')

    # --- 交易成本：滑点0.001%，万1免五 ---
    set_slippage(PriceRelatedSlippage(0.00001))
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.0001, close_commission=0.0001,
        close_today_commission=0, min_commission=0
    ), type='fund')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0001, close_commission=0.0001,
        close_today_commission=0, min_commission=0
    ), type='stock')

    log.set_level('order', 'error')
    log.set_level('system', 'error')

    # --- 设置3个子账户 ---
    initial_cash = context.portfolio.starting_cash
    set_subportfolios([
        SubPortfolioConfig(cash=initial_cash * ALLOCATION_WEIGHTS[i], type='stock')
        for i in range(3)
    ])

    # --- 收益追踪 ---
    g.start_date_str = context.current_dt.strftime('%Y-%m-%d')
    g.initial_values = [initial_cash * ALLOCATION_WEIGHTS[i] for i in range(3)]
    g.year_start_values = [initial_cash * ALLOCATION_WEIGHTS[i] for i in range(3)]
    g.month_start_values = [initial_cash * ALLOCATION_WEIGHTS[i] for i in range(3)]
    g.prev_day_values = [initial_cash * ALLOCATION_WEIGHTS[i] for i in range(3)]
    g.last_recorded_year = context.current_dt.year
    g.last_recorded_month = context.current_dt.month

    # ---- 策略1参数（红利低波全天候）----
    g.s1_etf = '512890.XSHG'          # 红利低波ETF（核心监控标的）
    g.s1_ma_length = 250               # MA均线周期
    g.s1_buy_threshold = 0.985         # 买入阈值（低偏离）
    g.s1_sell_threshold = 1.095        # 卖出阈值（高偏离）
    g.s1_mode = 'A'                    # 初始模式A（持有512890）
    g.s1_stock_fund = []               # B模式持仓记录

    # ---- 策略2参数（永久投资优化）----
    g.s2_risk_assets = [
        '513100.XSHG',  # 纳指ETF
        '518880.XSHG',  # 黄金ETF
        '159985.XSHE',  # 豆粕ETF
    ]
    g.s2_bond_etf = '511260.XSHG'     # 十年国债（全高估时使用）
    g.s2_price_threshold = 0.18        # 价格触发再平衡阈值 ±18%
    g.s2_cash_buffer = 0.0             # 现金缓冲比例
    g.s2_ma_period = 250               # 估值评分MA周期
    g.s2_overvalued_ratio = 1.30       # 高估阈值
    g.s2_undervalued_ratio = 0.70      # 低估阈值
    g.s2_last_rebalance_prices = {}    # 上次再平衡后各资产价格
    g.s2_initialized = False           # 是否已初始化
    g.s2_rebalance_count = 0           # 累计再平衡次数

    # ---- 策略3参数（全天候策略微调）----
    g.s3_internal_weights = {          # 5个内部仓位权重
        'stock': 0.40,
        'hl': 0.00,
        'hj': 0.30,
        'gz': 0.20,
        'xj': 0.10,
    }
    g.s3_market_status = 'neutral'     # 市场波动状态
    g.s3_market_trend = 'neutral'      # 市场趋势
    g.s3_volatility = 0                # 当前年化波动率
    g.s3_year_end_cleared = False      # 年末是否已清仓

    # ========== 调度任务 ==========
    # 盘前：年度处理+更新基准值
    run_daily(pre_market_tasks, time=SCHEDULE['pre_market'])

    # 每日交易：策略1/2 每日检查（含策略1 B模式月度调仓）
    run_daily(daily_trade, time=SCHEDULE['daily_trade'])

    # 月度交易：策略3（每日判断是否为调仓日）
    run_daily(monthly_trade_s3, time=SCHEDULE['monthly_trade'])

    # 每周市场监控：策略3
    run_weekly(s3_monitor_market, SCHEDULE['s3_weekly_day'], time=SCHEDULE['weekly_monitor'])

    # 盘后：每日收盘报告
    run_daily(daily_report, time=SCHEDULE['post_market'])


# ======================= 白皮书 E5：分层风险平价 helper（López de Prado 2016）======================
HRP_WINDOW = 60
HRP_CASH = ['511260.XSHG', '511520.XSHG', '511880.XSHG', '511360.XSHG']


def _hrp_returns(code, window):
    """截至昨日的 window 期日收益（ndarray）。数据不足返回 None。"""
    import numpy as _np
    try:
        df = attribute_history(code, window + 1, '1d', ['close'],
                               skip_paused=True, df=True)
        v = _np.asarray(df['close'], dtype=float)
        if len(v) < window + 1:
            return None
        r = v[1:] / v[:-1] - 1
        if not _np.isfinite(r).all():
            return None
        import pandas as _pd
        _pairs = _pd.MultiIndex.from_arrays([df.index[:-1], df.index[1:]])
        return _pd.Series(r, index=_pairs)
    except Exception:
        return None


def _hrp_seriate(dist):
    """单连接层次聚类 → 叶子序（准对角化）。dist 为 NxN 距离矩阵。"""
    clusters = [[i] for i in range(dist.shape[0])]
    while len(clusters) > 1:
        best, bd = None, None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                d = None
                for _a in clusters[i]:
                    for _b in clusters[j]:
                        _v = dist[_a][_b]
                        if d is None or _v < d:
                            d = _v
                if bd is None or d < bd:
                    best, bd = (i, j), d
        i, j = best
        merged = clusters[i] + clusters[j]
        clusters = [c for k, c in enumerate(clusters) if k not in (i, j)] + [merged]
    return clusters[0]


def _hrp_cluster_var(cov, items):
    """簇内逆方差加权的簇方差。"""
    import numpy as _np
    sub = list(items)
    c = cov[_np.ix_(sub, sub)]
    iv = 1.0 / _np.clip(_np.diag(c), 1e-18, None)
    iv = iv / iv.sum()
    return float(iv @ c @ iv)


def _hrp_bipart(cov, items, weights, scale):
    """递归二分分配：方差小的簇拿更大份额。"""
    import numpy as _np
    if len(items) <= 1:
        if len(items) == 1:
            weights[items[0]] += scale
        return
    half = len(items) // 2
    left, right = items[:half], items[half:]
    vl = _hrp_cluster_var(cov, left)
    vr = _hrp_cluster_var(cov, right)
    alpha = 1.0 - vl / (vl + vr) if (vl + vr) > 0 else 0.5
    _hrp_bipart(cov, left, weights, scale * alpha)
    _hrp_bipart(cov, right, weights, scale * (1.0 - alpha))


def _hrp_weights(free_codes, window):
    """对自由槽位标的做 HRP，返回 {code: weight}（合计 1）。
    任一标的数据不足 → 回退 1/σ；全部不足 → 等权。"""
    import numpy as _np
    # 同一证券只参加一次聚类；槽位层再拆回，避免重复预算。
    unique_codes = []
    for c in free_codes:
        if c not in unique_codes:
            unique_codes.append(c)
    free_codes = unique_codes
    if len(free_codes) == 0:
        return {}
    if len(free_codes) == 1:
        return {free_codes[0]: 1.0}
    rets = {}
    for c in free_codes:
        r = _hrp_returns(c, window)
        if r is not None and float(_np.std(r, ddof=1)) > 0:
            rets[c] = r
    n_all = len(free_codes)
    if not rets:
        return {c: 1.0 / n_all for c in free_codes}
    if len(rets) < n_all:
        # 数据不齐：回退逆波动（与 IV 引擎同口径）
        inv = {}
        for c, r in rets.items():
            s = float(_np.std(r, ddof=1))
            if s > 0:
                inv[c] = 1.0 / s
        if not inv:
            return {c: 1.0 / len(rets) for c in rets}
        tot = 0.0
        for c in inv:
            tot += inv[c]
        return {c: inv[c] / tot for c in inv}
    codes = list(free_codes)
    import pandas as _pd
    aligned = _pd.concat([rets[c] for c in codes], axis=1, join="inner").dropna()
    if len(aligned) < 2:
        inv = {c: 1.0 / float(_np.std(rets[c], ddof=1)) for c in codes}
        total = 0.0
        for c in codes:
            total += inv[c]
        return {c: inv[c] / total for c in codes}
    mat = _np.asarray(aligned, dtype=float)
    corr = _np.corrcoef(mat.T)
    corr = _np.clip(_np.nan_to_num(corr), -1.0, 1.0)
    dist = _np.sqrt(_np.clip(0.5 * (1.0 - corr), 0.0, 1.0))
    cov = _np.cov(mat.T)
    order = _hrp_seriate(dist)
    weights = [0.0] * len(codes)
    _hrp_bipart(cov, order, weights, 1.0)
    return {codes[i]: weights[i] for i in range(len(codes))}


def _hrp_slot_weights(codes, base_weights, window, cash_set):
    """与 _iv_slot_weights 同签名的 HRP 版：现金类/零权重槽位保留原权重，其余按 HRP 瓜分预算。"""
    total = 0.0
    for w in base_weights:
        total += float(w)
    fixed = [i for i, w in enumerate(base_weights) if w > 0 and codes[i] in cash_set]
    # 不用内建 sum()：聚宽里 star import 会把 sum 覆盖成 numpy.sum，而 numpy.sum(生成器)
    # 不能可靠转换 → 下面除它抛 TypeError 又被策略的 try/except 静默吞掉（09-28 IV 版腰斩根因）。
    _fx = 0.0
    for _i in fixed:
        _fx += float(base_weights[_i])
    budget = total - _fx
    free = [i for i, w in enumerate(base_weights) if w > 0 and i not in fixed]
    if not free or budget <= 0:
        return list(base_weights)
    wmap = _hrp_weights([codes[i] for i in free], window)
    out = [0.0] * len(codes)
    for i in fixed:
        out[i] = base_weights[i]
    counts = {}
    for i in free:
        counts[codes[i]] = counts.get(codes[i], 0) + 1
    for i in free:
        out[i] = budget * wmap.get(codes[i], 0.0) / counts[codes[i]]
    return out


# ======================= 定档 E1.2：现金标的选择 =======================
def _s3_cash_code():
    """现金槽用哪个标的：优先 511360 短融 ETF，它没有可用日线就退回 511880 银华日利。

    为什么不用硬编码日期：本地面板对 511360 做了「上市前按 511880 收益拼接」（README §六-4 同款口径），
    所以本地恒返回 511360 → 与 wp 台账逐位一致；聚宽侧在 2020-09-25 上市前取不到 511360 的历史，
    自动落回 511880，经济含义相同（同为现金类），不需要再维护一份日期常量。
    只用 len()/属性访问，不依赖任何内建函数名（聚宽 star import 遮蔽教训）。
    """
    for _c in ('511360.XSHG', '511880.XSHG'):
        try:
            _df = attribute_history(_c, 2, '1d', ['close'], skip_paused=True, df=True)
        except Exception:
            continue
        if _df is not None and len(_df) >= 2:
            return _c
    return '511880.XSHG'
