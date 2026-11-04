# Clone from JoinQuant
# postId: 8a35249a271537b9e9afb9b3df184335
# backtestId: f1226782484cceef03a60cf1fa320563
# title: 金纳油三选一（ETF策略复现之七）

# -*- coding: utf-8 -*-
# =============================================================================
#  ETF组合宝「轮动策略」—— 聚宽（JoinQuant）复现版
# =============================================================================
#  【原始平台配置】ETF组合宝 App - 轮动策略（截图见项目目录）
#  ---------------------------------------------------------------------------
#   候选轮动池 ：纳指ETF国泰 513100 / 标普油气 159518 / 黄金ETF华安 518880
#                （v1.2：按用户要求把原 160723 嘉实原油LOF 替换为 159518 标普油气）
#   排序指标   ：3-30均线 = (均线(3) - 均线(30)) / 均线(30)，排序方式 大→小，权重 1
#   买入规则   ：[全部匹配] 涨幅(3)<0.05  且  涨幅(5)>0.01  且  乖离率(60)<8
#   卖出规则   ：[自定义匹配] (涨幅(1)>0.06  或  乖离率(60)>15)  且  持有天数>2
#   轮动设置   ：轮动周期 1 个交易日；最大持仓数量 1；持仓比例 固定；替代资产 无
#   回测设置   ：对比基准 纳指ETF国泰 513100；起始/结束时间 不限
#  ---------------------------------------------------------------------------
#  【交易时序】与平台“次日开盘成交”一致
#   T 日收盘后（T+1 日开盘前 before_trading_start）用截至 T 日收盘的数据计算信号，
#   T+1 日 09:30（run_daily）以开盘价挂市价单执行。
#  ---------------------------------------------------------------------------
#  【指标定义】（日线、收盘价、前复权）
#   涨幅(N)    = close[T] / close[T-N] - 1
#   乖离率(60) = (close[T] - MA60) / MA60 * 100（单位：%）
#   均线(N)    = 最近 N 个交易日收盘价的简单移动平均
#   3-30均线   = (MA3 - MA30) / MA30（与 MA3/MA30-1 排序等价）
#  ---------------------------------------------------------------------------
#  【聚宽使用步骤】
#   1. 聚宽 - 策略研究 - 回测 - 新建策略，将本文件全部内容粘贴到代码编辑区；
#   2. 回测频率选择“每天”，起始时间建议 2024-03-01 之后（159518 于 2023-11-15 上市，
#      凑满 60 根日线约到 2024 年 2 月下旬；513100/518880 数据更早），基准建议 513100.XSHG；
#   3. 初始资金建议先用 10 万~50 万元；159518 为 QDII ETF、518880 为商品 ETF，流动性与溢价差异大，
#      请先用近 20 日成交额验证容量：单笔订单 ≤ 日均成交额 5%~10%，超出则拆单/限价/VWAP；
#      （旧池 160723 曾因流动性极差导致 98% 仓位多次只成交 9%~50%，新标的必须重新做容量测试）
#   4. 点击“开始回测”/“模拟运行”即可。
#   （本文件按“每天”频率设计；分钟频率回测也能运行，但无必要。）
#  ---------------------------------------------------------------------------
#  【v1.1 修订】根据 2014-07~2026-09 真实聚宽回测（transaction/position/log）诊断：
#   - 修复“部分成交被当成完全成交”导致同日买入新标的、持仓超过 max_hold、漏掉残仓顺延；
#   - 修复 positions.get() 触发的聚宽兼容性告警刷屏（原占日志 66%）；
#   - 新增可选防抖参数 g.rotation_min_hold_days（默认 0=平台原逻辑），可抑制“今买明卖”。
#  【v1.2 修订】按用户要求：
#   - 候选池 160723 嘉实原油LOF → 159518 标普油气（嘉实标普石油天然气上游 ETF，2023-11-15 上市）；
#   - 日志为每只标的新增全部指标明细（收盘/MA3/MA30/3-30均线/涨幅1/3/5/MA60/乖离率60/排名），
#     并为持仓输出 [持有] 行（建仓日/已持有交易日数），便于逐日核对；
#   - v1.1 的真实回测诊断基于旧池 160723，换池后仅作换手/容量/防抖参数参考，需重新回测。
#  【v2.0 修订】按用户提供的参考代码模板统一代码风格与日志格式：
#   - 逻辑与参数 100% 沿用 v1.2（候选池、3-30均线排序、买卖规则、最大持仓1、固定比例、
#     次日开盘执行、费用/滑点、防抖参数等均未改动）；
#   - 新增表格化日志：每日【指标总览】表格（含全部指标）、【排名与买入校验】、【持仓与卖出判断明细】、
#     【买入计划明细】、【开盘执行明细】、【组合状态】；
#   - 新增 _get_display_width / _format_table 等日志工具函数，统一使用 f-string，风格对齐参考代码；
#   - 保留 v1.1/v1.2 全部健壮性逻辑（信号新鲜度、部分成交/撤单校验、pending 顺延、数据异常保护等）。
# =============================================================================

from jqdata import *
import datetime
import numpy as np
import pandas as pd


# =============================================================================
#  一、初始化与参数
# =============================================================================
def initialize(context):
    _setup_params(context)        # 策略参数（与 ETF组合宝 配置一一对应）
    _setup_environment(context)   # 聚宽环境：基准、复权、费用、滑点
    _reset_runtime_state(context) # 运行时状态
    # ========== ✨ 启动参数完整打印（v2.0：对齐参考模板） ==========
    log.info('=' * 65)
    log.info('  策略初始化完成 | 配置参数核对（v2.0）')
    log.info('=' * 65)
    log.info(f"每日执行时间：{g.exec_time}（T日收盘后生成信号，T+1日开盘以开盘价执行）")
    log.info(f"对比基准：{g.benchmark}")
    log.info(f"交易标的池（共{len(g.pool)}只）：")
    for code in g.pool:
        try:
            info = get_security_info(code)
            name = info.display_name if info else '标的无效'
        except Exception:
            name = g.sec_name.get(code, code)
        log.info(f"  · {code}  {name}")
    log.info(f"指标周期：取数{g.history_count}天 / 排序均线{g.rank_fast_ma}日与{g.rank_slow_ma}日 / 乖离率{g.bias_window}日")
    log.info(f"排序条件：3-30均线=({g.rank_fast_ma}日均线-{g.rank_slow_ma}日均线)/{g.rank_slow_ma}日均线，降序取前{g.max_hold_num}名")
    bp, sp = g.buy_params, g.sell_params
    log.info(f"买入条件：涨幅(3) < {bp['ret3_lt'] * 100:.2f}% 且 涨幅(5) > {bp['ret5_gt'] * 100:.2f}% 且 乖离率({g.bias_window}) < {bp['bias60_lt']:.1f}%")
    log.info(f"卖出条件：(涨幅(1) > {sp['ret1_gt'] * 100:.2f}% 或 乖离率({g.bias_window}) > {sp['bias60_gt']:.1f}%) 且 持有天数 > {sp['hold_days_gt']}")
    log.info(f"轮动设置：周期{g.rotation_days}个交易日 / 最大持仓{g.max_hold_num}只 / 持仓比例固定 / 替代资产无")
    log.info(f"换手防抖：轮动卖出最小持有{g.rotation_min_hold_days}个交易日（0=平台原逻辑）")
    log.info(f"交易成本：滑点千1（双边约0.10%）/ 佣金万三（最低0.1元）/ 无印花税")
    log.info(f"资金使用：买入使用可用资金的{g.buy_cash_buffer * 100:.1f}%，单标的目标=总资产/{g.max_hold_num}")
    log.info('=' * 65 + '\n')

    # 启动策略每日运行
    run_daily(open_execute, time=g.exec_time)   # 每交易日 g.exec_time（默认 09:30）执行


