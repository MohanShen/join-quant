// Usage: node -e "process.argv[2]='baseline-e6.py';process.argv[3]='dbdx-baseline-e6';require('./study/打板短线/run.js')"
// One TRAIN backtest, foreground/blocking, output to data/autostudy-logs/<expId>.log, terminated
// by an EXIT line. Paths are relative to study/打板短线/ unless they start with enhance/.
// Optional argv[4]/argv[5] = --start/--end for a single-year sub-window (still inside TRAIN).
// ⚠ This base is a wall-clock heavyweight (≈16 JQ min per TRAIN run, >20 min wall): the poll
// cap is 50 min, and the Bash tool's 10-min cap means the caller must run this in the background.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const rel = process.argv[2], id = process.argv[3], start = process.argv[4], end = process.argv[5];
const file = rel.startsWith('enhance/') ? rel : path.join('study', '打板短线', rel);
fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = `data/autostudy-logs/${id}.log`;
const log = fs.openSync(logPath, 'w');
const win = start && end ? ['--start', start, '--end', end] : ['--window', 'train'];
const r = spawnSync('node', ['utils/strategy-post-backtest.js', file, id, ...win,
  '--usage-limit', '170', '--max-poll-min', '50'], { stdio: ['ignore', log, log] });
fs.writeSync(log, `\nEXIT ${r.status}\n`);
console.log(fs.readFileSync(logPath, 'utf8').split('\n').filter(l => /^(SUMMARY|SERIES|EXIT)|usage|STOP|error|algorithmId|backtestId/i.test(l)).join('\n'));
