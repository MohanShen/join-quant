# Clone from JoinQuant
# postId: b4089243c616b50b979c1947ea3f989c
# backtestId: 996b437e5f9c67ae993d41a08d9a6d41
# title: 模拟了一个月的策略，分享给大家，至少9收益为正，太难了

# 克隆自聚宽文章：https://www.joinquant.com/post/78185
# 标题：涨停先锋v0.11，年化500+→700+
# 作者：fs阿简

# 标题： 涨停先锋策略（v0.11）
# 作者：阿简
# ==================== v0.1 -> v0.11 优化清单 ====================
# 1.【修复】复权混用：全策略统一使用真实价格(fq=None)，消除前复权价与真实价混算偏差（选股/卖出的关键bug）
# 2.【修复】get_hot_concept 概念权重：首次出现也按连板数加权，不再固定=1
# 3.【修复】attribute_history 空数据处理：显式校验字段长度与NaN，不再依赖 len(dict)==0 的失效判断
# 4.【新增】情绪过滤：昨日涨停家数 + 最高连板高度，情绪退潮期空仓（开关 g.use_emotion_filter）
# 5.【新增】大盘趋势过滤：沪深300 MA5/MA20 弱市空仓（开关 g.use_market_signal，默认关）
# 6.【新增】09:45 硬止损：昨日持仓浮亏超阈值立即清仓（g.stop_loss_pct）
# 7.【新增】10:00 未成交补单：限价单未成交且未涨停时，撤单后市价补买，降低踏空
# 8.【优化】竞价低开止损改为阈值触发（g.low_open_pct 默认-1%，原为低开即卖）
# 9.【优化】涨停开板判定由固定3分钱改为百分比回落（g.kai_ban_pct 默认0.5%）
#10.【优化】创业板(30开头,20cm)高开区间单独参数化，与主板10cm区分
#11.【优化】当日最高价按日缓存合并，减少分钟数据请求
#12.【优化】全市场股票池按日期缓存，减少全市场 get_price 调用
#13.【优化】概念出现次数 occurrence 参数化（g.min_occurrence 默认1，原固定2）
#14.【清理】删除死代码（extract_concepts / get_init_emo_count / g.emo_count / date_1 等）
#15.【清理】静默异常改为打印日志，便于排查数据问题
# =================================================================

# 导入所需模块
from jqdata import *               # 聚宽数据接口
from jqfactor import *             # 因子相关
from jqlib.technical_analysis import *  # 技术分析库
import datetime as dt              # 日期时间处理
import pandas as pd                # 数据分析
import numpy as np                 # 数值计算

def initialize(context):
    # 系统设置
    set_option('use_real_price', True)       # 使用真实价格
    set_option('avoid_future_data', True)    # 避免未来数据
    set_option("match_by_signal", True)      # 信号匹配
    log.set_level('system', 'error')         # 只记录错误级别的系统日志
    # 设置交易费用（佣金、印花税等）
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='stock')

    # ==================== 策略参数 ====================
    g.buy_pct = 2                # 资金分配：总资金的 1/g.buy_pct 用于买入（分散到多只，原为2）
    g.jqfactor = 'VOL5'          # 排序因子：5日平均换手率（示例）
    g.sort = True                # True=升序取最小；方向可回测对比
    g.min_occurrence = 2         # 个股至少出现在几个热门概念中（原固定2，放宽为1）
    g.open_pct_min = 0.02        # 主板(10cm)高开下限 2%
    g.open_pct_max = 0.08        # 主板(10cm)高开上限 8%
    g.open_pct_min_gem = 0.02    # 创业板(20cm)高开下限 3%
    g.open_pct_max_gem = 0.08    # 创业板(20cm)高开上限 12%
    g.low_open_pct = -0.001       # 竞价止损：低开超过0.1%才卖（设0=恢复原"低开即卖"）
    g.kai_ban_pct = 0.0005        # 涨停开板判定：回落超过0.05%视为开板（原固定3分钱）
    g.stop_loss_pct = -0.05      # 09:45 硬止损线：浮亏超过5%清仓
    g.use_emotion_filter = False  # 情绪过滤开关，默认开
    g.min_hl_count = 15          # 情绪过滤：昨日涨停家数下限
    g.min_max_count = 3          # 情绪过滤：昨日最高连板高度下限
    g.use_market_signal = False  # 大盘趋势过滤开关（默认关）

    # 运行时状态
    g.target_list = []           # 当日目标买入列表
    g.order_value = {}           # 每只目标股的计划买入金额（补单用）
    g.day_high = {}              # 当日最高价缓存
    g.day_high_date = None
    g.all_list = None            # 全市场股票池缓存
    g.all_list_date = None

    # 每日定时任务
    run_daily(get_stock_list, '09:25:45')    # 选股
    run_daily(sell_check_open, '09:27')      # 竞价低开止损
    run_daily(buy, '09:30:00')               # 开盘价限价买入
    #run_daily(sell_check_stop, '09:45')      # 硬止损
    #run_daily(check_unfilled, '10:00')       # 未成交补单
    run_daily(sell_check_morning, '10:30')   # 早盘卖出（开板/止盈止损）
    run_daily(sell_check_afternoon, '14:30') # 尾盘卖出
    run_daily(print_position_info, '15:02')  # 打印持仓

