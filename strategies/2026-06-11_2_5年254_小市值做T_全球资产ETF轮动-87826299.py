# Clone from JoinQuant
# postId: 878262999daea2bc8d6043a113b42955
# backtestId: 43c286ed441aefb8b3c5b5e76a854ffb
# title: 2.5年254%：小市值做T+全球资产ETF轮动

# ==============================================================================
# 【双轨并行旗舰版】全市场小市值做T +  ETF轮动 (全节点盈亏+数量播报版)
#  核心逻辑：
#  1. 资金隔离：采用数组框架 [小市值比例, ETF比例] 进行资金分配，互不干涉。
#  2. 定时任务集中管理：小市值与ETF的运行时间统一在 initialize 尾部列阵配置。
#  3. 全节点详尽播报：所有触发买卖的节点，强制输出【数量、金额、盈亏比例】。
#  4. 小市值核心：中小板综选股 + 基本面选股排雷 + 大跌避险冷静期 + ATR动态止损。
#  5. ETF核心：长短双周期动量 + 溢价率过滤 + 盘中高位盈利保护 + 防御货币基金。
# ==============================================================================

from jqdata import *
from jqfactor import *
from jqlib.technical_analysis import *
import datetime as dt
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import math
import warnings

# 屏蔽底层无害警告，让日志清清爽爽，不被无用报错刷屏
warnings.filterwarnings('ignore', message='.*Truncated incorrect DOUBLE value.*')

def initialize(context):
    """
    【策略总指挥部】开局运行一次，设置各种基础参数、费用和定时任务
    """
    set_option('use_real_price', True)       # 用真实价格交易
    set_option('avoid_future_data', True)    # 坚决避免未来函数，防止回测自欺欺人
    set_benchmark('000300.XSHG')             # 业绩基准设为沪深300
    
    # 日志显示级别（只看重要的）
    log.set_level('order', 'error')   
    log.set_level('system', 'error')  
    log.set_level('strategy', 'info') 
    
    log.info("=" * 60)
    log.info("🚀 双轨并行旗舰版：小市值 +  ETF轮动(长短双周期) 启动")
    log.info("📅 启动时间: {}".format(context.current_dt))
    log.info("💰 初始资金: {:.2f}元".format(context.portfolio.total_value))
    log.info("=" * 60)
    
    # 设定滑点（模拟真实的买卖价差损失）
    set_slippage(FixedSlippage(0.002), type="stock")
    set_slippage(FixedSlippage(0.001), type="fund")
    
    # 设定交易费用（印花税、佣金等）
    cost_configs = [
        ("stock", 0.0005, 0.855 / 10000, 5),  # 股票：卖出印花税万5，双向佣金万0.85，最低5元
        ("fund", 0, 0.5 / 10000, 5),          # ETF基金：无印花税，佣金万0.5
        ("mmf", 0, 0, 0)                      # 货币基金：无费用
    ]    
    for asset_type, close_tax, commission, min_comm in cost_configs:
        set_order_cost(OrderCost(
            open_tax=0, close_tax=close_tax,
            open_commission=commission, close_commission=commission,
            close_today_commission=0, min_commission=min_comm
        ), type=asset_type)
        
    # ================= 💰 资金分配比例 💰 =================
    # 数组说明：[小市值策略占比, ETF轮动策略占比]
    # 例如 [0.5, 0.5] 代表总资产各分50%；[0.7, 0.3] 代表小市值占70%，ETF占30%
    g.portfolio_value_proportion = [0.6, 0.4]  
    # ===================================================================================
    
    # ================= 策略1：小市值核心参数 =================
    g.index = '399101.XSHE'            # 选股池：中小板综指
    g.enable_dynamic_stock_num = False  # True为开启动态数量，False为固定数量
    g.buy_stock_count = 5              # 默认目标持仓股票数量：5只
    g.screen_stock_count = 15          # 备选池股票数量：15只（从前15名里挑）
    g.down_stock_count = 15            # 卖出判定池数量
    g.blacklist = []                   # 黑名单（不想买的股票代码填这里）

    g.stock_list = []                  # 每日候选股池
    g.current_date = None
    g.handle_data_flag = False

    # 分钟做T与收益止盈参数
    g.uprate = 8.0              # 分钟级暴涨风控：日内涨幅达到8%直接止盈卖出
    g.downrate = -2.5           # 分钟级暴跌风控：日内跌破-2.5%尝试抄底
    g.sell_cooldown_days = 1    # 卖出后的冷却天数（5个交易日内不准买回）
    g.hold_profit_rate = 30.0   # 整体持仓止盈率：这只股票赚够30%就落袋为安
    g.sold_stocks_dates = {}    # 记录每只股票卖出的日期，用于计算冷却期
    g.today_bought_stocks = set() # 记录今天刚买的票（T+1限制，今天买今天不能卖）
    g.today_sold_stocks = set()   # 记录今天卖出的票（今天卖了绝对不准今天再买回）
    g.today_limit_up_stocks = set()  # 记录当天触及涨停的票
    
    # 大盘连续暴跌冷静期参数
    g.in_cooldown = False       # 当前是否处于大跌冷静期空仓状态
    g.last_sell_date = None     # 记录进入冷静期清仓的日期
    g.days_since_sell = 0       # 记录已经冷静了几天
    g.return_threshold = -0.02  # 冷静期触发条件：单日组合跌幅达 -2%
    g.days = 3                  # 冷静期触发条件：连续3天跌破上述阈值
    g.cooldown_days = 5         # 强制冷静的时间：5个交易日
    g.portfolio_values = []     # 记录最近几天的总资产，用来算跌幅
    
    # 季节性空仓期（避开财报雷区）
    g.empty_months = []         # 若设为[1, 4]就是在1月和4月坚决空仓不买股票
    g.in_empty_period = False   
    g.no_trading_hold_signal = False  
    g.is_last_day_of_empty_period = False  

    # 五重风控开关与参数 
    g.macro_risk_triggered = True        # 宏观风控触发标识
    g.enable_consistency_control = True  # 开启微盘股一致性恐慌（踩踏）检测
    g.consistency_boll_period = 120  
    g.mini_cosi_list = []  
    g.DBL_control = True                 # 开启大盘顶背离检测（上涨乏力提前跑）
    g.enable_atr_stop_loss = False       # 开启ATR动态止损
    g.atr_period = 14                    # ATR计算周期
    g.atr_multiplier = 2.5               # ATR倍数：给予主力洗盘更多缓冲空间
    g.atr_stop_prices = {}               # 记录动态防守线
    g.huanshou_check = True              # 开启换手率异常检测（剔除死水股或爆炒出货股）

    # ================= 策略2： ETF轮动大池子参数 =================
    g.etf_pool = [
        # 境外
        "513100.XSHG",  # 纳指ETF
        "513520.XSHG",  # 日经ETF
        "513030.XSHG",  # 德国ETF
        # 商品
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF
        "159985.XSHE",  # 豆粕ETF
        "501018.XSHG",  # 南方原油
        # 债券
        "511090.XSHG",  # 30年国债ETF
        # 国内
        "513130.XSHG",  # 恒生科技  
    ]                           
    
    g.lookback_days = 25        # 短周期动量计算周期：看过去25天的涨势
    g.long_lookback_days = 250  # 长周期动量计算周期：看过去250天的长线趋势
    g.holdings_num = 2          # ETF目标持仓数量：持股2只（长短周期各1只）
    g.defensive_etf = "511880.XSHG"  # 防御资产：银华日利货币ETF（没行情时吃利息）
    g.min_money = 5000          # 交易最小金额限制
    
    # 风险与跌幅控制
    g.stop_loss = 0.95          
    g.loss = 0.97               # 近3日单日最大跌幅限制（跌破3%不买，防止接飞刀）
    g.loss_limit = g.loss
    g.min_score_threshold = 0   # 动量得分低于0说明都是跌的，不买
    g.max_score_threshold = 100.0
    
    # 成交量与短期动量防坑过滤
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0
    
    # 盘中高位盈利保护（防暴跌回撤）
    g.enable_profit_protection = True
    g.profit_protection_lookback = 1
    g.profit_protection_threshold = 0.05
    
    # --- 参数桥接：解决 San Ma 报表函数报错 ---
    g.m_days = g.lookback_days
    g.m_score = g.min_score_threshold
	
    # === 新增：溢价率过滤参数 ===
    g.enable_premium_filter = True      # 是否启用溢价率过滤
    g.premium_threshold = 0.20          # 溢价率阈值，例如0.02表示2%

    # 状态记录
    g.position_highs = {}
    g.rankings_cache = {'date': None}
    g.target_etfs = []          # 记录ETF每日目标持仓

    # ================= 定时任务列阵 =================
    
    if g.portfolio_value_proportion[0] > 0:
        # ----- 小市值专区定时任务 -----
        run_daily(prepare_stock_list, time='09:05')          # 盘前准备
        run_daily(check_empty_period, time='09:05:05')       # 检查空仓期
        run_daily(macro_risk_check, time='09:20')            # 大盘看门狗
        run_daily(before_trading_start, time='09:25')        # 盘前排雷选股
        run_daily(download_sell, time='09:30')               # 检查大跌冷静期
        run_daily(buy_stocks, time='09:40')                  # 集合竞价后买入
        run_daily(close_account_sell, time='10:00')          # 若空仓期则清仓
        run_daily(update_atr_stop_prices, time='10:30')      # 检查防守线
        run_daily(check_turnover, time='10:30')              # 检查异常换手
        run_daily(update_atr_stop_prices, time='14:00')      # 下午再检防守线
        run_daily(check_and_clean_stocks_in_cooldown, time='10:30') # 冷静期持续清仓
        run_daily(check_and_clean_stocks_in_cooldown, time='13:30')
        run_daily(check_and_clean_stocks_in_cooldown, time='14:30')
        run_daily(sell_stocks, time='14:49')                 # 尾盘根据排名淘汰卖出
    
    if g.portfolio_value_proportion[1] > 0:
        # ----- ETF独立专区定时任务 -----
        run_daily(profit_protection_check_172, time='11:00')  # 盘中高位保护（发现暴跌提前跑）
        run_daily(etf_rotation_sell, time='11:00')            # ETF轮动卖出判定
        run_daily(etf_rotation_buy, time='11:01')             # ETF轮动买入最新最强
    
    # 统一收盘报表
    run_daily(print_position_table, time='15:02')        

    # 小市值分钟级别盯盘（监控涨停/止损/止盈）
    if g.portfolio_value_proportion[0] > 0:
        for hour in range(9, 15):
            for minute in range(0, 60):
                current_time = "%02d:%02d" % (hour, minute)
                if ('09:31' < current_time < '11:30') or ('13:00' < current_time < '14:54'):
                    run_daily(interval_sell_buy, time=current_time)


