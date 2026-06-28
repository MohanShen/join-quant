# Clone from JoinQuant
# postId: d02cde29e649c9e8056582149cebf276
# backtestId: 195f89912425ad2135fd7b9cf49687d5
# title: 高质量稳定上涨策略

# 克隆自聚宽文章：https://www.joinquant.com/post/1399
# 标题：【量化课堂】多因子策略入门
# 作者：JoinQuant量化课堂

# 克隆自聚宽文章：https://www.joinquant.com/post/15002
# 标题：价值选股与RSRS择时
# 作者：K线放荡不羁

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import datetime
import math
from datetime import time
import talib
from prettytable import PrettyTable
import warnings
warnings.filterwarnings("ignore")

# ==================== 全局配置 ====================
STRATEGY_ALLOCATION = {
    'etf': 0.4,
    'small_cap': 0.35,
    'white_horse': 0.25
}
# ETF轮动策略配置
ETF_CONFIG = {
    'etf_pool': [
        "513100.XSHG", 
        '159525.XSHE',
        "513130.XSHG", 
        '159915.XSHE',
        '159628.XSHE',
        "588120.XSHG", 
        "513520.XSHG",
        "513030.XSHG", 
        "518880.XSHG",
        "161226.XSHE",
        "159985.XSHE",
        "501018.XSHG",
        "159652.XSHE", 
        "511090.XSHG",
    ],
    'target_num': 1,
    'm25_days': 25,
    'auto_day': True,
    'min_days': 20,
    'max_days': 60,
    'premium_threshold': 5.0
}
# 小市值策略配置
SMALL_CAP_CONFIG = {
    'market_index': '399100.XSHE',
    'stock_num': 6,
    'up_price': 20,
    'pass_april': True,
    'run_stoploss': True,
    'stoploss_strategy': 3,
    'stoploss_limit': 0.91,
    'stoploss_market': 0.95,
    'no_trading_buy': ['600036.XSHG']
}
# 白马策略配置
WHITE_HORSE_CONFIG = {
    'stock_num': 20,
    'max_stock_price': 50,
    'stop_loss_ratio': 0.94,
    'recent_days': 10,
    'buy_stock_count': 20,
    'foreign_etfs': [
        '513520.XSHG', 
        '513100.XSHG', 
        '159934.XSHE',
        '515180.XSHG'
    ]
}
# ==================== 初始化函数 ====================
def initialize(context):
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_benchmark('000300.XSHG')
    
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=1/10000, close_commission=1/10000,
        close_today_commission=0, min_commission=5
    ), type='stock')
    
    set_slippage(FixedSlippage(0.0001), type='fund')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.0002, close_commission=0.0002,
        close_today_commission=0, min_commission=1
    ), type='fund')
    
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    
    # ========== 先初始化全局变量 ==========
    init_globals(context)
    
    # ========== 然后再调度任务 ==========
    schedule_tasks(context)
    
    log.info("=" * 80)
    log.info("多策略组合系统初始化完成")
    log.info(f"ETF轮动: {STRATEGY_ALLOCATION['etf']:.0%} | "
             f"小市值: {STRATEGY_ALLOCATION['small_cap']:.0%} | "
             f"白马: {STRATEGY_ALLOCATION['white_horse']:.0%}")
    log.info("=" * 80)

def init_globals(context):
    """初始化全局变量"""
    initial_cash = context.portfolio.starting_cash
    
    # 股票归属追踪
    g.stock_strategy = {}
    
    # 各策略累计净值(包含已实现盈亏)
    g.strategy_value = {
        'etf': initial_cash * STRATEGY_ALLOCATION['etf'],
        'small_cap': initial_cash * STRATEGY_ALLOCATION['small_cap'],
        'white_horse': initial_cash * STRATEGY_ALLOCATION['white_horse']
    }
    
    # 初始资金(用于计算收益率)
    g.strategy_starting_cash = {
        'etf': initial_cash * STRATEGY_ALLOCATION['etf'],
        'small_cap': initial_cash * STRATEGY_ALLOCATION['small_cap'],
        'white_horse': initial_cash * STRATEGY_ALLOCATION['white_horse']
    }
    
    # 各策略持仓列表
    g.strategy_holdings = {
        'etf': [],
        'small_cap': [],
        'white_horse': []
    }
    
    # ETF策略特有变量
    g.etf = {
        'positions': {}
    }
    
    # 小市值策略特有变量
    g.small_cap = {
        'yesterday_hl_list': [],
        'target_list': [],
        'not_buy_again': [],
        'reason_to_sell': '',
        'no_trading_today': False,
        'no_trading_hold_signal': False
    }
    
    # 白马策略特有变量
    g.white_horse = {
        'yesterday_limit_up': [],
        'market_temp': 'warm',
        'signal': 'big',
        'rebound_stocks': {}
    }
