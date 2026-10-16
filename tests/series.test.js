/**
 * Tests for the daily-equity-curve layer: the curve math, the zero-cost backfill matcher, and
 * the component register.
 *
 * Most of these cover a real incident from the build:
 *   - annualizing each side over its OWN span matched 0 of 124 ledger rows, because the ledger
 *     annualizes over the requested window (729 days) and a curve spans the trading days that
 *     actually occurred (724);
 *   - differencing cumulative percentages instead of chaining them reports volatility of 1.362
 *     where JoinQuant reports 0.227 — a 6x error that looks plausible in isolation;
 *   - "one curve claimed by several rows" is usually 16%-duplicate strategies, not ambiguity.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const series = require('../utils/backtest-series');
const backfill = require('../utils/series-backfill');
const scan = require('../utils/component-scan');

/** A curve rising a steady 1%/day, as cumulative percent. */
const steady = (n, pct = 1) => {
  const out = [];
  let eq = 1;
  for (let i = 0; i < n; i++) { eq *= (1 + pct / 100); out.push((eq - 1) * 100); }
  return out;
};
const dates = n => Array.from({ length: n }, (_, i) =>
  new Date(Date.UTC(2022, 0, 3) + i * 86400000).toISOString().slice(0, 10));

test('dailyReturns chains, never differences', async t => {
  await t.test('recovers a constant daily return far from zero', () => {
    // The whole point: at +300% cumulative, a 1% day is still 1%. Differencing would call it 4%.
    const cum = steady(200, 1);
    const r = series.dailyReturns(cum);
    assert.strictEqual(r.length, 200, 'returns are index-aligned with the curve');
    for (const v of r) assert.ok(Math.abs(v - 0.01) < 1e-9, `expected 0.01, got ${v}`);
  });

  await t.test('counts the FIRST day — cum[0] is a return, not a starting level', () => {
    // Regression guard. Starting the loop at i=1 dropped a +21.51% opening day on
    // 以混沌之火_信息熵策略, turning +25.77% into +3.51% and annual 12.16% into 1.75%.
    const r = series.dailyReturns([21.51, 20.55]);
    assert.ok(Math.abs(r[0] - 0.2151) < 1e-9, `first day should be 21.51%, got ${r[0]}`);
  });

  await t.test('recompounding the returns reproduces the curve exactly', () => {
    const cum = [21.51, 20.55, 21.23, 25.77];
    const r = series.dailyReturns(cum);
    let eq = 1;
    for (const v of r) eq *= (1 + v);
    assert.ok(Math.abs((eq - 1) * 100 - 25.77) < 1e-9, `got ${(eq - 1) * 100}`);
  });

  await t.test('differencing the same curve would be badly wrong — the guarded bug', () => {
    const cum = steady(200, 1);
    const diffed = [];
    for (let i = 1; i < cum.length; i++) diffed.push((cum[i] - cum[i - 1]) / 100);
    const last = diffed[diffed.length - 1];
    assert.ok(last > 0.05, `differencing should blow up far from zero, got ${last}`);
  });

  await t.test('survives a -100% wipeout instead of dividing by zero', () => {
    const r = series.dailyReturns([0, -100, -100]);
    assert.strictEqual(r[1], -1, 'losing everything IS a -100% day, not a null');
    assert.strictEqual(r[2], null, 'the day AFTER a wipeout has no defined return');
  });
});

test('pearson', async t => {
  await t.test('is 1 for a series against itself', () => {
    assert.strictEqual(series.pearson([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]), 1);
  });

  await t.test('is -1 when perfectly opposed', () => {
    assert.strictEqual(series.pearson([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]), -1);
  });

  await t.test('returns null for a flat series — undefined, not zero', () => {
    // A flat leg has no variance; calling that "uncorrelated" would make it look like a
    // perfect diversifier and rank it top of every component scan.
    assert.strictEqual(series.pearson([1, 2, 3], [2, 2, 2]), null);
  });

  await t.test('returns null when there is too little overlap to mean anything', () => {
    assert.strictEqual(series.pearson([1, 2], [1, 2]), null);
  });
});