# ==================== 小市值风控核心模块（排雷与避险） ====================

# 【防雷系统】九重财务排雷，踢出有问题和潜在暴雷的垃圾股
# （此注释为原版保留，以下逻辑已完美替换为基本面重度过滤选股逻辑）

def filter_basic_stock(context, stocks):
    """基础过滤：过滤ST、停牌、科创北交、次新股"""
    current_data = get_current_data()
    result = []
    for s in stocks:
        try:
            # 检查ST、停牌、科创北交
            if current_data[s].is_st or current_data[s].paused:
                continue
            if s[0] in ['4', '8'] or s[:2] == '68':
                continue
            # 检查次新股（上市不满360天）
            start_date = get_security_info(s).start_date
            if (context.current_dt.date() - start_date).days < 360:
                continue
            result.append(s)
        except:
            pass
    return result

def filter_limitup_stock(context, stocks, days):
    """过滤过去N日涨停的股票"""
    result = []
    for stock in stocks:
        try:
            df = attribute_history(stock, days, "1d", ["close", "high_limit"])
            if not any(df["close"] >= df["high_limit"]):
                result.append(stock)
        except:
            result.append(stock)
    return result

def filter_financial_stocks(stocks):
    """过滤金融股"""
    try:
        industry_data = get_industry(stocks)
        return [s for s in stocks if not industry_data.get(s, {}).get("sw_l1", {}).get("industry_name", "") in ["银行I", "非银金融I"]]
    except:
        return stocks

def filter_audit_opinion(context, stocks, years):
    """过滤审计意见异常的股票"""
    try:
        a = finance.STK_AUDIT_OPINION
        df = finance.run_query(
            query(a.code)
            .filter(
                a.code.in_(stocks),
                a.pub_date >= context.previous_date - timedelta(days=365 * years),
                a.pub_date <= context.previous_date,
                a.opinion_type_id.notin_([1, 6])
            )
        )
        excluded = df["code"].drop_duplicates().tolist()
        return [s for s in stocks if s not in excluded]
    except:
        return stocks