def schedule_tasks(context):
    """调度任务"""
    run_daily(daily_prepare, '9:05')
    
    if STRATEGY_ALLOCATION['etf'] > 0:
        run_daily(etf_trade, '9:31')
    
    if STRATEGY_ALLOCATION['small_cap'] > 0:
        run_daily(small_cap_check_no_trading_month, '9:35')
        run_daily(small_cap_stoploss, '10:00')
        run_weekly(small_cap_weekly_adjust, 2, '10:30')
        run_daily(small_cap_check_afternoon, '14:25')
        run_daily(small_cap_check_afternoon, '14:55')
        run_daily(small_cap_close_account, '14:50')
    
    if STRATEGY_ALLOCATION['white_horse'] > 0:
        run_monthly(white_horse_signal, 1, '9:00')
        run_weekly(white_horse_clear_rebound, 5, '9:35')
        run_daily(white_horse_adjust, '9:35')
        run_daily(white_horse_stop_loss, '14:00')
        run_daily(white_horse_stop_loss, '14:30')
        run_daily(white_horse_stop_loss, '14:50')
    
    #run_daily(daily_settlement, '15:00')
def daily_prepare(context):
    """每日开盘前准备"""
    log.info(f"{'='*30}{context.current_dt.strftime('%Y-%m-%d')} 开盘准备{'='*30}")
    
    # 更新持仓列表
    for strategy_name in ['etf', 'small_cap', 'white_horse']:
        g.strategy_holdings[strategy_name] = []
    
    for stock in context.portfolio.positions.keys():
        strategy = g.stock_strategy.get(stock)
        if strategy:
            g.strategy_holdings[strategy].append(stock)
    
    # 小市值：昨日涨停
    if g.strategy_holdings['small_cap']:
        df = get_price(
            g.strategy_holdings['small_cap'],
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1, panel=False, fill_paused=False
        )
        if not df.empty:
            g.small_cap['yesterday_hl_list'] = list(df[df['close'] >= df['high_limit'] * 0.997].code)
    
    g.small_cap['no_trading_today'] = is_no_trading_month(context)

    # 白马：昨日涨停
    if g.strategy_holdings['white_horse']:
        df = get_price(
            g.strategy_holdings['white_horse'],
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1, panel=False, fill_paused=False
        )
        if not df.empty:
            g.white_horse['yesterday_limit_up'] = list(df[df['close'] >= df['high_limit'] * 0.997].code)


# ==================== 策略专用交易函数 ====================
def strategy_open_position(context, strategy_name, security, value):
    """策略买入"""
    # 计算可用资金
    strategy_total = context.portfolio.total_value * STRATEGY_ALLOCATION[strategy_name]
    current_holdings_value = sum([
        context.portfolio.positions[s].value 
        for s in g.strategy_holdings[strategy_name]
        if s in context.portfolio.positions
    ])
    available = max(0, strategy_total - current_holdings_value)
    
    # 调整买入金额
    if value > available:
        value = available * 0.95
    
    current_price = get_current_data()[security].last_price
    if value < current_price * 100:
        return False
    
    order = order_target_value(security, value)
    if order and order.filled > 0:
        g.stock_strategy[security] = strategy_name
        g.strategy_holdings[strategy_name].append(security)
        log.info(f"[{strategy_name}] 买入 {security} 数量:{order.filled} 金额:{value:.0f}")
        return True
    return False
    
def strategy_open_position_add(context, strategy_name, security, value):
    """策略买入(买入)"""
    order = order_value(security, value)
    if order and order.filled > 0:
        g.stock_strategy[security] = strategy_name
        if value > 0:
            g.strategy_holdings[strategy_name].append(security)
        return order
    return order
    
def strategy_close_position(context, strategy_name, position):
    """策略卖出"""
    security = position.security
    order = order_target_value(security, 0)
    
    if order and order.status == OrderStatus.held:
        # 计算已实现盈亏
        pnl = (order.price - order.avg_cost) * order.amount
        g.strategy_value[strategy_name] += pnl
        
        # 清理
        if security in g.stock_strategy:
            del g.stock_strategy[security]
        if security in g.strategy_holdings[strategy_name]:
            g.strategy_holdings[strategy_name].remove(security)
        
        log.info(f"[{strategy_name}] 卖出 {security} 盈亏:{pnl:.2f}")
        return True
    return False


