// q-e9-2 — edge test for 低波动异象: which rank of the sorted 60-day vol Series is taken as `best`.
//   mid : best = vol.index[len(vol)//2]  (14 risk ETFs -> index 7, the upper median)
//   high: best = vol.index[-1]           (highest vol)
// Everything else verbatim. Mirrored edits (all asserted, exactly-once):
//   l.393/394  best / best_vol           -> chosen rank, best_vol = vol[best]
//   l.426/427  risk_best / risk_best_vol -> same rank on risk_vol_only (safe leg inert in 2024)
//   l.483      switch condition:
//     high: best_vol > cur_vol * (1 + g.switch_threshold)   (switch TOWARD higher vol by >=10%)
//     mid : best != cur   (only reached when cur != best, cur in pool, min-hold elapsed => switch
//            whenever the median name differs; there is no monotone "closer" metric to threshold)
// `cur == best` (add-on eligibility) is untouched: it now means "cur is still the chosen rank".
// Build: py2to3(source) + edits + live OVERRIDE. strategies/ never modified.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-10-17_量化分享_ETF低波海龟法则与复利增强的验证-4a8bcfd5.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}
const V = {
  mid: { idx: 'len(vol)//2', ridx: 'len(risk_vol_only)//2', sw: 'best != cur' },
  high: { idx: '-1', ridx: '-1', sw: 'best_vol > cur_vol * (1 + g.switch_threshold)' },
};
for (const [k, v] of Object.entries(V)) {
  let b = src;
  b = edit(b, '    best = vol.index[0]\n    best_vol = vol.iloc[0]\n',
    `    best = vol.index[${v.idx}]  # q-e9-2-${k}\n    best_vol = vol[best]\n`);
  b = edit(b, '                risk_best = risk_vol_only.index[0]\n                risk_best_vol = risk_vol_only.iloc[0]\n',
    `                risk_best = risk_vol_only.index[${v.ridx}]  # q-e9-2-${k}\n                risk_best_vol = risk_vol_only[risk_best]\n`);
  b = edit(b, '    if best_vol < cur_vol * (1 - g.switch_threshold):\n',
    `    if ${v.sw}:  # q-e9-2-${k}\n`);
  const a = src.split('\n'), c = b.split('\n');
  if (a.length !== c.length) throw new Error('line count moved');
  const changed = a.filter((l, i) => l !== c[i]).length;
  if (changed !== 5) throw new Error(`expected 5 changed lines, got ${changed}`);
  const hdr = `# q-e9-2-${k}: ETF低波海龟 base 4a8bcfd5 with best = vol.index[${v.idx}]; switch if ${v.sw}. Built by study/ETF低波海龟/build-q-e9-2.js\n`;
  const out = path.join(__dirname, 'variants', `q-e9-2-${k}.py`);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, hdr + b + OVERRIDE);
  console.log('wrote', out, 'changed', changed);
}
