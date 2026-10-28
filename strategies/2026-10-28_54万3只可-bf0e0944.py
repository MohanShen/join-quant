# Clone from JoinQuant
# postId: bf0e094410458e8e67053255212aa8bb
# backtestId: c4b2d85a539e558b371cb83e2d19e794
# title: 54万3只可******

import jqdata
import talib as ta
import numpy as np
import datetime
import pandas as pd
from collections import defaultdict
# ==================== 核心工具函数：日期/交易判断 ====================
def get_previous_trading_date(target_date):
    """获取指定日期的前一个交易日（兼容回测/实盘）"""
    if not isinstance(target_date, datetime.date):
        raise ValueError("target_date必须是datetime.date类型")
    
    prev_date = target_date - datetime.timedelta(days=1)
    while True:
        try:
            trading_calendar = get_trade_days(start_date=prev_date, end_date=prev_date)
            if len(trading_calendar) > 0:
                return prev_date
        except:
            if prev_date.weekday() not in (5, 6):
                return prev_date
        prev_date -= datetime.timedelta(days=1)

def is_real_trade(context):
    """判断当前运行模式：回测/模拟/实盘"""
    try:
        return context.account_id is not None
    except:
        return '回测' not in str(context).lower()

def get_unified_price_data(stock, context, count=2, frequency='daily'):
    """统一回测/实盘的价格数据获取逻辑（消除未来函数）- 修复：补全open字段"""
    select_time = datetime.time(9, 30)
    current_dt = context.current_dt
    
    if is_real_trade(context):
        data_end_dt = datetime.datetime.combine(current_dt.date(), select_time) - datetime.timedelta(minutes=1)
    else:
        data_end_dt = current_dt
    
    df = get_price(
        stock,
        count=count,
        end_date=data_end_dt,
        frequency=frequency,
        fields=['open','close','high','low','volume'],
        fq='pre'
    )
    return df

# ==================== 核心修改：取daily.open和盘中价的最大值，适配低于20日新高逻辑 ====================
def get_latest_20day_high(context, stock, include_intraday=False):
    """
    修复后逻辑：正确计算20日新高（包含真实开盘价+当日盘中高点），适配低于20日新高判断
    1. 历史部分：前19个交易日的收盘价（收盘价新高口径）
    2. 当日部分：取daily数据open + 当日盘中价的最大值（核心修改：取两者最高价作为当日有效参考）
    3. 20日新高 = max(前19日收盘价新高, 当日有效参考价, 当日盘中最新价)
    4. include_intraday：是否包含当日盘中价（False=仅用前20日收盘价新高，避免盘中价导致的计算偏差）
    """
    try:
        # 1. 获取前19个交易日的日线数据（含close，用于计算历史收盘价新高）
        hist_19d = get_unified_price_data(stock, context, count=19, frequency='daily')
        if len(hist_19d) < 1:
            # 兜底：获取前20日日线数据，取收盘价新高
            hist_20d = get_unified_price_data(stock, context, count=20, frequency='daily')
            fallback_high = hist_20d['close'].max() if len(hist_20d) > 0 else 0
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.info(f"{stock}({name}) 前19日数据不足，兜底前20日收盘价新高：{fallback_high:.2f}")
            return fallback_high
        
        # 提取前19日收盘价的最大值（历史部分新高）
        prev_19d_close_max = hist_19d['close'].max()

        # 2. 获取当日有效开盘参考价（核心修改：取daily.open 和 盘中价的最大值）
        today_daily = get_unified_price_data(stock, context, count=1, frequency='daily')
        
        # 步骤1：从daily数据中提取open（原逻辑保留，过滤无效值）
        daily_open = 0
        if len(today_daily) >= 1 and 'open' in today_daily.columns:
            daily_open_candidate = today_daily['open'].iloc[-1]
            if daily_open_candidate > 0 and not pd.isna(daily_open_candidate):
                daily_open = daily_open_candidate
        
        # 步骤2：获取盘中价（实盘/回测兼容，过滤无效值）
        intraday_price = 0
        current_data = get_current_data()[stock]
        if current_data and include_intraday:
            intraday_candidate = current_data.last_price if is_real_trade(context) else current_data.high
            if intraday_candidate > 0 and not pd.isna(intraday_candidate):
                intraday_price = intraday_candidate
        
        # 步骤3：核心修改——取两者最大值作为当日有效开盘参考价
        today_open = max(daily_open, intraday_price)
        
        # 步骤4：最终兜底（两者均无效时，用历史新高）
        if today_open <= 0 or pd.isna(today_open):
            today_open = prev_19d_close_max
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.info(f"{stock}({name}) 当日daily.open和盘中价均异常，兜底使用前19日收盘价新高：{today_open:.2f}")

        # 3. 获取当日盘中最新价（真实盘中价格，原逻辑保留）
        latest_intraday_price = 0
        if current_data and include_intraday:
            latest_intraday_price = current_data.last_price if is_real_trade(context) else current_data.high
            if latest_intraday_price <= 0 or pd.isna(latest_intraday_price):
                latest_intraday_price = today_open

        # 4. 计算最终20日新高（区分是否包含当日盘中价）
        if include_intraday:
            final_20day_high = max(prev_19d_close_max, today_open, latest_intraday_price)
        else:
            # 不包含当日盘中价：取前20日收盘价新高（避免盘中价导致的计算偏差）
            hist_20d_close = get_unified_price_data(stock, context, count=20, frequency='daily')['close']
            final_20day_high = hist_20d_close.max() if len(hist_20d_close) >=20 else prev_19d_close_max
        
        # 详细日志，方便验证修改效果
        name = get_security_info(stock).display_name if get_security_info(stock) else ""
        log.info(f"{stock}({name}) 20日新高计算明细：前19日收盘价新高={prev_19d_close_max:.2f} | 当日daily.open={daily_open:.2f} | 当日盘中价={intraday_price:.2f} | 当日有效开盘价（最大值）={today_open:.2f} | 当日盘中最新价={latest_intraday_price:.2f} | 最终20日新高={final_20day_high:.2f}")
        
        return final_20day_high
    except Exception as e:
        name = get_security_info(stock).display_name if get_security_info(stock) else ""
        log.warning(f"获取{stock}({name})最新20日新高异常：{str(e)}，兜底前20日收盘价新高")
        hist_20d = get_unified_price_data(stock, context, count=20, frequency='daily')
        return hist_20d['close'].max() if len(hist_20d) > 0 else 0

