#!/usr/bin/env node
// Builds the three 小盘 merge candidates (round 1) from 小市值's pinned epoch-6 baseline.
// Generator, not a strategy: keeps the cross-family transplant byte-identical across candidates
// so the only difference between xp-merge-1 and -2 is the 11:30 exit, and between -1 and -3 the
// honest-accounting base (q-13 + q-15).
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const BASE = path.join(ROOT, 'study', '小市值', 'baseline-e6.py');

const src = fs.readFileSync(BASE, 'utf8');

// ── the transplant: 多因子ML (d02cde29) SMALL_CAP_CONFIG stoploss_strategy=3 ────────────
// (a) market gauge  mean(close/open) over 399100.XSHE constituents on previous_date <= 0.95
//     -> liquidate the book;  (b) per-position  pos.price < avg_cost * 0.91 -> close it.
const CFG = `
    # ===== TRANSPLANT from 多因子ML [[d02cde29_高质量稳定上涨]] — SMALL_CAP_CONFIG 三档止损 =====
    # The one thing 多因子ML contributes to this merge: an explicit loss-cutting exit that does
    # NOT depend on the 11:30 schedule, plus the market filter 小市值 does not have at all.
    # Literal port of small_cap_stoploss() with stoploss_strategy=3.
    g.ml_market_index = '399100.XSHE'   # same index 多因子ML gauges breadth on
    g.ml_stoploss_market = 0.95         # avg stock down 5% from its own open -> liquidate
    g.ml_stoploss_limit = 0.91          # per-position -9% stop
`;

const FN = `

# ===== TRANSPLANT from 多因子ML — small_cap_stoploss(), stoploss_strategy=3 =====
def ml_stoploss(context):
    """多因子ML 的三档止损，原样移植到 小市值 的机器上。
    (a) 大盘闸：前一日 399100 成分股 mean(close/open) <= 0.95 -> 清仓
    (b) 个股闸：pos.price < avg_cost * 0.91 -> 平该仓
    两者都用 context.previous_date / 当日价，不含前视。"""
    data_today = get_current_data()

    try:
        stock_df = get_price(
            security=get_index_stocks(g.ml_market_index),
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'open'],
            count=1, panel=False
        )
        down_ratio = (stock_df['close'] / stock_df['open']).mean()
    except Exception as e:
        log.warn(f"[ML止损] 大盘闸取数失败: {e}")
        down_ratio = 1.0

    if down_ratio <= g.ml_stoploss_market:
        log.info(f"[ML止损] 大盘惨跌 {down_ratio:.2%}，清仓")
        for stock, pos in list(context.portfolio.positions.items()):
            if pos.sellable_amount <= 0:
                continue
            if data_today[stock].last_price == data_today[stock].low_limit:
                continue
            close_position(stock)
        return

    for stock, pos in list(context.portfolio.positions.items()):
        if pos.sellable_amount <= 0:
            continue
        if pos.avg_cost <= 0:
            continue
        if data_today[stock].last_price == data_today[stock].low_limit:
            continue
        if pos.price < pos.avg_cost * g.ml_stoploss_limit:
            log.info(f"[ML止损] 止损 {stock}")
            close_position(stock)
`;

const RUNDAILY = `    run_daily(ml_stoploss, time='10:00', reference_security='399303.XSHE')\n`;

function addTransplant(code) {
  // config into initialize, right after g.target_count
  const anchor = "    g.target_count = 5         # 目标持仓数量（最多同时持有5只股票）\n";
  if (!code.includes(anchor)) throw new Error('config anchor not found');
  code = code.replace(anchor, anchor + CFG);

  // run_daily before the 11:30 sell registration (so the stop fires first in the day)
  const sellReg = "    run_daily(sell, time='11:30', reference_security='399303.XSHE')\n";
  const profitReg = "    run_daily(stop_profit, time='14:50', reference_security='399303.XSHE')\n";
  if (code.includes(sellReg)) {
    code = code.replace(sellReg, RUNDAILY + sellReg);
  } else if (code.includes(profitReg)) {
    code = code.replace(profitReg, RUNDAILY + profitReg);
  } else {
    throw new Error('run_daily anchor not found');
  }

  // function body before the harness OVERRIDE block
  const ov = '# ===== AUTORESEARCH NORMALIZATION OVERRIDE';
  const i = code.indexOf(ov);
  if (i < 0) throw new Error('OVERRIDE block not found — candidate would be UNPINNED');
  return code.slice(0, i) + FN.trimStart() + '\n' + code.slice(i);
}

function dropElevenThirty(code) {
  const sellReg = "    run_daily(sell, time='11:30', reference_security='399303.XSHE')\n";
  if (!code.includes(sellReg)) throw new Error('11:30 registration not found');
  return code.replace(sellReg,
    "    # xp-merge-2: 11:30 破开盘价退出已删除，亏损退出全部交给移植来的 ml_stoploss\n");
}

function honestBase(code) {
  const a = '        money = a1_p * a1_v * 100';
  const b = '    cash_per_stock = available_cash / len(final_buy_list)';
  if (!code.includes(a) || !code.includes(b)) throw new Error('q-18 anchors not found');
  code = code.replace(a, '        money = a1_p * a1_v  # q-13: b1_v 以股计，*100 是 100x 高估');
  code = code.replace(b,
    '    cash_per_stock = min(available_cash / len(final_buy_list), total_value * 0.5 / g.target_count)  # q-15');
  return code;
}

const HDR = (id, what) => `# xp-merge candidate ${id} — 小盘 universe merge round 1 (epoch 6)
# ${what}
# base: study/小市值/baseline-e6.py (7a1c225f) | transplant: 多因子ML d02cde29 small_cap_stoploss
# generated by enhance/candidates/_build-xp-merge.js — do not hand-edit
`;

const out = {
  'xp-merge-1.py': HDR('1', '小市值 baseline-e6 + 多因子ML 三档止损 (ADDED; 11:30 退出保留)')
    + addTransplant(src),
  'xp-merge-2.py': HDR('2', '小市值 baseline-e6, 11:30 退出 -> 多因子ML 三档止损 (REPLACED)')
    + addTransplant(dropElevenThirty(src)),
  'xp-merge-3.py': HDR('3', '小市值 q-18 诚实口径 (q-13 修单位 + q-15 单票上限) + 多因子ML 三档止损')
    + addTransplant(honestBase(src)),
};

for (const [name, code] of Object.entries(out)) {
  const p = path.join(__dirname, name);
  fs.writeFileSync(p, code);
  const pins = ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']
    .filter(m => !code.includes(m));
  console.log(`${name}\t${code.length} chars\tmissingPins=${pins.length ? pins.join(',') : 'none'}`);
}
