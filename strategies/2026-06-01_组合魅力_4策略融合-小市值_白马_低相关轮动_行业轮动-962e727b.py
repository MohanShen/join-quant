# Clone from JoinQuant
# postId: 962e727ba0a1908b77ac9c92753f8497
# backtestId: 80900e81ef5046649ec57fe553a2ec92
# title: 【组合魅力】4策略融合-小市值/白马/低相关轮动/行业轮动

enable_profile()
from jqdata import *
from jqmt import *
from functools import wraps
import numpy as np
import pandas as pd
import datetime
import math
import gc  
import re

# ==================== 行业关键词映射 (模型2引入) ====================
INDUSTRY_KEYWORDS = {
    '芯片': ['芯片'], '半导体': ['半导体'], '集成电路': ['集成电路'], '电子': ['电子'],
    '创新药': ['创新药'], '疫苗': ['疫苗'], '医疗器械': ['医疗器械'], '生物': ['生物'], '医药': ['医药'], '医疗': ['医疗'],
    '光伏': ['光伏'], '风电': ['风电'], '锂电': ['锂电'], '新能车': ['新能车'], '新能源': ['新能源'], '碳中和': ['碳中和'],
    '白酒': ['白酒'], '食品': ['食品'], '饮料': ['饮料'], '家电': ['家电'], '旅游': ['旅游'], '免税': ['免税'], '消费': ['消费'],
    '航天': ['航天'], '航空': ['航空'], '军工': ['军工'], '国防': ['国防'],
    '银行': ['银行'], '证券': ['证券', '券商'], '保险': ['保险'], '信托': ['信托'], '金融': ['金融'],
    '稀土': ['稀土'], '有色': ['有色'], '钢铁': ['钢铁'], '煤炭': ['煤炭'], '化工': ['化工'], '建材': ['建材'],
    'AI': ['AI', '人工智能'], '互联网': ['互联网'], '软件': ['软件'], '传媒': ['传媒'], '游戏': ['游戏'], '通信': ['通信'], '5G': ['5G'], '计算机': ['计算机'], '科技': ['科技'],
    '养殖': ['养殖'], '畜牧': ['畜牧'], '饲料': ['饲料'], '农林': ['农林'], '农业': ['农业'],
    '房地产': ['房地产'], '建筑': ['建筑'], '工程': ['工程'], '基建': ['基建'],
    '环保': ['环保'], '环境': ['环境'], '水务': ['水务'],
    '黄金': ['黄金'], '白银': ['白银'], '原油': ['原油'], '豆粕': ['豆粕'], '商品': ['商品'],
    'H股': ['H股'], '恒生': ['恒生'], '港股': ['港股'], '中概股': ['中概股'],
    '纳指': ['纳指'], '标普': ['标普'], '道琼斯': ['道琼斯'], '德国': ['德国'], '日经': ['日经'], '沙特': ['沙特']
}

# 预编译正则表达式以提高匹配效率
INDUSTRY_PATTERNS = {industry: [re.compile(kw) for kw in keywords] 
                    for industry, keywords in INDUSTRY_KEYWORDS.items()}

# ==================== 初始化函数 ====================
def initialize(context):
    """初始化函数，设定基准等"""
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('order', 'error')
    
    # 设置交易费用和滑点
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001, close_commission=0.0001, close_today_commission=0.0001, min_commission=5), type="fund")
    
    # 设置四个子账户
    set_subportfolios([
        SubPortfolioConfig(cash=50000, type='stock'),  # 策略1: 低相关性ETF轮动
        SubPortfolioConfig(cash=30000, type='stock'),  # 策略2: 温度白马
        SubPortfolioConfig(cash=50000, type='stock'),  # 策略3: 存量搅屎棍小市值
        SubPortfolioConfig(cash=50000, type='stock')   # 策略4: 动态行业ETF轮动
    ])
    
    # 初始化全局运行天数计数器
    g.run_days = 0
    
    # 初始化各策略全局变量
    init_strategies(context)
    
    # 设置定时任务
    setup_schedule(context)
    
    # 初始化子策略收益记录
    init_sub_strategy_records(context)

def init_sub_strategy_records(context):
    """初始化子策略收益记录"""
    # 记录每个子策略的初始资金和每日收益
    g.sub_strategy_records = {
        'strategy1': {
            'name': 'S1_低相关ETF',
            'initial_cash': 50000,  
            'daily_values': [],
            'daily_dates': [],
            'daily_returns': []
        },
        'strategy2': {
            'name': 'S2_温度白马',
            'initial_cash': 30000,  
            'daily_values': [],
            'daily_dates': [],
            'daily_returns': []
        },
        'strategy3': {
            'name': 'S3_小市值',
            'initial_cash': 50000,  
            'daily_values': [],
            'daily_dates': [],
            'daily_returns': []
        },
        'strategy4': {
            'name': 'S4_动态ETF',
            'initial_cash': 50000,  
            'daily_values': [],
            'daily_dates': [],
            'daily_returns': []
        }
    }


def init_strategies(context):
    """初始化各策略参数"""
    # ========== 策略1: 低相关性ETF轮动 ==========
    g.etf_strategy = {
        'name': '低相关性ETF轮动',
        'pindex': 0, 
        'etf_pool': ["159915.XSHE", "518880.XSHG", "513100.XSHG", "511220.XSHG"],
        'lookback_days': 25,
        'holdings_num': 1,
        'min_score_threshold': 0.0,
        'max_score_threshold': 6.0,
        'stop_loss': 0.92,
        'use_atr_stop_loss': True,
        'atr_period': 14,
        'atr_multiplier': 2.5,
        'atr_trailing_stop': True,
        'atr_smoothing': 3,
        'min_money': 4000,
        'position_highs': {},
        'position_stop_prices': {},
        'yesterday_HL_list': [],
        'today_limitup_stocks': [],
        'today_limitdown_stocks': []
    }
    
    # ========== 策略2: 温度白马 ==========
    g.temp_strategy = {
        'name': '温度白马',
        'pindex': 1,
        'config': type('Config', (), {
            'BENCHMARK': '000300.XSHG',
            'BUY_STOCK_COUNT': 3,
            'STOCK_SCREENING_TIME': '09:40',
            'SELL_TIME': '09:50',
            'BUY_TIME': '10:33',
            'REBALANCE_DAY': 3,
            'MARKET_HEIGHT_COLD_THRESHOLD': 0.2,
            'MARKET_HEIGHT_HOT_THRESHOLD': 0.9,
            'MARKET_HEIGHT_DELTA_THRESHOLD': -0.5,
            'MARKET_HEIGHT_2_THRESHOLD': 1.3,
            'MOMENTUM_DAYS': 25,
            'MOMENTUM_LOWER_LIMIT': -1.0,
            'MOMENTUM_UPPER_LIMIT': 10.5,
            'MARKET_WINDOW': 220,
            'SHORT_MA_DAYS': 5,
            'LONG_MA_DAYS': 60,
            'MIN_LISTED_DAYS': 365,
            'MAX_PRICE_RATIO': 0.95,
            'STOCK_COMMISSION': 0.0000875,
            'STOCK_TAX': 0.001,
            'MIN_COMMISSION': 0.01,
            'SLIPPAGE': 0.01
        })(),
        'check_out_lists': [],
        'market_height': 0.0,
        'market_height_2': 0.0,
        'market_temperature': "warm",
        'first_run': True,
        'immediate_rebalance_done': False
    }
    
    # ========== 策略3: 存量搅屎棍小市值 ==========
    g.small_strategy = {
        'name': '存量搅屎棍小市值',
        'pindex': 2, 
        'filter_roe': 0.15,
        'filter_roa': 0.10,
        'filter_market_cap_min': 5,
        'filter_market_cap_max': 300,
        'max_stock_price': 30,
        'quality_retention_ratio': 0.5,
        'min_listed_days': 60,
        'avg_money_threshold': 20000000,
        'avoid_industries': ['801780', '801050', '801950', '801040'],
        'industry_width_threshold': 1,
        'market_bias_lookback': 20,
        'market_env_ma_window': 20,
        'market_env_slope_window': 5,
        'market_env_change_threshold': 0.1,
        'market_env_bank_threshold': 0.9,
        'trade_weekday': 1,
        'limitup_stop_time': '14:30',
        'max_position_count': 10,
        'yesterday_HL_list': [],
        'reason_to_sell': '',
        'not_buy_again': [],
        'limitup_sold_today': [],
        'today_limitup_stocks': [],
        'today_limitdown_stocks': [],
        'initial_total_value': 0,
        'position_size': 0,
        'first_run': True,
        'market_width_value': 0,
        'risk_flag': False,
        'market_environment': None,
        'days': 0,
        'stocks': [],
        'SW1': {
            '801010': '农林牧渔', '801020': '采掘', '801030': '化工', '801040': '钢铁',
            '801050': '有色金属', '801080': '电子', '801110': '家用电器', '801120': '食品饮料',
            '801130': '纺织服装', '801140': '轻工制造', '801150': '医药生物', '801160': '公用事业',
            '801170': '交通运输', '801180': '房地产', '801200': '商业贸易', '801210': '休闲服务',
            '801230': '综合', '801710': '建筑材料', '801720': '建筑装饰', '801730': '电气设备',
            '801740': '国防军工', '801750': '计算机', '801760': '传媒', '801770': '通信',
            '801780': '银行', '801790': '非银金融', '801880': '汽车', '801890': '机械设备',
            '801950': '煤炭', '801960': '石油石化', '801970': '环保', '801980': '美容护理'
        }
    }
    
    # ========== 策略4: 动态行业ETF轮动 (模型2) ==========
    g.dynamic_etf_strategy = {
        'name': '动态行业ETF轮动',
        'pindex': 3,
        'fixed_etf_pool': [
            '518880.XSHG', '159980.XSHE', '159985.XSHE', '159981.XSHE', '501018.XSHG',
            '511090.XSHG', '159941.XSHE', '159509.XSHE', '513520.XSHG', '513030.XSHG',
            '510180.XSHG', '159915.XSHE', '588220.XSHG', '562500.XSHG', '588170.XSHG',
            '159837.XSHE', '159825.XSHE', '562570.XSHG', '512170.XSHG', '588200.XSHG',
            '512400.XSHG', '512000.XSHG', '512660.XSHG', '512010.XSHG', '512100.XSHG',
            '512690.XSHG', '512200.XSHG', '512980.XSHG', '512760.XSHG', '512910.XSHG',
            '512900.XSHG', '512330.XSHG', '512360.XSHG', '512500.XSHG', '512310.XSHG',
            '513130.XSHG', '513690.XSHG', '515650.XSHG', '512290.XSHG', '159819.XSHE',
            '159851.XSHE', '515030.XSHG', '159516.XSHE', '516160.XSHG', '515400.XSHG',
            '515700.XSHG', '561170.XSHG', '510410.XSHG', '512710.XSHG', '159692.XSHE',
            '512480.XSHG', '561330.XSHG', '515250.XSHG', '516510.XSHG', '562800.XSHG',
            '588790.XSHG', '515050.XSHG', '159995.XSHE', '159273.XSHE', '159227.XSHE',
            '159755.XSHE', '516910.XSHG', '515790.XSHG', '515920.XSHG', '515000.XSHG',
            '560980.XSHG', '159141.XSHE', '159326.XSHE', '560800.XSHE', '159108.XSHE',
            '159368.XSHE', '515880.XSHG', '159992.XSHE', '515230.XSHG', '563380.XSHG',
            '560280.XSHG', '516150.XSHG', '561380.XSHG', '562920.XSHG', '560880.XSHG',
            '159792.XSHE', '516500.XSHG', '159275.XSHE', '512880.XSHG', '513050.XSHG',
            '159530.XSHE', '159667.XSHE', '159638.XSHE', '159550.XSHE', '159378.XSHE',
            '161226.XSHE', '517520.XSHG', '513100.XSHG', '513300.XSHG', '513400.XSHG',
            '159529.XSHE', '159329.XSHE', '513090.XSHG', '513120.XSHG', '159206.XSHE',
            '159218.XSHE', '159565.XSHE', '159363.XSHE', '159786.XSHE', '159890.XSHE',
            '159732.XSHE', '159852.XSHE', '159869.XSHE', '516780.XSHG', '159928.XSHE',
            '515170.XSHG', '159611.XSHE', '159766.XSHE', '515220.XSHG', '159865.XSHE',
            '560860.XSHG', '510050.XSHG', '510300.XSHG', '159922.XSHE', '159531.XSHE',
            '588080.XSHG', '588380.XSHG', '160211.XSHE', '512800.XSHG', '510880.XSHG'
        ],
        'dynamic_etf_pool': [],
        'holdings_num': 1,
        'min_money': 4000,
        'lookback_days': 25,
        'min_score_threshold': 0,
        'max_score_threshold': 5,
        'enable_r2_filter': True,
        'r2_threshold': 0.4,
        'enable_volume_check': True,
        'volume_lookback': 5,
        'volume_threshold': 1.0,
        'enable_loss_filter': True,
        'loss': 0.97,
        'use_fixed_stop_loss': True,
        'fixedStopLossThreshold': 0.95,
        'target_etfs_list': []
    }

