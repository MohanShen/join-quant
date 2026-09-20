/**
 * stockcost-affected.js — which held strategies the epoch-6 stock-cost pin actually changes.
 *
 * Why this exists. `harness.measurementValid()` is deliberately coarse: an epoch bump that
 * touches fills or fees invalidates every earlier row, because it cannot know per-strategy
 * what changed. That is the safe default, but taken literally here it would re-measure all
 * 215 strategies — roughly a week of the 60-minute daily budget — when the epoch-6 change can
 * only move a strategy that was setting its OWN stock cost to something other than the bench's.
 *
 * Three groups, and only one of them needs a backtest:
 *
 *   never called set_order_cost(type='stock')  -> ran on JQ's default (万3 + 0.1% stamp),
 *                                                 which is exactly what epoch 6 pins. UNCHANGED.
 *   called it with bench-equivalent economics  -> pinning replaces the value with itself.
 *                                                 UNCHANGED.
 *   called it with anything else               -> its fees really were the author's. AFFECTED.
 *
 * ⚠ This narrows the RE-MEASUREMENT QUEUE, never the epoch rule. A row's `epoch` column still
 * says which bench produced it and `measurementValid` still rejects it; this only decides what
 * to spend minutes on first. If the parse below is wrong about a strategy, the cost is a stale
 * row that still reads as epoch 5 — visible, not silent.
 *
 * Usage:
 *   node utils/stockcost-affected.js            # report the three groups
 *   node utils/stockcost-affected.js --enqueue  # put the affected ones at the head of the
 *                                               # normalize queue (data/pending-normalize.json)
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const STRAT = path.join(ROOT, 'strategies');
const PENDING = path.join(ROOT, 'data/pending-normalize.json');

/** What epoch 6 pins for the stock table. Read from the config, never retyped. */
function benchStock() {
  const c = require('./harness-config').config().costs.stockOrderCost;
  if (!c) throw new Error('active epoch declares no costs.stockOrderCost — is epoch 6 active?');
  return { open: c.openCommission, close: c.closeCommission, ctax: c.closeTax };
}

/** `2.5/10000` appears in real strategies, so a bare parseFloat is not enough. */
function num(v) {
  if (v == null) return null;
  const s = String(v).trim();
  if (/^[0-9.]+\s*\/\s*[0-9.]+$/.test(s)) {
    const [a, b] = s.split('/').map(Number);
    return b ? a / b : null;
  }
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : null;
}

/** The stock OrderCost a strategy declares, or null if it never sets one. */
function declaredStockCost(src) {
  const m = src.match(/set_order_cost\(\s*OrderCost\(([^)]*)\)\s*,\s*type\s*=\s*['"]stock['"]/);
  if (!m) return null;
  const args = m[1];
  const g = k => {
    const r = args.match(new RegExp(`${k}\\s*=\\s*([0-9.]+(?:\\s*/\\s*[0-9.]+)?)`));
    return r ? num(r[1]) : null;
  };
  return { open: g('open_commission'), close: g('close_commission'), ctax: g('close_tax') };
}

const eq = (a, b) => a != null && b != null && Math.abs(a - b) < 1e-9;

function classify() {
  const bench = benchStock();
  const out = { unset: [], equivalent: [], affected: [], unparseable: [] };
  for (const f of fs.readdirSync(STRAT).filter(x => x.endsWith('.py'))) {
    const src = fs.readFileSync(path.join(STRAT, f), 'utf8');
    const d = declaredStockCost(src);
    if (!d) { out.unset.push(f); continue; }
    if (d.open == null && d.close == null) { out.unparseable.push(f); continue; }
    // close_tax omitted means the strategy left JQ's default stamp duty in place, which is
    // the bench value — so absence counts as equivalent, not as a difference.
    const sameTax = d.ctax == null || eq(d.ctax, bench.ctax);
    if (eq(d.open, bench.open) && eq(d.close, bench.close) && sameTax) out.equivalent.push(f);
    else out.affected.push({ file: f, declared: d });
  }
  return { bench, ...out };
}

/** Normalized rows, so the report can say how many affected strategies are actually measured. */
function normalizedSet() {
  const f = path.join(ROOT, 'harness/normalize-train.tsv');
  const s = new Set();
  try {
    for (const l of fs.readFileSync(f, 'utf8').split('\n').slice(1)) {
      const c = l.split('\t');
      if (c[0] && c[3] === 'normalized') s.add(c[0].replace('strategies/', ''));
    }
  } catch { /* ledger is gitignored and may be absent */ }
  return s;
}

if (require.main === module) {
  const r = classify();
  const norm = normalizedSet();
  const affectedMeasured = r.affected.filter(a => norm.has(a.file));

  console.log(`[stockcost] bench pins open=${r.bench.open} close=${r.bench.close} close_tax=${r.bench.ctax}`);
  console.log(`[stockcost] never set a stock cost      : ${r.unset.length}  (ran on JQ's default = the bench value)`);
  console.log(`[stockcost] set it, bench-equivalent    : ${r.equivalent.length}  (pin is a no-op)`);
  console.log(`[stockcost] set it, DIFFERENT           : ${r.affected.length}  -> ${affectedMeasured.length} of them are normalized rows`);
  if (r.unparseable.length) console.log(`[stockcost] unparseable                 : ${r.unparseable.length}  (treated as affected out of caution)`);
  console.log('');
  for (const a of affectedMeasured.slice(0, 12)) {
    const d = a.declared;
    console.log(`   open=${String(d.open).padEnd(8)} close=${String(d.close).padEnd(8)} ctax=${String(d.ctax).padEnd(7)} ${a.file.slice(0, 50)}`);
  }
  if (affectedMeasured.length > 12) console.log(`   …and ${affectedMeasured.length - 12} more`);

  if (process.argv.includes('--enqueue')) {
    // Head of the queue, order preserved by strategy-normalize's --files contract.
    const head = [...affectedMeasured.map(a => a.file), ...r.unparseable.filter(f => norm.has(f))];
    let rest = [];
    try { rest = JSON.parse(fs.readFileSync(PENDING, 'utf8')); } catch { rest = []; }
    const merged = [...head, ...rest.filter(f => !head.includes(f))];
    fs.writeFileSync(PENDING, JSON.stringify(merged, null, 2) + '\n');
    console.log(`\n[stockcost] enqueued ${head.length} affected strategy(ies) at the head of ` +
                `${path.relative(ROOT, PENDING)} (${merged.length} total)`);
  }
}

module.exports = { classify, declaredStockCost, benchStock, num };
