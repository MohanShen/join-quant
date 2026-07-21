# Clone from JoinQuant
# postId: db14a7316ed712b3f01ef9d9b4c675d3
# backtestId: d124b8e7c7c81d3995e35d892c61790b
# title: 年化160000000倍百分之10万有未来函数的策略见过吗

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

# ==================== 通用成交量获取函数（核心修复：vol优先+volume兜底）====================
def get_realtime_volume(current_data, fallback_volume=0):
    """
    通用成交量获取函数：vol优先，volume兜底
    :param current_data: get_current_data()返回的单只股票对象
    :param fallback_volume: 最终兜底值（默认0）
    :return: 成交量（股），无有效值则返回fallback_volume
    """
    try:
        # 优先级1：模拟/实盘的vol（实时成交量）
        if hasattr(current_data, 'vol') and current_data.vol > 0:
            return current_data.vol
        # 优先级2：回测的volume（历史成交量）
        elif hasattr(current_data, 'volume') and current_data.volume > 0:
            return current_data.volume
        # 优先级3：兜底值
        else:
            return fallback_volume
    except Exception:
        return fallback_volume

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
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        
        # 1. 获取前19个交易日的日线数据（含close，用于计算历史收盘价新高）
        hist_19d = get_unified_price_data(stock, context, count=19, frequency='daily')
        if len(hist_19d) < 1:
            # 兜底：获取前20日日线数据，取收盘价新高
            hist_20d = get_unified_price_data(stock, context, count=20, frequency='daily')
            fallback_high = hist_20d['close'].max() if len(hist_20d) > 0 else 0
            log.info(f"{stock}({stock_name}) 前19日数据不足，兜底前20日收盘价新高：{fallback_high:.2f}")
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
        if today_open<= 0 or pd.isna(today_open):
            today_open = prev_19d_close_max
            log.info(f"{stock}({stock_name}) 当日daily.open和盘中价均异常，兜底使用前19日收盘价新高：{today_open:.2f}")

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
        log.info(f"{stock}({stock_name}) 20日新高计算明细：前19日收盘价新高={prev_19d_close_max:.2f} | 当日daily.open={daily_open:.2f} | 当日盘中价={intraday_price:.2f} | 当日有效开盘价（最大值）={today_open:.2f} | 当日盘中最新价={latest_intraday_price:.2f} | 最终20日新高={final_20day_high:.2f}")
        
        return final_20day_high
    except Exception as e:
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        log.warning(f"获取{stock}({stock_name})最新20日新高异常：{str(e)}，兜底前20日收盘价新高")
        hist_20d = get_unified_price_data(stock, context, count=20, frequency='daily')
        return hist_20d['close'].max() if len(hist_20d) > 0 else 0

# ==================== 核心修复：vol优先+volume兜底 流动性校验函数 ====================
def check_liquidity(context, stock):
    """
    流动性校验：vol优先+volume兜底，完美兼容回测/模拟/实盘
    1. 近5日平均成交量≥500手（所有环境通用，用日线数据的volume）
    2. 当日成交量≥100手（优先vol，降级到volume，最后用昨日日线数据）
    """
    try:
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        
        # 1. 基础校验：近5日平均成交量（用日线数据，始终用volume）
        hist_5d = get_unified_price_data(stock, context, count=5, frequency='daily')
        if len(hist_5d) < 5:
            log.info(f"{stock}({stock_name}) 近5日数据不足，跳过流动性校验")
            return True
        
        avg_vol_5d = hist_5d['volume'].mean() / 100  # 转换为手
        if avg_vol_5d < 500:
            log.info(f"{stock}({stock_name}) 流动性不足：近5日平均成交量{avg_vol_5d:.0f}手 < 500手")
            return False
        
        # 2. 当日成交量校验（核心：vol优先 + volume兜底）
        current_data = get_current_data()[stock]
        if current_data:
            # 第一步：调用通用函数获取成交量（vol/volume自动兼容）
            realtime_vol = get_realtime_volume(current_data)
            
            if realtime_vol > 0:
                today_vol = realtime_vol / 100  # 转换为手
                if today_vol < 100:
                    log.info(f"{stock}({stock_name}) 当日流动性不足：实时成交量{today_vol:.0f}手 < 100手（来源：{'vol' if hasattr(current_data, 'vol') and current_data.vol>0 else 'volume'}）")
                    return False
            else:
                # 第二步：实时成交量无效，用昨日日线volume兜底
                hist_2d = get_unified_price_data(stock, context, count=2, frequency='daily')
                if len(hist_2d) >= 2:
                    yesterday_vol = hist_2d['volume'].iloc[-2] / 100  # 昨日成交量（手）
                    if yesterday_vol < 100:
                        log.info(f"{stock}({stock_name}) 当日流动性不足：昨日成交量{yesterday_vol:.0f}手 < 100手（兜底校验）")
                        return False
                # 无任何成交量数据，跳过当日校验
                log.info(f"{stock}({stock_name}) 无实时成交量数据，跳过当日成交量校验")
        
        return True
    except Exception as e:
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        log.warning(f"{stock}({stock_name}) 流动性校验异常：{str(e)}，默认通过校验")
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
            log.warning(f"{stock} 无法获取上市信息，暂按非新股处理")
            return False
        
        list_date = stock_info.start_date.date()
        current_date = context.current_dt.date()
        
        trade_days = get_trade_days(start_date=list_date, end_date=current_date)
        trade_days_count = len(trade_days)
        stock_name = stock_info.display_name
        
        if trade_days_count < 30:
            log.info(f"{stock}({stock_name}) 为新股：上市{trade_days_count}个交易日（不满30个），过滤")
            return True
        return False
    except Exception as e:
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        log.warning(f"{stock}({stock_name}) 新股判断异常：{str(e)}，暂按非新股处理")
        return False

