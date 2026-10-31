/**
 * The ledger schema, and the two hazards that made it worth centralising.
 *
 * `harness/normalize-*.tsv` is what every family §3 table, the integration bar, the /run-family
 * exit gate and champion resolution are computed from — and until 2026-10-17 **eight files
 * hard-coded numeric column indices** into it. A column inserted anywhere but the end would have
 * silently turned `sharpe` into `annual_pct` in all of them, with nothing failing.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

// The ledger is gitignored, so these tests must not assume it exists; and they must never write
// to the real one.
const ROOT = path.join(__dirname, '..');
const ledger = require('../utils/ledger');

test('ledger schema', async (t) => {
  await t.test('COLS matches the live header, or one of them is wrong', () => {
    const header = ledger.header();
    if (!header.length) { t.diagnostic('no ledger on disk — skipping header comparison'); return; }
    assert.deepStrictEqual(header, ledger.COLS,
      'the writer (strategy-normalize.js) and utils/ledger.js have diverged. This is the ONE ' +
      'place that fails when a column is added — fix both in the same commit.');
  });

  await t.test('IDX is derived from COLS, so the two cannot disagree', () => {
    ledger.COLS.forEach((name, i) => assert.strictEqual(ledger.IDX[name], i));
    assert.strictEqual(Object.keys(ledger.IDX).length, ledger.COLS.length);
  });

  await t.test('the epoch column is last, which is what makes appending safe', () => {
    assert.strictEqual(ledger.COLS[ledger.COLS.length - 1], 'epoch');
  });

  await t.test('a blank or headerless line parses to null rather than a ghost row', () => {
    assert.strictEqual(ledger.parse(''), null);
    assert.strictEqual(ledger.parse('\n'), null);
    assert.strictEqual(ledger.parse('\tx\ty'), null, 'no sourceFile means no row');
  });

  await t.test('numeric columns are null when unparseable, never NaN', () => {
    // NaN propagates through every comparison as false, which makes a MISSING measurement look
    // like a losing one — the bug class the integration bar is most exposed to.
    const r = ledger.parse('strategies/x.py\tpid\ttitle\tnormalized\t\t\t\t\t\t\t\t\t\t');
    for (const n of ['days', 'total_pct', 'annual_pct', 'sharpe', 'maxdd_pct', 'objective']) {
      assert.strictEqual(r[n], null, `${n} must be null, got ${r[n]}`);
      assert.ok(!Number.isNaN(r[n]), `${n} must never be NaN`);
    }
  });

  await t.test("objective 'DQ' survives as the string — it is a verdict, not a number", () => {
    const cols = [...ledger.COLS].fill('');
    cols[ledger.IDX.sourceFile] = 'strategies/x.py';
    cols[ledger.IDX.status] = 'normalized';
    cols[ledger.IDX.objective] = 'DQ';
    assert.strictEqual(ledger.parse(cols.join('\t')).objective, 'DQ');
  });

  await t.test('an unstamped row reports epoch null, not a default', () => {
    // measurementValid(null) and measurementValid('2') are different questions. family-queue
    // applies its own '2' default; the schema must not pre-empt that.
    const cols = [...ledger.COLS].fill('');
    cols[ledger.IDX.sourceFile] = 'strategies/x.py';
    cols[ledger.IDX.status] = 'normalized';
    assert.strictEqual(ledger.parse(cols.join('\t')).epoch, null);
  });

  await t.test('JQ_LEDGER redirects the file, so a test can never read the real one', () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'jq-ledger-'));
    const f = path.join(tmp, 'probe.tsv');
    fs.writeFileSync(f, ledger.COLS.join('\t') + '\n' +
      ['strategies/probe.py', 'pid', 'T', 'normalized', '', '', '10',
       '5', '4', '1.23', '2', '0.02', 'pass', '8'].join('\t') + '\n');
    const prev = process.env.JQ_LEDGER;
    process.env.JQ_LEDGER = f;
    try {
      const rows = ledger.normalized();
      assert.strictEqual(rows.length, 1);
      assert.strictEqual(rows[0].sharpe, 1.23);
      assert.strictEqual(rows[0].epoch, '8');
    } finally {
      if (prev === undefined) delete process.env.JQ_LEDGER; else process.env.JQ_LEDGER = prev;
    }
  });

  await t.test('no util reads the ledger by numeric index any more', () => {
    // The whole point. A new reader that re-introduces c[9] gets caught here rather than by a
    // wrong number in a family table months later.
    const offenders = [];
    for (const f of fs.readdirSync(path.join(ROOT, 'utils')).filter(x => x.endsWith('.js'))) {
      if (f === 'ledger.js') continue;
      const src = fs.readFileSync(path.join(ROOT, 'utils', f), 'utf8');
      if (!/normalize-(train|val|holdout)\.tsv|JQ_LEDGER|require\('\.\/ledger'\)/.test(src)) continue;
      // c[0]..c[13] applied to a split('\t') row. Allowed: ledger.IDX.<name>.
      const lines = src.split('\n');
      lines.forEach((line, i) => {
        if (/^\s*(\/\/|\*)/.test(line)) return;               // prose, including the index tables
        if (/\bc\[\d+\]|\bcol\[\d+\]/.test(line)) offenders.push(`${f}:${i + 1}  ${line.trim()}`);
      });
    }
    assert.deepStrictEqual(offenders, [],
      'read the ledger through utils/ledger.js (r.sharpe) or a named index (r.raw[ledger.IDX.sharpe])');
  });
});

/**
 * ⚠ The guard rule's own audit had a blind spot.
 *
 * CLAUDE.md says "every entry point in utils/ needs a require.main guard", and the audit behind it
 * looked for files reading `process.argv`. `consumption-seed.js` takes no arguments, so it was
 * missed — and on 2026-10-17 a bare `require()` of it appended 82 duplicate rows to the tracked
 * `data/consumption.tsv`, the ledger the VAL and OOS budgets are computed from.
 */
