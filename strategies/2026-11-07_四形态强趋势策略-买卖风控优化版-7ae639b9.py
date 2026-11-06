# Clone from JoinQuant
# postId: 7ae639b9cef527232531f1b29cd6df5d
# backtestId: f6d56adab7c63e659415d5be3764756f
# title: 四形态强趋势策略-买卖风控优化版

# 克隆自聚宽文章：https://www.joinquant.com/post/81348
# 标题：战法三：双创恐慌低吸策略，需要择时，7月翻倍策略
# 作者：Grd2880278

# -*- coding: utf-8 -*-
"""
四形态强趋势策略-买卖风控优化版

一、投资范围与信号时点
策略在历史中证1000成分股中寻找放量突破、主升浪回踩、缩量回调和多头排列。
基础股票池排除科创板、北交所、上市不超过50个自然日、ST及停牌股票。
形态指标使用截至上一交易日的已完成日线，当日开盘价仅用于开盘强度确认。
热门概念来自昨日涨停股和当日已完成集合竞价近涨停股的概念排名，各取前4名，
合并后最多8个概念，股票必须命中概念池。
竞价接口按当日日期查询，采用09:25起、09:30前且不晚于当前逻辑时刻的记录；
排除其他日期、尚未发生和非开盘时段数据，并输出实际时间范围与覆盖数量。
数据获取失败时暂停新增买入。


二、四类入场形态
优先级：放量突破 → 主升浪回踩 → 缩量回调 → 多头排列；同级按分数降序、
证券代码升序排列。一只股票只归属第一个完整满足的形态，每日仅前5名入围。

放量突破：昨日涨幅>4%、量比>1.3、均线集中度<0.025、相对MA20角度>25度；
当日高开3%至7%。附加条件衡量均线扩张、阳线实体、阳包阴、收盘位置、
近期连续增量和已完成两日的量能脉冲确认。

主升浪回踩：昨日收盘>MA5>MA10>MA20、距离MA10不足3%、MA20斜率>0、
量比<0.8；当日高开>1%。附加条件衡量下影线、收盘位置、均线扩张、
MA20支撑空间、量能下限及短均线斜率。

缩量回调：昨日收盘低于MA10约2%至5%、同时高于MA20、RSI介于45和60；
当日高开>1%。附加条件衡量均线支撑、缩量、下影线、量能脉冲、收盘位置
以及MA5相对MA10的斜率。前三类均要求核心条件全部满足，六项附加条件
至少满足四项；分数=75+25×附加条件满足数/6。

多头排列：MA5>MA10>MA20、量比>1.2、当日高开>1.5%；另要求五项中
至少满足四项：高开<5%、5日均量>20日均量、昨收>MA5、上影线占比<0.3、
MACD柱为正。分数=90+2×附加条件满足数。

均线频繁交叉、RSI在中性区域低波动且近10日窄幅横盘同时出现时不入围。
“突破、回踩、回调”等名称代表价格和成交量规则，不代表对资金意图的判断。

三、固定名额与资金预算
单账户固定5个持仓名额、5名候选、单笔预算分母5。市场仓位系数r只缩放
资金，不缩减名额：单只标准预算=账户净值×r/5，账户股票目标敞口上限=净值×r。
真实持仓和尚未终结的买单共同占用名额及敞口；未成交不等于释放名额。
单笔金额同时受剩余敞口、实际可用现金、100股整手和佣金约束，现金不足时
预留实际所需佣金。不自动补足旧仓，不因新候选替换旧仓，不用第6名以后股票补位。
5只表示最多5只，并非要求每天满仓；r=0时不新买。

四、市场仓位评分与指数风控
使用上证指数截至昨日的日线。趋势原始分最高70，按40/70归一到40分；
动量最高30分、波动最高20分、市场结构最高10分，合计最高100分。
动量计算使用充分预热的历史日线并验证RSI和MACD有效值。
昨日涨停家数先准备完成，再参与市场结构评分；没有有效数据时不新买。
指数短期ATR相对长期ATR放大时降低资金系数。近3日若至少2日出现指数
下跌且成交量较前一日增加超过10%，盘前系数上限30%。
盘中指数相隔10分钟跌幅超过1.5%，当日风险上限收紧到30%；上午指数
相对昨收跌幅超过1.5%，收紧到50%。当日取最严格上限，撤待买单并尝试
减少普通持仓。强趋势持仓豁免主动减仓，但仍占用持仓名额和总资金预算。
强趋势豁免、T+1、停牌、跌停及未成交可使实际敞口暂时超过目标。

五、普通持仓退出与ATR跟踪
持有天数从首次真实买入成交日开始计算，该日为第1个交易日。
ATR周期14：第1至第3个持有交易日使用1.8倍，第4日起使用1.5倍。
止损线=max(已有止损线，持仓跟踪高点−对应倍数×当日ATR)，同一价格基准
下只上移。开盘起维护已完成行情中的高点；ATR退出从10:00起判断，
10:00前不触发、不预先锁存ATR退出。当天新买受T+1限制，仍维护高点。
ATR以已完成日线计算并在日内缓存；除权除息时同步调整高点和止损价格基准。

普通持仓的其他退出独立生效：相对昨收低开6%及以上；持有达到第10个交易日；
14:30后接近跌停；至少3只持仓属于同一概念且当日曾触及涨停、当前打开；
以及指数风险超出目标敞口。开盘涨停不豁免后续退出监控。
有效卖出信号保留到真实退出，未成交或部分成交继续管理剩余持仓，盘中持续监控
到14:59，收盘后仍核对订单和成交。停牌及T+1期间不提交不可卖数量。

六、强趋势持仓与独立退出
盘前持有至少4个交易日，且昨收相对平台持仓成本浮盈达到22.4%时标记为
强趋势；创业板300、301开头证券门槛为22.9%。使用昨日已完成收盘，不以
今日盘中浮盈授予资格；缺数不推断。标记持续至真实清仓，不因浮盈回落取消。

强趋势豁免普通ATR、低开6%、持有到期、尾盘接近跌停、概念退出与指数主动
减仓，只在14:54产生强趋势走弱退出信号。以下七项任一满足即退出：
A. 当前价相对昨收跌幅>7%。
B. 当前价距当日已核验高点回落>9%。
C. 当日振幅=(已核验高点−低点)/昨收>12%，且当前价<开盘×0.975、当前价<昨收。
D. 当前价相对强趋势标记前一交易日起累计收盘高点回撤>13%。
E. 持有期间截至当前报价连续下跌至少4日，连续下跌区间复合跌幅>8.5%。
F. 当前价≤临时MA10×0.97；临时MA10=(过去9个完整交易日收盘之和+当前价)/10。
G. 当前价≤临时MA20×0.985；临时MA20=(过去19个完整交易日收盘之和+当前价)/20。
日内极值由截至前一分钟的完整分钟数据与已知开盘、当前报价核验；收盘历史
仅截至昨日，统一到当前前复权基准。部分数据缺失时，只执行证据完整的独立条件。
14:54确认的有效退出，在后续分钟和交易日继续尝试剩余数量，不限于再次14:54。

强趋势标记期间，最近两个完整交易日连续一字涨停后，当日首次核验开板则
当天豁免全部强趋势退出；当日回封不取消豁免，下一交易日恢复正常强趋势检查。
一字涨停用原始OHLC与各日涨停价比较，停牌或缺失数据不推断；09:30及以前
只以已知开盘价判断是否开板，不将可能仍为昨收的last_price当作开板证据。
进入强趋势时撤销失效的普通退出意图；开板豁免时撤销失效的强趋势退出意图。
只对未成交余单申请撤单，确认前保持订单占用，已发生的成交不撤回、不改写。

七、真实订单与成交账本
09:28按目标金额提交买入委托，使用order_target_value的默认下单方式。
盘前最新价可以仍是昨收，不要求它与开盘价相等，不附加上浮限价。
开盘接近涨停时优先检查tick盘口，无权限或查询异常时回退到开盘价判断；
已涨停、停牌、ST/退市或资金不足时不提交买单。
单只目标金额按净值乘仓位系数再除以5，并受剩余敞口、现金和佣金约束。
委托数量以平台Order.amount为准；目标金额用于预算，并非成交价格上限。
盘前报单的两分钟超时从09:30起计算，只向平台当前未完成订单申请撤单。
已完成但逐笔回报尚未到齐的订单继续对账，不再次撤单；部分成交保留余单占用。
买卖均依平台撮合执行。成交价、成交量、首次买入日期仅由Trade回报建立，Order用于
跟踪委托、已报成交数量和终态，Position用于核对实际剩余持仓。
订单提交、撤单申请和退出信号都不是成交。部分成交逐笔去重入账；只有
真实持仓为零、相关订单终态且成交对账完整，才结束该持仓的策略状态。
订单超时申请撤单，确认前继续占用预算。无法核对的订单或持仓暂停新增，
不会删除实际持仓。手续费和最终净收益以平台成交及账户报告为准。

八、运行安排与费用
使用分钟级回测或模拟：09:24市场准备；09:25:45选股；09:27检查低开6%；
09:28提交入围股买单，实际成交时刻以平台Trade为准；11:30午间风险；
盘中逐分钟同步订单和管理退出至14:59；14:54检查强趋势；15:10汇总及对账。
收盘集合竞价阶段采用适用的限价委托，并等待平台最终成交或撤销结果。
开启动态复权和未来数据检查，使用match_by_signal=True撮合设置。
这一回测撮合模式可能在盘前使用当时的最新参考价格，不代表现实市场能在该价格成交。
委托参考价与平台Trade分别输出，持仓账本始终按平台回报建立，不由日志报价推定成交。
该设置作用于账户买卖撮合，退出条件与时点仍由普通和强趋势规则决定。
佣金双向万三、每笔最低5元；
卖出印花税按日期设置，2023-08-28起万五，之前使用千一口径。
固定滑点配置为价差0.005元；撮合设置决定其适用方式，成交以平台回报为准。
"""

from jqdata import *
import datetime as dt
import math
import time
import copy
import builtins as _builtins
from collections import defaultdict
import numpy as np
import pandas as pd
import talib

# 数值归约统一使用Python内置函数，避免平台通配导入改变生成器的求值行为。
min, max, sum = _builtins.min, _builtins.max, _builtins.sum
any, all, abs, round = _builtins.any, _builtins.all, _builtins.abs, _builtins.round


def log_event(tag, message):
    log.info('【%s】%s' % (tag, message))


def is_finite_positive(value):
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def get_quote(context, stock):
    """同一逻辑时刻复用纯数值行情快照，不跨分钟保存动态行情对象。"""
    stamp = str(context.current_dt)
    if getattr(g, '_quote_stamp', None) != stamp:
        g._quote_stamp = stamp
        g._quote_cache = {}
    stock = str(stock)
    if stock not in g._quote_cache:
        value = get_current_data([stock])[stock]
        def number(field):
            try:
                return float(getattr(value, field, float('nan')))
            except (TypeError, ValueError, OverflowError):
                return float('nan')
        g._quote_cache[stock] = dict(
            last=number('last_price'), open=number('day_open'),
            high_limit=number('high_limit'), low_limit=number('low_limit'),
            paused=bool(getattr(value, 'paused', False)),
            is_st=bool(getattr(value, 'is_st', False)),
            name=str(getattr(value, 'name', stock)))
    return dict(g._quote_cache[stock])


def is_trading_time(context):
    clock = context.current_dt.strftime('%H:%M')
    return ('09:30' <= clock < '11:30') or ('13:00' <= clock < '15:00')


import builtins as _selection_builtin
import datetime as _selection_datetime
import time as _selection_time


# 股票池与形态选择
# 基础范围为昨日仍上市的股票，上市超过50个自然日，排除ST、退市、停牌及科创/北交标的。
# 市场热度在基础全市场计算，实际候选再与昨日中证1000成分股取交集。
# 热门概念为昨日收盘涨停概念前4与今日已完成开盘竞价概念前4的并集。
# 每个股票在同一概念只计一次；概念关系统一查询昨日日期，名称只作展示，匹配使用概念代码。
# 全部形态指标来自截至昨日的日线；今日已知开盘价只用于开盘涨幅确认。
# 入围固定为形态优先级、原分降序、股票代码升序排序后的前5名，不因无法买入而追加候补。


class SelectionDataError(ValueError):
    """候选排序依赖的数据不可确认时，停止当天新增计划。"""


def _selection_date(value):
    return pd.Timestamp(value).date()


def initialize_selection_state():
    """当日选股状态与真实持仓账本独立，重新选股不会改写既有持仓。"""
    g.candidates = []
    g.signal_ready = False
    g.selection_error = None
    g.selection_asof = None
    g.universe = []
    g.limit_up_count = 0
    g.concept_pool = set()
    g.concepts_by_stock = {}
    g.concept_names = {}
    g.selection_profile = {}
    g.selection_diagnostics = {}
    g.selection_stage = '尚未开始'


def _selection_stock_allowed(stock):
    code = str(stock).split('.')[0]
    exchange = str(stock).split('.')[-1]
    return (len(code) == 6 and code.isdigit()
            and not code.startswith(('4', '8', '68', '92', '005'))
            and exchange not in ('XBSE', 'XBEI'))


def _selection_daily_frame(frame, asof, stock=None):
    """按真实日期排序并验证截止日期，不以返回行号推断行情先后顺序。"""
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        raise SelectionDataError('%s 日线为空' % (stock or '批量'))
    result = frame.copy()
    if 'time' in result.columns:
        times = pd.to_datetime(result.pop('time'), errors='raise')
    elif isinstance(result.index, pd.DatetimeIndex):
        times = pd.to_datetime(result.index, errors='raise')
    else:
        raise SelectionDataError('%s 日线缺少可核验的time字段' % (stock or '批量'))
    result.index = pd.DatetimeIndex(times)
    if result.index.hasnans:
        raise SelectionDataError('%s 日线存在空日期' % (stock or '批量'))
    if _selection_builtin.any(t.date() > _selection_date(asof) for t in result.index):
        raise SelectionDataError('%s 日线超过昨日截止日期' % (stock or '批量'))
    result = result.sort_index()
    if result.index.duplicated().any():
        raise SelectionDataError('%s 日线日期重复' % (stock or '批量'))
    if 'code' in result:
        if stock is not None and set(result['code'].astype(str)) != {str(stock)}:
            raise SelectionDataError('%s 日线包含其他证券' % stock)
        result = result.drop(columns=['code'])
    return result


def prepare_universe(context):
    """先得到昨日涨停家数，再交给市场评分使用同一截止日的事实。"""
    started = _selection_time.perf_counter()
    g.signal_ready = False
    g.selection_error = None
    asof = _selection_date(context.previous_date)
    g.selection_asof = asof
    try:
        securities = get_all_securities(types=['stock'], date=asof)
        if securities is None or securities.empty or 'start_date' not in securities:
            raise SelectionDataError('全市场股票基础信息缺失')
        securities = securities.copy()
        securities.index = securities.index.map(str)
        names = [s for s in securities.index if _selection_stock_allowed(s)]
        starts = pd.to_datetime(securities.loc[names, 'start_date'], errors='raise')
        ages = (pd.Timestamp(asof) - starts).dt.days
        names = sorted(ages[ages > 50].index.tolist())
        if not names:
            g.universe = []
            g.limit_up_count = 0
            g.daily_cache['selection_yesterday_limits'] = pd.DataFrame()
            return []

        st = get_extras('is_st', names, start_date=asof, end_date=asof, df=True)
        if st is None or len(st) != 1 or _selection_date(st.index[0]) != asof:
            raise SelectionDataError('昨日ST状态日期或行数不符')
        if not set(names).issubset(set(st.columns)) or st[names].iloc[0].isna().any():
            raise SelectionDataError('昨日ST状态覆盖不完整')
        names = [s for s in names if not bool(st[s].iloc[0])]
        if not names:
            g.universe = []
            g.limit_up_count = 0
            g.daily_cache['selection_yesterday_limits'] = pd.DataFrame()
            return []

        snapshot = get_price(names, end_date=asof, count=1, frequency='daily',
                             fields=['paused', 'close', 'high_limit'],
                             skip_paused=False, panel=False, fill_paused=True)
        if snapshot is None or snapshot.empty or 'code' not in snapshot:
            raise SelectionDataError('昨日停牌及涨停快照缺失')
        snapshot = snapshot.copy()
        snapshot['code'] = snapshot['code'].astype(str)
        if 'time' not in snapshot or not _selection_builtin.all(
                _selection_date(x) == asof for x in snapshot['time']):
            raise SelectionDataError('昨日行情快照日期不符')
        if snapshot['code'].duplicated().any() or not set(names).issubset(set(snapshot['code'])):
            raise SelectionDataError('昨日行情快照重复或覆盖不完整')
        snapshot = snapshot.set_index('code').loc[names]
        if snapshot['paused'].isna().any() or not snapshot['paused'].isin([0, 1, False, True]).all():
            raise SelectionDataError('昨日停牌状态无效')
        names = [s for s in names if snapshot.at[s, 'paused'] == 0]

        # 名称/ST状态只使用当前已知快照，不在盘前读取当日高低收等未完成数据。
        current = get_current_data(names) if names else {}
        filtered = []
        for stock in names:
            item = current[stock]
            name = str(item.name)
            if 'ST' not in name and '退' not in name and not bool(item.is_st):
                filtered.append(stock)
        final = snapshot.loc[filtered].copy()
        if not _selection_builtin.all(is_finite_positive(v) for v in final['close']):
            raise SelectionDataError('昨日收盘价含非有效价格')
        # 无涨跌幅限制时涨停价可以为正无穷；这类股票不会被计作收盘涨停。
        if not _selection_builtin.all(not pd.isna(v) and float(v) > 0 for v in final['high_limit']):
            raise SelectionDataError('昨日涨停价含无效值')
        g.universe = filtered
        g.daily_cache['selection_yesterday_limits'] = final
        g.limit_up_count = int((final['close'] == final['high_limit']).sum())
        log_event('基础池', '截至%s 全市场过滤后%d只；昨日收盘涨停%d只' %
                  (asof, len(filtered), g.limit_up_count))
        return list(filtered)
    except Exception as exc:
        g.selection_error = '基础池：%s' % exc
        g.universe = []
        log_event('选股数据异常', g.selection_error)
        raise
    finally:
        g.selection_profile['universe_seconds'] = _selection_time.perf_counter() - started