# ==================== 涨停判断函数 ====================
def is_stock_limit_up(context, stock):
    """统一回测/实盘的涨停判断逻辑（返回：是否涨停 + 详细信息，方便日志排查）"""
    try:
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        
        current_data = get_current_data()[stock]
        if not current_data:
            return False, f"{stock}({stock_name}) 获取current_data失败（返回None）"
        
        current_price = current_data.last_price if is_real_trade(context) else current_data.close
        if current_price <= 0:
            return False, f"{stock}({stock_name}) 当前价格异常（current_price={current_price}）"
        
        close_data = get_unified_price_data(stock, context, count=2, frequency='daily')
        if len(close_data) < 2:
            return False, f"{stock}({stock_name}) 获取昨日收盘价失败（数据不足2条）"
        
        close_yesterday = close_data['close'].iloc[-2]
        if close_yesterday == 0:
            return False, f"{stock}({stock_name}) 昨日收盘价异常（close_yesterday={close_yesterday}）"
        
        # 计算涨停价
        if 'ST' in current_data.name or '*ST' in current_data.name:
            limit_up_price = round(close_yesterday * 1.05, 2)
            limit_type = "ST股（5%）"
        else:
            limit_up_price = round(close_yesterday * 1.1, 2)
            limit_type = "普通股（10%）"
        
        is_limit_up = abs(current_price - limit_up_price) <= 0.01
        info = f"{limit_type} | 昨日收盘价={close_yesterday:.2f} | 涨停价={limit_up_price:.2f} | 当前价={current_price:.2f}"
        return is_limit_up, info
    except Exception as e:
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        return False, f"{stock}({stock_name}) 涨停判断函数执行异常：{str(e)}"

# ==================== 动态仓位分配函数（核心修改：全量均分逻辑）====================
def calculate_equal_position_ratio(target_stock_count):
    """
    全量均分仓位比例计算：
    - 若有N只符合条件标的，每只仓位 = 1/N（扣除手续费预留）
    - 兜底：至少保留0.5%现金作为预留
    """
    if target_stock_count <= 0:
        return 0.0
    
    cash_reserve_ratio = 0.005
    position_ratio = (1 - cash_reserve_ratio) / target_stock_count
    
    return max(position_ratio, 0.001)

def calculate_target_position_value(context, target_stock_count):
    """计算单只股票的目标持仓市值（全量均分逻辑）"""
    total_portfolio_value = context.portfolio.total_value
    position_ratio = calculate_equal_position_ratio(target_stock_count)
    target_position_value = total_portfolio_value * position_ratio
    
    return target_position_value, position_ratio

def calculate_buy_amount(stock, target_value, current_price):
    """根据目标市值计算可买入股数（100股整数倍，扣除手续费）"""
    if current_price <= 0 or target_value <= 0:
        return 0
    
    usable_cash = target_value * (1 - 0.0003)
    buy_amount = int(usable_cash / current_price / 100) * 100
    
    if buy_amount < 100 and usable_cash >= current_price * 100:
        buy_amount = 100
    
    return buy_amount

