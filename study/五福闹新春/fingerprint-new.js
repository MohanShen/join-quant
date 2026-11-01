// Step-0 fingerprint of new members: size leg? key knobs? pool size? nearest known member by line Jaccard.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const tags = process.argv.slice(2);
const all = fs.readdirSync(path.join(ROOT, 'strategies'));
const norm = s => new Set(s.split('\n').map(l => l.replace(/#.*/, '').trim()).filter(l => l.length > 8));
const KNOWN = ['bf30eb36', '17b3b439', '73b13d92', '1cc495be', 'bba95a11', 'b50e4387', 'fd5d388d', '7c2e9238', 'aaee3035'];
const known = KNOWN.map(t => [t, all.find(f => f.includes(t))]).filter(x => x[1])
  .map(([t, f]) => [t, norm(fs.readFileSync(path.join(ROOT, 'strategies', f), 'utf8'))]);
for (const t of tags) {
  const f = all.find(x => x.includes(t));
  const src = fs.readFileSync(path.join(ROOT, 'strategies', f), 'utf8');
  const knobs = [...new Set(src.match(/g\.(holdings_num|enable_weak_r2_filter|sell_cooldown_days|m_days|r2_threshold|stock_num)\s*=\s*[^\s#]+/g) || [])];
  const codes = new Set(src.match(/\d{6}\.XSH[GE]/g) || []);
  const L = norm(src);
  const sims = known.map(([k, S]) => {
    let i = 0; for (const x of L) if (S.has(x)) i++;
    return [k, (i / (L.size + S.size - i)).toFixed(2)];
  }).sort((a, b) => b[1] - a[1]).slice(0, 3);
  console.log(`== ${t} ${src.split('\n').length} lines | size-leg refs ${(src.match(/market_cap|circulating_market_cap/g) || []).length} | codes ${codes.size}`);
  console.log('   knobs', knobs.join(' '));
  console.log('   nearest', sims.map(s => s.join(':')).join(' '));
}