test('correlate aligns on dates, not positions', async t => {
  const n = 120;
  const A = { dates: dates(n), cum: steady(n, 1) };
  // B starts 10 days later — position-alignment would compare different days.
  const B = { dates: dates(n).slice(10), cum: steady(n - 10, 1) };

  await t.test('uses only the shared days', () => {
    const { overlapDays } = series.correlate(A, B);
    assert.ok(overlapDays > 0 && overlapDays <= n - 10,
      `overlap ${overlapDays} should be bounded by the shorter series`);
  });

  await t.test('a series correlated with itself is 1', () => {
    const { corr } = series.correlate(A, A);
    assert.strictEqual(corr, 1);
  });
});

test('seriesKey', async t => {
  await t.test('is built from the ledger identity triple, never a backtestId', () => {
    const k = series.seriesKey('strategies/2026-05-12_foo-598050b9.py', 'train', 4);
    assert.match(k, /__train__e4$/);
    assert.ok(!k.includes('strategies/'), 'the directory prefix is redundant in a key');
  });

  await t.test('is stable for the same triple', () => {
    assert.strictEqual(
      series.seriesKey('strategies/a.py', 'train', 2),
      series.seriesKey('strategies/a.py', 'train', 2));
  });

  await t.test('separates epochs, because a result belongs to the bench that made it', () => {
    assert.notStrictEqual(
      series.seriesKey('strategies/a.py', 'train', 2),
      series.seriesKey('strategies/a.py', 'train', 4));
  });
});

test('maxDrawdownPct', async t => {
  await t.test('is zero for a monotonically rising curve', () => {
    assert.strictEqual(backfill.maxDrawdownPct(steady(50, 1)), 0);
  });

  await t.test('measures the peak-to-trough fall in equity terms', () => {
    // equity 1.00 -> 1.10 -> 0.99 : a 10% fall from the peak
    const cum = [0, 10, -1];
    assert.ok(Math.abs(backfill.maxDrawdownPct(cum) - 10) < 1e-6);
  });
});

test('backfill matching', async t => {
  // The row is annualized over the REQUESTED window; the curve spans actual trading days.
  const row = { start: '2022-01-01', end: '2023-12-31', days: 729,
                total: null, annual: 33.79, maxdd: 19.68 };
  const cand = { start: '2022-01-04', end: '2023-12-29',
                 totalPct: 78.86, maxddPct: 19.67,
                 annualPct: backfill.annualize(78.86, 724) };

  await t.test('matches despite the two sides spanning different day counts', () => {
    assert.ok(backfill.matches(row, cand),
      `should match; candidate self-annualized to ${cand.annualPct.toFixed(2)} vs row ${row.annual}`);
  });

  await t.test('the curve\'s own annualization really does differ by more than the tolerance', () => {
    // This is why the match key is re-annualized rather than taken from the fingerprint.
    assert.ok(Math.abs(cand.annualPct - row.annual) > backfill.TOL_PP);
  });

  await t.test('prefers total_pct exactly when the row has one', () => {
    assert.ok(backfill.matches({ ...row, total: 78.86 }, cand));
    assert.ok(!backfill.matches({ ...row, total: 91.0 }, cand));
  });

  await t.test('rejects a different window', () => {
    assert.ok(!backfill.matches({ ...row, start: '2024-01-01', end: '2025-12-31' }, cand));
  });

  await t.test('rejects a matching return with a different drawdown', () => {
    assert.ok(!backfill.matches(row, { ...cand, maxddPct: 31.0 }));
  });
});

test('reconcile', async t => {
  const curve = { backtestId: 'b1', start: '2022-01-04', end: '2023-12-29',
                  totalPct: 78.86, maxddPct: 19.68, points: 484,
                  annualPct: backfill.annualize(78.86, 724) };
  const base = { start: '2022-01-01', end: '2023-12-31', days: 729, total: 78.86,
                 annual: 33.79, maxdd: 19.68, epoch: '2' };

  await t.test('matches a single row to a single curve', () => {
    const r = backfill.reconcile([{ ...base, sourceFile: 'strategies/only.py' }], [curve]);
    assert.strictEqual(r.matched.length, 1);
    assert.strictEqual(r.ambiguous.length, 0);
  });

  await t.test('holds back a curve claimed by two DIFFERENT strategies', () => {
    // Neither file exists on disk, so no body hash can prove them identical — and an
    // unprovable duplicate must not be assigned. A wrong curve corrupts every correlation.
    const r = backfill.reconcile([
      { ...base, sourceFile: 'strategies/does-not-exist-a.py' },
      { ...base, sourceFile: 'strategies/does-not-exist-b.py' },
    ], [curve]);
    assert.strictEqual(r.matched.length, 0);
    assert.strictEqual(r.ambiguous.length, 2);
    for (const a of r.ambiguous) assert.match(a.reason, /DIFFERENT/);
  });

  await t.test('reports a row no curve explains as unmatched, not as a guess', () => {
    const r = backfill.reconcile([{ ...base, sourceFile: 'strategies/x.py', annual: -99, total: -99 }], [curve]);
    assert.strictEqual(r.unmatched.length, 1);
    assert.strictEqual(r.matched.length, 0);
  });
});