def macro_risk_check(context):
    """【大盘看门狗】每天早上检查一下整个大环境，环境不好直接清仓小市值"""
    g.macro_risk_triggered = False 
    if g.in_empty_period or getattr(g, 'in_cooldown', False): return
    
    # 检测1：微盘股群体是否发生恐慌踩踏（一致性暴跌）
    if g.enable_consistency_control:
        last_date = context.previous_date
        all_data = get_current_data()
        q = query(valuation.code, valuation.market_cap).order_by(valuation.market_cap.asc()).limit(500)
        stock_list = [code for code in get_fundamentals(q)["code"] if not all_data[code].paused and not all_data[code].is_st]
        if stock_list:
            df_chg = get_money_flow(stock_list, end_date=last_date, fields="change_pct", count=1)
            chg_med, chg_std = np.median(df_chg.change_pct), np.std(df_chg.change_pct)
            df_temp = df_chg[(df_chg.change_pct < (chg_med + chg_std)) & (df_chg.change_pct > (chg_med - chg_std))]
            consistency_last = len(df_temp) / len(stock_list)
            g.mini_cosi_list.append(consistency_last)
            
            cos_mean = np.mean(g.mini_cosi_list[-g.consistency_boll_period:]) if len(g.mini_cosi_list) >= g.consistency_boll_period else 0.8
            cos_std = np.std(g.mini_cosi_list[-g.consistency_boll_period:]) if len(g.mini_cosi_list) >= g.consistency_boll_period else 0.05
            
            if chg_med < -2 and consistency_last >= (cos_mean + cos_std):
                log.warn(f"🚨 宏观警报: 微盘股发生恐慌踩踏！触发避险！")
                g.macro_risk_triggered = True

    # 检测2：大盘（中小板指）是否发生MACD顶背离（上涨乏力，即将暴跌）
    if g.DBL_control and not g.macro_risk_triggered:
        grid = attribute_history("399101.XSHE", 100, fields=["close"]).dropna()
        if len(grid) > 40:
            grid["dif"], grid["dea"], grid["macd"] = mcad(grid.close)
            mask = (grid["macd"] < 0) & (grid["macd"].shift(1) >= 0)
            if mask.sum() >= 2:
                key2, key1 = mask[mask].index[-2], mask[mask].index[-1]
                if grid.close[key2] < grid.close[key1] and grid.dif[key2] > grid.dif[key1] > 0 and grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1] and grid["dif"].iloc[-10:].mean() < grid["dif"].iloc[-20:-10].mean():
                    log.warn(f"🚨 宏观警报: 大盘指标顶背离(上涨乏力)，触发避险！")
                    g.macro_risk_triggered = True

    # 如果有警报，直接强制进入冷静期清仓（仅清股票）
    if g.macro_risk_triggered: _enter_cooldown(context, reason="宏观风控强制避险")

def calculate_atr(security, context, period=14):
    """计算单只股票的ATR（真实波动幅度）"""
    df = get_price(security, end_date=context.previous_date, count=period + 1, frequency="daily", fields=["high", "low", "close"])
    if len(df) < period + 1: return None
    df["pre_close"] = df["close"].shift(1)
    df["tr"] = df[["high", "low", "pre_close"]].apply(lambda x: max(x["high"]-x["low"], abs(x["high"]-x["pre_close"]), abs(x["low"]-x["pre_close"])), axis=1)
    return df["tr"].iloc[-period:].mean()

def update_atr_stop_prices(context):
    """每天更新每只持仓股的防守生命线，如果赚钱了，防守线会往上移"""
    if not g.enable_atr_stop_loss or getattr(g, 'in_cooldown', False) or g.in_empty_period: return
    for stock, pos in list(context.portfolio.positions.items()):
        if stock in getattr(g, 'etf_pool', []) or stock == getattr(g, 'defensive_etf', ''): continue
        atr = calculate_atr(stock, context, g.atr_period)
        if atr:
            stop_price = pos.price - (g.atr_multiplier * atr)
            if stock not in g.atr_stop_prices: g.atr_stop_prices[stock] = pos.avg_cost - (g.atr_multiplier * atr)
            elif stop_price > g.atr_stop_prices[stock]: g.atr_stop_prices[stock] = stop_price

def check_turnover(context):
    """换手率检查：识别出冷门无流动性的死水股，或已被过度炒作即将见顶的股票"""
    if not g.huanshou_check or getattr(g, 'in_cooldown', False): return
    for stock, pos in list(context.portfolio.positions.items()):
        if stock in getattr(g, 'etf_pool', []) or stock == getattr(g, 'defensive_etf', '') or pos.closeable_amount == 0: continue
        try:
            cap = get_valuation(stock, end_date=context.previous_date, fields=["circulating_cap"], count=1)["circulating_cap"].iloc[0]
            if cap == 0: continue
            avg_turnover = (get_price(stock, end_date=context.previous_date, frequency="daily", fields=["volume"], count=20)["volume"] / (cap * 10000)).mean()
            rt_turnover = get_price(stock, start_date=context.current_dt.date(), end_date=context.current_dt, frequency="1m", fields=["volume"])["volume"].sum() / (cap * 10000)
            if avg_turnover > 0:
                if avg_turnover < 0.003: 
                    p_amt = (pos.price - pos.avg_cost) * pos.total_amount
                    p_rat = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
                    sell_qty = int(pos.total_amount)
                    order_target(stock, 0)
                    log.info(f'🧊 换手极低抛售: [{stock[:6]}] {_get_stock_name(stock)} | 数量: {sell_qty}股 | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)')
                elif rt_turnover > 0.1 and (rt_turnover/avg_turnover) > 2: 
                    p_amt = (pos.price - pos.avg_cost) * pos.total_amount
                    p_rat = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
                    sell_qty = int(pos.total_amount)
                    order_target(stock, 0)
                    log.info(f'🔥 换手异常抛售: [{stock[:6]}] {_get_stock_name(stock)} | 数量: {sell_qty}股 | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)')
        except: pass

def mcad(close, short=12, long=26, m=9):
    """计算MACD指标"""
    def ema(series, n): return pd.Series.ewm(series, span=n, min_periods=n - 1, adjust=False).mean()
    dif = ema(close, short) - ema(close, long)
    dea = ema(dif, m)
    return dif, dea, (dif - dea) * 2

# ==================== 工具与选股模块 ====================
def _get_stock_name(code):
    try: return get_current_data()[code].name
    except: return code[:6]

def _get_prev_trade_day(context):
    ds = get_trade_days(end_date=context.current_dt.date(), count=2)
    return str(ds[-2]) if len(ds) >= 2 else str(context.current_dt.date())

def _get_limit_rate(code, day_str, st_flag=False):
    rate = 0.20 if code.startswith('68') or (code.startswith('3') and day_str.replace('-','') >= '20200824') else 0.10
    if st_flag: rate = 0.05
    return rate

def _get_today_high_limit_from_yclose(code, today_str, yclose):
    cd = get_current_data()
    st_flag = False
    try: st_flag = bool(cd[code].is_st)
    except: pass
    rate = _get_limit_rate(code, today_str, st_flag)
    return yclose * (1.0 + rate)

