# Clone from JoinQuant
# postId: d274a9c9c83a8c188387448dce486930
# backtestId: 8742d0f7673ce7d38f07b81b9dc32223
# title: 红利策略改造记：年化 19.4%、9 年超额全正

# -*- coding: utf-8 -*-
"""
红利低波 + 红利价值 月度轮动策略（v2：基准口径 + 排名缓冲带 + 价值陷阱过滤）
原策略：聚宽社区 wywy1995《红利可以抄底吗》 https://www.joinquant.com/post/61657
v1：hongli_fixed.py（修 bug，逻辑与原版一致）

======================= v2 新增（对应回测复盘的三条结论） =======================
【改进 1】含息基准：把"基准被低估"这块水分挤掉
  平台 set_benchmark('000015.XSHG') 是价格指数，不含股息；而策略在 use_real_price=True
  下是收现金分红的。上证红利股息率长期 5%~6%，5.8 年复利下来基准被低估约 35%，
  于是"超额收益 176.99%/Alpha 0.209"里有一大块是口径造成的。
  v2 在策略内部自建一条含息基准曲线，每月打印三个数：
      策略累计 / 含息基准累计 / 真实超额
  口径优先级：
      ① g.tr_bench_code 指定的 ETF（默认 510880 上证红利ETF）后复权收盘价
         —— 后复权 = 分红再投资净值，且不使用未来数据（前复权会用到未来分红，不能用）
      ② 取不到 → 退回 000015 价格 × (1+假定股息率)^年数 估算，并在日志里标注"估算"
  想彻底改掉平台显示的基准，把 set_benchmark 那行的注释打开即可。

【改进 2】排名缓冲带（buffer）：把边界抖动造成的换手砍掉
  v1 实测：单边月换手 51%（年化 6.1 倍）、286 笔买入里有 53 笔是"卖出后 60 天内又买回"。
  原因是每月只取前 N 名，卡在第 N 名附近的股票反复进出（如工行 2022-08 卖 → 09 买）。
  v2 规则：新进必须进前 N，已持有只要还在前 N×g.buffer_ratio 就保留。
  持仓只数不变（仍是 5+3），换手显著下降。
     g.buffer_ratio = 1.6  → 低波 保留区 前 8，价值 保留区 前 5
     g.buffer_ratio = None → 关闭缓冲，完全等同 v1（用来做 A/B 对照）

【改进 3】价值陷阱过滤：直接针对 2023 年那 13.54% 回撤
  v1 实测回撤窗口（2023-05~2024-01）里，红利价值分支持有过 通威股份 / 藏格矿业 / 双良节能，
  都是"PE 极低 + 股息率极高 + 净利润同比 +100%" —— 而这恰好是周期股盈利顶部的标准形态：
  E 是周期峰值 → PE 最低，大额分红 → 股息率最高。用"低 PE + 高股息"选股，在周期顶部是
  最精确的买入信号，而不是安全边际。
  v2 在红利价值分支加两道闸：
    ① 股息率上限 g.trap_div_max（默认 10%）：可持续股息率极少超过 10%，
       超过的多是周期顶利润或特别分红（市值下跌还会把历史股息率进一步推高）
    ② ROE 稳定性：取最近 4 期中报的 ROE(扣非)（每年 9/25 时点查询，那时最新披露的就是中报），
       算变异系数 CV = std/|mean|，CV > g.trap_cv_max（默认 0.5）视为利润大起大落 → 剔除。
       银行中报 ROE 常年 5.5%~6%，CV 约 0.03，稳过；通威 2019~2022 中报 ROE 约 5%/6%/15%/25%，
       CV ≈ 0.65，剔掉。
       ★★ 踩过的坑：最初用 get_fundamentals(..., statDate='2019') 取年报，
          聚宽在 set_option('avoid_future_data', True) 下会直接抛
          "回测中 get_fundamentals 不支持 statDate 参数"，424 次全部失败、过滤静默失效。
          现改为 date='YYYY-09-25'，既绕开限制，又因为时点固定在过去，
          avoid_future_data 会按 pub_date 过滤，天然不含未来数据。
  红利低波分支不加这两道闸：它按 beta 最低选，天然选不到高 beta 的周期成长股。

【改进 4】财务安全过滤（v2.3，只作用于红利价值分支）
  v2.1 实跑 2018-01~2026-10 后发现的漏网之鱼：红利价值分支在 2018~2020 买过 11 笔地产/困境股
  —— 华夏幸福、新城控股、绿地控股、荣盛发展、银亿股份、深大通、三湘印象、新黄浦。
  共同点：暴雷前的 ROE 是"稳定高位"（华夏幸福 2015~2018 常年 20%+ 且波动很小），
  所以改进 3 的 ROE 变异系数天生抓不到 —— 它只能识别"盈利波动"，识别不了"盈利靠借钱撑"。
  v2.3 改为盯经营活动现金流（真分红必须有真现金）：
    · 取最近 g.cash_min_years(默认3) 期年报的"经营活动产生的现金流量净额"
    · 规则：最新一期 > 0、至少 g.cash_min_positive(默认2) 年为正、累计 > 0
    · 银行/保险/证券豁免（它们的经营现金流含存款、保证金变动，口径完全不同，不能一起比）
    · ★ 取数用 finance.run_query 且 pub_date <= 昨日，不用 statDate / 不用当前时点，
      天然不含未来数据；查询失败会 log.error 并 fail-open（宁可漏杀，不可错杀）
  可选第二道闸 g.cash_debt_max（默认 None 关闭）：资产负债率上限，如设 0.70。

【v1 已修的 11 项 bug】见 hongli_fixed.py 文件头，本次未回退，全部保留。

【怎么做 A/B 对照】把下面四个开关都关掉，就和 v1 等价（基准追踪只打日志，不影响交易）：
     g.buffer_ratio = None      # 关缓冲带
     g.trap_cv_max = None       # 关 ROE 稳定性过滤
     g.trap_div_max = None      # 关股息率上限
     g.cash_min_years = None    # 关经营现金流过滤（v2.3 新增）
  已跑过的对照：v1 / v2.1(前三项) / v2.3(四项)，结论见文件末版本的实测数字。

【仍未改动】（属策略设计，不是 bug）
 - 高价股"一手买不起"被剔除后不补位（吉比特/茅台，v1 实测 9 次）→ 会少一个仓位
 - 行业权重上限：银行仍占持仓月 30%、类债合计约 48%
 - 任何"抄底"择时：原策略没有，v2 也没有
================================================================
"""

import datetime
import re

from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

from jqdata import *
from jqfactor import get_factor_values

# 放在 jqdata 的 * 导入之后，避免被通配符导入的 datetime 遮蔽
from datetime import timedelta