# ==================== 修复：流动性校验函数（兼容模拟/回测环境）====================
def check_liquidity(context, stock):
    """
    流动性校验：避免买入低成交、低流动性标的，降低交易滑点和无法成交风险
    修复点：
    1. 模拟/回测环境跳过当日成交量校验（_CurrentObj无volume属性）
    2. 仅用日线成交量做校验，保证兼容性
    """
    try:
        # 获取近5日日线成交量数据
        hist_5d = get_unified_price_data(stock, context, count=5, frequency='daily')
        if len(hist_5d) < 5:
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.info(f"{stock}({name}) 近5日数据不足，跳过流动性校验")
            return True
        
        avg_vol_5d = hist_5d['volume'].mean() / 100  # 转换为手
        if avg_vol_5d < 500:
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.info(f"{stock}({name}) 流动性不足：近5日平均成交量{avg_vol_5d:.0f}手 < 500手")
            return False
        
        # 仅实盘环境校验当日成交量（模拟/回测跳过）
        if is_real_trade(context):
            current_data = get_current_data()[stock]
            if current_data and hasattr(current_data, 'volume'):
                today_vol = current_data.volume / 100  # 实时成交量（手）
                if today_vol < 100:
                    name = get_security_info(stock).display_name if get_security_info(stock) else ""
                    log.info(f"{stock}({name}) 当日流动性不足：当前成交量{today_vol:.0f}手 < 100手")
                    return False
        
        return True
    except Exception as e:
        name = get_security_info(stock).display_name if get_security_info(stock) else ""
        log.warning(f"{stock}({name}) 流动性校验异常：{str(e)}，默认通过校验")
        return True

# ==================== 账户权限过滤函数（修改：适配全部00/60开头股票）====================
def is_stock_tradable(stock):
    """过滤可交易标的：仅保留00、60开头股票，排除300、688、8、4开头"""
    allow_prefix = ('000', '002', '600', '603', '601', '605')
    forbid_prefix = ('300', '688', '8', '4', '001', '003')
    
    if stock.startswith(forbid_prefix):
        return False
    if stock.startswith(allow_prefix):
        return True
    return False

# ==================== 新增：新股过滤函数（核心：排除上市不满30个交易日的新股）====================
def is_new_stock(context, stock):
    """判断是否为新股：上市交易日数不满30个，返回True（需过滤）"""
    try:
        # 获取股票上市日期
        stock_info = get_security_info(stock)
        if not stock_info:
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.warning(f"{stock}({name}) 无法获取上市信息，暂按非新股处理")
            return False
        
        list_date = stock_info.start_date.date()
        current_date = context.current_dt.date()
        
        trade_days = get_trade_days(start_date=list_date, end_date=current_date)
        trade_days_count = len(trade_days)
        
        if trade_days_count < 30:
            name = stock_info.display_name
            log.info(f"{stock}({name}) 为新股：上市{trade_days_count}个交易日（不满30个），过滤")
            return True
        return False
    except Exception as e:
        name = get_security_info(stock).display_name if get_security_info(stock) else ""
        log.warning(f"{stock}({name}) 新股判断异常：{str(e)}，暂按非新股处理")
        return False

