# Clone from JoinQuant
# postId: efef8e6a4e4a7f1d6dba7c24ccc9dcc2
# backtestId: 66d30489de88b3bbf2030a5a0a2d8a40
# title: 多 ETF 轮动 + 自适应市场状态 + 严格风控的量化策略

# 克隆自聚宽文章：https://www.joinquant.com/post/69446
# 标题：五福 v3.4.1.1 14年310倍 快50%+多周期验证
# 作者：xiaoji2025

import numpy as np
import math
import pandas as pd
from jqdata import *
from datetime import datetime, date, timedelta

# ==================== 策略初始化 ====================
def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.0001,
        close_commission=0.0001,
        close_today_commission=0.0001,
        min_commission=5
    ), type="fund")

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')

    # ==================== 固定ETF池 ====================
    g.fixed_etf_pool = [
#大宗商品ETF：
        '518880.XSHG',  # (黄金ETF) [ETF]-成交额：54.60亿元-上市日期：2013-07-29
        '161226.XSHE',  # (国投白银LOF) [LOF]-成交额：21.54亿元-上市日期：2015-08-17
        '159980.XSHE',  # (有色ETF大成) [ETF]-成交额：23.57亿元-上市日期：2019-12-24
        '501018.XSHG',  # (南方原油ETF) [LOF]-成交额：1.34亿元-上市日期：2016-06-28
        '159985.XSHE',  # (豆粕ETF) [ETF]-成交额：0.67亿元
#海外ETF：       
        '513100.XSHG',  # (纳指ETF) [ETF]-成交额：4.24亿元-上市日期：2013-05-15
        '159509.XSHE',  # (纳指科技ETF景顺) [ETF]-成交额：5.65亿元-上市日期：2023-08-08
        '513290.XSHG',  # (纳指生物) [ETF]-成交额：1.28亿元-上市日期：2022-08-29        
        '513500.XSHG',  # (标普500) [ETF]-成交额：2.22亿元-上市日期：2014-01-15
        '159518.XSHE',  # (标普油气ETF嘉实) [ETF]-成交额：5.35亿元-上市日期：2023-11-15
        '159502.XSHE',  # (标普生物科技ETF嘉实) [ETF]-成交额：4.00亿元-上市日期：2024-01-10        
        '159529.XSHE',  # (标普消费ETF) [ETF]-成交额：2.25亿元-上市日期：2024-02-02
        '513400.XSHG',  # (道琼斯) [ETF]-成交额：1.09亿元-上市日期：2024-02-02
        '520830.XSHG',  # (沙特ETF) [ETF]-成交额：1.16亿元-上市日期：2024-07-16
        '513520.XSHG',  # (日经ETF) [ETF]-成交额：1.11亿元-上市日期：2019-06-25
        '513030.XSHG',  # (德国ETF) [ETF]-成交额：0.77亿元
#港股ETF：
        '513090.XSHG',  # (香港证券) [ETF]-成交额：68.32亿元-上市日期：2020-03-26
        '513180.XSHG',  # (恒指科技) [ETF]-成交额：61.72亿元-上市日期：2021-05-25
        '513120.XSHG',  # (HK创新药) [ETF]-成交额：48.95亿元-上市日期：2022-07-12
        '513330.XSHG',  # (恒生互联) [ETF]-成交额：37.01亿元-上市日期：2021-02-08
        '513750.XSHG',  # (港股非银) [ETF]-成交额：23.06亿元-上市日期：2023-11-27
        '159892.XSHE',  # (恒生医药ETF) [ETF]-成交额：12.25亿元-上市日期：2021-10-19
        '159605.XSHE',  # (中概互联ETF) [ETF]-成交额：5.14亿元-上市日期：2021-12-02
        '513190.XSHG',  # (H股金融) [ETF]-成交额：5.07亿元-上市日期：2023-10-11
        '510900.XSHG',  # (恒生中国) [ETF]-成交额：3.73亿元-上市日期：2012-10-22
        '513630.XSHG',  # (香港红利) [ETF]-成交额：3.69亿元-上市日期：2023-12-08
        '513920.XSHG',  # (港股通央企红利) [ETF]-成交额：3.11亿元-上市日期：2024-01-05
        '159323.XSHE',  # (港股通汽车ETF) [ETF]-成交额：2.02亿元-上市日期：2025-01-08
        '513970.XSHG',  # (恒生消费) [ETF]-成交额：1.25亿元-上市日期：2023-04-21
#指数ETF：        
        '510500.XSHG',  # (中证500ETF) [ETF]-成交额：263.30亿元-上市日期：2013-03-15
        '512100.XSHG',  # (中证1000ETF) [ETF]-成交额：32.30亿元-上市日期：2016-11-04
        '563300.XSHG',  # (中证2000) [ETF]-成交额：3.34亿元-上市日期：2023-09-14        
        '510300.XSHG',  # (沪深300ETF) [ETF]-成交额：253.91亿元-上市日期：2012-05-28
        '512050.XSHG',  # (A500E) [ETF]-成交额：151.68亿元-上市日期：2024-11-15        
        '510760.XSHG',  # (上证ETF) [ETF]-成交额：1.10亿元-上市日期：2020-09-09        
        '159915.XSHE',  # (创业板ETF易方达) [ETF]-成交额：129.05亿元-上市日期：2011-12-09
        '159949.XSHE',  # (创业板50ETF) [ETF]-成交额：15.23亿元-上市日期：2016-07-22
        '159967.XSHE',  # (创业板成长ETF) [ETF]-成交额：3.27亿元-上市日期：2019-07-15        
        '588080.XSHG',  # (科创板50) [ETF]-成交额：123.46亿元-上市日期：2020-11-16
        '588220.XSHG',  # (科创100) [ETF]-成交额：4.99亿元-上市日期：2023-09-15
        '511380.XSHG',  # (可转债ETF) [ETF]-成交额：165.76亿元-上市日期：2020-04-07
#行业ETF：
        '513310.XSHG',  # (中韩芯片) [ETF]-成交额：38.68亿元-上市日期：2022-12-22
        '588200.XSHG',  # (科创芯片) [ETF]-成交额：37.94亿元-上市日期：2022-10-26
        '159852.XSHE',  # (软件ETF) [ETF]-成交额：36.26亿元-上市日期：2021-02-09
        '512880.XSHG',  # (证券ETF) [ETF]-成交额：34.01亿元-上市日期：2016-08-08
        '159206.XSHE',  # (卫星ETF) [ETF]-成交额：32.60亿元-上市日期：2025-03-14
        '512400.XSHG',  # (有色金属ETF) [ETF]-成交额：31.27亿元-上市日期：2017-09-01
        '512980.XSHG',  # (传媒ETF) [ETF]-成交额：30.96亿元-上市日期：2018-01-19
        '159516.XSHE',  # (半导体设备ETF) [ETF]-成交额：28.21亿元-上市日期：2023-07-27
        '512480.XSHG',  # (半导体) [ETF]-成交额：16.29亿元-上市日期：2019-06-12
        '515880.XSHG',  # (通信ETF) [ETF]-成交额：13.46亿元-上市日期：2019-09-06
        '562500.XSHG',  # (机器人) [ETF]-成交额：12.92亿元-上市日期：2021-12-29
        '159218.XSHE',  # (卫星产业ETF) [ETF]-成交额：12.74亿元-上市日期：2025-05-22
        '159869.XSHE',  # (游戏ETF) [ETF]-成交额：12.42亿元-上市日期：2021-03-05
        '159870.XSHE',  # (化工ETF) [ETF]-成交额：12.30亿元-上市日期：2021-03-03
        '159326.XSHE',  # (电网设备ETF) [ETF]-成交额：12.02亿元-上市日期：2024-09-09
        '159851.XSHE',  # (金融科技ETF) [ETF]-成交额：11.79亿元-上市日期：2021-03-19
        '560860.XSHG',  # (工业有色) [ETF]-成交额：11.71亿元-上市日期：2023-03-13
        '159363.XSHE',  # (创业板人工智能ETF华宝) [ETF]-成交额：10.63亿元-上市日期：2024-12-16
        '588170.XSHG',  # (科创半导) [ETF]-成交额：10.28亿元-上市日期：2025-04-08
        '159755.XSHE',  # (电池ETF) [ETF]-成交额：10.02亿元-上市日期：2021-06-24
        '512170.XSHG',  # (医疗ETF) [ETF]-成交额：9.54亿元-上市日期：2019-06-17
        '512800.XSHG',  # (银行ETF) [ETF]-成交额：9.48亿元-上市日期：2017-08-03
        '159819.XSHE',  # (人工智能ETF易方达) [ETF]-成交额：9.40亿元-上市日期：2020-09-23
        '512710.XSHG',  # (军工龙头) [ETF]-成交额：9.39亿元-上市日期：2019-08-26
        '159638.XSHE',  # (高端装备ETF嘉实) [ETF]-成交额：8.92亿元-上市日期：2022-08-12
        '517520.XSHG',  # (黄金股) [ETF]-成交额：8.73亿元-上市日期：2023-11-01
        '515980.XSHG',  # (人工智能) [ETF]-成交额：8.73亿元-上市日期：2020-02-10
        '159995.XSHE',  # (芯片ETF) [ETF]-成交额：8.45亿元-上市日期：2020-02-10
        '159227.XSHE',  # (航空航天ETF) [ETF]-成交额：8.42亿元-上市日期：2025-05-16
        '512660.XSHG',  # (军工ETF) [ETF]-成交额：7.78亿元-上市日期：2016-08-08
        '512690.XSHG',  # (酒ETF) [ETF]-成交额：6.74亿元-上市日期：2019-05-06
        '516150.XSHG',  # (稀土基金) [ETF]-成交额：6.41亿元-上市日期：2021-03-17
        '512890.XSHG',  # (红利低波) [ETF]-成交额：6.03亿元-上市日期：2019-01-18
        '588790.XSHG',  # (科创智能) [ETF]-成交额：5.92亿元-上市日期：2025-01-09
        '159992.XSHE',  # (创新药ETF) [ETF]-成交额：5.63亿元-上市日期：2020-04-10
        '512070.XSHG',  # (证券保险) [ETF]-成交额：5.50亿元-上市日期：2014-07-18
        '562800.XSHG',  # (稀有金属) [ETF]-成交额：5.49亿元-上市日期：2021-09-27
        '512010.XSHG',  # (医药ETF) [ETF]-成交额：5.22亿元-上市日期：2013-10-28
        '515790.XSHG',  # (光伏ETF) [ETF]-成交额：4.95亿元-上市日期：2020-12-18
        '510880.XSHG',  # (红利ETF) [ETF]-成交额：4.90亿元-上市日期：2007-01-18
        '159928.XSHE',  # (消费ETF) [ETF]-成交额：4.71亿元-上市日期：2013-09-16
        '159883.XSHE',  # (医疗器械ETF) [ETF]-成交额：4.44亿元-上市日期：2021-04-30
        '159998.XSHE',  # (计算机ETF) [ETF]-成交额：3.93亿元-上市日期：2020-04-13
        '515220.XSHG',  # (煤炭ETF) [ETF]-成交额：3.92亿元-上市日期：2020-03-02
        '561980.XSHG',  # (芯片设备) [ETF]-成交额：3.89亿元-上市日期：2023-09-01
        '515400.XSHG',  # (大数据) [ETF]-成交额：3.54亿元-上市日期：2021-01-20
        '515120.XSHG',  # (创新药) [ETF]-成交额：3.54亿元-上市日期：2021-01-04
        '159566.XSHE',  # (储能电池ETF易方达) [ETF]-成交额：3.05亿元-上市日期：2024-02-08
        '515050.XSHG',  # (5GETF) [ETF]-成交额：3.04亿元-上市日期：2019-10-16
        '516510.XSHG',  # (云计算ETF) [ETF]-成交额：2.95亿元-上市日期：2021-04-07
        '159256.XSHE',  # (创业板软件ETF华夏) [ETF]-成交额：2.89亿元-上市日期：2025-08-04
        '159766.XSHE',  # (旅游ETF) [ETF]-成交额：2.57亿元-上市日期：2021-07-23
        '512200.XSHG',  # (地产ETF) [ETF]-成交额：2.53亿元-上市日期：2017-09-25
        '513350.XSHG',  # (油气ETF) [ETF]-成交额：2.48亿元-上市日期：2023-11-28
        '159583.XSHE',  # (通信设备ETF) [ETF]-成交额：2.47亿元-上市日期：2024-07-08
        '159732.XSHE',  # (消费电子ETF) [ETF]-成交额：2.39亿元-上市日期：2021-08-23
        '516160.XSHG',  # (新能源) [ETF]-成交额：2.26亿元-上市日期：2021-02-04
        '516520.XSHG',  # (智能驾驶) [ETF]-成交额：2.22亿元-上市日期：2021-03-01
        '562590.XSHG',  # (半导材料) [ETF]-成交额：1.94亿元-上市日期：2023-10-18
        '515030.XSHG',  # (新汽车) [ETF]-成交额：1.93亿元-上市日期：2020-03-04
        '512670.XSHG',  # (国防ETF) [ETF]-成交额：1.84亿元-上市日期：2019-08-01
        '561330.XSHG',  # (矿业ETF) [ETF]-成交额：1.81亿元-上市日期：2022-11-01
        '516190.XSHG',  # (文娱ETF) [ETF]-成交额：1.67亿元-上市日期：2021-09-17
        '159840.XSHE',  # (锂电池ETF工银) [ETF]-成交额：1.61亿元-上市日期：2021-08-20
        '159611.XSHE',  # (电力ETF) [ETF]-成交额：1.52亿元-上市日期：2022-01-07
        '159981.XSHE',  # (能源化工ETF) [ETF]-成交额：1.48亿元-上市日期：2020-01-17
        '159865.XSHE',  # (养殖ETF) [ETF]-成交额：1.40亿元-上市日期：2021-03-08
        '561360.XSHG',  # (石油ETF) [ETF]-成交额：1.36亿元-上市日期：2023-10-31
        '159667.XSHE',  # (工业母机ETF) [ETF]-成交额：1.32亿元-上市日期：2022-10-26
        '515170.XSHG',  # (食品饮料ETF) [ETF]-成交额：1.30亿元-上市日期：2021-01-13
        '513360.XSHG',  # (教育ETF) [ETF]-成交额：1.09亿元-上市日期：2021-06-17
        '159825.XSHE',  # (农业ETF) [ETF]-成交额：1.05亿元-上市日期：2020-12-29
        '515210.XSHG',  # (钢铁ETF) [ETF]-成交额：1.03亿元-上市日期：2020-03-02
    ]

    g.filtered_fixed_pool = []
    g.dynamic_etf_pool = []
    g.merged_etf_pool = []
    g.ranked_etfs_result = []
    g.target_etfs_list = []
    g.etf_names_dict = {}

    # ===== 名称/元数据缓存 =====
    g.all_etf_list_cache = []
    g.etf_meta_cache = {}
    g.last_etf_universe_refresh = None

    # ===== 行情缓存 =====
    g.risk_hist_cache = None
    g.risk_hist_cache_date = None
    g.current_data_cache = None
    g.current_data_cache_dt = None

    # ===== 溢价率缓存 =====
    g.etf_yesterday_close_batch = {}
    g.etf_yesterday_nav_batch = {}

    # ===== 止损缓存 =====
    g.cache_date = None
    g.yesterday_close_cache = {}
    g.stop_loss_triggered_today = False

    # ==================== 策略核心参数 ====================
    #set_benchmark("510300.XSHG")
    g.holdings_num = 1
    g.defensive_etf = "511880.XSHG"
    g.min_money = 10

    # ===== 动量参数 =====
    g.lookback_days = 25
    g.min_score_threshold = 0
    g.max_score_threshold = 5
    g.score_threshold_ratio = 0.9

    g.use_short_momentum_period = False
    g.short_momentum_lookback = 21
    g.short_momentum_min_score = 0
    g.short_momentum_max_score = 6

    # ===== 过滤开关 =====
    g.enable_r2_filter = True
    g.r2_threshold = 0.4

    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 1.8

    g.enable_loss_filter = True
    g.loss = 0.97

    g.enable_premium_filter = True
    g.max_premium_rate = 30

    # ==================== 改良后的滤波器参数 ====================
    # 正常期：慢滤波（EMA风格，原laplace思想）
    g.normal_filter_type = 'laplace'
    g.laplace_s_param = 0.05
    g.laplace_min_slope_pct = 0.0005     # 0.05%
    g.laplace_max_deviation_pct = 0.03   # 价格高于滤波线不超过3%

    # 震荡期：快滤波（高斯）
    g.range_filter_type = 'gaussian'
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope_pct = 0.0003    # 0.03%
    g.gaussian_max_deviation_pct = 0.02  # 价格高于滤波线不超过2%

    # ==================== 震荡期参数 ====================
    g.enable_range_bound_mode = True
    g.current_filter = 'laplace'
    g.risk_state = 'normal'
    g.lookback_high_low_days = 20
    g.risk_benchmark = '510300.XSHG'

    # 进入震荡期
    g.enable_bias_trigger = True
    g.bias_threshold = 0.08
    g.ma_period = 20

    g.enable_rsi_trigger = True
    g.rsi_overbought = 70
    g.rsi_pullback = 65
    g.previous_rsi = None
    g.enable_stop_loss_trigger = True

    # 退出震荡期
    g.enable_low_point_rise_trigger = True
    g.low_point_rise_threshold = 0.04
    g.enable_stable_signal_trigger = True
    g.drawdown_recovery = 0.02
    g.max_range_bound_days = 20
    g.stable_days = 0

    # 切换控制
    g.filter_switch_cooldown = 3
    g.last_switch_date = None
    g.range_bound_start_date = None
    g.range_bound_days_count = 0

    # 回撤监控
    g.previous_drawdown = None
    g.max_portfolio_value = 0
    g.drawdown_threshold = 0.03
    g.drawdown_records = []

    # 止损
    g.use_fixed_stop_loss = True
    g.fixedStopLossThreshold = 0.95

    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95

    # 流动性阈值
    g.avg_etf_money_threshold = None

    # 日志控制
    g.verbose_log = True

    # ===== 初始化ETF缓存 =====
    refresh_etf_universe_cache(context, force=True)

    # ==================== 定时任务 ====================
    run_weekly(morning_routine, 1, time='09:00')
    run_daily(afternoon_routine, time='13:10')
    run_daily(reset_daily_flags, time='15:10')
    run_daily(minute_level_stop_loss, time='every_bar')
    # run_daily(minute_level_pct_stop_loss, time='every_bar')

    log.info("【重构版策略】初始化完成")
    init_range_bound_status(context)