test('two-pass reconcile: tight first, relaxed only as a fallback', async t => {
  const mkCurve = (id, totalPct, maxddPct) => ({
    backtestId: id, start: '2022-01-04', end: '2023-12-29', points: 484,
    totalPct, maxddPct, annualPct: backfill.annualize(totalPct, 724),
  });
  // A reconstructed row: no measured total, so the relaxed annual bound is available to it.
  const recon = (sourceFile, annual, maxdd) => ({
    sourceFile, start: '2022-01-01', end: '2023-12-31', days: 729,
    total: null, annual, maxdd, epoch: '2',
  });

  await t.test('the relaxed bound applies ONLY to reconstructed rows', () => {
    const cand = mkCurve('b1', 78.86, 19.68);
    const annualAtRowDays = backfill.annualize(78.86, 729);
    // 0.2pp away: inside the reconstructed bound, outside the tight one.
    const row = recon('strategies/a.py', annualAtRowDays + 0.2, 19.68);
    assert.ok(backfill.matches(row, cand, true), 'reconstructed row should match when relaxed');
    assert.ok(!backfill.matches(row, cand, false), 'the same row must NOT match tight');
    // A row WITH a measured total is held to the exact total regardless of the relaxed flag.
    const measured = { ...row, total: 91.0 };
    assert.ok(!backfill.matches(measured, cand, true), 'a measured total is never relaxed');
  });

  await t.test('drawdown is never relaxed', () => {
    const cand = mkCurve('b1', 78.86, 19.68);
    const row = recon('strategies/a.py', backfill.annualize(78.86, 729), 25.0);
    assert.ok(!backfill.matches(row, cand, true));
  });

  await t.test('a tight match is not spoiled by a relaxed-only rival curve', () => {
    // Regression: one relaxed pass over everything pulled extra curves into the candidate set
    // of rows that already matched tightly and pushed 4 of them into "ambiguous", including
    // the 低换手红利 component candidate.
    const exact = backfill.annualize(78.86, 729);
    const row = recon('strategies/tight.py', exact, 19.68);
    const curves = [
      mkCurve('tight', 78.86, 19.68),        // agrees to ~0.00pp
      mkCurve('loose', 79.30, 19.68),        // only reachable under the relaxed bound
    ];
    const r = backfill.reconcile([row], curves);
    assert.strictEqual(r.matched.length, 1, 'the tight match should survive');
    assert.strictEqual(r.matched[0].curve.backtestId, 'tight');
    assert.strictEqual(r.matched[0].relaxed, false);
  });

  await t.test('every row lands in exactly one bucket', () => {
    // Concatenating both passes' ambiguous lists double-counted rows both passes contested,
    // so the buckets summed to 135 against a ledger of 124.
    const rows = [
      recon('strategies/a.py', backfill.annualize(78.86, 729), 19.68),
      recon('strategies/b.py', backfill.annualize(50.00, 729), 11.00),
      recon('strategies/c.py', -999, 99.0),                       // nothing can match
    ];
    const curves = [mkCurve('x', 78.86, 19.68), mkCurve('y', 50.00, 11.00)];
    const r = backfill.reconcile(rows, curves);
    assert.strictEqual(r.matched.length + r.ambiguous.length + r.unmatched.length, rows.length);
  });

  await t.test('matchBasis records how a row was paired', () => {
    assert.strictEqual(backfill.matchBasis({ total: 78.86 }, false), 'exact-total');
    assert.strictEqual(backfill.matchBasis({ total: null }, false), 'tight-reconstructed');
    assert.strictEqual(backfill.matchBasis({ total: null }, true), 'relaxed-reconstructed');
  });
});

