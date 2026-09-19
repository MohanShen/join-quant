/**
 * wiki-concept-lint.js — report drift between what a concept page CLAIMS and what the
 * knowledge base actually contains (docs/consolidation-plan.md §3).
 *
 * `strategyCount` is quoted as fact by /query-wiki and by anyone reading the page, and it has
 * drifted badly: 止损模块 claimed 12 against 83 actual, 动量与趋势 27 against 74. The counts
 * went stale because the study and enhance loops write to family pages and are only
 * *instructed* to backfill concepts.
 *
 * This REPORTS and does not silently rewrite. The number also appears in prose on some pages,
 * so a silent fix would leave the page contradicting itself — and a lint that edits is a lint
 * you stop reading. `--fix` updates only the frontmatter field, and says which pages still
 * mention a stale number in their text.
 *
 * Usage:
 *   node utils/wiki-concept-lint.js            # report
 *   node utils/wiki-concept-lint.js --fix      # update frontmatter strategyCount only
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const CONCEPTS = path.join(ROOT, 'wiki/concepts');
const PAGES = path.join(ROOT, 'wiki/strategies');
const TOLERANCE = 0.05;   // plan §3 acceptance: under 5%

function actualCount(concept, pageTexts) {
  return pageTexts.filter(t => t.includes(concept)).length;
}

function lint() {
  const pageTexts = fs.readdirSync(PAGES).filter(f => f.endsWith('.md'))
    .map(f => fs.readFileSync(path.join(PAGES, f), 'utf8'));
  const rows = [];
  for (const f of fs.readdirSync(CONCEPTS).filter(f => f.endsWith('.md'))) {
    const name = f.replace(/\.md$/, '');
    const text = fs.readFileSync(path.join(CONCEPTS, f), 'utf8');
    const claim = parseInt((text.match(/^strategyCount:\s*(\d+)/m) || [])[1] || '0', 10);
    const actual = actualCount(name, pageTexts);
    const drift = claim === 0 ? (actual === 0 ? 0 : 1) : Math.abs(actual - claim) / claim;
    // does the stale number also appear in the prose?
    const inProse = claim > 0 && new RegExp(`(^|[^0-9])${claim}([^0-9]|$)`)
      .test(text.replace(/^strategyCount:.*$/m, ''));
    rows.push({ name, claim, actual, drift, inProse, file: path.join(CONCEPTS, f) });
  }
  return rows.sort((a, b) => b.drift - a.drift);
}

if (require.main === module) {
  const fix = process.argv.includes('--fix');
  const rows = lint();
  const bad = rows.filter(r => r.drift > TOLERANCE);

  console.log(`[concept-lint] ${rows.length} concept page(s), ${bad.length} over the ${TOLERANCE * 100}% tolerance`);
  for (const r of rows) {
    const mark = r.drift > TOLERANCE ? '⚠' : ' ';
    console.log(`  ${mark} ${r.name.padEnd(14)} claims ${String(r.claim).padStart(3)}  actual ${String(r.actual).padStart(3)}` +
                `  drift ${(r.drift * 100).toFixed(0).padStart(4)}%${r.inProse ? '   (number also in prose)' : ''}`);
  }

  if (fix) {
    let n = 0;
    const prose = [];
    for (const r of bad) {
      const t = fs.readFileSync(r.file, 'utf8');
      if (!/^strategyCount:/m.test(t)) continue;
      fs.writeFileSync(r.file, t.replace(/^strategyCount:.*$/m, `strategyCount: ${r.actual}`));
      n++;
      if (r.inProse) prose.push(r.name);
    }
    console.log(`[concept-lint] updated ${n} frontmatter field(s)`);
    if (prose.length) {
      console.log(`[concept-lint] ⚠ these pages ALSO state the old number in their text — fix by hand: ${prose.join(', ')}`);
    }
  } else if (bad.length) {
    console.log('[concept-lint] run with --fix to update the frontmatter field (prose is never touched)');
    process.exitCode = 1;
  }
}

module.exports = { lint, TOLERANCE };
