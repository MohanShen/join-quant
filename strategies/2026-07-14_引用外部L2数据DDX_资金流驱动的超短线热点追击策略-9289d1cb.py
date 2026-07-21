# Clone from JoinQuant
# postId: 9289d1cbac8323a43a33d9815312b1d0
# backtestId: f6d0ebacfc8efbd862447107511138d9
# title: 引用外部L2数据DDX_资金流驱动的超短线热点追击策略

from __future__ import division
import math
import jqdata
from jqdata import *
import datetime as dt
import time
import warnings
import numpy as np
import pandas as pd
from six import BytesIO
import urllib.request
import urllib.error
import json
from collections import defaultdict
import ssl

# 初始化函数 
def initialize(context):
    # 基础设置
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(30/10000))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.95/10000, close_commission=0.95/10000, close_today_commission=0, min_commission=1), type='stock')
    
    # 全局变量
    g.stock_num = 2  # 持股数量
    g.hold_days = 3  # 持股天数
    g.ddx_threshold = 0  # DDX阈值
    g.use_ddx_data = True  # 是否使用DDX数据
    g.ddx_data_available = False  # DDX数据是否可用
    g.take_profit_threshold = 0.08  # 止盈阈值：涨幅大于8%
    g.max_ddx_retries = 5  # DDX最大重试次数
    g.ddx_retry_count = 0  # DDX重试计数器
    g.ddx_required_min_stocks = 1000  # DDX数据最少需要的股票数量
    g.hot_category_count = 12  # 选择最热的板块数量
    g.ddx_weight = 0.5  # DDX排序权重
    g.volume_ratio_weight = 1  # 成交量比排序权重
    g.hot_category_rank_weight = 0.75  # 热点板块排名权重
    g.min_avg_ddx = 0.1  # 最终股票池平均DDX的最小要求
    g.max_buy_increase = 0.0995  # 买入时最大涨幅限制9.95%
    g.max_prev_turnover_rate = 0.17  # T-1日换手率最大限制17%
    
    # 成交量比例参数
    g.volume_ratio_multiplier = 0.5  # 实时成交量与5日均量对比的比例参数
    
    # 数据完整性检查相关
    g.data_complete = False  # 数据是否完整标志
    g.min_stocks_in_pool = 1  # 股票池最少股票数量
    g.min_history_days = 10  # 最少需要的历史数据天数
    g.max_data_check_retries = 5  # 数据检查最大重试次数
    
    # 板块DDX相关参数
    g.min_sector_ddx = 0  # 板块平均DDX最小值要求
    g.min_sector_stocks_with_ddx = 5  # 板块中至少要有几只股票有DDX数据才计算平均
    g.stocks_min_categories = 2  # 股票至少要在几个板块中才入选
    
    # 热点板块统计天数参数
    g.watch_days = 7  # 热点板块统计天数
    
    # DDX数据获取相关参数
    g.ddx_page_size = 100  # 每页获取的股票数量
    g.ddx_max_pages = 55   # 最大获取页数（100*50=5000只股票）
    
    # 热点板块计算结果缓存
    g.hot_stocks_cache = None  # 缓存热点板块股票列表
    g.hot_category_ranking_cache = {}  # 缓存热点板块排名
    g.category_ddx_info_cache = {}  # 缓存板块DDX信息
    g.hot_categories_cache = []  # 缓存热点板块列表
    g.is_hot_category_calculated = False  # 标志热点板块是否已计算
    
    # 新增：缓存股票热点板块排名分
    g.stock_hot_category_score_cache = {}  # 缓存每只股票的热点板块排名分
    
    # 盘前计算结果缓存
    g.pre_market_results = {}  # 存储所有盘前计算结果
    g.pre_market_calculated = False  # 盘前计算是否完成
    g.volume_ratio_dict = {}  # 缓存成交量比计算结果
    
    # 交易时间监控点（每5分钟一次）
    g.monitor_times = []
    for hour in range(9, 15):
        for minute in range(0, 60, 5):
            if hour == 9 and minute < 30:
                continue
            if hour == 14 and minute > 30:
                break
            g.monitor_times.append(f"{hour:02d}:{minute:02d}")
    
    # 在监控时间点中添加9:31
    if '09:31' not in g.monitor_times:
        g.monitor_times.append('09:31')
        g.monitor_times.sort()
    
    # 买入监控时间（9:31-13:15）
    g.buy_monitor_times = [t for t in g.monitor_times 
                           if (int(t.split(':')[0]) < 13 or 
                               (int(t.split(':')[0]) == 13 and int(t.split(':')[1]) <= 30))]
    
    # 卖出监控时间（9:30-14:25）
    g.sell_monitor_times = [t for t in g.monitor_times 
                            if (int(t.split(':')[0]) < 14 or 
                                (int(t.split(':')[0]) == 14 and int(t.split(':')[1]) <= 54))]
    
    log.info(f"总共{len(g.monitor_times)}个监控时间点")
    log.info(f"买入监控时间点: {g.buy_monitor_times}")
    log.info(f"卖出监控时间点: {g.sell_monitor_times}")
    
    # 运行时间设置
    # 获取前一日DDX数据（盘前），使用重试机制
    run_daily(get_previous_day_ddx_with_retry, '9:15')
    # 数据完整性检查（9:20）
    run_daily(check_data_completeness, '9:20')
    # 盘前计算（9:25）- 包含DDX相关计算、盘后量比、昨日换手率等
    run_daily(pre_market_calculations, '9:25')
    # 热点板块计算排序（9:26）并缓存股票热点板块排名分
    run_daily(calculate_hot_categories, '9:26')
    # 14:30定点卖出所有持仓
    run_daily(sell_all_positions_at_1430, '14:28')
    
    # 注册所有监控时间点
    for time_str in g.monitor_times:
        run_daily(monitor_buy_and_sell, time_str)
    
    # 初始化持仓记录
    g.positions_info = {}  # 记录买入日期和买入价格
    g.previous_day_ddx_data = None  # 存储前一日DDX数据
    g.category_ddx_info = {}  # 存储板块DDX信息
    g.end_date = None  # 存储结束日期，将在get_stocks_list2中设置
    g.hot_category_ranking = {}  # 热点板块排名字典

def pre_market_calculations(context):
    """盘前计算：包含DDX相关计算、盘后量比、昨日换手率等"""
    log.info("=== 9:25 开始盘前计算 ===")
    
    # 重置盘前计算标志
    g.pre_market_calculated = False
    g.pre_market_results = {}
    g.volume_ratio_dict = {}
    
    # 检查DDX数据是否可用
    if g.use_ddx_data and (not g.ddx_data_available or g.previous_day_ddx_data is None):
        log.warning("DDX数据不可用，跳过盘前计算")
        return
    
    try:
        # 1. 获取热点板块股票列表
        log.info("步骤1: 获取热点板块股票列表")
        hot_stocks = get_stocks_list2_for_cache(context)
        
        if not hot_stocks or len(hot_stocks) == 0:
            log.warning("热点板块股票列表为空，跳过盘前计算")
            return
        
        log.info(f"获取到{len(hot_stocks)}只热点板块股票")
        
        # 2. 计算成交量比（盘后量比条件）
        log.info("步骤2: 计算成交量比（5日成交量/53日成交量）")
        valid_stocks = []
        
        for idx, stock in enumerate(hot_stocks):
            try:
                # 计算成交量比
                volume_ratio = calculate_volume_ratio_pre_market(stock, context)
                
                if volume_ratio is not None:
                    g.volume_ratio_dict[stock] = volume_ratio
                    valid_stocks.append(stock)
                
                # 每计算100只股票输出一次进度
                if (idx + 1) % 100 == 0:
                    log.info(f"已计算{idx + 1}只股票的成交量比，有效数据: {len(valid_stocks)}只")
                    
            except Exception as e:
                log.warning(f"股票{stock}成交量比计算失败: {e}")
                continue
        
        log.info(f"成交量比计算完成，有效数据: {len(valid_stocks)}/{len(hot_stocks)}只股票")
        
        # 3. 计算昨日换手率条件
        log.info("步骤3: 提取昨日换手率数据")
        turnover_stocks = []
        
        for stock in valid_stocks:
            if stock in g.previous_day_ddx_data.index:
                turnover_rate = g.previous_day_ddx_data.loc[stock, 'turnover_rate']
                # 检查换手率是否满足条件
                if turnover_rate < g.max_prev_turnover_rate:
                    turnover_stocks.append(stock)
        
        log.info(f"昨日换手率筛选: {len(turnover_stocks)}/{len(valid_stocks)}只股票满足换手率<{g.max_prev_turnover_rate*100:.0f}%")
        
        # 4. 计算DDX相关条件
        log.info("步骤4: 计算DDX相关条件")
        ddx_stocks = []
        
        for stock in turnover_stocks:
            if stock in g.previous_day_ddx_data.index:
                ddx_value = g.previous_day_ddx_data.loc[stock, 'ddx']
                # 检查DDX是否满足条件
                if ddx_value > g.ddx_threshold:
                    ddx_stocks.append(stock)
        
        log.info(f"DDX筛选: {len(ddx_stocks)}/{len(turnover_stocks)}只股票满足DDX>{g.ddx_threshold}")
        
        # 5. 存储盘前计算结果
        g.pre_market_results = {
            'hot_stocks': hot_stocks,
            'valid_stocks': valid_stocks,
            'turnover_stocks': turnover_stocks,
            'ddx_stocks': ddx_stocks,
            'volume_ratio_dict': g.volume_ratio_dict.copy(),
            'calculation_time': context.current_dt
        }
        
        # 标记盘前计算完成
        g.pre_market_calculated = True
        
        # 输出盘前计算统计信息
        log.info("=== 盘前计算完成 ===")
        log.info(f"初始热点板块股票: {len(hot_stocks)}只")
        log.info(f"有效成交量比数据: {len(valid_stocks)}只")
        log.info(f"满足换手率条件: {len(turnover_stocks)}只")
        log.info(f"满足DDX条件: {len(ddx_stocks)}只")
        
        # 输出示例数据
        if len(ddx_stocks) > 0:
            sample_size = min(5, len(ddx_stocks))
            log.info(f"盘前计算示例股票（前{sample_size}只）:")
            for i in range(sample_size):
                stock = ddx_stocks[i]
                ddx_value = g.previous_day_ddx_data.loc[stock, 'ddx']
                turnover_rate = g.previous_day_ddx_data.loc[stock, 'turnover_rate']
                volume_ratio = g.volume_ratio_dict.get(stock, None)
                
                stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知"
                log.info(f"  {stock} ({stock_name}): DDX={ddx_value:.4f}, 换手率={turnover_rate:.2%}, 成交量比={volume_ratio:.2f if volume_ratio else 'N/A'}")
    
    except Exception as e:
        log.error(f"盘前计算过程中出错: {e}")
        import traceback
        log.error(traceback.format_exc())

