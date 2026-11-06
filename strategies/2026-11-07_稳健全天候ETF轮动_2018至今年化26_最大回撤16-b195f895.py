# Clone from JoinQuant
# postId: b195f89547c15361057cecc114314606
# backtestId: 1c0a45a274cbcee9b9578878560f3991
# title: 稳健全天候ETF轮动，2018至今年化26%最大回撤16%

# -*- coding: utf-8 -*-
"""
三层结构：
  ① 底仓 B（逆波动率配置）：5 只风险资产（黄金/豆粕/纳指100/创业板/科创芯片）
     按 60 日波动率倒数加权，每月首个交易日调仓；
     上市不足 61 个收盘价（或当日停牌）的资产自动缺席，次月再入池
  ② 创业板 ROC 择时（滞回状态机）：创业板ETF ROC(20) > 8% 转进攻（持创业板）；
     ROC(20) < 0 转防御（该仓位换国债ETF）；0~8% 之间维持原状态。
  ③ 反转抄底 A：上证指数昨日跌 ≥1.5% 且今日跌 ≥1.4% → 清仓全部，全仓买入
     中证1000ETF，持有 15 个交易日（入场日计第 0 天）后交还底仓。
"""

from jqdata import *
import numpy as np


# ==================== 标的池 ====================
RISK_POOL = [
    '518880.XSHG',  # 黄金ETF（华安）
    '159985.XSHE',  # 豆粕ETF（2019-12 上市）
    '513100.XSHG',  # 纳指100（国泰）
    '159915.XSHE',  # 创业板ETF（易方达）
    '588200.XSHG',  # 科创芯片ETF（2022-10 上市）
]
DEFENSE_ETF = '511010.XSHG'   # 国债ETF（防御）
DIP_ETF = '512100.XSHG'       # 中证1000ETF（抄底）
ROC_ASSET = '159915.XSHE'     # ROC 择时标的（创业板ETF）
INDEX_SH = '000001.XSHG'      # 上证指数（抄底触发参照）

ETF_NAMES = {
    '518880.XSHG': '黄金ETF', '159985.XSHE': '豆粕ETF', '513100.XSHG': '纳指100',
    '159915.XSHE': '创业板ETF', '588200.XSHG': '科创芯片ETF',
    '511010.XSHG': '国债ETF', '512100.XSHG': '中证1000ETF',
}

# ==================== 参数 ====================
VOL_WINDOW = 60               # 逆波动率：60 日日收益波动率
ROC_DAYS = 20                 # ROC(20)
ROC_ON = 0.08                 # >8% 转进攻
ROC_OFF = 0.0                 # <0 转防御
DIP_DROP1 = 0.015             # 上证指数昨日跌 ≥1.5%
DIP_DROP2 = 0.014             # 上证指数今日跌 ≥1.4%
DIP_HOLD_DAYS = 15            # 抄底持有 15 个交易日（入场日=第0天）

# ---- 消融开关 ----
ENABLE_ROC = True             # False = 去掉创业板 ROC 择时
ENABLE_DIP = True             # False = 去掉反转抄底
WEIGHT_MODE = 'invvol'        # 'invvol' 逆波动率 / 'equal' 等权


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.00013, close_commission=0.00013,
        close_today_commission=0, min_commission=5,
    ), type='fund')
    set_slippage(PriceRelatedSlippage(0.001))   # 总价差 0.1% → 单边 0.05%

    log.set_level('order', 'error')

    # 状态
    g.weights = None           # 本月逆波动率权重 {code: w}
    g.last_month = None        # 月份切换检测
    g.roc_state = 'defense'    # 'attack' / 'defense'（滞回初值，首日按 ROC 定夺）
    g.roc_now = None           # 最近一次 ROC(20) 值（日志用）
    g.in_dip = False           # 是否处于抄底持有期
    g.dip_days = 0             # 抄底已持有交易日数（入场日=0）

    run_daily(trade, '14:30')


# ==================== 数据辅助 ====================
def today_price(code):
    """当日现价（14:30 口径）；停牌/无效返回 None。"""
    cd = get_current_data()[code]
    if cd.paused:
        return None
    p = cd.last_price
    if p is None or p <= 0 or np.isnan(p):
        return None
    return p


