/**
 * family-queue.js — the daily pipeline's unit of work is a FAMILY, not a strategy.
 *
 * The pipeline used to carry four independent queues (enhance / study / normalize / discover) and
 * pick one stage per fire. That made normalize and discover compete with the agent loops for the
 * same minutes, and it meant a newly normalized strategy had no route into research except a
 * human noticing. The new shape is a funnel:
 *
 *     discover -> fetch -> normalize -> ASSIGN FAMILY -> family queue -> /run-family
 *
 * and the daily job drains the family queue first, then tops the funnel back up.
 *
 * ## Scoring, and the join that is dead
 *
 * A family's score is the **max post-screen priority among its members** — the screening rubric
 * already ranks on marginal information, so the best candidate in a lineage is what says whether
 * the lineage deserves attention.
 *
 * ⚠ That score CANNOT be computed per-strategy. `screen/verdicts.json` is keyed on 32-hex
 * postIds, screened 2026-09-17, five days AFTER `migrate-unique-key.js` re-keyed the discovery
 * store to `uniqueKey` (2026-09-12). JoinQuant re-mints postIds per request, so those keys now
 * dereference to nothing: **0 of 857 verdicts resolve to a held strategy**. This is exactly the
 * failure CLAUDE.md warns about — "never key a store, a dedup or a join on an id" — and the
 * verdicts did.
 *
 * What rescues it: each verdict carries its own `family` field, written by the screener. So the
 * score is computed on the SCREENING side (max priority per family name) instead of by joining
 * each member. All 14 registered families get a score this way.
 *
 * ⚠ Read it for what it is: the best thing the screen has SEEN in that lineage, not the best
 * thing we HOLD in it. For a "what deserves attention next" queue those are close enough to be
 * useful and the difference is reported, not hidden. Restoring the literal reading needs a
 * re-screen keyed on uniqueKey (`screen-prefilter.js --keys`), which costs tokens and zero
 * backtest minutes.
 *
 * Usage:
 *   node utils/family-queue.js              # the queue
 *   node utils/family-queue.js --gaps       # unassigned strategies + unscored families
 *   node utils/family-queue.js --json
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const ledger = require('./ledger');
const FAM_DIR = path.join(ROOT, 'wiki/families');
const STRAT_PAGES = path.join(ROOT, 'wiki/strategies');
const LEDGER = path.join(ROOT, 'harness/normalize-train.tsv');

const { field: fm } = require('./frontmatter');

/** sourceFile -> { family, page } for every strategy page that declares one. */
function assignments() {
  const out = new Map();
  let files = [];
  try { files = fs.readdirSync(STRAT_PAGES).filter(f => f.endsWith('.md')); } catch { return out; }
  for (const f of files) {
    const t = fs.readFileSync(path.join(STRAT_PAGES, f), 'utf8');
    const src = fm(t, 'sourceFile');
    if (!src) continue;
    const family = fm(t, 'family').replace(/[[\]]/g, '');
    out.set(src, { family, page: f, proposal: fm(t, 'familyProposal').replace(/[[\]]/g, '') });
  }
  return out;
}

/**
 * Normalized rows at a measurement-valid epoch, newest epoch per file.
 *
 * ⚠ Columns come from `utils/ledger.js`. This read `c[0]`..`c[13]` directly, as seven other files
 * did, so a column inserted into normalize-*.tsv would have silently relabelled every field.
 */
function normalized() {
  const harness = require('./harness-config');
  const best = new Map();
  for (const r of ledger.normalized()) {
    // ⚠ An unstamped row is treated as epoch 2 HERE and only here: that is this queue's policy
    // (the oldest bench still in the ledger), not the ledger's, which reports it as null.
    const epoch = r.epoch || '2';
    const row = {
      sourceFile: r.sourceFile, title: r.title, epoch,
      objective: typeof r.objective === 'number' ? r.objective : null, gate: r.gate,
      // sharpe is the /run-family ORDER key since 2026-10-16 — see the sort below.
      sharpe: r.sharpe,
      valid: harness.measurementValid(epoch),
    };
    const prev = best.get(r.sourceFile);
    if (!prev || Number(epoch) >= Number(prev.epoch)) best.set(r.sourceFile, row);
  }
  return [...best.values()];
}

/**
 * family name -> max post-screen priority. Computed from the verdicts' own `family` field,
 * because the per-strategy join is dead (see the header).
 */
function screenScores() {
  const out = new Map();
  try {
    const V = JSON.parse(fs.readFileSync(path.join(ROOT, 'screen/verdicts.json'), 'utf8')).verdicts || {};
    for (const v of Object.values(V)) {
      if (!v.family) continue;
      const p = Number(v.priority) || 0;
      if (!out.has(v.family) || p > out.get(v.family)) out.set(v.family, p);
    }
  } catch { /* no verdicts yet */ }
  return out;
}

