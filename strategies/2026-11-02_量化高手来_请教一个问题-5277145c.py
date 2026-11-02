# Clone from JoinQuant
# postId: 5277145c5360aac8ecf765208c5b219b
# backtestId: 3f424bfe6f74c0bb57d876381be3267a
# title: 量化高手来，请教一个问题

# 克隆自聚宽文章：https://www.joinquant.com/post/77656
# 标题：七星+择时，回撤15收益88倍
# 作者：徐丁丁

# 克隆自聚宽文章：https://www.joinquant.com/post/73708
# 标题：七星175五年4597%回撤13%
# 作者：yyh001
# 新增：日内趋势择时（一次性买入版，基于五福5.2日内趋势逻辑改造）

"""
    策略自动判断当前是趋势行情还是震荡行情，并切换不同的滤波器：

        正常期 → 拉普拉斯滤波器（灵敏，跟趋势）
        震荡期 → 高斯滤波器（平滑，防假信号）

    ==========================================================

    震荡期机制（策略核心特色）
        通过监测沪深300ETF（510300）的技术状态，自动切换：

    【进入震荡期的条件】（任一触发即切换）
        ① 乖离率 > 8%：价格偏离20日均线过远
        ② RSI超买回落：RSI从>70跌破65

    【退出震荡期的条件】（任一触发即切换）
        ① 从近20日最低点上涨 ≥ 4%
        ② 连续企稳信号：回撤< 2% + 至少2个企稳指标 + 连续≥2天
        ③ 震荡期满20个交易日，强制退出

    【冷却机制】
        切换后有3个交易日的冷却期，防止频繁翻转。

    【两种滤波器的区别】
        拉普拉斯滤波器（正常期）：
        - 本质是指数加权移动平均（EMA的变体）
        - 对价格变化反应灵敏，适合趋势追踪
        - 参数 s=0.05，斜率阈值 0.002

        高斯滤波器（震荡期）：
        - 高斯核加权平均，越远的数据衰减越快
        - 比拉普拉斯更平滑，过滤噪音能力更强
        - 参数 sigma=1.2，斜率阈值 0.002
        - 震荡市中会过滤掉更多标的 → 更容易进入防御

    ==========================================================
    
    【新增：日内趋势择时】
        - 13:08 先判断目标ETF日内30分钟趋势
        - 上涨趋势 → 一次性全额买入
        - 下跌趋势 → 推迟到14:55 一次性强制买入
        - 不分批建仓，全程仅一次买入操作
"""

# 七星175（原 七星173_动量13_阴跌防守v2）
# 克隆自聚宽文章：https://www.joinquant.com/post/70329
# 标题：60倍七星高照+高斯+拉普拉斯
# 作者：king088

# 克隆自聚宽文章：https://www.joinquant.com/post/69163
# 标题：【策略优化】ETF轮动策略优化-V1.7.2
# 作者：晨曦量化

import math
import datetime
import json
import re
import numpy as np
import pandas as pd
from jqdata import *

# ---------- 研究环境 sim_sync（自动，无需开关）----------
# 回测：末日 write_file；接续日 09:09 对齐持仓；模拟/实盘：仅恢复 g（持仓以账户为准）
SIM_SYNC_FILE = 'sim_sync.json'

# ---------- stream → Redis（本机 consumer 落盘）----------
# 回测且研究环境有 jq_stream_push.py 时 initialize 自动开启；模拟/实盘或无文件时关闭
# 排障时可改 True（含 filter/rank debug，很慢）
STREAM_LOG_DEBUG = False
_CODE_RE = re.compile(r'(\d{6})(?:\.XSH[EG])?')


def _jq_log(level, text):
    """聚宽 log 统一出口。"""
    text = str(text).replace('\n', ' ').strip()
    if not text:
        return
    fn = getattr(log, level, None)
    if fn is None and level in ('warn', 'warning'):
        fn = log.warning
    if fn is None:
        fn = log.info
    fn(text)

# ==================== 日志（即时打印 + 收盘汇总）====================
def _daily_log_date(context):
    return context.current_dt.strftime('%Y-%m-%d')


def _daily_log_reset(context):
    day = _daily_log_date(context)
    if getattr(g, 'daily_log_date', None) == day:
        return
    g.daily_log_date = day
    g.daily_log_events = []
    g.daily_log_flushed = False


def _code_short(text):
    m = _CODE_RE.search(str(text))
    return m.group(1) if m else ''


def _daily_log_add(context, message):
    if context is None:
        return
    _daily_log_reset(context)
    text = str(message).replace('\n', ' ').strip()
    if text:
        g.daily_log_events.append(text)


def _daily_log_flush(context):
    _daily_log_reset(context)
    if getattr(g, 'daily_log_flushed', False):
        return
    day = _daily_log_date(context)
    events = list(getattr(g, 'daily_log_events', []))
    _jq_log('info', '[daily] %s 共%d条' % (day, len(events)))
    if not events:
        _jq_log('info', '  (无)')
    else:
        for i, e in enumerate(events, 1):
            _jq_log('info', '  %d. %s' % (i, e))
    g.daily_log_events = []
    g.daily_log_flushed = True


def _set_log_context(context):
    g._log_context = context


def _log_write(text, level='info', context=None, daily=False):
    text = str(text).replace('\n', ' ').strip()
    if not text:
        return
    fn = getattr(log, level, None)
    if fn is None and level in ('warn', 'warning'):
        fn = log.warning
    if fn is None:
        fn = log.info
    fn(text)
    if daily:
        ctx = context if context is not None else getattr(g, '_log_context', None)
        if ctx is not None:
            _daily_log_add(ctx, text)


def _slog(module, msg, level='info', context=None):
    """[模块] 正文 → 聚宽 log；info/warn 且带 context 时记入日终汇总。"""
    daily = level in ('info', 'warn', 'warning')
    _log_write('[%s] %s' % (module, msg), level=level, context=context, daily=daily)


def _ilog(msg, context=None, level='info'):
    """正文 → 聚宽 log；info/warn 且带 context 时记入日终汇总。"""
    daily = level in ('info', 'warn', 'warning')
    _log_write(msg, level=level, context=context, daily=daily)


def _fmt_pass(value_str, passed):
    return f"{value_str} {'✅' if passed else '❌'}"


def _is_sim_trade(context):
    try:
        t = str(getattr(getattr(context, 'run_params', None), 'type', '') or '')
        return t in ('sim_trade', 'live_trade', 'simulation')
    except Exception:
        return False


def _should_write_sim_sync(context):
    """回测末日写文件；模拟/实盘不写。"""
    return not _is_sim_trade(context)


def _jq_stream_push_available():
    try:
        import jq_stream_push  # noqa: F401
        return True
    except ImportError:
        return False


def _resolve_stream_setup(context):
    """回测 + jq_stream_push → 开 stream；其余关闭。"""
    if _is_sim_trade(context) or not _jq_stream_push_available():
        return None
    return {
        'enable_log': True,
        'enable_trade': True,
        'enable_daily': True,
        'stream_log_debug': bool(globals().get('STREAM_LOG_DEBUG', False)),
        'quiet': False,
    }


# 日终 g 导出/模拟恢复：跳过静态池、日志缓冲、stream 内部字段
_SIM_SYNC_G_SKIP = frozenset({
    'etf_pool', 'etf_pool_bak',
    '_backtest_sync_done', '_backtest_sync_from_g', '_sim_sync_align_snap', '_sim_sync_g_exported', '_log_context',
    'jq_stream_strategy', 'jq_run_id', 'jq_stream_log_min_level',
    '_jq_stream_ctx', '_jq_stream_daily_pos', '_jq_stream_daily_regime',
    'daily_log_date', 'daily_log_events', 'daily_log_flushed',
    'pending_buy_target',
})
_SIM_SYNC_G_PRIVATE_OK = frozenset({'_drawdown_warn_date'})
_SIM_SYNC_G_DATE_KEYS = frozenset({
    'last_switch_date', 'range_bound_start_date', 'stop_loss_triggered_date',
    'bear_market_start_date', 'bear_market_last_exit_date', '_drawdown_warn_date',
})


