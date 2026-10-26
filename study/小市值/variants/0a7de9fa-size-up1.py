# Clone from JoinQuant
# postId: 0a7de9fad52e6c789cae6ef3b5032c61
# backtestId: 18cbe934dc6e4d24686343e5b69014dd
# title: 中小盘趋势策略（年化 85%）

# 克隆自聚宽文章：https://www.joinquant.com/post/59926
# 标题：中小盘趋势稳健策略【胜率84.2%，最大回测5.47%】
# 作者：流沙九月

# 克隆自聚宽文章：https://www.joinquant.com/post/59703
# 标题：中小盘策略BBI优化版
# 作者：股市的说法

# 克隆自聚宽文章：https://www.joinquant.com/post/59389
# 标题：﻿全市场小市值自带macd，10年年化76%回撤最大27%
# 作者：福娃她爹2



from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time, timedelta

# ======== 策略常量定义 ========
BENCHMARK = '000001.XSHG'  # 业绩基准指数（上证综指）
MARKET_INDEX = '399101.XSHE'  # 市场参考指数（中小板综指，用于趋势判断）
EMPTY_MONTHS = [1,4,]  # 空仓月份（1月、4月，基于历史数据统计的风险较高月份）
CASH_ETF = '511880.XSHG'  # 现金替代工具（华宝添益，低风险流动性工具）
STOPLOSS_SINGLE = 1       # 仅个股止损模式
STOPLOSS_MARKET = 2       # 仅市场整体止损模式
STOPLOSS_COMBINED = 3     # 个股+市场联合止损模式


# ======== 技术指标计算 ========
def EMA(series, N):
    """计算指数移动平均线（Exponential Moving Average）
    用于平滑价格波动，反映近期价格趋势，权重随时间递减
    
    参数:
        series: 价格序列（如收盘价）
        N: 计算周期
        
    返回:
        EMA序列
    """
    return pd.Series.ewm(series, span=N, min_periods=N-1, adjust=False).mean()

def MACD(close, SHORT=12, LONG=26, M=9):
    """计算MACD指标（Moving Average Convergence Divergence）
    用于判断趋势强度和潜在反转点，由DIF、DEA、MACD柱组成
    
    参数:
        close: 收盘价序列
        SHORT: 短期EMA周期（默认12）
        LONG: 长期EMA周期（默认26）
        M: 信号周期（默认9）
        
    返回:
        DIF: 短期EMA与长期EMA的差值
        DEA: DIF的M期EMA
        MACD: (DIF-DEA)*2（放大波动）
    """
    DIF = EMA(close, SHORT) - EMA(close, LONG)
    DEA = EMA(DIF, M)
    MACD = (DIF - DEA) * 2
    return DIF, DEA, MACD


# ======== 初始化函数 ========
def initialize(context):
    """策略初始化：设置核心参数、交易规则和运行时间"""
    # 防未来函数与价格设置（确保回测真实性）
    set_option('avoid_future_data', True)
    set_benchmark(BENCHMARK)
    set_option('use_real_price', True)
    
    # 交易成本设置（贴近实盘）
    set_slippage(FixedSlippage(3/1000))  # 滑点0.03%（保守估计，覆盖买卖价差）
    set_order_cost(
        OrderCost(
            open_tax=0,  # 买入无印花税
            close_tax=0.001,  # 卖出印花税0.1%
            open_commission=3/10000,  # 买入佣金0.03%
            close_commission=3/10000,  # 卖出佣金0.03%
            close_today_commission=0,  # 当日平仓无额外佣金
            min_commission=5  # 最低佣金5元
        ),
        type='stock'
    )
    
    # 日志级别设置（减少冗余，聚焦关键信息）
    log.set_level('order', 'error')  # 过滤订单错误日志
    log.set_level('system', 'error')  # 过滤系统错误日志
    log.set_level('strategy', 'debug')  # 保留策略调试日志
    
    # 全局变量（策略运行状态与中间结果）
    g.trading_signal = True  # 今日是否可交易（受空仓月份影响）
    g.run_stoploss = True    # 是否启用止损机制
    g.hold_list = []         # 当前持仓股票列表
    g.yesterday_HL_list = [] # 昨日涨停的持仓股票
    g.target_list = []       # 本周目标持仓股票列表
    g.limitup_stocks = []    # 因涨停打开卖出的股票
    g.not_buy_again = []     # 暂不重复买入的股票（避免短期重复交易）
    g.pass_months = EMPTY_MONTHS  # 空仓月份列表
    g.sell_reason = ''       # 最近一次卖出的原因
    g.dbl = []               # 大盘顶背离记录（用于风险控制）
    
    # 策略核心参数
    g.target_stock_count = 2  # 目标持仓数量
    g.up_price = 80            # 股价上限（避免高价股流动性风险）
    g.stoploss_strategy = STOPLOSS_COMBINED  # 采用联合止损模式
    g.stoploss_limit = 0.07   # 个股止损线（下跌7%强制止损）
    g.stoploss_market = 0.05   # 市场止损线（指数单日跌幅5%强制止损）
    g.etf = CASH_ETF           # 现金替代工具
    
    # 运行时间设置（关键节点触发）
    run_daily(prepare_stock_list, '9:05')       # 每日开盘前初始化
    run_daily(dapan, '9:00')                    # 每日开盘前检测大盘顶背离
    run_daily(sell_stocks, '10:30')             # 上午10:30检查止损
    run_daily(sell_stocks, '14:35')             # 下午14:00检查止损
    run_daily(trade_afternoon, '14:00')         # 下午14:30处理涨停与补仓
    run_daily(close_account, '14:50')           # 下午14:50空仓月份清仓
    run_weekly(weekly_adjustment, 2, '10:45')   # 每周二10:00调仓