test('diversification decomposition', async t => {
  const n = 300;
  // Deterministic pseudo-random daily returns with a `drift` added to each day.
  const mk = (seed, drift = 0.0012) => {
    let s = seed, cum = [], eq = 1;
    for (let i = 0; i < n; i++) {
      s = (s * 1103515245 + 12345) % 2147483648;
      eq *= (1 + ((s / 2147483648) - 0.5) * 0.04 + drift);
      cum.push((eq - 1) * 100);
    }
    return { dates: dates(n), cum };
  };

  await t.test('ratio is 1.0 when a series is blended with itself — no diversification', () => {
    const A = mk(7);
    const d = scan.diversification([A, A]);
    assert.ok(d, 'expected a decomposition');
    assert.ok(Math.abs(d.ratio - 1) < 1e-6, `ratio should be 1, got ${d.ratio}`);
    assert.ok(Math.abs(d.meanCorr - 1) < 1e-6, `corr should be 1, got ${d.meanCorr}`);
  });

  await t.test('ratio exceeds 1 for imperfectly correlated members', () => {
    const d = scan.diversification([mk(7), mk(91)]);
    assert.ok(d.ratio > 1, `expected a diversification benefit, got ${d.ratio}`);
    assert.ok(d.meanCorr < 1);
  });

  await t.test('at rho=1 the same returns always carry more volatility', () => {
    const d = scan.diversification([mk(7), mk(91)]);
    assert.ok(d.weightedVolPct >= d.blendVolPct);
  });

  await t.test('strips the risk-side gain when the excess return is POSITIVE', () => {
    const d = scan.diversification([mk(7), mk(91)]);
    assert.ok(d.blend.annualPct / 100 > scan.RISK_FREE,
      'this case needs a positive excess return to be the right test');
    assert.ok(d.sharpeNoDiversification <= d.blend.sharpe + 1e-9,
      `${d.sharpeNoDiversification} should not exceed ${d.blend.sharpe}`);
  });

  await t.test('⚠ the comparison INVERTS when the excess return is negative', () => {
    // Dividing a negative excess return by a LARGER volatility moves it toward zero, so
    // stripping diversification RAISES the reported Sharpe. Any rule that reads
    // "sharpeNoDiversification below the best member" as evidence of a manufactured pass is
    // therefore only valid above the risk-free rate — which is why the guard checks first.
    const d = scan.diversification([mk(7, -0.002), mk(91, -0.002)]);
    assert.ok(d.blend.annualPct / 100 < scan.RISK_FREE);
    assert.ok(d.sharpeNoDiversification > d.blend.sharpe,
      `expected the inversion: ${d.sharpeNoDiversification} vs ${d.blend.sharpe}`);
  });

  await t.test('refuses to decompose a single member', () => {
    assert.strictEqual(scan.diversification([mk(7)]), null);
  });

  await t.test('refuses when the members barely overlap', () => {
    const short = { dates: dates(10), cum: steady(10, 1) };
    assert.strictEqual(scan.diversification([short, short]), null);
  });
});

test('familyToType parses the frontmatter list', async t => {
  const map = scan.familyToType();

  await t.test('no family name keeps a stray bracket', () => {
    // `families: [[[A]], [[B]]]` is a YAML list OF wiki links, so the FIRST entry carries three
    // opening brackets. Stripping only the `[[`/`]]` pairs left `[A`, so the first family of
    // every type never matched and its strategies fell into `(untyped)` — 33 of 71 of them.
    for (const name of Object.keys(map)) {
      assert.ok(!/[[\]]/.test(name), `family name "${name}" still carries a bracket`);
    }
  });

  await t.test('maps the families the type pages actually list',
    { skip: Object.keys(map).length === 0 }, () => {
      for (const [fam, type] of Object.entries(map)) {
        assert.ok(fam.length > 0 && type.length > 0);
        assert.ok(fs.existsSync(path.join(__dirname, '..', 'wiki/types', `${type}.md`)),
          `type ${type} has no page`);
      }
    });
});

