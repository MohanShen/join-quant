# Clone from JoinQuant
# postId: 24c875937455660e2a152f9f7987f5f3
# backtestId: 04477757c62c96f9d7f7951865cd13aa
# title: 七星高照ETF轮动V1.7.5之PT分仓隔离版本


# 标题：七星超级加175v311 V3.15 双风险规避定版（聚宽）
# 作者：任侠

"""
七星超级加175v311 V3.15 双风险规避定版（聚宽独立版，基于 V3.14）

【说明】
- 由合并版 `七星超级加175v311V3.15.py` 拆分；QMT 端见 `七星超级加175v311V3.15-QMT.py`。

【变更记录】
- V3.15 [2026/05/25]（当前定版）
  - 盈利仓分钟回撤豁免：浮盈≥10% 时分钟守卫不卖，改由 13:09/盈利保护处理（修 3/4 原油 10:31 误杀）。
  - 盈利仓 13:09 回撤仅用日内高点→现价，不用昨收跳空（保留对亏损仓的昨收低开保护）。
  - 同日 13:09 轮动卖海外后，13:10 允许买入另一只 QDII（修 6/5 标普→日经被挡又买回标普）。
- V3.14 [2026/05/25]
  - 日内回撤守卫扩展：get_intraday_drawdown_ratio 买入/13:09 持仓/分钟检查三处共用；持仓触发则强制卖并剔除目标缓存。
  - 关闭防御 ETF 兜底（enable_defensive_etf=False）：无合格标的时保持空仓，减少 511010 换仓摩擦（全周期约 37 笔）。
  - 双弱无商品标的时亦空仓（不再兜底 511010）。
  - 持仓回撤补昨收基准：除日内高点→现价外，兼看昨收→现价（覆盖跳空低开）。
  - 有害卖出冷却期内禁止买回同一只标的（修复 6/4 卖出 513520 后 6/5 又买回）。
  - 回撤测算统一 float 转换（修复分钟检查 str/float 异常导致盘中守卫失效）。
- V3.13 [2026/05/25]
  - 双风险规避固定：A 股弱（回避 A 股 ETF）+ 海外弱（屏蔽 QDII）独立判断、四格池、盘中现价双轨复检。
  - 13:09/13:10 统一 refresh_regime_for_trade：A 股弱与海外弱同分钟各检一次，边界迟滞 + 有效池/守卫/缓存复检闭环。
  - 定版目标：规避国内系统性风险与海外 QDII 风险，双弱时仅商品池（V3.13 曾兜底 511010，V3.14 已关）。
- V3.12.3 [2026/05/25]
  - 海外弱双轨：09:40 日 K 定调 + 13:09/13:10 盘中现价对 MA 复检（真正「越晚越准」）。
  - 边界迟滞：同日 enter/exit 同时满足时维持原状态，盘中退出门槛 3/4（严于进入 2/4），且每分钟只复检一次。
- V3.12.2 [2026/05/25]
  - resolve_rotation_targets / select_target 统一强制当前有效池过滤；池与缓存排名不一致时兜底路径自动重算排名，杜绝回退仍选池外 QDII。
- V3.12.1 [2026/05/25]
  - 13:10 复用缓存前：刷新海外弱状态，对缓存目标复跑全部买入守卫，并剔除当前有效池外弱势标；不足则排名顺延或 resolve 兜底。
- V3.12 [2026/05/25]
  - 海外弱独立判断（与 A 股弱解耦）：4 个 QDII 代理 MA10/MA5 结构，≥2/4 进入海外弱。
  - 四格 active_pool：A正常+海外弱→A股+商品；A弱+海外弱→仅商品；海外弱即屏蔽 QDII 排名。
  - 海外弱时商品替代买入门槛 buy_min_score_overseas_weak；无合格标的仍走 511010 兜底。
  - 走弱期轮动卖出海外 QDII 后 1 日禁买同簇；有害卖 2 日 qdii_guard 保留。
  - overseas_proxy_pool 去掉 513100，与 159509 对齐。
- V3.11 [2026/05/25]
  - 在 V3.10 高收益骨架上精修：走弱期有害卖出由「2日全盘空仓」改为「2日仅挡QDII追高」，商品/原油等可继续轮动（修复3月原油被挡）。
  - 走弱期冷却内叠加：海外有害簇挡 + 低相关守卫（仅挡高相关海外，不挡商品）。
  - 排名得分上限 100→10000，避免超高动量主线被误杀。
- V3.10 [2026/05/25]
  - 有害卖出冷却收窄：正常期仅禁止同日买回该标的（drawdown_selled_today），不暂停轮动、不强制511010。
  - 走弱期保留有害卖出后2日空仓（防6/3纳指回撤后接日经）。
  - 买入得分保持V3.9：仅下限0.2、上限100，无年化上限。
- V3.9 [2026/05/25]
  - 买入仅下限0.2/上限100；V3.9回测1-5月约195%（V3.6约220%），差距主因正常期有害冷却误杀轮动。
- V3.8 [2026/05/25]
  - 买入得分[0.2,10.0]；关闭全局年化上限；有害卖出后严带≤2.5（实测仍挡主线）。
- V3.7 [2026/06/03]
  - 有害卖出冷却：分钟回撤/盈利保护卖出后暂停轮动；正常期防御511010，走弱期空仓；冷却1日/走弱2日。
  - 震荡期空仓（参考175）：震荡期无合格标的不买511010，保持空仓。
  - 买入得分双轨：排名宽区间[0,100]；买入阶段得分[0.2,2.5]+可选年化上限200%（仅买不卖）。
- V3.6 [2026/06/03]
  - 融合七星175阶段1：全时期均线结构硬过滤(价>MA10且MA5>MA10)、R²≥0.35、拉普拉斯/高斯 per-ETF 滤波。
  - 510300 震荡期切换(13:05检查)：正常期拉普拉斯、震荡期高斯；保留走弱期切池+511010防御+is_etf_tradable。
- V3.5 [2026/06/03]
  - 退出弱势期：废弃「≥3 指数站上 MA10 连续 2 日」；改为「≥3 指数 MA5、MA10 较前一日同时上升」；20 日强制退出不变。
  - 盘中停牌防护：is_etf_tradable（paused + 本交易时段无成交）；目标选择 / 13:10 缓存复检 / 下单前拦截；不可买则排名顺延。
  - 策略文件为 .py；QMT 代码见独立文件 `七星超级加175v311V3.15-QMT.py`。
- V3.4 [2026/05/31]
  - 退出弱势期条件调整（聚宽 + QMT 同步）：
    * 原「当日 ≥3 指数站上 MA10 即恢复」改为「≥3 指数站上 MA10 连续 2 个交易日」方可恢复。
    * 走弱期满 20 日强制退出逻辑不变。
- V3.3 [2026/05/31]
  - 弱势期第二路条件调整（聚宽 + QMT 同步）：
    * 移除 MA10 近 5 日斜率向下判断。
    * 改为 ≥3 个指数满足「MA5/MA10 死叉」或「MA5 < MA10」。
    * 第一路「≥3 指数现价 < MA10」保留；退出弱势逻辑不变。
- V3.2 [2026/05/31]
  - 弱势期判断升级（聚宽 + QMT 同步）：
    * 监测指数由 4 个扩充为 6 个：在原有沪深300、深证综指、创业板指、中证A500 基础上，新增上证指数(000001)、深证成指(399001)。
    * 进入弱势期条件（满足其一即可）：① ≥3 个指数当前价低于各自 10 日均线；② ≥3 个指数 10 日均线近 5 日斜率向下。
- V3 [2026/05/30]
  - 修复「同日先卖后买同一标的」的 bug：
    * 根因：卖出模块只看 ranked[:N] 前 N 名（无过滤），买入模块遍历全部排名并应用多种过滤（盈利保护/日内回撤），前 N 名被过滤后排名靠后的 ETF 会被"提拔"到目标列表，导致 13:09 卖出的 ETF 在 13:10 又被买入。
    * 修复：提取统一函数 select_target_etfs_from_rankings()，卖出与买入共用完全相同的目标选择逻辑，保证同一交易日内两者的目标集合严格一致。
    * 补充：13:09 卖出时将最终目标列表写入 g.target_etfs_cache，13:10 买入直接复用，避免日内回撤等时间敏感过滤在 1 分钟内变化导致买卖目标再次分歧。
- V2 [2026/05/29]
  - 卖出分类优化：区分"有害卖出"（回撤/盈利保护）和"中性卖出"（排名轮动/溢价率）
    * 新增 g.drawdown_selled_today 记录有害卖出标的，禁止日内买回；中性卖出（轮动/溢价率）不禁止日内买回
  - 日内回撤守卫（get_intraday_drawdown_ratio）：买入过滤 + 13:09 持仓强制卖 + 分钟检查共用；原 check_intraday_drawdown_for_buy：
    * 任何买入候选标的需通过日内回撤检查（>2%回撤暂不买入），避免"接飞刀"
  - 防御ETF检查改用 drawdown_selled_today，仅在回撤/盈利保护卖出时禁止买回
"""

import numpy as np
import math
import datetime
import pandas as pd
import time
from functools import wraps
from jqdata import *

# ==================== 物理时间监控装饰器 ====================
def time_monitor(func_name=None):
    """时间监控装饰器，记录函数执行的真实物理时间"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_real = datetime.datetime.now()

            log.info(f"⏱️ [{func_name or func.__name__}] 开始执行 - 真实时间: {start_real.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                end_real = datetime.datetime.now()
                elapsed = end_time - start_time

                log.info(f"✅ [{func_name or func.__name__}] 执行完成 - 耗时: {elapsed*1000:.2f}ms | 真实时间: {end_real.strftime('%H:%M:%S')}")

                if elapsed > 0.95:
                    log.warning(f"⚠️ [{func_name or func.__name__}] 执行耗时过长: {elapsed*1000:.2f}ms")

                return result
            except Exception as e:
                end_time = time.time()
                elapsed = end_time - start_time
                log.error(f"❌ [{func_name or func.__name__}] 执行异常 - 耗时: {elapsed*1000:.2f}ms | 错误: {str(e)[:100]}")
                raise
        return wrapper
    return decorator

# ==================== 辅助函数：获取真实时间 ====================
def get_real_time():
    return datetime.datetime.now().strftime('%H:%M:%S')

# ==================== 初始化模块 ====================
def initialize(context):
    """
    初始化函数：设置交易参数、ETF池、核心参数、调度任务
    """
    g.strategy_version = 'V3.15'
    g.strategy_id = 'QX3.15'
    g.strategy_log_marker = '[QX3.15]'

    # ---------- 交易设置 ----------
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0005,
            close_commission=0.0005,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    set_benchmark("000300.XSHG")

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("🚀 ========== 策略初始化开始 ==========")

    # ---------- ETF池 ----------
    g.etf_pool_bak = [
        "518880.XSHG",   # 黄金ETF
        "159985.XSHE",   # 豆粕ETF
        "501018.XSHG",   # 南方原油
        "161226.XSHE",   # 白银LOF
        "513100.XSHG",   # 纳指ETF
        "159915.XSHE",   # 创业板ETF
        "511220.XSHG",   # 城投债ETF
    ]

    # ==========按类别分类ETF ==========
    # 海外ETF（走弱期可交易）
    g.overseas_etf_pool = [
        "513100.XSHG",  # 纳指ETF
        "159509.XSHE",  # 纳指科技ETF
        "513290.XSHG",  # 纳指生物ETF
        "513500.XSHG",  # 标普500ETF
        "159529.XSHE",  # 标普消费
        "513400.XSHG",  # 道琼斯ETF
        "513520.XSHG",  # 日经225ETF
        "513030.XSHG",  # 德国30ETF
        "513080.XSHG",  # 法国ETF
        "513310.XSHG",  # 中韩半导体ETF
        "513730.XSHG",  # 东南亚ETF
        "159792.XSHE",  # 港股互联ETF
        "513130.XSHG",  # 恒生科技
        "513050.XSHG",  # 中概互联网ETF
        "159920.XSHE",  # 恒生ETF
        "513690.XSHG",  # 港股红利
        # 债券ETF
        "511380.XSHG",  # 可转债ETF
        "511010.XSHG",  # 国债ETF
        "511220.XSHG",  # 城投债ETF
    ]

    # 商品ETF（走弱期可交易）
    g.commodity_etf_pool = [
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色金属ETF
        "159985.XSHE",  # 豆粕ETF
        "501018.XSHG",  # 南方原油
        '161226.XSHE',  # 白银LOF
        "159981.XSHE",  # 能源化工ETF
        "512400.XSHG",  # 工业有色ETF
    ]

    # A股ETF（走弱期回避）
    g.domestic_etf_pool = [
        # 指数ETF
        "510300.XSHG",  # 沪深300ETF
        "510500.XSHG",  # 中证500ETF
        "510050.XSHG",  # 上证50ETF
        "510210.XSHG",  # 上证ETF
        "159915.XSHE",  # 创业板ETF
        "588080.XSHG",  # 科创50
        "512100.XSHG",  # 中证1000ETF
        "563360.XSHG",  # A500-ETF
        "563300.XSHG",  # 中证2000ETF
        # 风格ETF
        "512890.XSHG",  # 红利低波ETF
        "159967.XSHE",  # 创业板成长ETF
        "588020.XSHG",  # 科创成长ETF
        "512040.XSHG",  # 价值ETF
        "159201.XSHE",  # 自由现金流ETF
        # 行业板块ETF
        "515790.XSHG",   # 光伏ETF
        "563230.XSHG",   # 卫星ETF
        "515880.XSHG",   # 通信ETF
        "512660.XSHG",   # 军工ETF
        "561380.XSHG",   # 电网设备ETF
        "159667.XSHE",   # 工业母机ETF
        "159559.XSHE",   # 机器人ETF
        "159819.XSHE",   # 人工智能ETF
        "159381.XSHE",   # 创业板人工智能ETF
        "159732.XSHE",   # 消费电子ETF
        "159995.XSHE",   # 芯片ETF
        "512220.XSHG",   # TMT(科技传媒通信150）ETF
    ]

    # 完整ETF池（初始化时合并）
    g.etf_pool = g.overseas_etf_pool + g.commodity_etf_pool + g.domestic_etf_pool

    # ---------- 核心参数 ----------
    g.lookback_days = 25               # 动量计算周期
    g.holdings_num = 1                 # 候选数量
    g.defensive_etf = '511010.XSHG'    # 避险资产：10年国债ETF（enable_defensive_etf 关时不买入）
    g.enable_defensive_etf = False     # False=无标的时空仓；True=兜底买入 511010
    g.min_money = 5000                 # 最小交易金额

    # ---------- 盈利保护参数 ----------
    g.enable_profit_protection = True                      # 盈利保护开关
    g.profit_protection_lookback = 1                       # 盈利保护回看周期（天）
    g.profit_protection_threshold = 0.05                   # 盈利保护回撤阈值（5%）

    # 盈利保护检查时间点
    g.profit_protection_check_times = ['11:00']


    g.loss = 0.97                      # 近3日单日跌幅阈值（排除）

    # ---------- 得分区间（排名宽 / 买入窄）----------
    g.rank_min_score = 0               # 排名入围下限
    g.rank_max_score = 10000.0         # 排名入围上限（实质取消，防误杀超高动量）
    g.min_score_threshold = 0          # 兼容别名 → rank_min_score
    g.max_score_threshold = 10000.0    # 兼容别名 → rank_max_score
    g.enable_buy_score_band = True     # 买入阶段得分区间开关（仅下限，不设上限）
    g.buy_min_score = 0.20             # 买入得分下限（挡极弱标的）
    g.buy_max_score = 100.0            # 买入得分上限（与排名同宽，不挡高分主线）
    g.enable_buy_annualized_cap = False  # 关闭年化上限
    g.buy_max_annualized = 5.0         # 备用（默认不启用）
    g.enable_cooldown_strict_buy_band = False  # 关闭冷却后严买入带（V3.8实测误杀高分）
    g.buy_max_score_cooldown = 2.50
    g.enable_buy_annualized_cap_cooldown = False
    g.buy_max_annualized_cooldown = 2.0
    g.harmful_sell_strict_extra_days = 0

    # ---------- 有害卖出冷却（V3.11：走弱期仅挡QDII追高，商品继续轮动）----------
    g.enable_harmful_sell_guard = True
    g.harmful_sell_last_date = None
    g.harmful_sell_last_security = None
    g.harmful_sell_cooldown_days = 0       # 正常期不暂停轮动（仅 drawdown_selled_today 禁同日买回）
    g.harmful_sell_cooldown_weak_days = 2  # 走弱期冷却交易日
    g.harmful_sell_mode_normal = 'rotation'   # 正常期：继续轮动
    g.harmful_sell_mode_weak = 'qdii_guard'   # 走弱期：仅挡海外追高，不全盘空仓

    # ---------- 走弱期有害卖后 QDII 精准防追高（V3.11）----------
    g.enable_weak_qdii_guard = True
    g.overseas_proxy_pool = [
        '159509.XSHE', '513500.XSHG', '513520.XSHG', '513400.XSHG',
        '513290.XSHG', '513030.XSHG',
        '513130.XSHG', '513050.XSHG', '159920.XSHE',
    ]
    g.correlation_lookback = 20
    g.correlation_max = 0.88

    # ---------- 海外弱判断（V3.12：独立于 A 股弱）----------
    g.enable_overseas_regime_switch = True
    g.enable_overseas_weak_shield = True
    g.is_overseas_weak = False
    g.overseas_weak_counter = 0
    g.overseas_weak_max_days = 20
    g.overseas_weak_enter_count = 2          # ≥2/4 代理走弱即进入
    g.overseas_weak_exit_count = 2           # 日频退出：≥2/4 MA5/10 回升
    g.overseas_weak_intraday_exit_count = 3  # 盘中退出：≥3/4（严于进入，防边界抖动）
    g._regime_trade_refresh_key = None       # 盘中双风险复检去重（每分钟一次）
    g.overseas_regime_proxies = {
        '纳指科技': '159509.XSHE',
        '标普500': '513500.XSHG',
        '道琼斯': '513400.XSHG',
        '日经': '513520.XSHG',
    }
    g.overseas_bond_etfs = {
        '511380.XSHG', '511010.XSHG', '511220.XSHG',
    }

    # ---------- 海外弱时商品替代门槛（非默认兜底）----------
    g.enable_overseas_weak_commodity_gate = True
    g.buy_min_score_overseas_weak = 0.50
    g.enable_overseas_weak_cash = False      # True=海外弱无商品时空仓（与 enable_defensive_etf 独立）

    # ---------- 走弱期轮动卖海外冷却（V3.12，补 6/3）----------
    g.enable_overseas_rotation_guard = True
    g.overseas_rotation_sell_last_date = None
    g.overseas_rotation_sell_last_security = None
    g.overseas_rotation_cooldown_days = 1

    # ---------- 震荡期空仓（参考175）----------
    g.enable_range_bound_cash = True

    # ---------- 成交量过滤 ----------
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1          # 年化收益>100%时启用放量过滤

    # ---------- 短期动量过滤 ----------
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0

    # ---------- 溢价率过滤 ----------
    g.enable_premium_filter = True      # 是否启用溢价率过滤
    g.premium_threshold = 0.20          # 溢价率阈值（20%）


    # ---------- R² 过滤（参考七星175）----------
    g.enable_r2_filter = True
    g.r2_threshold = 0.35

    # ---------- 均线趋势结构硬过滤 ----------
    g.enable_trend_structure_filter = True
    g.trend_ma_period = 10
    g.trend_require_price_above_ma = True
    g.trend_require_ma5_above_ma10 = True

    # ---------- 震荡期 + 拉普拉斯/高斯（参考七星175/172）----------
    g.enable_range_bound_mode = True
    g.current_filter = '正常期'
    g.risk_state = '正常期'
    g.lookback_high_low_days = 20
    g.risk_benchmark = '510300.XSHG'
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.001
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002
    g.enable_bias_trigger = True
    g.bias_threshold = 0.10
    g.ma_period = 20
    g.enable_rsi_trigger = True
    g.rsi_overbought = 75
    g.rsi_pullback = 60
    g.previous_rsi = None
    g.enable_stop_loss_trigger = False
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    g.enable_low_point_rise_trigger = True
    g.low_point_rise_threshold = 0.03
    g.enable_stable_signal_trigger = True
    g.drawdown_recovery = 0.03
    g.max_range_bound_days = 15
    g.stable_days = 0
    g.filter_switch_cooldown = 2
    g.last_switch_date = None
    g.range_bound_start_date = None
    g.range_bound_days_count = 0
    g.previous_drawdown = None

    # ========== 分钟级当日回撤保护（V2.1：开关自动跟随行情状态） ==========
    g.intraday_drawdown_threshold = 0.02            # 当日回撤阈值（2%）
    g.enable_holding_prev_close_drawdown = True     # 持仓兼看昨收→现价回撤（补跳空低开）
    g.holding_profit_skip_minute_pct = 0.10       # 浮盈≥10%：分钟守卫不卖（防盈利商品早盘误杀）
    g.holding_profit_skip_prev_close_pct = 0.10   # 浮盈≥10%：13:09 不用昨收跳空触发卖
    # 注意：不再使用 g.enable_intraday_drawdown，改为在 handle_data 中动态判断
    # ================================================================

    # ==========  A股行情判断 ==========
    g.enable_regime_switch = True                    # 行情判断开关
    g.weak_period_ma_lookback = 10                   # 10日均线
    g.weak_period_max_days = 20                      # 走弱期最长持续20个交易日
    g.is_a_share_weak = False                        # 当前是否走弱期
    g.a_share_weak_daily_lock = False                # 09:40日频走弱后当日禁止盘中假恢复
    g.weak_period_counter = 0                        # 走弱期天数计数器
    g.a_share_weak_enter_count = 3                   # ≥3/6 指数走弱进入 A 股弱
    g.a_share_weak_exit_count = 3                    # 日频退出：≥3/6 MA5/10 回升
    g.a_share_intraday_exit_count = 4                # 盘中退出：≥4/6（严于进入，防边界抖动）
    # g.weak_exit_above_streak = 0                     # ≥3指数站上MA10的连续交易日数（满2日退出）
    # g.weak_exit_above_days = 2                       # 退出弱势：站上MA10须连续满足的天数
    # ==========  独立手动开关 ==========
    g.enable_avoid_a_share = True                    # 走弱期回避A股开关（关闭则走弱期不回避A股）
    g.enable_intraday_drawdown = True                # 分钟级回撤保护独立开关（关闭则不触发）
    # ==========================================
    g.regime_indexes = {                             # 监测指数（V3.3：6指数 + 价破线/MA5死叉双条件）
        '上证指数': '000001.XSHG',
        '沪深300': '000300.XSHG',
        '深证成指': '399001.XSHE',
        '深证综指': '399101.XSHE',
        '创业板指': '399006.XSHE',
        '中证A500': '000510.XSHG',
    }
    # ============================================

    # ---------- 运行时变量 ----------
    g.rankings_cache = {'date': None, 'data': None}   # 排名缓存
    g.target_etfs_cache = {'date': None, 'data': None}  # 13:09 目标ETF缓存，供13:10买入复用
    g.drawdown_selled_today = set()                    # 当日因回撤/盈利保护卖出的标的（禁止日内买回）

    # 盘后总结需要的变量
    g.buy_date = {}                                    # 记录买入日期
    g.trade_log = {'sell_records': []}                 # 记录当日卖出

    # ---------- 交易调度 ----------
    run_daily(check_positions, time='09:10')
    run_daily(regime_check, time='09:40')              # 行情判断
    run_daily(check_range_bound, time='13:05')         # 震荡期/滤波器切换
    run_daily(etf_sell_trade, time='13:09')
    run_daily(etf_buy_trade, time='13:10')
    run_daily(reset_range_bound_daily, time='15:10')
    run_daily(daily_summary_report, time='15:05')      # 盘后总结

    # 动态注册盈利保护检查时间点
    for check_time in g.profit_protection_check_times:
        run_daily(profit_protection_check, time=check_time)
        log.info(f"📅 已注册盈利保护检查时间：{check_time}")

    # V2.2 日志
    if g.enable_regime_switch:
        log.info(f"🌍 A股行情判断已启用，走弱期最长{g.weak_period_max_days}日")
        if g.enable_avoid_a_share:
            log.info(f"🔄 走弱期回避A股开关：ON（走弱期自动回避A股ETF）")
        else:
            log.info(f"⚠️ 走弱期回避A股开关：OFF（走弱期仍交易A股ETF）")
        if g.enable_intraday_drawdown:
            log.info(f"🛡️ 分钟级回撤保护开关：ON（走弱期自动启用）")
        else:
            log.info(f"⭕ 分钟级回撤保护开关：OFF（不触发）")
    else:
        log.info("⚠️ A股行情判断未启用")

    log.info(f"📋 策略初始化完成：ETF池{len(g.etf_pool)}只（海外{len(g.overseas_etf_pool)}只+商品{len(g.commodity_etf_pool)}只+A股{len(g.domestic_etf_pool)}只）")
    log.info(f"📈 盈利保护：{'开' if g.enable_profit_protection else '关'}，回撤{g.profit_protection_threshold*100:.0f}%")
    log.info(
        f"💰 盈利仓回撤豁免：分钟不卖≥{g.holding_profit_skip_minute_pct*100:.0f}%浮盈；"
        f"13:09不卖昨收跳空≥{g.holding_profit_skip_prev_close_pct*100:.0f}%浮盈"
    )
    if g.enable_premium_filter:
        log.info(f"💰 溢价率过滤已启用，阈值：{g.premium_threshold*100:.0f}%")
    else:
        log.info("⚠️ 溢价率过滤未启用")

    marker = getattr(g, 'strategy_log_marker', '[QX3.14]')
    log.info(f"{marker} 策略版本：{g.strategy_version} | STRATEGY_ID={g.strategy_id}")
    log.info("%s 走弱有害卖=%s 弱QDII守卫=%s 海外弱屏蔽=%s 轮动卖挡海外=%s rank_max=%.0f" % (
        marker, g.harmful_sell_mode_weak,
        'on' if g.enable_weak_qdii_guard else 'off',
        'on' if g.enable_overseas_weak_shield else 'off',
        'on' if g.enable_overseas_rotation_guard else 'off',
        g.rank_max_score))
    if g.enable_overseas_regime_switch:
        log.info(
            "🌐 海外弱判断：ON 进入≥%d/4 日退≥%d/4 盘中退≥%d/4 商品替代下限=%.2f" % (
                g.overseas_weak_enter_count, g.overseas_weak_exit_count,
                g.overseas_weak_intraday_exit_count, g.buy_min_score_overseas_weak,
            )
        )
    log.info(
        "🛡️ 双风险规避定版：A股弱≥%d/6回避A股 | 海外弱屏蔽QDII | 双弱→仅商品 | 防御511010=%s"
        % (g.a_share_weak_enter_count, "开" if g.enable_defensive_etf else "关(空仓)")
    )
    log.info("📐 趋势过滤：均线=%s R2=%s 滤波=%s(%s)" % (
        "开" if g.enable_trend_structure_filter else "关",
        "开" if g.enable_r2_filter else "关",
        "开" if g.enable_range_bound_mode else "关", g.current_filter))
    log.info("📊 买入得分：%s 下限=%.2f 上限=%.0f(同排名) 年化上限=关 冷却严带=关" % (
        "开" if g.enable_buy_score_band else "关",
        g.buy_min_score, g.buy_max_score))
    log.info("🛡️ 有害卖出冷却：%s 正常=仅禁同日买回 走弱%d日空仓 震荡期空仓=%s" % (
        "开" if g.enable_harmful_sell_guard else "关",
        g.harmful_sell_cooldown_weak_days,
        "开" if g.enable_range_bound_cash else "关"))
    init_range_bound_status(context)
    log.info("🎉 ========== 策略初始化完成 ==========")


# ==================== 开盘检查模块 ====================
def check_positions(context):
    """每日开盘检查持仓状态"""

    # 日期标记
    log.info(f"\n{'='*22}🐂🧨🧨🧨🧨🧨{context.current_dt.strftime('%Y-%m-%d')}📌策略运行开始📌一路长红🧨🧨🧨🧨🧨🐂{'='*22}")

    g.drawdown_selled_today = set()                    # 清空当日回撤卖出缓存
    g.a_share_weak_daily_lock = False                    # 新交易日重置，09:40日频后再锁定
    g.target_etfs_cache = {'date': None, 'data': None}
    g.trade_log['sell_records'] = []
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")

# ====================  行情判断模块 ====================
def _index_live_price(context, code):
    """指数/ETF 盘中现价。"""
    try:
        price = get_current_data()[code].last_price
        if price is not None and price > 0:
            return price
    except Exception:
        pass
    return None


def compute_a_share_regime_signals(context, use_intraday=False):
    """统计 6 指数 A 股弱信号。盘中模式用现价对已完成日 K 的 MA。"""
    below_count, ma_weak_count, ma_recover_count = 0, 0, 0
    detail = []
    need_days = max(g.weak_period_ma_lookback, 5) + 1
    price_tag = '盘中' if use_intraday else '日频'

    for name, code in g.regime_indexes.items():
        try:
            df = attribute_history(code, need_days + 2, '1d', ['close'], skip_paused=False)
            if df.empty or len(df) < need_days + 1:
                continue
            closes = df['close'].values

            if use_intraday:
                live = _index_live_price(context, code)
                current_price = live if live is not None else closes[-1]
                base = closes[:-1] if len(closes) > need_days else closes
                if len(base) < g.weak_period_ma_lookback + 1:
                    continue
                ma10 = base[-g.weak_period_ma_lookback:].mean()
                ma5 = base[-5:].mean()
                ma10_prev = base[-(g.weak_period_ma_lookback + 1):-1].mean()
                ma5_prev = base[-6:-1].mean()
            else:
                current_price = closes[-1]
                ma10 = closes[-g.weak_period_ma_lookback:].mean()
                ma5 = closes[-5:].mean()
                ma10_prev = closes[-(g.weak_period_ma_lookback + 1):-1].mean()
                ma5_prev = closes[-6:-1].mean()

            if current_price < ma10:
                below_count += 1
                detail.append(f"{name}↓")
            else:
                detail.append(f"{name}↑")
            death_cross = ma5 < ma10 and ma5_prev >= ma10_prev
            if death_cross or ma5 < ma10:
                ma_weak_count += 1
                tag = '死叉' if death_cross else 'MA5<10'
                detail[-1] = detail[-1] + f'({tag})'
            if ma5 > ma5_prev and ma10 > ma10_prev:
                ma_recover_count += 1
                detail[-1] = detail[-1] + '(MA5↑10↑)'
        except Exception as e:
            log.warning(f"⚠️ 指数{name}获取失败: {e}")

    return below_count, ma_weak_count, ma_recover_count, detail, price_tag


def _log_a_share_transition(entering_weak):
    if entering_weak:
        if g.enable_avoid_a_share:
            log.info("   → 将回避A股ETF，仅交易海外+商品ETF")
        else:
            log.info("   → ⚠️ 回避A股开关已关闭，仍交易全市场ETF")
        if g.enable_intraday_drawdown:
            log.info(f"   → 🛡️ 分钟级回撤保护已启用（阈值{g.intraday_drawdown_threshold*100:.0f}%）")
        else:
            log.info("   → ⭕ 分钟级回撤保护已被独立开关关闭，不触发")
    else:
        if g.enable_avoid_a_share:
            log.info("   → 恢复交易A股ETF")
        else:
            log.info("   → 回避A股开关关闭，始终交易全市场")
        if g.enable_intraday_drawdown:
            log.info("   → 关闭分钟级回撤保护")
        else:
            log.info("   → 分钟级回撤保护独立开关已关闭，无变化")


def _apply_a_share_regime_state(context, below_count, ma_weak_count, ma_recover_count,
                                detail, mode='daily'):
    """应用 A 股弱状态迁移；边界 enter+exit 同时满足时维持原状。"""
    enter_n = g.a_share_weak_enter_count
    exit_n = (
        g.a_share_intraday_exit_count if mode == 'intraday'
        else g.a_share_weak_exit_count
    )
    would_enter = below_count >= enter_n or ma_weak_count >= enter_n
    would_exit = ma_recover_count >= exit_n
    old_state = g.is_a_share_weak
    prefix = '🕐盘中' if mode == 'intraday' else ''

    if not g.is_a_share_weak:
        if would_enter:
            g.is_a_share_weak = True
            g.weak_period_counter = 0
            reasons = []
            if below_count >= enter_n:
                reasons.append(f"价破线:{below_count}")
            if ma_weak_count >= enter_n:
                reasons.append(f"MA5弱:{ma_weak_count}")
            log.info(f"🔴 {prefix}进入走弱期 ({' + '.join(reasons)} {detail})")
            _log_a_share_transition(True)
    else:
        if mode == 'daily':
            g.weak_period_counter += 1
        if would_exit and would_enter:
            log.info(f"⚖️ {prefix}A股弱边界僵持(进/退同触)，维持走弱期 {detail}")
        elif would_exit:
            if mode == 'intraday' and g.a_share_weak_daily_lock:
                log.info(
                    f"🔒 {prefix}日频已确认走弱，忽略盘中假恢复，维持走弱期 {detail}"
                )
            else:
                g.is_a_share_weak = False
                g.weak_period_counter = 0
                log.info(f"🟢 {prefix}恢复正常期 (≥{exit_n}指数MA5/10↑:{ma_recover_count} {detail})")
                _log_a_share_transition(False)
        elif mode == 'daily' and g.weak_period_counter >= g.weak_period_max_days:
            g.is_a_share_weak = False
            g.weak_period_counter = 0
            log.info(f"⏰ 走弱期满{g.weak_period_max_days}日强制退出，恢复正常期")
            _log_a_share_transition(False)

    state_changed = old_state != g.is_a_share_weak
    if state_changed:
        g.rankings_cache = {'date': None, 'data': None}
        if mode == 'intraday':
            g.target_etfs_cache = {'date': None, 'data': None}
    return state_changed


def a_share_regime_check(context):
    """09:40 日频 A 股弱判断。"""
    if not g.enable_regime_switch:
        g.is_a_share_weak = False
        return False
    signals = compute_a_share_regime_signals(context, use_intraday=False)
    changed = _apply_a_share_regime_state(context, *signals[:4], mode='daily')
    ma_recover = signals[2]
    if g.enable_regime_switch:
        current_status = '🔴走弱期' if g.is_a_share_weak else '🟢正常期'
        avoid_status = (
            '(回避A股)' if (g.is_a_share_weak and g.enable_avoid_a_share)
            else ('(不回避A股)' if g.is_a_share_weak else '')
        )
        drawdown_status = (
            '🛡️启用' if (g.is_a_share_weak and g.enable_intraday_drawdown)
            else '⭕关闭'
        )
        recover_info = (
            f" MA5/10↑:{ma_recover}/{len(g.regime_indexes)}"
            if g.is_a_share_weak else ""
        )
        log.info(
            f"📊 当前状态：{current_status}{avoid_status} "
            f"计数:{g.weak_period_counter}/{g.weak_period_max_days}{recover_info}"
        )
        log.info(f"📊 分钟级回撤保护：{drawdown_status}（阈值{g.intraday_drawdown_threshold*100:.0f}%）")
    g.a_share_weak_daily_lock = bool(g.is_a_share_weak)
    return changed


def regime_check(context):
    """每日 9:40 双风险日频定调：A 股弱 + 海外弱。"""
    log.info("🌍 ========== 行情判断开始（双风险日频）==========")
    overseas_regime_check(context)
    a_share_regime_check(context)
    log.info("🌍 ========== 行情判断完成 ==========")


def _overseas_proxy_live_price(context, code):
    """盘中海外代理现价；无效时返回 None。"""
    try:
        price = get_current_data()[code].last_price
        if price is not None and price > 0:
            return price
    except Exception:
        pass
    return None


def compute_overseas_regime_signals(context, use_intraday=False):
    """统计 4 代理海外弱信号。盘中模式用现价对已完成日 K 的 MA。"""
    below_count, ma_weak_count, ma_recover_count = 0, 0, 0
    detail = []
    need_days = max(g.weak_period_ma_lookback, 5) + 1
    price_tag = '盘中' if use_intraday else '日频'

    for name, code in g.overseas_regime_proxies.items():
        try:
            df = attribute_history(code, need_days + 2, '1d', ['close'], skip_paused=False)
            if df.empty or len(df) < need_days + 1:
                continue
            closes = df['close'].values

            if use_intraday:
                live = _overseas_proxy_live_price(context, code)
                current_price = live if live is not None else closes[-1]
                base = closes[:-1] if len(closes) > need_days else closes
                if len(base) < g.weak_period_ma_lookback + 1:
                    continue
                ma10 = base[-g.weak_period_ma_lookback:].mean()
                ma5 = base[-5:].mean()
                ma10_prev = base[-(g.weak_period_ma_lookback + 1):-1].mean()
                ma5_prev = base[-6:-1].mean()
            else:
                current_price = closes[-1]
                ma10 = closes[-g.weak_period_ma_lookback:].mean()
                ma5 = closes[-5:].mean()
                ma10_prev = closes[-(g.weak_period_ma_lookback + 1):-1].mean()
                ma5_prev = closes[-6:-1].mean()

            if current_price < ma10:
                below_count += 1
                detail.append(f"{name}↓")
            else:
                detail.append(f"{name}↑")
            death_cross = ma5 < ma10 and ma5_prev >= ma10_prev
            if death_cross or ma5 < ma10:
                ma_weak_count += 1
                tag = '死叉' if death_cross else 'MA5<10'
                detail[-1] = detail[-1] + f'({tag})'
            if ma5 > ma5_prev and ma10 > ma10_prev:
                ma_recover_count += 1
                detail[-1] = detail[-1] + '(MA5↑10↑)'
        except Exception as e:
            log.warning(f"⚠️ 海外代理{name}获取失败: {e}")

    return below_count, ma_weak_count, ma_recover_count, detail, price_tag


def _apply_overseas_regime_state(context, below_count, ma_weak_count, ma_recover_count,
                                 detail, mode='daily'):
    """应用海外弱状态迁移；边界 enter+exit 同时满足时维持原状（迟滞）。"""
    enter_n = g.overseas_weak_enter_count
    if mode == 'intraday':
        exit_n = g.overseas_weak_intraday_exit_count
    else:
        exit_n = g.overseas_weak_exit_count

    would_enter = below_count >= enter_n or ma_weak_count >= enter_n
    would_exit = ma_recover_count >= exit_n
    old_state = g.is_overseas_weak
    prefix = '🕐盘中' if mode == 'intraday' else ''

    if not g.is_overseas_weak:
        if would_enter:
            g.is_overseas_weak = True
            g.overseas_weak_counter = 0
            reasons = []
            if below_count >= enter_n:
                reasons.append(f"价破线:{below_count}")
            if ma_weak_count >= enter_n:
                reasons.append(f"MA5弱:{ma_weak_count}")
            log.info(f"🔴 {prefix}进入海外弱 ({' + '.join(reasons)} {detail})")
    else:
        if mode == 'daily':
            g.overseas_weak_counter += 1
        if would_exit and would_enter:
            log.info(f"⚖️ {prefix}海外弱边界僵持(进/退同触)，维持海外弱 {detail}")
        elif would_exit:
            g.is_overseas_weak = False
            g.overseas_weak_counter = 0
            log.info(f"🟢 {prefix}海外弱恢复 (≥{exit_n}代理MA5/10↑:{ma_recover_count} {detail})")
        elif mode == 'daily' and g.overseas_weak_counter >= g.overseas_weak_max_days:
            g.is_overseas_weak = False
            g.overseas_weak_counter = 0
            log.info(f"⏰ 海外弱满{g.overseas_weak_max_days}日强制退出 {detail}")

    state_changed = old_state != g.is_overseas_weak
    if state_changed:
        g.rankings_cache = {'date': None, 'data': None}
        if mode == 'intraday':
            g.target_etfs_cache = {'date': None, 'data': None}
    if state_changed or g.is_overseas_weak:
        ostatus = '🔴海外弱' if g.is_overseas_weak else '🟢海外正常'
        log.info(f"🌐 海外状态：{ostatus} 计数:{g.overseas_weak_counter}/{g.overseas_weak_max_days}")
    return state_changed


def overseas_regime_check(context):
    """09:40 日频海外弱判断（独立于 A 股弱）。"""
    if not g.enable_overseas_regime_switch:
        g.is_overseas_weak = False
        return False
    signals = compute_overseas_regime_signals(context, use_intraday=False)
    return _apply_overseas_regime_state(context, *signals[:4], mode='daily')


def refresh_regime_for_trade(context):
    """13:09/13:10 双风险盘中复检（A股弱+海外弱）；同一分钟只执行一次。"""
    key = (context.current_dt.date(), context.current_dt.strftime('%H%M'))
    if getattr(g, '_regime_trade_refresh_key', None) == key:
        return False
    g._regime_trade_refresh_key = key
    changed = False
    if g.enable_overseas_regime_switch:
        signals = compute_overseas_regime_signals(context, use_intraday=True)
        below, ma_weak, ma_recover, detail, price_tag = signals
        log.info(f"🕐 盘中海外弱复检({price_tag}) 价破:{below} MA弱:{ma_weak} MA回升:{ma_recover}")
        changed |= _apply_overseas_regime_state(
            context, below, ma_weak, ma_recover, detail, mode='intraday'
        )
    if g.enable_regime_switch:
        signals = compute_a_share_regime_signals(context, use_intraday=True)
        below, ma_weak, ma_recover, detail, price_tag = signals
        log.info(f"🕐 盘中A股弱复检({price_tag}) 价破:{below} MA弱:{ma_weak} MA回升:{ma_recover}")
        changed |= _apply_a_share_regime_state(
            context, below, ma_weak, ma_recover, detail, mode='intraday'
        )
    return changed


def refresh_overseas_regime_for_trade(context):
    """兼容别名 → 双风险盘中复检。"""
    return refresh_regime_for_trade(context)


def is_overseas_qdii(etf):
    """海外池中的 QDII 权益类（不含债券）。"""
    bond_set = getattr(g, 'overseas_bond_etfs', set())
    return etf in g.overseas_etf_pool and etf not in bond_set


def is_intraday_drawdown_enabled():
    """判断分钟级回撤保护是否启用
    V2.2: 优先判断独立开关，关闭则不触发；开启则走弱期自动启用"""
    # 独立开关关闭 → 不触发
    if not g.enable_intraday_drawdown:
        return False
    # 行情判断未启用 → 不触发
    if not g.enable_regime_switch:
        return False
    # 走弱期自动启用
    return g.is_a_share_weak


def get_active_etf_pool():
    """根据 A 股弱 × 海外弱 四格矩阵返回可排名池（V3.12）。"""
    overseas_shield = (
        g.enable_overseas_weak_shield
        and g.enable_overseas_regime_switch
        and g.is_overseas_weak
    )

    if not g.enable_avoid_a_share:
        if overseas_shield and g.is_a_share_weak:
            active_pool = list(g.commodity_etf_pool)
            log.info(f"📊 【A弱+海外弱】仅商品池({len(active_pool)}只) [回避A股关]")
        elif overseas_shield:
            active_pool = list(g.domestic_etf_pool) + list(g.commodity_etf_pool)
            log.info(f"📊 【海外弱】A股+商品池({len(active_pool)}只) [回避A股关]")
        else:
            active_pool = list(g.etf_pool)
            log.info(f"📊 【强制】A股回避关，完整池({len(active_pool)}只)")
        return active_pool

    if g.is_a_share_weak:
        if overseas_shield:
            active_pool = list(g.commodity_etf_pool)
            log.info(f"📊 【A弱+海外弱】仅商品池({len(active_pool)}只)")
        else:
            active_pool = list(g.overseas_etf_pool) + list(g.commodity_etf_pool)
            log.info(f"📊 【走弱期】海外+商品池({len(active_pool)}只)")
    elif overseas_shield:
        active_pool = list(g.domestic_etf_pool) + list(g.commodity_etf_pool)
        log.info(f"📊 【海外弱】A股+商品池({len(active_pool)}只)")
    else:
        active_pool = list(g.etf_pool)
        log.info(f"📊 【正常期】完整池({len(active_pool)}只)")
    return active_pool


# ==================== 分钟级回测入口：每分钟执行一次 ====================
def handle_data(context, data):
    """当回测/实盘频率设为'分钟'时，此函数每分钟自动调用一次。
    V2.1: 只在走弱期执行回撤检查，正常期跳过
    V2.2: 受独立开关控制"""
    # V2.2: 动态判断是否启用（独立开关 + 走弱期）
    if not is_intraday_drawdown_enabled():
        return

    # 9:46 之后才执行检查
    current_time = context.current_dt.strftime('%H:%M')
    if current_time < '09:46':
        return

    intraday_drawdown_check(context)


# ==================== 分钟级当日回撤检查函数 ====================
def intraday_drawdown_check(context):
    """每分钟执行一次，检查所有持仓从当日盘中最高点的回撤。
    V2.1: 此函数仅在走弱期被调用
    V2.2: 受独立开关控制"""
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount == 0:
            continue
        # 跳过当日买入的ETF（避免刚买入就被日内回撤保护卖出）
        if g.buy_date.get(sec) == context.current_dt.date():
            continue

        try:
            drawdown, detail, threshold = get_holding_drawdown_for_sell(
                sec, context, source='minute'
            )
            if (
                drawdown is not None
                and threshold is not None
                and drawdown >= threshold
            ):
                execute_intraday_drawdown_sell(
                    context, sec, drawdown, source='分钟级',
                    detail=detail, threshold=threshold
                )
        except Exception as e:
            log.debug(f"分钟级回撤检查异常 {sec}: {e}")


# ==================== 盈利保护独立检查函数 ====================
@time_monitor(func_name="盈利保护检查")
def profit_protection_check(context):
    """独立执行的盈利保护检查函数"""
    if not g.enable_profit_protection:
        log.debug("盈利保护模块已关闭，跳过检查")
        return

    log.info("🛡️ ========== 盈利保护检查开始 ==========")
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if check_profit_protection(sec, context):
                if smart_order_target_value(sec, 0, context):
                    log.info(f"🛡️ 盈利保护卖出：{sec} {get_name(sec)}")
                    g.drawdown_selled_today.add(sec)
                    mark_harmful_sell(context, sec)
                    if getattr(g, 'enable_stop_loss_trigger', False):
                        g.stop_loss_triggered_today = True
                        g.stop_loss_triggered_date = context.current_dt.date()
    log.info("🛡️ ========== 盈利保护检查完成 ==========")


# ==================== 盈利保护检查函数（核心逻辑） ====================
def check_profit_protection(security, context, lookback=None, threshold=None):
    """检查是否触发盈利保护（从最近N日最高点回撤超过阈值）"""
    if not g.enable_profit_protection:
        return False

    lookback = lookback or g.profit_protection_lookback
    threshold = threshold or g.profit_protection_threshold

    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        return False

    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price

    if current_price <= max_high * (1 - threshold):
        log.info(f"🔻 盈利保护触发 {security} 回撤{(1-current_price/max_high)*100:.2f}% > {threshold*100:.0f}%")
        return True
    return False


# ==================== 溢价率获取函数 ====================
def get_premium_rate(code, date):
    """获取指定交易日的溢价率，自动向前寻找最近有净值的交易日"""
    price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
    if price_data.empty:
        log.debug(f"⚠️ {date} {code} 无交易价格数据")
        return None, None, None
    price = price_data['close'].iloc[0]

    net_value = None
    use_date = date
    max_search_days = 3
    found = False

    for _ in range(max_search_days):
        net_data = get_extras('unit_net_value', code, start_date=use_date, end_date=use_date, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            found = True
            break

        try:
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == use_date
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                found = True
                break
        except:
            pass

        trade_days = get_trade_days(end_date=use_date, count=2)
        if len(trade_days) < 2:
            break
        use_date = trade_days[0]

    if not found or net_value is None:
        log.debug(f"⚠️ {code} 在{date}无净值数据")
        return None, None, None

    if use_date != date:
        log.debug(f"🔍 {code} 使用最近净值日期 {use_date}")

    premium_rate = (price - net_value) / net_value
    return premium_rate, price, net_value



# ==================== 震荡期机制（拉普拉斯/高斯，参考七星175）====================
def calculate_rsi(close, period=14):
    try:
        if len(close) < period + 1:
            return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    except Exception:
        return None


def laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def gaussian_filter_last_two(price, sigma=1.2):
    n = len(price)
    if n < 2:
        return 0, 0
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


def get_risk_benchmark_state(context):
    required_days = max(g.ma_period, g.lookback_high_low_days)
    lookback = required_days + 30
    end_date = getattr(context, 'previous_date', None)
    if end_date is None:
        return None
    df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,
                   frequency='daily', fields=['close', 'high', 'low'], panel=False)
    if df is None or len(df) < required_days:
        return None
    daily_close = df['close'].values.astype(float)
    daily_high = df['high'].values.astype(float)
    daily_low = df['low'].values.astype(float)
    current_price = float(daily_close[-1])
    intraday_high = current_price
    intraday_low = current_price
    data_source = '昨日日线'
    try:
        today = context.current_dt.date()
        minute_df = get_price(
            g.risk_benchmark, start_date=today, end_date=context.current_dt,
            frequency='1m', fields=['close', 'high', 'low'], panel=False, fill_paused=False
        )
        if minute_df is not None and not minute_df.empty:
            minute_close = minute_df['close'].dropna()
            minute_high = minute_df['high'].dropna()
            minute_low = minute_df['low'].dropna()
            if not minute_close.empty:
                current_price = float(minute_close.iloc[-1])
                intraday_high = float(minute_high.max()) if not minute_high.empty else current_price
                intraday_low = float(minute_low.min()) if not minute_low.empty else current_price
                data_source = '当日盘中'
    except Exception:
        pass
    if current_price <= 0:
        try:
            live_price = get_current_data()[g.risk_benchmark].last_price
            if live_price is not None and live_price > 0:
                current_price = float(live_price)
                intraday_high = max(intraday_high, current_price)
                intraday_low = min(intraday_low, current_price)
                data_source = '实时快照'
        except Exception:
            current_price = float(daily_close[-1])
    close_series = np.append(daily_close, current_price)
    high_series = np.append(daily_high, max(intraday_high, current_price))
    low_series = np.append(daily_low, min(intraday_low, current_price))
    recent_high = np.max(high_series[-g.lookback_high_low_days:])
    recent_low = np.min(low_series[-g.lookback_high_low_days:])
    ma = np.mean(close_series[-g.ma_period:])
    current_rsi = calculate_rsi(close_series, period=14)
    previous_rsi = calculate_rsi(daily_close, period=14)
    return {
        'close_series': close_series,
        'high_series': high_series,
        'low_series': low_series,
        'current_price': current_price,
        'recent_high': recent_high,
        'recent_low': recent_low,
        'ma': ma,
        'current_rsi': current_rsi,
        'previous_rsi': previous_rsi,
        'data_source': data_source,
    }


def is_fresh_stop_loss_signal(context):
    signal_date = getattr(g, 'stop_loss_triggered_date', None)
    if signal_date is None:
        return False
    today = context.current_dt.date()
    previous_date = getattr(context, 'previous_date', None)
    if signal_date == today:
        return True
    if previous_date is not None and signal_date == previous_date:
        return True
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    return False


def init_range_bound_status(context):
    if not g.enable_range_bound_mode:
        return
    log.info("【首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None:
            return
        end_date = context.previous_date
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        recent_high = np.max(high[-g.lookback_high_low_days:]) if len(close) >= g.lookback_high_low_days else np.max(high)
        ma = np.mean(close[-g.ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        current_rsi = calculate_rsi(close, period=14)
        should_enter = False
        signals = []
        if g.enable_bias_trigger and bias > g.bias_threshold:
            should_enter = True
            signals.append(f"乖离率{bias:.2%}")
        if g.enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback:
                should_enter = True
                signals.append(f"RSI回落{prev_rsi:.1f}->{current_rsi:.1f}")
        if should_enter:
            g.current_filter = '震荡期'
            g.risk_state = '震荡期'
            g.range_bound_start_date = end_date
            log.info(f"【首次运行】初始化进入震荡期: {'; '.join(signals)}")
        else:
            g.current_filter = '正常期'
            g.risk_state = '正常期'
            g.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            g.previous_rsi = current_rsi
            log.info(f"【首次运行】初始状态: 正常期(拉普拉斯)")
    except Exception as e:
        log.warning(f"【首次运行】震荡期初始化异常: {e}")


def check_and_exit_range_bound_mode(context):
    if not g.enable_range_bound_mode or g.current_filter != '震荡期':
        return
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is None:
            return
        close = benchmark_state['close_series']
        current_price = benchmark_state['current_price']
        recent_high = benchmark_state['recent_high']
        recent_low = benchmark_state['recent_low']
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        recovery_signals = []
        ma = benchmark_state['ma']
        current_rsi = benchmark_state['current_rsi']
        if g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold:
            recovery_signals.append(f"从低点涨{rise_from_low:.2%}")
        if g.enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("站上均线")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                recovery_signals.append("回撤收窄")
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                recovery_signals.append("RSI回升")
            if current_drawdown < g.drawdown_recovery:
                g.stable_days += 1
            else:
                g.stable_days = 0
        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi
        range_bound_days = 0
        if g.range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
        low_point_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_condition = False
        if g.enable_stable_signal_trigger:
            stable_condition = current_drawdown < g.drawdown_recovery and len(recovery_signals) >= 2 and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days
        if low_point_condition or stable_condition or force_condition:
            can_switch = True
            if g.last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
                if len(trade_days) - 1 < g.filter_switch_cooldown:
                    can_switch = False
            if can_switch:
                g.current_filter = '正常期'
                g.risk_state = '正常期'
                g.last_switch_date = context.current_dt.date()
                g.range_bound_start_date = None
                g.stable_days = 0
                log.info(f"【退出震荡期】切回拉普拉斯: {'; '.join(recovery_signals)}")
    except Exception as e:
        log.warning(f"【震荡期退出检查】异常: {e}")


def check_and_enter_range_bound_mode(context):
    if not g.enable_range_bound_mode:
        return
    if g.current_filter == '震荡期':
        return
    if g.last_switch_date is not None:
        trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
        if len(trade_days) - 1 < g.filter_switch_cooldown:
            return
    risk_signals = []
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is not None:
            if g.enable_bias_trigger:
                ma = benchmark_state['ma']
                bias = (benchmark_state['current_price'] - ma) / ma if ma > 0 else 0
                if bias > g.bias_threshold:
                    risk_signals.append(f"乖离率{bias:.2%}")
            if g.enable_rsi_trigger:
                current_rsi = benchmark_state['current_rsi']
                prev_rsi = benchmark_state['previous_rsi']
                if prev_rsi is not None and current_rsi is not None:
                    if prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                        risk_signals.append(f"RSI回落{prev_rsi:.1f}->{current_rsi:.1f}")
    except Exception as e:
        log.warning(f"【震荡期检查】异常: {e}")
    if g.enable_stop_loss_trigger and is_fresh_stop_loss_signal(context):
        risk_signals.append("盈利保护止损")
    if risk_signals:
        g.current_filter = '震荡期'
        g.risk_state = '震荡期'
        g.last_switch_date = context.current_dt.date()
        g.range_bound_start_date = context.current_dt.date()
        g.stable_days = 0
        log.info(f"【进入震荡期】切至高斯: {'; '.join(risk_signals)}")


def check_range_bound(context):
    if not g.enable_range_bound_mode:
        return
    log.info("========== 震荡期检查开始 ==========")
    prev_filter = g.current_filter
    check_and_exit_range_bound_mode(context)
    check_and_enter_range_bound_mode(context)
    log.info(f"震荡期状态: {g.current_filter}")
    if prev_filter != g.current_filter:
        g.rankings_cache = {'date': None, 'data': None}
        g.target_etfs_cache = {'date': None, 'data': None}
    log.info("========== 震荡期检查完成 ==========")


def reset_range_bound_daily(context):
    if g.current_filter == '震荡期' and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
        g.range_bound_days_count = len(trade_days) - 1


def check_etf_trend_structure(price_series, current_price):
    """均线结构硬过滤：现价>MA10 且 MA5>MA10"""
    if not g.enable_trend_structure_filter:
        return True, ''
    closes = np.asarray(price_series, dtype=float)
    if len(closes) < max(g.trend_ma_period, 10) + 1:
        return False, '历史不足'
    ma10 = float(np.mean(closes[-g.trend_ma_period:]))
    ma5 = float(np.mean(closes[-5:]))
    if g.trend_require_price_above_ma and current_price <= ma10:
        return False, f'现价{current_price:.3f}<=MA{g.trend_ma_period}({ma10:.3f})'
    if g.trend_require_ma5_above_ma10 and ma5 <= ma10:
        return False, f'MA5({ma5:.3f})<=MA10({ma10:.3f})'
    return True, ''


# ==================== 有害卖出冷却 / 震荡期空仓 / 买入得分区间 ====================
def is_range_bound_filter_active(context):
    return g.enable_range_bound_mode and g.current_filter == '震荡期'


def should_fallback_defensive(context):
    """排名为空时是否允许兜底防御ETF。关闭时/震荡期保持空仓。"""
    if not g.enable_defensive_etf:
        return False
    if g.enable_range_bound_cash and is_range_bound_filter_active(context):
        return False
    return True


def mark_harmful_sell(context, security=None):
    """记录有害卖出。走弱期启动QDII守卫冷却；正常期靠 drawdown_selled_today 禁同日买回。"""
    if security:
        g.harmful_sell_last_security = security
    name = get_name(security) if security else ''
    if g.is_a_share_weak:
        g.harmful_sell_last_date = context.current_dt.date()
        log.info(
            f"🛡️ 走弱期有害卖出 {security} {name}，"
            f"{g.harmful_sell_cooldown_weak_days}日内挡QDII追高（商品可轮动）"
        )
    else:
        log.info(f"🛡️ 正常期有害卖出 {security} {name}，仅禁止同日买回该标的")


def get_harmful_sell_cooldown_days(context):
    if g.is_a_share_weak:
        return g.harmful_sell_cooldown_weak_days
    return g.harmful_sell_cooldown_days


def is_harmful_sell_cooldown_active(context):
    if not g.enable_harmful_sell_guard or g.harmful_sell_last_date is None:
        return False
    if not g.is_a_share_weak:
        return False
    cooldown = get_harmful_sell_cooldown_days(context)
    if cooldown <= 0:
        return False
    trade_days = get_trade_days(start_date=g.harmful_sell_last_date, end_date=context.current_dt.date())
    days_since = len(trade_days) - 1
    return days_since < cooldown


def trading_days_since_harmful_sell(context):
    if g.harmful_sell_last_date is None:
        return None
    trade_days = get_trade_days(start_date=g.harmful_sell_last_date, end_date=context.current_dt.date())
    return len(trade_days) - 1


def _daily_returns_series(security, context, lookback):
    hist = attribute_history(security, lookback + 1, '1d', ['close'], skip_paused=True)
    if hist is None or len(hist) < lookback + 1:
        return None
    closes = hist['close'].values.astype(float)
    if np.any(closes <= 0):
        return None
    return np.diff(closes) / closes[:-1]


def calc_return_correlation(sec_a, sec_b, context, lookback=None):
    lookback = lookback or g.correlation_lookback
    ra = _daily_returns_series(sec_a, context, lookback)
    rb = _daily_returns_series(sec_b, context, lookback)
    if ra is None or rb is None or len(ra) != len(rb) or len(ra) < 5:
        return None
    corr = float(np.corrcoef(ra, rb)[0, 1])
    if np.isnan(corr):
        return None
    return corr


def get_weak_qdii_guard_refs(context):
    """走弱期有害卖后：被卖标的 + 当日有害卖集合。"""
    refs = []
    sec = getattr(g, 'harmful_sell_last_security', None)
    if sec and (sec in g.etf_pool or sec == g.defensive_etf):
        refs.append(sec)
    for s in g.drawdown_selled_today:
        if s in g.etf_pool or s == g.defensive_etf:
            refs.append(s)
    return list(dict.fromkeys(refs))


def is_blocked_by_harmful_sell_same_etf(candidate, context):
    """有害卖出冷却期内禁止买回同一只标的（仅挡自身，不挡商品）。"""
    if not g.enable_harmful_sell_guard or not is_harmful_sell_cooldown_active(context):
        return False, None
    ref_sec = getattr(g, 'harmful_sell_last_security', None)
    if ref_sec and candidate == ref_sec:
        return True, ref_sec
    return False, None


def is_blocked_by_weak_overseas_cluster(candidate, context):
    """有害卖出海外代理后，冷却期内禁止买入其他海外ETF。"""
    if not g.enable_weak_qdii_guard or not is_harmful_sell_cooldown_active(context):
        return False, None
    proxy_set = set(getattr(g, 'overseas_proxy_pool', []))
    ref_sec = getattr(g, 'harmful_sell_last_security', None)
    if ref_sec not in proxy_set:
        return False, None
    if is_overseas_qdii(candidate) and candidate != ref_sec:
        return True, ref_sec
    return False, None


def mark_overseas_rotation_sell(context, security=None):
    """走弱期轮动卖出海外 QDII 后，启动短期禁买同簇冷却。"""
    if not g.enable_overseas_rotation_guard or not g.is_a_share_weak:
        return
    if security and not is_overseas_qdii(security):
        return
    g.overseas_rotation_sell_last_date = context.current_dt.date()
    if security:
        g.overseas_rotation_sell_last_security = security
    log.info(
        f"🛡️ 走弱期轮动卖海外 {security} {get_name(security)}，"
        f"{g.overseas_rotation_cooldown_days}日内禁买其他QDII"
    )


def is_overseas_rotation_cooldown_active(context):
    if not g.enable_overseas_rotation_guard or g.overseas_rotation_sell_last_date is None:
        return False
    if not g.is_a_share_weak:
        return False
    cooldown = g.overseas_rotation_cooldown_days
    if cooldown <= 0:
        return False
    trade_days = get_trade_days(
        start_date=g.overseas_rotation_sell_last_date,
        end_date=context.current_dt.date(),
    )
    return len(trade_days) - 1 < cooldown


def is_blocked_by_overseas_rotation_cluster(candidate, context):
    """走弱期轮动卖海外后，冷却期内禁止买入其他海外 QDII。"""
    if not is_overseas_rotation_cooldown_active(context):
        return False, None
    ref_sec = getattr(g, 'overseas_rotation_sell_last_security', None)
    if not ref_sec or not is_overseas_qdii(ref_sec):
        return False, None
    if is_overseas_qdii(candidate) and candidate != ref_sec:
        # 同日 13:09 轮动卖出后，13:10 允许切换至另一只 QDII（避免挡掉正当换仓）
        if g.overseas_rotation_sell_last_date == context.current_dt.date():
            hm = context.current_dt.strftime('%H:%M')
            if '13:05' <= hm <= '13:15':
                return False, None
        return True, ref_sec
    return False, None


def passes_weak_qdii_correlation_guard(candidate, context, refs=None):
    if not g.enable_weak_qdii_guard or not is_harmful_sell_cooldown_active(context):
        return True, None
    refs = refs or get_weak_qdii_guard_refs(context)
    worst = None
    for ref in refs:
        if ref == candidate:
            continue
        corr = calc_return_correlation(candidate, ref, context)
        if corr is None:
            continue
        if corr >= g.correlation_max and (worst is None or corr > worst[1]):
            worst = (ref, corr)
    if worst:
        return False, worst
    return True, None


def resolve_guard_target(context):
    """走弱期有害卖出冷却内的强制目标（cash 模式专用）。"""
    if g.is_a_share_weak and g.harmful_sell_mode_weak == 'cash':
        log.info("🛡️ 走弱期有害卖出冷却中，目标空仓")
        return []
    log.info("🛡️ 有害卖出冷却中，目标空仓")
    return []


def get_harmful_sell_strict_buy_days(context):
    """有害卖出后严买入带持续交易日数 = 冷却天数 + 额外观望日。"""
    return get_harmful_sell_cooldown_days(context) + g.harmful_sell_strict_extra_days


def is_harmful_sell_strict_buy_band_active(context):
    """有害卖出后是否仍处严买入带（冷却期内及恢复轮动后的额外观望日）。"""
    if not g.enable_cooldown_strict_buy_band or g.harmful_sell_last_date is None:
        return False
    trade_days = get_trade_days(start_date=g.harmful_sell_last_date, end_date=context.current_dt.date())
    days_since = len(trade_days) - 1
    return days_since < get_harmful_sell_strict_buy_days(context)


def get_buy_score_band_limits(context=None, etf=None):
    """返回当前生效的买入得分/年化上下限（正常期宽区间，有害卖出后严带）。"""
    max_score = g.buy_max_score
    enable_ann_cap = g.enable_buy_annualized_cap
    max_ann = g.buy_max_annualized
    min_score = g.buy_min_score
    if context is not None and is_harmful_sell_strict_buy_band_active(context):
        max_score = g.buy_max_score_cooldown
        enable_ann_cap = g.enable_buy_annualized_cap_cooldown
        max_ann = g.buy_max_annualized_cooldown
    if (
        context is not None
        and etf
        and g.enable_overseas_weak_commodity_gate
        and g.enable_overseas_regime_switch
        and g.is_overseas_weak
        and etf in g.commodity_etf_pool
    ):
        min_score = max(min_score, g.buy_min_score_overseas_weak)
    return min_score, max_score, enable_ann_cap, max_ann


def passes_buy_score_band(metrics, context=None):
    """买入阶段得分/年化区间（仅影响买，不影响卖）。"""
    score = metrics['score']
    if not g.enable_buy_score_band:
        return score >= g.min_score_threshold
    min_score, max_score, enable_ann_cap, max_ann = get_buy_score_band_limits(
        context, metrics.get('etf')
    )
    if score < min_score:
        log.info(f"🚫 {metrics['etf']} {metrics['etf_name']} 得分{score:.4f} < 买入下限{min_score:.2f}")
        return False
    if score > max_score:
        log.info(f"🚫 {metrics['etf']} {metrics['etf_name']} 得分{score:.4f} > 买入上限{max_score:.2f}")
        return False
    if enable_ann_cap:
        ann = metrics.get('annualized_returns', 0)
        if ann > max_ann:
            log.info(
                f"🚫 {metrics['etf']} {metrics['etf_name']} 年化{ann * 100:.1f}% > "
                f"买入上限{max_ann * 100:.0f}%"
            )
            return False
    return True


def filter_ranked_by_active_pool(ranked, active_pool):
    """仅保留当前有效池内的排名条目。"""
    pool_set = set(active_pool)
    return [m for m in ranked if m['etf'] in pool_set]


def refresh_rankings_for_current_pool(context, ranked):
    """兜底路径：排名含池外标的时，按当前有效池重算排名。"""
    active_pool = set(get_active_etf_pool())
    out_pool = [m['etf'] for m in ranked[:max(g.holdings_num * 3, 5)]
                if m['etf'] not in active_pool]
    if not out_pool:
        return ranked
    log.info(
        f"📊 排名含池外标的{out_pool}，按当前有效池({len(active_pool)}只)重算排名"
    )
    ranked = get_ranked_etfs(context)
    g.rankings_cache = {'date': context.current_dt.date(), 'data': ranked}
    return ranked


def resolve_rotation_targets(context, ranked):
    """统一解析 13:09/13:10 目标ETF（有害卖出冷却 > 轮动 > 防御/震荡期空仓）。"""
    if is_harmful_sell_cooldown_active(context):
        days_since = trading_days_since_harmful_sell(context)
        cooldown = get_harmful_sell_cooldown_days(context)
        if g.harmful_sell_mode_weak == 'cash':
            log.info(f"🛡️ 走弱期有害卖出冷却 {days_since}/{cooldown} 日，全盘空仓")
            return resolve_guard_target(context)
        log.info(
            f"🛡️ 走弱期有害卖出冷却 {days_since}/{cooldown} 日，"
            f"仅挡QDII追高，商品/轮动继续"
        )

    target_etfs = select_target_etfs_from_rankings(context, ranked)
    if not target_etfs and g.enable_overseas_weak_cash and g.is_overseas_weak:
        log.info("💤 海外弱无合格商品标的，目标空仓")
    elif not target_etfs and should_fallback_defensive(context):
        if check_defensive_etf_available(context) and g.defensive_etf not in g.drawdown_selled_today:
            target_etfs = [g.defensive_etf]
            log.info(f"🛡️ 无目标ETF，防御模式：{g.defensive_etf} {get_name(g.defensive_etf)}")
    elif not target_etfs and not g.enable_defensive_etf:
        log.info("💤 无合格标的，防御ETF已关闭，目标空仓")
    elif not target_etfs and g.enable_range_bound_cash and is_range_bound_filter_active(context):
        log.info("💤 震荡期无合格标的，目标空仓")
    return target_etfs


# ==================== 核心计算模块 ====================
def get_cached_rankings(context):
    """获取缓存的ETF排名"""
    today = context.current_dt.date()
    if g.rankings_cache['date'] != today:
        log.info("📊 重新计算ETF排名...")
        ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': today, 'data': ranked}
    else:
        log.debug("🔍 使用缓存的ETF排名")
    return g.rankings_cache['data']


def get_ranked_etfs(context):
    """计算所有ETF的动量得分（V2.0：根据行情状态动态选择ETF池，V2.2受独立开关影响）"""
    active_pool = get_active_etf_pool()

    etf_metrics = []
    for etf in active_pool:
        tradable, reason = is_etf_tradable(context, etf)
        if not tradable:
            log.debug(f"❌ {etf} {get_name(etf)} 不可交易({reason})，跳过")
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            if g.rank_min_score < metrics['score'] < g.rank_max_score:
                etf_metrics.append(metrics)
            else:
                log.debug(f"❌ {etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超出排名区间，过滤")

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def calculate_momentum_metrics(context, etf):
    """计算单只ETF的动量指标（无未来）"""
    try:
        name = get_name(etf)
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < g.lookback_days:
            log.debug(f"🚫 {etf} {name} 历史数据不足{len(prices)}天，跳过")
            return None

        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # 1. 盈利保护检查
        if check_profit_protection(etf, context):
            log.info(f"🚫 {etf} {name} 触发盈利保护，从排名中排除")
            return None

        # 2. 溢价率过滤
        if g.enable_premium_filter:
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = get_premium_rate(etf, prev_date)
            if premium is not None:
                if premium > g.premium_threshold:
                    log.info(f"🚫 {etf} {name} 溢价率{premium*100:.2f}% > 阈值，排除")
                    return None
            else:
                log.debug(f"🚫 {etf} {name} 无法获取{prev_date}的净值，排除")
                return None

        # 3. 成交量过滤
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns(price_series, g.lookback_days)
                if annualized > g.volume_return_limit:
                    log.info(f"📉 {etf} {name} 成交量放量，过滤")
                    return None

        # 4. 短期动量过滤
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0

        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            log.debug(f"❌ {etf} {name} 短期动量不足，过滤")
            return None

        # 4b. 均线趋势结构硬过滤
        ok_trend, trend_reason = check_etf_trend_structure(price_series, current_price)
        if not ok_trend:
            log.info(f"🚫 {etf} {name} 趋势结构未通过({trend_reason})，排除")
            return None

        # 5. 长期动量计算
        recent = price_series[-(g.lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        if g.enable_r2_filter and r_squared < g.r2_threshold:
            log.info(f"🚫 {etf} {name} R²={r_squared:.3f} < {g.r2_threshold:.2f}，排除")
            return None

        score = annualized_returns * r_squared

        # 6. 近3日跌幅过滤
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < g.loss:
                log.info(f"⚠️ {etf} {name} 近3日有单日跌幅超限，排除")
                return None

        # 7. 拉普拉斯/高斯动态滤波（正常期/震荡期）
        if g.enable_range_bound_mode and len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                laplace_slope = laplace_values[-1] - laplace_values[-2] if len(laplace_values) >= 2 else 0
                passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
                g1_val, g2_val = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
                gaussian_slope = g1_val - g2_val
                passed_gaussian = (current_price > g1_val and gaussian_slope > g.gaussian_min_slope)
                if g.current_filter == '正常期':
                    passed_filter = passed_laplace
                    filter_name = '拉普拉斯'
                else:
                    passed_filter = passed_gaussian
                    filter_name = '高斯'
                if not passed_filter:
                    log.info(f"🚫 {etf} {name} 未通过{filter_name}滤波({g.current_filter})，排除")
                    return None
            except Exception as e:
                log.debug(f"{etf} {name} 滤波器异常: {e}")

        return {
            'etf': etf,
            'etf_name': name,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'current_price': current_price,
            'short_annualized': short_annualized,
        }

    except Exception as e:
        log.warning(f"计算{etf} {get_name(etf)}时出错: {e}")
        return None


def get_annualized_returns(price_series, lookback_days):
    """计算加权年化收益率（无未来）"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def get_volume_ratio(context, security, lookback=None, threshold=None):
    """计算成交量比值（基于分钟线）"""
    lookback = lookback or g.volume_lookback
    threshold = threshold or g.volume_threshold
    try:
        name = get_name(security)
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()

        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        if ratio > threshold:
            log.debug(f"❌ {security} {name} 成交量比{ratio:.2f} > {threshold}")
            return ratio
        return None
    except Exception as e:
        log.warning(f"🚨成交量计算失败 {security}: {e}")
        return None


def is_etf_tradable(context, security):
    """
    判断 ETF 当前是否可交易（含盘中临时停牌）。
    聚宽 get_current_data().paused 对「下午临时停牌」常为 False，需结合本时段分钟成交判断。
    返回 (bool, str)：可交易时 (True, '')，不可交易时 (False, 原因)。
    """
    try:
        data = get_current_data()[security]
        if data.paused:
            return False, '全天停牌(paused)'

        price = data.last_price
        if price is None or price <= 0:
            return False, '现价无效'

        now = context.current_dt
        t = now.time()
        session_start = None
        if datetime.time(9, 30) <= t <= datetime.time(11, 30):
            session_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        elif datetime.time(13, 0) <= t <= datetime.time(15, 0):
            session_start = now.replace(hour=13, minute=0, second=0, microsecond=0)
        else:
            return True, ''

        minutes_elapsed = (now - session_start).total_seconds() / 60.0
        if minutes_elapsed < 5:
            return True, ''

        df = get_price(
            security, start_date=session_start, end_date=now,
            frequency='1m', fields=['volume'], skip_paused=True, fq='pre'
        )
        if df is None or df.empty:
            return False, '本交易时段无分钟行情(可能盘中停牌)'

        recent = df.tail(min(15, len(df)))
        if recent['volume'].sum() == 0:
            return False, '本交易时段近段无成交(可能盘中停牌)'

        return True, ''
    except Exception as e:
        log.warning(f"⚠️ {security} {get_name(security)} 可交易性检查异常: {e}")
        return True, ''


def _to_float(value):
    """聚宽行情字段偶为 str，统一转 float 供回撤比较。"""
    try:
        if value is None:
            return None
        v = float(value)
        if np.isnan(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def get_intraday_drawdown_ratio(security, context):
    """测算当日盘中高点→现价的回撤比例；数据不足时返回 None。"""
    try:
        df = get_price(
            security, start_date=context.current_dt.date(), end_date=context.current_dt,
            frequency='1m', fields=['high', 'close'], skip_paused=True, fq='pre'
        )
        if df is None or df.empty:
            return None
        day_high = _to_float(df['high'].max())
        current = _to_float(df['close'].iloc[-1])
        if not day_high or not current or day_high <= 0:
            return None
        return (day_high - current) / day_high
    except Exception:
        return None


def get_prev_trading_close(security, context):
    """前一交易日收盘价（用于持仓跳空回撤）。"""
    try:
        prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
        df = get_price(
            security, end_date=prev_date, frequency='1d',
            fields=['close'], count=1, fq='pre', skip_paused=True
        )
        if df is None or df.empty:
            return None
        return float(df['close'].iloc[-1])
    except Exception:
        return None


def get_holding_drawdown_detail(security, context):
    """持仓回撤明细：日内高点→现价；可选昨收→现价。买入过滤仍仅用日内。"""
    detail = {}
    idd = get_intraday_drawdown_ratio(security, context)
    if idd is not None:
        detail['日内'] = idd
    if g.enable_holding_prev_close_drawdown:
        prev_close = get_prev_trading_close(security, context)
        try:
            current = get_current_data()[security].last_price
        except Exception:
            current = None
        current = _to_float(current)
        prev_close = _to_float(prev_close)
        if prev_close and current and prev_close > 0 and current > 0:
            detail['昨收'] = (prev_close - current) / prev_close
    return detail


def get_holding_drawdown_ratio(security, context):
    detail = get_holding_drawdown_detail(security, context)
    if not detail:
        return None, detail
    return max(detail.values()), detail


def get_position_unrealized_gain(security, context):
    """持仓相对成本的浮盈比例；无法计算时返回 None。"""
    try:
        pos = context.portfolio.positions[security]
        if pos.total_amount <= 0:
            return None
        cost = _to_float(pos.avg_cost)
        price = _to_float(pos.price)
        if not price:
            try:
                price = _to_float(get_current_data()[security].last_price)
            except Exception:
                price = None
        if not price or not cost or cost <= 0:
            return None
        return (price - cost) / cost
    except Exception:
        return None


def get_holding_drawdown_for_sell(security, context, source='minute'):
    """持仓卖出回撤：盈利仓豁免分钟误杀；盈利仓 13:09 不用昨收跳空。
    返回 (drawdown, detail, threshold)；drawdown/threshold 为 None 表示不触发卖。
    """
    gain = get_position_unrealized_gain(security, context)
    skip_minute = getattr(g, 'holding_profit_skip_minute_pct', 0.10)
    skip_prev = getattr(g, 'holding_profit_skip_prev_close_pct', 0.10)

    if source == 'minute' and gain is not None and gain >= skip_minute:
        return None, {}, None

    detail = get_holding_drawdown_detail(security, context)
    if gain is not None and gain >= skip_prev and '昨收' in detail:
        detail = {k: v for k, v in detail.items() if k != '昨收'}

    if not detail:
        return None, {}, None

    drawdown = max(detail.values())
    threshold = g.intraday_drawdown_threshold
    return drawdown, detail, threshold


def is_intraday_drawdown_active(security, context):
    """与买入守卫同源：当日盘中回撤是否已达阈值。"""
    drawdown = get_intraday_drawdown_ratio(security, context)
    return drawdown is not None and drawdown >= g.intraday_drawdown_threshold


def check_intraday_drawdown_for_buy(security, context):
    """买入前检查：ETF当前是否处于日内显著回撤状态
    返回 True 表示正在回撤（不宜买入），False 表示正常
    """
    return is_intraday_drawdown_active(security, context)


def execute_intraday_drawdown_sell(
    context, security, drawdown, source='日内回撤', detail=None, threshold=None
):
    """日内回撤触发的统一卖出（分钟级 / 13:09 持仓守卫共用）。"""
    name = get_name(security)
    th = threshold if threshold is not None else g.intraday_drawdown_threshold
    detail_str = ''
    if detail:
        detail_str = ' [' + ' '.join(
            f"{k}{v * 100:.2f}%" for k, v in detail.items()
        ) + ']'
    log.info(
        f"⚠️ {source}回撤触发：{security} {name} "
        f"回撤{drawdown * 100:.2f}% > {th * 100:.0f}%"
        f"{detail_str}"
    )
    if smart_order_target_value(security, 0, context):
        log.info(f"🧨 {source}回撤卖出：{security} {name}")
        g.drawdown_selled_today.add(security)
        mark_harmful_sell(context, security)
        if security in g.buy_date:
            del g.buy_date[security]
        return True
    return False


def filter_intraday_drawdown_targets(context, target_etfs):
    """从目标列表剔除回撤标的；已持仓用持仓回撤（含昨收），候选仅用日内。"""
    held = {
        s for s in context.portfolio.positions
        if (s in g.etf_pool or s == g.defensive_etf)
        and context.portfolio.positions[s].total_amount > 0
    }
    filtered = []
    for etf in target_etfs:
        if etf in held:
            drawdown, detail, threshold = get_holding_drawdown_for_sell(
                etf, context, source='slot1309'
            )
        else:
            drawdown = get_intraday_drawdown_ratio(etf, context)
            detail = {'日内': drawdown} if drawdown is not None else {}
            threshold = g.intraday_drawdown_threshold
        if (
            drawdown is not None
            and threshold is not None
            and drawdown >= threshold
        ):
            detail_str = ' '.join(f"{k}={v * 100:.2f}%" for k, v in detail.items())
            log.info(
                f"🌊 {etf} {get_name(etf)} 回撤"
                f"(>{g.intraday_drawdown_threshold * 100:.0f}%)，目标列表剔除 [{detail_str}]"
            )
            continue
        filtered.append(etf)
    return filtered


def passes_buy_candidate_filters(m, context, guard_refs=None):
    """单只 ETF 是否通过买入阶段全部守卫与弱势过滤。"""
    etf = m['etf']
    etf_name = m['etf_name']

    if not passes_buy_score_band(m, context):
        return False

    tradable, reason = is_etf_tradable(context, etf)
    if not tradable:
        log.info(f"🚫 {etf} {etf_name} 不可交易({reason})，买入过滤剔除")
        return False

    if g.enable_profit_protection and check_profit_protection(etf, context):
        log.info(f"🚫 {etf} {etf_name} 触发盈利保护，买入过滤剔除")
        return False

    if etf in g.drawdown_selled_today:
        log.info(f"🚫 {etf} {etf_name} 今日因回撤/盈利保护卖出，买入过滤剔除")
        return False

    blocked_same, ref_same = is_blocked_by_harmful_sell_same_etf(etf, context)
    if blocked_same:
        days_since = trading_days_since_harmful_sell(context)
        cooldown = get_harmful_sell_cooldown_days(context)
        log.info(
            f"🚫 {etf} {etf_name} 有害卖出冷却 {days_since}/{cooldown} 日，"
            f"禁止买回同标的"
        )
        return False

    blocked, ref_sec = is_blocked_by_weak_overseas_cluster(etf, context)
    if blocked:
        log.info(
            f"🚫 {etf} {etf_name} 海外有害簇挡："
            f"近期有害卖出 {ref_sec} {get_name(ref_sec)}"
        )
        return False

    blocked_rot, ref_rot = is_blocked_by_overseas_rotation_cluster(etf, context)
    if blocked_rot:
        log.info(
            f"🚫 {etf} {etf_name} 轮动卖海外挡："
            f"近期轮动卖出 {ref_rot} {get_name(ref_rot)}"
        )
        return False

    ok_corr, corr_info = passes_weak_qdii_correlation_guard(etf, context, guard_refs)
    if not ok_corr:
        ref, corr = corr_info
        log.info(
            f"🚫 {etf} {etf_name} 弱期低相关守卫：与 {ref} {get_name(ref)} "
            f"{g.correlation_lookback}日相关{corr:.2f}≥{g.correlation_max:.2f}"
        )
        return False

    if check_intraday_drawdown_for_buy(etf, context):
        log.info(
            f"🌊 {etf} {etf_name} 当前处于日内回撤状态"
            f"(>{g.intraday_drawdown_threshold*100:.0f}%)，买入过滤剔除"
        )
        return False

    if g.enable_holding_prev_close_drawdown:
        _, detail = get_holding_drawdown_ratio(etf, context)
        prev_dd = detail.get('昨收')
        if prev_dd is not None and prev_dd >= g.intraday_drawdown_threshold:
            log.info(
                f"🌊 {etf} {etf_name} 相对昨收回撤{prev_dd * 100:.2f}%"
                f"(>{g.intraday_drawdown_threshold * 100:.0f}%)，买入过滤剔除"
            )
            return False

    return True


def refilter_cached_buy_targets(context, cached_etfs, ranked):
    """买入前对缓存目标复跑守卫，并过滤当前有效池外的弱势标。"""
    active_pool = set(get_active_etf_pool())
    ranked_map = {m['etf']: m for m in ranked}
    guard_refs = get_weak_qdii_guard_refs(context) if is_harmful_sell_cooldown_active(context) else []
    result = []
    for etf in cached_etfs:
        if etf not in active_pool:
            log.info(f"🚫 {etf} {get_name(etf)} 不在当前有效池(弱势屏蔽)，缓存复检剔除")
            continue
        m = ranked_map.get(etf)
        if m is None:
            log.info(f"🚫 {etf} {get_name(etf)} 不在当日排名，缓存复检剔除")
            continue
        if passes_buy_candidate_filters(m, context, guard_refs):
            result.append(etf)
            if guard_refs is not None:
                guard_refs.append(etf)
    return result, guard_refs


def extend_buy_targets_from_rankings(context, ranked, target_etfs, guard_refs=None):
    """缓存过滤后不足持仓数时，按排名顺延替补（复用相同守卫）。"""
    active_pool = set(get_active_etf_pool())
    existing = set(target_etfs)
    for m in ranked:
        if len(target_etfs) >= g.holdings_num:
            break
        etf = m['etf']
        if etf in existing:
            continue
        if etf not in active_pool:
            continue
        if passes_buy_candidate_filters(m, context, guard_refs):
            target_etfs.append(etf)
            existing.add(etf)
            log.info(f"🔄 缓存目标不可买，顺延替补：{etf} {m['etf_name']}")
            if guard_refs is not None:
                guard_refs.append(etf)
    return target_etfs


def _pick_targets_from_ranked(context, ranked, guard_refs):
    """从已按有效池过滤的排名列表中选出目标 ETF。"""
    target_etfs = []
    for m in ranked:
        if len(target_etfs) >= g.holdings_num:
            break
        if passes_buy_candidate_filters(m, context, guard_refs):
            target_etfs.append(m['etf'])
            if guard_refs is not None:
                guard_refs.append(m['etf'])
    return target_etfs


def select_target_etfs_from_rankings(context, ranked, allow_rerank=True):
    """从排名列表中按统一过滤条件选出目标ETF，最多 holdings_num 个。

    卖出和买入共用此函数，确保两者的目标集合完全一致，
    杜绝「13:09 卖出 → 13:10 买回同一标的」的现象。

    过滤逻辑（优先级从高到低）：
      0. 当前有效池（V3.12.2：池外弱势标直接跳过）
      1. 买入得分区间（passes_buy_score_band）
      2. 可交易性（全天/盘中停牌）
      3. 盈利保护检查（避免卖了又买）
      4. 当日回撤/盈利保护卖出禁止买回（drawdown_selled_today）
      5. 走弱期有害卖后 QDII 簇挡 / 低相关守卫（V3.11）
      6. 走弱期轮动卖海外后 QDII 簇挡（V3.12）
      7. 日内回撤检查（避免"接飞刀"）
    """
    active_pool = get_active_etf_pool()
    pool_ranked = filter_ranked_by_active_pool(ranked, active_pool)
    skipped = len(ranked) - len(pool_ranked)
    if skipped:
        log.info(f"📊 有效池过滤：{skipped}只不在当前池，候选缩至{len(pool_ranked)}只")

    guard_refs = get_weak_qdii_guard_refs(context) if is_harmful_sell_cooldown_active(context) else []
    target_etfs = _pick_targets_from_ranked(context, pool_ranked, guard_refs)

    if not target_etfs and allow_rerank and skipped:
        log.info("📊 池过滤后无合格标的，按当前有效池重算排名后再选")
        fresh_ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': context.current_dt.date(), 'data': fresh_ranked}
        return select_target_etfs_from_rankings(context, fresh_ranked, allow_rerank=False)

    return target_etfs


# ==================== 卖出模块 ====================
@time_monitor(func_name="卖出操作")
def etf_sell_trade(context):
    """卖出不符合条件的持仓"""
    log.info("📤 ========== 卖出操作开始 ==========")

    refresh_regime_for_trade(context)
    ranked = get_cached_rankings(context)
    target_etfs = resolve_rotation_targets(context, ranked)
    target_etfs = filter_intraday_drawdown_targets(context, target_etfs)

    # 缓存最终目标列表，供 13:10 买入复用（避免时间敏感过滤在 1 分钟内变化）
    g.target_etfs_cache = {'date': context.current_dt.date(), 'data': list(target_etfs)}

    target_set = set(target_etfs)

    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount <= 0:
            continue

        drawdown, detail, threshold = get_holding_drawdown_for_sell(
            sec, context, source='slot1309'
        )
        in_drawdown = (
            drawdown is not None
            and threshold is not None
            and drawdown >= threshold
        )
        if detail and drawdown is not None and drawdown >= 0.01:
            log.info(
                f"📉 持仓回撤检视 {sec} {get_name(sec)}: "
                + ' '.join(f"{k}={v * 100:.2f}%" for k, v in detail.items())
            )

        if in_drawdown:
            cost = pos.avg_cost
            buy_date = g.buy_date.get(sec)
            hold_days = (context.current_dt.date() - buy_date).days if buy_date else 0
            if execute_intraday_drawdown_sell(
                context, sec, drawdown, source='13:09持仓',
                detail=detail, threshold=threshold
            ):
                g.trade_log['sell_records'].append({
                    'time': get_real_time(),
                    'code': sec,
                    'name': get_name(sec),
                    'cost': cost,
                    'price': get_current_data()[sec].last_price,
                    'hold_days': hold_days
                })
            continue

        if sec not in target_set:
            cost = pos.avg_cost
            buy_date = g.buy_date.get(sec)
            hold_days = (context.current_dt.date() - buy_date).days if buy_date else 0
            if smart_order_target_value(sec, 0, context):
                log.info(f"📤 卖出持仓：{sec} {get_name(sec)}")
                if is_overseas_qdii(sec):
                    mark_overseas_rotation_sell(context, sec)
                g.trade_log['sell_records'].append({
                    'time': get_real_time(),
                    'code': sec,
                    'name': get_name(sec),
                    'cost': cost,
                    'price': get_current_data()[sec].last_price,
                    'hold_days': hold_days
                })
                if sec in g.buy_date:
                    del g.buy_date[sec]

    log.info("📤 ========== 卖出操作完成 ==========")


# ==================== 买入模块 ====================
@time_monitor(func_name="买入操作")
def etf_buy_trade(context):
    """买入符合条件的ETF"""
    log.info("📥 ========== 买入操作开始 ==========")

    refresh_regime_for_trade(context)
    ranked = get_cached_rankings(context)
    log.info("📊 === ETF排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        annual_pct = m['annualized_returns'] * 100
        r_sq = m['r_squared']
        log.info(f"   排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} 年化{annual_pct:.2f}%")

    today = context.current_dt.date()
    if is_harmful_sell_cooldown_active(context):
        target_etfs = resolve_rotation_targets(context, ranked)
    elif g.target_etfs_cache['date'] == today and g.target_etfs_cache['data'] is not None:
        raw_targets = list(g.target_etfs_cache['data'])
        log.info(f"📋 复用13:09目标ETF缓存：{raw_targets}")
        target_etfs, guard_refs = refilter_cached_buy_targets(context, raw_targets, ranked)
        if len(target_etfs) < g.holdings_num:
            target_etfs = extend_buy_targets_from_rankings(
                context, ranked, target_etfs, guard_refs
            )
        if not target_etfs:
            log.info("📋 缓存目标经守卫复检后为空，回退 resolve_rotation_targets（同步有效池）")
            ranked = refresh_rankings_for_current_pool(context, ranked)
            target_etfs = resolve_rotation_targets(context, ranked)
    else:
        target_etfs = resolve_rotation_targets(context, ranked)

    if not target_etfs:
        log.info("💤 无目标ETF，保持空仓")
        return

    if target_etfs:
        for i, etf in enumerate(target_etfs):
            m = next((x for x in ranked if x['etf'] == etf), None)
            if m:
                log.info(f"🎯 目标ETF {i+1}: {etf} {m['etf_name']} 得分{m['score']:.4f}")
    else:
        log.info("💤 无目标ETF，保持空仓")
        return

    # 检查是否有持仓需要先卖出
    current_etf_pos = [s for s in context.portfolio.positions if s in g.etf_pool or s == g.defensive_etf]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        log.info(f"⏳ 尚有持仓需要卖出：{[get_name(s) for s in to_sell]}，等待卖出完成")
        return

    # 等权分配
    total_val = context.portfolio.total_value
    target_per_etf = total_val / len(target_etfs)

    for etf in target_etfs:
        current_val = 0
        if etf in context.portfolio.positions:
            pos = context.portfolio.positions[etf]
            if pos.total_amount > 0:
                current_val = pos.total_amount * pos.price
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            if smart_order_target_value(etf, target_per_etf, context):
                action = "买入" if current_val < target_per_etf else "调仓"
                log.info(f"📦 {action}：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")

    log.info("📥 ========== 买入操作完成 ==========")


# ==================== 辅助函数 ====================
def get_name(security):
    try:
        return get_current_data()[security].name
    except:
        return "未知"


def check_defensive_etf_available(context):
    etf = g.defensive_etf
    tradable, _ = is_etf_tradable(context, etf)
    if not tradable:
        return False
    data = get_current_data()
    if data[etf].last_price >= data[etf].high_limit:
        return False
    if data[etf].last_price <= data[etf].low_limit:
        return False
    return True


def smart_order_target_value(security, target_value, context):
    data = get_current_data()
    name = get_name(security)

    tradable, reason = is_etf_tradable(context, security)
    if not tradable:
        log.info(f"❌ {security} {name} 不可交易({reason})，跳过下单")
        return False

    price = data[security].last_price
    if price == 0:
        return False

    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount

    if diff > 0:
        if data[security].last_price >= data[security].high_limit:
            log.info(f"🔒 {security} {name} 涨停，跳过买入")
            return False
    elif diff < 0:
        if data[security].last_price <= data[security].low_limit:
            log.info(f"🔒 {security} {name} 跌停，跳过卖出")
            return False

    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        log.info(f"💰 {security} {name} 交易金额太小，跳过")
        return False

    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            return False
        diff = -min(abs(diff), closeable)

    if diff != 0:
        order_result = order(security, diff)
        if order_result:
            log.info(f"{'📥 买入' if diff>0 else '📤 卖出'} {security} {name} 数量{abs(diff)} 价格{price:.3f}")
            if diff > 0:
                g.buy_date[security] = context.current_dt.date()
            return True
        else:
            log.warning(f"⚠️ 下单失败: {security} {name}")
            return False
    return False


# ==================== 盘后总结报告 ====================
def daily_summary_report(context):
    """盘后总结"""
    current_date = context.current_dt.strftime('%Y-%m-%d')
    total_value = context.portfolio.total_value
    cash = context.portfolio.cash
    positions_value = total_value - cash

    log.info("📋 ========== 策略运行日报 ==========")
    log.info(f"📅 日期: {current_date}")

    # 市场状态（含独立开关状态）
    if g.enable_regime_switch:
        status = "🔴走弱期" if g.is_a_share_weak else "🟢正常期"
        avoid_status = "回避A股" if (g.is_a_share_weak and g.enable_avoid_a_share) else ("不回避A股" if g.is_a_share_weak else "正常交易")
        drawdown_status = "🛡️启用" if (g.is_a_share_weak and g.enable_intraday_drawdown) else ("⭕关闭" if (g.is_a_share_weak and not g.enable_intraday_drawdown) else "⭕关闭")
        log.info(f"🌍 市场状态：{status} | {avoid_status} 计数:{g.weak_period_counter}/{g.weak_period_max_days}")
        log.info(f"🛡️ 分钟级回撤：{drawdown_status}（阈值{g.intraday_drawdown_threshold*100:.0f}%）")
        filt = "拉普拉斯·正常期" if g.current_filter == "正常期" else "高斯·震荡期"
        log.info("📐 滤波器：%s | R2过滤：%s | 均线结构：%s" % (filt, "开" if g.enable_r2_filter else "关", "开" if g.enable_trend_structure_filter else "关"))
    else:
        log.info("🌍 行情判断未启用，始终全市场交易")

    if g.enable_overseas_regime_switch:
        ostatus = "🔴海外弱" if g.is_overseas_weak else "🟢海外正常"
        log.info(f"🌐 海外状态：{ostatus} 计数:{g.overseas_weak_counter}/{g.overseas_weak_max_days}")

    if g.enable_overseas_rotation_guard and g.overseas_rotation_sell_last_date is not None:
        if is_overseas_rotation_cooldown_active(context):
            trade_days = get_trade_days(
                start_date=g.overseas_rotation_sell_last_date,
                end_date=context.current_dt.date(),
            )
            days_since = len(trade_days) - 1
            log.info(
                f"🛡️ 轮动卖海外冷却：激活 {days_since}/{g.overseas_rotation_cooldown_days}日 "
                f"上次={g.overseas_rotation_sell_last_date}"
            )

    if g.enable_harmful_sell_guard and g.harmful_sell_last_date is not None:
        if is_harmful_sell_cooldown_active(context):
            trade_days = get_trade_days(start_date=g.harmful_sell_last_date, end_date=context.current_dt.date())
            days_since = len(trade_days) - 1
            cooldown = get_harmful_sell_cooldown_days(context)
            log.info(f"🛡️ 走弱期有害卖出冷却：激活 {days_since}/{cooldown}日 上次={g.harmful_sell_last_date}")
        else:
            log.info(f"🛡️ 有害卖出冷却：已过期 上次={g.harmful_sell_last_date}")
    else:
        log.info("🛡️ 有害卖出冷却：无记录")

    # 独立开关汇总
    avoid_switch_status = "ON（走弱期回避A股）" if g.enable_avoid_a_share else "OFF（走弱期不回避A股）"
    drawdown_switch_status = "ON（走弱期自动启用）" if g.enable_intraday_drawdown else "OFF（不触发）"
    log.info(f"⚙️ 独立开关：A股回避={avoid_switch_status} | 分钟回撤={drawdown_switch_status}")

    # 今日卖出
    sell_records = g.trade_log.get('sell_records', [])
    log.info(f"📤 今日卖出：{len(sell_records)}只")
    for r in sell_records:
        cost = r.get('cost', 0)
        sell_price = r.get('price', 0)
        profit_pct = (sell_price / cost - 1) * 100 if cost > 0 else 0
        hold_days = r.get('hold_days', 0)
        log.info(f"   {r['code']} {r['name']} | 成本:{cost:.3f} | 卖出:{sell_price:.3f} | 收益:{profit_pct:+.2f}% | 持有{hold_days}天")

    # 最终持仓
    pos_list = []
    for sec, pos in context.portfolio.positions.items():
        if pos.total_amount == 0:
            continue
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos_list.append(sec)
    log.info(f"📊 最终持仓：{len(pos_list)}只")
    for sec, pos in context.portfolio.positions.items():
        if pos.total_amount == 0:
            continue
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        current_price = get_current_data()[sec].last_price
        cost = pos.avg_cost
        profit_pct = (current_price / cost - 1) * 100 if cost > 0 else 0
        buy_date = g.buy_date.get(sec)
        hold_days = (context.current_dt.date() - buy_date).days if buy_date else 0
        log.info(f"   {sec} {get_name(sec)} | 成本:{cost:.3f} | 当前:{current_price:.3f} | 收益:{profit_pct:+.2f}% | 持有{hold_days}天")

    # 账户汇总
    returns = (total_value - context.portfolio.starting_cash) / context.portfolio.starting_cash * 100
    log.info(f"💰 总资产：{total_value:.2f} | 可用：{cash:.2f} | 市值：{positions_value:.2f} | 累计收益：{returns:.2f}%")
    log.info("📋🐂🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩报告结束 🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🐂")
    log.info("")

'''
# 标题：七星超级加175v311 V3.15 双风险规避定版（聚宽）
# 作者：任侠

"""
七星超级加175v311 V3.15 双风险规避定版（聚宽独立版，基于 V3.14）

【说明】
- 由合并版 `七星超级加175v311V3.15.py` 拆分；QMT 端见 `七星超级加175v311V3.15-QMT.py`。

【变更记录】
- V3.15 [2026/05/25]（当前定版）
  - 盈利仓分钟回撤豁免：浮盈≥10% 时分钟守卫不卖，改由 13:09/盈利保护处理（修 3/4 原油 10:31 误杀）。
  - 盈利仓 13:09 回撤仅用日内高点→现价，不用昨收跳空（保留对亏损仓的昨收低开保护）。
  - 同日 13:09 轮动卖海外后，13:10 允许买入另一只 QDII（修 6/5 标普→日经被挡又买回标普）。
- V3.14 [2026/05/25]
  - 日内回撤守卫扩展：get_intraday_drawdown_ratio 买入/13:09 持仓/分钟检查三处共用；持仓触发则强制卖并剔除目标缓存。
  - 关闭防御 ETF 兜底（enable_defensive_etf=False）：无合格标的时保持空仓，减少 511010 换仓摩擦（全周期约 37 笔）。
  - 双弱无商品标的时亦空仓（不再兜底 511010）。
  - 持仓回撤补昨收基准：除日内高点→现价外，兼看昨收→现价（覆盖跳空低开）。
  - 有害卖出冷却期内禁止买回同一只标的（修复 6/4 卖出 513520 后 6/5 又买回）。
  - 回撤测算统一 float 转换（修复分钟检查 str/float 异常导致盘中守卫失效）。
- V3.13 [2026/05/25]
  - 双风险规避固定：A 股弱（回避 A 股 ETF）+ 海外弱（屏蔽 QDII）独立判断、四格池、盘中现价双轨复检。
  - 13:09/13:10 统一 refresh_regime_for_trade：A 股弱与海外弱同分钟各检一次，边界迟滞 + 有效池/守卫/缓存复检闭环。
  - 定版目标：规避国内系统性风险与海外 QDII 风险，双弱时仅商品池（V3.13 曾兜底 511010，V3.14 已关）。
- V3.12.3 [2026/05/25]
  - 海外弱双轨：09:40 日 K 定调 + 13:09/13:10 盘中现价对 MA 复检（真正「越晚越准」）。
  - 边界迟滞：同日 enter/exit 同时满足时维持原状态，盘中退出门槛 3/4（严于进入 2/4），且每分钟只复检一次。
- V3.12.2 [2026/05/25]
  - resolve_rotation_targets / select_target 统一强制当前有效池过滤；池与缓存排名不一致时兜底路径自动重算排名，杜绝回退仍选池外 QDII。
- V3.12.1 [2026/05/25]
  - 13:10 复用缓存前：刷新海外弱状态，对缓存目标复跑全部买入守卫，并剔除当前有效池外弱势标；不足则排名顺延或 resolve 兜底。
- V3.12 [2026/05/25]
  - 海外弱独立判断（与 A 股弱解耦）：4 个 QDII 代理 MA10/MA5 结构，≥2/4 进入海外弱。
  - 四格 active_pool：A正常+海外弱→A股+商品；A弱+海外弱→仅商品；海外弱即屏蔽 QDII 排名。
  - 海外弱时商品替代买入门槛 buy_min_score_overseas_weak；无合格标的仍走 511010 兜底。
  - 走弱期轮动卖出海外 QDII 后 1 日禁买同簇；有害卖 2 日 qdii_guard 保留。
  - overseas_proxy_pool 去掉 513100，与 159509 对齐。
- V3.11 [2026/05/25]
  - 在 V3.10 高收益骨架上精修：走弱期有害卖出由「2日全盘空仓」改为「2日仅挡QDII追高」，商品/原油等可继续轮动（修复3月原油被挡）。
  - 走弱期冷却内叠加：海外有害簇挡 + 低相关守卫（仅挡高相关海外，不挡商品）。
  - 排名得分上限 100→10000，避免超高动量主线被误杀。
- V3.10 [2026/05/25]
  - 有害卖出冷却收窄：正常期仅禁止同日买回该标的（drawdown_selled_today），不暂停轮动、不强制511010。
  - 走弱期保留有害卖出后2日空仓（防6/3纳指回撤后接日经）。
  - 买入得分保持V3.9：仅下限0.2、上限100，无年化上限。
- V3.9 [2026/05/25]
  - 买入仅下限0.2/上限100；V3.9回测1-5月约195%（V3.6约220%），差距主因正常期有害冷却误杀轮动。
- V3.8 [2026/05/25]
  - 买入得分[0.2,10.0]；关闭全局年化上限；有害卖出后严带≤2.5（实测仍挡主线）。
- V3.7 [2026/06/03]
  - 有害卖出冷却：分钟回撤/盈利保护卖出后暂停轮动；正常期防御511010，走弱期空仓；冷却1日/走弱2日。
  - 震荡期空仓（参考175）：震荡期无合格标的不买511010，保持空仓。
  - 买入得分双轨：排名宽区间[0,100]；买入阶段得分[0.2,2.5]+可选年化上限200%（仅买不卖）。
- V3.6 [2026/06/03]
  - 融合七星175阶段1：全时期均线结构硬过滤(价>MA10且MA5>MA10)、R²≥0.35、拉普拉斯/高斯 per-ETF 滤波。
  - 510300 震荡期切换(13:05检查)：正常期拉普拉斯、震荡期高斯；保留走弱期切池+511010防御+is_etf_tradable。
- V3.5 [2026/06/03]
  - 退出弱势期：废弃「≥3 指数站上 MA10 连续 2 日」；改为「≥3 指数 MA5、MA10 较前一日同时上升」；20 日强制退出不变。
  - 盘中停牌防护：is_etf_tradable（paused + 本交易时段无成交）；目标选择 / 13:10 缓存复检 / 下单前拦截；不可买则排名顺延。
  - 策略文件为 .py；QMT 代码见独立文件 `七星超级加175v311V3.15-QMT.py`。
- V3.4 [2026/05/31]
  - 退出弱势期条件调整（聚宽 + QMT 同步）：
    * 原「当日 ≥3 指数站上 MA10 即恢复」改为「≥3 指数站上 MA10 连续 2 个交易日」方可恢复。
    * 走弱期满 20 日强制退出逻辑不变。
- V3.3 [2026/05/31]
  - 弱势期第二路条件调整（聚宽 + QMT 同步）：
    * 移除 MA10 近 5 日斜率向下判断。
    * 改为 ≥3 个指数满足「MA5/MA10 死叉」或「MA5 < MA10」。
    * 第一路「≥3 指数现价 < MA10」保留；退出弱势逻辑不变。
- V3.2 [2026/05/31]
  - 弱势期判断升级（聚宽 + QMT 同步）：
    * 监测指数由 4 个扩充为 6 个：在原有沪深300、深证综指、创业板指、中证A500 基础上，新增上证指数(000001)、深证成指(399001)。
    * 进入弱势期条件（满足其一即可）：① ≥3 个指数当前价低于各自 10 日均线；② ≥3 个指数 10 日均线近 5 日斜率向下。
- V3 [2026/05/30]
  - 修复「同日先卖后买同一标的」的 bug：
    * 根因：卖出模块只看 ranked[:N] 前 N 名（无过滤），买入模块遍历全部排名并应用多种过滤（盈利保护/日内回撤），前 N 名被过滤后排名靠后的 ETF 会被"提拔"到目标列表，导致 13:09 卖出的 ETF 在 13:10 又被买入。
    * 修复：提取统一函数 select_target_etfs_from_rankings()，卖出与买入共用完全相同的目标选择逻辑，保证同一交易日内两者的目标集合严格一致。
    * 补充：13:09 卖出时将最终目标列表写入 g.target_etfs_cache，13:10 买入直接复用，避免日内回撤等时间敏感过滤在 1 分钟内变化导致买卖目标再次分歧。
- V2 [2026/05/29]
  - 卖出分类优化：区分"有害卖出"（回撤/盈利保护）和"中性卖出"（排名轮动/溢价率）
    * 新增 g.drawdown_selled_today 记录有害卖出标的，禁止日内买回；中性卖出（轮动/溢价率）不禁止日内买回
  - 日内回撤守卫（get_intraday_drawdown_ratio）：买入过滤 + 13:09 持仓强制卖 + 分钟检查共用；原 check_intraday_drawdown_for_buy：
    * 任何买入候选标的需通过日内回撤检查（>2%回撤暂不买入），避免"接飞刀"
  - 防御ETF检查改用 drawdown_selled_today，仅在回撤/盈利保护卖出时禁止买回
"""

# 导入函数库
import numpy as np
import pandas as pd
import math
from datetime import datetime, timedelta
from scipy import stats
from sklearn.metrics import r2_score
import time
import json
# import pickle
from collections import defaultdict
from functools import wraps
import talib    
import platform

# ==================== 物理时间监控装饰器 ====================
def time_monitor(func_name=None):
    """时间监控装饰器，记录函数执行的真实物理时间"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_real = datetime.now()

            log.info(f"⏱️ [{func_name or func.__name__}] 开始执行 - 真实时间: {start_real.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                end_real = datetime.now()
                elapsed = end_time - start_time

                log.info(f"✅ [{func_name or func.__name__}] 执行完成 - 耗时: {elapsed*1000:.2f}ms | 真实时间: {end_real.strftime('%H:%M:%S')}")

                if elapsed > 0.95:
                    log.warning(f"⚠️ [{func_name or func.__name__}] 执行耗时过长: {elapsed*1000:.2f}ms")

                return result
            except Exception as e:
                end_time = time.time()
                elapsed = end_time - start_time
                log.error(f"❌ [{func_name or func.__name__}] 执行异常 - 耗时: {elapsed*1000:.2f}ms | 错误: {str(e)[:100]}")
                raise
        return wrapper
    return decorator

# ==================== 辅助函数：获取真实时间 ====================
def get_real_time():
    return datetime.now().strftime('%H:%M:%S')

# ==================== 初始化模块 ====================
def initialize(context):
    """
    初始化函数：设置交易参数、ETF池、核心参数、调度任务
    """
    g.strategy_version = 'V3.15'
    g.strategy_id = 'QX3.15'
    g.strategy_log_marker = '[QX3.15]'

    # ---------- 交易设置 ----------
    # set_option("avoid_future_data", True)
    # set_option("use_real_price", True)
    # set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    # set_order_cost(
    #     OrderCost(
    #         open_tax=0,
    #         close_tax=0,
    #         open_commission=0.0005,
    #         close_commission=0.0005,
    #         close_today_commission=0,
    #         min_commission=5,
    #     ),
    #     type="fund",
    # )
    set_benchmark("000300.SS")

    
    if not is_trade():        
    # # 设置佣金费率
        # set_commission(0.0001)  # 设置佣金为万分之一,  
        # #没有设置印花税的接口, 印花税是卖收 0.0005, 总共0.0007, 平均单向0.00035。 只对Stock收印花税， ETF不收印花税 
        set_commission(commission_ratio=0.0001, min_commission=1, type="ETF")
        # set_commission(commission_ratio=0.0035, min_commission=5.0, type="STOCK")
    
    # # 设置滑点
        set_slippage(0.0002)  # 设置滑点为万分之二 0.0002

    # # 设置成交数量限制模式
        set_limit_mode(limit_mode='UNLIMITED')
        
    # log.set_level('order', 'error')
    # log.set_level('system', 'error')
    # log.set_level('strategy', 'debug')
    log.info("🚀 ==========七星三池风规V175 策略初始化开始 ==========")

    # ---------- ETF池 ----------
    g.etf_pool_bak = [
        "518880.SS",   # 黄金ETF
        "159985.SZ",   # 豆粕ETF
        "501018.SS",   # 南方原油
        "161226.SZ",   # 白银LOF
        "513100.SS",   # 纳指ETF
        "159915.SZ",   # 创业板ETF
        "511220.SS",   # 城投债ETF
    ]

    # ==========按类别分类ETF ==========
    # 海外ETF（走弱期可交易）
    g.overseas_etf_pool = [
        "513100.SS",  # 纳指ETF
        "159509.SZ",  # 纳指科技ETF
        "513290.SS",  # 纳指生物ETF
        "513500.SS",  # 标普500ETF
        "159529.SZ",  # 标普消费
        "513400.SS",  # 道琼斯ETF
        "513520.SS",  # 日经225ETF
        "513030.SS",  # 德国30ETF
        "513080.SS",  # 法国ETF
        "513310.SS",  # 中韩半导体ETF
        "513730.SS",  # 东南亚ETF
        "159792.SZ",  # 港股互联ETF
        "513130.SS",  # 恒生科技
        "513050.SS",  # 中概互联网ETF
        "159920.SZ",  # 恒生ETF
        "513690.SS",  # 港股红利
        # 债券ETF
        "511380.SS",  # 可转债ETF
        "511010.SS",  # 国债ETF
        "511220.SS",  # 城投债ETF
    ]

    # 商品ETF（走弱期可交易）
    g.commodity_etf_pool = [
        "518880.SS",  # 黄金ETF
        "159980.SZ",  # 有色金属ETF
        "159985.SZ",  # 豆粕ETF
        "501018.SS",  # 南方原油
        '161226.SZ',  # 白银LOF
        "159981.SZ",  # 能源化工ETF
        "512400.SS",  # 工业有色ETF
    ]

    # A股ETF（走弱期回避）
    g.domestic_etf_pool = [
        # 指数ETF
        "510300.SS",  # 沪深300ETF
        "510500.SS",  # 中证500ETF
        "510050.SS",  # 上证50ETF
        "510210.SS",  # 上证ETF
        "159915.SZ",  # 创业板ETF
        "588080.SS",  # 科创50
        "512100.SS",  # 中证1000ETF
        "563360.SS",  # A500-ETF
        "563300.SS",  # 中证2000ETF
        
        # 风格ETF
        "512890.SS",  # 红利低波ETF
        "159967.SZ",  # 创业板成长ETF
        "588020.SS",  # 科创成长ETF
        "512040.SS",  # 价值ETF
        "159201.SZ",  # 自由现金流ETF
        
        # 行业板块ETF
        "515790.SS",   # 光伏ETF
        "563230.SS",   # 卫星ETF
        "515880.SS",   # 通信ETF
        "512660.SS",   # 军工ETF
        "561380.SS",   # 电网设备ETF
        "159667.SZ",   # 工业母机ETF
        "159559.SZ",   # 机器人ETF
        "159819.SZ",   # 人工智能ETF
        "159381.SZ",   # 创业板人工智能ETF
        "159732.SZ",   # 消费电子ETF
        "159995.SZ",   # 芯片ETF
        "512220.SS",   # TMT(科技传媒通信150）ETF
    ]

    # 完整ETF池（初始化时合并）
    g.etf_pool = g.overseas_etf_pool + g.commodity_etf_pool + g.domestic_etf_pool

    # ---------- 核心参数 ----------
    g.lookback_days = 25               # 动量计算周期
    g.holdings_num = 1                 # 候选数量
    g.defensive_etf = '511010.SS'    # 避险资产：10年国债ETF（enable_defensive_etf 关时不买入）
    g.enable_defensive_etf = False     # False=无标的时空仓；True=兜底买入 511010
    g.min_money = 5000                 # 最小交易金额

    # ---------- 盈利保护参数 ----------
    g.enable_profit_protection = True                      # 盈利保护开关
    g.profit_protection_lookback = 1                       # 盈利保护回看周期（天）
    g.profit_protection_threshold = 0.05                   # 盈利保护回撤阈值（5%）

    # 盈利保护检查时间点
    g.profit_protection_check_times = ['10:57']


    g.loss = 0.97                      # 近3日单日跌幅阈值（排除）

    # ---------- 得分区间（排名宽 / 买入窄）----------
    g.rank_min_score = 0               # 排名入围下限
    g.rank_max_score = 10000.0         # 排名入围上限（实质取消，防误杀超高动量）
    g.min_score_threshold = 0          # 兼容别名 → rank_min_score
    g.max_score_threshold = 10000.0    # 兼容别名 → rank_max_score
    g.enable_buy_score_band = True     # 买入阶段得分区间开关（仅下限，不设上限）
    g.buy_min_score = 0.20             # 买入得分下限（挡极弱标的）
    g.buy_max_score = 100.0            # 买入得分上限（与排名同宽，不挡高分主线）
    g.enable_buy_annualized_cap = False  # 关闭年化上限
    g.buy_max_annualized = 5.0         # 备用（默认不启用）
    g.enable_cooldown_strict_buy_band = False  # 关闭冷却后严买入带（V3.8实测误杀高分）
    g.buy_max_score_cooldown = 2.50
    g.enable_buy_annualized_cap_cooldown = False
    g.buy_max_annualized_cooldown = 2.0
    g.harmful_sell_strict_extra_days = 0

    # ---------- 有害卖出冷却（V3.11：走弱期仅挡QDII追高，商品继续轮动）----------
    g.enable_harmful_sell_guard = True
    g.harmful_sell_last_date = None
    g.harmful_sell_last_security = None
    g.harmful_sell_cooldown_days = 0       # 正常期不暂停轮动（仅 drawdown_selled_today 禁同日买回）
    g.harmful_sell_cooldown_weak_days = 2  # 走弱期冷却交易日
    g.harmful_sell_mode_normal = 'rotation'   # 正常期：继续轮动
    g.harmful_sell_mode_weak = 'qdii_guard'   # 走弱期：仅挡海外追高，不全盘空仓

    # ---------- 走弱期有害卖后 QDII 精准防追高（V3.11）----------
    g.enable_weak_qdii_guard = True
    g.overseas_proxy_pool = [
        '159509.SZ', '513500.SS', '513520.SS', '513400.SS',
        '513290.SS', '513030.SS',
        '513130.SS', '513050.SS', '159920.SZ',
    ]
    g.correlation_lookback = 20
    g.correlation_max = 0.88

    # ---------- 海外弱判断（V3.12：独立于 A 股弱）----------
    g.enable_overseas_regime_switch = True
    g.enable_overseas_weak_shield = True
    g.is_overseas_weak = False
    g.overseas_weak_counter = 0
    g.overseas_weak_max_days = 20
    g.overseas_weak_enter_count = 2          # ≥2/4 代理走弱即进入
    g.overseas_weak_exit_count = 2           # 日频退出：≥2/4 MA5/10 回升
    g.overseas_weak_intraday_exit_count = 3  # 盘中退出：≥3/4（严于进入，防边界抖动）
    g._regime_trade_refresh_key = None       # 盘中双风险复检去重（每分钟一次）
    g.overseas_regime_proxies = {
        '纳指科技': '159509.SZ',
        '标普500': '513500.SS',
        '道琼斯': '513400.SS',
        '日经': '513520.SS',
    }
    g.overseas_bond_etfs = {
        '511380.SS',  # 可转债ETF博时
        '511010.SS',  # 国债ETF国泰
        '511220.SS',  # 城投债ETF海富通
    }

    # ---------- 海外弱时商品替代门槛（非默认兜底）----------
    g.enable_overseas_weak_commodity_gate = True
    g.buy_min_score_overseas_weak = 0.50
    g.enable_overseas_weak_cash = False      # True=海外弱无商品时空仓（与 enable_defensive_etf 独立）

    # ---------- 走弱期轮动卖海外冷却（V3.12，补 6/3）----------
    g.enable_overseas_rotation_guard = True
    g.overseas_rotation_sell_last_date = None
    g.overseas_rotation_sell_last_security = None
    g.overseas_rotation_cooldown_days = 1

    # ---------- 震荡期空仓（参考175）----------
    g.enable_range_bound_cash = True

    # ---------- 成交量过滤 ----------
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1          # 年化收益>100%时启用放量过滤

    # ---------- 短期动量过滤 ----------
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0

    # ---------- 溢价率过滤 ----------
    g.enable_premium_filter = True      # 是否启用溢价率过滤
    g.premium_threshold = 0.20          # 溢价率阈值（20%）


    # ---------- R² 过滤（参考七星175）----------
    g.enable_r2_filter = True
    g.r2_threshold = 0.35

    # ---------- 均线趋势结构硬过滤 ----------
    g.enable_trend_structure_filter = True
    g.trend_ma_period = 10
    g.trend_require_price_above_ma = True
    g.trend_require_ma5_above_ma10 = True

    # ---------- 震荡期 + 拉普拉斯/高斯（参考七星175/172）----------
    g.enable_range_bound_mode = True
    g.current_filter = '正常期'
    g.risk_state = '正常期'
    g.lookback_high_low_days = 20
    g.risk_benchmark = '510300.SS'
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.001
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002
    g.enable_bias_trigger = True
    g.bias_threshold = 0.10
    g.ma_period = 20
    g.enable_rsi_trigger = True
    g.rsi_overbought = 75
    g.rsi_pullback = 60
    g.previous_rsi = None
    g.enable_stop_loss_trigger = False
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    g.enable_low_point_rise_trigger = True
    g.low_point_rise_threshold = 0.03
    g.enable_stable_signal_trigger = True
    g.drawdown_recovery = 0.03
    g.max_range_bound_days = 15
    g.stable_days = 0
    g.filter_switch_cooldown = 2
    g.last_switch_date = None
    g.range_bound_start_date = None
    g.range_bound_days_count = 0
    g.previous_drawdown = None

    # ========== 分钟级当日回撤保护（V2.1：开关自动跟随行情状态） ==========
    g.intraday_drawdown_threshold = 0.02            # 当日回撤阈值（2%）
    g.enable_holding_prev_close_drawdown = True     # 持仓兼看昨收→现价回撤（补跳空低开）
    g.holding_profit_skip_minute_pct = 0.10       # 浮盈≥10%：分钟守卫不卖（防盈利商品早盘误杀）
    g.holding_profit_skip_prev_close_pct = 0.10   # 浮盈≥10%：13:09 不用昨收跳空触发卖
    # 注意：不再使用 g.enable_intraday_drawdown，改为在 handle_data 中动态判断
    # ================================================================

    # ==========  A股行情判断 ==========
    g.enable_regime_switch = True                    # 行情判断开关
    g.weak_period_ma_lookback = 10                   # 10日均线
    g.weak_period_max_days = 20                      # 走弱期最长持续20个交易日
    g.is_a_share_weak = False                        # 当前是否走弱期
    g.a_share_weak_daily_lock = False                # 09:40日频走弱后当日禁止盘中假恢复
    g.weak_period_counter = 0                        # 走弱期天数计数器
    g.a_share_weak_enter_count = 3                   # ≥3/6 指数走弱进入 A 股弱
    g.a_share_weak_exit_count = 3                    # 日频退出：≥3/6 MA5/10 回升
    g.a_share_intraday_exit_count = 4                # 盘中退出：≥4/6（严于进入，防边界抖动）
    # g.weak_exit_above_streak = 0                     # ≥3指数站上MA10的连续交易日数（满2日退出）
    # g.weak_exit_above_days = 2                       # 退出弱势：站上MA10须连续满足的天数
    # ==========  独立手动开关 ==========
    g.enable_avoid_a_share = True                    # 走弱期回避A股开关（关闭则走弱期不回避A股）
    g.enable_intraday_drawdown = True                # 分钟级回撤保护独立开关（关闭则不触发）
    # ==========================================
    g.regime_indexes = {                             # 监测指数（V3.3：6指数 + 价破线/MA5死叉双条件）
        '上证指数': '000001.SS',
        '沪深300': '000300.SS',
        '深证成指': '399001.SZ',
        '深证综指': '399101.SZ',
        '创业板指': '399006.SZ',
        '中证A500': '000510.SS',
    }
    # ============================================

    # ---------- 运行时变量 ----------
    g.rankings_cache = {'date': None, 'data': None}   # 排名缓存
    g.target_etfs_cache = {'date': None, 'data': None}  # 13:09 目标ETF缓存，供13:10买入复用
    g.drawdown_selled_today = set()                    # 当日因回撤/盈利保护卖出的标的（禁止日内买回）

    # 盘后总结需要的变量
    g.buy_date = {}                                    # 记录买入日期
    g.trade_log = {'sell_records': []}                 # 记录当日卖出

    # ---------- 交易调度 ----------
    run_daily(context, check_positions, time='09:12')    #开盘重置当日风控缓存、打印持仓
    run_daily(context, regime_check, time='09:40')              # 日频判定A 股弱、海外弱双风险状态（全天定调）
    run_daily(context, check_range_bound, time='13:05')         # 判断市场震荡期，切换滤波（拉普拉斯 / 高斯）
    run_daily(context, etf_sell_trade, time='13:09')            # 统一卖出：排名轮动清仓 + 13 点持仓回撤强制止损
    run_daily(context, etf_buy_trade, time='13:10')             # 复用 13:09 缓存目标买入，统一过滤避免买卖分歧
    run_daily(context, reset_range_bound_daily, time='15:10')   # 
    # run_daily(context, daily_summary_report, time='15:05')      # 盘后总结

    # 动态注册盈利保护检查时间点
    for check_time in g.profit_protection_check_times:
        run_daily(context, profit_protection_check, time=check_time)
        log.info(f"📅 已注册盈利保护检查时间：{check_time}")

    # V2.2 日志
    if g.enable_regime_switch:
        log.info(f"🌍 A股行情判断已启用，走弱期最长{g.weak_period_max_days}日")
        if g.enable_avoid_a_share:
            log.info(f"🔄 走弱期回避A股开关：ON（走弱期自动回避A股ETF）")
        else:
            log.info(f"⚠️ 走弱期回避A股开关：OFF（走弱期仍交易A股ETF）")
        if g.enable_intraday_drawdown:
            log.info(f"🛡️ 分钟级回撤保护开关：ON（走弱期自动启用）")
        else:
            log.info(f"⭕ 分钟级回撤保护开关：OFF（不触发）")
    else:
        log.info("⚠️ A股行情判断未启用")

    log.info(f"📋 策略初始化完成：ETF池{len(g.etf_pool)}只（海外{len(g.overseas_etf_pool)}只+商品{len(g.commodity_etf_pool)}只+A股{len(g.domestic_etf_pool)}只）")
    log.info(f"📈 盈利保护：{'开' if g.enable_profit_protection else '关'}，回撤{g.profit_protection_threshold*100:.0f}%")
    log.info(
        f"💰 盈利仓回撤豁免：分钟不卖≥{g.holding_profit_skip_minute_pct*100:.0f}%浮盈；"
        f"13:09不卖昨收跳空≥{g.holding_profit_skip_prev_close_pct*100:.0f}%浮盈"
    )
    if g.enable_premium_filter:
        log.info(f"💰 溢价率过滤已启用，阈值：{g.premium_threshold*100:.0f}%")
    else:
        log.info("⚠️ 溢价率过滤未启用")

    marker = getattr(g, 'strategy_log_marker', '[QX3.14]')
    log.info(f"{marker} 策略版本：{g.strategy_version} | STRATEGY_ID={g.strategy_id}")
    log.info("%s 走弱有害卖=%s 弱QDII守卫=%s 海外弱屏蔽=%s 轮动卖挡海外=%s rank_max=%.0f" % (
        marker, g.harmful_sell_mode_weak,
        'on' if g.enable_weak_qdii_guard else 'off',
        'on' if g.enable_overseas_weak_shield else 'off',
        'on' if g.enable_overseas_rotation_guard else 'off',
        g.rank_max_score))
    if g.enable_overseas_regime_switch:
        log.info(
            "🌐 海外弱判断：ON 进入≥%d/4 日退≥%d/4 盘中退≥%d/4 商品替代下限=%.2f" % (
                g.overseas_weak_enter_count, g.overseas_weak_exit_count,
                g.overseas_weak_intraday_exit_count, g.buy_min_score_overseas_weak,
            )
        )
    log.info(
        "🛡️ 双风险规避定版：A股弱≥%d/6回避A股 | 海外弱屏蔽QDII | 双弱→仅商品 | 防御511010=%s"
        % (g.a_share_weak_enter_count, "开" if g.enable_defensive_etf else "关(空仓)")
    )
    log.info("📐 趋势过滤：均线=%s R2=%s 滤波=%s(%s)" % (
        "开" if g.enable_trend_structure_filter else "关",
        "开" if g.enable_r2_filter else "关",
        "开" if g.enable_range_bound_mode else "关", g.current_filter))
    log.info("📊 买入得分：%s 下限=%.2f 上限=%.0f(同排名) 年化上限=关 冷却严带=关" % (
        "开" if g.enable_buy_score_band else "关",
        g.buy_min_score, g.buy_max_score))
    log.info("🛡️ 有害卖出冷却：%s 正常=仅禁同日买回 走弱%d日空仓 震荡期空仓=%s" % (
        "开" if g.enable_harmful_sell_guard else "关",
        g.harmful_sell_cooldown_weak_days,
        "开" if g.enable_range_bound_cash else "关"))
    
    
    #### PT多策略隔离初始化开始...
    # 配置Pandas显示参数（关键）, 便于打印显示对齐
    # 解决中文 打印对齐问题
    pd.set_option('display.unicode.ambiguous_as_wide', True)
    pd.set_option('display.unicode.east_asian_width', True)
    # 显示所有列
    pd.set_option('display.width', None)                      # 自动适配终端宽度
    pd.set_option('display.max_columns', None)                # 显示所有列
    pd.set_option('display.max_colwidth', None)               # 显示列内容完整宽度
    # # 防止列名折叠
    pd.set_option('display.expand_frame_repr', False)
    
    # Python 简洁版本字符串， 不同版本API有差异。
    g.python_version = platform.python_version()
    if g.python_version.startswith('3.5'):
        log.info("Python版本={}".format(g.python_version))
    else:
        log.info("Python版本={}".format(g.python_version))
    
    g.strategy_name = "七星三池V175"       # 手工配置，   策略名称。
    g.use_orig_portfolio_data = False    # 手工配置，   是否使用原始总仓数据,  True表示使用总仓数据，  False 表示使用分仓数据。 
    
    g.fq_type = 'dypre'                  # fq：数据复权选项，支持包括，pre-前复权，post-后复权，dypre-动态前复权，None-不复权；选填参数，默认为None；入参类型：str；

    g.order_api_type = "order"  #"order"     # 手工配置： 买入调用哪个order接口,  
    g.sell_api_type = "order"   # 手工配置： 卖出调用哪个order接口,
                                         # "order_market_five_dealed" - 按市价进行委托(五档即时成交),    
                                         # "order_market_peer_price" - 按市价进行委托(对手最优价成交),  
                                         # "order_target_value"--调整股票持仓市值到value价值 (多策略同标的时不能用)
                                         # "order" - 按数量买卖, 同None， 缺省值调用order接口。
                                         # "observe_not_buy" - 只观察， 不买入。
    # 回测时不能调用  order_market 接口。                                                                                  
    if not is_trade() and (g.order_api_type == "order_market_five_dealed" or g.order_api_type == "order_market_peer_price"):
        g.order_api_type = "order_target_value"
        
                                        # 买卖队列，   如果买入标的 要等 卖队列中标的成交才可以买入， 需要增加这个队列。  
    g.sell_queue = []                   # 卖出队列，   格式： ["002222.SZ","601111.SZ"]
    g.buy_queue = {}                    # 买入队列,    格式： {'001654.SZ': {"symbol": '001654.SZ', "buy_value": 10000, "limit_price": 10.1, "callback": None}}
    g.auto_append_sell_queue = True     # 缺省所有卖操作自动入卖方队列， 这样需要等所有卖操作完成才自动执行买操作。 如果买入操作不要等卖出操作完成，需要将这个标志设置成False

    
    g.re_order_interval = 120            # 轮询任务间隔：如果订单 下单后超过这个时间间隔没有成交， 就撤单重新提交。 单位：秒, 建议至少60S以上。 
    if is_trade() and g.re_order_interval > 60:                       # 实盘场景的周期任务， 注意是多线程。 
        run_interval(context, sub_interval_job_re_order_handle, seconds=g.re_order_interval) #1、订单超时重新下单的任务。

    # 每个策略都有需要持久化的参数， 这里设置需要持久化的全局变量, 只支持JSON格式。 如：g.black_list, 
    g.need_persistent_list = ["etf_pool", "triger_time"]
    
    # 设置本策略可以使用的资金， 本策略所有持仓， 资金数据都保存在g.__sub_portfolio 
    g.__sub_portfolio = sub_init_strategy_portfolio(context, init_cash=100000)

    # 首次运行时，根据历史数据判断当前是否处于震荡期
    init_range_bound_status(context)
    # run_daily(context, init_range_bound_status, time='09:12')
    
    #初始资金 {g.__sub_portfolio.init_cash}, 
    log.info(f" {g.strategy_name} 策略初始化成功， 可用资金 = {g.__sub_portfolio.cash}")
    return

# ==================== 开盘检查模块 ====================
def check_positions(context):
    """每日开盘检查持仓状态"""

    # 日期标记
    log.info(f"\n{'='*22}🐂🧨🧨🧨🧨🧨{context.current_dt.strftime('%Y-%m-%d')}📌策略运行开始📌一路长红🧨🧨🧨🧨🧨🐂{'='*22}")

    g.drawdown_selled_today = set()                    # 清空当日回撤卖出缓存
    g.a_share_weak_daily_lock = False                    # 新交易日重置，09:40日频后再锁定
    g.target_etfs_cache = {'date': None, 'data': None}
    g.trade_log['sell_records'] = []
    positions = sub_get_strategy_positions(context)
    for sec in positions:
        pos = positions[sec]
        if pos.amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.amount} 成本{pos.cost_basis:.3f} 现价{pos.last_sale_price:.3f}")

# ====================  行情判断模块 ====================
def _index_live_price(context, code):
    """指数/ETF 盘中现价。"""
    try:
        price = sub_get_current_price(code, context)
        if price is not None and price > 0:
            return price
    except Exception:
        pass
    return None


def compute_a_share_regime_signals(context, use_intraday=False):
    """统计 6 指数 A 股弱信号。盘中模式用现价对已完成日 K 的 MA。"""
    below_count, ma_weak_count, ma_recover_count = 0, 0, 0
    detail = []
    need_days = max(g.weak_period_ma_lookback, 5) + 1
    price_tag = '盘中' if use_intraday else '日频'

    for name, code in g.regime_indexes.items():
        try:
            # df = attribute_history(code, need_days + 2, '1d', ['close'], skip_paused=False)
            df = pt_get_history(need_days + 2, frequency='1d', field=['close'], security_list=code, fq=g.fq_type, include=False)        
            if df.empty or len(df) < need_days + 1:
                continue
            closes = df['close'].values

            if use_intraday:
                live = _index_live_price(context, code)
                current_price = live if live is not None else closes[-1]
                base = closes[:-1] if len(closes) > need_days else closes
                if len(base) < g.weak_period_ma_lookback + 1:
                    continue
                ma10 = base[-g.weak_period_ma_lookback:].mean()
                ma5 = base[-5:].mean()
                ma10_prev = base[-(g.weak_period_ma_lookback + 1):-1].mean()
                ma5_prev = base[-6:-1].mean()
            else:
                current_price = closes[-1]
                ma10 = closes[-g.weak_period_ma_lookback:].mean()
                ma5 = closes[-5:].mean()
                ma10_prev = closes[-(g.weak_period_ma_lookback + 1):-1].mean()
                ma5_prev = closes[-6:-1].mean()

            if current_price < ma10:
                below_count += 1
                detail.append(f"{name}↓")
            else:
                detail.append(f"{name}↑")
            death_cross = ma5 < ma10 and ma5_prev >= ma10_prev
            if death_cross or ma5 < ma10:
                ma_weak_count += 1
                tag = '死叉' if death_cross else 'MA5<10'
                detail[-1] = detail[-1] + f'({tag})'
            if ma5 > ma5_prev and ma10 > ma10_prev:
                ma_recover_count += 1
                detail[-1] = detail[-1] + '(MA5↑10↑)'
        except Exception as e:
            log.warning(f"⚠️ 指数{name}获取失败: {e}")

    return below_count, ma_weak_count, ma_recover_count, detail, price_tag


def _log_a_share_transition(entering_weak):
    if entering_weak:
        if g.enable_avoid_a_share:
            log.info("   → 将回避A股ETF，仅交易海外+商品ETF")
        else:
            log.info("   → ⚠️ 回避A股开关已关闭，仍交易全市场ETF")
        if g.enable_intraday_drawdown:
            log.info(f"   → 🛡️ 分钟级回撤保护已启用（阈值{g.intraday_drawdown_threshold*100:.0f}%）")
        else:
            log.info("   → ⭕ 分钟级回撤保护已被独立开关关闭，不触发")
    else:
        if g.enable_avoid_a_share:
            log.info("   → 恢复交易A股ETF")
        else:
            log.info("   → 回避A股开关关闭，始终交易全市场")
        if g.enable_intraday_drawdown:
            log.info("   → 关闭分钟级回撤保护")
        else:
            log.info("   → 分钟级回撤保护独立开关已关闭，无变化")


def _apply_a_share_regime_state(context, below_count, ma_weak_count, ma_recover_count,
                                detail, mode='daily'):
    """应用 A 股弱状态迁移；边界 enter+exit 同时满足时维持原状。"""
    enter_n = g.a_share_weak_enter_count
    exit_n = (
        g.a_share_intraday_exit_count if mode == 'intraday'
        else g.a_share_weak_exit_count
    )
    would_enter = below_count >= enter_n or ma_weak_count >= enter_n
    would_exit = ma_recover_count >= exit_n
    old_state = g.is_a_share_weak
    prefix = '🕐盘中' if mode == 'intraday' else ''

    if not g.is_a_share_weak:
        if would_enter:
            g.is_a_share_weak = True
            g.weak_period_counter = 0
            reasons = []
            if below_count >= enter_n:
                reasons.append(f"价破线:{below_count}")
            if ma_weak_count >= enter_n:
                reasons.append(f"MA5弱:{ma_weak_count}")
            log.info(f"🔴 {prefix}进入走弱期 ({' + '.join(reasons)} {detail})")
            _log_a_share_transition(True)
    else:
        if mode == 'daily':
            g.weak_period_counter += 1
        if would_exit and would_enter:
            log.info(f"⚖️ {prefix}A股弱边界僵持(进/退同触)，维持走弱期 {detail}")
        elif would_exit:
            if mode == 'intraday' and g.a_share_weak_daily_lock:
                log.info(
                    f"🔒 {prefix}日频已确认走弱，忽略盘中假恢复，维持走弱期 {detail}"
                )
            else:
                g.is_a_share_weak = False
                g.weak_period_counter = 0
                log.info(f"🟢 {prefix}恢复正常期 (≥{exit_n}指数MA5/10↑:{ma_recover_count} {detail})")
                _log_a_share_transition(False)
        elif mode == 'daily' and g.weak_period_counter >= g.weak_period_max_days:
            g.is_a_share_weak = False
            g.weak_period_counter = 0
            log.info(f"⏰ 走弱期满{g.weak_period_max_days}日强制退出，恢复正常期")
            _log_a_share_transition(False)

    state_changed = old_state != g.is_a_share_weak
    if state_changed:
        g.rankings_cache = {'date': None, 'data': None}
        if mode == 'intraday':
            g.target_etfs_cache = {'date': None, 'data': None}
    return state_changed


def a_share_regime_check(context):
    """09:40 日频 A 股弱判断。
1. A 股弱判断（6 大指数监测）
    
监测指数：上证、沪深 300、深成指、深综指、创业板、中证 A500
进入走弱期（满足其一）：
≥3 只指数现价 < MA10；
≥3 只指数 MA5 死叉 / MA5<MA10；
退出规则（迟滞防反复）：
日频退出：≥3 指数 MA5、MA10 同步上行；
盘中退出门槛更严（4/6），且 09:40 判定走弱后当日锁定，忽略盘中假反弹；
最多连续走弱 20 个交易日强制恢复正常。
    """
    if not g.enable_regime_switch:
        g.is_a_share_weak = False
        return False
    signals = compute_a_share_regime_signals(context, use_intraday=False)
    changed = _apply_a_share_regime_state(context, *signals[:4], mode='daily')
    ma_recover = signals[2]
    if g.enable_regime_switch:
        current_status = '🔴走弱期' if g.is_a_share_weak else '🟢正常期'
        avoid_status = (
            '(回避A股)' if (g.is_a_share_weak and g.enable_avoid_a_share)
            else ('(不回避A股)' if g.is_a_share_weak else '')
        )
        drawdown_status = (
            '🛡️启用' if (g.is_a_share_weak and g.enable_intraday_drawdown)
            else '⭕关闭'
        )
        recover_info = (
            f" MA5/10↑:{ma_recover}/{len(g.regime_indexes)}"
            if g.is_a_share_weak else ""
        )
        log.info(
            f"📊 当前状态：{current_status}{avoid_status} "
            f"计数:{g.weak_period_counter}/{g.weak_period_max_days}{recover_info}"
        )
        log.info(f"📊 分钟级回撤保护：{drawdown_status}（阈值{g.intraday_drawdown_threshold*100:.0f}%）")
    g.a_share_weak_daily_lock = bool(g.is_a_share_weak)
    return changed


def regime_check(context):
    """每日 9:40 双风险日频定调：A 股弱 + 海外弱。"""
    log.info("🌍 ========== 行情判断开始（双风险日频）==========")
    overseas_regime_check(context)
    a_share_regime_check(context)
    log.info("🌍 ========== 行情判断完成 ==========")


def _overseas_proxy_live_price(context, code):
    """盘中海外代理现价；无效时返回 None。"""
    try:
        price = sub_get_current_price(code, context)
        if price is not None and price > 0:
            return price
    except Exception:
        pass
    return None


def compute_overseas_regime_signals(context, use_intraday=False):
    """统计 4 代理海外弱信号。盘中模式用现价对已完成日 K 的 MA。"""
    below_count, ma_weak_count, ma_recover_count = 0, 0, 0
    detail = []
    need_days = max(g.weak_period_ma_lookback, 5) + 1
    price_tag = '盘中' if use_intraday else '日频'

    for name, code in g.overseas_regime_proxies.items():
        try:
            # df = attribute_history(code, need_days + 2, '1d', ['close'], skip_paused=False)
            df = pt_get_history(need_days + 2, frequency='1d', field=['close'], security_list=code, fq=g.fq_type, include=False)
            if df.empty or len(df) < need_days + 1:
                continue
            closes = df['close'].values

            if use_intraday:
                live = _overseas_proxy_live_price(context, code)
                current_price = live if live is not None else closes[-1]
                base = closes[:-1] if len(closes) > need_days else closes
                if len(base) < g.weak_period_ma_lookback + 1:
                    continue
                ma10 = base[-g.weak_period_ma_lookback:].mean()
                ma5 = base[-5:].mean()
                ma10_prev = base[-(g.weak_period_ma_lookback + 1):-1].mean()
                ma5_prev = base[-6:-1].mean()
            else:
                current_price = closes[-1]
                ma10 = closes[-g.weak_period_ma_lookback:].mean()
                ma5 = closes[-5:].mean()
                ma10_prev = closes[-(g.weak_period_ma_lookback + 1):-1].mean()
                ma5_prev = closes[-6:-1].mean()

            if current_price < ma10:
                below_count += 1
                detail.append(f"{name}↓")
            else:
                detail.append(f"{name}↑")
            death_cross = ma5 < ma10 and ma5_prev >= ma10_prev
            if death_cross or ma5 < ma10:
                ma_weak_count += 1
                tag = '死叉' if death_cross else 'MA5<10'
                detail[-1] = detail[-1] + f'({tag})'
            if ma5 > ma5_prev and ma10 > ma10_prev:
                ma_recover_count += 1
                detail[-1] = detail[-1] + '(MA5↑10↑)'
        except Exception as e:
            log.warning(f"⚠️ 海外代理{name}获取失败: {e}")

    return below_count, ma_weak_count, ma_recover_count, detail, price_tag


def _apply_overseas_regime_state(context, below_count, ma_weak_count, ma_recover_count,
                                 detail, mode='daily'):
    """应用海外弱状态迁移；边界 enter+exit 同时满足时维持原状（迟滞）。"""
    enter_n = g.overseas_weak_enter_count
    if mode == 'intraday':
        exit_n = g.overseas_weak_intraday_exit_count
    else:
        exit_n = g.overseas_weak_exit_count

    would_enter = below_count >= enter_n or ma_weak_count >= enter_n
    would_exit = ma_recover_count >= exit_n
    old_state = g.is_overseas_weak
    prefix = '🕐盘中' if mode == 'intraday' else ''

    if not g.is_overseas_weak:
        if would_enter:
            g.is_overseas_weak = True
            g.overseas_weak_counter = 0
            reasons = []
            if below_count >= enter_n:
                reasons.append(f"价破线:{below_count}")
            if ma_weak_count >= enter_n:
                reasons.append(f"MA5弱:{ma_weak_count}")
            log.info(f"🔴 {prefix}进入海外弱 ({' + '.join(reasons)} {detail})")
    else:
        if mode == 'daily':
            g.overseas_weak_counter += 1
        if would_exit and would_enter:
            log.info(f"⚖️ {prefix}海外弱边界僵持(进/退同触)，维持海外弱 {detail}")
        elif would_exit:
            g.is_overseas_weak = False
            g.overseas_weak_counter = 0
            log.info(f"🟢 {prefix}海外弱恢复 (≥{exit_n}代理MA5/10↑:{ma_recover_count} {detail})")
        elif mode == 'daily' and g.overseas_weak_counter >= g.overseas_weak_max_days:
            g.is_overseas_weak = False
            g.overseas_weak_counter = 0
            log.info(f"⏰ 海外弱满{g.overseas_weak_max_days}日强制退出 {detail}")

    state_changed = old_state != g.is_overseas_weak
    if state_changed:
        g.rankings_cache = {'date': None, 'data': None}
        if mode == 'intraday':
            g.target_etfs_cache = {'date': None, 'data': None}
    if state_changed or g.is_overseas_weak:
        ostatus = '🔴海外弱' if g.is_overseas_weak else '🟢海外正常'
        log.info(f"🌐 海外状态：{ostatus} 计数:{g.overseas_weak_counter}/{g.overseas_weak_max_days}")
    return state_changed


def overseas_regime_check(context):
    """09:40 日频海外弱判断（独立于 A 股弱）。
海外弱判断（4 大 QDII 代理）
代理标的：纳指科技、标普 500、道琼斯、日经 225
进入海外弱：≥2/4 代理跌破 MA10 或 MA5 走弱；
退出门槛更高（盘中 3/4、日频 2/4），同样带边界僵持机制（同时满足进 / 出条件维持原状态，防频繁切换）。    
    """
    if not g.enable_overseas_regime_switch:
        g.is_overseas_weak = False
        return False
    signals = compute_overseas_regime_signals(context, use_intraday=False)
    return _apply_overseas_regime_state(context, *signals[:4], mode='daily')


def refresh_regime_for_trade(context):
    """13:09/13:10 双风险盘中复检（A股弱+海外弱）；同一分钟只执行一次。"""
    key = (context.current_dt.date(), context.current_dt.strftime('%H%M'))
    if getattr(g, '_regime_trade_refresh_key', None) == key:
        return False
    g._regime_trade_refresh_key = key
    changed = False
    if g.enable_overseas_regime_switch:
        signals = compute_overseas_regime_signals(context, use_intraday=True)
        below, ma_weak, ma_recover, detail, price_tag = signals
        log.info(f"🕐 盘中海外弱复检({price_tag}) 价破:{below} MA弱:{ma_weak} MA回升:{ma_recover}")
        changed |= _apply_overseas_regime_state(
            context, below, ma_weak, ma_recover, detail, mode='intraday'
        )
    if g.enable_regime_switch:
        signals = compute_a_share_regime_signals(context, use_intraday=True)
        below, ma_weak, ma_recover, detail, price_tag = signals
        log.info(f"🕐 盘中A股弱复检({price_tag}) 价破:{below} MA弱:{ma_weak} MA回升:{ma_recover}")
        changed |= _apply_a_share_regime_state(
            context, below, ma_weak, ma_recover, detail, mode='intraday'
        )
    return changed


def refresh_overseas_regime_for_trade(context):
    """兼容别名 → 双风险盘中复检。"""
    return refresh_regime_for_trade(context)


def is_overseas_qdii(etf):
    """海外池中的 QDII 权益类（不含债券）。"""
    bond_set = getattr(g, 'overseas_bond_etfs', set())
    return etf in g.overseas_etf_pool and etf not in bond_set


def is_intraday_drawdown_enabled():
    """判断分钟级回撤保护是否启用
    V2.2: 优先判断独立开关，关闭则不触发；开启则走弱期自动启用"""
    # 独立开关关闭 → 不触发
    if not g.enable_intraday_drawdown:
        return False
    # 行情判断未启用 → 不触发
    if not g.enable_regime_switch:
        return False
    # 走弱期自动启用
    return g.is_a_share_weak


def get_active_etf_pool():
    """根据 A 股弱 × 海外弱 四格矩阵返回可排名池（V3.12）。"""
    overseas_shield = (
        g.enable_overseas_weak_shield
        and g.enable_overseas_regime_switch
        and g.is_overseas_weak
    )

    if not g.enable_avoid_a_share:
        if overseas_shield and g.is_a_share_weak:
            active_pool = list(g.commodity_etf_pool)
            log.info(f"📊 【A弱+海外弱】仅商品池({len(active_pool)}只) [回避A股关]")
        elif overseas_shield:
            active_pool = list(g.domestic_etf_pool) + list(g.commodity_etf_pool)
            log.info(f"📊 【海外弱】A股+商品池({len(active_pool)}只) [回避A股关]")
        else:
            active_pool = list(g.etf_pool)
            log.info(f"📊 【强制】A股回避关，完整池({len(active_pool)}只)")
        return active_pool

    if g.is_a_share_weak:
        if overseas_shield:
            active_pool = list(g.commodity_etf_pool)
            log.info(f"📊 【A弱+海外弱】仅商品池({len(active_pool)}只)")
        else:
            active_pool = list(g.overseas_etf_pool) + list(g.commodity_etf_pool)
            log.info(f"📊 【走弱期】海外+商品池({len(active_pool)}只)")
    elif overseas_shield:
        active_pool = list(g.domestic_etf_pool) + list(g.commodity_etf_pool)
        log.info(f"📊 【海外弱】A股+商品池({len(active_pool)}只)")
    else:
        active_pool = list(g.etf_pool)
        log.info(f"📊 【正常期】完整池({len(active_pool)}只)")
    return active_pool


# ==================== 分钟级回测入口：每分钟执行一次 ====================
def handle_data(context, data):
    """当回测/实盘频率设为'分钟'时，此函数每分钟自动调用一次。 走弱期分钟级 2% 回撤动态守卫
    V2.1: 只在走弱期执行回撤检查，正常期跳过
    V2.2: 受独立开关控制"""
    # V2.2: 动态判断是否启用（独立开关 + 走弱期）
    if not is_intraday_drawdown_enabled():
        return

    # 9:46 之后才执行检查
    current_time = context.current_dt.strftime('%H:%M')
    if current_time < '09:46':
        return

    intraday_drawdown_check(context)


# ==================== 分钟级当日回撤检查函数 ====================
def intraday_drawdown_check(context):
    """每分钟执行一次，检查所有持仓从当日盘中最高点的回撤。
    V2.1: 此函数仅在走弱期被调用
    V2.2: 受独立开关控制"""
    positions = sub_get_strategy_positions(context)
    for sec in list(positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = positions[sec]
        if pos.enable_amount == 0:
            continue
        # 跳过当日买入的ETF（避免刚买入就被日内回撤保护卖出）
        if g.buy_date.get(sec) == context.current_dt.date():
            continue

        try:
            drawdown, detail, threshold = get_holding_drawdown_for_sell(
                sec, context, source='minute'
            )
            if (
                drawdown is not None
                and threshold is not None
                and drawdown >= threshold
            ):
                execute_intraday_drawdown_sell(
                    context, sec, drawdown, source='分钟级',
                    detail=detail, threshold=threshold
                )
        except Exception as e:
            log.debug(f"分钟级回撤检查异常 {sec}: {e}")


# ==================== 盈利保护独立检查函数 ====================
@time_monitor(func_name="盈利保护检查")
def profit_protection_check(context):
    """独立执行的盈利保护检查函数"""
    if not g.enable_profit_protection:
        log.debug("盈利保护模块已关闭，跳过检查")
        return

    log.info("🛡️ ========== 盈利保护检查开始 ==========")
    positions = sub_get_strategy_positions(context)
    for sec in list(positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = positions[sec]
        if pos.amount > 0:
            if check_profit_protection(sec, context):
                if smart_order_target_value(sec, 0, context):
                    log.info(f"🛡️ 盈利保护卖出：{sec} {get_name(sec)}")
                    g.drawdown_selled_today.add(sec)
                    mark_harmful_sell(context, sec)
                    if getattr(g, 'enable_stop_loss_trigger', False):
                        g.stop_loss_triggered_today = True
                        g.stop_loss_triggered_date = context.current_dt.date()
    log.info("🛡️ ========== 盈利保护检查完成 ==========")


# ==================== 盈利保护检查函数（核心逻辑） ====================
def check_profit_protection(security, context, lookback=None, threshold=None):
    """检查是否触发盈利保护（从最近N日最高点回撤超过阈值）"""
    if not g.enable_profit_protection:
        return False

    lookback = lookback or g.profit_protection_lookback
    threshold = threshold or g.profit_protection_threshold

    hist = pt_get_history(lookback, frequency='1d', field=['high'], security_list=security, fq=g.fq_type, include=False)
    if hist.empty or len(hist) < lookback:
        return False

    max_high = hist['high'].max()
    current_price = sub_get_current_price(security, context)
    if current_price <= max_high * (1 - threshold):
        log.info(f"🔻 盈利保护触发 {security} 回撤{(1-current_price/max_high)*100:.2f}% > {threshold*100:.0f}%")
        return True
    return False


# ==================== 溢价率获取函数 ====================
def pt_get_premium_rate(code, date, max_back_days=5):
    """_summary_
    PTrade 获取ETF溢价率的
    Args:
        code (_type_): _description_
        date (_type_): _description_
        max_back_days (int, optional): _description_. Defaults to 5.

    Returns:
        _type_: _description_
    """

    if not is_trade():
        return 0, 0, 0

    snapshot = get_snapshot(code)
    etf_price = snapshot[code]["last_px"]
    nav = snapshot[code]["iopv"]

    # 只有ETF在盘中才发布IOPV， LOF在盘中不发布IOPV。
    if float(nav) > 0:
        premium_rate = (etf_price - float(nav)) / float(nav)
    else:
        premium_rate = 0
        
    return premium_rate, etf_price, nav

# ==================== 震荡期机制（拉普拉斯/高斯，参考七星175）====================
def calculate_rsi(close, period=14):
    try:
        if len(close) < period + 1:
            return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    except Exception:
        return None


def laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def gaussian_filter_last_two(price, sigma=1.2):
    n = len(price)
    if n < 2:
        return 0, 0
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


def get_risk_benchmark_state(context):
    required_days = max(g.ma_period, g.lookback_high_low_days)
    lookback = required_days + 30

    end_date = context.previous_date.strftime("%Y-%m-%d")    
    df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,frequency='1d', fields=['close', 'high', 'low'], fq=g.fq_type)
    
    # df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,
    #                frequency='daily', fields=['close', 'high', 'low'], panel=False)
    if df is None or len(df) < required_days:
        return None
    daily_close = df['close'].values.astype(float)
    daily_high = df['high'].values.astype(float)
    daily_low = df['low'].values.astype(float)
    current_price = float(daily_close[-1])
    intraday_high = current_price
    intraday_low = current_price
    data_source = '昨日日线'
    try:
        # today = context.current_dt.date()
        # minute_df = get_price(
        #     g.risk_benchmark, start_date=today, end_date=context.current_dt,
        #     frequency='1m', fields=['close', 'high', 'low'], panel=False, fill_paused=False
        # )

        total_minutes =  get_today_exchanged_minutes(context)
        minute_df = pt_get_history(total_minutes, frequency='1m', field=['close', 'high', 'low'], security_list=g.risk_benchmark, fq=g.fq_type,include=True)   
        if minute_df is not None and not minute_df.empty:
            minute_close = minute_df['close'].dropna()
            minute_high = minute_df['high'].dropna()
            minute_low = minute_df['low'].dropna()
            if not minute_close.empty:
                current_price = float(minute_close.iloc[-1])
                intraday_high = float(minute_high.max()) if not minute_high.empty else current_price
                intraday_low = float(minute_low.min()) if not minute_low.empty else current_price
                data_source = '当日盘中'
    except Exception:
        pass
    if current_price <= 0:
        try:
            live_price = sub_get_current_price(g.risk_benchmark, context)
            if live_price is not None and live_price > 0:
                current_price = float(live_price)
                intraday_high = max(intraday_high, current_price)
                intraday_low = min(intraday_low, current_price)
                data_source = '实时快照'
        except Exception:
            current_price = float(daily_close[-1])
    close_series = np.append(daily_close, current_price)
    high_series = np.append(daily_high, max(intraday_high, current_price))
    low_series = np.append(daily_low, min(intraday_low, current_price))
    recent_high = np.max(high_series[-g.lookback_high_low_days:])
    recent_low = np.min(low_series[-g.lookback_high_low_days:])
    ma = np.mean(close_series[-g.ma_period:])
    current_rsi = calculate_rsi(close_series, period=14)
    previous_rsi = calculate_rsi(daily_close, period=14)
    return {
        'close_series': close_series,
        'high_series': high_series,
        'low_series': low_series,
        'current_price': current_price,
        'recent_high': recent_high,
        'recent_low': recent_low,
        'ma': ma,
        'current_rsi': current_rsi,
        'previous_rsi': previous_rsi,
        'data_source': data_source,
    }


def is_fresh_stop_loss_signal(context):
    signal_date = getattr(g, 'stop_loss_triggered_date', None)
    if signal_date is None:
        return False
    today = context.current_dt.date()
    previous_date = getattr(context, 'previous_date', None)
    if signal_date == today:
        return True
    if previous_date is not None and signal_date == previous_date:
        return True
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    return False


def init_range_bound_status(context):
    if not g.enable_range_bound_mode:
        return
    log.info("【首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None:
            return
        # end_date = context.previous_date
        # # lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        # # df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,
        # #                frequency='daily', fields=['close', 'high', 'low'], panel=False)
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30        
        end_date = context.previous_date.strftime("%Y-%m-%d")
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,frequency='1d', fields=['close', 'high', 'low'], fq=g.fq_type)
        
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        recent_high = np.max(high[-g.lookback_high_low_days:]) if len(close) >= g.lookback_high_low_days else np.max(high)
        ma = np.mean(close[-g.ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        current_rsi = calculate_rsi(close, period=14)
        should_enter = False
        signals = []
        if g.enable_bias_trigger and bias > g.bias_threshold:
            should_enter = True
            signals.append(f"乖离率{bias:.2%}")
        if g.enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback:
                should_enter = True
                signals.append(f"RSI回落{prev_rsi:.1f}->{current_rsi:.1f}")
        if should_enter:
            g.current_filter = '震荡期'
            g.risk_state = '震荡期'
            g.range_bound_start_date = end_date
            log.info(f"【首次运行】初始化进入震荡期: {'; '.join(signals)}")
        else:
            g.current_filter = '正常期'
            g.risk_state = '正常期'
            g.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            g.previous_rsi = current_rsi
            log.info(f"【首次运行】初始状态: 正常期(拉普拉斯)")
    except Exception as e:
        log.warning(f"【首次运行】震荡期初始化异常: {e}")


def check_and_exit_range_bound_mode(context):
    if not g.enable_range_bound_mode or g.current_filter != '震荡期':
        return
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is None:
            return
        close = benchmark_state['close_series']
        current_price = benchmark_state['current_price']
        recent_high = benchmark_state['recent_high']
        recent_low = benchmark_state['recent_low']
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        recovery_signals = []
        ma = benchmark_state['ma']
        current_rsi = benchmark_state['current_rsi']
        if g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold:
            recovery_signals.append(f"从低点涨{rise_from_low:.2%}")
        if g.enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("站上均线")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                recovery_signals.append("回撤收窄")
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                recovery_signals.append("RSI回升")
            if current_drawdown < g.drawdown_recovery:
                g.stable_days += 1
            else:
                g.stable_days = 0
        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi
        range_bound_days = 0
        if g.range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
        low_point_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_condition = False
        if g.enable_stable_signal_trigger:
            stable_condition = current_drawdown < g.drawdown_recovery and len(recovery_signals) >= 2 and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days
        if low_point_condition or stable_condition or force_condition:
            can_switch = True
            if g.last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
                if len(trade_days) - 1 < g.filter_switch_cooldown:
                    can_switch = False
            if can_switch:
                g.current_filter = '正常期'
                g.risk_state = '正常期'
                g.last_switch_date = context.current_dt.date()
                g.range_bound_start_date = None
                g.stable_days = 0
                log.info(f"【退出震荡期】切回拉普拉斯: {'; '.join(recovery_signals)}")
    except Exception as e:
        log.warning(f"【震荡期退出检查】异常: {e}")


def check_and_enter_range_bound_mode(context):
    if not g.enable_range_bound_mode:
        return
    if g.current_filter == '震荡期':
        return
    if g.last_switch_date is not None:
        trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
        if len(trade_days) - 1 < g.filter_switch_cooldown:
            return
    risk_signals = []
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is not None:
            if g.enable_bias_trigger:
                ma = benchmark_state['ma']
                bias = (benchmark_state['current_price'] - ma) / ma if ma > 0 else 0
                if bias > g.bias_threshold:
                    risk_signals.append(f"乖离率{bias:.2%}")
            if g.enable_rsi_trigger:
                current_rsi = benchmark_state['current_rsi']
                prev_rsi = benchmark_state['previous_rsi']
                if prev_rsi is not None and current_rsi is not None:
                    if prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                        risk_signals.append(f"RSI回落{prev_rsi:.1f}->{current_rsi:.1f}")
    except Exception as e:
        log.warning(f"【震荡期检查】异常: {e}")
    if g.enable_stop_loss_trigger and is_fresh_stop_loss_signal(context):
        risk_signals.append("盈利保护止损")
    if risk_signals:
        g.current_filter = '震荡期'
        g.risk_state = '震荡期'
        g.last_switch_date = context.current_dt.date()
        g.range_bound_start_date = context.current_dt.date()
        g.stable_days = 0
        log.info(f"【进入震荡期】切至高斯: {'; '.join(risk_signals)}")


def check_range_bound(context):
    if not g.enable_range_bound_mode:
        return
    log.info("========== 震荡期检查开始 ==========")
    prev_filter = g.current_filter
    check_and_exit_range_bound_mode(context)
    check_and_enter_range_bound_mode(context)
    log.info(f"震荡期状态: {g.current_filter}")
    if prev_filter != g.current_filter:
        g.rankings_cache = {'date': None, 'data': None}
        g.target_etfs_cache = {'date': None, 'data': None}
    log.info("========== 震荡期检查完成 ==========")


def reset_range_bound_daily(context):
    if g.current_filter == '震荡期' and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
        g.range_bound_days_count = len(trade_days) - 1


def check_etf_trend_structure(price_series, current_price):
    """均线结构硬过滤：现价>MA10 且 MA5>MA10"""
    if not g.enable_trend_structure_filter:
        return True, ''
    closes = np.asarray(price_series, dtype=float)
    if len(closes) < max(g.trend_ma_period, 10) + 1:
        return False, '历史不足'
    ma10 = float(np.mean(closes[-g.trend_ma_period:]))
    ma5 = float(np.mean(closes[-5:]))
    if g.trend_require_price_above_ma and current_price <= ma10:
        return False, f'现价{current_price:.3f}<=MA{g.trend_ma_period}({ma10:.3f})'
    if g.trend_require_ma5_above_ma10 and ma5 <= ma10:
        return False, f'MA5({ma5:.3f})<=MA10({ma10:.3f})'
    return True, ''


# ==================== 有害卖出冷却 / 震荡期空仓 / 买入得分区间 ====================
def is_range_bound_filter_active(context):
    return g.enable_range_bound_mode and g.current_filter == '震荡期'


def should_fallback_defensive(context):
    """排名为空时是否允许兜底防御ETF。关闭时/震荡期保持空仓。"""
    if not g.enable_defensive_etf:
        return False
    if g.enable_range_bound_cash and is_range_bound_filter_active(context):
        return False
    return True


def mark_harmful_sell(context, security=None):
    """记录有害卖出。走弱期启动QDII守卫冷却；正常期靠 drawdown_selled_today 禁同日买回。"""
    if security:
        g.harmful_sell_last_security = security
    name = get_name(security) if security else ''
    if g.is_a_share_weak:
        g.harmful_sell_last_date = context.current_dt.date()
        log.info(
            f"🛡️ 走弱期有害卖出 {security} {name}，"
            f"{g.harmful_sell_cooldown_weak_days}日内挡QDII追高（商品可轮动）"
        )
    else:
        log.info(f"🛡️ 正常期有害卖出 {security} {name}，仅禁止同日买回该标的")


def get_harmful_sell_cooldown_days(context):
    if g.is_a_share_weak:
        return g.harmful_sell_cooldown_weak_days
    return g.harmful_sell_cooldown_days


def is_harmful_sell_cooldown_active(context):
    if not g.enable_harmful_sell_guard or g.harmful_sell_last_date is None:
        return False
    if not g.is_a_share_weak:
        return False
    cooldown = get_harmful_sell_cooldown_days(context)
    if cooldown <= 0:
        return False
    trade_days = get_trade_days(start_date=g.harmful_sell_last_date, end_date=context.current_dt.date())
    days_since = len(trade_days) - 1
    return days_since < cooldown


def trading_days_since_harmful_sell(context):
    if g.harmful_sell_last_date is None:
        return None
    trade_days = get_trade_days(start_date=g.harmful_sell_last_date, end_date=context.current_dt.date())
    return len(trade_days) - 1


def _daily_returns_series(security, context, lookback):
    # hist = attribute_history(security, lookback + 1, '1d', ['close'], skip_paused=True)
    hist = pt_get_history(lookback+ 1, frequency='1d', field=['close'], security_list=security, fq=g.fq_type, include=False)
    
    if hist is None or len(hist) < lookback + 1:
        return None
    closes = hist['close'].values.astype(float)
    if np.any(closes <= 0):
        return None
    return np.diff(closes) / closes[:-1]


def calc_return_correlation(sec_a, sec_b, context, lookback=None):
    lookback = lookback or g.correlation_lookback
    ra = _daily_returns_series(sec_a, context, lookback)
    rb = _daily_returns_series(sec_b, context, lookback)
    if ra is None or rb is None or len(ra) != len(rb) or len(ra) < 5:
        return None
    corr = float(np.corrcoef(ra, rb)[0, 1])
    if np.isnan(corr):
        return None
    return corr


def get_weak_qdii_guard_refs(context):
    """走弱期有害卖后：被卖标的 + 当日有害卖集合。"""
    refs = []
    sec = getattr(g, 'harmful_sell_last_security', None)
    if sec and (sec in g.etf_pool or sec == g.defensive_etf):
        refs.append(sec)
    for s in g.drawdown_selled_today:
        if s in g.etf_pool or s == g.defensive_etf:
            refs.append(s)
    return list(dict.fromkeys(refs))


def is_blocked_by_harmful_sell_same_etf(candidate, context):
    """有害卖出冷却期内禁止买回同一只标的（仅挡自身，不挡商品）。"""
    if not g.enable_harmful_sell_guard or not is_harmful_sell_cooldown_active(context):
        return False, None
    ref_sec = getattr(g, 'harmful_sell_last_security', None)
    if ref_sec and candidate == ref_sec:
        return True, ref_sec
    return False, None


def is_blocked_by_weak_overseas_cluster(candidate, context):
    """有害卖出海外代理后，冷却期内禁止买入其他海外ETF。"""
    if not g.enable_weak_qdii_guard or not is_harmful_sell_cooldown_active(context):
        return False, None
    proxy_set = set(getattr(g, 'overseas_proxy_pool', []))
    ref_sec = getattr(g, 'harmful_sell_last_security', None)
    if ref_sec not in proxy_set:
        return False, None
    if is_overseas_qdii(candidate) and candidate != ref_sec:
        return True, ref_sec
    return False, None


def mark_overseas_rotation_sell(context, security=None):
    """走弱期轮动卖出海外 QDII 后，启动短期禁买同簇冷却。"""
    if not g.enable_overseas_rotation_guard or not g.is_a_share_weak:
        return
    if security and not is_overseas_qdii(security):
        return
    g.overseas_rotation_sell_last_date = context.current_dt.date()
    if security:
        g.overseas_rotation_sell_last_security = security
    log.info(
        f"🛡️ 走弱期轮动卖海外 {security} {get_name(security)}，"
        f"{g.overseas_rotation_cooldown_days}日内禁买其他QDII"
    )


def is_overseas_rotation_cooldown_active(context):
    if not g.enable_overseas_rotation_guard or g.overseas_rotation_sell_last_date is None:
        return False
    if not g.is_a_share_weak:
        return False
    cooldown = g.overseas_rotation_cooldown_days
    if cooldown <= 0:
        return False
    trade_days = get_trade_days(
        start_date=g.overseas_rotation_sell_last_date,
        end_date=context.current_dt.date(),
    )
    return len(trade_days) - 1 < cooldown


def is_blocked_by_overseas_rotation_cluster(candidate, context):
    """走弱期轮动卖海外后，冷却期内禁止买入其他海外 QDII。"""
    if not is_overseas_rotation_cooldown_active(context):
        return False, None
    ref_sec = getattr(g, 'overseas_rotation_sell_last_security', None)
    if not ref_sec or not is_overseas_qdii(ref_sec):
        return False, None
    if is_overseas_qdii(candidate) and candidate != ref_sec:
        # 同日 13:09 轮动卖出后，13:10 允许切换至另一只 QDII（避免挡掉正当换仓）
        if g.overseas_rotation_sell_last_date == context.current_dt.date():
            hm = context.current_dt.strftime('%H:%M')
            if '13:05' <= hm <= '13:15':
                return False, None
        return True, ref_sec
    return False, None


def passes_weak_qdii_correlation_guard(candidate, context, refs=None):
    if not g.enable_weak_qdii_guard or not is_harmful_sell_cooldown_active(context):
        return True, None
    refs = refs or get_weak_qdii_guard_refs(context)
    worst = None
    for ref in refs:
        if ref == candidate:
            continue
        corr = calc_return_correlation(candidate, ref, context)
        if corr is None:
            continue
        if corr >= g.correlation_max and (worst is None or corr > worst[1]):
            worst = (ref, corr)
    if worst:
        return False, worst
    return True, None


def resolve_guard_target(context):
    """走弱期有害卖出冷却内的强制目标（cash 模式专用）。"""
    if g.is_a_share_weak and g.harmful_sell_mode_weak == 'cash':
        log.info("🛡️ 走弱期有害卖出冷却中，目标空仓")
        return []
    log.info("🛡️ 有害卖出冷却中，目标空仓")
    return []


def get_harmful_sell_strict_buy_days(context):
    """有害卖出后严买入带持续交易日数 = 冷却天数 + 额外观望日。"""
    return get_harmful_sell_cooldown_days(context) + g.harmful_sell_strict_extra_days


def is_harmful_sell_strict_buy_band_active(context):
    """有害卖出后是否仍处严买入带（冷却期内及恢复轮动后的额外观望日）。"""
    if not g.enable_cooldown_strict_buy_band or g.harmful_sell_last_date is None:
        return False
    trade_days = get_trade_days(start_date=g.harmful_sell_last_date, end_date=context.current_dt.date())
    days_since = len(trade_days) - 1
    return days_since < get_harmful_sell_strict_buy_days(context)


def get_buy_score_band_limits(context=None, etf=None):
    """返回当前生效的买入得分/年化上下限（正常期宽区间，有害卖出后严带）。"""
    max_score = g.buy_max_score
    enable_ann_cap = g.enable_buy_annualized_cap
    max_ann = g.buy_max_annualized
    min_score = g.buy_min_score
    if context is not None and is_harmful_sell_strict_buy_band_active(context):
        max_score = g.buy_max_score_cooldown
        enable_ann_cap = g.enable_buy_annualized_cap_cooldown
        max_ann = g.buy_max_annualized_cooldown
    if (
        context is not None
        and etf
        and g.enable_overseas_weak_commodity_gate
        and g.enable_overseas_regime_switch
        and g.is_overseas_weak
        and etf in g.commodity_etf_pool
    ):
        min_score = max(min_score, g.buy_min_score_overseas_weak)
    return min_score, max_score, enable_ann_cap, max_ann


def passes_buy_score_band(metrics, context=None):
    """买入阶段得分/年化区间（仅影响买，不影响卖）。"""
    score = metrics['score']
    if not g.enable_buy_score_band:
        return score >= g.min_score_threshold
    min_score, max_score, enable_ann_cap, max_ann = get_buy_score_band_limits(
        context, metrics.get('etf')
    )
    if score < min_score:
        log.info(f"🚫 {metrics['etf']} {metrics['etf_name']} 得分{score:.4f} < 买入下限{min_score:.2f}")
        return False
    if score > max_score:
        log.info(f"🚫 {metrics['etf']} {metrics['etf_name']} 得分{score:.4f} > 买入上限{max_score:.2f}")
        return False
    if enable_ann_cap:
        ann = metrics.get('annualized_returns', 0)
        if ann > max_ann:
            log.info(
                f"🚫 {metrics['etf']} {metrics['etf_name']} 年化{ann * 100:.1f}% > "
                f"买入上限{max_ann * 100:.0f}%"
            )
            return False
    return True


def filter_ranked_by_active_pool(ranked, active_pool):
    """仅保留当前有效池内的排名条目。"""
    pool_set = set(active_pool)
    return [m for m in ranked if m['etf'] in pool_set]


def refresh_rankings_for_current_pool(context, ranked):
    """兜底路径：排名含池外标的时，按当前有效池重算排名。"""
    active_pool = set(get_active_etf_pool())
    out_pool = [m['etf'] for m in ranked[:max(g.holdings_num * 3, 5)]
                if m['etf'] not in active_pool]
    if not out_pool:
        return ranked
    log.info(
        f"📊 排名含池外标的{out_pool}，按当前有效池({len(active_pool)}只)重算排名"
    )
    ranked = get_ranked_etfs(context)
    g.rankings_cache = {'date': context.current_dt.date(), 'data': ranked}
    return ranked


def resolve_rotation_targets(context, ranked):
    """统一解析 13:09/13:10 目标ETF（有害卖出冷却 > 轮动 > 防御/震荡期空仓）。"""
    if is_harmful_sell_cooldown_active(context):
        days_since = trading_days_since_harmful_sell(context)
        cooldown = get_harmful_sell_cooldown_days(context)
        if g.harmful_sell_mode_weak == 'cash':
            log.info(f"🛡️ 走弱期有害卖出冷却 {days_since}/{cooldown} 日，全盘空仓")
            return resolve_guard_target(context)
        log.info(
            f"🛡️ 走弱期有害卖出冷却 {days_since}/{cooldown} 日，"
            f"仅挡QDII追高，商品/轮动继续"
        )

    target_etfs = select_target_etfs_from_rankings(context, ranked)
    if not target_etfs and g.enable_overseas_weak_cash and g.is_overseas_weak:
        log.info("💤 海外弱无合格商品标的，目标空仓")
    elif not target_etfs and should_fallback_defensive(context):
        if check_defensive_etf_available(context) and g.defensive_etf not in g.drawdown_selled_today:
            target_etfs = [g.defensive_etf]
            log.info(f"🛡️ 无目标ETF，防御模式：{g.defensive_etf} {get_name(g.defensive_etf)}")
    elif not target_etfs and not g.enable_defensive_etf:
        log.info("💤 无合格标的，防御ETF已关闭，目标空仓")
    elif not target_etfs and g.enable_range_bound_cash and is_range_bound_filter_active(context):
        log.info("💤 震荡期无合格标的，目标空仓")
    return target_etfs


# ==================== 核心计算模块 ====================
def get_cached_rankings(context):
    """获取缓存的ETF排名"""
    today = context.current_dt.date()
    if g.rankings_cache['date'] != today:
        log.info("📊 重新计算ETF排名...")
        ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': today, 'data': ranked}
    else:
        log.debug("🔍 使用缓存的ETF排名")
    return g.rankings_cache['data']


def get_ranked_etfs(context):
    """计算所有ETF的动量得分（V2.0：根据行情状态动态选择ETF池，V2.2受独立开关影响）"""
    active_pool = get_active_etf_pool()

    etf_metrics = []
    for etf in active_pool:
        tradable, reason = is_etf_tradable(context, etf)
        if not tradable:
            log.debug(f"❌ {etf} {get_name(etf)} 不可交易({reason})，跳过")
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            if g.rank_min_score < metrics['score'] < g.rank_max_score:
                etf_metrics.append(metrics)
            else:
                log.debug(f"❌ {etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超出排名区间，过滤")

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def calculate_momentum_metrics(context, etf):
    """计算单只ETF的动量指标（无未来）"""
    try:
        name = get_name(etf)
        # prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        prices = pt_get_history(lookback, frequency='1d', field=['close', 'high'], security_list=etf, fq=g.fq_type)
        
        if len(prices) < g.lookback_days:
            log.debug(f"🚫 {etf} {name} 历史数据不足{len(prices)}天，跳过")
            return None

        current_price = sub_get_current_price(etf, context)
        price_series = np.append(prices["close"].values, current_price)

        # 1. 盈利保护检查
        if check_profit_protection(etf, context):
            log.info(f"🚫 {etf} {name} 触发盈利保护，从排名中排除")
            return None

        # 2. 溢价率过滤
        if g.enable_premium_filter:
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = pt_get_premium_rate(etf, prev_date)
            if premium is not None:
                if premium > g.premium_threshold:
                    log.info(f"🚫 {etf} {name} 溢价率{premium*100:.2f}% > 阈值，排除")
                    return None
            else:
                log.debug(f"🚫 {etf} {name} 无法获取{prev_date}的净值，排除")
                return None

        # 3. 成交量过滤
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns(price_series, g.lookback_days)
                if annualized > g.volume_return_limit:
                    log.info(f"📉 {etf} {name} 成交量放量，过滤")
                    return None

        # 4. 短期动量过滤
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0

        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            log.debug(f"❌ {etf} {name} 短期动量不足，过滤")
            return None

        # 4b. 均线趋势结构硬过滤
        ok_trend, trend_reason = check_etf_trend_structure(price_series, current_price)
        if not ok_trend:
            log.info(f"🚫 {etf} {name} 趋势结构未通过({trend_reason})，排除")
            return None

        # 5. 长期动量计算
        recent = price_series[-(g.lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        if g.enable_r2_filter and r_squared < g.r2_threshold:
            log.info(f"🚫 {etf} {name} R²={r_squared:.3f} < {g.r2_threshold:.2f}，排除")
            return None

        score = annualized_returns * r_squared

        # 6. 近3日跌幅过滤
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < g.loss:
                log.info(f"⚠️ {etf} {name} 近3日有单日跌幅超限，排除")
                return None

        # 7. 拉普拉斯/高斯动态滤波（正常期/震荡期）
        if g.enable_range_bound_mode and len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                laplace_slope = laplace_values[-1] - laplace_values[-2] if len(laplace_values) >= 2 else 0
                passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
                g1_val, g2_val = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
                gaussian_slope = g1_val - g2_val
                passed_gaussian = (current_price > g1_val and gaussian_slope > g.gaussian_min_slope)
                if g.current_filter == '正常期':
                    passed_filter = passed_laplace
                    filter_name = '拉普拉斯'
                else:
                    passed_filter = passed_gaussian
                    filter_name = '高斯'
                if not passed_filter:
                    log.info(f"🚫 {etf} {name} 未通过{filter_name}滤波({g.current_filter})，排除")
                    return None
            except Exception as e:
                log.debug(f"{etf} {name} 滤波器异常: {e}")

        return {
            'etf': etf,
            'etf_name': name,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'current_price': current_price,
            'short_annualized': short_annualized,
        }

    except Exception as e:
        log.warning(f"计算{etf} {get_name(etf)}时出错: {e}")
        return None


def get_annualized_returns(price_series, lookback_days):
    """计算加权年化收益率（无未来）"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def get_volume_ratio(context, security, lookback=None, threshold=None):
    """计算成交量比值（基于分钟线）"""
    lookback = lookback or g.volume_lookback
    threshold = threshold or g.volume_threshold
    try:
        name = get_name(security)
        # hist = attribute_history(security, lookback, '1d', ['volume'])
        hist = pt_get_history(lookback, frequency='1d', field=['volume'], security_list=security, fq=g.fq_type)        
        
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()

        # today = context.current_dt.date()
        # df_vol = get_price(security, start_date=today, end_date=context.current_dt,
        #                    frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        total_minutes =  get_today_exchanged_minutes(context)
        df_vol = pt_get_history(total_minutes, frequency='1m', field=['volume'], security_list=security, fq=g.fq_type,include=True)   
        
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        if ratio > threshold:
            log.debug(f"❌ {security} {name} 成交量比{ratio:.2f} > {threshold}")
            return ratio
        return None
    except Exception as e:
        log.warning(f"🚨成交量计算失败 {security}: {e}")
        return None

def get_today_exchanged_minutes(context):
    """_summary_
    获取当天交易的分钟数。
    Args:
        context (_type_): _description_
    """
    end_date_str = context.blotter.current_dt.strftime('%H:%M')
    minute = context.blotter.current_dt.minute

    total_minutes = 0
    if end_date_str >= "09:30" and end_date_str < "10:00":
        total_minutes = minute -30
    elif end_date_str >= "10:00" and end_date_str < "11:00":
        total_minutes = minute + 30
    elif end_date_str >= "11:00" and end_date_str < "11:30":
        total_minutes = minute + 90
    elif end_date_str >= "11:30" and end_date_str < "13:00":
        total_minutes = 120
    elif end_date_str >= "13:00" and end_date_str < "14:00":
        total_minutes = minute + 120 
    elif end_date_str >= "14:00" and end_date_str < "15:00":
        total_minutes = minute + 180
    elif end_date_str >= "15:00": 
        total_minutes = 240

    return total_minutes


def is_etf_tradable(context, security):
    """
    判断 ETF 当前是否可交易（含盘中临时停牌）。
    聚宽 get_current_data().paused 对「下午临时停牌」常为 False，需结合本时段分钟成交判断。
    返回 (bool, str)：可交易时 (True, '')，不可交易时 (False, 原因)。
    """
    try:
        # data = get_current_data()[security]
        
        halt_status = get_stock_status(security, 'HALT')

        if halt_status[security] is True or halt_status[security] is None:
            return False, '全天停牌(paused)'

        # price = data.last_price
        price = sub_get_current_price(security, context)
        if price is None or price <= 0:
            return False, '现价无效'

        total_minutes =  get_today_exchanged_minutes(context)
        if total_minutes > 5:
            total_minutes = 5
        df = pt_get_history(total_minutes, frequency='1m', field=['volume'], security_list=security, fq=g.fq_type,include=True)   
        
        if df is None or df.empty:
            return False, '本交易时段无分钟行情(可能盘中停牌)'

        recent = df.tail(min(5, len(df)))
        if recent['volume'].sum() == 0:
            return False, '本交易时段近段无成交(可能盘中停牌)'

        return True, ''
    except Exception as e:
        log.warning(f"⚠️ {security} {get_name(security)} 可交易性检查异常: {e}")
        return True, ''


def _to_float(value):
    """聚宽行情字段偶为 str，统一转 float 供回撤比较。"""
    try:
        if value is None:
            return None
        v = float(value)
        if np.isnan(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def get_intraday_drawdown_ratio(security, context):
    """测算当日盘中高点→现价的回撤比例；数据不足时返回 None。"""
    try:
       
        minutes_length = get_today_exchanged_minutes(context)
        df = pt_get_history(minutes_length, frequency='1m', field=['high', 'close'], security_list=security, fq=g.fq_type, include=True)
        
        if df is None or df.empty:
            return None
        day_high = _to_float(df['high'].max())
        current = _to_float(df['close'].iloc[-1])
        if not day_high or not current or day_high <= 0:
            return None
        return (day_high - current) / day_high
    except Exception:
        return None


def get_prev_trading_close(security, context):
    """前一交易日收盘价（用于持仓跳空回撤）。"""
    try:
        # prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
        # df = get_price(
        #     security, end_date=prev_date, frequency='1d',
        #     fields=['close'], count=1, fq='pre', skip_paused=True
        # )
        df = pt_get_history(1, frequency='1d', field=['close'], security_list=security, fq=g.fq_type, include=False)
        
        if df is None or df.empty:
            return None
        return float(df['close'].iloc[-1])
    except Exception:
        return None


def get_holding_drawdown_detail(security, context):
    """持仓回撤明细：日内高点→现价；可选昨收→现价。买入过滤仍仅用日内。"""
    detail = {}
    idd = get_intraday_drawdown_ratio(security, context)
    if idd is not None:
        detail['日内'] = idd
    if g.enable_holding_prev_close_drawdown:
        prev_close = get_prev_trading_close(security, context)
        try:
            # current = get_current_data()[security].last_price
            current = sub_get_current_price(security,context)
        except Exception:
            current = None
        current = _to_float(current)
        prev_close = _to_float(prev_close)
        if prev_close and current and prev_close > 0 and current > 0:
            detail['昨收'] = (prev_close - current) / prev_close
    return detail


def get_holding_drawdown_ratio(security, context):
    detail = get_holding_drawdown_detail(security, context)
    if not detail:
        return None, detail
    return max(detail.values()), detail


def get_position_unrealized_gain(security, context):
    """持仓相对成本的浮盈比例；无法计算时返回 None。"""
    try:
        # pos = context.portfolio.positions[security]
        pos = sub_get_strategy_positions(context, security)
        if pos.amount <= 0:
            return None
        cost = _to_float(pos.cost_basis)
        price = _to_float(pos.last_sale_price)
        if not price:
            try:
                # price = _to_float(get_current_data()[security].last_price)
                price = sub_get_current_price(security,context)
            except Exception:
                price = None
        if not price or not cost or cost <= 0:
            return None
        return (price - cost) / cost
    except Exception:
        return None


def get_holding_drawdown_for_sell(security, context, source='minute'):
    """持仓卖出回撤：盈利仓豁免分钟误杀；盈利仓 13:09 不用昨收跳空。
    返回 (drawdown, detail, threshold)；drawdown/threshold 为 None 表示不触发卖。
    """
    gain = get_position_unrealized_gain(security, context)
    skip_minute = getattr(g, 'holding_profit_skip_minute_pct', 0.10)
    skip_prev = getattr(g, 'holding_profit_skip_prev_close_pct', 0.10)

    if source == 'minute' and gain is not None and gain >= skip_minute:
        return None, {}, None

    detail = get_holding_drawdown_detail(security, context)
    if gain is not None and gain >= skip_prev and '昨收' in detail:
        detail = {k: v for k, v in detail.items() if k != '昨收'}

    if not detail:
        return None, {}, None

    drawdown = max(detail.values())
    threshold = g.intraday_drawdown_threshold
    return drawdown, detail, threshold


def is_intraday_drawdown_active(security, context):
    """与买入守卫同源：当日盘中回撤是否已达阈值。"""
    drawdown = get_intraday_drawdown_ratio(security, context)
    return drawdown is not None and drawdown >= g.intraday_drawdown_threshold


def check_intraday_drawdown_for_buy(security, context):
    """买入前检查：ETF当前是否处于日内显著回撤状态
    返回 True 表示正在回撤（不宜买入），False 表示正常
    """
    return is_intraday_drawdown_active(security, context)


def execute_intraday_drawdown_sell(
    context, security, drawdown, source='日内回撤', detail=None, threshold=None
):
    """日内回撤触发的统一卖出（分钟级 / 13:09 持仓守卫共用）。"""
    name = get_name(security)
    th = threshold if threshold is not None else g.intraday_drawdown_threshold
    detail_str = ''
    if detail:
        detail_str = ' [' + ' '.join(
            f"{k}{v * 100:.2f}%" for k, v in detail.items()
        ) + ']'
    log.info(
        f"⚠️ {source}回撤触发：{security} {name} "
        f"回撤{drawdown * 100:.2f}% > {th * 100:.0f}%"
        f"{detail_str}"
    )
    if smart_order_target_value(security, 0, context):
        log.info(f"🧨 {source}回撤卖出：{security} {name}")
        g.drawdown_selled_today.add(security)
        mark_harmful_sell(context, security)
        if security in g.buy_date:
            del g.buy_date[security]
        return True
    return False


def filter_intraday_drawdown_targets(context, target_etfs):
    """从目标列表剔除回撤标的；已持仓用持仓回撤（含昨收），候选仅用日内。"""
    positions = sub_get_strategy_positions(context)
    held = {
        s for s in positions
        if (s in g.etf_pool or s == g.defensive_etf)
        and positions[s].amount > 0
    }
    filtered = []
    for etf in target_etfs:
        if etf in held:
            drawdown, detail, threshold = get_holding_drawdown_for_sell(
                etf, context, source='slot1309'
            )
        else:
            drawdown = get_intraday_drawdown_ratio(etf, context)
            detail = {'日内': drawdown} if drawdown is not None else {}
            threshold = g.intraday_drawdown_threshold
        if (
            drawdown is not None
            and threshold is not None
            and drawdown >= threshold
        ):
            detail_str = ' '.join(f"{k}={v * 100:.2f}%" for k, v in detail.items())
            log.info(
                f"🌊 {etf} {get_name(etf)} 回撤"
                f"(>{g.intraday_drawdown_threshold * 100:.0f}%)，目标列表剔除 [{detail_str}]"
            )
            continue
        filtered.append(etf)
    return filtered


def passes_buy_candidate_filters(m, context, guard_refs=None):
    """单只 ETF 是否通过买入阶段全部守卫与弱势过滤。"""
    etf = m['etf']
    etf_name = m['etf_name']

    if not passes_buy_score_band(m, context):
        return False

    tradable, reason = is_etf_tradable(context, etf)
    if not tradable:
        log.info(f"🚫 {etf} {etf_name} 不可交易({reason})，买入过滤剔除")
        return False

    if g.enable_profit_protection and check_profit_protection(etf, context):
        log.info(f"🚫 {etf} {etf_name} 触发盈利保护，买入过滤剔除")
        return False

    if etf in g.drawdown_selled_today:
        log.info(f"🚫 {etf} {etf_name} 今日因回撤/盈利保护卖出，买入过滤剔除")
        return False

    blocked_same, ref_same = is_blocked_by_harmful_sell_same_etf(etf, context)
    if blocked_same:
        days_since = trading_days_since_harmful_sell(context)
        cooldown = get_harmful_sell_cooldown_days(context)
        log.info(
            f"🚫 {etf} {etf_name} 有害卖出冷却 {days_since}/{cooldown} 日，"
            f"禁止买回同标的"
        )
        return False

    blocked, ref_sec = is_blocked_by_weak_overseas_cluster(etf, context)
    if blocked:
        log.info(
            f"🚫 {etf} {etf_name} 海外有害簇挡："
            f"近期有害卖出 {ref_sec} {get_name(ref_sec)}"
        )
        return False

    blocked_rot, ref_rot = is_blocked_by_overseas_rotation_cluster(etf, context)
    if blocked_rot:
        log.info(
            f"🚫 {etf} {etf_name} 轮动卖海外挡："
            f"近期轮动卖出 {ref_rot} {get_name(ref_rot)}"
        )
        return False

    ok_corr, corr_info = passes_weak_qdii_correlation_guard(etf, context, guard_refs)
    if not ok_corr:
        ref, corr = corr_info
        log.info(
            f"🚫 {etf} {etf_name} 弱期低相关守卫：与 {ref} {get_name(ref)} "
            f"{g.correlation_lookback}日相关{corr:.2f}≥{g.correlation_max:.2f}"
        )
        return False

    if check_intraday_drawdown_for_buy(etf, context):
        log.info(
            f"🌊 {etf} {etf_name} 当前处于日内回撤状态"
            f"(>{g.intraday_drawdown_threshold*100:.0f}%)，买入过滤剔除"
        )
        return False

    if g.enable_holding_prev_close_drawdown:
        _, detail = get_holding_drawdown_ratio(etf, context)
        prev_dd = detail.get('昨收')
        if prev_dd is not None and prev_dd >= g.intraday_drawdown_threshold:
            log.info(
                f"🌊 {etf} {etf_name} 相对昨收回撤{prev_dd * 100:.2f}%"
                f"(>{g.intraday_drawdown_threshold * 100:.0f}%)，买入过滤剔除"
            )
            return False

    return True


def refilter_cached_buy_targets(context, cached_etfs, ranked):
    """买入前对缓存目标复跑守卫，并过滤当前有效池外的弱势标。"""
    active_pool = set(get_active_etf_pool())
    ranked_map = {m['etf']: m for m in ranked}
    guard_refs = get_weak_qdii_guard_refs(context) if is_harmful_sell_cooldown_active(context) else []
    result = []
    for etf in cached_etfs:
        if etf not in active_pool:
            log.info(f"🚫 {etf} {get_name(etf)} 不在当前有效池(弱势屏蔽)，缓存复检剔除")
            continue
        m = ranked_map.get(etf)
        if m is None:
            log.info(f"🚫 {etf} {get_name(etf)} 不在当日排名，缓存复检剔除")
            continue
        if passes_buy_candidate_filters(m, context, guard_refs):
            result.append(etf)
            if guard_refs is not None:
                guard_refs.append(etf)
    return result, guard_refs


def extend_buy_targets_from_rankings(context, ranked, target_etfs, guard_refs=None):
    """缓存过滤后不足持仓数时，按排名顺延替补（复用相同守卫）。"""
    active_pool = set(get_active_etf_pool())
    existing = set(target_etfs)
    for m in ranked:
        if len(target_etfs) >= g.holdings_num:
            break
        etf = m['etf']
        if etf in existing:
            continue
        if etf not in active_pool:
            continue
        if passes_buy_candidate_filters(m, context, guard_refs):
            target_etfs.append(etf)
            existing.add(etf)
            log.info(f"🔄 缓存目标不可买，顺延替补：{etf} {m['etf_name']}")
            if guard_refs is not None:
                guard_refs.append(etf)
    return target_etfs


def _pick_targets_from_ranked(context, ranked, guard_refs):
    """从已按有效池过滤的排名列表中选出目标 ETF。"""
    target_etfs = []
    for m in ranked:
        if len(target_etfs) >= g.holdings_num:
            break
        if passes_buy_candidate_filters(m, context, guard_refs):
            target_etfs.append(m['etf'])
            if guard_refs is not None:
                guard_refs.append(m['etf'])
    return target_etfs


def select_target_etfs_from_rankings(context, ranked, allow_rerank=True):
    """从排名列表中按统一过滤条件选出目标ETF，最多 holdings_num 个。

    卖出和买入共用此函数，确保两者的目标集合完全一致，
    杜绝「13:09 卖出 → 13:10 买回同一标的」的现象。

    过滤逻辑（优先级从高到低）：
      0. 当前有效池（V3.12.2：池外弱势标直接跳过）
      1. 买入得分区间（passes_buy_score_band）
      2. 可交易性（全天/盘中停牌）
      3. 盈利保护检查（避免卖了又买）
      4. 当日回撤/盈利保护卖出禁止买回（drawdown_selled_today）
      5. 走弱期有害卖后 QDII 簇挡 / 低相关守卫（V3.11）
      6. 走弱期轮动卖海外后 QDII 簇挡（V3.12）
      7. 日内回撤检查（避免"接飞刀"）
    """
    active_pool = get_active_etf_pool()
    pool_ranked = filter_ranked_by_active_pool(ranked, active_pool)
    skipped = len(ranked) - len(pool_ranked)
    if skipped:
        log.info(f"📊 有效池过滤：{skipped}只不在当前池，候选缩至{len(pool_ranked)}只")

    guard_refs = get_weak_qdii_guard_refs(context) if is_harmful_sell_cooldown_active(context) else []
    target_etfs = _pick_targets_from_ranked(context, pool_ranked, guard_refs)

    if not target_etfs and allow_rerank and skipped:
        log.info("📊 池过滤后无合格标的，按当前有效池重算排名后再选")
        fresh_ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': context.current_dt.date(), 'data': fresh_ranked}
        return select_target_etfs_from_rankings(context, fresh_ranked, allow_rerank=False)

    return target_etfs


# ==================== 卖出模块 ====================
@time_monitor(func_name="卖出操作")
def etf_sell_trade(context):
    """卖出不符合条件的持仓"""
    log.info("📤 ========== 卖出操作开始 ==========")

    refresh_regime_for_trade(context)
    ranked = get_cached_rankings(context)
    target_etfs = resolve_rotation_targets(context, ranked)
    target_etfs = filter_intraday_drawdown_targets(context, target_etfs)

    # 缓存最终目标列表，供 13:10 买入复用（避免时间敏感过滤在 1 分钟内变化）
    g.target_etfs_cache = {'date': context.current_dt.date(), 'data': list(target_etfs)}

    target_set = set(target_etfs)

    positions = sub_get_strategy_positions(context)
    for sec in list(positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = positions[sec]
        if pos.amount <= 0:
            continue

        drawdown, detail, threshold = get_holding_drawdown_for_sell(
            sec, context, source='slot1309'
        )
        in_drawdown = (
            drawdown is not None
            and threshold is not None
            and drawdown >= threshold
        )
        if detail and drawdown is not None and drawdown >= 0.01:
            log.info(
                f"📉 持仓回撤检视 {sec} {get_name(sec)}: "
                + ' '.join(f"{k}={v * 100:.2f}%" for k, v in detail.items())
            )

        if in_drawdown:
            cost = pos.cost_basis 
            buy_date = g.buy_date.get(sec)
            hold_days = (context.current_dt.date() - buy_date).days if buy_date else 0
            if execute_intraday_drawdown_sell(
                context, sec, drawdown, source='13:09持仓',
                detail=detail, threshold=threshold
            ):
                g.trade_log['sell_records'].append({
                    'time': get_real_time(),
                    'code': sec,
                    'name': get_name(sec),
                    'cost': cost,
                    'price': sub_get_current_price(sec, context),
                    'hold_days': hold_days
                })
            continue

        if sec not in target_set:
            cost = pos.cost_basis 
            buy_date = g.buy_date.get(sec)
            hold_days = (context.current_dt.date() - buy_date).days if buy_date else 0
            if smart_order_target_value(sec, 0, context):
                log.info(f"📤 卖出持仓：{sec} {get_name(sec)}")
                if is_overseas_qdii(sec):
                    mark_overseas_rotation_sell(context, sec)
                g.trade_log['sell_records'].append({
                    'time': get_real_time(),
                    'code': sec,
                    'name': get_name(sec),
                    'cost': cost,
                    'price': sub_get_current_price(sec, context),
                    'hold_days': hold_days
                })
                if sec in g.buy_date:
                    del g.buy_date[sec]

    log.info("📤 ========== 卖出操作完成 ==========")


# ==================== 买入模块 ====================
@time_monitor(func_name="买入操作")
def etf_buy_trade(context):
    """买入符合条件的ETF"""
    log.info("📥 ========== 买入操作开始 ==========")

    refresh_regime_for_trade(context)
    ranked = get_cached_rankings(context)
    log.info("📊 === ETF排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        annual_pct = m['annualized_returns'] * 100
        r_sq = m['r_squared']
        log.info(f"   排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} 年化{annual_pct:.2f}%")

    today = context.current_dt.date()
    if is_harmful_sell_cooldown_active(context):
        target_etfs = resolve_rotation_targets(context, ranked)
    elif g.target_etfs_cache['date'] == today and g.target_etfs_cache['data'] is not None:
        raw_targets = list(g.target_etfs_cache['data'])
        log.info(f"📋 复用13:09目标ETF缓存：{raw_targets}")
        target_etfs, guard_refs = refilter_cached_buy_targets(context, raw_targets, ranked)
        if len(target_etfs) < g.holdings_num:
            target_etfs = extend_buy_targets_from_rankings(
                context, ranked, target_etfs, guard_refs
            )
        if not target_etfs:
            log.info("📋 缓存目标经守卫复检后为空，回退 resolve_rotation_targets（同步有效池）")
            ranked = refresh_rankings_for_current_pool(context, ranked)
            target_etfs = resolve_rotation_targets(context, ranked)
    else:
        target_etfs = resolve_rotation_targets(context, ranked)

    if not target_etfs:
        log.info("💤 无目标ETF，保持空仓")
        return

    if target_etfs:
        for i, etf in enumerate(target_etfs):
            m = next((x for x in ranked if x['etf'] == etf), None)
            if m:
                log.info(f"🎯 目标ETF {i+1}: {etf} {m['etf_name']} 得分{m['score']:.4f}")
    else:
        log.info("💤 无目标ETF，保持空仓")
        return

    # 检查是否有持仓需要先卖出
    positions = sub_get_strategy_positions(context)
    current_etf_pos = [s for s in positions if s in g.etf_pool or s == g.defensive_etf]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        log.info(f"⏳ 尚有持仓需要卖出：{[get_name(s) for s in to_sell]}，等待卖出完成")
        return

    # 等权分配
    portfolio = sub_get_strategy_portfolio(context)
    total_val = portfolio.portfolio_value
    target_per_etf = total_val / len(target_etfs)

    for etf in target_etfs:
        current_val = 0
        if etf in positions:
            pos = positions[etf]
            if pos.amount > 0:
                current_val = pos.amount * pos.last_sale_price
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            if smart_order_target_value(etf, target_per_etf, context):
                action = "买入" if current_val < target_per_etf else "调仓"
                log.info(f"📦 {action}：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")

    log.info("📥 ========== 买入操作完成 ==========")


# ==================== 辅助函数 ====================
def get_name(security):
    try:
        return sub_get_stock_name(security)
    except:
        return "未知"


def check_defensive_etf_available(context):
    etf = g.defensive_etf
    tradable, _ = is_etf_tradable(context, etf)
    if not tradable:
        return False
    data = pt_get_current_data(context,[etf])
    if data[etf].last_price >= data[etf].high_limit:
        return False
    if data[etf].last_price <= data[etf].low_limit:
        return False
    return True

def smart_order_target_value(security, target_value, context):
    """
    智能下单：根据目标市值调整持仓，处理停牌、涨跌停、最小交易金额、T+1
    """
    # data = get_current_data()
    data = pt_get_current_data(context, [security])
    name = get_name(security)

    if data[security].paused:
        log.info(f"{security} {name} 停牌，跳过")
        return False

    price = data[security].last_price
    if price == 0:
        # 停牌时， 价格会为0
        log.info(f"{security} {name} 当前价格0，跳过")
        return False

    target_amount = int(target_value / price)
    # 按100股整数倍调整
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    # cur_pos = context.portfolio.positions.get(security, None)
    cur_pos = sub_get_strategy_positions(context, security) 
    cur_amount = cur_pos.amount if cur_pos else 0
    diff = target_amount - cur_amount

    # 根据交易方向检查涨跌停
    if diff > 0:  # 买入
        if data[security].last_price >= data[security].high_limit:
            log.info(f"{security} {name} 涨停，跳过买入")
            return False
        
    elif diff < 0:  # 卖出
        if data[security].last_price <= data[security].low_limit:
            log.info(f"{security} {name} 跌停，跳过卖出")
            return False

    # 最小交易金额检查
    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        log.info(f"{security} {name} 交易金额{trade_val:.2f} < {g.min_money}，跳过")
        return False

    # T+1处理
    if diff < 0:
        closeable = cur_pos.enable_amount if cur_pos else 0
        if closeable == 0:
            log.info(f"{security} {name} 当天买入不可卖出")
            return False
        diff = -min(abs(diff), closeable)

    if diff != 0:
        # order_result = order(security, diff)
        # if order_result:
        #     log.info(f"{'📥 买入' if diff>0 else '📤 卖出'} {security} {name} 数量{abs(diff)} 价格{price:.3f}")
        #     return True
        # else:
        #     log.warning(f"下单失败: {security} {name} 数量{diff}")
        #     return False
        sub_order_target_value(security, target_value, context)
        return True

    return False

def get_tushare_api_pro():
    import sxsc_tushare as sx
    import pandas as pd
    import json

    NOTEBOOK_PATH = get_research_path()

    filename = NOTEBOOK_PATH + "tushare_token.json"
    token_json = None
    with open(filename, 'r', encoding='utf-8') as file:
        token_json = json.load(file)

    # log.info(f"现在环境参数: {token_json}")
    g.__env = token_json["env"] # 'qa' 表示生产环境， 'prd' 表示仿真环境
    if g.__env == 'qa':
        log.info("这是山西证券 生产环境")
        g.__env = '生产环境'
    elif g.__env == 'prd':
        log.info("这是山西证券 仿真环境")
        g.__env = '仿真环境'
    else:
        log.error("环境参数错误")

    sx.set_token(token_json["token"])
    pro = sx.get_api(env=token_json["env"])

    return pro 

# ==================== 盘后总结报告 ====================
def daily_summary_report(context):
    """盘后总结"""
    current_date = context.current_dt.strftime('%Y-%m-%d')
    portfolio = sub_get_strategy_portfolio(context)
    total_value = portfolio.portfolio_value 
    cash = portfolio.cash
    positions_value = total_value - cash

    log.info("📋 ========== 策略运行日报 ==========")
    log.info(f"📅 日期: {current_date}")

    # 市场状态（含独立开关状态）
    if g.enable_regime_switch:
        status = "🔴走弱期" if g.is_a_share_weak else "🟢正常期"
        avoid_status = "回避A股" if (g.is_a_share_weak and g.enable_avoid_a_share) else ("不回避A股" if g.is_a_share_weak else "正常交易")
        drawdown_status = "🛡️启用" if (g.is_a_share_weak and g.enable_intraday_drawdown) else ("⭕关闭" if (g.is_a_share_weak and not g.enable_intraday_drawdown) else "⭕关闭")
        log.info(f"🌍 市场状态：{status} | {avoid_status} 计数:{g.weak_period_counter}/{g.weak_period_max_days}")
        log.info(f"🛡️ 分钟级回撤：{drawdown_status}（阈值{g.intraday_drawdown_threshold*100:.0f}%）")
        filt = "拉普拉斯·正常期" if g.current_filter == "正常期" else "高斯·震荡期"
        log.info("📐 滤波器：%s | R2过滤：%s | 均线结构：%s" % (filt, "开" if g.enable_r2_filter else "关", "开" if g.enable_trend_structure_filter else "关"))
    else:
        log.info("🌍 行情判断未启用，始终全市场交易")

    if g.enable_overseas_regime_switch:
        ostatus = "🔴海外弱" if g.is_overseas_weak else "🟢海外正常"
        log.info(f"🌐 海外状态：{ostatus} 计数:{g.overseas_weak_counter}/{g.overseas_weak_max_days}")

    if g.enable_overseas_rotation_guard and g.overseas_rotation_sell_last_date is not None:
        if is_overseas_rotation_cooldown_active(context):
            trade_days = get_trade_days(
                start_date=g.overseas_rotation_sell_last_date,
                end_date=context.current_dt.date(),
            )
            days_since = len(trade_days) - 1
            log.info(
                f"🛡️ 轮动卖海外冷却：激活 {days_since}/{g.overseas_rotation_cooldown_days}日 "
                f"上次={g.overseas_rotation_sell_last_date}"
            )

    if g.enable_harmful_sell_guard and g.harmful_sell_last_date is not None:
        if is_harmful_sell_cooldown_active(context):
            trade_days = get_trade_days(start_date=g.harmful_sell_last_date, end_date=context.current_dt.date())
            days_since = len(trade_days) - 1
            cooldown = get_harmful_sell_cooldown_days(context)
            log.info(f"🛡️ 走弱期有害卖出冷却：激活 {days_since}/{cooldown}日 上次={g.harmful_sell_last_date}")
        else:
            log.info(f"🛡️ 有害卖出冷却：已过期 上次={g.harmful_sell_last_date}")
    else:
        log.info("🛡️ 有害卖出冷却：无记录")

    # 独立开关汇总
    avoid_switch_status = "ON（走弱期回避A股）" if g.enable_avoid_a_share else "OFF（走弱期不回避A股）"
    drawdown_switch_status = "ON（走弱期自动启用）" if g.enable_intraday_drawdown else "OFF（不触发）"
    log.info(f"⚙️ 独立开关：A股回避={avoid_switch_status} | 分钟回撤={drawdown_switch_status}")

    # 今日卖出
    sell_records = g.trade_log.get('sell_records', [])
    log.info(f"📤 今日卖出：{len(sell_records)}只")
    for r in sell_records:
        cost = r.get('cost', 0)
        sell_price = r.get('price', 0)
        profit_pct = (sell_price / cost - 1) * 100 if cost > 0 else 0
        hold_days = r.get('hold_days', 0)
        log.info(f"   {r['code']} {r['name']} | 成本:{cost:.3f} | 卖出:{sell_price:.3f} | 收益:{profit_pct:+.2f}% | 持有{hold_days}天")

    # 最终持仓
    pos_list = []
    positions = sub_get_strategy_positions(context)
    for sec, pos in positions.items():
        if pos.amount == 0:
            continue
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos_list.append(sec)
    log.info(f"📊 最终持仓：{len(pos_list)}只")
    for sec, pos in positions.items():
        if pos.amount == 0:
            continue
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue

        current_price = sub_get_current_price(sec, context)
        cost = pos.cost_basis 
        profit_pct = (current_price / cost - 1) * 100 if cost > 0 else 0
        buy_date = g.buy_date.get(sec)
        hold_days = (context.current_dt.date() - buy_date).days if buy_date else 0
        log.info(f"   {sec} {get_name(sec)} | 成本:{cost:.3f} | 当前:{current_price:.3f} | 收益:{profit_pct:+.2f}% | 持有{hold_days}天")

    # 账户汇总
    portfolio = sub_get_strategy_portfolio(context)
    # returns = (total_value - context.portfolio.starting_cash) / context.portfolio.starting_cash * 100
    returns = portfolio.returns  # (total_value - context.portfolio.starting_cash) / context.portfolio.starting_cash * 100
    log.info(f"💰 总资产：{total_value:.2f} | 可用：{cash:.2f} | 市值：{positions_value:.2f} | 累计收益：{returns:.2f}%")
    log.info("📋🐂🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩报告结束 🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🐂")
    log.info("")




###########################################################################################################################################################################################
"""
以下是PT支持多策略分仓隔离功能。 Powered By 山红 
V1.0功能列表:
2025-10-20: PT支持多策略分仓隔离功能, 多策略运行互不干扰。
2025-10-25: 初步调试通过
2025-11-10: 实盘增加买卖队列功能,  只有卖出标的成交后，才执行买入标的。实盘场景卖出操作有时延， 卖出后不能马上执行买入操作。 回测场景不存在这个问题。
2025-11-15: 增加功能：超时没有成交订单支持撤单重新下单。
2025-11-18: 增加扣除佣金。
2025-11-20: 支持分红配送股, 除权功能。
2025-12-02: 支持order_tick函数, 便于打板操作。
2025-12-10: Fix Bug: 卖出成交后, PT(Portfolio, Position全局变量)资金到账会有几秒时间延迟(大概6秒延迟), 需等待几秒再买入, 另外个股买入资金需要重新计算。
2025-12-20: 增加 每日操作，每日持仓，策略资产 保存至Excel表格, 便于单策略复盘
2025-12-25: 支持order_market接口, 便于抢单，以便适配不同策略风格。
V1.1功能列表:
2026-03-25: Fix Bug: 1. 修正订单超时未重新提交。   2. 修正全天未成交时持仓资金错误。
2026-04-03: 支持不同策略购买相同标的。 
2026-04-03: 实盘时缺省所有卖出操作自动加入卖方队列，只有卖出操作全部完成才自动执行买入操作。 并增加控制标志 g.auto_append_sell_queue = True。
对于不用等卖出操作完成就可以执行买入操作的策略， 需要设置g.auto_append_sell_queue = False
V1.2功能列表：
2026-05-21: 支持记录最近最高收益， 以及最近回撤百分比。  
V1.3功能列表：
2026-06-27: Fix Bug: 修正 缩股时 股票数量计算不对的Bug。  
2026-06-27: Fix Bug: 修正 order_target_value 调整股票持仓数量的Bug, 如现持股10000元, 可调整为持仓为8000元, 或15000元。 原来只支持 全仓卖出买入。  
V1.4功能列表：
2026-07-13: Fix Bug: 卖出部撤再下单时数量不对.
"""    
#####################################################################################################################################

class subPortfolio():
    """_summary_
    分仓类定义，  与PT的总仓类结构定义完全相同。 并增加几个必要变量。
    """
    def __init__(self, strategy_name:str, init_cash:int, date:str):
        self.strategy_name = strategy_name  # 策略名称
        self.init_cash = init_cash          # 初始资金, 添加资金时， init_cash 与 cash都要添加
        self.cash = init_cash               # 当前可用资金（不包含冻结资金）
        self.positions = {}                 # 当前持有的标的(包含不可卖出的标的), dict类型，key是标的代码，value是Position对象
        self.portfolio_value = init_cash    # 当前持有的标的和现金的总价值
        self.positions_value = 0            # 持仓价值
        self.capital_used = 0               # 已使用的现金
        self.returns = 0                    # 当前的收益比例, 相对于初始资金
        self.pnl = 0                        # 浮动盈亏
        self.start_date = date              # 开始时间  
        self.pre_portfolio_value = init_cash # 昨日总价值  
        self.pre_max_value = None           # 最近的最高市值  
        self.pre_max_value_date = None      # 最近的最高市值的日期。 格式： 2026-05-21  
        self.drawdown_rate = None           # 回撤百分比  
        
        
    def __str__(self):
        # {'002193.SZ': <IQEngine.user_module.subPosition object at 0x7f7cf03f2010>, '002719.SZ': <IQEngine.user_module.subPosition object at 0x7f7d2446df90>, '002856.SZ': <IQEngine.user_module.subPosition object at 0x7f7d2112d050>, '002883.SZ': <IQEngine.user_module.subPosition object at 0x7f7cf03f2050>, '002188.SZ': <IQEngine.user_module.subPosition object at 0x7f7cf03f2090>, '002652.SZ': <IQEngine.user_module.subPosition object at 0x7f7cf03f20d0>}
        postion_str = "{"
        for symbol, position in self.positions.items():
            postion_str = postion_str + "\n{}: {}".format(symbol, position)
        postion_str = postion_str + "}\n"
             
        """字符串表示"""
        return "subPortfolio(strategy_name={strategy_name}, init_cash={init_cash}, cash={cash}, positions={postion_str}, portfolio_value={portfolio_value}, positions_value={positions_value}, capital_used={capital_used}, returns={returns}, pnl={pnl}, start_date={start_date}, pre_portfolio_value={pre_portfolio_value}, pre_max_value={pre_max_value}, pre_max_value_date={pre_max_value_date}, drawdown_rate={drawdown_rate}); ".format(
                    strategy_name=self.strategy_name,
                    init_cash=self.init_cash,
                    cash=self.cash,
                    postion_str=postion_str,
                    portfolio_value=self.portfolio_value,
                    positions_value=self.positions_value,
                    capital_used=self.capital_used,
                    returns=self.returns,
                    pnl=self.pnl,
                    start_date=self.start_date,
                    pre_portfolio_value=self.pre_portfolio_value,
                    pre_max_value=self.pre_max_value,
                    pre_max_value_date=self.pre_max_value_date,
                    drawdown_rate=self.drawdown_rate,
                )

class subPosition():
    """_summary_
    分仓持仓定义，  与PT的持仓类结构定义完全相同。 并增加几个必要变量。
    """
    def __init__(self):
        self.buy_date = None    # 买入日期
        self.buy_time = None    # 买入时间
        self.sell_date = None   # 卖出日期
        self.sid = None         # 股票代码
        self.name = None        # 股票名称
        self.enable_amount = 0  # 可用数量
        self.amount = 0         # 总持仓数量
        self.last_sale_price = None # 最新价格
        self.cost_basis = None      # 持仓成本价格
        self.reorder_timeout = False # 超时重新下单标志
        self.order_dict =  {}       # 订单情况。 KEY 为order_id, Value为subOrder对象。

    def __str__(self):
        """字符串表示"""
        return "subPosition: buy_date: {buy_date}, buy_time: {buy_time}, sell_date: {sell_date}, sid:{sid},name:{name}, enable_amount:{enable_amount}, amount:{amount}, last_sale_price:{last_sale_price}, cost_basis: {cost_basis}, reorder_timeout: {reorder_timeout}, order_dict: {order_dict}; ".format(
                buy_date=self.buy_date,
                buy_time=self.buy_time,
                sell_date=self.sell_date,
                sid=self.sid,
                name=self.name,
                enable_amount=self.enable_amount,
                amount=self.amount,
                last_sale_price=self.last_sale_price,
                cost_basis=self.cost_basis,
                reorder_timeout=self.reorder_timeout,
                order_dict=list(self.order_dict.keys())
            )

class subOrder():
    """_summary_
    订单对象
    """
    def __init__(self):
        # self.id = None,          # 本次下单ID
        self.dt = None,        # 本次下单时间
        self.symbol = None,            # 本次下单代码
        self.order_amount = 0       # 本次下单数量
        self.order_price  = 0        # 本次下单价格        
        self.order_cash = 0          # 本次买入锁定金额
        self.business_price = 0      # 本订单成交价              
        self.business_amount = 0     # 本订单累计成交数量              
        self.business_balance = 0    # 本订单累计成交金额
        self.settlemented = False    # 订单是否完成结算
        self.tax_commission = None   # 手续费
        self.entrust_no = None       # 委托编号
        self.orig_order_money = None # 记录本次下单原始金额,  用于超时再次下单
        self.trade_response = []     # 本订单的的响应列表, 一条或多条。  返回的成交资金已经包含费用了。
    def __str__(self):
        """字符串表示"""
        return "subOrder: dt: {dt}, symbol: {symbol}, name: {name},order_amount: {order_amount}, order_price: {order_price}, order_cash: {order_cash}, business_amount:{business_amount}, business_balance:{business_balance}, settlemented:{settlemented}, tax_commission:{tax_commission}, entrust_no:{entrust_no}; ".format(
                dt=self.dt,
                symbol=self.symbol,
                name=sub_get_stock_name(self.symbol),
                order_amount=self.order_amount,
                order_price=self.order_price,
                order_cash=self.order_cash,
                business_amount=self.business_amount,
                business_balance=self.business_balance,
                settlemented=self.settlemented,
                tax_commission=self.tax_commission,
                entrust_no=self.entrust_no,
            )        

class StockCurrentData:
    """
    股票信息类，包含股票的各种属性信息。 与聚宽的类定义完成全一样, 为了在PT中实现聚宽的get_current_data函数
    
    属性说明：
    - last_price: 最新价，09:30之前获取返回昨日收盘价
    - high_limit: 涨停价
    - low_limit: 跌停价
    - paused: 是否停止或暂停交易（停牌、未上市或退市返回True）
    - is_st: 是否为ST股（包括ST、*ST，是则返回True）
    - day_open: 当天开盘价（09:27分之后才可获取）
    - name: 股票当前名称（可用于判断ST状态和退市风险），   PT没有历史名称API, 不支持历史名称。
    - industry_code: 股票所属行业代码， 使用的PT的行业数据，  行业划分与聚宽不一样
    """
    
    def __init__(self, last_price: float, high_limit: float, low_limit: float,
                 paused: bool, is_st: bool, day_open: float, name: str, industry_code: str):
        """
        初始化股票信息对象
        
        参数：
            last_price: 最新价
            high_limit: 涨停价
            low_limit: 跌停价
            paused: 是否停止交易
            day_open: 当天开盘价
            name: 股票名称
            industry_code: 行业代码
        """
        self.last_price = last_price
        self.high_limit = high_limit
        self.low_limit = low_limit
        self.paused = paused
        self.is_st = is_st
        self.day_open = day_open
        self.name = name
        self.industry_code = industry_code
        
    
    def _judge_st_status(self) -> bool:
        """根据股票名称判断是否为ST股（包括ST、*ST）"""
        if not self.name:
            return False
        # 检查股票名称是否以ST或*ST开头
        return self.name.startswith(('ST', '*ST'))
    
    def __repr__(self) -> str:
        """返回股票信息的字符串表示"""
        return "StockInfo(name={!r}, last_price={}, high_limit={}, low_limit={}, paused={}, is_st={}, day_open={}, industry_code={!r})".format(
            self.name,
            self.last_price,
            self.high_limit,
            self.low_limit,
            self.paused,
            self.is_st,
            self.day_open,
            self.industry_code
        )


def pt_get_current_data(context, symbol_list):
    """_summary_
    用于替换 聚宽API get_current_data,     # https://www.joinquant.com/help/api/help#name:api

    Args:
        context (_type_): _description_
        symbol_list (_type_): _description_

    Returns:
        _type_: _description_
    """
    
    # 获取当前时间
    current_time = context.blotter.current_dt.strftime('%H:%M')
    
    # 获取市场数据并计算目标持仓
    daily_data = get_history(
        count=1,
        frequency="1d",
        field=['open', 'close','is_open','preclose','high_limit','low_limit','unlimited'],
        security_list=symbol_list,
        fq=g.fq_type,
        #include：是否包含当前周期，True -包含，False-不包含；选填参数，默认为False；入参类型：bool；
        #include = True 一定要修正当天价， 否则包含未来函数。  
        include=True
    )

    # 低版本的Ptrade格式转换。
    if g.python_version.startswith('3.5'):
        # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
        df_flat = daily_data.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
        df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

        df_flat.columns = ['date', 'code', 'open', 'close','is_open','preclose','high_limit','low_limit','unlimited']
        daily_data = df_flat
        
    minute_data = get_history(
        count=1,
        frequency='1m',
        field=['open', 'close', 'high', 'low'],
        security_list=symbol_list,
        fq=g.fq_type,
        include=True
        )
    
    # 低版本的Ptrade格式转换。
    if g.python_version.startswith('3.5'):
        # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
        df_flat = minute_data.to_frame()  # 转为长格式：索引=(major_axis, minor_axis, items)，值=价格
        df_flat.reset_index(inplace=True)  # 展开索引为列（此时列名是默认的：major_axis, minor_axis, items）

        df_flat.columns = ['date', 'code', 'open','close', 'high', 'low']
        minute_data = df_flat

        # 国盛PT的烂接口， 有时候get_history返回的数据不全， 再获取一次。
        if len(minute_data) < len(symbol_list):
            current_minute = context.blotter.current_dt.strftime('%Y-%m-%d %H:%M')  # YYYY-mm-dd HH:MM start_date=current_minute, 
            minute_data = get_price(symbol_list, end_date=current_minute, frequency='1m', fields=['open', 'close'], fq=g.fq_type, count=1)
            df_flat = minute_data.to_frame() 
            df_flat.reset_index(inplace=True)
            df_flat.columns = ['date', 'code', 'open','close', 'high', 'low']
            minute_data = df_flat
            
    # 合并两份数据， 清除未来数据。
    
    # 判断股票是否为ST、停牌或者退市的股票, （回测为回测当前周期，研究与交易则取系统当前时间）(str)；
    st_status = get_stock_status(symbol_list, 'ST')
        
    result_dict = {}
    for symbol in symbol_list:
        
        daily_df = daily_data[daily_data['code'].isin([symbol])]
        latest_minute_df = minute_data[minute_data['code'].isin([symbol])]
        
        last_price = None
        if is_trade():
            snapshot_dict = get_snapshot(symbol)
            last_price = snapshot_dict[symbol]["last_px"]
        else:
            last_price=latest_minute_df['close'].iloc[-1]
        # result_dict[symbol] = {
        #     'last_price' : latest_minute_df['close'].iloc[-1] , #最新价,09:30之前获取返回昨日收盘价
        #     'high_limit':  daily_df['high_limit'].iloc[-1], #涨停价
        #     'low_limit':  daily_df['low_limit'].iloc[-1],  #跌停价
        #     'paused': daily_df['is_open'].iloc[-1], # 是否停止或者暂停了交易, 当停牌、未上市或者退市后返回 True
        #     'is_st': st_status[symbol] , #是否是 ST(包括ST, *ST)，是则返回 True，否则返回 False
        #     'day_open': daily_df['open'].iloc[-1] ,  #当天开盘价,当天的开盘价至少09:27分之后才可获取
        #     #name: 股票现在的名称, 可以用这个来判断股票当天是否是 ST, *ST, 是否快要退市
        #     # industry_code: 股票现在所属行业代码, 参见 行业概念数据  blocks = get_stock_blocks(stock_code)
        # }

        result_dict[symbol] = StockCurrentData(last_price=last_price, 
                                                high_limit=daily_df['high_limit'].iloc[-1], 
                                                low_limit= daily_df['low_limit'].iloc[-1],  #跌停价
                                                paused= (daily_df['is_open'].iloc[-1] == 0), # 是否停止或者暂停了交易, 当停牌、未上市或者退市后返回 True
                                                is_st = st_status[symbol] , #是否是 ST(包括ST, *ST)，是则返回 True，否则返回 False
                                                day_open = daily_df['open'].iloc[-1] ,  #当天开盘价,当天的开盘价至少09:27分之后才可获取
                                                name = sub_get_stock_name(symbol),    # 股票现在的名称,  聚宽回测可以用这个来判断股票当天是否是 ST, *ST, 是否快要退市。 在PT中不能用这个字段判断ST，退市。
                                                industry_code = None  #get_stock_blocks(symbol)  #股票现在所属行业代码,  参见 行业概念数据。  PT中行业数据与聚宽不一样。
                                               )

    return result_dict    

def pt_get_history(count, frequency='1d', field='close', security_list=None, fq=None, include=False, fill='nan', is_dict=False):
    """_summary_
    pt_get_history 解决ptrade的接口get_history的问题：
    1、 统一所有Python版本返回为dataFrame格式。 python 3.5版本，原函数返回Pannel格式, Python 3.11原函数返回dataFrame格式。 本函数统一转换成 pandas.DataFrame格式。 
    2、 解决未来函数问题： 原函数frequency='1d'时， 并且include = True时,  获取的'close', 'volume' 是当天收盘价, 收盘成交量，这是未来数据。使用'1m'替换掉。
    3、 本接口只支持 frequency='1d', '1m'两种
    Args:
        count (_type_): _description_
        frequency (str, optional): _description_. Defaults to '1d'.
        field (str, optional): _description_. Defaults to 'close'.
        security_list (_type_, optional): _description_. Defaults to None.
        fq (_type_, optional): _description_. Defaults to None.
        include (bool, optional): _description_. Defaults to False.
        fill (str, optional): _description_. Defaults to 'nan'.
        is_dict (bool, optional): _description_. Defaults to False.
    """
    #统一格式
    if frequency == 'daily':
        frequency = '1d'
    
    history_df = None
    if isinstance(security_list, str):
        #当获取单支股票的数据
        history_df = get_history(count, frequency=frequency, field=field, security_list=security_list, fq=fq, include=include, fill=fill)

        # 解决未来函数问题。
        if frequency == '1d' and (include is True) and ('close' in field):
            minute_df = get_history(1, frequency='1m', field='close', security_list=security_list, fq=fq, include=include)
            history_df['close'].iloc[-1] = minute_df['close'].iloc[-1]
    
    elif isinstance(security_list, list) and isinstance(field, list):
        #当获取多支股票, 
        history_temp = get_history(count, frequency=frequency, field=field, security_list=security_list, fq=fq, include=include, fill=fill)

        # 老版本
        if g.python_version.startswith('3.5'):
            # 2. 通用 Panel 转平铺 DataFrame（核心步骤）, # 思路：先将 Panel 转为 MultiIndex DataFrame，再展开索引为列
            df_flat = history_temp.to_frame()  
            df_flat.reset_index(inplace=True)  
            columns_list = ['date', 'code'] + field
            df_flat.columns = columns_list
            history_temp = df_flat
        elif g.python_version.startswith('3.11'):
             # 将索引转换为'date'列
            history_temp['date'] = history_temp.index
        else:
            log.error("不支持Python Version ={}".format(g.python_version))
            return None            

        # 日线需要, 解决未来函数问题。
        if frequency == '1d' and (include is True) and ('close' in field):
            for symbol in security_list:
                minute_df = get_history(1, frequency='1m', field='close', security_list=symbol, fq=fq, include=include)
                stock_df = history_temp[history_temp['code'] == symbol]
                current_date = stock_df['date'].iloc[-1]
                # 最近日期为 current_date（日期格式，如 '2025-11-26'）和 symbol   # 修改目标行的 close 列为 minute_df的值。
                history_temp.loc[(history_temp['date'] == current_date) & (history_temp['code'] == symbol), 'close'] = minute_df['close'].iloc[-1]

        history_df = history_temp
    # 多支股票， 只获取单个字段。 返回格式是dataFrame
    elif isinstance(security_list, list) and (isinstance(field, str) or len(field) == 1) :

        #解决未来函数
        if field == 'close' and frequency == '1d' and include is True:
            frequency = '1m'
            
        history_df = get_history(count, frequency=frequency, field=field, security_list=security_list, fq=fq, include=include, fill=fill)

        pass
    else:
        log.error("请输入正确的参数格式,  security_list={} , field={}".format(security_list, field))
        pass
        
    return history_df
def filter_st_paused_delisting_stock(context, stock_list):
    """_summary_
    股票列表（该列表已剔除符合任一指定状态的标的）(list)
    过滤停牌股票  PTrade filter_stock_by_status 或者 # get_price 检查is_open字段,  

    'ST' - 查询是否属于ST股票
    'HALT' - 查询是否停牌
    'DELISTING' - 查询是否退市
    'DELISTING_SORTING' - 查询是否退市整理期(只过滤交易当日数据)

    Args:
        context (_type_): _description_
        stock_list (_type_): _description_

    Returns:
        _type_: _description_
    """

    current_date_tight = context.blotter.current_dt.strftime('%Y%m%d')

    # 过滤ST， 停牌， 退市， 退市整理期的票
    filter_stock = []
    if g.python_version.startswith('3.5'):
        filter_stock = []
        st_status = get_stock_status(stock_list, 'ST')
        # 将不是ST的股票筛选出来
        for i in stock_list:
            if st_status[i] is not True:
                filter_stock.append(i)

        stock_list = filter_stock
        filter_stock = []
        halt_status = get_stock_status(stock_list, 'HALT')
        # 将不是ST的股票筛选出来
        for i in stock_list:
            if halt_status[i] is not True:
                filter_stock.append(i)

        stock_list = filter_stock
        filter_stock = []
        delist_status = get_stock_status(stock_list, 'DELISTING')
        # 将不是ST的股票筛选出来
        for i in stock_list:
            if delist_status[i] is not True:
                filter_stock.append(i)
                
    else:
        filter_stock = filter_stock_by_status(stock_list, ["ST", "HALT", "DELISTING", "DELISTING_SORTING"],current_date_tight)            

    # PTrade上ST等数据有些不准， 进行双重过滤。  # 回测发现， 小市值有些票过段时候会被ST
    if is_trade():
        current_name_dict = get_stock_name(filter_stock)
        filter_stock =  [stock for stock in filter_stock 
                if current_name_dict[stock] is not None
                and 'ST' not in current_name_dict[stock]
                and '*' not in current_name_dict[stock]
                and '退' not in current_name_dict[stock]]

    return filter_stock

# position
def ParseJsonToObj(jsonStr:dict, objClass):
    """_summary_
    定义JSON Dict 与 class 对象互转函数
    Args:
        jsonStr (_type_): _description_ JSON String
        objClass (_type_): _description_  class对象名称

    Returns:
        _type_: _description_
    """
    # parseData = json.loads(jsonStr.strip('\t\r\n'))
    parseData = jsonStr

    if objClass.__name__ == "subPortfolio":
        result = objClass(parseData["strategy_name"],  parseData["cash"],  parseData["start_date"])
    elif objClass.__name__ == "subPosition":
        result = objClass()
    else:
        log.error("请输入正确的类名")
        return None
    
    result.__dict__.update(parseData)
 
    return result

def load_strategy_persistent_data() -> subPortfolio:
    """_summary_
    本策略持仓信息的持久化函数。 为了防止冲突，  每个策略的仓位信息需要持久化, 各自保存在一个JSON文件中。 
    不使用pkl格式, 使用JSON文件是为了提高盘后的阅读性。
    Args:
        strategy_name (_type_): _description_

    Returns:
        _type_: _description_
    """
    # # 回测场景 交易状态数据不进行持久化
    # if not is_trade():
    #     return None
    
    # 回测场景， 不用加载数据， 从头开始
    if not is_trade():
        return None

    # 实盘场景
    NOTEBOOK_PATH = get_research_path()
    
    filename =  NOTEBOOK_PATH + "running_info_"+g.strategy_name + '.json'

    saved_json = None
    sub_portfolio = None
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            saved_json = json.load(file)

        # 加载  持久化的全局参数。只支持JSON格式。
        for saved_item in g.need_persistent_list:
            # 如果变量是list ， 以持久化数据为准直接覆盖。
            if saved_item in saved_json and isinstance(getattr(g, saved_item, None), list):
                setattr(g, saved_item, saved_json[saved_item])
            # 如果变量是dict， 以持久化数据 与 程序中变量合并， dict中的相同变量名以持久化数据为准覆盖。
            elif saved_item in saved_json and isinstance(saved_json[saved_item], dict) and isinstance(getattr(g, saved_item, None), dict):
                setattr(g, saved_item, {**getattr(g, saved_item, {}),  **saved_json[saved_item]} )
            elif saved_item in saved_json:
            # 其他类型直接覆盖
                setattr(g, saved_item, saved_json[saved_item])

        # 加载资产数据
        sub_portfolio_json = saved_json['sub_portfolio']
        if sub_portfolio_json['strategy_name'] != g.strategy_name:
            log.error("策略名字不一样, {} , {} ".format(sub_portfolio_json['strategy_name'],  g.strategy_name))
            return None
        
        sub_portfolio = ParseJsonToObj(sub_portfolio_json, subPortfolio)

        positions_json_str = sub_portfolio.positions
        # 将持仓的JSON转换成Class对象
        if len(list(positions_json_str.keys())) > 0:
            positions_obj_dict = {}
            for symbol, position_str in positions_json_str.items():
                position_obj = ParseJsonToObj(position_str, subPosition)
                positions_obj_dict[symbol] = position_obj
        
            sub_portfolio.positions = positions_obj_dict            
        log.info("策略资产持久数据={} , 导入成功, Portfolio = {}".format(filename, sub_portfolio))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.error("错误: 文件 {} 未找到 {}".format(filename, e))    
        
    return sub_portfolio

def save_strategy_persistent_data(context):
    """_summary_
    保存 策略的 仓位的数据
    Args:
        g (_type_): _description_

    Returns:
        _type_: _description_
    """
    # # 回测场景 交易状态数据不进行持久化
    # if not is_trade():
    #     return

    # 回测场景不要进行数据持久化。
    if not is_trade():
        return None
    
    NOTEBOOK_PATH = "./"
    NOTEBOOK_PATH = get_research_path()
    
    filename =  NOTEBOOK_PATH + "running_info_"+g.strategy_name + '.json'

    ## 准备好备份数###
    portfolio_obj = sub_get_strategy_portfolio(context)

    # 先保存对象的链接，  持久化后需要恢复链接
    old_positions_class = portfolio_obj.positions
    
    positions = portfolio_obj.positions
    if len(list(positions.keys()))> 0:
        positions_dict = {}
        for symbol, position_obj in positions.items():
            position_dict = position_obj.__dict__
            positions_dict[symbol] = position_dict
            
            portfolio_obj.positions = positions_dict

    #JSON保存 策略的资产组合
    saved_json = {
        'sub_portfolio': portfolio_obj.__dict__,
        }
    
    # 保存需要  持久化的全局参数
    for saved_item in g.need_persistent_list:
        if hasattr(g, saved_item):
            saved_json[saved_item] = getattr(g, saved_item)
        
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(saved_json, file, ensure_ascii=False, indent=4)
        log.info("策略资产数据保存成功: {}, saved_json = {}".format(filename, saved_json))
    except Exception as e:
        log.error("策略资产数据保存失败{}, Reason= {}, json={}".format(filename, e, saved_json))

    ## 恢复持仓对象链接。
    portfolio_obj.positions = old_positions_class

    return

def inner_append_portfolio_to_excel(new_df,sheet_name="Sheet1"):
    """
    读取 Excel 并追加一行数据（支持更新/去重）
    :param new_row: 新行数据（字典格式，key=列名，value=值）
    :param sheet_name: 工作表名称
    :param index: 是否保留 pandas 索引列（默认不保留）
    """
    # 回测场景不要进行数据持久化。
    if not is_trade():
        return None
    
    NOTEBOOK_PATH = get_research_path()

    filename =  NOTEBOOK_PATH     
    if g.python_version.startswith('3.11'):
        filename =  filename + "策略资产_"+g.strategy_name + '_data.xlsx'
    elif g.python_version.startswith('3.5'):
        filename =  filename + "策略资产_"+g.strategy_name + '_data.xls'
    else:
        log.error("错误环境：{}".format(g.python_version))
        return

    try:
        # 1. 读取现有 Excel 数据（若文件不存在，会抛出 FileNotFoundError）
        df = pd.read_excel(filename, sheet_name=sheet_name)
    except FileNotFoundError as e:
        log.warning("文件不存在: {}, 异常提示={}".format(filename, e))
        # 2. 若文件不存在，创建新 DataFrame（以新行的键为列名）
        df = new_df
    except ValueError as e:
        log.warning("sheet页面 {} 不存在, 异常提示={}".format(sheet_name, e))
        # 2. 若文件不存在，创建新 DataFrame（以新行的键为列名）
        df = new_df       
    else:
        # 3. 若文件存在，追加新行（先转为 DataFrame 再合并）
        # 可选：去重（根据关键列判断，避免重复追加，例如按 "ID" 列去重）
        df = pd.concat([df, new_df], ignore_index=True)
    

    # 4. 保存回 Excel（index=False 表示不写入索引列）
    # 关键：用ExcelWriter打开文件，mode='a'（追加模式），engine='openpyxl'
    try:
        with pd.ExcelWriter(filename, mode='a', engine='openpyxl', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            log.info("成功追加页面: {} 到文件：{}".format(sheet_name, filename))
    except FileNotFoundError:
        df.to_excel(filename, sheet_name=sheet_name, index=False)
        log.info(f"成功新建文件{filename}并写入sheet【{sheet_name}】")
    except Exception as e:
        # 捕获其他未知错误，打印详细信息
        log.error(f"写入Excel文件{filename}失败，未知错误：{str(e)}")
        
    return

def sub_init_strategy_portfolio(context, init_cash=0):
    """_summary_
    initialize(context)
    1、 第一次运行： 注册运行策略，   只设置本策略的数据， 策略名称 + 可用资金 即可。
    2、 第N次运行:   读取存盘的策略运行数据，  

    Args:
        strategy_name (_type_): _description_
        g (_type_): _description_
        context (_type_): _description_
        init_cash (_type_): _description_, 初始资金
    """
    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        return context.portfolio
   
    # 读取 持久化的策略数据。
    load_strategy_data = load_strategy_persistent_data()

    # 持久化数据中没有这个策略数据， 初始注册
    if load_strategy_data is None:

        # 初始资金必须小于账户的可用资金
        # 实盘会有现金宝业务，  可用资金会少点。
        available_cash = context.portfolio.cash
        if is_trade():
            available_cash = context.portfolio.portfolio_value - context.portfolio.positions_value
        
        if init_cash > available_cash:
            log.error("输入初始资金太大, 调整为账户可用资金。初始资金{},  账户可用资金{}".format(init_cash, available_cash))
            init_cash = available_cash
                   
        # 获取当前日期
        current_date = context.blotter.current_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        sub_portfolio = subPortfolio(g.strategy_name, init_cash, current_date)
    else:
        # 读取 持久化数据， 赋值完成。 
        sub_portfolio = load_strategy_data

    return sub_portfolio
def sub_get_strategy_portfolio(context):
    """_summary_
    获取本策略的 运行有标的操作仓位的信息汇总，
    Args:
        strategy_name (_type_): _description_ 策略名称
        g (_type_): _description_   全局变量
        context (_type_): _description_ 运行环境上下文

    Returns:
        _type_: _description_ 可用资金
    """
    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        return context.portfolio

    # 刷新与校验分仓持股数据
    sub_refresh_position_data(context)
   
    sub_portfolio = g.__sub_portfolio

    return sub_portfolio

def inner_sub_get_strategy_portfolio(context):
    """_summary_
    获取本策略的 运行有标的操作仓位的信息汇总，
    Args:
        strategy_name (_type_): _description_ 策略名称
        g (_type_): _description_   全局变量
        context (_type_): _description_ 运行环境上下文

    Returns:
        _type_: _description_ 可用资金
    """

    sub_portfolio = g.__sub_portfolio

    return sub_portfolio

def sub_get_strategy_available_cash(context):
    """_summary_
    获取本策略的可用资金，
    Args:
        strategy_name (_type_): _description_ 策略名称
        g (_type_): _description_   全局变量
        context (_type_): _description_ 运行环境上下文

    Returns:
        _type_: _description_ 可用资金
    """
    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        return context.portfolio.cash
    
    sub_portfolio = g.__sub_portfolio
    if sub_portfolio.cash > context.portfolio.cash:
        #2025-02-11 10:30:00 - WARNING - 本策略可用资金大于总仓位可用资金, 本策略可用资金=18628.988400000002, 总仓可用资金=18606.445766664725
        # 回测时：总仓卖出成交扣除佣金时机,  收到卖出已成成交通知就扣除了佣金。 会造成盘中分仓可用资金大于总仓可用资金 
        # Fix Bug： 实盘场景, 如果卖出票后， 不能马上调用 sub_get_strategy_available_cash API， 会造成可用资金不足。 
        # 因为总仓的context.portfolio.cash的数据更新有近6秒延迟。 
# 2026-02-26 14:20:00 - INFO - 卖出盘后结算: symbol=002725.SZ, 跃岭股份, 下单数=-1100.0, 成本价=15.361元, 成交数=-1100, 成交均价=16.872725, 成交额=18535.0, 手续费=24.998, 利润=1612.9019999999978, 利润率=9.84%
# 2026-02-26 14:20:00 - WARNING - 本策略可用资金大于总仓位可用资金,  本策略可用资金=20726.339,  总仓可用资金=14065.07        
        log.warning("本策略可用资金大于总仓位可用资金,  本策略可用资金={},  总仓可用资金={}".format(sub_portfolio.cash, context.portfolio.cash))
        sub_portfolio.cash = context.portfolio.cash  
        pass
    
    return sub_portfolio.cash
    
def inner_del_strategy_positions(symbol): #->List[subPosition] Python 3.5 之前版本不支持指定List 类型返回值。
    """_summary_
    删除分仓策略 持仓股票
    Args:
        symbol (_type_): _description_
    """

    sub_portfolio = g.__sub_portfolio
    positions = sub_portfolio.positions

    if symbol in positions:
        del positions[symbol]

    return    

def sub_get_strategy_positions(context, symbol=None): #->List[subPosition] Python 3.5 之前版本不支持指定List 类型返回值。
    """_summary_
    获取本策略的所有持仓标的
    Args:
        strategy_name (_type_): _description_ 策略名称
        g (_type_): _description_   全局变量
        context (_type_): _description_ 运行环境上下文
    Returns:
        _type_: _description_      #如果传入的symbol,  不在持仓列表中， 返回amount=0的持仓subPosition对象
    """
    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        return context.portfolio.positions

    # 刷新最新价
    sub_portfolio = g.__sub_portfolio
    positions = sub_portfolio.positions

    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')

    hold_list = list(positions.keys())
    
    result_list = {}

    for index, holding_symbol in enumerate(hold_list):
        position = positions[holding_symbol]
        # 持仓已经卖出了。
        if position.amount == 0 and current_date > position.buy_date:
            # # 在dict枚举时，不能删除,  在尾盘结算时再删除。
            continue    
        
        position.last_sale_price = sub_get_current_price(holding_symbol, context)
    
        # 检查是否查询特定代码的持仓, 持仓会返回真实持仓。  不是持仓会返回amount=0的持仓Position对象
        # {'002188.XSHE': <Position {'sid': '002188.SZ', 'enable_amount': 2500, 'amount': 2500.0, 'last_sale_price': 6.12, 'cost_basis': 6.392, 'business_type': 'stock', 'today_amount': 0.0, 'update_time': '2025-11-24 10:21:50'}>}
        # {'601869.XSHG': <Position {'sid': '601869.SS', 'enable_amount': 0, 'amount': 0, 'last_sale_price': 73.74, 'cost_basis': 0, 'business_type': 'stock', 'today_amount': 0, 'update_time': None}>}
        if symbol is not None: 
            #传入symbol 有效并且存在
            if isinstance(symbol, str) and holding_symbol == symbol:
                return position
            #传入symbol 有效并且不存在
            elif isinstance(symbol, str) and index == (len(hold_list) - 1):
                no_position = subPosition()
                no_position.sid = symbol         # sid 标的代码
                no_position.enable_amount = 0  # 可用数量
                no_position.amount = 0         # 总持仓数量 
                return no_position
            #传入symbol 有效并且还没有轮询完成。
            elif isinstance(symbol, str):
                continue
            #传入symbol 是List， 有效并且有效
            elif isinstance(symbol, list) and holding_symbol in symbol:
                result_list[holding_symbol] = position

            #传入symbol 是List， 有效 轮询完成
            elif isinstance(symbol, list) and holding_symbol not in symbol and index == (len(hold_list) - 1):
                for query_symbol  in symbol:
                    if query_symbol not in hold_list :
                        no_position = subPosition()
                        no_position.sid = symbol         # sid 标的代码
                        no_position.enable_amount = 0  # 可用数量
                        no_position.amount = 0         # 总持仓数量
                        result_list[symbol] = no_position                    
            #传入symbol 是List有效，  轮询还没有完成
            elif isinstance(symbol, list) and holding_symbol not in symbol and index < (len(hold_list) - 1):
                continue
            
        else:
            result_list[holding_symbol] = position
            
    # 获取所有持仓。
    if symbol is None:
        return positions
    
    return result_list


def sub_get_current_price(symbol, context):
    """_summary_
    获取股票现在价格
    Args:
        symbol (_type_): _description_

    Returns:
        _type_: _description_
    """
    
    price = None
    
    if is_trade():
        snapshot = get_snapshot(symbol)
        
        price = snapshot[symbol]["last_px"]
    else:
        
        df_minute = get_history(1, frequency='1m', field=['close'], security_list=symbol, fq=g.fq_type, include=True)

        # 获取单只股票的一个，或多个字段时， 没有code这一列。 此时的dataframe列，是没有code这一列的
        # PT烂问题 ,  国盛的PT get_history接口 有时候返回数为空。 
        current_minute = context.blotter.current_dt.strftime('%Y-%m-%d %H:%M')  # YYYY-mm-dd HH:MM start_date=current_minute, 
        if len(df_minute) == 0:
            df_minute = get_price(symbol, end_date=current_minute, frequency='1m', fields=['close'], fq=g.fq_type, count=1)

        if len(df_minute) > 0:
            price = df_minute['close'].iloc[-1]
        else:
            log.error(f"获取价格失败{symbol},{sub_get_stock_name(symbol)}, time = {current_minute}")
            
    return price


def sub_interval_job_re_order_handle(context):
    """_summary_
    订单超时没成交， 撤单重新提交。
    Args:
        context (_type_): _description_
    """
    
    if not is_trade():
        return

    current_time = context.blotter.current_dt.strftime("%H:%M:%S")

    # 非交易时间退出
    if current_time < "09:30:00" or current_time > "15:00:00":
        return
    
    # order_list = get_all_orders() 
    order_list = get_orders()   # 只获取本策略订单。

    # [{'price': 135.777, 'entrust_no': '65313', 'filled_amount': 0, 'entrust_bs': 2, 'status': '6', 'symbol': '113601.SS', 'amount': -50, 'entrust_time': '2025-06-10 09:48:40'}
    # entrust_bs -- 成交方向，1-买，2-卖；
    for order_obj in order_list:
        
        symbol = order_obj.symbol

        # 只处理未成交的订单，     '2' -- "已报"，  '7' -- "部成"
        if order_obj.status == '2' or order_obj.status == '7':
            pass
        else:
            continue

        # PT有时候代码后缀会变化。
        if symbol.endswith(".XSHG"):
            # 替换后缀为 .SS
            symbol = symbol.replace(".XSHG", ".SS")
        elif symbol.endswith(".XSHE"):
            # 替换后缀为 .SZ
            symbol = symbol.replace(".XSHE", ".SZ")
        elif symbol.endswith(".SS") or symbol.endswith(".SZ"):
            # 正确代码
            pass
        else:
            log.error("错误的代码 {}".format(symbol))
            continue

        # 标的隔离， 不在本策略持仓中订单忽略。
        holding_dict = sub_get_strategy_positions(context)
        if symbol not in  holding_dict:
            log.error("错误的代码 {}".format(symbol))
            continue
        
        # 获取持仓
        position = holding_dict[symbol]
        
        # 卖单持仓应该大于0
        if order_obj.amount < 0 and position.amount <= 0: 
            log.warning("校验数据不一致, 卖出标的持仓数量为0,  order={}, position={}".format(order_obj, position))
            continue

        # 检查订单是否提交太久， 没有成交  entrust_time
        current_timestamp = int(datetime.now().timestamp())

        # 订单提交时间, 转换为秒级时间戳（浮点数，含小数部分）
        # delivered_dt = datetime.strptime(order_dict['entrust_time'], "%Y-%m-%d %H:%M:%S")
        delivered_timestamp = int(order_obj.dt.timestamp())

        if (current_timestamp - delivered_timestamp) < g.re_order_interval:
            continue
       
        # 买入时：需要检查是不是打板涨停价， 涨停价买入不撤单。
        if order_obj.amount > 0:
            df_history = get_history(1, '1d', 'high_limit', symbol, fq=None, include=True)
            high_limit = df_history['high_limit'].iloc[0]
            order_id = order_obj.id
            if order_id in position.order_dict:
                sub_order = position.order_dict[order_id]
                if sub_order.order_price == high_limit:
                    log.info("打板买入不撤单:symbol={}:{}, price={}".format(symbol, sub_get_stock_name(),sub_order.order_price))
                    continue
            else:
                log.warning("subPosition没有记录订单:symbol={}, order_id={}, order={}, position={}".format(symbol, order_id, order_obj, position))
                pass
       
        # 卖单已报， 或部成。 超时没有成交， 撤单重新提交订单。
        if order_obj.status == '2' or order_obj.status == '7':
            # 设置标志，发展订单超时重新下单。
            position.reorder_timeout = True
            cancel_order(order_obj.id)
            log.info("超时未成交, 撤单order_id={}, order={}".format(order_obj.id, order_obj))
        elif order_obj.status == '8' or order_obj.status == '6' or order_obj.status == '5':
            # 订单已成  或 已撤 就忽略
            pass
        else:
            log.warning('FF未知订单状态,  {}'.format(order_obj))
   
    return

def sub_on_order_response(context, order_list):
    """_summary_
    撤单成功， 就要重新下单。
    Args:
        context (_type_): _description_
        order_list (_type_): _description_

    Returns:
        _type_: _description_
    """

# 本交易产生的主推：[{'business_amount': 0.0, 'order_id': 'e71d1684c8a74b4ca00b3326c9eb8614', 'order_time': '2022-05-10 15:52:10.780', 'entrust_prop': '0', 'status': '2', 'price': 36.95, 
# 'entrust_no': 700006, 'error_info': '', 'amount': 200, 'stock_code': '600570.SS', 'entrust_type': '0'}]

    for order in order_list:
        symbol = order['stock_code']
        
        
        if order['entrust_type'] == '2' and order['status'] == '8':
            log.warning("撤单已成{}".format(order))
            # 是买单撤单成功， 还是卖单撤单成功？
            symbol =  order['stock_code']
            business_amount =  order['business_amount'] #(成交数量)
            order_id = order['order_id']    # 这个是被撤单的订单编号吗？
            #order_id
           
    
    return

def inner_remove_symbol_from_sell_queue(sell_symbol, context):
    """_summary_
    由于卖出标的后，持仓信息更新有几秒的时延， 需等待一下。     
    
    Args:
        sell_symbol (_type_): _description_
        context (_type_): _description_
    """

    # 最大待待10秒
    loop = 10
    
    while loop > 0:
        # 如果多策略买了相同的股票， 这里就不能调用get_position 接口 检查PT的信息有没有更新。         # 账户持仓， 与可用资金已更新。
        # position = get_position(sell_symbol)
        # if position.amount == 0: 
        #     g.sell_queue.remove(sell_symbol) 
        #     return 
        
        time.sleep(1)
        loop = loop -1 
        pass

    g.sell_queue.remove(sell_symbol) 
    log.warning("卖出成交, 删除卖出队列中股票: {},{};  卖出队列: {}".format(sell_symbol, sub_get_stock_name(sell_symbol), g.sell_queue))

    return 

def inner_callback_sell_dealed(sell_symbol, context):
    """_summary_
    用于卖出标的全部成交时的回调。 如果卖出队列全部成交，   就可以执行买入了。 
    实盘验证： on_trade_response 回调 比 全局持仓对象的Portfolio.cash 与Position 会早1~~6秒左右,  这导致可用资金没有及时到位。
    order_target_value 测试3次: 分别延时6秒, 1秒, 3秒。 order 也有时延， 测试一次时延3秒。
    order_value("518880.SS", 0) 2026-01-16 14:47:00 - WARNING - 股票委托数量为0, 委托取消
    
    Args:
        sell_symbol (_type_): _description_
        context (_type_): _description_
    """
    # 回测场景马上成交， 不用买卖队列； 实盘才需要买卖队列。 
    if not is_trade():
        return

    if sell_symbol not in g.sell_queue or len(g.sell_queue) == 0:
        return

    if len(g.sell_queue) > 1:
        # 还有 2个， 及以上标的， 买入操作还需要再等待
        # 删除 卖出标的
        inner_remove_symbol_from_sell_queue(sell_symbol, context)
        return

    # 删除 卖出标的
    inner_remove_symbol_from_sell_queue(sell_symbol, context)

    buy_list = list(g.buy_queue.keys())
    buy_number = len(list(buy_list))

    if buy_number == 0:
        log.warning("卖出队列已全部成交, 买入队列没有标的: {} ".format(g.buy_queue))
        return

    # 由于所有卖出股票已经成交，  可用资金增加，需要重新计算每支股票的可用资金。
    # 这里PTrade还有问题， 根据实盘验证： 
    # on_trade_response回调 比PT的Position全局变量更新更早, Portfolio 中的可用资金没有 还没有更新？
    available_cash = sub_get_strategy_available_cash(context)

    single_value = available_cash/buy_number
    
    for buy_symbol in buy_list:
        buy_dict = g.buy_queue[buy_symbol]
        if buy_dict['callback'] is not None:
            # buy_dict['callback'] 保存的函数字符串名称， 必须转换成函数。
            callback_func = globals()[buy_dict['callback']]
            callback_func(context)
            pass
        else:
            log.info("重新调整股票 ({}:{}) 买入金额,  原买入金额={:.2f}元， 调整后资金={:.2f} 元".format(buy_symbol, sub_get_stock_name(buy_symbol), buy_dict['value'], single_value))
            sub_order_target_value(buy_symbol, single_value, context)
            
        # 买入完成， 删除买入队列中标的
        del g.buy_queue[buy_symbol]
    
    return

def sub_add_sell_stock_into_queue(sell_symbol, context):
    """_summary_
    往卖方队列增加卖出标的

    Args:
        sell_symbol (_type_): _description_
        context (_type_): _description_
    """
    # 回测场景会马上成交， 不用卖方队列。
    if not is_trade():
        return
    
    # 非字符串
    if isinstance(sell_symbol, str) is False:
        log.error(f"输入参数错误: {sell_symbol}")
        return
    
    if sell_symbol not in g.sell_queue:
        g.sell_queue.append(sell_symbol)
    
    return

def sub_remove_sell_stock_from_queue(sell_symbol, context):
    """_summary_
    往卖方队列删除卖出标的

    Args:
        sell_symbol (_type_): _description_
        context (_type_): _description_
    """
    if sell_symbol in g.sell_queue:
        g.sell_queue.remove(sell_symbol)
    
    return

def sub_add_buy_stock_into_queue(buy_symbol, value, price, context, sell_list=None, callback=None):
    """_summary_
    如果有买操作（买入标的），  紧跟在卖操作之后, 需要等卖操作成交后才能执行买操作,  
    需要增加买卖操作队列,  sub_add_buy_stock_into_queue 放在

    Args:
        buy_symbol (_type_): _description_
        value (_type_): _description_
        price (_type_): _description_
        context (_type_): _description_
        sell_list (_type_, optional): _description_. Defaults to None.
        callback (_type_, optional): _description_. Defaults to None. 如果定义了回调函数， 使用回调函数买入, 否则使用sub_order_target_value买入。
                                    call_back 传入函数名称， 内部保存函数名称字符串， 因为在JSON中函数指针不能持久化。
    """

    all_buy_symbol_list = list(g.buy_queue.keys())
        
    # 防止重入
    if buy_symbol not in all_buy_symbol_list:
        if callback is not None:
            callback = callback.__name__
        buy_dict = {'symbol': buy_symbol, "value": value, "limit_price": price, 'callback': callback}
        g.buy_queue[buy_symbol] = buy_dict  

    # 增加卖方队列
    if sell_list is not None and len(sell_list) > 0:
        for sell_symbol in sell_list:
            sub_add_sell_stock_into_queue(sell_symbol, context)
        
    return

def sub_clear_buy_sell_queue(context):
    """_summary_
    清空所有买卖队列
    """

    current_time = context.blotter.current_dt.strftime("%H:%M:%S")

    if current_time > "15:01:00" and (len(g.sell_queue) > 0 or len(list(g.buy_queue.keys())) > 0):
        log.warning("今天交易已结束, 还有卖队列没有成交, sell queue = {}, buy queue = {}".format(g.sell_queue, g.buy_queue))
    
    # 买卖队列，   如果买入标的 要等 卖队列中标的成交才可以买入， 可增加这个队列。  
    g.sell_queue = []                # 卖出队列，   格式： ["002222.SZ","601111.SZ"]
    g.buy_queue = {}                  # 买入队列,    格式： {'001654.SZ':{"symbol": '001654.SZ', "buy_value": 10000, "limit_price": 10.1, "callback": None}}
    
    return

def inner_check_sell_queue_dealed(context):
    """_summary_
    检查是否所标的都已卖出。
    如果有多策略 有相同标的。 如何检查呢？
    Args:
        stocks (_type_): _description_
        context (_type_): _description_
        g (_type_): _description_

    Returns:
        _type_: _description_  False 有标的没成交， True 所有标的都成交
    """
    stocks = g.sell_queue
    
    # 卖出队列没有标的
    if len(stocks) == 0:
        return True
    
    # holding_dict = get_positions(stocks)
    
    # all_dealed_flag = True
    # for symbol, position in holding_dict.items():
    #     # 有标的还没有成交。 如何多策略有相同标的， 不能检查持仓数量， 必须检查卖出票的订单状态,  或者直接检查卖方队列有没有清空。 
    #     if position.amount > 0:
    #         all_dealed_flag = False
    #         break
 
    return False

def sub_order_tick(symbol, amount, context, priceGear='1', limit_price=None):
    """_summary_

    返回一个委托流水编号(str)
    Args:
        symbol (_type_): _description_
        amount (_type_): _description_
        context (_type_): _description_
        priceGear (str, optional): _description_. Defaults to '1'.
        limit_price (_type_, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """

    if sub_use_orig_portfolio_data():
        order_number = order_tick(symbol, amount, priceGear=priceGear, limit_price=limit_price)
        return order_number

    # 交易场景， 获取 标的的即时价格
    price = limit_price
    if price is None:
        price = sub_get_current_price(symbol, context)

    # 获取当前日期
    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')
    current_time = context.blotter.current_dt.strftime("%H:%M:%S")
    
    # 检查是否全部卖出
    if amount == 0:
        position = sub_get_strategy_positions(context, symbol=symbol)

        #是否已卖出。
        if position.enable_amount == 0:
            log.error("{}, {} 已全部卖出".format(symbol, sub_get_stock_name(symbol)))
            return None

        amount = 0 - abs(position.enable_amount)
    
    if amount < 0:
        positions = sub_get_strategy_positions(context)
        if symbol not in positions:
            log.error("卖出操作失败, 持仓数据错误， 不存在的持仓{}".format(symbol))
            return None

        position = positions[symbol]

        position.sell_date = current_date
        # 可用数量变成0
        position.enable_amount = position.enable_amount - abs(amount)

        sub_order = subOrder()

        # 本次卖出总量
        sub_order.order_amount = 0 - abs(amount)
        sub_order.dt = current_date + " " + current_time
        sub_order.symbol = symbol
        sub_order.order_price = price

        # 卖出操作, 回测场景： order_target_value 先回调 on_trade_response, 再
        if not is_trade():
            position.order_dict["bt_order_id"] = sub_order

        order_id = order_tick(symbol, amount)

        if order_id is None:
            log.error("卖出错误, 卖出票={}, {}, order_flow_no={}".format(symbol, sub_get_stock_name(symbol) , order_id))
            return None

        position.order_dict[order_id] = sub_order 

        if not is_trade():
            del position.order_dict["bt_order_id"]

    else:
        # 校验是否已经持有 买入的股票,   避免多策略冲突。
        holding_dict = context.portfolio.positions
        holding_list = list(holding_dict.keys())
        if symbol in holding_list:
            hold_position = holding_dict[symbol]
            if hold_position.amount > 0:
                log.warning("已经持有买入标的, 不再买入: {symbol}, {name}".format(symbol=symbol, name=sub_get_stock_name(symbol)))
                return None
            
        # 买入操作
        portfolio = inner_sub_get_strategy_portfolio(context)    
        # 可用资金
        used_money = amount * price 
        value = used_money
        if value > portfolio.cash:
            value = portfolio.cash*0.999    # 留出手续费
            new_amount = int(value/100/price)*100
            if new_amount < 100:
                log.error("买入金额太小, 股数小于100. 买入金额={},  买入票={}".format(value, symbol))
                return None
            log.error("买入 {symbol}, 金额大于可用金额.  买入金额={value} > 可用金额{available_cash}, 重新调整买入数量={new_amount}".format(symbol=symbol, value=value, available_cash=portfolio.cash, new_amount = new_amount))
            amount = new_amount
        
        if value > context.portfolio.cash:
            value = portfolio.cash*0.999    # 留出手续费
            new_amount = int(value/100/price)*100
            if new_amount < 100:
                log.error("买入金额太小, 股数小于100. 买入金额={},  买入票={}".format(value, symbol))
                return None
            log.error("买入金额大于总仓可用金额.  买入金额={value} > 可用金额{available_cash}。 买入票={symbol}, 重新调整买入数量={new_amount}".format(value=value, available_cash=context.portfolio.cash, symbol=symbol, new_amount = new_amount))
            amount = new_amount
        
        # 可用资金
        used_money = amount * price 
        portfolio.cash = portfolio.cash - used_money 
       
        sub_position = subPosition() 
        sub_order = subOrder()
        sub_order.dt = current_date + " " + current_time
        sub_order.symbol = symbol
        sub_order.order_amount = amount
        sub_order.order_price = price
        sub_order.order_cash = used_money
        sub_order.business_amount = 0
        sub_order.business_balance = 0

        position_dict = {
                'buy_date':  current_date,    # 买入日期
                'buy_time':  current_time ,   # 买入时间
                'sell_date':  None,   # 卖出日期
                'sid':  symbol ,        # sid 标的代码
                'name': sub_get_stock_name(symbol),
                'enable_amount':  0,  # 可用数量
                'amount': 0,         # 总持仓数量
                'last_sale_price': None, # 最新价格
                'cost_basis': price,      # 持仓成本价格
                'order_dict': {}         # 这个标的订单
            }
        sub_position.__dict__.update(position_dict)

    
        portfolio.positions[symbol] = sub_position

        #Fix BUG: 回测场景中, on_trade_response - 交易主推(可选)  函数先回调， order函数才会返回。 这时order_id 还 没生成。 收盘校验就会出错的。
        # 这里需要检查  on_trade_response 有没有 回调成功。
        if not is_trade():
            sub_position.order_dict["bt_order_id"] = sub_order
            
        # order_id = order(symbol, amount, limit_price=price)
        # order_id = order_target_value(symbol, value, limit_price=price)
        order_id = order_tick(symbol, amount, limit_price=limit_price)

        if order_id == "None" and  order_id is None:
            log.error("order_id买入出错, 买入金额={},  买入票={}:{}, 数量 = {}, 价格 = {}, order_id={}".format(used_money, symbol, sub_get_stock_name(symbol), amount, price, order_id))
            return None

        # 回测场景
        if not is_trade():
            del sub_position.order_dict["bt_order_id"]
        else: 
            sub_position.order_dict[order_id] = sub_order
            pass

    return order_id

def sub_order_target_value(symbol, value, context, sell_list = None, limit_price = None):
    """_summary_
    买卖操作
    
    PT的API说明：  
    实盘验证： order_target_value(security, value, limit_price=None) 有时延问题。
    柜台返回持仓数据体现当日变化(由柜台配置决定)：交易场景中持仓信息同步有时滞，一般在6秒左右。 
    
    Args:
        strategy_name (_type_): _description_
        symbol (_type_): _description_
        value (_type_): _description_
        context (_type_): _description_
        g (_type_): _description_

    Returns:
        _type_: _description_
        None:   买入失败
        True:   进入买入队列
        order_id: 买入id
    """

    if sub_use_orig_portfolio_data():
        # log.info("当前运行场景：回测")        
        order_id = order_target_value(symbol, value)
        return order_id

    # 交易场景， 获取 标的的即时价格
    price = limit_price
    if price is None:
        price = sub_get_current_price(symbol, context)

    if price == 0:
        log.info(f"股票价格为零, 可能停牌了, 不能买入。 {symbol}:{sub_get_stock_name(symbol)}, 价格={price}")
        return None

    # 检测 卖出，还是买入股票。
    positions = sub_get_strategy_positions(context)
    operated_amount = 0
    if symbol in positions and value > 0:
        position = positions[symbol]
        position_value = position.amount * price 

        buy_in_value = value - position_value
        # operated_amount 大于0表示买入股票数量，  小于0表示卖出股票数量。
        operated_amount = int(buy_in_value/100/price)*100
        if operated_amount < 100 and operated_amount > -100:
            # 调整数量不足100， 不买入,  也不卖出。
            log.info(f"调整数量不足100。 {symbol}:{sub_get_stock_name(symbol)}, 市值 = {position_value}, 目标金额 = {value}, 价格={price}, 数量={operated_amount}")
            return True
 
    # 实盘场景： 如果买入的标的symbol， 必须在sell_list成交后才能买入， 先入队列。
    # 回测场景的买卖操作没有时延。
    if is_trade() and value > 0 and (sell_list is not None):
        sub_add_buy_stock_into_queue(symbol, value, limit_price, context, sell_list) 
        log.info("买入标的入队等待={}, {},  卖出队列={}".format(symbol, sub_get_stock_name(symbol), g.sell_queue))
        
    
    # 实盘场景： 买操作必须检查， 检查相关的卖队列是否标的有没有成交。
    if is_trade() and value > 0 and (sell_list is not None or len(g.sell_queue) > 0):
        if inner_check_sell_queue_dealed(context) is False:
            log.warning("买入标的={}, {},  还有卖队列没有成交={}".format(symbol, sub_get_stock_name(symbol), g.sell_queue))
            sub_add_buy_stock_into_queue(symbol, value, limit_price, context, sell_list) 
            return True
        else:
            # 所有卖队列都已成交， 可以买入了。 删除买队列中的 待买入标的
            if symbol in g.buy_queue:
                del g.buy_queue[symbol]

    # 获取当前日期
    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')
    current_time = context.blotter.current_dt.strftime("%H:%M:%S")
            
    if value == 0 or operated_amount < 0:
        if symbol not in positions:
            log.error("卖出操作失败, 持仓数据错误， 不存在的持仓{}".format(symbol))
            return None

        position = positions[symbol]

        # 检查可卖数量。
        if position.enable_amount == 0 or position.amount == 0 :
            log.error("本策略可卖数量为0: 股票({}, {}):  可用数={}, 总数={}".format(symbol, sub_get_stock_name(symbol), position.enable_amount, position.amount))
            return None

        # 持仓数量检验， 可能与其他策略持有相同股票。 不能卖出其他策略股票。
        main_position = get_position(symbol)
        if position.enable_amount < main_position.enable_amount:
            log.warning("本策略股票({}, {}): 可用持仓数量{}小于 总仓股票持仓可用数量{}; 可能与其他策略持仓相同股票。".format(symbol, sub_get_stock_name(symbol), position.enable_amount , main_position.enable_amount))
        
        if position.enable_amount > main_position.enable_amount:
            lost_market_value = price * (position.enable_amount - main_position.enable_amount) 
            # FFFFFFFFixed 分仓发现了 损失金额， 是否程序恢复， 还是手动恢复？ 暂时手动恢复吧。
            # sub_portfolio = sub_get_strategy_portfolio(context)
            # sub_portfolio.cash = sub_portfolio.cash + lost_market_value
            if position.reorder_timeout is True:
                log.error("可能重新下单时总仓持仓数据还没有恢复: 股票({}, {}): 分仓持仓数量{}大于总仓股票持仓数量{}; 恢复损失金额:{}".format(symbol, sub_get_stock_name(symbol), position.enable_amount , main_position.enable_amount, lost_market_value))
            else:
                log.error("总分仓数据错误: 本策略股票({}, {}): 分仓持仓数量{}大于总仓股票持仓数量{}; 恢复损失金额:{}".format(symbol, sub_get_stock_name(symbol), position.enable_amount , main_position.enable_amount, lost_market_value))
                position.enable_amount = main_position.enable_amount
                position.amount = main_position.amount

        if position.enable_amount != position.amount:
            log.error("分仓持仓数据错误11: 本策略股票({}, {}): 持仓可用数量{} 不等于 总数量{}".format(symbol, sub_get_stock_name(symbol), position.enable_amount, position.amount))

        if main_position.enable_amount == 0:
            log.error("总仓可卖数量为0: 股票({}, {}): 可用数={}, position = {}".format(symbol, sub_get_stock_name(symbol), main_position.enable_amount, position))
            # 暂时不返回， 可能重新下单时总仓持仓数据还没有恢复, 此时可能 main_position.enable_amount 为0 
            # return None

        sub_order = subOrder()

        sub_order.dt = current_date + " " + current_time
        sub_order.symbol = symbol
        sub_order.order_price = price
        # 检查是否部分卖出。
        if operated_amount < 0:
            sub_order.order_amount = operated_amount
        else:
            # 否则就是卖出全部。
            sub_order.order_amount = 0 - abs(position.enable_amount)
        # 记录本次下单原始金额
        sub_order.orig_order_money = value

        # 全部卖出时可用数量变成0,  部分卖出时减少卖出的数量。
        position.enable_amount = position.enable_amount + sub_order.order_amount
        position.sell_date = current_date
        

        # 卖出操作, 回测场景： order_target_value 先回调 on_trade_response, 再
        if not is_trade():
            position.order_dict["bt_order_id"] = sub_order

        # order_id = order(symbol, sub_order.order_amount, limit_price=price)
        order_api_type = getattr(g, "order_api_type", None)
        order_api_type = getattr(g, "sell_api_type", None)  #兼容处理
        
        order_id = None

        #  "order_market_five_dealed" - 按市价进行委托(五档即时成交),    
        if order_api_type == 'order_market_five_dealed':
            market_type = 1  #1：最优五档即时成交剩余转限价(上海)
            if symbol.endswith('SZ'):
                market_type = 4  # 4：最优五档即时成交剩余撤销；(深圳)

            order_id = order_market(symbol, sub_order.order_amount, market_type, limit_price=price)
        ## "order_market_peer_price" - 按市价进行委托(对手最优价成交),  
        elif order_api_type == 'order_market_peer_price':
            market_type = 0 # 0：对手方最优价格；
            order_id = order_market(symbol, sub_order.order_amount, market_type, limit_price=price)

        # "order_target_value"--调整股票持仓市值到value价值 (多策略同标的时不能用, 否则会将其他策略标的也处理掉)
        elif order_api_type == 'order_target_value':
            ## 如何有多策略买卖相同的标的？ 就不能使用 order_target_value 接口， 必须使用 order 接口， 指定买卖数量， 与价格。
            order_id = order_target_value(symbol, value, limit_price=limit_price)
            
        # "order"-按数量买卖
        else:
            order_id = order(symbol, sub_order.order_amount, limit_price=limit_price)
        

        position.order_dict[order_id] = sub_order 

        if not is_trade():
            del position.order_dict["bt_order_id"]
        elif getattr(g, "auto_append_sell_queue", True):
            #检查是否 所有卖出标的， 统一入卖方队列。 不管后面有没有买入股票。
            sub_add_sell_stock_into_queue(symbol, context)

    else:
        ## 如何有多策略买卖相同的标的？ 就不能使用 order_target_value 接口， 必须使用 order 接口， 指定买卖数量， 与价格。
        order_api_type = getattr(g, "order_api_type", None)
        if order_api_type == "observe_not_buy":
            log.info(f"配置只观察不买入。 放弃买入={symbol}:{sub_get_stock_name(symbol)}")
            return None
        
        # 买入操作， 检校分仓与主仓的可用资金是否足够。
        portfolio = inner_sub_get_strategy_portfolio(context)    
        # 保存原始买入资金, 并校验买入资金是否足够。
        orig_value = value 
        if (value > portfolio.cash * 0.999 and operated_amount == 0):
            log.warning("买入金额大于本策略可用金额。  买入金额={value} > 可用金额{available_cash}。 买入票={symbol}:{name}, 增加数量={operated_amount} ".format(value=value, available_cash=portfolio.cash, symbol=symbol, name=sub_get_stock_name(symbol), operated_amount = operated_amount))
            value = portfolio.cash*0.999        #  留出手续费
            log.warning(f"1.预留0.1%手续费; 调整买入金额为 ={value}")

        if (operated_amount*price > portfolio.cash*0.999):
            operated_value = operated_amount*price
            log.warning("调整买入金额大于本策略可用金额22.  买入金额={operated_value} > 可用金额{available_cash}。 买入票={symbol}:{name}, 增加数量={operated_amount} ".format(operated_value=operated_value, available_cash=portfolio.cash, symbol=symbol, name=sub_get_stock_name(symbol), operated_amount = operated_amount))
            operated_value = portfolio.cash*0.999    # 留出手续费
            operated_amount = int(operated_value/100/price)*100
            log.warning(f"2.预留0.1%手续费; 调整买入金额为 ={operated_value}, 调整买入数量为={operated_amount}")
        
        if (value > context.portfolio.cash*0.999 and operated_amount == 0):
            log.warning("买入金额大于总仓可用金额.  买入金额={value} > 总仓可用金额{available_cash}。 买入票={symbol}:{name},  增加数量={operated_amount}".format(value=value, available_cash=context.portfolio.cash, symbol=symbol, name=sub_get_stock_name(symbol), operated_amount = operated_amount))
            value = context.portfolio.cash*0.999    # 留出手续费
            log.warning(f"3.预留0.1%手续费; 调整买入金额为 ={value}")

        if (operated_amount*price > context.portfolio.cash*0.999):
            operated_value = operated_amount*price
            log.warning("调整买入金额大于总仓可用金额22.  买入金额={operated_value} > 可用金额{available_cash}。 买入票={symbol}:{name}, 增加数量={operated_amount} ".format(operated_value=operated_value, available_cash=context.portfolio.cash, symbol=symbol, name=sub_get_stock_name(symbol), operated_amount = operated_amount))
            operated_value = context.portfolio.cash*0.999    # 留出手续费
            operated_amount = int(operated_value/100/price)*100
            log.warning(f"4.预留0.1%手续费; 调整买入金额为 ={operated_value}, 调整买入数量为={operated_amount}")

        # 校验是否已经持有 买入的股票,   避免多策略冲突。
        holding_dict = context.portfolio.positions 
        holding_list = list(holding_dict.keys())
        if symbol in holding_list:
            hold_position = holding_dict[symbol]
            if hold_position.amount > 0 and is_etf_lof_fund(symbol):
                log.warning("请注意其他策略已经持有相同的ETF: {symbol}, {name}".format(symbol=symbol, name=sub_get_stock_name(symbol)))
            elif hold_position.amount > 0:
                log.warning("请注意其他策略已经持有相同股票: {symbol}, {name}".format(symbol=symbol, name=sub_get_stock_name(symbol)))
        
        amount = int(value/100/price)*100
        if amount < 100:
            log.error("买入金额太小, 股数小于100. 买入金额={},  买入票={}".format(value, symbol))
            return None
        
        # 检查是不是调整买入更多数量。
        if operated_amount > 0:
            amount = operated_amount
        if amount < 100:
            log.error("买入股数太小, 股数小于100. 买入数量={},  买入票={}".format(operated_amount, symbol))
            return None
        
        #order(security, amount, limit_price=None) 该接口用于买卖指定数量为amount的股票，同时支持国债逆回购
        # order_id = order_target(symbol, amount, limit_price=price)
        # 可用资金减少。
        used_money = amount * price 
        portfolio.cash = portfolio.cash - used_money 
       
        sub_position = subPosition() 
        sub_order = subOrder()
        sub_order.dt = current_date + " " + current_time
        sub_order.symbol = symbol
        sub_order.order_amount = amount
        sub_order.order_price = price
        sub_order.order_cash = used_money
        sub_order.business_amount = 0
        sub_order.business_balance = 0
        # 记录本次下单原始金额
        sub_order.orig_order_money = orig_value


        sub_position.buy_date = current_date
        sub_position.buy_time = current_time
        sub_position.sid = symbol
        sub_position.name = sub_get_stock_name(symbol)
        sub_position.enable_amount = 0
        sub_position.amount = 0
        sub_position.cost_basis = price
        sub_position.last_sale_price = price
    
        # 检查是否已经有这个股票的持仓
        if symbol in portfolio.positions:
            # 已经这支股票的持仓,  新旧持仓进行合并；
            old_sub_position = portfolio.positions[symbol]
            
            if old_sub_position.amount > 0 or old_sub_position.enable_amount > 0:
                log.info(f"新增持仓, 还有旧持仓. old position = {old_sub_position}")
                #持仓数量进行合并
                sub_position.amount = sub_position.amount + old_sub_position.amount
                sub_position.enable_amount = sub_position.enable_amount + old_sub_position.enable_amount
            #合并订单
            sub_position.order_dict.update(old_sub_position.order_dict) 

            portfolio.positions[symbol] = sub_position
            pass
        else:
            portfolio.positions[symbol] = sub_position

        #Fix BUG: 回测场景中, on_trade_response - 交易主推(可选)  函数先回调， order函数才会返回。 
        # 这时order_id 还 没生成。 收盘校验就会出错的。
        # 这里需要检查  on_trade_response 有没有 回调成功。
        if not is_trade():
            sub_position.order_dict["bt_order_id"] = sub_order

        order_id = None
        
        #  "order_market_five_dealed" - 按市价进行委托(五档即时成交),    
        if order_api_type == 'order_market_five_dealed':
            market_type = 1  #1：最优五档即时成交剩余转限价(上海)
            if symbol.endswith('SZ'):
                market_type = 4  # 4：最优五档即时成交剩余撤销；(深圳)

            order_id = order_market(symbol, amount, market_type, limit_price=price)
        ## "order_market_peer_price" - 按市价进行委托(对手最优价成交),  
        elif order_api_type == 'order_market_peer_price':
            market_type = 0 # 0：对手方最优价格；
            order_id = order_market(symbol, amount, market_type, limit_price=price)

        # "order_target_value"--调整股票持仓市值到value价值 (多策略同标的时不能用, 否则会将其他策略标的也处理掉)
        elif order_api_type == 'order_target_value':
            ## 如何有多策略买卖相同的标的？ 就不能使用 order_target_value 接口， 必须使用 order 接口， 指定买卖数量， 与价格。
            order_id = order_target_value(symbol, orig_value, limit_price=limit_price)
        else:
            order_id = order(symbol, amount, limit_price=limit_price)
            

        if order_id == "None" or order_id is None:
            log.error("sub买入出错, 买入票={}:{}, 买入金额={}, price = {}, order_id={}".format(symbol, sub_get_stock_name(symbol), value, limit_price, order_id))

            # 买入错误,  恢复可用资金。 并删除持仓。
            portfolio.cash = portfolio.cash + sub_order.order_cash
            if sub_position.amount == 0:
                inner_del_strategy_positions(symbol)
            return order_id

        sub_position.order_dict[order_id] = sub_order
        # 回测场景, 已返回真实的order_id, 删除暂时的回测 bt_order_id
        if not is_trade():
            del sub_position.order_dict["bt_order_id"]
            pass
        else: 
            # 实盘场景买入数量，价格可能不一致，同步刷新一下。 
            # PT接口的问题：get_order 取不到委托价格, ## limit -- 指定价格, 为limit_price=price， 不传入为None，这个不是委托价格，不能取这个字段。
            current_order_obj = get_order(order_id)[0]
            # get_all_orders(security=None) 返回为dict list,可以取得委托价格。 
            current_order_list = get_all_orders(security=symbol)  

            current_order = None
            
            # 通过委托编号， 查到匹配的订单号
            for order_loop in current_order_list:
                if order_loop['entrust_no'] == current_order_obj.entrust_no:
                    current_order = order_loop
                    break

            sub_order.entrust_no = current_order_obj.entrust_no
            #找到相应的订单
            if current_order is not None:
                log.info(current_order)
                sub_order.order_price = current_order['price']  ## limit -- 指定价格为None，这个不是委托价格，不能取这个字段。
                real_order_cash = abs(current_order['amount']*current_order['price'])
                sub_order.order_cash = real_order_cash
                sub_order.order_amount = current_order['amount']
                sub_order.order_price = current_order['price']

                # 按真实锁定金额 修改 可用资金
                portfolio.cash = portfolio.cash + used_money - real_order_cash 
            pass
       
    return order_id
    
def inner_after_trading_settlement(position:subPosition, sub_order:subOrder, context):
    """_summary_
    盘后结算： 扣除佣金， 恢复未成交金额
    Args:
        position (subPosition): _description_
        sub_order (subOrder): _description_
        g (_type_): _description_
        context (_type_): _description_
    """
    
    # 买入已成: symbol=002890.SZ, name=弘宇股份, 下单数价=1100, 14.98元, 成交数=1100, 成交价=14.982247000000001
    # 为什么买入价总是比 下单价大了一点？

    current_time = context.blotter.current_dt.strftime("%H:%M:%S")
    
    # 结算只能是一次, # 已完成结算，直接退出。
    if sub_order.settlemented is True:
        if current_time > '15:10:00':
            #盘后结算， 可用数量 与总量一致。
            position.enable_amount = position.amount 
        return
    else:
        # 未完成结算
        sub_order.settlemented = True

    # 部成的结算在算后。
    if current_time > '15:10:00':
        #盘后结算， 可用数量 与总量一致。
        position.enable_amount = position.amount 

    symbol = position.sid 

    # 计算成交总金额,
    used_money = sub_order.business_balance
    business_amount = sub_order.business_amount
    business_balance = sub_order.business_balance
        
                    
    # 印花税 + 佣金 trade_response的响应已经扣除了费用。
    tax_commission = sub_calculate_commission_and_tax(symbol, sub_order, used_money, context) 
    #2025-02-11 10:30:00 - WARNING - 本策略可用资金大于总仓位可用资金, 本策略可用资金=18628.988400000002, 总仓可用资金=18606.445766664725
    # 卖出成交扣除佣金时机： 收到成交通知就扣除了佣金。

    # 计算成交均价。
    if business_amount == 0:
        log.error(f"错误成交数量 business_amount = {business_amount}, position={position}, order={sub_order}")    
    business_price = abs(custom_round((abs(used_money) + tax_commission)/abs(business_amount), 6))
    #记录本次订单成交均价， 与手续费。
    sub_order.business_price = business_price
    sub_order.tax_commission = tax_commission
    
    portfolio = inner_sub_get_strategy_portfolio(context)
    
    # 应该最后再算佣金吧， 这里算佣金会不会双算呢？  减去佣金, 不应该 
    portfolio.cash = portfolio.cash - tax_commission 
    
    #盘中买入已成， 盘后不再处理。 盘后可用数量需要与全部数量相等。 
    direction = "卖出"
    benefit_selled = None
    benefit_rate = 0
    
    if sub_order.order_amount > 0:
        direction = "买入"
        # 按成交价， 算出成本价。
        position.cost_basis = business_price
    else:
        # 如果是卖出， 计算盈利金额,  利润率。
        benefit_selled =  abs(business_balance) - abs(business_amount* position.cost_basis) - abs(tax_commission) 
        benefit_rate = (business_price - abs(position.cost_basis))/abs(position.cost_basis) 
        
        
    log.info("{direction}盘后结算: symbol={stock_code}, {stock_name}, 下单数={order_amount}, 成本价={cost_basis}元, 成交数={business_amount}, 成交均价={business_price}, 成交额={business_balance}, 手续费={tax_commission}, 利润={benefit_selled}, 利润率={benefit_rate:.2%}".format(
        direction=direction,
        stock_code=symbol,
        stock_name=sub_get_stock_name(symbol),
        order_amount=sub_order.order_amount,
        cost_basis = position.cost_basis,
        # order_price=sub_order.order_price,
        business_amount=business_amount,
        business_price=business_price,
        business_balance=abs(business_balance),
        tax_commission=tax_commission,
        benefit_selled = benefit_selled,
        benefit_rate = benefit_rate
    ))

    # 校验： 买入已成， 但是 买入总数量，  与累计成交数量不一致。 
    if abs(sub_order.order_amount) != abs(business_amount) and (not is_trade()):
        # 2025-11-20 09:33:50 - INFO - 买入累计已成: symbol=000586.SZ, name=汇源通信, 下单数价=7600, 12.99元, 成交数=1200/7600, 成交价=12.97                
        # 2025-11-20 15:30:00 - INFO - 盘后买入已成结算: symbol=000586.SZ, 汇源通信, 下单数价==7600, 12.99元, 成交数=6900, 成交价=12.978, 手续费=31.23                
        log.warning("下单总数量 与 累计成交数量不一致。symbol ={}; sub_order={};  business_amount={} ".format(symbol, sub_order, business_amount))
        
    # 买入时： 恢复未成交的资金。
    no_dealed_amount = abs(sub_order.order_amount) - abs(business_amount)
    if sub_order.order_amount > 0:
        
        # 1、计算未成交的股数，  需要恢复金额。
        no_dealed_money = no_dealed_amount * sub_order.order_price
        
        # 2、比较锁定金额  与  已成交的金额。  成交金额可能比锁定金额 多， 或者少，也要恢复。
        no_order_cash = (business_amount)*sub_order.order_price - abs(business_balance)
        portfolio.cash = custom_round(portfolio.cash + no_dealed_money + no_order_cash, 2) 

    return

def inner_update_sub_position(trade, position:subPosition, sub_order:subOrder, context):
    """_summary_
    更新持仓信息。
    Args:
        order (_type_): _description_ 订单对象，
        position (_type_): _description_ 持仓对象
        strategy_name (_type_): _description_ 策略名，唯一
        g (_type_): _description_  全局变量
        context (_type_): _description_ 运行上下文
    """
    current_time = context.blotter.current_dt.strftime("%H:%M:%S")

  
    #  trade_list
    # [{'entrust_no': '9538', 'business_time': '2025-10-28 10:31:01', 'stock_code': '002193.SZ', 'entrust_bs': '1', 'business_amount': 3000, 'business_price': 5.49, 
    # 'business_balance': 16470.0, 'business_id': '1010000432942590', 'status': '8', 'cancel_info': ' ', 'withdraw_no': '0', 'real_type': '0', 'real_status': '0', 
    # 'order_id': 'c78bcb3375c344c3937df76358b6892d'}]
    symbol = trade["stock_code"] 

    # 注意： 已成与部成的消息可能乱序。
    if trade["entrust_bs"] == '1' and trade["status"] == '8':

        if current_time < "15:10:00":
            # print("SSSSSSS", sub_order, trade)
            # 买入已成
            log.info("买入已成: symbol={stock_code}, name={stock_name}, 下单数价={order_amount}, {order_price}元, 成交数={business_amount}, 成交价={business_price}".format(
                stock_code=trade['stock_code'],
                stock_name=sub_get_stock_name(symbol),
                order_amount=sub_order.order_amount,
                order_price=sub_order.order_price,
                business_amount=trade['business_amount'],
                business_price=trade['business_price']
            ))
            position.amount =  position.amount + trade["business_amount"]      # 成交数量 倒底是哪个字段？
            sub_order.business_amount = sub_order.business_amount + trade["business_amount"]   # 本次买入累计成交数量
            sub_order.business_balance = sub_order.business_balance + trade["business_balance"]   # 本次买入累计成交金额
            sub_order.business_price = trade["business_price"]                 # 本次买入累计成交价
            
            # 已全部成交，可以进行结算了。
            if sub_order.business_amount >= sub_order.order_amount:
                inner_after_trading_settlement(position, sub_order, context)

        else:
            # 买入已成盘后结算
            inner_after_trading_settlement(position, sub_order, context)

        return
    elif trade["entrust_bs"] == '1' and trade["status"] == '7':
        # 部成 怎么处量： 盘中只打印信息， 盘后统一计算佣金。 
        # position["amount"] = position["amount"] + order.filled
        
        # 收盘前的部成会有多条消息，  部成在收盘后统一处理。  
        if current_time < "15:10:00":
            position.amount =  position.amount + trade["business_amount"]      # 成交数量 倒底是哪个字段？

            sub_order.business_amount = sub_order.business_amount + trade["business_amount"]   # 本次买入累计成交数量
            sub_order.business_balance = sub_order.business_balance + trade["business_balance"]   # 本次买入累计成交金额, 
            sub_order.business_price = trade["business_price"]      # 本次部成价格, 

            # 全部成交， 
            if sub_order.business_amount >= sub_order.order_amount: 
                log.info("买入累计已成: symbol={stock_code}, name={stock_name}, 下单数={order_amount},  下单价={order_price}元, 累计成交数={total_business_amount}, 本次成交数={business_amount}, 本次成交价={business_price}".format(
                    stock_code=trade['stock_code'],
                    stock_name=sub_get_stock_name(symbol),
                    order_amount=sub_order.order_amount,
                    order_price=sub_order.order_price,
                    total_business_amount=sub_order.business_amount,
                    business_amount=trade['business_amount'],
                    business_price=trade['business_price']
                ))            
                inner_after_trading_settlement(position, sub_order, context)
            else:
                log.info("买入部成: symbol={stock_code}, name={stock_name}, 下单数={order_amount},  下单价={order_price}元, 累计成交数={total_business_amount}, 本次成交数={business_amount}, 本次成交价={business_price}".format(
                    stock_code=trade['stock_code'],
                    stock_name=sub_get_stock_name(symbol),
                    order_amount=sub_order.order_amount,
                    order_price=sub_order.order_price,
                    total_business_amount=sub_order.business_amount,
                    business_amount=trade['business_amount'],
                    business_price=trade['business_price']
                ))     
                       
        else:
            # 买入部成， 盘后结算。
            inner_after_trading_settlement(position, sub_order, context)
        
        return            
    # elif trade["entrust_bs"] == '1' and (trade["status"] == '9'):
    # # 废单， 价格笼子没过。  
        # pass
    #                                              订单状态: 废单                    状态：已撤,         5是部撤
    elif trade["entrust_bs"] == '1' and (trade["status"] == '9' or trade["status"] == '6' or trade["status"] == '5'):
# 2025-11-24 11:16:00 - INFO - 后端服务 操作账户股票代码：【002264.SZ】 委托号：【19487】 发起撤单
# 2025-11-24 11:16:00 - INFO - on_trade_response [{'entrust_no': '19487', 'business_time': '2025-11-24 11:16:00', 'stock_code': '002264.SZ', 'entrust_bs': '1', 'business_amount': -1100, 
# 'business_price': 8.92, 'business_balance': -9812.0, 'business_id': '1010000581572195', 'status': '6', 'cancel_info': ' ', 'withdraw_no': '19487', 'real_type': '2', 'real_status': '0', 
# 'order_id': '76c109e6fbbd428185050a0adcf6948a'}]        
        # 盘中交易通知： 买入 撤单， 删除持仓。
        # del my_positions[symbol]??
        if current_time < "15:10:00":
            log.warning("买单{}, Trade={}, sub_order = {}".format(get_order_status_name(trade['status']), trade, sub_order))
            
            sub_portfolio = inner_sub_get_strategy_portfolio(context)

            # 买入撤单， 恢复撤单的可用资金。 两种情况： 1、买入全部撤单，   2、 买入已经部成， 部分撤单。
            if trade["status"] == '6':
                used_money = sub_order.order_cash
                # 校验一下： 理论上，锁定金额需要大于等于撤单金额
                if abs(used_money) < abs(trade["business_balance"]):
                    log.warning("撤单金额小于锁定金额.  锁定={},  撤单={}".format(used_money, trade["business_balance"]))
            # 买入废单， 价格错误
            elif trade["status"] == '9':
                used_money = sub_order.order_cash
            else:
                #部撤的订单。
                used_money = abs(trade['business_balance'])
                
            sub_portfolio.cash = sub_portfolio.cash + used_money
            
            # 订单完成结算。
            sub_order.settlemented = True 
            # 价格超笼子的废单响应。
            # 获取重新下单金额， 使用本次下单的原始金额。
            order_money = used_money
            #取得全部撤单的资金。
            if sub_order.orig_order_money is not None and trade["status"] == '6':
                order_money = sub_order.orig_order_money
            elif sub_order.orig_order_money is not None and trade["status"] == '5':
                # 计算部分撤单的资金,  下单资金减去已成交金额。
                order_money = sub_order.orig_order_money -  sub_order.business_balance
                pass

            # 买单撤单成功, 重新下单。  如果是超时未成交的撤单，需要重新下单。
            if position.reorder_timeout is True and (trade["status"] == '6'  or trade["status"] == '5'):  
                log.info("超时未成交撤单，重新下单.  标的={}, {};  金额 = {}".format(symbol, sub_get_stock_name(symbol), order_money))
                # 实盘由于总仓的资金数据更新有延迟几秒， 撤单资金还没有到账。 需要等待一会再下单。  实盘测试延迟： 5秒，4秒，6秒，5秒，
                time.sleep(10) 
                position.reorder_timeout = False
                sub_order_target_value(symbol, order_money, context)
            elif trade["status"] == '9' and "无对手方" in trade["cancel_info"] and current_time >= "09:30:00":
# 七星v172的log: "order_market_five_dealed" - 按市价进行委托(五档即时成交),   产生的错误委托。                
# 2026-07-01 14:10:18 - WARNING - 买单废单, Trade={'entrust_no': '131', 'business_time': '2026-07-01 14:10:18', 'stock_code': '510500.SS', 'entrust_bs': '1', 
# 'business_amount': 11000, 'business_price': 0.0, 'business_balance': 0.0, 'business_id': '0', 'status': '9', 
# 'cancel_info': '最优五档即时成交余量转限价的市价订单无对手方和本方申报订单', 'withdraw_no': '0', 'entrust_reference': '330002730', 
# 'real_type': '0', 'real_status': '2', 'order_id': 'f2048c8a9ad1466dafbfd56bbc5a0a4e', 'amount': 11000}, sub_order = subOrder: dt: 2026-07-01 14:10:18, 
# symbol: 510500.SS, name: 500ETF  ,order_amount: 11000, order_price: 9.187, order_cash: 101057.0, business_amount:0, business_balance:0, settlemented:False,
# tax_commission:None, entrust_no:None; 
                log.info("无对手单造成的废单，重新下单.  标的={}, {};  金额 = {}".format(symbol, sub_get_stock_name(symbol), order_money))
                # 实盘由于总仓的资金数据更新有延迟几秒， 撤单资金还没有到账。 需要等待一会再下单。  实盘测试延迟： 5秒，4秒，6秒，5秒，
                # time.sleep(10) 
                # position.reorder_timeout = False
                # sub_order_target_value(symbol, order_money, context)
                pass
            else:
                log.warning("错误委托, 标的={}, {};  金额 = {}".format(symbol, sub_get_stock_name(symbol), order_money))
                pass
        else:
            log.warning("错误状态订单11, 买单{}, Trade={}, sub_order = {}, position = {}".format(get_order_status_name(trade['status']), trade, sub_order, position))

            #如果订单没有完成结算,  并且订单是废单， 需要恢复买入金额。
            if sub_order.settlemented is False and trade["status"] == '9':
                used_money = sub_order.order_cash
                sub_portfolio = inner_sub_get_strategy_portfolio(context)
                used_money = sub_order.order_cash
                sub_portfolio.cash = sub_portfolio.cash + used_money
                sub_order.settlemented = True
            pass
        return
    elif trade["entrust_bs"] == '1' and (trade["status"] == '2'):
        # 买入已报， 还未成交
        
        # 买单收盘后仍未成交
        if current_time > "15:01:00":
            log.warning("买单收盘后仍未成交{}".format(trade))
            
            used_money = sub_order.order_cash  
            sub_portfolio = inner_sub_get_strategy_portfolio(context)
            # 没有买入成功， 恢复可用资金。
            sub_portfolio.cash = sub_portfolio.cash + used_money 
            # 订单完成结算。
            sub_order.settlemented = True 
        else:
            log.warning("错误状态订单22, 买单{}, Trade={}, sub_order = {}".format(get_order_status_name(trade['status']), trade, sub_order))
            pass

        return
    # 卖单 可能多条已成， 部成消息， 还可能乱序。
    elif trade["entrust_bs"] == '2' and trade["status"] == '8':
        # 卖出已成, 删除持仓

        # 收盘前的部成会有多条消息，  部成在收盘后统一处理。  
        if current_time < "15:05:00":
        
            position.amount =  position.amount - abs(trade["business_amount"]) 

            # 成交数量累计
            sub_order.business_amount = sub_order.business_amount - abs(trade["business_amount"])
            sub_order.business_balance = sub_order.business_balance - abs(trade["business_balance"])

            # 盘后结算只减去佣金， 盘中增加可用资金
            used_money = abs(trade["business_balance"]) 
            sub_portfolio = inner_sub_get_strategy_portfolio(context)
            sub_portfolio.cash = sub_portfolio.cash + used_money

            log.info("盘中卖出已成, symbol={symbol}, name={stock_name}, 下单数={order_amount}, 成交数={business_amount},  成交价={business_price}, 成交金额={business_balance}, 可用金额={av_cash};".format(
                symbol=symbol,
                stock_name=sub_get_stock_name(symbol),
                order_amount=sub_order.order_amount,
                business_amount=trade['business_amount'],
                business_price=trade['business_price'],
                business_balance=trade['business_balance'],
                av_cash=sub_portfolio.cash,
            ))

            # 检查买卖队列有没有等待买入的标的。
            # 异常场景：如果是  多个部成消息 + 一个已成消息。 并且是消息乱序了？
            if abs(sub_order.order_amount) == abs(sub_order.business_amount):
                # 卖出已成，检查是否有标的正在等待买入
                inner_after_trading_settlement(position, sub_order, context)
                inner_callback_sell_dealed(symbol, context)
            else:
                log.warning("卖出已成但成交数量不足, 可能多个部成消息乱序了。symbol={symbol}, name={stock_name}, 未成交数={no_deal_amount}, 成交数={business_amount}".format(
                    symbol=symbol,
                    stock_name=sub_get_stock_name(symbol),
                    no_deal_amount=position.amount,
                    business_amount=trade['business_amount'],
                ))
        else:
            #  卖出已成,  盘后结算
            inner_after_trading_settlement(position, sub_order, context)
            
        return
    elif trade["entrust_bs"] == '2' and trade["status"] == '7':
        # 卖出部成， 部成的成交通知在收盘后统一计算。 如查部成全部成交呢？
        # print(f"卖出部成{trade}")
        # log.info(f"卖出部成, {symbol}, 下单数={trade['amount']}, 成交数{trade['business_price']}")

        # 收盘前的部成会有多条消息，  部成在收盘后统一处理。  
        if current_time < "15:10:00":
            position.amount = position.amount - abs(trade["business_amount"])

            # 成交数量累计,  成交金额累计, 
            sub_order.business_amount = sub_order.business_amount - abs(trade["business_amount"])
            sub_order.business_balance = sub_order.business_balance - abs(trade["business_balance"])

            
            # 盘后结算只减去佣金， 盘中增加可用资金
            # used_money = abs(trade["business_amount"] * trade["business_price"]) 
            used_money = abs(trade["business_balance"])
            sub_portfolio = inner_sub_get_strategy_portfolio(context)
            sub_portfolio.cash = sub_portfolio.cash + used_money
            
            # 卖出累计已全部成交， 就需要恢复 可用资金。 否则可用资金留到盘后再统一恢复。
            if abs(sub_order.business_amount) >= abs(sub_order.order_amount):

                log.info("卖出累计已成, symbol={symbol}, name={stock_name}, 下单数={order_amount}, 累计成交数={total_order_amount}, 本次成交数={business_amount}, 本次成交价={business_price}, 本次成交金额={business_balance}, 可用金额={av_cash}; ".format(
                    symbol=symbol,
                    stock_name=sub_get_stock_name(symbol),
                    order_amount=sub_order.order_amount,
                    total_order_amount=sub_order.business_amount,
                    business_amount=trade['business_amount'],
                    business_price=trade['business_price'],
                    business_balance=trade['business_balance'],
                    av_cash=sub_portfolio.cash
                ))

                # 检查买卖队列有没有等待买入的标的
                inner_callback_sell_dealed(symbol, context)
                inner_after_trading_settlement(position, sub_order, context)
            else:
                log.info("卖出部成, symbol={symbol}, name={stock_name}, 下单数={order_amount}, 成交数={business_amount}, 成交价={business_price}, 成交金额={business_balance}".format(
                    symbol=symbol,
                    stock_name=sub_get_stock_name(symbol),
                    order_amount=sub_order.order_amount,
                    business_amount=trade['business_amount'],
                    business_price=trade['business_price'],
                    business_balance=trade['business_balance'],
                ))
            pass
        else:
            # 佣金如何计算, 对于部成通知， 盘后统计计算佣金。
            #  卖出部成,  盘后结算
            inner_after_trading_settlement(position, sub_order, context)

        return
    #                                              订单状态: 废单                    状态：已撤,         5是部撤
    elif trade["entrust_bs"] == '2' and (trade["status"] == '9' or trade["status"] == '6' or trade["status"] == '5'):
# WARNING - 卖单已撤, order={'entrust_no': '38', 'business_time': '2026-03-19 10:27:52', 'stock_code': '518880.SS', 'entrust_bs': '2', 'business_amount': 900, 
# 'business_price': 10.9, 'business_balance': 9810.0, 'business_id': '0000000050004261', 'status': '6', 'cancel_info': ' ', 'withdraw_no': '38', 
# 'real_type': '2', 'real_status': '0', 'order_id': '36732f0c2aca44709025444100f7cb76', 'amount': 900.0}
        # 盘中通知： 卖出 成废单， 或者 卖单已撤 恢复可用数量
        if current_time < "15:10:00":
            position.enable_amount = position.enable_amount + abs(trade["business_amount"])

            used_money = abs(trade["business_balance"])
            log.warning("卖单{}, trade={}, sub_order= {}".format(get_order_status_name(trade['status']), trade, sub_order))
            position.order_id = None             
            # 数据保护
            if position.enable_amount > position.amount:
                position.enable_amount = position.amount

            # 卖单撤单成功, 重新下单。  如果是超时未成交的撤单，需要重新下单。
            # 实盘由于总仓的资金数据更新有延迟几秒， 撤单资金, 或股份还没有到账。 需要等待一会再下单。  实盘测试延迟： 5秒，4秒，6秒，5秒，
            if position.reorder_timeout is True and (trade["status"] == '6' or trade["status"] == '5') and sub_order.orig_order_money == 0:  
                log.info("卖单超时未成交撤单，重新下单.  标的={}, {};  数量 = {}".format(symbol, sub_get_stock_name(symbol), position.enable_amount))
                time.sleep(10) 
                ##卖单撤单成功， 重新下单卖出。
                sub_order_target_value(symbol, 0, context)
                position.reorder_timeout = False
            ## 部分卖单撤单， 调整仓位到目标金额。
            elif position.reorder_timeout is True and trade["status"] == '5' and sub_order.orig_order_money > 0:  
                log.info("卖单超时部分未成交撤单，重新下单.  标的={}, {};  数量 = {}".format(symbol, sub_get_stock_name(symbol), position.enable_amount))
                time.sleep(10) 
                ##卖单撤单成功， 重新下单卖出。
                sub_order_target_value(symbol, sub_order.orig_order_money, context)
                position.reorder_timeout = False
            else:
                log.info("错误委托, 标的={}, {};  金额 = {}".format(symbol, sub_get_stock_name(symbol), used_money))
                pass

            # 废单在盘中没见回调。
        else:
            # 废单在盘中没见回调。
            log.warning("卖单{},trade = {},  order={}".format(get_order_status_name(trade['status']), trade, sub_order))
            position.enable_amount = position.amount # 卖单已撤，恢复持仓。
            pass

    elif trade["entrust_bs"] == '2' and (trade["status"] == '2'):
        # 卖单收盘后仍为成交
        if current_time > "15:10:00":
            position.enable_amount = position.enable_amount + abs(trade["amount"])
            log.warning("卖单收盘仍未成交{}".format(trade))

            # 数据保护
            if position.enable_amount > position.amount:
                log.warning("持仓可用数量 大于持仓数. position = {}".format(position))
                position.enable_amount = position.amount

        return
    else:
# 2025-11-18 14:50:00 - INFO - 生成订单，订单号：5dbebfe6661d4b9e9866932da71b3548 股票代码：513520.XSHG 数量：卖出51200
# 2025-11-18 14:50:30 - WARNING - 异常下单响应 = {'entrust_no': '11556', 'business_time': '2025-11-18 14:50:30', 'stock_code': '513520.SS', 'entrust_bs': '2', 'business_amount': -31400, 
# 'business_price': 1.796, 'business_balance': -56394.4, 'business_id': '50026834', 'status': '7', 'cancel_info': ' ', 'withdraw_no': '0', 'real_type': '0', 'real_status': '0', 'order_id': '5dbebfe6661d4b9e9866932da71b3548', 'amount': 0}
# 2025-11-18 14:50:30 - WARNING - 异常下单响应 = {'entrust_no': '11556', 'business_time': '2025-11-18 14:50:30', 'stock_code': '513520.SS', 'entrust_bs': '2', 'business_amount': -19800, 
# 'business_price': 1.795, 'business_balance': -35541.0, 'business_id': '50026835', 'status': '8', 'cancel_info': ' ', 'withdraw_no': '0', 'real_type': '0', 'real_status': '0', 'order_id': '5dbebfe6661d4b9e9866932da71b3548', 'amount': 0}
# 2025-11-18 15:30:00 - INFO - 卖出已成, symbol=513520.SS, name=日经ETF , 下单数=-51200, 成交数=0, 成交价=0, 手续费=5.0
        log.warning("异常下单响应. Trade = {}, position={}, order={}".format(trade, position, sub_order))
            
    return 

def sub_use_orig_portfolio_data():
    """_summary_
    封装 交易， 回测检测函数。  用于 判断 交易， 回测使用是否使用原始仓位数据 ,     
    回测时使用分仓数据， 看不到回测曲线， 需要看每日收盘打印。
    Returns:
        _type_: _description_ True : 使用原始仓位数据， False:  使用自定义的分仓数据
    """
    use_orig_portfolio_data = True
    use_orig_portfolio_data = g.use_orig_portfolio_data
    
    if use_orig_portfolio_data is True:
        return True

    return False



def on_trade_response (context, trade_list):
    """_summary_
    1. 该函数会在成交主推回调时响应，比引擎和get_trades()函数更新Order状态的速度更快，适合对速度要求比较高的策略。
    2. 撤单成功也在这个函数中回调。
    
    这个函数好像在order 函数返回前进行回调的。
    Args:
        context (_type_): _description_
        trade_list：一个列表，当前成交单发生变化时，发生变化的成交单列表。成交单以字典形式展现，内容包括：'entrust_no'(委托编号), 'business_time'(成交时间), 
        'stock_code'(股票代码), 'entrust_bs'(成交方向), 'business_amount'(成交数量), 'business_price'(成交价格), 'business_balance'(成交额), 
        'business_id'(成交编号), 'status'(委托状态), 'order_id'(Order订单编号)；
    """

    # 回测场景
    if sub_use_orig_portfolio_data():
        return
   
    # print("TTTTTTTTTTTT", trade_list)
    # trade_list =  [{'entrust_no': '9538', 'business_time': '2025-10-28 10:31:01', 'stock_code': '002193.SZ', 'entrust_bs': '1', 'business_amount': 3000, 'business_price': 5.49, 
    # 'business_balance': 16470.0, 'business_id': '1010000432942590', 'status': '8', 'cancel_info': ' ', 'withdraw_no': '0', 'real_type': '0', 'real_status': '0', 
    # 'order_id': 'c78bcb3375c344c3937df76358b6892d'}]

    ## 回测时的 回调数据
    # 2025-09-02 10:30:00 - INFO - TTTTTTTTTTTT <Trade {'datetime': datetime.datetime(2025, 9, 2, 10, 30), 'trading_datetime': datetime.datetime(2025, 9, 2, 10, 30), 
    # 'order_id': '5feb864f053f458a99176292b4d33fae', 'price': 10.361554, 'amount': 1500, 'commission': 5.7569115197, 'tax': 0, 'transaction_cost': 5.7569115197, 'entrust_direction': 'BUY', 
    # 'asset': <StockAsset {'symbol': '002856.XSHE', 'name': '美芝股份', 'exchange': 'XSHE', 'type': 'STOCK', 'listed_date': datetime.datetime(2017, 3, 20, 0, 0), 'trade_unit': 100, 
    # 'trading_time': '09:30-11:30, 13:00-15:00', 'delisted_date': datetime.datetime(2900, 1, 1, 0, 0), 'precision': 2}>, 'futures_direction': 'OPEN', 'id': '7ac253ac1d5c45a88330cea55adbc3ac', 
    # 'symbol': '002856.XSHE', 'entrust_no': None, 'hedge_type': 'SPECULATION', 'status': None}>
    
    
    if not is_trade():
        # 回测场景 的参数格式是Class,  实盘场景的参数格式是Dict,  需要进行格式转换。
        trade_obj = trade_list
        business_time = trade_obj.trading_datetime.strftime("%Y-%m-%d %H:%M")
        symbol = trade_obj.symbol
        if symbol.endswith('.XSHE') or symbol.endswith('.SZ'):
            symbol = symbol.split(".")[0] + ".SZ"
        elif symbol.endswith('.XSHG') or symbol.endswith('.SS'):
            symbol = symbol.split(".")[0] + ".SS"
        else:
            log.error("Error code = {}, trade = {}".format(symbol, trade_obj))
            return
        
        entrust_bs = '1'
        # log.info("DDDDDDDDDDdirection={}".format(trade_obj.entrust_direction))
        if trade_obj.entrust_direction == EntrustDirection.BUY:
            entrust_bs = '1'
        elif trade_obj.entrust_direction == EntrustDirection.SELL:
            entrust_bs = '2'
        else:
            #2025-09-02 10:30:00 - ERROR - Error direction=EntrustDirection.BUY
            log.error("Error direction={}".format(trade_obj.entrust_direction))
            return

# 2025-09-02 10:30:00 - INFO - DDDDDDDDDDDD {'_trade_id': 'b165a4a79e46439abf161615fa520e78', '_order_id': 'f9efb19379a044bfbe772c75e80beb25', '_calendar_dt': datetime.datetime(2025, 9, 2, 10, 30), 
# '_trading_dt': datetime.datetime(2025, 9, 2, 10, 30), '_price': 10.361554, '_amount': 1500, '_commission': 5.7569115197, '_tax': 0, '_close_today_amount': 0, '_entrust_direction': 'BUY', 
# '_futures_direction': 'OPEN', '_asset': <StockAsset {'symbol': '002856.XSHE', 'name': '美芝股份', 'exchange': 'XSHE', 'type': 'STOCK', 'listed_date': datetime.datetime(2017, 3, 20, 0, 0), 
# 'trade_unit': 100, 'trading_time': '09:30-11:30, 13:00-15:00', 'delisted_date': datetime.datetime(2900, 1, 1, 0, 0), 'precision': 2}>, '_frozen_price': 10.36, '_hedge_type': 'SPECULATION', 
# '_status': None}
# 2025-09-02 10:30:00 - INFO - 222222222222 ['__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__getstate__', 
# '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', 
# '__str__', '__subclasshook__', '__weakref__', '_amount', '_asset', '_calendar_dt', '_close_today_amount', '_commission', '_entrust_direction', '_frozen_price', '_futures_direction', 
# '_hedge_type', '_make_id', '_order_id', '_price', '_repr_attr_list', '_status', '_tax', '_trade_id', '_trading_dt', 'amount', 'asset', 'close_today_amount', 'commission', 'create_trade', 
# 'datetime', 'entrust_direction', 'frozen_price', 'futures_direction', 'hedge_type', 'id', 'order_id', 'price', 'status', 'symbol', 'tax', 'trading_datetime', 'transaction_cost']
# 2025-09-02 10:30:00 - INFO - TTTTTTTTTTTT <Trade {'datetime': datetime.datetime(2025, 9, 2, 10, 30), 'trading_datetime': datetime.datetime(2025, 9, 2, 10, 30), 
# 'order_id': 'f9efb19379a044bfbe772c75e80beb25', 'price': 10.361554, 'amount': 1500, 'commission': 5.7569115197, 'tax': 0, 'transaction_cost': 5.7569115197, 
# 'entrust_direction': 'BUY', 'asset': <StockAsset {'symbol': '002856.XSHE', 'name': '美芝股份', 'exchange': 'XSHE', 'type': 'STOCK', 'listed_date': datetime.datetime(2017, 3, 20, 0, 0), 
# 'trade_unit': 100, 'trading_time': '09:30-11:30, 13:00-15:00', 'delisted_date': datetime.datetime(2900, 1, 1, 0, 0), 'precision': 2}>, 'futures_direction': 'OPEN', 
# 'id': 'b165a4a79e46439abf161615fa520e78', 'symbol': '002856.XSHE', 'entrust_no': None, 'hedge_type': 'SPECULATION', 'status': None}>
# 2025-09-02 10:30:00 - INFO - DDDDDDDDDDdirection=EntrustDirection.BUY
        #trade_obj.entrust_no
        business_balance = trade_obj.amount * trade_obj.price
        new_trade_list = [{'entrust_no': None, 'business_time': business_time, 'stock_code': symbol, 'entrust_bs': entrust_bs, 'business_amount': trade_obj.amount, 
                        'business_price': trade_obj.price, 'business_balance': business_balance, 'business_id': '1010000432942590', 'status': '8', 'cancel_info': ' ', 'withdraw_no': '0',  'real_type': '0', 
                        'real_status': '0',  'order_id': "bt_order_id", 'bt_real_order_id': trade_obj.order_id}] # trade_obj.order_id,  trade_obj.order_id , 
    else:
        new_trade_list = trade_list
        
    sub_positions = sub_get_strategy_positions(context)

    for trade in new_trade_list:
        # print("BBBBBBBBBBBBBB", trade)
        symbol = trade["stock_code"]
        
        # 股票不在本策略持仓
        if symbol not in sub_positions:
            log.warning("股票不在本策略持仓,  symbol = {}, position={}".format(symbol, sub_positions))
            continue
        
        position = sub_positions[symbol]

        # 在Order函数返回前进行回调的。 此时还没有取得order_id
        order_id = None  
        bt_real_order_id = None  # 回测模式的order 返回的真实id
        #实盘模式
        if is_trade():
            order_id = trade["order_id"]
        # 回测模式， 有时候on_trade_response 在order前回调， 有时候又在order后回调。
        else:
            bt_real_order_id = trade["bt_real_order_id"]
            
        sub_order = None
        # 实盘模式
        if is_trade() and order_id in position.order_dict:
           sub_order = position.order_dict[order_id]
        # 回测模式
        elif (not is_trade()) and "bt_order_id" in position.order_dict:
           sub_order = position.order_dict["bt_order_id"]
        elif (not is_trade()) and bt_real_order_id in position.order_dict:
           sub_order = position.order_dict[bt_real_order_id]
        else:
            log.error("错误消息: symbol = {}, position={}, trade={}, 原始Trade={}".format(symbol, position, trade, trade_list))
            return                     
                     
        #entrust_bs -- 成交方向(注意：str类型)，'1'-买，'2'-卖；
        if trade['entrust_bs'] == '1':
            trade['amount'] = sub_order.order_amount # 买入数量
        elif trade['entrust_bs'] == '2':
            trade['amount'] = 0 - sub_order.order_amount   # 卖出数量
        else:
            log.error("不匹配的消息类型, trade = {}".format(trade))
            return
        #  根据订单的成交情况， 更新策略的仓位数据。
        # print("AAAAAAAAAAAAAA", trade)
        inner_update_sub_position(trade, position, sub_order, context)

        # 订单响应先保存， 盘后结算还需要使用。
        sub_order.trade_response.append(trade)
   
    return

def sub_refresh_position_data(context):
    """_summary_
    ###### 刷新持仓收益，  市值等数据 
    # #校验分仓库资金 与 股票 与总仓的 资金 ， 持仓是否一致，  本策略可用资金必须小于总仓位资金， 
    # 本策略持仓股票数必须在总仓也存在， 股数必须小于总仓持股数

    Args:
        context (_type_): _description_
    """
    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')
    current_time = context.blotter.current_dt.strftime("%H:%M:%S")
    
    sub_positions = sub_get_strategy_positions(context)
    sub_holding_list = list(sub_positions.keys())

    # 总仓的实际持股
    # Fix PTrade BUG:  get_positions() 返回的股票代码以 XSHG, XSHE为后缀, context.portfolio.positions是以SS,SZ为后缀。
    # main_positions = get_positions() 
    main_positions = context.portfolio.positions
    main_holding_list = list(main_positions.keys())
    
    # 这里刷新分仓数据，  直接用全局变量， 否则死循环。
    sub_portfolio = g.__sub_portfolio 

    total_market_value = 0
    for symbol in sub_holding_list:
        
        position = sub_positions[symbol]
        ####校验持仓
        #  当天收盘后持股数为0
        # Fix BUG:  回测场景：当天Bar交易量不足， 订单撤消却没有回调通知。
        # if position.amount == 0 and current_date == position.sell_date: 
        #     # 2024-02-06 10:30:00 - WARNING - 订单撤销:  当前bar交易量不足  003033.XSHE  bar.volume 0.0
        #     # 2024-02-06 10:30:00 - INFO - 生成订单，订单号:c0dc52f6f1af4518b1cad6e3522cb851，股票代码：003033.XSHE，数量：买入700股
        #     log.error("数据错误: {}, {}持股数量为0".format(symbol, sub_get_stock_name(symbol)))
        #     continue                
        # Fix BUG:  检查股票是否已经卖出。 
        if position.amount == 0: 
            continue
        
        market_value = position.last_sale_price * position.amount 

        # 2、 分仓持股在总仓数据存在。 
        if symbol not in main_holding_list:
            log.error("分仓策略持股在总仓不存在，请检查计算分仓可用金额。 ={}: {}, 在总仓不存在={}, 分仓数据= {}".format(symbol, sub_get_stock_name(symbol), main_holding_list, sub_positions[symbol]))
            # 2025-02-20 15:30:00 - ERROR - 分仓持股=003011.SZ, 在总仓不存在=['002058.SZ', '002188.SZ', '002207.SZ', '002719.SZ', '002789.SZ', '002910.SZ']
            # 2025-02-20 15:30:00 - WARNING - Order Rejected: 003011.XSHE can not match. Market close.
            # FIX BUG: TO DO: 订单买单没有成交， 或者是废单， 总仓就会没有数据， 这时需要, 删除分仓数据, 恢复分仓可用资金
            # 计算这支票的占用资金
            log.error("分仓策略持股 {}: {}, 恢复占用资金 = {}, 持仓={}".format(symbol, sub_get_stock_name(symbol), market_value, position.amount))
            sub_portfolio.cash = sub_portfolio.cash  + market_value
            inner_del_strategy_positions(symbol)
            continue
        
        if position.amount > 0 and main_positions[symbol].amount == 0:
            log.error("分仓策略持股与总仓不一致, 请检查计算分仓可用金额。 分仓标的={}:{}, 总仓已卖出={}, 分仓数据= {}".format(symbol, sub_get_stock_name(symbol), main_holding_list, sub_positions[symbol]))
            # 2025-02-20 15:30:00 - ERROR - 分仓持股=003011.SZ, 在总仓不存在=['002058.SZ', '002188.SZ', '002207.SZ', '002719.SZ', '002789.SZ', '002910.SZ']
            # 2025-02-20 15:30:00 - WARNING - Order Rejected: 003011.XSHE can not match. Market close.
            # FIX BUG: TO DO: 订单买单没有成交， 或者是废单， 总仓就会没有数据， 这时需要, 删除分仓数据, 恢复分仓可用资金
            # current_order = get_order(sub_positions[symbol].order_id)
            # print("current_order", current_order)
            # 计算这支票的占用资金
            log.error("分仓策略持股 {}: {}, 恢复占用资金 =  {}, 持仓={}".format(symbol, sub_get_stock_name(symbol), market_value, position.amount))
            sub_portfolio.cash = sub_portfolio.cash + market_value
            inner_del_strategy_positions(symbol)
            continue

        #3、 分仓 持股数必须小于等于 总仓 持仓数 . 如何不同策略买入的票怎么算？
        if position.amount != main_positions[symbol].amount:
            log.warning("{symbol}, {name}分仓持股数量不等总仓持股数量不一致,  请检查多策略是否购买同一股票。 分仓持股数{sub_amount}, 总仓持股数{main_amount}".format(
                symbol=symbol,
                name=sub_get_stock_name(symbol),
                sub_amount=position.amount,
                main_amount=main_positions[symbol].amount
            ))

        market_value = position.last_sale_price * position.amount 
        total_market_value = total_market_value + market_value
            
            
    # 这里刷新分仓数据，  直接用全局变量， 否则死循环。
    sub_portfolio = g.__sub_portfolio 
    
    # 策略可用资金必须小于  总仓可用资金
    if custom_round(sub_portfolio.cash, 2)  > custom_round(context.portfolio.cash, 2) :
        log.warning("分仓可用资金: {}元 > 总仓资金: {}".format(sub_portfolio.cash, context.portfolio.cash))
        sub_portfolio.cash = context.portfolio.cash

    sub_portfolio.positions_value = total_market_value       #   持仓价值
    sub_portfolio.portfolio_value = total_market_value  + sub_portfolio.cash     #   当前持有的标的和现金的总价值
    #当前的收益比例, 相对于初始资金
    sub_portfolio.returns = round((sub_portfolio.portfolio_value - sub_portfolio.init_cash)*100/sub_portfolio.init_cash, 2)

    return

def after_trading_end(context, data):
    """_summary_
    该函数会在每天交易结束之后调用， 扣除税费， 校验并同步订单与资金状态。
    收益率统一采用 %格式， 打印出来%省略了， 并保留2位小数。 

    Args:
        context (_type_): _description_
        strategy_name (_type_): _description_
        g (_type_): _description_
    """
    # 使用原始仓位数据， 直接返回。
    if sub_use_orig_portfolio_data():
        return

    current_date = context.blotter.current_dt.strftime('%Y-%m-%d')

    # 结算要用原始数据。
    sub_portfolio = inner_sub_get_strategy_portfolio(context) 
    sub_positions = sub_portfolio.positions

    holding_list = list(sub_positions.keys())

    # 将每日交易操作 转换成DF保存到本地
    sub_order_columns = list(subOrder().__dict__.keys())
    today_order_df = pd.DataFrame(columns=sub_order_columns)

    for symbol in holding_list:
        
        position = sub_positions[symbol]
        order_id_list = list(position.order_dict.keys()) 
        
        if len(order_id_list) == 0:
            continue
        
        # 遍历每个订单， 完成盘后结算。
        for order_id in order_id_list:
            
            sub_order = position.order_dict[order_id]

            #回测场景
            if order_id == "bt_order_id":
                continue
            else:
                #实盘场景
                order_list = get_order(order_id)
    # 买入订单号=59629bf875f240b6b2fa5d3963eb7d72, result=[<Order {'id': '59629bf875f240b6b2fa5d3963eb7d72', 'dt': datetime.datetime(2025, 2, 6, 10, 30), 'priceGear': 0, 'limit': None, 
    # 'symbol': '002848.XSHE', 'amount': 2700, 'created': datetime.datetime(2025, 2, 6, 10, 30), 'filled': 2700, 'status': '8', 'entrust_no': None, 'cancel_entrust_no': None}>],  2700, None
    # 卖出订单号=8315600670cf4517a319a3440f599a9b, result=[<Order {'id': '8315600670cf4517a319a3440f599a9b', 'dt': datetime.datetime(2025, 2, 18, 14, 20), 'priceGear': 0, 'limit': None, 
    # 'symbol': '002848.XSHE', 'amount': -2700.0, 'created': datetime.datetime(2025, 2, 18, 14, 20), 'filled': -2700.0, 'status': '8', 'entrust_no': None, 'cancel_entrust_no': None}>],  -2700.0, None

                if order_list is None or len(order_list) == 0:
                    log.error("获取订单错误{},  订单号={}, order_list={}, position={}".format(symbol, order_id, order_list, position))
                    if position.amount == 0:
                        inner_del_strategy_positions(symbol)
                    continue

                var_order = order_list[0]

            # '6' -- "已撤", 已经撤消，没有成交的订单不处理。
            if var_order.status == '6':
                log.warning("订单已撤={}, 订单号={}, sub_order = {}".format(symbol, order_id, sub_order))
                continue
            
            entrust_bs = "1"  #entrust_bs -- 成交方向(str)，1-买，2-卖；
            entrust_bs_text = "买入"
            if var_order.amount > 0:
                entrust_bs = "1"
            else: 
                entrust_bs = "2"
                entrust_bs_text = "卖出"
                sub_order.order_price = var_order.limit
            # log.error("获取订单{},  订单号={}, result={},  {}, {}".format(symbol, order_id, order_list, var_order.amount, var_order.limit))
            # 统一处理： 构建盘后成交消息。
            trade_dict = {'entrust_bs': entrust_bs, 'business_amount': sub_order.business_amount, 'business_balance': sub_order.business_balance, 'business_price': var_order.limit, 'order_id': order_id, 
                        'order_time': var_order.dt, 'entrust_prop': '0', 'status': var_order.status, 'price': var_order.limit, 'entrust_no': var_order.entrust_no, 
                        'error_info': None, 'amount': var_order.amount, 'stock_code': symbol, 'entrust_type': '0'}
            # 每天收盘后， 根据订单的成交情况， 更新策略的仓位数据。
            inner_update_sub_position(trade_dict, position, sub_order, context)

            # 可能出现BUG, 校验一下。  
            if position.enable_amount == 0 and position.amount > 0:
                log.warning("XXX订单处理出错 pt_order={}, sub_order={}, trade={}".format(var_order, sub_order, trade_dict))  #涨停卖出没成交时有BUG？
        
            # 计算卖出的利润率 与 利润总钱数
            profit_rate = None
            profit_money = None
            if entrust_bs == "2" and sub_order.business_price > 0:
                profit_rate = custom_round((sub_order.business_price - position.cost_basis)*100/position.cost_basis, 2)  
                profit_money = custom_round((sub_order.business_price - position.cost_basis)*abs(sub_order.business_amount), 2)  

            # 盘后结算， 记录今日操作到excel表格
            sub_order_dict = {
                "订单号": order_id,
                "时间": sub_order.dt,
                "方向": entrust_bs_text,
                '代码': sub_order.symbol, 
                '名称': sub_get_stock_name(sub_order.symbol),  
                '下单数量': sub_order.order_amount,
                '下单价格': sub_order.order_price,
                '买入锁定金额': sub_order.order_cash,
                '成本价': custom_round(position.cost_basis, 3),
                '成交均价': custom_round(sub_order.business_price, 2),
                '成交总数': sub_order.business_amount,
                '成交金额': sub_order.business_balance,
                '卖出利润': profit_money,
                '利润率': profit_rate,
                '是否结算': sub_order.settlemented,
                '手续费': sub_order.tax_commission,
                '委托编号': sub_order.entrust_no                
            }
            
            if len(today_order_df) > 0:
                new_row = pd.DataFrame([sub_order_dict])  # 转成DataFrame
                today_order_df = pd.concat([today_order_df, new_row], ignore_index=True)
            else:
                today_order_df = pd.DataFrame([sub_order_dict])  # 转成DataFrame
            
        # 清除 订单 信息
        position.order_dict = {}
        position.reorder_timeout = False

        # 持仓数量为0, 标的可能已卖出，或者买入失败,  则删除持仓对象。
        if position.amount == 0:
            inner_del_strategy_positions(symbol)
            continue

    # 增加分红除权的收益
    inner_calculate_exrights(context)

    # 刷新与校验分仓持股数据
    sub_refresh_position_data(context)


    # 实盘打印 持仓 数据， 并对交易记录持久化
    if is_trade():
        sub_portfolio = inner_sub_get_strategy_portfolio(context)
        sub_positions = sub_get_strategy_positions(context)

        # 方法1：先创建空DataFrame，然后使用append()
        # 创建空DataFrame并指定列名
        today_stock_df = pd.DataFrame(columns=['日期', '代码', '名称', '可用数', '总数', '最新价', '成本价', '市值', '利润', '利润率%', '买入日期', '持仓天'])

        holding_list = list(sub_positions.keys())

        for symbol in holding_list:
            position = sub_positions[symbol]
            
            # 持仓数量为0, 标的可能已卖出，或者买入失败,  则删除持仓对象。
            if position.amount == 0 :
                inner_del_strategy_positions(symbol)
                continue
            
            rate = custom_round((position.last_sale_price - position.cost_basis)/position.cost_basis, 4)
            # 逐条追加数据
            stock_dict = {
                    '日期': current_date,
                    '代码': symbol, 
                    '名称': sub_get_stock_name(symbol),  
                    '可用数': position.enable_amount, 
                    '总数': position.amount, 
                    '最新价': custom_round(position.last_sale_price, 3), 
                    '成本价': custom_round(position.cost_basis, 3), 
                    '市值':  custom_round(position.last_sale_price * position.amount, 2),
                    '利润': custom_round(position.cost_basis*position.amount*rate, 2),
                    '利润率%': rate*100,
                    '买入日期': position.buy_date,
                    '持仓天': len(get_trade_days(start_date=position.buy_date, end_date=current_date)),
                    }
            if len(today_stock_df) > 0:
                new_row = pd.DataFrame([stock_dict])  # 转成DataFrame
                today_stock_df = pd.concat([today_stock_df, new_row], ignore_index=True)
            else:
                today_stock_df = pd.DataFrame([stock_dict])  # 转成DataFrame

        # 计算当天本策略的收益
        today_benefit = sub_portfolio.portfolio_value - sub_portfolio.pre_portfolio_value
        today_rate = custom_round(today_benefit*100/sub_portfolio.pre_portfolio_value, 2) 
        sub_portfolio.pre_portfolio_value = sub_portfolio.portfolio_value

        # 记录最近最高市值，便于计算最近的最大回撤。
        # 1、 收益创新高， 或者第一次记录 最近最高市值。
        if sub_portfolio.pre_max_value is None or sub_portfolio.pre_max_value <= sub_portfolio.portfolio_value:
            sub_portfolio.pre_max_value = sub_portfolio.portfolio_value
            sub_portfolio.pre_max_value_date = current_date
            sub_portfolio.drawdown_rate = 0
        
        # 当天发生回撤， 记算回撤百分比。
        elif sub_portfolio.pre_max_value > sub_portfolio.portfolio_value:
            sub_portfolio.drawdown_rate = (sub_portfolio.portfolio_value - sub_portfolio.pre_max_value)/sub_portfolio.pre_max_value*100
            sub_portfolio.drawdown_rate = custom_round(sub_portfolio.drawdown_rate, 2)
            
        # 2. 配置显示参数（关键）
        # 解决中文 打印对齐问题
        pd.set_option('display.unicode.ambiguous_as_wide', True)
        pd.set_option('display.unicode.east_asian_width', True)
        # # 防止列名折叠
        pd.set_option('display.expand_frame_repr', False)
        # 显示所有列
        pd.set_option('display.width', None)                      # 自动适配终端宽度
        pd.set_option('display.max_columns', None)                # 显示所有列
        pd.set_option('display.max_colwidth', None)               # 显示列内容完整宽度

        if len(today_order_df) > 0:
            inner_append_portfolio_to_excel(today_order_df, sheet_name = '每日操作')
            log.info("每日操作：\n {}".format(today_order_df))

        if len(today_stock_df) > 0:
            inner_append_portfolio_to_excel(today_stock_df, sheet_name = '每日持仓')
        log.info("每日持股：\n {}".format(today_stock_df))

        # 逐条追加数据
        daily_portfolio = {
                '日期': current_date, 
                '日收益': today_benefit,  
                '日收益率': today_rate,  
                '可用资金': sub_portfolio.cash, 
                '持仓市值': sub_portfolio.positions_value, 
                '总资金': sub_portfolio.portfolio_value, 
                '初始资金': sub_portfolio.init_cash, 
                '总收益率': sub_portfolio.returns, 
                '最高市值': sub_portfolio.pre_max_value, 
                '最高日期': sub_portfolio.pre_max_value_date, 
                '回撤比率': sub_portfolio.drawdown_rate, 
                }        
        # log.info("本策略收盘：日收益={today_benefit}元, 日收益率={today_rate:.2%}, 可用资金={available_cash}, 持仓市值={position_value}元, 总资金={total_value}元, 初始资金={init_cash}元, 总收益率={total_rate:.2%}".format(
        #     today_benefit=today_benefit,
        #     today_rate=today_rate,
        #     available_cash=sub_portfolio.cash,
        #     position_value=sub_portfolio.positions_value,
        #     total_value=sub_portfolio.portfolio_value,
        #     init_cash=sub_portfolio.init_cash, 
        #     total_rate=sub_portfolio.returns
        # ))

        daily_portfolio_df = pd.DataFrame([daily_portfolio])
        log.info("本策略每日收益:\n {}".format(daily_portfolio_df))

        # 策略资产追加到本地Excel， 便于复盘。     sheet_name = '策略资产'
        inner_append_portfolio_to_excel(daily_portfolio_df, sheet_name = '策略资产')
        # log.info("总仓数据, 总资金={}, 持仓市值={}, 可用资金={}, 收益率={}", context.portfolio.portfolio_value, context.portfolio.positions_value, context.portfolio.cash,  context.portfolio.returns)


        ########## 每天收盘后， 需要保存策略仓位数据。
        # 实盘场景， 为了保持数据一致性， 每天收盘后都对数据持久化
        save_strategy_persistent_data(context)
            
    # 清空买卖队列,  卖方队列
    sub_clear_buy_sell_queue(context)
        
    return
def inner_calculate_exrights(context):
    """_summary_
    除权分红时间顺序如下。 除权分红逻辑的函数最好在早盘开盘前调用。最好在9:00之前, 8点调用比较好。
    1、T 日（登记日）收盘 15:00 后。  交易所完成当日交易清算，统计完整股东名册、确定本次分红送转参数。
    2、T 日晚间 20:00–24:00 沪深清算时段： 中登、交易所生成正式除权权息记录、复权因子，同步给数据服务商、券商总部
    3、 T+1 日（除权除息日）开盘前 08:00 前 交易所行情系统载入除权价，行情快照、实时 K 线自动应用除权调整，盘中行情自带除权逻辑。
    
    计算除权， 分红,  配送股等数据。 如： 长江电力在 20250124 日： 每10股派现金2.100元。
2025-01-23 15:30:00 - INFO - 每日收盘资金：日收益=38.0元, 日收益率=0.04%, 可用资金=73054.69, 持仓市值=31668.0元, 总资金=104722.69元, 初始资金=100000元, 总收益率=4.72%
2025-01-23 15:30:00 - INFO - 总仓数据, 总资金=106086.69206878523, 持仓市值=33032.0, 可用资金=73054.69206878523, 收益率=0.060866920687852266
2025-01-24 15:30:00 - INFO - XFFFFFFfff 600900.SS           
date       allotted_ps  bonus_ps  exer_backward_a  exer_backward_b   exer_forward_a  exer_forward_b  rationed_ps  rationed_px                                                           
20250124          0.0      0.21           1.7508           16.325         1.0          -0.943          0.0          0.0  
2025-01-24 15:30:00 - INFO - XXXX 44
2025-01-24 15:30:00 - INFO - 账户现金分红（税前）：126.00 元,  税后：113.40 元  ,  PT 在回测时都按20%交税。
2025-01-24 15:30:00 - INFO - 每日收盘持股：
            代码         名称         可用数        总数          最新价        成本价        市值         利润         利润率%      买入日期        持仓天       
1           600900.SS  长江电力       600        600        27.47      27.25      16482.0    132.44     0.81       2024-12-11  32       
2025-01-24 15:30:00 - INFO - 每日收盘资金：日收益=118.0元, 日收益率=0.11%, 可用资金=73168.09, 持仓市值=31786.0元, 总资金=104840.69元, 初始资金=100000元, 总收益率=4.84%
2025-01-24 15:30:00 - INFO - 总仓数据, 总资金=106179.49206878523, 持仓市值=33024.0, 可用资金=73155.49206878523, 收益率=0.061794920687852306    

stock_exrights = get_stock_exrights('515980.SS', date='20250930'): 1拆2股。 
date        allotted_ps  rationed_ps  rationed_px  bonus_ps  exer_forward_a  exer_forward_b  exer_backward_a  exer_backward_b   
20250930          1.0          0.0          0.0       0.0             0.5    0.0              2.0              0.0  
    Args:
        context (_type_): _description_
    """

    #get_stock_exrights(stock_code, date=None)
    current_date = context.blotter.current_dt.strftime('%Y%m%d')
    current_date_line = context.blotter.current_dt.strftime('%Y-%m-%d')

    sub_portfolio = inner_sub_get_strategy_portfolio(context)
    sub_positions = sub_get_strategy_positions(context)

    holding_list = list(sub_positions.keys())

    for symbol in holding_list:
        position = sub_positions[symbol]
        
        # 持仓数量为0, 标的可能已卖出，或者买入失败,  则删除持仓对象。
        if position.amount == 0 :
            continue    

        # 当天刚买入的票不进行 除权除息操作。
        # if position.buy_date == current_date_line:
        #     continue

        fq_data = get_stock_exrights(symbol, date=current_date)

        # 当天没有分红，除权等数据。
        if fq_data is None:
            continue

        # 返回结果字段介绍：
        # date -- 日期(索引列，类型为int64)；
        # allotted_ps -- 每股送股(str:numpy.float64)；
        # rationed_ps -- 每股配股(str:numpy.float64)；
        # rationed_px -- 配股价(str:numpy.float64)；
        # bonus_ps -- 每股分红(str:numpy.float64)；
        # exer_forward_a -- 前复权除权因子A；用于计算前复权价格(前复权价格=A*价格+B)(str:numpy.float64)
        # exer_forward_b -- 前复权除权因子B；用于计算前复权价格(前复权价格=A*价格+B)(str:numpy.float64)
        # exer_backward_a -- 后复权除权因子A；用于计算后复权价格(后复权价格=A*价格+B)(str:numpy.float64)
        # exer_backward_b -- 后复权除权因子B；用于计算后复权价格(后复权价格=A*价格+B)(str:numpy.float64)
        
        # ===================== 2. 计算账户维度数据 =====================
        # 除权数据（转为浮点数，模拟实际值）
        fq_data_columns = fq_data.columns.tolist()
        allotted_ps = 0
        if 'allotted_ps' in fq_data_columns:
            allotted_ps = np.float64(fq_data['allotted_ps'].iloc[-1])    # 每股送0.1股（10送1）

        rationed_ps = 0
        if 'rationed_ps' in fq_data_columns:
            rationed_ps = np.float64(fq_data['rationed_ps'].iloc[-1])    # 每股配0.2股（10配2）

        rationed_px = 0
        if 'rationed_px' in fq_data_columns:
            rationed_px = np.float64(fq_data['rationed_px'].iloc[-1])    # 配股价5元/股

        bonus_ps = 0
        if 'bonus_ps' in fq_data_columns:
            bonus_ps = np.float64(fq_data['bonus_ps'].iloc[-1])      # 每股分红0.05元        

        # （1）送股。 由于总额不能变，  送股后股票价格要变低。 如果是送股， allotted_ps 是大于0，股价变低； 如果是 缩股： allotted_ps 是小于0， 股价变高。
        if allotted_ps > 0 or allotted_ps < 0:
            total_allotted = int(position.amount * allotted_ps)
            log.info("{symbol}-{name}, 送股数：{total_allotted:.0f} 股".format(symbol=symbol, name=sub_get_stock_name(symbol), total_allotted=total_allotted))
            position.amount = position.amount + total_allotted
            position.enable_amount = position.enable_amount + total_allotted
            
        # （2）配股（全额参与）
        if rationed_ps > 0 and rationed_px > 0:
            total_rationed = int(position.amount * rationed_ps)
            rationed_amount = custom_round(total_rationed * rationed_px) 
            log.info("{symbol}-{name}, 配股数：{total_rationed:.0f} 股，需缴款：{rationed_amount:.2f} 元".format(symbol=symbol, name=sub_get_stock_name(symbol), total_rationed=total_rationed, rationed_amount=rationed_amount))
            position.amount = position.amount + total_allotted
            position.enable_amount = position.enable_amount + total_allotted
            sub_portfolio.cash = sub_portfolio.cash - rationed_amount

        # （3）现金分红（税前）
        if bonus_ps > 0:
            total_bonus = position.amount * bonus_ps
            #分红扣税：≤30 天 20%、31 天～1 年 10%、>1 年 0%；
            # 3. 计算天数差（取绝对值，避免顺序影响）
            days_diff = abs((datetime.strptime(current_date_line, "%Y-%m-%d") - datetime.strptime(position.buy_date, "%Y-%m-%d")).days) - 1
            tax = 0
            if days_diff > 0:   # PT好像都按20%缴税
                tax = total_bonus * 0.2                
            # if days_diff <= 30:
            #     tax = total_bonus * 0.2
            # elif days_diff > 30 and days_diff <= 365:
            #     tax = total_bonus * 0.1
            # else:
            #     tax = 0                
            total_bonus_taxed =  total_bonus - tax
            sub_portfolio.cash = sub_portfolio.cash + total_bonus_taxed
            log.info("{symbol}-{name}, 现金分红, {bonus_ps:.4f}/股 （税前）：{total_bonus:.2f} 元,  税后：{total_bonus_taxed:.2f} 元".format(symbol=symbol, name=sub_get_stock_name(symbol), bonus_ps=bonus_ps,total_bonus=total_bonus, total_bonus_taxed=total_bonus_taxed))   

            
        # 计算定点除权价,   除权价直接取数股票最新价即可， 不用计算。
        # pre_close = (pre_close - fq_data['bonus_ps'].iloc[0] + fq_data['rationed_ps'].iloc[0]*fq_data['rationed_px'].iloc[0])/(1+fq_data['allotted_ps'].iloc[0]+fq_data['rationed_ps'].iloc[0])
        # pre_close = custom_round(pre_close, 2)
   
    return 

def sub_calculate_commission_and_tax(symbol, sub_order, total_money, context):
    """_summary_
    计算买卖所需的费用， 含 印花税， 佣金， 经手费。 
    关于回测手续费计算：手续费=佣金费+经手费+印花税。
    1.佣金费=佣金费率*交易总金额(若佣金费计算后小于设置的最低佣金，则佣金费取最小佣金)。
    2.经手费=经手费率(万分之 0.487)*交易总金额。
    3.印花税=印花税率(千分之1)*交易总金额，仅卖出时收。

    本接口按通用规则计算,  与实盘发生费用不同。
    主要原因: 1、每个人的实际佣金费率不同。   2、这里context.commission数据主要用于回测, 与券商实际扣除的也不一致。
    Args:
        symbol (_type_): _description_
        trade (_type_): _description_
        total_money (_type_): _description_ 买入， 卖出总金额
        context (_type_): _description_

    Returns:
        _type_: _description_
    """
    tax = context.commission.tax
    
    # ETF 不收印花税
    if symbol.startswith('1') or symbol.startswith('5'):
        tax = 0
    
    # 买入不收印花税 trade["entrust_bs"] == '1'
    if sub_order.order_amount > 0: 
        tax = 0
    else:
        # 回测时 印花税固定为0.001,
        # log.info("XXXXX 印花税= {}, {}, {}, {}".format(tax, context.commission.tax, total_money, sub_order))
        pass

    # 关于回测手续费计算：手续费=佣金费+经手费

    # 佣金费=佣金费率*交易总金额(若佣金费计算后小于设置的最低佣金，则佣金费取最小佣金)
    # 经手费=经手费率(万分之0.487)*交易总金额
    # 卖出再加上印花税
    # 总费用 = 印花税 + 经手费 + MAX(佣金费, 最小佣金)
    total_money = abs(total_money)
    commission_and_tax = total_money * (tax + 0.0000487) + max(total_money*context.commission.cost, context.commission.min_trade_cost)

    return custom_round(commission_and_tax, 3)

def sub_get_stock_name(symbol):
    """_summary_

    Args:
        stocks (_type_): _description_  {'600570.SS': '恒生电子'}

    """

    name_dict = get_stock_name(symbol)
        
    return name_dict[symbol]

def get_order_direction_name(entrust_bs):
    
    direction = ""
    if entrust_bs  == "1":
        direction = "买入"
    else:
        direction = "卖出"
        
    return direction


def get_order_status_name(status):
    """_summary_
    获取订单状态的中文解释
    Args:
        status (_type_): _description_

    Returns:
        _type_: _description_
    """
    name = ""
    # status -- 订单状态(str)，该字段取值范围：
    if status == '0': #    '0' -- "未报"
        name = "未报"
    elif status == '1':     #    '1' -- "待报"
        name = "待报"
    elif status == '2': # # '2' -- "已报"
        name = "已报"
    elif status == '3': #     # '3' -- "已报待撤"
        name = "已报待撤"
    elif status == '4':     #    # '4' -- "部成待撤"
        name = "部成待撤"
    elif status == '5': #    # '5' -- "部撤"
        name = "部撤"
    elif status == '6':     # '6' -- "已撤"
        name = "已撤"
    elif status == '7':     # '7' -- "部成"
        name = "部成"
    elif status == '8':     # '8' -- "已成"
        name = "已成"       
    elif status == '9': #    # '9' -- "废单"
        name = "废单"
    elif status == '+':     # '+' -- "已受理"
        name = "已受理"
    elif status == '-':         # '-' -- "已确认"
        name = "已确认"
    elif status == 'V':         # 'V' -- "已确认"
        name = "已确认"
        
    return name
def is_etf_lof_fund(symbol):
    """_summary_
    检查标的是否是ETF,  或LOF基金
    
    Args:
        symbol (_type_): _description_

    Returns:
        _type_: _description_
    """
    if symbol.startswith('5') or symbol.startswith('1'):
        return True
    return False

def custom_round(num, ndigits=0):
    """
    解决python 四舍五入特殊情况的问题

    在Python中，当小数的尾数是5时，round()函数会根据5前面的数字是奇数还是偶数来决定是进位还是舍去。如果前一位是奇数，则进位；如果是偶数，则舍去。这种方法称为“银行家舍入法”。

    例如：

    print(round(0.5)) # 输出: 0
    print(round(1.5)) # 输出: 2

    Args:
        num (_type_): _description_
        ndigits (int, optional): _description_. Defaults to 0.

    Returns:
        _type_: _description_
    """
    temp = num * 10 ** ndigits
    if temp >= 0:
        return int(temp + 0.5) / (10 ** ndigits)
    else:
        return int(temp - 0.5) / (10 ** ndigits)
    

'''
