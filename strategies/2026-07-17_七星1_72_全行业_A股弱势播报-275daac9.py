# Clone from JoinQuant
# postId: 275daac96f0cc4919ca057a03354dbb1
# backtestId: eee2219fd8d177dfa7db8c6f25b90729
# title: 七星1.72+全行业+A股弱势播报

# 克隆自聚宽文章：https://www.joinquant.com/post/72011
# 标题：最能打策略三马七星2个月推荐经典五福3.5七星172合一
# 作者：感恩遇见

# 克隆自聚宽文章：https://www.joinquant.com/post/70329
# 标题：60倍七星高照+高斯+拉普拉斯
# 作者：king088

# 克隆自聚宽文章：https://www.joinquant.com/post/69163
# 标题：【策略优化】ETF轮动策略优化-V1.7.2
# 作者：晨曦量化

import numpy as np
import math
import datetime
import pandas as pd
from jqdata import *

# ==================== 初始化模块 ====================
def initialize(context):
    """
    初始化函数：设置交易参数、ETF池、核心参数、调度任务
    """
    # ---------- 交易设置 ----------
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    set_benchmark("161226.XSHE")

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("========== 策略初始化开始 ==========")

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
        # 大ETF池
    g.etf_pool  = [
        # 大宗商品ETF
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF（跟踪有色金属板块）
        "159985.XSHE",  # 豆粕ETF（跟踪豆粕期货价格）
        "501018.XSHG",  # 南方原油（投资原油相关资产）
        '161226.XSHE',  # 白银LOF
        "159981.XSHE",  # 能源化工ETF
        # 国际ETF
        "513100.XSHG",  # 纳指ETF（成交额最大）
        "513500.XSHG",  # 标普500ETF
        "513400.XSHG",  # 道琼斯ETF
        "513880.XSHG",  # 日经225ETF
        "513030.XSHG",  # 德国30ETF
        "513080.XSHG",  # 法国ETF
        "513310.XSHG",  # 中韩半导体ETF
        "513730.XSHG",  # 东南亚ETF
        "518880.XSHG",  # 黄金ETF
        "513350.XSHG",  # 标普油气ETF
        "159529.XSHE",  # 标普消费ETF
        "159502.XSHE",  # 标普生物科技ETF
        "159100.XSHE",  # 巴西ETF
        "159329.XSHE",  # 沙特ETF
        # 香港ETF
        "159792.XSHE",  # 港股互联ETF（成交额最大）
        "513180.XSHG",  # 恒生科技ETF
        "513050.XSHG",  # 中概互联网ETF
        "159920.XSHE",  # 恒生ETF
        "513120.XSHG",  # 港股创新药ETF
        "513630.XSHG",  # 港股低波红利ETF
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
    ]

    # ---------- ETF分类映射（用于弱势期过滤）----------
    g.domestic_etf_codes = set([
        "510300.XSHG",  # 沪深300ETF
        "510500.XSHG",  # 中证500ETF
        "510050.XSHG",  # 上证50ETF
        "510210.XSHG",  # 上证ETF
        "159915.XSHE",  # 创业板ETF
        "588080.XSHG",  # 科创50
        "512100.XSHG",  # 中证1000ETF
        "563360.XSHG",  # A500-ETF
        "563300.XSHG",  # 中证2000ETF
    ])
    g.overseas_commodity_etf_codes = set(g.etf_pool) - g.domestic_etf_codes

    # ========== A股行情判断参数 ==========
    g.enable_regime_switch = True                    # 行情判断开关
    g.weak_period_ma_lookback = 10                   # 10日均线
    g.weak_period_max_days = 15                      # 走弱期最长持续15个交易日
    g.is_a_share_weak = False                        # 当前是否走弱期
    g.a_share_weak_daily_lock = False                # 09:40日频走弱后当日禁止盘中假恢复
    g.weak_period_counter = 0                        # 走弱期天数计数器
    g.a_share_weak_enter_count = 3                   # ≥3/6 指数走弱进入A股弱
    g.a_share_weak_exit_count = 2                    # 日频退出：≥2/6 MA5/10回升
    g.a_share_intraday_exit_count = 2                # 盘中退出：≥2/6（与日频一致）
    g.enable_avoid_a_share = True                    # 走弱期回避A股开关
    g.regime_indexes = {                             # 监测指数（6指数 + 价破线/MA5死叉双条件）
        '上证指数': '000001.XSHG',
        '沪深300': '000300.XSHG',
        '深证成指': '399001.XSHE',
        '深证综指': '399101.XSHE',
        '创业板指': '399006.XSHE',
        '中证A500': '000510.XSHG',
    }

    # ========== 弱势期统计相关 ==========
    g.regime_score_detail = {}                    # {etf_code: [day1_score, day2_score, ...]} 每日得分明细
    g.regime_trading_dates = []                   # 弱势期内的交易日列表
    g.regime_min_volume_million = 1000            # 最低成交额门槛（万元）

    # ========== 行业ETF池（用于高相似性分析，不直接交易）==========
    g.industry_etf_pool = [
        "588200.XSHG",   # 科创芯片ETF嘉实
        "588170.XSHG",   # 科创半导体ETF华夏
        "515880.XSHG",   # 通信ETF国泰
        "159516.XSHE",   # 半导体设备ETF国泰
        "512880.XSHG",   # 证券ETF国泰
        "159995.XSHE",   # 芯片ETF华夏
        "512480.XSHG",   # 半导体ETF国联安
        "512400.XSHG",   # 有色金属ETF南方
        "512890.XSHG",   # 红利低波ETF华泰柏瑞
        "515050.XSHG",   # 通信ETF华夏
        "159363.XSHE",   # 创业板人工智能ETF华宝
        "512800.XSHG",   # 银行ETF华宝
        "159611.XSHE",   # 电力ETF广发
        "510880.XSHG",   # 红利ETF华泰柏瑞
        "512000.XSHG",   # 券商ETF华宝
        "159326.XSHE",   # 电网设备ETF华夏
        "159870.XSHE",   # 化工ETF鹏华
        "159530.XSHE",   # 机器人ETF易方达
        "159206.XSHE",   # 卫星ETF永赢
        "159819.XSHE",   # 人工智能ETF易方达
        "159558.XSHE",   # 半导体设备ETF易方达
        "512760.XSHG",   # 芯片ETF国泰
        "562500.XSHG",   # 机器人ETF华夏
        "512690.XSHG",   # 酒ETF鹏华
        "515220.XSHG",   # 煤炭ETF国泰
        "159732.XSHE",   # 消费电子ETF华夏
        "512070.XSHG",   # 证券保险ETF易方达
        "159992.XSHE",   # 创新药ETF银华
        "159259.XSHE",   # 成长ETF易方达
        "562590.XSHG",   # 半导体设备ETF华夏
        "562800.XSHG",   # 稀有金属ETF嘉实
        "159381.XSHE",   # 创业板人工智能ETF华夏
        "159755.XSHE",   # 电池ETF广发
        "515180.XSHG",   # 红利ETF易方达
        "515080.XSHG",   # XD中证红利ETF招商
        "560860.XSHG",   # 工业有色ETF万家
        "588290.XSHG",   # 科创芯片ETF华安
        "159813.XSHE",   # 半导体ETF鹏华
        "588790.XSHG",   # 科创AIETF博时
        "588710.XSHG",   # 科创半导体设备ETF华泰柏瑞
        "560780.XSHG",   # 半导体设备ETF广发
        "517520.XSHG",   # 黄金股ETF永赢
        "159842.XSHE",   # 券商ETF银华
        "512170.XSHG",   # 医疗ETF华宝
        "515980.XSHG",   # 人工智能ETF华富
        "159583.XSHE",   # 通信ETF富国
        "515450.XSHG",   # 红利低波50ETF南方
        "512010.XSHG",   # 医药ETF易方达
        "510720.XSHG",   # 红利国企ETF国泰
        "515120.XSHG",   # 创新药ETF广发
        "159566.XSHE",   # 储能电池ETF易方达
        "159796.XSHE",   # 电池ETF汇添富
        "588750.XSHG",   # 科创芯片ETF汇添富
        "561980.XSHG",   # 半导体设备ETF招商
        "159201.XSHE",   # 自由现金流ETF华夏
        "516150.XSHG",   # 稀土ETF嘉实
        "589020.XSHG",   # 科创半导体设备ETF鹏华
        "588800.XSHG",   # 科创100ETF华夏
        "515070.XSHG",   # 人工智能ETF华夏
        "159801.XSHE",   # 芯片ETF广发
        "159227.XSHE",   # 航空航天ETF华夏
        "159994.XSHE",   # 通信ETF银华
        "512710.XSHG",   # 军工龙头ETF富国
        "159246.XSHE",   # 创业板人工智能ETF富国
        "562880.XSHG",   # 电池ETF嘉实
        "159869.XSHE",   # 游戏ETF华夏
        "588760.XSHG",   # 科创人工智能ETF广发
        "512660.XSHG",   # 军工ETF国泰
        "159387.XSHE",   # 创业板新能源ETF国泰
        "563230.XSHG",   # 卫星ETF富国
        "159852.XSHE",   # 软件ETF嘉实
        "159667.XSHE",   # 工业母机ETF国泰
        "159928.XSHE",   # 消费ETF汇添富
        "159382.XSHE",   # 创业板人工智能ETF南方
        "588780.XSHG",   # 科创芯片设计ETF国联安
        "589720.XSHG",   # 科创创新药ETF国泰
        "159608.XSHE",   # 稀有金属ETF广发
        "159841.XSHE",   # 证券ETF天弘
        "561560.XSHG",   # 电力ETF华泰柏瑞
        "516350.XSHG",   # 芯片ETF易方达
        "515790.XSHG",   # 光伏ETF华泰柏瑞
        "159770.XSHE",   # 机器人ETF天弘
        "562550.XSHG",   # 绿电ETF华夏
        "515100.XSHG",   # 红利低波100ETF景顺
        "159652.XSHE",   # 有色ETF汇添富
        "515000.XSHG",   # 科技ETF华宝
        "512930.XSHG",   # AI人工智能ETF平安
        "588730.XSHG",   # 科创人工智能ETF易方达
        "159368.XSHE",   # 创业板新能源ETF华夏
        "159715.XSHE",   # 稀土ETF易方达
        "159263.XSHE",   # 价值ETF易方达
        "588890.XSHG",   # 科创芯片ETF南方
        "159325.XSHE",   # 半导体ETF南方
        "512040.XSHG",   # 价值100ETF富国
        "159399.XSHE",   # 现金流ETF国泰
        "516650.XSHG",   # 有色金属ETF华夏
        "562950.XSHG",   # 消费电子ETF易方达
        "516780.XSHG",   # 稀土ETF华泰柏瑞
        "159599.XSHE",   # 芯片ETF东财
        "516640.XSHG",   # 芯片ETF富国
        "159307.XSHE",   # 红利低波100ETF博时
        "515300.XSHG",   # 300红利低波ETF嘉实
        "159232.XSHE",   # 自由现金流ETF南方
        "512200.XSHG",   # 房地产ETF南方
        "588020.XSHG",   # 科创成长ETF易方达
        "159851.XSHE",   # 金融科技ETF华宝
        "159218.XSHE",   # 卫星ETF招商
        "512980.XSHG",   # 传媒ETF广发
        "561380.XSHG",   # 电网设备ETF国泰
        "159327.XSHE",   # 半导体设备ETF万家
        "515030.XSHG",   # 新能源车ETF华夏
        "159272.XSHE",   # 机器人ETF富国
        "588010.XSHG",   # 科创新材料ETF博时
        "159559.XSHE",   # 机器人ETF景顺
        "159242.XSHE",   # 创业板人工智能ETF大成
        "159388.XSHE",   # 创业板人工智能ETF国泰
        "516160.XSHG",   # 新能源ETF南方
        "561910.XSHG",   # 电池ETF招商
        "159997.XSHE",   # 电子ETF天弘
        "561100.XSHG",   # 消费电子ETF富国
        "515230.XSHG",   # 软件ETF国泰
        "516020.XSHG",   # 化工ETF华宝
        "159278.XSHE",   # 机器人ETF鹏华
        "159713.XSHE",   # 稀土ETF富国
        "588810.XSHG",   # 科创芯片ETF富国
        "512290.XSHG",   # 生物医药ETF国泰
        "159859.XSHE",   # 生物医药ETF天弘
        "516120.XSHG",   # 化工ETF富国
        "159998.XSHE",   # 计算机ETF天弘
        "516510.XSHG",   # 云计算ETF易方达
        "512570.XSHG",   # 证券ETF易方达
        "512090.XSHG",   # MSCIA股ETF易方达
        "510230.XSHG",   # 金融ETF国泰
        "560050.XSHG",   # 中国A50ETF汇添富
        "159562.XSHE",   # 黄金股ETF华夏
        "589010.XSHG",   # 科创人工智能ETF华夏
        "516310.XSHG",   # 银行ETF易方达
        "159766.XSHE",   # 旅游ETF富国
        "588230.XSHG",   # 科创200ETF华泰柏瑞
        "560090.XSHG",   # 证券ETF汇添富
        "159930.XSHE",   # 能源ETF汇添富
        "515020.XSHG",   # 银行ETF华夏
        "159865.XSHE",   # 养殖ETF国泰
        "159267.XSHE",   # 航天ETF华安
        "515010.XSHG",   # 证券ETF华夏
        "159597.XSHE",   # 创业板成长ETF易方达
        "159993.XSHE",   # 证券ETF鹏华
        "515260.XSHG",   # 电子ETF华宝
        "159731.XSHE",   # 石化ETF华夏
        "159320.XSHE",   # 电网设备ETF广发
        "159840.XSHE",   # 锂电池ETF工银
        "515700.XSHG",   # 新能源车ETF平安
        "561360.XSHG",   # 石油ETF国泰
        "159695.XSHE",   # 通信ETF嘉实
        "515210.XSHG",   # 钢铁ETF国泰
        "159221.XSHE",   # 现金流ETF嘉实
        "159887.XSHE",   # 银行ETF富国
        "588830.XSHG",   # 科创新能源ETF鹏华
        "512820.XSHG",   # 银行ETF汇添富
        "588930.XSHG",   # 科创人工智能ETF银华
        "159663.XSHE",   # 机床ETF华夏
        "516080.XSHG",   # 创新药ETF易方达
        "563760.XSHG",   # 全指现金流ETF中银
        "159241.XSHE",   # 航空航天ETF天弘
        "588990.XSHG",   # 科创芯片ETF博时
        "159207.XSHE",   # 高股息ETF广发
        "563390.XSHG",   # 全指现金流ETF华泰柏瑞
        "159305.XSHE",   # 储能电池ETF广发
        "159546.XSHE",   # 集成电路ETF国泰
        "159209.XSHE",   # 红利质量ETF招商
        "562960.XSHG",   # 绿色电力ETF易方达
        "516810.XSHG",   # 农业ETF华夏
        "159665.XSHE",   # 半导体龙头ETF工银
        "561330.XSHG",   # 矿业ETF国泰
        "560280.XSHG",   # 工程机械ETF广发
        "159883.XSHE",   # 医疗器械ETF永赢
        "159235.XSHE",   # 中证现金流ETF大成
        "159507.XSHE",   # 通信ETF广发
        "159875.XSHE",   # 新能源ETF嘉实
        "159857.XSHE",   # 光伏ETF天弘
        "561580.XSHG",   # 央企红利ETF华泰柏瑞
        "159876.XSHE",   # 有色ETF华宝
        "561170.XSHG",   # 绿色电力ETF富国
        "512700.XSHG",   # 银行ETF南方
        "516820.XSHG",   # 医疗创新ETF平安
        "515290.XSHG",   # 银行ETF天弘
        "517400.XSHG",   # 黄金股ETF国泰
        "159582.XSHE",   # 半导体ETF博时
        "515170.XSHG",   # 食品饮料ETF华夏
        "159279.XSHE",   # 创业板人工智能ETF华安
        "159625.XSHE",   # 绿色电力ETF嘉实
        "512670.XSHG",   # 国防ETF鹏华
        "159807.XSHE",   # 科技ETF易方达
        "515400.XSHG",   # 大数据ETF富国
        "159622.XSHE",   # 创新药ETF东财
        "516920.XSHG",   # 芯片ETF汇添富
        "159601.XSHE",   # A50ETF华夏
        "159692.XSHE",   # 证券ETF东财
        "159222.XSHE",   # 自由现金流ETF易方达
        "159671.XSHE",   # 稀有金属ETF工银
        "561160.XSHG",   # 电池ETF富国
        "159839.XSHE",   # 生物医药ETF汇添富
        "159256.XSHE",   # 创业板软件ETF华夏
        "516520.XSHG",   # 智能驾驶ETF华泰柏瑞
        "563000.XSHG",   # 中国A50ETF易方达
        "515650.XSHG",   # 消费50ETF富国
        "515630.XSHG",   # 证券保险ETF鹏华
        "589520.XSHG",   # 科创人工智能ETF华宝
        "159929.XSHE",   # 医药ETF汇添富
        "589100.XSHG",   # 科创芯片ETF国泰
        "516010.XSHG",   # 游戏ETF国泰
        "588160.XSHG",   # 科创新材料ETF南方
        "562820.XSHG",   # 集成电路ETF嘉实
        "159880.XSHE",   # 有色ETF鹏华
        "159540.XSHE",   # 信创ETF易方达
        "159996.XSHE",   # 家电ETF国泰
        "159697.XSHE",   # 石油ETF鹏华
        "515060.XSHG",   # 房地产ETF华夏
        "561600.XSHG",   # 消费电子ETF平安
        "159828.XSHE",   # 医疗ETF国泰
        "516090.XSHG",   # 新能源ETF易方达
        "159939.XSHE",   # 信息技术ETF广发
        "589120.XSHG",   # 科创创新药ETF汇添富
        "516570.XSHG",   # 化工行业ETF易方达
        "159871.XSHE",   # 有色ETF银华
        "516630.XSHG",   # 云计算ETF华夏
        "562510.XSHG",   # 旅游ETF华夏
        "560170.XSHG",   # 央企科技ETF南方
        "588850.XSHG",   # 科创机械ETF嘉实
        "159745.XSHE",   # 建材ETF国泰
        "512900.XSHG",   # 证券ETF南方
        "588920.XSHG",   # 科创芯片ETF鹏华
        "159638.XSHE",   # 高端装备ETF嘉实
        "560080.XSHG",   # 中药ETF汇添富
        "159526.XSHE",   # 机器人ETF嘉实
        "563330.XSHG",   # A股ETF华泰柏瑞
        "560770.XSHG",   # 机器人ETF招商
        "512560.XSHG",   # 军工ETF易方达
        "159707.XSHE",   # 地产ETF华宝
        "517380.XSHG",   # 创新药ETF天弘
        "159273.XSHE",   # 云计算ETF汇添富
        "588110.XSHG",   # 科创成长ETF广发
        "159107.XSHE",   # 创业板软件ETF富国
        "516110.XSHG",   # 汽车ETF国泰
        "159779.XSHE",   # 消费电子ETF招商
        "512680.XSHG",   # 军工ETF广发
        "516860.XSHG",   # 金融科技ETF博时
        "589180.XSHG",   # 科创新材料ETF汇添富
        "516970.XSHG",   # 基建ETF广发
        "159233.XSHE",   # 自由现金流ETF平安
        "515850.XSHG",   # 证券ETF富国
        "562930.XSHG",   # 软件ETF易方达
        "159560.XSHE",   # 芯片ETF景顺
        "159309.XSHE",   # 油气ETF汇添富
        "159690.XSHE",   # 有色矿业ETF招商
        "159758.XSHE",   # 红利质量ETF华夏
        "159938.XSHE",   # 医药ETF广发
        "159549.XSHE",   # 红利低波ETF天弘
        "588240.XSHG",   # 科创200ETF鹏华
        "159825.XSHE",   # 农业ETF富国
        "589900.XSHG",   # 科创综指ETF博时
        "512810.XSHG",   # 军工ETF华宝
        "159590.XSHE",   # 软件ETF汇添富
        "560120.XSHG",   # 中证500现金流ETF华夏
        "159213.XSHE",   # 机器人ETF汇添富
        "159310.XSHE",   # 芯片ETF天弘
        "159739.XSHE",   # 云计算ETF鹏华
        "561800.XSHG",   # 稀有金属ETF华富
        "562080.XSHG",   # 300现金流ETF华宝
        "588820.XSHG",   # 科创200ETF华夏
        "516670.XSHG",   # 畜牧养殖ETF招商
        "512220.XSHG",   # TMTETF景顺
        "588770.XSHG",   # 科创信息ETF摩根
        "159811.XSHE",   # 5GETF博时
        "588700.XSHG",   # 科创医药ETF嘉实
        "159888.XSHE",   # 智能汽车ETF华夏
        "512720.XSHG",   # 计算机ETF国泰
        "510630.XSHG",   # 消费ETF华夏
        "159698.XSHE",   # 粮食ETF鹏华
        "159248.XSHE",   # 人工智能ETF万家
        "159837.XSHE",   # 生物科技ETF易方达
        "159738.XSHE",   # 云计算ETF华泰柏瑞
        "563900.XSHG",   # 300自由现金流ETF摩根
        "159378.XSHE",   # 通用航空ETF永赢
        "513220.XSHG",   # 中概互联ETF招商
        "589960.XSHG",   # 科创新能源ETF易方达
        "159635.XSHE",   # 基建ETF华夏
        "159905.XSHE",   # 红利ETF工银
        "159847.XSHE",   # 医疗ETF易方达
        "159551.XSHE",   # 机器人ETF国泰
        "159790.XSHE",   # 碳中和ETF华夏
        "515710.XSHG",   # 食品饮料ETF华宝
        "159748.XSHE",   # 创新药ETF富国
        "159864.XSHE",   # 光伏ETF国泰
        "510150.XSHG",   # 消费ETF招商
        "159786.XSHE",   # VRETF银华
        "159602.XSHE",   # 中国A50ETF南方
        "515890.XSHG",   # 红利ETF博时
        "159581.XSHE",   # 红利ETF万家
        "516910.XSHG",   # 物流ETF富国
        "561090.XSHG",   # A500增强ETF华安
        "159321.XSHE",   # 黄金股ETF华安
        "562600.XSHG",   # 医疗器械ETF华夏
        "159565.XSHE",   # 汽车零部件ETF易方达
        "159768.XSHE",   # 房地产ETF银华
        "516100.XSHG",   # 金融科技ETF华夏
        "588270.XSHG",   # 科创200ETF易方达
        "561130.XSHG",   # 国货ETF富国
        "159890.XSHE",   # 云计算ETF招商
        "159761.XSHE",   # 新材料ETF国泰
        "516000.XSHG",   # 大数据ETF华夏
        "515320.XSHG",   # 电子50ETF华安
        "159805.XSHE",   # 传媒ETF鹏华
        "159258.XSHE",   # 机器人ETF南方
        "159945.XSHE",   # 能源ETF广发
        "159867.XSHE",   # 养殖ETF鹏华
        "561570.XSHG",   # 油气ETF华泰柏瑞
        "512330.XSHG",   # 信息科技ETF南方
        "159775.XSHE",   # 电池ETF建信
        "159230.XSHE",   # 通用航空ETF华夏
        "516800.XSHG",   # 智能制造ETF华宝
        "563210.XSHG",   # 专精特新ETF富国
        "159208.XSHE",   # 航空航天ETF万家
        "515250.XSHG",   # 智能汽车ETF富国
        "159588.XSHE",   # 石油ETF景顺
        "159835.XSHE",   # 创新药ETF建信
        "562360.XSHG",   # 机器人ETF银华
        "561310.XSHG",   # 消电ETF国泰
        "562350.XSHG",   # 电力ETF银华
        "510170.XSHG",   # 大宗商品ETF国联安
        "159881.XSHE",   # 有色金属ETF国泰
        "560980.XSHG",   # 光伏龙头ETF广发
        "589560.XSHG",   # 科创人工智能ETF汇添富
        "588910.XSHG",   # 科创价值ETF建信
        "560800.XSHG",   # 数字经济ETF鹏扬
        "159736.XSHE",   # 食品饮料ETF天弘
        "159899.XSHE",   # 软件ETF招商
        "516770.XSHG",   # 游戏ETF华泰柏瑞
        "560570.XSHG",   # A500红利ETF国联安
        "159511.XSHE",   # 通信ETF南方
        "159806.XSHE",   # 新能源车ETF国泰
        "159301.XSHE",   # 公用事业ETF华夏
        "516880.XSHG",   # 光伏ETF银华
        "563580.XSHG",   # 自由现金流800ETF万家
        "516850.XSHG",   # 新能源ETF华夏
        "562570.XSHG",   # 信创ETF华夏
        "159538.XSHE",   # 信创ETF富国
        "513360.XSHG",   # 教育ETF博时
        "561700.XSHG",   # 电力ETF博时
        "588100.XSHG",   # 科创信息ETF嘉实
        "562700.XSHG",   # 汽车零部件ETF华夏
        "530880.XSHG",   # 红利国企ETF银河
        "159539.XSHE",   # 信创ETF广发
        "517900.XSHG",   # 银行AH优选ETF招商
        "516290.XSHG",   # 光伏ETF汇添富
        "516130.XSHG",   # 消费龙头ETF华宝
        "159587.XSHE",   # 粮食ETF广发
        "589600.XSHG",   # 科创综指ETF富国
        "159525.XSHE",   # 红利低波ETF富国
        "562970.XSHG",   # 光伏ETF易方达
        "515580.XSHG",   # 科技100ETF华泰柏瑞
        "512990.XSHG",   # MSCIA股ETF华夏
        "516190.XSHG",   # 传媒ETF华夏
        "563320.XSHG",   # 通用航空ETF华泰柏瑞
        "516050.XSHG",   # 科技龙头ETF工银
        "159537.XSHE",   # 信创ETF国泰
        "159623.XSHE",   # 成渝经济圈ETF博时
        "159315.XSHE",   # 黄金股ETF工银
        "159757.XSHE",   # 电池ETF景顺
        "159858.XSHE",   # 创新药ETF南方
        "516620.XSHG",   # 影视ETF国泰
        "159385.XSHE",   # 数字经济ETF富国
        "589110.XSHG",   # 科创人工智能ETF国泰
        "516210.XSHG",   # 银行ETF华安
        "512950.XSHG",   # 央企改革ETF华夏
        "159666.XSHE",   # 交通运输ETF华夏
        "516460.XSHG",   # 现金流ETF800鹏华
        "588960.XSHG",   # 科创新能源ETF富国
        "562850.XSHG",   # 央企能源ETF嘉实
        "159299.XSHE",   # 金融科技ETF易方达
        "159226.XSHE",   # 中证A500增强ETF国泰
        "159898.XSHE",   # 医疗器械ETF招商
        "159249.XSHE",   # A500增强ETF工银
        "512550.XSHG",   # 富时A50ETF嘉实
        "512120.XSHG",   # 医药ETF华安
        "517800.XSHG",   # 人工智能50ETF方正富邦
        "159283.XSHE",   # 通用航空ETF南方
        "563010.XSHG",   # 电信ETF易方达
        "560580.XSHG",   # 电力ETF南方
        "510660.XSHG",   # 医药ETF华夏
        "516950.XSHG",   # 基建ETF银华
        "510410.XSHG",   # 资源ETF博时
        "159527.XSHE",   # 云计算ETF广发
        "159377.XSHE",   # 创业板医药ETF国泰
        "516220.XSHG",   # 化工ETF国泰
        "159708.XSHE",   # 红利ETF西部利得
        "159798.XSHE",   # 消费ETF易方达
        "159225.XSHE",   # 现金流ETF银华
        "563990.XSHG",   # 800现金流ETF富国
        "560180.XSHG",   # 沪深300ESGETF南方
        "560630.XSHG",   # 机器人ETF万家
        "588130.XSHG",   # 科创医药ETF华夏
        "159647.XSHE",   # 中药ETF鹏华
        "588860.XSHG",   # 科创医药ETF工银
        "516270.XSHG",   # 新能源ETF华安
        "159658.XSHE",   # 数字经济ETF华安
        "589090.XSHG",   # 科创AIETF鹏华
        "516060.XSHG",   # 创新药ETF工银
        "560880.XSHG",   # 家电ETF广发
        "159276.XSHE",   # 现金流ETF汇添富
        "588140.XSHG",   # 科创200ETF广发
        "515560.XSHG",   # 证券ETF建信
        "561010.XSHG",   # 软件ETF华安
        "562030.XSHG",   # 信创ETF华宝
        "512730.XSHG",   # 银行ETF鹏华
        "515750.XSHG",   # 科技50ETF富国
        "159389.XSHE",   # 数字经济ETF嘉实
        "589500.XSHG",   # 科创综指ETF工银
        "159512.XSHE",   # 汽车ETF广发
        "159229.XSHE",   # 自由现金流ETF广发
        "159223.XSHE",   # 现金流ETF永赢
        "563780.XSHG",   # 现金流全指ETF方正富邦
        "561760.XSHG",   # 油气ETF博时
        "159148.XSHE",   # 石油ETF富国
        "516500.XSHG",   # 生物科技ETF华夏
        "560660.XSHG",   # 云计算50ETF新华
        "159292.XSHE",   # 创业板综增强ETF华宝
        "561060.XSHG",   # 国企红利ETF华安
        "560850.XSHG",   # 信创ETF汇添富
        "588210.XSHG",   # 科创100ETF易方达
        "517110.XSHG",   # 创新药ETF国泰
    ]

    # ========== 行业高相似性交易相关变量 ==========
    g.industry_holdings = {}  # 行业ETF持仓记录 {etf_code: buy_date}
    g.industry_rankings_cache = {'date': None, 'data': None}  # 行业ETF排名缓存
    g.industry_similarity_threshold = 0.85  # 高相似性阈值（相关性）
    g.industry_group_min_score = 20  # 高相似组平均分阈值（需达到20分以上）
    g.current_industry_group = None  # 当前持有的高相似性分组信息 {'keyword': str, 'avg_score': float, 'etf_codes': list}
    g.current_mode = None  # 当前模式：'国内模式' | '全球模式'
    g.industry_group_history = []    # 高相似分组历史记录（用于连续两天监测）
    
    # ---------- 春节窗口参数 ----------
    g.spring_festival_window = {
        'before_days': 3,    # 春节前15个交易日
        'after_days': 15,     # 春节后45个交易日
        'start_month': 1,     # 春节窗口开始月份
        'end_month': 3,       # 春节窗口结束月份
        'last_year': None,    # 上一次计算春节日期的年份
        'pre_window_start': None,  # 春节前窗口开始日期
        'pre_window_end': None,    # 春节前窗口结束日期（春节当天）
        'post_window_start': None, # 春节后窗口开始日期（春节当天）
        'post_window_end': None    # 春节后窗口结束日期
    }
    
    # ---------- 纳斯达克暴跌空仓期参数 ----------
    g.enable_nasdaq_crash_cash = True        # 纳斯达克振幅触发空仓开关
    g.nasdaq_crash_threshold = 0.025         # 纳斯达克单日振幅阈值（2.5%）
    g.nasdaq_crash_cash_days = 5             # 触发后空仓持续天数
    g.nasdaq_crash_counter = 0               # 暴跌空仓期计数器
    g.nasdaq_crash_date = None               # 最近一次触发暴跌的日期

    # ---------- 核心参数 ----------
    g.lookback_days = 25               # 动量计算周期
    g.holdings_num = 1                 # 候选数量
    g.previous_global_top5 = []        # 前一天全球模式top5 ETF列表（包含得分信息）
    g.min_money = 5000                 # 最小交易金额

    # ---------- 盈利保护参数 ----------
    g.enable_profit_protection = True                      # 盈利保护开关
    g.profit_protection_lookback = 1                       # 盈利保护回看周期（天）
    g.profit_protection_threshold = 0.05                   # 盈利保护回撤阈值（5%）
    g.profit_protection_check_times = ['11:00']            # 盈利保护检查时间点（可添加多个，如['09:45','11:00','13:30']）

    g.loss = 0.97                      # 近3日单日跌幅阈值（排除）

    g.min_score_threshold = 0          # 最低得分
    g.max_score_threshold = 100.0      # 最高得分

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

    # ---------- 运行时变量 ----------
    g.rankings_cache = {'date': None, 'data': None}   # 排名缓存

    # ---------- 震荡期参数 ----------
    g.enable_range_bound_mode = True      # 震荡期模式开关
    g.current_filter = '正常期'           # 当前滤波器：'正常期'=拉普拉斯, '震荡期'=高斯
    g.risk_state = '正常期'               # 风险状态
    g.lookback_high_low_days = 20         # 近N个交易日高低点回看
    g.risk_benchmark = '510300.XSHG'      # 风险基准ETF
    # 滤波器参数（正常期拉普拉斯，震荡期高斯）
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.001
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002
    # 进入震荡期条件
    g.enable_bias_trigger = True          # 乖离率过大触发
    g.bias_threshold = 0.10               # 乖离率阈值（8%）
    g.ma_period = 20                      # 均线周期
    g.enable_rsi_trigger = True           # RSI超买回落触发
    g.rsi_overbought = 75
    g.rsi_pullback = 60
    g.previous_rsi = None
    g.enable_stop_loss_trigger = False    # 盈利保护触发止损信号开关
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    # 退出震荡期条件
    g.enable_low_point_rise_trigger = True
    g.low_point_rise_threshold = 0.03     # 从低点上涨4%退出
    g.enable_stable_signal_trigger = True
    g.drawdown_recovery = 0.03            # 回撤收窄阈值
    g.max_range_bound_days = 15           # 最大震荡期天数
    g.stable_days = 0
    # 震荡期控制
    g.filter_switch_cooldown = 2          # 切换冷却期（交易日）
    g.last_switch_date = None
    g.range_bound_start_date = None
    g.range_bound_days_count = 0
    g.previous_drawdown = None

    # ---------- 交易调度 ----------
    run_daily(check_positions, time='09:10')
    run_daily(regime_check, time='09:40')
    run_daily(etf_sell_trade, time='11:25')
    run_daily(etf_buy_trade, time='11:26')

    # 动态注册盈利保护检查时间点
    for check_time in g.profit_protection_check_times:
        run_daily(profit_protection_check, time=check_time)
        log.info(f"已注册盈利保护检查时间：{check_time}")

    # 震荡期检查（在卖出前执行）与收盘重置
    run_daily(check_range_bound, time='11:20')
    run_daily(regime_daily_statistics, time='15:05')
    run_daily(reset_range_bound_daily, time='15:10')
    
    # 纳斯达克暴跌空仓期检查（早盘09:50检查，触发时立即清仓）
    run_daily(check_nasdaq_crash_morning, time='09:50')

    log.info(f"策略初始化完成：ETF池{len(g.etf_pool)}只，动量周期{g.lookback_days}天，持仓{g.holdings_num}只")
    log.info(f"盈利保护开关：{'开启' if g.enable_profit_protection else '关闭'}，回看周期{g.profit_protection_lookback}天，回撤阈值{g.profit_protection_threshold*100:.0f}%")
    if g.enable_premium_filter:
        log.info(f"溢价率过滤已启用，阈值：{g.premium_threshold*100:.0f}%")
    else:
        log.info("溢价率过滤未启用")
    log.info(f"震荡期模式：{'开启' if g.enable_range_bound_mode else '关闭'}，正常期=拉普拉斯滤波器，震荡期=高斯滤波器")

    # 首次运行时，根据历史数据判断当前是否处于震荡期
    init_range_bound_status(context)
    log.info("========== 策略初始化完成 ==========")


