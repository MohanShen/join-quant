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
    assert.match(src, /\['add', '-u', '--', \.\.\.paths\]/);
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
      assert.strictEqual(r.owner, 'none',
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
      assert.strictEqual(r.owner, 'none', `${fam}: a declared decline must not be reopened`);
    }
    assert.ok(declared >= 1, 'expected at least one recorded decline');
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
