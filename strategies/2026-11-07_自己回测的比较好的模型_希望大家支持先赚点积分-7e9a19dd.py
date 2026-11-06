# Clone from JoinQuant
# postId: 7e9a19dd94269da82d92ba622268407f
# backtestId: 16c1839fb65500f4d6ee535e43d99bb2
# title: 自己回测的比较好的模型，希望大家支持先赚点积分

# -*- coding: utf-8 -*-
# 克隆自聚宽文章：https://www.joinquant.com/post/78912
# 标题：自用【已用】稳赢轮动策略分享！不定时删除
# 作者：量化老兵
# ============================================================================
# 【V7.34L】V7.34 + 实盘日志增强（2026-09-02 实盘定稿）：收盘快照/成交回报/目标组合明细
# 【V7.34】V7.33 + 三修复（2026-09-02）：高价股过滤/ETF买入前置+动态资金/空仓防误止损
# 基底 V7.5（实盘定稿）→ V7.32(ETF通道+动态持仓) → V7.33(过热+冷却) → V7.34(修3bug)
#
# 用户两点纠正（2026-08-30）：
#   1. 行业热点变化可能发生在月中，月度识别太慢 → 每日更新 + 每周一换仓检查
#   2. 不只是弱市不空仓，强市也要跟热点行业猛干 → 所有模式选股热点优先
#
# V7.5 改动：
#   1.【热点日更】每天9:10计算申万一级行业20日涨幅排名（行业指数为主，
#      成分股平均兜底），缓存 g.hot_industries 供当日所有函数复用
#   2.【全模式融合】hot/big/small 的候选池 = 热点行业基本面候选(优先) +
#      原版基本面候选(补充)，取3只；foreign 只用热点行业候选，无标的才空仓
#   3.【月中切换】每周一10:00检查：若top1热点行业20日涨幅>5%且当前持仓
#      不在其中，且距上次调仓≥5天 → 换仓到热点行业（月中爆发最多滞后1周）
#   4. 保留：风格切换停止补跌、柔和大盘保护(破MA20且MA20<MA60清浮亏)
# ============================================================================
# 【V7.32】V7.5 + 双创ETF通道 + 动态持仓数 + 日志增强（2026-09-02）
#
# 用户需求（2026-09-02）：
#   1. 实盘日志太少，要加详细输出（状态/选股理由/买卖动作/开关依据）
#   2. 不想失去创业板/科创板暴涨优势 → 双创ETF通道（不是放开双创个股，
#      规避V7.6小票挤占+20cm动量虚高的坑，指数化吃板块β）
#   3. 动态持仓数：初始5万集中3只，资金滚大后分散降回撤
#
# V7.32 改动：
#   1.【日志增强】全链路 log.info：每日资产/目标持仓数、风格信号明细、
#      选股候选与理由、买卖动作、ETF通道开关依据
#   2.【双创ETF通道】占1席（主板N-1只+ETF1只）：
#      - 开启条件：创业板指20日涨幅相对沪深300超额≥1%（创业板ETF 159915）
#        或 科创50超额≥2%（科创50ETF 588000），且指数中期趋势向上
#        （收盘>MA20 且 MA20>MA60），且市场非弱市（mode≠foreign）
#      - 关闭：超额转负或趋势破坏 → ETF不在目标列表自动卖出
#      - 弱市(mode=foreign)/大盘保护清仓期：通道同步关闭（保V7.5择时系统完整）
#      - ETF止损线 -10%（介于主板-8%与双创股-14%之间）；ETF不参与补跌
#   3.【动态持仓数】按总资产阶梯(V7.43e·资金无关版)：档位线=起步资金倍数
#      资金<2×起步→3只、2~4×→5只、4~8×→6只、>8×→8只封顶（任何初始资金行为一致）
#   4. 其余（热点日更/全模式融合/周切换/风格切换停止补跌/柔和大盘保护/
#      主板-8%止损）与 V7.5 完全一致
# ============================================================================
# 【V7.33】V7.32 + 过热过滤 + 通道冷却期（2026-09-02）
#
# V7.32 回测发现的磨损（24-26 已完胜 V7.5，以下修尾部）：
#   1. 2024-11/2025-09：超额刚转正+趋势未破就开通道 → 转头回调吃 -3.4pt
#   2. 2022 阴跌年：通道可能"开→止损→反弹又开"反复磨损
#
# V7.33 改动（相对 V7.32）：
#   1.【过热过滤】指数20日乖离(close/MA20-1) ≥ 阈值(创18%/科20%) 不开通道
#      ——防快速拉升后追高（借鉴V7.28 HEAT_BIAS，比个股版0.20/0.22略严）
#   2.【通道冷却期】ETF被卖出（止损/信号关闭/弱市）后 10 个交易日内不重开
#      ——防 2022 式"刚止损又追反弹"循环磨损
#   其余（ETF通道机制/动态持仓数/日志增强）与 V7.32 完全一致
# ============================================================================
# 【V7.43g】V7.34L + 科创个股(688)通道（2026-09-08，用户要求试科创板）
#   688通道占1席（ETF未开时才试）：科创50超额≥0.5%+20日涨>0+close>MA20+非弱市+非冷却
#   候选=热点top3行业688成分（科创50成分兜底），市值80亿+换手2%双门槛
# 【V7.43g2】（2026-09-08）参数放宽：市值30亿/换手1.5%/pool>=1/每步诊断日志 —— 仍三年0触发
# 【V7.43g3】（2026-09-09）★根因修复：
#   ①市值门槛单位bug：聚宽valuation市值单位=亿元（实测688981流通市值1046.4），
#     43g写8e9/43g2写3e9=30亿亿元→全市场恒空→kcb_pool基本面后恒0只→通道从未买成
#   ②删除换手率硬门槛：valuation.turnover_ratio实测全NaN，NaN>1.5恒False也会滤空；
#     市值门槛已隐含流动性质量，改按市值排序即可
# 【V7.43g8】（2026-09-10）300通道超严格阈值版（用户方向：688行300就该行，300开放多了更差→应更严格）
#   43g4~g7 六版验证结论：300通道净≈0（2024 +19.29pt 全靠两段：3月软通~2pt + 924主升10-11月~17pt；
#   2025 -18.8pt 主因 2025-05 单月脉冲追高 -12.3pt；2026 前7月 +5.6、8月 -6.5 尾盘吐回）
#   → 触发太多=平庸介入多（超额1.5~5%的介入好坏参半）；区分度在 6% 以上：
#   创业板20日超额≥6%连续区间回放：2024-10-08~11-14 主升6周✓ / 2025-08~09 反弹✓ / 2026-05~06 主升✓
#   而 2025-05-08 脉冲峰值仅+5.0%（躲✓）/ 2025-12 妖股 +5.3%（放弃✓）/ 2026-07 超额-11.6%（躲✓）
#   → 43g8 = 43g4 单参数改动：CYB_EDGE 0.005 → 0.06（其余全同43g4，无过热闸无状态机）
#   代价：放弃 2024-03 软通(~2pt)、2024-12/2025-12 妖股尾部；预期躲 2025-05 -12pt + 2026-07~08 -6pt
# ============================================================================
# 【V7.43g4】（2026-09-09）用户要求对称开放创业板个股(300)：
#   新增创业板个股通道（cyb_signal/cyb_pool/is_cyb_stock/CYB_*参数）——与688通道对称：
#   创业板指20日超额沪深300≥0.5%+20日涨>0+close>MA20+非弱市+非冷却；市值门槛30(亿元)
#   调度升级：ETF通道 > 688/300个股通道（占1席）；688与300双开时取20日超额大者
#   止损-14%同688、独立冷却20日、不参与补跌；43g3验证：688通道修好后三年首次真买（+7.9pt）
# ============================================================================

