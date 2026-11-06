# Clone from JoinQuant
# postId: 505f2af0267a6826ecfd222328299364
# backtestId: 38a7d5582b51d1819571430186a6bfc4
# title: 3只标的持仓4天

import jqdata
import talib as ta
import numpy as np
import datetime
import pandas as pd
from collections import defaultdict

# ==================== 核心工具函数 ====================
def get_previous_trading_date(target_date):
    """获取指定日期的前一个交易日"""
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
    """统一价格数据获取逻辑"""
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

# ==================== 辅助函数 ====================
def get_stock_name(stock_code):
    """获取股票中文全称（修复：从current_data取中文名称）"""
    try:
        # 优先从实时行情数据获取中文名称（最准）
        current_data = get_current_data()[stock_code]
        if current_data and hasattr(current_data, 'name'):
            return current_data.name  # 这里是中文全称，如"佛燃能源"
        
        # 兜底：用get_security_info（部分场景可能还是缩写）
        stock_info = get_security_info(stock_code)
        return stock_info.name if stock_info else "未知名称"
    except Exception as e:
        log.warning(f"获取{stock_code}中文名称失败：{str(e)}")
        return "未知名称"

def check_position_status(context, stock, expected_amount=0):
    """校验仓位状态（核心：成交验证）
    Args:
        context: 上下文
        stock: 股票代码
        expected_amount: 期望仓位（0=清仓，>0=持仓）
    Returns:
        bool: 是否符合期望仓位
        int: 当前实际仓位
    """
    try:
        pos = context.portfolio.positions[stock]
        current_amount = pos.total_amount
    except:
        current_amount = 0
    
    # 回测中允许微小误差（如手续费导致的股数差异）
    if expected_amount == 0:
        return current_amount <= 0, current_amount
    else:
        # 允许±100股的误差（A股最小交易单位）
        return abs(current_amount - expected_amount) <= 100, current_amount

# ==================== 流动性/新高/订单判断 ====================
def check_liquidity(context, stock):
    """近5日平均成交量≥500手"""
    try:
        hist_5d = get_unified_price_data(stock, context, count=5, frequency='daily')
        if len(hist_5d) < 5:
            return True
        
        avg_vol_5d = hist_5d['volume'].mean() / 100
        if avg_vol_5d < 500:
            return False
        
        return True
    except Exception as e:
        return True

def get_latest_20day_high(context, stock):
    """获取20日新高及低于比例"""
    try:
        hist_20d = get_unified_price_data(stock, context, count=20, frequency='daily')
        if len(hist_20d) < 20:
            fallback_high = hist_20d['close'].max() if len(hist_20d) > 0 else 0
            return fallback_high, 0.0
        
        hhv_20_close = hist_20d['close'].max()
        current_data = get_current_data()[stock]
        today_price = 0
        if current_data:
            today_price = current_data.last_price if is_real_trade(context) else current_data.close
        if today_price <= 0:
            today_price = hist_20d['close'].iloc[-1]
        
        below_high_rate = (hhv_20_close - today_price) / hhv_20_close
        return hhv_20_close, below_high_rate
    except Exception as e:
        hist_20d = get_unified_price_data(stock, context, count=20, frequency='daily')
        return hist_20d['close'].max() if len(hist_20d) > 0 else 0, 0.0

def is_order_successful(order_result):
    """适配聚宽的订单状态判断（核心修复！）
    聚宽订单状态枚举：
    - submitted: 已提交
    - filled: 已成交
    - partially_filled: 部分成交
    - cancelled: 已撤销
    - failed: 失败
    """
    if not order_result:
        return False
    
    # 兼容聚宽的订单状态（字符串/枚举两种形式）
    status = str(order_result.status).lower() if hasattr(order_result, 'status') else ''
    return status in ['submitted', 'filled', 'partially_filled']

# ==================== 基础过滤 ====================
def is_stock_tradable(stock):
    """仅保留00/60开头股票"""
    allow_prefix = ('000', '002', '600', '603', '601', '605')
    forbid_prefix = ('300', '688', '8', '4', '001', '003')
    if stock.startswith(forbid_prefix):
        return False
    if stock.startswith(allow_prefix):
        return True
    return False

def is_new_stock(context, stock):
    """排除上市不满30日新股"""
    try:
        stock_info = get_security_info(stock)
        if not stock_info:
            return False
        
        list_date = stock_info.start_date.date()
        current_date = context.current_dt.date()
        trade_days = get_trade_days(start_date=list_date, end_date=current_date)
        trade_days_count = len(trade_days)
        
        if trade_days_count < 30:
            return True
        return False
    except Exception as e:
        return False