def calculate_volume_ratio_pre_market(stock, context):
    """盘前计算成交量比：5日成交量/53日成交量"""
    try:
        # 获取53日历史数据，不包含当日
        hist_data_53 = attribute_history(stock, 54, '1d', ['volume'], skip_paused=True)
        
        if len(hist_data_53) < 54:
            return None
        
        # 使用T-1日到T-53日的数据
        # 排除最新一天（如果是当日数据）或直接使用历史数据
        hist_data_53 = hist_data_53.iloc[:-1]  # 排除最新数据
        
        if len(hist_data_53) >= 5:
            avg_volume_5 = hist_data_53['volume'][-5:].mean()
        else:
            avg_volume_5 = hist_data_53['volume'].mean()
        
        avg_volume_53 = hist_data_53['volume'].mean()
        
        if avg_volume_53 > 0:
            volume_ratio = avg_volume_5 / avg_volume_53
            return volume_ratio
        else:
            return None
            
    except Exception as e:
        log.error(f"盘前计算股票{stock}成交量比失败: {e}")
        return None

def calculate_hot_categories(context):
    """在9:26计算热点板块排序并缓存股票热点板块排名分"""
    log.info("=== 9:26 开始计算热点板块排序 ===")
    
    # 检查DDX数据是否可用（热点板块计算需要DDX数据）
    if g.use_ddx_data and (not g.ddx_data_available or g.previous_day_ddx_data is None):
        log.warning("DDX数据不可用，跳过热点板块计算")
        return
    
    # 检查盘前计算是否完成
    if not g.pre_market_calculated:
        log.warning("盘前计算未完成，跳过热点板块计算")
        return
    
    # 清空之前的缓存
    g.hot_stocks_cache = None
    g.hot_category_ranking_cache = {}
    g.category_ddx_info_cache = {}
    g.hot_categories_cache = []
    g.is_hot_category_calculated = False
    g.stock_hot_category_score_cache = {}  # 清空股票排名分缓存
    
    # 执行热点板块计算
    try:
        # 调用原有的热点板块计算逻辑，但不返回结果而是缓存到全局变量
        cached_hot_stocks = get_stocks_list2_for_cache(context)
        
        if cached_hot_stocks:
            log.info(f"热点板块计算完成，缓存了{len(cached_hot_stocks)}只股票")
            g.is_hot_category_calculated = True
            
            # 显示缓存的热点板块排名
            if g.hot_category_ranking_cache:
                log.info("热点板块排名缓存:")
                for category, rank in sorted(g.hot_category_ranking_cache.items(), key=lambda x: x[1])[:10]:
                    log.info(f"  第{rank}名: {category}")
        else:
            log.warning("热点板块计算未返回有效股票列表")
            
    except Exception as e:
        log.error(f"计算热点板块时出错: {e}")
        import traceback
        log.error(traceback.format_exc())

def get_stocks_list2_for_cache(context):
    """为缓存而设计的get_stocks_list2版本，计算热点板块并缓存股票排名分"""
    log.info('开始计算热点板块（仅供缓存）')
    
    # 使用前一个交易日作为结束日期
    yesterday = context.previous_date
    g.end_date = yesterday.strftime('%Y-%m-%d')  # T-1日
    
    # 使用全局变量g.watch_days作为统计天数
    log.info(f"板块热度计算使用数据范围: 最近{g.watch_days}天，结束日期: {g.end_date}")
    
    category = Category()
    
    # 修复：确保category.concept_category有正确的列
    if not category.concept_category.empty:
        # 确保列名正确
        if 'code' not in category.concept_category.columns:
            # 尝试重命名列
            if 'stock' in category.concept_category.columns:
                category.concept_category = category.concept_category.rename(columns={'stock': 'code'})
        
        # 获取股票名称
        category.concept_category['name'] = category.concept_category['code'].apply(get_stock_name)
        category.concept_category = category.concept_category[category.concept_category['name'] != 'Unknown']
        category.concept_category.reset_index(drop=True, inplace=True)
        
        log.info(f"概念板块数据加载成功，共{len(category.concept_category)}条记录")
    else:
        log.error("概念板块数据为空，无法继续")
        return []
    
    # 原有过滤逻辑...
    categories_to_drop = [
        '标普道琼斯中国', '富时罗素', 'MSCI', 'CIPS概念', 'ST', 'st', 
        '融资融券', '融券', '融资', '微盘股', '专精特新', '区块链', '数字经济',
        '注册制次新股', '新股与次新股', '央企国企改革', '国企改革', '破净股',
        '低价股', '可转债', '沪股通', '深股通', '昨日涨停', '昨日连板', '昨日首板', '昨日触板',
        '科创企业同股同权', '一带一路', '东数西算(算力)', '北京冬奥会', '房价上涨',     
        '广东', '浙江', '上海', '江苏', '深圳', '北京'
    ]
    
    category.concept_category = category.concept_category[~category.concept_category['category'].isin(categories_to_drop)]
    pattern = '|'.join([f'.*{word}.*' for word in categories_to_drop])
    category.concept_category = category.concept_category[~category.concept_category['category'].str.contains(pattern, na=False)]
    
    log.info(f"过滤后概念板块数据: {len(category.concept_category)}条记录")
    
    # 计算股票得分
    df_stock_score = stocks_score(category, context)
    
    if df_stock_score.empty:
        log.warning("股票得分数据为空，无法计算板块热度")
        return []
    
    log.info(f"股票得分数据形状: {df_stock_score.shape}")
    
    # 计算板块得分
    df_category_score = category.category_score_and_pct_attacking(
        df_score=df_stock_score, 
        df_category=category.concept_category, 
        count=g.watch_days,  # 使用全局变量g.watch_days
        daily_top_filter=5
    )
    
    if df_category_score.empty:
        log.warning("板块得分数据为空")
        return []
    
    hot_categories = df_category_score['category'].head(g.hot_category_count).tolist()
    g.hot_categories_cache = hot_categories  # 缓存热点板块列表
    
    log.info(f"最热的{g.hot_category_count}个板块: {', '.join(hot_categories)}")
    
    # 新增：计算每个板块的平均DDX
    good_categories = []  # 符合DDX要求的板块
    g.category_ddx_info_cache = {}  # 重置板块DDX信息缓存
    
    for category_name in hot_categories:
        # 获取板块内的股票
        stocks = category.find_stocks_by_category(category_name, fuzzy_match=True)
        
        # 计算板块平均DDX
        category_ddx_info = calculate_category_ddx(category_name, stocks)
        
        if category_ddx_info is not None:
            g.category_ddx_info_cache[category_name] = category_ddx_info
            
            # 检查板块平均DDX是否满足要求
            if category_ddx_info['avg_ddx'] >= g.min_sector_ddx:
                good_categories.append(category_name)
                log.info(f"板块 '{category_name}' 通过DDX筛选，平均DDX: {category_ddx_info['avg_ddx']:.4f}")
            else:
                log.info(f"板块 '{category_name}' 被剔除，平均DDX: {category_ddx_info['avg_ddx']:.4f} < {g.min_sector_ddx}")
        else:
            # 如果没有足够的DDX数据，默认通过
            log.info(f"板块 '{category_name}' DDX数据不足，默认通过")
            good_categories.append(category_name)
            g.category_ddx_info_cache[category_name] = {
                'category': category_name,
                'avg_ddx': None,
                'stocks_count': len(stocks),
                'stocks_with_ddx_count': 0,
                'stocks_with_ddx': [],
                'ddx_values': []
            }
    
    log.info(f"DDX筛选后，{len(good_categories)}/{g.hot_category_count}个板块符合要求")
    
    if len(good_categories) == 0:
        log.warning("没有板块通过DDX筛选，无法选股")
        return []
    
    # 获取通过DDX筛选的板块中的股票
    stocks_by_category = []
    for category_name in good_categories:
        stocks = category.find_stocks_by_category(category_name, fuzzy_match=True)
        stocks_by_category.append(set(stocks))
        log.info(f"板块 '{category_name}' 包含 {len(stocks)} 只股票")
    
    # 新增：构建热点板块排名字典（按热度从高到低，1为最热）
    g.hot_category_ranking_cache = {}
    for idx, category_name in enumerate(good_categories):
        g.hot_category_ranking_cache[category_name] = idx + 1
    
    log.info(f"热点板块排名：{g.hot_category_ranking_cache}")
    
    # 统计股票出现在多少个板块中
    stock_count = defaultdict(int)
    for stock_set in stocks_by_category:
        for stock in stock_set:
            stock_count[stock] += 1
    
    # 修改：要求股票至少出现在2个板块中
    min_occurrence = g.stocks_min_categories
    stocks_in_hot_concept = [stock for stock, count in stock_count.items() if count >= min_occurrence]
    
    total_stocks = sum(len(stock_set) for stock_set in stocks_by_category)
    unique_stocks = len(stock_count)
    log.info(f"{len(good_categories)}个合格板块总共包含 {total_stocks} 次股票出现，去重后 {unique_stocks} 只唯一股票")
    log.info(f"出现在至少{min_occurrence}个板块中的股票有 {len(stocks_in_hot_concept)} 只")
    
    if len(stocks_in_hot_concept) < g.min_stocks_in_pool:
        log.warning(f"出现在至少{min_occurrence}个板块中的股票数量不足: {len(stocks_in_hot_concept)} < {g.min_stocks_in_pool}")
        return []
    
    filtered_stocks = []
    for stock in stocks_in_hot_concept:
        # 修改：去掉科创板选股限制
        # if stock.startswith('688'):
        #     continue
            
        try:
            current_data = get_current_data()[stock]
            if current_data.paused or current_data.is_st or '退' in current_data.name:
                continue
            filtered_stocks.append(stock)
        except:
            continue
    
    log.info(f"计算完成，得到{len(filtered_stocks)}只热点板块股票")
    
    # 新增：计算并缓存每只股票的热点板块排名分
    log.info("=== 计算并缓存股票热点板块排名分 ===")
    stocks_calculated = 0
    
    for stock in filtered_stocks:
        hot_category_score = calculate_hot_category_rank_score_for_cache(stock)
        g.stock_hot_category_score_cache[stock] = hot_category_score
        stocks_calculated += 1
        
        # 每计算100只股票输出一次进度
        if stocks_calculated % 100 == 0:
            log.info(f"已计算并缓存{stocks_calculated}只股票的热点板块排名分")
    
    log.info(f"总共计算并缓存了{stocks_calculated}只股票的热点板块排名分")
    
    # 输出板块DDX排名
    if g.use_ddx_data and g.ddx_data_available:
        log.info("=== 板块DDX排名 ===")
        # 只显示有DDX数据的板块
        category_ddx_list = []
        for category_name, info in g.category_ddx_info_cache.items():
            if info['avg_ddx'] is not None:
                category_ddx_list.append((category_name, info['avg_ddx']))
        
        # 按DDX值排序
        category_ddx_list.sort(key=lambda x: x[1], reverse=True)
        for idx, (category_name, avg_ddx) in enumerate(category_ddx_list):
            log.info(f"DDX排名{idx+1}: 板块 '{category_name}', 平均DDX: {avg_ddx:.4f}")
    
    if len(filtered_stocks) > 0:
        sample_size = min(10, len(filtered_stocks))
        sample_stocks = filtered_stocks[:sample_size]
        log.info(f"示例股票({sample_size}只): {', '.join(sample_stocks)}")
    
    # 缓存结果
    g.hot_stocks_cache = filtered_stocks
    
    # 将缓存同步到原始全局变量，以便其他函数使用
    g.category_ddx_info = g.category_ddx_info_cache
    g.hot_category_ranking = g.hot_category_ranking_cache
    
    return filtered_stocks

