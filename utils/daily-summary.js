/**
 * daily-summary.js — write one markdown file per day's pipeline run, then (optionally)
 * commit and push it.
 *
 * Why a file rather than a log line. `data/daily-logs/` is gitignored and rotates; the run log
 * inside `daily-state.json` is machine-shaped and bounded to 120 entries. Neither survives as
 * something a person can read a week later to answer "what did this thing actually do while I
 * was away". The summary is that record: one file, tracked, per day.
 *
 * ⚠ It reports what MOVED, not what ran. Three times in this repo a scheduled job exited 0
 * while accomplishing nothing — a branch gate that no longer matched, a session pin to a
 * deleted branch, a manifest that disagreed with the ledger. So the summary leads with the
 * artefact delta (git working-tree changes + ledger/consumption counts) rather than with the
 * stage outcomes, because "enhance -> ran" is exactly the line those failures produced.
 *
 * ⚠ Commit scope is `git add -u` (tracked modifications) plus an ENUMERATED set of paths whose
 * new files a run legitimately produces — see SAFE_ADD. Not `git add -A`: that once staged a
 * git worktree as a gitlink, which a clone cannot resolve. Anything untracked outside the set
 * is listed in the summary under "Untracked and NOT committed" rather than swept in silently.
 *
 * Usage:
 *   node utils/daily-summary.js                 # write today's summary
 *   node utils/daily-summary.js --commit        # + commit and push it
 *   node utils/daily-summary.js --dry           # print it, write nothing
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'docs/daily');

const state = require('./daily-state');

const sh = (cmd, args, opt = {}) => {
  try { return execFileSync(cmd, args, { encoding: 'utf8', cwd: ROOT, timeout: 120000, ...opt }).trim(); }
  catch (e) { return `__ERR__ ${String((e.stdout || '') + (e.stderr || '') + e.message).slice(0, 300)}`; }
};
const ok = s => typeof s === 'string' && !s.startsWith('__ERR__');

const today = () => new Date().toISOString().slice(0, 10);

/** Rows the ledger holds right now, by status. */
function ledgerCounts() {
  const f = path.join(ROOT, 'harness/normalize-train.tsv');
  const out = {};
  try {
    for (const l of fs.readFileSync(f, 'utf8').split('\n').slice(1)) {
      const c = l.split('\t');
      if (c[0]) out[c[3]] = (out[c[3]] || 0) + 1;
    }
  } catch { /* gitignored and may be absent — reported as unknown */ }
  return out;
}

/** Consumption events recorded today, which is the durable proof a stage did something. */
function eventsToday() {
  try {
    const c = require('./consumption');
    return c.events({}).filter(e => String(e.at).slice(0, 10) === today());
  } catch { return []; }
}

function parseStatusLine(l) {
  if (!l || !l.trim()) return null;
  const m = l.match(/^\s*(\S{1,2})\s+(.*)$/);
  if (!m) return null;
  // A rename is reported as `old -> new`; the new name is what exists now.
  const file = m[2].split(' -> ').pop().replace(/^"(.*)"$/, '$1');
  return file ? { status: m[1], file } : null;
}

/** Working-tree changes = what this run actually produced since the last commit. */
function changedFiles() {
  const s = sh('git', ['status', '--short']);
  if (!ok(s) || !s) return [];
  // ⚠ Parse by SHAPE, not by column offset. `git status --short` puts the status in two fixed
  // columns, so `slice(3)` is the path — but only if the line still has both. `sh()` trims the
  // whole output, which eats the leading space of an unstaged ` M`, and every fixed offset on
  // that one line then slips by a character: the 2026-09-21 summary published the change as
  // `ata/daily-state.json`. A wrong path in the day's record is worse than a missing one,
  // because it reads as a real file.
  return s.split('\n').map(parseStatusLine).filter(Boolean);
}

