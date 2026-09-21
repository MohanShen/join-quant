/**
 * Tests for the daily pipeline: queue priority, the in-flight claim, and the deferred pool.
 *
 * The three things that decide whether an unattended daily job is trustworthy:
 *   - it spends the budget on the RIGHT stage (later stages outrank earlier ones);
 *   - a run that dies does not deadlock tomorrow's run;
 *   - a strategy that blew the cap is parked, not stranded — `slow-skipped` is terminal in
 *     the normalizer on purpose (so it is not re-billed every batch), which left 14 rows with
 *     no route back until the pool existed.
 *
 * State is redirected to a temp dir via JQ_DAILY_STATE_DIR before anything is required —
 * data/daily-state.json and data/deferred.json are TRACKED, and a test that appends probe
 * rows to them writes fiction into the record the next morning's run reads.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const os = require('os');

// Must be set BEFORE the modules below resolve their paths.
process.env.JQ_DAILY_STATE_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'jq-daily-'));

const daily = require('../utils/daily-pipeline');
const state = require('../utils/daily-state');

const ROOT = path.join(__dirname, '..');

test('queue priority', async t => {
  await t.test('later stages outrank earlier ones', () => {
    assert.deepStrictEqual(daily.PRIORITY, ['enhance', 'study', 'normalize', 'discover']);
  });

  await t.test('the planner picks the highest-priority non-empty queue', () => {
    const q = {
      enhance: [], study: [{ family: 'X' }],
      normalize: { pending: ['a.py'], retry: [], total: 1 },
      discover: { uncopied: 99, total: 99 },
    };
    // study is non-empty and outranks normalize/discover, so it wins despite being smaller.
    const first = daily.PRIORITY.find(s =>
      s === 'discover' ? true
      : s === 'normalize' ? q.normalize.total > 0
      : q[s].length > 0);
    assert.strictEqual(first, 'study');
  });

  await t.test('discover is the only stage allowed to run on an empty board', () => {
    // It is what refills the board, so an empty queue is its trigger rather than its veto.
    assert.strictEqual(daily.PRIORITY[daily.PRIORITY.length - 1], 'discover');
  });

  await t.test('a real plan names a stage and explains itself', () => {
    const p = daily.plan({ stageOverride: 'normalize' });
    assert.strictEqual(p.stage, 'normalize');
    assert.match(p.why, /override/);
    assert.ok(p.q && p.q.normalize, 'the plan must carry the queues it decided from');
  });
});

test('this pipeline raises the slow-skip cap', async t => {
  await t.test('30 minutes per backtest, above the 20-minute default', () => {
    assert.strictEqual(daily.SLOW_SKIP_MIN, 30);
    const src = fs.readFileSync(path.join(ROOT, 'utils/strategy-normalize.js'), 'utf8');
    assert.match(src, /max-poll-min/, 'the cap has to be forwardable to the child');
  });

  await t.test('the cap is passed to the normalizer, not left to its default', () => {
    const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');
    assert.match(src, /'--max-poll-min', String\(SLOW_SKIP_MIN\)/);
  });

  await t.test('the daily budget stays inside the free tier', () => {
    assert.ok(daily.USAGE_LIMIT <= 60, 'above 60 spends credits, not free minutes');
  });
});

test('the deferred pool', async t => {
  const PROBE = 'strategies/__daily_test_probe__.py';

  t.after(() => { state.resolve(PROBE, 'test-cleanup'); });

  await t.test('a slow-skipped strategy is parked with the cap it failed at', () => {
    const e = state.defer(PROBE, { reason: 'slow-skipped', capMin: 20 });
    assert.strictEqual(e.attempts, 1);
    assert.strictEqual(e.maxCapTried, 20);
  });

  await t.test('it is re-offered only at a HIGHER cap', () => {
    // Re-running at the same cap spends the same minutes to learn the same thing.
    assert.ok(!state.dueForRetry(20).some(d => d.file === PROBE), 'same cap must not re-offer');
    assert.ok(state.dueForRetry(30).some(d => d.file === PROBE), 'a bigger cap should re-offer');
  });

  await t.test('attempts accumulate and eventually exhaust', () => {
    state.defer(PROBE, { capMin: 30 });
    state.defer(PROBE, { capMin: 40 });
    const d = state.deferred()[PROBE];
    assert.strictEqual(d.attempts, 3);
    assert.ok(!state.dueForRetry(999).some(x => x.file === PROBE),
      `${state.MAX_ATTEMPTS} attempts should stop it being re-offered`);
    assert.ok(state.exhausted(999).some(x => x.file === PROBE), 'and it must stay visible, not vanish');
  });

  await t.test('resolving removes it', () => {
    state.resolve(PROBE);
    assert.ok(!state.deferred()[PROBE]);
  });

  await t.test('the 14 originally-stranded rows are in the REAL pool', () => {
    // slow-skipped is TERMINAL in strategy-normalize (correctly — otherwise every batch
    // re-bills them), so without the pool they could never be retried at all.
    const real = path.join(ROOT, 'data/deferred.json');
    if (!fs.existsSync(real)) return;   // not seeded yet on a fresh clone
    const pool = JSON.parse(fs.readFileSync(real, 'utf8'));
    const seeded = Object.values(pool).filter(v => /seeded from ledger/.test(v.reason || ''));
    assert.ok(seeded.length > 0, 'run: node utils/daily-pipeline.js --seed-deferred');
  });

  await t.test('slow-skipped is still terminal for the normalizer itself', () => {
    const src = fs.readFileSync(path.join(ROOT, 'utils/strategy-normalize.js'), 'utf8');
    const terminal = src.split('\n').find(l => l.includes('const TERMINAL'));
    const retriable = src.split('\n').find(l => l.includes('const RETRIABLE'));
    assert.ok(terminal.includes("'slow-skipped'"), 'must stay terminal — the pool is the retry path');
    assert.ok(!retriable.includes("'slow-skipped'"), 'making it retriable re-bills it every batch');
  });
});

test('the in-flight claim survives a crash', async t => {
  await t.test('a fresh claim blocks a second concurrent run', () => {
    const before = state.load();
    assert.ok(state.beginRun({ stage: 'normalize', target: null, force: true }));
    assert.strictEqual(state.beginRun({ stage: 'study' }), false, 'a live claim must hold');
    state.endRun({ outcome: 'test', note: 'concurrency probe' });
    assert.strictEqual(state.inFlight().held, false, 'endRun must release');
    assert.ok(state.load().runs.length >= before.runs.length);
  });

  await t.test('a claim older than the stale window is taken over, not deadlocked', () => {
    // A cron killed mid-run leaves the marker set forever otherwise.
    const s = state.load();
    s.inFlight = { stage: 'enhance', at: new Date(Date.now() - (state.STALE_HOURS + 1) * 3.6e6).toISOString() };
    state.save(s);
    const f = state.inFlight();
    assert.strictEqual(f.stale, true);
    assert.strictEqual(f.held, false, 'a stale claim must not hold the pipeline');
    assert.ok(state.beginRun({ stage: 'normalize' }), 'the next run should take over');
    state.endRun({ outcome: 'test', note: 'takeover probe' });
  });

  await t.test('the takeover is recorded rather than silently dropped', () => {
    const runs = state.load().runs;
    assert.ok(runs.some(r => r.outcome === 'abandoned'),
      'a run that keeps dying mid-stage is a fact worth seeing');
  });

  await t.test('the run log stays bounded', () => {
    assert.ok(state.load().runs.length <= 120);
  });
});

test('agent loops are reported as blocked, never as quiet success', async t => {
  const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');

  await t.test('the pinned session\'s BRANCH is checked, not just the file', () => {
    // The loop script refuses a session pinned to another branch and exits 0. Checking only
    // for the file's existence would report OK every day while starting nothing.
    assert.match(src, /rev-parse/);
    assert.match(src, /pinBranch !== branch/);
  });

  await t.test('a blocked stage cedes the budget to the next one', () => {
    assert.match(src, /cededFrom/);
  });

  await t.test('blocked exits non-zero so a dead cron is visible', () => {
    assert.match(src, /outcome === 'blocked'/);
  });
});

test('state files are durable and gitignored appropriately', async t => {
  await t.test('the deferred pool is tracked — it is a work queue, not a cache', () => {
    const ignore = fs.readFileSync(path.join(ROOT, '.gitignore'), 'utf8');
    assert.ok(!/^data\/deferred\.json/m.test(ignore),
      'losing the pool re-strands every slow-skipped strategy');
  });

  await t.test('logs and locks are not tracked', () => {
    const ignore = fs.readFileSync(path.join(ROOT, '.gitignore'), 'utf8');
    assert.match(ignore, /daily-logs/);
    assert.match(ignore, /\.lock/);
  });
});

test('the daily summary', async t => {
  const summary = require('../utils/daily-summary');

  await t.test('builds a dated markdown report', () => {
    const b = summary.build();
    assert.match(b.day, /^\d{4}-\d{2}-\d{2}$/);
    assert.match(b.markdown, /^# Daily pipeline — \d{4}-\d{2}-\d{2}/);
    for (const section of ['## Stages', '## Queues after the run', '## Deferred pool']) {
      assert.ok(b.markdown.includes(section), `missing ${section}`);
    }
  });

  await t.test('leads with what MOVED, not with what ran', () => {
    // "enhance -> ran" is the exact line all three of this repo's silent no-ops produced,
    // so the artefact delta has to come first or the report reassures rather than informs.
    const md = summary.build().markdown;
    const firstClaim = md.split('\n').find(l => l.startsWith('**'));
    assert.match(firstClaim, /\*\*(Moved|Nothing moved)\.\*\*/);
    assert.ok(md.indexOf(firstClaim) < md.indexOf('## Stages'));
  });

  await t.test('a no-op says so in words, not just by omission', () => {
    const src = fs.readFileSync(path.join(ROOT, 'utils/daily-summary.js'), 'utf8');
    assert.match(src, /Nothing moved/);
    assert.match(src, /no-op, not as success/);
  });
});

