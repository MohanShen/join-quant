// One-shot recorder for the family VAL lcfh-dxpit-val-e9 (family-recorder, 2026-11-01). Idempotent guard.
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
if (rq.findings(FAM).some(f => f.qId === 'lcfh-dxpit-val-e9')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'lcfh-dxpit-val-e9',
  type: 'understand',
  component_or_param: 'family VAL (finalize step): the TRAIN-selected candidate study/蓝筹分红持续性/variants/dxpit.py run verbatim on VAL 2025-01-01..2025-12-31 (runId lcfh-dxpit-val-e9, algorithmId 5d2e296d2c63f3135ebaf46732679efd, --family 蓝筹分红持续性); the one VAL per (family, bench) on epoch 9',
  metric_delta: 'VAL vs same book TRAIN: obj 0.2630->-0.0923 (Δ-0.3553); sharpe 2.02->0.09 (Δ-1.93); maxDD 14.61->14.61 (Δ0); total 40.91->5.36, annual 5.38; vol 16.0%; vs HS300 2025 +17.66 -> -12.3pp; beta 0.48, alpha -5.3%; stageGate(validate) min 1.0 -> FAIL',
  window: 'VAL 2025 e9',
  finding: 'VAL FAIL: total 5.36% / annual 5.38% / sharpe 0.09 / maxDD 14.61% / objective -0.0923 on 2025, against TRAIN 2024 0.2630 / sharpe 2.02, and 12.3pp BEHIND 沪深300 (+17.66). maxDD 14.61 is NOT a scrape artefact although it equals the TRAIN figure to 2dp: JQ\'s own stats endpoint (re-fetched free, 2026-11-01) returns max_drawdown 0.14607 over 2025-01-02 -> 04-07, and the stored curve\'s minimum is cum -14.61 on 04-07 — the book fell 3.06% on its first day, so JQ measures from initial capital while component-scan.maxDrawdownPct peaks at the first curve point (01-06) and gives 12.48 / obj -0.0710. The ledger convention is JQ\'s, so -0.0923 is the comparable objective; the gate is on sharpe and fails either way (0.0945, JQ). Monthly (curve): Jan -5.8, Feb -2.9, Mar -0.4, Apr -4.0, May +5.5, Jun +1.6, Jul +3.4, Aug +1.6, Sep -1.8, Oct +7.6, Nov +1.5, Dec -0.2 — the whole loss is Jan-Apr (trough 04-07), after which the book roughly tracks a flat-to-up path but never recovers the gap to a broad rally year in which high-dividend/红利 lagged. The post was published 2026-06-19, so 2025 was INSIDE the author\'s sample: no hindsight rescue, which makes this a stronger negative than an out-of-sample fail would be.',
  confidence: 'high',
  flags: 'regime-specific (2025 broad rally, 红利 lagging; one VAL year); in-author-sample window (post 2026-06-19) — strengthens the negative; maxDD convention (JQ initial-capital 14.61 vs first-point 12.48 — ledger uses JQ); ⚠零滑点高估 (minor, HS300 monthly); edge tests NOT re-run on VAL',
  description: 'executor: node utils/strategy-post-backtest.js study/蓝筹分红持续性/variants/dxpit.py "lcfh-dxpit-val-e9" --window val --family 蓝筹分红持续性 --source-file study/蓝筹分红持续性/variants/dxpit.py; VAL-SPENT recorded by the executor (consumption.tsv validate row, epoch 9); curve study_蓝筹分红持续性_variants_dxpit__val__e9 (243 pts 2025-01-02..12-31, final cum 5.36, benchCum 17.66). Recorder verified maxDD/period/sharpe against POST /algorithm/backtest/stats. Archived validated_strategies/lcfh-dxpit-val-e9.py (gate_val fail, body sha256 = dxpit.py).',
  implication: 'CLOSES VAL for this family on epoch 9: the one validation per (family, bench) is spent and failed, so there is NO candidate on this bench — no second VAL on any variant (that would be selection on VAL; JQ_ALLOW_REVAL must not be set), and no improve round should be run toward one. The gate now reads a failed VAL with a measured realizability, i.e. a measured rejection (owner none), not a to-do; the family reopens only on a new member or a new bench. RE-SCOPES both measured edges: 股息率 and 分红持续性 stay measured (their tests ran on TRAIN), but they are 2024-scoped readings and must not be cited as forward-valid — the candidate built on them failed 2025 inside the author\'s own sample. DROPS liq-2: the capacity of a book that failed VAL buys no decision (it was only ever optional, for integration and the dxpit-vs-dxew choice, both now moot). Cross-family: with 银行股轮动 (VAL 0.69) and 红利低频 (OOS -0.51), this is the third dividend/红利 book on the bench that fit 2024 and did not carry forward — a new dividend family arriving should be expected to fail VAL unless its edge is shown in a non-2024 window, and dxew\'s style basket (not validated) inherits the same 2025 regime problem.',
  spawned: 'none (closed: liq-2 dropped as moot)',
  edgeRef: '股息率,分红持续性',
});

const q = rq.load(FAM);
const liq2 = q.find(x => x.id === 'liq-2');
if (liq2) {
  liq2.status = 'dropped';
  liq2.note = 'recorder 2026-11-01 (lcfh-dxpit-val-e9): DROPPED as moot — the candidate failed VAL 2025 (sharpe 0.09) and the family has no candidate on epoch 9; capacity of a failed book informs no decision (integration and dxpit-vs-dxew both moot). Reopen only with a new candidate on a new bench. ' + (liq2.note || '');
}
rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.map(e => `${e.id}\t${e.status}`).join('\n'));