def hist_closes(code, n):
    """截至昨日的 n 个收盘价；不足返回 None。"""
    df = attribute_history(code, n, '1d', ['close'], skip_paused=True, df=True)
    if df is None or len(df) < n:
        return None
    closes = df['close'].values
    if np.any(~np.isfinite(closes)) or np.any(closes <= 0):
        return None
    return closes


# ==================== ① 逆波动率权重 ====================
def compute_weights(context):
    """对合格风险资产计算权重：w_i ∝ 1/σ_i（σ_i=近60日日收益标准差）。
    合格 = 已上市满 VOL_WINDOW+1 个收盘价 且 今日未停牌。"""
    vols = {}
    for code in RISK_POOL:
        closes = hist_closes(code, VOL_WINDOW + 1)
        p = today_price(code)
        if closes is None or p is None:
            continue
        series = np.append(closes, p)          # 追加今日现价（CLOSE口径）
        rets = series[1:] / series[:-1] - 1.0  # 恰好 VOL_WINDOW 个日收益
        sigma = float(np.std(rets))
        if not np.isfinite(sigma) or sigma <= 0:
            continue
        vols[code] = sigma

    if not vols:
        return None

    if WEIGHT_MODE == 'equal':
        weights = {c: 1.0 / len(vols) for c in vols}
    else:
        inv = {c: 1.0 / s for c, s in vols.items()}
        total = float(np.sum(list(inv.values())))   # 注意：聚宽环境内建 sum 被遮蔽，勿用
        weights = {c: v / total for c, v in inv.items()}
    return weights


# ==================== ② 创业板 ROC 择时（滞回） ====================
def update_roc_state(context):
    """ROC(20)=现价/20个交易日前收盘-1：>8%转进攻；<0转防御；带内维持。"""
    if not ENABLE_ROC:
        g.roc_state = 'attack'
        return
    p = today_price(ROC_ASSET)
    closes = hist_closes(ROC_ASSET, ROC_DAYS)
    if p is None or closes is None:
        return                                # 数据不足 → 维持原状态
    roc = p / closes[0] - 1.0
    g.roc_now = roc
    if roc > ROC_ON:
        g.roc_state = 'attack'
    elif roc < ROC_OFF:
        g.roc_state = 'defense'


# ==================== ③ 抄底信号 ====================
def sh_two_day_drop(context):
    """上证指数昨日跌≥1.5% 且 今日跌≥1.4%（今日跌幅以14:30现价近似）。"""
    closes = hist_closes(INDEX_SH, 2)          # [C(t-2), C(t-1)]
    p = today_price(INDEX_SH)
    if closes is None or p is None:
        return False
    r1 = closes[1] / closes[0] - 1.0           # 昨日跌幅
    r0 = p / closes[1] - 1.0                   # 今日跌幅（近似）
    return (r1 <= -DIP_DROP1) and (r0 <= -DIP_DROP2)


def dip_etf_ready(context):
    """抄底标的可交易：已上市、未停牌。"""
    df = attribute_history(DIP_ETF, 1, '1d', ['close'], df=True)
    if df is None or len(df) < 1:
        return False
    return today_price(DIP_ETF) is not None


# ==================== 目标与执行 ====================
def build_base_targets(context):
    """底仓目标权重：本月权重 + 择时换仓（防御时创业板份额并入国债ETF）。"""
    targets = {}
    for code, w in g.weights.items():
        dst = DEFENSE_ETF if (code == ROC_ASSET and g.roc_state == 'defense') else code
        targets[dst] = targets.get(dst, 0.0) + w
    return targets


