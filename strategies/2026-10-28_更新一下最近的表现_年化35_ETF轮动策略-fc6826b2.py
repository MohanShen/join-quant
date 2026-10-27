# Clone from JoinQuant
# postId: fc6826b23d10a9759100d9e1ddc8a242
# backtestId: dbf9941740cb2cb87da5cf81290e7f93
# title: 更新一下最近的表现，年化35%ETF轮动策略

from jqdata import *
import pandas as pd
import numpy as np
import talib
import datetime
from collections import defaultdict
import random
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score, roc_auc_score
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
import math

# =========================
# 1️⃣ 市场风险监测模块
# =========================
class MarketRiskMonitor:
    """市场风险监测：行业宽度 + 集中度 + Z分数"""
    
    def __init__(self):
        self.SPECIAL_INDS = ['801780', '801050', '801950', '801040']  # 银行、有色、煤炭、钢铁
        self.risk_history = []
        self.risk_cache = {}  # 缓存计算结果
        
    def calculate_risk_indicators(self, context, date=None):
        """计算风险指标"""
        if date is None:
            yesterday = context.previous_date
        else:
            yesterday = date
            
        # 缓存检查
        cache_key = str(yesterday)
        if cache_key in self.risk_cache:
            return self.risk_cache[cache_key]
        
        # 获取中证全指成分股
        stocks = get_index_stocks('000985.XSHG', yesterday)
        stocks = [s for s in stocks if s[0] not in ['4','8'] and s[:2]!='68']
        
        if len(stocks) < 100:  # 股票数量太少时不计算
            return {'risk_level': 0, 'concentration_ratio': 0, 'market_breadth': 0.5}
            
        # 获取行业分类
        ind_map = get_industry(stocks, date=yesterday)
        stk_to_ind = {}
        for s in stocks:
            if s in ind_map and 'sw_l1' in ind_map[s]:
                stk_to_ind[s] = ind_map[s]['sw_l1']['industry_code']
        
        # 获取价格数据
        price_df = get_price(
            list(stk_to_ind.keys()),
            end_date=yesterday,
            count=40,  # 获取40天数据计算20日均线
            fields=['close'],
            panel=False
        )
        
        if price_df.empty or len(price_df) < 20:
            return {'risk_level': 0, 'concentration_ratio': 0, 'market_breadth': 0.5}
            
        # 计算股价在20日均线以上比例
        pivot = price_df.pivot(index='time', columns='code', values='close')
        ma20 = pivot.rolling(20).mean()
        above = (pivot > ma20).astype(float)
        
        # 计算最新交易日的行业宽度
        latest_date = above.index[-1]
        daily = above.loc[latest_date]
        
        ind_breadth = {}
        for stk, val in daily.items():
            if stk in stk_to_ind:
                ind_code = stk_to_ind[stk]
                if ind_code not in ind_breadth:
                    ind_breadth[ind_code] = []
                ind_breadth[ind_code].append(val)
        
        # 计算各项指标
        all_values = []
        for vals in ind_breadth.values():
            all_values.extend(vals)
        market_breadth = np.mean(all_values) if all_values else 0.5
        
        # 四大行业集中度
        special_vals = []
        for ind in self.SPECIAL_INDS:
            if ind in ind_breadth and ind_breadth[ind]:
                special_vals.append(np.mean(ind_breadth[ind]))
        
        if not special_vals:
            return {'risk_level': 0, 'concentration_ratio': 0, 'market_breadth': 0.5}
            
        special_avg = np.mean(special_vals)
        concentration_ratio = special_avg / (market_breadth + 1e-5)
        
        # 计算Z分数（过去20天）
        if len(self.risk_history) >= 20:
            hist_special = [r['special_avg'] for r in self.risk_history[-20:]]
            mean_special = np.mean(hist_special)
            std_special = np.std(hist_special) + 1e-5
            z_score = (special_avg - mean_special) / std_special
        else:
            z_score = 0
        
        # 计算风险级别
        if z_score > 1.0 and concentration_ratio > 1.2 and market_breadth < 0.6:
            risk_level = 2
        elif (z_score > 0.8 and concentration_ratio > 1.1) or market_breadth < 0.5:
            risk_level = 1
        else:
            risk_level = 0
        
        # 记录历史
        result = {
            'date': yesterday,
            'risk_level': risk_level,
            'concentration_ratio': concentration_ratio,
            'market_breadth': market_breadth,
            'special_avg': special_avg,
            'z_score': z_score
        }
        
        self.risk_history.append(result)
        self.risk_cache[cache_key] = result
        
        # 只保留最近100天数据
        if len(self.risk_history) > 100:
            self.risk_history = self.risk_history[-100:]
            
        if len(self.risk_cache) > 20:
            keys = list(self.risk_cache.keys())[:-20]
            for k in keys:
                del self.risk_cache[k]
        
        return result


