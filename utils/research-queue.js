/**
 * research-queue.js — the merged loop's queue and findings ledger.
 *
 * One queue per family holding BOTH kinds of idea (`understand` / `improve`), replacing
 * `study/<family>/questions.json` + `enhance/ideas-queue.json`. Changes C and D of
 * `docs/proposals/merged-research-loop.md`.
 *
 * ## Why this is code and not another paragraph
 *
 * Both contracts previously lived only in prose — in two program.md files and eight agent
 * definitions. Prose drifted: within one day of fixing the enhance resume nudge, the study copy
 * still named a superseded epoch. A contract that nothing can check is a contract that quietly
 * stops holding.
 *
 * ## The part that makes the loop a loop
 *
 * `context(family)` is what a generator MUST read before proposing. Today that happens only
 * because an agent happens to read the right files; when it doesn't, the round re-proposes work
 * already done — ETF动量's idea-1 flagged itself in its own reasoning as 新颖度为零, a
 * re-measurement of a config the family already held.
 *
 * Two links make that auditable, and they point at each other:
 *   - a finding's `spawned` lists the ideas it produced (or `none`);
 *   - an idea's `from` lists the results that prompted it.
 * An idea with an empty `from` is not forbidden — sometimes a genuinely new thought arrives — but
 * it is *ungrounded*, it ranks last, and `context()` reports how many there are.
 *
 * ## finding vs implication
 *
 * `finding` is WHAT HAPPENED: "sharpe 8.44 -> 3.16 -> 1.10 as the volume floor rises."
 * `implication` is WHAT IT CHANGES ABOUT WHAT WE DO NEXT, and must either
 *   - CLOSE a direction: "no_buy_after_day is monotone-worsening from 2 — that knob is closed", or
 *   - OPEN one: "the 2e6 floor is too loose; retest every member at 1e7 before trusting any Δ".
 * A restatement of the finding is a schema violation. Code cannot judge semantics, but it can
 * refuse the empty case and the literal-copy case, which is most of what goes wrong.
 *
 * Usage:
 *   const rq = require('./research-queue');
 *   rq.context('ETF溢价')                  // what the generators must read first
 *   rq.add('ETF溢价', { kind: 'understand', title, hypothesis, from: ['q-1'] })
 *   rq.recordFinding('ETF溢价', { qId, finding, implication, spawned, edgeRef, ... })
 *
 *   node utils/research-queue.js <family>            # show the queue + context
 *   node utils/research-queue.js <family> --lint     # contract violations only
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const dir = family => path.join(process.env.JQ_RESEARCH_DIR || path.join(ROOT, 'study'), family);
const queueFile = family => path.join(dir(family), 'queue.json');
const findingsFile = family => path.join(dir(family), 'findings.tsv');

const KINDS = new Set(['understand', 'improve']);
const STATUSES = new Set(['queued', 'active', 'blocked', 'answered', 'dropped', 'done']);

/**
 * findings.tsv columns. The first 9 are the original study ledger; the last 3 are appended, the
 * same migration `consumption.tsv` used for `members`/`memberHash` — readers indexing 0..8 are
 * unaffected and older rows simply read empty.
 */
const FINDING_COLUMNS = [
  'qId', 'type', 'component_or_param', 'metric_delta', 'window', 'finding', 'confidence',
  'flags', 'description',
  'implication', 'spawned', 'edgeRef',
];

const clean = v => String(v == null ? '' : v).replace(/[\t\r\n]/g, ' ').trim();

// ── queue ───────────────────────────────────────────────────────────────────

function load(family) {
  try { return JSON.parse(fs.readFileSync(queueFile(family), 'utf8')); } catch { return []; }
}

function save(family, entries) {
  fs.mkdirSync(dir(family), { recursive: true });
  fs.writeFileSync(queueFile(family), JSON.stringify(entries, null, 2) + '\n');
  return entries.length;
}

/** Contract violations in one entry. Returns [] when it is well-formed. */
function validate(e) {
  const bad = [];
  if (!e || typeof e !== 'object') return ['not an object'];
  if (!e.id) bad.push('missing id');
  if (!KINDS.has(e.kind)) bad.push(`kind must be understand|improve (got ${JSON.stringify(e.kind)})`);
  if (!e.title) bad.push('missing title');
  if (e.status && !STATUSES.has(e.status)) bad.push(`unknown status ${JSON.stringify(e.status)}`);
  if (!Array.isArray(e.from)) bad.push('from must be an array (use [] for an ungrounded idea)');
  // An `improve` idea that names no edge is not refused — the family may not have one yet — but
  // once the family HAS a measured edge, an improve idea that ignores it is off-mechanism by
  // default, which is what the prior exists to prevent. Reported by lint, not blocked here.
  return bad;
}