def process_initialize(context):
    # 模拟交易中策略进程每天重启后会调用本函数（initialize 只在首次启动时调用）。
    # 这里重新写入参数并幂等重设环境；持仓/资金以账户实际状态为准。
    _setup_params(context)
    _setup_environment(context)
    for name, val in (('entry_date', {}), ('top_set', []), ('ranked', []),
                      ('signal', None), ('_warned_no_entry', set()), ('_data_checked', False),
                      ('pending_sells', {})):
        if not hasattr(g, name):
            setattr(g, name, val)
    g.signal = None     # 重启后旧信号作废，等当日盘前重新生成
    # 用实际持仓的建仓时间恢复建仓日期记录（用于“持有天数>2”的卖出规则）
    try:
        for sec in _held_secs(context):
            pos = _position_of(context, sec)
            init_time = getattr(pos, 'init_time', None) if pos is not None else None
            entry = _to_date(init_time) if init_time is not None else None
            if entry is not None:
                g.entry_date[sec] = entry
    except Exception:
        pass
    log.info('process_initialize：策略参数已恢复（持仓以账户实际为准）')


def _setup_params(context):
    # ---------------- 候选轮动池（对应“候选轮动池”） ----------------
    # v1.2：按用户要求把 160723 嘉实原油LOF 替换为 159518 标普油气（深交所 QDII ETF）
    g.pool = ['513100.XSHG', '159518.XSHE', '518880.XSHG']
    g.sec_name = {
        '513100.XSHG': '纳指ETF国泰',
        '159518.XSHE': '标普油气',
        '518880.XSHG': '黄金ETF华安',
    }
    g.benchmark = '513100.XSHG'          # 对比基准：纳指ETF国泰

    # ---------------- 排序指标：3-30均线（对应“排序指标”） ----------------
    g.rank_fast_ma = 3                   # 均线(3)
    g.rank_slow_ma = 30                  # 均线(30)
    g.bias_window = 60                   # 乖离率窗口：乖离率(60)
    # 排序公式：(MA3 - MA30) / MA30，降序（大→小）；单指标，权重 1

    # ---------------- 买入规则（对应“买入规则”，匹配方式=全部匹配） ----------------
    g.buy_params = {
        'ret3_lt': 0.05,     # 涨幅(3) 小于 0.05（小数口径，即 5%）
        'ret5_gt': 0.01,     # 涨幅(5) 大于 0.01（即 1%）
        'bias60_lt': 8.0,    # 乖离率(60) 小于 8（单位：%，与平台显示一致）
    }

    # ---------------- 卖出规则（对应“卖出规则”，自定义匹配 (1or2)and3） ----------------
    g.sell_params = {
        'ret1_gt': 0.06,     # 涨幅(1) 大于 0.06（即 6%）
        'bias60_gt': 15.0,   # 乖离率(60) 大于 15（单位：%）
        'hold_days_gt': 2,   # 持有天数 大于 2（交易日，买入成交日算第 0 天）
    }

    # ---------------- 轮动设置（对应“轮动设置”） ----------------
    g.rotation_days = 1                  # 轮动周期：1 个交易日
    g.rotation_anchor = '2017-01-01'     # 轮动周期>1 时计算轮动日的锚点（无状态，重启不丢）
    g.max_hold_num = 1                   # 最大持仓数量：1
    g.position_mode = 'fixed'            # 持仓比例：'fixed' 固定 / 'adaptive' 自适应
    g.substitute = None                  # 替代资产：无（空出的仓位保留现金）

    # ---------------- 运行参数 ----------------
    g.min_bars = max(int(g.bias_window), int(g.rank_slow_ma))  # 最少需要的交易日数
    g.history_count = g.min_bars + 20            # 每次获取的历史收盘价根数
    g.hold_days_include_entry_day = False        # 持有天数是否含买入当日；False=买入日算第0天
    # 轮动卖出的最小持有交易日数：0 = 平台原逻辑（跌出排序即次日开盘卖，可能出现“今买明卖”）；
    # 设为 1 可消除一日往返（真实回测 17 笔一日往返合计亏 7.47 万且白付摩擦），设为 2 更保守。
    g.rotation_min_hold_days = 0
    g.buy_cash_buffer = 0.98                     # 买入资金预留（覆盖隔夜跳空/佣金/滑点/整手误差）
    g.exec_time = '09:30'                        # 每日执行时间；模拟盘若因成交量不足被拒单可改 '09:31'
    g.verbose = True                             # 是否输出每日信号日志


def _setup_environment(context):
    # 基准：纳指ETF国泰（ETF 可作为聚宽基准；若失败退化为沪深300并在日志中说明）
    try:
        set_benchmark(g.benchmark)
    except Exception as e:
        log.error('基准 %s 设置失败(%r)，改用 000300.XSHG，回测对比口径将改变！' % (g.benchmark, e))
        set_benchmark('000300.XSHG')
    try:
        set_option('use_real_price', True)      # 真实价格成交（动态复权）
    except Exception:
        pass
    try:
        set_option('avoid_future_data', True)   # 避免未来数据（模拟盘尤其重要）
    except Exception:
        pass
    # 场内基金（ETF/LOF）：无印花税；佣金按万三、最低 0.1 元估算（可按自己券商改成 5 等）
    cost = OrderCost(open_tax=0, close_tax=0,
                     open_commission=0.0003, close_commission=0.0003,
                     close_today_commission=0, min_commission=0.1)
    for tp in ('fund', 'stock'):
        try:
            set_order_cost(cost, type=tp)       # ETF/LOF 属于场内基金，type='fund'
        except Exception:
            pass
    try:
        set_slippage(PriceRelatedSlippage(0.001))   # 双边约千分之一，单边约万分之五
    except Exception:
        try:
            set_slippage(FixedSlippage(0.001))
        except Exception:
            pass
    try:
        log.set_level('order', 'info')          # 保留聚宽下单日志（缩量/拒单 warning 可见）
    except Exception:
        pass


