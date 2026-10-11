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

/**
 * ALL of a family's edge claims, not just the first.
 *
 * ⚠ This read one 600-char window and returned the FIRST name/status, so a family with several
 * edges was represented by whichever happened to be listed first. Measured 2026-10-11: ETF溢价
 * carries 均值回归 + 流动性溢价 and PT多策略 carries 流动性溢价 + 均值回归 — the IDENTICAL set in
 * the opposite order — and the queue reported them as 均值回归 vs 流动性溢价, i.e. as a distinct
 * pair. Under Revision 1, where a shared edge was a veto, that silently weakened the gate; under
 * Revision 2 a shared edge no longer vetoes, so this is now an evidence-quality defect rather
 * than a gating one. Either way the judge must see the real set.
 */
function edgesOf(text) {
  const at = text.indexOf('edge:');
  if (at < 0) return [];
  // Stop at the next top-level frontmatter key so a long evidence block cannot run past the list.
  const rest = text.slice(at);
  const end = rest.search(/\n[a-z][A-Za-z]*:\s/);
  const blk = end > 0 ? rest.slice(0, end) : rest.slice(0, 4000);
  const out = [];
  for (const line of blk.split('\n')) {
    const n = line.match(/^\s+-\s+name:\s*(.*)$/);
    if (n) { out.push({ name: n[1].trim(), status: null, kind: null, claim: null }); continue; }
    const kv = line.match(/^\s+(status|kind|claim|test):\s*(.*)$/);
    if (kv && out.length) out[out.length - 1][kv[1]] = kv[2].trim().replace(/^"(.*)"$/, '$1');
  }
  return out;
}

/** Back-compat: the first edge, as the old callers and tests expect. */
function edgeOf(text) {
  const e = edgesOf(text)[0];
  return { name: e ? e.name : null, status: e ? e.status : null };
}

function families() {
  const dir = FAM_DIR();
  let names = [];
  try { names = fs.readdirSync(dir).filter(f => f.endsWith('.md')); } catch { return []; }
  return names.map(f => {
    const t = fs.readFileSync(path.join(dir, f), 'utf8');
    const all = edgesOf(t);
    const e = all[0] || { name: null, status: null };
    const measuredEdges = all.filter(x => x.status === 'measured');
    return {
      family: f.replace(/\.md$/, ''),
      universe: fmField(t, 'universe') || null,
      edge: e.name,
      edgeStatus: e.status,
      edges: all,
      measuredEdges,
      bestObjective: parseFloat(fmField(t, 'bestObjective')),
      realism: fmField(t, 'realism'),
      members: parseInt(fmField(t, 'memberCount'), 10) || 0,
    };
  });
}


/**
 * Does the family's own `realism:` declare its headline unrealizable?
 *
 * ⚠ A promotion SHIPS a family as the universe's answer, so it must inherit the same discipline
 * integration applies at rule 4 (realizability at the worst leg). Without this, the ETF universe
 * promotes PT多策略 on objective 3.5952 / VAL sharpe 12.82 — a book whose own realism block opens
 * 「⚠⚠ 头条不可实现，且已定量」 and whose edge evidence says 「band 越薄头条越高、越不可成交」. CLAUDE.md
 * records the same figure as "an ETF-discount book that dies under mild friction".
 *
 * ⚠ This is a FLOOR, not the judgement: it reads one phrase out of prose a human wrote. It cannot
 * rank degrees of unrealizability, and a family with no realism recorded passes by default. What
 * it catches is the explicit self-declaration, which is the case that matters. Skipped candidates
 * are reported, never silently dropped.
 */
const UNREALIZABLE = /\u4e0d\u53ef\u5b9e\u73b0/;   // 不可实现 — "not realizable"
const declaredUnrealizable = (realism) => UNREALIZABLE.test(String(realism || ''));

/**
 * Provably the same edge? Name equality, or one name containing the other.
 * ⚠ A floor only — see the header. `规模` ⊂ `规模因子` is the case this exists for.
 */
function sameEdge(a, b) {
  if (!a || !b) return false;
  const x = String(a).trim(), y = String(b).trim();
  return x === y || x.includes(y) || y.includes(x);
}