# ==================== 主策略 ====================
def initialize(context):
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(FixedSlippage(0.0002))
    set_benchmark('000905.XSHG')
    
    g.stock_pool = get_all_securities(['stock']).index.tolist()
    g.stop_loss_rate = 0.04
    g.take_profit_drawdown = 0.02
    g.pool_stock_take_profit_drawdown = 0.02
    g.buy_below_high_rate = 0.0015
    g.track_high = {}
    g.watch_list = []
    g.selected_stocks_cache = None
    g.stock_high_dict_cache = {}
    g.today_bought_stocks = set()
    g.need_sell_stocks = set()
    g.sold_cash = 0.0
    g.executed_sold_cash = 0.0
    
    run_daily(before_trading_start, time='09:00')  
    run_daily(select_stock, time='09:30')          
    run_daily(sell_unselected_stocks, time='09:33')
    run_daily(buy_after_below_high, time='09:34')
    run_daily(calibrate_position, time='09:35')
    run_daily(stop_loss_take_profit, time='every_bar')

def before_trading_start(context):
    g.today_bought_stocks = set()
    g.need_sell_stocks = set()
    g.selected_stocks_cache = None
    g.stock_high_dict_cache = {}
    g.watch_list = []
    g.sold_cash = 0.0
    g.executed_sold_cash = 0.0
    
    g.stock_pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()
    
    log.info("="*60)
    log.info(f"交易日: {context.current_dt.date()} | 运行模式: {'实盘/模拟' if is_real_trade(context) else '回测'}")
    log.info(f"全部A股数量: {len(g.stock_pool)} | 当前持仓: {len(context.portfolio.positions)}只")
    # 补充持仓股票名称显示
    if context.portfolio.positions:
        hold_stocks_info = [f"{code}({get_security_info(code).display_name if get_security_info(code) else '未知名称'})" 
                           for code in context.portfolio.positions.keys()]
        log.info(f"当前持仓明细: {hold_stocks_info}")
    log.info(f"仓位配置：全量均分持仓（无最大持仓限制）")
    log.info(f"买入条件：价格低于20日新高≥4.5% + 昨日收阳 + 涨幅≥6.2%")
    log.info(f"选股过滤规则：仅00/60开头A股 | 排除ST/*ST股 | 排除上市不满30日新股 | 排除低流动性标的")
    log.info("="*60)

def select_stock(context):
    """核心选股：昨日收阳 + 涨幅≥6.2%，替换原来的首次涨停"""
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
    
    log.info("="*50 + " 选股阶段开始 " + "="*50)
    
    for stock in g.stock_pool:
        try:
            current_data = get_current_data()[stock]
            if not current_data:
                filter_stats['error'] += 1
                continue
            
            # 获取股票名称
            stock_name = current_data.name if hasattr(current_data, 'name') else (get_security_info(stock).display_name if get_security_info(stock) else "未知名称")
            
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
            if 'ST' in stock_name or '*ST' in stock_name:
                filter_stats['st_stock'] += 1
                continue
            
            # 过滤5：排除上市不满30日新股
            if is_new_stock(context, stock):
                filter_stats['new_stock'] += 1
                continue
            
            # 过滤6：排除数据不足
            df = get_unified_price_data(stock, context, count=60, frequency='daily')
            if len(df) < 20:
                filter_stats['insufficient_data'] += 1
                continue

            # ==================== 新条件：昨日收阳 + 涨幅≥6.2% ====================
            close_yest = df['close'].iloc[-1]
            open_yest = df['open'].iloc[-1]
            close_pre = df['close'].iloc[-2]

            # 收阳：收盘价 > 开盘价
            is_up_bar = close_yest > open_yest
            # 涨幅 ≥ 6.2%
            rise_rate = (close_yest - close_pre) / close_pre
            is_rise_enough = rise_rate >= 0.062

            if not (is_up_bar and is_rise_enough):
                filter_stats['yest_not_good'] += 1
                continue
            
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
                log.info(f"选股成功：{stock}({stock_name}) | 昨日涨幅:{rise_rate:.1%} | 20日新高:{hhv_20:.2f}")
            else:
                filter_stats['no_meet_cond'] += 1
                
        except Exception as e:
            # 获取股票名称
            stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
            log.error(f"选股处理{stock}({stock_name})出错：{str(e)}")
            filter_stats['error'] += 1
    
    g.selected_stocks_cache = g.buy_list
    g.stock_high_dict_cache = g.stock_high_dict
    g.need_sell_stocks = hold_stocks - set(g.buy_list)
    
    log.info("="*40 + " 选股过滤统计 " + "="*40)
    log.info(f"账户权限过滤（非00/60开头）：{filter_stats['no_permission']}只")
    log.info(f"已持仓过滤：{filter_stats['already_hold']}只")
    log.info(f"停牌过滤：{filter_stats['paused']}只")
    log.info(f"ST过滤：{filter_stats['st_stock']}只")
    log.info(f"新股过滤（不满30日）：{filter_stats['new_stock']}只")
    log.info(f"数据不足过滤：{filter_stats['insufficient_data']}只")
    log.info(f"昨日未收阳/涨幅不足6.2%：{filter_stats.get('yest_not_good',0)}只")
    log.info(f"条件不满足过滤：{filter_stats['no_meet_cond']}只")
    log.info(f"处理错误：{filter_stats['error']}只")
    log.info(f"最终入选：{filter_stats['pass_all']}只")
    # 补充入选股票名称显示
    if g.buy_list:
        buy_list_info = [f"{code}({get_security_info(code).display_name if get_security_info(code) else '未知名称'})" 
                         for code in g.buy_list]
        log.info(f"选股列表明细: {buy_list_info}")
    else:
        log.info(f"选股列表明细: 空")
    log.info("="*50 + " 选股阶段结束 " + "="*50)