# ==================== 涨停判断函数 ====================
def is_stock_limit_up(context, stock):
    """统一回测/实盘的涨停判断逻辑（返回：是否涨停 + 详细信息，方便日志排查）"""
    try:
        current_data = get_current_data()[stock]
        if not current_data:
            return False, "获取current_data失败（返回None）"
        
        current_price = current_data.last_price if is_real_trade(context) else current_data.close
        if current_price <= 0:
            return False, f"当前价格异常（current_price={current_price}）"
        
        close_data = get_unified_price_data(stock, context, count=2, frequency='daily')
        if len(close_data) < 2:
            return False, "获取昨日收盘价失败（数据不足2条）"
        
        close_yesterday = close_data['close'].iloc[-2]
        if close_yesterday == 0:
            return False, f"昨日收盘价异常（close_yesterday={close_yesterday}）"
        
        # 计算涨停价
        if 'ST' in current_data.name or '*ST' in current_data.name:
            limit_up_price = round(close_yesterday * 1.05, 2)
            limit_type = "ST股（5%）"
        else:
            limit_up_price = round(close_yesterday * 1.1, 2)
            limit_type = "普通股（10%）"
        
        is_limit_up = abs(current_price - limit_up_price) <= 0.01
        name = get_security_info(stock).display_name if get_security_info(stock) else ""
        info = f"{stock}({name}) {limit_type} | 昨日收盘价={close_yesterday:.2f} | 涨停价={limit_up_price:.2f} | 当前价={current_price:.2f}"
        return is_limit_up, info
    except Exception as e:
        name = get_security_info(stock).display_name if get_security_info(stock) else ""
        return False, f"{stock}({name}) 涨停判断函数执行异常：{str(e)}"

# ==================== 【持仓修改】动态仓位分配函数（修复：按剩余资金动态调整）====================
def calculate_dynamic_position_ratio(target_buy_count):
    """策略1核心分仓逻辑：按目标买入数量动态分配单只仓位比例"""
    if target_buy_count == 3:
        return 0.33  # 3只各占33%
    elif target_buy_count == 2:
        return 0.49  # 2只各占49%
    elif target_buy_count == 1:
        return 0.99  # 1只占99%
    else:
        return 0.33  # 兜底比例

def calculate_target_position_value(context, target_buy_count, used_cash=0):
    """
    修复：计算单只股票的目标持仓市值（扣除已使用资金）
    used_cash：前几只股票已占用的资金
    """
    total_portfolio_value = context.portfolio.total_value
    position_ratio = calculate_dynamic_position_ratio(target_buy_count)
    # 总可用资金 = 总资产 * 单只比例 - 已使用资金
    total_available = total_portfolio_value * position_ratio - used_cash
    # 按剩余目标数量均分
    remaining_count = max(target_buy_count - len([x for x in used_cash if x > 0]), 1) if isinstance(used_cash, list) else target_buy_count
    target_position_value = total_available / remaining_count
    
    return max(target_position_value, 0), position_ratio

def calculate_buy_amount(stock, target_value, current_price, min_amount=100):
    """
    修复：根据目标市值计算可买入股数（确保至少100股，不足时跳过）
    min_amount：最小买入数量（100股）
    """
    if current_price <= 0 or target_value <= 0:
        return 0
    
    usable_cash = target_value * (1 - 0.0003)
    buy_amount = int(usable_cash / current_price / 100) * 100
    
    # 修复：不足100股直接返回0，避免委托失败
    if buy_amount < min_amount:
        name = get_security_info(stock).display_name if get_security_info(stock) else ""
        log.warning(f"{stock}({name}) 计算买入数量不足{min_amount}股（{buy_amount}股），跳过买入")
        return 0
    
    return buy_amount