/**
 * Gatekeeper refusals, append-only and tracked (`data/integrate-refusals.tsv`).
 *
 * ⚠ Without this the queue re-proposes a pair the gatekeeper has already killed, and the next
 * round pays again for a decision already made with evidence. It is the same role
 * `closedDirections` plays in the research loop: a reasoned NO is a result, and results are kept.
 *
 * A refusal is keyed by the unordered pair, so (A,B) and (B,A) are one fact.
 */
const REFUSALS = () => path.join(
  process.env.JQ_DAILY_STATE_DIR || path.join(ROOT, 'data'), 'integrate-refusals.tsv');

const pairKey = (u, a, b) => [u, ...[a, b].sort()].join('\u0000');

function refusals() {
  const out = new Map();
  let text;
  try { text = fs.readFileSync(REFUSALS(), 'utf8'); } catch { return out; }
  for (const line of text.trim().split('\n').slice(1)) {
    const c = line.split('\t');
    if (c.length < 4 || !c[0]) continue;
    out.set(pairKey(c[0], c[1], c[2]), { universe: c[0], a: c[1], b: c[2], why: c[3], at: c[4] || '' });
  }
  return out;
}

function refuse(universe, a, b, why) {
  if (!universe || !a || !b || !why || why.trim().length < 15) {
    throw new Error('refuse(universe, a, b, why): a refusal needs a reason of its own — ' +
                    'the whole point is that the next round can read why, not just that');
  }
  const f = REFUSALS();
  if (!fs.existsSync(f)) fs.writeFileSync(f, 'universe\tfamilyA\tfamilyB\twhy\tat\n');
  fs.appendFileSync(f, [universe, a, b, why.replace(/[\t\n]/g, ' '), new Date().toISOString()].join('\t') + '\n');
  return { universe, a, b, why };
}

/** Integration events already recorded against a universe. */
function attempted(universe) {
  try {
    return require('./consumption').events({ stage: 'integrate', kind: 'type', key: universe });
  } catch { return []; }
}