def _limit_flags_today(context, codes):
    """判断涨跌停状态"""
    if not codes: return {'up_limit': [], 'down_limit': []}
    today, yday = str(context.current_dt.date()), _get_prev_trade_day(context)
    cd, up, down = get_current_data(), [], []
    for s in codes:
        try:
            ybar = get_price(s, end_date=yday, count=1, frequency='daily', fields=['close'])
            if ybar is None or ybar.empty: continue
            yclose = float(ybar['close'].iloc[-1])
            price = float(cd[s].last_price) if s in cd else yclose
            rate = _get_limit_rate(s, today, cd[s].is_st if s in cd else False)
            if price >= yclose * (1.0 + rate) - 0.01: up.append(s)
            if price <= yclose * (1.0 - rate) + 0.01: down.append(s)
        except: continue
    return {'up_limit': list(set(up)), 'down_limit': list(set(down))}

def _trading_days_since_last_sell(context):
    if not getattr(g, 'last_sell_date', None): return 0
    start = datetime.strptime(g.last_sell_date, '%Y-%m-%d').date() + timedelta(days=1)
    return len(get_trade_days(start_date=start, end_date=context.current_dt.date()))

def _is_empty_period(context):
    return context.current_dt.month in getattr(g, 'empty_months', [1, 4])


# ==================== 小市值 每日主流程模块 ====================

def before_trading_start(context):
    """【盘前会议】每天早上整理思路，算数据，选出最好的候选股票"""
    log.info("-" * 45 + str(context.current_dt.date()) + "-" * 45)
    g.in_empty_period = _is_empty_period(context)
    
    if getattr(g, 'in_cooldown', False) and g.days_since_sell >= g.cooldown_days:
        if not getattr(g, 'macro_risk_triggered', False):
            g.in_cooldown = False
            log.info("=" * 50)
            log.info("🟢 小市值冷静期结束，恢复买入")
            log.info("=" * 50)

    try:
        g.stock_list = get_index_stocks(g.index)
        g.initial_pool_size = len(g.stock_list) 
    except Exception:
        g.stock_list = []
        g.initial_pool_size = 0
            
    g.current_date = _get_prev_trade_day(context)
    g.today_bought_stocks, g.today_sold_stocks, g.today_limit_up_stocks = set(), set(), set()
    g.buy_executed, g.sell_executed = False, False
    g.days_since_sell = _trading_days_since_last_sell(context)
    
    check_and_clean_stocks_in_cooldown(context)

    # 动态调整小市值买入数量（看大盘温度）
    if getattr(g, 'enable_dynamic_stock_num', False):
        ma_para = 10  
        today = context.previous_date
        start_date = today - timedelta(days=ma_para * 2)
        index_df = get_price("399101.XSHE", start_date=start_date, end_date=today, frequency="daily")
        
        if not index_df.empty and len(index_df) >= ma_para:
            index_df["ma"] = index_df["close"].rolling(window=ma_para).mean()
            last_row = index_df.iloc[-1]
            diff = last_row["close"] - last_row["ma"]
            
            g.buy_stock_count = (
                3 if diff >= 800             
                else 4 if 200 <= diff < 500  
                else 5 if -200 <= diff < 200 
                else 6 if -500 <= diff < -200
                else 6                       
            )
            log.info(f"🌡️ 大盘偏离度(diff): {diff:.2f} | 今日小市值持仓数调整为 {g.buy_stock_count} 只")

    try:
        # 【选股】：1. 基础过滤（ST、停牌、科创北交、次新股）
        stocks = filter_basic_stock(context, g.stock_list)
        
        # 【选股】：2. 过滤涨停股票（过去5日）
        stocks = filter_limitup_stock(context, stocks, 5)
        
        # 【选股】：3. 按市值排序并筛选（扣非净利>0，PB>0）
        q = query(valuation.code, valuation.circulating_market_cap, valuation.market_cap).filter(
            valuation.code.in_(stocks),
            indicator.adjusted_profit > 0,
            valuation.pb_ratio > 0
        ).order_by(valuation.market_cap.asc()).limit(200)
        
        df = get_fundamentals(q, g.current_date)
        
        if df is None or df.empty: 
            g.handle_data_flag = False
            return
            
        stocks = list(df.code)
        
        # 【选股】：4. 过滤金融股
        stocks = filter_financial_stocks(stocks)
        
        # 【选股】：5. 过滤审计意见异常
        stocks = filter_audit_opinion(context, stocks, 2)
        
        if not stocks: 
            g.handle_data_flag = False
            return

        # 兼容原有的 df2 格式（提取通过过滤的股票并赋值给 df2 供后续价格精算调用）
        df = df[df['code'].isin(stocks)]
        df = df.sort_values(by='circulating_market_cap', ascending=True).sort_values(by='market_cap', ascending=True)
        g.df2 = df.set_index('code')
        g.handle_data_flag = True
        
        # 将最终通过选股系统清洗的股票名单，存入 g.safe_stocks
        g.safe_stocks = stocks
        log.info(f"✅ 盘前准备完毕! 基础候选池: {g.initial_pool_size}只 | 顺利通过排雷选股: {len(g.safe_stocks)}只")
        
    except Exception as e:
        log.error("🔴 盘前准备出错: {}".format(e))
        g.handle_data_flag = False


def _get_trade_stocks(context, mode='sell'):
    """二次精算实时市值，剔除涨跌停，输出候选"""
    if not getattr(g, 'df2', None) is not None or g.df2.empty or not hasattr(g, 'safe_stocks'): return []
    df = g.df2.copy()
    cd = get_current_data()
    
    safe_df = df.loc[df.index.intersection(g.safe_stocks)].copy()
    safe_df['curr_float_value'] = np.nan
    for code in safe_df.index.tolist():
        try:
            px = cd[code].last_price
            if math.isnan(px) or px <= 0:
                safe_df.loc[code, 'curr_float_value'] = safe_df.loc[code, 'circulating_market_cap']
                continue
            ybar = get_price(code, end_date=g.current_date, count=1, fields=['close'])
            if not ybar.empty:
                yclose = float(ybar['close'].iloc[-1])
                safe_df.loc[code, 'curr_float_value'] = safe_df.loc[code, 'circulating_market_cap'] * (px / yclose if yclose > 0 else 1.0)
            else:
                safe_df.loc[code, 'curr_float_value'] = safe_df.loc[code, 'circulating_market_cap']
        except:
            safe_df.loc[code, 'curr_float_value'] = safe_df.loc[code, 'circulating_market_cap']

    safe_df = safe_df.dropna(subset=['curr_float_value']).sort_values(by=['curr_float_value'])
    stocks = safe_df.head(g.screen_stock_count).index.tolist()
    
    if mode == 'buy' and stocks:
        log.info("🏆 小市值排名 (TOP{}):".format(min(15, len(stocks))))
        for idx, code in enumerate(stocks[:15], 1):
            try:
                market_cap = safe_df.loc[code, 'curr_float_value']
                stock_name = _get_stock_name(code)
                log.info("  {}. {}({})  市值:{:.2f}亿".format(idx, code[:6], stock_name, market_cap))
            except: pass

    lim = _limit_flags_today(context, stocks)
    up_limit_stock = set(lim['up_limit'])
    stocks = [s for s in stocks if s not in up_limit_stock]

    # 持仓仅计算小市值股票（严格过滤掉ETF）
    hold_codes = [c for c in context.portfolio.positions.keys() if c not in getattr(g, 'etf_pool', []) and c != getattr(g, 'defensive_etf', '')]
    lim_hold = _limit_flags_today(context, hold_codes)
    hold_up = set(lim_hold['up_limit'])

    if mode == 'sell':
        need_num = max(0, g.down_stock_count - len(hold_up))
        return list(hold_up) + stocks[:need_num]
    else:
        return list(hold_up) + stocks


