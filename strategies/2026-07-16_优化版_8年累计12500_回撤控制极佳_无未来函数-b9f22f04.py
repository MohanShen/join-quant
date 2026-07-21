# Clone from JoinQuant
# postId: b9f22f042582431f28b2692d8dfacee0
# backtestId: acf08cb2c79f3dcbd3d2c7e7e94e0719
# title: 优化版｜8年累计12500%｜回撤控制极佳｜无未来函数

# 克隆自聚宽文章：https://www.joinquant.com/post/72984
# 标题：五福51-三状态V4-分母2万-11年386倍回撤19.82
# 作者：rbq2025

# 克隆自聚宽文章：https://www.joinquant.com/post/71413
# 标题：【五福闹新春】v5.1-拟合ETF池最严厉的父亲
# 作者：烟花三月ETF

import numpy as np
import math
import copy
import pandas as pd
from jqdata import *
from datetime import datetime, date, timedelta, time as dt_time


CORR_GUARD_DECISION_INTERCEPT = 'intercept'
CORR_GUARD_DECISION_ALLOW_LOW = 'allow_low_corr'
CORR_GUARD_DECISION_ALLOW_MOM = 'allow_momentum'

# 动量×P_adj 矩阵分桶（与复盘热力图表格一致）
CORR_GUARD_MOM_MATRIX_BUCKETS = [
    '[0,2)', '[2,3)', '[3,4)', '[4,4.5)', '[4.5,5)',
    '[5,5.5)', '[5.5,6)', '[6,7]', '>7',
]
CORR_GUARD_PADJ_MATRIX_COLS = [
    '≤0.50', '0.60~0.70', '0.70~0.80', '0.80~0.85',
    '0.85~0.90', '0.90~0.95', '>0.95',
]
CORR_GUARD_MATRIX_REGIMES = ('全样本', '正常期', '震荡期', '走弱期')

# 分状态×动量 P_adj 守卫规则 mode 说明：
# - always_allow: 一律放行
# - intercept_if_gt: P_adj > intercept_gt → 拦截
# - intercept_if_gt_with_release_le: P_adj ≤ release_le 或 (release_le, intercept_gt] 放行，> intercept_gt 拦截
# - intercept_outside_release_bands: P_adj ≤ release_le 或 release_band_lo~hi 放行，其余拦截
# - intercept_if_between: intercept_lo ≤ P_adj ≤ intercept_hi 拦截（可走 release_le / release_gt 先放行）
# - intercept_only_in_bands: 仅当 P_adj 落在 intercept_bands 任一 [lo,hi] 闭区间内 → 拦截，否则放行
# - fallback_gt: 未命中更细规则时的兜底，P_adj > intercept_gt → 拦截


def _format_corr_intercept_bands(bands):
    if not bands:
        return '—'
    return '|'.join(f'{float(b["lo"]):.2f}~{float(b["hi"]):.2f}' for b in bands)


def default_corr_regime_mom_guard_rules():
    """
    分市场状态 × 动量区间 P_adj 多带拦截默认方案（v2：矩阵 9 档动量 + intercept_bands）。
    可通过 g.corr_regime_mom_guard_rules 整表覆盖；
    或用 g.corr_regime_band_overrides[(状态, label)] 覆盖单档 intercept_bands。
    """
    return {
        '正常期': [
            {'label': '[0,2)', 'mom_lo': 0, 'mom_hi': 2,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.80, 'hi': 0.85}]},
            {'label': '[2,3)', 'mom_lo': 2, 'mom_hi': 3,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.55, 'hi': 0.70}, {'lo': 0.85, 'hi': 0.90}]},
            {'label': '[3,4)', 'mom_lo': 3, 'mom_hi': 4,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.85, 'hi': 0.95}]},
            {'label': '[4,4.5)', 'mom_lo': 4, 'mom_hi': 4.5,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.80, 'hi': 0.85}]},
            {'label': '[4.5,5)', 'mom_lo': 4.5, 'mom_hi': 5,
             'mode': 'intercept_outside_release_bands',
             'release_le': 0.85, 'release_band_lo': 0.90, 'release_band_hi': 0.92},
            {'label': '[5,5.5)', 'mom_lo': 5, 'mom_hi': 5.5,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.85, 'hi': 0.90}]},
            {'label': '[5.5,6)', 'mom_lo': 5.5, 'mom_hi': 6,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.85, 'hi': 0.95}]},
            {'label': '[6,7]', 'mom_lo': 6, 'mom_hi': 7, 'hi_inclusive': True,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.80, 'hi': 0.85}]},
            {'label': '>7', 'mom_lo': 7, 'mom_lo_exclusive': True,
             'mode': 'always_allow'},
        ],
        '震荡期': [
            {'label': '[0,2)', 'mom_lo': 0, 'mom_hi': 2,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.75, 'hi': 0.90}]},
            {'label': '[2,3)', 'mom_lo': 2, 'mom_hi': 3,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.50, 'hi': 0.70}]},
            {'label': '[3,4)', 'mom_lo': 3, 'mom_hi': 4,
             'mode': 'intercept_if_gt', 'intercept_gt': 0.84},
            {'label': '[4,4.5)', 'mom_lo': 4, 'mom_hi': 4.5,
             'mode': 'always_allow'},
            {'label': '[4.5,5)', 'mom_lo': 4.5, 'mom_hi': 5,
             'mode': 'always_allow'},
            {'label': '[5,5.5)', 'mom_lo': 5, 'mom_hi': 5.5,
             'mode': 'intercept_only_in_bands',
             'intercept_bands': [{'lo': 0.60, 'hi': 0.80}]},
            {'label': '>=5.5', 'mom_lo': 5.5, 'mom_hi': None,
             'mode': 'always_allow'},
        ],
        '走弱期': [
            {'label': '[0,2)', 'mom_lo': 0, 'mom_hi': 2,
             'mode': 'intercept_if_between',
             'intercept_lo': 0.62, 'intercept_hi': 0.78,
             'release_le': 0.55, 'release_gt': 0.78},
            {'label': '[2,3)', 'mom_lo': 2, 'mom_hi': 3,
             'mode': 'always_allow'},
            {'label': '[3,4)', 'mom_lo': 3, 'mom_hi': 4,
             'mode': 'intercept_if_between',
             'intercept_lo': 0.55, 'intercept_hi': 0.70,
             'release_le': 0.50},
            {'label': '>=4.5', 'mom_lo': 4.5, 'mom_hi': None,
             'mode': 'always_allow'},
        ],
    }


def _corr_regime_mom_guard_mode_desc():
    """启动日志/守卫明细用：当前分档守卫模式描述。"""
    if not getattr(g, 'enable_corr_regime_mom_guard', False):
        th = float(getattr(g, 'corr_hold_threshold', 0.80))
        mom = float(getattr(g, 'corr_hold_momentum_max', 6))
        return f'统一阈值 P_adj>{th:.2f} 且动量≤{mom:.2f}'
    return '方案B·完整v2矩阵(9档+多带intercept_bands) + band_overrides'


def _default_corr_guard_type_stats():
    return {
        'registered': 0,
        'done': 0,
        'hold_win': 0,
        'target_win': 0,
        'tie': 0,
        'sum_hold_ret': 0.0,
        'sum_target_ret': 0.0,
        'sum_spread': 0.0,
    }


def _default_corr_guard_stats():
    """相关性守卫复盘统计（拦截 / 低相关放行 / 动量豁免）。"""
    by_type = {
        CORR_GUARD_DECISION_INTERCEPT: _default_corr_guard_type_stats(),
        CORR_GUARD_DECISION_ALLOW_LOW: _default_corr_guard_type_stats(),
        CORR_GUARD_DECISION_ALLOW_MOM: _default_corr_guard_type_stats(),
    }
    return {
        'review_done': 0,
        'by_type': by_type,
        # 兼容旧看板字段（仅拦截类）
        'intercept_total': 0,
        'hold_better': 0,
        'target_better': 0,
        'tie': 0,
        'sum_hold_ret': 0.0,
        'sum_target_ret': 0.0,
        'sum_spread': 0.0,
    }


def _default_corr_regime_band_overrides():
    return {
        ('正常期', '[5.5,6)'): {'mode': 'intercept_if_gt', 'intercept_gt': 0.78},
        ('正常期', '[5,5.5)'): {
            'mode': 'intercept_only_in_bands',
            'intercept_bands': [{'lo': 0.85, 'hi': 0.95}],
        },
        ('震荡期', '[0,2)'): {'mode': 'intercept_if_gt', 'intercept_gt': 0.30},
        ('震荡期', '[2,3)'): {'mode': 'intercept_if_gt', 'intercept_gt': 0.30},
    }


def _corr_guard_scheme_b_band_overrides():
    """方案 B：v2 矩阵 + 分档 override（含 initialize 中正常期修补）。"""
    ov = copy.deepcopy(_default_corr_regime_band_overrides())
    ov.update({
        ('正常期', '[5.5,6)'): {'mode': 'intercept_if_gt', 'intercept_gt': 0.78},
        ('正常期', '[5,5.5)'): {
            'mode': 'intercept_only_in_bands',
            'intercept_bands': [{'lo': 0.85, 'hi': 0.95}],
        },
    })
    return ov


def apply_corr_guard_test_scheme(scheme=None):
    """
    应用方案 B 守卫预设（完整 v2 矩阵 + band_overrides）。
    策略切换：统一阈值模式设 enable_corr_regime_mom_guard=False；
    方案 B 设 enable_corr_regime_mom_guard=True 且 corr_guard_test_scheme='B'。
    """
    scheme = (scheme if scheme is not None else getattr(g, 'corr_guard_test_scheme', None))
    if not scheme:
        return
    scheme = str(scheme).upper()
    if scheme != 'B':
        log.warning(f"【守卫预设】仅支持方案 B，收到 {scheme!r}，已忽略")
        return
    params = {
        'corr_regime_mom_guard_rules': None,
        'corr_regime_band_overrides': _corr_guard_scheme_b_band_overrides(),
        'corr_regime_mom_guard_allow_legacy_when_mom_missing': False,
    }
    for key, value in params.items():
        if isinstance(value, dict):
            setattr(g, key, copy.deepcopy(value))
        else:
            setattr(g, key, value)
    g.corr_guard_test_scheme = 'B'
    log.info('【守卫预设】已应用方案B — 完整v2矩阵(9档+多带) + band_overrides 分档修补')


def _corr_guard_test_scheme_desc():
    if not getattr(g, 'enable_corr_regime_mom_guard', False):
        return '未启用(统一阈值模式)'
    scheme = getattr(g, 'corr_guard_test_scheme', None)
    if str(scheme).upper() == 'B':
        return '方案B: 完整v2矩阵(9档+多带) + band_overrides 分档修补'
    return '分档守卫已开但未应用方案B'


def _ensure_corr_globals():
    """模拟实盘热更新时 initialize 可能不重跑，补齐修正相关性相关 g 字段。"""
    defaults = {
        'enable_corr_pool_filter': False,
        'corr_pool_threshold': 0.5,
        'corr_lookback_days': 60,
        'enable_corr_overview': True,
        'enable_corr_hold_guard': True,
        'corr_hold_threshold': 0.80,
        'corr_hold_momentum_max': 6,
        'enable_corr_regime_mom_guard': True,
        'corr_regime_mom_guard_rules': None,
        'corr_regime_momentum_always_allow_above': 7.0,
        'corr_regime_mom_guard_allow_legacy_when_mom_missing': False,
        'corr_guard_test_scheme': None,
        'enable_corr_high_pair_overlay': True,
        'corr_high_pair_block_threshold': 0.88,
        'corr_high_pair_overlay_mom_max': 8.0,
        'corr_mom_exempt_requires_low_corr': True,
        'corr_mom_exempt_max_pair_corr': 0.82,
        'corr_regime_band_overrides': _default_corr_regime_band_overrides(),
        'pick_target_skip_high_corr': True,
        'pick_target_max_padj': 0.85,
        'anti_churn_immediate_requires_low_corr': True,
        'anti_churn_immediate_max_padj': 0.85,
        'log_corr_detail': True,
        'enable_corr_guard_review': True,
        'enable_corr_mom_padj_matrix_report': True,
        'corr_mom_padj_matrix_min_cell_n': 1,
        'pending_corr_guard_reviews': [],
        'corr_guard_review_history': [],
        'corr_guard_all_records': [],
    }
    for key, value in defaults.items():
        if not hasattr(g, key):
            setattr(g, key, value)
    if not hasattr(g, 'corr_guard_stats') or not isinstance(g.corr_guard_stats, dict):
        g.corr_guard_stats = _default_corr_guard_stats()


def _corr_guard_type_label(decision_type):
    return {
        CORR_GUARD_DECISION_INTERCEPT: '拦截',
        CORR_GUARD_DECISION_ALLOW_LOW: '低相关放行',
        CORR_GUARD_DECISION_ALLOW_MOM: '动量豁免放行',
    }.get(decision_type, str(decision_type))


def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001,
                              close_commission=0.0001, close_today_commission=0.0001,
                              min_commission=5), type="fund")
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    log.info("【五福闹新春】v5.1启动！")

    # ==================== ETF池定义 ====================
    # 全球/海外ETF池（含大宗商品和海外市场ETF）
    g.global_etf_pool = [
#大宗商品ETF：
        '518880.XSHG',  # (黄金ETF) [ETF]-日均成交额：51.35亿元-上市日期：2013-07-29
        '501018.XSHG',  # (南方原油) [LOF]-日均成交额：24.38亿元-上市日期：2016-06-28
        '161226.XSHE',  # (国投白银LOF) [LOF]-日均成交额：5.44亿元-上市日期：2015-08-17
        '159985.XSHE',  # (豆粕ETF华夏) [ETF]-日均成交额：4.63亿元-上市日期：2019-12-05
        '159980.XSHE',  # (有色ETF大成) [ETF]-日均成交额：3.84亿元-上市日期：2019-12-24
#海外ETF：       
        '513310.XSHG',  # (中韩芯片) [ETF]-日均成交额：59.37亿元-上市日期：2022-12-22
        '159518.XSHE',  # (标普油气ETF嘉实) [ETF]-日均成交额：27.93亿元-上市日期：2023-11-15
        '159509.XSHE',  # (纳指科技ETF景顺) [ETF]-日均成交额：7.24亿元-上市日期：2023-08-08
        '513100.XSHG',  # (纳指ETF) [ETF]-日均成交额：5.02亿元-上市日期：2013-05-15
        '513520.XSHG',  # (日经ETF) [ETF]-日均成交额：3.72亿元-上市日期：2019-06-25
        '513500.XSHG',  # (标普500) [ETF]-日均成交额：2.89亿元-上市日期：2014-01-15
        '159502.XSHE',  # (标普生物科技ETF嘉实) [ETF]-日均成交额：1.80亿元-上市日期：2024-01-10
        '513400.XSHG',  # (道琼斯) [ETF]-日均成交额：1.70亿元-上市日期：2024-02-02
        '513030.XSHG',  # (德国ETF) [ETF]-日均成交额：0.95亿元-上市日期：2014-09-05
        '513290.XSHG',  # (纳指生物) [ETF]-日均成交额：0.78亿元-上市日期：2022-08-29
        '520830.XSHG',  # (沙特ETF) [ETF]-日均成交额：0.62亿元-上市日期：2024-07-16
        '159529.XSHE',  # (标普消费ETF景顺) [ETF]-日均成交额：0.50亿元-上市日期：2024-02-02
        '513400.XSHG',  # (道琼斯ETF) [ETF]-日均成交额：0.2亿元-上市日期：2024-02-29
        '164824.XSHE',  # (印度基金LOF) [ETF]-日均成交额：0.50亿元-上市日期：2018-08-31
        '513080.XSHG',  # 法国ETF
        '513730.XSHG',  # 东南亚ETF
        '511380.XSHG',  # 可转债ETF
        #'511010.XSHG',  # 国债ETF
        '511220.XSHG',  # 城投债E
        '510050.XSHG',  # 上证50
        '563300.XSHG',  # (中证2000) [ETF]-日均成交额：4.13亿元-上市日期：2023-09-14
        #'512010.XSHG',  # (医药ETF) [ETF]-日均成交额：4.27亿元-上市日期：2013-10-28
        #'510880.XSHG',  # (红利ETF) [ETF]-日均成交额：3.97亿元-上市日期：2007-01-18        
        '159928.XSHE',  # (消费ETF汇添富) [ETF]-日均成交额：3.66亿元-上市日期：2013-09-16        
        '510300.XSHG',  # 300ETF    
        '510500.XSHG',  # 500ETF    
        '512100.XSHG',  # 1000ETF    
        '159915.XSHE',  # 创业板ETF
        '513180.XSHG',  # (恒指科技) [ETF]-日均成交额：36.66亿元-上市日期：2021-05-25
        '159920.XSHE',  # (恒生中国) [ETF]-日均成交额：1.46亿元-上市日期：2012-10-22        
]
    # 中国ETF池（含港股、指数、行业ETF）
    g.china_etf_pool = [
#港股ETF：
        '513090.XSHG',  # (香港证券) [ETF]-日均成交额：54.24亿元-上市日期：2020-03-26
        '513120.XSHG',  # (HK创新药) [ETF]-日均成交额：52.34亿元-上市日期：2022-07-12
        '513180.XSHG',  # (恒指科技) [ETF]-日均成交额：36.66亿元-上市日期：2021-05-25
        '513330.XSHG',  # (恒生互联) [ETF]-日均成交额：20.45亿元-上市日期：2021-02-08
        '513750.XSHG',  # (港股非银) [ETF]-日均成交额：9.55亿元-上市日期：2023-11-27
        '159892.XSHE',  # (恒生医药ETF华夏) [ETF]-日均成交额：7.90亿元-上市日期：2021-10-19
        '513190.XSHG',  # (H股金融) [ETF]-��均成交额：3.74亿元-上市日期：2023-10-11
        '159605.XSHE',  # (中概互联ETF广发) [ETF]-日均成交额：3.19亿元-上市日期：2021-12-02
        '513630.XSHG',  # (香港红利) [ETF]-日均成交额：2.84亿元-上市日期：2023-12-08
        '159323.XSHE',  # (港股通汽车ETF华夏) [ETF]-日均成交额：1.98亿元-上市日期：2025-01-08
        '510900.XSHG',  # (恒生中国) [ETF]-日均成交额：1.46亿元-上市日期：2012-10-22
        '513920.XSHG',  # (央企40) [ETF]-日均成交额：1.38亿元-上市日期：2024-01-05
        '513970.XSHG',  # (恒生消费) [ETF]-日均成交额：0.82亿元-上市日期：2023-04-21
#指数ETF：        
        '511380.XSHG',  # (转债ETF) [ETF]-日均成交额：115.92亿元-上市日期：2020-04-07
        '512050.XSHG',  # (A500E) [ETF]-日均成交额：48.05亿元-上市日期：2024-11-15
        '510500.XSHG',  # (500ETF) [ETF]-日均成交额：45.45亿元-上市日期：2013-03-15
        '159915.XSHE',  # (创业板ETF易方达) [ETF]-日均成交额：43.55亿元-上市日期：2011-12-09
        '510300.XSHG',  # (300ETF) [ETF]-日均成交额：34.60亿元-上市日期：2012-05-28
        '512100.XSHG',  # (1000ETF) [ETF]-日均成交额：25.26亿元-上市日期：2016-11-04
        '159949.XSHE',  # (创业板50ETF华安) [ETF]-日均成交额：16.52亿元-上市日期：2016-07-22
        '588080.XSHG',  # (科创板50) [ETF]-日均成交额：13.32亿元-上市日期：2020-11-16
        '159967.XSHE',  # (创业板成长ETF华夏) [ETF]-日均成交额：5.29亿元-上市日期：2019-07-15
        '588220.XSHG',  # (科创100F) [ETF]-日均成交额：5.01亿元-上市日期：2023-09-15
        '563300.XSHG',  # (中证2000) [ETF]-日均成交额：4.13亿元-上市日期：2023-09-14
        '510760.XSHG',  # (上证ETF) [ETF]-日均成交额：1.45亿元-上市日期：2020-09-09
#行业ETF：
        '588200.XSHG',  # (科创芯片) [ETF]-日均成交额：28.07亿元-上市日期：2022-10-26
        '515880.XSHG',  # (通信ETF) [ETF]-日均成交额：22.39亿元-上市日期：2019-09-06
        '159981.XSHE',  # (能源化工ETF建信) [ETF]-日均成交额：21.63亿元-上市日期：2020-01-17
        '512880.XSHG',  # (证券ETF) [ETF]-日均成交额：16.21亿元-上市日期：2016-08-08
        '513350.XSHG',  # (油气ETF) [ETF]-日均成交额：15.66亿元-上市日期：2023-11-28
        '159326.XSHE',  # (电网设备ETF华夏) [ETF]-日均成交额：14.86亿元-上市日期：2024-09-09
        '159516.XSHE',  # (半导体设备ETF国泰) [ETF]-日均成交额：14.23亿元-上市日期：2023-07-27
        '159206.XSHE',  # (卫星ETF永赢) [ETF]-日均成交额：13.87亿元-上市日期：2025-03-14
        '512480.XSHG',  # (半导体) [ETF]-日均成交额：13.07亿元-上市日期：2019-06-12
        '159363.XSHE',  # (创业板人工智能ETF华宝) [ETF]-日均成交额：10.50亿元-上市日期：2024-12-16
        '159870.XSHE',  # (化工ETF鹏华) [ETF]-日均成交额：10.03亿元-上市日期：2021-03-03
        '512400.XSHG',  # (有色ETF) [ETF]-日均成交额：9.97亿元-上市日期：2017-09-01
        '159755.XSHE',  # (电池ETF广发) [ETF]-日均成交额：8.58亿元-上市日期：2021-06-24
        '588170.XSHG',  # (科创半导) [ETF]-日均成交额：7.74亿元-上市日期：2025-04-08
        '159992.XSHE',  # (创新药ETF银华) [ETF]-日均成交额：7.59亿元-上市日期：2020-04-10
        '159995.XSHE',  # (芯片ETF华夏) [ETF]-日均成交额：7.51亿元-上市日期：2020-02-10
        '512890.XSHG',  # (红利低波) [ETF]-日均成交额：6.79亿元-上市日期：2019-01-18
        '515220.XSHG',  # (煤炭ETF) [ETF]-日均成交额：6.44亿元-上市日期：2020-03-02
        '159566.XSHE',  # (储能电池ETF易方达) [ETF]-日均成交额：6.31亿元-上市日期：2024-02-08
        '159819.XSHE',  # (人工智能ETF易方达) [ETF]-日均成交额：6.26亿元-上市日期：2020-09-23
        '512800.XSHG',  # (银行ETF) [ETF]-日均成交额：6.13亿元-上市日期：2017-08-03
        '512690.XSHG',  # (酒ETF) [ETF]-日均成交额：5.99亿元-上市日期：2019-05-06
        '515050.XSHG',  # (5GETF) [ETF]-日均成交额：5.93亿元-上市日期：2019-10-16
        '562500.XSHG',  # (机器人) [ETF]-日均成交额：5.83亿元-上市日期：2021-12-29
        '512170.XSHG',  # (医疗ETF) [ETF]-日均成交额：5.63亿元-上市日期：2019-06-17
        '517520.XSHG',  # (黄金股) [ETF]-日均成交额：5.01亿元-上市日期：2023-11-01
        '159869.XSHE',  # (游戏ETF华夏) [ETF]-日均成交额：4.77亿元-上市日期：2021-03-05
        '512070.XSHG',  # (证券保险) [ETF]-日均成交额：4.61亿元-上市日期：2014-07-18
        '159611.XSHE',  # (电力ETF广发) [ETF]-日均成交额：4.42亿元-上市日期：2022-01-07
        '562800.XSHG',  # (稀有金属) [ETF]-日均成交额：4.39亿元-上市日期：2021-09-27
        '515120.XSHG',  # (创新药) [ETF]-日均成交额：4.34亿元-上市日期：2021-01-04
        '512010.XSHG',  # (医药ETF) [ETF]-日均成交额：4.27亿元-上市日期：2013-10-28
        '510880.XSHG',  # (红利ETF) [ETF]-日均成交额：3.97亿元-上市日期：2007-01-18
        '515790.XSHG',  # (光伏ETF) [ETF]-日均成交额：3.87亿元-上市日期：2020-12-18
        '515980.XSHG',  # (人工智能) [ETF]-日均成交额：3.78亿元-上市日期：2020-02-10
        '512660.XSHG',  # (军工ETF) [ETF]-日均成交额：3.75亿元-上市日期：2016-08-08
        '159928.XSHE',  # (消费ETF汇添富) [ETF]-日均成交额：3.66亿元-上市日期：2013-09-16
        '512710.XSHG',  # (军工龙头) [ETF]-日均成交额：3.60亿元-上市日期：2019-08-26
        '560860.XSHG',  # (工业有色) [ETF]-日均成交额：3.57亿元-上市日期：2023-03-13
        '515030.XSHG',  # (新汽车) [ETF]-日均成交额：3.33亿元-上市日期：2020-03-04
        '159766.XSHE',  # (旅游ETF富国) [ETF]-日均成交额：3.30亿元-上市日期：2021-07-23
        '159218.XSHE',  # (卫星ETF招商) [ETF]-日均成交额：3.21亿元-上市日期：2025-05-22
        '159852.XSHE',  # (软件ETF嘉实) [ETF]-日均成交额：3.19亿元-上市日期：2021-02-09
        '516160.XSHG',  # (新能源) [ETF]-日均成交额：3.07亿元-上市日期：2021-02-04
        '516150.XSHG',  # (稀土基金) [ETF]-日均成交额：3.03亿元-上市日期：2021-03-17
        '159227.XSHE',  # (航空航天ETF华夏) [ETF]-日均成交额：2.98亿元-上市日期：2025-05-16
        '159583.XSHE',  # (通信ETF富国) [ETF]-日均成交额：2.93亿元-上市日期：2024-07-08
        '588790.XSHG',  # (科创智能) [ETF]-日均成交额：2.62亿元-上市日期：2025-01-09
        '159865.XSHE',  # (养殖ETF国泰) [ETF]-日均成交额：2.44亿元-上市日期：2021-03-08
        '512980.XSHG',  # (传媒ETF) [ETF]-日均成交额：2.43亿元-上市日期：2018-01-19
        '159851.XSHE',  # (金融科技ETF华宝) [ETF]-日均成交额：2.27亿元-上市日期：2021-03-19
        '561360.XSHG',  # (石油ETF) [ETF]-日均成交额：2.04亿元-上市日期：2023-10-31
        '561980.XSHG',  # (芯片设备) [ETF]-日均成交额：2.01亿元-上市日期：2023-09-01
        '562590.XSHG',  # (半导材料) [ETF]-日均成交额：1.76亿元-上市日期：2023-10-18
        '512200.XSHG',  # (地产ETF) [ETF]-日均成交额：1.71亿元-上市日期：2017-09-25
        '159732.XSHE',  # (消费电子ETF华夏) [ETF]-日均成交额：1.62亿元-上市日期：2021-08-23
        '159667.XSHE',  # (工业母机ETF国泰) [ETF]-日均成交额：1.58亿元-上市日期：2022-10-26
        '516510.XSHG',  # (云计算) [ETF]-日均成交额：1.49亿元-上市日期：2021-04-07
        '159840.XSHE',  # (锂电池ETF工银) [ETF]-日均成交额：1.42亿元-上市日期：2021-08-20
        '159998.XSHE',  # (计算机ETF天弘) [ETF]-日均成交额：1.30亿元-上市日期：2020-04-13
        '159825.XSHE',  # (农业ETF富国) [ETF]-日均成交额：1.15亿元-上市日期：2020-12-29
        '512670.XSHG',  # (国防ETF) [ETF]-日均成交额：1.12亿元-上市日期：2019-08-01
        '159883.XSHE',  # (医疗器械ETF永赢) [ETF]-日均成交额：1.05亿元-上市日期：2021-04-30
        '515210.XSHG',  # (钢铁ETF) [ETF]-日均成交额：1.01亿元-上市日期：2020-03-02
        '515400.XSHG',  # (大数据) [ETF]-日均成交额：0.94亿元-上市日期：2021-01-20
        '159256.XSHE',  # (创业板软件ETF华夏) [ETF]-日均成交额：0.83亿元-上市日期：2025-08-04
        '561330.XSHG',  # (矿业ETF) [ETF]-日均成交额：0.83亿元-上市日期：2022-11-01
        '515170.XSHG',  # (食品饮料) [ETF]-日均成交额：0.67亿元-上市日期：2021-01-13
        '159638.XSHE',  # (高端装备ETF嘉实) [ETF]-日均成交额：0.56亿元-上市日期：2022-08-12
        '516520.XSHG',  # (智能驾驶) [ETF]-日均成交额：0.47亿元-上市日期：2021-03-01
        '513360.XSHG',  # (教育ETF) [ETF]-日均成交额：0.43亿元-上市日期：2021-06-17
        '516190.XSHG',  # (文娱ETF) [ETF]-日均成交额：0.18亿元-上市日期：2021-09-17
    ]
    # 固定ETF池 = 全球池 + 中国池（正常期使用）
    g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool

    g.avg_etf_money_threshold = None
    # 全市场近3日 ETF 日均总成交额 avg_total_money；门槛 = avg_total_money / 分母（原硬编码 20000）
    g.global_liquidity_threshold_divisor = 20000
    g.filtered_fixed_pool = []
    g.dynamic_etf_pool = []
    g.merged_etf_pool = []
    g.ranked_etfs_result = []
    g.filtered_global_pool = []
    
    # 三态市场：走弱期 / 正常期 / 震荡期（每日 09:40 判定，全日有效）
    g.market_regime = '震荡期'
    g.regime_prev_day = None           # 上一交易日早盘判定结果（用于切换/反复跳跃日志）
    g.regime_prev_prev_day = None      # 上上交易日早盘判定结果
    g.regime_flip_flop_count = 0       # 「隔日跳回」A→B→A 累计次数（整个回测）
    # 指标与生效不一致时：需连续 N 个交易日指标均为「目标状态」才真正切换（默认 2，减轻一日游/死猫跳）
    g.regime_switch_confirm_days = 2
    g.regime_switch_pending_raw = None    # 待确认的指标状态
    g.regime_switch_pending_streak = 0    # 已连续多少个交易日指标均为 pending_raw
    g.regime_last_change_date = None      # 最近一次生效状态切换日
    g.normal_ma_lookback = 10          # 正常期广度：站上 MA10 的指数个数
    g.regime_ma20_lookback = 20        # 走弱判定用的 MA20 周期（日）
    # 六指数齐备时：below_ma20 计数 ≥ 此值 → 走弱期；above_ma10 计数 ≥ 此值 → 正常期（且未触发走弱）
    g.regime_weak_below_ma20_min = 4   # 默认 6 即「六指均跌破 MA20」
    g.regime_normal_above_ma10_min = 4

    # 震荡期高斯滤波（对齐五福35）
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002  # 绝对斜率 g1-g2 时的阈值（gaussian_use_relative_slope=False）
    # True：斜率改为 (g1-g2)/g2，与拉普拉斯相对斜率口径一致，便于低价标的公平比较；False：沿用原绝对差
    g.gaussian_use_relative_slope = True
    g.gaussian_min_slope_relative = 0.0013  # 相对斜率阈值（仅 gaussian_use_relative_slope=True 时参与比较）

    # 回测全周期：各状态累计交易日与当日净值复利因子（收盘 after_close 更新）
    g.regime_day_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_return_factors = {'正常期': 1.0, '震荡期': 1.0, '走弱期': 1.0}
    # 有上一日净值可比时：各状态下日收益为正/负/平的天数，及日收益率算术累加（不含首日）
    g.regime_win_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_loss_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_flat_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_sum_pos_daily_ret = {'正常期': 0.0, '震荡期': 0.0, '走弱期': 0.0}
    g.regime_sum_neg_daily_ret = {'正常期': 0.0, '震荡期': 0.0, '走弱期': 0.0}
    g.prev_eod_portfolio_value = None

    g.holdings_num = 1
    g.holdings_num_normal = 1
    g.holdings_num_oscillation = 1
    g.holdings_num_weak = 1
    g.defensive_etf = "511880.XSHG"
    g.min_money = 10
    g.target_etfs_list = []
    g.trade_entry_open = {}
    g.trade_roundtrip_history = []
    # 卖出原因分类统计（P0-1）：数据缺失 / 过滤失败 / 排名落后
    g.exit_reason_stats = {
        'total': 0,
        'by_bucket': {'missing_data': 0, 'filter_fail': 0, 'rank_lag': 0, 'other': 0},
        'by_regime': {},
        'by_detail': {},
    }
    # 卖出时短动量近「三个交易日」为「增增增」的标的：下一交易日 13:10 打印区间收益与动量复盘
    g.pending_sm3up_sell_followups = []
    g.last_metrics_by_etf_code = {}

    g.etf_names_dict = {}
    g.cache_date = None
    g.yesterday_close_cache = {}

    g.lookback_days = 25
    g.min_score_threshold = 0
    g.max_score_threshold = 5
    g.score_threshold_ratio = 0.9
    g.short_momentum_lookback = 21
    g.short_momentum_min_score = 0
    g.short_momentum_max_score = 6

    # ==================== 震荡收割 / Whipsaw（参照五福35warmup，默认与震荡期联动）====================
    g.enable_smoothed_momentum_input = False
    g.smoothed_ma_window = 5
    g.smoothed_momentum_only_in_range = True
    g.enable_range_r2_veto = False
    g.r2_threshold_range_bound = 0.9
    g.enable_range_momentum_floor = False
    g.range_momentum_min = 0.0
    g.range_momentum_max = 2.0
    g.enable_range_short_momentum_limits = True
    g.range_short_momentum_min = 0.0
    g.range_short_momentum_max = 6.0
    g.enable_switch_hysteresis = False
    g.switch_buffer_normal = 0.10
    g.switch_buffer_range = 0.40
    g.enable_dual_positive_momentum = True
    g.dual_positive_only_in_range = True
    g.whipsaw_options_only_in_range = True
    g.log_whipsaw_filter_detail = True
    # 详细日志开关（默认关闭）
    g.log_pool_update_details = False      # 阈值/池更新相关详细日志
    g.log_first_step_ranking = False       # 动量第一步全量排序日志

    # ==================== 修正相关性（逻辑同 相关性.py / 五福 v3.01 文章）====================
    # P_adj = P_base × exp(-MAE(累计收益曲线)) × min(σ)/max(σ)
    g.enable_corr_pool_filter = False       # True：动态池更新时剔除与固定池修正相关性≥阈值的标的
    g.corr_pool_threshold = 0.5             # 入池：相对固定池最大 P_adj 须严格小于此值
    g.corr_lookback_days = 60               # 相关性回看交易日
    g.enable_corr_overview = True           # 第二步前检查一览中展示「相对固定池」修正相关性
    g.enable_corr_hold_guard = True         # 第四步：高相关且持仓动量偏弱时保留现仓
    g.corr_hold_threshold = 0.85             # 统一阈值模式：P_adj 超过此值则触发守卫判断
    g.corr_hold_momentum_max = 7             # 统一阈值模式：现仓动量≤此值且高相关 → 不换仓
    # ---------- 相关性守卫：仅保留两种策略 ----------
    # 策略1(统一阈值): enable_corr_regime_mom_guard=False, corr_guard_test_scheme=None
    # 策略2(方案B):    enable_corr_regime_mom_guard=True,  corr_guard_test_scheme='B'
    g.enable_corr_regime_mom_guard = True    # False→统一阈值 | True→分市场状态×动量分档(方案B)
    g.corr_regime_mom_guard_rules = None     # 非 None 时整表覆盖内置 v2 矩阵规则
    g.corr_regime_momentum_always_allow_above = 7.0   # 动量严格大于此值一律放行（各状态通用）
    g.corr_regime_mom_guard_allow_legacy_when_mom_missing = False  # 动量缺失：False=放行；True=退回统一阈值
    g.corr_guard_test_scheme = 'B'   # 方案B: 完整v2矩阵 + band_overrides；统一阈值模式请设为 None
    # 高相关换仓抑制（P0）：覆盖层 + 分档修补 + 动量豁免仅低相关
    g.enable_corr_high_pair_overlay = True
    g.corr_high_pair_block_threshold = 0.88       # 持仓 vs 目标 P_adj≥此值且动量≤overlay_mom_max → 拦截
    g.corr_high_pair_overlay_mom_max = 8.0
    g.corr_mom_exempt_requires_low_corr = True    # 动量>7 豁免须 P_adj < corr_mom_exempt_max_pair_corr
    g.corr_mom_exempt_max_pair_corr = 0.82
    g.corr_regime_band_overrides = {
        ('正常期', '[5.5,6)'): {'mode': 'intercept_if_gt', 'intercept_gt': 0.78},
        ('正常期', '[5,5.5)'): {
            'mode': 'intercept_only_in_bands',
            'intercept_bands': [{'lo': 0.85, 'hi': 0.95}],
        },
    }
    apply_corr_guard_test_scheme()  # 须在 band_overrides 等基线参数写完后调用，方案B会覆盖 overrides
    # 候选目标优选（P1）：跳过与持仓过高相关的候选
    g.pick_target_skip_high_corr = True
    g.pick_target_max_padj = 0.85
    g.anti_churn_immediate_requires_low_corr = True   # 掉池立即换股时须存在低相关候选
    g.anti_churn_immediate_max_padj = 0.85
    g.log_corr_detail = True                # 打印相关性矩阵计算与守卫决策明细
    g.enable_corr_guard_review = True       # 守卫决策后纳入「当日13:10→次日13:10」隔日复盘
    g.corr_guard_stats = _default_corr_guard_stats()
    g.pending_corr_guard_reviews = []       # 待隔日复盘队列
    g.corr_guard_review_history = []        # 最近复盘明细(供看板展示)
    g.corr_guard_all_records = []           # 全部已完成复盘(供分桶有效性分析)
    g.enable_corr_mom_padj_matrix_report = True   # 回测末日输出动量×P_adj分状态矩阵
    g.corr_mom_padj_matrix_min_cell_n = 1         # 单元格最少样本，不足则显示 n=xx

    g.enable_r2_filter = True
    g.r2_threshold = 0.4
    g.enable_ma_filter = True
    g.ma_lookback = 10
    g.ma_threshold = 1.0001
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 1.8
    # 量比阈值缓冲带（默认关闭；开启后在 [threshold, threshold+buffer) 内仍视为通过）
    g.enable_volume_threshold_buffer = True
    g.volume_threshold_buffer = 0.1
    g.enable_loss_filter = True
    g.loss = 0.97
    g.enable_premium_filter = False
    g.max_premium_rate = 30
    g.enable_laplace_filter = True
    g.laplace_s_param = 0.05
    # True：按市场状态差异化拉普拉斯滤波平滑系数 s（v32：正常期偏松减噪、走弱期更松保趋势）；False：全局统一用 laplace_s_param（旧版 0.05）
    g.enable_laplace_s_regime_differentiation = True
    g.laplace_s_param_normal = 0.06   # 正常期 s（较 0.05 略宽松，减少震荡误杀）
    g.laplace_s_param_weak = 0.12     # 走弱期 s（更宽松，减轻海外 ETF 强趋势被过度平滑）
    g.laplace_min_slope = 0.002
    # P0-2 参数补丁（可回滚）：仅正常期放宽 R²，降低边缘误杀
    g.enable_p0_state_tuning_patch = True
    g.normal_r2_threshold_override = 0.39

    # 走弱期是否参与各过滤：True=走弱期与正常/震荡同样对待该步；False=走弱期跳过该步（与 v3-1 对齐的默认见下方）
    g.weak_apply_r2_filter = False       # False=走弱期不做 R²（同 五福51-v3-1）；True=走弱期也筛 R²（v3-2 新行为）
    g.weak_apply_ma_filter = True
    g.weak_apply_volume_filter = True
    g.weak_apply_loss_filter = True
    g.weak_apply_premium_filter = False   # True=全局开溢价时走弱期也筛（同 v3-1）；False=走弱期不筛溢价
    g.weak_apply_laplace_filter = True  # False=仅正常期拉普拉斯（同 v3-1）；True=走弱期也参与拉普拉斯

    # 正常/震荡/走弱期防频换：当前持仓连续未重返「当日目标持仓数 TopK」达到阈值后才强制换股
    # 兼容 holdings_num=1 与 holdings_num>1（多持仓时按每只ETF分别累计 streak）
    g.normal_max_days_not_rank1 = 5
    # 多持仓(holdings_num>1)时，正常/震荡期分别使用独立阈值，默认与单持仓阈值一致
    g.normal_max_days_not_topk = 5
    g.oscillation_max_days_not_topk = 5
    g.normal_not_rank1_streak = 0       # 当前持仓连续「在候选池但非全表第1名」的交易日数
    g.normal_streak_hold_code = None    # streak 绑定的持仓代码
    g.normal_not_topk_streaks = {}      # 多持仓防频换：{etf: 连续未进TopK天数}
    # True：震荡期启用与正常期相同的防频换逻辑（共用 streak、normal_max_days_not_rank1）
    g.oscillation_anti_churn_enabled = True
    # True：走弱期启用与正常期相同的防频换逻辑（共用 streak、normal_max_days_not_rank1）
    g.weak_anti_churn_enabled = True

    g.max_portfolio_value = 0
    g.drawdown_threshold = 0.03
    # ---------- 组合回撤分级动作（在 monitor_drawdown 中，默认关闭，与旧回测一致）----------
    # 总开关：True 时，在已有「≥drawdown_threshold 预警日志」之外，按阈值执行减仓/切防御/清仓
    g.enable_drawdown_risk_actions = True
    # 分级阈值（相对历史最高净值 g.max_portfolio_value 的回撤比例）；须满足 high > mid > low > drawdown_threshold
    g.dd_half_position_threshold = 0.10      # ≥此：按可卖数量保留 dd_partial_close_keep_fraction，其余卖出
    g.dd_switch_defensive_threshold = 0.12 # ≥此：清仓非防御标的（防御可用时）；否则仅打日志
    g.dd_flat_threshold = 0.20               # ≥此：全部可卖标的清仓
    g.dd_partial_close_keep_fraction = 0.50  # 减半仓时保留「可卖股数」的比例（0~1）
    # 同一自然日最多触发一档组合回撤动作（避免与其它定时任务重复冲击）
    g.dd_action_cooldown_date = None
    # 执行任意一档动作后，是否将 g.max_portfolio_value 重置为当前净值（避免空仓后仍相对历史峰值天天触发高档）
    g.dd_reset_peak_after_action = True
    # 回撤监控触发时刻（聚宽 run_daily）：勿用 09:00——尚未连续竞价，QDII/LOF 常见 10:30 起才有场内成交价
    g.dd_monitor_time = '10:31'
    # True：用 get_current_data().last_price×持仓数量 + 现金 重估组合市值算回撤（场内成交价口径，避免盘前/净值错觉）
    g.dd_valuation_use_mtm_last_price = True

    g.use_fixed_stop_loss = True
    g.fixedStopLossThreshold = 0.91
    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95
    # 午盘买卖分时：False=13:10 同刻先卖后买（原逻辑）；True=13:10 卖、13:11 买
    g.enable_split_afternoon_trades = True
    g.afternoon_sell_time = '13:10'
    g.afternoon_buy_time = '13:11'
    # 当日午盘买入前发生的「分钟止损」成功后，若干交易日内禁止买回同一标的（可调）
    g.enable_stop_loss_rebuy_cooldown = True
    # 止损日期的次一交易日起计，连续 N 个交易日不得买入（默认 2：约等价于「两天内不接」）
    g.stop_loss_rebuy_cooldown_trade_days = 2
    # 仅统计此时刻之前的止损（应与午盘买入时刻一致，由开关自动对齐）
    g.stop_loss_rebuy_cutoff_time = (
        g.afternoon_buy_time if g.enable_split_afternoon_trades else g.afternoon_sell_time
    )
    g.stop_loss_rebuy_first_allowed_date = {}  # code -> 首个允许再买回的交易日 date

    # ============================================================
    # 固化当前最优参数组合（移除实验 case 切换）
    # ============================================================
    g.S2_enable_consecutive_filter_fail_to_defensive = True
    g.S2_consecutive_filter_fail_days = 4
    g.S2_filter_fail_streak = 0
    g.S2_filter_fail_last_signal_date = None

    g.S4_enable_dd_regime_specific = True
    g.S4_dd_half_position_threshold_weak = 0.05
    g.S4_dd_switch_defensive_threshold_weak = 0.08
    g.S4_dd_flat_threshold_weak = 0.12
    g.S4_dd_half_position_threshold_oscillation = None
    g.S4_dd_switch_defensive_threshold_oscillation = None
    g.S4_dd_flat_threshold_oscillation = None

    # B4：状态切换日禁用立即换股（最优配置保留）
    g.B4_disable_immediate_swap_on_regime_change = True
    _corr_overrides = copy.deepcopy(getattr(g, 'corr_regime_band_overrides', {}) or {})
    _corr_overrides[('震荡期', '[0,2)')] = {'mode': 'intercept_if_gt', 'intercept_gt': 0.30}
    _corr_overrides[('震荡期', '[2,3)')] = {'mode': 'intercept_if_gt', 'intercept_gt': 0.30}
    g.corr_regime_band_overrides = _corr_overrides

    # B2：正常期拉普拉斯最小斜率覆盖（当前最优为 0.0022）
    g.exp_enable_normal_laplace_min_slope_override = True
    g.exp_normal_laplace_min_slope_override = 0.0022

    _fixed_profile_notes = [
        'B4: 状态切换日禁立即换股=True',
        'P0: 震荡期[0,2)拦截阈值=0.30',
        'P0: 震荡期[2,3)拦截阈值=0.30',
        'B2: 正常期拉普拉斯最小斜率覆盖=0.0022',
    ]

    # 动量上限软处理（默认关闭）：
    # 当动量分超过 max_score_threshold 时，不直接剔除，而是用“排序分”降权参与排序
    g.enable_momentum_soft_cap = False
    g.momentum_soft_cap_penalty = 0.05  # 排序分=max + (raw-max)*penalty
    g.momentum_soft_cap_normal_only = True
    # 防御切换确认（默认关闭）：
    # 当日无排名结果且目标为防御ETF时，需要连续 N 个交易日信号成立才切换
    g.enable_defensive_switch_confirm = False
    g.defensive_switch_confirm_days = 2
    g.defensive_switch_pending_streak = 0
    g.defensive_switch_last_signal_date = None
    
    # 市场状态逐指数明细日志开关（默认关闭，避免 log.txt 过长）
    g.log_market_status_details = False

    # 持仓 14:50 跌破日 K 的 MA5/MA10/MA20/MA30（均线用截至昨收的收盘序列）→ 统计至次一交易日收盘的价差收益
    g.enable_holdings_ma_break_nextday_stats = True
    g.ma_break_nextday_pending = []  # 待结算记录，after_close 与 signal 日对齐
    g.ma_break_nextday_stats = {
        'ma5': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
        'ma10': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
        'either_5_10': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
        'ma20': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
        'ma30': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
        'either': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
    }

    set_benchmark("510300.XSHG")
    run_daily(morning_routine, time='09:00')
    run_daily(drawdown_monitor_routine, time=getattr(g, 'dd_monitor_time', '10:31'))
    run_daily(check_weak_period_daily, time='09:40')
    if getattr(g, 'enable_split_afternoon_trades', False):
        run_daily(afternoon_sell_routine, time=getattr(g, 'afternoon_sell_time', '13:10'))
        run_daily(afternoon_buy_routine, time=getattr(g, 'afternoon_buy_time', '13:11'))
    else:
        run_daily(afternoon_routine, time=getattr(g, 'afternoon_sell_time', '13:10'))
    run_daily(holdings_ma_break_1450_check, time='14:50')
    run_daily(reset_daily_flags, time='15:10')
    run_daily(minute_level_stop_loss, time='every_bar')
    run_daily(minute_level_pct_stop_loss, time='every_bar')