function build() {
  const fams = families().filter(f => f.universe);
  const known = refusals();
  const byU = {};
  for (const f of fams) (byU[f.universe] = byU[f.universe] || []).push(f);

  return Object.entries(byU).map(([universe, group]) => {
    // A family with no measured edge has no identified return source, so there is nothing
    // trustworthy to take a step from. That is the only eligibility floor.
    const measured = group.filter(f => (f.measuredEdges || []).length > 0);

    const pairs = [], refused = [];
    for (let i = 0; i < measured.length; i++) {
      for (let j = i + 1; j < measured.length; j++) {
        const a = measured[i], b = measured[j];
        const ea = a.measuredEdges.map(e => e.name);
        const eb = b.measuredEdges.map(e => e.name);
        // ⚠ ANNOTATION, NOT A VERDICT (user's decision, 2026-10-11: the universe check is
        // deterministic, the edge judgement is not). A shared edge no longer refuses anything —
        // under Revision 2 it is what makes a merge coherent. And a name is a free-text label,
        // not an identity: 规模 vs 规模因子 are one edge in two spellings, while 动量 in 七星高照
        // (cross-sectional over 7 hand-picked ETFs, its own evidence says NOT portable) and in
        // 趋势技术 (HS300 large caps) are two mechanisms under one word. Only a reader can tell,
        // so the queue reports what it sees and leaves the call to the gatekeeper.
        const shared = ea.filter(x => eb.some(y => sameEdge(x, y)));
        const entry = { a: a.family, b: b.family, edgesA: ea, edgesB: eb, shared,
                        sameSet: shared.length === ea.length && shared.length === eb.length };
        const gk = known.get(pairKey(universe, a.family, b.family));
        if (gk) refused.push({ ...entry, why: gk.why, gatekeeper: true });
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
    const eligible = ranked.filter(f => Number.isFinite(f.bestObjective) && f.bestObjective > 0
                                     && !declaredUnrealizable(f.realism));
    const promote = eligible[0] || null;
    // Everything stronger that was passed over, and why — a promotion that quietly skipped the
    // top family would hide the most important thing about the universe.
    const skipped = ranked
      .filter(f => Number.isFinite(f.bestObjective) && (!promote || f.bestObjective > promote.bestObjective))
      .map(f => ({ family: f.family, objective: f.bestObjective,
                   why: f.bestObjective <= 0 ? 'negative objective'
                      : declaredUnrealizable(f.realism) ? 'its own realism: declares the headline unrealizable'
                      : 'passed over' }));

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
    const action = pairs.length ? 'merge' : (promote ? 'promote' : 'blocked');

    return {
      universe,
      families: group.length,
      measured: measured.length,
      pairs,
      refused,
      attempted: done.map(e => ({ runId: e.runId, outcome: e.outcome, at: e.at })),
      action,
      promote: promote && { family: promote.family, objective: promote.bestObjective, val: promoteVal },
      skipped,
      why: pairs.length
        ? `${pairs.length} mergeable pair(s) from ${measured.length} famil(y/ies) with a measured edge`
        : promote
          ? `no mergeable pair (${measured.length} eligible, ${refused.length} refused by the gatekeeper) ` +
            `— promote ${promote.family}` +
            (promoteVal && !promoteVal.validated ? ' ⚠ never validated' : '')
          : top
            ? `nothing to deliver: no admissible pair, and every family is either negative or ` +
              `declares its own headline unrealizable (best: ${top.family} at ${top.bestObjective})`
            : 'no family in this universe carries a measurable objective',
    };
  }).sort((a, b) => b.pairs.length - a.pairs.length || b.families - a.families);
}

/** The single highest-value next action: the most composable universe, else the best promotion. */
function next() {
  const rows = build();
  return rows.find(r => r.action === 'merge' && r.pairs.length > r.attempted.length)
      || rows.find(r => r.action === 'merge')
      || rows.find(r => r.action === 'promote')
      || null;
}

module.exports = { build, next, sameEdge, families, edgeOf, edgesOf, refusals, refuse, REFUSALS };

if (require.main === module) {
  const argv = process.argv.slice(2);
  if (argv[0] === '--refuse') {
    const i = argv.indexOf('--why');
    const why = i >= 0 ? argv.slice(i + 1).join(' ') : '';
    const [, u, a, b] = argv;
    try { refuse(u, a, b, why); console.log(`[integrate] refused ${a} \u00d7 ${b} in ${u}`); }
    catch (e) { console.error('[integrate] ' + e.message); process.exit(1); }
    process.exit(0);
  }
  const rows = build();
  if (process.argv.includes('--next')) {
    const n = next();
    if (!n) { console.log('[integrate] nothing to do'); process.exit(0); }
    console.log(`[integrate] -> ${n.action.toUpperCase()}  ${n.universe}`);
    console.log(`   ${n.why}`);
    if (n.action === 'merge') for (const p of n.pairs) console.log(`   pair: ${p.a} × ${p.b}  | ${p.a}: ${p.edgesA.join(', ')} | ${p.b}: ${p.edgesB.join(', ')} | shared: ${p.shared.join(', ') || 'none'}`);
    else if (n.promote) console.log(`   promote: ${n.promote.family} (objective ${n.promote.objective})`);
    process.exit(0);
  }
  for (const r of rows) {
    console.log(`\n■ ${r.universe}  ${r.families} famil(y/ies), ${r.measured} with a measured edge -> ${r.action.toUpperCase()}`);
    console.log(`   ${r.why}`);
    for (const p of r.pairs) console.log(`   pair    ${p.a} × ${p.b}`
      + `\n             ${p.a}: ${p.edgesA.join(', ')}`
      + `\n             ${p.b}: ${p.edgesB.join(', ')}`
      + `\n             shared: ${p.shared.length ? p.shared.join(', ') + (p.sameSet ? '  ⚠ IDENTICAL SET' : '') : 'none'}`);
    for (const p of r.refused) console.log(`   refused ${p.a} × ${p.b} — ${p.why}`);
    if (r.action === 'promote' && r.promote) console.log(`   promote ${r.promote.family} (objective ${r.promote.objective})` +
      (r.promote.val ? (r.promote.val.validated ? `  VAL ${r.promote.val.runId} -> ${r.promote.val.outcome}` : '  ⚠ never validated') : ''));
    for (const k of (r.skipped || [])) console.log(`   skipped ${k.family} (objective ${k.objective}) — ${k.why}`);
    for (const a of r.attempted) console.log(`   done    ${a.runId} -> ${a.outcome}`);
  }
  console.log('\n⚠ A surviving pair is a CANDIDATE, not a verdict: name-distinctness is a floor, and');
  console.log('  whether two differently-named edges are really the same mechanism is the gatekeeper\'s call.');
}
