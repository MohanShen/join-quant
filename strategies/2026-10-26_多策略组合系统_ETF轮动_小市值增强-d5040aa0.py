# Clone from JoinQuant
# postId: d5040aa00b1168d9c0926f68ba673b8d
# backtestId: 064331ec67e5f803d7055c456e474785
# title: 多策略组合系统：ETF轮动 + 小市值增强

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

# ==================== 全局配置（集中管理所有参数） ====================
# 策略资金分配
STRATEGY_ALLOCATION = {
    'etf': 0.5,          # ETF轮动资金占比
    'small_cap': 0.5,    # 小市值策略资金占比
}

# ==================== ETF轮动策略配置 ====================
ETF_CONFIG = {
    'etf_pool': [
        "159915.XSHE",  # 创业板ETF（易方达）
        "510180.XSHG",  # 上证180ETF（华安）
        "513030.XSHG",  # 德国DAX ETF（华安）
        "513100.XSHG",  # 纳指ETF（国泰）
        "513520.XSHG",  # 日经225ETF（华夏）
        "510410.XSHG",  # 上证自然资源ETF（博时）
        "518880.XSHG",  # 黄金ETF（华安）
        "501018.XSHG",  # 南方原油LOF（南方）
        "159985.XSHE",  # 豆粕期货ETF（华夏）
    ],
    'target_num': 1,                 # 持仓ETF数量
    'momentum_days': 25,             # 动量计算周期（固定25天）
    'premium_threshold': 5.0,        # ETF溢价率阈值（超过则扣分）
    'min_score': 0,                  # 最小动量得分
    'max_score': 6,                  # 最大动量得分
    'price_drop_threshold': 0.96,    # 价格下跌阈值
}

# ==================== 小市值策略配置 ====================
SMALL_CAP_CONFIG = {
    'market_index': '399100.XSHE',   # 参考指数
    'stock_num': 6,                  # 持仓股票数量
    'up_price': 50,                  # 最高股价限制
    'pass_april': True,              # 1/4月空仓
    'run_stoploss': True,            # 是否启用止损
    'stoploss_strategy': 3,          # 止损策略类型
    'stoploss_limit': 0.92,          # 个股止损阈值
    'stoploss_market': 0.96,         # 大盘止损阈值
    'no_trading_buy': ['511010.XSHG'], # 空仓期持有标的
    'turnover_threshold': 0.01,     # 换手率阈值（过滤极低换手）
    'turnover_days': 5,             # 换手率计算周期
    'new_stock_days': 375,           # 次新股过滤天数
}