# ==================== ETF轮动策略 ====================
def etf_trade(context):
    """ETF轮动主交易函数"""
    config = ETF_CONFIG
    
    # 获取目标ETF列表
    if config['auto_day']:
        target_list, rank_info = etf_get_rank_auto(context, return_info=True)
        target_list = target_list[:config['target_num']]
    else:
        target_list, rank_info = etf_get_rank_fixed(context, return_info=True)
        target_list = target_list[:config['target_num']]
    
    if rank_info:
        log.info("[ETF轮动] 动量评分排行:")
        for i, (etf, score) in enumerate(rank_info[:5], 1):
            etf_name = get_security_info(etf).display_name
            log.info(f"  {i}. {etf} {etf_name:10s} 得分:{score:.4f}")

    if not target_list:
        log.warning("[ETF轮动] 无符合条件的标的")
        return
    
    current_holdings = g.strategy_holdings['etf'][:]
    
    # 卖出不在目标列表的持仓
    for stock in current_holdings:
        if stock not in target_list and stock in context.portfolio.positions:
            pos = context.portfolio.positions[stock]
            strategy_close_position(context, 'etf', pos)
    
    # 买入新标的
    if len(g.strategy_holdings['etf']) < config['target_num']:
        strategy_total = context.portfolio.total_value * STRATEGY_ALLOCATION['etf']
        current_holdings_value = sum([
            context.portfolio.positions[s].value 
            for s in g.strategy_holdings['etf']
            if s in context.portfolio.positions
        ])
        available = max(0, strategy_total - current_holdings_value)
        
        if available > 0 and (config['target_num'] - len(g.strategy_holdings['etf'])) > 0:
            value_per_stock = available / (config['target_num'] - len(g.strategy_holdings['etf']))
            
            for stock in target_list:
                if stock not in g.strategy_holdings['etf']:
                    strategy_open_position(context, 'etf', stock, value_per_stock)
                    if len(g.strategy_holdings['etf']) >= config['target_num']:
                        break

def etf_get_rank_fixed(context, return_info=False):
    """固定周期动量评分"""
    config = ETF_CONFIG
    data = pd.DataFrame(index=config['etf_pool'], 
                       columns=["annualized_returns", "r2", "score"])
    current_data = get_current_data()
    
    for etf in config['etf_pool']:
        try:
            df = attribute_history(etf, config['m25_days'], "1d", ["close", "high"])
            if len(df) < config['m25_days']:
                continue
            
            prices = np.append(df["close"].values, current_data[etf].last_price)
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1
            
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
            
            if len(prices) >= 4:
                if min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < 0.95:
                    data.loc[etf, "score"] = 0
            
            premium_rate = get_etf_premium_rate(context, etf)
            if premium_rate >= config['premium_threshold']:
                data.loc[etf, "score"] -= 1
                
        except Exception as e:
            continue
    
    data = data.query("0 < score < 6").sort_values(by="score", ascending=False)
    
    if return_info:
        rank_info = [(idx, row['score']) for idx, row in data.iterrows()]
        return data.index.tolist(), rank_info
    return data.index.tolist()

def etf_get_rank_auto(context, return_info=False):
    """动态周期动量评分（基于波动率）"""
    config = ETF_CONFIG
    data = pd.DataFrame(index=config['etf_pool'], 
                       columns=["annualized_returns", "r2", "score"])
    current_data = get_current_data()
    
    for etf in config['etf_pool']:
        try:
            df = attribute_history(etf, config['max_days']+10, "1d", ["close", "high", "low"])
            
            if len(df) < (config['max_days']+10) or \
               df["low"].isna().sum() > config['max_days'] or \
               df["close"].isna().sum() > config['max_days'] or \
               df["high"].isna().sum() > config['max_days']:
                continue
            
            long_atr = talib.ATR(df["high"], df["low"], df["close"], timeperiod=config['max_days'])
            short_atr = talib.ATR(df["high"], df["low"], df["close"], timeperiod=config['min_days'])
            
            lookback = int(config['min_days'] + 
                          (config['max_days'] - config['min_days']) * 
                          (1 - min(0.9, short_atr[-1]/long_atr[-1])))
            
            prices = np.append(df["close"].values, current_data[etf].last_price)
            prices = prices[-lookback:]
            
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1
            
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
            
            con1 = min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < 0.95
            con2 = (prices[-1] < prices[-2]) & (prices[-2] < prices[-3]) & \
                   (prices[-3] < prices[-4]) & (prices[-1]/prices[-4] < 0.95)
            
            if con1 or con2:
                data.loc[etf, "score"] = 0
            
            premium_rate = get_etf_premium_rate(context, etf)
            if premium_rate >= config['premium_threshold']:
                data.loc[etf, "score"] -= 1
                
        except Exception as e:
            continue
    
    data = data.sort_values(by="score", ascending=False).reset_index()
    data = data.query("0 < score < 6").sort_values(by="score", ascending=False)
    
    if return_info:
        rank_info = [(row['index'], row['score']) for _, row in data.iterrows()]
        return data['index'].tolist(), rank_info
    return data['index'].tolist()

