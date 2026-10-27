// archive-e9-pit.js — ARCHIVE the validated book to the product shelf (五福闹新春, epoch 9).
//
// Run via: node -e "require('./study/五福闹新春/archive-e9-pit.js')"
//
// The shelf is what `utils/integrate-eligible.js::shelfProductOf()` reads, and for THIS family it
// is the only route to the gate: the MEMBER path demands `base == bestVariant`, and here
// base = 17b3b439 while bestVariant = bf30eb36, so a member can never be confirmed.
//
// The body is the validated book byte-for-byte; only a header is prepended.
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const SRC = path.join(ROOT, 'study/五福闹新春/q-e9-pit_bf30eb36.py');
const OUT = path.join(ROOT, 'validated_strategies/wufu-e9-pit.py');

const header = `# ===== VALIDATED STRATEGY (run-family archive) — join-quant epoch 9 =====
# expId:            wufu-e9-pit
# runId:            wufu-e9-pit-val   (the VAL recorded in data/consumption.tsv)
# ideaId:           q-e9-pit  (point-in-time POOL build of the family champion)
# family:           五福闹新春   (source champion: strategies/2026-05-23_三马105-五福35-修复版-11年收益677倍回撤14-bf30eb36.py)
# sourceBook:       study/五福闹新春/q-e9-pit_bf30eb36.py   (builder: study/五福闹新春/build-e9-pit.js)
# mutation:         pool = (g.global_etf_pool + g.china_etf_pool) ∩ { 上市日期 < TRAIN start }, i.e. the 17
#                   names listed on/after 2024-01-01 are COMMENTED OUT IN PLACE. Ranking, momentum window,
#                   timing, thresholds, liquidity filter and the cost block are verbatim.
# train_objective:  1.9658   (TRAIN 2024-01-01..2024-12-31: total 209.36% / annual 209.36% / maxDD 12.78% / sharpe 7.51)
# val_objective:    2.0785   (VAL   2025-01-01..2025-12-31: total 214.55% / annual 215.54% / maxDD 7.69% / sharpe 9.64)
# sharpe_val:       9.64
# gate_val:         pass     (sharpe 9.64 >= 1.0)
# harness_epoch:    9
# ranAt:            2026-10-26
# curves:           data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json (242 pts)
#                   data/series/study_五福闹新春_q-e9-pit_bf30eb36__val__e9.json   (243 pts, 2025-01-02..2025-12-31)
#                   recorder recomputed both: TRAIN final cum 209.36 / maxDD 12.7802; VAL final cum 214.55 /
#                   maxDD 7.6967 — the scrape exactly. VAL annualized vol 22.9% is consistent with the 21.9%
#                   implied by sharpe 9.64, so this is NOT the scrape-artefact class (>~150% implied vol).
#
# flags — READ BEFORE USING THIS PRODUCT FOR ANYTHING:
#   ⚠⚠ THE MAJORITY OF THIS BOOK'S RETURN IS ANOTHER FAMILY'S EDGE. It is a capital-isolated
#      CROSS-FAMILY combination book: 50% 小市值 stock-selection leg / 50% 五福 ETF-rotation leg.
#      Measured in-place (study q-e9-leg, one line L118, the ETF sleeve's capital and position size
#      left verbatim): zeroing the 小市值 leg leaves objective 0.5589 / annual 65.93% — so
#      五福闹新春's OWN mechanism supplies only **28.4% of this book's objective** (31.5% of annual)
#      and the majority driver is 规模, which is [[小市值]]'s edge, not this family's.
#      ⇒ INTEGRATION MUST NOT DOUBLE-COUNT 规模 across 五福闹新春 and 小市值. 小市值's own champion
#      (bba95a11) is itself a 小市值×五福 hybrid, so the two families are each booking the other's leg
#      as their product. Any merge or universe arrival involving this product has to resolve that
#      overlap explicitly — the integration guard's symbol-overlap test will not see it, because the
#      overlap is a MECHANISM overlap, not a symbol one.
#      ⚠ 28.4% is a LOWER-BOUND reading, not an additive decomposition: the sleeve sizes orders off
#      L1679 portfolio.total_value × pvp[2] (half the WHOLE portfolio), so no "what the sleeve makes
#      standalone" number may be derived from it.
#   ✅ REALIZABILITY 2, MEASURED ON THIS EXACT BOOK (study q-e9-liq, epoch 9, 4 backtest minutes), which
#      is why realizabilityScope: wufu-e9-pit is on the family page. Both legs were given their own
#      feasibility floor, computed off the LIVE context.portfolio.total_value (not initial capital —
#      this book triples inside 2024, so a fixed floor is only the January requirement): objective
#      1.9658 → 1.8858, sharpe 7.51 → 7.16, maxDD +0.01pp. Floor-SENSITIVE but not floor-broken, and
#      provably non-inert (ETF leg 16/216 decision days in≠out, 9 of them at rank 1, 5 names excluded,
#      one day with zero survivors, max|Δcum| 7.99).
#      ⚠⚠ The bottleneck is the ETF leg's single holding (thin names 561330 / 513350), NOT the stock leg:
#      the 小市值 leg is **100% inert**, 0/203 candidate days excluded under three independent floor
#      definitions, and the tightest name-day of the year (002830 on 2024-08-12) still has 2.95× headroom.
#      So this book does NOT inherit [[小市值]]'s measured R=1.
#      ⚠ R=3 is neither earned nor excluded — only ONE floor point (1×) was ever run, and capacity is
#      what a book can ABSORB, not how much sharpe it has spare.
#   ⚠⚠ THE VAL CAME IN ABOVE TRAIN (2.0785 vs 1.9658; sharpe 9.64 vs 7.51). DO NOT read that as the book
#      improving out of sample. Each window is ONE calendar year, so each number is as much a property of
#      its year as of the book, and 2025 was evidently a strong year for these holdings. What the pass
#      licenses is ELIGIBILITY — a gate-clearing result on a window not used for selection. It licenses
#      NO claim about 2026. The repo's actual out-of-sample record is **0 for 2** (大小盘轮动 −0.21,
#      红利低频 −0.51), and both of those looked healthy on TRAIN and on VAL.
#   ⚠  零滑点台 — the bench charges no slippage. The floor test above asks only "could the day's volume
#      fill this order"; market impact, partial fills, QDII premium/discount and ETF creation/redemption
#      quotas are all unmeasured.
#   ✅ WHY THIS BOOK AND NOT THE RAW CHAMPION — the precondition was SATISFIED, not overridden.
#      The family had recorded valDeclined: 9; a human reopened the VAL on 2026-10-26 (commit a981eaf),
#      preserving the reasoning as valDeclinedPrior/valDeclinedPriorBasis and stating that any
#      precondition it names must still be met first. The named precondition was a PRE-2025 POOL CUTOFF:
#      the raw champion's hand-written pool contains **7 names that listed during 2025** (159323, 159206,
#      588170, 159218, 159227, 588790, 159256) and epoch 9's VAL window IS 2025, so a 2026-authored pool
#      has selection-on-VAL built into it. This build's pool is ∩ { 上市日期 < 2024-01-01 }, a strict
#      SUBSET of what was tradeable in 2025, so it cannot carry selection-on-VAL. The membership rule
#      cites no price, return, volume or ranking from either window.
#   ⚠  The prior decline's OTHER reason is NOT resolved by this run and is carried forward: the champion's
#      excess is mostly 规模 (the 28.4% flag above). Its third reason — "the candidate and the validated
#      book do not match" — IS resolved, and this archive is what resolves it: the shelf product IS the
#      book that was validated, so the gate's product path confirms by expId rather than guessing.
#   ⚠  This product is NOT the family's measured ETF-mechanism level. For that, cite base 17b3b439
#      (epoch 9 TRAIN: objective 1.7479 / sharpe 5.97 / annual 187.39%) — never 1.9658.
#   Full write-up: wiki/families/五福闹新春.md §1/§2/§4/§6 (q-e9-pit, q-e9-leg, q-e9-weak, q-e9-liq,
#   imp-e9-1, val-e9-pit).
# ================================================================================

`;

