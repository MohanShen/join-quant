// Recorder helper for u-2: spawns u-6/u-7 (time-shifted placebos) and records the u-2 finding.
// One-shot; guarded so a re-run cannot double-append.
const rq = require('../../utils/research-queue');
const F = '小盘ETF双轨切换';
const EDGE = '微盘广度推力择时';

if (rq.findings(F).some(f => f.qId === 'u-2')) { console.log('u-2 already recorded — nothing done'); return; }

const common = {
  kind: 'understand', edgeRef: EDGE, status: 'queued',
  from: ['u-2 (calendar substitute, obj −0.8056: lock PHASE alone moved objective 0.60 vs u-1)',
         'u-1 (always-偷鸡, obj −0.2040)',
         'edge 微盘广度推力择时 .test second half (same 3 entries, dates shifted)'],
};
const why = 'The edge test\'s declared second half. u-1/u-2 showed the outcome is dominated by WHERE each 30-day lock lands, so exposure-matched timing controls cannot separate signal from luck; a time-shifted placebo with the base\'s own n=3 entries can. Read u-6 and u-7 TOGETHER: CONFIRMS signal (weakly) if BOTH shifted books score objective <= 0.36; "lucky days / phase" if EITHER stays >= 0.6. Between = inconclusive. n=3, so this can only WEAKEN the claim, never establish it — a pass keeps the edge proposed-with-support, it does not license measured. Cost ~3-6 backtest-min each.';

const have = new Set(rq.load(F).map(e => e.id));
if (!have.has('u-6')) rq.add(F, { ...common, id: 'u-6', rank: 3,
  title: 'placebo +5: base entries hard-coded at 2024-02-28 / 10-15 / 11-29 (base dates +5 trading days), DDDD removed',
  hypothesis: 'If the DDDD cosine signal carries information, the same 3 entries 5 trading days later lose most of the base\'s excess.',
  why,
  design: 'Base 0d1bbe83, epoch-9 pins. Replace the DDDD entry condition with `context.current_dt.date() in {2024-02-28, 2024-10-15, 2024-11-29}` (trading days verified against the u-2 curve\'s date list: base 02-21/10-08/11-22 +5). Keep the 30-day lock, exit-to-摸狗, selection, 14:00 check_limit_up verbatim. Log each 偷鸡 entry and per-period return.',
});
if (!have.has('u-7')) rq.add(F, { ...common, id: 'u-7', rank: 4,
  title: 'placebo −5: base entries hard-coded at 2024-02-06 / 09-24 / 11-15 (base dates −5 trading days), DDDD removed',
  hypothesis: 'Mirror of u-6; together they bracket the base\'s entry dates.',
  why: why + ' ⚠ Asymmetry: the −5 dates are not neutral — 02-06 sits at the Feb 2024 micro-cap crash low and 09-24 is the policy-announcement day, so u-7 can score WELL by its own luck. A strong u-7 therefore reads as "phase/luck dominates", not as evidence for DDDD.',
  design: 'Base 0d1bbe83, epoch-9 pins. Replace the DDDD entry condition with `context.current_dt.date() in {2024-02-06, 2024-09-24, 2024-11-15}` (base 02-21/10-08/11-22 −5 trading days; 02-06 spans the Spring Festival closure, verified on the u-2 curve dates). Everything else verbatim as u-6.',
});

rq.recordFinding(F, {
  qId: 'u-2', type: 'understand',
  component_or_param: 'DDDD 进场条件 → `context.current_dt.month not in (1, 4)`，30 日锁定保留',
  metric_delta: 'Δobjective −1.5322 vs base (0.7266→−0.8056); −0.6016 vs u-1 (−0.2040); sharpe 2.85→−0.80; total 89.75→−26.20%; maxDD 17.09→54.36',
  window: 'TRAIN 2024 (epoch 9)',
  finding: 'Calendar substitute (variant u-2-calendar, builder build-u2.js, algorithmId b81302eb…, curve study_小盘ETF双轨切换_variants_u-2-calendar__train__e9, final cum −26.20 verified) scores total −26.20% / sharpe −0.80 / maxDD 54.36 / objective −0.8056. 摸狗 through January; first 偷鸡 entered 02-01 (just before the Feb 2024 micro-cap crash), then re-entered at every lock end: 03-25, 05-14, 06-27, 08-09, 09-25, 11-14, 12-27 (~213 偷鸡 days vs base 88). April was NEVER skipped: the 03-25 lock ran to 05-13 and the month condition only binds on a lock-end day. Blocks: 02-02..03-22 −22.23%, 03-25..05-13 −20.83%, 05-14..06-26 −14.55%, 06-27..08-08 +13.89%, 08-09..09-24 −1.13%, 09-25..11-13 +35.38%, 11-14..12-26 −3.04%. maxDD window 01-30..07-10. So u-2 is effectively always-偷鸡 minus January with the lock cycle phase-shifted by ~one month vs u-1, and that phase shift alone moved objective by 0.60 — the same order as the base-vs-u-1 gap (0.93).',
  implication: 'Do NOT read the queue rule literally (≤0.36 ⇒ "DDDD informative beyond calendar"): u-2 never tested the calendar hypothesis it was designed for (April was not skipped) and its loss is mostly lock PHASE, not information. The real conclusion is that this book\'s outcome is dominated by where each 30-day lock lands, so exposure-matched timing controls (u-1, u-2 and any further calendar rule) cannot separate the cosine signal from luck — that line of control is closed as non-discriminating. Opens the edge test\'s declared second half: a time-shifted placebo of the base\'s own 3 entries (u-6 = +5 trading days, u-7 = −5), confirm only if BOTH ≤0.36, "phase/luck" if EITHER ≥0.6. Edge stays proposed; n=3 means the placebo can only weaken the claim. Also: since a one-month phase shift is worth ~0.6 objective, any improve variant on this book that changes entry timing or lock length must be read as noise-dominated unless its Δ clearly exceeds ~0.6.',
  spawned: 'u-6,u-7',
  edgeRef: EDGE,
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (one-year TRAIN); overfit-cliff (lock phase); design-miss (April never skipped)',
  description: 'Literal queue threshold satisfied (−0.8056 ≤ 0.36) but uninformative about DDDD; see implication.',
});
console.log('recorded u-2; queue:', rq.load(F).map(e => `${e.id}:${e.status}`).join(' '));