# ---------- 选股 ----------
def get_stock_list(context):
    # 上一交易日（选股基准日）
    date = transform_date(context.previous_date, 'str')

    # 初始股票列表（经过过滤）
    initial_list = prepare_stock_list(date)
    # 昨日涨停股票
    hl_list = get_hl_stock(initial_list, date)
    # 连板统计（连板天数、一字板天数）
    ccd_hl = get_continue_count_df(hl_list, date, 20) if len(hl_list) != 0 else pd.DataFrame(index=[], data={'count':[],'extreme_count':[]})

    # ============ 情绪过滤（复用已有数据，情绪退潮期空仓） ============
    hl_count = len(hl_list)
    max_count = int(ccd_hl['count'].max()) if len(ccd_hl) != 0 else 0
    if g.use_emotion_filter and (hl_count < g.min_hl_count or max_count < g.min_max_count):
        log.info(f'【情绪过滤】昨日涨停 {hl_count} 家 / 最高 {max_count} 板，低于阈值({g.min_hl_count}家/{g.min_max_count}板)，今日空仓')
        g.target_list = []
        return
    if g.use_market_signal and not market_signal(context):
        log.info('【大盘过滤】沪深300 趋势走弱，今日空仓')
        g.target_list = []
        return

    # 龙头候选（连板天数 >= 2）
    ccd_lb = ccd_hl[ccd_hl['count']>=2]
    lt_lb = list(ccd_lb.index)             # 龙头股列表
    # 获取这些涨停股票所属的概念
    dct = get_concept(lt_lb, date) if len(lt_lb) != 0 else {}
    # 获取热门概念（连板数加权前5）
    hot_concepts = get_hot_concept(dct, ccd_lb, date)

    combined_df = pd.DataFrame(index=[], data={'count':[],'extreme_count':[]})
    for concept in hot_concepts:
        hot_stocks = get_stocks_by_concept_name(concept)   # 热门概念下的所有股票
        hot_stocks = filter_stock_list(hot_stocks, date)   # 过滤（剔除ST、停牌等）
        hl_hot_list = list(set(hl_list) & set(hot_stocks)) # 热门概念中昨日涨停的股票
        ccd = ccd_hl[ccd_hl.index.isin(hl_hot_list)]
        combined_df = pd.concat([combined_df, ccd], ignore_index=False)

    # 统计每只股票在热门概念中出现的次数
    occurrence_count = combined_df.groupby(combined_df.index).size()
    final_df = combined_df[~combined_df.index.duplicated(keep='last')].copy()   # 显式拷贝，避免对切片视图赋值触发 SettingWithCopyWarning
    final_df.loc[:, 'occurrence'] = final_df.index.map(occurrence_count)
    # 筛选：出现次数 >= min_occurrence，且一字板占比 <= 66%
    final_df = final_df[(final_df['occurrence']>=g.min_occurrence) & (final_df['extreme_count']/final_df['count']<=0.66)]
    final_df = final_df.sort_values('count', ascending=False)  # 按连板天数降序
    lt = list(final_df.index)   # 最终龙头股列表

    # 龙头特征选股：检查开盘涨幅和价格位置（真实价格体系，fq=None）
    stock_list = []
    current_data = get_current_data()
    for s in lt:
        try:
            # 获取上一交易日的历史数据（fq=None 真实价，与 day_open 基准一致）
            hist = attribute_history(
                security=s,
                count=1,
                unit='1d',
                fields=('close', 'low', 'high', 'paused', 'high_limit'),
                skip_paused=False,
                df=False,
                fq=None
            )
            if hist is None or 'close' not in hist or len(hist['close']) == 0 or pd.isna(hist['close'][-1]):
                log.info(f'【跳过】{s} 昨日收盘数据为空（可能停牌/复权异常）')
                continue
            prev_close = hist['close'][-1]
            # 计算开盘涨幅
            pct_chg = (current_data[s].day_open - prev_close) / prev_close

            # 按板块选择高开区间：创业板20cm与主板10cm分开
            if s[:2] == '30':
                pct_min, pct_max = g.open_pct_min_gem, g.open_pct_max_gem
            else:
                pct_min, pct_max = g.open_pct_min, g.open_pct_max

            # 高开在区间内，且开盘价低于涨停价至少3分钱（留有空间）
            if (pct_min <= pct_chg <= pct_max) and (current_data[s].day_open <= current_data[s].high_limit - 0.03):
                stock_list.append(s)
        except Exception as e:
            log.info(f'【跳过】{s} 异常: {type(e).__name__}: {str(e)}')
    log.info('候选代码:{}'.format(stock_list))

    # 因子筛选（使用换手率因子）
    df = get_factor_filter_df(context, stock_list, g.jqfactor, g.sort)
    stock_list = list(df.index)
    log.info('因子筛选后:{}'.format(stock_list))

    hold_list = list(context.portfolio.positions)   # 当前持仓
    # 目标买入列表 = 选出的股票中未持有的
    g.target_list = [x for x in stock_list if x not in hold_list]