# ==================== 初始化函数 ====================
def initialize(context):
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_benchmark('000300.XSHG')
    
    # 股票交易成本设置
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=1/10000, close_commission=1/10000,
        close_today_commission=0, min_commission=5
    ), type='stock')
    
    # 基金交易成本设置
    set_slippage(FixedSlippage(0.0001), type='fund')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.0002, close_commission=0.0002,
        close_today_commission=0, min_commission=1
    ), type='fund')
    
    # 日志级别设置
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    
    # 初始化全局变量
    init_globals(context)
    
    # 调度任务
    schedule_tasks(context)
    
    # 初始化完成日志
    log.info("=" * 80)
    log.info("多策略组合系统初始化完成")
    log.info(f"ETF轮动: {STRATEGY_ALLOCATION['etf']:.0%} | "
             f"小市值: {STRATEGY_ALLOCATION['small_cap']:.0%}")
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
    }
    
    # 初始资金(用于计算收益率)
    g.strategy_starting_cash = {
        'etf': initial_cash * STRATEGY_ALLOCATION['etf'],
        'small_cap': initial_cash * STRATEGY_ALLOCATION['small_cap'],
    }
    
    # 各策略持仓列表
    g.strategy_holdings = {
        'etf': [],
        'small_cap': [],
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

def schedule_tasks(context):
    """调度任务"""
    run_daily(daily_prepare, '9:05')
    
    # ETF轮动任务
    if STRATEGY_ALLOCATION['etf'] > 0:
        run_daily(etf_trade, '9:31')
    
    # 小市值策略任务
    if STRATEGY_ALLOCATION['small_cap'] > 0:
        run_daily(small_cap_check_no_trading_month, '9:35')
        run_daily(small_cap_stoploss, '10:00')
        run_weekly(small_cap_weekly_adjust, 2, '10:30')  # 周二调仓
        run_daily(small_cap_check_afternoon, '14:25')
        run_daily(small_cap_check_afternoon, '14:55')
        run_daily(small_cap_close_account, '14:50')

def daily_prepare(context):
    """每日开盘前准备"""
    log.info(f"{'='*30}{context.current_dt.strftime('%Y-%m-%d')} 开盘准备{'='*30}")
    
    # 更新持仓列表
    for strategy_name in ['etf', 'small_cap']:
        g.strategy_holdings[strategy_name] = []
    
    for stock in context.portfolio.positions.keys():
        strategy = g.stock_strategy.get(stock)
        if strategy:
            g.strategy_holdings[strategy].append(stock)
    
    # 小市值：昨日涨停股票更新
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
    
    # 检查是否为空仓月份
    g.small_cap['no_trading_today'] = is_no_trading_month(context)

# ==================== 策略专用交易函数 ====================
def strategy_open_position(context, strategy_name, security, value):
    """策略买入"""
    # 计算该策略可用资金
    strategy_total = context.portfolio.total_value * STRATEGY_ALLOCATION[strategy_name]
    current_holdings_value = sum([
        context.portfolio.positions[s].value 
        for s in g.strategy_holdings[strategy_name]
        if s in context.portfolio.positions
    ])
    available = max(0, strategy_total - current_holdings_value)
    
    # 调整买入金额（不超过可用资金）
    if value > available:
        value = available * 0.95
    
    # 最小交易金额检查
    current_price = get_current_data()[security].last_price
    if value < current_price * 100:
        return False
    
    # 执行买入
    order = order_target_value(security, value)
    if order and order.filled > 0:
        g.stock_strategy[security] = strategy_name
        g.strategy_holdings[strategy_name].append(security)
        log.info(f"[{strategy_name}] 买入 {security} 数量:{order.filled} 金额:{value:.0f}")
        return True
    return False

def strategy_open_position_add(context, strategy_name, security, value):
    """策略加仓"""
    order = order_value(security, value)
    if order and order.filled > 0:
        g.stock_strategy[security] = strategy_name
        if value > 0 and security not in g.strategy_holdings[strategy_name]:
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
        
        # 清理持仓记录
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
    
    # 获取目标ETF列表（固定25天动量）
    target_list, rank_info = etf_get_rank_fixed(context, return_info=True)
    target_list = target_list[:config['target_num']]
    
    # 打印动量排行
    if rank_info:
        log.info("[ETF轮动] 动量评分排行:")
        for i, (etf, score) in enumerate(rank_info[:5], 1):
            etf_name = get_security_info(etf).display_name
            log.info(f"  {i}. {etf} {etf_name:10s} 得分:{score:.4f}")

    if not target_list:
        log.warning("[ETF轮动] 无符合条件的标的")
        return
    
    # 获取当前持仓
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
    """固定25天周期动量评分（移除ATR计算）"""
    config = ETF_CONFIG
    data = pd.DataFrame(index=config['etf_pool'], 
                       columns=["annualized_returns", "r2", "score"])
    current_data = get_current_data()
    
    for etf in config['etf_pool']:
        try:
            # 获取固定25天的价格数据
            df = attribute_history(etf, config['momentum_days'], "1d", ["close", "high"])
            if len(df) < config['momentum_days']:
                continue
            
            # 拼接最新价格
            prices = np.append(df["close"].values, current_data[etf].last_price)
            
            # 计算带权重的线性回归
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))  # 近期价格权重更高
            
            # 计算斜率和R²
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            annualized_returns = math.exp(slope * 250) - 1  # 年化收益率
            
            # 计算决定系数R²
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot else 0
            
            # 最终得分 = 年化收益率 * 决定系数
            score = annualized_returns * r2
            
            # 价格暴跌惩罚
            if len(prices) >= 4:
                if min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < config['price_drop_threshold']:
                    score = 0
            
            # 高溢价惩罚
            premium_rate = get_etf_premium_rate(context, etf)
            if premium_rate >= config['premium_threshold']:
                score -= 1
            
            # 保存计算结果
            data.loc[etf, "annualized_returns"] = annualized_returns
            data.loc[etf, "r2"] = r2
            data.loc[etf, "score"] = score
                
        except Exception as e:
            log.warning(f"[ETF轮动] {etf} 计算失败: {str(e)}")
            continue
    
    # 过滤有效得分并排序
    data = data.query(f"{config['min_score']} < score < {config['max_score']}").sort_values(by="score", ascending=False)
    
    if return_info:
        rank_info = [(idx, row['score']) for idx, row in data.iterrows()]
        return data.index.tolist(), rank_info
    return data.index.tolist()

