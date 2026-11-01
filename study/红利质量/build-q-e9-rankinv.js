// q-e9-rankinv — baseline.py with ONE asserted edit: in _rank_and_build,
// df.sort_values('composite', ascending=False) -> ascending=True (take the pool BOTTOM TopN).
// Everything else verbatim, including the OVERRIDE the baseline already carries.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const base = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');
const OLD = "    df = df.sort_values('composite', ascending=False)";
const NEW = "    df = df.sort_values('composite', ascending=True)";
const hits = base.split('\n').filter(l => l === OLD);
if (hits.length !== 1) throw new Error('expected exactly one composite sort line, got ' + hits.length);
const header = '# q-e9-rankinv — 红利质量 understand: baseline.py with composite sort ascending=False->True (pool bottom). Built by study/红利质量/build-q-e9-rankinv.js.\n';
const out = header + base.replace(OLD, NEW);
const a = base.split('\n'), b = out.split('\n').slice(1);
const diff = a.map((l, i) => l !== b[i] ? i : -1).filter(i => i >= 0);
if (a.length !== b.length || diff.length !== 1 || b[diff[0]] !== NEW) throw new Error('edit assertion failed: ' + diff);
const dst = path.join(__dirname, 'variants/q-e9-rankinv.py');
fs.writeFileSync(dst, out);
console.log('built', path.relative(ROOT, dst), 'changed line', diff[0] + 1, JSON.stringify(b[diff[0]]));