# ---------- 买入 ----------
def buy(context):
    """09:30 以开盘价限价买入"""
    current_data = get_current_data()
    g.order_value = {}
    if len(g.target_list) > 0:
        # 计算总可用资金（总资金的 1/g.buy_pct）
        value1 = context.portfolio.total_value / g.buy_pct
        # 每只股票分配的资金 = min(总现金, 计划资金) / 目标股票数量
        value = min(context.portfolio.available_cash, value1) / len(g.target_list)
        g.order_value = {s: value for s in g.target_list}   # 记录计划金额（补单用）

        for s in g.target_list:
            # 跳过停牌、ST、退市股票
            if current_data[s].paused or 'ST' in current_data[s].name or '退' in current_data[s].name:
                log.info(f'跳过买入: {s} ({current_data[s].name}) 停牌或ST/退市')
                continue
            # 确保买入数量至少100股
            if context.portfolio.available_cash / current_data[s].last_price > 100:
                # 以当日开盘价限价买入
                order_value(s, value, LimitOrderStyle(current_data[s].day_open))
                log.info('买入(开盘价限价): ' + s)

def check_unfilled(context):
    """10:00 检查未成交买单：撤销原限价单，未涨停则市价补买（降低踏空）"""
    if not g.target_list:
        return
    current_data = get_current_data()
    unfilled = [s for s in g.target_list if s not in context.portfolio.positions]
    if not unfilled:
        return
    open_orders = get_open_orders()
    for s in unfilled:
        cd = current_data[s]
        if cd.paused or 'ST' in cd.name or '退' in cd.name:
            continue
        # 撤销该股未完成的限价委托，避免重复买入
        for o in open_orders:
            if o.security == s:
                cancel_order(o)
        # 已涨停不追高
        if cd.last_price >= cd.high_limit - 0.01:
            log.info(f'补单跳过: {s} 已涨停，不追高')
            continue
        # 补买金额：不超过计划金额，同时按剩余未买数分摊可用现金
        remaining = max(len([x for x in unfilled if x != s]), 1)
        value = min(g.order_value.get(s, 0), context.portfolio.available_cash / remaining)
        if value > 0 and context.portfolio.available_cash / cd.last_price > 100:
            order_value(s, value, MarketOrderStyle())
            log.info(f'补单买入(市价): {s} 金额 {value:.0f}')

