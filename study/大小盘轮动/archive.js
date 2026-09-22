// Archives the VAL-passed candidate to validated_strategies/ and records the round's research event.
//   node -e "require('./study/大小盘轮动/archive.js')"
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');

const HEADER = `# ===== VALIDATED STRATEGY (run-family archive) — join-quant epoch 6 =====
# expId:            dxp-imp-1
# ideaId:           imp-1  (= study u-1: the style vote bypassed, the 高息低价小盘 sleeve held always)
# baseExpId:        dxp-e6-0  (= base 2f5bc859 + epoch-6 OVERRIDE, study/大小盘轮动/baseline-e6.py)
# family:           大小盘轮动   (source base: strategies/2026-05-20_四择时高息低价小市值和白马大市值轮动-2f5bc859.py)
# mutation:         one edit — signal() sets g.signal='small' and returns before the three votes are computed
#                   (they write no g state). dapan kept. Built by study/大小盘轮动/build-e6.js.
# train_objective:  0.6623   (TRAIN 2022-01-01..2023-12-31: total 226.83% / annual 80.93% / maxDD 14.70% / sharpe 3.51; base 0.4567)
# val_objective:    0.3144   (VAL   2024-01-01..2025-12-31: total 181.61% / annual 67.81% / maxDD 36.37% / sharpe 1.88)
# sharpe_val:       1.88
# gate_val:         pass     (sharpe 1.88 >= 1.5)
# harness_epoch:    6
# ranAt:            2026-09-22
#
# flags:
#   ⚠⚠ VAL's drawdown is 36.37%, 2024-01-04 -> 2024-02-07 (the microcap stampede); 2024-H1 total -3.40%.
#      The VOTING base over the same half (epoch-2 study q-3; epoch 2->6 is a no-op for this book) made
#      +37.22% with an 18.23% drawdown. The vote this candidate removes is a net cost on TRAIN and was
#      insurance in 2024-02. There is NO evidence this candidate beats the base out of sample.
#      Adopted on TRAIN only.
#   ⚠  零滑点台 — trades the 10 smallest dividend-paying profitable stocks under 9 yuan; microcap impact and
#      the 5-yuan minimum commission are not in these numbers. Monthly rebalance keeps turnover low.
#   ⚠  epoch-2 study q-3 ran the base on 2024-H1 before this epoch's VAL definition; attribution only.
#   Full write-up: wiki/families/大小盘轮动.md §1/§2/§4/§6 (e6-0, u-1..u-8, imp-1..3, val-imp-1).
# ================================================================================

`;

fs.writeFileSync(path.join(ROOT, 'validated_strategies/dxp-imp-1.py'),
  HEADER + fs.readFileSync(path.join(ROOT, 'enhance/candidates/dxp-imp-1.py'), 'utf8'));

require('../../utils/consumption').record({
  key: '大小盘轮动', kind: 'family', stage: 'research', runId: 'run-family-2026-09-22', outcome: 'done',
  note: '9 epoch-6 TRAIN backtests + 1 VAL (~27 JQ min); 7 understand + 2 improve findings + VAL; '
    + 'base 2f5bc859 epoch-6 obj 0.4567 sharpe 2.68 (epoch 2: 0.4550), 2022 +57.6% / 2023 +57.0%; '
    + 'edge: 规模因子 measured (largest-first in the same filter set keeps 19% of annual), '
    + '低价股效应 NEW + measured (no price cap keeps 50%, both years; 9-12 yuan plateau, 5 yuan cliff), '
    + '股息率 refuted (no dividend gate raises annual +6.6pt; the low-yield loss was size), '
    + '风格轮动择时 back to proposed/contested (TRAIN refutes: always-small +0.2056 both years; '
    + 'VAL 2024-H1 always-small -3.4%/DD 36% vs voting base +37%/DD 18%); dapan +0.057 on always-small, 2022 only; '
    + 'imp-1 always-small adopted on TRAIN; imp-2 (no dividend gate, +0.049, 2022 only) not adopted; '
    + 'imp-3 (5-yuan cap) rejected; VAL spent on imp-1: obj 0.3144 sharpe 1.88, pass, DD 36.37% in the 2024-02 stampede',
});
console.log('archived validated_strategies/dxp-imp-1.py + research event');