# 注册：在回测最后一天收盘后执行
    run_daily(record_daily_positions_to_storage, time='15:30')  # 每天记录到缓存
    run_daily(after_close_regime_statistics, time='after_close')  # 收盘后更新状态累计天数与收益（收盘净值）
    run_daily(output_all_positions_summary, time='after_close')  # 最后一天汇总输出
    
    log.info(f"""
【策略参数初始化完成】
=== ETF池配置 ===
- 全球/海外ETF池: {len(g.global_etf_pool)}只
- 国内ETF池: {len(g.china_etf_pool)}只
- 固定池合计: {len(g.fixed_etf_pool)}只
- 流动性门槛分母: {g.global_liquidity_threshold_divisor}（门槛=全市场日均ETF总成交额/分母，可调 g.global_liquidity_threshold_divisor）
=== 三态市场判定（每日，六指数） ===
- 指数: 沪深300、399101、创业板、中证A500、中证1000、国证2000(399303 代中证2000；聚宽无932000)
- 走弱期: ≥{g.regime_weak_below_ma20_min} 只指数收盘 < 各自MA{g.regime_ma20_lookback}（可调 g.regime_weak_below_ma20_min）
- 正常期: 未触发走弱 且 ≥{g.regime_normal_above_ma10_min} 只收盘 > 各自MA{g.normal_ma_lookback}（可调 g.regime_normal_above_ma10_min）
- 震荡期: 其余；六指数任一条数据不足时指标口径默认震荡
- 震荡期选股: 高斯滤波 σ={g.gaussian_sigma}, 斜率{'相对' if getattr(g, 'gaussian_use_relative_slope', False) else '绝对'}≥{g.gaussian_min_slope_relative if getattr(g, 'gaussian_use_relative_slope', False) else g.gaussian_min_slope}
- 状态切换确认: 指标与生效不一致时，连续 {g.regime_switch_confirm_days} 个交易日指标口径相同才切换（g.regime_switch_confirm_days=1 即次日确认）
=== 动量得分过滤 ===
- 周期: {g.lookback_days}天
- 得分阈值: [{g.min_score_threshold}, {g.max_score_threshold}]
- 调仓系数: {g.score_threshold_ratio}
=== 过滤条件 ===
- 正常期 R²过滤: {'启用' if g.enable_r2_filter else '禁用'} (基阈值>{g.r2_threshold:.2f}{f", 正常期覆盖>{g.normal_r2_threshold_override:.2f}" if getattr(g, 'enable_p0_state_tuning_patch', False) else ""}) + 拉普拉斯
- 震荡期 R²过滤: {'启用' if g.enable_r2_filter else '禁用'} + 高斯滤波
- 走弱期 R²过滤: {'启用' if g.enable_r2_filter and getattr(g, 'weak_apply_r2_filter', False) else '禁用'} (基阈>{g.r2_threshold:.2f}；走弱期是否参与见 g.weak_apply_r2_filter)
- 走弱期可切换过滤: R² g.weak_apply_r2_filter={getattr(g, 'weak_apply_r2_filter', False)} | 均线 g.weak_apply_ma_filter={getattr(g, 'weak_apply_ma_filter', False)} | 量比 g.weak_apply_volume_filter={getattr(g, 'weak_apply_volume_filter', False)} | 短期风控 g.weak_apply_loss_filter={getattr(g, 'weak_apply_loss_filter', False)} | 溢价 g.weak_apply_premium_filter={getattr(g, 'weak_apply_premium_filter', False)} | 拉普拉斯 g.weak_apply_laplace_filter={getattr(g, 'weak_apply_laplace_filter', False)}
- 走弱期 均线过滤: 全局 enable_ma_filter={'启用' if g.enable_ma_filter else '禁用'}；走弱期管线是否启用均线见 g.weak_apply_ma_filter（MA{g.ma_lookback}×{g.ma_threshold}）
- 通用 成交量过滤: {'启用' if g.enable_volume_check else '禁用'} (近{g.volume_lookback}日均量比<{g.volume_threshold:.1f})
- 量比缓冲带: {'启用' if g.enable_volume_threshold_buffer else '禁用'} (buffer={g.volume_threshold_buffer:.2f})
- 通用 短期风控: {'启用' if g.enable_loss_filter else '禁用'} (近3日单日跌幅<{1-g.loss:.0%})
- 通用 溢价率过滤: {'启用' if g.enable_premium_filter else '禁用'} (阈值≤{g.max_premium_rate}%)
- 正常期 拉普拉斯滤波: {'启用' if g.enable_laplace_filter else '禁用'} ({f"差异化 s 正常期={getattr(g, 'laplace_s_param_normal', 0.07):.2f}/走弱期={getattr(g, 'laplace_s_param_weak', 0.10):.2f}" if getattr(g, 'enable_laplace_s_regime_differentiation', False) else f"统一 s={g.laplace_s_param:.2f}"}, 基阈值≥{g.laplace_min_slope}{f", 正常期覆盖≥{g.exp_normal_laplace_min_slope_override}" if getattr(g, 'exp_enable_normal_laplace_min_slope_override', False) else ""}; 开关 g.enable_laplace_s_regime_differentiation)
=== 防频繁换股（正常期默认启用） ===
- 候选池内非第1名可继续持有；掉出候选池立即换股
- 连续未重返过筛第1名 ≥ {g.normal_max_days_not_rank1} 个交易日 → 换为候选池第1名
- 多持仓时：正常期阈值={getattr(g, 'normal_max_days_not_topk', g.normal_max_days_not_rank1)}，震荡期阈值={getattr(g, 'oscillation_max_days_not_topk', g.normal_max_days_not_rank1)}；按目标持仓数 TopK 逐持仓累计，连续未进 TopK 达阈值才替换（掉出候选池仍立即替换）
- 震荡期防频换: {'启用' if g.oscillation_anti_churn_enabled else '关闭'}（开关 g.oscillation_anti_churn_enabled，与正常期共用 streak）
- 走弱期防频换: {'启用' if g.weak_anti_churn_enabled else '关闭'}（开关 g.weak_anti_churn_enabled，与正常期共用 streak）
=== 震荡期 Whipsaw（总开关仅震荡期={g.whipsaw_options_only_in_range}） ===
- 短期动量: {g.short_momentum_lookback}日 得分∈[{g.short_momentum_min_score},{g.short_momentum_max_score}]；震荡期短期区间: {'开' if g.enable_range_short_momentum_limits else '关'} [{g.range_short_momentum_min},{g.range_short_momentum_max}]
- [1]平滑输入: {'开' if g.enable_smoothed_momentum_input else '关'} MA={g.smoothed_ma_window}
- [2]震荡R²加码: {'开' if g.enable_range_r2_veto else '关'} (震荡阈>{g.r2_threshold_range_bound} vs 基阈{g.r2_threshold})
- [3]震荡长动量区间: {'开' if g.enable_range_momentum_floor else '关'} [{g.range_momentum_min},{g.range_momentum_max}]
- [4]换仓滞回: {'开' if g.enable_switch_hysteresis else '关'} 正常{g.switch_buffer_normal:.0%} / 震荡{g.switch_buffer_range:.0%}
- [5]长短双正: {'开' if g.enable_dual_positive_momentum else '关'} (仅震荡={g.dual_positive_only_in_range})
- 动量上限软处理: {'开' if g.enable_momentum_soft_cap else '关'} (penalty={g.momentum_soft_cap_penalty:.2f}, 仅正常期={getattr(g, 'momentum_soft_cap_normal_only', True)})
=== 止损机制 ===
- 分钟级固定比例止损: {'启用' if g.use_fixed_stop_loss else '禁用'} (成本价×{g.fixedStopLossThreshold:.0%})
- 分钟级当日跌幅止损: {'启用' if g.use_pct_stop_loss else '禁用'} (昨收×{g.pct_stop_loss_threshold:.0%})
- 止损买回冷却: {'启用' if getattr(g, 'enable_stop_loss_rebuy_cooldown', False) else '禁用'}（{getattr(g, 'stop_loss_rebuy_cutoff_time', '13:10')} 前触发且下单成功→禁买 {getattr(g, 'stop_loss_rebuy_cooldown_trade_days', 2)} 个交易日）
- 午盘买卖分时: {'开' if getattr(g, 'enable_split_afternoon_trades', False) else '关'}（关= {getattr(g, 'afternoon_sell_time', '13:10')} 同刻先卖后买；开= 卖 {getattr(g, 'afternoon_sell_time', '13:10')} / 买 {getattr(g, 'afternoon_buy_time', '13:11')}）
=== 组合回撤分级动作（g.enable_drawdown_risk_actions）===
- 开关: {'启用' if getattr(g, 'enable_drawdown_risk_actions', False) else '禁用'}（默认关闭；开启后在 g.dd_monitor_time 在预警日志外可减仓，默认 10:31 避开盘前无效时点）
- 回撤监控时刻: {getattr(g, 'dd_monitor_time', '10:31')}  | 场内 last_price 重估市值: {'是' if getattr(g, 'dd_valuation_use_mtm_last_price', True) else '否'}
- 减半仓阈值: ≥{getattr(g, 'dd_half_position_threshold', 0.10):.0%}  | 切防御阈值: ≥{getattr(g, 'dd_switch_defensive_threshold', 0.15):.0%}  | 全清阈值: ≥{getattr(g, 'dd_flat_threshold', 0.20):.0%}
- 减半仓保留可卖比例: {getattr(g, 'dd_partial_close_keep_fraction', 0.5):.0%}  | 动作后重置峰值: {'是' if getattr(g, 'dd_reset_peak_after_action', True) else '否'}
=== 修正相关性（同 相关性.py）===
- 动态池入池筛: {'开' if g.enable_corr_pool_filter else '关'} (vs固定池 max P_adj < {g.corr_pool_threshold}, 回看{g.corr_lookback_days}日)
- 第二步一览: {'开' if g.enable_corr_overview else '关'} | 明细日志 g.log_corr_detail={'开' if g.log_corr_detail else '关'}
- 持仓守卫: {'开' if g.enable_corr_hold_guard else '关'} ({_corr_regime_mom_guard_mode_desc()})
- 守卫预设: {_corr_guard_test_scheme_desc()}
- 高相关覆盖层: {'开' if getattr(g, 'enable_corr_high_pair_overlay', False) else '关'} (P_adj≥{getattr(g, 'corr_high_pair_block_threshold', 0.88):.2f} 且动量≤{getattr(g, 'corr_high_pair_overlay_mom_max', 8):.1f}→拦截)
- 动量豁免: {'须低相关' if getattr(g, 'corr_mom_exempt_requires_low_corr', False) else '一律'} (>{getattr(g, 'corr_regime_momentum_always_allow_above', 7):.1f} 且 P_adj<{getattr(g, 'corr_mom_exempt_max_pair_corr', 0.82):.2f} 才豁免)
- 候选低相关优选: {'开' if getattr(g, 'pick_target_skip_high_corr', False) else '关'} (max P_adj<{getattr(g, 'pick_target_max_padj', 0.85):.2f}) | 掉池换股须低相关候选: {'开' if getattr(g, 'anti_churn_immediate_requires_low_corr', False) else '关'}
- 隔日复盘: {'开' if g.enable_corr_guard_review else '关'} (拦截/低相关放行/动量豁免 均登记；决策日13:10→次日13:10 持有vs候选收益差)
- 动量×P_adj矩阵: {'开' if g.enable_corr_mom_padj_matrix_report else '关'} (回测末日按正常/震荡/走弱期输出拦截表现与最优阈值)
=== 固化参数（最优组合）===
- 生效项: {'; '.join(_fixed_profile_notes)}
=== 其他配置 ===
- 持仓数量(动态): 正常期{g.holdings_num_normal}只 / 震荡期{g.holdings_num_oscillation}只 / 走弱期{g.holdings_num_weak}只
- 防御ETF: {g.defensive_etf}
- 防御切换确认: {'启用' if g.enable_defensive_switch_confirm else '禁用'} (连续{g.defensive_switch_confirm_days}日)
- 最小交易额: {g.min_money}元
- 基准: 510300.XSHG
""")


def check_weak_period_daily(context):
    resolve_market_regime(context)
    midday_routine(context)


def drawdown_monitor_routine(context):
    """组合回撤：在连续竞价后执行，用场内 last_price 估值（见 g.dd_valuation_use_mtm_last_price）。"""
    log.info("★" * 40)
    log.info(f"▶️ 【回撤监控·盘中】{context.current_dt.strftime('%H:%M')} 启动…")
    monitor_drawdown(context)
    log.info("⏸️ 【回撤监控·盘中】执行完毕！")