# ---------- 工具函数 ----------
def transform_date(date, date_type):
    """日期格式转换：支持 str、datetime、date 之间互转"""
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

def get_shifted_date(date, days, days_type='T'):
    """
    健壮的日期偏移函数，自动扩大缓冲区直到成功
    days_type: 'N' 自然日偏移, 'T' 交易日偏移
    """
    d_date = transform_date(date, 'd')
    if days_type == 'N':
        shifted = d_date + dt.timedelta(days=days)
        return transform_date(shifted, 'str')
    else:  # 交易日偏移
        buffer = abs(days) + 50  # 初始缓冲区（比需要多50天）
        while True:
            start = d_date - dt.timedelta(days=buffer)
            end = d_date + dt.timedelta(days=buffer)
            trade_days = list(get_trade_days(start_date=start, end_date=end))
            if len(trade_days) == 0:
                buffer += 10
                continue
            # 如果基准日期不是交易日，向前找到最近一个交易日
            base_date = d_date
            if base_date not in trade_days:
                found = False
                for i in range(1, buffer + 1):
                    candidate = d_date - dt.timedelta(days=i)
                    if candidate in trade_days:
                        base_date = candidate
                        found = True
                        break
                if not found:
                    buffer += 10
                    continue
            try:
                idx = trade_days.index(base_date)
            except ValueError:
                buffer += 10
                continue
            shifted_idx = idx + days
            if shifted_idx < 0 or shifted_idx >= len(trade_days):
                buffer += 10
                continue
            shifted_date = trade_days[shifted_idx]
            return shifted_date.strftime('%Y-%m-%d')

# ---------- 股票过滤 ----------
def filter_new_stock(initial_list, date, days=50):
    """过滤上市时间不足 days 天的次新股"""
    d_date = transform_date(date, 'd')
    return [stock for stock in initial_list if d_date - get_security_info(stock).start_date > dt.timedelta(days=days)]

def filter_st_stock(initial_list, date):
    """过滤 ST、*ST 股票"""
    str_date = transform_date(date, 'str')
    # 如果当天非交易日，则取前一个交易日
    if get_shifted_date(str_date, 0, 'N') != get_shifted_date(str_date, 0, 'T'):
        str_date = get_shifted_date(str_date, -1, 'T')
    df = get_extras('is_st', initial_list, start_date=str_date, end_date=str_date, df=True)
    df = df.T
    df.columns = ['is_st']
    df = df[df['is_st'] == False]
    return list(df.index)

def filter_kcbj_stock(initial_list):
    """过滤北交所（4/8开头）和科创板（68开头）股票（本策略只做主板的10cm与创业板的20cm）"""
    return [stock for stock in initial_list if stock[0] != '4' and stock[0] != '8' and stock[:2] != '68']

def filter_paused_stock(initial_list, date):
    """过滤当日停牌的股票"""
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['paused'], count=1, panel=False, fill_paused=True, fq=None)
    df = df[df['paused'] == 0]
    return list(df.code)

def filter_name_stock(initial_list):
    """过滤名称包含 ST、*ST、退 的股票（二次过滤）"""
    current_data = get_current_data()
    filtered_list = []
    for s in initial_list:
        name = current_data[s].name
        if 'ST' not in name and '※ST' not in name and '退' not in name:
            filtered_list.append(s)
    return filtered_list

def filter_stock_list(stock_list, date):
    """综合过滤：依次应用各类过滤器"""
    if not stock_list:
        return []
    stock_list = filter_kcbj_stock(stock_list)
    stock_list = filter_new_stock(stock_list, date)
    stock_list = filter_st_stock(stock_list, date)
    stock_list = filter_paused_stock(stock_list, date)
    stock_list = filter_name_stock(stock_list)
    return stock_list

