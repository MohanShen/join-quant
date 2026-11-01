// Per-name P&L from ATTRIB POS/CASH lines (logged 15:00 daily) + targets per rebalance.
// Usage: node -e "require('./study/破净价值多因子/attrib-analyze.js').main()" -- <runlog> [<runlog2>...]
// Method: name P&L = Σ_d [value_d − value_{d−1}] − buy cost + sell proceeds.
// Buy cost = Δ(amount·avg_cost). Sell proceeds = (Δcash + buy costs) split over the day's sellers by
// prior value × fraction sold. A cash change on a day with no seller (dividends) goes to '(unattributed)'.
// The sum reconciles exactly to final total_value − initial capital.
const fs = require('fs');

function analyze(file) {
  const lines = fs.readFileSync(file, 'utf8').split('\n');
  const days = new Map(); // d -> {pos:{code:{a,v,c,p}}, cash, tv}
  const targets = []; const names = {};
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    let m;
    if ((m = l.match(/ATTRIB POS (\S+) (\S+) (\d+) (\S+) (\S+) (\S+)/))) {
      const d = days.get(m[1]) || { pos: {} }; days.set(m[1], d);
      d.pos[m[2]] = { a: +m[3], v: +m[4], c: +m[5], p: +m[6] };
    } else if ((m = l.match(/ATTRIB CASH (\S+) (\S+) (\S+)/))) {
      const d = days.get(m[1]) || { pos: {} }; days.set(m[1], d);
      d.cash = +m[2]; d.tv = +m[3];
    } else if (/筛选结果/.test(l)) {
      const nx = lines[i + 1] || '';
      const codes = [...nx.matchAll(/'(\d{6}\.XS\w\w)'/g)].map(x => x[1]);
      targets.push({ date: l.slice(0, 10), n: codes.length, codes });
    }
    if ((m = l.match(/(?:买入|卖出): (\d{6}\.XS\w\w) (\S+)/))) names[m[1]] = m[2];
  }
  const ds = [...days.keys()].sort();
  const pnl = {}; const held = {}; let prev = { pos: {}, cash: 1e6, tv: 1e6 };
  const add = (k, x) => { pnl[k] = (pnl[k] || 0) + x; };
  for (const d of ds) {
    const cur = days.get(d);
    const codes = new Set([...Object.keys(prev.pos), ...Object.keys(cur.pos)]);
    let buyCost = 0; const sellers = [];
    for (const k of codes) {
      const a0 = prev.pos[k] ? prev.pos[k].a : 0, a1 = cur.pos[k] ? cur.pos[k].a : 0;
      if (cur.pos[k]) held[k] = (held[k] || 0) + 1;
      if (a1 > a0) {
        const bc = (a1 * cur.pos[k].c) - (a0 ? a0 * prev.pos[k].c : 0);
        buyCost += bc; add(k, -bc);
      } else if (a1 < a0) sellers.push({ k, w: prev.pos[k].v * (a0 - a1) / a0 });
      add(k, (cur.pos[k] ? cur.pos[k].v : 0) - (prev.pos[k] ? prev.pos[k].v : 0));
    }
    const resid = (cur.cash - prev.cash) + buyCost; // proceeds of sells (+ dividends − fees)
    if (sellers.length) { const W = sellers.reduce((s, x) => s + x.w, 0); for (const s of sellers) add(s.k, resid * s.w / W); }
    else if (Math.abs(resid) > 1e-6) add('(unattributed)', resid);
    prev = cur;
  }
  const total = Object.values(pnl).reduce((s, x) => s + x, 0);
  const finalTv = days.get(ds[ds.length - 1]).tv;
  const rows = Object.entries(pnl).sort((a, b) => b[1] - a[1]);
  const net = finalTv - 1e6;
  return { file, net, total, rows, held, names, targets };
}

function main() {
  const files = process.argv.slice(1).filter(a => a !== '--' && fs.existsSync(a) && !a.endsWith('node'));
  for (const f of files) {
    const r = analyze(f);
    console.log(`\n== ${f}\nnet ${r.net.toFixed(0)}  sum-of-names ${r.total.toFixed(0)}  distinct ${r.rows.filter(x => x[0][0] !== '(').length}`);
    for (const [k, v] of r.rows) console.log(`${k}\t${r.names[k] || ''}\t${v.toFixed(0)}\t${(100 * v / r.net).toFixed(1)}%\t${r.held[k] || 0}d`);
    const top2 = r.rows.filter(x => x[0][0] !== '(').slice(0, 2).reduce((s, x) => s + x[1], 0);
    console.log(`600368 share ${(100 * (r.rows.find(x => x[0] === '600368.XSHG') || [0, 0])[1] / r.net).toFixed(1)}%  top2 share ${(100 * top2 / r.net).toFixed(1)}%`);
    console.log('targets per rebalance:', r.targets.map(t => `${t.date}:${t.n}`).join(' '));
    const hc = {}; for (const t of r.targets) hc[t.date] = t.codes.includes('600368.XSHG') ? 'y' : 'n';
    console.log('600368 targeted:', Object.entries(hc).map(([d, v]) => d.slice(5, 7) + v).join(' '));
  }
}
module.exports = { analyze, main };