def setup_schedule(context):
    """设置定时任务"""
    # 策略1: ETF轮动
    run_daily(etf_check_positions, '09:45')
    run_daily(etf_check_atr_stop_loss, '10:31')
    run_daily(etf_sell_trade, '14:20')
    run_daily(etf_buy_trade, '14:29')
    
    # 策略2: 温度白马
    run_monthly(temp_get_stock_list, 
                g.temp_strategy['config'].REBALANCE_DAY, 
                time=g.temp_strategy['config'].STOCK_SCREENING_TIME)
    run_monthly(temp_sell_stocks, 
                g.temp_strategy['config'].REBALANCE_DAY, 
                time=g.temp_strategy['config'].SELL_TIME)
    run_monthly(temp_buy_stocks, 
                g.temp_strategy['config'].REBALANCE_DAY, 
                time=g.temp_strategy['config'].BUY_TIME)
    run_daily(temp_check_immediate_rebalance, '13:00')
    
    # 策略3: 存量搅屎棍小市值
    run_daily(small_iUpdate, 'before_open')
    run_daily(small_iTrader, '10:00')
    run_daily(small_check_limit_up, g.small_strategy['limitup_stop_time'])
    run_daily(small_iReport, 'after_close')
    
    # 策略4: 动态行业ETF轮动
    run_daily(dynamic_update_sector_pool, time='09:00')
    run_daily(dynamic_check_positions, time='09:10')
    run_daily(dynamic_etf_sell_trade, time='13:10')
    run_daily(dynamic_etf_buy_trade, time='13:11')
    
    # 策略4: 分钟级止损
    for hour in range(9, 15):
        for minute in range(0, 60):
            current_time = "%02d:%02d" % (hour, minute)
            if ('09:27' < current_time < '11:30') or ('13:00' < current_time < '14:57'):
                run_daily(dynamic_minute_level_stop_loss, time=current_time)
    
    # 每日收盘后记录收益
    run_daily(record_daily_performance, 'after_close')
    
    # 每日收盘后执行内存清理 (最后执行)
    run_daily(daily_memory_cleanup, 'after_close')

# ==================== 收益记录函数 ====================
def record_daily_performance(context):
    """记录每日各子策略收益"""
    try:
        # 更新全局运行天数
        g.run_days += 1
        
        # 获取当前日期
        current_date = context.current_dt.date()
        
        # 准备记录数据字典
        records_to_log = {}
        
        # 记录各子策略收益
        for i, strategy_key in enumerate(['strategy1', 'strategy2', 'strategy3', 'strategy4']):
            sub_portfolio = context.subportfolios[i]
            strategy_info = g.sub_strategy_records[strategy_key]
            
            initial_cash = strategy_info['initial_cash']
            current_value = sub_portfolio.total_value
            
            # 记录每日总资产
            strategy_info['daily_values'].append(current_value)
            strategy_info['daily_dates'].append(current_date)
            
            # 计算累计收益率 (百分比)
            cumulative_return = (current_value / initial_cash - 1) * 100
            
            # 记录每日收益率
            strategy_info['daily_returns'].append(cumulative_return)
            
            # 添加到记录字典
            records_to_log[strategy_info['name']] = cumulative_return
            
            # 内存优化：限制历史数据长度，仅保留最近252个交易日
            MAX_HISTORY = 252
            if len(strategy_info['daily_values']) > MAX_HISTORY:
                strategy_info['daily_values'] = strategy_info['daily_values'][-MAX_HISTORY:]
                strategy_info['daily_dates'] = strategy_info['daily_dates'][-MAX_HISTORY:]
                strategy_info['daily_returns'] = strategy_info['daily_returns'][-MAX_HISTORY:]
        
        # 使用 record 函数记录数据，这将显示在回测页面的图表中
        record(**records_to_log)
        
        # 每周五输出详细日志报告
        if context.current_dt.weekday() == 4:  # 周五
            log_performance_summary(context)
            
    except Exception as e:
        log.error(f"记录每日收益时出错: {e}")

def log_performance_summary(context):
    """输出收益汇总报告"""
    log.info("=" * 60)
    log.info("📊 子策略收益汇总报告")
    log.info("=" * 60)
    
    # 计算总收益
    total_initial = 50000 + 50000 + 50000 + 30000  # 180000
    total_current = sum([context.subportfolios[i].total_value for i in range(4)])
    total_return = (total_current / total_initial - 1) * 100
    
    log.info(f"💰 总资金: {total_initial:,.0f}元 → {total_current:,.0f}元, 总收益率: {total_return:.2f}%")
    log.info("-" * 60)
    
    # 各子策略收益
    for i, strategy_key in enumerate(['strategy1', 'strategy2', 'strategy3', 'strategy4']):
        sub_portfolio = context.subportfolios[i]
        strategy_info = g.sub_strategy_records[strategy_key]
        
        initial_cash = strategy_info['initial_cash']
        current_value = sub_portfolio.total_value
        total_return = (current_value / initial_cash - 1) * 100
        
        # 使用全局运行天数计算年化收益
        days_count = g.run_days
        annualized_return = ((1 + total_return/100) ** (252/days_count) - 1) * 100 if days_count > 0 else 0
        
        log.info(f"📈 {strategy_info['name']}:")
        log.info(f"   初始资金: {initial_cash:,.0f}元, 当前价值: {current_value:,.0f}元")
        log.info(f"   累计收益: {total_return:.2f}%, 年化收益: {annualized_return:.2f}%")
        
        # 如果有持仓，显示持仓信息
        if sub_portfolio.positions:
            log.info(f"   持仓数量: {len(sub_portfolio.positions)}只")
            for security in sub_portfolio.positions:
                position = sub_portfolio.positions[security]
                security_name = get_security_name(security)
                position_return = (position.price / position.avg_cost - 1) * 100 if position.avg_cost > 0 else 0
                log.info(f"     {security} {security_name}: {position.total_amount}股, 成本:{position.avg_cost:.2f}, 现价:{position.price:.2f}, 收益率:{position_return:.2f}%")
        else:
            log.info("   当前无持仓")
        
        log.info("-" * 60)
    
    log.info("=" * 60)

# ==================== 内存管理函数 ====================
def daily_memory_cleanup(context):
    """每日收盘后执行内存清理"""
    try:
        # 1. 清理全局缓存
        if hasattr(g, 'index_stocks_cache'):
            g.index_stocks_cache = {}
        if hasattr(g, 'volume_cache'):
            g.volume_cache = {}
        if hasattr(g, 'price_cache'):
            g.price_cache = {}
        if hasattr(g, 'fund_info_cache'):
            g.fund_info_cache = {}
        if hasattr(g, 'security_info_cache'):
            g.security_info_cache = {}
            
        # 2. 强制执行垃圾回收
        # 收盘后释放当日产生的临时对象
        collected = gc.collect()
        log.info(f"🧹 每日内存清理完成，回收对象数: {collected}")
        
    except Exception as e:
        log.error(f"内存清理出错: {e}")

# ==================== 策略1: 低相关性ETF轮动 ====================
def etf_check_positions(context):
    """ETF策略持仓检查"""
    strategy = g.etf_strategy
    for security in context.subportfolios[strategy['pindex']].positions:
        position = context.subportfolios[strategy['pindex']].positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"[{strategy['name']}] 持仓: {security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}")

def etf_check_atr_stop_loss(context):
    """ETF策略ATR止损检查"""
    strategy = g.etf_strategy
    if not strategy['use_atr_stop_loss']:
        return
    
    for security in list(context.subportfolios[strategy['pindex']].positions.keys()):
        if security not in strategy['etf_pool']:
            continue
            
        position = context.subportfolios[strategy['pindex']].positions[security]
        if position.total_amount <= 0:
            continue
        
        try:
            current_price = get_previous_minute_price(security, context)
            if current_price <= 0:
                continue
            
            cost_price = position.avg_cost
            current_atr, success, _ = calculate_smoothed_atr(security, strategy)
            
            if not success:
                continue
            
            if security not in strategy['position_highs']:
                strategy['position_highs'][security] = current_price
            else:
                strategy['position_highs'][security] = max(strategy['position_highs'][security], current_price)
            
            position_high = strategy['position_highs'][security]
            
            if strategy['atr_trailing_stop']:
                atr_stop_price = position_high - strategy['atr_multiplier'] * current_atr
            else:
                atr_stop_price = cost_price - strategy['atr_multiplier'] * current_atr
            
            strategy['position_stop_prices'][security] = atr_stop_price
            
            if current_price <= atr_stop_price:
                success = etf_smart_order_target_value(security, 0, context, strategy)
                if success:
                    security_name = get_security_name(security)
                    loss_percent = (current_price/cost_price - 1) * 100
                    atr_stop_type = "跟踪" if strategy['atr_trailing_stop'] else "固定"
                    log.info(f"[{strategy['name']}] ATR止损卖出: {security} {security_name}，亏损: {loss_percent:.2f}%")
                    
                    if security in strategy['position_highs']:
                        del strategy['position_highs'][security]
                    if security in strategy['position_stop_prices']:
                        del strategy['position_stop_prices'][security]
        
        except Exception as e:
            log.warn(f"[{strategy['name']}] ATR止损检查出错: {e}")

def etf_sell_trade(context):
    """ETF策略卖出交易"""
    strategy = g.etf_strategy
    log.info(f"[{strategy['name']}] 卖出交易开始")
    
    ranked_etfs = etf_get_ranked_etfs(context, strategy)
    target_etf = None
    if ranked_etfs and ranked_etfs[0]['score'] >= strategy['min_score_threshold']:
        target_etf = ranked_etfs[0]['etf']
    
    for security in list(context.subportfolios[strategy['pindex']].positions.keys()):
        position = context.subportfolios[strategy['pindex']].positions[security]
        if security in strategy['etf_pool'] and position.total_amount > 0:
            current_price = get_previous_minute_price(security, context)
            cost_price = position.avg_cost
            
            if current_price <= cost_price * strategy['stop_loss']:
                success = etf_smart_order_target_value(security, 0, context, strategy)
                if success:
                    security_name = get_security_name(security)
                    loss_percent = (current_price/cost_price-1)*100
                    log.info(f"[{strategy['name']}] 固定止损卖出: {security} {security_name}，亏损: {loss_percent:.2f}%")
    
    target_etfs_set = set([target_etf] if target_etf else [])
    current_positions = set(context.subportfolios[strategy['pindex']].positions.keys())
    
    for security in current_positions:
        if security in strategy['etf_pool'] and security not in target_etfs_set:
            position = context.subportfolios[strategy['pindex']].positions[security]
            if position.total_amount > 0:
                success = etf_smart_order_target_value(security, 0, context, strategy)
                if success:
                    security_name = get_security_name(security)
                    log.info(f"[{strategy['name']}] 卖出: {security} {security_name}")