def prepare_stock_list(date):
    """获取经过基本过滤的全部股票列表（按日期缓存，减少全市场请求）"""
    if g.all_list is not None and g.all_list_date == date:
        return g.all_list
    initial_list = get_all_securities('stock', date).index.tolist()
    result = filter_stock_list(initial_list, date)
    g.all_list = result
    g.all_list_date = date
    return result

# ---------- 情绪与概念 ----------
def market_signal(context):
    """判断市场趋势：沪深300指数在20日均线上方且收盘价在5日均线上方"""
    #prices = attribute_history('000300.XSHG', 60, '1d', fields=['close'], skip_paused=True, fq=None)
    prices = attribute_history('399317.XSHE', 60, '1d', fields=['close'], skip_paused=True, fq=None)
    if len(prices) < 60:
        return False
    #ma5 = prices['close'].rolling(window=5).mean()
    ma20 = prices['close'].rolling(window=20).mean()
    #return (ma5[-1] > ma20[-1] and prices['close'][-1] > ma5[-1])
    return  prices['close'][-1] > ma20[-1]

def get_hot_concept(dct, ccd, date):
    """计算热门概念：根据龙头股的连板数加权，返回前5个热门概念"""
    concept_count = {}
    for key in dct:
        try:
            lb_count = int(ccd.loc[key, 'count'])   # 连板天数
        except (KeyError, TypeError, ValueError):
            continue
        for i in dct[key]['jq_concept']:
            name = i['concept_name']
            # 排除一些常见但可能无意义的宽基概念
            if name in ['转融券标的', '融资融券', '深股通', '沪股通', '国企改革']:
                continue
            concept_count[name] = concept_count.get(name, 0) + lb_count
    df = pd.DataFrame(list(concept_count.items()), columns=['concept_name', 'concept_count'])
    df = df.set_index('concept_name')
    df = df.sort_values(by='concept_count', ascending=False)
    concept = list(df.index)[0:5]   # 取前5
    log.info('热门概念:{}'.format(concept))
    return concept

def get_stocks_by_concept_name(concept_name):
    """根据概念名称获取该概念下的所有股票代码"""
    df_concepts = get_concepts()
    concept_code = df_concepts[df_concepts['name'] == concept_name].index
    if len(concept_code) == 0:
        log.info(f"警告：概念 '{concept_name}' 不存在，已跳过")
        return []
    try:
        stocks = get_concept_stocks(str(concept_code[0]))
        return stocks
    except Exception as e:
        error_type = type(e).__name__
        log.info(f"[错误] 获取概念股票失败 | 概念: {concept_name} | 错误类型: {error_type} | 详情: {str(e)}")
        return []

def get_hl_stock(initial_list, date):
    """获取当日涨停的股票（收盘价等于涨停价，真实价格体系）"""
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False, fq=None)
    df = df.dropna()
    df = df[df['close'] == df['high_limit']]
    return list(df.code)

def get_continue_count_df(hl_list, date, watch_days):
    """计算涨停股票的连板天数及一字板天数（真实价格体系）"""
    if not hl_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    df = get_price(hl_list, end_date=date, frequency='daily',
                   fields=['close', 'high_limit', 'low'], count=watch_days,
                   panel=False, fill_paused=False, skip_paused=False, fq=None)
    if df.empty:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    results = []
    for stock in hl_list:
        stock_df = df[df['code'] == stock].copy()
        stock_df = stock_df.sort_values('time', ascending=False)  # 按日期倒序
        stock_df.reset_index(drop=True, inplace=True)
        consecutive_count = 0   # 连续涨停天数
        extreme_count = 0       # 一字板天数（最低价等于涨停价）
        for i in range(len(stock_df)):
            row = stock_df.iloc[i]
            if pd.isna(row['close']) or pd.isna(row['high_limit']):
                break
            if row['close'] == row['high_limit']:
                consecutive_count += 1
                if row['low'] == row['high_limit']:
                    extreme_count += 1
            else:
                break
        if consecutive_count > 0:
            results.append({
                'code': stock,
                'count': consecutive_count,
                'extreme_count': extreme_count
            })
    result_df = pd.DataFrame(results)
    if not result_df.empty:
        result_df.set_index('code', inplace=True)
    return result_df

