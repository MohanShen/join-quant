# Clone from JoinQuant
# postId: 917985c45d61dda13ed5603a8323b7fa
# backtestId: 1b5ef972030afbb24574b0234a3ea898
# title: 【五福闹新春】v4.3-完全体动态池的实现

import numpy as np
import math
import pandas as pd
from jqdata import *
from datetime import datetime, date, timedelta

# ==================== 策略初始化 ====================
def initialize(context):
    """初始化策略（设置参数、全局变量、定时任务）"""
    # ==================== 系统设置 ====================
    set_option("avoid_future_data", True)       # 避免未来函数
    set_option("use_real_price", True)          # 使用真实价格
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")  # 设置滑点
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001,
                              close_commission=0.0001, close_today_commission=0.0001,
                              min_commission=5), type="fund")  # 设置交易费用
    # 日志级别配置
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    log.info("【五福闹新春】v4.3启动！")

    # ==================== 固定池 ====================
    g.fixed_etf_pool = [
#大宗商品ETF：
        '518880.XSHG',  # (黄金ETF) [ETF]-成交额：54.60亿元-上市日期：2013-07-29
        '161226.XSHE',  # (国投白银LOF) [LOF]-成交额：21.54亿元-上市日期：2015-08-17
        '159980.XSHE',  # (有色ETF大成) [ETF]-成交额：23.57亿元-上市日期：2019-12-24
        '501018.XSHG',  # (南方原油LOF) [LOF]-成交额：1.34亿元-上市日期：2016-06-28
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
    g.filtered_fixed_pool = []           # 过滤后的固定池
    g.dynamic_etf_pool = []              # 动态池（初始为空）
    g.merged_etf_pool = []               # 合并后的池
    g.ranked_etfs_result = []            # 动量计算结果的列表
    g.positions = {}                     # 记录目标持仓
    g.target_etfs_list = []              # 目标列表
    g.etf_names_dict = {}                # 名称字典
    g.cache_date = None                  # 缓存日期（用于止损）
    g.yesterday_close_cache = {}         # 昨日收盘价缓存（用于止损）
    # ==================== 策略核心参数 ====================
    set_benchmark("510300.XSHG")         # 设置基准
    g.holdings_num = 1                   # 持仓数量
    g.defensive_etf = "511880.XSHG"      # 防御型ETF（市场低迷时持有）
    g.min_money = 10                     # 最小交易金额（元）

    # 动量计算参数（25天周期，0-5分阈值）
    g.lookback_days = 25                 # 动量计算回看天数（交易日）
    g.min_score_threshold = 0            # 动量得分下限
    g.max_score_threshold = 5            # 动量得分上限
    g.score_threshold_ratio = 0.9        # 减少调仓控制得分比例

    # 短期动量参数（21天周期，0-6分阈值）
    g.use_short_momentum_period = False  # 短期动量过滤开关
    g.short_momentum_lookback = 21       # 短期动量回看天数（交易日）
    g.short_momentum_min_score = 0       # 短期动量得分下限
    g.short_momentum_max_score = 6       # 短期动量得分上限

    # 过滤开关及参数
    g.enable_r2_filter = True            # R²过滤开关
    g.r2_threshold = 0.4                 # R²阈值
    g.enable_volume_check = True         # 成交量过滤开关
    g.volume_lookback = 5                # 成交量回看天数（交易日）
    g.volume_threshold = 1.8             # 成交量比阈值
    g.enable_loss_filter = True          # 短期风控过滤开关
    g.loss = 0.97                        # 单日最大允许跌幅（3%）
    g.enable_premium_filter = False       # 溢价率过滤开关
    g.max_premium_rate = 30              # 最大允许溢价率（%）

    # 滤波器参数（正常期使用拉普拉斯，震荡期使用高斯）
    g.laplace_s_param = 0.05             # 拉普拉斯衰减率
    g.laplace_min_slope = 0.002          # 拉普拉斯斜率阈值
    g.gaussian_sigma = 1.2               # 高斯标准差
    g.gaussian_min_slope = 0.002         # 高斯模式专用斜率阈值

    # ==================== 震荡期参数 ====================
    g.enable_range_bound_mode = True      # 震荡期模式开关
    g.current_filter = '正常期'           # 当前滤波器：'正常期'=拉普拉斯滤波器, '震荡期'=高斯滤波器
    g.risk_state = '正常期'               # 风险状态：'正常期' 或 '震荡期'
    g.lookback_high_low_days = 20         # 近20个交易日  
    g.risk_benchmark = '510300.XSHG'      # 风险基准ETF
    
    # 进入震荡期的条件开关
    g.enable_bias_trigger = True          # 乖离率过大触发开关
    g.bias_threshold = 0.08               # 乖离率阈值（8%）
    g.ma_period = 20                      # 均线周期（交易日）
    g.enable_rsi_trigger = True           # RSI超买回落触发开关
    g.rsi_overbought = 70                 # RSI超买阈值
    g.rsi_pullback = 65                   # RSI超买后回落阈值
    g.previous_rsi = None                 # 前一日RSI    
    g.enable_stop_loss_trigger = True     # 持仓ETF止损触发开关
    g.stop_loss_triggered_today = False   # 今日是否触发过止损
    
    # 退出震荡期的条件开关
    g.enable_low_point_rise_trigger = True    # 从低点上涨触发开关
    g.low_point_rise_threshold = 0.04         # 从近期最低点上涨阈值（4%）    
    g.enable_stable_signal_trigger = True     # 企稳信号触发开关
    g.drawdown_recovery = 0.02                # 回撤收窄阈值（2%）
    g.max_range_bound_days = 20               # 最大震荡期天数（20个交易日）
    g.stable_days = 0                         # 企稳天数计数器（交易日）
    
    # 震荡期控制
    g.filter_switch_cooldown = 3          # 切换冷却期（3个交易日）
    g.last_switch_date = None             # 上次切换日期
    g.range_bound_start_date = None       # 震荡期开始日期
    g.range_bound_days_count = 0          # 震荡期内经过的交易日计数

    # 风险监控数据
    g.previous_drawdown = None            # 前一日回撤值
    g.max_portfolio_value = 0             # 策略净值最高点
    g.drawdown_threshold = 0.03           # 回撤监控阈值（3%）
    g.drawdown_records = []               # 回撤记录
    
    # 止损参数
    g.use_fixed_stop_loss = True          # 固定比例止损开关
    g.fixedStopLossThreshold = 0.95       # 固定止损比例（5%）
    g.use_pct_stop_loss = False           # 当日跌幅止损开关
    g.pct_stop_loss_threshold = 0.95      # 当日跌幅止损比例

    # 流动性阈值设置
    g.avg_etf_money_threshold = None
    # ==================== 定时任务 ====================
    run_daily(morning_routine, time='09:00')      # 晨间准备流水线（09:00）
    run_daily(afternoon_routine, time='13:10')    # 午后交易流水线（13:10）
    run_daily(reset_daily_flags, time='15:10')    # 收盘后重置当日标志（15:10）
    
    # 【效率优化】使用原生的 every_bar 替换嵌套 for 循环生成的数百个 run_daily
    run_daily(minute_level_stop_loss, time='every_bar')
    run_daily(minute_level_pct_stop_loss, time='every_bar')
    # 打印策略初始化参数
    log.info(f"""【策略参数初始化完成】
=== 动量得分过滤 ===
- 周期: {g.lookback_days}天
- 得分阈值: [{g.min_score_threshold}, {g.max_score_threshold}]
=== 短期动量得分过滤 ===
- 周期: {g.short_momentum_lookback}天
- 得分阈值: [{g.short_momentum_min_score}, {g.short_momentum_max_score}]
- 短期动量开关: {'启用' if g.use_short_momentum_period else '禁用'}
=== 其他过滤条件 ===
- R²过滤: {'启用' if g.enable_r2_filter else '禁用'} (阈值 > {g.r2_threshold:.1f})
- 成交量过滤: {'启用' if g.enable_volume_check else '禁用'} (近{g.volume_lookback}日均量比 < {g.volume_threshold:.1f})
- 短期风控过滤: {'启用' if g.enable_loss_filter else '禁用'} (近3日单日跌幅 < {1 - g.loss:.0%})
- 溢价率过滤: {'启用' if g.enable_premium_filter else '禁用'} (最大溢价率 ≤ {g.max_premium_rate:.1f}%)
=== 止损机制 ===
- 分钟级固定比例止损: {'启用' if g.use_fixed_stop_loss else '禁用'} (持仓成本价 × {g.fixedStopLossThreshold:.2%})
- 分钟级当日跌幅止损: {'启用' if g.use_pct_stop_loss else '禁用'} (昨日收盘价 × {g.pct_stop_loss_threshold:.2%})
=== 震荡期机制 ===
- 震荡期开关: {'启用' if g.enable_range_bound_mode else '禁用'}
- 进入条件: 乖离率>8% | RSI超买回落 | 当日触发止损
- 退出条件: 从低点上涨>4% | 连续企稳信号 | 震荡期>20天
- 正常期滤波器: 拉普拉斯 (s={g.laplace_s_param}, 斜率≥{g.laplace_min_slope})
- 震荡期滤波器: 高斯 (sigma={g.gaussian_sigma}, 斜率≥{g.gaussian_min_slope})
=== 其他配置 ===
- 标的类型: ETF + LOF
- 固定池: {len(g.fixed_etf_pool)}只
- 持仓数量: {g.holdings_num}只
- 防御标的: {g.defensive_etf}
""")
    # 首次运行时，初始化震荡期状态（通过计算历史数据判断当前是否处于震荡期）
    init_range_bound_status(context)

# ==================== 首次运行震荡期状态初始化 ====================
def init_range_bound_status(context):
    """首次运行时，根据历史数据判断当前是否处于震荡期"""
    if not g.enable_range_bound_mode:
        return
    log.info("🔍 【首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None:
            log.warning("【首次运行】无法获取前一个交易日，保持正常期")
            return
        end_date = context.previous_date
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback, 
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            log.warning(f"【首次运行】数据不足(需{max(g.ma_period, g.lookback_high_low_days)}天，实际{len(df) if df is not None else 0}天)，保持正常期")
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        if len(close) >= g.lookback_high_low_days:
            recent_high = np.max(high[-g.lookback_high_low_days:])
            recent_low = np.min(low[-g.lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        ma = np.mean(close[-g.ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        current_rsi = calculate_rsi(close, period=14)
        should_enter_range_bound = False
        signals = []
        if g.enable_bias_trigger and bias > g.bias_threshold:
            should_enter_range_bound = True
            signals.append(f"乖离率{bias:.2%}>{g.bias_threshold:.0%}")
        if g.enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback:
                should_enter_range_bound = True
                signals.append(f"RSI超买回落{prev_rsi:.1f}→{current_rsi:.1f}")
        if should_enter_range_bound:
            g.current_filter = '震荡期'           # 切换到震荡期（高斯滤波器）
            g.risk_state = '震荡期'               # 风险状态：震荡期
            g.range_bound_start_date = end_date
            g.range_bound_days_count = 0
            log.info(f"🔔 【首次运行】初始化进入震荡期: {'; '.join(signals)}")
        else:
            g.current_filter = '正常期'           # 正常期（拉普拉斯滤波器）
            g.risk_state = '正常期'               # 风险状态：正常期
            if len(close) >= g.lookback_high_low_days:
                g.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            else:
                g.previous_drawdown = 0
            g.previous_rsi = current_rsi
            log.info(f"📌 【首次运行】初始状态: 正常期(拉普拉斯滤波器), 乖离率: {bias:.2%}, RSI: {current_rsi:.1f}, 从低点涨幅: {rise_from_low:.2%}")
    except Exception as e:
        log.warning(f"【首次运行】初始化震荡期状态异常: {e}，保持正常期")

# ==================== 任务流水线 ====================
def morning_routine(context):
    """晨间准备流水线（09:00执行）：持仓检查 → 回撤监控 → 流动性阈值计算 → 动态池更新 → 固定池过滤 → 合并池"""
    log.info("★" * 80)
    log.info("▶️ 【晨间流水线】启动...")
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)    
    log.info("【回撤监控】监控策略回撤...")
    monitor_drawdown(context)
    log.info("【流动性阈值】计算全市场ETF+LOF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("【动态池更新】更新行业动态池...")
    update_sector_pool(context)
    log.info("【固定池过滤】过滤固定池流动性...")
    filter_fixed_pool_by_volume(context)
    log.info("【合并池】合并固定池与动态池...")
    daily_merge_etf_pools(context)
    log.info("⏸️ 【晨间流水线】执行完毕！")
def afternoon_routine(context):
    """午后交易流水线（13:10执行）：震荡期退出检查 → 震荡期进入检查 → 动量计算 → 卖出执行 → 买入执行"""
    log.info("▶️ 【午后交易流水线】启动...")
    log.info("【震荡期退出检查】检查是否需要退出震荡期...")
    check_and_exit_range_bound_mode(context)     
    log.info("【震荡期进入检查】检查是否需要进入震荡期...")
    check_and_enter_range_bound_mode(context)
    log.info("【动量计算】计算动量得分与排序...")
    calculate_and_log_ranked_etfs(context)
    log.info("【卖出执行】执行卖出操作...")
    execute_sell_trades(context)
    log.info("【买入执行】执行买入操作...")
    execute_buy_trades(context)
    log.info("⏸️ 【午后交易流水线】执行完毕！")
def reset_daily_flags(context):
    """收盘流水线（15:10执行）：重置价格缓存，更新震荡期统计"""
    # 重置价格缓存（防止次日止损计算使用错误数据）
    g.cache_date = None
    g.yesterday_close_cache = {}
    # 更新震荡期已持续天数
    if g.current_filter == '震荡期' and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
        g.range_bound_days_count = len(trade_days) - 1
        log.info(f"📊 震荡期已持续 {g.range_bound_days_count} 个交易日")
    log.info("🔄 收盘缓存重置完成")
    # 注意：止损标志 g.stop_loss_triggered_today 不在收盘时重置
    # 它会在次日13:10被 check_and_enter_range_bound_mode 检查后清零
# ==================== 持仓检查 ====================
def check_positions(context):
    """盘前持仓检查"""
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 【持仓检查】{security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")
def monitor_drawdown(context):
    """回撤监控：当策略回撤超过阈值时，记录"""
    try:
        current_value = context.portfolio.total_value
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value > 0:
            current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
            if current_drawdown >= g.drawdown_threshold:
                record = {
                    'date': context.current_dt.strftime('%Y-%m-%d'),
                    'drawdown': current_drawdown,
                    'portfolio_value': current_value,
                    'max_value': g.max_portfolio_value,
                    'current_filter': g.current_filter,
                    'risk_state': g.risk_state
                }
                positions_info = []
                for security in context.portfolio.positions:
                    position = context.portfolio.positions[security]
                    if position.total_amount > 0:
                        security_name = get_security_name(security)
                        positions_info.append(f"{security_name}:{position.total_amount}股")
                record['positions'] = positions_info
                g.drawdown_records.append(record)
                log.info(f"【回撤预警】回撤达到 {current_drawdown:.2%} (阈值: {g.drawdown_threshold:.0%})")
                log.info(f"  当前净值: {current_value:,.0f}  |  最高净值: {g.max_portfolio_value:,.0f}")
                log.info(f"  当前滤波器: {g.current_filter}  |  风险状态: {g.risk_state}")
                log.info(f"  持仓: {', '.join(positions_info) if positions_info else '空仓'}")
                log.info(f"{'='*70}\n")
    except Exception as e:
        log.error(f"【回撤监控】计算异常: {e}")
# ==================== 流动性阈值计算 ====================
def calculate_global_etf_threshold(context):
    """计算全市场ETF+LOF流动性阈值"""
    log.info("【全局阈值更新】开始计算全市场ETF+LOF流动性门槛")
    try:
        # 【修改点1】获取全市场ETF和LOF
        df_etf = get_all_securities(['etf', 'lof'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            log.warning("未找到任何场内ETF或LOF，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        log.info(f"全市场ETF+LOF总数: {len(etf_list)}只")
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date, frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            log.warning("无法获取历史成交额数据，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        daily_totals = df.groupby('time')['money'].sum()
        daily_counts = df[df['money'] > 0].groupby('time')['code'].nunique()
        for day, money in daily_totals.items():
            count = daily_counts.get(day, 0)
            log.info(f"  {day.date()} 全市场ETF+LOF总成交额: {money/1e8:.2f}亿元 ({count}只有成交)")
        if len(daily_totals) < 3:
            log.warning(f"仅有{len(daily_totals)}个有效交易日，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        threshold = avg_total_money / 20000
        g.avg_etf_money_threshold = threshold
        log.info(f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF+LOF日均总成交额={avg_total_money/1e8:.2f}亿元，阈值={threshold/1e4:.0f}万元({threshold:,.0f}元)")
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000
# ==================== 动态池更新 ====================
def update_sector_pool(context):
    """更新行业动态池（三层分组：宽基组 > 特别组 > 普通组）"""
    log.info("【动态池更新】开始执行")
    if g.avg_etf_money_threshold is None:
        log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    # ==================== 宽基ETF分类表 ====================
    BROAD_BASE_GROUPS = [
        {'name': '创业板综指', 'keywords': ['创业板ETF', '创业板综指', '创业综指', '创业板综', '创业板成长', '创业板价值', '创业板增强', '创业板指增']},
        {'name': '创业板50', 'keywords': ['创业板50', '创50', '创业板五零']},
        {'name': '创业板200', 'keywords': ['创业板200', '创200', '创业板两百']},
        {'name': '创业板大盘', 'keywords': ['创业板大盘', '创业大盘', '创大盘']},
        {'name': '科创50', 'keywords': ['科创50', '科创板50', '科创50E', '科创50指', '科创50基', '科创50增', '50科创', '科50']},
        {'name': '科创100', 'keywords': ['科创100', '科创100F', '科创100C', '科创100S', '科创100E', '科创100Z', '科100增', '科100FG', '科100']},
        {'name': '科创200', 'keywords': ['科创200', '科创200E', '科创200F', '科200GT', '科200E', '科200GF', '科200FG', '科200']},
        {'name': '双创', 'keywords': ['科创创业50', '双创50', '双创ETF', '双创基金', '双创']},
        {'name': 'MSCI系列', 'keywords': ['MSCI', 'MS', 'MSCIA股', 'MSCI国际', 'MSCI中国', 'MSCIETF']},
        {'name': 'A500', 'keywords': ['中证A500', 'A500E', 'A500增强', 'A500龙头', 'A500中证', 'A500基金', 'A500指数', '红利A500', '增强A500', 'A500增', 'A500']},
        {'name': '沪深300', 'keywords': ['沪深300', '300增强', '300质量', '300ESG', '300指增', '300价值', '300红利', '300成长', '300价值A', '300永赢', 'HS300', '300ETF增', '300ETF', '300增']},
        {'name': '中证500', 'keywords': ['中证500', '500增强', '国联500', 'ZZ500', '500指增']},
        {'name': '中证1000', 'keywords': ['中证1000', '1000增强', '1000成长', '1000价值', '1000鹏华', 'ZZ1000', '1000ETF', '1000基金', '增强1000', '1000指增']},
        {'name': '中证2000', 'keywords': ['中证2000', '国证2000', '2000增强', 'ZZ2000', '2000ETF', '2000基金', '2000指数', 'ZZ2000增强']},
        {'name': '中证800', 'keywords': ['中证800', '800价值', '800红利', '800低波', '800指数', 'ZZ800', '800ETF']},
        {'name': '上证50', 'keywords': ['上证50', '上50增强', 'SZ50', '上50', '沪50', 'SH50', '50指增', '50增强']},
        {'name': '上证180', 'keywords': ['上证180', '上180', '180ETF', '180基金', '180E', '180指数', '180指', '180ETF指']},
        {'name': '上证综指', 'keywords': ['上证综指', '上证综合', '上证ETF', '上证广发']},
        {'name': '深证100', 'keywords': ['深证100', '深100', '深100ETF', '深100指', '深100增']},
        {'name': '深证50', 'keywords': ['深证50', '深50ETF', '深50', '深证主板50']},
        {'name': '深证成指', 'keywords': ['深证成指', '深成指', '深成ETF', '深成长', '深成', '深证成']},
        {'name': 'A50', 'keywords': ['中证A50', 'MSCIA50', '中国A50', 'A50ETF', 'A50基金', 'A50龙头', 'A50中证', 'A50增', 'A50增强', 'A50']},
        {'name': 'A100', 'keywords': ['中证A100', 'A100ETF', 'A100指数', 'A100基金', '指基A100', 'A100']},
        {'name': '标普500', 'keywords': ['标普500']},
        {'name': '纳指', 'keywords': ['纳斯达克100', '纳斯达克', '纳指100', '纳指ETF', '纳指基金', '纳指指数', '美国50']},
    ]
    # 构建宽基关键词列表（长词优先）
    BROAD_BASE_KEYWORDS = []
    BROAD_BASE_CATEGORY_MAP = {}
    for group in BROAD_BASE_GROUPS:
        for kw in group['keywords']:
            BROAD_BASE_KEYWORDS.append(kw)
            BROAD_BASE_CATEGORY_MAP[kw] = group['name']
    BROAD_BASE_KEYWORDS.sort(key=len, reverse=True)
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
    # 噪音词列表
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)
    # 特别分组
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
    # 排除关键词（仅用于普通组）
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
        # 【修改点2】获取全市场ETF和LOF
        df_etf = get_all_securities(['etf', 'lof'])
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"获取全市场ETF+LOF列表失败: {e}")
        return
    log.info(f"【动态池更新】全市场ETF+LOF总数: {len(etf_list)}只")
    # 初始化分组
    broad_base_etfs, broad_base_categories_found = [], {}
    special_etfs, special_group_map = [], {}
    normal_etfs, excluded_etfs = [], []
    excluded_count = 0
    # ==================== 分类（优先级：宽基组 > 特别组 > 普通组）====================
    for code in etf_list:
        try:
            name = g.etf_names_dict.get(code, str(code))
            # 第一步：宽基组
            is_broad_base = False
            broad_base_category = None
            for kw in BROAD_BASE_KEYWORDS:
                if kw in name:
                    is_broad_base = True
                    broad_base_category = BROAD_BASE_CATEGORY_MAP.get(kw)
                    break
            if is_broad_base:
                broad_base_etfs.append(code)
                broad_base_categories_found[code] = broad_base_category
                continue
            # 第二步：特别组
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
            if is_special:
                special_etfs.append(code)
                special_group_map[code] = matched_group
                continue
            # 第三步：普通组
            is_excluded = False
            for k in exclude_keywords:
                if k in name:
                    is_excluded = True
                    excluded_count += 1
                    break
            if not is_excluded:
                normal_etfs.append(code)
            else:
                excluded_etfs.append(code)
        except Exception:
            continue
    # 输出分类统计
    log.info(f"原始ETF+LOF总数: {len(etf_list)}只")
    log.info(f"    ├─ 宽基组: {len(broad_base_etfs)}只")
    log.info(f"    ├─ 特别组: {len(special_etfs)}只")
    log.info(f"    ├─ 普通组: {len(normal_etfs)}只")
    log.info(f"    └─ 排除组: {excluded_count}只")
    # 流动性过滤
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold
    def filter_by_liquidity(etf_codes):
        if not etf_codes:
            return pd.Series(dtype=float), 0, {}, []
        try:
            price_data = get_price(etf_codes, end_date=end_date, count=TRADE_DAYS_COUNT,
                                   frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                return pd.Series(dtype=float), len(etf_codes), {}, etf_codes
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            qualified_series = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
            all_codes_set = set(etf_codes)
            qualified_set = set(qualified_series.index.tolist())
            removed_codes = list(all_codes_set - qualified_set)
            money_map = avg_daily_money.to_dict()
            return qualified_series, len(qualified_series), money_map, removed_codes
        except Exception:
            return pd.Series(dtype=float), len(etf_codes), {}, etf_codes
    broad_qualified_series, broad_q_count, broad_money_map, broad_removed = filter_by_liquidity(broad_base_etfs)
    special_qualified_series, special_q_count, special_money_map, special_removed = filter_by_liquidity(special_etfs)
    normal_qualified_series, normal_q_count, normal_money_map, normal_removed = filter_by_liquidity(normal_etfs)
    broad_qualified = broad_qualified_series.index.tolist()
    special_qualified = special_qualified_series.index.tolist()
    normal_qualified = normal_qualified_series.index.tolist()
    # 输出流动性过滤结果
    log.info(f"【动态池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    total_removed = len(broad_removed) + len(special_removed) + len(normal_removed)
    log.info(f"流动性过滤剔除: {total_removed}只")
    log.info(f"    ├─ 宽基组剔除: {len(broad_removed)}只，余{len(broad_qualified)}只")
    log.info(f"    ├─ 特别组剔除: {len(special_removed)}只，余{len(special_qualified)}只")
    log.info(f"    └─ 普通组剔除: {len(normal_removed)}只，余{len(normal_qualified)}只")
    # 名称清洗函数
    def clean_broad_base_name(original_name):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        return cleaned.strip()
    def clean_special_name(original_name, matched_group_name):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                for word in group['remove_words']:
                    cleaned = cleaned.replace(word, '')
                break
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()
    def clean_normal_name(original_name):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()
    # 宽基组处理（按分类分组，清洗后为空则使用分类名）
    broad_base_groups = {}
    broad_cleaned_empty = 0
    for code in broad_qualified:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            money = broad_qualified_series.get(code, 0)
            category = broad_base_categories_found.get(code, '其他')
            cleaned = clean_broad_base_name(original_name)
            if cleaned == '':
                cleaned = category
                broad_cleaned_empty += 1
            group_key = category
            if group_key not in broad_base_groups:
                broad_base_groups[group_key] = []
            broad_base_groups[group_key].append({'code': code, 'money': money, 'group_type': '宽基'})
        except Exception:
            continue
    # 特别组处理（按清洗后前2字符细分，清洗后为空则删除）
    special_groups = {}
    special_cleaned_empty = 0
    for code in special_qualified:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified_series.get(code, 0)
            cleaned = clean_special_name(original_name, matched_group)
            if cleaned == '':
                special_cleaned_empty += 1
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = f"{matched_group}_{industry_key}"
            if group_key not in special_groups:
                special_groups[group_key] = []
            special_groups[group_key].append({'code': code, 'money': money, 'group_type': matched_group})
        except Exception:
            continue
    # 普通组处理（按清洗后前2字符分组，清洗后为空则删除）
    normal_groups = {}
    normal_cleaned_empty = 0
    for code in normal_qualified:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            money = normal_qualified_series.get(code, 0)
            cleaned = clean_normal_name(original_name)
            if cleaned == '':
                normal_cleaned_empty += 1
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            if industry_key not in normal_groups:
                normal_groups[industry_key] = []
            normal_groups[industry_key].append({'code': code, 'money': money, 'group_type': '普通'})
        except Exception:
            continue
    # 输出名称清洗结果
    log.info(f"名称清洗删除: {special_cleaned_empty + normal_cleaned_empty}只")
    log.info(f"    ├─ 宽基组无清洗而是根据名称关键词分组: 余{len(broad_base_groups)}个分类")
    log.info(f"    ├─ 特别组删除: {special_cleaned_empty}只，余{len(special_groups)}个分组")
    log.info(f"    └─ 普通组删除: {normal_cleaned_empty}只，余{len(normal_groups)}个行业")
    # 每组选取成交额最大的1只
    final_pool_info = []
    for items in broad_base_groups.values():
        final_pool_info.append(max(items, key=lambda x: x['money']))
    for items in special_groups.values():
        final_pool_info.append(max(items, key=lambda x: x['money']))
    for items in normal_groups.values():
        final_pool_info.append(max(items, key=lambda x: x['money']))
    # 按成交额排序，取前100只
    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    top_100 = final_pool_info_sorted[:100]
    g.dynamic_etf_pool = [item['code'] for item in top_100]
    # 输出最终结果
    log.info(f"动态池最终结果：")
    log.info(f"    ├─ 宽基组贡献: {len(broad_base_groups)}个分类 → {len(broad_base_groups)}只")
    log.info(f"    ├─ 特别组贡献: {len(special_groups)}个分组 → {len(special_groups)}只")
    log.info(f"    └─ 普通组贡献: {len(normal_groups)}个行业 → {len(normal_groups)}只")
    log.info(f"最终动态池纳入: {len(g.dynamic_etf_pool)}只ETF+LOF")
# ==================== 固定池流动性过滤 ====================
def filter_fixed_pool_by_volume(context):
    """每日对固定池进行流动性过滤"""
    log.info("【固定池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        log.info("【固定池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.fixed_etf_pool:
        log.info("【固定池过滤】固定池为空，跳过过滤")
        return
    dynamic_threshold = g.avg_etf_money_threshold
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
            log.info(f"【固定池过滤】剔除低流动性标的({len(removed)}只)")
        g.filtered_fixed_pool = new_fixed_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        kept_info = []
        for code, money in sorted_qualified.items():
            try:
                name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                kept_info.append(f"{name}({code})日均{money/1e8:.2f}亿")
            except:
                kept_info.append(f"{code}日均{money/1e8:.2f}亿")
        log.info(f"【固定池过滤】保留高流动性标的({len(new_fixed_pool)}只)")
    except Exception as e:
        log.warning(f"【固定池过滤】异常: {e}")
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
        
# ==================== 合并池 ====================
def daily_merge_etf_pools(context):
    """每日合并固定池和动态池"""
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    log.info("【合并池】开始执行")
    log.info(f"【合并池统计】固定池: {len(g.filtered_fixed_pool)}只, 动态池: {len(g.dynamic_etf_pool)}只, 合并后: {len(merged)}只")
    g.merged_etf_pool = merged
# ==================== 退出震荡期检查 ====================
def check_and_exit_range_bound_mode(context):
    """在13:10检查是否需要退出震荡期"""
    if not g.enable_range_bound_mode:
        return
    if g.current_filter != '震荡期':
        return
    log.info("🔍 【震荡期退出检查】开始检测退出条件...")
    try:
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        end_date = context.previous_date
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback, frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            log.warning("【震荡期退出检查】数据不足，跳过检查")
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        if len(close) >= g.lookback_high_low_days:
            recent_high = np.max(high[-g.lookback_high_low_days:])
            recent_low = np.min(low[-g.lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        recovery_signals = []
        ma = np.mean(close[-g.ma_period:])
        current_rsi = calculate_rsi(close, period=14)
        log.info(f"📊 【震荡期数据】当前价: {current_price:.3f}, 近{g.lookback_high_low_days}日高点: {recent_high:.3f}, 低点: {recent_low:.3f}")
        log.info(f"📊 【震荡期数据】回撤: {current_drawdown:.2%}, 从低点涨幅: {rise_from_low:.2%}")
        if g.enable_low_point_rise_trigger:
            if rise_from_low >= g.low_point_rise_threshold:
                recovery_signals.append(f"从近{g.lookback_high_low_days}日低点上涨{rise_from_low:.2%}≥{g.low_point_rise_threshold:.0%}")
                log.info(f"✅ 【退出条件触发】从低点上涨: {rise_from_low:.2%}")
        if g.enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("价格站上均线")
                log.info(f"✅ 【企稳信号】价格站上均线({ma:.3f})")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
                log.info(f"✅ 【企稳信号】当日价格上涨: {((close[-1]/close[-2]-1)*100):.2f}%")
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                recovery_signals.append(f"回撤收窄({current_drawdown:.2%}<{g.previous_drawdown:.2%})")
                log.info(f"✅ 【企稳信号】回撤收窄: {g.previous_drawdown:.2%}→{current_drawdown:.2%}")
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                recovery_signals.append(f"RSI回升({current_rsi:.1f})")
                log.info(f"✅ 【企稳信号】RSI回升: {g.previous_rsi:.1f}→{current_rsi:.1f}")
            drawdown_safe = current_drawdown < g.drawdown_recovery
            if drawdown_safe:
                g.stable_days += 1
                log.info(f"📊 【企稳计数】连续企稳天数: {g.stable_days}")
            else:
                g.stable_days = 0
        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi
        range_bound_days = 0
        if hasattr(g, 'range_bound_start_date') and g.range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
            if range_bound_days >= g.max_range_bound_days:
                recovery_signals.append(f"震荡期满({range_bound_days}个交易日)")
                log.info(f"✅ 【退出条件触发】震荡期已满{range_bound_days}天")
        low_point_rise_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_signal_condition = False
        if g.enable_stable_signal_trigger:
            drawdown_safe = current_drawdown < g.drawdown_recovery
            stable_signal_condition = drawdown_safe and len(recovery_signals) >= 2 and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days
        should_recover = low_point_rise_condition or stable_signal_condition or force_condition
        if should_recover:
            can_switch = True
            if g.last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
                days_since_switch = len(trade_days) - 1
                if days_since_switch < g.filter_switch_cooldown:
                    can_switch = False
                    log.info(f"⏳ 【震荡期退出】冷却期中，距上次切换 {days_since_switch} 天")
            if can_switch:
                g.current_filter = '正常期'
                g.risk_state = '正常期'
                g.last_switch_date = context.current_dt.date()
                g.range_bound_start_date = None
                g.range_bound_days_count = 0
                g.stable_days = 0
                log.info(f"🔔 【退出震荡期】切换回拉普拉斯滤波器: {'; '.join(recovery_signals)}")
            else:
                log.info("⏳ 【震荡期退出】冷却期内，暂不切换")
        else:
            log.info("📌 【震荡期退出检查】未满足退出条件，保持震荡期(高斯滤波器)")
    except Exception as e:
        log.warning(f"【震荡期退出检查】判断出错: {e}")
# ==================== 进入震荡期检查 ====================
def check_and_enter_range_bound_mode(context):
    """在13:10检查是否需要进入震荡期"""
    if not g.enable_range_bound_mode:
        return
    log.info("🔍 【震荡期检查】开始检测进入条件...")
    can_switch = True
    if g.last_switch_date is not None:
        trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
        days_since_switch = len(trade_days) - 1
        if days_since_switch < g.filter_switch_cooldown:
            can_switch = False
            log.info(f"⏳ 【震荡期检查】冷却期中，距上次切换 {days_since_switch} 天 (需{g.filter_switch_cooldown}天)")
    if g.current_filter == '震荡期':  # 当前已是震荡期则返回
        log.info(f"📌 【震荡期检查】当前已在震荡期，滤波器: 高斯")
        return
    if not can_switch:
        return
    risk_signals = []
    try:
        lookback = max(g.ma_period, g.lookback_high_low_days) + 10
        end_date = context.previous_date
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback, frequency='daily', fields=['close'], panel=False)
        if df is not None and len(df) >= max(g.ma_period, g.lookback_high_low_days):
            close = df['close'].values
            current_price = close[-1]
            # 条件1: 乖离率过大
            if g.enable_bias_trigger:
                ma = np.mean(close[-g.ma_period:])
                bias = (current_price - ma) / ma if ma > 0 else 0
                if bias > g.bias_threshold:
                    risk_signals.append(f"乖离率过大({bias:.2%}>{g.bias_threshold:.0%})")
                    log.info(f"⚠️ 【条件触发】乖离率: {bias:.2%} (阈值>{g.bias_threshold:.0%})")
            # 条件2: RSI超买回落
            if g.enable_rsi_trigger:
                current_rsi = calculate_rsi(close, period=14)
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = calculate_rsi(close[:-1], period=14)
                    if prev_rsi is not None:
                        if prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                            risk_signals.append(f"RSI超买回落({prev_rsi:.1f}→{current_rsi:.1f})")
                            log.info(f"⚠️ 【条件触发】RSI超买回落: {prev_rsi:.1f}→{current_rsi:.1f}")
    except Exception as e:
        log.warning(f"【震荡期检查】获取基准数据异常: {e}")
    # 条件3: 持仓触发止损
    if g.enable_stop_loss_trigger and g.stop_loss_triggered_today:
        risk_signals.append("今日触发止损")
        log.info(f"⚠️ 【条件触发】今日已触发止损")
        g.stop_loss_triggered_today = False  # 检查后清零
    if len(risk_signals) > 0:
        g.current_filter = '震荡期'           # 切换到震荡期（高斯滤波器）
        g.risk_state = '震荡期'               # 风险状态：震荡期
        g.last_switch_date = context.current_dt.date()
        g.range_bound_start_date = context.current_dt.date()
        g.range_bound_days_count = 0
        g.stable_days = 0
        log.info(f"🔔 【进入震荡期】切换到高斯滤波器: {'; '.join(risk_signals)}")
    else:
        log.info("✅ 【震荡期检查】未满足进入条件，保持正常期(拉普拉斯滤波器)")
# ==================== 动量得分计算 ====================
def calculate_and_log_ranked_etfs(context):
    """计算合并池中的标的动量得分"""
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list
def calculate_momentum_score(price_series, lookback_days):
    """计算动量得分（100%还原 np.polyfit 权重逻辑和原版 R² 算法）"""
    if len(price_series) < lookback_days + 1:
        return None, None, None
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2  # np.polyfit底层实际生效的权重是传入参数的平方
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

def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    """计算单个标的所有动量指标"""
    try:
        price_series = np.append(hist_closes, current_price)
        if len(price_series) < max(g.lookback_days, g.short_momentum_lookback) * 0.8:
            return None
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_series, g.lookback_days)
        if momentum_score is None:
            return None
        short_momentum_score, short_annualized_returns, short_r_squared = calculate_momentum_score(price_series, g.short_momentum_lookback)
        passed_momentum = (g.min_score_threshold <= momentum_score <= g.max_score_threshold)
        passed_short_momentum = (g.short_momentum_min_score <= short_momentum_score <= g.short_momentum_max_score) if short_momentum_score is not None else False
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
        laplace_value = 0
        laplace_slope = 0
        passed_laplace = False
        gaussian_value = 0
        gaussian_slope = 0
        passed_gaussian = False
        if len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                if len(laplace_values) >= 2:
                    laplace_value = laplace_values[-1]
                    laplace_slope = laplace_values[-1] - laplace_values[-2]
                    passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
                g1, g2 = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
                gaussian_value = g1
                gaussian_slope = g1 - g2
                passed_gaussian = (current_price > g1 and gaussian_slope > g.gaussian_min_slope)
            except Exception as e:
                pass
        # 根据当前模式选择使用的滤波器
        if g.current_filter == '正常期':      # 正常期（拉普拉斯滤波器）
            filter_value = laplace_value
            filter_slope = laplace_slope
            passed_filter = passed_laplace
        else:                               # 震荡期（高斯滤波器）
            filter_value = gaussian_value
            filter_slope = gaussian_slope
            passed_filter = passed_gaussian
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
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'passed_premium': passed_premium,
            'laplace_value': laplace_value,
            'laplace_slope': laplace_slope,
            'gaussian_value': gaussian_value,
            'gaussian_slope': gaussian_slope,
            'passed_laplace': passed_laplace,
            'passed_gaussian': passed_gaussian,
            'filter_value': filter_value,
            'filter_slope': filter_slope,
            'passed_filter': passed_filter,
        }
    except Exception as e:
        log.debug(f"【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None
def get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
    """计算成交量比（动态计算已交易时间）"""
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
# ==================== 溢价率计算 ====================
def calculate_premium_rate(etf, context):
    """计算ETF/LOF溢价率"""
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
        return None, True  # 异常时默认通过溢价率校验
    
# ==================== 滤波器函数 ====================
def gaussian_filter(price, sigma=1.2):
    """高斯滤波器（震荡期使用）"""
    n = len(price)
    G = np.zeros(n)
    for t in range(n):
        weights = np.array([np.exp(-((i+1)**2) / (2 * sigma**2)) for i in range(t+1)])
        weights = weights[::-1]
        weights = weights / np.sum(weights)
        G[t] = np.sum(price[:t+1] * weights)
    return G

def gaussian_filter_last_two(price, sigma=1.2):
    """仅计算高斯滤波所需的最后两个点（效率优化）"""
    n = len(price)
    if n < 2: 
        return 0, 0
    idx_1 = np.arange(n)
    weights_1 = np.exp(-((idx_1+1)**2) / (2 * sigma**2))[::-1]
    weights_1 /= np.sum(weights_1)
    g1 = np.sum(price * weights_1)
    price_2 = price[:-1]
    idx_2 = np.arange(n-1)
    weights_2 = np.exp(-((idx_2+1)**2) / (2 * sigma**2))[::-1]
    weights_2 /= np.sum(weights_2)
    g2 = np.sum(price_2 * weights_2)
    return g1, g2

def laplace_filter(price, s=0.05):
    """拉普拉斯滤波器（正常期使用）"""
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L
def calculate_rsi(close, period=14):
    """计算RSI值"""
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
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except:
        return None
# ==================== 过滤条件应用 ====================
def apply_filters(metrics_list):
    """根据开关应用所有过滤条件"""
    use_short_momentum = g.use_short_momentum_period
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], not use_short_momentum),
        ('短期动量', lambda m: m['passed_short_momentum'], use_short_momentum),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
        ('溢价率', lambda m: m['passed_premium'], g.enable_premium_filter),
        ('动态滤波', lambda m: m['passed_filter'], g.enable_range_bound_mode),
    ]
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            before_count = len(filtered)
            filtered = [m for m in filtered if condition(m)]
            after_count = len(filtered)
            if before_count > after_count:
                log.debug(f"【过滤条件】{name}: 通过 {after_count}/{before_count}")
    return filtered

def get_final_ranked_etfs(context):
    """主筛选函数，从合并池中选出最终排名标的"""
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = context.previous_date
    log.info(f"【动量得分计算】使用合并池，合计{len(etf_set)}只ETF+LOF")
    log.info(f"【当前滤波器】{'拉普拉斯(正常期)' if g.current_filter == '正常期' else '高斯(震荡期)'}")
    use_short_momentum = g.use_short_momentum_period
    log.info(f"【动量模式】{'使用短期动量得分(21天,0-6分)' if use_short_momentum else '使用动量得分(25天,0-5分)'}")
    lookback = max(g.lookback_days, g.short_momentum_lookback, g.volume_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
    safe_lookback = lookback + 20
    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        log.warning("【动量计算】无法获取历史价格数据")
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
        if len(hist_closes) < max(g.lookback_days, g.short_momentum_lookback):
            continue
        etf_name = get_security_name(etf)
        current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        metrics = calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
        short_score = item.get('short_momentum_score')
        if pd.isna(short_score) or (isinstance(short_score, float) and np.isnan(short_score)):
            item['short_momentum_score'] = float('-inf')
    if use_short_momentum:
        all_metrics.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    log_buffer = []
    log_buffer.append("")
    log_buffer.append(f">>> 第一步：所有ETF+LOF按{'短期' if use_short_momentum else '原'}动量得分从大到小排序 <<<")
    for m in all_metrics[:100]:
        def fmt_status(value_str, passed):
            return f"{value_str} {'✅' if passed else '❌'}"
        score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
        short_score_str = f"{m['short_momentum_score']:.4f}" if m['short_momentum_score'] != float('-inf') else "nan"
        r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
        vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
        min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
        loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
        premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
        line = (
            f"{m['etf']} {m['etf_name']}: "
            f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
            f"短期动量: {fmt_status(short_score_str, m['passed_short_momentum'])}，"
            f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
            f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
            f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
            f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
            f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}，"
            f"高斯斜率: {m['gaussian_slope']:.4f} {fmt_status('', m['passed_gaussian'])}"
        )
        log_buffer.append(line)
    filtered_list = apply_filters(all_metrics)
    if use_short_momentum:
        filtered_list.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    top_10 = filtered_list[:10]
    log_buffer.append("")
    log_buffer.append(f">>> 第二步：符合全部过滤条件的ETF+LOF按{'短期' if use_short_momentum else '原'}动量得分从大到小排序(前10名) <<<")
    if top_10:
        for m in top_10:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            short_score_str = f"{m['short_momentum_score']:.4f}" if m['short_momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"短期动量: {fmt_status(short_score_str, m['passed_short_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
                f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
                f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}，"
                f"高斯斜率: {m['gaussian_slope']:.4f} {fmt_status('', m['passed_gaussian'])}"
            )
            log_buffer.append(line)
    else:
        log_buffer.append("（无符合条件的标的）")
        full_log = "\n".join(log_buffer)
        log.info(full_log)
        return []
    score_key = 'short_momentum_score' if use_short_momentum else 'momentum_score'
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        score_threshold = reference_score * g.score_threshold_ratio
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：选取{'短期' if use_short_momentum else '原'}动量得分≥第{g.holdings_num}名({top_10[g.holdings_num - 1]['etf_name']})得分{reference_score:.4f}×{g.score_threshold_ratio}={score_threshold:.4f}的标的 <<<")
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<")
        candidate_pool = top_10[:]
    log_buffer.append(f"【候选池】共{len(candidate_pool)}只标的（按{'短期' if use_short_momentum else '原'}动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")
    log_buffer.append("")
    log_buffer.append(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    log_buffer.append(f"当前持仓标的：{current_holdings}")
    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    log_buffer.append(f"其中存在于候选池中的持仓标的：{[item['etf'] for item in retained]}")
    if len(retained) >= g.holdings_num:
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
        log_buffer.append(f"保留的持仓标的数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的标的中按{'短期' if use_short_momentum else '原'}动量得分取前{g.holdings_num}只作为最终目标。")
    else:
        need = g.holdings_num - len(retained)
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        additional = remaining_pool[:need]
        final_result = retained + additional
        log_buffer.append(f"保留持仓标的 {len(retained)}只，还需补充{need}只。")
        if retained:
            log_buffer.append("保留的标的（按原有顺序）：")
            for item in retained:
                log_buffer.append(f"  {item['etf_name']}({item['etf']})")
        if additional:
            log_buffer.append("补充的标的（按动量得分排序）：")
            for i, item in enumerate(additional):
                log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")
    log_buffer.append(f"【最终目标】共{len(final_result)}只标的：")
    for i, item in enumerate(final_result):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']})")
    log_buffer.append("==================================================")
    full_log = "\n".join(log_buffer)
    log.info(full_log)
    return final_result

# ==================== 交易执行 ====================
def execute_sell_trades(context):
    """卖出交易逻辑"""
    log.info("========== 卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    target_etfs = []
    if ranked_etfs:
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}")
    else:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            etf_name = get_security_name(g.defensive_etf)
            log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
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
            success = smart_order_target_value(security, 0, context)
            if success:
                sell_count += 1
                log.info(f"✅ 已成功卖出: {security} {security_name}")
    log.info(f"本次共计划卖出{sell_count}只。")
    log.info("========== 卖出操作完成 ==========")
def execute_buy_trades(context):
    """买入交易逻辑"""
    log.info("========== 买入操作开始 ==========")
    target_etfs = g.target_etfs_list
    if not target_etfs:
        log.info("根据计算的结果，今日无目标标的，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return
    current_positions = set(context.portfolio.positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("========== 买入操作完成 ==========")
        return
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标持仓: {g.holdings_num}只, 本次计划买入: {num_etfs_to_buy}只")
    available_cash = context.portfolio.available_cash
    allocated_value_per_etf = available_cash // num_etfs_to_buy
    log.info(f"账户可用现金: {available_cash:.2f}, 分配给每只标的的资金: {allocated_value_per_etf:.2f}")
    if allocated_value_per_etf < g.min_money:
        log.info(f"单只标的分配金额{allocated_value_per_etf:.2f}小于最小交易额{g.min_money:.2f}，无法买入")
        log.info("========== 买入操作完成 ==========")
        return
    for i, etf in enumerate(etfs_to_buy):
        target_value_for_this_etf = allocated_value_per_etf
        if i == len(etfs_to_buy) - 1 and context.portfolio.available_cash >= g.min_money:
            target_value_for_this_etf = context.portfolio.available_cash
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ {etf} 下单成功")
        else:
            log.info(f"❌ {etf} 下单失败")
    log.info("========== 买入操作完成 ==========")
def smart_order_target_value(security, target_value, context):
    """智能下单"""
    current_data = get_current_data()
    security_name = get_security_name(security)
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
    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.min_money:
        log.info(f"{security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过")
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
            if amount_diff > 0:
                log.info(f"📦 买入{security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
            else:
                log.info(f"📤 卖出{security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}")
            return True
        else:
            log.warning(f"下单失败: {security} {security_name}，数量: {amount_diff}")
            return False
    return False
# ==================== 止损函数 ====================
def minute_level_stop_loss(context):
    """分钟级固定比例止损"""
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
            success = smart_order_target_value(security, 0, context)
            if success and g.enable_stop_loss_trigger:
                g.stop_loss_triggered_today = True
                log.info(f"✅ 【止损触发】记录今日止损，将在13:10检查并进入震荡期")

def minute_level_pct_stop_loss(context):
    """分钟级当日跌幅止损"""
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
            success = smart_order_target_value(security, 0, context)
            if success and g.enable_stop_loss_trigger:
                g.stop_loss_triggered_today = True
                log.info(f"✅ 【止损触发】记录今日止损，将在13:10检查并进入震荡期")
# ==================== 辅助函数 ====================
def get_security_name(security):
    """安全获取证券名称"""
    try:
        if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"
def check_defensive_etf_available(context):
    """检查防御性标的是否可交易"""
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    if current_data[defensive_etf].paused:
        log.info(f"防御性标的 {defensive_etf} 今日停牌")
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        log.info(f"防御性标的 {defensive_etf} 当前涨停")
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        log.info(f"防御性标的 {defensive_etf} 当前跌停")
        return False
    return True

def trade(context):
    pass