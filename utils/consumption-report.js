/**
 * consumption-report.js — "what has nothing touched yet", for each stage.
 *
 * This is the input side of the pipeline (docs/consolidation-plan.md §2.2). Before it, the
 * loops took a family a human picked; there was no way to ask which of the measured strategies
 * had ever been examined. Every answer here is derived from durable artefacts — the normalize
 * ledger, family frontmatter, data/consumption.tsv — and involves no judgement, so it can be
 * read by an agent at the top of a run.
 *
 * Usage:
 *   node utils/consumption-report.js            # full report
 *   node utils/consumption-report.js --next     # one line per stage: the next candidate
 */

const fs = require('fs');
const path = require('path');
const c = require('./consumption');

const ROOT = path.resolve(__dirname, '..');
const FAM_DIR = path.join(ROOT, 'wiki/families');
const PAGES_DIR = path.join(ROOT, 'wiki/strategies');

const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };
const fm = (text, key) => (text.match(new RegExp(`^${key}:\\s*(.*)$`, 'm')) || [])[1] || '';

/** Families with their base, best objective and member count. */
function families() {
  if (!fs.existsSync(FAM_DIR)) return [];
  return fs.readdirSync(FAM_DIR).filter(f => f.endsWith('.md')).map(f => {
    const t = fs.readFileSync(path.join(FAM_DIR, f), 'utf8');
    return {
      name: f.replace(/\.md$/, ''),
      base: fm(t, 'base').trim(),
      bestVariant: fm(t, 'bestVariant').trim(),
      bestObjective: parseFloat(fm(t, 'bestObjective')) || null,
      members: parseInt(fm(t, 'memberCount'), 10) || 0,
      status: fm(t, 'status').trim(),
    };
  });
}

/** Measured strategies, and whether each is assigned to a family page. */
function measured() {
  const rows = [];
  for (const line of fs.readFileSync(path.join(ROOT, 'harness/normalize-train.tsv'), 'utf8').split('\n').slice(1)) {
    const col = line.split('\t');
    if (col[0] && col[3] === 'normalized') rows.push({ file: col[0], objective: col[11], gate: col[12] });
  }
  const famOf = {};
  if (fs.existsSync(PAGES_DIR)) {
    for (const p of fs.readdirSync(PAGES_DIR).filter(f => f.endsWith('.md'))) {
      const t = fs.readFileSync(path.join(PAGES_DIR, p), 'utf8');
      const src = fm(t, 'sourceFile').trim();
      if (src) famOf[src] = fm(t, 'family').trim();
    }
  }
  return rows.map(r => ({ ...r, family: famOf[r.file] || null }));
}

function report() {
  const fams = families();
  const meas = measured();
  const studied = c.consumed('study', 'family');
  const enhanced = c.consumed('enhance', 'family');
  const integrated = c.consumed('integrate', 'type');

  const unassigned = meas.filter(m => !m.family);

  // ⚠ "Has this family EVER been studied" is the wrong question, and was the reason a family
  // that gained members after its study never came back: `consumed()` is a binary set, so once
  // all 14 families were done the study queue read empty BY CONSTRUCTION no matter how many
  // new members arrived. The right question is whether the family has changed since the last
  // run, which `staleFor` answers from the membership hash stamped on each event.
  const withStale = stage => fams
    .map(f => ({ ...f, ...c.staleFor(stage, f.name) }))
    .filter(f => f.stale);

  const noStudy = withStale('study');
  const noEnhance = withStale('enhance').filter(f => f.bestObjective != null);

  // types come from wiki/types/ once §3 of the plan is built; absent until then
  const typeDir = path.join(ROOT, 'wiki/types');
  const types = fs.existsSync(typeDir)
    ? fs.readdirSync(typeDir).filter(f => f.endsWith('.md')).map(f => f.replace(/\.md$/, ''))
    : [];
  const noIntegrate = types.filter(t => !integrated.has(t));

  return { fams, meas, unassigned, noStudy, noEnhance, types, noIntegrate };
}

if (require.main === module) {
  const nextOnly = process.argv.includes('--next');
  const r = report();

  if (nextOnly) {
    console.log(`ingest   : ${r.unassigned.length ? r.unassigned[0].file : '—'}  (${r.unassigned.length} unassigned)`);
    const why = f => (f ? `  [${f.reason}]` : '');
    console.log(`study    : ${r.noStudy.length ? r.noStudy[0].name : '—'}  (${r.noStudy.length} families never studied or changed since)${why(r.noStudy[0])}`);
    console.log(`enhance  : ${r.noEnhance.length ? r.noEnhance[0].name : '—'}  (${r.noEnhance.length} families with a best variant, never enhanced or changed since)${why(r.noEnhance[0])}`);
    console.log(`integrate: ${r.noIntegrate.length ? r.noIntegrate[0] : '—'}  (${r.types.length} type page(s) exist)`);
    process.exit(0);
  }

  console.log('=== consumption report ===');
  console.log(`  measured strategies      : ${r.meas.length}`);
  console.log(`    assigned to a family   : ${r.meas.length - r.unassigned.length}`);
  console.log(`    UNASSIGNED             : ${r.unassigned.length}`);
  r.unassigned.slice(0, 6).forEach(m => console.log(`       ${m.file.replace('strategies/', '').slice(0, 56)}`));

  console.log(`\n  families                 : ${r.fams.length}`);
  console.log(`    never studied          : ${r.noStudy.length}${r.noStudy.length ? ' -> ' + r.noStudy.map(f => f.name).join(', ') : ''}`);
  console.log(`    have a best variant but never enhanced : ${r.noEnhance.length}`);
  r.noEnhance.slice(0, 8).forEach(f => console.log(`       ${f.name.padEnd(12)} objective=${f.bestObjective} members=${f.members}`));

  console.log(`\n  types                    : ${r.types.length}${r.types.length ? '' : '  (not built yet — plan §1.3)'}`);
  if (r.types.length) console.log(`    never integrated       : ${r.noIntegrate.length}`);

  const stages = {};
  for (const e of c.events()) stages[e.stage] = (stages[e.stage] || 0) + 1;
  console.log(`\n  recorded events          : ${JSON.stringify(stages)}`);
}

module.exports = { report, families, measured };
