/**
 * integrate-queue.js — what the integration loop should do next, per universe.
 *
 * The type axis is the UNIVERSE alone (`docs/proposals/type-integration-by-edge.md`).
 *
 * ## INCREMENTAL, not all-pairs  (Revision 4 — user specification, 2026-10-16)
 *
 * This used to enumerate every PAIR of families in a universe. That treated a universe as a
 * static set, had no notion of what the universe had already delivered, and so offered the same
 * pairs round after round while a round's own result changed nothing about the next one.
 *
 * Now a universe holds a set of PROMOTED candidates (`utils/promoted.js`), and families arrive
 * ONE AT A TIME after clearing `/run-family` (`utils/integrate-eligible.js`: champion + passing
 * VAL + realizability >= 2). Each arrival meets the promoted set:
 *
 *   1. nothing promoted OVERLAPS its symbols  -> promoted automatically. With an EMPTY set that
 *      needs no judgement at all: it is simply the first, and the queue says `seed`.
 *   2. an overlapping promoted candidate exists and the merge is BETTER -> the merged candidate is
 *      promoted and SUPERSEDES the incumbent; the arrival lives on inside it.
 *   3. an overlapping promoted candidate exists and the merge fails -> the incumbent is unchanged
 *      and the ARRIVAL is rejected, until that family has a new best variant (the rejection is
 *      keyed to the candidateId, so a new champion is automatically a new attempt).
 *
 * ⚠ **Sequence matters, by design.** The first arrival defines what everything after it has to
 * beat, so families enter `/run-family` ordered by their champion's TRAIN sharpe, highest first.
 * That ordering lives in `utils/family-queue.js`; this file consumes its result.
 *
 * ⚠ **Multi-overlap**: an arrival that overlaps SEVERAL promoted candidates merges against the
 * highest-sharpe one only (user's choice). One merge attempt per arrival keeps the cost bounded
 * and the verdict unambiguous; trying each in turn would be a search over incumbents.
 *
 * ## What is deterministic here and what is not
 *
 * Deterministic: which universes exist, who is eligible, the arrival ORDER, the promoted set, and
 * whether a universe needs a seed or an integration. NOT deterministic, and never decided here:
 * **symbol overlap**, which the agent reads off each candidate's selection logic because
 * JoinQuant exposes no holdings. `edgesOf`/`sameEdge` remain as ANNOTATION for that reader — an
 * edge name is free text, so 规模 and 规模因子 are one mechanism in two spellings while 动量 in
 * two families can be two mechanisms under one word.
 *
 * ⚠ A declared `parent:` lineage IS refused here, deterministically: a child is a FORK of its
 * parent and already carries its mechanism, so that is a within-lineage variant choice
 * (`/run-family`), not an integration of two return sources.
 *
 * Usage:
 *   node utils/integrate-queue.js            # every universe: promoted set, arrival queue, action
 *   node utils/integrate-queue.js --next     # the single highest-value action
 *   node utils/integrate-queue.js --refuse <universe> <A> <B> --why "…"
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
      // `parent: [[X]]` on the CHILD — the relation is stored once, never reciprocated.
      parent: (fmField(t, 'parent').match(/\[\[([^\]]+)\]\]/) || [])[1] || null,
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

/**
 * Are these two families the same LINEAGE — one a declared ancestor of the other?
 *
 * ⚠⚠ Why this is a structural refusal and not a judgement call. A family is a lineage, and
 * `parent:` is a declared frontmatter fact, so this sits in the same deterministic class as
 * `universe:` rather than with the edge semantics the gatekeeper owns. Merging a family with its
 * own parent is not integrating two return sources — the child is a FORK of the parent and
 * already contains its mechanism by construction. Picking the better variant within one lineage
 * is `/run-family`'s job; integration exists to combine lineages.
 *
 * Measured on the live queue (2026-10-16): ETF offered `ETF动量 × 五福闹新春` as a mergeable pair,
 * and because the child's measured edge is named 趋势择时 while the parent's is 动量, the pair
 * read as DIFFERENT edge sets — i.e. the queue presented a parent/child fork as the universe's
 * most attractive "combine" candidate. Edge names cannot catch this; only the lineage can.
 *
 * Walks the chain rather than checking one hop, so a grandchild is caught too, and tolerates a
 * cycle in the declarations instead of looping forever.
 */
