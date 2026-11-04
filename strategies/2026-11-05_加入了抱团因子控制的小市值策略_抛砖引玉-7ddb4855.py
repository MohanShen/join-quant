# Clone from JoinQuant
# postId: 7ddb4855abfc4049c9f182afc271cccb
# backtestId: 4a6efbac15739094cb0f166b9d795389
# title: 加入了抱团因子控制的小市值策略（抛砖引玉）

# 标题：三马策略1-小市值独立版 (无防御+无月份限制)
# 说明：
# 1. 移除了成交额宽度防御（组20）逻辑。
# 2. 移除了1月和4月空仓限制，全年交易。
# 3. 保留了大盘顶背离风控、止盈止损、换手率检测。
# 4. 新增：可选集中度抱团风控（MA20>42% 且 当日>44% 时清仓并禁止当日买入）
#    集中度历史数据实时累积，无需预填充。
# 5. 新增：附图显示当日集中度和20日均线（含当日）。

import datetime
import math
import prettytable
import numpy as np
import pandas as pd
from collections import defaultdict
from jqdata import *
from jqfactor import *
from prettytable import PrettyTable

""" ====================== 基础设置 ====================== """

def initialize(context):
    set_backtest()  # 设置回测条件
    set_params(context)  # 设置参数
    
    # 过滤日志
    log.set_level('order', 'error')

    # === 定时任务配置 ===
    
    # 1. 每日9:15输出集中度日志并记录到图表
    run_daily(log_concentration_stat, '9:15')
    
    # 2. 每日开盘后检测集中度风控 (9:31)
    run_daily(concentration_risk_control, '9:31')
    
    # 3. 每日开盘前检测大盘顶背离 (DBL)
    if g.DBL_control:
        run_daily(check_dbl, '9:31') 

    # 4. 每周一进行买卖操作
    run_weekly(strategy_1_sell, 1, '09:49')
    run_weekly(strategy_1_buy, 1, '09:50')

    # 5. 每日盘中检查
    # 换手率放量/缩量检查
    if g.huanshou_check:
        run_daily(xsz_huanshou_check, '10:30')
    
    # 止盈止损检查 (10:35)
    run_daily(take_profit_stop_loss, '10:35')
    
    # 昨日涨停股检查 (14:00)
    run_daily(check_limit_up, '14:00')
    
    # 6. 打印持仓日报
    run_daily(print_summary, '15:02')

# 回测环境设置
def set_backtest():
    set_option('avoid_future_data', True)
    set_benchmark('000001.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.002), type="stock")
    
    # 设置手续费
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.85/10000, close_commission=0.85/10000,
        close_today_commission=0, min_commission=5
    ), type="stock")

# 参数设置
def set_params(context):
    # === 策略核心参数 ===
    g.xsz_stock_num = 5       # 持股数量
    g.min_mv = 5              # 最小市值(亿)
    g.max_mv = 50             # 最大市值(亿)
    g.up_price = 20           # 个股价格上限
    
    # === 状态变量 ===
    g.target_list = []        # 目标持仓股票
    g.yesterday_HL_list = []  # 昨日涨停股票
    g.no_buy_stocks = {}      # 黑名单（止损后短期不买）
    g.check_after_no_buy = True 
    g.no_buy_after_day = 3    # 止损后不买入的时间窗口

    # === 风控配置 ===
    
    # 1. 顶背离(DBL)配置
    g.DBL_control = True      # 开关
    g.dbl = []
    g.check_dbl_days = 10     # 检测窗口
    
    # 2. 止盈止损配置
    g.run_stoploss = True     
    g.use_move_stoploss = False 
    g.stoploss_limit = 0.09   # 止损线 9%
    g.stop_loss_tracking = {} 
    
    # 3. 换手率检查配置
    g.huanshou_check = True   
    
    # ========== 新增：集中度抱团风控配置 ==========
    g.concentration_history = []          # 存储每日集中度（含当日，每日9:15追加）
    g.in_risk_mode = False                # 风控状态标记（True时禁止买入）
    g.enable_concentration_risk_control = True   # 总开关
    g.concentration_ma_threshold = 0.43   # 20日均线阈值 42%
    g.concentration_current_threshold = 0.45  # 当日集中度阈值 44%

""" ====================== 选股与交易逻辑 ====================== """