def get_etf_premium_rate(context, etf_code):
    """计算ETF溢价率"""
    try:
        # 获取前一日收盘价
        etf_price = get_price(etf_code, start_date=context.previous_date, 
                             end_date=context.previous_date).iloc[-1]['close']
        # 获取前一日IOPV
        iopv = get_extras('unit_net_value', etf_code, 
                         start_date=context.previous_date, 
                         end_date=context.previous_date).iloc[-1].values[0]
        
        if iopv is not None and iopv != 0:
            premium_rate = (etf_price - iopv) / iopv * 100
        else:
            premium_rate = 0
        
        return premium_rate
    except Exception as e:
        log.warning(f"[ETF轮动] {etf_code} 溢价率计算失败: {str(e)}")
        return 0

# ==================== 小市值399100策略 ====================
def small_cap_weekly_adjust(context):
    """周二调仓"""
    config = SMALL_CAP_CONFIG
    
    # 空仓月份处理
    if g.small_cap['no_trading_today']:
        if len(g.strategy_holdings['small_cap']) > 0 and not g.small_cap['no_trading_hold_signal']:
            # 清空小市值持仓
            for stock in g.strategy_holdings['small_cap'][:]:
                if stock in context.portfolio.positions:
                    pos = context.portfolio.positions[stock]
                    strategy_close_position(context, 'small_cap', pos)
            
            # 买入空仓期持有品种
            small_cap_buy_stocks(context, config['no_trading_buy'])
            g.small_cap['no_trading_hold_signal'] = True
        return
    
    # 退出空仓期，清空空仓标的
    if g.small_cap['no_trading_hold_signal']:
        for stock in g.strategy_holdings['small_cap'][:]:
            if stock in context.portfolio.positions:
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
        g.small_cap['no_trading_hold_signal'] = False
    
    # 清空不再买入的股票列表
    g.small_cap['not_buy_again'] = []
    
    # 获取目标股票池（包含换手率过滤）
    g.small_cap['target_list'] = small_cap_get_stocks(context)
    target_list = g.small_cap['target_list'][:config['stock_num']*2]
    
    log.info(f"[小市值] 目标池: {target_list}")
    
    # 卖出不在目标池且非昨日涨停的股票
    for stock in g.strategy_holdings['small_cap'][:]:
        if (stock not in target_list) and (stock not in g.small_cap['yesterday_hl_list']):
            if stock in context.portfolio.positions:
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
                log.info(f"[小市值] 卖出 {stock}")
        else:
            log.info(f"[小市值] 持有 {stock}")
    
    # 买入新标的
    small_cap_buy_stocks(context, target_list)
    
    # 记录已买入股票
    g.small_cap['not_buy_again'] = g.strategy_holdings['small_cap'][:]