test('component register', async t => {
  const comp = require('../utils/components');

  await t.test('refuses a claim with no evidence', () => {
    // The repo has already paid for guess-based rules: a screening hard-reject built on a
    // hunch permanently discarded 287 of 549 strategies.
    assert.throws(() => comp.record({
      source: 'strategies/a.py', aspect: 'atr-stop', kind: 'exit', claim: 'looks useful',
    }), /evidence is required/);
  });

  await t.test('refuses a kind outside the vocabulary', () => {
    assert.throws(() => comp.record({
      source: 'strategies/a.py', aspect: 'x', kind: 'vibes', claim: 'c', evidence: 'e',
    }), /unknown kind/);
  });

  await t.test('refuses a nameless source or aspect', () => {
    assert.throws(() => comp.record({ aspect: 'x', kind: 'exit', claim: 'c', evidence: 'e' }), /source is required/);
    assert.throws(() => comp.record({ source: 's', kind: 'exit', claim: 'c', evidence: 'e' }), /aspect is required/);
  });

  await t.test('the tracked file keeps its column contract', { skip: !fs.existsSync(comp.FILE) }, () => {
    const head = fs.readFileSync(comp.FILE, 'utf8').split('\n')[0].split('\t');
    assert.deepStrictEqual(head, comp.COLUMNS);
  });
});

test('stored series on disk', async t => {
  const keys = series.list();

  await t.test('every stored series carries the fields a decomposition needs',
    { skip: keys.length === 0 }, () => {
      for (const k of keys.slice(0, 40)) {
        const r = series.load(k);
        assert.ok(Array.isArray(r.dates) && Array.isArray(r.cum), `${k} missing arrays`);
        assert.strictEqual(r.dates.length, r.cum.length, `${k} dates/cum length mismatch`);
        assert.ok(r.dates.length > 0, `${k} is empty`);
      }
    });

  await t.test('none is stored under a bare backtestId — ids are re-minted per request',
    { skip: keys.length === 0 }, () => {
      for (const k of keys) assert.ok(!/^[a-f0-9]{32}$/.test(k), `${k} looks like a raw id`);
    });
});

/**
 * `members()` must never mix benches.
 *
 * It used to read every `normalized` ledger row regardless of epoch. Two defects rode on that:
 * the ranking was built on superseded measurements (86 of 88 emitted members were epoch-2 rows,
 * so its 小盘-H-high leader read 0.5267 where epoch 6 measures 0.2944), and because the ledger
 * is append-only, a re-measured strategy appeared once PER EPOCH — the stale copy could take
 * the leader slot from its own newer row. Uplift is a difference between two members, so this
 * is not staleness; it is arithmetic across incommensurable benches, and the sign can flip.
 */
test('component members are epoch-filtered and de-duplicated', async t => {
  const harness = require('../utils/harness-config');
  const src = fs.readFileSync(path.join(__dirname, '../utils/component-scan.js'), 'utf8');

  await t.test('the same rule the bench uses decides what counts as measured', () => {
    assert.match(src, /harness\.measurementValid\(epoch\)/,
      'members() must gate on measurementValid, not on its own notion of recency');
  });

  await t.test('no emitted member belongs to a superseded bench', () => {
    for (const m of scan.members()) {
      assert.ok(harness.measurementValid(m.epoch),
        `${m.sourceFile} was emitted at epoch ${m.epoch}, which is not valid under the active epoch`);
    }
  });

  await t.test('one row per strategy, newest epoch winning', () => {
    const seen = new Map();
    for (const m of scan.members()) {
      assert.ok(!seen.has(m.sourceFile),
        `${m.sourceFile} emitted twice (epochs ${seen.get(m.sourceFile)} and ${m.epoch})`);
      seen.set(m.sourceFile, m.epoch);
    }
  });

  await t.test('what was dropped is reported, not swallowed', () => {
    // An empty ranking and a ranking built on a dead bench look identical from outside; the
    // counts are what let a caller tell them apart.
    const ms = scan.members();
    assert.ok(ms.skipped && typeof ms.skipped.staleEpoch === 'number',
      'members() must report how many rows it dropped as superseded');
    assert.ok(typeof ms.skipped.noSeries === 'number',
      'members() must report how many valid rows have no stored curve');
  });

  await t.test('the mixed-bench view still exists, but only behind an explicit flag', () => {
    const all = scan.members({ allEpochs: true });
    assert.ok(all.length >= scan.members().length,
      'allEpochs must be a superset — it is the inspection escape hatch');
    assert.match(src, /--all-epochs/, 'the CLI must label the mixed view, not hide it');
  });
});