def calculate_hot_category_rank_score_for_cache(stock):
    """为缓存计算股票的热点板块排名分（盘前调用）"""
    # 获取股票的板块信息
    stock_categories = []
    
    # 遍历所有板块，找出股票所在的板块
    for category_name, category_info in g.category_ddx_info_cache.items():
        if stock in category_info.get('stocks_with_ddx', []):
            stock_categories.append(category_name)
    
    if not stock_categories:
        # 如果股票不在任何热点板块中，返回一个很大的分数
        return 999
    
    # 计算股票所在的板块排名平均值
    total_rank = 0
    valid_categories = 0
    
    # 热点板块的排名（按热度从高到低，1为最热）
    hot_category_rank_dict = g.hot_category_ranking_cache
    
    # 计算平均排名
    for category_name in stock_categories:
        if category_name in hot_category_rank_dict:
            category_rank = hot_category_rank_dict[category_name]
            total_rank += category_rank
            valid_categories += 1
        else:
            # 如果板块不在前12热点中，给一个较高的排名
            total_rank += g.hot_category_count + 1
            valid_categories += 1
    
    if valid_categories == 0:
        return 999
    
    avg_rank = total_rank / valid_categories
    
    # 检查是否至少出现在2个板块中
    if valid_categories < 2:
        # 如果不满足至少2个板块的条件，惩罚性增加分数
        return avg_rank * 2
    
    return avg_rank

def calculate_hot_category_rank_score(stock):
    """计算股票在热点板块中的排名分（盘中调用，使用缓存）"""
    # 如果有缓存，直接返回缓存结果
    if stock in g.stock_hot_category_score_cache:
        return g.stock_hot_category_score_cache[stock]
    
    # 否则回退到实时计算（兼容性）
    # 获取股票的板块信息
    stock_categories = []
    
    # 使用缓存的数据
    if g.is_hot_category_calculated and g.category_ddx_info_cache:
        # 使用缓存的数据
        category_info_to_use = g.category_ddx_info_cache
    else:
        # 使用原始数据
        category_info_to_use = g.category_ddx_info
    
    for category_name, category_info in category_info_to_use.items():
        if stock in category_info.get('stocks_with_ddx', []):
            stock_categories.append(category_name)
    
    if not stock_categories:
        # 如果股票不在任何热点板块中，返回一个很大的分数
        return 999
    
    # 计算股票所在的板块排名平均值
    total_rank = 0
    valid_categories = 0
    
    # 热点板块的排名
    if g.is_hot_category_calculated and g.hot_category_ranking_cache:
        # 使用缓存的排名
        hot_category_rank_dict = g.hot_category_ranking_cache
    else:
        # 使用原始排名
        hot_category_rank_dict = g.hot_category_ranking
    
    # 计算平均排名
    for category_name in stock_categories:
        if category_name in hot_category_rank_dict:
            category_rank = hot_category_rank_dict[category_name]
            total_rank += category_rank
            valid_categories += 1
        else:
            # 如果板块不在前12热点中，给一个较高的排名
            total_rank += g.hot_category_count + 1
            valid_categories += 1
    
    if valid_categories == 0:
        return 999
    
    avg_rank = total_rank / valid_categories
    
    # 检查是否至少出现在2个板块中
    if valid_categories < 2:
        # 如果不满足至少2个板块的条件，惩罚性增加分数
        return avg_rank * 2
    
    return avg_rank

def get_stocks_list2(context):
    """获取同花顺热点板块股票（使用缓存结果）"""
    current_time = context.current_dt
    current_time_str = current_time.strftime('%H:%M')
    
    # 如果热点板块已经计算并缓存，直接使用缓存结果
    if g.is_hot_category_calculated and g.hot_stocks_cache is not None:
        log.info(f"=== {current_time_str} 使用9:26计算的热点板块缓存结果 ===")
        
        # 确保全局变量已同步
        if not g.category_ddx_info:
            g.category_ddx_info = g.category_ddx_info_cache
        if not g.hot_category_ranking:
            g.hot_category_ranking = g.hot_category_ranking_cache
            
        # 从缓存中获取热点板块列表
        if g.hot_categories_cache:
            log.info(f"热点板块列表（来自缓存）: {', '.join(g.hot_categories_cache[:5])}...")
        
        log.info(f"热点板块股票数量（来自缓存）: {len(g.hot_stocks_cache)}只")
        
        # 输出缓存的热点板块排名
        if g.hot_category_ranking_cache:
            log.info("热点板块排名（来自缓存）:")
            for category, rank in sorted(g.hot_category_ranking_cache.items(), key=lambda x: x[1])[:5]:
                log.info(f"  第{rank}名: {category}")
        
        return g.hot_stocks_cache
    else:
        # 如果缓存不可用，则回退到原始计算方式（但这种情况不应该在9:26之后发生）
        log.warning(f"=== {current_time_str} 热点板块缓存不可用，回退到实时计算 ===")
        return get_stocks_list2_backup(context)

