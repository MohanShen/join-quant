# Clone from JoinQuant
# postId: 23f077343c62f8c3bcb8d919258c5164
# backtestId: 4d106b4257271bc344660fa327b688ec
# title: 【策略发布】A股日频均值回归_低换手_多因子截面

# coding: utf-8
from jqdata import *
import json
import re
import datetime

# =========================================================
# MeanReversion / 模拟盘+回测自适应（含关键调试日志）
#
# 需求实现：
# 1) 自动区分回测 vs 模拟盘：
#    - 聚宽回测数据通常滞后；你上传的 JSON 往往包含“下一交易日预测持仓”
#    - 若 JSON 的 last_date 是 today(最近交易日) 的“下一交易日”（交易日差=1）
#      -> 用 last_date（模拟盘/实盘按预测持仓调仓，第一天也会建仓）
#    - 否则 -> 用 today(最近交易日)（回测严格历史）
#
# 2) 信号日期缺失：严格空仓 -> 清仓（而不是“不调仓”）
#
# 3) 保留科创板等股票处理（688XXX 保护限价下单）
#
# 4) 含完整关键日志：足够明天模拟盘开盘时 debug
#
# 注意：
# - 文件名默认：signal_table_meanreverse.json
# - 调仓时间默认：open（尽量复现你旧回测口径）
# =========================================================

# ========= 全局变量 =========
signal_table = {}          # { 'YYYY-MM-DD': { 'SH600000': {'weight':..}, ... } 或 float }
next_day_holdings = {}     # 可选：合并进主信号（若文件中存在）
future_rank = {}           # 可选：只保留参考，不参与交易
all_signal_dates = []      # 排序后的日期键列表


# ========= 初始化 =========
def initialize(context):
    set_benchmark('000852.XSHG')          # 中证1000/策略基准保持你原来的
    set_option('use_real_price', True)

    # 费用设置（保持你原来的）
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0003,
            close_commission=0.0003,
            min_commission=5
        ),
        type='stock'
    )

    set_slippage(FixedSlippage(0))

    load_signal_table()

    log.info("=== INIT DONE === dt={}, dates_cnt={}, range={}~{}, last_date={}".format(
        context.current_dt,
        len(all_signal_dates),
        all_signal_dates[0] if all_signal_dates else None,
        all_signal_dates[-1] if all_signal_dates else None,
        all_signal_dates[-1] if all_signal_dates else None
    ))

    # 用 open 保持回测口径接近旧版；模拟盘是否成交稳定你可用限价单技巧增强
    run_daily(rebalance, time='open')


def handle_data(context, data):
    # 空函数：部分模拟盘环境下有助于定时任务被持续驱动（无副作用）
    pass


