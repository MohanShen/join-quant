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
