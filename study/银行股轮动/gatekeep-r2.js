// gatekeeper round 2 (post u-e9-dyla) for 银行股轮动: queue rewrite. Idempotent (refuses a second apply).
const path = require('path');
const rq = require(path.join(__dirname, '../../utils/research-queue'));
const F = '银行股轮动';
const q = rq.load(F);
if (q.some(e => e.id === 'u-e9-dypit')) throw new Error('already applied');
const by = id => q.find(e => e.id === id);
const G = 'gatekeeper 2026-11-01 (round 2, post-dyla): ';
const ZERO = 'ZERO-COST PATH: if u-e9-dypit\'s RANK log shows the honest score order == the leaky order on EVERY rebalance AND DYZERO = 0, this book is identical to the leaky run by construction (eligibility and every downstream decision are the same). Record the leaky result as re-confirmed on honest dividends with no backtest (u-e9-noma precedent).';

const dypit = {
  id: 'u-e9-dypit', kind: 'understand',
  title: 'honest-dividend baseline: add finance.STK_XR_XD.a_bonus_date <= context.current_dt.date() to calc_dividend_yield (TTM = paid in the last 365 days, nothing future); all else verbatim; log per-rebalance holdings and honest-vs-leaky score rank',
  hypothesis: 'Part of the base level (0.3371) was bought by the STK_XR_XD lookahead (dy inflated ~3.5-4x, varying by bank and week). With honest dividends the score ranks differently on some weeks and the book falls toward or below equal-weight beta (u-e9-ew 0.3185).',
  why: 'type: lookahead removal and new family reference baseline. Spawned by u-e9-dyla (lookahead measured, 1198/1460 rows future-dated). It is the honest book every later Δ (inv-h, nobb-h, pit, eqw) is measured against, and the only route to a VAL candidate without contamination. A likely "the leak bought most of the residual" is a GOOD outcome: it is information either way. DECISION RULE (declared before the number): report Δobj/Δsharpe vs base 0.3371/2.37 AND vs u-e9-ew 0.3185/2.23, plus leak share = (0.3371 - dypit)/(0.3371 - 0.3185). (a) dypit obj < 0.3185 => the honest score adds NOTHING over beta (rotation residual <= 0). (b) 0.3185 <= dypit < 0.3385 (within +0.02 of EW, which is the size of the original base-EW gap) => residual indistinguishable from beta on this bench; record it as that, not as support. (c) dypit >= 0.3385 => honest residual positive, provisional until inv-h. Holdings: count the weeks where the dypit target set (and order) differs from the base twin. 0 differing weeks plus a bit-identical curve => "the leak moved dy but not decisions on 2024". ⚠ Second channel: the L110 dy<=0 exclusion. An honest 365-day window can miss a bank\'s annual payment near its anniversary (e.g. paid 2023-07-10, next on 2024-07-11), which drops the name for a week for a DEFINITIONAL reason rather than the leak. Log it (DYZERO) and report the count separately. Cost ~1 min (two ~30s runs).',
  design: 'Base study/银行股轮动/baseline.py (2a323522 + py2to3 + OVERRIDE, epoch 9). ONE asserted logic edit in calc_dividend_yield: the filter gains `finance.STK_XR_XD.a_bonus_date <= context.current_dt.date()` beside the existing `>= start_date` (lower bound verbatim). Observation only, in try/except that log.error\'s any exception (build-dyla.js pattern): (1) RANK date=<d> code=<c> pb=<> dy_h=<honest> dy_l=<leaky, from a second query without the upper bound> s_h=<honest score> s_l=<leaky score> for each scored name; (2) DYZERO date=<d> code=<c> when honest dy <= 0 (name excluded at L110); (3) HOLD date=<d> n_elig=<k> target=<ordered codes> just before the 调仓 block, and HOLD ... target=KEEP on the L154 early-return path. CONTROL TWIN (same builder, second file variants/u-e9-dypit-ctl.py): the base with ONLY the identical HOLD line and no logic edit. It must reproduce 0.3371 / 2.37 / 45.54 / 11.83 bit-identically, and it supplies the base holdings for the diff (the base never logged them). Page logs with study/小市值/pagelog.js (100 lines/page; expect >1000 lines). Report: dypit metrics, Δ vs base and EW, leak share, weeks with a different target set / order, weeks where the same-state honest vs leaky rank differs (from RANK), DYZERO count, daily corr vs base.',
  from: [
    'u-e9-dyla implication (2): u-e9-dypit is the next experiment and the new reference baseline',
    'wiki §4 [下一步 / 新基线] u-e9-dypit',
    'u-e9-ew 0.3185 (beta reference)',
    'base TRAIN 2024 0.3371 / 2.37 / 45.54 / 11.83',
  ],
  edgeRef: '池内 PB+股息+1M 动量轮动', rank: 1, status: 'active',
  note: G + 'ACCEPTED, rank 1, ACTIVE. Falsifiable (declared bands vs EW). One experiment: the twin is its control, not a second question. Grounded in a measured lookahead. Not answered yet: dyla measured the leak in the INPUT, not its effect on the book. Added the base HOLD-logging twin (the base never logged holdings, so a diff needs one) and the DYZERO channel. ⚠ Its RANK log can make inv-h / nobb-h zero-cost (see their notes).',
  result: null,
};