const body = fs.readFileSync(SRC, 'utf8');
fs.writeFileSync(OUT, header + body);

// Verify the body survives byte-for-byte, and that the gate's own parser reads every field.
const written = fs.readFileSync(OUT, 'utf8');
const bodyOk = written.slice(header.length) === body;
const raw = k => ((written.match(new RegExp(`^#\\s*${k}:\\s*(.+)$`, 'm')) || [])[1] || '').trim();
const g = k => raw(k).split(/\s{2,}|\s*\(/)[0].trim();
const norm = x => String(x || '').toLowerCase()
  .replace(/[-_]?val[-_]?/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
const sharpeTrain = (raw('train_objective').match(/sharpe\s+(-?\d+(?:\.\d+)?)/i) || [])[1];

console.log(JSON.stringify({
  out: path.relative(ROOT, OUT),
  bodyByteIdentical: bodyOk,
  family: g('family'),
  expId: g('expId'),
  harness_epoch: g('harness_epoch'),
  train_objective: parseFloat(g('train_objective')),
  trainSharpeFromGloss: sharpeTrain ? parseFloat(sharpeTrain) : null,
  sharpe_val: parseFloat(g('sharpe_val')),
  gate_val: g('gate_val').split(/\s+/)[0],
  runIdNormalisesToExpId: norm('wufu-e9-pit-val') === norm(g('expId')),
}, null, 1));
