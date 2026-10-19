# Clone from JoinQuant
# postId: 9473ea7ad9691f7f2e030ac6add13c98
# backtestId: 91958fed384cc2d7549b24f09002f147
# title: 暴跌抄底融合五福

# 融合策略：动态池ETF抄底（S1，高优先级） + 五福v7轮动（S2，低优先级）
# 版本：1.2.0

from jqdata import *
import numpy as np
import math
import pandas as pd
import json
import re
import datetime as _dt
from datetime import datetime, date, timedelta

__version__ = "1.2.0"

# ==================== S1 模块级参数（抄底策略） ====================
EXCLUDE_MONEY = True       # 剔除货币类ETF
EXCLUDE_BOND = True        # 剔除债券类ETF
EXCLUDE_DIVIDEND = False   # 剔除股息红利类
EXCLUDE_CROSS = False      # 剔除跨境类
EXCLUDE_COMMODITY = False  # 剔除商品类
MIN_LIST_DAYS = 180        # 上市不足180天剔除
AVG_MONEY_DAYS = 20        # 日均成交额回看天数
EXCLUDE_MINI = True        # 剔除迷你基金
MINI_SCALE = 2.0           # 迷你基金阈值（亿元）
EXCLUDE_LIQUIDITY = True   # 剔除低流动性
MIN_MONEY = 1000           # 日均成交额阈值（万元）
SHOW_FULL_POOL = False     # 是否打印完整池子

MAX_HOLD = 1               # 最大持仓数
BIAS_SORT_DAYS = 50        # 排序用乖离率周期
BIAS_BUY_DAYS = 20         # 买入条件乖离率周期
BUY_BIAS_TH = -16          # 买入阈值：20日乖离率小于该值
TRAILING_STOP_PCT = 0.08   # 移动止盈回撤阈值
HOLD_MAX_DAYS = 21       # 持仓时间上限（None为不限制）
RUN_TIME = "09:35"         # S1每日判断时间
POOL_UPDATE_MONTHLY = True # 是否周期刷新池
POOL_REFRESH_MONTHS = 3    # 刷新间隔（月）
TREND_FILTER_MODE = 0      # 企稳过滤模式：0=不要求
TREND_LOOKBACK = 5         # 企稳回看天数
OVERSOLD_LOOKBACK = 5      # 先超跌回看天数
GAP_FILTER_TH = 0.03       # 高开过滤阈值

# ==================== 容器框架 ====================
SID_S1 = 1                  # 抄底策略ID
SID_S2 = 2                  # 轮动策略ID
MIN_OPEN_GRANT = 5000       # 单笔买入最小可批额度（元）

class CapitalAllocator:
    def __init__(self, strategies, used_of, sell_some):
        self.strategies = strategies
        self.used_of = used_of
        self.sell_some = sell_some

    def idle_pool(self, total_value):
        used_all = sum(self.used_of(s) for s in self.strategies)
        return max(0.0, total_value - used_all)

    def usable(self, sid, total_value):
        base = total_value * self.strategies[sid]["base_ratio"]
        others_idle = 0.0
        for o, acc in self.strategies.items():
            if o == sid:
                continue
            others_idle += max(0.0, total_value * acc["base_ratio"] - self.used_of(o))
        return base + others_idle

    def ensure_nominal(self, sid, total_value):
        acc = self.strategies[sid]
        base_value = total_value * acc["base_ratio"]
        shortage = max(0.0, base_value - self.idle_pool(total_value) - self.used_of(sid))
        if shortage <= 1e-9:
            return 0.0
        lower = sorted(
            (s for s in self.strategies if self.strategies[s]["priority"] < acc["priority"]),
            key=lambda s: self.strategies[s]["priority"],
        )
        reclaimed = 0.0
        for other in lower:
            if shortage <= 1e-9:
                break
            over = max(0.0, self.used_of(other) - total_value * self.strategies[other]["base_ratio"])
            if over <= 1e-9:
                continue
            got = self.sell_some(other, min(over, shortage))
            reclaimed += got
            shortage -= got
        return reclaimed

    def __getstate__(self):
        state = self.__dict__.copy()
        state["used_of"] = None
        state["sell_some"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.used_of = _alloc_used_of
        self.sell_some = _alloc_sell_some

_CTX = {}
def context_holder():
    return _CTX.get("ctx")
def set_context(context):
    _CTX["ctx"] = context

def _alloc_used_of(sid):
    return _used_of(context_holder(), sid)
def _alloc_sell_some(sid, amt):
    return _sell_some(context_holder(), sid, amt)

def allocator_init(context):
    g.accounts = {}
    g.stock_owner = {}
    g.allocator = None

def register_strategy(sid, base_ratio, priority=1, enabled=True):
    g.accounts[sid] = {
        "base_ratio": base_ratio,
        "priority": priority,
        "enabled": enabled,
        "holdings": [],
    }
    g.allocator = CapitalAllocator(
        strategies=g.accounts,
        used_of=_alloc_used_of,
        sell_some=_alloc_sell_some,
    )

def ensure_container(context):
    if hasattr(g, 'allocator') and g.allocator is not None and hasattr(g, 'accounts'):
        return
    try:
        allocator_init(context)
        register_strategy(SID_S1, 0.5, priority=2)
        register_strategy(SID_S2, 0.5, priority=1)
        if context is not None:
            sid = SID_S1 if getattr(g, 'mode', 'rot') == 'bottom' else SID_S2
            for sec, pos in context.portfolio.positions.items():
                if getattr(pos, 'closeable_amount', 0) > 0:
                    if sec not in g.accounts[sid]['holdings']:
                        g.accounts[sid]['holdings'].append(sec)
                    g.stock_owner[sec] = sid
        log.info("【容器自愈】g.allocator 缺失已重建")
    except Exception as e:
        log.error("【容器自愈失败】%s", e)

def _used_of(context, sid):
    acc = g.accounts[sid]
    total = 0.0
    for s in list(acc["holdings"]):
        pos = context.portfolio.positions.get(s)
        if pos:
            total += pos.value
    return total

def _sell_some(context, sid, amount):
    acc = g.accounts[sid]
    released = 0.0
    for s in list(acc["holdings"]):
        if amount - released <= 1e-9:
            break
        pos = context.portfolio.positions.get(s)
        if not pos or pos.closeable_amount <= 0:
            continue
        if pos.value <= (amount - released):
            close_position(s)
            released += pos.value
        else:
            target = pos.value - (amount - released)
            order_target_value(s, target)
            released += amount - released
    return released

def open_position(context, security, value, sid):
    ensure_container(context)
    total = context.portfolio.total_value
    acc = g.accounts[sid]
    if not acc["enabled"]:
        return None
    g.allocator.ensure_nominal(sid, total)
    grant = min(value, g.allocator.usable(sid, total))
    if grant < MIN_OPEN_GRANT:
        log.info("【容器·买入放弃】%s 可批额度 %.2f < 最小 %.0f", security, grant, MIN_OPEN_GRANT)
        return None
    order = my_order_target_value(security, grant)
    if order:
        filled = getattr(order, 'filled', 0)
        if filled > 0:
            if security not in acc["holdings"]:
                acc["holdings"].append(security)
            g.stock_owner[security] = sid
        else:
            log.info("【容器·买入未成交】%s 订单未成交，不登记归属", security)
    return order

def close_position(security):
    ensure_container(context_holder())
    sid = g.stock_owner.get(security)
    order = my_order_target_value(security, 0)
    filled = getattr(order, 'filled', 0) if order else 0
    if order and sid is not None and filled > 0:
        acc = g.accounts[sid]
        if security in acc["holdings"]:
            acc["holdings"].remove(security)
        del g.stock_owner[security]
    return order

def my_order_target_value(security, value):
    return order_target_value(security, value)
# ==================== S1 ETF池构建辅助函数（完整版，来自第一个策略） ====================
def _get_display_width(text):
    width = 0
    for c in str(text):
        width += 2 if ord(c) > 127 else 1
    return width

def _format_table(df):
    cols = df.columns.tolist()
    col_widths = {}
    for col in cols:
        max_w = _get_display_width(col)
        for val in df[col]:
            max_w = max(max_w, _get_display_width(val))
        col_widths[col] = max_w + 2
    numeric_cols = [c for c in cols if any(k in c for k in ['乖离率', '排名', '%', '规模', '成交额'])]
    header_cells, sep_cells = [], []
    for col in cols:
        w = col_widths[col]
        cell = str(col)
        pad = w - _get_display_width(cell)
        header_cells.append(cell + " " * pad)
        sep_cells.append("-" * w)
    header_line = "| " + " | ".join(header_cells) + " |"
    sep_line = "| " + " | ".join(sep_cells) + " |"
    data_lines = []
    for _, row in df.iterrows():
        row_cells = []
        for col in cols:
            w = col_widths[col]
            val = row[col]
            if col in numeric_cols:
                try:
                    cell = f"{float(val):.2f}"
                except:
                    cell = str(val)
            else:
                cell = str(val)
            pad = w - _get_display_width(cell)
            row_cells.append((" " * pad + cell) if col in numeric_cols else (cell + " " * pad))
        data_lines.append("| " + " | ".join(row_cells) + " |")
    return "\n".join([header_line, sep_line] + data_lines)

# 步骤计数器
_step_counter = [0]

def yy_step(msg):
    _step_counter[0] += 1
    #log.info(f"\n\n【{_step_counter[0]}】{msg}")

def yy_sub(msg):
    log.info(f"  {msg}")

# 关键词列表
MONEY_KEYWORDS = ['货币', '现金', '快线', '快钱', '理财金', '保证金', '财富宝', '日利', '添益']
BOND_KEYWORDS = ['国债', '信用债', '城投债', '短融', '可转债', '转债', '政金债', '国开债', '金融债', '公司债', '地方债']
STAR_BROAD_KEYWORDS = ['科创5', '科创1', '科创2', '科创综', '科创价格', '科创创业50', '双创50', '双创']
SMART_BETA_KEYWORDS = ['红利', '高股息', '价值', '成长', '低波', '质量']
REAL_INDUSTRY_KEYWORDS = [
    '银行', '证券', '保险', '券商', '地产', '房地产', '医药', '医疗', '消费', '白酒', '食品', '酒',
    '科技', '芯片', '半导体', '集成电路', '电子', '计算机', '软件', '信创', '通信', '传媒', 'tmt',
    '5g', '人工智能', 'ai', '云计算', '大数据', '物联网', '卫星', '电网', '金融',
    '新能源', '新能车', '电车', '光伏', '锂电', '电池', '汽车', '军工', '国防', '有色', '稀土', '稀有',
    '科创', '创新药', '中药', '疫苗', '信息安全', '数字经济', '影视', '新材料',
    '煤炭', '钢铁', '石油', '油气', '化工', '农业', '畜牧', '养殖', '粮食', '基建', '建筑', '能源', '资源', '船舶',
    '建材', '家电', '纺织', '旅游', '酒店', '游戏', '动漫', '机器人',
    '高端制造', '工业', '机械', '电力', '公用', '水务', '环保', '物流', '交运', '港口',
    '航运', '航空', '铁路', '公路', '教育', '养老', '健康',
]
CROSS_BORDER_KEYWORDS = [
    '纳斯达克', '纳指', '标普', '道琼斯', '恒指', '恒生', '港股', '中概',
    '德国', '日本', '东证', '日经', '越南', '印度', '海外', '全球',
    '美国', '亚太', '欧洲', '法国', '英国', '沙特', '巴西', '东南亚', '新兴亚洲',
    '香港', 'h股',
]
CROSS_BORDER_EXCLUDE = ['中国a', '中国a股']

ASSET_CLASS_KEYWORDS = {
    '股票-宽基': ['300', '500', '1000', '2000', '800', '50', '100', '180', '380', '创业板', '科创5', '科创1',
                '科创2', '科创综', '中证a', 'a50', '沪深', '上证', '深证', '深成', '全指', '综指', '龙头',
                'msci中国a', '超大盘', '民企', '专精特新', '战略新兴', '成渝', '长江'],
    '债券': ['债', '城投', '短融', '国债', '转债', '信用', '国开', '金融债', '企业债', '政金'],
    '商品': ['黄金', '金etf', '金基金', '上海金', '金9999', '中银黄金', '白银', '豆粕', '能源化工',
             '天然气', '商品', '原油', '有色期'],
    '股票-行业': ['银行', '证券', '保险', '券商', '地产', '房地产', '医药', '医疗', '消费', '白酒', '食品', '酒',
                '科技', '芯片', '半导体', '集成电路', '电子', '信息', '计算机', '软件', '信创', '通信', '传媒', 'tmt',
                '5g', '人工智能', 'ai', '云计算', '大数据', '物联网', '卫星', '电网', '金融',
                '新能源', '新能车', '电车', '光伏', '锂电', '电池', '汽车', '军工', '国防', '有色', '稀土', '稀有',
                '科创芯片', '科创ai', '科创生物', '科创半导', '科创材料', '科创新能', '科创机械', '科创信息',
                '创新药', '中药', '疫苗', '信息安全', '数字经济', '影视', '新材料',
                '煤炭', '钢铁', '石油', '油气', '化工', '农业', '畜牧', '养殖', '粮食', '基建', '建筑', '能源', '资源', '船舶',
                '建材', '家电', '纺织', '旅游', '酒店', '游戏', '动漫', '机器人', '央企', '国企', '碳中和',
                '高端制造', '工业', '机械', '电力', '公用', '水务', '环保', '物流', '交运', '港口',
                '航运', '航空', '铁路', '公路', '教育', '养老', '健康'],
    '跨境': ['纳斯达克', '纳指', '标普', '道琼斯', '恒指', '恒生', '港股', '中概', '德国', '日本', '东证', '日经',
             '越南', '印度', '海外', '全球', '美国', '亚太', '欧洲', '法国', '英国', '沙特', '巴西',
             '东南亚', '新兴亚洲', '香港', 'h股'],
    '股票-股息红利': ['红利', '高股息', '价值', '成长', '低波', '质量'],
    'REITs': ['reit'],
    '货币': ['货币', '现金'],
}

SUBCLASS_KEYWORDS = {
    '股票-行业': [
        ('银行', ['银行']),
        ('电子通信', ['信息', '科技', '通信', '电子', '5g', '物联网', '信息技术', '计算机', '软件',
                     '云计算', '大数据', '信创', '信息安全', '数字经济', '人工智能', 'ai',
                     '卫星', 'tmt', '传媒']),
        ('证券保险', ['证券', '券商', '保险', '非银', '证保', '金融']),
        ('医药', ['医药', '医疗', '生物', '创新药', '中药', '疫苗', '医疗器械', '药']),
        ('食品饮料', ['白酒', '食品', '饮料', '酒']),
        ('半导体', ['芯片', '半导体', '集成电路']),
        ('新能源', ['新能源', '新能', '光伏', '锂电', '电池', '碳中和', '绿色电力', '新能车', '新汽车', '电车']),
        ('军工', ['军工', '国防', '航天', '航空']),
        ('有色', ['有色', '稀土', '稀有', '金属', '矿业']),
        ('能源煤炭', ['煤炭', '石油', '油气', '能源', '资源']),
        ('化工', ['化工', '石化', '材料']),
        ('农业', ['农业', '畜牧', '养殖', '粮食', '农牧']),
        ('地产建筑', ['地产', '房地产', '基建', '建筑', '建材']),
        ('公用环保', ['电力', '公用', '环保', '水务', '电网']),
        ('消费', ['家电', '消费', '旅游', '零售', '纺织', '养老', '教育', '酒店']),
        ('传媒游戏', ['传媒', '游戏', '影视', '动漫', '文娱']),
        ('机械制造', ['机械', '装备', '制造', '机器人', '机床', '船舶', '汽车', '高端',
                     '工业', '智能', '物流', '交运', '运输', '航运', '港口', '铁路', '公路']),
        ('钢铁', ['钢铁']),
        ('央企国企', ['央企', '国企', '央创']),
        ('贵金属', ['黄金']),
    ],
    '跨境': [
        ('中概', ['中概', '中国互联网']),
        ('港股', ['港股', '恒生', '恒指', '香港', 'h股']),
        ('美股', ['纳斯达克', '纳指', '标普', '道琼斯', '美国']),
        ('日本', ['日经', '东证']),
        ('欧股', ['德国', '法国']),
        ('中东', ['沙特']),
        ('新兴市场', ['东南亚', '新兴亚洲', '亚太', '巴西', '印度', '越南', '全球']),
    ],
    '股票-宽基': [
        ('科创板', ['科创', '双创']),
        ('创业板', ['创业']),
        ('小盘', ['1000', '2000', '中创', '民企', '中小']),
        ('策略', ['esg', '龙头', '创新100', '科技',
                 '专精特新', '央企', '互联网', '基本面', '央视', '漂亮', '凤凰', '治理', '可持续', '核心',
                 '战略新兴']),
        ('中盘', ['500']),
        ('大盘', ['300', 'a500', 'a50', '50', '100', '180', '800', '超大盘', '沪深', '中证a', 'a股', '全指', '综指', '深成']),
        ('主题区域', ['湾区', '长三角', '杭州湾', '浙江', '湖北', '成渝', '长江', '之江', '张江', '一带一路']),
    ],
    '股票-股息红利': [
        ('策略', ['红利', '高股息', '价值', '成长', '低波', '质量']),
    ],
    '债券': [
        ('利率债', ['国债', '政金', '国开']),
        ('可转债', ['转债']),
        ('地方债', ['地债', '地方债']),
        ('短融', ['短融']),
        ('信用债', ['城投', '公司债', '信用', '企业债', '科创债', '金融债']),
    ],
    '商品': [
        ('商品期货', ['上期有色金属', '期货']),
        ('贵金属', ['黄金', '金']),
        ('农产品', ['豆粕']),
        ('能化', ['能源化工', '原油', '油气']),
    ],
}

def yy_resolve_end_date(end_date):
    if end_date is None:
        today = _dt.date.today()
        days = get_trade_days(start_date=(today - _dt.timedelta(days=30)).strftime('%Y-%m-%d'),
                              end_date=today.strftime('%Y-%m-%d'))
        if len(days) == 0:
            raise RuntimeError('无法获取交易日历')
        return pd.Timestamp(days[-1]).date()
    return pd.Timestamp(end_date).date()

def yy_get_all_etfs(date):
    date = pd.Timestamp(date).date()
    cache = getattr(g, '_all_etfs_cache', {})
    if cache.get('date') == date and cache.get('df') is not None:
        return cache['df']
    all_funds = get_all_securities(['fund'], date=date)
    yy_step(f"取全部场内基金: {len(all_funds)} 只")
    etfs = all_funds[all_funds['type'] == 'etf'].copy()
    yy_step(f"只留ETF类型: 剩 {len(etfs)} 只（剔除 {len(all_funds) - len(etfs)} 只非ETF基金）")
    etfs = etfs.reset_index()
    etfs = etfs.rename(columns={etfs.columns[0]: 'code'})
    g._all_etfs_cache = {'date': date, 'df': etfs}
    return etfs

def yy_name_hit(name, keywords):
    if not name: return False
    for kw in keywords:
        if kw in name: return True
    return False

def yy_filter_basic(etfs_df, date):
    df = etfs_df.copy()
    stats = {'money': 0, 'bond': 0, 'new': 0}
    if EXCLUDE_MONEY:
        n_before = len(df)
        mask_money = df['display_name'].apply(lambda x: yy_name_hit(str(x), MONEY_KEYWORDS))
        df = df[~mask_money]
        stats['money'] = n_before - len(df)
        if stats['money'] > 0:
            yy_step(f"剔除货币类ETF: 剩 {len(df)} 只（剔除 {stats['money']} 只）")
    if EXCLUDE_BOND:
        n_before = len(df)
        mask_bond = df['display_name'].apply(lambda x: yy_name_hit(str(x), BOND_KEYWORDS))
        df = df[~mask_bond]
        stats['bond'] = n_before - len(df)
        if stats['bond'] > 0:
            yy_step(f"剔除债券类ETF: 剩 {len(df)} 只（剔除 {stats['bond']} 只）")
    if MIN_LIST_DAYS > 0:
        cutoff = pd.Timestamp(date) - pd.Timedelta(days=MIN_LIST_DAYS)
        mask_new = pd.to_datetime(df['start_date']) > cutoff
        stats['new'] = int(mask_new.sum())
        if stats['new'] > 0:
            yy_step(f"硬过滤·剔除上市不足{MIN_LIST_DAYS}天的新ETF: 剩 {len(df) - stats['new']} 只（剔除 {stats['new']} 只）")
            df = df[~mask_new]
    return df, stats

def yy_fetch_traced_index_table():
    today = str(_dt.date.today())
    cache = getattr(g, '_index_table_cache', {})
    if cache.get('date') == today and cache.get('df') is not None:
        return cache['df']
    PAGE = 4000
    chunks = []
    offset = 0
    while True:
        q = (query(finance.FUND_INVEST_TARGET).limit(PAGE).offset(offset))
        part = finance.run_query(q)
        if part is None or len(part) == 0: break
        chunks.append(part)
        if len(part) < PAGE: break
        offset += PAGE
    if len(chunks) == 0:
        return pd.DataFrame(columns=['code', 'name', 'traced_index_name', 'traced_index_code'])
    df = pd.concat(chunks, ignore_index=True)
    end_col = df['end_date'].astype(str).str.strip()
    expired_mask = ~((df['end_date'].isna()) | (end_col == '') | (end_col.str.lower() == 'none') | (end_col.str.lower() == 'nat'))
    active = df[~expired_mask].copy()
    if 'pub_date' in active.columns:
        active = active.sort_values('pub_date')
    active = active.drop_duplicates(subset=['code'], keep='last')
    yy_sub(f"获取ETF跟踪指数记录: 有效 {len(active)} 条")
    g._index_table_cache = {'date': today, 'df': active[['code', 'name', 'traced_index_name', 'traced_index_code']]}
    return active[['code', 'name', 'traced_index_name', 'traced_index_code']]

def yy_fetch_one_price(code, end, count):
    try:
        px = get_price(code, end_date=end, count=count, frequency='daily',
                       fields=['close', 'money'], skip_paused=True, fq=None, panel=False)
    except Exception:
        return None
    if px is None or len(px) == 0: return None
    close_col = px['close']
    if hasattr(close_col, 'iloc'):
        close_val = float(close_col.iloc[-1])
        money_val = float(px['money'].mean()) / 1e4
    else:
        return None
    return {'code': code, 'close': close_val, 'avg_money_wan': money_val}

def yy_fetch_market_data(codes, end_date):
    end = pd.Timestamp(end_date).strftime('%Y-%m-%d')
    records = []
    for code in codes:
        rec = yy_fetch_one_price(code, end, AVG_MONEY_DAYS)
        if rec is not None: records.append(rec)
    if len(records) == 0:
        yy_sub('警告: 未获取到任何行情数据！')
        return pd.DataFrame(columns=['close', 'avg_money_wan'])
    out = pd.DataFrame(records).set_index('code')
    yy_sub(f"逐只取行情和成交额: {len(out)}/{len(codes)} 只")
    return out

def yy_query_share_day(d):
    chunks = []
    offset = 0
    while True:
        q = (query(finance.FUND_SHARE_DAILY)
             .filter(finance.FUND_SHARE_DAILY.date == d)
             .limit(4000).offset(offset))
        part = finance.run_query(q)
        if part is None or len(part) == 0: break
        chunks.append(part)
        if len(part) < 4000: break
        offset += 4000
    if len(chunks) == 0: return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)

