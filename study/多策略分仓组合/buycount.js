// Count leg-A buys by the regime logged on the buy date, distinct names, bull-day sells.
// usage: node -e "require('./study/多策略分仓组合/buycount.js').main('u-6')"
const fs = require('fs');
const path = require('path');
function main(id) {
  const f = path.join(__dirname, `${id}.log`);
  const L = fs.readFileSync(f, 'utf8').split('\n');
  const rs = require('./regime-split.js').regimes(f); const reg = new Map(rs);
  const buys = L.filter(l => /虚拟账户买入/.test(l)), sells = L.filter(l => /虚拟账户卖出/.test(l));
  const c = { bullEtf: 0, bullStk: 0, bearStk: 0, bearEtf: 0, nonRegimeDay: 0 }; const names = new Set();
  for (const l of buys) {
    const d = l.slice(0, 10), code = l.match(/买入 (\S+)/)[1], g = reg.get(d);
    if (g === 'bull') code === '511880.XSHG' ? c.bullEtf++ : c.bullStk++;
    else if (g === 'bear') { if (code === '511880.XSHG') c.bearEtf++; else { c.bearStk++; names.add(code); } }
    else c.nonRegimeDay++;
  }
  const bullD = new Set(rs.filter(x => x[1] === 'bull').map(x => x[0]));
  const err = {}; L.filter(l => / - ERROR - /.test(l)).forEach(l => { const k = l.replace(/^\S+ \S+ - ERROR - /, '').slice(0, 50); err[k] = (err[k] || 0) + 1; });
  console.log(id, 'buys', buys.length, 'sells', sells.length, JSON.stringify(c), 'distinctStockNames', names.size,
    'bullDaySells', sells.filter(l => bullD.has(l.slice(0, 10))).length, 'ERROR kinds', JSON.stringify(err));
  return { names: [...names] };
}
module.exports = { main };
