# Clone from JoinQuant
# postId: d1ac793b3f0da6c53de6856a76ff46de
# backtestId: 5b59a2eca6aa403109de35c2868fd669
# title: 发个分钟级打板策略，带来了个简化板的，年化123%无未来。

from jqdata import *
from jqfactor import *
import pandas as pd
from datetime import datetime,timedelta,date
import time
import numpy as np

################################### 可配置参数（取消市值过滤） #############################################
g_check_start_time = "10:00"  # 非涨停检查开始时间
g_check_end_time = "14:45"    # 非涨停检查结束时间
g_check_interval = 5          # 检查间隔（分钟）
g_buy_price_threshold = 0.02  # 距离涨停价≥2%（放宽后）
g_high_open_threshold = 0.03  # 高开≥3%（放宽后）
g_buy_window_start = "09:40"  # 买入开始时间
g_buy_window_end = "10:00"    # 买入结束时间（延长至10:00）
# 新增高开比例异常值阈值
g_high_open_min = 0.03  # 最低高开比例（≥0.03，剔除低开/平开）
g_high_open_max = 0.20  # 最高高开比例（≤20%，剔除极端高开）
# 新增回撤控制参数
g_max_drawdown = 0.06   # 最大允许回撤比例（6%）
g_cool_down_days = 5    # 冷却期交易日数量
g_drawdown_check_times = ["10:00", "14:00"]  # 回撤检查时间点
# 新增涨停数量阈值
g_zt_count_min = 60     # 昨日涨停数量下限
g_zt_count_max = 80     # 昨日涨停数量上限

################################### 核心清仓函数 #############################################
def order_target_percent(security, target_percent):
    """保留核心清仓逻辑"""
    context = get_current_context()
    position = context.portfolio.positions.get(security, None)
    current_amount = position.closeable_amount if position else 0
    
    target_value = context.portfolio.total_value * target_percent
    current_price = get_current_data()[security].last_price
    
    target_amount = int(target_value / current_price // 100 * 100) if current_price > 0 else 0
    delta_amount = target_amount - current_amount
    
    if delta_amount != 0:
        order_id = order(security, delta_amount)
        if order_id and target_percent == 0 and position:
            profit_amount = (current_price - position.avg_cost) * abs(delta_amount)
            profit_ratio = (current_price - position.avg_cost) / position.avg_cost * 100
            actual_time = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
            print(f"📊 清仓盈亏 | 时间：{actual_time} | 股票：{security} | 成本：{position.avg_cost:.2f} | 卖出价：{current_price:.2f} | "
                  f"数量：{abs(delta_amount)} | 盈亏金额：{profit_amount:.2f}元 | 盈亏比：{profit_ratio:.2f}%")
        return order_id
    return None

################################### 新增：计算昨日涨停股票数量 #############################################
def get_yesterday_zt_count(context):
    """计算昨日全市场涨停股票数量"""
    # 获取昨日日期
    yesterday = context.previous_date
    
    # 获取全市场A股
    all_stocks = get_all_securities('stock', yesterday).index.tolist()
    
    # 过滤ST、退市、停牌股票
    current_data = get_current_data()
    valid_stocks = [s for s in all_stocks if not (
        current_data[s].is_st or current_data[s].paused or '退' in current_data[s].name
    )]
    
    # 获取昨日价格数据
    price_data = get_price(
        valid_stocks, end_date=yesterday, frequency='daily',
        fields=['close', 'high_limit', 'paused'], count=1,
        panel=False, fill_paused=False, skip_paused=True
    )
    
    # 统计涨停股票数量
    zt_count = 0
    zt_stocks = []
    for code, group in price_data.groupby('code'):
        if len(group) == 1:
            row = group.iloc[0]
            if row['close'] == row['high_limit'] and row['paused'] == 0:
                zt_count += 1
                zt_stocks.append(code)
    
    print(f"📊 昨日({yesterday})涨停统计 | 总涨停数：{zt_count} | 阈值范围：{g_zt_count_min}-{g_zt_count_max}")
    if zt_count > 0:
        print(f"   涨停股票示例：{zt_stocks[:10]}...")  # 仅打印前10个
    
    return zt_count

def check_zt_count_condition(context):
    """检查昨日涨停数量是否在指定范围内"""
    zt_count = get_yesterday_zt_count(context)
    condition_met = g_zt_count_min <= zt_count <= g_zt_count_max
    
    if condition_met:
        print(f"✅ 涨停数量条件满足（{zt_count}），今日正常交易")
        g.zt_count_condition_met = True
    else:
        print(f"❌ 涨停数量条件不满足（{zt_count}），今日暂停建仓")
        g.zt_count_condition_met = False
    
    return condition_met

################################### 初始化设置 #############################################
def initialize(context):
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    set_option('avoid_future_data', True)
    
    # 交易成本配置
    set_slippage(FixedSlippage(3/1000))
    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0.001, open_commission=3/10000,
            close_commission=3/10000, close_today_commission=0, min_commission=5
        ), 
        type='stock'
    )
    
    set_option("match_by_signal", True)
    g.stock_num=3  # 持仓数量上限
    g.min_order_amount = 1000     # 最小委托金额
    g.bought_stocks = {}  # 记录买入股票：{code: buy_date}
    g.bought_today = set()  # 记录当日已委托的股票
    g.intraday_high = {}  # 实时更新个股当日盘中最高价

    # 初始化存储
    g.closed_positions = {}
    g.daily_holdings = {}
    g.last_sell_trigger = ""
    # 新增：标记当日是否已打印高开排序日志
    g.has_printed_high_open_log = False
    
    # 新增回撤控制相关变量
    g.account_high_watermark = context.portfolio.total_value  # 账户最高水位
    g.in_cool_down = False  # 是否处于冷却期
    g.cool_down_remaining_days = 0  # 冷却期剩余天数
    g.pending_sell_stocks = set()  # 因涨跌停未卖出的股票
    
    # 新增：涨停数量条件标记
    g.zt_count_condition_met = False
    
    # 重新规划定时任务
    after_code_changed(context)

