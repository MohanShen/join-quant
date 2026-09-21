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
const FAM_DIR = path.join(ROOT, 'wiki/families');
const STRAT_PAGES = path.join(ROOT, 'wiki/strategies');
const LEDGER = path.join(ROOT, 'harness/normalize-train.tsv');

const fm = (t, k) => ((t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm')) || [])[1] || '').trim();

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

/** Normalized rows at a measurement-valid epoch, newest epoch per file. */
function normalized() {
  const harness = require('./harness-config');
  const best = new Map();
  let text;
  try { text = fs.readFileSync(LEDGER, 'utf8'); } catch { return []; }
  for (const line of text.split('\n').slice(1)) {
    if (!line.trim()) continue;
    const c = line.split('\t');
    if (c[3] !== 'normalized') continue;
    const epoch = c[13] || '2';
    const row = {
      sourceFile: c[0], title: c[2], epoch,
      objective: c[11] === 'DQ' ? null : parseFloat(c[11]), gate: c[12],
      valid: harness.measurementValid(epoch),
    };
    const prev = best.get(c[0]);
    if (!prev || Number(epoch) >= Number(prev.epoch)) best.set(c[0], row);
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
 * `reason` is the field the daily pipeline acts on, and it is deliberately three-valued rather
 * than a boolean "due": a family with new members is NOT the same work as a family that has
 * never been researched, and /run-family's early exit depends on telling them apart.
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

  const out = [];
  for (const family of reg) {
    const mem = members.get(family) || [];
    // Staleness must span study/enhance/research, or every family reads as untouched the moment
    // the merged stage is introduced — all the history lives under the two old stage names.
    const stale = consumption.staleForResearch(family);
    const everRun = !!consumption.lastConsumption(family);

    const reason = !everRun ? 'never-researched'
      : stale.stale ? 'new-members'
      : 'done';

    out.push({
      family,
      score: scores.has(family) ? scores.get(family) : null,
      members: mem.length,
      validMembers: mem.filter(m => m.valid).length,
      bestObjective: mem.reduce((a, m) => (m.objective != null && (a == null || m.objective > a) ? m.objective : a), null),
      reason,
      note: stale && stale.reason ? stale.reason : '',
    });
  }

  const due = out.filter(f => f.reason !== 'done')
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || (b.bestObjective ?? -99) - (a.bestObjective ?? -99));

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

  console.log(`[fq] family queue — ${q.due.length} due of ${q.all.length} registered\n`);
  console.log('  score  members  bestObj   reason            family');
  for (const f of q.due) {
    console.log(`  ${String(f.score ?? '—').padStart(5)}  ${String(f.members).padStart(7)}  ` +
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