def yy_probe_latest_she_date(end_date):
    probe_code = '159915.XSHE'
    try:
        q = (query(finance.FUND_SHARE_DAILY.date)
             .filter(finance.FUND_SHARE_DAILY.code == probe_code)
             .order_by(finance.FUND_SHARE_DAILY.date.desc())
             .limit(1))
        df = finance.run_query(q)
        if df is not None and len(df) > 0:
            return str(df['date'].iloc[0])[:10]
    except Exception:
        pass
    for back in range(0, 181):
        d = (pd.Timestamp(end_date) - _dt.timedelta(days=back)).strftime('%Y-%m-%d')
        try:
            probe = finance.run_query(
                query(finance.FUND_SHARE_DAILY.code)
                .filter(finance.FUND_SHARE_DAILY.date == d,
                        finance.FUND_SHARE_DAILY.code == probe_code)
                .limit(1))
        except Exception:
            continue
        if probe is not None and len(probe) > 0:
            return d
    return None

def yy_update_shares_map(shares_map, df):
    for c, s in zip(df['code'].astype(str), df['shares']):
        shares_map[c] = s
        shares_map[c.split('.')[0]] = s

def yy_fetch_scale(codes, end_date):
    shares_map = {}
    for back in range(0, 16):
        d = (pd.Timestamp(end_date) - _dt.timedelta(days=back)).strftime('%Y-%m-%d')
        df_day = yy_query_share_day(d)
        if len(df_day) == 0: continue
        yy_sub(f"取基金份额（沪市）: 数据日期 {d}")
        yy_update_shares_map(shares_map, df_day)
        break
    has_she = any(str(c).endswith('.XSHE') for c in shares_map.keys())
    if not has_she:
        she_date = yy_probe_latest_she_date(end_date)
        if she_date:
            df_she = yy_query_share_day(she_date)
            df_she = df_she[df_she['code'].astype(str).str.endswith('.XSHE')]
            yy_sub(f"取基金份额（深市）: {len(df_she)} 只，数据日期 {she_date}")
            yy_update_shares_map(shares_map, df_she)
    missing = [c for c in codes
               if shares_map.get(c) is None
               and shares_map.get(str(c).split('.')[0]) is None]
    if len(missing) > 0:
        filled = 0
        for code in missing:
            try:
                fund_data = get_fund_info(code, end_date)
                if fund_data is not None and 'fund_share' in fund_data.columns:
                    share_series = fund_data['fund_share'].dropna()
                    if len(share_series) > 0:
                        shares_map[code] = float(share_series.iloc[-1]) * 10000
                        filled += 1
            except Exception:
                continue
        yy_sub(f"get_fund_info 补齐份额: {filled}/{len(missing)} 只")
    rows = []
    for code in codes:
        s = shares_map.get(code)
        if s is None:
            s = shares_map.get(str(code).split('.')[0])
        rows.append({'code': code, 'shares': s})
    return pd.DataFrame(rows).set_index('code')

def yy_index_display(row):
    code = str(row.get('traced_index_code') or '').strip()
    name = str(row.get('traced_index_name') or '').strip()
    if code.lower() in ('none', 'nan'): code = ''
    if name.lower() in ('none', 'nan'): name = ''
    if name and code and ('(' not in name):
        return f"{name}({code})"
    return name or code or '未知指数'

def yy_sort_by_rank(df):
    return df.sort_values(['规模_亿'], ascending=False, na_position='last')

def yy_classify_etf(name):
    if not name: return '其他'
    low = str(name).lower()
    for asset_class, keywords in ASSET_CLASS_KEYWORDS.items():
        if any(kw.lower() in low for kw in keywords):
            return asset_class
    return '其他'

def yy_asset_class(row):
    name = str(row.get('display_name') or '')
    idx = re.sub(r'\([^)]*\)$', '', str(row.get('index_display') or '')).strip()
    low_name = name.lower()
    low_idx = idx.lower() if idx else ''
    if yy_name_hit(low_name, STAR_BROAD_KEYWORDS) or yy_name_hit(low_idx, STAR_BROAD_KEYWORDS):
        return '股票-宽基'
    if yy_name_hit(low_name, BOND_KEYWORDS) or yy_name_hit(low_idx, BOND_KEYWORDS):
        return '债券'
    if (yy_name_hit(low_idx, ['上期有色金属', '期货'])
            or yy_name_hit(low_name, ['上期有色金属', '豆粕期货', '能源化工'])):
        return '商品'
    if yy_name_hit(low_name, ['黄金股']) or yy_name_hit(low_idx, ['黄金股', '黄金股票']):
        return '股票-行业'
    cross_hit = (yy_name_hit(low_name, CROSS_BORDER_KEYWORDS)
                 or yy_name_hit(low_idx, CROSS_BORDER_KEYWORDS))
    cross_exclude = (yy_name_hit(low_name, CROSS_BORDER_EXCLUDE)
                     or yy_name_hit(low_idx, CROSS_BORDER_EXCLUDE))
    if cross_hit and not cross_exclude:
        return '跨境'
    if yy_name_hit(low_name, SMART_BETA_KEYWORDS) or yy_name_hit(low_idx, SMART_BETA_KEYWORDS):
        return '股票-股息红利'
    cls = yy_classify_etf(name)
    if cls == '其他' and low_idx:
        idx_cls = yy_classify_etf(idx)
        if idx_cls == '股票-宽基': cls = '股票-宽基'
    if cls == '股票-宽基' and (yy_name_hit(low_name, REAL_INDUSTRY_KEYWORDS)
                               or yy_name_hit(low_idx, REAL_INDUSTRY_KEYWORDS)):
        return '股票-行业'
    if cls != '其他': return cls
    if idx and idx != '未知指数':
        idx_cls = yy_classify_etf(idx)
        if idx_cls != '其他': return idx_cls
    return '其他'