# ========================================================
# 全局配置与参数
# ========================================================
class SystemConfig:
    """系统全局参数配置"""
    
    # 机器学习参数
    TRAIN_CYCLE = 7                     # 模型重训练周期
    TRAIN_SAMPLES = 50                  # 训练样本数
    FUTURE_DAYS = 5                      # 预测未来天数
    TOP_N = 3                            # 持仓ETF数量
    POSITIVE_THRESHOLD = 0.6             # 高概率阈值
    
    # ====== 动态候选池（根据市场环境+风险等级自动切换） ======
    # 基础池（兜底用，不再直接用于 inference）
    ASSET_LIST = [
        '159915.XSHE',  # 创业板ETF
        '518880.XSHG',  # 黄金ETF
        '513100.XSHG',  # 纳指ETF
        '510180.XSHG',  # 上证180
        '159740.XSHE',  # 恒生科技
        '515980.XSHG',  # AI人工智能
        '516160.XSHG',  # 新能源
        '513120.XSHG',  # 医药创新
    ]
    
    # 成长型池：增量/牛市追求弹性
    AGGRESSIVE_POOL = [
        '159915.XSHE',  # 创业板ETF
        '159949.XSHE',  # 创业板50
        '515980.XSHG',  # AI人工智能
        '516160.XSHG',  # 新能源
        '159740.XSHE',  # 恒生科技
        '513100.XSHG',  # 纳斯达克100
        '512100.XSHG',  # 中证1000
        '159992.XSHE',  # 创新药
        '512880.XSHG',  # 证券ETF
        '513050.XSHG',  # 中概互联
    ]
    
    # 防御型池：存量/熊市追求低波动
    DEFENSIVE_POOL = [
        '518880.XSHG',  # 黄金ETF
        '510880.XSHG',  # 红利ETF
        '510300.XSHG',  # 沪深300ETF
        '511090.XSHG',  # 30年国债ETF
        '511380.XSHG',  # 可转债ETF
        '510180.XSHG',  # 上证180
        '513100.XSHG',  # 纳斯达克（海外分散）
        '516160.XSHG',  # 新能源（少量成长兜底）
    ]
    
    CASH_FUND = '511880.XSHG'           # 现金替代品
    LOOKBACK_DAYS = 25                  # 回溯周期
    DECLINE_LIMIT = -2                  # 累计跌幅阈值
    SINGLE_DROP_LIMIT = -4              # 单日跌幅阈值
    
    # 资产名称映射（含新增ETF）
    ASSET_NAMES = {
        '159915.XSHE': '创业板',
        '159949.XSHE': '创业板50',
        '518880.XSHG': '黄金',
        '513100.XSHG': '纳斯达克',
        '510180.XSHG': '上证180',
        '159740.XSHE': '恒生科技',
        '515980.XSHG': '人工智能',
        '516160.XSHG': '新能源',
        '513120.XSHG': '医药创新',
        '512100.XSHG': '中证1000',
        '159992.XSHE': '创新药',
        '512880.XSHG': '证券ETF',
        '513050.XSHG': '中概互联',
        '510880.XSHG': '红利ETF',
        '510300.XSHG': '沪深300',
        '511090.XSHG': '30年国债',
        '511380.XSHG': '可转债',
    }


class PortfolioState:
    """投资组合状态管理"""
    
    def __init__(self):
        self.classifier = None
        self.model_ready = False
        self.asset_universe = []
        self.last_training = None
        self.boundary_values = {}
        self.scaling_params = {}
        self.selected_assets = []       # 模型选出的ETF列表
        self.asset_probs = {}           # 每只ETF的预测概率
        
        # 模型评估指标
        self.last_training_metrics = {}
        self.model_performance_history = []
        
        # 数据缓存
        self.return_cache = defaultdict(list)
        
        # ETF上市日期缓存 {asset_code: datetime.date or None}
        self.listing_date_cache = {}
        
        # 当前风险等级（由 execute_trading 计算后写入，供 handle_cash_fund 读取）
        self.current_risk_level = 0
        
    def clear_cache(self):
        """清理缓存数据"""
        self.return_cache.clear()


# 创建全局状态实例
portfolio = PortfolioState()

# ========================================================
# 策略初始化
# ========================================================
def initialize(context):
    """策略初始化"""

    print("=" * 60)
    print("多因子机器学习ETF轮动策略 - v3融合版")
    print(f"持仓数量: {SystemConfig.TOP_N} 只ETF")
    print(f"风控模块: MarketRiskMonitor（行业宽度+集中度+Z分数）")
    print(f"候选池: 动态切换（增量→成长池10只 / 存量→防御池8只）")
    print("=" * 60)

    # 基准设置
    set_benchmark('000300.XSHG')

    # 实盘参数
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.000))
    
    # 费率设置
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, 
                           close_commission=0.0002, close_today_commission=0, min_commission=5), 
                 type='fund')
    
    # 日志设置
    log.set_level('system', 'error')
    
    # 全局变量
    g.num = 1
    g.risk_monitor = MarketRiskMonitor()
    
    g.SW1 = {
        '801010': '农林牧渔I', '801020': '采掘I', '801030': '化工I', '801040': '钢铁I',
        '801050': '有色金属I', '801060': '建筑建材I', '801070': '机械设备I', '801080': '电子I',
        '801110': '家用电器I', '801120': '食品饮料I', '801150': '医药生物I', '801180': '房地产I',
        '801190': '金融服务I', '801200': '商业贸易I', '801220': '信息服务I', '801230': '综合I',
        '801710': '建筑材料I', '801720': '建筑装饰I', '801730': '电气设备I', '801740': '国防军工I',
        '801750': '计算机I', '801760': '传媒I', '801770': '通信I', '801780': '银行I',
        '801790': '非银金融I', '801880': '汽车I', '801890': '机械设备I', '801950': '煤炭I',
        '801960': '石油石化I'
    }
    
    g.industry_code = list(g.SW1.keys())

    # 初始化全局状态
    portfolio.asset_universe = []
    portfolio.classifier = None
    portfolio.model_ready = False
    portfolio.last_training = None
    portfolio.boundary_values = {}
    portfolio.scaling_params = {}
    portfolio.selected_assets = []
    portfolio.asset_probs = {}
    portfolio.current_risk_level = 0
    
    # 模型评估相关
    portfolio.last_training_metrics = {}
    portfolio.model_performance_history = []
    
    # 上市日期缓存
    portfolio.listing_date_cache = {}
    
    # 注册定时任务
    run_daily(pre_market_operations, time='before_open')
    run_daily(prepare_trading, time='9:00')
    run_daily(execute_trading, time='10:30')
    run_daily(handle_cash_fund, time='14:55')
    run_daily(generate_portfolio_summary, time='15:30')
    
    # 每周评估模型性能
    run_weekly(evaluate_model_performance, weekday=1, time='15:00')

    print("=" * 60)

# ========================================================
# ETF上市状态检查
# ========================================================
def is_listed(context, asset_code):
    """
    判断ETF在回测当前日期是否已上市（带缓存）。
    """
    current_date = context.current_dt.date()
    
    if asset_code in portfolio.listing_date_cache:
        listing_date = portfolio.listing_date_cache[asset_code]
        if listing_date is None:
            return False
        return listing_date <= current_date
    
    try:
        start_date = get_security_info(asset_code).start_date
        portfolio.listing_date_cache[asset_code] = start_date
        return start_date <= current_date
    except Exception as e:
        log.warning(f"查询 {asset_code} 上市日期失败: {e}")
        portfolio.listing_date_cache[asset_code] = None
        return False