def _reset_runtime_state(context):
    g.entry_date = {}        # 建仓日期记录（辅助；持有天数优先使用持仓的 init_time）
    g.top_set = []           # 最近一次轮动日排序前 max_hold_num 名
    g.ranked = []            # 最近一次轮动日完整排序
    g.signal = None          # 当日待执行信号
    g.pending_sells = {}     # 已发出但未成交的卖出委托（停牌/跌停顺延用）
    g._warned_no_entry = set()   # 已提示过“无法确定建仓日”的标的
    g._data_checked = False      # 是否已输出过行情字段自检
    g._sec_start = {}            # 标的上市日期缓存


# =============================================================================
#  二、每日盘前：生成信号（T 日收盘数据 -> T+1 开盘执行）
# =============================================================================
def before_trading_start(context):
    g.signal = None      # 先清空，避免异常时执行旧信号
    try:
        _make_signal(context)
    except Exception as e:
        log.error('[信号] 生成失败：%r' % (e,))


def _make_signal(context):
    eval_date = _get_previous_trade_date(context)   # 信号使用的数据截止日（上一交易日）
    if eval_date is None:
        log.error('[信号] 无法确定上一交易日，今日不交易')
        return
    do_rotate = _is_rotation_day(eval_date)         # 是否轮动日
    held = _held_secs(context)
    if not hasattr(g, 'pending_sells'):
        g.pending_sells = {}

    # 清理已卖出标的的建仓日期记录与待成交卖出记录
    for sec in list(g.entry_date.keys()):
        if sec not in held:
            g.entry_date.pop(sec, None)
    for sec in list(g.pending_sells.keys()):
        if sec not in held:
            g.pending_sells.pop(sec, None)

    # 计算三只候选资产的指标（只使用截至 eval_date 的收盘价，无未来数据）
    metrics = {}
    for sec in g.pool:
        m = _calc_metrics(sec, eval_date)
        if m is not None:
            metrics[sec] = m
    if not metrics:
        # 三只标的同时取不到有效数据：当日不交易，避免把持仓误判为“跌出排序”而清仓
        log.error('[信号] 三只标的均无有效数据，今日不交易（避免误清仓）')
        return

    # 轮动日：按 3-30均线 由大到小排序，取前 max_hold_num 名（满足排序条件）
    # 并列时保持候选池顺序（Python sorted 稳定，dict 按 g.pool 顺序插入）
    if do_rotate:
        g.ranked = sorted(metrics.keys(), key=lambda s: metrics[s]['rank'], reverse=True)
        g.top_set = list(g.ranked[:int(g.max_hold_num)])

    # ---------------- 卖出判断 ----------------
    sells, keeps, sell_reasons = [], [], {}
    for sec in held:
        reasons = []
        m = metrics.get(sec)
        hold_days = _hold_days(context, sec, eval_date)

        if m is not None:
            # 评估日有最新数据：以当日新信号为准，作废历史“待成交卖出”记录
            g.pending_sells.pop(sec, None)
        elif sec in g.pending_sells:
            # 评估日无有效数据（停牌/数据缺失）：不产生新卖出信号；但此前已发出但未成交的
            # 卖出（停牌/跌停导致）继续顺延到下一个可成交日
            reasons.append('顺延卖出（评估日无有效数据）')

        # 规则A（轮动）：轮动日未进入排序前 N 名且当前持有 -> 次日开盘卖出
        #   注意：按 ETF组合宝 逻辑说明，轮动卖出不受“持有天数”限制；
        #   若评估日该标的无有效数据（停牌/数据缺失，m is None），当日不做轮动卖出判断，继续持有。
        if do_rotate and m is not None and sec not in g.top_set:
            min_hold = int(getattr(g, 'rotation_min_hold_days', 0) or 0)
            if hold_days >= min_hold:
                reasons.append('未进入排序前%d名' % int(g.max_hold_num))
            # 否则：持有不足最小轮动天数，暂不卖出（防抖参数，默认 0 等于平台原逻辑）

        # 规则B（卖出规则）：(涨幅(1)>阈值 或 乖离率(60)>阈值) 且 持有天数>阈值
        if m is not None and _sell_rules_hit(m, hold_days):
            if m['ret1'] > g.sell_params['ret1_gt']:
                reasons.append('涨幅(1)=%.2f%%>%.2f%%' % (
                    m['ret1'] * 100.0, g.sell_params['ret1_gt'] * 100.0))
            if m['bias60'] > g.sell_params['bias60_gt']:
                reasons.append('乖离率(60)=%.2f>%.2f' % (
                    m['bias60'], g.sell_params['bias60_gt']))
            reasons.append('持有%d个交易日>%d' % (hold_days, g.sell_params['hold_days_gt']))

        if reasons:
            sells.append(sec)
            sell_reasons[sec] = '；'.join(reasons)
        else:
            keeps.append(sec)

    # ---------------- 买入判断（仅在轮动日；已持有的资产不再检查买入规则） ----------------
    buys = []
    if do_rotate:
        free_slots = max(int(g.max_hold_num) - len(keeps), 0)
        for sec in g.top_set:
            if len(buys) >= free_slots:
                break
            if sec in held:
                continue
            m = metrics.get(sec)
            if m is None:
                continue
            if _buy_rules_pass(m):
                buys.append(sec)

    g.signal = {
        'eval_date': eval_date,
        'do_rotate': do_rotate,
        'held': held,
        'metrics': metrics,
        'ranked': list(g.ranked),
        'top_set': list(g.top_set),
        'sells': sells,
        'keeps': keeps,
        'buys': buys,
        'sell_reasons': sell_reasons,
    }
    _log_signal(context, g.signal)


def _calc_metrics(sec, eval_date):
    """计算单只资产截至 eval_date 的指标；历史不足/停牌等正常情况返回 None。"""
    s = _get_close_series(sec, eval_date)
    if s is None or len(s) < g.min_bars:
        return None
    # 最新一根 K 线必须是上一交易日，否则视为停牌/无有效数据，当日不参与排序与买卖判断
    if _to_date(s.index[-1]) != eval_date:
        return None
    closes = np.asarray(s.values, dtype=float)
    ma_fast = float(np.mean(closes[-int(g.rank_fast_ma):]))
    ma_slow = float(np.mean(closes[-int(g.rank_slow_ma):]))
    rank_val = (ma_fast - ma_slow) / ma_slow if ma_slow > 0 else -1e9
    ret1 = float(closes[-1] / closes[-2] - 1.0)
    ret3 = float(closes[-1] / closes[-4] - 1.0)
    ret5 = float(closes[-1] / closes[-6] - 1.0)
    ma_bias = float(np.mean(closes[-int(g.bias_window):]))
    bias = float((closes[-1] - ma_bias) / ma_bias * 100.0) if ma_bias > 0 else 0.0
    return {
        'sec': sec,
        'close': float(closes[-1]),
        'ma_fast': ma_fast,
        'ma_slow': ma_slow,
        'rank': rank_val,
        'ret1': ret1,
        'ret3': ret3,
        'ret5': ret5,
        'ma_bias': ma_bias,
        'bias60': bias,      # 乖离率（百分数数值；窗口为 g.bias_window）
    }