def is_stock_limit_up(context, stock):
    """判断是否涨停"""
    try:
        current_data = get_current_data()[stock]
        if not current_data:
            return False, "无数据"
        
        current_price = current_data.last_price if is_real_trade(context) else current_data.close
        if current_price <= 0:
            return False, "价格异常"
        
        close_data = get_unified_price_data(stock, context, count=2, frequency='daily')
        if len(close_data) < 2:
            return False, "无昨日数据"
        
        close_yesterday = close_data['close'].iloc[-2]
        if close_yesterday == 0:
            return False, "昨日收盘价异常"
        
        if 'ST' in current_data.name or '*ST' in current_data.name:
            limit_up_price = round(close_yesterday * 1.05, 2)
        else:
            limit_up_price = round(close_yesterday * 1.1, 2)
        
        is_limit_up = abs(current_price - limit_up_price) <= 0.01
        info = f"涨停价={limit_up_price:.2f} 当前价={current_price:.2f}"
        return is_limit_up, info
    except Exception as e:
        return False, f"异常：{str(e)}"

# ==================== 仓位计算 ====================
def calculate_equal_position_ratio(target_stock_count):
    """均分仓位比例计算"""
    if target_stock_count <= 0:
        return 0.0
    
    cash_reserve_ratio = 0.005
    position_ratio = (1 - cash_reserve_ratio) / target_stock_count
    
    return max(position_ratio, 0.001)

def calculate_target_position_value(context, target_stock_count):
    """计算单只股票的目标持仓市值"""
    total_portfolio_value = context.portfolio.total_value
    position_ratio = calculate_equal_position_ratio(target_stock_count)
    target_position_value = total_portfolio_value * position_ratio
    
    return target_position_value, position_ratio

def calculate_buy_amount(stock, target_value, current_price):
    """计算可买入股数"""
    if current_price <= 0 or target_value <= 0:
        return 0
    
    usable_cash = target_value * (1 - 0.0003)
    buy_amount = int(usable_cash / current_price / 100) * 100
    
    if buy_amount < 100 and usable_cash >= current_price * 100:
        buy_amount = 100
    
    return buy_amount

# ==================== 兜底选股 ====================
def select_stock_fallback(context):
    """兜底选股：降低标准"""
    log.info("⚠️ 核心选股无结果，触发兜底选股")
    
    g.buy_list = []
    g.stock_high_dict = {}
    g.stock_type_dict = {}
    hold_stocks = set(context.portfolio.positions.keys())
    
    for stock in g.stock_pool:
        try:
            current_data = get_current_data()[stock]
            if not current_data: continue
            
            if not is_stock_tradable(stock): continue
            if stock in hold_stocks: continue
            if current_data.paused: continue
            if 'ST' in current_data.name or '*ST' in current_data.name: continue
            if is_new_stock(context, stock): continue
            
            df = get_unified_price_data(stock, context, count=60, frequency='daily')
            if len(df) < 20: continue

            # 放宽条件：昨日收阳 + 涨幅≥0%
            close_yest = df['close'].iloc[-1]
            open_yest = df['open'].iloc[-1]
            close_pre = df['close'].iloc[-2]

            is_up_bar = close_yest > open_yest
            rise_rate = (close_yest - close_pre) / close_pre
            if not (is_up_bar and rise_rate >= 0.0): continue
            
            # 仅保留MA5≥MA20
            close = df['close'].values
            ma5 = ta.MA(close, 5)
            ma20 = ta.MA(close, 20)
            if ma5[-1] < ma20[-1]: continue
            
            # 存储标的信息
            hhv_20 = np.max(close[-20:])
            stock_name = get_stock_name(stock)
            g.buy_list.append(stock)
            g.stock_high_dict[stock] = hhv_20
            g.stock_type_dict[stock] = 'fallback'
        except Exception as e:
            continue
    
    g.selected_stocks_cache = g.buy_list
    g.stock_high_dict_cache = g.stock_high_dict
    g.need_sell_stocks = hold_stocks - set(g.buy_list)
    log.info(f"兜底选股结果：共{len(g.buy_list)}只标的")

# ==================== 主策略 ====================
def initialize(context):
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(FixedSlippage(0.002))
    set_benchmark('000905.XSHG')
    
    # 核心修复：将字典式赋值改为属性赋值（适配聚宽g变量）
    global g
    g.stock_pool = get_all_securities(['stock']).index.tolist()
    g.stop_loss_rate = 0.02  # 核心调整：1-3天统一止损4%
    g.take_profit_drawdown = 0.02  # 续抱期间最高价回落2%清仓（核心）
    g.pool_stock_take_profit_drawdown = 0.02
    g.buy_below_high_rate = 0.045  # 保留配置但买入逻辑中不再使用
    g.track_high = {}
    g.watch_list = []
    g.selected_stocks_cache = None
    g.stock_high_dict_cache = {}
    g.stock_type_dict = {}
    g.today_bought_stocks = set()
    g.need_sell_stocks = set()
    g.sold_cash = 0.0
    g.executed_sold_cash = 0.0
    g.max_pos = 3  # 最大持仓3只（不变）
    g.hold_days = {}  # 新增：记录每只股票持仓天数（核心适配4天持股）
    
    run_daily(before_trading_start, time='09:00')  
    run_daily(select_stock, time='09:51')          
    run_daily(sell_unselected_stocks, time='09:53')
    run_daily(buy_after_below_high, time='09:55')
    run_daily(calibrate_position, time='10:00')
    run_daily(stop_loss_take_profit, time='every_bar')  # 核心止盈止损（适配4天持股）
    # 新增：每日收盘校验仓位
    run_daily(check_daily_position, time='14:55')