def _selection_parse_concepts(payload, stocks):
    """标准返回结构为stock→jq_concept→concept_code/concept_name列表。"""
    if not isinstance(payload, dict):
        raise SelectionDataError('get_concept返回结构不是字典')
    mapping, labels = {}, {}
    excluded = {'转融券标的', '融资融券', '深股通', '沪股通', '国企改革'}
    for stock in stocks:
        if stock not in payload or not isinstance(payload[stock], dict):
            raise SelectionDataError('%s 概念结果缺失' % stock)
        details = payload[stock]
        if 'jq_concept' not in details or not isinstance(details['jq_concept'], (list, tuple)):
            raise SelectionDataError('%s 概念字段jq_concept缺失或无效' % stock)
        mapping[stock] = set()
        for item in details['jq_concept']:
            if not isinstance(item, dict) or not item.get('concept_code') or not item.get('concept_name'):
                raise SelectionDataError('%s 概念条目缺少代码或名称' % stock)
            code, name = str(item['concept_code']), str(item['concept_name'])
            if name in excluded:
                continue
            if code in labels and labels[code] != name:
                raise SelectionDataError('%s 同日概念代码名称不一致' % code)
            mapping[stock].add(code)
            labels[code] = name
    return mapping, labels


def _selection_load_concepts(stocks, asof):
    pending = sorted(set(str(s) for s in stocks) - set(g.concepts_by_stock))
    batch_size = int(g.cfg.get('concept_batch_size', 200))
    new_mapping, new_labels = {}, {}
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset:offset + batch_size]
        payload = get_concept(batch, date=asof)
        mapping, labels = _selection_parse_concepts(payload, batch)
        new_mapping.update(mapping)
        new_labels.update(labels)
    g.concepts_by_stock.update(new_mapping)
    g.concept_names.update(new_labels)


def populate_holding_concepts(context):
    """持仓概念查询失败只报告该项风控缺数，真实仓位和其他退出仍继续管理。"""
    stocks = [str(s) for s in context.portfolio.positions.keys()]
    try:
        _selection_load_concepts(stocks, _selection_date(context.previous_date))
        return True
    except Exception as exc:
        log_event('持仓概念缺数', str(exc))
        return False


def _selection_rank_concepts(stocks, money=None):
    stats = {}
    for stock in sorted(set(stocks)):
        for concept in sorted(g.concepts_by_stock[stock]):
            row = stats.setdefault(concept, {'count': 0, 'money': 0.0})
            row['count'] += 1
            row['money'] += float((money or {}).get(stock, 0.0))
    if not stats:
        return []
    rank_score = [1.0, 0.8, 0.7, 0.6, 0.5]
    by_count = sorted(stats, key=lambda code: (-stats[code]['count'], code))
    by_money = sorted(stats, key=lambda code: (-stats[code]['money'], code))
    count_scores = {code: rank_score[i] if i < 5 else 0.4 for i, code in enumerate(by_count)}
    money_scores = {code: rank_score[i] if i < 5 else 0.4 for i, code in enumerate(by_money)}
    use_money = _selection_builtin.sum(x['money'] for x in stats.values()) > 0
    scores = {code: (0.5 * count_scores[code] + 0.5 * money_scores[code]
                     if use_money else count_scores[code]) for code in stats}
    return sorted(stats, key=lambda code: (-scores[code], code))[:4]


def _selection_auction_snapshot(context, auction, stocks):
    """按日期查询开盘竞价，仅采用当日09:25后且当前时刻已知的开盘时段记录。"""
    required = {'code', 'time', 'current', 'volume'}
    if auction is None or not isinstance(auction, pd.DataFrame) or auction.empty or not required.issubset(auction.columns):
        raise SelectionDataError('今日竞价数据为空或字段不完整')
    now = pd.Timestamp(context.current_dt)
    if now.tzinfo is not None:
        now = now.tz_convert('Asia/Shanghai').tz_localize(None)
    start = now.replace(hour=9, minute=25, second=0, microsecond=0)
    stop = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now < start:
        raise SelectionDataError('开盘竞价尚未结束')
    result = auction.copy()
    result['code'] = result['code'].astype(str)
    times = pd.to_datetime(result['time'], errors='coerce')
    if getattr(times.dt, 'tz', None) is not None:
        times = times.dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
    result['time'] = times
    dated = times.notna()
    same_day = dated & (times.dt.normalize() == now.normalize())
    known = same_day & (times >= start) & (times < stop) & (times <= now)
    requested = result['code'].isin(set(str(s) for s in stocks))
    usable = result.loc[known & requested].copy()
    details = dict(raw_rows=len(result), invalid_times=int((~dated).sum()),
        other_dates=int((dated & ~same_day).sum()), before_auction=int((same_day & (times < start)).sum()),
        after_now=int((same_day & (times > now)).sum()),
        outside_opening=int((same_day & (times >= stop)).sum()),
        unknown_codes=int((~requested).sum()), valid_rows=len(usable))
    g.selection_profile['auction_validation'] = details
    lower = str(times.min()) if dated.any() else '无有效时间'
    upper = str(times.max()) if dated.any() else '无有效时间'
    log_event('竞价时间核验', '当前%s；返回时间%s至%s；%s' % (now, lower, upper, details))
    if usable.empty:
        raise SelectionDataError('没有当前已知的当日开盘竞价记录；当前%s，返回%s至%s，核验%s' %
                                 (now, lower, upper, details))
    # 同一快照的重复副本可以合并，冲突副本不能任意选一条参与概念排名。
    usable = usable.drop_duplicates(subset=['code', 'time', 'current', 'volume'])
    if usable.duplicated(subset=['code', 'time']).any():
        raise SelectionDataError('同一股票同一竞价时间存在冲突数据')
    latest = usable.sort_values(['code', 'time']).groupby('code', sort=False).tail(1).set_index('code')
    g.selection_profile['auction_valid_stocks'] = len(latest)
    return latest


def _selection_build_concept_pool(context):
    if not g.universe:
        g.concept_pool = set()
        return
    asof = g.selection_asof
    previous = g.daily_cache['selection_yesterday_limits']
    yesterday = list(previous.index[previous['close'] == previous['high_limit']])
    today = _selection_date(context.current_dt)
    completed = _selection_datetime.datetime.combine(today, _selection_datetime.time(9, 25))
    if context.current_dt < completed:
        raise SelectionDataError('开盘竞价尚未结束')
    # 此接口提供日期区间的集合竞价快照；在本地按当前时刻校验实际返回时间。
    auction = get_call_auction(g.universe, start_date=str(today), end_date=str(today),
                               fields=['time', 'current', 'volume'])
    latest = _selection_auction_snapshot(context, auction, g.universe)
    today_limits, amounts = [], {}
    current = get_current_data(g.universe)
    for stock in g.universe:
        if stock not in latest.index:
            continue
        if bool(getattr(current[stock], 'paused', False)):
            continue
        row = latest.loc[stock]
        price, volume, upper = float(row['current']), float(row['volume']), float(current[stock].high_limit)
        if not np.isfinite(volume) or volume < 0:
            raise SelectionDataError('%s 竞价成交量无效' % stock)
        if volume > 0 and is_finite_positive(price) and is_finite_positive(upper) and price >= upper * 0.998:
            today_limits.append(stock)
            amounts[stock] = volume * upper
    _selection_load_concepts(yesterday + today_limits, asof)
    prior_top = _selection_rank_concepts(yesterday)
    today_top = _selection_rank_concepts(today_limits, amounts)
    g.concept_pool = set(prior_top) | set(today_top)
    log_event('竞价覆盖', '基础池%d只；有效竞价%d只；竞价近涨停%d只' %
              (len(g.universe), len(latest), len(today_limits)))
    labels = lambda codes: [g.concept_names.get(code, code) for code in codes]
    log_event('热门概念', '昨日涨停前4=%s；今日竞价前4=%s；合并%d项' %
              (labels(prior_top), labels(today_top), len(g.concept_pool)))


def _selection_valid_history(frame, asof, stock):
    frame = _selection_daily_frame(frame, asof, stock)
    fields = ['open', 'high', 'low', 'close', 'volume', 'paused']
    if not set(fields).issubset(frame.columns):
        raise SelectionDataError('%s 日线缺少OHLCV或paused字段' % stock)
    if frame['paused'].isna().any() or not frame['paused'].isin([0, 1, False, True]).all():
        raise SelectionDataError('%s 日线停牌状态无效' % stock)
    frame = frame.loc[frame['paused'] == 0].copy()
    if frame.empty:
        raise SelectionDataError('%s 缺少非停牌日线' % stock)
    if frame.index[-1].date() != _selection_date(asof):
        raise SelectionDataError('%s 末条日线不是昨日' % stock)
    numeric = frame[['open', 'high', 'low', 'close', 'volume']].astype(float)
    if not np.isfinite(numeric.values).all() or (numeric[['open', 'high', 'low', 'close']] <= 0).any().any():
        raise SelectionDataError('%s 日线包含无效价格或成交量' % stock)
    if (numeric['volume'] < 0).any():
        raise SelectionDataError('%s 日线成交量小于零' % stock)
    frame.loc[:, ['open', 'high', 'low', 'close', 'volume']] = numeric
    return frame.tail(int(g.cfg.get('history_count', 80)))


def _selection_histories(stocks, asof):
    """每只股票保留最近80个非停牌日；批量不足时按单股相同口径补齐。"""
    result = {}
    count = int(g.cfg.get('history_count', 80))
    batch_size = int(g.cfg.get('history_batch_size', 200))
    fields = ['open', 'high', 'low', 'close', 'volume', 'paused']
    fallbacks = 0
    for offset in range(0, len(stocks), batch_size):
        batch = stocks[offset:offset + batch_size]
        try:
            frame = get_price(batch, end_date=asof, count=count, frequency='daily',
                              fields=fields, skip_paused=False, panel=False, fq='pre')
        except Exception as exc:
            log_event('日线批量回退', '%d只：%s' % (len(batch), exc))
            frame = None
        groups = {}
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            if 'code' not in frame:
                raise SelectionDataError('批量日线缺少code字段')
            groups = {str(code): sub for code, sub in frame.groupby('code', sort=False)}
        for stock in batch:
            hist = None
            if stock in groups:
                try:
                    hist = _selection_valid_history(groups[stock], asof, stock)
                except SelectionDataError as exc:
                    log_event('日线单股核对', '%s 批量返回需核对:%s' % (stock, exc))
            if hist is None or len(hist) < count:
                fallbacks += 1
                single = get_price(stock, end_date=asof, count=count, frequency='daily',
                                   fields=fields, skip_paused=True, fq='pre')
                hist = _selection_valid_history(single, asof, stock)
            if len(hist) >= 65:
                result[stock] = hist
    g.selection_profile['single_history_queries'] = fallbacks
    return result