################################### 新增高开比例计算与排序函数（含异常值过滤+日志频率控制） #############################################
def get_stocks_sorted_by_high_open(context, stock_list, need_print_log):
    """计算候选股票高开比例，过滤异常值后按高开比例从低到高排序，仅在need_print_log=True时打印日志"""
    current_data = get_current_data()
    valid_stocks = []
    filtered_stocks = []  # 记录被过滤的股票
    
    for s in stock_list:
        # 基础数据有效性校验
        high_limit = current_data[s].high_limit
        day_open = current_data[s].day_open
        if day_open == 0 or high_limit == 0:
            filtered_stocks.append((s, "无效价格（开盘价/涨停价为0）"))
            continue
        
        # 计算高开比例
        yesterday_close = high_limit / 1.1  # 涨停价=昨日收盘价*1.1
        high_open_ratio = (day_open - yesterday_close) / yesterday_close
        
        # 异常值过滤
        if np.isnan(high_open_ratio) or np.isinf(high_open_ratio):
            filtered_stocks.append((s, f"高开比例无效（{high_open_ratio}）"))
            continue
        if high_open_ratio < g_high_open_min:
            filtered_stocks.append((s, f"低开/平开（高开比例{high_open_ratio:.2%} < {g_high_open_min:.2%}）"))
            continue
        if high_open_ratio > g_high_open_max:
            filtered_stocks.append((s, f"极端高开（高开比例{high_open_ratio:.2%} > {g_high_open_max:.2%}）"))
            continue
        
        # 过滤后保留有效股票
        valid_stocks.append((s, high_open_ratio))
    
    # 仅在需要时打印过滤和排序日志
    if need_print_log:
        if filtered_stocks:
            print(f"❌ 高开比例异常过滤列表：")
            for code, reason in filtered_stocks:
                print(f"   {code}({current_data[code].name if code in current_data else '未知'}) | 原因：{reason}")
        
        # 打印排序结果
        print(f"\n📊 候选池按高开比例排序结果（已过滤异常值）：")
        if valid_stocks:
            for code, ratio in valid_stocks:
                print(f"   {code}({current_data[code].name}) | 高开比例：{ratio:.2%}")
        else:
            print(f"   无有效候选股票")
    
    # 按高开比例升序排序（从低到高）
    valid_stocks.sort(key=lambda x: x[1])
    # 提取排序后的股票代码
    sorted_codes = [stock[0] for stock in valid_stocks]
    return sorted_codes

