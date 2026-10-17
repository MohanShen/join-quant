// node -e "require('./study/五福闹新春/run-e8-2.js')"
// Launches the ONE TRAIN backtest for q-e8-2 DETACHED, tee'd to
// data/autostudy-logs/wufu-q-e8-2.log, and returns the pid. The caller then BLOCKS in
// the foreground on wait-e8-2.js (the tool's foreground timeout is shorter than this
// family's worst run, 466s+, so the block is split across calls -- never a notification).
const fs = require('fs');
const { spawn } = require('child_process');
fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = 'data/autostudy-logs/wufu-q-e8-2.log';
const log = fs.openSync(logPath, 'w');
const child = spawn('node', [
  'utils/strategy-post-backtest.js',
  'study/五福闹新春/variants/q-e8-2_trade-1312.py',
  'q-e8-2',
  '--window', 'train',
  '--usage-limit', 'free',
], { stdio: ['ignore', log, log], detached: true });
child.unref();
fs.writeFileSync('data/autostudy-logs/wufu-q-e8-2.pid', String(child.pid));
console.log('launched pid', child.pid, '->', logPath);
