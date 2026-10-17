# Clone from JoinQuant
# postId: 091e1822b2816a02153f9c91298c6134
# backtestId: 5ad1541b787a944d0fa708a16cc4e0d5
# title: 单吊还是分散？ETF轮动1至5只黄金分仓实测分享

# 克隆自聚宽文章：https://www.joinquant.com/post/68519
# 标题：【五福闹新春】v4.1-5年25倍-喂它吃了1400条数据
# 作者：烟花三月ETF

import numpy as np
import math
import pandas as pd
from jqdata import *
from datetime import datetime, date


# ==================== 函数定义 ====================
def initialize(context):
    """初始化策略（设置参数、全局变量、定时任务）"""
    set_option("avoid_future_data", True)       # 避免未来函数
    set_option("use_real_price", True)          # 使用真实价格
    
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")  # 设置滑点
    
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001, close_commission=0.0001, close_today_commission=0.0001, min_commission=5,), type="fund")  # 设置交易费用

    log.set_level('order', 'error')     # 降低日志级别
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    log.info("【五福闹新春】v4.1启动！")

    set_benchmark("510300.XSHG")        # 设置基准

    g.fixed_etf_pool = [                # 固定ETF池（原始列表）
        # 大宗商品ETF：
        '518880.XSHG', # (黄金ETF) [ETF]-成交额：54.60亿元-上市日期：2013-07-29
        '161226.XSHE', # (国投白银LOF) [LOF]-成交额：21.54亿元-上市日期：2015-08-17
        '159980.XSHE', # (有色ETF大成) [ETF]-成交额：23.57亿元-上市日期：2019-12-24
        '501018.XSHG', # (南方原油ETF) [LOF]-成交额：1.34亿元-上市日期：2016-06-28
        '159985.XSHE', # (豆粕ETF) [ETF]-成交额：0.67亿元
        # 港股ETF：
        '513090.XSHG', # (香港证券) [ETF]-成交额：68.32亿元-上市日期：2020-03-26
        '513180.XSHG', # (恒指科技) [ETF]-成交额：61.72亿元-上市日期：2021-05-25
        '513120.XSHG', # (HK创新药) [ETF]-成交额：48.95亿元-上市日期：2022-07-12
        '513330.XSHG', # (恒生互联) [ETF]-成交额：37.01亿元-上市日期：2021-02-08
        '513750.XSHG', # (港股非银) [ETF]-成交额：23.06亿元-上市日期：2023-11-27
        '159892.XSHE', # (恒生医药ETF) [ETF]-成交额：12.25亿元-上市日期：2021-10-19
        '159605.XSHE', # (中概互联ETF) [ETF]-成交额：5.14亿元-上市日期：2021-12-02
        '513190.XSHG', # (H股金融) [ETF]-成交额：5.07亿元-上市日期：2023-10-11
        '510900.XSHG', # (恒生中国) [ETF]-成交额：3.73亿元-上市日期：2012-10-22
        '513630.XSHG', # (香港红利) [ETF]-成交额：3.69亿元-上市日期：2023-12-08
        '513920.XSHG', # (港股通央企红利) [ETF]-成交额：3.11亿元-上市日期：2024-01-05
        '159323.XSHE', # (港股通汽车ETF) [ETF]-成交额：2.02亿元-上市日期：2025-01-08
        '513970.XSHG', # (恒生消费) [ETF]-成交额：1.25亿元-上市日期：2023-04-21
        # 指数ETF：
        '510500.XSHG', # (中证500ETF) [ETF]-成交额：263.30亿元-上市日期：2013-03-15
        '512100.XSHG', # (中证1000ETF) [ETF]-成交额：32.30亿元-上市日期：2016-11-04
        '563300.XSHG', # (中证2000) [ETF]-成交额：3.34亿元-上市日期：2023-09-14
        '510300.XSHG', # (沪深300ETF) [ETF]-成交额：253.91亿元-上市日期：2012-05-28
        '512050.XSHG', # (A500E) [ETF]-成交额：151.68亿元-上市日期：2024-11-15
        '510760.XSHG', # (上证ETF) [ETF]-成交额：1.10亿元-上市日期：2020-09-09
        '159915.XSHE', # (创业板ETF易方达) [ETF]-成交额：129.05亿元-上市日期：2011-12-09
        '159949.XSHE', # (创业板50ETF) [ETF]-成交额：15.23亿元-上市日期：2016-07-22
        '159967.XSHE', # (创业板成长ETF) [ETF]-成交额：3.27亿元-上市日期：2019-07-15
        '588080.XSHG', # (科创板50) [ETF]-成交额：123.46亿元-上市日期：2020-11-16
        '588220.XSHG', # (科创100) [ETF]-成交额：4.99亿元-上市日期：2023-09-15
        '511380.XSHG', # (可转债ETF) [ETF]-成交额：165.76亿元-上市日期：2020-04-07
        # 行业ETF：
        '513310.XSHG', # (中韩芯片) [ETF]-成交额：38.68亿元-上市日期：2022-12-22
        '588200.XSHG', # (科创芯片) [ETF]-成交额：37.94亿元-上市日期：2022-10-26
        '159852.XSHE', # (软件ETF) [ETF]-成交额：36.26亿元-上市日期：2021-02-09
        '512880.XSHG', # (证券ETF) [ETF]-成交额：34.01亿元-上市日期：2016-08-08
        '159206.XSHE', # (卫星ETF) [ETF]-成交额：32.60亿元-上市日期：2025-03-14
        '512400.XSHG', # (有色金属ETF) [ETF]-成交额：31.27亿元-上市日期：2017-09-01
        '512980.XSHG', # (传媒ETF) [ETF]-成交额：30.96亿元-上市日期：2018-01-19
        '159516.XSHE', # (半导体设备ETF) [ETF]-成交额：28.21亿元-上市日期：2023-07-27
        '512480.XSHG', # (半导体) [ETF]-成交额：16.29亿元-上市日期：2019-06-12
        '515880.XSHG', # (通信ETF) [ETF]-成交额：13.46亿元-上市日期：2019-09-06
        '562500.XSHG', # (机器人) [ETF]-成交额：12.92亿元-上市日期：2021-12-29
        '159218.XSHE', # (卫星产业ETF) [ETF]-成交额：12.74亿元-上市日期：2025-05-22
        '159869.XSHE', # (游戏ETF) [ETF]-成交额：12.42亿元-上市日期：2021-03-05
        '159870.XSHE', # (化工ETF) [ETF]-成交额：12.30亿元-上市日期：2021-03-03
        '159326.XSHE', # (电网设备ETF) [ETF]-成交额：12.02亿元-上市日期：2024-09-09
        '159851.XSHE', # (金融科技ETF) [ETF]-成交额：11.79亿元-上市日期：2021-03-19
        '560860.XSHG', # (工业有色) [ETF]-成交额：11.71亿元-上市日期：2023-03-13
        '159363.XSHE', # (创业板人工智能ETF华宝) [ETF]-成交额：10.63亿元-上市日期：2024-12-16
        '588170.XSHG', # (科创半导) [ETF]-成交额：10.28亿元-上市日期：2025-04-08
        '159755.XSHE', # (电池ETF) [ETF]-成交额：10.02亿元-上市日期：2021-06-24
        '512170.XSHG', # (医疗ETF) [ETF]-成交额：9.54亿元-上市日期：2019-06-17
        '512800.XSHG', # (银行ETF) [ETF]-成交额：9.48亿元-上市日期：2017-08-03
        '159819.XSHE', # (人工智能ETF易方达) [ETF]-成交额：9.40亿元-上市日期：2020-09-23
        '512710.XSHG', # (军工龙头) [ETF]-成交额：9.39亿元-上市日期：2019-08-26
        '159638.XSHE', # (高端装备ETF嘉实) [ETF]-成交额：8.92亿元-上市日期：2022-08-12
        '517520.XSHG', # (黄金股) [ETF]-成交额：8.73亿元-上市日期：2023-11-01
        '515980.XSHG', # (人工智能) [ETF]-成交额：8.73亿元-上市日期：2020-02-10
        '159995.XSHE', # (芯片ETF) [ETF]-成交额：8.45亿元-上市日期：2020-02-10
        '159227.XSHE', # (航空航天ETF) [ETF]-成交额：8.42亿元-上市日期：2025-05-16
        '512660.XSHG', # (军工ETF) [ETF]-成交额：7.78亿元-上市日期：2016-08-08
        '512690.XSHG', # (酒ETF) [ETF]-成交额：6.74亿元-上市日期：2019-05-06
        '516150.XSHG', # (稀土基金) [ETF]-成交额：6.41亿元-上市日期：2021-03-17
        '512890.XSHG', # (红利低波) [ETF]-成交额：6.03亿元-上市日期：2019-01-18
        '588790.XSHG', # (科创智能) [ETF]-成交额：5.92亿元-上市日期：2025-01-09
        '159992.XSHE', # (创新药ETF) [ETF]-成交额：5.63亿元-上市日期：2020-04-10
        '512070.XSHG', # (证券保险) [ETF]-成交额：5.50亿元-上市日期：2014-07-18
        '562800.XSHG', # (稀有金属) [ETF]-成交额：5.49亿元-上市日期：2021-09-27
        '512010.XSHG', # (医药ETF) [ETF]-成交额：5.22亿元-上市日期：2013-10-28
        '515790.XSHG', # (光伏ETF) [ETF]-成交额：4.95亿元-上市日期：2020-12-18
        '510880.XSHG', # (红利ETF) [ETF]-成交额：4.90亿元-上市日期：2007-01-18
        '159928.XSHE', # (消费ETF) [ETF]-成交额：4.71亿元-上市日期：2013-09-16
        '159883.XSHE', # (医疗器械ETF) [ETF]-成交额：4.44亿元-上市日期：2021-04-30
        '159998.XSHE', # (计算机ETF) [ETF]-成交额：3.93亿元-上市日期：2020-04-13
        '515220.XSHG', # (煤炭ETF) [ETF]-成交额：3.92亿元-上市日期：2020-03-02
        '561980.XSHG', # (芯片设备) [ETF]-成交额：3.89亿元-上市日期：2023-09-01
        '515400.XSHG', # (大数据) [ETF]-成交额：3.54亿元-上市日期：2021-01-20
        '515120.XSHG', # (创新药) [ETF]-成交额：3.54亿元-上市日期：2021-01-04
        '159566.XSHE', # (储能电池ETF易方达) [ETF]-成交额：3.05亿元-上市日期：2024-02-08
        '515050.XSHG', # (5GETF) [ETF]-成交额：3.04亿元-上市日期：2019-10-16
        '516510.XSHG', # (云计算ETF) [ETF]-成交额：2.95亿元-上市日期：2021-04-07
        '159256.XSHE', # (创业板软件ETF华夏) [ETF]-成交额：2.89亿元-上市日期：2025-08-04
        '159766.XSHE', # (旅游ETF) [ETF]-成交额：2.57亿元-上市日期：2021-07-23
        '512200.XSHG', # (地产ETF) [ETF]-成交额：2.53亿元-上市日期：2017-09-25
        '513350.XSHG', # (油气ETF) [ETF]-成交额：2.48亿元-上市日期：2023-11-28
        '159583.XSHE', # (通信设备ETF) [ETF]-成交额：2.47亿元-上市日期：2024-07-08
        '159732.XSHE', # (消费电子ETF) [ETF]-成交额：2.39亿元-上市日期：2021-08-23
        '516160.XSHG', # (新能源) [ETF]-成交额：2.26亿元-上市日期：2021-02-04
        '516520.XSHG', # (智能驾驶) [ETF]-成交额：2.22亿元-上市日期：2021-03-01
        '562590.XSHG', # (半导材料) [ETF]-成交额：1.94亿元-上市日期：2023-10-18
        '515030.XSHG', # (新汽车) [ETF]-成交额：1.93亿元-上市日期：2020-03-04
        '512670.XSHG', # (国防ETF) [ETF]-成交额：1.84亿元-上市日期：2019-08-01
        '561330.XSHG', # (矿业ETF) [ETF]-成交额：1.81亿元-上市日期：2022-11-01
        '516190.XSHG', # (文娱ETF) [ETF]-成交额：1.67亿元-上市日期：2021-09-17
        '159840.XSHE', # (锂电池ETF工银) [ETF]-成交额：1.61亿元-上市日期：2021-08-20
        '159611.XSHE', # (电力ETF) [ETF]-成交额：1.52亿元-上市日期：2022-01-07
        '159981.XSHE', # (能源化工ETF) [ETF]-成交额：1.48亿元-上市日期：2020-01-17
        '159865.XSHE', # (养殖ETF) [ETF]-成交额：1.40亿元-上市日期：2021-03-08
        '561360.XSHG', # (石油ETF) [ETF]-成交额：1.36亿元-上市日期：2023-10-31
        '159667.XSHE', # (工业母机ETF) [ETF]-成交额：1.32亿元-上市日期：2022-10-26
        '515170.XSHG', # (食品饮料ETF) [ETF]-成交额：1.30亿元-上市日期：2021-01-13
        '513360.XSHG', # (教育ETF) [ETF]-成交额：1.09亿元-上市日期：2021-06-17
        '159825.XSHE', # (农业ETF) [ETF]-成交额：1.05亿元-上市日期：2020-12-29
        '515210.XSHG', # (钢铁ETF) [ETF]-成交额：1.03亿元-上市日期：2020-03-02
        ]

    g.filtered_fixed_pool = []           # 过滤后的固定ETF池
    g.dynamic_etf_pool = []              # 动态ETF池（初始为空）
    g.merged_etf_pool = []               # 合并后的ETF池
    g.ranked_etfs_result = []            # 动量计算结果的ETF列表
    g.last_refresh_date = None           # 上次刷新日期
    
    # ========== 流动性阈值统一设置 ==========
    # 阈值模式控制（两个开关互斥，建议只开启一个）
    g.use_fixed_threshold = False        # 是否使用固定金额阈值（True=使用5000万固定值）
    g.fixed_threshold_value = 50000000 # 固定阈值金额
    g.use_dynamic_threshold = True       # 是否使用动态阈值（True=使用calculate_global_etf_threshold计算的动态值）
    
    # 根据模式设置初始阈值
    if g.use_fixed_threshold:
        g.avg_etf_money_threshold = g.fixed_threshold_value
        log.info(f"【流动性阈值模式】使用固定阈值: {g.avg_etf_money_threshold/1e4:.0f}万元")
    elif g.use_dynamic_threshold:
        # 动态模式：初始值先用1000万，等08:50计算后更新
        g.avg_etf_money_threshold = 5000000
        log.info("【流动性阈值模式】使用动态阈值（初始值500万，每天08:50更新）")
    else:
        g.avg_etf_money_threshold = 5000000
        log.info(f"【流动性阈值模式】使用默认阈值: {g.avg_etf_money_threshold/1e4:.0f}万元")

    g.holdings_num = 2                  # 持仓数量
    g.defensive_etf = "511880.XSHG"     # 防御型ETF
    g.safe_haven_etf = '511660.XSHG'    # 冷却期避险ETF
    g.min_money = 5000                  # 最小交易金额

    g.lookback_days = 25                # 动量计算回看天数
    g.min_score_threshold = 0           # 动量得分下限
    g.max_score_threshold = 5           # 动量得分上限

    g.use_short_momentum_filter = False # 是否启用短期动量过滤
    g.short_lookback_days = 10          # 短期动量回看天数
    g.short_momentum_threshold = 0.0    # 短期动量阈值

    g.enable_r2_filter = True           # 是否启用R²过滤
    g.r2_threshold = 0.4                # R²阈值

    g.enable_annualized_return_filter = False   # 是否启用年化收益过滤
    g.min_annualized_return = 1.0       # 年化收益阈值

    g.enable_ma_filter = False          # 是否启用均线过滤
    g.ma_filter_days = 20               # 均线周期

    g.enable_volume_check = True        # 是否启用成交量过滤
    g.volume_lookback = 5               # 成交量回看天数
    g.volume_threshold = 1.0            # 成交量比阈值

    g.enable_loss_filter = True         # 是否启用短期风控过滤
    g.loss = 0.97                       # 单日最大允许跌幅（1 - 0.97 = 3%）

    g.use_rsi_filter = False            # 是否启用RSI过滤
    g.rsi_period = 6                    # RSI周期
    g.rsi_lookback_days = 1             # RSI回看天数
    g.rsi_threshold = 98                 # RSI超买阈值

    g.use_fixed_stop_loss = True        # 是否启用固定比例止损
    g.fixedStopLossThreshold = 0.95     # 固定止损比例（5%）
    g.use_pct_stop_loss = False         # 是否启用当日跌幅止损
    g.pct_stop_loss_threshold = 0.95    # 当日跌幅止损比例
    g.use_atr_stop_loss = False         # 是否启用ATR动态止损
    g.atr_period = 14                   # ATR周期
    g.atr_multiplier = 2                # ATR倍数
    g.atr_trailing_stop = True          # 是否启用ATR跟踪止损
    g.atr_exclude_defensive = True      # ATR是否排除防御ETF

    g.sell_cooldown_enabled = False     # 是否启用卖出冷却期
    g.sell_cooldown_days = 3            # 冷却期天数
    g.cooldown_end_date = None          # 冷却期结束日期

    g.positions = {}                    # 记录目标持仓
    g.position_highs = {}               # 记录持仓最高价（用于ATR跟踪）
    g.position_stop_prices = {}         # 记录ATR止损价
    g.target_etfs_list = []             # 今日目标ETF列表

    # ========== 初始化时刷新 ==========
    # 刷新月度动态池（全市场选取）- 初始化运行
    g.dynamic_etf_pool = refresh_etf_pool(context, trigger_type="初始化运行")

    # ========== 定时任务 ==========
    # 每月第一个交易日开盘前刷新一次全市场池子
    run_monthly(monthly_refresh_etf_pool, monthday=1, time='08:55')

    # 每日任务（严格按照要求的时间顺序）
    run_daily(calculate_global_etf_threshold, time='08:50')  # 每天8:50更新全局阈值
    run_daily(check_positions, time='09:01')                 # 每天9:01盘前检查持仓
    run_daily(daily_refresh_filtered_dynamic_pool, time='09:02') # 每天9:02动态池流动性过滤
    run_daily(daily_refresh_filtered_fixed_pool, time='09:03')  # 每天9:03固定池流动性过滤
    run_daily(daily_merge_etf_pools, time='09:04')           # 每天9:04合并池

    # 交易时段任务
    run_daily(calculate_and_log_ranked_etfs, time='13:09:59')   # 计算动量得分
    run_daily(execute_sell_trades, time='13:10:00')             # 执行卖出
    run_daily(execute_buy_trades, time='13:11:00')              # 执行买入

    # 分钟级止损任务
    for hour in range(9, 15):
        for minute in range(0, 60):
            current_time = "%02d:%02d" % (hour, minute)
            if ('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57'):
                run_daily(minute_level_stop_loss, time=current_time)          # 固定比例止损
                run_daily(minute_level_pct_stop_loss, time=current_time)      # 当日跌幅止损
                run_daily(minute_level_atr_stop_loss, time=current_time)      # ATR动态止损
            
    log.info(f"""策略参数初始化完成:
=== 过滤条件 ===
- 流动性门槛: 近{LIQUIDITY_LOOKBACK_DAYS}日日均成交额 ≥ {g.avg_etf_money_threshold/10000:.0f}万元 (模式: {'固定' if g.use_fixed_threshold else '动态' if g.use_dynamic_threshold else '默认'})
- 动量得分过滤: {'启用' if (g.min_score_threshold > -1e9 or g.max_score_threshold < 1e9) else '禁用'} (阈值范围: [{g.min_score_threshold}, {g.max_score_threshold}])
- 短期动量过滤: {'启用' if g.use_short_momentum_filter else '禁用'} (周期: {g.short_lookback_days}天, 阈值 ≥ {g.short_momentum_threshold:.2f})
- R²过滤: {'启用' if g.enable_r2_filter else '禁用'} (阈值 > {g.r2_threshold:.3f})
- 年化收益率过滤: {'启用' if g.enable_annualized_return_filter else '禁用'} (阈值 ≥ {g.min_annualized_return:.2%})
- 均线过滤: {'启用' if g.enable_ma_filter else '禁用'} ({g.ma_filter_days}日均线)
- 成交量过滤: {'启用' if g.enable_volume_check else '禁用'} (近{g.volume_lookback}日均量比 < {g.volume_threshold:.2f})
- 短期风控过滤: {'启用' if g.enable_loss_filter else '禁用'} (近3日单日跌幅 < {1 - g.loss:.1%})
- RSI过滤: {'启用' if g.use_rsi_filter else '禁用'} (周期: {g.rsi_period}, 回看{g.rsi_lookback_days}日, 触发阈值 > {g.rsi_threshold})

=== 止损机制 ===
- 分钟级固定比例止损: {'启用' if g.use_fixed_stop_loss else '禁用'} (成本价 × {g.fixedStopLossThreshold:.2%})
- 分钟级当日跌幅止损: {'启用' if g.use_pct_stop_loss else '禁用'} (开盘价 × {g.pct_stop_loss_threshold:.2%})
- 分钟级ATR动态止损: {'启用' if g.use_atr_stop_loss else '禁用'} (ATR周期: {g.atr_period}, 倍数: {g.atr_multiplier}, 跟踪止损: {'是' if g.atr_trailing_stop else '否'})

=== 其他配置 ===
- 固定ETF池（原始）: {len(g.fixed_etf_pool)} 只ETF
- 固定ETF池（过滤后）: {len(g.filtered_fixed_pool)} 只ETF (流动性≥{g.avg_etf_money_threshold/10000:.0f}万)
- 动态ETF池: {len(g.dynamic_etf_pool)} 只ETF (动态更新，每月1号刷新)
- 动量计算周期: {g.lookback_days} 天
- 持仓数量: {g.holdings_num}
- 防御ETF: {g.defensive_etf}
- 冷却期避险ETF: {g.safe_haven_etf}
- 冷却期机制: {'启用' if g.sell_cooldown_enabled else '禁用'} (持续{g.sell_cooldown_days}个交易日)
""")