# ======== 核心功能模块 ========
def prepare_stock_list(context):
    """每日初始化：更新持仓状态与昨日涨停信息
    确保策略运行时掌握最新的持仓结构和个股状态
    """
    # 更新当前持仓列表（从账户持仓中提取）
    g.hold_list = [pos.security for pos in context.portfolio.positions.values()]
    g.limitup_stocks = []  # 重置当日涨停打开卖出记录
    
    # 更新昨日涨停的持仓股票（用于次日涨停打开检测）
    if g.hold_list:
        # 获取持仓股昨日收盘价与涨停价
        price_df = get_price(
            g.hold_list,
            end_date=context.previous_date,  # 取昨日数据
            frequency='daily',
            fields=['close', 'high_limit'],  # 收盘价和涨停价
            count=1,
            panel=False,
            fill_paused=False
        )
        # 筛选收盘价等于涨停价的股票（即昨日涨停）
        g.yesterday_HL_list = price_df[price_df['close'] == price_df['high_limit']]['code'].tolist()
    else:
        g.yesterday_HL_list = []  # 无持仓时为空
    
    # 判断今日是否可交易（空仓月份不交易）
    g.trading_signal = today_is_tradable(context)
    log.info(f"今日交易状态: {'可交易' if g.trading_signal else '空仓月份，暂停交易'}")


