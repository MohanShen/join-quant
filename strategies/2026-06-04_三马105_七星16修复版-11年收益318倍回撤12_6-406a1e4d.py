# Clone from JoinQuant
# postId: 406a1e4dac6d86b7a07459894c2c127b
# backtestId: 78945bb4ee1457207ec34c41d2c81a99
# title: 三马105+七星16修复版-11年收益318倍回撤12.6

# 克隆自聚宽文章：https://www.joinquant.com/post/69017
# 标题：【策略升级】七星高照ETF轮动策略-V1.6
# 作者：晨曦量化

# 策略名称：七星高照ETF轮动策略-V1.6
# 策略作者：屌丝逆袭量化
# 优化时间：2026-3-26
# 优化内容：
# 1、增加溢价率过滤（可开关）：溢价率 = (场内价格 - 基金净值) / 基金净值，使用前一日净值计算
# 2、修复上篇文章中代码中卖出时未检查溢价率的问题
# 3、修复只有一个候选ETF的问题，该问题会导致如果候选的1只不满足要求，则直接进入防御模式
# 4、优化买卖逻辑，买入只检查是否涨停，卖出只检查是否跌停


# 克隆自聚宽文章：https://www.joinquant.com/post/68949
# 标题：溢价率是啥？在哪查？聚宽能获取吗？
# 作者：晨曦量化

# 策略名称：七星高照ETF轮动策略-V1.6-精简版（增加溢价率过滤）
# 策略作者：屌丝逆袭量化
# 优化时间：2026-3-25
# 优化内容：增加溢价率过滤（可开关）
# 说明：溢价率 = (场内价格 - 基金净值) / 基金净值，使用前一日净值计算

# 克隆自聚宽文章：https://www.joinquant.com/post/68577
# 标题：【策略微调】七星高照ETF轮动策略-V1.5
# 作者：屌丝逆袭量化

# 策略名称：七星高照ETF轮动策略-V1.5-20260319
# 策略作者：屌丝逆袭量化
# 优化时间：2026-3-19
# 优化内容：
# 1、 修复买卖计算结果相互矛盾的问题（引入当日排名缓存机制）
# 2、 关闭RSI过滤

# 克隆自聚宽文章：https://www.joinquant.com/post/66918
# 标题：【策略微调】七星高照ETF轮动策略-V1.3
# 作者：屌丝逆袭量化


# 克隆自聚宽文章：https://www.joinquant.com/post/67039
# 标题：三马持续优化版 - v10.5
# 作者：Charlessssss

# 克隆自聚宽文章：https://www.joinquant.com/post/63661
# 原作者：Cibo
# 当前作者：Charlessssss
#
# 集成一致性指标版本 - 基于v10.5 缓存加速版
# 新增功能：将微盘股一致性指标（蒋氏一致性）集成到小市值策略风控体系中
# 新增功能：ETF轮动策略缓存加速（减少重复数据获取和计算）
# 来源策略：
#   - https://www.joinquant.com/post/47349 - 韶华研究之十九，一致性用在微盘控制回撤
#   - https://www.joinquant.com/post/66998 - 三马优化版 v10.4缓存加速版

"""
三驾马车优化版 v10.5 + 一致性风控集成 + ETF缓存加速

策略组合：
- 策略1：小市值策略 + 一致性风控
- 策略2：ETF反弹策略 (仅适用于2023.9月后)
- 策略3：ETF轮动策略（缓存加速版）
- 策略4：白马攻防 v2.0

v10.5 更新：
- 新增：ETF轮动策略缓存加速
  - 批量预加载所有ETF历史数据（250天）
  - RSRS Beta值缓存机制（每日只需计算一次）
  - 五重过滤流程优化（按计算复杂度排序）
- 优化：ETF池保持原有配置
  - 多样性市场：上证180、德国DAX、纳指、日经225
  - 大宗商品：自然资源、黄金、原油LOF、豆粕期货、国债
  - 科技成长：创业板、科创100、半导体、金融科技、港股科技、新能源车
  - 蓝筹高股息：港股红利、上证180

v10.4 更新：成本保护止损
- 盈利>=15%：止损线上移到成本价(0%)，锁定本金
- 盈利>=30%：止损线上移至+10%，保护部分利润

一致性风控功能：
- 基于微盘股（最小5%市值）的市场一致性指标
- 使用120日布林带动态计算一致性阈值
- 牛熊市场自动切换：牛市关闭一致性检查，熊市开启
- 触发条件：大跌+高一致性 → 清仓；大涨+低一致性 → 满仓
"""
import datetime
import math
import prettytable
import numpy as np
import pandas as pd
from datetime import timedelta
from jqdata import *
from jqfactor import *
from prettytable import PrettyTable

""" ====================== 基础配置 ====================== """


def initialize(context):
    set_backtest()
    set_params(context)
    set_strategy_params(context)
    log.set_level("order", "error")


# 基础参数设置
def set_params(context):
    """
    资金分配比例：[小市值, ETF反弹, ETF轮动, 白马攻防]
    注意：ETF反弹策略仅适用于2023.9月后（中证2000ETF上市时间）
    """
    #g.portfolio_value_proportion = [0.35, 0.1, 0.35, 0.2]  # 小市值/ETF反弹/ETF轮动/白马攻防 (实盘)
    # g.portfolio_value_proportion = [0.4, 0.2, 0.4, 0]  # 小市值/ETF反弹/ETF轮动 (实盘/短回测)
    g.portfolio_value_proportion = [0.5, 0, 0.5, 0]  # 小市值/ETF轮动 (用于长回测)
    # g.portfolio_value_proportion = [0.35, 0, 0.35, 0.3]  # 小市值/ETF轮动/白马 (用于长回测)
    #g.portfolio_value_proportion = [0, 0, 1, 0]  # 小市值/ETF轮动 (用于长回测)

    g.starting_cash = context.portfolio.total_value
    g.stock_strategy = {}
    g.strategy_holdings = {1: [], 2: [], 3: [], 4: []}
    # 记录策略初始的金额, 用于计算各策略收益波动曲线
    g.strategy_starting_cash = {
        1: g.starting_cash * g.portfolio_value_proportion[0],  # 小市值 初始资金
        2: g.starting_cash * g.portfolio_value_proportion[1],  # ETF反弹 初始资金
        3: g.starting_cash * g.portfolio_value_proportion[2],  # ETF轮动 初始资金
        4: g.starting_cash * g.portfolio_value_proportion[3],  # 白马攻防 初始资金
    }
    # 记录每日策略收益
    g.strategy_value_data = {}
    g.strategy_value = {
        1: g.starting_cash * g.portfolio_value_proportion[0],  # 小市值 初始资金
        2: g.starting_cash * g.portfolio_value_proportion[1],  # ETF反弹 初始资金
        3: g.starting_cash * g.portfolio_value_proportion[2],  # ETF轮动 初始资金
        4: g.starting_cash * g.portfolio_value_proportion[3],  # 白马攻防 初始资金
    }
    # 暂存一个ETF反弹的初始比例
    g.strategy_ETF_2000_proportion = g.portfolio_value_proportion[1]
    g.strategy_ETF_2000_proportion_reset = None  # 用于检测拨正
    capital_balance_2(context)  # 首次就进行一次检测


# 策略参数设置
def set_strategy_params(context):
    """策略1 小市值 参数"""
    g.avoid_trade_april = True  # 是否在1、4月份避免交易小市值策略（避开高风险月份）
    # ======== 【修复代码】添加默认初始化，防止盘中启动报错 ========
    if g.avoid_trade_april and context.current_dt.month in [1, 4]:
        g.trading_signal = False
    else:
        g.trading_signal = True
    # ================================================================g.huanshou_check = False  # 放量换手检测，Ture是日频判断是否放量，False则不然
    g.huanshou_check = False  # 放量换手检测，Ture是日频判断是否放量，False则不然
    g.xsz_version = "v3"  # 市值选用版本 可选值: v1/v2/v3 具体逻辑自己看代码吧, 写不下
    g.enable_dynamic_stock_num = True  # 启用动态选股数量 3~6
    g.xsz_stock_num = 5  # 默认的持股数量, 启用动态后会被覆盖为 3~6
    g.yesterday_HL_list = []  # 昨日涨停股票
    g.target_list = []  # 目标持仓股票
    g.xsz_buy_etf = "511880.XSHG"  # 空仓时购买ETF

    # ========== 动态资金管理 ========== 打开以后，2年收益提升，回撤不变；10年收益降低，回撤降低
    # 根据市场波动率动态调整仓位，高波动时降低仓位，低波动时增加仓位
    g.enable_dynamic_position = True  # 是否启用基于波动率的动态仓位管理
    g.volatility_lookback = 20  # 波动率计算回溯期（交易日）
    g.base_position_ratio = 1.0  # 基准仓位比例（正常市场环境）
    g.volatility_threshold_low = 0.015  # 低波动率阈值（增加仓位）典型值: 0.01-0.02
    g.volatility_threshold_high = 0.035  # 高波动率阈值（降低仓位）典型值: 0.03-0.04
    g.position_ratio_min = 0.5  # 最小仓位比例（高波动时）
    g.position_ratio_max = 1.0  # 最大仓位比例（低波动时）

    # ========== 止损检查 ==========
    g.run_stoploss = True  # 是否进行止损
    g.stoploss_strategy = 3  # 1=固定止损，2=市场趋势止损，3=联合1+2策略
    g.stoploss_limit = 0.09  # 固定止损线（亏损9%止损）
    g.stoploss_market = 0.05  # 市场趋势止损参数（大盘跌5%清仓）

    # ========== ATR动态止损 ==========关闭ATR，2年收益提升，回撤不变；10年收益降低，回撤降低
    # ATR止损根据市场波动自动调整止损距离，比固定止损更灵活
    # 示例：成本价10元，ATR=0.5，倍数=2，则止损价=10-0.5*2=9元
    g.enable_atr_stop_loss = True  # 是否启用ATR动态止损（可与上述止损并用）
    g.atr_period = 14  # ATR计算周期（交易日）典型值: 10-20
    g.atr_multiplier = 2.0  # ATR止损倍数，值越大止损越宽松。典型值: 1.5-3.0
    g.atr_stop_prices = {}  # 存储每只股票的ATR止损价（自动维护，无需手动设置）

    # ========== 成本保护止损 ==========打开后，收益提升一点点，两年回撤不变
    # 盈利后动态上移止损线，保护已获利润
    # 示例：成本价10元，盈利15%（当前价11.5元）-> 止损线上移到10元（保护本金）
    #       成本价10元，盈利30%（当前价13元）-> 止损线上移到11元（保护10%利润）
    g.enable_cost_protection = True  # 是否启用成本保护止损
    g.cost_protection_profit_threshold_1 = 0.15  # 第一档盈利阈值（15%），触发后止损线上移到成本价
    g.cost_protection_profit_threshold_2 = 0.30  # 第二档盈利阈值（30%），触发后止损线上移到+10%
    g.cost_protection_stop_line_1 = 0.00  # 第一档止损线（成本价，0%）
    g.cost_protection_stop_line_2 = 0.10  # 第二档止损线（+10%利润）

    # ========== 一致性风控（新增）========== 不开收益更高，回撤更低
    # 基于微盘股（最小5%市值）的市场一致性指标，用于控制回撤
    g.enable_consistency_control = False  # 是否启用一致性风控
    g.consistency_signal = False  # False=满仓 True=清仓，初始满仓
    g.consistency_boll_period = 120  # 布林带计算周期（交易日）
    g.consistency_threshold_mean = 0.8  # 默认一致性均值（历史数据不足时使用）
    g.consistency_threshold_std = 0.05  # 默认一致性标准差（历史数据不足时使用）
    g.mini_cosi_list = []  # 存储微盘股一致性数据历史

    # 顶背离检查
    g.DBL_control = True  # 小市值大盘顶背离记录（用于风险控制）
    g.dbl = []
    g.check_macd_divergence_days = 10  # 顶背离检测窗口期长度, 窗口内不仅买入
    # 异常处理窗口期检查
    g.check_after_no_buy = False  # 检查后不再买入时间
    g.no_buy_stocks = {}  # 检查卖出的股票
    g.no_buy_after_day = 3  # 止损后不买入的时间窗口
    # 成交额宽度检查
    g.check_defense = False  # 成交额宽度检查
    g.industries = ["组20"]  # 高位防御板块
    g.defense_signal = None
    g.cnt_defense_signal = []  # 择时次数
    g.cnt_bank_signal = []  # 组20择时次数
    g.history_defense_date_list = []

    """ 策略2 ETF反弹 参数 """
    g.limit_days = 2  # 最少持仓周期
    g.n_days = 5  # 持仓周期
    g.holding_days = 0
    g.buy_list = []
    # etf池子，优先级从高到低
    g.etf_pool_2 = [
        "159536.XSHE",  # 中证2000
        "159629.XSHE",  # 中证1000
        "159922.XSHE",  # 中证500
        "159919.XSHE",  # 沪深300
        "159783.XSHE",  # 双创50
    ]

    """ 策略3 ETF轮动 参数 """
    g.etf_pool_3 = [
        "518880.XSHG",  # 黄金ETF
        "159985.XSHE",  # 豆粕ETF
        "501018.XSHG",  # 南方原油
        "161226.XSHE",  # 白银LOF
        "513100.XSHG",  # 纳指ETF
        "159915.XSHE",  # 创业板ETF
        #"159783.XSHE",  # 双创50
        #"512890.XSHG",  # 红利低波
        "511220.XSHG",  # 城投债ETF
    ]
    
    # 大ETF池（备用，本策略未使用）
    g.etf_pool_bak  = [
        # 大宗商品ETF
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF（跟踪有色金属板块）
        "159985.XSHE",  # 豆粕ETF（跟踪豆粕期货价格）
        "501018.XSHG",  # 南方原油（投资原油相关资产）
        "561360.XSHG",  # 石油ETF
        #'161226.XSHE',  # 白银LOF
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
    ]    
    
    
    g.lookback_days = 25  
    g.holdings_num = 1    
    g.defensive_etf = "511880.XSHG"
    g.min_money = 5000  
    
    # 风险控制
    g.stop_loss = 0.95    # 固定止损
    g.loss_limit = 0.97   # 3日跌幅止损线
    g.min_score_threshold = 0
    g.max_score_threshold = 100.0
    
    # 过滤参数
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0
    
    # ATR参数
    g.use_atr_stop_loss = False
    g.atr_period = 14
    g.atr_multiplier = 2
    g.atr_trailing_stop = False
    g.atr_exclude_defensive = True
    
    # RSI参数
    g.use_rsi_filter = False
    g.rsi_period = 6
    g.rsi_lookback_days = 1
    g.rsi_threshold = 98
    
    # --- 参数桥接：解决 San Ma 报表函数报错 ---
    g.m_days = g.lookback_days
    g.m_score = g.min_score_threshold
	
    # === 新增：溢价率过滤参数 ===
    g.enable_premium_filter = True      # 是否启用溢价率过滤
    g.premium_threshold = 0.20          # 溢价率阈值，例如0.02表示2%（注意：七星1.6源码写的是0.20/20%，通常建议设为0.02或0.03）	

    # 状态记录
    g.position_highs = {}
    g.rankings_cache = {'date': None, 'data': None}

    """ 策略4 白马攻防 参数 """
    g.check_out_lists = []
    g.market_temperature = "warm"
    g.stock_num_2 = 5  # 目标持股数量
    g.roe = 10  # ROE权重
    g.roa = 6  # ROA权重