def get_stocks_list2_backup(context):
    """备份函数：当缓存不可用时实时计算热点板块"""
    log.info('获取热点板块股票（实时计算）')
    
    # 使用前一个交易日作为结束日期
    yesterday = context.previous_date
    g.end_date = yesterday.strftime('%Y-%m-%d')  # T-1日
    
    # 使用全局变量g.watch_days作为统计天数
    log.info(f"板块热度计算使用数据范围: 最近{g.watch_days}天，结束日期: {g.end_date}")
    
    category = Category()
    
    # 修复：确保category.concept_category有正确的列
    if not category.concept_category.empty:
        # 确保列名正确
        if 'code' not in category.concept_category.columns:
            # 尝试重命名列
            if 'stock' in category.concept_category.columns:
                category.concept_category = category.concept_category.rename(columns={'stock': 'code'})
        
        # 获取股票名称
        category.concept_category['name'] = category.concept_category['code'].apply(get_stock_name)
        category.concept_category = category.concept_category[category.concept_category['name'] != 'Unknown']
        category.concept_category.reset_index(drop=True, inplace=True)
        
        log.info(f"概念板块数据加载成功，共{len(category.concept_category)}条记录")
    else:
        log.error("概念板块数据为空，无法继续")
        return []
    
    # 原有过滤逻辑...
    categories_to_drop = [
        '标普道琼斯中国', '富时罗素', 'MSCI', 'CIPS概念', 'ST', 'st', 
        '融资融券', '融券', '融资', '微盘股', '专精特新', '区块链', '数字经济',
        '注册制次新股', '新股与次新股', '央企国企改革', '国企改革', '破净股',
        '低价股', '可转债', '沪股通', '深股通', '昨日涨停', '昨日连板', '昨日首板', '昨日触板',
        '科创企业同股同权', '一带一路', '东数西算(算力)', '北京冬奥会', '房价上涨',     
        '广东', '浙江', '上海', '江苏', '深圳', '北京'
    ]
    
    category.concept_category = category.concept_category[~category.concept_category['category'].isin(categories_to_drop)]
    pattern = '|'.join([f'.*{word}.*' for word in categories_to_drop])
    category.concept_category = category.concept_category[~category.concept_category['category'].str.contains(pattern, na=False)]
    
    log.info(f"过滤后概念板块数据: {len(category.concept_category)}条记录")
    
    # 计算股票得分
    df_stock_score = stocks_score(category, context)
    
    if df_stock_score.empty:
        log.warning("股票得分数据为空，无法计算板块热度")
        return []
    
    log.info(f"股票得分数据形状: {df_stock_score.shape}")
    
    # 计算板块得分
    df_category_score = category.category_score_and_pct_attacking(
        df_score=df_stock_score, 
        df_category=category.concept_category, 
        count=g.watch_days,  # 使用全局变量g.watch_days
        daily_top_filter=5
    )
    
    if df_category_score.empty:
        log.warning("板块得分数据为空")
        return []
    
    hot_categories = df_category_score['category'].head(g.hot_category_count).tolist()
    
    log.info(f"最热的{g.hot_category_count}个板块: {', '.join(hot_categories)}")
    
    # 新增：计算每个板块的平均DDX
    good_categories = []  # 符合DDX要求的板块
    g.category_ddx_info = {}  # 重置板块DDX信息
    
    for category_name in hot_categories:
        # 获取板块内的股票
        stocks = category.find_stocks_by_category(category_name, fuzzy_match=True)
        
        # 计算板块平均DDX
        category_ddx_info = calculate_category_ddx(category_name, stocks)
        
        if category_ddx_info is not None:
            g.category_ddx_info[category_name] = category_ddx_info
            
            # 检查板块平均DDX是否满足要求
            if category_ddx_info['avg_ddx'] >= g.min_sector_ddx:
                good_categories.append(category_name)
                log.info(f"板块 '{category_name}' 通过DDX筛选，平均DDX: {category_ddx_info['avg_ddx']:.4f}")
            else:
                log.info(f"板块 '{category_name}' 被剔除，平均DDX: {category_ddx_info['avg_ddx']:.4f} < {g.min_sector_ddx}")
        else:
            # 如果没有足够的DDX数据，默认通过
            log.info(f"板块 '{category_name}' DDX数据不足，默认通过")
            good_categories.append(category_name)
            g.category_ddx_info[category_name] = {
                'category': category_name,
                'avg_ddx': None,
                'stocks_count': len(stocks),
                'stocks_with_ddx_count': 0,
                'stocks_with_ddx': [],
                'ddx_values': []
            }
    
    log.info(f"DDX筛选后，{len(good_categories)}/{g.hot_category_count}个板块符合要求")
    
    if len(good_categories) == 0:
        log.warning("没有板块通过DDX筛选，无法选股")
        return []
    
    # 获取通过DDX筛选的板块中的股票
    stocks_by_category = []
    for category_name in good_categories:
        stocks = category.find_stocks_by_category(category_name, fuzzy_match=True)
        stocks_by_category.append(set(stocks))
        log.info(f"板块 '{category_name}' 包含 {len(stocks)} 只股票")
    
    # 新增：构建热点板块排名字典（按热度从高到低，1为最热）
    g.hot_category_ranking = {}
    for idx, category_name in enumerate(good_categories):
        g.hot_category_ranking[category_name] = idx + 1
    
    log.info(f"热点板块排名：{g.hot_category_ranking}")
    
    # 统计股票出现在多少个板块中
    stock_count = defaultdict(int)
    for stock_set in stocks_by_category:
        for stock in stock_set:
            stock_count[stock] += 1
    
    # 修改：要求股票至少出现在2个板块中
    min_occurrence = g.stocks_min_categories
    stocks_in_hot_concept = [stock for stock, count in stock_count.items() if count >= min_occurrence]
    
    total_stocks = sum(len(stock_set) for stock_set in stocks_by_category)
    unique_stocks = len(stock_count)
    log.info(f"{len(good_categories)}个合格板块总共包含 {total_stocks} 次股票出现，去重后 {unique_stocks} 只唯一股票")
    log.info(f"出现在至少{min_occurrence}个板块中的股票有 {len(stocks_in_hot_concept)} 只")
    
    if len(stocks_in_hot_concept) < g.min_stocks_in_pool:
        log.warning(f"出现在至少{min_occurrence}个板块中的股票数量不足: {len(stocks_in_hot_concept)} < {g.min_stocks_in_pool}")
        return []
    
    filtered_stocks = []
    for stock in stocks_in_hot_concept:
        # 修改：去掉科创板选股限制
        # if stock.startswith('688'):
        #     continue
            
        try:
            current_data = get_current_data()[stock]
            if current_data.paused or current_data.is_st or '退' in current_data.name:
                continue
            filtered_stocks.append(stock)
        except:
            continue
    
    log.info(f"获取到{len(filtered_stocks)}只热点板块股票")
    
    # 输出板块DDX排名
    if g.use_ddx_data and g.ddx_data_available:
        log.info("=== 板块DDX排名 ===")
        # 只显示有DDX数据的板块
        category_ddx_list = []
        for category_name, info in g.category_ddx_info.items():
            if info['avg_ddx'] is not None:
                category_ddx_list.append((category_name, info['avg_ddx']))
        
        # 按DDX值排序
        category_ddx_list.sort(key=lambda x: x[1], reverse=True)
        for idx, (category_name, avg_ddx) in enumerate(category_ddx_list):
            log.info(f"DDX排名{idx+1}: 板块 '{category_name}', 平均DDX: {avg_ddx:.4f}")
    
    if len(filtered_stocks) > 0:
        sample_size = min(10, len(filtered_stocks))
        sample_stocks = filtered_stocks[:sample_size]
        log.info(f"示例股票({sample_size}只): {', '.join(sample_stocks)}")
    
    return filtered_stocks

def check_data_completeness(context):
    """检查数据完整性"""
    log.info("=== 开始数据完整性检查 ===")
    
    # 重置数据完整性标志
    g.data_complete = False
    
    # 1. 检查DDX数据（如果使用DDX）
    if g.use_ddx_data:
        if not g.ddx_data_available:
            log.error("数据不完整：DDX数据不可用")
            return False
        
        if g.previous_day_ddx_data is None or g.previous_day_ddx_data.empty:
            log.error("数据不完整：DDX数据为空")
            return False
        
        # 检查DDX数据质量
        ddx_data_ok = is_ddx_data_complete(g.previous_day_ddx_data, context.previous_date.strftime('%Y-%m-%d'))
        if not ddx_data_ok:
            log.error("数据不完整：DDX数据质量不合格")
            return False
        
        log.info(f"DDX数据检查通过：{len(g.previous_day_ddx_data)}条记录")
    
    # 2. 检查股票池数据
    try:
        # 获取热点板块股票
        hot_stocks = get_stocks_list2(context)
        
        if not hot_stocks:
            log.error("数据不完整：热点板块股票列表为空")
            return False
        
        if len(hot_stocks) < g.min_stocks_in_pool:
            log.error(f"数据不完整：热点板块股票数量不足（{len(hot_stocks)} < {g.min_stocks_in_pool}）")
            return False
        
        # 抽样检查几只股票的历史数据
        sample_size = min(10, len(hot_stocks))
        sample_stocks = hot_stocks[:sample_size]
        
        valid_stock_count = 0
        for stock in sample_stocks:
            try:
                # 检查是否有足够的历史数据
                hist_data = attribute_history(stock, g.min_history_days, '1d', ['close', 'volume'])
                if len(hist_data) >= g.min_history_days:
                    valid_stock_count += 1
            except Exception as e:
                log.warning(f"股票{stock}历史数据检查失败: {e}")
                continue
        
        if valid_stock_count < sample_size * 0.7:  # 要求70%的抽样股票有足够历史数据
            log.error(f"数据不完整：抽样股票历史数据不足（{valid_stock_count}/{sample_size}）")
            return False
        
        log.info(f"股票池数据检查通过：{len(hot_stocks)}只股票，抽样{valid_stock_count}/{sample_size}只合格")
    
    except Exception as e:
        log.error(f"股票池数据检查异常: {e}")
        return False
    
    # 3. 检查实时数据可用性
    try:
        current_time = context.current_dt
        # 获取几只股票的实时数据
        test_stocks = ['000001.XSHE', '600000.XSHG']  # 测试用股票
        for stock in test_stocks:
            current_data = get_current_data()[stock]
            if current_data is None:
                log.error(f"数据不完整：实时数据不可用（{stock}）")
                return False
    except Exception as e:
        log.error(f"实时数据检查异常: {e}")
        return False
    
    # 所有检查通过
    g.data_complete = True
    log.info("=== 数据完整性检查通过 ===")
    return True

def monitor_buy_and_sell(context):
    """每个监控时间点执行买入和卖出检查"""
    current_time = context.current_dt
    current_time_str = current_time.strftime('%H:%M')
    
    # 新增：9:30的买入监控延迟到9:31执行
    if current_time_str == '09:30':
        # 只执行卖出监控，不执行买入监控
        log.info(f"=== {current_time_str} 监控检查开始 (9:30只执行卖出监控，买入监控延迟到9:31) ===")
        
        # 检查数据完整性
        if not g.data_complete:
            log.warning("数据不完整，跳过本次监控")
            return
        
        # 执行卖出监控
        log.info(f"{current_time_str} 执行卖出监控")
        monitor_sell_conditions(context)
        
        log.info(f"=== {current_time_str} 监控检查结束 ===")
        return
    
    log.info(f"=== {current_time_str} 监控检查开始 ===")
    
    # 新增：检查数据完整性
    if not g.data_complete:
        log.warning("数据不完整，跳过本次监控")
        return
    
    # 执行卖出监控（如果在卖出监控时间内）
    if current_time_str in g.sell_monitor_times:
        log.info(f"{current_time_str} 执行卖出监控")
        monitor_sell_conditions(context)
    
    # 执行买入监控（如果在买入监控时间内）
    if current_time_str in g.buy_monitor_times:
        log.info(f"{current_time_str} 执行买入监控")
        monitor_buy_conditions(context)
    
    log.info(f"=== {current_time_str} 监控检查结束 ===")

def monitor_buy_conditions(context):
    """监控买入条件"""
    # 新增：再次检查数据完整性
    if not g.data_complete:
        log.warning("数据不完整，跳过买入监控")
        return
    
    # 检查盘前计算是否完成
    if not g.pre_market_calculated:
        log.warning("盘前计算未完成，跳过买入监控")
        return
    
    # 检查是否有可用资金
    if context.portfolio.available_cash < 1000:
        log.info("可用资金不足，跳过买入监控")
        return
    
    # 检查是否已达到持股上限
    if len(context.portfolio.positions) >= g.stock_num:
        log.info("已达到持股上限，跳过买入监控")
        return
    
    # 获取符合条件的股票列表
    stock_list = get_realtime_stock_list(context)
    
    if stock_list:
        # 买入符合条件的股票
        buy_realtime_stocks(context, stock_list)
    else:
        log.info("没有符合条件的股票")