# ============ V7.43g 科创个股通道参数（2026-09-08，用户要求试科创板） ============
KCB_EDGE = 0.005          # 688通道：科创50 20日超额沪深300 >=0.5%（刻意比ETF通道2%松，确保能触发）
KCB_MIN_CAP = 30          # 688候选最低流通市值 30（单位=亿元！聚宽valuation市值单位是亿元）
                          # ★43g3根因修复：43g/43g2写8e9/3e9=80/30亿亿元→全市场恒空→通道0生效
                          #   2026-09-09研究环境实测：688981流通市值=1046.4、688111=1459.97（亿元）
KCB_STOP = 0.86           # 688止损线：-14%（20cm波动，v7.8双创参数）
KCB_COOLDOWN_DAYS = 20    # 688止损后冷却交易日（防反复挨打，同ETF冷却思想）
KCB_POOL_N = 5            # 688候选池上限（动量排序后取前N，实买1只）
# ============ V7.43g4 创业板个股(300)通道参数（2026-09-09，用户要求对称开放300） ============
CYB_EDGE = 0.06           # V7.43g8: 300通道 20日超额沪深300 >=6%（超严格！只做指数级主升）
#   0.5/1.5% 零差异(43g5证)因失败介入也发生在1.5~5%；6%以上才是主升(924后+16~33%/2026-05 +10~22%)
CYB_MIN_CAP = 30          # 300候选最低流通市值 30（亿元，同688修复口径）
CYB_STOP = 0.86           # 300止损线：-14%（20cm波动，同688）
CYB_COOLDOWN_DAYS = 20    # 300止损后冷却交易日（同688）
CYB_POOL_N = 5            # 300候选池上限（动量排序后取前N，实买1只）
# 设计：ETF通道5条件AND(超额1%/2%+趋势+乖离<18%/20%+非弱市+冷却)三年0触发(过热过滤太严)
#   → 688开关必须宽松才不是死代码：超额>=0.5% + 20日涨幅>0 + close>MA20 + 非弱市 + 非冷却
#   科创成长股PE普遍高 → 688候选不用PE/ROE过滤，用流通市值保质量（43g3起不用换手率硬门槛：
#   聚宽valuation.turnover_ratio实测全NaN，硬门槛会把候选滤空）
# ============ V7.33 模块级参数 ============
EDGE_CYB_ETF = 0.01    # 创业板ETF通道开启阈值：20日超额>1%（V7.28的0.5%太松/2%太严折中）
EDGE_KCB_ETF = 0.02    # 科创50ETF更严：超额>2%（科创板回撤最大）
ETF_STOP = 0.90        # ETF止损线：-10%（介于主板-8%与双创股-14%）
HEAT_BIAS_CYB_ETF = 0.18   # V7.33: 创业板指20日乖离>18% = 过热，不开ETF通道
HEAT_BIAS_KCB_ETF = 0.20   # V7.33: 科创50乖离>20% = 过热（V7.28个股版0.22略严）
ETF_COOLDOWN_DAYS = 10     # V7.33: ETF卖出后冷却交易日数（防反复挨打）
GE_ETF_POOL = ['159915.XSHE', '588000.XSHG']   # 创业板ETF / 科创50ETF

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import pickle
import talib
import warnings
warnings.filterwarnings("ignore")

# 初始化函数
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='stock')
    # V7.32: ETF（基金）免印花税，佣金万3
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='fund')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    # 初始化全局变量
    g.no_trading_today_signal = False
    g.stock_num = 1            # 每套过滤器选1只（兼容旧函数签名）
    g.target_num = 3           # V7.32: 动态目标持仓数（每日按总资产刷新）
    g.etf_cooldown_date = None # V7.33: ETF通道冷却起始日（10交易日内不重开）
    g.kcb_cooldown_date = None # V7.43g: 688个股通道冷却起始日（20交易日内不重开）
    g.cyb_cooldown_date = None # V7.43g4: 创业板个股通道冷却起始日（20交易日内不重开）
    g.init_cash = None         # V7.34L: 初始资金（累计收益基准）
    g.prev_close_value = None  # V7.34L: 上一交易日收盘总资产（当日盈亏基准）
    g.use_foreign = False      # False=行业轮动，True=弱市买ETF避险
    g.hold_list = []           # 当前持仓的全部股票
    g.yesterday_HL_list = []   # 记录持仓中昨日涨停的股票
    g.last_mode = None         # 上次调仓的风格（big/small/hot/foreign）
    g.style_date = None        # 风格信号缓存日期
    g.style_signal = None      # 风格信号缓存 (B_mean, S_mean, mode, B_stocks, S_stocks)
    g.hot_date = None          # 行业热点计算日期
    g.hot_industries = None    # 强势行业列表 [(chg, code, name), ...] 每日更新
    g.last_adjust_date = None  # 最近一次调仓/换仓日期
    g.foreign_ETF = [
        '518880.XSHG',
        '513030.XSHG',
        '513100.XSHG',
        '164824.XSHE',
        '159866.XSHE',
        ]
    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    run_daily(update_hot, '9:10')                # V7.5：每日更新行业热点
    run_monthly(monthly_adjustment, 1, '9:31')
    run_weekly(weekly_rotate, 1, '10:00')        # V7.5：每周一检查热点切换
    run_daily(stop_loss, '14:00')
    run_daily(regime_guard, '14:30')             # 柔和大盘保护
    run_daily(daily_snapshot, '14:55')           # V7.34L: 每日收盘资产快照（实盘日志）

def prepare_stock_list(context):
    # V7.32: 每日按总资产刷新目标持仓数
    g.target_num = calc_hold_num(context)
    log.info('💼 总资产%.0f元 → 目标持仓%d只' % (context.portfolio.total_value, g.target_num))
    # 获取已持有列表
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    # 获取昨日涨停列表（V7.32: 仅股票，ETF无涨停打开逻辑）
    g.yesterday_HL_list = []
    stock_holds = [s for s in g.hold_list if not is_ge_etf(s)]
    if stock_holds:
        df = get_price(stock_holds, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)