def filter_listed_assets(context, asset_list, min_days_listed=5):
    """
    从资产列表中筛选出已上市且满足最小上市天数的ETF。
    """
    current_date = context.current_dt.date()
    available = []
    
    for asset in asset_list:
        if asset in portfolio.listing_date_cache:
            listing_date = portfolio.listing_date_cache[asset]
        else:
            try:
                listing_date = get_security_info(asset).start_date
                portfolio.listing_date_cache[asset] = listing_date
            except Exception:
                portfolio.listing_date_cache[asset] = None
                continue
        
        if listing_date is None:
            continue
        
        days_since_listing = (current_date - listing_date).days
        if days_since_listing >= min_days_listed:
            available.append(asset)
    
    return available

# ========================================================
# 动态候选池选择（根据市场环境+风险等级切换）
# ========================================================
def get_dynamic_asset_list(context, risk_level=None):
    """
    根据市场环境和风险等级，动态返回 inference 候选 ETF 池。
    
    训练池（asset_universe）保持不变，此函数仅影响预测和交易阶段的候选范围。
    
    切换逻辑：
      增量 + 低风险(0)  → 全成长池     (10只高弹性)
      增量 + 中风险(1)  → 成长 + 防御[:3] (红利/黄金/国债兜底)
      存量 + 低风险(0)  → 防御 + 成长[:3] (创业板/AI/纳指博弈)
      存量 + 中风险(1)  → 纯防御池     (8只低波动)
      高风险(≥2)        → 纯防御池     (安全第一，虽然 execute_trading 会全现金)
    """
    if risk_level is None:
        risk_level = portfolio.current_risk_level
    
    try:
        market_env = judge_market_env(context)
    except Exception as e:
        log.warning(f"市场环境判断失败: {e}，使用基础池")
        return filter_listed_assets(context, SystemConfig.ASSET_LIST, 
                                    min_days_listed=SystemConfig.LOOKBACK_DAYS + 5)
    
    if market_env == '增量':
        if risk_level == 0:
            pool = SystemConfig.AGGRESSIVE_POOL
            tag = '增量+低风险 → 全成长池'
        elif risk_level == 1:
            pool = SystemConfig.AGGRESSIVE_POOL + SystemConfig.DEFENSIVE_POOL[:3]
            pool = list(dict.fromkeys(pool))  # 去重保序
            tag = '增量+中风险 → 成长+防御兜底'
        else:
            pool = SystemConfig.DEFENSIVE_POOL
            tag = '增量+高风险 → 纯防御'
    else:  # 存量
        if risk_level == 0:
            pool = SystemConfig.DEFENSIVE_POOL + SystemConfig.AGGRESSIVE_POOL[:3]
            pool = list(dict.fromkeys(pool))
            tag = '存量+低风险 → 防御+成长博弈'
        elif risk_level == 1:
            pool = SystemConfig.DEFENSIVE_POOL
            tag = '存量+中风险 → 纯防御'
        else:
            pool = SystemConfig.DEFENSIVE_POOL
            tag = '存量+高风险 → 纯防御'
    
    log.info(f"候选池切换: {tag} ({len(pool)}只ETF)")
    
    # 过滤未上市的
    listed = filter_listed_assets(context, pool, min_days_listed=SystemConfig.LOOKBACK_DAYS + 5)
    
    if not listed:
        log.warning("动态池全部未上市，回退到基础 ASSET_LIST")
        listed = filter_listed_assets(context, SystemConfig.ASSET_LIST, 
                                      min_days_listed=SystemConfig.LOOKBACK_DAYS + 5)
    
    return listed


# ========================================================
# 数据处理工具
# ========================================================
def trim_outliers(data_array, trim_percent=0.05):
    """数据边界修剪"""
    if len(data_array) == 0:
        return data_array
    
    lower_bound = np.percentile(data_array, trim_percent * 100)
    upper_bound = np.percentile(data_array, (1 - trim_percent) * 100)
    return np.clip(data_array, lower_bound, upper_bound)


def standardize_series(data_series):
    """数据标准化"""
    if len(data_series) == 0:
        return data_series
    
    mean_val = np.mean(data_series)
    std_val = np.std(data_series)
    
    if std_val > 0:
        return (data_series - mean_val) / std_val
    
    return data_series


def getStockIndustry(p_stocks, p_industries_type, p_day):
    """获取股票的行业分类"""
    dict_stk_2_ind = {}
    stocks_industry_dict = get_industry(p_stocks, date=p_day)
    for stock in stocks_industry_dict:
        if p_industries_type in stocks_industry_dict[stock]:
            dict_stk_2_ind[stock] = stocks_industry_dict[stock][p_industries_type]['industry_code']
    return pd.Series(dict_stk_2_ind)


def judge_market_env(context, ma_window=20, slope_window=5):
    """判断市场环境：增量 vs 存量"""
    yesterday = context.previous_date
    trade_days = get_trade_days(end_date=yesterday, count=ma_window + slope_window)
    start_date = trade_days[0]

    total_money = (
        get_price('000001.XSHG', start_date=start_date, end_date=yesterday, fields='money')['money'] +
        get_price('399001.XSHE', start_date=start_date, end_date=yesterday, fields='money')['money']
    )
    ma_total = total_money.rolling(ma_window).mean().dropna()
    change_total = (ma_total.iloc[-1] - ma_total.iloc[-slope_window - 1]) / ma_total.iloc[-slope_window - 1]
    
    price_df = get_price('399986.XSHE', end_date=yesterday, count=ma_window, fields='close', skip_paused=True)
    close_prices = price_df['close']
    bank_return = close_prices.iloc[-1] / close_prices.iloc[0] 
    
    return '存量' if change_total <= 0.1 or bank_return <= 0.9 else '增量'


