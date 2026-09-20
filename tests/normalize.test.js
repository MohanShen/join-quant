/**
 * Tests for the normalize ledger: reconstruction from the wiki, and the terminal
 * status set.
 *
 * Both cover real incidents:
 *   - the ledger is gitignored and silently regressed from ~119 normalized rows to
 *     18, freezing every family page's §3 table, and
 *   - `no-trades` sat in neither the terminal nor the retriable set, so those
 *     strategies were re-run and re-billed on every batch forever.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const { parseNormalized, rowsFromWiki } = require('../utils/normalize-ledger-rebuild');

const UTILS = path.join(__dirname, '..', 'utils');

test('parseNormalized', async t => {
  await t.test('reads a full block written by kb-stub', () => {
    const got = parseNormalized(
      'normalized: { epoch: 1, window: "TRAIN 2022-2023", annualReturn: 0.5698, ' +
      'sharpe: 3.21, maxDrawdown: 0.0961, objective: 0.4737, gate: pass }'
    );
    assert.strictEqual(got.window, 'TRAIN 2022-2023');
    assert.strictEqual(got.annualReturn, '0.5698');
    assert.strictEqual(got.sharpe, '3.21');
    assert.strictEqual(got.maxDrawdown, '0.0961');
    assert.strictEqual(got.objective, '0.4737');
    assert.strictEqual(got.gate, 'pass');
  });

  await t.test('handles a DQ objective and negative returns', () => {
    const got = parseNormalized(
      'normalized: { epoch: 1, window: "TRAIN 2022-2023", annualReturn: -0.1166, ' +
      'sharpe: -0.97, maxDrawdown: 0.2385, objective: DQ, gate: fail }'
    );
    assert.strictEqual(got.objective, 'DQ');
    assert.strictEqual(got.annualReturn, '-0.1166');
    assert.strictEqual(got.gate, 'fail');
  });

  await t.test('returns null when there is no block', () => {
    assert.strictEqual(parseNormalized(undefined), null);
    assert.strictEqual(parseNormalized('autoStub: true'), null);
  });
});

test('rowsFromWiki', async t => {
  const { rows } = rowsFromWiki('TRAIN');

  await t.test('recovers a row for every page carrying a TRAIN result', () => {
    assert.ok(rows.length > 100, `expected >100 reconstructed rows, got ${rows.length}`);
  });

  await t.test('emits exactly the 13 ledger columns', () => {
    for (const r of rows) assert.strictEqual(r.length, 13);
  });

  await t.test('marks every row as normalized, with the frozen TRAIN window', () => {
    for (const r of rows) {
      assert.strictEqual(r[3], 'normalized');
      assert.strictEqual(r[4], '2022-01-01');
      assert.strictEqual(r[5], '2023-12-31');
    }
  });

  await t.test('leaves total_pct empty — the wiki does not store it', () => {
    // This emptiness is the in-file marker separating reconstructed rows from
    // measured ones. Back-computing it would look like real data.
    for (const r of rows) assert.strictEqual(r[7], '');
  });

  await t.test('converts fractions to percentages', () => {
    for (const r of rows) {
      if (r[8] !== '') assert.match(r[8], /^-?\d+\.\d{2}$/);   // annual_pct
      if (r[10] !== '') assert.match(r[10], /^-?\d+\.\d{2}$/); // maxdd_pct
    }
  });

  await t.test('carries a sourceFile that points into strategies/', () => {
    for (const r of rows) assert.match(r[0], /^strategies\/.*\.py$/);
  });
});

test('no-trades is a terminal status', async t => {
  // TERMINAL is a local const inside main(), so assert on the source. The cost of a
  // regression here is silent and recurring (re-billed backtests), which is worth a
  // guard even in this blunt form.
  await t.test('strategy-normalize treats it as terminal', () => {
    const src = fs.readFileSync(path.join(UTILS, 'strategy-normalize.js'), 'utf8');
    const line = src.split('\n').find(l => l.includes('const TERMINAL'));
    assert.ok(line, 'TERMINAL set not found');
    assert.ok(line.includes("'no-trades'"), 'no-trades missing from TERMINAL');
  });

  await t.test('it is NOT also retriable — that would double-count failures', () => {
    const src = fs.readFileSync(path.join(UTILS, 'strategy-normalize.js'), 'utf8');
    const line = src.split('\n').find(l => l.includes('const RETRIABLE'));
    assert.ok(line, 'RETRIABLE set not found');
    assert.ok(!line.includes("'no-trades'"), 'no-trades must not be retriable');
  });

  await t.test('the daily pruner uses the same set', () => {
    const src = fs.readFileSync(path.join(UTILS, 'normalize-daily.js'), 'utf8');
    const line = src.split('\n').find(l => l.includes('const TERMINAL'));
    assert.ok(line, 'TERMINAL set not found in normalize-daily');
    assert.ok(line.includes("'no-trades'"), 'no-trades missing — pending would never be pruned');
  });
});

test('the rebuilt ledger', async t => {
  const ledger = path.join(__dirname, '..', 'harness', 'normalize-train.tsv');

  await t.test('exists and carries the expected header', { skip: !fs.existsSync(ledger) }, () => {
    const head = fs.readFileSync(ledger, 'utf8').split('\n')[0].split('\t');
    // The first 13 columns are the original contract that wiki-family-build.js reads by index;
    // `epoch` was appended in epoch 4 to record which bench measured each row, and readers that
    // index 0..12 ignore it.
    assert.deepStrictEqual(head.slice(0, 13), ['sourceFile', 'postId', 'title', 'status', 'start',
      'end', 'days', 'total_pct', 'annual_pct', 'sharpe', 'maxdd_pct', 'objective', 'gate']);
    assert.ok(head.length === 13 || head[13] === 'epoch', `unexpected 14th column: ${head[13]}`);
  });

  await t.test('holds no duplicate sourceFile+status pair WITHIN an epoch', { skip: !fs.existsSync(ledger) }, () => {
    // Since epoch 4 the same file legitimately carries one row per epoch — that is the point
    // of the column, because a result only means something next to the bench that produced it.
    // A repeat within ONE epoch is still a bug (it is what the no-trades loop used to cause).
    const seen = new Set();
    const dupes = [];
    for (const l of fs.readFileSync(ledger, 'utf8').split('\n').slice(1)) {
      if (!l.trim()) continue;
      const c = l.split('\t');
      const k = `${c[0]} ${c[3]} epoch=${c[13] || '?'}`;
      if (seen.has(k)) dupes.push(k); else seen.add(k);
    }
    assert.deepStrictEqual(dupes, [], `duplicate ledger rows: ${dupes.join(', ')}`);
  });
});
