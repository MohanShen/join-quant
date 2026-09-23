/**
 * family-assign.js — the funnel step between `normalize` and the family queue.
 *
 *     discover -> fetch -> normalize -> [ASSIGN FAMILY] -> family queue -> /run-family
 *
 * A normalized strategy with no `family:` is **invisible**: `wiki-family-build.js` skips pages
 * without one (`if (!fm.family) continue`), so it never joins a family page, never reaches the
 * queue, and never gets researched. Four are sitting there now.
 *
 * ## Why an agent and not the matcher
 *
 * `utils/family-match.js` scores Jaccard overlap of normalized code lines against each family's
 * `base:`. It is deliberately timid — it decides only 31 of 175 hand-labelled pages and abstains
 * on 82% — and on the four currently pending it abstains on all four. Its precision was also
 * tuned on the same 31 calls it decides, so that number is not an independent estimate. It is a
 * good PROPOSER and a bad decider, which is why CLAUDE.md's rule is that `family:` is never
 * auto-assigned.
 *
 * So the decision is a judgement call made by `.claude/agents/family-assign.md`, reading the
 * source and the candidate family pages. This file is the tooling around that judgement: the
 * evidence it must look at, the guards it cannot bypass silently, and the audit trail.
 *
 * ## What a wrong assignment costs
 *
 * It is not a mislabelled row. `family:` drives §2 membership, `memberCount`, `bestObjective`,
 * §3's cross-comparison and the whole type layer — and it fails **silently, in the direction of
 * the biggest families**, because a combination book overlaps every lineage it embeds. 三马 /
 * 七星 / 五福 are the measured trap: the matcher scored 0.98 against TWO bases at once, most
 * confident exactly where it was most wrong. Hence `combination` below, and hence every write
 * lands in an append-only ledger that `--revert` can undo.
 *
 * Usage:
 *   node utils/family-assign.js                       # what needs a decision, with evidence
 *   node utils/family-assign.js --evidence <file.py>  # everything about one candidate
 *   node utils/family-assign.js --assign <file.py> --family <name> --why "..." --confidence high
 *   node utils/family-assign.js --assign ... --new-family      # register an unseen lineage
 *   node utils/family-assign.js --assign ... --combination-ack # override the combination guard
 *   node utils/family-assign.js --revert <file.py>
 *   node utils/family-assign.js --log
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PAGES = path.join(ROOT, 'wiki/strategies');
const FAMS = path.join(ROOT, 'wiki/families');
const LEDGER = path.join(ROOT, 'data/family-assignments.tsv');
const COLUMNS = ['at', 'sourceFile', 'page', 'family', 'confidence', 'decidedBy', 'why', 'topScore', 'runnerUp'];

const fm = (t, k) => ((t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm')) || [])[1] || '').trim();
const clean = v => String(v == null ? '' : v).replace(/[\t\r\n]/g, ' ').trim();

// wiki-schema §2.2 registers one family that has NO page by rule: `其他`, the singleton bucket for
// one-off strategies that formed no lineage ("不建家族页"; wiki-family-build.js skips it). Page
// existence is the right proxy for "registered" everywhere else, but for this entry it turned a
// schema-sanctioned answer into a refusal that could only be passed with --new-family — the flag
// meant for lineages nobody has registered.
const SINGLETON_BUCKET = '其他';

const registered = () => {
  try { return fs.readdirSync(FAMS).filter(f => f.endsWith('.md')).map(f => f.replace(/\.md$/, '')).concat(SINGLETON_BUCKET); }
  catch { return [SINGLETON_BUCKET]; }
};

/** page file -> { sourceFile, family } for every strategy page. */
function pages() {
  const out = [];
  for (const f of fs.readdirSync(PAGES).filter(x => x.endsWith('.md'))) {
    const t = fs.readFileSync(path.join(PAGES, f), 'utf8');
    out.push({ page: f, sourceFile: fm(t, 'sourceFile'), family: fm(t, 'family').replace(/[[\]]/g, '') });
  }
  return out;
}

/** Normalized strategies with no family — the ones the queue cannot see. */
function pending() {
  const fq = require('./family-queue');
  const byFile = new Map(pages().map(p => [p.sourceFile, p]));
  return fq.normalized()
    .filter(r => { const p = byFile.get(r.sourceFile); return !p || !p.family; })
    .map(r => ({ ...r, page: (byFile.get(r.sourceFile) || {}).page || null }));
}

