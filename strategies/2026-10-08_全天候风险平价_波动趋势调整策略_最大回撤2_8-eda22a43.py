# Clone from JoinQuant
# postId: eda22a433508c4527764fed0cceefffb
# backtestId: d0001fb0a98f840ee1d1282d8f081526
# title: 全天候风险平价 + 波动趋势调整策略，最大回撤2.8%

# 克隆自聚宽文章：https://www.joinquant.com/post/57565
# 标题：改良版全天候策略（目标年化大于8%最大回撤小于3%）
# 作者：1ZHXCQL

#全天候策略_风险平价_波动趋势调整

from kuanke.wizard import *
from jqdata import *
import numpy as np
import pandas as pd
import talib
import datetime
import time
import math
from six import StringIO,BytesIO
from sklearn.decomposition import PCA
from scipy.optimize import minimize

def after_code_changed(context):
    
    # ====== 初始化设定 ====== 
    # 设置基准为五年期国债ETF 511010.XSHG； 161716.XSHE 招商双债LOF
    set_benchmark('161716.XSHE') 
    # 设定滑点 
    set_slippage(FixedSlippage(0.002), type='fund')
    # True为开启动态复权模式，使用真实价格交易
    set_option('use_real_price', True)
    # 设定成交量比例
    set_option('order_volume_ratio', 1)
    # 股票类交易手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0003, 
    close_commission=0.0003, min_commission=5), type='stock')
    #避免未来函数
    set_option("avoid_future_data", True)
    # 关闭部分log
    # log.set_level('order', 'error')
    
    # ====== 全局参数变量 ====== 
    g.period_count, g.cycle_period = 20, 20 # 多少个交易日计算一次
    g.trade_threshold = 0.05 # 价值变化多少以上才调仓
    g.rebalance_threshold = 0.15 # 如果变化多少以上进行再平衡
    g.rebalance_price = {} #记录再平衡价格的字典
    g.etf_allocations = {}
    g.valid_etf_pools = []
    # g.confidence_level = 2.58 # 1.96 置信水平为95%；2.58对应99%%
    
    # ====== 定时运行函数 ====== 
    # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 开盘时运行 - 测试每周一调仓
    run_daily(market_open, time="9:33", reference_security='000300.XSHG')
    # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
def strategy_initialize(context):
    # ====== 策略核心设定 ====== 
    g.etf_pool = {
        "equity": ['510300.XSHG', '159915.XSHE'],
        # 股票类：510300.XSHG为沪深300ETF；510880.XSHG为红利ETF；
        # 159915.XSHE为创业板ETF；'512890.XSHG', #红利低波ETF
        # 510180.XSHG 上证180ETF
        "commodities": ['518880.XSHG'], 
        # 商品类：518880.XSHG 黄金ETF; 510170.XSHG 大宗商品ETF 
        "bonds": ['161716.XSHE'], 
        # 债券类：511010为5年期国债ETF；511260为10年期国债ETF；
        # 511090.XSHG, 30年国债；511360.XSHG	短融ETF
        "foreign_equity": ['513100.XSHG'] 
        # 美股类：513100.XSHG 纳指ETF; 159655.XSHE 标普ETF；
        # 513500.XSHG 成立时间更早的博时标普
    }
    g.equity_etfs = set(g.etf_pool.get("equity", [])) | set(g.etf_pool.get("foreign_equity", []))

def before_market_open(context):
    strategy_initialize(context)

