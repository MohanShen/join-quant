# Clone from JoinQuant
# postId: 7f7e13ee082ad1a81d6a2f1ab7ce6967
# backtestId: 651cbb79b58a56dd2997e062318b8866
# title: gap创新+离散度判断

# -*- coding: utf-8 -*-
"""
全天候动量策略 - 整合版
功能：分组冠军选择 + 大池离散度 + 进阶池对比 + 动态池筛选
"""

import numpy as np
import math
import datetime
import pandas as pd
from jqdata import *

# ==================== 数据缓存类（优化重复调用） ====================
class DataCache:
    """数据缓存类，避免重复调用API"""
    def __init__(self):
        self._current_data = None
        self._current_data_dt = None
        self._name_cache = {}           # 标的名称缓存
        self._price_cache = {}          # 价格序列缓存
        self._momentum_cache = {}       # 动量指标缓存
        self._premium_cache = {}        # 溢价率缓存
        self._current_price_cache = {}  # 当前价格缓存

    def get_current_data(self):
        """获取当前数据（缓存60秒）"""
        now = datetime.datetime.now()
        if self._current_data is None or (now - self._current_data_dt).seconds > 60:
            self._current_data = get_current_data()
            self._current_data_dt = now
        return self._current_data

    def get_name(self, security):
        """获取标的名称"""
        if security not in self._name_cache:
            try:
                self._name_cache[security] = self.get_current_data()[security].name
            except:
                self._name_cache[security] = "未知"
        return self._name_cache[security]

    def get_current_price(self, security):
        """获取当前价格"""
        if security in self._current_price_cache:
            return self._current_price_cache[security]
        try:
            price = self.get_current_data()[security].last_price
            self._current_price_cache[security] = price
            return price
        except:
            return None

    def get_price_series(self, etf, lookback_days):
        """获取价格序列（历史收盘价 + 当前价格）"""
        cache_key = (etf, lookback_days)
        if cache_key not in self._price_cache:
            prices = attribute_history(etf, lookback_days, '1d', ['close', 'high'])
            if len(prices) >= lookback_days:
                current_price = self.get_current_price(etf)
                if current_price is not None:
                    price_series = np.append(prices["close"].values, current_price)
                    self._price_cache[cache_key] = (prices, price_series)
                else:
                    self._price_cache[cache_key] = (prices, None)
            else:
                self._price_cache[cache_key] = (prices, None)
        return self._price_cache[cache_key]

    def get_momentum_metrics(self, context, etf):
        """获取动量指标（带缓存）"""
        if etf not in self._momentum_cache:
            self._momentum_cache[etf] = calculate_momentum_metrics_internal(context, etf)
        return self._momentum_cache[etf]

    def get_premium_rate(self, etf, date, max_back_days=5):
        """获取溢价率（带缓存）"""
        cache_key = (etf, date)
        if cache_key not in self._premium_cache:
            self._premium_cache[cache_key] = get_premium_rate_internal(etf, date, max_back_days)
        return self._premium_cache[cache_key]

    def clear_daily_cache(self):
        """清空每日缓存"""
        self._price_cache = {}
        self._momentum_cache = {}
        self._premium_cache = {}
        self._current_price_cache = {}

g.data_cache = DataCache()

