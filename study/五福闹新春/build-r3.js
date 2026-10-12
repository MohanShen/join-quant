// Round 3 (2026-10-12) for 五福闹新春, prompted by new member 73b13d92 (obj 0.4848 @ epoch 6).
// H78a = keep the R² filter during the weak period (base turns it OFF there).
// Two readings of ONE mechanism: port it onto the base, and knock it out of the member.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const BASE = path.join(ROOT, 'strategies/2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py');
const MEMBER = path.join(ROOT, 'strategies/2026-10-12_五福_ETF_轮动五年迭代_谁才是五年收益之王-73b13d92.py');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

// ── idea-imp-6: port H78a onto the family base ──
let base = py2to3(fs.readFileSync(BASE, 'utf8'));
base = edit(base, '    g.enable_r2_filter = True\n',
  '    g.enable_r2_filter = True\n    g.enable_weak_r2_filter = True  # imp-6 (H78a, from 73b13d92)\n');
base = edit(base,
  "        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter and not g.is_a_share_weak),\n",
  "        ('R²', lambda m: m['passed_r2'],\n" +
  "         (g.enable_r2_filter and not g.is_a_share_weak)\n" +
  "         or (getattr(g, 'enable_weak_r2_filter', False) and g.is_a_share_weak)),  # imp-6 (H78a)\n");
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'enhance/candidates', 'wufu-imp-6.py'), base + OVERRIDE);

// ── q-e6-5: knock H78a out of the member, in situ (control = its ledger row 0.4848) ──
let member = py2to3(fs.readFileSync(MEMBER, 'utf8'));
member = edit(member, '    g.enable_weak_r2_filter = True\n',
  '    g.enable_weak_r2_filter = False  # q-e6-5: H78a knocked out\n');
fs.mkdirSync(path.join(__dirname, 'variants'), { recursive: true });
fs.writeFileSync(path.join(__dirname, 'variants', 'q-5_member-no-h78a.py'), member + OVERRIDE);

console.log('built wufu-imp-6 (base+H78a) and q-5_member-no-h78a');
