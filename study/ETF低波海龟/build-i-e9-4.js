// i-e9-4: i-e9-3 (3 lowest-vol, 1/vol, set-change rebalance, min-hold + band, overlay off) with the
// 14 hand-picked g.all_risk_etfs replaced by q-e9-4's daily point-in-time equity pool — copied
// VERBATIM out of variants/q-e9-4-pit.py (the initialize-side NEW block and the appended
// POINT-IN-TIME EQUITY POOL block), never retyped. Asserted: exactly one OLD pool block in i-e9-3,
// diff confined to it + the appended pool block; OVERRIDE is the live one (never hand-copied).
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const sha = s => crypto.createHash('sha256').update(s).digest('hex').slice(0, 16);

const i3 = fs.readFileSync(path.join(__dirname, 'variants/i-e9-3.py'), 'utf8');
const pit = fs.readFileSync(path.join(__dirname, 'variants/q-e9-4-pit.py'), 'utf8');
const q3 = fs.readFileSync(path.join(__dirname, 'variants/q-e9-3.py'), 'utf8');
if (!i3.startsWith('# i-e9-3:')) throw new Error('i-e9-3 header');
for (const [n, s] of [['i-e9-3', i3], ['q-e9-4-pit', pit], ['q-e9-3', q3]])
  if (!s.endsWith(OVERRIDE)) throw new Error(`${n} OVERRIDE differs from live OVERRIDE`);

// OLD = the 14-name dict block as it appears in q-e9-3 (i-e9-3's parent) — derive it as the
// region where q-e9-3 and q-e9-4-pit's bodies disagree in initialize.
const q3b = q3.slice(q3.indexOf('\n') + 1, q3.length - OVERRIDE.length);
const pitb = pit.slice(pit.indexOf('\n') + 1, pit.length - OVERRIDE.length);
const M0 = '\n# ===== POINT-IN-TIME EQUITY POOL';
const M1 = '# ===== END POINT-IN-TIME EQUITY POOL =====\n';
const p0 = pitb.indexOf(M0), p1 = pitb.indexOf(M1);
if (p0 < 0 || p1 < 0 || pitb.split(M0).length !== 2) throw new Error('pool markers');
const POOL = pitb.slice(p0, p1 + M1.length);
const pitHead = pitb.slice(0, p0);
if (pitb.slice(p1 + M1.length) !== '') throw new Error('unexpected text after pool block in q-e9-4-pit');
// common prefix / suffix between q3b and pitHead isolates OLD (in q3) and NEW (in pit)
let a = 0; while (q3b[a] === pitHead[a]) a++;
a = q3b.lastIndexOf('\n', a - 1) + 1;
let z = 0; while (q3b[q3b.length - 1 - z] === pitHead[pitHead.length - 1 - z]) z++;
let OLD = q3b.slice(a, q3b.length - z), NEW = pitHead.slice(a, pitHead.length - z);
// extend to full lines
const eol = s => s.endsWith('\n') ? s : s;
if (!OLD.includes('g.all_risk_etfs = {') || !NEW.includes('rebuild_pool')) throw new Error('OLD/NEW isolation failed');
console.log('OLD block lines', OLD.split('\n').length, '| NEW block lines', NEW.split('\n').length);

let body = i3.slice(0, i3.length - OVERRIDE.length);
const n = body.split(OLD).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 OLD pool block in i-e9-3, got ${n}`);
const i = body.indexOf(OLD);
const swapped = body.slice(0, i) + NEW + body.slice(i + OLD.length);
if (swapped.slice(0, i) !== body.slice(0, i) || swapped.slice(i + NEW.length) !== body.slice(i + OLD.length))
  throw new Error('diff escaped the pool block');
// header: replace the first line
const nl = swapped.indexOf('\n');
const hdr = '# i-e9-4: i-e9-3 (3 lowest-vol, 1/vol, set-change, overlay off) with the 14 hand-picked risk ETFs -> q-e9-4 daily point-in-time equity pool (verbatim). Built by study/ETF低波海龟/build-i-e9-4.js\n';
const outBody = hdr + swapped + POOL + OVERRIDE;
// guard: no bare builtin sum( in the appended/new code (jqdata shadows it)
if (/(^|[^\w.])sum\(/.test(NEW + POOL)) throw new Error('builtin sum() in new code — jqdata shadows it');
const out = path.join(__dirname, 'variants', 'i-e9-4.py');
fs.writeFileSync(out, outBody);
console.log('wrote', out, 'sha', sha(outBody), 'i-e9-3 sha', sha(i3), 'pit sha', sha(pit));