# 选股核心模块
def xsz_get_stock_list(context):
    initial_list = filter_stocks(context, get_index_stocks('399101.XSHE'))

    # 基本面筛选：5-50亿市值，正收益，营收>1亿，高ROE/ROA
    q = query(
        valuation.code,
        valuation.market_cap,
        income.np_parent_company_owners,
        income.net_profit,
        income.operating_revenue,
        valuation.turnover_ratio
    ).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(g.min_mv, g.max_mv),
        income.np_parent_company_owners > 0,
        income.net_profit > 0,
        income.operating_revenue > 1e8,
        fundamentals.indicator.roe > 0.15,
        fundamentals.indicator.roa > 0.10,
    ).order_by(valuation.market_cap.asc()).limit(50)
    
    df = get_fundamentals(q)
    if df.empty:
        return []
    final_list = list(df.code)
    
    # 价格过滤
    last_prices = history(1, '1d', 'close', final_list, df=False)
    return [stock for stock in final_list if stock in context.portfolio.positions or last_prices[stock] <= g.up_price][:g.xsz_stock_num]

# 卖出逻辑
def strategy_1_sell(context):
    g.target_list = []
    
    # 1. 大盘顶背离风控
    if g.DBL_control:
        # 首次运行检测最近10日顶背离
        if len(g.dbl) < 10:
            for i in range(9, -1, -1):
                check_dbl(context, end_days=0 - i)
        
        # 如果近10天有触发顶背离，暂停交易并清仓（非涨停）
        if 1 in g.dbl[-g.check_dbl_days:]:
            print(f"近{g.check_dbl_days}日检测到大盘顶背离，暂停调仓以控制风险")
            return

    # [已移除] 成交额宽度防御风控
    # [已移除] 1月和4月空仓月份限制

    current_data = get_current_data()

    # 2. 获取最新选股目标
    g.target_list = xsz_get_stock_list(context)[:g.xsz_stock_num]
    print(f'小市值目标持仓: {g.target_list}')

    # 3. 卖出不在目标列表中的股票（除昨日涨停股）
    sell_list = [s for s in context.portfolio.positions.keys() if s not in g.target_list and s not in g.yesterday_HL_list]
    for stock in sell_list:
        if current_data[stock].paused:
            print(f"{stock} 停牌, 无法卖出")
        else:
            close_position(context, stock)
            print(f"小市值策略卖出: {stock}")

# 买入逻辑
def strategy_1_buy(context):
    # ===== 新增：如果处于集中度风控模式，禁止买入 =====
    if g.in_risk_mode:
        print("[统一买入] 当前处于集中度风控模式，暂停买入小市值股票")
        return
    
    # 计算可用资金 (全仓模式)
    current_value = context.portfolio.total_value
    
    # 买入新标的
    buy_list = [s for s in g.target_list if s not in context.portfolio.positions]
    
    if buy_list and context.portfolio.available_cash > 0:
        # 简单均分资金，实际交易时可能会有剩余
        position_count = len(context.portfolio.positions)
        target_slots = g.xsz_stock_num - position_count
        if target_slots > 0:
            cash_per_stock = context.portfolio.available_cash / len(buy_list)
            for stock in buy_list:
                open_position(context, stock, cash_per_stock)
                print(f"小市值策略买入: {stock}, 金额: {cash_per_stock:.2f}")

""" ====================== 风控模块 ====================== """

# 大盘顶背离检测 (DBL)
def check_dbl(context, market_index='399101.XSHE', end_days=0):
    # 避免第一次9:31造成的干扰
    if not g.dbl and "9:31" in str(context.current_dt.time()):
        return

    def detect_divergence():
        fast, slow, sign = 12, 26, 9
        rows = (fast + slow + sign) * 5
        grid = attribute_history(market_index, rows + 10, fields=['close']).dropna()
        if end_days < 0:
            grid = grid.iloc[:end_days]

        if len(grid) < rows:
            return False

        try:
            grid['dif'], grid['dea'], grid['macd'] = mcad(grid.close, fast, slow, sign)
            mask = (grid['macd'] < 0) & (grid['macd'].shift(1) >= 0)
            if mask.sum() < 2:
                return False

            key2, key1 = mask[mask].index[-2], mask[mask].index[-1]
            price_cond = grid.close[key2] < grid.close[key1]
            dif_cond = grid.dif[key2] > grid.dif[key1] > 0
            macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]

            if len(grid['dif']) > 20:
                recent_avg = grid['dif'].iloc[-10:].mean()
                prev_avg = grid['dif'].iloc[-20:-10].mean()
                trend_cond = recent_avg < prev_avg
            else:
                trend_cond = False
            
            return price_cond and dif_cond and macd_cond and trend_cond

        except Exception as e:
            print(f"顶背离检测错误: {e}")
            return False

    if detect_divergence():
        g.dbl.append(1)
        print(f"⚠️⚠️⚠️⚠️ 检测到{market_index}顶背离信号，清仓非涨停股票")
        current_data = get_current_data()
        for stock in list(context.portfolio.positions.keys()):
            if current_data[stock].last_price < current_data[stock].high_limit:
                print(f"{stock} 因大盘顶背离清仓（非涨停股）")
                close_position(context, stock)
    else:
        g.dbl.append(0)
        print(f"未检测到大盘顶背离，市场趋势正常")