def get_stock_list(context):
    """选股逻辑：从中小板综指中筛选优质中小市值股
    步骤：基础池筛选→多维度过滤→市值精选→趋势验证
    目的：选出流动性合理、风险可控、有上涨趋势的中小市值股
    """
    # 基础股票池：中小板综指成分股（聚焦中小市值企业）
    initial_list = get_index_stocks(MARKET_INDEX)
    log.info(f"初始股票池数量: {len(initial_list)}")
    
    # 初步过滤（排除高风险或不符合条件的股票）
    initial_list = filter_new_stock(context, initial_list)        # 排除次新股（上市不足1年）
    initial_list = filter_kcbj_stock(initial_list)                # 排除科创板、创业板、北交所（风险较高）
    initial_list = filter_st_stock(initial_list)                  # 排除ST、*ST及退市风险股
    initial_list = filter_paused_stock(initial_list)              # 排除停牌股（无法交易）
    log.info(f"初步过滤后数量: {len(initial_list)}")
    
    # 市值筛选：5-50亿中小市值（兼顾成长空间与流动性）
    # 按市值升序排序（优先更小市值，潜在弹性更高）
    q = query(
        valuation.code,
        valuation.market_cap  # 总市值
    ).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(10, 80)  # 市值范围：5亿-50亿
    ).order_by(valuation.market_cap.asc())  # 从小到大排序
    
    fund_df = get_fundamentals(q)  # 获取基本面数据
    if fund_df.empty:
        log.warning("市值筛选后无符合条件股票")
        return []
    # 取前100只最小市值股（缩小范围）
    initial_list = fund_df['code'].iloc[200:400].tolist()  # q-e9-champ-size: pool moved ONE cap notch up (ranks 201-400) — ONLY change vs the raw book
    log.error('POOLDEPTH date=%s n=%d' % (str(context.previous_date), len(fund_df)))  # q-e9-champ-size instrumentation: n < 400 at ANY rebalance => measurement INVALID
    log.info(f"市值筛选后数量: {len(initial_list)}")
    
    # 二次过滤（排除短期风险过高的股票）
    initial_list = filter_limitup_stock(context, initial_list)    # 排除非持仓的昨日涨停股（避免追高）
    initial_list = filter_limitdown_stock(context, initial_list)   # 排除非持仓的昨日跌停股（避免惯性下跌）
    initial_list = filter_highprice_stock(context, initial_list)   # 排除股价>80元的高价股（降低波动风险）
    log.info(f"二次过滤后数量: {len(initial_list)}")
    
    # 精选前50只最小市值股（进一步聚焦）
    q = query(valuation.code).filter(valuation.code.in_(initial_list)).order_by(valuation.market_cap.asc())
    fund_df = get_fundamentals(q)
    if fund_df.empty:
        log.warning("精选市值后无符合条件股票")
        return []
    candidate_list = fund_df['code'].head(80).tolist()
    log.info(f"精选市值后数量: {len(candidate_list)}")
    
    # BBI趋势过滤：收盘价在BBI线上方（确保中期趋势向上）
    # BBI（多空指标）=（3日+6日+12日+24日均价）/4，反映中期趋势
    if not candidate_list:
        return []
    
    # 获取计算BBI所需的价格数据（前60日至昨日）
    start_date = context.previous_date - timedelta(days=60)
    prices = get_price(
        candidate_list,
        start_date=start_date,
        end_date=context.previous_date,
        frequency='daily',
        fields='close',  # 收盘价
        panel=False
    )
    
    # 计算每只股票的BBI并过滤
    bbi_pass = []
    for stock in candidate_list:
        stock_data = prices[prices['code'] == stock]
        if len(stock_data) < 24:  # 确保有24天以上数据（满足最长周期计算）
            log.debug(f"{stock} 数据不足24天，排除")
            continue
        
        closes = stock_data['close'].values  # 提取收盘价序列
        prev_close = closes[-1]  # 前一日收盘价
        
        # 计算BBI各周期均值
        ma3 = np.mean(closes[-3:])    # 3日均价
        ma6 = np.mean(closes[-6:])    # 6日均价
        ma12 = np.mean(closes[-12:])  # 12日均价
        ma24 = np.mean(closes[-24:])  # 24日均价
        bbi = (ma3 + ma6 + ma12 + ma24) / 4  # 多空指标
        
        # 收盘价在BBI上方，说明中期趋势向上
        if bbi*0.9 < prev_close < bbi*1.3:
            bbi_pass.append(stock)
            log.debug(f"{stock} BBI验证通过（收盘价: {prev_close:.2f}, BBI: {bbi:.2f}）")
    
    log.info(f"BBI趋势过滤后最终选股数量: {len(bbi_pass)}")
    return bbi_pass


def weekly_adjustment(context):
    """每周调仓：根据目标列表调整持仓
    逻辑：卖出非目标股（保留涨停股）→买入目标股→平衡仓位
    目的：维持符合策略条件的持仓结构
    """
    # 空仓月份不调仓，持有现金ETF
    if not g.trading_signal:
        buy_security(context, [g.etf])
        log.info(f"空仓月份（{g.pass_months}），切换至持有现金ETF: {g.etf}")
        return
    
    # 近期有顶背离信号时暂停调仓（规避系统性风险）
    if True in g.dbl[-4:]:
        log.info("近5日检测到大盘顶背离，暂停调仓以控制风险")
        return
    
    # 获取本周目标持仓列表
    g.target_list = get_stock_list(context)
    g.not_buy_again = []  # 重置禁止重复买入列表
    log.info(f"本周目标持仓列表（前{min(g.target_stock_count, len(g.target_list))}只）: {g.target_list[:g.target_stock_count]}")
    
    # 卖出非目标持仓（保留当前涨停股，避免错失涨停收益）
    current_high_limit = now_high_limit(context)  # 当前涨停的持仓股
    sell_list = [
        stock for stock in g.hold_list
        if stock not in g.target_list[:g.target_stock_count]  # 不在目标列表前N只
        and stock not in current_high_limit  # 非当前涨停股
    ]
    for stock in sell_list:
        # 记录卖出原因：非目标持仓
        log.info(f"调仓卖出 {stock}（原因：不在本周目标持仓列表）")
        close_position(context.portfolio.positions[stock])
    log.info(f"调仓完成，共卖出 {len(sell_list)} 只股票")
    
    # 买入目标持仓（补足至目标数量）
    buy_security(context, g.target_list[:g.target_stock_count])


