# Clone from JoinQuant
# postId: 24fd28131501d93817c01d302f306763
# backtestId: 26d52b0437edaa89b3bc43ce09bb8004
# title: 【实用贴】一份对研究行业ETF轮动有帮助的代码

from jqdata import *
import pandas as pd
from datetime import datetime

def initialize(context):
    # 设置基准和交易参数
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, 
                              close_commission=0.0003, min_commission=5), type='stock')
    
    # 设置每日收盘后自动执行日志记录
    run_daily(log_high_volume_funds, time='after_close')

def filter_row(row_text):
    """
    筛选函数：如果行文本包含 'A', '上证', '深证', '债' 中的任意一个，则返回 True (表示需要过滤掉)。
    否则返回 False (表示保留)。
    """
    keywords_to_filter = ['A', '上证', '深证', '债', '30', '50', '100', '300', '500', '1000', '2000']
    for keyword in keywords_to_filter:
        if keyword in row_text:
            return True  # 需要过滤
    return False  # 不需要过滤，保留

def log_high_volume_funds(context):
    """获取当日高成交额ETF和LOF并记录到日志"""
    # 1. 获取高成交额ETF/LOF列表
    high_volume_funds = get_high_volume_funds(context)
    
    # 2. 构建初步的日志行列表
    current_date = context.current_dt.strftime('%Y-%m-%d')
    log_lines = [f"【高成交额ETF/LOF日志】{current_date} - 当日成交金额大于1亿元的ETF/LOF共有{len(high_volume_funds)}只："]
    
    for code, volume in high_volume_funds:
        # 获取基金基本信息
        info = get_security_info(code)
        name = info.display_name
        fund_type = "ETF" if info.type == 'etf' else "LOF"
        
        # 获取上市日期
        listing_date = info.start_date
        # 将 datetime.date 对象转换为 'YYYY-MM-DD' 字符串格式
        listing_date_str = listing_date.strftime('%Y-%m-%d') if isinstance(listing_date, (datetime, pd.Timestamp)) else str(listing_date)
        
        # 格式化日志信息行，包含上市日期
        formatted_line_text = f"'{code}',  # ({name}) [{fund_type}]-成交额：{volume/100000000:.2f}亿元-上市日期：{listing_date_str}"
        log_lines.append(formatted_line_text)
    
    # 3. 应用筛选函数，过滤掉包含关键词的行
    # 保留标题行 (索引为0) 和经过筛选后符合条件的基金行
    filtered_log_lines = [log_lines[0]] + [line for line in log_lines[1:] if not filter_row(line)]

    # 4. 检查筛选后是否还有符合条件的基金信息行
    if len(filtered_log_lines) <= 1: # 只有标题，没有具体内容
        # 如果筛选后没有符合条件的基金，则记录一条提示信息
        log.info(f"【高成交额ETF/LOF日志】{context.current_dt.strftime('%Y-%m-%d')} - 经过筛选后，当日无符合条件的ETF/LOF。")
        return

    # 5. 更新日志标题，反映筛选后的数量
    final_count = len(filtered_log_lines) - 1 # 减去标题行
    filtered_log_lines[0] = f"【高成交额ETF/LOF日志】{context.current_dt.strftime('%Y-%m-%d')} - 经过筛选后，当日成交金额大于1亿元的ETF/LOF共有{final_count}只："

    # 6. 将所有行合并为一个字符串并记录
    full_log_message = "\n".join(filtered_log_lines)
    log.info(full_log_message)


def get_high_volume_funds(context):
    """获取当日成交额大于1亿的ETF和LOF"""
    # 获取所有ETF和LOF列表
    all_fund_types = ['etf', 'lof']
    all_funds = get_all_securities(all_fund_types)
    current_date = context.current_dt.strftime('%Y-%m-%d')
    high_volume_funds = []
    
    # 遍历所有ETF和LOF
    for code in all_funds.index:
        try:
            # 获取当日行情数据
            df = get_price(code, start_date=current_date, end_date=current_date, frequency='daily')
            
            # 检查数据有效性
            if not df.empty:
                volume = df['money'].iloc[0]
                
                # 筛选成交额大于1亿元的基金
                if volume > 100000000:
                    high_volume_funds.append((code, volume))
        except Exception as e:
            # 记录异常但不中断流程
            continue
    
    # 按成交额排序
    high_volume_funds.sort(key=lambda x: x[1], reverse=True)
    return high_volume_funds