def _buy_rules_pass(m):
    """买入规则（全部匹配）：涨幅(3)<0.05 且 涨幅(5)>0.01 且 乖离率(60)<8。"""
    p = g.buy_params
    return (m['ret3'] < p['ret3_lt']) and \
           (m['ret5'] > p['ret5_gt']) and \
           (m['bias60'] < p['bias60_lt'])


def _sell_rules_hit(m, hold_days):
    """卖出规则： (涨幅(1)>0.06 或 乖离率(60)>15) 且 持有天数>2。"""
    p = g.sell_params
    r1 = m['ret1'] > p['ret1_gt']
    r2 = m['bias60'] > p['bias60_gt']
    r3 = hold_days > p['hold_days_gt']
    return (r1 or r2) and r3


# =============================================================================
#  三、每日开盘：执行交易（T+1 日 09:30，以开盘价成交）
# =============================================================================
def _fmt_indicator(m):
    """把单只标的的指标格式化为一行文本，供买入/卖出日志附带（便于复盘）。"""
    if not m:
        return '指标=无有效数据'
    return ('3-30均线=%.5f 涨幅1=%.2f%% 涨幅3=%.2f%% 涨幅5=%.2f%% 乖离率%d=%.2f%%' % (
        m['rank'], m['ret1'] * 100.0, m['ret3'] * 100.0, m['ret5'] * 100.0,
        int(g.bias_window), m['bias60']))


def _log_execution_status(context):
    """输出执行后的组合状态（v2.0 日志格式）。"""
    try:
        held = _held_secs(context)
        names = [g.sec_name.get(s, s) for s in held]
        log.info(f"  组合状态：总资产 {context.portfolio.total_value:.2f}元 | 可用资金 {context.portfolio.available_cash:.2f}元 | 持仓：{', '.join(names) if names else '空仓'}")
        log.info('-' * 75)
    except Exception:
        pass


def open_execute(context):
    try:
        _open_execute(context)
    except Exception as e:
        log.error('[执行] 开盘交易异常：%r' % (e,))
    finally:
        g.signal = None      # 当日信号只执行一次，避免重启/异常重跑时重复下单


def _open_execute(context):
    sig = getattr(g, 'signal', None)
    if not sig:
        return
    if not hasattr(g, 'pending_sells'):
        g.pending_sells = {}
    # 信号新鲜度校验：只执行“上一交易日收盘后生成、今日开盘执行”的信号
    prev = _get_previous_trade_date(context)
    if prev is None or sig.get('eval_date') != prev:
        log.warning('[执行] 信号日期(%s)与上一交易日(%s)不一致，丢弃过期信号' % (
            sig.get('eval_date'), prev))
        return
    today = _to_date(context.current_dt)
    cur = get_current_data()

    log.info('=' * 75)
    log.info(f"  开盘执行明细 | {today} {context.current_dt.strftime('%H:%M')} | 信号日：{sig['eval_date']}")
    log.info('=' * 75)

    # 首次运行时输出行情字段，便于核对 last_price / day_open / 涨跌停价（可保留）
    if not getattr(g, '_data_checked', False):
        g._data_checked = True
        for _sec in g.pool:
            try:
                _cd = cur[_sec]
                log.info('[行情自检] %s last_price=%s day_open=%s 涨停=%s 跌停=%s 停牌=%s' % (
                    g.sec_name.get(_sec, _sec), getattr(_cd, 'last_price', None),
                    getattr(_cd, 'day_open', None), getattr(_cd, 'high_limit', None),
                    getattr(_cd, 'low_limit', None), getattr(_cd, 'paused', None)))
            except Exception:
                pass

    # ---------------- 1) 先卖出（释放资金；卖单先于买单发出） ----------------
    sold_ok = set()
    for sec in sig.get('sells', []):
        pos = _position_of(context, sec)
        if pos is None:
            continue
        name = g.sec_name.get(sec, sec)
        reason = sig.get('sell_reasons', {}).get(sec, '')
        try:
            cd = cur[sec]
        except Exception:
            g.pending_sells[sec] = reason
            log.warning('[卖出跳过] %s %s 无行情数据（顺延）' % (today, name))
            continue
        if _is_paused(cd):
            g.pending_sells[sec] = reason
            log.warning('[卖出跳过] %s %s 今日停牌（顺延）' % (today, name))
            continue
        price = _current_price(cd)
        if price is None:
            g.pending_sells[sec] = reason
            log.warning('[卖出跳过] %s %s 无有效价格（顺延）' % (today, name))
            continue
        low = _num_attr(cd, 'low_limit')
        if low is not None and price <= low + 1e-9:
            g.pending_sells[sec] = reason
            log.warning('[卖出跳过] %s %s 跌停(%.4f)（顺延）' % (today, name, price))
            continue
        amount = int(pos.total_amount)
        ret = order_target(sec, 0)      # 清仓（自动处理零股）
        if ret is None:
            g.pending_sells[sec] = reason
            log.warning('[卖出失败] %s %s 下单被拒或未成交（停牌/涨跌停/成交量不足，顺延）' % (today, name))
            continue
        # 聚宽在“当日成交量限制”下可能只成交一部分（部成部撤）但仍返回非 None 订单。
        # 必须以实际持仓为准核对：否则会误以为已清仓，既可能同日买入新标的造成超过
        # max_hold 的持仓，也会漏掉剩余仓位的顺延卖出/重复卖出。
        pos_after = _position_of(context, sec)
        if pos_after is not None:
            g.pending_sells[sec] = reason
            log.warning('[卖出未完成] %s %s 委托%d股，剩余%d股未成交（成交量限制/停牌），顺延' % (
                today, name, amount, int(pos_after.total_amount)))
            continue
        g.pending_sells.pop(sec, None)
        sold_ok.add(sec)
        log.info(f"  卖出 {name}（{sec}） | 数量：{amount}股 | 参考价：{price:.4f} | 原因：{reason} | {_fmt_indicator(sig.get('metrics', {}).get(sec))}")

    # ---------------- 2) 读取买入可用资金 ----------------
    # 聚宽回测/模拟的市价单同步撮合，卖出回款当天可用于买入；未成交的卖单资金不计入。
    cash_avail = context.portfolio.available_cash

    # ---------------- 3) 再买入（固定比例：每个仓位 = 总资产 / 最大持仓数量） ----------------
    held_now = [s for s in _held_secs(context) if s not in sold_ok]
    buys = [s for s in sig.get('buys', [])
            if (s not in held_now) and (_position_of(context, s) is None)]
    max_new = max(int(g.max_hold_num) - len(held_now), 0)
    if max_new <= 0:
        _log_execution_status(context)
        return
    buys = buys[:max_new]                   # 买入数量不得超过最大持仓数量
    if not buys:
        _log_execution_status(context)
        return
    total_value = context.portfolio.total_value
    if g.position_mode == 'adaptive':
        n_slots = len(held_now) + len(buys)       # 自适应：按实际持有资产数平均
    else:
        n_slots = int(g.max_hold_num)             # 固定：按最大持仓数量平均
    n_slots = max(int(n_slots), 1)
    slot_value = total_value / n_slots

    for sec in buys:
        if _position_of(context, sec) is not None:
            continue
        name = g.sec_name.get(sec, sec)
        try:
            cd = cur[sec]
        except Exception:
            log.warning('[买入跳过] %s %s 无行情数据' % (today, name))
            continue
        if _is_paused(cd):
            log.warning('[买入跳过] %s %s 今日停牌' % (today, name))
            continue
        price = _current_price(cd)
        if price is None:
            log.warning('[买入跳过] %s %s 无有效价格' % (today, name))
            continue
        high = _num_attr(cd, 'high_limit')
        if high is not None and price >= high - 1e-9:
            log.warning('[买入跳过] %s %s 涨停(%.4f)，无法买入' % (today, name, price))
            continue
        alloc = min(slot_value, cash_avail)
        amount = int(alloc * g.buy_cash_buffer / price / 100.0) * 100
        if amount <= 0:
            log.warning('[买入跳过] %s %s 可用资金不足(%.2f)' % (today, name, alloc))
            continue
        ret = order(sec, amount)        # 市价买入，100 份整数倍
        pos_after = _position_of(context, sec)
        if ret is None or pos_after is None:
            log.warning('[买入失败] %s %s 下单被拒或未成交（资金/涨跌停/成交量不足）' % (today, name))
            continue
        filled = int(getattr(pos_after, 'total_amount', 0))
        g.entry_date[sec] = today
        cash_avail = context.portfolio.available_cash    # 以实际可用资金为准
        if filled < amount:
            log.warning('[买入部分成交] %s %s 委托%d股，实际成交%d股（%.0f%%），剩余未成交' % (
                today, name, amount, filled, filled * 100.0 / amount if amount else 0.0))
        log.info(f"  买入 {name}（{sec}） | 委托：{amount}股 | 实际成交：{filled}股 | 参考价：{price:.4f} | 成交市值：{filled * price:.2f}元 | 仓位：{filled * price / total_value * 100 if total_value > 0 else 0:.2f}% | {_fmt_indicator(sig.get('metrics', {}).get(sec))}")


    _log_execution_status(context)


