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
  // ⚠ The wiki `normalized:` blocks are the ledger's DURABLE BACKUP, so this reconstructs from
  // them. After a measurement-breaking bump there is nothing to reconstruct: `epoch-reset.js`
  // strips the blocks because they describe windows the active bench no longer measures. An empty
  // result is then correct, and the column/format assertions below still run on whatever exists.
  // ⚠ The condition is SUFFICIENCY, not emptiness. A first version skipped only at 0 rows, which
  // broke the moment the library was PARTIALLY re-measured: epoch 9 stripped every `normalized:`
  // block, normalize-sync then wrote fresh ones for the handful of re-measured strategies, and
  // `rows.length` sat at ~18 — non-zero, so the skip did not fire, and "expected >100" failed on
  // a correct mid-re-measurement state.
  const nothingToRebuild = rows.length < 100;

  await t.test('recovers a row for every page carrying a TRAIN result',
    { skip: nothingToRebuild }, () => {
    assert.ok(rows.length > 100, `expected >100 reconstructed rows, got ${rows.length}`);
  });

  await t.test('emits exactly the 13 ledger columns', () => {
    for (const r of rows) assert.strictEqual(r.length, 13);
  });

  await t.test('marks every row as normalized, with the window its LABEL declares', () => {
    // ⚠ Not the ACTIVE window. A rebuild decodes whatever label each page carries, which for a
    // page written before epoch 9 is TRAIN 2022-2023 — that is the point of a historical decoder.
    const spec = require('../utils/normalize-ledger-rebuild');
    for (const r of rows) {
      assert.strictEqual(r[3], 'normalized');
      assert.ok(/^\d{4}-\d{2}-\d{2}$/.test(r[4]) && /^\d{4}-\d{2}-\d{2}$/.test(r[5]),
        `a reconstructed row needs real dates, got ${r[4]}..${r[5]}`);
      assert.ok(r[4] < r[5]);
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
    // ⚠ With an EMPTY ledger every strategy is legitimately backlog and this invariant is
    // vacuous — which is exactly the state a measurement-breaking epoch bump leaves behind
    // (epoch 9). The failure mode it guards (gating on measurementValid() took the queue from 53
    // to 175) can only be observed once there are terminal rows again.
    // ⚠ Same sufficiency rule: `=== 0` was too narrow. Mid-re-measurement the ledger holds a few
    // dozen rows, so the early return did not fire and `checked > 50` failed on correct behaviour.
    // The invariant can only be observed once there are enough terminal rows to observe it with.
    if (checked + queued.size === 0 || newest().size < 60) return;
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

  /**
   * ⚠⚠⚠ A listed entry whose own log says FINISHED is not a live blocker.
   *
   * Measured 2026-10-18: the normalizer sat in the waiter for 34 of 50 minutes at 0.21s CPU on
   * 这是一个简单的策略-1251, a COMPLETED run JQ never dropped from `running`. The age rule cannot
   * help — at 36min the entry was UNDER the 45min cap, so it read as "ours, still running. WAIT",
   * the one verdict that is pure loss here.
   *
   * ⚠ This was withheld until the state code was OBSERVED, because this waiter is what prevents
   * two concurrent backtests and concurrent runs have returned IDENTICAL metrics for different
   * strategies on this account. Settled by instrumenting the executor to print the state while a
   * run was KNOWN live (`LIVE-RUN-STATE`): in-flight = 1, finished = 2. Live-checked afterwards:
   * two CANCELLED-but-unreaped entries both reported 1 and correctly kept blocking — the check
   * fires only on runs that actually finished, which are the ones with a result to capture.
   */
  await t.test('a FINISHED entry stops blocking, but only on a positive read', () => {
    const src = cwfs.readFileSync(cwpath.join(__dirname, '../utils/jq-running.js'), 'utf8');
    // The probe is keyed by the entry's OWN id, which is what makes it attributable to that entry
    // even though the entry is not attributable to one of our algorithms.
    cwa.match(src, /algorithm\/backtest\/log\?backtestId=\$\{bt\}/);
    cwa.match(src, /finishedIds\.add\(r\.id\)/);
    cwa.match(src, /!finishedIds\.has\(r\.id\)/, 'the live filter must exclude finished entries');

    // ⚠ ONLY an exact '2' clears an entry. state 1, null (unreadable) and a throw must all leave
    // it blocking — a false "not blocking" corrupts results, a false "blocking" only wastes time.
    // ⚠ Clearing must be a POSITIVE read against a WHITELIST, never a truthy test and never a
    // blacklist. '2' = finished (settled 2026-10-18 via LIVE-RUN-STATE); '3' = errored (settled
    // 2026-10-22 on 这是一个简单的策略-1424, whose log's first line is an import Traceback and
    // whose episode never moved `duration.used` off 90). A state nobody has observed must keep
    // the entry BLOCKING, because a false "not blocking" permits two concurrent backtests and
    // concurrent runs have returned identical metrics for different strategies.
    cwa.match(src, /DONE_STATES\s*=\s*new Set\(\[([^\]]*)\]\)/,
      'the done states must be an explicit whitelist');
    const listed = src.match(/DONE_STATES\s*=\s*new Set\(\[([^\]]*)\]\)/)[1];
    cwa.match(listed, /'2'/, "'2' (finished) must clear");
    cwa.match(listed, /'3'/, "'3' (errored) must clear — it can never complete");
    cwa.ok(!/'1'/.test(listed), "'1' is IN-FLIGHT and must never clear");
    cwa.match(src, /DONE_STATES\.has\(st\)/, 'the whitelist must be what gates the clear');
    cwa.doesNotMatch(src, /st\s*!==?\s*'1'/, 'never infer finished from "not 1"');
    // The age rule stays — a cancelled-but-unreaped run reports 1 and is still handled by age.
    cwa.match(src, /cnMinutes\(r\.usedSec\) <= STALE_MIN/);
  });

  /**
   * ⚠⚠⚠ BOTH blockers must answer "is this entry live?" with the SAME rule.
   *
   * "Is the account blocked?" is asked in two places: `waitClear` here, and `concurrencyGate` in
   * the executor. The finished-entry rule above landed in the waiter ONLY, and the two then
   * disagreed about one entry and LIVELOCKED the normalizer — the executor's age-only split put a
   * finished 28-minute entry in `young` and printed CONCURRENT-STOP, the normalizer called the
   * waiter, the waiter cleared the account in seconds, the same file was retried, refused again,
   * round and round. Measured 2026-10-21: `used` frozen at 49/180 for ~38 minutes with 183 files
   * pending and a waiter child respawning every few seconds — a whole day spent refusing itself.
   *
   * It is not enough that both files happen to implement the rule: they must SHARE it, because the
   * failure was a fix applied to one copy. So `probeFinished` is exported and the executor calls
   * it, and this test fails if the executor grows its own version.
   */
  await t.test('the executor and the waiter share ONE finished-entry rule', () => {
    const jr = cwfs.readFileSync(cwpath.join(__dirname, '../utils/jq-running.js'), 'utf8');
    const ex = cwfs.readFileSync(cwpath.join(__dirname, '../utils/strategy-post-backtest.js'), 'utf8');

    cwa.match(jr, /module\.exports = \{[^}]*probeFinished/, 'the rule must be exported to be shared');
    cwa.ok(require('../utils/jq-running').probeFinished, 'probeFinished must be callable');

    cwa.match(ex, /require\('\.\/jq-running'\)/, 'the executor must import the rule, not restate it');
    cwa.match(ex, /probeFinished\(page, rows\)/, 'concurrencyGate must actually call it');
    cwa.match(ex, /finishedIds\.has\(r\.id\)/,
      'a finished entry must be excluded from the refuse-worthy category');

    // ⚠ The silent way to break this: the executor's running[] map drops `id`, so probeFinished
    // has nothing to key on, returns an empty set, and the livelock returns with every call site
    // still looking correct.
    const mapLine = (ex.match(/\.map\(r => \(\{ usedSec: r\.usedSec[^)]*\)/) || [''])[0];
    cwa.match(mapLine, /id: r\.id/, 'the executor must carry each entry id through to the probe');

    // The executor must not re-derive "finished" from the log itself — one owner, one rule.
    const gate = ex.slice(ex.indexOf('async function concurrencyGate'),
                          ex.indexOf('async function usageGate'));
    cwa.doesNotMatch(gate, /backtest\/log\?backtestId=/,
      'the executor must not grow a second copy of the log probe');
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

/**
 * ⚠⚠⚠ `realizabilityFlags:` was DEAD CODE: written, documented, never called.
 *
 * CLAUDE.md says kb-stub "stamps `realizabilityFlags:` beside the `normalized:` block, because
 * that line is what feeds §3, `wiki/types/` and champion resolution". The lint existed, the
 * 18-of-259 figure came from its CLI, the rationale was recorded — and `realizabilityLine()` was
 * called by nothing and exported by nothing. Measured 2026-10-22: **0 of 256 pages** carried a
 * flag line, so the caveat a §3 reader needs was on no page at all, the night the bench's top
 * four turned out to be limit-up/auction books at sharpe 11.95 / 11.46 / 11.48 / 5.14.
 */
dbt('realizability flags reach the page', async (t) => {
  const ns = require('../utils/normalize-sync');
  const kb = require('../utils/kb-stub');
  const tmp2 = () => dbfs.mkdtempSync(dbpath.join(dbos.tmpdir(), 'kbflag-'));

  await t.test('the writer is reachable at all — exported and called', () => {
    dba.ok(typeof kb.realizabilityLine === 'function', 'realizabilityLine must be exported');
    dba.ok(typeof kb.stampRealizability === 'function', 'stampRealizability must be exported');
    const sync = dbfs.readFileSync(dbpath.join(__dirname, '../utils/normalize-sync.js'), 'utf8');
    dba.match(sync, /stampRealizability\(/, 'something must CALL it — dead code is how this broke');
    dba.match(sync, /const realizability = syncRealizability\(/,
      'sync() must run it, so every entry point converges like stubs and queue pruning do');
  });

  /**
   * ⚠ The bug this test exists for, hit while writing the feature: the dry run reported 34 pages
   * to stamp and the real run stamped 0. `lintFile(rel)` does `path.join(ROOT, rel)`, so an
   * ABSOLUTE path becomes garbage, `readFileSync` throws, and the catch returns `[]` — identical
   * to "this book has no flags". One code path passed `src`, the other `path.join(ROOT, src)`.
   */
  await t.test('an absolute sourceFile THROWS rather than silently finding no flags', () => {
    const d = tmp2(), f = dbpath.join(d, 'p.md');
    dbfs.writeFileSync(f, '---\npostId: a\n---\n\n# x\n');
    dba.throws(() => kb.stampRealizability(f, '/abs/strategies/x.py'), /repo-relative/);
  });

  await t.test('dry and wet agree on what would change', () => {
    const a = ns.syncRealizability({ dry: true });
    const b = ns.syncRealizability({ dry: true });
    dba.deepStrictEqual(
      { add: a.added.length, up: a.updated.length, rm: a.removed.length },
      { add: b.added.length, up: b.updated.length, rm: b.removed.length },
      'the dry decision must be deterministic');
    // After the real sync ran, a dry run must report nothing left to do — which is exactly the
    // invariant the absolute-path bug violated (dry said 34, wet did 0, dry still said 34).
    dba.strictEqual(a.added.length, 0, 'the live wiki should already be stamped');
    dba.strictEqual(a.updated.length, 0);
  });

  await t.test('it is idempotent, and the flag sits beside the measurement', () => {
    const d = tmp2(), f = dbpath.join(d, 'p.md');
    // A real flagged source, so the lint actually fires: the bench's #3 book buys at 09:25:41.
    const src = dbfs.readdirSync(dbpath.join(__dirname, '../strategies'))
      .find(x => x.includes('38ca196e'));
    dba.ok(src, '38ca196e must still exist for this fixture');
    const rel = `strategies/${src}`;
    dbfs.writeFileSync(f, `---\npostId: a\nsourceFile: ${rel}\nnormalized: { epoch: 9 }\n---\n\n# x\n`);

    dba.strictEqual(kb.stampRealizability(f, rel), 'added');
    const once = dbfs.readFileSync(f, 'utf8');
    dba.match(once, /^normalized: \{ epoch: 9 \}\nrealizabilityFlags: \[call-auction-entry\]/m,
      'the flag belongs immediately after the measurement it qualifies');

    dba.strictEqual(kb.stampRealizability(f, rel), 'unchanged');
    dba.strictEqual(dbfs.readFileSync(f, 'utf8'), once, 'a second stamp must not alter the file');
  });

  await t.test('a flag that no longer applies is REMOVED, not left to rot', () => {
    const d = tmp2(), f = dbpath.join(d, 'p.md');
    // An unflagged source with a stale flag line: it must go. A column with one wrong entry is
    // what taught readers to ignore `limit-up-entry` before it was deleted.
    const clean = dbfs.readdirSync(dbpath.join(__dirname, '../strategies'))
      .find(x => require('../utils/realizability-lint').lintFile(`strategies/${x}`).length === 0);
    dba.ok(clean, 'some strategy must lint clean');
    dbfs.writeFileSync(f, `---\npostId: a\nsourceFile: strategies/${clean}\n` +
                          'realizabilityFlags: [tick-depth-x100!]   # stale\n---\n\n# x\n');
    dba.strictEqual(kb.stampRealizability(f, `strategies/${clean}`), 'removed');
    dba.doesNotMatch(dbfs.readFileSync(f, 'utf8'), /realizabilityFlags/);
  });
});

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
    // Two copies of this format would drift, and normalize-ledger-rebuild.js parses it back.
    // ⚠ This used to enforce single-sourcing by COUNTING the literal `window: "TRAIN 2022-2023"`
    // and requiring exactly one occurrence. Epoch 9 moved TRAIN to 2024 and the label became
    // DERIVED, so the literal is gone entirely — a strictly stronger form of the same guarantee,
    // but it took the old assertion to 0 !== 1. Assert the property instead of a spelling:
    // exactly one place builds the block, and the window in it comes from the harness.
    const src = dbfs.readFileSync(dbpath.join(__dirname, '../utils/kb-stub.js'), 'utf8');
    dba.strictEqual((src.match(/`normalized: \{ epoch:/g) || []).length, 1,
      'exactly one builder may construct the normalized: block');
    dba.ok(!/window: "TRAIN \d/.test(src),
      'the window label must be derived from the harness, never written down here');
    dba.match(src, /windowLabel\('train'\)/, 'and normalizedLine must use it');
    // The label tracks the active epoch, whatever its windows are.
    const { windowLabel } = require('../utils/kb-stub');
    const years = require('../utils/harness-config').windowYears('train').map(y => y.year);
    dba.strictEqual(windowLabel('train'),
      years.length === 1 ? `TRAIN ${years[0]}` : `TRAIN ${years[0]}-${years[years.length - 1]}`);
    dba.match(normalizedLine(M), new RegExp(`window: "${windowLabel('train')}"`));
    dba.match(normalizedLine(M), /epoch: 6.*sharpe: -0\.48.*gate: fail/);
  });
});

test('--redo re-measures already-valid rows, but only behind an explicit --files list', async t => {
  // Why --redo exists: the curve store is LOSSY in a way the ledger is not. JQ reaps retained
  // algorithms, so a row can be a current measurement while its daily curve is gone — measured
  // 2026-10-16, four family champions matched ZERO of 3,796 cached account curves at any
  // tolerance, so series-backfill (the free path) could not recover them. Since epoch 8 the
  // integration bar is per-year sharpe off those curves, so a missing curve silently downgrades
  // the bar to the pooled fallback.
  const execFileSync = require('child_process').execFileSync;
  const norm = path.join(UTILS, 'strategy-normalize.js');

  await t.test('refuses a bulk redo — it would re-bill the whole library', () => {
    // The guard matters because the failure is expensive and silent: a bare require of this file
    // once started a 214-strategy batch and spent 42 backtest minutes before being killed.
    let code = 0, out = '';
    try {
      out = execFileSync(process.execPath, [norm, '--window', 'train', '--redo', '--dry-run'],
        { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) {
      code = e.status; out = String(e.stdout || '') + String(e.stderr || '');
    }
    assert.strictEqual(code, 2, 'a --redo with no --files must exit non-zero');
    assert.match(out, /--redo requires an explicit --files list/);
  });

  await t.test('without --redo, a file with a valid row is NOT selected', () => {
    const src = fs.readFileSync(norm, 'utf8');
    // The default path must still filter by `done`, or every batch re-bills the library.
    assert.match(src, /todo = files\.filter\(f => !done\.has\('strategies\/' \+ f\)\)/);
  });

  await t.test('the redo path announces the re-bill rather than doing it quietly', () => {
    const src = fs.readFileSync(norm, 'utf8');
    assert.match(src, /--redo: re-measuring/);
    assert.match(src, /newest-row-wins/, 'the operator must be told the new row supersedes');
  });
});
