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

/** sourceFile -> epoch, taken from the row that MEASURED it (terminal rows only). */
function ledgerEpochs(window = 'train') {
  const file = path.join(ROOT, `harness/normalize-${window}.tsv`);
  const out = new Map();
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch { return out; }
  for (const line of text.split('\n').slice(1)) {
    const c = line.split('\t');
    if (!c[0] || c[3] !== 'normalized') continue;
    const e = c[13] && c[13].trim();
    if (!e) continue;
    // Later rows win: a re-measurement under a newer epoch supersedes the older one.
    const prev = out.get(c[0]);
    out.set(c[0], prev == null ? e : String(Math.max(Number(prev), Number(e))));
  }
  return out;
}

const fmField = (t, k) => (t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm')) || [])[1] || '';

function repair({ dry = false, window = 'train' } = {}) {
  const epochs = ledgerEpochs(window);
  const changed = [], already = [], noRow = [], noBlock = [];

  for (const f of fs.readdirSync(SDIR).filter(x => x.endsWith('.md'))) {
    const p = path.join(SDIR, f);
    const text = fs.readFileSync(p, 'utf8');
    const line = (text.match(/^normalized:\s*\{.*\}$/m) || [])[0];
    if (!line) { noBlock.push(f); continue; }

    const src = fmField(text, 'sourceFile').trim();
    const want = epochs.get(src);
    if (!want) { noRow.push(f); continue; }

    const have = (line.match(/epoch:\s*(\d+)/) || [])[1];
    if (have === want) { already.push(f); continue; }

    changed.push({ file: f, from: have, to: want });
    if (!dry) {
      fs.writeFileSync(p, text.replace(line, line.replace(/epoch:\s*\d+/, `epoch: ${want}`)));
    }
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

module.exports = { repair, ledgerEpochs };