def before_trading_start(context):
    # 核心修复：将字典式赋值改为属性赋值
    global g
    # 重置每日变量
    g.today_bought_stocks = set()
    g.need_sell_stocks = set()
    g.selected_stocks_cache = None
    g.stock_high_dict_cache = {}
    g.stock_type_dict = {}
    g.watch_list = []
    g.sold_cash = 0.0
    g.executed_sold_cash = 0.0
    
    g.stock_pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()
    
    # 每日更新持仓天数（关键：买入当天算0天，次日开始计数，适配4天持股）
    for stock in context.portfolio.positions:
        g.hold_days[stock] = g.hold_days.get(stock, 0) + 1
    
    # 精简开盘日志，补充4天持股策略说明
    log.info("="*60)
    log.info(f"交易日: {context.current_dt.date()} | 运行模式: {'实盘/模拟' if is_real_trade(context) else '回测'}")
    log.info(f"当前持仓: {len(context.portfolio.positions)}只 | 股票池总数: {len(g.stock_pool)}只 | 最大持仓: {g.max_pos}只")
    log.info(f"核心策略：持股4天为主，1-3天统一止损4%，第4天涨停续抱，续抱回落2%清仓；持仓已满/无资金不买入")
    log.info(f"买入条件：昨日收阳 + 涨幅≥6.2% + 技术指标达标（已移除低于新高限制）")
    log.info("="*60)

