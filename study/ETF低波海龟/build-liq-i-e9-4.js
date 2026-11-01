// liq-i-e9-4: i-e9-4 + buy-side feasibility floor per position = capital / 3 / order_volume_ratio,
// both READ FROM THE HARNESS (expect ≈6.67e6 CNY/day), on 20-day AVERAGE money ending previous_date
// (liq-e9-1 convention: held names exempt, floor_live = total_value/3/ovr logged beside it).
// Applied to the buy candidate set of rebalance_top3 (risk pool ∪ safe leg when allowed); the 0.40
// median regime signal is untouched. ONE asserted edit + appended helper; live OVERRIDE.
// Why the run exists: the PIT pool's 20-bar median >= 2e7 implies 20-bar mean >= 1e7 > floor for
// every NON-held risk entry (inert by construction), but the SAFE leg 511010/511260 is not under
// the pool floor, so the floor could bind there. The log therefore records safe-leg money daily.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');
const sha = s => crypto.createHash('sha256').update(s).digest('hex').slice(0, 16);

const hc = harness.config();
const CAPITAL = hc.costs.capital, OVR = hc.costs.orderVolumeRatio, SLOTS = 3;
const FLOOR = CAPITAL / SLOTS / OVR;
console.log(`harness epoch ${hc.epoch}: capital ${CAPITAL} ovr ${OVR} slots ${SLOTS} => floor ${FLOOR}`);
if (Math.abs(FLOOR - 6666666.67) > 1) throw new Error('floor expected ~6.67e6, got ' + FLOOR);

const P = fs.readFileSync(path.join(__dirname, 'variants/i-e9-4.py'), 'utf8');
if (!P.startsWith('# i-e9-4:')) throw new Error('i-e9-4 header');
if (!P.endsWith(OVERRIDE)) throw new Error('i-e9-4 OVERRIDE differs from live');
let b = P.slice(0, P.length - OVERRIDE.length);
const FROM = '    vol = get_vol_rank(context, candidates)\n    if len(vol) == 0:\n        log.warn("I3 ';
const TO = '    candidates = liq_screen_i4(context, candidates)  # liq-i-e9-4\n' + FROM;
const n = b.split(FROM).length - 1;
if (n !== 1) throw new Error('expected 1 match, got ' + n);
const b2 = b.replace(FROM, TO);
const x = b.split('\n'), y = b2.split('\n');
if (y.length !== x.length + 1) throw new Error('edit moved more than one line');
const HELPER = `

# ==================== liq-i-e9-4: buy-side feasibility floor (capital/3/ovr) ====================
LIQ4_CAPITAL = ${CAPITAL}.0  # harness capital
LIQ4_OVR = ${OVR}  # harness orderVolumeRatio
LIQ4_SLOTS = ${SLOTS}
LIQ4_DAYS = 20

def liq_screen_i4(context, cands):
    codes = list(cands.keys())
    floor = LIQ4_CAPITAL / LIQ4_SLOTS / LIQ4_OVR
    floor_live = float(context.portfolio.total_value) / LIQ4_SLOTS / LIQ4_OVR
    pos = context.portfolio.positions
    held = set([c for c in pos if pos[c].total_amount > 0])
    try:
        df = get_price(codes, end_date=context.previous_date, count=LIQ4_DAYS,
                       frequency='daily', fields=['money'], panel=False)
        money = df.groupby('code')['money'].mean().to_dict()
    except Exception as e:
        money = None
    if not money:
        log.info("LIQ4 date=%s floor=%.0f in=%d status=bypass-nodata" % (context.previous_date, floor, len(codes)))
        return cands
    kept = {}
    removed = []
    live_removed = []
    for c in codes:
        m = float(money.get(c, 0.0) or 0.0)
        if c in held:
            kept[c] = cands[c]
            continue
        if m < floor_live:
            live_removed.append(c)
        if m >= floor:
            kept[c] = cands[c]
        else:
            removed.append(c)
    safe = ';'.join(['%s:%.0f' % (c, float(money.get(c, 0.0) or 0.0)) for c in codes if c in g.safe_etfs]) or '-'
    nonheld = [float(money.get(c, 0.0) or 0.0) for c in codes if c not in held and c not in g.safe_etfs]
    log.info("LIQ4 date=%s floor=%.0f floor_live=%.0f in=%d out=%d removed=%s live_removed=%s safe=%s minRiskNonHeld=%.0f status=ok"
             % (context.previous_date, floor, floor_live, len(codes), len(kept),
                ';'.join(removed) or '-', ';'.join(live_removed) or '-', safe,
                sorted(nonheld)[0] if nonheld else -1))
    return kept
`;
const hdr = `# liq-i-e9-4: i-e9-4 + buy-side floor capital ${CAPITAL} / ${SLOTS} / ovr ${OVR} = ${FLOOR.toFixed(0)} CNY/day on 20d avg money; held exempt. Built by study/ETF低波海龟/build-liq-i-e9-4.js\n`;
const outBody = hdr + b2 + HELPER + OVERRIDE;
if (/(^|[^\w.])sum\(/.test(HELPER)) throw new Error('builtin sum() in helper');
const out = path.join(__dirname, 'variants', 'liq-i-e9-4.py');
fs.writeFileSync(out, outBody);
console.log('wrote', out, 'sha', sha(outBody), 'parent sha', sha(P));