def sell_stocks(context):
    """【尾盘调仓】把变大变弱的票卖掉，并打印数量与盈亏"""
    if g.in_empty_period or g.in_cooldown or not g.handle_data_flag or g.macro_risk_triggered: return
    target_set = set(_get_trade_stocks(context, mode='sell'))
    for code, pos in list(context.portfolio.positions.items()):
        try:
            # 隔离ETF不卖
            if code in getattr(g, 'etf_pool', []) or code == getattr(g, 'defensive_etf', ''): continue
            if pos.total_amount > 0:
                profit_rate = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
                profit_amount = (pos.price - pos.avg_cost) * pos.total_amount
                sell_qty = int(pos.total_amount)
                
                # 30% 止盈逻辑
                if profit_rate >= g.hold_profit_rate and code not in g.today_bought_stocks:
                    order_target(code, 0)
                    log.info(f"💰 止盈卖出 [{code[:6]}] {_get_stock_name(code)} | 数量: {sell_qty}股 | 盈亏: {profit_amount:.2f}元 ({profit_rate:.2f}%)")
                    continue
                    
            cd = get_current_data()[code]
            # 跌出排名、ST或退市的淘汰卖出逻辑
            if cd.is_st or ('退' in cd.name if cd.name else False) or code not in target_set:
                p_amt = (pos.price - pos.avg_cost) * pos.total_amount
                p_rat = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
                sell_qty = int(pos.total_amount)
                order_target(code, 0)
                log.info(f"📉 调仓卖出 [{code[:6]}] {_get_stock_name(code)} | 数量: {sell_qty}股 | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)")
        except: pass


def buy_stocks(context):
    """【早盘建仓】绝对固定配额版本：买入金额 = 小市值总金额 / 应持仓数量"""
    if g.in_empty_period or g.in_cooldown or not g.handle_data_flag or g.macro_risk_triggered: return
    targets = _get_trade_stocks(context, mode='buy')
    if not targets: return
    
    # 1. 找出当前手里的小市值持仓（这些老股绝对不碰）
    held = [c for c, p in context.portfolio.positions.items() if p.total_amount > 0 and c not in getattr(g, 'etf_pool', []) and c != getattr(g, 'defensive_etf', '')]
    need_num = max(0, g.buy_stock_count - len(held)) 
    if need_num <= 0: return  # 坑位满了，直接休息

    # 2. 挑选出需要新建仓的新标的（只挑手里没有的）
    new_targets = []
    for code in targets:
        if len(new_targets) >= need_num: break
        if code not in held:
            if code in getattr(g, 'today_sold_stocks', set()): continue
            if code in g.sold_stocks_dates:
                last_s = datetime.strptime(g.sold_stocks_dates[code], '%Y-%m-%d').date()
                if len(get_trade_days(start_date=last_s + timedelta(days=1), end_date=context.current_dt.date())) < getattr(g, 'cooldown_days', 5): continue
            new_targets.append(code)
            
    if not new_targets: return

    # 3. ==== 【核心修复：绝对固定配额计算】 ====
    # 小市值总金额 = 账户总资产 * 小市值资金比例
    total_stock_capital = context.portfolio.total_value * g.portfolio_value_proportion[0]
    
    # 理论买入金额 = 小市值总金额 / 应持仓数量 (预留1%防滑点超支)
    per_value = (total_stock_capital * 0.99) / max(1, g.buy_stock_count)
    
    # 4. ==== 【执行买入】 ====
    for code in new_targets:
        cd = get_current_data()[code]
        
        # 必须要保证兜里真实的可用现金够用，取较小值防止透支
        safe_buy_amount = min(per_value, context.portfolio.available_cash)
        
        # 限制1：买入金额不能少于 500 元
        # 限��2：买入金额必须够买 100 股（1手）
        if safe_buy_amount < 500 or safe_buy_amount < (cd.last_price * 100):
            log.info(f"⚠️ 资金拦截: 实际可分额 {safe_buy_amount:.2f}元 不足 500元 或不够买 100股，跳过买入 [{code[:6]}]")
            continue
            
        try:
            o = order_value(code, safe_buy_amount)
            if o and o.filled > 0:
                g.today_bought_stocks.add(code) 
                log.info(f"📈 建仓买入 [{code[:6]}] {_get_stock_name(code)} | 数量: {int(o.filled)}股 | 金额: {o.price * o.filled:.2f}元")
        except: pass


