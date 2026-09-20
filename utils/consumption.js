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

/**
 * `members` / `memberHash` were appended in 2026-09 (see `memberState`). Readers that index
 * 0..6 ignore them, the same way ledger readers ignore the normalize ledger's 14th `epoch`
 * column. Rows written before the change simply have them empty, which reads as "unknown
 * membership at the time" — and unknown is treated as stale, so those families resurface once.
 */
const COLUMNS = ['key', 'kind', 'stage', 'runId', 'at', 'outcome', 'note', 'members', 'memberHash'];
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
function record({ key, kind, stage, runId = '', outcome = '', note = '', at = null,
                  members = null, memberHash = null }) {
  if (!key) throw new Error('consumption.record: key is required');
  if (!KINDS.has(kind)) throw new Error(`consumption.record: unknown kind "${kind}"`);
  if (!STAGES.has(stage)) throw new Error(`consumption.record: unknown stage "${stage}"`);
  ensure();
  const dup = events({ stage, key }).some(e => e.runId === String(runId));
  if (dup) return false;
  // Stamp what the family looked like WHEN it was consumed. Without this the ledger can only
  // answer "has this family ever been studied", which is why a family that gained members
  // after its study never reappeared in the queue.
  let m = members, h = memberHash;
  if (kind === 'family' && m == null && h == null) {
    const st = memberState(key);
    m = st.count; h = st.hash;
  }
  const row = [key, kind, stage, runId, at || new Date().toISOString(), outcome, note,
               m == null ? '' : m, h || ''].map(clean).join('\t');
  fs.appendFileSync(FILE, row + '\n');
  return true;
}

/**
 * What a family's membership looks like RIGHT NOW: the count and a hash of the sorted member
 * source files. The hash is what makes "changed since last studied" exact — a count alone
 * cannot see a swap, and the wiki is the only place membership is recorded.
 */
function memberState(family) {
  const PAGES = path.join(ROOT, 'wiki/strategies');
  if (!fs.existsSync(PAGES)) return { count: 0, hash: '' };
  const members = [];
  for (const p of fs.readdirSync(PAGES).filter(f => f.endsWith('.md'))) {
    const t = fs.readFileSync(path.join(PAGES, p), 'utf8');
    const fam = (t.match(/^family:\s*(.*)$/m) || [])[1];
    if (!fam || fam.trim() !== family) continue;
    const src = (t.match(/^sourceFile:\s*(.*)$/m) || [])[1];
    members.push((src || p).trim());
  }
  members.sort();
  const hash = members.length
    ? require('crypto').createHash('sha256').update(members.join('\n')).digest('hex').slice(0, 12)
    : '';
  return { count: members.length, hash, members };
}

/**
 * Has `family` changed since the last event for `stage`?
 * @returns {{stale:boolean, reason:string, last:object|null, now:{count:number,hash:string}}}
 */
function staleFor(stage, family) {
  const evs = events({ stage, kind: 'family', key: family });
  const now = memberState(family);
  if (!evs.length) return { stale: true, reason: 'never consumed', last: null, now };
  const last = evs[evs.length - 1];
  if (!last.memberHash) {
    // Recorded before membership was tracked — treat as stale ONCE rather than assume current.
    return { stale: true, reason: 'last run predates membership tracking', last, now };
  }
  if (last.memberHash !== now.hash) {
    const delta = now.count - (parseInt(last.members, 10) || 0);
    return { stale: true, last, now,
             reason: delta > 0 ? `${delta} new member(s) since last ${stage}`
                               : `membership changed since last ${stage}` };
  }
  return { stale: false, reason: 'up to date', last, now };
}

/** Set of keys that have any event for a stage — the "already consumed" test. */
function consumed(stage, kind = null) {
  return new Set(events({ stage, kind }).map(e => e.key));
}

module.exports = { record, events, consumed, memberState, staleFor,
                   FILE, COLUMNS, KINDS, STAGES };