# ---- 版本 ----
#   v2.0  初版：含息基准 + 排名缓冲带 + 价值陷阱过滤
#         ★ ROE 过滤用 get_fundamentals(statDate=...) 取年报，在 avoid_future_data=True 下
#           被聚宽拒绝，424 次全部失败、过滤静默失效（2026-10-31 首次回测发现）
#   v2.1  仅修 ROE 取数方式：改 date='YYYY-09-25' 取中报。其余逻辑与 v2.0 完全一致。
#   v2.3  在 v2.1 基础上加【改进 4】财务安全过滤（经营现金流 3 年为正 + 银行豁免），
#         用于挡掉 v2.1 漏过的 11 笔地产/困境股。v2.1 的其余开关与逻辑一字未动。
#         ★ v2.3 首跑 425.90% 与 v2.1 完全一致 → 现金流取数失败、整道过滤 fail-open。
#           原因是聚宽财务表的列是动态生成的，字段名写错不会在 getattr 阶段报错，
#           要到 run_query 才抛异常，被我自己的 try/except 吞掉退化成"无事发生"。
#   v2.3.1 取数改自愈：候选字段名逐个试查 → 都失败则读表头自动匹配 → 全失败才停用，
#         并明确打印用的是哪个字段。其余逻辑同 v2.3。
#         ★ v2.3.1 实跑 425.90%，仍与 v2.1 逐位相同。但这次不是现金流的问题：
#           日志显示 106/106 期把整个候选池（如 52/52）全判成"金融股"而豁免，
#           现金流字段探测一次都没跑到。根因是 k in ind 用了子串匹配，而
#           get_security_info().industry 返回的不是单个行业名，关键词全部命中。
#   v2.3.2 金融股识别改两条独立通道：名称看关键词、行业用 get_industry 白名单**精确匹配**；
#         再加一道比例兜底（豁免超 60% 就退回仅按名称识别并 log.error 打印样本）。
#         ★ v2.3.2 实跑仍然 106/106 期整池被判为金融股——而且"退回仅按名称识别"后
#           依然 52/52，可样本里"清新环境"等名称根本不含金融关键词，纯逻辑上不可能。
#           远程无法定位运行时哪一环失真，v2.3.3 改为结构性免疫：
#           ① 名称/行业两通道各自计数、逐月打印；
#           ② 行业通道只看 sw_l1（第一段）、去罗马数字后缀后精确匹配；
#           ③ 任一通道整体失灵(>50%) → 降级；两道都失灵 → 整道停用并 log.error（绝不再静默）；
#           ④ 首月打印 repr 级诊断（名称/行业/白名单原样），隐形字符或被改动的常量都会现形。
#   v2.3.4 v2.3.3 实跑结果：行业通道（精确匹配）完全正常（每期 0~1 只，与真实金融股对应），
#           名称通道（in 子串匹配）仍然 52/52 全员命中——"清新环境"对这组关键词做子串
#           匹配在标准 Python 里不可能为 True，说明运行时 str 的 in 行为不可信。
#           ★ 行业通道走的是 == 精确匹配（正常），名称通道走的是 in 子串（异常），
#             两条通道唯一的环境差异就是匹配算子 → v2.3.4 名称通道改用 re.search
#             （sre 引擎匹配，不走 str.__contains__），绕开可疑的 in；
#           ② initialize 加字符串自检（工商银行→应为True / 清新环境→应为False），
#             首月逐键打印匹配表 + any/正则双路对比，运行时异常一锤定音；
#           ③ 降级策略修正：v2.3.3 在名称通道失灵时把整道过滤停用，白白扔掉正常的
#             行业通道。改为：名称失灵→只信行业通道继续过滤；行业也失灵→才整道停用。
#   v2.3.5 v2.3.4 实跑：过滤器完全正常生效（自检过、83 期全执行、零异常），收益
#           425.9% → 349.4%（年化 21.4%→18.7%）。差距解剖：
#           ① 2018-19 荣盛发展(8期)/华夏幸福(3期)——正是本过滤的设计目标（借钱分红的
#             地产股），属于"主动付的保险费"；但本次回测路径里 v2.1 后来也没再持有它们，
#             2021 地产暴雷的防御价值未在回测窗口内兑现；
#           ② 2022 起最大拖累是"最新年报经营现金流为负"这一条：四川路桥(-10.2亿，
#             建筑垫资模式)、华致酒行(-3.7亿，备货)等单年 OCF 为负的行业常态股被杀。
#           → v2.3.5 只放开这一条：g.cash_require_latest = False，保留
#             「3 年中≥2 年为正 且 累计为正」的底线（荣盛发展 3年1正、唐德影视累计负
#             仍会被剔）。预期捞回单年 OCF 为负但整体造血正常的公司，其余不变。
VERSION = "v2.3.5"


# ---------------------------------------------------------------- 初始化

def initialize(context):
    # 版本号：每次改动都往上加，回测日志第一行会打出来，便于对照是哪一版跑的
    log.info("========== 策略版本 {} ==========".format(VERSION))

    # ★ 字符串环境自检：三组结果应分别为 True / False / False / ('银行', 2)。
    #   若"清新环境"被判成金融股或"银行"长度不是 2，说明运行环境的字符串
    #   比较不可信（粘贴损坏/编码错乱），后续财务安全过滤会自动降级处理。
    try:
        _t1 = _name_is_financial(u"工商银行")
        _t2 = _name_is_financial(u"清新环境")
        _t3 = _name_is_financial(u"贵州茅台")
        log.info("自检：工商银行→{}（应True） 清新环境→{}（应False） 贵州茅台→{}（应False） len('银行')={}".format(
            _t1, _t2, _t3, len(u"银行")))
        if not _t1 or _t2 or _t3:
            log.error("自检失败！名称识别在本环境不可信，财务安全过滤将依赖行业通道/自动降级")
    except Exception as _e:
        log.error("字符串自检异常：{}".format(_e))

    # 系统设置
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    # 平台展示用基准（价格指数，不含股息，保留是为了和历史结果可比）
    set_benchmark("000015.XSHG")
    # 若想让平台直接显示含息基准（聚宽支持用 ETF 作基准，但同样不复权），可改成：
    # set_benchmark("510880.XSHG")

    log.set_level("order", "warning")      # 资金不足/部分成交必须看得见
    log.set_level("history", "error")
    log.set_level("system", "error")

    # 显式交易成本（佣金万 2.5、卖出印花税万 5、最低 5 元）与滑点
    set_order_cost(OrderCost(open_tax=0,
                             close_tax=0.0005,
                             open_commission=0.00025,
                             close_commission=0.00025,
                             close_today_commission=0,
                             min_commission=5), type="stock")
    set_slippage(FixedSlippage(0.002))

    # ---- 组合结构 ----
    g.target_num = [5, 3]          # 红利低波 5 只 + 红利价值 3 只
    g.buffer_ratio = 1.6           # ★改进2 排名缓冲带；设 None 则关闭（等同 v1）

    # ---- 交易参数 ----
    g.buy_limit_premium = 0.03     # 买入限价 = 昨收 × 1.03；设 None 则用分板块涨停价

    # ---- ★改进3 价值陷阱过滤（只作用于红利价值分支）----
    g.trap_div_max = 0.10          # 股息率上限；设 None 关闭
    g.trap_cv_max = 0.50           # ROE 变异系数上限；设 None 关闭
    g.trap_min_years = 3           # 至少拿到几期财报才做稳定性判断

    # ---- ★改进4 财务安全过滤（v2.3，只作用于红利价值分支）----
    g.cash_min_years = 3           # 看最近几期年报的经营现金流；设 None 关闭整道过滤
    g.cash_min_positive = 2        # 这 N 年里有几年必须为正
    g.cash_require_latest = False  # 最新一期年报是否必须为正（v2.3.5 放开：单年 OCF 为负
                                   # 对建筑垫资/备货经销等行业是常态；底线由
                                   # "3年中≥2年为正 且 累计为正" 承担）
    g.cash_debt_max = None         # 资产负债率上限（0.70=70%）；None=不用这道理
    # 金融股豁免名单见模块级 FIN_NAME_KEYS（名称关键词）+ FIN_IND_NAMES（行业白名单）
    g._cash_field = "?"            # 现金流字段名缓存（首次调用时自动探测）

    # ---- ★改进1 含息基准 ----
    g.tr_bench_code = "510880.XSHG"   # 上证红利ETF；若聚宽有中证红利全收益，可换 'H00922.XSHG'
    g.bench_div_yield = 0.055         # 兜底估算用的年化股息率（仅当 ETF 取不到时使用）
    g.bench = {"mode": None, "px0": None, "start": None, "code": None}

    # ---- 状态 ----
    g.hold_list = []
    g.high_limit_list = []
    g.target_list = []
    g.sell_list = []
    g.buy_df = _empty_buy_df()
    g.trade_date = None

    # 交易时间
    run_daily(prepare_stock_list, "09:00")
    run_monthly(get_stock_list, 1, "09:01")
    run_daily(execute_sell, "09:30")
    run_daily(execute_buy, "09:31")
    run_daily(check_limit_up, "14:45")


