/**
 * family-match.js — propose which FAMILY a strategy belongs to, from its source code.
 *
 * The gap this fills. `kb-stub.js` creates a page for every newly-measured strategy but never
 * writes a `family:` field, and `wiki-family-build.js` skips any page without one
 * (`if (!fm.family) continue`). So a newly fetched member of an existing family was
 * structurally invisible to that family's page: §3, memberCount and bestVariant never saw it.
 * The only reason the library looks assigned today is that people did it by hand afterwards.
 *
 * Why code and not labels. A family is a LINEAGE — strategies sharing a base code body
 * (CLAUDE.md). Concepts and factors cut ACROSS lineages by design, so matching on them would
 * merge families that merely trade the same idea. Comparing source against each family's
 * declared `base:` is the definition, applied directly.
 *
 * Method: Jaccard overlap of normalized code lines (comments, blank lines, docstrings and
 * indentation removed). Clones of a base share large verbatim blocks, which this measures
 * directly and cheaply. It is deliberately NOT a semantic model — a confident wrong assignment
 * is worse than none, because it corrupts §3, memberCount and the whole type layer above it.
 *
 * ⚠ Abstains rather than guesses. A proposal is returned only when the best match clears
 * `MIN_SCORE` *and* beats the runner-up by `MIN_MARGIN`. Everything else is reported
 * `unassigned` for a human or `/ingest-strategy` to decide. Validate before trusting a change:
 *
 *   node utils/family-match.js --validate    # score against the hand-labelled pages
 *   node utils/family-match.js <file.py>     # rank families for one strategy
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const FAM_DIR = path.join(ROOT, 'wiki/families');
const PAGES_DIR = path.join(ROOT, 'wiki/strategies');

/** Best match must reach this Jaccard score. Calibrated by --validate, not guessed. */
const MIN_SCORE = 0.35;
/** …and beat the runner-up by this much, so two near-identical families abstain instead. */
const MIN_MARGIN = 0.05;

