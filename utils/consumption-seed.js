/**
 * consumption-seed.js — backfill data/consumption.tsv from evidence already on disk.
 *
 * One-off (idempotent). Everything here is reconstructed from a durable artefact, never
 * guessed: the normalize ledger, study/manifest.json, the validated_strategies/ headers and
 * wiki/experiments/. Where a date is unknown the artefact's own timestamp is used and the
 * note says so, so a reconstructed event is never mistaken for a live one.
 */
const fs = require('fs');
const path = require('path');
const c = require('./consumption');

const ROOT = path.resolve(__dirname, '..');
const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

let n = 0;
const add = e => { if (c.record(e)) n++; };

// ── normalize: one event per ledger row ──────────────────────────────────────
const copied = readJson(path.join(ROOT, 'data/copy-queue.json'), {}).copied || {};
const keyOf = {};
for (const [k, v] of Object.entries(copied)) if (v && v.sourceFile) keyOf[v.sourceFile] = k;

for (const line of fs.readFileSync(path.join(ROOT, 'harness/normalize-train.tsv'), 'utf8').split('\n').slice(1)) {
  const col = line.split('\t');
  if (!col[0]) continue;
  const base = col[0].replace('strategies/', '');
  add({
    key: keyOf[base] || keyOf[base.replace(/^\d{4}-\d{2}-\d{2}_/, '')] || col[0],
    kind: 'strategy', stage: 'normalize', runId: 'seed-ledger-train',
    outcome: col[3], note: `objective=${col[11] || '-'} gate=${col[12] || '-'} file=${base}`,
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