# ========================================================
# 特征工程
# ========================================================
def compute_technical_features(price_data):
    """计算7维技术指标"""
    
    close_prices = price_data['close'].values.astype(float)
    high_prices = price_data['high'].values.astype(float)
    low_prices = price_data['low'].values.astype(float)
    volumes = price_data['volume'].values.astype(float)

    if len(close_prices) < 20:
        return None
    if len(volumes) < 28:
        return None
    if np.any(np.isnan(close_prices)) or np.any(np.isnan(high_prices)) or np.any(np.isnan(low_prices)):
        return None

    # 1. ATR
    atr_vals = talib.ATR(high_prices, low_prices, close_prices, 14)
    if atr_vals is None or len(atr_vals) == 0:
        return None
    atr_val = float(atr_vals[-1])
    if np.isnan(atr_val):
        atr_val = 0.0

    # 2. RSI
    rsi_vals = talib.RSI(close_prices, 14)
    if rsi_vals is None or len(rsi_vals) == 0:
        return None
    rsi_val = float(rsi_vals[-1])
    if np.isnan(rsi_val):
        rsi_val = 50.0

    # 3. MACD
    macd_line, _, _ = talib.MACD(close_prices)
    if macd_line is None or len(macd_line) == 0:
        return None
    macd_val = float(macd_line[-1])
    if np.isnan(macd_val):
        macd_val = 0.0

    # 4. 布林带中轨
    _, midline, _ = talib.BBANDS(close_prices, 20)
    if midline is None or len(midline) == 0:
        return None
    bb_val = float(midline[-1])
    if np.isnan(bb_val):
        bb_val = float(close_prices[-1])

    # 5. 成交量比率
    recent_volume = np.sum(volumes[-14:])
    previous_volume = np.sum(volumes[-28:-14])
    vol_ratio = float(recent_volume / previous_volume) if previous_volume > 0 else 1.0

    # 6. MFI
    mfi_vals = talib.MFI(high_prices, low_prices, close_prices, volumes, 14)
    if mfi_vals is None or len(mfi_vals) == 0:
        return None
    mfi_val = float(mfi_vals[-1])
    if np.isnan(mfi_val):
        mfi_val = 50.0

    # 7. PSY
    if len(close_prices) < 12:
        return None
    price_changes = np.diff(close_prices[-12:])
    rising_days = np.sum(price_changes > 0)
    psy_val = float(rising_days / 11 * 100)

    feature_vector = [atr_val, rsi_val, macd_val, bb_val, vol_ratio, mfi_val, psy_val]

    for i, feature in enumerate(feature_vector):
        if feature is None or not np.isfinite(feature):
            return None

    return np.array(feature_vector, dtype=float)


# ========================================================
# 机器学习模型 - 分类模型
# ========================================================
def train_classification_model(context):
    """训练分类模型预测未来收益是否高于截面中位数"""
    current_date = context.current_dt.date()
    if portfolio.last_training is not None:
        days_passed = (current_date - portfolio.last_training).days
        if days_passed < SystemConfig.TRAIN_CYCLE:
            return False

    log.info("=" * 50)
    log.info(f"开始训练分类模型，预测未来{SystemConfig.FUTURE_DAYS}天收益是否高于截面中位数...")

    if not portfolio.asset_universe:
        portfolio.asset_universe = [
            '517520.XSHG', '159583.XSHE', '159992.XSHE', '159723.XSHE', '159871.XSHE',
            '513050.XSHG', '159320.XSHE', '516160.XSHG', '159915.XSHE', '159667.XSHE',
            '159836.XSHE', '159855.XSHE', '562310.XSHG', '563300.XSHG', '512980.XSHG',
            '517800.XSHG', '515030.XSHG', '159912.XSHE', '512100.XSHG', '159755.XSHE',
            '159628.XSHE', '560980.XSHG', '515400.XSHG', '512200.XSHG', '159985.XSHE',
            '512050.XSHG', '159851.XSHE', '159930.XSHE', '159561.XSHE', '159698.XSHE',
            '510210.XSHG', '159611.XSHE', '562000.XSHG', '510300.XSHG', '513080.XSHG',
            '159998.XSHE', '511090.XSHG', '159766.XSHE', '516600.XSHG', '516110.XSHG',
            '159616.XSHE', '159745.XSHE', '159790.XSHE', '562500.XSHG', '159687.XSHE',
            '159518.XSHE', '512660.XSHG', '516150.XSHG', '513310.XSHG', '513500.XSHG',
            '512690.XSHG', '513520.XSHG', '511380.XSHG', '159941.XSHE', '159887.XSHE',
            '513090.XSHG', '159509.XSHE',
        ]

    # ★ 训练前过滤未上市ETF
    min_listed_days = 60 + SystemConfig.FUTURE_DAYS + 10
    listed_universe = filter_listed_assets(context, portfolio.asset_universe, min_listed_days)
    
    unlisted_count = len(portfolio.asset_universe) - len(listed_universe)
    if unlisted_count > 0:
        log.info(f"过滤掉 {unlisted_count} 只未上市/上市不足{min_listed_days}天的ETF")
    
    if len(listed_universe) < 10:
        log.warning(f"上市ETF不足: {len(listed_universe)} < 10，无法训练")
        return False

    if len(listed_universe) > SystemConfig.TRAIN_SAMPLES:
        training_set = random.sample(listed_universe, SystemConfig.TRAIN_SAMPLES)
    else:
        training_set = listed_universe

    log.info(f"使用{len(training_set)}个样本训练")

    feature_collection = []
    label_collection = []
    data_issues = 0
    feature_issues = 0
    date_data = {}
    
    for asset in training_set:
        end_date = context.current_dt - datetime.timedelta(days=SystemConfig.FUTURE_DAYS)
        price_history = get_price(asset, count=60, end_date=end_date,
                                fields=['close', 'high', 'low', 'volume'],
                                skip_paused=True, fq='pre')

        if price_history is None or len(price_history) < 60:
            data_issues += 1
            continue

        price_history['close'] = pd.to_numeric(price_history['close'], errors='coerce').astype('float64')
        price_history['high'] = pd.to_numeric(price_history['high'], errors='coerce').astype('float64')
        price_history['low'] = pd.to_numeric(price_history['low'], errors='coerce').astype('float64')
        price_history['volume'] = pd.to_numeric(price_history['volume'], errors='coerce').astype('float64')
        price_history = price_history.dropna()

        if len(price_history) < 50 + SystemConfig.FUTURE_DAYS:
            data_issues += 1
            continue

        features = compute_technical_features(price_history.iloc[:50])
        if features is None:
            feature_issues += 1
            continue

        start_price = price_history['close'].iloc[49]
        end_price = price_history['close'].iloc[49 + SystemConfig.FUTURE_DAYS]
        
        if start_price > 0:
            future_return = (end_price - start_price) / start_price
        else:
            future_return = 0.0
        
        if np.isnan(future_return) or np.isinf(future_return):
            continue
        
        date = price_history.index[49]
        if date not in date_data:
            date_data[date] = []
        
        date_data[date].append({
            'features': features,
            'future_return': future_return
        })

    for date, assets_data in date_data.items():
        if len(assets_data) < 5:
            continue
        
        future_returns = [data['future_return'] for data in assets_data]
        median_return = np.median(future_returns)
        
        for data in assets_data:
            label = 1 if data['future_return'] > median_return else 0
            feature_collection.append(data['features'].copy())
            label_collection.append(label)

    log.info(f"数据收集完成: 成功{len(feature_collection)}个, 数据不足{data_issues}个, "
            f"特征提取失败{feature_issues}个")
    
    if len(feature_collection) < 20:
        return False

    positive_ratio = sum(label_collection) / len(label_collection)
    if not (0.3 <= positive_ratio <= 0.7):
        log.warning(f"正样本比例异常: {positive_ratio:.2%}")
        return False

    X = np.array(feature_collection, dtype=float)
    y = np.array(label_collection, dtype=int)

    if not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
        return False

    # 特征预处理
    X_winsorized = X.copy()
    for col_idx in range(X.shape[1]):
        X_winsorized[:, col_idx] = trim_outliers(X[:, col_idx], trim_percent=0.05)

    X_normalized = X_winsorized.copy()
    for col_idx in range(X_normalized.shape[1]):
        X_normalized[:, col_idx] = standardize_series(X_winsorized[:, col_idx])

    X_train, X_test, y_train, y_test = train_test_split(
        X_normalized, y, test_size=0.3, random_state=42, stratify=y
    )

    clf_model = RandomForestClassifier(
        n_estimators=100, max_depth=10, min_samples_split=5, min_samples_leaf=2,
        random_state=42, class_weight='balanced'
    )
    clf_model.fit(X_train, y_train)

    train_accuracy = clf_model.score(X_train, y_train)
    test_accuracy = clf_model.score(X_test, y_test)
    
    y_train_pred = clf_model.predict(X_train)
    y_test_pred = clf_model.predict(X_test)
    
    train_f1 = f1_score(y_train, y_train_pred)
    test_f1 = f1_score(y_test, y_test_pred)
    
    y_test_prob = clf_model.predict_proba(X_test)[:, 1]
    test_roc_auc = roc_auc_score(y_test, y_test_prob)
    
    portfolio.last_training_metrics = {
        'train_accuracy': train_accuracy, 'test_accuracy': test_accuracy,
        'train_f1': train_f1, 'test_f1': test_f1, 'test_roc_auc': test_roc_auc,
        'positive_ratio': positive_ratio, 'train_size': X_train.shape[0],
        'test_size': X_test.shape[0], 'training_date': current_date
    }
    
    portfolio.model_performance_history.append(portfolio.last_training_metrics.copy())
    if len(portfolio.model_performance_history) > 20:
        portfolio.model_performance_history.pop(0)
    
    log.info("测试集分类报告:")
    test_report = classification_report(y_test, y_test_pred, target_names=['低于中位数', '高于中位数'])
    log.info(f"\n{test_report}")
    
    cm = confusion_matrix(y_test, y_test_pred)
    log.info(f"混淆矩阵: TN={cm[0,0]}, FP={cm[0,1]}, FN={cm[1,0]}, TP={cm[1,1]}")
    
    portfolio.classifier = clf_model
    portfolio.model_ready = True
    portfolio.last_training = current_date

    portfolio.boundary_values = {}
    for col_idx in range(X.shape[1]):
        portfolio.boundary_values[col_idx] = (
            np.percentile(X[:, col_idx], 5),
            np.percentile(X[:, col_idx], 95)
        )

    portfolio.scaling_params = {}
    for col_idx in range(X_winsorized.shape[1]):
        portfolio.scaling_params[col_idx] = (
            np.mean(X_winsorized[:, col_idx]),
            np.std(X_winsorized[:, col_idx])
        )

    log.info(f"模型训练完成: 训练集准确率={train_accuracy:.2%}, 测试集准确率={test_accuracy:.2%}, "
            f"测试集F1={test_f1:.3f}, ROC AUC={test_roc_auc:.3f}")
    
    return True