def _empty_buy_df():
    df = pd.DataFrame(columns=["name", "prev_close", "limit_price"])
    df.index.name = "code"
    return df


# ---------------------------------------------------------------- 盘前准备

def prepare_stock_list(context):
    """记录持仓，并找出"昨日涨停"的持仓股"""
    g.hold_list = list(context.portfolio.positions)
    g.high_limit_list = []
    if not g.hold_list:
        return

    df = get_price(g.hold_list, end_date=context.previous_date, frequency="daily",
                   fields=["close", "high_limit"], count=1, panel=False,
                   skip_paused=False, fill_paused=False).dropna()
    hit = df[(df["close"] - df["high_limit"]).abs() < 1e-6]
    g.high_limit_list = list(hit["code"])


# ---------------------------------------------------------------- 选股

def get_stock_list(context):
    yesterday = context.previous_date
    today = context.current_dt
    log.info("==================== {} 调仓 ====================".format(str(today)[:10]))

    # ---------- 初始过滤 ----------
    initial_list = get_all_securities("stock", today).index.tolist()
    raw_n = len(initial_list)
    initial_list = filter_new_stock(context, initial_list)
    new_n = len(initial_list)
    initial_list = filter_kcb_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    log.info("  股票池：全部 {} → 剔除次新 {} → 剔除科创/北交/ST/停牌 {}".format(
        raw_n, new_n, len(initial_list)))
    if not initial_list:
        _reset_plan()
        _log_bench(context, yesterday)
        return

    held = set(g.hold_list)

    # ---------- 红利低波 ----------
    hldb_pool = get_dividend_ratio_filter_list(context, initial_list, False, 0.00, 0.10, 0.03)
    log.info("  红利低波｜股息率前 10% 且 > 3%：{} 只".format(len(hldb_pool)))
    hldb_ranked = get_factor_filter_list(context, hldb_pool, "beta", True, 0.00, 0.50)
    log.info("  红利低波｜beta 最低的 50%：{} 只".format(len(hldb_ranked)))
    HLDB_list, HLDB_kept = select_with_buffer(hldb_ranked, g.target_num[0], held, g.buffer_ratio)

    # ---------- 红利价值 ----------
    df = get_fundamentals(query(
        valuation.code,
    ).filter(
        valuation.code.in_(initial_list),
        # 合理的财务指标，既避免价值陷阱，也防止畸高收益
        valuation.pe_ratio.between(5, 50),                                    # 市盈率
        indicator.inc_return.between(5, 100),                                 # 净资产收益率(扣非)(%)
        indicator.inc_total_revenue_year_on_year.between(5, 100),             # 营业总收入同比(%)
        indicator.inc_net_profit_year_on_year.between(10, 100),               # 净利润同比(%)
    ), date=yesterday)                                                        # ★ 补 date
    stock_list = list(df["code"]) if len(df) else []
    log.info("  红利价值｜财务质量四项筛选：{} 只".format(len(stock_list)))

    # ★改进3：价值陷阱过滤（ROE 稳定性）
    stock_list = roe_stability_filter(context, stock_list, yesterday)
    log.info("  红利价值｜ROE 稳定性过滤后：{} 只".format(len(stock_list)))

    # ★改进4：财务安全过滤（经营现金流 / 可选资产负债率）
    stock_list = cashflow_safety_filter(context, stock_list, yesterday)
    log.info("  红利价值｜财务安全过滤后：{} 只".format(len(stock_list)))

    # ★改进3：股息率上限（同时保留原有的 >3% 下限）
    hljz_ranked = get_dividend_ratio_filter_list(context, stock_list, False, 0.00, 0.10, 0.03,
                                                 upper=g.trap_div_max)
    log.info("  红利价值｜股息率前 10% 且 3%~{}：{} 只".format(
        "∞" if g.trap_div_max is None else "{:.0%}".format(g.trap_div_max), len(hljz_ranked)))
    HLJZ_list, HLJZ_kept = select_with_buffer(hljz_ranked, g.target_num[1], held, g.buffer_ratio)

    # ---------- 目标组合（保序去重） ----------
    target_list = list(dict.fromkeys(HLDB_list + HLJZ_list))
    kept_by_buffer = list(dict.fromkeys(HLDB_kept + HLJZ_kept))
    log.info("  目标组合 {} 只（持有 {} 只，其中靠缓冲带保留 {} 只：{}）：{}".format(
        len(target_list), len(held), len(kept_by_buffer), kept_by_buffer, target_list))

    g.target_list = target_list
    if not target_list:
        log.warn("  目标组合为空：本月空仓。若连续多月如此，请先看上面的股息率中位数是否异常")
    g.sell_list = [s for s in g.hold_list
                   if s not in target_list and s not in g.high_limit_list]
    buy_list = [s for s in target_list if s not in g.hold_list]

    # ---------- 生成买入计划（只算价格，资金在执行时点重算） ----------
    g.buy_df = _empty_buy_df()
    if buy_list:
        px = get_price(buy_list, end_date=yesterday, frequency="1d", count=1,
                       fields=["close"], fq="pre", panel=False,
                       skip_paused=False, fill_paused=True).set_index("code")["close"]
        rows = []
        for s in buy_list:
            info = get_security_info(s, yesterday)
            prev_close = float(px.loc[s])
            rows.append({
                "code": s,
                "name": info.display_name,
                "prev_close": prev_close,
                "limit_price": get_limit_price(context, s, prev_close, info.display_name),
            })
        g.buy_df = pd.DataFrame(rows).set_index("code")

    g.trade_date = today.date()

    log.info("  卖出 {} 只：{}".format(len(g.sell_list), g.sell_list))
    if not g.buy_df.empty:
        log.info("  买入计划：\n{}".format(g.buy_df))

    _log_bench(context, yesterday)


