// u-1 buy-and-hold control: baseline + two asserted edits (chandelier disabled, target_ratio=1.0).
const fs = require('fs');
const path = require('path');
const base = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');
function swap(s, a, b) {
  if (s.split(a).length !== 2) throw new Error('anchor not unique: ' + a);
  return s.replace(a, b);
}
let v = swap(base, 'if current_position > 0 and current_price < chandelier_exit_price:',
  'if False and current_position > 0 and current_price < chandelier_exit_price:');
v = swap(v, '    target_value = total_value * target_ratio',
  '    target_ratio = 1.0  # u-1 control: always fully invested\n    target_value = total_value * target_ratio');
fs.mkdirSync(path.join(__dirname, 'variants'), { recursive: true });
fs.writeFileSync(path.join(__dirname, 'variants/u-1-buyhold.py'), v);
console.log('built u-1-buyhold.py');