# ============ 风格信号（月度调仓与每日止损共用，当日缓存） ============
def get_style_signal(context):
    today = context.current_dt.date()
    if g.style_date == today and g.style_signal is not None:
        return g.style_signal
    dt_last = context.previous_date
    N = 10
    # 大盘：沪深300成分，过滤后取流通市值前20
    B_stocks = get_index_stocks('000300.XSHG', dt_last)
    B_stocks = filter_kcbj_stock(B_stocks)
    B_stocks = filter_st_stock(B_stocks)
    B_stocks = filter_new_stock(context, B_stocks)
    q = query(
        valuation.code, valuation.circulating_market_cap
    ).filter(
        valuation.code.in_(B_stocks)
    ).order_by(
        valuation.circulating_market_cap.desc()
    )
    df = get_fundamentals(q, date=dt_last)
    Blst = list(df.code)[:20]
    # 小盘：中小板综成分，过滤后取流通市值前20
    S_stocks = get_index_stocks('399101.XSHE', dt_last)
    S_stocks = filter_kcbj_stock(S_stocks)
    S_stocks = filter_st_stock(S_stocks)
    S_stocks = filter_new_stock(context, S_stocks)
    q = query(
        valuation.code, valuation.circulating_market_cap
    ).filter(
        valuation.code.in_(S_stocks)
    ).order_by(
        valuation.circulating_market_cap.asc()
    )
    df = get_fundamentals(q, date=dt_last)
    Slst = list(df.code)[:20]

    B_mean = 0.0
    S_mean = 0.0
    if Blst:
        B_ratio = get_price(Blst, end_date=dt_last, frequency='1d', fields=['close'], count=N, panel=False
                            ).pivot(index='time', columns='code', values='close')
        chg = np.nan_to_num(np.array(B_ratio.iloc[-1] / B_ratio.iloc[0] - 1)) * 100
        B_mean = float(np.mean(chg))
    if Slst:
        S_ratio = get_price(Slst, end_date=dt_last, frequency='1d', fields=['close'], count=N, panel=False
                            ).pivot(index='time', columns='code', values='close')
        chg = np.nan_to_num(np.array(S_ratio.iloc[-1] / S_ratio.iloc[0] - 1)) * 100
        S_mean = float(np.mean(chg))

    if B_mean > 10 or S_mean > 10:
        mode = 'hot'
    elif B_mean > S_mean and B_mean > 0:
        mode = 'big'
    elif B_mean < S_mean and S_mean > 0:
        mode = 'small'
    else:
        mode = 'foreign'
    g.style_date = today
    g.style_signal = (B_mean, S_mean, mode, B_stocks, S_stocks)
    return g.style_signal

# ============ V7.5：每日更新行业热点（当日缓存，供全函数复用） ============
def update_hot(context):
    if g.hot_date != context.current_dt.date() or g.hot_industries is None:
        g.hot_industries = get_hot_industries(context, top_n=5)
        g.hot_date = context.current_dt.date()

# ============ 强势行业识别（申万一级，20日涨幅排名） ============
# V7.34L-fix（2026-09-03）：聚宽策略沙箱无 get_industries()（诊断确认 NameError），
# 改为硬编码申万一级行业表（2021版），指数代码用 .SI 后缀，成分股兜底逻辑保留
SW_L1_TABLE = [
    ('801010', '农林牧渔'), ('801030', '基础化工'), ('801040', '钢铁'),
    ('801050', '有色金属'), ('801080', '电子'), ('801110', '家用电器'),
    ('801120', '食品饮料'), ('801130', '纺织服饰'), ('801140', '轻工制造'),
    ('801150', '医药生物'), ('801160', '公用事业'), ('801170', '交通运输'),
    ('801180', '房地产'), ('801200', '商贸零售'), ('801210', '社会服务'),
    ('801230', '综合'), ('801710', '建筑材料'), ('801720', '建筑装饰'),
    ('801730', '电力设备'), ('801740', '国防军工'), ('801750', '计算机'),
    ('801760', '传媒'), ('801770', '通信'), ('801780', '银行'),
    ('801790', '非银金融'), ('801880', '汽车'), ('801890', '机械设备'),
    ('801950', '煤炭'), ('801960', '石油石化'), ('801970', '环保'),
    ('801980', '美容护理'),
]

def get_hot_industries(context, top_n=5):
    dt_last = context.previous_date
    results = []
    for code, name in SW_L1_TABLE:
        chg = None
        # 优先用行业指数（20日涨幅）；.SI 为申万指数后缀，失败则试裸代码
        for idx in (code + '.SI', code):
            try:
                df = get_price(idx, end_date=dt_last, frequency='daily', fields=['close'], count=21)
                close = df['close'].dropna()
                if len(close) >= 21:
                    chg = close.iloc[-1] / close.iloc[0] - 1
                    break
            except Exception:
                chg = None
        # 兜底：成分股平均20日涨幅
        if chg is None:
            try:
                stocks = get_industry_stocks(code, date=dt_last)
                if not stocks:
                    stocks = get_industry_stocks(code + '.SI', date=dt_last)
            except Exception:
                try:
                    stocks = get_industry_stocks(code + '.SI', date=dt_last)
                except Exception:
                    continue
            stocks = filter_kcbj_stock(stocks)
            stocks = filter_st_stock(stocks)
            stocks = filter_new_stock(context, stocks)
            if len(stocks) < 10:
                continue
            try:
                df = get_price(stocks, end_date=dt_last, frequency='daily', fields=['close'],
                               count=21, panel=False, skip_paused=True)
                if df is None or len(df) == 0:
                    continue
                df = df.reset_index()
                code_col = None
                for c in df.columns:
                    try:
                        if isinstance(df[c].iloc[0], str) and '.' in str(df[c].iloc[0]):
                            code_col = c
                            break
                    except Exception:
                        continue
                if code_col is None:
                    continue
                chgs = []
                for _, grp in df.groupby(code_col):
                    close = grp['close'].dropna()
                    if len(close) >= 21:
                        chgs.append(close.iloc[-1] / close.iloc[0] - 1)
                if chgs:
                    chg = float(np.mean(chgs))
            except Exception:
                continue
        if chg is not None:
            results.append((chg, code, name))
    results.sort(reverse=True)
    log.info('强势行业TOP%d: %s' % (top_n, ' | '.join(['%s%.1f%%' % (n, c*100) for c, _, n in results[:top_n]])))
    return results[:top_n]

# ============ 热点行业候选池（基本面过滤+动量排序，取30只） ============
def hot_pool(context, hot):
    if not hot:
        return []
    dt_last = context.previous_date
    pool = []
    for _, code, _ in hot[:3]:
        try:
            stocks = get_industry_stocks(code, date=dt_last)
            if not stocks:
                stocks = get_industry_stocks(code + '.SI', date=dt_last)
        except Exception:
            try:
                stocks = get_industry_stocks(code + '.SI', date=dt_last)
            except Exception:
                continue
        stocks = filter_kcbj_stock(stocks)
        stocks = filter_st_stock(stocks)
        stocks = filter_new_stock(context, stocks)
        pool.extend(stocks)
    pool = list(set(pool))
    if len(pool) < 3:
        return []
    q = query(
        valuation.code,
    ).filter(
        valuation.code.in_(pool),
        valuation.pe_ratio_lyr.between(0, 60),
        indicator.roe > 0.08,
        valuation.pb_ratio.between(0, 10),
    ).order_by(
        valuation.market_cap.asc()
    ).limit(30)
    try:
        cand = list(get_fundamentals(q, date=dt_last).code)
    except Exception:
        return []
    if len(cand) < 1:
        return []
    cand = momentum_rank(context, cand)
    return cand

