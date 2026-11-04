# Clone from JoinQuant
# postId: ec04617bd9c683f1f90560990129ec3c
# backtestId: 90b15eb601cda9b472c0ffa5e1a0f44f
# title: 五子策略无shipan和中继系统，需要的去另一个帖子

"""
多策略组合 - 终极优化完整版（内存+性能优化版）
包含：
1. ETF轮动策略 (50000元)
2. 4支红利指数线性回归增强 (20000元)
3. QDII ETF/LOF 折溢价套利策略 (20000元)
4. 博收益ETF轮动 (40000元)
5. 小市值策略-独立版V3 (50000元)
总资金: 180000元

"""
from jqdata import *
from functools import wraps
import numpy as np
import pandas as pd
import datetime
import math
import gc
import re




# ==================== 静态配置 静态配置移至模块级 ====================
_SW1 = {
    '801010': '农林牧渔', '801020': '采掘', '801030': '化工', '801040': '钢铁',
    '801050': '有色金属', '801080': '电子', '801110': '家用电器', '801120': '食品饮料',
    '801130': '纺织服装', '801140': '轻工制造', '801150': '医药生物', '801160': '公用事业',
    '801170': '交通运输', '801180': '房地产', '801200': '商业贸易', '801210': '休闲服务',
    '801230': '综合', '801710': '建筑材料', '801720': '建筑装饰', '801730': '电气设备',
    '801740': '国防军工', '801750': '计算机', '801760': '传媒', '801770': '通信',
    '801780': '银行', '801790': '非银金融', '801880': '汽车', '801890': '机械设备',
    '801950': '煤炭', '801960': '石油石化', '801970': '环保', '801980': '美容护理'
}

# 模块级缓存 模块级缓存，不参与pickle序列化
__all_securities_cache = {'data': None, 'etf_data': None, 'date': None}

# 名称缓存限容 限制安全名称缓存大小
_SECURITY_NAME_CACHE_MAX = 500


# ==================== 统一日志函数 ====================
# 格式: [S编号] 模块 | 信息    例: [S1] 轮动 | 排名: 纳指(2.88) > 创业板(1.36)
_SLOG_STRATEGY_MAP = {
    'S1': 'ETF轮动',
    'S2': '红利指数',
    'S3': 'QDII套利',
    'S4': '博收益ETF',
    'S5': '小市值',
}

def _slog(sid, module, msg, level='info'):
    """统一日志: [S编号] 模块 | 信息"""
    prefix = f"[{sid}] {module}"
    text = f"{prefix} | {msg}"
    getattr(log, level)(text)

# 正则预编译 预编译正则表达式
_BOYI_EXCLUDE_PATTERN = None
_BOYI_SPECIAL_PATTERNS = {}
_BOYI_COMPILED = False

def _compile_boyi_patterns():
    """正则预编译 预编译博收益策略的关键词正则，避免每次调用都重新匹配"""
    global _BOYI_EXCLUDE_PATTERN, _BOYI_SPECIAL_PATTERNS, _BOYI_COMPILED
    if _BOYI_COMPILED:
        return

    exclude_keywords = [
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ]
    # 按长度降序排列，确保长关键词优先匹配
    exclude_keywords.sort(key=len, reverse=True)
    _BOYI_EXCLUDE_PATTERN = re.compile('|'.join(re.escape(k) for k in exclude_keywords))

    _BOYI_SPECIAL_PATTERNS = {
        '创业组': re.compile('|'.join(re.escape(k) for k in
            sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True))),
        '科创组': re.compile('|'.join(re.escape(k) for k in
            sorted(['科创', '科创板', '科综', '双创', '科创创业', '创创'], key=len, reverse=True))),
        '香港组': re.compile('|'.join(re.escape(k) for k in
            sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '中概'], key=len, reverse=True))),
        '美指组': re.compile('|'.join(re.escape(k) for k in
            sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True))),
    }
    _BOYI_COMPILED = True


def _get_all_securities_info():
    """模块级缓存 获取证券信息缓存（模块级，不参与pickle）"""
    today = datetime.date.today()
    if __all_securities_cache['data'] is not None and __all_securities_cache['date'] == today:
        return __all_securities_cache['data'], __all_securities_cache['etf_data']
    etf_data = get_all_securities(['etf'])
    fund_data = get_all_securities(['etf', 'fund'])
    __all_securities_cache['data'] = fund_data
    __all_securities_cache['etf_data'] = etf_data
    __all_securities_cache['date'] = today
    return fund_data, etf_data


# ==================== 初始化函数 ====================
def initialize(context):

    unschedule_all()
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('order', 'error')
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001, close_commission=0.0001, close_today_commission=0.0001, min_commission=5), type="fund")
    set_subportfolios([
        SubPortfolioConfig(cash=50000, type='stock'),
        SubPortfolioConfig(cash=20000, type='stock'),
        SubPortfolioConfig(cash=20000, type='stock'),
        SubPortfolioConfig(cash=40000, type='stock'),
        SubPortfolioConfig(cash=50000, type='stock'),
    ])
    g.run_days = 0
    # 模块级缓存 不再将大DataFrame存入g，改为模块级缓存
    # g.all_securities_info = get_all_securities(['etf', 'fund'])  # 旧代码
    # g.all_etf_info = get_all_securities(['etf'])  # 旧代码
    _get_all_securities_info()  # 预加载到模块级缓存
    init_strategies(context)
    _validate_etf_pool(context)
    setup_schedule(context)
    init_sub_strategy_records(context)

def _validate_etf_pool(context):
    fixed_pool = getattr(g, 'fixed_etf_pool', [])
    if not fixed_pool:
        return
    all_info, _ = _get_all_securities_info()
    valid_pool = []
    invalid_list = []
    for etf in fixed_pool:
        if etf in all_info.index:
            valid_pool.append(etf)
        else:
            invalid_list.append(etf)
            log.warn(f"[ETF池校验] 无效/已下线标的已移除: {etf}")
    removed = len(fixed_pool) - len(valid_pool)
    if removed > 0:
        log.info(f"[ETF池校验] 共移除 {removed} 只无效标的，池子剩余 {len(valid_pool)} 只")
    if invalid_list:
        log.info(f"[ETF池校验] 无效清单: {invalid_list}")
    g.fixed_etf_pool = valid_pool

def init_sub_strategy_records(context):
    # 记录窗口限制 滚动窗口从60降至30，减少g对象大小
    g.sub_strategy_records = {
        'strategy1': {'name': 'S1_ETF轮动', 'initial_cash': 50000, 'daily_values': [], 'daily_dates': [], 'daily_returns': []},
        'strategy2': {'name': 'S2_4支红利', 'initial_cash': 20000, 'daily_values': [], 'daily_dates': [], 'daily_returns': []},
        'strategy3': {'name': 'S3_QDII套利', 'initial_cash': 20000, 'daily_values': [], 'daily_dates': [], 'daily_returns': []},
        'strategy4': {'name': 'S4_博收益ETF(新)', 'initial_cash': 40000, 'daily_values': [], 'daily_dates': [], 'daily_returns': []},
        'strategy5': {'name': 'S5_小市值', 'initial_cash': 50000, 'daily_values': [], 'daily_dates': [], 'daily_returns': []}
    }

def init_strategies(context):
# ==================== S1 ETF轮动策略参数（新版大ETF池） ====================
# etf_pool: 轮动候选池(ETF列表); 修改需同时更新代码中引用
# etf_pool_bak: 小ETF池(备用)
# lookback_days: 动量回看窗口(日); 增大→长趋势/减小→更敏感; 推荐15-40
# holdings_num: 持仓ETF数量; 推荐1-4
# defensive_etf: 防御ETF（货币基金）
# min_money: 最小交易金额(元); 推荐1000-5000
# loss: 连跌过滤阈值; 推荐0.95-0.98
# min/max_score_threshold: 动量得分阈值范围
# enable_profit_protection: True=启用盈利保护
# profit_protection_lookback: 盈利保护回看周期（天）
# profit_protection_threshold: 盈利保护回撤阈值
# profit_protection_check_times: 盈利保护检查时间点
# use_short_momentum_filter: True=启用短动量过滤
# short_lookback_days: 短动量回看天数; 推荐5-15
# short_momentum_threshold: 短动量阈值
# enable_volume_check: True=启用成交量过滤
# volume_threshold: 量比阈值; 推荐1.5-3.0
# enable_premium_filter: True=启用溢价率过滤
# premium_threshold: 溢价率阈值
# rebalance_cap: 再平衡截流上限(None=不限)
    g.etf4_strategy = {
        'name': 'ETF轮动', 'pindex': 0,
        'etf_pool_bak': [
            "518880.XSHG",   # 黄金ETF
            "159985.XSHE",   # 豆粕ETF
            "501018.XSHG",   # 南方原油
            "161226.XSHE",   # 白银LOF
            "513100.XSHG",   # 纳指ETF
            "159915.XSHE",   # 创业板ETF
            "511220.XSHG",   # 城投债ETF
        ],
        'etf_pool': [
            # 大宗商品ETF
            "518880.XSHG",  # 黄金ETF
            "159980.XSHE",  # 有色ETF
            "159985.XSHE",  # 豆粕ETF
            "501018.XSHG",  # 南方原油
            "161226.XSHE",  # 白银LOF
            "159981.XSHE",  # 能源化工ETF
            # 国际ETF
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
            # 香港ETF
            "159792.XSHE",  # 港股互联ETF
            "513130.XSHG",  # 恒生科技
            "513050.XSHG",  # 中概互联网ETF
            "159920.XSHE",  # 恒生ETF
            "513690.XSHG",  # 港股红利
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
            "512040.XSHG",  # 价值ETF
            "159201.XSHE",  # 自由现金流ETF
            # 债券ETF
            "511380.XSHG",  # 可转债ETF
            "511010.XSHG",  # 国债ETF
            "511220.XSHG",  # 城投债ETF
        ],
        'lookback_days': 25, 'holdings_num': 1, 'min_money': 5000,
        'defensive_etf': "511880.XSHG",  # 货币基金（防御标的）
        'loss': 0.97,
        'min_score_threshold': 0, 'max_score_threshold': 100.0,
        'enable_profit_protection': True,
        'profit_protection_lookback': 1,
        'profit_protection_threshold': 0.05,
        'profit_protection_check_times': ['11:00'],
        'enable_volume_check': True, 'volume_lookback': 5, 'volume_threshold': 2,
        'volume_return_limit': 1,
        'use_short_momentum_filter': True, 'short_lookback_days': 10, 'short_momentum_threshold': 0.0,
        'enable_premium_filter': True, 'premium_threshold': 0.20,
        'positions': {}, 'rankings_cache': {'date': None, 'data': None},
        'rebalance_cap': None,  # 再平衡截流上限
    }
# ==================== S2 红利指数策略参数 ====================
# etfs: 红利ETF名称→代码映射; 修改需同时更新target_ratio
# target_ratio: 目标仓位比例(合计=1.0)
# lookback_days: 回归回看窗口(日); 推荐60-250
# std_multiplier: 标准差倍数; 推荐1.0-2.5
# vol_adjust: True=波动率调整权重
# min_trade_value: 最小交易金额(元); 推荐500-2000
# stop_loss/stop_gain: 止损/止盈线; 推荐-0.05~-0.15 / 0.15-0.30
# rebalance_freq: 再平衡频率; 'monthly'/'weekly'
# hk_max_ratio: 港股ETF最大仓位比; 推荐0.3-0.6
# rebalance_cap: 再平衡截流上限(None=不限)
    g.hongli_strategy = {
        'name': '4支红利指数', 'pindex': 1,
        'etfs': {'中证红利ETF': '515080.XSHG', '上证红利ETF': '510880.XSHG', '红利低波ETF': '512890.XSHG', '红利低波50ETF': '515450.XSHG'},
        'target_ratio': {'中证红利ETF': 0.25, '上证红利ETF': 0.20, '红利低波ETF': 0.30, '红利低波50ETF': 0.25},
        'lookback_days': 180, 'min_lookback': 60, 'std_multiplier': 1.5,
        'vol_adjust': True, 'vol_lookback': 60, 'min_trade_value': 1000,
        'stop_loss': -0.08, 'stop_gain': 0.20, 'rebalance_freq': 'monthly', 'hk_max_ratio': 0.15, 'debug': True,
        'rebalance_cap': None,  # 再平衡截流上限
    }
# ==================== S3 QDII套利策略参数 ====================
# ratio: 折溢价率Series(运行时变量)
# daily_loss_limit: 单日亏损阈值; 推荐0.02-0.05
# hold_time_limit: 最长持仓天数; 推荐5-30
# partial_stop_threshold: 部分止损阈值; 推荐0.05-0.10
# full_stop_threshold: 全部止损阈值; 推荐0.10-0.20
# min_daily_volume/money: 最低日均成交量/额; 推荐1000/500000
# cool_down_days: 冷却期天数; 推荐1-5
# max_position_pct: 单只最大仓位比; 推荐0.3-0.6
# rebalance_cap: 再平衡截流上限(None=不限)
    g.qdii_strategy = {
        'name': 'QDII套利', 'pindex': 2, 'ratio': pd.Series(),
        'daily_loss_limit': 0.02, 'hold_time_limit': 10,
        'partial_stop_threshold': 0.10, 'full_stop_threshold': 0.20,
        'min_daily_volume': 10000, 'min_daily_money': 2e6,
        'cool_down_days': 3, 'previous_day_value': None,
        'last_update_date': None, 'position_peak_value': {},
        'position_entry_date': {}, 'last_sell_date': {},
        'rebalance_cap': None,  # 再平衡截流上限
    }
    # ==================== S4 博收益ETF v5.1 参数 ====================
    g.boyishouyi_pindex = 3
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
        '164824.XSHE',  # (印度基金LOF) [ETF]-日均成交额：0.50亿元-上市日期：2018-08-31
        "513080.XSHG",  # 法国ETF
        "513730.XSHG",  # 东南亚ETF
        "511010.XSHG",  # 国债ETF
        "511220.XSHG",  # 城投债E
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
        '513190.XSHG',  # (H股金融) [ETF]-日均成交额：3.74亿元-上市日期：2023-10-11
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
    g.fixed_etf_pool = list(dict.fromkeys(g.global_etf_pool + g.china_etf_pool))

    g.avg_etf_money_threshold = None
    # 全市场近3日 ETF 日均总成交额 avg_total_money；门槛 = avg_total_money / 分母（原硬编码 20000）
    g.global_liquidity_threshold_divisor = 3000
    g.filtered_fixed_pool = []
    g.dynamic_etf_pool = []
    g.merged_etf_pool = []
    g.ranked_etfs_result = []
    g.filtered_global_pool = []

    # 三态市场：走弱期 / 正常期 / 震荡期（每日 09:40 判定，全日有效）
    g.market_regime = '震荡期'
    g.is_a_share_weak = False  # 等价于 market_regime == '走弱期'，便于旧逻辑阅读
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
    g.weak_period_ma_lookback = 10     # 保留变量名，与 normal_ma_lookback 一致
    # 六指数齐备时：below_ma20 计数 ≥ 此值 → 走弱期；above_ma10 计数 ≥ 此值 → 正常期（且未触发走弱）
    g.regime_weak_below_ma20_min = 4   # 默认 6 即「六指均跌破 MA20」
    g.regime_normal_above_ma10_min = 4

    # 震荡期高斯滤波
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002  # 绝对斜率 g1-g2 时的阈值（gaussian_use_relative_slope=False）
    # True：斜率改为 (g1-g2)/g2，与拉普拉斯相对斜率口径一致，便于低价标的公平比较；False：沿用原绝对差
    g.gaussian_use_relative_slope = True
    g.gaussian_min_slope_relative = 0.001  # 相对斜率阈值（仅 gaussian_use_relative_slope=True 时参与比较）

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

    # ==================== 震荡收割 / Whipsaw ====================
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
    g.log_trade_detail = True   # 买卖决策/止损触发日志开关
    g.log_ranking_detail = True # 动量排名详情日志开关
    g.log_filter_detail = True  # 过滤流水线/选股漏斗日志开关
    g.log_pool_update_details = False      # 阈值/池更新相关详细日志
    g.log_first_step_ranking = False       # 动量第一步全量排序日志

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
    g.laplace_s_param_normal = 0.05   # 正常期 s（较 0.05 略宽松，减少震荡误杀）
    g.laplace_s_param_weak = 0.04     # 走弱期 s（更宽松，减轻海外 ETF 强趋势被过度平滑）
    g.laplace_min_slope = 0.0005
    # P0-2 参数补丁（可回滚）：仅正常期放宽部分过滤，降低边缘误杀
    g.enable_p0_state_tuning_patch = True
    g.normal_r2_threshold_override = 0.39
    g.normal_laplace_min_slope_override = 0.0024

    # 走弱期是否参与各过滤：True=走弱期与正常/震荡同样对待该步；False=走弱期跳过该步（与 v3-1 对齐的默认见下方）
    g.weak_apply_r2_filter = False       # False=走弱期不做 R²（同 五福51-v3-1）；True=走弱期也筛 R²（v3-2 新行为）
    g.weak_apply_ma_filter = True
    g.weak_apply_volume_filter = False
    g.weak_apply_loss_filter = True
    g.weak_apply_premium_filter = True   # True=全局开溢价时走弱期也筛（同 v3-1）；False=走弱期不筛溢价
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
    g.drawdown_records = []
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
    g.fixedStopLossThreshold = 0.92
    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95
    # 当日 13:10 午盘买入前发生的「分钟止损」成功后，若干交易日内禁止买回同一标的（可调）
    g.enable_stop_loss_rebuy_cooldown = True
    # 止损日期的次一交易日起计，连续 N 个交易日不得买入（默认 2：约等价于「两天内不接」）
    g.stop_loss_rebuy_cooldown_trade_days = 2
    # 仅统计此时刻之前的止损（应与 afternoon_routine 时间一致，默认 13:10）
    g.stop_loss_rebuy_cutoff_time = '13:10'
    g.stop_loss_rebuy_first_allowed_date = {}  # code -> 首个允许再买回的交易日 date
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

    # ==================== S5 小市值策略 ====================