# ==================== 新增：二次筛选函数（9:51执行）====================
def recheck_selected_stocks(context):
    """
    9:51二次筛选：重新验证9:40选出的股票是否仍满足所有买入条件
    核心：实时校验股价、流动性、涨停状态、20日新高阈值等动态条件
    """
    if g.selected_stocks_cache is None or len(g.selected_stocks_cache) == 0:
        log.info("9:51二次筛选：无初始选股结果，无需筛选")
        return
    
    original_list = g.selected_stocks_cache.copy()
    rechecked_list = []
    
    log.info("="*50 + " 9:51二次筛选开始 " + "="*50)
    log.info(f"初始选股数量：{len(original_list)}只")
    
    for stock in original_list:
        try:
            current_data = get_current_data()[stock]
            if not current_data:
                name = get_security_info(stock).display_name if get_security_info(stock) else ""
                log.info(f"剔除{stock}({name})：无法获取实时数据")
                continue
            
            # 1. 校验是否停牌
            if current_data.paused:
                name = get_security_info(stock).display_name if get_security_info(stock) else ""
                log.info(f"剔除{stock}({name})：实时停牌")
                continue
            
            # 2. 校验是否涨停（涨停不买）
            is_limit, _ = is_stock_limit_up(context, stock)
            if is_limit:
                name = get_security_info(stock).display_name if get_security_info(stock) else ""
                log.info(f"剔除{stock}({name})：实时涨停")
                continue
            
            # 3. 校验流动性（实时更新）
            if not check_liquidity(context, stock):
                name = get_security_info(stock).display_name if get_security_info(stock) else ""
                log.info(f"剔除{stock}({name})：实时流动性不足")
                continue
            
            # 4. 校验20日新高阈值（实时价格）
            current_price = current_data.last_price if is_real_trade(context) else current_data.close
            if current_price <= 0:
                name = get_security_info(stock).display_name if get_security_info(stock) else ""
                log.info(f"剔除{stock}({name})：实时价格异常")
                continue
            
            latest_hhv_20 = get_latest_20day_high(context, stock, include_intraday=True)
            if latest_hhv_20 <= 0:
                name = get_security_info(stock).display_name if get_security_info(stock) else ""
                log.info(f"剔除{stock}({name})：无法获取实时20日新高")
                continue
            
            below_high_rate = (latest_hhv_20 - current_price) / latest_hhv_20
            if below_high_rate < g.buy_below_high_rate:
                name = get_security_info(stock).display_name if get_security_info(stock) else ""
                log.info(f"剔除{stock}({name})：实时跌深不足（当前{below_high_rate*100:.1f}% < 要求{g.buy_below_high_rate*100:.1f}%）")
                continue
            
            # 5. 校验是否仍为可交易标的（兜底）
            if not is_stock_tradable(stock):
                name = get_security_info(stock).display_name if get_security_info(stock) else ""
                log.info(f"剔除{stock}({name})：非可交易标的")
                continue
            
            # 所有条件均满足，保留
            rechecked_list.append(stock)
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.info(f"保留{stock}({name})：所有实时条件均满足")
            
        except Exception as e:
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.error(f"二次筛选{stock}({name})出错：{str(e)}，剔除该标的")
            continue
    
    # 更新缓存为二次筛选后的结果
    g.selected_stocks_cache = rechecked_list
    # 同步更新待卖出股票池
    hold_stocks = set(context.portfolio.positions.keys())
    g.need_sell_stocks = hold_stocks - set(rechecked_list)
    
    log.info(f"二次筛选完成：最终保留{len(rechecked_list)}只 | 剔除{len(original_list)-len(rechecked_list)}只")
    log.info(f"二次筛选后选股列表：{rechecked_list}")
    log.info("="*50 + " 9:51二次筛选结束 " + "="*50)

# ==================== 主策略 ====================
def initialize(context):
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(FixedSlippage(0.0002))
    set_benchmark('000905.XSHG')
    
    g.stock_pool = get_all_securities(['stock']).index.tolist()
    g.stop_loss_rate = 0.04
    g.take_profit_drawdown = 0.02
    g.pool_stock_take_profit_drawdown = 0.02
    g.buy_below_high_rate = 0.0015  # 保留策略2的买入阈值（可按需调整）
    g.track_high = {}
    g.watch_list = []
    g.selected_stocks_cache = None
    g.stock_high_dict_cache = {}
    g.today_bought_stocks = set()
    g.need_sell_stocks = set()
    g.sold_cash = 0.0
    g.executed_sold_cash = 0.0
    
    # 【持仓修改】新增：半仓卖出资金记录（策略1核心变量）
    g.half_sold_cash = 0.0
    # 【持仓修改】新增：最大持仓数（策略1核心限制，固定3只）
    g.max_pos = 3
    
    # 【持仓修改】调整交易时间节点，适配策略1的半仓轮动节奏（和策略1一致）
    run_daily(before_trading_start, time='09:00')  
    run_daily(select_stock, time='09:40')          # 初次选股
    run_daily(sell_unselected_stocks, time='09:50')# 清仓非池股
    run_daily(recheck_selected_stocks, time='09:51')# 二次筛选（新增）
    run_daily(buy_after_below_high, time='09:52')  # 买入+半仓卖出
    run_daily(calibrate_position, time='09:55')    # 仓位校准
    run_daily(stop_loss_take_profit, time='every_bar')