# ==================== 盈利保护独立检查函数 ====================
def profit_protection_check(context):
    """
    独立执行的盈利保护检查函数
    遍历所有持仓，若触发盈利保护则卖出
    """
    if not g.enable_profit_protection:
        log.debug("盈利保护模块已关闭，跳过检查")
        return

    log.info("========== 盈利保护独立检查开始 ==========")
    for sec in list(context.portfolio.positions.keys()):
        # 只处理主ETF池和行业ETF池中的标的
        if sec not in g.etf_pool and sec not in g.industry_etf_pool:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if check_profit_protection(sec, context):
                if smart_order_target_value(sec, 0, context):
                    log.info(f"🛡️ 盈利保护卖出（独立检查）：{sec} {get_name(sec)}")
                    # 触发止损信号，用于震荡期进入判断
                    if getattr(g, 'enable_stop_loss_trigger', False):
                        g.stop_loss_triggered_today = True
                        g.stop_loss_triggered_date = context.current_dt.date()
                        log.info("【盈利保护触发】记录止损信号，将在震荡期检查时使用")
    log.info("========== 盈利保护独立检查完成 ==========")


# ==================== 盈利保护检查函数（核心逻辑） ====================
def check_profit_protection(security, context, lookback=None, threshold=None):
    """
    检查是否触发盈利保护（从最近N日最高点回撤超过阈值）
    参数:
        security: ETF代码
        context: 上下文
        lookback: 回看天数，默认g.profit_protection_lookback
        threshold: 回撤阈值，默认g.profit_protection_threshold
    返回:
        bool: True表示应触发盈利保护（卖出/排除），False表示安全
    """
    # 若开关关闭，直接返回安全（独立检查函数已在外层判断，但保留此判断以防直接调用）
    if not g.enable_profit_protection:
        return False

    lookback = lookback or g.profit_protection_lookback
    threshold = threshold or g.profit_protection_threshold

    # 获取最近N日的最高价（不包括当天）
    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        log.debug(f"{security} {get_name(security)} 历史数据不足{lookback}天，无法检查盈利保护")
        return False

    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price

    if current_price <= max_high * (1 - threshold):
        return True
    else:
        return False