# ==================== S5 小市值策略参数 ====================
# pindex: 子组合索引(0-4); 勿修改
# filter_market_cap_min/max: 市值范围(亿); 推荐8-20 / 50-150
# max_stock_price: 最高股价(元); 推荐30-100
# min_listed_days: 最少上市天数; 推荐250-500
# max_position_count: 最大持仓数; 推荐3-10
# enable_dynamic_stock_num: True=按MA10偏离动态调仓
# defensive_etf: 防御ETF代码; 走弱时切换
# stoploss_limit/market: 涨停/市场暴跌止损阈值
# stoploss_strategy: 止损策略编号; 3=ATR+成本保护+市场
# atr_period/multiplier: ATR周期/止损倍数; 推荐14/1.5-3.0
# cost_protection_*: 成本保护止盈止损(两档)
# DBL_control/check_macd_divergence_days: MACD背离开关/回看天数
# enable_audit_filter/audit_tolerance: 审计开关/容差项数
# enable_bonus_filter: 分红过滤开关(5月)
# enable_cooldown/cooldown_days: 冷却期开关/天数
# rebalance_cap: 再平衡截流上限(None=不限)
    g.small_strategy = {
        'name': 'S5_小市值(独立版V3)', 'pindex': 4,
        'filter_market_cap_min': 10, 'filter_market_cap_max': 100,
        'max_stock_price': 50, 'min_listed_days': 375,
        'max_position_count': 5, 'min_buy_amount': 200,
        'enable_dynamic_stock_num': True,
        'defensive_etf': '511880.XSHG',
        'stoploss_limit': 0.09, 'stoploss_market': 0.05,
        'stoploss_strategy': 3,
        'yesterday_HL_list': [], 'reason_to_sell': '', 'not_buy_again': [],
        'limitup_sold_today': [], 'initial_total_value': 0, 'position_size': 0,
        'enable_atr_stop_loss': True, 'atr_period': 14, 'atr_multiplier': 2.0,
        'atr_stop_prices': {},
        'enable_cost_protection': True,
        'cost_protection_profit_threshold_1': 0.15, 'cost_protection_profit_threshold_2': 0.30,
        'cost_protection_stop_line_1': 0.00, 'cost_protection_stop_line_2': 0.10,
        'DBL_control': True, 'dbl': [], 'check_macd_divergence_days': 10,
        'enable_audit_filter': True, 'enable_bonus_filter': True,
        'audit_tolerance': 2,
        'enable_cooldown': True, 'cooldown_days': 2, 'no_buy_stocks': {},
        'days': 0, 'first_run': True,
        'stocks': [],
        'rebalance_cap': None,  # 再平衡截流上限（None=无限制）
    }

    _validate_etf_pool(context)

def setup_schedule(context):
    run_daily(etf4_check_positions, '09:10')
    run_daily(etf4_sell_trade, '13:16')
    run_daily(etf4_buy_trade, '13:21')  # 拉长5分钟间隔，确保卖出成交回款
    # 动态注册盈利保护检查时间点
    strategy = g.etf4_strategy
    for check_time in strategy.get('profit_protection_check_times', []):
        run_daily(etf4_profit_protection_check, check_time)
    run_daily(hongli_before_trading, 'before_open')
    run_monthly(hongli_trade_rebalance, 1, time='10:00')
    run_daily(qdii_iUpdate, '9:35')
    run_daily(qdii_iTrader, '9:36')
    run_daily(qdii_iUpdate, '10:31')
    run_daily(qdii_iTrader, '10:32')
    run_daily(qdii_iReport, 'after_close')
    # S4 博收益ETF v5.1 定时任务
    run_daily(boyishouyi_morning_routine, '09:00')
    run_daily(boyishouyi_drawdown_monitor_routine, '10:31')
    run_daily(boyishouyi_check_weak_period_daily, '09:40')
    run_daily(boyishouyi_midday_routine, '10:00')
    run_daily(boyishouyi_afternoon_sell, '13:10')
    run_daily(boyishouyi_afternoon_buy, '13:15')  # 拉长5分钟间隔，确保卖出成交回款
    run_daily(boyishouyi_holdings_ma_break_1450_check, '14:50')
    run_daily(boyishouyi_reset_daily_flags, '15:10')
    run_daily(boyishouyi_after_close_regime_statistics, 'after_close')
    run_daily(boyishouyi_minute_stop_loss, 'every_bar')
    run_daily(boyishouyi_minute_pct_stop_loss, 'every_bar')
    run_daily(boyishouyi_record_daily_positions, '15:30')
    run_daily(boyishouyi_output_positions_summary, 'after_close')
    run_daily(small_before_trading, 'before_open')
    run_weekly(small_iSell, 2, '09:50')   # 每周二调仓卖出（→09:50 提前，预留卖出成交时间）
    run_weekly(small_iBuy, 2, '10:00')    # 每周二调仓买入（滞后10分钟，卖出已提交）
    run_daily(small_daily_stoploss, '10:05')
    run_daily(small_check_macd_divergence_daily, '09:31')
    run_daily(small_check_limit_up, '14:30')
    run_daily(small_iReport, 'after_close')
    run_daily(record_daily_performance, 'after_close')
    run_daily(daily_memory_cleanup, 'after_close')
    run_daily(daily_closing_summary, 'after_close')
    run_monthly(rebalance_evaluate, 1, '09:25')   # 每月1号评估+设置截流
    run_monthly(rebalance_transfer_cash, 3, '14:50')  # 每月3号转移现金

# ==================== 进程重启时恢复 ====================
def process_initialize(context):
    unschedule_all()
    setup_schedule(context)
    log.info(f'[全局] 初始化 | ' + f"进程重启, run_days={getattr(g, 'run_days', 'N/A')}")
    # 安全合并：防止pickle中缺少新版本代码新增的参数
    _safe_reinit_strategies(context)
    # 模块级缓存 重新加载模块级缓存
    _get_all_securities_info()
    # 正则预编译 重新编译正则
    _compile_boyi_patterns()

def _safe_reinit_strategies(context):
    """代码变更后安全重新初始化策略参数：仅添加新参数，不覆盖已有运行时状态"""
    # Step 1: 先保存所有dict策略的当前值（在init重置之前）
    saved_all = {}
    for attr in ['etf4_strategy', 'hongli_strategy', 'qdii_strategy', 'small_strategy']:
        if hasattr(g, attr):
            saved_all[attr] = dict(getattr(g, attr))
    # Step 1b: 保存S4博收益运行时状态（非dict的g.*属性，被init_strategies重置但需保留）
    _s4_runtime_attrs = [
        'merged_etf_pool', 'dynamic_etf_pool', 'filtered_fixed_pool',
        'ranked_etfs_result', 'filtered_global_pool',
        'market_regime', 'is_a_share_weak',
        'regime_prev_day', 'regime_prev_prev_day',
        'regime_flip_flop_count', 'regime_switch_confirm_days',
        'regime_switch_pending_raw', 'regime_switch_pending_streak',
        'regime_last_change_date',
        'last_metrics_by_etf_code', 'etf_yesterday_close_batch',
        'etf_yesterday_nav_batch', 'global_liquidity_threshold_divisor',
        'avg_etf_money_threshold',
    ]
    _saved_s4_runtime = {}
    for attr in _s4_runtime_attrs:
        if hasattr(g, attr):
            _saved_s4_runtime[attr] = getattr(g, attr)
    # Step 2: 一次性重新初始化（包括S4的g.xxx属性）
    init_strategies(context)
    # Step 3: 合并：仅添加新参数，保留运行时值
    for attr in saved_all:
        current = getattr(g, attr)
        for key, value in current.items():
            if key not in saved_all[attr]:
                saved_all[attr][key] = value
                log.info(f"[代码变更] 新增参数: {attr}['{key}'] = {value}")
        setattr(g, attr, saved_all[attr])
    # Step 3b: 恢复S4博收益运行时状态（防止process_initialize清空合并池等关键数据）
    for attr, value in _saved_s4_runtime.items():
        setattr(g, attr, value)
    # Clean up obsolete attributes from old pickle
    for attr in ['all_securities_info', 'all_etf_info', 'boyishouyi_strategy']:
        if hasattr(g, attr):
            try:
                delattr(g, attr)
                log.info(f"[代码变更] 清理废弃属性: g.{attr}")
            except Exception:
                pass
    # 再平衡系统属性
    if not hasattr(g, 'rebalance_config'):
        g.rebalance_config = {
            'alpha': 0.5,  # 基础比例与市值比例混合权重
            'base_ratios': [5/18, 2/18, 2/18, 4/18, 5/18],  # 初始资金比例
            'upper_factor': 2.0,  # 上限因子
            'lower_factor': 0.5,  # 下限因子
            'deviation_trigger': 0.5,  # 偏离触发阈值(50%)
            'min_transfer': 1000,  # 单次最小转移金额(元)
        }
        log.info("[代码变更] 新增全局属性: g.rebalance_config")
    # 补充已有rebalance_config中可能缺失的新key
    _rb_new_keys = {'min_transfer': 1000}
    for k, v in _rb_new_keys.items():
        if k not in g.rebalance_config:
            g.rebalance_config[k] = v
            log.info(f"[代码变更] 补充rebalance_config参数: {k} = {v}")
    if not hasattr(g, 'rebalance_pending'):
        g.rebalance_pending = False
        log.info("[代码变更] 新增全局属性: g.rebalance_pending")

def after_code_changed(context):
    log.info(f'[全局] 代码 | ' + '检测到变更, 重新初始化...')
    unschedule_all()
    setup_schedule(context)
    _safe_reinit_strategies(context)
    _validate_etf_pool(context)
    _get_all_securities_info()
    _compile_boyi_patterns()
    log.info(f'[全局] 代码 | ' + '初始化完成: 定时任务重注册 + 策略参数安全合并')


# ==================== 每日收盘摘要 ====================
def daily_closing_summary(context):
    """收盘后输出：总资产/年化/回撤/日盈亏 + 5策略持仓明细"""
    try:
        today = context.current_dt.date()
        total_value = sum(context.subportfolios[i].total_value for i in range(5))
        total_cash = sum(context.subportfolios[i].available_cash for i in range(5))
        total_initial = 180000

        # 累计收益率 & 年化
        cum_return = (total_value / total_initial - 1)
        days = max(g.run_days, 1)
        annualized = ((1 + cum_return) ** (252 / days) - 1) * 100

        # 最大回撤 (基于 sub_strategy_records 中的每日总值)
        max_dd = 0
        if hasattr(g, '_daily_total_values') and g._daily_total_values:
            g._daily_total_values.append(total_value)
            peak = g._daily_total_values[0]
            for v in g._daily_total_values:
                if v > peak:
                    peak = v
                dd = (peak - v) / peak
                if dd > max_dd:
                    max_dd = dd
        else:
            g._daily_total_values = [total_value]

        # 日盈亏
        daily_pnl = 0
        daily_pnl_pct = 0
        if hasattr(g, '_prev_total_value') and g._prev_total_value > 0:
            daily_pnl = total_value - g._prev_total_value
            daily_pnl_pct = daily_pnl / g._prev_total_value * 100
        g._prev_total_value = total_value

        # === 打印摘要 ===
        log.info(f'[全局] 日报 | ' + f"{today} | 总资产 {total_value:,.0f} | 年化 {annualized:.1f}% | 最大回撤 {max_dd*100:.1f}% | 日盈亏 {daily_pnl:+,.0f}({daily_pnl_pct:+.2f}%) | 可用 {total_cash:,.0f}")

        strategy_names = ['S1-ETF轮动', 'S2-红利指数', 'S3-QDII套利', 'S4-博收益ETF', 'S5-小市值']
        strategy_allocs = [50000, 20000, 20000, 40000, 50000]

        for i in range(5):
            sp = context.subportfolios[i]
            sv = sp.total_value
            sc = sp.available_cash
            s_return = (sv / strategy_allocs[i] - 1) * 100
            positions = sp.positions
            pos_count = len([p for p in positions.values() if p.total_amount > 0])

            if pos_count == 0:
                _slog(f'S{i+1}', '日报', f"{strategy_names[i].split('-',1)[1]} | 市值 {sv:,.0f}(收益{s_return:+.1f}%) | 空仓")
                continue

            # 子策略回撤
            s_max_dd = 0
            dd_key = f'_daily_sv_{i}'
            if hasattr(g, dd_key):
                getattr(g, dd_key).append(sv)
                peak = getattr(g, dd_key)[0]
                for v in getattr(g, dd_key):
                    if v > peak: peak = v
                    dd = (peak - v) / peak
                    if dd > s_max_dd: s_max_dd = dd
            else:
                setattr(g, dd_key, [sv])

            _slog(f'S{i+1}', '日报', f"{strategy_names[i].split('-',1)[1]} | 市值 {sv:,.0f}(收益{s_return:+.1f}%) 回撤{s_max_dd*100:.1f}% 可用{sc:,.0f} | {pos_count}只持仓:")

            for sec, pos in positions.items():
                if pos.total_amount <= 0:
                    continue
                name = _get_security_name(sec)
                pnl_amount = pos.value - pos.avg_cost * pos.total_amount
                pnl_pct = (pos.price / pos.avg_cost - 1) * 100 if pos.avg_cost > 0 else 0
                # 持仓回撤
                pos_dd = 0
                if hasattr(pos, 'value') and pos.avg_cost > 0:
                    pos_dd = max(0, (pos.avg_cost * pos.total_amount - pos.value) / (pos.avg_cost * pos.total_amount)) * 100
                _slog(f'S{i+1}', '持仓', f"  {sec} {name} | {pos.total_amount}股 成本{pos.avg_cost:.3f} 现价{pos.price:.3f} | 市值{pos.value:,.0f} 盈亏{pnl_amount:+,.0f}({pnl_pct:+.1f}%)")

        # 市场状态 & 信号统计
        regime = getattr(g, 'market_regime', '未知')
        log.info(f'[全局] 日报 | ' + f"市场状态: {regime} | run_days={g.run_days}")

    except Exception as e:
        log.error(f'[全局] 日报 | ' + f"生成失败: {e}")


def _get_security_name(sec):
    """获取证券名称（带缓存）"""
    if hasattr(g, '_security_name_cache') and sec in g._security_name_cache:
        return g._security_name_cache[sec]
    try:
        info = get_all_securities(['stock', 'etf', 'fund'])
        if sec in info.index:
            name = info.loc[sec, 'display_name']
            if not hasattr(g, '_security_name_cache'):
                g._security_name_cache = {}
            g._security_name_cache[sec] = name
            return name
    except:
        pass
    return sec


def record_daily_performance(context):
    try:
        g.run_days += 1
        current_date = context.current_dt.date()
        records_to_log = {}
        # 记录窗口限制 滚动窗口降至30
        MAX_DAILY_RECORDS = 30
        for i, strategy_key in enumerate(['strategy1', 'strategy2', 'strategy3', 'strategy4', 'strategy5']):
            sub_portfolio = context.subportfolios[i]
            strategy_info = g.sub_strategy_records[strategy_key]
            initial_cash = strategy_info['initial_cash']
            current_value = sub_portfolio.total_value
            strategy_info['daily_values'].append(current_value)
            strategy_info['daily_dates'].append(current_date)
            strategy_info['daily_returns'].append((current_value / initial_cash - 1) * 100)
            if len(strategy_info['daily_values']) > MAX_DAILY_RECORDS:
                strategy_info['daily_values'] = strategy_info['daily_values'][-MAX_DAILY_RECORDS:]
                strategy_info['daily_dates'] = strategy_info['daily_dates'][-MAX_DAILY_RECORDS:]
                strategy_info['daily_returns'] = strategy_info['daily_returns'][-MAX_DAILY_RECORDS:]
            records_to_log[strategy_info['name']] = strategy_info['daily_returns'][-1]
        record(**records_to_log)
        if context.current_dt.weekday() == 4:
            log_performance_summary(context)
    except Exception as e:
        log.error(f"记录每日收益时出错: {e}")

def log_performance_summary(context):
    log.info(f'[全局] 周报 | ' + '子策略收益汇总')
    total_initial = 180000
    total_current = sum(context.subportfolios[i].total_value for i in range(5))
    total_return = (total_current / total_initial - 1) * 100
    log.info(f"💰 总资金: {total_initial:,}元 → {total_current:,.0f}元, 总收益率: {total_return:.2f}%")
    for i, strategy_key in enumerate(['strategy1', 'strategy2', 'strategy3', 'strategy4', 'strategy5']):
        sub_portfolio = context.subportfolios[i]
        strategy_info = g.sub_strategy_records[strategy_key]
        initial_cash = strategy_info['initial_cash']
        current_value = sub_portfolio.total_value
        total_return_s = (current_value / initial_cash - 1) * 100
        days_count = g.run_days
        annualized_return = ((1 + total_return_s / 100) ** (252 / days_count) - 1) * 100 if days_count > 0 else 0
        log.info(f'[全局] 周报 | ' + f"{strategy_info['name']}:")
        log.info(f"  初始资金: {initial_cash:,}元, 当前价值: {current_value:,.0f}元")
        log.info(f"  累计收益: {total_return_s:.2f}%, 年化收益: {annualized_return:.2f}%")
        if sub_portfolio.positions:
            log.info(f"  持仓数量: {len(sub_portfolio.positions)}只")
        else:
            log.info("  当前无持仓")