# 换手率检查
def xsz_huanshou_check(context):
    def huanshoulv(_stock, is_avg=False):
        if is_avg:
            end_date = context.previous_date
            df_volume = get_price(_stock, end_date=end_date, frequency='daily', fields=['volume'], count=20)
            df_cap = get_valuation(_stock, end_date=end_date, fields=['circulating_cap'], count=1)
            circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
            if circulating_cap == 0:
                return 0.0
            df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
            return df_volume['turnover_ratio'].mean()
        else:
            date_now = context.current_dt
            df_vol = get_price(_stock, start_date=date_now.date(), end_date=date_now, frequency='1m', fields=['volume'],
                               skip_paused=False, fq='pre', panel=True, fill_paused=False)
            volume = df_vol['volume'].sum()
            date_pre = context.previous_date
            df_circulating_cap = get_valuation(_stock, end_date=date_pre, fields=['circulating_cap'], count=1)
            circulating_cap = df_circulating_cap['circulating_cap'].iloc[0] if not df_circulating_cap.empty else 0
            if circulating_cap == 0:
                return 0.0
            turnover_ratio = volume / (circulating_cap * 10000)
            return turnover_ratio

    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in list(context.portfolio.positions.keys()):
        if current_data[stock].paused:
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
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        if action:
            print(f"{action} {stock} {get_stock_name(stock)}  换手率:{rt:.2%}  均:{avg:.2%} 倍率:x{r:.1f} {icon}")
            close_position(context, stock)

# 止盈止损
def take_profit_stop_loss(context):
    if not g.run_stoploss:
        return

    # 更新黑名单计数
    no_buy_stocks = {}
    for k, v in g.no_buy_stocks.items():
        v += 1
        if v <= g.no_buy_after_day:
            no_buy_stocks[k] = v
    g.no_buy_stocks = no_buy_stocks

    current_data = get_current_data()
    
    # 移动止损逻辑
    if g.use_move_stoploss:
        for stock, position in context.portfolio.positions.items():
            if current_data[stock].paused: continue
            current_price = current_data[stock].last_price
            if stock not in g.stop_loss_tracking:
                g.stop_loss_tracking[stock] = max(position.avg_cost, current_price)
            else:
                g.stop_loss_tracking[stock] = max(g.stop_loss_tracking[stock], current_price)
            
            highest_price = g.stop_loss_tracking[stock]
            if current_price <= highest_price * (1 - g.stoploss_limit):
                close_position(context, stock)
                g.no_buy_stocks[stock] = 1
                print(f"移动止损卖出 {stock}, 亏损:{(1 - position.price / position.avg_cost):.2%}")

    # 固定止盈止损逻辑
    for stock, pos in context.portfolio.positions.items():
        if current_data[stock].paused: continue
        
        # 止盈：100%
        if pos.price >= pos.avg_cost * 2:
            close_position(context, stock)
            g.no_buy_stocks[stock] = 1
            print(f"止盈卖出 {stock}, 收益率:{(pos.price / pos.avg_cost - 1):.2%}")
        
        # 止损：9%
        if not g.use_move_stoploss and pos.price <= pos.avg_cost * (1 - g.stoploss_limit):
            close_position(context, stock)
            g.no_buy_stocks[stock] = 1
            print(f"止损卖出 {stock}, 亏损:{(1 - pos.price / pos.avg_cost):.2%}")