def after_trading_end(context):
    # 每日收盘后输出账户概况（v2.0 日志格式）
    if not g.verbose:
        return
    try:
        held = _held_secs(context)
        names = [g.sec_name.get(s, s) for s in held]
        log.info(f"  收盘 | {_to_date(context.current_dt)} | 总资产：{context.portfolio.total_value:.2f}元 | 可用资金：{context.portfolio.available_cash:.2f}元 | 持仓：{', '.join(names) if names else '空仓'}")
    except Exception:
        pass


# =============================================================================
#  四、数据与工具函数
# =============================================================================
def _get_close_series(sec, end_date):
    """获取截至 end_date（含）的最近 history_count 根日线收盘价（前复权、剔除停牌日）。

    尚未上市的标的返回 None（正常排除）；取数接口异常则抛 RuntimeError，当日中止交易。
    """
    start = _security_start_date(sec)
    if start is not None and end_date < start:
        return None
    count = max(int(g.history_count), int(g.min_bars) + 5)
    df = None
    try:
        df = get_price(sec, end_date=end_date, count=count, frequency='1d',
                       fields=['close'], skip_paused=True, fq='pre')
    except Exception:
        # 前复权取数失败：退化为后复权（两者都是连续复权价），并告警一次
        warned = getattr(g, '_warned_fq', None)
        if warned is None:
            warned = set()
            g._warned_fq = warned
        if sec not in warned:
            warned.add(sec)
            log.warning('[数据] %s 前复权取数失败，改用后复权数据（复权口径可能变化）' % sec)
        try:
            df = get_price(sec, end_date=end_date, count=count, frequency='1d',
                           fields=['close'], skip_paused=True, fq='post')
        except Exception as e:
            raise RuntimeError('[数据] %s 获取历史数据失败：%r' % (sec, e))
    if df is None or len(df) == 0:
        return None
    if 'close' not in getattr(df, 'columns', []):
        return None
    s = df['close'].dropna()
    return s if len(s) > 0 else None


def _security_start_date(sec):
    """标的上市日期（带缓存）；用于区分“尚未上市/无数据”与“数据接口异常”。"""
    cache = getattr(g, '_sec_start', None)
    if cache is None:
        cache = {}
        g._sec_start = cache
    if sec not in cache:
        try:
            info = get_security_info(sec)
            cache[sec] = _to_date(info.start_date) if info is not None else None
        except Exception:
            cache[sec] = None
    return cache[sec]


def _entry_date_of(context, sec):
    """返回建仓日期：优先使用持仓的 init_time，其次 g.entry_date 记录。"""
    pos = _position_of(context, sec)
    if pos is not None:
        init_time = getattr(pos, 'init_time', None)
        if init_time is not None:
            entry = _to_date(init_time)
            if entry is not None:
                return entry
    return g.entry_date.get(sec)


def _hold_days(context, sec, eval_date):
    """持有天数：从买入成交日到信号计算日 eval_date 经过的交易日数。

    默认 g.hold_days_include_entry_day=False：买入成交日算第 0 天（即“已过交易日数”），
    例如周一开盘买入，周四收盘后持有天数=3，满足“持有天数>2”，周五开盘卖出。
    """
    entry = _entry_date_of(context, sec)
    if entry is None:
        warned = getattr(g, '_warned_no_entry', None)
        if warned is None:
            warned = set()
            g._warned_no_entry = warned
        if sec not in warned:
            warned.add(sec)
            log.warning('[持有天数] %s 无法确定建仓日期，暂按 0 天处理（止盈卖出可能延后）' % sec)
        return 0
    if entry > eval_date:
        return 0
    try:
        n = len(get_trade_days(start_date=entry, end_date=eval_date))
    except Exception:
        n = (eval_date - entry).days + 1
    if not g.hold_days_include_entry_day:
        n -= 1
    return max(int(n), 0)