# ============ V7.43g：688子候选（热点top3行业里的科创板成分） ============
def kcb_pool(context, hot):
    """V7.43g3: 688子候选——热点top3行业688成分 + 科创50指数成分兜底
    43g/43g2教训：不是"参数交集小"，是单位bug——聚宽valuation市值单位=亿元，
    43g写8e9/43g2写3e9 = 80/30亿亿元 全市场恒空；且turnover_ratio实测全NaN，
    换手硬门槛恒False → 三年候选恒空 → 通道0生效
    g3修复：市值门槛30(亿元) + 删换手硬门槛(市值排序保质量) + 保留诊断日志"""
    if not hot:
        log.info('🔬 kcb_pool: hot为空，跳过')
        return []
    dt_last = context.previous_date
    pool = []
    for _, code, _ in hot[:3]:
        try:
            stocks = get_industry_stocks(code, date=dt_last)
            if not stocks:
                stocks = get_industry_stocks(code + '.SI', date=dt_last)
        except Exception:
            try:
                stocks = get_industry_stocks(code + '.SI', date=dt_last)
            except Exception:
                continue
        pool.extend([s for s in stocks if s[:3] == '688'])
    pool = list(set(pool))
    log.info('🔬 kcb_pool: 热点行业688成分 %d只' % len(pool))
    # 兜底：热点行业688太少时用科创50指数成分补（保证候选源不空）
    if len(pool) < 1:
        try:
            idx_stocks = get_index_stocks('000688.XSHG', dt_last)
            pool = [s for s in idx_stocks if s[:3] == '688']
            log.info('🔬 kcb_pool: 热点688不足，科创50成分兜底 %d只' % len(pool))
        except Exception:
            return []
    if len(pool) < 1:
        return []
    q = query(
        valuation.code,
    ).filter(
        valuation.code.in_(pool),
        valuation.circulating_market_cap > KCB_MIN_CAP,
    ).order_by(
        valuation.circulating_market_cap.desc()
    ).limit(KCB_POOL_N * 3)
    try:
        cand = list(get_fundamentals(q, date=dt_last).code)
        log.info('🔬 kcb_pool: 基本面(流通市值>%.0f亿)后 %d只' % (KCB_MIN_CAP, len(cand)))
    except Exception as e:
        log.info('🔬 kcb_pool: 基本面查询失败 %s' % e)
        return []
    if len(cand) < 1:
        return []
    cand = momentum_rank(context, cand)
    n0 = len(cand)
    cand = filter_limitup_stock(context, cand)
    cand = filter_limitdown_stock(context, cand)
    cand = filter_paused_stock(cand)
    cand = filter_expensive_stock(context, cand)
    log.info('🔬 kcb_pool: 动量%d只 → 过滤后%d只: %s' % (n0, len(cand), ' '.join(cand[:KCB_POOL_N])))
    return cand[:KCB_POOL_N]


# ============ V7.43g4：创业板子候选（热点top3行业里的300/301成分） ============
def cyb_pool(context, hot):
    """V7.43g4: 300子候选——热点top3行业创业板成分 + 创业板指成分兜底
    对称kcb_pool：市值门槛30(亿元，单位已修正) + 不设换手硬门槛（NaN坑）"""
    if not hot:
        log.info('🔬 cyb_pool: hot为空，跳过')
        return []
    dt_last = context.previous_date
    pool = []
    for _, code, _ in hot[:3]:
        try:
            stocks = get_industry_stocks(code, date=dt_last)
            if not stocks:
                stocks = get_industry_stocks(code + '.SI', date=dt_last)
        except Exception:
            try:
                stocks = get_industry_stocks(code + '.SI', date=dt_last)
            except Exception:
                continue
        pool.extend([s for s in stocks if s[:3] in ('300', '301')])
    pool = list(set(pool))
    log.info('🔬 cyb_pool: 热点行业300成分 %d只' % len(pool))
    # 兜底：热点行业300太少时用创业板指成分补（保证候选源不空）
    if len(pool) < 1:
        try:
            idx_stocks = get_index_stocks('399006.XSHE', dt_last)
            pool = [s for s in idx_stocks if s[:3] in ('300', '301')]
            log.info('🔬 cyb_pool: 热点300不足，创业板指成分兜底 %d只' % len(pool))
        except Exception:
            return []
    if len(pool) < 1:
        return []
    q = query(
        valuation.code,
    ).filter(
        valuation.code.in_(pool),
        valuation.circulating_market_cap > CYB_MIN_CAP,
    ).order_by(
        valuation.circulating_market_cap.desc()
    ).limit(CYB_POOL_N * 3)
    try:
        cand = list(get_fundamentals(q, date=dt_last).code)
        log.info('🔬 cyb_pool: 基本面(流通市值>%.0f亿)后 %d只' % (CYB_MIN_CAP, len(cand)))
    except Exception as e:
        log.info('🔬 cyb_pool: 基本面查询失败 %s' % e)
        return []
    if len(cand) < 1:
        return []
    cand = momentum_rank(context, cand)
    n0 = len(cand)
    cand = filter_limitup_stock(context, cand)
    cand = filter_limitdown_stock(context, cand)
    cand = filter_paused_stock(cand)
    cand = filter_expensive_stock(context, cand)
    log.info('🔬 cyb_pool: 动量%d只 → 过滤后%d只: %s' % (n0, len(cand), ' '.join(cand[:CYB_POOL_N])))
    return cand[:CYB_POOL_N]


# ============ 动量排序（只排序不剔除，避免候选清零空仓） ============
def momentum_rank(context, stock_list):
    if not stock_list:
        return []
    today = context.previous_date
    try:
        df = get_price(stock_list, end_date=today, frequency='daily', fields=['close'],
                       count=30, panel=False, skip_paused=True)
        if df is None or len(df) == 0:
            return stock_list
        df = df.reset_index()
        code_col = None
        for c in df.columns:
            try:
                if isinstance(df[c].iloc[0], str) and '.' in str(df[c].iloc[0]):
                    code_col = c
                    break
            except Exception:
                continue
        if code_col is None:
            return stock_list
        out = []
        for code, grp in df.groupby(code_col):
            try:
                close = grp['close'].dropna()
                if len(close) < 21:
                    out.append((-999, code))
                    continue
                c = close.iloc[-1]
                mom20 = c / close.iloc[-21] - 1
                out.append((mom20, code))
            except Exception:
                out.append((-999, code))
        out.sort(reverse=True)
        return [c for _, c in out]
    except Exception:
        return stock_list