# 检查昨日涨停
def check_limit_up(context):
    holdings = list(context.portfolio.positions.keys())
    g.yesterday_HL_list = []
    if holdings:
        valid_holdings = [s for s in holdings if isinstance(s, str) and '.' in s]
        if valid_holdings:
            df = get_price(valid_holdings, end_date=context.previous_date,
                           frequency='daily', fields=['close', 'high_limit'],
                           count=1, panel=False)
            if not df.empty:
                g.yesterday_HL_list = list(df[df['close'] >= df['high_limit'] * 0.997].index)
                if g.yesterday_HL_list:
                    print(f"昨日涨停股: {g.yesterday_HL_list}")

    for stock in g.yesterday_HL_list:
        try:
            current_data = get_current_data()[stock]
            if current_data.last_price < current_data.high_limit * 0.99:
                print(f"涨停打开卖出 {stock}")
                close_position(context, stock)
                g.no_buy_stocks[stock] = 1
        except Exception:
            pass

""" ====================== 新增：集中度相关函数（含图表记录） ====================== """

# 集中度日志函数（每日9:15执行，计算并存储当日集中度，并记录到图表）
def log_concentration_stat(context):
    """
    每日9:15输出成交额集中度统计（基于前一交易日数据）
    集中度 = Top5%成交额 / 总成交额
    均值、标准差基于历史前20个交易日数据（不含当日），不足则提示。
    同时将当日集中度和20日均线（含当日）记录到自定义图表。
    """
    prev_date = context.previous_date
    if prev_date is None:
        return
    
    # 获取全市场股票列表
    all_stocks = list(get_all_securities(['stock']).index)
    try:
        df = get_price(all_stocks, end_date=prev_date, frequency='daily',
                       fields=['money'], count=1, panel=False, skip_paused=False)
        if df is None or df.empty:
            print("[集中度] 获取成交额数据为空")
            return
        money_series = df.set_index('code')['money'].dropna()
        if len(money_series) == 0:
            print("[集中度] 有效成交额数据为空")
            return
    except Exception as e:
        print(f"[集中度] 获取成交额数据失败: {e}")
        return
    
    total_money = money_series.sum()
    if total_money == 0:
        print("[集中度] 总成交额为0，无法计算")
        return
    
    sorted_money = money_series.sort_values(ascending=False)
    top_n = max(1, int(len(money_series) * 0.05))
    concentration = sorted_money.iloc[:top_n].sum() / total_money
    
    # 将当日集中度追加到历史（供后续使用）
    g.concentration_history.append(concentration)
    
    # ---- 图表记录部分 ----
    # 计算包含当日的20日均线（与风控阈值一致）
    if len(g.concentration_history) >= 20:
        ma20 = np.mean(g.concentration_history[-20:])
    else:
        ma20 = np.mean(g.concentration_history) if g.concentration_history else concentration
    
    # 记录到自定义图表（数值乘以100转换为百分比）
    record(当日成交额集中度=round(concentration * 100, 2))
    record(集中度20日均线=round(ma20 * 100, 2))
    
    # ---- 日志输出部分 ----
    # 统计量基于历史数据（不含当日）
    if len(g.concentration_history) <= 1:
        print("[集中度] 历史数据不足，无法计算统计量")
    else:
        # 取最近20个历史值（不含当日，即除去刚追加的最后一个）
        hist = g.concentration_history[:-1]
        lookback = min(20, len(hist))
        hist_arr = np.array(hist[-lookback:])
        mean_val = hist_arr.mean()
        std_val = hist_arr.std()
        current_val = concentration
        extreme_thresh = mean_val + 1.5 * std_val
        
        print(f"今日【成交额集中度（核心抱团指标）】")
        print(f"  均值: {mean_val:.1%}    标准差: {std_val:.1%}    当前: {current_val:.1%}    极端阈值(均值+1.5σ): {extreme_thresh:.1%}")