def sell_stocks(context):
    """止损止盈逻辑：结合个股与市场风险控制
    目的：通过止损限制亏损，通过止盈锁定收益，应对个股与系统性风险
    """
    if not g.run_stoploss or not g.hold_list:
        return  # 未启用止损或无持仓时不操作
    
    positions = context.portfolio.positions  # 当前持仓
    
    # 个股止损止盈（应对个股风险）
    if g.stoploss_strategy in (STOPLOSS_SINGLE, STOPLOSS_COMBINED):
        for stock, pos in positions.items():
            if stock == g.etf:  # 现金ETF不参与止损
                continue
                
            current_price = pos.price  # 当前价格
            avg_cost = pos.avg_cost   # 平均成本
            profit_ratio = (current_price / avg_cost) - 1  # 收益率
            
            # 止盈条件：收益达100%（锁定高额收益）
            if current_price >= avg_cost * 1.4:
                log.info(
                    f"{stock} 执行止盈（当前价: {current_price:.2f}, 成本: {avg_cost:.2f}, "
                    f"收益率: {profit_ratio:.2%}，达到100%止盈线）"
                )
                order_target_value(stock, 0)
                g.sell_reason = 'take_profit'  # 记录卖出原因
            
            # 止损条件：跌幅达7%（限制单笔亏损）
            elif current_price < avg_cost * (1 - g.stoploss_limit):
                log.info(
                    f"{stock} 执行止损（当前价: {current_price:.2f}, 成本: {avg_cost:.2f}, "
                    f"跌幅: {abs(profit_ratio):.2%}，达到7%止损线）"
                )
                order_target_value(stock, 0)
                g.sell_reason = 'stoploss'  # 记录卖出原因
    
    # 市场整体止损（应对系统性风险）
    if g.stoploss_strategy in (STOPLOSS_MARKET, STOPLOSS_COMBINED):
        # 获取市场指数昨日开盘价与收盘价
        index_data = get_price(
            MARKET_INDEX,
            end_date=context.previous_date,
            frequency='daily',
            fields=['open', 'close'],
            count=1
        )
        if not index_data.empty:
            # 计算市场指数单日跌幅
            market_down_ratio = (index_data['close'].iloc[0] / index_data['open'].iloc[0]) - 1
            # 跌幅达5%时触发整体止损
            if abs(market_down_ratio) >= g.stoploss_market:
                log.info(
                    f"市场指数单日跌幅达 {market_down_ratio:.2%}（超过3%止损线），执行整体止损"
                )
                for stock in positions.keys():
                    if stock == g.etf:
                        continue
                    order_target_value(stock, 0)
                g.sell_reason = 'market_stoploss'  # 记录卖出原因


def trade_afternoon(context):
    """下午交易处理：涨停打开检测与剩余资金补仓
    目的：及时处理涨停打开的个股（锁定收益），利用闲置资金提高仓位效率
    """
    if not g.trading_signal:
        return  # 空仓月份不操作
    
    check_limit_up(context)      # 检查昨日涨停股是否打开涨停
    check_remain_amount(context) # 利用卖出后的剩余资金补仓


def dapan(context):
    """大盘顶背离检测：通过MACD判断市场潜在反转风险
    目的：在大盘出现顶背离（上涨乏力）时提前减仓，规避系统性下跌
    """
    if detect_divergence(MARKET_INDEX, context):
        g.dbl.append(True)
        log.warning("⚠️ 检测到大盘顶背离信号（价格新高但MACD走弱），清仓非涨停股票")
        
        # 仅保留当前涨停股（可能延续强势），清仓其他股票
        current_data = get_current_data()
        for stock in list(g.hold_list):
            if stock == g.etf:
                continue
            # 当前未涨停的股票清仓
            if current_data[stock].last_price < current_data[stock].high_limit:
                log.info(f"{stock} 因大盘顶背离清仓（非涨停股）")
                close_position(context.portfolio.positions[stock])
    else:
        g.dbl.append(False)
        log.info("未检测到大盘顶背离，市场趋势正常")