def calculate_micro_structure(frame):
    """完成日线上的均线、量价与K线特征；每行只依赖本行及其以前的数据。"""
    df = frame.copy()
    df['returns_1d'] = df['close'].pct_change()
    for period in [5, 10, 20, 60]:
        df['ma%d' % period] = df['close'].rolling(period).mean()
        if period in (5, 10, 20):
            ma = df['ma%d' % period]
            df['ma%d_slope' % period] = (ma - ma.shift(5)) / ma.shift(5)
    df['ma_spread_ratio'] = (abs(df['ma5'] - df['ma10']) / (df['ma10'] + 0.0001)) / (
        abs(df['ma10'] - df['ma20']) / (df['ma20'] + 0.0001) + 0.0001)
    mas = df[['ma5', 'ma10', 'ma20', 'ma60']]
    df['ma_convergence'] = mas.std(axis=1) / (mas.mean(axis=1) + 0.0001)
    df['price_ma_angle'] = np.arctan((df['close'] - df['ma20']) / (df['ma20'] + 0.0001) * 20) * 180 / np.pi
    df['volume_ma5'] = df['volume'].rolling(5).mean()
    df['volume_ma20'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / (df['volume_ma5'] + 0.0001)
    increasing = ((df['volume'] > df['volume'].shift(1))
                  & (df['volume'].shift(1) > df['volume'].shift(2))).astype(int)
    df['volume_stack_days'] = increasing.rolling(5).sum()
    # 两个已完成交易日确认：前一日量比>3、本日量比<1.5，确认信号归属本日。
    df['volume_pulse'] = (df['volume_ratio'].shift(1) > 3.0) & (df['volume_ratio'] < 1.5)
    body = abs(df['close'] - df['open'])
    spread = df['high'] - df['low']
    df['body_ratio'] = body / (spread + 0.0001)
    df['upper_shadow_ratio'] = (df['high'] - np.maximum(df['close'], df['open'])) / (spread + 0.0001)
    df['lower_shadow_ratio'] = (np.minimum(df['close'], df['open']) - df['low']) / (spread + 0.0001)
    df['close_position'] = (df['close'] - df['low']) / (spread + 0.0001)
    df['engulfing'] = ((df['close'] > df['open'])
                       & (df['close'].shift(1) < df['open'].shift(1))
                       & (df['close'] > df['open'].shift(1))
                       & (df['open'] < df['close'].shift(1)))
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi_14'] = 100 - 100 / (1 + gain / (loss + 0.0001))
    dif = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = 2 * (dif - dif.ewm(span=9, adjust=False).mean())
    return df


def identify_shakeout(df):
    """近6日均线反复交叉、近5日RSI平稳中性且近10日窄幅横盘时不入围。"""
    latest = df.iloc[-1]
    above = (df['ma5'].iloc[-6:] > df['ma20'].iloc[-6:]).astype(int)
    crosses = above.diff().abs().sum()
    neutral = 40 < latest['rsi_14'] < 60 and df['rsi_14'].iloc[-5:].std() < 5
    closes = df['close'].iloc[-10:]
    spread = (closes.max() - closes.min()) / (latest['close'] + 0.0001) * 100
    return bool(crosses >= 2 and neutral and spread < 4)


class ComboEvaluator:
    """四形态按突破、主升回踩、缩量回调、多头排列的顺序唯一归属。"""

    COMBO_CONFIG = {
        'combo_3': {'name': '放量突破', 'priority': 1},
        'combo_4': {'name': '主升浪回踩', 'priority': 2},
        'combo_2': {'name': '缩量回调', 'priority': 3},
        'combo_6': {'name': '多头排列', 'priority': 4},
    }

    @staticmethod
    def _score(core, edges):
        core_met = _selection_builtin.sum(bool(x) for x in core.values())
        edge_met = _selection_builtin.sum(bool(x) for x in edges.values())
        score = 75.0 * core_met / len(core) + 25.0 * edge_met / len(edges)
        return core_met == len(core) and score >= 90, score, core_met, edge_met

    @staticmethod
    def evaluate_combo_3(latest, prev):
        # 核心：昨日涨幅>4%、量比>1.3、均线离散度<2.5%、价格偏离角>25度。
        core = dict(breakout=latest['returns_1d'] > .04, volume=latest['volume_ratio'] > 1.3,
                    converge=latest['ma_convergence'] < .025, angle=latest['price_ma_angle'] > 25)
        edges = dict(spread=latest['ma_spread_ratio'] > 1.8, body=latest['body_ratio'] > .5,
                     engulfing=bool(latest['engulfing']), close_high=latest['close_position'] > .8,
                     stacked=latest['volume_stack_days'] >= 2, no_pulse=not bool(latest['volume_pulse']))
        return ComboEvaluator._score(core, edges)

    @staticmethod
    def evaluate_combo_4(latest, prev):
        # 核心：C>MA5>MA10>MA20、距离MA10<3%、MA20上行、量比<0.8。
        core = dict(bull=latest['close'] > latest['ma5'] > latest['ma10'] > latest['ma20'],
                    near_ma10=abs(latest['close'] / latest['ma10'] - 1) < .03,
                    slope=latest['ma20_slope'] > 0, volume=latest['volume_ratio'] < .8)
        edges = dict(shadow=latest['lower_shadow_ratio'] > .35, close_high=latest['close_position'] > .55,
                     spread=latest['ma_spread_ratio'] > 1.3, above_ma20=latest['close'] > latest['ma20'] * 1.02,
                     volume_floor=latest['volume'] > latest['volume_ma20'] * .4,
                     short_slope=latest['ma5_slope'] > -.02)
        return ComboEvaluator._score(core, edges)

    @staticmethod
    def evaluate_combo_2(latest, prev):
        # 核心：C在MA10下方2%至5%、仍高于MA20、45<RSI14<60。
        deviation = latest['close'] / latest['ma10'] - 1
        core = dict(pullback=-.05 < deviation < -.02, above_ma20=latest['close'] > latest['ma20'],
                    rsi=45 < latest['rsi_14'] < 60)
        edges = dict(bull=latest['ma5'] > latest['ma20'] and latest['ma10'] > latest['ma20'],
                     volume=latest['volume_ratio'] < .7,
                     shadow=latest['lower_shadow_ratio'] > latest['body_ratio'] * 1.5,
                     no_pulse=not bool(latest['volume_pulse']), close_high=latest['close_position'] > .5,
                     slope=latest['ma5_slope'] > latest['ma10_slope'])
        return ComboEvaluator._score(core, edges)

    @staticmethod
    def evaluate_combo_6(latest, prev, open_chg):
        # 备用形态：MA5>MA10>MA20、量比>1.2、高开>1.5%，五项附加条件至少四项。
        core = dict(bull=latest['ma5'] > latest['ma10'] > latest['ma20'],
                    volume=latest['volume_ratio'] > 1.2, opening=open_chg > 1.5)
        edges = dict(opening_cap=open_chg < 5, volume_up=latest['volume_ma5'] > latest['volume_ma20'],
                     price=latest['close'] > latest['ma5'], shadow=latest['upper_shadow_ratio'] < .3,
                     macd=latest['macd'] > 0)
        core_met = _selection_builtin.sum(bool(x) for x in core.values())
        edge_met = _selection_builtin.sum(bool(x) for x in edges.values())
        return core_met == 3 and edge_met >= 4, 90.0 + edge_met * 2, core_met, edge_met


def _selection_evaluate_stock(stock, frame, opening, diagnostics=None):
    if not is_finite_positive(opening):
        raise SelectionDataError('%s 今日开盘价尚不可用' % stock)
    df = calculate_micro_structure(frame)
    latest, prev = df.iloc[-1], df.iloc[-2]
    numeric = [key for key in df.columns if key not in ('engulfing', 'volume_pulse')]
    if not np.isfinite(latest[numeric].astype(float).values).all():
        raise SelectionDataError('%s 形态末行存在非有效指标' % stock)
    if identify_shakeout(df):
        if diagnostics is not None:
            diagnostics['shakeout'] = diagnostics.get('shakeout', 0) + 1
        return None
    open_chg = (float(opening) / float(latest['close']) - 1) * 100
    checks = [('combo_3', ComboEvaluator.evaluate_combo_3),
              ('combo_4', ComboEvaluator.evaluate_combo_4),
              ('combo_2', ComboEvaluator.evaluate_combo_2)]
    evaluated = []
    for combo, evaluate in checks:
        passed, score, core_met, edge_met = evaluate(latest, prev)
        opening_ok = (3 <= open_chg <= 7) if combo == 'combo_3' else open_chg > 1
        evaluated.append((combo, passed, opening_ok, score, core_met, edge_met))
    passed, score, core_met, edge_met = ComboEvaluator.evaluate_combo_6(latest, prev, open_chg)
    evaluated.append(('combo_6', passed, open_chg > 1.5, score, core_met, edge_met))
    if diagnostics is not None:
        for name, shape_ok, gap_ok, _, core_count, _ in evaluated:
            stats = diagnostics.setdefault('patterns', {}).setdefault(name,
                dict(checked=0, core=0, qualified=0, opening=0, full=0))
            stats['checked'] += 1
            stats['core'] += int(core_count == (4 if name in ('combo_3', 'combo_4') else 3))
            stats['qualified'] += int(shape_ok)
            stats['opening'] += int(gap_ok)
            stats['full'] += int(shape_ok and gap_ok)
    matched = [row for row in evaluated if row[1] and row[2]]
    if not matched:
        return None
    combo, _, _, score, core_met, edge_met = matched[0]
    cfg = ComboEvaluator.COMBO_CONFIG[combo]
    return dict(stock=stock, combo_type=combo, combo_name=cfg['name'], priority=cfg['priority'],
                score=float(score), core_met=int(core_met), edge_met=int(edge_met),
                open_chg=float(open_chg), signal_date=str(g.selection_asof),
                opening=float(opening), previous_close=float(latest['close']))


def _selection_finalists(candidates):
    ranked = sorted(candidates, key=lambda item: (item['priority'], -item['score'], item['stock']))
    return ranked[:int(g.cfg.get('candidate_count', 5))]


def select_candidates(context):
    """固定前五入围；异常不是空信号，只有完整阶段成功才允许新增买入。"""
    started = _selection_time.perf_counter()
    g.signal_ready = False
    g.selection_error = None
    g.candidates = []
    g.selection_diagnostics = dict(universe=len(g.universe), shakeout=0, paused_or_st=0)
    g.selection_stage = '基础日期核对'
    g.selection_profile.update(history_seconds=0, single_history_queries=0)
    try:
        asof = _selection_date(context.previous_date)
        if g.selection_asof != asof:
            raise SelectionDataError('基础池尚未按昨日日期准备')
        if not g.universe:
            g.signal_ready = True
            return []
        g.selection_stage = '历史指数成分'
        components = get_index_stocks('000852.XSHG', date=asof)
        if components is None or len(components) == 0:
            raise SelectionDataError('中证1000历史成分为空')
        stocks = sorted(set(g.universe) & set(str(s) for s in components))
        g.selection_diagnostics['index_intersection'] = len(stocks)
        log_event('指数过滤', '基础池%d只 → 中证1000交集%d只' % (len(g.universe), len(stocks)))
        if g.cfg.get('use_concept_filter', True):
            g.selection_stage = '概念池与竞价核验'
            _selection_build_concept_pool(context)
            if g.concept_pool:
                _selection_load_concepts(stocks, asof)
                stocks = [s for s in stocks if g.concepts_by_stock[s] & g.concept_pool]
            else:
                stocks = []
        else:
            log_event('概念过滤', '配置关闭入池限制；持仓概念风险仍独立查询')
        g.selection_diagnostics['concept_survivors'] = len(stocks)
        log_event('概念过滤', '指数交集%d只 → 概念匹配%d只；有效热门概念%d项' %
                  (g.selection_diagnostics['index_intersection'], len(stocks), len(g.concept_pool)))
        g.selection_stage = '历史日线获取'
        history_started = _selection_time.perf_counter()
        histories = _selection_histories(stocks, asof)
        g.selection_profile['history_seconds'] = _selection_time.perf_counter() - history_started
        g.selection_diagnostics['valid_history'] = len(histories)
        log_event('历史覆盖', '请求%d只；满足65根以上已完成非停牌日线%d只；历史长度不足%d只；单股核对%d次' %
                  (len(stocks), len(histories), len(stocks)-len(histories), g.selection_profile['single_history_queries']))
        candidates = []
        for stock in stocks:
            g.selection_stage = '个股形态 ' + stock
            if stock not in histories:
                continue
            q = get_quote(context, stock)
            if q is None:
                raise SelectionDataError('%s 开盘快照缺失' % stock)
            if q.get('paused') or q.get('is_st') or '退' in str(q.get('name', '')):
                g.selection_diagnostics['paused_or_st'] += 1
                continue
            item = _selection_evaluate_stock(stock, histories[stock], q.get('open'), g.selection_diagnostics)
            if item is not None:
                candidates.append(item)
        g.candidates = _selection_finalists(candidates)
        g.signal_ready = True
        g.selection_stage = '选股完成'
        log_event('四形态选股', '候选范围%d只；有效日线%d只；合格%d只；固定入围%d只' %
                  (len(stocks), len(histories), len(candidates), len(g.candidates)))
        log_event('形态排除', '停牌/ST/退市%d只；窄幅震荡%d只' %
                  (g.selection_diagnostics['paused_or_st'], g.selection_diagnostics['shakeout']))
        for name, config in sorted(ComboEvaluator.COMBO_CONFIG.items(), key=lambda item: item[1]['priority']):
            stats = g.selection_diagnostics.get('patterns', {}).get(name, {})
            log_event('形态门槛', '%s | 检查%d 核心全满足%d 核心及附加达标%d 开盘门槛达标%d 同时通过%d' %
                      (config['name'], stats.get('checked', 0), stats.get('core', 0),
                       stats.get('qualified', 0), stats.get('opening', 0), stats.get('full', 0)))
        for rank, item in enumerate(g.candidates, 1):
            log_event('入围', '%d %s %s 得分%.4f 高开%.2f%% 核心%d/附加%d' %
                      (rank, item['stock'], item['combo_name'], item['score'], item['open_chg'],
                       item['core_met'], item['edge_met']))
        return list(g.candidates)
    except Exception as exc:
        g.selection_error = '%s：%s' % (g.selection_stage, exc)
        g.candidates = []
        g.signal_ready = False
        log_event('选股未就绪', g.selection_error)
        return []
    finally:
        g.selection_profile['selection_seconds'] = _selection_time.perf_counter() - started
        log_event('选股耗时', '本轮%.3f秒；日线%.3f秒；单股补取%d次' %
                  (g.selection_profile['selection_seconds'], g.selection_profile.get('history_seconds', 0),
                   g.selection_profile.get('single_history_queries', 0)))


# 订单、成交与持仓
# 委托只表达交易意图。实际成交逐笔入账；余单在终态且成交已核对后释放。
# 平台仍有持仓、锁定股数或待核对成交时，形态、高点与退出状态继续保留。
import builtins as _execution_builtin
import datetime as _execution_dt
import math as _execution_math


def initialize_execution_state():
    g.orders = {}
    g.book = {}
    g.seen_trades = set()
    g.fill_log = []
    g.closed = []
    g.execution_blockers = set()
    g.execution_warnings = set()
    g.sold_today = set()


def _execution_block(key, message):
    if key not in g.execution_blockers:
        log_event('成交核验', message + '；暂停新增，持仓退出继续')
    g.execution_blockers.add(key)


def _execution_clear(key):
    g.execution_blockers.discard(key)


def _execution_datetime(value):
    if isinstance(value, _execution_dt.datetime):
        return value
    if isinstance(value, _execution_dt.date):
        return _execution_dt.datetime.combine(value, _execution_dt.time())
    if value is not None:
        try:
            return _execution_dt.datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            return None
    return None


def _execution_order_key(day, order_id):
    return (str(day), str(order_id))


def _execution_status(order_object):
    value = getattr(order_object, 'status', '')
    name = getattr(value, 'name', None)
    status = str(name if name is not None else value).split('.')[-1].lower()
    # filled 是尚未结束的部分成交，不能与全部成交 held 混同。
    aliases = {'cancelled': 'canceled', 'all_filled': 'held',
               '0': 'open', '1': 'filled', '2': 'canceled', '3': 'rejected',
               '4': 'held', '8': 'new', '9': 'pending_cancel'}
    return aliases.get(status, status)


def _execution_platform_terminal(order_object, quantity=None):
    """平台完成与逐笔成交对账分别确认；done 需有全部成交数量证据。"""
    status = _execution_status(order_object)
    if status in ('canceled', 'rejected'):
        return True
    amount = getattr(order_object, 'amount', quantity)
    if status in ('held', 'done') and amount is not None:
        return int(amount) > 0 and int(getattr(order_object, 'filled', 0)) == int(amount)
    return False


def _execution_order_time(order_object):
    for name in ('add_time', 'entrust_time', 'created_at', 'datetime'):
        stamp = _execution_datetime(getattr(order_object, name, None))
        if stamp is not None:
            return stamp
    return None


def _execution_find_order(order_id, day, security=None):
    direct = _execution_order_key(day, order_id)
    if direct in g.orders:
        candidate = g.orders[direct]
        if security is None or candidate['stock'] == str(security):
            return direct
    # 平台查询仅提供当日订单/成交；编号跨日复用不能归给昨日未完成意图。
    return None


def position_total(position):
    """包含卖单锁定数量的持仓；已核对账本可识别锁定字段口径。"""
    if position is None:
        return 0
    total = int(getattr(position, 'total_amount', 0))
    locked = int(getattr(position, 'locked_amount', 0))
    stock = str(getattr(position, 'security', ''))
    if total < 0 or locked < 0:
        raise ValueError('平台持仓数量为负')
    if locked == 0:
        _execution_clear('POSITION_QUANTITY_MODE:' + stock)
        return total
    candidates = {'total_includes_locked': total, 'total_excludes_locked': total + locked}
    book = g.book.get(stock)
    if book is not None:
        matched = [mode for mode, quantity in candidates.items()
                   if quantity > 0 and quantity == book['qty']]
        if len(matched) == 1:
            _execution_clear('POSITION_QUANTITY_MODE:' + stock)
            return candidates[matched[0]]
        _execution_block('POSITION_QUANTITY_MODE:' + stock,
                         '%s 锁定数量口径与成交账本不一致，保守保留持仓' % stock)
        return _execution_builtin.max(candidates.values())
    # 未知持仓没有逐笔数量证据，市值也可能不含锁定部分，只使用显式口径。
    mode = g.cfg.get('position_quantity_mode', 'total_excludes_locked')
    if mode not in candidates:
        raise ValueError('未知持仓数量口径：' + str(mode))
    return candidates[mode]


def _execution_trading_time(context):
    clock = context.current_dt.strftime('%H:%M')
    return '09:30' <= clock < '11:30' or '13:00' <= clock < '15:00'


def active_order(stock, side=None):
    return _execution_builtin.any(
        intent['stock'] == str(stock) and not intent['terminal']
        and (side is None or intent['side'] == side)
        for intent in g.orders.values())


def pending_buy_reserve():
    """未释放买单占用的风险预算，包含剩余股数的估算佣金。"""
    value = 0.0
    for intent in g.orders.values():
        if intent['side'] != 'buy' or intent['terminal']:
            continue
        remaining = _execution_builtin.max(0, intent['qty'] - intent['seen_qty'])
        if remaining:
            notional = remaining * intent.get('reserve_price', intent['limit_price'])
            value += notional + _execution_builtin.max(
                g.cfg.get('min_commission', 5), notional * g.cfg.get('commission_rate', .0003))
    return value


def occupied_stocks(context):
    stocks = set(str(s) for s, p in context.portfolio.positions.items() if position_total(p) > 0)
    stocks.update(s for s, book in g.book.items() if book['qty'] > 0 or active_order(s))
    stocks.update(intent['stock'] for intent in g.orders.values()
                  if intent['side'] == 'buy' and not intent['terminal'])
    return stocks


def _execution_new_book(context, intent, trade, quantity, price):
    stamp = _execution_datetime(getattr(trade, 'time', None))
    if stamp is None:
        raise ValueError('成交缺少有效时间')
    atr = intent.get('atr')
    stop = price - g.cfg.get('atr_early_multiplier', 1.8) * atr if is_finite_positive(atr) else None
    return dict(qty=quantity, entry_date=str(stamp.date()), entry_time=str(stamp),
                combo=dict(intent.get('combo') or {}), high=price, stop=stop,
                exit_reason=None, buy_value=quantity * price, sell_value=0.0,
                price_basis_factor=intent.get('price_basis_factor'), recovered=False,
                entry_date_estimated=False)


def _execution_apply_trade(context, trade_id, trade, key):
    intent = g.orders[key]
    stock = intent['stock']
    stamp = _execution_datetime(getattr(trade, 'time', None))
    quantity = _execution_builtin.abs(int(getattr(trade, 'amount', 0)))
    price = float(getattr(trade, 'price', 0))
    if stamp is None or quantity <= 0 or not is_finite_positive(price):
        _execution_block('INVALID_TRADE:' + str(trade_id), '成交时间、数量或价格无效：' + str(trade_id))
        return
    token = (str(stamp.date()), str(trade_id), str(intent['native_order_id']))
    if token in g.seen_trades:
        return
    if str(getattr(trade, 'security', stock)) != stock:
        _execution_block('TRADE_SECURITY:' + str(token), '成交证券与委托不一致：' + str(token))
        return
    if intent['seen_qty'] + quantity > intent['qty']:
        _execution_block('TRADE_QUANTITY:' + str(key), '实际成交超过委托数量：' + stock)
    if intent['side'] == 'buy':
        if stock not in g.book:
            g.book[stock] = _execution_new_book(context, intent, trade, quantity, price)
        else:
            book = g.book[stock]
            book['qty'] += quantity
            if book.get('buy_value') is not None:
                book['buy_value'] += quantity * price
            book['high'] = _execution_builtin.max(book.get('high') or price, price)
        if intent['limit_price'] is not None and price > intent['limit_price'] + .011:
            _execution_block('BUY_LIMIT:' + str(key), '实际买入价格高于委托限价：' + stock)
    else:
        if stock not in g.book:
            _execution_block('SELL_WITHOUT_BOOK:' + str(key), '卖出成交缺少持仓元数据：' + stock)
        else:
            book = g.book[stock]
            if quantity > book['qty']:
                _execution_block('SELL_QUANTITY:' + str(key), '卖出成交超过内部持仓数量：' + stock)
            book['qty'] = _execution_builtin.max(0, book['qty'] - quantity)
            book['sell_value'] = book.get('sell_value', 0.0) + quantity * price
        g.sold_today.add(stock)
    intent['seen_qty'] += quantity
    g.seen_trades.add(token)
    g.fill_log.append(dict(trade_id=str(trade_id), order_key=key, stock=stock,
                           side=intent['side'], quantity=quantity, price=price,
                           time=str(stamp), value=quantity * price, reason=intent['reason']))
    log_event('实际成交', '%s %s %d股，成交价%.4f，成交额%.2f；%s' %
              (stock, '买入' if intent['side'] == 'buy' else '卖出', quantity,
               price, quantity * price, intent['reason']))


def _execution_update_order(key, order_object):
    intent = g.orders[key]
    reported = int(getattr(order_object, 'filled', 0))
    status = _execution_status(order_object)
    intent['reported_filled'] = reported
    intent['status'] = status
    intent['platform_terminal'] = _execution_platform_terminal(order_object, intent['qty'])
    intent['terminal'] = intent['platform_terminal'] and reported == intent['seen_qty']
    if status in ('held', 'done') and not intent['platform_terminal']:
        _execution_block('ORDER_STATUS:' + str(key), '完成状态与委托数量不一致，保留占用：' + intent['stock'])
    else:
        _execution_clear('ORDER_STATUS:' + str(key))
    if reported < intent['seen_qty'] or reported > intent['qty']:
        intent['terminal'] = False
        _execution_block('ORDER_QUANTITY:' + str(key), '委托累计成交与已核对成交冲突：' + intent['stock'])
    elif reported > intent['seen_qty']:
        _execution_block('TRADE_LAG:' + str(key), '等待委托对应的逐笔成交：' + intent['stock'])
    else:
        _execution_clear('TRADE_LAG:' + str(key))
        _execution_clear('ORDER_QUANTITY:' + str(key))
    if intent['terminal']:
        _execution_clear('MISSING_ORDER:' + str(key))
        _execution_clear('CANCEL_PENDING:' + str(key))
    commission = getattr(order_object, 'commission', None)
    if commission is not None:
        try:
            value = float(commission)
            if _execution_math.isfinite(value):
                intent['commission'] = value
        except (ValueError, TypeError):
            pass
    state = (status, reported, intent['seen_qty'], intent['terminal'])
    if state != intent.get('logged_state'):
        log_event('委托状态', '%s %s，状态%s，平台已成交%d股，已核对%d股，终态确认%s' %
                  (intent['stock'], intent['side'], status, reported, intent['seen_qty'], intent['terminal']))
        intent['logged_state'] = state


def _execution_recover_position(context, stock, position, quantity):
    stamp = _execution_datetime(getattr(position, 'init_time', None))
    if stamp is not None and stamp > context.current_dt:
        stamp = None
    price = float(getattr(position, 'price', 0) or 0)
    cost = float(getattr(position, 'avg_cost', 0) or 0)
    anchor = cost if is_finite_positive(cost) else price
    try:
        atr = current_atr(context, stock)
    except Exception as error:
        atr = None
        log_event('持仓恢复', '%s ATR暂不可得：%s' % (stock, error))
    g.book[stock] = dict(qty=quantity, entry_date=str(stamp.date()) if stamp else None,
                        entry_time=str(stamp) if stamp else None,
                        combo={'name': '已存在持仓', 'priority': 99},
                        high=price if is_finite_positive(price) else anchor,
                        stop=anchor - g.cfg.get('atr_multiplier', 1.5) * atr
                        if is_finite_positive(anchor) and is_finite_positive(atr) else None,
                        exit_reason=None, buy_value=None, sell_value=0.0,
                        price_basis_factor=None, recovered=True, entry_date_estimated=stamp is None)
    _execution_block('RECOVERED_POSITION:' + stock, '恢复平台已有持仓，入场形态与历史成交待核验：' + stock)


def reconcile_positions(context):
    """平台数量与逐笔账本交叉检查；差异不被解释为虚构成交。"""
    actual = {str(s): p for s, p in context.portfolio.positions.items()}
    for stock, position in actual.items():
        try:
            quantity = position_total(position)
        except Exception as error:
            _execution_block('POSITION_FIELDS:' + stock, '%s 持仓字段异常：%s' % (stock, error))
            continue
        if quantity <= 0:
            continue
        if stock not in g.book:
            if active_order(stock, 'buy'):
                _execution_block('POSITION_MISMATCH:' + stock, '平台已有仓位，等待买入成交核对：' + stock)
                continue
            _execution_recover_position(context, stock, position, quantity)
        book = g.book[stock]
        book['platform_qty'] = quantity
        if quantity != book['qty']:
            _execution_block('POSITION_MISMATCH:' + stock,
                             '%s 平台持仓%d股、成交账本%d股，保留退出元数据' % (stock, quantity, book['qty']))
        else:
            _execution_clear('POSITION_MISMATCH:' + stock)
            _execution_clear('POSITION_FIELDS:' + stock)
    for stock, book in list(g.book.items()):
        position = actual.get(stock)
        try:
            quantity = position_total(position)
        except Exception:
            continue
        locked = int(getattr(position, 'locked_amount', 0)) if position is not None else 0
        if quantity == 0 and locked == 0 and book['qty'] == 0 and not active_order(stock):
            # 卖单与成交均核对完成后，实际持仓也归零，才结束这一笔持仓。
            archive = dict(book)
            archive.update(stock=stock, closed_at=str(context.current_dt))
            if archive.get('buy_value') is not None:
                archive['gross_cash_difference'] = archive.get('sell_value', 0.0) - archive['buy_value']
            g.closed.append(archive)
            del g.book[stock]
            _execution_clear('POSITION_MISMATCH:' + stock)
            _execution_clear('RECOVERED_POSITION:' + stock)
            _execution_clear('POSITION_QUANTITY_MODE:' + stock)
            log_event('持仓结束', stock + ' 已核对完全退出；净收益以平台费用和分红记录为准')
        elif quantity != book['qty']:
            _execution_block('POSITION_MISMATCH:' + stock,
                             '%s 平台持仓%d股、成交账本%d股，等待同步' % (stock, quantity, book['qty']))


def sync_execution(context):
    """订单终态、逐笔成交与平台仓位共同决定是否允许新增。"""
    try:
        native_orders = get_orders() or {}
        trades = get_trades() or {}
    except Exception as error:
        _execution_block('QUERY_FAILED', '订单或成交查询失败：' + str(error))
        return False
    _execution_clear('QUERY_FAILED')
    current_day = str(context.current_dt.date())
    matched_orders = {}
    for native_id, native_order in native_orders.items():
        stamp = _execution_order_time(native_order)
        day = str(stamp.date()) if stamp else current_day
        native_id = getattr(native_order, 'order_id', native_id)
        key = _execution_find_order(native_id, day, getattr(native_order, 'security', None))
        if key is None:
            if not _execution_platform_terminal(native_order):
                _execution_block('UNKNOWN_ORDER:' + str((day, native_id)), '发现未归属的活跃委托：' + str(native_id))
                security = getattr(native_order, 'security', None)
                if security is not None:
                    _execution_block('UNKNOWN_ORDER_STOCK:' + str(security), '存在未归属活跃委托，禁止重复委托：' + str(security))
            continue
        matched_orders[key] = native_order
    def sort_trade(item):
        return (str(getattr(item[1], 'time', '')), str(item[0]))
    for trade_id, trade in sorted(trades.items(), key=sort_trade):
        stamp = _execution_datetime(getattr(trade, 'time', None))
        day = str(stamp.date()) if stamp else current_day
        native_id = getattr(trade, 'order_id', None)
        key = _execution_find_order(native_id, day, getattr(trade, 'security', None))
        if key is None:
            _execution_block('UNKNOWN_TRADE:' + str((day, trade_id, native_id)),
                             '发现未归属的实际成交：' + str(trade_id))
            continue
        _execution_apply_trade(context, trade_id, trade, key)
    for key, intent in g.orders.items():
        native = matched_orders.get(key)
        if native is None:
            if not intent['terminal']:
                _execution_block('MISSING_ORDER:' + str(key), '待确认委托暂不可见，继续保留占用：' + intent['stock'])
            continue
        _execution_clear('MISSING_ORDER:' + str(key))
        _execution_update_order(key, native)
    reconcile_positions(context)
    return not g.execution_blockers


def _execution_register(context, native, stock, side, qty, price, reason, combo=None, atr=None,
                        reserve_price=None):
    native_id = getattr(native, 'order_id', None)
    if native_id is None:
        _execution_block('ORDER_WITHOUT_ID:' + stock, '委托返回对象缺少编号，需核对平台：' + stock)
        return False
    day = str(context.current_dt.date())
    key = _execution_order_key(day, native_id)
    if key in g.orders:
        _execution_block('ORDER_ID_COLLISION:' + str(key), '同日委托编号重复，停止新增：' + str(native_id))
        return False
    g.orders[key] = dict(stock=str(stock), side=side, qty=int(qty), limit_price=price,
                         reserve_price=price if reserve_price is None else reserve_price,
                         submitted=context.current_dt, native_order_id=native_id,
                         seen_qty=0, reported_filled=int(getattr(native, 'filled', 0)),
                         status=_execution_status(native), platform_terminal=False,
                         terminal=False, cancel_requested=False,
                         cancel_last_attempt=None, cancel_attempts=0, commission=None, atr=atr,
                         combo=dict(combo or {}), reason=str(reason), price_basis_factor=None)
    # 某些撮合会同步返回成交，先登记归属，再读取逐笔事实。
    _execution_update_order(key, native)
    log_event('委托受理', '%s %s %d股，编号%s；等待实际成交核对' % (stock, side, qty, native_id))
    sync_execution(context)
    intent = g.orders[key]
    return not (intent['terminal'] and intent['seen_qty'] == 0 and intent['status'] in ('rejected', 'canceled'))


def submit_buy_value(context, stock, target_value, reference_price, combo, atr):
    """09:28按目标金额委托；原生订单数量和Trade回报分别记录，不推定成交。"""
    stock = str(stock)
    if (context.current_dt.strftime('%H:%M:%S') != '09:28:00'
            or g.execution_blockers or active_order(stock) or stock in g.book):
        return False
    if not all(is_finite_positive(v) for v in (target_value, reference_price, atr)):
        return False
    fee = _execution_builtin.max(g.cfg.get('min_commission', 5),
                                  target_value * g.cfg.get('commission_rate', .0003))
    if target_value + fee > float(context.portfolio.available_cash) + 1e-8:
        log_event('买入未提交', stock + ' 实际可用现金不足以覆盖目标金额及佣金')
        return False
    try:
        native = order_target_value(stock, float(target_value))
    except Exception as error:
        _execution_block('SUBMIT_UNCERTAIN:' + stock, '%s 买入委托结果未知：%s' % (stock, error))
        return False
    if native is None:
        log_event('买入未受理', stock + ' 未产生有效委托，不建立持仓或成交记录')
        return False
    quantity = int(getattr(native, 'amount', 0))
    if quantity <= 0:
        # 已报单后不能用参考价估算数量覆盖原生委托事实。
        _execution_block('ORDER_QUANTITY_MISSING:' + stock, '委托数量不可用，等待核对平台：' + stock)
        return False
    return _execution_register(context, native, stock, 'buy', quantity, None,
        (combo or {}).get('name', (combo or {}).get('combo_name', '形态入场')),
        combo=combo, atr=float(atr),
        reserve_price=_execution_builtin.max(reference_price, target_value / quantity))


def submit_buy(context, stock, qty, limit_price, combo, atr):
    stock = str(stock)
    if not _execution_trading_time(context) or g.execution_blockers or active_order(stock) or stock in g.book:
        return False
    quantity = int(qty) // 100 * 100
    if quantity <= 0 or not is_finite_positive(limit_price) or not is_finite_positive(atr):
        return False
    fee = _execution_builtin.max(g.cfg.get('min_commission', 5),
                                  quantity * limit_price * g.cfg.get('commission_rate', .0003))
    if quantity * limit_price + fee > float(context.portfolio.available_cash) + 1e-8:
        log_event('买入未提交', stock + ' 实际可用现金不足以覆盖限价金额及佣金')
        return False
    try:
        style = LimitOrderStyle(float(limit_price))
    except Exception as error:
        log_event('买入未提交', '%s 限价委托参数无效：%s' % (stock, error))
        return False
    try:
        native = order(stock, quantity, style=style)
    except Exception as error:
        # 传输异常不能证明交易所未受理，先核对原生订单，避免重复下单。
        _execution_block('SUBMIT_UNCERTAIN:' + stock, '%s 买入委托结果未知：%s' % (stock, error))
        return False
    if native is None:
        log_event('买入未受理', stock + ' 未产生有效委托，不建立持仓或成交记录')
        return False
    return _execution_register(context, native, stock, 'buy', quantity, float(limit_price),
                               (combo or {}).get('name', (combo or {}).get('combo_name', '形态入场')),
                               combo=combo, atr=float(atr))


def submit_sell(context, stock, qty, reason, limit_price=None):
    stock = str(stock)
    book = g.book.get(stock)
    if book and book.get('strong_trend') and strong_exit_exempt(context, stock, book, reason):
        return False
    preopen_gap = (context.current_dt.strftime('%H:%M:%S') == '09:27:00'
                   and str(reason).startswith('开盘低开'))
    if ((not _execution_trading_time(context) and not preopen_gap) or active_order(stock)
            or 'SUBMIT_UNCERTAIN:' + stock in g.execution_blockers
            or 'UNKNOWN_ORDER_STOCK:' + stock in g.execution_blockers):
        return False
    position = context.portfolio.positions.get(stock)
    if position is None:
        return False
    actual_quantity = position_total(position)
    book = g.book.get(stock)
    if book is not None and int(book['qty']) != actual_quantity:
        # 已核对成交可能先于Position快照到达。不能按陈旧快照再次卖出。
        # 送转等非交易数量变化也不当作买卖成交，保留元数据等待数量核验。
        _execution_block('POSITION_MISMATCH:' + stock,
                         '%s 待持仓数量核对：平台%d股、成交账本%d股，暂不重复卖出' %
                         (stock, actual_quantity, int(book['qty'])))
        return False
    available = int(getattr(position, 'closeable_amount', 0))
    quantity = _execution_builtin.min(int(qty), available, actual_quantity)
    if quantity <= 0:
        return False
    try:
        quote = get_quote(context, stock)
        if not quote:
            raise ValueError('卖出报价为空')
        if quote['paused']:
            return False
        clock = context.current_dt.strftime('%H:%M')
        if limit_price is None and '14:57' <= clock <= '15:00':
            # 收盘集合竞价使用当日允许的卖出限价，等待竞价成交。
            limit_price = quote.get('low_limit')
            if not is_finite_positive(limit_price):
                log_event('卖出未提交', stock + ' 收盘竞价缺少有效跌停价')
                return False
        if limit_price is not None and not is_finite_positive(limit_price):
            return False
        style = LimitOrderStyle(float(limit_price)) if limit_price is not None else None
    except Exception as error:
        log_event('卖出报价暂不可用', '%s: %s；尚未报单，保留持仓风控并在后续检查重试' % (stock, error))
        return False
    try:
        if limit_price is None:
            native = order(stock, -quantity)
        else:
            native = order(stock, -quantity, style=style)
    except Exception as error:
        _execution_block('SUBMIT_UNCERTAIN:' + stock, '%s 卖出委托结果未知：%s' % (stock, error))
        return False
    if native is None:
        log_event('卖出未受理', stock + ' 保留持仓、高点、止损线及退出意图')
        return False
    return _execution_register(context, native, stock, 'sell', quantity, limit_price, reason)


def cancel_stale_orders(context, force=False, side=None, stock=None, exempt_only=False):
    """撤单申请不释放名额与金额；等待平台终态和全部成交完成核对。"""
    clock = context.current_dt.strftime('%H:%M')
    if '14:57' <= clock <= '15:00' or '09:20' <= clock < '09:25':
        return
    if not _execution_builtin.any(not row['terminal'] for row in g.orders.values()):
        _execution_clear('CANCEL_QUERY_FAILED')
        return
    # 先处理已经到达的成交/终态，再核验当前确实仍可撤的原生订单。
    sync_execution(context)
    try:
        open_orders = get_open_orders() or {}
    except Exception as error:
        _execution_block('CANCEL_QUERY_FAILED', '未完成订单查询失败，保留委托占用：' + str(error))
        return
    _execution_clear('CANCEL_QUERY_FAILED')
    visible = {str(getattr(native, 'order_id', oid)): native for oid, native in open_orders.items()}
    requested = False
    timeout = _execution_dt.timedelta(minutes=g.cfg.get('order_timeout_minutes', 2))
    for key, intent in list(g.orders.items()):
        if intent['terminal'] or intent.get('platform_terminal'):
            continue
        if side is not None and intent['side'] != side:
            continue
        if stock is not None and intent['stock'] != str(stock):
            continue
        if exempt_only and not intent.get('strong_exit_exempt'):
            continue
        # 当日查询无法证明历史委托的状态；不可用旧编号撤销今天的另一笔订单。
        if intent['submitted'].date() != context.current_dt.date():
            continue
        native = visible.get(str(intent['native_order_id']))
        if native is None:
            continue
        stamp = _execution_order_time(native)
        if (str(getattr(native, 'security', '')) != intent['stock']
                or (stamp is not None and stamp.date() != context.current_dt.date())):
            continue
        _execution_update_order(key, native)
        if (intent.get('platform_terminal') or intent['status'] not in ('new', 'open', 'filled')
                or intent['reported_filled'] >= intent['qty']):
            continue
        # 盘前报单的超时从连续交易开市起算，给订单保留首次撮合机会。
        start = _execution_builtin.max(intent['submitted'],
            context.current_dt.replace(hour=9, minute=30, second=0, microsecond=0))
        if not force and context.current_dt - start < timeout:
            continue
        last_attempt = intent.get('cancel_last_attempt')
        if last_attempt is not None and context.current_dt - last_attempt < _execution_dt.timedelta(
                minutes=g.cfg.get('cancel_retry_minutes', 2)):
            continue
        if intent.get('cancel_attempts', 0) >= g.cfg.get('cancel_max_attempts', 3):
            _execution_block('CANCEL_PENDING:' + str(key), '撤单未确认，继续对账并保留占用：' + intent['stock'])
            continue
        intent['cancel_last_attempt'] = context.current_dt
        intent['cancel_attempts'] = intent.get('cancel_attempts', 0) + 1
        try:
            result = cancel_order(native)
            requested = True
            if result is None:
                log_event('撤单未确认', '%s 委托%s 返回None，继续核对实际状态并保留占用' %
                          (intent['stock'], intent['native_order_id']))
            else:
                intent['cancel_requested'] = True
                _execution_update_order(key, result)
                log_event('撤单返回', '%s 委托%s，状态%s；剩余占用依终态与逐笔成交核对结果处理' %
                          (intent['stock'], intent['native_order_id'], intent['status']))
        except Exception as error:
            _execution_block('CANCEL_PENDING:' + str(key), '%s 撤单结果未知：%s' % (intent['stock'], error))
    if requested:
        sync_execution(context)


# ================================================================
# 市场仓位与持仓退出
# ================================================================
# 市场指标仅使用截至昨日的完整日线。趋势分按 40 分计，动量、波动、
# 市场结构分别为 30、20、10 分；指数风险警报在当日持续约束新增和减仓。
# 普通持仓的 ATR 持有期从首次真实成交日计算，第 1—3 个交易日用 1.8 倍，第 4 日起
# 用 1.5 倍。持仓高点从已知价格和完整分钟最高价累计，ATR 退出从 10:00
# 开始；低开、持有期、概念与指数风险退出不受该时间门槛限制。

import builtins as _risk_builtins


def initialize_risk_state():
    g.risk_day = None
    g.base_position_ratio = 0.0
    g.risk_cap = 1.0
    g.risk_alert = False
    g.market_score_details = {}
    g.risk_atr_cache = {}
    g.risk_day_counts = {}
    g.risk_index_samples = {}
    g.risk_minute_cursor = {}
    g.risk_day_highs = {}
    g.risk_open_checked = set()
    g.risk_basis_checked = set()
    g.risk_warned = set()
    g.risk_concept_clock = None


def reset_risk_day(context):
    """仅更新当天采样和缓存，持仓止损、首次成交日和退出原因持续保留。"""
    g.risk_day = context.current_dt.date()
    g.risk_cap = 1.0
    g.risk_alert = False
    g.risk_atr_cache = {}
    g.risk_day_counts = {}
    g.risk_index_samples = {}
    g.risk_minute_cursor = {}
    g.risk_day_highs = {}
    g.risk_open_checked = set()
    g.risk_basis_checked = set()
    g.risk_warned = set()
    g.risk_concept_clock = None


def _risk_warn_once(key, message):
    if key not in g.risk_warned:
        g.risk_warned.add(key)
        log_event('风控数据', message)


def _risk_date(value):
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return pd.Timestamp(value).date()


def _risk_daily_frame(context, stock, count, fields):
    frame = get_price(stock, end_date=context.previous_date, count=count,
                      frequency='daily', fields=list(fields), fq='pre',
                      skip_paused=True)
    if frame is None or frame.empty:
        raise ValueError('%s 日线为空' % stock)
    dates = pd.to_datetime(frame['time'] if 'time' in frame.columns else frame.index)
    if not dates.is_monotonic_increasing or dates.duplicated().any():
        raise ValueError('%s 日线时间不连续有序或重复' % stock)
    if _risk_builtins.any(stamp.date() > _risk_date(context.previous_date) for stamp in dates):
        raise ValueError('%s 日线包含尚未完成的日期' % stock)
    values = frame[list(fields)].astype(float)
    if not np.isfinite(values.values).all():
        raise ValueError('%s 日线存在非有限数值' % stock)
    for field in fields:
        if field != 'volume' and (values[field] <= 0).any():
            raise ValueError('%s %s 日线存在无效价格' % (stock, field))
    if 'volume' in fields and (values['volume'] < 0).any():
        raise ValueError('%s 成交量无效' % stock)
    return values


def calculate_market_ratio(context, limit_up_count):
    """在昨日涨停家数就绪后计算百分制仓位，缺失必需数据时不新增仓位。"""
    try:
        if limit_up_count is None or int(limit_up_count) < 0:
            raise ValueError('昨日涨停家数未就绪')
        index = g.cfg.get('index_code', '000001.XSHG')
        hist = _risk_daily_frame(context, index, 120, ('close', 'high', 'low', 'volume'))
        if len(hist) < 80:
            raise ValueError('指数完整日线不足 80 根')
        close = hist['close']
        ma3, ma10 = float(close.iloc[-3:].mean()), float(close.iloc[-10:].mean())
        ma20, ma60 = float(close.iloc[-20:].mean()), float(close.iloc[-60:].mean())
        last = float(close.iloc[-1])
        bull = 30 if ma3 > ma10 > ma20 > ma60 else (20 if ma3 > ma10 > ma20 else (10 if ma10 > ma20 else 0))
        previous_ma20 = float(close.iloc[-25:-5].mean())
        slope = (ma20 / previous_ma20 - 1.0) * 100.0
        slope_score = _risk_builtins.max(0.0, _risk_builtins.min(20.0, (slope + 2.0) * 5.0))
        bias = (last / ma20 - 1.0) * 100.0
        if bias > 5.0:
            bias_score = _risk_builtins.max(0.0, 15.0 - (bias - 5.0) * 3.0)
        elif bias < -5.0:
            bias_score = _risk_builtins.min(20.0, _risk_builtins.abs(bias) * 2.0)
        else:
            bias_score = 15.0
        trend_raw = bull + slope_score + bias_score
        trend = trend_raw * 40.0 / 70.0

        momentum_hist = hist.iloc[-80:]
        momentum_close = momentum_hist['close'].values
        rsi = talib.RSI(momentum_close, timeperiod=14)
        _, _, macd_hist = talib.MACD(momentum_close, fastperiod=12, slowperiod=26, signalperiod=9)
        if len(rsi) < 5 or len(macd_hist) < 3 or not np.isfinite(rsi[-5:]).all() or not np.isfinite(macd_hist[-3:]).all():
            raise ValueError('RSI / MACD 有效预热结果缺失')
        penalty = 0
        if last >= float(close.iloc[-10:].max()) * .998 and float(hist['volume'].iloc[-5:].mean()) < float(hist['volume'].iloc[-10:-5].mean()) * .85:
            penalty += 20
        if last > float(close.iloc[-5]) and rsi[-1] < rsi[-5] * .98:
            penalty += 15
        if macd_hist[-1] > 0 and macd_hist[-1] < macd_hist[-2] < macd_hist[-3]:
            penalty += 10
        momentum = _risk_builtins.max(0, 30 - penalty)

        a14 = float(talib.ATR(hist['high'].values, hist['low'].values, close.values, timeperiod=14)[-1])
        a60 = float(talib.ATR(hist['high'].values, hist['low'].values, close.values, timeperiod=60)[-1])
        if not is_finite_positive(a14) or not is_finite_positive(a60):
            raise ValueError('指数 ATR14 / ATR60 无效')
        atr_ratio = a14 / a60
        if atr_ratio < .8:
            volatility, coefficient = 20, 1.0
        elif atr_ratio > 1.5:
            volatility, coefficient = 5, .5
        elif atr_ratio > 1.2:
            volatility, coefficient = 10, .75
        else:
            volatility, coefficient = 15, 1.0

        volume_mean = float(hist['volume'].iloc[-5:].mean())
        if not is_finite_positive(volume_mean):
            raise ValueError('指数近五日成交量无效')
        volume_ratio = float(hist['volume'].iloc[-1]) / volume_mean
        if volume_ratio > 1.5:
            structure = 2 if int(limit_up_count) < 30 else 5
        elif volume_ratio > 1.2:
            structure = 10
        elif volume_ratio < .7:
            structure = 3
        else:
            structure = 8
        capital_flight_days = _risk_builtins.sum(
            float(close.iloc[i]) < float(close.iloc[i - 1])
            and float(hist['volume'].iloc[i]) > float(hist['volume'].iloc[i - 1]) * 1.1
            for i in (-3, -2, -1))
        total = trend + momentum + volatility + structure
        ratio = total / 100.0 * coefficient
        if capital_flight_days >= 2:
            ratio = _risk_builtins.min(ratio, .30)
        ratio = _risk_builtins.max(0.0, _risk_builtins.min(1.0, ratio))
        g.market_score_details = dict(trend_raw=trend_raw, trend=trend, momentum=momentum,
                                      volatility=volatility, structure=structure, total=total,
                                      coefficient=coefficient, limit_up_count=int(limit_up_count),
                                      capital_flight_days=capital_flight_days, ratio=ratio)
        log_event('市场仓位', '趋势 %.2f/40 动量 %.2f/30 波动 %.2f/20 结构 %.2f/10；昨日涨停 %d 家；总分 %.2f，波动乘数 %.2f，仓位系数 %.2f%%' %
                  (trend, momentum, volatility, structure, int(limit_up_count), total, coefficient, ratio * 100.0))
        return ratio
    except Exception as exc:
        g.market_score_details = dict(error=str(exc), ratio=0.0)
        log_event('市场仓位数据缺失', '暂停新增仓位，已有持仓退出继续：%s' % exc)
        return 0.0


def holding_days(context, entry_date):
    """首次实际成交所在交易日计为第 1 日；日期未知时返回 None。"""
    try:
        first = _risk_date(entry_date)
    except (TypeError, ValueError):
        return None
    today = context.current_dt.date()
    if first is None or first > today:
        return None
    key = (str(first), str(today))
    if key not in g.risk_day_counts:
        days = get_trade_days(start_date=first, end_date=today)
        count = len(days)
        g.risk_day_counts[key] = count if count > 0 else None
    return g.risk_day_counts[key]


def current_atr(context, stock):
    """持仓 ATR14 取完成日线，在同一交易日内固定。"""
    key = (context.current_dt.date(), str(stock))
    if key in g.risk_atr_cache:
        return g.risk_atr_cache[key]
    try:
        period = int(g.cfg.get('atr_period', 14))
        count = _risk_builtins.max(period + 1, int(g.cfg.get('atr_history_count', period + 1)))
        hist = _risk_daily_frame(context, stock, count, ('high', 'low', 'close'))
        if len(hist) < period + 1:
            raise ValueError('完整日线不足 ATR 初始化长度')
        value = float(talib.ATR(hist['high'].values, hist['low'].values, hist['close'].values, timeperiod=period)[-1])
        if not is_finite_positive(value):
            raise ValueError('ATR 不是有限正值')
        g.risk_atr_cache[key] = value
        return value
    except Exception as exc:
        _risk_warn_once(('atr', stock), '%s ATR 暂不可用：%s' % (stock, exc))
        return None


def effective_position_ratio():
    return _risk_builtins.max(0.0, _risk_builtins.min(1.0, float(g.base_position_ratio), float(g.risk_cap)))


def _risk_session_time(context):
    clock = context.current_dt.strftime('%H:%M')
    return ('09:30' <= clock <= '11:29') or ('13:00' <= clock <= '14:59')


def _risk_lock_cap(cap, reason):
    old = float(g.risk_cap)
    g.risk_cap = _risk_builtins.min(old, float(cap))
    g.risk_alert = True
    if g.risk_cap < old:
        log_event('指数风险', '%s；当日风险上限 %.0f%%，实际减仓受可卖数量和成交约束' % (reason, 100.0 * g.risk_cap))


def monitor_market_risk(context):
    if not _risk_session_time(context) or context.current_dt.minute % 5:
        return
    index = g.cfg.get('index_code', '000001.XSHG')
    try:
        quote = get_quote(context, index)
    except Exception as exc:
        _risk_warn_once('index_quote_error', '指数报价查询异常，保留已有风险上限：%s' % exc)
        return
    if not quote or not is_finite_positive(quote.get('last')):
        _risk_warn_once('index_quote', '指数最新报价缺失，无法判断盘中急跌')
        return
    now = context.current_dt.replace(second=0, microsecond=0)
    price = float(quote['last'])
    g.risk_index_samples[now] = price
    target = now - dt.timedelta(minutes=10)
    # 只比较精确间隔十分钟的同日采样，不跨午休或沿用昨日报价。
    previous = g.risk_index_samples.get(target)
    g.risk_index_samples = {stamp: value for stamp, value in g.risk_index_samples.items()
                            if stamp.date() == now.date() and stamp >= now - dt.timedelta(minutes=30)}
    if previous and price / previous - 1.0 < -float(g.cfg.get('risk_drop_10m', .015)):
        _risk_lock_cap(g.cfg.get('risk_emergency_cap', .30), '指数十分钟跌幅 %.2f%%' % ((price / previous - 1.0) * 100.0))


def _risk_previous_close(context, stock):
    key = ('risk_previous_close', context.current_dt.date(), stock)
    if key not in g.daily_cache:
        frame = _risk_daily_frame(context, stock, 1, ('close',))
        g.daily_cache[key] = float(frame['close'].iloc[-1])
    return g.daily_cache[key]


def midday_risk_check(context):
    try:
        index = g.cfg.get('index_code', '000001.XSHG')
        frame = get_price(index, start_date=context.current_dt.strftime('%Y-%m-%d 09:30:00'),
                          end_date=context.current_dt, frequency='1m', fields=['close'], fq='pre')
        if frame is None or frame.empty:
            raise ValueError('上午已完成分钟数据缺失')
        times = pd.to_datetime(frame['time'] if 'time' in frame.columns else frame.index)
        valid = (times <= pd.Timestamp(context.current_dt)) & (times >= pd.Timestamp(context.current_dt.date()))
        completed = frame.loc[valid]
        if completed.empty:
            raise ValueError('没有当前时刻之前的上午分钟数据')
        price = float(completed['close'].iloc[-1])
        previous = _risk_previous_close(context, index)
        if not is_finite_positive(price):
            raise ValueError('上午收盘价格无效')
        change = price / previous - 1.0
        log_event('午间指数', '上午涨跌幅 %.2f%%' % (change * 100.0))
        if change < -float(g.cfg.get('midday_drop', .015)):
            _risk_lock_cap(g.cfg.get('midday_cap', .50), '上午指数跌幅 %.2f%%' % (change * 100.0))
    except Exception as exc:
        _risk_warn_once('midday', '午间指数检查未完成：%s' % exc)


def prepare_position_price_basis(context):
    """同一历史锚点的动态前复权价格比例同步高点和止损，不改成交账本。"""
    for marker in list(g.execution_blockers):
        if not str(marker).startswith('risk_price_basis:'):
            continue
        stock = str(marker).split(':', 1)[1]
        position = context.portfolio.positions.get(stock)
        if stock not in g.book and (position is None or position_total(position) <= 0):
            g.execution_blockers.discard(marker)
            g.risk_basis_checked.discard(stock)
    for stock, book in list(g.book.items()):
        if stock in g.risk_basis_checked:
            continue
        marker = 'risk_price_basis:' + str(stock)
        try:
            anchor_date = book.get('price_basis_anchor_date') or context.previous_date
            frame = get_price(stock, end_date=anchor_date, count=1, frequency='daily',
                              fields=['close'], fq='pre', skip_paused=True)
            if frame is None or frame.empty:
                raise ValueError('价格锚点为空')
            new_anchor = float(frame['close'].iloc[-1])
            if not is_finite_positive(new_anchor):
                raise ValueError('价格锚点非有限正值')
            old_anchor = book.get('price_basis_anchor_close')
            if is_finite_positive(old_anchor):
                ratio = new_anchor / float(old_anchor)
                if _risk_builtins.abs(ratio - 1.0) > 1e-8:
                    for field in ('high', 'stop'):
                        if is_finite_positive(book.get(field)):
                            book[field] *= ratio
                    book['price_basis_factor'] = float(book.get('price_basis_factor') or 1.0) * ratio
                    log_event('持仓价格基准', '%s 高点与止损按 %.8f 同步，真实成交价格和数量以平台记录为准' % (stock, ratio))
            else:
                book['price_basis_factor'] = float(book.get('price_basis_factor') or 1.0)
            book['price_basis_anchor_date'] = str(_risk_date(anchor_date))
            book['price_basis_anchor_close'] = new_anchor
            g.risk_basis_checked.add(stock)
            g.execution_blockers.discard(marker)
        except Exception as exc:
            g.execution_blockers.add(marker)
            _risk_warn_once(('basis', stock), '%s 持仓价格基准待核对：%s；其他可用退出继续' % (stock, exc))


def _risk_collect_highs(context, quotes):
    """全部持仓共用一次增量分钟查询，概念日内高点与持仓 ATR 高点分别累计。"""
    starts = {}
    day_start = context.current_dt.replace(hour=9, minute=31, second=0, microsecond=0)
    for stock, quote in quotes.items():
        book = g.book[stock]
        price = float(quote['last'])
        book['high'] = _risk_builtins.max(float(book.get('high') or price), price)
        known_day_high = _risk_builtins.max(float(g.risk_day_highs.get(stock, price)), price)
        if is_finite_positive(quote.get('open')):
            known_day_high = _risk_builtins.max(known_day_high, float(quote['open']))
        g.risk_day_highs[stock] = known_day_high
        cursor = g.risk_minute_cursor.get(stock)
        start = _risk_builtins.max(day_start, cursor + dt.timedelta(seconds=1)) if cursor is not None else day_start
        if start <= context.current_dt:
            starts[stock] = start
    if not starts:
        return
    try:
        frame = get_price(list(starts), start_date=_risk_builtins.min(starts.values()),
                          end_date=context.current_dt, frequency='1m', fields=['high'],
                          fq='pre', skip_paused=False, panel=False, fill_paused=False)
        if frame is None or frame.empty:
            return
        frame = frame.copy()
        if 'code' not in frame.columns:
            if len(starts) != 1:
                raise ValueError('批量分钟数据缺少股票代码')
            frame['code'] = list(starts)[0]
        frame['_risk_time'] = pd.to_datetime(frame['time'] if 'time' in frame.columns else frame.index)
        for stock, rows in frame.groupby('code', sort=False):
            stock = str(stock)
            if stock not in starts:
                continue
            rows = rows.loc[(rows['_risk_time'] >= pd.Timestamp(starts[stock])) &
                            (rows['_risk_time'] <= pd.Timestamp(context.current_dt))]
            highs = pd.to_numeric(rows['high'], errors='coerce')
            rows = rows.loc[np.isfinite(highs) & (highs > 0)].copy()
            if rows.empty:
                continue
            # 概念事件使用整个当日已完成行情，包括入场以前发生的触板。
            g.risk_day_highs[stock] = _risk_builtins.max(g.risk_day_highs[stock], float(rows['high'].max()))
            book = g.book[stock]
            first = book.get('entry_time')
            owned_start = day_start
            if first is not None:
                first = pd.Timestamp(first).to_pydatetime()
                if first.date() == context.current_dt.date():
                    owned_start = first.replace(second=0, microsecond=0) + dt.timedelta(minutes=1 + int(bool(first.second or first.microsecond)))
                    # 09:31分钟包含09:25集合竞价；开盘后买入不能把整根高点算作持仓高点。
                    if first < day_start:
                        owned_start = _risk_builtins.max(owned_start, day_start + dt.timedelta(minutes=1))
            owned_rows = rows.loc[rows['_risk_time'] >= pd.Timestamp(owned_start)]
            if not owned_rows.empty:
                book['high'] = _risk_builtins.max(book['high'], float(owned_rows['high'].max()))
            g.risk_minute_cursor[stock] = context.current_dt
    except Exception as exc:
        _risk_warn_once('minute_high_batch', '完整分钟高点暂不可用，仅累计已知报价：%s' % exc)


def _risk_update_high(context, stock, book, quote):
    _risk_collect_highs(context, {stock: quote})


def _risk_request_exit(context, stock, book, reason):
    if book.get('strong_trend') and strong_exit_exempt(context, stock, book, reason):
        return False
    # 原因持续保留，T+1、停牌、拒单和部分成交都不代表仓位已经退出。
    previous_reason = book.get('exit_reason')
    preopen_gap = (context.current_dt.strftime('%H:%M:%S') == '09:27:00'
                   and str(reason).startswith('开盘低开'))
    if preopen_gap and previous_reason and previous_reason != reason:
        book['previous_exit_reason'] = previous_reason
    if (not previous_reason or preopen_gap
            or (str(previous_reason).startswith('ATR ') and not str(reason).startswith('ATR '))):
        book['exit_reason'] = reason
        log_event('退出信号', '%s %s' % (stock, reason))
    if str(book['exit_reason']).startswith('ATR ') and context.current_dt.strftime('%H:%M') < g.cfg.get('atr_start_time', '10:00'):
        return False
    position = context.portfolio.positions.get(stock)
    if position is None or position_total(position) <= 0 or active_order(stock):
        return False
    closeable = int(getattr(position, 'closeable_amount', 0))
    if closeable <= 0:
        _risk_warn_once(('closeable', stock), '%s 已有退出信号，当前无可卖数量，继续保留持仓风控' % stock)
        return False
    return submit_sell(context, stock, _risk_builtins.min(closeable, position_total(position)), book['exit_reason'])


def _risk_check_concepts(context, quotes):
    now = context.current_dt.replace(second=0, microsecond=0)
    if now.minute % 5 or g.risk_concept_clock == now:
        return
    g.risk_concept_clock = now
    holdings = [stock for stock in g.book if stock in context.portfolio.positions and position_total(context.portfolio.positions[stock]) > 0]
    threshold = int(g.cfg.get('concept_count', 3))
    if len(holdings) < threshold:
        return
    counts = {}
    for stock in holdings:
        try:
            quote = quotes.get(stock)
            if not quote or quote.get('paused') or not is_finite_positive(quote.get('high_limit')):
                continue
            limit = float(quote['high_limit'])
            high = float(g.risk_day_highs.get(stock, quote['last']))
            if high >= limit * float(g.cfg.get('concept_touch_ratio', .998)) and float(quote['last']) < limit * float(g.cfg.get('concept_open_ratio', .995)):
                for concept in set(getattr(g, 'concepts_by_stock', {}).get(stock, ())):
                    counts[concept] = counts.get(concept, 0) + 1
        except Exception as exc:
            _risk_warn_once(('concept_count', stock), '%s 概念触板计数暂不可用：%s' % (stock, exc))
    affected = {concept for concept, count in counts.items() if count >= threshold}
    if not affected:
        return
    for stock in holdings:
        try:
            overlap = affected.intersection(getattr(g, 'concepts_by_stock', {}).get(stock, ()))
            if overlap:
                _risk_request_exit(context, stock, g.book[stock], '概念集中炸板 ' + ','.join(sorted(str(value) for value in overlap)))
        except Exception as exc:
            _risk_warn_once(('concept_exit', stock), '%s 概念退出提交未完成，保留信号：%s' % (stock, exc))


def monitor_open_gap(context):
    """09:27以已形成的开盘价检查低开6%，普通ATR仍从10:00起执行。"""
    if context.current_dt.strftime('%H:%M:%S') != '09:27:00':
        return
    for stock, book in list(g.book.items()):
        try:
            position = context.portfolio.positions.get(stock)
            if (position is None or position_total(position) <= 0
                    or book.get('strong_trend') or stock in g.risk_open_checked):
                continue
            age = holding_days(context, book.get('entry_date'))
            if age is not None and age <= 1:
                continue
            quote = get_quote(context, stock)
            if quote.get('paused') or not is_finite_positive(quote.get('open')):
                continue
            previous_close = _risk_previous_close(context, stock)
            g.risk_open_checked.add(stock)
            if float(quote['open']) <= previous_close * (1.0 - float(g.cfg.get('open_gap_exit', .06))) + 1e-10:
                _risk_request_exit(context, stock, book, '开盘低开达到 %.1f%%' %
                                   (100.0 * float(g.cfg.get('open_gap_exit', .06))))
        except Exception as exc:
            _risk_warn_once(('opening_previous', stock), '%s 盘前低开检查暂不可用，盘中继续核对：%s' % (stock, exc))


def monitor_positions(context):
    if not _risk_session_time(context):
        return
    prepare_position_price_basis(context)
    clock = context.current_dt.strftime('%H:%M')
    quotes = {}
    for stock in list(g.book):
        position = context.portfolio.positions.get(stock)
        if position is None or position_total(position) <= 0:
            continue
        try:
            quote = get_quote(context, stock)
        except Exception as exc:
            _risk_warn_once(('quote_error', stock), '%s 当前报价查询异常，其他持仓继续监控：%s' % (stock, exc))
            continue
        if quote and is_finite_positive(quote.get('last')):
            quotes[stock] = quote
        else:
            _risk_warn_once(('quote', stock), '%s 当前报价缺失，持仓与退出状态保留' % stock)
    _risk_collect_highs(context, quotes)
    for stock, book in list(g.book.items()):
        position = context.portfolio.positions.get(stock)
        if position is None or position_total(position) <= 0:
            continue
        try:
            quote = quotes.get(stock)
            if not quote:
                continue
            if book.get('strong_trend'):
                monitor_strong_position(context, stock, book, quote)
                continue
            age = holding_days(context, book.get('entry_date'))
            # 持有日未知的恢复持仓仍执行低开、概念及指数风险退出。
            if age is None:
                _risk_warn_once(('age', stock), '%s 首次成交日待核对，暂不臆造 ATR 阶段或持有到期日' % stock)
            else:
                atr = current_atr(context, stock)
                if atr is not None and stock in g.risk_basis_checked:
                    multiplier = float(g.cfg.get('atr_early_multiplier', 1.8) if age <= int(g.cfg.get('atr_early_days', 3)) else g.cfg.get('atr_multiplier', 1.5))
                    candidate = float(book['high']) - multiplier * atr
                    previous_stop = float(book.get('stop') or 0.0)
                    book['stop'] = _risk_builtins.max(previous_stop, candidate)
                    if book.get('atr_multiplier') != multiplier:
                        book['atr_multiplier'] = multiplier
                        log_event('ATR 阶段', '%s 持有第 %d 交易日，倍数 %.2f，止损 %.3f，退出起点 %s' % (stock, age, multiplier, book['stop'], g.cfg.get('atr_start_time', '10:00')))
            if book.get('exit_reason') and (not str(book['exit_reason']).startswith('ATR ') or clock >= g.cfg.get('atr_start_time', '10:00')):
                _risk_request_exit(context, stock, book, book['exit_reason'])
                continue

            if not quote.get('paused') and stock not in g.risk_open_checked and (age is None or age > 1):
                opening = quote.get('open')
                if is_finite_positive(opening):
                    try:
                        previous_close = _risk_previous_close(context, stock)
                        g.risk_open_checked.add(stock)
                        if float(opening) <= previous_close * (1.0 - float(g.cfg.get('open_gap_exit', .06))) + 1e-10:
                            _risk_request_exit(context, stock, book, '开盘低开达到 %.1f%%' % (100.0 * float(g.cfg.get('open_gap_exit', .06))))
                            continue
                    except Exception as exc:
                        _risk_warn_once(('opening_previous', stock), '%s 低开检查前收盘缺失，其他退出继续：%s' % (stock, exc))
            if age is not None and age >= int(g.cfg.get('max_hold_days', 10)):
                _risk_request_exit(context, stock, book, '持有满 %d 个交易日' % int(g.cfg.get('max_hold_days', 10)))
                continue
            if not quote.get('paused') and clock >= g.cfg.get('afternoon_exit_time', '14:30') and is_finite_positive(quote.get('low_limit')) and float(quote['last']) <= float(quote['low_limit']) * (1.0 + float(g.cfg.get('afternoon_limit_buffer', .005))):
                _risk_request_exit(context, stock, book, '尾盘接近跌停')
                continue
            # 首日可以累计高点；自身 ATR 退出只针对有可卖股份的持仓。
            if not quote.get('paused') and clock >= g.cfg.get('atr_start_time', '10:00') and age is not None and int(getattr(position, 'closeable_amount', 0)) > 0 and stock in g.risk_basis_checked and is_finite_positive(book.get('stop')) and float(quote['last']) <= float(book['stop']):
                _risk_request_exit(context, stock, book, 'ATR 跟踪止损')
        except Exception as exc:
            _risk_warn_once(('position', stock), '%s 持仓监控异常，状态保留：%s' % (stock, exc))
    _risk_check_concepts(context, quotes)


def reduce_risk_exposure(context):
    """指数警报下按低优先级先减仓；未成交卖单不作为已释放资金。"""
    if not g.risk_alert or not _risk_session_time(context):
        return
    # 买单撤销申请后仍占预算；撤单终态和成交均由执行同步确认。
    for intent in list(g.orders.values()):
        if not intent.get('terminal') and intent.get('side') == 'buy':
            cancel_stale_orders(context, force=True, side='buy')
            return
    nav = float(context.portfolio.total_value)
    target = nav * effective_position_ratio()
    actual = portfolio_exposure(context)
    excess = actual - target
    tolerance = nav * float(g.cfg.get('risk_reduce_tolerance', .005))
    if excess <= tolerance:
        return
    if _risk_builtins.any(not intent.get('terminal') and intent.get('side') == 'sell' for intent in g.orders.values()):
        return
    priorities = {'combo_3': 1, 'combo_4': 2, 'combo_2': 3, 'combo_6': 4}
    ranked = sorted(g.book, key=lambda stock: (int(g.book[stock].get('combo', {}).get('priority', priorities.get(g.book[stock].get('combo', {}).get('combo_type'), 99))), stock), reverse=True)
    for stock in ranked:
        if g.book[stock].get('strong_trend'):
            continue
        position = context.portfolio.positions.get(stock)
        if position is None or active_order(stock):
            continue
        closeable = int(getattr(position, 'closeable_amount', 0))
        if closeable <= 0:
            continue
        try:
            quote = get_quote(context, stock)
        except Exception as exc:
            _risk_warn_once(('reduce_quote', stock), '%s 减仓报价查询异常，继续检查其他持仓：%s' % (stock, exc))
            continue
        if not quote or quote.get('paused') or not is_finite_positive(quote.get('last')):
            continue
        price = float(quote['last'])
        desired = int(np.ceil(excess / price / 100.0)) * 100
        qty = _risk_builtins.min(closeable, desired)
        if qty < closeable:
            qty = (qty // 100) * 100
        if qty > 0:
            try:
                if submit_sell(context, stock, qty, '指数风险减仓'):
                    return
            except Exception as exc:
                _risk_warn_once(('reduce_submit', stock), '%s 指数减仓提交异常，继续检查其他持仓：%s' % (stock, exc))
    _risk_warn_once('risk_reduce_blocked', '当前仓位高于风险目标，受强趋势豁免、T+1、停牌、行情或订单约束，保留实际持仓并继续检查')


# ============================================================================
# 强趋势识别、尾盘退出与连续一字涨停开板观察
# ============================================================================
# 强趋势资格由盘前已完成收盘和平台持仓成本确定，标记持续到真实清仓。
# 强趋势仓位只产生14:54走弱退出，豁免普通退出及指数主动减仓，仍占资金预算。
# 当日临时均线由历史收盘和同一当前报价合成，不读取当日最终日线。


def is_strong_exit_reason(reason):
    return str(reason or '').startswith('14:54强趋势走弱退出:')


def strong_exit_exempt(context, stock, book, reason):
    if not book.get('strong_trend'):
        return False
    return (not is_strong_exit_reason(reason) or
            book.get('strong_oneword_observation_day') == str(context.current_dt.date()))


def strong_trend_qualified(stock, age, profit):
    threshold = g.cfg.get('strong_trend_growth_profit', .229) if str(stock).startswith(('300', '301')) else g.cfg.get('strong_trend_profit', .224)
    return age is not None and age >= g.cfg.get('strong_trend_age', 4) and math.isfinite(profit) and profit >= threshold - 1e-12


def _strong_dates(context, count=None, start=None, end=None):
    end = _risk_date(end or context.previous_date)
    key = ('strong_calendar', str(start), str(end), count)
    if key not in g.daily_cache:
        args = dict(end_date=end)
        if start is not None:
            args['start_date'] = _risk_date(start)
        else:
            args['count'] = count
        g.daily_cache[key] = [_risk_date(value) for value in get_trade_days(**args)]
    return list(g.daily_cache[key])


def _strong_checked_frame(frame, end, start=None):
    if frame is None or frame.empty:
        raise ValueError('历史数据为空')
    result = frame.copy()
    result.index = pd.to_datetime(result['time'] if 'time' in result.columns else result.index)
    if result.index.has_duplicates or not result.index.is_monotonic_increasing:
        raise ValueError('历史时间重复或未按时间排序')
    if any(value.date() > _risk_date(end) for value in result.index):
        raise ValueError('日线含尚未完成的日期')
    if start is not None and any(value.date() < _risk_date(start) for value in result.index):
        raise ValueError('历史日期早于指定起点')
    return result


def _strong_closes(context, stock, count=None, start=None):
    key = ('strong_closes', stock, str(context.previous_date), count, str(start))
    if key not in g.daily_cache:
        args = dict(end_date=context.previous_date, frequency='daily', fields=['close'],
                    fq='pre', skip_paused=False)
        if start is None:
            args['count'] = count
        else:
            args['start_date'] = start
        frame = _strong_checked_frame(get_price(stock, **args), context.previous_date, start)
        values = pd.to_numeric(frame['close'], errors='coerce')
        if not np.isfinite(values.values).all() or (values <= 0).any():
            raise ValueError('收盘价格不是有限正值')
        frame['close'] = values
        g.daily_cache[key] = frame
    return g.daily_cache[key]


def _strong_previous_close(context, stock):
    frame = _strong_closes(context, stock, count=1)
    if len(frame) != 1 or frame.index[-1].date() != _risk_date(context.previous_date):
        raise ValueError('前收盘日期不匹配')
    return float(frame['close'].iloc[-1])


def prepare_strong_states(context):
    """盘前识别，09:30前允许缺数重试；盘中不借变化后的成本新授予豁免。"""
    if context.current_dt.strftime('%H:%M') > '09:30':
        return
    day = str(context.current_dt.date())
    for stock, book in list(g.book.items()):
        if book.get('strong_trend') or book.get('strong_qualification_day') == day:
            continue
        try:
            position = context.portfolio.positions.get(stock)
            if position is None or book.get('qty', 0) <= 0 or position_total(position) != book['qty']:
                continue
            age = holding_days(context, book.get('entry_date'))
            if age is None:
                raise ValueError('首次真实成交日期未知')
            if age < g.cfg.get('strong_trend_age', 4):
                book['strong_qualification_day'] = day
                continue
            if stock not in g.risk_basis_checked:
                raise ValueError('持仓价格基准尚未核验')
            cost = float(getattr(position, 'avg_cost', float('nan')))
            if not is_finite_positive(cost):
                raise ValueError('平台持仓成本无效')
            previous = _strong_previous_close(context, stock)
            profit = previous / cost - 1.0
            if strong_trend_qualified(stock, age, profit):
                book.update(strong_trend=True, strong_mark_date=day, strong_mark_profit=profit,
                            strong_mark_age=age, strong_mark_anchor_date=str(context.previous_date))
                log_event('强趋势标记', '%s | 第%d交易日 | 昨收%.3f/平台成本%.3f/浮盈%.2f%% | 标记保留至清仓，仅按强趋势退出管理' %
                          (stock, age, previous, cost, profit*100))
            book['strong_qualification_day'] = day
        except Exception as exc:
            _risk_warn_once(('strong_qualify', stock), '%s 强趋势资格暂不可核验：%s；不臆造标记' % (stock, exc))


def strong_oneword_history(context, stock, book):
    """最近两完整交易日必须均处于强趋势标记期间，使用原始OHLC与各日涨停价。"""
    key = ('strong_oneword', stock, str(context.previous_date), book.get('strong_mark_date'))
    if key in g.daily_cache:
        return g.daily_cache[key]
    result = dict(available=False, eligible=False, dates=[], error=None)
    try:
        mark = _risk_date(book.get('strong_mark_date'))
        if mark is None or mark > context.current_dt.date():
            raise ValueError('强趋势标记日期无效')
        expected = _strong_dates(context, count=2)
        if len(expected) != 2 or expected[-1] != _risk_date(context.previous_date):
            raise ValueError('最近两个交易日缺失')
        result['dates'] = [str(day) for day in expected]
        if expected[0] < mark:
            result['available'] = True
        else:
            fields = ['open', 'high', 'low', 'close', 'high_limit', 'paused', 'volume']
            frame = _strong_checked_frame(get_price(stock, end_date=context.previous_date,
                count=2, frequency='daily', fields=fields, fq=None, skip_paused=False), context.previous_date)
            if list(frame.index.date) != expected:
                raise ValueError('一字涨停历史没有覆盖指定两日')
            flags = []
            for _, row in frame.iterrows():
                v = {field: float(row[field]) for field in fields}
                if not all(is_finite_positive(v[field]) for field in fields[:5]):
                    raise ValueError('一字涨停历史价格无效')
                if v['paused'] not in (0., 1.) or not math.isfinite(v['volume']) or v['volume'] < 0:
                    raise ValueError('停牌或成交量字段无效')
                if (v['paused'] == 1 and v['volume'] != 0) or (v['paused'] == 0 and v['volume'] <= 0):
                    raise ValueError('停牌与成交量互相冲突')
                if v['high'] < max(v['open'], v['close'], v['low']) - 1e-8 or v['low'] > min(v['open'], v['close']) + 1e-8 or v['high'] > v['high_limit'] + .005:
                    raise ValueError('历史OHLC次序或涨停价格异常')
                flags.append(v['paused'] == 0 and v['volume'] > 0 and
                             all(abs(v[field]-v['high_limit']) <= .005 for field in fields[:4]))
            result.update(available=True, eligible=all(flags))
    except Exception as exc:
        result['error'] = str(exc)
    g.daily_cache[key] = result
    return result


def _strong_minutes(context):
    """保守使用截至前一分钟的完整交易分钟，排除午休时段。"""
    day = str(context.current_dt.date())
    expected = pd.date_range(day+' 09:31', day+' 11:30', freq='min').union(
        pd.date_range(day+' 13:01', day+' 15:00', freq='min'))
    cutoff = pd.Timestamp(context.current_dt - dt.timedelta(minutes=1))
    return expected[expected <= cutoff], cutoff


def _strong_minute_rows(context, stock):
    """逐股缓存完整原始分钟极值，后续只补缺失区间，保留缺口而不虚构行情。"""
    expected, cutoff = _strong_minutes(context)
    key = ('strong_minutes', str(context.current_dt.date()), stock)
    cache = g.daily_cache.setdefault(key, dict(rows={}, probe=None, error=None))
    missing = [stamp for stamp in expected if stamp not in cache['rows']]
    if missing and cache['probe'] != str(context.current_dt):
        cache['probe'] = str(context.current_dt)
        start = missing[0] - dt.timedelta(minutes=1)
        try:
            frame = get_price(stock, start_date=start, end_date=cutoff.to_pydatetime(),
                frequency='1m', fields=['high', 'low', 'volume'], fq=None, skip_paused=False)
            if frame is None or frame.empty:
                raise ValueError('完整分钟数据为空')
            frame = frame.copy()
            frame.index = pd.to_datetime(frame['time'] if 'time' in frame.columns else frame.index)
            if frame.index.has_duplicates or not frame.index.is_monotonic_increasing or frame.index.min() < start or frame.index.max() > cutoff:
                raise ValueError('分钟时间重复、错序或越界')
            staged = {}
            for stamp, row in frame.iterrows():
                if stamp not in expected:
                    continue
                high, low, volume = (float(row[field]) for field in ('high', 'low', 'volume'))
                if not all(math.isfinite(v) for v in (high, low, volume)) or low <= 0 or high < low or volume < 0:
                    raise ValueError('分钟极值或成交量无效')
                staged[stamp] = dict(high=high, low=low, volume=volume)
            cache['rows'].update(staged)
            cache['error'] = None
        except Exception as exc:
            cache['error'] = str(exc)
    missing = [stamp for stamp in expected if stamp not in cache['rows']]
    if missing:
        raise ValueError(cache['error'] or '缺%d个完整分钟，首缺%s' % (len(missing), missing[0]))
    return [cache['rows'][stamp] for stamp in expected]


def strong_openboard_evidence(context, stock):
    q = get_quote(context, stock)
    opening, price, limit = q['open'], q['last'], q['high_limit']
    clock = context.current_dt.strftime('%H:%M')
    if clock < '09:27' or clock > '15:00' or q['paused'] or not all(is_finite_positive(v) for v in (opening, limit)):
        raise ValueError('开盘价或涨停价尚不可核验')
    if opening > limit + .005:
        raise ValueError('开盘价高于涨停价')
    if opening < limit - .005:
        return dict(opened=True, low=opening, source='当日开盘价')
    # 09:30及以前的last_price可能仍是昨收，不能作为开板证据。
    if clock <= '09:30':
        return dict(opened=False, low=opening, source='开盘封板，等待盘中')
    if not is_finite_positive(price) or price > limit + .005:
        raise ValueError('最新价与涨停价不可核验')
    if price < limit - .005:
        return dict(opened=True, low=price, source='当前报价')
    rows = _strong_minute_rows(context, stock)
    if any(row['high'] > limit + .005 for row in rows):
        raise ValueError('原始分钟高点超过当日涨停价')
    low = min([opening, price] + [row['low'] for row in rows if row['volume'] > 0])
    return dict(opened=low < limit - .005, low=low, source='完整分钟低价与已知报价')


def strong_oneword_observation_exempt(context, stock, book):
    if not book.get('strong_trend'):
        return False
    day = str(context.current_dt.date())
    if book.get('strong_oneword_observation_day') == day:
        return True
    if book.get('strong_oneword_probe') == str(context.current_dt):
        return False
    book['strong_oneword_probe'] = str(context.current_dt)
    history = strong_oneword_history(context, stock, book)
    if not history['available']:
        _risk_warn_once(('strong_oneword_history', stock), '%s 一字涨停历史缺数：%s；不推断豁免' % (stock, history['error']))
    if not history['eligible']:
        return False
    try:
        evidence = strong_openboard_evidence(context, stock)
        if evidence['opened']:
            book['strong_oneword_observation_day'] = day
            book['strong_oneword_observation_evidence'] = dict(at=str(context.current_dt), history=history, opening=evidence)
            log_event('强趋势开板观察', '%s 连续一字日%s，%s核验开板；今日豁免强趋势退出，回封仍有效，下一交易日恢复' %
                      (stock, history['dates'], evidence['source']))
            return True
    except Exception as exc:
        _risk_warn_once(('strong_openboard', stock), '%s 开板证据缺数：%s；不推断豁免' % (stock, exc))
    return False


def refresh_strong_exemptions(context):
    """先核验豁免再管理余单；失效退出只撤未成交部分，不改写实际成交。"""
    for stock, book in list(g.book.items()):
        if not book.get('strong_trend'):
            continue
        try:
            strong_oneword_observation_exempt(context, stock, book)
            reason = book.get('exit_reason')
            if reason and strong_exit_exempt(context, stock, book, reason):
                book['last_exempt_exit'] = dict(reason=reason, at=str(context.current_dt))
                book['exit_reason'] = None
                log_event('强趋势退出豁免', '%s 撤销退出意图:%s；真实成交和剩余持仓继续保留' % (stock, reason))
            obsolete = False
            for intent in g.orders.values():
                if intent['stock'] == stock and intent['side'] == 'sell' and not intent['terminal']:
                    if strong_exit_exempt(context, stock, book, intent.get('reason')):
                        intent['strong_exit_exempt'] = True
                    obsolete = obsolete or bool(intent.get('strong_exit_exempt'))
            if obsolete:
                cancel_stale_orders(context, force=True, side='sell', stock=stock, exempt_only=True)
        except Exception as exc:
            _risk_warn_once(('strong_exemption', stock), '%s 强趋势豁免同步异常：%s；保留真实订单等待核对' % (stock, exc))


def strong_close_history(context, stock, book):
    entry = _risk_date(book.get('entry_date'))
    anchor = _risk_date(book.get('strong_mark_anchor_date'))
    if entry is None or anchor is None:
        raise ValueError('入场日期或强趋势基准日期缺失')
    baseline = _strong_dates(context, count=2, end=entry)
    if len(baseline) != 2 or baseline[-1] != entry:
        raise ValueError('入场前收盘基准交易日缺失')
    start = min(baseline[0], anchor)
    frame = _strong_closes(context, stock, start=start)
    expected = _strong_dates(context, start=start)
    if not expected or list(frame.index.date) != expected:
        raise ValueError('持有期间完整收盘日期缺失或错位')
    return list(frame.index.date), [float(v) for v in frame['close']]


def strong_tail_evidence(price, previous, opening, extrema, dates, closes, anchor):
    """七项条件各自核验；某类历史缺失不妨碍其他完整证据触发退出。"""
    signals = dict(A=price/previous-1 < -.07-1e-12, B=None, C=None, D=None, E=None)
    values = dict(day_return=price/previous-1, high_drawdown=None, amplitude=None,
                  close_drawdown=None, down_days=None, down_return=None)
    if extrema.get('valid'):
        high, low = float(extrema['high']), float(extrema['low'])
        values.update(high_drawdown=1-price/high, amplitude=(high-low)/previous)
        signals['B'] = values['high_drawdown'] > .09+1e-12
        signals['C'] = values['amplitude'] > .12+1e-12 and is_finite_positive(opening) and price < opening*.975-1e-10 and price < previous-1e-10
    if dates and closes and anchor:
        selected = [value for day, value in zip(dates, closes) if _risk_date(day) >= _risk_date(anchor)]
        if selected:
            peak = max(selected+[price])
            values['close_drawdown'] = 1-price/peak
            signals['D'] = values['close_drawdown'] > .13+1e-12
        sequence = list(closes)+[price]
        end = len(sequence)-1
        start = end
        while start > 0 and sequence[start] < sequence[start-1]-1e-10:
            start -= 1
        days, move = end-start, price/sequence[start]-1
        values.update(down_days=days, down_return=move)
        signals['E'] = days >= 4 and move < -.085-1e-12
    return signals, values


def provisional_strong_mas(context, stock, price, previous):
    result = dict(ma10=None, ma20=None, errors={})
    if context.current_dt.strftime('%H:%M') != g.cfg.get('strong_exit_time', '14:54'):
        raise ValueError('不在强趋势尾盘检查时刻')
    frame = _strong_closes(context, stock, count=19)
    for period in (10, 20):
        try:
            tail = frame.tail(period-1)
            expected = _strong_dates(context, count=period-1)
            if len(expected) != period-1 or list(tail.index.date) != expected:
                raise ValueError('历史完整收盘不足或日期错位')
            if abs(float(tail['close'].iloc[-1])-previous) > .005+1e-10:
                raise ValueError('历史末收与前收盘基准不一致')
            result['ma%d' % period] = (sum(float(v) for v in tail['close'])+price)/period
        except Exception as exc:
            result['errors']['ma%d' % period] = str(exc)
    return result


def monitor_strong_position(context, stock, book, quote):
    """14:54产生新信号；已经确认的有效退出可在后续分钟和交易日继续成交。"""
    if book.get('strong_oneword_observation_day') == str(context.current_dt.date()):
        return
    if is_strong_exit_reason(book.get('exit_reason')):
        _risk_request_exit(context, stock, book, book['exit_reason'])
        return
    if context.current_dt.strftime('%H:%M') != g.cfg.get('strong_exit_time', '14:54'):
        return
    day = str(context.current_dt.date())
    if book.get('strong_tail_checked') == day:
        return
    book['strong_tail_checked'] = day
    try:
        if quote.get('paused') or not is_finite_positive(quote.get('last')) or stock not in g.risk_basis_checked:
            raise ValueError('当前价格、交易状态或复权基准不可核验')
        price, opening = float(quote['last']), quote.get('open')
        previous = _strong_previous_close(context, stock)
        extrema = dict(valid=False)
        try:
            if not is_finite_positive(opening):
                raise ValueError('当日开盘价不可核验')
            rows = _strong_minute_rows(context, stock)
            extrema = dict(valid=True, high=max([opening, price]+[r['high'] for r in rows]),
                           low=min([opening, price]+[r['low'] for r in rows]))
        except Exception as exc:
            _risk_warn_once(('strong_extrema', stock), '%s 日内高低点缺数：%s；其他强趋势条件继续' % (stock, exc))
        dates, closes = [], []
        try:
            dates, closes = strong_close_history(context, stock, book)
            if abs(closes[-1]-previous) > .005+1e-10:
                dates, closes = [], []
                raise ValueError('持有收盘历史与前收基准不一致')
        except Exception as exc:
            _risk_warn_once(('strong_close_history', stock), '%s 持有收盘缺数：%s；其他强趋势条件继续' % (stock, exc))
        signals, values = strong_tail_evidence(price, previous, opening, extrema, dates, closes, book.get('strong_mark_anchor_date'))
        signals.update(F=None, G=None)
        try:
            ma = provisional_strong_mas(context, stock, price, previous)
            values.update(ma10=ma['ma10'], ma20=ma['ma20'])
            for letter, field, coefficient in (('F', 'ma10', .97), ('G', 'ma20', .985)):
                if ma[field] is not None:
                    signals[letter] = bool(price <= ma[field]*coefficient+1e-10)
            if ma['errors']:
                _risk_warn_once(('strong_mas', stock), '%s 临时均线部分缺数:%s' % (stock, ma['errors']))
        except Exception as exc:
            _risk_warn_once(('strong_mas', stock), '%s 临时均线缺数：%s；A至E独立判断' % (stock, exc))
        log_event('强趋势14:54检查', '%s | A跌昨收7%% B距日高9%% C振幅12%%且弱于开盘/昨收 D收盘高点回撤13%% E连跌4日且8.5%% F临时MA10×.97 G临时MA20×.985 | %s | %s' % (stock, signals, values))
        triggered = [key for key, value in signals.items() if value is True]
        if triggered:
            book['strong_exit_evidence'] = dict(day=day, signals=signals, values=values,
                price=price, previous=previous, opening=opening, extrema=extrema)
            _risk_request_exit(context, stock, book, '14:54强趋势走弱退出:'+'/'.join(triggered))
    except Exception as exc:
        _risk_warn_once(('strong_tail', stock), '%s 强趋势尾盘检查不可用：%s；不臆造退出信号' % (stock, exc))


def strong_tail_session(context):
    if context.current_dt.strftime('%H:%M') == g.cfg.get('strong_exit_time', '14:54'):
        intraday_cycle(context)


# ============================================================================
# 日内调度、固定五名额预算与账户观察
# ============================================================================

def configure_order_cost(context):
    rate = .0005 if context.current_dt.date() >= dt.date(2023, 8, 28) else .001
    if getattr(g, 'sell_tax_rate', None) == rate:
        return
    set_order_cost(OrderCost(open_tax=0, close_tax=rate,
        open_commission=g.cfg['commission_rate'],
        close_commission=g.cfg['commission_rate'], close_today_commission=0,
        min_commission=g.cfg['min_commission']), type='stock')
    g.sell_tax_rate = rate


def portfolio_exposure(context):
    """包含挂卖冻结股票；未实际卖出的持仓仍占用资金预算。"""
    value = 0.0
    for stock, position in context.portfolio.positions.items():
        amount = position_total(position)
        if amount <= 0:
            continue
        price = float(position.price)
        if not is_finite_positive(price):
            raise ValueError('持仓估值价格无效: ' + str(stock))
        value += amount * price
    return value


def prepare_day(context):
    """当日价格缓存可以清空；真实订单、成交去重键和持仓风险状态持续保存。"""
    today = context.current_dt.date()
    if getattr(g, 'strategy_day', None) != today:
        g.strategy_day = today
        g.daily_cache = {}
        g._quote_cache = {}
        g._quote_stamp = None
        g.buy_attempted = set()
        g.sold_today = set()
        g.buy_session_day = None
        g.preparation_ready = False
        g.holding_concepts_ready = False
        g.base_position_ratio = 0.0
        g.risk_cap = 1.0
        initialize_selection_state()
        reset_risk_day(context)
    configure_order_cost(context)
    sync_execution(context)
    prepare_position_price_basis(context)
    reconcile_positions(context)
    run_management_stage(context, prepare_strong_states)
    run_management_stage(context, refresh_strong_exemptions)
    started = time.perf_counter()
    try:
        prepare_universe(context)
        if getattr(g, 'selection_error', None):
            raise ValueError(str(g.selection_error))
        g.base_position_ratio = calculate_market_ratio(context, g.limit_up_count)
        if getattr(g, 'market_score_details', {}).get('error'):
            raise ValueError(g.market_score_details['error'])
        if not math.isfinite(g.base_position_ratio):
            raise ValueError('市场仓位系数不是有效数值')
        g.preparation_ready = True
        log_event('盘前准备', '基础股票%d只 | 昨日涨停%d只 | 资金系数%.2f%% | 耗时%.2f秒' %
                  (len(g.universe), g.limit_up_count,
                   100*g.base_position_ratio, time.perf_counter()-started))
    except Exception as exc:
        g.preparation_ready = False
        g.base_position_ratio = 0.0
        g.signal_ready = False
        log_event('盘前数据不可用', '%s；暂停新增，持仓退出继续' % exc)


def prepare_entries(context):
    refresh_holding_concepts(context)
    if not getattr(g, 'preparation_ready', False):
        return
    started = time.perf_counter()
    try:
        g.candidates = select_candidates(context)
        if g.signal_ready:
            log_event('当日入围', '%d只 | 最多5只 | 耗时%.2f秒' %
                      (len(g.candidates), time.perf_counter()-started))
    except Exception as exc:
        g.signal_ready = False
        g.candidates = []
        log_event('选股数据不可用', '%s；当日不以异常空结果放开过滤' % exc)


def preopen_session(context):
    """09:27检查已有持仓低开风险；不改变已完成的候选列表。"""
    for stage in (sync_execution, prepare_position_price_basis, prepare_strong_states,
                  refresh_strong_exemptions, refresh_holding_concepts, monitor_open_gap):
        run_management_stage(context, stage)


def refresh_holding_concepts(context):
    """持仓概念独立于新增选股就绪状态，缺数时保留重试机会。"""
    try:
        g.holding_concepts_ready = bool(populate_holding_concepts(context))
    except Exception as exc:
        g.holding_concepts_ready = False
        log_event('持仓概念缺数', str(exc))


def budgeted_buy_quantity(budget, limit_price):
    """按参考价预检整手及估算佣金，实际委托量以Order.amount为准。"""
    if budget <= 0 or not is_finite_positive(limit_price):
        return 0
    quantity = int(budget / limit_price / 100) * 100
    while quantity > 0:
        commission = max(quantity*limit_price*g.cfg['commission_rate'],
                         g.cfg['min_commission'])
        if quantity*limit_price + commission <= budget + 1e-8:
            return quantity
        quantity -= 100
    return 0


def entry_is_one_word_limit(context, stock, quote):
    """开盘接近涨停时优先检查盘口；无tick权限时以开盘价回退判断。"""
    if quote['open'] < quote['high_limit'] * .995:
        return False
    try:
        tick = get_current_tick(str(stock))
        if tick:
            if tick['b1_v'] > 10000 and tick['a1_v'] == 0:
                return True
            if (quote['last'] >= quote['high_limit'] * .998
                    and quote['open'] >= quote['high_limit'] * .995):
                return True
    except Exception:
        return quote['open'] >= quote['high_limit'] * .995
    return False


def buy_finalists(context):
    """一次入场窗口；已有持仓不补仓，前5名以外不递补。"""
    if context.current_dt.strftime('%H:%M:%S') != '09:28:00':
        return
    today = context.current_dt.date()
    if getattr(g, 'buy_session_day', None) == today:
        return
    g.buy_session_day = today
    if not g.preparation_ready or not g.signal_ready:
        log_event('买入暂停', '基础数据或选股未完成')
        return
    if g.execution_blockers:
        log_event('买入暂停', '订单或持仓尚未完成对账: %s' % sorted(g.execution_blockers))
        return
    ratio = effective_position_ratio()
    if ratio <= 0:
        log_event('买入预算', '有效资金系数为0，不提交新买单')
        return
    for candidate in list(g.candidates)[:g.cfg['candidate_count']]:
        stock = str(candidate['stock'])
        if g.execution_blockers:
            break
        occupied = occupied_stocks(context)
        if len(occupied) >= g.cfg['max_positions']:
            break
        if stock in occupied or stock in g.buy_attempted or stock in g.sold_today:
            continue
        try:
            q = get_quote(context, stock)
            if q['paused'] or q['is_st'] or 'ST' in q['name'] or '退' in q['name']:
                continue
            if not all(is_finite_positive(q[k]) for k in ('last', 'open', 'high_limit')):
                continue
            if entry_is_one_word_limit(context, stock, q) or q['last'] >= q['high_limit']*.998:
                continue
            nav = float(context.portfolio.total_value)
            reserve = pending_buy_reserve()
            available_exposure = nav*ratio-portfolio_exposure(context)-reserve
            # available_cash已扣平台冻结现金，不能在此再扣一次相同冻结款。
            cash = float(context.portfolio.available_cash)
            budget = min(nav*ratio/g.cfg['unit_budget_divisor'], available_exposure,
                         cash-g.cfg['min_commission'], cash/(1+g.cfg['commission_rate']))
            if budget <= 0 or int(budget/q['last']/100) <= 0:
                continue
            atr = current_atr(context, stock)
            if not is_finite_positive(atr):
                log_event('买入数据不足', '%s ATR不可用' % stock)
                continue
            g.buy_attempted.add(stock)
            log_event('买入委托基准', '%s | 目标金额%.2f | 最新价%.4f | 开盘价%.4f | 09:28默认目标金额委托；成交另按Trade核对' %
                      (stock, budget, q['last'], q['open']))
            submit_buy_value(context, stock, budget, q['last'], candidate, atr)
        except Exception as exc:
            log_event('买入检查异常', '%s: %s' % (stock, exc))


def intraday_cycle(context):
    if not is_trading_time(context):
        return
    for stage in (sync_execution, prepare_strong_states, refresh_strong_exemptions,
                  cancel_stale_orders, reconcile_positions,
                  monitor_market_risk, monitor_positions, reduce_risk_exposure):
        run_management_stage(context, stage)


def run_management_stage(context, stage):
    """一项查询异常不关闭其他持仓退出；异常未恢复前暂停新增。"""
    marker = 'runtime_stage:' + stage.__name__
    try:
        stage(context)
        g.execution_blockers.discard(marker)
        return True
    except Exception as exc:
        if marker not in g.execution_blockers:
            log_event('管理阶段异常', '%s: %s；继续其他退出检查' % (stage.__name__, exc))
        g.execution_blockers.add(marker)
        return False


def opening_session(context):
    """09:28仅提交一次候选买单，盘前订单是否成交由平台回报决定。"""
    if context.current_dt.strftime('%H:%M:%S') != '09:28:00':
        return
    for stage in (sync_execution, reconcile_positions):
        run_management_stage(context, stage)
    buy_finalists(context)


def handle_data(context, data):
    """分钟回调始终管理真实持仓；日内数据准备失败也不关闭退出。"""
    intraday_cycle(context)


def midday_session(context):
    run_management_stage(context, sync_execution)
    run_management_stage(context, midday_risk_check)
    # 午休不报单；下午第一分钟根据已经锁定的风险上限执行减仓。


def finish_day(context):
    sync_execution(context)
    cancel_stale_orders(context, force=True)
    sync_execution(context)
    reconcile_positions(context)
    nav = float(context.portfolio.total_value)
    exposure = portfolio_exposure(context)
    log_event('账户日末', '净值资产%.2f | 股票市值%.2f | 实际仓位%.2f%% | 资金系数%.2f%% | 持仓%d只' %
              (nav, exposure, exposure/nav*100 if nav else 0,
               effective_position_ratio()*100,
               sum(position_total(p)>0 for p in context.portfolio.positions.values())))
    for stock, book in sorted(g.book.items()):
        position = context.portfolio.positions.get(stock)
        actual = position_total(position) if position else 0
        log_event('持仓日末', '%s | %s | 实际%d股 | 首次成交%s | 止损线%s | 状态:%s | 待退出:%s' %
                  (stock, book.get('combo', {}).get('combo_name', '持仓恢复'), actual,
                   book.get('entry_date'), book.get('stop'), '强趋势' if book.get('strong_trend') else '普通',
                   book.get('exit_reason') or '无'))
    if g.execution_blockers:
        log_event('待对账事项', str(sorted(g.execution_blockers)))
    record(exposure=exposure/nav if nav else 0,
           target_ratio=effective_position_ratio(),
           holding_count=sum(position_total(p)>0 for p in context.portfolio.positions.values()))


def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option('match_by_signal', True)
    set_benchmark('000852.XSHG')
    set_slippage(FixedSlippage(.005))
    g.cfg = dict(
        max_positions=5, candidate_count=5, unit_budget_divisor=5,
        use_concept_filter=True, history_count=80, max_hold_days=10,
        atr_period=14, atr_early_days=3, atr_early_multiplier=1.8,
        atr_multiplier=1.5, atr_start_time='10:00', open_gap_exit=.06,
        strong_trend_age=4, strong_trend_profit=.224, strong_trend_growth_profit=.229,
        strong_exit_time='14:54',
        order_timeout_minutes=2, commission_rate=.0003, min_commission=5,
        cancel_retry_minutes=2, cancel_max_attempts=3)
    g.strategy_day = None
    g.daily_cache = {}
    g.base_position_ratio = 0.0
    g.risk_cap = 1.0
    g.preparation_ready = False
    g.buy_attempted = set()
    g.sold_today = set()
    initialize_execution_state()
    initialize_selection_state()
    initialize_risk_state()
    configure_order_cost(context)
    run_daily(prepare_day, time='09:24:00')
    run_daily(prepare_entries, time='09:25:45')
    run_daily(preopen_session, time='09:27:00')
    run_daily(opening_session, time='09:28:00')
    run_daily(midday_session, time='11:30')
    run_daily(strong_tail_session, time='14:54')
    run_daily(finish_day, time='15:10')
    log_event('四形态趋势跟踪', '放量突破→主升浪回踩→缩量回调→多头排列；单账户固定5名额、5入围、预算分母5')
    log_event('资金管理', '单只标准=NAV×有效仓位系数÷5；真实持仓和未终结买单共同占用预算；不补旧仓、不递补入围外股票')
    log_event('普通退出规则', '首次成交日为第1日；前3交易日ATR×1.8，第4日起×1.5；10:00起ATR退出；低开6%退出；持有满10交易日退出')
    log_event('强趋势管理', '盘前持有至少4交易日且昨收对成本浮盈非创业22.4%/创业22.9%，标记至清仓；豁免普通退出与指数主动减仓，14:54七项走弱条件退出；连续两完整一字日后首次开板当日豁免强趋势退出')
    log_event('运行方式', '09:24市场准备；09:25:45选股；09:27低开检查；09:28目标金额买入委托；盘中至14:59持续管理；实际成交以平台Trade回报为准')
    log_event('撮合设置', 'match_by_signal=True；固定滑点配置0.005；成交价格与时间按平台该模式回报记录，参考报价不代替成交')