# ==================== 初始化模块 ====================
def initialize(context):
    """
    初始化函数：设置交易参数、ETF池分组、大池、核心参数、调度任务
    """
    # ---------- 交易设置 ----------
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0002,
            close_commission=0.0002,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    set_benchmark("159915.XSHE")  # 基准：创业板ETF

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("========== 策略初始化开始 ==========")

    # ---------- 大类资产分组（用于分组策略冠军选择） ----------
    g.group_stock = [
        "159915.XSHE",   # 创业板ETF
        "588080.XSHG",   # 科创50
        "513100.XSHG",   # 纳指ETF
        "513290.XSHG",   # 纳指生物ETF
        "159529.XSHE",   # 标普消费
        "513310.XSHG",   # 中韩半导体ETF
        "513730.XSHG",   # 东南亚ETF
        "513050.XSHG",   # 中概互联网ETF
        "159509.XSHE",   # 纳指科技ETF
        "588020.XSHG",   # 科创成长
        '159783.XSHE',   # 双创ETF
        "159967.XSHE",   # 创成长ETF
    ]
    g.group_dividend = [
        "512890.XSHG",   # 红利低波ETF
        "513690.XSHG",   # 港股红利
        "159263.XSHE",   # 价值ETF
    ]
    g.group_bond_soy = [
        "159985.XSHE",   # 豆粕ETF
        "511380.XSHG",   # 可转债ETF
        "511010.XSHG",   # 国债ETF
        "511220.XSHG",   # 城投债ETF
    ]
    g.group_commodity = [
        "518880.XSHG",   # 黄金ETF
        "159980.XSHE",   # 有色ETF
        "501018.XSHG",   # 南方原油
        "161226.XSHE",   # 白银LOF
        "159981.XSHE",   # 能源化工ETF
    ]

    # 特殊标的常量
    g.GOLD_ETF = "518880.XSHG"      # 黄金ETF
    g.TREASURY_BOND_ETF = "511010.XSHG"  # 国债ETF
    g.CITY_INVEST_BOND_ETF = "511220.XSHG"  # 城投债ETF

    # 是否启用债券+豆粕分组
    g.enable_bond_soy_group = True

    # 所有分组集合
    if g.enable_bond_soy_group:
        g.all_etfs = (g.group_stock + g.group_dividend +
                      g.group_bond_soy + g.group_commodity)
    else:
        g.all_etfs = (g.group_stock + g.group_dividend +
                      g.group_commodity)

    # ---------- 大池（用于离散度计算） ----------
    g.big_pool = [
        # 股票组
        "159915.XSHE",   # 创业板ETF
        "159259.XSHE",   # 易方达100成长
        "513100.XSHG",   # 纳指ETF
        "513290.XSHG",   # 纳指生物ETF
        "159529.XSHE",   # 标普消费
        "513310.XSHG",   # 中韩半导体ETF
        "513730.XSHG",   # 东南亚ETF
        "513050.XSHG",   # 中概互联网ETF
        "159967.XSHE",   # 创成长ETF
        "159509.XSHE",   # 纳指科技ETF
        "588020.XSHG",   # 科创成长
        "159606.XSHE",   # 中证500成长
        "159203.XSHE",   # 大盘成长
        '159783.XSHE',   # 双创ETF
        # 红利组
        "512890.XSHG",   # 红利低波ETF
        "513690.XSHG",   # 港股红利
        "159263.XSHE",   # 价值ETF
        # 商品组
        "518880.XSHG",   # 黄金ETF
        "159980.XSHE",   # 有色ETF
        "501018.XSHG",   # 南方原油
        "161226.XSHE",   # 白银LOF
        "159981.XSHE",   # 能源化工ETF
        "159985.XSHE",   # 豆粕ETF
    ]

    # ---------- 核心参数 ----------
    g.lookback_days = 25                    # 动量计算回看天数
    g.holdings_num = 4                      # 持仓标的数量
    g.min_money = 5000                      # 最小交易金额（元）

    # ========== 盈利保护参数 ==========
    g.enable_profit_protection = True       # 盈利保护开关
    g.profit_protection_lookback = 1        # 盈利保护回看天数
    g.profit_protection_threshold = 0.05    # 盈利保护阈值（5%）
    g.profit_protection_check_times = ['10:00', '14:20']  # 盈利保护检查时间点

    # ========== 动量过滤参数 ==========
    g.loss = 0.97                           # 单日最大跌幅阈值（3%）
    g.min_score_threshold = 0.03               # 动量得分最小阈值
    g.max_score_threshold = 100.0           # 动量得分最大阈值

    # ========== 成交量过滤参数 ==========
    g.enable_volume_check = True            # 成交量过滤开关
    g.volume_lookback = 5                   # 成交量回看天数
    g.volume_threshold = 2                  # 成交量倍数阈值
    g.volume_return_limit = 1               # 年化收益率上限

    # ========== 短期动量过滤参数 ==========
    g.use_short_momentum_filter = True      # 短期动量过滤开关
    g.short_lookback_days = 10              # 短期动量回看天数
    g.short_momentum_threshold = 0.03        # 短期动量阈值

    # ========== 溢价率过滤参数 ==========
    g.enable_premium_filter = True          # 溢价率过滤开关
    g.premium_threshold = 0.18              # 溢价率阈值（18%）

    # ========== ES（预期损失）参数 ==========
    g.es_lookback = 120                     # ES计算回看天数
    g.es_confidence_level = 2.58            # ES置信水平（99%）

    # ========== 豆粕与债券权重上限 ==========
    g.max_bond_soy_weight_4 = 0.0           # 4只冠军时豆粕+债券最大权重（0%）
    g.max_bond_soy_weight_3 = 0.10          # 3只冠军时豆粕+债券最大权重（10%）
    g.max_bond_soy_weight_2 = 0.20          # 2只冠军时豆粕+债券最大权重（25%）

    # ========== 调仓参数 ==========
    g.rebalance_threshold = 1            # 加权偏离度阈值（50%）

    # ========== 运行时变量 ==========
    g.group_champions = {}                  # 各分组冠军
    g.last_champions = {}                   # 上一轮冠军
    g.cache_rankings = {}                   # 排名缓存

    # ========== 大池双信号参数 ==========
    g.enable_dispersion_filter = True       # 离散度过滤开关
    g.enable_dispersion_and_gap = True      # 启用离散度+Gap联合判断
    g.dispersion_mode = False               # 当前是否处于全仓单只模式
    g.dispersion_target = None              # 全仓单只模式的目标ETF
    
    # 离散度（沿用原有设定）
    g.dispersion_high_threshold = 0.3       # 固定阈值
    g.dispersion_min_count = 5              # 最小通过标的数
    g.dispersion_history = []               # 离散度历史记录
    g.dispersion_window = 5                 # 离散度平滑窗口（天数）
    
    # Gap开关（关闭时仅使用离散度）
    g.enable_gap_filter = True              # 是否启用Gap过滤
    g.gap_history = []                      # 预学习填充
    g.gap_percentile = 68                   # Gap分位阈值
    g.gap_history_window = 90              # 历史窗口
    g.gap_min_passed = 3                    # Gap触发所需最小通过数
    
    # 动量强度确认（历史分位）
    g.top1_score_history = []               # 预学习填充
    g.top1_score_percentile = 68            # 68%分位
    g.top1_score_window = 120               # 窗口
    g.top1_score_min_days = 30              # 需要的最少天数

    # ========== 商品单只+债券对冲机制 ==========
    g.enable_commodity_bond_hedge = False   # 原油和白银单只时启用债券对冲
    g.commodity_hedge_bond_weight = 0.10    # 债券对冲权重（10%）
    g.commodity_hedge_commodity_weight = 0.90  # 商品标的权重（90%）

    # ========== 进阶对比池参数 ==========
    # 触发进阶对比的股票类冠军标的（成长风格ETF）
    g.growth_champions = [
        "159967.XSHE",   # 创成长ETF
        "588020.XSHG",   # 科创成长
        "159783.XSHE",   # 双创ETF
        "159915.XSHE",   # 创业板ETF
        "588080.XSHG",   # 科创50
    ]

    # 分组模式下成长风格标的是否启用进阶对比
    g.enable_group_growth_advanced = True

    # A股走强判断开关（作为进阶池启用的前提条件）
    g.enable_a_share_strong_check = True       # 默认开启

    # 进阶标的池（行业最佳选择，固定池）
    g.advanced_pool = [
        # 电子
        "159997.XSHE",   # 天弘电子ETF
        # 电力设备/新能源
        "159368.XSHE",   # 华夏创业板新能源ETF
        "588960.XSHG",   # 科创新能源ETF
        "515030.XSHG",   # 华夏新能源车ETF
        # 医药生物/医疗保健
        "159377.XSHE",   # 国泰创业板医药ETF
        "588700.XSHG",   # 嘉实科创生物医药ETF
        "512170.XSHG",   # 华宝医疗ETF
        # 通信
        "159363.XSHE",   # 创业板人工智能ETF
        "515050.XSHG",   # 华夏5G通信ETF
        "515880.XSHG",   # 通信设备ETF
        # 金融服务
        "510230.XSHG",   # 国泰金融ETF
    ]

    # ========== 进阶动态池参数 ==========
    g.enable_advanced_dynamic_pool = True   # 启用进阶动态池
    g.dynamic_pool_volume_top = 200         # 流动性过滤前N只
    g.dynamic_pool_momentum_top = 20        # 动量过滤前N只
    g.dynamic_etf_pool = []                 # 动态ETF池（实际筛选结果）
    g.dynamic_pool_last_update = None       # 上次更新时间
    g.avg_etf_money_threshold = 5000000     # 日均成交额阈值（默认500万）

    # ========== 趋势得分参数（趋势得分 = 年化收益率 × R方）==========
    g.enable_trend_score = True              # 进阶池/动态池使用趋势得分（默认开启）
    g.enable_global_trend_score = False      # 全局趋势得分开关（默认关闭，开启后所有池都使用趋势得分）

    # ========== 相关性过滤参数 ==========
    g.enable_correlation_filter = True      # 是否启用相关性过滤
    g.correlation_lookback_days = 55        # 相关性计算回看天数
    g.correlation_top_n = 30                # 先选动量前N名再计算相关性
    g.correlation_threshold = 0.8           # 相关性阈值
    g.correlation_diversification_count = 10  # 最终选择的低相关标的数量

    # ========== 替换相关性检查参数 ==========
    g.enable_replace_correlation_check = True  # 是否启用替换时的相关性检查
    g.replace_correlation_threshold = 0.8      # 替换相关性阈值
    g.replace_trend_score_improve_threshold = 0.05  # 趋势得分提升阈值（5%）
    g.replace_trend_score_diff_threshold = 0.02    # 趋势得分差异阈值

    # ========== 进阶对比连续触发延迟参数 ==========
    g.advanced_trigger_count = 0            # 进阶对比连续触发计数
    g.advanced_trigger_days_required = 2    # 需要连续触发1天才真正启用

    # ========== 进阶池关键词分组 ==========
    g.advanced_keywords = {
        '半导体/电子': ['半导体', '电路', '电子', '芯片', '计算机', 'TMT'],
        '新能源': ['新能源', '光伏'],
        '电池': ['电池', '储能'],
        '医疗': ['医疗', '医药', '生物医药', '创新药'],
        '通信': ['通信', '5G', '高端', '人工智能', '信息'],
        '金融': ['金融', '证券', '保险', '非银']
    }

    # 动态池排除关键词
    g.dynamic_pool_exclude_words = ['债', '债券', '企业债', '国债', '金融债']

    # 运行时状态变量
    g.in_advanced_mode = False              # 当前是否处于进阶对比模式

    # ---------- 更新全局ETF集合 ----------
    g.all_etfs = (g.group_stock + g.group_dividend +
                  g.group_bond_soy + g.group_commodity +
                  g.advanced_pool)

    # ---------- 交易调度 ----------
    run_daily(check_positions, time='09:10')
    run_daily(etf_sell_trade, time='14:30')
    run_daily(etf_buy_trade, time='14:40')

    for check_time in g.profit_protection_check_times:
        run_daily(profit_protection_check, time=check_time)

    log.info(f"策略初始化完成，加权偏离度阈值：{g.rebalance_threshold*100:.0f}%")
    log.info(f"豆粕+债券组权重上限：4只冠军 {g.max_bond_soy_weight_4*100:.0f}% | 3只冠军 {g.max_bond_soy_weight_3*100:.0f}% | 2只冠军 {g.max_bond_soy_weight_2*100:.0f}%")
    log.info(f"双信号过滤器：{'开启' if g.enable_dispersion_filter else '关闭'}，Gap过滤：{'开启' if g.enable_gap_filter else '关闭'}")
    log.info(f"进阶动态池：{'开启' if g.enable_advanced_dynamic_pool else '关闭'}")
    
    # 预学习 Gap 和 Top1 历史（仅在Gap过滤开启时执行）
    if g.enable_gap_filter and not g.gap_history:
        pre_learn_dual_signal(context)
    
    log.info("========== 策略初始化完成 ==========")


