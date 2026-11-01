# Clone from JoinQuant
# postId: 20cfa178e93511598608a0b56ffc067e
# backtestId: 7e590e63aae941ec2229d98946996440
# title: 朋友们，你们能忍受策略多久不赚钱？

# 克隆自聚宽文章：https://www.joinquant.com/post/63726
# 标题：【策略发布】CSI300_多因子截面策略_低换手
# 作者：Neo_Alice

# coding: utf-8
from jqdata import *
import json
import re
import datetime

# =========================================================
# CSI300 / 模拟盘+回测自适应版本（含关键调试日志）
# 规则：
# - 自动区分回测 vs 模拟盘：
#   若 JSON 的 last_date 是 “today(最近交易日) 的下一交易日” -> 用 last_date（模拟盘/实盘）
#   否则 -> 用 today(最近交易日)（回测）
# - 信号日期缺失：严格空仓（清仓）
# - 保留科创板（688XXX）保护限价下单逻辑
# - 基准：CSI300（000300.XSHG）
# =========================================================

# ========= 全局变量 =========
signal_table = {}         # { 'YYYY-MM-DD': { 'SH600000': {...} 或 0.12, ... }, ... }
next_day_holdings = {}    # 可选：合并进 signal_table，单独保留便于检查
future_rank = {}          # 可选：仅保留参考，不参与交易
all_signal_dates = []     # 所有信号日期（排序后）


# ========= 初始化 =========
def initialize(context):
    set_benchmark('000300.XSHG')          # CSI300
    set_option('use_real_price', True)

    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            min_commission=5
        ),
        type='stock'
    )
    set_slippage(FixedSlippage(0))

    load_signal_table()

    log.info("=== INIT DONE === dt={}, dates_cnt={}, range={}~{}".format(
        context.current_dt,
        len(all_signal_dates),
        all_signal_dates[0] if all_signal_dates else None,
        all_signal_dates[-1] if all_signal_dates else None
    ))

    # 保持 open 以尽量复现你旧回测口径
    run_daily(rebalance, time='09:30')


def handle_data(context, data):
    # 空函数：部分模拟盘环境下更稳（无副作用）
    pass


# ========= 加载信号表 =========
def load_signal_table():
    global signal_table, next_day_holdings, future_rank, all_signal_dates

    content = read_file('signal_table_4.json')  # <<< 你的文件名若是 signal_table_meanreverse.json 请改这里
    raw = json.loads(content)

    next_day_holdings = raw.get('next_day_holdings', {}) or {}
    future_rank = raw.get('future_rank', {}) or {}

    # 主信号：只筛选 YYYY-MM-DD
    main_table = {}
    for k, v in raw.items():
        if isinstance(k, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', k):
            main_table[k] = v

    # 合并 next_day_holdings（若有）
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
        log.warn("signal_table 为空，请检查 JSON 文件格式 / 文件名是否正确")


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
            log.info("prev_trade_day fallback: input={} -> {} (back {} days)".format(date_str, ds, i+1))
            return ds

    log.warn("prev_trade_day fallback failed: input={}, return_self".format(date_str))
    return date_str


# ========= 自动区分回测/模拟盘（强制回测模式） =========
def pick_signal_date_by_gap(context):
    """
    强制仅使用“当前日期对应的最近交易日”作为信号日期。
    修复回测时若 JSON 包含“下一日”数据会导致偷价（读取未来信号）的问题。
    """
    if not all_signal_dates:
        log.warn("pick_signal_date: all_signal_dates empty")
        return None

    today = context.current_dt.strftime('%Y-%m-%d')
    today_td = _prev_trade_day(today)

    log.info("pick_signal_date: Strict Mode -> use today_td={}".format(today_td))
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
    科创板：用 LimitOrderStyle 保护限价，避免“需要保护限价”报错
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

    for raw_code, info in day_info.items():
        if isinstance(info, dict):
            w = float(info.get('weight', 0.0) or 0.0)
        else:
            w = float(info)

        if w <= 0:
            continue

        jq_code = convert_code_to_jq(raw_code)
        if jq_code is None:
            continue

        temp[jq_code] = w
        total += w

    if total <= 0:
        return {}

    # 归一化
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

    use_date = pick_signal_date_by_gap(context)
    target_weights = get_target_weights_for_date(use_date)

    # 输出目标摘要：方便判断是否解析成功
    if target_weights is None:
        log.warn("use_date={} -> target_weights=None (missing date)".format(use_date))
        _clear_all_positions(context, "signal missing for {}".format(use_date))
        return

    log.info("use_date={} -> target_cnt={}, sample={}".format(
        use_date, len(target_weights), list(target_weights.items())[:3]
    ))

    # 严格空仓：空信号或权重全0
    if len(target_weights) == 0:
        _clear_all_positions(context, "empty signal for {}".format(use_date))
        return

    # 计算可用资金：当前可用 + 卖出股票回笼资金
    # 注意：这里预估卖出会成功并全额回款（忽略交易成本的粗略估算）
    cash_to_spend = context.portfolio.available_cash
    
    # 获取当前持仓对象
    current_positions = context.portfolio.positions
    current_stock_list = list(current_positions.keys())
    
    # 1. 卖出不在持股列表的
    sell_cnt = 0
    for stock in current_stock_list:
        if stock not in target_weights:
            # 累加将获得的现金 (Position.value)
            pos = current_positions[stock]
            # 兼容性处理：优先用 value，没有则用 total_amount * price
            pos_val = getattr(pos, 'value', pos.total_amount * pos.price)
            
            cash_to_spend += pos_val
            
            order_target_value_smart(context, stock, 0)
            sell_cnt += 1

    # 2. 用现金等额买入“新增”的股票 (Target - Held)
    # 用户要求：已持有的股票不分配资金，只买新入选的
    target_stock_list = list(target_weights.keys())
    stocks_to_buy = [s for s in target_stock_list if s not in current_positions]
    buy_cnt = 0
    
    if len(stocks_to_buy) > 0 and cash_to_spend > 0:
        # 每一只新买入的金额
        amount_per_stock = cash_to_spend / len(stocks_to_buy)
        
        for stock in stocks_to_buy:
            order_target_value_smart(context, stock, amount_per_stock)
            buy_cnt += 1

    log.info("rebalance done: use_date={}, target_cnt={}, sold_out={}, ordered={}".format(
        use_date, len(target_weights), sell_cnt, buy_cnt
    ))