def get_etf_premium_rate(context, etf_code):
    """计算ETF溢价率"""
    try:
        etf_price = get_price(etf_code, start_date=context.previous_date, 
                             end_date=context.previous_date).iloc[-1]['close']
        iopv = get_extras('unit_net_value', etf_code, 
                         start_date=context.previous_date, 
                         end_date=context.previous_date).iloc[-1].values[0]
        
        if iopv is not None and iopv != 0:
            premium_rate = (etf_price - iopv) / iopv * 100
        else:
            premium_rate = 0
        
        return premium_rate
    except Exception as e:
        return 0

# ==================== 小市值399100策略 ====================
def small_cap_weekly_adjust(context):
    """周二调仓"""
    config = SMALL_CAP_CONFIG
    
    # 空仓月份处理
    if g.small_cap['no_trading_today']:
        if len(g.strategy_holdings['small_cap']) > 0 and not g.small_cap['no_trading_hold_signal']:
            for stock in g.strategy_holdings['small_cap'][:]:
                if stock in context.portfolio.positions:
                    pos = context.portfolio.positions[stock]
                    strategy_close_position(context, 'small_cap', pos)
            
            # 买入空仓期持有品种
            small_cap_buy_stocks(context, config['no_trading_buy'])
            g.small_cap['no_trading_hold_signal'] = True
        return
    
    # 正常调仓
    if g.small_cap['no_trading_hold_signal']:
        for stock in g.strategy_holdings['small_cap'][:]:
            if stock in context.portfolio.positions:
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
        g.small_cap['no_trading_hold_signal'] = False
    
    # 清空记录
    g.small_cap['not_buy_again'] = []
    
    # 获取目标股票池
    g.small_cap['target_list'] = small_cap_get_stocks(context)
    target_list = g.small_cap['target_list'][:config['stock_num']*2]
    
    log.info(f"[小市值] 目标池: {target_list}")
    
    # 卖出不在目标池的股票
    for stock in g.strategy_holdings['small_cap'][:]:
        if (stock not in target_list) and (stock not in g.small_cap['yesterday_hl_list']):
            if stock in context.portfolio.positions:
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
                log.info(f"[小市值] 卖出 {stock}")
        else:
            log.info(f"[小市值] 持有 {stock}")
    
    # 买入
    small_cap_buy_stocks(context, target_list)
    
    # 记录已买入
    g.small_cap['not_buy_again'] = g.strategy_holdings['small_cap'][:]


def small_cap_get_stocks(context):
    """小市值选股"""
    config = SMALL_CAP_CONFIG
    
    # 获取指数成分股
    initial_list = get_index_stocks(config['market_index'])
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    
    # 按流通市值排序
    q = query(
        valuation.code
    ).filter(
        valuation.code.in_(initial_list)
    ).order_by(
        valuation.circulating_market_cap.asc()
    ).limit(200)
    initial_list = list(get_fundamentals(q).code)
    
    # 过滤涨跌停
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    
    # 按总市值排序
    q = query(
        valuation.code, 
        indicator.eps
    ).filter(
        valuation.code.in_(initial_list)
    ).order_by(
        valuation.market_cap.asc()
    )
    df = get_fundamentals(q)
    stock_list = list(df.code)[:100]
    
    # 行业分散
    stock_list = small_cap_get_stock_industry(stock_list)
    final_list = stock_list[:config['stock_num']*2]
    
    log.info(f'[小市值] 今日前10: {final_list}')
    return final_list

def small_cap_get_stock_industry(stocks):
    """行业分散选股"""
    result = get_industry(security=stocks)
    selected_stocks = []
    industry_list = []
    
    for stock_code, info in result.items():
        industry_name = info['sw_l2']['industry_name']
        if industry_name not in industry_list:
            industry_list.append(industry_name)
            selected_stocks.append(stock_code)
            if len(industry_list) == 10:
                break
    return selected_stocks

def small_cap_check_no_trading_month(context):
    """检查空仓月份并买入指定ETF"""
    if not g.small_cap['no_trading_today']:
        # 非空仓月份，如果持有空仓ETF则清仓
        if g.small_cap['no_trading_hold_signal']:
            no_trading_etf = SMALL_CAP_CONFIG['no_trading_buy']
            for etf in no_trading_etf:
                if etf in g.strategy_holdings['small_cap'] and etf in context.portfolio.positions:
                    pos = context.portfolio.positions[etf]
                    strategy_close_position(context, 'small_cap', pos)
                    log.info(f"[小市值] 退出空仓月份，卖出 {etf}")
            g.small_cap['no_trading_hold_signal'] = False
        return
    
    # 空仓月份逻辑
    no_trading_etf = SMALL_CAP_CONFIG['no_trading_buy']
    has_no_trading_etf = False
    for etf in no_trading_etf:
        if etf in g.strategy_holdings['small_cap']:
            has_no_trading_etf = True
            break

    # 如果没有持有空仓期ETF，则买入
    if not has_no_trading_etf:
        log.info("[小市值] 空仓月份，买入指定ETF")
        small_cap_buy_stocks(context, no_trading_etf)
        g.small_cap['no_trading_hold_signal'] = True