# ==================== 溢价率获取函数 ====================
def get_premium_rate(code, date, max_back_days=5):
    """
    获取指定日期的溢价率，若当天无净值则向前搜索最多max_back_days个交易日
    参数:
        code: 基金代码
        date: 日期，datetime.date 对象
        max_back_days: 最大回退天数
    返回:
        premium_rate: 溢价率（小数形式），None 表示获取失败
        price: 场内交易价格
        net_value: 基金净值
    """
    # 获取场内交易价格（给定日期）
    price_data = get_price(
        code,
        start_date=date,
        end_date=date,
        frequency='daily',
        fields=['close']
    )
    if price_data.empty:
        log.debug(f"{date} {code} 无交易价格数据")
        return None, None, None
    price = price_data['close'].iloc[0]

    # 获取净值，先尝试指定日期，若失败则向前搜索交易日
    net_value = None
    used_date = date
    # 获取从date往前max_back_days个交易日的列表（扩大范围确保包含足够交易日）
    start_date = date - datetime.timedelta(days=max_back_days*2)
    trade_days = get_trade_days(start_date=start_date, end_date=date)
    # 转换为 Python date 对象
    trade_days = [pd.to_datetime(d).date() for d in trade_days]
    # 倒序搜索，从date开始向前
    for dt in reversed(trade_days):
        if dt > date:  # 忽略大于date的日期
            continue
        # 尝试获取净值的两种方式
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            used_date = dt
            break
        # 备用方法
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
        log.debug(f"{code} 在{date}及前{max_back_days}个交易日均无净值数据")
        return None, None, None

    premium_rate = (price - net_value) / net_value
    if used_date != date:
        log.debug(f"{code} 使用{used_date}的净值{net_value:.4f}代替{date}的净值计算溢价率")
    return premium_rate, price, net_value


