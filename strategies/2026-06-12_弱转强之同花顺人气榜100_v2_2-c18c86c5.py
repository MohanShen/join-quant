# Clone from JoinQuant
# postId: c18c86c5b597ce42d64fbc6778abb4d2
# backtestId: d037a5b3aebff3aa964d2a1719e74a96
# title: 弱转强之同花顺人气榜100 v2.2

# test2_modified.py
# 克隆自聚宽文章：https://www.joinquant.com/post/58908
# 标题：ST弱转强策略在主板股票上有效吗？
# 作者：庄庄庄

# 克隆自聚宽文章：https://www.joinquant.com/post/58411
# 标题：ST弱转强V5.1-竞价筛选 20-25年化172 回撤15
# 作者：TUFI

# 克隆自聚宽文章：https://www.joinquant.com/post/58365
# 标题：弱转强V5实盘版本今年85%！！
# 作者：bossquant

from six import BytesIO
import time
import requests
import pandas as pd
import numpy as np
import math
import talib as tl
import datetime as dt
from datetime import datetime
from datetime import timedelta
from jqlib.technical_analysis import *
from jqdata import *
import os
import json

# ==================== 全局模式控制 ====================
# 模式设置: 'backtest' 用于回测, 'realtime' 用于实时模拟
g_mode = 'backtest'  # 可修改为 'backtest' 或 'realtime'

# 实时模拟时是否使用腾讯实时价格
USE_TENCENT_REALTIME_PRICE = True

# 实时模拟时是否追加写入hot100.csv
APPEND_HOT100_TO_CSV = True

# 历史hot100.csv文件路径
HOT100_CSV_PATH = 'hot100.csv'

# 实时追加的hot100_realtime.csv文件路径
HOT100_REALTIME_CSV_PATH = 'hot100_realtime.csv'

#配置钉钉webhook
WEBHOOK_URL = 'https://connector.dingtalk.com/webhook/flow/103125f514df2xxxxxxxxxxdea000e'

# ====================================================

# ==================== 辅助函数 ，回测是读取聚宽文件====================
def read_stock_data(filepath, date_filter=None):
    # 读取数据文件
    df = pd.read_csv(BytesIO(read_file(filepath)))
    # 确保日期列是字符串类型
    df['日期'] = df['日期'].astype(str)
    
    # 如果有日期过滤条件，进行过滤
    if date_filter is not None:
        date_filter = str(date_filter)  # 确保是字符串
        df = df[df['日期'] == date_filter]
    
    return df



#============================新增加钉钉推送接口================================

def send_dingtalk_message(webhook, personal_info):
    """
    发送个人信息到钉钉机器人，可以反生更多信息，买入，卖出，盘后账号信息钉钉，可以资源配置
    :param webhook: 钉钉机器人Webhook地址
    :param personal_info: 要发送的个人信息字典
    """
    # 构造消息内容
    message = {
        "msgtype": "text",
        "text": {
            "content": f"个人信息通知：\n{json.dumps(personal_info, indent=2, ensure_ascii=False)}"
        },
        "at": {
            "isAtAll": False  # 不@所有人，如果需要@特定人，可以设置atMobiles
        }
    }

    # 发送请求
    headers = {'Content-Type': 'application/json'}
    response = requests.post(webhook, headers=headers, data=json.dumps(message))
    if response.status_code != 200:
        raise Exception(f"Failed to send message. Status code: {response.status_code}, Response: {response.text}")

    return response.json()
    
    
# ==================== 辅助函数用于持久化人气榜数据 ====================
def append_hot100_to_csv(hot100_df, filepath=HOT100_REALTIME_CSV_PATH):
    """
    将当日人气榜100数据追加写入CSV文件（聚宽环境专用）
    :param hot100_df: 当日人气榜DataFrame
    :param filepath: CSV文件路径
    """
    if hot100_df is None or hot100_df.empty:
        log.info("【存储】无人气榜数据，跳过写入")
        return False
    
    try:
        from six import BytesIO
        import pandas as pd
        
        # 检查文件是否存在
        file_exists = False
        existing_df = None
        
        try:
            # 尝试读取现有文件
            file_content = read_file(filepath)
            if file_content:
                existing_df = pd.read_csv(BytesIO(file_content))
                file_exists = True
                log.info(f"【存储】文件已存在，当前行数: {len(existing_df)}")
            else:
                log.info("【存储】文件存在但内容为空")
        except Exception as e:
            log.info(f"【存储】文件不存在或读取失败: {e}")
            file_exists = False
        
        # 准备新数据
        new_df = hot100_df.copy()
        
        # 如果文件已存在且有数据，合并去重
        if file_exists and existing_df is not None and len(existing_df) > 0:
            # 合并新旧数据
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            # 去重（基于日期和股票代码）
            combined_df = combined_df.drop_duplicates(subset=['日期', 'stock_code'], keep='last')
            log.info(f"【存储】合并去重后总行数: {len(combined_df)}")
            final_df = combined_df
        else:
            final_df = new_df
            log.info(f"【存储】创建新文件，写入 {len(new_df)} 行数据")
        
        # 将DataFrame转换为CSV字符串
        csv_content = final_df.to_csv(index=False, encoding='utf-8')
        
        # 使用聚宽的write_file写入文件
        write_file(filepath, csv_content)
        
        log.info(f"【存储】成功保存 {len(new_df)} 条新数据到 {filepath}")
        log.info(f"【存储】文件当前总行数: {len(final_df)}")
        
        # 验证写入
        try:
            verify_content = read_file(filepath)
            if verify_content:
                verify_df = pd.read_csv(BytesIO(verify_content))
                log.info(f"【存储】验证成功，文件行数: {len(verify_df)}")
                return True
            else:
                log.info("【存储】警告：写入后文件为空")
                return False
        except Exception as e:
            log.info(f"【存储】验证失败: {e}")
            return False
        
    except Exception as e:
        log.info(f"【存储】写入CSV文件失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# ======================================================================


# 初始化函数
def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.01))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0001, close_commission=0.0001,
                             close_today_commission=0, min_commission=5), type='stock')
    
    # 策略共同的全局变量
    g.no_trading_today_signal = False
    g.yesterday_HL_list = []
    g.strategys = {}
    g.portfolio_value_proportion = [0, 1.0]
    g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}
    g.context = context
    g.hot_concept_data_dict = {}
    g.hot100_today_list = []
    g.dieting = []

    # 初始化腾讯实时数据获取器（仅实时模拟时使用）
    if g_mode == 'realtime':
        g.tencent_fetcher = StockDataFetcher()
        log.info("实时模拟模式已启用，使用腾讯接口获取实时价格")
    else:
        g.tencent_fetcher = None
        log.info("回测模式已启用")

    # 弱转强策略
    if g.portfolio_value_proportion[1] > 0:
        run_daily(prepare_stock_list, time="9:01")
        run_daily(buy_stocks, time="9:30")
        run_daily(sell_stocks, time='11:29')
        run_daily(sell_stocks, time='13:09')
        run_daily(sell_stocks, time='14:47')
        run_daily(sell_stocks, time='14:50')
        run_daily(sell_stocks, time='14:55')