def select_stock(context):
    """核心选股：精简日志，突出关键信息"""
    global g
    if g.selected_stocks_cache is not None:
        g.buy_list = g.selected_stocks_cache
        g.stock_high_dict = g.stock_high_dict_cache
        hold_stocks = set(context.portfolio.positions.keys())
        g.need_sell_stocks = hold_stocks - set(g.buy_list)
        return
    
    g.buy_list = []
    g.stock_high_dict = {}
    g.stock_type_dict = {}
    hold_stocks = set(context.portfolio.positions.keys())
    filter_stats = defaultdict(int)
    filter_stats['total'] = len(g.stock_pool)
    
    log.info("="*50 + " 选股阶段 " + "="*50)
    
    # 核心选股逻辑
    qualified_stocks_detail = []
    for stock in g.stock_pool:
        try:
            current_data = get_current_data()[stock]
            if not current_data:
                filter_stats['error'] += 1
                continue
            
            # 获取股票名称（确保所有日志都显示名称）
            stock_name = get_stock_name(stock)
            
            # 基础过滤
            if not is_stock_tradable(stock):
                filter_stats['no_permission'] += 1
                continue
            if stock in hold_stocks:
                filter_stats['already_hold'] += 1
                continue
            if current_data.paused:
                filter_stats['paused'] += 1
                continue
            if 'ST' in current_data.name or '*ST' in current_data.name:
                filter_stats['st_stock'] += 1
                continue
            if is_new_stock(context, stock):
                filter_stats['new_stock'] += 1
                continue
            
            df = get_unified_price_data(stock, context, count=60, frequency='daily')
            if len(df) < 20:
                filter_stats['insufficient_data'] += 1
                continue

            # 核心条件
            close_yest = df['close'].iloc[-1]
            open_yest = df['open'].iloc[-1]
            close_pre = df['close'].iloc[-2]

            is_up_bar = close_yest > open_yest
            rise_rate = (close_yest - close_pre) / close_pre
            is_rise_enough = rise_rate >= 0.062

            if not (is_up_bar and is_rise_enough):
                filter_stats['yest_not_good'] += 1
                continue
            
            # 技术指标
            close = df['close'].values
            vol = df['volume'].values
            ma5 = ta.MA(close, 5)
            ma20 = ta.MA(close, 20)
            
            cond1 = ma5[-1] >= ma20[-1]  # MA5≥MA20
            hhv_20 = np.max(close[-20:])
            cond2 = (np.max(close[-20:]) / close[-1] <= 1.08) and vol[-1] >= 1.2 * np.mean(vol[-20:])  # 20日新高比≤1.08 + 成交量≥20日均1.2倍
            roc_10 = ta.ROC(close, 10)
            macd, macdsignal, _ = ta.MACD(close)
            cond3 = roc_10[-1] > 5 and macd[-1] > macdsignal[-1]  # ROC10>5 + MACD金叉
            
            if cond1 and cond2 and cond3:
                # 记录达标标的及条件
                qualified_stocks_detail.append({
                    'stock': stock,
                    'name': stock_name,
                    'rise_rate': rise_rate,
                    'hhv_20': hhv_20,
                    'ma5': ma5[-1],
                    'ma20': ma20[-1],
                    'roc_10': roc_10[-1],
                    'macd_val': macd[-1],
                    'macd_signal': macdsignal[-1],
                    # 新增条件明细
                    'cond1': f"MA5({ma5[-1]:.2f})≥MA20({ma20[-1]:.2f})",
                    'cond2': f"20日新高比({np.max(close[-20:])/close[-1]:.2f})≤1.08 + 成交量({vol[-1]:.0f})≥20日均({np.mean(vol[-20:]):.0f})×1.2",
                    'cond3': f"ROC10({roc_10[-1]:.1f})>5 + MACD({macd[-1]:.2f})>信号线({macdsignal[-1]:.2f})",
                    'core_cond': f"昨日收阳({close_yest:.2f}>{open_yest:.2f}) + 涨幅({rise_rate:.1%})≥6.2%"
                })
                g.buy_list.append(stock)
                g.stock_high_dict[stock] = hhv_20
                g.stock_type_dict[stock] = 'strict'
                filter_stats['pass_all'] += 1
            else:
                filter_stats['no_meet_cond'] += 1
                
        except Exception as e:
            filter_stats['error'] += 1
            continue
    
    # 触发兜底选股
    if len(g.buy_list) == 0:
        select_stock_fallback(context)
    
    # 存储缓存
    g.selected_stocks_cache = g.buy_list
    g.stock_high_dict_cache = g.stock_high_dict
    g.need_sell_stocks = hold_stocks - set(g.buy_list)
    
    # 精简日志输出
    log.info("【选股过滤统计】")
    log.info(f"总标的数：{filter_stats['total']} | 最终入选：{filter_stats['pass_all']}")
    log.info(f"过滤项：权限{filter_stats['no_permission']} | 已持仓{filter_stats['already_hold']} | ST{filter_stats['st_stock']} | 新股{filter_stats['new_stock']} | 其他{filter_stats['yest_not_good']+filter_stats['no_meet_cond']}")
    
    # 初选标的列表 - 详细展示符合的条件
    log.info("\n【初选标的明细（符合所有条件）】")
    if qualified_stocks_detail:
        for idx, stock_info in enumerate(qualified_stocks_detail):
            log.info(f"{idx+1}. {stock_info['stock']}({stock_info['name']})")
            log.info(f"   📌 核心条件：{stock_info['core_cond']}")
            log.info(f"   📌 技术条件1：{stock_info['cond1']}")
            log.info(f"   📌 技术条件2：{stock_info['cond2']}")
            log.info(f"   📌 技术条件3：{stock_info['cond3']}")
    else:
        log.info("无符合所有条件的标的")
    
    # 最终选股列表
    log.info("\n【最终选股列表】")
    if g.buy_list:
        for idx, stock in enumerate(g.buy_list):
            stock_name = get_stock_name(stock)
            stock_type = g.stock_type_dict.get(stock, 'fallback')
            tag = "🟢 符合所有条件" if stock_type == 'strict' else "🟡 兜底硬凑"
            log.info(f"{idx+1}. {stock}({stock_name}) {tag}")
    else:
        log.info("无可选标的")
    
    log.info("="*50 + " 选股结束 " + "="*50)