def before_trading_start(context):
    g.today_bought_stocks = set()
    g.need_sell_stocks = set()
    g.selected_stocks_cache = None
    g.stock_high_dict_cache = {}
    g.watch_list = []
    g.sold_cash = 0.0
    g.executed_sold_cash = 0.0
    
    # 【持仓修改】每日重置半仓卖出资金（策略1逻辑）
    g.half_sold_cash = 0.0
    
    g.stock_pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()
    
    log.info("="*60)
    log.info(f"交易日: {context.current_dt.date()} | 运行模式: {'实盘/模拟' if is_real_trade(context) else '回测'}")
    log.info(f"全部A股数量: {len(g.stock_pool)} | 当前持仓: {len(context.portfolio.positions)}只")
    # 【持仓修改】更新仓位配置说明（改为策略1的半仓轮动逻辑）
    log.info(f"仓位配置：半仓轮动（最大持仓3只）| 有新标→池内持仓卖半仓 | 无新标→全仓持有")
    log.info(f"买入条件：价格低于20日新高≥0.15% + 昨日收阳 + 涨幅≥0.07%")
    log.info(f"选股过滤规则：仅00/60开头A股 | 排除ST/*ST股 | 排除上市不满30日新股 | 排除低流动性标的")
    log.info("="*60)

def select_stock(context):
    """核心选股：修复「昨日收阳 + 涨幅≥0.07%」的筛选逻辑，确保条件严格生效"""
    if g.selected_stocks_cache is not None:
        g.buy_list = g.selected_stocks_cache
        g.stock_high_dict = g.stock_high_dict_cache
        hold_stocks = set(context.portfolio.positions.keys())
        g.need_sell_stocks = hold_stocks - set(g.buy_list)
        return
    
    g.buy_list = []
    g.stock_high_dict = {}
    hold_stocks = set(context.portfolio.positions.keys())
    filter_stats = defaultdict(int)
    filter_stats['total'] = len(g.stock_pool)
    
    log.info("="*50 + " 9:40初次选股阶段开始 " + "="*50)
    
    for stock in g.stock_pool:
        try:
            current_data = get_current_data()[stock]
            if not current_data:
                filter_stats['error'] += 1
                continue
            
            # 过滤1：仅保留00/60开头可交易标的
            if not is_stock_tradable(stock):
                filter_stats['no_permission'] += 1
                continue
            
            # 过滤2：排除已持仓标的
            if stock in hold_stocks:
                filter_stats['already_hold'] += 1
                continue
            
            # 过滤3：排除停牌标的
            if current_data.paused:
                filter_stats['paused'] += 1
                continue
            
            # 过滤4：排除ST/*ST股
            if 'ST' in current_data.name or '*ST' in current_data.name:
                filter_stats['st_stock'] += 1
                continue
            
            # 过滤5：排除上市不满30日新股
            if is_new_stock(context, stock):
                filter_stats['new_stock'] += 1
                continue
            
            # 过滤6：排除数据不足（至少需要3条数据：前日、昨日、当日）
            df = get_unified_price_data(stock, context, count=60, frequency='daily')
            if len(df) < 3:
                filter_stats['insufficient_data'] += 1
                continue

            # ========== 核心修复：正确计算「昨日收阳 + 昨日涨幅≥0.07%」 ==========
            # 昨日数据（倒数第2行）
            close_yest = df['close'].iloc[-2]  # 昨日收盘价
            open_yest = df['open'].iloc[-2]   # 昨日开盘价
            # 前日数据（倒数第3行）
            close_pre = df['close'].iloc[-3]  # 前日收盘价

            # 1. 昨日收阳：昨日收盘价 > 昨日开盘价
            is_up_bar = close_yest > open_yest
            # 2. 昨日涨幅 ≥ 0.07%：(昨日收盘价 - 前日收盘价) / 前日收盘价
            if close_pre <= 0:
                filter_stats['yest_not_good'] += 1
                continue
            rise_rate = (close_yest - close_pre) / close_pre
            is_rise_enough = rise_rate >= 0.007

            # 必须同时满足：昨日收阳 + 昨日涨幅≥0.07%
            if not (is_up_bar and is_rise_enough):
                filter_stats['yest_not_good'] += 1
                continue
            # ========== 修复结束 ==========
            
            close = df['close'].values
            vol = df['volume'].values
            ma5 = ta.MA(close, 5)
            ma20 = ta.MA(close, 20)
            
            cond1 = ma5[-1] >= ma20[-1]  
            hhv_20 = np.max(close[-20:])
            cond2 = (np.max(close[-20:]) / close[-1] <= 1.08) and vol[-1] >= 1.2 * np.mean(vol[-20:])
            roc_10 = ta.ROC(close, 10)[-1]
            macd, macdsignal, _ = ta.MACD(close)
            cond3 = roc_10 > 5 and macd[-1] > macdsignal[-1]
            
            if cond1 and cond2 and cond3:
                g.buy_list.append(stock)
                g.stock_high_dict[stock] = hhv_20
                filter_stats['pass_all'] += 1
                name = get_security_info(stock).display_name if get_security_info(stock) else ""
                log.info(f"初次选股成功：{stock}({name}) | 昨日涨幅:{rise_rate:.1%} | 昨日收阳:{is_up_bar} | 20日新高:{hhv_20:.2f}")
            else:
                filter_stats['no_meet_cond'] += 1
                
        except Exception as e:
            filter_stats['error'] += 1
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.error(f"初次选股处理{stock}({name})出错：{str(e)}")
    
    g.selected_stocks_cache = g.buy_list
    g.stock_high_dict_cache = g.stock_high_dict
    g.need_sell_stocks = hold_stocks - set(g.buy_list)
    
    log.info("="*40 + " 初次选股过滤统计 " + "="*40)
    log.info(f"账户权限过滤（非00/60开头）：{filter_stats['no_permission']}只")
    log.info(f"已持仓过滤：{filter_stats['already_hold']}只")
    log.info(f"停牌过滤：{filter_stats['paused']}只")
    log.info(f"ST过滤：{filter_stats['st_stock']}只")
    log.info(f"新股过滤（不满30日）：{filter_stats['new_stock']}只")
    log.info(f"数据不足过滤：{filter_stats['insufficient_data']}只")
    log.info(f"昨日未收阳/涨幅不足0.07%：{filter_stats.get('yest_not_good',0)}只")
    log.info(f"条件不满足过滤：{filter_stats['no_meet_cond']}只")
    log.info(f"处理错误：{filter_stats['error']}只")
    log.info(f"最终入选：{filter_stats['pass_all']}只 | 初次选股列表：{g.buy_list}")
    log.info("="*50 + " 9:40初次选股阶段结束 " + "="*50)