def process_initialize(context):
    print("重启程序")
    g.strategys["热榜100弱转强策略"] = Hot100MainBoardWeakToStrongStrategy(context, index=1, name="热榜100弱转强策略")

def prepare_stock_list(context):g.strategys["热榜100弱转强策略"].get_stock_list(context)
def buy_stocks(context):g.strategys["热榜100弱转强策略"].buy(context)
def sell_stocks(context):g.strategys["热榜100弱转强策略"].sell(context)
def monitor_dieting(context):g.strategys["热榜100弱转强策略"].dieting_monitor(context)


# 添加after_trading_end函数记录每日终值
def after_trading_end(context):
    print("盘后执行")
    #summary_msg = get_portfolio_summary
    #send_dingtalk_message(WEBHOOK_URL, summary_msg)
    
    #输出漂亮的账户信息
    _print_pretty_portfolio_summary(context)

#================================= 组织账户号信息发送钉钉 ===========================================
def get_portfolio_summary(context):

    """盘后记录信息"""
    portfolio_value = context.portfolio.total_value
    if not hasattr(g, 'max_portfolio_value'):
        g.max_portfolio_value = portfolio_value
    else:
        g.max_portfolio_value = max(portfolio_value, g.max_portfolio_value)

    drawdown = portfolio_value / g.max_portfolio_value - 1

    # 生成每日总结消息
    summary_msg = {
        "title": "每日策略总结报告",
        "date": context.current_dt.strftime('%Y-%m-%d'),
        "account_status": {
            "total_value": portfolio_value,
            "positions_value": context.portfolio.positions_value,
            "available_cash": context.portfolio.available_cash,
            "drawdown": drawdown
        },
        "positions": []
    }

    # 持仓详情
    if context.portfolio.positions:
        for stock in context.portfolio.positions:
            position = context.portfolio.positions[stock]
            returns = (position.price / position.avg_cost - 1)
            market_value = position.total_amount * position.price

            summary_msg["positions"].append({
                "stock": stock,
                "total_amount": position.total_amount,
                "avg_cost": position.avg_cost,
                "current_price": position.price,
                "market_value": market_value,
                "returns": returns,
                "market_value_percentage": (market_value / portfolio_value) * 100
            })
    else:
        summary_msg["positions"] = "当前无持仓"

    return summary_msg