def _get_previous_trade_date(context):
    prev = getattr(context, 'previous_date', None)
    if prev is not None:
        d = _to_date(prev)
        if d is not None:
            return d
    cur = _to_date(context.current_dt)
    if cur is None:
        log.error('[日期] 无法获取当前日期')
        return None
    try:
        days = get_trade_days(end_date=cur, count=2)
        if len(days) >= 2:
            return _to_date(days[-2])
        return _to_date(days[-1])
    except Exception as e:
        log.error('[日期] 无法确定上一交易日：%r' % (e,))
        return None


def _is_rotation_day(eval_date):
    """无状态地判断 eval_date 是否为轮动日（轮动周期>1 时使用，模拟盘重启不丢失）。"""
    try:
        k = int(g.rotation_days)
    except Exception:
        k = 1
    if k <= 1:
        return True
    anchor = _to_date(g.rotation_anchor) or eval_date
    try:
        n = len(get_trade_days(start_date=anchor, end_date=eval_date))
    except Exception:
        n = 1
    if n <= 0:
        return False        # 锚点晚于信号日（配置异常）：不轮动，等待人工检查
    return ((n - 1) % k) == 0


def _held_secs(context):
    out = []
    for sec in g.pool:
        if _position_of(context, sec) is not None:
            out.append(sec)
    return out


def _position_of(context, sec):
    """返回 sec 的有效持仓（total_amount>0），否则 None。

    注意：不要用 context.portfolio.positions.get(sec)。聚宽对“不存在于 positions 的标的”
    调用 get/__getitem__ 时会打印兼容性 WARNING（本项目真实回测中该告警占日志 66%），
    必须先做成员判断再取值。
    """
    positions = context.portfolio.positions
    try:
        if sec not in positions:
            return None
        pos = positions[sec]
    except Exception:
        return None
    if pos is not None and getattr(pos, 'total_amount', 0) > 0:
        return pos
    return None


def _is_paused(cd):
    try:
        return bool(getattr(cd, 'paused', False))
    except Exception:
        return False


def _current_price(cd):
    """当前参考价：优先当日开盘价（09:27 后可得），其次最新价。

    聚宽撮合规则：“如果在开盘时刻运行，最新价格为开盘价”，所以 09:30 下单的
    成交价≈当日开盘价（另加滑点）；用 day_open 估算下单数量、判断涨跌停最准确。
    """
    for field in ('day_open', 'last_price'):
        v = _num_attr(cd, field)
        if v is not None and v > 0:
            return v
    return None


def _num_attr(obj, field):
    v = getattr(obj, field, None)
    if v is None:
        return None
    try:
        v = float(v)
    except Exception:
        return None
    if v != v or v <= 0:   # NaN / 非正数
        return None
    return v


def _to_date(x):
    if x is None:
        return None
    if isinstance(x, datetime.datetime):
        return x.date()
    if isinstance(x, datetime.date):
        return x
    try:
        return pd.Timestamp(x).date()
    except Exception:
        return None


# =============================================================================
#  四、日志工具（v2.0：表格化输出，风格对齐参考模板）
# =============================================================================
def _get_display_width(text):
    """计算字符串显示宽度：中文占2字符、英文数字占1字符，用于表格对齐。"""
    width = 0
    for c in str(text):
        width += 2 if ord(c) > 127 else 1
    return width


def _fmt_cell(col, val):
    """按列类型格式化表格单元格：排名取整、收盘价/均线保留4位、3-30均线5位、百分比2位。"""
    try:
        fv = float(val)
    except Exception:
        return str(val)
    if col == '排名':
        return str(int(round(fv)))
    if '3-30均线' in col:
        return f'{fv:.5f}'
    if ('MA' in col) or ('均线' in col):
        return f'{fv:.4f}'
    if col == '收盘价':
        return f'{fv:.4f}'
    return f'{fv:.2f}'


def _is_numeric_col(col):
    return any(k in col for k in ('收盘价', 'MA', '均线', '涨幅', '乖离率', '%', '排名'))


def _format_table(df):
    """把 DataFrame 格式化为对齐的文本表格（数值列右对齐，按列类型格式化）。"""
    cols = df.columns.tolist()
    formatted = {}
    for col in cols:
        if _is_numeric_col(col):
            formatted[col] = [_fmt_cell(col, v) for v in df[col]]
        else:
            formatted[col] = [str(v) for v in df[col]]

    col_widths = {}
    for col in cols:
        max_w = _get_display_width(col)
        for cell in formatted[col]:
            max_w = max(max_w, _get_display_width(cell))
        col_widths[col] = max_w + 2

    header_cells, sep_cells = [], []
    for col in cols:
        w = col_widths[col]
        cell = str(col)
        header_cells.append(cell + ' ' * (w - _get_display_width(cell)))
        sep_cells.append('-' * w)
    lines = ['| ' + ' | '.join(header_cells) + ' |',
             '| ' + ' | '.join(sep_cells) + ' |']

    for i in range(len(df)):
        row_cells = []
        for col in cols:
            w = col_widths[col]
            cell = formatted[col][i]
            if _is_numeric_col(col):
                row_cells.append(' ' * (w - _get_display_width(cell)) + cell)
            else:
                row_cells.append(cell + ' ' * (w - _get_display_width(cell)))
        lines.append('| ' + ' | '.join(row_cells) + ' |')
    return '\n'.join(lines)


def _build_metrics_df(sig):
    """把当日指标整理成 DataFrame（字段覆盖排序与买卖规则用到的全部指标）。"""
    rows = []
    ranked = list(sig.get('ranked', []))
    for sec in g.pool:
        name = g.sec_name.get(sec, sec)
        m = sig['metrics'].get(sec)
        if m is None:
            rows.append({
                '代码': sec, '名称': name, '收盘价': float('nan'),
                f'MA{g.rank_fast_ma}': float('nan'), f'MA{g.rank_slow_ma}': float('nan'),
                f'MA{g.bias_window}': float('nan'), '3-30均线': float('nan'),
                '涨幅(1)(%)': float('nan'), '涨幅(3)(%)': float('nan'), '涨幅(5)(%)': float('nan'),
                f'乖离率({g.bias_window})(%)': float('nan'),
                '排名': '-', f'入前{g.max_hold_num}名': '数据缺失'})
            continue
        rank_pos = ranked.index(sec) + 1 if sec in ranked else 0
        rows.append({
            '代码': sec, '名称': name, '收盘价': m['close'],
            f'MA{g.rank_fast_ma}': m['ma_fast'], f'MA{g.rank_slow_ma}': m['ma_slow'],
            f'MA{g.bias_window}': m['ma_bias'], '3-30均线': m['rank'],
            '涨幅(1)(%)': m['ret1'] * 100.0, '涨幅(3)(%)': m['ret3'] * 100.0,
            '涨幅(5)(%)': m['ret5'] * 100.0,
            f'乖离率({g.bias_window})(%)': m['bias60'],
            '排名': rank_pos, f'入前{g.max_hold_num}名': '是' if sec in sig['top_set'] else '否'})
    return pd.DataFrame(rows)


