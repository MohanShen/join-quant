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

  await t.test('no family has an edge block that nothing derives', () => {
    // Absent means UNANSWERED (§2.3), so a missing block is fine. What is not fine is a block
    // appearing without a derivation or an experiment behind it.
    const migrate = require('../utils/edge-migrate.js');
    let seeded = 0;
    for (const f of files) {
      const body = fs.readFileSync(path.join(DIR, f), 'utf8');
      if (!/^edge:/m.test(body)) continue;
      seeded++;
      const measured = /status: measured/.test(body);
      assert.ok(migrate.derivedEdge(body) || measured,
        `${f}: carries edge: but neither a 因子族 concept nor a measurement supports it`);
    }
    assert.ok(seeded >= 2, `expected the 因子族-declaring families to be seeded, got ${seeded}`);
  });

  await t.test('the study log was not touched by the migration', () => {
    // The one irreversible thing in this repo's wiki. If a future change starts rewriting §6,
    // this is where it should stop.
    const { execFileSync } = require('child_process');
    for (const f of files) {
      const rel = `wiki/families/${f}`;
      let head;
      try {
        head = execFileSync('git', ['show', `HEAD:${rel}`],
          { cwd: path.join(__dirname, '..'), encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
      } catch { continue; }          // new page, nothing to compare
      const sec6 = s => (s.split('\n').reduce((a, l) => {
        if (/^## 6\./.test(l)) a.on = true;
        else if (/^## 7\./.test(l)) a.on = false;
        if (a.on) a.out.push(l);
        return a;
      }, { on: false, out: [] }).out.join('\n'));
      assert.strictEqual(sec6(fs.readFileSync(path.join(DIR, f), 'utf8')), sec6(head),
        `${rel}: §6 study-log differs from HEAD — findings.tsv is gitignored, so this is the only copy`);
    }
  });
});