/**
 * Everything the agent must weigh for one candidate. Returned as data rather than prose so the
 * combination guard can key on it instead of on someone's reading of it.
 */
function evidence(sourceFile) {
  const fmatch = require('./family-match');
  const abs = path.join(ROOT, sourceFile);
  let src = '';
  try { src = fs.readFileSync(abs, 'utf8'); } catch { return { err: `cannot read ${sourceFile}` }; }

  // familyBases() returns { bases: Map, skipped: [] }. `skipped` matters right now: a family page
  // that is still a scaffold has the literal `[[<postId8>_…]]` placeholder as its base:, so it
  // contributes NO comparable source. With every page scaffolded the matcher has nothing to score
  // against at all — which is a real state to report, not a crash.
  const { bases, skipped } = fmatch.familyBases();

  // Reuse match() rather than re-scoring here: it owns MIN_SCORE, MIN_MARGIN and the abstain
  // rules, all tuned against the 175 hand-labelled pages. A second scoring path would drift.
  const m = bases.size ? fmatch.match(src, bases) : { family: null, score: 0, margin: 0, ranked: [], reason: 'no comparable base' };
  const ranked = (m.ranked || []).map(r => ({ family: r.family || r[0], score: +(r.score ?? r[1]).toFixed(4) }));

  const MIN = 0.35;
  const clearing = ranked.filter(r => r.score >= MIN);
  return {
    sourceFile,
    title: path.basename(sourceFile),
    comparableBases: bases.size,
    unreadableBases: (skipped || []).length,
    proposal: m.family || null,
    reason: m.reason,
    scores: ranked.slice(0, 6),
    top: ranked[0] || null,
    runnerUp: ranked[1] || null,
    margin: ranked[1] ? +(ranked[0].score - ranked[1].score).toFixed(4) : null,
    // ⚠ The measured trap: a book that EMBEDS other families overlaps all of them. Two bases
    // clearing the threshold is the signature, and it is where the matcher was most confident
    // and most wrong (0.98 against two at once).
    combination: clearing.length >= 2,
    clearing: clearing.map(c => c.family),
    lines: src.split('\n').length,
  };
}

// ── the write path ──────────────────────────────────────────────────────────

function ensureLedger() {
  if (!fs.existsSync(LEDGER)) fs.writeFileSync(LEDGER, COLUMNS.join('\t') + '\n');
}

function history() {
  ensureLedger();
  return fs.readFileSync(LEDGER, 'utf8').split('\n').slice(1).filter(Boolean)
    .map(l => Object.fromEntries(COLUMNS.map((k, i) => [k, l.split('\t')[i] || ''])));
}

/**
 * Write `family:` onto the strategy page.
 *
 * Every refusal here is a rule CLAUDE.md already paid for, so none of them is bypassable by
 * omission — each needs an explicit flag.
 */
function assign(sourceFile, family, opts = {}) {
  const { why = '', confidence = '', decidedBy = 'agent', newFamily = false, combinationAck = false } = opts;
  const p = pages().find(x => x.sourceFile === sourceFile);
  if (!p) return { ok: false, why: `no strategy page has sourceFile ${sourceFile}` };
  if (p.family) return { ok: false, why: `${p.page} already has family: ${p.family} — use --revert first` };
  if (!family) return { ok: false, why: 'a family name is required' };
  if (String(why).trim().length < 15) {
    return { ok: false, why: 'a --why of at least 15 chars is required: a silent assignment cannot be audited, and this one corrupts §3/memberCount/the type layer when wrong' };
  }
  if (!registered().includes(family) && !newFamily) {
    return { ok: false, why: `"${family}" is not a registered family (wiki/families/${family}.md). Pass --new-family to register a genuinely new lineage, per wiki-schema §2.2.` };
  }

  const ev = evidence(sourceFile);
  if (ev.combination && !combinationAck) {
    return { ok: false, combination: true,
      why: `${sourceFile} clears the match threshold against ${ev.clearing.length} bases ` +
           `(${ev.clearing.join(', ')}) — the combination-book signature. 三马/七星/五福 embed other ` +
           `families verbatim and the matcher scored 0.98 against two at once. Decide which lineage ` +
           `it BELONGS to (or register a new combination family) and pass --combination-ack.` };
  }

  const file = path.join(PAGES, p.page);
  const text = fs.readFileSync(file, 'utf8');
  // Insert after sourceFile: so the frontmatter stays in its documented order.
  const next = /^family:/m.test(text)
    ? text.replace(/^family:.*$/m, `family: ${family}`)
    : text.replace(/^(sourceFile:.*)$/m, `$1\nfamily: ${family}`);
  if (next === text) return { ok: false, why: `could not place family: in ${p.page}` };
  fs.writeFileSync(file, next);

  ensureLedger();
  fs.appendFileSync(LEDGER, [
    new Date().toISOString(), sourceFile, p.page, family, confidence, decidedBy, why,
    ev.top ? `${ev.top.family}:${ev.top.score}` : '', ev.runnerUp ? `${ev.runnerUp.family}:${ev.runnerUp.score}` : '',
  ].map(clean).join('\t') + '\n');

  return { ok: true, page: p.page, family, evidence: ev };
}