def _reset_plan():
    g.target_list = []
    g.sell_list = []
    g.buy_df = _empty_buy_df()


# ---------------------------------------------------------------- ★改进2：排名缓冲带

def select_with_buffer(ranked, n, held, ratio):
    """从排名列表里选 n 只，带缓冲带（纯函数，可离线单测）

    ranked: 已按优先级排好序的代码列表（前 n 名 = 原版会直接买的那几只）
    n     : 该分支的目标只数
    held  : 当前持仓集合
    ratio : 缓冲倍数。None 或 <=1 → 关闭缓冲，直接返回 ranked[:n]（等同 v1）

    规则：
      1) 新进必须先进入前 n 名（和前 n 名里的老持仓一起构成核心区）
      2) 已持有、且排名还在前 int(round(n*ratio)) 内的，即使滑出前 n 也保留，
         占掉核心区排名最靠后的名额
    返回 (selection, kept_extra)
      selection : 最终选出的代码，按 ranked 顺序排列
      kept_extra: 仅因缓冲带才留下的代码（用于日志）
    """
    if n <= 0 or not ranked:
        return [], []
    if not ratio or ratio <= 1.0:
        return list(ranked[:n]), []

    keep_n = max(n, int(round(n * ratio)))
    core = list(ranked[:n])
    buffer_zone = list(ranked[n:keep_n])

    result = [s for s in core if s in held]
    rooms = n - len(result)
    kept_extra = []
    if rooms > 0:
        for s in buffer_zone:
            if rooms <= 0:
                break
            if s in held and s not in result:
                result.append(s)
                kept_extra.append(s)
                rooms -= 1

    for s in core:
        if len(result) >= n:
            break
        if s not in result:
            result.append(s)

    order = dict((c, i) for i, c in enumerate(ranked))
    result.sort(key=lambda s: order.get(s, 10 ** 6))
    return result, kept_extra


# ---------------------------------------------------------------- ★改进3：价值陷阱过滤

def roe_cv(series_by_code, min_years=3):
    """ROE 变异系数（纯函数，可离线单测）

    series_by_code: {code: [roe_year1, roe_year2, ...]}，含 None/NaN 会被跳过
    返回 {code: cv}，有效年份不足 min_years 或均值接近 0 的不出现在结果里
    """
    out = {}
    for code, vals in series_by_code.items():
        xs = []
        for v in vals:
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if f != f:                      # NaN
                continue
            xs.append(f)
        if len(xs) < min_years:
            continue
        mean = sum(xs) / len(xs)
        if abs(mean) < 1e-9:
            continue
        var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
        out[code] = (var ** 0.5) / abs(mean)
    return out


def roe_report_years(today, n=4):
    """取 n 个"中报已披露"的年份（纯函数，可离线单测）

    每年 8/31 是中报披露截止日，10/1 起 Q3 陆续出来。
    → 10/1 之后才认为"当年中报"+之前的都到位；否则只算到上一年。
    """
    latest = today.year if (today.month, today.day) >= (10, 1) else today.year - 1
    return [latest - i for i in range(n)]


def roe_stability_filter(context, stock_list, yesterday):
    """用"最近 4 期中报的 ROE(扣非)"变异系数剔除利润大起大落的周期股

    ★ 为什么用 date 而不是 statDate：
      聚宽在 set_option('avoid_future_data', True) 下，回测中 get_fundamentals
      不支持 statDate 参数（会直接抛异常），只能传 date。
      所以这里在"每年 9/25"这个时点查询——那一刻最新已披露的财报就是当年中报。
      好处：① 不触发 API 限制；② 4 期都是半年报，口径一致可比；
            ③ 时点固定在过去，avoid_future_data 按 pub_date 过滤，天然不含未来数据。
    """
    cv_max = getattr(g, "trap_cv_max", None)
    if cv_max is None or not stock_list:
        return list(stock_list)

    years = roe_report_years(yesterday, 4)
    log.info("    ROE 稳定性：取 {}~{} 中报 ROE（均已披露，不含未来数据）".format(
        years[-1], years[0]))

    frames = []
    for y in years:
        q = query(indicator.code, indicator.inc_return).filter(
            indicator.code.in_(stock_list))
        try:
            d = get_fundamentals(q, date="{}-09-25".format(y))
        except Exception as e:
            log.warn("    取 {} 中报 ROE 失败：{}".format(y, e))
            d = None
        if d is None or not len(d):
            continue
        frames.append(d.set_index("code")["inc_return"].rename(str(y)))

    if len(frames) < g.trap_min_years:
        log.warn("    财报只取到 {} 期（<{}），本次跳过 ROE 稳定性过滤".format(
            len(frames), g.trap_min_years))
        return list(stock_list)

    # sort=False：几期财报的股票集合不完全一致，默认排序会触发 FutureWarning 刷屏
    df = pd.concat(frames, axis=1, sort=False)
    # 转成 {code: [roe...]} 交给纯函数算 CV，避免依赖各版本 pandas 的 axis 语义
    series_by_code = {}
    for code, row in df.iterrows():
        series_by_code[code] = list(row.values)
    cv = roe_cv(series_by_code, g.trap_min_years)

    keep, drop = [], []
    for s in stock_list:
        if s in cv and cv[s] <= cv_max:
            keep.append(s)
        else:
            drop.append(s)
    if drop:
        show = ["{}={:.2f}".format(s, cv[s]) for s in drop[:8] if s in cv]
        log.info("    ROE 稳定性剔除 {} 只（CV>{:.2f}），例：{}".format(len(drop), cv_max, show))
    return keep


# ---------------------------------------------------------------- ★改进4：财务安全过滤（v2.3）

def cash_ok(values, min_years=3, min_positive=2, require_latest=True):
    """判断一家公司的"年度经营现金流净额"是否健康（纯函数，可离线单测）

    values: 按年份升序的年度经营现金流净额（单位：元），最新一期在最后
    返回 (是否通过, 原因字符串)

    规则（三条同时满足）：
      ① 最新一期 > 0                    —— 现在就在造血，不是靠卖资产/借钱撑
      ② 最近 N 年里至少 min_positive 年为正
      ③ 最近 N 年累计 > 0                —— 防止"小赚三年抵不过一次巨亏"
    """
    if not values:
        return False, "无经营现金流数据"
    if len(values) < min_years:
        return False, "年报不足 {} 期（仅 {}）".format(min_years, len(values))
    vals = list(values)[-min_years:]
    if require_latest and vals[-1] <= 0:
        return False, "最新年报经营现金流为负({:.1f}亿)".format(vals[-1] / 1e8)
    pos = sum(1 for v in vals if v > 0)
    if pos < min_positive:
        return False, "{}年中仅{}年为正".format(len(vals), pos)
    total = sum(vals)
    if total <= 0:
        return False, "{}年累计为负({:.1f}亿)".format(len(vals), total / 1e8)
    return True, "ok"


def _sec_name(code, yesterday):
    """取"昨日"的证券简称（时点安全，不使用未来信息）"""
    try:
        info = get_security_info(code, yesterday)
    except Exception:
        return ""
    return getattr(info, "display_name", "") or ""