def small_cap_buy_stocks(context, target_list, cash=0, buy_number=0):
    """小市值买入"""
    config = SMALL_CAP_CONFIG
    
    position_count = len(g.strategy_holdings['small_cap'])
    target_num = config['stock_num']
    
    # 筛选符合条件的股票
    qualified_stocks = [s for s in target_list if s not in g.strategy_holdings['small_cap']]
    if not qualified_stocks:
        return
    
    # ✅ 计算可用资金
    if cash == 0:
        strategy_total = context.portfolio.total_value * STRATEGY_ALLOCATION['small_cap']
        current_holdings_value = sum([
            context.portfolio.positions[s].value 
            for s in g.strategy_holdings['small_cap']
            if s in context.portfolio.positions
        ])
        cash = max(0, strategy_total - current_holdings_value)
    
    if buy_number == 0:
        buy_number = target_num
    
    bought_num = 0
    
    if target_num > position_count and cash > 0:
        value = cash / (target_num - position_count)
        for stock in qualified_stocks:
            if stock not in g.strategy_holdings['small_cap']:
                if bought_num < buy_number:
                    if strategy_open_position(context, 'small_cap', stock, value):
                        g.small_cap['not_buy_again'].append(stock)
                        bought_num += 1
                        if len(g.strategy_holdings['small_cap']) == target_num:
                            break

def small_cap_stoploss(context):
    """小市值止损"""
    strategy = g.small_cap
    config = SMALL_CAP_CONFIG
    
    if not config['run_stoploss']:
        return
    
    stoploss_type = config['stoploss_strategy']
    stock_df = get_price(
        security=get_index_stocks(config['market_index']),
        end_date=context.previous_date,
        frequency='daily',
        fields=['close', 'open'],
        count=1, panel=False
    )
    down_ratio = (stock_df['close'] / stock_df['open']).mean()
    
    if down_ratio <= config['stoploss_market']:
        strategy['reason_to_sell'] = 'stoploss'
        log.info(f"[小市值] 大盘惨跌 {down_ratio:.2%}")
        for stock in g.strategy_holdings['small_cap'][:]:
            if stock in context.portfolio.positions:
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
    else:
        for stock in g.strategy_holdings['small_cap'][:]:
            pos = context.portfolio.positions[stock]
            
            if pos.avg_cost <= 0:
                log.warning(f"[小市值] {stock} 持仓成本为0，跳过")
                continue
            
            if pos.price < pos.avg_cost * config['stoploss_limit']:
                strategy_close_position(context, 'small_cap', pos)
                log.info(f"[小市值] 止损 {stock}")
                strategy['reason_to_sell'] = 'stoploss'



def small_cap_check_afternoon(context):
    """小市值下午检查"""
    strategy = g.small_cap
    
    if strategy['no_trading_today']:
        return
    
    small_cap_check_limit_up(context)
    small_cap_check_remain(context)
    
def small_cap_check_limit_up(context):
    """检查涨停股"""
    strategy = g.small_cap
    now_time = context.current_dt
    
    if not strategy['yesterday_hl_list']:
        return
    
    for stock in strategy['yesterday_hl_list'][:]:
        if stock not in g.strategy_holdings['small_cap']:
            continue
        
        if stock not in context.portfolio.positions:
            continue
        
        pos = context.portfolio.positions[stock]
        if pos.closeable_amount <= 0:
            continue
        
        current_data = get_price(
            stock, end_date=now_time,
            frequency='1m', fields=['close', 'high_limit'],
            count=1, panel=False, fill_paused=True
        )
        
        if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
            log.info(f"[小市值] 涨停打开 {stock}")
            strategy_close_position(context, 'small_cap', pos)
            strategy['reason_to_sell'] = 'limitup'

def small_cap_check_remain(context):
    """检查余额补仓"""
    strategy = g.small_cap
    config = SMALL_CAP_CONFIG
    
    if strategy['reason_to_sell'] == 'limitup':
        if len(g.strategy_holdings['small_cap']) < config['stock_num']:
            target_list = small_cap_get_stocks(context)
            target_list = [s for s in target_list if s not in strategy['not_buy_again']]
            target_list = target_list[:min(config['stock_num'], len(target_list))]
            log.info(f"[小市值] 补仓 {target_list}")
            small_cap_buy_stocks(context, target_list)
        
        strategy['reason_to_sell'] = ''
    else:
        strategy['reason_to_sell'] = ''