# 回测设置
def set_backtest():
    set_option("avoid_future_data", True)
    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)

    set_slippage(FixedSlippage(0.002), type="stock")
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    cost_configs = [
        ("stock", 0.0005, 0.85 / 10000, 5),
        ("fund", 0, 0.5 / 10000, 5),
        ("mmf", 0, 0, 0),
    ]
    for asset_type, close_tax, commission, min_comm in cost_configs:
        set_order_cost(
            OrderCost(
                open_tax=0,
                close_tax=close_tax,
                open_commission=commission,
                close_commission=commission,
                close_today_commission=0,
                min_commission=min_comm,
            ),
            type=asset_type,
        )


""" ====================== 策略1: 小市值 ====================== """


# v1 选股模块 (双市值+行业分散)
def get_small_cap_stocks_v1(context):
    # 获取股票所属行业
    def filter_industry_stock(stock_list):
        result = get_industry(security=stock_list)
        selected_stocks = []
        industry_list = []
        for stock_code, info in result.items():
            industry_name = info["sw_l2"]["industry_name"]
            if industry_name not in industry_list:
                industry_list.append(industry_name)
                selected_stocks.append(stock_code)
                log.info(
                    f"[选股] 行业信息: {industry_name} (股票: {stock_code} {get_security_info(stock_code).display_name})"
                )
                if len(industry_list) == 10:
                    break
        return selected_stocks

    initial_list = filter_stocks(context, get_index_stocks("399101.XSHE"))

    q = (
        query(valuation.code)
        .filter(valuation.code.in_(initial_list))
        .order_by(valuation.circulating_market_cap.asc())
        .limit(50)
    )
    initial_list = list(get_fundamentals(q).code)

    q = (
        query(valuation.code)
        .filter(valuation.code.in_(initial_list))
        .order_by(valuation.market_cap.asc())
    )
    initial_list = list(get_fundamentals(q).code)
    initial_list = initial_list[:30]
    final_list = filter_industry_stock(initial_list)[: g.xsz_stock_num]
    log.info(
        f"[选股v1] 选出的股票: {[f'{i} {get_security_info(i).display_name}' for i in final_list]}"
    )
    return final_list


# v2 选股模块 (国九+roa+roe)
def get_small_cap_stocks_v2(context):
    initial_list = filter_stocks(context, get_index_stocks("399101.XSHE"))

    # 修复：正确使用聚宽基本面表查询方式
    q = (
        query(
            valuation.code,
            valuation.market_cap,
            income.np_parent_company_owners,
            income.net_profit,
            income.operating_revenue,
            valuation.turnover_ratio,
        )
        .filter(
            valuation.code.in_(initial_list),
            valuation.market_cap.between(5, 50),
            income.np_parent_company_owners > 0,
            income.net_profit > 0,
            income.operating_revenue > 1e8,
            fundamentals.indicator.roe > 0.15,
            fundamentals.indicator.roa > 0.10,
        )
        .order_by(valuation.market_cap.asc())
        .limit(50)
    )
    df = get_fundamentals(q)
    if df.empty:
        return []
    final_list = list(df.code)
    last_prices = history(1, "1d", "close", final_list, df=False)
    # 价格过滤
    return [
        stock
        for stock in final_list
        if stock in context.portfolio.positions or last_prices[stock] <= 20
    ][: g.xsz_stock_num]


# v3 选股模块 (国九+红利+审计)
def get_small_cap_stocks_v3(context):
    initial_list = filter_stocks(context, get_index_stocks("399101.XSHE"))

    q = (
        query(
            valuation.code,
            valuation.market_cap,
            income.net_profit,
            income.operating_revenue,
        )
        .filter(
            valuation.code.in_(initial_list),
            valuation.market_cap.between(10, 100),
            income.operating_revenue > 1e8,
            indicator.roe > 0,
            indicator.roa > 0,
            income.net_profit > 2000000,
        )
        .order_by(valuation.market_cap.asc())
        .limit(g.xsz_stock_num * 5)
    )
    final_list = list(get_fundamentals(q).code)
    final_list = filter_audit(context, final_list)
    final_list = bonus_filter(context, final_list)
    if not final_list:
        log.warn("[选股v3] 无适合股票，买入ETF")
        return [g.xsz_buy_etf]
    # 价格过滤
    last_prices = history(1, unit="1d", field="close", security_list=final_list)
    return [
        s for s in final_list if s in g.strategy_holdings[1] or last_prices[s][-1] <= 50
    ]


# 核心风控：微盘股10%指数一致性检查（蒋氏一致性）- 从xsz_yi_zhi_xing.py集成
def mini_consistency_check(context, signal):
    """
    一致性风控检查：基于微盘股（最小5%市值）的市场一致性指标

    核心逻辑：
    1. 筛选全市场有效标的（非停牌/非ST/非退市/非科创板/上市>20天）
    2. 选取市值最小的5%标的作为微盘股样本池
    3. 计算微盘股涨跌幅中位数和标准差
    4. 计算一致性比例：在[m-std, m+std]区间内的股票占比
    5. 使用120日布林带计算一致性动态阈值
    6. 牛熊判断：上证指数>240日均线=牛市关闭检查，否则开启

    风控规则：
    - 大跌（中位数<-2%）+ 高一致性（>=上轨） → 清仓（返回True）
    - 大涨（中位数>2%）+ 低一致性（>=均值） → 满仓（返回False）
    - 其他情况 → 保持原信号

    参数:
        context: 聚宽上下文
        signal: 当前一致性信号（False=满仓，True=清仓）

    返回:
        True: 触发清仓信号
        False: 不触发清仓信号（保持满仓）
    """
    today_date = context.current_dt.date()
    last_date = context.previous_date
    all_data = get_current_data()

    # 步骤1：筛选有效标的：全市场非停牌/非ST/非退市/非科创板/上市超20天
    stock_list = list(get_all_securities(["stock"]).index)
    total_stock_cnt = len(stock_list)
    stock_list = [code for code in stock_list if not all_data[code].paused]
    stock_list = [code for code in stock_list if not all_data[code].is_st]
    stock_list = [code for code in stock_list if "退" not in all_data[code].name]
    stock_list = [code for code in stock_list if code[0:3] != "688"]
    stock_list = [
        code
        for code in stock_list
        if (today_date - get_security_info(code).start_date).days > 20
    ]
    filter_stock_cnt = len(stock_list)

    # 步骤2：选取市值最小的5%标的作为微盘股样本池
    q = (
        query(valuation.code, valuation.market_cap)
        .filter(valuation.code.in_(stock_list))
        .order_by(valuation.market_cap.asc())
    )
    df_val = get_fundamentals(q)
    sample_stock_cnt = round(0.05 * total_stock_cnt)
    stock_list = list(df_val["code"])[:sample_stock_cnt]

    # 步骤3：计算微盘股样本池的涨跌幅中位数/标准差/一致性比例
    df_chg = get_money_flow(
        stock_list, end_date=last_date, fields="change_pct", count=1
    )
    chg_med = np.median(df_chg.change_pct)
    chg_std = np.std(df_chg.change_pct)
    df_temp = df_chg[
        (df_chg.change_pct < (chg_med + chg_std))
        & (df_chg.change_pct > (chg_med - chg_std))
    ]
    consistency_stock_cnt = len(df_temp)

    # 计算当日一致性比例并存储
    consistency_last = consistency_stock_cnt / sample_stock_cnt
    g.mini_cosi_list.append(consistency_last)

    # 牛熊判断：上证指数站上年线=牛市，关闭一致性检查；反之熊市开启
    df_index = get_price(
        "000001.XSHG",
        end_date=last_date,
        frequency="1d",
        fields="close",
        count=240,
        panel=False,
    )
    if df_index["close"].values[-1] > df_index["close"].values.mean():
        log.info("[一致性风控] 牛市判定，关闭一致性风控检查")
        return False
    else:
        log.info("[一致性风控] 熊市判定，打开一致性风控检查")

    # 计算一致性的120日布林带上下轨
    if len(g.mini_cosi_list) >= g.consistency_boll_period:
        cosistency_mean = np.mean(g.mini_cosi_list[-g.consistency_boll_period :])
        cosistency_std = np.std(g.mini_cosi_list[-g.consistency_boll_period :])
    else:
        cosistency_mean = g.consistency_threshold_mean
        cosistency_std = g.consistency_threshold_std
    cosistency_upper = cosistency_mean + cosistency_std

    # 打印一致性风控关键数据
    log.info(
        f"[一致性风控] {last_date} 微盘股-涨跌幅中位数:{chg_med:.4f},标准差:{chg_std:.4f},"
        f"当日一致性:{consistency_last:.4f},一致性均值:{cosistency_mean:.4f},一致性上轨:{cosistency_upper:.4f}"
    )

    # 布林带风控规则：大跌+高一致性=清仓，大涨+低一致性=满仓，其余保持原信号
    if chg_med < -2 and consistency_last >= cosistency_upper:
        log.warn("[一致性风控] 触发清仓信号：大跌+高一致性 → 清仓")
        return True
    elif chg_med > 2 and consistency_last >= cosistency_mean:
        log.info("[一致性风控] 触发满仓信号：大涨+低一致性 → 满仓")
        return False
    else:
        log.info("[一致性风控] 无信号，维持原持仓状态")
        return signal


# 小市值早盘变量预处理
def prepare_small_cap_strategy(context):
    # 根据配置决定是否在1、4月份避免交易
    if g.avoid_trade_april:
        g.trading_signal = False if context.current_dt.month in [1, 4] else True
    else:
        g.trading_signal = True

    # 更新一致性风控信号（新增）
    if g.enable_consistency_control:
        g.consistency_signal = mini_consistency_check(context, g.consistency_signal)

    g.yesterday_HL_list = []
    # 获取昨日涨停列表
    if g.strategy_holdings[1]:
        df = get_price(
            g.strategy_holdings[1],
            end_date=context.previous_date,
            fields=["close", "high_limit", "low_limit"],
            frequency="daily",
            count=1,
            panel=False,
            fill_paused=False,
        )
        g.yesterday_HL_list = list(df[df["close"] == df["high_limit"]].code)