# ========= 加载信号表 =========
def load_signal_table():
    global signal_table, next_day_holdings, future_rank, all_signal_dates

    content = read_file('signal_table_meanreverse.json')
    raw = json.loads(content)

    next_day_holdings = raw.get('next_day_holdings', {}) or {}
    future_rank = raw.get('future_rank', {}) or {}

    # 只取日期键 YYYY-MM-DD
    main_table = {}
    for k, v in raw.items():
        if isinstance(k, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', k):
            main_table[k] = v

    # 合并 next_day_holdings（如果有）
    if isinstance(next_day_holdings, dict):
        for d, v in next_day_holdings.items():
            if d not in main_table:
                main_table[d] = v

    signal_table = main_table
    all_signal_dates = sorted(signal_table.keys())

    if all_signal_dates:
        log.info("signal_table loaded: dates_cnt={}, first={}, last={}".format(
            len(all_signal_dates), all_signal_dates[0], all_signal_dates[-1]
        ))
    else:
        log.warn("signal_table 为空：请检查 signal_table_meanreverse.json 是否上传成功、文件名是否一致")


# ========= 交易日兜底 =========
def _is_trade_day(date_str):
    try:
        tds = get_trade_days(start_date=date_str, end_date=date_str)
        return tds is not None and len(tds) == 1
    except Exception as e:
        log.warn("_is_trade_day error: date={}, err={}".format(date_str, e))
        return False


def _prev_trade_day(date_str):
    """返回 <= date_str 的最近一个交易日（YYYY-MM-DD）"""
    if _is_trade_day(date_str):
        return date_str

    d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    for i in range(30):
        d = d - datetime.timedelta(days=1)
        ds = d.strftime("%Y-%m-%d")
        if _is_trade_day(ds):
            log.info("prev_trade_day fallback: input={} -> {} (back {} days)".format(date_str, ds, i + 1))
            return ds

    log.warn("prev_trade_day fallback failed: input={}, return_self".format(date_str))
    return date_str


# ========= 自动区分回测/模拟盘（按“下一交易日预测”） =========
def pick_signal_date_by_gap(context):
    """
    - today_td = 当前日期映射到最近交易日（兜底周末/节假日/夜间）
    - last_date = JSON 最后一个日期键
    - 若 last_date 是 today_td 的“下一交易日”（交易日序列长度=2） -> 用 last_date
    - 否则 -> 用 today_td
    """
    if not all_signal_dates:
        log.warn("pick_signal_date: all_signal_dates empty")
        return None

    last_date = all_signal_dates[-1]
    today = context.current_dt.strftime('%Y-%m-%d')
    today_td = _prev_trade_day(today)

    if last_date <= today_td:
        log.info("pick_signal_date: today_td={}, last_date={} (not future) -> use today_td".format(today_td, last_date))
        return today_td

    try:
        tds = get_trade_days(start_date=today_td, end_date=last_date)
        gap = len(tds) if tds is not None else -1
        log.info("pick_signal_date: today_td={}, last_date={}, trade_days_len={}".format(today_td, last_date, gap))
        if tds is not None and len(tds) == 2:
            log.info("pick_signal_date: last_date is next trade day -> use last_date={}".format(last_date))
            return last_date
    except Exception as e:
        log.warn("pick_signal_date error: today_td={}, last_date={}, err={}".format(today_td, last_date, e))

    log.info("pick_signal_date: default -> use today_td={}".format(today_td))
    return today_td


# ========= 代码转换 =========
def convert_code_to_jq(raw_code):
    """SH600000 -> 600000.XSHG ; SZ000001 -> 000001.XSHE"""
    if not isinstance(raw_code, str):
        return None

    s = raw_code.strip().upper()

    if s.endswith('.XSHG') or s.endswith('.XSHE'):
        return s

    if s.startswith('SH') and len(s) >= 8:
        return s[2:] + '.XSHG'
    if s.startswith('SZ') and len(s) >= 8:
        return s[2:] + '.XSHE'

    log.warn("convert_code_to_jq: unrecognized code={}".format(raw_code))
    return None


# ========= 科创板保护限价下单 =========
def is_kechuang(stock):
    """科创板：688XXX.XSHG"""
    return isinstance(stock, str) and stock.startswith('688') and stock.endswith('.XSHG')


def get_ref_price(stock):
    """取最近1日收盘作为参考价"""
    try:
        h = attribute_history(stock, 1, '1d', ['close'], df=False)
        price = h['close'][0]
        if price is None or price <= 0:
            return None
        return price
    except Exception as e:
        log.warn("get_ref_price fail: stock={}, err={}".format(stock, e))
        return None


def order_target_value_smart(context, stock, target_value):
    """
    普通股：直接 order_target_value
    科创板：用 LimitOrderStyle 保护限价，避免“需要保护限价”的报错
    同时打印关键下单回执（None 是最重要的排错信号）
    """
    if not is_kechuang(stock):
        o = order_target_value(stock, target_value)
        if o is None:
            log.warn("order None: stock={}, target_value={:.2f}".format(stock, float(target_value)))
        return

    price = get_ref_price(stock)
    if price is None:
        log.warn("KC skip: stock={}, reason=no_ref_price".format(stock))
        return

    pos = context.portfolio.positions.get(stock, None)
    cur_amount = pos.total_amount if pos is not None else 0
    cur_value = cur_amount * price

    protect_price = price * (1.02 if target_value > cur_value else 0.98)
    protect_price = max(min(protect_price, 9999), 0.01)

    o = order_target_value(stock, target_value, style=LimitOrderStyle(protect_price))
    if o is None:
        log.warn("KC order None: stock={}, target_value={:.2f}, protect_price={:.3f}".format(
            stock, float(target_value), float(protect_price)
        ))


# ========= 权重解析 =========
def get_target_weights_for_date(date_str):
    """
    返回：
      - None：日期不在 signal_table（信号缺失）
      - {}：日期存在但总权重<=0（空仓信号）
      - {jq_code: w}：归一化目标权重
    """
    if not date_str:
        return None

    if date_str not in signal_table:
        return None

    day_info = signal_table[date_str] or {}
    temp = {}
    total = 0.0
    bad_code_cnt = 0

    for raw_code, info in day_info.items():
        # info 可能是 dict 或 float
        if isinstance(info, dict):
            w = float(info.get('weight', 0.0) or 0.0)
        else:
            try:
                w = float(info)
            except:
                w = 0.0

        if w <= 0:
            continue

        jq_code = convert_code_to_jq(raw_code)
        if jq_code is None:
            bad_code_cnt += 1
            continue

        temp[jq_code] = w
        total += w

    log.info("parse_target: date={}, raw_cnt={}, parsed_cnt={}, bad_code_cnt={}, total_w={:.6f}".format(
        date_str, len(day_info), len(temp), bad_code_cnt, total
    ))

    if total <= 0:
        return {}

    return {c: w / total for c, w in temp.items()}


# ========= 清仓辅助 =========
def _clear_all_positions(context, reason):
    if len(context.portfolio.positions) == 0:
        log.info("{}: already empty, skip clear".format(reason))
        return

    log.info("{}: clearing all positions, cnt={}".format(reason, len(context.portfolio.positions)))
    for stock in list(context.portfolio.positions.keys()):
        order_target_value_smart(context, stock, 0)


# ========= 调仓（核心） =========
def rebalance(context):
    if not signal_table or not all_signal_dates:
        log.warn("rebalance: signal_table empty -> return")
        return

    log.info("=== rebalance fired === dt={}".format(context.current_dt))
    log.info("portfolio snapshot: pos_cnt={}, cash={:.2f}, total_value={:.2f}".format(
        len(context.portfolio.positions),
        context.portfolio.available_cash,
        context.portfolio.total_value
    ))

    # 每次调仓前可选：若你会在盘后更新文件，模拟盘第二天自动生效可以打开
    # load_signal_table()

    use_date = pick_signal_date_by_gap(context)
    log.info("rebalance: selected use_date={}".format(use_date))

    target_weights = get_target_weights_for_date(use_date)

    # 信号缺失：严格空仓 -> 清仓
    if target_weights is None:
        log.warn("use_date={} -> target_weights=None (missing date)".format(use_date))
        _clear_all_positions(context, "signal missing for {}".format(use_date))
        return

    # 目标摘要：方便判断解析是否正常
    log.info("use_date={} -> target_cnt={}, sample={}".format(
        use_date, len(target_weights), list(target_weights.items())[:3]
    ))

    # 空仓信号：清仓
    if len(target_weights) == 0:
        _clear_all_positions(context, "empty signal for {}".format(use_date))
        return

    total_value = context.portfolio.total_value

    # 清仓不在目标中的股票
    current_positions = list(context.portfolio.positions.keys())
    sell_cnt = 0
    for stock in current_positions:
        if stock not in target_weights:
            order_target_value_smart(context, stock, 0)
            sell_cnt += 1

    # 建仓/调仓（下单回执在 order_target_value_smart 内）
    order_cnt = 0
    for stock, w in target_weights.items():
        order_target_value_smart(context, stock, total_value * w)
        order_cnt += 1

    log.info("rebalance done: use_date={}, target_cnt={}, sold_out={}, ordered={}".format(
        use_date, len(target_weights), sell_cnt, order_cnt
    ))