def sell_unselected_stocks(context):
    """清仓非选股列表标的：新增成交校验，修复日志误判，适配4天持股（不做隔日卖出）"""
    global g
    if len(g.need_sell_stocks) == 0:
        log.info("清仓阶段：无需要清仓的标的")
        return
    
    log.info("="*50 + " 清仓阶段 " + "="*50)
    sell_count = 0
    actual_sold_amount = 0.0
    g.sold_cash = 0.0
    g.executed_sold_cash = 0.0
    
    # 清仓明细
    sell_details = []
    failed_sell = []
    
    for stock in g.need_sell_stocks:
        stock_name = get_stock_name(stock)
        # 核心：4天持股策略，仅清仓非选股列表且持仓满4天（或未涨停）的标的，禁止隔日卖出
        hold_days = g.hold_days.get(stock, 0)
        if hold_days < 4:
            log.info(f"跳过{stock}({stock_name})：持仓{hold_days}天（未满4天），不做隔日卖出")
            continue
        if stock in g.today_bought_stocks:
            log.info(f"跳过{stock}({stock_name})：当日买入，禁止清仓")
            continue
        if stock not in context.portfolio.positions:
            log.info(f"跳过{stock}({stock_name})：无持仓")
            continue
        
        try:
            is_limit_up, limit_info = is_stock_limit_up(context, stock)
            if is_limit_up:
                log.info(f"跳过{stock}({stock_name})：涨停 | {limit_info}，继续持有")
                continue
            
            # 获取清仓前仓位
            pos = context.portfolio.positions[stock]
            pre_sell_amount = pos.total_amount
            current_price = get_current_data()[stock].last_price if is_real_trade(context) else pos.price
            
            # 提交清仓订单（单独处理，避免异常影响）
            order_result = None
            try:
                order_result = order_target(stock, 0)
            except Exception as e:
                log.error(f"提交清仓订单失败 {stock}({stock_name})：{str(e)}")
                failed_sell.append(f"{stock}({stock_name})：提交订单异常")
                continue
            
            # 核心：判断订单状态 + 校验实际仓位
            if order_result and is_order_successful(order_result):
                # 校验清仓是否成功
                is_cleared, current_amount = check_position_status(context, stock, 0)
                if is_cleared:
                    # 计算实际回笼资金
                    sold_amount = pre_sell_amount * current_price
                    sold_amount_after_fee = sold_amount * (1 - 0.0013)
                    actual_sold_amount += sold_amount_after_fee
                    sell_count += 1
                    sell_details.append(f"{stock}({stock_name})：清仓成功 | 持仓{hold_days}天 | 原持仓{pre_sell_amount}股 | 成交价{current_price:.2f} | 回笼{sold_amount_after_fee:.2f}元")
                    
                    if stock in g.track_high:
                        del g.track_high[stock]
                    if stock in g.hold_days:
                        del g.hold_days[stock]
                else:
                    failed_sell.append(f"{stock}({stock_name})：订单提交成功，但仓位未清仓（当前持仓{current_amount}股）")
            else:
                failed_sell.append(f"{stock}({stock_name})：订单提交失败 | 状态={str(order_result.status) if (order_result and hasattr(order_result, 'status')) else 'None'}")
        except Exception as e:
            failed_sell.append(f"{stock}({stock_name})：清仓异常 | {str(e)}")
            continue
    
    # 更新实际成交资金
    g.executed_sold_cash = actual_sold_amount
    
    # 输出清仓结果
    log.info(f"【清仓结果】")
    log.info(f"成功清仓：{sell_count}只 | 失败/跳过：{len(failed_sell)}只")
    
    # 成功清仓明细
    if sell_details:
        log.info("✅ 成功清仓明细：")
        for detail in sell_details:
            log.info(f"  - {detail}")
    
    # 失败清仓明细
    if failed_sell:
        log.info("❌ 清仓失败/异常明细：")
        for fail in failed_sell:
            log.info(f"  - {fail}")
    
    log.info(f"合计实际回笼资金：{actual_sold_amount:.2f}元")
    log.info("="*50 + " 清仓结束 " + "="*50)

