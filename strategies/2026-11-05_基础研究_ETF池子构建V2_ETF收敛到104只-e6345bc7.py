# Clone from JoinQuant
# postId: e6345bc798de86376e1b57de5551b57a
# backtestId: 15fabcbda2233e1166444a92cafe76ff
# title: 【基础研究】【ETF池子构建V2】ETF收敛到104只

# 风险及免责提示：该策略仅供学习交流使用，不构成投资建议。
# ============================================================
# 策略：00_ETF基础池子构建（用法示例）
# ============================================================
# 目的：演示「怎么使用 etf_pool.py」—— 核心只有一行：
#
#   pool, scale, meta = yy_build_pool(context.previous_date)
#
# 返回三个字典：
#   pool  = {code: asset_class}                     code -> 六大类分类
#   scale = {code: 规模(亿元)}                      流动性兜底指标
#   meta  = {code: {'name','asset_class','scale',
#                   'index_name','index_code'}}    详细信息（名称/跟踪指数等）
#
# 用法示例：拿到 pool 后按分类取标的
#   wide_base   = [c for c, cls in pool.items() if cls == '股票-宽基']   # 宽基类
#   exclude_bond = [c for c, cls in pool.items() if cls != '债券']        # 剔除债券
#   按规模取前 N 只：codes.sort(key=lambda c: -scale.get(c, 0)); picked = codes[:N]
#
# 本策略每月首个交易日构建一次池子并打印完整结构：
#   六大类数量统计 + 每类明细（code 名称(规模亿)[跟踪指数]），供人核对池子质量。
#   构建结果缓存到 g.pool / g.scale / g.pool_meta，下游逻辑（如 03 等权配置）
#   直接读取即可，无需重复调用。
#
# 池子构建流程（etf_pool.py，粗到细）：
#   1. 全市场场内基金 → 筛 ETF 代码段（剔除 LOF/分级/REITs/货币）
#   2. 上市满 2 年、未退市（剔除新发迷你与临清盘）
#   3. 规模 ≥ 5 亿（份额 × 收盘价，流动性兜底）
#   4. 跟踪指数去重：同一指数只留规模最大一只（FUND_INVEST_TARGET）
#   5. 名称去重兜底：黄金/转债等无跟踪指数的，按名称分组只留规模最大
#   6. 六大类分类：商品/债券/跨境/股息红利/宽基/行业（名称 + 跟踪指数双关键词）
#   7. 容量上限 120 只，超限按规模保留前 N 只
#
# 聚宽多文件说明：本策略 = main.py + etf_pool.py 两个文件。
#   在策略编辑页点「+」新增文件 etf_pool.py，粘贴 etf_pool.py 内容，
#   即可 from etf_pool import yy_build_pool。
#
# ⚠️ 避免未来数据：取数用 context.previous_date（上一交易日，收盘已定）。
# ============================================================
from jqdata import *
from etf_pool import yy_build_pool


__version__ = "2.0.1"
# 自修改自动更新版本号（pre-commit hook 自动维护）


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('order', 'error')
    set_slippage(FixedSlippage(3 / 10000))
    # ETF 费用：type='fund'，close_tax=0，open/close_commission=0.0002
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0,
                  open_commission=0.0002, close_commission=0.0002,
                  close_today_commission=0, min_commission=5),
        type='fund')

    g.pool = {}          # {code: asset_class}
    g.scale = {}         # {code: 规模(亿元)}
    g.pool_meta = {}     # {code: {name, asset_class, scale, index_name, index_code}}

    # 每月首个交易日 10:00：重建池子并缓存结果（全月复用，不重复调用）
    run_monthly(jq_build_pool, 1, '10:00')


def jq_build_pool(context):
    """怎么获取池子：yy_build_pool(交易日) 一行调用，返回 (pool, scale, meta)。"""
    log.info('\n########## 月初 ETF 池子重建 ##########')
    pool, scale, meta = yy_build_pool(context.previous_date)  # ← 核心用法
    g.pool, g.scale, g.pool_meta = pool, scale, meta

    if not pool:
        log.warn('池子为空：请检查 etf_pool 模块参数与数据源')
        return

    # 六大类数量统计，一眼看清池子构成
    cls_count = {}
    for c, cls in pool.items():
        cls_count[cls] = cls_count.get(cls, 0) + 1
    log.info('【池子】共 %d 只: %s', len(pool),
             ' '.join(f'{k}{v}只' for k, v in sorted(cls_count.items())))

    # 每大类完整列表（一行一只：code 名称(规模亿)，序号/总数），便于核对分类与去重：
    #   池子已是「同一指数只留规模最大一只」，这里再按规模排序方便人工核对；
    #   每大类之间空两行，日志一眼区分六大类
    for cls in ['股票-宽基', '股票-行业', '股票-股息红利', '跨境', '债券', '商品']:
        codes = [c for c, cc in pool.items() if cc == cls]
        if not codes:
            continue
        codes.sort(key=lambda c: -scale.get(c, 0))   # 按规模降序
        log.info('')
        log.info('')
        for i, c in enumerate(codes, 1):
            m = meta[c]
            log.info('  %s[%d/%d]: %s %s(%.0f亿)',
                     cls, i, len(codes), c.split('.')[0], m['name'], scale.get(c, 0))