def small_cap_get_stocks(context):
    """小市值选股（增加换手率过滤）"""
    config = SMALL_CAP_CONFIG
    
    # 获取指数成分股
    initial_list = get_index_stocks(config['market_index'])
    
    # 基础过滤
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    
    # 过滤低换手率股票
    initial_list = filter_low_turnover_stock(context, initial_list)
    
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

def filter_low_turnover_stock(context, stock_list):
    """过滤极低换手率股票"""
    config = SMALL_CAP_CONFIG
    if not stock_list:
        return []
    
    try:
        # 获取换手率数据
        turnover_data = get_price(
            stock_list,
            end_date=context.previous_date,
            frequency='daily',
            fields=['turnover_ratio'],
            count=config['turnover_days'],
            panel=False
        )
        
        # 计算平均换手率
        turnover_mean = turnover_data.groupby('code')['turnover_ratio'].mean()
        
        # 过滤换手率低于阈值的股票
        high_turnover_stocks = [
            code for code in stock_list
            if code in turnover_mean.index and turnover_mean[code] >= config['turnover_threshold']
        ]
        
        log.info(f"[小市值] 换手率过滤: {len(stock_list)} -> {len(high_turnover_stocks)}")
        return high_turnover_stocks
    except Exception as e:
        log.warning(f"[小市值] 换手率过滤失败: {str(e)}")
        return stock_list

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
        # 非空仓月份，清空空仓ETF
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
    has_no_trading_etf = any(etf in g.strategy_holdings['small_cap'] for etf in no_trading_etf)

    # 买入空仓期ETF
    if not has_no_trading_etf:
        log.info("[小市值] 空仓月份，买入指定ETF")
        small_cap_buy_stocks(context, no_trading_etf)
        g.small_cap['no_trading_hold_signal'] = True

def small_cap_buy_stocks(context, target_list, cash=0, buy_number=0):
    """小市值买入"""
    config = SMALL_CAP_CONFIG
    
    position_count = len(g.strategy_holdings['small_cap'])
    target_num = config['stock_num']
    
    # 筛选未持仓的股票
    qualified_stocks = [s for s in target_list if s not in g.strategy_holdings['small_cap']]
    if not qualified_stocks:
        return
    
    # 计算可用资金
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
    
    # 执行买入
    if target_num > position_count and cash > 0:
        value = cash / (target_num - position_count)
        for stock in qualified_stocks:
            if bought_num < buy_number:
                if strategy_open_position(context, 'small_cap', stock, value):
                    g.small_cap['not_buy_again'].append(stock)
                    bought_num += 1
                    if len(g.strategy_holdings['small_cap']) == target_num:
                        break

def small_cap_stoploss(context):
    """小市值止损"""
    config = SMALL_CAP_CONFIG
    
    if not config['run_stoploss']:
        return
    
    # 计算大盘平均下跌幅度
    stock_df = get_price(
        security=get_index_stocks(config['market_index']),
        end_date=context.previous_date,
        frequency='daily',
        fields=['close', 'open'],
        count=1, panel=False
    )
    down_ratio = (stock_df['close'] / stock_df['open']).mean()
    
    # 大盘止损
    if down_ratio <= config['stoploss_market']:
        g.small_cap['reason_to_sell'] = 'stoploss'
        log.info(f"[小市值] 大盘惨跌 {down_ratio:.2%}，全仓止损")
        for stock in g.strategy_holdings['small_cap'][:]:
            if stock in context.portfolio.positions:
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
    else:
        # 个股止损
        for stock in g.strategy_holdings['small_cap'][:]:
            pos = context.portfolio.positions[stock]
            
            if pos.avg_cost <= 0:
                log.warning(f"[小市值] {stock} 持仓成本为0，跳过止损")
                continue
            
            if pos.price < pos.avg_cost * config['stoploss_limit']:
                strategy_close_position(context, 'small_cap', pos)
                log.info(f"[小市值] 个股止损 {stock}")
                g.small_cap['reason_to_sell'] = 'stoploss'

def small_cap_check_afternoon(context):
    """小市值下午检查"""
    if g.small_cap['no_trading_today']:
        return
    
    small_cap_check_limit_up(context)
    small_cap_check_remain(context)