# 计算市场波动率（基于大盘指数）
def calculate_market_volatility(context):
    """
    计算市场波动率，使用沪深300或其他大盘指数
    返回值：波动率（标准差）
    """
    index_code = "000300.XSHG"  # 沪深300指数
    df = get_price(
        index_code,
        end_date=context.previous_date,
        count=g.volatility_lookback + 1,
        frequency="daily",
        fields=["close"],
    )
    if len(df) < g.volatility_lookback:
        return None

    # 计算日收益率
    returns = df["close"].pct_change().dropna()
    # 计算波动率（标准差）
    volatility = returns.std()
    return volatility


# 根据波动率计算动态仓位比例
def calculate_dynamic_position_ratio(context):
    """
    根据市场波动率动态调整仓位比例
    低波动 -> 增加仓位（最高100%）
    正常波动 -> 基准仓位（100%）
    高波动 -> 降低仓位（最低50%）
    """
    if not g.enable_dynamic_position:
        return g.base_position_ratio

    volatility = calculate_market_volatility(context)
    if volatility is None:
        log.info("[动态仓位] 波动率数据不足，使用基准仓位")
        return g.base_position_ratio

    # 根据波动率区间调整仓位
    if volatility < g.volatility_threshold_low:
        # 低波动率，可以适当增加仓位
        position_ratio = g.position_ratio_max
        level = "低波动"
    elif volatility > g.volatility_threshold_high:
        # 高波动率，降低仓位控制风险
        position_ratio = g.position_ratio_min
        level = "高波动"
    else:
        # 正常波动率，线性插值
        # volatility 在 [low, high] 之间，position_ratio 在 [max, min] 之间
        ratio_range = g.position_ratio_max - g.position_ratio_min
        volatility_range = g.volatility_threshold_high - g.volatility_threshold_low
        position_ratio = g.position_ratio_max - (
            (volatility - g.volatility_threshold_low) / volatility_range * ratio_range
        )
        level = "正常波动"

    log.info(
        f"[动态仓位] 市场波动率: {volatility:.4f} ({level}) -> 仓位比例: {position_ratio:.2%}"
    )
    return position_ratio


# 计算ATR（平均真实波幅）
def calculate_atr(security, context, period=14):
    """
    计算ATR指标
    ATR = Average True Range，衡量价格波动幅度
    """
    df = get_price(
        security,
        end_date=context.previous_date,
        count=period + 1,
        frequency="daily",
        fields=["high", "low", "close"],
    )

    if len(df) < period + 1:
        return None

    # 计算真实波幅（True Range）
    # TR = max(high - low, abs(high - pre_close), abs(low - pre_close))
    df["pre_close"] = df["close"].shift(1)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["pre_close"])
    df["tr3"] = abs(df["low"] - df["pre_close"])
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

    # 计算ATR（使用简单移动平均）
    atr = df["tr"].iloc[-period:].mean()
    return atr


# 更新ATR止损价格
def update_atr_stop_prices(context):
    """
    为持仓股票更新ATR止损价格
    止损价 = 买入价 - (ATR × 倍数)
    """
    if not g.enable_atr_stop_loss:
        return

    current_positions = context.portfolio.positions
    for stock in current_positions.keys():
        if stock in g.strategy_holdings[1]:
            # 如果这只股票还没有止损价，计算并设置
            if stock not in g.atr_stop_prices:
                atr = calculate_atr(stock, context, g.atr_period)
                if atr:
                    avg_cost = current_positions[stock].avg_cost
                    # 止损价 = 成本价 - ATR倍数 * ATR
                    stop_price = avg_cost - (g.atr_multiplier * atr)
                    g.atr_stop_prices[stock] = stop_price
                    log.info(
                        f"[ATR止损] {format_stock_code(stock)} 成本: {avg_cost:.2f}, "
                        f"ATR: {atr:.2f}, 止损价: {stop_price:.2f}"
                    )
            else:
                # 已有止损价，可以选择使用跟踪止损（trailing stop）
                # 这里实现简单版本：如果价格上涨，止损价也向上调整
                current_price = current_positions[stock].price
                atr = calculate_atr(stock, context, g.atr_period)
                if atr:
                    trailing_stop = current_price - (g.atr_multiplier * atr)
                    # 止损价只能上移，不能下移（保护利润）
                    if trailing_stop > g.atr_stop_prices[stock]:
                        old_stop = g.atr_stop_prices[stock]
                        g.atr_stop_prices[stock] = trailing_stop
                        log.info(
                            f"[ATR止损] {format_stock_code(stock)} 跟踪止损价调整: "
                            f"{old_stop:.2f} -> {trailing_stop:.2f}"
                        )


# ATR动态止损检查
def check_atr_stop_loss(context):
    """
    检查是否触发ATR止损
    """
    if not g.enable_atr_stop_loss:
        return

    current_positions = context.portfolio.positions
    for stock in list(current_positions.keys()):
        if stock in g.strategy_holdings[1] and stock in g.atr_stop_prices:
            current_price = current_positions[stock].price
            stop_price = g.atr_stop_prices[stock]

            if current_price <= stop_price:
                avg_cost = current_positions[stock].avg_cost
                loss_pct = (current_price - avg_cost) / avg_cost * 100
                log.warn(
                    f"[ATR止损] {format_stock_code(stock)} 触发止损 "
                    f"当前价: {current_price:.2f}, 止损价: {stop_price:.2f}, "
                    f"亏损: {loss_pct:.2f}%"
                )
                close_position(stock)
                # 清除止损价记录
                del g.atr_stop_prices[stock]


# 小市值卖出
def strategy_1_sell(context):
    log.info("=" * 100)
    log.info(f"[策略1] 日期: {context.current_dt.date()}")
    g.target_list = []

    # 一致性风控检查（新增）：如果触发清仓信号，则不允许调仓
    if g.enable_consistency_control and g.consistency_signal:
        log.warn("[策略1] 一致性风控触发清仓信号，暂停调仓")
        return

    if g.DBL_control:
        # 首次运行检测最近10日顶背离
        if len(g.dbl) < 10:
            for i in range(9, -1, -1):
                check_macd_divergence(context, end_days=0 - i)
    if g.DBL_control and 1 in g.dbl[-g.check_macd_divergence_days :]:
        log.warn(f"[策略1] 近{g.check_macd_divergence_days}日检测到大盘顶背离，暂停调仓以控制风险")
        return

    # 检测空仓期（根据配置决定是否在1、4月份避免交易）
    if g.avoid_trade_april:
        month = context.current_dt.month
        if month in [1, 4]:
            g.trading_signal = False
    if not g.trading_signal:
        return

    if g.check_defense and g.defense_signal:
        log.warn("[策略1] 触发成交额宽度检查信号，暂停调仓以控制风险")
        return

    # 动态调整选股数量
    diff = None
    if g.enable_dynamic_stock_num:
        ma_para = 10  # 设置MA参数
        today = context.previous_date
        start_date = today - timedelta(days=ma_para * 2)
        index_df = get_price(
            "399101.XSHE", start_date=start_date, end_date=today, frequency="daily"
        )
        index_df["ma"] = index_df["close"].rolling(window=ma_para).mean()
        last_row = index_df.iloc[-1]
        diff = last_row["close"] - last_row["ma"]
        g.xsz_stock_num = (
            3
            if diff >= 500
            else 3
            if 200 <= diff < 500
            else 4
            if -200 <= diff < 200
            else 5
            if -500 <= diff < -200
            else 6
        )
    # 选择要启用的选股版本
    g.target_list = {
        "v1": get_small_cap_stocks_v1,
        "v2": get_small_cap_stocks_v2,
        "v3": get_small_cap_stocks_v3,
    }[g.xsz_version](context)[: g.xsz_stock_num]
    log.info(
        f"[策略1] 小市值{g.xsz_version} 目标持股数: {g.xsz_stock_num} [diff:{str(diff)[:6]}] 目标持仓: {g.target_list}"
    )

    # 卖出不在目标列表中的股票（除昨日涨停股）
    sell_list = [
        s
        for s in g.strategy_holdings[1]
        if s not in g.target_list and s not in g.yesterday_HL_list
    ]
    hold_list = [
        s
        for s in g.strategy_holdings[1]
        if s in g.target_list or s in g.yesterday_HL_list
    ]

    if sell_list:
        if hold_list:
            log.info(
                f"[策略1] 当前持有: {[format_stock_code(stock) for stock in hold_list]}"
            )
        log.info(
            f"[策略1] 计划卖出: {[format_stock_code(stock) for stock in sell_list]}"
        )
    for stock in sell_list:
        close_position(stock)


def strategy_1_buy(context):
    # 一致性风控检查（新增）：如果触发清仓信号，则不买入
    if g.enable_consistency_control and g.consistency_signal:
        log.warn("[策略1] 一致性风控触发清仓信号，暂停买入")
        return

    if not g.trading_signal:
        # 【修复/优化】：确保真实账户没有，且记录里没有，才去买，买完确保记录写入
        if g.xsz_buy_etf not in context.portfolio.positions:
            log.info("[策略1] 小市值清仓时期, 买入ETF")
            open_position(
                context,
                g.xsz_buy_etf,
                context.portfolio.total_value * g.portfolio_value_proportion[0],
                1,
            )
            # 防止 open_position 漏记
            if g.xsz_buy_etf not in g.strategy_holdings[1]:
                g.strategy_holdings[1].append(g.xsz_buy_etf)
                g.stock_strategy[g.xsz_buy_etf] = 1
        return

    # 计算动态仓位比例
    position_ratio = calculate_dynamic_position_ratio(context)

    # 计算可用资金（策略1专用部分，考虑动态仓位）
    strategy_value = (
        context.portfolio.total_value * g.portfolio_value_proportion[0] * position_ratio
    )
    current_value = sum(
        [
            pos.value
            for pos in context.portfolio.positions.values()
            if pos.security in g.strategy_holdings[1]
        ]
    )
    available_cash = max(0, strategy_value - current_value)  # 确保非负

    # 买入新标的
    buy_list = [s for s in g.target_list if s not in g.strategy_holdings[1][:]]
    if buy_list and available_cash > 0:
        cash_per_stock = available_cash / len(buy_list)
        for stock in buy_list:
            open_position(context, stock, cash_per_stock, 1)

    # 买入后更新ATR止损价
    if g.enable_atr_stop_loss:
        update_atr_stop_prices(context)


def close_account(context):
    if not g.trading_signal:
        if g.strategy_holdings[1] and g.xsz_buy_etf not in g.strategy_holdings[1]:
            for stock in g.strategy_holdings[1][:]:
                log.warn(f"[策略1] 进入清仓期间，卖出 {format_stock_code(stock)}")
                close_position(stock)


# 检查昨日涨停股今日表现
def check_small_cap_limit_up(context):
    # 获取当前持仓
    holdings = g.strategy_holdings[1][:]  # 只检查策略1
    if holdings:
        now_time = context.current_dt
        if g.yesterday_HL_list:
            # 对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
            for stock in g.yesterday_HL_list:
                current_data = get_price(
                    stock,
                    end_date=now_time,
                    frequency="1m",
                    fields=["close", "high_limit"],
                    skip_paused=False,
                    fq="pre",
                    count=1,
                    panel=False,
                    fill_paused=True,
                )
                if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                    log.info(f"[策略1] {format_stock_code(stock)} 涨停打开，卖出")
                    close_position(stock)
                else:
                    log.info(f"[策略1] {stock} 继续涨停，继续持有")