def get_factor_filter_df(context, stock_list, jqfactor, sort):
    """根据因子值对股票列表排序"""
    if len(stock_list) != 0:
        yesterday = context.previous_date
        score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
        df = pd.DataFrame(index=stock_list, data={'score': score_list}).dropna()
        df = df.sort_values(by='score', ascending=sort)  # sort=True 升序，取最小
    else:
        df = pd.DataFrame(index=[], data={'score': []})
    return df

# ---------- 辅助函数：获取当日最高价（分钟数据，按日缓存） ----------
def get_today_high(stock, context):
    """
    获取股票当天截至当前时间的最高价（同日内合并最大值，减少请求量）
    """
    if g.day_high_date != context.current_dt.date():
        g.day_high = {}
        g.day_high_date = context.current_dt.date()
    # 获取当天从开盘到现在的分钟数据
    df = get_price(stock, start_date=context.current_dt.date(), end_date=context.current_dt,
                   frequency='1m', fields=['high'], skip_paused=True, panel=False, fq=None)
    if df is not None and not df.empty:
        high = df['high'].max()
    else:
        # 如果没有分钟数据（可能刚开盘或停牌），返回当前价
        high = get_current_data()[stock].last_price
    if stock in g.day_high:
        high = max(high, g.day_high[stock])
    g.day_high[stock] = high
    return high

# ==============================================================================
# 1. 竞价低开卖出（09:27）
# ==============================================================================
def sell_check_open(context):
    """09:27 检查竞价情况，低开超过阈值则卖出（阈值可配，默认-1%）"""
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0: continue

        open_price = current_data[stock].day_open
        hist = attribute_history(stock, 1, '1d', ['close'], skip_paused=False, fq=None)
        if hist is None or 'close' not in hist or len(hist['close']) == 0 or pd.isna(hist['close'][0]):
            continue
        prev_close = hist['close'][0]

        # 跌停无法卖出
        if abs(open_price - current_data[stock].low_limit) < 0.001:
            log.info(f'【竞价止损】{stock} 跌停，无法卖出')
            continue
        # 低开超过阈值才卖（避免噪音换手）
        if open_price < prev_close * (1 + g.low_open_pct):
            log.info(f'【竞价止损】{stock} 低开 {open_price/prev_close-1:.2%}（阈值{g.low_open_pct:.1%}），清仓')
            order_target(stock, 0)

# ==============================================================================
# 2. 硬止损（09:45）
# ==============================================================================
def sell_check_stop(context):
    """09:45 硬止损：昨日持仓浮亏超过阈值立即清仓，防止10:30前亏损扩大"""
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0: continue

        curr_price = current_data[stock].last_price
        low_limit = current_data[stock].low_limit
        if abs(curr_price - low_limit) < 0.001:
            continue  # 跌停无法卖出
        avg_cost = context.portfolio.positions[stock].avg_cost
        pnl_ratio = (curr_price - avg_cost) / avg_cost
        if pnl_ratio < g.stop_loss_pct:
            log.info(f'【硬止损】{stock} 浮亏 {pnl_ratio:.2%} 超阈值 {g.stop_loss_pct:.2%}，清仓')
            order_target(stock, 0)