# ==================== 修复：清仓函数（正确统计回笼资金）====================
def sell_unselected_stocks(context):
    """09:50清仓非池股（策略1节奏），修复：正确统计实际回笼资金"""
    if len(g.need_sell_stocks) == 0:
        log.info("09:50清仓阶段：无需要清仓的股票（股票池内持仓股继续持有）")
        return
    
    log.info("="*50 + " 09:50清仓阶段开始 " + "="*50)
    sell_count = 0
    g.sold_cash = 0.0
    g.executed_sold_cash = 0.0
    
    for stock in g.need_sell_stocks:
        if stock in g.today_bought_stocks:
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.info(f"跳过清仓{stock}({name})：当日新买入，禁止卖出")
            continue
        
        if stock not in context.portfolio.positions:
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.info(f"跳过清仓{stock}({name})：已无持仓")
            continue
        
        try:
            is_limit_up, limit_info = is_stock_limit_up(context, stock)
            if is_limit_up:
                log.info(f"跳过清仓{limit_info}")
                continue
            
            pos = context.portfolio.positions[stock]
            current_price = get_current_data()[stock].last_price if is_real_trade(context) else pos.price
            sold_amount = pos.total_amount * current_price
            sold_amount_after_fee = sold_amount * (1 - 0.0013)
            
            order_result = order_target(stock, 0)
            if order_result:
                # 修复：无论实盘/回测，只要委托成功就统计资金
                if order_result.status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED, None):
                    # 模拟环境order_result.status为None，直接统计
                    executed_amount = order_result.filled_amount if hasattr(order_result, 'filled_amount') else pos.total_amount
                    executed_amount_after_fee = executed_amount * current_price * (1 - 0.0013)
                    g.executed_sold_cash += executed_amount_after_fee
                    g.sold_cash += sold_amount_after_fee
                    sell_count += 1
                    name = get_security_info(stock).display_name if get_security_info(stock) else ""
                    log.info(f"清仓成交：{stock}({name}) | 实际回笼资金：{executed_amount_after_fee:.2f}元")
            
            if stock in g.track_high:
                del g.track_high[stock]
        except Exception as e:
            # 修复：即使报错，只要有成交就统计资金
            if 'FILLED' in str(e):
                pos = context.portfolio.positions.get(stock)
                if pos:
                    current_price = get_current_data()[stock].last_price if is_real_trade(context) else pos.price
                    executed_amount_after_fee = pos.total_amount * current_price * (1 - 0.0013)
                    g.executed_sold_cash += executed_amount_after_fee
                    sell_count += 1
                    name = get_security_info(stock).display_name if get_security_info(stock) else ""
                    log.info(f"清仓成交（异常处理）：{stock}({name}) | 回笼资金：{executed_amount_after_fee:.2f}元")
            name = get_security_info(stock).display_name if get_security_info(stock) else ""
            log.error(f"09:50清仓{stock}({name})失败：{str(e)}")
    
    log.info(f"当日清仓：标记清仓{len(g.need_sell_stocks)}只 | 实际成交{sell_count}只")
    log.info(f"实际成交回笼资金：{g.executed_sold_cash:.2f}元")
    log.info("="*50 + " 清仓阶段结束 " + "="*50)