def small_cap_close_account(context):
    """小市值清仓检查"""
    strategy = g.small_cap
    
    if not strategy['no_trading_today']:
        return
    
    if len(g.strategy_holdings['small_cap']) > 0:
        for stock in g.strategy_holdings['small_cap'][:]:
            if stock in context.portfolio.positions:
                if stock in SMALL_CAP_CONFIG['no_trading_buy']:
                    continue
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
        
        # 买入空仓期持有品种
        if SMALL_CAP_CONFIG['no_trading_buy']:
            small_cap_buy_stocks(context, SMALL_CAP_CONFIG['no_trading_buy'])


def small_cap_prepare(context):
    """小市值准备（已在daily_prepare中处理）"""
    pass


# ==================== 大小择时白马策略 ====================

def white_horse_prepare(context):
    """白马策略准备（已在daily_prepare中处理）"""
    pass

def white_horse_signal(context):
    """白马策略月度信号生成"""
    strategy = g.white_horse
    config = WHITE_HORSE_CONFIG
    
    today = context.current_dt
    dt_last = context.previous_date
    N = config['recent_days']
    
    # 获取大盘股(沪深300前20)
    B_stocks = get_index_stocks('000300.XSHG', dt_last)
    B_stocks = filter_kcbj_stock(B_stocks)
    B_stocks = filter_st_stock(B_stocks)
    B_stocks = filter_new_stock(context, B_stocks)
    
    q = query(
        valuation.code, 
        valuation.circulating_market_cap
    ).filter(
        valuation.code.in_(B_stocks)
    ).order_by(
        valuation.circulating_market_cap.desc()
    ).limit(20)
    Blst = list(get_fundamentals(q).code)
    
    # 获取小盘股(创业板指后20)
    S_stocks = get_index_stocks('399101.XSHE', dt_last)
    S_stocks = filter_kcbj_stock(S_stocks)
    S_stocks = filter_st_stock(S_stocks)
    S_stocks = filter_new_stock(context, S_stocks)
    
    q = query(
        valuation.code, 
        valuation.circulating_market_cap
    ).filter(
        valuation.code.in_(S_stocks)
    ).order_by(
        valuation.circulating_market_cap.asc()
    ).limit(20)
    Slst = list(get_fundamentals(q).code)
    
    # 计算大盘股表现
    B_ratio = get_price(Blst, end_date=dt_last, frequency='1d', 
                       fields=['close'], count=N, panel=False)
    B_ratio = B_ratio.pivot(index='time', columns='code', values='close')
    change_BIG = (B_ratio.iloc[-1] / B_ratio.iloc[0] - 1) * 100
    A1 = np.array(change_BIG)
    A1 = np.nan_to_num(A1)
    B_mean = np.mean(A1)
    
    # 计算小盘股表现
    S_ratio = get_price(Slst, end_date=dt_last, frequency='1d', 
                       fields=['close'], count=N, panel=False)
    S_ratio = S_ratio.pivot(index='time', columns='code', values='close')
    change_SMALL = (S_ratio.iloc[-1] / S_ratio.iloc[0] - 1) * 100
    A1 = np.array(change_SMALL)
    A1 = np.nan_to_num(A1)
    S_mean = np.mean(A1)
    
    # 信号判断
    old_signal = strategy['signal']
    if B_mean > S_mean and B_mean > 0:
        if B_mean > 5:
            strategy['signal'] = 'small'
            log.info('[白马] 大市值到头，切换小盘')
        else:
            strategy['signal'] = 'big'
            log.info('[白马] 大盘占优')
    elif B_mean < S_mean and S_mean > 0:
        strategy['signal'] = 'small'
        log.info('[白马] 小盘占优')
    else:
        log.info('[白马] 切换外盘ETF')
        strategy['signal'] = 'etf'
    
    if old_signal != strategy['signal']:
        log.info(f"[白马] 信号变化: {old_signal} -> {strategy['signal']}")

