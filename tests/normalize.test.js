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

bft('normalize backlog is decided by the NEWEST ledger row', async (t) => {
  const backfill = require('../utils/normalize-backfill');
  const LEDGER = bfpath.join(__dirname, '../harness/normalize-train.tsv');
  const RETRIABLE = new Set(['failed', 'crash', 'window-mismatch', 'rate-limited', 'budget-stopped']);

  const newest = () => {
    const last = new Map();
    let text;
    try { text = bffs.readFileSync(LEDGER, 'utf8'); } catch { return last; }
    for (const l of text.split('\n').slice(1)) {
      const c = l.split('\t');
      if (c[0] && c[3]) last.set(c[0], c[3]);   // append-only: final write wins
    }
    return last;
  };

  await t.test('a file whose newest row FAILED is back in the backlog', () => {
    // The eight stranded on 2026-09-23 read `slow-skipped@e2, normalized@e2, crash@e6`: an old
    // terminal row plus a newer failed attempt. Matching on "has any terminal row" called them
    // done and nothing re-offered them at any cap.
    const queued = new Set(backfill.build({}).queued.map(q => `strategies/${q.file}`));
    for (const [file, status] of newest()) {
      if (!RETRIABLE.has(status)) continue;
      if (!bffs.existsSync(bfpath.join(__dirname, '..', file))) continue;
      bfa.ok(queued.has(file), `${file} newest row is ${status} but it is not in the backlog`);
    }
  });

  await t.test('a file whose newest row is terminal stays OUT, whatever its epoch', () => {
    // Epoch is not a queueing trigger. Gating on measurementValid() turned 141 already-measured
    // strategies into backlog and took the queue from 53 to 175. Those went through the family
    // pipeline and have numbers; a deliberate re-measurement is stockcost-affected.js's job.
    const queued = new Set(backfill.build({}).queued.map(q => `strategies/${q.file}`));
    let checked = 0;
    for (const [file, status] of newest()) {
      if (RETRIABLE.has(status)) continue;
      if (!queued.has(file)) { checked++; continue; }
      bfa.fail(`${file} newest row is ${status} (terminal) but it is queued for re-normalizing`);
    }
    bfa.ok(checked > 50, `expected many already-normed files to stay out, saw ${checked}`);
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

  await t.test('CONCURRENT-STOP never blames the strategy', () => {
    // The stop-vs-wait behaviour is covered by its own test below; what matters HERE is that a
    // refusal to start is never recorded as a failure of the strategy — that is what turned six
    // refusals into six crash rows and stranded them.
    const at = norm.indexOf("const cs = out.split");
    csa.ok(at > 0, 'the CONCURRENT-STOP handler is missing');
    const block = concurrentBlock(norm);
    csa.doesNotMatch(block, /appendRow/, 'it must not write a ledger row against the strategy');
    csa.match(block, /break;/, 'it must still be able to stop when the blocker outlasts the wait');
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

/**
 * A concurrent backtest must be WAITED OUT, not treated as the end of the batch.
 *
 * The blocker is usually ours: a slow-skipped strategy is cancelled locally at the cap, JQ does
 * not always honour the cancel (「在此状态不能取消」), and the leftover blocks the next strategy.
 * Measured 2026-09-26 — the batch normalized 2, slow-skipped 1, and its next stage hit
 * CONCURRENT STOP instantly; the chain read that as no progress and ended with ~130 of 180 budget
 * minutes unspent.
 */
/**
 * The CONCURRENT-STOP handler, sliced by its real boundaries.
 *
 * ⚠ These tests used to slice a hard-coded 2200 characters. Adding the age-vs-cap rule made the
 * handler longer and four assertions failed on correct code, because `break;`/`si--`/the retry
 * bound had moved past the window. A byte count is not a boundary; the next statement is.
 */
function concurrentBlock(norm) {
  const at = norm.indexOf('const cs = out.split');
  const end = norm.indexOf('// Escalate a retriable failure', at);
  if (at < 0 || end < 0) return '';
  return norm.slice(at, end);
}

const cwt = require('node:test');
const cwa = require('node:assert');
const cwfs = require('fs');
const cwpath = require('path');

cwt('a concurrent backtest is waited out', async (t) => {
  const norm = cwfs.readFileSync(cwpath.join(__dirname, '../utils/strategy-normalize.js'), 'utf8');
  const runner = require('../utils/jq-running');

  await t.test('the handler waits before it gives up', () => {
    const at = norm.indexOf("const cs = out.split");
    const block = concurrentBlock(norm);
    cwa.match(block, /jq-running\.js/, 'it must poll the account rather than stop immediately');
    cwa.match(block, /--wait/);
    cwa.match(block, /still blocked after/, 'it must still stop when the blocker outlasts the wait');

    // The wait must be DERIVED from the slow-skip cap, not a flat number. A 10min wait in front
    // of a 45min cap abandoned 136 of 180 budget minutes on 2026-10-02, waiting on a backtest
    // 19 minutes into its own entitlement.
    cwa.match(block, /waitMinFor\(MAX_POLL_MIN\)/,
      'the wait must come from the cap — our own run is entitled to the full cap');
    cwa.doesNotMatch(block, /--timeout-min', '10'|CONCURRENT_WAIT_MIN\b/,
      'a flat wait is what caused the lost budget');

    // And a past-cap blocker must be told apart from a live one.
    cwa.match(block, /--cap-min/, 'the waiter needs the cap to apply the age-vs-cap rule');
    cwa.match(block, /status === 2/, 'exit 2 (blocker past the cap) must be distinguished');

    // ⚠ This assertion used to demand the word PHANTOM in a STOPPING message, which encoded a
    // design that lasted one day. A past-cap blocker is a run of ours JQ would not cancel: it
    // never finishes, so waiting is pointless, but the executor now measures completion against
    // a baseline that includes it, so it is no longer a reason to stop. The invariant is that
    // exit 2 RETRIES and only a LIVE run stops the batch.
    const deadBranch = block.slice(block.indexOf('!cleared && phantom'));
    cwa.match(deadBranch, /cleared = true/, 'a dead blocker must let the retry proceed');
    cwa.match(block, /still blocked after \$\{waitMin\}min by a LIVE run/,
      'only genuine contention may stop the batch');
  });

  await t.test('a blocked strategy is retried in place, not consumed', () => {
    const block = concurrentBlock(norm);
    cwa.match(block, /si--/, '`continue` advances the loop, so a retry must step the index back');
    cwa.match(norm, /for \(let si = 0; si < slice\.length; si\+\+\)/,
      'the loop must be index-based for a retry to be possible');
  });

  await t.test('the retry is bounded, so it cannot spin', () => {
    const at = norm.indexOf("const cs = out.split");
    cwa.match(concurrentBlock(norm), /concurrentRetries\[srcFile\][\s\S]{0,60}> 2/);
  });

  await t.test('a stale phantom does not make the waiter block forever', () => {
    // One reached 701 minutes while billing nothing. The waiter must ignore those, exactly as
    // concurrencyGate does, or the batch waits on something JQ will never reap.
    const src = cwfs.readFileSync(cwpath.join(__dirname, '../utils/jq-running.js'), 'utf8');
    cwa.match(src, /JQ_CONCURRENT_STALE_MIN/);
    cwa.match(src, /cnMinutes\(r\.usedSec\) <= STALE_MIN/);
  });

  await t.test('an unreadable account is treated as clear, not as blocked', () => {
    // A transient CDP failure must not wedge the batch; the executor's own gate re-checks anyway.
    const src = cwfs.readFileSync(cwpath.join(__dirname, '../utils/jq-running.js'), 'utf8');
    cwa.match(src, /treating as clear/);
  });

  await t.test('the duration parser handles JQ\'s Chinese format', () => {
    cwa.strictEqual(Math.round(runner.cnMinutes('701分34秒')), 702);
    cwa.strictEqual(Math.round(runner.cnMinutes('1时02分')), 62);
    cwa.strictEqual(runner.cnMinutes(''), 0);
  });
});

/**
 * A strategy must not be normalized twice in one batch.
 *
 * Measured 2026-09-26: 5511f8f0 got two identical `normalized epoch=6` rows. A file can sit in the
 * deferred pool and the pending queue at the same time, the pipeline concatenated
 * `retry ++ pending` without de-duplicating, and the normalizer preserves caller order without
 * de-duping either — so it ran twice and appended twice. A ledger-integrity test caught it, which
 * is the only reason it did not sit there.
 */
const ddt = require('node:test');
const dda = require('node:assert');
const ddfs = require('fs');
const ddpath = require('path');

ddt('a file is normalized at most once per batch', async (t) => {
  await t.test('the pipeline de-duplicates the --files list it builds', () => {
    const src = ddfs.readFileSync(ddpath.join(__dirname, '../utils/daily-pipeline.js'), 'utf8');
    dda.match(src, /const files = \[\.\.\.new Set\(\[/,
      'retry ++ pending must be de-duplicated — a file can be in both');
  });

  await t.test('the normalizer de-duplicates whatever it is handed', () => {
    // Belt and braces: any caller, not just the daily pipeline, can repeat a basename.
    const src = ddfs.readFileSync(ddpath.join(__dirname, '../utils/strategy-normalize.js'), 'utf8');
    dda.match(src, /const asked = \[\.\.\.new Set\(raw\)\]/);
    dda.match(src, /duplicate\(s\) dropped/, 'dropping duplicates silently hides the caller bug');
  });

  await t.test('and it reports them, so the caller bug stays visible', () => {
    const out = require('child_process').execFileSync(process.execPath,
      ['utils/strategy-normalize.js', '--window', 'train', '--files', 'x.py,x.py,y.py', '--dry-run'],
      { cwd: ddpath.join(__dirname, '..'), encoding: 'utf8', timeout: 60000 });
    dda.match(out, /1 duplicate\(s\) dropped/);
  });

  await t.test('the ledger holds no duplicate file+status+epoch triple', () => {
    // The invariant the run violated. Newest-wins makes a duplicate harmless to READ, but it
    // inflates every count derived from the ledger.
    const text = ddfs.readFileSync(ddpath.join(__dirname, '../harness/normalize-train.tsv'), 'utf8');
    const seen = new Set();
    const dupes = [];
    for (const l of text.split('\n').slice(1)) {
      if (!l.trim()) continue;
      const c = l.split('\t');
      const k = `${c[0]}|${c[3]}|${c[13] || ''}`;
      if (seen.has(k)) dupes.push(k);
      seen.add(k);
    }
    dda.deepStrictEqual(dupes, [], `duplicate ledger rows: ${dupes.join(', ')}`);
  });
});

/**
 * Two gaps found by reviewing for the SHAPE of earlier bugs rather than for new ones.
 *
 * 1. One source of truth, two reading rules. The concurrency gate filtered running[] by age
 *    while the completion detector counted it unfiltered (97d8067). The same split existed one
 *    layer up: strategy-normalize.js's done-check is epoch-aware, normalize-daily.js's prune was
 *    not — so Pipeline 1 dropped files from data/pending-normalize.json that the normalizer still
 *    considered unmeasured. 92 ledger rows were in that state when this was written.
 * 2. A missing entry-point guard. A bare require() of strategy-normalize.js once spent 42 of a
 *    60-minute budget. dq-finalize.js was the last argv-using file in utils/ without one.
 */
const gpt = require('node:test');
const gpa = require('node:assert');
const gpfs = require('fs');
const gppath = require('path');

const GP_UTILS = gppath.join(__dirname, '../utils');

gpt('every argv-using entry point in utils/ is guarded', () => {
  // Generalized on purpose. Asserting dq-finalize.js specifically would not have caught
  // dq-finalize.js — nothing was looking at the directory as a whole.
  const unguarded = gpfs.readdirSync(GP_UTILS)
    .filter(f => f.endsWith('.js'))
    .filter(f => {
      const src = gpfs.readFileSync(gppath.join(GP_UTILS, f), 'utf8');
      return src.includes('process.argv') && !src.includes('require.main');
    });
  gpa.deepStrictEqual(unguarded, [],
    'these run on require() — a bare require of one has already cost 42 backtest minutes: ' +
    unguarded.join(', '));
});

gpt('the pending-queue prune agrees with the normalizer about "done"', async (t) => {
  const daily = gpfs.readFileSync(gppath.join(GP_UTILS, 'normalize-daily.js'), 'utf8');
  const norm = gpfs.readFileSync(gppath.join(GP_UTILS, 'strategy-normalize.js'), 'utf8');

  await t.test('both decide it the same way: terminal AND epoch-comparable', () => {
    gpa.match(norm, /TERMINAL\.has\(st\) && harness\.measurementValid\(rowEpoch\)/,
      'the normalizer is the authority here');
    gpa.match(daily, /harness\.measurementValid\(rowEpoch\)/,
      'the prune must apply the epoch half too, or it drops work the bump exists to redo');
    gpa.match(daily, /TERMINAL\.has\(r\.status\) && r\.measured/,
      'the prune must require BOTH halves');
  });

  await t.test('a stale-epoch row is not reported as 完成', () => {
    // Reporting it as normalized while building no stub would move the disagreement into the
    // summary rather than removing it.
    gpa.match(daily, /'stale-epoch'/);
    gpa.doesNotMatch(daily, /if \(!row \|\| row\[3\] !== 'normalized'\) \{/,
      'the un-epoched fast path is the bug');
  });

  await t.test('the stub is stamped with the epoch that measured it', () => {
    // kb-stub falls back to the ACTIVE epoch when this is absent, and that block is the
    // ledger's durable backup — the reason 120 pages once claimed a superseded bench.
    gpa.match(daily, /epoch: rowEpoch/);
  });

  await t.test('the gate bar is read live, not hard-coded', () => {
    gpa.match(daily, /harness\.stageThreshold\('normalize'\)/);
    gpa.doesNotMatch(daily, /夏普≥2\.5/, 'epoch 5 moved the bar to 1.5');
  });
});

/**
 * The durable backup: a measured strategy's `normalized:` block.
 *
 * createStub returned early for any EXISTING page and wrote nothing, so a strategy that already
 * had a page never received the block when it was measured. 16 of 136 normalized rows were in
 * that state — recoverable only from harness/normalize-train.tsv, which is gitignored and has
 * regressed from ~119 rows to 18 once.
 */
const dbt = require('node:test');
const dba = require('node:assert');
const dbfs = require('fs');
const dbos = require('os');
const dbpath = require('path');
const { stampNormalized, normalizedLine } = require('../utils/kb-stub');

dbt('an existing page gets its measurement, without losing anything', async (t) => {
  const M = { annual: -7.72, sharpe: '-0.48', maxdd: 32.62, obj: '-0.4034', gate: 'fail', epoch: '6' };
  const tmp = () => dbfs.mkdtempSync(dbpath.join(dbos.tmpdir(), 'kbstub-'));
  const write = (body) => { const d = tmp(), f = dbpath.join(d, 'p.md'); dbfs.writeFileSync(f, body); return f; };

  await t.test('a page with no block gains one', () => {
    const f = write('---\npostId: abc\ntitle: x\n---\n\n# x\n');
    dba.strictEqual(stampNormalized(f, M), 'added');
    dba.match(dbfs.readFileSync(f, 'utf8'), /^normalized: \{ epoch: 6,/m);
  });

  await t.test('a page that already has one is LEFT ALONE', () => {
    // ⚠ This is the regression guard. Rewriting the line from the ledger stripped `ranAt` —
    // a field this builder does not emit — from 70 tracked pages before it was reverted.
    const existing = 'normalized: { epoch: 2, window: "TRAIN 2022-2023", annualReturn: 0.4705, ' +
                     'sharpe: 1.67, maxDrawdown: 0.1740, objective: 0.2965, gate: pass, ranAt: 2026-07-11 }';
    const f = write(`---\npostId: abc\n${existing}\n---\n\n# x\n`);
    const before = dbfs.readFileSync(f, 'utf8');
    dba.strictEqual(stampNormalized(f, M), 'present');
    dba.strictEqual(dbfs.readFileSync(f, 'utf8'), before, 'not one byte may change');
    dba.match(dbfs.readFileSync(f, 'utf8'), /ranAt: 2026-07-11/, 'provenance must survive');
  });

  await t.test('it refuses to guess where there is no frontmatter', () => {
    dba.strictEqual(stampNormalized(write('# just a heading\n'), M), 'no-frontmatter');
  });

  await t.test('a row with no metrics writes nothing', () => {
    dba.strictEqual(stampNormalized(write('---\na: 1\n---\n'), {}), 'no-metrics');
  });

  await t.test('one builder serves both the create and the stamp path', () => {
    // Two copies of this format would drift, and normalize-ledger-rebuild.js parses it.
    const src = dbfs.readFileSync(dbpath.join(__dirname, '../utils/kb-stub.js'), 'utf8');
    dba.strictEqual((src.match(/window: "TRAIN 2022-2023"/g) || []).length, 1,
      'the literal must appear exactly once — in normalizedLine');
    dba.match(normalizedLine(M), /epoch: 6.*sharpe: -0\.48.*gate: fail/);
  });
});