# ============ V7.32：动态持仓数（按总资产阶梯，净值涨自动分散） ============
def calc_hold_num(context):
    # V7.43e: 资金无关版（用户 9/7 洞察：收益率与初始资金无关，与行为有关）
    # 档位线 = 起步资金倍数（×2/×4/×8），而非绝对金额：
    #   5万起步 → 3只<10万(+100%)、5只<20万、6只<40万；10万起步 ≡ 43d(已证 +212.98%)
    #   100万起步 → 3只<200万…… 任何资金起步行为一致 → 收益率曲线一致
    # 安全阀(相对化后自动成立)：资金翻倍(+100%)即升 5只 → 5万起步 2025-12 升5只，
    #   2026-06 资金13-15万 已5只护体，不重演 37 清仓踏空（43d 绝对线 5万起步才危险）
    # 实盘注资：starting_cash 若固定，注资推高 total/base → 提前升档 = 自动保守化(安全方向)
    total = context.portfolio.total_value
    base = context.portfolio.starting_cash or 80000.0
    if base <= 0:
        base = 80000.0
    multi = total / base
    if multi < 2.0:
        n = 3
    elif multi < 4.0:
        n = 5
    elif multi < 8.0:
        n = 6
    else:
        n = 8
    return n


# ============ V7.32：双创ETF通道判断 ============
def is_ge_etf(security):
    return security in GE_ETF_POOL


def is_kcb_stock(security):
    # V7.43g: 科创板个股（688开头；588开头ETF由 is_ge_etf 单列，不冲突）
    return security[:3] == '688'


def is_cyb_stock(security):
    # V7.43g4: 创业板个股（300/301开头；159915ETF由 is_ge_etf 单列，不冲突）
    return security[:3] in ('300', '301')


def ge_etf_signal(context):
    """返回 (etf_code or None, reason)
    开启：指数20日涨幅相对沪深300超额≥阈值(创1%/科2%) AND 指数中期趋势向上
          (收盘>MA20且MA20>MA60) AND 非过热(乖离<18%/20%) AND 市场非弱市
          AND 不在冷却期(V7.33)"""
    dt_last = context.previous_date
    # V7.33: 冷却期检查（ETF卖出后10交易日内不重开）
    if g.etf_cooldown_date is not None:
        try:
            td = get_trade_days(g.etf_cooldown_date, context.current_dt.date())
            if len(td) < ETF_COOLDOWN_DAYS:
                return None, '冷却期第%d/%d交易日（%s卖出后）' % (
                    len(td), ETF_COOLDOWN_DAYS, g.etf_cooldown_date)
        except Exception:
            pass
    try:
        _, _, mode, _, _ = get_style_signal(context)
    except Exception:
        mode = 'foreign'
    if mode == 'foreign':
        # V7.33: 弱市关闭若当前持有ETF → 启动冷却
        if any(is_ge_etf(s) for s in g.hold_list):
            g.etf_cooldown_date = context.current_dt.date()
        return None, '弱市(%s)通道关闭' % mode
    # 沪深300基准20日涨幅
    try:
        df300 = get_price('000300.XSHG', end_date=dt_last, frequency='daily',
                          fields=['close'], count=25)
        c300 = df300['close'].dropna()
        if len(c300) < 21:
            return None, '沪深300数据不足'
        mom300 = c300.iloc[-1] / c300.iloc[-21] - 1
    except Exception:
        return None, '沪深300数据错误'
    # 各指数：趋势 + 20日涨幅 + 20日乖离(V7.33)
    def idx_stat(idx):
        try:
            df = get_price(idx, end_date=dt_last, frequency='daily',
                           fields=['close'], count=70)
            close = df['close'].dropna()
            if len(close) < 65:
                return None
            ma20 = close.rolling(20).mean().iloc[-1]
            ma60 = close.rolling(60).mean().iloc[-1]
            trend = close.iloc[-1] > ma20 and ma20 > ma60
            mom20 = close.iloc[-1] / close.iloc[-21] - 1
            heat = close.iloc[-1] / ma20 - 1   # 20日乖离率
            return trend, mom20, heat
        except Exception:
            return None
    cand = []
    cyb = idx_stat('399006.XSHE')
    if cyb:
        trend, mom, heat = cyb
        if trend and heat < HEAT_BIAS_CYB_ETF and (mom - mom300) >= EDGE_CYB_ETF:
            cand.append(((mom - mom300), '159915.XSHE', '创业板ETF'))
    kcb = idx_stat('000688.XSHG')
    if kcb:
        trend, mom, heat = kcb
        if trend and heat < HEAT_BIAS_KCB_ETF and (mom - mom300) >= EDGE_KCB_ETF:
            cand.append(((mom - mom300), '588000.XSHG', '科创50ETF'))
    if not cand:
        # V7.33: 通道关闭且当前持有ETF → 本次调仓将卖出 → 启动冷却
        if any(is_ge_etf(s) for s in g.hold_list):
            g.etf_cooldown_date = context.current_dt.date()
        return None, '双创无超额/过热/趋势未确立(创超额%+.1f%%乖离%+.1f%%|科超额%+.1f%%乖离%+.1f%% vs 300 %+.1f%%)' % (
            (cyb[1]-mom300)*100 if cyb else 0, cyb[2]*100 if cyb else 0,
            (kcb[1]-mom300)*100 if kcb else 0, kcb[2]*100 if kcb else 0, mom300*100)
    cand.sort(reverse=True)
    return cand[0][1], '%s超额%+.1f%%乖离%+.1f%%趋势向上' % (
        cand[0][2], cand[0][0]*100,
        (cyb[2] if cyb and cand[0][1] == '159915.XSHE' else (kcb[2] if kcb else 0))*100)


# ============ V7.43g：科创个股通道开关（宽松版，保证24-26有真实触发） ============
def kcb_signal(context):
    """返回 (启用bool, reason, 20日超额)  V7.43g4起返回超额供双通道比较
    开启：非弱市 AND 非冷却期 AND 科创50 20日涨幅>0 AND 超额沪深300>=0.5% AND 收盘>MA20"""
    dt_last = context.previous_date
    if g.kcb_cooldown_date is not None:
        try:
            td = get_trade_days(g.kcb_cooldown_date, context.current_dt.date())
            if len(td) < KCB_COOLDOWN_DAYS:
                return False, '冷却期第%d/%d交易日（688止损后）' % (len(td), KCB_COOLDOWN_DAYS), 0.0
        except Exception:
            pass
    try:
        _, _, mode, _, _ = get_style_signal(context)
    except Exception:
        mode = 'foreign'
    if mode == 'foreign':
        return False, '弱市(%s)通道关闭' % mode, 0.0
    try:
        df300 = get_price('000300.XSHG', end_date=dt_last, frequency='daily',
                          fields=['close'], count=25)
        c300 = df300['close'].dropna()
        dfk = get_price('000688.XSHG', end_date=dt_last, frequency='daily',
                        fields=['close'], count=70)
        ck = dfk['close'].dropna()
        if len(c300) < 21 or len(ck) < 25:
            return False, '指数数据不足', 0.0
        mom300 = c300.iloc[-1] / c300.iloc[-21] - 1
        mom_kcb = ck.iloc[-1] / ck.iloc[-21] - 1
        ma20 = ck.rolling(20).mean().iloc[-1]
        trend = ck.iloc[-1] > ma20
        if mom_kcb > 0 and (mom_kcb - mom300) >= KCB_EDGE and trend:
            return True, '科创50超额%+.1f%%趋势向上' % ((mom_kcb - mom300) * 100), (mom_kcb - mom300)
        return False, '科创50 20日%+.1f%%(超额%+.1f%%,%s)' % (
            mom_kcb * 100, (mom_kcb - mom300) * 100, '趋势向上' if trend else '跌破MA20'), (mom_kcb - mom300)
    except Exception as e:
        return False, '数据错误:%s' % e, 0.0