const invh = {
  id: 'u-e9-inv-h', kind: 'understand',
  title: 'score informativeness on HONEST dividends: u-e9-inv (reverse=False at L147 and L157) rebuilt on the dypit book; log n_eligible + order per rebalance',
  hypothesis: 'With honest dividends, the PB+dy+1M score still picks better banks within the 5-name pool than its inverse does.',
  why: 'type: re-measure of a withdrawn conclusion (u-e9-inv ran on leaky dy; dyla says it may not be cited). Decides whether the score half of 池内轮动 exists at all, which sets how pit / eqw / the VAL candidate are read, so it carries the most information after dypit. A refutation (score has no sign once honest) is a strong, useful result: the family is then beta only. DECISION RULE re-anchored to dypit (not base): CONFIRM score if Δobj(inv-h - dypit) <= -0.08 OR Δsharpe <= -0.55; REFUTE if |Δsharpe| <= 0.3 AND |Δobj| <= 0.03; anything between = partial. Valid only if binding: n_eligible >= 3 in >= 8 weeks, otherwise "untested on this bench". ' + ZERO + ' Cost ~30s.',
  design: 'Base = variants/u-e9-dypit.py (baseline + a_bonus_date upper bound), NOT baseline.py. Two asserted edits identical to build-inv.js: L147 sorted(..., reverse=True) -> reverse=False; L157 eligible_stocks.sort(..., reverse=True) -> reverse=False. Keep INV date=<d> n_eligible=<k> order=<codes>. Nothing else changes. Control: dypit\'s own metrics.',
  from: [
    'u-e9-dyla implication (1): u-e9-inv withdrawn, re-measure on honest dividends',
    'u-e9-inv (leaky) Δobj -0.0951, binding 17/14 weeks',
    'u-e9-dypit (new reference baseline)',
  ],
  edgeRef: '池内 PB+股息+1M 动量轮动', rank: 2, status: 'queued',
  note: G + 'ACCEPTED, rank 2. Not a duplicate of u-e9-inv: that measurement is contaminated (dyla) and the family page withdraws its conclusion. Rule re-anchored to the dypit baseline. Conditional zero-cost path declared.',
  result: null,
};

const nobbh = {
  id: 'u-e9-nobb-h', kind: 'understand',
  title: 'Bollinger mid-band filter off on HONEST dividends: u-e9-nobb (L137 -> if True) rebuilt on the dypit book; log STOP / NBB / HOLD',
  hypothesis: 'On the honest-dividend book, always holding the top 3 by score still beats the dip-entry filter, so the leaky nobb result survives.',
  why: 'type: re-measure of a withdrawn conclusion. The filter\'s eligibility does not read dy, but its Δ does: removing the filter hands every week to the score\'s top 3, so the leaky ordering decided which names nobb bought. The one BINDING closure on this family (u-e9-nobb, closedAtEpoch 9) rests on that contaminated ordering, so this is NOT a duplicate: same bench, invalidated evidence. DECISION RULE re-anchored to dypit: REFUTE the filter if Δsharpe(nobb-h - dypit) >= 0 AND ΔmaxDD <= +2pp; CONFIRM the filter if Δsharpe <= -0.3 OR ΔmaxDD >= +3pp; anything between = partial. Log STOP triggers (0 in the leaky runs) so the stop confound stays separable. ' + ZERO + ' Not adoptable on TRAIN alone either way (it removes a risk control on a one-year uptrend). Cost ~30s.',
  design: 'Base = variants/u-e9-dypit.py, NOT baseline.py. One asserted edit identical to build-nobb.js: the L137 condition -> if True:. Keep the STOP / NBB / MA log lines. Nothing else changes. Control: dypit\'s own metrics.',
  from: [
    'u-e9-dyla implication (1): u-e9-nobb withdrawn',
    'u-e9-nobb (leaky) Δobj +0.0428; binding closure closedAtEpoch 9 rests on the contaminated ordering',
    'u-e9-dypit (new reference baseline)',
  ],
  edgeRef: '池内 PB+股息+1M 动量轮动', rank: 3, status: 'queued',
  note: G + 'ACCEPTED, rank 3. Judged the binding closure u-e9-nobb: its REASONING depends on the leaky score order, so it does not bind the honest book. Rank 3, not 4 (the orchestrator suggested pit first), on the information axis: this question is open, while pit is expected to come back inert on TRAIN. Neither blocks the other and both will run, so swap them freely if VAL sequencing matters more.',
  result: null,
};