# 名称关键词：A 股金融机构的法定简称几乎都带这些词（工商银行/中信证券/新华保险/安信信托…）
FIN_NAME_KEYS = ("银行", "农商行", "保险", "证券", "信托", "人寿", "太保", "人保", "平安", "期货")
# 名称通道改用正则匹配：re.search 由 sre 引擎逐字符匹配，不经过 str.__contains__。
# 背景：v2.3.2/v2.3.3 两版实跑中，用 in 做子串匹配的名称通道都把整个候选池判成金融股，
# 而同一运行环境里用 == 精确匹配的行业通道完全正常——怀疑点集中 in 算子本身。
FIN_NAME_RE = re.compile(u"|".join(FIN_NAME_KEYS))


def _name_is_financial(name):
    """通道①：名称关键词（纯正则，不依赖 str.__contains__）"""
    if not name:
        return False
    try:
        return bool(FIN_NAME_RE.search(name))
    except Exception:
        # 正则失灵时退回逐键 == 分段比对（不使用 in）
        return any(name.find(k) >= 0 for k in FIN_NAME_KEYS)
# 行业名白名单：只做**精确匹配**，绝不做子串匹配
FIN_IND_NAMES = set([
    "银行", "银行Ⅱ", "非银金融", "保险", "保险Ⅱ", "保险业",
    "证券", "证券Ⅱ", "资本市场服务", "多元金融", "信托",
    "货币金融服务", "其他金融业",
])


def _norm_ind(name):
    """行业名归一化：去掉尾部的申万级别罗马数字后缀（公用事业I → 公用事业）"""
    s = str(name).strip()
    while True:
        for suf in ("Ⅰ", "Ⅱ", "Ⅲ", "IV", "III", "II", "I"):
            if s.endswith(suf) and len(s) > len(suf):
                s = s[:-len(suf)].strip()
                break
        else:
            return s


def _ind_is_financial(ind):
    """通道②：行业白名单（纯函数）——只看第一段（申万一级），归一化后**精确**匹配

    ★ 只看 sw_l1 的原因：申万一级是 ~28 个值的固定枚举（银行/非银金融/食品饮料…），
      精确匹配不可能"全员命中"；后面的 sw_l2/jq/zjw 层级名称不可控，一律不参与判断。
    """
    if not ind:
        return False
    return _norm_ind(str(ind).split("/")[0]) in ("银行", "非银金融")


def _industry_names(stock_list, yesterday):
    """用 get_industry 取"昨日"的行业名，返回 {code: "行业1/行业2"}

    取不到就返回空 dict（调用方只用名称兜底，不会崩）。
    """
    out = {}
    try:
        raw = get_industry(stock_list, date=yesterday)
    except Exception as e:
        log.warn("    财务安全：get_industry 失败（{}），本次仅按名称识别金融股".format(e))
        return out
    if not raw:
        return out
    try:
        for s in stock_list:
            d = raw.get(s) or {}
            got = []
            for k in ("sw_l1", "sw_l2", "jq_l1", "jq_l2", "zjw"):
                v = d.get(k)
                if isinstance(v, dict):
                    nm = v.get("industry_name") or v.get("industry") or ""
                    if nm:
                        got.append(str(nm))
            out[s] = "/".join(got)
    except Exception as e:
        log.warn("    财务安全：解析行业结构失败（{}），本次仅按名称识别".format(e))
        return {}
    return out


CASH_FIELD_CANDIDATES = [
    "net_operate_cash_flow",          # 经营活动产生的现金流量净额（聚宽 STK_CASHFLOW_STATEMENT 标准名）
    "net_cash_flows_oper_act",        # 部分数据源用的别名
    "net_cash_flow_operating",
    "net_operate_cash_flows",
]


def _probe_cash_field(field, yesterday, min_years):
    """用一只必然存在的股票试查一次，能取到数据就说明这个字段名可用"""
    probe = ["601398.XSHG", "600900.XSHG"]
    time0 = yesterday - timedelta(days=365 * (min_years + 2))
    tb = finance.STK_CASHFLOW_STATEMENT
    q = query(tb.code, tb.end_date, tb.pub_date, getattr(tb, field)).filter(
        tb.code.in_(probe),
        tb.pub_date <= yesterday,
        tb.end_date >= time0,
    )
    d = finance.run_query(q)
    return d is not None and len(d) > 0


def _resolve_cash_field(yesterday, min_years):
    """自动探测可用的现金流字段名，并缓存在 g 里（每个回测只探一次）

    ★ 为什么需要探测：聚宽财务表的"列"是动态生成的，写错字段名时不会在
      getattr 阶段报错，而是到 run_query 才抛，或者干脆返回空表。
      硬编码一个名字一旦写错，整道过滤就静默失效——v2.3 首跑就是这么废掉的。
      这里改成：候选名逐个试查 → 都失败则读表头自动挑 → 全失败才放弃。
    """
    cached = getattr(g, "_cash_field", "?")
    if cached != "?":
        return cached

    name = None
    for f in CASH_FIELD_CANDIDATES:
        try:
            if _probe_cash_field(f, yesterday, min_years):
                name = f
                log.info("    财务安全：现金流字段探测通过 → {}".format(f))
                break
        except Exception as e:
            log.warn("    财务安全：字段 {} 试查失败（{}）".format(f, e))

    if name is None:
        # 候选名全挂：直接读表头，从列名里挑含 net+oper+cash 的那一列
        try:
            head = finance.run_query(query(finance.STK_CASHFLOW_STATEMENT).limit(1))
            cols = [str(c) for c in getattr(head, "columns", [])]
            pick = [c for c in cols if "net" in c.lower() and "oper" in c.lower()
                    and "cash" in c.lower()]
            log.info("    财务安全：表头含 {} 列，匹配到 {}".format(len(cols), pick[:4]))
            for c in pick:
                try:
                    if _probe_cash_field(c, yesterday, min_years):
                        name = c
                        break
                except Exception:
                    continue
        except Exception as e:
            log.warn("    财务安全：读表头失败（{}）".format(e))

    g._cash_field = name
    if name is None:
        log.error("    财务安全：没有找到可用的现金流字段，本道过滤停用（选股结果与 v2.1 相同）")
    return name


