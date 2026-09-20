/**
 * wiki-epoch-repair.js — one-off: correct the `epoch` stamped in each strategy page's
 * `normalized: { … }` block from the ledger.
 *
 * Why this matters more than a wrong label. `kb-stub.js` wrote `epoch: 1` as a LITERAL, so
 * every page created since epoch 1 claims to have been measured by a bench that has been
 * superseded four times — 120 of them, while the ledger says epoch 2 (122 rows) and epoch 4 (2).
 *
 * That block is not decoration. CLAUDE.md designates it the DURABLE BACKUP of
 * `harness/normalize-*.tsv`, which is gitignored and has already regressed once from ~119 rows
 * to 18. `normalize-ledger-rebuild.js` reconstructs the ledger from these pages — so a rebuild
 * would have produced a ledger that said "epoch 1" everywhere, and the normalizer's
 * epoch-aware done-check would then have judged the entire library unmeasured and re-run all
 * 215 strategies at 60 backtest-minutes a day.
 *
 * The ledger is authoritative for `epoch`: it is written by the run that actually measured the
 * row. A page whose sourceFile has no ledger row is left alone and reported — inventing an
 * epoch would recreate the exact problem this repairs.
 *
 * Usage:
 *   node utils/wiki-epoch-repair.js --dry     # report what would change
 *   node utils/wiki-epoch-repair.js           # rewrite the epoch field in place
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SDIR = path.join(ROOT, 'wiki/strategies');

/**
 * sourceFile -> the FULL measured record from the newest epoch that measured it.
 *
 * ⚠ This used to return the epoch alone, and the repair rewrote only the `epoch:` field. That
 * left the metrics stale, which matters because nothing else refreshes them either:
 * `kb-stub.createStub` returns early when a page already exists, so a re-measured strategy
 * kept its old numbers forever. An epoch rollout re-measures in bulk, so the durable backup
 * went stale in bulk — and the backup is what `normalize-ledger-rebuild.js` reconstructs the
 * gitignored ledger from.
 *
 * Measured consequence: three different 打板 strategies (4cce4058, 69ca427f, a7f60565) all
 * carried the identical block annual 0.0910 / sharpe 0.16 / maxdd 0.2368. Fresh epoch-6 runs
 * measured them at 409.39%, 8.96% and 285.93% — nothing alike. Those contaminated values had
 * already propagated back into the ledger as reconstructed rows.
 */
function ledgerRecords(window = 'train') {
  const file = path.join(ROOT, `harness/normalize-${window}.tsv`);
  const out = new Map();
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch { return out; }
  for (const line of text.split('\n').slice(1)) {
    const c = line.split('\t');
    if (!c[0] || c[3] !== 'normalized') continue;
    const e = c[13] && c[13].trim();
    if (!e) continue;
    const rec = {
      epoch: e,
      annual: parseFloat(c[8]),
      sharpe: c[9],
      maxdd: parseFloat(c[10]),
      objective: c[11],
      gate: c[12],
    };
    if (!Number.isFinite(rec.annual) || !Number.isFinite(rec.maxdd)) continue;
    // Later epoch wins: a re-measurement supersedes the older bench's row.
    const prev = out.get(c[0]);
    if (prev == null || Number(e) >= Number(prev.epoch)) out.set(c[0], rec);
  }
  return out;
}

/** Back-compat: callers that only wanted the epoch. */
function ledgerEpochs(window = 'train') {
  const m = new Map();
  for (const [k, v] of ledgerRecords(window)) m.set(k, v.epoch);
  return m;
}

