// One-shot recorder for u-e9-dyla (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const rq = require('../../utils/research-queue');
const FAM = '银行股轮动';
if (rq.findings(FAM).some(f => f.qId === 'u-e9-dyla')) { console.log('already recorded'); process.exit(0); }
rq.recordFinding(FAM, {
  qId: 'u-e9-dyla',
  type: 'understand',
  component_or_param: 'log-only probe: calc_dividend_yield (L31-54) also selects a_bonus_date + publication dates from finance.STK_XR_XD and logs DYLA per row with future=<0|1> vs context.current_dt; no logic edit',
  metric_delta: 'obj 0.3371->0.3371 (Δ0); curve bit-identical to base, max|Δcum|=0 (control verified by orchestrator); 255 calls (51x5), n_book==n_probe on all; 1460 DYLA rows, 1198 future=1; book/honest TTM dy ratio ~3.5-4x',
  window: 'TRAIN 2024 e9',
  finding: 'finance.run_query on STK_XR_XD is NOT bounded by avoid_future_data. calc_dividend_yield has no upper bound on a_bonus_date, so on every 2024 rebalance it sums every dividend from current_dt-365 through 2026. 1460 DYLA rows, 0 errors; 1198 flagged future=1 - every bank on every date, mostly with ALL date fields (incl. publication dates) in the future. E.g. 2024-01-05 600036 counts 19.72 (a_bonus_date 2024-07-11, board_plan_pub 2024-03-26), 20.0 (2025-07-11), 10.13 (2026-01-16); 2024-12-27 601398 counts 1.434 (paid 2025-01-07, impl pub 2024-12-31), 1.646, 1.414, 1.689, 1.511 (2026-10-21). Book/honest-TTM dy ratio per bank (min-max, mean): 招行 3.04-4.45 (3.75), 农行 2.37-4.83 (4.01), 工行 3.51-4.54 (4.06), 建行 2.00-4.06 (3.51), 中行 2.98-4.04 (3.54). Declared rule -> CONFIRM lookahead (known fact, measured). Not measured: whether holdings flip.',
  confidence: 'high',
  flags: 'LOOKAHEAD (data-API, finance.STK_XR_XD open upper bound); regime-specific; hindsight-pool (2026-authored 5-bank list); ⚠零滑点高估 (minor at mega-cap weekly)',
  description: 'build study/银行股轮动/build-dyla.js -> variants/dyla.py; backtestId 02770e0424aef12c3bbc5e98fd7fe91f; curve study_银行股轮动_variants_dyla__train__e9; control bit-identical to base (max|Δcum|=0), so the logged dy values are the book own inputs. Same class as CLAUDE.md data-API probes (get_extras is_st and undated get_fundamentals were clean); this one is NOT.',
  implication: 'The dy input (30% nominal, ~4x effective weight) carries up to two years of future dividends with bank- and week-varying inflation, so the cross-bank dy order can differ from the honest one. Consequences: (1) u-e9-inv (score informative) and u-e9-nobb (top-3 by score beats base) were both computed on a contaminated dy - neither may be cited as evidence for 池内轮动 until re-measured on an honest-dividend book; the score part of that edge reverts to contaminated-by-lookahead, unmeasured. (2) Next experiment is u-e9-dypit: add finance.STK_XR_XD.a_bonus_date <= context.current_dt.date() (TTM = paid in last 365 days), single change; it becomes the family reference baseline for every later Δ, including bank-imp-pit and bank-imp-eqw. (3) u-e9-ew (板块贝塔) and liq-cap are unaffected - they use no score. (4) The raw base must never be the VAL candidate: a VAL of it validates a book with lookahead. (5) Cross-family: any library strategy querying finance.STK_XR_XD (or other finance.* tables) with an open upper date bound has the same leak - avoid_future_data does not protect finance.run_query; a repo-wide grep is owed.',
  spawned: 'u-e9-dypit (to be queued by the gatekeeper); cross-family gap: finance.* open-upper-bound grep',
  edgeRef: '池内 PB+股息+1M 动量轮动',
});
const q = rq.load(FAM);
const e = q.find(x => x.id === 'u-e9-dyla');
e.status = 'done';
e.result = 'LOOKAHEAD PRESENT: finance.STK_XR_XD not bounded by avoid_future_data; 1198/1460 DYLA rows future-dated, dy inflated ~3.5-4x (varies by bank/week). Control bit-identical (max|Δcum|=0). backtestId 02770e0424aef12c3bbc5e98fd7fe91f, curve study_银行股轮动_variants_dyla__train__e9.';
rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch, 'queue status', e.status);