def get_ES(stock, lag=120):
    
    hStocks = history(lag, '1d', 'close', stock, df=True)
    daily_returns = hStocks.resample('D').last().pct_change().fillna(value=0, method=None, axis=0).iloc[:, 0].values
    sorted_returns = sorted(daily_returns)

    a = 1 - 0.90 # 置信水平调整 
    count = 0
    sum_value = 0
    for i in range(len(sorted_returns)):
        if i < (lag * a):
            sum_value += sorted_returns[i] # 不是完全严谨，可能为正，但总ES应该还是负的
            count += 1
    if count == 0:
        ES = 0
    else:
        ES = -(sum_value / (lag * a))
     
    # 波动率调整
    price_data = history(250, '1d', 'close', stock, df=True)
    daily_returns = price_data.resample('D').last().pct_change().fillna(value=0, method=None, axis=0).iloc[:, 0].values
    
    short_vol = pd.Series(daily_returns).rolling(10).std().iloc[-1] * np.sqrt(252)
    long_vol = pd.Series(daily_returns).std() * np.sqrt(252)
    short_vol = short_vol.item() if isinstance(short_vol, pd.Series) else short_vol
    long_vol = long_vol.item() if isinstance(long_vol, pd.Series) else long_vol
    
    adjustment_factor = short_vol / long_vol if long_vol > 0 else 1
    ES *= adjustment_factor
    
    if stock in g.equity_etfs:
        # 趋势调整
        score = get_ETF_momentum(stock)
        adjusted_ES = adjust_ES(ES, score)
        log.info(f'{stock}的动量得分为{score}，调整前ES为{ES}，趋势调整后ES为{adjusted_ES}')
        return adjusted_ES
    else:
        log.info(f'{stock}的ES为{ES}')
        return ES

def get_portfolio_ES(asset_class, stock_list, weights, lag=120):
    
    hStocks = history(lag, '1d', 'close', stock_list, df=True)
    daily_returns = hStocks.resample('D').last().pct_change().fillna(value=0, method=None, axis=0).values
    weight_vector = np.array([weights.get(stock, 0) for stock in stock_list]).reshape(-1, 1)
    portfolio_returns = daily_returns.dot(weight_vector).squeeze()
    sorted_returns = sorted(portfolio_returns)

    a = 1 - 0.90 # 置信水平调整 
    count = 0
    sum_value = 0
    for i in range(len(sorted_returns)):
        if i < (lag * a):
            sum_value += sorted_returns[i] # 不是完全严谨，可能为正，但总ES应该还是负的
            count += 1
    if count == 0:
        ES = 0
    else:
        ES = -(sum_value / (lag * a))
   
    # 波动率调整
    price_data = history(250, '1d', 'close', stock_list, df=True)
    daily_returns = price_data.resample('D').last().pct_change().fillna(value=0, method=None, axis=0).values
    weight_vector = np.array([weights.get(stock, 0) for stock in stock_list]).reshape(-1, 1)
    
    portfolio_returns = np.dot(daily_returns, weight_vector).squeeze()
    portfolio_returns_series = pd.Series(portfolio_returns)
    
    short_vol = portfolio_returns_series.rolling(10).std().iloc[-1] * np.sqrt(252)
    long_vol = portfolio_returns_series.std() * np.sqrt(252)
    short_vol = short_vol.item() if isinstance(short_vol, pd.Series) else short_vol
    long_vol = long_vol.item() if isinstance(long_vol, pd.Series) else long_vol
    
    adjustment_factor = short_vol / long_vol if long_vol > 0 else 1
    ES *= adjustment_factor
    
    # 趋势调整
    if asset_class in ['equity', 'foreign_equity']:
        score = get_portfolio_momentum(stock_list)
        adjusted_ES = adjust_ES(ES,score)  
        log.info(f'{stock_list}的动量得分为{score}，调整前ES为{ES}，趋势调整后ES为{adjusted_ES}')
        return adjusted_ES
    else:
        return ES
        log.info(f'{stock_list}的ES为{ES}')

def calculate_asset_class_ES(context, etf_pool):

    asset_ES = {}
    etf_ES = {}
    valid_etf_pools = {}
    today = context.current_dt.date()

    for asset_class, stock_list in etf_pool.items():
        valid_etfs = []  # 存放符合条件的 ETF
        
        #计算每个ETF的ES
        for stock in stock_list:
            start_date = get_security_info(stock).start_date
            if start_date is None:
                log.info(f"{stock} 无法获取成立时间，忽略该 ETF")
                continue
            elif (today - start_date).days > 125:
                valid_etfs.append(stock)
            elif (today - start_date).days <= 125:
                log.info(f"{stock} 成立时间不足125天，暂不纳入 ES 计算")
        
        # 存储 valid_etfs 到 valid_etf_pools
        valid_etf_pools[asset_class] = valid_etfs
        
        # 如果该资产类别下没有足够久的 ETF，ES 设为 NaN
        if not valid_etfs:
            log.info(f"{asset_class} 下没有 ETF 满足历史数据要求，ES 设为 NaN")
            asset_ES[asset_class] = np.nan
            continue
        
        #计算大类资产的ES
        etf_ES_values = {}
        for stock in valid_etfs:
            etf_ES_values[stock] = get_ES(stock)
        etf_ES.update(etf_ES_values)  # 更新单个 ETF 的 ES
        
        if len(valid_etfs) == 1:
            # 只有 1 个 ETF，该 ETF 的 ES 作为大类 ES
            asset_ES[asset_class] = etf_ES[stock_list[0]]
        else:
            # 多个 ETF 计算组合的周度 ES 
            weights = {etf: 1 / len(valid_etfs) for etf in valid_etfs}
            asset_ES[asset_class] = get_portfolio_ES(asset_class, valid_etfs, weights)

    return asset_ES, etf_ES, valid_etf_pools