def etf_buy_trade(context):
    """ETF策略买入交易"""
    strategy = g.etf_strategy
    log.info(f"[{strategy['name']}] 买入交易开始")
    
    ranked_etfs = etf_get_ranked_etfs(context, strategy)
    target_etf = None
    if ranked_etfs and ranked_etfs[0]['score'] >= strategy['min_score_threshold']:
        target_etf = ranked_etfs[0]['etf']
        top_metrics = ranked_etfs[0]
        etf_name = get_security_name(target_etf)
        log.info(f"[{strategy['name']}] 买入目标ETF: {target_etf} {etf_name}，得分: {top_metrics['score']:.4f}")
    else:
        log.info(f"[{strategy['name']}] 无符合条件的ETF")
        return
    
    total_value = context.subportfolios[strategy['pindex']].total_value
    target_value = total_value if target_etf else 0
    
    if target_etf:
        current_value = 0
        if target_etf in context.subportfolios[strategy['pindex']].positions:
            position = context.subportfolios[strategy['pindex']].positions[target_etf]
            if position.total_amount > 0:
                current_value = position.total_amount * get_previous_minute_price(target_etf, context)
        
        if abs(current_value - target_value) > target_value * 0.05 or current_value == 0:
            success = etf_smart_order_target_value(target_etf, target_value, context, strategy)
            if success:
                action = "买入" if current_value < target_value else "调仓"
                etf_name = get_security_name(target_etf)
                log.info(f"[{strategy['name']}] {action}: {target_etf} {etf_name}，目标金额: {target_value:.2f}")

def etf_smart_order_target_value(security, target_value, context, strategy):
    """ETF策略智能下单"""
    current_data = get_current_data()
    
    if current_data[security].paused:
        log.info(f"[{strategy['name']}] {security}: 停牌")
        return False
    
    current_price = get_previous_minute_price(security, context)
    if current_price == 0:
        log.info(f"[{strategy['name']}] {security}: 无法获取价格")
        return False
    
    if current_price >= current_data[security].high_limit:
        log.info(f"[{strategy['name']}] {security}: 涨停")
        return False
    
    if current_price <= current_data[security].low_limit:
        log.info(f"[{strategy['name']}] {security}: 跌停")
        return False
    
    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    
    current_position = context.subportfolios[strategy['pindex']].positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < strategy['min_money']:
        log.info(f"[{strategy['name']}] {security}: 交易金额{trade_value:.2f}小于最小额{strategy['min_money']}")
        return False
    
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"[{strategy['name']}] {security}: T+1限制")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)
    
    if amount_diff != 0:
        order_result = order(security, amount_diff, pindex=strategy['pindex'])
        if order_result:
            security_name = get_security_name(security)
            if amount_diff > 0:
                log.info(f"[{strategy['name']}] 买入 {security} {security_name}，数量: {amount_diff}")
                strategy['position_highs'][security] = current_price
                
                if strategy['use_atr_stop_loss']:
                    current_atr, success, _ = calculate_smoothed_atr(security, strategy)
                    if success:
                        if strategy['atr_trailing_stop']:
                            strategy['position_stop_prices'][security] = current_price - strategy['atr_multiplier'] * current_atr
                        else:
                            strategy['position_stop_prices'][security] = current_price - strategy['atr_multiplier'] * current_atr
            else:
                log.info(f"[{strategy['name']}] 卖出 {security} {security_name}，数量: {abs(amount_diff)}")
                
                if security in strategy['position_highs']:
                    del strategy['position_highs'][security]
                if security in strategy['position_stop_prices']:
                    del strategy['position_stop_prices'][security]
            
            return True
        else:
            log.warn(f"[{strategy['name']}] 下单失败: {security}")
            return False
    
    return False

def etf_get_ranked_etfs(context, strategy):
    """获取ETF排名"""
    etf_metrics = []
    for etf in strategy['etf_pool']:
        metrics = etf_calculate_momentum_metrics(etf, context, strategy)
        if metrics is not None:
            if strategy['min_score_threshold'] <= metrics['score'] <= strategy['max_score_threshold']:
                etf_metrics.append(metrics)
    
    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics

def etf_calculate_momentum_metrics(etf, context, strategy):
    """计算ETF动量得分"""
    try:
        lookback = strategy['lookback_days'] + 20
        prices = attribute_history(etf, lookback, '1d', ['close'], skip_paused=True)
        
        if len(prices) < lookback:
            return None
        
        current_price = get_previous_minute_price(etf, context)
        if current_price <= 0:
            return None
        
        close_prices = prices["close"].values
        price_series = np.append(close_prices, current_price)

        recent_days = min(strategy['lookback_days'], len(price_series) - 1)
        if recent_days >= 10:
            recent_price_series = price_series[-(recent_days+1):]
            log_prices = np.log(recent_price_series)
            y = log_prices
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            annualized_returns = math.exp(slope * 250) - 1
            
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r_squared = 1 - ss_res / ss_tot if ss_tot else 0
            
            score = annualized_returns * r_squared
            
            if len(price_series) >= 4:
                day1_ratio = price_series[-1] / price_series[-2]
                day2_ratio = price_series[-2] / price_series[-3]
                day3_ratio = price_series[-3] / price_series[-4]
                
                if min(day1_ratio, day2_ratio, day3_ratio) < 0.97:
                    score = 0
        else:
            score = 0
        
        return {
            'etf': etf,
            'score': score,
            'current_price': current_price
        }
    except Exception as e:
        log.warn(f"计算{etf}动量指标时出错: {e}")
        return None

# ==================== 策略2: 温度白马 ====================
def temp_check_immediate_rebalance(context):
    """温度白马策略立即调仓检查"""
    strategy = g.temp_strategy
    if strategy['first_run'] and not strategy['immediate_rebalance_done']:
        log.info(f"[{strategy['name']}] 首次运行，执行立即调仓")
        temp_execute_immediate_rebalance(context, strategy)
        strategy['immediate_rebalance_done'] = True
        strategy['first_run'] = False

def temp_execute_immediate_rebalance(context, strategy):
    """温度白马策略立即调仓执行"""
    try:
        temp_get_stock_list(context)
        temp_sell_stocks(context)
        temp_buy_stocks(context)
        log.info(f"[{strategy['name']}] 立即调仓完成")
    except Exception as e:
        log.error(f"[{strategy['name']}] 立即调仓失败: {str(e)}")

def temp_get_stock_list(context):
    """温度白马策略获取股票池"""
    strategy = g.temp_strategy
    log.info(f"[{strategy['name']}] 开始筛选股票池")
    
    strategy['check_out_lists'] = []
    current_data = get_current_data()
    all_stocks = get_index_stocks(strategy['config'].BENCHMARK)
    
    all_stocks = temp_preliminary_screening(all_stocks, current_data, context, strategy)
    all_stocks = temp_filter_new_stock(context, all_stocks, strategy)
    temp_calc_market_temperature(context, strategy)
    
    if all_stocks:
        strategy['check_out_lists'] = temp_screen_stocks_by_temperature(all_stocks, strategy)
    
    if strategy['check_out_lists']:
        strategy['check_out_lists'] = temp_momentum_filter(strategy['check_out_lists'], strategy)
    
    if strategy['check_out_lists']:
        log.info(f"[{strategy['name']}] 筛选出{len(strategy['check_out_lists'])}只股票")
        for stock in strategy['check_out_lists']:
            position_flag = "持仓" if stock in context.subportfolios[strategy['pindex']].positions else ""
            log.info(f"  {stock} {current_data[stock].name} {position_flag}")
    else:
        log.info(f"[{strategy['name']}] 股票池为空")


def temp_preliminary_screening(stock_list, current_data, context, strategy):
    """温度白马策略初步筛选"""
    filtered_stocks = []
    
    for stock in stock_list:
        stock_data = current_data[stock]
        max_price = round(context.subportfolios[strategy['pindex']].total_value * 
                         strategy['config'].MAX_PRICE_RATIO / 
                         strategy['config'].BUY_STOCK_COUNT / 100, 2)
        
        exclude_conditions = [
            stock_data.last_price > max_price,
            stock_data.day_open == stock_data.high_limit,
            stock_data.day_open == stock_data.low_limit,
            stock_data.paused,
            stock_data.is_st,
            'ST' in stock_data.name,
            '*' in stock_data.name,
            '退' in stock_data.name,
            stock.startswith('30'),
            stock.startswith('68'),
            stock.startswith('8'),
            stock.startswith('4'),
        ]
        
        if not any(exclude_conditions):
            filtered_stocks.append(stock)
    
    return filtered_stocks

def temp_filter_new_stock(context, stock_list, strategy):
    """温度白马策略过滤次新股"""
    filtered_stocks = []
    cutoff_date = context.previous_date - datetime.timedelta(days=strategy['config'].MIN_LISTED_DAYS)
    
    for stock in stock_list:
        stock_info = get_security_info(stock)
        if stock_info.start_date <= cutoff_date:
            filtered_stocks.append(stock)
    
    return filtered_stocks

def temp_calc_market_temperature(context, strategy):
    """温度白马策略计算市场温度"""
    index_data = attribute_history(
        strategy['config'].BENCHMARK, 
        strategy['config'].MARKET_WINDOW, 
        '1d', 
        ('close'), 
        df=False
    )['close']
    
    old_market_height = strategy['market_height']
    min_price = min(index_data)
    max_price = max(index_data)
    short_ma = np.mean(index_data[-strategy['config'].SHORT_MA_DAYS:])
    
    strategy['market_height'] = (short_ma - min_price) / (max_price - min_price)
    delta_market_height = old_market_height - strategy['market_height']
    
    old_market_height_2 = strategy['market_height_2']
    recent_max = max(index_data[-strategy['config'].LONG_MA_DAYS:])
    strategy['market_height_2'] = recent_max / min_price
    
    if strategy['market_height'] < strategy['config'].MARKET_HEIGHT_COLD_THRESHOLD:
        strategy['market_temperature'] = "cold"
    elif strategy['market_height'] > strategy['config'].MARKET_HEIGHT_HOT_THRESHOLD or delta_market_height < strategy['config'].MARKET_HEIGHT_DELTA_THRESHOLD:
        strategy['market_temperature'] = "hot"
    elif min(strategy['market_height_2'], old_market_height_2) > strategy['config'].MARKET_HEIGHT_2_THRESHOLD:
        strategy['market_temperature'] = "warm"
    else:
        strategy['market_temperature'] = "warm"
    
    log.info(f"[{strategy['name']}] 市场温度: {strategy['market_temperature']}")

def temp_screen_stocks_by_temperature(stock_list, strategy):
    """温度白马策略按市场温度筛选"""
    if strategy['market_temperature'] == "cold":
        return temp_screen_cold_market_stocks(stock_list, strategy)
    elif strategy['market_temperature'] == "warm":
        return temp_screen_warm_market_stocks(stock_list, strategy)
    elif strategy['market_temperature'] == "hot":
        return temp_screen_hot_market_stocks(stock_list, strategy)
    else:
        return []

def temp_screen_cold_market_stocks(stock_list, strategy):
    """冷态市场筛选"""
    q = query(
        valuation.code,
    ).filter(
        valuation.pb_ratio > 0,
        valuation.pb_ratio < 1,
        cash_flow.subtotal_operate_cash_inflow > 0,
        cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 2.0,
        indicator.inc_return > 1.5,
        indicator.inc_net_profit_year_on_year > -15,
        indicator.gross_profit_margin > 0.2,
        indicator.adjusted_profit > 2.5e8,
        income.operating_revenue > 10e8,
        income.net_profit > 2.5e8,
        valuation.code.in_(stock_list)
    ).order_by(
        (indicator.roa / valuation.pb_ratio).desc()
    ).limit(
        strategy['config'].BUY_STOCK_COUNT + 1
    )
    
    return list(get_fundamentals(q).code)

