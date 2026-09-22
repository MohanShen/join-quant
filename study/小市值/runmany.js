// Usage: node -e "process.argv[2]='q-6_choice-800,q-7_choice-1200';require('./study/小市值/runmany.js')"
// Runs the named variants ONE AT A TIME (each blocking), then prints SUMMARY + per-year split.
const fs = require('fs');
const { spawnSync } = require('child_process');
for (const v of process.argv[2].split(',')) {
  const id = `xsz-${v}`;
  const r = spawnSync('node', ['-e', `process.argv[2]='variants/${v}.py';process.argv[3]='${id}';require('./study/小市值/run.js')`], { stdio: 'inherit' });
  const log = fs.readFileSync(`data/autostudy-logs/${id}.log`, 'utf8');
  console.log(v, (log.match(/^SUMMARY.*$/m) || ['NO SUMMARY'])[0], (log.match(/^EXIT.*$/m) || [''])[0]);
  if (!/^SUMMARY/m.test(log)) break;
  spawnSync('node', ['-e', `process.argv[2]='study_小市值_variants_${v}__train__e6';require('./study/小市值/yearsplit.js')`], { stdio: 'inherit' });
}