def _log_signal(context, sig):
    """输出每日信号日志（v2.0：指标总览表格 + 排名/买入校验 + 卖出判断 + 买入计划）。"""
    if not g.verbose:
        return
    try:
        ranked = list(sig.get('ranked', []))
        bp, sp = g.buy_params, g.sell_params
        names = lambda arr: [g.sec_name.get(s, s) for s in arr]

        # ========== 每日指标总览（表格，含全部指标） ==========
        log.info('=' * 75)
        log.info(f"  每日指标总览 | {context.current_dt.strftime('%Y-%m-%d %H:%M')} | 信号数据截止：{sig['eval_date']} | 轮动日：{'是' if sig['do_rotate'] else '否'}")
        log.info('=' * 75)
        log.info('\n' + _format_table(_build_metrics_df(sig)) + '\n')
        log.info('=' * 75)

        # ========== 排名与买入校验 ==========
        log.info('\n【排名与买入校验】')
        top_code = ranked[0] if ranked else None
        if top_code is None:
            log.info('  无任何标的参与排序（数据缺失），今日不交易')
        else:
            top_m = sig['metrics'][top_code]
            top_name = g.sec_name.get(top_code, top_code)
            c1 = top_m['ret3'] < bp['ret3_lt']
            c2 = top_m['ret5'] > bp['ret5_gt']
            c3 = top_m['bias60'] < bp['bias60_lt']
            log.info(f"  排序第一名：{top_name}（{top_code}） | 3-30均线：{top_m['rank']:.5f} | 排名前{g.max_hold_num}名：{names(sig['top_set'])}")
            log.info(f"  买入规则1 涨幅(3)：{top_m['ret3'] * 100:.2f}% < {bp['ret3_lt'] * 100:.2f}% → {'满足' if c1 else '不满足'}")
            log.info(f"  买入规则2 涨幅(5)：{top_m['ret5'] * 100:.2f}% > {bp['ret5_gt'] * 100:.2f}% → {'满足' if c2 else '不满足'}")
            log.info(f"  买入规则3 乖离率({g.bias_window})：{top_m['bias60']:.2f}% < {bp['bias60_lt']:.1f}% → {'满足' if c3 else '不满足'}")
            if top_code in sig['held']:
                log.info('  综合结论：第一名已持有，继续持有（已持有资产不再检查买入规则）')
            elif c1 and c2 and c3:
                log.info('  综合结论：满足开仓要求')
            else:
                log.info('  综合结论：不满足开仓要求，今日不新开仓')

        # ========== 持仓与卖出判断明细 ==========
        log.info('\n【持仓与卖出判断明细】')
        if not sig['held']:
            log.info('  当前空仓，无卖出操作')
        for sec in sig['held']:
            m = sig['metrics'].get(sec)
            name = g.sec_name.get(sec, sec)
            hold_days = _hold_days(context, sec, sig['eval_date'])
            entry = _entry_date_of(context, sec)
            entry_txt = entry if entry is not None else '未知'
            if m is None:
                log.info(f"  持仓 {name}（{sec}） | 当日无有效数据，今日不判断卖出 | 建仓日：{entry_txt} | 已持有：{hold_days}个交易日")
            else:
                rank_pos = ranked.index(sec) + 1 if sec in ranked else 0
                rank_txt = f'第{rank_pos}/{len(ranked)}名' if sec in ranked else '未参与排序'
                log.info(f"  持仓 {name}（{sec}） | 收盘价：{m['close']:.4f} | 3-30均线：{m['rank']:.5f} | 涨幅(1)：{m['ret1'] * 100:+.2f}% | 涨幅(3)：{m['ret3'] * 100:+.2f}% | 涨幅(5)：{m['ret5'] * 100:+.2f}% | 乖离率({g.bias_window})：{m['bias60']:+.2f}%")
                log.info(f"    排名：{rank_txt} | 进入排序前{g.max_hold_num}名：{'是' if sec in sig['top_set'] else '否'} | 建仓日：{entry_txt} | 已持有：{hold_days}个交易日（买入日算第0天）")
                r1 = m['ret1'] > sp['ret1_gt']
                r2 = m['bias60'] > sp['bias60_gt']
                r3 = hold_days > sp['hold_days_gt']
                rotation_out = sig['do_rotate'] and sec not in sig['top_set']
                log.info(f"    卖出规则1 涨幅(1)：{m['ret1'] * 100:+.2f}% > {sp['ret1_gt'] * 100:.2f}% → {'满足' if r1 else '不满足'}")
                log.info(f"    卖出规则2 乖离率({g.bias_window})：{m['bias60']:+.2f}% > {sp['bias60_gt']:.1f}% → {'满足' if r2 else '不满足'}")
                log.info(f"    卖出规则3 持有天数：{hold_days} > {sp['hold_days_gt']} → {'满足' if r3 else '不满足'}（组合：(1或2)且3）")
                log.info(f"    轮动卖出：轮动日{'是' if sig['do_rotate'] else '否'} / 未进入前{g.max_hold_num}名：{'是' if sec not in sig['top_set'] else '否'} → {'触发' if rotation_out else '不触发'}")
            if sec in sig['sells']:
                log.info(f"    → 卖出信号：{sig['sell_reasons'].get(sec, '')}，次日开盘执行")
            else:
                log.info('    → 继续持有')

        # ========== 买入计划明细 ==========
        log.info('\n【买入计划明细】')
        if sig['buys']:
            for sec in sig['buys']:
                m = sig['metrics'].get(sec)
                name = g.sec_name.get(sec, sec)
                if m is None:
                    log.info(f"  计划次日开盘买入 {name}（{sec}）（指标缺失）")
                else:
                    log.info(f"  计划次日开盘买入 {name}（{sec}） | 3-30均线：{m['rank']:.5f} | 涨幅(3)：{m['ret3'] * 100:.2f}% | 涨幅(5)：{m['ret5'] * 100:.2f}% | 乖离率({g.bias_window})：{m['bias60']:.2f}%")
        elif not sig['do_rotate']:
            log.info('  非轮动日，不产生新的买入计划')
        elif not sig['top_set']:
            log.info('  无满足排序条件的标的（或数据不足），今日不买入')
        elif len(sig['held']) >= int(g.max_hold_num):
            log.info(f"  已持有{g.max_hold_num}只（达到最大持仓数量），不新开仓")
        else:
            log.info('  排序前N名中没有可买入标的：')
            for sec in sig['top_set']:
                name = g.sec_name.get(sec, sec)
                if sec in sig['held']:
                    log.info(f"    {name}（{sec}）：已持有，继续持有（不再检查买入规则）")
                    continue
                m = sig['metrics'].get(sec)
                if m is None:
                    log.info(f"    {name}（{sec}）：无有效数据，跳过")
                    continue
                c1 = m['ret3'] < bp['ret3_lt']
                c2 = m['ret5'] > bp['ret5_gt']
                c3 = m['bias60'] < bp['bias60_lt']
                log.info(f"    {name}（{sec}）：涨幅(3) {m['ret3'] * 100:.2f}% → {'满足' if c1 else '不满足'} | 涨幅(5) {m['ret5'] * 100:.2f}% → {'满足' if c2 else '不满足'} | 乖离率({g.bias_window}) {m['bias60']:.2f}% → {'满足' if c3 else '不满足'}")
                log.info(f"      综合结论：{'满足买入规则，但受持仓数量/资金限制未买' if (c1 and c2 and c3) else '不满足买入规则，空仓观望'}")
        log.info('\n' + '=' * 75 + '\n')
    except Exception:
        pass