def _g_val_to_json(val):
    if val is None or isinstance(val, (bool, int, float, str)):
        return val
    if isinstance(val, datetime.date):
        return val.isoformat()
    if isinstance(val, datetime.datetime):
        return val.isoformat()
    if isinstance(val, dict):
        return {str(k): _g_val_to_json(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_g_val_to_json(x) for x in val]
    if isinstance(val, (np.floating, np.integer)):
        return float(val) if isinstance(val, np.floating) else int(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, pd.Timestamp):
        return val.strftime('%Y-%m-%d')
    return str(val)


def _json_to_g_val(key, raw):
    if key == 'last_sell_dates' and isinstance(raw, dict):
        out = {}
        for sec, d in raw.items():
            try:
                out[str(sec)] = datetime.datetime.strptime(str(d)[:10], '%Y-%m-%d').date()
            except Exception:
                pass
        return out
    if key == 'rankings_cache' and isinstance(raw, dict):
        cache = {'date': None, 'data': None}
        if raw.get('date'):
            try:
                cache['date'] = datetime.datetime.strptime(str(raw['date'])[:10], '%Y-%m-%d').date()
            except Exception:
                pass
        return cache
    if key in _SIM_SYNC_G_DATE_KEYS or (key.endswith('_date') and key != 'last_sell_dates'):
        if raw is None or raw == '':
            return None
        try:
            return datetime.datetime.strptime(str(raw)[:10], '%Y-%m-%d').date()
        except Exception:
            return None
    if isinstance(raw, list):
        return list(raw)
    return raw


def _iter_exportable_g_keys():
    keys = set()
    try:
        keys.update(k for k in g.__dict__.keys() if not k.startswith('__'))
    except Exception:
        pass
    return keys


def _export_g_state():
    out = {}
    for key in sorted(_iter_exportable_g_keys()):
        if key in _SIM_SYNC_G_SKIP:
            continue
        if key.startswith('_jq_stream'):
            continue
        if key.startswith('_') and key not in _SIM_SYNC_G_PRIVATE_OK:
            continue
        try:
            val = getattr(g, key)
        except Exception:
            continue
        if callable(val):
            continue
        if key == 'rankings_cache':
            rc = val if isinstance(val, dict) else {}
            val = {'date': rc.get('date'), 'data': None}
        try:
            jv = _g_val_to_json(val)
            json.dumps(jv, ensure_ascii=False)
            out[key] = jv
        except Exception:
            pass
    return out


def _sim_sync_fname():
    return str(globals().get('SIM_SYNC_FILE', 'sim_sync.json') or 'sim_sync.json')


def _dump_sim_sync_json(payload):
    """内嵌 JSON 导出（不依赖研究环境 sim_sync_format.py）。"""
    if not isinstance(payload, dict):
        return ''
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


def _apply_g_state(g_state):
    if not isinstance(g_state, dict):
        return 0
    n = 0
    for key, raw in g_state.items():
        if key in _SIM_SYNC_G_SKIP or key.startswith('_jq_stream'):
            continue
        if key.startswith('_') and key not in _SIM_SYNC_G_PRIVATE_OK:
            continue
        try:
            setattr(g, key, _json_to_g_val(key, raw))
            n += 1
        except Exception:
            pass
    return n


def _eod_target_from_portfolio(context):
    holdings = []
    for sec, pos in context.portfolio.positions.items():
        if pos.total_amount > 0:
            holdings.append((sec, get_name(sec)))
    if not holdings:
        return '', ''
    return holdings[0][0], holdings[0][1]


def _as_trade_date(v):
    """run_params 里 end_date 可为 date 或 datetime，统一成 date。"""
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    return datetime.datetime.strptime(str(v)[:10], '%Y-%m-%d').date()


def _backtest_end_date(context):
    return _as_trade_date(getattr(getattr(context, 'run_params', None), 'end_date', None))


def _last_trade_day_on_or_before(end_d):
    if end_d is None:
        return None
    try:
        days = get_trade_days(end_date=end_d, count=1)
        if days is not None and len(days):
            return _as_trade_date(days[-1])
    except Exception:
        pass
    return end_d


def _is_backtest_last_day(context):
    """回测区间内最后一个交易日（end_date 可为非交易日）。"""
    try:
        end_d = _backtest_end_date(context)
        if end_d is None:
            return False
        cur = _as_trade_date(context.current_dt)
        last_td = _last_trade_day_on_or_before(end_d)
        if last_td is not None and cur == last_td:
            return True
        if cur == end_d:
            return True
        nxt = _as_trade_date(getattr(context, 'next_trading_date', None))
        if nxt is not None and cur < end_d and nxt > end_d:
            return True
        if cur < end_d and nxt is not None and nxt >= end_d:
            return True
        return False
    except Exception:
        return False


def _should_emit_sim_sync_g(context):
    """回测最后一个交易日收盘导出一次；模拟/实盘跳过。"""
    if not _should_write_sim_sync(context):
        return False
    if getattr(g, '_sim_sync_g_exported', False):
        return False
    if not _is_backtest_last_day(context):
        return False
    return True


def _emit_sim_sync_g(context):
    """回测末日：write_file 写入 sim_sync.json。"""
    if not _should_emit_sim_sync_g(context):
        return
    try:
        target, target_name = _eod_target_from_portfolio(context)
        if target:
            g.hold_refs = [target]
        elif not getattr(g, 'hold_refs', None):
            g.hold_refs = []
        g_state = _export_g_state()
        payload = {
            'as_of_date': context.current_dt.strftime('%Y-%m-%d'),
            'target': target,
            'target_name': target_name,
            'target_weight': 0.98,
            'g': g_state,
            'current_filter': g_state.get('current_filter'),
            'risk_state': g_state.get('risk_state'),
            'bear_market_active': g_state.get('bear_market_active'),
            'source': 'sim_sync_g',
            'strategy': '七星175',
            'exported_at': context.current_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        try:
            from jq_stream_push import jq_raw
            jq_raw(context, 'sim_sync_g', payload)
        except Exception:
            pass
        body = _dump_sim_sync_json(payload)
        if body:
            write_file(_sim_sync_fname(), body)
        g._sim_sync_g_exported = True
    except Exception:
        pass


def after_trading_end(context):
    """聚宽每日收盘回调；回测末日写入 sim_sync.json。"""
    _emit_sim_sync_g(context)


def _apply_sim_g_from_snap(snap, tag='sim_sync'):
    """仅恢复 g（不含持仓）。"""
    g_state = snap.get('g')
    if isinstance(g_state, dict) and g_state:
        n = _apply_g_state(g_state)
        g._backtest_sync_from_g = True
        _jq_log('info', '[%s] 已恢复 g %d 个 as_of=%s' % (tag, n, snap.get('as_of_date', '')))
    else:
        filt = snap.get('current_filter')
        if filt:
            g.current_filter = str(filt)
            g.risk_state = str(snap.get('risk_state') or filt)
        if 'bear_market_active' in snap:
            g.bear_market_active = bool(snap['bear_market_active'])
        g.last_sell_dates = {}
        for sec, d in (snap.get('last_sell_dates') or {}).items():
            try:
                g.last_sell_dates[str(sec)] = datetime.datetime.strptime(str(d)[:10], '%Y-%m-%d').date()
            except Exception:
                pass
        g.rankings_cache = {'date': None, 'data': None}
    _apply_hold_refs_from_snap(snap)


def _apply_hold_refs_from_snap(snap):
    """低相关守卫参照：优先快照 target，否则沿用 g 内 hold_refs。"""
    target = str((snap or {}).get('target') or '').strip()
    if target:
        g.hold_refs = [target]
    elif not getattr(g, 'hold_refs', None):
        g.hold_refs = []


def _sync_hold_refs_after_order(security, context):
    """成交后刷新逻辑持仓（供低相关守卫用；与 portfolio 解耦读取）。"""
    sec = str(security)
    pos = context.portfolio.positions.get(sec)
    hold = list(getattr(g, 'hold_refs', None) or [])
    if pos and pos.total_amount > 0:
        if int(getattr(g, 'holdings_num', 1) or 1) <= 1:
            g.hold_refs = [sec]
        elif sec not in hold:
            hold.append(sec)
            g.hold_refs = hold
    else:
        g.hold_refs = [x for x in hold if x != sec]


def _portfolio_near_target(context, target, weight):
    if not target:
        return True
    pos = context.portfolio.positions.get(target)
    if not pos or pos.total_amount <= 0:
        return False
    total = float(context.portfolio.total_value)
    if total <= 0:
        return False
    return float(pos.value) >= total * float(weight) * 0.9


def _sim_sync_align_portfolio(context):
    """回测接续：09:09 按快照对齐持仓；未完成则次日重试。"""
    snap = getattr(g, '_sim_sync_align_snap', None)
    if not snap:
        return
    _set_log_context(context)
    target = str(snap.get('target') or '').strip() or None
    w = float(snap.get('target_weight') or 0.98)
    total = float(context.portfolio.total_value)
    for sec, pos in list(context.portfolio.positions.items()):
        if pos.total_amount > 0 and sec != target:
            smart_order_target_value(sec, 0, context)
    if target:
        smart_order_target_value(target, total * w, context)
    if not target or _portfolio_near_target(context, target, w):
        g._sim_sync_align_snap = None
        _jq_log('info', '[sim_sync] 持仓对齐 %s' % (target or '空仓'))
    else:
        _jq_log('info', '[sim_sync] 持仓对齐未完成(停牌等)，次日 09:09 重试')


def _apply_sim_snapshot(context, snap, tag='sim_sync'):
    """模拟/实盘只恢复 g；回测接续另在 09:09 对齐持仓。"""
    if not isinstance(snap, dict):
        return
    g._backtest_sync_done = True
    _apply_sim_g_from_snap(snap, tag=tag)
    if _is_sim_trade(context):
        _jq_log('info', '[%s] 模拟/实盘仅恢复 g，持仓以账户为准' % tag)
        return
    g._sim_sync_align_snap = snap
    _jq_log('info', '[%s] 回测接续：持仓对齐挂 09:09' % tag)


def _read_sim_sync_from_research():
    """从聚宽研究环境 read_file 读取快照（研究根目录 sim_sync.json）。"""
    fname = _sim_sync_fname()
    try:
        raw = read_file(fname)
    except Exception:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    text = str(raw).strip()
    snap = None
    if text.startswith('{'):
        try:
            snap = json.loads(text)
        except Exception:
            pass
    if snap is None:
        try:
            from sim_sync_format import parse_sim_sync
            snap = parse_sim_sync(text)
        except Exception:
            _jq_log('info', '[sim_sync] %s 解析失败' % fname)
            return None
    return snap if isinstance(snap, dict) else None


def _sync_sim_from_research(context):
    """initialize：模拟/实盘自动加载；回测仅当快照日早于运行首日（路径接续）。"""
    if getattr(g, '_backtest_sync_done', False):
        return
    snap = _read_sim_sync_from_research()
    if not snap:
        if _is_sim_trade(context):
            _jq_log('info', '[sim_sync] 研究环境无 %s，跳过' % _sim_sync_fname())
        return
    as_of = str(snap.get('as_of_date') or '')[:10]
    start_day = context.current_dt.strftime('%Y-%m-%d')
    if not _is_sim_trade(context) and as_of and as_of >= start_day:
        return
    _jq_log('info', '[sim_sync] 从研究环境加载 %s (as_of=%s)' % (_sim_sync_fname(), as_of))
    _apply_sim_snapshot(context, snap, tag='sim_sync')


# ======================== 初始化模块 ========================
def initialize(context):
    
    """
    初始化函数：设置交易参数、ETF池、核心参数、调度任务
    """
    # ---------- 交易设置 ----------
    set_option("avoid_future_data", True)  # 防止未来函数
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    set_benchmark("161226.XSHE")
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    # ---------- ETF池（原版 38 只固定池）----------
    g.etf_pool_bak = [
        "518880.XSHG",  # 黄金ETF
        "159985.XSHE",  # 豆粕ETF
        "501018.XSHG",  # 南方原油
        "161226.XSHE",  # 白银LOF
        "513100.XSHG",  # 纳指ETF
        "159915.XSHE",  # 创业板ETF
        "511220.XSHG",  # 城投债ETF
    ]
    g.etf_pool = [
        # 大宗商品ETF
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF（跟踪有色金属板块）
        "159985.XSHE",  # 豆粕ETF（跟踪豆粕期货价格）
        "501018.XSHG",  # 南方原油（投资原油相关资产）
        '161226.XSHE',  # 白银LOF
        "159981.XSHE",  # 能源化工ETF
        # 国际ETF
        "513100.XSHG",  # 纳指ETF
        "159509.XSHE",  # 纳指科技ETF
        "513290.XSHG",  # 纳指生物ETF
        "513500.XSHG",  # 标普500ETF
        "159529.XSHE",  # 标普消费
        "513400.XSHG",  # 道琼斯ETF
        "513520.XSHG",  # 日经225ETF
        "513030.XSHG",  # 德国30ETF
        "513080.XSHG",  # 法国ETF
        "513310.XSHG",  # 中韩半导体ETF
        "513730.XSHG",  # 东南亚ETF
        # 香港ETF
        "159792.XSHE",  # 港股互联ETF
        "513130.XSHG",  # 恒生科技
        "513050.XSHG",  # 中概互联网ETF
        "159920.XSHE",  # 恒生ETF
        "513690.XSHG",  # 港股红利
        # 指数ETF
        "510300.XSHG",  # 沪深300ETF
        "510500.XSHG",  # 中证500ETF
        "510050.XSHG",  # 上证50ETF
        "510210.XSHG",  # 上证ETF
        "159915.XSHE",  # 创业板ETF
        "588080.XSHG",  # 科创50
        "512100.XSHG",  # 中证1000ETF
        "563360.XSHG",  # A500-ETF
        "563300.XSHG",  # 中证2000ETF
        # 风格ETF
        "512890.XSHG",  # 红利低波ETF
        "159967.XSHE",  # 创业板成长ETF
        "512040.XSHG",  # 价值ETF
        "159201.XSHE",  # 自由现金流ETF
        # 债券ETF
        "511380.XSHG",  # 可转债ETF
        "511010.XSHG",  # 国债ETF
        "511220.XSHG",  # 城投债ETF
    ]

    # ---------- 核心参数 ----------
    g.lookback_days = 25  # 动量计算周期
    g.holdings_num = 2  # 候选数量
    g.defensive_etf = "511880.XSHG"  # 防御ETF（货币基金）
    g.min_money = 5000  # 最小交易金额

    # ---------- 盈利保护参数 ----------
    g.enable_profit_protection = True  # 盈利保护开关
    g.profit_protection_lookback = 1  # 盈利保护回看周期（天）
    g.profit_protection_threshold = 0.05  # 盈利保护回撤阈值（5%）
    g.profit_protection_check_times = ['11:00']  # 盈利保护检查时间点（可添加多个，如['09:45','11:00','13:30']）

    # ---------- 卖出冷却（任意卖出后 N 个交易日内禁止再买该标的）----------
    g.sell_cooldown_days = 2
    g.last_sell_dates = {}  # {标的代码: 最近卖出日期}

    # ---------- 短期风控 / R²（参考五福 apply_filters）----------
    g.enable_loss_filter = True   # 近3日单日跌幅过滤
    g.enable_r2_filter = True
    g.r2_threshold = 0.35

    # ---------- 低相关性守卫（避免刚卖标的的高相关替代品）----------
    g.enable_correlation_guard = True
    g.correlation_lookback = 20
    g.correlation_max = 0.88
    g.correlation_guard_benchmark = True

    # ---------- 组合回撤监控（参考五福 monitor_drawdown）----------
    g.max_portfolio_value = 0
    g.drawdown_threshold = 0.08

    g.loss = 0.97  # 近3日单日跌幅>3%剔除（五福 v52；2026H1 AB 优于 0.98）
    g.min_score_threshold = 0  # 最低得分
    g.max_score_threshold = 100.0  # 最高得分

    # ---------- 成交量过滤 ----------
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1  # 年化收益>100%时启用放量过滤

    # ---------- 短期动量过滤 ----------
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0

    # ---------- 溢价率过滤 ----------
    g.enable_premium_filter = True  # 是否启用溢价率过滤
    g.premium_threshold = 0.15  # 溢价率阈值（15%）

    # ---------- 动量质量因子（参考社区帖「动量33」v9/v10/v13）----------
    g.enable_momentum_quality = True
    g.mq_use_ma_alignment = True       # v13 均线排列（帖内最佳单因子）
    g.mq_use_breakout = False          # v9 与七星滤波叠加后易过拟合，默认关
    g.mq_use_relative_strength = False # v10 默认关，可单独打开做 AB 测
    g.mq_benchmark = '510300.XSHG'     # 相对强度基准（与 risk_benchmark 一致）
    g.mq_breakout_near_high = 0.95     # 接近新高阈值
    g.mq_rs_scale = 2.0                # 相对强度放大系数
    g.mq_rs_min_factor = 0.5         # 相对强度因子下限

    # ---------- 日内趋势择时（一次性买入版）----------
    g.enable_intraday_trend = True       # 日内趋势择时总开关
    g.trend_lookback_minutes = 30         # 趋势判断回看分钟K线数量
    g.trend_slope_threshold = 0.001       # 归一化斜率阈值（每分钟涨跌幅%，大于为上涨趋势）
    g.pending_buy_target = []             # 待尾盘强制买入的标的列表（每日重置）

    # ---------- 运行时变量 ----------
    g.rankings_cache = {'date': None, 'data': None}  # 排名缓存
    g.hold_refs = []  # 逻辑持仓（低相关守卫用，sim_sync 恢复，不读 portfolio）

    # ---------- 震荡期参数 ----------
    g.enable_range_bound_mode = True  # 震荡期模式开关
    g.current_filter = '正常期'  # 当前滤波器：'正常期'=拉普拉斯, '震荡期'=高斯
    g.risk_state = '正常期'  # 风险状态
    g.lookback_high_low_days = 20  # 近N个交易日高低点回看
    g.risk_benchmark = '510300.XSHG'  # 风险基准ETF
    # 滤波器参数（正常期拉普拉斯，震荡期高斯）
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.001
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002
    # 进入震荡期条件
    g.enable_bias_trigger = True  # 乖离率过大触发
    g.bias_threshold = 0.10  # 乖离率阈值（8%）
    g.ma_period = 20  # 均线周期
    g.enable_rsi_trigger = True  # RSI超买回落触发
    g.rsi_overbought = 75
    g.rsi_pullback = 60
    g.previous_rsi = None
    g.enable_stop_loss_trigger = True   # 盈利保护卖出后当日可触发震荡期检查（五福同款）
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    # 退出震荡期条件
    g.enable_low_point_rise_trigger = True
    g.low_point_rise_threshold = 0.03  # 从低点上涨4%退出
    g.enable_stable_signal_trigger = True
    g.drawdown_recovery = 0.03  # 回撤收窄阈值
    g.max_range_bound_days = 15  # 最大震荡期天数
    g.stable_days = 0
    # 震荡期控制
    g.filter_switch_cooldown = 2  # 切换冷却期（交易日）
    g.last_switch_date = None
    g.range_bound_start_date = None
    g.range_bound_days_count = 0
    g.previous_drawdown = None

    # ---------- 阴跌期（仅大盘在均线下方且深跌/负动量 → 511880，针对2021类行情）----------
    g.enable_bear_market_mode = True
    g.bear_market_active = False
    g.bear_drawdown_enter = 0.12          # 510300 近20日高点回撤 ≥12%（v2 放宽，少误触）
    g.bear_return_enter = -0.08           # 510300 近20日收益 ≤-8%
    g.bear_require_below_ma = True        # 必须收盘在 MA20 下方（阴跌，非过热）
    g.bear_exit_rise = 0.04               # 从近20日低点反弹 ≥4%（v2 略早退出）
    g.bear_exit_need_above_ma = True      # 退出需站上 MA20
    g.bear_market_min_days = 5            # 最少持防 5 日（v2 缩短，少错过反弹）force_buy_pending
    g.bear_market_max_days = 25
    g.bear_market_cooldown = 3
    g.bear_market_start_date = None
    g.bear_market_last_exit_date = None
    g.bear_market_days_count = 0

    # ---------- 震荡期短动量（仅 g.current_filter=='震荡期' 时生效，AB：15/10/5）----------
    g.enable_range_bound_short_momentum = True
    g.range_bound_lookback_days = 25         # 震荡期内动量窗口；变体文件改为 15/10/5
    g.enable_range_bound_cash = True         # 震荡期无合格 ETF → 空仓（不买 511880）

    # ---------- 交易调度 ----------
    run_daily(_sim_sync_align_portfolio, time='09:09')
    run_daily(check_positions, time='09:10')
    run_daily(check_bear_market, time='13:30')
    run_daily(check_range_bound, time='13:31')
    run_daily(etf_sell_trade, time='13:15')
    run_daily(etf_buy_trade, time='13:33')   # 第一次趋势判断+买入
    run_daily(second_trend_check, time='14:10') # 第二次趋势判断（新增）
    run_daily(force_buy_pending, time='14:55')  # 日内趋势择时：尾盘强制买入

    # 动态注册盈利保护检查时间点
    for check_time in g.profit_protection_check_times:
        run_daily(profit_protection_check, time=check_time)

    run_daily(reset_range_bound_daily, time='15:10')
    run_daily(reset_intraday_trend_daily, time='15:10')  # 重置日内趋势待买列表
    run_daily(_end_of_day_log, time='15:30')
    # 分钟回测末日 after_close/15:30 可能不触发，多挂几个时点 + after_trading_end
    run_daily(_emit_sim_sync_g, time='15:11')
    run_daily(_emit_sim_sync_g, time='15:00')
    run_daily(_emit_sim_sync_g, time='after_close')

    log_strategy_init_summary()
    stream_opts = _resolve_stream_setup(context)
    if stream_opts is not None:
        try:
            from jq_stream_push import setup
            setup(context, '七星175', **stream_opts)
        except Exception as e:
            _jq_log('info', 'jq_stream: setup FAIL %s' % e)

    _set_log_context(context)
    g._sim_sync_g_exported = False
    _sync_sim_from_research(context)
    if not getattr(g, '_backtest_sync_from_g', False):
        init_range_bound_status(context)


# ==================== 日内趋势择时核心函数 ====================
def check_intraday_trend(security, context):
    """
    判断ETF盘中短期趋势（复用五福5.2日内趋势逻辑）
    基于最近N分钟分钟线收盘价的线性回归斜率（归一化处理）
    返回True表示上涨趋势，False表示下跌/无趋势
    """
    try:
        minute_data = get_price(
            security,
            end_date=context.current_dt,
            count=g.trend_lookback_minutes,
            frequency='1m',
            fields=['close'],
            skip_paused=False,
            fq='pre'
        )
        if minute_data is None or minute_data.empty:
            _slog('趋势判断', f"{security} {get_name(security)} 无分钟数据，默认视为上涨趋势", level='debug')
            return True

        closes = minute_data['close'].values
        # 过滤掉价格为0的无效数据（停牌时段）
        closes = closes[closes > 0]
        if len(closes) < 5:
            _slog('趋势判断', f"{security} {get_name(security)} 有效分钟数据不足({len(closes)}根)，默认视为无上涨趋势", context=context)
            return False

        # 线性回归斜率判断趋势方向
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]

        # 斜率归一化：转为每分钟涨跌幅(%)，消除价格量纲影响，便于跨标的比较
        mean_price = closes.mean()
        slope_pct = slope / mean_price * 100 if mean_price > 0 else 0

        # 归一化斜率 > 阈值 才判定为上涨趋势
        is_uptrend = slope_pct > g.trend_slope_threshold
        trend_desc = "上涨" if is_uptrend else "下跌"
        _slog('趋势判断', f"{security} {get_name(security)} 最近{len(closes)}分钟归一化斜率={slope_pct:.6f}%/min (阈值{g.trend_slope_threshold})，判定为{trend_desc}趋势", context=context)
        return is_uptrend
    except Exception as e:
        _slog('趋势判断', f"{security} {get_name(security)} 异常: {e}，默认视为上涨趋势", level='warning', context=context)
        return True


def force_buy_pending(context):
    """
    14:55 强制买入待确认标的（一次性全额买入，不分批）
    """
    _set_log_context(context)
    if not g.pending_buy_target:
        return
    
    _slog('趋势择时', '⏰ 14:55 强制买入待确认标的，一次性全额买入', context=context)
    target_etfs = g.pending_buy_target
    
    # 检查是否有持仓需要先卖出（不在目标列表的持仓）
    current_etf_pos = [s for s in context.portfolio.positions if s in g.etf_pool or s == g.defensive_etf]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        _slog('趋势择时', '尚有持仓需要卖出，跳过强制买入', level='debug')
        return

    # 等权分配，一次性全额买入
    total_val = context.portfolio.total_value
    target_per_etf = total_val / len(target_etfs)

    for etf in target_etfs:
        current_val = 0
        if etf in context.portfolio.positions:
            pos = context.portfolio.positions[etf]
            if pos.total_amount > 0:
                current_val = pos.total_amount * pos.price
        # 5%容差调仓
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            if smart_order_target_value(etf, target_per_etf, context):
                _slog('趋势择时', f"📥 强制买入：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}", context=context)
    
    # 清空待买列表
    g.pending_buy_target = []

def second_trend_check(context):
    """14:10 第二次趋势检查：待买标的趋势转好则立即买入，否则保留到尾盘"""
    _set_log_context(context)
    if not g.enable_intraday_trend or not g.pending_buy_target:
        return
    
    _slog('趋势择时', '⏰ 14:10 第二次趋势检查', context=context)
    remaining = []
    total_val = context.portfolio.total_value
    target_per_etf = total_val / g.holdings_num  # 仓位与第一次买入一致
    
    for etf in g.pending_buy_target:
        if check_intraday_trend(etf, context):
            # 趋势转涨，立即全额买入
            current_val = 0
            if etf in context.portfolio.positions:
                pos = context.portfolio.positions[etf]
                if pos.total_amount > 0:
                    current_val = pos.total_amount * pos.price
            if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
                if smart_order_target_value(etf, target_per_etf, context):
                    _slog('趋势择时', f"📈 趋势转涨，14:10买入：{etf} {get_name(etf)}", context=context)
        else:
            # 仍下跌，保留到尾盘强制买入
            remaining.append(etf)
            _slog('趋势择时', f"📉 仍为下跌趋势，继续等待：{etf} {get_name(etf)}", context=context)
    
    g.pending_buy_target = remaining


def reset_intraday_trend_daily(context):
    """每日收盘重置日内趋势择时的待买变量"""
    g.pending_buy_target = []
    _slog('趋势择时', '日终重置待买列表', level='debug')


# ==================== 盈利保护独立检查函数 ====================
def profit_protection_check(context):
    """
    独立执行的盈利保护检查函数
    遍历所有持仓，若触发盈利保护则卖出
    """
    _set_log_context(context)
    if not g.enable_profit_protection:
        _slog('盈利保护', 'module=off reason=disabled', level='debug')
        return

    for sec in list(context.portfolio.positions.keys()):
        # 只处理ETF池中的标的和防御ETF
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if check_profit_protection(sec, context):
                if smart_order_target_value(sec, 0, context):
                    _slog('盈利保护', f"🛡️ 卖出 {sec} {get_name(sec)}")
                    if g.enable_stop_loss_trigger:
                        g.stop_loss_triggered_today = True
                        g.stop_loss_triggered_date = context.current_dt.date()
                        _slog('盈利保护', '记录止损信号，13:05 震荡期检查可用')


# ==================== 卖出冷却（轮动/盈利保护等任意卖出） ====================
def mark_sell_cooldown(security, context):
    """记录卖出日，用于冷却期内禁止再买。"""
    if not hasattr(g, 'last_sell_dates') or g.last_sell_dates is None:
        g.last_sell_dates = {}
    sell_day = context.current_dt.date()
    g.last_sell_dates[security] = sell_day
    _slog(
        '卖出冷却',
        f"⏳ {security} {get_name(security)} {g.sell_cooldown_days}个交易日内不可再买（卖出日 {sell_day}）",
    )


def trading_days_since_sell(security, context):
    """自最近卖出日至今日（含）经过的交易日数；0=卖出当日。"""
    sell_date = getattr(g, 'last_sell_dates', {}).get(security)
    if sell_date is None:
        return None
    today = context.current_dt.date()
    if today < sell_date:
        return None
    trade_days = get_trade_days(start_date=sell_date, end_date=today)
    return len(trade_days) - 1


def is_in_sell_cooldown(security, context):
    """
    是否处于卖出冷却期。
    规则：卖出当日不买回；卖出后再过 sell_cooldown_days 个交易日方可再买。
    例：cooldown=2，周一卖出 → 周二、周三仍禁买，周四可买。
    """
    days_since = trading_days_since_sell(security, context)
    if days_since is None:
        return False
    if days_since == 0:
        return True
    return days_since <= g.sell_cooldown_days


def _end_of_day_log(context):
    """收盘打印当日日志汇总；回测末日另写入 sim_sync.json。"""
    _set_log_context(context)
    _daily_log_flush(context)
    _emit_sim_sync_g(context)


def log_strategy_init_summary():
    prem = (
        'off'
        if not g.enable_premium_filter
        else '%.0f%%' % (g.premium_threshold * 100)
    )
    trend_status = 'on' if g.enable_intraday_trend else 'off'
    _jq_log(
        'info',
        '[init] pool=%d hold=%d loss=%.2f r2=%.2f prem=%s bear=%s range_lb=%d dd=%.0f%% trend=%s def=%s'
        % (
            len(g.etf_pool),
            g.holdings_num,
            g.loss,
            g.r2_threshold,
            prem,
            'on' if g.enable_bear_market_mode else 'off',
            g.range_bound_lookback_days,
            g.drawdown_threshold * 100,
            trend_status,
            _code_short(g.defensive_etf) or '511880',
        )
    )


def monitor_portfolio_drawdown(context):
    """组合净值回撤监控（参考五福）。"""
    try:
        current_value = context.portfolio.total_value
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value <= 0:
            return
        dd = (g.max_portfolio_value - current_value) / g.max_portfolio_value
        if dd < g.drawdown_threshold:
            return
        today = context.current_dt.date()
        if getattr(g, '_drawdown_warn_date', None) == today:
            return
        g._drawdown_warn_date = today
        pos_info = []
        for sec, pos in context.portfolio.positions.items():
            if pos.total_amount > 0:
                pos_info.append(f"{get_name(sec)}({sec})")
        _ilog(
            '%s 回撤%.1f%% 净值%d 持仓:%s'
            % (
                _daily_log_date(context),
                dd * 100,
                int(current_value),
                ','.join(pos_info) if pos_info else '空',
            ),
            context=context,
            level='warn',
        )
    except Exception as e:
        _slog('回撤预警', f'计算异常: {e}', level='warning')


def _daily_returns_series(security, context, lookback):
    hist = attribute_history(security, lookback + 1, '1d', ['close'], skip_paused=True)
    if hist is None or len(hist) < lookback + 1:
        return None
    closes = hist['close'].values.astype(float)
    if np.any(closes <= 0):
        return None
    return np.diff(closes) / closes[:-1]


def calc_return_correlation(sec_a, sec_b, context, lookback=None):
    lookback = lookback or g.correlation_lookback
    ra = _daily_returns_series(sec_a, context, lookback)
    rb = _daily_returns_series(sec_b, context, lookback)
    if ra is None or rb is None or len(ra) != len(rb) or len(ra) < 5:
        return None
    corr = float(np.corrcoef(ra, rb)[0, 1])
    if np.isnan(corr):
        return None
    return corr


def get_correlation_guard_refs(context):
    """低相关守卫参照：g.hold_refs + 卖出冷却中标的 + 可选基准（不读 portfolio）。"""
    refs = []
    for sec in getattr(g, 'hold_refs', None) or []:
        s = str(sec).strip()
        if s and (s in g.etf_pool or s == g.defensive_etf):
            refs.append(s)
    for sec in getattr(g, 'last_sell_dates', {}):
        if is_in_sell_cooldown(sec, context):
            refs.append(sec)
    if g.correlation_guard_benchmark and g.risk_benchmark:
        refs.append(g.risk_benchmark)
    return list(dict.fromkeys(refs))


def passes_correlation_guard(candidate, context, refs=None):
    if not g.enable_correlation_guard:
        return True, None
    refs = refs or get_correlation_guard_refs(context)
    worst = None
    for ref in refs:
        if ref == candidate:
            continue
        corr = calc_return_correlation(candidate, ref, context)
        if corr is None:
            continue
        if corr >= g.correlation_max and (worst is None or corr > worst[1]):
            worst = (ref, corr)
    if worst:
        return False, worst
    return True, None


def _format_rank_log_line(m, rank_no):
    r2_str = f"{m.get('r_squared', 0):.3f}"
    ann_str = f"{m.get('annualized_returns', 0) * 100:.1f}%"
    score_str = f"{m.get('score', 0):.4f}"
    short_str = f"{m.get('short_annualized', 0) * 100:.1f}%"
    min_ratio = m.get('min_day_ratio')
    loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, (float, int)) and not np.isnan(min_ratio) else 'N/A'
    qf = m.get('quality_factor', 1.0)
    q_hint = f" 质量×{qf:.2f}" if qf not in (None, 1.0) else ''
    return (
        f"#{rank_no} {m['etf']} {m['etf_name']}: "
        f"得分{_fmt_pass(score_str, True)} 年化{ann_str} R²{_fmt_pass(r2_str, m.get('passed_r2', True))} "
        f"短期动量{short_str} 三日比{loss_val} "
        f"滤波{_fmt_pass(m.get('filter_name', '-'), m.get('passed_filter', True))}{q_hint}"
    )