def white_horse_adjust(context):
    """白马策略调仓"""
    strategy = g.white_horse
    config = WHITE_HORSE_CONFIG
    
    # 根据信号选股
    if strategy['signal'] == 'big':
        target_list = white_horse_select_big(context)
    elif strategy['signal'] == 'small':
        target_list = white_horse_select_small(context)
    else:
        target_list = config['foreign_etfs']
    
    # 过滤
    target_list = filter_limitup_stock(context, target_list)
    target_list = filter_limitdown_stock(context, target_list)
    target_list = filter_paused_stock(target_list)
    
    for stock in g.strategy_holdings['white_horse'][:]:
        if (stock not in target_list) and (stock not in strategy['yesterday_limit_up']):
            if stock in context.portfolio.positions:
                position = context.portfolio.positions[stock]
                strategy_close_position(context, 'white_horse', position)
    
    # 买入逻辑
    position_count = len(g.strategy_holdings['white_horse'])
    target_buy_count = config['buy_stock_count'] - position_count
    
    if target_buy_count > 0:
        strategy_total = context.portfolio.total_value * STRATEGY_ALLOCATION['white_horse']
        current_holdings_value = sum([
            context.portfolio.positions[s].value 
            for s in g.strategy_holdings['white_horse']
            if s in context.portfolio.positions
        ])
        available = max(0, strategy_total - current_holdings_value)
        if available > 0:
            value_per_stock = available / target_buy_count
            bought_count = 0
            log.info(f"[白马] 可用金额: {available} ，每只股票分配资金：{value_per_stock} 当前持仓 {current_holdings_value}")
            for stock in target_list:
                if stock not in g.strategy_holdings['white_horse']:
                    if strategy_open_position_add(context, 'white_horse', stock, value_per_stock):
                        bought_count += 1
                        if bought_count >= target_buy_count:
                            break



def white_horse_select_big(context):
    """白马股选股（大盘）"""
    strategy = g.white_horse
    config = WHITE_HORSE_CONFIG
    
    white_horse_assess_market_temp(context)
    all_stocks = get_index_stocks("000300.XSHG")
    
    # 基础过滤
    all_stocks = [s for s in all_stocks if not (
        get_current_data()[s].paused or
        get_current_data()[s].is_st or
        'ST' in get_current_data()[s].name or
        '*' in get_current_data()[s].name or
        '退' in get_current_data()[s].name or
        s.startswith(('30', '68', '8', '4'))
    )]
    
    if strategy['market_temp'] == "cold":
        q = query(
            valuation.code
        ).filter(
            valuation.pb_ratio.between(0, 1),
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit > 2.0,
            indicator.inc_return > 1.5,
            indicator.inc_net_profit_year_on_year > -15,
            valuation.code.in_(all_stocks)
        ).order_by(
            (indicator.roa/valuation.pb_ratio).desc()
        ).limit(config['stock_num'] + 1)
    
    elif strategy['market_temp'] == "warm":
        q = query(
            valuation.code
        ).filter(
            valuation.pb_ratio.between(0, 1),
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit > 1.0,
            indicator.inc_return > 2.0,
            indicator.inc_net_profit_year_on_year > 0,
            valuation.code.in_(all_stocks)
        ).order_by(
            (indicator.roa/valuation.pb_ratio).desc()
        ).limit(config['stock_num'] + 1)
    
    else:  # hot
        q = query(
            valuation.code
        ).filter(
            valuation.pb_ratio > 3,
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit > 0.5,
            indicator.inc_return > 3.0,
            indicator.inc_net_profit_year_on_year > 20,
            valuation.code.in_(all_stocks)
        ).order_by(
            indicator.roa.desc()
        ).limit(config['stock_num'] + 1)
    
    return list(get_fundamentals(q).code)

def white_horse_select_small(context):
    """小盘股选股"""
    config = WHITE_HORSE_CONFIG
    
    stocks = get_index_stocks('399101.XSHE')
    stocks = filter_kcbj_stock(stocks)
    stocks = filter_st_stock(stocks)
    stocks = filter_new_stock(context, stocks)
    
    # 两步选股法
    q1 = query(
        valuation.code, 
        valuation.market_cap
    ).filter(
        valuation.code.in_(stocks),
        valuation.market_cap.between(5, 60)
    ).order_by(
        valuation.market_cap.asc()
    ).limit(100)
    df_fun = get_fundamentals(q1)
    initial_list = list(df_fun.code)
    
    q2 = query(
        valuation.code, 
        valuation.market_cap
    ).filter(
        valuation.code.in_(initial_list)
    ).order_by(
        valuation.market_cap.asc()
    ).limit(50)
    df_fun = get_fundamentals(q2)
    final_list = list(df_fun.code)
    
    # 价格过滤
    current_data = get_current_data()
    return [s for s in final_list 
           if s in context.portfolio.positions or current_data[s].last_price <= config['max_stock_price']]