#================================ 盘后输出详细持仓信息 ================================================
def _print_pretty_portfolio_summary(context):
    log.info('after_trading_end 被执行 ------------------------------------------------------------')
    """盘后记录信息"""
    
    # 收集所有输出行的列表
    output_lines = []
    
    def add_line(line):
        """添加一行到输出列表"""
        output_lines.append(line)
    
    portfolio_value = context.portfolio.total_value
    if not hasattr(g, 'max_portfolio_value'):
        g.max_portfolio_value = portfolio_value
    else:
        g.max_portfolio_value = max(portfolio_value, g.max_portfolio_value)

    drawdown = (portfolio_value / g.max_portfolio_value - 1) * 100

    # 生成每日总结消息
    summary_msg = {
        "title": "每日策略总结报告",
        "date": context.current_dt.strftime('%Y-%m-%d'),
        "account_status": {
            "total_value": round(portfolio_value, 2),
            "positions_value": round(context.portfolio.positions_value, 2),
            "available_cash": round(context.portfolio.available_cash, 2),
            "drawdown(%)": round(drawdown, 2)
        },
        "strategies": []
    }

    # 遍历子策略，获取各策略的持仓和收益详情
    for strategy_name, strategy in g.strategys.items():
        # 从 g.positions 获取该策略的持仓记录（包含持仓数量）
        strategy_holdings = g.positions.get(strategy.index, {})
        strategy_positions = []
        strategy_total_value = 0
        strategy_total_cost = 0
        
        # 遍历该策略记录的持仓股票
        for stock, strategy_amount in strategy_holdings.items():
            if strategy_amount == 0:
                continue
            
            # 获取该股票的实际持仓（用于获取当前价格、成本价等信息）
            position = context.portfolio.positions.get(stock)
            if position and position.total_amount > 0:
                # 注意：这里使用策略记录的持仓数量，而不是总持仓数量
                # 如果一只股票被多个策略持有，需要按比例分配
                actual_amount = position.total_amount
                
                # 计算该策略持有该股票的比例
                # 如果策略记录的持仓数量与实际持仓不一致，以实际持仓为准并修正
                if strategy_amount != actual_amount:
                    log.warning(f"策略 {strategy_name} 股票 {stock} 持仓数量不一致: 记录={strategy_amount}, 实际={actual_amount}")
                    # 使用实际持仓数量，但记录到策略中（可能是其他策略也持有了同一只股票）
                    # 这里我们仍然使用策略记录的持仓数量，因为这是该策略应该持有的份额
                    amount_to_use = strategy_amount
                else:
                    amount_to_use = strategy_amount
                
                # 计算该策略持有部分的市场价值
                market_value = amount_to_use * position.price
                cost_value = amount_to_use * position.avg_cost
                ret_pct = (position.price / position.avg_cost - 1) * 100
                
                strategy_total_value += market_value
                strategy_total_cost += cost_value
                
                strategy_positions.append({
                    "stock": stock,
                    "amount": int(amount_to_use),                      # 策略持股数量
                    "total_amount": int(actual_amount),               # 总持股数量（多策略合计）
                    "avg_cost": round(position.avg_cost, 2),          # 成本价
                    "current_price": round(position.price, 2),        # 现价
                    "market_value": round(market_value, 2),           # 策略持仓市值
                    "returns(%)": round(ret_pct, 2)                   # 收益率
                })
        
        strategy_ret = ((strategy_total_value / strategy_total_cost) - 1) * 100 if strategy_total_cost > 0 else 0
        summary_msg["strategies"].append({
            "name": strategy_name,
            "stock_count": len(strategy_positions),
            "total_value": round(strategy_total_value, 2),
            "total_cost": round(strategy_total_cost, 2),
            "returns(%)": round(strategy_ret, 2),
            "positions": strategy_positions if strategy_positions else []
        })

    # 收集所有输出内容
    add_line("\n" + "=" * 100)
    add_line(f"  📊 策略总结报告 - {summary_msg['date']}".center(100))
    add_line("=" * 100)
    
    # 账户总览
    status = summary_msg["account_status"]
    add_line(f"\n  💰 账户总览:")
    add_line(f"   总资产: {status['total_value']:>12,.2f} 元")
    add_line(f"   持仓市值: {status['positions_value']:>10,.2f} 元")
    add_line(f"   可用现金: {status['available_cash']:>10,.2f} 元")
    add_line(f"   总市值回撤: {status['drawdown(%)']:>10,.2f} %")
    
    # 子策略详情
    add_line(f"\n  📈 子策略详情:")
    add_line("-" * 100)
    
    for strat in summary_msg["strategies"]:
        add_line(f"\n    🎯 {strat['name']}")
        add_line(f"     持仓数量: {strat['stock_count']} 只")
        add_line(f"     持仓成本: {strat['total_cost']:>10,.2f} 元")
        add_line(f"     持仓市值: {strat['total_value']:>10,.2f} 元")
        
        # 盈亏显示带颜色标记
        profit = strat['total_value'] - strat['total_cost']
        profit_icon = "📈" if profit >= 0 else "📉"
        add_line(f"     浮动盈亏: {profit_icon} {profit:>+10,.2f} 元  ({strat['returns(%)']:>+6.2f} %)")
        
        if strat['positions']:
            # 扩展表格字段
            schema = ["股票代码", "持股数量", "成本价", "现价", "持仓市值", "收益率%", "盈亏金额"]
            data = []
            for pos in strat['positions']:
                stock_profit = pos['market_value'] - (pos['amount'] * pos['avg_cost'])
                data.append([
                    pos['stock'],
                    pos['amount'],
                    pos['avg_cost'],
                    pos['current_price'],
                    pos['market_value'],
                    pos['returns(%)'],
                    round(stock_profit, 2)
                ])
            
            add_line(f"\n     持仓明细:")
            _print_pretty_table(data, schema, output_lines=output_lines)
            
            # 打印策略汇总行
            add_line(f"\n     策略汇总: 持仓{strat['stock_count']}只 | 总成本{strat['total_cost']:>10,.2f} | 总市值{strat['total_value']:>10,.2f} | 收益{strat['returns(%)']:>+6.2f}%")
        else:
            add_line(f"     持仓明细: 无")
    
    # 全市场持仓汇总表（显示实际总持仓）
    all_positions = []
    for stock, position in context.portfolio.positions.items():
        if position and position.total_amount > 0:
            market_value = position.total_amount * position.price
            ret_pct = (position.price / position.avg_cost - 1) * 100
            stock_profit = market_value - (position.total_amount * position.avg_cost)
            position_ratio = (market_value / portfolio_value) * 100 if portfolio_value > 0 else 0
            
            # 找出哪些策略持有了这只股票
            owned_by_strategies = []
            for strategy_name, strategy in g.strategys.items():
                strategy_holdings = g.positions.get(strategy.index, {})
                if stock in strategy_holdings and strategy_holdings[stock] > 0:
                    owned_by_strategies.append(f"{strategy_name}({strategy_holdings[stock]}股)")
            
            all_positions.append({
                "stock": stock,
                "amount": int(position.total_amount),
                "avg_cost": round(position.avg_cost, 2),
                "current_price": round(position.price, 2),
                "market_value": round(market_value, 2),
                "returns(%)": round(ret_pct, 2),
                "profit": round(stock_profit, 2),
                "position_ratio": round(position_ratio, 2),
                "owned_by": ", ".join(owned_by_strategies) if owned_by_strategies else "未分配"
            })
    
    if all_positions:
        add_line(f"\n  📋 全市场持仓汇总 (按市值排序):")
        all_positions_sorted = sorted(all_positions, key=lambda x: x['market_value'], reverse=True)
        
        # 显示更多信息，包括持有该股票的策略
        schema_all = ["股票代码", "持股数量", "成本价", "现价", "持仓市值", "收益率%", "盈亏金额", "仓位占比%", "所属策略"]
        data_all = []
        for pos in all_positions_sorted:
            data_all.append([
                pos['stock'],
                pos['amount'],
                pos['avg_cost'],
                pos['current_price'],
                pos['market_value'],
                pos['returns(%)'],
                pos['profit'],
                pos['position_ratio'],
                pos['owned_by']
            ])
        _print_pretty_table(data_all, schema_all, output_lines=output_lines)
        
        # 全市场汇总统计
        total_profit = portfolio_value - (context.portfolio.available_cash + sum(p['amount'] * p['avg_cost'] for p in all_positions))
        add_line(f"\n📊 全市场汇总: 总资产{portfolio_value:>12,.2f} | 总市值{status['positions_value']:>10,.2f} | 现金{status['available_cash']:>10,.2f} | 总盈亏{total_profit:>+10,.2f}")
    
    add_line("\n" + "=" * 100)
    
    # 一次性输出所有内容
    output_str = "\n".join(output_lines)
    print(output_str) #输出账号完整信息