# ============ V7.43g4：创业板个股(300)通道开关（对称688，宽松版） ============
def cyb_signal(context):
    """返回 (启用bool, reason, 20日超额)
    开启：非弱市 AND 非冷却期 AND 创业板指 20日涨幅>0 AND 超额沪深300>=0.5% AND 收盘>MA20"""
    dt_last = context.previous_date
    if g.cyb_cooldown_date is not None:
        try:
            td = get_trade_days(g.cyb_cooldown_date, context.current_dt.date())
            if len(td) < CYB_COOLDOWN_DAYS:
                return False, '冷却期第%d/%d交易日（300止损后）' % (len(td), CYB_COOLDOWN_DAYS), 0.0
        except Exception:
            pass
    try:
        _, _, mode, _, _ = get_style_signal(context)
    except Exception:
        mode = 'foreign'
    if mode == 'foreign':
        return False, '弱市(%s)通道关闭' % mode, 0.0
    try:
        df300 = get_price('000300.XSHG', end_date=dt_last, frequency='daily',
                          fields=['close'], count=25)
        c300 = df300['close'].dropna()
        dfc = get_price('399006.XSHE', end_date=dt_last, frequency='daily',
                        fields=['close'], count=70)
        cc = dfc['close'].dropna()
        if len(c300) < 21 or len(cc) < 25:
            return False, '指数数据不足', 0.0
        mom300 = c300.iloc[-1] / c300.iloc[-21] - 1
        mom_cyb = cc.iloc[-1] / cc.iloc[-21] - 1
        ma20 = cc.rolling(20).mean().iloc[-1]
        trend = cc.iloc[-1] > ma20
        if mom_cyb > 0 and (mom_cyb - mom300) >= CYB_EDGE and trend:
            return True, '创业板指超额%+.1f%%≥%.0f%%趋势向上' % ((mom_cyb - mom300) * 100, CYB_EDGE * 100), (mom_cyb - mom300)
        return False, '创业板指 20日%+.1f%%(超额%+.1f%%,%s)' % (
            mom_cyb * 100, (mom_cyb - mom300) * 100, '趋势向上' if trend else '跌破MA20'), (mom_cyb - mom300)
    except Exception as e:
        return False, '数据错误:%s' % e, 0.0


# ============ V7.43g4：通道席决策（ETF > 688/300个股通道，双开取超额大者） ============
def pick_channel_stock(context):
    """返回 (通道票code or None, reason)
    优先级：双创ETF（指数化） > 688/300个股通道（占1席）
    688与300同时开启时：都生成候选，优先买20日超额更大的板块（更强趋势）
    ETF关闭时若个股通道候选空 → 静默回退全主板（不阻塞调仓）"""
    ge_etf, etf_reason = ge_etf_signal(context)
    if ge_etf:
        return ge_etf, etf_reason
    kcb_on, kcb_reason, kcb_ex = kcb_signal(context)
    cyb_on, cyb_reason, cyb_ex = cyb_signal(context)
    if not kcb_on and not cyb_on:
        return None, etf_reason
    # 至少一个开：688优先条件 = 开且(300未开或688超额更大)
    if kcb_on and (not cyb_on or kcb_ex >= cyb_ex):
        cand = kcb_pool(context, g.hot_industries)
        if cand:
            return cand[0], kcb_reason
        if not cyb_on:
            return None, kcb_reason + '（688候选空）'
    if cyb_on:
        cand = cyb_pool(context, g.hot_industries)
        if cand:
            return cand[0], cyb_reason
        if kcb_on:  # 300候选空 → 回退688
            cand = kcb_pool(context, g.hot_industries)
            if cand:
                return cand[0], kcb_reason + '（300候选空，回退688）'
    return None, '个股通道候选均空'


# ============ 柔和大盘保护（破MA20 且 MA20<MA60 才清浮亏，避免误杀） ============
def regime_guard(context):
    try:
        df = get_price('000300.XSHG', end_date=context.current_dt.date(), frequency='daily',
                       fields=['close'], count=70)
        close = df['close']
        c = close.iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1]
        if not (c < ma20 and ma20 < ma60):
            return
    except Exception:
        return
    for code in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[code]
        if pos.total_amount > 0 and pos.avg_cost and pos.price < pos.avg_cost:
            log.warn('🛡️ 大盘确认弱势且%s浮亏，清仓保护' % code)
            order_target_value(code, 0)

# ============ V7.5：每周一热点切换检查（月中变化最多滞后一周） ============
def weekly_rotate(context):
    today = context.current_dt.date()
    if g.last_adjust_date is not None and (today - g.last_adjust_date).days < 5:
        return
    if not g.hold_list:
        return
    if not g.hot_industries:
        return
    top1_chg, top1_code, top1_name = g.hot_industries[0]
    if top1_chg < 0.05:
        return  # 最强行业还不够强（20日涨幅<5%），不动
    # 当前持仓是否已在top1行业
    hold_in_top1 = False
    for s in g.hold_list:
        try:
            ind = get_industry(s, date=context.previous_date)
            info = None
            if ind and isinstance(ind, dict):
                info = ind.get(s)
                if info is None and len(ind) > 0:
                    info = ind[list(ind.keys())[0]]
            if info and 'sw_l1' in info and info['sw_l1'].get('industry_code') == top1_code:
                hold_in_top1 = True
                break
        except Exception:
            continue
    if hold_in_top1:
        return  # 已持有最强行业
    log.info('⚡ 热点切换：%s 20日涨幅%.1f%%，持仓不在其中 → 换仓' % (top1_name, top1_chg*100))
    target_list = hot_pool(context, g.hot_industries)
    if len(target_list) < 1:
        return
    # V7.43g4：通道席决策（双创ETF > 688/300个股通道，占1席；个股双开取超额大者）
    ch_code, ch_reason = pick_channel_stock(context)
    main_n = g.target_num
    if ch_code:
        main_n = max(g.target_num - 1, 1)
        tag = '双创ETF' if is_ge_etf(ch_code) else ('科创个股' if is_kcb_stock(ch_code) else '创业板个股')
        log.info('🚀 %s通道开启: %s（%s）→ 主板%d席 + 通道1席' % (tag, ch_code, ch_reason, main_n))
    target_list = target_list[:main_n]
    if ch_code:
        # V7.34: 通道票前置到首位 → 买入循环优先保证通道席位资金
        target_list = [ch_code] + target_list
    else:
        log.info('🔒 通道关闭（%s）→ 全主板%d席' % (ch_reason, main_n))
    target_list = filter_limitup_stock(context, target_list)
    target_list = filter_limitdown_stock(context, target_list)
    target_list = filter_paused_stock(target_list)
    target_list = filter_expensive_stock(context, target_list)
    log.info('🎯 目标组合(%d席): %s' % (len(target_list), ' '.join(target_list)))
    for stock in g.hold_list:
        if (stock not in target_list) and (stock not in g.yesterday_HL_list):
            position = context.portfolio.positions[stock]
            close_position(position)
    position_count = len(context.portfolio.positions)
    target_num = len(target_list)
    if target_num > position_count:
        for stock in target_list:
            if stock not in list(context.portfolio.positions.keys()):
                remain = target_num - len(context.portfolio.positions)
                if remain <= 0:
                    break
                value = context.portfolio.cash / remain
                if open_position(stock, value):
                    if len(context.portfolio.positions) == target_num:
                        break
                else:
                    log.info('⚠️ %s 买入未成交(现金%.0f)，跳过' % (stock, context.portfolio.cash))
    g.last_adjust_date = today