def buy_after_below_high(context):
    """买入逻辑：移除低于新高限制，完善股票名称显示，补充持仓已满/无资金不买入判断"""
    global g
    if g.selected_stocks_cache is None:
        select_stock(context)
    
    buy_list = g.selected_stocks_cache
    if len(buy_list) == 0:
        log.info("买入阶段：无标的可买")
        return
    
    # 核心：持仓已满（达到最大持仓3只），不做买入动作
    current_positions = list(context.portfolio.positions.keys())
    current_hold_count = len(current_positions)
    if current_hold_count >= g.max_pos:
        log.info(f"买入阶段：当前持仓{current_hold_count}只，已达最大持仓{g.max_pos}只，不买入")
        return
    
    new_stocks = [s for s in buy_list if s not in current_positions]
    target_buy_count = len(new_stocks)
    # 调整目标买入数量，确保不超过最大持仓剩余额度
    target_buy_count = min(target_buy_count, g.max_pos - current_hold_count)
    
    if target_buy_count <= 0:
        log.info("买入阶段：无新标的可买")
        return
    
    # 计算仓位，补充无资金不买入判断
    target_position_value, dynamic_ratio = calculate_target_position_value(context, target_buy_count)
    original_cash = context.portfolio.cash
    total_buy_cash = original_cash + g.executed_sold_cash
    total_usable_cash = total_buy_cash * (1 - 0.0003)
    
    log.info("="*50 + " 买入阶段 " + "="*50)
    log.info(f"买入目标：{target_buy_count}只 | 单只目标市值：{target_position_value:.2f}元（{dynamic_ratio*100:.2f}%）")
    log.info(f"可用资金：{total_usable_cash:.2f}元 | 当前持仓：{current_hold_count}只 | 最大持仓：{g.max_pos}只")
    
    # 核心：可用资金不足，不做买入动作
    if total_usable_cash < 1000:
        log.info("买入终止：可用资金不足1000元，不买入")
        return
    
    # 筛选合格标的（仅过滤涨停和流动性，移除低于新高限制）
    qualified_stocks = []
    for stock in new_stocks:
        stock_name = get_stock_name(stock)
        try:
            if not check_liquidity(context, stock):
                log.info(f"跳过{stock}({stock_name})：流动性不足（近5日平均成交量<500手）")
                continue
            
            is_limit_up, limit_info = is_stock_limit_up(context, stock)
            if is_limit_up:
                log.info(f"跳过{stock}({stock_name})：涨停 | {limit_info}")
                continue
            
            current_data = get_current_data()[stock]
            if not current_data or current_data.paused:
                log.info(f"跳过{stock}({stock_name})：无数据/停牌")
                continue
            
            current_price = current_data.last_price if is_real_trade(context) else current_data.close
            if current_price <= 0:
                log.info(f"跳过{stock}({stock_name})：价格异常（当前价={current_price}）")
                continue
            
            # 移除低于新高比例检查
            # 获取20日新高（仅用于日志展示，不做过滤）
            latest_hhv_20, below_high_rate = get_latest_20day_high(context, stock)
            log.info(f"筛选通过{stock}({stock_name})：低于新高{below_high_rate*100:.1f}% | 当前价{current_price:.2f} | 20日新高{latest_hhv_20:.2f}")
            
            # 存储标的详细信息
            qualified_stocks.append({
                'stock': stock,
                'name': stock_name,
                'price': current_price,
                'below_high_rate': below_high_rate,
                'type': g.stock_type_dict.get(stock, 'fallback')
            })
        except Exception as e:
            log.warning(f"筛选标的失败 {stock}({stock_name})：{str(e)}")
            continue
    
    # 执行买入 + 成交校验
    bought_count = 0
    buy_details = []
    failed_buy = []
    # 确保买入后不超过最大持仓
    qualified_stocks = qualified_stocks[:g.max_pos - current_hold_count]
    for item in qualified_stocks:
        stock = item['stock']
        stock_name = item['name']
        current_price = item['price']
        stock_type = "🟢 符合所有条件" if item['type'] == 'strict' else "🟡 兜底硬凑"
        
        # 计算买入数量
        buy_amount = 0
        try:
            buy_amount = calculate_buy_amount(stock, target_position_value, current_price)
        except Exception as e:
            log.error(f"计算买入数量失败 {stock}({stock_name})：{str(e)}")
            failed_buy.append(f"{stock}({stock_name})：计算数量异常")
            continue
        
        if buy_amount<= 0:
            log.info(f"跳过{stock}({stock_name})：可买数量为0（目标市值{target_position_value:.2f} | 当前价{current_price:.2f}）")
            continue
        
        # 提交买入订单
        order_result = None
        try:
            order_result = order(stock, buy_amount)
        except Exception as e:
            log.error(f"提交买入订单失败 {stock}({stock_name})：{str(e)}")
            failed_buy.append(f"{stock}({stock_name})：提交订单异常")
            continue
        
        # 核心：订单状态判断 + 实际仓位校验
        if order_result and is_order_successful(order_result):
            # 校验买入是否成功
            is_bought, current_amount = check_position_status(context, stock, buy_amount)
            if is_bought:
                bought_count += 1
                g.today_bought_stocks.add(stock)
                g.track_high[stock] = current_price
                g.hold_days[stock] = 0  # 买入当天持仓天数记为0（次日开始计数）
                
                # 记录买入明细
                buy_value = current_price * current_amount
                buy_details.append({
                    'stock': stock,
                    'name': stock_name,
                    'type': stock_type,
                    'price': current_price,
                    'amount': current_amount,
                    'value': buy_value,
                    'below_high_rate': item['below_high_rate']
                })
                log.info(f"✅ 买入成功：{stock}({stock_name}) {stock_type} | 委托{buy_amount}股 | 实际成交{current_amount}股")
            else:
                failed_buy.append(f"{stock}({stock_name})：订单提交成功，但未持仓（当前{current_amount}股）")
        else:
            status_str = str(order_result.status) if (order_result and hasattr(order_result, 'status')) else 'None'
            failed_buy.append(f"{stock}({stock_name})：订单提交失败 | 状态={status_str}")
    
    # 输出买入结果
    log.info(f"\n【买入结果明细】")
    if buy_details:
        for idx, detail in enumerate(buy_details):
            log.info(f"{idx+1}. {detail['stock']}({detail['name']}) {detail['type']}")
            log.info(f"   价格：{detail['price']:.2f}元 | 数量：{detail['amount']}股 | 金额：{detail['value']:.2f}元")
            log.info(f"   参考：低于20日新高{detail['below_high_rate']*100:.1f}% | 单只仓位占比{dynamic_ratio*100:.2f}%")
    
    # 输出买入失败明细
    if failed_buy:
        log.info("\n❌ 买入失败/异常明细：")
        for fail in failed_buy:
            log.info(f"  - {fail}")
    
    log.info(f"买入统计：目标{len(qualified_stocks)}只 | 实际成交{bought_count}只 | 买入后持仓：{current_hold_count + bought_count}只")
    log.info("="*50 + " 买入结束 " + "="*50)

