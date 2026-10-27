// archive-champ-product.js — put the book that reached VAL on the product shelf.
//
// The shelf (`validated_strategies/`) is the record of what REACHED validation, pass or fail —
// `integrate-eligible.shelfProductOf()` filters on `gate_val` itself, so a FAILED VAL belongs
// here too. This one FAILED (sharpe_val 0.83 < the epoch-9 validate gate of 1.0).
//
// The only edit is a comment header PREPENDED to the exact file that was run. The assertion below
// is what makes this an archive rather than a new book: the archived body must be byte-identical
// to `enhance/candidates/xsz-e9-champ.py`, which `build-champ-product.js` already asserted is
// `py2to3(raw champion)` + the frozen epoch-9 OVERRIDE with zero logic edits.
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const SRC = path.join(ROOT, 'enhance', 'candidates', 'xsz-e9-champ.py');
const OUT = path.join(ROOT, 'validated_strategies', 'xsz-e9-champ.py');

const body = fs.readFileSync(SRC, 'utf8');

const HEADER = `# ===== VALIDATED STRATEGY (run-family archive) — join-quant epoch 9 =====
# expId:            xsz-e9-champ
# runId:            xsz-e9-champ-val   (the VAL recorded in data/consumption.tsv)
# ideaId:           —   (no idea: this is the family CHAMPION itself, snapshotted for a VAL)
# family:           小市值   (source base: strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py)
# sourceBook:       enhance/candidates/xsz-e9-champ.py   (builder: study/小市值/build-champ-product.js)
# mutation:         NONE. The body is \`py2to3(raw champion)\` BYTE-FOR-BYTE plus the frozen epoch-9
#                   OVERRIDE (which is what supplies the three pins strategies/ does not carry:
#                   avoid_volume_ratio / set_order_cost / avoid_future_data). Zero logic edits —
#                   no knob, no filter, no threshold, no window inside the book was touched.
#                   build-champ-product.js asserts the pre-OVERRIDE body equality and the pins;
#                   archive-champ-product.js asserts this file's body equals that file byte-for-byte.
# train_objective:  2.6282   (TRAIN 2024-01-01..2024-12-31, 365d: total 276.82% / annual 276.82% / maxDD 14.00% / sharpe 7.07 — the champion's own epoch-9 ledger row, which is this book's control)
# val_objective:    0.0723   (VAL   2025-01-01..2025-12-31, 364d: total 27.03% / annual 27.11% / maxDD 19.80%)
# sharpe_val:       0.83
# gate_val:         fail     (0.83 < 1.0, epoch-9 validate gate)
# harness_epoch:    9
# ranAt:            2026-10-27
# curves:           data/series/enhance_candidates_xsz-e9-champ__val__e9.json (243 pts, 2025-01-02..2025-12-31)
#                   recorder recomputed from that curve, not from the report: final cum 27.03 (the
#                   scrape exactly), self-computed maxDD 19.7992, annualized vol 28.83%.
#
# flags — READ BEFORE USING THIS PRODUCT FOR ANYTHING:
#   ⚠⚠ THIS BOOK FAILED ITS VALIDATION. sharpe 7.07 on TRAIN 2024 -> 0.83 on VAL 2025, i.e. BELOW
#      the gate on the IMMEDIATELY ADJACENT calendar year, with annual falling 276.82% -> 27.11%
#      and drawdown RISING 14.00% -> 19.80%. ⇒ THE TRAIN LEVEL (2.6282 / sharpe 7.07 / annual
#      276.82%) MUST NEVER BE QUOTED AS THIS BOOK'S EXPECTED PERFORMANCE. It is a 2024 measurement
#      and 2025 did not reproduce it. The family has NO gate-passing validated candidate on this
#      bench; nothing here is eligible to be shipped.
#   ⚠⚠ ZERO LOGIC EDITS — this is the family CHAMPION verbatim. So the failure cannot be blamed on
#      a candidate-construction choice: there is no mutation to roll back. What failed is the
#      champion's own level, and its control is its own TRAIN ledger row (same book, same bench).
#   ⚠⚠ THE VAL WAS SPENT ON A HUMAN OVERRIDE. \`val-budget\` reported ALLOWED (human-override)
#      because JQ_ALLOW_REVAL=1 was set in the environment BY THE HUMAN (frontmatter
#      \`valRevalGranted: 9\`). The prior blocker was \`prior-unknown-epoch\`: the 2026-09-19
#      \`jul12-005\` row records \`val-pass\` with NO epoch, and unknown blocks. The consumption row
#      carries the marker: \`小市值 family validate xsz-e9-champ-val … sharpe 0.83 … [JQ_ALLOW_REVAL]\`,
#      epoch 9. An override VAL must stay legible as one — this is not a budgeted first-of-bench VAL.
#   ⚠⚠ 0.2963 OF THE TRAIN OBJECTIVE (11.3%) IS AN n=1 DECEMBER-2024 EVENT (q-e9-champ-dbl). The
#      MACD 顶背离 overlay fired exactly ONCE in twelve months — 2024-12-17 09:00 — and the two
#      curves are bit-identical through 2024-12-16 (max|Δcum| = 0.000000), with only 11 differing
#      days all in December. And it is NOT risk control: ΔmaxDD = 0.00 (14.01 on both the full year
#      and the Jan–Nov slice). So the TRAIN level rests partly on one session's luck — which is
#      exactly the fragility this VAL then measured.
#   ⚠  SHAPE OF THE VAL FAILURE (recorder, from the curve): it is NOT uniform weakness. H1 2025
#      +37.23% (maxDD 7.01%), peak cum +58.39% on 2025-08-11, then H2 2025 −7.43%; Q1 +17.85 /
#      Q2 +16.45 / Q3 −4.35 / Q4 −4.76. The 19.80% drawdown runs 2025-08-11 -> 2025-12-31, i.e. it
#      is STILL OPEN at the window edge, so 19.80% is a lower bound on that episode, not a completed
#      one. 121 up / 97 down / 24 flat days, worst −6.01%, best +7.94%.
#   ⚠  NOT a scrape artefact: annualized vol 28.83% is consistent with sharpe 0.83 at annual 27.11%
#      (the artefact class is implied vol > ~150%). Arithmetic-convention sharpe (mean/sd×√252) on
#      the same curve is 1.01 — do NOT quote that beside JQ's 0.83; they are different conventions.
#   ⚠  objective convention: 0.0723 takes annual = total 27.03; the ledger's 365/364 annualization
#      gives annual 27.11 ⇒ 0.0731. Both verified against the curve; the verdict is the same either
#      way and the gate is on SHARPE regardless.
#   ⚠  realizability 2 (q-e9-champ-liq, measured on THIS book): the ¥1e7/day feasibility floor
#      removes 1.96% of candidate slots, objective 2.6282 -> 2.4459. But 1e7 is only the START-OF-YEAR
#      floor — position size compounds to a single 1,939,339 order on 2024-12-05 (⇒ ~¥3.88e7/day
#      needed then), and liq-2 (5e7) / liq-3 (1e8) are BUILT BUT NOT RUN. Capacity above ¥1e7/day
#      is unmeasured.
#   ⚠  零滑点高估 — zero-slippage bench, 399101 中小板综指 pool, 2 positions only, weekly Tuesday
#      10:45 rebalance. The concentration (2 names) is an order of magnitude tighter than the
#      family's other branches (5 / 4 / 8), so the tail is thin in both directions.
#   ⚠  This is the family's THIRD branch (399101 中小盘趋势 + BBI band + 2 positions), NOT the
#      低开剥头皮 branch §1 describes. The only edge measured ON THIS BOOK is 规模 (q-e9-champ-size:
#      moving the pool up one notch keeps 29.5% of annual). The BBI band is REFUTED as a return
#      source (q-e9-champ-bbi-off: removing it leaves 100.9% of annual, +5.46pp drawdown).
#   ⚠  ARCHIVED BECAUSE IT REACHED VALIDATION, NOT BECAUSE IT IS A PRODUCT TO SHIP. And a failed
#      VAL is NOT a licence to build a replacement candidate and validate that: "the last VAL
#      disappointed, so make a new one" is selection on VAL one run at a time. The bench's VAL for
#      this family is spent.
#   Full write-up: wiki/families/小市值.md §2 (val-e9-champ), §4, frontmatter realism;
#   finding q-e9-champ-val in study/小市值/findings.tsv.
# ================================================================================

`;

const out = HEADER + body;

// The archive assertion: strip the header back off and the remainder must be the exact file that
// was run. A shelf artifact whose body has drifted from the measured book is worse than none.
if (out.slice(HEADER.length) !== body) throw new Error('body is not byte-identical to the measured book');
if (!/^# gate_val:\s*fail\b/m.test(HEADER)) throw new Error('gate_val must read fail');
if (!/^# train_objective:.*sharpe 7\.07/m.test(HEADER)) {
  throw new Error('train_objective gloss must contain the literal "sharpe 7.07" — shelfProductOf parses the TRAIN sharpe out of it');
}

fs.writeFileSync(OUT, out);
console.log(`wrote ${path.relative(ROOT, OUT)}  header=${HEADER.split('\n').length - 1} lines  body=${body.split('\n').length} lines (byte-identical)`);