def interval_sell_buy(context):
    """【盘中盯盘】每分钟检查涨停止盈/大跌止损/盘中固定配额抄底"""
    if g.in_empty_period or g.in_cooldown: return
    cd = get_current_data()
    today_str = str(context.current_dt.date())

    for code, pos in list(context.portfolio.positions.items()):
        try:
            # 隔离ETF
            if code in g.today_sold_stocks or code in g.today_bought_stocks or pos.total_amount <= 0 or code in getattr(g, 'etf_pool', []) or code == getattr(g, 'defensive_etf', ''): continue
            yday = _get_prev_trade_day(context)
            ybar = get_price(code, end_date=yday, count=1, frequency='daily', fields=['close'])
            if ybar is None or ybar.empty: continue
            yclose = float(ybar['close'].iloc[-1])
            last = float(cd[code].last_price) if code in cd else yclose
            pct = (last / yclose - 1.0) * 100.0 if yclose > 0 else 0.0
            
            high_limit = _get_today_high_limit_from_yclose(code, today_str, yclose)
            is_limit_up = (last >= high_limit - 0.01)  
            
            p_amt = (pos.price - pos.avg_cost) * pos.total_amount
            p_rat = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
            sell_qty = int(pos.total_amount)
            
            if pct >= g.uprate:
                if is_limit_up:  
                    if code not in g.today_limit_up_stocks: g.today_limit_up_stocks.add(code)
                    continue
                order_target(code, 0)
                g.today_sold_stocks.add(code)
                g.sold_stocks_dates[code] = today_str
                log.info(f"🚀 分钟止盈 [{code[:6]}] {_get_stock_name(code)} | 数量: {sell_qty}股 | 涨幅: +{pct:.2f}% | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)")
                continue
                
            if getattr(g, 'enable_atr_stop_loss', False) and code in g.atr_stop_prices:
                stop_price = g.atr_stop_prices[code]
                if last <= stop_price:
                    order_target(code, 0)
                    g.today_sold_stocks.add(code)
                    g.sold_stocks_dates[code] = today_str
                    log.info(f"🛡️ ATR止损 [{code[:6]}] {_get_stock_name(code)} | 数量: {sell_qty}股 | 击穿价: {stop_price:.2f} | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)")
        except: pass

    if g.downrate is not None:
        # ==== 资金隔离，空出坑位才抄底新建仓 ====
        held = [c for c, p in context.portfolio.positions.items() if p.total_amount > 0 and c not in getattr(g, 'etf_pool', []) and c != getattr(g, 'defensive_etf', '')]
        need_num = max(0, g.buy_stock_count - len(held))
        if need_num <= 0: return # 没坑位直接返回，绝不给老仓位加仓
        
        # 【核心修复：绝对固定配额计算】
        total_stock_capital = context.portfolio.total_value * g.portfolio_value_proportion[0]
        per_value = (total_stock_capital * 0.99) / max(1, g.buy_stock_count)
        
        for code in list(context.portfolio.positions.keys()):
            try:
                # 必须是没有持仓的新标的才能触发盘中抄底
                if context.portfolio.positions[code].total_amount > 0 or code in g.today_bought_stocks: continue
                if code not in g.sold_stocks_dates: can_buy = True
                else:
                    last_s = datetime.strptime(g.sold_stocks_dates[code], '%Y-%m-%d').date()
                    can_buy = len(get_trade_days(start_date=last_s + timedelta(days=1), end_date=context.current_dt.date())) >= getattr(g, 'cooldown_days', 5)
                if not can_buy: continue
                
                yclose = get_price(code, end_date=_get_prev_trade_day(context), count=1, fields=['close'])['close'].iloc[-1]
                last = float(cd[code].last_price) 
                if (last / yclose - 1.0) * 100.0 <= g.downrate:
                    safe_buy_amount = min(per_value, context.portfolio.available_cash)
                    
                    # 同样的限制：不足 500 元，或者不够买 100 股，绝不瞎下单
                    if safe_buy_amount >= 500 and safe_buy_amount >= (cd[code].last_price * 100):
                        o = order_value(code, safe_buy_amount)
                        if o and o.filled > 0:
                            g.today_bought_stocks.add(code)
                            log.info(f"🔄 盘中空位抄底 [{code[:6]}] {_get_stock_name(code)} | 数量: {int(o.filled)}股 | 金额: {o.price * o.filled:.2f}元")
            except: pass

def calculate_portfolio_return(context):
    """仅根据整体市值判断连续大跌，用于小市值避险"""
    g.portfolio_values.append(context.portfolio.total_value)
    if len(g.portfolio_values) > 4: g.portfolio_values.pop(0)
    if len(g.portfolio_values) >= 2 and g.portfolio_values[-2] > 0:
        return (context.portfolio.total_value - g.portfolio_values[-2]) / g.portfolio_values[-2]
    return 0.0

def download_sell(context):
    if g.in_empty_period: return
    _ = calculate_portfolio_return(context)
    need_num = int(getattr(g, 'days', 3))
    if len(g.portfolio_values) < need_num + 1: return
    decline_days = sum(1 for i in range(need_num) if g.portfolio_values[-(i+2)] > 0 and (g.portfolio_values[-(i+1)] - g.portfolio_values[-(i+2)]) / g.portfolio_values[-(i+2)] <= g.return_threshold)
    if decline_days >= need_num: _enter_cooldown(context, reason="连续3天跌幅破2%")

def _enter_cooldown(context, reason=''):
    """【避险清仓】进入大跌冷静期，清空小市值并打印数量与盈亏，保留ETF"""
    for code, pos in list(context.portfolio.positions.items()):
        if code not in getattr(g, 'etf_pool', []) and code != getattr(g, 'defensive_etf', '') and pos.total_amount > 0: 
            p_amt = (pos.price - pos.avg_cost) * pos.total_amount
            p_rat = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
            sell_qty = int(pos.total_amount)
            order_target_value(code, 0)
            log.info(f"💥 避险清仓 [{code[:6]}] {_get_stock_name(code)} | 数量: {sell_qty}股 | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)")
            
    g.in_cooldown = True
    g.last_sell_date = context.current_dt.strftime('%Y-%m-%d')
    g.portfolio_values = []
    log.info("=" * 50)
    log.info(f"🔴 小市值进入冷静期: {reason} (ETF策略正常运行不受影响)")
    log.info("=" * 50)

def check_and_clean_stocks_in_cooldown(context):
    """【冷静期清理】如果还在冷静期内，新复牌的票也要清理掉并打印盈亏"""
    if not g.in_cooldown: return
    g.days_since_sell = _trading_days_since_last_sell(context)
    if g.days_since_sell >= g.cooldown_days and not getattr(g, 'macro_risk_triggered', False):
        g.in_cooldown = False
    else:
        for code in [c for c in context.portfolio.positions.keys() if c not in getattr(g, 'etf_pool', []) and c != getattr(g, 'defensive_etf', '')]: 
            pos = context.portfolio.positions[code]
            if pos.total_amount > 0:
                p_amt = (pos.price - pos.avg_cost) * pos.total_amount
                p_rat = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
                sell_qty = int(pos.total_amount)
                order_target_value(code, 0)
                log.info(f"🧹 冷静期清理 [{code[:6]}] {_get_stock_name(code)} | 数量: {sell_qty}股 | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)")

def prepare_stock_list(context):
    g.sold_today = []
    g.hold_list = [pos.security for pos in context.portfolio.positions.values()]
    g.no_trading_today_signal = _is_empty_period(context)
    if g.no_trading_today_signal:
        trade_days = get_trade_days(end_date=context.current_dt, count=2)
        if len(trade_days) >= 2:
            next_d = trade_days[-1].strftime('%m-%d')
            g.is_last_day_of_empty_period = not ((('04-01' <= next_d) and (next_d <= '04-30')) or (('01-01' <= next_d) and (next_d <= '01-30')))
    else: g.is_last_day_of_empty_period = False

def check_empty_period(context): pass

def close_account_sell(context):
    """【空仓期清理】1/4月空仓期，清仓小市值并打印盈亏，ETF依然独立运作"""
    if g.no_trading_today_signal and not g.no_trading_hold_signal:
        for stock in [s for s in g.hold_list if s not in getattr(g, 'etf_pool', []) and s != getattr(g, 'defensive_etf', '')]: 
            pos = context.portfolio.positions.get(stock)
            if pos and pos.total_amount > 0:
                p_amt = (pos.price - pos.avg_cost) * pos.total_amount
                p_rat = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
                sell_qty = int(pos.total_amount)
                order_target_value(stock, 0)
                log.info(f"❄️ 季节空仓清理 [{stock[:6]}] {_get_stock_name(stock)} | 数量: {sell_qty}股 | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)")
        g.no_trading_hold_signal = True


