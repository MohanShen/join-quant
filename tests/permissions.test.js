/**
 * Every repo command a skill or agent tells an agent to run must be allowlisted.
 *
 * Headless sessions run with `--permission-mode acceptEdits`, which auto-accepts file edits but
 * NOT Bash. An un-allowlisted command comes back "This command requires approval", and a
 * non-interactive session cannot approve it.
 *
 * Measured 2026-09-22: the 七星高照 round was dispatched, produced nothing and exited 0 —
 * `node utils/research-queue.js` and `node utils/family-queue.js` were not in the allowlist, so
 * the skill's own mandatory first step was blocked. The two families before it happened to use
 * `node -e` (which IS allowed) and got through, which is why it looked intermittent. The daily
 * pipeline recorded it as `research -> RAN`; only the no-progress guard caught that the queue had
 * not moved.
 *
 * So this is the guard: a command documented in a skill is a command the pipeline depends on.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const settings = JSON.parse(fs.readFileSync(path.join(ROOT, '.claude/settings.json'), 'utf8'));
const allow = settings.permissions.allow || [];

const allowed = cmd => allow.some(rule => {
  const m = rule.match(/^Bash\((.*?)(:\*)?\)$/);
  if (!m) return false;
  return cmd.startsWith(m[1]);
});

/** `node utils/x.js` invocations mentioned in a doc. */
function commandsIn(file) {
  const text = fs.readFileSync(file, 'utf8');
  const out = new Set();
  for (const m of text.matchAll(/\bnode\s+(utils\/[\w.-]+\.js)/g)) out.add(`node ${m[1]}`);
  return [...out];
}

function docs() {
  const out = [];
  for (const d of ['.claude/skills', '.claude/agents']) {
    const abs = path.join(ROOT, d);
    if (!fs.existsSync(abs)) continue;
    for (const e of fs.readdirSync(abs)) {
      const p = path.join(abs, e);
      if (fs.statSync(p).isDirectory()) {
        const s = path.join(p, 'SKILL.md');
        if (fs.existsSync(s)) out.push(s);
      } else if (e.endsWith('.md')) out.push(p);
    }
  }
  return out;
}

test('skills and agents only tell agents to run allowlisted commands', async (t) => {
  await t.test('every documented node utils/... call is permitted', () => {
    const missing = [];
    for (const d of docs()) {
      for (const cmd of commandsIn(d)) {
        if (!allowed(cmd)) missing.push(`${path.relative(ROOT, d)}: ${cmd}`);
      }
    }
    assert.deepStrictEqual(missing, [],
      `these are documented but would be refused in a headless session:\n  ${missing.join('\n  ')}`);
  });

  await t.test('the merged loop\'s mandatory first step is permitted', () => {
    // The skill calls this "not optional", so a blocked one silently disables the whole loop.
    for (const cmd of ['node utils/research-queue.js', 'node utils/family-queue.js',
                       'node utils/val-budget.js', 'node utils/research-sync.js']) {
      assert.ok(allowed(cmd), `${cmd} is blocked — /run-family cannot start`);
    }
  });

  await t.test('nothing is denied outright', () => {
    assert.deepStrictEqual(settings.permissions.deny || [], [],
      'a deny rule would silently override the allowlist');
  });
});