# ==================== 缓存工具 ====================
def refresh_etf_universe_cache(context, force=False):
    """ETF列表和名称缓存；默认按月更新一次"""
    today = context.current_dt.date()
    if (not force) and g.last_etf_universe_refresh is not None:
        if (today - g.last_etf_universe_refresh).days < 30:
            return

    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        if df_etf is not None and not df_etf.empty:
            g.all_etf_list_cache = df_etf.index.tolist()
            g.etf_names_dict = df_etf['display_name'].to_dict()
            g.last_etf_universe_refresh = today
            log.info(f"【ETF缓存刷新】共{len(g.all_etf_list_cache)}只ETF")
    except Exception as e:
        log.warning(f"【ETF缓存刷新失败】{e}")

def get_cached_current_data(context):
    now = context.current_dt
    if g.current_data_cache_dt != now:
        g.current_data_cache = get_current_data()
        g.current_data_cache_dt = now
    return g.current_data_cache

def get_risk_hist(context, extra_days=30):
    """缓存风险基准行情，供多个函数复用"""
    end_date = context.previous_date
    need_count = max(g.ma_period, g.lookback_high_low_days) + extra_days

    if g.risk_hist_cache_date == end_date and g.risk_hist_cache is not None:
        return g.risk_hist_cache

    try:
        df = get_price(
            g.risk_benchmark,
            end_date=end_date,
            count=need_count,
            frequency='daily',
            fields=['close', 'high', 'low'],
            panel=False
        )
        g.risk_hist_cache = df
        g.risk_hist_cache_date = end_date
        return df
    except Exception as e:
        log.warning(f"【风险基准缓存失败】{e}")
        return None