function add(family, entry) {
  const entries = load(family);
  const e = {
    id: entry.id || `idea-${entries.length + 1}`,
    kind: entry.kind, title: entry.title,
    hypothesis: entry.hypothesis || null,
    why: entry.why || null,
    design: entry.design || null,
    // ⚠ NOT defaulted. `from` is the whole point of the loop closing — omitting it silently
    // would make "I didn't check what was already tried" indistinguishable from "I checked and
    // nothing applies". An explicit `from: []` is allowed and is reported as ungrounded; an
    // absent one is a contract error.
    from: entry.from,
    edgeRef: entry.edgeRef || null,
    rank: entry.rank == null ? 50 : entry.rank,
    status: entry.status || 'queued',
    note: entry.note || undefined,
    result: entry.result || null,
  };
  const bad = validate(e);
  if (bad.length) throw new Error(`research-queue.add(${family}): ${bad.join('; ')}`);
  entries.push(e);
  save(family, entries);
  return e;
}

// ── findings ────────────────────────────────────────────────────────────────

function findings(family) {
  const f = findingsFile(family);
  let text;
  try { text = fs.readFileSync(f, 'utf8'); } catch { return []; }
  const lines = text.split('\n').filter(l => l.trim());
  if (!lines.length) return [];
  const body = /^qId\t/.test(lines[0]) ? lines.slice(1) : lines;
  return body.map(l => {
    const c = l.split('\t');
    return Object.fromEntries(FINDING_COLUMNS.map((k, i) => [k, c[i] || '']));
  });
}

/**
 * `implication` must say what changes, not repeat what happened. Code cannot judge that, but the
 * two failures it CAN catch are the two that actually occur: an empty field, and a copy of the
 * finding with cosmetic edits.
 */