# ========================================================
# 收益预测函数
# ========================================================
def predict_asset_probability(context, asset):
    """预测资产未来收益高于截面中位数的概率"""

    if not portfolio.model_ready:
        return None

    # ★ 预测前检查上市状态
    if not is_listed(context, asset):
        return None

    end_date = context.current_dt - datetime.timedelta(days=1)
    price_history = get_price(asset, count=50, end_date=end_date,
                            fields=['close', 'high', 'low', 'volume'],
                            skip_paused=True, fq='pre')

    if price_history is None or len(price_history) < 32:
        return None

    price_history['close'] = pd.to_numeric(price_history['close'], errors='coerce').astype('float64')
    price_history['high'] = pd.to_numeric(price_history['high'], errors='coerce').astype('float64')
    price_history['low'] = pd.to_numeric(price_history['low'], errors='coerce').astype('float64')
    price_history['volume'] = pd.to_numeric(price_history['volume'], errors='coerce').astype('float64')
    price_history = price_history.dropna()

    if len(price_history) < 32:
        return None

    features = compute_technical_features(price_history)
    if features is None:
        return None

    features_winsorized = features.copy()
    for col_idx in range(len(features)):
        if col_idx in portfolio.boundary_values:
            lower, upper = portfolio.boundary_values[col_idx]
            features_winsorized[col_idx] = np.clip(features[col_idx], lower, upper)

    features_normalized = features_winsorized.copy()
    for col_idx in range(len(features_winsorized)):
        if col_idx in portfolio.scaling_params:
            mean, std = portfolio.scaling_params[col_idx]
            if std > 0:
                features_normalized[col_idx] = (features_winsorized[col_idx] - mean) / std

    X = np.array([features_normalized], dtype=float)
    positive_prob = portfolio.classifier.predict_proba(X)[0][1]
    return positive_prob