def calculate_asset_allocations(asset_ES_results):

    inv_ES = {k: 1 / v if v > 0 else 0 for k, v in asset_ES_results.items()}
    total_inv_ES = float(sum(list(inv_ES.values())))
    asset_allocations = {k: round(v / total_inv_ES, 3) for k, v in inv_ES.items()} if total_inv_ES > 0 else inv_ES

    return asset_allocations

def calculate_etf_allocations(asset_allocations, etf_pool, etf_ES_results):
    etf_allocations = {}
    ema_signals = {etf: get_ma_signal(etf) for asset_class, etfs in etf_pool.items() for etf in etfs}
    
    # 记录看空类别的资金
    unused_funds = 0 
    active_asset_allocations = {}
    
    # 先遍历所有资产类别，计算有效 ETF 并标记看空类别
    for asset_class, etfs in etf_pool.items():
        total_asset_weight = asset_allocations.get(asset_class, 0)  # 该大类资产的仓位
        
        valid_etfs=[]
        for etf in etfs:
            if asset_class in ["equity", "foreign_equity"] and ema_signals.get(etf, 0) == 1:
                valid_etfs.append(etf)
            if asset_class in ["bonds", "commodities"]:
                valid_etfs.append(etf)
        
        if asset_class in ["equity", "foreign_equity"]:
            # 只对 equity 和 foreign_equity 进行均线择时筛选
            if not valid_etfs:
                log.info(f"{asset_class} 类别下无看多信号的 ETF，资金将重新分配")
                unused_funds += total_asset_weight  # 记录未分配的资金
            else:
                active_asset_allocations[asset_class] = total_asset_weight
        else:
            active_asset_allocations[asset_class] = total_asset_weight
            
    # 将未分配资金按比例重新分配给有效的资产类别
    total_active_weight = float(sum(list(active_asset_allocations.values())))
    if total_active_weight > 0:
        scale_factor = 1 + (unused_funds / total_active_weight)
        active_asset_allocations = {
            k: v * scale_factor for k, v in active_asset_allocations.items()
        }
        
    # 进行 ETF 分配
    for asset_class, etfs in etf_pool.items():
        if asset_class not in active_asset_allocations:
            continue  # 该资产类别已看空，跳过分配
        total_asset_weight = active_asset_allocations[asset_class]
        
        valid_etfs=[]
        for etf in etfs:
            if asset_class in ["equity", "foreign_equity"] and ema_signals.get(etf, 0) == 1:
                valid_etfs.append(etf)
            if asset_class in ["bonds", "commodities"]:
                valid_etfs.append(etf)
        
        if len(valid_etfs) == 1:
            # 只有一个 ETF，继承大类仓位
            etf_allocations[valid_etfs[0]] = round(total_asset_weight, 3)
        else:
            # 多个 ETF，使用 1 / ES 计算权重
            etf_inv_ES = {etf: 1 / etf_ES_results[etf] if etf_ES_results[etf] > 0 else 0 for etf in etfs}
            total_etf_inv_ES = float(sum(list(etf_inv_ES.values())))

            # 计算 ETF 内部的权重
            etf_weights = {etf: etf_inv_ES[etf] / total_etf_inv_ES for etf in etfs}

            # 计算最终 ETF 权重（大类权重 * ETF 内部权重）
            for etf in etfs:
                etf_allocations[etf] = round(etf_weights[etf] * total_asset_weight, 3)
        
    return etf_allocations

