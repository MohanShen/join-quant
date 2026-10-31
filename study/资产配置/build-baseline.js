// Builds study/资产配置/baseline.py = py2to3(base 4a67a7b0) + OVERRIDE, byte-identical to the
// temp copy strategy-normalize.js measured for the epoch-9 ledger row. Also builds u-2-decomp.py:
// baseline + one DECOMP log line per day in before_market_open (previous closes of the 5 ETFs).
// The DECOMP edit is ONE asserted insertion; trading logic is untouched.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-10-26_多仓位再平衡22_77_年化_最大回撤11_17-4a67a7b0.py');
const base = py2to3(fs.readFileSync(SRC, 'utf8')) + OVERRIDE;
fs.writeFileSync(path.join(__dirname, 'baseline.py'), base);
console.log('built study/资产配置/baseline.py');

const ANCHOR = '    g.trade_day_count += 1\n';
if (base.split(ANCHOR).length !== 2) throw new Error('anchor not unique');
const INSERT = ANCHOR +
`    # u-2 DECOMP probe: previous closes (attribute_history at 09:00 => through previous_date)
    _codes = ['515450.XSHG', '513630.XSHG', '513100.XSHG', '518880.XSHG', '513650.XSHG']
    _vals = []
    for _s in _codes:
        try:
            _h = attribute_history(_s, 1, '1d', ['close'])
            _vals.append('%.4f' % float(_h['close'].iloc[-1]))
        except Exception as _e:
            _vals.append('nan')
    log.info('DECOMP %s %s' % (context.current_dt.date(), ' '.join(_vals)))
`;
const variant = base.replace(ANCHOR, INSERT);
fs.mkdirSync(path.join(__dirname, 'variants'), { recursive: true });
fs.writeFileSync(path.join(__dirname, 'variants/u-2-decomp.py'), variant);
if (variant.split('\n').length - base.split('\n').length !== 10) throw new Error('unexpected edit size');
console.log('built study/资产配置/variants/u-2-decomp.py');