def execute_targets(context, targets, force=False):
    """把持仓调到目标权重。targets: {code: w}（未列出的持仓目标为 0）。
    force=True 全量调仓（月调/抄底进出/交还）；
    非force=结构性自愈：仅处理"应持有却缺失 / 应清零却仍持有"的腿（择时换仓、
    上日失败单修复），不做权重漂移再平衡。"""
    total = context.portfolio.total_value
    cd = get_current_data()
    held = {c for c, pos in context.portfolio.positions.items() if pos.total_amount > 0}

    legs = []                                   # (diff, code)，diff<0 先执行（先卖后买）
    for code in set(targets) | held:
        w = targets.get(code, 0.0)
        pos = context.portfolio.positions.get(code)
        cur_val = pos.value if (pos and pos.total_amount > 0) else 0.0
        diff = w * total - cur_val
        if not force:
            in_tgt = (w > 0)
            in_pos = (code in held)
            if in_tgt == in_pos:
                continue                        # 结构一致 → 月内不动（漂移留待月调）
        if abs(diff) < 1000:                    # 不足最小调仓价值，忽略
            continue
        legs.append((diff, code))

    for diff, code in sorted(legs):
        c = cd[code]
        if c.paused:
            log.warn(f'[调仓] {ETF_NAMES.get(code, code)} 停牌，跳过（次日自愈）')
            continue
        if diff < 0 and c.last_price <= c.low_limit:
            log.warn(f'[调仓] {ETF_NAMES.get(code, code)} 跌停无法卖出，跳过')
            continue
        if diff > 0 and c.last_price >= c.high_limit:
            log.warn(f'[调仓] {ETF_NAMES.get(code, code)} 涨停无法买入，跳过')
            continue
        order_target_value(code, targets.get(code, 0.0) * total)
        log.info(f"[调仓] {ETF_NAMES.get(code, code)} → {targets.get(code, 0.0) * 100:.1f}%"
                 f"（{'减' if diff < 0 else '加'} {abs(diff) / 10000:.2f} 万）")


# ==================== 主流程（每日 14:30） ====================
def trade(context):
    today = context.current_dt.date()

    # ── 抄底持有期 ──
    if g.in_dip:
        update_roc_state(context)               # 持有期内择时状态照常更新，供交还时用
        if g.dip_days >= DIP_HOLD_DAYS:
            roc_txt = f'{g.roc_now * 100:+.2f}%' if g.roc_now is not None else 'NA'
            log.info(f'[抄底交还] 持满 {DIP_HOLD_DAYS} 个交易日，重建底仓'
                     f'（ROC(20)={roc_txt}，状态={g.roc_state}）')
            g.in_dip = False
            g.dip_days = 0
            g.last_month = today.month          # 交还即视为本月已调权
            g.weights = compute_weights(context) or g.weights
            execute_targets(context, build_base_targets(context), force=True)
        else:
            g.dip_days += 1
            execute_targets(context, {DIP_ETF: 1.0})   # 自愈：实际持仓偏离则修复
        return

    # ── ② ROC 择时（滞回） ──
    old_state = g.roc_state
    update_roc_state(context)
    if ENABLE_ROC and g.roc_state != old_state:
        log.info(f"[择时] ROC(20)={g.roc_now * 100:+.2f}% → {'进攻' if g.roc_state == 'attack' else '防御（创业板份额换国债ETF）'}")

    # ── ③ 抄底触发（优先于月度调仓，避免当日先买后卖的 T+1 冲突） ──
    if ENABLE_DIP and sh_two_day_drop(context):
        closes = hist_closes(INDEX_SH, 2)
        p = today_price(INDEX_SH)
        r1 = closes[1] / closes[0] - 1.0
        r0 = p / closes[1] - 1.0
        if dip_etf_ready(context):
            log.info(f'[抄底入场] 上证指数两日跌 {r1 * 100:.2f}%/{r0 * 100:.2f}%，'
                     f'清仓全部 → 全仓 {ETF_NAMES[DIP_ETF]}，持有 {DIP_HOLD_DAYS} 个交易日')
            g.in_dip = True
            g.dip_days = 0
            execute_targets(context, {DIP_ETF: 1.0}, force=True)
            return
        else:
            log.warn('[抄底] 触发但中证1000ETF 不可交易，本次放弃')

    # ── ① 每月首个交易日：重算逆波动率权重 ──
    if g.last_month != today.month or g.weights is None:
        g.last_month = today.month
        weights = compute_weights(context)
        if weights:
            g.weights = weights
            desc = '  '.join(f'{ETF_NAMES[c]}{w * 100:.1f}%'
                             for c, w in sorted(weights.items(), key=lambda x: -x[1]))
            log.info(f"[月调] {today} 逆波动率权重({WEIGHT_MODE})：{desc}")
            execute_targets(context, build_base_targets(context), force=True)
            return

    # ── 日常：按目标持仓自愈（择时换仓当日自动触发：偏差超容忍） ──
    if g.weights:
        execute_targets(context, build_base_targets(context))
