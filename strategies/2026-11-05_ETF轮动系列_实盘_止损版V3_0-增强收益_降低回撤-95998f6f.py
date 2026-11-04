# Clone from JoinQuant
# postId: 95998f6fcdd14f296dfa584b266640be
# backtestId: b90987b305433507c5d1065178d16773
# title: 【ETF轮动系列】【实盘】止损版V3.0-增强收益/降低回撤

# 风险及免责提示：该策略由聚宽用户在聚宽社区分享，仅供学习交流使用。
# 原文一般包含策略说明，如有疑问请到原文和作者交流讨论。
# 原文网址：https://www.joinquant.com/post/42673
# 标题：【回顾3】ETF策略之核心资产轮动
# 作者：wywy1995

import numpy as np
import pandas as pd


#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 设置滑点 https://www.joinquant.com/view/community/detail/a31a822d1cfa7e83b1dda228d4562a70
    set_slippage(FixedSlippage(0.000))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0, min_commission=5), type='fund')
    # 过滤一定级别的日志
    log.set_level('system', 'error')
    # 参数
    g.etf_pool = [
        '159915.XSHE', # 创业板100
        '518880.XSHG', #黄金ETF（大宗商品）
        '513100.XSHG',   #纳指100（海外资产）
        '510180.XSHG', # 上证180
    ]
    g.target_num = 1 #持股数量
    g.m_days = 25    #动量参考天数
    g.down = -2      #下跌2个点视为暴跌
    g.up = 2         #累计上涨2个点视为恢复
    g.fall = -4      #暴跌阈值
    
    g.daily_returns_cache = {} #涨跌幅缓存

    run_daily(trade, '10:30') #每天运行确保即时捕捉动量变化
    run_daily(print_summary, '15:30') #每天运行确保即时捕捉动量变化



# 基于年化收益和判定系数打分的动量因子轮动 https://www.joinquant.com/post/26142
def get_rank(etf_pool):
    score_list = []
    for etf in etf_pool:
        df = attribute_history(etf, g.m_days, '1d', ['close'])
        print(df)
        y = df['log'] = np.log(df.close)
        x = df['num'] = np.arange(df.log.size)
        slope, intercept = np.polyfit(x, y, 1)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
        score = annualized_returns * r_squared
        score_list.append(score)
    df = pd.DataFrame(index=etf_pool, data={'score':score_list})
    df = df.sort_values(by='score', ascending=False)
    return df

# 获取当日当时涨幅    
def get_today_raise(security_code):
    yesterday_price = attribute_history(security_code, 1, '1d', ['close'])['close'][0]
    current_price = get_current_data()[security_code].last_price
    delta = (current_price - yesterday_price) / yesterday_price
    return round(delta*100,4)

def check_down(security_code):
    """
    检查指定证券最近连续下跌的累计跌幅（包含今日实时涨幅）
    使用缓存机制，仅首次调用 attribute_history，后续仅更新今日数据

    参数:
        security_code: 证券代码，如 '513500.XSHG'

    返回:
        bool: 累计跌幅是否超过 g.down 阈值
    """

    # 只保留当前 security_code 的缓存，清除其他所有缓存
    current_cache = g.daily_returns_cache.get(security_code, [])
    g.daily_returns_cache = {security_code: current_cache}

    # 如果缓存中没有该证券的历史数据，则初始化历史数据
    if not g.daily_returns_cache[security_code]:
        check_days = g.m_days
        df = attribute_history(security_code, check_days, '1d', ['close'])
        if df.empty:
            print(f"{security_code} 没有历史数据")
            return False

        # 计算每日涨跌幅百分比
        daily_returns = df['close'].pct_change().dropna().tolist()
        daily_returns = [round(x * 100, 4) for x in daily_returns]  # 转换为百分比格式

        # 更新缓存
        g.daily_returns_cache[security_code] = daily_returns

    # 取出已缓存的涨跌幅数据（采用10点半的数据，直接用历史数据效果不佳）
    daily_returns = g.daily_returns_cache[security_code]

    # 获取今日涨跌幅
    today_return_percent = get_today_raise(security_code)
    print(f"{security_code} 今日涨幅: {today_return_percent}%")

    # 构造完整的涨跌幅列表（旧数据 + 今日）
    full_returns = daily_returns + [today_return_percent]

    # 移除最早的一天，保持窗口大小一致
    updated_returns = full_returns[1:]

    # 更新缓存
    g.daily_returns_cache[security_code] = updated_returns

    # 倒序统计连续下跌
    down_days = 0
    total_down = 0.0

    for ret in reversed(updated_returns):
        if ret <= 0.0:  # 小于 0.0% 视为下跌或横盘
            down_days += 1
            total_down += ret
        else:
            break  # 遇到上涨就停止统计

    # 打印调试信息
    if down_days and total_down <= g.down:
        print(f"{security_code} 最近连续 {down_days} 天累计跌幅: {round(total_down, 4)}%")
        return False
    
    if down_days > 3:
        print(f"{security_code} 最近连续 {down_days} 天下跌")
        return False

    # 检查最近两天是否有暴跌（主要看昨天）
    has_big_fall = False
    for ret in updated_returns[-2:]:
        if ret <= g.fall:
            has_big_fall = True
            break
    
    # 检查是否存在暴跌
    if has_big_fall:
        print(f"{security_code} 最近两天存在暴跌: {has_big_fall}")
        return False
            
    return True