function registered() {
  try { return fs.readdirSync(FAM_DIR).filter(f => f.endsWith('.md')).map(f => f.replace(/\.md$/, '')); }
  catch { return []; }
}

/**
 * The queue.
 *
 * `reason` is the field the daily pipeline acts on, and it is deliberately FOUR-valued rather
 * than a boolean "due": a family with new members is NOT the same work as a family that has
 * never been researched, and /run-family's early exit depends on telling them apart.
 *
 *   never-researched  | nothing has ever run on it
 *   new-members       | members arrived since the last round
 *   integrate-blocked | done, but stuck at the NEXT stage's gate on a step this loop performs
 *   done              | nothing to do
 *
 * `integrate-blocked` carries the gate's own sentence in `note` and the family's `gateStatus` /
 * `gateOwner`. It only ever appears for `gateOwner === 'research'` — see the comment on it.
 */
function build() {
  const asg = assignments();
  const rows = normalized();
  const scores = screenScores();
  const consumption = require('./consumption');
  const reg = new Set(registered());

  const members = new Map();
  const unassigned = [];
  for (const r of rows) {
    const a = asg.get(r.sourceFile);
    if (!a || !a.family) { unassigned.push({ ...r, proposal: (a || {}).proposal || '' }); continue; }
    if (!members.has(a.family)) members.set(a.family, []);
    members.get(a.family).push(r);
  }

  // ⚠ `members` counts strategies with a NORMALIZED ledger row — the only ones that can be
  // researched. A family page's own `memberCount` counts every assigned strategy, so the two
  // differ, sometimes hugely: 打板短线's page says 25 and only 9 are measured, because 15 have no
  // ledger row at all and two are compile-error / slow-skipped. Reporting the gap is what keeps
  // the queue from silently understating a family and what tells `normalize` where to aim.
  const assignedCount = new Map();
  for (const [, a] of asg) {
    if (!a.family) continue;
    assignedCount.set(a.family, (assignedCount.get(a.family) || 0) + 1);
  }

  const out = [];
  for (const family of reg) {
    const mem = members.get(family) || [];
    // Staleness must span study/enhance/research, or every family reads as untouched the moment
    // the merged stage is introduced — all the history lives under the two old stage names.
    const stale = consumption.staleForResearch(family);
    const everRun = !!consumption.lastConsumption(family);

    // ⚠⚠ A family can be `done` here and still be STUCK at the next stage's gate.
    //
    // Measured 2026-10-17: 8 of 13 families were `blocked` in `integrate-eligible` while this
    // queue read **0 due**. A family researched to exhaustion but never finalised on VAL has no
    // new members and a consumption row, so it reads `done` — yet integration cannot take it, and
    // the only thing that can perform the missing step is this loop. Nothing in the pipeline could
    // notice: the funnel's last stage was waiting on its predecessor, and its predecessor thought
    // it was finished. Four families (七星高照, 五福闹新春, 多因子ML, 趋势技术) sat there silently.
    //
    // So the gate's own verdict reopens them — but ONLY where it names `research` as the owner.
    // `human` (needs JQ_ALLOW_REVAL) and `none` (a measured rejection, e.g. realizability 1) are
    // left alone: a family the loop cannot clear would be dispatched every day to do nothing,
    // which is this repo's recurring failure shape, and an R=1 family would spin forever on a
    // decision already taken. `normalize`-owned blocks belong to the normalize queue.
    let gate = null;
    try { gate = require('./integrate-eligible').assess(family); } catch { gate = null; }
    const gateBlocked = gate && !gate.eligible && gate.owner === 'research';

    const reason = !everRun ? 'never-researched'
      : stale.stale ? 'new-members'
      : gateBlocked ? 'integrate-blocked'
      : 'done';

    out.push({
      family,
      score: scores.has(family) ? scores.get(family) : null,
      memberList: mem.map(m => ({
        sourceFile: m.sourceFile, title: m.title, epoch: m.epoch,
        objective: m.objective, sharpe: m.sharpe, gate: m.gate, valid: m.valid,
      })).sort((a, b) => (b.objective ?? -99) - (a.objective ?? -99)),
      members: mem.length,
      assigned: assignedCount.get(family) || 0,
      unmeasured: Math.max(0, (assignedCount.get(family) || 0) - mem.length),
      validMembers: mem.filter(m => m.valid).length,
      // ⚠ Epoch-aware, like the family pages and wiki-family-build. Reducing over EVERY member
      // regardless of epoch reported 小市值 at 1.3738 while its page said 1.0258 and ETF溢价 at
      // 1.5642 against 0.7767 — numbers measured on a superseded bench, presented beside
      // current ones. `bestObjectiveAnyEpoch` keeps the old view for families that have no valid
      // row at all, so a stale family still shows something rather than a bare dash.
      bestObjective: mem.reduce((a, m) => (m.valid && m.objective != null && (a == null || m.objective > a) ? m.objective : a), null),
      bestObjectiveAnyEpoch: mem.reduce((a, m) => (m.objective != null && (a == null || m.objective > a) ? m.objective : a), null),
      // The CHAMPION's sharpe — champion = best objective among members valid under the active
      // epoch. This is the /run-family order key (user specification, 2026-10-16).
      championSharpe: (() => {
        const valid = mem.filter(m => m.valid && m.objective != null);
        if (!valid.length) return null;
        return valid.reduce((a, b) => (b.objective > a.objective ? b : a)).sharpe;
      })(),
      reason,
      // The note is what the dispatched session reads to know WHY it was woken. For a gate block
      // that is the gate's own sentence, which names the missing step exactly.
      note: gateBlocked ? gate.why
          : stale && stale.reason ? stale.reason : '',
      gateStatus: gate ? gate.status : null,
      gateOwner: gate ? gate.owner : null,
    });
  }

  // ⚠ Ordered by CHAMPION TRAIN SHARPE, highest first (user specification, 2026-10-16).
  //
  // This is not cosmetic. Integration is INCREMENTAL: the first family to clear /run-family in a
  // universe becomes that universe's first promoted candidate and therefore defines what every
  // later arrival has to beat. So the order families enter /run-family decides the order they
  // arrive at integration, and the spec makes that order "highest sharpe first".
  //
  // The screen score — which ranks what is worth FETCHING — drops to a tiebreak. It answers a
  // different question and should not decide which already-held family is worked first.
  const due = out.filter(f => f.reason !== 'done')
    .sort((a, b) => (b.championSharpe ?? -Infinity) - (a.championSharpe ?? -Infinity)
                 || (b.score ?? -1) - (a.score ?? -1)
                 || (b.bestObjective ?? -99) - (a.bestObjective ?? -99));

  return { due, all: out.sort((a, b) => (b.score ?? -1) - (a.score ?? -1)), unassigned, scores };
}