# ==================== 首次运行震荡期状态初始化 ====================
def init_range_bound_status(context):
    if not g.enable_range_bound_mode:
        return
    try:
        if context.previous_date is None:
            return

        df = get_risk_hist(context)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            return

        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]

        recent_high = np.max(high[-g.lookback_high_low_days:])
        recent_low = np.min(low[-g.lookback_high_low_days:])
        ma = np.mean(close[-g.ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        current_rsi = calculate_rsi(close, period=14)

        should_enter = False
        signals = []

        if g.enable_bias_trigger and bias > g.bias_threshold:
            should_enter = True
            signals.append(f"乖离率{bias:.2%}>{g.bias_threshold:.0%}")

        if g.enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback:
                should_enter = True
                signals.append(f"RSI超买回落{prev_rsi:.1f}->{current_rsi:.1f}")

        if should_enter:
            g.current_filter = 'range_bound'
            g.risk_state = 'range_bound'
            g.range_bound_start_date = context.previous_date
            g.range_bound_days_count = 0
            log.info(f"【首次运行】初始化进入震荡期：{' ; '.join(signals)}")
        else:
            g.current_filter = 'laplace'
            g.risk_state = 'normal'
            g.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            g.previous_rsi = current_rsi

    except Exception as e:
        log.warning(f"【首次运行震荡期初始化异常】{e}")

# ==================== 任务流水线 ====================
def morning_routine(context):
    log.info("▶️ 【晨间流水线】启动")
    refresh_etf_universe_cache(context, force=False)
    calculate_global_etf_threshold(context)
    update_sector_pool(context)
    filter_fixed_pool_by_volume(context)
    daily_merge_etf_pools(context)
    log.info("⏸️ 【晨间流水线】结束")

def afternoon_routine(context):
    log.info("▶️ 【午后流水线】启动")
    check_positions(context)
    monitor_drawdown(context)
    check_and_exit_range_bound_mode(context)
    check_and_enter_range_bound_mode(context)
    calculate_and_log_ranked_etfs(context)
    execute_sell_trades(context)
    execute_buy_trades(context)
    log.info("⏸️ 【午后流水线】结束")

def reset_daily_flags(context):
    log.info("🔄 【收盘重置】完成")
    if g.current_filter == 'range_bound' and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
        g.range_bound_days_count = max(0, len(trade_days) - 1)

# ==================== 持仓检查 ====================
def check_positions(context):
    current_data = get_cached_current_data(context)
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            if current_data[security].paused:
                log.info(f"⚠️ {security} {get_security_name(security)} 今日停牌")

def monitor_drawdown(context):
    try:
        current_value = context.portfolio.total_value
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value

        if g.max_portfolio_value > 0:
            current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
            if current_drawdown >= g.drawdown_threshold:
                g.drawdown_records.append({
                    'date': context.current_dt.strftime('%Y-%m-%d'),
                    'drawdown': current_drawdown,
                    'portfolio_value': current_value,
                    'max_value': g.max_portfolio_value,
                    'current_filter': g.current_filter,
                    'risk_state': g.risk_state
                })
                log.info(f"【回撤预警】回撤 {current_drawdown:.2%}")
    except Exception as e:
        log.warning(f"【回撤监控异常】{e}")

# ==================== 流动性阈值计算 ====================
def calculate_global_etf_threshold(context):
    try:
        etf_list = g.all_etf_list_cache if g.all_etf_list_cache else []
        if not etf_list:
            g.avg_etf_money_threshold = 10000000
            return

        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]

        df = get_price(
            security=etf_list,
            start_date=start_day,
            end_date=context.previous_date,
            frequency='daily',
            fields=['money'],
            panel=False,
            skip_paused=True
        )
        if df is None or df.empty:
            g.avg_etf_money_threshold = 10000000
            return

        daily_totals = df.groupby('time')['money'].sum()
        if len(daily_totals) < 3:
            g.avg_etf_money_threshold = 10000000
            return

        avg_total_money = daily_totals.mean()
        threshold = avg_total_money / 20000
        g.avg_etf_money_threshold = threshold
        log.info(f"【流动性阈值】{threshold/1e4:.0f}万元")
    except Exception as e:
        log.warning(f"【流动性阈值异常】{e}")
        g.avg_etf_money_threshold = 10000000

# ==================== 动态池更新 ====================
def update_sector_pool(context):
    """更新行业ETF动态池（回归原版逻辑的稳定修正版）"""
    log.info("【动态池更新】开始执行")

    if g.avg_etf_money_threshold is None:
        log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)

    # 基金公司名称列表
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

    # 噪音词列表（保留原版）
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)

    # 特别分组（保留原版）
    SPECIAL_GROUPS = sorted([
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创', '创成长'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True)},
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HS', 'H', '中概'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HS', 'H', '中概'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)

    # 排除关键词（先保留原版，不动）
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
        # 只加这一条安全修补：按日期取ETF universe
        df_etf = get_all_securities(['etf'], date=context.previous_date)
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"获取全市场ETF列表失败: {e}")
        g.dynamic_etf_pool = []
        return

    log.info(f"【动态池更新】全市场ETF总数: {len(etf_list)}只")

    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0

    # 分类ETF（尽量保持原版）
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

    log.info(f"【动态池更新】进入特别组: {len(special_etfs)}只")
    log.info(f"【动态池更新】进入普通组: {len(normal_etfs)}只")
    log.info(f"【动态池更新】排除ETF: {excluded_count}只")

    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold

    log.info(f"【动态池更新】流动性门槛: {dynamic_threshold/1e4:.0f}万元")

    def filter_by_liquidity(etf_codes, group_name):
        if not etf_codes:
            return pd.Series(dtype=float), 0
        try:
            price_data = get_price(
                etf_codes,
                end_date=end_date,
                count=TRADE_DAYS_COUNT,
                frequency='daily',
                fields=['money'],
                panel=False
            )
            if price_data is None or price_data.empty:
                log.warning(f"【动态池更新】{group_name} 获取成交额数据为空")
                return pd.Series(dtype=float), len(etf_codes)

            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            qualified_series = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
            filtered_out = len(etf_codes) - len(qualified_series)

            log.info(f"【动态池更新】{group_name} 流动性过滤: {len(etf_codes)} → {len(qualified_series)}")
            return qualified_series, filtered_out
        except Exception as e:
            log.warning(f"【动态池更新】{group_name} 流动性过滤异常: {e}")
            return pd.Series(dtype=float), len(etf_codes)

    normal_qualified, normal_filtered_out = filter_by_liquidity(normal_etfs, "普通组")
    special_qualified, special_filtered_out = filter_by_liquidity(special_etfs, "特别组")

    normal_sorted = normal_qualified.index.tolist()
    special_sorted = special_qualified.index.tolist()

    if not normal_sorted and not special_sorted:
        log.warning("【动态池更新】流动性过滤后普通组和特别组都为空")
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
    empty_cleaned_normal = 0
    for code in normal_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            money = normal_qualified[code]
            cleaned = clean_name(original_name, is_special=False)
            if cleaned == '':
                empty_cleaned_normal += 1
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
    empty_cleaned_special = 0
    for code in special_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified[code]
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                empty_cleaned_special += 1
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

    log.info(f"【动态池更新】普通组clean后为空名称: {empty_cleaned_normal}只")
    log.info(f"【动态池更新】特别组clean后为空名称: {empty_cleaned_special}只")
    log.info(f"【动态池更新】普通组行业键数量: {len(normal_industry_groups)}")
    log.info(f"【动态池更新】特别组行业键数量: {len(special_industry_groups)}")

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

    log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF")
    for item in top_100[:10]:
        log.info(f"  {item['code']} {item['original_name']} 日均成交额: {item['money']/1e8:.2f}亿")