def sell_unselected_stocks(context):
    """09:59清仓，记录实际成交的回笼资金（核心优化：避免清仓资金虚高）"""
    if len(g.need_sell_stocks) == 0:
        log.info("09:59清仓阶段：无需要清仓的股票（股票池内持仓股继续持有）")
        return
    
    log.info("="*50 + " 09:59清仓阶段开始 " + "="*50)
    # 补充待清仓股票名称显示
    if g.need_sell_stocks:
        sell_stocks_info = [f"{code}({get_security_info(code).display_name if get_security_info(code) else '未知名称'})" 
                           for code in g.need_sell_stocks]
        log.info(f"待清仓股票列表: {sell_stocks_info}")
    
    sell_count = 0
    g.sold_cash = 0.0
    g.executed_sold_cash = 0.0
    
    for stock in g.need_sell_stocks:
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        
        if stock in g.today_bought_stocks:
            log.info(f"跳过清仓{stock}({stock_name})：当日新买入，禁止卖出")
            continue
        
        if stock not in context.portfolio.positions:
            log.info(f"跳过清仓{stock}({stock_name})：已无持仓")
            continue
        
        try:
            is_limit_up, limit_info = is_stock_limit_up(context, stock)
            if is_limit_up:
                log.info(f"跳过清仓{stock}({stock_name})：当前处于涨停状态 | {limit_info}")
                continue
            
            pos = context.portfolio.positions[stock]
            current_price = get_current_data()[stock].last_price if is_real_trade(context) else pos.price
            sold_amount = pos.total_amount * current_price
            sold_amount_after_fee = sold_amount * (1 - 0.0013)
            
            order_result = order_target(stock, 0)
            if order_result:
                if is_real_trade(context):
                    if order_result.status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
                        executed_amount = order_result.filled_amount * current_price
                        executed_amount_after_fee = executed_amount * (1 - 0.0013)
                        g.executed_sold_cash += executed_amount_after_fee
                        g.sold_cash += sold_amount_after_fee
                        sell_count += 1
                        log.info(f"清仓成交：{stock}({stock_name}) | 实际回笼资金：{executed_amount_after_fee:.2f}元")
                else:
                    g.executed_sold_cash += sold_amount_after_fee
                    g.sold_cash += sold_amount_after_fee
                    sell_count += 1
                    log.info(f"清仓成功：{stock}({stock_name}) | 回笼资金：{sold_amount_after_fee:.2f}元")
            
            if stock in g.track_high:
                del g.track_high[stock]
        except Exception as e:
            log.error(f"09:59清仓{stock}({stock_name})失败：{str(e)}")
    
    log.info(f"当日清仓：标记清仓{len(g.need_sell_stocks)}只 | 实际成交{sell_count}只")
    log.info(f"实际成交回笼资金：{g.executed_sold_cash:.2f}元")
    log.info("="*50 + " 清仓阶段结束 " + "="*50)