test('yearlySplit — the per-year basis of the epoch-7 integration bar', async t => {
  const harness = require('../utils/harness-config');

  /** A curve that gains `a`%/day through 2022 then `b`%/day through 2023. */
  const twoRegime = (a, b) => {
    const d = [], cum = [];
    let eq = 1;
    for (let y of [2022, 2023]) {
      for (let i = 0; i < 240; i++) {
        const day = new Date(Date.UTC(y, 0, 3) + i * 86400000);
        if (day.getUTCFullYear() !== y) break;
        eq *= 1 + (y === 2022 ? a : b) / 100;
        d.push(day.toISOString().slice(0, 10));
        cum.push((eq - 1) * 100);
      }
    }
    return { dates: d, cum, benchCum: cum.map(() => 0), points: d.length };
  };

  await t.test('converts BEFORE slicing — the trap that would make year 2 fiction', () => {
    // A book that compounds hard in 2022 ends that year far above its base. Clipping `cum`
    // first and calling dailyReturns() on the slice measures the 2023 opening day against a
    // base of 1, folding all of 2022's gain into one day: the year's annual, vol, sharpe and
    // drawdown all become numbers that look plausible and are wrong. Same family of error as
    // differencing cumulative percentages (vol 1.362 vs JQ's 0.227).
    const rec = twoRegime(1.0, 0.1);
    const ys = scan.yearlySplit(rec, 'train');
    assert.strictEqual(ys.length, 2);
    // 2023 gains 0.1%/day: a flat ~24% year, nowhere near the >1000% that the trap produces.
    assert.ok(ys[1].annualPct > 10 && ys[1].annualPct < 50,
      `2023 should be a modest year, got ${ys[1].annualPct}%`);
    assert.ok(ys[0].annualPct > ys[1].annualPct * 5, 'the regimes must stay distinguishable');
  });

  await t.test('annualizes over the WINDOW year, not the curve\'s own span', () => {
    // A full calendar year of a steady riser must report annual ~= total, because the slice's
    // day count comes from windowYears() (365) rather than from the ~240 trading days present.
    const rec = twoRegime(0.1, 0.1);
    const ys = scan.yearlySplit(rec, 'train');
    for (const y of ys) {
      assert.strictEqual(y.days, 365);
      assert.ok(Math.abs(y.annualPct - y.totalPct) < 1.0,
        `a full year should annualize to about its total, got ${y.annualPct} vs ${y.totalPct}`);
    }
  });

  await t.test('objective is the harness score applied within the year', () => {
    const ys = scan.yearlySplit(twoRegime(0.5, 0.2), 'train');
    for (const y of ys) {
      assert.strictEqual(y.objective, Number(((y.annualPct - y.maxddPct) / 100).toFixed(4)));
    }
  });

  await t.test('worstYear is the minimum, which is what the maximin compares', () => {
    const rec = twoRegime(1.0, 0.05);
    const w = scan.worstYear(rec, 'train');
    assert.strictEqual(w.year, 2023, 'the weak regime is the worst year');
    const ys = scan.yearlySplit(rec, 'train');
    assert.strictEqual(w.objective, Math.min(...ys.map(y => y.objective)));
  });

  await t.test('returns null when a TRAIN year is missing, never a partial verdict', () => {
    // A split that silently covers one year would be compared against one covering two.
    const rec = twoRegime(0.5, 0.5);
    const only2022 = scan.yearlySplit(
      series.clip(rec, '2022-01-01', '2022-12-31'), 'train');
    assert.strictEqual(only2022, null);
    assert.strictEqual(scan.worstYear(series.clip(rec, '2022-01-01', '2022-12-31'), 'train'), null);
  });

  await t.test('reproduces a real stored curve\'s yearly returns', () => {
    // PT多策略: 2022 +286.1%, 2023 +121.2%, computed independently from the raw curve.
    const r = series.loadComparable(
      'strategies/2026-07-18_PT多策略分仓隔离插件V1_3-c70281d3.py', 'train');
    if (!r.rec) return;          // curve store is gitignored; skip where it is absent
    const ys = scan.yearlySplit(r.rec, 'train');
    assert.ok(Math.abs(ys[0].totalPct - 286.1) < 0.5, `2022: ${ys[0].totalPct}`);
    assert.ok(Math.abs(ys[1].totalPct - 121.2) < 0.5, `2023: ${ys[1].totalPct}`);
  });

  await t.test('windowYears is read from the epoch, so the split moves with the window', () => {
    assert.deepStrictEqual(harness.windowYears('train').map(y => y.year), [2022, 2023]);
    assert.deepStrictEqual(harness.windowYears('val').map(y => y.year), [2024, 2025]);
    assert.deepStrictEqual(harness.windowYears('nonexistent'), []);
  });
});