# ==============================================================================
# 3. 早盘卖出（10:30）- 动态开板止盈 + 亏损清仓/盈利减半
# ==============================================================================
def sell_check_morning(context):
    """10:30 检查持仓：涨停开板则立即卖出，否则根据盈亏情况减仓或清仓"""
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0: continue

        curr_price = current_data[stock].last_price
        high_limit = current_data[stock].high_limit
        low_limit  = current_data[stock].low_limit
        avg_cost = context.portfolio.positions[stock].avg_cost

        # 获取当日最高价（缓存合并）
        day_high = get_today_high(stock, context)

        # --- 动态止盈：曾触板且回落超过 kai_ban_pct（百分比，代替固定3分钱） ---
        if day_high >= high_limit - 0.01 and curr_price < high_limit * (1 - g.kai_ban_pct):
            log.info(f'【动态止盈】{stock} 涨停开板(回落>{g.kai_ban_pct:.1%})，清仓')
            order_target(stock, 0)
            continue

        # --- 10:30 常规逻辑 ---
        is_limit = curr_price >= (high_limit - 0.01)   # 是否仍封涨停
        if is_limit:
            log.info(f'【10:30持仓】{stock} 封板中，继续持有')
            continue
        else:
            if abs(curr_price - low_limit) < 0.001:
                log.info(f'{stock} 跌停，无法卖出')
                continue
            pnl_ratio = (curr_price - avg_cost) / avg_cost
            if pnl_ratio < 0:
                log.info(f'【10:30止损】{stock} 未涨停且亏损 ({pnl_ratio:.2%})，清仓')
                order_target(stock, 0)
            else:
                # 盈利但未涨停，卖出一半
                target_amount = int(amount / 2 / 100) * 100
                if target_amount < 100:
                    order_target(stock, 0)
                    log.info(f'【10:30止盈】{stock} 盈利且股数过少，全卖')
                else:
                    order_target(stock, target_amount)
                    log.info(f'【10:30止盈】{stock} 未涨停但盈利 ({pnl_ratio:.2%})，卖出一半')

# ==============================================================================
# 4. 尾盘卖出（14:30）- 动态开板检查 + 未封板清仓
# ==============================================================================
def sell_check_afternoon(context):
    """14:30 检查持仓：若未封板则清仓，若开板也清仓；封板持有过夜"""
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0: continue

        curr_price = current_data[stock].last_price
        high_limit = current_data[stock].high_limit
        low_limit  = current_data[stock].low_limit

        # 获取当日最高价（缓存合并）
        day_high = get_today_high(stock, context)

        # 同样检查开板情况（尾盘开板更要走）
        if day_high >= high_limit - 0.01 and curr_price < high_limit * (1 - g.kai_ban_pct):
            log.info(f'【尾盘动态】{stock} 涨停开板(回落>{g.kai_ban_pct:.1%})，清仓')
            order_target(stock, 0)
            continue

        is_limit = curr_price >= (high_limit - 0.01)
        if is_limit:
            log.info(f'【14:30持仓】{stock} 尾盘封板，持有过夜')
        else:
            if abs(curr_price - low_limit) < 0.001:
                log.info(f'{stock} 跌停，无法卖出')
                continue
            log.info(f'【14:30清仓】{stock} 尾盘未封板，离场')
            order_target(stock, 0)

# ==============================================================================
# 5. 打印持仓信息
# ==============================================================================
def print_position_info(context):
    """收盘后打印持仓详情：每个标的一行 + 组合汇总（总资产/总收益/总收益率等）"""
    total_value = context.portfolio.total_value
    positions_value = context.portfolio.positions_value
    available_cash = context.portfolio.available_cash
    starting_cash = context.portfolio.starting_cash
    total_return = total_value - starting_cash
    total_return_pct = context.portfolio.returns

    lines = []
    lines.append('【盘后持仓】日期:{} | 总资产:{:.2f} | 持仓市值:{:.2f} | 可用现金:{:.2f} | 总收益:{:+.2f} ({:+.2%})'.format(
        context.current_dt.strftime('%Y-%m-%d'), total_value, positions_value, available_cash,
        total_return, total_return_pct))
    if len(context.portfolio.positions) == 0:
        lines.append('（空仓）')
    else:
        lines.append('{:<12}{:<10}{:>8}{:>8}{:>10}{:>8}{:>10}'.format('代码', '名称', '成本价', '现价', '收益率', '持仓', '市值'))
        for position in context.portfolio.positions.values():
            securities = position.security
            try:
                name = get_security_info(securities).display_name
            except Exception:
                name = ''
            cost = position.avg_cost
            price = position.price
            ret = (price / cost - 1) * 100
            value = position.value
            amount = position.total_amount
            lines.append('{:<12}{:<10}{:>8.2f}{:>8.2f}{:>+9.2f}%{:>8}{:>10.2f}'.format(securities, name, cost, price, ret, amount, value))
    log.info(chr(10).join(lines))
    log.info('———————————————————————————————————————分割线————————————————————————————————————————')