def log_ranking_pipeline(context, ranked):
    """压缩版排名摘要（每日缓冲，避免免费日志条数触顶）。"""
    lb = get_momentum_lookback_days(context)
    filt = '拉普拉斯·正常期' if g.current_filter == '正常期' else '高斯·震荡期'
    if not ranked:
        _slog('排名', f'入围0只 | 动量{lb}日 | {filt}', context=context)
        return
    top_parts = []
    for i, m in enumerate(ranked[:3]):
        top_parts.append(f"#{i + 1}{m['etf_name']}得分{m['score']:.3f}")
    _slog(
        '排名',
        f"入围{len(ranked)}只 | {lb}日{filt} | Top3: {'; '.join(top_parts)}",
        context=context,
    )


def select_target_etfs_with_guards(ranked, context):
    """按排名选标的，应用卖出冷却 + 低相关性守卫。"""
    targets = []
    refs = get_correlation_guard_refs(context)
    for m in ranked:
        if len(targets) >= g.holdings_num:
            break
        etf = m['etf']
        if m['score'] < g.min_score_threshold:
            continue
        if is_in_sell_cooldown(etf, context):
            days_since = trading_days_since_sell(etf, context)
            _slog(
                '买入',
                f"🚫 跳过 {etf} {m['etf_name']}：卖出冷却（已过{days_since}日，需满{g.sell_cooldown_days}日）",
            )
            continue
        ok, info = passes_correlation_guard(etf, context, refs)
        if not ok:
            ref, corr = info
            _slog(
                '低相关守卫',
                f"🚫 跳过 {etf} {m['etf_name']}：与 {ref} {get_name(ref)} "
                f"{g.correlation_lookback}日收益相关 {corr:.2f} ≥ {g.correlation_max:.2f}",
            )
            continue
        targets.append(etf)
        _slog('买入', f"🎯 目标{len(targets)}: {etf} {m['etf_name']} 得分{m['score']:.4f}")
        refs.append(etf)
    return targets


