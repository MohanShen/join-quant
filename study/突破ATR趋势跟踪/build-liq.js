// q-e9-atr-liq (realizability): entry-scan liquidity floor, after study/破净价值多因子/build-liq.js.
// Base e79e9884 built as the normalizer builds it (py2to3(src) + OVERRIDE) with ONE asserted
// insertion in the entry loop (after the already-held check, before calc_indicators / cond checks):
//   if not liq_floor_ok(context, symbol): continue
// plus an appended helper. The helper evaluates the WHOLE pool once per scan date — mean `money`
// over the last 20 daily bars via attribute_history (excludes today, ends previous_date) — logs
// `LIQFLOOR <date> in=<n> out=<n>` and answers membership. Exits / sizing / regime / pool verbatim.
// FLOOR ladder: 1e7 = own feasibility (MAX_POSITION_PCT 0.5 x 1e6 / order_volume_ratio 0.05);
//               1e8 = 10x.
// Usage: node build-liq.js --floor 1e7 --out q-e9-atr-liq-1.py
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const FLOOR = arg('--floor', '1e7');
const FNAME = arg('--out', 'q-e9-atr-liq-1.py');
const SRC = path.join(ROOT, 'strategies', '2026-10-27_基于上一版本进行了适当调整_增加其攻击性-e79e9884.py');
const raw = py2to3(fs.readFileSync(SRC, 'utf8'));

const ANCHOR = '        ind = calc_indicators(symbol)\n        if ind is None:\n            continue\n\n        # --- 四个开仓条件 ---\n';
const n = raw.split(ANCHOR).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 anchor match, got ${n}`);
const INSERT = '        if not liq_floor_ok(context, symbol):  # q-e9-atr-liq: ONLY change vs baseline\n            continue\n';

const HELPER = `

# ----------------- liquidity floor (realizability q-e9-atr-liq) -----------------
LIQ_FLOOR = ${FLOOR}
LIQ_WIN = 20
__liq_cache = {'date': None, 'keep': set()}

def liq_floor_ok(context, symbol):
    d = str(context.previous_date)
    if __liq_cache['date'] != d:
        keep, vals = set(), []
        for s in g.pool:
            try:
                h = attribute_history(s, LIQ_WIN, '1d', ['money'], skip_paused=True, df=False)
                m = float(np.mean(h['money'])) if len(h['money']) > 0 else float('nan')
            except Exception as e:
                log.info('LIQFLOOR ERROR %s %s exc=%s' % (d, s, str(e)))
                m = float('nan')
            if m == m and m >= LIQ_FLOOR:
                keep.add(s)
            vals.append('%s:%.3g' % (s, m))
        __liq_cache['date'] = d
        __liq_cache['keep'] = keep
        log.info('LIQFLOOR %s in=%d out=%d floor=%.0f %s' % (d, len(g.pool), len(keep), LIQ_FLOOR, ' '.join(vals)))
    return symbol in __liq_cache['keep']
`;

let body = raw.replace(ANCHOR, INSERT + ANCHOR);
body = body + HELPER;
// assert: removing exactly the insertion + helper gives back the source
const restored = body.replace(INSERT, '').replace(HELPER, '');
if (restored !== raw) throw new Error('variant is not source + one insertion + helper');
const a = raw.split('\n'), b = body.replace(HELPER, '').split('\n');
if (b.length - a.length !== 2) throw new Error('insertion is not 2 lines');
const out = path.join(__dirname, 'variants', FNAME);
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'floor', FLOOR);