def yy_subclass(row):
    rules = SUBCLASS_KEYWORDS.get(str(row.get('asset_class') or ''))
    if not rules: return '其他'
    texts = [str(row.get('display_name') or '')]
    idx = re.sub(r'\([^)]*\)$', '', str(row.get('index_display') or '')).strip()
    if idx and idx != '未知指数': texts.append(idx)
    for text in texts:
        if not text or text == '未知指数': continue
        low = text.lower()
        for subclass, keywords in rules:
            if any(kw.lower() in low for kw in keywords):
                return subclass
    return '其他'
# ==================== S1 build_etf_pool主函数 ====================
def build_etf_pool(end_date):
    """
    输入基准日期，基础过滤后返回最终ETF代码列表（已去掉深度去重）。
    """
    _step_counter[0] = 0
    end_date = yy_resolve_end_date(end_date)

    # 1. 获取全部场内ETF + 基础过滤
    etfs = yy_get_all_etfs(end_date)
    n_all = len(etfs)
    etfs, basic_stats = yy_filter_basic(etfs, end_date)

    # 2. 匹配跟踪指数 + 计算规模成交额
    index_table = yy_fetch_traced_index_table()
    df = etfs.merge(index_table[['code', 'traced_index_name', 'traced_index_code']], on='code', how='left')
    codes = df['code'].tolist()
    market = yy_fetch_market_data(codes, end_date)
    scale = yy_fetch_scale(codes, end_date)
    df = df.merge(market, on='code', how='left')
    df = df.merge(scale, on='code', how='left')
    df['规模_亿'] = df['shares'] * df['close'] / 1e8

    # 3. 迷你基金过滤
    if EXCLUDE_MINI and MINI_SCALE > 0:
        mini_mask = df['规模_亿'].notna() & (df['规模_亿'] < MINI_SCALE)
        df = df[~mini_mask]
        yy_step(f'迷你基金过滤: 剔除 {int(mini_mask.sum())} 只，剩 {len(df)} 只')

    # 4. 流动性过滤
    if EXCLUDE_LIQUIDITY and MIN_MONEY > 0:
        liq_mask = df['avg_money_wan'].notna() & (df['avg_money_wan'] < MIN_MONEY)
        df = df[~liq_mask]
        yy_step(f'流动性过滤后: 剩 {len(df)} 只')

    # 5. 资产分类
    df = yy_sort_by_rank(df).copy()
    df['index_display'] = df.apply(yy_index_display, axis=1)
    df['asset_class'] = df.apply(yy_asset_class, axis=1)
    df['subclass'] = df.apply(yy_subclass, axis=1)
    final = df.copy()

    # 大类剔除
    class_exclude = []
    if EXCLUDE_DIVIDEND: class_exclude.append(('股票-股息红利', '股息红利'))
    if EXCLUDE_CROSS: class_exclude.append(('跨境', '跨境'))
    if EXCLUDE_COMMODITY: class_exclude.append(('商品', '商品'))
    if class_exclude:
        for cls, label in class_exclude:
            final = final[final['asset_class'] != cls]
        yy_step(f'大类剔除后: 剩 {len(final)} 只')

    yy_step('构建完成·汇总')
    yy_sub(f'场内ETF总数      : {n_all} 只')
    yy_sub(f'最终池子数量    : {len(final)} 只')
    yy_sub(f'总压缩率        : {(1 - len(final) / n_all) * 100:.1f}%')

    if SHOW_FULL_POOL:
        show_cols = ['code', 'display_name', 'asset_class', 'subclass', '规模_亿', 'avg_money_wan']

    return final['code'].tolist()

# ==================== S1 交易逻辑函数 ====================
def calculate_bias(codes, end_date):
    records = []
    end = pd.Timestamp(end_date).strftime('%Y-%m-%d')
    max_period = max(BIAS_SORT_DAYS, BIAS_BUY_DAYS)
    fetch_count = max_period + 20
    for code in codes:
        try:
            px = get_price(code, end_date=end, count=fetch_count, frequency='daily',
                          fields=['close'], skip_paused=True, fq='pre', panel=False)
        except Exception:
            continue
        if px is None or len(px) < max_period:
            continue
        close = px['close']
        ma_buy = close.rolling(BIAS_BUY_DAYS).mean().iloc[-1]
        ma_sort = close.rolling(BIAS_SORT_DAYS).mean().iloc[-1]
        if ma_buy <= 0 or ma_sort <= 0:
            continue
        bias_buy = (close.iloc[-1] - ma_buy) / ma_buy * 100
        bias_sort = (close.iloc[-1] - ma_sort) / ma_sort * 100
        try:
            name = get_security_info(code).display_name
        except Exception:
            name = code
        records.append({'代码': code, '名称': name,
                        '20日乖离率(%)': bias_buy, '50日乖离率(%)': bias_sort})
    return pd.DataFrame(records) if records else pd.DataFrame()

def check_trend(code, end_date, mode):
    if mode == 0:
        return True
    look = TREND_LOOKBACK
    px = get_price(code, end_date=end_date, count=look + 1, frequency='daily',
                   fields=['close'], skip_paused=True, fq='pre', panel=False)
    if px is None or len(px) < look + 1:
        return True
    close = px['close']
    last = float(close.iloc[-1])
    ma = float(close.iloc[-look:].mean())
    recent_low = float(close.iloc[:-1].min())
    not_new_low = last > recent_low
    above_ma = last > ma
    if mode == 1:
        return not_new_low
    if mode == 2:
        return above_ma
    if mode == 3:
        return not_new_low and above_ma
    return True

def check_oversold_stabilized(code, end_date):
    need = 20 + OVERSOLD_LOOKBACK
    px = get_price(code, end_date=end_date, count=need, frequency='daily',
                   fields=['close'], skip_paused=True, fq='pre', panel=False)
    if px is None or len(px) < need:
        return False
    close = px['close']
    ma20 = close.rolling(20).mean()
    bias20 = (close / ma20 - 1) * 100
    was_oversold = bias20.iloc[-OVERSOLD_LOOKBACK:].min() < BUY_BIAS_TH
    if not was_oversold:
        return False
    return check_trend(code, end_date, TREND_FILTER_MODE)

def should_sell(code, entry_price, entry_date, context):
    if entry_price is None or entry_price <= 0:
        return False, ''
    px = get_price(code, end_date=context.previous_date, count=1,
                   frequency='daily', fields=['close'], skip_paused=True, fq='pre', panel=False)
    if px is None or len(px) == 0:
        return False, ''
    last = float(px['close'].iloc[-1])
    if g.highest_price is None or last > g.highest_price:
        g.highest_price = last
    if g.highest_price and g.highest_price > 0:
        drawdown = (g.highest_price - last) / g.highest_price
        if drawdown >= g.TRAILING_STOP_PCT:
            return True, '移动止盈'
    if g.HOLD_MAX_DAYS and entry_date:
        ndays = get_trade_days(start_date=entry_date, end_date=context.current_dt.date())
        if len(ndays) - 1 >= g.HOLD_MAX_DAYS:
            return True, '时间'
    return False, ''

def _sync_params(context):
    for _k in ['MAX_HOLD', 'BIAS_SORT_DAYS', 'BIAS_BUY_DAYS', 'BUY_BIAS_TH',
               'TRAILING_STOP_PCT', 'HOLD_MAX_DAYS',
               'TREND_FILTER_MODE', 'TREND_LOOKBACK', 'OVERSOLD_LOOKBACK', 'GAP_FILTER_TH']:
        globals()[_k] = getattr(g, _k)

def _s1_refresh_pool(context):
    if POOL_UPDATE_MONTHLY:
        m = context.current_dt.month
        if (m - 1) % POOL_REFRESH_MONTHS == 0 and m != getattr(g, 'last_pool_refresh_month', 0):
            g.etf_pool = build_etf_pool(context.previous_date)
            g.last_pool_refresh_month = m
    else:
        g.etf_pool = build_etf_pool(context.previous_date)

def _close_all_s2(context):
    for sec in list(g.accounts[SID_S2]['holdings']):
        close_position(sec)
    remaining = [sec for sec, pos in context.portfolio.positions.items()
                 if pos.total_amount > 0 and g.stock_owner.get(sec) == SID_S2]
    return remaining

def s1_init_state(context):
    """初始化S1状态"""
    g.etf_pool = []
    g.last_pool_refresh_month = 0
    g.entry_price = None
    g.entry_date = None
    g.highest_price = None
    g.MAX_HOLD          = getattr(g, 'MAX_HOLD', MAX_HOLD)
    g.BIAS_SORT_DAYS    = getattr(g, 'BIAS_SORT_DAYS', BIAS_SORT_DAYS)
    g.BIAS_BUY_DAYS     = getattr(g, 'BIAS_BUY_DAYS', BIAS_BUY_DAYS)
    g.BUY_BIAS_TH       = getattr(g, 'BUY_BIAS_TH', BUY_BIAS_TH)
    g.TRAILING_STOP_PCT = getattr(g, 'TRAILING_STOP_PCT', TRAILING_STOP_PCT)
    g.HOLD_MAX_DAYS     = getattr(g, 'HOLD_MAX_DAYS', HOLD_MAX_DAYS)
    g.TREND_FILTER_MODE = getattr(g, 'TREND_FILTER_MODE', TREND_FILTER_MODE)
    g.TREND_LOOKBACK    = getattr(g, 'TREND_LOOKBACK', TREND_LOOKBACK)
    g.OVERSOLD_LOOKBACK = getattr(g, 'OVERSOLD_LOOKBACK', OVERSOLD_LOOKBACK)
    g.GAP_FILTER_TH     = getattr(g, 'GAP_FILTER_TH', GAP_FILTER_TH)
    log.info("正在初始化S1 ETF股票池（完整版v2.2.3），请稍候...")
    g.etf_pool = build_etf_pool(context.previous_date)
    g.last_pool_refresh_month = context.current_dt.month

def s1_bottom_check(context):
    ensure_container(context)
    _sync_params(context)
    _s1_refresh_pool(context)
    if len(g.etf_pool) == 0:
        return
    bias_df = calculate_bias(g.etf_pool, context.previous_date)
    if bias_df.empty:
        return
    bias_df = bias_df.sort_values(by='50日乖离率(%)', ascending=True).reset_index(drop=True)

    # 0. 先检查S1持仓是否需要卖出
    s1_real_positions = []
    for sec in list(g.stock_owner.keys()):
        if g.stock_owner.get(sec) == SID_S1:
            pos = context.portfolio.positions.get(sec)
            if pos is not None and pos.total_amount > 0:
                s1_real_positions.append(sec)
    if not s1_real_positions and g.mode == 'bottom':
        for sec, pos in context.portfolio.positions.items():
            if pos.total_amount > 0:
                s1_real_positions.append(sec)

    if s1_real_positions:
        for code in list(s1_real_positions):
            sell, reason = should_sell(code, g.entry_price, g.entry_date, context)
            if sell:
                close_position(code)
                pos = context.portfolio.positions.get(code)
                if pos is None or pos.total_amount <= 0:
                    log.info("【融合·S1卖出】%s 触发卖出 (%s)", code, reason)
                    g.entry_price = None
                    g.entry_date = None
                    g.highest_price = None
                    g.mode = 'rot'
                    log.info("【融合·模式切换】抄底→轮动")
                else:
                    log.info("【融合·S1卖出未成交】%s 保留bottom下日再试", code)
        if g.mode == 'rot':
            return

    if g.mode == 'rot':
        # 抄底买入检测
        target = None
        for _, row in bias_df.iterrows():
            code = row['代码']
            if check_oversold_stabilized(code, context.previous_date):
                _day_open = get_current_data()[code].day_open
                if _day_open and _day_open > 0:
                    _px = get_price(code, end_date=context.previous_date, count=1,
                                    frequency='daily', fields=['close'], skip_paused=True, fq='pre', panel=False)
                    if _px is not None and len(_px) > 0:
                        _prev_close = float(_px['close'].iloc[-1])
                        if _prev_close > 0 and _day_open / _prev_close - 1 > GAP_FILTER_TH:
                            continue
                target = code
                break
        if target is None:
            return
        s2_remaining = _close_all_s2(context)
        if s2_remaining:
            log.info("【融合·抄底取消】S2清仓未完成(%s)，放弃本次抄底", s2_remaining)
            return
        total = context.portfolio.total_value
        order = open_position(context, target, total * 0.995, SID_S1)
        filled = getattr(order, 'filled', 0) if order else 0
        if filled <= 0:
            log.info("【融合·抄底取消】S1买入未成交(%s)，保持rot模式", target)
            return
        g.entry_price = get_current_data()[target].day_open
        g.entry_date = context.current_dt.date()
        g.highest_price = g.entry_price
        g.mode = 'bottom'
        log.info("【融合·模式切换】轮动→抄底：全仓买入 %s", target)
    else:
        if not s1_real_positions:
            g.mode = 'rot'
