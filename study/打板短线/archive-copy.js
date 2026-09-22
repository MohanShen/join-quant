// Copies the validated base to validated_strategies/dbdx-base-e6.py with the archive header.
//   node -e "require('./study/打板短线/archive-copy.js')"
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const body = fs.readFileSync(path.join(__dirname, 'baseline-e6.py'), 'utf8');
const header = `# ===== VALIDATED STRATEGY (run-family archive) — join-quant epoch 6 =====
# expId:            dbdx-base-e6
# ideaId:           (none — the base itself; no improve candidate beat it on TRAIN: imp-3 −0.12, imp-4 −0.41, imp-1/imp-2 dropped by arithmetic)
# baseExpId:        baseline-e6  (= base 439385b4 + epoch-6 OVERRIDE, study/打板短线/baseline-e6.py; reproduces the epoch-2 digits exactly)
# family:           打板短线   (source base: strategies/2026-05-27_首板高开-低开-弱转强混合策略_今年收益1138_61-439385b4.py, 子匀, post/48680)
# mutation:         none. Built by study/打板短线/build-e6.js (py2to3(source) + live OVERRIDE).
# train_objective:  0.9668   (TRAIN 2022-01-01..2023-12-31: total 424.33% / annual 129.24% / maxDD 32.56% / sharpe 2.58; 2022 +442.5 / 2023 −3.35)
# val_objective:    4.2002   (VAL   2024-01-01..2025-12-31: total 3085.45% / annual 464.40% / maxDD 44.38% / sharpe 7.48; 2024 +799 / 2025 +254)
# sharpe_val:       7.48
# gate_val:         pass     (sharpe 7.48 >= 1.5)
# harness_epoch:    6
# ranAt:            2026-09-22
#
# flags:
#   ⚠⚠ VAL is NOT clean for this author: the post was published in 2026 and its title claims the VAL window
#      ("过去两年年化304%"); the ~10 hand-tuned constants were set on 2024–25. Treat VAL as in-sample for the author.
#   ⚠⚠ 零滑点台 × 一字板可成交 × turnover 0.29 — the least realisable style in the library (harness §3 red line).
#      By the end of VAL the book is ¥31M and the 5% order_volume_ratio pin binds on ¥5.5e8-turnover names.
#   ⚠  Every year is "first-half fat tail, second-half fade": 2022 206/77, 2023 18/−18, 2024 933/−13, 2025 193/21.
#      The edge (涨停动量延续, measured: study-u-nolimit) is a recurring regime event, not a stable premium.
#      VAL maxDD 44.38% is 2024-08-30 -> 2024-10-22 (the September rally), not the 2024-02 microcap stampede (+55%).
#   ⚠  The 弱转强 leg is both the 2022-H1 fat tail and the whole 2023-H2 loss (study-u-rzq-deconf); dropping it or
#      gating on limit-up breadth gives four positive half-years but loses to the base on TRAIN objective.
#   Full write-up: wiki/families/打板短线.md §1/§2/§4/§6 (e6-ledger-audit, e6-dup, baseline-e6, u-2023, u-nolimit,
#   u-rzq-deconf, u-barprice, dbdx-imp-3, dbdx-imp-4, val-base-e6).
# ================================================================================

`;
const out = path.join(ROOT, 'validated_strategies/dbdx-base-e6.py');
fs.writeFileSync(out, header + body);
console.log('archived', out, header.length + body.length, 'chars');
