/**
 * The migrated family pages.
 *
 * These pages are the ONLY durable copy of every study finding — `study/<family>/findings.tsv` is
 * gitignored and nothing can reconstruct it (there is no findings equivalent of
 * `normalize-ledger-rebuild.js`). 608KB across 14 pages, 207KB of it §6 study-log. So the schema
 * migration edits in place and never regenerates, and these assertions are what stop a later
 * "just rebuild the pages" from looking cheap.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const DIR = path.join(__dirname, '../wiki/families');
const files = fs.readdirSync(DIR).filter(f => f.endsWith('.md'));

/** Split a markdown row on its real separators. An escaped `\|` is content, not a column break. */
const rowCells = line => line.replace(/^\||\|$/g, '').split(/(?<!\\)\|/);

/** Every `|`-row inside §2 of one page. */
function section2Rows(body) {
  const rows = [];
  let inSec = false;
  for (const line of body.split('\n')) {
    if (/^## 2\./.test(line)) { inSec = true; continue; }
    if (/^## 3\./.test(line)) inSec = false;
    if (inSec && line.trim().startsWith('|')) rows.push(line);
  }
  return rows;
}

test('family pages carry the post-merge §2 schema', async (t) => {
  await t.test('every §2 table is rectangular at 9 columns', () => {
    // A half-widened table renders ragged, which is worse than an unmigrated one. Before the
    // migration, 12 rows across 6 families sat at 9 and 11 cells because their 结论 prose held an
    // unescaped `|` ("Δannual|≥10pp") — those tables were already rendering wrong.
    for (const f of files) {
      const counts = section2Rows(fs.readFileSync(path.join(DIR, f), 'utf8')).map(l => rowCells(l).length);
      if (!counts.length) continue;
      assert.strictEqual(new Set(counts).size, 1,
        `${f}: §2 rows have differing column counts (${[...new Set(counts)].join(', ')})`);
      assert.strictEqual(counts[0], 9,
        `${f}: expected 9 columns (变体 + 类型 + … + 判定 + 结论), got ${counts[0]}`);
    }
  });

  await t.test('类型 and 判定 take only their declared values', () => {
    const KIND = new Set(['raw', 'understand', 'improve', '类型', '---', '—']);
    const VERDICT = new Set(['adopted', 'rejected', 'informative', '判定', '---', '—']);
    for (const f of files) {
      for (const line of section2Rows(fs.readFileSync(path.join(DIR, f), 'utf8'))) {
        const c = rowCells(line);
        if (c.length !== 9) continue;
        assert.ok(KIND.has(c[1].trim()), `${f}: unknown 类型 "${c[1].trim()}"`);
        assert.ok(VERDICT.has(c[7].trim()), `${f}: unknown 判定 "${c[7].trim()}"`);
      }
    }
  });

  await t.test('a seeded edge stays `proposed` and always carries a falsification test', () => {
    // The migration derives the NAME from a 因子族 concept; it must never invent a claim. A
    // fabricated claim/test pair reads like evidence, and `status: proposed` would not save it,
    // because people quote what is written down — this repo already lost 287 of 549 strategies
    // to a screening rule that guessed.
    for (const f of files) {
      const body = fs.readFileSync(path.join(DIR, f), 'utf8');
      const block = (body.match(/^edge:\n(?:[ ]+.*\n)+/m) || [])[0];
      if (!block) continue;
      assert.match(block, /status: (proposed|measured|refuted)/, `${f}: edge entry has no status`);
      assert.match(block, /test: /, `${f}: every edge entry needs a test (wiki-schema §2.3)`);
      if (/未回答/.test(block)) {
        assert.match(block, /status: proposed/,
          `${f}: a seeded placeholder must stay proposed until an experiment answers it`);
      }
    }
  });

  await t.test('an edge block says something, and `proposed` needs no evidence', () => {
    // ⚠ An earlier version of this test demanded that every block be derivable from a 因子族
    // concept OR cite evidence. That was wrong, and 红利低频 caught it: a reasoned hypothesis with
    // a mandatory falsification test and no measurement yet is EXACTLY what `proposed` means.
    // Requiring evidence for it would collapse the three statuses into one.
    //
    // What actually protects against a fabricated block is elsewhere and already tested: every
    // entry must carry a `test:`, every non-proposed entry must cite `evidence:`, and
    // edge-redundancy excludes `proposed` from the map so a guess cannot retire a family.
    let blocks = 0;
    for (const f of files) {
      const body = fs.readFileSync(path.join(DIR, f), 'utf8');
      const block = (body.match(/^edge:\n(?:[ ]+.*\n)+/m) || [])[0];
      if (!block) continue;
      blocks++;
      assert.match(block, /^\s+- name:\s*\S/m, `${f}: edge: block has no entry`);
      // Length of the claim, not a run of non-space characters — several claims open with "⚠ "
      // and a regex like /\S{10,}/ stops at that first space.
      for (const m of block.matchAll(/^\s+claim:\s*"?(.*?)"?\s*$/gm)) {
        assert.ok(m[1].trim().length >= 10, `${f}: a claim too short to mean anything: "${m[1]}"`);
      }
    }
    assert.ok(blocks >= 12, `expected the edge pass to have covered the library, got ${blocks}`);
  });

  await t.test('the migration tool cannot write to §6 at all', () => {
    // ⚠ An earlier version of this diffed each page's §6 against HEAD. It fired every time a
    // /run-family round legitimately appended to §6 — which is the loop's normal job — so it
    // reported "the only durable copy of the findings changed!" for correct work. A guard that
    // trips during ordinary use gets disabled, and then it guards nothing.
    //
    // The invariant that actually matters is about the TOOL: edge-migrate edits frontmatter and
    // the §2 table, and must never reach §6. That is checkable at the source, and it does not
    // care what a research round is doing right now.
    const src = fs.readFileSync(path.join(__dirname, '../utils/edge-migrate.js'), 'utf8');
    assert.match(src, /sectionRange\(lines, \/\^## 2\\\.\/, \/\^## 3\\\.\//,
      'the migration must be scoped to the §2..§3 range');
    assert.doesNotMatch(src, /## 6\./, 'edge-migrate must not reference §6');
  });

  await t.test('every page still HAS a study log to protect', () => {
    // findings.tsv is gitignored and nothing can reconstruct it, so §6 is the only copy. If a
    // page loses it, that is the alarm — not the fact that it changed.
    let withLog = 0;
    for (const f of files) {
      const body = fs.readFileSync(path.join(DIR, f), 'utf8');
      if (/^## 6\./m.test(body)) withLog++;
    }
    assert.ok(withLog >= 12, `only ${withLog} of ${files.length} pages carry a §6 study log`);
  });
});

/**
 * The edge pass, 2026-09-21. Zero backtests: every claim below was written from evidence already
 * on the pages (§1 mechanism + §6 study log), and the vocabulary is wiki-schema §2.3.
 *
 * What it bought, and why it is worth a test: under epoch 6 `component-scan` reports every
 * candidate in every type with NEGATIVE uplift, and CLAUDE.md separately records that 57% of
 * gate-passes are 小市值 variants. Those are the same fact. Naming the edge makes it legible —
 * and three of the redundant families carry names that say nothing about size.
 */
test('the edge pass holds its invariants', async (t) => {
  const redundancy = require('../utils/edge-redundancy.js');

  await t.test('only `measured` claims enter the redundancy map', () => {
    // A proposed claim carries no authority (§2.3). Letting one count would allow a guess to
    // retire a family — the failure mode that cost this repo 287 of 549 strategies once.
    const r = redundancy.report();
    const clustered = new Set(r.clusters.flatMap(c => c.families));
    for (const p of r.proposed) {
      const alsoMeasured = r.clusters.some(c => c.families.includes(p.family)
        && c.name === p.name);
      assert.ok(!alsoMeasured, `${p.family}: a proposed "${p.name}" leaked into the redundancy map`);
    }
    assert.ok(clustered.size > 0, 'expected at least one measured edge');
  });

  await t.test('none-found is flagged, never excluded', () => {
    // Human decision 2026-09-21. A family nobody can name an edge for is a reason to look harder.
    const r = redundancy.report();
    assert.ok(r.noneFound.length >= 1);
    for (const x of r.noneFound) {
      assert.ok(x.claim && x.claim.length > 20,
        `${x.family}: none-found must SAY why, not just assert absence`);
    }
  });

  await t.test('redundant() needs a shared MEASURED edge, not a shared name', () => {
    const same = redundancy.redundant('ETF动量', '多因子ML');
    assert.strictEqual(same.redundant, true, 'both are supplied by 规模因子');
    assert.ok(same.shared.includes('规模因子'));
    const diff = redundancy.redundant('ETF动量', '打板短线');
    assert.strictEqual(diff.redundant, false);
  });

  await t.test('every claim carries a falsification test, refuted ones included', () => {
    for (const f of redundancy.families()) {
      for (const e of f.edges) {
        assert.ok(e.test && e.test.length > 10,
          `${f.family}/${e.name}: a claim with no stated refutation is not a claim (§2.3)`);
        if (e.status !== 'proposed') {
          assert.ok(e.evidence, `${f.family}/${e.name}: status ${e.status} must cite evidence`);
        }
      }
    }
  });
});
