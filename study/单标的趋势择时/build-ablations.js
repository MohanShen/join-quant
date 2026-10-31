// u-2..u-5 ablations: baseline + ONE asserted edit each.
const fs = require('fs');
const path = require('path');
const base = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');
function swap(s, a, b) {
  if (s.split(a).length !== 2) throw new Error('anchor not unique: ' + a);
  return s.replace(a, b);
}
const R0 = 'g.strategy_weights = {0: 1.0, 1: 0.0, 2: 0.0}';
const R1 = 'g.strategy_weights = {0: 0.0, 1: 0.8, 2: 0.2}';
const R2 = 'g.strategy_weights = {0: 0.0, 1: 0.0, 2: 1.0}';
const out = {
  'u-2-router': swap(swap(base, R0, R2), R1, R2),
  'u-3-norsi': swap(base, R1, R2),
  'u-4-nochandelier': swap(base, 'g.stop_loss_atr_multi = 3.0', 'g.stop_loss_atr_multi = 99.0'),
  'u-5-noscale': swap(base, 'g.position_scale = 1.2 / current_vol_ratio', 'g.position_scale = 1.0'),
};
for (const [k, v] of Object.entries(out)) fs.writeFileSync(path.join(__dirname, 'variants', k + '.py'), v);
console.log('built', Object.keys(out).join(','));