# ==================== 盈利保护检查函数（核心逻辑） ====================
def check_profit_protection(security, context, lookback=None, threshold=None):
    """
    检查是否触发盈利保护（从最近N日最高点回撤超过阈值）
    参数:
        security: ETF代码
        context: 上下文
        lookback: 回看天数，默认g.profit_protection_lookback
        threshold: 回撤阈值，默认g.profit_protection_threshold
    返回:
        bool: True表示应触发盈利保护（卖出/排除），False表示安全
    """
    # 若开关关闭，直接返回安全（独立检查函数已在外层判断，但保留此判断以防直接调用）
    if not g.enable_profit_protection:
        return False

    lookback = lookback or g.profit_protection_lookback
    threshold = threshold or g.profit_protection_threshold

    # 获取最近N日的最高价（不包括当天）
    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        _slog('盈利保护', f"{security} {get_name(security)} reason=hist_short days={lookback}", level='debug')
        return False
    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price

    if current_price <= max_high * (1 - threshold):
        _ilog(
            f"🔻 {security} {get_name(security)} 触发盈利保护：当前价{current_price:.3f}，最近{lookback}日最高{max_high:.3f}，回撤{(1 - current_price / max_high) * 100:.2f}% > {threshold * 100:.0f}%")
        return True
    else:
        return False