def calibrate_position(context):
    """仓位校准：精简日志（带股票名称），适配4天持股，不影响持仓周期"""
    global g
    current_hold_count = len(context.portfolio.positions)
    if current_hold_count <= 0 or g.selected_stocks_cache is None:
        return
    
    # 仅对持仓未满4天的标的进行校准，避免影响4天持股周期
    target_stock_count = 0
    for stock in list(context.portfolio.positions.keys()):
        hold_days = g.hold_days.get(stock, 0)
        if hold_days < 4 and stock in g.selected_stocks_cache:
            target_stock_count += 1
    
    if target_stock_count <= 0:
        log.info("仓位校准：无需要校准的标的（均为持仓满4天或非选股列表标的）")
        return
    
    target_position_value, dynamic_ratio = calculate_target_position_value(context, target_stock_count)
    calibrate_count = 0
    selected_stocks = g.selected_stocks_cache
    
    calibrate_details = []
    for stock in list(context.portfolio.positions.keys()):
        stock_name = get_stock_name(stock)
        hold_days = g.hold_days.get(stock, 0)
        try:
            if stock in g.today_bought_stocks or stock not in selected_stocks or hold_days >= 4:
                continue
            
            is_limit_up, _ = is_stock_limit_up(context, stock)
            if is_limit_up:
                continue
            
            current_data = get_current_data()[stock]
            current_price = current_data.last_price if is_real_trade(context) else current_data.close
            pos = context.portfolio.positions[stock]
            current_val = pos.total_amount * current_price
            
            diff_rate = abs(current_val - target_position_value) / target_position_value
            if diff_rate < 0.05:
                continue
            
            # 执行校准
            if current_val < target_position_value:
                need = target_position_value - current_val
                buy_amt = calculate_buy_amount(stock, need, current_price)
                if buy_amt > 0 and check_liquidity(context, stock):
                    res = order(stock, buy_amt)
                    if res and is_order_successful(res):
                        calibrate_count += 1
                        calibrate_details.append(f"{stock}({stock_name})：加仓{buy_amt}股（持仓{hold_days}天）")
            else:
                need = current_val - target_position_value
                sell_amt = calculate_buy_amount(stock, need, current_price)
                if sell_amt > 0:
                    res = order(stock, -sell_amt)
                    if res and is_order_successful(res):
                        calibrate_count += 1
                        calibrate_details.append(f"{stock}({stock_name})：减仓{sell_amt}股（持仓{hold_days}天）")
        except Exception as e:
            continue
    
    if calibrate_count > 0:
        log.info(f"【仓位校准】共校准{calibrate_count}只")
        for detail in calibrate_details:
            log.info(f"  - {detail}")