################################### 核心买入逻辑（添加涨停数量判断） #############################################
def buy_logic(context):
    """分钟级买入逻辑：按高开比例从低到高建仓，仅保留委托日志"""
    # 冷却期内禁止买入
    if g.in_cool_down:
        return
    
    # 新增：涨停数量条件不满足则禁止买入
    if not g.zt_count_condition_met:
        return
    
    current_data = get_current_data()
    today_date = context.current_dt.date()
    
    # 1. 持仓已满则直接返回（基础判断）
    remaining_pos = g.stock_num - len(context.portfolio.positions)
    if remaining_pos <= 0:
        return
    
    # 2. 校验买入时间窗口
    time_now = context.current_dt.strftime('%H:%M:%S')
    if time_now >= g_buy_window_end or time_now < g_buy_window_start:
        return
    
    # 3. 判断是否需要打印高开排序日志（仅当日首次执行时打印）
    need_print = not g.has_printed_high_open_log
    # 执行排序（含过滤）
    sorted_jianting = get_stocks_sorted_by_high_open(context, g.jianting, need_print)
    
    # 首次打印后标记为已打印，后续不再输出冗余日志
    if need_print:
        print(f"\n📌 当日二连板候选池（原始）：{g.jianting} | 数量：{len(g.jianting)}")
        print(f"📌 排序后候选池（高开从低到高+异常过滤）：{sorted_jianting} | 数量：{len(sorted_jianting)}")
        g.has_printed_high_open_log = True
    
    # 遍历排序后的候选池股票
    for s in sorted_jianting:
        # 跳过已委托/已持仓/当日买入的股票
        if s in g.bought_today or s in context.portfolio.positions or (s in g.bought_stocks and g.bought_stocks[s] == today_date):
            continue
        
        # 再次校验剩余仓位（关键修复：避免循环中仓位被填满导致除零）
        remaining_pos = g.stock_num - len(context.portfolio.positions)
        if remaining_pos <= 0:
            break
        
        # 获取基础数据
        high_limit = current_data[s].high_limit  # 当日涨停价
        day_open = current_data[s].day_open      # 当日开盘价
        # 获取最新分钟价
        min_data = get_price(s, end_date=context.current_dt, frequency='1m', count=1, fields=['close'])
        if min_data.empty:
            continue
        current_price = min_data['close'].iloc[0]

        # 更新盘中最高价
        if s in g.intraday_high:
            g.intraday_high[s] = max(g.intraday_high[s], current_price)
        else:
            g.intraday_high[s] = current_price

        # 1. 距离涨停价≥3%（放宽后）
        price_gap_ratio = (high_limit - current_price) / high_limit
        if price_gap_ratio < g_buy_price_threshold:
            continue
        
        # 2. 高开≥3%（放宽后）
        yesterday_close = high_limit / 1.1  # 涨停价=昨日收盘价×1.1
        if day_open == 0 or yesterday_close == 0:
            continue
        high_open_ratio = (day_open - yesterday_close) / yesterday_close
        if high_open_ratio < g_high_open_threshold:
            continue
        
        # 3. 价格未回落（放宽：允许1%以内回落）
        if current_price < day_open * 0.99:
            continue
        
        # 计算买入金额（增加剩余仓位非零校验）
        if remaining_pos <= 0:
            continue
        target_value = context.portfolio.available_cash / remaining_pos
        
        # 过滤最小金额和1手限制
        if target_value < g.min_order_amount or (target_value / current_price) < 100:
            continue
        
        try:
            # 限价委托
            order_price = min(current_price + 0.01, high_limit - 0.01)
            order_quantity = int(target_value / order_price // 100 * 100)
            if order_quantity < 100:
                continue
            
            # 委托买入
            order_id = order(s, order_quantity)
            if order_id:
                g.bought_today.add(s)
                g.bought_stocks[s] = today_date
                print(f"✅ 委托买入 {current_data[s].name}({s}) | 委托价：{order_price:.2f} | 数量：{order_quantity} | "
                      f"距离涨停：{price_gap_ratio:.2%} | 高开幅度：{high_open_ratio:.2%}")
        
        except Exception as e:
            print(f"❌ 买入{s}失败：{str(e)}")
            continue

################################### 新增回撤控制核心逻辑 #############################################
def check_account_drawdown(context):
    """检查账户回撤，达到6%则强制清仓"""
    # 冷却期内跳过检查
    if g.in_cool_down:
        return
    
    current_total_value = context.portfolio.total_value
    # 更新账户最高水位
    if current_total_value > g.account_high_watermark:
        g.account_high_watermark = current_total_value
        print(f"📈 更新账户最高水位：{g.account_high_watermark:.2f}元")
    
    # 计算当前回撤比例
    drawdown_ratio = (g.account_high_watermark - current_total_value) / g.account_high_watermark
    print(f"📊 账户回撤检查 | 当前总资产：{current_total_value:.2f} | 最高水位：{g.account_high_watermark:.2f} | 回撤比例：{drawdown_ratio:.2%}")
    
    # 回撤达到6%触发强制清仓
    if drawdown_ratio >= g_max_drawdown:
        print(f"⚠️ 账户回撤达到{drawdown_ratio:.2%}（超过{g_max_drawdown:.2%}阈值），触发强制清仓！")
        force_clear_all_positions(context)
        # 启动冷却期
        start_cool_down(context)

def force_clear_all_positions(context):
    """强制清空所有持仓（处理涨跌停情况）"""
    current_data = get_current_data()
    actual_time = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    g.pending_sell_stocks.clear()
    
    for s in list(context.portfolio.positions):
        pos = context.portfolio.positions[s]
        if pos.closeable_amount == 0:
            continue
        
        high_limit = current_data[s].high_limit
        low_limit = current_data[s].low_limit
        min_data = get_price(s, end_date=context.current_dt, frequency='1m', count=1, fields=['close'])
        if min_data.empty:
            continue
        current_price = min_data['close'].iloc[0]
        
        # 尝试卖出
        try:
            # 涨停/跌停无法卖出，加入待卖出列表
            if current_price >= high_limit or current_price <= low_limit:
                g.pending_sell_stocks.add(s)
                print(f"🔒 {actual_time} 股票{s}处于涨跌停状态（现价：{current_price:.2f} 涨停：{high_limit:.2f} 跌停：{low_limit:.2f}），暂无法卖出，加入待卖出列表")
                continue
            
            # 正常卖出
            order_target_percent(s, 0)
            print(f"🔴 {actual_time} 回撤强制清仓 | 股票：{s} | 现价：{current_price:.2f}")
        except Exception as e:
            g.pending_sell_stocks.add(s)
            print(f"❌ {actual_time} 清仓{s}失败：{str(e)}，加入待卖出列表")

def monitor_pending_sell_stocks(context):
    """监控待卖出股票，开板后立即卖出"""
    if not g.pending_sell_stocks or g.in_cool_down:
        return
    
    current_data = get_current_data()
    actual_time = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    to_remove = []
    
    for s in g.pending_sell_stocks:
        if s not in context.portfolio.positions:
            to_remove.append(s)
            continue
        
        high_limit = current_data[s].high_limit
        low_limit = current_data[s].low_limit
        min_data = get_price(s, end_date=context.current_dt, frequency='1m', count=1, fields=['close'])
        if min_data.empty:
            continue
        current_price = min_data['close'].iloc[0]
        
        # 开板，尝试卖出
        if current_price < high_limit and current_price > low_limit:
            try:
                order_target_percent(s, 0)
                print(f"🟢 {actual_time} 股票{s}开板（现价：{current_price:.2f}），执行清仓 | 涨停：{high_limit:.2f} 跌停：{low_limit:.2f}")
                to_remove.append(s)
            except Exception as e:
                print(f"❌ {actual_time} 开板后清仓{s}失败：{str(e)}")
    
    # 移除已卖出的股票
    for s in to_remove:
        g.pending_sell_stocks.discard(s)

def start_cool_down(context):
    """启动冷却期"""
    g.in_cool_down = True
    g.cool_down_remaining_days = g_cool_down_days
    print(f"⏳ 进入冷却期，剩余{g.cool_down_remaining_days}个交易日")

def update_cool_down_status(context):
    """每日更新冷却期状态"""
    if g.in_cool_down:
        g.cool_down_remaining_days -= 1
        print(f"📅 冷却期剩余天数：{g.cool_down_remaining_days}")
        if g.cool_down_remaining_days <= 0:
            g.in_cool_down = False
            g.pending_sell_stocks.clear()
            # 重置最高水位为当前资产
            g.account_high_watermark = context.portfolio.total_value
            print(f"✅ 冷却期结束，恢复正常交易 | 当前账户最高水位重置为：{g.account_high_watermark:.2f}元")

################################### 时间工具函数 #############################################
def generate_check_times(start_time, end_time, interval):
    """生成自定义的检查时间列表"""
    check_times = []
    start_h, start_m = map(int, start_time.split(":"))
    end_h, end_m = map(int, end_time.split(":"))
    
    current_h, current_m = start_h, start_m
    while True:
        time_str = f"{current_h:02d}:{current_m:02d}"
        check_times.append(time_str)
        
        if current_h > end_h or (current_h == end_h and current_m >= end_m):
            break
        
        current_m += interval
        if current_m >= 60:
            current_h += 1
            current_m -= 60
    
    return check_times

################################### 定时任务（新增涨停数量检查） #############################################
def after_code_changed(context):
    """重新规划定时任务"""
    unschedule_all()
    
    # 基础任务
    run_daily(pre, '09:28')          
    # 新增：9:25检查昨日涨停数量
    run_daily(check_zt_count_condition, '09:25', reference_security='000300.XSHG')
    run_daily(cancel_unfilled_orders, '14:55', reference_security='000300.XSHG')
    run_daily(print_daily_holdings, '15:10', reference_security='000300.XSHG')
    run_daily(reset_daily_data, '15:30', reference_security='000300.XSHG')
    run_daily(force_sell_at_1450, '14:50', reference_security='000300.XSHG')
    # 新增冷却期每日更新
    run_daily(update_cool_down_status, '09:00', reference_security='000300.XSHG')
    
    # 买入任务：9:40-10:10每分钟执行一次
    for minute in range(40, 70):  # 9:40到10:10共30分钟
        if minute < 60:
            run_daily(buy_logic, f'09:{minute:02d}', reference_security='000300.XSHG')
        else:
            run_daily(buy_logic, f'10:{minute-60:02d}', reference_security='000300.XSHG')
    
    # 生成卖出检查时间
    check_times = generate_check_times(g_check_start_time, g_check_end_time, g_check_interval)
    print(f"📅 今日非涨停检查时间：{check_times}")
    
    # 注册卖出检查点
    for check_time in check_times:
        run_daily(sell_if_not_zt, check_time, reference_security='000300.XSHG')
    
    # 注册回撤检查任务（10:00和14:00）
    for check_time in g_drawdown_check_times:
        run_daily(check_account_drawdown, check_time, reference_security='000300.XSHG')
    
    # 注册待卖出股票监控（每分钟执行）
    for minute in range(0, 60):
        run_daily(monitor_pending_sell_stocks, f'09:{minute:02d}', reference_security='000300.XSHG')
        run_daily(monitor_pending_sell_stocks, f'10:{minute:02d}', reference_security='000300.XSHG')
        run_daily(monitor_pending_sell_stocks, f'11:{minute:02d}', reference_security='000300.XSHG')
        run_daily(monitor_pending_sell_stocks, f'13:{minute:02d}', reference_security='000300.XSHG')
        run_daily(monitor_pending_sell_stocks, f'14:{minute:02d}', reference_security='000300.XSHG')

################################### 核心卖出逻辑 #############################################
def sell_if_not_zt(context):
    """10:05-14:45 每5分钟执行：非涨停的可卖持仓立即卖出"""
    # 冷却期内强制清仓优先级最高，跳过常规卖出逻辑
    if g.in_cool_down:
        return
    
    current_data = get_current_data()
    actual_time = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    today_date = context.current_dt.date()
    
    for s in list(context.portfolio.positions):
        pos = context.portfolio.positions[s]
        if pos.closeable_amount == 0 or (s in g.bought_stocks and g.bought_stocks[s] == today_date):
            continue
        
        high_limit = current_data[s].high_limit
        min_data = get_price(s, end_date=context.current_dt, frequency='1m', count=1, fields=['close'])
        if min_data.empty:
            continue
        current_price = min_data['close'].iloc[0]
        
        if current_price < high_limit:
            order_target_percent(s, 0)
            print(f"⚠️ {actual_time} 非涨停卖出 | 股票：{s} | 现价：{current_price:.2f} | 涨停价：{high_limit:.2f}")
        else:
            print(f"✅ {actual_time} 持仓 {s} | 状态：涨停")

def force_sell_at_1450(context):
    """14:50兜底清仓"""
    # 冷却期内强制清仓
    if g.in_cool_down:
        force_clear_all_positions(context)
        return
    
    current_data = get_current_data()
    actual_time = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    today_date = context.current_dt.date()
    
    for s in list(context.portfolio.positions):
        pos = context.portfolio.positions[s]
        if pos.closeable_amount == 0 or (s in g.bought_stocks and g.bought_stocks[s] == today_date):
            continue
        
        high_limit = current_data[s].high_limit
        min_data = get_price(s, end_date=context.current_dt, frequency='1m', count=1, fields=['close'])
        if min_data.empty:
            continue
        current_price = min_data['close'].iloc[0]
        
        if current_price == high_limit:
            print(f"🔴 {actual_time} 股票{s}涨停，跳过兜底清仓")
            continue
        
        order_target_percent(s, 0)
        print(f"📌 {actual_time} 14:50兜底清仓 | 股票：{s} | 现价：{current_price:.2f}")

################################### 核心选股逻辑（取消市值过滤） #############################################
def get_2_lianban_stock(stock_list, end_date):
    """筛选连续两天涨停的股票"""
    if not stock_list:
        return []
    price_data = get_price(
        stock_list, end_date=end_date, frequency='daily',
        fields=['close', 'high_limit', 'paused'], count=2,
        panel=False, fill_paused=False, skip_paused=True
    )
    zt_stocks = []
    for code, group in price_data.groupby('code'):
        if len(group) != 2:
            continue
        group = group.sort_values('time')
        day1_zt = (group.iloc[0]['close'] == group.iloc[0]['high_limit']) and (group.iloc[0]['paused'] == 0)
        day2_zt = (group.iloc[1]['close'] == group.iloc[1]['high_limit']) and (group.iloc[1]['paused'] == 0)
        if day1_zt and day2_zt:
            zt_stocks.append(code)
    return zt_stocks

def pre(context):
    """初始化当日盯盘"""
    g.bought_today = set()
    g.intraday_high = {}
    # 冷却期内跳过选股
    if not g.in_cool_down:
        # 新增：如果涨停数量条件不满足，不选股
        if g.zt_count_condition_met:
            g.jianting = prepare_stock_list(context)
        else:
            g.jianting = []
            print(f"⏳ 涨停数量条件不满足，今日不选股")
    else:
        g.jianting = []
        print(f"⏳ 冷却期内，今日不选股")
    
    today_date = context.current_dt.strftime("%Y-%m-%d")
    g.daily_holdings[today_date] = {'holdings': {}, 'total_profit': 0, 'total_value': 0}
    # 每日重置高开日志打印标记
    g.has_printed_high_open_log = False

def prepare_stock_list(context):
    """核心选股逻辑：仅保留二连板 + ST/停牌过滤（取消市值过滤）"""
    today = context.current_dt.date()
    yesterday = context.previous_date
    
    # 1. 全市场A股基础池
    initial_list = get_all_securities('stock', yesterday).index.tolist()
    
    # 2. 基础过滤：仅保留ST/停牌/退市过滤（必要过滤）
    current_data = get_current_data()
    initial_list = [s for s in initial_list if not (
        current_data[s].is_st or current_data[s].paused or '退' in current_data[s].name
    )]
    
    # 3. 筛选二连板股票（核心逻辑，无市值过滤）
    initial_list = get_2_lianban_stock(initial_list, yesterday)
    print(f"📈 当日二连板股票数量：{len(initial_list)}")
    
    return initial_list

################################### 基础辅助函数 #############################################
def print_daily_holdings(context):
    """持仓汇总"""
    today_date = context.current_dt.strftime("%Y-%m-%d")
    current_data = get_current_data()
    holdings_detail = []
    total_hold_value = 0
    total_float_profit = 0
    total_cost = 0
    
    for s in context.portfolio.positions:
        pos = context.portfolio.positions[s]
        min_data = get_price(s, end_date=context.current_dt, frequency='1m', count=1, fields=['close'])
        if min_data.empty:
            continue
        current_price = min_data['close'].iloc[0]
        
        stock_cost = pos.avg_cost * pos.total_amount
        stock_value = current_price * pos.total_amount
        float_profit = stock_value - stock_cost
        float_profit_ratio = (current_price - pos.avg_cost) / pos.avg_cost * 100
        
        total_cost += stock_cost
        total_hold_value += stock_value
        total_float_profit += float_profit
        
        holdings_detail.append({
            'code': s,
            'name': current_data[s].name,
            'quantity': pos.total_amount,
            'avg_cost': pos.avg_cost,
            'current_price': current_price,
            'float_profit': float_profit,
            'float_profit_ratio': float_profit_ratio,
            'stock_value': stock_value
        })
    
    g.daily_holdings[today_date] = {
        'holdings': holdings_detail,
        'total_cost': total_cost,
        'total_hold_value': total_hold_value,
        'total_float_profit': total_float_profit,
        'total_float_profit_ratio': (total_float_profit / total_cost * 100) if total_cost > 0 else 0,
        'cash': context.portfolio.available_cash,
        'total_asset': context.portfolio.total_value,
        'in_cool_down': g.in_cool_down,
        'cool_down_remaining': g.cool_down_remaining_days,
        'zt_count_condition_met': g.zt_count_condition_met
    }
    
    # 打印核心汇总
    print(f"\n📋 【{today_date} 持仓汇总】")
    print(f"总资产：{context.portfolio.total_value:.2f}元 | 可用现金：{context.portfolio.available_cash:.2f}元")
    print(f"持仓总成本：{total_cost:.2f}元 | 持仓总市值：{total_hold_value:.2f}元")
    print(f"总浮动盈亏：{total_float_profit:.2f}元 | 总浮动盈亏比：{total_float_profit/total_cost*100:.2f}%" if total_cost>0 else "总浮动盈亏：0元 | 总浮动盈亏比：0%")
    print(f"冷却期状态：{'冷却中（剩余'+str(g.cool_down_remaining_days)+'天）' if g.in_cool_down else '正常交易'}")
    print(f"涨停数量条件：{'满足' if g.zt_count_condition_met else '不满足'}")
    if g.pending_sell_stocks:
        print(f"待卖出股票：{list(g.pending_sell_stocks)}")
    
    if holdings_detail:
        print("\n📈 【持仓个股利润明细】")
        for stock in holdings_detail:
            print(f"股票：{stock['name']}({stock['code']}) | 持仓数量：{stock['quantity']} | "
                  f"成本：{stock['avg_cost']:.2f} | 现价：{stock['current_price']:.2f} | "
                  f"浮动盈亏：{stock['float_profit']:.2f}元 | 盈亏比：{stock['float_profit_ratio']:.2f}%")

def cancel_unfilled_orders(context):
    """撤单逻辑"""
    # 冷却期内撤销所有未成交委托
    if g.in_cool_down:
        orders = get_orders()
        for order_id, order_detail in orders.items():
            if order_detail.status in ['submitted', 'pending']:
                cancel_order(order_id)
                print(f"🔴 冷却期撤销未成交委托 | 股票：{order_detail.security} | 委托价：{order_detail.price:.2f} | 数量：{order_detail.amount}")
        return
    
    # 涨停数量条件不满足时也撤销所有未成交委托
    if not g.zt_count_condition_met:
        orders = get_orders()
        for order_id, order_detail in orders.items():
            if order_detail.status in ['submitted', 'pending']:
                cancel_order(order_id)
                print(f"🔴 涨停数量条件不满足，撤销未成交委托 | 股票：{order_detail.security} | 委托价：{order_detail.price:.2f} | 数量：{order_detail.amount}")
        return
    
    orders = get_orders()
    for order_id, order_detail in orders.items():
        if order_detail.status in ['submitted', 'pending'] and order_detail.security in g.bought_today:
            cancel_order(order_id)
            print(f"🔄 {context.current_dt.strftime('%Y-%m-%d %H:%M:%S')} 撤单 {order_detail.security} | 委托价：{order_detail.price:.2f} | 数量：{order_detail.amount}")

def reset_daily_data(context):
    """数据重置"""
    g.bought_today = set()
    g.intraday_high = {}
    g.last_sell_trigger = ""
    # 每日重置涨停数量条件标记
    g.zt_count_condition_met = False

def get_current_context():
    """兼容函数"""
    import inspect
    frame = inspect.currentframe()
    try:
        while frame:
            if 'context' in frame.f_locals:
                return frame.f_locals['context']
            frame = frame.f_back
    finally:
        del frame
    return None