def apply_filters(metrics_list):
    """根据开关应用所有过滤条件"""
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('短期动量', lambda m: m['passed_short_mom'], g.use_short_momentum_filter),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
        ('年化收益率', lambda m: m['passed_annual_ret'], g.enable_annualized_return_filter), 
        ('均线', lambda m: m['passed_ma'], g.enable_ma_filter),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
        ('RSI', lambda m: m['passed_rsi'], g.use_rsi_filter),
    ]
    
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered

def check_positions(context):
    """盘前持仓检查"""
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 持仓检查: {security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")

LIQUIDITY_LOOKBACK_DAYS = 10   # 流动性计算回看天数（10日）

def get_daily_money(etf_code, days=LIQUIDITY_LOOKBACK_DAYS):
    """获取ETF的日均成交额（默认10日）"""
    try:
        hist = attribute_history(etf_code, days, '1d', ['money'])
        if hist.empty:
            return 0
        return hist['money'].mean()
    except:
        return 0

def calculate_global_etf_threshold(context):
    """计算全市场ETF流动性阈值 - 根据模式开关决定是否应用"""
    log.info("★" * 80)    
    log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    
    # 如果不使用动态阈值，直接返回
    if not g.use_dynamic_threshold:
        log.info(f"【全局阈值更新】动态阈值模式已关闭，保持当前阈值: {g.avg_etf_money_threshold/1e4:.0f}万元")
        return
    
    try:
        # 获取所有基金
        all_funds = get_all_securities(['fund'], date=context.current_dt).index.tolist()
        
        # 筛选真正的ETF（只保留subtype为'etf'的）
        etf_list = []
        for code in all_funds:
            try:
                info = get_security_info(code)
                if info and info.subtype == 'etf':  # 只保留ETF
                    etf_list.append(code)
            except Exception:
                continue
        
        if not etf_list:
            log.warning("未找到任何场内ETF")
            return
        
        log.info(f"全市场ETF总数: {len(etf_list)} 只")
        
        # 获取最近3个交易日
        current_date = context.current_dt.date()
        trade_days = get_trade_days(end_date=current_date - pd.Timedelta(days=1), count=3)
        
        if len(trade_days) < 3:
            log.warning("无法获取3个完整交易日，保持当前阈值")
            return
            
        daily_totals = []
        valid_days = 0
        for day in trade_days:
            try:
                df = get_price(
                    security=etf_list,
                    start_date=day,
                    end_date=day,
                    frequency='daily',
                    fields=['money'],
                    panel=False,
                    skip_paused=True
                )
                
                if df is not None and not df.empty:
                    daily_total = df['money'].sum()
                    daily_totals.append(daily_total)
                    log.info(f"{day} 全市场ETF总成交额: {daily_total/1e8:.2f}亿元 ({df['money'].count()}只ETF有成交)")
                    valid_days += 1
            except Exception as e:
                log.warning(f"计算 {day} 成交额失败: {e}")
                
        if valid_days < 3:
            log.warning(f"仅有 {valid_days} 个有效交易日，保持当前阈值")
            return
            
        avg_total_money = sum(daily_totals) / len(daily_totals)
        threshold = avg_total_money / 20000
        g.avg_etf_money_threshold = threshold
        
        log.info(
            f"【全局阈值更新完成】近3日全市场ETF日均总成交额 = {avg_total_money/1e8:.2f}亿元，"
            f"日均总成交/20000 = {threshold/1e4:.0f}万元 ({threshold:,.0f}元)"
        )
        
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}")