def white_horse_assess_market_temp(context):
    """市场温度评估"""
    strategy = g.white_horse
    
    index300 = attribute_history('000300.XSHG', 220, '1d', ('close'), df=False)['close']
    market_height = (np.mean(index300[-5:]) - min(index300)) / (max(index300) - min(index300))
    
    old_temp = strategy['market_temp']
    if market_height < 0.20:
        strategy['market_temp'] = "cold"
    elif market_height > 0.90:
        strategy['market_temp'] = "hot"
    elif max(index300[-60:]) / min(index300) > 1.20:
        strategy['market_temp'] = "warm"
    
    if old_temp != strategy['market_temp']:
        log.info(f"[白马] 市场温度: {old_temp} -> {strategy['market_temp']}")
    
    if context.run_params.type != 'sim_trade':
        temp_value = 200 if strategy['market_temp'] == "cold" else \
                    300 if strategy['market_temp'] == "warm" else 400

def white_horse_stop_loss(context):
    """白马策略止损"""
    strategy = g.white_horse
    config = WHITE_HORSE_CONFIG
    
    num = 0
    now_time = context.current_dt
    
    current_hold_list = g.strategy_holdings['white_horse'][:]
    current_limit_up_list = strategy['yesterday_limit_up'][:]
    
    # 检查昨日涨停股
    if current_limit_up_list:
        for stock in current_limit_up_list:
            if stock not in context.portfolio.positions:
                continue
            
            current_data = get_price(stock, end_date=now_time, frequency='1m',
                                   fields=['close', 'high_limit'], count=1, panel=False)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info(f"[白马] 涨停打开 {stock}")
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'white_horse', pos)
                num += 1
    
    # 普通止损
    SS = []
    S = []
    for stock in current_hold_list:
        if stock not in context.portfolio.positions:
            continue
        
        pos = context.portfolio.positions[stock]
        
        if pos.avg_cost <= 0:
            log.warning(f"[白马] {stock} 持仓成本为0，跳过止损检查")
            continue
        
        if pos.price < pos.avg_cost * config['stop_loss_ratio']:
            strategy_close_position(context, 'white_horse', pos)
            log.info(f"[白马] 止损 {stock}")
            num += 1
        else:
            S.append(stock)
            ret = (pos.price - pos.avg_cost) / pos.avg_cost
            SS.append(ret)
    
    # ========== 补跌逻辑 ==========
    if num >= 1 and len(SS) > 0:
        rebound_num = min(3, len(SS))
        worst = sorted(zip(SS, S))[:rebound_num]
        
        # 计算可用现金
        total_available_cash = context.portfolio.available_cash
        strategy_available_cash = total_available_cash * STRATEGY_ALLOCATION['white_horse']
        
        if strategy_available_cash > 0:
            cash_per_stock = strategy_available_cash / rebound_num
            for perf, stock in worst:
                if stock not in strategy['rebound_stocks']:
                    # 记录补跌前的持仓数量
                    pos = context.portfolio.positions[stock]
                    original_amount = pos.total_amount
                    
                    order = strategy_open_position_add(context,'white_horse', stock, cash_per_stock)
                    if order and order.filled > 0:
                        # 记录补跌增加的数量（而非金额）
                        added_amount = order.filled
                        strategy['rebound_stocks'][stock] = {
                            'original_amount': original_amount,
                            'added_amount': added_amount
                        }
                        log.info(f"[白马] 补跌买入 {stock} 数量:{added_amount} 金额:{cash_per_stock:.0f}")


def white_horse_clear_rebound(context):
    """清理补跌股票"""
    strategy = g.white_horse
    
    if strategy['rebound_stocks']:
        strategy['rebound_stocks'].clear()
        
        
# ==================== 通用工具函数 ====================
def filter_new_stock(context, stock_list):
    """过滤次新股"""
    yesterday = context.previous_date
    return [stock for stock in stock_list 
           if (yesterday - get_security_info(stock).start_date) >= datetime.timedelta(days=375)]

def filter_kcbj_stock(stock_list):
    """过滤科创北交股票"""
    return [s for s in stock_list if not s.startswith(('30', '68', '8', '4'))]

def filter_st_stock(stock_list):
    """过滤ST股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list
           if not current_data[stock].is_st
           and 'ST' not in current_data[stock].name
           and '*' not in current_data[stock].name
           and '退' not in current_data[stock].name]

def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_limitup_stock(context, stock_list):
    """过滤涨停股票"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
           if stock in context.portfolio.positions.keys()
           or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    """过滤跌停股票"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
           if stock in context.portfolio.positions.keys()
           or last_prices[stock][-1] > current_data[stock].low_limit]

def is_no_trading_month(context):
    """判断是否为空仓月份"""
    if not SMALL_CAP_CONFIG['pass_april']:
        return False
    today = context.current_dt.strftime('%m-%d')
    return (('04-01' <= today <= '04-30') or 
            ('01-01' <= today <= '01-30'))