# ========================================================
# 模型性能监控
# ========================================================
def evaluate_model_performance(context):
    """评估模型历史性能"""
    
    if not portfolio.model_performance_history:
        return None
    
    test_accuracies = [m['test_accuracy'] for m in portfolio.model_performance_history]
    test_f1s = [m['test_f1'] for m in portfolio.model_performance_history]
    test_roc_aucs = [m['test_roc_auc'] for m in portfolio.model_performance_history]
    
    avg_accuracy = np.mean(test_accuracies)
    avg_f1 = np.mean(test_f1s)
    avg_roc_auc = np.mean(test_roc_aucs)
    
    latest_metrics = portfolio.last_training_metrics
    
    log.info(f"模型历史性能: 准确率={avg_accuracy:.3f}±{np.std(test_accuracies):.3f}, "
            f"F1={avg_f1:.3f}±{np.std(test_f1s):.3f}, "
            f"ROC AUC={avg_roc_auc:.3f}±{np.std(test_roc_aucs):.3f}")
    
    if len(test_accuracies) >= 3:
        trend = np.polyfit(range(3), test_accuracies[-3:], 1)[0]
        if trend > 0.01:
            log.info("📈 模型性能趋势: 上升")
        elif trend < -0.01:
            log.info("📉 模型性能趋势: 下降")
        else:
            log.info("➡️ 模型性能趋势: 平稳")
    
    return {
        'avg_accuracy': avg_accuracy, 'avg_f1': avg_f1, 'avg_roc_auc': avg_roc_auc,
        'latest_accuracy': latest_metrics.get('test_accuracy', 0),
        'latest_f1': latest_metrics.get('test_f1', 0),
        'latest_roc_auc': latest_metrics.get('test_roc_auc', 0)
    }


# ========================================================
# 动量评分函数
# ========================================================
def calculate_asset_scores(context, asset_list):
    """计算资产动量得分（带上市检查）"""
    
    score_results = []
    valid_assets = []
    
    for asset in asset_list:
        # ★ 上市状态检查
        if not is_listed(context, asset):
            continue
        
        price_df = attribute_history(asset, SystemConfig.LOOKBACK_DAYS, '1d', ['close'])
        
        if len(price_df) < SystemConfig.LOOKBACK_DAYS:
            continue
            
        price_df['log_price'] = np.log(price_df.close)
        price_df['index'] = np.arange(len(price_df.log_price))
        
        y = price_df['log_price'].values
        x = price_df['index'].values
        
        slope, intercept = np.polyfit(x, y, 1)
        annual_return = math.pow(math.exp(slope), 250) - 1
        
        y_pred = slope * x + intercept
        y_mean = np.mean(y)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        score = annual_return * r_squared
        score_results.append(score)
        valid_assets.append(asset)
    
    if not score_results:
        return pd.DataFrame()
    
    result_df = pd.DataFrame(index=valid_assets, data={'score': score_results})
    result_df = result_df.sort_values(by='score', ascending=False)
    return result_df


# ========================================================
# 实时涨幅计算
# ========================================================
def get_intraday_change(asset_code):
    """获取当日实时涨幅"""
    yesterday_data = attribute_history(asset_code, 1, '1d', ['close'])
    if yesterday_data.empty:
        return 0.0
    
    yesterday_price = yesterday_data['close'].iloc[0]
    current_data = get_current_data()
    
    if asset_code not in current_data:
        return 0.0
    
    current_price = current_data[asset_code].last_price
    price_change = (current_price - yesterday_price) / yesterday_price
    return round(price_change * 100, 4)


# ========================================================
# 风险控制检查
# ========================================================
def evaluate_drawdown_risk(asset_code):
    """评估资产回撤风险"""
    
    current_cache = portfolio.return_cache.get(asset_code, [])
    portfolio.return_cache = {asset_code: current_cache}

    if not portfolio.return_cache[asset_code]:
        lookback_days = SystemConfig.LOOKBACK_DAYS
        historical_data = attribute_history(asset_code, lookback_days, '1d', ['close'])
        
        if historical_data.empty:
            return False, "无历史数据"

        daily_returns = historical_data['close'].pct_change().dropna().tolist()
        daily_returns = [round(x * 100, 4) for x in daily_returns]
        portfolio.return_cache[asset_code] = daily_returns

    daily_returns = portfolio.return_cache[asset_code]
    today_return = get_intraday_change(asset_code)
    full_returns = daily_returns + [today_return]
    updated_returns = full_returns[1:]
    portfolio.return_cache[asset_code] = updated_returns

    consecutive_days = 0
    total_drop = 0.0

    for ret in reversed(updated_returns):
        if ret <= 0.0:
            consecutive_days += 1
            total_drop += ret
        else:
            break

    if consecutive_days > 0 and total_drop <= SystemConfig.DECLINE_LIMIT:
        reason = f"连续{consecutive_days}天累计跌幅{round(total_drop, 2)}%，超过{SystemConfig.DECLINE_LIMIT}%阈值"
        return False, reason
    
    if consecutive_days > 3:
        reason = f"连续{consecutive_days}天下跌，超过3天阈值"
        return False, reason

    for i, ret in enumerate(updated_returns[-2:]):
        if ret <= SystemConfig.SINGLE_DROP_LIMIT:
            reason = f"最近{2-i}天前存在单日暴跌，超过{SystemConfig.SINGLE_DROP_LIMIT}%阈值"
            return False, reason
            
    return True, "通过风险检查"


# ========================================================
# 资产名称获取
# ========================================================
def get_asset_display_name(asset_code):
    return SystemConfig.ASSET_NAMES.get(asset_code, asset_code)