const fmField = (t, k) => (t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm')) || [])[1] || '';

const CANONICAL = ['epoch', 'window', 'annualReturn', 'sharpe', 'maxDrawdown', 'objective', 'gate'];

/**
 * The block as kb-stub writes it, PLUS any non-canonical keys the existing page already had.
 *
 * ⚠ 74 pages carry a `ranAt:` that the canonical shape does not include. Rewriting the block
 * from the ledger alone would have silently deleted the date each measurement ran — this repo
 * spends most of its guards on exactly that kind of quiet information loss, so the repair
 * carries unknown keys through instead of assuming it knows the full schema.
 *
 * `ranAt` is refreshed only when the EPOCH changed, i.e. a real re-measurement happened today.
 * A metrics-only change is usually a rescore (epoch 5 recomputed every objective without
 * running a single backtest), and stamping today's date on that would claim a run that never
 * occurred.
 */
function renderBlock(rec, window, existingLine) {
  const a = (rec.annual / 100).toFixed(4);
  const m = (rec.maxdd / 100).toFixed(4);

  const extras = [];
  if (existingLine) {
    const inner = (existingLine.match(/^normalized:\s*\{(.*)\}\s*$/) || [])[1] || '';
    const hadEpoch = (inner.match(/epoch:\s*(\d+)/) || [])[1];
    for (const part of inner.split(',')) {
      const k = part.split(':')[0].trim();
      if (!k || CANONICAL.includes(k)) continue;
      let v = part.slice(part.indexOf(':') + 1).trim();
      if (k === 'ranAt' && hadEpoch !== String(rec.epoch)) v = new Date().toISOString().slice(0, 10);
      extras.push(`${k}: ${v}`);
    }
  }

  return `normalized: { epoch: ${rec.epoch}, window: "${window}", annualReturn: ${a}, `
       + `sharpe: ${rec.sharpe}, maxDrawdown: ${m}, objective: ${rec.objective}, gate: ${rec.gate}`
       + (extras.length ? `, ${extras.join(', ')}` : '') + ' }';
}

function repair({ dry = false, window = 'train' } = {}) {
  const recs = ledgerRecords(window);
  // The window label the stub writes. Derived, so it follows an epoch's window change.
  const w = (() => {
    try {
      const x = require('./harness-config').window(window);
      return `${window.toUpperCase()} ${x.start.slice(0, 4)}-${x.end.slice(0, 4)}`;
    } catch { return 'TRAIN 2022-2023'; }
  })();

  const changed = [], already = [], noRow = [], noBlock = [];

  for (const f of fs.readdirSync(SDIR).filter(x => x.endsWith('.md'))) {
    const p = path.join(SDIR, f);
    const text = fs.readFileSync(p, 'utf8');
    const line = (text.match(/^normalized:\s*\{.*\}$/m) || [])[0];
    if (!line) { noBlock.push(f); continue; }

    const src = fmField(text, 'sourceFile').trim();
    const rec = recs.get(src);
    if (!rec) { noRow.push(f); continue; }

    const next = renderBlock(rec, w, line);
    if (line === next) { already.push(f); continue; }

    const have = (line.match(/epoch:\s*(\d+)/) || [])[1];
    const haveAnnual = (line.match(/annualReturn:\s*(-?[\d.]+)/) || [])[1];
    changed.push({
      file: f, from: have, to: rec.epoch,
      fromAnnual: haveAnnual, toAnnual: (rec.annual / 100).toFixed(4),
      metricsChanged: haveAnnual !== (rec.annual / 100).toFixed(4),
    });
    if (!dry) fs.writeFileSync(p, text.replace(line, next));
  }
  return { changed, already, noRow, noBlock };
}

if (require.main === module) {
  const dry = process.argv.includes('--dry');
  const r = repair({ dry });
  console.log(`[epoch-repair] ${dry ? 'would correct' : 'corrected'} ${r.changed.length} page(s)`);
  const byMove = {};
  for (const c of r.changed) byMove[`${c.from} -> ${c.to}`] = (byMove[`${c.from} -> ${c.to}`] || 0) + 1;
  for (const [k, v] of Object.entries(byMove)) console.log(`   epoch ${k.padEnd(10)} ${v} page(s)`);
  console.log(`[epoch-repair] already correct : ${r.already.length}`);
  console.log(`[epoch-repair] no ledger row   : ${r.noRow.length}  (left alone — the ledger is authoritative)`);
  console.log(`[epoch-repair] no normalized block: ${r.noBlock.length}`);
  if (dry) console.log('[epoch-repair] (--dry — nothing written)');
}

module.exports = { repair, ledgerEpochs, ledgerRecords, renderBlock };
