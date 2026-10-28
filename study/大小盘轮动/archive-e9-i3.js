// Archive the epoch-9 VALIDATED candidate dxp-e9-i3 to the product shelf.
// Body = the exact file the VAL ran (study/大小盘轮动/variants/i3-e9_no-s2.py), header prepended.
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const src = path.join(__dirname, 'variants/i3-e9_no-s2.py');
const out = path.join(ROOT, 'validated_strategies/dxp-e9-i3.py');
const body = fs.readFileSync(src, 'utf8');
if (!/g\.enable_strategy_two\s*=\s*False/.test(body)) throw new Error('variant does not carry the i3 edit');
if (fs.existsSync(out)) throw new Error(`${out} exists; refusing to overwrite`);
const header = `# ===== VALIDATED STRATEGY (run-family archive) — join-quant epoch 9 =====
# expId:            dxp-e9-i3
# ideaId:           e9-i3  (base 2f5bc859 with 择时二 disabled: g.enable_strategy_two=False)
# baseExpId:        dxp-e9-0  (= base 2f5bc859 + epoch-9 OVERRIDE; base TRAIN 2024 objective 1.0614 / sharpe 3.94)
# family:           大小盘轮动   (source base: strategies/2026-05-20_四择时高息低价小市值和白马大市值轮动-2f5bc859.py)
# mutation:         one edit — g.enable_strategy_two=False (two of three timing votes remain) + four logging-only
#                   lines. Built by study/大小盘轮动/build-e9-i3.js -> variants/i3-e9_no-s2.py (this body, verbatim).
# train_objective:  1.1219   (TRAIN 2024-01-01..2024-12-31: total 130.42% / annual 130.42% / maxDD 18.23% / sharpe 4.11; base 1.0614)
# val_objective:    0.4676   (VAL   2025-01-01..2025-12-31: total 56.80% / annual 56.99% / maxDD 10.23% / sharpe 2.54)
# sharpe_val:       2.54
# gate_val:         pass     (sharpe 2.54 >= 1.0, pre-registered before the run)
# harness_epoch:    9
# valRunId:         dxp-e9-i3-val   (curve: data/series/study_大小盘轮动_variants_i3-e9_no-s2__val__e9.json, 243 pts)
# ranAt:            2026-10-27
#
# flags:
#   ⚠⚠ ONE-YEAR TRAIN. Adopted on 2024 alone; +0.0605 over the base is ~6% and within one year's noise.
#      The gain is INFERRED to ride the 14:00 refill path mixing on daily signals (Feb/Nov/Dec +1.30/+3.36/
#      +0.83pp); the designed month-start vote effect (06-03 EMPTY->BIG) was -2.35pp. No fill log (e9-u5).
#   ⚠⚠ 2025 IS NOT A NEVER-SEEN WINDOW FOR THIS FAMILY. Epoch 6's VAL ran a DIFFERENT book over 2025
#      (dxp-imp-1, always-small: 2025 +74.2% / DD 10.36). Choosing this voting book over always-small was
#      done on 2024 TRAIN and goes AGAINST what that 2025 knowledge would favour, so this is not
#      selection-on-VAL — but it is not a clean first holdout either.
#   ⚠  THE BASE 2f5bc859 WAS NOT VALIDATED on epoch 9. Only this book was. Do not quote the base as validated.
#      The epoch-6 product dxp-imp-1 is superseded on this bench.
#   ⚠  零滑点台 — trades the 10 smallest dividend-paying profitable stocks under 9 yuan in the small leg;
#      the 2e6 liquidity floor is inert on the base at e9 (e9-r1) and the selection chain is unchanged here,
#      but realizability must be scoped to THIS book (realizabilityScope) before it is cited.
#   Full write-up: wiki/families/大小盘轮动.md §2/§6 (e9-r1, e9-u2, e9-i3, e9-i1, e9-u3, val-e9-i3).
# ================================================================================

`;
fs.writeFileSync(out, header + body);
console.log('wrote', path.relative(ROOT, out), (header + body).length, 'bytes');