def small_cap_check_limit_up(context):
    """检查涨停股打开"""
    if not g.small_cap['yesterday_hl_list']:
        return
    
    for stock in g.small_cap['yesterday_hl_list'][:]:
        if stock not in g.strategy_holdings['small_cap'] or stock not in context.portfolio.positions:
            continue
        
        pos = context.portfolio.positions[stock]
        if pos.closeable_amount <= 0:
            continue
        
        # 获取最新价格
        current_data = get_price(
            stock, end_date=context.current_dt,
            frequency='1m', fields=['close', 'high_limit'],
            count=1, panel=False, fill_paused=True
        )
        
        # 涨停打开则卖出
        if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
            log.info(f"[小市值] 涨停打开 {stock}，卖出")
            strategy_close_position(context, 'small_cap', pos)
            g.small_cap['reason_to_sell'] = 'limitup'

def small_cap_check_remain(context):
    """涨停打开后补仓"""
    config = SMALL_CAP_CONFIG
    
    if g.small_cap['reason_to_sell'] == 'limitup':
        if len(g.strategy_holdings['small_cap']) < config['stock_num']:
            # 获取新的目标列表（排除已买入的）
            target_list = small_cap_get_stocks(context)
            target_list = [s for s in target_list if s not in g.small_cap['not_buy_again']]
            target_list = target_list[:min(config['stock_num'], len(target_list))]
            
            log.info(f"[小市值] 涨停打开补仓 {target_list}")
            small_cap_buy_stocks(context, target_list)
        
        g.small_cap['reason_to_sell'] = ''
    else:
        g.small_cap['reason_to_sell'] = ''

def small_cap_close_account(context):
    """小市值清仓检查"""
    if not g.small_cap['no_trading_today']:
        return
    
    # 清空非空仓期标的
    for stock in g.strategy_holdings['small_cap'][:]:
        if stock in context.portfolio.positions and stock not in SMALL_CAP_CONFIG['no_trading_buy']:
            pos = context.portfolio.positions[stock]
            strategy_close_position(context, 'small_cap', pos)
    
    # 买入空仓期标的
    if SMALL_CAP_CONFIG['no_trading_buy']:
        small_cap_buy_stocks(context, SMALL_CAP_CONFIG['no_trading_buy'])

# ==================== 通用工具函数 ====================
def filter_new_stock(context, stock_list):
    """过滤次新股"""
    config = SMALL_CAP_CONFIG
    yesterday = context.previous_date
    return [
        stock for stock in stock_list 
        if (yesterday - get_security_info(stock).start_date) >= datetime.timedelta(days=config['new_stock_days'])
    ]

def filter_kcbj_stock(stock_list):
    """过滤科创北交股票"""
    return [s for s in stock_list if not s.startswith(('30', '68', '8', '4'))]

def filter_st_stock(stock_list):
    """过滤ST股票"""
    current_data = get_current_data()
    return [
        stock for stock in stock_list
        if not current_data[stock].is_st
        and 'ST' not in current_data[stock].name
        and '*' not in current_data[stock].name
        and '退' not in current_data[stock].name
    ]

def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_limitup_stock(context, stock_list):
    """过滤涨停股票"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [
        stock for stock in stock_list 
        if stock in context.portfolio.positions.keys()
        or last_prices[stock][-1] < current_data[stock].high_limit
    ]

def filter_limitdown_stock(context, stock_list):
    """过滤跌停股票"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [
        stock for stock in stock_list 
        if stock in context.portfolio.positions.keys()
        or last_prices[stock][-1] > current_data[stock].low_limit
    ]

def is_no_trading_month(context):
    """判断是否为空仓月份（1月/4月）"""
    if not SMALL_CAP_CONFIG['pass_april']:
        return False
    today = context.current_dt.strftime('%m-%d')
    return ('04-01' <= today <= '04-30') or ('01-01' <= today <= '01-30')