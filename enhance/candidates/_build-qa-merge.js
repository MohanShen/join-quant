#!/usr/bin/env node
'use strict';
// Builder for the 全A universe MERGE round (epoch 6).
//
//   base   : study/打板短线/baseline-e6.py  (439385b4, obj 0.9668 — the bar)
//   donor  : study/红利低频/baseline.py     (93379f98, obj 0.1348)
//
// Every candidate = the base BYTE-FOR-BYTE (incl. the frozen epoch-6 OVERRIDE it
// already carries) + one declared diff. The donor mechanism is imported as its
// OWN measured object: the 1:1 rank-sum of (dy-TTM desc, 20d turnover asc) over
// trailing-365d implemented cash-dividend payers, computed with 红利低频's exact
// code and refreshed on 红利低频's own 25-trading-day cadence (its q-6 shows the
// phase is insensitive, so the cadence is the mechanism's, not a tuned knob).
//
// Run: node enhance/candidates/_build-qa-merge.js
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const BASE = path.join(ROOT, 'study', '打板短线', 'baseline-e6.py');
const OUT = __dirname;

const src = fs.readFileSync(BASE, 'utf8');
const MARK = '# ===== AUTORESEARCH NORMALIZATION OVERRIDE';
const cut = src.indexOf(MARK);
if (cut < 0) throw new Error('OVERRIDE block not found in base');
const body = src.slice(0, cut);
const override = src.slice(cut);

function must(hay, needle, what) {
  const n = hay.split(needle).length - 1;
  if (n !== 1) throw new Error(`anchor ${what}: expected 1 occurrence, got ${n}`);
}
function patch(hay, needle, repl, what) {
  must(hay, needle, what);
  return hay.replace(needle, repl);
}

// ---------------------------------------------------------------- donor import
// Verbatim transcription of 红利低频's measure (study/红利低频/baseline.py):
//   dy_ttm  = sum(bonus_ratio_rmb/10) over implemented plans with a_registration_date
//             in (prev_date-365d, prev_date]  /  prev close
//   t20     = mean turnover_ratio over the last 20 valuation days to prev_date
//   rank    = 3*rank(dy desc) + 3*rank(t20 asc)      <- 1:1, untouched (its q-9)
const DONOR = `

# ===== 红利低频 (93379f98) 机制导入 — 全A MERGE round, epoch 6 =====================
# 逐字照搬 study/红利低频/baseline.py 的两条腿与 1:1 排名和（其 q-9 证明 1:1 是单峰，
# 不得重调）；刷新节奏沿用它自己的 25 个交易日（其 q-6 证明相位不敏感）。
# 活的 edge 只有两条：流动性溢价 (measured) 与 股息率 第 3 版措辞 (measured，
# 「作为与低换手等权的联合排名腿」)。前两版 股息率 是 refuted/superseded，不采用；
# 故股息率只以联合排名腿的形式出现，绝不单独使用（其 q-1：单用 obj -0.2658）。
from jqdata import finance
import numpy as np
from datetime import timedelta as _qa_td

QA_CYCLE = 25          # 红利低频 自己的轮动周期


def _qa_payer_table(context):
    prev_date = context.previous_date
    all_stocks = get_all_securities(['stock'], date=context.current_dt.date())
    all_stocks = all_stocks[~all_stocks.index.str.startswith('688')]
    stock_list = list(all_stocks.index)
    cd = get_current_data()
    stock_list = [s for s in stock_list if not cd[s].paused]

    start_date = prev_date - _qa_td(days=365)
    q = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.bonus_ratio_rmb,
        finance.STK_XR_XD.a_registration_date,
        finance.STK_XR_XD.plan_progress
    ).filter(
        finance.STK_XR_XD.code.in_(stock_list),
        finance.STK_XR_XD.a_registration_date >= str(start_date),
        finance.STK_XR_XD.a_registration_date <= str(prev_date),
        finance.STK_XR_XD.plan_progress == '实施方案'
    )
    df_all = []
    offset = 0
    while True:
        b = finance.run_query(q.offset(offset).limit(4000))
        if b is None or len(b) == 0:
            break
        df_all.append(b)
        if len(b) < 4000:
            break
        offset += 4000
    if not df_all:
        return None
    df_div = pd.concat(df_all, ignore_index=True)
    df_div = df_div[df_div['bonus_ratio_rmb'].notna() & (df_div['bonus_ratio_rmb'] > 0)]
    if len(df_div) == 0:
        return None
    df_div['dps'] = df_div['bonus_ratio_rmb'] / 10.0
    dps_ttm = df_div.groupby('code')['dps'].sum()

    price_stocks = list(dps_ttm.index)
    price_df = get_price(price_stocks, end_date=prev_date, frequency='daily',
                         fields=['close'], count=1, panel=False)
    price_dict = dict(zip(price_df['code'], price_df['close']))
    dy = {}
    for s in price_stocks:
        if s in price_dict and price_dict[s] > 0:
            dy[s] = dps_ttm[s] / price_dict[s]
    dy_series = pd.Series(dy)
    if len(dy_series) == 0:
        return None

    turnover = {}
    plist = list(dy_series.index)
    for i in range(0, len(plist), 500):
        batch = plist[i:i + 500]
        dv = get_valuation(batch, end_date=prev_date, count=20,
                           fields=['code', 'turnover_ratio'])
        if dv is not None and len(dv) > 0:
            turnover.update(dv.groupby('code')['turnover_ratio'].mean().to_dict())
    t_series = pd.Series(turnover)

    df = pd.DataFrame({'dy_ttm': dy_series, 'turnover_20d': t_series}).dropna()
    df = df[df['dy_ttm'] > 0]
    if len(df) == 0:
        return None
    df['dy_rank'] = df['dy_ttm'].rank(ascending=False, method='min')
    df['turnover_rank'] = df['turnover_20d'].rank(ascending=True, method='min')
    df['total_rank'] = df['dy_rank'] * 3 + df['turnover_rank'] * 3
    return df


def _qa_refresh(context):
    """每 25 个交易日刷新一次派息/换手排名表（红利低频 自己的节奏）。"""
    if not hasattr(g, 'qa_day'):
        g.qa_day = 0
        g.qa_tbl = None
        g.qa_t_med = None
        g.qa_pool = None
        g.qa_block_start = False
    g.qa_day += 1
    g.qa_block_start = (g.qa_day % QA_CYCLE) == 1
    if g.qa_tbl is not None and not g.qa_block_start:
        return
    try:
        tbl = _qa_payer_table(context)
    except Exception as _e:
        print('qa_refresh failed: %s' % _e)
        return
    g.qa_tbl = tbl
    if tbl is None or len(tbl) == 0:
        g.qa_t_med, g.qa_pool = None, None
        return
    g.qa_t_med = float(tbl['turnover_20d'].median())
    k = max(1, int(len(tbl) / 3))
    g.qa_pool = set(tbl.nsmallest(k, 'turnover_20d').index)
    print('qa table: payers=%d  t20 median=%.3f%%  lowest-tercile pool=%d'
          % (len(tbl), g.qa_t_med, len(g.qa_pool)))
# ===== 红利低频 机制导入 结束 =====================================================
`;