def buy_after_below_high(context):
    """10:00买入：全量均分"""
    if g.selected_stocks_cache is None:
        select_stock(context)
    
    buy_list = g.selected_stocks_cache
    stock_high_dict = g.stock_high_dict_cache
    
    if len(buy_list) == 0:
        log.info("10:00买入阶段：buy_list为空，无标的可买")
        return
    
    current_positions = list(context.portfolio.positions.keys())
    new_stocks = [s for s in buy_list if s not in current_positions]
    target_buy_count = len(new_stocks)
    
    if target_buy_count <= 0:
        log.info("买入阶段终止：无新标的可买")
        return
    
    # 补充待买入股票名称显示
    if new_stocks:
        new_stocks_info = [f"{code}({get_security_info(code).display_name if get_security_info(code) else '未知名称'})" 
                           for code in new_stocks]
        log.info(f"待买入新标的列表: {new_stocks_info}")
    
    target_position_value, dynamic_ratio = calculate_target_position_value(context, target_buy_count)
    original_cash = context.portfolio.cash
    total_buy_cash = original_cash + g.executed_sold_cash
    total_usable_cash = total_buy_cash * (1 - 0.0003)
    
    log.info("="*50 + f" 10:00买入阶段开始（全量均分：{target_buy_count}只） " + "="*50)
    log.info(f"账户总净资产：{context.portfolio.total_value:.2f}元")
    log.info(f"单只目标市值：{target_position_value:.2f}元（{dynamic_ratio*100:.2f}%）")
    log.info(f"总可用买入资金：{total_usable_cash:.2f}元")
    
    if total_usable_cash < 1000:
        log.info("买入阶段终止：可用资金不足1000元")
        return
    
    bought_count = 0
    for stock in new_stocks:
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        
        try:
            if not check_liquidity(context, stock):
                continue
            
            is_limit_up, limit_info = is_stock_limit_up(context, stock)
            if is_limit_up:
                log.info(f"跳过{stock}({stock_name})：涨停不追 | {limit_info}")
                continue
            
            current_data = get_current_data()[stock]
            if not current_data or current_data.paused:
                log.info(f"跳过{stock}({stock_name})：无实时数据或停牌")
                continue
            
            current_price = current_data.last_price if is_real_trade(context) else current_data.close
            if current_price <= 0:
                log.info(f"跳过{stock}({stock_name})：当前价格异常（{current_price}）")
                continue
            
            latest_hhv_20 = get_latest_20day_high(context, stock, include_intraday=False)
            if latest_hhv_20 <= 0:
                log.info(f"跳过{stock}({stock_name})：20日新高计算异常（{latest_hhv_20}）")
                continue
            
            below_high_rate = (latest_hhv_20 - current_price) / latest_hhv_20
            
            if below_high_rate < g.buy_below_high_rate:
                log.info(f"跳过{stock}({stock_name})：低于新高比例不足（{below_high_rate*100:.1f}% < {g.buy_below_high_rate*100:.1f}%）")
                continue
            
            buy_amount = calculate_buy_amount(stock, target_position_value, current_price)
            if buy_amount <= 0:
                log.info(f"跳过{stock}({stock_name})：可买入数量为0（目标市值{target_position_value:.2f}，当前价格{current_price:.2f}）")
                continue
            
            order_result = order(stock, buy_amount)
            if order_result and order_result.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED):
                bought_count += 1
                g.today_bought_stocks.add(stock)
                g.track_high[stock] = current_price
                log.info(f"买入成功：{stock}({stock_name}) | 价格{current_price:.2f} | 数量{buy_amount}股 | 低于新高{below_high_rate*100:.1f}%")
            
        except Exception as e:
            log.error(f"买入{stock}({stock_name})出错：{str(e)}")
    
    log.info(f"目标买入：{target_buy_count}只 | 实际买入：{bought_count}只")
    log.info("="*50 + " 买入阶段结束 " + "="*50)