function build() {
  const s = state.load();
  const day = today();
  const runs = (s.runs || []).filter(r => String(r.endedAt || r.at).slice(0, 10) === day);
  const daily = require('./daily-pipeline');
  const q = daily.queues();
  const changed = changedFiles();
  const events = eventsToday();
  const counts = ledgerCounts();
  const pool = state.deferred();
  const due = state.dueForRetry(daily.SLOW_SKIP_MIN);

  const L = [];
  L.push(`# Daily pipeline — ${day}`, '');

  // Lead with what moved, not with what ran. See the header note.
  // The summary file itself is not evidence that anything moved, and neither is an untracked
  // file the commit will not stage. Count only what a stage actually produced.
  const substantive = changed.filter(c =>
    !c.file.startsWith('docs/daily/') && !c.file.startsWith('utils/daily-summary'));
  const moved = substantive.length > 0 || events.length > 0;
  L.push(moved
    ? `**Moved.** ${substantive.length} file(s) changed, ${events.length} consumption event(s) recorded.`
    : '**Nothing moved.** No file changed and no consumption event was recorded — '
      + 'treat a clean exit today as a no-op, not as success.');
  L.push('');

  L.push('## Stages', '');
  if (!runs.length) {
    L.push('_No stage ran today._', '');
  } else {
    L.push('| stage | outcome | note |', '|---|---|---|');
    for (const r of runs) {
      L.push(`| ${r.stage} | \`${r.outcome}\` | ${String(r.note || '').replace(/\|/g, '\\|').slice(0, 160)} |`);
    }
    L.push('');
  }

  L.push('## Queues after the run', '');
  L.push('| queue | depth |', '|---|---|');
  L.push(`| enhance | ${q.enhance.length} |`);
  L.push(`| study | ${q.study.length} |`);
  L.push(`| normalize | ${q.normalize.total} (${q.normalize.pending.length} pending + ${q.normalize.retry.length} deferred-retry) |`);
  L.push(`| discover | ${q.discover.uncopied} uncopied of ${q.discover.total} |`);
  L.push('');

  if (Object.keys(counts).length) {
    L.push('## Ledger', '');
    L.push(Object.entries(counts).sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `- ${k}: **${v}**`).join('\n'), '');
  }

  L.push('## Deferred pool', '');
  L.push(`${Object.keys(pool).length} parked, ${due.length} retryable at ${daily.SLOW_SKIP_MIN} min.`, '');

  if (events.length) {
    L.push('## Consumption recorded today', '');
    for (const e of events.slice(0, 20)) {
      L.push(`- \`${e.stage}\` ${e.key} → ${e.outcome || '—'}${e.note ? ` (${String(e.note).slice(0, 80)})` : ''}`);
    }
    L.push('');
  }

  const unsafe = changed.filter(c => c.status === '??' &&
    !SAFE_ADD.some(p => c.file === p || c.file.startsWith(p + '/')));
  if (unsafe.length) {
    L.push('## ⚠ Untracked and NOT committed', '');
    L.push('These fall outside the commit allowlist, so the daily commit left them alone:', '');
    for (const u of unsafe.slice(0, 15)) L.push(`- \`${u.file}\``);
    L.push('');
  }

  if (changed.length) {
    L.push('## Files changed', '');
    for (const c of changed.slice(0, 40)) L.push(`- \`${c.status}\` ${c.file}`);
    if (changed.length > 40) L.push(`- …and ${changed.length - 40} more`);
    L.push('');
  }

  // `timeout` belongs here too: the stage had work in hand and was cut off, so tomorrow's run
  // inherits it. Leaving it out of this section is how a cutoff reads as a normal day.
  const blocked = runs.filter(r => ['blocked', 'error', 'timeout'].includes(r.outcome));
  if (blocked.length) {
    L.push('## ⚠ Needs a human', '');
    for (const b of blocked) L.push(`- **${b.stage}** (\`${b.outcome}\`): ${b.note}`);
    L.push('');
  }

  const budget = sh('node', [path.join(__dirname, 'jq-budget.js')]);
  L.push('---', '', `_Budget at write time: ${ok(budget) ? budget : 'unavailable'}. `
    + `Generated by \`utils/daily-summary.js\`._`);

  return { day, markdown: L.join('\n') + '\n', moved, runs, changed, events };
}