const fmField = (t, k) => (t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm')) || [])[1] || '';

/**
 * Reduce source to the lines that carry logic. Comments are dropped here (unlike
 * wiki-type-build, which keeps them because universe names live in Chinese comments) — a
 * lineage is shared CODE, and comment text is the part a re-poster most often rewrites.
 */
function normalize(src) {
  return new Set(
    src.split('\n')
      .map(l => l.replace(/#.*$/, '').trim())
      .filter(l => l.length > 3 && !/^(import|from)\s/.test(l))
  );
}

function jaccard(a, b) {
  if (!a.size || !b.size) return 0;
  let inter = 0;
  const [small, large] = a.size < b.size ? [a, b] : [b, a];
  for (const l of small) if (large.has(l)) inter++;
  return inter / (a.size + b.size - inter);
}

/** sourceFile for a strategy page name. */
function pageSource(pageName) {
  const p = path.join(PAGES_DIR, `${pageName}.md`);
  if (!fs.existsSync(p)) return null;
  return fmField(fs.readFileSync(p, 'utf8'), 'sourceFile').trim() || null;
}

/** family -> normalized base source. A family whose base cannot be read is skipped, loudly. */
function familyBases() {
  const out = new Map();
  const skipped = [];
  for (const f of fs.readdirSync(FAM_DIR).filter(x => x.endsWith('.md'))) {
    const name = f.replace(/\.md$/, '');
    const text = fs.readFileSync(path.join(FAM_DIR, f), 'utf8');
    const m = fmField(text, 'base').match(/\[\[([^\]]+)\]\]/);
    if (!m) { skipped.push(name); continue; }
    const src = pageSource(m[1]);
    const abs = src && path.join(ROOT, src);
    if (!abs || !fs.existsSync(abs)) { skipped.push(name); continue; }
    out.set(name, { lines: normalize(fs.readFileSync(abs, 'utf8')), sourceFile: src });
  }
  return { bases: out, skipped };
}

/**
 * Rank families for one strategy source.
 * @returns {{family:string|null, score:number, margin:number, ranked:Array, reason:string}}
 */
function match(src, bases) {
  const mine = normalize(src);
  const ranked = [...bases.entries()]
    .map(([name, b]) => ({ family: name, score: +jaccard(mine, b.lines).toFixed(4) }))
    .sort((a, b) => b.score - a.score);

  const best = ranked[0], second = ranked[1];
  const margin = best && second ? +(best.score - second.score).toFixed(4) : (best ? best.score : 0);
  if (!best || best.score < MIN_SCORE) {
    return { family: null, score: best ? best.score : 0, margin, ranked, reason: 'below MIN_SCORE' };
  }
  // A COMBINATION book contains several families' code verbatim (三马 / 七星 / 五福 all do), so
  // it scores high against several bases at once. Code overlap cannot say which lineage such a
  // strategy DESCENDS from — that is a provenance judgement — and this is exactly where the
  // matcher was most confident and most wrong in validation (0.98 against two bases at once).
  const strong = ranked.filter(r => r.score >= MIN_SCORE);
  if (strong.length > 1) {
    return { family: null, score: best.score, margin, ranked,
             reason: `combination: ${strong.length} bases above ${MIN_SCORE} ` +
                     `(${strong.slice(0, 3).map(s => `${s.family} ${s.score}`).join(', ')})` };
  }
  if (margin < MIN_MARGIN) {
    return { family: null, score: best.score, margin, ranked,
             reason: `ambiguous: ${best.family} ${best.score} vs ${second.family} ${second.score}` };
  }
  return { family: best.family, score: best.score, margin, ranked, reason: 'ok' };
}

/** Score the matcher against the hand-assigned `family:` fields already in the wiki. */
function validate() {
  const { bases } = familyBases();
  const labelled = [];
  for (const f of fs.readdirSync(PAGES_DIR).filter(x => x.endsWith('.md'))) {
    const text = fs.readFileSync(path.join(PAGES_DIR, f), 'utf8');
    const fam = fmField(text, 'family').trim();
    const src = fmField(text, 'sourceFile').trim();
    if (!fam || fam === '其他' || !src) continue;
    const abs = path.join(ROOT, src);
    if (!fs.existsSync(abs)) continue;
    labelled.push({ page: f, family: fam, src: abs });
  }

  let correct = 0, wrong = 0, abstained = 0;
  const wrongs = [], abstains = {};
  for (const l of labelled) {
    // A family's own base is in the reference set; exclude the page itself from being its
    // own evidence would be ideal, but the base IS the definition here, so a base scoring 1.0
    // against itself is the correct answer, not leakage.
    const r = match(fs.readFileSync(l.src, 'utf8'), bases);
    if (r.family == null) { abstained++; abstains[l.family] = (abstains[l.family] || 0) + 1; }
    else if (r.family === l.family) correct++;
    else { wrong++; wrongs.push({ ...l, got: r.family, score: r.score, margin: r.margin }); }
  }
  return { total: labelled.length, correct, wrong, abstained, wrongs, abstains };
}

if (require.main === module) {
  const argv = process.argv.slice(2);
  const { bases, skipped } = familyBases();

  if (argv.includes('--validate')) {
    const v = validate();
    const decided = v.correct + v.wrong;
    console.log(`[family-match] ${bases.size} family base(s) readable` +
                (skipped.length ? `, ${skipped.length} skipped (${skipped.join(', ')})` : ''));
    console.log(`[family-match] labelled pages: ${v.total}`);
    console.log(`  decided   : ${decided}  (correct ${v.correct}, wrong ${v.wrong})`);
    console.log(`  precision : ${decided ? (100 * v.correct / decided).toFixed(1) : '—'}%  ` +
                `(of the ones it was willing to call)`);
    console.log(`  abstained : ${v.abstained}  (${(100 * v.abstained / v.total).toFixed(1)}% — left for a human)`);
    if (v.wrongs.length) {
      console.log('  ⚠ wrong calls — each one would corrupt a family page:');
      for (const w of v.wrongs.slice(0, 10)) {
        console.log(`     ${w.family} -> ${w.got}  (score ${w.score}, margin ${w.margin})  ${w.page.slice(0, 44)}`);
      }
    }
    const top = Object.entries(v.abstains).sort((a, b) => b[1] - a[1]).slice(0, 6);
    if (top.length) console.log('  abstentions by true family: ' + top.map(([k, n]) => `${k}=${n}`).join('  '));
    process.exit(0);
  }

  if (argv.includes('--pending')) {
    // Every page that wiki-family-build currently ignores, with what the matcher would say.
    const rows = [];
    for (const f of fs.readdirSync(PAGES_DIR).filter(x => x.endsWith('.md'))) {
      const text = fs.readFileSync(path.join(PAGES_DIR, f), 'utf8');
      if (fmField(text, 'family').trim()) continue;
      const src = fmField(text, 'sourceFile').trim();
      const abs = src && path.join(ROOT, src);
      if (!abs || !fs.existsSync(abs)) { rows.push({ page: f, proposal: null, reason: 'source missing' }); continue; }
      const r = match(fs.readFileSync(abs, 'utf8'), bases);
      rows.push({ page: f, proposal: r.family, score: r.score, reason: r.reason });
    }
    const withProp = rows.filter(r => r.proposal);
    console.log(`[family-match] ${rows.length} page(s) with no family: — invisible to wiki-family-build`);
    console.log(`[family-match] ${withProp.length} have a confident proposal, ${rows.length - withProp.length} need a human\n`);
    for (const r of withProp) console.log(`  PROPOSE ${String(r.score).padStart(7)}  ${r.proposal.padEnd(12)} ${r.page.slice(0, 50)}`);
    for (const r of rows.filter(x => !x.proposal)) console.log(`  --      ${''.padStart(7)}  ${'(none)'.padEnd(12)} ${r.page.slice(0, 50)}  [${r.reason}]`);
    console.log('\n  Promote by setting `family: <name>` in the page, then run ' +
                '`node utils/wiki-family-build.js`. Measured precision on decided calls is 87.1% ' +
                '(node utils/family-match.js --validate), so CONFIRM before promoting.');
    process.exit(0);
  }

  const file = argv[0];
  if (!file) { console.error('usage: node utils/family-match.js <strategy.py> | --validate | --pending'); process.exit(2); }
  const r = match(fs.readFileSync(file, 'utf8'), bases);
  console.log(`[family-match] ${path.basename(file)}`);
  console.log(`  proposal: ${r.family || '(none)'}  score=${r.score} margin=${r.margin}  [${r.reason}]`);
  for (const x of r.ranked.slice(0, 5)) console.log(`    ${String(x.score).padStart(7)}  ${x.family}`);
}

module.exports = { match, familyBases, normalize, jaccard, validate, MIN_SCORE, MIN_MARGIN };