def monitor_sell_conditions(context):
    """监控卖出条件（新增：跌破7日均线的条件）"""
    # 新增：检查数据完整性（卖出时要求较低，但最好也有数据）
    positions_to_sell = []
    
    for stock in list(context.portfolio.positions.keys()):
        should_sell = False
        sell_reason = ""
        
        try:
            # 检查持股天数
            if stock in g.positions_info:
                buy_date = g.positions_info[stock]['buy_date']
                current_date = context.current_dt.date()
                hold_days = (current_date - buy_date).days
                
                # 条件0: 持股超过3天卖出
                if hold_days >= g.hold_days:
                    should_sell = True
                    sell_reason = f"持股{hold_days}天达到{g.hold_days}天上限"
            
            # 获取当前数据
            current_data = get_current_data()[stock]
            if current_data is None:
                log.warning(f"无法获取股票{stock}的实时数据，跳过卖出检查")
                continue
                
            current_price = current_data.last_price
            
            # 获取持仓信息
            position = context.portfolio.positions[stock]
            avg_cost = position.avg_cost  # 持仓成本
            
            # 计算当日涨幅（相对于持仓成本）
            if avg_cost > 0:
                profit_rate = (current_price - avg_cost) / avg_cost
                
                # 条件1: 涨幅大于8%卖出
                if profit_rate > g.take_profit_threshold:
                    should_sell = True
                    sell_reason = f"涨幅{profit_rate:.2%}超过{g.take_profit_threshold*100}%"
            
            # 新增：条件2: 跌破7日均线卖出
            try:
                # 获取7日历史数据（不包含今日）
                hist_data = attribute_history(stock, 8, '1d', ['close'])
                if len(hist_data) >= 8:
                    # 计算7日均线（使用前7日数据，不包含今日）
                    ma7 = hist_data['close'][:-1].mean()  # 排除最新一天
                    
                    if current_price < ma7:
                        should_sell = True
                        if sell_reason:
                            sell_reason += f", 且跌破7日均线(当前价:{current_price:.2f}, MA7:{ma7:.2f})"
                        else:
                            sell_reason = f"跌破7日均线(当前价:{current_price:.2f}, MA7:{ma7:.2f})"
            except Exception as e:
                log.warning(f"检查7日均线时出错: {e}")
            
            # 条件3: 检查是否涨停（涨停不卖）
            if current_price >= current_data.high_limit * 0.999:
                should_sell = False
                if sell_reason:
                    sell_reason = "涨停，暂不卖出"
            
            # 条件4: 检查是否跌停（跌停时可能无法卖出）
            if current_price <= current_data.low_limit * 1.001:
                # 跌停时也考虑卖出（如果条件触发）
                log.info(f"{stock} 跌停，但仍尝试卖出")
            
            if should_sell:
                positions_to_sell.append((stock, sell_reason))
                
        except Exception as e:
            log.error(f"检查股票{stock}卖出条件时出错: {e}")
    
    # 执行卖出
    for stock, reason in positions_to_sell:
        try:
            order_target(stock, 0)
            log.info(f"卖出 {stock}, 原因: {reason}")
            if stock in g.positions_info:
                del g.positions_info[stock]
        except Exception as e:
            log.error(f"卖出股票{stock}时出错: {e}")

def sell_all_positions_at_1430(context):
    """14:30定点卖出所有持仓"""
    log.info("=== 14:30定点卖出开始 ===")
    
    positions_to_sell = []
    
    for stock in list(context.portfolio.positions.keys()):
        try:
            current_data = get_current_data()[stock]
            if current_data is None:
                log.warning(f"无法获取股票{stock}的实时数据")
                continue
                
            current_price = current_data.last_price
            
            # 检查是否涨停（涨停不卖）
            if current_price >= current_data.high_limit * 0.999:
                log.info(f"{stock} 涨停，14:30不卖出")
                continue
            
            # 获取持仓信息
            position = context.portfolio.positions[stock]
            avg_cost = position.avg_cost
            
            # 计算当日涨幅
            profit_rate = (current_price - avg_cost) / avg_cost if avg_cost > 0 else 0
            
            positions_to_sell.append((stock, profit_rate))
            
        except Exception as e:
            log.error(f"检查股票{stock}时出错: {e}")
    
    # 执行卖出
    for stock, profit_rate in positions_to_sell:
        try:
            order_target(stock, 0)
            log.info(f"14:30定点卖出 {stock}, 收益率: {profit_rate:.2%}")
            if stock in g.positions_info:
                del g.positions_info[stock]
        except Exception as e:
            log.error(f"卖出股票{stock}时出错: {e}")
    
    log.info("=== 14:30定点卖出结束 ===")

def get_previous_day_ddx_with_retry(context):
    """获取前一个交易日的DDX数据，带重试��制"""
    if not g.use_ddx_data:
        return
    
    # 重置重试计数器
    g.ddx_retry_count = 0
    
    # 开始获取数据
    success = get_previous_day_ddx_with_retry_impl(context)
    
    # 如果失败，启动重试机制
    while not success and g.ddx_retry_count < g.max_ddx_retries:
        g.ddx_retry_count += 1
        log.info(f"DDX数据获取失败，进行第{g.ddx_retry_count}次重试...")
            
        success = get_previous_day_ddx_with_retry_impl(context)
    
    if not success:
        log.warning(f"DDX数据获取失败，已重试{g.max_ddx_retries}次，今日将跳过DDX选股")
        g.ddx_data_available = False
        g.previous_day_ddx_data = None
    else:
        log.info("DDX数据获取成功，可以正常选股")

def get_previous_day_ddx_with_retry_impl(context):
    """获取前一个交易日的DDX数据实现（改进：获取更多页数据）"""
    # 获取前一个交易日
    previous_date = context.previous_date.strftime('%Y-%m-%d')
    
    try:
        # 修改：分批获取多页DDX数据
        all_ddx_data = []
        
        log.info(f"开始分批获取{previous_date}的DDX数据，每页{g.ddx_page_size}只股票")
        
        for page in range(1, g.ddx_max_pages + 1):
            log.info(f"获取第{page}页DDX数据...")
            try:
                # 获取当前页的DDX数据
                ddx_df_page = ddx_with_retry(previous_date, g.ddx_page_size, page)
                
                if ddx_df_page is None or ddx_df_page.empty:
                    log.info(f"第{page}页数据为空，停止获取")
                    break
                
                # 记录本页数据量
                log.info(f"第{page}页获取到{len(ddx_df_page)}只股票DDX数据")
                
                # 添加到总数据
                all_ddx_data.append(ddx_df_page)
                
                # 如果本页数据少于预期，可能已经获取完所有数据
                if len(ddx_df_page) < g.ddx_page_size * 0.5:  # 如果数据少于一半
                    log.info(f"第{page}页数据较少({len(ddx_df_page)}只)，可能已获取完所有数据")
                    break
                    
            except Exception as e:
                log.warning(f"获取第{page}页DDX数据失败: {e}")
                # 继续尝试下一页
                continue
        
        # 合并所有页的数据
        if not all_ddx_data:
            log.warning(f"未能获取到任何{previous_date}的DDX数据")
            return False
        
        # 合并DataFrame
        ddx_df = pd.concat(all_ddx_data, axis=0)
        log.info(f"合并所有页数据，共获取{len(ddx_df)}只股票的DDX数据")
        
        # 去重（防止重复数据）
        ddx_df = ddx_df[~ddx_df.index.duplicated(keep='first')]
        log.info(f"去重后剩余{len(ddx_df)}只股票")
        
        # 检查数据是否完整
        if is_ddx_data_complete(ddx_df, previous_date):
            # 只保留DDX大于阈值、涨幅大于0且换手率<26%的股票
            ddx_df = ddx_df[(ddx_df['ddx'] > g.ddx_threshold) & 
                           (ddx_df['inc'] > 0) & 
                           (ddx_df['turnover_rate'] < g.max_prev_turnover_rate)]
            
            # 按DDX值降序排列
            ddx_df = ddx_df.sort_values('ddx', ascending=False)
            
            # 检查是否有足够的股票
            if len(ddx_df) < 10:
                log.warning(f"DDX数据中符合条件(DDX>{g.ddx_threshold}, 换手率<{g.max_prev_turnover_rate*100:.0f}%)的股票太少: {len(ddx_df)}只")
                return False
            
            # 存储到全局变量
            g.previous_day_ddx_data = ddx_df
            g.ddx_data_available = True
            
            log.info(f"获取到完整的前一日({previous_date})DDX数据，共{len(ddx_df)}只股票符合条件(DDX>{g.ddx_threshold}, 换手率<{g.max_prev_turnover_rate*100:.0f}%)")
            
            # 记录前几名股票
            if len(ddx_df) > 0:
                top_stocks = ddx_df.head(10)
                log.info(f"DDX排名前10的股票：")
                for idx, (stock_code, row) in enumerate(top_stocks.iterrows()):
                    log.info(f"第{idx+1}名: {stock_code}, DDX={row['ddx']:.4f}, 涨幅={row['inc']:.2%}, 换手率={row['turnover_rate']:.2%}")
            
            # 记录DDX分布统计
            if len(ddx_df) > 0:
                ddx_positive = len(ddx_df[ddx_df['ddx'] > 0])
                ddx_negative = len(ddx_df[ddx_df['ddx'] < 0])
                ddx_zero = len(ddx_df[ddx_df['ddx'] == 0])
                log.info(f"DDX分布统计：正DDX:{ddx_positive}只, 负DDX:{ddx_negative}只, 零DDX:{ddx_zero}只")
            
            return True
        else:
            log.warning(f"获取到的DDX数据不完整或为空")
            return False
            
    except Exception as e:
        log.error(f"获取DDX数据失败: {e}")
        return False

def is_ddx_data_complete(ddx_df, date_str):
    """检查DDX数据是否完整（放宽标准）"""
    if ddx_df is None:
        log.warning(f"DDX数据为空 (None)")
        return False
    
    if ddx_df.empty:
        log.warning(f"DDX数据为空 (DataFrame为空)")
        return False
    
    # 放宽标准：A股约5000只，获取3000只以上即可接受
    if len(ddx_df) < 1000:  # 最低要求1000只
        log.warning(f"DDX数据行数不足: {len(ddx_df)}行 (要求至少1000行)")
        return False
    
    # 检查必要的列是否存在
    required_columns = ['ddx', 'inc', 'price', 'turnover_rate']
    missing_columns = [col for col in required_columns if col not in ddx_df.columns]
    
    if missing_columns:
        log.warning(f"DDX数据缺少必要的列: {missing_columns}")
        return False
    
    # 检查数据质量：DDX值是否有异常
    if ddx_df['ddx'].isnull().all():
        log.warning("DDX列全部为NaN值")
        return False
    
    # 检查是否有足够的非NaN值
    non_null_count = ddx_df['ddx'].notnull().sum()
    if non_null_count < len(ddx_df) * 0.7:  # 要求70%的数据非空
        log.warning(f"DDX列非空值太少: {non_null_count}/{len(ddx_df)}")
        return False
    
    # 检查DDX值的范围是否合理
    ddx_mean = ddx_df['ddx'].mean()
    if abs(ddx_mean) > 10:  # 放宽范围
        log.warning(f"DDX均值异常: {ddx_mean:.4f}")
        return False
    
    # 检查涨幅数据是否异常
    inc_mean = ddx_df['inc'].abs().mean()
    if inc_mean > 20:  # 放宽范围
        log.warning(f"涨幅均值异常: {inc_mean:.2f}，可能数据格式有问题")
        return False
    
    log.info(f"DDX数据检查通过: {len(ddx_df)}行, DDX均值={ddx_mean:.4f}, 涨幅均值={inc_mean:.2%}")
    return True