/**
 * Directories whose NEW files a daily run legitimately produces, and which are therefore safe
 * to stage untracked.
 *
 * `git add -u` alone would leave real output behind — a normalize pass creates wiki stub pages
 * and `data/series/*.json`, an enhance pass creates `enhance/candidates/*.py`. But blanket
 * `git add -A` is not the answer either: it once staged a git worktree as a gitlink, which a
 * clone cannot resolve. So the set is enumerated. Anything appearing outside it is reported in
 * the summary and left for a human, which is the right default for an unattended job.
 */
const SAFE_ADD = [
  'docs/daily', 'wiki', 'data/series', 'data/daily-state.json', 'data/deferred.json',
  'data/consumption.tsv', 'data/components.tsv', 'enhance/candidates', 'enhance/results.tsv',
  'enhance/ideas-queue.json', 'enhance/loop-state.json', 'strategies', 'validated_strategies',
];

/**
 * Commit the day's work and push.
 *
 * A push failure is reported, never thrown: the summary is already on disk and the next run
 * carries it forward.
 */
function commitAndPush(file, { day, moved }) {
  const rel = path.relative(ROOT, file);
  const add1 = sh('git', ['add', '-u']);
  const paths = SAFE_ADD.filter(p => fs.existsSync(path.join(ROOT, p)));
  const add2 = paths.length ? sh('git', ['add', '--', ...paths]) : '';
  const add3 = sh('git', ['add', '--', rel]);
  if (!ok(add1) || !ok(add2) || !ok(add3)) {
    return { ok: false, why: `git add failed: ${add1} ${add2} ${add3}`.slice(0, 200) };
  }

  const staged = sh('git', ['diff', '--cached', '--name-only']);
  if (!ok(staged) || !staged) return { ok: true, skipped: true, why: 'nothing staged' };

  const subject = moved
    ? `daily: ${day} pipeline run`
    : `daily: ${day} pipeline run (no-op)`;
  const body = `Automated summary from utils/daily-summary.js.\n\n`
    + `Files in this commit: ${staged.split('\n').length}.\n`
    + `See ${rel} for stages, queues and anything needing a human.\n`;
  const msg = `${subject}\n\n${body}`;

  const c = sh('git', ['commit', '-q', '-m', msg]);
  if (!ok(c)) return { ok: false, why: `commit failed: ${c}` };

  const p = sh('git', ['push', '-q', 'origin', 'HEAD']);
  if (!ok(p)) return { ok: true, pushed: false, why: `committed but push failed: ${p}` };
  return { ok: true, pushed: true, staged: staged.split('\n').length };
}

function write({ dry = false, commit = false } = {}) {
  const b = build();
  const file = path.join(OUT_DIR, `${b.day}.md`);
  if (dry) return { ...b, file, wrote: false };
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(file, b.markdown);
  const res = commit ? commitAndPush(file, b) : null;
  return { ...b, file, wrote: true, commit: res };
}

if (require.main === module) {
  const argv = process.argv.slice(2);
  const r = write({ dry: argv.includes('--dry'), commit: argv.includes('--commit') });
  if (argv.includes('--dry')) {
    console.log(r.markdown);
    console.log(`[summary] (--dry — would write ${path.relative(ROOT, r.file)})`);
  } else {
    console.log(`[summary] wrote ${path.relative(ROOT, r.file)}  (${r.moved ? 'work moved' : 'NO-OP'})`);
    if (r.commit) {
      if (!r.commit.ok) console.error(`[summary] ⚠ ${r.commit.why}`);
      else if (r.commit.skipped) console.log(`[summary] nothing to commit`);
      else console.log(`[summary] committed ${r.commit.staged} file(s)` + (r.commit.pushed ? ' and pushed' : ` — ${r.commit.why}`));
      if (r.commit.ok && !r.commit.pushed && !r.commit.skipped) process.exitCode = 1;
    }
  }
}

module.exports = { build, write, commitAndPush, ledgerCounts, changedFiles, parseStatusLine };