module.exports = { build, assignments, normalized, screenScores, registered };

if (require.main === module) {
  const q = build();
  if (process.argv.includes('--json')) { console.log(JSON.stringify(q, null, 2)); process.exit(0); }

  if (process.argv.includes('--gaps')) {
    console.log(`[fq] ${q.unassigned.length} normalized strategy(ies) with NO family: — they cannot enter the queue`);
    for (const u of q.unassigned.slice(0, 20)) {
      console.log(`   ${path.basename(u.sourceFile).slice(0, 56).padEnd(56)} proposal: ${u.proposal || '(none)'}`);
    }
    const unscored = q.all.filter(f => f.score == null);
    if (unscored.length) {
      console.log(`\n[fq] ${unscored.length} family(ies) with NO screen score: ${unscored.map(f => f.family).join(', ')}`);
    }
    process.exit(0);
  }

  if (process.argv.includes('--members')) {
    for (const f of q.due) {
      console.log(`\n── ${f.family}  score ${f.score ?? '—'}  ${f.members} member(s)  [${f.reason}]`);
      for (const m of f.memberList) {
        console.log(`   e${m.epoch}${m.valid ? ' ' : '*'} ${String(m.objective == null ? 'DQ' : m.objective.toFixed(4)).padStart(8)}  ${m.gate.padEnd(4)}  ${require('path').basename(m.sourceFile).slice(0, 62)}`);
      }
      if (!f.members) console.log('   (no normalized members)');
    }
    console.log('\n  * = measured on a superseded epoch, not valid for the active bench');
    process.exit(0);
  }

  console.log(`[fq] family queue — ${q.due.length} due of ${q.all.length} registered\n`);
  console.log('  score  meas/assigned  bestObj   reason            family');
  for (const f of q.due) {
    console.log(`  ${String(f.score ?? '—').padStart(5)}  ${String(f.members + '/' + f.assigned).padStart(13)}  ` +
                `${String(f.bestObjective == null ? '—' : f.bestObjective.toFixed(4)).padStart(7)}   ` +
                `${f.reason.padEnd(17)} ${f.family}${f.note ? '  (' + f.note + ')' : ''}`);
  }
  const done = q.all.filter(f => f.reason === 'done');
  if (done.length) console.log(`\n  done this epoch: ${done.map(f => f.family).join(', ')}`);
  if (q.unassigned.length) {
    console.log(`\n  ⚠ ${q.unassigned.length} normalized strategy(ies) have no family: and are INVISIBLE to the`);
    console.log('    queue. node utils/family-queue.js --gaps lists them.');
  }
}