const ANCHOR_IMPORTS = "from datetime import datetime,timedelta,date\n";
const ANCHOR_ACC = `def after_code_changed(context):
    g.n_days_limit_up_list = []   #重新初始化列表`;
const ANCHOR_BUY = `def buy(context):
    current_data = get_current_data()
    qualified_stocks =  get_stock_list(context)
    if qualified_stocks:
        value = context.portfolio.available_cash / len(qualified_stocks)`;
const ANCHOR_NEWSTOCK = "    initial_list = filter_new_stock(initial_list, today)\n";
// NB: the base has a trailing space after the colon on this line — keep it explicit.
const ANCHOR_GSL = 'def get_stock_list(context):\u0020\n'
  + '    target_list, target_list2=prepare_stock_list(context)';
const ANCHOR_SBGK_MONEY =
  "        if avg_price_increase_value < 0.07 or prev_day_data['money'][0] < 5.5e8 or prev_day_data['money'][0] > 20e8:";
const ANCHOR_RZQ_MONEY =
  "        if avg_price_increase_value < -0.04 or prev_day_data['money'][-1] < 3e8 or prev_day_data['money'][-1] > 19e8:";
const ANCHOR_HL = "    hl_list = get_hl_stock(initial_list, yesterday, 1)     # 昨日涨停\n";
const ANCHOR_SELL_LOOP = `    for s in list(context.portfolio.positions):
        close_data = attribute_history(s, 4, '1d', ['close'])`;

const HEAD = (n, title, what) => `# qa-merge candidate ${n} — 全A universe MERGE round 1 (epoch 6)
# ${title}
# base : study/打板短线/baseline-e6.py (439385b4, obj 0.9668 = the bar)
# donor: study/红利低频/baseline.py    (93379f98, obj 0.1348)
# diff : ${what}
# generated by enhance/candidates/_build-qa-merge.js — do not hand-edit
`;