test('loadComparable — a scoring-only bump must not orphan the curve store', async t => {
  await t.test('finds a curve measured under an earlier COMPARABLE epoch', () => {
    // The regression this exists for: the key embeds the measuring epoch, so building one from
    // config().epoch found nothing the instant epoch 7 activated — all 280 stored curves are
    // stamped e6 and all 280 are still current, because epoch 7 changed only scoring.
    const r = series.loadComparable(
      'strategies/2026-07-18_PT多策略分仓隔离插件V1_3-c70281d3.py', 'train');
    if (!r.rec) return;
    assert.strictEqual(r.epoch, 6, 'the e6 curve is a current measurement under epoch 7');
    assert.match(r.key, /__e6$/);
  });

  await t.test('never substitutes a STALE epoch for a missing current one', () => {
    const harness = require('../utils/harness-config');
    const comparable = harness.comparableEpochs();
    assert.ok(!comparable.has(2), 'epoch 2 ran without the execution pins');
    // Asking for a stale epoch explicitly does not get one: only comparable epochs are tried.
    const r = series.loadComparable('strategies/whatever-does-not-exist.py', 'train', 2);
    assert.strictEqual(r.rec, null);
    for (const k of r.tried) assert.ok(!/__e2$/.test(k), `tried a stale epoch: ${k}`);
  });

  await t.test('reports the keys it tried, so a miss can be explained', () => {
    const r = series.loadComparable('strategies/definitely-absent.py', 'train');
    assert.strictEqual(r.rec, null);
    assert.ok(r.tried.length >= 1);
  });
});