function sameLineage(a, b, byName) {
  for (const [from, to] of [[a, b], [b, a]]) {
    let cur = from, hops = 0;
    const seen = new Set();
    while (cur && cur.parent && hops++ < 20 && !seen.has(cur.family)) {
      seen.add(cur.family);
      if (cur.parent === to.family) return { related: true, child: from.family, ancestor: to.family };
      cur = byName.get(cur.parent);
    }
  }
  return { related: false };
}

/**
 * One row per universe: what it has promoted, who is queued to arrive, and what to do next.
 */
function build() {
  const promoted = require('./promoted');
  const eligible = require('./integrate-eligible');
  const fams = families().filter(f => f.universe);
  const byName = new Map(fams.map(f => [f.family, f]));
  const known = refusals();

  // Eligibility is the /run-family exit gate; the queue never re-derives it.
  const assessed = new Map(eligible.all().map(a => [a.family, a]));

  const byU = {};
  for (const f of fams) (byU[f.universe] = byU[f.universe] || []).push(f);

  return Object.entries(byU).map(([universe, group]) => {
    const current = promoted.current(universe);

    // Arrivals: eligible families whose CHAMPION is neither already promoted nor already
    // rejected at this exact candidateId. Ordered by champion TRAIN sharpe — the sequence the
    // spec makes load-bearing.
    const promotedIds = new Set(current.map(c => c.candidateId));
    const arrivals = [], notEligible = [], dispositioned = [];
    for (const f of group) {
      const a = assessed.get(f.family);
      if (!a || !a.eligible) { notEligible.push({ family: f.family, status: a ? a.status : 'unknown', why: a ? a.why : '' }); continue; }
      const id = a.champion.sourceFile;
      if (promotedIds.has(id)) { dispositioned.push({ family: f.family, candidateId: id, state: 'already promoted' }); continue; }
      if (promoted.isRejected(universe, id)) {
        dispositioned.push({ family: f.family, candidateId: id,
                             state: 'rejected at this champion — a NEW best variant reopens it' });
        continue;
      }
      arrivals.push({ family: f.family, candidateId: id, sharpe: a.champion.sharpe,
                      objective: a.champion.objective, epoch: a.champion.epoch,
                      realizability: a.realizability, val: a.val,
                      edges: (f.measuredEdges || []).map(e => e.name) });
    }
    arrivals.sort((x, y) => (y.sharpe ?? -Infinity) - (x.sharpe ?? -Infinity));

    const arrival = arrivals[0] || null;

    // Lineage refusals against the promoted set, computed deterministically so a fork of an
    // already-promoted family can never be offered as something to merge with.
    const lineageRefused = [];
    if (arrival) {
      for (const c of current) {
        for (const m of (c.members.length ? c.members : [c.candidateId])) {
          const a = byName.get(arrival.family), b = byName.get(m);
          if (!a || !b) continue;
          const lin = sameLineage(a, b, byName);
          if (lin.related) {
            lineageRefused.push({ promoted: c.candidateId, member: m,
              why: `same lineage — ${lin.child} declares parent: [[${lin.ancestor}]]; a child is a ` +
                   'FORK of its parent, so this is a within-lineage variant choice (/run-family)' });
          }
        }
      }
    }

    // Gatekeeper refusals recorded against (universe, arrival family, promoted member).
    const gkRefused = [];
    if (arrival) {
      for (const c of current) {
        for (const m of (c.members.length ? c.members : [c.candidateId])) {
          const gk = known.get(pairKey(universe, arrival.family, m));
          if (gk) gkRefused.push({ promoted: c.candidateId, member: m, why: gk.why });
        }
      }
    }

    let action, why;
    if (!arrival) {
      action = 'idle';
      why = current.length
        ? `nothing queued — ${current.length} promoted, every eligible family already dispositioned`
        : 'nothing promoted and nothing eligible — the gate is upstream (/run-family)';
    } else if (!current.length) {
      action = 'seed';
      why = `${arrival.family} is the FIRST eligible candidate in this universe — promote it with ` +
            'no judgement and no backtest; it becomes what later arrivals must beat';
    } else {
      action = 'integrate';
      why = `${arrival.family} arrives against ${current.length} promoted candidate(s) — the agent ` +
            'judges symbol overlap, then promotes (no overlap) or merges against the strongest ' +
            'overlapping incumbent';
    }

    return {
      universe,
      families: group.length,
      promoted: current,
      arrival,
      arrivals,
      notEligible,
      dispositioned,
      lineageRefused,
      refused: gkRefused,
      attempted: attempted(universe).map(e => ({ runId: e.runId, outcome: e.outcome, at: e.at })),
      action, why,
    };
  }).sort((a, b) => {
    // Seeds first (free, and they define the bar), then integrations, then idle.
    const rank = r => (r.action === 'seed' ? 0 : r.action === 'integrate' ? 1 : 2);
    return rank(a) - rank(b) || (b.arrival ? b.arrival.sharpe : -Infinity) - (a.arrival ? a.arrival.sharpe : -Infinity);
  });
}