// ============================================================ candidate 1
// 低关注派息池内打板 — inclusion, ADDITIVE.
// 打板's machine runs unchanged inside 红利低频's lowest-20d-turnover TERCILE of
// the dividend-payer pool. That population is not a tuned width: it is exactly
// the set 红利低频's q-8a measured (lowest turnover tercile among payers).
let c1 = body;
c1 = patch(c1, ANCHOR_IMPORTS, ANCHOR_IMPORTS + DONOR, 'c1 imports');
c1 = patch(c1, ANCHOR_BUY, `def buy(context):
    _qa_refresh(context)          # QA-MERGE-1
    current_data = get_current_data()
    qualified_stocks =  get_stock_list(context)
    if qualified_stocks:
        value = context.portfolio.available_cash / len(qualified_stocks)`, 'c1 buy');
c1 = patch(c1, ANCHOR_NEWSTOCK, ANCHOR_NEWSTOCK + `    # QA-MERGE-1：把初始池收到「派息股中 20 日换手率最低的三分之一」
    # ——红利低频 q-8a 测过的那个总体。其余一字不动。
    if g.qa_pool:
        initial_list = [s for s in initial_list if s in g.qa_pool]
`, 'c1 pool');
fs.writeFileSync(path.join(OUT, 'qa-merge-1.py'),
  HEAD(1, '低关注派息池内打板 (inclusion, additive)',
    "prepare_stock_list 的初始池 ∩ 红利低频 派息股中 20 日换手最低三分之一 (q-8a 的总体)；其余逐字不动")
  + c1 + override);

// ============================================================ candidate 2
// 低关注派息条件替换手调成交额带 — inclusion, SUBSTITUTIVE.
// 打板's two hand-tuned prior-day 成交额 bands (5.5e8–20e8 / 3e8–19e8) are the
// family's own acknowledged blind spot (§4: ~10 untested constants, one probe
// q-5 found its band near non-binding) and u-nolimit showed the filters are NOT
// the source. Replace exactly those two conditions with 红利低频's measured
// liquidity formulation: payer AND 20d turnover <= the payer pool's median.
let c2 = body;
c2 = patch(c2, ANCHOR_IMPORTS, ANCHOR_IMPORTS + DONOR + `

def _qa_low_attention(s):
    """红利低频 的 流动性溢价 (measured, q-2/q-10) + 股息率 第 3 版 (联合排名腿)：
    必须是近 12 个月的现金派息股，且 20 日平均换手率不高于派息池中位数。"""
    tbl = g.qa_tbl
    if tbl is None or g.qa_t_med is None or len(tbl) == 0:
        return False
    if s not in tbl.index:
        return False
    return float(tbl.at[s, 'turnover_20d']) <= g.qa_t_med
`, 'c2 imports');
c2 = patch(c2, ANCHOR_BUY, `def buy(context):
    _qa_refresh(context)          # QA-MERGE-2
    current_data = get_current_data()
    qualified_stocks =  get_stock_list(context)
    if qualified_stocks:
        value = context.portfolio.available_cash / len(qualified_stocks)`, 'c2 buy');
c2 = patch(c2, ANCHOR_SBGK_MONEY,
  "        # QA-MERGE-2：手调成交额带 5.5e8–20e8 -> 红利低频 的低关注派息条件\n"
  + "        if avg_price_increase_value < 0.07 or not _qa_low_attention(s):", 'c2 sbgk');
c2 = patch(c2, ANCHOR_RZQ_MONEY,
  "        # QA-MERGE-2：手调成交额带 3e8–19e8 -> 红利低频 的低关注派息条件\n"
  + "        if avg_price_increase_value < -0.04 or not _qa_low_attention(s):", 'c2 rzq');
fs.writeFileSync(path.join(OUT, 'qa-merge-2.py'),
  HEAD(2, '低关注派息条件替换手调成交额带 (inclusion, substitutive)',
    "两条前日成交额带 (5.5e8–20e8 / 3e8–19e8) -> 派息 且 20 日换手 <= 派息池中位数；其余逐字不动")
  + c2 + override);