def temp_screen_warm_market_stocks(stock_list, strategy):
    """温态市场筛选"""
    q = query(
        valuation.code,
    ).filter(
        valuation.pb_ratio > 0,
        valuation.pb_ratio < 1,
        cash_flow.subtotal_operate_cash_inflow > 0,
        cash_flow.net_operate_cash_flow > 0,
        indicator.adjusted_profit > 8e7,
        income.operating_revenue > 1e9,
        income.net_profit > 8e7,
        cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 1.0,
        indicator.inc_return > 2.0,
        indicator.inc_net_profit_year_on_year > 0,
        valuation.code.in_(stock_list)
    ).order_by(
        (indicator.roa / valuation.pb_ratio).desc()
    ).limit(
        strategy['config'].BUY_STOCK_COUNT + 1
    )
    
    return list(get_fundamentals(q).code)

def temp_screen_hot_market_stocks(stock_list, strategy):
    """热态市场筛选"""
    q = query(
        valuation.code,
    ).filter(
        valuation.pb_ratio > 3,
        cash_flow.subtotal_operate_cash_inflow > 0,
        indicator.adjusted_profit > 2.5e8,
        income.operating_revenue > 1e9,
        income.net_profit > 2.5e8,
        cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 0.5,
        indicator.inc_return > 3.0,
        indicator.inc_net_profit_year_on_year > 20,
        valuation.code.in_(stock_list)
    ).order_by(
        indicator.roa.desc()
    ).limit(
        strategy['config'].BUY_STOCK_COUNT + 1
    )
    
    return list(get_fundamentals(q).code)

def temp_momentum_filter(stock_pool, strategy):
    """温度白马策略动量过滤"""
    score_list = []
    
    for stock in stock_pool:
        score_list.append(temp_momentum(stock, strategy))
    
    df = pd.DataFrame(index=stock_pool, data={'score': score_list})
    df = df.sort_values(by='score', ascending=False)
    df = df[(df['score'] > strategy['config'].MOMENTUM_LOWER_LIMIT) & 
            (df['score'] < strategy['config'].MOMENTUM_UPPER_LIMIT)]
    
    return list(df.index)

def temp_momentum(stock, strategy):
    """温度白马策略动量计算"""
    df = attribute_history(stock, strategy['config'].MOMENTUM_DAYS, '1d', ['close', 'open'], df=False)
    
    y_o = np.log(df['open'])
    y_c = np.log(df['close'])
    
    n = len(y_o)
    x = np.arange(n)
    weights = np.linspace(1, 2, n)
    
    slope_c, intercept_c = np.polyfit(x, y_c, 1, w=weights)
    slope_o, intercept_o = np.polyfit(x, y_o, 1, w=weights)
    
    slope = 0.7 * slope_c + 0.3 * slope_o
    intercept = 0.7 * intercept_c + 0.3 * intercept_o
    
    annualized_returns = math.pow(math.exp(slope), 250) - 1
    
    residuals = y_c - (slope * x + intercept)
    weighted_residuals = weights * residuals ** 2
    r_squared = 1 - (np.sum(weighted_residuals) / np.sum(weights * (y_c - np.mean(y_c)) ** 2))
    
    score = annualized_returns * r_squared
    
    return score

def temp_sell_stocks(context):
    """温度白马策略卖出"""
    strategy = g.temp_strategy
    log.info(f"[{strategy['name']}] 开始卖出操作")
    
    if not strategy['check_out_lists']:
        log.info(f"[{strategy['name']}] 股票池为空，清空所有持仓")
        for stock in context.subportfolios[strategy['pindex']].positions:
            order_target_value(stock, 0, pindex=strategy['pindex'])
        return
    
    current_data = get_current_data()
    
    for stock in list(context.subportfolios[strategy['pindex']].positions.keys()):
        in_target_list = stock in strategy['check_out_lists']
        not_limit_up = context.subportfolios[strategy['pindex']].positions[stock].price < current_data[stock].high_limit
        
        if not in_target_list and not_limit_up:
            log.info(f"[{strategy['name']}] 卖出 {stock} {current_data[stock].name}")
            order_target_value(stock, 0, pindex=strategy['pindex'])

def temp_buy_stocks(context):
    """温度白马策略买入"""
    strategy = g.temp_strategy
    log.info(f"[{strategy['name']}] 开始买入操作")
    
    if not strategy['check_out_lists']:
        log.info(f"[{strategy['name']}] 股票池为空，保持现金")
        return
    
    current_data = get_current_data()
    position_count = len(context.subportfolios[strategy['pindex']].positions)
    
    if position_count >= strategy['config'].BUY_STOCK_COUNT:
        log.info(f"[{strategy['name']}] 当前持仓{position_count}只，已达目标数量")
        return
    
    available_cash = context.subportfolios[strategy['pindex']].cash * 0.99
    stocks_to_buy = strategy['config'].BUY_STOCK_COUNT - position_count
    value_per_stock = available_cash / stocks_to_buy
    
    bought_count = 0
    for stock in strategy['check_out_lists']:
        if stock not in context.subportfolios[strategy['pindex']].positions:
            not_limit_down = current_data[stock].last_price > current_data[stock].low_limit
            
            if not_limit_down:
                log.info(f"[{strategy['name']}] 买入 {stock} {current_data[stock].name}")
                order_target_value(stock, value_per_stock, pindex=strategy['pindex'])
                bought_count += 1
                
                if len(context.subportfolios[strategy['pindex']].positions) >= strategy['config'].BUY_STOCK_COUNT:
                    break
    
    if context.subportfolios[strategy['pindex']].positions:
        log.info(f"[{strategy['name']}] 当前持仓:")
        for stock in context.subportfolios[strategy['pindex']].positions:
            position = context.subportfolios[strategy['pindex']].positions[stock]
            log.info(f"  {stock} {current_data[stock].name} {position.total_amount}股")
    else:
        log.info(f"[{strategy['name']}] 当前无持仓")

# ==================== 策略3: 存量搅屎棍小市值 ====================
def small_iUpdate(context):
    """小市值策略开盘前更新"""
    strategy = g.small_strategy
    strategy['days'] = strategy['days'] + 1
    
    if strategy['days'] == 1:
        log.info(f"[{strategy['name']}] 第1天运行，日期: {context.current_dt}")
        if strategy['first_run']:
            log.info(f"[{strategy['name']}] 将在10:00执行首次选股交易")
    
    if context.current_dt.weekday() < 5:
        small_update_yesterday_limit_up(context, strategy)
    
    strategy['today_limitup_stocks'] = []
    strategy['today_limitdown_stocks'] = []

def small_iTrader(context):
    """小市值策略交易"""
    strategy = g.small_strategy
    
    if strategy['first_run']:
        small_first_run_trader(context, strategy)
        return
    
    if context.current_dt.weekday() != strategy['trade_weekday']:
        return
    
    small_get_today_limit_stocks(context, strategy)
    risk_detected = small_industry_macro_control(context, strategy)
    
    if risk_detected:
        small_perform_risk_control(context, strategy)
        strategy['stocks'] = []
        return
    
    strategy['initial_total_value'] = context.subportfolios[strategy['pindex']].total_value
    strategy['position_size'] = strategy['initial_total_value'] / strategy['max_position_count']
    
    max_select_count = min(strategy['max_position_count'] * 1.5, strategy['max_position_count'])
    strategy['stocks'] = small_choice_small(context, max_select_count, strategy)
    
    cdata = get_current_data()
    
    for s in list(context.subportfolios[strategy['pindex']].positions.keys()):
        if cdata[s].paused:
            continue
        
        can_sell, reason = small_check_stock_trading_conditions(context, s, is_buy=False, strategy=strategy)
        
        if s not in strategy['stocks'] and s not in strategy['yesterday_HL_list']:
            if can_sell:
                order_target(s, 0, MarketOrderStyle(0.99 * cdata[s].last_price), pindex=strategy['pindex'])
                log.info(f"[{strategy['name']}] 卖出 {s}: {reason}")
    
    strategy['not_buy_again'] = []
    strategy['limitup_sold_today'] = []
    
    available_cash = context.subportfolios[strategy['pindex']].available_cash
    bought_count = 0
    
    for s in strategy['stocks']:
        if available_cash < 100 * cdata[s].last_price:
            break
            
        if cdata[s].paused:
            continue
        
        can_buy, reason = small_check_stock_trading_conditions(context, s, is_buy=True, strategy=strategy)
        
        if not can_buy:
            log.info(f"[{strategy['name']}] 跳过买入 {s}: {reason}")
            continue
            
        if s in context.subportfolios[strategy['pindex']].positions:
            current_value = context.subportfolios[strategy['pindex']].positions[s].value
            buy_value = max(0, strategy['position_size'] - current_value)
        else:
            buy_value = strategy['position_size']
        
        buy_value = min(buy_value, available_cash)
        
        min_cost = 100 * cdata[s].last_price
        if buy_value < min_cost:
            continue
            
        if buy_value > 0:
            order_value(s, buy_value, MarketOrderStyle(1.01 * cdata[s].last_price), pindex=strategy['pindex'])
            available_cash -= buy_value
            strategy['not_buy_again'].append(s)
            bought_count += 1
            log.info(f"[{strategy['name']}] 买入 {s}: 买入金额{buy_value:.2f}, {reason}")
    
    log.info(f"[{strategy['name']}] 本次买入: 计划{len(strategy['stocks'])}只, 实际买入{bought_count}只")

def small_first_run_trader(context, strategy):
    """小市值策略首次运行交易"""
    log.info(f"[{strategy['name']}] 首次运行，强制选股交易")
    
    small_get_today_limit_stocks(context, strategy)
    risk_detected = small_industry_macro_control(context, strategy)
    
    if risk_detected:
        log.warning(f"[{strategy['name']}] 首次运行检测到风险，执行风控清仓")
        small_perform_risk_control(context, strategy)
        strategy['stocks'] = []
        strategy['first_run'] = False
        return
    
    strategy['initial_total_value'] = context.subportfolios[strategy['pindex']].total_value
    strategy['position_size'] = strategy['initial_total_value'] / strategy['max_position_count']
    
    max_select_count = min(strategy['max_position_count'] * 1.5, strategy['max_position_count'])
    strategy['stocks'] = small_choice_small(context, max_select_count, strategy)
    
    if not strategy['stocks']:
        log.warning(f"[{strategy['name']}] 首次运行选股结果为空")
        strategy['first_run'] = False
        return
    
    cdata = get_current_data()
    
    for s in list(context.subportfolios[strategy['pindex']].positions.keys()):
        if not cdata[s].paused:
            order_target(s, 0, MarketOrderStyle(0.99 * cdata[s].last_price), pindex=strategy['pindex'])
            log.info(f"[{strategy['name']}] 首次运行清空持仓: {s}")
    
    strategy['not_buy_again'] = []
    strategy['limitup_sold_today'] = []
    
    available_cash = context.subportfolios[strategy['pindex']].available_cash
    bought_count = 0
    
    for s in strategy['stocks']:
        if available_cash < 100 * cdata[s].last_price:
            break
            
        if cdata[s].paused:
            continue
        
        can_buy, reason = small_check_stock_trading_conditions(context, s, is_buy=True, strategy=strategy)
        
        if not can_buy:
            log.info(f"[{strategy['name']}] 首次运行跳过买入 {s}: {reason}")
            continue
            
        buy_value = strategy['position_size']
        buy_value = min(buy_value, available_cash)
        
        min_cost = 100 * cdata[s].last_price
        if buy_value < min_cost:
            continue
            
        if buy_value > 0:
            order_value(s, buy_value, MarketOrderStyle(1.01 * cdata[s].last_price), pindex=strategy['pindex'])
            available_cash -= buy_value
            strategy['not_buy_again'].append(s)
            bought_count += 1
            log.info(f"[{strategy['name']}] 首次运行买入 {s}: 买入金额{buy_value:.2f}, {reason}")
    
    log.info(f"[{strategy['name']}] 首次运行完成: 计划{len(strategy['stocks'])}只, 实际买入{bought_count}只")
    strategy['first_run'] = False

