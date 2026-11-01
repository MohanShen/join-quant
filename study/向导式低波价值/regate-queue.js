// gatekeeper 2026-11-01: one-off queue re-gate after u-1/u-2. Run via
//   node -e "require('./study/向导式低波价值/regate-queue.js').main()"
// Idempotence guard: refuses if u-7 already exists.
const fs = require('fs');
const path = require('path');
const P = path.join(__dirname, 'queue.json');

function main() {
  const q = JSON.parse(fs.readFileSync(P, 'utf8'));
  if (q.some(e => e.id === 'u-7')) throw new Error('already re-gated (u-7 exists)');
  const by = id => q.find(e => e.id === id);
  const BASE = 'strategies/2026-10-29_向导式_ATR指标择时测试_0_0_1-8b9cb8e2.py + epoch-9 OVERRIDE';
  const HARNESS = 'POOL-EW HARNESS (shared by u-7/u-3/u-4/u-5, identical in all four): (H1) exit off: the L289 sell filter becomes sell_lists = []; (H2) g.max_hold_stocknum 5 -> 1000 (L38); (H3) in buy(), Cash = context.portfolio.available_cash / len(buy_lists) instead of result[stock] from order_style. H3 is REQUIRED: order_style(context, buy_lists, g.max_hold_stocknum, by_cap_mean) is a hidden wizard call, and u-1 cannot tell whether it divides by len(buy_lists) or by max_hold-positions (both equal 5 on day 1 and 1 on 11-04). At max_hold 1000 the second reading would put 0.1% in each name. H1 is REQUIRED because the 0.35 exit is in YUAN (u-2): on 2024-01-02, 12 of the 26 PE survivors already read dayu=True (000408 000651 000792 002129 002459 002460 600332 600585 600803 601318 688303 688599). Any variant that admits higher-priced names would sell them on the first sell day and buy them back at the next buy (sell and buy share the 10-day cadence). That measures churn, not selection. Log EWDEPLOY date=<d> n_buy=<k> cash_before=<c> cash_after=<c> on every buy day, and POOL0 code=<c> for every day-1 buy. VALIDITY CONTROL: on day 1, cash_after/total_value must be <= 5%, or the run is void. With exits off and cash ~0 after day 1, each run is in effect a DAY-1 EQUAL-WEIGHT BUY-AND-HOLD. Later buy days only spread dividend cash (the base left it idle; a small known difference).';
  const now = 'gatekeeper 2026-11-01 (re-gate after u-1/u-2)';

  q.push({
    id: 'u-7', kind: 'understand',
    title: 'pool-EW CONTROL: yuan-ATR<0.15 ∩ PE 6-11 pool, equal cash, exit off (base screens under the pool-EW harness)',
    hypothesis: 'The base is in effect this basket: the 6 day-1 names (600018 601006 601117 601319 601669 601800) at 1/6 each, held all year. It anchors u-3/u-4/u-5, and each of those changes exactly one screen relative to it.',
    why: 'type: control, required before u-3/u-4/u-5 can be read. It is not an edge test, so it has no CONFIRM/REFUTE. DECISION RULE (validity): VALID if POOL0 lists exactly those 6 codes and day-1 EWDEPLOY cash is <= 5%; otherwise the run is void and its three dependants wait. Also report Δ vs base (sharpe 1.19, obj 0.1858) and the daily corr, labelled as the JOINT effect of exit-off + 601800 added; do NOT attribute it to either one. Price-only pre-estimate from u-2 OPEN0/CLOSEN: 6-name EW +28.0% vs +25.3% for the base 5 held static (dividends excluded), so expect roughly base-level. Cost ~3-5 min.',
    design: 'Base = ' + BASE + '. ' + HARNESS + ' No other edit: the yuan ATR<0.15 entry and the PE 6-11 band both stay.',
    from: ['u-1 (2 selection events; exit fires once)', 'u-2 (day-1 pool 6, median 5; ATR unit = yuan; 12/26 PE survivors dayu=True on day 1)', 'u-3 re-gate'],
    edgeRef: '低价股效应', rank: 1, status: 'active',
    note: now + ': NEW, rank 1, ACTIVE, dispatch next. It replaces the base as the control for the edge ladder. Every ladder variant must turn the yuan exit off (see harness), and the base cannot serve as that control.',
  });

  const u3 = by('u-3');
  Object.assign(u3, {
    title: 'RE-SCOPED: PE 6-11 pool EW with NO price gate (yuan-ATR entry filter removed), under the pool-EW harness; control = u-7',
    hypothesis: 'The book is a 2024 low-valuation large-cap basket, and the yuan-ATR gate (a nominal-price filter, per u-2) adds nothing. The whole PE 6-11 HS300 pool (26 names on day 1, 7 of them SZ, ¥4.8-42.8) does about as well as the cheap 6-name subset. Proposed edge: 「2024 低估值大盘风格贝塔」.',
    why: 'type: edge ablation of the price gate. DECISION RULE vs u-7: PRICE GATE ADDS at Δsharpe <= -0.5 (supports 低价股效应 as a selection effect; whether it is price or low vol stays open, which is u-5); STYLE-BETA SUPPORTED at |Δsharpe| <= 0.3 AND daily corr >= 0.85; PRICE GATE HURTS at Δsharpe >= +0.5; otherwise partial. Report day-1 n_buy (expect 26) and both maxDDs. ⚠ Single cross-section: both legs are day-1 baskets, so the verdict rests on one date. Report the per-name total return of the 20 names u-3 adds beside the number. ⚠ 「2024 低估值大盘风格贝塔」 must be registered on the family page as proposed before the recorder may cite it. Cost ~3-5 min.',
    design: 'u-7 build + exactly one asserted edit: the L196 entry filter becomes a pass-through (buy_lists unchanged). PE band, universe, industry and the ST/paused/high-limit filters are unchanged.',
    from: ['u-2 (funnel: PE pool 21/27/43, day-1 26; yuan-ATR removes every SZ name on price)', 'u-7', 'free corr 0.882 with 蓝筹分红持续性 dxew'],
    edgeRef: '2024 低估值大盘风格贝塔', rank: 2, status: 'queued',
    note: u3.note + ' ‖ ' + now + ': RE-SCOPED in place (recorder proposal accepted). The original (max_hold 5->1000, gate kept) is DROPPED as near-inert. It adds only 601800 at 1/6 weight, whose +41% is already in the u-2 log, so its Δ was predictable and could not test a broad beta. Rewritten to remove the price gate instead, under the shared pool-EW harness (exit off is mandatory: 12 of 26 day-1 PE names read dayu=True in yuan). Control moved from the base to u-7.',
  });

  const u5 = by('u-5');
  Object.assign(u5, {
    title: 'REDESIGNED: relative-ATR gate (ATR/close < k) at day-1 breadth 6 in place of yuan-ATR<0.15, under the pool-EW harness; control = u-7',
    hypothesis: 'The edge is low NOMINAL PRICE, not low volatility: the 6 PE survivors with the lowest ATR/close do clearly worse than the 6 cheapest.',
    why: 'type: edge ablation, family page edge[1].test (低价股效应). DECISION RULE vs u-7: CONFIRM 低价 at Δsharpe <= -0.5; REFUTE (low vol does as well) at |Δsharpe| <= 0.2; LOW-VOL BETTER at Δsharpe >= +0.5; otherwise partial. The day-1 set is a pre-run fact from u-2 rel15: {601006 600018 600332 600362 600104 601319}. It overlaps u-7 on 3 of 6 (601006 600018 601319), so the 3 swapped names (600332 600362 600104 in; 601117 601669 601800 out) decide the result. Report their per-name returns. VALIDITY: POOL0 must equal that set, or the run is void. k is knife-edge: 601319 (rel15 0.01638) is in and 601318 (0.01654) is out. ⚠ Why the harness matters here: 600332 (¥28.60, ATR 0.426 yuan) reads dayu=True on day 1. Under the original design (yuan exit kept) it would be sold on the first sell day and churned, so the original u-5 was contaminated by construction. Read u-5 AFTER u-3: if u-3 shows the gate adds nothing, a null here means neither reading of the gate matters. Cost ~3-5 min.',
    design: 'u-7 build + exactly one asserted edit at L196: ATR_judge_xiaoyu(security,0.15,14) -> a local relative test using the SAME computation the u-2 probe logged as rel15 (talib.ATR timeperiod 14 on 15 daily bars up to previous_date, divided by the previous close), with k = 0.01646. The exit is off via the harness, so no exit-scale choice arises.',
    from: ['wiki edge[1].test', 'u-2 (rel15 for all 26 day-1 PE survivors; lowest-6 overlap 3/6)', 'u-7', 'u-3'],
    edgeRef: '低价股效应', rank: 3, status: 'queued',
    note: u5.note + ' ‖ ' + now + ': REDESIGNED. The original kept the wizard yuan exit while admitting higher-priced names. 600332 is dayu=True on day 1, so it would have tested churn, not selection. Moved onto the pool-EW harness with u-7 as control, and k pinned to the u-2 day-1 rel15 breakpoint.',
  });

  const u4 = by('u-4');
  Object.assign(u4, {
    title: 'REDESIGNED: yuan-ATR<0.15 gate on the full HS300 (PE 6-11 band removed), under the pool-EW harness; control = u-7. Does PE bind after the price gate?',
    hypothesis: 'Even with the price gate in place, the PE 6-11 band still selects. Removing it admits cheap names outside the band (2024 big banks at PE ~5-6, very cheap cyclicals), and the basket does clearly worse.',
    why: 'type: edge ablation, family page edge[0].test (低估值) at pool level. It also answers the binding question u-2 could not (ATR was computed only on PE survivors). DECISION RULE: NON-BINDING if day-1 POOL0 equals u-7\'s 6 codes (the curve should then be bit-identical; report max|Δcum|). That refutes 低估值 as a selection edge of this book, and no Δ is needed. Otherwise, vs u-7: CONFIRM 低估值 at Δsharpe <= -0.5; REFUTE at |Δsharpe| <= 0.2; otherwise partial. Log CNT stage=b_atr n and the PE of every day-1 buy, so the names the band had been excluding are visible. ⚠ The recorder must state that the control is u-7 (pool level), not the 5-name base the page names. Cost ~3-5 min.',
    design: 'u-7 build + exactly one asserted edit: L232 financial_data_filter_qujian(security_list, valuation.pe_ratio, (6,11)) becomes a pass-through. Add a log line PE0 code=<c> pe=<pe_ratio at previous_date> for each day-1 buy (logging only).',
    from: ['wiki edge[0].test', 'u-2 (PE-after-ATR binding not measurable)', 'u-7'],
    edgeRef: '低估值', rank: 4, status: 'queued',
    note: u4.note + ' ‖ ' + now + ': REDESIGNED to "yuan gate without the PE band", as proposed. The run itself answers the binding question (the non-binding branch = bit-identical to u-7). Control moved from u-3 to u-7. The exit is off via the harness for comparability, not because the cheap names would churn.',
  });

  const u6 = by('u-6');
  Object.assign(u6, {
    status: 'dropped', rank: null,
    note: u6.note + ' ‖ ' + now + ': DROPPED; a redesign is not worth it. With a day-1 pool of 6 there are only C(6,5) = 6 subsets, so the "distribution" is six points and the question collapses to "which name was cut", which u-2 already answers (601800). Gatekeeper arithmetic from u-2 OPEN0/CLOSEN, PRICE-ONLY (no dividends, no exit/refill, so it is NOT a finding and has no reproduction control): per name, 600018 +24.5, 601006 -5.3, 601117 +32.2, 601319 +61.4, 601669 +13.7, 601800 +41.4%. The 5-name subsets range from 21.3% (drop 601319) to 34.6% (drop 601006), and the base subset at 25.3% ranks 5th of 6. So code-order selection cost ~2.7pp against the 6-name EW, and selection noise spans ~13pp on a 29% book. u-7 measures the 6-name pool properly.',
  });

  const ps = by('dxlv-imp-pesort');
  Object.assign(ps, {
    status: 'dropped', rank: null,
    note: ps.note + ' ‖ ' + now + ': DROPPED. Priced off-line, it FAILS its own bar, and it is NOT inert. Day-1 PE (u-2): 601800 6.334, 601669 6.842, 601117 7.172, 600018 8.753, 601006 9.639, 601319 10.367. The PE-ascending top 5 cuts 601319 (+61.4%) and keeps 601800 (+41.4%), swapping the pool\'s best name for its second-best: Δtotal ≈ 0.2 x (41.4 - 61.4) = -4.0pp, price-only. The 11-04 refill is unchanged (601288 at PE 6.053 is the lowest of 601288/601988/601618), and so is the 601117 exit (same holding). Δobj ≈ -0.04 against an IMPROVEMENT bar of +0.03; maxDD would have to fall ~7pp to pass, which is implausible for a one-leg swap. Not run; ~4 min saved.',
  });

  const pd = by('dxlv-imp-pesort-desc');
  Object.assign(pd, {
    status: 'dropped', rank: null,
    note: pd.note + ' ‖ ' + now + ': DROPPED, because its condition (pesort IMPROVEMENT) cannot be met. For the record: the PE-descending top 5 cuts 601800, giving exactly the base\'s day-1 set. It differs only at the 11-04 refill (601618 at PE 9.658 vs 601288), a one-name single draw.',
  });

  const se = by('dxlv-imp-screenexit');
  Object.assign(se, {
    rank: 6,
    why: se.why + ' ⚠ RE-GATED: base is the original book (pesort dropped). CONDITIONAL on the ladder: run only if u-3 or u-4 shows a selection effect (Δsharpe <= -0.5 against u-7). If neither screen selects, exiting a name that leaves the screen has no premise, and this entry is dropped with that reason. The refill pool is small (median 5, 0 on 2024-10-21), so a screen-exit may leave cash idle: log idle-cash days.',
    note: se.note + ' ‖ ' + now + ': KEPT, rank 6 (last), now conditional on the edge ladder. u-1 showed the ATR exit is live (it fired once), so the "add a working exit" motivation is weaker than drafted.',
  });

  const lq = by('liq-1');
  Object.assign(lq, {
    rank: 5,
    note: lq.note + ' ‖ ' + now + ': KEPT unchanged, rank 5: after the ladder and BEFORE any VAL. It is independent of the ladder, so it may fill a budget gap at any point. It runs on the BASE book (the candidate), not on a harness variant.',
  });

  const order = { 'u-7': 1, 'u-3': 2, 'u-5': 3, 'u-4': 4, 'liq-1': 5, 'dxlv-imp-screenexit': 6 };
  const done = q.filter(e => e.status === 'done');
  const open = q.filter(e => order[e.id]).sort((a, b) => order[a.id] - order[b.id]);
  const drop = q.filter(e => e.status === 'dropped');
  if (done.length + open.length + drop.length !== q.length) throw new Error('entry lost');
  fs.writeFileSync(P, JSON.stringify([...done, ...open, ...drop], null, 2) + '\n');
  console.log('written', q.length);
}
module.exports = { main };