# 检查当日涨跌幅度  
def check_price(security_code):
    today_raise = get_today_raise(security_code)
    print(f"{security_code} 今日涨幅: {today_raise}")
    return today_raise > g.down
        
# 交易
def trade(context):
    print(' == '*16)
    # print_summary(context)
    # 获取动量最高的一只ETF
    df = get_rank(g.etf_pool)
    rank_list = list(df.index)    
    print(f"\n{df}")     
    record(黄金 = round(df.loc['518880.XSHG'], 2))
    record(纳指 = round(df.loc['513100.XSHG'], 2))
    record(创业 = round(df.loc['159915.XSHE'], 2))
    record(上证 = round(df.loc['510180.XSHG'], 2))

    target_num = g.target_num
    target_list = rank_list[:target_num] # 先取
    # target_list = [etf for etf in target_list if check_price(etf)] #再筛选
    target_list = [etf for etf in target_list if check_down(etf)] #再筛选
    print(f"cache: {g.daily_returns_cache}")


    # 卖出    
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            print('卖出' + str(etf))
        else:
            print('继续持有' + str(etf))
    # 买入
    hold_list = list(context.portfolio.positions)
    if len(hold_list) < target_num:
        value = context.portfolio.available_cash / (target_num - len(hold_list))
        for etf in target_list:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, value)
                print('买入' + str(etf))

import prettytable  # 新增模块导入
from prettytable import PrettyTable  # 导入prettytable库用于表格打印

def get_security_name(code):
    """获取股票的中文名称"""
    return get_security_info(code).display_name

def print_summary(context):
    """
    打印当前投资组合的总资产和持仓详情。效果大家可以看截图

    参数:
        context: 包含投资组合信息的对象。
        get_current_data: 获取当前市场数据的函数。
    """
    # 获取总资产
    total_value = round(context.portfolio.total_value, 2)

    # 获取当前持仓
    current_stocks = context.portfolio.positions
    if not current_stocks:
        # 如果没有持仓，只显示总资产
        print(f"当前总资产: {total_value}")
        return

    # 创建表格
    table = PrettyTable(["股票代码", "股票名称", "持仓数量", "持仓价格", "当前价格", "盈亏数额", "盈亏比例", "市值"])
    table.hrules = prettytable.ALL  # 显示所有水平线

    # 设置对齐方式
    table.align["股票代码"] = "l"
    table.align["股票名称"] = "l"
    for field in ["持仓数量", "持仓价格", "当前价格", "盈亏数额", "盈亏比例", "市值"]:
        table.align[field] = "r"

    # 遍历持仓股票
    total_market_value = 0  # 总市值（用于累加每只股票的市值）
    for stock in current_stocks:
        current_shares = current_stocks[stock].total_amount  # 持仓数量
        current_price = round(get_current_data()[stock].last_price, 3)  # 当前价格
        avg_cost = round(current_stocks[stock].avg_cost, 3)  # 持仓平均成本

        # 计算盈亏比例
        profit_ratio = (current_price - avg_cost) / avg_cost if avg_cost != 0 else 0
        profit_ratio_percent = f"{profit_ratio * 100:.2f}%"  # 转为百分比并保留两位小数

        # 计算盈亏数额
        profit_amount = round((current_price - avg_cost) * current_shares, 2)

        # 计算市值
        market_value = round(current_shares * current_price, 2)
        total_market_value += market_value  # 累加总市值

        # 处理股票代码：移除后缀
        stock_code = stock.split(".")[0]  # 只保留股票代码部分

        # 添加到表格
        table.add_row([
            stock_code,
            get_security_name(stock),  # 假设 get_security_name 是获取股票名称的函数
            current_shares,
            avg_cost,
            current_price,
            profit_amount,
            profit_ratio_percent,
            market_value
        ])

    # 添加总资产行（单独一行）
    table.add_row(["总市值", "", "", "", "", "", "", f"{total_market_value:.2f}"])
    table.add_row(["总资产", "", "", "", "", "", "", f"{total_value:.2f}"])

    # 打印表格
    print(f'当前总资产\n{table}')