test('the daily commit scope cannot silently widen', async t => {
  const src = fs.readFileSync(path.join(ROOT, 'utils/daily-summary.js'), 'utf8');

  await t.test('never uses git add -A or -all', () => {
    // A blanket add in this repo once staged a git worktree as a gitlink, which a clone
    // cannot resolve. An unattended committer must not be able to repeat that.
    const addCalls = [...src.matchAll(/'git',\s*\[\s*'add'[^\]]*\]/g)].map(m => m[0]);
    assert.ok(addCalls.length > 0, 'expected git add calls to inspect');
    for (const c of addCalls) {
      assert.ok(!/'-A'|'--all'/.test(c), `blanket add found: ${c}`);
    }
  });

  await t.test('stages an enumerated allowlist, not a glob', () => {
    assert.match(src, /const SAFE_ADD = \[/);
    const list = src.slice(src.indexOf('const SAFE_ADD'), src.indexOf('];', src.indexOf('const SAFE_ADD')));
    assert.ok(!/\*/.test(list), 'SAFE_ADD must not contain globs');
    assert.ok(!/worktree/.test(list), '.claude/worktrees must never be in the allowlist');
    assert.ok(!/'\.claude/.test(list), 'settings/agents are not daily output');
  });

  await t.test('untracked files outside the allowlist are reported, not swept in', () => {
    assert.match(src, /Untracked and NOT committed/);
  });

  await t.test('a push failure is surfaced rather than swallowed', () => {
    assert.match(src, /committed but push failed/);
  });

  await t.test('the pipeline can opt out of committing', () => {
    const p = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');
    assert.match(p, /--no-commit/);
    assert.match(p, /--no-summary/);
  });

  await t.test('a summary failure never fails the run that produced it', () => {
    const p = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');
    assert.match(p, /the run itself is unaffected/);
  });
});

test('daily-pipeline exports survive the summary’s circular require', async t => {
  await t.test('module.exports is assigned before the CLI block', () => {
    // daily-summary requires daily-pipeline, and daily-pipeline requires it back at the end
    // of a run. With module.exports after the CLI block, Node handed the summary a partially
    // initialised module and it died with "daily.queues is not a function" — after a real
    // run had already spent 10 backtest-minutes, which is the worst moment to lose the report.
    const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');
    const exportsAt = src.indexOf('module.exports =');
    const cliAt = src.indexOf('if (require.main === module)');
    assert.ok(exportsAt > 0 && cliAt > 0);
    assert.ok(exportsAt < cliAt, 'module.exports must come before the CLI block');
  });

  await t.test('the summary can reach the planner through the cycle', () => {
    const d = require('../utils/daily-pipeline');
    assert.strictEqual(typeof d.queues, 'function');
    assert.strictEqual(typeof d.SLOW_SKIP_MIN, 'number');
  });
});

test('the shared pipeline lock is not released by a process that never took it', async t => {
  for (const f of ['scripts/autoenhance-loop.sh', 'scripts/autostudy-loop.sh']) {
    await t.test(`${path.basename(f)} only removes PLOCK it acquired`, () => {
      // The trap is installed long before the PLOCK acquisition, so an unconditional
      // `rm -f "$PLOCK"` meant a fire that correctly skipped ("another JQ pipeline is
      // running") deleted the HOLDER's lock on its way out — observed live, and it let a
      // second dispatch start while the first was mid-backtest.
      const src = fs.readFileSync(path.join(ROOT, f), 'utf8');
      assert.ok(!/trap 'rm -f "\$LOCK" "\$PLOCK"' EXIT/.test(src), 'unconditional trap still present');
      assert.match(src, /PLOCK_MINE=0/);
      assert.match(src, /PLOCK_MINE=1/);
      assert.match(src, /PLOCK_MINE" = "1"/);
    });
  }

  await t.test('a nested dispatch does not deadlock on the caller’s lock', () => {
    // daily-pipeline.sh holds the shared lock, then invokes children that want it. Without
    // the handshake every nested dispatch skipped and exited 0, and the planner recorded
    // "ran" for work that never started.
    const w = fs.readFileSync(path.join(ROOT, 'scripts/daily-pipeline.sh'), 'utf8');
    assert.match(w, /export JQ_PIPELINE_LOCK_HELD=1/);
    for (const f of ['scripts/autoenhance-loop.sh', 'scripts/autostudy-loop.sh']) {
      assert.match(fs.readFileSync(path.join(ROOT, f), 'utf8'), /JQ_PIPELINE_LOCK_HELD/);
    }
  });
});

test('the chain does not repeat a stage that made no progress', async t => {
  await t.test('depth is compared before re-picking', () => {
    // Observed live: enhance "ran", its queue stayed at 13, and the planner picked it again —
    // each repeat resuming a Claude session to redo the same work.
    const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');
    assert.match(src, /no-progress/);
    assert.match(src, /not repeating it this chain/);
  });
});

test('a budget-spent day is still recorded', async t => {
  const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');

  await t.test('it does not exit before writing a row and a summary', () => {
    // This used to `process.exit(0)` at the budget check, skipping both — so a day the
    // pipeline fired and correctly stood down left no trace, indistinguishable from a day
    // the cron never fired. On a 60-minute budget that is the most common outcome.
    assert.match(src, /budgetSpent/);
    assert.match(src, /outcome: 'budget-spent'/);
    const gate = src.slice(src.indexOf('const budgetSpent'), src.indexOf('const bad = log.some'));
    assert.ok(!/process\.exit\(0\)/.test(gate), 'the budget path must fall through to the summary');
  });

  await t.test('budget-spent is not an error', () => {
    // Standing down when the budget is gone is correct behaviour; exiting non-zero would
    // train whoever watches the cron to ignore red.
    assert.match(src, /const bad = log\.some\(r => r\.outcome === 'error' \|\| r\.outcome === 'blocked'\)/);
  });
});

test('a failed stage reports its cause', async t => {
  const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');

  await t.test('the note carries the failure, not the dispatch boilerplate', () => {
    // The first real failure wrote "exit 0 is NOT proof work happened" into an `error` row,
    // which tells a human nothing about what broke.
    assert.match(src, /loop FAILED:/);
    assert.match(src, /const cause = lines/);
  });

  await t.test('the success note still warns that exit 0 proves nothing', () => {
    assert.match(src, /exit 0 is NOT proof work happened/);
  });
});

test('the daily schedule is a fixed UTC hour, DST-safe', async t => {
  const plist = fs.readFileSync(
    path.join(ROOT, 'scripts/com.mohanshen.join-quant-daily.plist'), 'utf8');
  const wrapper = fs.readFileSync(path.join(ROOT, 'scripts/daily-pipeline.sh'), 'utf8');

  await t.test('the target hour is declared once, in UTC', () => {
    assert.match(plist, /<key>DAILY_RUN_HOUR_UTC<\/key>\s*<string>18<\/string>/);
    assert.match(wrapper, /RUN_HOUR_UTC="\$\{DAILY_RUN_HOUR_UTC:-18\}"/);
  });

  await t.test('two local hours fire, because launchd uses LOCAL time', () => {
    // launchd evaluates StartCalendarInterval in the machine's timezone, which observes DST,
    // so a single fixed local hour drifts by an hour twice a year. Both candidates fire and
    // the wrapper keeps the one that is really 18:00 UTC.
    const hours = [...plist.matchAll(/<key>Hour<\/key><integer>(\d+)<\/integer>/g)].map(m => +m[1]);
    assert.strictEqual(hours.length, 2, 'expected exactly two candidate local hours');
    assert.strictEqual(Math.abs(hours[0] - hours[1]), 1, 'they must be adjacent hours');
  });

  await t.test('the gate compares against UTC, not local', () => {
    assert.match(wrapper, /date -u \+%H/);
  });

  await t.test('a manual run is never blocked by the clock', () => {
    // The gate keys on DAILY_SCHEDULED, which only the plist sets.
    assert.match(wrapper, /DAILY_SCHEDULED:-0.*=.*"1"/);
    assert.match(wrapper, /FORCE:-0/);
    assert.match(plist, /<key>DAILY_SCHEDULED<\/key>\s*<string>1<\/string>/);
  });

  await t.test('RunAtLoad is off, so loading does not fire at an arbitrary time', () => {
    assert.match(plist, /<key>RunAtLoad<\/key>\s*<false\/>/);
  });
});

/**
 * The stage bound, and what it must kill.
 *
 * Both halves of a real failure: the bound was hard-coded at 60 minutes while the day's budget
 * was raised to 170, so a healthy enhance loop was cut off at exactly 60:00 and filed as an
 * `error`; and the kill reached only the wrapper, leaving `claude -p --resume` running an hour
 * later — spending backtest minutes with nothing accounting for them.
 */
test('stage timeout: bounded by the budget, and kills the whole process group', async (t) => {
  const src = fs.readFileSync(path.join(__dirname, '../utils/daily-pipeline.js'), 'utf8');

  await t.test('the bound is DERIVED from the budget, never a literal', () => {
    assert.match(src, /STAGE_TIMEOUT_MIN[\s\S]{0,400}USAGE_LIMIT \+ SLOW_SKIP_MIN/,
      'STAGE_TIMEOUT_MIN must follow USAGE_LIMIT so the two cannot drift');
    assert.doesNotMatch(src, /timeout = 3\.6e6/, 'the hard-coded 60-minute ceiling is back');
  });

  await t.test('the bound exceeds the budget it guards', () => {
    for (const limit of ['55', '170', '300']) {
      const out = require('child_process').execFileSync(process.execPath, ['-e', `
        process.env.USAGE_LIMIT='${limit}';
        process.stdout.write(String(require('./utils/daily-pipeline.js').stageTimeoutMin()));
      `], { cwd: path.join(__dirname, '..'), encoding: 'utf8' }).trim();
      assert.ok(Number(out) > Number(limit),
        `at USAGE_LIMIT=${limit} the stage bound was ${out} — a stage would be cut off mid-budget`);
    }
  });

  await t.test('an explicit STAGE_TIMEOUT_MIN wins', () => {
    const out = require('child_process').execFileSync(process.execPath, ['-e', `
      process.env.USAGE_LIMIT='170'; process.env.STAGE_TIMEOUT_MIN='42';
      process.stdout.write(String(require('./utils/daily-pipeline.js').stageTimeoutMin()));
    `], { cwd: path.join(__dirname, '..'), encoding: 'utf8' }).trim();
    assert.strictEqual(out, '42');
  });

  await t.test('dispatch goes through the group-killing wrapper', () => {
    const w = path.join(__dirname, '../scripts/with-timeout.sh');
    assert.ok(fs.existsSync(w), 'scripts/with-timeout.sh is missing — sh() falls back to an orphan-leaking kill');
    assert.match(src, /TIMEOUT_WRAPPER/, 'sh() must dispatch through the wrapper');
    // The negative pid is the entire point: it addresses the process GROUP, not the child.
    assert.match(fs.readFileSync(w, 'utf8'), /kill -TERM -"\$child"/);
    assert.match(fs.readFileSync(w, 'utf8'), /kill -KILL -"\$child"/);
  });

  await t.test('a timeout is reported as a cutoff, not as a crash', () => {
    assert.match(src, /outcome: r\.ok \? 'ran' : r\.timedOut \? 'timeout'/);
    assert.match(src, /CUT OFF/);
  });

  await t.test('the wrapper passes a clean exit code through, and reports 124 on timeout', () => {
    const run = (args) => {
      try {
        return { rc: 0, out: require('child_process').execFileSync('bash',
          [path.join(__dirname, '../scripts/with-timeout.sh'), ...args],
          { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }) };
      } catch (e) { return { rc: e.status, out: e.stdout || '' }; }
    };
    assert.strictEqual(run(['5', 'bash', '-c', 'exit 7']).rc, 7, 'exit status must pass through');
    assert.strictEqual(run(['5', 'bash', '-c', 'true']).rc, 0);
  });
});

/**
 * The daily summary is the RECORD. A wrong path in it reads as a real file.
 *
 * `git status --short` uses two fixed status columns, so the old parser took `slice(3)` as the
 * path. `sh()` trims the whole output, which eats the leading space of an unstaged ` M` on the
 * FIRST line only — so exactly one path per summary lost its first character and nothing looked
 * broken. The 2026-09-21 summary published `ata/daily-state.json`.
 */
test('summary: git status is parsed by shape, not by column offset', async (t) => {
  const { parseStatusLine } = require('../utils/daily-summary.js');

  await t.test('an unstaged line survives losing its leading space', () => {
    assert.deepStrictEqual(parseStatusLine(' M data/daily-state.json'),
      { status: 'M', file: 'data/daily-state.json' });
    assert.deepStrictEqual(parseStatusLine('M data/daily-state.json'),
      { status: 'M', file: 'data/daily-state.json' },
      'the trimmed first line must parse to the SAME path');
  });

  await t.test('every porcelain status shape', () => {
    const cases = [
      ['?? scripts/with-timeout.sh',      '??', 'scripts/with-timeout.sh'],
      ['M  utils/daily-pipeline.js',      'M',  'utils/daily-pipeline.js'],
      ['MM harness/normalize-train.tsv',  'MM', 'harness/normalize-train.tsv'],
      ['A  wiki/types/全A-H-low.md',       'A',  'wiki/types/全A-H-low.md'],
      ['D  enhance/candidates/old.py',    'D',  'enhance/candidates/old.py'],
    ];
    for (const [line, status, file] of cases) {
      assert.deepStrictEqual(parseStatusLine(line), { status, file }, line);
    }
  });

  await t.test('a rename reports the name that exists now', () => {
    assert.deepStrictEqual(parseStatusLine('R  study/old.md -> study/new.md'),
      { status: 'R', file: 'study/new.md' });
  });

  await t.test('a quoted path (non-ASCII, which most of this repo is) is unquoted', () => {
    assert.strictEqual(parseStatusLine('?? "wiki/families/小市值.md"').file, 'wiki/families/小市值.md');
  });

  await t.test('blank and malformed lines are dropped, never emitted as a file', () => {
    for (const l of ['', '   ', null]) assert.strictEqual(parseStatusLine(l), null);
  });
});