def _cashflow_annual(codes, yesterday, min_years):
    """批量取年报经营现金流净额，返回 {code: [按年份升序的净额]}

    只用 pub_date <= yesterday 的记录 → 不引入未来数据。
    聚宽 finance.run_query 单次最多 4000 行，按 300 只一批拆分。
    """
    field = _resolve_cash_field(yesterday, min_years)
    if field is None:
        return None
    tb = finance.STK_CASHFLOW_STATEMENT
    time0 = yesterday - timedelta(days=365 * (min_years + 1))
    out = {}
    interval = 300
    for i in range(0, len(codes), interval):
        batch = list(codes[i:i + interval])
        try:
            q = query(tb.code, tb.end_date, tb.pub_date, getattr(tb, field)).filter(
                tb.code.in_(batch),
                tb.pub_date <= yesterday,
                tb.end_date >= time0,
            )
            d = finance.run_query(q)
        except Exception as e:
            log.error("    取经营现金流失败：{}".format(e))
            return None                      # None 表示整道过滤失效（fail-open）
        if d is None or not len(d):
            continue
        for code, end_date, pub_date, ocf in zip(
                d["code"], d["end_date"], d["pub_date"], d[field]):
            # 只要年报（end_date 落在 12 月）；季报/中报是累计数，混进来会重复计算
            try:
                month = end_date.month
            except AttributeError:
                month = int(str(end_date)[5:7])
            if month != 12:
                continue
            try:
                val = float(ocf)
            except (TypeError, ValueError):
                continue
            if val != val:
                continue
            year = str(end_date)[:4]
            # 同一会计年度若有更正/合并与母公司两版，取绝对值最大的那版
            # （合并报表口径的规模一定不小于母公司报表，用它才代表集团真实造血能力）
            bucket = out.setdefault(code, {})
            if year not in bucket or abs(val) > abs(bucket[year]):
                bucket[year] = val
    # 按年份升序输出
    return dict((c, [v[y] for y in sorted(v.keys())]) for c, v in out.items())


def cashflow_safety_filter(context, stock_list, yesterday):
    """★改进4：用经营现金流剔除"高股息但没钱"的公司（只作用于红利价值分支）

    为什么需要它：v2.1 里 ROE 变异系数抓不到地产/困境股——它们暴雷前 ROE 稳定在 20%+，
    波动很小，但利润是靠负债堆出来的。真正的预警在现金流：经营性现金流长期为负，
    却还在大额分红，等于借钱分红，暴雷只是时间问题。
    """
    if not stock_list:
        return list(stock_list)
    min_years = getattr(g, "cash_min_years", None)
    debt_max = getattr(g, "cash_debt_max", None)
    if min_years is None and debt_max is None:
        return list(stock_list)

    # ---- 豁免金融股（经营现金流含存款/保证金变动，口径完全不同）----
    # ★ 结构：名称/行业两条独立通道，各自计数、逐月打印；
    #   任一通道把 >50% 的候选池判成金融股 → 该通道视为失灵，降级；
    #   两道都失灵 → 整道过滤停用（最坏= v2.1 行为），绝不静默地"全员豁免"。
    names = {}
    for s in stock_list:
        names[s] = _sec_name(s, yesterday)
    inds = _industry_names(stock_list, yesterday)

    name_fin = [s for s in stock_list if _name_is_financial(names[s])]
    ind_fin = [s for s in stock_list if _ind_is_financial(inds.get(s, ""))]
    protected = list(dict.fromkeys(name_fin + ind_fin))
    log.info("    财务安全：名称通道(正则)金融 {} 只 / 行业通道 {} 只 / 拟豁免 {} 只".format(
        len(name_fin), len(ind_fin), len(protected)))

    # 首月诊断：repr 级别原样输出，隐形字符/被改动的常量/字段格式异常都会现形
    if not getattr(g, "_fin_dbg_done", False) and stock_list:
        g._fin_dbg_done = True
        s0 = stock_list[0]
        log.info("    财务安全[诊断] 代码={} name={!r} ind={!r} 名称通道={} 行业通道={}".format(
            s0, names[s0], inds.get(s0, ""), s0 in name_fin, s0 in ind_fin))
        log.info("    财务安全[诊断] FIN_NAME_KEYS={!r}".format(FIN_NAME_KEYS))
        # ★ 一锤定音：对首只股票逐键打印三种匹配路径的结果（in / find / 正则）。
        #   若三者不一致，即可锁定运行时哪一环失真；若一致且合理，则函数逻辑可信。
        probe = names[s0]
        tbl_in = [(k, (k in probe)) for k in FIN_NAME_KEYS]
        tbl_find = [(k, probe.find(k) >= 0) for k in FIN_NAME_KEYS]
        tbl_re = bool(FIN_NAME_RE.search(probe)) if probe else False
        log.info("    财务安全[诊断] in匹配={} find匹配={} 正则={}".format(
            tbl_in, tbl_find, tbl_re))

    n0 = len(stock_list)
    name_bad = n0 >= 8 and len(name_fin) > 0.5 * n0
    ind_bad = n0 >= 8 and len(ind_fin) > 0.5 * n0
    if name_bad or ind_bad:
        sample = ["{!r}|{!r}".format(names[s], inds.get(s, "")) for s in stock_list[:6]]
        log.error("    财务安全：通道异常 名称={}/{} 行业={}/{} 样本：{}".format(
            len(name_fin), n0, len(ind_fin), n0, sample))
        if name_bad and not ind_bad:
            # 名称通道失灵但行业通道正常 → 只信行业通道，继续过滤（v2.3.3 在这里
            # 直接整道停用，白白扔掉了一个明明正常的通道）
            log.error("    财务安全：名称通道失灵 → 本次仅按行业通道豁免，现金流过滤继续")
            protected = ind_fin
        elif ind_bad and not name_bad:
            log.error("    财务安全：行业通道失灵 → 本次仅按名称通道豁免，现金流过滤继续")
            protected = name_fin
        else:
            log.error("    财务安全：两条通道都异常 → 本道过滤整道停用，"
                      "选股结果将与 v2.1 相同。FIN_NAME_KEYS={!r}".format(FIN_NAME_KEYS))
            return list(stock_list)

    cand = [s for s in stock_list if s not in protected]
    if protected:
        log.info("    财务安全｜金融股口径不同，豁免 {} 只：{}".format(
            len(protected), [names[s] for s in protected[:12]]))

    keep, reason = [], {}

    # ---- 第一道：经营现金流 ----
    if min_years is not None and cand:
        cash = _cashflow_annual(cand, yesterday, min_years)
        if cash is None:
            log.error("    财务安全：取数失败，本次整道跳过 —— 选股结果将与 v2.1 完全相同")
            return list(stock_list)
        if not cash:
            # 一条都没取到，多半是字段名/权限问题，绝不能因此把整个池子清空
            log.error("    经营现金流一条都没取到（疑似字段名或权限问题），本次跳过财务安全过滤")
            return list(stock_list)
        log.info("    财务安全：取到 {} / {} 只的年报现金流".format(len(cash), len(cand)))
        for s in cand:
            ok, why = cash_ok(cash.get(s, []),
                              min_years=min_years,
                              min_positive=getattr(g, "cash_min_positive", 2),
                              require_latest=getattr(g, "cash_require_latest", True))
            if ok:
                keep.append(s)
            else:
                reason[s] = why
        cand = keep
        if reason:
            show = ["{}({})".format(names.get(s, s), reason[s]) for s in list(reason)[:8]]
            log.info("    财务安全剔除 {} 只，例：{}".format(len(reason), show))
            if len(reason) > 0.8 * (len(reason) + len(keep)):
                log.warn("    财务安全过滤一次剔掉 {:.0%} 的候选池，条件偏严，"
                         "可把 g.cash_min_positive 调成 1 或 g.cash_min_years 调成 2".format(
                             float(len(reason)) / (len(reason) + len(keep))))

    # ---- 第二道（可选）：资产负债率 ----
    if debt_max is not None and cand:
        try:
            q = query(balance.code, balance.total_liability, balance.total_assets).filter(
                balance.code.in_(cand))
            d = get_fundamentals(q, date=yesterday)
            ratio = {}
            for code, tl, ta in zip(d["code"], d["total_liability"], d["total_assets"]):
                try:
                    ta = float(ta)
                    if ta > 0:
                        ratio[code] = float(tl) / ta
                except (TypeError, ValueError):
                    pass
            kept, cut = [], 0
            for s in cand:
                r = ratio.get(s)
                if r is not None and r > debt_max:
                    cut += 1
                    reason[s] = "资产负债率{:.0%}".format(r)
                else:
                    kept.append(s)
            cand = kept
            if cut:
                log.info("    财务安全｜资产负债率>{:.0%} 再剔 {} 只".format(debt_max, cut))
        except Exception as e:
            log.warn("    资产负债率取数失败，跳过该道：{}".format(e))

    # ---- 按原顺序拼回（保持选股优先级）----
    final = set(cand)
    return ([s for s in stock_list if s in final or s in protected])


