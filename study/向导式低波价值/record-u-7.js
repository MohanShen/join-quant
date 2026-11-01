// recorder helper for u-7 (one-shot). Writes the finding and marks the queue entry done.
const rq = require('../../utils/research-queue');
rq.recordFinding('向导式低波价值', {
  qId: 'u-7',
  type: 'understand',
  component_or_param: 'pool-EW CONTROL (run dxlv-u-7): base 8b9cb8e2 + pool-EW harness H1 exit off / H2 max_hold 5->1000 / H3 cash split by len(buy_lists); yuan-ATR<0.15 entry and PE 6-11 kept',
  metric_delta: 'u-7 total/annual 29.50, sharpe 1.08, maxDD 12.20, obj 0.1730 vs base 29.38/1.19/10.80/0.1858 => Δobj -0.0128, Δsharpe -0.11, maxDD +1.40pp; daily corr 0.9784 (242/242 days, same start). Recomputed from curve study_向导式低波价值_variants_u-7__train__e9: final cum 29.50, maxDD 12.21, obj 0.1729, corr 0.9784; curve-sharpe estimator 1.036 vs base 1.136 (Δ -0.10, same direction and size as JQ)',
  window: 'TRAIN 2024',
  finding: 'VALID control (decision rule met). POOL0 = exactly 600018 601006 601117 601319 601669 601800; day-1 EWDEPLOY cash_after 1894.66 / total 999700.66 = 0.19% (<=5%). With exits off it is a day-1 6-name EW buy-and-hold. Per-name 2024 price return: 600018 +24.9, 601006 -5.7, 601117 +29.7, 601319 +57.4, 601669 +11.7, 601800 +37.7. vs base: 29.50 vs 29.38 total, sharpe 1.08 vs 1.19, maxDD 12.20 vs 10.80, corr 0.9784 — the JOINT effect of exit-off + 601800 added (code-order [:5] cut removed); it cannot be split. Later buy days spread dividend cash into 12 tiny extra names (600219 600000 601618 601868 601288 600039 601328 601988 600795 601398 601658 600023), 2.9% of the book at year end. amount=0 order errors are harmless (13 in the stored filtered log; 16 reported from the full log).',
  confidence: 'high (validity); medium (exit reading — joint Δ, one exit event)',
  flags: 'regime-specific',
  description: 'Control for u-3/u-4/u-5. The base exit fired once in 2024 (601117 sold 10-21 @8.18, +28%); u-7 holds it to 8.29. The dividend dust (2.9%) arises by the same mechanism in u-7/u-3/u-4/u-5, so it is a shared contaminant, not a per-variant difference. Log: study/向导式低波价值/log-u-7.txt; build: build-u-7.js.',
  implication: 'u-7 is a valid control: dispatch u-3 (price gate removed), u-4 (PE band removed) and u-5 (relative-ATR gate), each read as Δ vs u-7 and never vs the 5-name base. Closed for 2024: the ATR>0.35 sell plus the code-order [:5] cut are not a source of return — removing both moves total +0.12pp and sharpe -0.11 at corr 0.98, so the book is the day-1 basket and the 择时 in its title contributes nothing measurable on TRAIN (one exit fire, on 601117). Do not queue exit-threshold tuning variants; reopening needs a window with more than one exit event. The 2.9% dividend dust is shared, so u-3/u-4/u-5 deltas under ~0.05 sharpe are within it and must not be read as a selection effect.',
  spawned: 'none (unblocks existing u-3, u-4, u-5)',
  edgeRef: '低价股效应',
});
const e = rq.load('向导式低波价值');
const h = e.find(x => x.id === 'u-7');
h.status = 'done';
rq.save('向导式低波价值', e);
console.log(h.status, String(h.result).slice(0, 80));