def small_iReport(context):
    """小市值策略收盘后报告"""
    strategy = g.small_strategy
    
    if not hasattr(strategy, 'initial_total_value') or strategy['initial_total_value'] <= 0:
        strategy['initial_total_value'] = context.subportfolios[strategy['pindex']].total_value
        
    if strategy['position_size'] <= 0:
        strategy['position_size'] = strategy['initial_total_value'] / strategy['max_position_count']
        
    cdata = get_current_data()
    tvalue = context.subportfolios[strategy['pindex']].total_value
    
    total_profit = int(tvalue - context.subportfolios[strategy['pindex']].inout_cash)
    base_diff = int(tvalue - strategy['initial_total_value'])
    base_ratio = 100 * (tvalue - strategy['initial_total_value']) / strategy['initial_total_value'] if strategy['initial_total_value'] > 0 else 0
    
    ptable = pd.DataFrame(columns=['数量', '价值', '权重(%)', '基准(%)', '名称', '状态'])
    
    for s in context.subportfolios[strategy['pindex']].positions:
        ps = context.subportfolios[strategy['pindex']].positions[s]
        position_ratio = 100 * ps.value / tvalue
        base_ratio_val = 100 * ps.value / strategy['position_size'] if strategy['position_size'] > 0 else 0
        
        status = "正常"
        if s in strategy['yesterday_HL_list']:
            status = "昨日涨停"
        elif cdata[s].last_price == cdata[s].high_limit:
            status = "今日涨停"
        elif cdata[s].last_price == cdata[s].low_limit:
            status = "今日跌停"
        
        ptable.loc[s] = [
            ps.total_amount,
            int(ps.value),
            round(position_ratio, 2),
            round(base_ratio_val, 2),
            cdata[s].name,
            status
        ]
    
    ptable = ptable.sort_values(by='权重(%)', ascending=False)
    log.info(f"[{strategy['name']}] 持仓明细:\n{ptable}")
    
    log.info(f"[{strategy['name']}] 总盈亏:{total_profit},基准盈亏:{base_diff}({base_ratio:.2f}%)")
    log.info(f"[{strategy['name']}] 总资产:{tvalue/10000:.2f}万(初始{strategy['initial_total_value']/10000:.2f}万),可用现金:{context.subportfolios[strategy['pindex']].available_cash/10000:.2f}万")
    
    if strategy['first_run']:
        log.info(f"[{strategy['name']}] 首次运行状态: 等待首次选股交易")
    else:
        log.info(f"[{strategy['name']}] 首次运行状态: 已完成")
    
    if strategy['yesterday_HL_list']:
        log.info(f"[{strategy['name']}] 昨日涨停持仓:{[f'{s}({cdata[s].name})' for s in strategy['yesterday_HL_list']]}")
    
    if strategy['today_limitup_stocks']:
        log.info(f"[{strategy['name']}] 今日涨停开盘:{len(strategy['today_limitup_stocks'])}只")
    if strategy['today_limitdown_stocks']:
        log.info(f"[{strategy['name']}] 今日跌停开盘:{len(strategy['today_limitdown_stocks'])}只")
    
    status_title = "风控状态"
    if strategy['risk_flag']:
        status_text = f"{status_title}风险状态:触发,规避行业:{strategy['avoid_industries']}"
    else:
        status_text = f"{status_title}风险状态:正常"
    
    log.info(f"[{strategy['name']}] {status_text}市场环境:{strategy['market_environment']},市场宽度值:{strategy['market_width_value']:.2f}%")
    
    if context.current_dt.weekday() == strategy['trade_weekday']:
        log.info(f"[{strategy['name']}] 交易执行日:总资产{strategy['initial_total_value']/10000:.2f}万,仓位{strategy['position_size']/10000:.2f}万/只,最大持仓{strategy['max_position_count']}只")

def small_get_today_limit_stocks(context, strategy):
    """小市值策略获取今日涨跌停股票"""
    strategy['today_limitup_stocks'] = []
    strategy['today_limitdown_stocks'] = []
    
    try:
        all_stocks = get_all_securities(['stock'], date=context.current_dt).index.tolist()
        batch_size = 200
        
        current_data = get_current_data()
        
        for i in range(0, len(all_stocks), batch_size):
            batch_stocks = all_stocks[i:i+batch_size]
            
            try:
                for stock in batch_stocks:
                    try:
                        if stock not in current_data:
                            continue
                        
                        stock_data = current_data[stock]
                        
                        if stock_data.paused:
                            continue
                        
                        open_price = stock_data.day_open
                        high_limit = stock_data.high_limit
                        low_limit = stock_data.low_limit
                        
                        if open_price == high_limit and open_price > 0:
                            strategy['today_limitup_stocks'].append(stock)
                        
                        if open_price == low_limit and open_price > 0:
                            strategy['today_limitdown_stocks'].append(stock)
                            
                    except:
                        continue
                        
            except Exception as e:
                log.warning(f"[{strategy['name']}] 获取涨跌停股票批次{i}出错: {e}")
                continue
        
        log.info(f"[{strategy['name']}] 今日涨停开盘股票: {len(strategy['today_limitup_stocks'])}只")
        log.info(f"[{strategy['name']}] 今日跌停开盘股票: {len(strategy['today_limitdown_stocks'])}只")
        
    except Exception as e:
        log.error(f"[{strategy['name']}] 获取今日涨跌停股票出错: {e}")

def small_check_stock_trading_conditions(context, stock, is_buy=True, strategy=None):
    """小市值策略检查股票交易条件"""
    try:
        current_data = get_current_data()
        
        if stock not in current_data:
            return False, "股票数据不存在"
        
        stock_data = current_data[stock]
        
        if stock_data.paused:
            return False, "股票停牌"
        
        current_price = stock_data.last_price
        if current_price <= 0:
            return False, "价格无效"
        
        open_price = stock_data.day_open
        high_limit = stock_data.high_limit
        low_limit = stock_data.low_limit
        
        if is_buy:
            if open_price == high_limit and open_price > 0:
                return False, "涨停开盘"
            
            if open_price == low_limit and open_price > 0:
                return False, "跌停开盘"
            
            if current_price == low_limit:
                return False, "当前跌停"
            
            if stock in strategy['today_limitup_stocks']:
                return False, "今日涨停股"
            
            if stock in strategy['today_limitdown_stocks']:
                return False, "今日跌停股"
        else:
            if current_price == high_limit:
                return False, "涨停状态"
            
            if stock in strategy['yesterday_HL_list']:
                return True, "昨日涨停股"
        
        return True, "符合交易条件"
        
    except Exception as e:
        log.error(f"[{strategy['name']}] 检查股票交易条件出错: {e}")
        return False, f"检查出错: {str(e)}"

def small_check_limit_up(context):
    """小市值策略涨停检查"""
    strategy = g.small_strategy
    if not strategy['yesterday_HL_list']:
        return
    
    cdata = get_current_data()
    sold_count = 0
    kept_count = 0
    
    for stock in strategy['yesterday_HL_list'][:]:
        if cdata[stock].paused:
            continue
            
        try:
            current_price = get_price(stock, end_date=context.current_dt, 
                                     frequency='1m', fields='close', 
                                     skip_paused=False, count=1).iloc[0, 0]
        except:
            current_price = cdata[stock].last_price
        
        if current_price < cdata[stock].high_limit - 0.001:
            can_sell, reason = small_check_stock_trading_conditions(context, stock, is_buy=False, strategy=strategy)
            
            if can_sell:
                last_price = cdata[stock].last_price
                log_price = last_price if last_price > 0 else current_price
                
                order_target(stock, 0, MarketOrderStyle(0.99 * log_price), pindex=strategy['pindex'])
                
                sold_count += 1
                strategy['yesterday_HL_list'].remove(stock)
                strategy['limitup_sold_today'].append(stock)
                log.info(f"[{strategy['name']}] 涨停打开卖出 {stock}: {reason}")
            else:
                log.info(f"[{strategy['name']}] 涨停打开但保留 {stock}: {reason}")
        else:
            kept_count += 1
            log.info(f"[{strategy['name']}] 涨停保持 {stock}: 继续持有")
    
    if sold_count > 0:
        strategy['reason_to_sell'] = 'limitup'
        small_buy_with_remaining_cash(context, sold_count, strategy)
        strategy['reason_to_sell'] = ''
    
    log.info(f"[{strategy['name']}] 涨停股检查: 总数{len(strategy['yesterday_HL_list'])+sold_count}只, 卖出{sold_count}只, 保留{kept_count}只")

def small_buy_with_remaining_cash(context, buy_num=None, strategy=None):
    """小市值策略剩余资金买入"""
    if context.current_dt.weekday() == strategy['trade_weekday']:
        return
    
    if buy_num is None:
        current_position_count = len(context.subportfolios[strategy['pindex']].positions)
        max_new_positions = min(strategy['max_position_count'] - current_position_count, 3)
    else:
        max_new_positions = buy_num
    
    if max_new_positions <= 0:
        return
        
    cdata = get_current_data()
    cash = context.subportfolios[strategy['pindex']].available_cash
    
    target_position_value = strategy['position_size']
    
    buy_candidates = []
    for s in strategy['stocks']:
        if (s not in context.subportfolios[strategy['pindex']].positions and 
            s not in strategy['not_buy_again'] and 
            not cdata[s].paused and
            s not in strategy['limitup_sold_today']):
            
            can_buy, reason = small_check_stock_trading_conditions(context, s, is_buy=True, strategy=strategy)
            if can_buy:
                buy_candidates.append((s, reason))
                     
    if not buy_candidates:
        return
    
    max_buy = min(len(buy_candidates), max_new_positions)
    
    bought_count = 0
    for stock, reason in buy_candidates[:max_buy]:
        buy_value = min(target_position_value, cash)
        
        min_cost = 100 * cdata[stock].last_price
        
        if buy_value < min_cost:
            continue
            
        try:
            amount = min(int(buy_value / cdata[stock].last_price), 
                        int(cash / cdata[stock].last_price))
            amount = int(amount / 100) * 100
            if amount <= 0:
                continue
            actual_value = amount * cdata[stock].last_price
            order(stock, amount, MarketOrderStyle(1.01 * cdata[stock].last_price), pindex=strategy['pindex'])
            strategy['not_buy_again'].append(stock)
            cash -= actual_value
            bought_count += 1
            
            log.info(f"[{strategy['name']}] 补仓买入 {stock}: 买入{amount}股, {reason}")
            
            min_price = min((cdata[s].last_price for s, _ in buy_candidates), default=0)
            min_unit = 100 * min_price
            if cash < min_unit:
                break
        except Exception as e:
            log.error(f"[{strategy['name']}] 补仓买入出错: {e}")
            continue
    
    if bought_count > 0:
        log.info(f"[{strategy['name']}] 补仓操作完成: 买入{bought_count}只股票")
        return True
    else:
        return False

def small_judge_market_env(context, strategy, ma_window=None, slope_window=None):
    """小市值策略判断市场环境"""
    if ma_window is None:
        ma_window = strategy['market_env_ma_window']
    if slope_window is None:
        slope_window = strategy['market_env_slope_window']
    
    yesterday = context.previous_date
    
    try:
        trade_days = get_trade_days(end_date=yesterday, count=ma_window + slope_window)
        if len(trade_days) < ma_window + slope_window:
            return None
        
        start_date = trade_days[0]
        
        sh_money = get_price('000001.XSHG', start_date=start_date, end_date=yesterday, fields='money')['money']
        sz_money = get_price('399001.XSHE', start_date=start_date, end_date=yesterday, fields='money')['money']
        
        if sh_money.empty or sz_money.empty:
            return None
        
        total_money = sh_money + sz_money
        ma_total = total_money.rolling(ma_window).mean().dropna()
        if len(ma_total) < slope_window + 1:
            return None
        
        change_total = (ma_total.iloc[-1] - ma_total.iloc[-slope_window - 1]) / ma_total.iloc[-slope_window - 1]
        
        price_df = get_price('399986.XSHE', end_date=yesterday, count=ma_window, fields='close', skip_paused=True)
        if price_df.empty:
            return None
        
        close_prices = price_df['close']
        if len(close_prices) < 2:
            return None
        
        bank_return = close_prices.iloc[-1] / close_prices.iloc[0]
        
        if change_total <= strategy['market_env_change_threshold'] or bank_return <= strategy['market_env_bank_threshold']:
            return '存量'
        else:
            return None
            
    except Exception as e:
        log.error(f"[{strategy['name']}] 市场环境判断出错: {e}")
        return None