# ==================== A股走强判断（进阶池启用前提） ====================
def is_a_share_strong(context):
    """
    A股走强判断：使用创业板ETF(159915.XSHE)的均线判断
    条件：MA21 > MA55 > MA144（短期均线 > 中期均线 > 长期均线）
    用途：作为进阶池启用的前提条件
    
    全局开关：g.enable_a_share_strong_check（默认开启）
    """
    # 如果开关关闭，直接返回True（相当于不检查）
    if not getattr(g, 'enable_a_share_strong_check', True):
        return True
    
    code = "159915.XSHE"  # 创业板ETF
    try:
        df = attribute_history(code, 145, '1d', ['close'], skip_paused=True)
        if len(df) < 144:
            return False
        ma21 = df['close'].iloc[-21:].mean()
        ma55 = df['close'].iloc[-55:].mean()
        ma144 = df['close'].iloc[-144:].mean()
        is_strong = ma21 > ma55 > ma144
        return is_strong
    except Exception as e:
        return False


# ==================== 盈利保护检查函数 ====================
def profit_protection_check(context):
    """盈利保护独立检查（定时触发）"""
    if not g.enable_profit_protection:
        return
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.all_etfs:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if check_profit_protection(sec, context):
                smart_order_target_value(sec, 0, context)


def check_profit_protection(security, context, lookback=None, threshold=None):
    """检查是否触发盈利保护"""
    if not g.enable_profit_protection:
        return False
    lookback = lookback or g.profit_protection_lookback
    threshold = threshold or g.profit_protection_threshold
    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        return False
    max_high = hist['high'].max()
    current_price = g.data_cache.get_current_price(security)
    if current_price is None:
        return False
    if current_price <= max_high * (1 - threshold):
        return True
    return False


# ==================== 溢价率获取函数 ====================
def get_premium_rate_internal(code, date, max_back_days=5):
    """获取ETF溢价率"""
    price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
    if price_data.empty:
        return None, None, None
    price = price_data['close'].iloc[0]
    net_value = None
    used_date = date
    start_date = date - datetime.timedelta(days=max_back_days*2)
    trade_days = get_trade_days(start_date=start_date, end_date=date)
    trade_days = [pd.to_datetime(d).date() for d in trade_days]
    for dt in reversed(trade_days):
        if dt > date:
            continue
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            used_date = dt
            break
        try:
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == dt
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                used_date = dt
                break
        except:
            continue
    if net_value is None:
        return None, None, None
    premium_rate = (price - net_value) / net_value
    return premium_rate, price, net_value