const pit = by('bank-imp-pit');
pit.why = 'REBUILT ON THE DYPIT BOOK (u-e9-dyla: the raw base carries a dividend lookahead and may never be a VAL candidate, so a pit test on it would validate the wrong book). Expected gain ~0 on TRAIN: 工/建/农/中/招 are very likely the 2024 top 5 by market cap throughout. Its value is removing the hindsight caveat before VAL. Novelty low, VAL value high. DECISION RULE (re-anchored): ADOPT as the VAL-candidate pool if sharpe >= 1.0 AND objective falls by < 0.05 vs dypit; quote dypit/pit as a PAIR (CLAUDE.md q-e9-pit). Report the weeks where the pit set differs from the hardcoded 5 and which names they were (e.g. 邮储 601658). If no week differs, record "pool is pit-equivalent on 2024". ⚠ Any new name enters with HONEST dy (the dypit filter applies to it too); confirm in the log that the a_bonus_date upper bound covers every scored name. The 2025 check is still owed before VAL (no VAL-window run here). Cost ~1 min (weekly industry fetch).';
pit.design = 'Base = variants/u-e9-dypit.py (baseline + a_bonus_date <= current_dt.date()), NOT baseline.py. At the top of rebalance: g.stocks = top 5 of get_industry_stocks(<JQ bank industry code>, date=context.previous_date) minus ST names (is_st on previous_date), ordered by valuation.market_cap desc via get_fundamentals(date=context.previous_date). The hardcoded ICBC MA250 reference stays (it is a timing input, not the pool). Log PIT date=<d> pool=<codes>. Nothing else changes. Control: dypit\'s own metrics.';
pit.from = [...pit.from, 'u-e9-dyla: raw base is not a VAL candidate', 'u-e9-dypit (new reference baseline)'];
pit.rank = 4;
pit.note += ' ‖ ' + G + 'RE-GATED: base switched from baseline.py to the dypit book, rule re-anchored to dypit, pair-quoting required. Rank 4 (behind nobb-h on information; see the nobb-h note).';

const eqw = by('bank-imp-eqw');
eqw.why = 'REBUILT ON THE DYPIT BOOK (u-e9-dyla). Expected gain: probably positive on objective in a rising 2024 bank year, but that is exposure/beta, not mechanism. With 2 names the 40% cap still holds 80%, so the change bites only in 3-name weeks. u-e9-ew already CONFIRMED beta, so this mostly re-buys beta. Novelty low. DECISION RULE (re-anchored): ADOPT only if sharpe >= dypit sharpe (does not fall) AND objective rises > 0.02 vs dypit; otherwise reject. Report the number of 3-name weeks (the only weeks it can change). If inv-h REFUTES the score, read this as an exposure knob on a beta book and prefer the EW reference over it. The cap is KEPT so this stays one change. Cost ~30s.';
eqw.design = 'Base = variants/u-e9-dypit.py, NOT baseline.py. One asserted edit: compute target_per_stock_value = total_value*target_position_ratio/max(1,len(target_holdings)) after target_holdings is final instead of at L168; the 40% cap in the 调仓 loop is unchanged. Log EQW date=<d> n_target=<k>. Nothing else changes. Control: dypit\'s own metrics.';
eqw.from = [...eqw.from, 'u-e9-ew CONFIRM beta', 'u-e9-dypit (new reference baseline)'];
eqw.rank = 5;
eqw.note += ' ‖ ' + G + 'RE-GATED: base switched to dypit, rule re-anchored to dypit sharpe/objective. Rank 5 (last): an exposure change, and beta is already measured.';

for (const e of [dypit, invh, nobbh]) { const b = rq.validate(e); if (b.length) throw new Error(e.id + ': ' + b.join('; ')); }
const i = q.findIndex(e => e.id === 'bank-imp-pit');
q.splice(i, 0, dypit, invh, nobbh);
rq.save(F, q);
console.log(q.filter(e => ['queued', 'active'].includes(e.status)).sort((a, b) => a.rank - b.rank).map(e => `${e.rank} ${e.id} ${e.kind} ${e.status}`).join('\n'));