# ========================================================
# 持仓汇总
# ========================================================
def generate_portfolio_summary(context):
    """生成持仓汇总报告"""
    
    total_value = round(context.portfolio.total_value, 2)
    current_assets = context.portfolio.positions
    if not current_assets:
        print(f"当前总资产: {total_value}")
        return

    print(f"📈 持仓汇总 (总资产: ￥{total_value})")
    print("=" * 80)
    print(f"{'代码':<10} {'名称':<8} {'数量':>8} {'成本':>8} {'现价':>8} {'盈亏':>8} {'盈亏%':>8} {'市值':>10}")
    print("-" * 80)
    
    total_market_value = 0
    
    for asset in current_assets:
        position = current_assets[asset]
        if position.total_amount > 0:
            shares = position.total_amount
            current_price = round(get_current_data()[asset].last_price, 3)
            avg_cost = round(position.avg_cost, 3)
            
            profit_ratio = (current_price - avg_cost) / avg_cost if avg_cost != 0 else 0
            profit_pct = f"{profit_ratio * 100:>6.2f}%"
            profit_amount = round((current_price - avg_cost) * shares, 2)
            
            market_value = round(shares * current_price, 2)
            total_market_value += market_value
            
            asset_code = asset.split(".")[0]
            try:
                asset_name = get_security_info(asset).display_name
            except:
                asset_name = asset
            
            profit_amount_str = f"+{profit_amount:>7.2f}" if profit_amount > 0 else f"-{abs(profit_amount):>7.2f}" if profit_amount < 0 else f"{profit_amount:>8.2f}"
            
            print(f"{asset_code:<10} {asset_name[:8]:<8} {shares:>8} "
                  f"{avg_cost:>8.3f} {current_price:>8.3f} {profit_amount_str} "
                  f"{profit_pct} ￥{market_value:>9.2f}")
    
    print("-" * 80)
    print(f"{'总市值':<10} {'':<8} {'':>8} {'':>8} {'':>8} {'':>8} {'':>8} ￥{total_market_value:>9.2f}")
    print(f"{'总资产':<10} {'':<8} {'':>8} {'':>8} {'':>8} {'':>8} {'':>8} ￥{total_value:>9.2f}")


# ========================================================
# 盘前操作
# ========================================================
def pre_market_operations(context):
    """盘前模型训练和收益预测"""
    
    train_classification_model(context)
    portfolio.asset_probs.clear()
    
    if not portfolio.model_ready:
        print("分类模型未就绪，跳过预测")
        return

    # ★ 动态候选池：根据市场环境+风险等级切换
    dynamic_pool = get_dynamic_asset_list(context)
    
    if not dynamic_pool:
        print("当前无可用候选ETF，跳过预测")
        return

    for asset in dynamic_pool:
        try:
            prob = predict_asset_probability(context, asset)
            if prob is not None:
                portfolio.asset_probs[asset] = prob
                asset_name = get_asset_display_name(asset)
                print(f"📊 {asset_name} 预测上涨概率: {prob:.2%}")
        except Exception as e:
            print(f"资产{asset}收益预测失败: {e}")


# ========================================================
# 交易准备
# ========================================================
def prepare_trading(context):
    """交易前准备：从动态候选池中筛选目标资产"""
    
    # ★ 动态候选池：根据市场环境+风险等级切换（已在 get_dynamic_asset_list 内过滤上市状态）
    dynamic_pool = get_dynamic_asset_list(context)
    
    if not dynamic_pool:
        log.info("当前无可用候选ETF，选择现金基金")
        portfolio.selected_assets = [SystemConfig.CASH_FUND]
        return
    
    score_data = calculate_asset_scores(context, dynamic_pool)
    
    if score_data.empty:
        portfolio.selected_assets = [SystemConfig.CASH_FUND]
        return
    
    positive_score_assets = score_data[score_data["score"] > 0]
    
    if positive_score_assets.empty:
        portfolio.selected_assets = [SystemConfig.CASH_FUND]
        return
    
    # 结合机器学习预测概率
    valid_assets = []
    asset_scores = []
    
    for asset in positive_score_assets.index:
        if asset in portfolio.asset_probs:
            prob = portfolio.asset_probs[asset]
            momentum_score = positive_score_assets.loc[asset, "score"]
            combined_score = momentum_score * prob
            valid_assets.append(asset)
            asset_scores.append(combined_score)
    
    if not valid_assets:
        portfolio.selected_assets = [SystemConfig.CASH_FUND]
        return
    
    selection_df = pd.DataFrame(index=valid_assets, data={'combined_score': asset_scores})
    selection_df = selection_df.sort_values(by='combined_score', ascending=False)
    
    top_n = min(SystemConfig.TOP_N, len(selection_df))
    portfolio.selected_assets = selection_df.index[:top_n].tolist()
    
    selected_names = [get_asset_display_name(asset) for asset in portfolio.selected_assets]
    print(f"📊 选择资产: {', '.join(selected_names)}")
    print("详细得分:")
    for i, asset in enumerate(portfolio.selected_assets):
        asset_name = get_asset_display_name(asset)
        momentum_score = positive_score_assets.loc[asset, "score"]
        prob = portfolio.asset_probs.get(asset, 0)
        combined_score = selection_df.loc[asset, "combined_score"]
        print(f"  {i+1}. {asset_name}: 动量{round(momentum_score, 4)}, "
              f"概率{prob:.2%}, 综合{round(combined_score, 4)}")


