/**
 * consumption.js — the record of what each stage has already consumed.
 *
 * The gap this fills (docs/consolidation-plan.md §2): nothing recorded which strategies or
 * families had been through study or enhance. Family pages carry
 * `sources: { normalized, study, enhance }` and EVERY page reads `study: 0, enhance: 0` —
 * including families studied to exhaustion and the small-cap family that produced a validated
 * enhancement. The bookkeeping existed in form and was dead in practice, so a restarted loop
 * could not tell new work from repeated work.
 *
 * Append-only TSV rather than a frontmatter field, for three reasons:
 *   - concurrent agents append instead of read-modify-write, so they cannot clobber each other;
 *   - it survives page regeneration (wiki-family-build.js rewrites §3 wholesale);
 *   - "what has never been touched" is one scan, not a walk over every page.
 * Same reasoning that made harness/normalize-*.tsv a ledger.
 *
 * ⚠ Tracked in git on purpose. The normalize ledger was gitignored, silently regressed from
 * ~119 rows to 18, and blocked every family page from regenerating until it was rebuilt.
 *
 * Usage:
 *   const c = require('./consumption');
 *   c.record({ key, kind: 'family', stage: 'study', runId, outcome, note });
 *   c.events({ stage: 'study' });
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const FILE = path.join(ROOT, 'data/consumption.tsv');

const COLUMNS = ['key', 'kind', 'stage', 'runId', 'at', 'outcome', 'note'];
const KINDS = new Set(['strategy', 'family', 'concept', 'type']);
const STAGES = new Set(['normalize', 'ingest', 'study', 'enhance', 'integrate',
                        'concept-backfill', 'validate', 'oos']);

const clean = v => String(v == null ? '' : v).replace(/[\t\r\n]/g, ' ').trim();

function ensure() {
  if (!fs.existsSync(FILE)) {
    fs.mkdirSync(path.dirname(FILE), { recursive: true });
    fs.writeFileSync(FILE, COLUMNS.join('\t') + '\n');
  }
}

/** Every recorded event, optionally filtered. */
function events({ stage = null, kind = null, key = null } = {}) {
  ensure();
  const out = [];
  for (const line of fs.readFileSync(FILE, 'utf8').split('\n').slice(1)) {
    if (!line.trim()) continue;
    const c = line.split('\t');
    const e = Object.fromEntries(COLUMNS.map((k, i) => [k, c[i] || '']));
    if (stage && e.stage !== stage) continue;
    if (kind && e.kind !== kind) continue;
    if (key && e.key !== key) continue;
    out.push(e);
  }
  return out;
}

/**
 * Append one event. Returns false when an identical (key, stage, runId) is already
 * recorded, so seeding and re-runs are idempotent without needing a rewrite.
 */
function record({ key, kind, stage, runId = '', outcome = '', note = '', at = null }) {
  if (!key) throw new Error('consumption.record: key is required');
  if (!KINDS.has(kind)) throw new Error(`consumption.record: unknown kind "${kind}"`);
  if (!STAGES.has(stage)) throw new Error(`consumption.record: unknown stage "${stage}"`);
  ensure();
  const dup = events({ stage, key }).some(e => e.runId === String(runId));
  if (dup) return false;
  const row = [key, kind, stage, runId, at || new Date().toISOString(), outcome, note]
    .map(clean).join('\t');
  fs.appendFileSync(FILE, row + '\n');
  return true;
}

/** Set of keys that have any event for a stage — the "already consumed" test. */
function consumed(stage, kind = null) {
  return new Set(events({ stage, kind }).map(e => e.key));
}

module.exports = { record, events, consumed, FILE, COLUMNS, KINDS, STAGES };
