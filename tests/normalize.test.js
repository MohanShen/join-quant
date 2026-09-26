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

/**
 * The backfill must be epoch-aware, or terminal rows from a dead bench strand work forever.
 *
 * Measured 2026-09-23: JQ dropped the session mid-normalize, eight strategies came back `crash`,
 * and the normalizer's circuit breaker correctly stopped after 6 consecutive failures. `crash` is
 * retriable everywhere — strategy-normalize, normalize-sync and normalize-daily all keep it out of
 * TERMINAL. But every one of those eight ALSO carried an epoch-2 `normalized` or `slow-skipped`
 * row, and ledgerStatus() matched on status alone. So the backfill called them done, the pending
 * queue no longer held them, and they became unreachable at any cap — silently.
 *
 * The same blind spot hid the entire epoch-6 re-measurement set: any strategy with a stale
 * terminal row was excluded from the backlog by construction.
 */
const bft = require('node:test');
const bfa = require('node:assert');
const bffs = require('fs');
const bfpath = require('path');

bft('normalize backfill is epoch-aware', async (t) => {
  const backfill = require('../utils/normalize-backfill');
  const harness = require('../utils/harness-config');
  const LEDGER = bfpath.join(__dirname, '../harness/normalize-train.tsv');

  const rows = () => {
    const out = new Map();
    let text;
    try { text = bffs.readFileSync(LEDGER, 'utf8'); } catch { return out; }
    for (const l of text.split('\n').slice(1)) {
      const c = l.split('\t');
      if (!c[0]) continue;
      if (!out.has(c[0])) out.set(c[0], []);
      out.get(c[0]).push({ status: c[3], epoch: c[13] || '2' });
    }
    return out;
  };

  await t.test('a terminal row from a superseded epoch does not count as done', () => {
    const all = rows();
    const queued = new Set(backfill.build({}).queued.map(q => `strategies/${q.file}`));
    for (const [file, rs] of all) {
      const validTerminal = rs.some(r => harness.measurementValid(r.epoch) &&
        ['normalized', 'compile-error', 'slow-skipped', 'no-trades',
         'incompatible-futures', 'incompatible-notrunnable', 'failed-final'].includes(r.status));
      const onlyStale = !validTerminal && rs.some(r => !harness.measurementValid(r.epoch));
      if (onlyStale && bffs.existsSync(bfpath.join(__dirname, '..', file))) {
        bfa.ok(queued.has(file),
          `${file} has only superseded rows but is not in the backlog — stranded`);
      }
    }
  });

  await t.test('a crashed strategy is reachable again', () => {
    // `crash` is retriable by every other component; the backfill was the one that forgot.
    const crashed = [...rows()].filter(([, rs]) => rs.some(r => r.status === 'crash')).map(([f]) => f);
    if (!crashed.length) return;
    const queued = new Set(backfill.build({}).queued.map(q => `strategies/${q.file}`));
    for (const f of crashed) {
      if (!bffs.existsSync(bfpath.join(__dirname, '..', f))) continue;
      bfa.ok(queued.has(f), `${f} crashed and cannot be retried`);
    }
  });

  await t.test('re-measurements queue BEHIND genuinely unmeasured work', () => {
    // Otherwise 121 re-measurements land ahead of 54 strategies we have no number for at all.
    const q = backfill.build({}).queued;
    const firstRestale = q.findIndex(x => x.restale);
    const lastFresh = q.map(x => !x.restale).lastIndexOf(true);
    if (firstRestale >= 0 && lastFresh >= 0) {
      bfa.ok(firstRestale > lastFresh,
        'a superseded-epoch re-measurement is queued ahead of never-measured work');
    }
  });
});

/**
 * A refusal is not a crash.
 *
 * `crash` means the executor emitted no SUMMARY line. Every completion path prints one, so the
 * status is meant to catch "the child died". But the concurrency gate returns BEFORE reportResult,
 * printing only CONCURRENT-STOP — so on 2026-09-23 six refusals in a row became six crash rows and
 * tripped the circuit breaker, which blamed "JQ rate-limit or session drop". The session was fine.
 *
 * The strategies then became unreachable, because a crash row plus an older terminal row hid them
 * from the backfill. A gate that refuses to start must not look like a strategy that failed.
 */
const cst = require('node:test');
const csa = require('node:assert');
const csfs = require('fs');
const cspath = require('path');

cst('a gate refusal is distinguished from a crash', async (t) => {
  const norm = csfs.readFileSync(cspath.join(__dirname, '../utils/strategy-normalize.js'), 'utf8');
  const exec = csfs.readFileSync(cspath.join(__dirname, '../utils/strategy-post-backtest.js'), 'utf8');

  await t.test('every early-return marker the executor prints is understood by the normalizer', () => {
    // Only markers that signal an EARLY EXIT: by convention those end in -STOP or -BLOCKED.
    // (QUOTA is printed on every normal run and is not an exit.) Anything the child prints and
    // then returns on, without a SUMMARY, must be handled here — otherwise it is silently
    // recorded as a failure of the strategy.
    const markers = [...new Set(
      [...exec.matchAll(/([A-Z][A-Z-]*(?:STOP|BLOCKED))\\t/g)].map(m => m[1]))];
    csa.ok(markers.includes('USAGE-STOP') && markers.includes('CONCURRENT-STOP'),
      `expected both stop markers in the executor, found: ${markers.join(', ')}`);
    for (const m of markers) {
      csa.ok(norm.includes(`${m}\\t`), `the normalizer does not recognise ${m} — it will record a crash`);
    }
  });

  await t.test('CONCURRENT-STOP stops the batch without blaming the strategy', () => {
    // Locate the CODE, not the comment that explains it.
    const at = norm.indexOf("const cs = out.split");
    csa.ok(at > 0, 'the CONCURRENT-STOP handler is missing');
    const block = norm.slice(at, at + 700);
    csa.match(block, /break;/, 'it must stop the batch');
    csa.doesNotMatch(block, /appendRow/, 'it must not write a ledger row against the strategy');
  });

  await t.test('a genuine crash records WHY, not an empty row', () => {
    csa.match(norm, /normalize-crashes\.log/,
      'the child output is the only evidence of a crash and must be kept');
    csa.match(norm, /const why = out\.split/);
  });
});

/**
 * The backtest log is retrievable. CLAUDE.md said otherwise for months, and that claim shaped
 * every probe in study/_probes/ — they smuggled answers out as marker trades because nothing
 * could read what a strategy printed. The bare URL does 400; the parameters are the difference.
 */
cst('backtest logs are readable', async (t) => {
  const src = csfs.readFileSync(cspath.join(__dirname, '../utils/backtest-log.js'), 'utf8');

  await t.test('the working URL carries its parameters', () => {
    csa.match(src, /backtest\/log\?backtestId=\$\{bid\}&offset=0&limit=\$\{limit\}&ajax=1/);
    csa.match(src, /backtest\/error\?backtestId=\$\{bid\}&ajax=1/);
  });

  await t.test('it resolves the id rather than storing one', () => {
    // Ids are re-minted per request, so resolution and use must happen together.
    csa.match(src, /buildList\?algorithmId=/);
    csa.match(src, /re-minted/);
  });

  await t.test('CLAUDE.md no longer claims the log is unavailable', () => {
    const doc = csfs.readFileSync(cspath.join(__dirname, '../CLAUDE.md'), 'utf8');
    csa.doesNotMatch(doc, /log is not retrievable/,
      'the corrected note must replace the old claim, not sit beside it');
    csa.match(doc, /The backtest log IS retrievable/);
  });
});