# ==================== 固定池流动性过滤 ====================
def filter_fixed_pool_by_volume(context):
    if g.avg_etf_money_threshold is None:
        calculate_global_etf_threshold(context)

    if not g.fixed_etf_pool:
        g.filtered_fixed_pool = []
        return

    try:
        price_data = get_price(
            g.fixed_etf_pool,
            end_date=context.previous_date,
            count=3,
            frequency='daily',
            fields=['money'],
            panel=False
        )
        if price_data is None or price_data.empty:
            g.filtered_fixed_pool = g.fixed_etf_pool[:]
            return

        avg_daily_money = price_data.groupby('code')['money'].sum() / 3
        qualified = avg_daily_money[avg_daily_money > g.avg_etf_money_threshold]
        g.filtered_fixed_pool = qualified.index.tolist()
        log.info(f"【固定池过滤】{len(g.fixed_etf_pool)} -> {len(g.filtered_fixed_pool)}")
    except Exception as e:
        log.warning(f"【固定池过滤异常】{e}")
        g.filtered_fixed_pool = g.fixed_etf_pool[:]

# ==================== 合并ETF池 ====================
def daily_merge_etf_pools(context):
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    g.merged_etf_pool = merged
    log.info(f"【合并池】固定{len(g.filtered_fixed_pool)} + 动态{len(g.dynamic_etf_pool)} -> 合并{len(merged)}")