# ======== 辅助功能模块 ========
def filter_new_stock(context, stock_list):
    """过滤次新股（上市不足1年）
    原因：次新股波动大、估值高、无历史数据参考，风险较高
    """
    if not stock_list:
        return []
    yesterday = context.previous_date  # 昨日日期
    filtered = []
    for stock in stock_list:
        listing_date = get_security_info(stock).start_date  # 上市日期
        if (yesterday - listing_date).days > 375:  # 上市超过1年（375天）
            filtered.append(stock)
        else:
            log.debug(f"{stock} 因上市不足1年（次新股）被过滤")
    return filtered

def filter_kcbj_stock(stock_list):
    """过滤科创板、创业板、北交所股票
    原因：这些板块涨跌幅限制较宽（20%），风险高于主板
    代码规则：68开头=科创板，30开头=创业板，4/8开头=北交所
    """
    filtered = []
    for stock in stock_list:
        if stock.startswith(('68', '30', '4', '8')):
            log.debug(f"{stock} 因属于科创板/创业板/北交所被过滤")
            continue
        filtered.append(stock)
    return filtered

def filter_st_stock(stock_list):
    """过滤ST、*ST及退市风险股
    原因：这些股票存在退市风险，且涨跌幅限制5%，流动性差
    """
    current_data = get_current_data()
    filtered = []
    for stock in stock_list:
        data = current_data[stock]
        if data.is_st or 'ST' in data.name or '*' in data.name or '退' in data.name:
            log.debug(f"{stock} 因ST/*ST/退市风险被过滤")
            continue
        filtered.append(stock)
    return filtered

def filter_paused_stock(stock_list):
    """过滤停牌股
    原因：停牌股无法交易，影响调仓执行
    """
    current_data = get_current_data()
    filtered = []
    for stock in stock_list:
        if current_data[stock].paused:
            log.debug(f"{stock} 因停牌被过滤")
            continue
        filtered.append(stock)
    return filtered

def filter_limitup_stock(context, stock_list):
    """过滤非持仓的昨日涨停股
    原因：昨日涨停股次日可能高开低走，追高风险高；持仓股则保留观察
    """
    if not stock_list:
        return []
    # 获取股票昨日收盘价与涨停价
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency='daily',
        fields=['close', 'high_limit'],
        count=1,
        panel=False
    )
    if df.empty:
        return stock_list
    # 筛选昨日涨停的股票
    limit_up = df[df['close'] == df['high_limit']]['code'].tolist()
    # 保留持仓股，过滤非持仓的涨停股
    filtered = []
    for stock in stock_list:
        if stock not in g.hold_list and stock in limit_up:
            log.debug(f"{stock} 因非持仓且昨日涨停被过滤")
            continue
        filtered.append(stock)
    return filtered

def filter_limitdown_stock(context, stock_list):
    """过滤非持仓的昨日跌停股
    原因：昨日跌停股次日可能惯性下跌，风险高；持仓股则保留观察
    """
    if not stock_list:
        return []
    # 获取股票昨日收盘价与跌停价
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency='daily',
        fields=['close', 'low_limit'],
        count=1,
        panel=False
    )
    if df.empty:
        return stock_list
    # 筛选昨日跌停的股票
    limit_down = df[df['close'] == df['low_limit']]['code'].tolist()
    # 保留持仓股，过滤非持仓的跌停股
    filtered = []
    for stock in stock_list:
        if stock not in g.hold_list and stock in limit_down:
            log.debug(f"{stock} 因非持仓且昨日跌停被过滤")
            continue
        filtered.append(stock)
    return filtered

def filter_highprice_stock(context, stock_list):
    """过滤股价过高的股票（>80元）
    原因：高价股绝对波动大（如80元跌5%=4元），风险高于低价股
    """
    if not stock_list:
        return []
    # 获取股票昨日收盘价
    prices = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency='daily',
        fields='close',
        count=1,
        panel=False
    )
    if prices.empty:
        return []
    # 按股票分组取最后收盘价
    last_prices = prices.groupby('code')['close'].last()
    # 过滤高价股
    filtered = []
    for stock in stock_list:
        price = last_prices.get(stock, 999)  # 默认999（超过上限）
        if stock not in g.hold_list and price > g.up_price:
            log.debug(f"{stock} 因股价过高（{price:.2f}元>80元）被过滤")
            continue
        filtered.append(stock)
    return filtered