def stop_loss(context):
    num = 0
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        # 对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'],
                                     skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
                num = num+1
            else:
                log.info("[%s]涨停，继续持有" % (stock))
    SS=[]
    S=[]
    for stock in g.hold_list:
        if stock in list(context.portfolio.positions.keys()):
            # V7.32：止损线分级（主板-8%，ETF-10%）；V7.43g: 688个股-14%；V7.43g4: 300个股同-14%
            sl_ratio = ETF_STOP if is_ge_etf(stock) else (KCB_STOP if is_kcb_stock(stock) else (CYB_STOP if is_cyb_stock(stock) else 0.92))
            # V7.34: 防御——实际持仓>0且成本>0才止损（防买入失败的空仓假止损）
            pos = context.portfolio.positions[stock]
            if pos.total_amount > 0 and pos.avg_cost and pos.price < pos.avg_cost * sl_ratio:
                order_target_value(stock, 0)
                log.info('🛑 止损卖出 %s（跌破%.0f%%线 成本%.2f/现价%.2f）' % (
                    stock, (1-sl_ratio)*100, pos.avg_cost, pos.price))
                # V7.33: ETF止损 → 启动通道冷却；V7.43g: 688止损同样冷却
                if is_ge_etf(stock):
                    g.etf_cooldown_date = context.current_dt.date()
                    log.info('🧊 ETF止损 → 通道冷却%d个交易日' % ETF_COOLDOWN_DAYS)
                elif is_kcb_stock(stock):
                    g.kcb_cooldown_date = context.current_dt.date()
                    log.info('🧊 688止损 → 科创通道冷却%d个交易日' % KCB_COOLDOWN_DAYS)
                elif is_cyb_stock(stock):
                    g.cyb_cooldown_date = context.current_dt.date()
                    log.info('🧊 300止损 → 创业板通道冷却%d个交易日' % CYB_COOLDOWN_DAYS)
                num = num+1
            else:
                S.append(stock)
                NOW = (context.portfolio.positions[stock].price - context.portfolio.positions[stock].avg_cost)/context.portfolio.positions[stock].avg_cost
                SS.append(np.array(NOW))
    else:
        # 风格切换期停止补跌（用户核心要求）
        if num >= 1 and len(SS) > 0:
            try:
                _, _, cur_mode, _, _ = get_style_signal(context)
            except Exception:
                cur_mode = g.last_mode
            if cur_mode == 'foreign':
                log.info('弱市(%s)，停止补跌' % cur_mode)
            elif g.last_mode is not None and cur_mode != g.last_mode:
                log.info('风格切换(%s->%s)，停止补跌' % (g.last_mode, cur_mode))
            else:
                pairs = sorted(zip(SS, S))[:g.target_num]
                # V7.32: ETF不参与补跌；V7.43g: 688同样不参与（20cm波动不加摊）；V7.43g4: 300同
                pairs = [p for p in pairs if not is_ge_etf(p[1]) and not is_kcb_stock(p[1]) and not is_cyb_stock(p[1])]
                if not pairs:
                    return
                min_strings = [s for _, s in pairs]
                cash = context.portfolio.cash / len(min_strings)
                for ss in min_strings:
                    order_value(ss, cash)
                    log.info('🩹 补跌加仓 %s（浮亏%.1f%%，现金%.0f等分）' % (
                        ss, (context.portfolio.positions[ss].price/context.portfolio.positions[ss].avg_cost-1)*100, cash))

def filter_roic(context,stock_list):
    yesterday = context.previous_date
    list=[]
    for stock in stock_list:
        roic=get_factor_values(stock, 'roic_ttm', end_date=yesterday,count=1)['roic_ttm'].iloc[0,0]
        if roic>0.08:
            list.append(stock)
    return list

def SMALL(context,choice):
    df = get_fundamentals(query(
        valuation.code,
        indicator.roe,
        indicator.roa,
    ).filter(
        valuation.code.in_(choice),
        indicator.roe > 0.15,
        indicator.roa > 0.10,
    )).set_index('code').index.tolist()

    q = query(
    valuation.code
    ).filter(
	valuation.code.in_(df)
	).order_by(
         valuation.market_cap.asc())
    final_list = list(get_fundamentals(q).code)
    return final_list

def BIG(context,choice):
    BIG_stock_list = get_fundamentals(query(
        valuation.code,
    ).filter(
        valuation.code.in_(choice),
        valuation.pe_ratio_lyr.between(0,30),#市盈率
        valuation.ps_ratio.between(0,8),#市销率TTM
        valuation.pcf_ratio<10,#市现率TTM
        indicator.eps>0.3,#每股收益
        indicator.roe>0.1,#净资产收益率
        indicator.net_profit_margin>0.1,#销售净利率
        indicator.gross_profit_margin>0.3,#销售毛利率
        indicator.inc_revenue_year_on_year>0.25,#营业收入同比增长率
    ).order_by(
    valuation.market_cap.desc()).limit(g.stock_num)).set_index('code').index.tolist()

    return BIG_stock_list
def ROIC_BIG(context,choice):
    df = get_fundamentals(query(
            valuation.code,
        ).filter(
            valuation.code.in_(choice),
            valuation.market_cap>300,#总市值（亿元）
            valuation.pe_ratio.between(0,50),#市盈率TTM
            indicator.eps>0.12,#每股收益
            indicator.roa>0.15,  #总资产收益
            (balance.total_liability/balance.total_sheet_owner_equities)<0.5,
            indicator.inc_total_revenue_year_on_year>0.3,#营业总收入同比增长率
            indicator.inc_revenue_year_on_year>0.2,#营业收入同比增长率
            balance.retained_profit>0,#未分配利润
        )).set_index('code').index.tolist()
    df=filter_roic(context,df)
    q = query(
    valuation.code
    ).filter(
	valuation.code.in_(df)
	).order_by(
         balance.retained_profit.desc())

    final_list = list(get_fundamentals(q).code)[:g.stock_num]
    return final_list