def ddx_with_retry(date='2018-03-30', listnum=100, page=1, max_retries=3):
    """获取DDX数据函数 - 带重试机制（修改：减少每页数量以提高成功率）"""
    for retry in range(max_retries):
        try:
            data = ddx_impl(date, listnum, page)
            if data is not None and not data.empty:
                log.info(f"第{retry+1}次尝试成功获取DDX数据（第{page}页，{len(data)}条）")
                return data
            else:
                log.warning(f"第{retry+1}次尝试获取的DDX数据为空（第{page}页）")
        except Exception as e:
            log.error(f"第{retry+1}次尝试获取DDX数据失败（第{page}页）: {e}")
        
        # 如果不是最后一次重试，等待一段时间
        if retry < max_retries - 1:
            wait_time = 2 ** retry
            log.info(f"等待{wait_time}秒后重试第{page}页...")
    
    log.error(f"经过{max_retries}次重试后，仍然无法获取第{page}页DDX数据")
    return None

def ddx_impl(date='2018-03-30', listnum=100, page=1):
    """获取DDX数据实现（修改：优化参数处理）"""
    try:
        # 创建未验证的SSL上下文
        ssl_context = ssl._create_unverified_context()
        
        url = 'http://ddx.gubit.cn/ygetnewallddxpm.php?'
        params = {
            'zf': '0',
            'ddx': '0',
            'ddy': '0',
            'page': str(page),
            'pagenum': str(listnum),
            'orderby': '0',
            'lsdate': date
        }
        
        query_string = urllib.parse.urlencode(params)
        full_url = url + query_string + '&t=' + str(time.time())
        
        req = urllib.request.Request(full_url)
        req.add_header('Referer', 'http://ddx.gubit.cn/xg/ddx.html')
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        req.add_header('Accept', 'application/json, text/javascript, */*; q=0.01')
        req.add_header('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8')
        req.add_header('Connection', 'keep-alive')
        
        # 设置超时
        try:
            ro = urllib.request.urlopen(req, context=ssl_context, timeout=30)
            response_data = ro.read()
            
            if not response_data:
                log.error("获取到的响应数据为空")
                return None
                
            try:
                json_data = json.loads(response_data.decode('utf-8'))
            except json.JSONDecodeError as e:
                log.error(f"JSON解析失败: {e}")
                log.error(f"原始响应: {response_data[:200]}")
                return None
            
            if 'data' not in json_data:
                log.error(f"响应中没有'data'字段: {json_data}")
                return None
                
            jsonData = json_data['data']
            
        except urllib.error.URLError as e:
            log.error(f"URL错误: {e}")
            return None
        except Exception as e:
            log.error(f"请求异常: {e}")
            return None
        
        if not jsonData:
            log.error("DDX数据为空列表")
            return None
            
        ddx_df = pd.DataFrame(jsonData)
        
        if ddx_df.empty:
            log.error("转换后的DataFrame为空")
            return None
        
        # 将股票代码转换为聚宽格式
        def normalize_code_jq(code):
            if isinstance(code, str):
                code = str(code).strip()
                if '.' not in code:
                    if code.startswith('6'):
                        return code + '.XSHG'
                    elif code.startswith(('0', '3')):
                        return code + '.XSHE'
                    elif code.startswith('68'):
                        return code + '.XSHG'
                    else:
                        return code + '.XSHE'
                else:
                    code = code.replace('.SZ', '.XSHE').replace('.SH', '.XSHG')
                    return code
            return code
        
        try:
            ddx_df.index = [normalize_code_jq(code) for code in ddx_df[0]]
        except Exception as e:
            log.error(f"股票代码转换失败: {e}")
            return None
        
        # 只保留有效的股票代码（排除指数等）
        valid_stocks = [code for code in ddx_df.index if code.endswith(('.XSHG', '.XSHE'))]
        ddx_df = ddx_df.loc[valid_stocks]
        
        for idx in range(1, len(ddx_df.columns)):
            try:
                ddx_df[[idx]] = ddx_df[[idx]].astype(float)
            except Exception as e:
                log.warning(f"转换列{idx}为float失败: {e}")
        
        if 34 in ddx_df.columns:
            del ddx_df[34]
        del ddx_df[0]
        
        # 列名定义
        column_names = ['price', 'inc', 'turnover_rate', 'volumn_rate', 'ddx', 'ddy',
                        'ddz', 'dde_5', 'dde_10', 'dde_con', 'dde_inc', 'amount',
                        'bbd', 'order_rate', 'order_buy', 'order_sell', 'extra_dif', 'large_dif',
                        'mid_dif', 'small_diff', 'extra_buy', 'extra_sell', 'large_buy', 'large_sell',
                        'small_buy', 'small_sell', 'whole_buy_1', 'whole_buy_5', 'whole_buy10', 'whole_buy_20',
                        'proactive_rate_1', 'proactive_rate_5', 'proactive_rate_10']
        
        if len(ddx_df.columns) > len(column_names):
            ddx_df = ddx_df.iloc[:, :len(column_names)]
        elif len(ddx_df.columns) < len(column_names):
            for i in range(len(ddx_df.columns), len(column_names)):
                ddx_df[i] = np.nan
        
        ddx_df.columns = column_names[:len(ddx_df.columns)]
        
        # 修复涨幅数据
        if 'inc' in ddx_df.columns:
            inc_mean = ddx_df['inc'].abs().mean()
            if inc_mean > 1:
                log.info(f"检测到涨幅数据异常（平均涨幅={inc_mean:.2f}），进行修正（除以100）")
                ddx_df['inc'] = ddx_df['inc'] / 100.0
        
        # 修复换手率数据
        if 'turnover_rate' in ddx_df.columns:
            turnover_mean = ddx_df['turnover_rate'].mean()
            if turnover_mean > 1:
                log.info(f"检测到换手率数据异常（平均换手率={turnover_mean:.2f}），进行修正（除以100）")
                ddx_df['turnover_rate'] = ddx_df['turnover_rate'] / 100.0
        
        # 数据质量检查
        valid_count = len(ddx_df)
        if 'ddx' in ddx_df.columns:
            ddx_notna = ddx_df['ddx'].notna().sum()
            log.info(f"本页有效数据: {valid_count}条，DDX非空: {ddx_notna}条")
        
        return ddx_df
    except Exception as e:
        log.error(f"获取DDX数据异常: {e}")
        return None

def get_realtime_ddx(stock_code):
    """获取实时DDX数据（模拟）"""
    if g.ddx_data_available and g.previous_day_ddx_data is not None and stock_code in g.previous_day_ddx_data.index:
        return g.previous_day_ddx_data.loc[stock_code, 'ddx']
    return None

def calculate_category_ddx(category_name, category_stocks):
    """计算板块的平均DDX"""
    if not g.use_ddx_data or not g.ddx_data_available:
        return None
    
    if g.previous_day_ddx_data is None or g.previous_day_ddx_data.empty:
        return None
    
    # 找出板块中所有有DDX数据的股票
    stocks_with_ddx = []
    ddx_values = []
    
    for stock in category_stocks:
        if stock in g.previous_day_ddx_data.index:
            ddx_value = g.previous_day_ddx_data.loc[stock, 'ddx']
            if not np.isnan(ddx_value):
                stocks_with_ddx.append(stock)
                ddx_values.append(ddx_value)
    
    # 如果板块中有DDX数据的股票太少，返回None
    if len(ddx_values) < g.min_sector_stocks_with_ddx:
        log.info(f"板块 '{category_name}' 中有DDX数据的股票太少: {len(ddx_values)}只")
        return None
    
    # 计算平均DDX
    avg_ddx = np.mean(ddx_values)
    log.info(f"板块 '{category_name}' 平均DDX: {avg_ddx:.4f} (基于{len(ddx_values)}只股票)")
    
    return {
        'category': category_name,
        'avg_ddx': avg_ddx,
        'stocks_count': len(category_stocks),
        'stocks_with_ddx_count': len(ddx_values),
        'stocks_with_ddx': stocks_with_ddx,
        'ddx_values': ddx_values
    }