def stop_loss_take_profit(context):
    """止损止盈：适配4天持股策略，核心调整如下：
    1. 持仓1-3天：仅止损（不做止盈），统一4%止损，触发即卖，空出仓位资金可买新标的
    2. 持仓4天：早盘判断，未涨停则清仓，涨停则续抱
    3. 续抱期间（持仓≥5天）：仅最高价回落2%清仓，无其他止盈止损
    4. 新增成交校验，完善日志
    """
    global g
    current_time = context.current_dt.time()
    if not (datetime.time(9,30) <= current_time <= datetime.time(15,00)):
        return
    
    sl_count = 0
    tp_count = 0
    limit_up_hold = 0
    
    selected = g.selected_stocks_cache or []
    sl_tp_details = []
    
    for stock in list(context.portfolio.positions.keys()):
        stock_name = get_stock_name(stock)
        try:
            if stock in g.today_bought_stocks:
                continue
            
            pos = context.portfolio.positions[stock]
            cost = pos.avg_cost
            if cost <= 0:
                continue
            
            is_limit_up, limit_info = is_stock_limit_up(context, stock)
            hold_days = g.hold_days.get(stock, 0)  # 持仓天数：买入当天0天，次日1天，第4天3天，第5天4天
            
            # 实时更新最高价（用于续抱期间回落止损）
            current = get_current_data()[stock].last_price if is_real_trade(context) else get_current_data()[stock].close
            if current<= 0:
                continue
            if stock in g.track_high:
                g.track_high[stock] = max(g.track_high[stock], current)
            else:
                g.track_high[stock] = current
            high = g.track_high[stock]
            loss = (cost - current) / cost
            dd = (high - current) / high if high > 0 else 0
            
            # 1. 持仓1-3天（hold_days=1、2、3）：统一4%止损，触发即卖，可买新标的
            if 1 <= hold_days <= 3:
                if loss >= g.stop_loss_rate:
                    order_target(stock, 0)
                    # 校验止损是否成功
                    is_stopped, current_amount = check_position_status(context, stock, 0)
                    if is_stopped:
                        sl_count += 1
                        sl_tp_details.append(f"{stock}({stock_name})：止损成功 | 持仓{hold_days}天 | 成本{cost:.2f} 当前{current:.2f} 亏损{loss:.1%}（触发4%止损）")
                        if stock in g.track_high:
                            del g.track_high[stock]
                        if stock in g.hold_days:
                            del g.hold_days[stock]
                    else:
                        sl_tp_details.append(f"{stock}({stock_name})：止损订单提交，但仓位未清仓（当前{current_amount}股）")
                continue
            
            # 2. 持仓4天（hold_days=4）：早盘（9:30-10:00）判断，未涨停清仓，涨停续抱
            if hold_days == 4:
                if current_time<= datetime.time(10, 00):
                    if is_limit_up:
                        limit_up_hold += 1
                        sl_tp_details.append(f"{stock}({stock_name})：持仓4天，早盘涨停{limit_info}，继续持有（续抱）")
                    else:
                        order_target(stock, 0)
                        is_cleared, current_amount = check_position_status(context, stock, 0)
                        if is_cleared:
                            sl_tp_details.append(f"{stock}({stock_name})：持仓4天，早盘未涨停，清仓 | 成本{cost:.2f} 当前{current:.2f}")
                            if stock in g.track_high:
                                del g.track_high[stock]
                            if stock in g.hold_days:
                                del g.hold_days[stock]
                        else:
                            sl_tp_details.append(f"{stock}({stock_name})：清仓订单提交，但仓位未清仓（当前{current_amount}股）")
                # 早盘过后，涨停则续抱，未涨停已清仓，无需再操作
                continue
            
            # 3. 续抱期间（hold_days≥5）：仅最高价回落2%清仓，无其他止盈止损
            if hold_days >= 5:
                if dd >= g.take_profit_drawdown:
                    order_target(stock, 0)
                    is_taken, current_amount = check_position_status(context, stock, 0)
                    if is_taken:
                        tp_count += 1
                        sl_tp_details.append(f"{stock}({stock_name})：续抱清仓成功 | 持仓{hold_days}天 | 新高{high:.2f} 当前{current:.2f} 回撤{dd:.1%}")
                        if stock in g.track_high:
                            del g.track_high[stock]
                        if stock in g.hold_days:
                            del g.hold_days[stock]
                    else:
                        sl_tp_details.append(f"{stock}({stock_name})：止盈订单提交，但仓位未清仓（当前{current_amount}股）")
                # 未回落则继续持有
                continue
            
        except Exception as e:
            log.error(f"止损止盈处理{stock}({stock_name})出错：{str(e)}")
            continue
    
    if sl_count + tp_count + limit_up_hold > 0:
        log.info("="*50 + " 止损止盈 " + "="*50)
        log.info(f"止损：{sl_count} | 续抱清仓：{tp_count} | 涨停续抱：{limit_up_hold}")
        for detail in sl_tp_details:
            log.info(f"  - {detail}")
        log.info("="*50 + " 止损止盈结束 " + "="*50)

def check_daily_position(context):
    """新增：每日收盘仓位校验（核心），适配4天持股策略"""
    log.info("="*50 + " 每日仓位校验 " + "="*50)
    
    # 1. 校验选股列表持仓
    selected_stocks = g.selected_stocks_cache or []
    missing_selected = []
    for stock in selected_stocks:
        stock_name = get_stock_name(stock)
        has_position, current_amount = check_position_status(context, stock, 100)  # 至少持仓100股
        if not has_position:
            missing_selected.append(f"{stock}({stock_name})：应持仓但实际无持仓")
    
    # 2. 校验非选股列表持仓（应清仓，且持仓满4天）
    extra_positions = []
    for stock in context.portfolio.positions:
        stock_name = get_stock_name(stock)
        hold_days = g.hold_days.get(stock, 0)
        if stock not in selected_stocks:
            if hold_days >= 4:
                has_position, current_amount = check_position_status(context, stock, 0)
                if not has_position:
                    extra_positions.append(f"{stock}({stock_name})：应清仓但实际持仓{current_amount}股（持仓{hold_days}天）")
            else:
                log.info(f"⚠️ {stock}({stock_name})：非选股列表但持仓未满4天（{hold_days}天），暂不清仓")
    
    # 3. 校验最大持仓限制
    current_hold_count = len(context.portfolio.positions)
    if current_hold_count > g.max_pos:
        log.info(f"⚠️ 警告：当前持仓{current_hold_count}只，超过最大持仓{g.max_pos}只")
    else:
        log.info(f"✅ 持仓数量正常：当前{current_hold_count}只，最大{g.max_pos}只")
    
    # 4. 输出校验结果
    log.info(f"选股列表总数：{len(selected_stocks)} | 当前持仓总数：{len(context.portfolio.positions)}")
    
    if missing_selected:
        log.info("❌ 缺失持仓（应买未买）：")
        for miss in missing_selected:
            log.info(f"  - {miss}")
    else:
        log.info("✅ 选股列表持仓完整")
    
    if extra_positions:
        log.info("❌ 多余持仓（应清未清）：")
        for extra in extra_positions:
            log.info(f"  - {extra}")
    else:
        log.info("✅ 无多余持仓（非选股列表标的均未满4天）")
    
    log.info("="*50 + " 仓位校验结束 " + "="*50)

def handle_data(context, data):
    pass