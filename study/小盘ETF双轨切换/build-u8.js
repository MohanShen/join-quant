// u-8 摸狗 -> cash: base 0d1bbe83 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them)
// + ONE asserted edit: in consistent()'s 摸狗 branch, target_list = [] (was: get_rank(g.etf_pool)[:g.etf_target_num]).
// Effect: the hold loop sells EVERY holding (stocks liquidated exactly as in the base, where no stock is
// ever in the ETF target), and `for s in target_list` in the buy block iterates nothing -> no ETF bought.
// DDDD, the 30-day lock, the 偷鸡 leg and 14:00 check_limit_up verbatim (补跌 only loops non-etf_pool holdings).
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-12_年化51_的晴雨双轨_小盘游击_ETF防御-0d1bbe83.py';
function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));
const v = edit(raw,
  "            target_list = get_rank(g.etf_pool)[:g.etf_target_num]\n",
  "            target_list = []  # u-8 摸狗 -> cash (was: get_rank(g.etf_pool)[:g.etf_target_num])\n");
if (v === raw) throw new Error('edit changed nothing');
const a = raw.split('\n'), b = v.split('\n');
if (a.length !== b.length) throw new Error('line count changed');
const diff = b.filter((l, i) => l !== a[i]);
if (diff.length !== 1) throw new Error('expected exactly one changed line, got ' + diff.length);
const out = path.join(__dirname, 'variants/u-8-mogou-cash.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, v + OVERRIDE);
console.log('built', path.relative(ROOT, out), '| changed line:', diff[0].trim());