# =============================================================================
#  五、口径说明（与 ETF组合宝 平台的对应关系）
# =============================================================================
#  1. 排序：3-30均线 = (MA3 - MA30) / MA30，降序取前“最大持仓数量”名；单指标权重为1，
#     等价于直接按该指标排序。并列时保持候选池顺序。
#  2. 买入：仅对“排序前N名且当前未持有”的资产检查买入规则，三条规则全部满足（全部匹配）
#     才在次日开盘买入；已持有的资产不再检查买入规则，继续持有。
#  3. 卖出：
#     a) 轮动卖出：轮动日该资产未进入排序前N名且当前持有 -> 次日开盘卖出
#        （按平台逻辑说明，该卖出不受“持有天数”限制）；
#     a2) 评估日无有效数据（停牌/数据缺失）的持仓不产生新的卖出信号；但已发出却因停牌/
#        跌停未能成交的卖出委托会顺延到下一个可成交日（g.pending_sells）；
#     b) 卖出规则： (涨幅(1)>0.06 或 乖离率(60)>15) 且 持有天数>2 -> 次日开盘卖出。
#  4. 持仓比例：固定比例 = 总资产 / 最大持仓数量；最大持仓数量为1时即满仓单一资产。
#     替代资产为“无”，未分配仓位保留现金。
#  5. 成交价：次日开盘价（聚宽 09:30 市价单按“最新价+滑点”撮合，开盘时刻最新价=开盘价）。
#     停牌/涨跌停：基于当日开盘价判断，停牌不交易；开盘涨停不买入、跌停不卖出；
#     下单被拒会记录 warning，下一交易日重新判断。
#     部分成交：聚宽受“单笔不超过全天成交量”等限制时，订单可能只成交一部分（部成部撤）但仍
#     返回非 None。本版会核对实际持仓：卖出未清仓则保留 pending_sells 顺延、不释放持仓名额；
#     买入按实际成交数量记账，并输出 [买入部分成交]/[卖出未完成] 告警。
#  6. 持有天数：默认“买入成交日算第0天”（已过交易日数），即买入成交日到信号计算日
#     （上一交易日）经过的交易日数；若按“买入日算第1天”理解，把
#     g.hold_days_include_entry_day 改为 True（等价于持有门槛提前 1 个交易日）。
#  7. 资金预留：买入使用总资产的 98%（g.buy_cash_buffer），覆盖隔夜跳空/佣金/滑点/整手误差。
#  8. 模拟盘：聚宽日级模拟盘在 09:25 集合竞价后、09:27~09:30 之间运行；若日志出现
#     “成交量不足/下单被拒”，可把 g.exec_time 改为 '09:31'（成交价会略偏离开盘价）。
#  9. 资金容量（首要风险）：159518 标普油气、518880 黄金ETF、513100 纳指ETF 的流动性/溢价差异很大。
#     换池前旧标的 160723 曾因流动性极差，98% 仓位多次被聚宽按“不超过全天成交量”削减（16 笔部成部撤、
#     1 笔撤单，实际成交比例最低 9%，造成 109~132 天仓位严重不足）；159518 虽为 QDII ETF，也必须
#     先用近 20 日成交额验证容量：单笔订单 ≤ 日均成交额 5%~10%，超出则拆单/限价/VWAP，或降低权重。
#  10. 复权：指标用前复权收盘价、成交用真实价（use_real_price）。聚宽官方提醒含场内基金
#      的策略动态复权在份额折算/拆分时可能异常；513100 于 2022-01-13 做 1:5 份额拆分
#      （该回测期间策略当时空仓，未受影响）；若持仓跨拆分，需核对持仓数量/成本是否被正确调整。
#  11. 换手与防抖（旧池 160723 的真实回测结论，换池后仅作参考）：2014-07~2026-09 共 160 次买入/
#      159 次完整往返，其中“D 日买、D+1 日卖”17 次（10.7%，合计亏 7.47 万元），全部由“轮动出局”
#      触发（平台原逻辑）。g.rotation_min_hold_days 默认 0=平台原逻辑；设为 1 可消除一日往返
#      （旧池本地 mock 对照：年化 38.8%→39.4%、最大回撤 -14.7%→-14.0%），设为 2 约 37.5%。
#      换池后换手/收益特征会变化，请重新做 0/1/2 敏感性回测。
#  12. 起始时间：159518 于 2023-11-15 上市，凑满 60 根日线约到 2024 年 2 月下旬；在此之前
#      实际只有 513100/518880 两只候选（与平台三资产轮动不可比）。建议回测起始 2024-03-01 之后；
#      若想看更长历史，需接受“早期只有 2 只候选”，并在报告中单独标注。
#  13. 标的替换（v1.2）：按用户要求把原候选 160723 嘉实原油LOF 替换为 159518 标普油气
#      （嘉实标普石油天然气勘探及生产精选行业ETF，QDII，深交所上市）。两者的上市时间、流动性、
#      溢价特征、涨跌幅限制均不同，换池后的回测结果与旧池（含 v1.1 诊断报告中的数字）不可直接比较。
#  14. v2.0 仅调整代码风格与日志格式（表格化输出、f-string、参数启动打印、参考模板分节日志），
#      策略逻辑与全部参数（候选池/排序/买卖规则/持仓/执行时点/费用/防抖）均与 v1.2 完全一致。
# =============================================================================


# =============================================================================
#  六、聚宽框架占位函数
# =============================================================================
def handle_data(context, data):
    """本策略使用 before_trading_start（盘前算信号）+ run_daily（开盘执行）定时运行，
    handle_data 无需额外操作，保留空实现以兼容聚宽策略模板。"""
    pass