def calibrate_position(context):
    """10:10仓位校准"""
    current_hold_count = len(context.portfolio.positions)
    if current_hold_count <= 0 or g.selected_stocks_cache is None:
        return
    
    target_position_value, dynamic_ratio = calculate_target_position_value(context, current_hold_count)
    calibrate_count = 0
    selected_stocks = g.selected_stocks_cache
    
    log.info("="*50 + " 10:10仓位校准阶段开始 " + "="*50)
    
    for stock in list(context.portfolio.positions.keys()):
        # 获取股票名���
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        
        try:
            if stock in g.today_bought_stocks or stock not in selected_stocks:
                continue
            
            is_limit_up, _ = is_stock_limit_up(context, stock)
            if is_limit_up:
                log.info(f"跳过校准{stock}({stock_name})：当前涨停")
                continue
            
            current_data = get_current_data()[stock]
            current_price = current_data.last_price if is_real_trade(context) else current_data.close
            pos = context.portfolio.positions[stock]
            current_val = pos.total_amount * current_price
            
            diff_rate = abs(current_val - target_position_value) / target_position_value
            if diff_rate < 0.05:
                continue
            
            if current_val < target_position_value:
                need = target_position_value - current_val
                buy_amt = calculate_buy_amount(stock, need, current_price)
                if buy_amt <= 0:
                    continue
                if not check_liquidity(context, stock):
                    continue
                res = order(stock, buy_amt)
                if res:
                    calibrate_count += 1
                    log.info(f"加仓校准：{stock}({stock_name}) | 当前市值{current_val:.2f} | 目标市值{target_position_value:.2f} | 加仓{buy_amt}股")
            else:
                need = current_val - target_position_value
                sell_amt = calculate_buy_amount(stock, need, current_price)
                if sell_amt <= 0:
                    continue
                res = order(stock, -sell_amt)
                if res:
                    calibrate_count += 1
                    log.info(f"减仓校准：{stock}({stock_name}) | 当前市值{current_val:.2f} | 目标市值{target_position_value:.2f} | 减仓{sell_amt}股")
        except Exception as e:
            log.error(f"校准{stock}({stock_name})出错：{str(e)}")
            continue
    
    log.info(f"仓位校准完成：校准{calibrate_count}只")
    log.info("="*50 + " 仓位校准阶段结束 " + "="*50)

def stop_loss_take_profit(context):
    """止损止盈"""
    current_time = context.current_dt.time()
    if not (datetime.time(9,30) <= current_time <= datetime.time(15,00)):
        return
    
    sl_count = 0
    tp_count = 0
    pool_tp_count = 0
    limit_up_hold = 0
    
    selected = g.selected_stocks_cache or []
    
    for stock in list(context.portfolio.positions.keys()):
        # 获取股票名称
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知名称"
        
        try:
            if stock in g.today_bought_stocks:
                continue
            
            pos = context.portfolio.positions[stock]
            cost = pos.avg_cost
            if cost <= 0:
                continue
            
            is_limit_up, limit_info = is_stock_limit_up(context, stock)
            if is_limit_up:
                if stock in selected:
                    limit_up_hold += 1
                    log.info(f"持有涨停：{stock}({stock_name}) | {limit_info}")
                continue
            
            current = get_current_data()[stock].last_price if is_real_trade(context) else get_current_data()[stock].close
            if current <= 0:
                continue
            
            if stock in g.track_high:
                g.track_high[stock] = max(g.track_high[stock], current)
            else:
                g.track_high[stock] = current
            
            high = g.track_high[stock]
            loss = (cost - current) / cost
            dd = (high - current) / high if high > 0 else 0
            
            if loss >= g.stop_loss_rate:
                order_target(stock, 0)
                sl_count += 1
                log.info(f"止损卖出：{stock}({stock_name}) | 成本{cost:.2f} | 当前{current:.2f} | 亏损{loss*100:.1f}%")
                if stock in g.track_high:
                    del g.track_high[stock]
                continue
            
            if stock in selected:
                if dd >= g.pool_stock_take_profit_drawdown:
                    order_target(stock, 0)
                    pool_tp_count += 1
                    log.info(f"持仓池止盈卖出：{stock}({stock_name}) | 高点{high:.2f} | 当前{current:.2f} | 回撤{dd*100:.1f}%")
                    if stock in g.track_high:
                        del g.track_high[stock]
            else:
                if dd >= g.take_profit_drawdown:
                    order_target(stock, 0)
                    tp_count += 1
                    log.info(f"止盈卖出：{stock}({stock_name}) | 高点{high:.2f} | 当前{current:.2f} | 回撤{dd*100:.1f}%")
                    if stock in g.track_high:
                        del g.track_high[stock]
        except Exception as e:
            log.error(f"止损止盈处理{stock}({stock_name})出错：{str(e)}")
            continue
    
    if sl_count + tp_count + pool_tp_count > 0:
        log.info(f"止损止盈统计：止损{sl_count}只 | 止盈{tp_count+pool_tp_count}只 | 涨停持有{limit_up_hold}只")

def handle_data(context, data):
    pass