# ==================== 修复：买入函数（按剩余资金动态分配，避免资金不足）====================
def buy_after_below_high(context):
    """【持仓修改】核心修改：修复资金计算和买入数量逻辑，确保3只均分"""
    if g.selected_stocks_cache is None:
        select_stock(context)
    buy_list = g.selected_stocks_cache  # 使用二次筛选后的结果
    hold = set(context.portfolio.positions.keys())
    new_stocks = [s for s in buy_list if s not in hold]

    # 【持仓修改】核心逻辑：有新标的时，已持仓股卖半仓（完全复用策略1逻辑）
    if len(new_stocks) > 0 and len(hold) > 0:
        log.info("="*50 + " 有新标的，开始卖出已持仓股半仓 " + "="*50)
        # 只对「在二次筛选后选股池内」的已持仓股卖半仓
        hold_in_pool = [s for s in hold if s in buy_list]
        for s in hold_in_pool:
            if s in g.today_bought_stocks:
                continue
            pos = context.portfolio.positions[s]
            current_amount = pos.total_amount
            # 卖出半仓（向下取整到100股）
            sell_amount = int(current_amount / 2 / 100) * 100
            if sell_amount <= 0:
                continue
            
            # 检查是否涨停，涨停不卖
            is_limit, _ = is_stock_limit_up(context, s)
            if is_limit:
                name = get_security_info(s).display_name if get_security_info(s) else ""
                log.info(f"{s}({name}) 涨停，跳过半仓卖出")
                continue
            
            # 执行半仓卖出
            order_result = order(s, -sell_amount)
            if order_result:
                # 计算卖出回笼资金
                current_price = get_current_data()[s].last_price if is_real_trade(context) else pos.price
                sell_cash = sell_amount * current_price * (1 - 0.0013)  # 扣除手续费
                g.half_sold_cash += sell_cash
                g.executed_sold_cash += sell_cash
                
                name = get_security_info(s).display_name if get_security_info(s) else ""
                log.info(f"卖出{s}({name})半仓：原持仓{current_amount}股 → 卖出{sell_amount}股 → 剩余{current_amount-sell_amount}股")
                log.info(f"{s}({name}) 半仓卖出回笼资金：{sell_cash:.2f}元")
        
        log.info(f"半仓卖出完成，累计回笼资金：{g.half_sold_cash:.2f}元")
    elif len(new_stocks) == 0:
        log.info("无新标的，已持仓股按原有规则持有")

    # 【持仓修改】原有买入逻辑（修复：按剩余资金动态分配）
    qualified = []
    for s in new_stocks:
        try:
            d = get_current_data()[s]
            if not d or d.paused:
                continue
            if not check_liquidity(context, s):
                continue
            is_limit, _ = is_stock_limit_up(context, s)
            if is_limit:
                continue
            p = d.last_price if is_real_trade(context) else d.close
            if p <= 0:
                continue
            # 保留策略2的20日新高判断逻辑（低于0.15%）
            latest_hhv_20 = get_latest_20day_high(context, s, include_intraday=False)
            if latest_hhv_20 <= 0:
                continue
            below_high_rate = (latest_hhv_20 - p) / latest_hhv_20
            if below_high_rate < g.buy_below_high_rate:
                continue
            # 保留策略2的买入筛选，无需额外加策略1的翻红条件（策略2已筛选昨日强势）
            df5 = get_unified_price_data(s, context, 5)
            vol = df5['volume'].mean() if len(df5)>=1 else 0
            qualified.append({
                'stock':s, 'below':below_high_rate, 'vol':vol, 'p':p
            })
        except:
            continue

    # 【持仓修改】排序：适配策略1，按跌深→成交量排序（无翻红，因策略2已筛选昨日强势）
    qualified_sorted = sorted(qualified, key=lambda x: (-x['below'], -x['vol']))
    MAX_BUY = g.max_pos  # 最大持仓3只（策略1核心限制）
    final = [x['stock'] for x in qualified_sorted[:MAX_BUY]]
    # 核心修改：目标买入数量 = 最大持仓数 - 半仓后剩余持仓数
    remain_hold = len([s for s in hold if s in buy_list])  # 半仓后剩余的持仓数
    target_num = min(MAX_BUY - remain_hold, len(final))
    if target_num <= 0:
        log.info("已满仓或无合格标的")
        return

    # 修复：计算总可用资金（包含清仓+半仓卖出资金）
    total_available_cash = context.portfolio.cash + g.executed_sold_cash + g.half_sold_cash
    # 按目标数量均分资金
    per_stock_cash = total_available_cash * calculate_dynamic_position_ratio(target_num) / target_num
    log.info(f"二次筛选后符合条件:{len(qualified)}只，排序后买入前{MAX_BUY}名: {final}")
    log.info(f"半仓后剩余持仓{remain_hold}只，计划新买入{target_num}只 | 总可用资金：{total_available_cash:.2f}元 | 单只可用资金：{per_stock_cash:.2f}元")
    
    if total_available_cash < 1000:
        log.info("资金不足")
        return

    bought = 0
    used_cash = 0  # 记录已使用资金
    for s in final:
        if bought >= target_num:
            break
        try:
            item = next(x for x in qualified_sorted if x['stock']==s)
            # 修复：使用剩余可用资金计算买入数量
            remaining_cash = total_available_cash - used_cash
            per_stock_remaining = remaining_cash / (target_num - bought)
            amt = calculate_buy_amount(s, per_stock_remaining, item['p'])
            if amt <= 0:
                continue
            
            order_result = order(s, amt)
            if order_result:
                # 统计已使用资金（包含手续费）
                used_cash += amt * item['p'] / (1 - 0.0003)
                bought += 1
                g.today_bought_stocks.add(s)
                g.track_high[s] = item['p']
                name = get_security_info(s).display_name if get_security_info(s) else ""
                log.info(f"买入第{bought}名 {s}({name}) | 跌深:{item['below']*100:.1f}% | 价格:{item['p']:.2f} | 数量:{amt}股 | 占用资金:{amt*item['p']:.2f}元")
        except Exception as e:
            name = get_security_info(s).display_name if get_security_info(s) else ""
            log.error(f"买入{s}({name})失败：{str(e)}")
    log.info(f"本次买入完成，共买入:{bought}只 | 累计占用资金:{used_cash:.2f}元")