# ==================== 退出震荡期检查 ====================
def check_and_exit_range_bound_mode(context):
    if not g.enable_range_bound_mode:
        return
    if g.current_filter != 'range_bound':
        return

    try:
        df = get_risk_hist(context)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            return

        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]

        recent_high = np.max(high[-g.lookback_high_low_days:])
        recent_low = np.min(low[-g.lookback_high_low_days:])

        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        ma = np.mean(close[-g.ma_period:])
        current_rsi = calculate_rsi(close, period=14)

        recovery_signals = []

        if g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold:
            recovery_signals.append("低点反弹达标")

        if g.enable_stable_signal_trigger:
            stable_signal_count = 0
            if current_price > ma:
                stable_signal_count += 1
            if len(close) >= 2 and close[-1] > close[-2]:
                stable_signal_count += 1
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                stable_signal_count += 1
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                stable_signal_count += 1

            if current_drawdown < g.drawdown_recovery and stable_signal_count >= 2:
                g.stable_days += 1
            else:
                g.stable_days = 0

        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi

        range_bound_days = 0
        if g.range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = max(0, len(trade_days) - 1)

        low_point_rise_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_signal_condition = g.enable_stable_signal_trigger and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days

        if low_point_rise_condition or stable_signal_condition or force_condition:
            can_switch = True
            if g.last_switch_date is not None:
                td = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
                if len(td) - 1 < g.filter_switch_cooldown:
                    can_switch = False

            if can_switch:
                g.current_filter = 'laplace'
                g.risk_state = 'normal'
                g.last_switch_date = context.current_dt.date()
                g.range_bound_start_date = None
                g.range_bound_days_count = 0
                g.stable_days = 0
                log.info("🔔 【退出震荡期】切回正常期拉普拉斯滤波")
    except Exception as e:
        log.warning(f"【退出震荡期检查异常】{e}")