test('every util that writes on load is guarded', async (t) => {
  const dir = path.join(ROOT, 'utils');
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.js'));

  await t.test('a module with top-level script code declares a require.main guard', () => {
    const unguarded = [];
    for (const f of files) {
      const src = fs.readFileSync(path.join(dir, f), 'utf8');
      if (/require\.main\s*(===|!==)\s*module/.test(src)) continue;
      // Top-level statement (column 0) that is neither a declaration nor a comment: this file
      // DOES something on require.
      const runs = src.split('\n').some(l =>
        /^(for|while|if)\s*\(/.test(l) ||
        /^(fs|c)\.(write|append|record)/.test(l) ||
        /^[a-zA-Z_$][\w$]*\(/.test(l) && !/^(module|require|function|exports)/.test(l));
      if (runs) unguarded.push(f);
    }
    assert.deepStrictEqual(unguarded, [],
      'these run on require(). Add `if (require.main !== module) { module.exports = {}; return; }` ' +
      'or wrap the body — a bare require() of consumption-seed.js once wrote 82 rows into the ' +
      'tracked budget ledger.');
  });

  await t.test('consumption-seed specifically is inert on require', () => {
    const src = fs.readFileSync(path.join(dir, 'consumption-seed.js'), 'utf8');
    assert.match(src, /if \(require\.main !== module\)/);
    assert.ok(!/One-off \(idempotent\)/.test(src),
      'it is NOT idempotent — its dedup key comes from a re-minted postId');
  });
});

/**
 * The frontmatter reader, likewise: ten files carried their own copy and four of the ten trimmed.
 * Not a live bug (the wiki has zero trailing-whitespace values, and every uncompensated call site
 * feeds the result to parseFloat/parseInt/.match), but `family:` and `universe:` ARE compared by
 * equality across those files, so one hand-edited page would make a family vanish from one reader
 * and not another.
 */
test('one frontmatter reader', async (t) => {
  const { field, link } = require('../utils/frontmatter');

  await t.test('it trims, and returns the empty string for a missing field', () => {
    assert.strictEqual(field('family:  X  \n', 'family'), 'X');
    assert.strictEqual(field('a: 1\n', 'family'), '', 'never undefined — callers chain .match()');
    assert.strictEqual(field('', 'family'), '');
    assert.strictEqual(field(null, 'family'), '');
  });

  await t.test('it reads the first match anywhere in the document, not only the --- block', () => {
    // kb-stub.js stamps a `normalized:` block further down the page and readers reach into it.
    assert.strictEqual(field('---\na: 1\n---\n\nbody\nepoch: 8\n', 'epoch'), '8');
    assert.strictEqual(field('family: A\nfamily: B\n', 'family'), 'A');
  });

  await t.test('link() strips the wiki brackets', () => {
    assert.strictEqual(link('parent: [[ETF动量]]\n', 'parent'), 'ETF动量');
    assert.strictEqual(link('parent:\n', 'parent'), '');
  });

  await t.test('no util re-declares the regex locally', () => {
    const dir = path.join(ROOT, 'utils');
    const offenders = [];
    for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.js'))) {
      if (f === 'frontmatter.js') continue;
      const src = fs.readFileSync(path.join(dir, f), 'utf8');
      src.split('\n').forEach((line, i) => {
        if (/^\s*(\/\/|\*)/.test(line)) return;
        // The READER shape specifically: a capture of the value. `setFmKey` in
        // wiki-family-build.js uses `^${key}:.*$` with no capture — it is a WRITER, and
        // matching it here was a false positive.
        if (/new RegExp\(`\^\$\{\w+\}:\\\\s\*\(\.\*\)\$`/.test(line)) {
          offenders.push(`${f}:${i + 1}`);
        }
      });
    }
    assert.deepStrictEqual(offenders, [],
      "use require('./frontmatter').field — ten local copies is how the .trim() diverged");
  });
});

/**
 * ⚠⚠ The automated daily commit must never take a human's working copy.
 *
 * `commitAndPush` ran a bare `git add -u`, which stages EVERY modified tracked file. On
 * 2026-10-17 a run whose only stage reported `budget-spent` — it started nothing at all — swept up
 * 19 mid-edit source files across utils/ and backtest/, plus CLAUDE.md, and pushed them as
 * "daily: 2026-10-17 pipeline run". The commit message described none of it.
 */
test('the daily commit is scoped to pipeline output', async (t) => {
  const src = fs.readFileSync(path.join(ROOT, 'utils/daily-summary.js'), 'utf8');

  await t.test('git add -u is bounded by a pathspec, never bare', () => {
    assert.ok(!/sh\('git', \['add', '-u'\]\)/.test(src),
      "a bare `git add -u` stages the whole working tree — pass `--` and the SAFE_ADD paths");
    // `...tracked`, not `...paths`: the pathspec is filtered to what git knows, because
    // `git add -u` on an unknown path is fatal. See the pathspec test below.
    assert.match(src, /\['add', '-u', '--', \.\.\.tracked\]/);
  });

  await t.test('SAFE_ADD covers what a run produces and nothing a human edits', () => {
    // Read the REAL array, not the source text — an apostrophe in one of its own comments
    // ("The INTEGRATE layer's durable state") broke the regex that used to parse it here.
    const entries = require('../utils/daily-summary').SAFE_ADD;
    // The surfaces a run writes. `harness` (the ledger a normalize pass appends to) and `study`
    // (the findings a research round writes) were reachable only via the unscoped add.
    for (const must of ['docs/daily', 'wiki', 'harness', 'study', 'data/consumption.tsv',
                        'data/promoted.tsv', 'validated_strategies']) {
      assert.ok(entries.includes(must), `SAFE_ADD must include ${must}`);
    }
    // And must NOT reach code or configuration.
    for (const never of ['utils', 'tests', 'scripts', '.claude', 'CLAUDE.md', 'config', '.', '']) {
      assert.ok(!entries.includes(never),
        `SAFE_ADD must never include ${never || '(empty)'} — that is a working copy, not output`);
    }
  });

  await t.test('files left behind are reported, not silently dropped', () => {
    assert.match(src, /Left uncommitted \(not pipeline output/);
  });
});

/**
 * ⚠⚠⚠ "No VAL row" is not "nobody has done this step yet".
 *
 * The `integrate-blocked` reopening (2026-10-17) treated it as a research to-do and reopened four
 * families. Checked against what those families had recorded, it was wrong for 4 of 4 — every one
 * had already declined to spend its one validation, with the reason in §4. A dispatch would have
 * told a session to "finalize on VAL — one run" and spent an irreversible per-(family, epoch)
 * resource on a book its own round judged unworthy. Caught with the run live; nothing was spent.
 */
/**
 * ⚠⚠ The COVERAGE GUARD: a champion resting on a minority of a family is not a champion.
 *
 * Measured near-miss, 2026-10-18. Epoch 9 moved TRAIN to 2024, invalidating every row, and the
 * daily chain re-planned to `research` after its first normalize batch — research outranks
 * normalize by design. The family it picked was 小市值 with **37 members, exactly ONE measured on
 * the active bench**, so championSharpe 5.77 was a 1-of-37 sample presented as the family's
 * champion, and the next budget rollover would have gone to experiments built on it.
 *
 * ⚠ A fixed fraction would be the WRONG rule: partial coverage is normal (打板短线 runs at 9
 * measured of 25 assigned, because 15 have no row and two are terminal failures), so a 50% bar
 * would block that family forever. The rule is a comparison with no magic number — more members
 * awaiting measurement than measured means the champion is provisional.
 */
test('family-queue holds a family whose champion rests on a minority', async (t) => {
  const fq = require('../utils/family-queue');
  const src = fs.readFileSync(path.join(ROOT, 'utils/family-queue.js'), 'utf8');

  await t.test('the rule is a comparison, not a hard-coded fraction', () => {
    assert.match(src, /awaiting > validCount/, 'the guard must compare pending against measured');
    // A literal threshold is what this guard exists to avoid.
    assert.doesNotMatch(src, /awaiting\s*\/\s*(validCount|assigned)\s*[<>]/,
      'a ratio test would block families whose partial coverage is normal and permanent');
    assert.doesNotMatch(src, /MIN_COVERAGE|COVERAGE_PCT|0\.5\s*\*\s*assigned/,
      'no coverage constant — the comparison is the rule');
  });

  await t.test('a held family is excluded from `due` but still visible in `all`', () => {
    const q = fq.build();
    const held = q.all.filter(f => f.reason === 'awaiting-measurement');
    for (const f of held) {
      assert.ok(f.awaitingMeasurement > f.validMembers,
        `${f.family} is held but ${f.awaitingMeasurement} awaiting is not > ${f.validMembers} measured`);
      assert.strictEqual(f.championProvisional, true);
      assert.match(f.note, /awaiting measurement/, 'a held family must say why');
      assert.ok(!q.due.some(d => d.family === f.family),
        `${f.family} is provisional and must not be dispatched`);
    }
    // ...and the guard must not simply hide everything: a family with no pending members at all
    // can never be held by it.
    for (const f of q.all) {
      if ((f.awaitingMeasurement || 0) === 0) {
        assert.notStrictEqual(f.reason, 'awaiting-measurement',
          `${f.family} has nothing pending, so it cannot be awaiting measurement`);
      }
    }
  });

  await t.test('it overrides every due-making reason, never-researched included', () => {
    // Dispatching a never-researched family whose members are all unmeasured is the worst case,
    // not an exception to it — so the guard is first in the reason chain.
    const chain = src.slice(src.indexOf('const reason = provisional'), src.indexOf("      : 'done';") + 20);
    assert.match(chain, /provisional \? 'awaiting-measurement'/);
    assert.ok(chain.indexOf('awaiting-measurement') < chain.indexOf('never-researched'),
      'the guard must precede never-researched in the chain');
  });

  await t.test('it cannot deadlock on permanently unrunnable members', () => {
    // A compile-error / incompatible row is TERMINAL, so such a member leaves the pending queue
    // and never counts toward the block. The guard is therefore self-clearing: only the normalize
    // stage can satisfy it, and it always can.
    assert.match(src, /TERMINAL, so those\n  \/\/ members leave the pending queue/,
      'the self-clearing property must be stated where it can be read');
  });
});

test('a reasoned VAL decline is not reopened', async (t) => {
  const el = require('../utils/integrate-eligible');
  const harness = require('../utils/harness-config');
  const rows = el.all();

  await t.test('a candidate below the validate gate is never a research to-do', () => {
    // Derived, so it needs no field and cannot fall out of sync.
    for (const r of rows) {
      if (r.eligible || r.val?.has) continue;
      const s = r.candidate?.sharpe;
      if (s == null || harness.stageGate('validate', s)) continue;
      // Same refinement as below: what must never happen is a RESEARCH dispatch to spend a
      // validation on a candidate that cannot clear the gate. A `normalize` block is a different
      // statement — it says the candidate has no current measurement at all.
      assert.notStrictEqual(r.owner, 'research',
        `${r.family}: candidate sharpe ${s} fails the validate gate — there is nothing worth ` +
        'the family\'s one validation, so this must not be dispatched');
    }
  });

  await t.test('a declared valDeclined blocks with owner none, and carries a basis', () => {
    const dir = process.env.JQ_FAMILIES_DIR || path.join(ROOT, 'wiki/families');
    const { field } = require('../utils/frontmatter');
    let declared = 0;
    for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.md'))) {
      const t2 = fs.readFileSync(path.join(dir, f), 'utf8');
      if (!field(t2, 'valDeclined')) continue;
      declared++;
      const fam = f.replace(/\.md$/, '');
      assert.ok(field(t2, 'valDeclinedBasis').length > 40,
        `${fam}: valDeclined needs a basis saying WHY and what would change it`);
      const r = el.assess(fam);
      if (r.val && r.val.has) continue;   // a later VAL makes the field moot
      // ⚠ The invariant is that the RESEARCH LOOP is not re-dispatched to spend a validation the
      // family already declined — `family-queue` reopens only `research`-owned blocks, so that is
      // the owner that must never appear. It is NOT "owner is always none": epoch 9 moved the
      // windows, so these families now block one gate EARLIER, at `normalize`, for want of any
      // member measured on the active bench. That block is both correct and more fundamental, and
      // it is not a VAL dispatch.
      assert.notStrictEqual(r.owner, 'research',
        `${fam}: a declared decline must never be reopened for research (owner ${r.owner})`);
      assert.ok(['none', 'normalize', 'human'].includes(r.owner),
        `${fam}: unexpected owner ${r.owner} for a declared decline`);
    }
    // ⚠ A deliberate REOPEN may legitimately take the active-decline count to zero (human
    // decision, 2026-10-26: every declined family was reopened at epoch 9), so `declared >= 1`
    // would fail on a correct repo. The invariant that survives is that a VAL decision is never
    // DISCARDED — a reopen renames the keys and keeps the reasoning, because the clearing
    // condition it names still binds whoever runs the VAL. Without this, a reopen could quietly
    // delete the basis and the next round would re-derive it from nothing.
    let reopened = 0;
    for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.md'))) {
      const t2 = fs.readFileSync(path.join(dir, f), 'utf8');
      if (!field(t2, 'valReopened')) continue;
      reopened++;
      const fam = f.replace(/\.md$/, '');
      assert.ok(field(t2, 'valDeclinedPrior'),
        `${fam}: reopened but the prior decline's epoch was discarded`);
      assert.ok(field(t2, 'valDeclinedPriorBasis').length > 40,
        `${fam}: reopened but the prior decline's REASONING was discarded — it still binds the run`);
      assert.ok(field(t2, 'valReopenedBasis').length > 40,
        `${fam}: a reopen needs a basis saying who decided it and what it does NOT grant`);
      // ⚠ A reopened page MAY carry a fresh active decline, and 七星高照 does. That is the
      // mechanism working, not a conflict: the human reopen PERMITS a validation, the loop then
      // looks again and may decline on its own new evidence (its basis says "DECLINED AGAIN at
      // epoch 9, on a measurement taken this round — not inherited"). My first version of this
      // assertion demanded `valDeclined === ''` on any reopened page and failed the moment the
      // loop did the right thing — the test encoded "a reopen is final", which was never the rule.
      //
      // What must hold is that a NEW decline is its own judgement, not a silent restoration of the
      // old one: it carries its own basis, and it is recorded at an epoch no older than the reopen.
      const fresh = field(t2, 'valDeclined');
      if (fresh) {
        assert.ok(field(t2, 'valDeclinedBasis').length > 40,
          `${fam}: re-declined after a reopen without its own basis`);
        assert.ok(parseInt(fresh, 10) >= parseInt(field(t2, 'valReopened'), 10),
          `${fam}: re-declined at epoch ${fresh}, older than the reopen ` +
          `(${field(t2, 'valReopened')}) — that is the old decline restored, not a new judgement`);
      }
    }
    assert.ok(declared + reopened >= 1,
      'expected at least one recorded VAL decision (declined or reopened)');
  });

  await t.test('family-queue reopens nothing whose block is a decision', () => {
    const q = require('../utils/family-queue').build();
    const reopened = q.due.filter(f => f.reason === 'integrate-blocked').map(f => f.family);
    for (const fam of reopened) {
      assert.strictEqual(el.assess(fam).owner, 'research',
        `${fam} was reopened but its block is not research-owned`);
    }
  });
});

/**
 * /run-family is an ORCHESTRATOR, and until 2026-10-17 it did not say so.
 *
 * The skill drew the five roles (generator A/B -> gatekeeper -> executor -> recorder) in its loop
 * diagram but never told the session to dispatch them, so a session played all five itself and
 * 5 of the 16 agent contracts in .claude/agents/ were referenced from nowhere. Measured that day:
 * only post-screener, integrate-merger and family-assign were reachable at all.
 */
test('run-family dispatches its five roles', async (t) => {
  const skill = fs.readFileSync(path.join(ROOT, '.claude/skills/run-family/SKILL.md'), 'utf8');
  const ROLES = ['family-understand', 'family-improve', 'family-gatekeeper',
                 'family-executor', 'family-recorder'];

  await t.test('every role is named as a subagent_type in the skill', () => {
    for (const r of ROLES) {
      assert.ok(skill.includes(r), `${r} must be dispatched by name, not merely implied`);
    }
    assert.match(skill, /subagent_type/, 'the skill has to say how to dispatch them');
  });

  await t.test('each role has a contract on disk', () => {
    for (const r of ROLES) {
      const f = path.join(ROOT, '.claude/agents', `${r}.md`);
      assert.ok(fs.existsSync(f), `${r} is dispatched but has no contract`);
      const c = fs.readFileSync(f, 'utf8');
      assert.match(c, /ephemeral subagent/i,
        `${r} must state that it is spawned fresh and returns — the handoff is on disk`);
    }
  });

  await t.test('exactly one executor at a time, stated as a rule', () => {
    // The completion signal is the account-wide running count; concurrent runs have returned
    // identical metrics for different strategies.
    assert.match(skill, /one at a time, never parallel|ONE executor|one backtest at a time/i);
    assert.match(skill, /CONCURRENT-STOP/);
  });

  await t.test('the generators are the only fan-out, and are marked as such', () => {
    assert.match(skill, /Dispatch 1 and 2 in the same message|run concurrently/i);
  });

  await t.test('VAL and the budget are NOT delegated', () => {
    assert.match(skill, /Delegate VAL/);
    assert.match(skill, /valDeclined/, 'declining the VAL is the orchestrator\'s call too');
    for (const r of ROLES) {
      const c = fs.readFileSync(path.join(ROOT, '.claude/agents', `${r}.md`), 'utf8');
      assert.ok(!/--window val\b/.test(c),
        `${r} must not carry VAL authority — one validation per (family, epoch)`);
    }
  });
});

/**
 * Contract/step consistency — the review of 2026-10-17.
 *
 * Making /run-family dispatch its five roles exposed four things the contracts said that the code
 * did not do, plus one silent substitution in the planner.
 */
test('agent contracts match what each step actually does', async (t) => {
  const AG = path.join(ROOT, '.claude/agents');
  const read = f => fs.readFileSync(path.join(AG, f), 'utf8');

  await t.test('no subagent claims it can dispatch another subagent', () => {
    // family-gatekeeper said "hand it to the executor", which a subagent cannot do. It NAMES the
    // next entry; the orchestrator spawns it.
    for (const f of fs.readdirSync(AG).filter(x => x.endsWith('.md'))) {
      const s = read(f);
      if (/RETIRED/.test(s.slice(0, 1200))) continue;          // history, not live
      // Line-by-line, skipping the line that QUOTES the old wording to explain why it is wrong —
      // family-gatekeeper says: 'this line used to read "hand it to the executor"'. A test that
      // cannot tell an instruction from a citation of a retracted one is not measuring anything.
      const offending = s.split('\n').filter(l =>
        /hand it to the (executor|recorder|gatekeeper)/i.test(l) &&
        !/used to read|cannot|is not a thing|instead of/i.test(l));
      assert.deepStrictEqual(offending, [],
        `${f}: a subagent cannot dispatch a subagent — return to the orchestrator instead`);
    }
  });

  await t.test('the executor does not teach the superseded "log is unreadable" rule', () => {
    // /algorithm/backtest/log fails only in its BARE form; utils/backtest-log.js reads it.
    const s = read('family-executor.md');
    assert.ok(!/backtest log is not retrievable/.test(s));
    assert.match(s, /backtest log IS retrievable/);
    assert.ok(fs.existsSync(path.join(ROOT, 'utils/backtest-log.js')),
      'the correction depends on this wrapper existing');
  });

  await t.test('integrate-merger teaches the ACTIVE bar, not epoch 7\'s', () => {
    const s = read('integrate-merger.md');
    const basis = require('../utils/harness-config').integrateBar().basis;   // e.g. perYearSharpe
    // The contract states it as prose ("PER-YEAR SHARPE DOMINATION"), not as the config
    // identifier, so compare letters-only and case-insensitively.
    const flat = x => x.toLowerCase().replace(/[^a-z]/g, '');
    assert.ok(flat(s).includes(flat(basis)),
      `the contract must name the active basis (${basis}) — it teaches the bar an agent applies`);
    // Epoch 7's maximin may be cited as history, but must be labelled invalidated.
    if (/worst[- ]year/i.test(s)) {
      assert.match(s, /invalidated/i, 'a worst-year figure must be marked as the epoch-7 reading');
    }
  });

  await t.test('a read-only generator is never told to write', () => {
    for (const f of ['family-understand.md', 'family-improve.md']) {
      const s = read(f);
      const tools = (s.match(/^tools:\s*(.*)$/m) || [])[1] || '';
      assert.ok(!/\bWrite\b|\bEdit\b/.test(tools), `${f} should stay read-only`);
    }
  });

  await t.test('the retired stages are refused, not silently substituted', () => {
    const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');
    // The refusal...
    assert.match(src, /RETIRED stage/, 'enhance/study invoke skills that no longer exist');
    // ...and the bug that made it unreachable: indexOf(-1) + slice(-1) === ['discover'], so
    // `--stage enhance` printed "-> ENHANCE" and ran DISCOVER.
    assert.match(src, /const i = PRIORITY\.indexOf\(p\.stage\)/);
    assert.match(src, /i >= 0 \? PRIORITY\.slice\(i\) : \[p\.stage, \.\.\.PRIORITY\]/);
    for (const skill of ['run-enhance', 'run-study']) {
      assert.ok(!fs.existsSync(path.join(ROOT, '.claude/skills', skill)),
        `${skill} exists again — then the refusal above is now wrong`);
    }
  });

  await t.test('every orphaned contract is marked RETIRED', () => {
    const live = new Set(['family-understand', 'family-improve', 'family-gatekeeper',
                          'family-executor', 'family-recorder', 'family-assign',
                          'integrate-merger', 'post-screener']);
    for (const f of fs.readdirSync(AG).filter(x => x.endsWith('.md'))) {
      const name = f.replace(/\.md$/, '');
      if (live.has(name)) continue;
      assert.match(read(f).slice(0, 1500), /RETIRED/,
        `${name} is referenced by nothing — mark it, so its stale epoch facts are not read as current`);
    }
  });
});

/**
 * ⚠⚠ A hang spends wall clock, not backtest minutes — so no budget gate can see it.
 *
 * `jq-http`'s direct transport had a 30s `req.setTimeout` from the start; the CDP transport,
 * which is the DEFAULT, had none. `page.evaluate` is not an action with a Playwright timeout, so a
 * `fetch()` inside the page that never settled hung the call forever. Measured: the discover stage
 * sat for 4h25m on 2026-10-16 and was killed only by STAGE_TIMEOUT_MIN=255, losing the day's
 * remaining budget; it repeated on 2026-10-17 and was 61 minutes in when this was found.
 */
test('both HTTP transports are bounded', async (t) => {
  const src = fs.readFileSync(path.join(ROOT, 'utils/jq-http.js'), 'utf8');

  await t.test('the CDP path aborts in-page AND races outside it', () => {
    assert.match(src, /AbortController/, 'the browser must stop its own request');
    assert.match(src, /Promise\.race/,
      'an evaluate can hang for reasons the page cannot abort — a wedged renderer, a closed tab');
    assert.match(src, /CDP_TIMEOUT_MS/);
  });

  await t.test('the two transports agree on how long is too long', () => {
    const cdp = (src.match(/JQ_HTTP_TIMEOUT_MS[\s\S]{0,120}?:\s*(\d+)/) || [])[1];
    const direct = (src.match(/req\.setTimeout\((\d+)/) || [])[1];
    assert.ok(cdp && direct, 'both transports must state a timeout');
    assert.strictEqual(cdp, direct,
      'a default that differs by transport means the bound depends on which one happened to run');
  });

  await t.test('a timeout REJECTS, so jqText can fall back to the bounded transport', () => {
    // jqText drops the tab and retries direct when an evaluate throws. Returning a sentinel
    // instead would make a hang look like an empty result — the Pipeline-1 failure shape.
    assert.match(src, /reject\(new Error\(`timeout after/);
    assert.match(src, /catch \{[\s\S]{0,200}viaDirect/);
  });
});

/**
 * Two bugs the FIRST real run of the scoped commit exposed.
 */
test('the scoped daily commit survives its own pathspec', async (t) => {
  const src = fs.readFileSync(path.join(ROOT, 'utils/daily-summary.js'), 'utf8');

  await t.test('git add -u is filtered to paths git actually knows', () => {
    // `git add -u -- <path>` is FATAL when the pathspec matches nothing in the index, and takes
    // the whole commit with it. data/integrate-sessions is in SAFE_ADD and is an empty directory
    // until a universe has had a round, so the first scoped run wrote no commit at all.
    // fs.existsSync is not the test — an empty dir passes it and is still unknown to git.
    assert.match(src, /ls-files/, 'filter the -u pathspec by what is tracked');
    assert.match(src, /tracked\.length \? sh\('git', \['add', '-u', '--', \.\.\.tracked\]\)/);
  });

  await t.test('discover/fetch state is committed, not just named as left behind', () => {
    const list = require('../utils/daily-summary').SAFE_ADD;
    for (const f of ['data/content-hashes.json', 'data/fetch-manifest.json',
                     'data/notifications.json']) {
      assert.ok(list.includes(f), `${f} is pipeline output — the unscoped add was carrying it`);
    }
  });

  await t.test('every SAFE_ADD entry that exists is either tracked or creatable', () => {
    // A guard against the next empty-directory entry: if a path exists but git knows nothing in
    // it, the -u filter must be what saves the commit, not luck.
    const list = require('../utils/daily-summary').SAFE_ADD;
    for (const p2 of list) {
      assert.ok(!p2.startsWith('/') && !p2.includes('..'), `${p2} must be repo-relative`);
    }
  });
});

/**
 * ⚠⚠⚠ The `discover` stage was running the `normalize` stage's work.
 *
 * `strategy-daily.js` ends by calling `normalize-daily.normalizeNew()`, which runs BACKTESTS, and
 * `runDiscover` invoked it bare. So discover measured strategies outside the budget accounting,
 * the deferred pool and the retry-at-a-higher-cap rule, bounded only by STAGE_TIMEOUT_MIN:
 * **4h25m on 2026-10-16** (killed by that timeout, losing the day's remaining budget) and 61
 * minutes on 2026-10-17. Neither moved `used`, because JQ settles duration.used only when a run
 * TERMINATES — so no budget gate could see it.
 */
test('discover fetches; normalize measures', async (t) => {
  const pipeline = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');
  const daily = fs.readFileSync(path.join(ROOT, 'utils/strategy-daily.js'), 'utf8');

  await t.test('the discover stage never runs backtests', () => {
    assert.match(pipeline, /'utils\/strategy-daily\.js', '--no-normalize'/,
      'without the flag, discover calls normalizeNew() and spends hours measuring');
  });

  await t.test('--no-normalize still ENQUEUES, or the day\'s fetches are stranded', () => {
    // normalizeNew() is the only thing that appends a day's fetches to pending-normalize.json —
    // the enqueue is its first two lines and the backtests follow in the same call. Skipping it
    // entirely loses them: nothing else writes that file except the backfill and the sync.
    assert.match(daily, /enqueueOnly/,
      'the flag must mean "enqueue but do not measure", never "skip"');
    const nd = require('../utils/normalize-daily');
    assert.strictEqual(typeof nd.enqueueOnly, 'function');
    assert.strictEqual(typeof nd.normalizeNew, 'function');
  });

  await t.test('enqueueOnly is a pure queue write — it cannot reach a backtest', () => {
    const src = fs.readFileSync(path.join(ROOT, 'utils/normalize-daily.js'), 'utf8');
    const body = (src.match(/function enqueueOnly\([\s\S]*?\n\}/) || [''])[0];
    assert.ok(body, 'enqueueOnly must exist');
    for (const forbidden of ['execFileSync', 'strategy-normalize', 'post-backtest', 'cdpAlive']) {
      assert.ok(!body.includes(forbidden),
        `enqueueOnly must not reach ${forbidden} — measuring is the normalize stage's job`);
    }
    assert.match(body, /savePending/);
  });

  await t.test('the absent notifier is checked, not stack-traced into the log', () => {
    // The binary is missing on this machine, and `stdio: 'inherit'` printed a full
    // `Cannot find module` trace into the daily log — which daily-pipeline's cause-extractor then
    // reported as the REASON discover failed, while the real cause was the normalize sub-phase.
    assert.match(daily, /fs\.existsSync\(NOTIFY_BIN\)/);
    assert.ok(!/stdio: \['pipe', 'inherit', 'inherit'\]/.test(daily),
      "the notifier's stderr must not be inherited into our log");
  });
});

/**
 * ⚠⚠⚠ An entry point that opens jq-http and never closes it NEVER EXITS.
 *
 * jq-http holds a Playwright CDP connection to the logged-in Chrome. Eight modules call
 * `jq.close()` — each inside its OWN `require.main === module` block. `strategy-daily.js` requires
 * `strategy-discover` and `strategy-fetch` as MODULES, so those blocks never ran and nothing closed
 * the socket; the open `localhost:*->localhost:9225` kept Node's event loop alive and the process
 * sat idle after finishing its work, until STAGE_TIMEOUT_MIN=255 killed it.
 *
 * This was the SECOND independent cause of the discover stage running for hours. Fixing only the
 * first (the normalize sub-phase) did not fix the symptom: the work completed in ~3 minutes and the
 * process did not exit. With both fixed, the stage exits 0 in 14 seconds.
 */
test('an entry point that opens jq-http closes it', async (t) => {
  const dir = path.join(ROOT, 'utils');
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.js'));
  const srcOf = {};
  for (const f of files) srcOf[f] = fs.readFileSync(path.join(dir, f), 'utf8');

  const requiresJq = f => /require\('\.\/jq-http'\)/.test(srcOf[f] || '');
  const localRequires = f =>
    [...(srcOf[f] || '').matchAll(/require\('\.\/([a-z0-9-]+)'\)/g)].map(m => `${m[1]}.js`);

  await t.test('every CLI that CALLS jq-http closes it', () => {
    // ⚠ Narrowed deliberately. A "requires it, one level deep" rule flagged nine files and four
    // were false positives — integrate-eligible, component-scan, type-integrate-check and
    // series-rekey require backtest-series only to read local JSON, open no connection, and were
    // verified to exit 0 in under a second. "Could reach jq-http" is not statically decidable;
    // "makes a call itself" is, and it is the precise form of the hazard.
    const CALLS = /\b(jqJson|jqText|jqPostJson)\s*\(/;
    const offenders = [];
    for (const f of files) {
      const src = srcOf[f];
      if (!/require\.main\s*===\s*module/.test(src)) continue;      // not an entry point
      if (!CALLS.test(src)) continue;                                // makes no call of its own
      if (/jq-http'\)\.close\(\)|jq\.close\(\)/.test(src)) continue;
      offenders.push(f);
    }
    assert.deepStrictEqual(offenders, [],
      'these call jq-http and never close it, so the process hangs at exit after doing all its ' +
      'work — add `.finally(() => require("./jq-http").close())` to the CLI block');
  });

  await t.test('the TRANSITIVE case is named, because no static rule catches it', () => {
    // strategy-daily opens nothing itself: it requires strategy-discover and strategy-fetch as
    // MODULES, so their own CLI close-blocks never run. That is the shape that cost 4h25m, and it
    // is invisible to the check above — so it is asserted by name.
    assert.match(srcOf['strategy-daily.js'], /require\('\.\/jq-http'\)\.close\(\)/,
      'an orchestrator must close what its callees opened');
  });

  await t.test('strategy-daily specifically closes it, on both paths', () => {
    const src = srcOf['strategy-daily.js'];
    assert.match(src, /\.finally\(/, 'must close on the error path too, not just on success');
    assert.match(src, /require\('\.\/jq-http'\)\.close\(\)/);
    // A `process.exit()` in the catch would skip the finally and re-introduce the hang... or
    // rather mask it by killing the process. Either way the close must be reachable.
    assert.ok(!/catch\(e => \{ console\.error\(e\); process\.exit\(1\); \}\)/.test(src),
      'process.exit in the catch bypasses the finally — set process.exitCode instead');
  });
});

/**
 * ⚠⚠⚠ The normalize queue's depth was fiction, and the funnel decides on it.
 *
 * Measured 2026-10-17: the queue reported **24** while **9** entries were runnable. 5 could never
 * resolve (1 carried a `strategies/` prefix, 4 were re-minted ids matching no file) and 10 were
 * already finished — 9 of them `normalized` at epoch 6, which epoch 8 accepts. So the planner
 * picked `normalize` twice on an empty queue, the normalizer exited in 6 seconds having started no
 * backtest, and it was recorded as `RAN  21 queued`. The stage itself was never broken: given real
 * work it measured 9 strategies and moved `used`.
 */
test('the normalize queue reports runnable work', async (t) => {
  const daily = require('../utils/daily-pipeline');
  const pipeSrc = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');

  await t.test('total counts runnable; listed counts entries', () => {
    const q = daily.queues().normalize;
    assert.strictEqual(typeof q.total, 'number');
    assert.strictEqual(typeof q.listed, 'number');
    assert.ok(Array.isArray(q.runnable));
    assert.strictEqual(q.total, q.runnable.length);
    assert.ok(q.total <= q.listed, 'runnable can never exceed listed');
  });

  await t.test('depth() — what picks the stage — uses the runnable count', () => {
    // `depth(stage, q)` returns q.normalize.total for normalize. If that were `listed`, the
    // funnel would spend its turn on entries nothing can run.
    assert.match(pipeSrc, /stage === 'normalize' \? q\.normalize\.total/);
  });

  await t.test('a prefixed PENDING entry is stripped, not silently dropped', () => {
    // strategy-normalize --files matches bare basenames against the directory listing
    // (`asked.filter(f => onDisk.has(f))`), so `strategies/x.py` matched nothing. Only the retry
    // list was being stripped.
    assert.match(pipeSrc, /\.\.\.q\.normalize\.pending\.map\(base\)/);
  });

  await t.test('nothing runnable is reported as such, with the listed count', () => {
    assert.match(pipeSrc, /nothing runnable \(\$\{q\.normalize\.listed\} listed/);
    assert.match(pipeSrc, /normalize-sync/, 'the note must say what cleans them');
  });
});

test('normalize-sync can clean what it could not reach', async (t) => {
  const sync = require('../utils/normalize-sync');
  const src = fs.readFileSync(path.join(ROOT, 'utils/normalize-sync.js'), 'utf8');

  await t.test('the prune resolves an entry to a basename before looking it up', () => {
    // It was `entry.endsWith('.py') ? 'strategies/'+entry : null` — a bare id gave null and the
    // entry was KEPT forever; a prefixed entry became strategies/strategies/x.py and was also
    // kept. Those are exactly the entries that most needed pruning.
    assert.ok(!/entry\.endsWith\('\.py'\) \? `strategies\/\$\{entry\}` : null/.test(src));
    assert.match(src, /basenameOf/);
  });

  await t.test('an entry that resolves to no file is reported, not kept', () => {
    const r = sync.sync({ dry: true });
    assert.ok(Array.isArray(r.unresolvable),
      'unresolvable entries must be surfaced — they inflate the depth that picks the stage');
  });

  await t.test('the deferred pool drops entries the ledger says are finished', () => {
    // dueForRetry filters on attempts and cap only, never on whether the strategy has since
    // succeeded, so the pool re-offered 9 `normalized` strategies every day forever.
    const r = sync.sync({ dry: true });
    assert.ok(Array.isArray(r.resolvedDeferred));
    assert.match(src, /RETRIABLE/,
      'only a cap-related status stays retriable — a bigger cap cannot change compile-error');
    for (const bad of ['normalized', 'compile-error', 'no-trades']) {
      assert.ok(!new RegExp(`RETRIABLE = new Set\\(\\[[^\\]]*'${bad}'`).test(src),
        `${bad} must not be treated as retriable`);
    }
  });
});

/**
 * The three hand-offs the funnel depends on, asserted as behaviour rather than as prose.
 *
 *   new member assigned   -> research reopens
 *   new best variant      -> integrate reopens
 *   new promoted candidate-> surfaces as OOS-ready (reported, NEVER dispatched)
 */
test('each stage reopens the next', async (t) => {
  await t.test('a new member changes the family hash, which is what reopens research', () => {
    // staleFor compares the stamped memberHash with the current one. memberState hashes the
    // sorted `family:` members read from wiki/strategies/*.md, so ASSIGNING a strategy changes
    // the hash — that is the whole trigger, and it is why `assign` ranks above `normalize`.
    const c = require('../utils/consumption');
    const src = fs.readFileSync(path.join(ROOT, 'utils/consumption.js'), 'utf8');
    assert.match(src, /last\.memberHash !== now\.hash/, 'staleness must compare membership');
    assert.match(src, /new member\(s\) since last/);
    const st = c.staleForResearch('红利低频');
    assert.ok(typeof st.stale === 'boolean' && st.now && typeof st.now.hash === 'string');
  });

  await t.test('integrate dispositions on the CANDIDATE, so a new best variant reopens it', () => {
    // Keyed by family, one failed merge would retire a lineage forever.
    const src = fs.readFileSync(path.join(ROOT, 'utils/integrate-queue.js'), 'utf8');
    assert.match(src, /const id = a\.champion\.sourceFile/);
    assert.match(src, /promoted\.isRejected\(universe, id\)/);
    assert.match(src, /a NEW best variant reopens it/);
  });

  await t.test('a promoted candidate surfaces as OOS-ready, with its state', () => {
    const rows = require('../utils/oos-queue').build();
    assert.ok(Array.isArray(rows));
    for (const r of rows) {
      assert.ok(['ready', 'tested', 'blocked'].includes(r.state), `bad state ${r.state}`);
      assert.ok(r.candidateId, 'a row with no candidate cannot be acted on');
      assert.ok(r.why && r.why.length > 5, 'every state must say why');
    }
    // Ready first — it is the only actionable state.
    const idx = rows.map(r => r.state === 'ready' ? 0 : 1);
    assert.deepStrictEqual(idx, [...idx].sort(), 'ready rows must lead');
  });

  await t.test('a candidate below the stage gate is FLAGGED, not silently offered', () => {
    // The budget says a test is PERMITTED; it never says the candidate deserves one. And
    // integrate-eligible checks the VAL sharpe, not the champion's TRAIN sharpe — so a promoted
    // candidate can sit at 1.46 against a 1.5 gate (红利低频, live).
    const harness = require('../utils/harness-config');
    for (const r of require('../utils/oos-queue').build()) {
      if (r.sharpe == null || harness.stageGate('validate', r.sharpe)) continue;
      assert.ok((r.flags || []).some(f => /below the .* gate/.test(f)),
        `${r.candidateId} is sub-gate at sharpe ${r.sharpe} and carries no flag`);
    }
  });

  await t.test('oos is dispatchable, and the CEILING is what holds it', () => {
    // ⚠ Changed 2026-10-17 by user decision. This asserted that `oos` was absent from PRIORITY —
    // "spending the last clean surface is a decision, not a queue to drain". It is now a stage, so
    // the thing that must hold is no longer the absence of a queue but the ceiling in code:
    //   - `ready` requires untested AND within budget AND a pinned runnable artifact;
    //   - so when the bench's tests are spent, depth is 0 and the stage cannot be picked.
    const daily = require('../utils/daily-pipeline');
    const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');
    assert.match(src, /require\('\.\/oos-queue'\)/, 'the planner must name candidates');
    assert.strictEqual(daily.PRIORITY[0], 'oos');

    const rows = require('../utils/oos-queue').build();
    const budget = require('../utils/oos-budget');
    const spent = budget.testsOnThisBench().length;
    const cap = budget.policy().maxTestsPerEpoch;
    if (spent >= cap) {
      assert.strictEqual(daily.queues().oos.length, 0,
        'with the bench spent, the queue MUST be empty — that is the stop');
    }
    // No ready row may be one that was already tested, or that has no pinned artifact to run.
    for (const r of rows.filter(x => x.state === 'ready')) {
      assert.ok(r.runFile, `${r.candidateId} is ready with no pinned artifact — UNPINNED-STOP`);
      assert.ok(budget.check(r.candidateId).allowed, `${r.candidateId} is ready but over budget`);
    }
  });

  await t.test('the wrapper never sets a protection override', () => {
    const sh = fs.readFileSync(path.join(ROOT, 'scripts/run-oos.sh'), 'utf8');
    for (const env of ['JQ_ALLOW_OOS_OVERBUDGET=1', 'JQ_ALLOW_OOS_UNREADY=1']) {
      assert.ok(!new RegExp(`^\\s*(export\\s+)?${env.replace(/[=]/g, '=')}`, 'm').test(sh),
        `run-oos.sh must never set ${env} — overriding a protection stays the human's`);
    }
    // ⚠ It must NOT carry `--allow-oos` either: the wrapper dispatches a session that invokes
    // /run-oos, and the SKILL's step 3 owns the command. Asserting the flag here was asserting
    // something false about the design. What the wrapper owns is the hand-over — the candidate,
    // the pinned file to execute, and the --source-file that keeps the budget charging the book.
    assert.match(sh, /--source-file \$CANDIDATE/, 'the budget must charge the book, not the copy');
    assert.match(sh, /run this   : \$RUNFILE/, 'the session must be told which pinned file to run');
    assert.match(sh, /DECLARE THE EXPECTATION BEFORE THE NUMBER EXISTS/,
      'step 2 is the one step that cannot be recovered if skipped');
  });
});

/**
 * ⚠⚠⚠ The deferred pool re-offered entries the normalizer would always skip.
 *
 * A `slow-skipped` row is TERMINAL to `strategy-normalize.js`, so handing a deferred entry to
 * `--files` alone makes it skip the entry as already-done — at ANY cap. So the pool never retried
 * anything: it re-offered, the normalizer skipped, and `runNormalize` reported "0 deferred" because
 * it only counts newly-PARKED files. Visible in the 2026-10-17 log as
 * `normalize 0 runnable; 4 listed … (4 waiting for a higher cap)` — a higher cap would not have
 * helped, which made that line's wording wrong too.
 */
test('a deferred retry can actually run', async (t) => {
  const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');

  await t.test('a DUE retry counts as runnable work', () => {
    // dueForRetry(cap) already filtered on maxCapTried < cap, which is the right judge for a
    // retry; the ledger-terminal test is the right judge for a PENDING entry. Mixing them made
    // the pool permanently unrunnable.
    assert.match(src, /const dueRetry = new Set\(retry\.map\(r => r\.file\)\)/);
    assert.match(src, /runnable = all\.filter\(e => dueRetry\.has\(e\) \|\| isWork\(e\)\)/);
  });

  await t.test('the retry list gets --redo and the fresh list does NOT', () => {
    assert.match(src, /argsFor\(retryFiles, true\)/, 'retries need --redo to re-measure');
    assert.match(src, /argsFor\(freshFiles, false\)/,
      '--redo on a file with a current measurement re-bills a backtest to learn the same thing');
    assert.match(src, /\.\.\.\(redo \? \['--redo'\] : \[\]\)/);
  });

  await t.test('--redo stays scoped to an explicit --files list', () => {
    // strategy-normalize exits 2 on a bare --redo, because without the guard it re-bills the whole
    // 215-strategy library. Both invocations pass --files, so the guard is satisfied by shape.
    const n = fs.readFileSync(path.join(ROOT, 'utils/strategy-normalize.js'), 'utf8');
    assert.match(n, /--redo requires an explicit --files list/);
    assert.match(src, /'--files', list\.slice\(0, 40\)\.join\(','\)/);
  });

  await t.test('a due retry is never reported as dead', () => {
    assert.match(src, /if \(runnable\.includes\(e\) \|\| dueRetry\.has\(e\)\) return false;/);
    const q = require('../utils/daily-pipeline').queues().normalize;
    for (const r of q.retry) {
      assert.ok(!(q.dead || []).includes(r.file),
        `${r.file} is due for retry and must not be called dead`);
    }
  });
});

/**
 * Realizability: a FREE static flag at normalize time, never a gate.
 *
 * The question was whether to check realizability before normalize. It cannot be scored from
 * source — 大小盘轮动's R=2 took `liq-1` across three floors (31 JQ min) and the floor turned out to
 * remove ZERO names — and a pre-measurement reject must be a known fact, never a guess: one
 * guess-based screening rule discarded 287 of 549 strategies. Worse, the measurement is what
 * EXPOSES the problem: 7a1c225f's 100× unit bug was found by studying an already-measured book.
 * So the WARNING moves earlier; the decision does not.
 */
test('realizability flags are precise, and advisory', async (t) => {
  const rl = require('../utils/realizability-lint');
  const strategies = fs.readdirSync(path.join(ROOT, 'strategies')).filter(f => f.endsWith('.py'));

  await t.test('the three known unit-bug books are flagged, and only those', () => {
    const KNOWN = ['7a1c225f', '8dbd994c', '5e874b5b'];
    const flagged = strategies.filter(f =>
      rl.lintFile(`strategies/${f}`).some(r => r.id === 'tick-depth-x100'));
    assert.strictEqual(flagged.length, KNOWN.length,
      `expected exactly ${KNOWN.length} tick-depth-x100 files, got ${flagged.length}`);
    for (const k of KNOWN) {
      assert.ok(flagged.some(f => f.includes(k)), `${k} must be flagged`);
    }
  });

  await t.test('every pattern states a severity and a why', () => {
    for (const p of rl.PATTERNS) {
      assert.ok(['measured', 'info'].includes(p.severity), `${p.id}: bad severity`);
      assert.ok(p.why && p.why.length > 60, `${p.id}: a flag without a why is noise`);
      if (p.severity === 'measured') {
        assert.match(p.why, /MEASURED|q-e6|q-e8/,
          `${p.id}: 'measured' must cite the experiment that measured the cost`);
      }
    }
  });

  /**
   * ⚠⚠ The auction window MUST cover 9:26 — it is the pattern's own documented example.
   *
   * `call-auction-entry` was written for the 9:15–9:25 auction, but CLAUDE.md attributes
   * a30641fb's R=1 partly to "9:26 auction entry" — and the 9:15–9:25 regex reported
   * `0 of 1 file(s) flagged` on that very file. Found 2026-10-21 when 96fb1ca0 (竞价擒龙,
   * `run_daily(buy, '09:26')`) normalized at objective 7.8535 / sharpe 11.95, 3.7x the next book
   * on the bench, while the column a §3 reader weighs against such a score stayed silent.
   *
   * A flag that misses its own worked example is worse than no flag: it reads as evidence of
   * absence. This test pins both files so the window cannot be narrowed back.
   */
  await t.test('the auction window covers 9:26 — the documented R=1 entry', () => {
    for (const tag of ['a30641fb', '96fb1ca0']) {
      const f = strategies.find(x => x.includes(tag));
      assert.ok(f, `${tag} must still be in strategies/`);
      const ids = rl.lintFile(`strategies/${f}`).map(x => x.id);
      assert.ok(ids.includes('call-auction-entry'),
        `${tag} schedules an order at 9:26 and must be flagged; got [${ids.join(', ')}]`);
    }
  });

  /**
   * ⚠ SECONDS-PRECISION times, the same pattern's second false negative.
   *
   * `38ca196e` (一进二v3.0) schedules `run_daily(buy, '09:25:41')` and scored objective 5.2937 /
   * sharpe 11.48 — #3 on the epoch-9 bench — while a regex demanding the closing quote right
   * after the MINUTES could not see it. Seconds precision is not incidental: it is what you use
   * to time the auction, and every HH:MM:SS in the corpus clusters in 9:24–9:28 except two at
   * 09:30:00. So the most aggressively timed entries were exactly the ones the flag missed.
   */
  await t.test('the auction window reads HH:MM:SS, not just HH:MM', () => {
    const f = strategies.find(x => x.includes('38ca196e'));
    assert.ok(f, '38ca196e must still be in strategies/');
    const ids = rl.lintFile(`strategies/${f}`).map(x => x.id);
    assert.ok(ids.includes('call-auction-entry'),
      `a 09:25:41 entry must be flagged; got [${ids.join(', ')}]`);
  });

  await t.test('and STOPS at 9:29 — 9:30 is the ordinary open, implicated by nothing', () => {
    // 12 of the 20 files scheduling an order in 9:26–9:30 sit on 9:30 exactly, so including it
    // would roughly double the hits on no evidence. 9:26–9:29 is the gap between the auction
    // price publishing and continuous trading opening; 9:30 IS the open.
    const src = fs.readFileSync(path.join(ROOT, 'utils/realizability-lint.js'), 'utf8');
    assert.match(src, /1\[5-9\]\|2\[0-9\]/, 'the minute class must span 9:15-9:29');
    assert.ok(!/3\[0-9\]|\|30\)/.test(src.slice(src.indexOf("id: 'call-auction-entry'"),
                                                src.indexOf("id: 'depth-gated'"))),
      '9:30 must not be in the auction window');
  });

  await t.test('it stays PRECISE — a noisy flag teaches readers to skip the column', () => {
    // Measured 2026-10-17: 18 of 259 files. Re-measured 2026-10-21 after widening the auction
    // window to 9:29: 36 of 340 (0.106), of which call-auction-entry is 18, up from 2.
    // Two earlier attempts at a limit-up pattern hit 37 and
    // then 140, both dominated by code that AVOIDS limit-ups, and it was removed rather than
    // tuned a third time. If this ratio balloons, a pattern has gone loose.
    const n = strategies.filter(f => rl.lintFile(`strategies/${f}`).length).length;
    assert.ok(n / strategies.length < 0.25,
      `${n}/${strategies.length} flagged — too many for a "known pattern" signal to be trusted`);
  });

  await t.test('the removed pattern is documented, not silently dropped', () => {
    const src = fs.readFileSync(path.join(ROOT, 'utils/realizability-lint.js'), 'utf8');
    assert.match(src, /REMOVED: `limit-up-entry`/);
    assert.match(src, /140/, 'the second attempt\'s count is the evidence for dropping it');
    assert.ok(!rl.PATTERNS.some(p => p.id === 'limit-up-entry'));
  });

  await t.test('it is a reporter: no throw on junk, and NOT a gate', () => {
    assert.deepStrictEqual(rl.lint(''), []);
    assert.deepStrictEqual(rl.lint(null), []);
    assert.deepStrictEqual(rl.lintFile('does/not/exist.py'), []);
    // Nothing in the pipeline may consult it as a veto.
    for (const f of ['utils/daily-pipeline.js', 'utils/strategy-normalize.js',
                     'utils/integrate-eligible.js']) {
      const src = fs.readFileSync(path.join(ROOT, f), 'utf8');
      assert.ok(!/realizability-lint/.test(src),
        `${f} must not consult the lint — it reports, it does not decide`);
    }
  });

  await t.test('the flag is stamped where the NUMBER is created', () => {
    // Beside `normalized:` in the wiki stub, because that line feeds §3, wiki/types and champion
    // resolution — the reader who needs the caveat is looking at the table.
    const src = fs.readFileSync(path.join(ROOT, 'utils/kb-stub.js'), 'utf8');
    assert.match(src, /realizabilityFlags/);
    assert.match(src, /never a veto/);
  });
});

/**
 * ⚠⚠ The chain stops when the BUDGET is gone — not on the first stage that has a bad day.
 *
 * It used to break on `empty`, `error` and `blocked` as well, and at `maxStages = 6` with six
 * stages in PRIORITY. Each of those could end a day with minutes unspent; 2026-10-04 ended with
 * 124 unspent because a stalled stage broke the chain.
 */
test('the daily chain stops only for the budget, a lock, or an empty board', async (t) => {
  const src = fs.readFileSync(path.join(ROOT, 'utils/daily-pipeline.js'), 'utf8');

  await t.test('only a HELD claim ends the chain', () => {
    assert.ok(!/\['blocked', 'error', 'empty', 'held'\]\.includes\(r\.outcome\)\) break/.test(src),
      'empty/error/blocked must CEDE, as no-progress already does');
    assert.match(src, /if \(r\.outcome === 'held'\) break;/,
      'held is a lock — another run owns the in-flight claim, so proceeding double-spends');
  });

  await t.test('the retry loop is prevented by the no-progress guard, not by breaking', () => {
    // This is what makes ceding safe: a stage whose own run did not move its own queue is added
    // to `stalled` and skipped for the rest of the chain.
    assert.match(src, /const after = depth\(p\.stage, queues\(\)\)/);
    assert.match(src, /after >= before\[p\.stage\]/);
    assert.match(src, /stalled\.add\(p\.stage\)/);
  });

  /**
   * ⚠⚠ Progress is the stage's OWN delta, measured the moment it returns.
   *
   * It used to be deferred to the stage's NEXT pick and compared against the depth at its
   * previous pick — an interval that spans other stages, which in a FUNNEL legitimately add to
   * that queue. Measured on the 2026-10-17 18:00Z cron: assign drained 1→0 and was then read as
   * "queue still 2" because normalize had meanwhile produced two unassigned strategies; normalize
   * drained 2→0 and was read as "queue still 3" because discover had meanwhile admitted its 3
   * daily fetches. Both had done exactly their job, both were marked stalled, the chain reported
   * EXHAUSTED, and the day ended at **used=2 of 180 minutes** with 3 runnable strategies queued.
   */
  await t.test('a queue refilled by ANOTHER stage is not this stage failing', () => {
    const at = src.indexOf('const after = depth(p.stage, queues())');
    assert.ok(at > 0, 'the after-depth must be sampled');
    // It must be sampled AFTER execute() and BEFORE the loop comes round again, so that no other
    // stage can run in between. Those two anchors bracket it.
    const exec = src.indexOf('const r = execute(p, { dry })');
    assert.ok(exec > 0 && exec < at, 'the after-depth must be read AFTER the stage ran');
    // ...and the pre-depth must be the one recorded for THIS execution, not a prior pick.
    const pre = src.lastIndexOf('before[p.stage] = depth(p.stage, p.q)', exec);
    assert.ok(pre > 0 && pre < exec, 'the before-depth must be recorded just before execute');
    // The old deferred comparison must be gone, or both forms would coexist and the stale one
    // would keep stalling productive stages.
    assert.doesNotMatch(src, /depth\(p\.stage, p\.q\) >= before\[p\.stage\]/,
      'the next-pick comparison is the bug — it spans other stages feeding this queue');
  });

  await t.test('maxStages is a backstop, not the real bound', () => {
    const m = src.match(/function runChain\(\{ dry = false, maxStages = (\d+)/);
    assert.ok(m, 'runChain must declare maxStages');
    assert.ok(Number(m[1]) >= 20,
      `maxStages=${m[1]} is too low to let a draining stage finish — normalize takes 40 files a pass`);
  });

  await t.test('DISCOVER runs at most once per chain', () => {
    // It ADMITS work rather than consuming it, its own strategy-daily limit is 20 fetches per RUN
    // (raised from 3 on 2026-10-17), and it costs no backtest minutes — so an unbounded chain would
    // re-run it to maxStages and admit up to 800 in a day. The raise makes this brake the only
    // thing bounding the daily total, so it matters MORE than when the per-run cap was 3.
    assert.match(src, /if \(r\.stage === 'discover'\) stalled\.add\('discover'\)/);
  });

  await t.test('the budget gate is still the one that matters, and still exempts free stages', () => {
    assert.match(src, /used >= ceiling && !isFreeStage\(p\)/);
    assert.match(src, /outcome: 'budget-spent'/);
  });

  await t.test('an empty board still stops — that is not stopping early', () => {
    assert.match(src, /outcome: 'exhausted'/);
  });
});

/**
 * ⚠⚠ The phantom probe: JQ lists a running entry with no backtest behind it.
 *
 * Cost two sessions ~2 hours each on 2026-10-17. `pollUntilComplete` watches only
 * `statistics.running.length`, so a phantom keeps the count above baseline forever, `emptyStreak`
 * never accumulates, and the run spins to MAX_POLL_MS and reports a slow-skip. Both times
 * `duration.used` never moved (JQ bills nothing) and the entry released only at the 120-minute
 * stale threshold. The elapsed counter is no signal — the confirmed phantom incremented for 121
 * minutes. The buildList is, and it is free.
 */
test('the poller detects a phantom instead of burning to the cap', async (t) => {
  const post = fs.readFileSync(path.join(ROOT, 'utils/strategy-post-backtest.js'), 'utf8');
  const norm = fs.readFileSync(path.join(ROOT, 'utils/strategy-normalize.js'), 'utf8');

  await t.test('the probe asks the buildList, which is what distinguishes it', () => {
    assert.match(post, /algorithmHasBacktest/);
    assert.match(post, /backtest\/buildList\?algorithmId=/);
  });

  await t.test('all three conditions are required, so a healthy run is never cancelled', () => {
    // past the grace period AND JQ still claims a run above baseline AND no backtest exists.
    assert.match(post, /Date\.now\(\) - start > PHANTOM_GRACE_MS/);
    assert.match(post, /st\.runningCount > baseline/);
    assert.match(post, /has === false/);
  });

  await t.test('it is confirmed twice and an unreadable probe is never a phantom', () => {
    assert.match(post, /\+\+phantomStreak >= 2/, 'one bad render must not cancel a run');
    assert.match(post, /has === true[\s\S]{0,80}phantomStreak = 0/, 'never latch');
    // algorithmHasBacktest returns null on a failed read, and null is neither true nor false here.
    assert.match(post, /`null` is never treated as a phantom/);
  });

  /**
   * ⚠⚠ The verdict is THREE-VALUED, and this is the test that would have caught the bug.
   *
   * The first probe tested `/backtestId[=":\s]+[a-f0-9]{32}/` over the response body. Measured
   * against the live endpoint on 2026-10-17, that is right on the two pages that render and
   * DANGEROUSLY wrong on the third: `buildList` answers an algorithm it cannot read with a
   * 60-byte JSON error carrying no 32-hex id, which read as `false` = phantom. Two of those 30s
   * apart would have cancelled a healthy backtest — worse than the phantom it was built for.
   *
   * The fixtures below are reduced from real responses, each verified live:
   *   fresh algorithm, never run  22,883 bytes, 0 rows, shell field present but blank
   *   algorithm with >= 1 run     26,199 bytes, >= 1 `backtest-tr` row
   *   not readable                     60 bytes, `{"status":"2","code":"20000","msg":"系统繁忙…"}`
   */
  await t.test('an unreadable buildList is null, not "no backtest"', () => {
    const { classifyBuildList } = require(path.join(ROOT, 'utils/strategy-post-backtest.js'));

    const SHELL = '<form name="AlgorithmModel"><input type="hidden" id="backtestId" value="';
    const fresh = `${SHELL}" /><tbody></tbody>`;                    // blank value: no run yet
    const withRun = `${SHELL}10d73b95cdb8f1713f502ed28d622464" />` +
      '<tbody><tr _backtestId="de544f9667e7d284ae6cf3b368ca014e" class="backtest-tr"></tr></tbody>';
    const busy = '{"status":"2","code":"20000","msg":"系统繁忙，请稍后重试","reason":""}';

    assert.equal(classifyBuildList(withRun), true, 'a rendered page with a row has a backtest');
    assert.equal(classifyBuildList(fresh), false, 'a rendered page with no row IS the phantom');
    assert.equal(classifyBuildList(busy), null,
      'the 系统繁忙 error must never read as "no backtest" — it would cancel a healthy run');

    // Everything that is not a rendered buildList is unknown, never a verdict.
    for (const other of ['', null, undefined, '<html><body>登录</body></html>',
                         '当前地区暂不支持访问', '{"data":{}}']) {
      assert.equal(classifyBuildList(other), null, `must be unknown: ${String(other).slice(0, 24)}`);
    }

    // And the rule may not move back inside page.evaluate, where it cannot be tested at all.
    assert.match(post, /function classifyBuildList/);
    assert.match(post, /classifyBuildList\(body\)/);
  });

  /**
   * ⚠⚠ The INVERSE of the phantom: our run has FINISHED and JQ keeps listing it.
   *
   * Found 2026-10-18 by the human noticing the server showed 「完成」 while the poller was 33
   * minutes into polling. `pollUntilComplete`'s primary signal is the account-wide `running`
   * COUNT, and `running[].id` is a backtestId that never matches our algorithmId — so the count
   * cannot be attributed to us. A finished run JQ leaves in the list pins the count above baseline
   * forever: `emptyStreak` never accumulates, the run burns to MAX_POLL_MS and is reported
   * `slow-skipped`, while its completed result sits on the server. Measured: all five newest
   * algorithms (1245..1249) read 完成 while `statistics.running` still listed one.
   *
   * The other existing signal could not save it: `resultsRendered()` is forced to false whenever
   * `runningCount > baseline`, which is precisely this case.
   */
  await t.test('a finished run JQ still lists is detected via the buildList row state', () => {
    const { parseBuildList } = require(path.join(ROOT, 'utils/strategy-post-backtest.js'));
    const SHELL = '<form name="AlgorithmModel"><input type="hidden" id="backtestId" value="';

    // Reduced from the real response for 这是一个简单的策略-1249, the run this was found on.
    const doneRow = `${SHELL}4fbd66d5" /><tbody>` +
      '<tr _backtestId="4fbd66d56a8970a63024aa8962b8d425" _idx="0" class="backtest-tr" _status="2" >' +
      '<td><span class="dot-clamp">这是一个简单的策略-1249</span></td><td>完成</td></tr></tbody>';
    const s1 = parseBuildList(doneRow);
    assert.equal(s1.rendered, true);
    assert.equal(s1.rows, 1);
    assert.equal(s1.done, true, '_status="2" is 完成 — measured on all 10 newest rows');

    // An in-progress row must NOT read as done. DONE_STATUS is a whitelist of one precisely
    // because no live run was available to observe the in-progress code: anything else keeps
    // polling (the old behaviour), whereas guessing wrong would scrape a partial result as final.
    for (const st of ['0', '1', '3', '4']) {
      const s = parseBuildList(doneRow.replace('_status="2"', `_status="${st}"`).replace('完成', '运行中'));
      assert.equal(s.done, false, `_status="${st}" must not read as finished`);
    }

    // A fresh algorithm: rendered, no row — the phantom, and `done` is unknown, not false-y-done.
    const fresh = parseBuildList(`${SHELL}" /><tbody></tbody>`);
    assert.deepStrictEqual({ ...fresh }, { rendered: true, rows: 0, done: null });

    // Unreadable stays unreadable for BOTH questions — the 系统繁忙 shape.
    const busy = parseBuildList('{"status":"2","code":"20000","msg":"系统繁忙，请稍后重试"}');
    assert.deepStrictEqual({ ...busy }, { rendered: false, rows: 0, done: null });
    // ⚠ Note that error body literally contains `"status":"2"`. Requiring the row ATTRIBUTE
    // (`class="backtest-tr" … _status=`) is what stops it reading as a finished run.
    assert.notEqual(busy.done, true);

    // Wiring: one fetch answers both questions, and completion does not consult the count.
    const post = fs.readFileSync(path.join(ROOT, 'utils/strategy-post-backtest.js'), 'utf8');
    assert.match(post, /probe\.done === true/);
    assert.match(post, /\+\+doneStreak >= 2/, 'confirm twice, like every other signal here');
    assert.match(post, /doneStreak = 0/, 'never latch');
    assert.match(post, /const probe = st\.runningCount > baseline/,
      'the probe is only worth making while JQ claims a run above baseline');
  });

  /**
   * ⚠⚠⚠ A COMPLETED BACKTEST MUST ALWAYS BE CAPTURED.
   *
   * Three runs were written off as `slow-skipped` with their results sitting on the server
   * (c5d20393, c083c109 on 2026-10-18; 223a137e on 2026-10-16 — three days undetected). A
   * `slow-skipped` row carries NO number, so nothing downstream could tell a book that FAILS from
   * one never measured: the recovered negatives score -0.1384 and -0.3475.
   *
   * The in-loop `_status` probe catches this while polling, but it only runs while JQ claims a run
   * above baseline. This asserts the BACKSTOP on the give-up path, which covers every other route
   * to abandoning a run.
   */
  await t.test('the safety cap checks 完成 before discarding the run', () => {
    const at = post.indexOf('LAST-CHANCE CAPTURE');
    assert.ok(at > 0, 'the give-up path must make one last attributable check');
    const block = post.slice(at, at + 2200);
    assert.match(block, /parseBuildList\(await fetchBuildList\(page, algorithmId\)\)/,
      'it must ask the buildList, which is attributable, not the running count, which is not');
    assert.match(block, /last\.done === true/);
    assert.match(block, /finished = true/, 'a finished run must fall through to the scrape');

    // ⚠ Order matters: the check must come BEFORE cancelBacktest, or cancelling races a run that
    // is complete but not yet delisted — and the whole point is to prefer a real measurement over
    // a null row.
    const check = post.indexOf('parseBuildList(await fetchBuildList(page, algorithmId))', at);
    const cancel = post.indexOf('cancelBacktest(page)', at);
    assert.ok(check > 0 && cancel > check,
      'the 完成 check must precede the cancel on the give-up path');

    // And the slow-skip must still be reachable when the run genuinely did not finish.
    assert.match(block, /stopped: true/, 'a genuinely stuck run must still slow-skip');
  });

  await t.test('the grace period is long enough to beat registration lag', () => {
    const m = post.match(/PHANTOM_GRACE_MS = parseInt\([^)]*String\((\d+) \* 60 \* 1000\)/);
    assert.ok(m, 'the grace must be declared');
    assert.ok(Number(m[1]) >= 3,
      `grace ${m[1]}min is too short — cancelling a healthy run is worse than the phantom`);
  });

  await t.test('phantom is a RETRIABLE status, never slow-skipped', () => {
    // slow-skipped = "it ran and we gave up" -> terminal, parked in the deferred pool at a higher
    // cap. phantom = "the backtest never existed" -> nothing learned, nothing billed, a bigger cap
    // changes nothing. Same class as scrape-zero.
    assert.match(post, /result && result\.phantom\)\s*\? 'phantom'/);
    const i = post.indexOf("result.phantom"), j = post.indexOf("result.stopped");
    assert.ok(i > 0 && i < j, 'phantom must be checked BEFORE stopped or it reads as a slow-skip');
    const terminal = norm.match(/const TERMINAL = new Set\(\[(.*?)\]\)/)[1];
    assert.ok(!/phantom/.test(terminal), 'phantom must never join TERMINAL');
  });

  await t.test('the normalizer records nothing and stops the batch', () => {
    // Detected by STATUS or by the bare marker — the marker path matters because an
    // unrecognised `*-STOP` line is recorded as a `crash` against the strategy, which is what six
    // CONCURRENT-STOP refusals did on 2026-09-23. tests/normalize.test.js enforces that coverage
    // for every marker the executor prints, and it caught this one.
    assert.match(norm, /status === 'phantom' \|\| out\.split/);
    assert.match(norm, /startsWith\('PHANTOM-STOP\\t'\)/);
    // ⚠ Anchor on the condition's STABLE prefix. Anchoring on `if (status === 'phantom')` broke
    // the moment the condition was widened to also match the bare marker — indexOf returned -1
    // and slice(-1) silently tested the last character of the file.
    const at = norm.indexOf("status === 'phantom'");
    assert.ok(at > 0, 'the phantom branch must exist');
    const block = norm.slice(at);
    assert.match(block.slice(0, 1200), /break;/, 'the account just phantomed — stop, do not spend');
    assert.ok(!/state\.defer/.test(block.slice(0, 800)),
      'a phantom must not be parked in the deferred pool — nothing was learned about the cap');
  });
});