def small_industry_macro_control(context, strategy):
    """小市值策略行业轮动控制"""
    try:
        strategy['market_environment'] = small_judge_market_env(context, strategy)
        
        initial_list = get_index_stocks('000985.XSHG', context.current_dt)
        if not initial_list:
            strategy['risk_flag'] = False
            return False
            
        yesterday = context.previous_date
        p_count = 1
        
        lookback = strategy['market_bias_lookback'] + 20
        h = get_price(initial_list, end_date=yesterday, frequency='1d', 
                     fields=['close'], count=lookback, panel=False)
        if h is None or h.empty:
            strategy['risk_flag'] = False
            return False
            
        h['date'] = pd.DatetimeIndex(h.time).date
        df_close = h.pivot(index='code', columns='date', values='close').dropna(axis=0)
        
        if df_close.empty:
            strategy['risk_flag'] = False
            return False
            
        df_ma20 = df_close.rolling(window=strategy['market_bias_lookback'], axis=1).mean().iloc[:, -p_count:]
        df_bias = (df_close.iloc[:, -p_count:] > df_ma20)  
        
        stock_industries = {}
        
        try:
            industries_dict = get_industry(initial_list, date=yesterday)
            for stock in industries_dict:
                if 'sw_l1' in industries_dict[stock]:
                    stock_industries[stock] = industries_dict[stock]['sw_l1']['industry_code']
        except Exception as e:
            log.warning(f"[{strategy['name']}] 获取行业信息出错: {e}")
        
        if not stock_industries:
            strategy['risk_flag'] = False
            return False
            
        df_bias_with_ind = df_bias.copy()
        industry_series = pd.Series(stock_industries)
        common_stocks = df_bias_with_ind.index.intersection(industry_series.index)
        
        if len(common_stocks) == 0:
            strategy['risk_flag'] = False
            return False
            
        df_bias_with_ind = df_bias_with_ind.loc[common_stocks]
        df_bias_with_ind['industry_code'] = industry_series.loc[common_stocks]  
        
        df_ratio = ((df_bias_with_ind.groupby('industry_code').sum() * 100.0) / 
                   df_bias_with_ind.groupby('industry_code').count()).round()
        
        if df_ratio.empty:
            strategy['risk_flag'] = False
            return False
            
        if len(df_ratio.columns) > 0:
            current_date_data = df_ratio.iloc[:, 0]
            top_industry = current_date_data.nlargest(1)
            if not top_industry.empty:
                top_industry_code = top_industry.index[0]
            else:
                strategy['risk_flag'] = False
                return False
        else:
            strategy['risk_flag'] = False
            return False
        
        try:
            if len(df_ratio.columns) > 0:
                sum_of_top_values = df_ratio.iloc[:, 0]
                strategy['market_width_value'] = float(sum_of_top_values.mean())
            else:
                strategy['market_width_value'] = 0
        except:
            strategy['market_width_value'] = 0
            
        is_jsg_industry = top_industry_code in strategy['avoid_industries']
        is_stock_market = strategy['market_environment'] == '存量'
        
        risk_detected = is_jsg_industry and is_stock_market
        strategy['risk_flag'] = risk_detected
        
        if top_industry_code in strategy['SW1']:
            industry_name = strategy['SW1'][top_industry_code]
        else:
            industry_name = top_industry_code
            
        log.info(f"[{strategy['name']}] 行业轮动分析: 最强行业={industry_name}({top_industry_code}), " +
                f"市场环境={strategy['market_environment']}, " +
                f"是否搅屎棍={is_jsg_industry}, " +
                f"风险触发={risk_detected}")
        
        return risk_detected
        
    except Exception as e:
        log.error(f"[{strategy['name']}] 行业轮动引擎出错: {e}")
        strategy['risk_flag'] = False
        strategy['market_environment'] = None
        return False

def small_perform_risk_control(context, strategy):
    """小市值策略执行风控"""
    log.warning(f"[{strategy['name']}] 执行风控措施：风险行业出现，清仓非涨停股")
    cdata = get_current_data()
    sold_count = 0
    kept_count = 0
    
    for stock in list(context.subportfolios[strategy['pindex']].positions.keys()):
        if stock in strategy['yesterday_HL_list'] or cdata[stock].paused:
            kept_count += 1
            continue
        
        try:
            if cdata[stock].last_price == cdata[stock].high_limit:
                log.info(f"[{strategy['name']}] 风控保留涨停股 {stock}")
                kept_count += 1
                continue
                
            last_price = cdata[stock].last_price
            if last_price <= 0:  
                last_price = cdata[stock].pre_close
            
            order_target(stock, 0, MarketOrderStyle(0.99 * last_price), pindex=strategy['pindex'])
            sold_count += 1
            log.info(f"[{strategy['name']}] 风控卖出 {stock}")
        except:
            continue
    
    if sold_count > 0:
        strategy['reason_to_sell'] = 'macro_risk'
        strategy['yesterday_HL_list'] = []
    
    log.info(f"[{strategy['name']}] 风控清仓完成: 卖出{sold_count}只, 保留{kept_count}只(含涨停股)")

def small_update_yesterday_limit_up(context, strategy):
    """小市值策略更新昨日涨停股"""
    strategy['yesterday_HL_list'] = []
    if context.subportfolios[strategy['pindex']].positions:
        df = get_price(list(context.subportfolios[strategy['pindex']].positions.keys()), 
                      end_date=context.previous_date, 
                      frequency='daily', 
                      fields=['close', 'high_limit'], 
                      count=1, 
                      panel=False, 
                      fill_paused=False)
        
        if not df.empty:
            df = df[df['close'] == df['high_limit']]
            strategy['yesterday_HL_list'] = list(df.code)

def small_choice_small(context, nchoice, strategy):
    """小市值策略选股 - 优化版"""
    index_list = [
        '000852.XSHG',  # 中证1000
        '399317.XSHE',  # 国证A指
        '399101.XSHE',  # 中小板指
        '399303.XSHE'   # 国证成长
    ]
    
    cache_key = f"index_stocks_{context.current_dt.date()}"
    if not hasattr(g, 'index_stocks_cache'):
        g.index_stocks_cache = {}
    
    all_stocks = set()
    dt_now = context.current_dt.date()
    
    for index in index_list:
        cache_key_full = f"{cache_key}_{index}"
        if cache_key_full in g.index_stocks_cache:
            stocks = g.index_stocks_cache[cache_key_full]
        else:
            stocks = get_index_stocks(index, dt_now)
            g.index_stocks_cache[cache_key_full] = stocks
        
        all_stocks.update(stocks)
    
    if not all_stocks:
        log.info(f"[{strategy['name']}] 选股过程: 指数成分股为空")
        return []
    
    cdata = get_current_data()
    
    filtered_stocks = small_filter_basic_stocks(context, list(all_stocks), strategy, cdata)
    healthy_stocks = small_health_check_filter(context, filtered_stocks, strategy)
    quality_ranked = small_quality_scoring(context, healthy_stocks, strategy)
    
    if not quality_ranked:
        selected_stocks = []
    else:
        keep_count = max(10, int(len(quality_ranked) * strategy['quality_retention_ratio']))
        top_quality = quality_ranked[:keep_count]
        
        if not top_quality:
            selected_stocks = []
        else:
            df_market_cap = get_fundamentals(query(
                valuation.code, 
                valuation.market_cap
            ).filter(
                valuation.code.in_(top_quality)
            ), date=context.previous_date)
            
            if not df_market_cap.empty:
                df_market_cap = df_market_cap.sort_values('market_cap', ascending=True)
                selected_stocks = df_market_cap.head(min(nchoice, len(df_market_cap)))['code'].tolist()
            else:
                selected_stocks = top_quality[:min(nchoice, len(top_quality))]
    
    log.info(f"[{strategy['name']}] 选股过程:初始{len(all_stocks)}支→过滤{len(filtered_stocks)}支→健康{len(healthy_stocks)}支→质量{len(quality_ranked)}支→保留{strategy['quality_retention_ratio']*100:.0f}%:{len(top_quality) if quality_ranked else 0}支→最终{len(selected_stocks)}支")
    
    current_positions = set(context.subportfolios[strategy['pindex']].positions.keys())
    stocks_0 = [s for s in selected_stocks if s in current_positions]
    stocks_1 = [s for s in selected_stocks if s not in current_positions]
    choice = (stocks_0 + stocks_1)[:nchoice]
    
    return choice

def small_filter_basic_stocks(context, stock_list, strategy, cdata=None):
    """小市值策略基础筛选 - 性能优化版"""
    if not stock_list:
        return []
    
    if cdata is None:
        cdata = get_current_data()
    
    result = []
    
    # 获取所有股票的信息，减少循环内API调用
    all_info = get_all_securities(types=['stock'], date=context.current_dt)
    
    for stock in stock_list:
        try:
            stock_data = cdata[stock]
            
            if stock_data.paused:
                continue
            
            if stock_data.is_st or '退' in stock_data.name:
                continue
            
            code = stock.split('.')[0]
            if code.startswith(('688', '689')):
                continue
            if code.startswith('8'):
                continue
            
            if stock_data.last_price > strategy['max_stock_price']:
                continue
            
            if stock in all_info.index:
                start_date = all_info.loc[stock].start_date
                if start_date is not None:
                    days_listed = (context.current_dt.date() - start_date).days
                    if days_listed < strategy['min_listed_days']:
                        continue
            
            open_price = stock_data.day_open
            high_limit = stock_data.high_limit
            low_limit = stock_data.low_limit
            
            if open_price == high_limit and open_price > 0:
                continue
            
            if open_price == low_limit and open_price > 0:
                continue
            
            result.append(stock)
        except:
            continue
    
    log.info(f"[{strategy['name']}] 基础筛选: 从{len(stock_list)}只股票中筛选出{len(result)}只")
    return result

def small_health_check_filter(context, stock_list, strategy):
    """小市值策略健康检查 - 性能优化版"""
    if not stock_list:
        return []
    
    try:
        q = query(
            valuation.code,
            balance.total_assets,
            balance.total_liability,
            cash_flow.net_operate_cash_flow,
            income.np_parent_company_owners,
            income.operating_revenue
        ).filter(valuation.code.in_(stock_list))
        
        df = get_fundamentals(q, date=context.previous_date)
        if df is None or df.empty:
            return []
        
        # 计算净资产
        df['net_asset'] = df['total_assets'] - df['total_liability']
        
        # 应用过滤条件
        # 1. 净资产 > 0
        mask = df['net_asset'] > 0
        
        # 2. 经营现金流 > 0
        mask &= df['net_operate_cash_flow'] > 0
        
        # 3. 净利润检查
        # (净利润 > 0) OR (营收 >= 阈值)
        # 默认阈值
        revenue_threshold_default = 3e8
        revenue_threshold_gem = 1e8
        
        # 判断是否创业板
        codes = df['code'].str.startswith('300')
        
        condition_profit = df['np_parent_company_owners'] > 0
        condition_revenue = (df['operating_revenue'] >= revenue_threshold_default) | \
                            (codes & (df['operating_revenue'] >= revenue_threshold_gem))
        
        mask &= (condition_profit | condition_revenue)
        
        # 应用过滤
        filtered_df = df[mask].copy()
        
        if filtered_df.empty:
            return []
        
        # 优化：批量获取价格数据计算平均成交额
        # 获取满足基本面条件的股票列表
        candidate_stocks = filtered_df['code'].tolist()
        
        # 批量获取价格数据 (分块处理防止一次请求过多)
        batch_size = 1000  # 优化：增加批量大小
        all_money_data = []
        
        for i in range(0, len(candidate_stocks), batch_size):
            batch = candidate_stocks[i:i+batch_size]
            try:
                # 批量获取60日成交额
                price_df = get_price(batch, end_date=context.previous_date, count=60, 
                                    frequency='daily', fields=['money'], panel=False)
                if price_df is not None and not price_df.empty:
                    all_money_data.append(price_df)
            except:
                continue
        
        if not all_money_data:
            return []
        
        # 合并数据
        combined_money = pd.concat(all_money_data, ignore_index=True) if len(all_money_data) > 1 else all_money_data[0]
        
        # 计算每只股票的平均成交额
        avg_money = combined_money.groupby('code')['money'].mean()
        
        # 过滤成交额不足的股票
        valid_stocks = avg_money[avg_money >= strategy['avg_money_threshold']].index.tolist()
        
        # 取交集
        final_stocks = [s for s in candidate_stocks if s in valid_stocks]
        
        return final_stocks
        
    except Exception as e:
        log.error(f"[{strategy['name']}] 健康检查出错: {e}")
        return []