# ==================== 进入震荡期检查 ====================
def check_and_enter_range_bound_mode(context):
    if not g.enable_range_bound_mode:
        return
    if g.current_filter == 'range_bound':
        return

    can_switch = True
    if g.last_switch_date is not None:
        td = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
        if len(td) - 1 < g.filter_switch_cooldown:
            can_switch = False
    if not can_switch:
        return

    risk_signals = []

    try:
        df = get_risk_hist(context, extra_days=10)
        if df is not None and len(df) >= max(g.ma_period, g.lookback_high_low_days):
            close = df['close'].values
            current_price = close[-1]

            if g.enable_bias_trigger:
                ma = np.mean(close[-g.ma_period:])
                bias = (current_price - ma) / ma if ma > 0 else 0
                if bias > g.bias_threshold:
                    risk_signals.append("乖离率过大")

            if g.enable_rsi_trigger:
                current_rsi = calculate_rsi(close, period=14)
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = calculate_rsi(close[:-1], period=14)
                    if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                        risk_signals.append("RSI超买回落")
    except Exception as e:
        log.warning(f"【进入震荡期检查异常】{e}")

    if g.enable_stop_loss_trigger and g.stop_loss_triggered_today:
        risk_signals.append("今日触发止损")
        g.stop_loss_triggered_today = False

    if risk_signals:
        g.current_filter = 'range_bound'
        g.risk_state = 'range_bound'
        g.last_switch_date = context.current_dt.date()
        g.range_bound_start_date = context.current_dt.date()
        g.range_bound_days_count = 0
        g.stable_days = 0
        log.info(f"🔔 【进入震荡期】{' ; '.join(risk_signals)}")

# ==================== 动量得分计算 ====================
def calculate_and_log_ranked_etfs(context):
    if not g.merged_etf_pool:
        g.ranked_etfs_result = []
        return
    g.ranked_etfs_result = get_final_ranked_etfs(context)

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

# ==================== 改良滤波器 ====================
def laplace_filter_last_two(price, s=0.05):
    """只计算最后两个递推值"""
    n = len(price)
    if n == 0:
        return 0, 0
    if n == 1:
        return price[0], price[0]

    alpha = 1 - np.exp(-s)
    prev = price[0]
    prev_prev = price[0]

    for i in range(1, n):
        curr = alpha * price[i] + (1 - alpha) * prev
        prev_prev, prev = prev, curr

    return prev, prev_prev

