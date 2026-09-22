// Blocks up to ~9.5 min for data/autostudy-logs/<expId>.log to end with an EXIT line, then prints the result tail.
const fs = require('fs');
const p = `data/autostudy-logs/${process.argv[2]}.log`;
const t0 = Date.now();
(function tick() {
  const s = fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : '';
  const done = /\nEXIT /.test(s);
  if (done || Date.now() - t0 > 570000) {
    const i = s.lastIndexOf('[post]');
    console.log(done ? s.slice(Math.max(0, s.indexOf('====', Math.max(0, i - 200)) - 50)) : 'STILL RUNNING: ' + s.slice(-120));
    return;
  }
  setTimeout(tick, 10000);
})();