def calibrate_position(context):
    """【持仓修改】适配策略1，简化校准逻辑（和策略1一致，仅打印日志，避免冗余）"""
    hold_cnt = len(context.portfolio.positions)
    if hold_cnt == 0:
        return
    # 修复：显示实际持仓和资金情况
    total_value = context.portfolio.total_value
    cash = context.portfolio.cash
    hold_list = []
    for s in context.portfolio.positions.keys():
        name = get_security_info(s).display_name if get_security_info(s) else ""
        hold_list.append(f"{s}({name})")
    log.info(f"09:55 仓位校准 | 当前持仓：{hold_list} | 持仓数：{hold_cnt}只 | 剩余现金：{cash:.2f}元 | 总资产：{total_value:.2f}元")

def stop_loss_take_profit(context):
    """【持仓修改】适配策略1的止盈止损逻辑：池内仅止损，非池股止损+止盈"""
    now = context.current_dt.time()
    if not (datetime.time(9,30) <= now <= datetime.time(15,00)):
        return
    
    # 修复核心：先获取当天二次筛选后选股池股票，兼容缓存和未初始化的情况
    in_pool_today = set()
    if hasattr(g, 'selected_stocks_cache') and g.selected_stocks_cache is not None:
        in_pool_today = set(g.selected_stocks_cache)
    elif hasattr(g, 'buy_list') and g.buy_list is not None:
        in_pool_today = set(g.buy_list)

    for s in list(context.portfolio.positions.keys()):
        if s in g.today_bought_stocks:
            continue

        pos = context.portfolio.positions[s]
        cost = pos.avg_cost
        if cost <= 0:
            continue

        is_limit, _ = is_stock_limit_up(context, s)
        if is_limit:
            if s in g.track_high:
                current_price = get_current_data()[s].last_price if is_real_trade(context) else get_current_data()[s].close
                g.track_high[s] = max(g.track_high[s], current_price)
            continue

        p = get_current_data()[s].last_price if is_real_trade(context) else get_current_data()[s].close
        if s not in g.track_high:
            g.track_high[s] = p

        high = g.track_high[s]
        loss = (cost - p) / cost
        dd = (high - p) / high if high > 0 else 0
        name = get_security_info(s).display_name if get_security_info(s) else ""

        # 核心规则：半仓后剩余持仓仍按策略1逻辑执行（池内仅止损，非池股止损+止盈）
        if s in in_pool_today:
            if loss >= g.stop_loss_rate:
                order_target(s, 0)
                if s in g.track_high:
                    del g.track_high[s]
                log.info(f"【当日池内止损】{s}({name}) 成本:{cost:.2f} 当前价:{p:.2f} 亏损:{loss*100:.1f}%")
            continue
        else:
            if loss >= g.stop_loss_rate:
                order_target(s, 0)
                if s in g.track_high:
                    del g.track_high[s]
                log.info(f"止损 {s}({name}) 成本:{cost:.2f} 当前价:{p:.2f} 亏损:{loss*100:.1f}%")
                continue
            if dd >= g.take_profit_drawdown:
                order_target(s, 0)
                if s in g.track_high:
                    del g.track_high[s]
                log.info(f"止盈 {s}({name}) 高点:{high:.2f} 当前价:{p:.2f} 回落:{dd*100:.1f}%")

def handle_data(context, data):
    pass