# 止盈止损
def sell_small_cap_stocks(context):
    if g.run_stoploss:
        current_positions = context.portfolio.positions

        # ATR动态止损（优先级最高）
        if g.enable_atr_stop_loss:
            check_atr_stop_loss(context)

        # 固定止损线 + 成本保护止损 (策略1或3)
        if g.stoploss_strategy in [1, 3]:
            for stock in list(current_positions.keys()):
                if stock in g.strategy_holdings[1]:
                    price = current_positions[stock].price
                    avg_cost = current_positions[stock].avg_cost
                    profit_ratio = (price - avg_cost) / avg_cost

                    # 100%翻倍止盈（保持不变）
                    if price >= avg_cost * 2:
                        log.info(f"[策略1] {format_stock_code(stock)} 收益100%止盈，卖出")
                        close_position(stock)
                        # 清除ATR止损价记录
                        if stock in g.atr_stop_prices:
                            del g.atr_stop_prices[stock]
                    # 成本保护止损逻辑
                    elif g.enable_cost_protection:
                        # 确定当前适用的止损线
                        if profit_ratio >= g.cost_protection_profit_threshold_2:
                            # 盈利 >= 30%，止损线上移到 +10%
                            stop_loss_line = g.cost_protection_stop_line_2
                            trigger_name = f"成本保护止损(盈利{profit_ratio:.1%}，止损线{stop_loss_line:.1%})"
                        elif profit_ratio >= g.cost_protection_profit_threshold_1:
                            # 盈利 >= 15%，止损线上移到成本价（0%）
                            stop_loss_line = g.cost_protection_stop_line_1
                            trigger_name = f"成本保护止损(盈利{profit_ratio:.1%}，止损线{stop_loss_line:.1%})"
                        else:
                            # 未达盈利阈值，使用原始固定止损线（-9%）
                            stop_loss_line = -g.stoploss_limit
                            trigger_name = "固定止损"

                        # 检查是否触发止损
                        if profit_ratio < stop_loss_line:
                            log.warn(
                                f"[策略1] {format_stock_code(stock)} 触发{trigger_name}，"
                                f"成本:{avg_cost:.2f} 现价:{price:.2f} 盈亏:{profit_ratio:.2%}，卖出"
                            )
                            close_position(stock)
                            # 清除ATR止损价记录
                            if stock in g.atr_stop_prices:
                                del g.atr_stop_prices[stock]
                    # 如果未启用成本保护，使用原始固定止损
                    elif price < avg_cost * (1 - g.stoploss_limit):
                        log.warn(f"[策略1] {format_stock_code(stock)} 触发固定止损，卖出")
                        close_position(stock)
                        # 清除ATR止损价记录
                        if stock in g.atr_stop_prices:
                            del g.atr_stop_prices[stock]

        # 市场趋势止损 (策略2或3)
        if g.stoploss_strategy in [2, 3]:
            stock_df = get_price(
                security=get_index_stocks("399101.XSHE"),
                end_date=context.previous_date,
                frequency="daily",
                fields=["close", "open"],
                count=1,
                panel=False,
            )
            down_ratio = (stock_df["close"] / stock_df["open"] - 1).mean()
            if down_ratio <= -g.stoploss_market:
                log.warn(f"[策略1] 大盘惨跌，平均降幅 {down_ratio:.2%}")
                for stock in g.strategy_holdings[1][:]:
                    close_position(stock)
                    # 清除ATR止损价记录
                    if stock in g.atr_stop_prices:
                        del g.atr_stop_prices[stock]


""" ====================== 策略2: ETF反弹 ====================== """


# 原始中证2000策略
def trade_zz2000_etf(context):
    to_buy = False
    etf_index = "159536.XSHE"
    # 获取近3日的历史数据
    df = get_price(
        etf_index,
        end_date=context.previous_date,
        count=3,
        frequency="daily",
        fields=["high"],
    )
    df = df.reset_index()
    if len(df) < 3:
        return

    pre3_high_max = df["high"].max()

    # 获取当前盘中实时数据
    current_data = get_current_data()
    today_open = current_data[etf_index].day_open
    today_close = current_data[etf_index].last_price

    # 策略条件判断，开盘相比最高价下跌2% & 最新价相比开盘价涨1%
    if today_open / pre3_high_max < 0.98 and today_close / today_open > 1.01:
        to_buy = True

    # 已经持仓, 检查是否继续持有
    if etf_index in context.portfolio.positions:
        position = context.portfolio.positions[etf_index]
        trade_date = position.init_time
        holding_days = (
            len(get_trade_days(start_date=trade_date, end_date=context.current_dt)) - 1
        )
        if not to_buy and holding_days >= 2:
            close_position(etf_index)
            log.info(f"[策略2] 卖出：{etf_index}, 持仓{holding_days}天")
    elif to_buy:
        strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[1]
        open_position(context, etf_index, strategy_value, 2)
        log.info(f"[策略2] 符合中证2000买入条件：{etf_index}")


def strategy_2_sell(context):
    cur_date = str(context.current_dt.date())
    if cur_date <= "2023-10-01":
        return

    g.buy_list = []
    sell_list = []
    sell_for_money_list = []
    # 获取近3日的历史数据
    for etf in g.etf_pool_2:
        df = get_price(
            etf,
            end_date=context.previous_date,
            count=4,
            frequency="daily",
            fields=["high", "close"],
        )
        df = df.reset_index()
        if len(df) < 4:
            return
        pre_high_max = df["high"].max()
        yestoday_close = df["close"].iloc[-1]
        # 获取当前盘中实时数据
        current_data = get_current_data()
        today_open = current_data[etf].day_open
        today_close = current_data[etf].last_price
        # 买入条件判断，开盘相比最高价下跌2% & 最新价相比开盘价涨1%
        if today_open / pre_high_max < 0.98 and today_close / today_open > 1.01:
            g.buy_list.append(etf)
        # 卖出条件判断，当前价格小于昨日收盘价
        if today_close < yestoday_close:
            sell_list.append(etf)

    # 保留最佳标的
    if g.buy_list:
        g.buy_list.sort(key=lambda x: g.etf_pool_2.index(x))
        selected_etf = g.buy_list[0]
        g.buy_list = [selected_etf]
        current_holdings = g.strategy_holdings[2]
        if current_holdings and g.etf_pool_2.index(
            current_holdings[0]
        ) < g.etf_pool_2.index(selected_etf):
            # 如果有持仓，且持有的ETF不是高优先级ETF，则清仓
            sell_for_money_list.append(current_holdings[0])

    for etf in g.strategy_holdings[2]:
        position = context.portfolio.positions[etf]
        security = position.security  # 股票代码
        trade_date = position.init_time
        holding_days = (
            len(get_trade_days(start_date=trade_date, end_date=context.current_dt)) - 1
        )
        if (
            (security in sell_list and holding_days >= g.limit_days)
            or (holding_days >= g.n_days)
            or (security in sell_for_money_list)
        ):
            close_position(security)
            log.info(f"[策略2] 卖出：{security}，持股 {holding_days}天")
    if not g.buy_list:
        log.info("[策略2] 今日无反弹可购买选项")


def strategy_2_buy(context):
    cur_date = str(context.current_dt.date())
    if cur_date <= "2023-10-01":
        return

    g.buy_list = list(set(g.buy_list) - set(g.strategy_holdings[2]))
    if len(g.buy_list) > 0:
        cash = context.portfolio.total_value * g.portfolio_value_proportion[1]
        if cash < 100:
            log.warn(f"cash不足:{context.portfolio.available_cash}")
        else:
            cash = context.portfolio.total_value * g.portfolio_value_proportion[1]
            for etf in g.buy_list:
                log.info(f"[策略2] 符合买入条件：{etf}")
                open_position(context, etf, cash, 2)


""" ====================== 策略3: ETF轮动 ====================== """


def get_cached_rankings(context):
    today = context.current_dt.date()
    if g.rankings_cache.get('date') != today:
        ranked = get_ranked_etfs_15(context)
        g.rankings_cache = {'date': today, 'data': ranked}
    return g.rankings_cache['data']

def get_ranked_etfs_15(context):
    etf_metrics = []
    current_data = get_current_data()
    for etf in g.etf_pool_3:
        if current_data[etf].paused: continue
        metrics = calculate_momentum_metrics_15(context, etf)
        if metrics and 0 < metrics['score'] < g.max_score_threshold:
            etf_metrics.append(metrics)
    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics

def calculate_momentum_metrics_15(context, etf):
    try:
        lookback = max(g.lookback_days, g.short_lookback_days, g.rsi_period + 5) + 20
        df = attribute_history(etf, lookback, '1d', ['close', 'volume'])
        curr_p = get_current_data()[etf].last_price
        price_series = np.append(df["close"].values, curr_p)
        
        # 1. 成交量过滤 (高位放量)
        if g.enable_volume_check:
            avg_vol = df['volume'].iloc[-g.volume_lookback:].mean()
            # 获取当日累计成交量
            today_vol = get_price(etf, start_date=context.current_dt.date(), end_date=context.current_dt, frequency='1m', fields=['volume'])['volume'].sum()
            ann_ret = get_annualized_returns_15(price_series, g.lookback_days)
            if (today_vol / avg_vol > g.volume_threshold) and (ann_ret > g.volume_return_limit):
                return None

        # 2. RSI过滤
        if g.use_rsi_filter:
            rsi_vals = calculate_rsi_15(price_series, g.rsi_period)
            if len(rsi_vals) > 0 and np.any(rsi_vals[-g.rsi_lookback_days:] > g.rsi_threshold):
                return None

        # 3. 短期动量过滤
        short_ret = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
        short_ann = (1 + short_ret) ** (250 / g.short_lookback_days) - 1
        if g.use_short_momentum_filter and short_ann < g.short_momentum_threshold:
            return None

        # 4. 核心：加权回归得分
        recent_y = np.log(price_series[-(g.lookback_days + 1):])
        x = np.arange(len(recent_y))
        weights = np.linspace(1, 2, len(recent_y))
        slope, intercept = np.polyfit(x, recent_y, 1, w=weights)
        ann_ret = math.exp(slope * 250) - 1
        
        ss_res = np.sum(weights * (recent_y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (recent_y - np.mean(recent_y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot else 0
        score = ann_ret * r2

        # 5. 风控：近3日单日跌幅限制
        if len(price_series) >= 4:
            if min(price_series[-1]/price_series[-2], price_series[-2]/price_series[-3], price_series[-3]/price_series[-4]) < g.loss_limit:
                score = 0
                
        return {'etf': etf, 'score': score, 'ann_ret': ann_ret}
    except:
        return None

# ==================== 交易模块 (策略3移植) ====================

def get_etf_premium_16(code, date):
    """移植自七星1.6：获取指定日期的溢价率"""
    # 获取场内价格
    price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
    if price_data.empty: return None
    price = price_data['close'].iloc[0]

    # 获取基金净值
    net_data = get_extras('unit_net_value', code, start_date=date, end_date=date, df=True)
    if net_data.empty or pd.isna(net_data[code].iloc[0]):
        try:
            q = query(finance.FUND_NET_VALUE).filter(finance.FUND_NET_VALUE.code == code, finance.FUND_NET_VALUE.day == date)
            net_df = finance.run_query(q)
            net_value = net_df['net_value'].iloc[0] if not net_df.empty else None
        except: net_value = None
    else:
        net_value = net_data[code].iloc[0]

    if net_value is None or net_value == 0: return None
    return (price - net_value) / net_value

def get_premium_rate_tool(code, date):
    """
    获取指定日期的溢价率（使用前一日净值对比当日价格）
    """
    # 1. 获取场内交易价格（当日收盘价或当前价）
    price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
    if price_data.empty:
        return None, None, None
    price = price_data['close'].iloc[0]

    # 2. 获取基金净值
    # 优先从 get_extras 获取单位净值
    net_data = get_extras('unit_net_value', code, start_date=date, end_date=date, df=True)
    
    if net_data.empty or pd.isna(net_data[code].iloc[0]):
        try:
            # 备用方案：查询数据库
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == date
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
            else:
                return None, None, None
        except:
            return None, None, None
    else:
        net_value = net_data[code].iloc[0]

    if net_value == 0: return None, None, None
    
    premium_rate = (price - net_value) / net_value
    return premium_rate, price, net_value

def calculate_momentum_metrics_16(context, etf):
    """完全复刻七星1.6的计算逻辑"""
    try:
        # 1. 基础数据获取
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        df = attribute_history(etf, lookback, '1d', ['close', 'volume'])
        curr_p = get_current_data()[etf].last_price
        price_series = np.append(df["close"].values, curr_p)

        # 2. 成交量过滤
        if g.enable_volume_check:
            avg_vol = df['volume'].iloc[-g.volume_lookback:].mean()
            # 获取当日累计成交量
            today_vol = get_price(etf, start_date=context.current_dt.date(), end_date=context.current_dt, frequency='1m', fields=['volume'])['volume'].sum()
            ann_ret = get_annualized_returns_16(price_series, g.lookback_days)
            if (today_vol / avg_vol > g.volume_threshold) and (ann_ret > g.volume_return_limit):
                return None

        # 3. 短期动量过滤
        short_ret = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
        short_ann = (1 + short_ret) ** (250 / g.short_lookback_days) - 1
        if g.use_short_momentum_filter and short_ann < g.short_momentum_threshold:
            return None

        # 4. 核心加权回归得分
        recent_y = np.log(price_series[-(g.lookback_days + 1):])
        x = np.arange(len(recent_y))
        weights = np.linspace(1, 2, len(recent_y))
        slope, intercept = np.polyfit(x, recent_y, 1, w=weights)
        ann_ret = math.exp(slope * 250) - 1
        
        ss_res = np.sum(weights * (recent_y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (recent_y - np.mean(recent_y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
        score = ann_ret * r2

        # 5. 近3日大跌风控 (七星1.6核心)
        if len(price_series) >= 4:
            day1, day2, day3 = price_series[-1]/price_series[-2], price_series[-2]/price_series[-3], price_series[-3]/price_series[-4]
            if min(day1, day2, day3) < g.loss_limit:
                score = 0
                
        return {'etf': etf, 'score': score}
    except:
        return None

def get_annualized_returns_16(price_series, days):
    y = np.log(price_series[-days-1:])
    slope, _ = np.polyfit(np.arange(len(y)), y, 1, w=np.linspace(1, 2, len(y)))
    return math.exp(slope * 250) - 1

def strategy_3_sell(context):
    target_etfs = get_target_etfs_16(context) 
    target_set = set(target_etfs)
    
    # 【修复】：只遍历属于策略3自己的持仓！避免误杀策略1的防守ETF
    for s in g.strategy_holdings[3][:]: 
        # 获取真实账户中的持仓对象，如果因为某种原因不存在则跳过
        if s not in context.portfolio.positions:
            continue
            
        pos = context.portfolio.positions[s]
        
        # A. 不在最终目标列表，卖出
        if s not in target_set:
            smart_order_target_value_16(s, 0, context)
            continue
            
        # B. 固定止损
        if pos.price <= pos.avg_cost * g.stop_loss:
            smart_order_target_value_16(s, 0, context)
            continue
            
        # C. 持仓溢价率过高过滤
        if g.enable_premium_filter:
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium = get_etf_premium_16(s, prev_date)
            if premium and premium > g.premium_threshold:
                smart_order_target_value_16(s, 0, context)

# 增加 smart 下单函数
def smart_order_target_value_16(security, target_value, context):
    data = get_current_data()
    if data[security].paused: return False
    price = data[security].last_price
    if price == 0: return False

    # 100股整数倍手动计算（关键！）
    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0: target_amount = 100

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount

    # 涨跌停拦截
    if diff > 0 and data[security].last_price >= data[security].high_limit: return False
    if diff < 0 and data[security].last_price <= data[security].low_limit: return False
    
    # 最小金额检查
    if 0 < abs(diff) * price < g.min_money: return False

    # T+1 保护
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0: return False
        diff = -min(abs(diff), closeable)

    if diff != 0:
        if order(security, diff):
            # 同步更新三马的持仓记录
            if target_value == 0:
                if security in g.strategy_holdings[3]: g.strategy_holdings[3].remove(security)
            else:
                if security not in g.strategy_holdings[3]: g.strategy_holdings[3].append(security)
                g.stock_strategy[security] = 3
            return True
    return False
	
	
	
def strategy_3_buy(context):
    # 调用统一函数获取目标
    target_etfs = get_target_etfs_16(context)

    if not target_etfs: return

    # 使用策略3的资金进行分配买入
    total_val = context.portfolio.total_value * g.portfolio_value_proportion[2]
    val_per = total_val / len(target_etfs)
    
    for etf in target_etfs:
        smart_order_target_value_16(etf, val_per, context)

def get_ranked_etfs_v16(context):
    # 缓存机制保持一致
    today = context.current_dt.date()
    if g.rankings_cache.get('date') != today:
        res = []
        for etf in g.etf_pool_3:
            if get_current_data()[etf].paused: continue
            m = calculate_momentum_metrics_16(context, etf)
            if m: res.append(m)
        res.sort(key=lambda x: x['score'], reverse=True)
        g.rankings_cache = {'date': today, 'data': res}
    return g.rankings_cache['data']


def get_target_etfs_16(context):
    """统一获取最终的目标持仓ETF名单（包含得分过滤和溢价率过滤）"""
    ranked = get_ranked_etfs_v16(context)
    target_etfs = []
    prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]

    for m in ranked:
        if len(target_etfs) >= g.holdings_num: break
        if m['score'] < g.min_score_threshold: continue
        etf = m['etf']
        
        # 溢价率过滤
        if g.enable_premium_filter:
            premium = get_etf_premium_16(etf, prev_date)
            if premium is None or premium > g.premium_threshold: 
                continue # 溢价太高跳过，顺延给下一个
                
        target_etfs.append(etf)

    # 防御模式后备逻辑
    if not target_etfs:
        d_data = get_current_data()[g.defensive_etf]
        if not (d_data.paused or d_data.last_price >= d_data.high_limit):
            target_etfs = [g.defensive_etf]

    return target_etfs


""" ====================== 策略4: 白马攻防 ====================== """


def adjust_blue_chip_position(context):
    if not g.check_out_lists:
        prepare_blue_chip_before_open(context)
    buy_stocks = g.check_out_lists
    log.info(
        f"[策略4] 白马目标调仓: {','.join([f'{format_stock_code(i)}' for i in buy_stocks])}"
    )
    # 卖出不在目标列表中的股票（只处理本策略持仓）
    for stock in g.strategy_holdings[4][:]:
        current_data = get_current_data()
        if stock not in buy_stocks:
            if current_data[stock].last_price >= current_data[stock].high_limit:
                continue
            close_position(stock)
            log.info(f"[策略4] 白马策略调出: {stock}")

    # 买入新标的
    position_count = len(
        [s for s in context.portfolio.positions.keys() if s in g.strategy_holdings[4]]
    )
    if len(buy_stocks) > position_count:
        # 使用策略4专用资金
        value = (
            context.portfolio.total_value
            * g.portfolio_value_proportion[3]
            / g.stock_num_2
        )
        
        current_data = get_current_data()
        valid_buy_stocks = [s for s in buy_stocks if not (current_data[s].last_price >= current_data[s].high_limit or current_data[s].last_price <= current_data[s].low_limit)]
        
        for stock in valid_buy_stocks:
            if stock not in g.strategy_holdings[4]:
                if open_position(context, stock, value, 4):
                    if len(g.strategy_holdings[4]) >= g.stock_num_2:
                        break


# 市场温度判断
def calculate_market_temperature(context):
    # 数据回滚两年判断市场温度
    if not hasattr(g, "market_temperature"):
        long_index300 = list(
            attribute_history("000300.XSHG", 220 * 3, "1d", ("close",), df=False)[
                "close"
            ]
        )
        g.market_temperature = "cold"
        for back_day in range(220, len(long_index300)):
            index300 = long_index300[back_day - 220 : back_day]
            market_height = (mean(index300[-5:]) - min(index300)) / (
                max(index300) - min(index300)
            )
            if market_height < 0.20:
                g.market_temperature = "cold"
            elif market_height > 0.80:
                g.market_temperature = "hot"
            elif max(index300[-60:]) / min(index300) > 1.20:
                g.market_temperature = "warm"
    # 当前一年的温度判断
    index300 = attribute_history("000300.XSHG", 220, "1d", ("close",), df=True).drop(
        pd.to_datetime("2024-10-08"), errors="ignore"
    )
    index300 = index300["close"].tolist()
    market_height = (mean(index300[-5:]) - min(index300)) / (
        max(index300) - min(index300)
    )
    if market_height < 0.20:
        g.market_temperature = "cold"
    elif index300[-1] == min(index300):
        g.market_temperature = "cold"
    elif market_height > 0.90:
        g.market_temperature = "hot"
    elif index300[-1] == max(index300):
        g.market_temperature = "hot"
    elif max(index300[-60:]) / min(index300) > 1.20:
        g.market_temperature = "warm"


# 开盘前运行函数
def prepare_blue_chip_before_open(context):
    calculate_market_temperature(context)
    g.check_out_lists = []
    current_data = get_current_data()
    all_stocks = get_index_stocks("000300.XSHG")
    all_stocks = [
        stock
        for stock in all_stocks
        if not (
            (
                current_data[stock].last_price
                > round(
                    context.portfolio.total_value
                    * g.portfolio_value_proportion[0]
                    * 0.95
                    / g.stock_num_2
                    / 100,
                    2,
                )
            )
            #or (current_data[stock].day_open == current_data[stock].high_limit)
            #or (current_data[stock].day_open == current_data[stock].low_limit)
            or current_data[stock].paused
            or current_data[stock].is_st
            or ("ST" in current_data[stock].name)
            or ("*" in current_data[stock].name)
            or ("退" in current_data[stock].name)
            or (stock.startswith("30"))
            or (stock.startswith("68"))
            or (stock.startswith("8"))
            or (stock.startswith("4"))
        )
    ]
    last_prices = history(1, unit="1d", field="close", security_list=all_stocks)
    all_stocks = [
        stock for stock in all_stocks if last_prices[stock][-1] <= 100
    ]  # 过滤高价股

    q = None
    if g.market_temperature == "cold":
        q = (
            query(valuation.code, indicator.roe, indicator.roa)
            .filter(
                valuation.pb_ratio > 0,
                valuation.pb_ratio < 1,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit
                > 2.0,
                indicator.inc_return > 1.5,
                indicator.inc_net_profit_year_on_year > -15,
                valuation.code.in_(all_stocks),
            )
            .order_by((indicator.roa / valuation.pb_ratio).desc())
            .limit(50)
        )
    elif g.market_temperature == "warm":
        q = (
            query(valuation.code, indicator.roe, indicator.roa)
            .filter(
                valuation.pb_ratio > 0,
                valuation.pb_ratio < 1,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit
                > 1.0,
                indicator.inc_return > 2.0,
                indicator.inc_net_profit_year_on_year > 0,
                valuation.code.in_(all_stocks),
            )
            .order_by((indicator.roa / valuation.pb_ratio).desc())
            .limit(50)
        )
    elif g.market_temperature == "hot":
        q = (
            query(valuation.code, indicator.roe, indicator.roa)
            .filter(
                valuation.pb_ratio > 3,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 0.5,
                indicator.inc_return > 3.0,
                indicator.inc_net_profit_year_on_year > 20,
                valuation.code.in_(all_stocks),
            )
            .order_by(indicator.roa.desc())
            .limit(50)  # *10
        )

    df = get_fundamentals(q)
    df.index = df["code"].values

    roe_inv_rank = df["roe"].rank(ascending=False)
    roa_inv_rank = df["roa"].rank(ascending=False)

    df["point"] = g.roe * roe_inv_rank + g.roa * roa_inv_rank

    df = df.sort_values(by="point")

    check_out_lists = list(df.code)
    # 动量趋势过滤，剔除太高和太低的
    check_out_lists2 = moment_rank(check_out_lists, 25, -1.0, 10.5)
    # 顺序还是按照动量趋滤前原来的顺序
    check_out_lists = [x for x in check_out_lists if x in check_out_lists2]
    g.check_out_lists = check_out_lists[: g.stock_num_2]
    log.info(f"[策略4] 今日市场温度：{g.market_temperature}")
    log.info(f"[策略4] 今日白马股票池：{g.check_out_lists}")


# 动量计算
def moment_rank(stock_pool, days, ll, hh):
    def mom(_stock):
        y = np.log(attribute_history(_stock, days, "1d", ["close"], df=False)["close"])
        n = len(y)
        x = np.arange(n)
        weights = np.linspace(1, 2, n)
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        residuals = y - (slope * x + intercept)
        weighted_residuals = weights * residuals**2
        r_squared = 1 - (
            np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y)) ** 2)
        )
        return annualized_returns * r_squared

    score_list = []
    for stock in stock_pool:
        score = mom(stock)
        score_list.append(score)
    df = pd.DataFrame(index=stock_pool, data={"score": score_list})
    df = df.sort_values(by="score", ascending=False)  # 降序
    df = df[(df["score"] > ll) & (df["score"] < hh)]
    rank_list = list(df.index)
    return rank_list


""" ====================== 辅助的定时执行函数 ====================== """

def smart_open_15(context, security, value):
    if value < g.min_money: return
    curr_data = get_current_data()[security]
    if curr_data.paused or curr_data.last_price >= curr_data.high_limit: return
    
    cur_val = context.portfolio.positions[security].value if security in context.portfolio.positions else 0
    if abs(cur_val - value) > value * 0.05 or cur_val == 0:
        if order_target_value(security, value):
            if security not in g.strategy_holdings[3]:
                g.strategy_holdings[3].append(security)
                g.stock_strategy[security] = 3
            g.position_highs[security] = curr_data.last_price

def smart_close_15(security):
    curr_data = get_current_data()[security]
    if curr_data.paused or curr_data.last_price <= curr_data.low_limit: return
    if order_target_value(security, 0):
        if security in g.strategy_holdings[3]:
            g.strategy_holdings[3].remove(security)
        if security in g.position_highs: del g.position_highs[security]

def check_atr_stop_loss_15(context):
    if not g.use_atr_stop_loss: return
    for s in g.strategy_holdings[3][:]:
        if g.atr_exclude_defensive and s == g.defensive_etf: continue
        h = attribute_history(s, g.atr_period + 5, '1d', ['high', 'low', 'close'])
        tr = np.maximum(h['high'].values[1:] - h['low'].values[1:], 
                        np.maximum(abs(h['high'].values[1:] - h['close'].values[:-1]), 
                                   abs(h['low'].values[1:] - h['close'].values[:-1])))
        atr = np.mean(tr[-g.atr_period:])
        curr_p = get_current_data()[s].last_price
        g.position_highs[s] = max(g.position_highs.get(s, 0), curr_p)
        base_p = g.position_highs[s] if g.atr_trailing_stop else context.portfolio.positions[s].avg_cost
        if curr_p <= (base_p - g.atr_multiplier * atr):
            log.info(f"🚨 ATR止损: {s}")
            smart_close_15(s)

def calculate_rsi_15(prices, period):
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period]); avg_loss = np.mean(losses[:period])
    rsi = [100 - (100 / (1 + avg_gain/avg_loss)) if avg_loss != 0 else 100]
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi.append(100 - (100 / (1 + avg_gain/avg_loss)) if avg_loss != 0 else 100)
    return np.array(rsi)

def get_annualized_returns_15(price_series, days):
    y = np.log(price_series[-days-1:])
    slope, _ = np.polyfit(np.arange(len(y)), y, 1, w=np.linspace(1, 2, len(y)))
    return math.exp(slope * 250) - 1

def get_best_defensive_asset(context):
    """比较防御池中的资产，选出过去20天涨幅最好的"""
    best_etf = g.etf3_defensive_pool[0]
    max_ret = -999.0
    
    for etf in g.etf3_defensive_pool:
        try:
            # 获取过去20天数据
            df = attribute_history(etf, 20, '1d', ['close'])
            if len(df) > 10:
                # 简单计算区间涨幅
                ret = (df['close'][-1] / df['close'][0]) - 1
                if ret > max_ret:
                    max_ret = ret
                    best_etf = etf
        except:
            continue
            
    return best_etf

# 大盘顶背离
def check_macd_divergence(context, market_index="399101.XSHE", end_days=0):
    """
    大盘顶背离检测：通过MACD判断市场潜在反转风险
    目的：在大盘出现顶背离（上涨乏力）时提前减仓，规避系统性下跌
    """
    # 把第一次9:31执行的给忽略掉, 第一次9:49会回溯过去10天, 避免第一次造成干扰(其实也不会, 但看日志会看的不会有困惑)
    if not g.dbl and "9:31" in str(context.current_dt.time()):
        return

    def detect_divergence():
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
        grid = attribute_history(market_index, rows + 10, fields=["close"]).dropna()
        if end_days < 0:
            grid = grid.iloc[:end_days]

        if len(grid) < rows:
            log.warn(f"[顶背离] {market_index} 数据不足 {rows} 天，无法检测顶背离")
            return False

        try:
            # 计算MACD指标
            grid["dif"], grid["dea"], grid["macd"] = mcad(grid.close, fast, slow, sign)

            # 寻找死叉点（MACD由正转负的时刻）
            mask = (grid["macd"] < 0) & (grid["macd"].shift(1) >= 0)
            if mask.sum() < 2:
                log.warn(f"[顶背离] {market_index} 死叉点不足2个，无法检测顶背离")
                return False

            # 取最近两个死叉点（前一个与当前）
            key2, key1 = mask[mask].index[-2], mask[mask].index[-1]

            # 顶背离核心条件
            price_cond = grid.close[key2] < grid.close[key1]  # 价格创新高（后高>前高）
            dif_cond = grid.dif[key2] > grid.dif[key1] > 0  # DIF未创新高（后低<前高）且为正
            macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]  # MACD由正转负

            # 趋势验证：DIF近期处于下降趋势（近10日均值<前10日均值）
            if len(grid["dif"]) > 20:
                recent_avg = grid["dif"].iloc[-10:].mean()  # 近10日DIF均值
                prev_avg = grid["dif"].iloc[-20:-10].mean()  # 前10日DIF均值
                trend_cond = recent_avg < prev_avg
            else:
                trend_cond = False

            return price_cond and dif_cond and macd_cond and trend_cond

        except Exception as e:
            log.error(f"[顶背离] {market_index} 顶背离检测错误: {e}")
            return False

    if market_index != "399101.XSHE":
        res = 1 if detect_divergence() else 0
        if res:
            log.warn(f"[顶背离] {market_index} 触发顶背离了!!!!! 快跑 !!!!!")
        return res

    if detect_divergence():
        g.dbl.append(1)
        log.warn(f"[顶背离] ⚠️ 检测到{market_index}顶背离信号（价格新高但MACD走弱），清仓非涨停股票")

        current_data = get_current_data()

        for stock in g.strategy_holdings[1][:]:
            if current_data[stock].last_price < current_data[stock].high_limit:
                log.warn(f"[顶背离] {stock} 因大盘顶背离清仓（非涨停股）")
                close_position(stock)
    else:
        g.dbl.append(0)


def preload_etf_data(etf_pool, days=250):
    """
    批量预加载所有ETF的历史数据（性能优化）

    参数:
        etf_pool: ETF列表
        days: 需要获取的历史天数

    返回:
        data_cache: 数据缓存字典 {stock: dict{'hist': DataFrame, 'current_price': float}}
    """
    log.info(f"[ETF轮动] 正在批量加载 {len(etf_pool)} 个ETF的历史数据（{days}天）...")
    data_cache = {}
    current_data = get_current_data()

    for etf in etf_pool:
        try:
            # 一次性获取所有需要的字段
            hist_data = attribute_history(etf, days, "1d", ["close", "high", "low", "volume"])
            if not hist_data.empty:
                # 添加当前价格到数据中
                current_price = current_data[etf].last_price
                data_cache[etf] = {
                    'hist': hist_data,
                    'current_price': current_price
                }
        except Exception as e:
            log.error(f"[ETF轮动] 加载{etf}数据失败: {e}")
            continue

    log.info(f"[ETF轮动] 数据加载完成，成功加载 {len(data_cache)} 个ETF的数据")
    return data_cache

# 动量计算（使用缓存数据）
def filter_moment_rank(stock_pool, days, ll, hh, data_cache, show_print=True):
    """
    动量得分计算（使用缓存数据）

    参数:
        stock_pool: 股票列表
        days: 参考天数
        ll: 得分下限
        hh: 得分上限
        data_cache: 预加载的数据缓存
        show_print: 是否打印结果
    """
    log.debug("[ETF轮动] 计算动量得分" + "*" * 60)

    scores_data = pd.DataFrame(
        index=stock_pool, columns=["annualized_returns", "r2", "score"]
    )
    print_info = {}

    for code in stock_pool:
        try:
            # 从缓存中获取数据
            if code not in data_cache:
                continue

            cached_data = data_cache[code]
            hist_data = cached_data['hist']
            current_price = cached_data['current_price']

            if hist_data.empty or len(hist_data) < days:
                continue

            # 使用最近days天的数据
            recent_data = hist_data.tail(days)
            prices = np.append(recent_data["close"].values, current_price)
            log_prices = np.log(prices)
            x_values = np.arange(len(log_prices))
            weights = np.linspace(1, 2, len(log_prices))

            slope, intercept = np.polyfit(x_values, log_prices, 1, w=weights)
            annualized_return = math.exp(slope * 250) - 1
            scores_data.loc[code, "annualized_returns"] = annualized_return

            ss_res = np.sum(
                weights * (log_prices - (slope * x_values + intercept)) ** 2
            )
            ss_tot = np.sum(weights * (log_prices - np.mean(log_prices)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            scores_data.loc[code, "r2"] = r2

            momentum_score = annualized_return * r2
            scores_data.loc[code, "score"] = momentum_score

            if (
                min(
                    prices[-1] / prices[-2],
                    prices[-2] / prices[-3],
                    prices[-3] / prices[-4],
                )
                < 0.97
            ):
                scores_data.loc[code, "score"] = 0
            print_info[code] = scores_data.loc[code, "score"]

        except Exception as e:
            log.error(f"[ETF轮动] 计算{code}动量得分失败: {e}")
            scores_data.loc[code, "score"] = 0

    valid_etfs = scores_data[
        (scores_data["score"] > ll) & (scores_data["score"] < hh)
    ].sort_values("score", ascending=False)
    rank_list = valid_etfs.index.tolist()
    if show_print and rank_list:
        for i in rank_list:
            log.debug(f"[ETF轮动] {format_stock_code(i)} ({print_info[i]:.4f})")
    return rank_list

# 尾盘记录各个策略的收益
def make_record(context):
    positions = context.portfolio.positions
    if not positions:
        return
    current_data = get_current_data()
    g.strategy_value_data = {1: 0, 2: 0, 3: 0, 4: 0}
    # 复制一个昨天的记录进行累计
    copy_strategy_value = {
        1: g.strategy_value[1],
        2: g.strategy_value[2],
        3: g.strategy_value[3],
        4: g.strategy_value[4],
    }
    for stock, pos in positions.items():
        strategy_id = g.stock_strategy[stock]
        current_value = pos.total_amount * current_data[stock].last_price  # 当前价值
        cost_value = pos.total_amount * pos.avg_cost  # 成本价值
        pnl_value = current_value - cost_value  # 当前盈亏金额
        copy_strategy_value[strategy_id] += pnl_value  # 计算浮盈浮亏
        g.strategy_value_data[strategy_id] += current_value
    if g.portfolio_value_proportion[0]:
        record(
            小市值=round(
                copy_strategy_value[1] / g.strategy_starting_cash[1] * 100 - 100, 2
            )
        )
    if g.strategy_ETF_2000_proportion:
        record(
            ETF反弹=round(
                copy_strategy_value[2] / g.strategy_starting_cash[2] * 100 - 100, 2
            )
        )
    if g.portfolio_value_proportion[2]:
        record(
            ETF轮动=round(
                copy_strategy_value[3] / g.strategy_starting_cash[3] * 100 - 100, 2
            )
        )
    if g.portfolio_value_proportion[3]:
        record(
            白马攻防=round(
                copy_strategy_value[4] / g.strategy_starting_cash[4] * 100 - 100, 2
            )
        )

    # 收盘后再把ETF轮动的明日选股提前透漏下
    # 修正预览逻辑缩进 (4个空格)
    if g.portfolio_value_proportion[2]:
        log.info("[收盘] 检测最新的ETF动量排名, 方便明天参考")
        ranked = get_ranked_etfs_15(context)
        for i, m in enumerate(ranked[:5]):
            log.info(f"排名{i+1}: {m['etf']} 得分: {m['score']:.4f}")


def print_summary(context):
    """打印当前投资组合的总资产和持仓详情"""
    total_value = round(context.portfolio.total_value, 2)

    current_stocks = context.portfolio.positions
    if not current_stocks:
        log.info(f"[持仓] 当前总资产: {total_value} 休息ing")
        return

    # 创建表格
    table = PrettyTable(
        [
            " 所属策略 ",
            " 股票代码 ",
            " 股票名称 ",
            " 持仓数量 ",
            " 持仓价格 ",
            " 当前价格 ",
            " 盈亏数额 ",
            " 盈亏比例 ",
            " 股票市值 ",
            " 仓位占比 ",
        ]
    )
    table.hrules = prettytable.ALL

    total_market_value = 0
    for stock in current_stocks:
        current_shares = current_stocks[stock].total_amount  # 持仓数量
        current_price = round(get_current_data()[stock].last_price, 3)  # 当前价格
        avg_cost = round(current_stocks[stock].avg_cost, 3)  # 持仓平均成本

        # 计算盈亏比例
        profit_ratio = (current_price - avg_cost) / avg_cost if avg_cost != 0 else 0
        profit_ratio_percent = f"{profit_ratio * 100:.2f}%"  # 转为百分比并保留两位小数
        profit_ratio_percent += f" {'↑' if profit_ratio > 0 else '↓'}"
        # 计算盈亏数额
        profit_amount = round((current_price - avg_cost) * current_shares, 2)

        # 计算市值
        market_value = round(current_shares * current_price, 2)
        total_market_value += market_value  # 累加总市值

        # 处理股票代码：移除后缀
        stock_code = stock.split(".")[0]  # 只保留股票代码部分

        # 添加到表格
        table.add_row(
            [
                g.stock_strategy[stock],
                stock_code,
                format_stock_code(stock),
                current_shares,
                avg_cost,
                current_price,
                profit_amount,
                profit_ratio_percent,
                market_value,
                f"{market_value / context.portfolio.total_value * 100:.2f}%",
            ]
        )

    # 账户总资产
    total_value = context.portfolio.total_value
    # 汇总
    if g.strategy_value_data[1]:
        table.add_row(
            [
                "小市值",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                f"{g.strategy_value_data[1]:.2f}",
                f"{g.strategy_value_data[1] / total_value * 100:.2f}%",
            ]
        )
    if g.strategy_value_data[2]:
        table.add_row(
            [
                "ETF反弹",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                f"{g.strategy_value_data[2]:.2f}",
                f"{g.strategy_value_data[2] / total_value * 100:.2f}%",
            ]
        )
    if g.strategy_value_data[3]:
        table.add_row(
            [
                "ETF轮动",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                f"{g.strategy_value_data[3]:.2f}",
                f"{g.strategy_value_data[3] / total_value * 100:.2f}%",
            ]
        )
    if g.strategy_value_data[4]:
        table.add_row(
            [
                "白马攻防",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                f"{g.strategy_value_data[4]:.2f}",
                f"{g.strategy_value_data[4] / total_value * 100:.2f}%",
            ]
        )
    table.add_row(["总市值", "", "", "", "", "", "", "", f"{total_market_value:.2f}", ""])
    table.add_row(["总资产", "", "", "", "", "", "", "", f"{total_value:.2f}", ""])

    log.info(f"[持仓] 当前总资产\n{table}")


# 小市值换手检测
def check_small_cap_turnover(context):
    huanshou(context, stock_list=g.strategy_holdings[1][:])


# ETF轮动日内止损检测
def etf_stop_loss_by_cur_day(context):
    holdings = set(g.strategy_holdings[3])
    # 检测日内亏损
    stop_loss_by_cur_day(holdings, ratio=g.stoploss_limit_by_cur_day)


""" ====================== 公共函数 ====================== """


def my_order_target_value(security, value):
    o = order_target_value(security, value)
    if o:
        if o.is_buy:
            if o.price * o.amount > 0:
                log.info(
                    f"[交易] 买入 {format_stock_code(security)}  "
                    f"买价{o.price:<7.2f}  "
                    f"买量{o.amount:<7}   "
                    f"价值{o.price * o.amount:.2f}"
                )
                return o
        else:
            if o.price * o.amount > 0:
                log.info(
                    f"[交易] 卖出 {format_stock_code(security)}  "
                    f"卖价{o.price:<7.2f}  "
                    f"成本{o.avg_cost:<7.2f}   "
                    f"卖量{o.amount:<7}   "
                    f"盈亏{(o.price - o.avg_cost) * o.amount:.2f}"
                    f"( {(o.price - o.avg_cost) / o.avg_cost * 100:.2f}% )"
                )
                return o


# 开仓买入并记录策略持仓
def open_position(context, security, value, strategy_id):
    if value <= 5000:
        return
    if security in context.portfolio.positions:
        security_value = context.portfolio.positions[security].value
        if abs(value - security_value) < 5000:
            return
    order = my_order_target_value(security, value)
    if order:
        security not in g.strategy_holdings[strategy_id] and g.strategy_holdings[
            strategy_id
        ].append(security)
        g.stock_strategy[security] = strategy_id
    return order


# 闭仓卖出并清空策略持仓
def close_position(security):
    order = my_order_target_value(security, 0)
    if order:
        strategy_id = g.stock_strategy[security]
        # 持仓列表移除
        security in g.strategy_holdings[strategy_id] and g.strategy_holdings[
            strategy_id
        ].remove(security)
        # 计算卖出的盈亏
        pnl_value = (order.price - order.avg_cost) * order.amount
        # 每日策略总价值更新盈亏
        g.strategy_value[strategy_id] += pnl_value
    return order


def stop_loss_by_cur_day(stock_list, ratio=-0.03):
    for stock in stock_list:
        cur_ratio = cal_cur_to_open_ratio(stock)
        if cur_ratio < ratio:
            log.warn(
                f"[日内止损] {format_stock_code(stock)} 距离开盘跌幅 {cur_ratio * 100:.2f}% 清仓处理"
            )
            close_position(stock)


""" ====================== 模块工具函数 ====================== """


# 展示优化
def format_stock_code(stock_code):
    try:
        stock_info = get_security_info(stock_code)
    except Exception:
        return f"{stock_code[:6]}"
    return f"{stock_code[:6]}({stock_info.display_name}) "


# 筛选审计意见
def filter_audit(context, code_list):
    # 获取审计意见，近三年内如果有不合格(report_type为3、4、5、7)的审计意见则返回False，否则返回True
    final_list = []
    """
    审计意见类型编码
        类型编码 审计意见类型
        1 	     无保留
        2 	     无保留带解释性说明
        3        保留意见
        4        拒绝/无法表示意见
        5        否定意见
        6 	     未经审计
        7 	     保留带解释性说明
        10 	     经审计（不确定具体意见类型）
        11       无保留带持续经营重大不确定性
    """
    for stock in code_list:
        previous_date = context.previous_date
        last_year = (
            previous_date.replace(year=previous_date.year - 3, month=1, day=1)
        ).strftime("%Y-%m-%d")
        q = query(
            finance.STK_AUDIT_OPINION.code,
            finance.STK_AUDIT_OPINION.pub_date,
            finance.STK_AUDIT_OPINION,
        ).filter(
			finance.STK_AUDIT_OPINION.code == stock,
			finance.STK_AUDIT_OPINION.pub_date >= last_year,
			finance.STK_AUDIT_OPINION.pub_date <= context.previous_date  # 增加上限，阻断未来函数
        )
        df = finance.run_query(q)
        values_to_check = [3, 4, 5, 7]
        if not df["opinion_type_id"].isin(values_to_check).any():
            final_list.append(stock)
    return final_list


# 获取红利列表
def bonus_filter(context, stock_list):
    year = context.previous_date.year
    start_date = datetime.datetime(year=year, month=1, day=1)
    end_date = context.previous_date
    if end_date.month in [5]:
        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.company_name,
            finance.STK_XR_XD.board_plan_pub_date,
            finance.STK_XR_XD.bonus_amount_rmb,
            finance.STK_XR_XD.bonus_ratio_rmb,
        ).filter(
            finance.STK_XR_XD.board_plan_pub_date > start_date,
            finance.STK_XR_XD.implementation_pub_date <= end_date,
            finance.STK_XR_XD.bonus_ratio_rmb > 0,
            finance.STK_XR_XD.code.in_(stock_list),
        )
        expected_bonus_df = finance.run_query(q)

        if len(expected_bonus_df) > 0:
            bonus_list = expected_bonus_df["code"].unique().tolist()
            price_df = history(
                1,
                unit="1d",
                field="close",
                security_list=bonus_list,
                df=True,
                skip_paused=False,
                fq="pre",
            )
            price_df = price_df.T
            price_df.rename(columns={price_df.columns[0]: "Close_now"}, inplace=True)
            price_df["code"] = price_df.index
            expected_bonus_df = pd.merge(
                expected_bonus_df, price_df, on=("code",), how="left"
            )
            expected_bonus_df["bonus_ratio"] = (
                expected_bonus_df["bonus_ratio_rmb"]
            ) / expected_bonus_df["Close_now"]
            expected_bonus_df = expected_bonus_df.sort_values(
                by="bonus_ratio", ascending=True
            )
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
        # 排除今年不分红的股票
        bonus_list = [code for code in stock_list if code not in no_year_bonus_list]
        bonus_list = short_by_market_cap(context, bonus_list)

    if len(bonus_list) < g.xsz_stock_num:
        bonus_list.extend(
            [
                x
                for x in short_by_market_cap(context, stock_list)
                if x not in bonus_list
            ][: g.xsz_stock_num - len(bonus_list)]
        )
    return bonus_list


# 计算RSI指标
def calculate_rsi(code, period=14):
    """计算RSI指标"""
    df = attribute_history(
        code,
        125,
        "1d",
        [
            "close",
        ],
        skip_paused=True,
        df=True,
        fq="pre",
    )
    prices = df["close"].values
    deltas = np.diff(prices)
    seed = deltas[: period + 1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    if down == 0:
        return 100
    rs = up / down
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi


#  基础过滤各种股票
def filter_stocks(context, stock_list):
    current_data = get_current_data()
    # 涨跌停和最近价格的判断
    last_prices = history(1, unit="1m", field="close", security_list=stock_list)
    # 过滤标准
    filtered_stocks = []
    for stock in stock_list:
        if current_data[stock].paused:  # 停牌
            continue
        if current_data[stock].is_st:  # ST
            continue
        if "退" in current_data[stock].name:  # 退市
            continue
        if (
            stock.startswith("30")
            or stock.startswith("68")
            or stock.startswith("8")
            or stock.startswith("4")
        ):  # 市场类型
            continue
        if not (
            stock in context.portfolio.positions
            or last_prices[stock][-1] < current_data[stock].high_limit
        ):  # 涨停
            continue
        if not (
            stock in context.portfolio.positions
            or last_prices[stock][-1] > current_data[stock].low_limit
        ):  # 跌停
            continue
        # 次新股过滤
        start_date = get_security_info(stock).start_date
        if context.previous_date - start_date < timedelta(days=375):
            continue
        filtered_stocks.append(stock)
    return filtered_stocks


# 计算最新价格对比开盘价格的比值
def cal_cur_to_open_ratio(security):
    current_data = get_current_data()
    last_price = current_data[security].last_price
    day_open = current_data[security].day_open
    return (last_price - day_open) / day_open


# 计算MACD指标
def mcad(close, short=12, long=26, m=9):
    """计算 MACD 指标
    用于判断趋势强度和潜在反转点，由 DIF、DEA、MACD 柱组成

    参数:
        close: 收盘价序列
        short: 短期EMA周期（默认12）
        long: 长期EMA周期（默认26）
        m: 信号周期（默认9）

    返回:
        DIF: 短期EMA与长期EMA的差值
        DEA: DIF的M期EMA
        MACD: (DIF-DEA)*2（放大波动）
    """

    # 计算指数移动平均线
    def ema(series, n):
        """计算指数移动平均线（Exponential Moving Average）
        用于平滑价格波动，反映近期价格趋势，权重随时间递减

        参数:
            series: 价格序列（如收盘价）
            N: 计算周期

        返回:
            EMA序列
        """
        return pd.Series.ewm(series, span=n, min_periods=n - 1, adjust=False).mean()

    dif = ema(close, short) - ema(close, long)
    dea = ema(dif, m)
    return dif, dea, (dif - dea) * 2


# 换手检测
def huanshou(context, stock_list):
    # 换手率计算
    def huanshoulv(_stock, is_avg=False):
        if is_avg:
            # 计算平均换手率
            end_date = context.previous_date
            df_volume = get_price(
                _stock,
                end_date=end_date,
                frequency="daily",
                fields=["volume"],
                count=20,
            )
            df_cap = get_valuation(
                _stock, end_date=end_date, fields=["circulating_cap"], count=1
            )
            circulating_cap = (
                df_cap["circulating_cap"].iloc[0] if not df_cap.empty else 0
            )
            if circulating_cap == 0:
                return 0.0
            df_volume["turnover_ratio"] = df_volume["volume"] / (
                circulating_cap * 10000
            )
            return df_volume["turnover_ratio"].mean()
        else:
            # 计算实时换手率
            date_now = context.current_dt
            df_vol = get_price(
                _stock,
                start_date=date_now.date(),
                end_date=date_now,
                frequency="1m",
                fields=["volume"],
                skip_paused=False,
                fq="pre",
                panel=True,
                fill_paused=False,
            )
            volume = df_vol["volume"].sum()
            date_pre = context.previous_date
            df_circulating_cap = get_valuation(
                _stock, end_date=date_pre, fields=["circulating_cap"], count=1
            )
            circulating_cap = (
                df_circulating_cap["circulating_cap"].iloc[0]
                if not df_circulating_cap.empty
                else 0
            )
            if circulating_cap == 0:
                return 0.0
            turnover_ratio = volume / (circulating_cap * 10000)
            return turnover_ratio

    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in stock_list:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        rt = huanshoulv(stock, False)
        avg = huanshoulv(stock, True)
        if avg == 0:
            continue
        r = rt / avg
        action, icon = "", ""
        if avg < 0.003:
            action, icon = "缩量", "❄️"
        elif rt > expand and r > 2:
            action, icon = "放量", "🔥"
        if action:
            log.warn(
                f"[换手] {action} {format_stock_code(stock)}  换手率:{rt:.2%}  均:{avg:.2%} 倍率:x{r:.1f} {icon}"
            )
            close_position(stock)


# 成交量宽度防御检测
def check_defense_trigger(context):
    """改进后的防御条件检查"""

    # 计算宽度
    def get_market_breadth(ma_days):
        required_days = ma_days + 10
        end_date = context.current_dt.replace(hour=14, minute=49)

        # 获取行业分类数据
        sw_l1 = get_industries("sw_l1", date=context.current_dt.date())
        industry_stocks = {}
        for idx, row in sw_l1.iterrows():
            ind_stocks = get_industry_stocks(idx, date=end_date)
            industry_stocks[row["name"]] = ind_stocks  # 存储行业对应的股票列表

        # 获取所有股票
        all_stocks = []
        for stocks in industry_stocks.values():
            all_stocks.extend(stocks)
        all_stocks = list(set(all_stocks))  # 去重

        # 获取价格和成交额数据
        data = get_bars(
            all_stocks,
            end_dt=end_date,
            count=required_days,
            unit="1d",
            fields=["date", "close", "volume", "money"],
            include_now=True,
            df=True,
        )

        # 处理价格数据：用level_1作为索引（行号），level_0作为股票代码列
        price_reset = data.reset_index()
        price_data = price_reset.pivot(
            index="level_1", columns="level_0", values="close"
        )  # 按要求的透视表写法

        # 计算移动平均和站上均线的股票占比
        ma = price_data.rolling(window=ma_days).mean()
        above_ma = price_data > ma

        # 核心逻辑：按透视表处理20日成交金额，计算平均值后再分组
        # 1. 重置索引并创建成交额透视表（行=行号，列=股票代码，值=成交额）
        money_reset = data.reset_index()
        money_pivot = money_reset.pivot(
            index="level_1", columns="level_0", values="money"
        )  # 成交额透视表

        recent_20d_money_pivot = money_pivot.tail(20)  # 关键：直接从透视表取最近20天

        avg_money = recent_20d_money_pivot.mean().reset_index()  # 按列求平均
        avg_money.columns = ["code", "avg_money"]  # 重命名列：股票代码、平均成交额

        # 4. 按平均成交额排序并分为20组
        avg_money = avg_money.sort_values("avg_money", ascending=False)
        # 使用qcut进行分组，处理可能的重复值
        avg_money["money_group"] = pd.qcut(
            avg_money["avg_money"],
            20,
            labels=[f"组{i + 1}" for i in range(20)],
            duplicates="drop",
        )

        # 5. 创建成交额分组字典（组名: 股票列表）
        money_groups = {
            group: group_df["code"].tolist()
            for group, group_df in avg_money.groupby("money_group")
        }

        # 6. 计算每个成交额组站上均线的股票比例
        group_scores = pd.DataFrame(index=price_data.index)
        for group, stocks in money_groups.items():
            valid_stocks = list(set(above_ma.columns) & set(stocks))
            if valid_stocks:
                group_scores[group] = (
                    100 * above_ma[valid_stocks].sum(axis=1) / len(valid_stocks)
                )

        # 7. 计算近3天各组平均站上均线比例
        recent_group_data = group_scores[-3:].mean()
        _sorted_ma_data = recent_group_data.sort_values(ascending=False)

        # 8. 处理涨跌幅数据和每日指标
        df = data.reset_index().rename(
            columns={"level_0": "symbol", "level_1": "index"}
        )
        df["pct_change"] = df.groupby(["symbol"])["close"].pct_change()

        trade_days = get_trade_days(end_date=context.current_dt, count=3)
        by_date = trade_days[0]
        df = df[df.date >= by_date]

        grouped = df.groupby("date")
        _result = pd.DataFrame(
            {
                "up_ratio": grouped["pct_change"].apply(lambda x: (x > 0).mean()),
                "down_over": grouped["pct_change"].apply(
                    lambda x: (x <= -0.0985).sum()
                ),
            }
        ).reset_index()
        return _sorted_ma_data, _result

    # 计算趋势指标
    def calculate_trend_indicators(index_symbol="399101.XSHE"):
        """计算趋势指标: 过去3天内只要有一天处于高位，则视为高位，避免边界问题）"""
        # 参数设置
        high_lookback = 60  # 近期高点观察窗口
        high_proximity = 0.95  # 接近高点的阈值（95%）
        check_days = 2  # 检查过去1天的状态

        end_date = context.current_dt.replace(hour=14, minute=49)

        # 获取历史数据（需要包含足够天数，用于计算过去5天的指标）
        # 为了计算过去5天的指标，需要多获取high_lookback天数据（避免边界问题）
        total_days_needed = high_lookback + 10
        data = get_bars(
            index_symbol,
            end_dt=end_date,
            count=total_days_needed,
            unit="1d",
            fields=["date", "close", "high", "avg", "volume"],
            include_now=True,
            df=True,
        )

        data["date"] = pd.to_datetime(data["date"])

        # 计算过去每天的is_high状态
        _past_is_high_list = []

        # 遍历过去2天
        for i in range(-check_days, 0):
            # 数据切片，每次60天，不包含最后一天
            valid_data = data.iloc[:i][-high_lookback:]
            current_day_price = valid_data["close"].iloc[-1]

            # 计算当天的接近高点状态
            day_max_high = valid_data["high"].max()
            day_close_to_high = current_day_price >= (day_max_high * high_proximity)

            # 当天的is_high
            day_is_high = day_close_to_high
            _past_is_high_list.append(day_is_high)

        # 当前天的指标（最后一天）
        current_data = data[-high_lookback:]
        current_price = current_data["close"].iloc[-1]
        max_high = current_data["high"].max()
        close_to_high = current_price >= (max_high * high_proximity)

        # 将当前天加入列表，
        _past_is_high_list.append(close_to_high)

        # 新的is_high只要有一天为True，则为True
        _is_high = any(_past_is_high_list)

        return _is_high, _past_is_high_list

    cur_date_str = str(context.current_dt.date())
    if g.history_defense_date_list and cur_date_str <= g.history_defense_date_list[-1]:
        if cur_date_str in g.history_defense_date_list:
            g.defense_signal = True
            log.info("[防御] 组20防御: True, 处于历史触发范围内")
        else:
            g.defense_signal = False
            log.info("[防御] 触发防御: False, 未处于历史触发范围内")
    else:
        if g.defense_signal:
            sorted_ma_data, result = get_market_breadth(20)
            up_ratio = result.iloc[-3:]["up_ratio"].mean()
            avg_score = sorted_ma_data["组1"]
            defense_in_top = any(
                [ind in sorted_ma_data.index[:3] for ind in g.industries]
            )
            bank_exit_signal = not defense_in_top
            g.defense_signal = not bank_exit_signal
            log.info(
                f"[防御] 组20防御: {g.defense_signal} "
                f"组1宽度:{avg_score:.1f} "
                f"涨跌比:{up_ratio:.2f} "
                f"组20防御次数:{sum(g.cnt_bank_signal)} "
                f"top宽度:{sorted_ma_data.index[:5].tolist()}"
            )
        else:
            is_high, past_is_high_list = calculate_trend_indicators()
            if is_high:
                sorted_ma_data, result = get_market_breadth(20)
                defense_in_top = any(
                    [ind in sorted_ma_data.index[:2] for ind in g.industries]
                )
                avg_score = sorted_ma_data[
                    [ind not in g.industries for ind in sorted_ma_data.index]
                ].mean()
                above_average = avg_score < 60
                up_ratio = result.iloc[-3:]["up_ratio"].mean()
                above_ratio = up_ratio < 0.5
                is_bank_defense = defense_in_top and above_average and above_ratio
                g.defense_signal = is_bank_defense
                if is_bank_defense:
                    g.cnt_bank_signal.append(is_bank_defense)
                log.info(
                    f"[防御] 组20防御: {is_bank_defense} "
                    f"高位:{is_high}{past_is_high_list} "
                    f"组1宽度:{avg_score:.1f} "
                    f"涨跌比:{up_ratio:.2f} "
                    f"top宽度:{sorted_ma_data.index[:5].tolist()} "
                )
            else:
                g.defense_signal = False
                log.info(f"[防御] 触发防御: {g.defense_signal} 高位:{is_high}{past_is_high_list}")

    # 检测到需要防御进行空仓, 只空仓小市值的票
    now_time = context.current_dt
    if g.defense_signal:
        for stock in g.strategy_holdings[1][:]:
            current_data = get_price(
                stock,
                end_date=now_time,
                frequency="1m",
                fields=["close", "high_limit"],
                skip_paused=False,
                fq="pre",
                count=1,
                panel=False,
                fill_paused=True,
            )
            # 已涨停不清仓
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                close_position(stock)


def capital_balance_2(context):
    """2023.10之前ETF反弹的仓位纳入到ETF轮动中"""
    cur_date = str(context.current_dt.date())
    if cur_date < "2023-09-28" and g.strategy_ETF_2000_proportion_reset is None:
        g.portfolio_value_proportion[2] += g.strategy_ETF_2000_proportion
        g.portfolio_value_proportion[1] = 0
        g.strategy_ETF_2000_proportion_reset = False
    elif cur_date >= "2023-09-28" and g.strategy_ETF_2000_proportion_reset is False:
        strategy_total_value = (
            context.portfolio.total_value * g.strategy_ETF_2000_proportion
        )
        if g.strategy_holdings[2]:
            cur_etf = g.strategy_holdings[2]
            if context.portfolio.positions[cur_etf].closeable_amount > 0:
                o = order_value(context, cur_etf, -strategy_total_value)
                if o:
                    stock_show = f"{format_stock_code(cur_etf)}: ".ljust(20)
                    log.info(
                        f"[资金平衡] ETF反弹预留资金转移 {stock_show}  "
                        f"卖价{o.price:<7.2f}  "
                        f"成本{o.avg_cost:<7.2f}   "
                        f"卖量{o.amount:<7}   "
                        f"盈亏{(o.price - o.avg_cost) * o.amount:.2f}"
                        f"( {(o.price - o.avg_cost) / o.avg_cost * 100:.2f}% )"
                    )
        g.portfolio_value_proportion[2] -= g.strategy_ETF_2000_proportion
        g.portfolio_value_proportion[1] = g.strategy_ETF_2000_proportion
        g.strategy_ETF_2000_proportion_reset = True


def short_by_market_cap(context, stock_list):
    short_q = (
        query(valuation.code, valuation.market_cap)
        .filter(
            valuation.code.in_(stock_list),
            valuation.day == context.previous_date,
        )
        .order_by(valuation.market_cap.asc())
    )
    short_df = get_fundamentals(short_q)
    short_list = short_df["code"].unique().tolist()
    return short_list


""" ====================== 执行入口, 定时任务下发 ====================== """


def after_code_changed(context):
    unschedule_all()

    if g.portfolio_value_proportion[0] > 0:
        run_daily(prepare_small_cap_strategy, "9:05")
        if g.check_defense and g.defense_signal is None:
            check_defense_trigger(context)
        if g.DBL_control:
            run_daily(check_macd_divergence, "9:31")
        run_weekly(strategy_1_sell, 2, "09:40")
        run_weekly(strategy_1_buy, 2, "09:40:02")
        run_daily(sell_small_cap_stocks, time="10:00")
        # ATR止损价日常更新
        if g.enable_atr_stop_loss:
            run_daily(update_atr_stop_prices, "10:30")
            run_daily(update_atr_stop_prices, "14:00")
        if g.huanshou_check:
            run_daily(check_small_cap_turnover, "10:30")
        run_daily(check_small_cap_limit_up, "14:00")
        if g.check_defense:
            run_daily(check_defense_trigger, "14:50")
        run_daily(close_account, "14:50")

    # 策略2 ETF反弹策略
    if g.strategy_ETF_2000_proportion > 0:
        run_daily(capital_balance_2, "14:45")
        run_daily(strategy_2_sell, "14:49")
        run_daily(strategy_2_buy, "14:50")

    # 策略3 ETF轮动策略
    if g.portfolio_value_proportion[2] > 0:
        run_daily(check_atr_stop_loss_15, time='10:31')
        run_daily(strategy_3_sell, time='14:00')
        run_daily(strategy_3_buy, time='14:01')
    

    # 策略4 白马策略
    if g.portfolio_value_proportion[3] > 0:
        run_monthly(prepare_blue_chip_before_open, 1, time="8:00")
        run_monthly(adjust_blue_chip_position, 1, time="10:40")

    run_daily(make_record, "15:01")
    run_daily(print_summary, "15:02")
	
