// Usage: node -e "process.argv[2]='variants/q-1_next-1000.py';process.argv[3]='xsz-q-e6-1';require('./study/小市值/run.js')"
// One TRAIN backtest, output to data/autostudy-logs/<expId>.log, terminated by an EXIT line.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const rel = process.argv[2], id = process.argv[3];
const file = path.join('study', '小市值', rel);
fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = `data/autostudy-logs/${id}.log`;
const log = fs.openSync(logPath, 'w');
const r = spawnSync('node', ['utils/strategy-post-backtest.js', file, id, '--window', 'train', '--usage-limit', '170'],
  { stdio: ['ignore', log, log] });
fs.writeSync(log, `\nEXIT ${r.status}\n`);