# ==================== S2 五福v7初始化（完整g变量定义） ====================
def s2_init_state(context):
    log.info("[机制测试] C06_C03加入V6.6强弱市过滤 | 仅修改普通候选池过滤切换")
    log.info("【五福v1.1】择时执行 + opt2_v4 + H72 + H78a 方案B(MA+R²) 启动！")

    # ==================== ETF池定义 ====================
    g.global_etf_pool = [
        '518880.XSHG',  # (黄金ETF)
        '501018.XSHG',  # (南方原油)
        '161226.XSHE',  # (国投白银LOF)
        '159985.XSHE',  # (豆粕ETF华夏)
        '159980.XSHE',  # (有色ETF大成)
        '513310.XSHG',  # (中韩芯片)
        '159518.XSHE',  # (标普油气ETF嘉实)
        '159509.XSHE',  # (纳指科技ETF景顺)
        '513100.XSHG',  # (纳指ETF)
        '513520.XSHG',  # (日经ETF)
        '513500.XSHG',  # (标普500)
        '159502.XSHE',  # (标普生物科技ETF嘉实)
        '513400.XSHG',  # (道琼斯)
        '513030.XSHG',  # (德国ETF)
        '513290.XSHG',  # (纳指生物)
        '520830.XSHG',  # (沙特ETF)
        '159529.XSHE',  # (标普消费ETF景顺)
    ]
    g.china_etf_pool = [
        '513090.XSHG',  # (香港证券)
        '513120.XSHG',  # (HK创新药)
        '513180.XSHG',  # (恒指科技)
        '513330.XSHG',  # (恒生互联)
        '513750.XSHG',  # (港股非银)
        '159892.XSHE',  # (恒生医药ETF华夏)
        '513190.XSHG',  # (H股金融)
        '159605.XSHE',  # (中概互联ETF广发)
        '513630.XSHG',  # (香港红利)
        '159323.XSHE',  # (港股通汽车ETF华夏)
        '510900.XSHG',  # (恒生中国)
        '513920.XSHG',  # (央企40)
        '513970.XSHG',  # (恒生消费)
        '511380.XSHG',  # (转债ETF)
        '512050.XSHG',  # (A500E)
        '510500.XSHG',  # (500ETF)
        '159915.XSHE',  # (创业板ETF易方达)
        '510300.XSHG',  # (300ETF)
        '512100.XSHG',  # (1000ETF)
        '159949.XSHE',  # (创业板50ETF华安)
        '588080.XSHG',  # (科创板50)
        '159967.XSHE',  # (创业板成长ETF华夏)
        '588220.XSHG',  # (科创100F)
        '563300.XSHG',  # (中证2000)
        '510760.XSHG',  # (上证ETF)
        '588200.XSHG',  # (科创芯片)
        '515880.XSHG',  # (通信ETF)
        '159981.XSHE',  # (能源化工ETF建信)
        '512880.XSHG',  # (证券ETF)
        '513350.XSHG',  # (油气ETF)
        '159326.XSHE',  # (电网设备ETF华夏)
        '159516.XSHE',  # (半导体设备ETF国泰)
        '159206.XSHE',  # (卫星ETF永赢)
        '512480.XSHG',  # (半导体)
        '159363.XSHE',  # (创业板人工智能ETF华宝)
        '159870.XSHE',  # (化工ETF鹏华)
        '512400.XSHG',  # (有色ETF)
        '159755.XSHE',  # (电池ETF广发)
        '588170.XSHG',  # (科创半导)
        '159992.XSHE',  # (创新药ETF银华)
        '159995.XSHE',  # (芯片ETF华夏)
        '512890.XSHG',  # (红利低波)
        '515220.XSHG',  # (煤炭ETF)
        '159566.XSHE',  # (储能电池ETF易方达)
        '159819.XSHE',  # (人工智能ETF易方达)
        '512800.XSHG',  # (银行ETF)
        '512690.XSHG',  # (酒ETF)
        '515050.XSHG',  # (5GETF)
        '562500.XSHG',  # (机器人)
        '512170.XSHG',  # (医疗ETF)
        '517520.XSHG',  # (黄金股)
        '159869.XSHE',  # (游戏ETF华夏)
        '512070.XSHG',  # (证券保险)
        '159611.XSHE',  # (电力ETF广发)
        '562800.XSHG',  # (稀有金属)
        '515120.XSHG',  # (创新药)
        '512010.XSHG',  # (医药ETF)
        '510880.XSHG',  # (红利ETF)
        '515790.XSHG',  # (光伏ETF)
        '515980.XSHG',  # (人工智能)
        '512660.XSHG',  # (军工ETF)
        '159928.XSHE',  # (消费ETF汇添富)
        '512710.XSHG',  # (军工龙头)
        '560860.XSHG',  # (工业有色)
        '515030.XSHG',  # (新汽车)
        '159766.XSHE',  # (旅游ETF富国)
        '159218.XSHE',  # (卫星ETF招商)
        '159852.XSHE',  # (软件ETF嘉实)
        '516160.XSHG',  # (新能源)
        '516150.XSHG',  # (稀土基金)
        '159227.XSHE',  # (航空航天ETF华夏)
        '159583.XSHE',  # (通信ETF富国)
        '588790.XSHG',  # (科创智能)
        '159865.XSHE',  # (养殖ETF国泰)
        '512980.XSHG',  # (传媒ETF)
        '159851.XSHE',  # (金融科技ETF华宝)
        '561360.XSHG',  # (石油ETF)
        '561980.XSHG',  # (芯片设备)
        '562590.XSHG',  # (半导材料)
        '512200.XSHG',  # (地产ETF)
        '159732.XSHE',  # (消费电子ETF华夏)
        '159667.XSHE',  # (工业母机ETF国泰)
        '516510.XSHG',  # (云计算)
        '159840.XSHE',  # (锂电池ETF工银)
        '159998.XSHE',  # (计算机ETF天弘)
        '159825.XSHE',  # (农业ETF富国)
        '512670.XSHG',  # (国防ETF)
        '159883.XSHE',  # (医疗器械ETF永赢)
        '515210.XSHG',  # (钢铁ETF)
        '515400.XSHG',  # (大数据)
        '159256.XSHE',  # (创业板软件ETF华夏)
        '561330.XSHG',  # (矿业ETF)
        '515170.XSHG',  # (食品饮料)
        '159638.XSHE',  # (高端装备ETF嘉实)
        '516520.XSHG',  # (智能驾驶)
        '513360.XSHG',  # (教育ETF)
        '516190.XSHG',  # (文娱ETF)
    ]
    # 固定ETF池 = 全球池 + 中国池（正常期使用的完整候选池）
    g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool

    # ==================== S2 状态与参数 ====================
    g.avg_etf_money_threshold = None          # 全市场ETF流动性阈值（动态计算，单位：元）
    g.filtered_fixed_pool = []                # 经过流动性过滤后的固定池（正常期使用）
    g.dynamic_etf_pool = []                   # 动态行业ETF池（各行业流动性最佳者）
    g.merged_etf_pool = []                    # 合并池：过滤后固定池+动态池（最终参与动量计算）
    g.ranked_etfs_result = []                 # 动量排名结果列表
    g.filtered_global_pool = []               # 走弱期使用的过滤后全球/海外池

    g.is_a_share_weak = False                 # 大A走弱期标志
    g.weak_period_ma_lookback = 10            # 判断走弱期使用的MA均线周期（日）
    g.weak_start_date = None                  # 走弱期开始日期
    g.weak_days_count = 0                     # 走弱期已持续天数
    g.max_weak_days = 20                      # 走弱期最长持续天数（超过强制退出）

    g.holdings_num = 1                        # 目标持仓ETF数量
    g.defensive_etf = "511880.XSHG"           # 防御性ETF（无合适标的时买入）
    g.min_money = 10                          # 单笔交易最小金额（元）
    g.target_etfs_list = []                   # 今日目标ETF列表（卖出写入，买入使用）
    g.pending_buy_etfs = []                   # 待买入ETF列表（用于趋势复检/强制买入）
    g.etf_names_dict = {}                     # ETF代码→名称映射缓存
    g.cache_date = None                       # 缓存日期（每日重置）
    g.yesterday_close_cache = {}              # 昨日收盘价缓存（分钟级跌幅止损用）
    g.trend_lookback_minutes = 30             # 盘中趋势判断回看分钟数
    g.trend_slope_threshold = 0.001           # 趋势判断斜率阈值（%/min）
    g.trend_r2_threshold = 0.3                # 趋势判断R²阈值

    g.lookback_days = 25                      # 动量得分计算回看天数
    g.min_score_threshold = 0                 # 动量得分最低阈值
    g.max_score_threshold = 5                 # 动量得分最高阈值（主线可突破）
    g.score_threshold_ratio = 0.9             # 调仓系数（保留持仓得分阈值=第N名×该系数）

    g.enable_r2_filter = True                 # 启用R²过滤
    g.r2_threshold = 0.4                      # R²过滤阈值
    g.enable_ma_filter = True                 # 启用均线过滤（走弱期）
    g.ma_lookback = 10                        # 均线过滤回看天数
    g.ma_threshold = 1.0                      # 均线阈值：现价>MA×此值
    g.enable_volume_check = True              # 启用成交量过滤
    g.volume_lookback = 5                     # 成交量过滤回看天数
    g.volume_threshold = 1.8                  # 量比阈值：当日预估/过去日均<此值
    g.enable_loss_filter = True               # 启用短期风控（近3日跌幅）
    g.loss = 0.97                             # 短期风控阈值：近3日单日涨跌幅>此值
    g.enable_premium_filter = False           # 启用溢价率过滤
    g.max_premium_rate = 30                   # 溢价率阈值（%）
    g.enable_laplace_filter = False           # 启用拉普拉斯滤波
    g.laplace_s_param = 0.05                  # 拉普拉斯平滑参数s
    g.laplace_min_slope = 0.002               # 拉普拉斯斜率阈值
    g.dynamic_pool_top_n = 150                # 动态池保留行业数量（Top N）
    g.liquidity_threshold_divisor = 15000     # 流动性阈值分母（日均总成交额/此值）

    g.max_portfolio_value = 0                 # 历史最高组合价值（回撤监控）
    g.drawdown_threshold = 0.03               # 回撤预警阈值（3%记录一次）
    g.drawdown_records = []                   # 回撤记录列表

    g.use_fixed_stop_loss = False             # 启用分钟级固定比例止损
    g.fixedStopLossThreshold = 0.95           # 固定止损阈值（现价≤成本价×此值）
    g.use_pct_stop_loss = False               # 启用分钟级当日跌幅止损
    g.pct_stop_loss_threshold = 0.95          # 当日跌幅止损阈值（现价≤昨收×此值）

    # ==================== B型阶梯主线：极端高分前的早期识别 ====================
    g.enable_super_mainline = True            # 启用B型主线识别
    g.mainline_score_min = 5.0                # 主线动量得分下限
    g.mainline_score_max = 20.0               # 主线动量得分上限
    g.mainline_days = 5                       # 主线判断回看天数
    g.mainline_min_r2 = 0.85                  # 主线当日R²最低要求
    g.mainline_min_r2_avg = 0.90              # 主线近N日R²均值最低要求
    g.mainline_min_volume_avg = 1.8           # 主线近N日量比均值最低要求
    g.mainline_min_score_up_days = 4          # 主线近N日score抬升天数要求
    g.mainline_min_positive_laplace_days = 5  # 主线近N日拉普拉斯正斜率天数要求
    g.mainline_min_score_growth = 2.0         # 主线score增长倍数要求

    # ==================== B型主线持仓延续 ====================
    g.enable_mainline_retain = True           # 启用主线持仓延续
    g.mainline_retain_min_r2 = 0.85           # 持仓延续R²最低要求
    g.mainline_retain_min_lap_slope = 0.0     # 持仓延续拉普拉斯斜率最低要求

    # ==================== Regime P0：仅观测/record，不改交易 ====================
    g.enable_regime_p0 = True                 # 启用市场状态P0评估
    g.regime_breadth_ma = 20                  # 市场宽度计算MA周期
    g.regime_breadth_high = 0.55              # 市场宽度高阈值（强势）
    g.regime_breadth_structural = 0.50        # 市场宽度结构态阈值
    g.regime_breadth_low = 0.35               # 市场宽度低阈值（防御）
    g.regime_liquidity_min_yi = 20000.0       # 流动性阈值（亿元）
    g.regime_liquidity_lookback = 20          # 流动性计算回看天数
    g.regime_p0_log = []                      # P0状态日志列表

    # ==================== 优化2：震荡市量价背离过滤 ====================
    g.enable_choppy_detection = True          # 启用震荡市检测
    g.choppy_lookback = 10                    # 震荡市判断回看天数
    g.choppy_max_ret = 0.010                  # 震荡市涨跌幅阈值（绝对值<此值）
    g.is_choppy = False                       # 是否处于震荡市标志
    g.enable_volume_divergence_filter = True  # 启用量价背离过滤
    g.vd_lookback = 5                         # 量价背离检测窗口
    g.vd_price_up_threshold = 0.02            # 背离价格涨幅阈值
    g.vd_vol_down_threshold = -0.10           # 背离成交量缩量阈值

    # ==================== H72 动态走弱动量窗口 ====================
    g.weak_momentum_lookback = 25             # 走弱期动量计算回看天数
    g.weak_momentum_lookback_base = 25        # 基础回看天数
    g.weak_momentum_lookback_short = 23       # 缩短后回看天数（信号质量高时）
    g.enable_dynamic_weak_lookback = True     # 启用动态调整回看天数
    g.r2_lookback_for_signal_quality = 25     # 信号质量（R²）回看天数
    g.r2_threshold_for_signal_quality = 0.4   # 进入短窗口R²阈值
    g.r2_threshold_exit = 0.38                # 退出短窗口R²阈值
    g.r2_hysteresis_enter_days = 2            # 进入短窗口所需连续天数
    g.r2_hysteresis_exit_days = 2             # 退出短窗口所需连续天数
    g.r2_signal_aggregation = "mean"          # 信号聚合方式：mean/median
    g.r2_dynamic_tag = "H72"                  # 动态窗口标签
    g.r2_high_streak = 0                      # 连续高于阈值计数
    g.r2_low_streak = 0                       # 连续低于阈值计数
    g.r2_dyn_days_23 = 0                      # 使用短窗口天数统计
    g.r2_dyn_days_25 = 0                      # 使用基础窗口天数统计
    g.r2_dyn_switch_count = 0                 # 窗口切换次数统计

    # ==================== H78a 走弱期 R² 过滤（方案B：保留 MA + R² 双过滤）====================
    g.enable_weak_r2_filter = True            # 启用走弱期R²过滤

    log.info("【S2五福v7初始化完成】")