/** Undo an assignment. A wrong one is silent, so reversing must be cheap. */
function revert(sourceFile) {
  const p = pages().find(x => x.sourceFile === sourceFile);
  if (!p) return { ok: false, why: `no page for ${sourceFile}` };
  if (!p.family) return { ok: false, why: `${p.page} has no family: to revert` };
  const file = path.join(PAGES, p.page);
  const text = fs.readFileSync(file, 'utf8');
  fs.writeFileSync(file, text.replace(/^family:.*\n/m, ''));
  ensureLedger();
  fs.appendFileSync(LEDGER, [new Date().toISOString(), sourceFile, p.page, `REVERTED(was ${p.family})`,
    '', 'revert', 'reverted', '', ''].map(clean).join('\t') + '\n');
  return { ok: true, page: p.page, was: p.family };
}

module.exports = { pending, evidence, assign, revert, history, registered, pages };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const arg = n => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : null; };

  if (argv.includes('--log')) {
    const h = history();
    console.log(`[assign] ${h.length} decision(s)`);
    for (const r of h) console.log(`  ${r.at.slice(0, 10)}  ${r.family.padEnd(14)} ${r.confidence.padEnd(6)} ${r.sourceFile.slice(0, 48)}`);
    process.exit(0);
  }

  if (argv.includes('--evidence')) {
    const e = evidence(arg('--evidence'));
    console.log(JSON.stringify(e, null, 2));
    process.exit(e.err ? 1 : 0);
  }

  if (argv.includes('--assign')) {
    const r = assign(arg('--assign'), arg('--family'), {
      why: arg('--why') || '', confidence: arg('--confidence') || '',
      decidedBy: arg('--by') || 'agent',
      newFamily: argv.includes('--new-family'),
      combinationAck: argv.includes('--combination-ack'),
    });
    console.log(r.ok ? `[assign] ${r.page} -> family: ${r.family}` : `[assign] REFUSED: ${r.why}`);
    process.exit(r.ok ? 0 : 1);
  }

  if (argv.includes('--revert')) {
    const r = revert(arg('--revert'));
    console.log(r.ok ? `[assign] ${r.page}: removed family: ${r.was}` : `[assign] ${r.why}`);
    process.exit(r.ok ? 0 : 1);
  }

  const q = pending();
  console.log(`[assign] ${q.length} normalized strategy(ies) have no family: and are INVISIBLE to the queue\n`);
  for (const s of q) {
    const e = evidence(s.sourceFile);
    const top = e.top ? `${e.top.family} ${e.top.score}` : '— (no comparable base)';
    const flag = e.combination ? `  ⚠ COMBINATION (${e.clearing.join(', ')})` : '';
    console.log(`  ${path.basename(s.sourceFile).slice(0, 54)}`);
    console.log(`     obj ${s.objective == null ? 'DQ' : s.objective.toFixed(4)}  best match: ${top}` +
                `  margin ${e.margin ?? '—'}${flag}`);
  }
  if (q.length) {
    const e0 = evidence(q[0].sourceFile);
    if (!e0.comparableBases) {
      console.log(`\n  ⚠ ZERO comparable bases: all ${e0.unreadableBases} family page(s) are still`);
      console.log('    scaffolds, so code matching has nothing to score against. The agent must');
      console.log('    decide from the SOURCE and the family pages themselves, not from a score.');
    }
    console.log('\n  The matcher PROPOSES; it does not decide (31 of 175 decided, 82% abstain).');
    console.log('  Dispatch .claude/agents/family-assign.md, or assign by hand with --assign.');
  }
}