def check_limit_up(context):
    """检查昨日涨停的持仓股是否打开涨停
    逻辑：若当前价格低于涨停价，说明涨停打开，可能回调，执行卖出
    """
    if not g.yesterday_HL_list:
        return  # 无昨日涨停股时不操作
    
    for stock in g.yesterday_HL_list:
        # 获取当前价格与涨停价（1分钟数据，实时性高）
        price_df = get_price(
            stock,
            end_date=context.current_dt,
            frequency='1m',
            fields=['close', 'high_limit'],
            count=1,
            panel=False
        )
        if price_df.empty:
            continue
        
        current_close = price_df['close'].iloc[0]  # 当前价格
        high_limit = price_df['high_limit'].iloc[0]  # 涨停价
        
        # 涨停打开（当前价<涨停价），执行卖出
        if current_close < high_limit:
            log.info(
                f"{stock} 涨停打开（当前价: {current_close:.2f} < 涨停价: {high_limit:.2f}），执行卖出"
            )
            close_position(context.portfolio.positions[stock])
            g.sell_reason = 'limitup'  # 记录卖出原因
            g.limitup_stocks.append(stock)  # 加入涨停打开列表
        else:
            log.debug(f"{stock} 维持涨停（当前价: {current_close:.2f} = 涨停价: {high_limit:.2f}），继续持有")

def check_remain_amount(context):
    """利用卖出后的剩余资金补仓
    目的：提高资金利用率，维持目标持仓数量
    """
    if not g.sell_reason:
        return  # 无卖出行为时不操作
    
    cash = context.portfolio.cash  # 可用资金
    g.hold_list = [pos.security for pos in context.portfolio.positions.values()]  # 更新持仓
    log.info(f"当前可用资金: {cash:.2f}元，当前持仓数量: {len(g.hold_list)}")
    
    # 涨停打开卖出后补仓（维持目标持仓数量）
    if g.sell_reason == 'limitup':
        need_buy = g.target_stock_count - len(g.hold_list)  # 需要补仓的数量
        if need_buy > 0:
            # 候选股：目标列表中未持仓、非涨停打开卖出、未被禁止买入的股票
            candidates = [
                s for s in g.target_list
                if s not in g.hold_list and s not in g.limitup_stocks and s not in g.not_buy_again
            ]
            buy_list = candidates[:need_buy]  # 取前N只补仓
            log.info(f"因涨停打开卖出，需补仓 {need_buy} 只，候选列表: {buy_list}")
            buy_security(context, buy_list)
    
    # 止损后转入现金ETF（规避风险）
    elif g.sell_reason in ('stoploss', 'market_stoploss'):
        log.info(f"因止损操作，剩余资金 {cash:.2f} 元转入现金ETF: {g.etf}")
        buy_security(context, [g.etf])
    
    # 重置卖出原因
    g.sell_reason = ''

def detect_divergence(stock, context):
    """检测顶背离（价格新高但MACD指标走弱，预示趋势反转）
    条件：
    1. 价格创新高（后高>前高）
    2. MACD指标未创新高（后低<前低）
    3. MACD由正转负（趋势转弱）
    4. DIF处于下降趋势（近期均值<前期均值）
    """
    fast, slow, sign = 12, 26, 9  # MACD参数
    rows = (fast + slow + sign) * 5  # 确保足够数据量（约1年）
    # 获取历史收盘价数据
    grid = attribute_history(stock, rows, fields=['close']).dropna()
    
    if len(grid) < rows:
        log.debug(f"{stock} 数据不足 {rows} 天，无法检测顶背离")
        return False
    
    try:
        # 计算MACD指标
        grid['dif'], grid['dea'], grid['macd'] = MACD(grid.close, fast, slow, sign)
        
        # 寻找死叉点（MACD由正转负的时刻）
        mask = (grid['macd'] < -0.03) & (grid['macd'].shift(1) >= 0)
        if mask.sum() < 2:  # 需要至少2个死叉点对比
            log.debug(f"{stock} 死叉点不足2个，无法检测顶背离")
            return False
        
        # 取最近两个死叉点（前一个与当前）
        key2, key1 = mask[mask].index[-2], mask[mask].index[-1]
        
        # 顶背离核心条件
        price_cond = grid.close[key2] < grid.close[key1]  # 价格创新高（后高>前高）
        dif_cond = grid.dif[key2] > grid.dif[key1] > 0    # DIF未创新高（后低<前高）且为正
        macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]  # MACD由正转负
        
        # 趋势验证：DIF近期处于下降趋势（近10日均值<前10日均值）
        if len(grid['dif']) > 20:
            recent_avg = grid['dif'].iloc[-10:].mean()  # 近10日DIF均值
            prev_avg = grid['dif'].iloc[-20:-10].mean()  # 前10日DIF均值
            trend_cond = recent_avg < prev_avg
        else:
            trend_cond = False
        
        log.debug(
            f"{stock} 顶背离检测: 价格创新高={price_cond}, DIF未新高={dif_cond}, "
            f"MACD转负={macd_cond}, DIF下降趋势={trend_cond}"
        )
        return price_cond and dif_cond and macd_cond and trend_cond
    
    except Exception as e:
        log.error(f"{stock} 顶背离检测错误: {e}")
        return False