/** The single highest-value next action: a free seed before a backtest-spending integration. */
function next() {
  const rows = build();
  return rows.find(r => r.action === 'seed')
      || rows.find(r => r.action === 'integrate')
      || null;
}

module.exports = { build, next, sameEdge, sameLineage, families, edgeOf, edgesOf,
                   refusals, refuse, REFUSALS };

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
    if (!n) { console.log('[integrate] nothing to do — every universe is idle'); process.exit(0); }
    console.log(`[integrate] -> ${n.action.toUpperCase()}  ${n.universe}`);
    console.log(`   ${n.why}`);
    if (n.arrival) {
      console.log(`   arrival : ${n.arrival.family}  sharpe ${n.arrival.sharpe}  ` +
                  `R=${n.arrival.realizability}  edges: ${n.arrival.edges.join(', ') || 'none'}`);
      console.log(`             ${n.arrival.candidateId}`);
    }
    for (const c of n.promoted) {
      console.log(`   promoted: ${c.kind} ${c.candidateId}  sharpe ${c.sharpe ?? '?'}` +
                  (c.members.length > 1 ? `  <- ${c.members.join(' + ')}` : ''));
    }
    for (const r of n.lineageRefused) console.log(`   ⚠ lineage: ${r.why}`);
    for (const r of n.refused) console.log(`   ⚠ refused earlier vs ${r.member}: ${r.why}`);
    process.exit(0);
  }
  for (const r of rows) {
    console.log(`\n■ ${r.universe}  ${r.families} famil(y/ies) -> ${r.action.toUpperCase()}`);
    console.log(`   ${r.why}`);
    for (const c of r.promoted) {
      console.log(`   promoted   ${c.kind.padEnd(7)} ${c.candidateId}`);
      console.log(`              sharpe ${c.sharpe ?? '?'}  objective ${c.objective ?? '?'}  e${c.epoch}` +
                  (c.members.length > 1 ? `  <- ${c.members.join(' + ')}` : ''));
    }
    if (!r.promoted.length) console.log('   promoted   (none yet)');
    r.arrivals.forEach((a, i) => console.log(
      `   ${i === 0 ? 'ARRIVAL ->' : 'queued   '} ${a.family.padEnd(12)} sharpe ${String(a.sharpe).padStart(6)}  ` +
      `R=${a.realizability}  edges: ${a.edges.join(', ') || 'none'}`));
    for (const d of r.dispositioned) console.log(`   done       ${d.family} — ${d.state}`);
    for (const x of r.lineageRefused) console.log(`   ⚠ lineage  ${x.why}`);
    for (const x of r.refused) console.log(`   ⚠ refused  vs ${x.member} — ${x.why}`);
    for (const x of r.notEligible) console.log(`   ineligible ${x.family.padEnd(12)} [${x.status}] ${x.why}`);
    for (const a of r.attempted) console.log(`   history    ${a.runId} -> ${a.outcome}`);
  }
  console.log('\n⚠ Symbol overlap is the AGENT\'s call — JoinQuant exposes no holdings. The queue decides');
  console.log('  eligibility, arrival order and the promoted set; it never decides that two books overlap.');
}