# ==================== 核心去重逻辑常量 ====================
FUND_COMPANIES = sorted(list(set([
    '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华',
    '南方', '汇添富', '国泰', '平安', '银华', '天弘', '建信', '工银',
    '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
    '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银',
    '东方红', '财通', '华商', '国联', '永赢', '金鹰', '德邦', '创金合信',
    '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海', '华润元大', '大成',
    '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城',
    '中金', '浙商证券', '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航',
    '中融', '中邮', '中庚', '中信保诚', '中信建投', '中银国际', '中银证券', '九泰',
    '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林', '国联安', '国金',
    '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛',
    '长江证券', '鹏扬'
])), key=len, reverse=True)

NOISE_WORDS = sorted(list(set([
    '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C',
    'C类', 'CS', 'DB', 'E', 'E类', 'ESG', 'ETF', 'ETF基金',
    'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF',
    'LOF基金', 'LOF联接', 'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH',
    'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
    '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企',
    '民营', '国企', '央企', '全指', '上市开放式', '指基', '指增', '指数',
    '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强', '增强ETF'
])), key=len, reverse=True)

INDEX_SYNONYMS = {
    # ========== 债券类 ==========
    '短融': ['短融'],
    '可转债': ['可转债', '转债', '双债'],
    '利率债': ['利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债'],
    '信用债': ['信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债'],
    '科创债': ['科创债', '科债', '科创AAA', '科债AAA'],

    # ========== 商品类 ==========
    '黄金': ['黄金', '金', '上海金', '黄金9999', '金ETF'],
    '黄金股': ['黄金股', '黄金股票'],
    '白银': ['白银'],
    '豆粕': ['豆粕'],
    '能源商品': ['原油', '石油', '油气', '能源化工', '华宝油气', '嘉实原油', '南方原油', '全球油气能源'],
    '商品': ['商品', '抗通胀', '大宗商品', '国泰商品', '中信保诚商品'],

    # ========== 宽基指数类 ==========
    'A500': ['A500', '中证A500', '红利A500', '增强A500'],
    '沪深300': ['沪深300', 'HS300', '300增', '300增强', '300质量', '300ESG', '300指增', '300价值E', '300ETF', '300增ETF', '300ETF增'],
    '中证500': ['中证500', 'ZZ500', '500指增', '500质量', '500价值', '500低波', '500W', '500ETF'],
    '中证1000': ['中证1000', 'ZZ1000', '1000ETF', '1000基金', '增强1000', '1000指增', '1000增强'],
    '中证2000': ['中证2000', 'ZZ2000', '国证2000', '2000ETF', '2000基金', '2000指数'],
    '中证800': ['中证800', 'ZZ800', '800ETF', '800'],
    '上证50': ['上证50', 'SZ50', '上50', '沪50', 'SH50', '上50增强'],
    '上证180': ['上证180', '180', '180ETF', '180基金', '180E', '180指数', '上180'],
    '上证综指': ['上证综指', '综指', '上证综合', '综指ETF', '上证综E', '上证'],
    '深证100': ['深证100', '深100', '深100ETF'],
    '深证50': ['深证50', '深50ETF'],
    '深证成指': ['深证成指', '深成指', '深成ETF', '深成长', '深成'],
    'A50': ['A50', '中证A50', 'MSCIA50', '中国A50', 'A50ETF', 'A50基金', 'A50龙头', 'A50中证', 'A50增'],
    'A100': ['A100', '中证A100', 'A100ETF', 'A100指数', 'A100基金'],
    'A股': ['A股', 'MSCIA股'],
    '500': ['500', 'ZZ500ETF', '500ETF', '500指增', '500质量', '500W', '增强500', '国联500', '500价值', '500低波', 'AH500ETF', 'HGS500E', 'HGS500', '500ETF增强'],
    '1000': ['1000', '1000ETF', '1000基金', 'ZZ1000', '增强1000', '1000指增', '1000增强'],
    '300': ['300', '300ETF', '300增强', '300质量', '300永赢', '300中金', '300ESG', '300指增', '300价值E', '300ETF增强', 'AH300ETF', '民企300'],
    '50': ['50', '50ETF', 'SZ50ETF', '万家50', '基本面50', '央企50'],
    '2000': ['2000', 'ZZ2000', '2000ETF', '2000指数', '2000基金'],

    # ========== 科创系列 ==========
    '科创50': ['科创50', '科50', '科创板50', '科创50E', '科创50指', '科创50基', '科创50增'],
    '科创100': ['科创100', '科100', '科创100F', '科创100C', '科创100S', '科创100E', '科创100Z', '科100增', '科100FG'],
    '科创200': ['科创200', '科200', '科创200E', '科创200F', '科200GT', '科200E', '科200GF', '科200FG'],
    '科创综指': ['科创综指', '科创综合', '科创全指', '综指科创', '科创综', '科创综E', '科创综Z'],
    '科创芯片': ['科创芯片', '科创半导', '科芯片', 'KC芯片', 'KC半导体', '科创芯50', '科创芯', '科创芯易', '科创芯基', '科芯片GF', '芯设计KC', '科创芯片设计', '科半导体', '科芯设计'],
    '科创人工智能': ['科创人工智能', '科创AI', 'AI科创', '科创智能', '科创板AI', '科创AI指', '科创AITF', 'AI科创CS', 'AI科创指', 'KCAI', '科AI'],
    '科创新能源': ['科创新能', '新能科创'],
    '科创医药': ['科创医药', '科创新药', '科创生物', '科创药', 'KC医药'],
    '科创信息技术': ['科创信息', '信息科创'],
    '科创材料': ['科创材料', '科创新材', '科创材基'],
    '科创成长': ['科创成长', '成长科创'],
    '科创价值': ['科创价值', 'KC价值'],
    '科创增强': ['科创增强', '科创增', '科创增指'],
    '科创机械': ['科创机械'],
    '科创': ['科创', '科创板', '科创指基', '科创ETF', '上证科创', '科创综', '科综', '科创龙头', '科创五零', '科创板基', '科创红土', '科创大成', '科创富国', '科创广发', '中银科创', 'KC'],

    # ========== 双创系列 ==========
    '双创': ['双创', '科创创业', '创创', '双创ETF', '双创基金'],
    '双创50': ['双创50', '双创五零'],
    '双创人工智能': ['双创AI', 'AI双创', '科创创业人工智能'],
    '双创龙头': ['双创龙头'],

    # ========== 创业板系列 ==========
    '创业板': ['创业板', '创业大盘', '创业板增强'],
    '创业板50': ['创业板50', '创50'],
    '创业板200': ['创业板200', '创200'],
    '创业板成长': ['创业板成长'],
    '创业板人工智能': ['创业板人工智能'],
    '创业板新能源': ['创业板新能源'],
    '创业板软件': ['创业板软件'],
    '创业板综': ['创业板综', '创业综指', '创业板综增强'],

    # ========== 行业主题类 ==========
    '芯片半导体': ['芯片', '半导体', '集成电路', '芯片设计', '芯片设备', '半导体材料', '半导材料', '芯设计', '芯设计GF', '芯片科创', '半导体龙头'],
    '半导体设备': ['半导体设备', '半导设备'],
    '中韩芯片': ['全球芯片', '中韩芯片'],
    '军工': ['军工', '国防', '空天军工', '军工龙头', '中证军工', '国防军工', '军工基金'],
    '航空航天': ['航天', '航空', '航空航天', '通航', '通用航空', '航空通用'],
    '有色': ['有色', '有色金属', '工业有色', '资源', '稀有金属', '稀金属', '国投资源', '有色矿业', '油气资源', '稀土', '稀土基金', '稀土ETF'],
    '矿业': ['矿业'],
    '化工': ['化工', '化工50', '化工龙头'],
    '人工智能': ['人工智能', 'AI', 'AI智能', 'AI50', 'AIETF'],
    '机器人': ['机器人', '机器人50', '机器人ZS', '机器人YH', '机器人WJ'],
    '工业母机': ['工业母机', '机床'],
    '汽车': ['汽车', '新能源车', '新能车', '智能汽车', '智能驾驶', '电动车', '电动汽车', '汽车零部件', '汽车零件', '新汽车', '智能网联汽车'],
    '通信5G': ['通信', '5G', '电信', '通信设备', '电信50', '电信主题'],
    '金融科技': ['金融科技', '金融科'],
    '计算机软件': ['计算机', '软件', '信创', '数字经济', '云计算', '大数据', 'VR', '数据', '数字', '云50', '工业软件', '软件开发', '软件30', '软件指数', '数据产业', '国企数字', '云计算50'],
    '消费电子': ['消费电子', '消电', '电子龙头', '消电50'],
    '光伏': ['光伏', '光伏产业', '中证光伏', '光伏50', '光伏龙头', '光伏基金', '光伏E'],
    '电池': ['电池', '锂电池', '储能', '储能电池', '电池龙头', '电池基金'],
    '新能源': ['新能源', '碳中和', '环保', '绿电', '新能源80', '新能源50', '新能源E', '碳中和E', '碳中和基', '新能源BS', '新经济'],
    '电力': ['电力', '电网', '电网设备', '绿色电力', '电力指数', '电力基金', '电力指基', '绿电50'],
    '创新药': ['创新药', '创新药50', '创新药企', '创新药基', '创新药WJ'],
    '医疗器械': ['医疗器械', '医疗设备'],
    '医疗': ['医疗', '医药', '医疗创新', '标普医疗保健', '医药50', '医药100', '中医药', '医药龙头', '医药基金', '医疗50'],
    '生物医药': ['生物医药', '生物科技', '标普生物科技', '恒生生物科技', '生物ETF', '生科ETF'],
    '中药': ['中药'],
    '白酒': ['白酒', '酒'],
    '食品饮料': ['食品', '饮料'],
    '消费': ['消费', '家电', '在线消费', '线上消费', '品牌消费', '智能消费', '可选消费', '美国消费', '消费增强', '消费龙头', '消费主题', '家居家电'],
    '旅游酒店': ['旅游', '酒店'],
    '农业': ['农业', '养殖', '畜牧', '粮食', '农牧', '现代农业', '畜牧养殖', '农牧渔'],
    '证券': ['证券', '券商', '证券保险', '证券指数', '证券基金', '证券龙头', '上证券商', '证券E', '证券全指', '证券行业', '证券公司', '证券先锋'],
    '银行': ['银行', '银行指基', '银行股基', '银行基金', '银行指数', '银行优选'],
    '保险': ['保险', '保险证券', '保险主题'],
    '金融': ['金融', '科技金融', '金融地产', '金融科'],
    '地产': ['地产', '房地产', '华夏地产', '房地产银华'],
    '建材': ['建材'],
    '钢铁': ['钢铁'],
    '煤炭': ['煤炭', '煤炭龙头', '煤炭等权'],
    '基建': ['基建', '基建50'],
    '机械': ['机械', '工程机械', '华夏机械', '富国机械'],
    '高端装备': ['高端装备', '高端制造'],
    '专精特新': ['专精特新'],
    '交通运输': ['交通运输', '物流', '物流快递'],
    '教育': ['教育'],
    '公用事业': ['公用事业'],
    '石化': ['石化'],
    '船舶': ['船舶'],
    '卫星': ['卫星', '卫星产业'],
    '游戏': ['游戏', '游戏动漫', '游戏传媒'],
    '传媒': ['传媒', '影视', '文娱'],
    '科技': ['科技', '科技30', '科技50', '科技100', '科技龙头', '科技央企', '龙头科技', '科技引领', '海外科技', '央企科技', '交银科技', '创科技'],
    '电子': ['电子', '电子50', '电子龙头'],
    '智能车': ['智能车', '智能电车'],
    '工业互联网': ['工业互联网'],
    '物联网': ['物联网', '物联网50'],
    'TMT': ['TMT', 'TMT50'],
    '稀土': ['稀土', '稀土基金', '稀土ETF'],
    '能源': ['能源', '能源ETF', '央企能源'],
    '信息技术': ['信息技术', '信息技术ETF'],
    '材料': ['材料', '材料ETF'],
    '共赢': ['共赢', '共赢ETF'],
    '新经济': ['新经济', '新经济ETF'],
    'MSI': ['MSI', 'MSCI', 'MSI易基'],
    '央企': ['央企', '央', '央创', '央调', '央企创新', '央企改革', '央企分红', '央企回报', '央企ESG', '央企科创', '央企40', '央企能源', '央企ETF'],
    '国企': ['国企', '国企方达', '国企富国', '中国国企'],
    '民企': ['民企', '民企300'],
    'ESG': ['ESG', 'ESG180', 'ESG300'],

    # ========== 港股系列 ==========
    '恒生科技': ['恒生科技', '港股科技', '恒指科技', 'HKC科技', 'HK科技', '港科技', '科技HK', '香港科技', '恒科', '港科', 'HS科技', 'H科技', '港科技30', '恒科技'],
    '恒生互联网': ['恒生互联网', '港股互联网', '恒生互联', '港股通互联网', '香港互联', 'HK互联', '互联港股', '互联网30', '互联网HK', '港美互联网'],
    '恒生医药': ['恒生医药', '恒生医疗', '香港医药', '港股医药', '港股医疗', '港股通医疗'],
    '恒生消费': ['恒生消费', '港股消费', 'H股消费', '香港消费', '港股通消费', 'HK消费50', 'HK消费'],
    '恒生红利': ['恒生红利', '港股红利', '香港红利', '港股分红', '港股高股息', '港红利', '港红利CS', '港红利指'],
    '港股金融': ['港股金融', 'H股金融', '香港证券', '港股非银', '香港银行'],
    '港股创新药': ['港股创新药', '香港创新药', 'HK创新药', '港股新药', '恒生新药', '港股通创新药', '港股通药'],
    '港股汽车': ['港股汽车', '港股车50', '香港汽车'],
    '港股信息技术': ['港股信息技术'],
    '港股生物': ['港股生物'],
    '港股通': ['港股通', '恒指港股通', '港股100', '港股通科', '港股通综', '港股', '港股国企'],
    '恒生指数': ['恒生', '恒指', '香港30', '恒生中国企业', '恒生国企', '恒生中国'],
    '中概互联': ['中概互联', '中概互联网'],
    '香港大盘': ['香港大盘'],
    '香港中小': ['香港中小'],

    # ========== 美国市场系列 ==========
    '纳斯达克综合': ['纳斯达克', '纳指', '纳指ETF', '纳指指数', '纳指基金', '纳斯达克ETF'],
    '纳斯达克科技': ['纳指科技'],
    '纳斯达克100': ['纳指100', '纳斯达克100', '纳斯达克100ETF', '纳斯达克100LOF'],
    '纳斯达克生物': ['纳指生物'],
    '标普500': ['标普500', '标普', '标普ETF', '标普500LOF', '标普500ETF'],
    '标普油气': ['标普油气'],
    '标普信息科技': ['标普信息科技'],
    '标普红利': ['标普红利'],
    '道琼斯': ['道琼斯'],
    '美国50': ['美国50'],

    # ========== 其他海外市场 ==========
    '日经225': ['日经', '日经225', '225', '东证'],
    '德国': ['德国'],
    '法国': ['法国'],
    '沙特': ['沙特'],
    '巴西': ['巴西'],
    '印度': ['印度'],
    '东南亚': ['东南亚'],
    '亚太精选': ['亚太精选', '亚太', '新兴亚洲'],

    # ========== 策略指数类 ==========
    '红利': ['红利', '高股息', '红利低波', '红利质量', '全指红利', '红利央企', '红利香港', '红利国泰', '红利TK', '红利价值', '红利优选', '红利国企', '红利添富', '上证红利', '红利DB', '红利国有'],
    '价值': ['价值', '国信价值'],
    '成长': ['成长', '300成长', '科技成长', '1000成长'],
    '自由现金流': ['自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流'],
    '质量': ['质量'],

    # ========== 货币类 ==========
    '货币类': ['货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数', '全指现金', '现金全指', '招商快线', '汇添富快钱'],

    # ========== 主动基金类 ==========
    '主动基金': ['合宜', '天惠', '内需', '合润', '趋势', '鼎益', '瑞合', '社会责任定开', '红土创新', '智胜先锋', '商业模式', '行业优选', '福鑫', '鼎越', '磐泰', '易基未来', '南方香港', '博时主题', '创新', '回报', '之江凤凰', '广发小盘', '万家行业优选', '央企创新', '创新央企', '央企回报', 'G60创新', '中欧创新', '鹏华创新', '景顺鼎益', '兴全趋势', '兴全合润', '兴全商业模式', '兴全合宜'],
}