#================================ 日志辅助函数 ================================================
def _print_pretty_table(data, schema, output_lines=None):
    """
    打印漂亮表格
    参数:
        data: 表格数据
        schema: 表头
        output_lines: 用于收集输出行的列表
    """
    if not data:
        return
    
    def get_display_width(text):
        """计算字符串显示宽度（中文占2，英文占1）"""
        width = 0
        for ch in str(text):
            if '\u4e00' <= ch <= '\u9fff':
                width += 2
            else:
                width += 1
        return width
    
    def pad_string(text, width, align='left'):
        """根据显示宽度进行填充对齐"""
        text = str(text)
        current_width = get_display_width(text)
        padding = width - current_width
        if padding <= 0:
            return text
        if align == 'left':
            return text + ' ' * padding
        elif align == 'right':
            return ' ' * padding + text
        else:
            left_pad = padding // 2
            right_pad = padding - left_pad
            return ' ' * left_pad + text + ' ' * right_pad
    
    def add_line(line):
        if output_lines is not None:
            output_lines.append(line)
        else:
            print(line)
    
    # 计算每列最大显示宽度
    col_widths = [get_display_width(col) for col in schema]
    for row in data:
        for i, cell in enumerate(row):
            if isinstance(cell, float):
                cell_str = f"{cell:.2f}"
            elif isinstance(cell, int):
                cell_str = f"{cell:,}"
            else:
                cell_str = str(cell)
            cell_width = get_display_width(cell_str)
            col_widths[i] = max(col_widths[i], cell_width)
    
    col_widths = [w + 2 for w in col_widths]
    
    sep = "+" + "+".join(["-" * w for w in col_widths]) + "+"
    add_line("     " + sep)
    
    header_cells = [pad_string(schema[i], col_widths[i], 'center') for i in range(len(schema))]
    add_line("     |" + "|".join(header_cells) + "|")
    add_line("     " + sep)
    
    for row in data:
        cells = []
        for i, cell in enumerate(row):
            if isinstance(cell, float):
                cell_str = f"{cell:.2f}"
            elif isinstance(cell, int):
                cell_str = f"{cell:,}"
            else:
                cell_str = str(cell)
            if isinstance(cell, (int, float)):
                cells.append(pad_string(cell_str, col_widths[i], 'right'))
            else:
                cells.append(pad_string(cell_str, col_widths[i], 'left'))
        add_line("     |" + "|".join(cells) + "|")
    
    add_line("     " + sep)


# ====================  同花顺热股排行榜数据获取类 ====================  

class SlidingWindowData:
    def __init__(self, hot_concept_data_dict, window_size=30):
        self.window_size = window_size
        self.data_dict = hot_concept_data_dict

    def add_data(self, date, data):
        if len(self.data_dict) >= self.window_size:
            sorted_dates = sorted(self.data_dict.keys())
            oldest_date = sorted_dates[0]
            if oldest_date in self.data_dict:
                del self.data_dict[oldest_date]

        self.data_dict[date] = data

        df_list = list(self.data_dict.values())
        if df_list:
            df_merged = pd.concat(df_list, ignore_index=True)
            df_merged = df_merged.drop_duplicates(subset=['stock_code_with_market'])

        for date_key, group_df in df_merged.groupby('日期'):
            g.hot_concept_data_dict[date_key] = group_df
            self.data_dict = g.hot_concept_data_dict
            print(f"日期 {date_key} 的数据已更新，共 {len(group_df)} 条记录")

    def get_all_data(self):
        return list(self.data_dict.values())


# ====================  同花顺热股排行榜数据获取类 ====================  
class THSHotStockFetcher:
    """同花顺热股排行榜数据获取类"""
    
    def __init__(self):
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Cookie': 'SL_G_WPT_TO=eo; SL_GWPT_Show_Hide_tmp=1; SL_wptGlobTipTmp=1',
            'Host': 'search.10jqka.com.cn',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        }
        self.api_url = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock?stock_type=a&type=day&list_type=normal"

    @staticmethod
    def get_market(code):
        if code.startswith('6'):
            return code + '.XSHG'
        elif code.startswith('0') or code.startswith('3'):
            return code + '.XSHE'
        return 'Unknown'

    def fetch_hot_stocks(self):
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                headers = self.headers.copy()
                headers["Host"] = "dq.10jqka.com.cn"

                res = requests.get(url=self.api_url, headers=headers, timeout=10)
                res.raise_for_status()

                data = res.json()["data"]["stock_list"]
                data_list = []

                for d in data:
                    d["concept_tag"] = ";".join(d["tag"]["concept_tag"])
                    if "popularity_tag" in d["tag"]:
                        d["pop_tag"] = d["tag"]["popularity_tag"].replace("\n", "")
                    d["stock_code_with_market"] = self.get_market(d["code"])
                    data_list.append(d)

                rename = {
                    "order": "rank",
                    "rise_and_fall": "change_pct",
                    "code": "stock_code",
                    "name": "short_name",
                    "rate": "hot_value",
                    "concept_tag": "concept_tag",
                }

                rank_df = pd.DataFrame(data_list).rename(columns=rename)
                rank_df = rank_df[[
                    "rank", "stock_code", "stock_code_with_market", "short_name",
                    "change_pct", "hot_value", "pop_tag", "concept_tag"
                ]]

                return rank_df

            except Exception as e:
                retry_count += 1
                print(f"请求失败 (尝试 {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    time.sleep(1)
                else:
                    print("达到最大重试次数，获取股票数据失败")
                    return pd.DataFrame()

    def get_hot_stocks(self, date_now):
        hot_stocks = self.fetch_hot_stocks()
        if not hot_stocks.empty:
            hot_stocks['日期'] = date_now
            if 'change_pct' in hot_stocks.columns:
                hot_stocks['change_pct'] = pd.to_numeric(hot_stocks['change_pct'], errors='coerce')
            print(hot_stocks.to_string())
        return hot_stocks


# ==================== 导入简化的腾讯实时数据获取类 ==================== 
class StockDataFetcher:
    """股票数据获取类"""

    def __init__(self):
        """
        初始化股票数据获取器
        """
        self.base_url = "https://web.sqt.gtimg.cn/q="
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://gu.qq.com/'
        }

    def format_stock_code(self, stock_code):
        """
        格式化股票代码，添加相应的前缀
        :param stock_code: 不带前缀的股票代码
        :return: 带前缀的股票代码
        """
        stock_code = stock_code.strip()

        # 港股处理
        if stock_code.startswith('hk') or stock_code.startswith('HK'):
            return stock_code.lower()

        # A 股处理
        if len(stock_code) == 6 and stock_code.isdigit():
            if stock_code.startswith('6') or stock_code.startswith('9'):
                return f"sh{stock_code}"
            elif stock_code.startswith('0') or stock_code.startswith('3'):
                return f"sz{stock_code}"
            # ETF 基金处理（51 开头为沪市，15/16 开头为深市）
            elif stock_code.startswith('51'):
                return f"sh{stock_code}"
            elif stock_code.startswith('15') or stock_code.startswith('16'):
                return f"sz{stock_code}"
        elif len(stock_code) == 5 and stock_code.isdigit():
            return f"hk{stock_code}"

        # 其他情况直接返回（包括已经带前缀的代码）
        return stock_code

    def get_stock_data(self, stock_codes):
        """
        获取股票实时数据
        :param stock_codes: 股票代码列表（不带前缀），如 ['600036', '000001', '00700']
        :return: 股票信息列表
        """
        formatted_codes = [self.format_stock_code(code) for code in stock_codes]
        url = f"{self.base_url}{','.join(formatted_codes)}"

        try:
            response = requests.get(url, headers=self.headers)
            response.encoding = 'gbk'
            text = response.text
            results = []

            lines = text.strip().split(';')

            for line in lines:
                if not line:
                    continue

                content = line.split('~')

                if len(content) > 32:
                    stock_info = {
                        "代码": content[2],
                        "名称": content[1],
                        "当前价格": float(content[3]) if content[3] else 0.0,
                        "昨收": float(content[4]) if content[4] else 0.0,
                        "今开": float(content[5]) if content[5] else 0.0,
                        "涨跌额": float(content[31]) if content[31] else 0.0,
                        "涨幅 (%)": float(content[32]) if content[32] else 0.0,
                        "最高": float(content[33]) if content[33] else 0.0,
                        "最低": float(content[34]) if content[34] else 0.0,
                        "成交量 (手)": float(content[36]) if content[36] else 0.0,
                        "成交额 (万)": float(content[37]) if content[37] else 0.0
                    }
                    results.append(stock_info)

            return results

        except Exception as e:
            print(f"请求出错：{e}")
            return None

    def fetch_and_print(self, stock_codes):
        """
        获取并打印股票数据
        :param stock_codes: 股票代码列表（不带前缀）
        """
        data = self.get_stock_data(stock_codes)

        if data:
            print("成功")
        else:
            print("未能获取股票数据")

    def get_price(self, stock_code):
        """
        获取单个股票/ETF 的最新价格
        :param stock_code: 股票代码（不带前缀），如 '600036', '512800'
        :return: 最新价格 (float)，获取失败返回 None
        """
        results = self.get_stock_data([stock_code])
        if results and len(results) > 0:
            return results[0]["当前价格"]

        return None

    def get_prices(self, stock_codes):
        """
        批量获取多个股票/ETF 的最新价格
        :param stock_codes: 股票代码列表，如 ['600036', '512800']
        :return: 价格字典 {股票代码：价格}，获取失败的股票不在字典中
        """
        results = {}

        if not stock_codes:
            print("警告：股票代码列表为空")
            return results

        for code in stock_codes:
            try:
                price = self.get_price(code)
                if price is not None:
                    results[code] = price
                else:
                    print(f"提示：股票 {code} 获取失败，已跳过")
            except Exception as e:
                print(f"错误：处理股票 {code} 时发生异常 - {e}")

        success_count = len(results)
        total_count = len(stock_codes)
        if success_count < total_count:
            print(f"\n统计：成功 {success_count}/{total_count}，失败 {total_count - success_count}")

        return results