# ==================== S2 计算与过滤函数 ====================
def check_weak_period_daily(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    check_a_share_weak_period(context)
    if getattr(g, 'enable_choppy_detection', False):
        check_choppy_market(context)
    midday_routine(context)

def check_choppy_market(context):
    if not getattr(g, 'enable_choppy_detection', False):
        return
    indexes = ['000300.XSHG', '399101.XSHE', '399006.XSHE', '000510.XSHG']
    choppy_count = 0
    details = []
    for code in indexes:
        try:
            df = attribute_history(code, g.choppy_lookback + 1, '1d', ['close'], skip_paused=False)
            if df is None or len(df) < g.choppy_lookback + 1:
                details.append(f"{code}:数据不足")
                continue
            ret_10d = float(df['close'].iloc[-1] / df['close'].iloc[0] - 1)
            details.append(f"{code}:{ret_10d:+.2%}")
            if abs(ret_10d) < g.choppy_max_ret:
                choppy_count += 1
        except Exception:
            details.append(f"{code}:异常")
    was_choppy = bool(getattr(g, 'is_choppy', False))
    g.is_choppy = (choppy_count >= 3)
    if g.is_choppy and not was_choppy:
        log.info(f"🟡 【震荡市检测】{choppy_count}/4 指数近10日涨跌幅<{g.choppy_max_ret:.0%}，进入震荡模式 | {', '.join(details)}")
    elif not g.is_choppy and was_choppy:
        log.info(f"🟢 【震荡市检测】退出震荡模式 | {', '.join(details)}")

def check_volume_price_divergence(hist_closes, hist_volumes, context):
    if not getattr(g, 'enable_volume_divergence_filter', False):
        return True, {'reason': 'disabled'}
    if hist_closes is None or hist_volumes is None:
        return True, {'reason': 'no_data'}
    if len(hist_closes) < g.vd_lookback + 1 or len(hist_volumes) < g.vd_lookback + 1:
        return True, {'reason': 'insufficient_data'}
    try:
        price_change = float(hist_closes[-1] / hist_closes[-g.vd_lookback - 1] - 1)
        recent_vol = float(np.mean(hist_volumes[-3:]))
        earlier_vol = float(np.mean(hist_volumes[-g.vd_lookback - 1:-3]))
        if earlier_vol <= 0:
            return True, {'reason': 'earlier_vol_zero'}
        vol_change = float(recent_vol / earlier_vol - 1)
        is_divergence = (price_change > g.vd_price_up_threshold and vol_change < g.vd_vol_down_threshold)
        return (not is_divergence), {
            'price_change': price_change,
            'vol_change': vol_change,
            'is_divergence': is_divergence,
            'reason': 'divergence' if is_divergence else 'ok'
        }
    except Exception:
        return True, {'reason': 'error'}

def morning_routine(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    log.info("★" * 80)
    log.info("▶️ 【晨间流水线】启动...")
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)    
    log.info("【回撤监控】监控策略回撤...")
    monitor_drawdown(context)
    log.info("【流动性阈值】计算全市场ETF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("⏸️ 【晨间流水线】执行完毕！")

def midday_routine(context):
    if g.mode == 'bottom':
        return
    log.info("★" * 80)
    log.info("▶️ 【早盘流水线】启动...")
    if g.is_a_share_weak:
        log.info(f"🔴 【走弱期池更新】仅对全球/海外ETF池进行流动性过滤...")
        filter_global_pool_by_volume(context)
        log.info(f"【走弱期池更新完成】过滤后全球池: {len(g.filtered_global_pool)}只")
    else:
        log.info(f"🟢 【正常期池更新】执行动态池更新、固定池过滤、合并池...")
        log.info("【动态池更新】更新行业ETF动态池（各行业流动性最佳ETF）...")
        update_sector_pool(context)
        log.info("【固定池过滤】过滤固定ETF池流动性...")
        filter_fixed_pool_by_volume(context)
        log.info("【合并池】合并固定池与动态池...")
        daily_merge_etf_pools(context)
        log.info(f"【正常期池更新完成】合并池: {len(g.merged_etf_pool)}只")
    log.info("⏸️ 【早盘流水线】执行完毕！")

def afternoon_routine(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    log.info("▶️ 【午盘流水线】启动...")
    if g.is_a_share_weak:
        if hasattr(g, 'filtered_global_pool') and g.filtered_global_pool:
            g.merged_etf_pool = list(set(g.filtered_global_pool))
        else:
            g.merged_etf_pool = list(set(g.global_etf_pool))
        g.merged_etf_pool.sort()
        log.info(f"🔴 【大A走弱期】使用过滤后全球/海外ETF池，共{len(g.merged_etf_pool)}只")
    else:
        log.info(f"🟢 【大A正常期】使用合并池，共{len(g.merged_etf_pool)}只")
    log.info("【动量计算】计算ETF动量得分与排序...")
    calculate_and_log_ranked_etfs(context)
    log.info("【卖出执行】执行卖出操作...")
    execute_sell_trades(context)
    log.info("【买入执行】执行买入操作...")
    execute_buy_trades(context)
    log.info("⏸️ 【午盘流水线】执行完毕！")

def reset_daily_flags(context):
    ensure_container(context)
    g.cache_date = None
    g.yesterday_close_cache = {}
    g.pending_buy_etfs = []
    log.info("🔄 收盘缓存重置完成")

def adjust_weak_momentum_lookback(context):
    if not getattr(g, "enable_dynamic_weak_lookback", False):
        return
    try:
        etf_pool = g.global_etf_pool
        if not etf_pool:
            return
        lookback_days = g.r2_lookback_for_signal_quality
        end_date = context.previous_date
        r2_values = []
        for etf in etf_pool:
            try:
                df = get_price(
                    etf, end_date=end_date, count=lookback_days + 1,
                    frequency="daily", fields=["close"], panel=False,
                )
                if df is None or df.empty or len(df) < lookback_days + 1:
                    continue
                price_series = df["close"].values
                y = np.log(price_series)
                x = np.arange(len(y))
                weights = np.linspace(1, 2, len(y))
                W = weights ** 2
                W_sum = np.sum(W)
                x_bar = np.sum(W * x) / W_sum
                y_bar = np.sum(W * y) / W_sum
                dx = x - x_bar
                dy = y - y_bar
                variance_x = np.sum(W * dx ** 2)
                if variance_x == 0:
                    continue
                slope = np.sum(W * dx * dy) / variance_x
                intercept = y_bar - slope * x_bar
                y_pred = slope * x + intercept
                ss_res = np.sum(weights * (y - y_pred) ** 2)
                ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
                r_squared = 1 - ss_res / ss_tot if ss_tot else 0
                r2_values.append(r_squared)
            except Exception:
                continue
        if not r2_values:
            return
        agg = getattr(g, "r2_signal_aggregation", "mean")
        if agg == "median":
            pool_r2 = float(np.median(r2_values))
        else:
            pool_r2 = float(np.mean(r2_values))
        thr_hi = g.r2_threshold_for_signal_quality
        thr_lo = getattr(g, "r2_threshold_exit", 0.38)
        need_enter = int(getattr(g, "r2_hysteresis_enter_days", 2))
        need_exit = int(getattr(g, "r2_hysteresis_exit_days", 2))
        tag = getattr(g, "r2_dynamic_tag", "H72")
        if pool_r2 > thr_hi:
            g.r2_high_streak = getattr(g, "r2_high_streak", 0) + 1
            g.r2_low_streak = 0
        elif pool_r2 < thr_lo:
            g.r2_low_streak = getattr(g, "r2_low_streak", 0) + 1
            g.r2_high_streak = 0
        else:
            g.r2_high_streak = 0
            g.r2_low_streak = 0
        old_lookback = g.weak_momentum_lookback
        new_lookback = old_lookback
        reason = "hold"
        if old_lookback == g.weak_momentum_lookback_base and g.r2_high_streak >= need_enter:
            new_lookback = g.weak_momentum_lookback_short
            reason = "enter_23"
        elif old_lookback == g.weak_momentum_lookback_short and g.r2_low_streak >= need_exit:
            new_lookback = g.weak_momentum_lookback_base
            reason = "exit_23"
        switched = new_lookback != old_lookback
        if switched:
            g.weak_momentum_lookback = new_lookback
            g.r2_dyn_switch_count = getattr(g, "r2_dyn_switch_count", 0) + 1
        if g.weak_momentum_lookback == g.weak_momentum_lookback_short:
            g.r2_dyn_days_23 = getattr(g, "r2_dyn_days_23", 0) + 1
        else:
            g.r2_dyn_days_25 = getattr(g, "r2_dyn_days_25", 0) + 1
        if g.is_a_share_weak or switched:
            log.info(
                f"[R2动态{tag}] date={context.current_dt.date()} weak={int(g.is_a_share_weak)} "
                f"pool_r2={pool_r2:.4f} agg={agg} hi={g.r2_high_streak}/{need_enter} "
                f"lo={g.r2_low_streak}/{need_exit} reason={reason} "
                f"lb={g.weak_momentum_lookback} switched={int(switched)} "
                f"d23={getattr(g, 'r2_dyn_days_23', 0)} d25={getattr(g, 'r2_dyn_days_25', 0)} "
                f"sw={getattr(g, 'r2_dyn_switch_count', 0)}"
            )
            try:
                record(r2_avg=pool_r2, r2_weak_lb=float(g.weak_momentum_lookback))
            except Exception:
                pass
    except Exception as e:
        log.info(f"[R2动态{tag}] adjust 异常: {e}")

def check_positions(context):
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 【持仓检查】{security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")

def monitor_drawdown(context):
    try:
        current_value = context.portfolio.total_value
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value > 0:
            current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
            if current_drawdown >= g.drawdown_threshold:
                record = {
                    'date': context.current_dt.strftime('%Y-%m-%d'),
                    'drawdown': current_drawdown,
                    'portfolio_value': current_value,
                    'max_value': g.max_portfolio_value,
                    'is_weak': g.is_a_share_weak
                }
                positions_info = []
                for security in context.portfolio.positions:
                    position = context.portfolio.positions[security]
                    if position.total_amount > 0:
                        security_name = get_security_name(security)
                        positions_info.append(f"{security_name}:{position.total_amount}股")
                record['positions'] = positions_info
                g.drawdown_records.append(record)
                log.info(f"【回撤预警】回撤达到 {current_drawdown:.2%} (阈值: {g.drawdown_threshold:.0%})")
                log.info(f"  当前净值: {current_value:,.0f}  |  最高净值: {g.max_portfolio_value:,.0f}")
                log.info(f"  大A状态: {'走弱期' if g.is_a_share_weak else '正常期'}")
                log.info(f"  持仓: {', '.join(positions_info) if positions_info else '空仓'}")
    except Exception as e:
        log.error(f"【回撤监控】计算异常: {e}")

def calculate_global_etf_threshold(context):
    log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            log.warning("未找到任何场内ETF，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        log.info(f"全市场ETF总数: {len(etf_list)}只")
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date, frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            log.warning("无法获取历史成交额数据，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        daily_totals = df.groupby('time')['money'].sum()
        daily_counts = df[df['money'] > 0].groupby('time')['code'].nunique()
        for day, money in daily_totals.items():
            count = daily_counts.get(day, 0)
            log.info(f"  {day.date()} 全市场ETF总成交额: {money/1e8:.2f}亿元 ({count}只ETF有成交)")
        if len(daily_totals) < 3:
            log.warning(f"仅有{len(daily_totals)}个有效交易日，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        threshold = avg_total_money / g.liquidity_threshold_divisor
        g.avg_etf_money_threshold = threshold
        log.info(f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF日均总成交额={avg_total_money/1e8:.2f}亿元，阈值={threshold/1e4:.0f}万元({threshold:,.0f}元)")
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000

def filter_global_pool_by_volume(context):
    log.info("【全球池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        log.info("【全球池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.global_etf_pool:
        log.info("【全球池过滤】全球池为空，跳过过滤")
        g.filtered_global_pool = []
        return
    dynamic_threshold = g.avg_etf_money_threshold
    log.info(f"【全球池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.global_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【全球池过滤】无法获取成交额数据，使用原始全球池")
            g.filtered_global_pool = g.global_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_global_pool = qualified.index.tolist()
        removed = set(g.global_etf_pool) - set(new_global_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            log.info(f"【全球池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_global_pool = new_global_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        log.info(f"【全球池过滤】保留高流动性ETF({len(new_global_pool)}只)")
    except Exception as e:
        log.warning(f"【全球池过滤】异常: {e}")
        g.filtered_global_pool = g.global_etf_pool[:]

def update_sector_pool(context):
    log.info("【动态池更新】开始执行")
    if g.avg_etf_money_threshold is None:
        log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    
    FUND_COMPANIES = sorted(list(set([
        '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华', '南方', '汇添富', '国泰', '平安',
        '银华', '天弘', '建信', '工银', '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
        '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银', '东方红', '财通', '华商',
        '国联', '永赢', '金鹰', '德邦', '创金合信', '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海',
        '华润元大', '大成', '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城', '中金', '浙商证券',
        '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航', '中融', '中邮', '中庚', '中信保诚', '中信建投',
        '中银国际', '中银证券', '九泰', '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林',
        '国联安', '国金', '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛', '长江证券', '鹏扬'
    ])), key=len, reverse=True)
    
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)
    
    SPECIAL_GROUPS = sorted([
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS科技'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创', '债券', '债汇', '债指', '债沪', '债易', '债基', '债兴', '债摩', '债', 'AAA'], key=len, reverse=True)},
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)
    
    exclude_keywords = sorted(list(set([
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ])), key=len, reverse=True)
    
    try:
        df_etf = get_all_securities(['etf'])
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"获取全市场ETF列表失败: {e}")
        return
    
    log.info(f"【动态池更新】全市场ETF总数: {len(etf_list)}只")
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0
    
    for code in etf_list:
        try:
            name = g.etf_names_dict.get(code, str(code))
            is_special = False
            matched_group = None
            for group in SPECIAL_GROUPS:
                for kw in group['keywords']:
                    if kw in name:
                        is_special = True
                        matched_group = group['name']
                        break
                if is_special:
                    break
            is_excluded = False
            for k in exclude_keywords:
                if k in name:
                    is_excluded = True
                    excluded_count += 1
                    break
            if not is_excluded:
                if is_special:
                    special_etfs.append(code)
                    special_group_map[code] = matched_group
                else:
                    normal_etfs.append(code)
        except Exception:
            continue
    
    group_counts = {}
    for code in special_etfs:
        group_name = special_group_map.get(code, '未知')
        group_counts[group_name] = group_counts.get(group_name, 0) + 1
    log.info(f"【动态池更新】特别组分布: {group_counts}")
    log.info(f"【动态池更新】进入特别组: {len(special_etfs)}只")
    log.info(f"【动态池更新】进入普通组: {len(normal_etfs)}只")
    log.info(f"【动态池更新】排除ETF: {excluded_count}只")
    
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold
    
    def filter_by_liquidity(etf_codes, group_name):
        if not etf_codes:
            return pd.Series(dtype=float), 0
        try:
            price_data = get_price(etf_codes, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                return pd.Series(dtype=float), len(etf_codes)
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            qualified_series = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
            filtered_out = len(etf_codes) - len(qualified_series)
            return qualified_series, filtered_out
        except Exception:
            return pd.Series(dtype=float), len(etf_codes)
    
    normal_qualified, normal_filtered_out = filter_by_liquidity(normal_etfs, "普通组")
    special_qualified, special_filtered_out = filter_by_liquidity(special_etfs, "特别组")
    normal_sorted = normal_qualified.index.tolist()
    special_sorted = special_qualified.index.tolist()
    log.info(f"【动态池更新】特别组流动性过滤: {len(special_etfs)}→{len(special_sorted)}只")    
    log.info(f"【动态池更新】普通组流动性过滤: {len(normal_etfs)}→{len(normal_sorted)}只")
    
    if not normal_sorted and not special_sorted:
        log.warning("【动态池更新】无ETF通过流动性过滤")
        g.dynamic_etf_pool = []
        return
    
    def get_remove_words_for_etf(_, is_special, matched_group_name):
        if not is_special:
            return []
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                return group['remove_words']
        return []
    
    def clean_name(original_name, is_special=False, matched_group_name=None):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        if is_special and matched_group_name:
            for word in get_remove_words_for_etf(original_name, is_special, matched_group_name):
                cleaned = cleaned.replace(word, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()
    
    normal_industry_groups = {}
    for code in normal_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            money = normal_qualified[code]
            cleaned = clean_name(original_name, is_special=False)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            if industry_key not in normal_industry_groups:
                normal_industry_groups[industry_key] = []
            normal_industry_groups[industry_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': '普通'
            })
        except Exception:
            continue
    
    special_industry_groups = {}
    for code in special_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified[code]
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = f"{matched_group}_{industry_key}"
            if group_key not in special_industry_groups:
                special_industry_groups[group_key] = []
            special_industry_groups[group_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': matched_group, 'display_group': matched_group
            })
        except Exception:
            continue
    
    final_pool_info = []
    for industry_key, items in normal_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    for group_key, items in special_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    
    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    _top_n = getattr(g, 'dynamic_pool_top_n', 100)
    top_100 = final_pool_info_sorted[:_top_n]
    g.dynamic_etf_pool = [item['code'] for item in top_100]
    log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF")
    if len(g.dynamic_etf_pool) <= 10:
        for item in top_100[:10]:
            log.info(f"  {item['code']} {item['original_name']} 日均成交额: {item['money']/1e8:.2f}亿")

def filter_fixed_pool_by_volume(context):
    log.info("【固定池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        log.info("【固定池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.fixed_etf_pool:
        log.info("【固定池过滤】固定池为空，跳过过滤")
        return
    dynamic_threshold = g.avg_etf_money_threshold
    log.info(f"【固定池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.fixed_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【固定池过滤】无法获取成交额数据，跳过过滤")
            g.filtered_fixed_pool = g.fixed_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_fixed_pool = qualified.index.tolist()
        removed = set(g.fixed_etf_pool) - set(new_fixed_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            log.info(f"【固定池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_fixed_pool = new_fixed_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        log.info(f"【固定池过滤】保留高流动性ETF({len(new_fixed_pool)}只)")
    except Exception as e:
        log.warning(f"【固定池过滤】异常: {e}")
        g.filtered_fixed_pool = g.fixed_etf_pool[:]

def daily_merge_etf_pools(context):
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    log.info("【合并ETF池】开始执行")
    log.info(f"【合并池统计】固定池: {len(g.filtered_fixed_pool)}只, 动态池: {len(g.dynamic_etf_pool)}只, 合并后: {len(merged)}只")
    g.merged_etf_pool = merged
# ==================== S2 动量计算与排名函数 ====================
def calculate_and_log_ranked_etfs(context):
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list

def calculate_momentum_score(price_series, lookback_days):
    if len(price_series) < lookback_days + 1:
        return None, None, None
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2
    W_sum = np.sum(W)
    x_bar = np.sum(W * x) / W_sum
    y_bar = np.sum(W * y) / W_sum
    dx = x - x_bar
    dy = y - y_bar
    variance_x = np.sum(W * dx**2)
    if variance_x == 0:
        return 0, 0, 0
    slope = np.sum(W * dx * dy) / variance_x
    intercept = y_bar - slope * x_bar
    annualized_returns = math.exp(slope * 250) - 1
    y_pred = slope * x + intercept
    ss_res = np.sum(weights * (y - y_pred) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2) 
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    momentum_score = annualized_returns * r_squared
    return momentum_score, annualized_returns, r_squared

def get_series_ending_at(hist_closes, current_price, offset):
    hist = np.asarray(hist_closes, dtype=float)
    if offset == 0:
        return np.append(hist, float(current_price))
    cut = offset - 1
    if cut == 0:
        return hist
    if len(hist) <= cut:
        return None
    return hist[:-cut]

def get_historical_volume_ratio(hist_volumes, offset, lookback_days):
    try:
        vols = np.asarray(hist_volumes, dtype=float)
        idx = len(vols) - offset
        if idx <= 0 or idx >= len(vols):
            return None
        start = idx - lookback_days
        if start < 0:
            return None
        base = vols[start:idx]
        if len(base) < lookback_days or np.any(base <= 0) or np.any(np.isnan(base)):
            return None
        avg = np.mean(base)
        return vols[idx] / avg if avg > 0 else None
    except Exception:
        return None

def evaluate_super_mainline(hist_closes, hist_volumes, current_price, current_volume_ratio):
    if not getattr(g, 'enable_super_mainline', False):
        return False, {'reason': 'disabled'}
    days = int(getattr(g, 'mainline_days', 5))
    if hist_closes is None or hist_volumes is None:
        return False, {'reason': 'no_hist'}
    scores = []
    r2_values = []
    volume_ratios = []
    laplace_slopes = []
    for offset in range(days - 1, -1, -1):
        series = get_series_ending_at(hist_closes, current_price, offset)
        if series is None or len(series) < int(g.lookback_days * 0.8):
            return False, {'reason': f'series_short@offset{offset}'}
        score, _, r2 = calculate_momentum_score(series, g.lookback_days)
        if score is None or r2 is None or pd.isna(score) or pd.isna(r2):
            return False, {'reason': f'score_nan@offset{offset}'}
        scores.append(score)
        r2_values.append(r2)
        try:
            lap_values = laplace_filter(series, s=g.laplace_s_param)
            lap_slope = lap_values[-1] - lap_values[-2] if len(lap_values) >= 2 else 0
        except Exception:
            lap_slope = 0
        laplace_slopes.append(lap_slope)
        if offset == 0:
            volume_ratios.append(current_volume_ratio)
        else:
            volume_ratios.append(get_historical_volume_ratio(hist_volumes, offset, g.volume_lookback))
    vr_dump = []
    valid_vrs = []
    for v in volume_ratios:
        if v is None:
            vr_dump.append('None')
        elif pd.isna(v):
            vr_dump.append('NaN')
        else:
            vr_dump.append(f'{float(v):.2f}')
            valid_vrs.append(float(v))
    hist_vol_len = len(hist_volumes) if hist_volumes is not None else 0
    has_missing = len(valid_vrs) < len(volume_ratios)
    if has_missing:
        if len(valid_vrs) < 3:
            current_score = scores[-1] if scores else 0
            current_r2 = r2_values[-1] if r2_values else 0
            return False, {
                'reason': 'volume_none',
                'vr_dump': vr_dump,
                'hist_vol_len': hist_vol_len,
                'scores': scores, 'r2_values': r2_values,
                'volume_ratios': [None if v is None or pd.isna(v) else float(v) for v in volume_ratios],
                'laplace_slopes': laplace_slopes,
                'current_score': current_score, 'current_r2': current_r2,
                'r2_avg': float(np.mean(r2_values)) if r2_values else 0,
                'volume_avg': float(np.mean(valid_vrs)) if valid_vrs else 0,
                'score_up_days': sum(1 for i in range(1, len(scores)) if scores[i] >= scores[i - 1]),
                'positive_laplace_days': sum(1 for v in laplace_slopes if v > 0),
            }
        fallback_v = float(np.mean(valid_vrs))
        volume_ratios = [fallback_v if (v is None or pd.isna(v)) else float(v) for v in volume_ratios]
    current_score = scores[-1]
    current_r2 = r2_values[-1]
    r2_avg = float(np.mean(r2_values))
    volume_avg = float(np.mean(volume_ratios))
    score_up_days = sum(1 for i in range(1, len(scores)) if scores[i] >= scores[i - 1])
    positive_laplace_days = sum(1 for v in laplace_slopes if v > 0)
    start_score = scores[0]
    if start_score > 0:
        score_growth = current_score / start_score
    else:
        score_growth = float('inf') if current_score > 0 else 0
    fails = []
    if not (g.mainline_score_min < current_score <= g.mainline_score_max):
        fails.append('score_range')
    if current_r2 < g.mainline_min_r2:
        fails.append('r2_cur')
    if r2_avg < g.mainline_min_r2_avg:
        fails.append('r2_avg')
    if volume_avg < g.mainline_min_volume_avg:
        fails.append('vol_avg')
    if score_up_days < g.mainline_min_score_up_days:
        fails.append('score_up')
    if positive_laplace_days < g.mainline_min_positive_laplace_days:
        fails.append('lap_pos')
    if score_growth < g.mainline_min_score_growth:
        fails.append('score_growth')
    passed = not fails
    reason_str = 'pass' if passed else '+'.join(fails)
    if has_missing and passed:
        reason_str = f'pass(vr_filled@{vr_dump.count("None") + vr_dump.count("NaN")})'
    return passed, {
        'scores': scores,
        'r2_values': r2_values,
        'volume_ratios': volume_ratios,
        'laplace_slopes': laplace_slopes,
        'current_score': current_score,
        'current_r2': current_r2,
        'r2_avg': r2_avg,
        'volume_avg': volume_avg,
        'score_up_days': score_up_days,
        'positive_laplace_days': positive_laplace_days,
        'score_growth': score_growth,
        'vr_dump': vr_dump,
        'hist_vol_len': hist_vol_len,
        'reason': reason_str,
    }

def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    try:
        price_series = np.append(hist_closes, current_price)
        mom_lb = g.lookback_days
        if g.is_a_share_weak and getattr(g, "enable_dynamic_weak_lookback", False):
            mom_lb = g.weak_momentum_lookback
        if len(price_series) < mom_lb * 0.8:
            return None
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_series, mom_lb)
        if momentum_score is None:
            return None
        passed_momentum = (g.min_score_threshold <= momentum_score <= g.max_score_threshold)
        volume_ratio = get_volume_ratio(hist_volumes, today_vol, context, g.volume_lookback)
        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False
        passed_r2 = r_squared > g.r2_threshold
        passed_ma = True
        ma_value = None
        if len(price_series) >= g.ma_lookback:
            ma_value = np.mean(price_series[-g.ma_lookback:])
            passed_ma = current_price > ma_value * g.ma_threshold
        else:
            passed_ma = False
        premium_rate, passed_premium = calculate_premium_rate(etf, context)
        laplace_value = 0
        laplace_slope = 0
        passed_laplace = False
        if len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                if len(laplace_values) >= 2:
                    laplace_value = laplace_values[-1]
                    laplace_slope = laplace_values[-1] - laplace_values[-2]
                    passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
            except Exception:
                pass
        passed_mainline, mainline_info = evaluate_super_mainline(hist_closes, hist_volumes, current_price, volume_ratio)
        passed_volume_divergence, vd_info = check_volume_price_divergence(hist_closes, hist_volumes, context)
        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'premium_rate': premium_rate,
            'passed_momentum': passed_momentum,
            'passed_r2': passed_r2,
            'passed_ma': passed_ma,
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'passed_premium': passed_premium,
            'ma_value': ma_value,
            'laplace_value': laplace_value,
            'laplace_slope': laplace_slope,
            'passed_laplace': passed_laplace,
            'passed_mainline': passed_mainline,
            'mainline_info': mainline_info,
            'passed_volume_divergence': passed_volume_divergence,
            'vd_info': vd_info,
        }
    except Exception as e:
        log.debug(f"【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None

def get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
    if lookback_days is None:
        lookback_days = g.volume_lookback
    try:
        if hist_volumes is None or len(hist_volumes) < lookback_days:
            return None
        past_n_days_vol = hist_volumes[-lookback_days:]
        if np.any(np.isnan(past_n_days_vol)) or np.any(past_n_days_vol == 0):
            return None
        avg_volume = np.mean(past_n_days_vol)
        if avg_volume == 0:
            return None
        now = context.current_dt
        elapsed_minutes = (now.hour - 9) * 60 + now.minute - 30
        if now.hour >= 13:
            elapsed_minutes -= 90
        elapsed_minutes = max(1, min(elapsed_minutes, 240))
        projected_today_vol = today_vol * (240.0 / elapsed_minutes)
        return projected_today_vol / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None

def calculate_premium_rate(etf, context):
    try:
        etf_price = getattr(g, 'etf_yesterday_close_batch', {}).get(etf)
        if etf_price is None or pd.isna(etf_price):
            etf_price_df = get_price(etf, start_date=context.previous_date, end_date=context.previous_date, fields=['close'])
            if etf_price_df is None or len(etf_price_df) == 0:
                return None, False
            etf_price = etf_price_df['close'].iloc[-1]
        nav = getattr(g, 'etf_yesterday_nav_batch', {}).get(etf)
        if nav is None or pd.isna(nav):
            nav_df = get_extras('unit_net_value', etf, start_date=context.previous_date, end_date=context.previous_date)
            if nav_df is None or len(nav_df) == 0:
                return None, False
            nav = nav_df.iloc[-1].values[0]
        if nav <= 0 or pd.isna(nav):
            return None, False
        premium_rate = (etf_price - nav) / nav * 100
        passed_premium = premium_rate <= g.max_premium_rate
        return premium_rate, passed_premium
    except Exception as e:
        return None, True

def laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L

def _compute_hs300_breadth(context):
    try:
        stocks = get_index_stocks('000300.XSHG', date=context.previous_date)
        if not stocks:
            return None
        stocks = list(stocks)
        w = int(getattr(g, 'regime_breadth_ma', 20))
        df = get_price(
            stocks,
            end_date=context.previous_date,
            count=w,
            frequency='daily',
            fields=['close'],
            panel=False,
            skip_paused=True,
        )
        if df is None or len(df) == 0:
            return None
        cur = get_current_data()
        above = 0
        total = 0
        for code in stocks:
            sub = df[df['code'] == code] if 'code' in df.columns else df[df.index == code]
            if sub is None or len(sub) < w:
                continue
            closes = sub['close'].values if 'close' in sub.columns else sub.values
            if len(closes) < w:
                continue
            ma = float(np.mean(closes[-w:]))
            px = cur[code].last_price if code in cur else float(closes[-1])
            if px is None or pd.isna(px) or ma <= 0:
                continue
            total += 1
            if px > ma:
                above += 1
        if total < 50:
            return None
        return float(above) / float(total)
    except Exception as e:
        log.debug(f"[RegimeP0] breadth error: {e}")
        return None

def _compute_market_liquidity_yi(context):
    try:
        lb = int(getattr(g, 'regime_liquidity_lookback', 20))
        idx = ['000001.XSHG', '399001.XSHE']
        df = get_price(
            idx,
            end_date=context.previous_date,
            count=lb,
            frequency='daily',
            fields=['money'],
            panel=False,
            skip_paused=True,
        )
        if df is None or len(df) == 0:
            return None
        if 'time' in df.columns:
            daily = df.groupby('time')['money'].sum()
        else:
            daily = df['money']
        if len(daily) == 0:
            return None
        return float(daily.mean()) / 1e8
    except Exception as e:
        log.debug(f"[RegimeP0] liquidity error: {e}")
        return None

def _compute_trend_votes(context):
    indexes = {
        '大盘': '000300.XSHG',
        '小盘': '399101.XSHE',
        '创业板': '399006.XSHE',
        '中证A500': '000510.XSHG',
    }
    above_count = 0
    below_count = 0
    for name, code in indexes.items():
        df = attribute_history(code, g.weak_period_ma_lookback + 1, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < g.weak_period_ma_lookback:
            continue
        current_price = df['close'][-1]
        ma_val = df['close'][-g.weak_period_ma_lookback:].mean()
        if current_price > ma_val:
            above_count += 1
        elif current_price < ma_val:
            below_count += 1
    return above_count, below_count

def _classify_regime_p0(above_count, below_count, breadth, liquidity_yi):
    liq_min = float(getattr(g, 'regime_liquidity_min_yi', 20000.0))
    b_high = float(getattr(g, 'regime_breadth_high', 0.55))
    b_struct = float(getattr(g, 'regime_breadth_structural', 0.50))
    b_low = float(getattr(g, 'regime_breadth_low', 0.35))
    liquidity_ok = liquidity_yi is not None and liquidity_yi >= liq_min
    trend_ok = above_count >= 2
    trend_weak = below_count >= 3
    if breadth is not None and breadth < b_low:
        return 'DEFENSIVE', 2
    if not liquidity_ok:
        return 'DEFENSIVE', 2
    if trend_ok or (breadth is not None and breadth >= b_high):
        return 'NORMAL', 0
    if trend_weak and breadth is not None and breadth >= b_struct:
        return 'STRUCTURAL', 1
    if trend_weak and breadth is not None and breadth < b_low:
        return 'DEFENSIVE', 2
    return 'NORMAL', 0

def compute_regime_p0_daily(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    if not getattr(g, 'enable_regime_p0', False):
        return
    above_count, below_count = _compute_trend_votes(context)
    breadth = _compute_hs300_breadth(context)
    liquidity_yi = _compute_market_liquidity_yi(context)
    regime_name, regime_code = _classify_regime_p0(above_count, below_count, breadth, liquidity_yi)
    legacy_weak = bool(getattr(g, 'is_a_share_weak', False))
    mismatch = legacy_weak and regime_name in ('NORMAL', 'STRUCTURAL')
    entry = {
        'date': context.current_dt.strftime('%Y-%m-%d'),
        'regime': regime_name,
        'regime_code': regime_code,
        'breadth': None if breadth is None else round(breadth, 4),
        'liquidity_yi': None if liquidity_yi is None else round(liquidity_yi, 1),
        'trend_above': above_count,
        'trend_below': below_count,
        'legacy_weak': int(legacy_weak),
        'legacy_mismatch': int(mismatch),
    }
    g.regime_p0_log.append(entry)
    log.info(f"[REGIME_P0] {json.dumps(entry, ensure_ascii=False)}")
    log.info(f"📊 【RegimeP0】{regime_name} | 宽度={entry['breadth']} 流动性={entry['liquidity_yi']}亿 | 趋势 上/下={above_count}/{below_count} | 原走弱期={legacy_weak} | 错配={'是' if mismatch else '否'}")
    record(
        regime_p0=regime_code,
        breadth_p0=0.0 if breadth is None else float(breadth),
        liquidity_p0=0.0 if liquidity_yi is None else float(liquidity_yi),
        trend_below_p0=float(below_count),
        legacy_weak_p0=1.0 if legacy_weak else 0.0,
        regime_mismatch_p0=1.0 if mismatch else 0.0,
    )

def check_a_share_weak_period(context):
    today = context.current_dt.date()
    indexes = {
        '大盘': '000300.XSHG',
        '小盘': '399101.XSHE',
        '创业板': '399006.XSHE',
        '中证A500': '000510.XSHG'
    }
    above_count = 0
    below_count = 0
    for name, code in indexes.items():
        df = attribute_history(code, g.weak_period_ma_lookback + 1, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < g.weak_period_ma_lookback:
            log.warning(f"📊 【走弱期判断】{name}({code})数据不足，跳过该指数")
            continue
        current_price = df['close'][-1]
        ma_val = df['close'][-g.weak_period_ma_lookback:].mean()
        is_above = current_price > ma_val
        is_below = current_price < ma_val
        if is_above:
            above_count += 1
        if is_below:
            below_count += 1
        status_emoji = "⬆️站上" if is_above else ("⬇️低于" if is_below else "➡️持平")
        log.info(f"📊 【走弱期判断】{name}({code}): 收盘{current_price:.2f} / MA{g.weak_period_ma_lookback} {ma_val:.2f} → {status_emoji}")
    weak_condition_met = (below_count >= 3)
    exit_condition_met = (above_count >= 3)
    log.info(f"📊 【走弱期判断】低于MA{g.weak_period_ma_lookback}: {below_count}/4, 站上MA{g.weak_period_ma_lookback}: {above_count}/4")
    if g.is_a_share_weak and g.weak_start_date is not None:
        g.weak_days_count = len(get_trade_days(start_date=g.weak_start_date, end_date=today))
    else:
        g.weak_days_count = 0
    max_days_exceeded = (g.weak_days_count >= g.max_weak_days)
    if g.is_a_share_weak:
        if max_days_exceeded:
            log.info(f"🔔 【走弱期退出】已达到最大持续天数{g.max_weak_days}个交易日，强制退出")
            g.is_a_share_weak = False
            g.weak_start_date = None
            g.weak_days_count = 0
        elif exit_condition_met:
            log.info(f"🟢 【走弱期退出】满足退出条件，退出走弱期")
            g.is_a_share_weak = False
            g.weak_start_date = None
            g.weak_days_count = 0
        elif weak_condition_met:
            g.weak_start_date = today
            g.weak_days_count = 0
            log.info(f"🟡 【走弱期延续】再次触发进入条件，重置计数器")
        else:
            log.info(f"🔴 【走弱期中】已持续{g.weak_days_count}/{g.max_weak_days}个交易日")
    else:
        if weak_condition_met:
            log.info(f"🔴 【走弱期进入】触发进入条件，进入大A走弱期")
            g.is_a_share_weak = True
            g.weak_start_date = today
            g.weak_days_count = 0
        else:
            log.info(f"🟢 【正常期中】未满足进入条件")
    status_emoji = "🔴" if g.is_a_share_weak else "🟢"
    status_str = f"{status_emoji} 最终状态: 走弱期={g.is_a_share_weak}"
    if g.is_a_share_weak:
        status_str += f" (已持续{g.weak_days_count}/{g.max_weak_days}个交易日)"
        record(走弱期状态=1)
    else:
        record(走弱期状态=0)
    log.info(f"📊 【走弱期判断】{status_str}")
    if getattr(g, "enable_dynamic_weak_lookback", False):
        adjust_weak_momentum_lookback(context)
    return g.is_a_share_weak

def apply_filters(metrics_list):
    if g.is_a_share_weak:
        steps = [
            ('动量得分', lambda m: m['passed_momentum'], True),
            ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
        ]
    else:
        steps = [
            ('动量得分', lambda m: m['passed_momentum'], True),
            ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
            ('均线', lambda m: m['passed_ma'], g.enable_ma_filter),
            ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
            ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
            ('溢价率', lambda m: m['passed_premium'], g.enable_premium_filter),
            ('拉普拉斯滤波', lambda m: m['passed_laplace'], g.enable_laplace_filter),
            ('量价背离', lambda m: m.get('passed_volume_divergence', True),
             g.enable_volume_divergence_filter and g.is_choppy),
        ]
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered

def get_final_ranked_etfs(context):
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = context.previous_date
    log.info(f"【动量得分计算】使用合并池，合计{len(etf_set)}只ETF")
    log.info(f"【当前状态】{'🔴 大A走弱期' if g.is_a_share_weak else '🟢 大A正常期'}")
    mom_lb = g.weak_momentum_lookback if (
        g.is_a_share_weak and getattr(g, "enable_dynamic_weak_lookback", False)
    ) else g.lookback_days
    lookback = max(mom_lb, g.volume_lookback, g.ma_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
    safe_lookback = lookback + 20
    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        log.warning("【动量计算】无法获取历史价格数据")
        return []
    g.etf_yesterday_close_batch = {}
    g.etf_yesterday_nav_batch = {}
    try:
        y_price_df = get_price(etf_set, start_date=end_date, end_date=end_date, fields=['close'], panel=False)
        if y_price_df is not None and not y_price_df.empty:
            g.etf_yesterday_close_batch = y_price_df.groupby('code')['close'].last().to_dict()
        nav_df = get_extras('unit_net_value', etf_set, start_date=end_date, end_date=end_date)
        if nav_df is not None and not nav_df.empty:
            g.etf_yesterday_nav_batch = nav_df.iloc[-1].to_dict()
    except Exception as e:
        log.warning(f"【动量计算】批量获取溢价率数据异常: {e}")
    today_vols = today_vol_df.groupby('code')['volume'].sum() if (today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)
    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')
    for etf in etf_set:
        if current_data[etf].paused:
            continue
        if etf not in close_pivot.columns:
            continue
        raw_closes = close_pivot[etf].values
        raw_volumes = volume_pivot[etf].values
        valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
        hist_closes = raw_closes[valid_mask]
        hist_volumes = raw_volumes[valid_mask]
        hist_closes = hist_closes[-lookback:]
        hist_volumes = hist_volumes[-lookback:]
        if len(hist_closes) < g.lookback_days:
            continue
        etf_name = get_security_name(etf)
        current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        metrics = calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
    all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    log_buffer = []
    log_buffer.append("")
    log_buffer.append(">>> 第一步：所有ETF按动量得分从大到小排序 <<<")
    for m in all_metrics[:100]:
        def fmt_status(value_str, passed):
            return f"{value_str} {'✅' if passed else '❌'}"
        score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
        r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
        vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
        min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
        loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
        premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
        ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
        line = (
            f"{m['etf']} {m['etf_name']}: "
            f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
            f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
            f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
            f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
            f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
            f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
            f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}，"
            f"B型主线: {'✅' if m.get('passed_mainline') else '❌'}，"
            f"量价背离: {'✅' if m.get('passed_volume_divergence', True) else '❌'}"
        )
        log_buffer.append(line)
        if getattr(g, 'enable_super_mainline', False) and m.get('momentum_score', 0) > g.mainline_score_min:
            info = m.get('mainline_info', {}) or {}
            if info:
                line_d = (
                    f"    [主线诊断 {m['etf']}] reason={info.get('reason', 'n/a')} | "
                    f"score_cur={info.get('current_score', 0):.2f} "
                    f"r2_cur={info.get('current_r2', 0):.3f} "
                    f"r2_avg={info.get('r2_avg', 0):.3f} "
                    f"vol_avg={info.get('volume_avg', 0):.2f} "
                    f"up={info.get('score_up_days', 0)}/{g.mainline_days-1} "
                    f"lap+={info.get('positive_laplace_days', 0)}/{g.mainline_days} "
                    f"score_growth={info.get('score_growth', 0):.2f}"
                )
                vr_dump = info.get('vr_dump')
                if vr_dump:
                    line_d += f" | vr_list=[{', '.join(vr_dump)}] hist_vol_len={info.get('hist_vol_len', '?')}"
                log_buffer.append(line_d)
            else:
                log_buffer.append(f"    [主线诊断 {m['etf']}] info 为空 (评估提前返回)")
    filtered_list = apply_filters(all_metrics)
    if getattr(g, 'enable_super_mainline', False):
        normal_codes = {m['etf'] for m in filtered_list}
        mainline_list = [
            m for m in all_metrics
            if m.get('passed_mainline')
            and m['etf'] not in normal_codes
            and (not g.enable_loss_filter or m['passed_loss'])
            and (not g.enable_premium_filter or m['passed_premium'])
            and (not (g.enable_ma_filter and g.is_a_share_weak) or m['passed_ma'])
        ]
        filtered_list = filtered_list + mainline_list
        log_buffer.append("")
        log_buffer.append(
            f">>> B型阶梯主线：score在({g.mainline_score_min},{g.mainline_score_max}]且满足阶梯主线条件的ETF {len(mainline_list)}只 <<<"
        )
        for m in mainline_list[:15]:
            info = m.get('mainline_info', {})
            log_buffer.append(
                f"  {m['etf']} {m['etf_name']}: score={m['momentum_score']:.4f}, "
                f"R²当前={info.get('current_r2', 0):.3f}, R²均值={info.get('r2_avg', 0):.3f}, "
                f"量比均值={info.get('volume_avg', 0):.2f}, "
                f"score抬升={info.get('score_up_days', 0)}/{g.mainline_days-1}, "
                f"拉普拉斯正={info.get('positive_laplace_days', 0)}/{g.mainline_days}, "
                f"score增长={info.get('score_growth', 0):.2f}倍"
            )
        retain_list = []
        if getattr(g, 'enable_mainline_retain', True):
            held_codes_set = {sec for sec in g.accounts[SID_S2]['holdings']}
            already_codes = {m['etf'] for m in filtered_list}
            for m in all_metrics:
                if m['etf'] not in held_codes_set:
                    continue
                if m['etf'] in already_codes:
                    continue
                score_val = m.get('momentum_score', 0)
                if score_val is None or pd.isna(score_val):
                    continue
                if score_val <= g.mainline_score_max:
                    continue
                r2_val = m.get('r_squared')
                lap_slope = m.get('laplace_slope', 0)
                if r2_val is None or pd.isna(r2_val) or r2_val < g.mainline_retain_min_r2:
                    continue
                if lap_slope is None or pd.isna(lap_slope) or lap_slope <= g.mainline_retain_min_lap_slope:
                    continue
                if g.enable_loss_filter and not m['passed_loss']:
                    continue
                if g.enable_premium_filter and not m['passed_premium']:
                    continue
                if g.enable_ma_filter and g.is_a_share_weak and not m['passed_ma']:
                    continue
                retain_list.append(m)
            if retain_list:
                for m in retain_list:
                    m['mainline_retained'] = True
                filtered_list = filtered_list + retain_list
                log_buffer.append("")
                log_buffer.append(
                    f">>> B型主线持仓延续：当前持仓中 score 已突破{g.mainline_score_max}但趋势品质仍达标的ETF {len(retain_list)}只 <<<"
                )
                for m in retain_list:
                    log_buffer.append(
                        f"  {m['etf']} {m['etf_name']}: score={m['momentum_score']:.4f}, "
                        f"R²={m['r_squared']:.3f}, 拉普拉斯斜率={m['laplace_slope']:.4f} "
                        f"→ 持仓延续保留"
                    )
    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    top_10 = filtered_list[:10]
    log_buffer.append("")
    log_buffer.append(">>> 第二步：符合全部过滤条件的ETF按动量得分从大到小排序(前10名) <<<")
    if top_10:
        for m in top_10:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
            ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
                f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
                f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}，"
                f"B型主线: {'✅' if m.get('passed_mainline') else '❌'}，"
                f"量价背离: {'✅' if m.get('passed_volume_divergence', True) else '❌'}"
            )
            log_buffer.append(line)
    else:
        log_buffer.append("（无符合条件的ETF）")
        full_log = "\n".join(log_buffer)
        log.info(full_log)
        return []
    score_key = 'momentum_score'
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        ratio = g.score_threshold_ratio if not g.is_a_share_weak else 1.0
        score_threshold = reference_score * ratio
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：选取动量得分≥第{g.holdings_num}名({top_10[g.holdings_num - 1]['etf_name']})得分{reference_score:.4f}×{g.score_threshold_ratio}={score_threshold:.4f}的ETF <<<")
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<")
        candidate_pool = top_10[:]
    log_buffer.append(f"【候选池】共{len(candidate_pool)}只ETF（按动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        if item.get('mainline_retained'):
            tag = " [主线延续]"
        elif item.get('passed_mainline'):
            tag = " [B型主线]"
        else:
            tag = ""
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}{tag}")
    log_buffer.append("")
    log_buffer.append(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = list(g.accounts[SID_S2]['holdings'])
    log_buffer.append(f"当前S2持仓ETF：{current_holdings}")
    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    log_buffer.append(f"其中存在于候选池中的持仓ETF：{[item['etf'] for item in retained]}")
    if len(retained) >= g.holdings_num:
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
        log_buffer.append(f"保留的持仓ETF数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的ETF中按动量得分取前{g.holdings_num}只作为最终目标。")
    else:
        need = g.holdings_num - len(retained)
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        additional = remaining_pool[:need]
        final_result = retained + additional
        log_buffer.append(f"保留持仓ETF {len(retained)}只，还需补充{need}只。")
        if retained:
            log_buffer.append("保留的ETF（按原有顺序）：")
            for item in retained:
                log_buffer.append(f"  {item['etf_name']}({item['etf']})")
        if additional:
            log_buffer.append("补充的ETF（按动量得分排序）：")
            for i, item in enumerate(additional):
                if item.get('mainline_retained'):
                    tag = " [主线延续]"
                elif item.get('passed_mainline'):
                    tag = " [B型主线]"
                else:
                    tag = ""
                log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}{tag}")
    log_buffer.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        if item.get('mainline_retained'):
            tag = " [主线延续]"
        elif item.get('passed_mainline'):
            tag = " [B型主线]"
        else:
            tag = ""
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}){tag}")
    log_buffer.append("==================================================")
    full_log = "\n".join(log_buffer)
    log.info(full_log)
    return final_result

# ==================== S2 交易执行函数 ====================
def execute_sell_trades(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    log.info("========== 卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    target_etfs = []
    
    if ranked_etfs:
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}")
    else:
        # 无目标ETF时直接空仓，不买入防御性ETF
        log.info("💤 无最终目标，保持空仓（不买入防御ETF）")
        target_etfs = []
    
    g.target_etfs_list = target_etfs
    target_set = set(target_etfs)
    for security in list(g.accounts[SID_S2]['holdings']):
        position = context.portfolio.positions.get(security)
        if position and position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            success = smart_order_target_value(security, 0, context)
            if success:
                log.info(f"✅ 已成功卖出: {security} {security_name}")
    log.info("========== 卖出操作完成 ==========")

def execute_buy_trades(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    log.info("========== 买入操作开始（择时趋势判断）==========")
    g.pending_buy_etfs = []
    target_etfs = g.target_etfs_list
    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return
    current_positions = set(g.accounts[SID_S2]['holdings'])
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("========== 买入操作完成 ==========")
        return
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标持仓: {g.holdings_num}只, 本次计划买入: {num_etfs_to_buy}只")
    g.pending_buy_etfs = list(etfs_to_buy)
    log.info(f"计划买入ETF: {g.pending_buy_etfs}，先进行13:10趋势判断；若不满足，将在13:40/14:10/14:40复检，14:55强制买入")
    execute_buy_with_trend(context, force=False)
    if g.pending_buy_etfs:
        log.info(f"⏳ 等待趋势确认的ETF: {g.pending_buy_etfs}")
    log.info("========== 买入操作完成（择时趋势判断）==========")

def check_intraday_trend(security, context):
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
            log.info(f"【趋势判断】{security} 无分钟数据，默认上涨趋势")
            return True
        closes = minute_data['close'].values
        closes = closes[closes > 0]
        if len(closes) < 5:
            log.info(f"【趋势判断】{security} 有效分钟数据不足({len(closes)}根)，默认没有上涨趋势")
            return False
        n = len(closes)
        x = np.arange(n)
        weights = np.linspace(0.5, 2.0, n)
        w = weights / weights.sum()
        x_bar = np.sum(w * x)
        y_bar = np.sum(w * closes)
        dx = x - x_bar
        dy = closes - y_bar
        variance_x = np.sum(w * dx**2)
        if variance_x == 0:
            slope = 0
        else:
            slope = np.sum(w * dx * dy) / variance_x
        mean_price = y_bar if y_bar > 0 else closes.mean()
        slope_pct = slope / mean_price * 100 if mean_price > 0 else 0
        y_pred = slope * x + (y_bar - slope * x_bar)
        ss_res = np.sum(w * (closes - y_pred)**2)
        ss_tot = np.sum(w * (closes - y_bar)**2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        passed_slope = slope_pct > g.trend_slope_threshold
        passed_r2 = r2 > g.trend_r2_threshold
        is_uptrend = passed_slope and passed_r2
        trend_desc = "上涨趋势确认" if is_uptrend else (
            "斜率不足" if not passed_slope else "趋势质量差(R²过低，假突破)" if not passed_r2 else "未知"
        )
        log.info(
            f"【趋势判断】{security} 最近{n}分钟 | "
            f"斜率={slope_pct:.6f}%/min(阈值{g.trend_slope_threshold}){'✓' if passed_slope else '✗'} | "
            f"R²={r2:.3f}(阈值{g.trend_r2_threshold}){'✓' if passed_r2 else '✗'} | "
            f"判定: {trend_desc}"
        )
        return is_uptrend
    except Exception as e:
        log.info(f"【趋势判断】{security} 异常: {e}，默认上涨趋势")
        return True

def execute_buy_with_trend(context, force=False):
    if g.mode == 'bottom':
        return
    if not g.pending_buy_etfs:
        return
    current_positions = set(g.accounts[SID_S2]['holdings'])
    g.pending_buy_etfs = [etf for etf in g.pending_buy_etfs if etf not in current_positions]
    if not g.pending_buy_etfs:
        return
    current_time = context.current_dt.strftime('%H:%M')
    mode_desc = "强制买入" if force else "趋势判断"
    log.info(f"========== 买入操作开始（{mode_desc} {current_time}）==========")
    etfs_to_buy_now = []
    still_pending = []
    for etf in g.pending_buy_etfs:
        etf_name = get_security_name(etf)
        if force:
            etfs_to_buy_now.append(etf)
            log.info(f"⏰ {current_time} 强制买入 {etf} {etf_name}")
        else:
            if check_intraday_trend(etf, context):
                etfs_to_buy_now.append(etf)
                log.info(f"📈 {current_time} {etf} {etf_name} 趋势上涨，立即买入")
            else:
                still_pending.append(etf)
                log.info(f"📉 {current_time} {etf} {etf_name} 趋势未确认，等待下次判断")
    total_count = len(etfs_to_buy_now) + len(still_pending)
    for i, etf in enumerate(etfs_to_buy_now):
        remaining_cash = context.portfolio.available_cash
        if remaining_cash < g.min_money:
            log.info(f"可用现金 {remaining_cash:.2f} 不足最小交易额 {g.min_money:.2f}，停止买入")
            break
        remaining_to_buy = total_count - i
        target_value_for_this_etf = remaining_cash // remaining_to_buy
        if target_value_for_this_etf < g.min_money and remaining_cash >= g.min_money:
            target_value_for_this_etf = remaining_cash
        etf_name = get_security_name(etf)
        log.info(f"为 {etf} {etf_name} 分配目标金额: {target_value_for_this_etf:.2f} 元 (剩余现金 {remaining_cash:.2f}, 总待买 {remaining_to_buy})")
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
        else:
            log.info(f"❌ ETF {etf} 下单失败")
    g.pending_buy_etfs = still_pending
    if still_pending:
        log.info(f"⏳ 仍待趋势确认的ETF: {still_pending}")
    else:
        log.info("✅ 所有待买ETF已处理完毕")
    log.info(f"========== 买入操作完成（{mode_desc}）==========")

def check_pending_buys_trend(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    if not g.pending_buy_etfs:
        return
    log.info("★" * 80)
    log.info("▶️ 【趋势复检】检查待买ETF趋势...")
    execute_buy_with_trend(context, force=False)
    if g.pending_buy_etfs:
        log.info(f"⏳ 仍在等待的ETF: {g.pending_buy_etfs}")
    log.info("⏸️ 【趋势复检】执行完毕！")

def force_buy_pending(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    if not g.pending_buy_etfs:
        return
    log.info("★" * 80)
    log.info("▶️ 【14:55强制买入】强制买入所有待买ETF...")
    execute_buy_with_trend(context, force=True)
    log.info("⏸️ 【14:55强制买入】执行完毕！")

def smart_order_target_value(security, target_value, context):
    current_data = get_current_data()
    security_name = get_security_name(security)
    if target_value > 0:
        available_cash = context.portfolio.available_cash
        if target_value > available_cash:
            target_value = available_cash
        if target_value < g.min_money:
            log.info(f"{security} {security_name}: 目标金额{target_value:.2f}小于最小交易额{g.min_money}，跳过")
            return False
    if current_data[security].paused:
        log.info(f"{security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {security_name}: 当前涨停，跳过交易")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {security_name}: 当前跌停，跳过交易")
        return False
    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {security_name}: 当前价格为0，跳过交易")
        return False
    if target_value > 0:
        order_result = open_position(context, security, target_value, SID_S2)
        if order_result:
            log.info(f"📦 买入{security} {security_name}，金额约{target_value:.2f}")
            return True
        else:
            return False
    else:
        order_result = close_position(security)
        if order_result:
            log.info(f"📤 卖出{security} {security_name}")
            return True
        else:
            return False

def minute_level_stop_loss(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    if not g.use_fixed_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    current_data = get_current_data()
    for security in list(g.accounts[SID_S2]['holdings']):
        position = context.portfolio.positions.get(security)
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 【分钟级固定止损】{security} {security_name} 触发止损，亏损: {loss_percent:.2f}%")
            smart_order_target_value(security, 0, context)

def minute_level_pct_stop_loss(context):
    ensure_container(context)
    if g.mode == 'bottom':
        return
    if not g.use_pct_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    current_data = get_current_data()
    current_date = context.current_dt.date()
    if not hasattr(g, 'cache_date') or g.cache_date != current_date:
        g.yesterday_close_cache = {}
        g.cache_date = current_date
    for security in list(g.accounts[SID_S2]['holdings']):
        position = context.portfolio.positions.get(security)
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        yesterday_close = getattr(g, 'yesterday_close_cache', {}).get(security)
        if yesterday_close is None:
            try:
                close_series = attribute_history(security, 1, '1d', ['close'], skip_paused=False)
                if len(close_series['close']) == 0:
                    continue
                yesterday_close = close_series['close'][-1]
                if yesterday_close <= 0:
                    continue
                g.yesterday_close_cache[security] = yesterday_close
            except Exception:
                continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        stop_price = yesterday_close * g.pct_stop_loss_threshold
        if current_price <= stop_price:
            security_name = get_security_name(security)
            daily_loss = (current_price / yesterday_close - 1) * 100
            log.info(f"🚨 【分钟级跌幅止损】{security} {security_name} 触发止损，当日跌幅: {daily_loss:.2f}%")
            smart_order_target_value(security, 0, context)

def get_security_name(security):
    try:
        if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"

def check_defensive_etf_available(context):
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    if current_data[defensive_etf].paused:
        log.info(f"防御性ETF {defensive_etf} 今日停牌")
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        log.info(f"防御性ETF {defensive_etf} 当前涨停")
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        log.info(f"防御性ETF {defensive_etf} 当前跌停")
        return False
    return True

# ==================== 主初始化与调度 ====================
def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001,
                              close_commission=0.0001, close_today_commission=0.0001,
                              min_commission=5), type="fund")
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    set_benchmark("510300.XSHG")

    log.info("【融合策略】动态池ETF抄底(高优先级) + 五福v7轮动(低优先级) 版本 %s", __version__)

    allocator_init(context)
    register_strategy(SID_S1, 0.5, priority=2)
    register_strategy(SID_S2, 0.5, priority=1)
    set_context(context)

    s1_init_state(context)
    s2_init_state(context)

    g.mode = 'rot'                               

    run_daily(_sync_params, time='09:30')         # S1参数同步（extras注入后）
    run_daily(s1_bottom_check, time='09:35')      # S1抄底判断+模式切换
    run_daily(morning_routine, time='09:00')      # S2晨间流水线（持仓检查/回撤/流动性阈值）
    run_daily(check_weak_period_daily, time='09:40')  # 大A走弱期判断+早盘池更新
    run_daily(compute_regime_p0_daily, time='11:30')  # 市场状态P0评估（仅record，不改交易）
    run_daily(afternoon_routine, time='13:10')    # S2午盘流水线（计算排名+卖出+买入首检）
    run_daily(check_pending_buys_trend, time='13:40')  # 待买ETF趋势复检（第1次）
    run_daily(check_pending_buys_trend, time='14:10')  # 待买ETF趋势复检（第2次）
    run_daily(check_pending_buys_trend, time='14:40')  # 待买ETF趋势复检（第3次）
    run_daily(force_buy_pending, time='14:55')    # 强制买入所有剩余待买ETF
    run_daily(reset_daily_flags, time='15:10')    # 收盘缓存重置
    run_daily(minute_level_stop_loss, time='every_bar')       # 分钟级固定比例止损
    run_daily(minute_level_pct_stop_loss, time='every_bar')   # 分钟级当日跌幅止损

def after_code_changed(context):
    pass                                         