def monthly_refresh_etf_pool(context):
    """每月1号刷新动态ETF池"""
    g.dynamic_etf_pool = refresh_etf_pool(context, trigger_type="每月1号更新运行")

def refresh_etf_pool(context, trigger_type="初始化运行"):
    """
    月度动态更新 ETF 池：从全市场选取符合条件并去重后的标的
    未匹配到任何分组的ETF归为"未分组"，取成交额前5名
    """
    log.info(f"★【月度动态ETF池刷新】{trigger_type}、开始执行★")
    log.info(f"★【刷新时间】{context.current_dt}★")
    log.info(f"★【流动性门槛】近{LIQUIDITY_LOOKBACK_DAYS}日日均成交额 ≥ {g.avg_etf_money_threshold/10000:.0f}万元★")
    
    # ========== 第一步：获取全市场ETF ==========
    all_funds = get_all_securities(['fund'], date=context.current_dt).index.tolist()
    
    etf_list = []
    for code in all_funds:
        try:
            info = get_security_info(code)
            if info and info.subtype == 'etf':  # 只保留ETF
                etf_list.append(code)
        except Exception:
            continue
    
    log.info(f"★ 【初始池】 全市场ETF总数: {len(etf_list)} 只★")
    
    # ========== 第二步：流动性过滤（近10日） ==========
    log.info("=" * 70)
    log.info(f"【第一步：流动性过滤】近{LIQUIDITY_LOOKBACK_DAYS}日日均成交额 ≥ {g.avg_etf_money_threshold/10000:.0f}万元")
    liquid_etfs_info = []
    
    for etf in etf_list:
        money_avg = get_daily_money(etf, days=LIQUIDITY_LOOKBACK_DAYS)
        if money_avg >= g.avg_etf_money_threshold:
            try:
                display_name = get_security_info(etf).display_name
                liquid_etfs_info.append({
                    'code': etf,
                    'name': display_name,
                    'money': money_avg
                })
            except:
                continue
    
    liquid_etfs_info.sort(key=lambda x: x['money'], reverse=True)
    log.info(f"【流动性过滤】通过近{LIQUIDITY_LOOKBACK_DAYS}日流动性门槛的ETF: {len(liquid_etfs_info)} 只")
    
    # ========== 第三步：名称清理（先删除基金公司名称，再删除噪音词） ==========
    cleaned_info = []
    for item in liquid_etfs_info:
        code = item['code']
        original_name = item['name']
        cleaned = original_name
        
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        
        for noise in sorted(NOISE_WORDS, key=len, reverse=True):
            cleaned = cleaned.replace(noise, '')
        
        cleaned = cleaned.strip()
        
        if cleaned == '':
            cleaned = original_name
        
        cleaned_info.append({
            'code': code,
            'original_name': original_name,
            'cleaned_name': cleaned,
            'money': item['money']
        })
    
    # ========== 第四步：行业去重（基于清理后的名称） ==========
    log.info("=" * 70)
    log.info("【第二步：行业去重】开始执行（基于清理后的名称）")
    
    groups = {}
    ungrouped = []  # 存储未分组的ETF
    etf_info = {}
    
    for item in cleaned_info:
        code = item['code']
        cleaned_name = item['cleaned_name']
        money_avg = item['money']
        original_name = item['original_name']
        
        # 归一化处理：传入清理后的名称进行关键词匹配
        idx_key = get_normalized_index_key(code, cleaned_name)
        
        # 存储信息
        etf_info[code] = {
            'money': money_avg,
            'original_name': original_name,
            'cleaned_name': cleaned_name,
            'key': idx_key
        }
        
        # 判断是否匹配到分组
        if idx_key in INDEX_SYNONYMS:  # 匹配到已定义的分组
            if idx_key not in groups:
                groups[idx_key] = []
            groups[idx_key].append(code)
        else:
            # 未匹配到任何分组
            ungrouped.append((money_avg, code, original_name, cleaned_name))
    log.info(f"【分组统计】共形成 {len(groups)} 个行业类别，未分组ETF {len(ungrouped)} 只")
    # 显示已分组类别的成员（可选，按需保留或注释）
    #for key, members in groups.items():
    #    sorted_members = sorted(members, key=lambda x: etf_info[x]['money'], reverse=True)
    #    member_info = []
    #    for m in sorted_members:
    #        money = etf_info[m]['money'] / 1e8
    #        original = etf_info[m]['original_name']
    #        member_info.append(f"{original}({m})日均{money:.2f}亿 → [{key}]")
    #    log.info(f"【组内成员】类别 '{key}': {member_info}")
    
    # 显示未分组的前5名（调试用，可按需保留或注释）
    #if ungrouped:
    #    ungrouped_sorted = sorted(ungrouped, key=lambda x: x[0], reverse=True)
    #    log.info(f"【未分组ETF前5名】（按成交额排序）：")
    #    for i, (money, code, original_name, cleaned_name) in enumerate(ungrouped_sorted[:5]):
    #        log.info(f"  {i+1}. {original_name}({code}) 日均{money/1e8:.2f}亿，清理后: '{cleaned_name}'")
    
    # ========== 第五步：每组选冠军 + 未分组选前5 ==========
    final_pool = []
    final_pool_info = []
    
    # 已分组：每组选冠军
    for key, members in groups.items():
        sorted_members = sorted(members, key=lambda x: etf_info[x]['money'], reverse=True)
        winner = sorted_members[0]
        
        final_pool.append(winner)
        final_pool_info.append({
            'code': winner,
            'name': etf_info[winner]['original_name'],
            'money': etf_info[winner]['money'],
            'key': key
        })
    
    # 未分组：按成交额排序，取前0名
    if ungrouped:
        ungrouped.sort(key=lambda x: x[0], reverse=True)  # 按成交额降序
        ungrouped_top5 = ungrouped[:0]  # 取前0名
        
        for money, code, name, cleaned_name in ungrouped_top5:
            final_pool.append(code)
            final_pool_info.append({
                'code': code,
                'name': name,
                'money': money,
                'key': '未分组'
            })
    
    # 按成交额从大到小排序最终池
    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    
    # ========== 第六步：显示最终结果 ==========
    log.info(f"【最终结果】共 {len(final_pool)} 只ETF入选动态池")
    log.info("=" * 70)
    
    display_list = [f"{item['name']}({item['code']})日均{item['money']/1e8:.2f}亿 → [{item['key']}]" for item in final_pool_info_sorted]
    log.info(f"★ 【月度动态ETF池刷新】{trigger_type}、执行完成★")
    log.info(f"★ 动态池大小: {len(final_pool)} 只★")    
    log.info(f"{', '.join(display_list)}")
    log.info("★" * 80)
    
    return final_pool