# ==================== 策略基类 ==================== 
class Strategy:
    def __init__(self, context, index, name):
        self.context = context
        self.index = index
        self.name = name
        self.stock_sum = 1
        self.hold_list = []
        self.min_volume = 2000
        self.pass_months = []
        self.def_stocks = []
        self.yesterday_HL_list = []

    def get_total_value(self):
        if not g.positions[self.index]:
            return 0
        return sum(self.context.portfolio.positions[key].price * value 
                   for key, value in g.positions[self.index].items())

    def get_available_cash(self):
        target_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
        total_value = self.get_total_value()
        available_cash = self.context.portfolio.available_cash
        sub_available_cash = max(0, min(target_value - total_value, available_cash))
        return sub_available_cash

    def _check(self):
        self.hold_list = list(g.positions[self.index].keys())
        if self.hold_list:
            df = get_price(
                self.hold_list,
                end_date=self.context.previous_date,
                frequency="daily",
                fields=["close", "high_limit"],
                count=1,
                panel=False,
                fill_paused=False,
            )
            df = df[df["close"] == df["high_limit"]]
            return list(df.code)
        return []

    def prepare_stock_list(self, context):
        self.yesterday_HL_list = self._check()
        g.no_trading_today_signal = self.today_is_between(context)

    def filter_paused_stock(self, stock_list):
        current_data = get_current_data()
        return [stock for stock in stock_list if not current_data[stock].paused]

    def filter_new_stock(self, context, stock_list):
        yesterday = context.previous_date
        return [stock for stock in stock_list 
                if not yesterday - get_security_info(stock).start_date < dt.timedelta(days=375)]

    def filter_kcbj_stock(self, stock_list):
        for stock in stock_list[:]:
            if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
                stock_list.remove(stock)
        return stock_list

    def filter_st_stock(self, stock_list):
        current_data = get_current_data()
        return [stock for stock in stock_list
                if not current_data[stock].is_st
                and 'ST' not in current_data[stock].name
                and '*' not in current_data[stock].name
                and '退' not in current_data[stock].name]

    def filter_limitup_stock(self, context, stock_list):
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
        current_data = get_current_data()
        return [stock for stock in stock_list 
                if stock in context.portfolio.positions.keys()
                or last_prices[stock][-1] < current_data[stock].high_limit]

    def filter_limitdown_stock(self, context, stock_list):
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
        current_data = get_current_data()
        return [stock for stock in stock_list 
                if stock in context.portfolio.positions.keys() 
                or last_prices[stock][-1] > current_data[stock].low_limit]

    def open_position(self, security, value):
        return self.order_target_value_(security, value)

    def close_position(self, position):
        return self.order_target_value_(position.security, 0)

    def order_target_value_(self, security, value):
        current_data = get_current_data()
        
        # 实时模拟模式：使用腾讯接口获取实时价格
        price = None
        if g_mode == 'realtime' and USE_TENCENT_REALTIME_PRICE and g.tencent_fetcher:
            try:
                raw_code = security.split('.')[0] if '.' in security else security
                tencent_price = g.tencent_fetcher.get_price(raw_code)
                if tencent_price is not None and tencent_price > 0:
                    price = tencent_price
                    log.info(f"【腾讯实时】{security} 实时价格: {price}")
            except Exception as e:
                log.info(f"获取腾讯实时价格失败 {security}: {e}")
        
        # 如果腾讯价格获取失败或未启用，使用聚宽数据
        if price is None:
            price = current_data[security].last_price

        # 检查标的是否停牌、涨停、跌停
        if current_data[security].paused:
            log.info(f"{security}: 今日停牌")
            return False

        if price >= current_data[security].high_limit - 0.01:
            log.info(f"{security}: 当前涨停 (价格:{price}, 涨停价:{current_data[security].high_limit})")
            return False

        if price <= current_data[security].low_limit + 0.01:
            log.info(f"{security}: 当前跌停 (价格:{price}, 跌停价:{current_data[security].low_limit})")
            return False

        target_position = (int(value / price) // 100) * 100 if price != 0 else 0
        current_position = g.positions[self.index].get(security, 0)
        adjustment = target_position - current_position

        closeable_amount = self.context.portfolio.positions[security].closeable_amount if security in self.context.portfolio.positions else 0
        if adjustment < 0 and closeable_amount == 0:
            log.info(f"{security}: 当天买入不可卖出")
            return False

        if adjustment != 0:
            log.info("%s[%s]（%s元）(%s股) (价格:%s) current_position = %s, target_position = %s" % 
                    ("买入" if adjustment > 0 else "卖出", security, value, adjustment, 
                     price, current_position, target_position))
            o = order(security, adjustment)
            if o:
                amount = o.amount if o.is_buy else -o.amount
                g.positions[self.index][security] = amount + current_position
                if target_position == 0:
                    g.positions[self.index].pop(security, None)
                self.hold_list = list(g.positions[self.index].keys())
                return True
        return False

    def today_is_between(self, context):
        month = self.context.current_dt.month
        return month in self.pass_months

# ==================== 子策略类 ==================== 
class Hot100MainBoardWeakToStrongStrategy(Strategy):
    def __init__(self, context, index, name):
        super().__init__(context, index, name)
        self.stock_num = 8 
        self.down = 0.4
        self.pass_months = []

    def get_stock_list(self, context):
        g.dieting = []
        current_data = get_current_data()
        g.yesterday_high_dict = {}
        g.hot100_today_list = []
        
        stk_list = self.rq_hot100_list(context, [])
        
        signal = self.today_is_between(context)
        if signal:
            log.info(f'筛选前：{len(stk_list)}')
            stk_list = self.GJT_filter_stocks(stk_list)
            log.info(f'筛选后：{len(stk_list)}')

        stk_list = self.filter_kcbj_stock(stk_list)
        stk_list = self.filter_st_stock(stk_list)
        if len(stk_list) == 0:
            return []
        stk_list = self.filter_stocks(context, stk_list)
        if len(stk_list) == 0:
            return []

        g.hot100_today_list = stk_list
        log.info(f"股池数: {len(stk_list)}")
        return g.hot100_today_list

    def validate_open_increase(self, context, stk_list): #9:27分之后才能执行，
        """
        验证股票开盘涨幅是否仍在0.95~1.02范围内
        """
        current_data = get_current_data()
        valid_stocks = []
        if len(stk_list) == 0:
            log.error("数据为空")
            return valid_stocks
        # 低开
        # 获取前一日收盘价
        df = get_price(
            stk_list,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close'],
            count=1,
            panel=False,
            fill_paused=False,
            skip_paused=True
        ).set_index('code')

        # 添加当前开盘价，并处理可能的异常
        open_now_values = []
        for s in stk_list:
            try:
                open_now_values.append(current_data[s].day_open)
            except KeyError as e:
                log.info(f"警告: 股票 {s} 的数据不可用, 错误: {e}")
                open_now_values.append(None)

        df['open_now'] = open_now_values

        # 移除那些 'open_now' 是 None 的行
        df = df.dropna(subset=['open_now'])

        # 筛选开盘价在 0.95 ~ 1.01 倍 close 的股票
        df = df[(df['open_now'] / df['close']) < 1.02]
        df = df[(df['open_now'] / df['close']) > 0.95]
        # 更新 stk_list
        stk_list = list(df.index)

        # 排除已持仓的股票
        hold_list = list(g.positions[self.index].keys())
        stk_list = list(set(stk_list) - set(hold_list))

        if len(stk_list) == 0:
            return []

        # 获取估值数据（包括换手率等）
        df_val = get_valuation(
            stk_list,
            start_date=context.previous_date,
            end_date=context.previous_date,
            fields=['turnover_ratio', 'market_cap', 'circulating_market_cap']
        )

        # 确保两个DataFrame的code列都是字符串类型
        df.index = df.index.astype(str)
        df_val['code'] = df_val['code'].astype(str)

        # 使用 pd.merge 进行合并
        df_combined = pd.merge(df.reset_index(), df_val, on='code')

        # 新增因子：换手率 * 开盘/收盘比值
        df_combined['factor'] = df_combined['turnover_ratio'] * (df_combined['open_now'] / df_combined['close'])

        # 按照该因子从大到小排序
        df_sorted = df_combined.sort_values(by='factor', ascending=False)

        # 更新今日选股列表
        valid_stocks = list(df_sorted['code'])
        return valid_stocks
        
    def sell(self, context):
        hold_list = list(context.portfolio.positions.keys())
        if not hold_list:
            return

        current_data = get_current_data()
        yesterday = context.previous_date

        ma5_dict = {}
        for s in hold_list:
            close_data = attribute_history(s, 4, '1d', ['close'], skip_paused=True)
            if len(close_data) < 4:
                continue
            M4 = close_data['close'].mean()
            MA5 = (M4 * 4 + current_data[s].last_price) / 5
            ma5_dict[s] = MA5

        df_history = get_price(hold_list, end_date=yesterday, frequency='daily',
                              fields=['close', 'high_limit'], count=1, panel=False)
        df_history = df_history.set_index('code')

        df_history['avg_cost'] = [context.portfolio.positions[s].avg_cost for s in hold_list]
        df_history['price'] = [context.portfolio.positions[s].price for s in hold_list]
        df_history['last_price'] = [current_data[s].last_price for s in hold_list]
        df_history['high_limit'] = [current_data[s].high_limit for s in hold_list]
        df_history['low_limit'] = [current_data[s].low_limit for s in hold_list]
        df_history['MA5'] = [ma5_dict.get(s, 0) for s in hold_list]

        ret_matrix = (df_history['price'] / df_history['avg_cost'] - 1) * 100

        cond1 = (df_history['last_price'] != df_history['high_limit'])
        cond2_1 = (ret_matrix < -3) & (df_history['MA5'] > df_history['last_price'])
        cond2_2 = ret_matrix > 1.5
        cond2_3 = (df_history['close'] == df_history['high_limit'])

        sell_condition = cond1 & (cond2_1 | cond2_2 | cond2_3) & \
                        (df_history['last_price'] > df_history['low_limit'])

        for s in df_history[sell_condition].index:
            position = context.portfolio.positions[s]
            if self.close_position(position):
                log.info(f'卖出 {s} | 成本:{position.avg_cost:.2f} 现价:{position.price:.2f} '
                       f'收益率:{(position.price/position.avg_cost-1)*100:.2f}% '
                       f'MA5:{ma5_dict.get(s, 0):.2f}')
                log.info('-' * 50)

    def buy(self, context):
        target = g.hot100_today_list
        target = self.validate_open_increase(context, target)
        target = self.filter_stocks_by_b_s(context, target)
        target = self.filter_stocks_pass(context, target)

        hold_list = list(g.positions[self.index].keys())
        num = self.stock_num - len(hold_list)
        if num == 0:
            return
        target = [x for x in target if x not in hold_list][:num]
        log.info("备选股池:" + str(target))
        if len(target) > 0:
            value = self.get_available_cash()
            cash_per_stock = value / num
            for stock in target:
                if self.open_position(stock, cash_per_stock):
                    log.info(f"买入 {stock}")
                    num -= 1
                    if num == 0:
                        break

    def filter_stocks_pass(self, context, stock_list):
        date_now = context.current_dt.strftime("%Y-%m-%d")
        buy_list = []
        buy_list2 = []
        current_data = get_current_data()

        for stock in stock_list:
            day_open_price = current_data[stock].day_open
            last_price = current_data[stock].last_price

            if current_data[stock].paused or \
                    last_price == current_data[stock].low_limit or \
                    last_price == current_data[stock].high_limit:
                continue

            prev_day_data = attribute_history(stock, 1, '1d', fields=['close', 'volume', 'money'], skip_paused=True)
            auction_data = get_call_auction(stock, start_date=date_now, end_date=date_now,
                                            fields=['time', 'volume', 'current'])
            if auction_data.empty or auction_data['volume'][0] / prev_day_data['volume'][-1] < 0.015:
                continue

            buy_list.append(stock)

        return buy_list2 + buy_list

    def dieting_monitor(self, context):
        current_data = get_current_data()
        hold_list = list(g.positions[self.index].keys())
        for s in hold_list:
            if s not in g.dieting:
                dtj = current_data[s].low_limit
                zxj = current_data[s].last_price
                if zxj == dtj and (context.portfolio.positions[s].closeable_amount != 0):
                    if s not in g.dieting:
                        g.dieting.append(s)
        g.dieting = list(set(g.dieting))
        if len(g.dieting) > 0:
            for s in g.dieting[:]:
                dtj = current_data[s].low_limit
                zxj = current_data[s].last_price
                if zxj > dtj:
                    position = context.portfolio.positions[s]
                    self.close_position(position)
                    g.dieting.remove(s)
                    log.info(f"跌停打开卖出:{s}")

    def filter_stocks_by_b_s(self, context, stock_list):
        date = context.current_dt.strftime("%Y-%m-%d")
        valid_stocks = []

        for stock in stock_list:
            auction_df = get_call_auction(stock, start_date=date, end_date=date)

            if auction_df is None or auction_df.empty:
                continue

            auction_df = auction_df.assign(
                sellmoney=lambda df:
                df['a1_p'] * df['a1_v'] +
                df['a2_p'] * df['a2_v'] +
                df['a3_p'] * df['a3_v'] +
                df['a4_p'] * df['a4_v'] +
                df['a5_p'] * df['a5_v'],

                buymoney=lambda df:
                df['b1_p'] * df['b1_v'] +
                df['b2_p'] * df['b2_v'] +
                df['b3_p'] * df['b3_v'] +
                df['b4_p'] * df['b4_v'] +
                df['b5_p'] * df['b5_v']
            )

            auction_df = auction_df.assign(
                b_s=lambda df: (df['buymoney'] - df['sellmoney']) / df['sellmoney']
            )

            if not auction_df.empty and auction_df['b_s'].iloc[0] > 0:
                valid_stocks.append(stock)

        return valid_stocks

    def today_is_between(self, context):
        today = context.current_dt.strftime('%m-%d')
        if ('01-15' <= today) and (today <= '01-31'):
            return True
        elif ('04-15' <= today) and (today <= '04-31'):
            return True
        elif ('12-15' <= today) and (today <= '12-31'):
            return True
        return False

    def get_shifted_date(self, date, days, days_type='T'):
        d_date = self.transform_date(date, 'd')
        yesterday = d_date + dt.timedelta(-1)
        if days_type == 'N':
            shifted_date = yesterday + dt.timedelta(days + 1)
        if days_type == 'T':
            all_trade_days = [i.strftime('%Y-%m-%d') for i in list(get_all_trade_days())]
            if str(yesterday) in all_trade_days:
                shifted_date = all_trade_days[all_trade_days.index(str(yesterday)) + days + 1]
            else:
                for i in range(100):
                    last_trade_date = yesterday - dt.timedelta(i)
                    if str(last_trade_date) in all_trade_days:
                        shifted_date = all_trade_days[all_trade_days.index(str(last_trade_date)) + days + 1]
                        break
        return str(shifted_date)

    def transform_date(self, date, date_type):
        if type(date) == str:
            str_date = date
            dt_date = dt.datetime.strptime(date, '%Y-%m-%d')
            d_date = dt_date.date()
        elif type(date) == dt.datetime:
            str_date = date.strftime('%Y-%m-%d')
            dt_date = date
            d_date = dt_date.date()
        elif type(date) == dt.date:
            str_date = date.strftime('%Y-%m-%d')
            dt_date = dt.datetime.strptime(str_date, '%Y-%m-%d')
            d_date = date
        dct = {'str': str_date, 'dt': dt_date, 'd': d_date}
        return dct[date_type]

    def get_ever_not_hl_stock(self, initial_list, date):
        df = get_price(initial_list, end_date=date, frequency='daily',
                       fields=['close', 'high', 'high_limit'], count=1, panel=False,
                       fill_paused=False, skip_paused=False)
        df = df.dropna()
        df = df[df['high'] == df['high_limit']]
        cd2 = df['close'] != df['high_limit']
        df = df[cd2]
        return list(df.code)

    def get_ever_hl_stock(self, initial_list, date):
        df = get_price(initial_list, end_date=date, frequency='daily',
                       fields=['close', 'high', 'high_limit'], count=1, panel=False,
                       fill_paused=False, skip_paused=False)
        df = df.dropna()
        cd2 = df['close'] != df['high_limit']
        df = df[cd2]
        return list(df.code)

    def get_hl_stock(self, initial_list, date):
        df = get_price(initial_list, end_date=date, frequency='daily',
                       fields=['close', 'low', 'high_limit'], count=1, panel=False,
                       fill_paused=False, skip_paused=False)
        df = df.dropna()
        df = df[df['close'] == df['high_limit']]
        return list(df.code)

    def rq_hot100_list(self, context, initial_list):
        """获取人气榜100股票列表（根据模式选择）"""
        if g_mode == 'realtime':
            return self._get_hot100_realtime(context)
        else:
            return self._get_hot100_backtest(context)

    def _get_hot100_realtime(self, context):
        """实时获取人气榜100数据"""
        try:
            date_now = context.current_dt.strftime("%Y%m%d")
            log.info(f"【实时模式】开始获取 {date_now} 人气榜100数据...")
            
            fetcher = THSHotStockFetcher()
            hot100_stocks_df = fetcher.get_hot_stocks(date_now)
            
            if hot100_stocks_df is None or hot100_stocks_df.empty:
                log.info("【实时模式】获取人气榜100失败，返回空列表")
                return []
            
            # 追加写入CSV文件（如果启用）
            if APPEND_HOT100_TO_CSV:
                csv_df = hot100_stocks_df.copy()
                csv_df['日期'] = date_now
                csv_df = csv_df.rename(columns={
                    'rank': '个股热度排名',
                    'stock_code': 'code',
                    'short_name': '股票简称',
                    'change_pct': '最新涨跌幅',
                    'hot_value': '个股热度',
                })
                csv_df['最新价'] = None
                csv_df['market_code'] = 33
                
                output_columns = ['code', '股票简称', '最新价', '最新涨跌幅', '个股热度',
                                 '个股热度排名', 'market_code', '日期', 'stock_code_with_market']
                for col in output_columns:
                    if col not in csv_df.columns:
                        csv_df[col] = None
                
                csv_df = csv_df[output_columns]
                append_hot100_to_csv(csv_df, HOT100_REALTIME_CSV_PATH)
            
            stock_list = hot100_stocks_df['stock_code_with_market'].tolist()
            if not stock_list:
                return []
            
            yesterday = context.previous_date
            yesterday_hl_stocks = self.get_hl_stock(stock_list, yesterday)
            filtered_stocks = [stock for stock in stock_list if stock not in yesterday_hl_stocks]
            result = self.get_ever_hl_stock(filtered_stocks, context.previous_date)
            
            log.info(f"【实时模式】Hot100原始股票数: {len(stock_list)}, "
                    f"昨日涨停数: {len(yesterday_hl_stocks)}, "
                    f"最终股票数: {len(result)}")
            
            return result
            
        except Exception as e:
            log.info(f"【实时模式】获取hot100失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_hot100_backtest(self, context):
        """回测模式：从历史文件获取人气榜100数据"""
        date = context.previous_date
        date_2, date_1, date = get_trade_days(end_date=date, count=3)
        
        sliding_window = SlidingWindowData(g.hot_concept_data_dict, window_size=3)
        date_now = context.previous_date.strftime("%Y%m%d")
        
        hot100_stocks_df = read_stock_data(HOT100_CSV_PATH , date_now)
        sliding_window.add_data(date_now, hot100_stocks_df)
        
        history_hot100_stocks_list = list(g.hot_concept_data_dict.values())
        df = pd.concat(history_hot100_stocks_list, ignore_index=True)
        df = df[df['stock_code_with_market'] != 'Unknown']
        df = df['stock_code_with_market']
        
        if not df.tolist():
            return df.tolist()

        stock_list = self.get_hl_stock(df.tolist(), date_1)
        return self.get_ever_hl_stock(df.tolist(), context.previous_date)

    def filter_stocks(self, context, stocks):
        if len(stocks) == 0:
            return []
        yesterday = context.previous_date
        df = get_price(
            stocks,
            count=11,
            frequency='1d',
            fields=['close', 'low', 'volume'],
            end_date=yesterday,
            panel=False
        ).reset_index()
        
        grouped = df.groupby('code')
        ma10 = grouped['close'].transform(lambda x: x.rolling(10).mean())
        prev_low = grouped['low'].shift(1)
        prev_volume = grouped['volume'].shift(1)
        
        conditions = (
                (df['close'] > prev_low) &
                (df['close'] > ma10) &
                (df['volume'] > prev_volume) &
                (df['volume'] < 10 * prev_volume) &
                (df['close'] > 1)
        )
        
        latest_data = df[df['time'] == pd.Timestamp(yesterday)]
        condition_indexed = conditions.reindex(latest_data.index, fill_value=False)
        valid_stocks = latest_data[condition_indexed]['code'].unique().tolist()
        
        return valid_stocks

    def GJT_filter_stocks(self, stocks):
        q = query(
            valuation.code,
            valuation.market_cap,
            income.np_parent_company_owners,
            income.net_profit,
            income.operating_revenue
        ).filter(
            valuation.code.in_(stocks),
            income.np_parent_company_owners > 0,
            income.net_profit > 0,
            income.operating_revenue > 1e8,
            indicator.roe > 0,
            indicator.roa > 0,
        )
        df = get_fundamentals(q)
        return list(df.code)
        
        