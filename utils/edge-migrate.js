/**
 * edge-migrate.js — bring the 14 existing family pages onto the post-merge schema.
 *
 * Two mechanical edits, and a deliberate refusal to do a third.
 *
 *   1. §2 变体 gains `类型` and `判定` (docs/wiki-schema.md §3.3). Derived from the `来源`
 *      column, which already says which generator produced each row — so this needs no
 *      judgement and no backtests.
 *   2. `edge:` is seeded at `status: proposed` ONLY where it can be DERIVED, i.e. the page
 *      declares a `因子族` concept that §2.3 promotes to an edge name.
 *
 * ## What this refuses to do, and why
 *
 * It does NOT read each page's §1 「为什么有效」 prose and write an edge claim from it. That
 * would be a machine guessing at the one field the whole change exists to make trustworthy, and
 * it is exactly the failure this repo has already paid for: a screening rule that guessed from
 * titles permanently discarded 287 of 549 strategies. A fabricated `claim`/`test` pair would read
 * like evidence, and `status: proposed` would not save it — people quote what is written down.
 *
 * So a family with no derivable edge gets NO `edge:` block, and the gap is REPORTED. Absent means
 * unanswered, not absent-of-edge (§2.3). Answering it is an `understand` idea for the merged loop,
 * which is where a claim with a real falsification test comes from.
 *
 * ⚠ These pages are the ONLY durable copy of every study finding — `study/<family>/findings.tsv`
 * is gitignored and nothing can reconstruct it (there is no findings equivalent of
 * `normalize-ledger-rebuild.js`). 608KB across 14 pages, 207KB of it §6 study-log. So this edits
 * in place, line by line, and never regenerates: the schema is the container, the content is the
 * product, and changing the container must not cost the contents.
 *
 * Usage:
 *   node utils/edge-migrate.js --dry     # report every edit, write nothing
 *   node utils/edge-migrate.js           # apply
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const FAM = path.join(ROOT, 'wiki/families');

/** §2.3: only 因子族 concepts promote to an edge. 结构/机制 are techniques, not sources of return. */
const CONCEPT_TO_EDGE = {
  小市值因子: { name: '规模因子', kind: 'risk-premium' },
  动量与趋势: { name: '动量', kind: 'anomaly' },
  均值回归:   { name: '均值回归', kind: 'anomaly' },
};