def get_realtime_stock_list(context):
    """实时选股函数（使用盘前计算结果和缓存）"""
    # 新增：检查数据完整性
    if not g.data_complete:
        log.warning("数据不完整，不进行选股")
        return []
    
    # 检查盘前计算是否完成
    if not g.pre_market_calculated:
        log.warning("盘前计算未完成，不进行选股")
        return []
    
    # 1. 获取同花顺热点板块股票（使用缓存）
    hot_stocks = get_stocks_list2(context)
    
    if not hot_stocks:
        log.info("无热点板块股票")
        return []
    
    # 2. 过滤已持有的股票
    filtered_hot_stocks = []
    for stock in hot_stocks:
        if stock in context.portfolio.positions:
            continue
        filtered_hot_stocks.append(stock)
    
    if not filtered_hot_stocks:
        log.info("所有热点股票都已持有")
        return []
    
    # 3. 使用盘前计算的DDX和换手率筛选结果
    if 'ddx_stocks' in g.pre_market_results:
        ddx_stocks = g.pre_market_results['ddx_stocks']
        filtered_by_ddx = [stock for stock in filtered_hot_stocks if stock in ddx_stocks]
        
        log.info(f"盘前DDX筛选: {len(filtered_by_ddx)}/{len(filtered_hot_stocks)}只股票满足条件")
        
        if filtered_by_ddx:
            filtered_hot_stocks = filtered_by_ddx
        else:
            log.info("无股票符合DDX条件，今日不买入")
            return []
    
    # 4. 技术条件筛选（使用盘前计算的结果）
    buy_candidates = []
    
    for stock in filtered_hot_stocks:
        if check_realtime_technical_conditions_pre_market(stock, context):
            buy_candidates.append(stock)
    
    if not buy_candidates:
        log.info("没有通过技术条件筛选的股票")
        return []
    
    # 新增：检查最终股票池数量
    if len(buy_candidates) < g.min_stocks_in_pool:
        log.warning(f"最终股票池数量不足: {len(buy_candidates)} < {g.min_stocks_in_pool}")
        return []
    
    # 5. 计算最终股票池的平均DDX，并检查是否达标（使用盘前数据）
    if g.use_ddx_data and g.ddx_data_available and g.previous_day_ddx_data is not None and buy_candidates:
        # 计算最终股票池的平均DDX
        total_ddx = 0
        valid_stocks_count = 0
        
        for stock in buy_candidates:
            if stock in g.previous_day_ddx_data.index:
                ddx_value = g.previous_day_ddx_data.loc[stock, 'ddx']
                total_ddx += ddx_value
                valid_stocks_count += 1
        
        if valid_stocks_count > 0:
            avg_ddx = total_ddx / valid_stocks_count
            log.info(f"最终股票池平均DDX: {avg_ddx:.4f}, 要求: >{g.min_avg_ddx}")
            
            # 检查平均DDX是否达标
            if avg_ddx <= g.min_avg_ddx:
                log.warning(f"最终股票池平均DDX({avg_ddx:.4f})低于要求({g.min_avg_ddx})，今日不选股")
                return []
            else:
                log.info(f"最终股票池平均DDX({avg_ddx:.4f})达标，继续选股流程")
        else:
            log.warning("最终股票池中没有股票的DDX数据，今日不选股")
            return []
    
    # 6. 按综合权重排序（使用盘前计算的成交量比和缓存的热点板块排名分）
    if buy_candidates and g.use_ddx_data and g.ddx_data_available and g.previous_day_ddx_data is not None:
        stock_scores = []
        
        for stock in buy_candidates:
            if stock in g.previous_day_ddx_data.index:
                ddx_value = g.previous_day_ddx_data.loc[stock, 'ddx']
                # 使用盘前计算的成交量比
                volume_ratio = g.volume_ratio_dict.get(stock, None)
                
                if volume_ratio is not None:
                    # 使用缓存的热点板块排名分
                    hot_category_rank_score = g.stock_hot_category_score_cache.get(stock, 999)
                    
                    stock_scores.append({
                        'stock': stock,
                        'ddx': ddx_value,
                        'volume_ratio': volume_ratio,
                        'hot_category_rank_score': hot_category_rank_score
                    })
                else:
                    log.warning(f"股票 {stock} 无盘前成交量比数据，跳过该股票")
        
        if stock_scores:
            df_scores = pd.DataFrame(stock_scores)
            
            # 计算各个因子的排名（升序，越小越好）
            df_scores['volume_ratio_rank'] = df_scores['volume_ratio'].rank(ascending=False, method='min')
            df_scores['ddx_rank'] = df_scores['ddx'].rank(ascending=False, method='min')
            df_scores['hot_category_rank_score_rank'] = df_scores['hot_category_rank_score'].rank(ascending=True, method='min')
            
            # 计算综合排名分（权重：成交量比1，DDX0.5，热点板块排名0.75）
            df_scores['total_score'] = (
                df_scores['volume_ratio_rank'] * g.volume_ratio_weight + 
                df_scores['ddx_rank'] * g.ddx_weight +
                df_scores['hot_category_rank_score_rank'] * g.hot_category_rank_weight
            )
            
            # 对total_score四舍五入到小数点后1位，用于检查是否相同
            df_scores['total_score_rounded'] = df_scores['total_score'].round(1)
            
            # 按照total_score_rounded分组，组内按缓存的热点板块股票顺序排序
            score_groups = df_scores.groupby('total_score_rounded')
            
            # 对每个组进行排序
            sorted_dfs = []
            
            for score, group in score_groups:
                if len(group) == 1:
                    # 如果组内只有一只股票，直接加入结果
                    sorted_dfs.append(group)
                else:
                    # 如果组内有多只股票（总排名分相同），按缓存的热点板块股票顺序排序
                    log.info(f"发现总排名分相同的股票组（总分={score:.1f}），包含{len(group)}只股票: {group['stock'].tolist()}")
                    
                    # 使用缓存的热点板块股票列表作为原策略顺序
                    if g.is_hot_category_calculated and g.hot_stocks_cache is not None:
                        original_stocks = g.hot_stocks_cache
                    else:
                        # 如果缓存不可用，回退到实时计算
                        original_stocks = get_stocks_list2_backup(context)
                    
                    if original_stocks:
                        # 创建一个字典，存储股票在缓存中的位置
                        original_order_dict = {}
                        for idx, stock in enumerate(original_stocks):
                            if stock in group['stock'].tolist():
                                original_order_dict[stock] = idx
                        
                        # 对于不在缓存列表中的股票，给一个很大的顺序值
                        max_order = len(original_stocks)
                        for stock in group['stock'].tolist():
                            if stock not in original_order_dict:
                                original_order_dict[stock] = max_order + 1
                                max_order += 1
                        
                        # 添加缓存顺序列
                        group['original_order'] = group['stock'].map(original_order_dict)
                        # 按缓存顺序排序
                        group = group.sort_values('original_order')
                        log.info(f"按缓存热点板块顺序排序后的股票: {group['stock'].tolist()}")
                    else:
                        # 如果无法获取缓存列表，保持原顺序
                        log.warning("无法获取缓存热点板块股票列表，保持原始顺序")
                    
                    sorted_dfs.append(group)
            
            # 合并所有分组
            df_scores = pd.concat(sorted_dfs)
            
            # 按四舍五入后的总排名分排序（确保不同分数组的正确顺序）
            df_scores = df_scores.sort_values('total_score_rounded')
            
            log.info("综合排名结果（前10名）：")
            for idx, row in df_scores.head(10).iterrows():
                log.info(f"排名{idx+1}: {row['stock']}, "
                        f"成交量比={row['volume_ratio']:.2f}(排名{row['volume_ratio_rank']:.0f}), "
                        f"DDX={row['ddx']:.4f}(排名{row['ddx_rank']:.0f}), "
                        f"热点板块排名分={row['hot_category_rank_score']:.2f}(排名{row['hot_category_rank_score_rank']:.0f}), "
                        f"总排名分={row['total_score']:.1f}(四舍五入={row['total_score_rounded']:.1f})")
            
            buy_candidates = df_scores['stock'].tolist()
            log.info("按综合权重排序完成（相同总排名分时按缓存热点板块顺序）")
        else:
            log.warning("无法计算综合评分，保持原始顺序")
    else:
        log.info("DDX数据不可用，保持原始顺序")
    
    log.info(f"找到{len(buy_candidates)}只符合条件的股票")
    return buy_candidates[:g.stock_num - len(context.portfolio.positions)]

def check_realtime_technical_conditions_pre_market(stock, context):
    """检查实时技术条件（使用盘前计算结果）"""
    try:
        current_data = get_current_data()[stock]
        
        if current_data is None:
            log.warning(f"无法获取股票{stock}的实时数据")
            return False
        
        # 检查基础条件
        if current_data.paused:
            return False
        if current_data.is_st:
            return False
        if '退' in current_data.name:
            return False
        
        if current_data.last_price <= current_data.low_limit * 1.001:
            return False
        
        if current_data.last_price >= current_data.high_limit * 0.999:
            return False
        
        # 获取历史数据（不包含当日）
        try:
            hist_data = attribute_history(stock, 11, '1d', ['close', 'volume'])
            if len(hist_data) < 11:
                log.warning(f"股票{stock}历史数据不足: {len(hist_data)}天")
                return False
            
            # 使用T-1日到T-10日的数据（排除当日）
            hist_data = hist_data.iloc[:-1]  # 排除最新数据
            
            if len(hist_data) < 10:
                log.warning(f"股票{stock}历史数据不足（排除当日后）: {len(hist_data)}天")
                return False
        except Exception as e:
            log.warning(f"获取股票{stock}历史数据失败: {e}")
            return False
        
        yesterday_close = hist_data['close'].iloc[-1]  # T-1日收盘价
        current_price = current_data.last_price
        
        # 新增条件：计算当日涨幅，要求涨幅<9.95%
        daily_increase = (current_price - yesterday_close) / yesterday_close
        if daily_increase >= g.max_buy_increase:  # 9.95%
            log.info(f"股票 {stock} 涨幅{daily_increase:.2%}超过{g.max_buy_increase*100:.2f}%，不买入")
            return False
        
        # 使用盘前计算的DDX和换手率条件
        if g.use_ddx_data and g.ddx_data_available and g.previous_day_ddx_data is not None:
            if stock in g.previous_day_ddx_data.index:
                # 从DDX数据中获取T-1日换手率（盘前已计算）
                turnover_rate = g.previous_day_ddx_data.loc[stock, 'turnover_rate']
                if turnover_rate >= g.max_prev_turnover_rate:  # 26%
                    log.info(f"股票 {stock} T-1日换手率{turnover_rate:.2%} >= {g.max_prev_turnover_rate*100:.0f}%，不买入")
                    return False
                else:
                    log.info(f"股票 {stock} T-1日换手率{turnover_rate:.2%} < {g.max_prev_turnover_rate*100:.0f}%，符合条件")
                
                # 新增：检查DDX值是否大于阈值（盘前已计算）
                ddx_value = g.previous_day_ddx_data.loc[stock, 'ddx']
                if ddx_value < g.ddx_threshold:
                    log.info(f"股票 {stock} T-1日DDX值{ddx_value:.4f} < {g.ddx_threshold}，不买入")
                    return False
                else:
                    log.info(f"股票 {stock} T-1日DDX值{ddx_value:.4f} >= {g.ddx_threshold}，符合条件")
            else:
                # 如果股票不在DDX数据中，则无法检查换手率和DDX
                log.warning(f"股票 {stock} 不在DDX数据中，无法检查T-1日换手率和DDX")
                return False
        else:
            # 如果DDX数据不可用，则跳过换手率和DDX检查
            log.warning(f"DDX数据不可用，跳过T-1日换手率和DDX检查")
        
        # 计算均线（使用历史数据，不包含当日）
        ma5 = hist_data['close'][-5:].mean()  # T-1日到T-5日
        ma10 = hist_data['close'].mean()      # T-1日到T-10日
        
        # 条件1: 5日均线 > 10日均线
        if ma5 <= ma10:
            return False
        
        # 条件2: 盘中股价上穿均线
        # 昨日收盘价在均线下方，今日盘中价格在均线上方
        if not (yesterday_close < ma5 and yesterday_close < ma10):
            return False
        
        if not (current_price > ma5 and current_price > ma10):
            return False
        
        # 条件3: 实时成交量验证（使用前置参数g.volume_ratio_multiplier）
        current_time = context.current_dt
        
        try:
            today_minute_data = get_price(stock, start_date=current_time.date(), end_date=current_time,
                                         frequency='1m', fields=['volume', 'close'], skip_paused=True)
            
            if len(today_minute_data) > 0:
                today_volume = today_minute_data['volume'].sum()
                avg_volume_5 = hist_data['volume'][-5:].mean()
                
                if current_time.hour >= 9 and current_time.minute >= 30:
                    start_time = dt.datetime.combine(current_time.date(), dt.time(9, 30))
                    traded_minutes = max(1, (current_time - start_time).seconds / 60)
                    
                    total_trading_minutes = 240
                    expected_ratio = traded_minutes / total_trading_minutes
                    
                    # 使用前置参数 g.volume_ratio_multiplier
                    if today_volume < avg_volume_5 * g.volume_ratio_multiplier * expected_ratio:
                        log.info(f"股票 {stock} 成交量不足: 今日{today_volume:.0f} < 5日均量{avg_volume_5:.0f}×{g.volume_ratio_multiplier}×时间比例{expected_ratio:.2f}")
                        return False
        except Exception as e:
            log.warning(f"获取股票{stock}分钟数据失败: {e}")
        
        # 条件4: 价格在分时均线之上
        if 'today_minute_data' in locals() and len(today_minute_data) > 5:
            minute_ma = today_minute_data['close'].rolling(window=5, min_periods=1).mean().iloc[-1]
            if current_price < minute_ma:
                return False
        
        log.info(f"股票 {stock} 符合买入条件，当前价: {current_price}, 涨幅: {daily_increase:.2%}, MA5: {ma5:.2f}, MA10: {ma10:.2f}")
        return True
        
    except Exception as e:
        log.error(f"检查股票{stock}时出错: {e}")
        return False