def get_security_name(security):
    """安全获取证券名称"""
    try:
        current_data = get_current_data()
        return current_data[security].name
    except Exception as e:
        log.warning(f"获取{security}名称失败: {e}")
        return "未知名称"

def get_normalized_index_key(etf_code, display_name=None):
    """
    对 ETF 的名称进行归一化处理，生成去重标识
    使用行业关键词匹配的方式，按关键词长度降序匹配，确保同类ETF被正确合并
    """
    if display_name is None:
        display_name = get_security_info(etf_code).display_name
    
    # 收集所有关键词及其对应类别
    keyword_to_category = []
    for category, keywords in INDEX_SYNONYMS.items():
        for keyword in keywords:
            keyword_to_category.append((keyword, category))
    
    # 按关键词长度降序排序（长的优先匹配）
    keyword_to_category.sort(key=lambda x: len(x[0]), reverse=True)
    
    # 遍历排序后的关键词进行匹配
    for keyword, category in keyword_to_category:
        if keyword in display_name:
            return category
    
    # 如果没有匹配到，返回原名称
    return display_name

def daily_refresh_filtered_dynamic_pool(context):
    """每日对动态ETF池进行流动性过滤（使用全局阈值）"""
    log.info("=" * 70)
    log.info("【每日动态池过滤】开始执行")
    log.info(f"【流动性门槛】近3个交易日日均成交金额 > {g.avg_etf_money_threshold/10000:.0f}万元")
    
    if not g.dynamic_etf_pool:
        log.info("【动态池过滤】动态池为空，跳过过滤")
        return
    
    filtered_dynamic = []
    filtered_dynamic_info = []
    
    end_date = context.previous_date
    try:
        price_data = get_price(
            g.dynamic_etf_pool,
            end_date=end_date,
            count=3,
            frequency='daily',
            fields=['money'],
            panel=False
        )
        
        if price_data is not None and not price_data.empty:
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / 3
            
            for etf in g.dynamic_etf_pool:
                money_avg = avg_daily_money.get(etf, 0)
                if money_avg >= g.avg_etf_money_threshold:
                    try:
                        display_name = get_security_info(etf).display_name
                        filtered_dynamic.append(etf)
                        filtered_dynamic_info.append({
                            'code': etf,
                            'name': display_name,
                            'money': money_avg
                        })
                    except:
                        filtered_dynamic.append(etf)
                        filtered_dynamic_info.append({
                            'code': etf,
                            'name': "未知名称",
                            'money': money_avg
                        })
    except Exception as e:
        log.warning(f"【动态池过滤】异常: {e}")
        filtered_dynamic = g.dynamic_etf_pool[:]
    
    filtered_dynamic_info.sort(key=lambda x: x['money'], reverse=True)
    
    original_set = set(g.dynamic_etf_pool)
    filtered_set = set(filtered_dynamic)
    removed = original_set - filtered_set
    
    if removed:
        removed_info = []
        for code in removed:
            try:
                name = get_security_info(code).display_name
                removed_info.append(f"{name}({code})")
            except:
                removed_info.append(code)
        log.info(f"【动态池过滤】剔除 {len(removed)} 只低流动性ETF: {removed_info}")
    
    display_list = [f"{item['name']}({item['code']})日均{item['money']/1e8:.2f}亿" for item in filtered_dynamic_info]
    log.info(f"【动态池过滤】保留高流动性ETF ({len(filtered_dynamic_info)}只): {display_list}")
    
    g.dynamic_etf_pool = filtered_dynamic
    g.filtered_dynamic_pool_with_money = filtered_dynamic_info

