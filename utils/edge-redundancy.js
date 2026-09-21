/**
 * edge-redundancy.js — which families are the same bet.
 *
 * `type-integrate-check.js` already refuses a blend that does not beat its best MEMBER, because
 * blending raises Sharpe mechanically whenever correlation < 1. This is the rule one level up:
 * **two families sharing a measured edge are redundant no matter what their return correlation
 * says.** Correlation is a weak proxy — two size books with different code decorrelate on noise
 * and look like diversification. A shared source of return is the strong proxy.
 *
 * The measurement that motivated it: under epoch 6, `component-scan` reports **every candidate in
 * every type with negative uplift** — nothing improves any type leader — while `CLAUDE.md`
 * separately records that 57% of gate-passes are 小市值 variants and 4 of 6 types are exhausted.
 * Those are the same fact, and the edge pass names it: 5 of 14 families are supplied by 规模因子,
 * three of them under names that say nothing about size (ETF动量, 多因子ML, 七星高照 all turn out
 * to be "some leg + a small-cap leg", where the small-cap leg is the only one supplying return).
 *
 * ⚠ Only `status: measured` counts. A `proposed` claim carries no authority (wiki-schema §2.3) —
 * treating it as redundancy evidence would let a guess retire a family.
 *
 * `none-found` families are FLAGGED, never excluded (human decision, 2026-09-21): a family nobody
 * can name an edge for is a fitting artifact until shown otherwise, and that is a reason to look
 * harder, not to stop looking.
 *
 * Usage:
 *   node utils/edge-redundancy.js            # the redundancy map
 *   node utils/edge-redundancy.js --gaps     # only families with no edge / none-found / refuted
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const FAM = path.join(ROOT, 'wiki/families');

/** Parse the `edge:` block. Tolerant: a malformed entry is reported, never silently dropped. */
function parseEdges(body) {
  const block = (body.match(/^edge:\n((?:[ ]+.*\n)+)/m) || [])[1];
  if (!block) return [];
  const out = [];
  let cur = null;
  for (const line of block.split('\n')) {
    const m = line.match(/^\s+-\s+name:\s*(.*)$/);
    if (m) { if (cur) out.push(cur); cur = { name: m[1].trim() }; continue; }
    if (!cur) continue;
    const kv = line.match(/^\s+(\w+):\s*(.*)$/);
    if (kv) cur[kv[1]] = kv[2].trim().replace(/^"(.*)"$/, '$1');
  }
  if (cur) out.push(cur);
  return out;
}

function families() {
  return fs.readdirSync(FAM).filter(f => f.endsWith('.md')).map(f => {
    const body = fs.readFileSync(path.join(FAM, f), 'utf8');
    return { family: f.replace(/\.md$/, ''), edges: parseEdges(body) };
  });
}

function report() {
  const all = families();
  const byEdge = new Map();
  const noEdge = [], noneFound = [], refuted = [], proposed = [];

  for (const f of all) {
    if (!f.edges.length) { noEdge.push(f.family); continue; }
    for (const e of f.edges) {
      if (e.kind === 'none-found') { noneFound.push({ family: f.family, claim: e.claim }); continue; }
      if (e.status === 'refuted') { refuted.push({ family: f.family, name: e.name }); continue; }
      if (e.status !== 'measured') { proposed.push({ family: f.family, name: e.name }); continue; }
      if (!byEdge.has(e.name)) byEdge.set(e.name, []);
      byEdge.get(e.name).push({ family: f.family, kind: e.kind });
    }
  }
  const clusters = [...byEdge.entries()]
    .map(([name, fams]) => ({ name, kind: (fams[0] || {}).kind, families: fams.map(x => x.family) }))
    .sort((a, b) => b.families.length - a.families.length);
  return { total: all.length, clusters, noEdge, noneFound, refuted, proposed };
}

/** Are two families the same bet? Used as integrate rule 5. */
function redundant(a, b) {
  const map = new Map(families().map(f => [f.family, f.edges]));
  const measured = f => new Set((map.get(f) || [])
    .filter(e => e.status === 'measured' && e.kind !== 'none-found').map(e => e.name));
  const ea = measured(a), eb = measured(b);
  const shared = [...ea].filter(x => eb.has(x));
  return { redundant: shared.length > 0, shared, a: [...ea], b: [...eb] };
}

module.exports = { report, redundant, parseEdges, families };

if (require.main === module) {
  const r = report();
  const gapsOnly = process.argv.includes('--gaps');

  if (!gapsOnly) {
    console.log(`[edge] ${r.total} families, ${r.clusters.length} distinct MEASURED edge(s)\n`);
    for (const c of r.clusters) {
      const flag = c.families.length > 1 ? '  ⚠ INTEGRATION-REDUNDANT' : '';
      console.log(`  ${c.name.padEnd(12)} ${String(c.families.length).padStart(2)} family(ies)  [${c.kind}]${flag}`);
      console.log(`     ${c.families.join(', ')}`);
    }
    if (r.proposed.length) {
      console.log(`\n[edge] proposed, NOT yet authoritative (${r.proposed.length}):`);
      for (const p of r.proposed) console.log(`   ${p.family} -> ${p.name}`);
    }
  }

  if (r.refuted.length) {
    console.log(`\n[edge] REFUTED claims (${r.refuted.length}) — the family's stated mechanism was tested and failed:`);
    for (const x of r.refuted) console.log(`   ${x.family} -> ${x.name}`);
  }
  if (r.noneFound.length) {
    console.log(`\n[edge] none-found (${r.noneFound.length}) — flagged, NOT deprecated:`);
    for (const x of r.noneFound) console.log(`   ${x.family}: ${String(x.claim).slice(0, 96)}…`);
  }
  if (r.noEdge.length) {
    console.log(`\n[edge] NO edge block at all (${r.noEdge.length}) — unanswered, not "has no edge":`);
    console.log('   ' + r.noEdge.join(', '));
  }

  const worst = r.clusters[0];
  if (worst && worst.families.length > 1) {
    console.log(`\n[edge] Largest cluster: ${worst.families.length} of ${r.total} families are supplied by ${worst.name}.`);
    console.log('       Integration between any two of them adds a leg, not a bet. This is what');
    console.log("       component-scan measures as 'every candidate has negative uplift'.");
  }
}
