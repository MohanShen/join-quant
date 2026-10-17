/**
 * consumption-seed.js — backfill data/consumption.tsv from evidence already on disk.
 *
 * One-off. Everything here is reconstructed from a durable artefact, never guessed: the normalize
 * ledger, study/manifest.json, the validated_strategies/ headers and wiki/experiments/. Where a
 * date is unknown the artefact's own timestamp is used and the note says so, so a reconstructed
 * event is never mistaken for a live one.
 *
 * ## ⚠⚠ It is NOT idempotent, and it has no business being require()d
 *
 * The header used to claim "idempotent". It is not, and both halves of that went wrong together on
 * 2026-10-17: a bare `require('./utils/consumption-seed')` — typed to check the module loads after
 * a refactor — **appended 82 duplicate rows to `data/consumption.tsv`**, which is tracked,
 * append-only, and the ledger the VAL and OOS budgets are computed from. (The budgets were
 * unharmed: every row was `stage: normalize`, which neither reads. The write was uncommitted and
 * was reverted.)
 *
 * **Why dedup cannot work here.** `consumption.record()` de-duplicates on `(stage, key, runId)`,
 * and `runId` is the constant `seed-ledger-train` — but the KEY comes from
 * `data/copy-queue.json`'s `copied` map, and that map is rebuilt from scratch by every discovery
 * run while **JoinQuant re-mints `postId` on every request**. So the same strategy gets a
 * different key on a later run and the dedup has nothing to match. This is precisely the failure
 * CLAUDE.md names: *"Never key a store, a dedup or a join on an id."* The already-written rows
 * live under their original keys, so re-keying this seeder now would not make it idempotent
 * either — it is finished work, and the fix is to stop it running by accident.
 *
 * ⚠ ENTRY-POINT GUARD below. CLAUDE.md: "every entry point in `utils/` needs one" — the audit that
 * produced that rule looked for files reading `process.argv`, and this one takes no arguments, so
 * it was missed. The hazard is the same shape as the missing guard on `strategy-normalize.js`,
 * which spent 42 backtest minutes on a bare require.
 */
const fs = require('fs');
const path = require('path');
const c = require('./consumption');

const ROOT = path.resolve(__dirname, '..');

// Written as an early return rather than a main() wrapper, the same way dq-finalize.js does it:
// the body is top-level script code and indenting it into a function would be a larger edit than
// the fix warrants. `return` at CommonJS module top level is legal — the module body is already
// inside a function wrapper.
if (require.main !== module) { module.exports = {}; return; }
const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

let n = 0;
const add = e => { if (c.record(e)) n++; };

// ── normalize: one event per ledger row ──────────────────────────────────────
const copied = readJson(path.join(ROOT, 'data/copy-queue.json'), {}).copied || {};
const keyOf = {};
for (const [k, v] of Object.entries(copied)) if (v && v.sourceFile) keyOf[v.sourceFile] = k;

// Columns via `utils/ledger.js`; `objective`/`gate` are printed verbatim into the note, so the
// RAW STRINGS are used rather than parsed numbers.
for (const row of require('./ledger').rows()) {
  const base = row.sourceFile.replace('strategies/', '');
  add({
    key: keyOf[base] || keyOf[base.replace(/^\d{4}-\d{2}-\d{2}_/, '')] || row.sourceFile,
    kind: 'strategy', stage: 'normalize', runId: 'seed-ledger-train',
    outcome: row.status,
    note: `objective=${row.raw[11] || '-'} gate=${row.gate || '-'} file=${base}`,
  });
}

// ── study: manifest status is the durable record of family-level completion ──
for (const f of readJson(path.join(ROOT, 'study/manifest.json'), [])) {
  if (f.status !== 'done') continue;
  const findings = path.join(ROOT, 'study', f.family, 'findings.tsv');
  const rows = fs.existsSync(findings)
    ? fs.readFileSync(findings, 'utf8').split('\n').filter(l => l.trim()).length - 1 : 0;
  add({
    key: f.family, kind: 'family', stage: 'study', runId: 'seed-manifest',
    outcome: 'exhausted',
    note: `${rows} findings row(s); reconstructed from study/manifest.json status=done`,
  });
}

// ── enhance: the validated_strategies/ headers are the durable record ────────
// Key the event by the FAMILY it descends from, not by the session tag: the point of the
// ledger is to answer "has this family been enhanced", and a session-tag key answers nothing.
// The family is resolved from the header's `source:` pointer -> that strategy page's `family:`.
function familyOfSource(head) {
  const m = head.match(/^#\s*source:\s*(strategies\/\S+\.py)/m);
  if (!m) return null;
  const dir = path.join(ROOT, 'wiki/strategies');
  if (!fs.existsSync(dir)) return null;
  for (const p of fs.readdirSync(dir).filter(f => f.endsWith('.md'))) {
    const t = fs.readFileSync(path.join(dir, p), 'utf8');
    if ((t.match(/^sourceFile:\s*(\S+)/m) || [])[1] === m[1]) {
      return (t.match(/^family:\s*(.+)$/m) || [])[1].trim() || null;
    }
  }
  return null;
}

const vs = path.join(ROOT, 'validated_strategies');
for (const f of fs.existsSync(vs) ? fs.readdirSync(vs).filter(f => f.endsWith('.py')) : []) {
  const head = fs.readFileSync(path.join(vs, f), 'utf8').slice(0, 2000);
  const get = k => (head.match(new RegExp(`^#\\s*${k}:\\s*(.+)$`, 'm')) || [])[1] || '';
  const fam = familyOfSource(head);
  add({
    key: fam || `UNRESOLVED:${f.replace(/\.py$/, '')}`,
    kind: 'family', stage: 'enhance', runId: f.replace(/\.py$/, ''),
    outcome: get('gate_val').split(/\s+/)[0] === 'pass' ? 'val-pass' : 'val-dq',
    note: `train=${get('train_objective').split(/\s+/)[0]} val=${get('val_objective').split(/\s+/)[0]}`
        + ` base=${get('baseExpId').split(/\s+/)[0]}${fam ? '' : ' ⚠ family unresolved from header'}`,
  });
}
console.log(`[seed] appended ${n} event(s) -> ${path.relative(ROOT, c.FILE)}`);
const by = {};
for (const e of c.events()) by[e.stage] = (by[e.stage] || 0) + 1;
console.log('[seed] events by stage:', JSON.stringify(by));