def daily_memory_cleanup(context):
    """每日清理增强 增强版每日内存清理"""
    try:
        # 1. 清理索引缓存
        if hasattr(g, 'index_stocks_cache'):
            g.index_stocks_cache = {}

        # 2. 清理QDII历史数据
        if hasattr(g, 'qdii_strategy'):
            qdii = g.qdii_strategy
            if 'ratio_history' in qdii and len(qdii['ratio_history']) > 30:
                qdii['ratio_history'] = qdii['ratio_history'][-30:]
            # 清理QDII持仓峰值记录（只保留当前持仓的）
            if 'position_peak_value' in qdii:
                try:
                    current_positions = set(context.subportfolios[qdii['pindex']].positions.keys())
                    qdii['position_peak_value'] = {
                        k: v for k, v in qdii['position_peak_value'].items()
                        if k in current_positions
                    }
                except Exception as e:
                    _slog('S3', '清理', f'position_peak_value清理失败: {e}', 'warning')
            if 'position_entry_date' in qdii:
                try:
                    current_positions = set(context.subportfolios[qdii['pindex']].positions.keys())
                    qdii['position_entry_date'] = {
                        k: v for k, v in qdii['position_entry_date'].items()
                        if k in current_positions
                    }
                except Exception as e:
                    _slog('S3', '清理', f'position_entry_date清理失败: {e}', 'warning')
            if 'last_sell_date' in qdii:
                try:
                    current_positions = set(context.subportfolios[qdii['pindex']].positions.keys())
                    qdii['last_sell_date'] = {
                        k: v for k, v in qdii['last_sell_date'].items()
                        if k in current_positions
                    }
                except Exception as e:
                    _slog('S3', '清理', f'last_sell_date清理失败: {e}', 'warning')

        # 3. 清理ETF轮动排名缓存
        if hasattr(g, 'etf4_strategy') and 'rankings_cache' in g.etf4_strategy:
            g.etf4_strategy['rankings_cache'] = {'date': None, 'data': None}

        # 4. 名称字典裁剪 清理博收益策略的ETF名称字典（只保留需要的）
        if hasattr(g, 'etf_names_dict'):
            keep_etfs = set()
            keep_etfs.update(getattr(g, 'fixed_etf_pool', []))
            keep_etfs.update(getattr(g, 'dynamic_etf_pool', []))
            keep_etfs.update(getattr(g, 'merged_etf_pool', []))
            try:
                keep_etfs.update(context.subportfolios[getattr(g, 'boyishouyi_pindex', 3)].positions.keys())
            except Exception as e:
                _slog('S4', '清理', f'持仓ETF获取失败: {e}', 'warning')
            if keep_etfs and g.etf_names_dict:
                g.etf_names_dict = {
                    k: v for k, v in g.etf_names_dict.items()
                    if k in keep_etfs
                }

            # 清理临时缓存（新版S4用g.boyishouyi_xxx全局变量，非dict）
            for key in ['etf_yesterday_close_batch', 'etf_yesterday_nav_batch', 'yesterday_close_cache',
                        'stop_loss_blocked', 'low_liquidity_etfs', 'stop_loss_attempted_today']:
                attr = f'boyishouyi_{key}' if not key.startswith('boyishouyi_') else key
                if hasattr(g, attr):
                    val = getattr(g, attr)
                    setattr(g, attr, {} if isinstance(val, dict) else [])

            # 滚动窗口限制 drawdown_records 限制长度
            if hasattr(g, 'drawdown_records') and isinstance(g.drawdown_records, list) and len(g.drawdown_records) > 30:
                g.drawdown_records = g.drawdown_records[-30:]

        # 5. 清理小市值策略的列表
        if hasattr(g, 'small_strategy'):
            small = g.small_strategy
            small['yesterday_HL_list'] = []
            small['limitup_sold_today'] = []
            small['not_buy_again'] = []
            # 清理冷剘期中已过期的股票
            if 'no_buy_stocks' in small:
                current_date = context.current_dt.date()
                cooldown = small.get('cooldown_days', 2)
                expired = [k for k, v in small['no_buy_stocks'].items()
                           if len(get_trade_days(start_date=v, end_date=current_date)) - 1 >= cooldown]
                for k in expired:
                    del small['no_buy_stocks'][k]
            if 'dbl' in small and len(small['dbl']) > 60:
                small['dbl'] = small['dbl'][-60:]
            # 滚动窗口限制 清理已卖出股票的ATR止损价
            if 'atr_stop_prices' in small:
                try:
                    current_positions = set(context.subportfolios[small['pindex']].positions.keys())
                    small['atr_stop_prices'] = {
                        k: v for k, v in small['atr_stop_prices'].items()
                        if k in current_positions
                    }
                except Exception as e:
                    _slog('S5', '清理', f'atr_stop_prices清理失败: {e}', 'warning')

        # 6. 名称缓存限容 限制安全名称缓存大小
        global _security_name_cache
        if len(_security_name_cache) > _SECURITY_NAME_CACHE_MAX:
            # 保留最近的一半
            keys = list(_security_name_cache.keys())
            for k in keys[:len(keys)//2]:
                del _security_name_cache[k]

        # 7. 强制垃圾回收
        gc.collect()

        log.info(f'[全局] 清理 | ' + '每日内存清理完成')
    except Exception as e:
        log.error(f'[全局] 清理 | ' + f'内存清理出错: {e}')

_security_name_cache = {}

def get_security_name(security):
    """获取证券名称，优先从缓存/etf_names_dict获取"""
    # 名称字典裁剪 优先从博收益策略的etf_names_dict获取
    if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
        return g.etf_names_dict[security]
    if security in _security_name_cache:
        return _security_name_cache[security]
    try:
        all_info, _ = _get_all_securities_info()
        info = all_info.loc[security] if security in all_info.index else get_security_info(security)
        name = info.display_name if hasattr(info, 'display_name') else info.name
        _security_name_cache[security] = name
        return name
    except Exception:
        return str(security)

# ==================== S1 ETF轮动策略函数（新版大ETF池） ====================

def etf4_profit_protection_check(context):
    """独立执行的盈利保护检查函数，遍历所有持仓，若触发盈利保护则卖出"""
    strategy = g.etf4_strategy
    pindex = strategy['pindex']
    if not strategy.get('enable_profit_protection', False):
        return
    _slog('S1', '盈利保护', '检查开始')
    etf_pool = strategy['etf_pool']
    defensive_etf = strategy.get('defensive_etf', '511880.XSHG')
    for sec in list(context.subportfolios[pindex].positions.keys()):
        if sec not in etf_pool and sec != defensive_etf:
            continue
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount > 0:
            if etf4_check_profit_protection(sec, context, strategy):
                if etf4_smart_order_target_value(sec, 0, context, strategy):
                    _slog('S1', '盈利保护', f'卖出: {sec} {get_security_name(sec)}')
    _slog('S1', '盈利保护', '检查完毕')


def etf4_check_profit_protection(security, context, strategy, lookback=None, threshold=None):
    """检查是否触发盈利保护（从最近N日最高点回撤超过阈值）"""
    if not strategy.get('enable_profit_protection', False):
        return False
    lookback = lookback or strategy.get('profit_protection_lookback', 1)
    threshold = threshold or strategy.get('profit_protection_threshold', 0.05)
    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        return False
    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price
    if current_price <= max_high * (1 - threshold):
        _slog('S1', '盈利保护', f'🔻 {security} {get_security_name(security)} 触发: 现价{current_price:.3f}, {lookback}日最高{max_high:.3f}, 回撤{(1-current_price/max_high)*100:.2f}%>{threshold*100:.0f}%')
        return True
    return False


def etf4_get_premium_rate(code, date, max_back_days=5):
    """获取指定日期的溢价率，若当天无净值则向前搜索"""
    price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
    if price_data.empty:
        return None, None, None
    price = price_data['close'].iloc[0]
    net_value = None
    start_date = date - datetime.timedelta(days=max_back_days * 2)
    trade_days = get_trade_days(start_date=start_date, end_date=date)
    trade_days = [pd.to_datetime(d).date() for d in trade_days]
    for dt in reversed(trade_days):
        if dt > date:
            continue
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            break
        try:
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == dt
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                break
        except:
            continue
    if net_value is None:
        return None, None, None
    premium_rate = (price - net_value) / net_value
    return premium_rate, price, net_value


def etf4_get_volume_ratio(context, security, strategy):
    """计算当日成交量与过去N日均量的比值，若超过阈值则返回比值，否则None"""
    lookback = strategy.get('volume_lookback', 5)
    threshold = strategy.get('volume_threshold', 2)
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
    except Exception:
        return None


def etf4_check_positions(context):
    """每日开盘检查持仓状态，仅用于日志"""
    strategy = g.etf4_strategy
    pindex = strategy['pindex']
    for sec in context.subportfolios[pindex].positions:
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount > 0:
            _slog('S1', '持仓', f'{sec} {get_security_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}')


def etf4_sell_trade(context):
    """卖出不符合条件的持仓（排名变化、盈利保护）"""
    strategy = g.etf4_strategy
    pindex = strategy['pindex']
    _slog('S1', '卖出', '开始')
    etf_pool = strategy['etf_pool']
    defensive_etf = strategy.get('defensive_etf', '511880.XSHG')

    ranked = etf4_get_cached_rankings(context, strategy)
    target_etfs = []
    for m in ranked[:strategy['holdings_num']]:
        if m['score'] >= strategy['min_score_threshold']:
            target_etfs.append(m['etf'])
    # 防御模式：若无目标且防御可用，把防御ETF加入目标（供卖出判断用）
    defensive_available = etf4_check_defensive_etf_available(context, strategy)
    if not target_etfs and defensive_available:
        target_etfs = [defensive_etf]
    target_set = set(target_etfs)

    # 卖出不在目标列表的持仓
    for sec in list(context.subportfolios[pindex].positions.keys()):
        if sec not in etf_pool and sec != defensive_etf:
            continue
        if sec not in target_set:
            pos = context.subportfolios[pindex].positions[sec]
            if pos.total_amount > 0:
                if etf4_smart_order_target_value(sec, 0, context, strategy):
                    _slog('S1', '卖出', f'不在目标，卖出: {sec} {get_security_name(sec)}')
    _slog('S1', '卖出', '完毕')


def etf4_buy_trade(context):
    """买入符合条件的ETF，等权分配，按排名顺序逐个尝试直到凑够持仓数量"""
    strategy = g.etf4_strategy
    pindex = strategy['pindex']
    _slog('S1', '买入', '开始')
    etf_pool = strategy['etf_pool']
    defensive_etf = strategy.get('defensive_etf', '511880.XSHG')

    ranked = etf4_get_cached_rankings(context, strategy)
    # 打印排名前5的指标
    _slog('S1', '轮动', 'ETF排名前5')
    for i, m in enumerate(ranked[:5]):
        log.info(f"[S1] 排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} 年化{m['annualized_returns']*100:.2f}% R²={m['r_squared']:.4f}")

    # 确定目标ETF列表：依次尝试排名靠前的ETF
    target_etfs = []
    for m in ranked:  # 按得分从高到低遍历所有ETF
        if len(target_etfs) >= strategy['holdings_num']:
            break
        target_etfs.append(m['etf'])
        _slog('S1', '轮动', f'目标ETF {len(target_etfs)}: {m["etf"]} {m["etf_name"]} 得分{m["score"]:.4f}')

    # 防御模式判断
    if not target_etfs:
        if etf4_check_defensive_etf_available(context, strategy):
            target_etfs = [defensive_etf]
            _slog('S1', '防御', f'进入防御模式: {defensive_etf} {get_security_name(defensive_etf)}')
        else:
            _slog('S1', '买入', '无目标ETF且防御不可用，保持空仓')
            return

    # 检查是否有持仓需要先卖出（不在目标列表的持仓）
    current_etf_pos = [s for s in context.subportfolios[pindex].positions if s in etf_pool or s == defensive_etf]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        to_sell_names = [get_security_name(s) for s in to_sell]
        _slog('S1', '买入', f'尚有持仓需要卖出: {list(zip(to_sell, to_sell_names))}，等待卖出完成再买入')
        return

    # 等权分配
    total_val = context.subportfolios[pindex].total_value
    target_per_etf = total_val / len(target_etfs)
    # 再平衡截流
    if strategy.get('rebalance_cap') is not None:
        cap_per_etf = strategy['rebalance_cap'] / len(target_etfs)
        if target_per_etf > cap_per_etf:
            _slog('S1', '再平衡', f'截流: 原{target_per_etf:.0f}→{cap_per_etf:.0f}元/只 (上限{strategy["rebalance_cap"]:.0f})')
            target_per_etf = cap_per_etf

    for etf in target_etfs:
        current_val = 0
        if etf in context.subportfolios[pindex].positions:
            pos = context.subportfolios[pindex].positions[etf]
            if pos.total_amount > 0:
                current_val = pos.total_amount * pos.price
        # 5%容差调仓
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            if etf4_smart_order_target_value(etf, target_per_etf, context, strategy):
                action = '买入' if current_val < target_per_etf else '调仓'
                _slog('S1', action, f'{etf} {get_security_name(etf)} 目标金额{target_per_etf:.2f}')
    _slog('S1', '买入', '完毕')


def etf4_get_cached_rankings(context, strategy):
    """获取缓存的ETF排名，保证同一交易日内多次调用结果一致"""
    today = context.current_dt.date()
    if strategy['rankings_cache'].get('date') != today:
        _slog('S1', '轮动', '重新计算排名')
        ranked = etf4_get_ranked_etfs(context, strategy)
        strategy['rankings_cache'] = {'date': today, 'data': ranked}
    return strategy['rankings_cache']['data']


def etf4_get_ranked_etfs(context, strategy):
    """计算所有ETF的动量得分，应用所有过滤条件，返回按得分降序的列表"""
    etf_pool = strategy['etf_pool']
    lookback = max(strategy['lookback_days'], strategy.get('short_lookback_days', 10)) + 20
    hist_df = get_price(etf_pool, end_date=context.previous_date, count=lookback, frequency='1d', fields=['close'], panel=False)
    if hist_df is None or hist_df.empty:
        return []
    close_df = hist_df.pivot(index='time', columns='code', values='close')
    current_data = get_current_data()
    etf_metrics = []
    for etf in etf_pool:
        if current_data[etf].paused:
            continue
        if etf not in close_df.columns:
            continue
        closes = close_df[etf].dropna()
        if len(closes) < strategy['lookback_days']:
            continue
        current_price = current_data[etf].last_price
        metrics = etf4_calculate_momentum(etf, closes, current_price, context, strategy)
        if metrics and strategy['min_score_threshold'] < metrics['score'] < strategy['max_score_threshold']:
            etf_metrics.append(metrics)
    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def etf4_calculate_momentum(etf, closes, current_price, context, strategy):
    """计算单只ETF的动量指标，应用所有过滤条件"""
    try:
        etf_name = get_security_name(etf)
        lookback = max(strategy['lookback_days'], strategy.get('short_lookback_days', 10)) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < strategy['lookback_days']:
            return None
        price_series = np.append(closes.values, current_price)

        # 1. 盈利保护检查（排除）
        if etf4_check_profit_protection(etf, context, strategy):
            _slog('S1', '盈利保护', f'🚫 {etf} {etf_name} 触发，从排名中排除')
            return None

        # 2. 溢价率过滤
        if strategy.get('enable_premium_filter', False):
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = etf4_get_premium_rate(etf, prev_date)
            if premium is not None:
                if premium > strategy.get('premium_threshold', 0.20):
                    _slog('S1', '溢价过滤', f'🚫 {etf} {etf_name} 溢价率{premium*100:.2f}%>{strategy.get("premium_threshold",0.20)*100:.0f}%')
                    return None

        # 3. 成交量过滤
        if strategy.get('enable_volume_check', False):
            vol_ratio = etf4_get_volume_ratio(context, etf, strategy)
            if vol_ratio is not None:
                annualized = etf4_get_annualized_returns(price_series, strategy['lookback_days'])
                if annualized > strategy.get('volume_return_limit', 1):
                    _slog('S1', '量能过滤', f'📉 {etf} {etf_name} 放量{vol_ratio:.1f}倍且年化{annualized*100:.1f}%')
                    return None

        # 4. 短期动量过滤
        if strategy.get('use_short_momentum_filter', False):
            short_lookback = strategy.get('short_lookback_days', 10)
            if len(price_series) >= short_lookback + 1:
                short_return = price_series[-1] / price_series[-(short_lookback + 1)] - 1
                short_annualized = (1 + short_return) ** (250 / short_lookback) - 1
            else:
                short_annualized = 0
            if short_annualized < strategy.get('short_momentum_threshold', 0.0):
                return None
        else:
            short_annualized = 0

        # 5. 长期动量计算（得分）
        recent_prices = price_series[-(strategy['lookback_days'] + 1):]
        if len(recent_prices) < strategy['lookback_days'] + 1:
            return None
        y = np.log(recent_prices)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        # R²（趋势稳定性）
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0
        score = annualized_returns * r_squared

        # 6. 近3日单日跌幅过滤
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < strategy['loss']:
                _slog('S1', '跌幅过滤', f'⚠️ {etf} {etf_name} 近3日有单日跌幅超{(1-strategy["loss"])*100:.1f}%')
                return None

        return {
            'etf': etf, 'etf_name': etf_name,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'short_annualized': short_annualized,
        }
    except Exception as e:
        log.warning(f'[S1] 计算{etf} {get_security_name(etf)}动量出错: {e}')
        return None


def etf4_get_annualized_returns(price_series, lookback_days):
    """计算加权年化收益率"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def etf4_check_defensive_etf_available(context, strategy):
    """检查防御ETF是否可交易（未停牌、未涨跌停）"""
    data = get_current_data()
    etf = strategy.get('defensive_etf', '511880.XSHG')
    if data[etf].paused:
        return False
    if data[etf].last_price >= data[etf].high_limit:
        return False
    if data[etf].last_price <= data[etf].low_limit:
        return False
    return True


def etf4_smart_order_target_value(security, target_value, context, strategy):
    """智能下单：根据目标市值调整持仓，处理停牌、涨跌停、最小交易金额、T+1"""
    pindex = strategy['pindex']
    current_data = get_current_data()
    name = get_security_name(security)
    if current_data[security].paused:
        return False
    price = current_data[security].last_price
    if price == 0:
        return False
    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    cur_pos = context.subportfolios[pindex].positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount
    # 根据交易方向检查涨跌停
    if diff > 0:
        if current_data[security].last_price >= current_data[security].high_limit:
            return False
    elif diff < 0:
        if current_data[security].last_price <= current_data[security].low_limit:
            return False
    # 最小交易金额检查
    trade_val = abs(diff) * price
    if 0 < trade_val < strategy['min_money']:
        return False
    # T+1处理
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            return False
        diff = -min(abs(diff), closeable)
    if diff != 0:
        if diff < 0:
            # 卖出：用买一价确保快速成交，确保快速成交
            sell_price = None
            try:
                tick = get_current_tick(security)
                if tick is not None and tick.get('b1_p', 0) > 0:
                    sell_price = round(tick['b1_p'], 3)
            except Exception:
                pass
            if sell_price is None:
                sell_price = round(price * 0.99, 3)
            # 涨跌停保护
            low_limit = getattr(current_data[security], 'low_limit', None)
            if low_limit and sell_price < low_limit:
                sell_price = round(low_limit + 0.001, 3)
            order(security, diff, style=LimitOrderStyle(sell_price), pindex=pindex)
        else:
            order(security, diff, pindex=pindex)
        return True
    return False

# ==================== 策略2: 4支红利指数 ====================
def hongli_before_trading(context):
    strategy = g.hongli_strategy
    pindex = strategy['pindex']
    positions = context.subportfolios[pindex].positions
    cdata = get_current_data()
    for etf_name, etf_code in strategy['etfs'].items():
        if etf_code not in positions:
            continue
        pos = positions[etf_code]
        if pos.total_amount == 0:
            continue
        if cdata[etf_code].paused:
            continue
        current_price = cdata[etf_code].last_price
        if current_price >= cdata[etf_code].high_limit:
            continue
        if current_price <= cdata[etf_code].low_limit:
            continue
        pnl_ratio = (current_price - pos.avg_cost) / pos.avg_cost
        if pnl_ratio <= strategy['stop_loss']:
            _slog('S3', '止损', f'{etf_name}({etf_code}) 亏损{pnl_ratio*100:.1f}%, 触发止损', 'warning')
            order_target(etf_code, 0, pindex=pindex)
        elif pnl_ratio >= strategy['stop_gain']:
            _slog('S3', '止盈', f'{etf_name}({etf_code}) 盈利{pnl_ratio*100:.1f}%, 触发止盈', 'warning')
            order_target(etf_code, 0, pindex=pindex)

def hongli_get_etf_price(etf_code, context):
    try:
        return get_current_data()[etf_code].last_price
    except:
        return None

def hongli_trade_rebalance(context):
    strategy = g.hongli_strategy
    pindex = strategy['pindex']
    total_value = context.subportfolios[pindex].total_value
    _slog('S1', '检查', f'总资产: {total_value:.2f}')
    valid_etfs = {k: v for k, v in strategy['etfs'].items() if not get_current_data()[v].paused}
    if not valid_etfs:
        log.warn(f"[{strategy['name']}] 没有有效的ETF数据，跳过")
        return
    for etf_name, etf_code in valid_etfs.items():
        target_value = total_value * strategy['target_ratio'].get(etf_name, 0.25)
        position = context.subportfolios[pindex].positions.get(etf_code, None)
        current_value = position.value if position else 0
        if abs(current_value - target_value) < 1000:
            continue
        current_price = hongli_get_etf_price(etf_code, context)
        if not current_price:
            continue
        diff_amount = int((target_value - current_value) / current_price / 100) * 100
        if abs(diff_amount) > 0:
            order(etf_code, diff_amount, pindex=pindex)
            log.info(f"[{strategy['name']}] 调仓 {etf_name}: {diff_amount}股")

# ==================== 策略3: QDII套利 ====================
def qdii_check_daily_loss(context, strategy):
    current_date = context.current_dt.date()
    current_value = context.subportfolios[strategy['pindex']].total_value
    if strategy['previous_day_value'] is None or strategy['last_update_date'] != current_date:
        strategy['previous_day_value'] = current_value
        strategy['last_update_date'] = current_date
        return
    daily_return = (current_value - strategy['previous_day_value']) / strategy['previous_day_value']
    if daily_return < -strategy['daily_loss_limit']:
        log.warn(f"[{strategy['name']}] 触发单日亏损限制: {daily_return:.2%}")
        strategy['previous_day_value'] = current_value
        strategy['last_update_date'] = current_date

def qdii_check_pre_trade_risk(context, strategy):
    if strategy['previous_day_value'] is None:
        return True
    current_value = context.subportfolios[strategy['pindex']].total_value
    daily_return = (current_value - strategy['previous_day_value']) / strategy['previous_day_value']
    if daily_return < -strategy['daily_loss_limit']:
        log.info(f"[{strategy['name']}] 昨日亏损 {daily_return:.2%}，暂停新买入")
        return False
    return True

def qdii_update_position_peaks(context, strategy):
    pindex = strategy['pindex']
    for stock in context.subportfolios[pindex].positions:
        current_value = context.subportfolios[pindex].positions[stock].value
        if stock not in strategy['position_peak_value']:
            strategy['position_peak_value'][stock] = current_value
        elif current_value > strategy['position_peak_value'][stock]:
            strategy['position_peak_value'][stock] = current_value

def qdii_check_partial_stop_loss(context, strategy):
    pindex = strategy['pindex']
    cdata = get_current_data()
    for stock in list(context.subportfolios[pindex].positions.keys()):
        if stock not in strategy['position_peak_value']:
            continue
        current_value = context.subportfolios[pindex].positions[stock].value
        peak_value = strategy['position_peak_value'][stock]
        if peak_value > 0:
            drawdown = (peak_value - current_value) / peak_value
            if drawdown > strategy['full_stop_threshold']:
                log.warn(f"[{strategy['name']}] 触发全部止损: {stock}, 回撤: {drawdown:.2%}")
                order_target(stock, 0, LimitOrderStyle(0.99 * cdata[stock].last_price), pindex=pindex)
                if stock in strategy['position_peak_value']:
                    del strategy['position_peak_value'][stock]
            elif drawdown > strategy['partial_stop_threshold']:
                current_amount = context.subportfolios[pindex].positions[stock].total_amount
                target_amount = int(current_amount * 0.5)
                if target_amount > 0:
                    log.info(f"[{strategy['name']}] 触发部分止损: {stock}, 回撤: {drawdown:.2%}")
                    order_target(stock, target_amount, LimitOrderStyle(0.99 * cdata[stock].last_price), pindex=pindex)

def qdii_check_fund_liquidity(funds, context, strategy):
    if not funds:
        return []
    try:
        # 减少DataFrame开销 使用df=False减少开销
        volume_data = history(20, '1d', 'volume', funds, df=False)
        money_data = history(20, '1d', 'money', funds, df=False)
        liquid_funds = []
        for fund in funds:
            vol_arr = volume_data.get(fund)
            mon_arr = money_data.get(fund)
            if vol_arr is None or mon_arr is None:
                continue
            avg_vol = np.mean(vol_arr)
            avg_mon = np.mean(mon_arr)
            if avg_vol >= strategy['min_daily_volume'] and avg_mon >= strategy['min_daily_money']:
                liquid_funds.append(fund)
        return liquid_funds
    except:
        return funds

def qdii_record_position_entry(stock, current_date, strategy):
    strategy['position_entry_date'][stock] = current_date

def qdii_should_exit_position(context, stock, cdata, strategy):
    if stock not in strategy['ratio']:
        return True
    if strategy['ratio'][stock] >= 0.05:
        return True
    return False

def qdii_iUpdate(context):
    strategy = g.qdii_strategy
    keys = ['标普', '美国', '纳指', '纳斯达克', '法国', '德国', '日经', '亚太', '东南亚', '印度', '沙特']
    black_list = ['562060.XSHG']
    dt_last = context.previous_date
    all_fund = get_all_securities(['fund'], dt_last)
    try:
        pattern = '|'.join(keys)
        mask = all_fund.display_name.str.contains(pattern, na=False)
        funds = all_fund[mask].index.tolist()
        funds = [s for s in funds if s not in black_list]
    except:
        funds = []
    funds = qdii_check_fund_liquidity(funds, context, strategy)
    if funds:
        value = get_extras('unit_net_value', funds, end_date=dt_last, count=1).iloc[0]
        price = history(1, '1d', 'close', funds, df=False)
        # 减少DataFrame开销 df=False返回dict，需要转换
        price_dict = price
        r = pd.Series({k: price_dict[k][0] for k in price_dict if k in value.index}) / value - 1.0
        r = r[r < 0.15].sort_values()
        strategy['ratio'] = r
        log.info(f"[{strategy['name']}] 筛选出 {len(strategy['ratio'])} 只符合条件的基金")
        if not r.empty:
            log.info(f"[{strategy['name']}] === 折溢价率明细 ===")
            for code, prem_rate in r.items():
                fund_name = get_security_name(code)
                log.info(f"[{strategy['name']}]   {code} {fund_name}: 折溢价率 {prem_rate:.2%}")
    else:
        strategy['ratio'] = pd.Series()
        log.info(f"[{strategy['name']}] 无满足条件的基金")

def _get_bid1_sell_price(security, fallback_price):
    """获取买一价作为卖出限价，确保快速成交；无法获取时用fallback_price*0.99"""
    sell_price = None
    try:
        tick = get_current_tick(security)
        if tick is not None and tick.get('b1_p', 0) > 0:
            sell_price = round(tick['b1_p'], 3)
    except Exception:
        pass
    if sell_price is None:
        sell_price = round(fallback_price * 0.99, 3)
    return sell_price

def qdii_iTrader(context):
    strategy = g.qdii_strategy
    pindex = strategy['pindex']
    qdii_update_position_peaks(context, strategy)
    qdii_check_partial_stop_loss(context, strategy)
    if strategy['ratio'].empty:
        log.error(f"[{strategy['name']}] 无折溢价数据，跳过交易")
        return
    r = strategy['ratio']
    base_position_size = context.subportfolios[pindex].total_value / max(3, len(r))
    if strategy.get('rebalance_cap') is not None:
        cap_position_size = strategy['rebalance_cap'] / max(3, len(r))
        if base_position_size > cap_position_size:
            _slog('S3', '再平衡', f'截流: 持仓{base_position_size:.0f}→{cap_position_size:.0f}元 (上限{strategy["rebalance_cap"]:.0f})')
            base_position_size = cap_position_size
    # ===== S3截流结束 =====
    cdata = get_current_data()
    max_last_price = max((cdata[s].last_price for s in r.index), default=0)
    min_position = 100 * max_last_price if max_last_price > 0 else 600
    position_size = max(base_position_size, min_position)
    lm_value = 0.8 * position_size
    hm_value = 1.3 * position_size
    cash_size = 0.1 * context.subportfolios[pindex].total_value
    current_date = context.current_dt.date()
    can_buy_new = qdii_check_pre_trade_risk(context, strategy)
    if not can_buy_new:
        log.info(f"[{strategy['name']}] 风控限制：暂停新买入")
    log.info(f"[{strategy['name']}] === 卖出检查 | 当前持仓: {len(context.subportfolios[pindex].positions)} 只 ===")
    for stock in list(context.subportfolios[pindex].positions.keys()):
        if cdata[stock].paused:
            continue
        if stock in strategy['position_entry_date']:
            hold_days = (current_date - strategy['position_entry_date'][stock]).days
            if hold_days > strategy['hold_time_limit']:
                if qdii_should_exit_position(context, stock, cdata, strategy):
                    log.info(f"[{strategy['name']}] 持仓超时卖出: {stock}, 持有{hold_days}天")
                    _sell_price = 0.99 * cdata[stock].last_price
                    _down_limit = getattr(cdata[stock], 'low_limit', None)
                    _high_limit = getattr(cdata[stock], 'high_limit', None)
                    if _down_limit and _sell_price < _down_limit:
                        _sell_price = _down_limit + 0.001
                        log.info(f"[{strategy['name']}] 卖出限价上浮至跌停价: {stock}, {0.99 * cdata[stock].last_price:.3f} -> {_sell_price:.3f}")
                    if _high_limit and _sell_price > _high_limit:
                        _sell_price = _high_limit - 0.001
                        log.info(f"[{strategy['name']}] 卖出限价下压至涨停价: {stock}, {0.99 * cdata[stock].last_price:.3f} -> {_sell_price:.3f}")
                    order_target(stock, 0, LimitOrderStyle(_sell_price), pindex=pindex)
                    for key in ['position_entry_date', 'position_peak_value']:
                        if stock in strategy[key]:
                            del strategy[key][stock]
                continue
        if stock not in r.index:
            log.info(f"[{strategy['name']}] 不在目标列表，卖出: {stock}")
            _sell_price = 0.99 * cdata[stock].last_price
            _down_limit = getattr(cdata[stock], 'low_limit', None)
            _high_limit = getattr(cdata[stock], 'high_limit', None)
            if _down_limit and _sell_price < _down_limit:
                _sell_price = _down_limit + 0.001
                log.info(f"[{strategy['name']}] 卖出限价上浮至跌停价: {stock}, {0.99 * cdata[stock].last_price:.3f} -> {_sell_price:.3f}")
            if _high_limit and _sell_price > _high_limit:
                _sell_price = _high_limit - 0.001
                log.info(f"[{strategy['name']}] 卖出限价下压至涨停价: {stock}, {0.99 * cdata[stock].last_price:.3f} -> {_sell_price:.3f}")
            order_target(stock, 0, LimitOrderStyle(_sell_price), pindex=pindex)
            for key in ['position_entry_date', 'position_peak_value']:
                if stock in strategy[key]:
                    del strategy[key][stock]
    if not can_buy_new:
        return
    log.info(f"[{strategy['name']}] === 买入检查 | 可用现金: {context.subportfolios[pindex].available_cash:.2f} ===")
    for stock in r.index:
        if context.subportfolios[pindex].available_cash < cash_size:
            break
        if cdata[stock].paused:
            continue
        if stock not in context.subportfolios[pindex].positions:
            if r[stock] < 0:
                log.info(f"[{strategy['name']}] 新买入: {stock}, 折价{r[stock]:.2%}")
                _buy_price = 1.01 * cdata[stock].last_price
                _down_limit = getattr(cdata[stock], 'low_limit', None)
                _high_limit = getattr(cdata[stock], 'high_limit', None)
                if _down_limit and _buy_price < _down_limit:
                    _buy_price = _down_limit + 0.001
                    log.info(f"[{strategy['name']}] 买入限价上浮至跌停价: {stock}, {1.01 * cdata[stock].last_price:.3f} -> {_buy_price:.3f}")
                if _high_limit and _buy_price > _high_limit:
                    _buy_price = _high_limit - 0.001
                    log.info(f"[{strategy['name']}] 买入限价下压至涨停价: {stock}, {1.01 * cdata[stock].last_price:.3f} -> {_buy_price:.3f}")
                order_result = order_target_value(stock, position_size, LimitOrderStyle(_buy_price), pindex=pindex)
                if order_result is not None and order_result.filled > 0:
                    qdii_record_position_entry(stock, current_date, strategy)
        elif context.subportfolios[pindex].positions[stock].value < lm_value:
            if r[stock] < 0:
                log.info(f"[{strategy['name']}] 补仓: {stock}")
                _buy_price = 1.01 * cdata[stock].last_price
                _down_limit = getattr(cdata[stock], 'low_limit', None)
                _high_limit = getattr(cdata[stock], 'high_limit', None)
                if _down_limit and _buy_price < _down_limit:
                    _buy_price = _down_limit + 0.001
                    log.info(f"[{strategy['name']}] 补仓限价上浮至跌停价: {stock}, {1.01 * cdata[stock].last_price:.3f} -> {_buy_price:.3f}")
                if _high_limit and _buy_price > _high_limit:
                    _buy_price = _high_limit - 0.001
                    log.info(f"[{strategy['name']}] 补仓限价下压至涨停价: {stock}, {1.01 * cdata[stock].last_price:.3f} -> {_buy_price:.3f}")
                order_target_value(stock, position_size, LimitOrderStyle(_buy_price), pindex=pindex)
        elif context.subportfolios[pindex].positions[stock].value > hm_value:
            if r[stock] > 0:
                log.info(f"[{strategy['name']}] 减仓: {stock}, 溢价{r[stock]:.2%}")
                _sell_price = 0.99 * cdata[stock].last_price
                _down_limit = getattr(cdata[stock], 'low_limit', None)
                _high_limit = getattr(cdata[stock], 'high_limit', None)
                if _down_limit and _sell_price < _down_limit:
                    _sell_price = _down_limit + 0.001
                    log.info(f"[{strategy['name']}] 减仓限价上浮至跌停价: {stock}, {0.99 * cdata[stock].last_price:.3f} -> {_sell_price:.3f}")
                if _high_limit and _sell_price > _high_limit:
                    _sell_price = _high_limit - 0.001
                    log.info(f"[{strategy['name']}] 减仓限价下压至涨停价: {stock}, {0.99 * cdata[stock].last_price:.3f} -> {_sell_price:.3f}")
                order_target_value(stock, position_size, LimitOrderStyle(_sell_price), pindex=pindex)

def qdii_iReport(context):
    strategy = g.qdii_strategy
    pindex = strategy['pindex']
    qdii_check_daily_loss(context, strategy)
    cdata = get_current_data()
    tvalue = context.subportfolios[pindex].total_value
    ptable = pd.DataFrame(columns=['amount', 'value', 'weight', 'name', 'hold_days'])
    current_date = context.current_dt.date()
    for stock in context.subportfolios[pindex].positions:
        ps = context.subportfolios[pindex].positions[stock]
        hold_days = '-'
        if stock in strategy['position_entry_date']:
            hold_days = str((current_date - strategy['position_entry_date'][stock]).days)
        ptable.loc[stock] = [ps.total_amount, int(ps.value), 100 * ps.value / tvalue, cdata[stock].name, hold_days]
    ptable = ptable.sort_values(by='weight', ascending=False)
    log.info(f"[{strategy['name']}] 持仓数量: {len(ptable)}")
    log.info(f"[{strategy['name']}] 总资产: {context.subportfolios[pindex].total_value / 10000:.2f}万")

def boyishouyi_check_weak_period_daily(context):
    boyishouyi_resolve_market_regime(context)
    boyishouyi_midday_routine(context)


def boyishouyi_drawdown_monitor_routine(context):
    """组合回撤：在连续竞价后执行，用场内 last_price 估值（见 g.dd_valuation_use_mtm_last_price）。"""
    log.info(f'[全局] 回撤 | ' + f'盘中监控启动 {context.current_dt.strftime("%H:%M")}')
    boyishouyi_monitor_drawdown(context)
    log.info(f'[全局] 回撤 | ' + '盘中监控完毕')


def boyishouyi_morning_routine(context):
    log.info(f'[全局] 晨间 | ' + '流水线启动')
    log.info(f'[全局] 晨间 | ' + '持仓检查')
    boyishouyi_check_positions(context)
    log.info(
        f"【回撤监控】已移至盘中定时任务（默认 {getattr(g, 'dd_monitor_time', '10:31')}），"
        "避免开盘前无连续竞价价；QDII/LOF 请以该时点场内价口径为准。"
    )
    if getattr(g, 'log_pool_update_details', False):
        _slog('S4', '流动性', '计算全市场ETF阈值')
    boyishouyi_calculate_global_etf_threshold(context)
    log.info(f'[全局] 晨间 | ' + '流水线完毕')


def boyishouyi_refresh_holdings_num_by_regime(context):
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
        _slog('S4', '持仓数', f'切换: {regime}, {prev} → {new_holdings}')
    else:
        _slog('S4', '持仓数', f'{regime}, holdings_num={new_holdings}')


def boyishouyi_midday_routine(context):
    _slog('S4', '早盘', '流水线启动')
    
    if g.market_regime == '走弱期':
        _slog('S4', '池更新', '走弱期: 全球/海外ETF池流动性过滤')
        boyishouyi_filter_global_pool_by_volume(context)
        _slog('S4', '池更新', f'走弱期过滤后全球池: {len(g.filtered_global_pool)}只')
    else:
        _slog('S4', '池更新', f'{g.market_regime}: 执行动态池+固定池+合并池')
        if getattr(g, 'log_pool_update_details', False):
            _slog('S4', '动态池', '更新行业ETF动态池')
        boyishouyi_update_sector_pool(context)
        if getattr(g, 'log_pool_update_details', False):
            _slog('S4', '固定池', '过滤流动性')
        boyishouyi_filter_fixed_pool_by_volume(context)
        if getattr(g, 'log_pool_update_details', False):
            _slog('S4', '合并池', '合并固定池与动态池')
        boyishouyi_daily_merge_etf_pools(context)
        _slog('S4', '池更新', f'{g.market_regime}合并池: {len(g.merged_etf_pool)}只')
    
    _slog('S4', '早盘', '流水线完毕')


# ==================== 策略4: 博收益ETF轮动 v5.1（五福闹新春适配版）====================

def _boyishouyi_sp(context):
    """获取S4博收益子组合对象"""
    return context.subportfolios[3]

def boyishouyi_afternoon_sell(context):
    _slog('S4', '卖出', '流水线启动')
    boyishouyi_log_pending_short_momentum_3up_followups(context)

    if g.market_regime == '走弱期':
        if hasattr(g, 'filtered_global_pool') and g.filtered_global_pool:
            g.merged_etf_pool = list(set(g.filtered_global_pool))
        else:
            g.merged_etf_pool = list(set(g.global_etf_pool))
        g.merged_etf_pool.sort()
        _slog('S4', '卖出', f'走弱期: 使用全球池{len(g.merged_etf_pool)}只')
    else:
        _slog('S4', '卖出', f'{g.market_regime}: 合并池{len(g.merged_etf_pool)}只')
    boyishouyi_refresh_holdings_num_by_regime(context)
    _slog('S4', '动量', f'计算开始, 合并池{len(getattr(g, "merged_etf_pool", []))}只')
    boyishouyi_calculate_and_log_ranked_etfs(context)
    _slog('S4', '卖出', '执行操作')
    boyishouyi_execute_sell_trades(context)
    _slog('S4', '卖出', '流水线完毕')


def boyishouyi_afternoon_buy(context):
    _slog('S4', '买入', '流水线启动')
    _slog('S4', '买入', '执行操作')
    boyishouyi_execute_buy_trades(context)
    _slog('S4', '买入', '流水线完毕')


def boyishouyi_reset_daily_flags(context):
    g.cache_date = None
    g.yesterday_close_cache = {}
    _slog('S4', '收盘', '缓存重置完成')


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

    _slog('S4', 'MA观测', '全样本汇总: 14:50跌破MA→次日收盘收益')
    log.info(_line('ma5', '跌破 MA5'))
    log.info(_line('ma10', '跌破 MA10'))
    log.info(_line('either_5_10', '跌破 MA5 或 MA10（按事件计一次）'))
    log.info(_line('ma20', '跌破 MA20'))
    log.info(_line('ma30', '跌破 MA30'))
    log.info(_line('either', '跌破 MA20 或 MA30（按事件计一次）'))


def boyishouyi_holdings_ma_break_1450_check(context):
    """当日持仓在 14:50 若跌破 MA5/MA10/MA20/MA30 任一条，则登记次交易日收盘结算。"""
    if not getattr(g, 'enable_holdings_ma_break_nextday_stats', False):
        return
    signal_date = context.current_dt.date()
    prev_eod = context.previous_date
    if hasattr(prev_eod, 'date'):
        prev_eod = prev_eod.date()
    holdings = [s for s, p in _boyishouyi_sp(context).positions.items() if p.total_amount > 0]
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


def boyishouyi_after_close_regime_statistics(context):
    """收盘后统计：当日归属早盘判定的市场状态，累计天数与日收益（复利因子）。"""
    settle_ma_break_pending(context)
    boyishouyi_update_regime_performance_stats(context)
    boyishouyi_log_regime_performance_dashboard(context, full=False)
    boyishouyi_log_exit_reason_dashboard(context, top_n=8)


def boyishouyi_check_positions(context):
    current_data = get_current_data()
    for security in _boyishouyi_sp(context).positions:
        position = _boyishouyi_sp(context).positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f'[全局] 晨间 | ' + f'持仓: {security} {security_name}, {position.total_amount}股 成本{position.avg_cost:.3f} 现价{position.price:.3f}')
            if current_data[security].paused:
                _slog('S1', '检查', f'{security} {security_name} 今日停牌', 'warning')


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
    for sec in list(_boyishouyi_sp(context).positions.keys()):
        pos = _boyishouyi_sp(context).positions.get(sec)
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
                _slog('S4', '回撤', f'{sec} 停牌, 跳过减仓')
                continue
            lp = cd.last_price
            if lp <= 0:
                continue
            if lp >= cd.high_limit:
                _slog('S4', '回撤', f'{sec} 涨停, 跳过减仓')
                continue
            if lp <= cd.low_limit:
                _slog('S4', '回撤', f'{sec} 跌停, 跳过卖出')
                continue
        except Exception:
            continue
        # 卖出：用买一价确保快速成交
        _sell_price = None
        try:
            tick = get_current_tick(sec)
            if tick is not None and tick.get('b1_p', 0) > 0:
                _sell_price = round(tick['b1_p'], 3)
        except Exception:
            pass
        if _sell_price is None:
            _sell_price = round(lp * 0.99, 3)
        low_limit = getattr(cd, 'low_limit', None)
        if low_limit and _sell_price < low_limit:
            _sell_price = round(low_limit + 0.001, 3)
        order_result = order(sec, -sell_amt, style=LimitOrderStyle(_sell_price), pindex=3)
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
            return float(_boyishouyi_sp(context).total_value)
        except Exception:
            return 0.0
    cd = get_current_data()
    try:
        tv_legacy = float(_boyishouyi_sp(context).total_value)
    except Exception:
        tv_legacy = 0.0
    stock_legacy_sum = 0.0
    repriced = 0.0
    for sec, pos in _boyishouyi_sp(context).positions.items():
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


def boyishouyi_monitor_drawdown(context):
    if g.log_trade_detail:
        _slog('S4', '回撤', '监控开始')
    try:
        current_value = _portfolio_mtm_total_value(context)
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value <= 0:
            return
        current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
        if current_drawdown < g.drawdown_threshold:
            return

        record = {
            'date': context.current_dt.strftime('%Y-%m-%d'),
            'drawdown': current_drawdown,
            'portfolio_value': current_value,
            'max_value': g.max_portfolio_value,
            'market_regime': getattr(g, 'market_regime', ''),
        }
        positions_info = []
        for security in _boyishouyi_sp(context).positions:
            position = _boyishouyi_sp(context).positions[security]
            if position.total_amount > 0:
                security_name = get_security_name(security)
                positions_info.append(f"{security_name}:{position.total_amount}股")
        record['positions'] = positions_info
        g.drawdown_records.append(record)
        if len(g.drawdown_records) > 200:
            g.drawdown_records = g.drawdown_records[-200:]
        _slog('S4', '回撤', f'预警: 回撤{current_drawdown:.2%} (阈值{g.drawdown_threshold:.0%})', 'warning')
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
            _slog('S4', '回撤', f'全部清仓! 回撤{current_drawdown:.2%} >= {th_flat:.0%}', 'error')
            ok_any = False
            for sec in list(_boyishouyi_sp(context).positions.keys()):
                pos = _boyishouyi_sp(context).positions.get(sec)
                if pos and pos.total_amount > 0:
                    if boyishouyi_smart_order(sec, 0, context, exit_reason=f"{exit_tag}全部清仓", pindex=3):
                        ok_any = True
            acted = ok_any
        elif current_drawdown >= th_def:
            if boyishouyi_check_defensive_etf_available(context):
                _slog('S4', '回撤', f'切防御清仓! 回撤{current_drawdown:.2%}>={th_def:.0%}', 'error')
                def_etf = getattr(g, 'defensive_etf', None)
                ok_any = False
                for sec in list(_boyishouyi_sp(context).positions.keys()):
                    if sec == def_etf:
                        continue
                    pos = _boyishouyi_sp(context).positions.get(sec)
                    if pos and pos.total_amount > 0:
                        if boyishouyi_smart_order(sec, 0, context, exit_reason=f"{exit_tag}切防御清仓", pindex=3):
                            ok_any = True
                acted = ok_any
            else:
                log.warning(
                    f"🛡️ 【组合回撤·切防御】{current_drawdown:.2%} ≥ {th_def:.0%}，但防御ETF不可用，未执行清仓"
                )
        elif current_drawdown >= th_half:
            keep_frac = float(getattr(g, 'dd_partial_close_keep_fraction', 0.5))
            _slog('S4', '回撤', f'减仓: 回撤{current_drawdown:.2%}>={th_half:.0%}, 保留{keep_frac:.0%}', 'warning')
            if _drawdown_sell_closeable_keep_fraction(context, keep_frac, f"{exit_tag}减仓"):
                acted = True

        if acted:
            g.dd_action_cooldown_date = today
            if getattr(g, 'dd_reset_peak_after_action', True):
                nv = _portfolio_mtm_total_value(context)
                g.max_portfolio_value = max(nv, 1.0)
                _slog('S4', '回撤', f'减仓已执行, 峰值重置为{g.max_portfolio_value:,.0f}')
    except Exception as e:
        log.error(f'[全局] 回撤 | ' + f'计算异常: {e}')


def boyishouyi_calculate_global_etf_threshold(context):
    if getattr(g, 'log_pool_update_details', False):
        _slog('S4', '流动性', '计算全市场ETF门槛')
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


def boyishouyi_filter_global_pool_by_volume(context):
    _slog('S4', '全球池', '开始执行')
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        _slog('S4', '全球池', '阈值未初始化')
        boyishouyi_calculate_global_etf_threshold(context)
    if not g.global_etf_pool:
        _slog('S4', '全球池', '全球池为空, 跳过')
        g.filtered_global_pool = []
        return
    dynamic_threshold = g.avg_etf_money_threshold
    _slog('S4', '全球池', f'门槛=日均{dynamic_threshold/1e4:.0f}万元')
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.global_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            _slog('S4', '全球池', '无法获取成交额, 使用原始池', 'warning')
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
            _slog('S4', '全球池', f'剔除低流动性: {len(removed)}只')
        g.filtered_global_pool = new_global_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        _slog('S4', '全球池', f'保留: {len(new_global_pool)}只')
    except Exception as e:
        _slog('S4', '全球池', f'异常: {e}', 'warning')
        g.filtered_global_pool = g.global_etf_pool[:]


def boyishouyi_update_sector_pool(context):
    if getattr(g, 'log_pool_update_details', False):
        _slog('S4', '动态池', '开始执行')
    if g.avg_etf_money_threshold is None:
        if getattr(g, 'log_pool_update_details', False):
            _slog('S4', '动态池', '阈值未初始化, 立即计算')
        boyishouyi_calculate_global_etf_threshold(context)
    
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
        _slog('S4', '动态池', f'全市场ETF: {len(etf_list)}只')
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
        _slog('S4', '动态池', f'特别组: {group_counts}')
        _slog('S4', '动态池', f'特别组: {len(special_etfs)}只')
        _slog('S4', '动态池', f'普通组: {len(normal_etfs)}只')
        _slog('S4', '动态池', f'排除: {excluded_count}只')
    
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
    if getattr(g, 'log_pool_update_details', False):
        _slog('S4', '动态池', f'特别组过滤: {len(special_etfs)}→{len(special_sorted)}只')
        _slog('S4', '动态池', f'普通组过滤: {len(normal_etfs)}→{len(normal_sorted)}只')
    
    if not normal_sorted and not special_sorted:
        _slog('S4', '动态池', '无ETF通过流动性过滤', 'warning')
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
        _slog('S4', '动态池', f'完成: 动态池{len(g.dynamic_etf_pool)}只')
    if getattr(g, 'log_pool_update_details', False) and len(g.dynamic_etf_pool) <= 10:
        for item in top_100[:10]:
            log.info(f"  {item['code']} {item['original_name']} 日均成交额: {item['money']/1e8:.2f}亿")


def boyishouyi_filter_fixed_pool_by_volume(context):
    if getattr(g, 'log_pool_update_details', False):
        _slog('S4', '固定池', '开始执行')
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        if getattr(g, 'log_pool_update_details', False):
            _slog('S4', '固定池', '阈值未初始化, 立即计算')
        boyishouyi_calculate_global_etf_threshold(context)
    if not g.fixed_etf_pool:
        if getattr(g, 'log_pool_update_details', False):
            _slog('S4', '固定池', '固定池为空, 跳过')
        return
    dynamic_threshold = g.avg_etf_money_threshold
    if getattr(g, 'log_pool_update_details', False):
        _slog('S4', '固定池', f'门槛=日均{dynamic_threshold/1e4:.0f}万元')
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.fixed_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            _slog('S4', '固定池', '无法获取成交额, 跳过', 'warning')
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
                _slog('S4', '固定池', f'剔除低流动性: {len(removed)}只')
        g.filtered_fixed_pool = new_fixed_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        if getattr(g, 'log_pool_update_details', False):
            _slog('S4', '固定池', f'保留: {len(new_fixed_pool)}只')
    except Exception as e:
        _slog('S4', '固定池', f'异常: {e}', 'warning')
        g.filtered_fixed_pool = g.fixed_etf_pool[:]


def boyishouyi_daily_merge_etf_pools(context):
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    if getattr(g, 'log_pool_update_details', False):
        _slog('S4', '合并池', '开始执行')
        _slog('S4', '合并池', f'固定{len(g.filtered_fixed_pool)}只+动态{len(g.dynamic_etf_pool)}只=合并{len(merged)}只')
    g.merged_etf_pool = merged


def boyishouyi_calculate_and_log_ranked_etfs(context):
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        _slog('S4', '动量', '合并池为空, 跳过计算', 'warning')
        g.ranked_etfs_result = []
        g.last_metrics_by_etf_code = {}
        return
    final_list = boyishouyi_get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list


def boyishouyi_calculate_momentum_score(price_series, lookback_days):
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
        getattr(g, 'enable_p0_state_tuning_patch', False)
        and getattr(g, 'market_regime', '震荡期') == '正常期'
    ):
        return float(getattr(g, 'normal_laplace_min_slope_override', base))
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
        lm, lar, lr2 = boyishouyi_calculate_momentum_score(price_for, g.lookback_days)
        sm, sar, sr2 = boyishouyi_calculate_momentum_score(price_for, short_lb)
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
        # 需要保证可构造「前交易日、昨交易日、今交易日(当前价)」三组短期动量输入（日 K 仅含交易日）
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
            sm, _, _ = boyishouyi_calculate_momentum_score(sub, short_lb)
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
            sm, _, _ = boyishouyi_calculate_momentum_score(sub, short_lb)
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
            lm, _, _ = boyishouyi_calculate_momentum_score(sub, long_lb)
            sm, _, _ = boyishouyi_calculate_momentum_score(sub, short_lb)
            long_vals.append(float(np.asarray(lm).ravel()[0]) if _scalar_momentum_finite(lm) else None)
            short_vals.append(float(np.asarray(sm).ravel()[0]) if _scalar_momentum_finite(sm) else None)
        # 至少保证各自有两个可用点，便于观察趋势
        if sum(v is not None for v in long_vals) < 2 and sum(v is not None for v in short_vals) < 2:
            return None
        return {'long': long_vals, 'short': short_vals}
    except Exception:
        return None


def boyishouyi_log_pending_short_momentum_3up_followups(context):
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


def boyishouyi_record_buy_trade_entry(context, etf_code):
    """买入成功后记录开仓快照，供卖出复盘配对。"""
    try:
        cd = get_current_data()
        px = _coerce_scalar_price(cd[etf_code].last_price) if etf_code in cd else None
        pos = _boyishouyi_sp(context).positions.get(etf_code)
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
        _slog('S4', '交易', f'买入快照异常 {etf_code}: {e}', 'warning')


def boyishouyi_record_etf_roundtrip_on_sell(context, security, sold_amount, avg_cost_before, sell_price, exit_reason):
    """清仓后：复盘日志 + 写入 trade_roundtrip_history。"""
    name = get_security_name(security)
    entry = getattr(g, 'trade_entry_open', {}).pop(security, None) or {}
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
        g.trade_roundtrip_history = []  # [MEM] trimmed to 500
    g.trade_roundtrip_history.append(rec)
    if len(g.trade_roundtrip_history) > 500:
        g.trade_roundtrip_history = g.trade_roundtrip_history[-500:]

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


def boyishouyi_log_trade_roundtrip_leaderboard(context, top_n=20):
    """单次买卖往返盈亏榜：盈利前N / 亏损前N（按估算 pnl_abs）。"""
    hist = getattr(g, 'trade_roundtrip_history', []) or []
    if not hist:
        _slog('S4', '往返', '尚无完成清仓记录')
        return
    valid = [h for h in hist if h.get('pnl_abs') is not None and np.isfinite(h.get('pnl_abs', float('nan')))]
    if not valid:
        _slog('S4', '往返', '无有效盈亏样本')
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


def boyishouyi_calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
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
        momentum_score, annualized_returns, r_squared = boyishouyi_calculate_momentum_score(price_for_momentum, g.lookback_days)
        if momentum_score is None:
            return None
        short_momentum_score, _, _ = boyishouyi_calculate_momentum_score(price_for_momentum, short_lb)
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

        volume_ratio = boyishouyi_get_volume_ratio(hist_volumes, today_vol, context, g.volume_lookback)
        effective_volume_threshold = float(getattr(g, 'volume_threshold', 0))
        if getattr(g, 'enable_volume_threshold_buffer', False):
            effective_volume_threshold += max(0.0, float(getattr(g, 'volume_threshold_buffer', 0.0)))
        passed_volume = (volume_ratio is not None and volume_ratio < effective_volume_threshold)
        
        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False
        
        passed_ma = True
        ma_value = None
        if len(price_series) >= g.ma_lookback:
            ma_value = np.mean(price_series[-g.ma_lookback:])
            passed_ma = current_price > ma_value * g.ma_threshold
        else:
            passed_ma = False
        
        premium_rate, passed_premium = boyishouyi_calculate_premium_rate(etf, context)
        
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


def boyishouyi_get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
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


def boyishouyi_calculate_premium_rate(etf, context):
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


def boyishouyi_resolve_market_regime(context):
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
                log.warn(f'[全局] 市场 | ' + f'{name}({code})数据不足, 跳过')
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
            log.warn(f'[全局] 市场 | ' + f'六指数未齐({n_ok}/{n_index}), 默认震荡期')
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
        g.is_a_share_weak = raw_regime == '走弱期'
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
        log.info(f'[全局] 市场 | ' + f'首日/首次: 生效{g.market_regime}')
    elif raw_regime == effective_before:
        g.market_regime = raw_regime
        g.is_a_share_weak = raw_regime == '走弱期'
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
    elif n_need <= 1:
        g.market_regime = raw_regime
        g.regime_last_change_date = today
        g.is_a_share_weak = raw_regime == '走弱期'
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
        log.info(f'[全局] 市场 | ' + f'立即切换: {effective_before}→{raw_regime}')
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
            g.is_a_share_weak = raw_regime == '走弱期'
            g.regime_switch_pending_raw = None
            g.regime_switch_pending_streak = 0
            log.info(
                f"✅ 【状态切换·已确认】指标连续{streak}个交易日为【{raw_regime}】，"
                f"生效切换 【{effective_before}】→【{raw_regime}】"
            )
        else:
            g.market_regime = effective_before
            g.is_a_share_weak = effective_before == '走弱期'
            log.info(
                f"⏳ 【状态切换·待确认】指标【{raw_regime}】，生效仍为【{effective_before}】"
                f"（进度 {streak}/{n_need} 个交易日）"
            )

    log.info(f'[全局] 市场 | ' + f'生效: {g.market_regime}')
    record(
        正常期标记=1 if g.market_regime == '正常期' else 0,
        震荡期标记=1 if g.market_regime == '震荡期' else 0,
        走弱期标记=1 if g.market_regime == '走弱期' else 0,
    )
    boyishouyi_log_regime_transition_chain(context)
    return g.market_regime


def boyishouyi_log_regime_transition_chain(context):
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
            log.info(f'[全局] 市场 | ' + f'切换: {day_str}: {prev}→{new}')
        else:
            log.info(f'[全局] 市场 | ' + f'延续: {day_str} 连续{new}')
    else:
        log.info(f'[全局] 市场 | ' + f'状态首日: {day_str} {new}')

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


def boyishouyi_update_regime_performance_stats(context):
    """收盘统计：本交易日归属早盘判定的市场状态，累计天数与净值复利因子。"""
    _ensure_regime_stats_structures()
    reg = getattr(g, 'market_regime', '震荡期')
    if reg not in g.regime_day_counts:
        reg = '震荡期'
    g.regime_day_counts[reg] = int(g.regime_day_counts.get(reg, 0)) + 1
    v = _boyishouyi_sp(context).total_value
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


def boyishouyi_log_regime_performance_dashboard(context, full=False):
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
    lines.append(f"总交易日(状态归因): {total_days}  |  当前净值: {_boyishouyi_sp(context).total_value:,.2f}")
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
        log.info(f'[全局] 看板 | ' + " | ".join(parts) + f" || 隔日跳回{flip_n}次")


def boyishouyi_apply_filters(metrics_list):
    if g.log_filter_detail:
        log.info('[S4] 过滤流水线开始执行')
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
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered


def boyishouyi_explain_filter_failures_for_etf(etf_code, metrics=None):
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


def boyishouyi_log_exit_reason_dashboard(context, top_n=8):
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
        _slog('S4', '卖出', '原因·分状态: ' + " | ".join(regime_parts))
    by_detail = s.get('by_detail', {})
    if isinstance(by_detail, dict) and by_detail:
        top = sorted(by_detail.items(), key=lambda kv: kv[1], reverse=True)[:max(1, int(top_n))]
        top_parts = [f"{k}:{v}" for k, v in top]
        _slog('S4', '卖出', '原因·Top: ' + "; ".join(top_parts))


def _rank_in_filtered_list(filtered_list, etf_code):
    """在 filtered_list 中 1-based 名次，不在则 None。"""
    for i, m in enumerate(filtered_list):
        if m.get('etf') == etf_code:
            return i + 1
    return None


def boyishouyi_get_final_ranked_etfs(context):
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = context.previous_date
    _slog('S4', '动量', f'合并池{len(etf_set)}只ETF')
    regime = getattr(g, 'market_regime', '震荡期')
    regime_show = {'正常期': '🟢 正常期', '震荡期': '🟡 震荡期', '走弱期': '🔴 走弱期'}.get(regime, regime)
    _slog('S4', '动量', f'当前状态: {regime_show}')
    short_lb = int(getattr(g, 'short_momentum_lookback', 21))
    lookback = max(g.lookback_days, short_lb, g.volume_lookback, g.ma_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
    safe_lookback = lookback + 20
    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        _slog('S4', '动量', '无法获取历史价格', 'warning')
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
        _slog('S4', '动量', f'溢价率数据异常: {e}', 'warning')
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
        metrics = boyishouyi_calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
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
    # 先整体记录一遍「原始合并池」在各过滤条件下的通过情况，便于后续追溯某只ETF为何不在候选池
    log_buffer.append(">>> 第二步前检查：合并池中各ETF在过滤条件下的通过情况（一览） <<<")
    tmp_all = boyishouyi_apply_filters(all_metrics, return_all=True) if 'return_all' in boyishouyi_apply_filters.__code__.co_varnames else boyishouyi_apply_filters(all_metrics)
    # 如果 apply_filters 支持 return_all=True，则 tmp_all 中会包含所有ETF及各 passed_xx 标记；
    # 否则退化为 filtered_list，仅能看到“已通过”的部分。
    debug_metrics = tmp_all if isinstance(tmp_all, list) else all_metrics
    for m in debug_metrics:
        try:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m.get('momentum_score', float('-inf')):.4f}" if m.get('momentum_score', float('-inf')) != float('-inf') else "nan"
            r2_v = m.get('r_squared')
            r2_str = f"{r2_v:.3f}" if r2_v is not None and not pd.isna(r2_v) else "nan"
            vol_val = f"{m.get('volume_ratio', 0):.2f}" if m.get('volume_ratio') is not None else "N/A"
            day_ratios = m.get('day_ratios') or []
            min_ratio = min(day_ratios) if day_ratios else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_v = m.get('premium_rate')
            premium_str = f"{premium_v:.2f}%" if premium_v is not None else "N/A"
            ma_val = m.get('ma_value')
            ma_str = f"MA{g.ma_lookback}: {ma_val:.2f}" if ma_val is not None else "MA:N/A"
            regime = getattr(g, 'market_regime', '震荡期')
            if regime == '震荡期':
                filt_extra = f"高斯斜率: {m.get('gaussian_slope', 0):.4f} {fmt_status('', m.get('passed_gaussian', False))}"
                if getattr(g, 'log_whipsaw_filter_detail', True):
                    sms = m.get('short_momentum_score')
                    sms_s = f"{sms:.4f}" if sms is not None and not (isinstance(sms, float) and np.isnan(sms)) else "nan"
                    dp_ok = (not m.get('dual_positive_filter_active')) or m.get('passed_dual_positive', False)
                    filt_extra += f" | Whipsaw短动量:{sms_s} 双正{'✅' if dp_ok else '❌'}"
            elif regime == '正常期':
                filt_extra = f"拉普拉斯斜率: {m.get('laplace_slope', 0):.4f} {fmt_status('', m.get('passed_laplace', False))}"
            elif regime == '走弱期':
                if getattr(g, 'weak_apply_laplace_filter', False):
                    filt_extra = f"拉普拉斯斜率: {m.get('laplace_slope', 0):.4f} {fmt_status('', m.get('passed_laplace', False))}"
                else:
                    filt_extra = "走弱期: 拉普拉斯未参与筛选"
            else:
                filt_extra = ""
            line = (
                f"{m.get('etf')} {m.get('etf_name')}: "
                f"动量得分: {fmt_status(score_str, m.get('passed_momentum', True))}，"
                f"R²: {fmt_status(r2_str, m.get('passed_r2', True))}，"
                f"均线: {fmt_status(ma_str, m.get('passed_ma', True))}，"
                f"成交量比值: {fmt_status(vol_val, m.get('passed_volume', True))}，"
                f"短期风控: {fmt_status(loss_val, m.get('passed_loss', True))}，"
                f"溢价率: {fmt_status(premium_str, m.get('passed_premium', True))}，"
                f"{filt_extra}"
            )
            log_buffer.append(line)
        except Exception:
            continue

    # 真正用于后续排序/候选池的列表仍然是 filtered_list
    filtered_list = tmp_all if isinstance(tmp_all, list) and all('passed_momentum' in d for d in tmp_all) else boyishouyi_apply_filters(all_metrics)
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
    current_holdings = [sec for sec, pos in _boyishouyi_sp(context).positions.items() if pos.total_amount > 0]
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
        new_first = candidate_pool[0]
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

            for h in current_holdings:
                if h not in pool_codes:
                    must_replace.append((h, "掉出候选池"))
                    streaks.pop(h, None)
                    continue
                r = rank_map.get(h)
                if r is None:
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
                final_result = [new_first]
                g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = new_first['etf']
                t = f"{AC}立即换股({reason})：{H} → 候选池第1 {new_first['etf']} {new_first['etf_name']}"
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
                    final_result = [new_first]
                    g.normal_not_rank1_streak = 0
                    g.normal_streak_hold_code = new_first['etf']
                    t = (
                        f"{AC}⭐已满{max_days}个交易日未重返第1名 → 换股为候选池第1 "
                        f"{new_first['etf']} {new_first['etf_name']}"
                    )
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
    if getattr(g, 'enable_switch_hysteresis', False) and g.holdings_num == 1 and final_result:
        hs_holdings = [sec for sec, pos in _boyishouyi_sp(context).positions.items() if pos.total_amount > 0]
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


def boyishouyi_execute_sell_trades(context):
    if g.log_trade_detail:
        _slog('S4', '卖出', '决策链开始')
    _slog('S4', '卖出', '操作开始')
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    current_positions = list(_boyishouyi_sp(context).positions.keys())
    current_holdings_nonzero = [s for s in current_positions if _boyishouyi_sp(context).positions[s].total_amount > 0]
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
        if boyishouyi_check_defensive_etf_available(context):
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
                    _slog('S4', '卖出', f'防御模式: 目标{g.defensive_etf} {etf_name}')
                else:
                    target_etfs = current_holdings_nonzero[:]
                    log.info(
                        f"🕒 防御切换确认中：{g.defensive_switch_pending_streak}/{need_days}，"
                        f"暂不切换防御ETF，维持当前持仓"
                    )
            else:
                target_etfs = [g.defensive_etf]
                etf_name = get_security_name(g.defensive_etf)
                _slog('S4', '卖出', f'防御模式: 目标{g.defensive_etf} {etf_name}')
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
        position = _boyishouyi_sp(context).positions[security]
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
                        fail_detail = boyishouyi_explain_filter_failures_for_etf(security, met)
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

            success = boyishouyi_smart_order(security, 0, context, exit_reason=exit_reason, pindex=3)
            if success:
                sell_count += 1
                _record_exit_reason_stat(exit_bucket, exit_detail, getattr(g, 'market_regime', '未知'))
                log.info(f"✅ 已成功卖出: {security} {security_name}")
    
    log.info(f"本次共计划卖出{sell_count}只ETF。")
    _slog('S4', '卖出', '操作完成')


def boyishouyi_execute_buy_trades(context):
    if g.log_trade_detail:
        _slog('S4', '买入', '决策链开始')
    _slog('S4', '买入', '操作开始')
    target_etfs = g.target_etfs_list
    
    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        _slog('S4', '买入', '操作完成')
        return
    
    current_positions = set(_boyishouyi_sp(context).positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    etfs_to_buy = _filter_stop_loss_rebuy_cooldown(context, etfs_to_buy)
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    
    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        _slog('S4', '买入', '操作完成')
        return
    
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标持仓: {g.holdings_num}只, 本次计划买入: {num_etfs_to_buy}只")
    
    # 修复：动态分配资金，避免可用现金为负
    for i, etf in enumerate(etfs_to_buy):
        remaining_cash = _boyishouyi_sp(context).available_cash
        if remaining_cash < g.min_money:
            log.info(f"可用现金 {remaining_cash:.2f} 不足最小交易额 {g.min_money:.2f}，停止买入")
            break
        
        remaining_to_buy = len(etfs_to_buy) - i
        target_value_for_this_etf = remaining_cash // remaining_to_buy
        # [再平衡截流] S4买入截流
        if getattr(g, 'boyishouyi_rebalance_cap', None) is not None:
            _rb_cap = g.boyishouyi_rebalance_cap
            _existing_val = sum(
                _boyishouyi_sp(context).positions.get(e, type('',(),{'value':0})()).value
                for e in etfs_to_buy if e in _boyishouyi_sp(context).positions
            ) if etfs_to_buy else 0
            _max_buy = max(0, _rb_cap - _existing_val)
            _capped = int(_max_buy / max(1, len(etfs_to_buy))) if etfs_to_buy else 0
            if _capped < target_value_for_this_etf:
                _slog('S4', '再平衡', f'截流: 原{target_value_for_this_etf}→{_capped}元/只 (上限{_rb_cap})')
                target_value_for_this_etf = _capped
        # ===== S4截流结束 =====
        
        # 最后一笔可使用剩余全部现金，但确保不小于最小交易额
        if target_value_for_this_etf < g.min_money and remaining_cash >= g.min_money:
            target_value_for_this_etf = remaining_cash
        
        log.info(f"为 {etf} 分配目标金额: {target_value_for_this_etf:.2f} 元 (剩余现金 {remaining_cash:.2f}, 待买数量 {remaining_to_buy})")
        
        success = boyishouyi_smart_order(etf, target_value_for_this_etf, context, pindex=3)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
            boyishouyi_record_buy_trade_entry(context, etf)
        else:
            log.info(f"❌ ETF {etf} 下单失败")
    
    _slog('S4', '买入', '操作完成')

def boyishouyi_smart_order(security, target_value, context, exit_reason='午盘清仓', pindex=3):
    current_data = get_current_data()
    security_name = get_security_name(security)

    # ========== 1. 买入初步资金检查（仅对买入操作） ==========
    if target_value > 0:
        available_cash = _boyishouyi_sp(context).available_cash
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
        max_shares = int(_boyishouyi_sp(context).available_cash / current_price)
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
    current_position = _boyishouyi_sp(context).positions.get(security, None)
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
        if amount_diff < 0:
            # 卖出：用买一价确保快速成交，确保快速成交
            sell_price = None
            try:
                tick = get_current_tick(security)
                if tick is not None and tick.get('b1_p', 0) > 0:
                    sell_price = round(tick['b1_p'], 3)
            except Exception:
                pass
            if sell_price is None:
                sell_price = round(current_price * 0.99, 3)
            # 涨跌停保护
            cdata_now = get_current_data()
            low_limit = getattr(cdata_now.get(security), 'low_limit', None) if cdata_now.get(security) else None
            if low_limit and sell_price < low_limit:
                sell_price = round(low_limit + 0.001, 3)
            order_result = order(security, amount_diff, style=LimitOrderStyle(sell_price), pindex=3)
        else:
            order_result = order(security, amount_diff, pindex=3)
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
                pos_after = _boyishouyi_sp(context).positions.get(security)
                amt_after = pos_after.total_amount if pos_after else 0
                if amt_after <= 0:
                    boyishouyi_record_etf_roundtrip_on_sell(
                        context, security, float(abs(amount_diff)),
                        avg_cost_before, float(current_price), exit_reason
                    )
            return True
        else:
            log.warning(f"下单失败: {security} {security_name}，数量: {amount_diff}")
            return False
    return False


def _stop_loss_rebuy_cutoff_dt():
    s = getattr(g, 'stop_loss_rebuy_cutoff_time', '13:10')
    try:
        parts = str(s).strip().split(':')
        return datetime.time(int(parts[0]), int(parts[1]))
    except Exception:
        return datetime.time(13, 10)


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


def boyishouyi_minute_stop_loss(context):
    if not g.use_fixed_stop_loss:
        return
    
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    
    current_data = get_current_data()
    for security in list(_boyishouyi_sp(context).positions.keys()):
        position = _boyishouyi_sp(context).positions[security]
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
            _slog('S4', '止损', f'分钟固定止损! {security} {security_name} 亏损{loss_percent:.2f}%', 'error')
            ok = boyishouyi_smart_order(security, 0, context, exit_reason='分钟固定止损', pindex=3)
            if ok:
                _record_stop_loss_rebuy_cooldown(context, security)


def boyishouyi_minute_pct_stop_loss(context):
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
    
    for security in list(_boyishouyi_sp(context).positions.keys()):
        position = _boyishouyi_sp(context).positions[security]
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
            _slog('S4', '止损', f'分钟跌幅止损! {security} {security_name} 日跌{daily_loss:.2f}%', 'error')
            ok = boyishouyi_smart_order(security, 0, context, exit_reason='分钟跌幅止损', pindex=3)
            if ok:
                _record_stop_loss_rebuy_cooldown(context, security)


def boyishouyi_check_defensive_etf_available(context):
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
# ==================== 每日持仓成交金额（仅打印当日）====================
def boyishouyi_record_daily_positions(context):
    """每天15:30：仅打印当日持仓ETF的成交金额（不累积多日汇总）"""
    current_date = context.current_dt.strftime('%Y-%m-%d')
    holdings = [sec for sec, pos in _boyishouyi_sp(context).positions.items() if pos.total_amount > 0]
    if not holdings:
        _slog('S4', '成交', f'{current_date} 无持仓')
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
            _slog('S4', '成交', f'{current_date} {sec} {etf_name} 成交额{turnover_str}')
    except Exception as e:
        _slog('S4', '成交', f'查询失败: {e}', 'error')


def boyishouyi_output_positions_summary(context):
    """回测最后一天仅输出市场状态累计看板（不再打印多日持仓成交汇总表）"""
    end_date = context.run_params.end_date
    today = context.current_dt.date()
    if today != end_date:
        return
    boyishouyi_log_regime_performance_dashboard(context, full=True)
    log_ma_break_nextday_summary(context)
    boyishouyi_log_trade_roundtrip_leaderboard(context, top_n=20)

# ==================== 再平衡系统 ====================
def rebalance_calculate_targets(context):
    """计算各策略再平衡目标比例和目标资金
    
    公式：
      raw_ratio[i] = base[i] + alpha * (current[i] - base[i])
      clamped[i] = clamp(raw_ratio[i], base[i]*lower, base[i]*upper)
      target[i] = clamped[i] / sum(clamped)   # 归一化
    """
    cfg = g.rebalance_config
    base = cfg['base_ratios']
    alpha = cfg['alpha']
    lower = cfg['lower_factor']
    upper = cfg['upper_factor']
    
    total_value = sum(context.subportfolios[i].total_value for i in range(5))
    
    # 计算各策略当前市值占比
    current = []
    for i in range(5):
        current.append(context.subportfolios[i].total_value / total_value)
    
    # 混合 + 夹限 + 归一化
    raw = [base[i] + alpha * (current[i] - base[i]) for i in range(5)]
    clamped = [max(base[i] * lower, min(base[i] * upper, raw[i])) for i in range(5)]
    clamped_sum = sum(clamped)
    targets = [c / clamped_sum for c in clamped]
    
    return targets, total_value


def rebalance_evaluate(context):
    """再平衡第0步：每月1号09:25评估资金偏离，超阈值则设置截流上限"""
    cfg = g.rebalance_config
    base = cfg['base_ratios']
    trigger = cfg['deviation_trigger']
    
    targets, total_value = rebalance_calculate_targets(context)
    # S4新版用g.xxx全局变量，需构造兼容dict给再平衡系统
    _boyi_compat = {'name': getattr(g, 'boyishouyi_name', '博收益ETF轮动(新)'),
                    'rebalance_cap': getattr(g, 'boyishouyi_rebalance_cap', None)}
    strategies = [g.etf4_strategy, g.hongli_strategy, g.qdii_strategy,
                  _boyi_compat, g.small_strategy]
    log.info(f'[全局] 再平衡 | ' + '月度资金偏离检查')
    log.info(f"💰 组合总资产: {total_value/10000:.1f}万")
    
    # 检查是否需要触发再平衡
    max_deviation = 0
    need_rebalance = False
    
    for i in range(5):
        current = context.subportfolios[i].total_value
        current_ratio = current / total_value
        deviation = abs(current_ratio - base[i]) / base[i]  # 偏离基础比例的百分比
        target_value = targets[i] * total_value
        
        log.info(f"  {strategies[i]['name']}: "
                 f"当前{current/10000:.1f}万({current_ratio:.1%}) "
                 f"→ 目标{target_value/10000:.1f}万({targets[i]:.1%}) "
                 f"[基础{base[i]:.1%}, 偏离{deviation:+.0%}]")
        
        if deviation > max_deviation:
            max_deviation = deviation
    
    log.info(f"  最大偏离: {max_deviation:.0%}, 触发阈值: {trigger:.0%}")
    
    if max_deviation < trigger:
        log.info(f'[全局] 再平衡 | ' + '偏离未达阈值, 不需要')
        g.rebalance_pending = False
        # 清除可能残留的截流标志
        for s in strategies:
            s['rebalance_cap'] = None
        # 同步S4截流标志到g变量
        g.boyishouyi_rebalance_cap = None
        return
    
    # 触发再平衡
    need_rebalance = True
    g.rebalance_pending = True
    log.info("🔴 偏离超过阈值，启动再平衡！")
    
    # 设置超配策略的截流上限
    for i in range(5):
        current = context.subportfolios[i].total_value
        target_value = targets[i] * total_value
        
        if current > target_value * 1.02:  # 超配2%以上才截流
            strategies[i]['rebalance_cap'] = target_value
            log.info(f"  ✂️ {strategies[i]['name']} 设截流上限: {target_value/10000:.1f}万")
        else:
            strategies[i]['rebalance_cap'] = None
    
    # 同步S4截流标志到g变量
    g.boyishouyi_rebalance_cap = _boyi_compat['rebalance_cap']


def rebalance_transfer_cash(context):
    """再平衡第2步：每月3号14:50转移现金"""
    if not g.rebalance_pending:
        return
    
    cfg = g.rebalance_config
    min_transfer = cfg['min_transfer']
    targets, total_value = rebalance_calculate_targets(context)
    _boyi_compat = {'name': getattr(g, 'boyishouyi_name', '博收益ETF轮动(新)'),
                    'rebalance_cap': getattr(g, 'boyishouyi_rebalance_cap', None)}
    strategies = [g.etf4_strategy, g.hongli_strategy, g.qdii_strategy,
                  _boyi_compat, g.small_strategy]
    log.info(f'[全局] 再平衡 | ' + '执行资金转移')
    
    # 计算各策略需转出/转入的金额
    over_funded = []   # (pindex, over_amount, available_cash)
    under_funded = []  # (pindex, under_amount)
    
    for i in range(5):
        current = context.subportfolios[i].total_value
        target = targets[i] * total_value
        cash = context.subportfolios[i].available_cash
        
        if current > target + min_transfer:
            over_amount = current - target
            over_funded.append((i, over_amount, cash))
        elif current < target - min_transfer:
            under_amount = target - current
            under_funded.append((i, under_amount))
    
    if not over_funded or not under_funded:
        log.warn(f'[全局] 再平衡 | ' + '无可转移资金')
        # 检查是否已有策略成功完成再平衡
        all_balanced = True
        for i in range(5):
            current = context.subportfolios[i].total_value
            target = targets[i] * total_value
            if abs(current - target) / total_value > 0.05:  # 5%容差
                all_balanced = False
                break
        if all_balanced:
            g.rebalance_pending = False
            for s in strategies:
                s['rebalance_cap'] = None
            g.boyishouyi_rebalance_cap = None
            log.info(f'[全局] 再平衡 | ' + '所有策略接近目标, 完成')
        else:
            log.info("⏳ 超配策略尚无可用现金，截流标志保留至下月")
        return
    
    # 按欠配金额比例分配
    total_under = sum(u[1] for u in under_funded)
    
    any_transfer = False
    for from_idx, over_amount, available in over_funded:
        # 可转出金额 = min(超额金额, 可用现金)
        transferable = min(over_amount, available)
        if transferable < min_transfer:
            log.info(f"  ⏳ 策略{from_idx}({strategies[from_idx]['name']}) 无足够现金({available/10000:.1f}万), 截流标志保留")
            continue
        
        # 按欠配比例分配给各欠配策略
        for to_idx, under_amount in under_funded:
            share = transferable * (under_amount / total_under)
            if share < min_transfer:
                continue
            actual = min(share, under_amount)
            actual = min(actual, context.subportfolios[from_idx].available_cash)
            if actual >= min_transfer:
                try:
                    transfer_cash(from_idx, to_idx, actual)
                    log.info(f"  💸 转移 {actual/10000:.2f}万: "
                             f"{strategies[from_idx]['name']} → {strategies[to_idx]['name']}")
                    any_transfer = True
                except Exception as e:
                    log.error(f"  ❌ 转移失败: {e}")
    
    # 检查再平衡是否完成
    # 重新计算偏离
    all_balanced = True
    for i in range(5):
        current = context.subportfolios[i].total_value
        target = targets[i] * total_value
        if abs(current - target) / total_value > 0.05:  # 5%容差
            all_balanced = False
            break
    
    if all_balanced:
        g.rebalance_pending = False
        for s in strategies:
            s['rebalance_cap'] = None
        g.boyishouyi_rebalance_cap = None
        log.info(f'[全局] 再平衡 | ' + '截流标志已清除')
    else:
        # 保留仍超配策略的截流标志
        for i in range(5):
            current = context.subportfolios[i].total_value
            target = targets[i] * total_value
            if current <= target * 1.02:
                strategies[i]['rebalance_cap'] = None
                log.info(f"  ✅ {strategies[i]['name']} 已接近目标，清除截流")
        # 同步S4截流标志到g变量
        g.boyishouyi_rebalance_cap = _boyi_compat['rebalance_cap']
        log.info("⏳ 部分策略仍偏离目标，截流标志保留至下月")


# ==================== 策略5: 最新小市值（独立版逻辑移植） ====================

def small_before_trading(context):
    strategy = g.small_strategy
    pindex = strategy['pindex']
    strategy['days'] = strategy.get('days', 0) + 1
    small_update_yesterday_limit_up(context, strategy)

def small_update_yesterday_limit_up(context, strategy):
    pindex = strategy['pindex']
    strategy['yesterday_HL_list'] = []
    positions = context.subportfolios[pindex].positions
    if not positions:
        return
    df = get_price(list(positions.keys()), end_date=context.previous_date, frequency='daily',
                   fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
    if not df.empty:
        df = df[df['close'] == df['high_limit']]
        strategy['yesterday_HL_list'] = list(df.code)

def small_check_macd_divergence(context, strategy, market_index="399101.XSHE", end_days=0):
    """大盘顶背离检测"""
    if not strategy['dbl'] and "9:31" in str(context.current_dt.time()):
        return

    def detect_divergence():
        fast, slow, sign = 12, 26, 9
        rows = (fast + slow + sign) * 5
        grid = attribute_history(market_index, rows + 10, fields=["close"]).dropna()
        if end_days < 0:
            grid = grid.iloc[:end_days]
        if len(grid) < rows:
            return False
        try:
            grid["dif"], grid["dea"], grid["macd"] = small_macd(grid.close, fast, slow, sign)
            mask = (grid["macd"] < 0) & (grid["macd"].shift(1) >= 0)
            if mask.sum() < 2:
                return False
            key2, key1 = mask[mask].index[-2], mask[mask].index[-1]
            price_cond = grid.close[key2] < grid.close[key1]
            dif_cond = grid.dif[key2] > grid.dif[key1] > 0
            macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]
            if len(grid["dif"]) > 20:
                trend_cond = grid["dif"].iloc[-10:].mean() < grid["dif"].iloc[-20:-10].mean()
            else:
                trend_cond = False
            return price_cond and dif_cond and macd_cond and trend_cond
        except Exception as e:
            _slog('S5', 'MACD', f'{market_index} 检测错误: {e}', 'error')
            return False

    if detect_divergence():
        strategy['dbl'].append(1)
        _slog('S5', 'MACD', f'检测到{market_index}顶背离信号!', 'warning')
    else:
        strategy['dbl'].append(0)
    # 滚动窗口限制 限制dbl列表长度
    if len(strategy['dbl']) > 60:
        strategy['dbl'] = strategy['dbl'][-60:]


# ====================== 选股逻辑（独立版V3） ======================'"

def small_choice_small(context, strategy, nchoice):
    """选股：独立版V3逻辑，使用399101.XSHE中证等权指数"""
    target_list = small_get_stocks_v3(context, strategy)
    strategy['stocks'] = target_list
    return target_list[:nchoice]

def small_get_stocks_v3(context, strategy):
    """独立版V3选股：基础过滤→财务筛选→排雷→红利→冷却"""
    initial_list = small_filter_stocks(context, strategy, get_index_stocks("399101.XSHE"))

    # PIT日期修正 date=context.previous_date 提供PIT保护，只取截至昨日已公告的数据
    # 注意：聚宽 get_fundamentals 的 date 和 statDate 参数互斥，不能同时使用
    # - 用date：PIT安全，但income/indicator字段可能来自不同报告期（可接受）
    # - 用statDate：强制同一报告期，但无PIT保护，可能引入未来函数（不可接受）
    # 因此保留date参数，接受字段跨报告期的不一致性（对筛选准确性影响极小）
    q = (
        query(
            valuation.code,
            valuation.market_cap,
            income.net_profit,
            income.operating_revenue,
        )
        .filter(
            valuation.code.in_(initial_list),
            valuation.market_cap.between(strategy['filter_market_cap_min'], strategy['filter_market_cap_max']),
            income.operating_revenue > 1e8,
            indicator.roe > 0,
            indicator.roa > 0,
            income.net_profit > 2000000,
        )
        .order_by(valuation.market_cap.asc())
        .limit(strategy['max_position_count'] * 5)
    )
    candidate_list = list(get_fundamentals(q, date=context.previous_date).code)

    current_date = context.current_dt.date()
    start_audit_date = datetime.date(2025, 1, 1)

    if current_date > start_audit_date:
        audited_list = small_apply_nine_point_audit(context, strategy, candidate_list)
    else:
        audited_list = small_filter_audit(context, strategy, candidate_list)

    final_list = small_bonus_filter(context, strategy, audited_list)
    final_list = small_filter_cooldown_stocks(context, strategy, final_list)

    if not final_list:
        return [strategy['defensive_etf']]

    last_prices = history(1, unit="1d", field="close", security_list=final_list)
    positions = context.subportfolios[strategy['pindex']].positions
    return [s for s in final_list if s in positions or last_prices[s][-1] <= strategy['max_stock_price']][: strategy['max_position_count']]

def small_filter_stocks(context, strategy, stock_list):
    """基础过滤：停牌/ST/退市/市场类型/涨跌停/次新股"""
    current_data = get_current_data()
    last_prices = history(1, unit="1m", field="close", security_list=stock_list)
    positions = context.subportfolios[strategy['pindex']].positions
    filtered_stocks = []
    for stock in stock_list:
        if current_data[stock].paused:
            continue
        if current_data[stock].is_st:
            continue
        if "退" in current_data[stock].name:
            continue
        # 排除科创板(688/689)、北交所(8)、老三板(4)；创业板(30)不过滤
        code = stock.split('.')[0]
        if code.startswith(('688', '689')) or code.startswith('8') or code.startswith('4'):
            continue
        if not (
            stock in positions
            or last_prices[stock][-1] < current_data[stock].high_limit
        ):
            continue
        if not (
            stock in positions
            or last_prices[stock][-1] > current_data[stock].low_limit
        ):
            continue
        start_date = get_security_info(stock).start_date
        if hasattr(start_date, 'date'):
            start_date = start_date.date()
        if context.previous_date - start_date < datetime.timedelta(days=strategy['min_listed_days']):
            continue
        filtered_stocks.append(stock)
    return filtered_stocks


# ====================== 九项年报排雷系统（独立版） ======================'"

def small_apply_nine_point_audit(context, strategy, stock_list):
    """九项排雷检查（完整版）"""
    if g.log_filter_detail:
        _slog('S5', '排雷', '九项审计开始')
    if not stock_list:
        return []

    yesterday = context.previous_date
    curr_year = yesterday.year
    curr_month = yesterday.month

    if curr_month <= 4:
        report_year = curr_year - 2
    else:
        report_year = curr_year - 1
    report_date_str = f"{report_year}-12-31"

    q = query(
        valuation.code, indicator.adjusted_profit, income.net_profit,
        cash_flow.subtotal_operate_cash_inflow, cash_flow.subtotal_operate_cash_outflow,
        balance.good_will, balance.equities_parent_company_owners,
        balance.total_liability, balance.total_assets,
        balance.shortterm_loan, balance.cash_equivalents
    ).filter(valuation.code.in_(stock_list))

    fund_df = get_fundamentals(q, date=yesterday)
    if not fund_df.empty:
        fund_df = fund_df.set_index('code')
        fund_df.fillna(0, inplace=True)
    else:
        return stock_list

    final_list = []
    max_tolerance = strategy.get('audit_tolerance', 2)

    for stock in stock_list:
        score = 0
        hit_reasons = []

        try:
            stock_name = get_security_info(stock).display_name if get_security_info(stock) else ""

            # 1. 披露时间检查
            if hasattr(finance, 'STK_INCOME_STATEMENT'):
                q_time = query(finance.STK_INCOME_STATEMENT.pub_date).filter(
                    finance.STK_INCOME_STATEMENT.code == stock,
                    finance.STK_INCOME_STATEMENT.end_date == report_date_str,
                    finance.STK_INCOME_STATEMENT.pub_date <= yesterday
                ).limit(1)
                time_df = finance.run_query(q_time)
                if not time_df.empty:
                    actual_date = time_df['pub_date'].iloc[0]
                    if isinstance(actual_date, str):
                        actual_date = datetime.datetime.strptime(actual_date, '%Y-%m-%d').date()
                    elif isinstance(actual_date, datetime.datetime) or hasattr(actual_date, 'date'):
                        actual_date = actual_date.date()
                    if actual_date and actual_date > datetime.date(report_year + 1, 4, 20):
                        score += 1
                        hit_reasons.append("年报迟发(>4.20)")

            # 2. 业绩预告检查
            if hasattr(finance, 'STK_FIN_FORCAST'):
                q_forcast = query(finance.STK_FIN_FORCAST).filter(
                    finance.STK_FIN_FORCAST.code == stock,
                    finance.STK_FIN_FORCAST.end_date == report_date_str,
                    finance.STK_FIN_FORCAST.pub_date <= yesterday
                ).limit(1)
                forcast_df = finance.run_query(q_forcast)
                if not forcast_df.empty:
                    type_id = forcast_df['type_id'].iloc[0]
                    if type_id in [3, 4, 5, 9, 10]:
                        score += 1
                        hit_reasons.append("业绩预告不良")

            # 3. 审计意见检查（一票否决）
            if hasattr(finance, 'STK_AUDIT_OPINION'):
                q_audit = query(finance.STK_AUDIT_OPINION).filter(
                    finance.STK_AUDIT_OPINION.code == stock,
                    finance.STK_AUDIT_OPINION.end_date == report_date_str,
                    finance.STK_AUDIT_OPINION.pub_date <= yesterday
                ).limit(1)
                audit_df = finance.run_query(q_audit)
                if not audit_df.empty:
                    opinion_id = audit_df['opinion_type_id'].iloc[0]
                    if opinion_id in [3, 4, 5]:
                        _slog('S5', '排雷', f'{stock}({stock_name}) 审计异常, 一票否决', 'warning')
                        continue

            # 4-7. 财务硬指标
            if stock in fund_df.index:
                row = fund_df.loc[stock]
                adj_p = row['adjusted_profit']
                net_p = row['net_profit']
                cash_net = row['subtotal_operate_cash_inflow'] - row['subtotal_operate_cash_outflow']

                if adj_p < 0 or (net_p != 0 and adj_p / net_p < 0.5):
                    score += 1
                    hit_reasons.append("主业存疑")
                if net_p > 0 and cash_net < 0:
                    score += 1
                    hit_reasons.append("现金流异常")
                equity = row['equities_parent_company_owners']
                gw = row['good_will']
                if equity > 0 and (gw / equity) > 0.3:
                    score += 1
                    hit_reasons.append("商誉占比高(>30%)")
                t_liab = row['total_liability']
                t_assets = row['total_assets']
                st_loan = row['shortterm_loan']
                cash_val = row['cash_equivalents']
                debt_ratio = (t_liab / t_assets) if t_assets > 0 else 0
                if debt_ratio > 0.70 or st_loan > cash_val:
                    score += 1
                    hit_reasons.append(f"资金链紧绷(负债率{(debt_ratio*100):.0f}%)")

            # 8. 大股东质押率
            if hasattr(finance, 'STK_SHARES_PLEDGE'):
                q_pledge = query(finance.STK_SHARES_PLEDGE).filter(
                    finance.STK_SHARES_PLEDGE.code == stock,
                    finance.STK_SHARES_PLEDGE.pub_date <= yesterday
                ).order_by(finance.STK_SHARES_PLEDGE.pub_date.desc()).limit(1)
                pledge_df = finance.run_query(q_pledge)
                if not pledge_df.empty:
                    ratio_col = 'pledge_proportion' if 'pledge_proportion' in pledge_df.columns else ('pledge_ratio' if 'pledge_ratio' in pledge_df.columns else None)
                    if ratio_col is not None:
                        val = pledge_df[ratio_col].iloc[0]
                        if pd.notna(val) and val > 80:
                            score += 1
                            hit_reasons.append("大股东高质押(>80%)")

            # 9. 监管立案调查
            if hasattr(finance, 'STK_INVESTIGATION'):
                q_inv = query(finance.STK_INVESTIGATION).filter(
                    finance.STK_INVESTIGATION.code == stock,
                    finance.STK_INVESTIGATION.pub_date >= f"{curr_year-1}-01-01",
                    finance.STK_INVESTIGATION.pub_date <= yesterday
                ).limit(1)
                inv_df = finance.run_query(q_inv)
                if not inv_df.empty:
                    score += 1
                    hit_reasons.append("曾遭监管立案调查")

            if score > 0:
                log.info(f"[排雷透视] {stock}({stock_name}) 累计踩中 {score} 项: {' | '.join(hit_reasons)}")

            if score < max_tolerance:
                final_list.append(stock)
            else:
                _slog('S5', '排雷', f'{stock}({stock_name}) 踩雷{score}项>容忍度{max_tolerance}, 拦截', 'warning')

        except Exception as e:
            _slog('S5', '排雷', f'{stock} 异常: {e}', 'error')
            final_list.append(stock)

    return final_list


# ====================== ATR止损 ======================'"

def small_calculate_atr(security, context, period=14):
    df = get_price(security, end_date=context.previous_date, count=period + 1,
                   frequency="daily", fields=["high", "low", "close"])
    if len(df) < period + 1:
        return None
    df["pre_close"] = df["close"].shift(1)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["pre_close"])
    df["tr3"] = abs(df["low"] - df["pre_close"])
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
    return df["tr"].iloc[-period:].mean()

def small_update_atr_stop_prices(context, strategy):
    if g.log_trade_detail:
        _slog('S5', 'ATR止损', f'价格更新开始, {len(strategy.get("atr_stop_prices", {}))}只跟踪中')
    if not strategy['enable_atr_stop_loss']:
        return
    pindex = strategy['pindex']
    positions = context.subportfolios[pindex].positions
    for stock in positions.keys():
        atr = small_calculate_atr(stock, context, strategy['atr_period'])
        if atr:
            if stock not in strategy['atr_stop_prices']:
                strategy['atr_stop_prices'][stock] = positions[stock].avg_cost - (strategy['atr_multiplier'] * atr)
            else:
                trailing_stop = positions[stock].price - (strategy['atr_multiplier'] * atr)
                if trailing_stop > strategy['atr_stop_prices'][stock]:
                    strategy['atr_stop_prices'][stock] = trailing_stop

def small_check_atr_stop_loss(context, strategy):
    if not strategy['enable_atr_stop_loss']:
        return
    pindex = strategy['pindex']
    positions = context.subportfolios[pindex].positions
    if g.log_trade_detail:
        _slog('S5', 'ATR止损', f'触发检查开始, {len(positions)}只持仓')
    for stock in list(positions.keys()):
        if stock in strategy['atr_stop_prices'] and positions[stock].price <= strategy['atr_stop_prices'][stock]:
            if positions[stock].closeable_amount > 0:
                _sp = _get_bid1_sell_price(stock, positions[stock].price)
                order_target(stock, 0, LimitOrderStyle(_sp), pindex=pindex)
                _sell_qty = positions[stock].closeable_amount
                _slog('S5', 'ATR止损', f'触发卖出 {stock} {_sell_qty}股@{_sp:.2f}')
            else:
                del strategy['atr_stop_prices'][stock]
                continue
            # 记录冷却期
            if strategy.get('enable_cooldown'):
                strategy['no_buy_stocks'][stock] = context.current_dt.date()
            del strategy['atr_stop_prices'][stock]


# ====================== 成本保护止损 ======================'"

def small_check_cost_protection_stop_loss(context, strategy):
    if not strategy['enable_cost_protection']:
        return
    pindex = strategy['pindex']
    positions = context.subportfolios[pindex].positions
    if g.log_trade_detail:
        _slog('S5', '成本保护', f'止损检查开始, {len(positions)}只持仓')
    for stock in list(positions.keys()):
        price = positions[stock].price
        avg_cost = positions[stock].avg_cost
        profit_ratio = (price - avg_cost) / avg_cost
        # 100%翻倍止盈
        if price >= avg_cost * 2:
            if positions[stock].closeable_amount > 0:
                _sp = _get_bid1_sell_price(stock, price)
                order_target(stock, 0, LimitOrderStyle(_sp), pindex=pindex)
                _sell_qty = positions[stock].closeable_amount
                _slog('S5', '翻倍止盈', f'卖出 {stock} {_sell_qty}股@{_sp:.2f} 盈利{profit_ratio*100:.1f}%')
            if stock in strategy['atr_stop_prices']:
                del strategy['atr_stop_prices'][stock]
            continue
        # 成本保护止损
        stop_loss_line = -strategy['stoploss_limit']
        if profit_ratio >= strategy['cost_protection_profit_threshold_2']:
            stop_loss_line = strategy['cost_protection_stop_line_2']
        elif profit_ratio >= strategy['cost_protection_profit_threshold_1']:
            stop_loss_line = strategy['cost_protection_stop_line_1']
        if profit_ratio < stop_loss_line:
            if positions[stock].closeable_amount > 0:
                _sp = _get_bid1_sell_price(stock, price)
                order_target(stock, 0, LimitOrderStyle(_sp), pindex=pindex)
                _sell_qty = positions[stock].closeable_amount
                _slog('S5', '成本保护', f'止损卖出 {stock} {_sell_qty}股@{_sp:.2f} 盈亏{profit_ratio*100:+.1f}%')
            if strategy.get('enable_cooldown'):
                strategy['no_buy_stocks'][stock] = context.current_dt.date()
            if stock in strategy['atr_stop_prices']:
                del strategy['atr_stop_prices'][stock]


# ====================== 市场趋势止损 ======================'"

def small_check_market_stop_loss(context, strategy):
    """大盘惨跌止损"""
    if g.log_trade_detail:
        _slog('S5', '暴跌止损', '检查开始')
    stock_df = get_price(
        security=get_index_stocks("399101.XSHE"),
        end_date=context.previous_date,
        frequency="daily",
        fields=["close", "open"],
        count=1,
        panel=False,
    )
    down_ratio = (stock_df["close"] / stock_df["open"] - 1).mean()
    if down_ratio <= -strategy['stoploss_market']:
        pindex = strategy['pindex']
        log.warn(f"[{strategy['name']}] 大盘惨跌，平均降幅 {down_ratio:.2%}")
        for stock in list(context.subportfolios[pindex].positions.keys()):
            pos = context.subportfolios[pindex].positions[stock]
            if pos.closeable_amount > 0:
                _sp = _get_bid1_sell_price(stock, pos.price)
                _sell_qty = pos.closeable_amount
                order_target(stock, 0, LimitOrderStyle(_sp), pindex=pindex)
                _slog('S5', '市场止损', f'清仓卖出 {stock} {_sell_qty}股@{_sp:.2f}')
            if stock in strategy['atr_stop_prices']:
                del strategy['atr_stop_prices'][stock]


# ====================== 红利过滤 ======================'"

def small_bonus_filter(context, strategy, stock_list):
    if g.log_filter_detail:
        _slog('S5', '分红', '过滤开始')
    if not strategy.get('enable_bonus_filter'):
        return stock_list
    year = context.previous_date.year
    end_date = context.previous_date
    if end_date.month in [5]:
        start_date = datetime.datetime(year=year, month=1, day=1)
        # 5月分红处理 5月份分支：查已实施分红的股票
        # implementation_pub_date NULL时SQL的<=过滤天然排除NULL行，语义正确（未实施的不入选）
        # 显式添加 != None 增强防御性，避免ORM/数据库对NULL处理的兼容性差异
        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.company_name,
            finance.STK_XR_XD.board_plan_pub_date,
            finance.STK_XR_XD.bonus_amount_rmb,
            finance.STK_XR_XD.bonus_ratio_rmb,
        ).filter(
            finance.STK_XR_XD.board_plan_pub_date > start_date,
            finance.STK_XR_XD.board_plan_pub_date <= end_date,
            finance.STK_XR_XD.implementation_pub_date <= end_date,
            finance.STK_XR_XD.implementation_pub_date != None,
            finance.STK_XR_XD.bonus_ratio_rmb > 0,
            finance.STK_XR_XD.code.in_(stock_list),
        )
        expected_bonus_df = finance.run_query(q)
        if len(expected_bonus_df) > 0:
            bonus_list = expected_bonus_df["code"].unique().tolist()
        else:
            bonus_list = []
    else:
        reprot_date = datetime.datetime(year=year - 1, month=12, day=31)
        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.company_name,
            finance.STK_XR_XD.a_registration_date,
            finance.STK_XR_XD.bonus_amount_rmb,
            finance.STK_XR_XD.bonus_ratio_rmb,
        ).filter(
            finance.STK_XR_XD.report_date == reprot_date,
            finance.STK_XR_XD.bonus_type == "年度分红",
            finance.STK_XR_XD.implementation_pub_date <= end_date,
            finance.STK_XR_XD.board_plan_bonusnote == "不分配不转增",
            finance.STK_XR_XD.code.in_(stock_list),
        )
        no_year_bonus = finance.run_query(q)
        no_year_bonus_list = no_year_bonus["code"].unique().tolist()
        bonus_list = [code for code in stock_list if code not in no_year_bonus_list]
        # 市值排序
        bonus_list = small_short_by_market_cap(context, bonus_list)

    if len(bonus_list) < strategy['max_position_count']:
        bonus_list.extend(
            [x for x in small_short_by_market_cap(context, stock_list) if x not in bonus_list][
                : strategy['max_position_count'] - len(bonus_list)
            ]
        )
    return bonus_list


# ====================== 审计过滤（简化版，2025年前使用） ======================'"

def small_filter_audit(context, strategy, code_list):
    """简化版审计过滤：近三年审计意见检查"""
    if not code_list:
        return []
    previous_date = context.previous_date
    last_year = (previous_date.replace(year=previous_date.year - 3, month=1, day=1)).strftime("%Y-%m-%d")
    # 审计字段修正 查询具体字段opinion_type_id，而非整个表对象
    q = query(
        finance.STK_AUDIT_OPINION.code,
        finance.STK_AUDIT_OPINION.pub_date,
        finance.STK_AUDIT_OPINION.opinion_type_id,
    ).filter(
        finance.STK_AUDIT_OPINION.code.in_(code_list),
        finance.STK_AUDIT_OPINION.pub_date >= last_year,
        finance.STK_AUDIT_OPINION.pub_date <= context.previous_date
    )
    df = finance.run_query(q)
    values_to_check = [3, 4, 5, 7]
    if not df.empty and "opinion_type_id" in df.columns:
        bad_stocks = set(df[df["opinion_type_id"].isin(values_to_check)]['code'])
        return [s for s in code_list if s not in bad_stocks]
    return code_list


# ====================== 冷却期过滤 ======================'"

def small_filter_cooldown_stocks(context, strategy, stock_list):
    """过滤处于止损冷却期的股票"""
    if g.log_filter_detail:
        _slog('S5', '冷却', '过滤开始')
    if not strategy.get('enable_cooldown'):
        return stock_list

    current_date = context.current_dt.date()
    cooldown_days = strategy.get('cooldown_days', 2)
    valid_stocks = []

    for stock in stock_list:
        if stock in strategy.get('no_buy_stocks', {}):
            stop_date = strategy['no_buy_stocks'][stock]
            trade_days = get_trade_days(start_date=stop_date, end_date=current_date)
            passed_days = len(trade_days) - 1
            if passed_days < cooldown_days:
                _slog('S5', '冷却', f'{stock} 止损于{stop_date}, {passed_days}日, 仍在冷却期')
                continue
            else:
                del strategy['no_buy_stocks'][stock]
        valid_stocks.append(stock)
    return valid_stocks


# ====================== MACD工具函数 ======================'"

def small_macd(close, short=12, long=26, m=9):
    close_s = pd.Series(close)
    dif = close_s.ewm(span=short, min_periods=short - 1, adjust=False).mean() - \
          close_s.ewm(span=long, min_periods=long - 1, adjust=False).mean()
    dea = dif.ewm(span=m, min_periods=m - 1, adjust=False).mean()
    return dif, dea, (dif - dea) * 2


# ====================== 市值排序 ======================'"

def small_short_by_market_cap(context, stock_list):
    short_q = (
        query(valuation.code, valuation.market_cap)
        .filter(
            valuation.code.in_(stock_list),
            valuation.day == context.previous_date,
        )
        .order_by(valuation.market_cap.asc())
    )
    short_df = get_fundamentals(short_q, date=context.previous_date)
    return short_df["code"].unique().tolist() if not short_df.empty else []


# ====================== 买卖分离核心函数 ======================'"

def small_iSell(context):
    """策略5：10:00 专门执行卖出"""
    strategy = g.small_strategy
    pindex = strategy['pindex']
    sub_portfolio = context.subportfolios[pindex]
    if g.log_trade_detail:
        _slog('S5', '卖出', f'决策开始, {len(sub_portfolio.positions)}只持仓')
    strategy['limitup_sold_today'] = []
    strategy['not_buy_again'] = []

    # 顶背离检测
    # 简化逻辑优化 简化补检测：如dbl不足2个，仅补1次（而非10次大量API调用）
    # 正常每日检测在09:31执行(small_check_macd_divergence_daily)，此处仅作初始补位
    divergence_risk_flag = False
    if strategy['DBL_control']:
        if len(strategy['dbl']) < 2:
            # 仅在完全没有历史数据时补检测1次
            small_check_macd_divergence(context, strategy)
        if len(strategy['dbl']) > 0 and 1 in strategy['dbl'][-strategy['check_macd_divergence_days']:]:
            divergence_risk_flag = True

    # 动态调整持仓数量（独立版V3逻辑）
    if strategy['enable_dynamic_stock_num']:
        ma_para = 10
        today = context.previous_date
        start_date = today - datetime.timedelta(days=ma_para * 2)
        index_df = get_price("399101.XSHE", start_date=start_date, end_date=today, frequency="daily")
        index_df["ma"] = index_df["close"].rolling(window=ma_para).mean()
        last_row = index_df.iloc[-1]
        diff = last_row["close"] - last_row["ma"]
        strategy['max_position_count'] = (
            3 if diff >= 500
            else 3 if 200 <= diff < 500
            else 4 if -200 <= diff < 200
            else 5 if -500 <= diff < -200
            else 6
        )

    # 选股（使用独立版V3逻辑）
    strategy['stocks'] = small_choice_small(context, strategy, strategy['max_position_count'])

    cdata = get_current_data()
    positions = context.subportfolios[pindex].positions

    if divergence_risk_flag:
        log.warning(f"[{strategy['name']}] 顶背离触发，今日只卖不买")
        for stock in list(positions.keys()):
            if stock in strategy['yesterday_HL_list']:
                continue
            if cdata[stock].paused:
                continue
            order_target(stock, 0, LimitOrderStyle(_get_bid1_sell_price(stock, cdata[stock].last_price)), pindex=pindex)
            _sell_qty = positions[stock].closeable_amount
            _slog('S5', '卖出', f'非持仓列表 {stock} {_sell_qty}股@{cdata[stock].last_price:.2f}')
    else:
        for s in list(positions.keys()):
            if cdata[s].paused:
                continue
            if s not in strategy['stocks'] and s not in strategy['yesterday_HL_list']:
                order_target(s, 0, LimitOrderStyle(_get_bid1_sell_price(s, cdata[s].last_price)), pindex=pindex)
                _sell_qty = positions[s].closeable_amount
                _slog('S5', '卖出', f'非选股池 {s} {_sell_qty}股@{cdata[s].last_price:.2f}')

    # 止损检查已移至 small_daily_stoploss（每天执行）


def small_daily_stoploss(context):
    """策略5：每天10:05执行止损检查（与独立版sell_small_cap_stocks一致）"""
    strategy = g.small_strategy
    pindex = strategy['pindex']
    positions = context.subportfolios[pindex].positions
    if not positions:
        return
    cdata = get_current_data()
    # 更新ATR止损价（与独立版update_atr_stop_prices一致）
    if strategy['enable_atr_stop_loss']:
        small_update_atr_stop_prices(context, strategy)

    # ATR止损
    if strategy['enable_atr_stop_loss']:
        small_check_atr_stop_loss(context, strategy)
    # 成本保护止损 + 固定止损
    if strategy.get('stoploss_strategy', 3) in [1, 3]:
        small_check_cost_protection_stop_loss(context, strategy)
    # 市场止损
    if strategy.get('stoploss_strategy', 3) in [2, 3]:
        small_check_market_stop_loss(context, strategy)


def small_check_macd_divergence_daily(context):
    """策略5：每天09:31执行顶背离检测（与独立版check_macd_divergence一致）"""
    if g.log_trade_detail:
        _slog('S5', 'MACD', '背离检测开始')
    strategy = g.small_strategy
    if strategy['DBL_control']:
        small_check_macd_divergence(context, strategy)


def small_iBuy(context):
    """策略5：10:03 专门执行买入（等待卖出完成）"""
    strategy = g.small_strategy
    pindex = strategy['pindex']
    if g.log_trade_detail:
        _slog('S5', '买入', f'决策开始, 可用资金{context.subportfolios[pindex].available_cash:,.0f}')

    # 顶背离触发时不买入
    if strategy['DBL_control'] and 1 in strategy['dbl'][-strategy['check_macd_divergence_days']:]:
        _slog('S5', '买入', '顶背离模式, 暂停买入')
        return

    current_positions = context.subportfolios[pindex].positions
    available_cash = context.subportfolios[pindex].available_cash
    cdata = get_current_data()

    buy_list = [s for s in strategy.get('stocks', []) if s not in current_positions or current_positions[s].total_amount == 0]
    # 按实际候选数等分可用现金（与独立版一致）
    position_size = available_cash / len(buy_list) if buy_list else 0
    if strategy.get('rebalance_cap') is not None and buy_list:
        cap = strategy['rebalance_cap']
        existing_value = sum(pos.value for pos in current_positions.values())
        max_buy_value = max(0, cap - existing_value)
        position_size_capped = max_buy_value / len(buy_list)
        if position_size_capped < position_size:
            _slog('S5', '再平衡', f'截流: 原{position_size:.0f}→{position_size_capped:.0f}元/只 (上限{cap})')
            position_size = position_size_capped
    # ===== S5截流结束 =====
    for s in buy_list:
        if available_cash < 100 * cdata[s].last_price:
            break
        if cdata[s].paused:
            continue
        if s in current_positions:
            current_value = current_positions[s].value
            buy_value = max(0, position_size - current_value)
        else:
            buy_value = position_size
        if buy_value < 5000:  # 最低买入金额（与独立版open_position一致）
            continue
        buy_value = min(buy_value, available_cash)
        buy_amount = small_calculate_dynamic_buy_amount(buy_value, cdata[s].last_price, available_cash, strategy)
        min_cost = 100 * cdata[s].last_price
        if buy_amount * cdata[s].last_price < min_cost:
            continue
        if buy_amount > 0:
            order(s, buy_amount, style=LimitOrderStyle(round(1.01 * cdata[s].last_price, 3)), pindex=pindex)
            _slog('S5', '买入', f'{s} {buy_amount}股@{cdata[s].last_price:.2f} 金额{buy_amount*cdata[s].last_price:,.0f}')
            available_cash -= buy_amount * cdata[s].last_price

def small_check_limit_up(context):
    """检查昨日涨停股今日表现"""
    strategy = g.small_strategy
    pindex = strategy['pindex']
    positions = context.subportfolios[pindex].positions
    if not strategy['yesterday_HL_list']:
        return
    cdata = get_current_data()
    sold_count = 0
    for stock in strategy['yesterday_HL_list'][:]:
        if cdata[stock].paused:
            continue
        try:
            # 安全检查 end_date=current_dt + count=1，仅获取最近1根分钟K线，受 avoid_future_data 保护
            current_price = get_price(stock, end_date=context.current_dt,
                                     frequency='1m', fields='close',
                                     skip_paused=False, count=1).iloc[0, 0]
        except:
            current_price = cdata[stock].last_price
        if current_price < cdata[stock].high_limit - 0.001:
            last_price = cdata[stock].last_price
            log_price = last_price if last_price > 0 else current_price
            order_target(stock, 0, LimitOrderStyle(_get_bid1_sell_price(stock, log_price)), pindex=pindex)
            _sell_qty = positions[stock].closeable_amount
            _slog('S5', '涨停回落', f'卖出 {stock} {_sell_qty}股 昨涨停今日开板@{log_price:.2f}')
            sold_count += 1
            strategy['yesterday_HL_list'].remove(stock)
            strategy['limitup_sold_today'].append(stock)
    if sold_count > 0:
        strategy['reason_to_sell'] = 'limitup'
        small_buy_with_remaining_cash(context, strategy, sold_count)
        strategy['reason_to_sell'] = ''

def small_buy_with_remaining_cash(context, strategy, buy_num=None):
    """涨停卖出后用剩余资金补仓"""
    pindex = strategy['pindex']
    positions = context.subportfolios[pindex].positions
    if buy_num is None:
        max_new_positions = min(strategy['max_position_count'] - len(positions), 3)
    else:
        max_new_positions = buy_num
    if max_new_positions <= 0:
        return
    cdata = get_current_data()
    cash = context.subportfolios[pindex].available_cash
    buy_candidates = [s for s in strategy.get('stocks', [])
                     if s not in positions
                     and s not in strategy.get('not_buy_again', [])
                     and not cdata[s].paused
                     and s not in strategy.get('limitup_sold_today', [])]
    if not buy_candidates:
        return
    # 按实际候选数等分可用现金（与独立版一致）
    position_size = cash / len(buy_candidates) if buy_candidates else 0
    max_buy = min(len(buy_candidates), max_new_positions)
    bought_count = 0
    for stock in buy_candidates[:max_buy]:
        buy_value = min(position_size, cash)
        min_cost = 100 * cdata[stock].last_price
        if buy_value < min_cost:
            continue
        try:
            buy_amount = small_calculate_dynamic_buy_amount(buy_value, cdata[stock].last_price, cash, strategy)
            if buy_amount <= 0:
                continue
            actual_value = buy_amount * cdata[stock].last_price
            order(stock, buy_amount, style=LimitOrderStyle(round(1.01 * cdata[stock].last_price, 3)), pindex=pindex)
            _slog('S5', '补仓买入', f'{stock} {buy_amount}股@{cdata[stock].last_price:.2f} 金额{actual_value:,.0f}')
            strategy.setdefault('not_buy_again', []).append(stock)
            cash -= actual_value
            bought_count += 1
            min_price = min((cdata[s].last_price for s in buy_candidates), default=0)
            min_unit = 100 * min_price
            if cash < min_unit:
                break
        except Exception as e:
            log.error(f"[{strategy['name']}] 补仓买入出错: {e}")
            continue
    return bought_count > 0

def small_calculate_dynamic_buy_amount(target_value, current_price, available_cash, strategy):
    max_stock_price = strategy.get('max_stock_price', 50)
    min_buy_amount = strategy.get('min_buy_amount', 200)
    if current_price > max_stock_price:
        return 0
    theoretical_amount = int(target_value / current_price)
    buy_amount = int(theoretical_amount / min_buy_amount) * min_buy_amount
    if buy_amount < min_buy_amount:
        buy_amount = min_buy_amount if (min_buy_amount * current_price <= target_value) else 0
    if buy_amount * current_price > available_cash * 0.95:
        max_affordable = int(available_cash * 0.95 / current_price / min_buy_amount) * min_buy_amount
        buy_amount = max(0, max_affordable)
    return buy_amount

def small_iReport(context):
    """策略5收盘报告"""
    strategy = g.small_strategy
    pindex = strategy['pindex']
    if 'initial_total_value' not in strategy:
        strategy['initial_total_value'] = context.subportfolios[pindex].total_value
    cdata = get_current_data()
    tvalue = context.subportfolios[pindex].total_value
    total_profit = int(tvalue - context.subportfolios[pindex].inout_cash)
    base_diff = int(tvalue - strategy['initial_total_value'])
    base_ratio = 100 * (tvalue - strategy['initial_total_value']) / strategy['initial_total_value'] if strategy['initial_total_value'] > 0 else 0
    ptable = pd.DataFrame(columns=['数量', '价值', '名称'])
    positions = context.subportfolios[pindex].positions
    for s in positions:
        ps = positions[s]
        ptable.loc[s] = [ps.total_amount, int(ps.value), cdata[s].name]
    ptable = ptable.sort_values(by='价值', ascending=False)
    log.info(f"[{strategy['name']}] 持仓明细:\n{ptable}")
    log.info(f"[{strategy['name']}] 总盈亏:{total_profit}, 基准盈亏:{base_diff}({base_ratio:.2f}%)")