# ========================================================
# 执行交易（融合版：行业宽度 + 风险等级 + 模型选择）
# ========================================================
def execute_trading(context):
    """
    核心交易逻辑：
    1. 计算行业宽度，识别领涨行业
    2. 调用 MarketRiskMonitor 获取风险等级
    3. 判断市场环境（增量/存量）
    4. 根据风险等级决定最终持仓组合
    """
    yesterday = context.previous_date
    today = context.current_dt
    
    # ========== Step 1: 计算风险指标 ==========
    risk_data = g.risk_monitor.calculate_risk_indicators(context, yesterday)
    risk_level = risk_data['risk_level']
    concentration_ratio = risk_data['concentration_ratio']
    market_breadth = risk_data['market_breadth']
    
    # 写入 portfolio 供 handle_cash_fund 读取
    portfolio.current_risk_level = risk_level
    
    # ========== Step 2: 行业宽度分析 ==========
    initial_list = get_index_stocks('000985.XSHG', today)
    p_count = 1
    p_industries_type = 'sw_l1'
    
    leading_industry = None
    if initial_list:
        try:
            h = get_price(initial_list, end_date=yesterday, frequency='1d', 
                          fields=['close'], count=p_count + 20, panel=False)
            
            if not h.empty:
                h['date'] = pd.DatetimeIndex(h.time).date
                df_close = h.pivot(index='code', columns='date', values='close').dropna(axis=0)
                
                if not df_close.empty:
                    df_ma20 = df_close.rolling(window=20, axis=1).mean().iloc[:, -p_count:]
                    df_bias = (df_close.iloc[:, -p_count:] > df_ma20)
                    s_stk_2_ind = getStockIndustry(p_stocks=initial_list, p_industries_type=p_industries_type, p_day=yesterday)
                    df_bias['industry_code'] = s_stk_2_ind
                    
                    df_ratio = ((df_bias.groupby('industry_code').sum() * 100.0) / 
                                df_bias.groupby('industry_code').count()).round()
                    
                    if not df_ratio.empty and len(df_ratio.columns) > 0:
                        latest_date = df_ratio.columns[-1]
                        top_values = df_ratio[latest_date].nlargest(g.num)
                        I = top_values.index.tolist()
                        leading_industry = I[0] if I else None
        except Exception as e:
            log.warning(f"行业宽度计算异常: {e}")
    
    # ========== Step 3: 市场环境判断 ==========
    market_env = judge_market_env(context)
    
    # ========== Step 4: 根据风险等级确定买入组合 ==========
    buy_candidates = []
    reason = ""
    
    if risk_level >= 2:
        # 高风险：全部现金
        buy_candidates = [SystemConfig.CASH_FUND]
        reason = f"高风险(等级{risk_level})，集中度{concentration_ratio:.2f}，市场宽度{market_breadth:.2f}，全部持有现金"
        log.info(f"⚠️ 高风险等级{risk_level} -> 全部现金")
        
    elif risk_level == 1:
        # 中等风险：现金 + 模型选择
        buy_candidates = [SystemConfig.CASH_FUND] + portfolio.selected_assets
        buy_candidates = list(dict.fromkeys(buy_candidates))  # 去重保序
        reason = f"中等风险(等级{risk_level})，集中度{concentration_ratio:.2f}，市场宽度{market_breadth:.2f}"
        names = [get_asset_display_name(a) for a in portfolio.selected_assets]
        log.info(f"⚡ 中等风险等级{risk_level} -> 现金 + {', '.join(names)}")
        
    else:
        # 低风险：纯模型选择
        buy_candidates = portfolio.selected_assets.copy()
        reason = f"低风险(等级{risk_level})，集中度{concentration_ratio:.2f}，市场宽度{market_breadth:.2f}"
        if not buy_candidates:
            buy_candidates = [SystemConfig.CASH_FUND]
            log.info(f"✅ 低风险等级{risk_level}，模型未选出资产 -> 现金基金")
        else:
            names = [get_asset_display_name(a) for a in buy_candidates]
            log.info(f"✅ 低风险等级{risk_level} -> {', '.join(names)}")
    
    # ========== Step 5: 打印风险状态 ==========
    log.info(f"市场环境: {market_env}")
    if leading_industry:
        log.info(f"领涨行业: {g.SW1.get(leading_industry, leading_industry)}")
    log.info(f"风险等级: {risk_level} | 集中度: {concentration_ratio:.2f} | 市场宽度: {market_breadth:.2f}")
    
    # ========== Step 6: 卖出不在选中组合的持仓 ==========
    current_positions = context.portfolio.positions
    for asset, position in current_positions.items():
        if position.total_amount > 0 and asset not in buy_candidates:
            asset_name = get_asset_display_name(asset)
            sellable_amount = position.closeable_amount
            if sellable_amount > 0:
                sell_order = order_target_value(asset, 0)
                if sell_order is not None and sell_order.filled > 0:
                    print(f"✅ 卖出 {asset_name}【{asset}】 {sell_order.filled}股")
    
    # ========== Step 7: 资金分配与买入 ==========
    total_value = context.portfolio.total_value
    available_cash = context.portfolio.available_cash
    
    if available_cash < 10000:
        print("可用资金不足，跳过买入")
        return
    
    n_selected = len(buy_candidates)
    if n_selected == 0:
        return
    
    target_value_per_asset = total_value / n_selected
    
    for asset in buy_candidates:
        if asset == SystemConfig.CASH_FUND:
            continue
        
        current_position = context.portfolio.positions.get(asset)
        current_value = 0
        if current_position and current_position.total_amount > 0:
            current_price = get_current_data()[asset].last_price
            current_value = current_position.total_amount * current_price
        
        if abs(current_value - target_value_per_asset) > 1000:
            asset_name = get_asset_display_name(asset)
            order_target_value(asset, target_value_per_asset)
            if target_value_per_asset > current_value:
                print(f"✅ 买入 {asset_name}【{asset}】 目标市值: ¥{target_value_per_asset:.2f}")
            else:
                print(f"🔁 调整 {asset_name}【{asset}】 目标市值: ¥{target_value_per_asset:.2f}")


# ========================================================
# 现金管理（风险自适应）
# ========================================================
def handle_cash_fund(context):
    """收盘前现金管理：根据风险等级调整现金占比"""
    
    risk_level = portfolio.current_risk_level
    cash_fund = SystemConfig.CASH_FUND
    asset_name = get_asset_display_name(cash_fund)
    total_value = context.portfolio.total_value
    
    # 设置货币基金费率
    set_order_cost(OrderCost(close_tax=0, open_commission=0, 
        close_commission=0, min_commission=0), type='fund')
    
    if risk_level >= 2:
        # 高风险：全部现金
        target_value = total_value
        order_target_value(cash_fund, target_value)
        print(f"💰 高风险(等级{risk_level})，全部配置现金基金 {asset_name}: ¥{target_value:.2f}")
        
    elif risk_level == 1:
        # 中等风险：现金占 1/(模型资产数+1)
        n_assets = len(portfolio.selected_assets) + 1
        target_value = total_value / n_assets if n_assets > 0 else total_value
        order_target_value(cash_fund, target_value)
        print(f"💰 中等风险(等级{risk_level})，部分现金 {asset_name}: ¥{target_value:.2f}")
        
    else:
        # 低风险：如果模型选了现金基金才配置
        if SystemConfig.CASH_FUND in portfolio.selected_assets:
            n_selected = len(portfolio.selected_assets)
            target_value = total_value / n_selected if n_selected > 0 else 0
            order_target_value(cash_fund, target_value)
            print(f"💰 低风险(等级{risk_level})，现金 {asset_name}: ¥{target_value:.2f}")


# ========================================================
# 代码加载完成
# ========================================================
print("✅ 多因子机器学习ETF轮动策略 v3 (融合版) 加载完成！")
print("   融合特性: 上市状态检查 + MarketRiskMonitor风控 + 行业宽度 + 风险自适应仓位")
print("   动态候选池: 增量→成长池(10只) / 存量→防御池(8只)，根据市场环境+风险自动切换")