# ==================== 策略2：独立执行的  ETF长短双周期轮动模块 ====================

def get_cached_rankings(context, name, lookback_days, max_score):
    """使用缓存进行每日仅一次排名计算，节省系统资源，并打印排行榜"""
    today = context.current_dt.date()
    cache_key = f"{name}_{lookback_days}"
    
    if getattr(g, 'rankings_cache', None) is None or g.rankings_cache.get('date') != today:
        g.rankings_cache = {'date': today}
        
    if cache_key not in g.rankings_cache:
        ranked = get_ranked_etfs_172(context, lookback_days, max_score)
        g.rankings_cache[cache_key] = ranked
        
        # 打印 ETF 动量得分排行榜
        log.info(f"📊 今日 ETF 内核动量得分排名 - {name} (TOP 5):")
        if not ranked:
            log.info("  ⚠️ 空空如也 (所有ETF均被过滤或得分为负，准备退守防御资产)")
        else:
            for i, m in enumerate(ranked[:5]):
                etf_name = _get_stock_name(m['etf'])
                log.info(f"  TOP{i+1}: {etf_name.ljust(6)} ({m['etf'][:6]}) | 综合得分: {m['score']:.4f}")
        
    return g.rankings_cache[cache_key]

def get_premium_rate_172(code, date, max_back_days=5):
    """获取ETF溢价率 = (场内价格 - 基金净值) / 基金净值"""
    price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
    if price_data.empty: return None, None, None
    price = price_data['close'].iloc[0]

    net_value = None
    start_date = date - timedelta(days=max_back_days * 2)
    trade_days = get_trade_days(start_date=start_date, end_date=date)
    trade_days = [pd.to_datetime(d).date() for d in trade_days]
    for dt in reversed(trade_days):
        if dt > date: continue
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            break
        try:
            q = query(finance.FUND_NET_VALUE).filter(finance.FUND_NET_VALUE.code == code, finance.FUND_NET_VALUE.day == dt)
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                break
        except: continue

    if net_value is None or net_value == 0: return None, None, None
    return (price - net_value) / net_value, price, net_value

def check_profit_protection_172(security, context, lookback=None, threshold=None):
    """检查是否触发盘中盈利回撤保护"""
    if not getattr(g, 'enable_profit_protection', False): return False
    lookback = lookback or getattr(g, 'profit_protection_lookback', 1)
    threshold = threshold or getattr(g, 'profit_protection_threshold', 0.05)
    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback: return False
    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price
    return current_price <= max_high * (1 - threshold)

def profit_protection_check_172(context):
    """【高位保护清仓】盘中定时调用：如果ETF大幅回撤则强平保护并打印金额盈亏"""
    if not getattr(g, 'enable_profit_protection', False): return
    for sec in list(context.portfolio.positions.keys()):
        if (sec in getattr(g, 'etf_pool', []) or sec == getattr(g, 'defensive_etf', '')) and context.portfolio.positions[sec].total_amount > 0:
            if check_profit_protection_172(sec, context):
                pos = context.portfolio.positions[sec]
                p_amt = (pos.price - pos.avg_cost) * pos.total_amount
                p_rat = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
                market_val = pos.price * pos.total_amount
                sell_qty = int(pos.total_amount)
                order_target_value(sec, 0)
                log.info(f"🚨 ETF盈利保护清仓: {_get_stock_name(sec)} | 数量: {sell_qty}份 | 卖出金额: {market_val:.2f}元 | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)")