# ---------------------------------------------------------------- 交易

def execute_sell(context):
    if g.trade_date != context.current_dt.date() or not g.sell_list:
        return
    cd = get_current_data()
    for s in list(g.sell_list):
        if s not in context.portfolio.positions:
            continue
        if cd[s].paused:
            log.warn("{} 停牌，无法卖出".format(s))
            continue
        if cd[s].last_price <= cd[s].low_limit:
            log.warn("{} 跌停，无法卖出".format(s))
            continue
        order_target_value(s, 0)
        log.info("卖出 {}".format(s))
    g.sell_list = []


def execute_buy(context):
    if g.trade_date != context.current_dt.date() or g.buy_df.empty:
        return

    df = g.buy_df.copy()
    g.buy_df = _empty_buy_df()
    cd = get_current_data()

    df = df[~df.index.isin(list(context.portfolio.positions))]
    if df.empty:
        return

    plans = []
    for s in df.index:
        if cd[s].paused:
            log.warn("{} 停牌，跳过买入".format(s))
            continue
        if cd[s].last_price >= cd[s].high_limit:
            log.warn("{} 已涨停，跳过买入".format(s))
            continue
        plans.append({"code": s,
                      "name": df.at[s, "name"],
                      "prev_close": df.at[s, "prev_close"],
                      "limit_price": df.at[s, "limit_price"]})
    if not plans:
        return

    # 用执行时点的真实可用现金做资金分配
    executable, dropped = plan_orders(plans, context.portfolio.available_cash)
    for code, name, reason in dropped:
        log.warn("{} {} {}".format(code, name, reason))

    for item in executable:
        od = order(item["code"], item["lots"] * 100, LimitOrderStyle(item["limit_price"]))
        if od is None:
            log.warn("{} {} 下单失败（资金不足？）".format(item["code"], item["name"]))
            continue
        log.info("买入 {} {} {} 股，限价 {:.2f}".format(
            item["code"], item["name"], item["lots"] * 100, item["limit_price"]))


def plan_orders(plans, cash):
    """资金分配（纯函数，可离线单测）

    plans: [{"code","name","prev_close","limit_price"}]
    返回 (executable, dropped)
      executable: [{"code","name","lots","limit_price","max_cost"}]
      dropped:    [(code, name, reason)]
    规则：
      1) 反复剔除"一手都买不起"的标的，剩余标的重新均分预算（原版会下发 amount=0 的废单）
      2) 股数一律按"限价"（最坏成交价）定量与预留，合计永不超出现金，杜绝超买
    """
    executable, dropped = [], []
    pool = list(plans)
    if not pool or cash <= 0:
        return executable, dropped

    per = cash / len(pool)
    while pool:
        too_dear = [p for p in pool if p["limit_price"] * 100 > per]
        if not too_dear:
            break
        if len(too_dear) == len(pool):
            # 均分后全都买不起一整份预算：退化为只留最便宜的一只
            keep = [min(pool, key=lambda x: x["limit_price"])]
            for p in pool:
                if p is not keep[0]:
                    dropped.append((p["code"], p["name"], "一手需 {:.0f} 元 > 单只预算 {:.0f} 元，剔除".format(
                        p["limit_price"] * 100, per)))
            pool = keep
            per = cash / len(pool)
            break
        for p in too_dear:
            dropped.append((p["code"], p["name"], "一手需 {:.0f} 元 > 单只预算 {:.0f} 元，剔除并重新分配".format(
                p["limit_price"] * 100, per)))
        pool = [p for p in pool if p not in too_dear]
        if not pool:
            return executable, dropped
        per = cash / len(pool)

    est_cash = cash
    for p in pool:
        lots = int(per / p["limit_price"] / 100)
        lots = min(lots, int(est_cash / p["limit_price"] / 100))
        if lots <= 0:
            dropped.append((p["code"], p["name"], "可买 0 手，跳过"))
            continue
        max_cost = lots * 100 * p["limit_price"]
        est_cash -= max_cost
        executable.append({"code": p["code"], "name": p["name"], "lots": lots,
                           "limit_price": p["limit_price"], "max_cost": max_cost})
    return executable, dropped


def check_limit_up(context):
    """昨日涨停股：尾盘仍封板就继续持有，打开则卖出"""
    if not g.high_limit_list:
        return
    cd = get_current_data()
    for s in list(g.high_limit_list):
        if s not in context.portfolio.positions:
            g.high_limit_list.remove(s)
            continue
        if s in g.target_list:
            continue
        if cd[s].paused or cd[s].last_price <= cd[s].low_limit:
            continue
        if cd[s].last_price < cd[s].high_limit:
            order_target_value(s, 0)
            log.info("{} 涨停打开，卖出".format(s))


# ---------------------------------------------------------------- ★改进1：含息基准

def _etf_px(day):
    """ETF 后复权收盘价。后复权 = 分红再投资净值，且不依赖未来数据（前复权会用到未来分红）"""
    code = getattr(g, "tr_bench_code", None)
    if not code:
        return None
    try:
        df = get_price(code, end_date=day, count=1, fields=["close"],
                       fq="post", panel=False)
    except Exception as e:
        log.warn("  取 {} 后复权价失败：{}".format(code, e))
        return None
    if df is None or not len(df):
        return None
    v = df["close"].iloc[0]
    if pd.isna(v):
        return None
    return float(v)


def _index_px(day):
    try:
        df = get_price("000015.XSHG", end_date=day, count=1, fields=["close"], panel=False)
    except Exception:
        return None
    if df is None or not len(df):
        return None
    v = df["close"].iloc[0]
    return None if pd.isna(v) else float(v)


def _init_bench(day):
    if g.bench["mode"] is not None:
        return
    px = _etf_px(day)
    if px is not None:
        g.bench.update(mode="etf", px0=px, start=day, code=g.tr_bench_code)
        log.info("  含息基准：{} 后复权 {} 起，初始 {:.4f}".format(g.tr_bench_code, day, px))
        return
    px = _index_px(day)
    if px is not None:
        g.bench.update(mode="index_yield", px0=px, start=day, code="000015.XSHG")
        log.warn("  取不到 ETF 数据，含息基准退回「000015 价格 × (1+{:.1%})^年数」估算".format(
            g.bench_div_yield))


