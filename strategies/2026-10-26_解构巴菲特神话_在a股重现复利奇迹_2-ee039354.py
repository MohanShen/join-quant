# Clone from JoinQuant
# postId: ee03935459266d698b03c040fa1d4628
# backtestId: 091838f94e30c3f939dea54cac158745
# title: ⭐解构巴菲特神话，在a股重现复利奇迹（2）

# -*- coding: utf-8 -*-
# 衡流 Alpha V1.8-E1-DL1.6c3e-LEV12-LIVE-P1-3PCT-DCA3000-FZ2-PRICE50-PITFIX
# （定投测试P1｜每月首个交易日投入3000元｜3%融资成本｜仅deploy融资｜执行封顶1.20倍）
# E1原始质量排序、持有、止损、机构响应与流动性政策保持不变；
# 价格、市值和财报硬门只限制新建证券，不触发已有持仓卖出，也不阻断已有健康持仓的周度杠杆补仓；
# 杠杆不再全时段最高1.60倍动态阶梯，而是按防守→修复→扩张路径在1.00/1.20/1.40/1.60之间慢升快降；
# 升降档状态机与全部护栏语义保持母版原样，仅执行层按下述 g.leverage_effective_cap 封顶。
# 注意：融资部分仅能买入聚宽当日可融资标的；非融资标的优先使用自有现金，无法融资的差额保留。
# c3e监控校正：保留c3d全部交易行为；聚宽自定义图表改为实际股票总暴露率(%)与市场综合分数；
# 移出默认关闭的Q0观察器，删除4个零调用旧函数；
# 交易参数、选股、止损、融资和风控不变；收盘审计仅做日志分层，不改变订单。
# 日志同时展示政策目标暴露与当前持仓结构可执行暴露。
# 【PIT-FIX-P0-20260902 + CAP13-20260904 + LEV12-20260904】基金层PIT修复 + 杠杆配置调整版
# 基线：母版 Alpha-V1.8-E1-DL1.6c3e-FZ2-Price50（带融资账户）逐字节复制后修改。
# 依据《基金层未来函数审计报告_20260902》确定项修复，仅动基金样本构建与主动判定：
#  F-1/F-2/F-4  FUND_MAIN_INFO 原始帧缓存 + 每asof按start_date/end_date点时过滤（_load_fund_main_codes）
#  F-3          主动偏股判定改由当季已披露持仓推导（开关 g.pit_fix_holdings_derived_active，默认开）
#  未触碰       F-5份额合并、F-6分类精度、F-14阈值、全部评分权重与交易参数。
#  回退A/B      g.pit_fix_date_filter / g.pit_fix_holdings_derived_active 置 False 即恢复原行为。
# LEV12 杠杆配置（2026-09-04，相对 CAP13 的三处协调改动）：
#  ① deploy 政策仓位 0.92→1.00（满仓）：log40 显示 selective×1.20 档效率 -0.78（净亏），
#     deploy×1.20 档效率 +0.78（真有效），故把仓位集中在有效场景。
#  ② 杠杆仅限 deploy：selective 分支整段改为 desired=1.00（与 freeze/defense 一致不融资）。
#  ③ 执行封顶 1.30→1.20：deploy×1.30 档实测效率仅 0.06（强弩之末），1.20 档效率 0.78，
#     故顶档降到 1.20；内部阶梯 1.00/1.20/1.40/1.60 与 2/4/6 周升档节奏不变。
#  配套护栏重映射：cap=1.20 下 CAP13 的 -6%→1.20 会空转(=封顶值)，故下沉为
#     -6%→1.10、≤-10%→1.00（执行口径 1.20→1.10→1.00，严格递减无空转档）。
#  最大执行暴露 = 1.00(deploy) × 1.20(顶档) = 1.20（vs CAP13 的 0.92×1.30=1.196，
#  几乎相同，但基准仓位更高、2 周即达顶档、不碰效率最差的 1.30 档）。
# CAP13-GUARD13 是母版历史配置；LEV12 已按 1.20 封顶重新映射护栏。
# 当前唯一有效口径见上方 LEV12 配置说明与 _drawdown_raw_leverage_cap 自检。
# FZ2-PENDING-FIX（2026-09-06）：月度释放重验后必定消费本次触发；
# 空释放池也不允许旧 Freeze->Selective 事件跨月残留或重复重验。
# LIVE-P1-3PCT（2026-09-08）：不改变选股、持有、止损、市场评分、FZ2或杠杆状态机；
# 仅增加生产约束：融资年利率固定3%、融资名单显式使用交易日日期、
# 模拟盘重启/改码后先自检再允许新增风险、每日一条微信审计摘要。
# DCA3000（2026-09-08）：每月首个交易日开盘前用 inout_cash 转入3000元；
# 入金先于当月开盘调仓，按月份幂等，累计本金与投资损益分开审计。

from datetime import date
import hashlib
import json
import pickle
import re

from jqdata import *
from jqdata import finance
try:
    import builtins as _py_builtins
except ImportError:  # 兼容旧Python运行内核。
    import __builtin__ as _py_builtins
import numpy as np
import pandas as pd


def _live_run_type(context):
    """返回聚宽运行类型；无法识别时按非模拟盘处理。"""
    try:
        return str(context.run_params.type).strip().lower()
    except Exception:
        return "unknown"


def _live_is_sim_trade(context):
    """自定义外部通知只允许在聚宽模拟盘触发，回测绝不发送。"""
    return _live_run_type(context) == "sim_trade"


def _live_ensure_runtime_defaults():
    """补齐模拟盘热重启或代码更新后可能缺少的非交易状态。"""
    defaults = {
        "live_notification_enabled": True,
        "live_notification_max_per_day": 3,
        "live_notify_date": None,
        "live_notify_count": 0,
        "live_daily_summary_date": None,
        "live_new_risk_blocked": False,
        "live_restart_observed": False,
        "live_last_self_check": {},
        "live_expected_build_id": "DL16C3E-LEV12-LIVE-P1-3PCT-DCA3000-20260908",
    }
    for key, value in defaults.items():
        if not hasattr(g, key):
            setattr(g, key, value)


def _live_send_message(context, category, message):
    """模拟盘限频微信摘要；失败只记日志，不影响交易与风控。"""
    _live_ensure_runtime_defaults()
    if not bool(getattr(g, "live_notification_enabled", True)):
        return False
    if not _live_is_sim_trade(context):
        return False
    try:
        date_key = str(context.current_dt.date())
    except Exception:
        date_key = "unknown"
    if getattr(g, "live_notify_date", None) != date_key:
        g.live_notify_date = date_key
        g.live_notify_count = 0
    limit = max(1, int(getattr(g, "live_notification_max_per_day", 3)))
    if int(getattr(g, "live_notify_count", 0)) >= limit:
        log.warning("LIVE-P0微信消息达到当日%d条上限，已抑制：%s。" % (limit, category))
        return False
    text = "[衡流LEV12-LIVE][%s] %s" % (str(category), str(message))
    try:
        send_message(text)
        g.live_notify_count += 1
        log.info("LIVE_P0_MESSAGE|%s" % text)
        return True
    except Exception as exc:
        log.error("LIVE-P0微信消息发送失败：%s。" % exc)
        return False


def _live_runtime_self_check(context, event):
    """模拟盘生产自检；失败时只阻止新增风险，减仓路径保持开放。"""
    _live_ensure_runtime_defaults()
    if not _live_is_sim_trade(context):
        g.live_new_risk_blocked = False
        return {"passed": True, "event": event, "run_type": _live_run_type(context)}

    failures = []
    expected_build = str(getattr(g, "live_expected_build_id", ""))
    actual_build = str(getattr(g, "dynamic_leverage_build_id", ""))
    if actual_build != expected_build:
        failures.append("build_id_mismatch")
    if not isinstance(getattr(g, "fz2_deferred_pool", None), dict):
        failures.append("fz2_pool_invalid")
    if not isinstance(getattr(g, "fz2_release_pending", None), bool):
        failures.append("fz2_pending_invalid")

    leverage = float(getattr(g, "leverage_multiplier", 1.0))
    target = float(getattr(g, "current_target_exposure", 0.0))
    effective_cap = float(getattr(g, "leverage_effective_cap", 1.20))
    if not np.isfinite(leverage) or leverage < 1.0 or leverage > effective_cap + 1e-10:
        failures.append("leverage_out_of_range")
    if not np.isfinite(target) or target < 0.0 or target > 1.20 + 1e-10:
        failures.append("target_exposure_out_of_range")

    metrics = _l16_margin_metrics(context)
    gross = float(metrics.get("gross_exposure", 0.0))
    debt = float(metrics.get("debt_ratio", 0.0))
    if not np.isfinite(gross) or gross < 0.0 or gross > 1.22:
        failures.append("gross_exposure_out_of_range")
    if not np.isfinite(debt) or debt < 0.0:
        failures.append("debt_ratio_invalid")
    if debt > float(getattr(g, "debt_ratio_block_new", 0.45)):
        failures.append("debt_ratio_blocks_new_risk")

    result = {
        "passed": not failures,
        "event": str(event),
        "date": str(context.current_dt.date()),
        "run_type": _live_run_type(context),
        "build_id": actual_build,
        "gross_exposure": gross,
        "debt_ratio": debt,
        "target_exposure": target,
        "leverage_multiplier": leverage,
        "failures": failures,
    }
    g.live_last_self_check = result
    g.live_new_risk_blocked = bool(failures)
    log_method = log.error if failures else log.info
    log_method("LIVE_P0_SELF_CHECK|%s" % json.dumps(
        result, ensure_ascii=False, sort_keys=True
    ))
    if failures:
        _live_send_message(
            context,
            "风险阻断",
            "%s 自检失败=%s；已禁止新增买入和融资，减仓不受影响。"
            % (result["date"], ",".join(failures)),
        )
    return result


def process_initialize(context):
    """聚宽进程恢复钩子：模拟盘重启后先锁住新增风险。"""
    _live_ensure_runtime_defaults()
    if _live_is_sim_trade(context):
        g.marginable_cache_date = None
        g.marginable_cache_codes = []
        g.live_restart_observed = True
        g.live_new_risk_blocked = True
        log.warning("LIVE-P0检测到模拟盘进程初始化，新增风险锁定至盘前自检通过。")


def after_code_changed(context):
    """模拟盘换码后禁止立即扩仓，等待下一次盘前完整自检。"""
    _live_ensure_runtime_defaults()
    if _live_is_sim_trade(context):
        g.marginable_cache_date = None
        g.marginable_cache_codes = []
        g.live_new_risk_blocked = True
        log.warning("LIVE-P0检测到代码更新，新增风险锁定至盘前自检通过。")
        _live_send_message(context, "代码更新", "检测到代码更新，新增风险暂时锁定。")


def before_trading_start(context):
    """每天盘前恢复审计；只有通过后模拟盘才能新增风险。"""
    _live_runtime_self_check(context, "before_trading_start")


def monthly_cash_contribution(context):
    """每月首个交易日开盘前转入3000元；同一月份严格只执行一次。"""
    month_key = context.current_dt.strftime("%Y-%m")
    if getattr(g, "dca_last_contribution_month", None) == month_key:
        return
    amount = float(getattr(g, "dca_monthly_amount", 3000.0))
    if not np.isfinite(amount) or amount <= 0.0:
        log.error("DCA3000月度入金参数非法：%s。" % amount)
        return
    try:
        inout_cash(amount, pindex=0)
    except Exception as exc:
        g.dca_contribution_failures = int(
            getattr(g, "dca_contribution_failures", 0)
        ) + 1
        log.error("DCA3000月度入金失败 %s：%s。" % (month_key, exc))
        _live_send_message(
            context,
            "定投入金失败",
            "%s 应投入%.2f元但执行失败：%s" % (month_key, amount, exc),
        )
        return
    g.dca_last_contribution_month = month_key
    g.dca_contribution_count = int(getattr(g, "dca_contribution_count", 0)) + 1
    g.dca_total_contributed = float(getattr(g, "dca_total_contributed", 0.0)) + amount
    log.info(
        "DCA3000_CASHFLOW|month=%s|amount=%.2f|count=%d|total=%.2f"
        % (
            month_key,
            amount,
            g.dca_contribution_count,
            g.dca_total_contributed,
        )
    )


def after_trading_end(context):
    """模拟盘每日收盘后推送一条压缩摘要；完整明细仍留在聚宽日志。"""
    _live_ensure_runtime_defaults()
    if not _live_is_sim_trade(context):
        return
    date_key = str(context.current_dt.date())
    if getattr(g, "live_daily_summary_date", None) == date_key:
        return
    metrics = _l16_margin_metrics(context)
    holdings = _actual_holdings(context)
    policy = str(getattr(g, "liquidity_policy", "data_insufficient"))
    invested_capital = float(getattr(g, "dca_initial_capital", 0.0)) + float(
        getattr(g, "dca_total_contributed", 0.0)
    )
    investment_profit = float(context.portfolio.total_value) - invested_capital
    capital_roi = (
        investment_profit / invested_capital if invested_capital > 0.0 else 0.0
    )
    message = (
        "%s 净值=%.2f 持仓=%d 政策=%s 暴露=%.1f%% 债务=%.1f%% "
        "杠杆=%.2f 目标=%.2f 累计本金=%.2f 投资损益=%.2f 本金收益率=%.2f%% "
        "新风险锁=%s 融资委托=%d/失败=%d"
        % (
            date_key,
            float(context.portfolio.total_value),
            len(holdings),
            policy,
            100.0 * float(metrics.get("gross_exposure", 0.0)),
            100.0 * float(metrics.get("debt_ratio", 0.0)),
            float(getattr(g, "leverage_multiplier", 1.0)),
            float(getattr(g, "current_target_exposure", 0.0)),
            invested_capital,
            investment_profit,
            100.0 * capital_roi,
            bool(getattr(g, "live_new_risk_blocked", False)),
            int(getattr(g, "margin_order_calls", 0)),
            int(getattr(g, "margin_order_failures", 0)),
        )
    )
    if _live_send_message(context, "收盘审计", message):
        g.live_daily_summary_date = date_key


def initialize(context):
    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)
    set_option("order_volume_ratio", 0.10)
    set_slippage(PriceRelatedSlippage(0.002), type="stock")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            min_commission=5,
        ),
        type="stock",
    )

    # LIVE-P1-3PCT：使用聚宽融资融券账户；按用户指定年利率3%回测与模拟。
    init_cash = float(context.portfolio.starting_cash)
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type="stock_margin")])
    set_option("margincash_interest_rate", 0.03)
    set_option("margincash_margin_rate", 1.00)

    g.strategy_version = "衡流 Alpha V1.8-E1-DL1.6c3e-LEV12-LIVE-P1-3PCT-DCA3000-FZ2-PRICE50-PITFIX（定投测试P1｜每月3000元｜3%融资成本）"
    g.strategy_start = date(2005, 1, 1)
    g.benchmark = "000300.XSHG"
    g.max_holdings = 8
    # Top50只用于日志监控，不参与持仓卖出。
    g.monitor_rank_cutoff = 50
    g.max_industry_holdings = 2
    g.min_core_slots = 6
    # V18E1研究版保留最多2个机构响应席位；Buffett核心始终至少保留6只。
    # 每月最多更换1只响应证券；角色晋升不产生交易，但每月也最多1只。
    g.max_response_slots = 2
    g.max_response_changes_per_month = 1
    g.max_response_role_promotions_per_month = 1
    g.response_fail_months = 2
    g.response_min_upgrade_gap = 0.05
    g.holding_roles = {}
    g.response_fail_counts = {}

    # 名义股价研究门：只约束新建证券。保持母版完整横截面排名，不做低价残差、
    # 不做小市值排序，也不在过滤后重算质量/安全/价值/总分分位。
    g.price50_entry_enabled = True
    g.price50_min_close_exclusive = 5.0
    g.price50_max_close_inclusive = 50.0
    g.price50_min_market_cap_yi = 30.0
    g.price50_st_fail_closed = True
    g.price50_financial_min_roe = 0.0
    g.price50_financial_min_roa = 0.0
    g.price50_financial_min_ocf_assets = 0.0
    g.price50_financial_max_debt_ratio = 0.75
    g.price50_financial_min_profit_growth = -30.0
    g.price50_st_query_failures = 0
    g.price50_st_missing_fields = 0
    g.price50_raw_close_query_failures = 0
    g.price50_gate_audit_months = 0

    # DL1.6a动态阶梯杠杆覆盖层。
    # 仅允许1.00/1.20/1.40/1.60；加杠杆必须经过独立周度确认，
    # 月度流程只允许保持或降杠杆，不能消耗/伪造周度确认次数。
    g.dynamic_leverage_enabled = True
    g.dynamic_leverage_levels = (1.00, 1.20, 1.40, 1.60)
    g.dynamic_leverage_min = 1.00
    g.dynamic_leverage_max = 1.60
    # 【CAP13-20260904】执行杠杆封顶（单变量改动）：内部阶梯、强deploy 2/4/6 周、
    # 回撤/债务护栏、升降档节奏全部保持母版原样；仅把实际执行的杠杆倍数
    # （g.leverage_multiplier）与最大目标暴露（g.base_target_exposure）按本上限封顶。
    g.leverage_effective_cap = 1.20
    g.dynamic_leverage_step = 0.20
    g.dynamic_leverage_increase_confirm_weeks = 2
    g.dynamic_leverage_score_improve_threshold = 2.0
    g.dynamic_leverage_fast_drop_threshold = 8.0
    g.dynamic_leverage_rebalance_band = 0.01

    # deploy不再要求分数每周继续创新高；高位稳定本身也是有效确认。
    # 连续强deploy第2/4/6周分别允许升至1.20/1.40/1.60。
    g.strong_deploy_environment_min = 80.0
    g.strong_deploy_pure_min = 75.0
    g.strong_deploy_confirmation_min = 75.0
    g.strong_deploy_to_1_20_weeks = 2
    g.strong_deploy_to_1_40_weeks = 4
    g.strong_deploy_to_1_60_weeks = 6
    g.dynamic_leverage_strong_deploy_weeks = 0
    g.dynamic_leverage_weekly_history = []
    g.dynamic_leverage_weekly_history_limit = 20
    g.dynamic_leverage_last_processed_week = None

    # 基础仓位与杠杆仓位分开维护。
    # 即使杠杆阶梯没有变化，只要实际仓位明显低于目标，也按周补现有健康持仓。
    g.base_exposure_maintenance_band = 0.05
    g.leveraged_exposure_maintenance_band = 0.03
    g.exposure_maintenance_count = 0
    g.exposure_maintenance_last_result = {}
    g.dynamic_leverage_current = 1.00
    g.dynamic_leverage_stage_age = 0
    g.dynamic_leverage_previous_policy = "warming_up"
    g.dynamic_leverage_last_weekly_policy = None
    g.dynamic_leverage_last_weekly_asof = None
    g.dynamic_leverage_last_weekly_scores = {}
    g.dynamic_leverage_policy_confirm_weeks = 0
    g.dynamic_leverage_improve_confirm_weeks = 0
    g.dynamic_leverage_recovery_lock_weeks = 2
    g.dynamic_leverage_recovery_lock_remaining = 0
    g.dynamic_leverage_last_decrease_asof = None
    g.dynamic_leverage_last_change_asof = None
    g.dynamic_leverage_last_decision = {}
    g.dynamic_leverage_change_count = 0
    g.dynamic_leverage_increase_count = 0
    g.dynamic_leverage_decrease_count = 0

    # 组合净值回撤护栏：立即降档，解除必须连续两次独立周度确认，
    # 且每次最多只恢复一个杠杆阶梯。
    # 【LEV12-20260904】执行层封顶降至1.20后，护栏在封顶空间内严格递减至地板：
    #   -6%→1.10、≤-10%→1.00（执行口径 1.20→1.10→1.00，无空转档）。
    #   CAP13(cap=1.30)的 -6%→1.20 档位在 cap=1.20 下会空转(1.20=封顶)，故下沉。
    g.portfolio_peak_net_value = None
    g.portfolio_drawdown = 0.0
    g.drawdown_guard_cap = 1.60
    g.drawdown_guard_raw_cap = 1.60
    g.drawdown_guard_release_confirm_weeks = 2
    g.drawdown_guard_release_count = 0
    g.drawdown_guard_last_release_asof = None
    g.drawdown_guard_thresholds = {
        "cap_1_10": -0.06,
        "cap_1_00": -0.10,
    }
    # 护栏细分档：1.10 不是主阶梯(1.00/1.20/1.40/1.60)的合法档位，只由回撤
    # 护栏产出。登记于此供解除阶梯识别，避免被 _nearest_legal_leverage 抹掉
    # （向上会跳到1.40、向下会压回1.00）。母版该元组为空。
    g.drawdown_guard_extra_levels = (1.10,)

    # 融资债务护栏：债务率超过45%停止新增融资；
    # 超过50%最高1.40，超过55%最高1.20。
    g.debt_ratio_block_new = 0.45
    g.debt_ratio_cap_1_40 = 0.50
    g.debt_ratio_cap_1_20 = 0.55
    g.dynamic_leverage_new_financing_blocked = False
    g.dynamic_leverage_financing_block_reasons = []
    g.latest_debt_risk_state = {}

    # 初始核心结构未形成前，只禁止新增融资订单；政策杠杆阶段仍可按周确认升档。
    g.dynamic_leverage_min_holdings_for_financing = 6
    g.dynamic_leverage_logic_version = "DL1.6c3e-lev12-strict-246-actual-exposure-audit"
    g.dynamic_leverage_build_id = "DL16C3E-LEV12-LIVE-P1-3PCT-DCA3000-20260908"
    g.dynamic_leverage_strict_246_ladder = True
    g.dynamic_leverage_candidate_gate_recalculation = True
    g.dynamic_leverage_structure_capacity_diagnostics = True
    g.dynamic_leverage_fast_drop_invariant_failures = 0
    g.dynamic_leverage_reused_snapshot_skips = 0
    g.dynamic_leverage_runtime_self_test = _dynamic_leverage_logic_self_test()
    if not g.dynamic_leverage_runtime_self_test.get("passed", False):
        raise ValueError(
            "DL1.6c3e动态杠杆启动自检失败：%s"
            % g.dynamic_leverage_runtime_self_test
        )

    # 收盘前组合仓位强制校正。
    g.exposure_reconcile_enabled = True
    g.exposure_reconcile_tolerance = 0.01
    g.exposure_reconcile_attempts = 0
    g.exposure_reconcile_failures = 0
    g.exposure_reconcile_buy_lock = False
    g.exposure_reconcile_last_result = {}
    # c3e图表缓存真实股票总暴露；绝不再用杠杆档位冒充实际杠杆。
    g.latest_actual_gross_exposure = 0.0
    g.latest_actual_gross_exposure_asof = None

    # 保留leverage_multiplier字段，供原有权重、审计和日志代码读取；
    # 该值现在表示“当前阶梯”，而不是固定常数。
    g.leverage_multiplier = min(
        float(g.dynamic_leverage_current),
        float(g.leverage_effective_cap),
    )
    g.gross_leverage_cap = g.dynamic_leverage_max
    g.margin_interest_rate = 0.03
    g.margin_cash_margin_rate = 1.00
    g.marginable_cache_date = None
    g.marginable_cache_codes = []
    g.margin_order_calls = 0
    g.margin_order_failures = 0
    g.margin_unfilled_codes = []
    g.margin_successful_order_calls = 0
    g.margin_metrics_source_counts = {
        "reported": 0,
        "inferred": 0,
        "none": 0,
    }
    g.margin_last_diagnostic = {}
    # LIVE-P0仅增加运行安全和通知状态，不参与选股、评分或仓位决策。
    g.live_notification_enabled = True
    g.live_notification_max_per_day = 3
    g.live_notify_date = None
    g.live_notify_count = 0
    g.live_daily_summary_date = None
    g.live_new_risk_blocked = False
    g.live_restart_observed = False
    g.live_last_self_check = {}
    g.live_expected_build_id = "DL16C3E-LEV12-LIVE-P1-3PCT-DCA3000-20260908"
    # 定投本金单独记账，绝不能把外部入金当成策略收益。
    g.dca_monthly_amount = 3000.0
    g.dca_initial_capital = float(init_cash)
    g.dca_total_contributed = 0.0
    g.dca_contribution_count = 0
    g.dca_contribution_failures = 0
    g.dca_last_contribution_month = None
    g.financing_gate_status = "not_required"
    g.financing_gate_reasons = []
    g.financing_gate_warning_reasons = []
    g.available_margin_zero_is_diagnostic_only = True
    log.info(
        "动态杠杆逻辑版本：%s；构建=%s；政策阶段与融资执行门已解耦；"
        "显式差值判定自检=%s；全局any覆盖=%s/all覆盖=%s。"
        % (
            g.dynamic_leverage_logic_version,
            g.dynamic_leverage_build_id,
            g.dynamic_leverage_runtime_self_test.get("passed"),
            g.dynamic_leverage_runtime_self_test.get("global_any_shadowed"),
            g.dynamic_leverage_runtime_self_test.get("global_all_shadowed"),
        )
    )

    # base_target_exposure和单股上限继续按最大可用暴露设置，
    # 实际每期目标由“E1政策仓位×当前动态杠杆”决定。
    g.unlevered_base_target_exposure = 1.00
    g.base_target_exposure = (
        g.unlevered_base_target_exposure
        * min(g.dynamic_leverage_max, g.leverage_effective_cap)
    )
    g.current_target_exposure = 0.75
    g.rebalance_band = 0.02
    # 组合总仓位执行保险：单股调仓带只能减少无意义交易，不能让多只小幅超配累计成组合超仓。
    # 提交订单后的预计股票仓位最多高于整手计划0.5个百分点；整手计划本身仍受当前动态杠杆政策目标约束。
    g.exposure_guard_enabled = True
    g.portfolio_exposure_tolerance = 0.005
    # c3e仅用于收盘审计提示：相对整手计划超过1个百分点才记INFO；
    # 政策硬风险线仍沿用0.5个百分点执行容差。
    g.close_exposure_notice_buffer = 0.01
    # WATCH腾出的额度转配健康核心时使用更窄的阈值，否则1%至2%的补仓会被普通调仓带跳过。
    g.watch_reallocation_band = 0.005
    # 因子WATCH仓不再只是不加仓，而是月度主动压到8%以内；价格-10%观察本身仍只禁止加仓。
    g.watch_max_weight = 0.08
    # 整手二次分配只处理由100股向下取整造成的零散现金，不突破目标总暴露和单股上限。
    g.lot_reallocation_enabled = True
    g.lot_reallocation_max_rounds = 50
    g.lot_reallocation_weight_tolerance = 0.002
    g.min_listing_days = 365 * 3
    g.fundamental_pool_size = 240
    g.lookback = 252
    g.min_price_observations = 160
    g.min_avg_money = 20000000.0
    g.max_lot_to_target_ratio = 1.05
    g.weekly_candidate_count = 50
    g.weekly_daily_count = 500
    g.weekly_min_bars = 60
    g.trend_fast = 5
    g.trend_slow = 20
    g.trend_angle_points = 5
    g.trend_min_angle = 15.0
    g.trend_boll_period = 20
    g.trend_boll_angle_points = 5
    g.trend_boll_min_angle = -15.0
    # 核心新买入过渡区：快线已经站上慢线，或长趋势中轨已转平向上且价格站回中轨。
    # 这是买入资格，不用于机械卖出已有的基本面健康持仓。
    g.core_recovery_boll_min_angle = 0.0
    # V18E1研究版冻结质量/安全/价值门槛。机构响应候选也必须先通过同一套
    # Buffett与常态利润门槛，机构风向不能成为绕过基本面的捷径。
    g.entry_min_quality_rank = 0.55
    g.entry_min_safety_rank = 0.55
    g.entry_min_value_rank = 0.30
    g.entry_min_total_rank = 0.55
    g.entry_rank_limit = 30
    g.entry_max_beta = 1.05

    # 常态利润准入：避免把疫情、资源品等单年利润高峰同时误判为“高质量+低估值”。
    # 只约束新买入，不因历史数据短暂缺失机械卖出已有持仓。
    g.normalized_earnings_years = 5
    g.normalized_earnings_batch_size = 200
    g.normalized_earnings_top_count = 80
    g.entry_min_earnings_years = 3
    g.entry_min_positive_year_ratio = 0.80
    g.entry_max_normalized_pe = 35.0
    g.entry_max_profit_peak_ratio = 3.00
    # 单股上限随杠杆阶段变化，但初始核心结构未形成前固定为15.33%。
    # 1.40/1.60阶段硬上限统一封顶20%，避免两三只股票承载过多杠杆。
    g.unlevered_single_weight_cap = 0.92 / g.min_core_slots
    g.dynamic_single_weight_caps = {
        1.00: g.unlevered_single_weight_cap,
        1.20: 0.184,
        1.40: 0.20,
        1.60: 0.20,
    }
    g.max_single_weight = 0.20

    # 空账户分阶段建仓：第1个月最多形成3只，第2个月5只，第3个月6只。
    # 只有实际持仓达到6只后，才结束初始阶段并允许后续逐步扩展到8只。
    g.initial_build_enabled = True
    g.initial_build_target_counts = (3, 5, 6)
    g.initial_build_stage = 0
    g.initial_build_last_month = None
    g.initial_build_completed = False
    g.initial_build_effective_cap = g.max_holdings

    # 持仓缓冲：比买入宽松，连续两个月跌破才确认因子失效。
    g.hold_min_quality_rank = 0.40
    g.hold_min_safety_rank = 0.40
    g.hold_min_value_rank = 0.15
    g.hold_min_total_rank = 0.40
    g.hold_max_beta = 1.10
    g.immediate_beta_exit = 1.30
    g.factor_fail_months = 2
    g.factor_fail_counts = {}
    g.factor_fail_reasons = {}
    # WATCH席位治理不是月度排名淘汰赛。只有长期且严重失效，并且存在显著更优候选时才替换。
    g.watch_replacement_enabled = True
    g.watch_replacement_min_months = 4
    g.watch_replacement_max_per_month = 1
    g.watch_replacement_max_quality_rank = 0.15
    g.watch_replacement_max_total_rank = 0.20
    g.watch_replacement_min_score_gap = 0.10
    g.watch_replacement_count_this_month = 0
    g.watch_replacement_history = {}
    # 横截面分位跌破先进入观察；短期排名变化仍不触发核心仓之间的淘汰赛。

    # 组合层面低Beta护栏。0.85是目标，0.90是新买入后的上限。
    g.portfolio_beta_target = 0.85
    g.portfolio_beta_ceiling = 0.90
    # 股票仓内部Beta门槛仍为0.90；含杠杆账户Beta审计上限同步乘以1.60。
    g.leveraged_account_beta_ceiling = g.portfolio_beta_ceiling * g.dynamic_leverage_max
    # 扩张环境只通过响应席位温和提高组合Beta；绝不为追Beta卖掉健康核心仓。
    g.deploy_beta_floor = 0.55
    g.selective_beta_floor = 0.45

    # 买入后只要一个“新的财报期”满足实质恶化定义，就立即退出。
    # 实质恶化仍要求同一报告中至少两个独立恶化信号，避免单指标噪声误卖。
    g.fundamental_bad_reports_required = 1
    g.fundamental_soft_signals_required = 2
    g.holding_thesis_states = {}
    g.holding_fundamental_baselines = {}
    g.holding_report_states = {}
    # 财报退出版本锁独立于持仓状态，卖出后不会被_clear_holding_state清除。
    g.fundamental_exit_report_locks = {}
    g.pending_fundamental_exit_reports = {}
    g.latest_fundamental_lock_health = {}
    g.latest_holding_health = {}
    g.valuation_extreme_counts = {}
    g.valuation_extreme_months = 2
    g.pending_exit_reasons = {}

    # 止损是灾难风险安全阀，而不是日常卖出主逻辑。
    g.stop_watch_loss = -0.10
    g.stop_confirm_loss = -0.15
    g.stop_disaster_loss = -0.20
    g.stop_watch_logged = {}

    # V18E1研究版保留机构基金主线，但采用严格fail-closed：只有可比基金季度数据
    # 与当期价格容量同时可用时，才允许生成响应候选。
    g.mainline_enabled = True
    g.institution_fail_closed = True
    g.institution_actionable_modes = ("FUND_PRICE_CONFIRMED",)
    g.latest_mainline_mode = "INITIALIZING"
    g.latest_mainline_meta = {}
    g.response_role_promotions_this_month = 0
    g.response_role_demotions_this_month = 0
    g.response_security_changes_this_month = 0
    g.mainline_core_count = 3
    g.mainline_candidate_count = 5
    g.mainline_core_score = 65.0
    g.mainline_candidate_score = 55.0
    g.mainline_observe_score = 45.0
    g.mainline_confirm_months = 2
    g.industry_score_history = {}
    g.industry_confirm_counts = {}
    g.industry_states = {}
    g.latest_industry_scores = {}
    g.latest_industry_members = {}
    # 机构表只按单季度显式分页。清洗完成的季度快照跨月复用，避免每月重读数万行。
    g.fund_snapshot_cache = {}
    g.fund_quarter_meta_cache = {}
    g.fund_quarter_negative_cache = set()
    # Memory-Safe性能层：这里只记录当前活动pair的季度字符串。普通月份直接复用
    # 两个滚动季度快照，不访问基金主体表或持仓表，也不长期保存重复拼接大表。
    g.fund_selected_pair_cache = {}
    g.fund_last_selected_pair = None
    g.fund_quarter_retry_after = {}
    g.fund_query_stats = {
        "quarter_queries": 0,
        "quarter_cache_hits": 0,
        "pair_cache_hits": 0,
        "early_stops": 0,
        "retry_skips": 0,
        "disclosure_window_skips": 0,
    }
    g.active_fund_codes_cache = None
    g.all_fund_codes_cache = None
    g.fund_main_info_meta = {}
    # PIT-FIX：FUND_MAIN_INFO 原始帧缓存（只在首次调用时取数一次）。
    g.fund_main_frame_cache = None
    g.fund_main_frame_meta = {}
    g.pit_fix_derived_active_last = {}
    # V18E1研究版继续自动识别聚宽基金表字段。主体表仍必须成功提供基金代码和名称；
    # 分类字段可使用当前字符串字段，也兼容旧版数值ID字段。
    g.fund_schema_adapter_enabled = True
    g.fund_main_field_map = {}
    g.fund_holding_field_map = {}
    g.fund_holding_schema_cache = None
    g.fund_schema_diagnostics_logged = set()
    g.latest_fund_selection_meta = {}
    g.latest_fund_load_meta = {}
    g.fund_page_size = 5000
    g.fund_max_rows_per_quarter = 250000
    g.fund_max_main_info_rows = 150000
    # 6个季度只是异常情况下的回退上限；正常首次运行找到两个可比季度后立即早停。
    g.fund_max_quarters_to_scan = 6
    # Memory-Safe工程层：只约束缓存生命周期，不进入E1参数指纹和交易决策。
    g.fund_snapshot_cache_limit = 2
    g.fund_selected_pair_cache_limit = 1
    g.fund_auxiliary_key_limit = max(8, int(g.fund_max_quarters_to_scan) + 2)
    g.fund_cache_audit_enabled = True
    g.fund_cache_last_audit = {}
    g.memory_safe_version = "V1.8-E1-DL1.6c3e Memory-Safe 1.0"
    # 基金季度末刚过去时不会立即查询空表。按月调仓下，20天窗口意味着通常在
    # 下一月首个交易日读取新季报；失败后至少21天才允许再次尝试。
    g.fund_quarter_min_query_age_days = 20
    g.fund_monthly_quarter_query_limit = 2
    g.fund_quarter_retry_days = 21
    g.fund_min_a_share_rows = 500
    g.fund_min_valid_funds = 50
    g.fund_signal_min_valid_funds = 1000
    g.fund_min_stocks_per_fund = 4
    g.fund_min_disclosed_weight = 10.0
    g.fund_min_relative_coverage = 0.75
    g.fund_min_market_value_coverage = 0.80
    g.fund_min_comparable_funds = 1000
    g.market_price_sample_per_industry = 35
    g.capacity_daily_count = 260
    g.capacity_min_stocks = 5
    g.mainline_min_industries = 3
    # 超过180天的基金持仓不再参与响应层；价格容量只能做确认，不能单独发信号。
    g.mainline_max_fund_age_days = 180

    # ===== PIT-FIX 未来函数修复配置（2026-09-02，依据基金层审计报告确定项）=====
    # 只动基金样本构建与主动判定；不改任何评分权重、覆盖门槛数值与交易参数。
    g.pit_fix_version = "PIT-FIX-P0-20260902"
    # F-1/F-2/F-4：FUND_MAIN_INFO 按 start_date/end_date 做点时过滤（常开；
    # 置 False 可完全恢复原行为用于基线 A/B）。
    g.pit_fix_date_filter = True
    # F-3：主动偏股判定由当季已披露持仓推导（点时安全），默认开。
    g.pit_fix_holdings_derived_active = True
    # 诊断日志：每个 asof 输出 PIT_FIX_FUND_MAIN，量化修复前后口径差。
    g.pit_fix_diagnostics = True

    # V18E1研究版冻结使用已验收的流动性V4行动节奏：正常目标仓位仍为92%，普通环境只控制新增证券速度；
    # 只有至少两个独立硬风险同时成立，才允许周中只减仓、不换股。
    g.liquidity_controls_enabled = True
    g.extreme_risk_state = "normal"
    g.extreme_risk_trigger_count = 0
    g.extreme_risk_release_count = 0
    g.extreme_risk_last_asof = None
    g.current_target_exposure = g.base_target_exposure
    g.liquidity_index_codes = ["000300.XSHG", "000905.XSHG"]
    g.liquidity_price_index = "399006.XSHE"
    g.liquidity_daily_count = 360
    g.liquidity_percentile_window = 252
    g.liquidity_percentile_min = 120
    g.liquidity_pure_weights = {
        "activity": 0.40, "amihud": 0.40, "financing": 0.20
    }
    g.liquidity_environment_weights = {"pure": 0.65, "confirmation": 0.35}
    g.liquidity_weekly_history = []
    g.liquidity_macro_state = "warming_up"
    g.liquidity_macro_candidate = None
    g.liquidity_macro_candidate_count = 0
    g.liquidity_macro_state_age = 0
    g.liquidity_macro_confirm_weeks = 2
    g.liquidity_last_snapshot = None
    g.liquidity_policy = "warming_up"
    g.liquidity_policy_age = 0
    g.liquidity_previous_policy = None
    g.liquidity_risk_candidate = None
    g.liquidity_risk_candidate_count = 0
    g.liquidity_risk_confirm_weeks = 2
    # 行动政策只控制“新增证券数量”，不改变Buffett排序和健康核心持有逻辑。
    # deploy允许填满本阶段空位；selective最多2只；freeze最多1只；defense禁止新增。
    g.liquidity_policy_new_buy_limits = {
        "deploy": g.max_holdings,
        "selective": 2,
        # FZ2：Freeze发现机会但不立即建立新证券风险；候选进入Deferred Pool。
        "freeze": 0,
        "defense": 0,
        "warming_up": 1,
        "data_insufficient": 1,
    }
    g.fz2_deferred_enabled = True
    g.fz2_deferred_pool = {}
    g.fz2_release_pending = False
    # 本次释放窗口是否已经完成月度重验。即使没有候选通过，窗口也必须消费，
    # 避免旧的 Freeze->Selective 触发跨月残留并反复重验。
    g.fz2_release_evaluated = False
    g.fz2_release_trigger = {}
    g.fz2_release_active_codes = []
    g.fz2_capture_limit = int(g.entry_rank_limit)
    g.fz2_event_count = 0
    # 【LEV12-20260904】deploy 满仓 1.00；杠杆仅限 deploy（顶档 1.20）。
    # selective/freeze/defense 政策仓位保持 75%/50%/20%，且不融资。
    # DL1.6只在执行层乘以当前动态杠杆，不改变政策信号本身。
    g.policy_target_exposure = {
        "deploy": 1.00,
        "selective": 0.75,
        "freeze": 0.50,
        "defense": 0.20,
        "warming_up": 0.75,
        "data_insufficient": 0.50,
        "core_baseline": 1.00,
    }
    g.effective_allocation_policy = "warming_up"
    g.latest_allocation_policy_reasons = []
    g.latest_fast_deterioration_flags = {}

    # E2：主线对齐是权重强化层，不扩大纯response上限，也不强卖健康核心。
    g.mainline_alignment_enabled = False
    g.mainline_enhancement_targets = {
        "deploy": 6,
        "selective": 2,
        "freeze": 0,
        "defense": 0,
        "warming_up": 0,
        "data_insufficient": 0,
    }
    g.mainline_enhancement_multiplier = 1.25
    g.pending_mainline_enhanced_codes = []

    # E3：主线质量否决虚假deploy、基金证据按年龄衰减、快速恶化只降级不升级。
    g.mainline_deploy_veto_enabled = False
    g.fast_deterioration_enabled = False
    g.fund_age_decay_enabled = False
    g.deploy_gate_min_mainlines = 4
    g.deploy_gate_min_core_mainlines = 2
    g.deploy_gate_min_top5_confirmed = 3
    g.deploy_gate_min_relative_strength = 0.0
    g.deploy_gate_min_breadth = 0.55
    g.mainline_deploy_gate = {"available": False, "passed": False, "reason": "initializing"}

    # E4：新增响应先半权重试用，产生正相对收益后转完整权重；三个月不通过则退出或严格晋升核心。
    g.response_probation_enabled = False
    g.response_probation_weight_factor = 0.50
    g.response_probation_validate_after_months = 1
    g.response_probation_max_months = 3
    g.response_core_upgrade_rank_limit = 30
    g.response_probation_states = {}
    g.response_relative_return_cache = {}
    g.experiment_code = "FZ2-PRICE50-V1"
    g.experiment_log_tag = "FZ2-PRICE50-V1"
    # 独立硬风险：2项同时成立降至50%，3项及以上降至20%；连续2周解除后，
    # 只在下一个月度调仓日恢复92%，不在周中追涨恢复。
    g.extreme_risk_min_flags = 2
    g.extreme_risk_severe_flags = 3
    g.extreme_risk_exposure = 0.50
    g.extreme_risk_severe_exposure = 0.20
    g.extreme_risk_release_weeks = 2
    g.max_new_buys_this_month = 0
    g.effective_new_buy_budget = 0

    # 风险退出后封锁下一个完整月，避免刚止损又在下个选股日立即买回。
    g.reentry_cooldown_months = 1
    g.reentry_cooldowns = {}

    # BOLL与有效低点只用于估值/风险复核，不再因上轨后回撤5%机械卖出优质公司。
    g.boll_weekly_period = 20
    g.boll_std = 2.0
    g.pivot_left = 2
    g.pivot_right = 2
    g.exit_daily_count = 260
    g.last_rebalance_month = None
    g.pending_ranked = []
    g.pending_entry_ranked = []
    g.pending_core_entry_ranked = []
    g.pending_response_entry_ranked = []
    g.pending_scores = {}
    g.pending_targets = []
    g.pending_target_weights = {}
    g.pending_raw_target_weights = {}
    g.pending_planned_exposure = 0.0
    g.pending_planned_equity_beta = np.nan
    g.pending_planned_account_beta = np.nan
    g.pending_rounding_redeploy_value = 0.0
    g.pending_pre_trade_exposure = 0.0
    g.pending_projected_post_order_exposure = 0.0
    g.pending_exposure_guard_ceiling = 0.0
    g.pending_exposure_band_bypass_sells = []
    g.pending_buy_lots_blocked_by_exposure_guard = 0
    g.pending_locked_exposure = 0.0

    # E1-DL1.6c3e-CAP13研究版：以V1.8-E1为唯一行为基线，叠加基金层PIT修复；
    # 动态阶梯状态机保持原样，仅执行杠杆封顶1.30倍。
    # 以下状态只用于回归审计和净值检查点，不参与选股、仓位或下单。
    g.release_channel = "research"
    g.release_behavior_baseline = "V1.8-E1"
    g.release_parameter_lock = False
    g.release_retrospective_tuning = False
    g.release_runtime_audit_enabled = True
    g.release_initial_value = float(context.portfolio.total_value)
    g.release_peak_value = float(context.portfolio.total_value)
    g.release_audit_months = 0
    g.release_audit_failures = 0
    g.release_audit_warnings = 0
    g.release_config_snapshot = {}
    g.release_parameter_fingerprint = None

    v171_config = {
        "version": g.strategy_version,
        "institution_enabled": bool(g.mainline_enabled),
        "institution_fail_closed": bool(g.institution_fail_closed),
        "liquidity_timing_enabled": bool(g.liquidity_controls_enabled),
        "response_slots": int(g.max_response_slots),
        "core_slots_min": int(g.min_core_slots),
        "holdings_max": int(g.max_holdings),
        "target_exposure": float(g.base_target_exposure),
        "max_single_weight": float(g.max_single_weight),
        "watch_max_weight": float(g.watch_max_weight),
        "leverage_overlay": {
            "mode": "dynamic_step_1.0_to_1.6_cap_1.2_deploy_only",
            "effective_cap": float(g.leverage_effective_cap),
            "current_multiplier": float(g.leverage_multiplier),
            "levels": list(g.dynamic_leverage_levels),
            "min_multiplier": float(g.dynamic_leverage_min),
            "max_multiplier": float(g.dynamic_leverage_max),
            "step": float(g.dynamic_leverage_step),
            "increase_confirm_weeks": int(
                g.dynamic_leverage_increase_confirm_weeks
            ),
            "score_improve_threshold": float(
                g.dynamic_leverage_score_improve_threshold
            ),
            "fast_drop_threshold": float(
                g.dynamic_leverage_fast_drop_threshold
            ),
            "logic_build_id": str(g.dynamic_leverage_build_id),
            "explicit_delta_logic": True,
            "strict_246_deploy_ladder": bool(
                g.dynamic_leverage_strict_246_ladder
            ),
            "candidate_multiplier_gate_recalculation": bool(
                g.dynamic_leverage_candidate_gate_recalculation
            ),
            "structure_capacity_diagnostics": bool(
                g.dynamic_leverage_structure_capacity_diagnostics
            ),
            "nonweekly_reused_snapshot_score_reassessment": False,
            "runtime_self_test": dict(g.dynamic_leverage_runtime_self_test),
            "gross_leverage_cap": float(g.gross_leverage_cap),
            "margin_interest_rate": float(g.margin_interest_rate),
            "margin_cash_margin_rate": float(g.margin_cash_margin_rate),
            "account_type": "stock_margin",
            "marginable_only": True,
            "increase_existing_healthy_holdings_only": True,
            "slow_up_fast_down": True,
            "defense_and_freeze_no_financing": True,
            "monthly_increase_disabled": True,
            "unique_weekly_confirmation": True,
            "strong_deploy_confirmation": {
                "environment_min": float(g.strong_deploy_environment_min),
                "pure_liquidity_min": float(g.strong_deploy_pure_min),
                "market_confirmation_min": float(
                    g.strong_deploy_confirmation_min
                ),
                "to_1_20_weeks": int(g.strong_deploy_to_1_20_weeks),
                "to_1_40_weeks": int(g.strong_deploy_to_1_40_weeks),
                "to_1_60_weeks": int(g.strong_deploy_to_1_60_weeks),
            },
            "exposure_maintenance": {
                "base_band": float(g.base_exposure_maintenance_band),
                "leveraged_band": float(
                    g.leveraged_exposure_maintenance_band
                ),
                "existing_healthy_holdings_only": True,
            },
            "debt_metric": {
                "reported_field_aliases": True,
                "economic_inference_fallback": True,
                "missing_available_margin_is_warning_not_hard_block": True,
                "zero_available_margin_is_diagnostic_not_pretrade_block": True,
            },
            "weekly_state_engine": {
                "dedicated_weekly_asof": True,
                "independent_from_extreme_risk_last_asof": True,
                "history_based_consecutive_count": True,
                "history_limit": int(g.dynamic_leverage_weekly_history_limit),
            },
            "stage_execution_decoupling": {
                "policy_stage_can_exceed_1x_before_order_attempt": True,
                "financing_order_api_is_execution_authority": True,
                "target_exposure_kept_visible_when_execution_blocked": True,
                "gate_uses_candidate_multiplier": True,
                "policy_and_structure_targets_logged_separately": True,
            },
            "recovery_lock_weeks": int(g.dynamic_leverage_recovery_lock_weeks),
            "min_holdings_for_financing": int(
                g.dynamic_leverage_min_holdings_for_financing
            ),
            "dynamic_single_weight_caps": {
                str(key): float(value)
                for key, value in g.dynamic_single_weight_caps.items()
            },
            "watch_weight_cap": float(g.watch_max_weight),
            "drawdown_guard": {
                "thresholds": dict(g.drawdown_guard_thresholds),
                "release_confirm_weeks": int(
                    g.drawdown_guard_release_confirm_weeks
                ),
            },
            "debt_guard": {
                "block_new_ratio": float(g.debt_ratio_block_new),
                "cap_1_40_ratio": float(g.debt_ratio_cap_1_40),
                "cap_1_20_ratio": float(g.debt_ratio_cap_1_20),
                "missing_available_margin_blocks_new_financing": True,
            },
            "exposure_reconcile": {
                "enabled": bool(g.exposure_reconcile_enabled),
                "time": "14:45",
                "tolerance": float(g.exposure_reconcile_tolerance),
                "unresolved_gap_blocks_all_buys": True,
            },
        },
        "institution_response": {
            "actionable_modes": list(g.institution_actionable_modes),
            "max_response_slots": int(g.max_response_slots),
            "max_security_changes_per_month": int(g.max_response_changes_per_month),
            "max_role_promotions_per_month": int(g.max_response_role_promotions_per_month),
            "response_fail_months": int(g.response_fail_months),
            "mainline_confirm_months": int(g.mainline_confirm_months),
            "mainline_min_industries": int(g.mainline_min_industries),
            "max_fund_age_days": int(g.mainline_max_fund_age_days),
            "min_signal_funds": int(g.fund_signal_min_valid_funds),
            "min_comparable_funds": int(g.fund_min_comparable_funds),
            "min_relative_coverage": float(g.fund_min_relative_coverage),
            "min_market_value_coverage": float(g.fund_min_market_value_coverage),
            "fund_weight": 0.60,
            "capacity_weight": 0.30,
            "diffusion_weight": 0.10,
            "capacity_only_actionable": False,
            "schema_adapter_enabled": bool(g.fund_schema_adapter_enabled),
            "main_field_alias_compatible": True,
            "holding_field_alias_compatible": True,
            "quarter_early_stop": True,
            "selected_pair_cache_enabled": True,
            "quarter_min_query_age_days": int(g.fund_quarter_min_query_age_days),
            "quarter_retry_days": int(g.fund_quarter_retry_days),
            "monthly_quarter_query_limit": int(
                g.fund_monthly_quarter_query_limit
            ),
            "max_quarters_to_scan_fallback": int(g.fund_max_quarters_to_scan),
        },
        "watch_replacement": {
            "enabled": bool(g.watch_replacement_enabled),
            "min_months": int(g.watch_replacement_min_months),
            "max_per_month": int(g.watch_replacement_max_per_month),
            "max_quality_rank": float(g.watch_replacement_max_quality_rank),
            "max_total_rank": float(g.watch_replacement_max_total_rank),
            "min_score_gap": float(g.watch_replacement_min_score_gap),
        },
        "weighted_beta_guard": True,
        "lot_reallocation_enabled": bool(g.lot_reallocation_enabled),
        "exposure_guard": {
            "enabled": bool(g.exposure_guard_enabled),
            "tolerance": float(g.portfolio_exposure_tolerance),
            "sell_before_buy": True,
            "band_bypass_when_needed": True,
            "per_order_projected_exposure_check": True,
        },
        "initial_build_targets": list(g.initial_build_target_counts),
        "liquidity_action": {
            "model_version": "V4.0.1_BUFFETT_POLICY",
            "new_buy_limits": dict(g.liquidity_policy_new_buy_limits),
            "risk_flags": int(g.extreme_risk_min_flags),
            "severe_flags": int(g.extreme_risk_severe_flags),
            "risk_exposure": float(g.extreme_risk_exposure),
            "severe_exposure": float(g.extreme_risk_severe_exposure),
            "release_weeks": int(g.extreme_risk_release_weeks),
            "normal_target_exposure": float(g.base_target_exposure),
            "risk_signal_source": "raw_stress_flags",
            "policy_signal_source": "confirmed_action_policy",
        },
        "entry_thresholds": {
            "quality": float(g.entry_min_quality_rank),
            "safety": float(g.entry_min_safety_rank),
            "value": float(g.entry_min_value_rank),
            "total": float(g.entry_min_total_rank),
            "beta_max": float(g.entry_max_beta),
        },
        "price50_entry": {
            "enabled": bool(g.price50_entry_enabled),
            "price_source": "previous_trading_day_unadjusted_close_fq_none",
            "minimum_close_yuan_exclusive": float(
                g.price50_min_close_exclusive
            ),
            "maximum_close_yuan_inclusive": float(
                g.price50_max_close_inclusive
            ),
            "minimum_market_cap_yi": float(g.price50_min_market_cap_yi),
            "maximum_market_cap_yi": None,
            "ranking_policy": "preserve_full_mother_cross_section_no_rerank",
            "holding_policy": "entry_only_no_forced_exit_above_50",
            "leverage_topup_policy": "existing_healthy_holdings_not_price_gated",
            "st_policy": "point_in_time_fail_closed",
            "financial_nonfinancial": {
                "roe_min": float(g.price50_financial_min_roe),
                "roa_min": float(g.price50_financial_min_roa),
                "profit_growth_min_pct": float(
                    g.price50_financial_min_profit_growth
                ),
                "ocf_assets_min": float(g.price50_financial_min_ocf_assets),
                "debt_ratio_max": float(g.price50_financial_max_debt_ratio),
            },
            "financial_sector": {
                "roe_min": float(g.price50_financial_min_roe),
                "roa_min": float(g.price50_financial_min_roa),
                "profit_growth_min_pct": float(
                    g.price50_financial_min_profit_growth
                ),
                "industrial_cashflow_and_debt_gate_exempt": True,
            },
        },
    }
    v171_config["formal_release"] = {
        "channel": str(g.release_channel),
        "behavior_baseline": str(g.release_behavior_baseline),
        "parameter_lock": bool(g.release_parameter_lock),
        "retrospective_tuning": bool(g.release_retrospective_tuning),
        "runtime_audit_enabled": bool(g.release_runtime_audit_enabled),
        "behavior_change_from_baseline": True,
        "experiment_code": str(g.experiment_code),
        "policy_target_exposure": dict(g.policy_target_exposure),
        "mainline_alignment_enabled": bool(g.mainline_alignment_enabled),
        "mainline_deploy_veto_enabled": bool(g.mainline_deploy_veto_enabled),
        "response_probation_enabled": bool(g.response_probation_enabled),
    }
    fingerprint_payload = json.dumps(
        v171_config, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    g.release_config_snapshot = dict(v171_config)
    g.release_parameter_fingerprint = hashlib.sha256(
        fingerprint_payload.encode("utf-8")
    ).hexdigest()
    release_failures = (
        _validate_formal_release_config(v171_config)
        if g.release_parameter_lock else []
    )
    if release_failures:
        raise ValueError(
            "V18E1研究版参数锁失败：%s" % "；".join(release_failures)
        )

    if g.release_parameter_lock and (
        not v171_config["institution_enabled"]
        or not v171_config["institution_fail_closed"]
        or not v171_config["liquidity_timing_enabled"]
        or v171_config["response_slots"] != 2
        or v171_config["core_slots_min"] != 6
        or v171_config["holdings_max"] != 8
    ):
        raise ValueError(
            "V18E1研究版配置异常：必须启用fail-closed机构层、保留流动性V4，"
            "并维持6个核心+最多2个响应席位"
        )
    v171_config["formal_release"]["parameter_fingerprint"] = (
        g.release_parameter_fingerprint
    )
    log.info("V18E1LEV12_CONFIG|%s" % json.dumps(v171_config, ensure_ascii=False, sort_keys=True))

    run_monthly(
        monthly_cash_contribution,
        monthday=1,
        time="before_open",
        reference_security=g.benchmark,
    )
    run_monthly(
        monthly_rebalance,
        monthday=1,
        time="open",
        reference_security=g.benchmark,
    )
    run_monthly(
        monthly_after_close,
        monthday=1,
        time="after_close",
        reference_security=g.benchmark,
    )
    run_daily(
        daily_exposure_and_leverage_guard,
        time="14:45",
        reference_security=g.benchmark,
    )
    run_daily(
        daily_holding_risk_exit,
        time="14:50",
        reference_security=g.benchmark,
    )
    if g.liquidity_controls_enabled:
        run_weekly(
            weekly_extreme_risk_check,
            weekday=1,
            time="10:00",
            reference_security=g.benchmark,
        )
    log.info(
        g.strategy_version + "初始化：研究分支=%s；A版即时结构止损保持不变；"
        "未杠杆政策仓位=100%%/75%%/50%%/20%%；杠杆阶梯=1.00/1.20/1.40/1.60；"
        "慢加快减，freeze/defense/selective不融资，杠杆仅限deploy、执行封顶1.20；"
        "月度不升杠杆、独立周度确认、降档后锁定2周；"
        "强deploy严格连续2/4/6周升至1.20/1.40/1.60，"
        "不允许方向改善分支提前升档；"
        "强deploy周数由ISO周历史反推，不依赖易失累加器；"
        "融资门使用最终候选杠杆即时重算，"
        "并分列政策目标与当前结构可执行目标；"
        "周度杠杆引擎与月度极端风险asof完全解耦；"
        "基础仓位缺口和杠杆仓位缺口均按周维护；"
        "初始6只前禁融资、单股最高20%%、WATCH固定8%%；"
        "组合回撤/债务率/14:45仓位校正护栏全部启用；"
        "债务率采用平台报告值与经济推算值双口径；"
        "available_margin为0或缺失只告警，不再预先封死融资订单；"
        "主线强化=%s，deploy/selective强化名额=6/2；虚假risk-on否决=%s；"
        "响应三个月试用=%s；纯响应席位仍最多2只，Buffett与财报门槛不变；"
        "本轮未合并B版三日止损、ETF资产层和历史稀疏负缓存；"
        "已合并Memory-Safe；默认关闭且不参与交易的Q0观察器已移出主文件归档。"
        % (
            g.experiment_code,
            g.mainline_alignment_enabled,
            g.mainline_deploy_veto_enabled,
            g.response_probation_enabled,
        )
    )
def _validate_formal_release_config(config):
    """验证正式版关键参数；只在初始化阶段执行，不改变交易行为。"""
    failures = []
    expected = {
        "holdings_max": 8,
        "core_slots_min": 6,
        "response_slots": 2,
        "target_exposure": 1.00 * 1.20,
        "max_single_weight": 0.20,
        "watch_max_weight": 0.08,
    }
    for key, value in expected.items():
        actual = config.get(key)
        if isinstance(value, float):
            try:
                matched = abs(float(actual) - value) <= 1e-12
            except Exception:
                matched = False
        else:
            matched = actual == value
        if not matched:
            failures.append("%s=%s，预期%s" % (key, actual, value))

    institution = config.get("institution_response", {})
    institution_expected = {
        "max_response_slots": 2,
        "max_security_changes_per_month": 1,
        "max_role_promotions_per_month": 1,
        "mainline_confirm_months": 2,
        "mainline_min_industries": 3,
        "max_fund_age_days": 180,
        "min_signal_funds": 1000,
        "min_comparable_funds": 1000,
        "quarter_min_query_age_days": 20,
        "quarter_retry_days": 21,
    }
    for key, expected_value in institution_expected.items():
        if institution.get(key) != expected_value:
            failures.append(
                "institution_response.%s=%s，预期%s"
                % (key, institution.get(key), expected_value)
            )
    if institution.get("actionable_modes") != ["FUND_PRICE_CONFIRMED"]:
        failures.append("机构响应可行动模式必须仅为FUND_PRICE_CONFIRMED")
    if institution.get("capacity_only_actionable") is not False:
        failures.append("价格容量不得脱离基金证据单独发出响应信号")

    liquidity = config.get("liquidity_action", {})
    liquidity_expected = {
        "risk_flags": 2,
        "severe_flags": 3,
        "risk_exposure": 0.50,
        "severe_exposure": 0.20,
        "release_weeks": 2,
        "normal_target_exposure": 1.00 * 1.20,
        "risk_signal_source": "raw_stress_flags",
        "policy_signal_source": "confirmed_action_policy",
    }
    for key, expected_value in liquidity_expected.items():
        actual = liquidity.get(key)
        if isinstance(expected_value, float):
            try:
                matched = abs(float(actual) - expected_value) <= 1e-12
            except Exception:
                matched = False
        else:
            matched = actual == expected_value
        if not matched:
            failures.append(
                "liquidity_action.%s=%s，预期%s"
                % (key, actual, expected_value)
            )

    release = config.get("formal_release", {})
    if release.get("channel") != "formal":
        failures.append("正式版channel必须为formal")
    if release.get("behavior_baseline") != "V1.7.0b":
        failures.append("正式版行为基线必须为V1.7.0b")
    if release.get("parameter_lock") is not True:
        failures.append("正式版必须启用参数锁")
    if release.get("retrospective_tuning") is not False:
        failures.append("正式版禁止回看调参")
    if release.get("behavior_change_from_baseline") is not False:
        failures.append("V1.7.1不得改变V1.7.0b交易行为")
    return failures


def _exposure_audit_thresholds(planned_exposure):
    """分离计划偏差提示线与政策硬风险线；只影响日志等级。"""
    policy_target = max(
        0.0, float(getattr(g, "current_target_exposure", 0.0))
    )
    try:
        planned = float(planned_exposure)
    except (TypeError, ValueError):
        planned = policy_target
    if not np.isfinite(planned):
        planned = policy_target
    planned = max(0.0, planned)
    notice_buffer = max(
        0.0, float(getattr(g, "close_exposure_notice_buffer", 0.01))
    )
    hard_tolerance = max(
        0.0, float(getattr(g, "portfolio_exposure_tolerance", 0.005))
    )
    return {
        "planned_notice_ceiling": planned + notice_buffer,
        "policy_hard_ceiling": policy_target + hard_tolerance,
    }


def _formal_release_runtime_audit(context, holdings, check):
    """月度收盘回归审计；发现漂移只记录，不修改持仓和订单。"""
    failures = []
    warnings = []
    notes = []
    holdings = list(holdings)
    core_codes = [
        code for code in holdings if g.holding_roles.get(code, "core") == "core"
    ]
    response_codes = [
        code for code in holdings if g.holding_roles.get(code) == "response"
    ]
    unknown_role_codes = [
        code for code in holdings
        if g.holding_roles.get(code, "core") not in ("core", "response")
    ]

    if len(holdings) > g.max_holdings:
        failures.append("实际持仓%d超过上限%d" % (len(holdings), g.max_holdings))
    if len(response_codes) > g.max_response_slots:
        failures.append(
            "实际响应仓%d超过上限%d" % (len(response_codes), g.max_response_slots)
        )
    if response_codes and len(core_codes) < g.min_core_slots:
        failures.append(
            "存在响应仓时核心仅%d只，低于%d只" % (len(core_codes), g.min_core_slots)
        )
    if unknown_role_codes:
        failures.append("存在未知角色%s" % unknown_role_codes)

    industry_counts = {}
    industry_names = {}
    for code in holdings:
        item = getattr(g, "pending_scores", {}).get(code, {})
        industry_code = item.get("industry_code")
        industry_name = item.get("industry_name")
        if not industry_code:
            industry_code, industry_name = _get_sw1_industry(
                code, context.previous_date
            )
        industry_code = str(industry_code)
        industry_counts[industry_code] = industry_counts.get(industry_code, 0) + 1
        industry_names[industry_code] = str(industry_name or industry_code)
    over_limit = {
        industry_names.get(key, key): value
        for key, value in industry_counts.items()
        if value > g.max_industry_holdings
    }
    if over_limit:
        failures.append("实际行业持仓超限%s" % over_limit)

    if int(check.get("response_security_changes", 0)) > g.max_response_changes_per_month:
        failures.append("单月响应证券变化超过上限")
    if int(check.get("response_role_promotions", 0)) > g.max_response_role_promotions_per_month:
        failures.append("单月响应角色晋升超过上限")
    if int(check.get("watch_replacements", 0)) > g.watch_replacement_max_per_month:
        failures.append("单月WATCH替换超过上限")

    planned_account_beta = check.get("planned_account_beta")
    if planned_account_beta is not None:
        try:
            if float(planned_account_beta) > g.leveraged_account_beta_ceiling + 1e-8:
                failures.append(
                    "计划账户Beta %.3f超过硬上限%.2f"
                    % (float(planned_account_beta), g.leveraged_account_beta_ceiling)
                )
        except Exception:
            warnings.append("计划账户Beta无法解析")

    planned_exposure = check.get("planned_exposure")
    if planned_exposure is not None:
        try:
            if float(planned_exposure) > g.current_target_exposure + 1e-8:
                failures.append(
                    "整手计划仓位%.2f%%超过当前目标%.2f%%"
                    % (float(planned_exposure) * 100.0,
                       g.current_target_exposure * 100.0)
                )
        except Exception:
            warnings.append("整手计划仓位无法解析")

    actual_exposure = check.get("actual_exposure")
    audit_thresholds = _exposure_audit_thresholds(
        check.get("planned_exposure", g.current_target_exposure)
    )
    planned_notice_ceiling = float(
        audit_thresholds["planned_notice_ceiling"]
    )
    policy_hard_ceiling = float(
        audit_thresholds["policy_hard_ceiling"]
    )
    if actual_exposure is not None:
        try:
            actual_number = float(actual_exposure)
            if actual_number > policy_hard_ceiling + 1e-8:
                warnings.append(
                    "收盘实际仓位%.2f%%超过政策硬风险线%.2f%%"
                    % (
                        actual_number * 100.0,
                        policy_hard_ceiling * 100.0,
                    )
                )
            elif actual_number > planned_notice_ceiling + 1e-8:
                notes.append(
                    "收盘实际仓位%.2f%%超过计划偏差提示线%.2f%%，"
                    "但未突破政策硬风险线%.2f%%"
                    % (
                        actual_number * 100.0,
                        planned_notice_ceiling * 100.0,
                        policy_hard_ceiling * 100.0,
                    )
                )
        except Exception:
            warnings.append("收盘实际仓位无法解析")

    query_meta = (
        getattr(g, "latest_mainline_meta", {})
        .get("fund", {})
        .get("query_diagnostics", {})
    )
    selection_source = str(query_meta.get("selection_source", "unknown"))
    queried_quarters = int(query_meta.get("queried_quarters", 0) or 0)
    scanned_quarters = int(query_meta.get("scanned_quarters", 0) or 0)
    if selection_source == "ordinary_month_pair_cache" and queried_quarters != 0:
        failures.append("普通月份复用缓存时仍查询了基金季度")
    if queried_quarters > 2:
        failures.append("单月基金季度查询%d个，超过正式版上限2个" % queried_quarters)
    if selection_source == "quarter_snapshot_cache" and queried_quarters > 1:
        # 第一次启动允许两季；其后出现新季度应只补读一季。
        if int(getattr(g, "release_audit_months", 0)) > 0:
            failures.append("非首次月度刷新查询了多个新季度")
    if not bool(check.get("institution_actionable", False)):
        if int(check.get("response_security_changes", 0)) > 0:
            failures.append("机构闸门关闭时仍发生响应证券变化")

    total_value = float(context.portfolio.total_value)
    g.release_peak_value = max(float(g.release_peak_value), total_value)
    initial_value = max(float(g.release_initial_value), 1.0)
    peak_value = max(float(g.release_peak_value), 1.0)
    cumulative_return = total_value / initial_value - 1.0
    drawdown_from_peak = total_value / peak_value - 1.0
    g.release_audit_months += 1
    if failures:
        g.release_audit_failures += 1
        status = "FAIL"
    elif warnings:
        g.release_audit_warnings += 1
        status = "WARN"
    else:
        status = "PASS"

    audit = {
        "date": str(context.current_dt.date()),
        "status": status,
        "behavior_baseline": str(g.release_behavior_baseline),
        "parameter_fingerprint": str(g.release_parameter_fingerprint),
        "audit_month": int(g.release_audit_months),
        "failures": failures,
        "warnings": warnings,
        "notes": notes,
        "planned_notice_ceiling": float(planned_notice_ceiling),
        "policy_hard_ceiling": float(policy_hard_ceiling),
        "holding_count": int(len(holdings)),
        "core_holdings": int(len(core_codes)),
        "response_holdings": int(len(response_codes)),
        "industry_counts": industry_counts,
        "institution_actionable": bool(check.get("institution_actionable", False)),
        "institution_mode": str(check.get("institution_mode", "unknown")),
        "fund_query": {
            "selection_source": selection_source,
            "queried_quarters": queried_quarters,
            "scanned_quarters": scanned_quarters,
            "quarter_cache_hits": int(query_meta.get("quarter_cache_hits", 0) or 0),
            "refresh_due": bool(query_meta.get("refresh_due", False)),
        },
        "query_totals": dict(getattr(g, "fund_query_stats", {})),
        "total_value": total_value,
        "cumulative_return": float(cumulative_return),
        "drawdown_from_peak": float(drawdown_from_peak),
        "leverage_multiplier": float(getattr(g, "leverage_multiplier", 1.0)),
        "dynamic_leverage_stage_age": int(
            getattr(g, "dynamic_leverage_stage_age", 0)
        ),
        "dynamic_leverage_last_decision": dict(
            getattr(g, "dynamic_leverage_last_decision", {})
        ),
        "policy_confirm_weeks": int(
            getattr(g, "dynamic_leverage_policy_confirm_weeks", 0)
        ),
        "improve_confirm_weeks": int(
            getattr(g, "dynamic_leverage_improve_confirm_weeks", 0)
        ),
        "recovery_lock_remaining": int(
            getattr(g, "dynamic_leverage_recovery_lock_remaining", 0)
        ),
        "portfolio_drawdown": float(
            getattr(g, "portfolio_drawdown", 0.0)
        ),
        "drawdown_guard_cap": float(
            getattr(g, "drawdown_guard_cap", 1.60)
        ),
        "debt_risk_state": dict(
            getattr(g, "latest_debt_risk_state", {})
        ),
        "margin_metric_diagnostic": dict(
            getattr(g, "margin_last_diagnostic", {})
        ),
        "financing_gate_status": str(
            getattr(g, "financing_gate_status", "unknown")
        ),
        "financing_gate_reasons": list(
            getattr(g, "financing_gate_reasons", [])
        ),
        "financing_gate_warning_reasons": list(
            getattr(g, "financing_gate_warning_reasons", [])
        ),
        "weekly_state_history": list(
            getattr(g, "dynamic_leverage_weekly_history", [])
        ),
        "strong_deploy_weeks": int(
            getattr(g, "dynamic_leverage_strong_deploy_weeks", 0)
        ),
        "financing_demand_ratio": max(
            0.0, float(g.current_target_exposure) - 1.0
        ),
        "margin_successful_order_calls": int(
            getattr(g, "margin_successful_order_calls", 0)
        ),
        "exposure_reconcile_last_result": dict(
            getattr(g, "exposure_reconcile_last_result", {})
        ),
        "gross_exposure": check.get("actual_exposure"),
        "cash_liability": check.get("cash_liability"),
        "interest_liability": check.get("interest_liability"),
        "maintenance_margin_rate": check.get("maintenance_margin_rate"),
        "planned_exposure": check.get("planned_exposure"),
        "actual_exposure": check.get("actual_exposure"),
        "planned_account_beta": check.get("planned_account_beta"),
        "actual_account_beta": check.get("actual_account_beta"),
        "audit_failure_months": int(g.release_audit_failures),
        "audit_warning_months": int(g.release_audit_warnings),
    }
    payload = json.dumps(audit, ensure_ascii=False, sort_keys=True)
    if status == "FAIL":
        log.error("V18E1_RESEARCH_AUDIT|%s" % payload)
    elif status == "WARN":
        log.warning("V18E1_RESEARCH_AUDIT|%s" % payload)
    else:
        log.info("V18E1_RESEARCH_AUDIT|%s" % payload)
    return audit

def _liquidity_new_buy_limit(policy):
    """把V4行动政策映射为本月最多新增证券数；未知状态保守按1只。"""
    limits = getattr(g, "liquidity_policy_new_buy_limits", {})
    try:
        return max(0, int(limits.get(policy, limits.get("data_insufficient", 1))))
    except Exception:
        return 1


def _policy_unlevered_exposure(policy):
    """返回E1政策本身的未杠杆股票仓位。【LEV12】上限由0.92提至1.00(deploy满仓)。"""
    mapping = getattr(g, "policy_target_exposure", {})
    fallback = mapping.get("data_insufficient", 0.50)
    try:
        return max(0.0, min(1.00, float(mapping.get(policy, fallback))))
    except Exception:
        return max(0.0, min(1.00, float(fallback)))




def _clip_effective_leverage(multiplier):
    """LEV12：执行杠杆封顶。内部阶梯不变，仅实际执行倍数按上限截断。"""
    return min(
        float(multiplier),
        float(getattr(g, "leverage_effective_cap", 1.20)),
    )


def _nearest_legal_leverage(value, direction="nearest"):
    levels = sorted(
        float(item)
        for item in getattr(g, "dynamic_leverage_levels", (1.0, 1.2, 1.4, 1.6))
    )
    value = float(value)
    if direction == "down":
        valid = [item for item in levels if item <= value + 1e-10]
        return max(valid) if valid else min(levels)
    if direction == "up":
        valid = [item for item in levels if item >= value - 1e-10]
        return min(valid) if valid else max(levels)
    return min(levels, key=lambda item: abs(item - value))


def _dynamic_single_weight_cap(context=None, multiplier_override=None):
    """按杠杆阶段给出单股上限；核心结构未形成前固定15.33%。"""
    holdings_count = 0
    if context is not None:
        try:
            holdings_count = len(_actual_holdings(context))
        except Exception:
            holdings_count = 0
    initial_incomplete = bool(
        getattr(g, "initial_build_enabled", False)
        and not getattr(g, "initial_build_completed", False)
    )
    if (
        initial_incomplete
        or holdings_count < int(getattr(g, "dynamic_leverage_min_holdings_for_financing", 6))
    ):
        return float(g.unlevered_single_weight_cap)
    source_multiplier = (
        multiplier_override
        if multiplier_override is not None
        else getattr(g, "dynamic_leverage_current", 1.0)
    )
    current = _nearest_legal_leverage(source_multiplier)
    mapping = getattr(g, "dynamic_single_weight_caps", {})
    return float(mapping.get(current, g.max_single_weight))


def _current_structure_exposure_cap(context, candidate_multiplier=None):
    """估算当前实际持仓结构最多可承载的股票暴露。

    该值只描述“当前已有证券数量与单股上限”的容量，不会替代政策目标，
    也不会允许周度任务绕过月度选股新增证券。WATCH持仓继续按8%上限计。
    """
    try:
        holdings = list(_actual_holdings(context))
    except Exception:
        holdings = []
    if not holdings:
        return 0.0

    normal_cap = float(
        _dynamic_single_weight_cap(
            context,
            multiplier_override=candidate_multiplier,
        )
    )
    watch_cap = float(getattr(g, "watch_max_weight", 0.08))
    capacity = 0.0
    for code in holdings:
        thesis_state = str(
            getattr(g, "holding_thesis_states", {}).get(code, "HEALTHY")
        )
        capacity += watch_cap if thesis_state == "WATCH" else normal_cap
    return max(
        0.0,
        min(float(getattr(g, "gross_leverage_cap", 1.6)), float(capacity)),
    )


def _drawdown_raw_leverage_cap(drawdown):
    """LEV12：护栏档位重映射到封顶空间内（1.10/1.00）。

    封顶1.20后，-6%→1.10、≤-10%→1.00，使执行口径严格递减 1.20→1.10→1.00，
    无空转档（CAP13 的 -6%→1.20 在 cap=1.20 下会等于封顶值而零降档）。
    注意 1.10 不是主阶梯(1.00/1.20/1.40/1.60)的合法档位，因此本函数
    的返回值不得再经 _nearest_legal_leverage(..., direction="down") 处理
    （否则会被压成1.00）。
    """
    thresholds = getattr(g, "drawdown_guard_thresholds", {})
    if drawdown <= float(thresholds.get("cap_1_00", -0.10)):
        return 1.00
    if drawdown <= float(thresholds.get("cap_1_10", -0.06)):
        return 1.10
    return 1.60


def _update_portfolio_drawdown_guard(context, asof=None, allow_release=False):
    """组合回撤护栏：降档立即，恢复需两次独立周度确认。"""
    metrics = _l16_margin_metrics(context)
    net_value = float(metrics["net_value"])
    peak = getattr(g, "portfolio_peak_net_value", None)
    if peak is None or not np.isfinite(peak) or float(peak) <= 0:
        peak = net_value
    peak = max(float(peak), net_value)
    g.portfolio_peak_net_value = float(peak)
    drawdown = net_value / peak - 1.0 if peak > 0 else 0.0
    raw_cap = _drawdown_raw_leverage_cap(drawdown)
    current_cap = float(getattr(g, "drawdown_guard_cap", 1.60))

    if raw_cap < current_cap - 1e-10:
        current_cap = raw_cap
        g.drawdown_guard_release_count = 0
        g.drawdown_guard_last_release_asof = None
        log.warning(
            "组合回撤杠杆护栏触发：净值回撤%.2f%%，杠杆上限立即降至%.2f。"
            % (drawdown * 100.0, current_cap)
        )
    elif raw_cap > current_cap + 1e-10:
        asof_key = str(asof) if asof is not None else None
        is_new_release_observation = bool(
            allow_release
            and asof_key
            and asof_key != str(getattr(g, "drawdown_guard_last_release_asof", None))
        )
        if is_new_release_observation:
            g.drawdown_guard_last_release_asof = asof_key
            g.drawdown_guard_release_count += 1
            if (
                g.drawdown_guard_release_count
                >= int(g.drawdown_guard_release_confirm_weeks)
            ):
                # 【CAP13-GUARD13】解除改为"沿阶梯推进一档"，替代原
                # current_cap + 0.20 + _nearest_legal_leverage 的写法。
                # 原写法在 1.10 档上会出错：1.10+0.20 浮点为 1.3000000000000003，
                # nearest() 会判 1.40 更近(1.4 与 1.3 的浮点间距略小于 1.2 与 1.3)，
                # 导致从 1.10 一步跳到 1.40（执行口径 1.10→1.30，跳过 1.20），
                # 违反"每次最多恢复一个阶梯"且回补过急；而改用 down 取整又会让
                # 1.00→1.10 被压回 1.00 而卡死。显式阶梯两者皆可避免。
                # 母版等价性：extra_levels 为空时阶梯 = (1.0,1.2,1.4,1.6)，
                # "推进一档"与 "+0.20" 完全等价（已逐档验证）。
                ladder = sorted(
                    set(
                        [float(x) for x in getattr(
                            g, "dynamic_leverage_levels", (1.0, 1.2, 1.4, 1.6))]
                        + [float(x) for x in getattr(
                            g, "drawdown_guard_extra_levels", ())]
                    )
                )
                higher = [v for v in ladder if v > current_cap + 1e-9]
                target = min(higher) if higher else max(ladder)
                current_cap = min(raw_cap, target)
                g.drawdown_guard_release_count = 0
                log.info(
                    "组合回撤护栏连续确认解除一档：当前回撤%.2f%%，"
                    "杠杆上限恢复至%.2f。"
                    % (drawdown * 100.0, current_cap)
                )
    else:
        g.drawdown_guard_release_count = 0

    g.portfolio_drawdown = float(drawdown)
    g.drawdown_guard_raw_cap = float(raw_cap)
    g.drawdown_guard_cap = float(current_cap)
    return {
        "net_value": net_value,
        "peak_net_value": float(peak),
        "drawdown": float(drawdown),
        "raw_cap": float(raw_cap),
        "effective_cap": float(current_cap),
        "release_count": int(g.drawdown_guard_release_count),
    }


def _debt_risk_state(context):
    """融资债务率护栏；字段缺失仅告警，不再永久封死融资。"""
    metrics = _l16_margin_metrics(context)
    net_value = float(metrics["net_value"])
    total_liability = float(metrics["total_liability"])
    debt_ratio = (
        float(metrics["debt_ratio"])
        if np.isfinite(metrics["debt_ratio"])
        else np.nan
    )

    cap = 1.60
    if np.isfinite(debt_ratio):
        if debt_ratio > float(g.debt_ratio_cap_1_20):
            cap = 1.20
        elif debt_ratio > float(g.debt_ratio_cap_1_40):
            cap = 1.40

    available_margin = metrics.get("available_margin", np.nan)
    missing_margin_data = not np.isfinite(available_margin)
    hard_block_reasons = []
    warning_reasons = []

    if np.isfinite(debt_ratio) and debt_ratio > float(g.debt_ratio_block_new):
        hard_block_reasons.append("debt_ratio_above_45pct")
    if np.isfinite(available_margin) and available_margin <= 0:
        warning_reasons.append(
            "available_margin_nonpositive_use_order_api_guard"
        )
    if missing_margin_data:
        warning_reasons.append(
            "available_margin_missing_use_order_api_guard"
        )

    block_new = bool(hard_block_reasons)
    state = {
        "debt_ratio": float(debt_ratio) if np.isfinite(debt_ratio) else None,
        "reported_debt_ratio": (
            float(metrics["reported_debt_ratio"])
            if np.isfinite(metrics["reported_debt_ratio"])
            else None
        ),
        "inferred_debt_ratio": (
            float(metrics["inferred_debt_ratio"])
            if np.isfinite(metrics["inferred_debt_ratio"])
            else None
        ),
        "liability_source": str(metrics["liability_source"]),
        "leverage_cap": float(cap),
        "block_new_financing": bool(block_new),
        "block_reasons": list(hard_block_reasons),
        "warning_reasons": list(warning_reasons),
        "available_margin": (
            float(available_margin) if np.isfinite(available_margin) else None
        ),
        "maintenance_margin_rate": (
            float(metrics["maintenance_margin_rate"])
            if np.isfinite(metrics["maintenance_margin_rate"])
            else None
        ),
        "reported_total_liability": float(
            metrics["reported_total_liability"]
        ),
        "inferred_total_liability": float(
            metrics["inferred_total_liability"]
        ),
        "total_liability": float(total_liability),
        "margin_metric_diagnostic": dict(metrics["diagnostic"]),
    }
    g.latest_debt_risk_state = dict(state)
    g.dynamic_leverage_new_financing_blocked = bool(block_new)
    g.dynamic_leverage_financing_block_reasons = list(hard_block_reasons)
    return state


def _financing_structure_ready(context):
    """至少形成6只实际持仓且初始建仓阶段完成，才允许新增融资。"""
    holdings_count = len(_actual_holdings(context))
    initial_completed = bool(
        not getattr(g, "initial_build_enabled", False)
        or getattr(g, "initial_build_completed", False)
    )
    ready = bool(
        initial_completed
        and holdings_count
        >= int(getattr(g, "dynamic_leverage_min_holdings_for_financing", 6))
    )
    return {
        "ready": ready,
        "holding_count": int(holdings_count),
        "initial_build_completed": bool(initial_completed),
    }




def _runtime_leverage_base_state(
    context,
    asof=None,
    allow_drawdown_release=False,
):
    """一次性计算与候选杠杆无关的回撤、债务、结构和阶段上限。"""
    drawdown = _update_portfolio_drawdown_guard(
        context,
        asof=asof,
        allow_release=allow_drawdown_release,
    )
    debt = _debt_risk_state(context)
    structure = _financing_structure_ready(context)

    raw_stage_cap = min(
        float(g.dynamic_leverage_max),
        float(drawdown["effective_cap"]),
        float(debt["leverage_cap"]),
    )
    # 【CAP13-GUARD13-20260904】不再向下取整到主阶梯。
    # 母版下 raw_stage_cap 取值域 = {1.00/1.20/1.40/1.60}(回撤与债务护栏
    # 的输出本就全是合法档位)，因此 _nearest_legal_leverage(..., "down")
    # 是恒等运算，去掉它对母版行为零改变；但保留取整会把护栏细分档 1.10
    # 压成 1.00，使 -10% 一档直接全去杠杆(比母版更激进)。
    stage_cap = float(raw_stage_cap)

    stage_block_reasons = []
    if stage_cap < float(g.dynamic_leverage_max) - 1e-10:
        if (
            float(drawdown["effective_cap"])
            < float(g.dynamic_leverage_max) - 1e-10
            and stage_cap <= float(drawdown["effective_cap"]) + 1e-10
        ):
            stage_block_reasons.append("portfolio_drawdown_cap")
        if (
            float(debt["leverage_cap"])
            < float(g.dynamic_leverage_max) - 1e-10
            and stage_cap <= float(debt["leverage_cap"]) + 1e-10
        ):
            stage_block_reasons.append("debt_ratio_leverage_cap")

    potential_execution_block_reasons = []
    if not structure["ready"]:
        potential_execution_block_reasons.append(
            "initial_core_structure_incomplete"
        )
    if debt["block_new_financing"]:
        potential_execution_block_reasons.extend(debt["block_reasons"])
    if getattr(g, "exposure_reconcile_buy_lock", False):
        potential_execution_block_reasons.append("unresolved_exposure_gap")
    potential_execution_block_reasons = list(
        dict.fromkeys(potential_execution_block_reasons)
    )

    return {
        "leverage_cap": float(stage_cap),
        "raw_stage_cap": float(raw_stage_cap),
        "policy_stage_execution_decoupled": True,
        "stage_block_reasons": list(stage_block_reasons),
        "potential_financing_block_reasons": list(
            potential_execution_block_reasons
        ),
        "drawdown": drawdown,
        "debt": debt,
        "structure": structure,
    }


def _runtime_leverage_guard(
    context,
    policy,
    asof=None,
    allow_drawdown_release=False,
    candidate_multiplier=None,
    base_state=None,
):
    """用最终候选杠杆重算融资需求与执行门。

    政策状态机仍只受全局、回撤和债务杠杆上限约束；初始结构不足等条件
    只在候选目标确实超过100%时激活融资阻止。这样升档当下的日志、目标
    暴露和融资门使用同一个候选杠杆，不再出现“杠杆已升、门仍按旧档位”的
    一个周期诊断滞后。
    """
    state = (
        dict(base_state)
        if isinstance(base_state, dict)
        else _runtime_leverage_base_state(
            context,
            asof=asof,
            allow_drawdown_release=allow_drawdown_release,
        )
    )
    stage_cap = float(state["leverage_cap"])
    source_multiplier = (
        candidate_multiplier
        if candidate_multiplier is not None
        else getattr(g, "dynamic_leverage_current", 1.0)
    )
    candidate = float(_nearest_legal_leverage(source_multiplier))
    effective_candidate = min(
        candidate,
        stage_cap,
        float(getattr(g, "leverage_effective_cap", 1.20)),
    )

    policy_target_exposure = min(
        float(g.gross_leverage_cap),
        float(_policy_unlevered_exposure(policy)) * effective_candidate,
        float(_extreme_state_target_exposure()),
    )
    policy_target_exposure = max(0.0, float(policy_target_exposure))
    structure_cap = float(
        _current_structure_exposure_cap(
            context,
            candidate_multiplier=effective_candidate,
        )
    )
    current_structure_target = min(
        policy_target_exposure,
        structure_cap,
    )

    financing_required = bool(policy_target_exposure > 1.0 + 1e-10)
    potential_reasons = list(
        state.get("potential_financing_block_reasons", [])
    )
    active_reasons = potential_reasons if financing_required else []
    if not financing_required:
        gate_status = "not_required"
    elif active_reasons:
        gate_status = "blocked"
    else:
        gate_status = "ready_for_order_attempt"

    debt = state["debt"]
    g.financing_gate_status = str(gate_status)
    g.financing_gate_reasons = list(active_reasons)
    g.financing_gate_warning_reasons = list(
        debt.get("warning_reasons", [])
    )

    result = dict(state)
    result.update({
        "candidate_multiplier": float(candidate),
        "effective_candidate_multiplier": float(effective_candidate),
        "policy_target_exposure": float(policy_target_exposure),
        "current_structure_exposure_cap": float(structure_cap),
        "current_structure_target_exposure": float(
            current_structure_target
        ),
        "financing_execution_blocked": bool(active_reasons),
        "financing_execution_block_reasons": list(active_reasons),
        "financing_gate_status": str(gate_status),
        "financing_required": bool(financing_required),
    })
    return result


def _guarded_target_exposure(context, policy):
    """目标暴露反映策略意图；执行失败由订单与实际暴露指标单独揭示。"""
    guard = _runtime_leverage_guard(
        context,
        policy,
        asof=None,
        allow_drawdown_release=False,
        candidate_multiplier=getattr(g, "dynamic_leverage_current", 1.0),
    )
    effective_multiplier = min(
        float(getattr(g, "leverage_multiplier", 1.0)),
        float(guard["leverage_cap"]),
    )
    target = _policy_unlevered_exposure(policy) * effective_multiplier
    target = min(
        float(g.gross_leverage_cap),
        float(target),
        float(_extreme_state_target_exposure()),
    )
    return max(0.0, float(target))


def _weekly_state_key(asof):
    try:
        ts = pd.Timestamp(asof)
        iso = ts.isocalendar()
        return "%04d-W%02d" % (int(iso.year), int(iso.week))
    except Exception:
        return str(asof)


def _update_dynamic_weekly_history(asof, policy, metrics):
    """按ISO周保存一次状态，强deploy连续周数由历史反推，不依赖可变累加器。"""
    key = _weekly_state_key(asof)
    history = list(getattr(g, "dynamic_leverage_weekly_history", []))
    history = [
        item for item in history
        if str(item.get("week_key")) != str(key)
    ]
    history.append({
        "week_key": str(key),
        "asof": str(asof),
        "policy": str(policy),
        "strong_deploy": bool(
            str(policy) == "deploy"
            and metrics.get("strong_deploy_environment", False)
        ),
        "hard_count": int(metrics.get("hard_count", 0)),
        "environment_score": metrics.get("environment_score"),
        "pure_liquidity_score": (
            metrics.get("current_scores", {})
            .get("pure_liquidity_score")
        ),
        "market_confirmation_score": (
            metrics.get("current_scores", {})
            .get("market_confirmation_score")
        ),
    })
    history = sorted(history, key=lambda item: str(item.get("asof")))
    limit = max(8, int(getattr(g, "dynamic_leverage_weekly_history_limit", 20)))
    history = history[-limit:]
    g.dynamic_leverage_weekly_history = history
    g.dynamic_leverage_last_processed_week = str(key)

    count = 0
    previous_date = None
    for item in reversed(history):
        if (
            item.get("policy") != "deploy"
            or not item.get("strong_deploy", False)
            or int(item.get("hard_count", 0)) > 0
        ):
            break
        try:
            item_date = pd.Timestamp(item.get("asof")).date()
        except Exception:
            item_date = None
        if previous_date is not None and item_date is not None:
            # 节假日可造成7天以上间隔，但超过14天视为不连续。
            if (previous_date - item_date).days > 14:
                break
        count += 1
        previous_date = item_date

    g.dynamic_leverage_strong_deploy_weeks = int(count)
    return {
        "week_key": str(key),
        "history_size": len(history),
        "strong_deploy_weeks": int(count),
        "latest": history[-1] if history else None,
    }


def _explicit_delta_signals(
    pure_delta,
    confirm_delta,
    improve_threshold,
    drop_threshold,
):
    """显式计算改善/快速下坠；不依赖裸any/all或生成器真假值。"""
    try:
        improve_threshold = abs(float(improve_threshold))
    except Exception:
        improve_threshold = 2.0
    try:
        drop_threshold = abs(float(drop_threshold))
    except Exception:
        drop_threshold = 8.0

    pure_known = bool(np.isfinite(pure_delta))
    confirm_known = bool(np.isfinite(confirm_delta))

    pure_nonnegative = bool(
        not pure_known or float(pure_delta) >= 0.0
    )
    confirmation_nonnegative = bool(
        not confirm_known or float(confirm_delta) >= 0.0
    )
    pure_improved = bool(
        pure_known and float(pure_delta) >= improve_threshold
    )
    confirmation_improved = bool(
        confirm_known and float(confirm_delta) >= improve_threshold
    )
    pure_fast_drop = bool(
        pure_known and float(pure_delta) <= -drop_threshold
    )
    confirmation_fast_drop = bool(
        confirm_known and float(confirm_delta) <= -drop_threshold
    )

    has_known_delta = bool(pure_known or confirm_known)
    broad_improvement = bool(
        has_known_delta
        and pure_nonnegative
        and confirmation_nonnegative
        and (pure_improved or confirmation_improved)
    )
    fast_drop_detected = bool(
        pure_fast_drop or confirmation_fast_drop
    )
    return {
        "has_known_delta": bool(has_known_delta),
        "pure_known": bool(pure_known),
        "confirmation_known": bool(confirm_known),
        "pure_improved": bool(pure_improved),
        "confirmation_improved": bool(confirmation_improved),
        "pure_fast_drop": bool(pure_fast_drop),
        "confirmation_fast_drop": bool(confirmation_fast_drop),
        "broad_improvement": bool(broad_improvement),
        "fast_drop_detected": bool(fast_drop_detected),
        "improve_threshold": float(improve_threshold),
        "drop_threshold": float(drop_threshold),
    }


def _strict_deploy_ladder_step(current_multiplier, strong_deploy_weeks):
    """严格按强deploy连续2/4/6周，每个独立周最多上调一个阶梯。"""
    current = float(_nearest_legal_leverage(current_multiplier))
    strong_weeks = max(0, int(strong_deploy_weeks))
    if (
        current < 1.20 - 1e-10
        and strong_weeks >= int(g.strong_deploy_to_1_20_weeks)
    ):
        return 1.20, "strong_deploy_stable_to_1_20"
    if (
        current < 1.40 - 1e-10
        and strong_weeks >= int(g.strong_deploy_to_1_40_weeks)
    ):
        return 1.40, "strong_deploy_stable_to_1_40"
    if (
        current < 1.60 - 1e-10
        and strong_weeks >= int(g.strong_deploy_to_1_60_weeks)
    ):
        return 1.60, "strong_deploy_stable_to_1_60"
    return current, "deploy_high_level_hold"


def _dynamic_leverage_logic_self_test():
    """初始化时验证边界值，失败则停止回测，避免静默锁死杠杆。"""
    global_any = globals().get("any", _py_builtins.any)
    global_all = globals().get("all", _py_builtins.all)
    probes = [
        ("zero_delta", 0.0, 0.0, False, False),
        ("positive_delta", 3.0, 1.0, False, True),
        ("inside_boundary", -7.999, 0.0, False, False),
        ("pure_boundary", -8.0, 0.0, True, False),
        ("confirmation_drop", 5.0, -9.0, True, False),
    ]
    results = []
    passed = True
    for name, pure_delta, confirm_delta, expected_drop, expected_improve in probes:
        state = _explicit_delta_signals(
            pure_delta,
            confirm_delta,
            2.0,
            8.0,
        )
        case_passed = bool(
            state["fast_drop_detected"] == bool(expected_drop)
            and state["broad_improvement"] == bool(expected_improve)
        )
        passed = bool(passed and case_passed)
        results.append({
            "name": str(name),
            "passed": bool(case_passed),
            "fast_drop_detected": bool(state["fast_drop_detected"]),
            "broad_improvement": bool(state["broad_improvement"]),
        })
    ladder_multiplier = 1.00
    ladder_path = []
    ladder_reasons = []
    for strong_week in range(1, 7):
        ladder_multiplier, ladder_reason = _strict_deploy_ladder_step(
            ladder_multiplier,
            strong_week,
        )
        ladder_path.append(float(ladder_multiplier))
        ladder_reasons.append(str(ladder_reason))
    expected_ladder_path = [1.00, 1.20, 1.20, 1.40, 1.40, 1.60]
    strict_ladder_passed = bool(ladder_path == expected_ladder_path)
    passed = bool(passed and strict_ladder_passed)
    cap_check_passed = (
        abs(
            _clip_effective_leverage(1.60)
            - float(g.leverage_effective_cap)
        ) < 1e-9
        and abs(
            _clip_effective_leverage(float(g.leverage_effective_cap))
            - float(g.leverage_effective_cap)
        ) < 1e-9
        and abs(_clip_effective_leverage(1.20) - 1.20) < 1e-9
    )
    passed = bool(passed and cap_check_passed)
    # 【LEV12】回撤护栏档位自检：映射正确 + 封顶后严格递减至地板。
    # 核心不变量：cap=1.20 下执行路径必须 1.20>1.10>1.00（无空转档）。
    # CAP13 的 -6%→1.20 在 cap=1.20 下会产生 1.20→1.20 平段（零降档），
    # 故 LEV12 把护栏下沉为 -6%→1.10、≤-10%→1.00。
    guard_cases = ((0.0, 1.60), (-0.07, 1.10), (-0.12, 1.00), (-0.20, 1.00))
    guard_observed = [float(_drawdown_raw_leverage_cap(dd)) for dd, _ in guard_cases]
    guard_ladder_passed = bool(
        all(
            abs(obs - exp) < 1e-9
            for obs, (_, exp) in zip(guard_observed, guard_cases)
        )
    )
    guard_exec = [
        float(_clip_effective_leverage(float(_drawdown_raw_leverage_cap(dd))))
        for dd, _ in guard_cases
    ]
    # 到地板(1.00)前严格递减；地板处允许持平(都是"全去杠杆"，非bug)。
    guard_monotonic_passed = bool(
        guard_exec[0] > guard_exec[1] > guard_exec[2]
        and guard_exec[3] <= guard_exec[2] + 1e-9
        and guard_exec[3] <= 1.00 + 1e-9
    )
    guard_check_passed = bool(guard_ladder_passed and guard_monotonic_passed)
    passed = bool(passed and guard_check_passed)
    return {
        "passed": bool(passed),
        "cases": results,
        "strict_246_ladder": {
            "passed": bool(strict_ladder_passed),
            "observed_path": list(ladder_path),
            "expected_path": list(expected_ladder_path),
            "reasons": list(ladder_reasons),
        },
        "effective_cap_check": bool(cap_check_passed),
        "drawdown_guard_check": {
            "passed": bool(guard_check_passed),
            "observed": list(guard_observed),
            "expected": [float(exp) for _, exp in guard_cases],
            "execution_path": list(guard_exec),
            "monotonic_after_cap": bool(guard_monotonic_passed),
        },
        "global_any_shadowed": bool(global_any is not _py_builtins.any),
        "global_all_shadowed": bool(global_all is not _py_builtins.all),
    }


def _dynamic_leverage_score_state(snapshot, evaluate_score_delta=True):
    """输出互斥趋势状态；只有新观察才比较周度分数差值。"""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    previous = getattr(g, "dynamic_leverage_last_weekly_scores", {}) or {}

    pure = snapshot.get("pure_liquidity_score", np.nan)
    confirm = snapshot.get("market_confirmation_score", np.nan)
    environment = snapshot.get("environment_score", np.nan)
    previous_pure = previous.get("pure_liquidity_score", np.nan)
    previous_confirm = previous.get("market_confirmation_score", np.nan)

    if bool(evaluate_score_delta):
        pure_delta = (
            float(pure) - float(previous_pure)
            if np.isfinite(pure) and np.isfinite(previous_pure)
            else np.nan
        )
        confirm_delta = (
            float(confirm) - float(previous_confirm)
            if np.isfinite(confirm) and np.isfinite(previous_confirm)
            else np.nan
        )
    else:
        # daily_guard重复使用同一个周度快照时，不得把“相同值”当作新观察。
        pure_delta = np.nan
        confirm_delta = np.nan

    improving_momentum = {
        "sustained_improving",
        "short_pullback_in_medium_improvement",
        "medium_repair_in_long_weakness",
    }
    deteriorating_momentum = {
        "sustained_deteriorating",
        "short_rebound_in_medium_weakness",
        "medium_slowdown_in_long_strength",
    }
    momentum_state = str(snapshot.get("momentum_state", "unknown"))
    hard_count = int(
        sum(bool(value) for value in snapshot.get("stress_flags", {}).values())
    )
    delta_signals = _explicit_delta_signals(
        pure_delta,
        confirm_delta,
        g.dynamic_leverage_score_improve_threshold,
        g.dynamic_leverage_fast_drop_threshold,
    )
    broad_improvement = bool(delta_signals["broad_improvement"])
    strong_deterioration = bool(delta_signals["fast_drop_detected"])
    healthy_expansion = bool(
        snapshot.get("structure") == "healthy_broad_expansion"
        or snapshot.get("outlook") == "healthy_expansion_confirmed"
    )
    strong_deploy_environment = bool(
        hard_count == 0
        and np.isfinite(environment)
        and np.isfinite(pure)
        and np.isfinite(confirm)
        and float(environment) >= float(g.strong_deploy_environment_min)
        and float(pure) >= float(g.strong_deploy_pure_min)
        and float(confirm) >= float(g.strong_deploy_confirmation_min)
    )

    # 非新观察不重复执行分数/动量降档；日内风险由硬风险、回撤和债务护栏负责。
    if not bool(evaluate_score_delta):
        if hard_count >= 1:
            trend_state = "DETERIORATING"
            trend_rule = "hard_risk_reused_snapshot"
        else:
            trend_state = "NEUTRAL"
            trend_rule = "reused_snapshot_no_score_reassessment"
    elif hard_count >= 1:
        trend_state = "DETERIORATING"
        trend_rule = "hard_risk"
    elif strong_deterioration:
        trend_state = "DETERIORATING"
        trend_rule = "fast_score_drop"
    elif strong_deploy_environment:
        trend_state = "IMPROVING"
        trend_rule = "strong_deploy_high_level_stable"
    elif broad_improvement:
        trend_state = "IMPROVING"
        trend_rule = "broad_score_improvement"
    elif (
        healthy_expansion
        and momentum_state not in deteriorating_momentum
    ):
        trend_state = "IMPROVING"
        trend_rule = "healthy_expansion"
    elif momentum_state in improving_momentum:
        trend_state = "IMPROVING"
        trend_rule = "improving_momentum"
    elif momentum_state in deteriorating_momentum:
        trend_state = "DETERIORATING"
        trend_rule = "deteriorating_momentum"
    else:
        trend_state = "NEUTRAL"
        trend_rule = "mixed_or_insufficient"

    # 显式不变量：没有任一分项越过负阈值，fast_drop绝不能为True。
    component_drop = bool(
        delta_signals["pure_fast_drop"]
        or delta_signals["confirmation_fast_drop"]
    )
    if strong_deterioration != component_drop:
        try:
            g.dynamic_leverage_fast_drop_invariant_failures += 1
        except Exception:
            pass
        log.error(
            "DL1.6c3e快速下坠不变量失败：pure_delta=%s，confirmation_delta=%s，"
            "threshold=%s，fast_drop=%s，component_drop=%s；强制按分项结果修正。"
            % (
                pure_delta,
                confirm_delta,
                delta_signals["drop_threshold"],
                strong_deterioration,
                component_drop,
            )
        )
        strong_deterioration = bool(component_drop)

    current_scores = {
        "pure_liquidity_score": (
            float(pure) if np.isfinite(pure) else None
        ),
        "market_confirmation_score": (
            float(confirm) if np.isfinite(confirm) else None
        ),
        "environment_score": (
            float(environment) if np.isfinite(environment) else None
        ),
    }
    return {
        "pure_delta": float(pure_delta) if np.isfinite(pure_delta) else None,
        "confirmation_delta": (
            float(confirm_delta) if np.isfinite(confirm_delta) else None
        ),
        "delta_observation_fresh": bool(evaluate_score_delta),
        "fast_drop_threshold": float(delta_signals["drop_threshold"]),
        "pure_fast_drop": bool(delta_signals["pure_fast_drop"]),
        "confirmation_fast_drop": bool(
            delta_signals["confirmation_fast_drop"]
        ),
        "environment_score": (
            float(environment) if np.isfinite(environment) else None
        ),
        "momentum_state": momentum_state,
        "hard_count": hard_count,
        "trend_state": trend_state,
        "trend_rule": str(trend_rule),
        "fast_drop_detected": bool(strong_deterioration),
        "score_improving": trend_state == "IMPROVING",
        "score_deteriorating": trend_state == "DETERIORATING",
        "healthy_expansion": healthy_expansion,
        "strong_deploy_environment": strong_deploy_environment,
        "current_scores": current_scores,
    }


def _update_dynamic_leverage_state(
    snapshot,
    effective_policy,
    event,
    context=None,
):
    """DL1.6c3e：显式差值、严格2/4/6周升档，候选杠杆重算融资门。"""
    policy = str(effective_policy or "data_insufficient")
    previous_policy = str(
        getattr(g, "dynamic_leverage_previous_policy", "warming_up")
    )
    current = float(getattr(g, "dynamic_leverage_current", 1.0))
    asof = str((snapshot or {}).get("asof", "unknown"))
    is_weekly_event = str(event) == "weekly_radar"
    is_new_weekly = bool(
        is_weekly_event
        and asof != str(getattr(g, "dynamic_leverage_last_weekly_asof", None))
    )
    is_fresh_monthly_snapshot = bool(
        str(event) == "monthly_rebalance"
        and asof != str(getattr(g, "dynamic_leverage_last_weekly_asof", None))
    )
    evaluate_score_delta = bool(
        is_new_weekly or is_fresh_monthly_snapshot
    )
    if not evaluate_score_delta:
        try:
            g.dynamic_leverage_reused_snapshot_skips += 1
        except Exception:
            pass
    metrics = _dynamic_leverage_score_state(
        snapshot,
        evaluate_score_delta=evaluate_score_delta,
    )
    if (
        evaluate_score_delta
        and metrics.get("strong_deploy_environment", False)
        and not metrics.get("fast_drop_detected", False)
        and int(metrics.get("hard_count", 0)) == 0
        and metrics.get("trend_state") != "IMPROVING"
    ):
        log.error(
            "动态杠杆趋势不变量修正：强deploy且无硬风险/快速下坠，"
            "但趋势=%s；强制改为IMPROVING。"
            % metrics.get("trend_state")
        )
        metrics["trend_state"] = "IMPROVING"
        metrics["trend_rule"] = "strong_deploy_invariant_repair"
        metrics["score_improving"] = True
        metrics["score_deteriorating"] = False
    hard_count = int(metrics["hard_count"])

    if is_new_weekly:
        previous_weekly_policy = getattr(
            g, "dynamic_leverage_last_weekly_policy", None
        )
        if previous_weekly_policy == policy:
            g.dynamic_leverage_policy_confirm_weeks += 1
        else:
            g.dynamic_leverage_policy_confirm_weeks = 1

        if metrics["trend_state"] == "IMPROVING":
            g.dynamic_leverage_improve_confirm_weeks += 1
        else:
            g.dynamic_leverage_improve_confirm_weeks = 0

        weekly_history_state = _update_dynamic_weekly_history(
            asof, policy, metrics
        )

        g.dynamic_leverage_last_weekly_policy = policy
        g.dynamic_leverage_last_weekly_asof = asof
        g.dynamic_leverage_last_weekly_scores = dict(metrics["current_scores"])

    if not is_new_weekly:
        weekly_history_state = {
            "week_key": _weekly_state_key(asof),
            "history_size": len(
                getattr(g, "dynamic_leverage_weekly_history", [])
            ),
            "strong_deploy_weeks": int(
                getattr(g, "dynamic_leverage_strong_deploy_weeks", 0)
            ),
            "latest": (
                getattr(g, "dynamic_leverage_weekly_history", [])[-1]
                if getattr(g, "dynamic_leverage_weekly_history", [])
                else None
            ),
        }

    lock_before = int(
        getattr(g, "dynamic_leverage_recovery_lock_remaining", 0)
    )
    increase_locked = lock_before > 0
    if is_new_weekly and lock_before > 0:
        g.dynamic_leverage_recovery_lock_remaining = max(0, lock_before - 1)

    allow_increase = bool(is_new_weekly and not increase_locked)
    reasons = []
    desired = current

    if hard_count >= 2:
        desired = 1.00
        reasons.append("hard_risk_remove_all_leverage")
    elif policy in ("defense", "freeze", "warming_up", "data_insufficient"):
        desired = 1.00
        reasons.append("%s_no_financing" % policy)
    elif hard_count == 1:
        desired = min(current, 1.20)
        reasons.append("single_hard_risk_no_increase")

    elif policy == "selective":
        # 【LEV12-20260904】杠杆仅限 deploy；selective 一律不融资。
        # 实测（log40 按 政策×执行档位 分组，3080 共同交易日）：
        #   selective×1.20 共 394 天，杠杆相对无融资基线净超额 -5.87p（效率 -0.78），
        #   是唯一效率为负的档位（deploy×1.20 为 +18.21p / 效率 +0.78）。
        #   故 selective 与 freeze/defense 一样强制 desired=1.00。
        desired = 1.00
        reasons.append("selective_no_financing")

    elif policy == "deploy":
        strong_weeks = int(
            getattr(g, "dynamic_leverage_strong_deploy_weeks", 0)
        )
        if metrics["trend_state"] == "DETERIORATING":
            desired = min(current, 1.40)
            reasons.append("deploy_internal_deterioration_step_down")
        elif not allow_increase:
            desired = current
            reasons.append(
                "deploy_recovery_lock"
                if increase_locked
                else "deploy_wait_weekly_confirmation"
            )
        else:
            desired, ladder_reason = _strict_deploy_ladder_step(
                current,
                strong_weeks,
            )
            reasons.append(ladder_reason)

    else:
        desired = 1.00
        reasons.append("unknown_policy_conservative")

    # 只有独立周度观察可以升杠杆。
    if not is_new_weekly and desired > current:
        desired = current
        reasons.append("non_weekly_increase_blocked")

    runtime_guard = None
    runtime_base_state = None
    if context is not None:
        runtime_base_state = _runtime_leverage_base_state(
            context,
            asof=asof,
            allow_drawdown_release=is_new_weekly,
        )
        if desired > float(runtime_base_state["leverage_cap"]):
            reasons.append("runtime_leverage_cap")
        desired = min(
            desired,
            float(runtime_base_state["leverage_cap"]),
        )

    desired = max(
        float(g.dynamic_leverage_min),
        min(float(g.dynamic_leverage_max), float(desired)),
    )
    if desired > current + 1e-10:
        new_multiplier = min(
            desired,
            current + float(g.dynamic_leverage_step),
        )
    else:
        new_multiplier = desired
    new_multiplier = _nearest_legal_leverage(new_multiplier)

    # deploy升档严格服从2/4/6周。任何未来新增分支都不能绕过该不变量。
    if policy == "deploy" and new_multiplier > current + 1e-10:
        required_weeks = {
            1.20: int(g.strong_deploy_to_1_20_weeks),
            1.40: int(g.strong_deploy_to_1_40_weeks),
            1.60: int(g.strong_deploy_to_1_60_weeks),
        }.get(float(new_multiplier), 10 ** 9)
        observed_weeks = int(
            getattr(g, "dynamic_leverage_strong_deploy_weeks", 0)
        )
        if observed_weeks < required_weeks:
            log.error(
                "严格2/4/6升档不变量阻止：候选杠杆=%.2f，"
                "强deploy=%d周，最低要求=%d周；保持%.2f。"
                % (
                    new_multiplier,
                    observed_weeks,
                    required_weeks,
                    current,
                )
            )
            reasons.append("strict_246_ladder_invariant_block")
            new_multiplier = float(current)

    if context is not None:
        runtime_guard = _runtime_leverage_guard(
            context,
            policy,
            asof=asof,
            allow_drawdown_release=False,
            candidate_multiplier=new_multiplier,
            base_state=runtime_base_state,
        )

    changed = abs(new_multiplier - current) > 1e-10
    increased = new_multiplier > current + 1e-10
    decreased = new_multiplier < current - 1e-10

    if changed:
        g.dynamic_leverage_change_count += 1
        g.dynamic_leverage_stage_age = 0
        g.dynamic_leverage_last_change_asof = asof
        if increased:
            g.dynamic_leverage_increase_count += 1
        if decreased:
            g.dynamic_leverage_decrease_count += 1
            g.dynamic_leverage_recovery_lock_remaining = int(
                g.dynamic_leverage_recovery_lock_weeks
            )
            g.dynamic_leverage_last_decrease_asof = asof
    elif is_new_weekly:
        g.dynamic_leverage_stage_age += 1

    g.dynamic_leverage_current = float(new_multiplier)
    g.leverage_multiplier = _clip_effective_leverage(new_multiplier)
    g.dynamic_leverage_previous_policy = policy

    decision = {
        "event": str(event),
        "logic_version": str(getattr(
            g,
            "dynamic_leverage_logic_version",
            "unknown",
        )),
        "logic_build_id": str(getattr(
            g,
            "dynamic_leverage_build_id",
            "unknown",
        )),
        "evaluate_score_delta": bool(evaluate_score_delta),
        "asof": asof,
        "is_new_weekly": bool(is_new_weekly),
        "policy": policy,
        "previous_policy": previous_policy,
        "old_multiplier": float(current),
        "desired_multiplier": float(desired),
        "new_multiplier": float(new_multiplier),
        "effective_multiplier": float(g.leverage_multiplier),
        "strict_246_ladder": bool(
            getattr(g, "dynamic_leverage_strict_246_ladder", True)
        ),
        "required_strong_deploy_weeks": (
            {
                1.20: int(g.strong_deploy_to_1_20_weeks),
                1.40: int(g.strong_deploy_to_1_40_weeks),
                1.60: int(g.strong_deploy_to_1_60_weeks),
            }.get(float(new_multiplier))
            if policy == "deploy" and new_multiplier > 1.0 + 1e-10
            else 0
        ),
        "changed": bool(changed),
        "increased": bool(increased),
        "decreased": bool(decreased),
        "stage_age": int(g.dynamic_leverage_stage_age),
        "policy_confirm_weeks": int(g.dynamic_leverage_policy_confirm_weeks),
        "improve_confirm_weeks": int(g.dynamic_leverage_improve_confirm_weeks),
        "strong_deploy_weeks": int(
            g.dynamic_leverage_strong_deploy_weeks
        ),
        "weekly_history_state": dict(weekly_history_state),
        "recovery_lock_remaining": int(
            g.dynamic_leverage_recovery_lock_remaining
        ),
        "reasons": list(reasons),
        "score_state": {
            key: value
            for key, value in metrics.items()
            if key != "current_scores"
        },
        "runtime_guard": runtime_guard,
    }
    g.dynamic_leverage_last_decision = dict(decision)

    log.info(
        "动态杠杆决策：事件=%s/asof=%s/新周=%s，政策=%s，"
        "杠杆%.2f→%.2f，趋势=%s，强deploy=%d周，"
        "政策确认=%d周，改善确认=%d周，恢复锁=%d，原因=%s。"
        % (
            event,
            asof,
            is_new_weekly,
            policy,
            current,
            new_multiplier,
            metrics["trend_state"],
            g.dynamic_leverage_strong_deploy_weeks,
            g.dynamic_leverage_policy_confirm_weeks,
            g.dynamic_leverage_improve_confirm_weeks,
            g.dynamic_leverage_recovery_lock_remaining,
            reasons,
        )
    )
    log.info(
        "V18E1LEV12_LEVERAGE_STATE|%s"
        % json.dumps(
            _liquidity_json_safe(decision),
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return decision


def _extreme_state_target_exposure():
    state = str(getattr(g, "extreme_risk_state", "normal"))
    if state == "severe":
        return float(g.extreme_risk_severe_exposure)
    if state == "risk":
        return float(g.extreme_risk_exposure)
    return float(g.base_target_exposure)


def _mainline_enhancement_target(policy=None):
    if not bool(getattr(g, "mainline_alignment_enabled", False)):
        return 0
    policy = str(policy or getattr(g, "effective_allocation_policy", "warming_up"))
    mapping = getattr(g, "mainline_enhancement_targets", {})
    try:
        return max(0, min(int(g.max_holdings), int(mapping.get(policy, 0))))
    except Exception:
        return 0


def _mainline_alignment_sort_key(code, original_rank=10 ** 9):
    item = getattr(g, "pending_scores", {}).get(code, {})
    state = str(item.get("industry_state", "baseline"))
    state_rank = {"core": 0, "candidate": 1}.get(state, 2)
    mainline_score = item.get("mainline_score", np.nan)
    total_score = item.get("total", np.nan)
    return (
        state_rank,
        -float(mainline_score) if np.isfinite(mainline_score) else 0.0,
        -float(total_score) if np.isfinite(total_score) else 0.0,
        int(original_rank),
        str(code),
    )


def _select_mainline_enhanced_codes(codes, policy=None):
    target = _mainline_enhancement_target(policy)
    if target <= 0 or not _institution_response_actionable():
        return []
    candidates = []
    for index, code in enumerate(codes):
        item = getattr(g, "pending_scores", {}).get(code, {})
        if item.get("industry_state") not in ("core", "candidate"):
            continue
        if bool(item.get("severe_trend", False)):
            continue
        candidates.append((_mainline_alignment_sort_key(code, index), code))
    candidates.sort(key=lambda item: item[0])
    return [item[1] for item in candidates[:target]]


def _build_mainline_deploy_gate(rows, fund_age_days):
    active = [row for row in rows if row.get("state") in ("core", "candidate")]
    top5 = list(rows[:5])
    relative_values = [
        float(row.get("relative_strength")) for row in active
        if np.isfinite(row.get("relative_strength", np.nan))
    ]
    breadth_values = [
        float(row.get("breadth")) for row in active
        if np.isfinite(row.get("breadth", np.nan))
    ]
    active_count = int(len(active))
    core_count = int(sum(row.get("state") == "core" for row in active))
    price_confirmed_top5 = int(sum(bool(row.get("price_confirmed", False)) for row in top5))
    median_relative = float(np.median(relative_values)) if relative_values else np.nan
    median_breadth = float(np.median(breadth_values)) if breadth_values else np.nan
    checks = {
        "active_mainlines_at_least_4": active_count >= int(getattr(g, "deploy_gate_min_mainlines", 4)),
        "core_mainlines_at_least_2": core_count >= int(getattr(g, "deploy_gate_min_core_mainlines", 2)),
        "top5_price_confirmed_at_least_3": price_confirmed_top5 >= int(getattr(g, "deploy_gate_min_top5_confirmed", 3)),
        "mainline_relative_strength_nonnegative": bool(np.isfinite(median_relative) and median_relative >= float(getattr(g, "deploy_gate_min_relative_strength", 0.0))),
        "mainline_breadth_healthy": bool(np.isfinite(median_breadth) and median_breadth >= float(getattr(g, "deploy_gate_min_breadth", 0.55))),
    }
    return {
        "available": True,
        "passed": bool(_py_builtins.all(checks.values())),
        "checks": checks,
        "active_mainlines": active_count,
        "core_mainlines": core_count,
        "top5_price_confirmed": price_confirmed_top5,
        "median_relative_strength": median_relative if np.isfinite(median_relative) else None,
        "median_breadth": median_breadth if np.isfinite(median_breadth) else None,
        "fund_age_days": int(fund_age_days),
    }


def _fast_deterioration_flags(snapshot):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    macro = snapshot.get("macro_metrics", {}) or {}
    momentum = snapshot.get("momentum", {}) or {}
    price = snapshot.get("price_context", {}) or {}
    confirmation = snapshot.get("market_confirmation_score", np.nan)
    gate = getattr(g, "mainline_deploy_gate", {}) or {}
    level_change_4w = macro.get("level_change_4w", momentum.get("score_change_4w", np.nan))
    breadth_change_4w = macro.get("breadth_change_4w", momentum.get("breadth_change_4w", np.nan))
    gate_relative = gate.get("median_relative_strength")
    flags = {
        "liquidity_4w_drop": bool(np.isfinite(level_change_4w) and float(level_change_4w) <= -8.0),
        "breadth_4w_drop": bool(np.isfinite(breadth_change_4w) and float(breadth_change_4w) <= -8.0),
        "confirmation_below_45": bool(np.isfinite(confirmation) and float(confirmation) < 45.0),
        "index_below_ma20_ma60": bool(price.get("above_ma20") is False and price.get("above_ma60") is False),
        "mainline_gate_failed": bool(gate.get("available", False) and not gate.get("passed", False)),
        "mainline_relative_negative": bool(gate.get("available", False) and gate_relative is not None and float(gate_relative) < 0.0),
    }
    return flags


def _effective_allocation_policy(policy, snapshot=None):
    """在不改写流动性原始状态机的前提下，生成组合实际执行政策。"""
    effective = str(policy or "data_insufficient")
    reasons = []
    gate = getattr(g, "mainline_deploy_gate", {}) or {}
    if (
        bool(getattr(g, "mainline_deploy_veto_enabled", False))
        and effective == "deploy"
        and gate.get("available", False)
        and not gate.get("passed", False)
    ):
        effective = "selective"
        reasons.append("mainline_deploy_gate_failed")

    flags = _fast_deterioration_flags(snapshot)
    fast_count = int(sum(bool(value) for value in flags.values()))
    if bool(getattr(g, "fast_deterioration_enabled", False)):
        if fast_count >= 3 and effective in ("deploy", "selective"):
            effective = "freeze"
            reasons.append("fast_deterioration_%d" % fast_count)
        elif fast_count >= 2 and effective == "deploy":
            effective = "selective"
            reasons.append("fast_deterioration_%d" % fast_count)
    g.latest_fast_deterioration_flags = dict(flags)
    g.latest_allocation_policy_reasons = list(reasons)
    return effective


def _weighted_capped_allocation(codes, factors, total_weight, cap):
    """按因子比例分配，同时迭代处理单股上限。"""
    result = {code: 0.0 for code in codes}
    active = list(codes)
    remaining = max(0.0, float(total_weight))
    cap = max(0.0, float(cap))
    while active and remaining > 1e-12:
        denominator = sum(max(0.0, float(factors.get(code, 1.0))) for code in active)
        if denominator <= 0:
            break
        capped = []
        for code in active:
            proposed = remaining * max(0.0, float(factors.get(code, 1.0))) / denominator
            if proposed > cap + 1e-12:
                result[code] = cap
                remaining -= cap
                capped.append(code)
        if not capped:
            for code in active:
                result[code] = remaining * max(0.0, float(factors.get(code, 1.0))) / denominator
            remaining = 0.0
            break
        active = [code for code in active if code not in set(capped)]
    return result


def _start_response_probation(code, month_key, source):
    if not bool(getattr(g, "response_probation_enabled", False)):
        return
    g.response_probation_states[str(code)] = {
        "start_month": str(month_key),
        "status": "probation",
        "source": str(source),
        "last_month": str(month_key),
        "last_relative_20d": None,
        "last_passed": False,
    }


def _response_relative_return(code, asof):
    cache_key = "%s|%s" % (str(code), str(asof))
    cache = getattr(g, "response_relative_return_cache", {})
    if cache_key in cache:
        return cache[cache_key]
    frames = _load_price_frames([str(code), str(g.benchmark)], asof, count=40)
    result = {"stock_20d": np.nan, "benchmark_20d": np.nan, "relative_20d": np.nan}
    for key, output_key in ((str(code), "stock_20d"), (str(g.benchmark), "benchmark_20d")):
        frame = frames.get(key)
        if frame is None or frame.empty:
            continue
        close = pd.to_numeric(frame["close"], errors="coerce").dropna()
        if len(close) >= 21 and float(close.iloc[-21]) > 0:
            result[output_key] = float(close.iloc[-1] / close.iloc[-21] - 1.0)
    if np.isfinite(result["stock_20d"]) and np.isfinite(result["benchmark_20d"]):
        result["relative_20d"] = float(result["stock_20d"] - result["benchmark_20d"])
    cache[cache_key] = dict(result)
    # 只保留本轮月度计算需要的小字典，避免形成新的历史大缓存。
    if len(cache) > 20:
        cache = {cache_key: dict(result)}
    g.response_relative_return_cache = cache
    return result


def _response_independent_core_qualified(code):
    ranked = list(getattr(g, "pending_core_entry_ranked", []))
    limit = int(getattr(g, "response_core_upgrade_rank_limit", 30))
    item = getattr(g, "pending_scores", {}).get(code, {})
    return bool(
        str(code) in set(ranked[:limit])
        and _holding_company_qualified(code)
        and bool(item.get("weekly_trend_pass", False))
        and bool(item.get("normalized_earnings_pass", False))
    )


def _update_response_probation(code, month_key, asof):
    if not bool(getattr(g, "response_probation_enabled", False)):
        return "disabled", {}
    code = str(code)
    state = g.response_probation_states.get(code)
    if not isinstance(state, dict):
        _start_response_probation(code, month_key, "state_recovery")
        state = g.response_probation_states.get(code, {})
    relative = _response_relative_return(code, asof)
    item = getattr(g, "pending_scores", {}).get(code, {})
    passed = bool(
        item.get("industry_state") == "core"
        and np.isfinite(relative.get("relative_20d", np.nan))
        and float(relative.get("relative_20d")) >= 0.0
        and bool(item.get("weekly_trend_pass", False))
        and _holding_company_qualified(code)
    )
    start_month = state.get("start_month", month_key)
    try:
        age = max(0, _month_index(str(month_key) + "-01") - _month_index(str(start_month) + "-01"))
    except Exception:
        age = 0
    status = str(state.get("status", "probation"))
    if status != "validated":
        if age >= int(getattr(g, "response_probation_validate_after_months", 1)) and passed:
            status = "validated"
        elif age >= int(getattr(g, "response_probation_max_months", 3)):
            status = "expired"
        else:
            status = "probation"
    state.update({
        "status": status,
        "age_months": int(age),
        "last_month": str(month_key),
        "last_relative_20d": (
            float(relative.get("relative_20d"))
            if np.isfinite(relative.get("relative_20d", np.nan)) else None
        ),
        "last_passed": bool(passed),
    })
    g.response_probation_states[code] = state
    return status, dict(state)




def _apply_extreme_risk_snapshot(snapshot):
    """用原始硬风险处理月初与周度快照；行动政策平滑不得屏蔽即时降仓。"""
    flags = snapshot.get("stress_flags", {})
    trigger_count = int(sum(bool(value) for value in flags.values()))
    g.extreme_risk_trigger_count = trigger_count
    previous_state = str(g.extreme_risk_state)
    previous_exposure = float(g.current_target_exposure)

    if trigger_count < g.extreme_risk_min_flags:
        if g.extreme_risk_state != "normal":
            g.extreme_risk_release_count += 1
        else:
            g.extreme_risk_release_count = 0
        return {
            "flags": dict(flags),
            "trigger_count": trigger_count,
            "previous_state": previous_state,
            "state": str(g.extreme_risk_state),
            "previous_exposure": previous_exposure,
            "target_exposure": float(g.current_target_exposure),
            "lowered": False,
            "release_count": int(g.extreme_risk_release_count),
        }

    g.extreme_risk_release_count = 0
    severe = trigger_count >= g.extreme_risk_severe_flags
    candidate_state = "severe" if severe else "risk"
    candidate_exposure = (
        g.extreme_risk_severe_exposure if severe else g.extreme_risk_exposure
    )
    g.extreme_risk_state = candidate_state
    lowered = candidate_exposure < g.current_target_exposure - 1e-8
    g.current_target_exposure = min(
        float(g.current_target_exposure), float(candidate_exposure)
    )
    return {
        "flags": dict(flags),
        "trigger_count": trigger_count,
        "previous_state": previous_state,
        "state": str(g.extreme_risk_state),
        "previous_exposure": previous_exposure,
        "target_exposure": float(g.current_target_exposure),
        "lowered": bool(lowered),
        "release_count": int(g.extreme_risk_release_count),
    }




def _fz2_emit(event, payload=None):
    if not bool(getattr(g, "fz2_deferred_enabled", False)):
        return
    body = {"event": str(event)}
    if isinstance(payload, dict):
        body.update(payload)
    try:
        g.fz2_event_count = int(getattr(g, "fz2_event_count", 0)) + 1
    except Exception:
        pass
    log.info("V18E1_FZ2_DEFERRED|%s" % json.dumps(
        body, ensure_ascii=False, sort_keys=True, default=str
    ))


def _fz2_on_policy_transition(old_policy, new_policy, snapshot):
    """只冻结一种释放门：confirmed Freeze -> Selective。"""
    if not bool(getattr(g, "fz2_deferred_enabled", False)):
        return
    old_policy = str(old_policy or "unknown")
    new_policy = str(new_policy or "unknown")
    if old_policy == "freeze" and new_policy == "selective":
        g.fz2_release_pending = True
        g.fz2_release_trigger = {
            "asof": str((snapshot or {}).get("asof", "unknown")),
            "from": old_policy,
            "to": new_policy,
        }
        _fz2_emit("release_trigger", dict(g.fz2_release_trigger))


def _fz2_capture_candidates(context, asof, effective_policy, entry_ranked):
    """Freeze月把当期严格可买候选记入池；不额外放宽任何因子/趋势/Beta门槛。"""
    if not bool(getattr(g, "fz2_deferred_enabled", False)):
        return
    if str(effective_policy) != "freeze":
        return
    holdings = set(_actual_holdings(context))
    pool = dict(getattr(g, "fz2_deferred_pool", {}) or {})
    captured = []
    limit = max(1, int(getattr(g, "fz2_capture_limit", 30)))
    for code in list(entry_ranked)[:limit]:
        code = str(code)
        if code in holdings:
            continue
        item = dict(getattr(g, "pending_scores", {}).get(code, {}) or {})
        rec = dict(pool.get(code, {}) or {})
        if not rec:
            rec = {
                "code": code,
                "first_seen": str(asof),
                "times_seen": 0,
            }
        rec["last_seen"] = str(asof)
        rec["times_seen"] = int(rec.get("times_seen", 0)) + 1
        rec["source_policy"] = "freeze"
        for key in (
            "total", "total_rank", "quality", "safety", "value", "beta",
            "normalized_pe", "profit_peak_ratio", "industry_code", "industry_name",
            "weekly_trend_pass", "reentry_blocked"
        ):
            value = item.get(key)
            if isinstance(value, (np.floating, np.integer)):
                value = value.item()
            rec[key] = value
        pool[code] = rec
        captured.append(code)
    g.fz2_deferred_pool = pool
    _fz2_emit("freeze_capture", {
        "asof": str(asof),
        "captured_count": len(captured),
        "captured": captured,
        "pool_size": len(pool),
    })


def _fz2_prepare_monthly_release(context, asof, effective_policy, entry_ranked):
    """在下一次月度执行时，用当月 fresh entry_ranked 完整重新验证延期候选。"""
    if not bool(getattr(g, "fz2_deferred_enabled", False)):
        g.fz2_release_active_codes = []
        g.fz2_release_evaluated = False
        return []
    holdings = set(_actual_holdings(context))
    pool = dict(getattr(g, "fz2_deferred_pool", {}) or {})
    for code in list(pool):
        if code in holdings:
            pool.pop(code, None)
    g.fz2_deferred_pool = pool
    g.fz2_release_active_codes = []
    g.fz2_release_evaluated = False

    if not bool(getattr(g, "fz2_release_pending", False)):
        return []
    if str(effective_policy) not in ("selective", "deploy"):
        return []

    # 已进入合资格的月度重验即视为本次释放窗口已处理。后续不论 active
    # 是否为空，都在 target plan 之后一次性清除 pending/trigger。
    g.fz2_release_evaluated = True

    fresh = set(str(code) for code in list(entry_ranked))
    active = [code for code in list(entry_ranked) if str(code) in pool and str(code) in fresh]
    invalidated = [code for code in list(pool) if code not in fresh]
    for code in invalidated:
        pool.pop(code, None)
    g.fz2_deferred_pool = pool
    g.fz2_release_active_codes = list(dict.fromkeys(str(code) for code in active))
    _fz2_emit("monthly_revalidation", {
        "asof": str(asof),
        "effective_policy": str(effective_policy),
        "trigger": dict(getattr(g, "fz2_release_trigger", {}) or {}),
        "valid_count": len(g.fz2_release_active_codes),
        "valid": list(g.fz2_release_active_codes),
        "invalidated_count": len(invalidated),
        "invalidated": invalidated,
        "pool_size_after": len(pool),
    })
    return list(g.fz2_release_active_codes)


def _fz2_prioritize_pool(pool):
    """只改变候选顺序，不增加Policy允许的新证券预算。"""
    pool = list(pool)
    active = set(str(code) for code in getattr(g, "fz2_release_active_codes", []) or [])
    if not active:
        return pool
    priority = [code for code in pool if str(code) in active]
    rest = [code for code in pool if str(code) not in active]
    return priority + rest


def _fz2_after_target_plan(context, targets, asof):
    active = set(str(code) for code in getattr(g, "fz2_release_active_codes", []) or [])
    if not bool(getattr(g, "fz2_release_evaluated", False)):
        return
    holdings = set(_actual_holdings(context))
    selected = [str(code) for code in list(targets) if str(code) in active and str(code) not in holdings]
    _fz2_emit("release_plan", {
        "asof": str(asof),
        "active_count": len(active),
        "selected_count": len(selected),
        "selected": selected,
        "normal_policy_budget": int(getattr(g, "max_new_buys_this_month", 0)),
    })
    # 本次风险升级窗口只使用一次。未被正常预算选中的候选保留在池中，
    # 只有未来再次出现 Freeze->Selective 时才会重新验证/获得优先级。
    g.fz2_release_pending = False
    g.fz2_release_evaluated = False
    g.fz2_release_trigger = {}
    g.fz2_release_active_codes = []


def monthly_rebalance(context):
    month_key = context.current_dt.strftime("%Y-%m")
    if month_key == g.last_rebalance_month:
        return
    if not _is_first_trading_day(context):
        log.warning("跳过非月初首个交易日触发：%s。" % context.current_dt.date())
        return

    asof = context.previous_date
    snapshot = None
    if g.liquidity_controls_enabled:
        snapshot_asof = None
        if isinstance(g.liquidity_last_snapshot, dict):
            snapshot_asof = str(g.liquidity_last_snapshot.get("asof"))
        if snapshot_asof != str(asof):
            snapshot = _update_liquidity_snapshot(asof, "monthly_pretrade")
        else:
            snapshot = dict(g.liquidity_last_snapshot)
        decision = _apply_extreme_risk_snapshot(snapshot)
        g.extreme_risk_last_asof = asof
        if (
            g.extreme_risk_state != "normal"
            and decision["trigger_count"] < g.extreme_risk_min_flags
            and g.extreme_risk_release_count >= g.extreme_risk_release_weeks
        ):
            log.info(
                "极端风险连续%d周解除：月度调仓日允许按当前政策恢复仓位。"
                % g.extreme_risk_release_count
            )
            g.extreme_risk_state = "normal"
            g.extreme_risk_release_count = 0
    else:
        snapshot = {"action_policy": "core_baseline", "stress_flags": {}}
        g.extreme_risk_state = "normal"

    # 先完成当月Buffett与机构研究，使E3/E4可以用本月主线质量否决虚假deploy。
    buffett_ranked, entry_ranked, score_map, diagnostics = build_ranked_candidates(
        context, asof
    )
    g.pending_ranked = buffett_ranked
    g.pending_entry_ranked = entry_ranked
    g.pending_scores = score_map
    g.price50_gate_audit_months = int(
        getattr(g, "price50_gate_audit_months", 0)
    ) + 1
    log.info("V18E1_PRICE50_GATE|%s" % json.dumps({
        "asof": str(asof),
        "event": "monthly_entry_gate",
        "input": int(diagnostics.get("price50_gate_input", 0)),
        "raw_close_valid": int(
            diagnostics.get("price50_raw_close_valid", 0)
        ),
        "raw_close_missing": int(
            diagnostics.get("price50_raw_close_missing", 0)
        ),
        "raw_close_query_failures": int(
            diagnostics.get("price50_raw_close_query_failures", 0)
        ),
        "financial_pass": int(
            diagnostics.get("price50_financial_pass", 0)
        ),
        "price_5_to_50_pass": int(
            diagnostics.get("price50_price_pass", 0)
        ),
        "market_cap_30yi_pass": int(
            diagnostics.get("price50_market_cap_pass", 0)
        ),
        "combined_entry_pass": int(
            diagnostics.get("price50_entry_pass", 0)
        ),
        "strict_candidates_after_all_mother_gates": int(
            diagnostics.get("quality_entry_pass", 0)
        ),
        "minimum_close_exclusive": float(g.price50_min_close_exclusive),
        "maximum_close_inclusive": float(g.price50_max_close_inclusive),
        "minimum_market_cap_yi": float(g.price50_min_market_cap_yi),
        "ranking_policy": "preserve_full_mother_cross_section_no_rerank",
        "entry_only": True,
        "existing_holding_forced_exit": False,
        "leverage_topup_price_gate": False,
        "dynamic_leverage_max": float(g.dynamic_leverage_max),
        "hls_cap_enabled": False,
    }, ensure_ascii=False, sort_keys=True, default=str))
    log_month_end_top50(asof, buffett_ranked, score_map)

    raw_policy = (
        str(getattr(g, "liquidity_policy", "warming_up"))
        if g.liquidity_controls_enabled else "core_baseline"
    )
    effective_policy = (
        _effective_allocation_policy(raw_policy, snapshot)
        if g.liquidity_controls_enabled else "core_baseline"
    )
    g.effective_allocation_policy = effective_policy
    leverage_decision = _update_dynamic_leverage_state(
        snapshot, effective_policy, "monthly_rebalance", context=context
    )
    if g.liquidity_controls_enabled:
        g.current_target_exposure = _guarded_target_exposure(
            context, effective_policy
        )
        g.max_new_buys_this_month = _liquidity_new_buy_limit(effective_policy)
        if g.extreme_risk_state != "normal":
            g.max_new_buys_this_month = 0
    else:
        g.current_target_exposure = g.base_target_exposure
        g.max_new_buys_this_month = 2

    # FZ2路径：Freeze不新建证券；通过母版全部门和PRICE50入场门的严格候选
    # 才进入Deferred Pool。风险升级后仍用当月fresh entry_ranked重新验证，
    # 并共享原Selective/Deploy预算。
    _fz2_capture_candidates(context, asof, effective_policy, entry_ranked)
    _fz2_prepare_monthly_release(context, asof, effective_policy, entry_ranked)

    if raw_policy != effective_policy or getattr(g, "latest_allocation_policy_reasons", []):
        log.info(
            "组合执行政策覆盖：流动性原始=%s，实际=%s，原因=%s，动态杠杆=%.2f，目标股票仓位=%.1f%%。"
            % (
                raw_policy, effective_policy,
                getattr(g, "latest_allocation_policy_reasons", []),
                g.leverage_multiplier,
                g.current_target_exposure * 100.0,
            )
        )

    targets = build_target_list(context, buffett_ranked, entry_ranked)
    g.pending_targets = targets
    _fz2_after_target_plan(context, targets, asof)
    execute_rebalance(context, targets)
    g.last_rebalance_month = month_key

    log.info(
        "月度筛选：原始政策=%s/执行政策=%s/本月最多新买=%d/机构模式=%s/主线行业=%d/目标仓位=%.0f%%；历史股票池=%d，"
        "基本面有效=%d，研究池=%d，价量有效=%d，周线数据有效=%d，"
        "EXPMA5在20上方=%d，BOLL恢复分支=%d，"
        "EXPMA5角度>%.1f度=%d，BOLL中轨角度>=%.1f度=%d，核心买入趋势通过=%d，"
        "常态利润请求/有效/通过=%d/%d/%d，Buffett研究前50=%d，"
        "严格买入因子通过=%d，可买核心/响应=%d/%d，机构可行动=%s，合并候选=%d，目标持仓=%d。"
        % (
            raw_policy,
            effective_policy,
            g.max_new_buys_this_month,
            diagnostics.get("mainline_mode", "BASELINE"),
            diagnostics.get("entry_industries", 0),
            g.current_target_exposure * 100.0,
            diagnostics.get("universe", 0),
            diagnostics.get("fundamental_valid", 0),
            diagnostics.get("research_pool", 0),
            diagnostics.get("price_valid", 0),
            diagnostics.get("weekly_data_valid", 0),
            diagnostics.get("trend_fast_above_slow", 0),
            diagnostics.get("trend_boll_recovery_pass", 0),
            g.trend_min_angle,
            diagnostics.get("trend_angle_pass", 0),
            g.trend_boll_min_angle,
            diagnostics.get("trend_boll_direction_pass", 0),
            diagnostics.get("weekly_trend_pass", 0),
            diagnostics.get("normalized_requested", 0),
            diagnostics.get("normalized_valid", 0),
            diagnostics.get("normalized_entry_pass", 0),
            diagnostics.get("buffett_top50", 0),
            diagnostics.get("quality_entry_pass", 0),
            diagnostics.get("affordable_core", 0),
            diagnostics.get("affordable_response", 0),
            diagnostics.get("institution_actionable", False),
            diagnostics.get("affordable", 0),
            len(targets),
        )
    )
    log.info(
        "目标组合：%s"
        % [
            "%s 总分=%.3f/质=%.3f/安=%.3f/值=%.3f"
            % (
                _stock_label(code),
                score_map.get(code, {}).get("total", np.nan),
                score_map.get(code, {}).get("quality", np.nan),
                score_map.get(code, {}).get("safety", np.nan),
                score_map.get(code, {}).get("value", np.nan),
            )
            for code in targets
        ]
    )

































def _record_leverage_market(snapshot=None, context=None, actual_exposure=None):
    """聚宽自定义图表只展示实际股票总暴露率(%)与市场综合分数。"""
    if snapshot is None:
        snapshot = getattr(g, "liquidity_last_snapshot", {}) or {}
    try:
        market_score = float(snapshot.get("environment_score", np.nan))
    except (TypeError, ValueError):
        market_score = np.nan
    if not np.isfinite(market_score):
        market_score = np.nan

    exposure = actual_exposure
    if exposure is None and context is not None:
        try:
            exposure = _l16_margin_metrics(context).get("gross_exposure")
        except Exception:
            exposure = None
    try:
        exposure = float(exposure)
    except (TypeError, ValueError):
        exposure = np.nan
    if not np.isfinite(exposure) or exposure < 0:
        try:
            exposure = float(
                getattr(g, "latest_actual_gross_exposure", np.nan)
            )
        except (TypeError, ValueError):
            exposure = np.nan
    if not np.isfinite(exposure) or exposure < 0:
        exposure = 0.0

    g.latest_actual_gross_exposure = float(exposure)
    if context is not None:
        try:
            g.latest_actual_gross_exposure_asof = str(context.current_dt)
        except Exception:
            pass
    record(
        actual_exposure_pct=float(exposure) * 100.0,
        market_score=market_score,
    )


def monthly_after_close(context):
    if g.last_rebalance_month != context.current_dt.strftime("%Y-%m"):
        return
    trades = get_trades()
    if trades:
        for trade in trades.values():
            log.info("成交记录：%s" % str(trade))
    holdings = _actual_holdings(context)
    if (
        getattr(g, "initial_build_enabled", False)
        and not getattr(g, "initial_build_completed", False)
        and len(holdings) >= g.min_core_slots
    ):
        g.initial_build_completed = True
        g.initial_build_effective_cap = g.max_holdings
        log.info(
            "分阶段初始建仓完成：实际持仓%d只达到最低核心结构%d只；后续恢复最多%d只。"
            % (len(holdings), g.min_core_slots, g.max_holdings)
        )
    margin_metrics = _l16_margin_metrics(context)
    debt_state = _debt_risk_state(context)
    drawdown_state = _update_portfolio_drawdown_guard(
        context,
        asof=str(context.previous_date),
        allow_release=False,
    )
    _record_leverage_market(
        context=context,
        actual_exposure=margin_metrics.get("gross_exposure"),
    )
    log.info(
        "月度调仓后持仓 %d/%d：%s；净资产=%.2f，股票总市值=%.2f，融资负债=%.2f，"
        "总股票暴露=%.2f%%，可用现金=%.2f。"
        % (
            len(holdings),
            g.max_holdings,
            [_stock_label(code) for code in holdings],
            margin_metrics["net_value"],
            margin_metrics["gross_position_value"],
            margin_metrics["cash_liability"] + margin_metrics["interest_liability"],
            margin_metrics["gross_exposure"] * 100.0
            if np.isfinite(margin_metrics["gross_exposure"]) else np.nan,
            margin_metrics["available_cash"],
        )
    )
    total_value = float(margin_metrics["net_value"])
    cash_value = float(margin_metrics["available_cash"])
    check = {
        "date": str(context.current_dt.date()),
        "holding_count": int(len(holdings)),
        "target_count": int(len(getattr(g, "pending_targets", []))),
        # 杠杆账户现金比例用1-总股票暴露表示；融资状态下可以为负数。
        "cash_ratio": (
            float(1.0 - margin_metrics["gross_exposure"])
            if np.isfinite(margin_metrics["gross_exposure"]) else None
        ),
        "target_exposure": float(g.current_target_exposure),
        "leverage_multiplier": float(g.leverage_multiplier),
        "dynamic_leverage_stage_age": int(
            getattr(g, "dynamic_leverage_stage_age", 0)
        ),
        "dynamic_leverage_last_decision": dict(
            getattr(g, "dynamic_leverage_last_decision", {})
        ),
        "dynamic_leverage_change_count": int(
            getattr(g, "dynamic_leverage_change_count", 0)
        ),
        "dynamic_leverage_increase_count": int(
            getattr(g, "dynamic_leverage_increase_count", 0)
        ),
        "dynamic_leverage_decrease_count": int(
            getattr(g, "dynamic_leverage_decrease_count", 0)
        ),
        "dynamic_leverage_policy_confirm_weeks": int(
            getattr(g, "dynamic_leverage_policy_confirm_weeks", 0)
        ),
        "dynamic_leverage_improve_confirm_weeks": int(
            getattr(g, "dynamic_leverage_improve_confirm_weeks", 0)
        ),
        "dynamic_leverage_recovery_lock_remaining": int(
            getattr(g, "dynamic_leverage_recovery_lock_remaining", 0)
        ),
        "dynamic_single_weight_cap": float(
            _dynamic_single_weight_cap(context)
        ),
        "portfolio_peak_net_value": (
            float(g.portfolio_peak_net_value)
            if getattr(g, "portfolio_peak_net_value", None) is not None
            else None
        ),
        "portfolio_drawdown": float(
            getattr(g, "portfolio_drawdown", 0.0)
        ),
        "drawdown_guard_cap": float(
            getattr(g, "drawdown_guard_cap", 1.60)
        ),
        "drawdown_guard_release_count": int(
            getattr(g, "drawdown_guard_release_count", 0)
        ),
        "debt_ratio": (
            float(margin_metrics["debt_ratio"])
            if np.isfinite(margin_metrics["debt_ratio"])
            else None
        ),
        "reported_debt_ratio": (
            float(margin_metrics["reported_debt_ratio"])
            if np.isfinite(margin_metrics["reported_debt_ratio"])
            else None
        ),
        "inferred_debt_ratio": (
            float(margin_metrics["inferred_debt_ratio"])
            if np.isfinite(margin_metrics["inferred_debt_ratio"])
            else None
        ),
        "liability_source": str(
            margin_metrics["liability_source"]
        ),
        "financing_demand_ratio": max(
            0.0, float(g.current_target_exposure) - 1.0
        ),
        "margin_successful_order_calls": int(
            getattr(g, "margin_successful_order_calls", 0)
        ),
        "margin_metric_diagnostic": dict(
            getattr(g, "margin_last_diagnostic", {})
        ),
        "financing_gate_status": str(
            getattr(g, "financing_gate_status", "unknown")
        ),
        "financing_gate_reasons": list(
            getattr(g, "financing_gate_reasons", [])
        ),
        "financing_gate_warning_reasons": list(
            getattr(g, "financing_gate_warning_reasons", [])
        ),
        "weekly_state_history": list(
            getattr(g, "dynamic_leverage_weekly_history", [])
        ),
        "strong_deploy_weeks": int(
            getattr(g, "dynamic_leverage_strong_deploy_weeks", 0)
        ),
        "exposure_maintenance_count": int(
            getattr(g, "exposure_maintenance_count", 0)
        ),
        "exposure_maintenance_last_result": dict(
            getattr(g, "exposure_maintenance_last_result", {})
        ),
        "new_financing_blocked": bool(
            getattr(g, "dynamic_leverage_new_financing_blocked", False)
        ),
        "financing_block_reasons": list(
            getattr(g, "dynamic_leverage_financing_block_reasons", [])
        ),
        "exposure_reconcile_attempts": int(
            getattr(g, "exposure_reconcile_attempts", 0)
        ),
        "exposure_reconcile_failures": int(
            getattr(g, "exposure_reconcile_failures", 0)
        ),
        "exposure_reconcile_buy_lock": bool(
            getattr(g, "exposure_reconcile_buy_lock", False)
        ),
        "exposure_reconcile_last_result": dict(
            getattr(g, "exposure_reconcile_last_result", {})
        ),
        "gross_leverage_cap": float(g.gross_leverage_cap),
        "net_value": float(margin_metrics["net_value"]),
        "gross_position_value": float(margin_metrics["gross_position_value"]),
        "cash_liability": float(margin_metrics["cash_liability"]),
        "interest_liability": float(margin_metrics["interest_liability"]),
        "total_liability": float(margin_metrics["total_liability"]),
        "maintenance_margin_rate": (
            float(margin_metrics["maintenance_margin_rate"])
            if np.isfinite(margin_metrics["maintenance_margin_rate"]) else None
        ),
        "available_margin": (
            float(margin_metrics["available_margin"])
            if np.isfinite(margin_metrics["available_margin"]) else None
        ),
        "margin_order_calls": int(getattr(g, "margin_order_calls", 0)),
        "margin_order_failures": int(getattr(g, "margin_order_failures", 0)),
        "response_holdings": int(sum(
            g.holding_roles.get(code) == "response" for code in holdings
        )),
        "response_codes": [
            code for code in holdings if g.holding_roles.get(code) == "response"
        ],
        "institution_mode": str(getattr(g, "latest_mainline_mode", "unknown")),
        "institution_actionable": bool(_institution_response_actionable()),
        "response_candidates": int(len(getattr(g, "pending_response_entry_ranked", []))),
        "response_security_changes": int(getattr(g, "response_security_changes_this_month", 0)),
        "response_role_promotions": int(getattr(g, "response_role_promotions_this_month", 0)),
        "response_role_demotions": int(getattr(g, "response_role_demotions_this_month", 0)),
        "industry_limit": int(g.max_industry_holdings),
        "initial_build_stage": int(getattr(g, "initial_build_stage", 0)),
        "initial_build_completed": bool(getattr(g, "initial_build_completed", False)),
        "initial_build_cap": int(getattr(g, "initial_build_effective_cap", g.max_holdings)),
    }
    actual_exposure = (float(margin_metrics["gross_exposure"]) if np.isfinite(margin_metrics["gross_exposure"]) else None)
    planned_exposure = float(getattr(g, "pending_planned_exposure", 0.0))
    actual_equity_beta, actual_account_beta, actual_beta_missing = (
        _actual_weighted_beta(context, holdings)
    )
    check.update({
        "actual_exposure": actual_exposure,
        "planned_post_watch_exposure": planned_exposure,
        "exposure_gap": (
            actual_exposure - planned_exposure
            if actual_exposure is not None else None
        ),
        "target_weights": dict(getattr(g, "pending_target_weights", {})),
        "raw_target_weights": dict(getattr(g, "pending_raw_target_weights", {})),
        "planned_equity_beta": (
            float(g.pending_planned_equity_beta)
            if np.isfinite(getattr(g, "pending_planned_equity_beta", np.nan)) else None
        ),
        "planned_account_beta": (
            float(g.pending_planned_account_beta)
            if np.isfinite(getattr(g, "pending_planned_account_beta", np.nan)) else None
        ),
        "actual_equity_beta": (
            float(actual_equity_beta) if np.isfinite(actual_equity_beta) else None
        ),
        "actual_account_beta": (
            float(actual_account_beta) if np.isfinite(actual_account_beta) else None
        ),
        "actual_beta_missing": list(actual_beta_missing),
        "rounding_redeploy_value": float(
            getattr(g, "pending_rounding_redeploy_value", 0.0)
        ),
        "watch_replacements": int(
            getattr(g, "watch_replacement_count_this_month", 0)
        ),
        "pre_trade_exposure": float(
            getattr(g, "pending_pre_trade_exposure", 0.0)
        ),
        "planned_exposure": planned_exposure,
        "projected_post_order_exposure": float(
            getattr(g, "pending_projected_post_order_exposure", 0.0)
        ),
        "exposure_guard_ceiling": float(
            getattr(g, "pending_exposure_guard_ceiling", 0.0)
        ),
        "exposure_band_bypass_sells": list(
            getattr(g, "pending_exposure_band_bypass_sells", [])
        ),
        "buy_lots_blocked_by_exposure_guard": int(
            getattr(g, "pending_buy_lots_blocked_by_exposure_guard", 0)
        ),
        "locked_exposure": float(
            getattr(g, "pending_locked_exposure", 0.0)
        ),
        "institution_reason": str(
            getattr(g, "latest_mainline_meta", {}).get("reason", "unknown")
        ),
        "institution_current_period": (
            getattr(g, "latest_mainline_meta", {}).get("fund", {}).get("current_period")
        ),
        "institution_previous_period": (
            getattr(g, "latest_mainline_meta", {}).get("fund", {}).get("previous_period")
        ),
        "institution_fund_age_days": (
            getattr(g, "latest_mainline_meta", {}).get("fund", {}).get("current_period_age_days")
        ),
        "institution_valid_funds": (
            getattr(g, "latest_mainline_meta", {}).get("fund", {}).get("current_valid_funds")
            or getattr(g, "latest_mainline_meta", {}).get("fund", {}).get("funds")
        ),
        "institution_comparable_funds": (
            getattr(g, "latest_mainline_meta", {}).get("fund", {}).get("comparable_funds")
        ),
        "institution_relative_coverage": (
            getattr(g, "latest_mainline_meta", {}).get("fund", {}).get("relative_coverage")
        ),
        "institution_market_value_coverage": (
            getattr(g, "latest_mainline_meta", {}).get("fund", {}).get("market_value_coverage")
        ),
        "liquidity_policy": str(getattr(g, "liquidity_policy", "unknown")),
        "liquidity_policy_age": int(getattr(g, "liquidity_policy_age", 0)),
        "liquidity_new_buy_limit": int(getattr(g, "max_new_buys_this_month", 0)),
        "effective_new_buy_budget": int(getattr(g, "effective_new_buy_budget", 0)),
        "extreme_risk_state": str(getattr(g, "extreme_risk_state", "normal")),
        "extreme_risk_trigger_count": int(getattr(g, "extreme_risk_trigger_count", 0)),
        "extreme_risk_release_count": int(getattr(g, "extreme_risk_release_count", 0)),
        "liquidity_score": (
            float(g.liquidity_last_snapshot.get("pure_liquidity_score"))
            if isinstance(getattr(g, "liquidity_last_snapshot", None), dict)
            and np.isfinite(g.liquidity_last_snapshot.get("pure_liquidity_score", np.nan))
            else None
        ),
        "liquidity_structure": (
            str(g.liquidity_last_snapshot.get("structure"))
            if isinstance(getattr(g, "liquidity_last_snapshot", None), dict)
            else None
        ),
        "liquidity_macro_state": str(getattr(g, "liquidity_macro_state", "warming_up")),
    })
    exposure_thresholds = _exposure_audit_thresholds(planned_exposure)
    planned_notice_ceiling = float(
        exposure_thresholds["planned_notice_ceiling"]
    )
    policy_hard_ceiling = float(
        exposure_thresholds["policy_hard_ceiling"]
    )
    check.update({
        "planned_notice_ceiling": planned_notice_ceiling,
        "policy_hard_ceiling": policy_hard_ceiling,
    })
    if actual_exposure is not None:
        try:
            actual_number = float(actual_exposure)
        except (TypeError, ValueError):
            actual_number = np.nan
        if np.isfinite(actual_number):
            if actual_number > policy_hard_ceiling + 1e-8:
                log.warning(
                    "组合仓位收盘硬风险：实际%.2f%% > 政策硬风险线%.2f%%；"
                    "可能来自未成交、不可卖锁仓或异常超仓。"
                    % (
                        actual_number * 100.0,
                        policy_hard_ceiling * 100.0,
                    )
                )
            elif actual_number > planned_notice_ceiling + 1e-8:
                log.info(
                    "组合仓位收盘提示：实际%.2f%% > 计划偏差提示线%.2f%%，"
                    "但未突破政策硬风险线%.2f%%；通常来自整手取整或盘中价格波动。"
                    % (
                        actual_number * 100.0,
                        planned_notice_ceiling * 100.0,
                        policy_hard_ceiling * 100.0,
                    )
                )
    check["release_parameter_fingerprint"] = str(
        getattr(g, "release_parameter_fingerprint", "")
    )
    audit = _formal_release_runtime_audit(context, holdings, check)
    check["release_audit_status"] = str(audit.get("status", "unknown"))
    check["release_behavior_baseline"] = str(g.release_behavior_baseline)
    log.info("V18E1_PORTFOLIO_CHECK|%s" % json.dumps(check, ensure_ascii=False, sort_keys=True))



def weekly_extreme_risk_check(context):
    """周度杠杆引擎独立运行；风险快照可复用，但绝不整段跳过。"""
    asof = context.previous_date
    snapshot_asof = None
    if isinstance(getattr(g, "liquidity_last_snapshot", None), dict):
        snapshot_asof = str(g.liquidity_last_snapshot.get("asof"))

    if snapshot_asof == str(asof):
        snapshot = dict(g.liquidity_last_snapshot)
        snapshot["event"] = "weekly_radar_reused_snapshot"
    else:
        snapshot = _update_liquidity_snapshot(asof, "weekly_radar")

    previous_target = float(g.current_target_exposure)
    pre_metrics = _l16_margin_metrics(context)
    pre_actual = pre_metrics["gross_exposure"]

    if str(asof) != str(getattr(g, "extreme_risk_last_asof", None)):
        risk_decision = _apply_extreme_risk_snapshot(snapshot)
        g.extreme_risk_last_asof = asof
    else:
        # 相同asof已由月度/其他流程处理过风险状态。
        # 此处只读取原始硬风险标记用于周度杠杆判断，不能再次调用
        # _apply_extreme_risk_snapshot()，否则会重复累计风险解除周数。
        flags = dict(snapshot.get("stress_flags", {}) or {})
        risk_decision = {
            "flags": dict(flags),
            "trigger_count": int(sum(bool(v) for v in flags.values())),
            "previous_state": str(g.extreme_risk_state),
            "state": str(g.extreme_risk_state),
            "previous_exposure": float(g.current_target_exposure),
            "target_exposure": float(g.current_target_exposure),
            "lowered": False,
            "release_count": int(g.extreme_risk_release_count),
            "snapshot_reused": True,
            "risk_flag_source": "snapshot.stress_flags_read_only",
        }
        log.info(
            "周度风险快照复用：asof=%s，硬风险数量=%d，不重复更新extreme_risk_state。"
            % (asof, risk_decision["trigger_count"])
        )
    raw_policy = str(
        snapshot.get(
            "action_policy",
            getattr(g, "liquidity_policy", "warming_up"),
        )
    )
    effective_policy = _effective_allocation_policy(raw_policy, snapshot)
    g.effective_allocation_policy = effective_policy

    leverage_decision = _update_dynamic_leverage_state(
        snapshot, effective_policy, "weekly_radar", context=context
    )
    desired_target = _guarded_target_exposure(context, effective_policy)
    g.current_target_exposure = float(desired_target)
    structure_cap = float(
        _current_structure_exposure_cap(
            context,
            candidate_multiplier=g.leverage_multiplier,
        )
    )
    executable_target = min(float(desired_target), float(structure_cap))

    # 以真实总股票暴露决定是否行动，而不是只比较上周的目标值。
    if not np.isfinite(pre_actual):
        pre_actual = previous_target

    tolerance = float(g.dynamic_leverage_rebalance_band)
    must_reduce = bool(
        pre_actual > desired_target + tolerance
        or risk_decision["lowered"]
        or leverage_decision["decreased"]
    )

    base_target = min(
        1.0,
        _policy_unlevered_exposure(effective_policy),
    )
    executable_base_target = min(base_target, executable_target)
    base_gap = bool(
        pre_actual
        < executable_base_target - float(g.base_exposure_maintenance_band)
    )
    leveraged_gap = bool(
        desired_target > 1.0
        and executable_target > 1.0
        and pre_actual
        < executable_target
        - float(g.leveraged_exposure_maintenance_band)
    )
    stage_increase = bool(
        leverage_decision.get("increased", False)
        and leverage_decision.get("is_new_weekly", False)
    )
    maintenance_needed = bool(base_gap or leveraged_gap)

    may_increase = bool(
        (stage_increase or maintenance_needed)
        and pre_actual < executable_target - tolerance
        and risk_decision["trigger_count"] < g.extreme_risk_min_flags
        and g.extreme_risk_state == "normal"
        and not getattr(g, "exposure_reconcile_buy_lock", False)
    )

    if must_reduce:
        log.info(
            "动态杠杆快速降仓：原始政策=%s，执行政策=%s，"
            "杠杆%.2f→%.2f，实际暴露%.1f%%，政策目标%.1f%%，"
            "当前结构可执行%.1f%%，硬风险=%d项。"
            % (
                raw_policy,
                effective_policy,
                leverage_decision["old_multiplier"],
                leverage_decision["new_multiplier"],
                pre_actual * 100.0,
                desired_target * 100.0,
                executable_target * 100.0,
                risk_decision["trigger_count"],
            )
        )
        action = reduce_positions_for_extreme_risk(context)
        action["direction"] = "decrease"

    elif may_increase:
        increase_mode = (
            "stage_increase"
            if stage_increase
            else (
                "base_exposure_maintenance"
                if base_gap
                else "leveraged_exposure_maintenance"
            )
        )
        log.info(
            "动态仓位增仓：模式=%s，原始政策=%s，执行政策=%s，"
            "杠杆%.2f→%.2f，实际暴露%.1f%%，政策目标%.1f%%，"
            "当前结构可执行%.1f%%；只增加现有健康持仓。"
            % (
                increase_mode,
                raw_policy,
                effective_policy,
                leverage_decision["old_multiplier"],
                leverage_decision["new_multiplier"],
                pre_actual * 100.0,
                desired_target * 100.0,
                executable_target * 100.0,
            )
        )
        action = increase_positions_for_dynamic_leverage(context)
        action["direction"] = "increase"
        action["increase_mode"] = increase_mode
        if maintenance_needed:
            g.exposure_maintenance_count += 1
            g.exposure_maintenance_last_result = dict(action)

    else:
        log.info(
            "动态杠杆周度观察：原始政策=%s，执行政策=%s，"
            "杠杆=%.2f，实际暴露=%.1f%%，政策目标=%.1f%%，"
            "当前结构可执行=%.1f%%，硬风险=%d项；无需交易。"
            % (
                raw_policy,
                effective_policy,
                g.leverage_multiplier,
                pre_actual * 100.0,
                desired_target * 100.0,
                executable_target * 100.0,
                risk_decision["trigger_count"],
            )
        )
        return

    action.update({
        "asof": str(asof),
        "raw_policy": raw_policy,
        "effective_policy": effective_policy,
        "risk_state": str(g.extreme_risk_state),
        "trigger_count": int(risk_decision["trigger_count"]),
        "flags": dict(risk_decision["flags"]),
        "previous_target_exposure": float(previous_target),
        "new_target_exposure": float(desired_target),
        "policy_target_exposure": float(desired_target),
        "current_structure_exposure_cap": float(structure_cap),
        "current_structure_target_exposure": float(executable_target),
        "leverage_decision": dict(leverage_decision),
        "policy_reasons": list(
            getattr(g, "latest_allocation_policy_reasons", [])
        ),
    })
    log.info(
        "V18E1LEV12_POLICY_ACTION|%s"
        % json.dumps(
            _liquidity_json_safe(action),
            ensure_ascii=True,
            sort_keys=True,
        )
    )


def increase_positions_for_dynamic_leverage(context):
    """周度增杠杆只按比例增加现有健康持仓，不新增证券、不加WATCH仓。"""
    holdings = _actual_holdings(context)
    metrics = _l16_margin_metrics(context)
    net_value = float(metrics["net_value"])
    current_gross_value = float(metrics["gross_position_value"])
    current_exposure = float(metrics["gross_exposure"])
    policy_target_exposure = float(g.current_target_exposure)
    structure_cap = float(
        _current_structure_exposure_cap(
            context,
            candidate_multiplier=g.leverage_multiplier,
        )
    )
    target_exposure = min(policy_target_exposure, structure_cap)
    if (
        not holdings
        or net_value <= 0
        or not np.isfinite(current_exposure)
        or target_exposure <= current_exposure + float(g.dynamic_leverage_rebalance_band)
    ):
        return {
            "pre_exposure": current_exposure if np.isfinite(current_exposure) else None,
            "target_exposure": target_exposure,
            "policy_target_exposure": policy_target_exposure,
            "current_structure_exposure_cap": structure_cap,
            "projected_exposure": current_exposure if np.isfinite(current_exposure) else None,
            "buy_orders": 0,
            "eligible_codes": [],
        }

    current_data = get_current_data()
    eligible = []
    fixed_value = 0.0
    current_weights = {}
    for code in holdings:
        position = context.portfolio.positions.get(code)
        value = float(getattr(position, "value", 0.0)) if position is not None else 0.0
        current_weights[code] = value / net_value if net_value > 0 else 0.0
        holding_return = _current_holding_return(context, code, current_data)
        thesis_watch = (
            g.holding_thesis_states.get(code, "HEALTHY") == "WATCH"
        )
        price_watch = bool(
            np.isfinite(holding_return)
            and holding_return <= g.stop_watch_loss
        )
        if thesis_watch or price_watch:
            fixed_value += max(0.0, value)
        else:
            eligible.append(code)

    if not eligible:
        log.warning("动态杠杆增仓取消：没有可加仓的健康现有持仓。")
        return {
            "pre_exposure": current_exposure,
            "target_exposure": target_exposure,
            "policy_target_exposure": policy_target_exposure,
            "current_structure_exposure_cap": structure_cap,
            "projected_exposure": current_exposure,
            "buy_orders": 0,
            "eligible_codes": [],
        }

    # 固定WATCH仓保持原值，其余目标按当前健康持仓权重比例分配。
    healthy_budget_weight = max(
        0.0,
        target_exposure - fixed_value / net_value,
    )
    factors = {
        code: max(current_weights.get(code, 0.0), 1e-6)
        for code in eligible
    }
    target_weights = _weighted_capped_allocation(
        eligible,
        factors,
        healthy_budget_weight,
        _dynamic_single_weight_cap(context),
    )

    marginable = _l16_marginable_stocks(context)
    rank = {code: index for index, code in enumerate(eligible)}
    # 非融资标的先使用自有现金，可融资标的随后承接融资差额。
    sequence = sorted(
        eligible,
        key=lambda code: (
            code in marginable,
            rank.get(code, 10 ** 9),
        ),
    )
    projected_value = current_gross_value
    buy_orders = 0
    blocked = []
    for code in sequence:
        position = context.portfolio.positions.get(code)
        current_amount = int(
            getattr(position, "total_amount", 0)
        ) if position is not None else 0
        try:
            price = float(current_data[code].last_price)
        except Exception:
            price = np.nan
        if (
            current_amount <= 0
            or not np.isfinite(price)
            or price <= 0
            or not _is_trade_eligible(code, current_data, for_buy=True)
        ):
            continue

        desired_value = net_value * float(target_weights.get(code, 0.0))
        desired_amount = int(desired_value / price / 100.0) * 100
        desired_amount = max(current_amount, desired_amount)
        if desired_amount <= current_amount:
            continue

        remaining_room = max(
            0.0,
            net_value * target_exposure - projected_value,
        )
        allowed_add_amount = int(
            remaining_room / price / 100.0
        ) * 100
        target_amount = min(
            desired_amount,
            current_amount + max(0, allowed_add_amount),
        )
        if target_amount <= current_amount:
            blocked.append(code)
            continue

        order_obj = _l16_order_target(context, code, target_amount)
        if order_obj is not None:
            buy_orders += 1
            projected_value += (target_amount - current_amount) * price
            log.info(
                "动态杠杆周度增仓 %s：%d股→%d股，"
                "目标总暴露%.1f%%，当前杠杆%.2f。"
                % (
                    _stock_label(code),
                    current_amount,
                    target_amount,
                    target_exposure * 100.0,
                    g.leverage_multiplier,
                )
            )

    return {
        "pre_exposure": current_exposure,
        "target_exposure": target_exposure,
        "policy_target_exposure": policy_target_exposure,
        "current_structure_exposure_cap": structure_cap,
        "projected_exposure": (
            projected_value / net_value if net_value > 0 else None
        ),
        "buy_orders": int(buy_orders),
        "eligible_codes": list(eligible),
        "blocked_codes": list(blocked),
    }


def reduce_positions_for_extreme_risk(context):
    """按当前持仓比例降仓；不可卖仓位先占用风险预算，绝不产生买单。"""
    holdings = _actual_holdings(context)
    total_value = float(context.portfolio.total_value)
    if not holdings or total_value <= 0:
        return {
            "pre_exposure": 0.0,
            "target_exposure": float(g.current_target_exposure),
            "projected_exposure": 0.0,
            "locked_exposure": 0.0,
            "sell_orders": 0,
        }

    current_data = get_current_data()
    position_rows = []
    for code in holdings:
        position = context.portfolio.positions.get(code)
        if position is None:
            continue
        amount = int(getattr(position, "total_amount", 0))
        value = float(getattr(position, "value", 0.0))
        try:
            price = float(current_data[code].last_price)
        except Exception:
            price = np.nan
        if amount <= 0 or value <= 0 or not np.isfinite(price) or price <= 0:
            continue
        sellable = bool(_can_sell(context, code, current_data))
        position_rows.append({
            "code": code,
            "amount": amount,
            "value": value,
            "price": price,
            "sellable": sellable,
        })

    pre_equity_value = sum(row["value"] for row in position_rows)
    locked_value = sum(row["value"] for row in position_rows if not row["sellable"])
    sellable_value = sum(row["value"] for row in position_rows if row["sellable"])
    desired_equity_value = total_value * float(g.current_target_exposure)
    desired_sellable_value = max(0.0, desired_equity_value - locked_value)
    scale = (
        min(1.0, desired_sellable_value / sellable_value)
        if sellable_value > 0 else 0.0
    )

    projected_equity_value = locked_value
    sell_orders = 0
    skipped = []
    for row in position_rows:
        code = row["code"]
        if not row["sellable"]:
            log.warning("极端风险降仓但当前不可卖 %s。" % _stock_label(code))
            continue
        current_amount = row["amount"]
        target_amount = int(current_amount * scale / 100.0) * 100
        target_amount = max(0, min(current_amount, target_amount))
        projected_equity_value += target_amount * row["price"]
        if target_amount >= current_amount:
            continue
        if 0 < current_amount - target_amount < 100:
            skipped.append(code)
            continue
        order = _l16_order_target(context, code, target_amount)
        if order is not None:
            sell_orders += 1
            log.info(
                "极端风险比例减仓 %s：%d股→%d股，保留比例%.1f%%。"
                % (_stock_label(code), current_amount, target_amount, scale * 100.0)
            )

    projected_exposure = projected_equity_value / total_value
    if locked_value > desired_equity_value + 1e-8:
        log.warning(
            "极端风险目标无法完全达到：不可卖仓位%.2f%%已高于目标%.2f%%。"
            % (locked_value / total_value * 100.0, g.current_target_exposure * 100.0)
        )
    return {
        "pre_exposure": pre_equity_value / total_value,
        "target_exposure": float(g.current_target_exposure),
        "projected_exposure": float(projected_exposure),
        "locked_exposure": float(locked_value / total_value),
        "sellable_scale": float(scale),
        "sell_orders": int(sell_orders),
        "skipped_under_one_lot": list(skipped),
    }


def _load_exit_ohlc(code, asof):
    try:
        frame = get_price(
            code,
            end_date=asof,
            count=g.exit_daily_count,
            frequency="daily",
            fields=["close", "high", "low"],
            skip_paused=True,
            fq="pre",
        )
    except Exception as exc:
        log.warning("持仓风险行情读取失败 %s：%s" % (code, exc))
        return None
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    work = frame.copy()
    if not isinstance(work.index, pd.RangeIndex):
        work = work.reset_index()
    time_column = None
    for column in work.columns:
        if str(column).lower() in ("time", "datetime", "date", "index"):
            time_column = column
            break
    if time_column is None or not _py_builtins.all(x in work.columns for x in ("close", "high", "low")):
        return None
    work.rename(columns={time_column: "time"}, inplace=True)
    work = work.loc[:, ~work.columns.duplicated(keep="last")].copy()
    work["time"] = pd.to_datetime(work["time"], errors="coerce")
    for column in ("close", "high", "low"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work.dropna(subset=["time", "close", "high", "low"], inplace=True)
    work.sort_values("time", inplace=True)
    work.drop_duplicates("time", keep="last", inplace=True)
    return work[["time", "close", "high", "low"]]




def _latest_confirmed_effective_low(frame):
    """最近一个左右各2根日K确认的摆动低点，不使用未来未确认形态。"""
    lows = frame["low"].astype(float).values
    times = frame["time"].values
    left = g.pivot_left
    right = g.pivot_right
    if len(lows) < left + right + 1:
        return None, np.nan
    latest_index = None
    for index in range(left, len(lows) - right):
        window = lows[index - left:index + right + 1]
        if lows[index] <= np.min(window) and (
            lows[index] < np.min(window[:left])
            or lows[index] < np.min(window[left + 1:])
        ):
            latest_index = index
    if latest_index is None:
        return None, np.nan
    return pd.Timestamp(times[latest_index]), float(lows[latest_index])


def _daily_structure_broken(frame, price):
    """价格止损的确认条件：跌破已确认低点，且中期日线趋势已经转弱。"""
    if frame is None or frame.empty or len(frame) < 80:
        return False, np.nan, np.nan, np.nan
    close = pd.to_numeric(frame["close"], errors="coerce").dropna()
    if len(close) < 80:
        return False, np.nan, np.nan, np.nan
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema60 = close.ewm(span=60, adjust=False).mean()
    _, effective_low = _latest_confirmed_effective_low(frame)
    below_low = np.isfinite(effective_low) and price < effective_low
    medium_down = float(ema20.iloc[-1]) < float(ema60.iloc[-1])
    return bool(below_low and medium_down), effective_low, float(ema20.iloc[-1]), float(ema60.iloc[-1])


def _clear_holding_state(code):
    g.holding_thesis_states.pop(code, None)
    g.holding_fundamental_baselines.pop(code, None)
    g.holding_report_states.pop(code, None)
    g.holding_roles.pop(code, None)
    g.response_fail_counts.pop(code, None)
    if hasattr(g, "response_probation_states"):
        g.response_probation_states.pop(str(code), None)
    g.valuation_extreme_counts.pop(code, None)
    g.factor_fail_counts.pop(code, None)
    g.factor_fail_reasons.pop(code, None)
    g.stop_watch_logged.pop(code, None)


def _register_risk_exit(context, code):
    g.reentry_cooldowns[code] = (
        _month_index(context.current_dt.date()) + g.reentry_cooldown_months
    )
    _clear_holding_state(code)


def daily_exposure_and_leverage_guard(context):
    """14:45统一执行回撤、债务、融资和实际仓位护栏。"""
    if not bool(getattr(g, "exposure_reconcile_enabled", True)):
        return

    snapshot = (
        dict(g.liquidity_last_snapshot)
        if isinstance(getattr(g, "liquidity_last_snapshot", None), dict)
        else {
            "asof": str(context.previous_date),
            "action_policy": getattr(g, "liquidity_policy", "data_insufficient"),
            "stress_flags": {},
        }
    )
    policy = str(
        getattr(g, "effective_allocation_policy", None)
        or snapshot.get("action_policy")
        or getattr(g, "liquidity_policy", "data_insufficient")
    )

    # 日内只允许风险护栏降低杠杆，不允许增加。
    leverage_decision = _update_dynamic_leverage_state(
        snapshot,
        policy,
        "daily_guard",
        context=context,
    )
    g.current_target_exposure = _guarded_target_exposure(context, policy)

    metrics = _l16_margin_metrics(context)
    actual = float(metrics["gross_exposure"])
    target = float(g.current_target_exposure)
    structure_cap = float(
        _current_structure_exposure_cap(
            context,
            candidate_multiplier=g.leverage_multiplier,
        )
    )
    executable_target = min(target, structure_cap)
    tolerance = float(g.exposure_reconcile_tolerance)
    result = {
        "date": str(context.current_dt.date()),
        "policy": policy,
        "leverage_multiplier": float(g.leverage_multiplier),
        "actual_exposure": actual if np.isfinite(actual) else None,
        "target_exposure": target,
        "policy_target_exposure": target,
        "current_structure_exposure_cap": structure_cap,
        "current_structure_target_exposure": executable_target,
        "tolerance": tolerance,
        "attempted": False,
        "projected_exposure": actual if np.isfinite(actual) else None,
        "buy_lock": bool(getattr(g, "exposure_reconcile_buy_lock", False)),
        "leverage_decision": leverage_decision,
    }

    if np.isfinite(actual) and actual > target + tolerance:
        g.exposure_reconcile_attempts += 1
        result["attempted"] = True
        log.warning(
            "14:45组合仓位强制校正：实际暴露%.2f%% > 目标%.2f%%+容差%.2f%%。"
            % (actual * 100.0, target * 100.0, tolerance * 100.0)
        )
        action = reduce_positions_for_extreme_risk(context)
        projected = action.get("projected_exposure", actual)
        result["action"] = action
        result["projected_exposure"] = projected
        unresolved = bool(
            projected is None
            or not np.isfinite(projected)
            or projected > target + tolerance
        )
        g.exposure_reconcile_buy_lock = unresolved
        if unresolved:
            g.exposure_reconcile_failures += 1
            log.error(
                "14:45仓位校正未完全解决：预计暴露=%s，目标保险线=%.2f%%；"
                "启用新增买入锁。"
                % (
                    projected,
                    (target + tolerance) * 100.0,
                )
            )
    else:
        # 只有实际仓位已经回到保险线内，才解除新增买入锁。
        g.exposure_reconcile_buy_lock = False

    debt_state = _debt_risk_state(context)
    drawdown_state = _update_portfolio_drawdown_guard(
        context,
        asof=str(context.previous_date),
        allow_release=False,
    )
    result.update({
        "buy_lock": bool(g.exposure_reconcile_buy_lock),
        "debt_ratio": debt_state.get("debt_ratio"),
        "reported_debt_ratio": debt_state.get("reported_debt_ratio"),
        "inferred_debt_ratio": debt_state.get("inferred_debt_ratio"),
        "liability_source": debt_state.get("liability_source"),
        "financing_demand_ratio": max(0.0, target - 1.0),
        "margin_order_calls": int(g.margin_order_calls),
        "margin_successful_order_calls": int(
            g.margin_successful_order_calls
        ),
        "margin_order_failures": int(g.margin_order_failures),
        "financing_blocked": bool(
            getattr(g, "financing_gate_status", "") == "blocked"
        ),
        "financing_gate_status": str(
            getattr(g, "financing_gate_status", "unknown")
        ),
        "financing_block_reasons": list(
            getattr(g, "financing_gate_reasons", [])
        ),
        "financing_warning_reasons": list(
            getattr(g, "financing_gate_warning_reasons", [])
        ),
        "strong_deploy_weeks": int(
            getattr(g, "dynamic_leverage_strong_deploy_weeks", 0)
        ),
        "portfolio_drawdown": float(drawdown_state["drawdown"]),
        "drawdown_leverage_cap": float(drawdown_state["effective_cap"]),
        "debt_leverage_cap": float(debt_state["leverage_cap"]),
        "reconcile_attempts": int(g.exposure_reconcile_attempts),
        "reconcile_failures": int(g.exposure_reconcile_failures),
    })
    g.exposure_reconcile_last_result = dict(result)

    _record_leverage_market(
        context=context,
        actual_exposure=actual,
    )
    log.info(
        "V18E1LEV12_DAILY_GUARD|%s"
        % json.dumps(
            _liquidity_json_safe(result),
            ensure_ascii=True,
            sort_keys=True,
        )
    )


def daily_holding_risk_exit(context):
    """每日安全检查：ST立即退出；价格止损只处理结构破坏和灾难损失。"""
    holdings = _actual_holdings(context)
    if not holdings:
        return
    current_data = get_current_data()
    month_key = context.current_dt.strftime("%Y-%m")
    for code in holdings:
        try:
            data = current_data[code]
            price = float(data.last_price)
            name = str(data.name).upper()
        except Exception:
            continue
        if not np.isfinite(price) or price <= 0:
            continue

        is_risk_name = bool(data.is_st or "ST" in name or "退" in name)
        if is_risk_name:
            if not _can_sell(context, code, current_data):
                log.warning("风险警示退出待执行 %s：ST/退市风险，但当前停牌或跌停。" % _stock_label(code))
                continue
            order = _l16_order_target(context, code, 0)
            if order is not None:
                log.info("风险警示卖出 %s：变为ST或退市风险标的。" % _stock_label(code))
                _register_risk_exit(context, code)
            continue

        position = (
            context.portfolio.positions[code]
            if code in context.portfolio.positions else None
        )
        avg_cost = float(getattr(position, "avg_cost", np.nan))
        if not np.isfinite(avg_cost) or avg_cost <= 0:
            continue
        holding_return = price / avg_cost - 1.0

        if holding_return <= g.stop_disaster_loss:
            if not _can_sell(context, code, current_data):
                log.warning(
                    "灾难止损待执行 %s：收益%.2f%%，当前停牌或跌停。"
                    % (_stock_label(code), holding_return * 100.0)
                )
                continue
            order = _l16_order_target(context, code, 0)
            if order is not None:
                log.info(
                    "灾难止损卖出 %s：收益%.2f%% <= %.1f%%。"
                    % (_stock_label(code), holding_return * 100.0, g.stop_disaster_loss * 100.0)
                )
                _register_risk_exit(context, code)
            continue

        if holding_return <= g.stop_confirm_loss:
            frame = _load_exit_ohlc(code, context.previous_date)
            broken, effective_low, ema20, ema60 = _daily_structure_broken(frame, price)
            if broken:
                if not _can_sell(context, code, current_data):
                    log.warning(
                        "结构止损待执行 %s：收益%.2f%%且结构破坏，当前不可卖。"
                        % (_stock_label(code), holding_return * 100.0)
                    )
                    continue
                order = _l16_order_target(context, code, 0)
                if order is not None:
                    log.info(
                        "结构止损卖出 %s：收益%.2f%%，现价%.2f跌破有效低点%.2f，EMA20 %.2f < EMA60 %.2f。"
                        % (_stock_label(code), holding_return * 100.0, price, effective_low, ema20, ema60)
                    )
                    _register_risk_exit(context, code)
                continue

        if holding_return <= g.stop_watch_loss and g.stop_watch_logged.get(code) != month_key:
            g.stop_watch_logged[code] = month_key
            log.info(
                "持仓观察 %s：收益%.2f%% <= %.1f%%；禁止加仓，但价格本身尚不构成卖出理由。"
                % (_stock_label(code), holding_return * 100.0, g.stop_watch_loss * 100.0)
            )


def _is_first_trading_day(context):
    current_date = context.current_dt.date()
    month_start = current_date.replace(day=1)
    try:
        days = get_trade_days(start_date=month_start, end_date=current_date)
    except Exception as exc:
        log.error("交易日历读取失败：%s" % exc)
        return False
    return bool(days is not None and len(days) and pd.Timestamp(days[0]).date() == current_date)


def _rank_high(series):
    values = pd.to_numeric(series, errors="coerce")
    return values.rank(pct=True, method="average", ascending=True)


def _rank_low(series):
    values = pd.to_numeric(series, errors="coerce")
    return values.rank(pct=True, method="average", ascending=False)


def _safe_numeric(frame, column, default=np.nan):
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _winsorize(series, lower=0.02, upper=0.98):
    values = pd.to_numeric(series, errors="coerce")
    clean = values.dropna()
    if clean.empty:
        return values
    return values.clip(lower=clean.quantile(lower), upper=clean.quantile(upper))


def _last_percentile(series, higher_is_better=True, min_count=60):
    """当前值在自身历史中的百分位；所有输出统一为越高越好。"""
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    values = values.dropna()
    if len(values) < min_count:
        return np.nan
    current = float(values.iloc[-1])
    percentile = float((values <= current).mean() * 100.0)
    return percentile if higher_is_better else 100.0 - percentile




def _update_liquidity_snapshot(asof, event):
    """V4.0.1唯一入口：计算快照、更新慢周期与行动政策并输出JSON。"""
    snapshot = evaluate_market_liquidity(asof)
    _liquidity_attach_macro(snapshot)
    _liquidity_attach_confidence(snapshot)
    _liquidity_apply_policy(snapshot)
    snapshot["event"] = event
    snapshot["model_version"] = "V4.0.1_BUFFETT_POLICY"
    g.liquidity_last_snapshot = dict(snapshot)
    _emit_liquidity_log(snapshot)
    return snapshot


def evaluate_market_liquidity(asof):
    """完整V4快照：纯流动性、市场确认、结构、动量和独立硬风险。"""
    codes = []
    for index_code in g.liquidity_index_codes:
        try:
            codes.extend(get_index_stocks(index_code, date=asof))
        except Exception as exc:
            log.warning("流动性样本读取失败 %s：%s" % (index_code, exc))
    codes = sorted(set(str(code) for code in codes))
    frames = _load_price_frames(codes, asof, count=g.liquidity_daily_count)
    market = _liquidity_market_series(frames)
    financing = _liquidity_financing_series(asof)
    scores = _liquidity_score_frame(market, financing)
    if scores.empty:
        return _empty_liquidity_snapshot(asof, len(frames))

    pure = _liquidity_weighted_series(
        scores, g.liquidity_pure_weights, minimum_valid=2
    )
    scores["pure_liquidity"] = pure
    scores.dropna(subset=["pure_liquidity"], inplace=True)
    if scores.empty:
        return _empty_liquidity_snapshot(asof, len(frames))

    components = {
        name: _liq_last(scores[name])
        for name in ("activity", "amihud", "breadth", "financing")
    }
    pure_score = _liq_last(scores["pure_liquidity"])
    price = _liquidity_price_context(asof)
    confirmation_values = {"breadth": components["breadth"]}
    confirmation_weights = {"breadth": 0.60}
    if price.get("above_ma20") is not None:
        confirmation_values["ma20"] = 100.0 if price["above_ma20"] else 0.0
        confirmation_weights["ma20"] = 0.20
    if price.get("above_ma60") is not None:
        confirmation_values["ma60"] = 100.0 if price["above_ma60"] else 0.0
        confirmation_weights["ma60"] = 0.20
    confirmation = _liquidity_weighted_values(
        confirmation_values, confirmation_weights
    )
    environment = _liquidity_weighted_values(
        {"pure": pure_score, "confirmation": confirmation},
        g.liquidity_environment_weights,
    )
    momentum = {
        "score_change_1w": _liq_series_change(scores["pure_liquidity"], 5),
        "score_change_4w": _liq_series_change(scores["pure_liquidity"], 20),
        "score_change_12w": _liq_series_change(scores["pure_liquidity"], 60),
    }
    for name in ("activity", "amihud", "breadth", "financing"):
        momentum[name + "_change_4w"] = _liq_series_change(scores[name], 20)
    detail = _liquidity_market_detail(market)
    structure = _liquidity_classify_structure(components, detail)
    agreement = _liquidity_component_agreement(components, momentum)
    momentum_state = _liquidity_momentum_state(momentum)
    phase = _liquidity_phase(pure_score, momentum_state, structure, agreement)
    outlook = _liquidity_outlook(phase, structure, agreement)
    benchmark_dd = _liquidity_benchmark_drawdown(asof)
    stress_flags = {
        "amihud_worst10": _liq_le(components["amihud"], 10.0),
        "breadth60_below20": _liq_le(detail.get("breadth60"), 0.20),
        "index_drawdown12": _liq_le(benchmark_dd, -0.12),
        "financing_worst10": _liq_le(components["financing"], 10.0),
    }
    snapshot = {
        "asof": str(asof),
        "sample_size": len(frames),
        "pure_liquidity_score": pure_score,
        "pure_liquidity_band": _liquidity_level(pure_score),
        "market_confirmation_score": confirmation,
        "market_confirmation_band": _liquidity_level(confirmation),
        "environment_score": environment,
        "environment_band": _liquidity_level(environment),
        "components": components,
        "market_detail": detail,
        "price_context": price,
        "index_20d_drawdown": benchmark_dd,
        "momentum": momentum,
        "momentum_state": momentum_state,
        "structure": structure,
        "agreement": agreement,
        "phase": phase,
        "outlook": outlook,
        "stress_flags": stress_flags,
        "data_quality": {
            "pure_component_count": int(sum(np.isfinite(components[x]) for x in g.liquidity_pure_weights)),
            "score_history_days": int(len(scores)),
            "asof_only": True,
            "future_data_used": False,
        },
    }
    return snapshot


def _liquidity_market_series(frames):
    rows = []
    for frame in frames.values():
        if frame is None or frame.empty:
            continue
        work = frame.copy()
        work["time"] = pd.to_datetime(work["time"], errors="coerce")
        for column in ("close", "money", "paused"):
            work[column] = pd.to_numeric(work[column], errors="coerce")
        work.sort_values("time", inplace=True)
        work["ret"] = work["close"].pct_change()
        work["ma20"] = work["close"].rolling(20).mean()
        work["ma60"] = work["close"].rolling(60).mean()
        valid = (
            work["time"].notna() & work["close"].gt(0)
            & work["money"].gt(0) & work["paused"].fillna(0).eq(0)
        )
        work = work.loc[valid].copy()
        if work.empty:
            continue
        work["date"] = work["time"].dt.normalize()
        work["illiq"] = work["ret"].abs() / work["money"]
        work["above20"] = np.where(work["ma20"].notna(), work["close"] > work["ma20"], np.nan)
        work["above60"] = np.where(work["ma60"].notna(), work["close"] > work["ma60"], np.nan)
        work["up_money"] = np.where(work["ret"] > 0, work["money"], 0.0)
        rows.append(work[["date", "money", "illiq", "above20", "above60", "up_money"]])
    if not rows:
        return pd.DataFrame()
    panel = pd.concat(rows, ignore_index=True)
    grouped = panel.groupby("date")
    total_money = grouped["money"].sum().sort_index()
    result = pd.DataFrame(index=total_money.index)
    result["activity_raw"] = total_money.rolling(20).mean()
    result["amihud_raw"] = grouped["illiq"].median().sort_index().rolling(20).mean()
    result["breadth20"] = grouped["above20"].mean().sort_index().rolling(5).mean()
    result["breadth60"] = grouped["above60"].mean().sort_index().rolling(5).mean()
    result["up_money_ratio"] = (
        grouped["up_money"].sum().sort_index() / total_money.replace(0, np.nan)
    ).rolling(5).mean()
    result["breadth_raw"] = result[["breadth20", "breadth60", "up_money_ratio"]].mean(axis=1)
    return result


def _liquidity_financing_series(asof):
    try:
        start = (pd.Timestamp(asof) - pd.Timedelta(days=620)).date()
        q = query(
            finance.STK_MT_TOTAL.date,
            finance.STK_MT_TOTAL.fin_value,
            finance.STK_MT_TOTAL.fin_buy_value,
        ).filter(finance.STK_MT_TOTAL.date >= start, finance.STK_MT_TOTAL.date <= asof)
        frame = finance.run_query(q)
    except Exception as exc:
        log.warning("融资数据读取失败：%s" % exc)
        return pd.DataFrame()
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["fin_value"] = pd.to_numeric(work["fin_value"], errors="coerce")
    work["fin_buy_value"] = pd.to_numeric(work["fin_buy_value"], errors="coerce")
    daily = work.dropna(subset=["date"]).groupby("date")[["fin_value", "fin_buy_value"]].sum().sort_index()
    result = pd.DataFrame(index=daily.index)
    result["balance_20d_change"] = daily["fin_value"].rolling(5).mean().pct_change(20)
    result["buy_impulse"] = daily["fin_buy_value"].rolling(5).mean() / daily["fin_buy_value"].rolling(60).mean() - 1.0
    return result


def _liquidity_score_frame(market, financing):
    if market is None or market.empty:
        return pd.DataFrame()
    result = pd.DataFrame(index=market.index)
    result["activity"] = _liquidity_rolling_percentile(market["activity_raw"], True)
    result["amihud"] = _liquidity_rolling_percentile(market["amihud_raw"], False)
    result["breadth"] = _liquidity_rolling_percentile(market["breadth_raw"], True)
    if financing is None or financing.empty:
        result["financing"] = np.nan
    else:
        balance = _liquidity_rolling_percentile(financing["balance_20d_change"], True)
        impulse = _liquidity_rolling_percentile(financing["buy_impulse"], True)
        result["financing"] = pd.concat([balance, impulse], axis=1).mean(axis=1).reindex(result.index, method="ffill")
    return result


def _liquidity_rolling_percentile(series, higher_is_better):
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    def rank_last(window):
        clean = window[np.isfinite(window)]
        if len(clean) < g.liquidity_percentile_min:
            return np.nan
        return float(np.mean(clean <= clean[-1]) * 100.0)
    score = values.rolling(
        g.liquidity_percentile_window, min_periods=g.liquidity_percentile_min
    ).apply(rank_last, raw=True)
    return score if higher_is_better else 100.0 - score


def _liquidity_weighted_series(frame, weights, minimum_valid):
    numer = pd.Series(0.0, index=frame.index)
    denom = pd.Series(0.0, index=frame.index)
    count = pd.Series(0, index=frame.index)
    for name, weight in weights.items():
        values = pd.to_numeric(frame[name], errors="coerce")
        valid = values.notna()
        numer += values.fillna(0) * weight
        denom += valid.astype(float) * weight
        count += valid.astype(int)
    return (numer / denom.replace(0, np.nan)).where(count >= minimum_valid)


def _liquidity_weighted_values(values, weights):
    valid = []
    for key, weight in weights.items():
        value = values.get(key, np.nan)
        try:
            if np.isfinite(value):
                valid.append((float(value), weight))
        except Exception:
            pass
    return sum(v * w for v, w in valid) / sum(w for _, w in valid) if valid else np.nan


def _liquidity_market_detail(market):
    if market is None or market.empty:
        return {"breadth20": np.nan, "breadth60": np.nan, "up_money_ratio": np.nan}
    return {
        "breadth20": _liq_last(market["breadth20"]),
        "breadth60": _liq_last(market["breadth60"]),
        "up_money_ratio": _liq_last(market["up_money_ratio"]),
    }


def _liquidity_price_context(asof):
    frame = _load_price_frames([g.liquidity_price_index], asof, count=100).get(g.liquidity_price_index)
    empty = {"close": np.nan, "return_4w": np.nan, "return_12w": np.nan, "drawdown_60d": np.nan, "above_ma20": None, "above_ma60": None}
    if frame is None or frame.empty:
        return empty
    close = pd.to_numeric(frame["close"], errors="coerce").dropna()
    if len(close) < 61:
        return empty
    current = float(close.iloc[-1])
    return {
        "close": current,
        "return_4w": float(current / close.iloc[-21] - 1.0),
        "return_12w": float(current / close.iloc[-61] - 1.0),
        "drawdown_60d": float(current / close.tail(60).max() - 1.0),
        "above_ma20": bool(current > close.tail(20).mean()),
        "above_ma60": bool(current > close.tail(60).mean()),
    }


def _liquidity_benchmark_drawdown(asof):
    frame = _load_price_frames([g.benchmark], asof, count=30).get(g.benchmark)
    if frame is None or frame.empty:
        return np.nan
    close = pd.to_numeric(frame["close"], errors="coerce").dropna().tail(20)
    return float(close.iloc[-1] / close.max() - 1.0) if len(close) >= 20 else np.nan


def _liquidity_classify_structure(c, detail):
    activity, amihud = c.get("activity", np.nan), c.get("amihud", np.nan)
    breadth, financing = c.get("breadth", np.nan), c.get("financing", np.nan)
    breadth60 = detail.get("breadth60", np.nan)
    if _liq_ge(activity, 70) and _liq_le(breadth, 35):
        return "panic_or_concentrated_volume"
    if _liq_ge(activity, 65) and _liq_ge(amihud, 55) and _liq_ge(breadth, 60):
        return "healthy_broad_expansion"
    if _liq_ge(breadth, 60) and _liq_le(activity, 45):
        return "broad_repair_low_volume"
    if _liq_le(breadth, 35) and _liq_le(amihud, 35) and _liq_le(breadth60, 0.35):
        return "broad_stress"
    if _liq_ge(breadth, 60) and _liq_le(financing, 35):
        return "unlevered_broadening"
    if _liq_ge(financing, 75) and _liq_le(breadth, 50):
        return "leveraged_narrow_market"
    return "mixed"


def _liquidity_component_agreement(c, momentum):
    valid = [v for v in c.values() if np.isfinite(v)]
    pure = [c[x] for x in ("activity", "amihud", "financing") if np.isfinite(c.get(x, np.nan))]
    improving = sum(_liq_ge(momentum.get(x + "_change_4w"), 3) for x in ("activity", "amihud", "financing"))
    deteriorating = sum(_liq_le(momentum.get(x + "_change_4w"), -3) for x in ("activity", "amihud", "financing"))
    return {
        "pure_high_component_count": int(sum(v >= 60 for v in pure)),
        "pure_low_component_count": int(sum(v <= 40 for v in pure)),
        "pure_improving_component_count": int(improving),
        "pure_deteriorating_component_count": int(deteriorating),
        "level_confidence": float(max(sum(v >= 60 for v in valid), sum(v <= 40 for v in valid)) / max(1, len(valid))),
        "direction_confidence": float(max(improving, deteriorating) / max(1, len(pure))),
    }


def _liquidity_momentum_state(momentum):
    def direction(value, threshold):
        return "up" if _liq_ge(value, threshold) else ("down" if _liq_le(value, -threshold) else "flat")
    short = direction(momentum.get("score_change_1w"), 4.0)
    medium = direction(momentum.get("score_change_4w"), 5.0)
    long_term = direction(momentum.get("score_change_12w"), 6.0)
    if short == "up" and medium == "down": return "short_rebound_in_medium_weakness"
    if short == "down" and medium == "up": return "short_pullback_in_medium_improvement"
    if medium == "up" and long_term == "down": return "medium_repair_in_long_weakness"
    if medium == "down" and long_term == "up": return "medium_slowdown_in_long_strength"
    if short == "up" and medium == "up": return "sustained_improving"
    if short == "down" and medium == "down": return "sustained_deteriorating"
    if short == medium == long_term == "flat": return "stable"
    return "mixed_momentum"


def _liquidity_phase(score, momentum, structure, agreement):
    improving = momentum in ("sustained_improving", "short_pullback_in_medium_improvement", "medium_repair_in_long_weakness")
    deteriorating = momentum in ("sustained_deteriorating", "short_rebound_in_medium_weakness", "medium_slowdown_in_long_strength")
    if score >= 75 and improving and agreement["pure_high_component_count"] >= 2: return "strong_expansion"
    if score >= 65 and not deteriorating: return "expansion"
    if score >= 65 and deteriorating: return "high_level_slowdown"
    if score < 45 and improving: return "low_level_repair"
    if score < 30 and not improving and agreement["pure_low_component_count"] >= 2: return "stress"
    if score < 45 and deteriorating: return "contraction"
    if deteriorating: return "weakening"
    if structure == "broad_stress": return "contraction"
    return "balanced"


def _liquidity_outlook(phase, structure, agreement):
    if phase == "strong_expansion": return "liquidity_expansion_strengthening"
    if phase == "expansion": return "healthy_expansion_confirmed" if structure == "healthy_broad_expansion" else "expansion_with_internal_divergence"
    if phase == "high_level_slowdown": return "high_level_liquidity_slowdown"
    if phase == "low_level_repair": return "broad_low_level_repair" if agreement["pure_improving_component_count"] >= 2 else "unconfirmed_low_level_repair"
    if phase == "weakening": return "current_liquidity_weakening"
    if phase == "contraction": return "current_liquidity_pressure"
    if phase == "stress": return "liquidity_stress"
    return "liquidity_transition"


def _liquidity_attach_macro(snapshot):
    item = {
        "asof": snapshot.get("asof"), "level": snapshot.get("pure_liquidity_score", np.nan),
        "structure": snapshot.get("structure"),
        "activity": snapshot.get("components", {}).get("activity", np.nan),
        "amihud": snapshot.get("components", {}).get("amihud", np.nan),
        "breadth": snapshot.get("components", {}).get("breadth", np.nan),
    }
    history = list(g.liquidity_weekly_history)
    if np.isfinite(item["level"]):
        if history and history[-1].get("asof") == item["asof"]:
            history[-1] = item
        else:
            history.append(item)
    history = history[-80:]
    if len(history) < 13 or not np.isfinite(item["level"]):
        raw = "warming_up"
        metrics = {"level_13w": np.nan, "level_change_4w": np.nan, "level_change_12w": np.nan, "healthy_count_4w": 0, "risk_count_4w": 0}
    else:
        recent4 = history[-4:]
        metrics = {
            "level_13w": float(np.mean([x["level"] for x in history[-13:]])),
            "level_change_4w": float(history[-1]["level"] - history[-5]["level"]),
            "level_change_12w": float(history[-1]["level"] - history[-13]["level"]),
            "healthy_count_4w": int(sum(x["structure"] == "healthy_broad_expansion" for x in recent4)),
            "risk_count_4w": int(sum(x["structure"] in ("broad_stress", "panic_or_concentrated_volume", "leveraged_narrow_market") for x in recent4)),
            "breadth_change_4w": float(history[-1]["breadth"] - history[-5]["breadth"]),
            "amihud_change_4w": float(history[-1]["amihud"] - history[-5]["amihud"]),
        }
        level, change4, change12 = metrics["level_13w"], metrics["level_change_4w"], metrics["level_change_12w"]
        if level >= 60 and change12 >= 0 and metrics["healthy_count_4w"] >= 1:
            raw = "expansion_cycle"
        elif level >= 55 and (change4 <= -8 or metrics["risk_count_4w"] >= 2):
            raw = "high_level_slowdown_cycle"
        elif level < 50 and change4 >= 6 and metrics["breadth_change_4w"] > 0 and metrics["amihud_change_4w"] > 0:
            raw = "accumulation_cycle"
        elif level < 45 and change12 <= 0:
            raw = "contraction_cycle"
        else:
            raw = "transition_cycle"
    old = g.liquidity_macro_state
    if raw == "warming_up" or old == "warming_up":
        applied = raw
        g.liquidity_macro_state = raw
        g.liquidity_macro_state_age = g.liquidity_macro_state_age + 1 if raw == old else 1
    elif raw == old:
        applied = old
        g.liquidity_macro_candidate = None
        g.liquidity_macro_candidate_count = 0
        g.liquidity_macro_state_age += 1
    else:
        if g.liquidity_macro_candidate == raw:
            g.liquidity_macro_candidate_count += 1
        else:
            g.liquidity_macro_candidate, g.liquidity_macro_candidate_count = raw, 1
        if g.liquidity_macro_candidate_count >= g.liquidity_macro_confirm_weeks:
            g.liquidity_macro_state = raw
            g.liquidity_macro_candidate = None
            g.liquidity_macro_candidate_count = 0
            g.liquidity_macro_state_age = 1
        else:
            g.liquidity_macro_state_age += 1
        applied = g.liquidity_macro_state
    snapshot["macro_raw_state"] = raw
    snapshot["macro_state"] = applied
    snapshot["macro_state_age"] = g.liquidity_macro_state_age
    snapshot["macro_metrics"] = metrics
    snapshot["macro_regime_onset"] = bool(applied != old and applied not in ("warming_up", "data_insufficient"))
    g.liquidity_weekly_history = history


def _liquidity_attach_confidence(snapshot):
    quality = snapshot.get("data_quality", {})
    agreement = snapshot.get("agreement", {})
    data_confidence = 0.50 * min(1.0, quality.get("pure_component_count", 0) / 3.0) + 0.25 * min(1.0, snapshot.get("sample_size", 0) / 750.0) + 0.25 * min(1.0, quality.get("score_history_days", 0) / 252.0)
    structure = snapshot.get("structure")
    structure_confidence = 0.0 if structure == "data_insufficient" else (0.35 if structure == "mixed" else min(1.0, 0.60 + 0.40 * agreement.get("level_confidence", 0.0)))
    snapshot["confidence"] = {
        "data": float(data_confidence),
        "structure": float(structure_confidence),
        "direction": float(agreement.get("direction_confidence", 0.0)),
        "forecast_probability": None,
    }


def _liquidity_raw_policy(snapshot):
    hard_count = sum(bool(x) for x in snapshot.get("stress_flags", {}).values())
    if hard_count >= 2:
        return "defense", ["independent_hard_risk_%d" % hard_count]
    structure, outlook = snapshot.get("structure"), snapshot.get("outlook")
    macro, confirmation = snapshot.get("macro_state"), snapshot.get("market_confirmation_score", np.nan)
    if structure in ("broad_repair_low_volume", "leveraged_narrow_market", "broad_stress") or outlook in ("current_liquidity_weakening", "current_liquidity_pressure", "liquidity_stress"):
        return "freeze", [structure, outlook]
    if structure == "healthy_broad_expansion" or outlook == "healthy_expansion_confirmed" or (macro == "expansion_cycle" and _liq_ge(confirmation, 45.0)):
        return "deploy", [structure, macro]
    return "selective", [structure, outlook, macro]



def _liquidity_apply_policy(snapshot):
    raw, reasons = _liquidity_raw_policy(snapshot)
    old = g.liquidity_policy
    hard_count = sum(bool(x) for x in snapshot.get("stress_flags", {}).values())
    if raw in ("freeze", "defense") and not (raw == "defense" and hard_count >= 3):
        if g.liquidity_risk_candidate == raw:
            g.liquidity_risk_candidate_count += 1
        else:
            g.liquidity_risk_candidate, g.liquidity_risk_candidate_count = raw, 1
        applied = raw if g.liquidity_risk_candidate_count >= g.liquidity_risk_confirm_weeks else (old if old not in (None, "warming_up") else "selective")
    else:
        g.liquidity_risk_candidate = None
        g.liquidity_risk_candidate_count = 0
        applied = raw

    # E3/E4快速恶化通道只允许提前降级，不允许提前升级。
    if bool(getattr(g, "fast_deterioration_enabled", False)):
        fast_flags = _fast_deterioration_flags(snapshot)
        fast_count = int(sum(bool(value) for value in fast_flags.values()))
        if fast_count >= 3 and applied in ("deploy", "selective"):
            applied = "freeze"
            reasons = list(reasons) + ["fast_deterioration_%d" % fast_count]
        elif fast_count >= 2 and applied == "deploy":
            applied = "selective"
            reasons = list(reasons) + ["fast_deterioration_%d" % fast_count]
        snapshot["fast_deterioration_flags"] = fast_flags
        snapshot["fast_deterioration_count"] = fast_count

    if applied == old:
        g.liquidity_policy_age += 1
    else:
        g.liquidity_policy_age = 1
    g.liquidity_previous_policy = old
    g.liquidity_policy = applied
    _fz2_on_policy_transition(old, applied, snapshot)
    snapshot["action_policy_raw"] = raw
    snapshot["action_policy"] = applied
    snapshot["action_policy_age"] = g.liquidity_policy_age
    snapshot["action_policy_onset"] = bool(applied != old and applied not in ("warming_up", "data_insufficient"))
    snapshot["action_reasons"] = reasons
    snapshot["structure_onset"] = bool(snapshot.get("structure") != getattr(g, "liquidity_previous_structure", None))
    g.liquidity_previous_structure = snapshot.get("structure")
    snapshot["action_stress_flags"] = snapshot.get("stress_flags", {}) if applied == "defense" else {name: False for name in snapshot.get("stress_flags", {})}



def _emit_liquidity_log(snapshot):
    c, confidence = snapshot.get("components", {}), snapshot.get("confidence", {})
    log.info("流动性行动：日期=%s；政策=%s(第%d周)；纯流动性=%.1f；确认=%.1f；结构=%s；大周期=%s；硬风险=%d；数据/结构/方向置信度=%.2f/%.2f/%.2f。" % (
        snapshot.get("asof"), snapshot.get("action_policy"), snapshot.get("action_policy_age", 0),
        snapshot.get("pure_liquidity_score", np.nan), snapshot.get("market_confirmation_score", np.nan),
        snapshot.get("structure"), snapshot.get("macro_state"), sum(bool(x) for x in snapshot.get("stress_flags", {}).values()),
        confidence.get("data", 0.0), confidence.get("structure", 0.0), confidence.get("direction", 0.0),
    ))
    # 聚宽导出日志通常为GB18030；ASCII JSON可避免跨平台再次乱码。
    log.info("LIQ_RADAR|" + json.dumps(_liquidity_json_safe(snapshot), ensure_ascii=True, sort_keys=True))
    _record_leverage_market(snapshot)


def _empty_liquidity_snapshot(asof, sample_size):
    return {
        "asof": str(asof), "sample_size": sample_size,
        "pure_liquidity_score": np.nan, "market_confirmation_score": np.nan,
        "environment_score": np.nan, "components": {"activity": np.nan, "amihud": np.nan, "breadth": np.nan, "financing": np.nan},
        "structure": "data_insufficient", "phase": "data_insufficient", "outlook": "data_insufficient",
        "agreement": {"level_confidence": 0.0, "direction_confidence": 0.0},
        "stress_flags": {"amihud_worst10": False, "breadth60_below20": False, "index_drawdown12": False, "financing_worst10": False},
        "data_quality": {"pure_component_count": 0, "score_history_days": 0, "asof_only": True, "future_data_used": False},
    }


def _liquidity_level(value):
    if value is None or not np.isfinite(value): return "unknown"
    if value >= 75: return "very_high"
    if value >= 60: return "high"
    if value >= 45: return "middle"
    if value >= 30: return "low"
    return "very_low"


def _liq_last(series):
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(clean.iloc[-1]) if len(clean) else np.nan


def _liq_series_change(series, periods):
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(clean.iloc[-1] - clean.iloc[-periods - 1]) if len(clean) > periods else np.nan


def _liq_ge(value, threshold):
    return value is not None and np.isfinite(value) and value >= threshold


def _liq_le(value, threshold):
    return value is not None and np.isfinite(value) and value <= threshold


def _liq_record_value(value):
    try:
        return float(value) if np.isfinite(value) else 0.0
    except Exception:
        return 0.0


def _liquidity_json_safe(value):
    if isinstance(value, dict):
        return {str(k): _liquidity_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_liquidity_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (pd.Timestamp, date)):
        return str(value)
    return value


def _stock_name(stock):
    try:
        info = get_security_info(stock)
        name = getattr(info, "display_name", None) or getattr(info, "name", None)
        if name:
            return str(name)
    except Exception:
        pass
    return str(stock)


def _stock_label(stock):
    return "%s(%s)" % (_stock_name(stock), stock)


def _get_sw1_industry(code, asof):
    """读取申万一级行业；读取失败时按股票隔离，避免UNKNOWN共同占用行业上限。"""
    try:
        info = get_industry(code, date=asof)
        node = info.get(code, {}).get("sw_l1", {}) if isinstance(info, dict) else {}
        industry_code = node.get("industry_code")
        industry_name = node.get("industry_name")
        if industry_code or industry_name:
            return str(industry_code or industry_name), str(industry_name or industry_code)
    except Exception:
        pass
    return "UNKNOWN:%s" % code, "未知行业"


def _historical_universe(asof):
    securities = get_all_securities(types=["stock"], date=asof)
    if securities is None or securities.empty:
        return []
    result = []
    for code, row in securities.iterrows():
        text = str(code)
        if not (text.endswith(".XSHG") or text.endswith(".XSHE")):
            continue
        start_date = row.get("start_date", None)
        if start_date is not None and pd.notna(start_date):
            if (pd.Timestamp(asof) - pd.Timestamp(start_date)).days < g.min_listing_days:
                continue
        result.append(text)
    try:
        flags = get_extras(
            "is_st", result, start_date=asof, end_date=asof, df=True
        )
        if not isinstance(flags, pd.DataFrame) or flags.empty:
            raise ValueError("empty point-in-time is_st response")
        latest = flags.iloc[-1]
        missing = [code for code in result if code not in latest.index]
        if missing:
            g.price50_st_missing_fields = int(
                getattr(g, "price50_st_missing_fields", 0)
            ) + len(missing)
            log.warning(
                "PRICE50历史ST点时字段缺失%d只；逐证券fail-closed排除。"
                % len(missing)
            )
        result = [
            code for code in result
            if code in latest.index and not bool(latest.get(code, False))
        ]
    except Exception as exc:
        g.price50_st_query_failures = int(
            getattr(g, "price50_st_query_failures", 0)
        ) + 1
        if bool(getattr(g, "price50_st_fail_closed", True)):
            log.error("PRICE50历史ST过滤失败，按fail-closed禁止本月新买入：%s" % exc)
            return []
        log.warning("历史ST过滤读取失败，买入前仍会执行实时ST过滤：%s" % exc)
    return result


def load_fundamentals(asof, universe):
    if not universe:
        return pd.DataFrame()
    q = query(
        valuation.code,
        valuation.market_cap,
        valuation.pe_ratio,
        valuation.pb_ratio,
        income.net_profit,
        indicator.adjusted_profit,
        indicator.roe,
        indicator.roa,
        indicator.inc_revenue_year_on_year,
        indicator.inc_net_profit_year_on_year,
        balance.total_assets,
        balance.total_liability,
        cash_flow.net_operate_cash_flow,
    ).filter(
        valuation.code.in_(universe),
        valuation.market_cap > 0,
        valuation.pe_ratio > 0,
        valuation.pb_ratio > 0,
        balance.total_assets > 0,
    )
    try:
        frame = get_fundamentals(q, date=asof)
    except Exception as exc:
        log.error("历史基本面读取失败：%s" % exc)
        return pd.DataFrame()
    if frame is None or frame.empty:
        return pd.DataFrame()
    return score_fundamentals(frame)


def load_holding_health(asof, holdings):
    """读取已披露财报；同报告期同比，避免把Q1与年报直接比较。"""
    if not holdings:
        return {}
    fields = [
        income.net_profit,
        indicator.adjusted_profit,
        indicator.roe,
        indicator.roa,
        indicator.inc_revenue_year_on_year,
        indicator.inc_net_profit_year_on_year,
        balance.total_assets,
        balance.total_liability,
        cash_flow.net_operate_cash_flow,
    ]
    try:
        frame = get_history_fundamentals(
            holdings,
            fields=fields,
            watch_date=asof,
            count=9,
            interval="1q",
        )
    except Exception as exc:
        log.warning("持仓历史财务读取失败，本月不因基本面数据缺失卖出：%s" % exc)
        return {}
    if frame is None or frame.empty or "code" not in frame.columns:
        return {}

    work = frame.copy()
    work["code"] = work["code"].astype(str)
    for column in (
        "net_profit", "adjusted_profit", "roe", "roa",
        "inc_revenue_year_on_year", "inc_net_profit_year_on_year",
        "total_assets", "total_liability", "net_operate_cash_flow",
    ):
        work[column] = _safe_numeric(work, column)
    if "statDate" not in work.columns:
        work["statDate"] = np.arange(len(work)).astype(str)
    work["statDate"] = work["statDate"].astype(str)
    work["stat_stamp"] = pd.to_datetime(work["statDate"], errors="coerce")
    work["adjusted_profit"] = work["adjusted_profit"].fillna(work["net_profit"])
    work["debt_ratio"] = work["total_liability"] / work["total_assets"]
    work["ocf_assets"] = work["net_operate_cash_flow"] / work["total_assets"]
    work.replace([np.inf, -np.inf], np.nan, inplace=True)

    result = {}
    for code, group in work.groupby("code"):
        group = group.sort_values(["stat_stamp", "statDate"]).reset_index(drop=True)
        latest = group.iloc[-1]
        prior = None
        latest_stamp = latest.get("stat_stamp")
        if pd.notna(latest_stamp):
            prior_target = pd.Timestamp(latest_stamp) - pd.DateOffset(years=1)
            matched = group[
                (group["stat_stamp"].dt.year == prior_target.year)
                & (group["stat_stamp"].dt.month == prior_target.month)
                & (group["stat_stamp"].dt.day == prior_target.day)
            ]
            if not matched.empty:
                prior = matched.iloc[-1]
        # 少数旧数据的statDate格式不统一；只有恰好具备4期跨度时才做保守后备。
        if prior is None and len(group) >= 5:
            candidate = group.iloc[-5]
            candidate_stamp = candidate.get("stat_stamp")
            if pd.isna(latest_stamp) or pd.isna(candidate_stamp) or (
                330 <= (pd.Timestamp(latest_stamp) - pd.Timestamp(candidate_stamp)).days <= 400
            ):
                prior = candidate

        def prior_value(column):
            if prior is None:
                return np.nan
            value = prior.get(column, np.nan)
            return float(value) if np.isfinite(value) else np.nan

        signals = []
        latest_roe = float(latest["roe"]) if np.isfinite(latest["roe"]) else np.nan
        latest_roa = float(latest["roa"]) if np.isfinite(latest["roa"]) else np.nan
        prior_roe = prior_value("roe")
        prior_roa = prior_value("roa")
        prior_debt = prior_value("debt_ratio")

        if np.isfinite(latest_roe) and np.isfinite(prior_roe):
            if latest_roe < prior_roe * 0.60 and latest_roe < prior_roe - 3.0:
                signals.append("ROE显著下降")
        if np.isfinite(latest_roa) and np.isfinite(prior_roa):
            if latest_roa < prior_roa * 0.60 and latest_roa < prior_roa - 1.0:
                signals.append("ROA显著下降")
        revenue_growth = latest["inc_revenue_year_on_year"]
        profit_growth = latest["inc_net_profit_year_on_year"]
        if np.isfinite(revenue_growth) and revenue_growth < -15.0:
            signals.append("收入同比下降超过15%")
        if np.isfinite(profit_growth) and profit_growth < -30.0:
            signals.append("利润同比下降超过30%")
        latest_debt = latest["debt_ratio"]
        if np.isfinite(latest_debt) and np.isfinite(prior_debt):
            if latest_debt > prior_debt + 0.10 and latest_debt > 0.65:
                signals.append("负债率显著上升")
        latest_ocf_assets = latest.get("ocf_assets", np.nan)
        prior_ocf_assets = prior_value("ocf_assets")
        if np.isfinite(latest_ocf_assets) and np.isfinite(prior_ocf_assets):
            if latest_ocf_assets < -0.02 and latest_ocf_assets < prior_ocf_assets - 0.05:
                signals.append("同报告期经营现金流/资产显著恶化")

        net_profit = latest["net_profit"]
        adjusted_profit = latest["adjusted_profit"]
        loss_making = bool(
            (np.isfinite(net_profit) and net_profit <= 0)
            or (np.isfinite(adjusted_profit) and adjusted_profit <= 0)
        )
        result[str(code)] = {
            "report_date": str(latest["statDate"]),
            "comparison_report": str(prior["statDate"]) if prior is not None else None,
            "net_profit": float(net_profit) if np.isfinite(net_profit) else np.nan,
            "adjusted_profit": float(adjusted_profit) if np.isfinite(adjusted_profit) else np.nan,
            "roe": latest_roe,
            "roa": latest_roa,
            "debt_ratio": float(latest_debt) if np.isfinite(latest_debt) else np.nan,
            "ocf_assets": (
                float(latest_ocf_assets)
                if np.isfinite(latest_ocf_assets) else np.nan
            ),
            "revenue_growth": float(revenue_growth) if np.isfinite(revenue_growth) else np.nan,
            "profit_growth": float(profit_growth) if np.isfinite(profit_growth) else np.nan,
            "loss_making": loss_making,
            "deterioration_signals": signals,
            # 普通恶化需要同一份新报告中至少两个独立证据；亏损由上层单独硬退出。
            "deteriorated": len(signals) >= 2,
        }
    return result


def _health_baseline_snapshot(health):
    """保存买入时已经披露的原始质量快照，供以后新财报直接对照。"""
    mapping = {
        "entry_report_date": "report_date",
        "entry_roe": "roe",
        "entry_roa": "roa",
        "entry_debt_ratio": "debt_ratio",
        "entry_ocf_assets": "ocf_assets",
        "entry_revenue_growth": "revenue_growth",
        "entry_profit_growth": "profit_growth",
        "entry_net_profit": "net_profit",
        "entry_adjusted_profit": "adjusted_profit",
    }
    snapshot = {}
    for target, source in mapping.items():
        value = health.get(source)
        if source == "report_date":
            snapshot[target] = value
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = np.nan
        snapshot[target] = number if np.isfinite(number) else np.nan
    return snapshot


def _compare_new_report_to_entry(health, baseline):
    """返回相对买入质量基准的硬信号与软信号；只在新报告期调用。"""
    hard = []
    soft = []

    def number(mapping, key):
        try:
            value = float(mapping.get(key, np.nan))
        except (TypeError, ValueError):
            return np.nan
        return value if np.isfinite(value) else np.nan

    roe = number(health, "roe")
    entry_roe = number(baseline, "entry_roe")
    if np.isfinite(roe) and np.isfinite(entry_roe):
        if roe < 0 and entry_roe >= 5.0:
            hard.append("ROE由健康水平转负")
        elif roe < entry_roe * 0.60 and roe < entry_roe - 3.0:
            soft.append("ROE较买入基准显著下降")

    roa = number(health, "roa")
    entry_roa = number(baseline, "entry_roa")
    if np.isfinite(roa) and np.isfinite(entry_roa):
        if roa < 0 and entry_roa >= 2.0:
            hard.append("ROA由健康水平转负")
        elif roa < entry_roa * 0.60 and roa < entry_roa - 1.0:
            soft.append("ROA较买入基准显著下降")

    debt = number(health, "debt_ratio")
    entry_debt = number(baseline, "entry_debt_ratio")
    if np.isfinite(debt) and np.isfinite(entry_debt):
        if debt > entry_debt + 0.10 and debt > 0.65:
            soft.append("负债率较买入基准显著上升")

    ocf_assets = number(health, "ocf_assets")
    entry_ocf_assets = number(baseline, "entry_ocf_assets")
    if np.isfinite(ocf_assets) and np.isfinite(entry_ocf_assets):
        if ocf_assets < -0.05 and entry_ocf_assets > 0:
            hard.append("经营现金流/资产由正转为显著负值")
        elif ocf_assets < -0.02 and ocf_assets < entry_ocf_assets - 0.05:
            soft.append("经营现金流/资产较买入基准显著恶化")

    return list(dict.fromkeys(hard)), list(dict.fromkeys(soft))


def _fundamental_signal_dimension(signal):
    """把同比与买入基准的不同文案归并到同一独立财务维度。"""
    text = str(signal)
    mapping = (
        ("ROE", "roe"),
        ("ROA", "roa"),
        ("收入", "revenue"),
        ("利润", "profit"),
        ("负债率", "debt"),
        ("经营现金流", "ocf"),
    )
    for token, dimension in mapping:
        if token in text:
            return dimension
    return "other:" + text


def _merge_fundamental_soft_signals(yoy_signals, entry_soft_signals):
    """合并两套软信号，并按财务维度去重；一边一个不同维度也可共同确认恶化。"""
    merged = {}
    for source, signals in (("同比", yoy_signals), ("买入基准", entry_soft_signals)):
        for signal in signals or []:
            dimension = _fundamental_signal_dimension(signal)
            state = merged.setdefault(dimension, {"labels": [], "sources": []})
            if str(signal) not in state["labels"]:
                state["labels"].append(str(signal))
            if source not in state["sources"]:
                state["sources"].append(source)
    return merged


def _format_merged_fundamental_signals(merged):
    result = []
    for dimension, state in merged.items():
        labels = " / ".join(state.get("labels", []))
        sources = "+".join(state.get("sources", []))
        result.append("%s[%s]" % (labels or dimension, sources or "未知来源"))
    return result


def score_fundamentals(frame):
    """只做横截面打分，便于在聚宽外用合成数据验证。"""
    work = frame.copy()
    work["code"] = work["code"].astype(str)
    numeric = [
        "market_cap",
        "pe_ratio",
        "pb_ratio",
        "net_profit",
        "adjusted_profit",
        "roe",
        "roa",
        "inc_revenue_year_on_year",
        "inc_net_profit_year_on_year",
        "total_assets",
        "total_liability",
        "net_operate_cash_flow",
    ]
    for column in numeric:
        work[column] = _safe_numeric(work, column)

    # 聚宽扣非字段个别早期记录可能缺失；仅在缺失时回退净利润，绝不把负值改成正值。
    work["adjusted_profit"] = work["adjusted_profit"].fillna(work["net_profit"])

    work["debt_ratio"] = work["total_liability"] / work["total_assets"]
    work["ocf_assets"] = work["net_operate_cash_flow"] / work["total_assets"]
    work.replace([np.inf, -np.inf], np.nan, inplace=True)
    work.dropna(
        subset=["market_cap", "pe_ratio", "pb_ratio", "net_profit", "adjusted_profit", "roe", "roa", "debt_ratio"],
        inplace=True,
    )
    work = work[(work["net_profit"] > 0) & (work["adjusted_profit"] > 0)]
    if work.empty:
        return work

    for column in ("roe", "roa", "ocf_assets", "debt_ratio"):
        work[column] = _winsorize(work[column])
    for column in ("inc_revenue_year_on_year", "inc_net_profit_year_on_year"):
        median = work[column].median()
        work[column] = _winsorize(work[column].fillna(median if np.isfinite(median) else 0.0))

    work["profitability_score"] = (
        0.38 * _rank_high(work["roe"])
        + 0.22 * _rank_high(work["roa"])
        + 0.25 * _rank_high(work["ocf_assets"].fillna(work["ocf_assets"].median()))
        + 0.15 * _rank_low(work["debt_ratio"])
    )
    work["growth_score"] = (
        0.50 * _rank_high(work["inc_revenue_year_on_year"])
        + 0.50 * _rank_high(work["inc_net_profit_year_on_year"])
    )
    work["quality_score"] = (
        0.78 * work["profitability_score"] + 0.22 * work["growth_score"]
    )
    work["value_score"] = (
        0.55 * _rank_low(work["pe_ratio"]) + 0.45 * _rank_low(work["pb_ratio"])
    )
    work["size_score"] = _rank_high(work["market_cap"])
    work["fundamental_score"] = (
        0.58 * work["quality_score"]
        + 0.34 * work["value_score"]
        + 0.08 * work["size_score"]
    )
    work.sort_values("fundamental_score", ascending=False, inplace=True)
    return work.reset_index(drop=True)


def load_normalized_earnings(asof, codes, fundamentals):
    """读取决策日以前最近若干个已披露年度的扣非利润，构造常态利润准入指标。

    使用watch_date并开启avoid_future_data，避免用statDate直接查询尚未披露的年报。
    聚宽要求stat_by_year=True时interval必须为"1y"；这里按年取样，不能使用"1q"。
    查询失败时返回空表；新买入随后会采取fail-closed，已有持仓不会因此被卖出。
    """
    codes = list(dict.fromkeys(str(code) for code in codes if code))
    columns = [
        "code", "earnings_years", "positive_year_ratio",
        "normalized_profit", "normalized_pe", "profit_peak_ratio",
        "normalized_earnings_pass",
    ]
    if not codes or fundamentals is None or fundamentals.empty:
        return pd.DataFrame(columns=columns)

    market_caps = fundamentals.set_index("code")["market_cap"].to_dict()
    frames = []
    batch_size = max(1, int(g.normalized_earnings_batch_size))
    for start in range(0, len(codes), batch_size):
        batch = codes[start:start + batch_size]
        try:
            frame = get_history_fundamentals(
                batch,
                fields=[income.net_profit, indicator.adjusted_profit],
                watch_date=asof,
                count=g.normalized_earnings_years,
                interval="1y",
                stat_by_year=True,
            )
        except Exception as exc:
            log.warning(
                "常态利润历史读取失败（批次%d-%d），本月相关股票禁止新买：%s"
                % (start + 1, start + len(batch), exc)
            )
            continue
        if frame is not None and not frame.empty and "code" in frame.columns:
            frames.append(frame.copy())

    if not frames:
        return pd.DataFrame(columns=columns)

    work = pd.concat(frames, ignore_index=True, sort=False)
    work["code"] = work["code"].astype(str)
    work["net_profit"] = _safe_numeric(work, "net_profit")
    work["adjusted_profit"] = _safe_numeric(work, "adjusted_profit")
    work["adjusted_profit"] = work["adjusted_profit"].fillna(work["net_profit"])
    if "statDate" not in work.columns:
        work["statDate"] = np.arange(len(work)).astype(str)
    work["statDate"] = work["statDate"].astype(str)
    work.replace([np.inf, -np.inf], np.nan, inplace=True)

    rows = []
    for code, group in work.groupby("code"):
        group = (
            group.sort_values("statDate")
            .drop_duplicates(subset=["statDate"], keep="last")
            .tail(g.normalized_earnings_years)
        )
        profits = pd.to_numeric(group["adjusted_profit"], errors="coerce").dropna()
        if len(profits) == 0:
            continue
        profits = profits.astype(float)
        years = int(len(profits))
        positive_ratio = float((profits > 0).mean())
        positive = profits[profits > 0]
        normalized_profit = float(positive.median()) if len(positive) else np.nan

        previous = profits.iloc[:-1]
        previous_positive = previous[previous > 0]
        previous_median = (
            float(previous_positive.median()) if len(previous_positive) else np.nan
        )
        latest_profit = float(profits.iloc[-1])
        peak_ratio = (
            latest_profit / previous_median
            if np.isfinite(previous_median) and previous_median > 0
            else np.nan
        )
        market_cap = float(market_caps.get(code, np.nan))
        normalized_pe = (
            market_cap * 100000000.0 / normalized_profit
            if np.isfinite(market_cap) and market_cap > 0
            and np.isfinite(normalized_profit) and normalized_profit > 0
            else np.nan
        )
        passed = bool(
            years >= g.entry_min_earnings_years
            and positive_ratio >= g.entry_min_positive_year_ratio
            and np.isfinite(normalized_pe)
            and normalized_pe <= g.entry_max_normalized_pe
            and np.isfinite(peak_ratio)
            and peak_ratio <= g.entry_max_profit_peak_ratio
        )
        rows.append(
            {
                "code": str(code),
                "earnings_years": years,
                "positive_year_ratio": positive_ratio,
                "normalized_profit": normalized_profit,
                "normalized_pe": float(normalized_pe) if np.isfinite(normalized_pe) else np.nan,
                "profit_peak_ratio": float(peak_ratio) if np.isfinite(peak_ratio) else np.nan,
                "normalized_earnings_pass": passed,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _clean_price_frame(frame, code_hint=None):
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    work = frame.copy()
    if isinstance(work.index, pd.MultiIndex):
        work = work.reset_index()
    elif not isinstance(work.index, pd.RangeIndex):
        work = work.reset_index()
    # 聚宽部分版本的 panel=False 长表会同时带时间索引和 time 列。
    # reset_index 后可能同时出现 datetime/time；只能选择一个作为规范时间列，
    # 否则统一重命名会产生两个名为 time 的列，sort_values 会直接报错。
    columns = list(work.columns)
    lower_names = {column: str(column).lower() for column in columns}
    time_column = None
    for preferred in ("time", "datetime", "date", "index"):
        matches = [column for column in columns if lower_names[column] == preferred]
        if matches:
            time_column = matches[0]
            break

    rename = {}
    if time_column is not None and str(time_column) != "time":
        rename[time_column] = "time"
    for column in columns:
        name = lower_names[column]
        if column == time_column:
            continue
        if name in ("volume_money", "turnover", "amount"):
            rename[column] = "money"
        elif name in ("is_paused", "suspended"):
            rename[column] = "paused"
    work.rename(columns=rename, inplace=True)
    # 重命名后的成交额/停牌字段也可能与原字段重复，保留聚宽返回的最后一列。
    work = work.loc[:, ~work.columns.duplicated(keep="last")].copy()
    if "code" not in work.columns and code_hint is not None:
        work["code"] = str(code_hint)
    if "close" not in work.columns:
        return None
    if "money" not in work.columns:
        work["money"] = np.nan
    if "paused" not in work.columns:
        work["paused"] = 0
    if "time" not in work.columns:
        work["time"] = np.arange(len(work))
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    work["money"] = pd.to_numeric(work["money"], errors="coerce")
    work["paused"] = pd.to_numeric(work["paused"], errors="coerce").fillna(0)
    work = work.sort_values("time").drop_duplicates("time", keep="last")
    return work[["time", "code", "close", "money", "paused"]]


def _extract_price_frames(raw, codes):
    result = {}
    if raw is None:
        return result
    if isinstance(raw, pd.DataFrame):
        if "code" in raw.columns and "close" in raw.columns:
            for code, group in raw.groupby(raw["code"].astype(str)):
                cleaned = _clean_price_frame(group, code)
                if cleaned is not None:
                    result[str(code)] = cleaned
            return result
        if isinstance(raw.columns, pd.MultiIndex):
            for code in codes:
                pieces = {}
                for field in ("close", "money", "paused"):
                    for key in ((field, code), (code, field)):
                        if key in raw.columns:
                            pieces[field] = raw[key]
                            break
                if "close" in pieces:
                    cleaned = _clean_price_frame(pd.DataFrame(pieces), code)
                    if cleaned is not None:
                        result[str(code)] = cleaned
            return result
        if len(codes) == 1 and "close" in raw.columns:
            cleaned = _clean_price_frame(raw, codes[0])
            if cleaned is not None:
                result[str(codes[0])] = cleaned
    return result


def _load_price_frames(codes, asof, count=None):
    codes = [str(code) for code in codes]
    if not codes:
        return {}
    if count is None:
        count = g.lookback
    raw = None
    try:
        raw = get_price(
            codes,
            end_date=asof,
            count=count,
            frequency="daily",
            fields=["close", "money", "paused"],
            skip_paused=False,
            fq="pre",
            panel=False,
        )
    except TypeError:
        try:
            raw = get_price(
                codes,
                end_date=asof,
                count=count,
                frequency="daily",
                fields=["close", "money", "paused"],
                skip_paused=False,
                fq="pre",
            )
        except Exception as exc:
            log.warning("批量行情读取失败：%s" % exc)
    except Exception as exc:
        log.warning("批量行情读取失败：%s" % exc)
    frames = _extract_price_frames(raw, codes)
    if len(frames) < max(1, int(len(codes) * 0.80)):
        for code in codes:
            if code in frames:
                continue
            try:
                one = get_price(
                    code,
                    end_date=asof,
                    count=count,
                    frequency="daily",
                    fields=["close", "money", "paused"],
                    skip_paused=False,
                    fq="pre",
                )
                cleaned = _clean_price_frame(one, code)
                if cleaned is not None:
                    frames[code] = cleaned
            except Exception:
                pass
    return frames


def _load_point_in_time_raw_closes(codes, asof):
    """读取决策日可见的不复权收盘价；缺失证券不得通过PRICE50入场门。"""
    g.price50_raw_close_query_failures = 0
    codes = list(dict.fromkeys(str(code) for code in codes))
    if not codes:
        return {}
    result = {}
    for offset in range(0, len(codes), 200):
        batch = codes[offset:offset + 200]
        raw = None
        try:
            raw = get_price(
                batch,
                end_date=asof,
                count=1,
                frequency="daily",
                fields=["close", "money", "paused"],
                skip_paused=False,
                fq=None,
                panel=False,
            )
        except TypeError:
            try:
                raw = get_price(
                    batch,
                    end_date=asof,
                    count=1,
                    frequency="daily",
                    fields=["close", "money", "paused"],
                    skip_paused=False,
                    fq=None,
                )
            except Exception as exc:
                g.price50_raw_close_query_failures = int(
                    getattr(g, "price50_raw_close_query_failures", 0)
                ) + 1
                log.error("PRICE50不复权点时价格批次读取失败：%s" % exc)
                continue
        except Exception as exc:
            g.price50_raw_close_query_failures = int(
                getattr(g, "price50_raw_close_query_failures", 0)
            ) + 1
            log.error("PRICE50不复权点时价格批次读取失败：%s" % exc)
            continue
        frames = _extract_price_frames(raw, batch)
        for code, frame in frames.items():
            usable = frame.dropna(subset=["close"])
            if usable.empty:
                continue
            value = float(usable.iloc[-1]["close"])
            if np.isfinite(value) and value > 0:
                result[str(code)] = value
    return result


def _normalized_ema_angle(series, points):
    """用对数回归得到尺度无关的周涨速，再映射为可比较的角度。"""
    values = pd.to_numeric(series.tail(points), errors="coerce").dropna()
    if len(values) < points or (values <= 0).any():
        return np.nan, np.nan
    x = np.arange(len(values), dtype=float)
    log_slope = float(np.polyfit(x, np.log(values.values.astype(float)), 1)[0])
    weekly_rate = float(np.expm1(log_slope))
    angle = float(np.degrees(np.arctan(weekly_rate * 100.0)))
    return angle, weekly_rate


def filter_weekly_trend(codes, asof):
    """完整周线：核心新买入需通过快慢线或BOLL恢复分支。"""
    codes = [str(code) for code in codes]
    frames = _load_price_frames(codes, asof, count=g.weekly_daily_count)
    passed = []
    trend_map = {}
    for code in codes:
        frame = frames.get(code)
        if frame is None or frame.empty:
            continue
        daily = frame.dropna(subset=["close"]).copy()
        daily["time"] = pd.to_datetime(daily["time"], errors="coerce")
        daily.dropna(subset=["time"], inplace=True)
        if daily.empty:
            continue
        daily.sort_values("time", inplace=True)
        weekly_close = (
            daily.set_index("time")["close"]
            .resample("W-FRI")
            .last()
            .dropna()
        )
        # 月末可能位于周中；W-FRI会给残缺周标上未来周五，必须剔除。
        weekly_close = weekly_close[
            weekly_close.index.normalize() <= pd.Timestamp(asof).normalize()
        ]
        required = max(
            g.weekly_min_bars,
            g.trend_angle_points,
            g.trend_boll_period + g.trend_boll_angle_points - 1,
        )
        if len(weekly_close) < required:
            continue
        ema5 = weekly_close.ewm(span=g.trend_fast, adjust=False).mean()
        ema20 = weekly_close.ewm(span=g.trend_slow, adjust=False).mean()
        boll_mid = weekly_close.rolling(g.trend_boll_period).mean()
        current_ema5 = float(ema5.iloc[-1])
        current_ema20 = float(ema20.iloc[-1])
        ema5_angle, ema5_weekly_rate = _normalized_ema_angle(
            ema5, g.trend_angle_points
        )
        boll_mid_angle, boll_mid_weekly_rate = _normalized_ema_angle(
            boll_mid, g.trend_boll_angle_points
        )
        if not _py_builtins.all(
            np.isfinite(x)
            for x in (
                current_ema5,
                current_ema20,
                ema5_angle,
                ema5_weekly_rate,
                boll_mid_angle,
                boll_mid_weekly_rate,
            )
        ):
            continue
        fast_above_slow = current_ema5 > current_ema20
        fast_angle_pass = ema5_weekly_rate > 0 and ema5_angle > g.trend_min_angle
        boll_direction_pass = boll_mid_angle >= g.trend_boll_min_angle
        latest_close = float(weekly_close.iloc[-1])
        close_above_boll = latest_close >= float(boll_mid.iloc[-1])
        severe = (
            current_ema5 < current_ema20
            and boll_mid_angle < g.trend_boll_min_angle
            and latest_close < float(boll_mid.iloc[-1])
        )
        strict_pass = bool(
            fast_above_slow and fast_angle_pass
            and boll_direction_pass and close_above_boll
        )
        boll_recovery_pass = bool(
            boll_mid_angle >= g.core_recovery_boll_min_angle
            and close_above_boll
        )
        # V1.6.0只排除三条件同时恶化，导致快线陡降但BOLL尚未跌破-15度时
        # 仍可买入。V18E1研究版沿用过渡区：快线已经站上慢线，或BOLL中轨已
        # 转平向上且价格站回中轨。现有持仓不会因本条件失效被机械卖出。
        core_pass = bool(
            not severe and (fast_above_slow or boll_recovery_pass)
        )
        trend_map[code] = {
            "ema5w": current_ema5,
            "ema20w": current_ema20,
            "ema5_angle": ema5_angle,
            "ema5_weekly_rate": ema5_weekly_rate,
            "boll_mid": float(boll_mid.iloc[-1]),
            "boll_mid_angle": boll_mid_angle,
            "boll_mid_weekly_rate": boll_mid_weekly_rate,
            "fast_above_slow": bool(fast_above_slow),
            "fast_angle_pass": bool(fast_angle_pass),
            "boll_direction_pass": bool(boll_direction_pass),
            "close_above_boll": bool(close_above_boll),
            "boll_recovery_pass": boll_recovery_pass,
            "severe": bool(severe),
            "strict_pass": strict_pass,
            "core_pass": core_pass,
            # passed代表核心新买入是否允许。
            "passed": core_pass,
        }
        if core_pass:
            passed.append(code)
    return passed, trend_map


def _month_index(value):
    stamp = pd.Timestamp(value)
    return int(stamp.year * 12 + stamp.month)


def _report_version_is_newer(current_report, locked_report):
    """判断当前已披露报告是否严格晚于导致退出的报告版本。"""
    if not current_report or not locked_report:
        return False
    current_stamp = pd.to_datetime(str(current_report), errors="coerce")
    locked_stamp = pd.to_datetime(str(locked_report), errors="coerce")
    if pd.notna(current_stamp) and pd.notna(locked_stamp):
        return bool(current_stamp > locked_stamp)
    return str(current_report) != str(locked_report)


def _is_fundamental_report_locked(code, current_report, release_if_new=True):
    """同一份导致财报退出的报告不得重新触发买入；新报告披露后自动解锁。"""
    code = str(code)
    lock = g.fundamental_exit_report_locks.get(code)
    if not lock:
        return False
    locked_report = lock.get("report_date") if isinstance(lock, dict) else lock
    if _report_version_is_newer(current_report, locked_report):
        if release_if_new:
            g.fundamental_exit_report_locks.pop(code, None)
            log.info(
                "财报版本锁解除 %s：退出报告=%s，当前已披露新报告=%s。"
                % (_stock_label(code), locked_report, current_report)
            )
        return False
    return True


def _register_fundamental_exit_lock(context, code, report_date, reason):
    """成功创建财报退出卖单后，保存导致退出的报告版本。"""
    if not report_date:
        log.warning("财报退出未建立版本锁 %s：报告版本缺失。" % _stock_label(code))
        return
    code = str(code)
    g.fundamental_exit_report_locks[code] = {
        "report_date": str(report_date),
        "exit_date": str(context.current_dt.date()),
        "reason": str(reason),
    }
    log.info(
        "财报版本锁建立 %s：报告=%s；在新报告披露前禁止重新买入。"
        % (_stock_label(code), report_date)
    )


def _is_reentry_blocked(code, trade_date):
    blocked_through = g.reentry_cooldowns.get(str(code))
    if blocked_through is None:
        return False
    if _month_index(trade_date) <= int(blocked_through):
        return True
    g.reentry_cooldowns.pop(str(code), None)
    return False


def score_price_risk(codes, asof):
    frames = _load_price_frames(codes, asof)
    benchmark_frames = _load_price_frames([g.benchmark], asof)
    benchmark = benchmark_frames.get(g.benchmark)
    if benchmark is None:
        return pd.DataFrame()
    benchmark_returns = benchmark.set_index("time")["close"].pct_change().dropna()
    rows = []
    for code in codes:
        frame = frames.get(str(code))
        if frame is None or frame.empty:
            continue
        usable = frame.dropna(subset=["close"]).copy()
        if len(usable) < g.min_price_observations:
            continue
        if (usable.tail(20)["paused"] > 0).any():
            continue
        avg_money = usable["money"].tail(60).mean()
        if not np.isfinite(avg_money) or avg_money < g.min_avg_money:
            continue
        stock_returns = usable.set_index("time")["close"].pct_change().dropna()
        aligned = pd.concat(
            [stock_returns.rename("stock"), benchmark_returns.rename("market")],
            axis=1,
            join="inner",
        ).dropna()
        if len(aligned) < 120 or aligned["market"].var() <= 0:
            continue
        beta = aligned["stock"].cov(aligned["market"]) / aligned["market"].var()
        residual = aligned["stock"] - beta * aligned["market"]
        volatility = stock_returns.std() * np.sqrt(244.0)
        downside = stock_returns[stock_returns < 0].std() * np.sqrt(244.0)
        idio_vol = residual.std() * np.sqrt(244.0)
        close = usable["close"].astype(float)
        drawdown = (close / close.cummax() - 1.0).min()
        values = [beta, volatility, downside, idio_vol, drawdown, avg_money, close.iloc[-1]]
        if not _py_builtins.all(np.isfinite(value) for value in values):
            continue
        rows.append(
            {
                "code": str(code),
                "beta": float(beta),
                "volatility": float(volatility),
                "downside": float(downside),
                "idio_vol": float(idio_vol),
                "drawdown": float(drawdown),
                "avg_money": float(avg_money),
                "last_close": float(close.iloc[-1]),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["safety_score"] = (
        0.35 * _rank_low(result["beta"])
        + 0.25 * _rank_low(result["volatility"])
        + 0.18 * _rank_low(result["downside"])
        + 0.12 * _rank_low(result["idio_vol"])
        + 0.10 * _rank_high(result["drawdown"])
    )
    return result


def _build_industry_map(codes, asof):
    """批量读取决策日历史申万一级行业，失败的股票按UNKNOWN隔离。"""
    codes = [str(code) for code in codes]
    result = {}
    for start in range(0, len(codes), 500):
        batch = codes[start:start + 500]
        try:
            raw = get_industry(batch, date=asof)
        except Exception as exc:
            log.warning("历史行业批量读取失败[%d:%d]：%s" % (start, start + len(batch), exc))
            raw = {}
        for code in batch:
            node = raw.get(code, {}).get("sw_l1", {}) if isinstance(raw, dict) else {}
            key = node.get("industry_code")
            name = node.get("industry_name")
            if key or name:
                result[code] = (str(key or name), str(name or key))
            else:
                result[code] = ("UNKNOWN:%s" % code, "未知行业")
    return result


def _recent_quarter_ends(asof, count):
    """返回不晚于asof的自然季度末；是否可用只由pub_date<=asof决定。"""
    stamp = pd.Timestamp(asof).normalize()
    periods = []
    for year in range(stamp.year - 3, stamp.year + 1):
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            period = pd.Timestamp(year=year, month=month, day=day)
            if period <= stamp:
                periods.append(period)
    return sorted(set(periods), reverse=True)[:int(count)]


def _normalize_a_share_code(raw):
    """只接受沪深六位A股；港股、美股、期货和空值一律返回None。"""
    if raw is None or pd.isna(raw):
        return None
    text = str(raw).strip().upper()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    match = re.match(r"^(\d{6})\.(XSHG|XSHE)$", text)
    if match:
        return "%s.%s" % (match.group(1), match.group(2))
    match = re.match(r"^(\d{6})\.(SH|SS|SZ)$", text)
    if match:
        return "%s.%s" % (
            match.group(1), "XSHG" if match.group(2) in ("SH", "SS") else "XSHE"
        )
    match = re.match(r"^(SH|SZ)(\d{6})$", text)
    if match:
        return "%s.%s" % (
            match.group(2), "XSHG" if match.group(1) == "SH" else "XSHE"
        )
    if not re.match(r"^\d{6}$", text):
        return None
    if text[0] in ("5", "6", "9"):
        return text + ".XSHG"
    if text[0] in ("0", "1", "2", "3"):
        return text + ".XSHE"
    # 4/8开头主要为北交所/旧三板，不属于本策略沪深股票池。
    return None


def _table_schema_names(table):
    """尽量枚举JoinQuant ORM表字段；仅用于诊断和别名匹配。"""
    names = set()
    try:
        names.update(str(name) for name in dir(table) if not str(name).startswith("_"))
    except Exception:
        pass
    try:
        table_obj = getattr(table, "__table__", None)
        columns = getattr(table_obj, "columns", None)
        if columns is not None:
            for column in columns:
                for attr in ("name", "key"):
                    value = getattr(column, attr, None)
                    if value:
                        names.add(str(value))
    except Exception:
        pass
    return sorted(names)


def _schema_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _resolve_table_field(table, aliases):
    """按别名解析ORM字段；返回(field, 实际字段名)。"""
    for name in aliases:
        try:
            field = getattr(table, name)
        except Exception:
            field = None
        if field is not None:
            return field, str(name)
    available = _table_schema_names(table)
    normalized = {_schema_key(name): name for name in available}
    for alias in aliases:
        actual = normalized.get(_schema_key(alias))
        if not actual:
            continue
        try:
            field = getattr(table, actual)
        except Exception:
            field = None
        if field is not None:
            return field, str(actual)
    return None, None


def _canonicalize_query_columns(frame, field_map):
    if frame is None or frame.empty:
        return frame
    normalized = {_schema_key(name): name for name in frame.columns}
    rename = {}
    for canonical, actual in dict(field_map or {}).items():
        if canonical in frame.columns:
            continue
        if actual in frame.columns:
            rename[actual] = canonical
            continue
        hit = normalized.get(_schema_key(actual)) or normalized.get(_schema_key(canonical))
        if hit is not None:
            rename[hit] = canonical
    return frame.rename(columns=rename)


def _text_value_counts(series, limit=12):
    if series is None:
        return {}
    try:
        counts = series.fillna("").astype(str).str.strip().value_counts().head(int(limit))
        return {str(key): int(value) for key, value in counts.items() if str(key)}
    except Exception:
        return {}


def _active_fund_name_masks(names, styles=None):
    """字符串分类的保守规则：股票/混合类，排除指数、ETF、债基等被动或非A股产品。"""
    names = names.fillna("").astype(str)
    styles = (
        styles.fillna("").astype(str)
        if styles is not None else pd.Series("", index=names.index)
    )
    combined = names.str.cat(styles, sep="|")
    passive = combined.str.contains(
        r"ETF|指数|联接|增强指数|被动|QDII|债券|货币|FOF|商品|黄金|REIT|养老|目标日期|目标风险|海外|港股通指数",
        case=False,
        regex=True,
    )
    active_hint = combined.str.contains(
        r"股票|混合|偏股|灵活配置|价值|成长|精选|优选|优势|策略|主题|产业|行业|消费|医药|科技|制造|红利|蓝筹|量化",
        case=False,
        regex=True,
    )
    return active_hint & (~passive), passive


def _fetch_fund_main_frame():
    """加载 FUND_MAIN_INFO 原始帧并缓存（PIT-FIX F-1：只取数一次，分类按 asof 重算）。

    与原版相同的字段自适配与显式分页；新增 start_date/end_date 别名解析
    （F-4，审计日志证实该两列存在于表中）。
    """
    table = getattr(finance, "FUND_MAIN_INFO", None)
    if table is None:
        g.fund_main_info_meta = {"available": False, "reason": "table unavailable"}
        return None

    alias_map = {
        "main_code": ("main_code", "code", "fund_code", "statistics_main_code"),
        "name": ("name", "fund_name", "main_name", "short_name"),
        "underlying_asset_type": (
            "underlying_asset_type", "asset_type", "fund_asset_type",
            "underlying_asset_type_name",
        ),
        "underlying_asset_type_id": (
            "underlying_asset_type_id", "asset_type_id", "fund_asset_type_id",
        ),
        "operate_mode": ("operate_mode", "operation_mode", "fund_operate_mode"),
        "operate_mode_id": ("operate_mode_id", "operation_mode_id", "mode_id"),
        "invest_style": ("invest_style", "investment_style", "style_name"),
        "invest_style_id": ("invest_style_id", "investment_style_id", "style_id"),
        # PIT-FIX F-4：成立/终止日期（审计日志 available_fields 证实存在）。
        "start_date": ("start_date", "establish_date", "setup_date", "inception_date"),
        "end_date": ("end_date", "liquidation_date", "terminate_date", "maturity_date"),
    }
    fields, field_map = [], {}
    resolved = {}
    for canonical, aliases in alias_map.items():
        field, actual = _resolve_table_field(table, aliases)
        if field is not None:
            resolved[canonical] = field
            field_map[canonical] = actual
            fields.append(field)
    available_fields = _table_schema_names(table)
    g.fund_main_field_map = dict(field_map)
    if "main_code" not in resolved or "name" not in resolved:
        g.fund_main_info_meta = {
            "available": False,
            "reason": "code or name field unavailable",
            "field_map": dict(field_map),
            "available_fields": available_fields[:120],
        }
        log.warning("基金主体字段适配失败：%s" % g.fund_main_info_meta)
        log.info("V171_FUND_SCHEMA|%s" % json.dumps(
            {"table": "FUND_MAIN_INFO", **g.fund_main_info_meta},
            ensure_ascii=False, sort_keys=True, default=str,
        ))
        return None

    # 防止同一实际字段因多个别名重复进入query。
    unique_fields, seen_actual = [], set()
    for canonical, field in resolved.items():
        actual = field_map[canonical]
        if actual in seen_actual:
            continue
        seen_actual.add(actual)
        unique_fields.append(field)

    pieces, offset, last_rows, error = [], 0, 0, None
    while offset < int(g.fund_max_main_info_rows):
        q = query(*unique_fields)
        try:
            q = q.order_by(resolved["main_code"].asc())
        except Exception:
            pass
        try:
            part = finance.run_query(
                q.limit(int(g.fund_page_size)).offset(int(offset))
            )
        except Exception as exc:
            error = str(exc)
            break
        if part is None or part.empty:
            last_rows = 0
            break
        part = _canonicalize_query_columns(part, field_map)
        pieces.append(part)
        last_rows = int(len(part))
        offset += last_rows
        if last_rows < int(g.fund_page_size):
            break
    frame = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    hit_cap = bool(
        offset >= int(g.fund_max_main_info_rows)
        and last_rows >= int(g.fund_page_size)
    )
    if frame.empty or "main_code" not in frame.columns or hit_cap:
        g.fund_main_info_meta = {
            "available": False, "reason": error or "empty or hit cap",
            "rows": int(len(frame)), "hit_cap": hit_cap,
            "field_map": dict(field_map), "result_columns": list(frame.columns),
            "available_fields": available_fields[:120],
        }
        log.warning("基金主体表不可完整使用：%s" % g.fund_main_info_meta)
        log.info("V171_FUND_SCHEMA|%s" % json.dumps(
            {"table": "FUND_MAIN_INFO", **g.fund_main_info_meta},
            ensure_ascii=False, sort_keys=True, default=str,
        ))
        return None

    frame["main_code"] = frame["main_code"].astype(str).str.strip()
    for date_col in ("start_date", "end_date"):
        if date_col in frame.columns:
            frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    g.fund_main_frame_meta = {
        "available": True,
        "rows": int(len(frame)),
        "hit_cap": False,
        "field_map": dict(field_map),
        "result_columns": list(frame.columns),
        "available_fields": available_fields[:120],
        "has_start_date": bool("start_date" in frame.columns),
        "has_end_date": bool("end_date" in frame.columns),
        "start_date_nulls": (
            int(frame["start_date"].isna().sum())
            if "start_date" in frame.columns else None
        ),
        "end_date_nulls": (
            int(frame["end_date"].isna().sum())
            if "end_date" in frame.columns else None
        ),
        "asset_type_values": _text_value_counts(frame.get("underlying_asset_type")),
        "operate_mode_values": _text_value_counts(frame.get("operate_mode")),
        "invest_style_values": _text_value_counts(frame.get("invest_style")),
    }
    log.info("机构基金主体表：%s" % g.fund_main_frame_meta)
    log.info("V171_FUND_SCHEMA|%s" % json.dumps(
        {"table": "FUND_MAIN_INFO", **g.fund_main_frame_meta},
        ensure_ascii=False, sort_keys=True, default=str,
    ))
    return frame


def _classify_fund_main_frame(work):
    """原版分类逻辑原样保留（当前快照口径，审计 F-3 残留）。

    仅用于 g.pit_fix_holdings_derived_active=False 的回退路径与诊断对比。
    """
    names = work.get("name", pd.Series("", index=work.index)).fillna("").astype(str)
    styles = work.get("invest_style", pd.Series("", index=work.index)).fillna("").astype(str)
    name_active, passive = _active_fund_name_masks(names, styles)

    classification_mode = None
    asset_text = work.get("underlying_asset_type")
    if asset_text is not None:
        asset_text = asset_text.fillna("").astype(str).str.strip()
        equity_asset = asset_text.str.contains(r"股票|混合", case=False, regex=True)
        active_mask = equity_asset & (~passive)
        classification_mode = "string_asset_type"
    elif "underlying_asset_type_id" in work.columns:
        asset_type = pd.to_numeric(work["underlying_asset_type_id"], errors="coerce")
        active_mask = asset_type.isin([402001, 402004]) & (~passive)
        classification_mode = "numeric_asset_type_id"
    else:
        # 最后才使用名称/投资风格的保守分类；后续1000只有效基金和覆盖度门槛仍会fail-closed。
        active_mask = name_active
        classification_mode = "conservative_name_style_fallback"

    # 若平台字符串命名变化导致资产类型完全无命中，使用保守名称/风格回退，不能直接全量放行。
    if int(active_mask.sum()) == 0 and int(name_active.sum()) > 0:
        active_mask = name_active
        classification_mode += "+name_style_zero_hit_fallback"
    return active_mask, passive, classification_mode


def _load_fund_main_codes(asof):
    """PIT-FIX 版基金主体读取：原始帧缓存一次，随后每个 asof 在内存做点时过滤。

    修复（审计报告确定项）：
      F-1  原版无 asof 参数且分类结果全局永久缓存（12.6年回测只加载1次）；
           现改为原始帧缓存 + 每 asof 重算。
      F-2  start_date <= asof：剔除回测时点尚未成立的基金
           （原版在2014-01-02的回测时点读到102只2021年才有的基础设施REITs）。
      F-4  end_date 为空或 >= asof：剔除回测时点已清算的基金
           （原版表中存在 start_date/end_date 但完全未使用）。
    残留（审计 F-3）：分类字段仍是平台当前值。当
      g.pit_fix_holdings_derived_active=True（默认）时，本函数返回的
      active_codes 只用于诊断对比，实际准入由 _clean_one_fund_quarter
      按当季已披露持仓推导，不再依赖此处分类。
    """
    asof_ts = pd.Timestamp(asof)
    frame = getattr(g, "fund_main_frame_cache", None)
    if frame is None:
        frame = _fetch_fund_main_frame()
        g.fund_main_frame_cache = frame
    if frame is None or frame.empty:
        g.active_fund_codes_cache, g.all_fund_codes_cache = set(), set()
        return set(), set()

    work = frame
    alive_excluded = 0
    if bool(getattr(g, "pit_fix_date_filter", True)):
        alive_mask = pd.Series(True, index=work.index)
        if "start_date" in work.columns:
            alive_mask &= (work["start_date"].isna() | (work["start_date"] <= asof_ts))
        if "end_date" in work.columns:
            alive_mask &= (work["end_date"].isna() | (work["end_date"] >= asof_ts))
        alive_excluded = int((~alive_mask).sum())
        work = work[alive_mask]

    active_mask, passive, classification_mode = _classify_fund_main_frame(work)
    valid_code = work["main_code"].str.match(r"^\d{6}$", na=False)
    g.all_fund_codes_cache = set(work.loc[valid_code, "main_code"].dropna())
    g.active_fund_codes_cache = set(work.loc[valid_code & active_mask, "main_code"].dropna())
    g.fund_main_info_meta = {
        "available": bool(g.active_fund_codes_cache),
        "reason": "ok" if g.active_fund_codes_cache else "no active fund codes after classification",
        "asof": str(asof_ts.date()),
        "rows_total": int(len(frame)),
        "rows_alive": int(len(work)),
        "alive_excluded_by_date": alive_excluded,
        "all_codes": int(len(g.all_fund_codes_cache)),
        "active_codes": int(len(g.active_fund_codes_cache)),
        "classification_mode": classification_mode,
        "classification_scope": (
            "diagnostic_only_F3_residual"
            if bool(getattr(g, "pit_fix_holdings_derived_active", False))
            else "admission_filter"
        ),
        "pit_fix_version": str(getattr(g, "pit_fix_version", "")),
    }
    if bool(getattr(g, "pit_fix_diagnostics", True)):
        log.info("PIT_FIX_FUND_MAIN|%s" % json.dumps(
            g.fund_main_info_meta, ensure_ascii=False, sort_keys=True, default=str))
    return g.active_fund_codes_cache, g.all_fund_codes_cache


def _resolve_fund_holding_schema(table):
    alias_map = {
        "code": ("code", "fund_code", "main_code"),
        "name": ("name", "stock_name", "security_name"),
        "period_end": ("period_end", "report_date", "end_date", "period"),
        "pub_date": ("pub_date", "publish_date", "announcement_date", "ann_date"),
        "symbol": ("symbol", "stock_code", "security_code", "underlying_code"),
        "proportion": ("proportion", "ratio", "weight", "hold_ratio", "percentage"),
        "rank": ("rank", "stock_rank", "holding_rank"),
        "market_value": ("market_value", "market_cap", "holding_value", "position_value"),
    }
    cached = getattr(g, "fund_holding_schema_cache", None)
    if isinstance(cached, dict) and "resolved" not in cached:
        if not bool(cached.get("available", False)):
            runtime = dict(cached)
            runtime["resolved"] = {}
            return runtime
        cached_map = {
            str(canonical): str(actual)
            for canonical, actual in dict(cached.get("field_map", {})).items()
        }
        cached_resolved = {}
        for canonical, actual in cached_map.items():
            try:
                field = getattr(table, actual)
            except Exception:
                field = None
            if field is not None:
                cached_resolved[canonical] = field
        required = ("code", "period_end", "pub_date", "symbol", "proportion")
        if _py_builtins.all(name in cached_resolved for name in required):
            runtime = dict(cached)
            runtime["resolved"] = cached_resolved
            return runtime

    resolved, field_map = {}, {}
    for canonical, aliases in alias_map.items():
        field, actual = _resolve_table_field(table, aliases)
        if field is not None:
            resolved[canonical] = field
            field_map[canonical] = actual
    required = ("code", "period_end", "pub_date", "symbol", "proportion")
    missing = [name for name in required if name not in resolved]
    serializable_schema = {
        "available": not missing,
        "missing": list(missing),
        "field_map": {
            str(canonical): str(actual)
            for canonical, actual in field_map.items()
        },
        "available_fields": [
            str(name) for name in _table_schema_names(table)[:120]
        ],
    }
    g.fund_holding_field_map = dict(serializable_schema["field_map"])
    # JoinQuant ORM字段对象只在本次函数调用内存在；g中仅保留字符串描述。
    g.fund_holding_schema_cache = dict(serializable_schema)
    log.info("V171_FUND_SCHEMA|%s" % json.dumps(
        {
            "table": "FUND_PORTFOLIO_STOCK",
            "available": serializable_schema["available"],
            "missing": missing,
            "field_map": serializable_schema["field_map"],
            "available_fields": serializable_schema["available_fields"],
        },
        ensure_ascii=False, sort_keys=True, default=str,
    ))
    runtime_schema = dict(serializable_schema)
    runtime_schema["resolved"] = resolved
    return runtime_schema


def _load_one_fund_quarter(table, period, asof):
    """单季度显式分页，并把平台实际字段统一重命名为策略内部字段。"""
    schema = _resolve_fund_holding_schema(table)
    if not schema.get("available", False):
        return pd.DataFrame(), {
            "pages": 0, "raw_rows": 0, "last_page_rows": 0,
            "read_error": "holding fields unavailable: %s" % schema.get("missing", []),
            "hit_cap": False, "field_map": dict(schema.get("field_map", {})),
        }
    resolved = schema["resolved"]
    field_map = schema["field_map"]
    fields, seen_actual = [], set()
    for canonical in ("code", "name", "period_end", "pub_date", "symbol", "proportion", "rank", "market_value"):
        if canonical not in resolved:
            continue
        actual = field_map[canonical]
        if actual in seen_actual:
            continue
        seen_actual.add(actual)
        fields.append(resolved[canonical])

    pieces, offset, last_rows, pages, error = [], 0, 0, 0, None
    while offset < int(g.fund_max_rows_per_quarter):
        q = query(*fields).filter(
            resolved["period_end"] == period.date(),
            resolved["pub_date"] <= pd.Timestamp(asof).date(),
        )
        if "rank" in resolved:
            q = q.filter(resolved["rank"] <= 10)
        try:
            order_fields = [resolved["code"].asc(), resolved["symbol"].asc(), resolved["pub_date"].asc()]
            q = q.order_by(*order_fields)
        except Exception:
            pass
        try:
            part = finance.run_query(
                q.limit(int(g.fund_page_size)).offset(int(offset))
            )
        except Exception as exc:
            error = str(exc)
            break
        if part is None or part.empty:
            last_rows = 0
            break
        part = _canonicalize_query_columns(part, field_map)
        pieces.append(part)
        pages += 1
        last_rows = int(len(part))
        offset += last_rows
        if last_rows < int(g.fund_page_size):
            break
    frame = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    # 个别历史环境没有rank字段时，按每只基金披露权重降序保留前10，避免扩大披露口径。
    if len(frame) and "rank" not in frame.columns and _py_builtins.all(
        name in frame.columns for name in ("code", "period_end", "proportion")
    ):
        frame["proportion"] = pd.to_numeric(frame["proportion"], errors="coerce")
        frame.sort_values(["code", "period_end", "proportion"], ascending=[True, True, False], inplace=True)
        frame = frame.groupby(["code", "period_end"], as_index=False, group_keys=False).head(10)
        frame["rank"] = frame.groupby(["code", "period_end"]).cumcount() + 1
    return frame, {
        "pages": int(pages), "raw_rows": int(len(frame)),
        "last_page_rows": int(last_rows), "read_error": error,
        "field_map": dict(field_map),
        "result_columns": list(frame.columns),
        "hit_cap": bool(
            offset >= int(g.fund_max_rows_per_quarter)
            and last_rows >= int(g.fund_page_size)
        ),
    }


def _clean_one_fund_quarter(frame, period, asof, page_meta, active_codes, all_codes):
    meta = {
        "period": str(period.date()),
        "period_age_days": int((pd.Timestamp(asof) - period).days),
        "pages": int(page_meta.get("pages", 0)),
        "raw_rows": int(page_meta.get("raw_rows", 0)),
        "hit_cap": bool(page_meta.get("hit_cap", False)),
        "read_error": page_meta.get("read_error"),
        "holding_field_map": dict(page_meta.get("field_map", {})),
        "holding_result_columns": list(page_meta.get("result_columns", [])),
        "fund_classification_mode": dict(getattr(g, "fund_main_info_meta", {})).get("classification_mode"),
    }
    if frame is None or frame.empty:
        meta.update({"complete": False, "signal_ready": False, "reason": "no rows"})
        return pd.DataFrame(), meta
    work = frame.copy()
    work["period_end"] = pd.to_datetime(work["period_end"], errors="coerce")
    work["pub_date"] = pd.to_datetime(work["pub_date"], errors="coerce")
    work = work[work["pub_date"] <= pd.Timestamp(asof)].copy()
    work["fund"] = work["code"].astype(str).str.strip()
    work["stock"] = work["symbol"].map(_normalize_a_share_code)
    work["proportion"] = pd.to_numeric(work["proportion"], errors="coerce")
    value_column = "market_value" if "market_value" in work.columns else (
        "market_cap" if "market_cap" in work.columns else None
    )
    work["market_value"] = (
        pd.to_numeric(work[value_column], errors="coerce")
        if value_column is not None else np.nan
    )
    a_share = work[work["stock"].notna() & work["proportion"].gt(0)].copy()
    a_share_funds = set(a_share["fund"].astype(str))
    if bool(getattr(g, "pit_fix_holdings_derived_active", False)):
        # PIT-FIX F-3：主动偏股判定由当季已披露持仓推导（点时安全），不再使用
        # FUND_MAIN_INFO 的当前分类（审计确定前视：2013Q3 曾因此剔除452只/42%）。
        # 口径：当季A股披露权重合计>=fund_min_disclosed_weight 且持股数
        # >=fund_min_stocks_per_fund（复用原有 valid_funds 阈值，保持口径一致）。
        # 已知构念变化：满足披露条件的被动产品（指数基金等）会被纳入，
        # 信号由"主动资金"变为"全部权益敞口资金"；回退原行为做A/B：
        # 置 g.pit_fix_holdings_derived_active=False。
        _derived_weight = a_share.groupby("fund")["proportion"].sum()
        _derived_count = a_share.groupby("fund")["stock"].nunique()
        _derived_active = set(_derived_weight[
            (_derived_weight >= float(g.fund_min_disclosed_weight))
            & (_derived_count >= int(g.fund_min_stocks_per_fund))
        ].index.astype(str))
        g.pit_fix_derived_active_last = {
            "derived_active_funds": int(len(_derived_active)),
            "classification_active_funds": (
                int(len(set(a_share["fund"].astype(str)) & set(active_codes)))
                if active_codes else None
            ),
        }
        active = a_share[a_share["fund"].isin(_derived_active)].copy()
        meta["active_source"] = "holdings_derived_pit"
        meta["derived_active_funds"] = int(len(_derived_active))
        meta["classification_active_funds"] = g.pit_fix_derived_active_last[
            "classification_active_funds"]
    else:
        active = a_share[a_share["fund"].isin(active_codes)].copy() if active_codes else a_share.iloc[0:0].copy()
        meta["active_source"] = "fund_main_info_current_classification"
    active.sort_values("pub_date", inplace=True)
    duplicate_rows = int(
        active.duplicated(["fund", "period_end", "stock"], keep="last").sum()
    )
    active.drop_duplicates(["fund", "period_end", "stock"], keep="last", inplace=True)
    if active.empty:
        meta.update({
            "complete": False, "signal_ready": False,
            "reason": "no active A-share fund rows",
            "a_share_rows": int(len(a_share)), "valid_funds": 0, "valid_rows": 0,
        })
        return active, meta
    groups = active.groupby(["fund", "period_end"])
    valid_funds = pd.DataFrame({
        "stock_count": groups["stock"].nunique(),
        "disclosed_weight": groups["proportion"].sum(),
    })
    valid_funds = valid_funds[
        (valid_funds["stock_count"] >= int(g.fund_min_stocks_per_fund))
        & (valid_funds["disclosed_weight"] >= float(g.fund_min_disclosed_weight))
    ]
    valid_keys = set(valid_funds.index.tolist())
    mask = [
        tuple(item) in valid_keys
        for item in active[["fund", "period_end"]].itertuples(index=False, name=None)
    ]
    clean = active[mask].copy()
    market_value_coverage = float(clean["market_value"].notna().mean()) if len(clean) else 0.0
    reasons = []
    if meta["read_error"]:
        reasons.append("read_error")
    if meta["hit_cap"]:
        reasons.append("hit_cap")
    if not active_codes and not bool(getattr(g, "pit_fix_holdings_derived_active", False)):
        reasons.append("fund_main_info_unavailable")
    if len(a_share) < int(g.fund_min_a_share_rows):
        reasons.append("too_few_a_share_rows")
    if clean["fund"].nunique() < int(g.fund_min_valid_funds):
        reasons.append("too_few_valid_funds")
    complete = not reasons
    signal_ready = bool(
        complete
        and clean["fund"].nunique() >= int(g.fund_signal_min_valid_funds)
        and market_value_coverage >= float(g.fund_min_market_value_coverage)
    )
    meta.update({
        "complete": complete, "signal_ready": signal_ready,
        "reason": "ok" if complete else ",".join(reasons),
        "a_share_rows": int(len(a_share)),
        "a_share_funds": int(len(a_share_funds)),
        "active_funds": int(active["fund"].nunique()),
        "valid_funds": int(clean["fund"].nunique()),
        "valid_rows": int(len(clean)),
        "valid_stocks": int(clean["stock"].nunique()) if len(clean) else 0,
        "duplicate_rows_removed": duplicate_rows,
        "market_value_coverage": market_value_coverage,
        "main_code_match_rate": (
            float(len(a_share_funds.intersection(all_codes))) / float(len(a_share_funds))
            if a_share_funds and all_codes else np.nan
        ),
        "max_pub_date": (
            str(pd.Timestamp(work["pub_date"].max()).date())
            if work["pub_date"].notna().any() else None
        ),
    })
    return clean, meta


def _fund_pair_key(current_period, previous_period):
    return "%s|%s" % (
        str(pd.Timestamp(current_period).date()),
        str(pd.Timestamp(previous_period).date()),
    )


def _fund_select_usable_pair(quarters, asof):
    """从按季度倒序列表中选择第一组可比季度，保持V18E1研究版沿用的原覆盖规则。"""
    for index in range(max(0, len(quarters) - 1)):
        current_period, current, current_meta = quarters[index]
        previous_period, previous, previous_meta = quarters[index + 1]
        if not current_meta.get("signal_ready", False):
            continue
        previous_funds = max(1, int(previous_meta.get("valid_funds", 0)))
        relative_coverage = float(current_meta.get("valid_funds", 0)) / previous_funds
        if relative_coverage < float(g.fund_min_relative_coverage):
            continue
        return {
            "current_period": current_period,
            "current": current,
            "current_meta": current_meta,
            "previous_period": previous_period,
            "previous": previous,
            "previous_meta": previous_meta,
            "relative_coverage": relative_coverage,
        }
    return None


def _fund_frame_estimated_bytes(frame):
    if frame is None:
        return 0
    try:
        return int(frame.memory_usage(index=True, deep=True).sum())
    except Exception:
        return 0


def _fund_recent_auxiliary_keys(asof):
    periods = _recent_quarter_ends(asof, int(g.fund_max_quarters_to_scan) + 1)
    keys = set(str(pd.Timestamp(period).date()) for period in periods)
    last_pair = getattr(g, "fund_last_selected_pair", None)
    if last_pair and len(last_pair) == 2:
        keys.update(str(value) for value in last_pair)
    return keys


def _fund_prune_cache_state(asof, active_keys=None, reason="rolling_window"):
    """只保留活动两季度、一个pair描述和最近查询控制键。"""
    before_snapshot = set(getattr(g, "fund_snapshot_cache", {}).keys())
    before_pair = set(getattr(g, "fund_selected_pair_cache", {}).keys())
    if active_keys is None:
        last_pair = getattr(g, "fund_last_selected_pair", None)
        active_keys = list(last_pair) if last_pair and len(last_pair) == 2 else []
    keep_snapshot = set(str(value) for value in list(active_keys or [])[:2])
    if not keep_snapshot and before_snapshot:
        keep_snapshot = set(sorted(before_snapshot, reverse=True)[:2])

    g.fund_snapshot_cache = {
        key: frame for key, frame in getattr(g, "fund_snapshot_cache", {}).items()
        if str(key) in keep_snapshot
    }
    g.fund_quarter_meta_cache = {
        key: meta for key, meta in getattr(g, "fund_quarter_meta_cache", {}).items()
        if str(key) in keep_snapshot
    }

    active_pair_key = None
    if len(active_keys or []) >= 2:
        active_pair_key = _fund_pair_key(active_keys[0], active_keys[1])
    pair_cache = getattr(g, "fund_selected_pair_cache", {})
    if active_pair_key is not None and active_pair_key in pair_cache:
        g.fund_selected_pair_cache = {
            active_pair_key: pair_cache[active_pair_key]
        }
    elif pair_cache:
        newest_pair_key = sorted(pair_cache.keys(), reverse=True)[0]
        g.fund_selected_pair_cache = {
            newest_pair_key: pair_cache[newest_pair_key]
        }
    else:
        g.fund_selected_pair_cache = {}

    auxiliary_keys = _fund_recent_auxiliary_keys(asof)
    auxiliary_limit = int(getattr(g, "fund_auxiliary_key_limit", 8))
    if len(auxiliary_keys) > auxiliary_limit:
        auxiliary_keys = set(sorted(auxiliary_keys, reverse=True)[:auxiliary_limit])
    g.fund_quarter_negative_cache = set(
        str(key) for key in getattr(g, "fund_quarter_negative_cache", set())
        if str(key) in auxiliary_keys
    )
    g.fund_quarter_retry_after = {
        str(key): value
        for key, value in getattr(g, "fund_quarter_retry_after", {}).items()
        if str(key) in auxiliary_keys
    }

    removed_snapshot = sorted(before_snapshot - set(g.fund_snapshot_cache.keys()))
    removed_pair = sorted(before_pair - set(g.fund_selected_pair_cache.keys()))
    if removed_snapshot or removed_pair:
        log.info(
            "V18E1_MEMORY_CLEANUP|%s"
            % json.dumps(
                {
                    "reason": str(reason),
                    "removed_snapshot_keys": removed_snapshot,
                    "removed_pair_keys": removed_pair,
                    "kept_snapshot_keys": sorted(g.fund_snapshot_cache.keys()),
                    "kept_pair_keys": sorted(g.fund_selected_pair_cache.keys()),
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        )


def _fund_cache_pickle_probe():
    """用小样本验证缓存类型可pickle，避免复制完整季度造成审计峰值。"""
    sample_snapshots = {}
    for key, frame in getattr(g, "fund_snapshot_cache", {}).items():
        try:
            sample_snapshots[str(key)] = frame.head(2)
        except Exception:
            sample_snapshots[str(key)] = None
    payload = {
        "snapshot_samples": sample_snapshots,
        "quarter_meta": getattr(g, "fund_quarter_meta_cache", {}),
        "selected_pairs": getattr(g, "fund_selected_pair_cache", {}),
        "last_selected_pair": getattr(g, "fund_last_selected_pair", None),
        "holding_schema": getattr(g, "fund_holding_schema_cache", None),
        "holding_field_map": getattr(g, "fund_holding_field_map", {}),
        "negative_keys": getattr(g, "fund_quarter_negative_cache", set()),
        "retry_after": getattr(g, "fund_quarter_retry_after", {}),
    }
    pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
    return True


def _fund_cache_audit(reason):
    snapshot_cache = getattr(g, "fund_snapshot_cache", {})
    pair_cache = getattr(g, "fund_selected_pair_cache", {})
    snapshot_rows = int(sum(len(frame) for frame in snapshot_cache.values()))
    snapshot_bytes = int(sum(
        _fund_frame_estimated_bytes(frame) for frame in snapshot_cache.values()
    ))
    pickle_ok, pickle_error = True, None
    try:
        _fund_cache_pickle_probe()
    except Exception as exc:
        pickle_ok, pickle_error = False, str(exc)
    audit = {
        "reason": str(reason),
        "snapshot_keys": sorted(str(key) for key in snapshot_cache.keys()),
        "snapshot_key_count": int(len(snapshot_cache)),
        "snapshot_key_limit": int(getattr(g, "fund_snapshot_cache_limit", 2)),
        "pair_keys": sorted(str(key) for key in pair_cache.keys()),
        "pair_key_count": int(len(pair_cache)),
        "pair_key_limit": int(getattr(g, "fund_selected_pair_cache_limit", 1)),
        "snapshot_rows": snapshot_rows,
        "pair_cached_rows": 0,
        "estimated_snapshot_bytes": snapshot_bytes,
        "negative_key_count": int(len(getattr(g, "fund_quarter_negative_cache", set()))),
        "retry_key_count": int(len(getattr(g, "fund_quarter_retry_after", {}))),
        "pickle_probe_ok": bool(pickle_ok),
        "pickle_error": pickle_error,
    }
    audit["bounded"] = bool(
        audit["snapshot_key_count"] <= audit["snapshot_key_limit"]
        and audit["pair_key_count"] <= audit["pair_key_limit"]
        and audit["negative_key_count"] <= int(getattr(g, "fund_auxiliary_key_limit", 8))
        and audit["retry_key_count"] <= int(getattr(g, "fund_auxiliary_key_limit", 8))
    )
    g.fund_cache_last_audit = dict(audit)
    payload = json.dumps(audit, ensure_ascii=False, sort_keys=True, default=str)
    if audit["bounded"] and audit["pickle_probe_ok"]:
        log.info("V18E1_MEMORY_AUDIT|%s" % payload)
    else:
        log.warning("V18E1_MEMORY_AUDIT|%s" % payload)
    return audit


def _fund_activate_pair(pair, asof, diagnostics=None):
    """仅缓存活动pair的字符串描述；拼接表只在本次计算中临时存在。"""
    diagnostics = dict(diagnostics or {})
    current_period = pd.Timestamp(pair["current_period"])
    previous_period = pd.Timestamp(pair["previous_period"])
    pair_key = _fund_pair_key(current_period, previous_period)
    current_key = str(current_period.date())
    previous_key = str(previous_period.date())
    # 原子替换为活动两季度；扫描中的候选快照只留在局部变量，不进入长期g缓存。
    g.fund_snapshot_cache = {
        current_key: pair["current"],
        previous_key: pair["previous"],
    }
    g.fund_quarter_meta_cache = {
        current_key: dict(pair["current_meta"]),
        previous_key: dict(pair["previous_meta"]),
    }
    if pair_key in g.fund_selected_pair_cache:
        g.fund_query_stats["pair_cache_hits"] += 1
        diagnostics.setdefault("selection_source", "selected_pair_cache")
    else:
        g.fund_selected_pair_cache = {
            pair_key: {
                "current_period": str(current_period.date()),
                "previous_period": str(previous_period.date()),
            }
        }
        diagnostics.setdefault("selection_source", "quarter_snapshot_cache")
    g.fund_last_selected_pair = (
        str(current_period.date()), str(previous_period.date())
    )
    _fund_prune_cache_state(
        asof,
        active_keys=list(g.fund_last_selected_pair),
        reason="activate_pair",
    )
    # 下游第一步会按股票池筛选并copy；此处不再复制两个完整季度。
    selected = pd.concat(
        [pair["previous"], pair["current"]],
        ignore_index=True,
    )
    g.latest_fund_selection_meta = {
        "available": True,
        "current_period": str(current_period.date()),
        "previous_period": str(previous_period.date()),
        "current_period_age_days": int((pd.Timestamp(asof) - current_period).days),
        "current_valid_funds": int(pair["current_meta"].get("valid_funds", 0)),
        "previous_valid_funds": int(pair["previous_meta"].get("valid_funds", 0)),
        "relative_coverage": float(pair["relative_coverage"]),
        "market_value_coverage": float(
            pair["current_meta"].get("market_value_coverage", 0.0)
        ),
        "query_diagnostics": diagnostics,
    }
    log.info("机构季度采用｜%s" % json.dumps(
        g.latest_fund_selection_meta, ensure_ascii=False, default=str
    ))
    g.latest_fund_load_meta = dict(g.latest_fund_selection_meta)
    g.latest_fund_load_meta["available"] = True
    g.latest_fund_load_meta["reason"] = "ok"
    if bool(getattr(g, "fund_cache_audit_enabled", True)):
        _fund_cache_audit("activate_pair")
    return selected


def _fund_cached_selected_pair(asof):
    """没有需要刷新的新季度时，普通月份直接返回已采用季度，零数据库访问。"""
    last_pair = getattr(g, "fund_last_selected_pair", None)
    if not last_pair or len(last_pair) != 2:
        return None
    current_key, previous_key = tuple(last_pair)
    if (
        current_key not in g.fund_snapshot_cache
        or previous_key not in g.fund_snapshot_cache
    ):
        return None
    periods = _recent_quarter_ends(asof, 1)
    newest_period = periods[0] if periods else pd.Timestamp(current_key)
    current_period = pd.Timestamp(current_key)
    newest_key = str(pd.Timestamp(newest_period).date())
    newest_age = int((pd.Timestamp(asof) - pd.Timestamp(newest_period)).days)
    retry_after = getattr(g, "fund_quarter_retry_after", {}).get(newest_key)
    refresh_due = bool(
        pd.Timestamp(newest_period) > current_period
        and newest_key not in g.fund_quarter_negative_cache
        and newest_age >= int(g.fund_quarter_min_query_age_days)
        and (retry_after is None or pd.Timestamp(asof) >= pd.Timestamp(retry_after))
    )
    if refresh_due:
        return None
    current_meta = dict(g.fund_quarter_meta_cache.get(current_key, {}))
    previous_meta = dict(g.fund_quarter_meta_cache.get(previous_key, {}))
    previous_funds = max(1, int(previous_meta.get("valid_funds", 0)))
    pair = {
        "current_period": current_period,
        "current": g.fund_snapshot_cache[current_key],
        "current_meta": current_meta,
        "previous_period": pd.Timestamp(previous_key),
        "previous": g.fund_snapshot_cache[previous_key],
        "previous_meta": previous_meta,
        "relative_coverage": float(current_meta.get("valid_funds", 0)) / previous_funds,
    }
    return _fund_activate_pair(pair, asof, {
        "selection_source": "ordinary_month_pair_cache",
        "queried_quarters": 0,
        "quarter_cache_hits": 2,
        "scanned_quarters": 0,
        "early_stop": True,
        "newest_candidate_period": newest_key,
        "newest_candidate_age_days": newest_age,
        "refresh_due": False,
    })


def _fund_quarter_query_allowed(period, asof):
    key = str(pd.Timestamp(period).date())
    age = int((pd.Timestamp(asof) - pd.Timestamp(period)).days)
    if age < int(g.fund_quarter_min_query_age_days):
        g.fund_query_stats["disclosure_window_skips"] += 1
        return False, "before_disclosure_window"
    retry_after = getattr(g, "fund_quarter_retry_after", {}).get(key)
    if retry_after is not None and pd.Timestamp(asof) < pd.Timestamp(retry_after):
        g.fund_query_stats["retry_skips"] += 1
        return False, "retry_cooldown"
    return True, "ok"


def _fund_mark_retry(period, asof):
    key = str(pd.Timestamp(period).date())
    g.fund_quarter_retry_after[key] = (
        pd.Timestamp(asof) + pd.Timedelta(days=int(g.fund_quarter_retry_days))
    ).normalize()


def _load_fund_holdings(asof):
    """早停选择两个完整季度；普通月份零查询，新季度只补读一个季度。"""
    g.latest_fund_load_meta = {"available": False, "asof": str(asof)}
    _fund_prune_cache_state(asof, reason="load_start")

    # 最快路径：最新自然季度没有进入可查询窗口，或没有新季度，直接复用上月结果。
    cached_selected = _fund_cached_selected_pair(asof)
    if cached_selected is not None:
        return cached_selected

    table = getattr(finance, "FUND_PORTFOLIO_STOCK", None)
    if table is None:
        g.latest_fund_load_meta["reason"] = "FUND_PORTFOLIO_STOCK table unavailable"
        log.warning("机构持仓加载失败：%s" % g.latest_fund_load_meta)
        return pd.DataFrame()
    active_codes, all_codes = _load_fund_main_codes(asof)
    if not active_codes and not (
        bool(getattr(g, "pit_fix_holdings_derived_active", False)) and all_codes
    ):
        g.latest_fund_load_meta.update({
            "reason": "active fund main codes unavailable",
            "fund_main_info": dict(getattr(g, "fund_main_info_meta", {})),
            "fund_main_field_map": dict(getattr(g, "fund_main_field_map", {})),
            "fund_holding_field_map": dict(getattr(g, "fund_holding_field_map", {})),
        })
        log.warning("机构持仓加载失败：%s" % g.latest_fund_load_meta)
        return pd.DataFrame()

    quarters = []
    queried_quarters = 0
    quarter_cache_hits = 0
    scanned_quarters = 0
    skipped_quarters = []
    periods = _recent_quarter_ends(asof, g.fund_max_quarters_to_scan)
    for period in periods:
        scanned_quarters += 1
        key = str(period.date())
        if key in g.fund_quarter_negative_cache:
            skipped_quarters.append({"period": key, "reason": "negative_cache"})
            continue
        if key in g.fund_snapshot_cache:
            clean = g.fund_snapshot_cache[key]
            meta = dict(g.fund_quarter_meta_cache.get(key, {}))
            quarter_cache_hits += 1
            g.fund_query_stats["quarter_cache_hits"] += 1
        else:
            allowed, skip_reason = _fund_quarter_query_allowed(period, asof)
            if not allowed:
                skipped_quarters.append({"period": key, "reason": skip_reason})
                continue
            if queried_quarters >= int(
                getattr(g, "fund_monthly_quarter_query_limit", 2)
            ):
                skipped_quarters.append({
                    "period": key,
                    "reason": "monthly_query_budget_exhausted",
                })
                continue
            # 预算表示已经发起的真实API尝试，必须在调用前原子预占；
            # 查询异常同样消耗预算，第三个季度绝不能继续发起。
            queried_quarters += 1
            g.fund_query_stats["quarter_queries"] += 1
            try:
                raw, page_meta = _load_one_fund_quarter(table, period, asof)
                clean, meta = _clean_one_fund_quarter(
                    raw, period, asof, page_meta, active_codes, all_codes
                )
            except Exception as exc:
                _fund_mark_retry(period, asof)
                log.warning("机构季度%s读取失败：%s" % (key, exc))
                skipped_quarters.append({"period": key, "reason": "read_error"})
                continue
            log.info("机构季度快照｜%s" % json.dumps(meta, ensure_ascii=False, default=str))
            # 新季度只有达到可发出信号的覆盖度才锁定；历史完整基线可直接缓存。
            if meta.get("complete") and (
                meta.get("signal_ready")
                or int(meta.get("period_age_days", 0)) > g.mainline_max_fund_age_days
            ):
                # 只把最终选中的pair写入g；扫描候选留在本函数局部，避免缓存瞬时超界。
                g.fund_quarter_retry_after.pop(key, None)
            else:
                _fund_mark_retry(period, asof)
                if (
                    meta.get("reason") == "no rows"
                    and not meta.get("read_error")
                    and int(meta.get("period_age_days", 0)) > g.mainline_max_fund_age_days
                ):
                    # 已过去完整披露窗口仍无数据的历史季度记为永久空。
                    g.fund_quarter_negative_cache.add(key)
            if (
                meta.get("complete")
                and not meta.get("signal_ready")
                and int(meta.get("period_age_days", 0))
                > int(g.mainline_max_fund_age_days)
            ):
                # 已过完整披露窗仍达不到正式信号覆盖度的历史季度
                # 不会再改变。记为不可用，让后续月份在两次预算内向更早季度推进。
                g.fund_quarter_negative_cache.add(key)
        if meta.get("complete"):
            quarters.append((period, clean, meta))

        # 关键优化：每加入一个完整季度就立即检查；找到第一组可比季度马上停止。
        pair = _fund_select_usable_pair(quarters, asof)
        if pair is not None:
            g.fund_query_stats["early_stops"] += 1
            diagnostics = {
                "queried_quarters": int(queried_quarters),
                "quarter_cache_hits": int(quarter_cache_hits),
                "scanned_quarters": int(scanned_quarters),
                "configured_scan_cap": int(g.fund_max_quarters_to_scan),
                "monthly_query_limit": int(
                    getattr(g, "fund_monthly_quarter_query_limit", 2)
                ),
                "early_stop": True,
                "skipped_quarters": skipped_quarters,
            }
            log.info("V171_FUND_QUERY|%s" % json.dumps(
                diagnostics, ensure_ascii=False, default=str, sort_keys=True
            ))
            return _fund_activate_pair(pair, asof, diagnostics)

    g.latest_fund_selection_meta = {}
    diagnostics = {
        "queried_quarters": int(queried_quarters),
        "quarter_cache_hits": int(quarter_cache_hits),
        "scanned_quarters": int(scanned_quarters),
        "configured_scan_cap": int(g.fund_max_quarters_to_scan),
        "monthly_query_limit": int(
            getattr(g, "fund_monthly_quarter_query_limit", 2)
        ),
        "early_stop": False,
        "skipped_quarters": skipped_quarters,
    }
    g.latest_fund_load_meta.update({
        "reason": "no two sufficiently covered disclosed quarters",
        "complete_quarters": int(len(quarters)),
        "scanned_quarters": int(scanned_quarters),
        "query_diagnostics": diagnostics,
    })
    log.info("V171_FUND_QUERY|%s" % json.dumps(
        diagnostics, ensure_ascii=False, default=str, sort_keys=True
    ))
    log.warning("机构持仓加载失败：%s" % g.latest_fund_load_meta)
    _fund_prune_cache_state(asof, reason="no_usable_pair")
    if bool(getattr(g, "fund_cache_audit_enabled", True)):
        _fund_cache_audit("no_usable_pair")
    return pd.DataFrame()


def _cross_rank_dict(values):
    if not values:
        return {}
    series = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan)
    return (series.rank(pct=True, method="average") * 100.0).fillna(0.0).to_dict()


def _calc_fund_industry_scores(asof, industry_map, fundamentals):
    holdings = _load_fund_holdings(asof)
    if holdings.empty:
        reason = dict(getattr(g, "latest_fund_load_meta", {}))
        reason.setdefault("available", False)
        reason.setdefault("reason", "fund holdings empty")
        return {}, {}, reason
    holdings = holdings[holdings["stock"].isin(set(industry_map.keys()))].copy()
    periods = sorted(holdings["period_end"].dropna().unique())
    if len(periods) < 2:
        return {}, {}, {"available": False, "reason": "less than two disclosed quarters"}
    previous_period, current_period = periods[-2], periods[-1]
    current = holdings[holdings["period_end"] == current_period].copy()
    previous = holdings[holdings["period_end"] == previous_period].copy()
    if current.empty or previous.empty:
        return {}, {}, {"available": False, "reason": "quarter rows empty"}
    current["industry"] = current["stock"].map(lambda x: industry_map[x][0])
    previous["industry"] = previous["stock"].map(lambda x: industry_map[x][0])

    def fund_industry(frame):
        grouped = frame.groupby(["fund", "industry"])["proportion"].sum().reset_index()
        totals = grouped.groupby("fund")["proportion"].transform("sum").replace(0, np.nan)
        grouped["weight"] = grouped["proportion"] / totals
        return grouped.dropna(subset=["weight"])

    cur = fund_industry(current)
    prev = fund_industry(previous)
    cur_pivot = cur.pivot(index="fund", columns="industry", values="weight").fillna(0.0)
    prev_pivot = prev.pivot(index="fund", columns="industry", values="weight").fillna(0.0)
    comparable = cur_pivot.index.intersection(prev_pivot.index)
    industries = sorted(set(cur_pivot.columns) | set(prev_pivot.columns))
    if len(comparable) < int(g.fund_min_comparable_funds):
        return {}, {}, {
            "available": False,
            "reason": "comparable funds %d below %d" % (
                len(comparable), g.fund_min_comparable_funds
            ),
            "current_period": str(pd.Timestamp(current_period).date()),
            "previous_period": str(pd.Timestamp(previous_period).date()),
        }

    def capped_fund_weights(source, pivot):
        sizes = source.groupby("fund")["market_value"].sum().reindex(pivot.index)
        sizes = pd.to_numeric(sizes, errors="coerce").clip(lower=0)
        if sizes.notna().sum() < max(3, int(len(pivot) * 0.50)) or sizes.sum() <= 0:
            weights = pd.Series(1.0, index=pivot.index)
        else:
            weights = sizes.fillna(sizes.median())
        weights = weights / weights.sum()
        # 单一巨型基金贡献最多5%；反复截断后重新归一，直至稳定。
        for _ in range(5):
            weights = weights.clip(upper=0.05)
            weights = weights / weights.sum()
        return weights

    cur_matrix = cur_pivot.reindex(columns=industries, fill_value=0.0)
    prev_matrix = prev_pivot.reindex(columns=industries, fill_value=0.0)
    cur_weight = cur_matrix.mul(capped_fund_weights(current, cur_pivot), axis=0).sum(axis=0)
    prev_weight = prev_matrix.mul(capped_fund_weights(previous, prev_pivot), axis=0).sum(axis=0)

    caps = fundamentals.set_index("code")["market_cap"].astype(float)
    benchmark = {}
    total_cap = float(caps.sum())
    for industry in industries:
        members = [code for code, item in industry_map.items() if item[0] == industry]
        benchmark[industry] = float(caps.reindex(members).fillna(0.0).sum() / total_cap) if total_cap > 0 else 0.0
    overweight = {x: float(cur_weight.get(x, 0.0) - benchmark.get(x, 0.0)) for x in industries}
    addition = {x: float(cur_weight.get(x, 0.0) - prev_weight.get(x, 0.0)) for x in industries}
    increase_breadth, new_breadth = {}, {}
    company_coverage, top1_contribution = {}, {}
    for industry in industries:
        if len(comparable) == 0:
            increase_breadth[industry] = 0.0
            new_breadth[industry] = 0.0
            continue
        c = cur_pivot.reindex(index=comparable, columns=[industry], fill_value=0.0)[industry]
        p = prev_pivot.reindex(index=comparable, columns=[industry], fill_value=0.0)[industry]
        increase_breadth[industry] = float((c > p + 1e-8).mean())
        new_breadth[industry] = float(((c > 0) & (p <= 0)).mean())
        industry_rows = current[current["industry"] == industry]
        member_count = max(1, sum(1 for value in industry_map.values() if value[0] == industry))
        company_coverage[industry] = float(industry_rows["stock"].nunique() / member_count)
        stock_signal = industry_rows.groupby("stock")["fund"].nunique()
        top1_contribution[industry] = float(stock_signal.max() / stock_signal.sum()) if stock_signal.sum() > 0 else 1.0
    ranks = [_cross_rank_dict(x) for x in (overweight, addition, increase_breadth, new_breadth, company_coverage)]
    scores, diffusion = {}, {}
    for industry in industries:
        score = 0.30 * ranks[0].get(industry, 0) + 0.30 * ranks[1].get(industry, 0)
        score += 0.25 * ranks[2].get(industry, 0) + 0.15 * ranks[3].get(industry, 0)
        if cur_weight.get(industry, 0) >= cur_weight.quantile(0.70) and addition[industry] < 0:
            score = min(score, 60.0)
        scores[industry] = float(score)
        diff_score = 0.50 * ranks[2].get(industry, 0) + 0.25 * ranks[3].get(industry, 0)
        diff_score += 0.25 * ranks[4].get(industry, 0)
        concentration = top1_contribution.get(industry, 1.0)
        if concentration > 0.50:
            diff_score = min(diff_score, 40.0)
        elif concentration > 0.30:
            diff_score *= 0.80
        diffusion[industry] = float(diff_score)
    meta = {
        "available": True, "current_period": str(pd.Timestamp(current_period).date()),
        "previous_period": str(pd.Timestamp(previous_period).date()),
        "current_period_age_days": int((pd.Timestamp(asof) - pd.Timestamp(current_period)).days),
        "funds": int(cur_pivot.shape[0]), "rows": int(len(current)),
        "fund_weight_mode": "market_value_capped" if current["market_value"].notna().any() else "equal_weight",
        "comparable_funds": int(len(comparable)),
    }
    meta.update(getattr(g, "latest_fund_selection_meta", {}))
    return scores, diffusion, meta


def _calc_capacity_scores(asof, industry_members, fundamentals):
    """用每行业流通容量代表股批量确认20/60日中期趋势，控制平台算例。"""
    cap_map = fundamentals.set_index("code")["market_cap"].astype(float).to_dict()
    sample = []
    for industry, members in industry_members.items():
        ranked = sorted(members, key=lambda x: cap_map.get(x, 0.0), reverse=True)
        sample.extend(ranked[:g.market_price_sample_per_industry])
    sample = sorted(set(sample))
    frames = _load_price_frames(sample + [g.benchmark], asof, count=g.capacity_daily_count)
    benchmark = frames.get(g.benchmark)
    if benchmark is None or len(benchmark.dropna(subset=["close"])) < 80:
        return {}, {}, {"available": False, "sample": len(sample)}
    bench_close = benchmark.dropna(subset=["close"])["close"].astype(float)
    bench20 = float(bench_close.iloc[-1] / bench_close.iloc[-21] - 1.0)
    bench60 = float(bench_close.iloc[-1] / bench_close.iloc[-61] - 1.0)
    raw = {}
    overheat_raw = {}
    for industry, members in industry_members.items():
        rows = []
        for code in members:
            frame = frames.get(code)
            if frame is None:
                continue
            usable = frame[(frame["paused"] == 0)].dropna(subset=["close", "money"]).tail(80)
            if len(usable) < 65:
                continue
            close = usable["close"].astype(float)
            money = usable["money"].astype(float)
            r20 = float(close.iloc[-1] / close.iloc[-21] - 1.0)
            r60 = float(close.iloc[-1] / close.iloc[-61] - 1.0)
            rows.append({
                "code": code, "r20": r20, "r60": r60,
                "above20": float(close.iloc[-1] > close.tail(20).mean()),
                "above60": float(close.iloc[-1] > close.tail(60).mean()),
                "money20": float(money.tail(20).mean()),
                "money_prev60": float(money.iloc[-80:-20].mean()),
                "deviation20": float(close.iloc[-1] / close.tail(20).mean() - 1.0),
                "limit5": float((close.pct_change().tail(5) >= 0.095).any()),
            })
        if len(rows) < g.capacity_min_stocks:
            continue
        data = pd.DataFrame(rows)
        total_recent = data["money20"].sum()
        total_previous = data["money_prev60"].sum()
        raw[industry] = {
            "share_momentum": np.nan,
            "money_recent": float(total_recent),
            "money_previous": float(total_previous),
            "relative_strength": float(0.6 * (data["r20"].median() - bench20) + 0.4 * (data["r60"].median() - bench60)),
            "breadth": float(0.4 * data["above20"].mean() + 0.3 * data["above60"].mean() + 0.3 * (data["r60"] > 0).mean()),
            "persistence": float(0.5 * data["r20"].median() + 0.5 * data["r60"].median()),
            "leader": float(data.nlargest(min(5, len(data)), "money20")[["above20", "above60"]].mean().mean()),
        }
        overheat_raw[industry] = {
            "limit_ratio": float(data["limit5"].mean()),
            "money_ratio": float(total_recent / total_previous) if total_previous > 0 else 1.0,
            "deviation": float(data["deviation20"].median()),
        }
    if not raw:
        return {}, {}, {"available": False, "sample": len(sample)}
    market_recent = sum(item["money_recent"] for item in raw.values())
    market_previous = sum(item["money_previous"] for item in raw.values())
    for item in raw.values():
        current_share = item["money_recent"] / market_recent if market_recent > 0 else np.nan
        previous_share = item["money_previous"] / market_previous if market_previous > 0 else np.nan
        item["share_momentum"] = (
            float(current_share / previous_share - 1.0)
            if np.isfinite(current_share) and np.isfinite(previous_share) and previous_share > 0
            else np.nan
        )
    metric_ranks = {}
    for metric in ("share_momentum", "relative_strength", "breadth", "persistence", "leader"):
        metric_ranks[metric] = _cross_rank_dict({k: v[metric] for k, v in raw.items()})
    scores = {}
    for industry in raw:
        scores[industry] = float(
            0.25 * metric_ranks["share_momentum"][industry]
            + 0.25 * metric_ranks["relative_strength"][industry]
            + 0.20 * metric_ranks["breadth"][industry]
            + 0.15 * metric_ranks["persistence"][industry]
            + 0.15 * metric_ranks["leader"][industry]
        )
    # 过热先只记录：没有完成独立样本验收前不扣主线分。
    heat_ranks = {metric: _cross_rank_dict({k: v[metric] for k, v in overheat_raw.items()}) for metric in ("limit_ratio", "money_ratio", "deviation")}
    penalties = {}
    for industry in raw:
        signals = sum(heat_ranks[x].get(industry, 0) >= 90 for x in heat_ranks)
        penalties[industry] = 10.0 if signals == 3 else (5.0 if signals == 2 else 0.0)
    return scores, penalties, {
        "available": True, "sample": len(sample), "frames": len(frames) - 1,
        "details": raw,
    }



def _combine_mainline_scores(
    asof, fund_scores, diffusion, capacity, penalties, industry_map,
    fund_age_days=0, capacity_details=None,
):
    capacity_details = capacity_details or {}
    fund_is_fresh = bool(fund_scores) and fund_age_days <= g.mainline_max_fund_age_days
    decay = 1.0
    if fund_is_fresh and bool(getattr(g, "fund_age_decay_enabled", False)):
        if fund_age_days <= 90:
            decay = 1.00
        elif fund_age_days <= 120:
            decay = 0.75
        elif fund_age_days <= 150:
            decay = 0.50
        else:
            decay = 0.25
    if fund_is_fresh:
        industries = sorted(set(fund_scores) & set(capacity))
        fund_weight = 0.60 * decay
        diffusion_weight = 0.10 * decay
        capacity_weight = 1.0 - fund_weight - diffusion_weight
    else:
        industries = sorted(set(capacity))
        fund_weight = 0.0
        capacity_weight = 1.0
        diffusion_weight = 0.0
    rows = []
    for industry in industries:
        fund_score = fund_scores.get(industry, np.nan)
        diffusion_score = diffusion.get(industry, np.nan)
        score = capacity_weight * capacity[industry]
        if fund_is_fresh:
            score += fund_weight * fund_score + diffusion_weight * diffusion_score
        detail = capacity_details.get(industry, {})
        confirmation_signals = sum([
            bool(np.isfinite(detail.get("relative_strength", np.nan)) and detail.get("relative_strength") > 0),
            bool(np.isfinite(detail.get("breadth", np.nan)) and detail.get("breadth") >= 0.55),
            bool(np.isfinite(detail.get("persistence", np.nan)) and detail.get("persistence") > 0),
            bool(np.isfinite(detail.get("share_momentum", np.nan)) and detail.get("share_momentum") > 0),
        ])
        price_confirmed = bool(capacity[industry] >= 50.0 and confirmation_signals >= 2)
        fund_prior_pass = bool(
            fund_is_fresh and np.isfinite(fund_score) and fund_score >= 45.0
        )
        rows.append({
            "industry": industry,
            "score": float(score),
            "fund": fund_score,
            "capacity": capacity[industry],
            "diffusion": diffusion_score,
            "heat_watch": penalties.get(industry, 0.0),
            "fund_prior_pass": fund_prior_pass,
            "price_confirmed": price_confirmed,
            "confirmation_signals": int(confirmation_signals),
            "fund_weight": float(fund_weight),
            "capacity_weight": float(capacity_weight),
            "diffusion_weight": float(diffusion_weight),
            "fund_age_decay": float(decay),
            "relative_strength": detail.get("relative_strength", np.nan),
            "breadth": detail.get("breadth", np.nan),
            "persistence": detail.get("persistence", np.nan),
            "share_momentum": detail.get("share_momentum", np.nan),
        })
    rows.sort(key=lambda x: x["score"], reverse=True)
    states = {}
    for rank, row in enumerate(rows, 1):
        industry = row["industry"]
        evidence_pass = bool(row["fund_prior_pass"] and row["price_confirmed"])
        raw_core = bool(
            evidence_pass and rank <= g.mainline_core_count
            and row["score"] >= g.mainline_core_score
        )
        raw_candidate = bool(
            evidence_pass and rank <= g.mainline_candidate_count
            and row["score"] >= g.mainline_candidate_score
        )
        if raw_core:
            g.industry_confirm_counts[industry] = g.industry_confirm_counts.get(industry, 0) + 1
        elif raw_candidate:
            g.industry_confirm_counts[industry] = max(1, g.industry_confirm_counts.get(industry, 0))
        else:
            g.industry_confirm_counts[industry] = 0
        if raw_core and g.industry_confirm_counts[industry] >= g.mainline_confirm_months:
            state = "core"
        elif raw_candidate:
            state = "candidate"
        elif row["score"] >= g.mainline_observe_score:
            state = "observe"
        else:
            state = "weak"
        states[industry] = state
        row["rank"] = rank
        row["state"] = state
        row["name"] = next((v[1] for v in industry_map.values() if v[0] == industry), industry)
    g.industry_states = states
    g.latest_industry_scores = {row["industry"]: row for row in rows}
    return rows




def _institution_response_actionable():
    return bool(
        getattr(g, "mainline_enabled", False)
        and getattr(g, "institution_fail_closed", True)
        and getattr(g, "latest_mainline_mode", None)
        in tuple(getattr(g, "institution_actionable_modes", ("FUND_PRICE_CONFIRMED",)))
        and bool(getattr(g, "latest_mainline_meta", {}).get("actionable", False))
    )


def _close_institution_gate(mode, reason, members, fund_meta=None, capacity_meta=None):
    """机构证据不完整时清空可行动状态；价格容量绝不单独生成响应交易。"""
    g.industry_confirm_counts = {}
    g.industry_states = {}
    g.latest_industry_scores = {}
    g.latest_industry_members = members
    g.latest_mainline_mode = str(mode)
    capacity_summary = {
        key: value for key, value in dict(capacity_meta or {}).items()
        if key != "details"
    }
    meta = {
        "actionable": False,
        "mode": str(mode),
        "reason": str(reason),
        "fund": dict(fund_meta or {}),
        "capacity": capacity_summary,
        "mainline_count": 0,
    }
    g.latest_mainline_meta = meta
    g.mainline_deploy_gate = {
        "available": False,
        "passed": False,
        "reason": str(reason),
        "mode": str(mode),
    }
    log.info(
        "%s_INSTITUTION_GATE|%s" % (
            str(getattr(g, "experiment_log_tag", "V18_EXPERIMENT")),
            json.dumps(meta, ensure_ascii=False, sort_keys=True, default=str),
        )
    )
    return [], members, str(mode), meta


def _promote_existing_core_responses(targets, response_pool, effective_core_target):
    """不交易地把已持有且满足全部响应门槛的核心逐月晋升为response。"""
    g.response_role_promotions_this_month = 0
    if not _institution_response_actionable():
        return 0
    response_count = sum(g.holding_roles.get(code) == "response" for code in targets)
    core_count = sum(g.holding_roles.get(code) == "core" for code in targets)
    available_slots = max(0, int(g.max_response_slots) - response_count)
    promotable_core_surplus = max(0, core_count - int(effective_core_target))
    limit = min(
        available_slots,
        promotable_core_surplus,
        int(getattr(g, "max_response_role_promotions_per_month", 1)),
    )
    if limit <= 0:
        return 0
    pool_set = set(response_pool)
    candidates = [
        code for code in targets
        if g.holding_roles.get(code) == "core" and code in pool_set
    ]
    def _descending_score(code, key):
        value = g.pending_scores.get(code, {}).get(key, np.nan)
        try:
            return -float(value) if np.isfinite(value) else np.inf
        except Exception:
            return np.inf

    candidates.sort(
        key=lambda code: (
            _descending_score(code, "mainline_score"),
            _descending_score(code, "total"),
            code,
        )
    )
    promoted = 0
    for code in candidates[:limit]:
        g.holding_roles[code] = "response"
        if bool(getattr(g, "response_probation_enabled", False)):
            g.response_probation_states[str(code)] = {
                "start_month": str(getattr(g, "last_rebalance_month", "unknown")),
                "status": "validated",
                "source": "core_promotion",
                "last_month": str(getattr(g, "last_rebalance_month", "unknown")),
                "last_relative_20d": None,
                "last_passed": True,
            }
        promoted += 1
        log.info(
            "响应角色晋升：%s已持有且机构核心主线连续确认，core→response；不产生交易。"
            % _stock_label(code)
        )
    g.response_role_promotions_this_month = int(promoted)
    return int(promoted)

def build_institutional_mainline(asof, fundamentals, industry_map):
    members = {}
    for code in fundamentals["code"].astype(str):
        industry = industry_map.get(code, ("UNKNOWN:%s" % code, "未知行业"))[0]
        if not industry.startswith("UNKNOWN:"):
            members.setdefault(industry, []).append(code)
    g.latest_industry_members = members
    if not getattr(g, "mainline_enabled", False):
        return _close_institution_gate(
            "CORE_BASELINE_DISABLED", "institution module disabled", members
        )

    # 先验证机构季度数据。失败时不再继续计算容量，更不允许容量单独成为信号。
    fund_scores, diffusion, fund_meta = _calc_fund_industry_scores(
        asof, industry_map, fundamentals
    )
    if not bool(fund_meta.get("available", False)) or not fund_scores:
        return _close_institution_gate(
            "CORE_BASELINE_NO_VALID_FUND",
            fund_meta.get("reason", "fund evidence unavailable"),
            members,
            fund_meta=fund_meta,
        )
    fund_age = int(fund_meta.get("current_period_age_days", 10 ** 9))
    if fund_age > int(g.mainline_max_fund_age_days):
        return _close_institution_gate(
            "CORE_BASELINE_STALE_FUND",
            "fund period age %d exceeds %d days"
            % (fund_age, g.mainline_max_fund_age_days),
            members,
            fund_meta=fund_meta,
        )

    capacity, penalties, capacity_meta = _calc_capacity_scores(
        asof, members, fundamentals
    )
    if not capacity_meta.get("available", False) or not capacity:
        return _close_institution_gate(
            "CORE_BASELINE_NO_CAPACITY_CONFIRM",
            capacity_meta.get("reason", "capacity confirmation unavailable"),
            members,
            fund_meta=fund_meta,
            capacity_meta=capacity_meta,
        )

    rows = _combine_mainline_scores(
        asof,
        fund_scores,
        diffusion,
        capacity,
        penalties,
        industry_map,
        fund_age_days=fund_age,
        capacity_details=capacity_meta.get("details", {}),
    )

    def _mainline_number(value):
        return "NA" if not np.isfinite(value) else "%.1f" % value

    for row in rows[:10]:
        log.info(
            "主线%02d｜%s｜总分=%.1f｜基金=%s｜容量=%.1f｜扩散=%s｜"
            "价格确认=%s/%d｜过热观察=%.0f｜状态=%s"
            % (
                row["rank"], row["name"], row["score"],
                _mainline_number(row["fund"]), row["capacity"],
                _mainline_number(row["diffusion"]),
                row.get("price_confirmed", False),
                row.get("confirmation_signals", 0),
                row["heat_watch"], row["state"],
            )
        )

    entry = [
        row["industry"] for row in rows
        if row["state"] in ("core", "candidate")
    ]
    if len(entry) < int(g.mainline_min_industries):
        return _close_institution_gate(
            "CORE_BASELINE_INSUFFICIENT_MAINLINES",
            "actionable mainline industries %d below %d"
            % (len(entry), g.mainline_min_industries),
            members,
            fund_meta=fund_meta,
            capacity_meta=capacity_meta,
        )

    mode = "FUND_PRICE_CONFIRMED"
    deploy_gate = _build_mainline_deploy_gate(rows, fund_age)
    g.mainline_deploy_gate = dict(deploy_gate)
    meta = {
        "actionable": True,
        "mode": mode,
        "reason": "ok",
        "fund": dict(fund_meta),
        "capacity": {
            key: value for key, value in dict(capacity_meta).items()
            if key != "details"
        },
        "mainline_count": int(len(entry)),
        "core_industries": int(sum(row["state"] == "core" for row in rows)),
        "candidate_industries": int(sum(row["state"] == "candidate" for row in rows)),
        "deploy_gate": dict(deploy_gate),
        "fund_age_decay": float(rows[0].get("fund_age_decay", 1.0)) if rows else None,
    }
    g.latest_mainline_mode = mode
    g.latest_mainline_meta = meta
    g.latest_industry_members = members
    log.info(
        "%s_INSTITUTION_GATE|%s"
        % (
            str(getattr(g, "experiment_log_tag", "V18_EXPERIMENT")),
            json.dumps(meta, ensure_ascii=False, sort_keys=True, default=str),
        )
    )
    return rows, members, mode, meta


def _price50_is_financial_industry(industry_code, industry_name):
    text = "%s|%s" % (str(industry_code or ""), str(industry_name or ""))
    return bool(
        str(industry_code or "") in ("801780", "801790", "801190")
        or _py_builtins.any(
            keyword in text
            for keyword in ("银行", "保险", "证券", "非银金融", "综合金融")
        )
    )


def _price50_financial_gate(scored, industry_map):
    """只做新建证券财报硬门；金融业不误用工业企业现金流和负债率口径。"""
    roe = pd.to_numeric(scored["roe"], errors="coerce")
    roa = pd.to_numeric(scored["roa"], errors="coerce")
    profit_growth = pd.to_numeric(
        scored["inc_net_profit_year_on_year"], errors="coerce"
    )
    common = (
        (roe >= float(getattr(g, "price50_financial_min_roe", 0.0)))
        & (roa >= float(getattr(g, "price50_financial_min_roa", 0.0)))
        & (
            profit_growth
            >= float(getattr(g, "price50_financial_min_profit_growth", -30.0))
        )
    )
    industrial = (
        pd.to_numeric(scored["ocf_assets"], errors="coerce")
        >= float(getattr(g, "price50_financial_min_ocf_assets", 0.0))
    ) & (
        pd.to_numeric(scored["debt_ratio"], errors="coerce")
        <= float(getattr(g, "price50_financial_max_debt_ratio", 0.75))
    )
    financial_sector = scored["code"].astype(str).map(
        lambda code: _price50_is_financial_industry(
            *industry_map.get(code, (None, None))
        )
    )
    gate = common & (financial_sector | industrial)
    return gate.fillna(False), financial_sector.fillna(False)


def build_ranked_candidates(context, asof):
    # 防止本月数据查询失败时误用上月候选。
    g.pending_core_entry_ranked = []
    g.pending_response_entry_ranked = []
    universe = _historical_universe(asof)
    holdings = _actual_holdings(context)
    g.latest_holding_health = load_holding_health(asof, holdings)
    fundamentals = load_fundamentals(asof, universe)
    diagnostics = {
        "universe": len(universe),
        "fundamental_valid": len(fundamentals),
        "holding_health_valid": len(g.latest_holding_health),
    }
    if fundamentals.empty:
        _close_institution_gate(
            "CORE_BASELINE_NO_FUNDAMENTALS",
            "fundamental research data unavailable",
            {},
        )
        diagnostics["mainline_mode"] = g.latest_mainline_mode
        diagnostics["institution_actionable"] = False
        return [], [], {}, diagnostics
    industry_map = _build_industry_map(fundamentals["code"].astype(str).tolist(), asof)
    mainline_rows, industry_members, mainline_mode, mainline_meta = build_institutional_mainline(
        asof, fundamentals, industry_map
    )
    diagnostics["mainline_mode"] = mainline_mode
    diagnostics["mainline_meta"] = mainline_meta
    industry_state = {row["industry"]: row["state"] for row in mainline_rows}
    entry_industries = set(
        row["industry"] for row in mainline_rows if row["state"] in ("core", "candidate")
    )
    diagnostics["entry_industries"] = len(entry_industries)

    baseline_codes = fundamentals.head(g.fundamental_pool_size)["code"].astype(str).tolist()
    institution_actionable = bool(
        mainline_mode in tuple(g.institution_actionable_modes)
        and mainline_meta.get("actionable", False)
    )
    diagnostics["institution_actionable"] = institution_actionable
    if not institution_actionable:
        entry_universe = baseline_codes
    else:
        entry_universe = [
            code for code in fundamentals["code"].astype(str)
            if industry_map.get(code, (None, None))[0] in entry_industries
        ]
    research_codes = list(dict.fromkeys(entry_universe + baseline_codes))
    for code in holdings:
        if code in set(fundamentals["code"].astype(str)) and code not in research_codes:
            research_codes.append(code)
    diagnostics["research_pool"] = len(research_codes)

    price = score_price_risk(research_codes, asof)
    diagnostics["price_valid"] = len(price)
    if price.empty:
        _close_institution_gate(
            "CORE_BASELINE_NO_PRICE_RESEARCH",
            "price-risk research data unavailable",
            industry_members,
            fund_meta=mainline_meta.get("fund", {}),
            capacity_meta=mainline_meta.get("capacity", {}),
        )
        diagnostics["mainline_mode"] = g.latest_mainline_mode
        diagnostics["institution_actionable"] = False
        return [], [], {}, diagnostics
    scored = fundamentals.merge(price, on="code", how="inner")
    if scored.empty:
        _close_institution_gate(
            "CORE_BASELINE_EMPTY_RESEARCH_MERGE",
            "fundamental and price research merge empty",
            industry_members,
            fund_meta=mainline_meta.get("fund", {}),
            capacity_meta=mainline_meta.get("capacity", {}),
        )
        diagnostics["mainline_mode"] = g.latest_mainline_mode
        diagnostics["institution_actionable"] = False
        return [], [], {}, diagnostics

    # PRICE50只生成新建证券准入标记，不先删行、不改变母版横截面，也不重算
    # 过滤后分位。价格采用决策日可见的不复权收盘价，避免未来公司行为改变
    # 历史5—50元边界；母版前复权last_close仍只用于原收益/趋势研究。
    raw_closes = _load_point_in_time_raw_closes(
        scored["code"].astype(str).tolist(), asof
    )
    scored["point_in_time_close"] = scored["code"].astype(str).map(raw_closes)
    financial_gate, financial_sector = _price50_financial_gate(
        scored, industry_map
    )
    point_close = pd.to_numeric(scored["point_in_time_close"], errors="coerce")
    price_gate = (
        (point_close > float(getattr(g, "price50_min_close_exclusive", 5.0)))
        & (
            point_close
            <= float(getattr(g, "price50_max_close_inclusive", 50.0))
        )
    ).fillna(False)
    market_cap_gate = (
        pd.to_numeric(scored["market_cap"], errors="coerce")
        >= float(getattr(g, "price50_min_market_cap_yi", 30.0))
    ).fillna(False)
    scored["price50_financial_gate"] = financial_gate.astype(bool)
    scored["price50_price_gate"] = price_gate.astype(bool)
    scored["price50_market_cap_gate"] = market_cap_gate.astype(bool)
    scored["price50_entry_gate"] = (
        financial_gate & price_gate & market_cap_gate
    ).astype(bool)
    diagnostics["price50_gate_input"] = int(len(scored))
    diagnostics["price50_raw_close_valid"] = int(point_close.notna().sum())
    diagnostics["price50_raw_close_missing"] = int(point_close.isna().sum())
    diagnostics["price50_raw_close_query_failures"] = int(
        getattr(g, "price50_raw_close_query_failures", 0)
    )
    diagnostics["price50_financial_pass"] = int(financial_gate.sum())
    diagnostics["price50_financial_sector_count"] = int(financial_sector.sum())
    diagnostics["price50_price_pass"] = int(price_gate.sum())
    diagnostics["price50_market_cap_pass"] = int(market_cap_gate.sum())
    diagnostics["price50_entry_pass"] = int(scored["price50_entry_gate"].sum())

    # 在最终可研究横截面内统一重排，避免把不同候选池的分位数直接混合。
    scored["quality_rank"] = _rank_high(scored["quality_score"])
    scored["value_rank"] = _rank_high(scored["value_score"])
    scored["safety_rank"] = _rank_high(scored["safety_score"])
    scored["size_rank"] = _rank_high(scored["market_cap"])
    scored["total_score"] = (
        0.40 * scored["quality_rank"]
        + 0.30 * scored["safety_rank"]
        + 0.25 * scored["value_rank"]
        + 0.05 * scored["size_rank"]
    )
    scored["total_rank"] = _rank_high(scored["total_score"])
    scored.sort_values("total_score", ascending=False, inplace=True)

    # V18E1研究版核心层仍研究全市场优质基本面池。周线新买入通过两条路径：
    # EXPMA5站上20，或BOLL中轨转平向上且价格站回中轨。
    scored_codes = scored["code"].astype(str).tolist()
    trend_codes = list(dict.fromkeys(baseline_codes + entry_universe + holdings))
    trend_passed, trend_map = filter_weekly_trend(trend_codes, asof)
    diagnostics["weekly_data_valid"] = len(trend_map)
    diagnostics["trend_fast_above_slow"] = sum(
        1 for item in trend_map.values() if item.get("fast_above_slow", False)
    )
    diagnostics["trend_angle_pass"] = sum(
        1 for item in trend_map.values() if item.get("fast_angle_pass", False)
    )
    diagnostics["trend_boll_direction_pass"] = sum(
        1 for item in trend_map.values() if item.get("boll_direction_pass", False)
    )
    diagnostics["trend_boll_recovery_pass"] = sum(
        1 for item in trend_map.values() if item.get("boll_recovery_pass", False)
    )
    diagnostics["weekly_trend_pass"] = len(trend_passed)
    passed_set = set(trend_passed)

    # 只对可能进入Top50、严格趋势候选和现有持仓读取多年年报，控制聚宽查询量。
    preliminary_top = scored.head(g.normalized_earnings_top_count)["code"].astype(str).tolist()
    normalization_codes = list(dict.fromkeys(preliminary_top + trend_passed + holdings))
    normalized = load_normalized_earnings(asof, normalization_codes, fundamentals)
    diagnostics["normalized_requested"] = len(normalization_codes)
    diagnostics["normalized_valid"] = len(normalized)
    if normalized.empty:
        scored["earnings_years"] = np.nan
        scored["positive_year_ratio"] = np.nan
        scored["normalized_profit"] = np.nan
        scored["normalized_pe"] = np.nan
        scored["profit_peak_ratio"] = np.nan
        scored["normalized_earnings_pass"] = False
        log.warning("本月常态利润数据全部不可用：保留已有持仓，但禁止未经验证的新买入。")
    else:
        scored = scored.merge(normalized, on="code", how="left")
        scored["normalized_earnings_pass"] = (
            scored["normalized_earnings_pass"].fillna(False).astype(bool)
        )
    diagnostics["normalized_entry_pass"] = int(
        scored["normalized_earnings_pass"].fillna(False).sum()
    )

    buffett_top = scored.head(g.weekly_candidate_count).copy()
    top_codes = buffett_top["code"].astype(str).tolist()
    diagnostics["buffett_top50"] = len(top_codes)
    if bool(getattr(g, "price50_entry_enabled", True)):
        price50_entry_mask = scored["price50_entry_gate"].fillna(False)
    else:
        price50_entry_mask = pd.Series(True, index=scored.index)
    strict_scored = scored[
        scored["code"].astype(str).isin(passed_set)
        & scored["code"].astype(str).isin(set(baseline_codes))
        & (scored["quality_rank"] >= g.entry_min_quality_rank)
        & (scored["safety_rank"] >= g.entry_min_safety_rank)
        & (scored["value_rank"] >= g.entry_min_value_rank)
        & (scored["total_rank"] >= g.entry_min_total_rank)
        & (scored["beta"] <= g.entry_max_beta)
        & scored["normalized_earnings_pass"].fillna(False)
        & price50_entry_mask
    ].copy()
    strict_scored["industry_state"] = strict_scored["code"].astype(str).map(
        lambda x: industry_state.get(industry_map.get(x, (None, None))[0], "baseline")
    )
    core_scored = strict_scored.sort_values(
        ["total_score", "quality_rank", "safety_rank"],
        ascending=[False, False, False],
    ).copy()
    if g.max_response_slots <= 0 or not institution_actionable:
        response_scored = strict_scored.iloc[0:0].copy()
    else:
        response_scored = strict_scored[
            strict_scored["code"].astype(str).isin(set(entry_universe))
            & (strict_scored["industry_state"] == "core")
        ].copy()
        response_scored["mainline_score"] = response_scored["code"].astype(str).map(
            lambda x: g.latest_industry_scores.get(
                industry_map.get(x, (None, None))[0], {}
            ).get("score", np.nan)
        )
        response_scored.sort_values(
            ["mainline_score", "total_score", "quality_rank"],
            ascending=[False, False, False],
            inplace=True,
        )
    diagnostics["quality_entry_pass"] = len(strict_scored)
    diagnostics["core_entry_pass"] = len(core_scored)
    diagnostics["response_entry_pass"] = len(response_scored)

    # 可负担性按单股允许的最高核心权重判断，而不是永久按8席位的11.5%判断。
    slot_value = context.portfolio.total_value * _dynamic_single_weight_cap(context)
    current_data = get_current_data()
    buffett_ranked = top_codes
    entry_ranked = []
    core_entry_ranked = []
    response_entry_ranked = []
    score_map = {}
    relevant_codes = set(
        top_codes + holdings + core_scored["code"].astype(str).tolist()
        + response_scored["code"].astype(str).tolist()
    )
    lock_check_codes = sorted(
        set(g.fundamental_exit_report_locks.keys()) & set(relevant_codes)
    )
    g.latest_fundamental_lock_health = (
        load_holding_health(asof, lock_check_codes) if lock_check_codes else {}
    )
    fundamental_lock_blocked = {}
    for locked_code in lock_check_codes:
        current_report = g.latest_fundamental_lock_health.get(locked_code, {}).get("report_date")
        fundamental_lock_blocked[locked_code] = _is_fundamental_report_locked(
            locked_code, current_report, release_if_new=True
        )
    relevant_scored = scored[scored["code"].astype(str).isin(relevant_codes)]
    for _, row in relevant_scored.iterrows():
        code = str(row["code"])
        risk_reentry_blocked = _is_reentry_blocked(code, context.current_dt.date())
        trend = trend_map.get(code, {})
        industry_code, industry_name = industry_map.get(
            code, ("UNKNOWN:%s" % code, "未知行业")
        )
        score_map[code] = {
            "total": float(row["total_score"]),
            "total_rank": float(row["total_rank"]),
            "quality": float(row["quality_rank"]),
            "safety": float(row["safety_rank"]),
            "value": float(row["value_rank"]),
            "pe_ratio": float(row["pe_ratio"]),
            "pb_ratio": float(row["pb_ratio"]),
            "net_profit": float(row["net_profit"]),
            "adjusted_profit": float(row["adjusted_profit"]),
            "roe": float(row["roe"]),
            "roa": float(row["roa"]),
            "revenue_growth": float(row["inc_revenue_year_on_year"]),
            "profit_growth": float(row["inc_net_profit_year_on_year"]),
            "earnings_years": float(row.get("earnings_years", np.nan)),
            "positive_year_ratio": float(row.get("positive_year_ratio", np.nan)),
            "normalized_profit": float(row.get("normalized_profit", np.nan)),
            "normalized_pe": float(row.get("normalized_pe", np.nan)),
            "profit_peak_ratio": float(row.get("profit_peak_ratio", np.nan)),
            "normalized_earnings_pass": bool(row.get("normalized_earnings_pass", False)),
            "beta": float(row["beta"]),
            "last_close": float(row["last_close"]),
            "point_in_time_close": float(
                row.get("point_in_time_close", np.nan)
            ),
            "market_cap": float(row.get("market_cap", np.nan)),
            "price50_financial_gate": bool(
                row.get("price50_financial_gate", False)
            ),
            "price50_price_gate": bool(row.get("price50_price_gate", False)),
            "price50_market_cap_gate": bool(
                row.get("price50_market_cap_gate", False)
            ),
            "price50_entry_gate": bool(row.get("price50_entry_gate", False)),
            "trend_data_valid": bool(trend),
            "weekly_trend_pass": bool(trend.get("passed", False)),
            "weekly_strict_trend_pass": bool(trend.get("strict_pass", False)),
            "severe_trend": bool(trend.get("severe", False)),
            "ema5w": trend.get("ema5w", np.nan),
            "ema20w": trend.get("ema20w", np.nan),
            "ema5_angle": trend.get("ema5_angle", np.nan),
            "ema5_weekly_rate": trend.get("ema5_weekly_rate", np.nan),
            "boll_mid": trend.get("boll_mid", np.nan),
            "boll_mid_angle": trend.get("boll_mid_angle", np.nan),
            "close_above_boll": bool(trend.get("close_above_boll", False)),
            "boll_recovery_pass": bool(trend.get("boll_recovery_pass", False)),
            "risk_reentry_blocked": bool(risk_reentry_blocked),
            "fundamental_report_locked": bool(fundamental_lock_blocked.get(code, False)),
            "reentry_blocked": bool(
                risk_reentry_blocked or fundamental_lock_blocked.get(code, False)
            ),
            "industry_code": industry_code,
            "industry_name": industry_name,
            "industry_state": industry_state.get(industry_code, "baseline"),
            "institution_actionable": bool(institution_actionable),
            "mainline_score": g.latest_industry_scores.get(industry_code, {}).get("score", np.nan),
        }

    # 亏损或PE为负的旧持仓不会进入横截面评分，但仍必须进入持仓健康检查，
    # 否则恰恰在最需要退出时会因为“没有排名数据”而被遗漏。
    for code in holdings:
        if code in score_map:
            score_map[code]["holding_health"] = g.latest_holding_health.get(code, {})
            continue
        industry_code, industry_name = industry_map.get(
            code, _get_sw1_industry(code, asof)
        )
        health = g.latest_holding_health.get(code, {})
        score_map[code] = {
            "total": np.nan,
            "total_rank": np.nan,
            "quality": np.nan,
            "safety": np.nan,
            "value": np.nan,
            "pe_ratio": np.nan,
            "pb_ratio": np.nan,
            "weekly_trend_pass": False,
            "severe_trend": False,
            "industry_code": industry_code,
            "industry_name": industry_name,
            "industry_state": industry_state.get(industry_code, "baseline"),
            "holding_health": health,
        }

    def append_affordable(rows, output):
        for _, row in rows.iterrows():
            if len(output) >= g.entry_rank_limit:
                break
            code = str(row["code"])
            if fundamental_lock_blocked.get(code, False):
                lock = g.fundamental_exit_report_locks.get(code, {})
                current_report = g.latest_fundamental_lock_health.get(code, {}).get("report_date")
                log.info(
                    "财报版本锁跳过 %s：退出报告=%s，当前报告=%s；等待新报告披露。"
                    % (
                        _stock_label(code),
                        lock.get("report_date") if isinstance(lock, dict) else lock,
                        current_report or "数据暂缺",
                    )
                )
                continue
            if _is_reentry_blocked(code, context.current_dt.date()):
                log.info(
                    "冷静期跳过 %s：风险退出后本月禁止重新买入。"
                    % _stock_label(code)
                )
                continue
            if not _is_trade_eligible(code, current_data, for_buy=True):
                continue
            if code not in holdings:
                entry_price = float(row.get("point_in_time_close", np.nan))
                if not np.isfinite(entry_price) or entry_price <= 0:
                    continue
                one_lot_value = entry_price * 100.0
                if one_lot_value > slot_value * g.max_lot_to_target_ratio:
                    continue
            output.append(code)

    append_affordable(core_scored, core_entry_ranked)
    append_affordable(response_scored, response_entry_ranked)
    entry_ranked = list(dict.fromkeys(core_entry_ranked + response_entry_ranked))
    g.pending_core_entry_ranked = core_entry_ranked
    g.pending_response_entry_ranked = response_entry_ranked
    diagnostics["affordable_core"] = len(core_entry_ranked)
    diagnostics["affordable_response"] = len(response_entry_ranked)
    diagnostics["affordable"] = len(entry_ranked)
    return buffett_ranked, entry_ranked, score_map, diagnostics


def log_month_end_top50(asof, buffett_ranked, score_map):
    """逐条记录Buffett研究排名前50；排名仅供观察，不触发持仓卖出。"""
    log.info(
        "========== Buffett全市场观察排名前50（不触发卖出）｜数据截止 %s｜共%d只 =========="
        % (str(asof), len(buffett_ranked))
    )
    for rank, code in enumerate(buffett_ranked, 1):
        item = score_map.get(code, {})
        if not item.get("trend_data_valid", False):
            trend_text = "周线数据不足"
        elif item.get("severe_trend", False):
            trend_text = "核心趋势否决：明确长期下跌(EMA5角度=%.1f度/BOLL中轨角度=%+.1f度)" % (
                item.get("ema5_angle", np.nan),
                item.get("boll_mid_angle", np.nan),
            )
        elif not item.get("weekly_trend_pass", False):
            trend_text = "核心趋势否决：过渡区未通过(EMA5角度=%.1f度/BOLL中轨角度=%+.1f度)" % (
                item.get("ema5_angle", np.nan),
                item.get("boll_mid_angle", np.nan),
            )
        else:
            strict_text = "严格趋势通过" if item.get("weekly_strict_trend_pass", False) else "严格趋势未通过"
            trend_text = "核心趋势允许/%s(EMA5角度=%.1f度/BOLL中轨角度=%+.1f度)" % (
                strict_text,
                item.get("ema5_angle", np.nan),
                item.get("boll_mid_angle", np.nan),
            )
        if item.get("risk_reentry_blocked", False):
            trend_text += "｜风险退出冷静期中"
        if item.get("fundamental_report_locked", False):
            trend_text += "｜财报退出版本锁中"
        normalized_pe = item.get("normalized_pe", np.nan)
        peak_ratio = item.get("profit_peak_ratio", np.nan)
        earnings_years = item.get("earnings_years", np.nan)
        normalized_text = "常态利润不足"
        if np.isfinite(normalized_pe) and np.isfinite(peak_ratio):
            normalized_text = "常态PE=%.1f/峰值倍数=%.2f/年数=%d/%s" % (
                normalized_pe,
                peak_ratio,
                int(earnings_years) if np.isfinite(earnings_years) else 0,
                "通过" if item.get("normalized_earnings_pass", False) else "未通过",
            )
        log.info(
            "月末排名%02d｜%s｜行业=%s｜总分=%.3f｜质量=%.3f｜安全=%.3f｜"
            "价值=%.3f｜Beta=%.3f｜%s｜%s"
            % (
                rank,
                _stock_label(code),
                item.get("industry_name", "未知行业"),
                item.get("total", np.nan),
                item.get("quality", np.nan),
                item.get("safety", np.nan),
                item.get("value", np.nan),
                item.get("beta", np.nan),
                trend_text,
                normalized_text,
            )
        )
    log.info("========== Buffett月末排名结束 ==========")


def _is_extreme_valuation(item, baseline):
    """只识别极端估值透支；从便宜变为合理只停止加仓，不触发卖出。"""
    pe = item.get("pe_ratio", np.nan)
    pb = item.get("pb_ratio", np.nan)
    growth = item.get("profit_growth", np.nan)
    entry_pe = baseline.get("entry_pe", np.nan)
    entry_pb = baseline.get("entry_pb", np.nan)
    if not np.isfinite(pe) or pe <= 0:
        return False
    weak_growth = not np.isfinite(growth) or growth <= 15.0
    absolute_extreme = pe >= 60.0 or (pe >= 50.0 and np.isfinite(pb) and pb >= 5.0)
    relative_extreme = (
        np.isfinite(entry_pe) and entry_pe > 0 and pe >= max(40.0, entry_pe * 1.80)
        and np.isfinite(entry_pb) and entry_pb > 0 and np.isfinite(pb)
        and pb >= max(4.0, entry_pb * 1.50)
    )
    return bool(weak_growth and (absolute_extreme or relative_extreme))


def _evaluate_holding_exit(code, month_key):
    item = g.pending_scores.get(code, {})
    health = g.latest_holding_health.get(code, {})
    baseline = g.holding_fundamental_baselines.setdefault(
        code,
        {
            "entry_pe": item.get("pe_ratio", np.nan),
            "entry_pb": item.get("pb_ratio", np.nan),
        },
    )

    if health.get("loss_making", False):
        g.holding_thesis_states[code] = "EXIT"
        g.pending_fundamental_exit_reports[code] = health.get("report_date")
        return "最新财报净利润或扣非净利润转为亏损"

    beta = item.get("beta", np.nan)
    safety = item.get("safety", np.nan)
    if np.isfinite(beta) and beta > g.immediate_beta_exit and (
        not np.isfinite(safety) or safety < 0.20
    ):
        g.holding_thesis_states[code] = "EXIT"
        return "Beta %.2f超过%.2f且安全分位严重恶化" % (beta, g.immediate_beta_exit)

    report_state = g.holding_report_states.setdefault(
        code,
        {
            "entry_report": None,
            "last_report": None,
            "entry_date": None,
            "bad_report_count": 0,
        },
    )
    report_date = health.get("report_date")
    if report_date and not report_state.get("last_report"):
        # 兼容从旧版本启动时已经存在的持仓：第一次看到的报告只登记为基准，
        # 不把买入前已经披露的信息误当成“持有后的新恶化”。
        report_state["entry_report"] = report_date
        report_state["last_report"] = report_date
        baseline.update(_health_baseline_snapshot(health))
        log.info(
            "财报基准登记 %s：买入时/首次接管已披露报告=%s，ROE=%s，ROA=%s，"
            "负债率=%s，经营现金流/资产=%s；仅检查其后的新报告。"
            % (
                _stock_label(code), report_date,
                "%.2f" % health.get("roe") if np.isfinite(health.get("roe", np.nan)) else "缺失",
                "%.2f" % health.get("roa") if np.isfinite(health.get("roa", np.nan)) else "缺失",
                "%.3f" % health.get("debt_ratio") if np.isfinite(health.get("debt_ratio", np.nan)) else "缺失",
                "%.3f" % health.get("ocf_assets") if np.isfinite(health.get("ocf_assets", np.nan)) else "缺失",
            )
        )
    elif report_date and report_date != report_state.get("last_report"):
        previous_report = report_state.get("last_report")
        report_state["last_report"] = report_date
        entry_hard, entry_soft = _compare_new_report_to_entry(health, baseline)
        yoy_signals = list(health.get("deterioration_signals", []))
        merged_soft = _merge_fundamental_soft_signals(yoy_signals, entry_soft)
        merged_soft_text = _format_merged_fundamental_signals(merged_soft)
        deterioration_confirmed = bool(
            entry_hard
            or len(merged_soft) >= g.fundamental_soft_signals_required
        )
        if deterioration_confirmed:
            report_state["bad_report_count"] = int(
                report_state.get("bad_report_count", 0)
            ) + 1
        else:
            report_state["bad_report_count"] = 0
        if report_state["bad_report_count"] >= g.fundamental_bad_reports_required:
            g.holding_thesis_states[code] = "EXIT"
            g.pending_fundamental_exit_reports[code] = report_date
            all_signals = list(dict.fromkeys(entry_hard + merged_soft_text))
            return (
                "持有后新财报%s出现实质性恶化（上一已检查报告%s，"
                "合并独立软维度%d/%d，连续坏报告%d/%d）：%s"
                % (
                    report_date, previous_report, len(merged_soft),
                    g.fundamental_soft_signals_required,
                    report_state["bad_report_count"], g.fundamental_bad_reports_required,
                    "、".join(all_signals),
                )
            )
        log.info(
            "持仓新财报通过 %s：%s → %s；同比软信号=%s，买入基准硬/软信号=%s/%s，"
            "合并独立软维度=%d/%d。"
            % (
                _stock_label(code), previous_report, report_date,
                yoy_signals or "无", entry_hard or "无", entry_soft or "无",
                len(merged_soft), g.fundamental_soft_signals_required,
            )
        )

    extreme = _is_extreme_valuation(item, baseline)
    valuation_state = g.valuation_extreme_counts.setdefault(
        code, {"last_month": None, "count": 0}
    )
    if valuation_state.get("last_month") != month_key:
        valuation_state["last_month"] = month_key
        valuation_state["count"] = valuation_state.get("count", 0) + 1 if extreme else 0
    if valuation_state.get("count", 0) >= g.valuation_extreme_months:
        g.holding_thesis_states[code] = "EXIT"
        return "估值连续%d个月极端透支且利润增长不足" % valuation_state["count"]

    # 因子暴露按月复核。缺失值不作为失败证据，防止数据短暂缺失造成误卖。
    factor_reasons = []
    quality = item.get("quality", np.nan)
    value = item.get("value", np.nan)
    total_rank = item.get("total_rank", np.nan)
    pe = item.get("pe_ratio", np.nan)
    entry_pe = baseline.get("entry_pe", np.nan)
    if np.isfinite(quality) and quality < g.hold_min_quality_rank:
        factor_reasons.append("质量分位%.3f<%.2f" % (quality, g.hold_min_quality_rank))
    if np.isfinite(safety) and safety < g.hold_min_safety_rank:
        factor_reasons.append("安全分位%.3f<%.2f" % (safety, g.hold_min_safety_rank))
    if np.isfinite(total_rank) and total_rank < g.hold_min_total_rank:
        factor_reasons.append("综合分位%.3f<%.2f" % (total_rank, g.hold_min_total_rank))
    if np.isfinite(beta) and beta > g.hold_max_beta:
        factor_reasons.append("Beta %.2f>%.2f" % (beta, g.hold_max_beta))
    value_expensive = (
        np.isfinite(value) and value < g.hold_min_value_rank
        and np.isfinite(pe) and pe >= 30.0
        and (
            not np.isfinite(entry_pe) or entry_pe <= 0
            or pe >= entry_pe * 1.50
        )
    )
    if value_expensive:
        factor_reasons.append("价值分位%.3f且估值明显扩张" % value)

    factor_state = g.factor_fail_counts.setdefault(
        code, {"last_month": None, "count": 0}
    )
    if factor_state.get("last_month") != month_key:
        factor_state["last_month"] = month_key
        factor_state["count"] = factor_state.get("count", 0) + 1 if factor_reasons else 0
    g.factor_fail_reasons[code] = factor_reasons
    if factor_state.get("count", 0) >= g.factor_fail_months:
        g.holding_thesis_states[code] = "WATCH"
        log.info(
            "因子观察 %s：连续%d个月%s；横截面排名变化不触发卖出，也不参加高分替换。"
            % (_stock_label(code), factor_state["count"], "、".join(factor_reasons))
        )
        return None

    watch_reasons = []
    if valuation_state.get("count", 0) > 0:
        watch_reasons.append("估值进入极端区观察")
    if factor_reasons:
        watch_reasons.append(
            "核心因子第%d个月跌破持仓缓冲：%s"
            % (factor_state.get("count", 0), "、".join(factor_reasons))
        )
    if watch_reasons:
        g.holding_thesis_states[code] = "WATCH"
        log.info("持仓观察 %s：%s。" % (_stock_label(code), "；".join(watch_reasons)))
    else:
        g.holding_thesis_states[code] = "HEALTHY"
    return None


def _holding_company_qualified(code):
    """判断公司本身是否仍值得持有；主线角色失效不等于公司失效。"""
    if g.holding_thesis_states.get(code) == "EXIT":
        return False
    health = g.latest_holding_health.get(code, {})
    if health.get("loss_making", False) or health.get("deteriorated", False):
        return False
    factor_state = g.factor_fail_counts.get(code, {})
    factor_failed = bool(
        factor_state.get("count", 0) >= g.factor_fail_months
        and g.factor_fail_reasons.get(code)
    )
    return not factor_failed


def _sync_holding_roles(holdings):
    """恢复角色账本；只有完整机构证据下的合格现有持仓才可初始化为response。"""
    holding_set = set(holdings)
    for code in list(g.holding_roles.keys()):
        if code not in holding_set:
            g.holding_roles.pop(code, None)
            g.response_fail_counts.pop(code, None)
            if hasattr(g, "response_probation_states"):
                g.response_probation_states.pop(str(code), None)

    valid_roles = ("core", "response")
    for code in holdings:
        if g.holding_roles.get(code) not in valid_roles:
            g.holding_roles.pop(code, None)

    response_count = sum(g.holding_roles.get(code) == "response" for code in holdings)
    if response_count > g.max_response_slots:
        responses = [code for code in holdings if g.holding_roles.get(code) == "response"]
        responses.sort(
            key=lambda code: g.pending_scores.get(code, {}).get("mainline_score", -np.inf),
            reverse=True,
        )
        for code in responses[g.max_response_slots:]:
            g.holding_roles[code] = "core"
            log.warning("角色账本修复：%s由超额响应迁移为核心。" % _stock_label(code))
        response_count = min(response_count, g.max_response_slots)

    response_eligible = set(getattr(g, "pending_response_entry_ranked", []))
    actionable = _institution_response_actionable()
    unassigned = [code for code in holdings if code not in g.holding_roles]
    unassigned.sort(
        key=lambda code: g.pending_scores.get(code, {}).get("total", -np.inf),
        reverse=True,
    )
    for code in unassigned:
        item = g.pending_scores.get(code, {})
        industry_code = item.get("industry_code")
        current_core_count = sum(
            g.holding_roles.get(item_code) == "core"
            for item_code in holdings if item_code in g.holding_roles
        )
        can_be_response = bool(
            actionable
            and response_count < g.max_response_slots
            and code in response_eligible
            and item.get("industry_state") == "core"
            and g.industry_confirm_counts.get(industry_code, 0) >= g.mainline_confirm_months
            and max(current_core_count, len(holdings) - response_count - 1) >= g.min_core_slots
        )
        if can_be_response:
            g.holding_roles[code] = "response"
            if bool(getattr(g, "response_probation_enabled", False)) and str(code) not in g.response_probation_states:
                g.response_probation_states[str(code)] = {
                    "start_month": str(getattr(g, "last_rebalance_month", "state_recovery")),
                    "status": "validated",
                    "source": "role_state_recovery",
                    "last_month": str(getattr(g, "last_rebalance_month", "state_recovery")),
                    "last_relative_20d": None,
                    "last_passed": True,
                }
            response_count += 1
        else:
            g.holding_roles[code] = "core"
    if unassigned:
        log.info(
            "持仓角色初始化：%s。"
            % ["%s=%s" % (_stock_label(code), g.holding_roles.get(code)) for code in unassigned]
        )


def _initial_build_holding_cap(context, retained_count):
    """按月推进3/5/6只初始建仓；不会为了阶段上限卖掉已有持仓。"""
    if not getattr(g, "initial_build_enabled", False):
        g.initial_build_effective_cap = g.max_holdings
        return g.max_holdings
    if getattr(g, "initial_build_completed", False) or retained_count >= g.min_core_slots:
        if retained_count >= g.min_core_slots:
            g.initial_build_completed = True
        g.initial_build_effective_cap = g.max_holdings
        return g.max_holdings
    month_key = context.current_dt.strftime("%Y-%m")
    if g.initial_build_last_month != month_key:
        g.initial_build_stage = min(
            int(g.initial_build_stage) + 1,
            len(g.initial_build_target_counts),
        )
        g.initial_build_last_month = month_key
    stage_index = max(0, int(g.initial_build_stage) - 1)
    stage_target = int(g.initial_build_target_counts[stage_index])
    effective_cap = min(g.max_holdings, max(int(retained_count), stage_target))
    g.initial_build_effective_cap = effective_cap
    log.info(
        "分阶段初始建仓：阶段%d/%d，本月持仓上限%d只（当前保留%d只）；"
        "达到%d只实际持仓后结束初始阶段。"
        % (
            g.initial_build_stage, len(g.initial_build_target_counts),
            effective_cap, retained_count, g.min_core_slots,
        )
    )
    return effective_cap



def _current_position_weight(context, code):
    total_value = float(context.portfolio.total_value)
    if total_value <= 0 or code not in context.portfolio.positions:
        return 0.0
    value = float(getattr(context.portfolio.positions[code], "value", 0.0))
    return max(0.0, value / total_value)


def _current_holding_return(context, code, current_data):
    if code not in context.portfolio.positions:
        return np.nan
    position = context.portfolio.positions[code]
    avg_cost = float(getattr(position, "avg_cost", np.nan))
    try:
        price = float(current_data[code].last_price)
    except Exception:
        price = np.nan
    if not np.isfinite(price) or not np.isfinite(avg_cost) or avg_cost <= 0:
        return np.nan
    return price / avg_cost - 1.0



def _planned_weight_map(context, codes, current_data=None):
    """按政策仓位、WATCH约束、主线强化与响应试用期估算目标权重。"""
    ordered = []
    seen = set()
    for code in codes:
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    if not ordered:
        return {}, {
            "base_equal_weight": 0.0,
            "healthy": [],
            "factor_watch": [],
            "loss_watch": [],
            "mainline_enhanced": [],
            "response_probation": [],
            "planned_exposure": 0.0,
        }
    if current_data is None:
        current_data = get_current_data()
    dynamic_single_cap = _dynamic_single_weight_cap(context)
    base_equal_weight = min(
        dynamic_single_cap,
        g.current_target_exposure / float(len(ordered)),
    )
    weight_map = {}
    healthy = []
    factor_watch = []
    loss_watch = []
    for code in ordered:
        current_weight = _current_position_weight(context, code)
        thesis_watch = bool(
            code in context.portfolio.positions
            and g.holding_thesis_states.get(code, "HEALTHY") == "WATCH"
        )
        holding_return = _current_holding_return(context, code, current_data)
        price_watch = bool(
            code in context.portfolio.positions
            and np.isfinite(holding_return)
            and holding_return <= g.stop_watch_loss
        )
        if thesis_watch:
            weight_map[code] = min(
                g.watch_max_weight, base_equal_weight, current_weight
            )
            factor_watch.append(code)
        elif price_watch:
            weight_map[code] = min(
                dynamic_single_cap, base_equal_weight, current_weight
            )
            loss_watch.append(code)
        else:
            healthy.append(code)

    fixed_exposure = sum(float(value) for value in weight_map.values())
    remaining = max(0.0, float(g.current_target_exposure) - fixed_exposure)
    enhanced = _select_mainline_enhanced_codes(
        healthy, getattr(g, "effective_allocation_policy", None)
    )
    enhanced_set = set(enhanced)
    probation_codes = []
    factors = {}
    for code in healthy:
        factor = 1.0
        if code in enhanced_set:
            factor *= float(getattr(g, "mainline_enhancement_multiplier", 1.25))
        state = getattr(g, "response_probation_states", {}).get(str(code), {})
        if (
            bool(getattr(g, "response_probation_enabled", False))
            and g.holding_roles.get(code) == "response"
            and isinstance(state, dict)
            and state.get("status", "probation") == "probation"
        ):
            factor *= float(getattr(g, "response_probation_weight_factor", 0.50))
            probation_codes.append(code)
        factors[code] = max(0.0, factor)

    healthy_weights = _weighted_capped_allocation(
        healthy, factors, remaining, dynamic_single_cap
    )
    weight_map.update(healthy_weights)
    planned_exposure = sum(float(value) for value in weight_map.values())
    g.pending_mainline_enhanced_codes = list(enhanced)
    return weight_map, {
        "base_equal_weight": float(base_equal_weight),
        "healthy_weight": (
            float(np.mean(list(healthy_weights.values())))
            if healthy_weights else 0.0
        ),
        "healthy": healthy,
        "factor_watch": factor_watch,
        "loss_watch": loss_watch,
        "mainline_enhanced": list(enhanced),
        "response_probation": list(probation_codes),
        "planned_exposure": float(planned_exposure),
    }



def _weighted_beta_from_weights(weight_map):
    """返回股票仓内部加权Beta与含现金的账户Beta。"""
    beta_value = 0.0
    beta_weight = 0.0
    missing = []
    for code, weight in weight_map.items():
        weight = float(weight)
        if weight <= 0:
            continue
        beta = g.pending_scores.get(code, {}).get("beta", np.nan)
        if not np.isfinite(beta):
            missing.append(code)
            continue
        beta_value += weight * float(beta)
        beta_weight += weight
    equity_beta = beta_value / beta_weight if beta_weight > 0 else np.nan
    account_beta = beta_value if beta_weight > 0 else np.nan
    return float(equity_beta), float(account_beta), missing


def _planned_weighted_beta(context, codes, current_data=None):
    weight_map, meta = _planned_weight_map(context, codes, current_data)
    equity_beta, account_beta, missing = _weighted_beta_from_weights(weight_map)
    return equity_beta, account_beta, weight_map, meta, missing


def _actual_weighted_beta(context, holdings):
    total_value = float(context.portfolio.total_value)
    if total_value <= 0:
        return np.nan, np.nan, []
    weights = {}
    for code in holdings:
        position = context.portfolio.positions.get(code)
        if position is None:
            continue
        value = float(getattr(position, "value", 0.0))
        if value > 0:
            weights[code] = value / total_value
    return _weighted_beta_from_weights(weights)

def build_target_list(context, buffett_ranked, entry_ranked):
    """V18E1研究版：至少6个核心、最多2个fail-closed机构响应席位。"""
    holdings = _actual_holdings(context)
    current_data = get_current_data()
    month_key = context.current_dt.strftime("%Y-%m")
    g.pending_exit_reasons = {}
    g.watch_replacement_count_this_month = 0
    g.response_role_promotions_this_month = 0
    g.response_role_demotions_this_month = 0
    g.response_security_changes_this_month = 0
    g.pending_fundamental_exit_reports = {}
    _sync_holding_roles(holdings)

    def industry_of(code):
        item = g.pending_scores.get(code, {})
        key = item.get("industry_code")
        name = item.get("industry_name")
        if key:
            return str(key), str(name or key)
        return _get_sw1_industry(code, context.previous_date)

    def beta_of(code):
        value = g.pending_scores.get(code, {}).get("beta", np.nan)
        return float(value) if np.isfinite(value) else np.nan

    def weighted_beta(codes):
        equity_beta, _, _, _, _ = _planned_weighted_beta(
            context, codes, current_data
        )
        return equity_beta

    def average_metric(codes, key):
        values = [g.pending_scores.get(code, {}).get(key, np.nan) for code in codes]
        values = [float(value) for value in values if np.isfinite(value)]
        return float(np.mean(values)) if values else np.nan

    def projected_codes(current_codes, candidate, replacing=None):
        result = [code for code in current_codes if code != replacing]
        result.append(candidate)
        return result

    def candidate_allowed(current_codes, candidate, replacing=None):
        if candidate in holdings or candidate in current_codes:
            return False
        remaining = [code for code in current_codes if code != replacing]
        candidate_industry, _ = industry_of(candidate)
        same_industry = sum(industry_of(code)[0] == candidate_industry for code in remaining)
        if same_industry >= g.max_industry_holdings:
            return False
        before = weighted_beta(current_codes)
        after = weighted_beta(projected_codes(current_codes, candidate, replacing))
        if not np.isfinite(after):
            return True
        if np.isfinite(before) and before > g.portfolio_beta_ceiling:
            return after < before
        return after <= g.portfolio_beta_ceiling

    def response_soft_floor():
        policy = getattr(g, "effective_allocation_policy", getattr(g, "liquidity_policy", "warming_up"))
        if policy == "deploy":
            return g.deploy_beta_floor
        if policy == "selective":
            return g.selective_beta_floor
        return None

    def choose_candidate(pool, current_codes, role, replacing=None, beta_repair=False):
        eligible = []
        old_beta = beta_of(replacing) if replacing else np.nan
        for candidate in pool:
            if not candidate_allowed(current_codes, candidate, replacing):
                continue
            item = g.pending_scores.get(candidate, {})
            if role == "response":
                industry_code, _ = industry_of(candidate)
                if item.get("industry_state") != "core":
                    continue
                if g.industry_confirm_counts.get(industry_code, 0) < g.mainline_confirm_months:
                    continue
            candidate_beta = beta_of(candidate)
            if beta_repair and (
                not np.isfinite(candidate_beta) or not np.isfinite(old_beta)
                or candidate_beta > old_beta - 0.15
            ):
                continue
            after = weighted_beta(projected_codes(current_codes, candidate, replacing))
            floor = response_soft_floor() if role == "response" else None
            shortfall = max(0.0, floor - after) if floor is not None and np.isfinite(after) else 0.0
            mainline_score = item.get("mainline_score", np.nan)
            total_score = item.get("total", np.nan)
            eligible.append(
                (
                    shortfall,
                    -float(mainline_score) if np.isfinite(mainline_score) else 0.0,
                    -float(total_score) if np.isfinite(total_score) else 0.0,
                    candidate,
                )
            )
        if not eligible:
            return None
        eligible.sort()
        return eligible[0][-1]

    hard_exit = set()
    for code in holdings:
        reason = _evaluate_holding_exit(code, month_key)
        if reason:
            g.pending_exit_reasons[code] = reason
            hard_exit.add(code)

    retained = [code for code in holdings if code not in hard_exit]
    effective_holding_cap = _initial_build_holding_cap(context, len(retained))
    effective_core_target = min(g.min_core_slots, effective_holding_cap)
    targets = list(retained)
    core_pool = list(getattr(g, "pending_core_entry_ranked", entry_ranked))
    response_pool = list(getattr(g, "pending_response_entry_ranked", []))
    core_pool = _fz2_prioritize_pool(core_pool)
    response_pool = _fz2_prioritize_pool(response_pool)
    if bool(getattr(g, "mainline_alignment_enabled", False)):
        original_rank = {code: index for index, code in enumerate(core_pool)}
        core_pool.sort(
            key=lambda code: _mainline_alignment_sort_key(
                code, original_rank.get(code, 10 ** 9)
            )
        )
    policy_budget = max(0, int(getattr(g, "max_new_buys_this_month", 0)))
    safety_refill = len(hard_exit) if g.extreme_risk_state == "normal" else 0
    retained_core_count = sum(
        g.holding_roles.get(code) == "core" for code in retained
    )
    core_structure_refill = (
        max(0, effective_core_target - retained_core_count)
        if g.extreme_risk_state == "normal" else 0
    )
    # 沿用V1.6.3a的核心变化：所有新证券（初始建仓、财报退出补位、核心结构补位、
    # WATCH替换）都共享流动性政策额度。流动性差时宁可保留现金，也不绕过节奏限制。
    new_security_budget = 0 if g.extreme_risk_state != "normal" else policy_budget
    g.effective_new_buy_budget = new_security_budget
    new_securities_reserved = 0
    response_changes = 0
    if max(safety_refill, core_structure_refill) > new_security_budget:
        log.info(
            "流动性节奏限制补位：安全空位=%d、核心结构缺口=%d，但政策=%s本月最多新增%d只；"
            "剩余空位保留现金，后续月份再补。"
            % (
                safety_refill, core_structure_refill,
                getattr(g, "liquidity_policy", "unknown"), new_security_budget,
            )
        )

    # WATCH替换必须排在安全/核心结构补位之后；额度不足时不进行月度替换。
    mandatory_refill_budget = min(
        new_security_budget, max(safety_refill, core_structure_refill)
    )
    replacement_budget = max(0, new_security_budget - mandatory_refill_budget)
    if (
        g.watch_replacement_enabled
        and getattr(g, "initial_build_completed", False)
        and replacement_budget > 0
    ):
        eligible_watch = []
        for code in list(targets):
            state = g.factor_fail_counts.get(code, {})
            fail_months = int(state.get("count", 0))
            reasons = list(g.factor_fail_reasons.get(code, []))
            item = g.pending_scores.get(code, {})
            quality = item.get("quality", np.nan)
            total_rank = item.get("total_rank", np.nan)
            severe_quality = bool(
                np.isfinite(quality)
                and quality < g.watch_replacement_max_quality_rank
            )
            severe_total = bool(
                np.isfinite(total_rank)
                and total_rank < g.watch_replacement_max_total_rank
            )
            if (
                g.holding_thesis_states.get(code) == "WATCH"
                and fail_months >= g.watch_replacement_min_months
                and reasons
                and (severe_quality or severe_total)
            ):
                quality_sort = float(quality) if np.isfinite(quality) else 1.0
                total_sort = float(total_rank) if np.isfinite(total_rank) else 1.0
                old_score = item.get("total", np.nan)
                eligible_watch.append(
                    (min(quality_sort, total_sort), -fail_months,
                     float(old_score) if np.isfinite(old_score) else np.inf, code)
                )
        eligible_watch.sort()
        for _, _, _, old_code in eligible_watch:
            if (
                g.watch_replacement_count_this_month
                >= g.watch_replacement_max_per_month
                or new_securities_reserved >= replacement_budget
            ):
                break
            old_item = g.pending_scores.get(old_code, {})
            old_score = old_item.get("total", np.nan)
            chosen = choose_candidate(
                core_pool, targets, "core", replacing=old_code
            )
            new_score = (
                g.pending_scores.get(chosen, {}).get("total", np.nan)
                if chosen is not None else np.nan
            )
            score_gap = (
                float(new_score) - float(old_score)
                if np.isfinite(new_score) and np.isfinite(old_score)
                else np.nan
            )
            if chosen is None or not np.isfinite(score_gap) or (
                score_gap < g.watch_replacement_min_score_gap
            ):
                log.info(
                    "WATCH席位暂不替换 %s：连续%d个月失效，但没有同时满足行业、加权Beta约束且总分至少高%.2f的候选。"
                    % (
                        _stock_label(old_code),
                        int(g.factor_fail_counts.get(old_code, {}).get("count", 0)),
                        g.watch_replacement_min_score_gap,
                    )
                )
                continue
            targets.remove(old_code)
            targets.append(chosen)
            g.holding_roles[chosen] = "core"
            fail_months = int(g.factor_fail_counts.get(old_code, {}).get("count", 0))
            reason = (
                "WATCH席位治理：连续%d个月核心因子严重失效，由总分高%.3f的%s替代"
                % (fail_months, score_gap, _stock_label(chosen))
            )
            g.pending_exit_reasons[old_code] = reason
            g.holding_thesis_states[old_code] = "EXIT"
            g.watch_replacement_history[old_code] = {
                "month": month_key,
                "replacement": chosen,
                "watch_months": fail_months,
                "score_gap": float(score_gap),
            }
            g.watch_replacement_count_this_month += 1
            new_securities_reserved += 1
            log.info(
                "WATCH席位替换：%s → %s；连续%d个月失效，总分差=%.3f，本月替换%d/%d。"
                % (
                    _stock_label(old_code), _stock_label(chosen), fail_months,
                    score_gap, g.watch_replacement_count_this_month,
                    g.watch_replacement_max_per_month,
                )
            )

    # 响应角色失效与公司逻辑分开；E4启用后不再仅凭“公司没坏”自动转核心。
    invalid_responses = []
    probation_meta = {}
    for code in retained:
        if g.holding_roles.get(code) != "response":
            continue
        item = g.pending_scores.get(code, {})
        probation_status, probation_state = _update_response_probation(
            code, month_key, context.previous_date
        )
        probation_meta[code] = probation_state
        invalid = item.get("industry_state") not in ("core", "candidate") or bool(
            item.get("severe_trend", False)
        )
        probation_expired = bool(
            g.response_probation_enabled and probation_status == "expired"
        )
        state = g.response_fail_counts.setdefault(code, {"last_month": None, "count": 0})
        if state.get("last_month") != month_key:
            state["last_month"] = month_key
            state["count"] = state.get("count", 0) + 1 if invalid else 0
        role_failed = bool(state.get("count", 0) >= g.response_fail_months)
        if probation_expired or role_failed:
            can_upgrade = (
                _response_independent_core_qualified(code)
                if g.response_probation_enabled else _holding_company_qualified(code)
            )
            if can_upgrade:
                g.holding_roles[code] = "core"
                g.response_fail_counts.pop(code, None)
                if code in g.response_probation_states:
                    g.response_probation_states[code]["status"] = "promoted_core"
                g.response_role_demotions_this_month += 1
                log.info(
                    "角色迁移：%s通过独立Buffett核心准入，response→core；不因主线退潮卖出。"
                    % _stock_label(code)
                )
            else:
                invalid_responses.append(code)
                if probation_expired:
                    log.info(
                        "响应试用到期：%s满%d个月仍未产生合格相对收益，且不能独立进入核心池。"
                        % (_stock_label(code), g.response_probation_max_months)
                    )

    response_old = invalid_responses[0] if invalid_responses else None
    beta_repair = False
    current_beta = weighted_beta(targets)
    if response_old is None and np.isfinite(current_beta) and current_beta > g.portfolio_beta_ceiling:
        response_holdings = [
            code for code in retained if g.holding_roles.get(code) == "response"
            and np.isfinite(beta_of(code))
        ]
        if response_holdings:
            response_old = max(response_holdings, key=beta_of)
            beta_repair = True

    chosen = None
    if (
        response_old is not None
        and new_securities_reserved < new_security_budget
        and response_changes < g.max_response_changes_per_month
    ):
        chosen = choose_candidate(
            response_pool, targets, "response", replacing=response_old,
            beta_repair=beta_repair,
        )
        if chosen is not None and not beta_repair:
            old_total = g.pending_scores.get(response_old, {}).get("total", np.nan)
            new_total = g.pending_scores.get(chosen, {}).get("total", np.nan)
            if (
                not np.isfinite(old_total) or not np.isfinite(new_total)
                or new_total < old_total + g.response_min_upgrade_gap
            ):
                log.info(
                    "响应替换取消：%s相对%s的Buffett总分优势不足%.2f。"
                    % (_stock_label(chosen), _stock_label(response_old), g.response_min_upgrade_gap)
                )
                chosen = None

    if response_old is not None and chosen is not None:
        targets.remove(response_old)
        targets.append(chosen)
        g.holding_roles[chosen] = "response"
        _start_response_probation(chosen, month_key, "replacement")
        g.pending_exit_reasons[response_old] = (
            "响应层连续失效，由已确认主线%s替代" % _stock_label(chosen)
            if not beta_repair else
            "组合Beta %.3f超过%.2f，仅用响应席位的更低Beta候选%s修复"
            % (current_beta, g.portfolio_beta_ceiling, _stock_label(chosen))
        )
        g.holding_thesis_states[response_old] = "EXIT"
        new_securities_reserved += 1
        response_changes += 1
        log.info(
            "响应席位调整：%s → %s；原因=%s。"
            % (
                _stock_label(response_old), _stock_label(chosen),
                g.pending_exit_reasons[response_old],
            )
        )
    elif response_old is not None and g.response_probation_enabled:
        # E4试用到期或连续失效后，即使没有替代候选也退出，避免把失败响应永久留仓。
        if response_old in targets:
            targets.remove(response_old)
        g.pending_exit_reasons[response_old] = (
            "响应试用/主线连续失效，不能独立进入Buffett核心池；无替代也退出"
        )
        g.holding_thesis_states[response_old] = "EXIT"
        response_changes += 1
        log.info(
            "响应失败退出：%s；本月不强制补位。" % _stock_label(response_old)
        )
    elif response_old is not None:
        log.info(
            "响应席位暂不调整 %s：没有同时满足确认主线、Buffett门槛、行业及Beta约束的候选。"
            % _stock_label(response_old)
        )

    # 已持有且通过完整机构门槛的核心，可逐月无交易晋升为response。
    # 只使用超过最低6个核心的席位，不卖健康核心来追逐机构风向。
    _promote_existing_core_responses(
        targets, response_pool, effective_core_target
    )

    # 第一层：先达到本阶段核心目标（初始3/5/6，完成后最低6）。
    # 新核心不替换任何健康旧核心。
    while (
        sum(g.holding_roles.get(code) == "core" for code in targets) < effective_core_target
        and len(targets) < effective_holding_cap
        and new_securities_reserved < new_security_budget
    ):
        chosen = choose_candidate(core_pool, targets, "core")
        if chosen is None:
            break
        targets.append(chosen)
        g.holding_roles[chosen] = "core"
        new_securities_reserved += 1
        log.info("核心空位补仓：%s；核心趋势允许且Buffett门槛通过。" % _stock_label(chosen))

    # 第二层：完整机构证据下，用最多2个响应席位补充已满足Buffett门槛的主线公司。
    while (
        sum(g.holding_roles.get(code) == "response" for code in targets) < g.max_response_slots
        and len(targets) < effective_holding_cap
        and new_securities_reserved < new_security_budget
        and response_changes < g.max_response_changes_per_month
    ):
        chosen = choose_candidate(response_pool, targets, "response")
        if chosen is None:
            break
        targets.append(chosen)
        g.holding_roles[chosen] = "response"
        _start_response_probation(chosen, month_key, "new_response")
        new_securities_reserved += 1
        response_changes += 1
        log.info(
            "响应空位建仓：%s；主线已连续确认%d个月，且趋势/Buffett门槛通过。"
            % (
                _stock_label(chosen),
                g.industry_confirm_counts.get(industry_of(chosen)[0], 0),
            )
        )

    # 剩余空位全部由合格的Buffett核心填满。
    while (
        len(targets) < effective_holding_cap
        and new_securities_reserved < new_security_budget
    ):
        chosen = choose_candidate(core_pool, targets, "core")
        if chosen is None:
            break
        targets.append(chosen)
        g.holding_roles[chosen] = "core"
        new_securities_reserved += 1
        log.info("动态核心补位：%s；机构响应不足时由Buffett核心填充剩余席位。" % _stock_label(chosen))

    rank_map = {code: index + 1 for index, code in enumerate(entry_ranked)}
    targets.sort(
        key=lambda code: (
            0 if g.holding_roles.get(code) == "core" else 1,
            0 if code in holdings else 1,
            rank_map.get(code, 10 ** 9),
        )
    )
    targets = targets[:effective_holding_cap]
    for code in targets:
        if g.holding_roles.get(code) not in ("core", "response"):
            g.holding_roles[code] = "core"
    core_count = sum(g.holding_roles.get(code) == "core" for code in targets)
    response_count = sum(g.holding_roles.get(code) == "response" for code in targets)
    industry_counts = {}
    for code in targets:
        industry_code = industry_of(code)[0]
        industry_counts[industry_code] = industry_counts.get(industry_code, 0) + 1
    violations = []
    if core_count + response_count != len(targets):
        violations.append("角色数与持仓数不一致")
    if response_count > g.max_response_slots:
        violations.append("响应席位超过%d" % g.max_response_slots)
    if len(targets) > effective_holding_cap:
        violations.append("持仓超过本阶段上限%d" % effective_holding_cap)
    over_limit_industries = {
        key: count for key, count in industry_counts.items()
        if count > g.max_industry_holdings
    }
    # 目标总数不超过行业上限时，理论上不可能发生行业超限；显式短路并打印明细，
    # 便于区分策略约束、行业映射异常和平台粘贴版本不一致。
    if len(targets) > g.max_industry_holdings and over_limit_industries:
        violations.append(
            "行业超限%s（上限%d）" % (over_limit_industries, g.max_industry_holdings)
        )
    if len(targets) == effective_holding_cap and core_count < effective_core_target:
        violations.append("本阶段满仓时核心少于%d只" % effective_core_target)
    if violations:
        log.error("目标组合约束异常：%s。" % "、".join(violations))
    g.response_security_changes_this_month = int(response_changes)
    final_beta, final_account_beta, final_weight_map, _, beta_missing = (
        _planned_weighted_beta(context, targets, current_data)
    )
    final_quality = average_metric(targets, "quality")
    final_safety = average_metric(targets, "safety")
    final_value = average_metric(targets, "value")
    role_text = [
        "%s:%s" % (_stock_label(code), g.holding_roles.get(code, "core"))
        for code in targets
    ]
    log.info(
        "目标组合分层：核心%d（本阶段目标至少%d/席位上限%d），响应%d/%d；"
        "本月新证券=%d/%d，响应证券调整=%d/%d，角色晋升/降级=%d/%d；%s。"
        % (
            core_count, effective_core_target, effective_holding_cap,
            response_count, g.max_response_slots,
            new_securities_reserved, new_security_budget,
            response_changes, g.max_response_changes_per_month,
            g.response_role_promotions_this_month,
            g.response_role_demotions_this_month,
            role_text,
        )
    )
    if g.mainline_alignment_enabled:
        log.info(
            "主线权重强化：执行政策=%s，强化%d/%d只=%s；纯response仍为%d/%d。"
            % (
                getattr(g, "effective_allocation_policy", "unknown"),
                len(getattr(g, "pending_mainline_enhanced_codes", [])),
                _mainline_enhancement_target(),
                [_stock_label(code) for code in getattr(g, "pending_mainline_enhanced_codes", [])],
                response_count,
                g.max_response_slots,
            )
        )
    if g.response_probation_enabled:
        log.info(
            "响应试用状态：%s"
            % {
                _stock_label(code): g.response_probation_states.get(code, {})
                for code in targets if g.holding_roles.get(code) == "response"
            }
        )

    log.info(
        "目标组合因子：目标权重Beta=%s（目标<=%.2f/硬上限%.2f），账户Beta=%s，"
        "平均质量=%s，平均安全=%s，平均价值=%s，持仓=%d，Beta缺失=%s。"
        % (
            "%.3f" % final_beta if np.isfinite(final_beta) else "数据不足",
            g.portfolio_beta_target,
            g.portfolio_beta_ceiling,
            "%.3f" % final_account_beta if np.isfinite(final_account_beta) else "数据不足",
            "%.3f" % final_quality if np.isfinite(final_quality) else "数据不足",
            "%.3f" % final_safety if np.isfinite(final_safety) else "数据不足",
            "%.3f" % final_value if np.isfinite(final_value) else "数据不足",
            len(targets),
            [_stock_label(code) for code in beta_missing],
        )
    )
    return targets


def _is_trade_eligible(stock, current_data, for_buy=True):
    try:
        data = current_data[stock]
        name = str(data.name).upper()
        if data.paused or data.is_st or "ST" in name or "退" in name:
            return False
        if for_buy and data.last_price >= data.high_limit:
            return False
        return True
    except Exception:
        return False



def _l16_margin_subportfolio(context):
    """返回唯一的融资融券子账户。"""
    try:
        return context.subportfolios[0]
    except Exception:
        return None


def _first_finite_attr(obj, names, default=np.nan):
    """从多个聚宽字段别名中读取第一个有效数值。"""
    for name in names:
        try:
            value = float(getattr(obj, name))
        except Exception:
            continue
        if np.isfinite(value):
            return value, str(name)
    return float(default), None


def _l16_margin_metrics(context):
    """统一计算净资产、总暴露和融资债务。

    平台字段存在版本差异，因此同时使用：
    1. 子账户公开负债字段；
    2. 经济恒等式推算：负债≈股票市值+现金资产-净资产。

    最终债务取报告值与推算值的较大者，避免融资实际发生后
    cash_liability字段仍为0导致debt_ratio长期错误显示为0。
    """
    sub = _l16_margin_subportfolio(context)
    portfolio = context.portfolio

    if sub is None:
        account = portfolio
    else:
        account = sub

    net_value, net_field = _first_finite_attr(
        account,
        ("net_value", "total_value"),
        getattr(portfolio, "total_value", np.nan),
    )
    gross_value, gross_field = _first_finite_attr(
        account,
        ("positions_value", "long_positions_value", "stock_value"),
        getattr(portfolio, "positions_value", np.nan),
    )
    available_cash, cash_field = _first_finite_attr(
        account,
        ("available_cash", "cash"),
        getattr(portfolio, "available_cash", 0.0),
    )

    cash_liability, liability_field = _first_finite_attr(
        account,
        (
            "cash_liability",
            "margin_cash_liability",
            "financing_liability",
            "margin_liability",
        ),
        0.0,
    )
    total_liability_field_value, total_liability_field = _first_finite_attr(
        account,
        ("total_liability", "liability"),
        np.nan,
    )
    interest, interest_field = _first_finite_attr(
        account,
        (
            "interest",
            "interest_liability",
            "margin_interest",
            "financing_interest",
        ),
        0.0,
    )
    maintenance, maintenance_field = _first_finite_attr(
        account,
        (
            "maintenance_margin_rate",
            "maintain_margin_rate",
            "maintenance_rate",
        ),
        np.nan,
    )
    available_margin, available_margin_field = _first_finite_attr(
        account,
        (
            "available_margin",
            "margin_available",
            "available_credit",
        ),
        np.nan,
    )

    if not np.isfinite(net_value):
        net_value = float(getattr(portfolio, "total_value", 0.0))
    if not np.isfinite(gross_value):
        gross_value = float(getattr(portfolio, "positions_value", 0.0))
    if not np.isfinite(available_cash):
        available_cash = float(getattr(portfolio, "available_cash", 0.0))

    reported_total = max(0.0, float(cash_liability) + max(0.0, float(interest)))
    if np.isfinite(total_liability_field_value):
        reported_total = max(reported_total, max(0.0, total_liability_field_value))

    # 对纯股票融资账户：总资产≈股票市值+现金，净资产=总资产-负债。
    inferred_total = max(
        0.0,
        float(gross_value) + max(0.0, float(available_cash)) - float(net_value),
    )
    effective_total = max(reported_total, inferred_total)

    if reported_total > 1e-8 and reported_total >= inferred_total * 0.95:
        liability_source = "reported"
    elif inferred_total > 1e-8:
        liability_source = "inferred"
    else:
        liability_source = "none"

    try:
        g.margin_metrics_source_counts[liability_source] += 1
    except Exception:
        pass

    gross_exposure = (
        float(gross_value) / float(net_value)
        if float(net_value) > 0
        else np.nan
    )
    debt_ratio = (
        effective_total / float(net_value)
        if float(net_value) > 0
        else np.nan
    )
    reported_debt_ratio = (
        reported_total / float(net_value)
        if float(net_value) > 0
        else np.nan
    )
    inferred_debt_ratio = (
        inferred_total / float(net_value)
        if float(net_value) > 0
        else np.nan
    )

    diagnostic = {
        "liability_source": liability_source,
        "reported_total_liability": float(reported_total),
        "inferred_total_liability": float(inferred_total),
        "effective_total_liability": float(effective_total),
        "debt_ratio": float(debt_ratio) if np.isfinite(debt_ratio) else None,
        "reported_debt_ratio": (
            float(reported_debt_ratio)
            if np.isfinite(reported_debt_ratio)
            else None
        ),
        "inferred_debt_ratio": (
            float(inferred_debt_ratio)
            if np.isfinite(inferred_debt_ratio)
            else None
        ),
        "field_map": {
            "net_value": net_field,
            "gross_value": gross_field,
            "available_cash": cash_field,
            "cash_liability": liability_field,
            "total_liability": total_liability_field,
            "interest": interest_field,
            "maintenance_margin_rate": maintenance_field,
            "available_margin": available_margin_field,
        },
    }
    g.margin_last_diagnostic = dict(diagnostic)

    return {
        "net_value": float(net_value),
        "gross_position_value": float(gross_value),
        "gross_exposure": gross_exposure,
        "available_cash": float(available_cash),
        "cash_liability": float(cash_liability),
        "interest_liability": float(interest),
        "reported_total_liability": float(reported_total),
        "inferred_total_liability": float(inferred_total),
        "total_liability": float(effective_total),
        "liability_source": liability_source,
        "debt_ratio": debt_ratio,
        "reported_debt_ratio": reported_debt_ratio,
        "inferred_debt_ratio": inferred_debt_ratio,
        "maintenance_margin_rate": maintenance,
        "available_margin": available_margin,
        "diagnostic": diagnostic,
    }


def _l16_marginable_stocks(context=None):
    """按交易日缓存可融资标的；读取失败时返回空集并禁止新增融资。"""
    if context is None:
        log.error("LIVE-P0缺少context，拒绝读取无日期口径的可融资名单。")
        return set()
    try:
        trade_date = context.current_dt.date()
        date_key = str(trade_date)
    except Exception as exc:
        log.error("LIVE-P0无法取得当前交易日：%s；禁止新增融资。" % exc)
        return set()
    if date_key is not None and getattr(g, "marginable_cache_date", None) == date_key:
        return set(getattr(g, "marginable_cache_codes", []))
    try:
        codes = sorted(set(str(code) for code in get_margincash_stocks(date=trade_date)))
    except Exception as exc:
        log.error("E1-DL1.6c3e可融资标的读取失败：%s；本次只使用自有现金。" % exc)
        codes = []
    g.marginable_cache_date = date_key
    g.marginable_cache_codes = list(codes)
    return set(codes)


def _l16_order_target(context, security, target_amount):
    """融资融券账户的目标股数下单器。

    买入：优先使用自有现金；剩余整手仅对可融资标的调用margincash_open。
    卖出：存在融资负债时优先卖券还款；否则普通卖出。
    返回True代表至少提交了一个委托，None代表未提交。
    """
    security = str(security)
    target_amount = max(0, int(target_amount // 100) * 100)
    position = context.portfolio.positions.get(security)
    current_amount = int(getattr(position, "total_amount", 0)) if position is not None else 0
    if target_amount == current_amount:
        return None

    if target_amount < current_amount:
        sell_amount = current_amount - target_amount
        closeable = int(getattr(position, "closeable_amount", sell_amount)) if position is not None else 0
        sell_amount = min(sell_amount, closeable)
        sell_amount = int(sell_amount // 100) * 100
        if sell_amount <= 0:
            return None
        metrics = _l16_margin_metrics(context)
        if metrics["cash_liability"] + metrics["interest_liability"] > 1e-8:
            try:
                margincash_close(security, sell_amount)
                g.margin_order_calls += 1
                return True
            except Exception as exc:
                log.warning("卖券还款失败 %s %d股：%s；尝试普通卖出。" % (
                    _stock_label(security), sell_amount, exc
                ))
        try:
            order_obj = order(security, -sell_amount)
            return order_obj if order_obj is not None else None
        except Exception as exc:
            g.margin_order_failures += 1
            log.error("E1-DL1.6c3e卖出失败 %s %d股：%s。" % (
                _stock_label(security), sell_amount, exc
            ))
            return None

    # 增加仓位。模拟盘启动/热更新自检未通过时，只允许减仓，不允许增加风险。
    if bool(getattr(g, "live_new_risk_blocked", False)):
        log.error(
            "LIVE-P0新增风险锁生效：阻止新增买入%s；请先处理盘前自检失败项。"
            % _stock_label(security)
        )
        return None

    # 若上一轮仓位校正仍未解决，禁止所有新增买入。
    if bool(getattr(g, "exposure_reconcile_buy_lock", False)):
        log.warning(
            "仓位校正买入锁生效：阻止新增买入%s；须先把实际暴露降回保险线。"
            % _stock_label(security)
        )
        return None

    buy_amount = int((target_amount - current_amount) // 100) * 100
    if buy_amount <= 0:
        return None
    try:
        price = float(get_current_data()[security].last_price)
    except Exception:
        price = np.nan
    if not np.isfinite(price) or price <= 0:
        return None

    metrics = _l16_margin_metrics(context)
    # 自有现金预留0.5%成交缓冲，避免滑点、佣金使普通买单被拒。
    usable_cash = max(0.0, metrics["available_cash"] * 0.995)
    cash_lots = int(usable_cash / (price * 100.0))
    cash_amount = min(buy_amount, max(0, cash_lots) * 100)
    submitted = False
    if cash_amount > 0:
        try:
            order_obj = order(security, cash_amount)
            submitted = order_obj is not None
        except Exception as exc:
            log.warning("自有现金买入失败 %s %d股：%s。" % (
                _stock_label(security), cash_amount, exc
            ))
            cash_amount = 0

    remaining = buy_amount - cash_amount
    if remaining <= 0:
        return True if submitted else None

    policy = str(
        getattr(g, "effective_allocation_policy", None)
        or getattr(g, "liquidity_policy", "data_insufficient")
    )
    runtime_guard = _runtime_leverage_guard(
        context,
        policy,
        asof=str(context.previous_date),
        allow_drawdown_release=False,
    )
    if runtime_guard["financing_execution_blocked"]:
        log.warning(
            "新增融资被执行门阻止 %s：剩余%d股；原因=%s。"
            % (
                _stock_label(security),
                remaining,
                runtime_guard["financing_execution_block_reasons"],
            )
        )
        return True if submitted else None

    if security not in _l16_marginable_stocks(context):
        g.margin_unfilled_codes.append(security)
        log.warning(
            "E1-DL1.6c3e融资差额未成交 %s：目标增加%d股，自有现金完成%d股，"
            "剩余%d股非当日可融资标的。"
            % (_stock_label(security), buy_amount, cash_amount, remaining)
        )
        return True if submitted else None

    # 再以净资产和1.60倍动态总上限做最后一道融资保险。
    metrics = _l16_margin_metrics(context)
    room_value = max(
        0.0,
        metrics["net_value"]
        * min(float(g.gross_leverage_cap), float(g.current_target_exposure))
        - metrics["gross_position_value"],
    )
    margin_amount = min(remaining, int(room_value / (price * 100.0)) * 100)
    if margin_amount <= 0:
        log.warning("E1-DL1.6c3e总杠杆保险阻止 %s 剩余%d股融资买入。" % (
            _stock_label(security), remaining
        ))
        return True if submitted else None
    try:
        margin_order = margincash_open(security, margin_amount)
        g.margin_order_calls += 1
        if margin_order is None:
            # 聚宽融资买入成功通常返回Order；None按失败记录。
            g.margin_order_failures += 1
            log.warning("E1-DL1.6c3e融资买入委托未创建 %s %d股。" % (
                _stock_label(security), margin_amount
            ))
        else:
            submitted = True
            g.margin_successful_order_calls += 1
            log.info("E1-DL1.6c3e融资买入 %s：%d股，估算金额%.2f元。" % (
                _stock_label(security), margin_amount, margin_amount * price
            ))
    except Exception as exc:
        g.margin_order_failures += 1
        log.error("E1-DL1.6c3e融资买入失败 %s %d股：%s。" % (
            _stock_label(security), margin_amount, exc
        ))
    return True if submitted else None

def _can_sell(context, stock, current_data):
    if stock not in context.portfolio.positions:
        return False
    position = context.portfolio.positions[stock]
    if getattr(position, "closeable_amount", 0) <= 0:
        return False
    try:
        data = current_data[stock]
        return not data.paused and data.last_price > data.low_limit
    except Exception:
        return False


def _actual_holdings(context):
    return [
        str(stock)
        for stock, position in context.portfolio.positions.items()
        if getattr(position, "total_amount", 0) > 0
    ]


def _exposure_guard_ceiling_value(total_value, planned_total_value):
    """组合执行保险线：不高于整手计划或当前动态杠杆目标中的较低者，再允许0.5%执行容差。"""
    total_value = float(total_value)
    planned_total_value = max(0.0, float(planned_total_value))
    if total_value <= 0:
        return 0.0
    hard_target_value = total_value * float(g.current_target_exposure)
    anchor_value = min(hard_target_value, planned_total_value)
    tolerance_value = total_value * float(g.portfolio_exposure_tolerance)
    return min(total_value * float(g.gross_leverage_cap), max(0.0, anchor_value + tolerance_value))


def _guarded_increase_target_amount(
    current_amount,
    desired_amount,
    price,
    projected_equity_value,
    exposure_ceiling_value,
):
    """按100股整手返回允许的增加目标和被保险线拦截的手数。"""
    current_amount = max(0, int(current_amount))
    desired_amount = max(current_amount, int(desired_amount))
    price = float(price)
    if desired_amount <= current_amount or not np.isfinite(price) or price <= 0:
        return current_amount, 0
    desired_add = desired_amount - current_amount
    desired_lots = max(0, desired_add // 100)
    room_value = max(0.0, float(exposure_ceiling_value) - float(projected_equity_value))
    affordable_lots = max(0, int((room_value + 1e-8) / (price * 100.0)))
    allowed_lots = min(desired_lots, affordable_lots)
    guarded_amount = current_amount + allowed_lots * 100
    blocked_lots = desired_lots - allowed_lots
    return int(guarded_amount), int(blocked_lots)


def execute_rebalance(context, targets):
    current_data = get_current_data()
    existing = _actual_holdings(context)
    total_value = float(context.portfolio.total_value)

    # 在任何月度订单提交前冻结账户快照。后续预计仓位全部从这份快照推演，
    # 避免回测即时成交与实盘异步成交造成重复计算或漏算。
    pre_trade_amount_map = {}
    pre_trade_value_map = {}
    pre_trade_equity_value = 0.0
    for stock in existing:
        position = context.portfolio.positions.get(stock)
        if position is None:
            continue
        amount = int(getattr(position, "total_amount", 0))
        value = float(getattr(position, "value", 0.0))
        if amount <= 0 or value <= 0:
            continue
        pre_trade_amount_map[stock] = amount
        pre_trade_value_map[stock] = value
        pre_trade_equity_value += value
    pre_trade_exposure = (
        pre_trade_equity_value / total_value if total_value > 0 else 0.0
    )
    g.pending_pre_trade_exposure = float(pre_trade_exposure)
    g.pending_projected_post_order_exposure = float(pre_trade_exposure)
    g.pending_exposure_guard_ceiling = 0.0
    g.pending_exposure_band_bypass_sells = []
    g.pending_buy_lots_blocked_by_exposure_guard = 0
    g.pending_locked_exposure = 0.0

    new_budget = max(0, int(getattr(g, "effective_new_buy_budget", 0)))
    planned_new = [code for code in targets if code not in existing]
    # 在下单前固定“买入时已经披露的财报”。以后只有report_date发生变化，
    # 才属于持有后新财报，避免把买入前的历史恶化误判成新事件。
    entry_health = load_holding_health(context.previous_date, planned_new) if planned_new else {}
    if len(planned_new) > new_budget:
        # 最后一层执行保险：出现上游遗漏时，宁可保留待替换旧仓，也不绕过买入额度。
        allowed_new = set(planned_new[:new_budget])
        blocked_new = [code for code in planned_new if code not in allowed_new]
        targets = [code for code in targets if code in existing or code in allowed_new]
        for stock in existing:
            reason = g.pending_exit_reasons.get(stock, "")
            replacement_exit = "替代" in reason or "组合Beta" in reason
            if stock not in targets and replacement_exit:
                targets.append(stock)
                g.pending_exit_reasons.pop(stock, None)
                g.holding_thesis_states[stock] = "WATCH"
        log.error(
            "新证券计划%d只超过本月额度%d，执行层已拦截%s并保留对应旧仓。"
            % (len(planned_new), new_budget, [_stock_label(code) for code in blocked_new])
        )

    # 第一阶段：先提交完整退出。退出委托成功后，在预计仓位中按0处理；
    # 不可卖或委托未创建的旧仓进入locked，并真实占用席位和暴露预算。
    locked = []
    exit_submitted = []
    for stock in existing:
        if stock in targets:
            continue
        if _can_sell(context, stock, current_data):
            order = _l16_order_target(context, stock, 0)
            if order is None:
                locked.append(stock)
                log.warning("%s 退出委托未创建，暂时占用一个持仓位。" % _stock_label(stock))
                continue
            exit_submitted.append(stock)
            reason = g.pending_exit_reasons.get(stock, "投资逻辑失效")
            exit_report = g.pending_fundamental_exit_reports.get(stock)
            if exit_report:
                _register_fundamental_exit_lock(
                    context, stock, exit_report, reason
                )
            _clear_holding_state(stock)
            log.info("卖出 %s：%s。" % (_stock_label(stock), reason))
        else:
            locked.append(stock)
            log.warning("%s 应退出但当前不可卖，暂时占用一个持仓位。" % _stock_label(stock))

    # 不可卖旧仓会真实占用席位。先完整保留所有仍在账户里的目标旧仓，
    # 再按当前3/5/6阶段上限或正式8席位上限接纳新证券。
    kept_existing = [code for code in existing if code in targets or code in locked]
    execution_holding_cap = max(
        len(kept_existing),
        int(getattr(g, "initial_build_effective_cap", g.max_holdings)),
    )
    execution_holding_cap = min(g.max_holdings, execution_holding_cap)
    available_new_slots = max(0, execution_holding_cap - len(kept_existing))
    target_existing = [code for code in targets if code in existing and code not in locked]
    target_new = [code for code in targets if code not in existing][:available_new_slots]
    effective_targets = target_existing + target_new

    # 使用与选股阶段一致的真实权重规则，先形成理论权重，再形成100股整手计划。
    target_weight_map, weight_meta = _planned_weight_map(
        context, effective_targets, current_data
    )
    base_equal_weight = float(weight_meta.get("base_equal_weight", 0.0))
    healthy_weight = float(weight_meta.get("healthy_weight", 0.0))
    healthy_targets = list(weight_meta.get("healthy", []))
    factor_watch_capped = list(weight_meta.get("factor_watch", []))
    loss_watch_blocked = list(weight_meta.get("loss_watch", []))
    topup_blocked = list(factor_watch_capped) + list(loss_watch_blocked)
    planned_exposure = float(weight_meta.get("planned_exposure", 0.0))

    price_map = {}
    current_amount_map = {}
    target_amount_map = {}
    raw_target_value_map = {}
    invalid_price = []
    for stock in effective_targets:
        try:
            price = float(current_data[stock].last_price)
        except Exception:
            price = np.nan
        if not np.isfinite(price) or price <= 0:
            invalid_price.append(stock)
            continue
        price_map[stock] = price
        current_amount = int(pre_trade_amount_map.get(stock, 0))
        current_value = float(pre_trade_value_map.get(stock, 0.0))
        current_amount_map[stock] = current_amount
        target_weight = float(target_weight_map.get(stock, 0.0))
        target_value = total_value * target_weight
        raw_target_value_map[stock] = target_value
        if current_amount > 0 and stock in topup_blocked:
            target_value = min(target_value, current_value)
        target_amount = int(target_value / price / 100.0) * 100
        if current_amount > 0:
            target_amount = max(100, target_amount)
        if current_amount > 0 and stock in topup_blocked:
            target_amount = min(current_amount, target_amount)
        target_amount_map[stock] = max(0, int(target_amount))

    locked_value = sum(float(pre_trade_value_map.get(stock, 0.0)) for stock in locked)
    locked_exposure = locked_value / total_value if total_value > 0 else 0.0
    g.pending_locked_exposure = float(locked_exposure)
    exposure_budget_value = max(
        0.0, total_value * g.current_target_exposure - locked_value
    )
    planned_target_value = sum(
        float(amount) * float(price_map.get(stock, 0.0))
        for stock, amount in target_amount_map.items()
    )
    rounding_redeploy_value = 0.0
    reallocated_lots = []

    def amount_plan_beta(amount_map):
        weight_map = {}
        for code in locked:
            value = float(pre_trade_value_map.get(code, 0.0))
            if value > 0 and total_value > 0:
                weight_map[code] = value / total_value
        for code, amount in amount_map.items():
            price = price_map.get(code, np.nan)
            if amount > 0 and np.isfinite(price) and total_value > 0:
                weight_map[code] = float(amount) * float(price) / total_value
        return _weighted_beta_from_weights(weight_map)

    # 整手二次分配仍只给健康核心，并且将不可卖锁仓计入总暴露和Beta。
    if g.lot_reallocation_enabled and healthy_targets:
        for _ in range(int(g.lot_reallocation_max_rounds)):
            candidates = []
            for stock in healthy_targets:
                if stock not in price_map or stock not in target_amount_map:
                    continue
                price = price_map[stock]
                lot_value = price * 100.0
                next_amount = target_amount_map[stock] + 100
                next_value = next_amount * price
                raw_target = raw_target_value_map.get(stock, 0.0)
                max_value = min(
                    total_value * _dynamic_single_weight_cap(context),
                    raw_target * g.max_lot_to_target_ratio
                    + total_value * g.lot_reallocation_weight_tolerance,
                )
                if next_value > max_value + 1e-8:
                    continue
                if planned_target_value + lot_value > exposure_budget_value + 1e-8:
                    continue
                trial = dict(target_amount_map)
                trial[stock] = next_amount
                trial_beta, _, _ = amount_plan_beta(trial)
                if np.isfinite(trial_beta) and trial_beta > g.portfolio_beta_ceiling:
                    continue
                overshoot = max(0.0, next_value - raw_target) / max(raw_target, 1.0)
                total_score = g.pending_scores.get(stock, {}).get("total", np.nan)
                beta = g.pending_scores.get(stock, {}).get("beta", np.nan)
                candidates.append((
                    overshoot,
                    -float(total_score) if np.isfinite(total_score) else 0.0,
                    float(beta) if np.isfinite(beta) else np.inf,
                    stock,
                ))
            if not candidates:
                break
            candidates.sort()
            stock = candidates[0][-1]
            lot_value = price_map[stock] * 100.0
            target_amount_map[stock] += 100
            planned_target_value += lot_value
            rounding_redeploy_value += lot_value
            reallocated_lots.append(stock)

    executable_weight_map = {}
    combined_weight_map = {}
    for stock in locked:
        value = float(pre_trade_value_map.get(stock, 0.0))
        if value > 0 and total_value > 0:
            combined_weight_map[stock] = value / total_value
    for stock, amount in target_amount_map.items():
        price = price_map.get(stock, np.nan)
        if amount > 0 and np.isfinite(price) and total_value > 0:
            weight = amount * price / total_value
            executable_weight_map[stock] = weight
            combined_weight_map[stock] = weight
    executable_exposure = sum(float(value) for value in combined_weight_map.values())
    planned_total_value = executable_exposure * total_value
    planned_equity_beta, planned_account_beta, beta_missing = (
        _weighted_beta_from_weights(combined_weight_map)
    )
    exposure_guard_ceiling_value = _exposure_guard_ceiling_value(
        total_value, planned_total_value
    )
    exposure_guard_ceiling = (
        exposure_guard_ceiling_value / total_value if total_value > 0 else 0.0
    )

    g.pending_raw_target_weights = dict(target_weight_map)
    g.pending_target_weights = dict(executable_weight_map)
    g.pending_planned_exposure = float(executable_exposure)
    g.pending_planned_equity_beta = float(planned_equity_beta)
    g.pending_planned_account_beta = float(planned_account_beta)
    g.pending_rounding_redeploy_value = float(rounding_redeploy_value)
    g.pending_exposure_guard_ceiling = float(exposure_guard_ceiling)

    healthy_core_count = sum(
        g.holding_roles.get(code, "core") == "core" for code in healthy_targets
    )
    healthy_response_count = sum(
        g.holding_roles.get(code) == "response" for code in healthy_targets
    )
    log.info(
        "仓位计划：有效目标%d只，基础等权%.2f%%，健康持仓%d只（核心%d/响应%d）目标%.2f%%，"
        "因子WATCH上限%.1f%%=%s，价格观察禁止加仓=%s，锁定仓位%.2f%%，"
        "理论仓位%.2f%%，整手可执行总仓位%.2f%%，二次分配=%.2f元/%d手，"
        "目标权重Beta=%s，账户Beta=%s，执行保险线%.2f%%，计划现金%.2f%%。"
        % (
            len(effective_targets),
            base_equal_weight * 100.0,
            len(healthy_targets),
            healthy_core_count,
            healthy_response_count,
            healthy_weight * 100.0,
            g.watch_max_weight * 100.0,
            [_stock_label(code) for code in factor_watch_capped],
            [_stock_label(code) for code in loss_watch_blocked],
            locked_exposure * 100.0,
            planned_exposure * 100.0,
            executable_exposure * 100.0,
            rounding_redeploy_value,
            len(reallocated_lots),
            "%.3f" % planned_equity_beta if np.isfinite(planned_equity_beta) else "数据不足",
            "%.3f" % planned_account_beta if np.isfinite(planned_account_beta) else "数据不足",
            exposure_guard_ceiling * 100.0,
            (1.0 - executable_exposure) * 100.0,
        )
    )
    if invalid_price:
        log.warning("以下目标缺少有效价格，未纳入整手计划：%s。" % [
            _stock_label(code) for code in invalid_price
        ])
    if reallocated_lots:
        lot_counts = {}
        for code in reallocated_lots:
            lot_counts[code] = lot_counts.get(code, 0) + 1
        log.info(
            "整手剩余现金二次分配：%s。"
            % {
                _stock_label(code): count for code, count in lot_counts.items()
            }
        )

    # 从月初快照推演完整退出后的暴露。即使平台尚未刷新position，也不会把卖出价值重复计算。
    projected_equity_value = pre_trade_equity_value - sum(
        float(pre_trade_value_map.get(stock, 0.0)) for stock in exit_submitted
    )
    projected_equity_value = max(0.0, projected_equity_value)
    remaining_full_increase_value = 0.0
    for stock, target_amount in target_amount_map.items():
        current_amount = int(current_amount_map.get(stock, 0))
        if target_amount > current_amount and stock in price_map:
            remaining_full_increase_value += (
                target_amount - current_amount
            ) * price_map[stock]

    # 第二阶段：所有减仓严格先于任何加仓。正常情况下仍保留单股调仓带；
    # 但若跳过减仓会使“减仓后+全部计划买入”的最终暴露超过保险线，则强制绕过调仓带。
    exposure_band_bypass_sells = []
    reduction_plan = []
    for stock in effective_targets:
        if stock not in target_amount_map or stock not in price_map:
            continue
        current_amount = int(current_amount_map.get(stock, 0))
        target_amount = int(target_amount_map.get(stock, 0))
        if current_amount <= target_amount:
            continue
        delta_amount = current_amount - target_amount
        delta_value = delta_amount * price_map[stock]
        reduction_plan.append((delta_value, stock, current_amount, target_amount))
    reduction_plan.sort(reverse=True)

    for delta_value, stock, current_amount, target_amount in reduction_plan:
        price = price_map[stock]
        effective_band = (
            g.watch_reallocation_band
            if topup_blocked and stock in healthy_targets
            else g.rebalance_band
        )
        within_band = delta_value < total_value * effective_band
        final_if_skipped = projected_equity_value + remaining_full_increase_value
        capacity_needed = bool(
            g.exposure_guard_enabled
            and final_if_skipped > exposure_guard_ceiling_value + 1e-8
        )
        if within_band and not capacity_needed:
            continue
        if current_amount - target_amount < 100:
            log.info(
                "跳过 %s 的不足一手减仓：当前%d股，目标%d股。"
                % (_stock_label(stock), current_amount, target_amount)
            )
            continue
        if not _can_sell(context, stock, current_data):
            log.warning(
                "仓位保险需要减仓 %s，但当前不可卖；后续买入将按预计仓位自动缩减。"
                % _stock_label(stock)
            )
            continue
        if within_band and capacity_needed:
            exposure_band_bypass_sells.append(stock)
            log.info(
                "组合仓位保险绕过调仓带减仓 %s：减仓%.2f元，"
                "否则全部计划买入后预计仓位%.2f%% > 保险线%.2f%%。"
                % (
                    _stock_label(stock),
                    delta_value,
                    final_if_skipped / total_value * 100.0 if total_value > 0 else 0.0,
                    exposure_guard_ceiling * 100.0,
                )
            )
        order = _l16_order_target(context, stock, target_amount)
        if order is None:
            log.warning("%s 减仓委托未创建；后续买入将按预计仓位自动缩减。" % _stock_label(stock))
            continue
        projected_equity_value = max(0.0, projected_equity_value - delta_value)
        target_weight = float(executable_weight_map.get(stock, 0.0))
        log.info(
            "减仓调仓 %s：角色=%s，目标 %.1f%%/%d股，总分 %.3f。"
            % (
                _stock_label(stock), g.holding_roles.get(stock, "core"),
                target_weight * 100.0, target_amount,
                g.pending_scores.get(stock, {}).get("total", np.nan),
            )
        )

    # 第三阶段：在所有可执行减仓已提交后再增加仓位。每笔增加前都以当前预计暴露重新计算可买整手数。
    buy_lots_blocked = 0
    marginable_for_day = _l16_marginable_stocks(context)
    original_buy_rank = {code: index for index, code in enumerate(effective_targets)}
    buy_sequence = sorted(
        effective_targets,
        key=lambda code: (code in marginable_for_day, original_buy_rank.get(code, 10 ** 9)),
    )
    for stock in buy_sequence:
        if stock not in target_amount_map or stock not in price_map:
            continue
        current_amount = int(current_amount_map.get(stock, 0))
        desired_amount = int(target_amount_map.get(stock, 0))
        if desired_amount <= current_amount:
            continue
        if not _is_trade_eligible(stock, current_data, for_buy=True):
            continue
        if current_amount <= 0:
            health = entry_health.get(stock, {})
            if _is_fundamental_report_locked(
                stock, health.get("report_date"), release_if_new=True
            ):
                lock = g.fundamental_exit_report_locks.get(stock, {})
                g.holding_roles.pop(stock, None)
                log.warning(
                    "取消买入 %s：财报退出版本锁仍有效，退出报告=%s，当前报告=%s。"
                    % (
                        _stock_label(stock),
                        lock.get("report_date") if isinstance(lock, dict) else lock,
                        health.get("report_date") or "数据暂缺",
                    )
                )
                continue
            if health.get("loss_making", False) or health.get("deteriorated", False):
                g.holding_roles.pop(stock, None)
                reason = (
                    "最新财报已亏损" if health.get("loss_making", False)
                    else "买入前最新财报已出现实质性恶化：%s"
                    % "、".join(health.get("deterioration_signals", []))
                )
                log.warning("取消买入 %s：%s。" % (_stock_label(stock), reason))
                continue

        price = price_map[stock]
        desired_delta_value = (desired_amount - current_amount) * price
        effective_band = (
            g.watch_reallocation_band
            if topup_blocked and stock in healthy_targets
            else g.rebalance_band
        )
        if desired_delta_value < total_value * effective_band:
            continue

        guarded_amount, blocked_lots = _guarded_increase_target_amount(
            current_amount,
            desired_amount,
            price,
            projected_equity_value,
            exposure_guard_ceiling_value,
        )
        buy_lots_blocked += blocked_lots
        if blocked_lots > 0:
            log.warning(
                "组合仓位保险缩减 %s 买入%d手：原目标%d股，允许目标%d股，"
                "当前预计仓位%.2f%%，保险线%.2f%%。"
                % (
                    _stock_label(stock), blocked_lots,
                    desired_amount, guarded_amount,
                    projected_equity_value / total_value * 100.0 if total_value > 0 else 0.0,
                    exposure_guard_ceiling * 100.0,
                )
            )
        if guarded_amount <= current_amount:
            continue
        if guarded_amount - current_amount < 100:
            continue
        order = _l16_order_target(context, stock, guarded_amount)
        if order is None:
            log.warning("%s 加仓委托未创建。" % _stock_label(stock))
            continue
        add_value = (guarded_amount - current_amount) * price
        projected_equity_value += add_value
        action = "调仓" if current_amount > 0 else "买入"
        target_weight = guarded_amount * price / total_value if total_value > 0 else 0.0
        if current_amount <= 0:
            item = g.pending_scores.get(stock, {})
            baseline = {
                "entry_pe": item.get("pe_ratio", np.nan),
                "entry_pb": item.get("pb_ratio", np.nan),
            }
            health = entry_health.get(stock, {})
            baseline.update(_health_baseline_snapshot(health))
            g.holding_fundamental_baselines[stock] = baseline
            entry_report = health.get("report_date")
            g.holding_report_states[stock] = {
                "entry_report": entry_report,
                "last_report": entry_report,
                "entry_date": str(context.current_dt.date()),
                "bad_report_count": 0,
            }
            g.holding_thesis_states[stock] = "HEALTHY"
            log.info(
                "持仓基准建立 %s：角色=%s，买入日=%s，已披露财报=%s，PE=%s，PB=%s，"
                "ROE=%s，ROA=%s，负债率=%s，经营现金流/资产=%s。"
                % (
                    _stock_label(stock), g.holding_roles.get(stock, "core"),
                    context.current_dt.date(), entry_report or "数据暂缺",
                    "%.2f" % item.get("pe_ratio") if np.isfinite(item.get("pe_ratio", np.nan)) else "缺失",
                    "%.2f" % item.get("pb_ratio") if np.isfinite(item.get("pb_ratio", np.nan)) else "缺失",
                    "%.2f" % health.get("roe") if np.isfinite(health.get("roe", np.nan)) else "缺失",
                    "%.2f" % health.get("roa") if np.isfinite(health.get("roa", np.nan)) else "缺失",
                    "%.3f" % health.get("debt_ratio") if np.isfinite(health.get("debt_ratio", np.nan)) else "缺失",
                    "%.3f" % health.get("ocf_assets") if np.isfinite(health.get("ocf_assets", np.nan)) else "缺失",
                )
            )
        log.info(
            "%s %s：角色=%s，目标 %.1f%%/%d股，总分 %.3f。"
            % (
                action, _stock_label(stock), g.holding_roles.get(stock, "core"),
                target_weight * 100.0, guarded_amount,
                g.pending_scores.get(stock, {}).get("total", np.nan),
            )
        )

    projected_post_order_exposure = (
        projected_equity_value / total_value if total_value > 0 else 0.0
    )
    g.pending_projected_post_order_exposure = float(projected_post_order_exposure)
    g.pending_exposure_band_bypass_sells = list(exposure_band_bypass_sells)
    g.pending_buy_lots_blocked_by_exposure_guard = int(buy_lots_blocked)
    log.info(
        "组合仓位执行保险：交易前%.2f%%，整手计划%.2f%%，保险线%.2f%%，"
        "提交订单后预计%.2f%%；绕过调仓带减仓=%s，拦截买入=%d手。"
        % (
            pre_trade_exposure * 100.0,
            executable_exposure * 100.0,
            exposure_guard_ceiling * 100.0,
            projected_post_order_exposure * 100.0,
            [_stock_label(code) for code in exposure_band_bypass_sells],
            buy_lots_blocked,
        )
    )
