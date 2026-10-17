// node -e "require('./study/五福闹新春/run-e8-1.js')"
// ONE foreground TRAIN backtest for q-e8-1, tee'd to data/autostudy-logs/wufu-q-e8-1.log.
const fs = require('fs');
const { spawnSync } = require('child_process');
fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = 'data/autostudy-logs/wufu-q-e8-1.log';
const log = fs.openSync(logPath, 'w');
const r = spawnSync('node', [
  'utils/strategy-post-backtest.js',
  'study/五福闹新春/variants/q-e8-1_weak-gold-only.py',
  'wufu-q-e8-1',
  '--window', 'train',
  '--usage-limit', 'free',
], { stdio: ['ignore', log, log] });
fs.writeSync(log, `\nEXIT ${r.status}\n`);
console.log('EXIT', r.status);
