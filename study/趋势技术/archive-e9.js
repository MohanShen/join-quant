// Archives the epoch-9 VAL of the family champion (9befa9b8) to the product shelf — a FAILED VAL,
// archived with gate_val: fail per the family-recorder contract (the shelf records what reached
// validation; the exit gate filters on the field).
//   node -e "require('./study/趋势技术/archive-e9.js')"
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');

const HEADER = `# ===== VALIDATED STRATEGY (run-family archive) — join-quant epoch 9 =====
# expId:            qsjs-e9-9befa9b8
# runId:            qsjs-e9-9befa9b8-val   (the VAL recorded in data/consumption.tsv; algorithmId 63c6c78d15c536ae8ce9a30c44f13f93)
# ideaId:           q-e9-val  (step-0b narrow job: finalise the family champion on VAL; no new idea)
# family:           趋势技术   (source champion: strategies/2026-06-08_十日均线策略-9befa9b8.py — NOT the page base 33b1b1e3,
#                   which reads today's close at 08:00 and returns no-trades under avoid_future_data, so it has no epoch-9 row)
# sourceBook:       study/趋势技术/champion-e9.py   (builder: study/趋势技术/build-e9.js = py2to3(source) + OVERRIDE,
#                   byte-identical to the normalizer's construction, so the epoch-9 ledger row IS this book)
# mutation:         none — the champion as written, pinned. Single-stock MA10 timer on 600030 中信证券:
#                   all-in when price > MA10, flat when below (2016 community clone of post/664).
# train_objective:  0.1912   (TRAIN 2024-01-01..2024-12-31: total 34.13% / annual 34.13% / maxDD 15.01% / sharpe 1.03)
# val_objective:    -0.1143  (VAL   2025-01-01..2025-12-31: total -0.72% / annual -0.72% / maxDD 10.71% / sharpe -0.31)
# sharpe_val:       -0.31
# gate_val:         fail     (sharpe -0.31 < 1.0)
# harness_epoch:    9
# verified:         VAL checked against the stored curve
#                   data/series/2026-06-08_十日均线策略-9befa9b8__val__e9.json (243 points, final cum -0.72, maxDD 10.71);
#                   TRAIN curve …__train__e9.json reproduces the ledger row digit for digit (34.13 / 15.01).
# realizability:    3 — one of the most liquid A-shares (中信证券, multi-billion CNY daily turnover) traded all-in /
#                   all-out on a daily bar with a ¥1M book; the 5% volume cap and the 2e6 feasibility floor cannot bind.
#                   Structural, not liq-floor-measured. Scope: this book (= the champion as written).
# ⚠ caveats:        (1) THIN TRAIN MARGIN — sharpe 1.03 cleared the 1.0 gate by 0.03, and the 2024 number is one
#                   stock's beta in a year that contained the 2024-09 V-reversal (a brokerage name is the
#                   leveraged expression of that rally). VAL 2025 shows the timer has nothing of its own: flat
#                   (-0.72%) with a 10.7% drawdown.
#                   (2) The family's measured edges (动量 / 趋势择时) were measured on the RPS base 33b1b1e3 on the
#                   epoch-6 bench (TRAIN 2022-23) and describe a different book. Nothing on this page measures why
#                   THIS book earned 34% in 2024; the VAL says it did not carry over.
#                   (3) The family is a catch-all bucket (§5); this champion is a single-instrument MA-cross book,
#                   the same mechanism as 4 siblings that all fail — the bucket's one epoch-9 pass was its thinnest.
# =========================================================================

`;

fs.writeFileSync(path.join(ROOT, 'validated_strategies/qsjs-e9-9befa9b8.py'),
  HEADER + fs.readFileSync(path.join(__dirname, 'champion-e9.py'), 'utf8'));
console.log('archived validated_strategies/qsjs-e9-9befa9b8.py (gate_val: fail)');
