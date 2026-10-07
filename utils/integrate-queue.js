/**
 * integrate-queue.js — what the integration loop should do next, per universe.
 *
 * The type axis is the UNIVERSE alone (`docs/proposals/type-integration-by-edge.md`). Families
 * sharing a universe trade the same market, which is what makes their EDGES candidates to be
 * composed into one strategy — not blended as two books.
 *
 * ## Why composition and not blending
 *
 * A blend allocates capital across finished strategies. Its return cannot exceed the weighted
 * average of its legs; only its risk improves. 七星高照's blend scored sharpe 3.17 from legs of
 * 2.85/1.60 and still lost to its own small-cap leg (0.4814 vs 0.5984). A conjunction CAN be
 * superadditive: 红利低频's two-factor conjunction returned 23.41% against 11.75% for the sum of
 * its legs, at lower risk than either. So this queue proposes pairs of EDGES, not pairs of books.
 *
 * ## Every universe delivers something
 *
 * A universe with no admissible pair is not skipped — it PROMOTES its best family instead
 * (user's rule, 2026-10-07). Promotion ships that family's champion as the universe's deliverable
 * with no integration attempted. A singleton universe, or one whose only edges are refuted or
 * duplicated, still produces an answer rather than silence.
 *
 * ## Admissibility
 *
 * - both edges `measured` — never `proposed` (unevidenced) and never `refuted` (known false);
 * - edges must be DISTINCT.
 *
 * ⚠ Distinctness is checked here only by NAME (equality, or one containing the other, which is
 * what catches 规模因子 vs 规模 — one edge spelled two ways). That is a floor, not the rule: two
 * differently-named edges can still be the same mechanism, and only a reader can tell. Pairs that
 * survive this check are CANDIDATES for the gatekeeper, which must make the semantic call and
 * record its reason. This file never decides that a pair is genuinely distinct — it only removes
 * the ones that are provably not.
 *
 * Usage:
 *   node utils/integrate-queue.js            # what every universe should do next
 *   node utils/integrate-queue.js --next     # the single highest-value action
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const FAM_DIR = () => process.env.JQ_FAMILIES_DIR || path.join(ROOT, 'wiki/families');

const fmField = (t, k) => {
  const m = t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm'));
  return m ? m[1].trim() : '';
};

/** The edge block's name and status — the two fields admissibility turns on. */
function edgeOf(text) {
  const at = text.indexOf('edge:');
  if (at < 0) return { name: null, status: null };
  const blk = text.slice(at, at + 600);
  return {
    name: (blk.match(/name:\s*(\S+)/) || [])[1] || null,
    status: (blk.match(/status:\s*([a-z-]+)/) || [])[1] || null,
  };
}

function families() {
  const dir = FAM_DIR();
  let names = [];
  try { names = fs.readdirSync(dir).filter(f => f.endsWith('.md')); } catch { return []; }
  return names.map(f => {
    const t = fs.readFileSync(path.join(dir, f), 'utf8');
    const e = edgeOf(t);
    return {
      family: f.replace(/\.md$/, ''),
      universe: fmField(t, 'universe') || null,
      edge: e.name,
      edgeStatus: e.status,
      bestObjective: parseFloat(fmField(t, 'bestObjective')),
      members: parseInt(fmField(t, 'memberCount'), 10) || 0,
    };
  });
}

/**
 * Provably the same edge? Name equality, or one name containing the other.
 * ⚠ A floor only — see the header. `规模` ⊂ `规模因子` is the case this exists for.
 */
function sameEdge(a, b) {
  if (!a || !b) return false;
  const x = String(a).trim(), y = String(b).trim();
  return x === y || x.includes(y) || y.includes(x);
}

/** Integration events already recorded against a universe. */
function attempted(universe) {
  try {
    return require('./consumption').events({ stage: 'integrate', kind: 'type', key: universe });
  } catch { return []; }
}