function implicationProblems({ finding, implication }) {
  const bad = [];
  const i = clean(implication), f = clean(finding);
  if (!i) return ['implication is empty — say what this changes about what we do next, or that it closes a direction'];
  const norm = s => s.replace(/[\s。，．,.;；:：()（）「」"'`*_-]/g, '');
  if (norm(i) === norm(f)) bad.push('implication is a restatement of finding');
  if (i.length < 12) bad.push('implication is too short to say anything actionable');
  return bad;
}

function recordFinding(family, row) {
  const probs = implicationProblems(row);
  if (probs.length) throw new Error(`research-queue.recordFinding(${family}): ${probs.join('; ')}`);
  const f = findingsFile(family);
  fs.mkdirSync(dir(family), { recursive: true });
  if (!fs.existsSync(f)) fs.writeFileSync(f, FINDING_COLUMNS.join('\t') + '\n');
  const line = FINDING_COLUMNS.map(k => clean(row[k] == null ? (k === 'spawned' ? 'none' : '') : row[k]));
  fs.appendFileSync(f, line.join('\t') + '\n');

  // Close the idea this answers. Without it a run leaves its own finished ideas sitting at
  // `queued`, so the next round re-reads them as open work — the first trial did exactly that,
  // recording two findings while both ideas still showed `queued`. The link is the id: a finding
  // whose qId matches an entry answers that entry.
  const entries = load(family);
  const hit = entries.find(e => e.id === row.qId && e.status !== 'answered');
  if (hit) {
    hit.status = 'answered';
    hit.result = String(row.finding || '').slice(0, 300);
    save(family, entries);
  }
  return true;
}

// ── what a generator must read before proposing ─────────────────────────────

/** §2 rows already marked `rejected` — directions measured and not kept. */
function rejectedVariants(family) {
  const p = path.join(ROOT, 'wiki/families', `${family}.md`);
  let body;
  try { body = fs.readFileSync(p, 'utf8'); } catch { return []; }
  const out = [];
  let inSec = false;
  for (const line of body.split('\n')) {
    if (/^## 2\./.test(line)) { inSec = true; continue; }
    if (/^## 3\./.test(line)) inSec = false;
    if (!inSec || !line.trim().startsWith('|')) continue;
    const c = line.replace(/^\||\|$/g, '').split(/(?<!\\)\|/);
    if (c.length !== 9) continue;
    if (c[7].trim() === 'rejected') out.push({ variant: c[0].trim(), change: c[2].trim(), why: c[8].trim() });
  }
  return out;
}

/** The family's declared edge claims, if any. */
function edges(family) {
  const p = path.join(ROOT, 'wiki/families', `${family}.md`);
  let body;
  try { body = fs.readFileSync(p, 'utf8'); } catch { return []; }
  const block = (body.match(/^edge:\n((?:[ ]+.*\n)+)/m) || [])[1];
  if (!block) return [];
  return block.split(/\n(?=\s+- )/).map(chunk => ({
    name: (chunk.match(/name:\s*(.*)/) || [])[1] || '',
    kind: (chunk.match(/kind:\s*(.*)/) || [])[1] || '',
    status: (chunk.match(/status:\s*(.*)/) || [])[1] || '',
  })).filter(e => e.name);
}

/**
 * Everything a generator is required to have read. Returning it as one object is the point: an
 * agent that calls this cannot claim it did not know what had already been tried.
 */
function context(family) {
  const q = load(family);
  const fnd = findings(family);
  return {
    family,
    edges: edges(family),
    queue: q,
    open: q.filter(e => e.status === 'queued' || e.status === 'active'),
    findings: fnd,
    implications: fnd.filter(f => f.implication).map(f => ({ qId: f.qId, implication: f.implication })),
    closedDirections: fnd.filter(f => /closed|关闭|已闭|不再|封闭/.test(f.implication || ''))
      .map(f => ({ qId: f.qId, implication: f.implication })),
    rejected: rejectedVariants(family),
    ungrounded: q.filter(e => !(e.from || []).length).map(e => e.id),
    unspawned: fnd.filter(f => (f.spawned || 'none') === 'none' && /high/i.test(f.confidence || ''))
      .map(f => f.qId),
  };
}

function lint(family) {
  const c = context(family);
  const out = [];
  for (const e of c.queue) for (const b of validate(e)) out.push(`${e.id || '?'}: ${b}`);
  const measured = c.edges.filter(e => e.status === 'measured').map(e => e.name);
  if (measured.length) {
    for (const e of c.open.filter(x => x.kind === 'improve' && !x.edgeRef)) {
      out.push(`${e.id}: improve idea names no edgeRef, but the family has a measured edge (${measured.join(', ')}) — off-mechanism by default`);
    }
  }
  for (const id of c.ungrounded) out.push(`${id}: from[] is empty — ungrounded, ranks last`);
  for (const q of c.unspawned) out.push(`${q}: high-confidence finding with spawned=none — nobody followed it up`);
  return out;
}

module.exports = {
  load, save, add, validate, findings, recordFinding, implicationProblems,
  context, lint, edges, rejectedVariants, FINDING_COLUMNS, KINDS,
};

if (require.main === module) {
  const argv = process.argv.slice(2);
  const family = argv.find(a => !a.startsWith('--'));
  if (!family) {
    console.error('usage: node utils/research-queue.js <family> [--lint]');
    process.exit(1);
  }
  if (argv.includes('--lint')) {
    const problems = lint(family);
    console.log(problems.length
      ? `[rq] ${family}: ${problems.length} contract issue(s)\n` + problems.map(p => '   ' + p).join('\n')
      : `[rq] ${family}: queue is well-formed`);
    process.exit(problems.length ? 1 : 0);
  }
  const c = context(family);
  console.log(`[rq] ${family}`);
  console.log(`  edge claims   : ${c.edges.length ? c.edges.map(e => `${e.name}(${e.status})`).join(', ') : 'NONE — unanswered'}`);
  console.log(`  queue         : ${c.queue.length} (${c.open.length} open)`);
  console.log(`  findings      : ${c.findings.length}, of which ${c.implications.length} carry an implication`);
  console.log(`  closed dirs   : ${c.closedDirections.length}`);
  console.log(`  rejected §2   : ${c.rejected.length}`);
  if (c.ungrounded.length) console.log(`  ⚠ ungrounded  : ${c.ungrounded.join(', ')}`);
  if (c.unspawned.length) console.log(`  ⚠ unfollowed  : ${c.unspawned.join(', ')}`);
}