def get_annualized_returns_172(price_series, lookback_days):
    """计算年化收益率斜率"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1

def get_volume_ratio_172(context, security, lookback=None, threshold=None):
    """成交量异常放大防坑检测"""
    lookback = lookback or getattr(g, 'volume_lookback', 5)
    threshold = threshold or getattr(g, 'volume_threshold', 2)
    try:
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback: return None
        avg_vol = hist['volume'].mean()
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty: return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        if ratio > threshold: return ratio
        return None
    except: return None

def calculate_momentum_metrics_172(context, etf, lookback_days):
    """计算单一ETF的动量综合得分及各类条件过滤"""
    try:
        lookback = max(lookback_days, getattr(g, 'short_lookback_days', 10)) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < lookback_days: return None

        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices['close'].values, current_price)

        if check_profit_protection_172(etf, context): return None

        # 溢价率过滤
        if getattr(g, 'enable_premium_filter', False):
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = get_premium_rate_172(etf, prev_date)
            if premium is not None and premium > getattr(g, 'premium_threshold', 0.03): return None

        # 成交量异常过滤
        if getattr(g, 'enable_volume_check', False):
            vol_ratio = get_volume_ratio_172(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns_172(price_series, lookback_days)
                if annualized > getattr(g, 'volume_return_limit', 1): return None

        # 短期动量过滤
        if len(price_series) >= getattr(g, 'short_lookback_days', 10) + 1:
            short_ret = price_series[-1] / price_series[-(getattr(g, 'short_lookback_days', 10) + 1)] - 1
            short_ann = (1 + short_ret) ** (250 / getattr(g, 'short_lookback_days', 10)) - 1
        else: short_ann = 0
            
        if getattr(g, 'use_short_momentum_filter', False) and short_ann < getattr(g, 'short_momentum_threshold', 0.0): return None

        # R平方乘以年化斜率作为最终得分
        recent_y = np.log(price_series[-(lookback_days + 1):])
        x = np.arange(len(recent_y))
        weights = np.linspace(1, 2, len(recent_y))
        slope, intercept = np.polyfit(x, recent_y, 1, w=weights)
        ann_ret = math.exp(slope * 250) - 1
        ss_res = np.sum(weights * (recent_y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (recent_y - np.mean(recent_y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
        score = ann_ret * r2

        # 连续跌幅防接飞刀过滤
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < getattr(g, 'loss_limit', 0.97): return None

        return {'etf': etf, 'score': score}
    except: return None

def get_ranked_etfs_172(context, lookback_days, max_score):
    """排序获取符合条件的所有ETF名册"""
    etf_metrics = []
    for etf in getattr(g, 'etf_pool', []):
        if get_current_data()[etf].paused: continue
        metrics = calculate_momentum_metrics_172(context, etf, lookback_days)
        if metrics and (getattr(g, 'min_score_threshold', 0) <= metrics['score'] <= max_score):
            etf_metrics.append(metrics)
    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics

def check_defensive_etf_available_172(context):
    """检查防御ETF是否可以正常交易（未停牌且未涨跌停）"""
    data = get_current_data()
    etf = getattr(g, 'defensive_etf', '511880.XSHG')
    if data[etf].paused or data[etf].last_price >= data[etf].high_limit or data[etf].last_price <= data[etf].low_limit: 
        return False
    return True

def _get_best_etf_for_rotation(context):
    """最终裁定今天买哪两只（短周期和长周期各1只），没有合适的就买防御资产"""
    short_ranked = get_cached_rankings(context, "短周期", getattr(g, 'lookback_days', 25), 6.0)
    long_ranked = get_cached_rankings(context, "长周期", getattr(g, 'long_lookback_days', 250), 0.5)
    
    target_etfs = []
    
    if short_ranked:
        target_etfs.append(short_ranked[0]['etf'])
        
    if long_ranked:
        target_etfs.append(long_ranked[0]['etf'])
        
    # 去重（如果长短周期选出同一只，就只重仓买它）
    target_etfs = list(set(target_etfs))
            
    if not target_etfs and check_defensive_etf_available_172(context):
        target_etfs = [getattr(g, 'defensive_etf', '511880.XSHG')]
        
    if target_etfs:
        for etf in target_etfs:
            log.info("🎯 ETF 内核最终选择: {}".format(_get_stock_name(etf)))
        return target_etfs
    else:
        log.info("❌  ETF 判断：无符合动量及安全条件的ETF")
        return []

def etf_rotation_sell(context):
    """【轮动卖出】到达自定义时间，独立处理ETF卖出，并打印卖出金额与盈亏"""
    g.target_etfs = _get_best_etf_for_rotation(context)
    
    # 查找手里的ETF
    current_etfs = [c for c, pos in context.portfolio.positions.items() if pos.total_amount > 0 and (c in getattr(g, 'etf_pool', []) or c == getattr(g, 'defensive_etf', ''))]
    
    for current_etf in current_etfs:
        if current_etf not in getattr(g, 'target_etfs', []):
            pos = context.portfolio.positions[current_etf]
            market_val = pos.price * pos.total_amount
            p_amt = (pos.price - pos.avg_cost) * pos.total_amount
            p_rat = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost != 0 else 0
            sell_qty = int(pos.total_amount)
            order_target_value(current_etf, 0)
            log.info(f"📉 ETF换车卖出: {_get_stock_name(current_etf)} | 数量: {sell_qty}份 | 卖出金额: {market_val:.2f}元 | 盈亏: {p_amt:.2f}元 ({p_rat:.2f}%)")
        else:
            pos = context.portfolio.positions[current_etf]
            market_val = pos.price * pos.total_amount
            log.info(f"🛡️ ETF动量未变，继续持有最佳标的: {_get_stock_name(current_etf)} | 当前市值: {market_val:.2f}元")

def etf_rotation_buy(context):
    """到达自定义时间，使用专属资金买入ETF，并打印成交数量与金额"""
    if not getattr(g, 'target_etfs', []): return
        
    current_etfs = [c for c, pos in context.portfolio.positions.items() if pos.total_amount > 0 and (c in getattr(g, 'etf_pool', []) or c == getattr(g, 'defensive_etf', ''))]
    
    target_len = len(g.target_etfs)
    
    # ==== 【核心】使用数组里的比例，只动用分配给ETF的那一半总资金 ====
    total_etf_capital = context.portfolio.total_value * g.portfolio_value_proportion[1]
    
    # 平分算力：如果只有一只（选出相同），则全仓这一只；否则各占一半。
    per_value = (total_etf_capital * 0.99) / max(1, target_len)
    
    for etf in g.target_etfs:
        if etf not in current_etfs:
            safe_buy_amount = min(per_value, context.portfolio.available_cash)
            if safe_buy_amount > g.min_money:
                order = order_value(etf, safe_buy_amount)
                if order and order.filled > 0:
                    actual_value = order.price * order.filled
                    log.info(f"🚀 ETF建仓：买入 {_get_stock_name(etf)} | 数量: {int(order.filled)}份 | 成交金额: {actual_value:.2f}元")
                else:
                    log.info(f"🚀 ETF建仓：计划买入 {_get_stock_name(etf)} | 委托金额: {safe_buy_amount:.2f}元 (等待成交)")

# ==================== 交易明细与收盘展示 ====================
def print_position_table(context):
    """每天收盘帮你算一笔账：今天持有啥，赚了还是亏了"""
    total_value = context.portfolio.total_value
    current_stocks = context.portfolio.positions
    has_position = any(pos.total_amount > 0 for pos in current_stocks.values())
    
    if not has_position:
        log.info("当前总资产\n+------------+\n|  休息ing   |\n+------------+\n| 资产: {:.2f} |\n+------------+".format(total_value))
        return
    
    try:
        from prettytable import PrettyTable
        import prettytable
        table = PrettyTable([
            " 所属策略 ", " 代码 ", " 名称 ", " 持仓数量 ", " 持仓价格 ",
            " 当前价格 ", " 盈亏数额 ", " 盈亏比例 ", " 股票市值 ", " 仓位占比 "
        ])
        table.hrules = prettytable.ALL
        small_cap_value, etf_value = 0, 0
        
        for stock, position in current_stocks.items():
            current_shares = int(position.total_amount)
            if current_shares <= 0: continue
            
            current_price = round(position.price, 3)
            avg_cost = round(position.avg_cost, 3)
            profit_ratio = (current_price - avg_cost) / avg_cost if avg_cost != 0 else 0
            profit_ratio_percent = "{:.2f}% {}".format(profit_ratio * 100, '↑' if profit_ratio > 0 else '↓')
            profit_amount = round((current_price - avg_cost) * current_shares, 2)
            market_value = round(current_shares * current_price, 2)
            
            # 分类统计资产
            if stock in getattr(g, 'etf_pool', []) or stock == getattr(g, 'defensive_etf', ''):
                strategy = "ETF轮动"
                etf_value += market_value
            else:
                strategy = "小市值"
                small_cap_value += market_value
                
            table.add_row([
                strategy, stock.split(".")[0], _get_stock_name(stock),
                current_shares, avg_cost, current_price, profit_amount,
                profit_ratio_percent, market_value,
                "{:.2f}%".format(market_value / total_value * 100)  
            ])
            
        if small_cap_value > 0:
            table.add_row([" 小市值 ", "", "", "", "", "", "", "", "{:.1f}".format(small_cap_value), "{:.2f}%".format(small_cap_value / total_value * 100)])
        if etf_value > 0:
            table.add_row([" ETF轮动 ", "", "", "", "", "", "", "", "{:.1f}".format(etf_value), "{:.2f}%".format(etf_value / total_value * 100)])
            
        available_cash = context.portfolio.available_cash
        table.add_row([" Cash ", "", "", "", "", "", "", "", "{:.2f}".format(available_cash), "{:.2f}%".format(available_cash / total_value * 100)])
        table.add_row([" 总资产 ", "", "", "", "", "", "", "", "{:.2f}".format(total_value), ""])
        log.info('当前总资产\n{}'.format(table))
        
    except ImportError:
        log.info("💰 总资产: {:.2f}元".format(total_value))