def daily_refresh_filtered_fixed_pool(context):
    """每日对固定ETF池进行流动性过滤（使用全局阈值）"""
    log.info("=" * 70)
    log.info("【每日固定池过滤】开始执行")
    log.info(f"【流动性门槛】近3个交易日日均成交金额 > {g.avg_etf_money_threshold/10000:.0f}万元")
    
    filtered_fixed = []
    filtered_fixed_info = []
    
    end_date = context.previous_date
    try:
        price_data = get_price(
            g.fixed_etf_pool,
            end_date=end_date,
            count=3,
            frequency='daily',
            fields=['money'],
            panel=False
        )
        
        if price_data is not None and not price_data.empty:
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / 3
            
            for etf in g.fixed_etf_pool:
                money_avg = avg_daily_money.get(etf, 0)
                if money_avg >= g.avg_etf_money_threshold:
                    try:
                        display_name = get_security_info(etf).display_name
                        filtered_fixed.append(etf)
                        filtered_fixed_info.append({
                            'code': etf,
                            'name': display_name,
                            'money': money_avg
                        })
                    except:
                        filtered_fixed.append(etf)
                        filtered_fixed_info.append({
                            'code': etf,
                            'name': "未知名称",
                            'money': money_avg
                        })
    except Exception as e:
        log.warning(f"【固定池过滤】异常: {e}")
        filtered_fixed = g.fixed_etf_pool[:]
    
    filtered_fixed_info.sort(key=lambda x: x['money'], reverse=True)
    
    original_set = set(g.fixed_etf_pool)
    filtered_set = set(filtered_fixed)
    removed = original_set - filtered_set
    
    if removed:
        removed_info = []
        for code in removed:
            try:
                name = get_security_info(code).display_name
                removed_info.append(f"{name}({code})")
            except:
                removed_info.append(code)
        log.info(f"【固定池过滤】剔除 {len(removed)} 只低流动性ETF: {removed_info}")
    
    display_list = [f"{item['name']}({item['code']})日均{item['money']/1e8:.2f}亿" for item in filtered_fixed_info]
    log.info(f"【固定池过滤】保留高流动性ETF ({len(filtered_fixed_info)}只): {display_list}")
    
    g.filtered_fixed_pool = filtered_fixed
    g.filtered_fixed_pool_with_money = filtered_fixed_info

def daily_merge_etf_pools(context):
    """每日合并固定池和动态池"""
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    
    log.info("=" * 70)
    log.info("【合并ETF池】开始执行")    
    log.info(f"【合并池统计】")
    log.info(f"  - 固定池（过滤后）: {len(g.filtered_fixed_pool)} 只")
    log.info(f"  - 动态池（过滤后）: {len(g.dynamic_etf_pool)} 只")
    log.info(f"  - 合并后去重: {len(merged)} 只")
    log.info("【合并池明细】按日均成交额从大到小排序：")

    all_money_info = {}
    
    if hasattr(g, 'filtered_fixed_pool_with_money'):
        for item in g.filtered_fixed_pool_with_money:
            all_money_info[item['code']] = item
    
    if hasattr(g, 'filtered_dynamic_pool_with_money'):
        for item in g.filtered_dynamic_pool_with_money:
            all_money_info[item['code']] = item
    
    sorted_items = sorted(all_money_info.values(), key=lambda x: x['money'], reverse=True)
    
    display_list = [f"{item['name']}({item['code']})日均{item['money']/1e8:.2f}亿" for item in sorted_items]
    log.info(f"  {', '.join(display_list)}")
    log.info("=" * 70)    
    g.merged_etf_pool = merged

def calculate_and_log_ranked_etfs(context):
    """计算合并池中的标的动量得分"""
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list

def calculate_all_metrics_for_etf(context, etf):
    """计算单个ETF的所有动量指标（动量得分、年化收益、R²、短期动量、均线、成交量比、风控、RSI等）"""
    try:
        etf_name = get_security_name(etf)
        
        lookback = max(
            g.lookback_days,
            g.short_lookback_days,
            g.rsi_period + g.rsi_lookback_days,
            g.ma_filter_days,
            g.volume_lookback
        ) + 20
        
        prices = attribute_history(etf, lookback, '1d', ['close', 'high', 'low'])
        current_data = get_current_data()
        
        if len(prices) < max(g.lookback_days, g.ma_filter_days):
            return None
            
        current_price = current_data[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        recent_price_series = price_series[-(g.lookback_days + 1):]
        y = np.log(recent_price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0
        momentum_score = annualized_returns * r_squared

        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = -np.inf

        ma_price = np.mean(price_series[-g.ma_filter_days:])
        current_above_ma = current_price >= ma_price

        volume_ratio = get_volume_ratio(context, etf, show_detail_log=False)

        day_ratios = []
        passed_loss_filter = True
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False

        current_rsi = 0
        max_recent_rsi = 0
        passed_rsi_filter = True
        if g.use_rsi_filter and len(price_series) >= g.rsi_period + g.rsi_lookback_days:
            rsi_values = calculate_rsi(price_series, g.rsi_period)
            if len(rsi_values) >= g.rsi_lookback_days:
                recent_rsi = rsi_values[-g.rsi_lookback_days:]
                max_recent_rsi = np.max(recent_rsi)
                current_rsi = recent_rsi[-1]
                if np.any(recent_rsi > g.rsi_threshold):
                    ma5 = np.mean(price_series[-5:]) if len(price_series) >= 5 else current_price
                    if current_price < ma5:
                        passed_rsi_filter = False

        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'short_annualized': short_annualized,
            'current_price': current_price,
            'ma_price': ma_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'current_rsi': current_rsi,
            'max_recent_rsi': max_recent_rsi,
            'passed_momentum': g.min_score_threshold <= momentum_score <= g.max_score_threshold,
            'passed_short_mom': short_annualized >= g.short_momentum_threshold,
            'passed_r2': r_squared > g.r2_threshold,
            'passed_annual_ret': annualized_returns >= g.min_annualized_return,
            'passed_ma': current_above_ma,
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'passed_rsi': passed_rsi_filter,
        }
    except Exception as e:
        log.warning(f"计算 {etf} 指标出错: {e}")
        return None

def get_volume_ratio(context, security, lookback_days=None, threshold=None, show_detail_log=True):
    """计算成交量比（当前量/过去N日均量）"""
    if lookback_days is None:
        lookback_days = g.volume_lookback
    if threshold is None:
        threshold = g.volume_threshold
    try:
        security_name = get_security_name(security)
        hist_data = attribute_history(security, lookback_days, '1d', ['volume'])
        if hist_data.empty or len(hist_data) < lookback_days:
            return None
        past_n_days_vol = hist_data['volume']
        if past_n_days_vol.isnull().any() or past_n_days_vol.eq(0).any():
            return None
        avg_volume = past_n_days_vol.mean()
        if avg_volume == 0:
            return None
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], skip_paused=False, fq='pre', panel=False, fill_paused=False)
        if df_vol is None or df_vol.empty:
            return None
        current_volume = df_vol['volume'].sum()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        return volume_ratio
    except Exception as e:
        return None

def calculate_rsi(prices, period=6):
    """计算RSI指标"""
    if len(prices) < period + 1:
        return np.array([])
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    alpha = 2.0 / (period + 1)
    avg_gains = np.zeros(len(deltas))
    avg_losses = np.zeros(len(deltas))
    avg_gains[period - 1] = np.mean(gains[:period])
    avg_losses[period - 1] = np.mean(losses[:period])
    for i in range(period, len(deltas)):
        avg_gains[i] = (gains[i] * alpha) + (avg_gains[i - 1] * (1 - alpha))
        avg_losses[i] = (losses[i] * alpha) + (avg_losses[i - 1] * (1 - alpha))
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))
    full_rsi = np.full(len(prices), np.nan)
    full_rsi[1:] = rsi
    return full_rsi[period:]