def buy_realtime_stocks(context, stock_list):
    """实时买入股票"""
    if not stock_list:
        return
    
    available_positions = g.stock_num - len(context.portfolio.positions)
    cash_per_stock = context.portfolio.available_cash / min(available_positions, len(stock_list))
    
    for stock in stock_list:
        if stock in context.portfolio.positions:
            continue
        
        current_data = get_current_data()[stock]
        if current_data is None:
            log.warning(f"无法获取股票{stock}的实时数据，跳过买入")
            continue
            
        current_price = current_data.last_price
        
        if current_price >= current_data.high_limit * 0.999:
            log.info(f"{stock} 已涨停，跳过买入")
            continue
        
        if current_price <= current_data.low_limit * 1.001:
            log.info(f"{stock} 跌停，跳过买入")
            continue
        
        amount = int(cash_per_stock / current_price / 100) * 100
    
        if amount >= 100:
            try:
                order_result = order(stock, amount)
                if order_result is not None:
                    log.info(f"买入 {stock}, 价格: {current_price}, 数量: {amount}, 金额: {amount * current_price:.2f}")
                    
                    g.positions_info[stock] = {
                        'buy_date': context.current_dt.date(),
                        'buy_price': current_price
                    }
                else:
                    log.warning(f"买入 {stock} 失败")
            except Exception as e:
                log.error(f"买入 {stock} 时出错: {e}")
        else:
            log.info(f"{stock} 买入金额不足，跳过")

# Category类
class Category:
    def __init__(self):
        warnings.filterwarnings('ignore')
        self.concept_category = self.stock_concepts_and_industry_ths_20240928()
    
    def stock_concepts_and_industry_ths_20240928(self):
        """读取同花顺概念库"""
        try:
            concept_stocks = pd.read_csv(BytesIO(read_file('cpt_ind_stocks.csv')))
            concepts = pd.read_csv(BytesIO(read_file('cpt_ind.csv')))
            
            merged_df = concept_stocks.merge(concepts[['Unnamed: 0', 'name', 'type']], 
                                           left_on='index', right_on='Unnamed: 0', how='left')
            merged_df['name'].fillna('未知概念/行业', inplace=True)
            
            merged_df['stock'] = merged_df['stock'].str.replace('.SZ', '.XSHE', regex=False)
            merged_df['stock'] = merged_df['stock'].str.replace('.SH', '.XSHG', regex=False)
            
            merged_df = merged_df[~merged_df['stock'].str.startswith(('8', '4'))]
            
            final_df = merged_df[['stock', 'name']]
            final_df.columns = ['code', 'category']
            return final_df
            
        except Exception as e:
            log.error(f"读取同花顺概念失败: {e}")
            return pd.DataFrame(columns=['code', 'category'])
    
    def score_by_return(self, stock_list=list(get_all_securities(['stock']).index), return_days=1, return_filter=0.099,
                        end_dt=dt.datetime.now(), count=60, debug=False):
        """对个股打分：按日拉涨幅攻击超过9个点（统计天数由count参数控制）"""
        stock_list = [stock for stock in stock_list if stock[0] != '4' and stock[0] != '8']
        
        if isinstance(end_dt, str):
            end_dt = dt.datetime.strptime(end_dt, '%Y-%m-%d')
        
        batch_size = 500
        all_dfs = []
        
        # 获取数据时多取1天，用于计算涨幅
        data_days_needed = count + return_days  # n+1天
        
        if debug:
            log.info(f"score_by_return: 需要获取{data_days_needed}天数据，从{end_dt.strftime('%Y-%m-%d')}往前推")
        
        for i in range(0, len(stock_list), batch_size):
            batch = stock_list[i:i+batch_size]
            try:
                # 获取end_dt（T-1日）往前n+1天的数据
                close = get_price(batch, end_date=end_dt, count=data_days_needed, 
                                fields=['close'], panel=True)['close']
                
                # 计算每日相对于前一天的涨幅
                df_return = (close / close.shift(return_days) - 1).iloc[return_days:]
                
                # 筛选涨幅>9%的股票
                df_filter = (df_return > return_filter).astype(int)
                
                # 转置，使行是股票，列是日期
                df_filter = df_filter.T
                
                all_dfs.append(df_filter)
                    
            except Exception as e:
                if debug:
                    log.warning(f"处理批次{i}时出错: {e}")
                continue
        
        if not all_dfs:
            return pd.DataFrame()
        
        # 合并所有批次的数据
        all_df = pd.concat(all_dfs, axis=0)
        
        # 确保日期列排序正确（从左到右日期递增）
        all_df = all_df.sort_index(axis=1)
        
        if debug and not all_df.empty:
            # 获取日期列名
            dates = all_df.columns.tolist()
            log.info(f"score_by_return: 计算得到的涨幅数据日期范围: 从{dates[0]}到{dates[-1]}, 共{len(dates)}天")
            
            # 显示数据结构信息
            log.info(f"score_by_return: DataFrame形状: {all_df.shape}, 列名示例: {dates[:3]}")
        
        return all_df
    
    def category_score_and_pct_attacking(self, df_score, df_category=None, count=60, daily_top_filter=30, top_N=10):
        """计算分类的得分和成分股数量"""
        if df_category is None or df_category.empty:
            return pd.DataFrame()
            
        code_category_dict = df_category.groupby('code').apply(lambda dx: list(dx['category'].unique())).to_dict()
        
        if df_score.empty:
            log.warning("df_score为空，无法计算板块热度")
            return pd.DataFrame()
        
        # 获取日期列，按日期排序（从左到右日期递增）
        dats = df_score.columns.tolist()
        
        # 只使用最近count天的数据
        if len(dats) > count:
            dats = dats[-count:]
            df_score = df_score[dats]
        
        log.info(f"计算板块热度，使用日期范围: {dats[0]} 到 {dats[-1]}, 共{len(dats)}天")
        
        dat_cat_dict = {}
        for i in range(0, len(dats)):
            date = dats[i]
            # 找出在特定日期涨幅>9%的股票
            codes = list(df_score[df_score[date] > 0].index)
            s_score = df_score[date]
            category_count_dict = {}
            
            for code in codes:
                if code in code_category_dict:
                    categories = code_category_dict[code]
                    for category in categories:
                        if category not in category_count_dict:
                            category_count_dict[category] = float(s_score[code])
                        else:
                            category_count_dict[category] += float(s_score[code])
            
            dat_cat_dict[date] = category_count_dict
        
        # 创建DataFrame，行是板块，列是日期
        df_category_score = pd.DataFrame.from_dict(dat_cat_dict, orient='index').fillna(0).T
        
        # 计算板块的股票数量
        stock_count_dict = df_category.groupby('category')['code'].nunique().to_dict()
        
        # 计算每个板块的总得分
        category_total_scores = df_category_score.sum(axis=1).reset_index()
        category_total_scores.columns = ['category', 'score']
        category_total_scores['stock_count'] = [stock_count_dict.get(category, 0) for category in category_total_scores['category']]
        
        # 按得分降序排列
        category_total_scores = category_total_scores.sort_values('score', ascending=False)
        
        log.info(f"热点板块统计（前{len(dats)}日累计得分）：")
        for idx, row in category_total_scores.head(10).iterrows():
            log.info(f"板块排名{idx+1}: {row['category']}, 累计得分: {row['score']:.2f}, 包含股票数: {row['stock_count']}")
        
        return category_total_scores
    
    def find_stocks_by_category(self, category_value, fuzzy_match=True):
        """查找包含指定概念的所有股票代码"""
        category_df = self.concept_category
        
        if category_df.empty:
            return []
        
        if fuzzy_match:
            filtered_df = category_df[category_df['category'].str.contains(category_value, case=False, na=False)]
        else:
            filtered_df = category_df[category_df['category'] == category_value]
        
        if filtered_df.empty:
            return []
        
        return filtered_df['code'].unique().tolist()

def stocks_score(category, context):
    """获取股票统计热点概念方式（使用T-1到T-n日数据，n=g.watch_days）"""
    e_date = g.end_date  # T-1日
    log.info(f"stocks_score: 计算板块热度，结束日期={e_date}, 统计天数={g.watch_days}")
    
    df_stock_score = category.score_by_return(
        return_days=1, 
        return_filter=0.09, 
        end_dt=e_date,  # T-1日
        count=g.watch_days,  # 使用全局变量g.watch_days
        debug=True
    )
    
    # 验证数据日期范围
    if not df_stock_score.empty:
        dates = df_stock_score.columns.tolist()
        log.info(f"板块热度计算使用的日期范围: 从{dates[0]}到{dates[-1]}, 共{len(dates)}天")
    
    return df_stock_score

def get_stock_name(stock_code):
    """获取股票名称"""
    security_info = get_security_info(stock_code)
    if security_info is not None:
        return security_info.display_name
    else:
        return 'Unknown'