# ====== 择时 - 均线判断模块 ====== 

def get_ma_signal(stock):
    return 1
    '''
    # 获取最近 60 天的历史数据
    price_data = history(60, '1d', 'close', stock, df=True).dropna()
    
    if len(price_data) < 60:
        return 0  # 数据不足，保持原仓位
    
    # 计算均线
    ema12 = price_data.ewm(span=12, adjust=False).mean()
    ma50 = price_data.rolling(window=50).mean()
    latest_ema12 = float(ema12.iloc[-1])
    latest_ma50 = float(ma50.iloc[-1])
    
    # 计算MACD指标
    # ema12 = price_data.ewm(span=12, adjust=False).mean()
    # ema26 = price_data.ewm(span=26, adjust=False).mean()
    # macd_line = ema12 - ema26
    # signal_line = macd_line.ewm(span=9, adjust=False).mean()
    # latest_macd = float(macd_line.iloc[-1])
    # latest_signal = float(signal_line.iloc[-1])
    
    if latest_ema12 > latest_ma50: # and latest_macd > latest_signal:
        # log.info(f'{stock}符合择时信号')
        return 1  
    elif latest_ema12 < latest_ma50: # and latest_macd < latest_signal:
        return -1 
    else:
        return 0  # 无明显信号
    '''

# ====== 择时 - 单ETF动量得分计算 ======
def get_ETF_momentum(etf, momentum_day = 25):
    df = attribute_history(etf, momentum_day, '1d', ['close'])
    y = df['log'] = np.log(df.close)
    x = df['num'] = np.arange(df.log.size)
    slope, intercept = np.polyfit(x, y, 1)
    annualized_returns = math.pow(math.exp(slope), 250) - 1
    r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
    score = annualized_returns * r_squared
    return score

# ====== 择时 - ETF组合动量得分计算 ======
def get_portfolio_momentum(etf_list, weights=None, momentum_day=25):
    price_data = history(momentum_day, '1d', 'close', etf_list, df=True)
    if price_data.empty:
        return np.nan  # 数据缺失时返回 NaN
    
    if weights is None:
        weights = {etf: 1 / len(etf_list) for etf in etf_list}
    weight_sum = float(sum(list(weights.values())))
    weights = {etf: w / weight_sum for etf, w in weights.items()}
    
    portfolio_prices = sum(price_data[etf] * weights[etf] for etf in etf_list)
    y = np.log(portfolio_prices.dropna())
    x = np.arange(len(y))
    if len(y) < momentum_day:
        return np.nan
    
    slope, intercept = np.polyfit(x, y, 1)
    annualized_returns = math.pow(math.exp(slope), 250) - 1
    r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
    
    score = annualized_returns * r_squared
    return score

# ====== 择时 - 根据得分调整仓位-方法1-Sigmoid ======
def adjust_ES(ES, score, beta=5, min_ratio=0.75, max_ratio=1.25):
    adjustment_factor = max_ratio - (max_ratio - min_ratio) / (1 + np.exp(-beta * score))
    adjusted_ES = ES * adjustment_factor
    return adjusted_ES

# ====== 交易函数 ====== 

