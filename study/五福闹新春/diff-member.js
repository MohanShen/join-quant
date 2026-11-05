// Step-0 free diff: normalized (comment/log-stripped) code-line diff of a new member against named members.
// usage: node -e "process.argv=['n','x','<newTag>','<refTag>',...];require('./study/五福闹新春/diff-member.js')"
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const all = fs.readdirSync(path.join(ROOT, 'strategies'));
const lines = tag => {
  const f = all.find(x => x.includes(tag));
  return fs.readFileSync(path.join(ROOT, 'strategies', f), 'utf8').split('\n')
    .map(l => l.replace(/#.*/, '').trim())
    .filter(l => l && !/log\.(info|debug|warn)|print\(/.test(l));
};
const [nt, ...refs] = process.argv.slice(2);
const N = lines(nt);
const NS = new Set(N);
for (const r of refs) {
  const R = lines(r);
  const RS = new Set(R);
  const add = [...new Set(N.filter(l => !RS.has(l)))];
  const del = [...new Set(R.filter(l => !NS.has(l)))];
  console.log(`== ${nt} vs ${r}: +${add.length} / -${del.length} distinct lines`);
  add.slice(0, 25).forEach(l => console.log('  + ' + l.slice(0, 140)));
  del.slice(0, 25).forEach(l => console.log('  - ' + l.slice(0, 140)));
}