def get_final_ranked_etfs(context):
    """主筛选函数，从合并池中选出最终排名ETF（含详细日志）"""
    all_metrics = []
    etf_set = list(g.merged_etf_pool)

    end_date = context.previous_date

    log.info(f"【动量得分计算】使用合并池，合计{len(etf_set)}只ETF")

    for etf in etf_set:
        try:
            info = get_security_info(etf)
            start_date_raw = info.start_date if info else None
        except Exception:
            start_date_raw = None

        if start_date_raw is None:
            start_date = None
        elif isinstance(start_date_raw, datetime):
            start_date = start_date_raw.date()
        elif isinstance(start_date_raw, date):
            start_date = start_date_raw
        else:
            start_date = None

        if start_date is None or end_date < start_date:
            continue

        current_data = get_current_data()
        if current_data[etf].paused:
            continue

        metrics = calculate_all_metrics_for_etf(context, etf)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                log.warning(f"发现重复ETF数据: {metrics['etf']}，跳过。")
                continue
            all_metrics.append(metrics)

    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')

    all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)

    log_lines_step1 = ["", ">>> 第一步：所有ETF按动量得分从大到小排序 <<<"]
    for m in all_metrics:
        def fmt_status(value_str, passed):
            return f"{value_str} {'✅' if passed else '❌'}"

        original_score = m.get('momentum_score')
        if original_score == float('-inf'):
            mom_score_str = "nan"
            mom_passed = False
        else:
            mom_score_str = f"{original_score:.4f}" if not pd.isna(original_score) else "nan"
            mom_passed = m['passed_momentum']

        short_str = f"{m['short_annualized']:.4f}" if not pd.isna(m['short_annualized']) else "nan"
        short = fmt_status(f"短期动量: {short_str}", m['passed_short_mom'])
        r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
        r2 = fmt_status(f"R²: {r2_str}", m['passed_r2'])
        ann_str = f"{m['annualized_returns']:.2%}" if not pd.isna(m['annualized_returns']) else "nan%"
        ann = fmt_status(f"年化收益率: {ann_str}", m['passed_annual_ret'])
        ma_price_str = f"{m['ma_price']:.2f}" if not pd.isna(m['ma_price']) else "nan"
        ma = fmt_status(f"均线: 当前价{m['current_price']:.2f} vs 均线{ma_price_str}", m['passed_ma'])
        vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
        vol = fmt_status(f"成交量比值: {vol_val}", m['passed_volume'])
        min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
        loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
        loss = fmt_status(f"短期风控（近3日最低比值）: {loss_val}", m['passed_loss'])
        rsi_str = f"{m['current_rsi']:.1f}" if not pd.isna(m['current_rsi']) else "nan"
        max_rsi_str = f"{m['max_recent_rsi']:.1f}" if not pd.isna(m['max_recent_rsi']) else "nan"
        rsi = fmt_status(f"RSI: 当前{rsi_str} (峰值{max_rsi_str})", m['passed_rsi'])

        line = (
            f"{m['etf']} {m['etf_name']}: "
            f"{fmt_status(f'动量得分: {mom_score_str}', mom_passed)} ，"
            f"{short} ，"
            f"{r2}，"
            f"{ann}，"
            f"{ma}，"
            f"{vol}，"
            f"{loss}，"
            f"{rsi}"
        )
        log_lines_step1.append(line)

    # 第二步：应用过滤条件
    filtered_list = apply_filters(all_metrics)
    for item in filtered_list:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
    
    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    
    # 第二步：取前10名
    top_10 = filtered_list[:10]
    
    log_lines_step2 = ["", ">>> 第二步：符合全部过滤条件的ETF按动量得分从大到小排序 (前10名) <<<"]
    
    if top_10:
        for i, m in enumerate(top_10):
            # 复用第一步的完整日志格式，仅修改索引号
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"

            original_score = m.get('momentum_score')
            if original_score == float('-inf'):
                mom_score_str = "nan"
                mom_passed = False
            else:
                mom_score_str = f"{original_score:.4f}" if not pd.isna(original_score) else "nan"
                mom_passed = m['passed_momentum']

            short_str = f"{m['short_annualized']:.4f}" if not pd.isna(m['short_annualized']) else "nan"
            short = fmt_status(f"短期动量: {short_str}", m['passed_short_mom'])
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            r2 = fmt_status(f"R²: {r2_str}", m['passed_r2'])
            ann_str = f"{m['annualized_returns']:.2%}" if not pd.isna(m['annualized_returns']) else "nan%"
            ann = fmt_status(f"年化收益率: {ann_str}", m['passed_annual_ret'])
            ma_price_str = f"{m['ma_price']:.2f}" if not pd.isna(m['ma_price']) else "nan"
            ma = fmt_status(f"均线: 当前价{m['current_price']:.2f} vs 均线{ma_price_str}", m['passed_ma'])
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            vol = fmt_status(f"成交量比值: {vol_val}", m['passed_volume'])
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            loss = fmt_status(f"短期风控（近3日最低比值）: {loss_val}", m['passed_loss'])
            rsi_str = f"{m['current_rsi']:.1f}" if not pd.isna(m['current_rsi']) else "nan"
            max_rsi_str = f"{m['max_recent_rsi']:.1f}" if not pd.isna(m['max_recent_rsi']) else "nan"
            rsi = fmt_status(f"RSI: 当前{rsi_str} (峰值{max_rsi_str})", m['passed_rsi'])

            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"{fmt_status(f'动量得分: {mom_score_str}', mom_passed)} ，"
                f"{short} ，"
                f"{r2}，"
                f"{ann}，"
                f"{ma}，"
                f"{vol}，"
                f"{loss}，"
                f"{rsi}"
            )
            log_lines_step2.append(line)
    else:
        log_lines_step2.append("（无符合条件的ETF）")
        full_log = "\n".join(log_lines_step1 + log_lines_step2)
        log.info(full_log)
        return []
    
    # ========== 第三步：获取参考得分阈值，构建候选池（按动量得分排序） ==========
    if len(top_10) >= g.holdings_num:
        # 取第g.holdings_num名的得分作为参考
        reference_score = top_10[g.holdings_num - 1]['momentum_score']
        score_threshold = reference_score * 0.9
        log_lines_step3 = [f"", f">>> 第三步：选取动量得分 ≥ 第{g.holdings_num}名 ({top_10[g.holdings_num - 1]['etf_name']}) 得分 {reference_score:.4f} × 0.9 = {score_threshold:.4f} 的ETF <<<"]
        
        # 筛选得分 ≥ 阈值的ETF
        candidate_pool = [item for item in top_10 if item['momentum_score'] >= score_threshold]
    else:
        # 如果不足g.holdings_num只，则全部入选
        log_lines_step3 = [f"", f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<"]
        candidate_pool = top_10[:]   # 复制一份，保持原有顺序

    # 候选池已按动量得分从大到小排序（top_10原本就是排序的，筛选后保持顺序）
    log_lines_step3.append(f"【候选池】共{len(candidate_pool)}只ETF（按动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        log_lines_step3.append(f"  {i+1}. {item['etf_name']}({item['etf']}) 动量得分: {item['momentum_score']:.4f}")

    # ========== 第四步：结合当前持仓进行调整 ==========
    log_lines_step4 = ["", ">>> 第四步：结合当前持仓进行调整 <<<"]

    # 获取当前持仓（排除现金）
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    log_lines_step4.append(f"当前持仓ETF：{current_holdings}")

    # 建立候选池字典（便于快速查找）
    candidate_dict = {item['etf']: item for item in candidate_pool}

    # 确定保留的持仓ETF（存在于候选池中的）
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    log_lines_step4.append(f"其中存在于候选池中的持仓ETF：{[item['etf'] for item in retained]}")

    # 根据保留数量决定最终目标
    if len(retained) >= g.holdings_num:
        # 保留的超过目标数，从保留中按动量得分取前g.holdings_num
        retained_sorted = sorted(retained, key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
        log_lines_step4.append(f"保留的持仓ETF数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的ETF中按动量得分取前{g.holdings_num}只作为最终目标。")
    else:
        need = g.holdings_num - len(retained)
        # 从候选池中剔除已保留的ETF
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        # remaining_pool仍保持原动量得分排序
        additional = remaining_pool[:need]
        final_result = retained + additional
        log_lines_step4.append(f"保留持仓ETF {len(retained)}只，还需补充{need}只。")
        if retained:
            log_lines_step4.append("保留的ETF（按原有顺序）：")
            for item in retained:
                log_lines_step4.append(f"  {item['etf_name']}({item['etf']})")
        if additional:
            log_lines_step4.append("补充的ETF（按动量得分排序）：")
            for i, item in enumerate(additional):
                log_lines_step4.append(f"  {i+1}. {item['etf_name']}({item['etf']}) 动量得分: {item['momentum_score']:.4f}")

    log_lines_step4.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        log_lines_step4.append(f"  {i+1}. {item['etf_name']}({item['etf']})")
    log_lines_step4.append("==================================================")

    # 合并所有日志并输出
    full_log = "\n".join(log_lines_step1 + log_lines_step2 + log_lines_step3 + log_lines_step4)
    log.info(full_log)

    return final_result

def execute_sell_trades(context):
    """卖出交易逻辑"""
    log.info("========== 卖出操作开始 ==========")
    if is_in_cooldown(context):
        log.info("🔒 当前处于冷却期，跳过轮动逻辑中的卖出操作")
        log.info("========== 卖出操作完成 ==========")
        return

    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    target_etfs = []
    
    if ranked_etfs:
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}，得分: {metrics['momentum_score']:.4f}")
    else:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            etf_name = get_security_name(g.defensive_etf)
            log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}，得分: N/A")
        else:
            log.info("💤 无最终目标(空仓模式)")
            target_etfs = []

    g.target_etfs_list = target_etfs
    current_positions = list(context.portfolio.positions.keys())
    target_set = set(target_etfs)

    sell_count = 0
    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            if security not in g.filtered_fixed_pool and security != g.defensive_etf:
                 log.info(f"🔍 发现持仓不在预设池中: {security} {security_name}")
            
            success = smart_order_target_value(security, 0, context)
            if success:
                sell_count += 1
                log.info(f"✅ 已成功卖出: {security} {security_name}")
            else:
                log.info(f"❌ 卖出失败: {security} {security_name}")

            g.position_highs.pop(security, None)
            g.position_stop_prices.pop(security, None)
    
    log.info(f"本次共计划卖出 {sell_count} 只ETF。")
    log.info("========== 卖出操作完成 ==========")

def execute_buy_trades(context):
    """买入交易逻辑"""
    log.info("========== 买入操作开始 ==========")
    exit_safe_haven_if_cooldown_ends(context)
    if is_in_cooldown(context):
        log.info("🔒 当前处于冷却期，跳过正常买入操作")
        log.info("========== 买入操作完成 ==========")
        return
        
    target_etfs = g.target_etfs_list
    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return

    # 获取当前持仓
    current_positions = set(context.portfolio.positions.keys())
    # 计算需要买入的ETF列表
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    # 当前实际持仓数量
    actual_holding_count = len(current_positions)
    # 计算还可以买入多少只（不超过目标持仓数）
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    # 取需要买入和可买入数量的较小值
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    # 如果不需要买入，直接返回
    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("========== 买入操作完成 ==========")
        return
    # 只取前num_etfs_to_buy个ETF买入
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标持仓: {g.holdings_num}只, 本次计划买入: {num_etfs_to_buy}只")
    
    available_cash = context.portfolio.available_cash
    allocated_value_per_etf = available_cash // num_etfs_to_buy
    log.info(f"账户可用现金: {available_cash:.2f}, 分配给每只ETF的资金: {allocated_value_per_etf:.2f}")

    if allocated_value_per_etf < g.min_money:
        log.info(f"计算出的单只ETF分配金额 {allocated_value_per_etf:.2f} 小于最小交易额 {g.min_money:.2f}，无法买入任何目标ETF")
        log.info("========== 买入操作完成 ==========")
        return

    for i, etf in enumerate(etfs_to_buy):
        target_value_for_this_etf = allocated_value_per_etf
        
        if i == len(etfs_to_buy) - 1 and context.portfolio.available_cash >= g.min_money:
            target_value_for_this_etf = context.portfolio.available_cash
            log.info(f"为最后一支ETF {etf} 分配剩余所有可用现金: {target_value_for_this_etf:.2f}")

        log.info(f"准备买入第{i+1}/{num_etfs_to_buy}只ETF: {etf}, 目标金额: {target_value_for_this_etf:.2f}")
        
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功。")
        else:
            log.info(f"❌ ETF {etf} 下单失败。")
            
    log.info("========== 买入操作完成 ==========")

def smart_order_target_value(security, target_value, context):
    """智能下单（考虑停牌、涨跌停、最小交易额等）"""
    current_data = get_current_data()
    security_name = get_security_name(security)
    if current_data[security].paused:
        log.info(f"{security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {security_name}: 当前涨停，跳过交易")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {security_name}: 当前跌停，跳过卖出")
        return False
    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {security_name}: 当前价格为0，跳过交易")
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
        log.info(f"{security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过交易")
        return False
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {security_name}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)
    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            g.positions[security] = target_amount
            if amount_diff > 0 and security in g.filtered_fixed_pool:
                g.position_highs[security] = current_price
            if g.use_atr_stop_loss and not (g.atr_exclude_defensive and security == g.defensive_etf):
                current_atr, _, success, _ = calculate_atr(security, g.atr_period)
                if success:
                    if g.atr_trailing_stop:
                        g.position_stop_prices[security] = current_price - g.atr_multiplier * current_atr
                    else:
                        g.position_stop_prices[security] = current_price - g.atr_multiplier * current_atr
            if amount_diff > 0:
                buy_total = amount_diff * current_price
                log.info(f"📦 买入 {security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}，总金额: {buy_total:.2f}")
                log.info(f"📦 已成功买入: {security} {security_name}")
            else:
                sell_total = abs(amount_diff) * current_price
                log.info(f"📤 卖出 {security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}，总金额{sell_total:.2f}元")
                log.info(f"📤 已成功卖出: {security} {security_name}")
            return True
        else:
            log.warning(f"下单失败: {security} {security_name}，数量: {amount_diff}")
            return False
    return False