# ==================== 溢价率获取函数 ====================
def get_premium_rate(code, date, max_back_days=5):
    """
    获取指定日期的溢价率，若当天无净值则向前搜索最多max_back_days个交易日
    参数:
        code: 基金代码
        date: 日期，datetime.date 对象
        max_back_days: 最大回退天数
    返回:
        premium_rate: 溢价率（小数形式），None 表示获取失败
        price: 场内交易价格
        net_value: 基金净值
    """
    # 获取场内交易价格（给定日期）
    price_data = get_price(
        code,
        start_date=date,
        end_date=date,
        frequency='daily',
        fields=['close']
    )
    if price_data.empty:
        _slog('过滤', f"{code} reason=no_price date={date}", level='debug')
        return None, None, None
    price = price_data['close'].iloc[0]

    # 获取净值，先尝试指定日期，若失败则向前搜索交易日
    net_value = None
    used_date = date
    # 获取从date往前max_back_days个交易日的列表（扩大范围确保包含足够交易日）
    start_date = date - datetime.timedelta(days=max_back_days * 2)
    trade_days = get_trade_days(start_date=start_date, end_date=date)
    # 转换为 Python date 对象
    trade_days = [pd.to_datetime(d).date() for d in trade_days]
    # 倒序搜索，从date开始向前
    for dt in reversed(trade_days):
        if dt > date:  # 忽略大于date的日期
            continue
        # 尝试获取净值的两种方式
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            used_date = dt
            break
        # 备用方法
        try:
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == dt
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                used_date = dt
                break
        except:
            continue

    if net_value is None:
        _slog('过滤', f"{code} reason=no_nav date={date} back={max_back_days}d", level='debug')
        return None, None, None

    premium_rate = (price - net_value) / net_value
    if used_date != date:
        _slog('过滤', f"{code} reason=nav_fallback used={used_date} nav={net_value:.4f} for={date}", level='debug')
    return premium_rate, price, net_value


# ==================== 阴跌期机制（2021 类阴跌，非账户回撤触发）====================
def _bear_market_in_cooldown(context):
    if g.bear_market_last_exit_date is None:
        return False
    trade_days = get_trade_days(start_date=g.bear_market_last_exit_date, end_date=context.current_dt.date())
    return len(trade_days) - 1 < g.bear_market_cooldown


def _benchmark_20d_return(close_series):
    if len(close_series) < 21:
        return None
    return close_series[-1] / close_series[-21] - 1


def check_and_enter_bear_market(context):
    if _bear_market_in_cooldown(context):
        _ilog("【阴跌期】退出冷却中，暂不进入")
        return
    state = get_risk_benchmark_state(context)
    if state is None:
        _ilog("【阴跌期】基准数据不足，跳过")
        return
    current_price = state['current_price']
    ma = state['ma']
    recent_high = state['recent_high']
    close_series = state['close_series']
    if g.bear_require_below_ma and ma > 0 and current_price >= ma:
        _ilog(f"【阴跌期】基准在MA20上方({current_price:.3f}>={ma:.3f})，非阴跌，不进入")
        return
    bench_dd = (recent_high - current_price) / recent_high if recent_high > 0 else 0
    ret20 = _benchmark_20d_return(close_series)
    risk_signals = []
    if bench_dd >= g.bear_drawdown_enter:
        risk_signals.append(f"基准回撤{bench_dd:.2%}≥{g.bear_drawdown_enter:.0%}")
    if ret20 is not None and ret20 <= g.bear_return_enter:
        risk_signals.append(f"基准20日收益{ret20:.2%}≤{g.bear_return_enter:.0%}")
    if not risk_signals:
        _ilog("【阴跌期】回撤/收益未达阈值，保持轮动")
        return
    g.bear_market_active = True
    g.bear_market_start_date = context.current_dt.date()
    g.bear_market_days_count = 0
    below = f"价{current_price:.3f}<MA{ma:.3f}" if ma > 0 else "价<MA"
    _ilog(f"【进入阴跌期】{below}，强制防御: {'; '.join(risk_signals)}")


def check_and_exit_bear_market(context):
    if g.bear_market_start_date is not None:
        trade_days = get_trade_days(start_date=g.bear_market_start_date, end_date=context.current_dt.date())
        g.bear_market_days_count = len(trade_days) - 1
    if g.bear_market_days_count < g.bear_market_min_days:
        _ilog(f"【阴跌期】最少持有{g.bear_market_min_days}天，当前{g.bear_market_days_count}天")
        return
    if g.bear_market_days_count >= g.bear_market_max_days:
        _exit_bear_market(context, f"阴跌期满{g.bear_market_days_count}天")
        return
    state = get_risk_benchmark_state(context)
    if state is None:
        return
    current_price = state['current_price']
    ma = state['ma']
    recent_low = state['recent_low']
    rise = (current_price - recent_low) / recent_low if recent_low > 0 else 0
    above_ma = ma > 0 and current_price > ma
    rise_ok = rise >= g.bear_exit_rise
    ma_ok = (not g.bear_exit_need_above_ma) or above_ma
    if rise_ok and ma_ok:
        parts = [f"反弹{rise:.2%}≥{g.bear_exit_rise:.0%}"]
        if above_ma:
            parts.append("站上MA20")
        _exit_bear_market(context, '; '.join(parts))
    else:
        _ilog(f"【阴跌期】继续防御(反弹{rise:.2%}，MA上={above_ma})")


def _exit_bear_market(context, reason):
    g.bear_market_active = False
    g.bear_market_start_date = None
    g.bear_market_days_count = 0
    g.bear_market_last_exit_date = context.current_dt.date()
    g.rankings_cache = {'date': None, 'data': None}
    _ilog(f"【退出阴跌期】恢复轮动: {reason}")


def check_bear_market(context):
    if not g.enable_bear_market_mode:
        return
    _set_log_context(context)
    if g.bear_market_active:
        check_and_exit_bear_market(context)
    else:
        check_and_enter_bear_market(context)
    g.rankings_cache = {'date': None, 'data': None}


def is_bear_market_mode(context):
    return g.enable_bear_market_mode and g.bear_market_active


# ==================== 震荡期机制 ====================
def calculate_rsi(close, period=14):
    """计算RSI值"""
    try:
        if len(close) < period + 1:
            return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except:
        return None