def bench_cum(day):
    """返回含息基准累计收益；取不到返回 None"""
    b = g.bench
    if b["px0"] is None or b["start"] is None:
        return None
    if b["mode"] == "etf":
        px = _etf_px(day)
        return None if px is None else px / b["px0"] - 1.0
    px = _index_px(day)
    if px is None:
        return None
    years = max((day - b["start"]).days, 1) / 365.0
    return (px / b["px0"]) * ((1.0 + g.bench_div_yield) ** years) - 1.0


def _log_bench(context, yesterday):
    """每月打印：策略累计 vs 含息基准累计，并折算年化"""
    _init_bench(yesterday)
    start = getattr(context.portfolio, "starting_cash", None)
    if start is None:
        start = context.portfolio.total_value
    strat = context.portfolio.total_value / float(start) - 1.0

    bench = bench_cum(yesterday)
    if bench is None:
        log.info("  【累计】策略 {:.1%}（含息基准取数失败，本月只报策略）".format(strat))
        return

    excess = (1.0 + strat) / (1.0 + bench) - 1.0
    days = max((yesterday - g.bench["start"]).days, 1)
    if days >= 180:
        sa = (1.0 + strat) ** (365.0 / days) - 1.0
        ba = (1.0 + bench) ** (365.0 / days) - 1.0
        log.info("  【累计】策略 {:.1%}（年化 {:.1%}）｜ 含息基准 {:.1%}（年化 {:.1%}）｜ "
                 "真实超额 {:.1%}（年化差 {:.1%}）｜ 口径 {}".format(
                     strat, sa, bench, ba, excess, sa - ba,
                     "ETF后复权" if g.bench["mode"] == "etf" else "价格+股息估算"))
    else:
        log.info("  【累计】策略 {:.1%} ｜ 含息基准 {:.1%} ｜ 真实超额 {:.1%}".format(
            strat, bench, excess))


# ---------------------------------------------------------------- 涨跌停价

def get_limit_price(context, code, prev_close, name):
    """买入限价

    g.buy_limit_premium = 0.03  → 昨收 × 1.03（默认）：成交概率高、最坏预留只多 3%
    g.buy_limit_premium = None  → 按板块的真·涨停价（主板 10% / 创业板 20% / 科创板 20% / 北交所 30% / ST 5%）
    """
    premium = getattr(g, "buy_limit_premium", None)
    if premium is None:
        today = str(context.current_dt)[:10]
        if name and ("ST" in name or "*" in name or "退" in name):
            premium = 0.05
        elif code[:3] in ("688", "689"):
            premium = 0.20
        elif code[:3] in ("300", "301") and today >= "2020-08-24":
            premium = 0.20
        elif code[0] in ("4", "8"):
            premium = 0.30
        else:
            premium = 0.10

    price = Decimal(str(prev_close)) * (Decimal("1") + Decimal(str(premium)))
    return float(price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------- 过滤函数

def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].paused]


def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list
            if not current_data[s].is_st
            and "ST" not in current_data[s].name
            and "*" not in current_data[s].name
            and "退" not in current_data[s].name]


def filter_kcb_stock(stock_list):
    """剔除科创板(68x)与北交所(4/8 开头)"""
    return [s for s in stock_list
            if s[0] not in ("4", "8") and s[:2] != "68"]


def filter_new_stock(context, stock_list):
    """上市满 250 个自然日"""
    yesterday = context.previous_date
    return [s for s in stock_list
            if yesterday - get_security_info(s).start_date >= timedelta(days=250)]


# ---------------------------------------------------------------- 股息率筛选

def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2, threshold, upper=None):
    """按"最近 12 个月已登记分红 / 当前总市值"计算股息率并筛选

    upper: 股息率上限（改进3 用来剔除"周期顶利润撑起来的高股息"）；None = 不设上限
    """
    if not stock_list:
        return []

    time1 = context.previous_date
    time0 = time1 - timedelta(days=365)
    interval = 1000          # finance.run_query 单次上限 4000 行，一只票一年可能多次分红，留足余量

    parts = []
    for i in range(0, len(stock_list), interval):
        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.a_registration_date,
            finance.STK_XR_XD.bonus_amount_rmb,
        ).filter(
            finance.STK_XR_XD.a_registration_date >= time0,
            finance.STK_XR_XD.a_registration_date <= time1,
            finance.STK_XR_XD.code.in_(stock_list[i:i + interval]),
        )
        parts.append(finance.run_query(q))

    parts = [p for p in parts if p is not None and len(p)]
    if not parts:
        return []
    raw = pd.concat(parts, ignore_index=True)

    dividend = raw.set_index("code").groupby(level=0)["bonus_amount_rmb"].sum().to_frame()
    temp_list = list(dividend.index)
    if not temp_list:
        return []

    cap = get_fundamentals(query(valuation.code, valuation.market_cap)
                           .filter(valuation.code.in_(temp_list)), date=time1)
    cap = cap.set_index("code")

    df = dividend.join(cap, how="inner")
    if df.empty:
        return []

    # ★ 单位换算（原版就是对的，别乱改）：
    #   本表 bonus_amount_rmb 与 valuation.market_cap 的量级差恒为 1e4——
    #   无论是「派现(万元) / 市值(亿元)」还是「派现(元) / 市值(万元)」，系数都是 1e-4。
    #   → dividend_ratio 就是股息率小数（0.03 = 3%）
    df["dividend_ratio"] = df["bonus_amount_rmb"] / (df["market_cap"] * 1e4)

    med = float(df["dividend_ratio"].median())
    top = float(df["dividend_ratio"].max())
    passed = int((df["dividend_ratio"] > threshold).sum())
    log.info("    股息率：中位数 {:.4f}，最高 {:.4f}，>{:.0%} 的 {} 只".format(
        med, top, threshold, passed))
    if med < 1e-4:
        log.warn("    股息率量级偏小（{:.6f}），单位换算可能又改错了".format(med))
    elif med > 1:
        log.warn("    股息率量级偏大（{:.2f}），单位换算可能改错了".format(med))

    df = df.sort_values(by="dividend_ratio", ascending=sort)
    df = df[int(p1 * len(df)):int(p2 * len(df))]
    df = df[df["dividend_ratio"] > threshold]
    if upper is not None:
        n_before = len(df)
        df = df[df["dividend_ratio"] <= upper]
        if n_before != len(df):
            log.info("    股息率上限 {:.0%} 剔除 {} 只".format(upper, n_before - len(df)))
    return list(df.index)


# ---------------------------------------------------------------- 因子排序

def get_factor_filter_list(context, stock_list, factor_name, sort, p1, p2):
    if not stock_list:
        return []
    yesterday = context.previous_date
    values = get_factor_values(stock_list, factor_name, end_date=yesterday, count=1)[factor_name]
    if values is None or values.empty:
        return []
    df = pd.DataFrame({"code": stock_list, "score": values.iloc[0].tolist()})
    df = df.dropna()
    if df.empty:
        return []
    df.sort_values(by="score", ascending=sort, inplace=True)
    return list(df["code"])[int(p1 * len(df)):int(p2 * len(df))]