def minute_level_stop_loss(context):
    """分钟级固定比例止损"""
    if not g.use_fixed_stop_loss: return
    if is_in_cooldown(context): return

    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0: continue
        current_price = current_data[security].last_price
        if current_price <= 0: continue
        cost_price = position.avg_cost
        if cost_price <= 0: continue
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 [分钟级] 固定百分比止损卖出: {security} {security_name}，当前价: {current_price:.3f}, 成本: {cost_price:.3f}, 阈值: {g.fixedStopLossThreshold}, 亏损: {loss_percent:.2f}%")
            success = smart_order_target_value(security, 0, context)
            if success:
                log.info(f"✅ [分钟级] 已成功止损卖出: {security} {security_name}，持仓实际亏损: {loss_percent:.2f}%")
                g.position_highs.pop(security, None)
                g.position_stop_prices.pop(security, None)
                enter_safe_haven_and_set_cooldown(context, trigger_reason="分钟级固定止损")
            else:
                log.info(f"❌ [分钟级] 止损卖出失败: {security} {security_name}")

def minute_level_pct_stop_loss(context):
    """分钟级当日跌幅止损（基于昨日收盘价）"""
    if not g.use_pct_stop_loss: return
    if is_in_cooldown(context): return

    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0: continue
        try:
            close_series = attribute_history(security, 1, '1d', ['close'], skip_paused=False)
            if len(close_series['close']) == 0:
                continue
            yesterday_close = close_series['close'][-1]
            if yesterday_close <= 0:
                continue
        except Exception as e:
            continue

        current_price = current_data[security].last_price
        if current_price <= 0: continue

        stop_price = yesterday_close * g.pct_stop_loss_threshold
        if current_price <= stop_price:
            security_name = get_security_name(security)
            daily_loss = (current_price / yesterday_close - 1) * 100
            log.info(f"🚨 [分钟级] 当日跌幅止损卖出: {security} {security_name}，当前价: {current_price:.3f}, 昨收: {yesterday_close:.3f}, 触发价: {stop_price:.3f}, 跌幅: {daily_loss:.2f}%")
            success = smart_order_target_value(security, 0, context)
            if success:
                log.info(f"✅ [分钟级] 已成功按当日跌幅止损卖出: {security} {security_name}，当日实际跌幅: {daily_loss:.2f}%")
                g.position_highs.pop(security, None)
                g.position_stop_prices.pop(security, None)
                enter_safe_haven_and_set_cooldown(context, trigger_reason="分钟级当日跌幅止损")
            else:
                log.info(f"❌ [分钟级] 当日跌幅止损卖出失败: {security} {security_name}")

def minute_level_atr_stop_loss(context):
    """分钟级ATR动态止损"""
    if not g.use_atr_stop_loss: return
    if is_in_cooldown(context): return

    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0: continue
        if g.atr_exclude_defensive and security == g.defensive_etf: continue
        try:
            current_price = current_data[security].last_price
            if current_price <= 0: continue
            cost_price = position.avg_cost
            if cost_price <= 0: continue
            current_atr, _, success, _ = calculate_atr(security, g.atr_period)
            if not success or current_atr <= 0: continue
            if security not in g.position_highs:
                g.position_highs[security] = current_price
            else:
                g.position_highs[security] = max(g.position_highs[security], current_price)
            if g.atr_trailing_stop:
                atr_stop_price = g.position_highs[security] - g.atr_multiplier * current_atr
            else:
                atr_stop_price = cost_price - g.atr_multiplier * current_atr
            g.position_stop_prices[security] = atr_stop_price
            if current_price <= atr_stop_price:
                loss_percent = (current_price / cost_price - 1) * 100
                atr_type = "跟踪" if g.atr_trailing_stop else "固定"
                security_name = get_security_name(security)
                log.info(f"🚨 [分钟级] ATR动态止损({atr_type})卖出: {security} {security_name}，当前价: {current_price:.3f}, 止损价: {atr_stop_price:.3f}, 亏损: {loss_percent:.2f}%")
                success = smart_order_target_value(security, 0, context)
                if success:
                    log.info(f"✅ [分钟级] ATR止损成功: {security} {security_name}")
                    g.position_highs.pop(security, None)
                    g.position_stop_prices.pop(security, None)
                    enter_safe_haven_and_set_cooldown(context, trigger_reason="分钟级ATR动态止损")
                else:
                    log.info(f"❌ [分钟级] ATR止损失败: {security} {security_name}")
        except Exception as e:
            security_name = get_security_name(security)
            log.warning(f"[分钟级] ATR止损异常 {security} {security_name}: {e}")

def calculate_atr(security, period=14):
    """计算ATR指标"""
    try:
        needed_days = period + 20
        hist_data = attribute_history(security, needed_days, '1d', ['high', 'low', 'close'])
        if len(hist_data) < period + 1:
            return 0, [], False, f"数据不足{period+1}天"
        high_prices = hist_data['high'].values
        low_prices = hist_data['low'].values
        close_prices = hist_data['close'].values
        tr_values = np.zeros(len(high_prices))
        for i in range(1, len(high_prices)):
            tr1 = high_prices[i] - low_prices[i]
            tr2 = abs(high_prices[i] - close_prices[i-1])
            tr3 = abs(low_prices[i] - close_prices[i-1])
            tr_values[i] = max(tr1, tr2, tr3)
        atr_values = np.zeros(len(tr_values))
        for i in range(period, len(tr_values)):
            atr_values[i] = np.mean(tr_values[i-period+1:i+1])
        current_atr = atr_values[-1] if len(atr_values) > 0 else 0
        valid_atr = atr_values[period:] if len(atr_values) > period else atr_values
        return current_atr, valid_atr, True, "计算成功"
    except Exception as e:
        return 0, [], False, f"计算出错:{str(e)}"

def check_defensive_etf_available(context):
    """检查防御性ETF是否可交易（停牌、涨跌停）"""
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    if current_data[defensive_etf].paused:
        defensive_etf_name = get_security_name(defensive_etf)
        log.info(f"防御性ETF {defensive_etf} {defensive_etf_name} 今日停牌")
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        defensive_etf_name = get_security_name(defensive_etf)
        log.info(f"防御性ETF {defensive_etf} {defensive_etf_name} 当前涨停")
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        defensive_etf_name = get_security_name(defensive_etf)
        log.info(f"防御性ETF {defensive_etf} {defensive_etf_name} 当前跌停")
        return False
    return True

def is_in_cooldown(context):
    """判断是否在冷却期内"""
    if not g.sell_cooldown_enabled or g.cooldown_end_date is None:
        return False
    return context.current_dt.date() <= g.cooldown_end_date

def set_cooldown(context):
    """设置冷却期结束日期"""
    if g.sell_cooldown_enabled:
        g.cooldown_end_date = context.current_dt.date() + pd.Timedelta(days=g.sell_cooldown_days)
        log.info(f"🔒 触发冷却期，结束日期: {g.cooldown_end_date.strftime('%Y-%m-%d')}")

def enter_safe_haven_and_set_cooldown(context, trigger_reason=""):
    """进入冷却期并买入避险ETF"""
    if not g.sell_cooldown_enabled:
        return
    for security in list(context.portfolio.positions.keys()):
        if security in g.filtered_fixed_pool or security == g.defensive_etf:
            position = context.portfolio.positions[security]
            if position.total_amount > 0:
                security_name = get_security_name(security)
                success = smart_order_target_value(security, 0, context)
                if success:
                    log.info(f"✅ [冷却期] 卖出持仓: {security} {security_name}")
                else:
                    log.info(f"❌ [冷却期] 卖出持仓失败: {security} {security_name}")
                g.position_highs.pop(security, None)
                g.position_stop_prices.pop(security, None)
    total_value = context.portfolio.total_value
    if total_value > g.min_money:
        success = smart_order_target_value(g.safe_haven_etf, total_value * 0.99, context)
        if success:
            safe_name = get_security_name(g.safe_haven_etf)
            log.info(f"🛡️ [冷却期] 买入避险ETF: {g.safe_haven_etf} {safe_name}，金额: {total_value * 0.99:.2f}")
        else:
            log.info(f"❌ [冷却期] 买入避险ETF: {g.safe_haven_etf} ")
    else:
        log.info(f"💡 [冷却期] 资金不足，无法买入避险ETF。总资产: {total_value:.2f}")
    set_cooldown(context)
    log.info(f"🔒 [冷却期] 已进入冷却期，由 [{trigger_reason}] 触发。")

def exit_safe_haven_if_cooldown_ends(context):
    """冷却期结束时卖出避险ETF"""
    if not g.sell_cooldown_enabled or g.cooldown_end_date is None:
        return
    current_date = context.current_dt.date()
    if current_date > g.cooldown_end_date:
        log.info(f"🔓 冷却期结束，当前日期: {current_date.strftime('%Y-%m-%d')}")
        if g.safe_haven_etf in context.portfolio.positions:
            position = context.portfolio.positions[g.safe_haven_etf]
            if position.total_amount > 0:
                security_name = get_security_name(g.safe_haven_etf)
                success = smart_order_target_value(g.safe_haven_etf, 0, context)
                if success:
                    log.info(f"✅ [冷却期结束] 卖出避险ETF: {g.safe_haven_etf} {security_name}")
                else:
                    log.info(f"❌ [冷却期结束] 卖出避险ETF失败: {g.safe_haven_etf} {security_name}")
                g.position_highs.pop(g.safe_haven_etf, None)
                g.position_stop_prices.pop(g.safe_haven_etf, None)
        g.cooldown_end_date = None
        log.info(f"🔄 策略恢复正常运行")

def trade(context):
    pass