/** `来源` -> (类型, 判定). The source column already encodes which generator produced the row. */
function classify(source) {
  const s = String(source || '').replace(/[`*]/g, '').trim();
  if (/^study-/.test(s))      return { kind: 'understand', verdict: 'informative' };
  if (/^enhance-/.test(s))    return { kind: 'improve',    verdict: 'adopted' };
  if (/^normalized-raw/.test(s)) return { kind: 'raw',     verdict: '—' };
  return { kind: '—', verdict: '—' };           // placeholder rows stay placeholders
}

const cells = line => line.replace(/^\||\|$/g, '').split('|');
const isSeparator = line => /^\|[\s:|-]+\|$/.test(line.trim());

/**
 * Rewrite one §2 table. Columns are inserted POSITIONALLY (类型 after 变体, 判定 before 结论)
 * rather than by header name, because three pages label the 4th column `Δannual` instead of
 * `Δobjective` — a pre-existing inconsistency this migration must tolerate, not "fix".
 */
function migrateTable(lines, from, to) {
  const out = [];
  const strays = [], escaped = [];
  let edits = 0;
  for (let i = from; i < to; i++) {
    const line = lines[i];
    const t = line.trim();
    if (!t.startsWith('|')) { out.push(line); continue; }

    const c = cells(line);
    if (c.length < 7) { out.push(line); continue; }      // already migrated, or not this table

    // ⚠ Rows with MORE than 7 cells are not a different schema — they are 7-column rows whose
    // 结论 prose contains an unescaped `|` (e.g. "Δannual|≥10pp"). Measured: 12 such rows across
    // 6 families, at 9 and 11 cells, and in every one the overflow is the TAIL. Those tables
    // already render wrong; that is pre-existing and not what this migration is for.
    //
    // The first six columns are short and structured, so they survive. The guard below CHECKS
    // that rather than assuming it: if c[2] does not parse as a known 来源, the row's shape is
    // something this tool does not understand and it is left completely alone and reported.
    // A half-widened table is worse than an unmigrated one — markdown renders it ragged.
    const overflow = c.length > 7;
    if (overflow && !isSeparator(line) && !/^\s*变体\s*$/.test(c[0])
        && classify(c[2]).kind === '—') {
      out.push(line);
      strays.push({ line: i, cells: c.length, text: c[0].trim().slice(0, 40) });
      continue;
    }

    // Columns 0..5 positionally; everything from 6 on is one 结论 that got split. Re-joined with
    // an ESCAPED pipe so the row renders as its author meant — without that, the 判定 column we
    // are adding would sit in a table whose later rows still spill phantom columns.
    const tail = c.slice(6).join('\\|');
    const widen = (afterFirst, beforeLast) =>
      '|' + [c[0], afterFirst, ...c.slice(1, 6), beforeLast, tail].join('|') + '|';

    if (overflow) escaped.push({ line: i, cells: c.length });

    if (isSeparator(line))              { out.push(widen('---', '---')); edits++; continue; }
    if (/^\s*变体\s*$/.test(c[0]))      { out.push(widen(' 类型 ', ' 判定 ')); edits++; continue; }

    const { kind, verdict } = classify(c[2]);
    out.push(widen(` ${kind} `, ` ${verdict} `));
    edits++;
  }
  return { out, edits, strays, escaped };
}

function sectionRange(lines, startRe, endRe) {
  const from = lines.findIndex(l => startRe.test(l));
  if (from < 0) return null;
  let to = lines.findIndex((l, i) => i > from && endRe.test(l));
  if (to < 0) to = lines.length;
  return { from, to };
}

/** The edge block a page's declared concepts license, or null. */
function derivedEdge(text) {
  const line = (text.match(/^concepts:\s*(.*)$/m) || [])[1] || '';
  for (const [concept, e] of Object.entries(CONCEPT_TO_EDGE)) {
    if (line.includes(concept)) return { ...e, concept };
  }
  return null;
}

function renderEdge(e) {
  return [
    'edge:',
    `  - name: ${e.name}`,
    `    kind: ${e.kind}`,
    `    claim: "<未回答：由 concepts 的 [[${e.concept}]] 推出名字，但「为什么有超额」还没人答>"`,
    `    test: "<未回答：需要一个能证伪上面这句的测量>"`,
    '    status: proposed',
  ].join('\n');
}

function migrateFile(file, { dry }) {
  const p = path.join(FAM, file);
  const text = fs.readFileSync(p, 'utf8');
  const lines = text.split('\n');
  const r = { file, table: 0, edge: null, note: '' };

  // ── §2 table ──
  const sec = sectionRange(lines, /^## 2\./, /^## 3\./);
  if (sec) {
    const { out, edits, strays, escaped } = migrateTable(lines, sec.from, sec.to);
    if (edits) { lines.splice(sec.from, sec.to - sec.from, ...out); r.table = edits; }
    r.strays = strays; r.escaped = escaped.length;
  } else r.note = 'no §2 section';

  // ── edge: ──
  if (/^edge:/m.test(text)) {
    r.edge = 'already-present';
  } else {
    const e = derivedEdge(text);
    if (!e) r.edge = 'NO-DERIVATION';
    else {
      const at = lines.findIndex(l => /^base:/.test(l));
      if (at < 0) r.edge = 'no base: anchor';
      else { lines.splice(at, 0, ...renderEdge(e).split('\n')); r.edge = `seeded ${e.name}`; }
    }
  }

  const next = lines.join('\n');
  if (!dry && next !== text) fs.writeFileSync(p, next);
  r.changed = next !== text;
  return r;
}

function migrate({ dry = false } = {}) {
  return fs.readdirSync(FAM).filter(f => f.endsWith('.md')).map(f => migrateFile(f, { dry }));
}

module.exports = { migrate, classify, derivedEdge, CONCEPT_TO_EDGE };

if (require.main === module) {
  const dry = process.argv.includes('--dry');
  const rows = migrate({ dry });
  console.log(`[edge-migrate] ${dry ? 'would edit' : 'edited'} ${rows.filter(r => r.changed).length} of ${rows.length} family page(s)\n`);
  for (const r of rows) {
    const esc = r.escaped ? `  (${r.escaped} row(s) had an unescaped | in 结论 — escaped)` : '';
    console.log(`  ${r.file.replace(/\.md$/, '').padEnd(16)} §2 rows ${String(r.table).padStart(3)}   edge: ${r.edge}${esc}${r.note ? '  ⚠ ' + r.note : ''}`);
    for (const st of (r.strays || [])) {
      console.log(`      ⚠⚠ SKIPPED line ${st.line + 1} (${st.cells} cells, 来源 unrecognised): ${st.text}`);
    }
  }
  const gaps = rows.filter(r => r.edge === 'NO-DERIVATION');
  if (gaps.length) {
    console.log(`\n[edge-migrate] ${gaps.length} family(ies) have NO derivable edge and were left ALONE:`);
    console.log('   ' + gaps.map(g => g.file.replace(/\.md$/, '')).join(', '));
    console.log('   Absent means UNANSWERED, not "has no edge" (wiki-schema.md §2.3). Writing a claim');
    console.log('   from their §1 prose would be a machine guessing at the one field this change exists');
    console.log('   to make trustworthy — that is an `understand` idea for the loop, not a migration.');
  }
  if (dry) console.log('\n[edge-migrate] (--dry — nothing written)');
}