def small_quality_scoring(context, stock_list, strategy):
    """小市值策略质量评分"""
    if not stock_list:
        return []
    
    try:
        q = query(
            valuation.code,
            valuation.market_cap,
            indicator.roe,
            indicator.roa,
            valuation.pe_ratio,
            cash_flow.net_operate_cash_flow,
            income.np_parent_company_owners,
            balance.total_assets,
            balance.total_liability
        ).filter(valuation.code.in_(stock_list))
        
        df = get_fundamentals(q, date=context.previous_date)
        if df is None or df.empty:
            return []
        
        df = df[
            (df['roe'] >= strategy['filter_roe'] * 0.8) & 
            (df['roa'] >= strategy['filter_roa'] * 0.8) & 
            (df['market_cap'] >= strategy['filter_market_cap_min']) &
            (df['market_cap'] <= strategy['filter_market_cap_max'])
        ]
        
        if df.empty:
            return []
        
        df['net_asset'] = df['total_assets'] - df['total_liability']
        df['ocf_quality'] = df['net_operate_cash_flow'] / (df['np_parent_company_owners'] + 1e-5)
        df['debt_ratio'] = df['total_liability'] / (df['total_assets'] + 1e-5)
        df['enhanced_peg'] = df['pe_ratio'] / (df['roe'] * 100 + 1e-5)
        
        df['score'] = 0
        df['score'] += np.where(df['roe'] > 0.20, 3, np.where(df['roe'] > 0.15, 2, np.where(df['roe'] > 0.10, 1, 0)))
        df['score'] += np.where(df['roa'] > 0.15, 3, np.where(df['roa'] > 0.10, 2, np.where(df['roa'] > 0.05, 1, 0)))
        df['score'] += np.where(df['debt_ratio'] < 0.3, 3, np.where(df['debt_ratio'] < 0.5, 2, np.where(df['debt_ratio'] < 0.7, 1, 0)))
        df['score'] += np.where(df['ocf_quality'] > 1.2, 3, np.where(df['ocf_quality'] > 0.8, 2, np.where(df['ocf_quality'] > 0.5, 1, 0)))
        df['score'] += np.where(df['pe_ratio'] < 20, 3, np.where(df['pe_ratio'] < 35, 2, np.where(df['pe_ratio'] < 50, 1, 0)))
        df['score'] += np.where(df['enhanced_peg'] < 0.8, 3, np.where(df['enhanced_peg'] < 1.2, 2, np.where(df['enhanced_peg'] < 1.5, 1, 0)))
        
        df_sorted = df.sort_values('score', ascending=False)
        return df_sorted['code'].tolist()
        
    except Exception as e:
        log.error(f"[{strategy['name']}] 质量评分出错: {e}")
        return []

# ==================== 策略4: 动态行业ETF轮动 (模型2) ====================
def dynamic_update_sector_pool(context):
    """动态更新行业ETF池"""
    strategy = g.dynamic_etf_strategy
    all_etfs = get_all_securities(['etf']).index.tolist()
    candidate_dict = {} 
  
    end_date = context.previous_date
  
    chunk_size = 500
    money_data_list = []
  
    for i in range(0, len(all_etfs), chunk_size):
        chunk_codes = all_etfs[i:i+chunk_size]
        try:
            df = get_price(chunk_codes, count=1, end_date=end_date, frequency='daily', fields=['money'], panel=False)
          
            if df.empty:
                continue
          
            # 兼容不同的返回格式
            if isinstance(df.index, pd.MultiIndex):
                # 格式：索引为，列为 money
                # 将索引转为代码
                s = df['money']
                s.index = df.index.get_level_values(-1) # 取最后一级索引（代码）
                money_data_list.append(s)
            elif isinstance(df.index, pd.RangeIndex) and 'code' in df.columns:
                # 格式：索引为数字，包含 code 列
                s = df.set_index('code')['money']
                money_data_list.append(s)
            elif 'money' in df.columns:
                # 其他可能的扁平格式
                s = df['money']
                money_data_list.append(s)
              
        except Exception as e:
            # 即使某一块出错，也继续处理下一块
            continue

    if not money_data_list:
        log.warning(f"[{strategy['name']}] 未能获取任何成交额数据")
        return

    # 合并所有分块数据
    money_series = pd.concat(money_data_list)
  
    for code in money_series.index:
        money = money_series.get(code, 0)
      
        if pd.isna(money) or money <= 50000000:
            continue
      
        industry = dynamic_get_industry_by_index(code, context)
        if industry is None:
            industry = dynamic_get_industry_by_name(code)
      
        if industry is None:
            continue
      
        if industry not in candidate_dict or money > candidate_dict[industry][0]:
            candidate_dict[industry] = (money, code)
  
    if not candidate_dict:
        fallback_codes = []
        for code in strategy['fixed_etf_pool']:
            industry = dynamic_get_industry_by_index(code, context) or dynamic_get_industry_by_name(code)
            if industry:
                fallback_codes.append(code)
        strategy['dynamic_etf_pool'] = list(dict.fromkeys(fallback_codes))[:100]
    else:
        sorted_items = sorted(candidate_dict.items(), key=lambda x: x[1][0], reverse=True)
        strategy['dynamic_etf_pool'] = [code for industry, (money, code) in sorted_items][:100]
  
    etf_name_code_list = [f"{get_security_info(c).display_name}({c})" for c in strategy['dynamic_etf_pool']]
    log.info(f"[{strategy['name']}] 动态更新完成 热点资金涌入行业池(前{len(strategy['dynamic_etf_pool'])}只): {etf_name_code_list}")

def dynamic_get_industry_by_index(etf_code, context):
    """根据跟踪指数获取行业"""
    try:
        if not hasattr(g, 'fund_info_cache'):
            g.fund_info_cache = {}
        cache_key = f"{etf_code}_{context.previous_date}"
        if cache_key in g.fund_info_cache:
            fund_info = g.fund_info_cache[cache_key]
        else:
            fund_info = get_fund_info(etf_code, date=context.previous_date)
            g.fund_info_cache[cache_key] = fund_info
            
        track_index = fund_info.get('track_index', '')
        if not track_index:
            return None
            
        if not hasattr(g, 'security_info_cache'):
            g.security_info_cache = {}
        if track_index in g.security_info_cache:
            index_name = g.security_info_cache[track_index].display_name
        else:
            index_info = get_security_info(track_index)
            g.security_info_cache[track_index] = index_info
            index_name = index_info.display_name
            
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            for kw in keywords:
                if kw in index_name:
                    return industry
    except:
        pass
    return None

def dynamic_get_industry_by_name(etf_code):
    """根据名称获取行业"""
    try:
        if not hasattr(g, 'security_info_cache'):
            g.security_info_cache = {}
        if etf_code in g.security_info_cache:
            name = g.security_info_cache[etf_code].display_name
        else:
            security_info = get_security_info(etf_code)
            g.security_info_cache[etf_code] = security_info
            name = security_info.display_name
            
        for industry, patterns in INDUSTRY_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(name):
                    return industry
    except:
        pass
    return None

def dynamic_calculate_all_metrics_for_etf(context, etf):
    """计算ETF指标"""
    strategy = g.dynamic_etf_strategy
    try:
        etf_name = get_security_name(etf)
        lookback = strategy['lookback_days'] + 20
        prices = attribute_history(etf, lookback, '1d', ['close'])
        current_data = get_current_data()
        if len(prices) < strategy['lookback_days']:
            return None
        current_price = current_data[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        recent_price_series = price_series[-(strategy['lookback_days'] + 1):]
        # 优化：避免重复计算np.log
        log_prices = np.log(recent_price_series)
        y = log_prices
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0
        momentum_score = annualized_returns * r_squared

        volume_ratio = dynamic_get_volume_ratio(context, etf, show_detail_log=False)

        day_ratios = []
        passed_loss_filter = True
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < strategy['loss']:
                passed_loss_filter = False

        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'passed_momentum': strategy['min_score_threshold'] <= momentum_score <= strategy['max_score_threshold'],
            'passed_r2': r_squared > strategy['r2_threshold'],
            'passed_volume': volume_ratio is not None and volume_ratio < strategy['volume_threshold'],
            'passed_loss': passed_loss_filter,
        }
    except Exception as e:
        log.warning(f"[{strategy['name']}] 计算 {etf} 指标出错: {e}")
        return None
def dynamic_apply_filters(metrics_list):
    """应用过滤条件"""
    strategy = g.dynamic_etf_strategy
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('R²', lambda m: m['passed_r2'], strategy['enable_r2_filter']),
        ('成交量', lambda m: m['passed_volume'], strategy['enable_volume_check']),
        ('短期风控', lambda m: m['passed_loss'], strategy['enable_loss_filter']),
    ]
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered

def dynamic_get_final_ranked_etfs(context):
    """获取最终排名的ETF列表"""
    strategy = g.dynamic_etf_strategy
    # 行业去重合并逻辑（动态池优先策略）
    industry_map = {} # 键: 行业名, 值: ETF代码
  
    # 步骤A: 优先处理动态池（热点资金池）
    # 动态池本身已经是按成交额筛选的行业龙头，直接加入映射
    for etf in strategy['dynamic_etf_pool']:
        try:
            industry = dynamic_get_industry_by_index(etf, context) or dynamic_get_industry_by_name(etf)
            if industry:
                industry_map[industry] = etf
            else:
                # 如果无法识别行业，为了不丢失标的，用代码做Key强行保留
                industry_map[etf] = etf
        except:
            # 处理ETF代码不存在的情况
            continue

    # 步骤B: 补充固定池（白名单池）
    # 仅当固定池中的ETF所属行业不在动态池中时，才予以保留
    for etf in strategy['fixed_etf_pool']:
        try:
            industry = dynamic_get_industry_by_index(etf, context) or dynamic_get_industry_by_name(etf)
            if industry:
                if industry not in industry_map:
                    # 该行业在动态池中不存在（可能是冷门行业或未达标），使用固定池补充
                    industry_map[industry] = etf
            else:
                # 无法识别行业的固定ETF，作为独立标的保留
                if etf not in industry_map:
                    industry_map[etf] = etf
        except:
            # 处理ETF代码不存在的情况
            continue

    etf_set = list(industry_map.values())
    log.info(f"[{strategy['name']}] ETF池合并 固定池与动态池去重完成，最终参与计算: {len(etf_set)}只")

    # 指标计算与过滤
    all_metrics = []
    for etf in etf_set:
        try:
            current_data = get_current_data()
            if current_data[etf].paused:
                continue
            metrics = dynamic_calculate_all_metrics_for_etf(context, etf)
            if metrics:
                # 防止重复添加
                if metrics['etf'] not in {m['etf'] for m in all_metrics}:
                    all_metrics.append(metrics)
        except Exception as e:
            # 处理ETF数据获取异常
            continue

    # 处理 NaN 值
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or np.isnan(score):
            item['momentum_score'] = float('-inf')

    all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
  
    log.info(f"[{strategy['name']}] >>> ETF指标计算完成，正在进行过滤 <<<")

    final_list = dynamic_apply_filters(all_metrics)
    for item in final_list:
        score = item.get('momentum_score')
        if pd.isna(score) or np.isnan(score):
            item['momentum_score'] = float('-inf')
    final_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
  
    return final_list

