// q-e9-4 builder: pool hindsight test. The hand-picked 14-name g.all_risk_etfs is replaced by the
// a-priori EQUITY-ONLY broad A-share pool ETF动量 used in its pool-swap test
// (study/ETF动量/variants/q-3_ashare-pool.py — member 0717871e's 4 names, the "−0.27" experiment):
// 510300 沪深300ETF / 510500 中证500ETF / 159915 创业板ETF / 159949 创业板50ETF. No bond / money /
// gold / commodity / QDII name in it. g.safe_etfs, ranking, turtle overlay, switch band verbatim.
//   A: base 4a8bcfd5 (py2to3) + pool edit + live OVERRIDE
//   B: q-e9-3 (overlay off) body + pool edit + live OVERRIDE
// Asserted: the only changed region is the g.all_risk_etfs dict. strategies/ never modified.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-10-17_量化分享_ETF低波海龟法则与复利增强的验证-4a8bcfd5.py');
const base = py2to3(fs.readFileSync(SRC, 'utf8'));

const OLD = [
  '    g.all_risk_etfs = {',
  '        "159915.XSHE": "创业板ETF",',
  "        '510880.XSHG': \"红利ETF\",",
  "        '510050.XSHG': '50ETF',",
  "        '512100.XSHG': '1000ETF',",
  "        '159768.XSHE': '房地产ETF银华',",
  "        '515220.XSHG': '煤炭ETF',",
  "        '159928.XSHE': '消费ETF',",
  "        '512800.XSHG': '银行ETF',",
  "        '159995.XSHE': '芯片ETF',",
  "        '159870.XSHE': '化工ETF',",
  "        '513090.XSHG': '香港证券ETF',",
  '        "518880.XSHG": "黄金ETF",',
  '        "513100.XSHG": "纳指ETF",',
  '        "159985.XSHE": "豆粕ETF",',
  '    }',
  ''].join('\n');
const NEW = [
  '    g.all_risk_etfs = {  # q-e9-4: a-priori equity-only A-share pool (ETF动量 q-3 / 0717871e)',
  "        '510300.XSHG': '沪深300ETF',",
  "        '510500.XSHG': '中证500ETF',",
  '        "159915.XSHE": "创业板ETF",',
  "        '159949.XSHE': '创业板50ETF',",
  '    }',
  ''].join('\n');

function swap(s) {
  const n = s.split(OLD).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 pool block, got ${n}`);
  const i = s.indexOf(OLD);
  const out = s.slice(0, i) + NEW + s.slice(i + OLD.length);
  if (out.slice(0, i) !== s.slice(0, i) || out.slice(i + NEW.length) !== s.slice(i + OLD.length))
    throw new Error('diff escaped the pool block');
  return out;
}
function write(name, hdr, body) {
  const out = path.join(__dirname, 'variants', `${name}.py`);
  fs.writeFileSync(out, hdr + body + OVERRIDE);
  console.log('wrote', out);
}

write('q-e9-4-base',
  '# q-e9-4 arm A: ETF低波海龟 base 4a8bcfd5, risk pool 14 hand-picked -> 4 a-priori equity broad ETFs. Built by study/ETF低波海龟/build-q-e9-4.js\n',
  swap(base));

const q3 = fs.readFileSync(path.join(__dirname, 'variants/q-e9-3.py'), 'utf8');
if (!q3.startsWith('# q-e9-3:')) throw new Error('q-e9-3 header');
if (!q3.endsWith(OVERRIDE)) throw new Error('q-e9-3 OVERRIDE differs from live OVERRIDE');
const q3body = q3.slice(q3.indexOf('\n') + 1, q3.length - OVERRIDE.length);
write('q-e9-4-q3',
  '# q-e9-4 arm B: q-e9-3 (overlay off) with risk pool 14 hand-picked -> 4 a-priori equity broad ETFs. Built by study/ETF低波海龟/build-q-e9-4.js\n',
  swap(q3body));
