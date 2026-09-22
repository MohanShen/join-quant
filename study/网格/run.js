// Usage: node -e "process.argv[2]='variants/u-1_hold-control.py';process.argv[3]='wg-u-1';require('./study/网格/run.js')"
// One TRAIN backtest, foreground/blocking, output to data/autostudy-logs/<expId>.log, terminated
// by an EXIT line. Paths are relative to study/网格/ unless they start with enhance/.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const rel = process.argv[2], id = process.argv[3];
const file = rel.startsWith('enhance/') ? rel : path.join('study', '网格', rel);
fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = `data/autostudy-logs/${id}.log`;
const log = fs.openSync(logPath, 'w');
const r = spawnSync('node', ['utils/strategy-post-backtest.js', file, id, '--window', 'train',
  '--usage-limit', '170', '--max-poll-min', '30'], { stdio: ['ignore', log, log] });
fs.writeSync(log, `\nEXIT ${r.status}\n`);
console.log(fs.readFileSync(logPath, 'utf8').split('\n').filter(l => /^(SUMMARY|SERIES|EXIT)|usage|STOP|error|algorithmId|backtestId/i.test(l)).join('\n'));