function build() {
  const fams = families().filter(f => f.universe);
  const byU = {};
  for (const f of fams) (byU[f.universe] = byU[f.universe] || []).push(f);

  return Object.entries(byU).map(([universe, group]) => {
    const measured = group.filter(f => f.edgeStatus === 'measured' && f.edge);

    const pairs = [], refused = [];
    for (let i = 0; i < measured.length; i++) {
      for (let j = i + 1; j < measured.length; j++) {
        const a = measured[i], b = measured[j];
        const entry = { a: a.family, b: b.family, edges: [a.edge, b.edge] };
        if (sameEdge(a.edge, b.edge)) refused.push({ ...entry, why: 'same edge, by name' });
        else pairs.push(entry);
      }
    }

    // The deliverable when nothing is composable: the universe's strongest family.
    //
    // ⚠ With a FLOOR. objective = annual - maxdd, so a negative one means the drawdown exceeded
    // the return — 固定篮子's best is 三进兵 at -0.09. "Promote the best family" must not become
    // "ship the least bad loser": a universe whose best family loses money delivers nothing, and
    // saying so is the honest output. The floor is the family stage threshold, not integration's
    // 2.0, because a promotion is not an integration — it ships a champion that already cleared
    // its own loop.
    const ranked = [...group].sort((x, y) =>
      (Number.isFinite(y.bestObjective) ? y.bestObjective : -Infinity) -
      (Number.isFinite(x.bestObjective) ? x.bestObjective : -Infinity));
    const top = ranked.find(f => Number.isFinite(f.bestObjective)) || null;
    const promote = top && top.bestObjective > 0 ? top : null;

    // Does that champion actually have a validation behind it? A promotion ships it as the
    // universe's answer, so an unvalidated one is a caveat the caller must see, not a detail.
    let promoteVal = null;
    if (promote) {
      try {
        const v = require('./val-budget');
        const prior = v.priorValidations(promote.family);
        promoteVal = prior.length
          ? { validated: true, runId: prior[prior.length - 1].runId, outcome: prior[prior.length - 1].outcome }
          : { validated: false };
      } catch { promoteVal = null; }
    }

    const done = attempted(universe);
    const action = pairs.length ? 'compose' : (promote ? 'promote' : 'blocked');

    return {
      universe,
      families: group.length,
      measured: measured.length,
      pairs,
      refused,
      attempted: done.map(e => ({ runId: e.runId, outcome: e.outcome, at: e.at })),
      action,
      promote: promote && { family: promote.family, objective: promote.bestObjective, val: promoteVal },
      why: pairs.length
        ? `${pairs.length} admissible pair(s) from ${measured.length} measured edge(s)`
        : promote
          ? `no admissible pair (${measured.length} measured edge(s), ${refused.length} refused) ` +
            `— promote ${promote.family}` +
            (promoteVal && !promoteVal.validated ? ' ⚠ never validated' : '')
          : top
            ? `nothing to deliver: no admissible pair and the best family (${top.family}) scores ` +
              `${top.bestObjective} — a negative objective is not a deliverable`
            : 'no family in this universe carries a measurable objective',
    };
  }).sort((a, b) => b.pairs.length - a.pairs.length || b.families - a.families);
}

/** The single highest-value next action: the most composable universe, else the best promotion. */
function next() {
  const rows = build();
  return rows.find(r => r.action === 'compose' && r.pairs.length > r.attempted.length)
      || rows.find(r => r.action === 'compose')
      || rows.find(r => r.action === 'promote')
      || null;
}

module.exports = { build, next, sameEdge, families, edgeOf };

if (require.main === module) {
  const rows = build();
  if (process.argv.includes('--next')) {
    const n = next();
    if (!n) { console.log('[integrate] nothing to do'); process.exit(0); }
    console.log(`[integrate] -> ${n.action.toUpperCase()}  ${n.universe}`);
    console.log(`   ${n.why}`);
    if (n.action === 'compose') for (const p of n.pairs) console.log(`   pair: ${p.a} × ${p.b}  [${p.edges.join(' × ')}]`);
    else if (n.promote) console.log(`   promote: ${n.promote.family} (objective ${n.promote.objective})`);
    process.exit(0);
  }
  for (const r of rows) {
    console.log(`\n■ ${r.universe}  ${r.families} famil(y/ies), ${r.measured} measured edge(s) -> ${r.action.toUpperCase()}`);
    console.log(`   ${r.why}`);
    for (const p of r.pairs) console.log(`   pair    ${p.a} × ${p.b}  [${p.edges.join(' × ')}]`);
    for (const p of r.refused) console.log(`   refused ${p.a} × ${p.b}  [${p.edges.join(' × ')}] — ${p.why}`);
    if (r.action === 'promote' && r.promote) console.log(`   promote ${r.promote.family} (objective ${r.promote.objective})` +
      (r.promote.val ? (r.promote.val.validated ? `  VAL ${r.promote.val.runId} -> ${r.promote.val.outcome}` : '  ⚠ never validated') : ''));
    for (const a of r.attempted) console.log(`   done    ${a.runId} -> ${a.outcome}`);
  }
  console.log('\n⚠ A surviving pair is a CANDIDATE, not a verdict: name-distinctness is a floor, and');
  console.log('  whether two differently-named edges are really the same mechanism is the gatekeeper\'s call.');
}