def today_is_tradable(context):
    """判断今日是否为可交易月份（非空仓月份）"""
    return context.current_dt.month not in g.pass_months

def close_account(context):
    """空仓月份强制清仓（确保不在高风险月份持有股票）"""
    if not g.trading_signal:
        for stock in g.hold_list:
            if stock != g.etf:  # 保留现金ETF
                log.info(f"空仓月份清仓 {stock}（本月为风险控制月份）")
                close_position(context.portfolio.positions[stock])


# ======== 交易执行模块 ========
def order_target_value_(security, value):
    """增强型目标市值下单（记录详细日志）
    参数:
        security: 股票代码
        value: 目标市值（0表示清仓）
    返回:
        是否下单成功（True/False）
    """
    if value == 0:
        log.debug(f"执行清仓 {security}")
    else:
        log.debug(f"执行买入 {security}，目标金额 {value:.2f}元")
    
    # 下单操作
    order = order_target_value(security, value)
    # 判断是否成功（订单存在且状态为持有或部分成交）
    success = order is not None and (order.status == OrderStatus.held or order.filled > 0)
    if not success:
        log.warning(f"{security} 下单失败（目标金额: {value:.2f}元）")
    return success

def open_position(security, value):
    """开仓操作（买入指定金额的股票）
    参数:
        security: 股票代码
        value: 买入金额
    返回:
        是否开仓成功（True/False）
    """
    return order_target_value_(security, value)

def close_position(position):
    """平仓操作（清仓指定股票）
    参数:
        position: 持仓对象
    返回:
        是否平仓成功（True/False）
    """
    return order_target_value_(position.security, 0)

def buy_security(context, target_list):
    """批量买入目标股票（平均分配资金，补足至目标数量）
    参数:
        target_list: 目标股票列表
    """
    # 当前持仓股票
    current_hold = [pos.security for pos in context.portfolio.positions.values()]
    # 需要买入的股票（目标列表中未持仓的）
    need_buy = [stock for stock in target_list if stock not in current_hold]
    if not need_buy:
        log.info("无需要买入的股票（已全部持仓）")
        return
    
    cash = context.portfolio.cash  # 可用资金
    if cash <= 0:
        log.warning("可用资金为0，无法买入")
        return
    
    # 平均分配资金（每只股票分配等额资金）
    per_stock = cash / len(need_buy)
    log.info(f"共需买入 {len(need_buy)} 只股票，每只分配资金 {per_stock:.2f}元，总资金 {cash:.2f}元")
    
    for stock in need_buy:
        # 尝试买入
        if open_position(stock, per_stock):
            log.info(f"买入成功 {stock}，金额 {per_stock:.2f}元")
            g.not_buy_again.append(stock)  # 加入禁止重复买入列表
            # 达到目标持仓数量时停止
            if len(context.portfolio.positions) >= g.target_stock_count:
                log.info(f"已达到目标持仓数量 {g.target_stock_count}，停止买入")
                break
        else:
            log.warning(f"买入失败 {stock}，金额 {per_stock:.2f}元")

def now_high_limit(context):
    """获取当前处于涨停状态的持仓股
    返回:
        涨停股票列表
    """
    current_data = get_current_data()
    high_limit_list = []
    for stock in g.hold_list:
        # 当前价 >= 涨停价，视为涨停
        if current_data[stock].last_price >= current_data[stock].high_limit:
            high_limit_list.append(stock)
    log.debug(f"当前涨停的持仓股: {high_limit_list}")
    return high_limit_list
    
 

# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