def gaussian_filter_last_two(price, sigma=1.2):
    """只计算最后两个高斯平滑值"""
    n = len(price)
    if n == 0:
        return 0, 0
    if n == 1:
        return price[0], price[0]

    idx_1 = np.arange(n)
    weights_1 = np.exp(-((idx_1 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    weights_1 /= np.sum(weights_1)
    g1 = np.sum(price * weights_1)

    idx_2 = np.arange(n - 1)
    weights_2 = np.exp(-((idx_2 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    weights_2 /= np.sum(weights_2)
    g2 = np.sum(price[:-1] * weights_2)

    return g1, g2

def evaluate_dynamic_filter(price_series, current_price):
    """
    保留性能优化（只算最后两点），
    但通过条件恢复为原版口径：
    - 价格在滤波线上方
    - 绝对斜率 > 原阈值
    """
    if len(price_series) < 10:
        return 0, 0, 0, 0, False, g.current_filter

    if g.current_filter == 'laplace':
        f_now, f_prev = laplace_filter_last_two(price_series, s=g.laplace_s_param)
        slope_abs = f_now - f_prev
        slope_pct = (f_now / f_prev - 1) if f_prev > 0 else 0
        deviation_pct = (current_price / f_now - 1) if f_now > 0 else 0

        # 恢复原版逻辑：只看价格在线上方 + 绝对斜率阈值
        passed = (
            current_price > f_now and
            slope_abs > 0.002
        )
        return f_now, f_prev, slope_pct, deviation_pct, passed, 'laplace'

    else:
        f_now, f_prev = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
        slope_abs = f_now - f_prev
        slope_pct = (f_now / f_prev - 1) if f_prev > 0 else 0
        deviation_pct = (current_price / f_now - 1) if f_now > 0 else 0

        # 恢复原版逻辑
        passed = (
            current_price > f_now and
            slope_abs > 0.002
        )
        return f_now, f_prev, slope_pct, deviation_pct, passed, 'gaussian'


# ==================== 量比 ====================
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
    except:
        return None

# ==================== 溢价率计算 ====================
def calculate_premium_rate(etf, context):
    try:
        etf_price = g.etf_yesterday_close_batch.get(etf)
        if etf_price is None or pd.isna(etf_price):
            etf_price_df = get_price(etf, start_date=context.previous_date, end_date=context.previous_date, fields=['close'])
            if etf_price_df is None or len(etf_price_df) == 0:
                return None, False
            etf_price = etf_price_df['close'].iloc[-1]

        nav = g.etf_yesterday_nav_batch.get(etf)
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
    except:
        return None, True

# ==================== RSI ====================
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
    except:
        return None

# ==================== 单ETF指标计算 ====================
def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    try:
        price_series = np.append(hist_closes, current_price)
        if len(price_series) < max(g.lookback_days, g.short_momentum_lookback) * 0.8:
            return None

        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_series, g.lookback_days)
        if momentum_score is None:
            return None

        short_momentum_score, short_annualized_returns, short_r_squared = calculate_momentum_score(price_series, g.short_momentum_lookback)

        passed_momentum = (g.min_score_threshold <= momentum_score <= g.max_score_threshold)
        passed_short_momentum = (short_momentum_score is not None and g.short_momentum_min_score <= short_momentum_score <= g.short_momentum_max_score)

        volume_ratio = get_volume_ratio(hist_volumes, today_vol, context, g.volume_lookback)

        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False

        premium_rate, passed_premium = calculate_premium_rate(etf, context)

        filter_value, filter_prev, filter_slope_pct, filter_deviation_pct, passed_filter, filter_name = evaluate_dynamic_filter(
            price_series, current_price
        )

        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'short_momentum_score': short_momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'premium_rate': premium_rate,

            'passed_momentum': passed_momentum,
            'passed_short_momentum': passed_short_momentum,
            'passed_r2': r_squared > g.r2_threshold,
            'passed_volume': (volume_ratio is not None and volume_ratio < g.volume_threshold),
            'passed_loss': passed_loss_filter,
            'passed_premium': passed_premium,
            'passed_filter': passed_filter,

            'filter_name': filter_name,
            'filter_value': filter_value,
            'filter_prev': filter_prev,
            'filter_slope_pct': filter_slope_pct,
            'filter_deviation_pct': filter_deviation_pct,
        }
    except Exception:
        return None

# ==================== 过滤条件应用 ====================
def apply_filters(metrics_list):
    use_short_momentum = g.use_short_momentum_period
    steps = [
        ('原动量', lambda m: m['passed_momentum'], not use_short_momentum),
        ('短期动量', lambda m: m['passed_short_momentum'], use_short_momentum),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
        ('溢价率', lambda m: m['passed_premium'], g.enable_premium_filter),
        ('动态滤波', lambda m: m['passed_filter'], g.enable_range_bound_mode),
    ]
    filtered = metrics_list[:]
    for _, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered

# ==================== 主筛选函数 ====================
def get_final_ranked_etfs(context):
    etf_set = list(g.merged_etf_pool)
    if not etf_set:
        return []

    end_date = context.previous_date
    today = context.current_dt.date()
    current_data = get_cached_current_data(context)
    use_short_momentum = g.use_short_momentum_period

    lookback = max(g.lookback_days, g.short_momentum_lookback, g.volume_lookback) + 20
    safe_lookback = lookback + 20

    hist_df = get_price(
        etf_set,
        count=safe_lookback,
        end_date=end_date,
        frequency='1d',
        fields=['close', 'volume'],
        panel=False
    )
    today_vol_df = get_price(
        etf_set,
        start_date=today,
        end_date=context.current_dt,
        frequency='1m',
        fields=['volume'],
        panel=False,
        fill_paused=False
    )

    if hist_df is None or hist_df.empty:
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
        log.warning(f"【批量溢价率数据获取异常】{e}")

    today_vols = today_vol_df.groupby('code')['volume'].sum() if (today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)

    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')

    all_metrics = []
    seen = set()

    for etf in etf_set:
        try:
            if current_data[etf].paused:
                continue
            if etf not in close_pivot.columns:
                continue

            raw_closes = close_pivot[etf].values
            raw_volumes = volume_pivot[etf].values
            valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)

            hist_closes = raw_closes[valid_mask][-lookback:]
            hist_volumes = raw_volumes[valid_mask][-lookback:]

            if len(hist_closes) < max(g.lookback_days, g.short_momentum_lookback):
                continue

            etf_name = get_security_name(etf)
            current_price = current_data[etf].last_price
            today_vol = today_vols.get(etf, 0)

            metrics = calculate_all_metrics_for_etf(
                etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context
            )
            if metrics is None:
                continue
            if metrics['etf'] in seen:
                continue

            seen.add(metrics['etf'])
            all_metrics.append(metrics)
        except:
            continue

    if not all_metrics:
        return []

    for item in all_metrics:
        if pd.isna(item.get('momentum_score')):
            item['momentum_score'] = float('-inf')
        if pd.isna(item.get('short_momentum_score')):
            item['short_momentum_score'] = float('-inf')

    sort_key = 'short_momentum_score' if use_short_momentum else 'momentum_score'
    all_metrics.sort(key=lambda x: x.get(sort_key, float('-inf')), reverse=True)

    filtered_list = apply_filters(all_metrics)
    filtered_list.sort(key=lambda x: x.get(sort_key, float('-inf')), reverse=True)
    top_10 = filtered_list[:10]

    if not top_10:
        if g.verbose_log:
            log.info("【筛选结果】无符合条件ETF")
        return []

    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(sort_key, float('-inf'))
        score_threshold = reference_score * g.score_threshold_ratio
        candidate_pool = [item for item in top_10 if item.get(sort_key, float('-inf')) >= score_threshold]
    else:
        candidate_pool = top_10[:]

    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]

    if len(retained) >= g.holdings_num:
        final_result = sorted(retained, key=lambda x: x.get(sort_key, float('-inf')), reverse=True)[:g.holdings_num]
    else:
        need = g.holdings_num - len(retained)
        retained_codes = set(x['etf'] for x in retained)
        remaining_pool = [item for item in candidate_pool if item['etf'] not in retained_codes]
        final_result = retained + remaining_pool[:need]

    if final_result:
        best = final_result[0]
        log.info(
            f"【最终目标】{best['etf_name']}({best['etf']}) "
            f"score={best.get(sort_key, 0):.4f} "
            f"R2={best['r_squared']:.3f} "
            f"量比={best['volume_ratio'] if best['volume_ratio'] is not None else 'N/A'} "
            f"滤波={best['filter_name']} "
            f"斜率={best['filter_slope_pct']:.3%} "
            f"偏离={best['filter_deviation_pct']:.3%}"
        )

    return final_result

# ==================== 交易执行 ====================
def execute_sell_trades(context):
    ranked_etfs = g.ranked_etfs_result
    target_etfs = []

    if ranked_etfs:
        target_etfs = [m['etf'] for m in ranked_etfs[:g.holdings_num]]
    else:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
        else:
            target_etfs = []

    g.target_etfs_list = target_etfs
    target_set = set(target_etfs)

    for security, position in context.portfolio.positions.items():
        if position.total_amount > 0 and security not in target_set:
            smart_order_target_value(security, 0, context)

def execute_buy_trades(context):
    target_etfs = g.target_etfs_list
    if not target_etfs:
        return

    current_positions = {sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0}
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]

    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    if num_etfs_to_buy <= 0:
        return

    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    available_cash = context.portfolio.available_cash
    allocated_value_per_etf = available_cash // num_etfs_to_buy

    if allocated_value_per_etf < g.min_money:
        return

    for i, etf in enumerate(etfs_to_buy):
        target_value_for_this_etf = allocated_value_per_etf
        if i == len(etfs_to_buy) - 1 and context.portfolio.available_cash >= g.min_money:
            target_value_for_this_etf = context.portfolio.available_cash
        smart_order_target_value(etf, target_value_for_this_etf, context)

def smart_order_target_value(security, target_value, context):
    current_data = get_cached_current_data(context)
    cd = current_data[security]
    security_name = get_security_name(security)

    if cd.paused:
        return False
    if cd.last_price >= cd.high_limit:
        return False
    if cd.last_price <= cd.low_limit:
        return False

    current_price = cd.last_price
    if current_price <= 0:
        return False

    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount

    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.min_money:
        return False

    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount <= 0:
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    if amount_diff == 0:
        return False

    order_result = order(security, amount_diff)
    if order_result:
        if amount_diff > 0:
            log.info(f"📦 买入 {security} {security_name} 数量:{amount_diff}")
        else:
            log.info(f"📤 卖出 {security} {security_name} 数量:{abs(amount_diff)}")
        return True
    return False

# ==================== 分钟级止损 ====================
def minute_level_stop_loss(context):
    if not g.use_fixed_stop_loss:
        return

    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return

    current_data = get_cached_current_data(context)

    for security, position in list(context.portfolio.positions.items()):
        if position.total_amount <= 0:
            continue
        if position.closeable_amount <= 0:
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
            log.info(f"🚨 【固定止损】{security} {security_name} 亏损 {loss_percent:.2f}%")
            success = smart_order_target_value(security, 0, context)
            if success and g.enable_stop_loss_trigger:
                g.stop_loss_triggered_today = True

def minute_level_pct_stop_loss(context):
    if not g.use_pct_stop_loss:
        return

    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return

    current_data = get_cached_current_data(context)
    current_date = context.current_dt.date()

    if g.cache_date != current_date:
        g.yesterday_close_cache = {}
        g.cache_date = current_date

    for security, position in list(context.portfolio.positions.items()):
        if position.total_amount <= 0:
            continue
        if position.closeable_amount <= 0:
            continue

        yesterday_close = g.yesterday_close_cache.get(security)
        if yesterday_close is None:
            try:
                close_series = attribute_history(security, 1, '1d', ['close'], skip_paused=False)
                if len(close_series['close']) == 0:
                    continue
                yesterday_close = close_series['close'][-1]
                if yesterday_close <= 0:
                    continue
                g.yesterday_close_cache[security] = yesterday_close
            except:
                continue

        current_price = current_data[security].last_price
        if current_price <= 0:
            continue

        stop_price = yesterday_close * g.pct_stop_loss_threshold
        if current_price <= stop_price:
            success = smart_order_target_value(security, 0, context)
            if success and g.enable_stop_loss_trigger:
                g.stop_loss_triggered_today = True

# ==================== 辅助函数 ====================
def get_security_name(security):
    try:
        if security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except:
        return "未知名称"

def check_defensive_etf_available(context):
    current_data = get_cached_current_data(context)
    defensive_etf = g.defensive_etf
    cd = current_data[defensive_etf]
    if cd.paused:
        return False
    if cd.last_price >= cd.high_limit:
        return False
    if cd.last_price <= cd.low_limit:
        return False
    return True

def trade(context):
    pass