def dynamic_minute_level_stop_loss(context):
    """分钟级止损"""
    strategy = g.dynamic_etf_strategy
    if not strategy['use_fixed_stop_loss']:
        return

    for security in list(context.subportfolios[strategy['pindex']].positions.keys()):
        if security not in strategy['fixed_etf_pool']:
            continue
        position = context.subportfolios[strategy['pindex']].positions[security]
        if position.total_amount <= 0:
            continue

        current_data = get_current_data()
        current_price = current_data[security].last_price
        cost_price = position.avg_cost

        if current_price <= cost_price * strategy['fixedStopLossThreshold']:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"[{strategy['name']}] [分钟级] 固定百分比止损卖出: {security} {security_name}，当前价: {current_price:.3f}, 成本: {cost_price:.3f}, 预估亏损: {loss_percent:.2f}%")

            success = dynamic_smart_order_target_value(security, 0, context)
            if success:
                log.info(f"[{strategy['name']}] [分钟级] 已成功止损卖出: {security} {security_name}")
            else:
                log.info(f"[{strategy['name']}] [分钟级] 止损卖出失败: {security} {security_name}")

def dynamic_etf_sell_trade(context):
    """卖出交易"""
    strategy = g.dynamic_etf_strategy
    log.info(f"[{strategy['name']}] ========== 卖出操作开始 ==========")

    ranked_etfs = dynamic_get_final_ranked_etfs(context)
    target_etfs = []
  
    if ranked_etfs:
        for metrics in ranked_etfs[:strategy['holdings_num']]:
            target_etfs.append(metrics['etf'])
            log.info(f"[{strategy['name']}] 确定最终目标: {metrics['etf']} {metrics['etf_name']}，得分: {metrics['momentum_score']:.4f}")
    else:
        log.info(f"[{strategy['name']}] 无符合条件的ETF，目标为空仓")
        target_etfs = []

    strategy['target_etfs_list'] = target_etfs

    current_positions = list(context.subportfolios[strategy['pindex']].positions.keys())
    target_set = set(target_etfs)

    for security in current_positions:
        position = context.subportfolios[strategy['pindex']].positions[security]
        if position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            log.info(f"[{strategy['name']}] 准备卖出不在今日目标列表的持仓: {security} {security_name}")

            success = dynamic_smart_order_target_value(security, 0, context)
            if success:
                log.info(f"[{strategy['name']}] 已成功卖出: {security} {security_name}")
            else:
                log.info(f"[{strategy['name']}] 卖出失败: {security} {security_name}")

    log.info(f"[{strategy['name']}] ========== 卖出操作完成 ==========")

def dynamic_etf_buy_trade(context):
    """买入交易"""
    strategy = g.dynamic_etf_strategy
    log.info(f"[{strategy['name']}] ========== 买入操作开始 ==========")

    target_etfs = strategy['target_etfs_list']
    if not target_etfs:
        log.info(f"[{strategy['name']}] 根据昨日计算，今日无目标ETF，保持空仓")
        log.info(f"[{strategy['name']}] ========== 买入操作完成 ==========")
        return

    current_positions = list(context.subportfolios[strategy['pindex']].positions.keys())
    current_etf_positions = [pos for pos in current_positions if pos in strategy['fixed_etf_pool']]
    positions_to_sell = [pos for pos in current_etf_positions if pos not in target_etfs]

    if positions_to_sell:
        log.info(f"[{strategy['name']}] 尚有持仓需要卖出: {[get_security_name(p) for p in positions_to_sell]}，等待卖出完成后再买入新标的")
        log.info(f"[{strategy['name']}] ========== 买入操作完成 ==========")
        return

    total_value = context.subportfolios[strategy['pindex']].total_value
    cash_buffer_ratio = 0.01
    investable_value = total_value * (1 - cash_buffer_ratio)

    target_value_per_etf = investable_value / len(target_etfs)

    log.info(f"[{strategy['name']}] 账户总价值: {total_value:.2f}, 可投资金额: {investable_value:.2f}, 目标ETF数量: {len(target_etfs)}, 单只ETF目标金额: {target_value_per_etf:.2f}")

    if target_value_per_etf < strategy['min_money']:
        log.info(f"[{strategy['name']}] 计算出的单只ETF目标金额 {target_value_per_etf:.2f} 小于最小交易额 {strategy['min_money']:.2f}，无法买入")
        log.info(f"[{strategy['name']}] ========== 买入操作完成 ==========")
        return

    for etf in target_etfs:
        current_value = 0
        if etf in context.subportfolios[strategy['pindex']].positions:
            position = context.subportfolios[strategy['pindex']].positions[etf]
            if position.total_amount > 0:
                current_value = position.total_amount * position.price

        value_diff = abs(target_value_per_etf - current_value)

        required_funds = max(0, value_diff)
        if context.subportfolios[strategy['pindex']].available_cash < required_funds:
            log.info(f"[{strategy['name']}] 可用现金不足，无法买入/调仓 {etf}。所需: {required_funds:.2f}, 可用: {context.subportfolios[strategy['pindex']].available_cash:.2f}")
            continue

        success = dynamic_smart_order_target_value(etf, target_value_per_etf, context)
        if success:
            etf_name = get_security_name(etf)
            if current_value == 0:
                log.info(f"[{strategy['name']}] 买入新持仓: {etf} {etf_name}，目标金额: {target_value_per_etf:.2f}")
            elif current_value < target_value_per_etf:
                log.info(f"[{strategy['name']}] 增持: {etf} {etf_name}，目标金额: {target_value_per_etf:.2f}")
            else:
                log.info(f"[{strategy['name']}] 减持/调仓: {etf} {etf_name}，目标金额: {target_value_per_etf:.2f}")

    log.info(f"[{strategy['name']}] ========== 买入操作完成 ==========")

def dynamic_check_positions(context):
    """持仓检查"""
    strategy = g.dynamic_etf_strategy
    current_data = get_current_data()
    for security in context.subportfolios[strategy['pindex']].positions:
        position = context.subportfolios[strategy['pindex']].positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"[{strategy['name']}] 持仓检查: {security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")

def dynamic_smart_order_target_value(security, target_value, context):
    """智能下单"""
    strategy = g.dynamic_etf_strategy
    current_data = get_current_data()
    security_name = get_security_name(security)

    if current_data[security].paused:
        log.info(f"[{strategy['name']}] {security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"[{strategy['name']}] {security} {security_name}: 当前涨停，跳过买入")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"[{strategy['name']}] 持仓检查: {security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")

def dynamic_smart_order_target_value(security, target_value, context):
    """智能下单"""
    strategy = g.dynamic_etf_strategy
    current_data = get_current_data()
    security_name = get_security_name(security)

    if current_data[security].paused:
        log.info(f"[{strategy['name']}] {security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"[{strategy['name']}] {security} {security_name}: 当前涨停，跳过买入")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"[{strategy['name']}] {security} {security_name}: 当前跌停，跳过卖出")
        return False

    current_price = current_data[security].last_price
    if current_price == 0:
        return False

    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    current_position = context.subportfolios[strategy['pindex']].positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0

    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price

    if 0 < trade_value < strategy['min_money']:
        log.info(f"[{strategy['name']}] {security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{strategy['min_money']}，跳过交易")
        return False

    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    if amount_diff != 0:
        order_result = order(security, amount_diff, pindex=strategy['pindex'])
        if order_result:
            if amount_diff > 0:
                log.info(f"[{strategy['name']}] 买入 {security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
            else:
                sell_total_amount = abs(amount_diff) * current_price
                log.info(f"[{strategy['name']}] 卖出 {security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}，总金额{sell_total_amount:.2f}元")
            return True
        else:
            log.warning(f"[{strategy['name']}] 下单失败: {security} {security_name}，数量: {amount_diff}")
            return False
    return False

def dynamic_get_volume_ratio(context, security, lookback_days=None, threshold=None, show_detail_log=True):
    """获取量比"""
    strategy = g.dynamic_etf_strategy
    if lookback_days is None:
        lookback_days = strategy['volume_lookback']
    if threshold is None:
        threshold = strategy['volume_threshold']

    try:
        if not hasattr(g, 'volume_cache'):
            g.volume_cache = {}
        cache_key = f"{security}_{context.current_dt.strftime('%Y%m%d')}_{lookback_days}"
        if cache_key in g.volume_cache:
            return g.volume_cache[cache_key]

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
        df_vol = get_price(security,
                           start_date=today,
                           end_date=context.current_dt,
                           frequency='1m',
                           fields=['volume'],
                           skip_paused=False,
                           fq='pre',
                           fill_paused=False,
                           panel=False)

        current_volume = df_vol['volume'].sum()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        g.volume_cache[cache_key] = volume_ratio
        
        return volume_ratio
    except Exception as e:
        return None

# ==================== 通用工具函数 ====================
def get_previous_minute_price(security, context):
    """获取前一分钟价格"""
    try:
        if not hasattr(g, 'price_cache'):
            g.price_cache = {}
        cache_key = f"{security}_{context.current_dt.strftime('%Y%m%d%H%M')}"
        if cache_key in g.price_cache:
            return g.price_cache[cache_key]

        end_time = context.current_dt
        start_time = end_time - datetime.timedelta(minutes=2)
        
        minute_data = get_price(
            security, 
            start_date=start_time, 
            end_date=end_time, 
            frequency='1m', 
            fields=['close'],
            skip_paused=False,
            fq='pre',
            panel=False
        )
        
        if minute_data is None or len(minute_data) < 2:
            hist_data = attribute_history(security, 2, '1d', ['close'], skip_paused=True)
            if not hist_data.empty:
                price = hist_data['close'].iloc[-1]
                g.price_cache[cache_key] = price
                return price
            return 0
        
        if len(minute_data) >= 2:
            price = minute_data['close'].iloc[-2]
        else:
            price = minute_data['close'].iloc[-1]
            
        g.price_cache[cache_key] = price
        return price
            
    except Exception as e:
        log.warn(f"获取{security}前1分钟价格失败: {e}")
        return 0

def calculate_smoothed_atr(security, strategy):
    """计算平滑ATR"""
    current_atr, atr_values, success, msg = calculate_atr(security, strategy['atr_period'])
    
    if success and len(atr_values) >= strategy['atr_smoothing']:
        smoothed_atr = np.mean(atr_values[-strategy['atr_smoothing']:])
        return smoothed_atr, True, "平滑ATR计算成功"
    
    return current_atr, success, msg

def calculate_atr(security, period=14):
    """计算ATR指标"""
    try:
        needed_days = period + 20
        hist_data = attribute_history(security, needed_days, '1d', 
                                     ['high', 'low', 'close'], skip_paused=True)
        
        if len(hist_data) < period + 1:
            return 0, [], False, f"数据不足{period+1}天"
        
        high_prices = hist_data['high'].values
        low_prices = hist_data['low'].values
        close_prices = hist_data['close'].values
        
        tr_values = np.zeros(len(high_prices))
        if len(high_prices) > 1:
            tr1 = high_prices[1:] - low_prices[1:]
            tr2 = np.abs(high_prices[1:] - close_prices[:-1])
            tr3 = np.abs(low_prices[1:] - close_prices[:-1])
            tr_values[1:] = np.maximum(np.maximum(tr1, tr2), tr3)
        
        atr_values = np.zeros(len(tr_values))
        for i in range(period, len(tr_values)):
            atr_values[i] = np.mean(tr_values[i-period+1:i+1])
        
        current_atr = atr_values[-1] if len(atr_values) > 0 else 0
        valid_atr = atr_values[period:] if len(atr_values) > period else atr_values
        
        return current_atr, valid_atr, True, "计算成功"
    
    except Exception as e:
        log.warn(f"计算{security} ATR时出错: {e}")
        return 0, [], False, f"计算出错:{str(e)}"

def get_security_name(security):
    """获取证券名称"""
    current_data = get_current_data()
    return current_data[security].name if security in current_data else security