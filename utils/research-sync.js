/**
 * research-sync.js — make the family page catch up with findings.tsv.
 *
 * ## The hole this closes
 *
 * `findings.tsv` is GITIGNORED. The family page's §2 and §6 are the durable copy — the same
 * relationship the `normalized:` blocks have with `harness/normalize-*.tsv`, which CLAUDE.md
 * records regressing from ~119 rows to 18.
 *
 * The recorder wrote the ledger first and the page second, so anything that interrupted a round
 * between the two lost the durable copy silently. Measured: a 红利低频 round was killed mid-loop
 * by an API 529 with **4 findings in findings.tsv, 0 rows in §2 and no §6 section at all**. The
 * results existed only in a file git does not track.
 *
 * This is the same fix `normalize-sync.js` applies one layer down, and for the same stated reason:
 * **bookkeeping belongs to the step that owns it, not to one caller.** Run it at the end of every
 * round, and after any interrupted one.
 *
 * Append-only and idempotent: a qId already present in §6 is never rewritten, so a human edit to
 * a conclusion survives. It never touches §1, §3 (generated), §4 or §5.
 *
 * Usage:
 *   node utils/research-sync.js <family> --dry
 *   node utils/research-sync.js <family>
 *   node utils/research-sync.js --all
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const famPath = f => path.join(ROOT, 'wiki/families', `${f}.md`);

const SECTION6 = '## 6. 研究问答 (study-log)';

/** Findings whose qId does not yet appear in §6. */
function missing(family) {
  const rq = require('./research-queue');
  let body;
  try { body = fs.readFileSync(famPath(family), 'utf8'); } catch { return { err: 'no family page' }; }
  const found = rq.findings(family);
  const log = body.includes(SECTION6) ? body.slice(body.indexOf(SECTION6)) : '';
  const absent = found.filter(f => f.qId && !log.includes(`[Q ${f.qId}]`));
  return { body, found, absent, hasSection: body.includes(SECTION6) };
}

/**
 * One §6 entry. `implication` is carried through deliberately — it is the field the next round's
 * generators read to see what a result CLOSED, and a §6 that records only the conclusion would
 * make the page a weaker handoff than the ledger it is backing up.
 */
function renderEntry(f) {
  const flags = String(f.flags || '').trim();
  return [
    `- **[Q ${f.qId}]** ${f.component_or_param || '(component not recorded)'}（type: ${f.type || '?'}）`,
    `  **→** ${f.finding || '(no finding recorded)'}`,
    `  **⇒** ${f.implication || '(no implication recorded — contract violation)'}`,
    `  （Δ ${f.metric_delta || '—'}；confidence ${f.confidence || '?'}${flags ? '；⚠ ' + flags : ''}）` +
      `${f.edgeRef ? ` edge: ${f.edgeRef}` : ''} 溯源 [[study-${f.qId}]]`,
  ].join('\n');
}

function sync(family, { dry = false } = {}) {
  const m = missing(family);
  if (m.err) return { family, ...m, wrote: 0 };
  if (!m.absent.length) return { family, wrote: 0, total: m.found.length, hasSection: m.hasSection };

  let body = m.body;
  const block = m.absent.map(renderEntry).join('\n');

  if (m.hasSection) {
    // Append inside the existing section, before whatever follows it.
    const at = body.indexOf(SECTION6) + SECTION6.length;
    const rest = body.slice(at);
    const nextHeading = rest.search(/\n## \d/);
    const cut = nextHeading < 0 ? body.length : at + nextHeading;
    body = body.slice(0, cut).replace(/\s*$/, '\n') + block + '\n' + body.slice(cut);
  } else {
    // A scaffolded page has no §6 yet. Create it at the end rather than guessing a position —
    // the section order is fixed by wiki-schema and §6 is last.
    body = body.replace(/\s*$/, '\n') + `\n${SECTION6}\n${block}\n`;
  }

  if (!dry) fs.writeFileSync(famPath(family), body);
  return { family, wrote: m.absent.length, total: m.found.length, hasSection: m.hasSection,
           ids: m.absent.map(f => f.qId) };
}

function families() {
  try {
    return fs.readdirSync(path.join(ROOT, 'wiki/families'))
      .filter(f => f.endsWith('.md')).map(f => f.replace(/\.md$/, ''));
  } catch { return []; }
}

module.exports = { sync, missing, renderEntry, families };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const dry = argv.includes('--dry');
  const targets = argv.includes('--all') ? families() : argv.filter(a => !a.startsWith('--'));
  if (!targets.length) {
    console.error('usage: node utils/research-sync.js <family>|--all [--dry]');
    process.exit(1);
  }
  let total = 0;
  for (const f of targets) {
    const r = sync(f, { dry });
    if (r.err) { console.log(`  ${f.padEnd(14)} ⚠ ${r.err}`); continue; }
    if (r.wrote) {
      total += r.wrote;
      console.log(`  ${f.padEnd(14)} ${dry ? 'would add' : 'added'} ${r.wrote} §6 entry(ies)` +
                  `${r.hasSection ? '' : ' (created §6)'}: ${r.ids.join(', ')}`);
    } else if (r.total) {
      console.log(`  ${f.padEnd(14)} up to date (${r.total} finding(s))`);
    }
  }
  console.log(`[research-sync] ${dry ? 'would write' : 'wrote'} ${total} entry(ies)` +
              (dry ? '  (--dry — nothing written)' : ''));
}