# ==================== 震荡期机制 ====================
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


def laplace_filter(price, s=0.05):
    """拉普拉斯滤波器（正常期使用）"""
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def gaussian_filter_last_two(price, sigma=1.2):
    """仅计算高斯滤波最后两个点（震荡期使用，效率优化）"""
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


def get_risk_benchmark_state(context):
    """获取风险基准的日线+盘中融合状态，用于震荡期判断"""
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
            frequency='1m', fields=['close', 'high', 'low'],
            panel=False, fill_paused=False
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
            current_data = get_current_data()
            live_price = current_data[g.risk_benchmark].last_price
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
    """判断止损信号是否仍在有效期内"""
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
    """首次运行时，根据历史数据判断当前是否处于震荡期"""
    if not g.enable_range_bound_mode:
        return
    log.info("【首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None:
            log.warning("【首次运行】无法获取前一个交易日，保持正常期")
            return
        end_date = context.previous_date
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            log.warning("【首次运行】数据不足，保持正常期")
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
            g.current_filter = '震荡期'
            g.risk_state = '震荡期'
            g.range_bound_start_date = end_date
            g.range_bound_days_count = 0
            log.info(f"【首次运行】初始化进入震荡期: {'; '.join(signals)}")
        else:
            g.current_filter = '正常期'
            g.risk_state = '正常期'
            if len(close) >= g.lookback_high_low_days:
                g.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            else:
                g.previous_drawdown = 0
            g.previous_rsi = current_rsi
            rsi_str = f"{current_rsi:.1f}" if current_rsi is not None else "N/A"
            log.info(f"【首次运行】初始状态: 正常期, 乖离率: {bias:.2%}, RSI: {rsi_str}, 从低点涨幅: {rise_from_low:.2%}")
    except Exception as e:
        log.warning(f"【首次运行】初始化震荡期状态异常: {e}，保持正常期")


def check_and_exit_range_bound_mode(context):
    """检查是否需要退出震荡期"""
    if not g.enable_range_bound_mode:
        return
    if g.current_filter != '震荡期':
        return
    log.info("【震荡期退出检查】开始检测退出条件...")
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is None:
            log.warning("【震荡期退出检查】数据不足，跳过")
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
        log.info(f"【震荡期数据】当前价: {current_price:.3f}, 近{g.lookback_high_low_days}日高点: {recent_high:.3f}, 低点: {recent_low:.3f}")
        log.info(f"【震荡期数据】回撤: {current_drawdown:.2%}, 从低点涨幅: {rise_from_low:.2%}")
        if g.enable_low_point_rise_trigger:
            if rise_from_low >= g.low_point_rise_threshold:
                recovery_signals.append(f"从低点上涨{rise_from_low:.2%}>={g.low_point_rise_threshold:.0%}")
                log.info(f"【退出条件触发】从低点上涨: {rise_from_low:.2%}")
        if g.enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("价格站上均线")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                recovery_signals.append(f"回撤收窄({current_drawdown:.2%}<{g.previous_drawdown:.2%})")
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                recovery_signals.append(f"RSI回升({current_rsi:.1f})")
            drawdown_safe = current_drawdown < g.drawdown_recovery
            if drawdown_safe:
                g.stable_days += 1
                log.info(f"【企稳计数】连续企稳天数: {g.stable_days}")
            else:
                g.stable_days = 0
        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi
        range_bound_days = 0
        if g.range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
            if range_bound_days >= g.max_range_bound_days:
                recovery_signals.append(f"震荡期满({range_bound_days}天)")
                log.info(f"【退出条件触发】震荡期已满{range_bound_days}天")
        low_point_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_condition = False
        if g.enable_stable_signal_trigger:
            drawdown_safe = current_drawdown < g.drawdown_recovery
            stable_condition = drawdown_safe and len(recovery_signals) >= 2 and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days
        should_recover = low_point_condition or stable_condition or force_condition
        if should_recover:
            can_switch = True
            if g.last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
                days_since = len(trade_days) - 1
                if days_since < g.filter_switch_cooldown:
                    can_switch = False
                    log.info(f"【震荡期退出】冷却期中，距上次切换{days_since}天")
            if can_switch:
                g.current_filter = '正常期'
                g.risk_state = '正常期'
                g.last_switch_date = context.current_dt.date()
                g.range_bound_start_date = None
                g.range_bound_days_count = 0
                g.stable_days = 0
                log.info(f"【退出震荡期】切换回拉普拉斯滤波器: {'; '.join(recovery_signals)}")
        else:
            log.info("【震荡期退出检查】未满足退出条件，保持震荡期(高斯滤波器)")
    except Exception as e:
        log.warning(f"【震荡期退出检查】判断出错: {e}")


def check_and_enter_range_bound_mode(context):
    """检查是否需要进入震荡期"""
    if not g.enable_range_bound_mode:
        return
    log.info("【震荡期进入检查】开始检测...")
    stop_loss_signal_active = is_fresh_stop_loss_signal(context)
    can_switch = True
    if g.last_switch_date is not None:
        trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
        days_since = len(trade_days) - 1
        if days_since < g.filter_switch_cooldown:
            can_switch = False
            log.info(f"【震荡期检查】冷却期中，距上次切换{days_since}天")
    if g.current_filter == '震荡期':
        log.info("【震荡期检查】当前已在震荡期")
        return
    if not can_switch:
        return
    risk_signals = []
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is not None:
            close = benchmark_state['close_series']
            current_price = benchmark_state['current_price']
            # 条件1: 乖离率过大
            if g.enable_bias_trigger:
                ma = benchmark_state['ma']
                bias = (current_price - ma) / ma if ma > 0 else 0
                if bias > g.bias_threshold:
                    risk_signals.append(f"乖离率过大({bias:.2%}>{g.bias_threshold:.0%})")
                    log.info(f"【条件触发】乖离率: {bias:.2%} (数据源:{benchmark_state['data_source']})")
            # 条件2: RSI超买回落
            if g.enable_rsi_trigger:
                current_rsi = benchmark_state['current_rsi']
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = benchmark_state['previous_rsi']
                    if prev_rsi is not None:
                        if prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                            risk_signals.append(f"RSI超买回落({prev_rsi:.1f}->{current_rsi:.1f})")
                            log.info(f"【条件触发】RSI超买回落: {prev_rsi:.1f}->{current_rsi:.1f}")
    except Exception as e:
        log.warning(f"【震荡期检查】获取基准数据异常: {e}")
    # 条件3: 盈利保护触发止损
    if g.enable_stop_loss_trigger and stop_loss_signal_active:
        risk_signals.append("盈利保护触发止损")
        log.info("【条件触发】盈利保护触发止损信号")
    if len(risk_signals) > 0:
        g.current_filter = '震荡期'
        g.risk_state = '震荡期'
        g.last_switch_date = context.current_dt.date()
        g.range_bound_start_date = context.current_dt.date()
        g.range_bound_days_count = 0
        g.stable_days = 0
        g.stop_loss_triggered_today = False
        g.stop_loss_triggered_date = None
        log.info(f"【进入震荡期】切换到高斯滤波器: {'; '.join(risk_signals)}")
    else:
        log.info("【震荡期检查】未满足进入条件，保持正常期(拉普拉斯滤波器)")


def check_range_bound(context):
    """震荡期检查入口（11:20定时调度，在卖出前执行）"""
    refresh_regime_for_trade(context)
    
    if not g.enable_range_bound_mode:
        return
    log.info("========== 震荡期检查开始 ==========")
    log.info(f"当前状态: {g.current_filter}")
    check_and_exit_range_bound_mode(context)
    check_and_enter_range_bound_mode(context)
    log.info(f"检查后状态: {g.current_filter}")
    # 状态变更后清除排名缓存，确保11:25卖出时重新计算
    g.rankings_cache = {'date': None, 'data': None}
    log.info("========== 震荡期检查完成 ==========")


def reset_range_bound_daily(context):
    """收盘后重置震荡期相关的每日标志"""
    if g.current_filter == '震荡期' and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
        g.range_bound_days_count = len(trade_days) - 1
        log.info(f"震荡期已持续 {g.range_bound_days_count} 个交易日")


# ==================== A股行情判断模块 ====================
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
    else:
        if g.enable_avoid_a_share:
            log.info("   → 恢复交易A股ETF")
        else:
            log.info("   → 回避A股开关关闭，始终交易全市场")


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
            reset_regime_statistics()
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
                broadcast_regime_top20(context, is_final=True)
                reset_regime_statistics()
        elif mode == 'daily' and g.weak_period_counter >= g.weak_period_max_days:
            g.is_a_share_weak = False
            g.weak_period_counter = 0
            log.info(f"⏰ 走弱期满{g.weak_period_max_days}日强制退出，恢复正常期")
            _log_a_share_transition(False)
            broadcast_regime_top20(context, is_final=True)
            reset_regime_statistics()

    state_changed = old_state != g.is_a_share_weak
    if state_changed:
        g.rankings_cache = {'date': None, 'data': None}
        g.industry_rankings_cache = {'date': None, 'data': None}
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
        recover_info = (
            f" MA5/10↑:{ma_recover}/{len(g.regime_indexes)}"
            if g.is_a_share_weak else ""
        )
        log.info(
            f"📊 当前状态：{current_status}{avoid_status} "
            f"计数:{g.weak_period_counter}/{g.weak_period_max_days}{recover_info}"
        )
    g.a_share_weak_daily_lock = bool(g.is_a_share_weak)
    return changed


def regime_check(context):
    """每日 9:40 行情判断：A股弱。"""
    log.info("🌍 ========== A股行情判断开始（日频）==========")
    a_share_regime_check(context)
    log.info("🌍 ========== A股行情判断完成 ==========")


def refresh_regime_for_trade(context):
    """盘中复检A股弱状态；同一分钟只执行一次。"""
    key = (context.current_dt.date(), context.current_dt.strftime('%H%M'))
    if getattr(g, '_regime_trade_refresh_key', None) == key:
        return False
    g._regime_trade_refresh_key = key
    changed = False
    if g.enable_regime_switch:
        signals = compute_a_share_regime_signals(context, use_intraday=True)
        below, ma_weak, ma_recover, detail, price_tag = signals
        log.info(f"🕐 盘中A股弱复检({price_tag}) 价破:{below} MA弱:{ma_weak} MA回升:{ma_recover}")
        changed |= _apply_a_share_regime_state(
            context, below, ma_weak, ma_recover, detail, mode='intraday'
        )
    return changed


# ==================== 弱势期统���模块 ====================
def calculate_regime_scores(context):
    """计算国内弱势期当日得分：ETF涨跌幅 - 上证指数涨跌幅（超额收益）"""
    if not g.is_a_share_weak:
        return

    try:
        sh_index_code = '000001.XSHG'
        sh_data = attribute_history(sh_index_code, 2, '1d', ['close'])
        if len(sh_data) < 2:
            log.warning("无法获取上证指数数据，跳过当日统计")
            return
        sh_return = sh_data['close'].iloc[-1] / sh_data['close'].iloc[-2] - 1

        min_volume = g.regime_min_volume_million * 10000

        today_scores = {}
        for etf in g.industry_etf_pool:
            try:
                data = attribute_history(etf, 2, '1d', ['close', 'money'])
                if len(data) < 2:
                    continue
                etf_return = data['close'].iloc[-1] / data['close'].iloc[-2] - 1
                money = data['money'].iloc[-1]
                if money < min_volume:
                    continue
                score = etf_return - sh_return
                today_scores[etf] = score
            except Exception as e:
                continue

        g.regime_trading_dates.append(context.current_dt.date())
        for etf, score in today_scores.items():
            if etf not in g.regime_score_detail:
                g.regime_score_detail[etf] = []
            g.regime_score_detail[etf].append(score)

    except Exception as e:
        log.warning(f"弱势期统计计算失败: {e}")


def broadcast_regime_top20(context, is_final=False):
    """盘后播报弱势期行业ETF得分排名top20"""
    if not g.is_a_share_weak and not is_final:
        return

    detail = g.regime_score_detail
    if not detail:
        return

    total_days = len(g.regime_trading_dates)
    if total_days == 0:
        return

    results = []
    for etf, scores in detail.items():
        cum_score = sum(scores)
        pos_days = sum(1 for s in scores if s > 0)
        neg_days = sum(1 for s in scores if s < 0)
        zero_days = len(scores) - pos_days - neg_days

        half_point = (total_days + 1) // 2
        first_half_score = sum(scores[:half_point]) if half_point > 0 else 0
        second_start = half_point - 1 if total_days % 2 == 1 else half_point
        second_half_score = sum(scores[second_start:]) if second_start < len(scores) else 0
        is_preferred = second_half_score > first_half_score and total_days >= 2

        results.append({
            'etf': etf,
            'name': get_name(etf),
            'cum_score': cum_score,
            'pos_days': pos_days,
            'neg_days': neg_days,
            'zero_days': zero_days,
            'is_preferred': is_preferred,
            'first_half_score': first_half_score,
            'second_half_score': second_half_score,
        })

    results.sort(key=lambda x: x['cum_score'], reverse=True)
    top20 = results[:20]

    log.info("=" * 70)
    if is_final:
        log.info(f"📊 A股弱势期结束总结（共{total_days}个交易日）")
    else:
        log.info(f"📊 A股弱势期第{total_days}天统计")
    log.info("=" * 70)
    log.info(f"{'排名':<4} {'ETF代码':<14} {'名称':<20} {'累计得分':>12} {'正天数':>6} {'负天数':>6} {'标记':<8}")
    log.info("-" * 70)

    for i, item in enumerate(top20, 1):
        tag = "⭐优选" if item['is_preferred'] else ""
        log.info(
            f"{i:<4} {item['etf']:<14} {item['name']:<20} "
            f"{item['cum_score']:>12.2f} {item['pos_days']:>6} {item['neg_days']:>6} {tag:<8}"
        )

    if is_final:
        preferred_count = sum(1 for r in results if r['is_preferred'])
        log.info("-" * 70)
        log.info(f"📈 新行情优选标记：共{preferred_count}只ETF（后半程得分>前半程）")
        log.info(f"示例：排名前5中优选ETF")
        for item in top20[:5]:
            if item['is_preferred']:
                log.info(
                    f"   {item['etf']} {item['name']} "
                    f"前半程:{item['first_half_score']:.2f} → 后半程:{item['second_half_score']:.2f}"
                )

    log.info("=" * 70)


def regime_daily_statistics(context):
    """每日15:05执行弱势期统计和播报"""
    if not g.is_a_share_weak:
        return
    calculate_regime_scores(context)
    broadcast_regime_top20(context)


def reset_regime_statistics():
    """重置弱势期统计数据"""
    g.regime_score_detail = {}
    g.regime_trading_dates = []


# ==================== 核心计算模块 ====================
def get_cached_rankings(context):
    """获取缓存的ETF排名，保证同一交易日内多次调用结果一致"""
    today = context.current_dt.date()
    if g.rankings_cache['date'] != today:
        log.info("重新计算ETF排名...")
        ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': today, 'data': ranked}
    return g.rankings_cache['data']


def get_ranked_etfs(context):
    """
    计算所有ETF的动量得分，应用所有过滤条件，返回按得分降序的列表
    """
    etf_metrics = []
    for etf in g.etf_pool:
        # 停牌过滤
        if get_current_data()[etf].paused:
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            # 得分范围过滤
            if g.min_score_threshold < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def get_industry_ranked_etfs(context):
    """
    计算行业ETF的动量得分（仅用于排名分析，不直接交易）
    返回按得分降序的列表
    """
    today = context.current_dt.date()
    if g.industry_rankings_cache['date'] == today:
        return g.industry_rankings_cache['data']
    
    log.info("计算行业ETF排名...")
    etf_metrics = []
    for etf in g.industry_etf_pool:
        # 停牌过滤
        if get_current_data()[etf].paused:
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            etf_metrics.append(metrics)

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    g.industry_rankings_cache = {'date': today, 'data': etf_metrics}
    
    log.info(f"行业ETF排名完成，共{len(etf_metrics)}只")
    return etf_metrics


def calculate_industry_similarity_groups(top10_metrics):
    """计算行业ETF top10的高相似度分组
    
    规则：
    - 从ETF中文名字中提取"ETF"之前的部分
    - 找出所有可能的≥2字符的连续子串作为候选分类关键词
    - 如果某个关键词在≥2只ETF中出现，则形成一个分类组
    - 计算每个分类组的ETF数量、占比和平均分
    """
    if not top10_metrics or len(top10_metrics) < 2:
        return []
    
    # 提取ETF前缀（"ETF"之前的部分）
    prefixes = []
    for m in top10_metrics:
        name = m.get('etf_name', '')
        if 'ETF' in name:
            prefix = name.split('ETF')[0]
        else:
            prefix = name
        prefixes.append((prefix, m))
    
    # 收集所有≥2字符的候选关键词及其出现的ETF
    candidate_keywords = {}
    
    for prefix, m in prefixes:
        # 生成所有≥2字符的连续子串作为候选关键词
        for start in range(len(prefix)):
            for end in range(start + 2, len(prefix) + 1):
                keyword = prefix[start:end]
                if keyword not in candidate_keywords:
                    candidate_keywords[keyword] = []
                candidate_keywords[keyword].append((prefix, m))
    
    # 筛选出包含≥2只ETF的关键词作为分类组
    groups = []
    for keyword, etfs in candidate_keywords.items():
        if len(etfs) >= 2:
            # 计算该组的平均分
            scores = [m['score'] for _, m in etfs]
            avg_score = sum(scores) / len(scores)
            # 计算占比
            ratio = len(etfs) / len(top10_metrics)
            # 获取组内ETF名称列表
            etf_names = [m['etf_name'] for _, m in etfs]
            groups.append({
                'keyword': keyword,
                'count': len(etfs),
                'ratio': ratio,
                'avg_score': avg_score,
                'etf_names': etf_names,
                'etf_codes': [m['etf'] for _, m in etfs]
            })
    
    # 按组内数量降序排序，数量相同时按关键词长度降序排序（优先保留更长的关键词）
    groups.sort(key=lambda x: (-x['count'], -len(x['keyword'])))
    
    # 过滤掉被更长关键词包含的短关键词（避免重复计数）
    filtered_groups = []
    for group in groups:
        is_subsumed = False
        for existing in filtered_groups:
            if group['keyword'] in existing['keyword']:
                is_subsumed = True
                break
        if not is_subsumed:
            filtered_groups.append(group)
    
    return filtered_groups


def is_in_spring_festival_window(context):
    """检查当前日期是否在春节窗口期间（春节前15个交易日到春节后45个交易日）
    
    返回：
    - True：在春节窗口期间，不得启用国内模式
    - False：不在春节窗口期间，可以启用国内模式
    """
    today = context.current_dt.date()
    
    # 获取当前年份
    current_year = today.year
    
    # 如果年份变化或窗口未计算，重新计算春节日期
    if g.spring_festival_window['last_year'] != current_year:
        # 获取春节日期（农历正月初一）
        # 春节日期计算：1月21日到2月20日之间
        # 我们需要找到当前年份春节的确切日期
        spring_festival_date = get_spring_festival_date(current_year)
        
        if spring_festival_date:
            # 获取春节前15个交易日
            pre_window_start = get_n_trading_days_before(spring_festival_date, g.spring_festival_window['before_days'])
            # 获取春节后45个交易日
            post_window_end = get_n_trading_days_after(spring_festival_date, g.spring_festival_window['after_days'])
            
            g.spring_festival_window['last_year'] = current_year
            g.spring_festival_window['pre_window_start'] = pre_window_start
            g.spring_festival_window['pre_window_end'] = spring_festival_date
            g.spring_festival_window['post_window_start'] = spring_festival_date
            g.spring_festival_window['post_window_end'] = post_window_end
            
            log.info(f"🎉 春节窗口计算完成：{pre_window_start} ~ {post_window_end}（春节: {spring_festival_date}）")
    
    # 检查是否在窗口期间
    pre_start = g.spring_festival_window['pre_window_start']
    post_end = g.spring_festival_window['post_window_end']
    
    if pre_start is not None and post_end is not None:
        is_in_window = pre_start <= today <= post_end
        if is_in_window:
            log.info(f"📅 当前日期{today}在春节窗口期间（{pre_start} ~ {post_end}），禁止启用国内模式")
        return is_in_window
    
    return False


def get_spring_festival_date(year):
    """获取指定年份的春节日期（农历正月初一）
    
    使用查表法，支持1900-2100年
    """
    spring_festival_dates = {
        2000: datetime.date(2000, 2, 5),
        2001: datetime.date(2001, 1, 24),
        2002: datetime.date(2002, 2, 12),
        2003: datetime.date(2003, 2, 1),
        2004: datetime.date(2004, 1, 22),
        2005: datetime.date(2005, 2, 9),
        2006: datetime.date(2006, 1, 29),
        2007: datetime.date(2007, 2, 18),
        2008: datetime.date(2008, 2, 7),
        2009: datetime.date(2009, 1, 26),
        2010: datetime.date(2010, 2, 14),
        2011: datetime.date(2011, 2, 3),
        2012: datetime.date(2012, 1, 23),
        2013: datetime.date(2013, 2, 10),
        2014: datetime.date(2014, 1, 31),
        2015: datetime.date(2015, 2, 19),
        2016: datetime.date(2016, 2, 8),
        2017: datetime.date(2017, 1, 28),
        2018: datetime.date(2018, 2, 16),
        2019: datetime.date(2019, 2, 5),
        2020: datetime.date(2020, 1, 25),
        2021: datetime.date(2021, 2, 12),
        2022: datetime.date(2022, 2, 1),
        2023: datetime.date(2023, 1, 22),
        2024: datetime.date(2024, 2, 10),
        2025: datetime.date(2025, 1, 29),
        2026: datetime.date(2026, 2, 17),
        2027: datetime.date(2027, 2, 6),
        2028: datetime.date(2028, 1, 26),
        2029: datetime.date(2029, 2, 13),
        2030: datetime.date(2030, 2, 3),
        2031: datetime.date(2031, 1, 23),
        2032: datetime.date(2032, 2, 11),
        2033: datetime.date(2033, 1, 31),
        2034: datetime.date(2034, 2, 19),
        2035: datetime.date(2035, 2, 8),
        2036: datetime.date(2036, 1, 29),
        2037: datetime.date(2037, 2, 17),
        2038: datetime.date(2038, 2, 6),
        2039: datetime.date(2039, 1, 26),
        2040: datetime.date(2040, 2, 14),
        2041: datetime.date(2041, 2, 4),
        2042: datetime.date(2042, 1, 24),
        2043: datetime.date(2043, 2, 12),
        2044: datetime.date(2044, 2, 1),
        2045: datetime.date(2045, 2, 20),
        2046: datetime.date(2046, 2, 9),
        2047: datetime.date(2047, 1, 29),
        2048: datetime.date(2048, 2, 17),
        2049: datetime.date(2049, 2, 6),
        2050: datetime.date(2050, 1, 26),
    }
    
    if year in spring_festival_dates:
        return spring_festival_dates[year]
    
    # 对于不在表中的年份，使用估算方法
    # 春节日期大约在每年的1月21日到2月20日之间
    # 这里使用一个简单的公式估算
    # 实际应用中可以扩展上表或使用更精确的算法
    return datetime.date(year, 2, 10)


def get_n_trading_days_before(date, n):
    """获取指定日期之前的第N个交易日"""
    trading_days = get_trade_days(end_date=date, count=n+1)
    if len(trading_days) > 0:
        return trading_days[0]
    return date


def get_n_trading_days_after(date, n):
    """获取指定日期之后的第N个交易日"""
    trading_days = get_trade_days(start_date=date, count=n+1)
    if len(trading_days) > 0:
        return trading_days[-1]
    return date


def check_nasdaq_crash_morning(context):
    """09:50 早盘检查美股前一交易日数据，触发纳斯达克空仓期（立即清仓）。"""
    if not getattr(g, 'enable_nasdaq_crash_cash', True):
        return False
    
    if getattr(g, 'nasdaq_crash_counter', 0) > 0:
        return False
    
    nasdaq_etfs = [
        '159501.XSHE', '159509.XSHE', '159513.XSHE', '159632.XSHE',
        '159659.XSHE', '159660.XSHE', '159696.XSHE', '159941.XSHE',
        '161130.XSHE', '513100.XSHG', '513110.XSHG', '513290.XSHG',
        '513300.XSHG', '513390.XSHG', '513870.XSHG',
    ]
    
    crash_count = 0
    crash_details = []
    
    for etf_code in nasdaq_etfs:
        try:
            df = attribute_history(etf_code, 2, '1d', ['close', 'high', 'low'], skip_paused=False)
            if df.empty or len(df) < 2:
                continue
            prev_close = df['close'].values[0]
            today_close = df['close'].values[-1]
            today_high = df['high'].values[-1]
            today_low = df['low'].values[-1]
            if prev_close <= 0:
                continue
            amplitude = (today_high - today_low) / prev_close
            is_down = today_close < prev_close
            
            threshold = getattr(g, 'nasdaq_crash_threshold', 0.025)
            if amplitude >= threshold and is_down:
                crash_count += 1
                crash_details.append(f"{etf_code} 振幅{amplitude*100:.2f}%")
        except Exception:
            continue
    
    if crash_count >= 4:
        log.info(f"🌙 【早盘触发】美股前一交易日{crash_count}/15只ETF下跌且振幅≥{threshold*100:.1f}%，立即清仓并进入空仓期")
        for detail in crash_details[:3]:
            log.info(f"   {detail}")
        if len(crash_details) > 3:
            log.info(f"   ...还有{len(crash_details)-3}只")
        
        nasdaq_crash_clear(context)
        return True
    
    return False


def nasdaq_crash_clear(context):
    """纳斯达克暴跌触发时清仓所有持仓并进入空仓期"""
    log.info("💥 纳斯达克暴跌触发，清仓所有持仓")
    for sec in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if smart_order_target_value(sec, 0, context):
                log.info(f"📤 清仓卖出：{sec} {get_name(sec)}")
    
    g.nasdaq_crash_counter = 1
    g.nasdaq_crash_date = context.current_dt.date()
    days = getattr(g, 'nasdaq_crash_cash_days', 5)
    log.info(f"💥 进入纳斯达克空仓期（第1天/共{days}天），禁止买入任何ETF")


def is_in_nasdaq_crash_window(context):
    """检查当前是否处于纳斯达克空仓期"""
    if not getattr(g, 'enable_nasdaq_crash_cash', True):
        return False
    
    if getattr(g, 'nasdaq_crash_counter', 0) <= 0:
        return False
    
    return True


def check_industry_high_similarity_buy(context):
    """检查行业ETF top10是否出现高相似性分组且满足买入条件
    
    买入条件：
    1. 不在春节窗口期间
    2. 高相似分组平均分需要达到20分以上
    3. 筛选后保留的ETF数量需要达到150只以上
    4. 连续两天存在同一主题的高相似分组，且平均分数增长
    5. 不在A股弱势期
    
    返回：(should_buy, group_info)
    - should_buy: 是否应该买入高相似性分组的ETF
    - group_info: 最佳分组信息（如果满足条件）
    """
    # ========== 春节窗口检查 ==========
    if is_in_spring_festival_window(context):
        log.info("❌ 春节窗口期间，禁止启用国内模式")
        g.industry_group_history = []  # 清空历史记录
        return False, None
    
    # 获取行业ETF排名
    industry_ranked = get_industry_ranked_etfs(context)
    
    # 不足10只时无法分析
    if len(industry_ranked) < 10:
        log.info(f"行业ETF不足10只（仅{len(industry_ranked)}只），无法进行高相似性分析")
        return False, None
    
    # 新增条件：筛选后保留的ETF数量需要达到150只以上
    if len(industry_ranked) < 150:
        log.info(f"❌ 筛选后保留的行业ETF数量{len(industry_ranked)}只 < 150只，不满足买入条件")
        return False, None
    
    # 取top10
    top10 = industry_ranked[:10]
    
    # 计算高相似性分组
    similarity_groups = calculate_industry_similarity_groups(top10)
    
    if not similarity_groups:
        log.info("行业ETF top10未发现高相似性分组")
        g.industry_group_history = []  # 清空历史记录
        return False, None
    
    # 打印分组信息
    log.info("========== 行业ETF top10高相似性分组 ==========")
    for group in similarity_groups:
        log.info(f"  分组'{group['keyword']}': {group['count']}只 ({group['ratio']:.0%}), 平均分{group['avg_score']:.2f}")
        log.info(f"    ETF: {', '.join(group['etf_names'])}")
    
    # 检查是否有分组平均分 > 阈值（3分以上），选择平均分最高的
    best_group = None
    for group in similarity_groups:
        if group['avg_score'] > g.industry_group_min_score:
            if best_group is None or group['avg_score'] > best_group['avg_score']:
                best_group = group
    
    if best_group:
        log.info(f"✅ 发现满足条件的高相似性分组：'{best_group['keyword']}'，平均分{best_group['avg_score']:.2f} > {g.industry_group_min_score}")
        
        # ========== 连续两天监测逻辑 ==========
        today_group = {
            'date': context.current_dt.date(),
            'keyword': best_group['keyword'],
            'avg_score': best_group['avg_score'],
            'etf_codes': best_group['etf_codes']
        }
        
        # 检查是否连续两天同一主题且分数增长
        should_buy = False
        if len(g.industry_group_history) >= 1:
            yesterday_group = g.industry_group_history[-1]
            if yesterday_group['keyword'] == best_group['keyword']:
                if best_group['avg_score'] > yesterday_group['avg_score']:
                    log.info(f"✅ 连续两天同一主题'{best_group['keyword']}'，分数从{yesterday_group['avg_score']:.2f}增长到{best_group['avg_score']:.2f}，满足买入条件")
                    should_buy = True
                else:
                    log.info(f"⚠️ 连续两天同一主题'{best_group['keyword']}'，但分数从{yesterday_group['avg_score']:.2f}下降到{best_group['avg_score']:.2f}，不满足买入条件")
        
        # 更新历史记录（只保留最近1天）
        g.industry_group_history = [today_group]
        
        if should_buy:
            return True, best_group
        else:
            log.info(f"⚠️ 等待连续两天同一主题且分数增长...")
            return False, None
    else:
        log.info(f"❌ 所有高相似性分组平均分均未达到阈值{g.industry_group_min_score}")
        g.industry_group_history = []  # 清空历史记录
        return False, None


def calculate_momentum_metrics(context, etf):
    """
    计算单只ETF的动量指标，应用所有过滤条件
    返回字典：etf, etf_name, annualized_returns, r_squared, score, current_price, short_annualized
    """
    try:
        name = get_name(etf)
        # 获取足够历史数据
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < g.lookback_days:
            return None

        # 价格序列（含当天）
        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # ===== 1. 盈利保护检查（排除） =====
        if check_profit_protection(etf, context):
            return None

        # ===== 2. 溢价率过滤（提前至排名阶段，获取失败则跳过过滤）=====
        if g.enable_premium_filter:
            # 获取前一个交易日（用于净值数据）
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = get_premium_rate(etf, prev_date)
            if premium is not None:
                if premium > g.premium_threshold:
                    return None
            else:
                # 无法获取溢价率，跳过该过滤条件（不过滤）
                pass

        # ===== 3. 成交量过滤（排除） =====
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns(price_series, g.lookback_days)
                if annualized > g.volume_return_limit:
                    return None

        # ===== 4. 短期动量过滤（排除） =====
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0

        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            return None

        # ===== 5. 长期动量计算（得分） =====
        recent = price_series[-(g.lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        # R²（趋势稳定性）
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        score = annualized_returns * r_squared

        # ===== 6. 近3日单日跌幅过滤（排除） =====
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < g.loss:
                return None

        # ===== 7. 动态滤波器过滤（震荡期机制） =====
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
                    return None
            except Exception as e:
                pass

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
    """计算加权年化收益率"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def get_volume_ratio(context, security, lookback=None, threshold=None):
    """计算当日成交量与过去N日均量的比值，若超过阈值则返回比值，否则None"""
    lookback = lookback or g.volume_lookback
    threshold = threshold or g.volume_threshold
    try:
        name = get_name(security)
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()

        # 获取当日分钟成交量累计
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


# ==================== 卖出模块 ====================
def check_positions(context):
    """每日开盘检查持仓状态，仅用于日志"""
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


def etf_sell_trade(context):
    """卖出操作（已简化，主要卖出逻辑在买入模块中）"""
    log.info("========== 卖出操作开始 ==========")
    log.info("� 卖出逻辑已移至买入模块，此处为空操作")
    log.info("========== 卖出操作完成 ==========")


# ==================== 买入模块 ====================
def etf_buy_trade(context):
    """买入符合条件的ETF
    
    简化逻辑：
    - 每天计算新的高相似性分组名单
    - 如果有高相似分组：等权买入平均分最高的分组内所有ETF（只用现金）
    - 如果没有高相似分组：切换到全球模式，按照原版七星逻辑买入
    """
    log.info("========== 买入操作开始 ==========")
    
    # ========== 纳斯达克空仓期检查 ==========
    if is_in_nasdaq_crash_window(context):
        days = getattr(g, 'nasdaq_crash_cash_days', 5)
        log.info(f"💥 纳斯达克空仓期：第{g.nasdaq_crash_counter}/{days}天，禁止买入任何ETF")
        
        # 更新空仓期计数器
        if g.nasdaq_crash_date != context.current_dt.date():
            g.nasdaq_crash_counter += 1
            g.nasdaq_crash_date = context.current_dt.date()
            
            # 检查是否退出空仓期
            if g.nasdaq_crash_counter > days:
                g.nasdaq_crash_counter = 0
                g.nasdaq_crash_date = None
                log.info(f"✅ 纳斯达克空仓期结束，恢复正常交易")
        
        log.info("========== 买入操作完成（纳斯达克空仓期）==========")
        return

    # ========== 获取行业ETF排名 ==========
    industry_ranked = get_industry_ranked_etfs(context)
    industry_top10_codes = set([m['etf'] for m in industry_ranked[:10]]) if len(industry_ranked) >= 10 else set()
    
    # ========== 检查行业ETF高相似性分组 ==========
    should_buy_industry, industry_group = check_industry_high_similarity_buy(context)
    
    target_etfs = []
    buy_mode = None
    
    # ========== 国内模式：有高相似性分组 ==========
    if should_buy_industry and industry_group:
        # ========== 模式切换时清仓主ETF池持仓 ==========
        if g.current_mode != "国内模式":
            log.info("🔄 从全球模式切换到国内模式，清仓主ETF池持仓")
            for sec in list(context.portfolio.positions.keys()):
                if sec in g.etf_pool:
                    pos = context.portfolio.positions[sec]
                    if pos.total_amount > 0:
                        if smart_order_target_value(sec, 0, context):
                            log.info(f"📤 卖出主ETF池持仓：{sec} {get_name(sec)}")
        
        g.current_mode = "国内模式"
        buy_mode = "国内模式"
        
        # 买入高相似性分组的ETF（等权买入分组内所有ETF）
        target_etfs = industry_group['etf_codes']
        log.info(f"🇨🇳 国内模式：发现高相似性分组'{industry_group['keyword']}'(平均分{industry_group['avg_score']:.2f})")
        log.info(f"🎯 买入分组ETF：{', '.join([get_name(e) for e in target_etfs])}")
        log.info(f"📊 分组共{len(target_etfs)}只ETF，将等权分配现金买入")
        
        # ========== 检查昨日分组和今日分组的重合情况 ==========
        # 昨日分组默认为空（从全球模式切换到国内模式时）
        yesterday_group = set(g.current_industry_group['etf_codes']) if g.current_industry_group is not None else set()
        today_group = set(target_etfs)
        overlap = yesterday_group & today_group  # 重合的ETF
        to_sell = yesterday_group - overlap  # 昨日有但今日没有的ETF
        
        if to_sell:
            log.info(f"🔄 昨日分组与今日分组重合{len(overlap)}只，需卖出{len(to_sell)}只")
            log.info(f"📤 卖出不重合的ETF：{', '.join([get_name(e) for e in to_sell])}")
            for etf in to_sell:
                if etf in context.portfolio.positions and context.portfolio.positions[etf].total_amount > 0:
                    if smart_order_target_value(etf, 0, context):
                        log.info(f"📤 卖出：{etf} {get_name(etf)}")
                        if etf in g.industry_holdings:
                            del g.industry_holdings[etf]
        elif yesterday_group:
            log.info(f"✅ 昨日分组与今日分组完全重合，无需卖出")
        else:
            log.info(f"✅ 从全球模式切换到国内模式，昨日分组为空，无需卖出")
        
        # 记录当前分组信息（用于日志）
        g.current_industry_group = {
            'keyword': industry_group['keyword'],
            'avg_score': industry_group['avg_score'],
            'etf_codes': industry_group['etf_codes']
        }
        
        # ========== 只用现金买入新分组，不额外卖出凑钱 ==========
        # 获取当前可用现金
        available_cash = context.portfolio.cash
        log.info(f"💰 当前可用现金：{available_cash:.2f}")
        
        if available_cash > 0:
            # 计算每只ETF分配金额
            target_per_etf = available_cash / len(target_etfs)
            
            # 只买入不在持仓中的ETF
            for etf in target_etfs:
                if etf not in context.portfolio.positions or context.portfolio.positions[etf].total_amount == 0:
                    if smart_order_target_value(etf, target_per_etf, context):
                        log.info(f"📥 买入：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")
                        # 记录买入日期
                        g.industry_holdings[etf] = context.current_dt.date()
                else:
                    log.info(f"✅ 已持有：{etf} {get_name(etf)}")
        else:
            log.info("💤 可用现金为0，无法买入")
        
        log.info("========== 买入操作完成（模式：国内模式）==========")
        return
    
    # ========== 全球模式：没有高相似性分组 ==========
    # ========== 模式切换时清仓行业ETF持仓 ==========
    if g.current_mode != "全球模式":
        log.info("🔄 从国内模式切换到全球模式，清仓行业ETF持仓")
        for sec in list(context.portfolio.positions.keys()):
            if sec in g.industry_etf_pool:
                pos = context.portfolio.positions[sec]
                if pos.total_amount > 0:
                    if smart_order_target_value(sec, 0, context):
                        log.info(f"📤 卖出行业ETF持仓：{sec} {get_name(sec)}")
                        if sec in g.industry_holdings:
                            del g.industry_holdings[sec]
    
    g.current_mode = "全球模式"
    buy_mode = "全球模式"
    g.current_industry_group = None
    
    log.info("🌍 全球模式：无满足条件的高相似性分组")
    
    # 按照原版七星改逻辑买入
    ranked = get_cached_rankings(context)
    
    # 打印排名前5的指标
    log.info("=== ETF排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        log.info(f"排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} 年化{m['annualized_returns']*100:.2f}% R²={m['r_squared']:.4f}")

    # 获取top5 ETF列表和代码集合
    today_top5 = ranked[:5]
    today_top5_codes = set([m['etf'] for m in today_top5])
    
    # 获取前一天的top5信息（包含得分）
    previous_top5_map = {item['etf']: item['score'] for item in g.previous_global_top5} if g.previous_global_top5 else {}
    
    # 确定目标ETF列表
    prev_date = None
    if g.enable_premium_filter:
        prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]

    # 检查前一天买入的ETF
    previous_etf = None
    for sec in context.portfolio.positions:
        if sec in g.etf_pool and context.portfolio.positions[sec].total_amount > 0:
            previous_etf = sec
            break
    
    # 获取top1得分
    top1_score = ranked[0]['score'] if ranked else 0
    
    # 低分模式：top1得分<10，每天轮动买入top1
    if top1_score < 10:
        for m in ranked:
            if len(target_etfs) >= g.holdings_num:
                break
            etf = m['etf']
            target_etfs.append(etf)
            log.info(f"🔄 top1得分{top1_score:.4f} < 10，进入轮动模式，买入top1: {etf} {m['etf_name']} 得分{m['score']:.4f}")
        if previous_etf:
            log.info(f"🔻 前一天买入的{previous_etf} {get_name(previous_etf)}将被卖出，进入轮动")
    # 高分模式：top1得分>=10，考虑连续两天进入top5的条件
    else:
        # 最高优先级：找连续两天分数>10且环比增长在1-1.5之间的ETF，平铺买入
        high_score_consecutive = []
        for m in today_top5:
            etf = m['etf']
            today_score = m['score']
            if etf in previous_top5_map:
                yesterday_score = previous_top5_map[etf]
                if today_score > 10 and yesterday_score > 10:
                    growth_rate = today_score / yesterday_score
                    if 1 < growth_rate < 1.5:
                        high_score_consecutive.append({
                            'etf': etf,
                            'etf_name': m['etf_name'],
                            'today_score': today_score,
                            'yesterday_score': yesterday_score,
                            'growth_rate': growth_rate
                        })
        
        if high_score_consecutive:
            # 按环比增长率从小到大排序，选择增长最小的
            high_score_consecutive.sort(key=lambda x: x['growth_rate'])
            best_etf = high_score_consecutive[0]
            target_etfs.append(best_etf['etf'])
            log.info(f"🚨 发现{len(high_score_consecutive)}只连续两天分数>10且环比增长在1-1.5之间的ETF")
            for item in high_score_consecutive:
                log.info(f"   - {item['etf']} {item['etf_name']} 今日得分{item['today_score']:.4f} 昨日得分{item['yesterday_score']:.4f} 环比增长{item['growth_rate']:.2f}")
            log.info(f"   ✅ 选定环比增长最小的：{best_etf['etf']} {best_etf['etf_name']} 环比增长{best_etf['growth_rate']:.2f}")
            if previous_etf and previous_etf != best_etf['etf']:
                log.info(f"🔻 前一天买入的{previous_etf} {get_name(previous_etf)}被替换")
        elif previous_etf and previous_etf in today_top5_codes:
            # 次优先级：前一天买入的ETF仍在top5，继续持有
            target_etfs.append(previous_etf)
            log.info(f"✅ 前一天买入的{previous_etf} {get_name(previous_etf)}仍在top5，继续持有")
        else:
            # 无条件买入top1
            target_etfs.append(ranked[0]['etf'])
            log.info(f"🚨 top1 {ranked[0]['etf']} {ranked[0]['etf_name']} 得分{top1_score:.4f} >= 10，无条件买入")
            if previous_etf:
                log.info(f"🔻 前一天买入的{previous_etf} {get_name(previous_etf)}被top1高分替换")

    # 无目标ETF时保持空仓
    if not target_etfs:
        log.info("💤 无目标ETF，保持空仓")
        log.info("========== 买入操作完成（模式：全球模式）==========")
        return

    # 卖出不在目标列表的主ETF池持仓
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool:
            continue
        if sec not in target_etfs:
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                if smart_order_target_value(sec, 0, context):
                    log.info(f"📤 卖出不在目标的持仓：{sec} {get_name(sec)}")

    # 更新前一天的top5记录（保留得分信息，用于计算环比增长）
    g.previous_global_top5 = [{'etf': m['etf'], 'score': m['score']} for m in today_top5]

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

    log.info("========== 买入操作完成（模式：全球模式）==========")


# ==================== 辅助函数 ====================
def get_name(security):
    """获取证券名称，带异常处理"""
    try:
        return get_current_data()[security].name
    except:
        return "未知"


def smart_order_target_value(security, target_value, context):
    """
    智能下单：根据目标市值调整持仓，处理停牌、涨跌停、最小交易金额、T+1
    """
    data = get_current_data()
    name = get_name(security)

    if data[security].paused:
        log.info(f"{security} {name} 停牌，跳过")
        return False

    price = data[security].last_price
    if price == 0:
        log.info(f"{security} {name} 当前价格0，跳过")
        return False

    target_amount = int(target_value / price)
    # 按100股整数倍调整
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
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
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            log.info(f"{security} {name} 当天买入不可卖出")
            return False
        diff = -min(abs(diff), closeable)

    if diff != 0:
        order_result = order(security, diff)
        if order_result:
            log.info(f"{'📥 买入' if diff>0 else '📤 卖出'} {security} {name} 数量{abs(diff)} 价格{price:.3f}")
            return True
        else:
            log.warning(f"下单失败: {security} {name} 数量{diff}")
            return False
    return False