# ==================== 动量评分（通用过滤 + 得分） ====================
def calculate_momentum_metrics_internal(context, etf):
    """计算动量指标（包含所有过滤条件）"""
    try:
        name = g.data_cache.get_name(etf)
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        prices, price_series = g.data_cache.get_price_series(etf, lookback)
        
        if price_series is None or len(price_series) < g.lookback_days:
            return None

        # 盈利保护检查
        if check_profit_protection(etf, context):
            return None

        # 溢价率过滤
        if g.enable_premium_filter:
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = g.data_cache.get_premium_rate(etf, prev_date)
            if premium is not None and premium > g.premium_threshold:
                return None

        # 成交量过滤
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns(price_series, g.lookback_days)
                if annualized > g.volume_return_limit:
                    return None

        # 短期动量过滤
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0
        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            return None

        # 计算加权线性回归斜率（动量得分）
        recent = price_series[-(g.lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        
        # 计算R方
        y_pred = intercept + slope * x
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        ss_res = np.sum((y - y_pred) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # 趋势得分 = 年化收益率 × R方（如果启用趋势得分模式）
        # 判断逻辑：
        # 1. 全局趋势得分开关开启 → 所有场景都使用趋势得分
        # 2. 进阶池开关开启 且 在进阶模式中 → 使用趋势得分
        # 3. 其他情况 → 使用原始动量算法
        use_trend_score = False
        if getattr(g, 'enable_global_trend_score', False):
            use_trend_score = True
        elif getattr(g, 'enable_trend_score', True) and getattr(g, 'in_advanced_mode', False):
            use_trend_score = True
        
        if use_trend_score:
            score = annualized_returns * r_squared
        else:
            score = annualized_returns

        # 连续下跌检查
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < g.loss:
                return None

        return {
            'etf': etf,
            'etf_name': name,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'current_price': price_series[-1],
            'short_annualized': short_annualized,
        }
    except Exception as e:
        return None


def get_annualized_returns(price_series, lookback_days):
    """计算年化收益率"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def get_volume_ratio(context, security, lookback=None, threshold=None):
    """计算成交量比率"""
    lookback = lookback or g.volume_lookback
    threshold = threshold or g.volume_threshold
    try:
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
            return ratio
        return None
    except Exception as e:
        return None


# ==================== Gap预学习模块 ====================
def compute_simple_momentum(security, end_date, lookback_days):
    """
    基于指定日期的历史收盘价，计算加权对数回归的动量得分。
    返回值：年化收益率（即原始得分），若数据不足则返回 None。
    """
    df = get_price(security, end_date=end_date, count=lookback_days + 5,
                   frequency='daily', fields=['close'], skip_paused=True, fq='pre')
    if df is None or len(df) < lookback_days + 1:
        return None
    
    closes = df['close'].values[-lookback_days-1:]   # 取最近 lookback_days+1 个点
    if len(closes) < lookback_days + 1:
        return None
    
    y = np.log(closes)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    
    try:
        slope, _ = np.polyfit(x, y, 1, w=weights)
    except:
        return None
    
    annualized = math.exp(slope * 250) - 1
    return annualized


def pre_learn_dual_signal(context):
    """
    使用最近 90 个交易日，逐日计算大池的 Gap 和 top1 动量得分，
    填充 g.gap_history 和 g.top1_score_history。
    """
    trade_days = get_trade_days(end_date=context.current_dt.date(), count=120)
    if len(trade_days) < 90:
        days = trade_days
        log.warning("历史天数不足90天，使用全部")
    else:
        days = trade_days[-90:]

    log.info(f"开始预学习 Gap/Top1，共 {len(days)} 天")
    temp_gap, temp_top1 = [], []

    for d in days:
        scores = []
        for etf in g.big_pool:
            try:
                info = get_security_info(etf)
                if info.start_date > d:
                    continue
            except:
                continue
            score = compute_simple_momentum(etf, d, g.lookback_days)
            if score is not None:
                scores.append(score)

        if len(scores) < 2:
            continue

        scores_sorted = sorted(scores, reverse=True)
        top1, top2 = scores_sorted[0], scores_sorted[1]
        std_val = np.std(scores)
        denom = max(std_val, top1 * 0.0001)
        gap = (top1 - top2) / denom if denom > 0 else 0.0

        temp_gap.append(gap)
        temp_top1.append(top1)

    # 保留窗口长度
    g.gap_history = temp_gap[-g.gap_history_window:]
    g.top1_score_history = temp_top1[-g.top1_score_window:]
    log.info(f"预学习完成：Gap 记录 {len(g.gap_history)} 条，Top1 记录 {len(g.top1_score_history)} 条")


def _get_percentile_threshold(history, min_days, percentile, default):
    """获取滚动分位阈值（辅助函数，保证计算结果一致）"""
    if len(history) >= min_days:
        return np.percentile(history, percentile)
    return default


# ==================== 大池过滤 + 双信号计算 ====================
def compute_filtered_pool_dispersion(context):
    """
    返回:
      trigger_dispersion: bool, 是否触发大池全仓单只
      passed_metrics: list of dict, 通过过滤的标的动量详情
      best_etf: str, 最优ETF代码
    """
    # ---------- 1. 遍历大池，收集通过过滤的标的 ----------
    passed = []
    for etf in g.big_pool:
        if g.data_cache.get_current_data()[etf].paused:
            continue
        metrics = g.data_cache.get_momentum_metrics(context, etf)
        if metrics is not None:
            passed.append({
                'etf': etf,
                'score': metrics['score'],
                'name': g.data_cache.get_name(etf),
                **metrics
            })
    
    passed.sort(key=lambda x: x['score'], reverse=True)
    scores = [m['score'] for m in passed]
    best_etf = passed[0]['etf'] if passed else None
    
    # 缓存长度，避免重复计算
    n_passed = len(passed)
    n_scores = len(scores)
    
    # 如果标的数量太少，直接放弃大池
    if n_passed < 2:
        return False, passed, best_etf

    top1_score = scores[0]

    # ---------- 2. 计算离散度（5只起算，固定阈值0.3） ----------
    dispersion_trigger = False
    if n_passed >= g.dispersion_min_count:
        # 只计算一次均值和标准差
        mean_score = np.mean(scores)
        std_score = np.std(scores)
        disp_ratio = (top1_score - mean_score) / std_score if std_score > 0 else 0.0
        
        # 优化：直接存储数值而非字典
        g.dispersion_history.append(disp_ratio)
        # 优化：使用 pop(0) 替代切片
        while len(g.dispersion_history) > g.dispersion_window:
            g.dispersion_history.pop(0)
        
        # 优化：直接计算均值，无需列表推导
        avg_disp = np.mean(g.dispersion_history)
        dispersion_trigger = avg_disp > g.dispersion_high_threshold

    # ---------- 3. 计算 Gap 及滚动分位阈值（可选） ----------
    gap_trigger = False
    current_gap = 0.0
    gap_threshold = 0.0
    
    if g.enable_gap_filter:
        if n_passed >= g.gap_min_passed and n_scores >= 2:
            # 优化：复用已计算的标准差（如果之前计算过）
            if 'std_score' in locals():
                std_val = std_score
            else:
                std_val = np.std(scores)
            
            denom = max(std_val, top1_score * 0.0001)
            current_gap = (top1_score - scores[1]) / denom if denom > 0 else 0.0

        # 使用辅助函数获取阈值（保证逻辑一致）
        gap_threshold = _get_percentile_threshold(g.gap_history, 30, g.gap_percentile, 2.5)

        # 存储今日gap（供未来使用）
        g.gap_history.append(current_gap)
        while len(g.gap_history) > g.gap_history_window:
            g.gap_history.pop(0)

        gap_trigger = n_passed >= g.gap_min_passed and current_gap > gap_threshold

    # ---------- 4. 动量强度确认：top1_score > 历史68%分位（可选） ----------
    momentum_confirmed = True  # 默认确认
    top1_threshold = 0.0
    
    if g.enable_gap_filter:
        # 使用辅助函数获取阈值（保证逻辑一致）
        top1_threshold = _get_percentile_threshold(g.top1_score_history, g.top1_score_min_days, g.top1_score_percentile, 0.03)

        # 将今日top1存入历史（供明天使用）
        g.top1_score_history.append(top1_score)
        while len(g.top1_score_history) > g.top1_score_window:
            g.top1_score_history.pop(0)

        momentum_confirmed = top1_score > top1_threshold

    # ---------- 5. 综合判断 ----------
    if g.enable_gap_filter:
        # 双信号模式：离散度 OR Gap，且动量确认
        signal_disp_or_gap = dispersion_trigger or gap_trigger
        final_trigger = signal_disp_or_gap and momentum_confirmed
    else:
        # 纯离散度模式：仅离散度触发
        final_trigger = dispersion_trigger

    if final_trigger:
        log.info(f"🎯 大池模式触发: 离散度={dispersion_trigger}, Gap={gap_trigger}({current_gap:.3f}>{gap_threshold:.3f}), " 
                 f"Top1动量{top1_score*100:.2f}% > {top1_threshold*100:.2f}%(68分位)")
    else:
        # 未触发时输出详细判断结果
        reasons = []
        if not dispersion_trigger:
            reasons.append(f"离散度未达标")
        if g.enable_gap_filter:
            if not gap_trigger:
                reasons.append(f"Gap未达标({current_gap:.3f}<{gap_threshold:.3f})")
            if not momentum_confirmed:
                reasons.append(f"动量未达标({top1_score*100:.2f}%<{top1_threshold*100:.2f}%(68分位))")
        if reasons:
            log.info(f"📊 大池模式未触发: {' | '.join(reasons)}")
    
    return final_trigger, passed, best_etf


# ==================== 分组冠军选择 ====================
def select_champion_in_group(context, group_etfs):
    """从分组中选择冠军"""
    best_etf = None
    best_score = -np.inf
    for etf in group_etfs:
        if g.data_cache.get_current_data()[etf].paused:
            continue
        metrics = g.data_cache.get_momentum_metrics(context, etf)
        if metrics is not None:
            if metrics['score'] > best_score:
                best_score = metrics['score']
                best_etf = etf
    return best_etf


def update_group_champions(context):
    """更新各分组冠军"""
    champions = {}
    champions['stock'] = select_champion_in_group(context, g.group_stock)
    champions['dividend'] = select_champion_in_group(context, g.group_dividend)
    
    if g.enable_bond_soy_group:
        champions['bond_soy'] = select_champion_in_group(context, g.group_bond_soy)
    
    champions['commodity'] = select_champion_in_group(context, g.group_commodity)
    g.group_champions = {k: v for k, v in champions.items() if v is not None}
    
    # 增强股票类冠军选择（进阶对比）
    enhance_stock_champion(context)


# ==================== ES计算 ====================
def get_daily_returns_safe(security, required_days):
    """获取日收益率序列"""
    try:
        df = attribute_history(security, required_days + 5, '1d', ['close'], skip_paused=True)
        if df is None or len(df) < 2:
            return []
        rets = df['close'].pct_change().dropna().values
        return rets
    except Exception as e:
        return []


def calculate_es(security, lookback_days, confidence_level=2.58):
    """计算ES（预期损失）"""
    alpha_map = {1.96: 0.05, 2.06: 0.04, 2.18: 0.03, 2.34: 0.02, 2.58: 0.01, 5: 0.00001}
    a = alpha_map.get(confidence_level, 0.05)
    rets = get_daily_returns_safe(security, lookback_days)
    if len(rets) < 5:
        return 0.0
    rets_sorted = sorted(rets)
    n = int(len(rets) * a)
    if n == 0:
        n = 1
    es = -sum(rets_sorted[:n]) / n
    return es


# ==================== 风险平价权重计算 ====================
def compute_risk_parity_weights(es_dict):
    """计算风险平价权重"""
    if not es_dict:
        return {}
    
    pos_es = [v for v in es_dict.values() if isinstance(v, (int, float)) and v > 0]
    if pos_es:
        min_es = min(pos_es)
        eps = min_es * 0.01
    else:
        eps = 0.0001
    
    es_adj = {}
    for k, v in es_dict.items():
        if isinstance(v, (int, float)) and v > 0:
            es_adj[k] = v
        else:
            es_adj[k] = eps
    
    max_es = max(es_adj.values())
    risk_contrib = {}
    for k, v in es_adj.items():
        risk_contrib[k] = max_es / v
    
    total_risk = 0.0
    for v in risk_contrib.values():
        total_risk += v
    
    if total_risk == 0:
        total_risk = 1.0
    
    weights = {}
    for k, v in risk_contrib.items():
        weights[k] = v / total_risk
    return weights


def apply_bond_cap(weights, bond_key='bond_soy', max_weight=None):
    """应用债券权重上限"""
    if max_weight is None or bond_key not in weights or weights[bond_key] <= max_weight:
        return weights
    old_bond = weights[bond_key]
    new_bond = max_weight
    other_total_old = 1.0 - old_bond
    if other_total_old <= 0:
        weights[bond_key] = new_bond
        return weights
    scale = (1.0 - new_bond) / other_total_old
    new_weights = {}
    for k, w in weights.items():
        if k == bond_key:
            new_weights[k] = new_bond
        else:
            new_weights[k] = w * scale
    total = 0.0
    for v in new_weights.values():
        total += v
    if total > 0 and abs(total - 1.0) > 1e-6:
        for k in new_weights:
            new_weights[k] = new_weights[k] / total
    return new_weights


def compute_target_weights(context):
    """计算目标权重"""
    champions = g.group_champions
    if len(champions) == 0:
        return {}
    
    es_dict = {group: calculate_es(etf, g.es_lookback, g.es_confidence_level) for group, etf in champions.items()}
    rp_weights = compute_risk_parity_weights(es_dict)
    n = len(champions)
    if n == 4:
        rp_weights = apply_bond_cap(rp_weights, max_weight=g.max_bond_soy_weight_4)
    elif n == 3:
        rp_weights = apply_bond_cap(rp_weights, max_weight=g.max_bond_soy_weight_3)
    elif n == 2:
        rp_weights = apply_bond_cap(rp_weights, max_weight=g.max_bond_soy_weight_2)
    final_weights = {}
    for g_key, w in rp_weights.items():
        if champions.get(g_key):
            final_weights[champions[g_key]] = w
    total = 0.0
    for v in final_weights.values():
        total += v
    if total > 0:
        for k in final_weights:
            final_weights[k] = final_weights[k] / total
    return final_weights


# ==================== 进阶对比机制 ====================
def select_best_advanced_etf(context, current_champion):
    """
    进阶对比：从进阶池+动态池中选择最优标的
    前提条件：A股走强判断通过（MA21 > MA55 > MA144）
    """
    # ========== A股走强判断（进阶池启用前提） ==========
    if not is_a_share_strong(context):
        log.info(f"【进阶对比】A股未走强（MA21未大于MA55大于MA144），跳过进阶对比")
        return current_champion
    
    # 仅当当前冠军为成长风格时才进行进阶对比
    if current_champion not in g.growth_champions:
        log.info(f"【进阶对比】当前冠军{current_champion} {get_name(current_champion)}不是成长风格，跳过进阶对比")
        return current_champion
    
    # 确保动态池已更新
    ensure_dynamic_pool_updated(context, current_champion)
    
    # 设置进阶模式标志（在计算当前冠军之前设置，确保使用相同的评分算法）
    g.in_advanced_mode = True
    
    # 计算当前冠军的动量得分
    current_metrics = g.data_cache.get_momentum_metrics(context, current_champion)
    if current_metrics is None:
        g.in_advanced_mode = False  # 重置标志
        log.info(f"【进阶对比】当前冠军{current_champion}核心过滤未通过，保持原冠军")
        return current_champion
    
    current_score = current_metrics['score']
    current_r_squared = current_metrics.get('r_squared', 0)
    current_annualized = current_metrics['annualized_returns']
    score_type = "趋势得分" if getattr(g, 'enable_trend_score', True) else "动量得分"
    log.info(f"【进阶对比】A股走强，启动进阶对比！当前冠军: {current_champion} {get_name(current_champion)} {score_type}{current_score*100:.2f}% (R方:{current_r_squared:.4f}, 年化:{current_annualized*100:.2f}%)")
    
    # 合并进阶池 + 动态池
    advanced_pool = list(g.advanced_pool) if hasattr(g, 'advanced_pool') else []
    dynamic_pool = list(g.dynamic_etf_pool) if g.dynamic_etf_pool else []
    compare_pool = list(set(advanced_pool + dynamic_pool))
    log.info(f"【进阶对比】进阶池{len(advanced_pool)}只 + 动态池{len(dynamic_pool)}只 = 合并池{len(compare_pool)}只")
    
    if not compare_pool:
        g.in_advanced_mode = False  # 重置标志
        log.info(f"【进阶对比】合并池为空，跳过对比")
        return current_champion
    
    best_etf = current_champion
    best_score = current_score
    filtered_count = 0
    
    for etf in compare_pool:
        if etf == current_champion:
            continue
        
        # 核心过滤：动量计算
        metrics = g.data_cache.get_momentum_metrics(context, etf)
        if metrics is None:
            continue
        
        filtered_count += 1
        score = metrics['score']
        
        if score > best_score:
            best_score = score
            best_etf = etf
    
    g.in_advanced_mode = False
    
    log.info(f"【进阶对比】合并池过滤后: {filtered_count}只")
    
    if best_etf != current_champion:
        # 替换相关性检查
        should_replace = True
        if g.enable_replace_correlation_check:
            advanced_pool_set = set(advanced_pool + dynamic_pool)
            if current_champion in advanced_pool_set:
                try:
                    end_date = context.previous_date
                    price_data = get_price([current_champion, best_etf], 
                                          end_date=end_date, 
                                          count=g.correlation_lookback_days,
                                          frequency='daily', fields=['close'], 
                                          panel=False, fq='pre')
                    
                    if price_data is not None and not price_data.empty:
                        pivot_data = price_data.pivot(index='time', columns='code', values='close')
                        pivot_data = pivot_data.dropna()
                        returns = pivot_data.pct_change().dropna()
                        corr_matrix = returns.corr()
                        correlation = 0
                        if current_champion in corr_matrix and best_etf in corr_matrix:
                            correlation = abs(corr_matrix.loc[current_champion, best_etf])
                        
                        momentum_improve = (best_score - current_score) / max(current_score, 0.001)
                        momentum_diff = best_score - current_score
                        
                        if correlation > g.replace_correlation_threshold and \
                           (momentum_improve < g.replace_trend_score_improve_threshold or \
                            momentum_diff < g.replace_trend_score_diff_threshold):
                            should_replace = False
                            log.info(f"【进阶对比-相关性检查】相关性{correlation:.4f} > {g.replace_correlation_threshold}，趋势得分提升不足，不替换")
                
                except Exception as e:
                    pass
        
        if should_replace:
            log.info(f"🏆【进阶对比】最终选择: {best_etf} {get_name(best_etf)} 得分{best_score*100:.2f}% > {current_champion} {get_name(current_champion)} {current_score*100:.2f}%")
        else:
            best_etf = current_champion
    else:
        log.info(f"【进阶对比】{current_champion} {get_name(current_champion)} 仍然最优，得分{current_score*100:.2f}%")
    
    g.in_advanced_mode = False  # 重置进阶模式标志
    return best_etf


def enhance_stock_champion(context):
    """
    增强股票类冠军选择：如果是成长风格，进行进阶对比
    前提条件：A股走强判断通过
    """
    stock_champion = g.group_champions.get('stock')
    if stock_champion is None:
        return
    
    # 检查进阶对比开关
    if not getattr(g, 'enable_group_growth_advanced', True):
        return
    
    # ========== A股走强判断（进阶池启用前提） ==========
    if not is_a_share_strong(context):
        g.advanced_trigger_count = 0
        log.info(f"【进阶对比】A股未走强（MA21未大于MA55大于MA144），跳过进阶对比")
        return
    
    if stock_champion not in g.growth_champions:
        g.advanced_trigger_count = 0
        return
    
    g.advanced_trigger_count += 1
    
    if g.advanced_trigger_count < g.advanced_trigger_days_required:
        log.info(f"【进阶对比】成长冠军{stock_champion} {get_name(stock_champion)}触发进阶对比，连续触发第{g.advanced_trigger_count}天，需连续{g.advanced_trigger_days_required}天才启用")
        return
    
    enhanced_champion = select_best_advanced_etf(context, stock_champion)
    if enhanced_champion != stock_champion:
        g.group_champions['stock'] = enhanced_champion
        log.info(f"【进阶对比】股票类冠军更新为: {enhanced_champion} {get_name(enhanced_champion)}")


# ==================== 进阶动态池更新 ====================
def ensure_dynamic_pool_updated(context, target_etf=None):
    """确保动态池已更新（在需要时才更新）"""
    if not g.enable_advanced_dynamic_pool:
        return
    # ========== A股走强判断（动态池启用前提） ==========
    if not is_a_share_strong(context):
        return
    today = context.current_dt.date()
    if g.dynamic_pool_last_update != today:
        update_advanced_dynamic_pool(context, target_etf)


def update_advanced_dynamic_pool(context, target_etf=None):
    """根据关键词从全市场筛选ETF构建动态池"""
    if not g.enable_advanced_dynamic_pool:
        return
    
    # ========== A股走强判断（动态池启用前提） ==========
    if not is_a_share_strong(context):
        log.info(f"【进阶动态池】A股未走强，跳过动态池更新")
        return
    
    if target_etf is not None:
        if target_etf not in g.growth_champions:
            return
    
    today = context.current_dt.date()
    if g.dynamic_pool_last_update == today:
        return
    
    log.info(f"【进阶动态池】A股走强，开始更新...")
    
    try:
        df_etf = get_all_securities(['etf'])
        today_dt = context.current_dt.date()
        min_listing_days = 30
        df_etf['listing_days'] = df_etf['start_date'].apply(
            lambda x: (today_dt - (x.date() if hasattr(x, 'date') else x)).days
        )
        df_etf = df_etf[df_etf['listing_days'] > min_listing_days]
        etf_list = df_etf.index.tolist()
        etf_names_dict = df_etf['display_name'].to_dict()
        
        # 收集所有关键词
        all_keywords = []
        for keywords in g.advanced_keywords.values():
            all_keywords.extend(keywords)
        
        # 关键词筛选
        filtered_etfs = []
        for code in etf_list:
            name = etf_names_dict.get(code, str(code))
            excluded = [ex for ex in g.dynamic_pool_exclude_words if ex in name]
            if excluded:
                continue
            matched_kws = [kw for kw in all_keywords if kw in name]
            if matched_kws:
                filtered_etfs.append(code)
        
        if not filtered_etfs:
            g.dynamic_etf_pool = []
            g.dynamic_pool_last_update = today
            return
        
        # 流动性过滤
        dynamic_threshold = g.avg_etf_money_threshold
        end_date = context.previous_date
        TRADE_DAYS_COUNT = 5
        
        try:
            money_data = get_price(filtered_etfs, end_date=end_date, count=TRADE_DAYS_COUNT,
                                   frequency='daily', fields=['money'], panel=False, fq='pre')
            if money_data is not None and not money_data.empty:
                total_money = money_data.groupby('code')['money'].sum()
                avg_daily_money = total_money / TRADE_DAYS_COUNT
                qualified = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
                liquid_etfs = qualified.head(g.dynamic_pool_volume_top * 2).index.tolist()
            else:
                liquid_etfs = filtered_etfs[:g.dynamic_pool_volume_top * 2]
        except:
            liquid_etfs = filtered_etfs[:g.dynamic_pool_volume_top * 2]
        
        log.info(f"【进阶动态池】关键词筛选{len(filtered_etfs)}只，流动性过滤后{len(liquid_etfs)}只")
        
        # 动量过滤 + R方过滤
        momentum_scores = []
        filtered_logs = []
        g.in_advanced_mode = True
        
        for etf in liquid_etfs:
            try:
                prices, price_series = g.data_cache.get_price_series(etf, g.lookback_days + 1)
                if prices is None or price_series is None or len(price_series) < g.lookback_days:
                    continue
                
                # 使用14:20实时价格+历史价格计算动量和R方
                recent_prices = price_series[-(g.lookback_days + 1):]
                y = np.log(recent_prices)
                x = np.arange(len(y))
                weights = np.linspace(1, 2, len(y))
                slope, intercept = np.polyfit(x, y, 1, w=weights)
                
                # 计算R方
                y_pred = intercept + slope * x
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                ss_res = np.sum((y - y_pred) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                
                # R方过滤（阈值0.4，过滤拟合质量差的标的）
                if r_squared < 0.4:
                    filtered_logs.append(f"【进阶动态池】{etf} {g.data_cache.get_name(etf)} R方{r_squared:.4f} < 0.4，排除")
                    continue
                
                annualized_returns = math.exp(slope * 250) - 1
                
                # 趋势得分 = 年化收益率 × R方（根据开关决定是否使用）
                # 判断逻辑：
                # 1. 全局趋势得分开关开启 → 使用趋势得分
                # 2. 进阶池开关开启 且 在进阶模式中 → 使用趋势得分
                # 3. 其他情况 → 使用原始动量算法
                use_trend_score = False
                if getattr(g, 'enable_global_trend_score', False):
                    use_trend_score = True
                elif getattr(g, 'enable_trend_score', True) and getattr(g, 'in_advanced_mode', False):
                    use_trend_score = True
                
                if use_trend_score:
                    final_score = annualized_returns * r_squared
                    score_type = "趋势得分"
                else:
                    final_score = annualized_returns
                    score_type = "动量得分"
                
                momentum_scores.append((etf, final_score, r_squared, annualized_returns))
                
            except Exception as e:
                log.warning(f"【进阶动态池】{etf} {g.data_cache.get_name(etf)} 过滤/计算失败: {e}")
                continue
        
        g.in_advanced_mode = False
        
        # 随机显示3个过滤日志
        if filtered_logs:
            import random
            sample_logs = random.sample(filtered_logs, min(3, len(filtered_logs)))
            for log_msg in sample_logs:
                log.info(log_msg)
        
        log.info(f"【进阶动态池】核心过滤+R方过滤后: {len(momentum_scores)}只")
        
        # 取前N只（按最终得分排序）
        momentum_scores.sort(key=lambda x: x[1], reverse=True)
        top_momentum = [x[0] for x in momentum_scores[:g.dynamic_pool_momentum_top]]
        
        # 显示前3只ETF得分情况（含R方和原始年化收益率）
        if momentum_scores:
            sample_size = min(3, len(momentum_scores))
            score_type = "趋势得分" if getattr(g, 'enable_trend_score', True) else "动量得分"
            for etf, score, r_sq, annualized in momentum_scores[:sample_size]:
                log.info(f"  📊 {etf} {g.data_cache.get_name(etf)} {score_type}: {score*100:.2f}% (R方: {r_sq:.4f}, 年化: {annualized*100:.2f}%)")
        
        # 相关性过滤
        if g.enable_correlation_filter and len(top_momentum) > g.correlation_diversification_count:
            candidates = top_momentum[:g.correlation_top_n]
            
            if len(candidates) >= 2:
                try:
                    end_date = context.previous_date
                    price_data = get_price(candidates, end_date=end_date, 
                                          count=g.correlation_lookback_days,
                                          frequency='daily', fields=['close'], 
                                          panel=False, fq='pre')
                    
                    if price_data is not None and not price_data.empty:
                        pivot_data = price_data.pivot(index='time', columns='code', values='close')
                        pivot_data = pivot_data.dropna(axis=1)
                        returns = pivot_data.pct_change().dropna()
                        corr_matrix = returns.corr()
                        
                        selected_etfs = [candidates[0]]
                        
                        while len(selected_etfs) < min(g.correlation_diversification_count, len(candidates)):
                            best_etf = None
                            best_score = float('inf')
                            
                            for etf in candidates:
                                if etf in selected_etfs:
                                    continue
                                
                                avg_corr = 0
                                count = 0
                                for selected in selected_etfs:
                                    if etf in corr_matrix and selected in corr_matrix:
                                        avg_corr += abs(corr_matrix.loc[etf, selected])
                                        count += 1
                                if count > 0:
                                    avg_corr /= count
                                
                                momentum_idx = candidates.index(etf)
                                score = momentum_idx * 0.1 + avg_corr * 10
                                
                                if score < best_score:
                                    best_score = score
                                    best_etf = etf
                            
                            if best_etf:
                                selected_etfs.append(best_etf)
                            else:
                                break
                        
                        g.dynamic_etf_pool = list(set(selected_etfs))
                    else:
                        g.dynamic_etf_pool = top_momentum[:g.dynamic_pool_momentum_top]
                except:
                    g.dynamic_etf_pool = top_momentum[:g.dynamic_pool_momentum_top]
            else:
                g.dynamic_etf_pool = candidates
        else:
            g.dynamic_etf_pool = top_momentum
        
        log.info(f"【进阶动态池】更新完成，共{len(g.dynamic_etf_pool)}只")
        
        # 更新全局ETF集合
        g.all_etfs = (g.group_stock + g.group_dividend +
                      g.group_bond_soy + g.group_commodity +
                      g.advanced_pool + g.dynamic_etf_pool)
        
        g.dynamic_pool_last_update = today
        
    except Exception as e:
        log.warning(f"【进阶动态池】更新失败: {e}")


# ==================== 交易执行模块 ====================
def check_positions(context):
    """检查当前持仓"""
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


def get_name(security):
    """获取标的名称"""
    return g.data_cache.get_name(security)


def smart_order_target_value(security, target_value, context, skip_closeable_check=False):
    """智能下单：按目标市值调整仓位"""
    data = g.data_cache.get_current_data()
    if data[security].paused:
        return False
    price = data[security].last_price
    if price == 0:
        return False
    target_amount = int(target_value / price) // 100 * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    if cur_amount == target_amount:
        return False
    if not skip_closeable_check:
        if hasattr(data[security], 'closeable') and not data[security].closeable:
            return False
    order_target(security, target_amount)
    return True


def etf_sell_trade(context):
    """卖出操作（14:30执行）"""
    g.data_cache.clear_daily_cache()

    trigger, passed, best_etf = compute_filtered_pool_dispersion(context)
    if trigger:
        g.dispersion_mode = True
        g.dispersion_target = best_etf
        
        # Gap触发进阶对比
        if best_etf in g.growth_champions:
            g.advanced_trigger_count += 1
            if g.advanced_trigger_count >= g.advanced_trigger_days_required:
                final_target = select_best_advanced_etf(context, best_etf)
            else:
                log.info(f"【进阶对比】连续触发第{g.advanced_trigger_count}天，需连续{g.advanced_trigger_days_required}天才启用")
                final_target = best_etf
        else:
            g.advanced_trigger_count = 0
            final_target = best_etf
        
        g.dispersion_target = final_target
        log.info(f"🚀 Gap触发全仓单只模式，目标：{final_target} {get_name(final_target)}")
        
        # 商品对冲机制
        if g.enable_commodity_bond_hedge and final_target in ['501018.XSHG', '161226.XSHE']:
            if g.enable_bond_soy_group:
                bond_champion = select_champion_in_group(context, g.group_bond_soy)
                if bond_champion:
                    g.dispersion_bond_hedge = bond_champion
                    log.info(f"【商品对冲】选择债券对冲标的：{bond_champion} {get_name(bond_champion)}")
                else:
                    g.dispersion_bond_hedge = None
            else:
                g.dispersion_bond_hedge = None
        else:
            g.dispersion_bond_hedge = None
        
        # 卖出所有非目标持仓
        for sec in list(context.portfolio.positions.keys()):
            if sec != final_target and sec != g.dispersion_bond_hedge and context.portfolio.positions[sec].total_amount > 0:
                smart_order_target_value(sec, 0, context)
        g.group_champions = {}
        g.last_champions = {}
        return
    else:
        g.dispersion_mode = False
        g.dispersion_target = None

    # 正常分组冠军淘汰
    update_group_champions(context)
    current_etfs = [s for s in context.portfolio.positions if s in g.all_etfs]
    if not current_etfs:
        return
    new_champion_set = set(g.group_champions.values())
    to_sell = [s for s in current_etfs if s not in new_champion_set]
    for etf in to_sell:
        if context.portfolio.positions[etf].total_amount > 0:
            smart_order_target_value(etf, 0, context)
    enforce_bond_weight_limit(context, len(g.group_champions), sell_phase=True)


def enforce_bond_weight_limit(context, n_champions, sell_phase=False):
    """执行债券权重上限限制"""
    if n_champions == 4:
        max_weight = g.max_bond_soy_weight_4
    elif n_champions == 3:
        max_weight = g.max_bond_soy_weight_3
    elif n_champions == 2:
        max_weight = g.max_bond_soy_weight_2
    else:
        return

    total_val = context.portfolio.total_value
    if total_val <= 0:
        return

    bond_etfs = [etf for etf in g.group_bond_soy if etf in context.portfolio.positions]
    bond_value = 0.0
    for etf in bond_etfs:
        pos = context.portfolio.positions[etf]
        if pos.total_amount > 0:
            bond_value += pos.total_amount * pos.price
    bond_weight = bond_value / total_val

    if bond_weight > max_weight:
        target_bond_value = total_val * max_weight
        excess_value = bond_value - target_bond_value
        for etf in bond_etfs:
            pos = context.portfolio.positions[etf]
            if pos.total_amount <= 0:
                continue
            current_val = pos.total_amount * pos.price
            sell_value = excess_value * (current_val / bond_value) if bond_value > 0 else 0
            if sell_value > g.min_money:
                new_target_val = current_val - sell_value
                smart_order_target_value(etf, new_target_val, context, skip_closeable_check=sell_phase)


def etf_buy_trade(context):
    """买入操作（14:40执行）"""
    # 全仓单只模式
    if g.dispersion_mode and g.dispersion_target is not None:
        target_etf = g.dispersion_target
        total_val = context.portfolio.total_value
        
        # 商品对冲模式
        if hasattr(g, 'dispersion_bond_hedge') and g.dispersion_bond_hedge:
            bond_etf = g.dispersion_bond_hedge
            commodity_val = total_val * g.commodity_hedge_commodity_weight
            bond_val = total_val * g.commodity_hedge_bond_weight
            
            pos = context.portfolio.positions.get(target_etf, None)
            current_val = (pos.total_amount * pos.price) if pos and pos.total_amount > 0 else 0
            diff_val = commodity_val - current_val
            if diff_val > g.min_money:
                smart_order_target_value(target_etf, commodity_val, context)
            
            pos = context.portfolio.positions.get(bond_etf, None)
            current_val = (pos.total_amount * pos.price) if pos and pos.total_amount > 0 else 0
            diff_val = bond_val - current_val
            if diff_val > g.min_money:
                smart_order_target_value(bond_etf, bond_val, context)
        else:
            pos = context.portfolio.positions.get(target_etf, None)
            current_val = (pos.total_amount * pos.price) if pos and pos.total_amount > 0 else 0
            diff_val = total_val - current_val
            if diff_val > g.min_money:
                smart_order_target_value(target_etf, total_val, context)
        
        g.dispersion_mode = False
        g.dispersion_target = None
        g.dispersion_bond_hedge = None
        return

    # 正常冠军模式
    if not g.group_champions:
        update_group_champions(context)
    target_weights = compute_target_weights(context)
    
    # ========== 黄金+国债+城投债同时持仓时的特殊处理 ==========
    # 当持仓标的为黄金与国债、城投债同时存在时，去除城投债和国债
    if target_weights:
        has_gold = g.GOLD_ETF in target_weights
        has_treasury = g.TREASURY_BOND_ETF in target_weights
        has_city_invest = g.CITY_INVEST_BOND_ETF in target_weights
        
        if has_gold and (has_treasury or has_city_invest):
            # 需要去除的债券
            bonds_to_remove = []
            if has_treasury:
                bonds_to_remove.append(g.TREASURY_BOND_ETF)
            if has_city_invest:
                bonds_to_remove.append(g.CITY_INVEST_BOND_ETF)
            
            log.info(f"【特殊处理】黄金与债券同时持仓，去除: {bonds_to_remove}")
            
            # 计算剩余权重总和
            remaining_weight = sum(w for etf, w in target_weights.items() 
                                  if etf not in bonds_to_remove)
            
            if remaining_weight > 0:
                # 重新计算剩余标的的权重
                new_weights = {}
                for etf, w in target_weights.items():
                    if etf not in bonds_to_remove:
                        new_weights[etf] = w / remaining_weight
                target_weights = new_weights
                
                # 卖出被去除的债券
                for bond_etf in bonds_to_remove:
                    if context.portfolio.positions.get(bond_etf) and context.portfolio.positions[bond_etf].total_amount > 0:
                        smart_order_target_value(bond_etf, 0, context)
                        log.info(f"【特殊处理】卖出 {bond_etf}")
    
    if not target_weights:
        for sec in list(context.portfolio.positions.keys()):
            if sec in g.all_etfs:
                smart_order_target_value(sec, 0, context)
        g.last_champions = {}
        return

    total_val = context.portfolio.total_value
    current_set = set(g.group_champions.values())
    last_set = set(g.last_champions.values()) if g.last_champions else set()
    champions_changed = (current_set != last_set)

    # 冠军变化时调仓
    if champions_changed:
        for etf in last_set - current_set:
            if context.portfolio.positions.get(etf) and context.portfolio.positions[etf].total_amount > 0:
                smart_order_target_value(etf, 0, context)
        total_val = context.portfolio.total_value
        for etf in current_set:
            target_val = total_val * target_weights.get(etf, 0.0)
            pos = context.portfolio.positions.get(etf)
            current_val = pos.total_amount * pos.price if pos and pos.total_amount > 0 else 0.0
            if current_val < target_val:
                diff_val = target_val - current_val
                price = g.data_cache.get_current_data()[etf].last_price
                if price > 0 and diff_val >= g.min_money:
                    target_amount = int(diff_val / price) // 100 * 100
                    if target_amount > 0:
                        order(etf, target_amount)
        g.last_champions = g.group_champions.copy()
        enforce_bond_weight_limit(context, len(g.group_champions))
        log.info(f"分组策略持仓: {list(g.group_champions.values())}")
        return

    # 冠军未变，偏离度调仓
    current_weights = {}
    for etf in g.all_etfs:
        if etf in context.portfolio.positions:
            pos = context.portfolio.positions[etf]
            if total_val > 0:
                current_weights[etf] = (pos.total_amount * pos.price) / total_val

    weighted_deviation = 0.0
    for e in set(target_weights) | set(current_weights):
        weighted_deviation += abs(target_weights.get(e, 0) - current_weights.get(e, 0))

    if weighted_deviation >= g.rebalance_threshold:
        for etf, w in target_weights.items():
            smart_order_target_value(etf, total_val * w, context)

        for sec in list(context.portfolio.positions.keys()):
            if sec in g.all_etfs and sec not in target_weights and context.portfolio.positions[sec].total_amount > 0:
                smart_order_target_value(sec, 0, context)

    g.last_champions = g.group_champions.copy()
    enforce_bond_weight_limit(context, len(g.group_champions))
    log.info(f"分组策略持仓: {list(target_weights.keys())}")