# 集中度抱团风控函数（9:31执行）
def concentration_risk_control(context):
    """
    基于集中度指标的抱团风控：
    如果 20日均线 > 42% 且 当日集中度 > 44%，则清仓所有小市值股票，并设置 g.in_risk_mode = True。
    如果条件不再满足且之前处于风控模式，则解除风控模式。
    注意：当日集中度已在9:15存入 g.concentration_history，因此历史列表最后一项即为当日值。
    """
    if not g.enable_concentration_risk_control:
        return
    
    # 需要至少20个历史数据点（含当日）
    if len(g.concentration_history) < 20:
        print(f"[抱团风控] 历史数据不足（需至少20个数据，当前{len(g.concentration_history)}），暂不判断")
        return
    
    # 获取包含当日的20日均线和当日集中度
    ma20 = np.mean(g.concentration_history[-20:])
    conc_current = g.concentration_history[-1]
    
    # 判断是否触发清仓
    trigger = (ma20 > g.concentration_ma_threshold) and (conc_current > g.concentration_current_threshold)
    
    if trigger:
        if not g.in_risk_mode:
            print(f"[抱团风控] 触发清仓条件！集中度MA20={ma20:.1%} > {g.concentration_ma_threshold:.1%} 且 当日集中度={conc_current:.1%} > {g.concentration_current_threshold:.1%}")
            print("[抱团风控] 开始清仓所有小市值股票，并禁止当日买入")
            
            # 收集所有持仓股票
            stocks_to_sell = list(context.portfolio.positions.keys())
            
            if stocks_to_sell:
                print(f"[抱团风控] 待清仓股票: {[format_stock_code(s) for s in stocks_to_sell]}")
                for stock in stocks_to_sell:
                    try:
                        current_data = get_current_data()[stock]
                        limit_price = current_data.low_limit
                        order = order_target_value(stock, 0, style=LimitOrderStyle(limit_price))
                        if order:
                            print(f"[抱团风控] 已卖出 {format_stock_code(stock)}，挂单价{limit_price:.2f}")
                        else:
                            print(f"[抱团风控] 卖出失败 {format_stock_code(stock)}")
                    except Exception as e:
                        print(f"[抱团风控] 卖出异常 {stock}: {e}")
            else:
                print("[抱团风控] 当前无持仓，无需清仓")
            
            # 设置风控模式，禁止当天买入
            g.in_risk_mode = True
        # 若已在风控模式，无需重复操作
    else:
        # 条件不满足，如果之前处于风控模式，则解除
        if g.in_risk_mode:
            print(f"[抱团风控] 风险解除，集中度MA20={ma20:.1%} 或 当日集中度={conc_current:.1%} 已低于阈值，恢复买入权限")
            g.in_risk_mode = False

# 工具函数：格式化股票代码（用于日志）
def format_stock_code(stock_code):
    try:
        stock_info = get_security_info(stock_code)
        return f"{stock_code[:6]}({stock_info.display_name})"
    except:
        return stock_code[:6]

""" ====================== 工具函数 ====================== """

def filter_stocks(context, stock_list):
    current_data = get_current_data()
    filtered = []
    for stock in stock_list:
        if current_data[stock].paused: continue
        if current_data[stock].is_st: continue
        if '退' in current_data[stock].name: continue
        if stock.startswith(('30', '68', '8', '4')): continue
        
        ipo_date = get_security_info(stock).start_date
        if (context.current_dt.date() - ipo_date).days < 365: continue
        
        last_price = current_data[stock].last_price
        if last_price >= current_data[stock].high_limit: continue
        if last_price <= current_data[stock].low_limit: continue
        
        if g.check_after_no_buy:
            if stock in g.no_buy_stocks:
                continue
        filtered.append(stock)
    return filtered

def mcad(close, short=12, long=26, m=9):
    def ema(series, n):
        return pd.Series.ewm(series, span=n, min_periods=n - 1, adjust=False).mean()
    dif = ema(close, short) - ema(close, long)
    dea = ema(dif, m)
    return dif, dea, (dif - dea) * 2

def get_stock_name(security):
    try:
        return get_security_info(security).display_name
    except:
        return "Unknown"

def open_position(context, security, value):
    return order_target_value(security, value)

def close_position(context, security):
    return order_target_value(security, 0)

def print_summary(context):
    table = PrettyTable(["股票名称", "代码", "持仓", "成本", "现价", "盈亏", "市值"])
    total_val = 0
    for stock, pos in context.portfolio.positions.items():
        pnl = (pos.price - pos.avg_cost) * pos.total_amount
        table.add_row([get_stock_name(stock), stock[:6], pos.total_amount, f"{pos.avg_cost:.2f}", 
                       f"{pos.price:.2f}", f"{pnl:.2f}", f"{pos.value:.2f}"])
        total_val += pos.value
    print(f"总资产: {context.portfolio.total_value:.2f} 持仓市值: {total_val:.2f}")
    print(table)