// ============================================================ candidate 3
// 情绪门控下的资本交接 — CAPITAL, regime switch.
// dbdx-imp-3 measured a limit-up-breadth gate at -0.1245: it produced 4/4
// positive half-years but parked the gated-off capital in CASH. This candidate
// changes only where that capital goes: into 红利低频's top-10 rank-sum book,
// held for the block at 红利低频's native 25-day horizon. One capital pool, one
// priority rule, no weights — so guard rule 3 stays inert by construction.
let c3 = body;
c3 = patch(c3, ANCHOR_IMPORTS, ANCHOR_IMPORTS + DONOR + `

def _qa_decide_block(context):
    """块首决定本 25 日块的资本归谁。门控形式照搬 dbdx-imp-3（昨日原始涨停家数
    低于其前 20 日中位数 ⇒ 打板的 edge 缺席），一个先验值，不扫。"""
    if len(g.qa_hl_counts) < 21:
        g.qa_block_on = True
        return
    hist = g.qa_hl_counts[-21:-1]
    g.qa_block_on = bool(g.qa_hl_counts[-1] >= float(np.median(hist)))
    print('qa block: hl=%d median20=%.1f -> %s'
          % (g.qa_hl_counts[-1], float(np.median(hist)), '打板' if g.qa_block_on else '红利'))


def qa_park(context):
    """14:50（在打板的 sell 之后）：只在块首动作。
    门控开 -> 清掉停泊仓，资本明日 09:26 归打板；
    门控关 -> 全账户按 红利低频 的选法（14:50、等权、total_value/10）停泊一个块。"""
    if not g.qa_block_start:
        return
    cd = get_current_data()
    if g.qa_block_on:
        for s in list(g.qa_parked):
            if s in context.portfolio.positions and not cd[s].paused:
                order_target_value(s, 0)
        g.qa_parked = []
        return
    tbl = g.qa_tbl
    if tbl is None or len(tbl) == 0:
        return
    targets = list(tbl.sort_values('total_rank', ascending=True).index[:10])
    for s in list(context.portfolio.positions):
        if s not in targets and not cd[s].paused:
            order_target_value(s, 0)
    tv = context.portfolio.total_value / 10.0
    for s in targets:
        if not cd[s].paused:
            order_target_value(s, tv)
    g.qa_parked = targets
`, 'c3 imports');
c3 = patch(c3, ANCHOR_ACC, ANCHOR_ACC + `
    g.qa_hl_counts = []           # QA-MERGE-3：昨日原始涨停家数序列
    g.qa_block_on = True
    g.qa_parked = []
    g.qa_pending = False`, 'c3 acc');
c3 = patch(c3, `    run_daily(sell, time='14:50', reference_security='000300.XSHG')`,
  `    run_daily(sell, time='14:50', reference_security='000300.XSHG')
    run_daily(qa_park, time='14:50', reference_security='000300.XSHG')   # QA-MERGE-3，注册在 sell 之后`,
  'c3 schedule');
c3 = patch(c3, ANCHOR_BUY, `def buy(context):
    _qa_refresh(context)          # QA-MERGE-3
    if g.qa_block_start:
        g.qa_pending = True
    current_data = get_current_data()
    qualified_stocks =  get_stock_list(context)
    if qualified_stocks:
        # QA-MERGE-3：打板对资本有绝对优先权——同 bar 先清停泊仓再买
        for _p in list(g.qa_parked):
            if _p in context.portfolio.positions and not current_data[_p].paused:
                order_target_value(_p, 0)
        g.qa_parked = []
        value = context.portfolio.available_cash / len(qualified_stocks)`, 'c3 buy');
c3 = patch(c3, ANCHOR_GSL, ANCHOR_GSL + `
    if g.qa_pending:               # QA-MERGE-3：家数已记录，定本块归属
        _qa_decide_block(context)
        g.qa_pending = False
    if not g.qa_block_on:          # 本块资本在 红利低频 书里，不选股
        return []`, 'c3 gsl');
c3 = patch(c3, ANCHOR_HL, ANCHOR_HL + `    g.qa_hl_counts.append(len(hl_list))   # QA-MERGE-3：腿过滤前的原始家数（= dbdx-imp-3 的口径）
`, 'c3 breadth');
c3 = patch(c3, ANCHOR_SELL_LOOP, `    for s in list(context.portfolio.positions):
        if s in g.qa_parked:       # QA-MERGE-3：停泊仓按 红利低频 的 25 日节奏持有，不走打板的出场
            continue
        close_data = attribute_history(s, 4, '1d', ['close'])`, 'c3 sell');
fs.writeFileSync(path.join(OUT, 'qa-merge-3.py'),
  HEAD(3, '情绪门控下的资本交接 (capital, regime switch)',
    "每 25 日块首：昨日涨停家数 >= 前 20 日中位数 -> 打板独占全账户；否则全账户停泊在 红利低频 top-10 排名和书里一个块")
  + c3 + override);

for (const f of ['qa-merge-1.py', 'qa-merge-2.py', 'qa-merge-3.py']) {
  const p = path.join(OUT, f);
  console.log(`${f}  ${fs.readFileSync(p, 'utf8').split('\n').length} lines`);
}