def BM(context,choice):
    BM_list = get_fundamentals(query(
            valuation.code,
        ).filter(
            valuation.code.in_(choice),
            valuation.market_cap.between(100,900),#总市值（亿元）
            valuation.pb_ratio.between(0,10),#市净率
            valuation.pcf_ratio<4,#市现率TTM
            indicator.eps>0.3,#每股收益
            indicator.roe>0.2,#净资产收益率
            indicator.net_profit_margin>0.1,#销售净利率
            indicator.inc_revenue_year_on_year>0.2,#营业收入同比增长率
            indicator.inc_operation_profit_year_on_year>0.1,#营业利润同比增长率
        ).order_by(
        valuation.market_cap.asc()).limit(g.stock_num)).set_index('code').index.tolist()
    return BM_list

# 1-3 整体调整持仓（每月1日）
def monthly_adjustment(context):
    B_mean, S_mean, mode, B_stocks, S_stocks = get_style_signal(context)
    log.info('📊 月度调仓 风格信号 B(大盘10日):%+.1f%% S(小盘10日):%+.1f%% mode:%s 目标持仓%d只' % (
        B_mean, S_mean, mode, g.target_num))
    # 确保热点已更新（今日未算则算）
    if g.hot_date != context.current_dt.date() or g.hot_industries is None:
        g.hot_industries = get_hot_industries(context, top_n=5)
        g.hot_date = context.current_dt.date()

    if mode == 'hot':
        print('无敌好行情·猛干')
        if B_mean > S_mean:
            print('开大')
            choice = B_stocks
            base_list = list(set(BM(context,choice)+ROIC_BIG(context,choice)+BIG(context,choice)))
        else:
            print('开小')
            choice = S_stocks
            base_list = SMALL(context,choice)[:g.stock_num*3]
    elif mode == 'big':
        print('开大')
        choice = B_stocks
        base_list = list(set(BIG(context,choice)+ROIC_BIG(context,choice)+BM(context,choice)))
    elif mode == 'small':
        print('开小')
        choice = S_stocks
        base_list = SMALL(context,choice)[:g.stock_num*3]
    else:
        print('弱市·行业轮动')
        if g.use_foreign:
            base_list = g.foreign_ETF
        else:
            base_list = []

    # V7.5：全模式融合热点行业（热点优先，原版候选补充）
    # V7.32：动态持仓数 + 双创ETF通道占1席
    if g.use_foreign and mode == 'foreign':
        target_list = base_list
    else:
        hot_stocks = hot_pool(context, g.hot_industries) if g.hot_industries else []
        base_list = momentum_rank(context, base_list)
        ch_code, ch_reason = pick_channel_stock(context)
        main_n = g.target_num
        if ch_code:
            main_n = max(g.target_num - 1, 1)
            tag = '双创ETF' if is_ge_etf(ch_code) else ('科创个股' if is_kcb_stock(ch_code) else '创业板个股')
            log.info('🚀 %s通道开启: %s（%s）→ 主板%d席 + 通道1席' % (tag, ch_code, ch_reason, main_n))
        target_list = (hot_stocks + [s for s in base_list if s not in hot_stocks])[:main_n]
        if ch_code:
            # V7.34: 通道票前置到首位 → 买入循环优先保证通道席位资金
            target_list = [ch_code] + target_list
        else:
            log.info('🔒 通道关闭（%s）→ 全主板%d席' % (ch_reason, main_n))

    g.last_mode = mode
    g.last_adjust_date = context.current_dt.date()

    target_list = filter_limitup_stock(context,target_list)
    target_list = filter_limitdown_stock(context,target_list)
    target_list = filter_paused_stock(target_list)
    target_list = filter_expensive_stock(context, target_list)
    log.info('🎯 目标组合(%d席): %s' % (len(target_list), ' '.join(target_list)))
    for stock in g.hold_list:
        if (stock not in target_list) and (stock not in g.yesterday_HL_list):
            position = context.portfolio.positions[stock]
            close_position(position)
    position_count = len(context.portfolio.positions)
    target_num = len(target_list)
    if target_num > position_count:
        for stock in target_list:
            if stock not in list(context.portfolio.positions.keys()):
                remain = target_num - len(context.portfolio.positions)
                if remain <= 0:
                    break
                value = context.portfolio.cash / remain
                if open_position(stock, value):
                    if len(context.portfolio.positions) == target_num:
                        break
                else:
                    log.info('⚠️ %s 买入未成交(现金%.0f)，跳过' % (stock, context.portfolio.cash))


# 3-1 交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        log.info('📤 卖出 %s' % security)
    else:
        log.info('📥 买入 %s 目标市值%.0f' % (security, value))
    return order_target_value(security, value)

# 3-2 交易模块-开仓
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        log.info('✅ 成交 %s %d股（目标%.0f元）' % (security, order.filled, value))
        return True
    return False

# 3-3 交易模块-平仓
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            log.info('✅ 清仓成交 %s %d股' % (security, order.filled))
            return True
    return False


def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

# 2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


# 2-3 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68' or stock[0] == '3':
            stock_list.remove(stock)
    return stock_list


# 2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


# 2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]


# 2-6 过滤次新股
def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if
            not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=375)]

# 2-7 过滤高价股（V7.34：一手金额>单席预算 → 买不起1手会委托失败占名额）
def filter_expensive_stock(context, stock_list):
    if not stock_list:
        return stock_list
    n = max(g.target_num, 1)
    budget = context.portfolio.total_value * 0.95 / n
    current_data = get_current_data()
    out = []
    for stock in stock_list:
        try:
            price = current_data[stock].last_price
            if price is None or price <= 0:
                price = current_data[stock].day_open
            if price is not None and price > 0 and price * 100 > budget:
                log.info('💸 过滤高价股 %s（现价%.0f，一手%.0f > 单席预算%.0f）' % (stock, price, price*100, budget))
                continue
        except Exception:
            pass
        out.append(stock)
    return out

# V7.34L: 每日收盘资产快照（14:55）——复制日志即可重建收益曲线
def daily_snapshot(context):
    try:
        tv = context.portfolio.total_value
        cash = context.portfolio.cash
        if g.init_cash is None:
            try:
                g.init_cash = context.portfolio.starting_cash
            except Exception:
                g.init_cash = tv
        pnl = ''
        if g.prev_close_value is not None and g.prev_close_value > 0:
            pnl = '当日%+8.0f元(%+.2f%%)' % (tv - g.prev_close_value, (tv / g.prev_close_value - 1) * 100)
        log.info('💼 收盘快照 总资产%.0f元(累计%+.2f%%) 现金%.0f %s' % (
            tv, (tv / g.init_cash - 1) * 100, cash, pnl))
        for code in list(context.portfolio.positions.keys()):
            try:
                pos = context.portfolio.positions[code]
                if pos.total_amount > 0:
                    log.info('   📦 %s %d股 成本%.3f 现价%.3f 市值%.0f 盈亏%+.1f%%' % (
                        code, pos.total_amount, pos.avg_cost, pos.price,
                        pos.total_amount * pos.price, (pos.price / pos.avg_cost - 1) * 100))
            except Exception:
                pass
        g.prev_close_value = tv
    except Exception:
        pass