def morning_routine(context):
    _ensure_corr_globals()
    log.info("★" * 80)
    log.info("▶️ 【晨间流水线】启动...")
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)
    log.info(
        f"【回撤监控】已移至盘中定时任务（默认 {getattr(g, 'dd_monitor_time', '10:31')}），"
        "避免开盘前无连续竞价价；QDII/LOF 请以该时点场内价口径为准。"
    )
    if getattr(g, 'log_pool_update_details', False):
        log.info("【流动性阈值】计算全市场ETF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("⏸️ 【晨间流水线】执行完毕！")


def refresh_holdings_num_by_regime(context):
    regime = getattr(g, 'market_regime', '震荡期')
    prev = int(getattr(g, 'holdings_num', 1))
    target_map = {
        '正常期': int(getattr(g, 'holdings_num_normal', prev)),
        '震荡期': int(getattr(g, 'holdings_num_oscillation', prev)),
        '走弱期': int(getattr(g, 'holdings_num_weak', prev)),
    }
    new_holdings = max(1, target_map.get(regime, prev))
    g.holdings_num = new_holdings
    if new_holdings != prev:
        log.info(f"🧭 【持仓数切换】状态={regime}，holdings_num: {prev} → {new_holdings}")
    else:
        log.info(f"🧭 【持仓数】状态={regime}，holdings_num={new_holdings}")


def midday_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【早盘流水线】启动...")
    
    if g.market_regime == '走弱期':
        log.info(f"🔴 【走弱期池更新】仅对全球/海外ETF池进行流动性过滤...")
        filter_global_pool_by_volume(context)
        log.info(f"【走弱期池更新完成】过滤后全球池: {len(g.filtered_global_pool)}只")
    else:
        log.info(f"🟢 【{g.market_regime}池更新】执行动态池更新、固定池过滤、合并池...")
        if getattr(g, 'log_pool_update_details', False):
            log.info("【动态池更新】更新行业ETF动态池（各行业流动性最佳ETF）...")
        update_sector_pool(context)
        if getattr(g, 'log_pool_update_details', False):
            log.info("【固定池过滤】过滤固定ETF池流动性...")
        filter_fixed_pool_by_volume(context)
        if getattr(g, 'log_pool_update_details', False):
            log.info("【合并池】合并固定池与动态池...")
        daily_merge_etf_pools(context)
        log.info(f"【{g.market_regime}池更新完成】合并池: {len(g.merged_etf_pool)}只")
    
    log.info("⏸️ 【早盘流水线】执行完毕！")


def _afternoon_prepare_and_rank(context):
    """午盘共用：复盘跟踪、池更新、动量排序（不含买卖）。"""
    _ensure_corr_globals()
    log_pending_short_momentum_3up_followups(context)
    log_pending_corr_guard_followups(context)

    if g.market_regime == '走弱期':
        if hasattr(g, 'filtered_global_pool') and g.filtered_global_pool:
            g.merged_etf_pool = list(set(g.filtered_global_pool))
        else:
            g.merged_etf_pool = list(set(g.global_etf_pool))
        g.merged_etf_pool.sort()
        log.info(f"🔴 【走弱期】使用过滤后全球/海外ETF池，共{len(g.merged_etf_pool)}只")
    else:
        log.info(f"🟢 【{g.market_regime}】使用合并池，共{len(g.merged_etf_pool)}只")
    refresh_holdings_num_by_regime(context)
    log.info("【动量计算】计算ETF动量得分与排序...")
    calculate_and_log_ranked_etfs(context)


def afternoon_routine(context):
    """原逻辑：13:10 同刻先卖后买。"""
    t = getattr(g, 'afternoon_sell_time', '13:10')
    log.info(f"▶️ 【午盘流水线】{t} 启动...")
    _afternoon_prepare_and_rank(context)
    log.info("【卖出执行】执行卖出操作...")
    execute_sell_trades(context)
    log.info("【买入执行】执行买入操作...")
    execute_buy_trades(context)
    log.info(f"⏸️ 【午盘流水线】{t} 执行完毕！")


def afternoon_sell_routine(context):
    sell_time = getattr(g, 'afternoon_sell_time', '13:10')
    log.info(f"▶️ 【午盘卖出流水线】{sell_time} 启动...")
    _afternoon_prepare_and_rank(context)
    log.info("【卖出执行】执行卖出操作...")
    execute_sell_trades(context)
    log.info(f"⏸️ 【午盘卖出流水线】{sell_time} 执行完毕！")


def afternoon_buy_routine(context):
    buy_time = getattr(g, 'afternoon_buy_time', '13:11')
    log.info(f"▶️ 【午盘买入流水线】{buy_time} 启动...")
    log.info("【买入执行】执行买入操作...")
    execute_buy_trades(context)
    log.info(f"⏸️ 【午盘买入流水线】{buy_time} 执行完毕！")


def reset_daily_flags(context):
    g.cache_date = None
    g.yesterday_close_cache = {}
    log.info("🔄 收盘缓存重置完成")


def _trading_day_after(d):
    """严格晚于日历日 d 的第一个交易日（date）。"""
    arr = get_trade_days(start_date=d + timedelta(days=1), count=5)
    if not len(arr):
        return None
    x = arr[0]
    return x.date() if hasattr(x, 'date') else x


def _update_ma_break_bucket(bucket, ret):
    bucket['n'] += 1
    bucket['sum_ret'] += float(ret)
    if ret > 0:
        bucket['wins'] += 1


def settle_ma_break_pending(context):
    """结算：信号日 14:50 参考价 → 次一交易日收盘价的收益率，并累计统计。"""
    if not getattr(g, 'enable_holdings_ma_break_nextday_stats', False):
        return
    today = context.current_dt.date()
    pending = getattr(g, 'ma_break_nextday_pending', None)
    if not pending:
        return
    kept = []
    stats = getattr(g, 'ma_break_nextday_stats', None)
    if not isinstance(stats, dict):
        stats = {
            'ma5': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
            'ma10': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
            'either_5_10': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
            'ma20': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
            'ma30': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
            'either': {'n': 0, 'sum_ret': 0.0, 'wins': 0},
        }
        g.ma_break_nextday_stats = stats
    for _k in ('ma5', 'ma10', 'either_5_10', 'ma20', 'ma30', 'either'):
        if _k not in stats:
            stats[_k] = {'n': 0, 'sum_ret': 0.0, 'wins': 0}
    for rec in pending:
        if rec.get('settle_date') != today:
            kept.append(rec)
            continue
        sec = rec.get('code')
        px0 = rec.get('px_1450')
        if not sec or px0 is None or px0 <= 0:
            continue
        try:
            hd = get_price(
                sec, start_date=today, end_date=today, frequency='1d', fields=['close'],
                panel=False, skip_paused=True,
            )
            if hd is None or hd.empty or 'close' not in hd.columns:
                kept.append(rec)
                continue
            close_px = float(hd['close'].iloc[-1])
            if not math.isfinite(close_px) or close_px <= 0:
                kept.append(rec)
                continue
        except Exception:
            kept.append(rec)
            continue
        ret = close_px / float(px0) - 1.0
        nm = get_security_name(sec)
        b5 = rec.get('below_ma5', False)
        b10 = rec.get('below_ma10', False)
        b20, b30 = rec.get('below_ma20'), rec.get('below_ma30')
        sig_parts = []
        if b5:
            sig_parts.append('破MA5')
        if b10:
            sig_parts.append('破MA10')
        if b20:
            sig_parts.append('破MA20')
        if b30:
            sig_parts.append('破MA30')
        sig_str = '、'.join(sig_parts) if sig_parts else '无'
        log.info(
            f"📈 【MA跌破·次日收盘】信号日 {rec.get('signal_date')} {sec} {nm} "
            f"14:50 参考价 {px0:.4f} → {today} 收盘 {close_px:.4f} 收益 {ret * 100:.2f}% "
            f"(信号: {sig_str})"
        )
        if b5:
            _update_ma_break_bucket(stats['ma5'], ret)
        if b10:
            _update_ma_break_bucket(stats['ma10'], ret)
        if b5 or b10:
            _update_ma_break_bucket(stats['either_5_10'], ret)
        if b20:
            _update_ma_break_bucket(stats['ma20'], ret)
        if b30:
            _update_ma_break_bucket(stats['ma30'], ret)
        if b20 or b30:
            _update_ma_break_bucket(stats['either'], ret)
    g.ma_break_nextday_pending = kept


def log_ma_break_nextday_summary(context):
    """回测结束时打印 MA 跌破观测累计。"""
    if not getattr(g, 'enable_holdings_ma_break_nextday_stats', False):
        return
    st = getattr(g, 'ma_break_nextday_stats', {})
    if not st:
        return

    def _line(key, label):
        b = st.get(key) or {}
        n = int(b.get('n', 0))
        if n <= 0:
            return f"  - {label}: 尚无样本"
        mean_r = b['sum_ret'] / n
        wr = b['wins'] / n
        return f"  - {label}: n={n} 均值收益={mean_r * 100:.2f}% 上涨占比={wr * 100:.1f}%"

    log.info("【MA跌破观测·全样本汇总】14:50 跌破 MA5/MA10/MA20/MA30（均线截至昨收）→ 次交易日收盘收益")
    log.info(_line('ma5', '跌破 MA5'))
    log.info(_line('ma10', '跌破 MA10'))
    log.info(_line('either_5_10', '跌破 MA5 或 MA10（按事件计一次）'))
    log.info(_line('ma20', '跌破 MA20'))
    log.info(_line('ma30', '跌破 MA30'))
    log.info(_line('either', '跌破 MA20 或 MA30（按事件计一次）'))


def holdings_ma_break_1450_check(context):
    """当日持仓在 14:50 若跌破 MA5/MA10/MA20/MA30 任一条，则登记次交易日收盘结算。"""
    if not getattr(g, 'enable_holdings_ma_break_nextday_stats', False):
        return
    signal_date = context.current_dt.date()
    prev_eod = context.previous_date
    if hasattr(prev_eod, 'date'):
        prev_eod = prev_eod.date()
    holdings = [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]
    if not holdings:
        return
    settle_date = _trading_day_after(signal_date)
    if settle_date is None:
        return
    for sec in holdings:
        try:
            hd = get_price(
                sec, end_date=prev_eod, count=35, frequency='1d', fields=['close'],
                panel=False, skip_paused=True,
            )
            if hd is None or len(hd) < 30:
                continue
            closes = hd['close'].astype(float).values
            ma5 = float(np.mean(closes[-5:]))
            ma10 = float(np.mean(closes[-10:]))
            ma20 = float(np.mean(closes[-20:]))
            ma30 = float(np.mean(closes[-30:]))
        except Exception:
            continue
        px = _get_intraday_price_with_fallback(context, sec)
        if px is None or px <= 0 or not math.isfinite(px):
            continue
        below5 = px < ma5
        below10 = px < ma10
        below20 = px < ma20
        below30 = px < ma30
        if not (below5 or below10 or below20 or below30):
            continue
        nm = get_security_name(sec)
        if not hasattr(g, 'ma_break_nextday_pending') or g.ma_break_nextday_pending is None:
            g.ma_break_nextday_pending = []
        g.ma_break_nextday_pending.append({
            'signal_date': signal_date,
            'settle_date': settle_date,
            'code': sec,
            'px_1450': float(px),
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'ma30': ma30,
            'below_ma5': below5,
            'below_ma10': below10,
            'below_ma20': below20,
            'below_ma30': below30,
        })
        log.info(
            f"📌 【MA跌破观测·登记】{signal_date} 14:50 {sec} {nm} 价 {px:.4f} "
            f"MA5={ma5:.4f}({'破' if below5 else '未破'}) MA10={ma10:.4f}({'破' if below10 else '未破'}) "
            f"MA20={ma20:.4f}({'破' if below20 else '未破'}) MA30={ma30:.4f}({'破' if below30 else '未破'}) "
            f"→ 将于 {settle_date} 收盘结算收益"
        )


def after_close_corr_guard_summary(context):
    """收盘后汇总相关性守卫复盘统计（拦截 / 低相关放行 / 动量豁免）。"""
    if not getattr(g, 'enable_corr_guard_review', True):
        return
    s = _ensure_corr_guard_stats()
    pending_n = len(getattr(g, 'pending_corr_guard_reviews', []) or [])
    n_registered = sum(int(s['by_type'][dt].get('registered', 0)) for dt in s['by_type'])
    if n_registered == 0 and pending_n == 0:
        return
    log_corr_guard_dashboard(
        context,
        title_suffix=f"(收盘汇总 {context.current_dt.date()})",
    )
    log_corr_guard_effectiveness_analysis(context)


def after_close_regime_statistics(context):
    """收盘后统计：当日归属早盘判定的市场状态，累计天数与日收益（复利因子）。"""
    settle_ma_break_pending(context)
    update_regime_performance_stats(context)
    log_regime_performance_dashboard(context, full=False)
    log_exit_reason_dashboard(context, top_n=8)
    after_close_corr_guard_summary(context)


def check_positions(context):
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 【持仓检查】{security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")


def _drawdown_sell_closeable_keep_fraction(context, keep_fraction, exit_reason):
    """
    各持仓按「可卖股数 closeable_amount」保留 keep_fraction（0~1），其余按 100 股步长卖出。
    遵守停牌、涨跌停、T+1（仅用 closeable）。返回是否至少成交一笔。
    """
    try:
        keep_fraction = float(keep_fraction)
    except Exception:
        keep_fraction = 0.5
    keep_fraction = max(0.0, min(1.0, keep_fraction))
    current_data = get_current_data()
    any_trade = False
    for sec in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions.get(sec)
        if not pos or pos.closeable_amount <= 0:
            continue
        ca = int(pos.closeable_amount)
        if ca < 100:
            continue
        keep = int(ca * keep_fraction)
        keep = max(0, (keep // 100) * 100)
        if keep >= ca:
            keep = ca - 100
        sell_amt = ca - keep
        sell_amt = (sell_amt // 100) * 100
        if sell_amt < 100:
            continue
        try:
            cd = current_data[sec]
            if cd.paused:
                log.info(f"【组合回撤减仓】{sec} 停牌，跳过")
                continue
            lp = cd.last_price
            if lp <= 0:
                continue
            if lp >= cd.high_limit:
                log.info(f"【组合回撤减仓】{sec} 涨停，跳过")
                continue
            if lp <= cd.low_limit:
                log.info(f"【组合回撤减仓】{sec} 跌停，跳过")
                continue
        except Exception:
            continue
        order_result = order(sec, -sell_amt)
        if order_result:
            any_trade = True
            nm = get_security_name(sec)
            log.info(
                f"📉 【组合回撤减仓】{sec} {nm} 卖出 {sell_amt} 股（可卖{ca}股中保留≈{keep_fraction:.0%}），原因: {exit_reason}"
            )
    return any_trade


def _portfolio_mtm_total_value(context):
    """
    按场内 last_price 重估账户总资产（现金 + Σ last_price×股数）。
    QDII/LOF 回测里 portfolio.total_value 在盘前时点可能仍贴近昨收；连续竞价后用成交价口径更贴近真实盘中回撤。
    """
    if not getattr(g, 'dd_valuation_use_mtm_last_price', True):
        try:
            return float(context.portfolio.total_value)
        except Exception:
            return 0.0
    cd = get_current_data()
    try:
        tv_legacy = float(context.portfolio.total_value)
    except Exception:
        tv_legacy = 0.0
    stock_legacy_sum = 0.0
    repriced = 0.0
    for sec, pos in context.portfolio.positions.items():
        ta = int(getattr(pos, 'total_amount', 0) or 0)
        if ta <= 0:
            continue
        leg = float(getattr(pos, 'value', 0) or 0)
        stock_legacy_sum += leg
        try:
            lp = float(cd[sec].last_price or 0)
            if lp > 0:
                repriced += lp * ta
            else:
                repriced += leg
        except Exception:
            repriced += leg
    cash_equiv = max(0.0, tv_legacy - stock_legacy_sum)
    return cash_equiv + repriced


def monitor_drawdown(context):
    try:
        current_value = _portfolio_mtm_total_value(context)
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value <= 0:
            return
        current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
        if current_drawdown < g.drawdown_threshold:
            return

        positions_info = []
        for security in context.portfolio.positions:
            position = context.portfolio.positions[security]
            if position.total_amount > 0:
                security_name = get_security_name(security)
                positions_info.append(f"{security_name}:{position.total_amount}股")
        log.info(f"【回撤预警】回撤达到 {current_drawdown:.2%} (阈值: {g.drawdown_threshold:.0%})")
        log.info(f"  当前净值: {current_value:,.0f}  |  最高净值: {g.max_portfolio_value:,.0f}")
        log.info(f"  市场状态: {getattr(g, 'market_regime', '')}")
        log.info(f"  持仓: {', '.join(positions_info) if positions_info else '空仓'}")

        # ---------- 组合回撤分级动作（可选，默认关闭）----------
        if not getattr(g, 'enable_drawdown_risk_actions', False):
            return

        today = context.current_dt.date()
        if getattr(g, 'dd_action_cooldown_date', None) == today:
            return

        th_flat = float(getattr(g, 'dd_flat_threshold', 0.20))
        th_def = float(getattr(g, 'dd_switch_defensive_threshold', 0.15))
        th_half = float(getattr(g, 'dd_half_position_threshold', 0.10))
        warn = float(getattr(g, 'drawdown_threshold', 0.03))

        # ---- +4 改进：差异化阈值（按市场状态收紧）----
        if getattr(g, 'S4_enable_dd_regime_specific', False):
            _regime_now = getattr(g, 'market_regime', '')
            if _regime_now == '走弱期':
                th_half = float(getattr(g, 'S4_dd_half_position_threshold_weak', th_half))
                th_def = float(getattr(g, 'S4_dd_switch_defensive_threshold_weak', th_def))
                th_flat = float(getattr(g, 'S4_dd_flat_threshold_weak', th_flat))
                log.info(
                    f"📐 【+4 差异化阈值·走弱期】half={th_half:.0%} defensive={th_def:.0%} flat={th_flat:.0%}"
                )
            elif _regime_now == '震荡期':
                _oh = getattr(g, 'S4_dd_half_position_threshold_oscillation', None)
                _od = getattr(g, 'S4_dd_switch_defensive_threshold_oscillation', None)
                _of = getattr(g, 'S4_dd_flat_threshold_oscillation', None)
                if _oh is not None:
                    th_half = float(_oh)
                if _od is not None:
                    th_def = float(_od)
                if _of is not None:
                    th_flat = float(_of)
                if _oh is not None or _od is not None or _of is not None:
                    log.info(
                        f"📐 【+4 差异化阈值·震荡期】half={th_half:.0%} defensive={th_def:.0%} flat={th_flat:.0%}"
                    )
        # 阈值链：必须 flat > defend > half > warn（half 须严格大于预警阈值，否则与「仅日志」的 3% 线重叠）
        if not (th_flat > th_def > th_half > warn):
            log.warning(
                "【组合回撤动作】阈值链不合法（需 flat>defend>half>drawdown_threshold），已跳过动作；请检查 "
                "g.dd_flat_threshold / g.dd_switch_defensive_threshold / g.dd_half_position_threshold / g.drawdown_threshold"
            )
            return

        acted = False
        exit_tag = f"组合回撤{current_drawdown:.2%}"

        if current_drawdown >= th_flat:
            log.warning(f"🛑 【组合回撤·全部清仓】{current_drawdown:.2%} ≥ {th_flat:.0%}")
            ok_any = False
            for sec in list(context.portfolio.positions.keys()):
                pos = context.portfolio.positions.get(sec)
                if pos and pos.total_amount > 0:
                    if smart_order_target_value(sec, 0, context, exit_reason=f"{exit_tag}全部清仓"):
                        ok_any = True
            acted = ok_any
        elif current_drawdown >= th_def:
            if check_defensive_etf_available(context):
                log.warning(f"🛡️ 【组合回撤·切防御清仓】{current_drawdown:.2%} ≥ {th_def:.0%}")
                def_etf = getattr(g, 'defensive_etf', None)
                ok_any = False
                for sec in list(context.portfolio.positions.keys()):
                    if sec == def_etf:
                        continue
                    pos = context.portfolio.positions.get(sec)
                    if pos and pos.total_amount > 0:
                        if smart_order_target_value(sec, 0, context, exit_reason=f"{exit_tag}切防御清仓"):
                            ok_any = True
                acted = ok_any
            else:
                log.warning(
                    f"🛡️ 【组合回撤·切防御】{current_drawdown:.2%} ≥ {th_def:.0%}，但防御ETF不可用，未执行清仓"
                )
        elif current_drawdown >= th_half:
            keep_frac = float(getattr(g, 'dd_partial_close_keep_fraction', 0.5))
            log.warning(f"⚠️ 【组合回撤·减仓】{current_drawdown:.2%} ≥ {th_half:.0%}，可卖部分保留 {keep_frac:.0%}")
            if _drawdown_sell_closeable_keep_fraction(context, keep_frac, f"{exit_tag}减仓"):
                acted = True

        if acted:
            g.dd_action_cooldown_date = today
            if getattr(g, 'dd_reset_peak_after_action', True):
                nv = _portfolio_mtm_total_value(context)
                g.max_portfolio_value = max(nv, 1.0)
                log.info(f"【组合回撤动作】已执行，冷却至次日；峰值已重置为当前净值≈{g.max_portfolio_value:,.0f}")
    except Exception as e:
        log.error(f"【回撤监控】计算异常: {e}")


def calculate_global_etf_threshold(context):
    if getattr(g, 'log_pool_update_details', False):
        log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            log.warning("未找到任何场内ETF，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        if getattr(g, 'log_pool_update_details', False):
            log.info(f"全市场ETF总数: {len(etf_list)}只")
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date, frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            log.warning("无法获取历史成交额数据，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        daily_totals = df.groupby('time')['money'].sum()
        daily_counts = df[df['money'] > 0].groupby('time')['code'].nunique()
        if getattr(g, 'log_pool_update_details', False):
            for day, money in daily_totals.items():
                count = daily_counts.get(day, 0)
                log.info(f"  {day.date()} 全市场ETF总成交额: {money/1e8:.2f}亿元 ({count}只ETF有成交)")
        if len(daily_totals) < 3:
            log.warning(f"仅有{len(daily_totals)}个有效交易日，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        div = float(getattr(g, 'global_liquidity_threshold_divisor', 20000))
        if div <= 0:
            div = 20000
        threshold = avg_total_money / div
        g.avg_etf_money_threshold = threshold
        if getattr(g, 'log_pool_update_details', False):
            log.info(
                f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF日均总成交额={avg_total_money/1e8:.2f}亿元，"
                f"分母={div:g}，阈值={threshold/1e4:.0f}万元({threshold:,.0f}元)"
            )
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000


def filter_global_pool_by_volume(context):
    log.info("【全球池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        log.info("【全球池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.global_etf_pool:
        log.info("【全球池过滤】全球池为空，跳过过滤")
        g.filtered_global_pool = []
        return
    dynamic_threshold = g.avg_etf_money_threshold
    log.info(f"【全球池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.global_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【全球池过滤】无法获取成交额数据，使用原始全球池")
            g.filtered_global_pool = g.global_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_global_pool = qualified.index.tolist()
        removed = set(g.global_etf_pool) - set(new_global_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            log.info(f"【全球池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_global_pool = new_global_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        log.info(f"【全球池过滤】保留高流动性ETF({len(new_global_pool)}只)")
    except Exception as e:
        log.warning(f"【全球池过滤】异常: {e}")
        g.filtered_global_pool = g.global_etf_pool[:]


def _fetch_close_panel_for_corr(codes, lookback, end_date):
    """拉取收盘价宽表，供修正相关性计算。"""
    if not codes:
        return pd.DataFrame()
    try:
        raw = get_price(
            list(codes), end_date=end_date, count=int(lookback),
            frequency='daily', fields=['close'], panel=False,
        )
        if raw is None or raw.empty:
            return pd.DataFrame()
        price_df = raw.pivot(index='time', columns='code', values='close')
        price_df = price_df.dropna(thresh=int(lookback * 0.7), axis=1)
        price_df = price_df.ffill().dropna()
        return price_df
    except Exception as e:
        if getattr(g, 'log_corr_detail', False):
            log.warning(f"【修正相关性】取价失败: {e}")
        return pd.DataFrame()


def compute_adjusted_corr_matrix(price_df):
    """
    修正相关性矩阵（与 相关性.py 一致）：
    P_adj = P_base × exp(-MAE(累计收益曲线差)) × min(σ_i,σ_j)/max(σ_i,σ_j)
    """
    if price_df is None or price_df.empty or price_df.shape[1] < 1:
        return pd.DataFrame()
    if price_df.shape[1] == 1:
        code = price_df.columns[0]
        return pd.DataFrame([[1.0]], index=[code], columns=[code])
    returns_df = np.log(price_df / price_df.shift(1)).dropna()
    if returns_df.empty or returns_df.shape[1] < 1:
        return pd.DataFrame()
    base_corr = returns_df.corr()
    cum_returns = (price_df / price_df.iloc[0]) - 1
    vols = returns_df.std() * np.sqrt(252)
    cum_ret_arr = cum_returns.values
    vol_arr = vols.values
    curve_diff = np.mean(np.abs(cum_ret_arr[:, :, None] - cum_ret_arr[:, None, :]), axis=0)
    ret_factor = np.exp(-curve_diff)
    vol_min = np.minimum(vol_arr[:, None], vol_arr[None, :])
    vol_max = np.maximum(vol_arr[:, None], vol_arr[None, :])
    vol_max[vol_max == 0] = 1e-9
    vol_ratio = vol_min / vol_max
    adj_corr_matrix = base_corr.values * ret_factor * vol_ratio
    codes = price_df.columns.tolist()
    return pd.DataFrame(adj_corr_matrix, index=codes, columns=codes)


def get_adj_corr_matrix_cached(context, codes):
    """同日同代码集复用修正相关性矩阵。"""
    codes_key = tuple(sorted(set(codes)))
    today = context.current_dt.date()
    if (
        getattr(g, '_adj_corr_cache_date', None) == today
        and getattr(g, '_adj_corr_cache_key', None) == codes_key
        and getattr(g, '_adj_corr_matrix', None) is not None
    ):
        return g._adj_corr_matrix
    lookback = int(getattr(g, 'corr_lookback_days', 60))
    price_df = _fetch_close_panel_for_corr(codes_key, lookback, context.previous_date)
    adj = compute_adjusted_corr_matrix(price_df)
    g._adj_corr_cache_date = today
    g._adj_corr_cache_key = codes_key
    g._adj_corr_matrix = adj
    if getattr(g, 'log_corr_detail', False) and not adj.empty:
        log.info(
            f"【修正相关性】矩阵已更新: {adj.shape[0]}×{adj.shape[1]} "
            f"回看{lookback}日 截止{context.previous_date}"
        )
    return adj


def get_pair_adjusted_corr(code_a, code_b, adj_corr):
    if adj_corr is None or adj_corr.empty:
        return None
    if code_a not in adj_corr.index or code_b not in adj_corr.columns:
        return None
    try:
        return float(adj_corr.loc[code_a, code_b])
    except Exception:
        return None


def filter_pool_by_max_corr(context, candidate_pool, base_pool, threshold=None, lookback=None):
    """候选相对基础池：最大修正相关性 < threshold 的标的（保持 candidate_pool 顺序）。"""
    threshold = float(getattr(g, 'corr_pool_threshold', 0.5) if threshold is None else threshold)
    lookback = int(getattr(g, 'corr_lookback_days', 60) if lookback is None else lookback)
    if not candidate_pool:
        return []
    if not base_pool:
        return list(candidate_pool)
    all_codes = list(set(base_pool + candidate_pool))
    price_df = _fetch_close_panel_for_corr(all_codes, lookback, context.previous_date)
    adj_corr = compute_adjusted_corr_matrix(price_df)
    if adj_corr.empty:
        return list(candidate_pool)
    valid_base = [c for c in adj_corr.columns if c in base_pool]
    valid_cands = [c for c in candidate_pool if c in adj_corr.index]
    if not valid_base or not valid_cands:
        return list(candidate_pool)
    sub = adj_corr.loc[valid_cands, valid_base]
    max_corr = sub.max(axis=1)
    passed = set(max_corr[max_corr < threshold].index.tolist())
    out = [c for c in candidate_pool if c in passed]
    if getattr(g, 'log_corr_detail', False):
        dropped = [c for c in candidate_pool if c not in passed]
        log.info(
            f"【动态池·相关性过滤】阈值<{threshold} 回看{lookback}日: "
            f"通过{len(out)}/{len(candidate_pool)} 剔除{len(dropped)}"
        )
    return out


def annotate_corr_vs_fixed_pool(metrics_list, context):
    """为第二步前检查附加：相对固定池的最大修正相关性及是否达入池标准。"""
    if not metrics_list:
        return
    fixed = list(getattr(g, 'filtered_fixed_pool', None) or g.fixed_etf_pool or [])
    fixed_set = set(fixed)
    etf_codes = [m['etf'] for m in metrics_list if m.get('etf')]
    adj_corr = get_adj_corr_matrix_cached(context, list(set(etf_codes + fixed)))
    threshold = float(getattr(g, 'corr_pool_threshold', 0.5))
    pool_filter_on = bool(getattr(g, 'enable_corr_pool_filter', False))
    for m in metrics_list:
        etf = m.get('etf')
        if not etf:
            continue
        if etf in fixed_set:
            m['max_corr_vs_fixed'] = None
            m['passed_corr_pool'] = True
            m['corr_pool_note'] = '固定池成员'
            continue
        if adj_corr.empty or etf not in adj_corr.index:
            m['max_corr_vs_fixed'] = None
            m['passed_corr_pool'] = True
            m['corr_pool_note'] = '相关性数据不足(一览视为通过)'
            continue
        cols = [c for c in fixed if c in adj_corr.columns]
        if not cols:
            m['max_corr_vs_fixed'] = None
            m['passed_corr_pool'] = True
            m['corr_pool_note'] = '固定池无有效行情'
            continue
        vals = [float(adj_corr.loc[etf, c]) for c in cols]
        mx = max(vals)
        m['max_corr_vs_fixed'] = mx
        m['passed_corr_pool'] = mx < threshold
        m['corr_pool_note'] = (
            f"vs固定池max P_adj={mx:.4f} {'<' if mx < threshold else '≥'} {threshold}"
        )
        if pool_filter_on and not m['passed_corr_pool']:
            m['corr_pool_note'] += '(动态池入池筛已启用→未通过)'


def _fmt_corr_pct_decimal(ret_dec):
    if ret_dec is None or (isinstance(ret_dec, float) and (np.isnan(ret_dec) or np.isinf(ret_dec))):
        return 'N/A'
    return f"{float(ret_dec) * 100:.4f}%"


def _ensure_corr_guard_stats():
    if not hasattr(g, 'corr_guard_stats') or not isinstance(g.corr_guard_stats, dict):
        g.corr_guard_stats = _default_corr_guard_stats()
    s = g.corr_guard_stats
    if 'by_type' not in s or not isinstance(s.get('by_type'), dict):
        s['by_type'] = _default_corr_guard_stats()['by_type']
    for dt in (CORR_GUARD_DECISION_INTERCEPT, CORR_GUARD_DECISION_ALLOW_LOW, CORR_GUARD_DECISION_ALLOW_MOM):
        if dt not in s['by_type']:
            s['by_type'][dt] = _default_corr_guard_type_stats()
    return s


def _corr_guard_type_summary(s, decision_type):
    ts = s['by_type'][decision_type]
    n_done = int(ts.get('done', 0))
    return {
        'registered': int(ts.get('registered', 0)),
        'done': n_done,
        'hold_win': int(ts.get('hold_win', 0)),
        'target_win': int(ts.get('target_win', 0)),
        'tie': int(ts.get('tie', 0)),
        'avg_spread': (float(ts.get('sum_spread', 0)) / n_done) if n_done else None,
        'avg_hold': (float(ts.get('sum_hold_ret', 0)) / n_done) if n_done else None,
        'avg_tgt': (float(ts.get('sum_target_ret', 0)) / n_done) if n_done else None,
    }


def _corr_guard_verdict(decision_type, spread):
    if spread is None:
        return '数据不足'
    if spread > 1e-12:
        if decision_type == CORR_GUARD_DECISION_INTERCEPT:
            return '拦截正确·继续持有更优'
        return f'{_corr_guard_type_label(decision_type)}失误·应拦截'
    if spread < -1e-12:
        if decision_type == CORR_GUARD_DECISION_INTERCEPT:
            return '拦截失误·候选更优'
        return f'{_corr_guard_type_label(decision_type)}正确·换仓更优'
    return '持平'


def _update_corr_guard_type_stats(ts, spread, ret_h, ret_t):
    if spread is None:
        return
    if spread > 1e-12:
        ts['hold_win'] = int(ts.get('hold_win', 0)) + 1
    elif spread < -1e-12:
        ts['target_win'] = int(ts.get('target_win', 0)) + 1
    else:
        ts['tie'] = int(ts.get('tie', 0)) + 1
    if ret_h is not None:
        ts['sum_hold_ret'] = float(ts.get('sum_hold_ret', 0)) + ret_h
    if ret_t is not None:
        ts['sum_target_ret'] = float(ts.get('sum_target_ret', 0)) + ret_t
    ts['sum_spread'] = float(ts.get('sum_spread', 0)) + spread
    ts['done'] = int(ts.get('done', 0)) + 1


def log_corr_guard_dashboard(context, title_suffix=''):
    """打印相关性守卫复盘统计看板（拦截 / 低相关放行 / 动量豁免）。"""
    s = _ensure_corr_guard_stats()
    n_done = int(s.get('review_done', 0))
    pending_n = len(getattr(g, 'pending_corr_guard_reviews', []) or [])
    lines = [
        '',
        '─' * 72,
        f"📊 【相关性守卫·统计看板】{title_suffix}".strip(),
        f"  累计登记复盘: 拦截 {s['by_type'][CORR_GUARD_DECISION_INTERCEPT]['registered']} | "
        f"低相关放行 {s['by_type'][CORR_GUARD_DECISION_ALLOW_LOW]['registered']} | "
        f"动量豁免 {s['by_type'][CORR_GUARD_DECISION_ALLOW_MOM]['registered']}",
        f"  已完成隔日复盘: {n_done} 次  |  待复盘: {pending_n} 笔",
    ]
    for dt in (CORR_GUARD_DECISION_INTERCEPT, CORR_GUARD_DECISION_ALLOW_LOW, CORR_GUARD_DECISION_ALLOW_MOM):
        sm = _corr_guard_type_summary(s, dt)
        label = _corr_guard_type_label(dt)
        if not sm['done']:
            lines.append(f"  【{label}】尚无已完成样本")
            continue
        if dt == CORR_GUARD_DECISION_INTERCEPT:
            correct = sm['hold_win']
            rate_label = '拦截正确率(持有>候选)'
        else:
            correct = sm['target_win']
            rate_label = '放行正确率(候选>持有)'
        wrong = sm['target_win'] if dt == CORR_GUARD_DECISION_INTERCEPT else sm['hold_win']
        lines.append(
            f"  【{label}】完成 {sm['done']} | 决策正确 {correct} | 决策失误 {wrong} | "
            f"持平 {sm['tie']} | {rate_label} {correct / sm['done'] * 100:.1f}%"
        )
        lines.append(
            f"    平均区间收益 — 继续持有: {_fmt_corr_pct_decimal(sm['avg_hold'])}"
            f"  候选买入: {_fmt_corr_pct_decimal(sm['avg_tgt'])}"
            f"  收益差(持有−候选): {_fmt_corr_pct_decimal(sm['avg_spread'])}"
        )
    hist = list(getattr(g, 'corr_guard_review_history', []) or [])[-5:]
    if hist:
        lines.append("  最近复盘(至多5条):")
        for h in hist:
            lines.append(
                f"    · [{_corr_guard_type_label(h.get('decision_type', CORR_GUARD_DECISION_INTERCEPT))}] "
                f"{h.get('intercept_date')}→{h.get('followup_date')} "
                f"持有{h.get('held_name', '?')} vs 候选{h.get('target_name', '?')} "
                f"差={h.get('spread_pct_str', 'N/A')} ({h.get('verdict', '')})"
            )
    lines.append('─' * 72)
    log.info('\n'.join(lines))


def _record_corr_guard_review(
    context, decision_type, held_code, held_name, target_code, target_name,
    pair_corr, hold_mom, corr_th, mom_th,
):
    """登记守卫决策，下一交易日 13:10 做持有 vs 候选收益对比。"""
    if not getattr(g, 'enable_corr_guard_review', True):
        return
    fu = _first_trading_day_after(context.current_dt.date())
    if not fu:
        log.warning("【相关性守卫】无法确定下一交易日，跳过隔日复盘登记")
        return
    px_h = _get_intraday_price_with_fallback(context, held_code)
    px_t = _get_intraday_price_with_fallback(context, target_code)
    if not px_h or px_h <= 0 or not px_t or px_t <= 0:
        log.warning(
            f"【相关性守卫】复盘价获取失败(持有={px_h} 候选={px_t})，仍登记但收益可能为N/A"
        )
    s = _ensure_corr_guard_stats()
    ts = s['by_type'][decision_type]
    ts['registered'] = int(ts.get('registered', 0)) + 1
    if decision_type == CORR_GUARD_DECISION_INTERCEPT:
        s['intercept_total'] = int(s.get('intercept_total', 0)) + 1
    if not hasattr(g, 'pending_corr_guard_reviews'):
        g.pending_corr_guard_reviews = []
    g.pending_corr_guard_reviews.append({
        'decision_type': decision_type,
        'intercept_date': str(context.current_dt.date()),
        'followup_date': fu,
        'held_code': held_code,
        'held_name': held_name,
        'target_code': target_code,
        'target_name': target_name,
        'price_held_1310': float(px_h) if px_h and px_h > 0 else None,
        'price_target_1310': float(px_t) if px_t and px_t > 0 else None,
        'pair_corr': float(pair_corr) if pair_corr is not None else None,
        'hold_momentum': float(hold_mom) if hold_mom is not None and not pd.isna(hold_mom) else None,
        'corr_threshold': float(corr_th),
        'momentum_threshold': float(mom_th),
        'regime': getattr(g, 'market_regime', '—'),
    })
    label = _corr_guard_type_label(decision_type)
    corr_s = f"{pair_corr:.4f}" if pair_corr is not None else 'N/A'
    log.info(
        f"【相关性守卫】已登记{label}隔日复盘 #{ts['registered']}: "
        f"持有 {held_name}({held_code}) vs 候选 {target_name}({target_code}) "
        f"P_adj={corr_s} 复盘日={fu} (决策日13:10→复盘日13:10)"
    )
    log_corr_guard_dashboard(context, title_suffix=f'(本次{label}登记后)')


def _record_corr_guard_intercept(
    context, held_code, held_name, target_code, target_name,
    pair_corr, hold_mom, corr_th, mom_th,
):
    """登记一次拦截（兼容旧调用）。"""
    _record_corr_guard_review(
        context, CORR_GUARD_DECISION_INTERCEPT, held_code, held_name,
        target_code, target_name, pair_corr, hold_mom, corr_th, mom_th,
    )


def log_corr_guard_effectiveness_analysis(context):
    """收盘汇总：分决策类型 / P_adj / 动量 / 市场状态 对比守卫有效性。"""
    records = list(getattr(g, 'corr_guard_all_records', []) or [])
    if not records:
        return
    valid = [r for r in records if r.get('spread') is not None]
    if not valid:
        return

    def _bucket_padj(p):
        if p is None:
            return 'N/A'
        p = float(p)
        if p <= 0.80:
            return '≤0.80(低相关)'
        if p <= 0.85:
            return '0.80~0.85'
        if p <= 0.90:
            return '0.85~0.90'
        if p <= 0.95:
            return '0.90~0.95'
        return '>0.95'

    def _bucket_mom(m):
        if m is None:
            return '动量缺失'
        m = float(m)
        if m < 3:
            return '[0,3)'
        if m < 4.5:
            return '[3,4.5)'
        if m < 5.5:
            return '[4.5,5.5)'
        if m <= 6:
            return '[5.5,6]'
        return '>6(豁免区)'

    def _decision_correct(rec):
        dt = rec.get('decision_type', CORR_GUARD_DECISION_INTERCEPT)
        sp = rec.get('spread')
        if sp is None:
            return None
        if dt == CORR_GUARD_DECISION_INTERCEPT:
            return sp > 1e-12
        return sp < -1e-12

    lines = [
        '',
        '=' * 72,
        f"📈 【相关性守卫·有效性分析】(收盘汇总 {context.current_dt.date()})",
        f"  已完成复盘样本: {len(valid)} 笔（spread 可计算）",
    ]

    for dt in (CORR_GUARD_DECISION_INTERCEPT, CORR_GUARD_DECISION_ALLOW_LOW, CORR_GUARD_DECISION_ALLOW_MOM):
        rs = [r for r in valid if r.get('decision_type') == dt]
        if not rs:
            continue
        correct = sum(1 for r in rs if _decision_correct(r))
        spreads = [r['spread'] for r in rs]
        med = sorted(spreads)[len(spreads) // 2]
        label = _corr_guard_type_label(dt)
        lines.append(
            f"  ▶ {label}: n={len(rs)} 决策正确率={correct / len(rs) * 100:.1f}% "
            f"平均收益差(持有−候选)={_fmt_corr_pct_decimal(sum(spreads) / len(spreads))} "
            f"中位数={_fmt_corr_pct_decimal(med)}"
        )

    lines.append('  ── 按 P_adj 分桶（全样本）──')
    padj_groups = {}
    for r in valid:
        padj_groups.setdefault(_bucket_padj(r.get('pair_corr')), []).append(r)
    for bk in ['≤0.80(低相关)', '0.80~0.85', '0.85~0.90', '0.90~0.95', '>0.95', 'N/A']:
        rs = padj_groups.get(bk)
        if not rs:
            continue
        int_rs = [r for r in rs if r.get('decision_type') == CORR_GUARD_DECISION_INTERCEPT]
        int_correct = sum(1 for r in int_rs if _decision_correct(r))
        avg_sp = sum(r['spread'] for r in rs) / len(rs)
        lines.append(
            f"    {bk:14s}: n={len(rs):3d} 拦截{len(int_rs):2d} "
            f"拦截正确率={(int_correct / len(int_rs) * 100 if int_rs else 0):5.1f}% "
            f"均差={_fmt_corr_pct_decimal(avg_sp)}"
        )

    lines.append('  ── 按持仓动量分桶（全样本）──')
    mom_groups = {}
    for r in valid:
        mom_groups.setdefault(_bucket_mom(r.get('hold_momentum')), []).append(r)
    for bk in ['[0,3)', '[3,4.5)', '[4.5,5.5)', '[5.5,6]', '>6(豁免区)', '动量缺失']:
        rs = mom_groups.get(bk)
        if not rs:
            continue
        int_rs = [r for r in rs if r.get('decision_type') == CORR_GUARD_DECISION_INTERCEPT]
        int_correct = sum(1 for r in int_rs if _decision_correct(r))
        avg_sp = sum(r['spread'] for r in rs) / len(rs)
        lines.append(
            f"    {bk:12s}: n={len(rs):3d} 拦截{len(int_rs):2d} "
            f"拦截正确率={(int_correct / len(int_rs) * 100 if int_rs else 0):5.1f}% "
            f"均差={_fmt_corr_pct_decimal(avg_sp)}"
        )

    lines.append('  ── 按市场状态（拦截样本）──')
    regime_groups = {}
    for r in valid:
        if r.get('decision_type') != CORR_GUARD_DECISION_INTERCEPT:
            continue
        regime_groups.setdefault(r.get('regime', '—'), []).append(r)
    for reg, rs in sorted(regime_groups.items(), key=lambda x: -len(x[1])):
        correct = sum(1 for r in rs if _decision_correct(r))
        avg_sp = sum(r['spread'] for r in rs) / len(rs)
        lines.append(
            f"    {reg:6s}: n={len(rs):2d} 拦截正确率={correct / len(rs) * 100:5.1f}% "
            f"均差={_fmt_corr_pct_decimal(avg_sp)}"
        )

    int_rs = [r for r in valid if r.get('decision_type') == CORR_GUARD_DECISION_INTERCEPT]
    if int_rs:
        best = sorted(int_rs, key=lambda r: -(r.get('spread') or 0))[:5]
        worst = sorted(int_rs, key=lambda r: (r.get('spread') or 0))[:5]
        lines.append('  ── 拦截最有效 TOP5（持有显著优于候选）──')
        for r in best:
            lines.append(
                f"    · {r.get('intercept_date')} {r.get('held_name', '?')} vs {r.get('target_name', '?')} "
                f"差={r.get('spread_pct_str', 'N/A')} P_adj={r.get('pair_corr')} 动量={r.get('hold_momentum')} {r.get('regime', '')}"
            )
        lines.append('  ── 拦截最差 TOP5（候选显著优于持有）──')
        for r in worst:
            lines.append(
                f"    · {r.get('intercept_date')} {r.get('held_name', '?')} vs {r.get('target_name', '?')} "
                f"差={r.get('spread_pct_str', 'N/A')} P_adj={r.get('pair_corr')} 动量={r.get('hold_momentum')} {r.get('regime', '')}"
            )

    allow_rs = [r for r in valid if r.get('decision_type') in (CORR_GUARD_DECISION_ALLOW_LOW, CORR_GUARD_DECISION_ALLOW_MOM)]
    if allow_rs:
        missed = sorted(allow_rs, key=lambda r: -(r.get('spread') or 0))[:5]
        lines.append('  ── 放行最差 TOP5（本应拦截：持有优于候选）──')
        for r in missed:
            lines.append(
                f"    · [{_corr_guard_type_label(r.get('decision_type'))}] {r.get('intercept_date')} "
                f"{r.get('held_name', '?')} vs {r.get('target_name', '?')} 差={r.get('spread_pct_str', 'N/A')} "
                f"P_adj={r.get('pair_corr')} 动量={r.get('hold_momentum')}"
            )

    lines.append('=' * 72)
    log.info('\n'.join(lines))


def _corr_guard_mom_matrix_bucket_label(m):
    """动量矩阵行标签（与复盘热力图一致）。"""
    if m is None or (isinstance(m, float) and (np.isnan(m) or not np.isfinite(m))):
        return None
    m = float(m)
    if m < 2:
        return '[0,2)'
    if m < 3:
        return '[2,3)'
    if m < 4:
        return '[3,4)'
    if m < 4.5:
        return '[4,4.5)'
    if m < 5:
        return '[4.5,5)'
    if m < 5.5:
        return '[5,5.5)'
    if m < 6:
        return '[5.5,6)'
    if m <= 7:
        return '[6,7]'
    return '>7'


def _corr_guard_padj_matrix_bucket_label(p):
    """P_adj 矩阵列标签（0.50~0.60 并入 0.60~0.70，与用户表格列一致）。"""
    if p is None or (isinstance(p, float) and (np.isnan(p) or not np.isfinite(p))):
        return None
    p = float(p)
    if p <= 0.50:
        return '≤0.50'
    if p <= 0.70:
        return '0.60~0.70'
    if p <= 0.80:
        return '0.70~0.80'
    if p <= 0.85:
        return '0.80~0.85'
    if p <= 0.90:
        return '0.85~0.90'
    if p <= 0.95:
        return '0.90~0.95'
    return '>0.95'


def _corr_guard_matrix_cell_str(spreads, intercept_mode=False, min_n=1):
    """单元格：持有更优占比% / 均差(持有−候选)% ；intercept_mode 时占比为拦截正确率。"""
    if not spreads:
        return '—'
    n = len(spreads)
    if n < min_n:
        return f'n={n}'
    if intercept_mode:
        win = sum(1 for s in spreads if s > 1e-12)
    else:
        win = sum(1 for s in spreads if s > 1e-12)
    avg = sum(spreads) / n * 100.0
    return f"{win / n * 100:.0f}%/{avg:+.2f}"


def _corr_guard_filter_matrix_regime(records, regime_label):
    if regime_label == '全样本':
        return list(records)
    return [r for r in records if r.get('regime') == regime_label]


def _corr_guard_simulate_threshold_accuracy(records, threshold, mom_max):
    """模拟：P_adj>T 且 动量≤mom_max → 拦截(保留持有)，否则放行。"""
    if not records:
        return 0.0, 0, 0
    correct = 0
    intercept_n = 0
    for r in records:
        sp = r.get('spread')
        if sp is None:
            continue
        p = r.get('pair_corr')
        mom = r.get('hold_momentum')
        if p is None or mom is None:
            continue
        should_intercept = float(p) > float(threshold) and float(mom) <= float(mom_max)
        if should_intercept:
            intercept_n += 1
            if sp > 1e-12:
                correct += 1
        else:
            if sp < -1e-12:
                correct += 1
    total = len([r for r in records if r.get('spread') is not None
                 and r.get('pair_corr') is not None and r.get('hold_momentum') is not None])
    acc = correct / total if total else 0.0
    return acc, correct, total


def _corr_guard_build_mom_padj_matrix(records, decision_type=None):
    """构建动量×P_adj 单元格 spread 列表。"""
    matrix = {}
    for mb in CORR_GUARD_MOM_MATRIX_BUCKETS:
        matrix[mb] = {pb: [] for pb in CORR_GUARD_PADJ_MATRIX_COLS}
    for r in records:
        if decision_type is not None and r.get('decision_type') != decision_type:
            continue
        sp = r.get('spread')
        if sp is None:
            continue
        mb = _corr_guard_mom_matrix_bucket_label(r.get('hold_momentum'))
        pb = _corr_guard_padj_matrix_bucket_label(r.get('pair_corr'))
        if mb is None or pb is None:
            continue
        matrix[mb][pb].append(float(sp))
    return matrix


def _corr_guard_format_mom_padj_matrix_table(matrix, intercept_mode=False, min_n=1):
    """格式化动量×P_adj 矩阵为文本行。"""
    col_w = 12
    header = '动量\\P_adj'.ljust(10) + ''.join(c.rjust(col_w) for c in CORR_GUARD_PADJ_MATRIX_COLS)
    lines = [header]
    for mb in CORR_GUARD_MOM_MATRIX_BUCKETS:
        row = mb.ljust(10)
        for pb in CORR_GUARD_PADJ_MATRIX_COLS:
            cell = _corr_guard_matrix_cell_str(
                matrix[mb][pb], intercept_mode=intercept_mode, min_n=min_n,
            )
            row += cell.rjust(col_w)
        lines.append(row)
    return lines


def _corr_guard_optimal_threshold_by_mom(records, mom_label, mom_max, step=0.05):
    """在给定动量区间内搜索最优 P_adj 拦截阈值 T。"""
    bucket_rs = [
        r for r in records
        if _corr_guard_mom_matrix_bucket_label(r.get('hold_momentum')) == mom_label
        and r.get('spread') is not None
        and r.get('pair_corr') is not None
        and r.get('hold_momentum') is not None
    ]
    if not bucket_rs:
        return None
    best = None
    for ti in range(50, 96):
        T = ti / 100.0
        acc, correct, total = _corr_guard_simulate_threshold_accuracy(bucket_rs, T, mom_max)
        if best is None or acc > best['acc'] or (acc == best['acc'] and T < best['T']):
            best = {'T': T, 'acc': acc, 'correct': correct, 'total': total, 'n': len(bucket_rs)}
    return best


def log_corr_guard_mom_padj_regime_matrix(context):
    """
    回测末日汇总：动量×P_adj 拦截表现矩阵，按 全样本 / 正常期 / 震荡期 / 走弱期 分组。
    单元格格式：持有更优占比% / 均差(持有−候选)% ；拦截子表为拦截正确率 / 均差。
    并给出各动量区间最优 P_adj 阈值 T*（模拟 P_adj>T 且动量≤mom_max → 拦截）。
    """
    if not getattr(g, 'enable_corr_mom_padj_matrix_report', True):
        return
    if not getattr(g, 'enable_corr_guard_review', True):
        return
    records = list(getattr(g, 'corr_guard_all_records', []) or [])
    valid = [r for r in records if r.get('spread') is not None]
    if not valid:
        log.info('【相关性守卫·动量×P_adj矩阵】无已完成复盘样本，跳过')
        return

    min_n = int(getattr(g, 'corr_mom_padj_matrix_min_cell_n', 1))
    mom_max = float(getattr(g, 'corr_hold_momentum_max', 6))
    cur_th = float(getattr(g, 'corr_hold_threshold', 0.80))
    today = context.current_dt.date()

    lines = [
        '',
        '=' * 88,
        f'📊 【相关性守卫·动量×P_adj矩阵·分市场状态】(回测汇总 {today}，样本 {len(valid)} 笔)',
        f'  当前守卫参数: P_adj>{cur_th:.2f} 且 持仓动量≤{mom_max:.2f} → 拦截 | 单元格=占比%/均差(持有−候选)%',
        f'  说明: 均差>0 表示继续持有更优(拦截合理)；均差<0 表示换仓更优(拦截失误)',
        '=' * 88,
    ]

    for regime in CORR_GUARD_MATRIX_REGIMES:
        rs = _corr_guard_filter_matrix_regime(valid, regime)
        if not rs:
            lines.append(f'\n── {regime}：无样本 ──')
            continue

        lines.append(f'\n{"─" * 88}')
        lines.append(f'▶ {regime} (n={len(rs)})')
        lines.append('  【全样本·持有更优占比 / 均差】')
        mat_all = _corr_guard_build_mom_padj_matrix(rs)
        lines.extend('  ' + ln for ln in _corr_guard_format_mom_padj_matrix_table(mat_all, min_n=min_n))

        int_rs = [r for r in rs if r.get('decision_type') == CORR_GUARD_DECISION_INTERCEPT]
        if int_rs:
            lines.append(f'  【仅拦截样本·拦截正确率 / 均差】(n={len(int_rs)})')
            mat_int = _corr_guard_build_mom_padj_matrix(rs, decision_type=CORR_GUARD_DECISION_INTERCEPT)
            lines.extend(
                '  ' + ln for ln in _corr_guard_format_mom_padj_matrix_table(
                    mat_int, intercept_mode=True, min_n=min_n,
                )
            )
        else:
            lines.append('  【仅拦截样本】无')

        lines.append(f'  【各动量区间·最优 P_adj 阈值 T*】(模拟 P_adj>T 且动量≤{mom_max:.2f}→拦截，最大化综合决策准确率)')
        lines.append(f'    {"动量区间":<10} {"样本":>5} {"T*":>6} {"准确率":>8} {"当前T":>8} {"当前准确率":>10}')
        for mb in CORR_GUARD_MOM_MATRIX_BUCKETS:
            opt = _corr_guard_optimal_threshold_by_mom(rs, mb, mom_max)
            if not opt:
                continue
            cur_acc, _, cur_total = _corr_guard_simulate_threshold_accuracy(
                [r for r in rs if _corr_guard_mom_matrix_bucket_label(r.get('hold_momentum')) == mb],
                cur_th, mom_max,
            )
            lines.append(
                f'    {mb:<10} {opt["n"]:>5} {opt["T"]:>6.2f} {opt["acc"] * 100:>7.1f}% '
                f'{cur_th:>8.2f} {cur_acc * 100:>9.1f}%'
            )

    lines.append('=' * 88)
    log.info('\n'.join(lines))


def log_pending_corr_guard_followups(context):
    """下一交易日 13:10：对比决策日继续持有 vs 若买入候选的区间收益差。"""
    pending = getattr(g, 'pending_corr_guard_reviews', None)
    if not pending:
        return
    today = context.current_dt.date()
    keep = []
    s = _ensure_corr_guard_stats()

    for item in pending:
        fu = item.get('followup_date')
        if fu is None:
            continue
        if fu < today:
            log.warning(
                f"【相关性守卫·隔日复盘】跳过过期 "
                f"{item.get('held_name')} vs {item.get('target_name')} 计划={fu} 当前={today}"
            )
            continue
        if fu > today:
            keep.append(item)
            continue
        decision_type = item.get('decision_type', CORR_GUARD_DECISION_INTERCEPT)
        hc = item.get('held_code')
        tc = item.get('target_code')
        hn = item.get('held_name') or get_security_name(hc)
        tn = item.get('target_name') or get_security_name(tc)
        p0h = item.get('price_held_1310')
        p0t = item.get('price_target_1310')
        p1h = _get_intraday_price_with_fallback(context, hc)
        p1t = _get_intraday_price_with_fallback(context, tc)
        ret_h = ret_t = spread = None
        if p0h and p0h > 0 and p1h and p1h > 0:
            ret_h = float(p1h) / float(p0h) - 1.0
        if p0t and p0t > 0 and p1t and p1t > 0:
            ret_t = float(p1t) / float(p0t) - 1.0
        if ret_h is not None and ret_t is not None:
            spread = ret_h - ret_t
        spread_pct_str = _fmt_corr_pct_decimal(spread)
        verdict = _corr_guard_verdict(decision_type, spread)
        ts = s['by_type'][decision_type]
        _update_corr_guard_type_stats(ts, spread, ret_h, ret_t)
        s['review_done'] = int(s.get('review_done', 0)) + 1
        if decision_type == CORR_GUARD_DECISION_INTERCEPT and spread is not None:
            if spread > 1e-12:
                s['hold_better'] = int(s.get('hold_better', 0)) + 1
            elif spread < -1e-12:
                s['target_better'] = int(s.get('target_better', 0)) + 1
            else:
                s['tie'] = int(s.get('tie', 0)) + 1
            s['sum_hold_ret'] = float(s.get('sum_hold_ret', 0)) + (ret_h or 0)
            s['sum_target_ret'] = float(s.get('sum_target_ret', 0)) + (ret_t or 0)
            s['sum_spread'] = float(s.get('sum_spread', 0)) + spread
        rec = {
            'decision_type': decision_type,
            'intercept_date': item.get('intercept_date'),
            'followup_date': str(fu),
            'held_code': hc,
            'held_name': hn,
            'target_code': tc,
            'target_name': tn,
            'pair_corr': item.get('pair_corr'),
            'hold_momentum': item.get('hold_momentum'),
            'ret_hold': ret_h,
            'ret_target': ret_t,
            'spread': spread,
            'spread_pct_str': spread_pct_str,
            'verdict': verdict,
            'regime': item.get('regime'),
        }
        if not hasattr(g, 'corr_guard_review_history'):
            g.corr_guard_review_history = []
        g.corr_guard_review_history.append(rec)
        if len(g.corr_guard_review_history) > 50:
            g.corr_guard_review_history = g.corr_guard_review_history[-50:]
        if not hasattr(g, 'corr_guard_all_records'):
            g.corr_guard_all_records = []
        g.corr_guard_all_records.append(rec)

        def _px(v):
            if v is None or (isinstance(v, float) and (np.isnan(v) or not np.isfinite(v))):
                return 'N/A'
            return f"{float(v):.4f}"

        type_label = _corr_guard_type_label(decision_type)
        log.info(
            f"\n{'=' * 72}\n"
            f"📉 【相关性守卫·隔日复盘·{type_label}】决策日 {item.get('intercept_date')} 13:10 → 本日 {fu} 13:10\n"
            f"  市场状态(决策日): {item.get('regime', '—')}  |  P_adj={item.get('pair_corr')}  "
            f"持仓动量={item.get('hold_momentum')} (阈值 P_adj>{item.get('corr_threshold')} 动量≤{item.get('momentum_threshold')})\n"
            f"  继续持有 {hn}({hc}): 决策日价≈{_px(p0h)} → 本日价≈{_px(p1h)}  "
            f"区间收益 {_fmt_corr_pct_decimal(ret_h)}\n"
            f"  若买候选 {tn}({tc}): 决策日价≈{_px(p0t)} → 本日价≈{_px(p1t)}  "
            f"区间收益 {_fmt_corr_pct_decimal(ret_t)}\n"
            f"  ★ 收益差(持有−候选): {spread_pct_str}  →  {verdict}\n"
            f"{'=' * 72}"
        )
        log_corr_guard_dashboard(context, title_suffix='(隔日复盘后)')

    g.pending_corr_guard_reviews = keep


def _get_corr_regime_mom_guard_rules():
    custom = getattr(g, 'corr_regime_mom_guard_rules', None)
    if custom is not None:
        rules = copy.deepcopy(custom)
    else:
        rules = copy.deepcopy(default_corr_regime_mom_guard_rules())
    overrides = getattr(g, 'corr_regime_band_overrides', None) or {}
    for key, ov in overrides.items():
        if ov is None:
            continue
        if isinstance(key, (list, tuple)) and len(key) >= 2:
            regime, label = key[0], key[1]
        else:
            continue
        for rule in rules.get(regime, []):
            if rule.get('label') == label:
                if isinstance(ov, dict):
                    for k, v in ov.items():
                        rule[k] = copy.deepcopy(v)
                else:
                    rule['mode'] = 'intercept_only_in_bands'
                    rule['intercept_bands'] = copy.deepcopy(ov)
                break
    return rules


def _mom_in_corr_guard_band(mom, rule):
    """动量是否落入规则档 [mom_lo, mom_hi) 或 [mom_lo, mom_hi]。"""
    if mom is None or (isinstance(mom, float) and (pd.isna(mom) or not np.isfinite(mom))):
        return False
    m = float(mom)
    lo = float(rule.get('mom_lo', 0))
    hi = rule.get('mom_hi')
    if rule.get('mom_lo_exclusive'):
        if m <= lo:
            return False
    elif m < lo:
        return False
    if hi is None:
        return True
    hi = float(hi)
    if rule.get('hi_inclusive'):
        return m <= hi
    return m < hi


def _find_corr_regime_mom_guard_rule(regime, hold_mom, rules=None):
    rules = rules or _get_corr_regime_mom_guard_rules()
    regime_rules = rules.get(regime) or rules.get('震荡期') or []
    for rule in regime_rules:
        if _mom_in_corr_guard_band(hold_mom, rule):
            return rule
    return None


def _eval_corr_regime_rule_intercept(pair_corr, rule):
    """按单档规则判断是否应该拦截。返回 (should_intercept, reason_str)。"""
    if pair_corr is None:
        return False, 'P_adj缺失'
    p = float(pair_corr)
    mode = rule.get('mode', 'intercept_if_gt')
    label = rule.get('label', '?')

    if mode == 'always_allow':
        return False, f'{label} 一律放行'

    if mode == 'fallback_gt':
        gt = float(rule.get('intercept_gt', 0.65))
        if p > gt:
            return True, f'{label} P_adj>{gt:.2f}→拦截(震荡兜底)'
        return False, f'{label} P_adj≤{gt:.2f}→放行(震荡兜底)'

    if mode == 'intercept_if_gt':
        gt = float(rule.get('intercept_gt', 0.80))
        if p > gt:
            return True, f'{label} P_adj>{gt:.2f}→拦截'
        return False, f'{label} P_adj≤{gt:.2f}→放行'

    if mode == 'intercept_if_gt_with_release_le':
        release_le = float(rule.get('release_le', 0.70))
        gt = float(rule.get('intercept_gt', 0.73))
        if p <= release_le:
            return False, f'{label} P_adj≤{release_le:.2f}→放行'
        if p > gt:
            return True, f'{label} P_adj>{gt:.2f}→拦截'
        return False, f'{label} {release_le:.2f}<P_adj≤{gt:.2f}→放行(灰区)'

    if mode == 'intercept_outside_release_bands':
        release_le = float(rule.get('release_le', 0.85))
        blo = float(rule.get('release_band_lo', 0.89))
        bhi = float(rule.get('release_band_hi', 0.92))
        if p <= release_le:
            return False, f'{label} P_adj≤{release_le:.2f}→放行'
        if blo <= p <= bhi:
            return False, f'{label} {blo:.2f}≤P_adj≤{bhi:.2f}→放行'
        return True, f'{label} P_adj在({release_le:.2f},{blo:.2f})或>{bhi:.2f}→拦截'

    if mode == 'intercept_if_between':
        ilo = float(rule.get('intercept_lo', 0.62))
        ihi = float(rule.get('intercept_hi', 0.80))
        if rule.get('release_le') is not None and p <= float(rule['release_le']):
            return False, f'{label} P_adj≤{float(rule["release_le"]):.2f}→放行'
        if rule.get('release_gt') is not None and p > float(rule['release_gt']):
            return False, f'{label} P_adj>{float(rule["release_gt"]):.2f}→放行'
        if ilo <= p <= ihi:
            return True, f'{label} {ilo:.2f}≤P_adj≤{ihi:.2f}→拦截'
        return False, f'{label} P_adj在拦截带外→放行'

    if mode == 'intercept_only_in_bands':
        if rule.get('always_allow_le') is not None and p <= float(rule['always_allow_le']):
            return False, f'{label} P_adj≤{float(rule["always_allow_le"]):.2f}→放行'
        if rule.get('always_allow_gt') is not None and p > float(rule['always_allow_gt']):
            return False, f'{label} P_adj>{float(rule["always_allow_gt"]):.2f}→放行'
        bands = rule.get('intercept_bands') or []
        band_str = _format_corr_intercept_bands(bands)
        for b in bands:
            blo = float(b.get('lo', 0))
            bhi = float(b.get('hi', 1))
            if blo <= p <= bhi:
                return True, f'{label} {blo:.2f}≤P_adj≤{bhi:.2f}→拦截(带:{band_str})'
        return False, f'{label} P_adj不在拦截带({band_str})→放行'

    gt = float(rule.get('intercept_gt', 0.80))
    if p > gt:
        return True, f'{label} P_adj>{gt:.2f}→拦截(未知mode={mode})'
    return False, f'{label} P_adj≤{gt:.2f}→放行(未知mode={mode})'


def _corr_regime_guard_effective_threshold(rule):
    """供复盘登记/日志展示的代表性阈值。"""
    if not rule:
        return float(getattr(g, 'corr_hold_threshold', 0.80))
    mode = rule.get('mode')
    if mode == 'intercept_if_gt':
        return float(rule.get('intercept_gt', 0.80))
    if mode == 'intercept_if_gt_with_release_le':
        return float(rule.get('intercept_gt', 0.73))
    if mode == 'fallback_gt':
        return float(rule.get('intercept_gt', 0.65))
    if mode == 'intercept_outside_release_bands':
        return float(rule.get('release_le', 0.85))
    if mode == 'intercept_if_between':
        return float(rule.get('intercept_lo', 0.62))
    if mode == 'intercept_only_in_bands':
        bands = rule.get('intercept_bands') or []
        if bands:
            return float(bands[0].get('lo', 0.80))
    return float(getattr(g, 'corr_hold_threshold', 0.80))


def pick_target_with_corr_cap(context, candidate_pool, hold_code=None, max_padj=None, log_buffer=None):
    """
    在候选池（已按动量排序）中选取第一个与 hold_code 修正相关性 < max_padj 的标的。
    无持仓或无可算相关时返回候选第 1；全部过高相关时返回 None。
    """
    if not candidate_pool:
        return None
    if not getattr(g, 'pick_target_skip_high_corr', False):
        return candidate_pool[0]
    max_padj = float(max_padj if max_padj is not None else getattr(g, 'pick_target_max_padj', 0.85))
    codes = [item['etf'] for item in candidate_pool if item.get('etf')]
    if hold_code:
        codes = list({hold_code} | set(codes))
    adj_corr = get_adj_corr_matrix_cached(context, codes) if codes else None
    skipped = []
    for item in candidate_pool:
        tgt = item.get('etf')
        if not tgt:
            continue
        if hold_code and tgt == hold_code:
            return item
        if hold_code:
            p = get_pair_adjusted_corr(hold_code, tgt, adj_corr)
            if p is not None and float(p) >= max_padj:
                skipped.append((tgt, item.get('etf_name', tgt), float(p)))
                continue
        if log_buffer is not None and skipped:
            log_buffer.append(
                f"【低相关目标优选】相对持仓 {hold_code} 跳过 {len(skipped)} 只 (P_adj≥{max_padj:.2f})，"
                f"选用 {item.get('etf_name')}({tgt})"
            )
            if getattr(g, 'log_corr_detail', False):
                for tc, tn, pv in skipped[:5]:
                    log.info(f"【低相关目标优选】跳过 {tn}({tc}) P_adj={pv:.4f}")
        return item
    if log_buffer is not None:
        msg = (
            f"【低相关目标优选】候选池内相对 {hold_code or '—'} "
            f"无 P_adj<{max_padj:.2f} 的标的（共跳过{len(skipped)}只）"
        )
        log_buffer.append(msg)
        if getattr(g, 'log_corr_detail', False):
            log.info(msg)
    return None


def _resolve_hold_metric(hold_code, filtered_list, all_metrics, candidate_dict):
    if not hold_code:
        return None
    if hold_code in candidate_dict:
        return candidate_dict[hold_code]
    m = next((x for x in filtered_list if x.get('etf') == hold_code), None)
    if m is not None:
        return m
    return next((x for x in all_metrics if x.get('etf') == hold_code), None)


def resolve_switch_target(context, candidate_pool, hold_code, filtered_list, all_metrics, log_buffer):
    """
    防频换/换股：优先低相关候选；若无则按 anti_churn_immediate_requires_low_corr 保留原仓。
    """
    max_p = float(getattr(g, 'anti_churn_immediate_max_padj', getattr(g, 'pick_target_max_padj', 0.85)))
    picked = pick_target_with_corr_cap(context, candidate_pool, hold_code, max_padj=max_p, log_buffer=log_buffer)
    if picked is not None:
        return picked, 'low_corr_pick'
    if hold_code and getattr(g, 'anti_churn_immediate_requires_low_corr', False):
        hold_item = _resolve_hold_metric(hold_code, filtered_list, all_metrics, {item['etf']: item for item in candidate_pool})
        if hold_item is not None:
            msg = (
                f"【防频换·高相关无替代】候选相对 {hold_code} 均 P_adj≥{max_p:.2f} → "
                f"继续持有 {hold_item.get('etf_name')}({hold_code})"
            )
            log_buffer.append(msg)
            log.info(msg)
            return hold_item, 'keep_high_corr'
    if candidate_pool:
        return candidate_pool[0], 'fallback_first'
    return None, 'empty'


def should_corr_hold_guard_intercept(context, hold_mom, pair_corr, regime=None, candidate_mom=None):
    """
    判断是否应拦截换仓。
    返回 (should_intercept, detail_str, effective_corr_th, mom_th_for_log, decision_allow_type_hint)
    decision_allow_type_hint: None | 'mom' | 'low' — 放行时用于复盘分类
    """
    mom_th = float(getattr(g, 'corr_hold_momentum_max', 6))
    legacy_th = float(getattr(g, 'corr_hold_threshold', 0.80))
    mom_allow_above = float(getattr(g, 'corr_regime_momentum_always_allow_above', 7.0))

    if getattr(g, 'enable_corr_high_pair_overlay', False) and pair_corr is not None:
        ov_th = float(getattr(g, 'corr_high_pair_block_threshold', 0.88))
        ov_mom = float(getattr(g, 'corr_high_pair_overlay_mom_max', 8.0))
        if float(pair_corr) >= ov_th:
            if hold_mom is None or pd.isna(hold_mom):
                return True, f'高相关覆盖层 P_adj≥{ov_th:.2f} 动量缺失→拦截', ov_th, ov_mom, None
            if float(hold_mom) <= ov_mom:
                return True, f'高相关覆盖层 P_adj≥{ov_th:.2f} 且动量≤{ov_mom:.2f}→拦截', ov_th, ov_mom, None

    if not getattr(g, 'enable_corr_regime_mom_guard', False):
        if pair_corr is None:
            return False, '统一阈值模式 P_adj缺失', legacy_th, mom_th, 'low'
        if hold_mom is None or pd.isna(hold_mom):
            return False, f'统一阈值模式 动量缺失', legacy_th, mom_th, 'low'
        hm = float(hold_mom)
        if pair_corr > legacy_th and hm <= mom_th:
            return True, f'统一阈值 P_adj>{legacy_th:.2f} 且动量≤{mom_th:.2f}', legacy_th, mom_th, None
        if pair_corr > legacy_th and hm > mom_th:
            return False, f'统一阈值 动量>{mom_th:.2f} 豁免', legacy_th, mom_th, 'mom'
        return False, f'统一阈值 P_adj≤{legacy_th:.2f} 放行', legacy_th, mom_th, 'low'

    regime = regime or getattr(g, 'market_regime', '震荡期')
    rules = _get_corr_regime_mom_guard_rules()

    # 全局高动量豁免优先于分档规则（因此表内 >7 规则通常无需单列）。
    if hold_mom is not None and not pd.isna(hold_mom) and float(hold_mom) > mom_allow_above:
        if getattr(g, 'corr_mom_exempt_requires_low_corr', False) and pair_corr is not None:
            max_p = float(getattr(g, 'corr_mom_exempt_max_pair_corr', 0.82))
            if float(pair_corr) >= max_p:
                return (
                    True,
                    f'动量>{mom_allow_above:.2f} 但 P_adj≥{max_p:.2f}→拦截(高相关不放行动量豁免)',
                    max_p, mom_allow_above, None,
                )
        return False, f'分档守��� 动量>{mom_allow_above:.2f} 一律放行', legacy_th, mom_allow_above, 'mom'

    if hold_mom is None or pd.isna(hold_mom):
        if getattr(g, 'corr_regime_mom_guard_allow_legacy_when_mom_missing', False):
            if pair_corr is not None and pair_corr > legacy_th:
                return True, f'动量缺失→退回统一阈值 P_adj>{legacy_th:.2f}', legacy_th, mom_th, None
            return False, f'动量缺失→退回统一阈值 P_adj≤{legacy_th:.2f}', legacy_th, mom_th, 'low'
        return False, f'分档守卫 动量缺失→放行', legacy_th, mom_th, 'low'

    rule = _find_corr_regime_mom_guard_rule(regime, hold_mom, rules)
    if rule is None:
        if pair_corr is not None and pair_corr > legacy_th and float(hold_mom) <= mom_th:
            return True, f'{regime} 未命中动量档→统一阈值兜底拦截', legacy_th, mom_th, None
        return False, f'{regime} 未命中动量档→放行', legacy_th, mom_th, 'low'

    should_block, reason = _eval_corr_regime_rule_intercept(pair_corr, rule)
    eff_th = _corr_regime_guard_effective_threshold(rule)
    allow_hint = None if should_block else ('mom' if rule.get('mode') == 'always_allow' and float(hold_mom) > mom_th else 'low')
    return should_block, f'{regime} {reason}', eff_th, mom_th, allow_hint


def apply_corr_hold_guard(context, final_result, all_metrics, filtered_list, log_buffer):
    """
    持仓守卫：统一阈值模式或分市场状态×动量分档模式（g.enable_corr_regime_mom_guard）。
    """
    if not getattr(g, 'enable_corr_hold_guard', False):
        return final_result
    if int(getattr(g, 'holdings_num', 1)) != 1 or not final_result:
        return final_result
    holdings = [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]
    if not holdings:
        return final_result
    H = holdings[0]
    target_item = final_result[0]
    target = target_item.get('etf')
    if not target or H == target:
        return final_result
    mom_th = float(getattr(g, 'corr_hold_momentum_max', 7.0))
    legacy_th = float(getattr(g, 'corr_hold_threshold', 0.7))
    lookback = int(getattr(g, 'corr_lookback_days', 60))
    regime = getattr(g, 'market_regime', '—')
    regime_guard_on = getattr(g, 'enable_corr_regime_mom_guard', False)
    adj_corr = get_adj_corr_matrix_cached(context, [H, target])
    pair_corr = get_pair_adjusted_corr(H, target, adj_corr)
    hold_metric = next((m for m in filtered_list if m.get('etf') == H), None)
    if hold_metric is None:
        hold_metric = next((m for m in all_metrics if m.get('etf') == H), None)
    hold_mom = hold_metric.get('momentum_score') if hold_metric else None
    cand_mom = target_item.get('momentum_score')
    if cand_mom is None:
        cand_mom = target_item.get('momentum_rank_score')
    hold_name = (hold_metric or {}).get('etf_name') or get_security_name(H)
    tgt_name = target_item.get('etf_name') or get_security_name(target)
    log_buffer.append("")
    log_buffer.append(f">>> 修正相关性·持仓守卫 (回看{lookback}日) <<<")
    if regime_guard_on:
        if getattr(g, 'corr_mom_exempt_requires_low_corr', False):
            mom_exempt_note = (
                f"动量>{getattr(g, 'corr_regime_momentum_always_allow_above', 7.0):.2f}且P_adj<{getattr(g, 'corr_mom_exempt_max_pair_corr', 0.82):.2f}才豁免"
            )
        else:
            mom_exempt_note = (
                f"动量>{getattr(g, 'corr_regime_momentum_always_allow_above', 7.0):.2f}一律放行"
            )
        overlay_note = (
            f" | 覆盖层P_adj≥{getattr(g, 'corr_high_pair_block_threshold', 0.88):.2f}拦截"
            if getattr(g, 'enable_corr_high_pair_overlay', False) else ''
        )
        scheme_note = (
            f" | 预设={getattr(g, 'corr_guard_test_scheme', '—')}"
            if getattr(g, 'corr_guard_test_scheme', None) else ''
        )
        log_buffer.append(
            f"开关=开 模式={_corr_regime_mom_guard_mode_desc()} | 市场状态={regime} | {mom_exempt_note}{overlay_note}{scheme_note} | "
            f"持仓 {H} {hold_name} 动量={hold_mom if hold_mom is not None else 'N/A'} | "
            f"候选 {target} {tgt_name} 动量={cand_mom if cand_mom is not None else 'N/A'}"
        )
    else:
        log_buffer.append(
            f"开关=开 模式=统一阈值 P_adj>{legacy_th:.2f} 且动量≤{mom_th:.2f} | "
            f"持仓 {H} {hold_name} 动量={hold_mom if hold_mom is not None else 'N/A'} | "
            f"候选 {target} {tgt_name}"
        )
    if pair_corr is None:
        msg = "【相关性守卫】跳过: 无法计算 P_adj"
        log_buffer.append(msg)
        if getattr(g, 'log_corr_detail', False):
            log.info(msg)
        return final_result
    log_buffer.append(f"【相关性守卫】P_adj({H},{target})={pair_corr:.4f}")
    should_block, detail, corr_th, _, allow_hint = should_corr_hold_guard_intercept(
        context, hold_mom, pair_corr, regime=regime, candidate_mom=cand_mom,
    )
    log_buffer.append(f"【相关性守卫·判定】{detail}")
    if getattr(g, 'log_corr_detail', False):
        log.info(
            f"【相关性守卫】{H} vs {target} P_adj={pair_corr:.4f} "
            f"持仓动量={hold_mom} 状态={regime} 判定={detail}"
        )
    if should_block:
        t = (
            f"⏸️ 【相关性守卫】拦截换仓 → 保留 {hold_name}({H}) "
            f"(P_adj={pair_corr:.4f}, {detail})；"
            f"不买入 {tgt_name}({target})"
        )
        log_buffer.append(t)
        log.info(t)
        _record_corr_guard_intercept(
            context, H, hold_name, target, tgt_name,
            pair_corr, hold_mom, corr_th, mom_th,
        )
        log_buffer.append(
            f"【相关性守卫】已登记隔日复盘(决策日13:10→下一交易日13:10 持有vs候选收益差)，"
            f"详见统计看板"
        )
        if hold_metric is not None:
            return [hold_metric]
        return [{
            'etf': H, 'etf_name': hold_name,
            'momentum_score': hold_mom,
            'momentum_rank_score': hold_mom,
        }]
    use_mom_allow = (
        allow_hint == 'mom'
        or (
            not regime_guard_on
            and pair_corr > legacy_th
            and hold_mom is not None
            and not pd.isna(hold_mom)
            and float(hold_mom) > mom_th
        )
    )
    if use_mom_allow:
        log_buffer.append(
            f"✅ 【相关性守卫】放行换仓至 {tgt_name}({target}) ({detail})"
        )
        _record_corr_guard_review(
            context, CORR_GUARD_DECISION_ALLOW_MOM, H, hold_name, target, tgt_name,
            pair_corr, hold_mom, corr_th, mom_th,
        )
        log_buffer.append("【相关性守卫】已登记动量豁免放行隔日复盘，详见统计看板")
    else:
        log_buffer.append(
            f"✅ 【相关性守卫】放行换仓至 {tgt_name}({target}) ({detail})"
        )
        _record_corr_guard_review(
            context, CORR_GUARD_DECISION_ALLOW_LOW, H, hold_name, target, tgt_name,
            pair_corr, hold_mom, corr_th, mom_th,
        )
        log_buffer.append("【相关性守卫】已登记低相关放行隔日复盘，详见统计看板")
    return final_result


def update_sector_pool(context):
    if getattr(g, 'log_pool_update_details', False):
        log.info("【动态池更新】开始执行")
    if g.avg_etf_money_threshold is None:
        if getattr(g, 'log_pool_update_details', False):
            log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    
    FUND_COMPANIES = sorted(list(set([
        '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华', '南方', '汇添富', '国泰', '平安',
        '银华', '天弘', '建信', '工银', '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
        '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银', '东方红', '财通', '华商',
        '国联', '永赢', '金鹰', '德邦', '创金合信', '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海',
        '华润元大', '大成', '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城', '中金', '浙商证券',
        '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航', '中融', '中邮', '中庚', '中信保诚', '中信建投',
        '中银国际', '中银证券', '九泰', '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林',
        '国联安', '国金', '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛', '长江证券', '鹏扬'
    ])), key=len, reverse=True)
    
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)
    
    SPECIAL_GROUPS = sorted([
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS科技'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创', '债券', '债汇', '债指', '债沪', '债易', '债基', '债兴', '债摩', '债', 'AAA'], key=len, reverse=True)},
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)
    
    exclude_keywords = sorted(list(set([
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ])), key=len, reverse=True)
    
    try:
        df_etf = get_all_securities(['etf'])
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"获取全市场ETF列表失败: {e}")
        return
    
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新】全市场ETF总数: {len(etf_list)}只")
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0
    
    for code in etf_list:
        try:
            name = g.etf_names_dict.get(code, str(code))
            is_special = False
            matched_group = None
            for group in SPECIAL_GROUPS:
                for kw in group['keywords']:
                    if kw in name:
                        is_special = True
                        matched_group = group['name']
                        break
                if is_special:
                    break
            is_excluded = False
            for k in exclude_keywords:
                if k in name:
                    is_excluded = True
                    excluded_count += 1
                    break
            if not is_excluded:
                if is_special:
                    special_etfs.append(code)
                    special_group_map[code] = matched_group
                else:
                    normal_etfs.append(code)
        except Exception:
            continue
    
    group_counts = {}
    for code in special_etfs:
        group_name = special_group_map.get(code, '未知')
        group_counts[group_name] = group_counts.get(group_name, 0) + 1
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新】特别组分布: {group_counts}")
        log.info(f"【动态池更新】进入特别组: {len(special_etfs)}只")
        log.info(f"【动态池更新】进入普通组: {len(normal_etfs)}只")
        log.info(f"【动态池更新】排除ETF: {excluded_count}只")
    
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold
    
    def filter_by_liquidity(etf_codes, group_name):
        if not etf_codes:
            return pd.Series(dtype=float), 0
        try:
            price_data = get_price(etf_codes, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                return pd.Series(dtype=float), len(etf_codes)
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            qualified_series = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
            filtered_out = len(etf_codes) - len(qualified_series)
            return qualified_series, filtered_out
        except Exception:
            return pd.Series(dtype=float), len(etf_codes)
    
    normal_qualified, normal_filtered_out = filter_by_liquidity(normal_etfs, "普通组")
    special_qualified, special_filtered_out = filter_by_liquidity(special_etfs, "特别组")
    normal_sorted = normal_qualified.index.tolist()
    special_sorted = special_qualified.index.tolist()
    if getattr(g, 'enable_corr_pool_filter', False):
        base_pool = list(getattr(g, 'filtered_fixed_pool', None) or g.fixed_etf_pool or [])
        th = float(getattr(g, 'corr_pool_threshold', 0.5))
        lb = int(getattr(g, 'corr_lookback_days', 60))
        log.info(
            f"【动态池·修正相关性过滤】开启 阈值<{th} 回看{lb}日 基础池{len(base_pool)}只"
        )
        n_before, s_before = len(normal_sorted), len(special_sorted)
        normal_sorted = filter_pool_by_max_corr(context, normal_sorted, base_pool, th, lb)
        special_sorted = filter_pool_by_max_corr(context, special_sorted, base_pool, th, lb)
        log.info(
            f"【动态池·修正相关性过滤】普通组 {n_before}→{len(normal_sorted)} "
            f"特别组 {s_before}→{len(special_sorted)}"
        )
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新】特别组流动性过滤: {len(special_etfs)}→{len(special_sorted)}只")
        log.info(f"【动态池更新】普通组流动性过滤: {len(normal_etfs)}→{len(normal_sorted)}只")
    
    if not normal_sorted and not special_sorted:
        log.warning("【动态池更新】无ETF通过流动性过滤")
        g.dynamic_etf_pool = []
        return
    
    def get_remove_words_for_etf(_, is_special, matched_group_name):
        if not is_special:
            return []
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                return group['remove_words']
        return []
    
    def clean_name(original_name, is_special=False, matched_group_name=None):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        if is_special and matched_group_name:
            for word in get_remove_words_for_etf(original_name, is_special, matched_group_name):
                cleaned = cleaned.replace(word, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()
    
    normal_industry_groups = {}
    for code in normal_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            money = normal_qualified[code]
            cleaned = clean_name(original_name, is_special=False)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            if industry_key not in normal_industry_groups:
                normal_industry_groups[industry_key] = []
            normal_industry_groups[industry_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': '普通'
            })
        except Exception:
            continue
    
    special_industry_groups = {}
    for code in special_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified[code]
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = f"{matched_group}_{industry_key}"
            if group_key not in special_industry_groups:
                special_industry_groups[group_key] = []
            special_industry_groups[group_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': matched_group, 'display_group': matched_group
            })
        except Exception:
            continue
    
    final_pool_info = []
    for industry_key, items in normal_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    for group_key, items in special_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    
    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    top_100 = final_pool_info_sorted[:100]
    g.dynamic_etf_pool = [item['code'] for item in top_100]
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF")
    if getattr(g, 'log_pool_update_details', False) and len(g.dynamic_etf_pool) <= 10:
        for item in top_100[:10]:
            log.info(f"  {item['code']} {item['original_name']} 日均成交额: {item['money']/1e8:.2f}亿")


def filter_fixed_pool_by_volume(context):
    if getattr(g, 'log_pool_update_details', False):
        log.info("【固定池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        if getattr(g, 'log_pool_update_details', False):
            log.info("【固定池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.fixed_etf_pool:
        if getattr(g, 'log_pool_update_details', False):
            log.info("【固定池过滤】固定池为空，跳过过滤")
        return
    dynamic_threshold = g.avg_etf_money_threshold
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【固定池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.fixed_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【固定池过滤】无法获取成交额数据，跳过过滤")
            g.filtered_fixed_pool = g.fixed_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_fixed_pool = qualified.index.tolist()
        removed = set(g.fixed_etf_pool) - set(new_fixed_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            if getattr(g, 'log_pool_update_details', False):
                log.info(f"【固定池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_fixed_pool = new_fixed_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        if getattr(g, 'log_pool_update_details', False):
            log.info(f"【固定池过滤】保留高流动性ETF({len(new_fixed_pool)}只)")
    except Exception as e:
        log.warning(f"【固定池过滤】异常: {e}")
        g.filtered_fixed_pool = g.fixed_etf_pool[:]


def daily_merge_etf_pools(context):
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    if getattr(g, 'log_pool_update_details', False):
        log.info("【合并ETF池】开始执行")
        log.info(f"【合并池统计】固定池: {len(g.filtered_fixed_pool)}只, 动态池: {len(g.dynamic_etf_pool)}只, 合并后: {len(merged)}只")
    g.merged_etf_pool = merged


def calculate_and_log_ranked_etfs(context):
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        g.last_metrics_by_etf_code = {}
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list


def calculate_momentum_score(price_series, lookback_days):
    if len(price_series) < lookback_days + 1:
        return None, None, None
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2
    W_sum = np.sum(W)
    x_bar = np.sum(W * x) / W_sum
    y_bar = np.sum(W * y) / W_sum
    dx = x - x_bar
    dy = y - y_bar
    variance_x = np.sum(W * dx**2)
    if variance_x == 0:
        return 0, 0, 0
    slope = np.sum(W * dx * dy) / variance_x
    intercept = y_bar - slope * x_bar
    annualized_returns = math.exp(slope * 250) - 1
    y_pred = slope * x + intercept
    ss_res = np.sum(weights * (y - y_pred) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2) 
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    momentum_score = annualized_returns * r_squared
    return momentum_score, annualized_returns, r_squared


def _whipsaw_global_period_ok():
    if not getattr(g, 'whipsaw_options_only_in_range', True):
        return True
    return getattr(g, 'market_regime', '震荡期') == '震荡期'


def _use_smoothed_momentum_prices():
    if not getattr(g, 'enable_smoothed_momentum_input', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    if getattr(g, 'smoothed_momentum_only_in_range', True):
        return getattr(g, 'market_regime', '震荡期') == '震荡期'
    return True


def _use_range_long_momentum_limits():
    if not getattr(g, 'enable_range_momentum_floor', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    return getattr(g, 'market_regime', '震荡期') == '震荡期'


def _use_range_short_momentum_limits():
    if not getattr(g, 'enable_range_short_momentum_limits', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    return getattr(g, 'market_regime', '震荡期') == '震荡期'


def _dual_positive_filter_should_apply():
    if not getattr(g, 'enable_dual_positive_momentum', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    if getattr(g, 'dual_positive_only_in_range', True):
        return getattr(g, 'market_regime', '震荡期') == '震荡期'
    return True


def _effective_r2_threshold_whipsaw():
    base = float(getattr(g, 'r2_threshold', 0.4))
    # P0-2：正常期可单独放宽 R² 阈值；关闭开关即回退到 base
    if (
        getattr(g, 'enable_p0_state_tuning_patch', False)
        and getattr(g, 'market_regime', '震荡期') == '正常期'
    ):
        return float(getattr(g, 'normal_r2_threshold_override', base))
    if not getattr(g, 'enable_range_r2_veto', False):
        return base
    if not _whipsaw_global_period_ok():
        return base
    if getattr(g, 'market_regime', '震荡期') != '震荡期':
        return base
    return float(getattr(g, 'r2_threshold_range_bound', 0.9))


def _effective_laplace_min_slope():
    """返回当前状态应使用的拉普拉斯斜率阈值（支持正常期单独放宽）。"""
    base = float(getattr(g, 'laplace_min_slope', 0.002))
    if (
        getattr(g, 'exp_enable_normal_laplace_min_slope_override', False)
        and getattr(g, 'market_regime', '震荡期') == '正常期'
    ):
        return float(getattr(g, 'exp_normal_laplace_min_slope_override', base))
    return base


def _effective_laplace_s():
    """当前市场状态下拉普拉斯一阶平滑系数 s（越大滤波越宽松）。关闭差异化时用 laplace_s_param。"""
    base = float(getattr(g, 'laplace_s_param', 0.05))
    if not getattr(g, 'enable_laplace_s_regime_differentiation', False):
        return base
    regime = getattr(g, 'market_regime', '震荡期')
    if regime == '正常期':
        return float(getattr(g, 'laplace_s_param_normal', 0.07))
    if regime == '走弱期':
        return float(getattr(g, 'laplace_s_param_weak', 0.10))
    return base


def _coerce_scalar_price(x):
    if x is None:
        return None
    try:
        arr = np.asarray(x, dtype=float).ravel()
        if arr.size == 0:
            return None
        return float(arr[0])
    except Exception:
        return None


def _get_intraday_price_with_fallback(context, security):
    """
    获取当前时点价格：
    1) 优先 get_current_data().last_price
    2) 回退到 1 分钟 get_price 的 close（覆盖已卖出且不在当前订阅集合的标的）
    """
    # 1) 优先 current_data
    try:
        cd = get_current_data()
        if security in cd:
            cur = _coerce_scalar_price(cd[security].last_price)
            if cur is not None and cur > 0:
                return cur
    except Exception:
        pass
    # 2) 回退到分钟收盘价
    try:
        dt = getattr(context, 'current_dt', None)
        dfm = get_price(
            security,
            end_date=dt,
            count=1,
            frequency='1m',
            fields=['close'],
            panel=False,
            skip_paused=False
        )
        if dfm is not None and not dfm.empty:
            if 'close' in dfm.columns:
                cur = _coerce_scalar_price(dfm['close'].iloc[-1])
            else:
                cur = _coerce_scalar_price(dfm.iloc[-1, -1])
            if cur is not None and cur > 0:
                return cur
    except Exception:
        pass
    return None


def _scalar_momentum_finite(v):
    """动量得分是否为有限数值（统一转为 float + math.isfinite，避免 np.isfinite 与 not 在非标量上的异常）。"""
    if v is None:
        return False
    try:
        x = float(np.asarray(v, dtype=float).ravel()[0])
        return math.isfinite(x)
    except Exception:
        return False


def build_short_momentum_3day_pattern_str(vals, eps=1e-12):
    """
    由三个递进端点上的短期动量得分生成三位模式（与 get_short_momentum_3day_pattern 约定一致：p1 p2 p2）。
    """
    if not vals or len(vals) != 3:
        return "N/A"
    if not all(_scalar_momentum_finite(v) for v in vals):
        return "N/A"
    try:
        v0 = float(np.asarray(vals[0], dtype=float).ravel()[0])
        v1 = float(np.asarray(vals[1], dtype=float).ravel()[0])
        v2 = float(np.asarray(vals[2], dtype=float).ravel()[0])
    except Exception:
        return "N/A"
    d1, d2 = v1 - v0, v2 - v1

    def _dir(d):
        if d > eps:
            return "增"
        if d < -eps:
            return "减"
        return "平"

    p1, p2 = _dir(d1), _dir(d2)
    return f"{p1}{p2}{p2}"


def snapshot_momentum_for_security(context, security):
    """卖出复盘：与持仓当日框架一致的长/短动量快照（attribute_history + 当前价）。"""
    try:
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return None
        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        need = max(g.lookback_days, short_lb)
        bars = max(need + 25, 35)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < need:
            return None
        hist = df['close'].values.astype(float)
        price_series = np.append(hist, cur)
        price_for = price_series
        if _use_smoothed_momentum_prices():
            w = max(1, int(getattr(g, 'smoothed_ma_window', 5)))
            price_for = pd.Series(price_series).rolling(window=w, min_periods=1).mean().values
        lm, lar, lr2 = calculate_momentum_score(price_for, g.lookback_days)
        sm, sar, sr2 = calculate_momentum_score(price_for, short_lb)
        return {
            'momentum_score': lm,
            'short_momentum_score': sm,
            'annualized_returns': lar,
            'short_annualized_returns': sar,
            'r_squared': lr2,
            'short_r_squared': sr2,
            'price': cur,
            'market_regime': getattr(g, 'market_regime', ''),
        }
    except Exception:
        return None


def get_short_momentum_3day_pattern(context, security):
    """
    返回短期动量近三个交易日的方向模式（如：增增增/增减增）及三个动量值。
    价格序列为日 K（仅交易日）收盘价 + 当日当前价；三个端点为连续三个交易日递进，非自然日。
    """
    try:
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return "N/A", []

        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        # 需要保证可构造「前交易日、昨交易日、今交易日(���前价)」三组短期动量输入（日 K 仅含交易日）
        bars = max(short_lb + 10, 40)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < short_lb + 4:
            return "N/A", []

        hist = df['close'].values.astype(float)
        price_series = np.append(hist, cur)

        # 三个观测点：前交易日、昨交易日、今交易日（按交易日递进；最后一根为当日盘中价）
        ends = [len(price_series) - 3, len(price_series) - 2, len(price_series) - 1]
        vals = []
        for end in ends:
            sub = price_series[:end + 1]
            if len(sub) < short_lb + 1:
                vals.append(None)
                continue
            sm, _, _ = calculate_momentum_score(sub, short_lb)
            vals.append(sm)

        if len(vals) != 3 or any(v is None for v in vals):
            return "N/A", vals
        if not all(_scalar_momentum_finite(v) for v in vals):
            return "N/A", vals
        pattern = build_short_momentum_3day_pattern_str(vals)
        return pattern, vals
    except Exception:
        return "N/A", []


def _first_trading_day_after(d):
    """严格晚于 d 的第一个交易日（d 为卖出当日）。"""
    try:
        tds = get_trade_days(start_date=d, count=60)
        if tds is None or len(tds) == 0:
            return None
        for x in tds:
            xd = x.date() if hasattr(x, 'date') else x
            if xd > d:
                return xd
        return None
    except Exception:
        return None


def get_short_momentum_last_n_endpoint_scores(context, security, n=4):
    """
    与 get_short_momentum_3day_pattern 相同口径：在最近 n 个「交易日」递进端点上计算短期动量得分。
    数据为日 K（attribute_history 1d，仅交易日）+ 当日当前价；共 n 个端点，非自然日。
    """
    try:
        n = int(n)
        if n < 1:
            return None
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return None
        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        bars = max(short_lb + n + 10, 40)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < short_lb + n + 1:
            return None
        hist = df['close'].values.astype(float)
        price_series = np.append(hist, cur)
        if len(price_series) < short_lb + n:
            return None
        vals = []
        for k in range(n):
            end = len(price_series) - n + k
            sub = price_series[:end + 1]
            if len(sub) < short_lb + 1:
                vals.append(None)
                continue
            sm, _, _ = calculate_momentum_score(sub, short_lb)
            vals.append(sm)
        if any(v is None or not _scalar_momentum_finite(v) for v in vals):
            return None
        return vals
    except Exception:
        return None


def get_long_short_momentum_last_n_endpoint_scores(context, security, n=4):
    """
    最近 n 个交易日递进端点上的长/短动量序列（与卖出复盘口径一致）：
    - 价格序列：日K收盘（交易日）+ 当日当前价
    - 每个端点都分别计算 long(lookback_days) 与 short(short_momentum_lookback)
    """
    try:
        n = int(n)
        if n < 1:
            return None
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return None
        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        long_lb = int(getattr(g, 'lookback_days', 25))
        need = max(long_lb, short_lb)
        # 放大窗口，避免因停牌/脏数据导致可用样本不足
        bars = max(need + n + 60, 120)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < need + 2:
            return None
        hist_raw = pd.to_numeric(df['close'], errors='coerce').values.astype(float)
        # 去掉非数值/非正价格点，提升序列健壮性
        hist = hist_raw[np.isfinite(hist_raw) & (hist_raw > 0)]
        if len(hist) < need + 2:
            return None
        price_series = np.append(hist, cur)
        if len(price_series) < need + 1:
            return None

        long_vals = []
        short_vals = []
        for k in range(n):
            end = len(price_series) - n + k
            sub = price_series[:end + 1]
            if len(sub) < need + 1:
                long_vals.append(None)
                short_vals.append(None)
                continue
            lm, _, _ = calculate_momentum_score(sub, long_lb)
            sm, _, _ = calculate_momentum_score(sub, short_lb)
            long_vals.append(float(np.asarray(lm).ravel()[0]) if _scalar_momentum_finite(lm) else None)
            short_vals.append(float(np.asarray(sm).ravel()[0]) if _scalar_momentum_finite(sm) else None)
        # 至少保证各自有两个可用点，便于观察趋势
        if sum(v is not None for v in long_vals) < 2 and sum(v is not None for v in short_vals) < 2:
            return None
        return {'long': long_vals, 'short': short_vals}
    except Exception:
        return None


def log_pending_short_momentum_3up_followups(context):
    """下一交易日 13:10：卖出价至本日 13:10 区间收益 + 近4个交易日端点短动量 + 当前长/短动量等。"""
    pending = getattr(g, 'pending_sm3up_sell_followups', None)
    if not pending:
        return
    today = context.current_dt.date()
    keep = []

    def _fmt_m(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v):.4f}"

    def _fmt_pct(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v) * 100:.2f}%"

    def _fmt_nvals(vals):
        if not vals:
            return "N/A"
        return " -> ".join(_fmt_m(v) for v in vals)

    def _slope(vals):
        if not vals or len(vals) < 2:
            return None
        try:
            arr = []
            for v in vals:
                if v is None:
                    continue
                x = float(np.asarray(v, dtype=float).ravel()[0])
                if np.isfinite(x):
                    arr.append(x)
            if len(arr) < 2:
                return None
            return (arr[-1] - arr[0]) / float(len(arr) - 1)
        except Exception:
            return None

    def _risk_label(ret_pct, long_vals, short_vals):
        """
        放强追弱风险标签（经验规则）：
        - 高：次日收益显著为正，且短/长动量斜率至少一项明显上行
        - 低：次日收益显著为负，且短/长动量斜率至少一项下行
        - 其余：中
        """
        sl = _slope(short_vals)
        ll = _slope(long_vals)
        if ret_pct is None or not np.isfinite(ret_pct):
            return "未知", sl, ll, "收益缺失"
        up = (sl is not None and sl > 0.01) or (ll is not None and ll > 0.005)
        down = (sl is not None and sl < -0.01) or (ll is not None and ll < -0.005)
        if ret_pct >= 1.0 and up:
            return "高", sl, ll, "次日继续走强且动量延续上行"
        if ret_pct <= -1.0 and down:
            return "低", sl, ll, "次日回落且动量转弱"
        if ret_pct >= 1.5:
            return "高", sl, ll, "次日收益显著为正"
        if ret_pct <= -1.5:
            return "低", sl, ll, "次日收益显著为负"
        return "中", sl, ll, "信号分化或幅度不显著"

    for item in pending:
        fu = item.get('followup_date')
        if fu is None:
            continue
        if fu < today:
            log.warning(
                f"【短动量三连涨-卖出跟踪】跳过过期项 {item.get('name')}({item.get('code')})，"
                f"计划复盘日={fu} 当前={today}"
            )
            continue
        if fu > today:
            keep.append(item)
            continue
        # fu == today，在午盘 13:10 流水线中复盘
        code = item.get('code')
        name = item.get('name') or get_security_name(code)
        px0 = item.get('sell_price_1310')
        px1 = _get_intraday_price_with_fallback(context, code)
        ret_pct = float('nan')
        if px0 and px0 > 0 and px1 and px1 > 0:
            ret_pct = (px1 / float(px0) - 1.0) * 100.0
        snap = snapshot_momentum_for_security(context, code) or {}
        mom4 = get_long_short_momentum_last_n_endpoint_scores(context, code, 4) or {}
        lm4 = mom4.get('long')
        sm4 = mom4.get('short')
        sm_pat_now, sm_vals_now = get_short_momentum_3day_pattern(context, code)
        if sm_pat_now == "N/A" and isinstance(sm_vals_now, (list, tuple)) and len(sm_vals_now) == 3:
            if all(_scalar_momentum_finite(v) for v in sm_vals_now):
                _sp = build_short_momentum_3day_pattern_str(sm_vals_now)
                if _sp != "N/A":
                    sm_pat_now = _sp
        # 若三日模式函数失败，则退化为使用近4短动量末3点构造模式
        if sm_pat_now == "N/A" and sm4 and len(sm4) >= 3:
            sm_pat_now = build_short_momentum_3day_pattern_str(sm4[-3:])
            sm_vals_now = sm4[-3:]
        lm4_line = _fmt_nvals(lm4) if lm4 else "N/A"
        sm4_line = _fmt_nvals(sm4) if sm4 else "N/A"
        ret_line = f"{ret_pct:.4f}%" if np.isfinite(ret_pct) else "N/A"
        risk, slp_s, slp_l, risk_reason = _risk_label(ret_pct, lm4, sm4)
        slp_s_line = "N/A" if slp_s is None else f"{slp_s:.4f}"
        slp_l_line = "N/A" if slp_l is None else f"{slp_l:.4f}"
        log.info(
            f"\n{'=' * 72}\n"
            f"📈 【短动量三连涨-卖出跟踪】下一交易日 13:10 复盘  {name}({code})\n"
            f"  卖出日: {item.get('sell_date')} 13:10  卖出价≈{_fmt_m(px0)}  原因: {item.get('exit_reason', '—')}\n"
            f"  本日 13:10 价≈{_fmt_m(px1)}  "
            f"区间收益(卖后→今13:10): {ret_line}\n"
            f"  当前 长动量={_fmt_m(snap.get('momentum_score'))}  短动量={_fmt_m(snap.get('short_momentum_score'))}  "
            f"R²={_fmt_m(snap.get('r_squared'))}  短R²={_fmt_m(snap.get('short_r_squared'))}\n"
            f"  当前 年化收益≈{_fmt_pct(snap.get('annualized_returns'))}  短期年化≈{_fmt_pct(snap.get('short_annualized_returns'))}  "
            f"市场状态={snap.get('market_regime', getattr(g, 'market_regime', '—'))}\n"
            f"  近4日(均为交易日)端点长期动量得分: {lm4_line}\n"
            f"  近4日(均为交易日)端点短期动量得分: {sm4_line}\n"
            f"  近3日(均为交易日)短期动量模式(当日视角): {sm_pat_now}  ({_fmt_nvals(sm_vals_now)})\n"
            f"  放强追弱风险标签: {risk}  |  短斜率={slp_s_line}  长斜率={slp_l_line}  |  依据: {risk_reason}\n"
            f"{'=' * 72}"
        )
    g.pending_sm3up_sell_followups = keep


def record_buy_trade_entry(context, etf_code):
    """买入成功后记录开仓快照，供卖出复盘配对。"""
    try:
        # A.2 改进：记录新建仓的买入日，用于最小持有天数判定（旧仓不会有此键，自然不受约束）
        if getattr(g, 'A2_enable_min_hold_days', False):
            if not hasattr(g, 'A2_buy_first_day_map') or not isinstance(g.A2_buy_first_day_map, dict):
                g.A2_buy_first_day_map = {}
            # 若已是持仓中（同 ETF 加仓）保留原买入日，否则记录今天
            if etf_code not in g.A2_buy_first_day_map:
                g.A2_buy_first_day_map[etf_code] = context.current_dt.date()
        cd = get_current_data()
        px = _coerce_scalar_price(cd[etf_code].last_price) if etf_code in cd else None
        pos = context.portfolio.positions.get(etf_code)
        met = getattr(g, 'last_metrics_by_etf_code', {}).get(etf_code)
        if met is None:
            met = snapshot_momentum_for_security(context, etf_code) or {}
        g.trade_entry_open[etf_code] = {
            'code': etf_code,
            'name': get_security_name(etf_code),
            'buy_datetime': context.current_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'buy_date': str(context.current_dt.date()),
            'buy_price_last': px,
            'buy_avg_cost': float(pos.avg_cost) if pos and pos.avg_cost else None,
            'buy_amount': int(pos.total_amount) if pos else None,
            'buy_long_m': met.get('momentum_score'),
            'buy_short_m': met.get('short_momentum_score'),
            'buy_r2': met.get('r_squared'),
            'buy_regime': getattr(g, 'market_regime', ''),
            'buy_annual_ret': met.get('annualized_returns'),
        }
    except Exception as e:
        log.warning(f"【交易记录】买入快照异常 {etf_code}: {e}")


def record_etf_roundtrip_on_sell(context, security, sold_amount, avg_cost_before, sell_price, exit_reason):
    """清仓后：复盘日志 + 写入 trade_roundtrip_history。"""
    name = get_security_name(security)
    entry = getattr(g, 'trade_entry_open', {}).pop(security, None) or {}
    # A.2 改进：清仓时一并清理新仓买入日记录
    if isinstance(getattr(g, 'A2_buy_first_day_map', None), dict):
        g.A2_buy_first_day_map.pop(security, None)
    sell_snap = snapshot_momentum_for_security(context, security) or {}
    sell_fee = 0.0001
    cost_basis = sold_amount * avg_cost_before if avg_cost_before and sold_amount else 0.0
    proceeds = sold_amount * sell_price * (1.0 - sell_fee) if sold_amount and sell_price else 0.0
    pnl_abs = proceeds - cost_basis
    pnl_pct = (pnl_abs / cost_basis * 100.0) if cost_basis > 1e-9 else float('nan')

    buy_dt = entry.get('buy_datetime', '—')
    sell_dt = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    bl = entry.get('buy_long_m')
    bs = entry.get('buy_short_m')
    sl = sell_snap.get('momentum_score')
    ss = sell_snap.get('short_momentum_score')
    # 年化收益等额外参数（便于卖出复盘）
    buy_annual_ret = entry.get('buy_annual_ret')
    sell_annual_ret = sell_snap.get('annualized_returns')
    sell_short_annual_ret = sell_snap.get('short_annualized_returns')
    sell_sm_pattern, sell_sm_vals = get_short_momentum_3day_pattern(context, security)
    if sell_sm_pattern == "N/A" and isinstance(sell_sm_vals, (list, tuple)) and len(sell_sm_vals) == 3:
        if all(_scalar_momentum_finite(v) for v in sell_sm_vals):
            _fix_pat = build_short_momentum_3day_pattern_str(sell_sm_vals)
            if _fix_pat != "N/A":
                sell_sm_pattern = _fix_pat

    # 短动量近三个交易日连续走强（与 get_short_momentum_3day_pattern 中「增增增」一致）→ 下一交易日 13:10 复盘区间收益
    if sell_sm_pattern == "增增增":
        fu = _first_trading_day_after(context.current_dt.date())
        if fu:
            g.pending_sm3up_sell_followups.append({
                'code': security,
                'name': name,
                'sell_date': str(context.current_dt.date()),
                'sell_price_1310': float(sell_price),
                'followup_date': fu,
                'exit_reason': exit_reason,
            })
            log.info(
                f"【短动量三连涨卖出】{name}({security}) 已纳入下一交易日 13:10 区间收益跟踪 "
                f"(卖价≈{float(sell_price):.4f} 复盘日={fu})"
            )

    rec = {
        'code': security,
        'name': name,
        'buy_datetime': buy_dt,
        'sell_datetime': sell_dt,
        'buy_date': entry.get('buy_date', ''),
        'exit_reason': exit_reason,
        'buy_long_m': bl,
        'buy_short_m': bs,
        'sell_long_m': sl,
        'sell_short_m': ss,
        'buy_r2': entry.get('buy_r2'),
        'sell_r2': sell_snap.get('r_squared'),
        'buy_regime': entry.get('buy_regime'),
        'sell_regime': sell_snap.get('market_regime', getattr(g, 'market_regime', '')),
        'buy_annual_ret': buy_annual_ret,
        'sell_annual_ret': sell_annual_ret,
        'sell_short_annual_ret': sell_short_annual_ret,
        'avg_cost': avg_cost_before,
        'sell_price': sell_price,
        'sold_amount': sold_amount,
        'pnl_abs': pnl_abs,
        'pnl_pct': pnl_pct,
    }
    if not hasattr(g, 'trade_roundtrip_history'):
        g.trade_roundtrip_history = []
    g.trade_roundtrip_history.append(rec)

    def _fmt_m(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v):.4f}"

    def _fmt_pct(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v) * 100:.2f}%"

    def _fmt_3vals(vals):
        if not vals or len(vals) != 3:
            return "N/A"
        out = []
        for v in vals:
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                out.append("N/A")
            else:
                out.append(f"{float(v):.4f}")
        return " -> ".join(out)

    def _label_sm_pattern(pattern):
        """将短动量模式粗略归类为：持续走强 / 持续走弱 / 震荡。"""
        if not pattern or pattern == "N/A":
            return "未知"
        # 典型强/弱趋势：全增或全减
        if pattern.count("增") == len(pattern) and "增" in pattern:
            return "持续走强"
        if pattern.count("减") == len(pattern) and "减" in pattern:
            return "持续走弱"
        # 其他混合情况统一视为震荡
        return "震荡"

    # 当天计划买入的目标标的（用于对比：卖出标的 vs 今日买入标的）
    target_lines = []
    try:
        today_targets = list(getattr(g, 'target_etfs_list', []) or [])
    except Exception:
        today_targets = []
    if today_targets:
        ranked = getattr(g, 'ranked_etfs_result', []) or []
        ranked_map = {}
        try:
            ranked_map = {m.get('etf'): m for m in ranked if isinstance(m, dict) and m.get('etf')}
        except Exception:
            ranked_map = {}
        for t in today_targets[:max(1, int(getattr(g, 'holdings_num', 1)))]:
            t_name = get_security_name(t)
            met = ranked_map.get(t) or getattr(g, 'last_metrics_by_etf_code', {}).get(t)
            if met is None:
                met = snapshot_momentum_for_security(context, t) or {}
            # 兼容两种键名：momentum_score / short_momentum_score 与 sell_xxx 使用的 annualized_returns / r_squared
            t_lm = met.get('momentum_score')
            t_sm = met.get('short_momentum_score')
            t_r2 = met.get('r_squared')
            t_ar = met.get('annualized_returns')
            t_sar = met.get('short_annualized_returns')
            t_reg = met.get('market_regime', getattr(g, 'market_regime', ''))
            t_sm_pattern, t_sm_vals = get_short_momentum_3day_pattern(context, t)
            if t_sm_pattern == "N/A" and isinstance(t_sm_vals, (list, tuple)) and len(t_sm_vals) == 3:
                if all(_scalar_momentum_finite(v) for v in t_sm_vals):
                    _tp = build_short_momentum_3day_pattern_str(t_sm_vals)
                    if _tp != "N/A":
                        t_sm_pattern = _tp
            target_lines.append(
                f"  今日买入标的(目标): {t_name}({t})  |  长动量={_fmt_m(t_lm)}  短动量={_fmt_m(t_sm)}  "
                f"R²={_fmt_m(t_r2)}  市场状态={t_reg or '—'}  年化≈{_fmt_pct(t_ar)}  短期年化≈{_fmt_pct(t_sar)}  "
                f"短动量近三日(均为交易日)={t_sm_pattern} [{_label_sm_pattern(t_sm_pattern)}] "
                f"({_fmt_3vals(t_sm_vals)})"
            )
    else:
        target_lines.append("  今日买入标的(目标): 无（空仓/无目标）")

    log.info(
        f"\n{'=' * 72}\n"
        f"📋 【卖出复盘】{name}({security})  |  原因: {exit_reason}  |  卖出市场状态: {rec['sell_regime']}\n"
        f"  买入时间: {buy_dt}  →  卖出时间: {sell_dt}\n"
        f"  买入时 长动量={_fmt_m(bl)}  短动量={_fmt_m(bs)}  R²={_fmt_m(entry.get('buy_r2'))}  市场状态={entry.get('buy_regime', '—')}\n"
        f"  卖出时 长动量={_fmt_m(sl)}  短动量={_fmt_m(ss)}  R²={_fmt_m(sell_snap.get('r_squared'))}  市场状态={rec['sell_regime']}\n"
        f"  卖出标的短动量近三日(均为交易日): {sell_sm_pattern} [{_label_sm_pattern(sell_sm_pattern)}] "
        f"({_fmt_3vals(sell_sm_vals)})\n"
        f"{chr(10).join(target_lines)}\n"
        f"  买入时 年化收益≈{_fmt_pct(buy_annual_ret)}  卖出时 年化收益≈{_fmt_pct(sell_annual_ret)}  卖出时 短期年化≈{_fmt_pct(sell_short_annual_ret)}\n"
        f"  数量={sold_amount:.0f}  成本均价≈{avg_cost_before:.4f}  卖出价≈{sell_price:.4f}\n"
        f"  本次估算盈亏: {pnl_abs:,.2f} 元 ({pnl_pct:.2f}%)\n"
        f"  单次往返收益总结: 代码={security}, 名称={name}, 收益={pnl_abs:,.2f}元, 收益率={pnl_pct:.2f}%, "
        f"原因={exit_reason}, 买入状态={entry.get('buy_regime', '—')}, 卖出状态={rec['sell_regime']}, "
        f"买入长/短动量={_fmt_m(bl)}/{_fmt_m(bs)}, 卖出长/短动量={_fmt_m(sl)}/{_fmt_m(ss)}\n"
        f"{'=' * 72}"
    )


def log_trade_roundtrip_leaderboard(context, top_n=20):
    """单次买卖往返盈亏榜：盈利前N / 亏损前N（按估算 pnl_abs）。"""
    hist = getattr(g, 'trade_roundtrip_history', []) or []
    if not hist:
        log.info("【往返盈亏看板】尚无已完成清仓记录")
        return
    valid = [h for h in hist if h.get('pnl_abs') is not None and np.isfinite(h.get('pnl_abs', float('nan')))]
    if not valid:
        log.info("【往返盈亏看板】无有效盈亏样本")
        return
    gainers = sorted(valid, key=lambda x: x['pnl_abs'], reverse=True)[:top_n]
    losers = sorted(valid, key=lambda x: x['pnl_abs'])[:top_n]
    lines = []
    lines.append("")
    lines.append("=" * 80)
    lines.append(f"【往返盈亏看板】单次买卖一轮（共 {len(hist)} 笔），估算盈利/亏损各前 {top_n} 名")
    lines.append("-" * 80)
    lines.append(f"{'排名':<4} {'标的':<22} {'买入时间':<20} {'卖出时间':<20} {'盈亏(元)':>12} {'收益率%':>10}")
    lines.append("-" * 80)
    for i, h in enumerate(gainers, 1):
        nm = (h.get('name') or '')[:10]
        lines.append(
            f"{i:<4} {nm:<12} {str(h.get('code','')):<10} "
            f"{str(h.get('buy_datetime','')):<20} {str(h.get('sell_datetime','')):<20} "
            f"{h.get('pnl_abs', 0):>12,.2f} {h.get('pnl_pct', 0):>10.2f}"
        )
    lines.append("-" * 80)
    lines.append(f"{'排名':<4} {'标的':<22} {'买入时间':<20} {'卖出时间':<20} {'盈亏(元)':>12} {'收益率%':>10}")
    lines.append("-" * 80)
    for i, h in enumerate(losers, 1):
        nm = (h.get('name') or '')[:10]
        lines.append(
            f"{i:<4} {nm:<12} {str(h.get('code','')):<10} "
            f"{str(h.get('buy_datetime','')):<20} {str(h.get('sell_datetime','')):<20} "
            f"{h.get('pnl_abs', 0):>12,.2f} {h.get('pnl_pct', 0):>10.2f}"
        )
    lines.append("=" * 80)
    lines.append("")
    log.info("\n".join(lines))


def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    try:
        current_price = _coerce_scalar_price(current_price)
        if current_price is None or current_price <= 0:
            return None
        price_series = np.append(hist_closes, current_price)
        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        need_len = max(g.lookback_days, short_lb)
        if len(price_series) < need_len * 0.8:
            return None
        smoothed_used = False
        price_for_momentum = price_series
        if _use_smoothed_momentum_prices():
            w = max(1, int(getattr(g, 'smoothed_ma_window', 5)))
            price_for_momentum = pd.Series(price_series).rolling(window=w, min_periods=1).mean().values
            smoothed_used = True
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_for_momentum, g.lookback_days)
        if momentum_score is None:
            return None
        short_momentum_score, _, _ = calculate_momentum_score(price_for_momentum, short_lb)
        effective_r2_threshold = _effective_r2_threshold_whipsaw()
        passed_r2 = r_squared > effective_r2_threshold

        effective_min_score = float(getattr(g, 'min_score_threshold', 0))
        effective_max_score = float(getattr(g, 'max_score_threshold', 5))
        effective_short_min = float(getattr(g, 'short_momentum_min_score', 0))
        effective_short_max = float(getattr(g, 'short_momentum_max_score', 6))
        if _use_range_long_momentum_limits():
            r_lo = float(getattr(g, 'range_momentum_min', 0))
            r_hi = float(getattr(g, 'range_momentum_max', effective_max_score))
            effective_min_score = max(effective_min_score, r_lo)
            effective_max_score = min(effective_max_score, r_hi)
        if _use_range_short_momentum_limits():
            rs_lo = float(getattr(g, 'range_short_momentum_min', 0))
            rs_hi = float(getattr(g, 'range_short_momentum_max', effective_short_max))
            effective_short_min = max(effective_short_min, rs_lo)
            effective_short_max = min(effective_short_max, rs_hi)
        momentum_rank_score = momentum_score
        momentum_soft_capped = False
        soft_cap_enabled = bool(getattr(g, 'enable_momentum_soft_cap', False))
        soft_cap_normal_only = bool(getattr(g, 'momentum_soft_cap_normal_only', True))
        regime = getattr(g, 'market_regime', '震荡期')
        apply_soft_cap = soft_cap_enabled and ((not soft_cap_normal_only) or regime == '正常期')
        if apply_soft_cap and momentum_score > effective_max_score:
            penalty = float(getattr(g, 'momentum_soft_cap_penalty', 0.2))
            penalty = max(0.0, min(1.0, penalty))
            momentum_rank_score = effective_max_score + (momentum_score - effective_max_score) * penalty
            momentum_soft_capped = True
            passed_momentum = (momentum_score >= effective_min_score)
        else:
            passed_momentum = (effective_min_score <= momentum_score <= effective_max_score)
        passed_short_momentum = (
            effective_short_min <= short_momentum_score <= effective_short_max
            if short_momentum_score is not None else False)
        if _use_range_short_momentum_limits():
            passed_whipsaw_short_band = passed_short_momentum
        else:
            passed_whipsaw_short_band = True
        dual_pos_active = _dual_positive_filter_should_apply()
        passed_dual_positive = (
            (momentum_score > 0 and short_momentum_score > 0)
            if short_momentum_score is not None else False)

        volume_ratio = get_volume_ratio(hist_volumes, today_vol, context, g.volume_lookback)
        effective_volume_threshold = float(getattr(g, 'volume_threshold', 0))
        if getattr(g, 'enable_volume_threshold_buffer', False):
            _vbuf = float(getattr(g, 'volume_threshold_buffer', 0.0))
            effective_volume_threshold += max(0.0, _vbuf)
        passed_volume = (volume_ratio is not None and volume_ratio < effective_volume_threshold)
        
        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            effective_loss_threshold = float(getattr(g, 'loss', 0.97))
            if min(day_ratios) < effective_loss_threshold:
                passed_loss_filter = False
        
        passed_ma = True
        ma_value = None
        if len(price_series) >= g.ma_lookback:
            ma_value = np.mean(price_series[-g.ma_lookback:])
            passed_ma = current_price > ma_value * g.ma_threshold
        else:
            passed_ma = False
        
        premium_rate, passed_premium = calculate_premium_rate(etf, context)
        
        laplace_value = 0
        laplace_slope = 0
        passed_laplace = False
        effective_laplace_s = _effective_laplace_s()
        gaussian_value = 0.0
        gaussian_slope = 0.0
        passed_gaussian = False
        if len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=effective_laplace_s)
                if len(laplace_values) >= 2:
                    laplace_value = laplace_values[-1]
                    laplace_slope = laplace_values[-1] - laplace_values[-2]
                    laplace_min_slope = _effective_laplace_min_slope()
                    passed_laplace = (current_price > laplace_values[-1] and laplace_slope > laplace_min_slope)
                g1, g2 = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
                gaussian_value = g1
                if getattr(g, 'gaussian_use_relative_slope', False):
                    gaussian_slope = ((g1 - g2) / g2) if abs(g2) > 1e-12 else 0.0
                    _g_min = float(getattr(g, 'gaussian_min_slope_relative', 0.001))
                else:
                    gaussian_slope = g1 - g2
                    _g_min = g.gaussian_min_slope
                passed_gaussian = (current_price > g1 and gaussian_slope > _g_min)
            except Exception:
                pass
        
        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'momentum_rank_score': momentum_rank_score,
            'momentum_soft_capped': momentum_soft_capped,
            'short_momentum_score': short_momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'effective_r2_threshold': effective_r2_threshold,
            'effective_min_score_threshold': effective_min_score,
            'effective_max_score_threshold': effective_max_score,
            'effective_short_min_score_threshold': effective_short_min,
            'effective_short_max_score_threshold': effective_short_max,
            'passed_whipsaw_short_band': passed_whipsaw_short_band,
            'smoothed_momentum_used': smoothed_used,
            'passed_dual_positive': passed_dual_positive,
            'dual_positive_filter_active': dual_pos_active,
            'passed_short_momentum': passed_short_momentum,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'effective_volume_threshold': effective_volume_threshold,
            'day_ratios': day_ratios,
            'effective_loss_threshold': effective_loss_threshold if len(day_ratios) > 0 else float(getattr(g, 'loss', 0.97)),
            'premium_rate': premium_rate,
            'passed_momentum': passed_momentum,
            'passed_r2': passed_r2,
            'passed_ma': passed_ma,
            'passed_volume': passed_volume,
            'passed_loss': passed_loss_filter,
            'passed_premium': passed_premium,
            'ma_value': ma_value,
            'laplace_value': laplace_value,
            'laplace_slope': laplace_slope,
            'effective_laplace_s': effective_laplace_s,
            'passed_laplace': passed_laplace,
            'gaussian_value': gaussian_value,
            'gaussian_slope': gaussian_slope,
            'passed_gaussian': passed_gaussian,
        }
    except Exception as e:
        log.debug(f"【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None


def get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
    if lookback_days is None:
        lookback_days = g.volume_lookback
    try:
        if hist_volumes is None or len(hist_volumes) < lookback_days:
            return None
        past_n_days_vol = hist_volumes[-lookback_days:]
        if np.any(np.isnan(past_n_days_vol)) or np.any(past_n_days_vol == 0):
            return None
        avg_volume = np.mean(past_n_days_vol)
        if avg_volume == 0:
            return None
        now = context.current_dt
        elapsed_minutes = (now.hour - 9) * 60 + now.minute - 30
        if now.hour >= 13:
            elapsed_minutes -= 90
        elapsed_minutes = max(1, min(elapsed_minutes, 240))
        projected_today_vol = today_vol * (240.0 / elapsed_minutes)
        return projected_today_vol / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None


def calculate_premium_rate(etf, context):
    try:
        etf_price = getattr(g, 'etf_yesterday_close_batch', {}).get(etf)
        if etf_price is None or pd.isna(etf_price):
            etf_price_df = get_price(etf, start_date=context.previous_date, end_date=context.previous_date, fields=['close'])
            if etf_price_df is None or len(etf_price_df) == 0:
                return None, False
            etf_price = etf_price_df['close'].iloc[-1]
        nav = getattr(g, 'etf_yesterday_nav_batch', {}).get(etf)
        if nav is None or pd.isna(nav):
            nav_df = get_extras('unit_net_value', etf, start_date=context.previous_date, end_date=context.previous_date)
            if nav_df is None or len(nav_df) == 0:
                return None, False
            nav = nav_df.iloc[-1].values[0]
        if nav <= 0 or pd.isna(nav):
            return None, False
        premium_rate = (etf_price - nav) / nav * 100
        passed_premium = premium_rate <= g.max_premium_rate
        return premium_rate, passed_premium
    except Exception as e:
        return None, True


def laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def gaussian_filter_last_two(price, sigma=1.2):
    """震荡期高斯滤波末两点（对齐五福35）"""
    n = len(price)
    if n < 2:
        return 0.0, 0.0
    idx_1 = np.arange(n)
    weights_1 = np.exp(-((idx_1 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    weights_1 /= np.sum(weights_1)
    g1 = np.sum(price * weights_1)
    price_2 = price[:-1]
    idx_2 = np.arange(n - 1)
    weights_2 = np.exp(-((idx_2 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    weights_2 /= np.sum(weights_2)
    g2 = np.sum(price_2 * weights_2)
    return g1, g2


def resolve_market_regime(context):
    """三态判定（六指数）：①below_ma20 计数≥weak_min→走弱；②否则 above_ma10≥normal_min→正常；③其余→震荡。
    生效状态切换：指标与生效不一致时，需连续 regime_switch_confirm_days 个交易日指标口径一致才切换。"""
    # 中证2000 官方为 932000；聚宽 convert_security 报「找不到标的」，故第六条改用国证2000 399303.XSHE（小盘广度近似）。
    indexes = {
        '沪深300': '000300.XSHG',
        '深证综指(399101)': '399101.XSHE',
        '创业板': '399006.XSHE',
        '中证A500': '000510.XSHG',
        '中证1000': '000852.XSHG',
        '国证2000(代中证2000)': '399303.XSHE',
    }
    n_index = len(indexes)
    bars_need = max(g.regime_ma20_lookback, g.normal_ma_lookback) + 1
    below_ma20 = 0
    above_ma10 = 0
    n_ok = 0
    log_details = bool(getattr(g, 'log_market_status_details', False))
    for name, code in indexes.items():
        df = attribute_history(code, bars_need, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < g.regime_ma20_lookback:
            if log_details:
                log.warning(f"📊 【市场状态】{name}({code})数据不足，跳过")
            continue
        cur = df['close'][-1]
        ma10 = df['close'][-g.normal_ma_lookback:].mean()
        ma20 = df['close'][-g.regime_ma20_lookback:].mean()
        if cur < ma20:
            below_ma20 += 1
        if cur > ma10:
            above_ma10 += 1
        n_ok += 1
        st_m10 = "⬆️" if cur > ma10 else ("⬇️" if cur < ma10 else "➡️")
        st_m20 = "⬇️" if cur < ma20 else ("⬆️" if cur > ma20 else "➡️")
        if log_details:
            log.info(
                f"📊 【市场状态】{name}({code}): 收盘{cur:.2f} / MA{g.normal_ma_lookback}={ma10:.2f}{st_m10} "
                f"/ MA{g.regime_ma20_lookback}={ma20:.2f}{st_m20}"
            )
    weak_min = int(getattr(g, 'regime_weak_below_ma20_min', 6))
    normal_min = int(getattr(g, 'regime_normal_above_ma10_min', 3))
    if n_ok < n_index:
        raw_regime = '震荡期'
        if log_details:
            log.warning(f"📊 【市场状态】六指数未齐({n_ok}/{n_index})，指标口径默认震荡期")
    elif below_ma20 >= weak_min:
        raw_regime = '走弱期'
    elif above_ma10 >= normal_min:
        raw_regime = '正常期'
    else:
        raw_regime = '震荡期'

    today = context.current_dt.date()
    effective_before = getattr(g, 'market_regime', '震荡期')
    last_change = getattr(g, 'regime_last_change_date', None)
    n_need = int(getattr(g, 'regime_switch_confirm_days', 2))
    if n_need < 1:
        n_need = 1

    log.info(
        f"📊 【市场状态·指标】below_ma20={below_ma20}/{n_ok} (走弱阈值≥{weak_min}), "
        f"above_ma10={above_ma10}/{n_ok} (正常阈值≥{normal_min}) → 【{raw_regime}】"
    )

    if last_change is None:
        g.market_regime = raw_regime
        g.regime_last_change_date = today
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
        log.info(f"📌 【状态切换】回测首日/首次：生效【{g.market_regime}】")
    elif raw_regime == effective_before:
        g.market_regime = raw_regime
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
    elif n_need <= 1:
        g.market_regime = raw_regime
        g.regime_last_change_date = today
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
        log.info(f"✅ 【状态切换】确认天数=1，指标切换立即生效 【{effective_before}】→【{raw_regime}】")
    else:
        pending = getattr(g, 'regime_switch_pending_raw', None)
        streak = int(getattr(g, 'regime_switch_pending_streak', 0))
        if pending == raw_regime:
            streak += 1
            g.regime_switch_pending_streak = streak
            g.regime_switch_pending_raw = raw_regime
        else:
            streak = 1
            g.regime_switch_pending_streak = 1
            g.regime_switch_pending_raw = raw_regime
            log.info(
                f"🔔 【状态切换·待确认】指标【{raw_regime}】≠ 生效【{effective_before}】，"
                f"已连续 1/{n_need} 个交易日为该指标（需连续{n_need}日一致才切换）"
            )
        if streak >= n_need:
            g.market_regime = raw_regime
            g.regime_last_change_date = today
            g.regime_switch_pending_raw = None
            g.regime_switch_pending_streak = 0
            log.info(
                f"✅ 【状态切换·已确认】指标连续{streak}个交易日为【{raw_regime}】，"
                f"生效切换 【{effective_before}】→【{raw_regime}】"
            )
        else:
            g.market_regime = effective_before
            log.info(
                f"⏳ 【状态切换·待确认】指标【{raw_regime}】，生效仍为【{effective_before}】"
                f"（进度 {streak}/{n_need} 个交易日）"
            )

    log.info(f"📊 【市场状态·生效】→ 【{g.market_regime}】")
    record(
        正常期标记=1 if g.market_regime == '正常期' else 0,
        震荡期标记=1 if g.market_regime == '震荡期' else 0,
        走弱期标记=1 if g.market_regime == '走弱期' else 0,
    )
    log_regime_transition_chain(context)
    return g.market_regime


def log_regime_transition_chain(context):
    """打印相邻交易日状态切换；检测「隔日跳回」如 正常→震荡→正常。"""
    new = g.market_regime
    day_str = context.current_dt.strftime('%Y-%m-%d')
    prev = getattr(g, 'regime_prev_day', None)
    prev2 = getattr(g, 'regime_prev_prev_day', None)

    if prev is not None and prev2 is not None:
        if new == prev2 and new != prev:
            if not hasattr(g, 'regime_flip_flop_count'):
                g.regime_flip_flop_count = 0
            g.regime_flip_flop_count = int(g.regime_flip_flop_count) + 1
            n = g.regime_flip_flop_count
            log.info(
                f"🔀 【状态反复·隔日跳回】第{n}次（回测累计）{day_str}: {prev2} → {prev} → {new} "
                f"（首尾同为【{new}】，中间为【{prev}】）"
            )

    if prev is not None:
        if new != prev:
            log.info(f"🔁 【状态切换】{day_str}: {prev} → {new}")
        else:
            log.info(f"⏺ 【状态延续】{day_str}: 连续【{new}】")
    else:
        log.info(f"📌 【状态首日】{day_str}: 【{new}】")

    g.regime_prev_prev_day = prev
    g.regime_prev_day = new


REGIME_LABELS = ('正常期', '震荡期', '走弱期')


def _ensure_regime_stats_structures():
    """聚宽 g 上部分字段可能非原生 dict，统一为可数字累加的结构。"""
    if not isinstance(getattr(g, 'regime_day_counts', None), dict):
        g.regime_day_counts = {k: 0 for k in REGIME_LABELS}
    else:
        for k in REGIME_LABELS:
            g.regime_day_counts.setdefault(k, 0)
    if not isinstance(getattr(g, 'regime_return_factors', None), dict):
        g.regime_return_factors = {k: 1.0 for k in REGIME_LABELS}
    else:
        for k in REGIME_LABELS:
            g.regime_return_factors.setdefault(k, 1.0)
    for attr, default in (
        ('regime_win_counts', 0),
        ('regime_loss_counts', 0),
        ('regime_flat_counts', 0),
    ):
        if not isinstance(getattr(g, attr, None), dict):
            setattr(g, attr, {k: default for k in REGIME_LABELS})
        else:
            for k in REGIME_LABELS:
                getattr(g, attr).setdefault(k, default)
    for attr in ('regime_sum_pos_daily_ret', 'regime_sum_neg_daily_ret'):
        if not isinstance(getattr(g, attr, None), dict):
            setattr(g, attr, {k: 0.0 for k in REGIME_LABELS})
        else:
            for k in REGIME_LABELS:
                getattr(g, attr).setdefault(k, 0.0)


def update_regime_performance_stats(context):
    """收盘统计：本交易日归属早盘判定的市场状态，累计天数与净值复利因子。"""
    _ensure_regime_stats_structures()
    reg = getattr(g, 'market_regime', '震荡期')
    if reg not in g.regime_day_counts:
        reg = '震荡期'
    g.regime_day_counts[reg] = int(g.regime_day_counts.get(reg, 0)) + 1
    v = context.portfolio.total_value
    prev = getattr(g, 'prev_eod_portfolio_value', None)
    if prev is not None and prev > 0:
        daily_ret = (v - prev) / prev
        g.regime_return_factors[reg] = g.regime_return_factors.get(reg, 1.0) * (1.0 + daily_ret)
        if daily_ret > 0:
            g.regime_win_counts[reg] = int(g.regime_win_counts.get(reg, 0)) + 1
            g.regime_sum_pos_daily_ret[reg] = float(g.regime_sum_pos_daily_ret.get(reg, 0.0)) + daily_ret
        elif daily_ret < 0:
            g.regime_loss_counts[reg] = int(g.regime_loss_counts.get(reg, 0)) + 1
            g.regime_sum_neg_daily_ret[reg] = float(g.regime_sum_neg_daily_ret.get(reg, 0.0)) + daily_ret
        else:
            g.regime_flat_counts[reg] = int(g.regime_flat_counts.get(reg, 0)) + 1
    g.prev_eod_portfolio_value = v


def log_regime_performance_dashboard(context, full=False):
    """累计天数、复利收益、各状态日收益胜负统计与胜率（日收益仅统计有上日净值可比时）。"""
    _ensure_regime_stats_structures()
    lines = []
    total_days = sum(int(g.regime_day_counts.get(k, 0)) for k in REGIME_LABELS)
    lines.append("")
    lines.append("=" * 80)
    lines.append("【市场状态累计看板】累计交易日与各状态下策略净值复利（自回测起）")
    lines.append("=" * 80)
    lines.append(f"{'状态':<10} {'累计天数':>10} {'占比':>10} {'复利因子':>14} {'累计收益率':>14}")
    lines.append("-" * 80)
    for label in REGIME_LABELS:
        cnt = int(g.regime_day_counts.get(label, 0))
        fac = g.regime_return_factors.get(label, 1.0)
        pct = (cnt / total_days * 100) if total_days else 0.0
        cum_r = (fac - 1.0) * 100
        lines.append(f"{label:<10} {cnt:>10} {pct:>9.2f}% {fac:>14.6f} {cum_r:>13.2f}%")
    lines.append("=" * 80)
    lines.append("【日收益胜负明细】仅统计「当日相对昨日收盘净值」可比的交易日（不含回测首日）")
    lines.append(
        f"{'状态':<8} {'赢(+)':>8} {'输(-)':>8} {'平(0)':>8} "
        f"{'胜率①':>10} {'胜率②':>10} {'正日收益累加':>14} {'负日收益累加':>14}"
    )
    lines.append("-" * 80)
    lines.append("① 胜率=赢/(赢+输)  ② 胜率=赢/(赢+输+平)")
    lines.append("-" * 80)
    for label in REGIME_LABELS:
        w = int(g.regime_win_counts.get(label, 0))
        el = int(g.regime_loss_counts.get(label, 0))
        z = int(g.regime_flat_counts.get(label, 0))
        wl = w + el
        wlf = w + el + z
        rate1 = (100.0 * w / wl) if wl else float('nan')
        rate2 = (100.0 * w / wlf) if wlf else float('nan')
        sp = float(g.regime_sum_pos_daily_ret.get(label, 0.0)) * 100
        sn = float(g.regime_sum_neg_daily_ret.get(label, 0.0)) * 100
        r1s = f"{rate1:.2f}%" if wl else "  —  "
        r2s = f"{rate2:.2f}%" if wlf else "  —  "
        lines.append(
            f"{label:<8} {w:>8} {el:>8} {z:>8} {r1s:>10} {r2s:>10} {sp:>13.2f}% {sn:>13.2f}%"
        )
    flip_n = int(getattr(g, 'regime_flip_flop_count', 0))
    lines.append("-" * 80)
    lines.append(
        f"【状态切换】隔日跳回(A→B→A，首尾状态相同、中间不同) 累计次数: {flip_n}"
    )
    lines.append("=" * 80)
    lines.append(f"总交易日(状态归因): {total_days}  |  当前净值: {context.portfolio.total_value:,.2f}")
    lines.append("")
    text = "\n".join(lines)
    if full:
        log.info(text)
    else:
        parts = []
        for label in REGIME_LABELS:
            fac = g.regime_return_factors.get(label, 1.0)
            cn = int(g.regime_day_counts.get(label, 0))
            w = int(g.regime_win_counts.get(label, 0))
            el = int(g.regime_loss_counts.get(label, 0))
            zc = int(g.regime_flat_counts.get(label, 0))
            wl = w + el
            rate1 = (100.0 * w / wl) if wl else 0.0
            sp = float(g.regime_sum_pos_daily_ret.get(label, 0.0)) * 100
            sn = float(g.regime_sum_neg_daily_ret.get(label, 0.0)) * 100
            short = f"{label}(含{cn}天 复利{(fac-1)*100:.2f}% 胜{rate1:.0f}% {w}+/{el}-/{zc}0 正累{sp:.2f}% 负累{sn:.2f}%)"
            parts.append(short)
        flip_n = int(getattr(g, 'regime_flip_flop_count', 0))
        log.info("📈 【状态看板】" + " | ".join(parts) + f" || 隔日跳回累计{flip_n}次")


def apply_filters(metrics_list, return_all=False):
    regime = getattr(g, 'market_regime', '震荡期')
    is_weak = regime == '走弱期'
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter and (not is_weak or getattr(g, 'weak_apply_r2_filter', False))),
        ('均线', lambda m: m['passed_ma'], g.enable_ma_filter and is_weak and getattr(g, 'weak_apply_ma_filter', False)),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check and (not is_weak or getattr(g, 'weak_apply_volume_filter', False))),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter and (not is_weak or getattr(g, 'weak_apply_loss_filter', False))),
        ('溢价率', lambda m: m['passed_premium'], g.enable_premium_filter and (not is_weak or getattr(g, 'weak_apply_premium_filter', False))),
        ('拉普拉斯滤波', lambda m: m['passed_laplace'], g.enable_laplace_filter and (regime == '正常期' or (is_weak and getattr(g, 'weak_apply_laplace_filter', False)))),
        ('高斯滤波', lambda m: m['passed_gaussian'], regime == '震荡期'),
        ('震荡期短期动量区间(Whipsaw)', lambda m: m.get('passed_whipsaw_short_band', True), True),
        ('长短动量双正(Whipsaw)', lambda m: (not m.get('dual_positive_filter_active', False)) or m.get('passed_dual_positive', False), True),
    ]
    if return_all:
        for m in metrics_list:
            failed = [name for name, condition, is_enabled in steps if is_enabled and not condition(m)]
            m['filter_failed_steps'] = failed
            m['passed_all_filters'] = len(failed) == 0
        return metrics_list
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered


def _fmt_corr_pool_status(m):
    """第二步一览：修正相关性相对固定池展示。"""
    if not getattr(g, 'enable_corr_overview', True):
        return ''
    mx = m.get('max_corr_vs_fixed')
    if mx is None:
        note = m.get('corr_pool_note', '固定池/无数据')
        return f"修正相关性(池): {note} ✅"
    th = float(getattr(g, 'corr_pool_threshold', 0.5))
    passed = bool(m.get('passed_corr_pool', True))
    active = bool(getattr(g, 'enable_corr_pool_filter', False))
    tag = '✅' if passed else '❌'
    extra = '(入池筛开)' if active and not passed else ('(入池筛关·仅展示)' if not active else '')
    return f"修正相关性(池): max P_adj={mx:.4f} vs<{th:.2f} {tag} {extra}"


def explain_filter_failures_for_etf(etf_code, metrics=None):
    """返回该ETF在当日过滤步骤中未通过的真实原因（含阈值与数值）。"""
    try:
        m = metrics or getattr(g, 'last_metrics_by_etf_code', {}).get(etf_code)
        if not isinstance(m, dict):
            return "无指标记录"
        regime = getattr(g, 'market_regime', '震荡期')
        reasons = []

        # 1) 动量得分区间
        if not m.get('passed_momentum', True):
            sc = m.get('momentum_score')
            lo = m.get('effective_min_score_threshold')
            hi = m.get('effective_max_score_threshold')
            reasons.append(f"动量得分不在区间[{lo:.4f},{hi:.4f}] (score={sc:.4f})" if sc is not None else "动量得分不达标")

        # 2) R² 过滤（走弱期须 weak_apply_r2_filter，与 v3-1「走弱不做 R²」对齐时可置 False）
        if getattr(g, 'enable_r2_filter', False) and (
            regime != '走弱期' or getattr(g, 'weak_apply_r2_filter', False)
        ):
            if not m.get('passed_r2', True):
                r2 = m.get('r_squared')
                th = m.get('effective_r2_threshold', getattr(g, 'r2_threshold', None))
                if r2 is None or (isinstance(r2, float) and (np.isnan(r2) or np.isinf(r2))):
                    reasons.append("R²无效/缺失")
                else:
                    reasons.append(f"R²不足 (r2={float(r2):.3f} ≤ 阈值{float(th):.3f})" if th is not None else f"R²不足 (r2={float(r2):.3f})")

        # 3) 走弱期均线过滤（须 weak_apply_ma_filter）
        if (
            getattr(g, 'enable_ma_filter', False)
            and regime == '走弱期'
            and getattr(g, 'weak_apply_ma_filter', False)
        ):
            if not m.get('passed_ma', True):
                px = m.get('current_price')
                ma = m.get('ma_value')
                th = float(getattr(g, 'ma_threshold', 1.0))
                if px is not None and ma is not None:
                    reasons.append(f"均线过滤未过 (现价{px:.3f} ≤ MA×{th:.2f}={ma*th:.3f})")
                else:
                    reasons.append("均线过滤未过")

        # 4) 成交量过滤（走弱期须 weak_apply_volume_filter）
        if getattr(g, 'enable_volume_check', False) and (
            regime != '走弱期' or getattr(g, 'weak_apply_volume_filter', False)
        ):
            if not m.get('passed_volume', True):
                vr = m.get('volume_ratio')
                thr = float(m.get('effective_volume_threshold', getattr(g, 'volume_threshold', 0)))
                if vr is None:
                    reasons.append("成交量比值缺失/不可算")
                else:
                    reasons.append(f"成交量比值未过 (量比{float(vr):.2f} ≥ 阈值{thr:.2f}，需<{thr:.2f})")

        # 5) 短期风控（走弱期须 weak_apply_loss_filter）
        if getattr(g, 'enable_loss_filter', False) and (
            regime != '走弱期' or getattr(g, 'weak_apply_loss_filter', False)
        ):
            if not m.get('passed_loss', True):
                ratios = m.get('day_ratios') or []
                min_ratio = min(ratios) if ratios else None
                loss_th = float(getattr(g, 'loss', 0))
                if min_ratio is not None:
                    reasons.append(f"短期风控未过 (近3日最差日涨跌比{float(min_ratio):.4f} < 阈值{loss_th:.4f})")
                else:
                    reasons.append("短期风控未过")

        # 6) 溢价率过滤（走弱期须 weak_apply_premium_filter）
        if getattr(g, 'enable_premium_filter', False) and (
            regime != '走弱期' or getattr(g, 'weak_apply_premium_filter', False)
        ):
            if not m.get('passed_premium', True):
                pr = m.get('premium_rate')
                max_pr = float(getattr(g, 'max_premium_rate', 0))
                if pr is None:
                    reasons.append("溢价率缺失/不可算")
                else:
                    reasons.append(f"溢价率超阈值 (溢价{float(pr):.2f}% > {max_pr:.2f}%)")

        # 7) 拉普拉斯（正常期；走弱期仅当 weak_apply_laplace_filter）
        if getattr(g, 'enable_laplace_filter', False) and (
            regime == '正常期'
            or (regime == '走弱期' and getattr(g, 'weak_apply_laplace_filter', False))
        ):
            if not m.get('passed_laplace', True):
                slope = m.get('laplace_slope')
                min_s = _effective_laplace_min_slope()
                es = m.get('effective_laplace_s')
                if slope is not None:
                    suf = f", s={float(es):.4f}" if es is not None else ""
                    reasons.append(f"拉普拉斯滤波未过{suf} (斜率{slope:.4f} ≤ 最小{min_s:.4f} 或 现价≤滤波值)")
                else:
                    reasons.append("拉普拉斯滤波未过")

        # 8) 震荡期高斯
        if regime == '震荡期':
            if not m.get('passed_gaussian', True):
                slope = m.get('gaussian_slope')
                if getattr(g, 'gaussian_use_relative_slope', False):
                    min_s = float(getattr(g, 'gaussian_min_slope_relative', 0.001))
                else:
                    min_s = float(getattr(g, 'gaussian_min_slope', 0))
                if slope is not None:
                    reasons.append(f"高斯滤波未过 (斜率{slope:.4f} ≤ 最小{min_s:.4f} 或 现价≤滤波值)")
                else:
                    reasons.append("高斯滤波未过")

        # 9) 震荡期短动量区间（如启用）
        if not m.get('passed_whipsaw_short_band', True):
            sms = m.get('short_momentum_score')
            lo = m.get('effective_short_min_score_threshold')
            hi = m.get('effective_short_max_score_threshold')
            if sms is not None and lo is not None and hi is not None:
                reasons.append(f"短期动量不在区间[{lo:.4f},{hi:.4f}] (short={sms:.4f})")
            else:
                reasons.append("短期动量区间未过")

        # 10) 长短动量双正（如启用）
        if m.get('dual_positive_filter_active', False) and (not m.get('passed_dual_positive', True)):
            lm = m.get('momentum_score')
            sm = m.get('short_momentum_score')
            reasons.append(f"长短动量双正未过 (长={lm:.4f} 短={sm:.4f} 需均>0)" if lm is not None and sm is not None else "长短动量双正未过")

        return "；".join(reasons) if reasons else "通过全部过滤条件"
    except Exception:
        return "过滤原因解析失败"


def _ensure_exit_reason_stats():
    """确保卖出原因统计结构可用（兼容旧缓存字段）。"""
    if not isinstance(getattr(g, 'exit_reason_stats', None), dict):
        g.exit_reason_stats = {}
    s = g.exit_reason_stats
    s.setdefault('total', 0)
    if not isinstance(s.get('by_bucket'), dict):
        s['by_bucket'] = {}
    for k in ('missing_data', 'filter_fail', 'rank_lag', 'other'):
        s['by_bucket'].setdefault(k, 0)
    if not isinstance(s.get('by_regime'), dict):
        s['by_regime'] = {}
    if not isinstance(s.get('by_detail'), dict):
        s['by_detail'] = {}


def _record_exit_reason_stat(bucket, detail, regime):
    _ensure_exit_reason_stats()
    s = g.exit_reason_stats
    b = bucket if bucket in ('missing_data', 'filter_fail', 'rank_lag', 'other') else 'other'
    r = regime if regime in ('正常期', '震荡期', '走弱期') else '未知'
    d = detail if detail else '未细分'
    s['total'] = int(s.get('total', 0)) + 1
    s['by_bucket'][b] = int(s['by_bucket'].get(b, 0)) + 1
    by_r = s['by_regime'].setdefault(
        r, {'missing_data': 0, 'filter_fail': 0, 'rank_lag': 0, 'other': 0, 'total': 0}
    )
    by_r[b] = int(by_r.get(b, 0)) + 1
    by_r['total'] = int(by_r.get('total', 0)) + 1
    s['by_detail'][d] = int(s['by_detail'].get(d, 0)) + 1


def log_exit_reason_dashboard(context, top_n=8):
    """收盘打印卖出原因分类看板（累计口径）。"""
    _ensure_exit_reason_stats()
    s = g.exit_reason_stats
    total = int(s.get('total', 0))
    if total <= 0:
        return
    by_bucket = s.get('by_bucket', {})
    m = int(by_bucket.get('missing_data', 0))
    f = int(by_bucket.get('filter_fail', 0))
    r = int(by_bucket.get('rank_lag', 0))
    o = int(by_bucket.get('other', 0))
    log.info(
        f"🧾 【卖出原因分类看板】累计{total}笔 | "
        f"数据缺失={m}({(100.0*m/total):.1f}%) | "
        f"过滤失败={f}({(100.0*f/total):.1f}%) | "
        f"排名落后={r}({(100.0*r/total):.1f}%) | "
        f"其他={o}({(100.0*o/total):.1f}%)"
    )
    by_regime = s.get('by_regime', {})
    regime_parts = []
    for reg in ('正常期', '震荡期', '走弱期', '未知'):
        item = by_regime.get(reg)
        if not item:
            continue
        rt = int(item.get('total', 0))
        if rt <= 0:
            continue
        regime_parts.append(
            f"{reg}(总{rt} 缺{item.get('missing_data',0)} 过{item.get('filter_fail',0)} 排{item.get('rank_lag',0)} 其{item.get('other',0)})"
        )
    if regime_parts:
        log.info("🧾 【卖出原因·分状态】" + " | ".join(regime_parts))
    by_detail = s.get('by_detail', {})
    if isinstance(by_detail, dict) and by_detail:
        top = sorted(by_detail.items(), key=lambda kv: kv[1], reverse=True)[:max(1, int(top_n))]
        top_parts = [f"{k}:{v}" for k, v in top]
        log.info("🧾 【卖出原因·细分Top】" + "；".join(top_parts))


def _rank_in_filtered_list(filtered_list, etf_code):
    """在 filtered_list 中 1-based 名次，不在则 None。"""
    for i, m in enumerate(filtered_list):
        if m.get('etf') == etf_code:
            return i + 1
    return None


def get_final_ranked_etfs(context):
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = context.previous_date
    log.info(f"【动量得分计算】使用合并池，合计{len(etf_set)}只ETF")
    regime = getattr(g, 'market_regime', '震荡期')
    regime_show = {'正常期': '🟢 正常期', '震荡期': '🟡 震荡期', '走弱期': '🔴 走弱期'}.get(regime, regime)
    log.info(f"【当前状态】{regime_show}")
    short_lb = int(getattr(g, 'short_momentum_lookback', 21))
    lookback = max(g.lookback_days, short_lb, g.volume_lookback, g.ma_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
    safe_lookback = lookback + 20
    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        log.warning("【动量计算】无法获取历史价格数据")
        g.last_metrics_by_etf_code = {}
        return []
    g.etf_yesterday_close_batch = {}
    g.etf_yesterday_nav_batch = {}
    try:
        y_price_df = get_price(etf_set, start_date=end_date, end_date=end_date, fields=['close'], panel=False)
        if y_price_df is not None and not y_price_df.empty:
            g.etf_yesterday_close_batch = y_price_df.groupby('code')['close'].last().to_dict()
        nav_df = get_extras('unit_net_value', etf_set, start_date=end_date, end_date=end_date)
        if nav_df is not None and not nav_df.empty:
            g.etf_yesterday_nav_batch = nav_df.iloc[-1].to_dict()
    except Exception as e:
        log.warning(f"【动量计算】批量获取溢价率数据异常: {e}")
    today_vols = today_vol_df.groupby('code')['volume'].sum() if (today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)
    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')
    for etf in etf_set:
        if current_data[etf].paused:
            continue
        if etf not in close_pivot.columns:
            continue
        raw_closes = close_pivot[etf].values
        raw_volumes = volume_pivot[etf].values
        valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
        hist_closes = raw_closes[valid_mask]
        hist_volumes = raw_volumes[valid_mask]
        hist_closes = hist_closes[-lookback:]
        hist_volumes = hist_volumes[-lookback:]
        if len(hist_closes) < max(g.lookback_days, short_lb):
            continue
        etf_name = get_security_name(etf)
        current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        metrics = calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)
    g.last_metrics_by_etf_code = {m['etf']: m for m in all_metrics}
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
        rscore = item.get('momentum_rank_score', score)
        if pd.isna(rscore) or (isinstance(rscore, float) and np.isnan(rscore)):
            item['momentum_rank_score'] = float('-inf')
    all_metrics.sort(key=lambda x: x.get('momentum_rank_score', float('-inf')), reverse=True)
    log_buffer = []
    if getattr(g, 'log_first_step_ranking', False):
        log_buffer.append("")
        log_buffer.append(">>> 第一步：所有ETF按动量得分从大到小排序 <<<")
        for m in all_metrics[:100]:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
            ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
            if regime == '震荡期':
                filt_extra = f"高斯斜率: {m.get('gaussian_slope', 0):.4f} {fmt_status('', m.get('passed_gaussian', False))}"
                if getattr(g, 'log_whipsaw_filter_detail', True):
                    sms = m.get('short_momentum_score')
                    sms_s = f"{sms:.4f}" if sms is not None and not (isinstance(sms, float) and np.isnan(sms)) else "nan"
                    dp_ok = (not m.get('dual_positive_filter_active')) or m.get('passed_dual_positive', False)
                    filt_extra += f" | Whipsaw短动量:{sms_s} 双正{'✅' if dp_ok else '❌'}"
            elif regime == '正常期':
                filt_extra = f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}"
            elif regime == '走弱期':
                if getattr(g, 'weak_apply_laplace_filter', False):
                    filt_extra = f"拉普拉斯斜率: {m.get('laplace_slope', 0):.4f} {fmt_status('', m.get('passed_laplace', False))}"
                else:
                    filt_extra = "走弱期: 拉普拉斯未参与筛选"
            else:
                filt_extra = ""
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
                f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
                f"{filt_extra}"
            )
            log_buffer.append(line)
    # 仅进行筛选计算，不输出第二步前检查的一览日志。
    if getattr(g, 'enable_corr_overview', True):
        annotate_corr_vs_fixed_pool(all_metrics, context)
    debug_metrics = apply_filters(all_metrics, return_all=True)

    # 真正用于后续排序/候选池的列表仍然是 filtered_list
    filtered_list = [m for m in debug_metrics if m.get('passed_all_filters', False)]
    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    # 记录当日通过过滤的列表（用于卖出时精确判断“是否被过滤掉”）
    try:
        g.today_filtered_codes = [m.get('etf') for m in filtered_list if isinstance(m, dict) and m.get('etf')]
        g.today_filtered_rank_map = {m.get('etf'): (i + 1) for i, m in enumerate(filtered_list) if isinstance(m, dict) and m.get('etf')}
    except Exception:
        g.today_filtered_codes = []
        g.today_filtered_rank_map = {}
    top_10 = filtered_list[:10]
    log_buffer.append("")
    log_buffer.append(">>> 第二步：符合全部过滤条件的ETF按动量得分从大到小排序(前10名) <<<")
    _hold_for_corr = [
        s for s, p in context.portfolio.positions.items() if p.total_amount > 0
    ]
    if _hold_for_corr and top_10 and (
        getattr(g, 'enable_corr_hold_guard', False) or getattr(g, 'enable_corr_overview', True)
    ):
        log_buffer.append(
            f">>> 第二步·过筛Top10 vs 当前持仓 修正相关性 (回看{getattr(g, 'corr_lookback_days', 60)}日) <<<"
        )
        _corr_codes = list(set(_hold_for_corr + [m['etf'] for m in top_10]))
        _adj = get_adj_corr_matrix_cached(context, _corr_codes)
        for h in _hold_for_corr:
            h_nm = get_security_name(h)
            h_m = next((x for x in all_metrics if x.get('etf') == h), None)
            h_mom = h_m.get('momentum_score') if h_m else None
            for m in top_10[:10]:
                pc = get_pair_adjusted_corr(h, m['etf'], _adj)
                pc_s = f"{pc:.4f}" if pc is not None else "N/A"
                guard_hint = ""
                if pc is not None and getattr(g, 'enable_corr_hold_guard', False):
                    c_mom = m.get('momentum_score')
                    block, _, _, _, _ = should_corr_hold_guard_intercept(
                        context, h_mom, pc, candidate_mom=c_mom,
                    )
                    if block:
                        guard_hint = " ⚠️达持仓守卫拦截条件"
                log_buffer.append(
                    f"  P_adj({h_nm},{m['etf_name']})={pc_s}{guard_hint}"
                )
    if top_10:
        for m in top_10:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
            ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
            if regime == '震荡期':
                filt_extra = f"高斯斜率: {m.get('gaussian_slope', 0):.4f} {fmt_status('', m.get('passed_gaussian', False))}"
                if getattr(g, 'log_whipsaw_filter_detail', True):
                    sms = m.get('short_momentum_score')
                    sms_s = f"{sms:.4f}" if sms is not None and not (isinstance(sms, float) and np.isnan(sms)) else "nan"
                    dp_ok = (not m.get('dual_positive_filter_active')) or m.get('passed_dual_positive', False)
                    filt_extra += f" | Whipsaw短动量:{sms_s} 双正{'✅' if dp_ok else '❌'}"
            elif regime == '正常期':
                filt_extra = f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}"
            elif regime == '走弱期':
                if getattr(g, 'weak_apply_laplace_filter', False):
                    filt_extra = f"拉普拉斯斜率: {m.get('laplace_slope', 0):.4f} {fmt_status('', m.get('passed_laplace', False))}"
                else:
                    filt_extra = "走弱期: 拉普拉斯未参与筛选"
            else:
                filt_extra = ""
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
                f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
                f"{filt_extra}"
            )
            log_buffer.append(line)
    else:
        log_buffer.append("（无符合条件的ETF）")
        full_log = "\n".join(log_buffer)
        log.info(full_log)
        g.last_metrics_by_etf_code = {m['etf']: m for m in all_metrics}
        return []
    score_key = 'momentum_rank_score'
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        ratio = g.score_threshold_ratio if regime != '走弱期' else 1.0
        score_threshold = reference_score * ratio
        log_buffer.append("")
        log_buffer.append(
            f">>> 第三步：选取动量得分≥第{g.holdings_num}名({top_10[g.holdings_num - 1]['etf_name']})得分{reference_score:.4f}×{ratio}={score_threshold:.4f}的ETF <<<"
        )
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<")
        candidate_pool = top_10[:]
    # 记录当日候选池（用于卖出时精确判断“掉出候选池”）
    try:
        g.today_candidate_pool_codes = [m.get('etf') for m in candidate_pool if isinstance(m, dict) and m.get('etf')]
        g.today_candidate_score_threshold = score_threshold if 'score_threshold' in locals() else None
        g.today_candidate_reference_score = reference_score if 'reference_score' in locals() else None
        g.today_candidate_ratio = ratio if 'ratio' in locals() else None
    except Exception:
        g.today_candidate_pool_codes = []
        g.today_candidate_score_threshold = None
        g.today_candidate_reference_score = None
        g.today_candidate_ratio = None
    log_buffer.append(f"【候选池】共{len(candidate_pool)}只ETF（按动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")
    log_buffer.append("")
    log_buffer.append(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    log_buffer.append(f"当前持仓ETF：{current_holdings}")
    candidate_dict = {item['etf']: item for item in candidate_pool}

    # 注意：不在此因「非防频换适用状态」清空 streak。否则指数+冷却下常日不适用，streak 永无法累加。
    # streak 仅在防频换分支内：重返第1/换股/出池/无仓/候选池空 时清零；不适用日仅「暂停累加」。

    regime_allows_anti_churn = (
        regime == '正常期'
        or (regime == '震荡期' and getattr(g, 'oscillation_anti_churn_enabled', False))
        or (regime == '走弱期' and getattr(g, 'weak_anti_churn_enabled', False))
    )
    use_regime_anti_churn = (
        regime_allows_anti_churn and g.holdings_num >= 1 and len(candidate_pool) > 0
    )
    if not use_regime_anti_churn:
        _nr = int(getattr(g, 'normal_not_rank1_streak', 0))
        why = []
        if not regime_allows_anti_churn:
            if regime == '震荡期':
                why.append("震荡期防频换关闭(g.oscillation_anti_churn_enabled=False)")
            elif regime == '走弱期':
                why.append("走弱期防频换关闭(g.weak_anti_churn_enabled=False)")
            else:
                why.append(f"状态【{regime}】不适用防频换")
        if g.holdings_num < 1:
            why.append(f"holdings_num={g.holdings_num}")
        if len(candidate_pool) == 0:
            why.append("候选池为空")
        if why:
            log.info(
                f"【防频换】本日不执行: {'; '.join(why)}。streak 保持不重置(当前={_nr})，走原合并逻辑。"
            )
    if use_regime_anti_churn:
        max_days_single = int(getattr(g, 'normal_max_days_not_rank1', 5))
        AC = (
            '【震荡期防频换】'
            if regime == '震荡期'
            else ('【走弱期防频换】' if regime == '走弱期' else '【正常期防频换】')
        )
        rank1_etf = filtered_list[0]['etf']
        rank1_name = filtered_list[0]['etf_name']
        H_for_pick = current_holdings[0] if len(current_holdings) == 1 else (current_holdings[0] if current_holdings else None)
        new_first, _pick_mode = resolve_switch_target(
            context, candidate_pool, H_for_pick, filtered_list, all_metrics, log_buffer,
        )
        if new_first is None:
            new_first = candidate_pool[0] if candidate_pool else None
        pool_codes = set(candidate_dict.keys())
        topk = max(1, int(getattr(g, 'holdings_num', 1)))

        if g.holdings_num > 1:
            # 多持仓模式：候选池内且排名进入TopK则保留；候选池外立即替换；
            # 候选池内但排名未进TopK时，达到max_days再替换，防止频繁抖动。
            if regime == '震荡期':
                max_days = int(getattr(g, 'oscillation_max_days_not_topk', max_days_single))
            else:
                max_days = int(getattr(g, 'normal_max_days_not_topk', max_days_single))
            streaks = dict(getattr(g, 'normal_not_topk_streaks', {}) or {})
            ranked_codes = [item['etf'] for item in filtered_list]
            rank_map = {code: idx + 1 for idx, code in enumerate(ranked_codes)}
            retained = []
            must_replace = []
            watch_replace = []

            # ---- B.4 改进：状态切换日，"掉出候选池/不在过筛排序表" 视为继续持有 ----
            _b4_today = context.current_dt.date()
            _b4_change_day = getattr(g, 'regime_last_change_date', None)
            _b4_active_mh = (
                getattr(g, 'B4_disable_immediate_swap_on_regime_change', False)
                and _b4_change_day == _b4_today
            )

            for h in current_holdings:
                if h not in pool_codes:
                    if _b4_active_mh:
                        _h_metric = next((x for x in all_metrics if x.get('etf') == h), None)
                        if _h_metric is None:
                            _h_metric = (getattr(g, 'last_metrics_by_etf_code', {}) or {}).get(h)
                        if _h_metric is None:
                            _h_metric = {'etf': h, 'etf_name': get_security_name(h)}
                        retained.append(_h_metric)
                        log_buffer.append(
                            f"{AC}🚧 【B.4 状态切换日】{h} 掉出候选池但今日为状态切换日，继续持有"
                        )
                        continue
                    must_replace.append((h, "掉出候选池"))
                    streaks.pop(h, None)
                    continue
                r = rank_map.get(h)
                if r is None:
                    if _b4_active_mh:
                        _h_metric = next((x for x in all_metrics if x.get('etf') == h), None)
                        if _h_metric is None:
                            _h_metric = (getattr(g, 'last_metrics_by_etf_code', {}) or {}).get(h)
                        if _h_metric is None:
                            _h_metric = {'etf': h, 'etf_name': get_security_name(h)}
                        retained.append(_h_metric)
                        log_buffer.append(
                            f"{AC}🚧 【B.4 状态切换日】{h} 不在过筛排序表但今日为状态切换日，继续持有"
                        )
                        continue
                    must_replace.append((h, "不在过筛排序表"))
                    streaks.pop(h, None)
                    continue
                if r <= topk:
                    retained.append(candidate_dict[h])
                    streaks[h] = 0
                else:
                    streaks[h] = int(streaks.get(h, 0)) + 1
                    watch_replace.append((h, r, streaks[h]))

            # 先保留应保留，再按规则把超出TopK且达阈值的持仓替换
            for h, r, s in watch_replace:
                if s >= max_days:
                    must_replace.append((h, f"连续{s}日未进Top{topk}"))
                    streaks.pop(h, None)
                else:
                    retained.append(candidate_dict[h])
                    log_buffer.append(
                        f"{AC}{h} 名次={r} 未进Top{topk} streak={s}/{max_days}，暂继续持有"
                    )

            if must_replace:
                rs = "；".join([f"{h}({reason})" for h, reason in must_replace])
                log_buffer.append(f"{AC}触发替换: {rs}")
                log.info(f"{AC}多持仓替换触发: {rs}")

            target_count = max(1, int(g.holdings_num))
            retained_codes = {item['etf'] for item in retained}
            fill_pool = [item for item in candidate_pool if item['etf'] not in retained_codes]
            final_result = retained + fill_pool[:max(0, target_count - len(retained))]
            final_result = final_result[:target_count]

            for item in final_result:
                streaks.setdefault(item['etf'], 0)

            # 清理不在当前持仓目标中的旧键，避免字典无限增长
            active_codes = {item['etf'] for item in final_result}
            streaks = {k: v for k, v in streaks.items() if k in active_codes}
            g.normal_not_topk_streaks = streaks
            # 单持仓变量在多持仓场景不再使用，清零避免混淆日志
            g.normal_not_rank1_streak = 0
            g.normal_streak_hold_code = None

            log_buffer.append(
                f"{AC}多持仓防频换完成：保留{len(retained)}只，最终目标{len(final_result)}/{target_count}只，TopK={topk}"
            )
            log.info(
                f"{AC}多持仓防频换: 保留{len(retained)} 目标{len(final_result)}/{target_count} TopK={topk}"
            )
        else:
            max_days = max_days_single
            H = current_holdings[0] if len(current_holdings) == 1 else (current_holdings[0] if current_holdings else None)
            rH = _rank_in_filtered_list(filtered_list, H) if H else None

            if not H:
                final_result = [new_first]
                g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = new_first['etf']
                t = f"{AC}无持仓 → 目标为候选池第1名"
                log_buffer.append(t)
                log.info(f"{t}: {new_first['etf']} {new_first['etf_name']}")
            elif H not in pool_codes or rH is None:
                reason = "掉出候选池" if H not in pool_codes else "不在过筛排序表"
                # ---- B.4 改进：状态切换日禁用立即换股 ----
                _today_dt = context.current_dt.date()
                _regime_change_day = getattr(g, 'regime_last_change_date', None)
                _b4_hit = (
                    getattr(g, 'B4_disable_immediate_swap_on_regime_change', False)
                    and _regime_change_day == _today_dt
                )
                if _b4_hit:
                    _h_metric = next((x for x in all_metrics if x.get('etf') == H), None)
                    if _h_metric is None:
                        _h_metric = (getattr(g, 'last_metrics_by_etf_code', {}) or {}).get(H)
                    if _h_metric is None:
                        _h_metric = {'etf': H, 'etf_name': get_security_name(H)}
                    final_result = [_h_metric]
                    g.normal_streak_hold_code = H
                    t = (
                        f"{AC}🚧 【B.4 状态切换日禁立即换股】今日 {_today_dt} == 状态切换生效日，"
                        f"虽然 {H} {reason}，仍保留持有，明日再按正常逻辑换股"
                    )
                    log_buffer.append(t)
                    log.info(t)
                else:
                    switch_item, sw_mode = resolve_switch_target(
                        context, candidate_pool, H, filtered_list, all_metrics, log_buffer,
                    )
                    if sw_mode == 'keep_high_corr' and switch_item is not None:
                        final_result = [switch_item]
                        g.normal_streak_hold_code = H
                        t = f"{AC}立即换股中止({reason})：高相关无低相关候选 → 继续持有 {H} {switch_item.get('etf_name')}"
                    elif switch_item is not None:
                        final_result = [switch_item]
                        g.normal_not_rank1_streak = 0
                        g.normal_streak_hold_code = switch_item['etf']
                        t = (
                            f"{AC}立即换股({reason})：{H} → {switch_item['etf']} "
                            f"{switch_item['etf_name']}"
                        )
                    else:
                        final_result = [new_first] if new_first else []
                        if new_first:
                            g.normal_not_rank1_streak = 0
                            g.normal_streak_hold_code = new_first['etf']
                        t = f"{AC}立即换股({reason})：{H} → 候选 {new_first['etf'] if new_first else '—'}"
                    log_buffer.append(t)
                    log.info(t)
            elif rH == 1:
                g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = H
                final_result = [candidate_dict[H]]
                t = (
                    f"{AC}持仓即为过筛动量第1名 → 继续持有 streak已清零 | "
                    f"持仓 {H} {candidate_dict[H]['etf_name']}"
                )
                log_buffer.append(t)
                log.info(t)
            else:
                if g.normal_streak_hold_code != H:
                    g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = H
                g.normal_not_rank1_streak = int(getattr(g, 'normal_not_rank1_streak', 0)) + 1
                streak = g.normal_not_rank1_streak
                log_buffer.append(
                    f"{AC}持仓在候选池内，过筛名次={rH}/第1名={rank1_etf}({rank1_name})，"
                    f"连续未登首 streak={streak}/{max_days}"
                )
                log.info(
                    f"{AC} {H} {candidate_dict[H]['etf_name']} "
                    f"名次{rH} 未登首{streak}/{max_days}天 候选池内 | 今日第1名 {rank1_etf}"
                )
                if streak >= max_days:
                    switch_item, sw_mode = resolve_switch_target(
                        context, candidate_pool, H, filtered_list, all_metrics, log_buffer,
                    )
                    if sw_mode == 'keep_high_corr' and switch_item is not None:
                        final_result = [switch_item]
                        g.normal_streak_hold_code = H
                        t = (
                            f"{AC}⭐已满{max_days}日未登第1但高相关无替代 → 继续持有 "
                            f"{H} {switch_item.get('etf_name')}"
                        )
                    elif switch_item is not None:
                        final_result = [switch_item]
                        g.normal_not_rank1_streak = 0
                        g.normal_streak_hold_code = switch_item['etf']
                        t = (
                            f"{AC}⭐已满{max_days}个交易日未重返第1名 → 换股为 "
                            f"{switch_item['etf']} {switch_item['etf_name']}"
                        )
                    else:
                        final_result = [new_first] if new_first else []
                        if new_first:
                            g.normal_not_rank1_streak = 0
                            g.normal_streak_hold_code = new_first['etf']
                        t = f"{AC}⭐已满{max_days}日未登第1 → 换股为候选第1"
                    log_buffer.append(t)
                    log.info(t)
                else:
                    final_result = [candidate_dict[H]]
                    t = (
                        f"{AC}继续持有 {H} {candidate_dict[H]['etf_name']} "
                        f"（streak {streak}/{max_days}，未满不换）"
                    )
                    log_buffer.append(t)
                    log.info(t)
    else:
        anti_churn_candidate_pool_empty = (
            g.holdings_num == 1
            and len(candidate_pool) == 0
            and (
                regime == '正常期'
                or (regime == '震荡期' and getattr(g, 'oscillation_anti_churn_enabled', False))
                or (regime == '走弱期' and getattr(g, 'weak_anti_churn_enabled', False))
            )
        )
        if anti_churn_candidate_pool_empty:
            g.normal_not_rank1_streak = 0
            g.normal_streak_hold_code = None
            g.normal_not_topk_streaks = {}
            msg = "【防频换】候选池为空，回退原合并逻辑，streak已清零"
            log_buffer.append(msg)
            log.info(msg)
        retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
        log_buffer.append(f"其中存在于候选池中的持仓ETF：{[item['etf'] for item in retained]}")
        if len(retained) >= g.holdings_num:
            retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
            final_result = retained_sorted[:g.holdings_num]
            log_buffer.append(f"保留的持仓ETF数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的ETF中按动量得分取前{g.holdings_num}只作为最终目标。")
        else:
            need = g.holdings_num - len(retained)
            remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
            additional = remaining_pool[:need]
            final_result = retained + additional
            log_buffer.append(f"保留持仓ETF {len(retained)}只，还需补充{need}只。")
            if retained:
                log_buffer.append("保留的ETF（按原有顺序）：")
                for item in retained:
                    log_buffer.append(f"  {item['etf_name']}({item['etf']})")
            if additional:
                log_buffer.append("补充的ETF（按动量得分排序）：")
                for i, item in enumerate(additional):
                    log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")
    final_result = apply_corr_hold_guard(
        context, final_result, all_metrics, filtered_list, log_buffer
    )
    if getattr(g, 'enable_switch_hysteresis', False) and g.holdings_num == 1 and final_result:
        hs_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
        if hs_holdings:
            hs_current = hs_holdings[0]
            hs_target = final_result[0]['etf']
            if hs_current != hs_target:
                in_range = regime == '震荡期'
                hbuf = float(getattr(g, 'switch_buffer_range', 0.40)) if in_range else float(getattr(g, 'switch_buffer_normal', 0.10))
                hs_cur_metric = next((m for m in filtered_list if m['etf'] == hs_current), None)
                if hs_cur_metric is None:
                    hs_cur_metric = next((m for m in all_metrics if m['etf'] == hs_current), None)
                if hs_cur_metric is not None:
                    t_sc = final_result[0].get(score_key, float('-inf'))
                    c_sc = hs_cur_metric.get(score_key, float('-inf'))
                    hurdle = c_sc * (1.0 + hbuf)
                    t_nm = final_result[0].get('etf_name', hs_target)
                    c_nm = hs_cur_metric.get('etf_name', hs_current)
                    log_buffer.append(
                        f"🔎 【Whipsaw·滞回】缓冲={hbuf:.0%}({'震荡期' if in_range else '正常期'}), "
                        f"要求 {score_key}(目标)>{hurdle:.4f} (=持仓{c_sc:.4f}×(1+{hbuf:.0%}))"
                    )
                    if np.isfinite(t_sc) and np.isfinite(c_sc):
                        if t_sc <= hurdle:
                            log_buffer.append(
                                f"⏸️ 【Whipsaw·滞回】拦截换仓 → 保留 {c_nm}({hs_current})"
                            )
                            if getattr(g, 'log_whipsaw_filter_detail', True):
                                log.info(
                                    f"【Whipsaw·滞回】拦截换仓: 目标 {hs_target} {score_key}={t_sc:.4f} ≤ 门槛 {hurdle:.4f} "
                                    f"(持仓 {hs_current} {score_key}={c_sc:.4f})"
                                )
                            final_result = [hs_cur_metric]
                        else:
                            log_buffer.append(f"✅ 【Whipsaw·滞回】通过: {t_nm} {score_key}={t_sc:.4f} > {hurdle:.4f}")
                    else:
                        log_buffer.append("ℹ️ 【Whipsaw·滞回】跳过: 评分非有限值")
                else:
                    log_buffer.append(f"ℹ️ 【Whipsaw·滞回】跳过: 持仓 {hs_current} 无指标记录")
    log_buffer.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']})")
    log_buffer.append("==================================================")
    full_log = "\n".join(log_buffer)
    log.info(full_log)
    return final_result


def execute_sell_trades(context):
    log.info("========== 卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    current_positions = list(context.portfolio.positions.keys())
    current_holdings_nonzero = [s for s in current_positions if context.portfolio.positions[s].total_amount > 0]
    target_etfs = []
    # 注意：ranked_etfs_result 是“最终目标结果”，不是候选池本身；候选池与过滤名单需单独保存
    filtered_codes_today = list(getattr(g, 'today_filtered_codes', []) or [])
    candidate_codes_today = list(getattr(g, 'today_candidate_pool_codes', []) or [])
    
    if ranked_etfs:
        g.defensive_switch_pending_streak = 0
        g.defensive_switch_last_signal_date = None
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}")
    else:
        if check_defensive_etf_available(context):
            # 防御切换确认：避免单日噪声导致立刻从风险资产切防御
            if getattr(g, 'enable_defensive_switch_confirm', False):
                today = context.current_dt.date()
                if g.defensive_switch_last_signal_date != today:
                    g.defensive_switch_pending_streak = int(getattr(g, 'defensive_switch_pending_streak', 0)) + 1
                    g.defensive_switch_last_signal_date = today
                need_days = max(1, int(getattr(g, 'defensive_switch_confirm_days', 1)))
                already_defensive = (len(current_holdings_nonzero) == 1 and current_holdings_nonzero[0] == g.defensive_etf)
                if already_defensive or g.defensive_switch_pending_streak >= need_days:
                    target_etfs = [g.defensive_etf]
                    etf_name = get_security_name(g.defensive_etf)
                    log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
                else:
                    target_etfs = current_holdings_nonzero[:]
                    log.info(
                        f"🕒 防御切换确认中：{g.defensive_switch_pending_streak}/{need_days}，"
                        f"暂不切换防御ETF，维持当前持仓"
                    )
            else:
                target_etfs = [g.defensive_etf]
                etf_name = get_security_name(g.defensive_etf)
                log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
        else:
            g.defensive_switch_pending_streak = 0
            g.defensive_switch_last_signal_date = None
            log.info("💤 无最终目标(空仓模式)")
            target_etfs = []
    
    # 非动量排行场景（防御模式 / 策略空仓）的统一卖出原因前缀
    if (not ranked_etfs) and target_etfs:
        # 无排名结果但有防御标的 → 切换到防御ETF
        etf_name = get_security_name(target_etfs[0])
        base_exit_reason = f"防御模式卖出：腾出仓位切换至防御ETF {target_etfs[0]} {etf_name}（午盘清仓）"
    elif (not ranked_etfs) and (not target_etfs):
        # 今日无任何目标 → 策略选择空仓
        base_exit_reason = "策略空仓卖出：今日无目标ETF，全部持仓午盘清仓"
    else:
        base_exit_reason = ""
    
    g.target_etfs_list = target_etfs
    target_set = set(target_etfs)
    sell_count = 0
    
    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            exit_bucket = 'other'
            exit_detail = '防御/空仓/非动量调仓'
            # 针对不同场景生成更细化的卖出原因
            if ranked_etfs:
                # 正常动量调仓场景：进一步区分几种情况
                try:
                    target_desc = ", ".join(target_etfs) if target_etfs else "无"
                except Exception:
                    target_desc = "—"
                if security not in candidate_codes_today:
                    # 1) 已不在今日候选池：要进一步区分是“被过滤掉”还是“过筛但未达候选门槛/未入Top10”
                    if security not in filtered_codes_today:
                        met = getattr(g, 'last_metrics_by_etf_code', {}).get(security)
                        fail_detail = explain_filter_failures_for_etf(security, met)
                        exit_reason = (
                            "动量调仓卖出：已被第二步过滤剔除，真实原因="
                            f"{fail_detail}；不在今日目标ETF列表（今日目标: {target_desc}），且午盘清仓"
                        )
                        exit_detail = str(fail_detail)
                        if '无指标记录' in str(fail_detail):
                            exit_bucket = 'missing_data'
                        else:
                            exit_bucket = 'filter_fail'
                    else:
                        met = getattr(g, 'last_metrics_by_etf_code', {}).get(security) or {}
                        sc = met.get('momentum_rank_score', met.get('momentum_score'))
                        rk = (getattr(g, 'today_filtered_rank_map', {}) or {}).get(security)
                        th = getattr(g, 'today_candidate_score_threshold', None)
                        if th is not None and sc is not None:
                            detail = f"通过过滤但未入候选池：排序分{sc:.4f} < 候选门槛{th:.4f}"
                        elif rk is not None:
                            detail = f"通过过滤但未入候选池：过滤后排名第{rk}（仅Top10参与候选池）"
                        else:
                            detail = "通过过滤但未入候选池：未达到候选池入选规则"
                        exit_reason = (
                            f"动量调仓卖出：{detail}；不在今日目标ETF列表（今日目标: {target_desc}），且午盘清仓"
                        )
                        exit_bucket = 'rank_lag'
                        exit_detail = detail
                else:
                    # 2) 仍在候选池，但动量排名落后，没进入前N名目标
                    exit_reason = (
                        f"动量调仓卖出：仍在今日候选池但未进入前{g.holdings_num}名目标ETF，"
                        f"今日目标: {target_desc}，且午盘清仓"
                    )
                    exit_bucket = 'rank_lag'
                    exit_detail = f"仍在候选池但未进入前{g.holdings_num}名"
            else:
                # 防御模式 / 策略空仓 等统一使用 base_exit_reason
                exit_reason = base_exit_reason or "午盘清仓"

            # ---- A.2 改进：新仓最小持有天数 ----
            # 仅对 "动量调仓·filter_fail / rank_lag" 类卖出生效；
            # 防御切换/空仓/止损/回撤动作 等风控类卖出不受 A.2 约束。
            if exit_bucket in ('filter_fail', 'rank_lag'):
                _a2_imm_reason = (
                    '已被第二步过滤剔除' if exit_bucket == 'filter_fail' else '掉出候选池/未进TopN'
                )
                if _a2_should_block_swap_out(context, security, immediate_swap_reason=_a2_imm_reason):
                    held_d = _a2_held_days(context, security)
                    min_hold = int(getattr(g, 'A2_min_hold_days', 2))
                    log.info(
                        f"⏳ 【A.2 最小持有天数】跳过卖出 {security} {security_name}：已持有 {held_d} 日 < {min_hold} 日，"
                        f"原拟卖出原因: {exit_reason}"
                    )
                    # 把该 ETF 强制加入今日目标，避免买入分支又试图换其他标的导致超仓
                    if security not in target_etfs:
                        target_etfs.append(security)
                        g.target_etfs_list = target_etfs
                        target_set.add(security)
                    continue
            success = smart_order_target_value(security, 0, context, exit_reason=exit_reason)
            if success:
                sell_count += 1
                _record_exit_reason_stat(exit_bucket, exit_detail, getattr(g, 'market_regime', '未知'))
                log.info(f"✅ 已成功卖出: {security} {security_name}")
                # ---- +2 改进：累计 "过滤剔除" 日数（一天最多 +1，无论几只）----
                if getattr(g, 'S2_enable_consecutive_filter_fail_to_defensive', False) and exit_bucket == 'filter_fail':
                    today_d = context.current_dt.date()
                    if getattr(g, 'S2_filter_fail_last_signal_date', None) != today_d:
                        g.S2_filter_fail_streak = int(getattr(g, 'S2_filter_fail_streak', 0)) + 1
                        g.S2_filter_fail_last_signal_date = today_d
                        log.info(
                            f"📈 【+2 过滤剔除累计】连续 {g.S2_filter_fail_streak} "
                            f"个交易日出现 filter_fail 卖出"
                        )
    
    log.info(f"本次共计划卖出{sell_count}只ETF。")
    log.info("========== 卖出操作完成 ==========")


def execute_buy_trades(context):
    log.info("========== 买入操作开始 ==========")
    target_etfs = g.target_etfs_list
    
    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return
    
    # ---- +1 改进：止损全局冷却（早于 first_allowed_date 的交易日跳过所有买入）----
    if getattr(g, 'S1_enable_stop_loss_global_cooldown', False):
        block_until = getattr(g, 'S1_stop_loss_global_block_until_date', None)
        if block_until is not None:
            bd = block_until.date() if hasattr(block_until, 'date') else block_until
            today_d = context.current_dt.date()
            if today_d < bd:
                log.info(
                    f"🧊 【+1 止损全局冷却】今日 {today_d} < 解冻日 {bd}，全账户跳过买入"
                )
                log.info("========== 买入操作完成 ==========")
                return
            # 到期清理，避免日志重复
            elif today_d >= bd:
                g.S1_stop_loss_global_block_until_date = None

    # ---- +2 改进：连续 N 日 "过滤剔除" → 强制切到防御 ETF ----
    if getattr(g, 'S2_enable_consecutive_filter_fail_to_defensive', False):
        today_d2 = context.current_dt.date()
        last_sig = getattr(g, 'S2_filter_fail_last_signal_date', None)
        # 今日没有任何 filter_fail 卖出 → 计数器清零
        if last_sig != today_d2:
            if int(getattr(g, 'S2_filter_fail_streak', 0)) > 0:
                log.info(
                    f"📉 【+2 过滤剔除累计】今日无 filter_fail 卖出，streak "
                    f"{g.S2_filter_fail_streak}→0 重置"
                )
            g.S2_filter_fail_streak = 0
        else:
            need_n = int(getattr(g, 'S2_consecutive_filter_fail_days', 3))
            if int(g.S2_filter_fail_streak) >= need_n:
                # 触发：强制把目标改为防御 ETF（前提：防御 ETF 可用）
                if check_defensive_etf_available(context):
                    def_etf = getattr(g, 'defensive_etf', None)
                    if def_etf:
                        log.warning(
                            f"🛡️ 【+2 转防御】连续 {g.S2_filter_fail_streak}≥{need_n} 日 "
                            f"filter_fail，强制目标=防御ETF {def_etf} {get_security_name(def_etf)}"
                        )
                        # 先把当前持仓里非防御 ETF 卖掉（execute_sell_trades 已过，需补卖）
                        _sold_for_s2 = False
                        for _sec in list(context.portfolio.positions.keys()):
                            if _sec == def_etf:
                                continue
                            _pos = context.portfolio.positions.get(_sec)
                            if _pos and _pos.total_amount > 0:
                                _ok = smart_order_target_value(
                                    _sec, 0, context,
                                    exit_reason=f"+2 连续{g.S2_filter_fail_streak}日filter_fail切防御",
                                )
                                if _ok:
                                    _sold_for_s2 = True
                        target_etfs = [def_etf]
                        g.target_etfs_list = target_etfs
                        # 触发后清零 streak，下次重新累计
                        g.S2_filter_fail_streak = 0
                        g.S2_filter_fail_last_signal_date = None
                        if _sold_for_s2:
                            log.info("【+2 转防御】已补卖非防御持仓，下面将买入防御ETF")
                else:
                    log.warning(
                        f"🛡️ 【+2 转防御】连续 {g.S2_filter_fail_streak}≥{need_n} 日 "
                        f"filter_fail，但防御ETF不可用，按原目标继续"
                    )

    current_positions = set(context.portfolio.positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    etfs_to_buy = _filter_stop_loss_rebuy_cooldown(context, etfs_to_buy)
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    
    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("========== 买入操作完成 ==========")
        return
    
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标持仓: {g.holdings_num}只, 本次计划买入: {num_etfs_to_buy}只")
    
    # 修复：动态分配资金，避免可用现金为负
    for i, etf in enumerate(etfs_to_buy):
        remaining_cash = context.portfolio.available_cash
        if remaining_cash < g.min_money:
            log.info(f"可用现金 {remaining_cash:.2f} 不足最小交易额 {g.min_money:.2f}，停止买入")
            break
        
        remaining_to_buy = len(etfs_to_buy) - i
        target_value_for_this_etf = remaining_cash // remaining_to_buy
        
        # 最后一笔可使用剩余全部现金，但确保不小于最小交易额
        if target_value_for_this_etf < g.min_money and remaining_cash >= g.min_money:
            target_value_for_this_etf = remaining_cash
        
        log.info(f"为 {etf} 分配目标金额: {target_value_for_this_etf:.2f} 元 (剩余现金 {remaining_cash:.2f}, 待买数量 {remaining_to_buy})")
        
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
            record_buy_trade_entry(context, etf)
        else:
            log.info(f"❌ ETF {etf} 下单失败")
    
    log.info("========== 买入操作完成 ==========")

def smart_order_target_value(security, target_value, context, exit_reason='午盘清仓'):
    current_data = get_current_data()
    security_name = get_security_name(security)

    # ========== 1. 买入初步资金检查（仅对买入操作） ==========
    if target_value > 0:
        available_cash = context.portfolio.available_cash
        if target_value > available_cash:
            target_value = available_cash
        if target_value < g.min_money:
            log.info(f"{security} {security_name}: 目标金额{target_value:.2f}小于最小交易额{g.min_money}，跳过")
            return False

    # ========== 2. 通用交易限制 ==========
    if current_data[security].paused:
        log.info(f"{security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {security_name}: 当前涨停，跳过交易")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {security_name}: 当前跌停，跳过交易")
        return False

    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {security_name}: 当前价格为0，跳过交易")
        return False

    # ========== 3. 买入时使用预估成交价（包含佣金+滑点）计算股数 ==========
    # 佣金和滑点费率（买入方向）
    buy_commission_rate = 0.0001   # 买入佣金
    slippage_rate = 0.0001         # 滑点（价格相关滑点）
    estimated_price = current_price * (1 + buy_commission_rate + slippage_rate)
    
    if target_value > 0:
        # 用预估价格计算可买股数，确保实际花费不超可用现金
        target_amount = int(target_value / estimated_price)
        target_amount = (target_amount // 100) * 100
        if target_amount <= 0 and target_value > 0:
            target_amount = 100
        # 二次校验：用实时可用现金和当前价格严格限制（兜底）
        max_shares = int(context.portfolio.available_cash / current_price)
        max_shares = (max_shares // 100) * 100
        if max_shares < target_amount:
            log.info(f"{security} {security_name}: 现金可买{max_shares}股，原计划{target_amount}股，已调低")
            target_amount = max_shares
        if target_amount <= 0:
            log.info(f"{security} {security_name}: 现金不足买100股，跳过")
            return False
    else:
        # 卖出时不需要考虑资金，直接按目标数量0计算
        target_amount = 0

    # ========== 4. 获取当前持仓 ==========
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price

    # 小额交易过滤
    if 0 < trade_value < g.min_money:
        log.info(f"{security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过")
        return False

    # 卖出时检查可卖股数
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {security_name}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    avg_cost_before = 0.0
    if current_position and getattr(current_position, 'avg_cost', None):
        try:
            avg_cost_before = float(current_position.avg_cost)
        except Exception:
            avg_cost_before = 0.0

    # ========== 5. 执行下单 ==========
    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            if amount_diff > 0:
                log.info(f"📦 买入{security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f} (预估含成本价: {estimated_price:.3f})")
            else:
                regime_now = getattr(g, 'market_regime', '')
                regime_str = f"{regime_now}" if regime_now else "—"
                log.info(
                    f"📤 卖出{security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}，"
                    f"原因: {exit_reason}，市场状态: {regime_str}"
                )
                pos_after = context.portfolio.positions.get(security)
                amt_after = pos_after.total_amount if pos_after else 0
                if amt_after <= 0:
                    record_etf_roundtrip_on_sell(
                        context, security, float(abs(amount_diff)),
                        avg_cost_before, float(current_price), exit_reason
                    )
            return True
        else:
            log.warning(f"下单失败: {security} {security_name}，数量: {amount_diff}")
            return False
    return False


def _stop_loss_rebuy_cutoff_dt():
    if getattr(g, 'enable_split_afternoon_trades', False):
        s = getattr(g, 'stop_loss_rebuy_cutoff_time', None) or getattr(g, 'afternoon_buy_time', '13:11')
        fallback = dt_time(13, 11)
    else:
        s = getattr(g, 'stop_loss_rebuy_cutoff_time', None) or getattr(g, 'afternoon_sell_time', '13:10')
        fallback = dt_time(13, 10)
    try:
        parts = str(s).strip().split(':')
        return dt_time(int(parts[0]), int(parts[1]))
    except Exception:
        return fallback


def _first_allowed_buy_date_after_stop_loss(stop_date, cooldown_trade_days):
    """
    止损所在交易日为 D；从 D 的次一交易日起连续 cooldown_trade_days 个交易日禁止买入。
    返回首个允许买入的交易日（date）。
    """
    n = max(0, int(cooldown_trade_days))
    arr = get_trade_days(start_date=stop_date, count=n + 10)
    if len(arr) < n + 2:
        return stop_date
    first_allow = arr[n + 1]
    return first_allow.date() if hasattr(first_allow, 'date') else first_allow


def _record_stop_loss_rebuy_cooldown(context, security):
    """在分钟止损下单成功后调用：仅统计 cutoff 时间之前的止损。"""
    # ---- +1 改进：全局止损冷却（独立于单标的冷却，对账户内任何买入都禁止）----
    if getattr(g, 'S1_enable_stop_loss_global_cooldown', False):
        try:
            n_g = int(getattr(g, 'S1_stop_loss_global_cooldown_days', 1))
            if n_g >= 1:
                stop_day_g = context.current_dt.date()
                first_allow_g = _first_allowed_buy_date_after_stop_loss(stop_day_g, n_g)
                # 取较晚日期保留（避免被更短冷却覆盖）
                prev = getattr(g, 'S1_stop_loss_global_block_until_date', None)
                if prev is None or (first_allow_g is not None and first_allow_g > prev):
                    g.S1_stop_loss_global_block_until_date = first_allow_g
                log.info(
                    f"🧊 【+1 止损全局冷却】登记触发：止损日 {stop_day_g}，"
                    f"全账户买入冷却 {n_g} 个交易日（最早允许买入日 {g.S1_stop_loss_global_block_until_date}）"
                )
        except Exception as e:
            log.warning(f"【+1 止损全局冷却】登记异常: {e}")
    if not getattr(g, 'enable_stop_loss_rebuy_cooldown', False):
        return
    if context.current_dt.time() >= _stop_loss_rebuy_cutoff_dt():
        return
    stop_day = context.current_dt.date()
    n = int(getattr(g, 'stop_loss_rebuy_cooldown_trade_days', 2))
    first_allow = _first_allowed_buy_date_after_stop_loss(stop_day, n)
    if not hasattr(g, 'stop_loss_rebuy_first_allowed_date'):
        g.stop_loss_rebuy_first_allowed_date = {}
    g.stop_loss_rebuy_first_allowed_date[security] = first_allow
    log.info(
        f"📌 【止损买回冷却】登记 {security} {get_security_name(security)} "
        f"最早可买回日 {first_allow}（止损日 {stop_day}，随后禁买 {n} 个交易日）"
    )


def _a2_held_days(context, security):
    """A.2：返回 security 已持有的【日历天数】（None=未登记买入日 / 未开启 A2）。"""
    if not getattr(g, 'A2_enable_min_hold_days', False):
        return None
    bm = getattr(g, 'A2_buy_first_day_map', None)
    if not isinstance(bm, dict):
        return None
    bd = bm.get(security)
    if bd is None:
        return None
    today = context.current_dt.date()
    if hasattr(bd, 'date'):
        bd = bd.date()
    try:
        return (today - bd).days
    except Exception:
        return None


def _a2_should_block_swap_out(context, security, immediate_swap_reason=None):
    """A.2：是否应阻止把 security 因 "过滤/防频换/立即换股" 而卖出。
    immediate_swap_reason: '掉出候选池' / '不在过筛排序表' / None。
    返回 True 表示当前应继续持有 security（最小持有天数未到）。
    """
    if not getattr(g, 'A2_enable_min_hold_days', False):
        return False
    min_hold = int(getattr(g, 'A2_min_hold_days', 2))
    if min_hold <= 0:
        return False
    held = _a2_held_days(context, security)
    if held is None:
        # 旧仓（无买入日记录）不受 min-hold 约束
        return False
    if held >= min_hold:
        return False
    # 若开关允许 "立即换股(掉出候选池)" 绕过 min-hold，则在该场景不拦截
    if (
        immediate_swap_reason is not None
        and getattr(g, 'A2_allow_immediate_swap_skip_minhold', True)
    ):
        return False
    return True


def _filter_stop_loss_rebuy_cooldown(context, candidate_etfs):
    """买入候选中剔除仍在冷却内的标的。"""
    if not getattr(g, 'enable_stop_loss_rebuy_cooldown', False):
        return list(candidate_etfs)
    fa_map = getattr(g, 'stop_loss_rebuy_first_allowed_date', None) or {}
    today = context.current_dt.date()
    out = []
    for c in candidate_etfs:
        fa = fa_map.get(c)
        if fa is None:
            out.append(c)
            continue
        fd = fa.date() if hasattr(fa, 'date') else fa
        if today < fd:
            log.info(
                f"⏸️ 【止损买回冷却】跳过买入 {c} {get_security_name(c)}，最早允许 {fd}"
            )
            continue
        out.append(c)
    return out


def minute_level_stop_loss(context):
    if not g.use_fixed_stop_loss:
        return

    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    
    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 【分钟级固定止损】{security} {security_name} 触发止损，亏损: {loss_percent:.2f}%")
            ok = smart_order_target_value(security, 0, context, exit_reason='分钟固定止损')
            if ok:
                _record_stop_loss_rebuy_cooldown(context, security)


def minute_level_pct_stop_loss(context):
    if not g.use_pct_stop_loss:
        return
    
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    
    current_data = get_current_data()
    current_date = context.current_dt.date()
    
    if not hasattr(g, 'cache_date') or g.cache_date != current_date:
        g.yesterday_close_cache = {}
        g.cache_date = current_date
    
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        
        yesterday_close = getattr(g, 'yesterday_close_cache', {}).get(security)
        if yesterday_close is None:
            try:
                close_series = attribute_history(security, 1, '1d', ['close'], skip_paused=False)
                if len(close_series['close']) == 0:
                    continue
                yesterday_close = close_series['close'][-1]
                if yesterday_close <= 0:
                    continue
                g.yesterday_close_cache[security] = yesterday_close
            except Exception:
                continue
        
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        
        stop_price = yesterday_close * g.pct_stop_loss_threshold
        if current_price <= stop_price:
            security_name = get_security_name(security)
            daily_loss = (current_price / yesterday_close - 1) * 100
            log.info(f"🚨 【分钟级跌幅止损】{security} {security_name} 触发止损，当日跌幅: {daily_loss:.2f}%")
            ok = smart_order_target_value(security, 0, context, exit_reason='分钟跌幅止损')
            if ok:
                _record_stop_loss_rebuy_cooldown(context, security)


def get_security_name(security):
    try:
        if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"


def check_defensive_etf_available(context):
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    if current_data[defensive_etf].paused:
        log.info(f"防御性ETF {defensive_etf} 今日停牌")
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        log.info(f"防御性ETF {defensive_etf} 当前涨停")
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        log.info(f"防御性ETF {defensive_etf} 当前跌停")
        return False
    return True


def trade(context):
    pass

# 记得在原代码的run_daily时间任务后，加入下面2行run_daily，去掉符号#
    #run_daily(record_daily_positions_to_storage, time='15:30')  # 每天记录到缓存
    #run_daily(output_all_positions_summary, time='after_close')  # 最后一天汇总输出
# ==================== 每日持仓成交金额（仅打印当日）====================
def record_daily_positions_to_storage(context):
    """每天15:30：仅打印当日持仓ETF的成交金额（不累积多日汇总）"""
    current_date = context.current_dt.strftime('%Y-%m-%d')
    holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    if not holdings:
        log.info(f"【持仓成交】{current_date} 无持仓")
        return
    try:
        df = get_price(holdings, start_date=current_date, end_date=current_date,
                       frequency='daily', fields=['money'], panel=False, skip_paused=True)
        for sec in holdings:
            etf_data = df[df['code'] == sec]
            turnover = etf_data['money'].iloc[-1] if not etf_data.empty else 0
            etf_name = get_security_name(sec)
            turnover_yi = turnover / 100000000
            turnover_str = f"{turnover_yi:.2f}亿"
            log.info(f"【持仓成交】{current_date} {sec} {etf_name} 当日成交金额 {turnover_str}")
    except Exception as e:
        log.error(f"【持仓成交】查询失败: {e}")


def output_all_positions_summary(context):
    """回测最后一天仅输出市场状态累计看板（不再打印多日持仓成交汇总表）"""
    end_date = context.run_params.end_date
    today = context.current_dt.date()
    if today != end_date:
        return
    log_regime_performance_dashboard(context, full=True)
    log_corr_guard_mom_padj_regime_matrix(context)
    log_ma_break_nextday_summary(context)
    log_trade_roundtrip_leaderboard(context, top_n=20)