test('a curve is keyed by its LOGICAL source, never by the temp copy that ran', async t => {
  // ⚠⚠ The incident, 2026-10-16. strategy-post-backtest derived the key from the file it was
  // handed. That is right for a repo path and silently wrong for strategy-normalize.js, which
  // runs a normalized COPY at /tmp/jq-normalize/<tag>.py — so the key became
  // `.._.._.._tmp_jq-normalize_<tag>__train__e6`. Two things hid it completely: the key starts
  // with a DOT so `ls data/series/` never listed the files, and no reader could find them because
  // every reader builds its key from the real sourceFile. 63 curves were stranded, four family
  // champions read as curveless, and the epoch-8 per-year bar silently fell back to pooled.
  const rekey = require('../utils/series-rekey');

  await t.test('the mangled pattern is recognised, and a normal key is not', () => {
    assert.match('.._.._.._tmp_jq-normalize_406a1e4d__train__e6.json', rekey.MANGLED);
    assert.doesNotMatch('2026-06-04_foo-406a1e4d__train__e6.json', rekey.MANGLED);
    // The tag, window and epoch all have to come back out, or a re-key cannot be addressed.
    const m = '.._.._.._tmp_jq-normalize_406a1e4d__train__e8.json'.match(rekey.MANGLED);
    assert.deepStrictEqual([m[1], m[2], m[3]], ['406a1e4d', 'train', '8']);
  });

  await t.test('the executor REFUSES a path that escapes the repo instead of hiding it', () => {
    // The fix is not just "pass --source-file"; an un-passed escape must fail loudly, because a
    // silent hidden file is exactly how this survived months of use.
    const src = fs.readFileSync(path.join(__dirname, '..', 'utils/strategy-post-backtest.js'), 'utf8');
    assert.match(src, /function logicalSourceFile/);
    assert.match(src, /rel\.startsWith\('\.\.'\)/,
      'an escaping relative path must be detected');
    assert.match(src, /--source-file/, 'the error must name the way out');
    assert.match(src, /captureSeries\(editorPage, algorithmId, strategyPath, window, parsed\.sourceFile\)/,
      'the explicit identity must actually reach captureSeries');
  });

  await t.test('the normalizer passes the strategies/ path, not its temp copy', () => {
    const src = fs.readFileSync(path.join(__dirname, '..', 'utils/strategy-normalize.js'), 'utf8');
    assert.match(src, /'--source-file', srcFile/);
    // srcFile is the ledger identity; keying by anything else re-creates the bug.
    assert.match(src, /const srcFile = 'strategies\/' \+ f;/);
  });

  await t.test('re-key never guesses: an ambiguous tag is skipped, a target is not overwritten', () => {
    const os = require('os');
    const d = fs.mkdtempSync(path.join(os.tmpdir(), 'rekey-'));
    const sdir = path.join(d, 'series'); fs.mkdirSync(sdir);
    const hdir = path.join(d, 'harness'); fs.mkdirSync(hdir);

    // Two different sourceFiles sharing one 8-char tag — a wrong pick here would silently
    // corrupt every correlation and per-year bar built on that curve.
    fs.writeFileSync(path.join(hdir, 'normalize-train.tsv'),
      ['sourceFile\tpostId\ttitle\tstatus',
       'strategies/one.py\tdeadbeef\tA\tnormalized',
       'strategies/two.py\tdeadbeef\tB\tnormalized',
       'strategies/three.py\tcafe1234\tC\tnormalized'].join('\n') + '\n');
    const body = JSON.stringify({ dates: ['2022-01-04'], cum: [1], benchCum: [0], points: 1 });
    fs.writeFileSync(path.join(sdir, '.._.._.._tmp_jq-normalize_deadbeef__train__e6.json'), body);
    fs.writeFileSync(path.join(sdir, '.._.._.._tmp_jq-normalize_cafe1234__train__e6.json'), body);
    // …and a target that already exists must not be clobbered.
    fs.writeFileSync(path.join(sdir, 'three__train__e6.json'), body);

    const prevS = process.env.JQ_SERIES_DIR, prevH = process.env.JQ_HARNESS_DIR;
    process.env.JQ_SERIES_DIR = sdir; process.env.JQ_HARNESS_DIR = hdir;
    try {
      const { moves, skipped } = rekey.plan();
      assert.strictEqual(moves.length, 0, 'neither file is safely mappable');
      assert.strictEqual(skipped.length, 2);
      assert.ok(skipped.some(s => /claimed by 2 sourceFiles/.test(s.why)));
      assert.ok(skipped.some(s => /already exists/.test(s.why)));
    } finally {
      if (prevS === undefined) delete process.env.JQ_SERIES_DIR; else process.env.JQ_SERIES_DIR = prevS;
      if (prevH === undefined) delete process.env.JQ_HARNESS_DIR; else process.env.JQ_HARNESS_DIR = prevH;
    }
  });

  await t.test('re-key rewrites the record\'s own sourceFile, not just the filename', () => {
    const os = require('os');
    const d = fs.mkdtempSync(path.join(os.tmpdir(), 'rekey2-'));
    const sdir = path.join(d, 'series'); fs.mkdirSync(sdir);
    const hdir = path.join(d, 'harness'); fs.mkdirSync(hdir);
    fs.writeFileSync(path.join(hdir, 'normalize-train.tsv'),
      ['sourceFile\tpostId\ttitle\tstatus', 'strategies/solo.py\tfeedface\tA\tnormalized'].join('\n') + '\n');
    fs.writeFileSync(path.join(sdir, '.._.._.._tmp_jq-normalize_feedface__train__e6.json'),
      JSON.stringify({ sourceFile: '../../../tmp/jq-normalize/feedface.py',
                       dates: ['2022-01-04'], cum: [1], benchCum: [0], points: 1 }));

    const prevS = process.env.JQ_SERIES_DIR, prevH = process.env.JQ_HARNESS_DIR;
    process.env.JQ_SERIES_DIR = sdir; process.env.JQ_HARNESS_DIR = hdir;
    try {
      const { moves } = rekey.plan();
      assert.strictEqual(moves.length, 1);
      assert.strictEqual(rekey.apply(moves), 1);
      const to = path.join(sdir, moves[0].to);
      assert.ok(fs.existsSync(to));
      assert.ok(!fs.existsSync(path.join(sdir, moves[0].from)), 'the original is renamed, not copied');
      const rec = JSON.parse(fs.readFileSync(to, 'utf8'));
      // Leaving the temp path inside the record keeps a second, stale copy of the identity.
      assert.strictEqual(rec.sourceFile, 'strategies/solo.py');
      assert.strictEqual(rec.rekeyedFrom, moves[0].from);
    } finally {
      if (prevS === undefined) delete process.env.JQ_SERIES_DIR; else process.env.JQ_SERIES_DIR = prevS;
      if (prevH === undefined) delete process.env.JQ_HARNESS_DIR; else process.env.JQ_HARNESS_DIR = prevH;
    }
  });
});