def trade(context, etf_allocations, valid_etf_pools):
    # 获取不同类别的 ETF 列表
    # equity_etfs = set(valid_etf_pools.get("equity", [])) | set(valid_etf_pools.get("foreign_equity", []))
    # commodities_etfs = set(valid_etf_pools.get("commodities", []))
    # bond_etfs = set(valid_etf_pools.get("bonds", []))
    
    # 计算卖出（需要减仓或清仓的 ETF）
    sell_orders = {}
    for position in context.portfolio.positions.values():
        etf = position.security
        current_value = position.value
        target_value = etf_allocations.get(etf, 0) * context.portfolio.total_value
        
        if target_value < current_value:  # 需要减少持仓
            sell_orders[etf] = target_value
    
    # 计算买入（需要加仓的 ETF）
    buy_orders = {}
    for etf, allocation in etf_allocations.items():
        target_value = allocation * context.portfolio.total_value
        if etf in list(context.portfolio.positions.keys()):
            current_value = context.portfolio.positions[etf].value
        else:
            current_value = 0
        
        if target_value > current_value:  # 需要增加持仓
            buy_orders[etf] = target_value
    
     # **第一步：先卖出 ETF，释放资金**
    for etf, target_value in sell_orders.items():
        current_value = context.portfolio.positions[etf].value
        if (current_value - target_value) / target_value > g.trade_threshold and (current_value - target_value) > 1000: 
            order_target_value(etf, target_value)
            log.info(f"减仓 {etf}")

    # **第二步：再买入 ETF，确保资金足够**
    for etf, target_value in buy_orders.items():
        if etf in list(context.portfolio.positions.keys()):
            current_value = context.portfolio.positions[etf].value
        else:
            current_value = 1 # 避免除0错误
        # if context.portfolio.positions[etf].price < context.portfolio.positions[etf].avg_cost: 
            # 如果最新行情价格 < 开仓均价，说明亏损，则不加仓
            # continue
        cash = context.portfolio.available_cash
        if (target_value - current_value) / target_value > g.trade_threshold and (target_value - current_value) > 1000:
            cash = context.portfolio.available_cash
            if cash >= target_value * g.trade_threshold:
                order_target_value(etf, target_value)
                log.info(f"加仓 {etf}")

# ====== 再平衡模块 ====== 
def need_rebalance(context):
    # 再平衡调整
    for etf in context.portfolio.positions:
        current_price = context.portfolio.positions[etf].price
        old_price = g.rebalance_price[etf]
        if old_price != 0:
            if (abs (current_price - old_price)) / old_price > g.rebalance_threshold:
                log.info('触发再平衡')
                return True
    
    # 均线策略判断
    '''
    for etf in context.portfolio.positions: 
        if etf in g.equity_etfs and get_ma_signal(etf) != 1:
            log.info(f'触发均线策略择时再平衡 {etf}不满足择时信号')
            return True
    '''


# ====== 封装计算仓位分配的所有函数 ====== 
def prepare_trade(context):

    asset_ES_results,etf_ES_results, valid_etf_pools = calculate_asset_class_ES(context, g.etf_pool)
    log.info("各大类资产的 ES:{}".format(asset_ES_results))
    
    asset_allocations = calculate_asset_allocations(asset_ES_results)
    log.info("各大类资产的仓位:{}".format(asset_allocations))
    
    etf_allocations = calculate_etf_allocations(asset_allocations, valid_etf_pools, etf_ES_results)
    log.info("具体 ETF 的仓位:{}".format(etf_allocations))

    record(
        Equity=asset_allocations['equity'], 
        Commodities=asset_allocations['commodities'],
        Bonds=asset_allocations['bonds'],
        US_Stock=asset_allocations['foreign_equity']
    )

    for etf in etf_allocations.keys():
        if etf in context.portfolio.positions:
            g.rebalance_price[etf] = context.portfolio.positions[etf].price
        else:
            g.rebalance_price[etf] = 0 

    return etf_allocations, valid_etf_pools

# ====== 调用 ======
def market_open(context):
    
    if g.period_count == g.cycle_period or need_rebalance(context):
        log.info('今日为交易日')
        g.period_count = 0
        g.etf_allocations, g.valid_etf_pools = prepare_trade(context)
        
    else: 
        g.period_count += 1 
    
    trade(context, g.etf_allocations, g.valid_etf_pools)

# ====== 盘后输出日志 ====== 
def after_market_close(context):
    current_holding = list(context.portfolio.positions.keys()) 
    for position in list(context.portfolio.positions.values()):
        securities=position.security
        name=get_security_info(securities).display_name
        cost=position.avg_cost
        price=position.price
        ret=100*(price/cost-1)
        value=position.value
        amount=position.total_amount
        ratio=position.value/context.portfolio.positions_value
        log.info("代码 {} 名称 {} 数量{} 成本价{} 现价 {} 收益率 {} 市值 {} 占比{}%".format(
            securities,
            name,
            amount,
            format(cost,'.2f'),
            price,
            format(ret,'.2f'),
            format(value,'.2f'),
            format(ratio*100,'.2f')
        ))
    log.info('今日账户总资产:{} 总持仓为:{}'.format(
        round(context.portfolio.total_value,2),
        round(context.portfolio.positions_value,2)
    ))
    log.info('=======================================')
