// node -e "require('./study/多因子ML/syntax-check-e9-cand.js')"
// Free local Python syntax check on enhance/candidates/xp-e9-1.py before any backtest minute is
// spent, plus a STRUCTURAL re-check of both edits that is independent of the builder's own
// assertions: the pit side (etf_pool 14 -> 13 active, exactly 1 commented out) and the liq side
// (5 call sites, 2 helper defs, the dynamic floor expression, LIQ_FLOOR_MULT = 1.0).
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '../..');
const file = path.join(ROOT, 'enhance/candidates/xp-e9-1.py');
const baseline = path.join(__dirname, 'baseline-e6.py');

const prog = [
  'import ast, sys',
  'p = sys.argv[1]',
  'src = open(p, encoding="utf-8").read()',
  'try:',
  '    ast.parse(src)',
  '    print("OK    %s  (%d chars)" % (p.split("/")[-1], len(src)))',
  'except SyntaxError as e:',
  '    print("SYNTAX ERROR  %s  line %s: %s" % (p.split("/")[-1], e.lineno, e.msg))',
  '    sys.exit(1)',
].join('\n');

let bad = 0;
try {
  console.log(execFileSync('python3', ['-I', '-c', prog, file], { encoding: 'utf8' }).trim());
} catch (e) {
  console.error((e.stdout || '') + (e.stderr || ''));
  process.exitCode = 1;
  return;
}

const text = fs.readFileSync(file, 'utf8');
const base = fs.readFileSync(baseline, 'utf8');

// ── pit side: the etf_pool block
const poolCount = (t) => {
  const i = t.indexOf("'etf_pool': [");
  const j = t.indexOf(']', i);
  const block = t.slice(i, j);
  return {
    active: block.split('\n').filter(l => /^\s*["'][0-9]{6}\./.test(l)).length,
    commented: block.split('\n').filter(l => /^\s*#["'][0-9]{6}\./.test(l)).length,
  };
};
const v = poolCount(text), b = poolCount(base);
console.log(`[check] pit: etf_pool active ${b.active} -> ${v.active} (commented out ${v.commented})`);
if (!(b.active === 14 && v.active === 13 && v.commented === 1)) { console.error('[check] REFUSE: expected 14 -> 13 with exactly 1 commented'); bad++; }

// ── liq side: the floor machinery, counted on code lines only
const code = text.split('\n').filter(l => !/^\s*#/.test(l)).join('\n');
const n = (re) => (code.match(re) || []).length;
const sites = n(/filter_liquidity_floor\(context, '/g);
const defs = n(/def (filter_liquidity_floor|liq_floor_for)\(/g);
console.log(`[check] liq: ${sites} call sites, ${defs} helper defs, mult=${(text.match(/^LIQ_FLOOR_MULT = ([0-9.]+)/m) || [])[1]}, ovr=${(text.match(/^LIQ_ORDER_VOLUME_RATIO = ([0-9.]+)/m) || [])[1]}`);
if (sites !== 5) { console.error('[check] REFUSE: expected 5 filter_liquidity_floor call sites'); bad++; }
if (defs !== 2) { console.error('[check] REFUSE: expected 2 helper definitions'); bad++; }
if (!/return pos \/ float\(LIQ_ORDER_VOLUME_RATIO\) \* float\(LIQ_FLOOR_MULT\)/.test(code)) { console.error('[check] REFUSE: the dynamic floor expression is missing'); bad++; }
if (!/^LIQ_FLOOR_MULT = 1\.0/m.test(text)) { console.error('[check] REFUSE: LIQ_FLOOR_MULT is not 1.0'); bad++; }

// ── bench: the pins and the frozen cost block
const { OVERRIDE } = require('../../utils/strategy-normalize');
if (!text.endsWith(OVERRIDE)) { console.error('[check] REFUSE: frozen OVERRIDE is not the file tail'); bad++; }
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!text.includes(pin)) { console.error(`[check] REFUSE: missing pin ${pin}`); bad++; }
}
console.log(`[check] bench: frozen OVERRIDE is the tail, all 3 pins present`);
console.log(bad ? `[check] ${bad} PROBLEM(S)` : '[check] clean');
if (bad) process.exitCode = 1;