def laplace_filter(price, s=0.05):
    """拉普拉斯滤波器（正常期使用）"""
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def gaussian_filter_last_two(price, sigma=1.2):
    """仅计算高斯滤波最后两个点（震荡期使用，效率优化）"""
    n = len(price)
    if n < 2:
        return 0, 0
    idx_1 = np.arange(n)
    weights_1 = np.exp(-((idx_1 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    weights_1 /= np.sum(weights_1)
    g1 = np.sum(price * weights_1)
    price_2 = price[:-1]
    idx_2 = np.arange(n - 1)
    weights_2 = np.exp(-((idx_2 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    weights_2 /= np.sum(weights_2)
    g2 = np.sum(price_2 * weights_2)
    return g1, g2


def get_risk_benchmark_state(context):
    """获取风险基准的日线+盘中融合状态，用于震荡期判断"""
    required_days = max(g.ma_period, g.lookback_high_low_days)
    lookback = required_days + 30
    end_date = getattr(context, 'previous_date', None)
    if end_date is None:
        return None
    df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,
                   frequency='daily', fields=['close', 'high', 'low'], panel=False)
    if df is None or len(df) < required_days:
        return None
    daily_close = df['close'].values.astype(float)
    daily_high = df['high'].values.astype(float)
    daily_low = df['low'].values.astype(float)
    current_price = float(daily_close[-1])
    intraday_high = current_price
    intraday_low = current_price
    data_source = '昨日日线'
    try:
        today = context.current_dt.date()
        minute_df = get_price(
            g.risk_benchmark, start_date=today, end_date=context.current_dt,
            frequency='1m', fields=['close', 'high', 'low'],
            panel=False, fill_paused=False
        )
        if minute_df is not None and not minute_df.empty:
            minute_close = minute_df['close'].dropna()
            minute_high = minute_df['high'].dropna()
            minute_low = minute_df['low'].dropna()
            if not minute_close.empty:
                current_price = float(minute_close.iloc[-1])
                intraday_high = float(minute_high.max()) if not minute_high.empty else current_price
                intraday_low = float(minute_low.min()) if not minute_low.empty else current_price
                data_source = '当日盘中'
    except Exception:
        pass
    if current_price <= 0:
        try:
            current_data = get_current_data()
            live_price = current_data[g.risk_benchmark].last_price
            if live_price is not None and live_price > 0:
                current_price = float(live_price)
                intraday_high = max(intraday_high, current_price)
                intraday_low = min(intraday_low, current_price)
                data_source = '实时快照'
        except Exception:
            current_price = float(daily_close[-1])
    close_series = np.append(daily_close, current_price)
    high_series = np.append(daily_high, max(intraday_high, current_price))
    low_series = np.append(daily_low, min(intraday_low, current_price))
    recent_high = np.max(high_series[-g.lookback_high_low_days:])
    recent_low = np.min(low_series[-g.lookback_high_low_days:])
    ma = np.mean(close_series[-g.ma_period:])
    current_rsi = calculate_rsi(close_series, period=14)
    previous_rsi = calculate_rsi(daily_close, period=14)
    return {
        'close_series': close_series,
        'high_series': high_series,
        'low_series': low_series,
        'current_price': current_price,
        'recent_high': recent_high,
        'recent_low': recent_low,
        'ma': ma,
        'current_rsi': current_rsi,
        'previous_rsi': previous_rsi,
        'data_source': data_source,
    }


def is_fresh_stop_loss_signal(context):
    """判断止损信号是否仍在有效期内"""
    signal_date = getattr(g, 'stop_loss_triggered_date', None)
    if signal_date is None:
        return False
    today = context.current_dt.date()
    previous_date = getattr(context, 'previous_date', None)
    if signal_date == today:
        return True
    if previous_date is not None and signal_date == previous_date:
        return True
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    return False


def init_range_bound_status(context):
    """首次运行时，根据历史数据判断当前是否处于震荡期"""
    if not g.enable_range_bound_mode:
        return
    _ilog("【首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None:
            log.warning("【首次运行】无法获取前一个交易日，保持正常期")
            return
        end_date = context.previous_date
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            log.warning("【首次运行】数据不足，保持正常期")
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        if len(close) >= g.lookback_high_low_days:
            recent_high = np.max(high[-g.lookback_high_low_days:])
            recent_low = np.min(low[-g.lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        ma = np.mean(close[-g.ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        current_rsi = calculate_rsi(close, period=14)
        should_enter = False
        signals = []
        if g.enable_bias_trigger and bias > g.bias_threshold:
            should_enter = True
            signals.append(f"乖离率{bias:.2%}>{g.bias_threshold:.0%}")
        if g.enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback:
                should_enter = True
                signals.append(f"RSI超买回落{prev_rsi:.1f}->{current_rsi:.1f}")
        if should_enter:
            g.current_filter = '震荡期'
            g.risk_state = '震荡期'
            g.range_bound_start_date = end_date
            g.range_bound_days_count = 0
            _ilog(f"【首次运行】初始化进入震荡期: {'; '.join(signals)}")
        else:
            g.current_filter = '正常期'
            g.risk_state = '正常期'
            if len(close) >= g.lookback_high_low_days:
                g.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            else:
                g.previous_drawdown = 0
            g.previous_rsi = current_rsi
            rsi_str = f"{current_rsi:.1f}" if current_rsi is not None else "N/A"
            _ilog(f"【首次运行】初始状态: 正常期, 乖离率: {bias:.2%}, RSI: {rsi_str}, 从低点涨幅: {rise_from_low:.2%}")
    except Exception as e:
        log.warning(f"【首次运行】初始化震荡期状态异常: {e}，保持正常期")


def check_and_exit_range_bound_mode(context):
    """检查是否需要退出震荡期"""
    if not g.enable_range_bound_mode:
        return
    if g.current_filter != '震荡期':
        return
    _ilog("【震荡期退出检查】开始检测退出条件...")
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is None:
            log.warning("【震荡期退出检查】数据不足，跳过")
            return
        close = benchmark_state['close_series']
        current_price = benchmark_state['current_price']
        recent_high = benchmark_state['recent_high']
        recent_low = benchmark_state['recent_low']
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        recovery_signals = []
        ma = benchmark_state['ma']
        current_rsi = benchmark_state['current_rsi']
        _ilog(
            f"【震荡期数据】当前价: {current_price:.3f}, 近{g.lookback_high_low_days}日高点: {recent_high:.3f}, 低点: {recent_low:.3f}")
        _ilog(f"【震荡期数据】回撤: {current_drawdown:.2%}, 从低点涨幅: {rise_from_low:.2%}")
        if g.enable_low_point_rise_trigger:
            if rise_from_low >= g.low_point_rise_threshold:
                recovery_signals.append(f"从低点上涨{rise_from_low:.2%}>={g.low_point_rise_threshold:.0%}")
                _ilog(f"【退出条件触发】从低点上涨: {rise_from_low:.2%}")
        if g.enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("价格站上均线")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                recovery_signals.append(f"回撤收窄({current_drawdown:.2%}<{g.previous_drawdown:.2%})")
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                recovery_signals.append(f"RSI回升({current_rsi:.1f})")
            drawdown_safe = current_drawdown < g.drawdown_recovery
            if drawdown_safe:
                g.stable_days += 1
                _ilog(f"【企稳计数】连续企稳天数: {g.stable_days}")
            else:
                g.stable_days = 0
        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi
        range_bound_days = 0
        if g.range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
            if range_bound_days >= g.max_range_bound_days:
                recovery_signals.append(f"震荡期满({range_bound_days}天)")
                _ilog(f"【退出条件触发】震荡期已满{range_bound_days}天")
        low_point_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_condition = False
        if g.enable_stable_signal_trigger:
            drawdown_safe = current_drawdown < g.drawdown_recovery
            stable_condition = drawdown_safe and len(recovery_signals) >= 2 and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days
        should_recover = low_point_condition or stable_condition or force_condition
        if should_recover:
            can_switch = True
            if g.last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
                days_since = len(trade_days) - 1
                if days_since < g.filter_switch_cooldown:
                    can_switch = False
                    _ilog(f"【震荡期退出】冷却期中，距上次切换{days_since}天")
            if can_switch:
                g.current_filter = '正常期'
                g.risk_state = '正常期'
                g.last_switch_date = context.current_dt.date()
                g.range_bound_start_date = None
                g.range_bound_days_count = 0
                g.stable_days = 0
                _ilog(f"【退出震荡期】切换回拉普拉斯滤波器: {'; '.join(recovery_signals)}")
        else:
            _ilog("【震荡期退出检查】未满足退出条件，保持震荡期(高斯滤波器)")
    except Exception as e:
        log.warning(f"【震荡期退出检查】判断出错: {e}")


def check_and_enter_range_bound_mode(context):
    """检查是否需要进入震荡期"""
    if not g.enable_range_bound_mode:
        return
    _ilog("【震荡期进入检查】开始检测...")
    stop_loss_signal_active = is_fresh_stop_loss_signal(context)
    can_switch = True
    if g.last_switch_date is not None:
        trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
        days_since = len(trade_days) - 1
        if days_since < g.filter_switch_cooldown:
            can_switch = False
            _ilog(f"【震荡期检查】冷却期中，距上次切换{days_since}天")
    if g.current_filter == '震荡期':
        _ilog("【震荡期检查】当前已在震荡期")
        return
    if not can_switch:
        return
    risk_signals = []
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is not None:
            close = benchmark_state['close_series']
            current_price = benchmark_state['current_price']
            # 条件1: 乖离率过大
            if g.enable_bias_trigger:
                ma = benchmark_state['ma']
                bias = (current_price - ma) / ma if ma > 0 else 0
                if bias > g.bias_threshold:
                    risk_signals.append(f"乖离率过大({bias:.2%}>{g.bias_threshold:.0%})")
                    _ilog(f"【条件触发】乖离率: {bias:.2%} (数据源:{benchmark_state['data_source']})")
            # 条件2: RSI超买回落
            if g.enable_rsi_trigger:
                current_rsi = benchmark_state['current_rsi']
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = benchmark_state['previous_rsi']
                    if prev_rsi is not None:
                        if prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                            risk_signals.append(f"RSI超买回落({prev_rsi:.1f}->{current_rsi:.1f})")
                            _ilog(f"【条件触发】RSI超买回落: {prev_rsi:.1f}->{current_rsi:.1f}")
    except Exception as e:
        log.warning(f"【震荡期检查】获取基准数据异常: {e}")
    # 条件3: 盈利保护触发止损
    if g.enable_stop_loss_trigger and stop_loss_signal_active:
        risk_signals.append("盈利保护触发止损")
        _ilog("【条件触发】盈利保护触发止损信号")
    if len(risk_signals) > 0:
        g.current_filter = '震荡期'
        g.risk_state = '震荡期'
        g.last_switch_date = context.current_dt.date()
        g.range_bound_start_date = context.current_dt.date()
        g.range_bound_days_count = 0
        g.stable_days = 0
        g.stop_loss_triggered_today = False
        g.stop_loss_triggered_date = None
        _ilog(f"【进入震荡期】切换到高斯滤波器: {'; '.join(risk_signals)}")
    else:
        _ilog("【震荡期检查】未满足进入条件，保持正常期(拉普拉斯滤波器)")


def check_range_bound(context):
    """震荡期检查入口（13:05定时调度，在卖出前执行）"""
    if not g.enable_range_bound_mode:
        return
    _set_log_context(context)
    if is_bear_market_mode(context):
        _ilog("【震荡期】阴跌期激活，跳过")
        return
    check_and_exit_range_bound_mode(context)
    check_and_enter_range_bound_mode(context)
    g.rankings_cache = {'date': None, 'data': None}


def reset_range_bound_daily(context):
    """收盘后重置震荡期相关的每日标志"""
    _set_log_context(context)
    if g.current_filter == '震荡期' and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
        g.range_bound_days_count = len(trade_days) - 1
        _ilog(f"震荡期已持续 {g.range_bound_days_count} 个交易日")
    _slog('regime', 'eod reset range_bound daily flags', level='debug')


# ==================== 动量质量因子（动量33 社区帖） ====================
def get_mq_benchmark_return(context):
    """缓存当日基准区间收益，供相对强度因子使用。"""
    today = context.current_dt.date()
    if getattr(g, '_mq_bench_ret_date', None) != today:
        g._mq_bench_ret_date = today
        g._mq_benchmark_return = 0.0
        try:
            bench_lb = get_momentum_lookback_days(context)
            bench_prices = attribute_history(
                g.mq_benchmark, bench_lb, '1d', ['close'], skip_paused=True
            )
            if len(bench_prices) >= max(5, int(bench_lb * 0.8)):
                g._mq_benchmark_return = float(
                    bench_prices['close'].iloc[-1] / bench_prices['close'].iloc[0] - 1
                )
        except Exception as e:
            _slog('rank', f"bench={g.mq_benchmark} reason=bench_ret_fail err={e}", level='debug')
    return getattr(g, '_mq_benchmark_return', 0.0)


def calc_ma_alignment_factor(closes):
    """v13：均线多头排列加分，空头排列减分。"""
    if len(closes) < 20:
        return 1.0
    ma5 = float(np.mean(closes[-5:]))
    ma10 = float(np.mean(closes[-10:]))
    ma20 = float(np.mean(closes[-20:]))
    if ma5 > ma10 > ma20:
        return 1.3
    if ma5 > ma10:
        return 1.1
    if ma10 > ma20:
        return 1.0
    return 0.7


def calc_breakout_factor(price_series):
    """v9：越接近区间新高，动量得分越高。"""
    recent_high = float(np.max(price_series))
    if recent_high <= 0:
        return 1.0
    breakout_ratio = float(price_series[-1] / recent_high)
    if breakout_ratio > g.mq_breakout_near_high:
        return breakout_ratio
    return breakout_ratio * 0.5


def calc_relative_strength_factor(context, price_series, momentum_lb=None):
    """v10：跑赢基准加分，跑输减分。"""
    momentum_lb = momentum_lb or get_momentum_lookback_days(context)
    if len(price_series) < momentum_lb + 1:
        return 1.0
    stock_return = float(price_series[-1] / price_series[-(momentum_lb + 1)] - 1)
    relative_strength = stock_return - get_mq_benchmark_return(context)
    rs_factor = 1 + relative_strength * g.mq_rs_scale
    return max(g.mq_rs_min_factor, rs_factor)


def apply_momentum_quality_factor(context, price_series, base_score, momentum_lb=None):
    """在基础动量得分上乘以质量因子。"""
    if not g.enable_momentum_quality or base_score <= 0:
        return base_score, 1.0, {}
    momentum_lb = momentum_lb or get_momentum_lookback_days(context)

    quality_factor = 1.0
    detail = {}
    if g.mq_use_ma_alignment:
        ma_factor = calc_ma_alignment_factor(price_series)
        quality_factor *= ma_factor
        detail['ma_factor'] = ma_factor
    if g.mq_use_breakout:
        breakout_factor = calc_breakout_factor(price_series)
        quality_factor *= breakout_factor
        detail['breakout_factor'] = breakout_factor
    if g.mq_use_relative_strength:
        rs_factor = calc_relative_strength_factor(context, price_series, momentum_lb)
        quality_factor *= rs_factor
        detail['rs_factor'] = rs_factor
    detail['quality_factor'] = quality_factor
    return base_score * quality_factor, quality_factor, detail


# ==================== 核心计算模块 ====================
def is_range_bound_filter_active(context):
    """是否处于策略自带的「震荡期」（13:05 乖离/RSI 等触发，切换高斯滤波）。"""
    return (
        g.enable_range_bound_mode
        and g.current_filter == '震荡期'
    )


def get_momentum_lookback_days(context):
    """正常期 25 日；仅进入震荡期后用 range_bound_lookback_days（15/10/5 AB）。"""
    if g.enable_range_bound_short_momentum and is_range_bound_filter_active(context):
        return g.range_bound_lookback_days
    return g.lookback_days


def should_fallback_defensive(context):
    """排名为空时是否买入货币基金。震荡期可空仓。"""
    if is_bear_market_mode(context):
        return True
    if g.enable_range_bound_cash and is_range_bound_filter_active(context):
        return False
    return True


def get_cached_rankings(context):
    """获取缓存的ETF排名，保证同一交易日内多次调用结果一致"""
    today = context.current_dt.date()
    lb = get_momentum_lookback_days(context)
    filt = 'range' if is_range_bound_filter_active(context) else 'trend'
    bear = 'bear' if is_bear_market_mode(context) else 'off'
    if g.rankings_cache['date'] != today:
        _slog(
            'rebalance',
            f"start pool={len(g.etf_pool)} lb={lb}d filter={filt} bear={bear} regime={g.current_filter}",
            level='debug',
            context=context,
        )
        _slog('排名', f"recalc momentum_lb={lb} regime={g.current_filter}", level='debug', context=context)
        ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': today, 'data': ranked}
    else:
        _slog('排名', 'cache_hit same_day', level='debug', context=context)
    return g.rankings_cache['data']


def get_ranked_etfs(context):
    """
    计算所有ETF的动量得分，应用所有过滤条件，返回按得分降序的列表
    """
    etf_metrics = []
    paused_count = 0
    for etf in g.etf_pool:
        if get_current_data()[etf].paused:
            paused_count += 1
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            if g.min_score_threshold < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
            else:
                _slog(
                    '过滤',
                    f"{etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超出区间",
                    level='debug',
                )

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    if paused_count:
        _slog('排名', f"停牌跳过 {paused_count} 只", level='debug')
    log_ranking_pipeline(context, etf_metrics)
    return etf_metrics


def calculate_momentum_metrics(context, etf):
    """
    计算单只ETF的动量指标，应用所有过滤条件
    返回字典：etf, etf_name, annualized_returns, r_squared, score, current_price, short_annualized
    """
    try:
        name = get_name(etf)
        momentum_lb = get_momentum_lookback_days(context)
        # 获取足够历史数据
        lookback = max(momentum_lb, g.short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < momentum_lb:
            _slog(
                '过滤',
                f"{etf} {name} reason=hist_short have={len(prices)} need={momentum_lb}",
                level='debug',
                context=context,
            )
            return None

        # 价格序列（含当天）
        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # ===== 1. 盈利保护检查（排除） =====
        if is_in_sell_cooldown(etf, context):
            days_since = trading_days_since_sell(etf, context)
            _slog(
                '过滤',
                f"🚫 {etf} {name} 卖出冷却（{days_since}/{g.sell_cooldown_days}交易日）",
            )
            return None
        if check_profit_protection(etf, context):
            _slog('过滤', f"🚫 {etf} {name} 触发盈利保护回撤，不参与排名")
            return None

        # ===== 2. 溢价率过滤（提前至排名阶段，获取失败则跳过过滤）=====
        if g.enable_premium_filter:
            # 获取前一个交易日（用于净值数据）
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, prem_price, prem_nav = get_premium_rate(etf, prev_date)
            if premium is not None:
                if premium > g.premium_threshold:
                    px_s = f'{prem_price:.4f}' if prem_price is not None else 'n/a'
                    nav_s = f'{prem_nav:.4f}' if prem_nav is not None else 'n/a'
                    _ilog(
                        f"🚫 {etf} {name} 溢价率{premium * 100:.2f}% > "
                        f"{g.premium_threshold * 100:.0f}%，从排名中排除 "
                        f"(ref={prev_date} price={px_s} nav={nav_s})",
                        context=context,
                    )
                    return None
            else:
                # 无法获取溢价率，跳过该过滤条件（不过滤）
                _ilog(
                    f"⚠️ {etf} {name} 无法获取溢价率(ref={prev_date})，跳过溢价过滤仍参与排名",
                    context=context,
                    level='warn',
                )

        # ===== 3. 成交量过滤（排除） =====
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns(price_series, momentum_lb)
                if annualized > g.volume_return_limit:
                    _slog(
                        '过滤',
                        f"{etf} {name} reason=volume_high_return vol={vol_ratio:.1f}x "
                        f"ann={annualized * 100:.1f}% thr={g.volume_return_limit * 100:.1f}%",
                        level='debug',
                        context=context,
                    )
                    return None

        # ===== 4. 短期动量过滤（排除） =====
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0

        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            _slog(
                '过滤',
                f"{etf} {name} reason=short_momentum val={short_annualized * 100:.1f}% "
                f"thr={g.short_momentum_threshold * 100:.1f}%",
                level='debug',
                context=context,
            )
            return None

        # ===== 5. 长期动量计算（得分） =====
        recent = price_series[-(momentum_lb + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        # R²（趋势稳定性）
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        base_score = annualized_returns * r_squared
        score, quality_factor, mq_detail = apply_momentum_quality_factor(
            context, price_series, base_score, momentum_lb
        )

        # ===== 6. R² 过滤（五福同款） =====
        passed_r2 = (not g.enable_r2_filter) or (r_squared >= g.r2_threshold)
        if not passed_r2:
            _slog('过滤', f"🚫 {etf} {name} R²={r_squared:.3f} < {g.r2_threshold:.2f}")
            return None

        # ===== 7. 近3日单日跌幅过滤（短期风控） =====
        min_day_ratio = 1.0
        passed_loss = True
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            min_day_ratio = float(min(day1, day2, day3))
            passed_loss = min_day_ratio >= g.loss
            if g.enable_loss_filter and not passed_loss:
                _slog(
                    '过滤',
                    f"🚫 {etf} {name} 短期风控：近3日最低日比{min_day_ratio:.4f} < {g.loss:.2f}",
                )
                return None

        # ===== 8. 动态滤波器过滤（震荡期机制） =====
        passed_filter = True
        filter_name = g.current_filter
        if g.enable_range_bound_mode and len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                laplace_slope = laplace_values[-1] - laplace_values[-2] if len(laplace_values) >= 2 else 0
                passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
                g1_val, g2_val = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
                gaussian_slope = g1_val - g2_val
                passed_gaussian = (current_price > g1_val and gaussian_slope > g.gaussian_min_slope)
                if g.current_filter == '正常期':
                    passed_filter = passed_laplace
                    filter_name = '拉普拉斯'
                else:
                    passed_filter = passed_gaussian
                    filter_name = '高斯'
                if not passed_filter:
                    _slog('过滤', f"🚫 {etf} {name} 未通过{filter_name}滤波({g.current_filter})")
                    return None
            except Exception as e:
                _slog('过滤', f"{etf} {name} 滤波器异常: {e}", level='debug')

        result = {
            'etf': etf,
            'etf_name': name,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'base_score': base_score,
            'current_price': current_price,
            'short_annualized': short_annualized,
            'momentum_lookback': momentum_lb,
            'passed_r2': passed_r2,
            'passed_loss': passed_loss,
            'min_day_ratio': min_day_ratio,
            'passed_filter': passed_filter,
            'filter_name': filter_name,
        }
        if mq_detail:
            result.update(mq_detail)
        return result

    except Exception as e:
        log.warning(f"计算{etf} {get_name(etf)}时出错: {e}")
        return None


def get_annualized_returns(price_series, lookback_days):
    """计算加权年化收益率"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def get_volume_ratio(context, security, lookback=None, threshold=None):
    """计算当日成交量与过去N日均量的比值，若超过阈值则返回比值，否则None"""
    lookback = lookback or g.volume_lookback
    threshold = threshold or g.volume_threshold
    try:
        name = get_name(security)
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()

        # 获取当日分钟成交量累计
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        if ratio > threshold:
            _slog(
                '过滤',
                f"{security} {name} reason=volume_spike ratio={ratio:.2f} thr={threshold}",
                level='debug',
                context=context,
            )
            return ratio
        return None
    except Exception as e:
        log.warning(f"成交量计算失败 {security}: {e}")
        return None


# ==================== 卖出模块 ====================
def check_positions(context):
    """每日开盘检查持仓状态 + 组合回撤（参考五福晨间流水线）。"""
    _daily_log_reset(context)
    _set_log_context(context)
    has_pos = any(
        context.portfolio.positions[sec].total_amount > 0
        for sec in context.portfolio.positions
    )
    monitor_portfolio_drawdown(context)


def etf_sell_trade(context):
    """卖出不符合条件的持仓（排名变化、溢价率过高）"""
    _set_log_context(context)
    if is_bear_market_mode(context):
        target_set = {g.defensive_etf} if check_defensive_etf_available(context) else set()
        if target_set:
            _ilog(f"🛡️ 【阴跌期】目标仅 {g.defensive_etf}")
        for sec in list(context.portfolio.positions.keys()):
            if sec not in g.etf_pool and sec != g.defensive_etf:
                continue
            if sec not in target_set:
                pos = context.portfolio.positions[sec]
                if pos.total_amount > 0 and smart_order_target_value(sec, 0, context):
                    _ilog(f"📤 【阴跌期】卖出 {sec} {get_name(sec)}")
        return

    ranked = get_cached_rankings(context)
    target_etfs = []
    for m in ranked[:g.holdings_num]:
        if m['score'] >= g.min_score_threshold:
            target_etfs.append(m['etf'])
    if not target_etfs and should_fallback_defensive(context):
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
    elif not target_etfs and is_range_bound_filter_active(context):
        _ilog("💤 【震荡期】无合格标的，目标空仓")
    target_set = set(target_etfs)
    # 卖出不在目标列表的持仓
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        if sec not in target_set:
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                if smart_order_target_value(sec, 0, context):
                    _ilog(f"📤 卖出不在目标的持仓：{sec} {get_name(sec)}")


# ==================== 买入模块（含日内趋势择时）====================
def etf_buy_trade(context):
    """
    买入符合条件的ETF，等权分配，按排名顺序逐个尝试直到凑够持仓数量
    新增：日内趋势择时
    - 上涨趋势 → 13:08 一次性全额买入
    - 下跌趋势 → 推迟到 14:55 一次性强制买入
    - 不分批建仓
    """
    _set_log_context(context)
    
    # 阴跌期直接买防御，不做趋势判断
    if is_bear_market_mode(context):
        if not check_defensive_etf_available(context):
            _ilog("🛡️ 【阴跌期】防御ETF不可用")
            return
        target_etfs = [g.defensive_etf]
        current_etf_pos = [s for s in context.portfolio.positions if s in g.etf_pool or s == g.defensive_etf]
        if [s for s in current_etf_pos if s not in target_etfs]:
            _ilog("【阴跌期】待卖清风险仓后再买防御")
            return
        total_val = context.portfolio.total_value
        etf = g.defensive_etf
        current_val = 0
        if etf in context.portfolio.positions:
            pos = context.portfolio.positions[etf]
            if pos.total_amount > 0:
                current_val = pos.total_amount * pos.price
        if abs(current_val - total_val) > total_val * 0.05 or current_val == 0:
            if smart_order_target_value(etf, total_val, context):
                _ilog(f"📥 【阴跌期】防御仓 {etf} 目标{total_val:.0f}")
        return

    ranked = get_cached_rankings(context)
    target_etfs = select_target_etfs_with_guards(ranked, context)

    if not target_etfs:
        if should_fallback_defensive(context) and check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            _ilog(f"🛡️ 进入防御模式，选择防御ETF：{g.defensive_etf} {get_name(g.defensive_etf)}")
        elif is_range_bound_filter_active(context) and g.enable_range_bound_cash:
            _ilog("💤 【震荡期】无合格标的，保持空仓")
            return
        else:
            _ilog("💤 无目标ETF且防御不可用，保持空仓")
            return

    # 检查是否有持仓需要先卖出（不在目标列表的持仓）
    current_etf_pos = [s for s in context.portfolio.positions if s in g.etf_pool or s == g.defensive_etf]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        to_sell_names = [get_name(s) for s in to_sell]
        _ilog(f"尚有持仓需要卖出：{list(zip(to_sell, to_sell_names))}，等待卖出完成再买入")
        return

    # ========== 日内趋势择时判断 ==========
    if g.enable_intraday_trend:
        # 只对风险ETF做趋势判断，货币基金直接买
        risk_targets = [t for t in target_etfs if t != g.defensive_etf]
        cash_targets = [t for t in target_etfs if t == g.defensive_etf]
        
        # 货币基金直接买入
        if cash_targets:
            total_val = context.portfolio.total_value
            target_per_etf = total_val / len(target_etfs)
            for etf in cash_targets:
                current_val = 0
                if etf in context.portfolio.positions:
                    pos = context.portfolio.positions[etf]
                    if pos.total_amount > 0:
                        current_val = pos.total_amount * pos.price
                if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
                    if smart_order_target_value(etf, target_per_etf, context):
                        _ilog(f"📦 买入防御：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")
        
        # 风险ETF逐个做趋势判断
        buy_now = []
        buy_later = []
        for etf in risk_targets:
            if check_intraday_trend(etf, context):
                buy_now.append(etf)
            else:
                buy_later.append(etf)
        
        # 上涨趋势的立即一次性全额买入
        if buy_now:
            total_val = context.portfolio.total_value
            target_per_etf = total_val / len(target_etfs)
            for etf in buy_now:
                current_val = 0
                if etf in context.portfolio.positions:
                    pos = context.portfolio.positions[etf]
                    if pos.total_amount > 0:
                        current_val = pos.total_amount * pos.price
                if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
                    if smart_order_target_value(etf, target_per_etf, context):
                        _ilog(f"📥 趋势上涨，立即买入：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")
        
        # 下跌趋势的存入待买列表，14:55 强制买入
        if buy_later:
            g.pending_buy_target = buy_later
            names = [get_name(e) for e in buy_later]
            _ilog(f"⏳ 趋势下跌，推迟买入：{list(zip(buy_later, names))}，等待14:55强制买入")
        return

    # 关闭趋势择时则按原逻辑直接买入
    total_val = context.portfolio.total_value
    target_per_etf = total_val / len(target_etfs)

    for etf in target_etfs:
        current_val = 0
        if etf in context.portfolio.positions:
            pos = context.portfolio.positions[etf]
            if pos.total_amount > 0:
                current_val = pos.total_amount * pos.price
        # 5%容差调仓
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            if smart_order_target_value(etf, target_per_etf, context):
                action = "买入" if current_val < target_per_etf else "调仓"
                _ilog(f"📦 {action}：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")


# ==================== 辅助函数 ====================
def get_name(security):
    """获取证券名称，带异常处理"""
    try:
        return get_current_data()[security].name
    except:
        return "未知"


def check_defensive_etf_available(context):
    """检查防御ETF是否可交易（未停牌、未涨跌停）"""
    data = get_current_data()
    etf = g.defensive_etf
    if data[etf].paused:
        _slog('defense', f"{etf} {get_name(etf)} reason=paused", level='debug')
        return False
    if data[etf].last_price >= data[etf].high_limit:
        _slog('defense', f"{etf} {get_name(etf)} reason=limit_up", level='debug')
        return False
    if data[etf].last_price <= data[etf].low_limit:
        _slog('defense', f"{etf} {get_name(etf)} reason=limit_down", level='debug')
        return False
    return True


def smart_order_target_value(security, target_value, context):
    """
    智能下单：根据目标市值调整持仓，处理停牌、涨跌停、最小交易金额、T+1
    """
    data = get_current_data()
    name = get_name(security)

    if data[security].paused:
        _ilog(f"{security} {name} 停牌，跳过")
        return False

    price = data[security].last_price
    if price == 0:
        _ilog(f"{security} {name} 当前价格0，跳过")
        return False

    target_amount = int(target_value / price)
    # 按100股整数倍调整
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount

    # 根据交易方向检查涨跌停
    if diff > 0:  # 买入
        if is_in_sell_cooldown(security, context):
            _ilog(f"{security} {name} 卖出冷却期内，跳过买入")
            return False
        if data[security].last_price >= data[security].high_limit:
            _ilog(f"{security} {name} 涨停，跳过买入")
            return False
    elif diff < 0:  # 卖出
        if data[security].last_price <= data[security].low_limit:
            _ilog(f"{security} {name} 跌停，跳过卖出")
            return False

    # 最小交易金额检查
    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        _ilog(f"{security} {name} 交易金额{trade_val:.2f} < {g.min_money}，跳过")
        return False

    # T+1处理
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            _ilog(f"{security} {name} 当天买入不可卖出")
            return False
        diff = -min(abs(diff), closeable)

    if diff != 0:
        order_result = order(security, diff)
        if order_result:
            _ilog(f"{'📥 买入' if diff > 0 else '📤 卖出'} {security} {name} 数量{abs(diff)} 价格{price:.3f}")
            if diff < 0:
                mark_sell_cooldown(security, context)
            _sync_hold_refs_after_order(security, context)
            return True
        else:
            log.warning(f"下单失败: {security} {name} 数量{diff}")
            return False
    return False