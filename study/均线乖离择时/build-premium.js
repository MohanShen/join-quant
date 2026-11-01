// Builds study/均线乖离择时/variants/u-premium.py — OBSERVE-ONLY probe.
// py2to3(base) + ONE asserted edit (an extra run_daily at 09:31 scheduling a logger) + the
// logger function appended + OVERRIDE. Trading logic is verbatim; the logger only reads data.
// Logs per day: 'PREM today sig_date close nav_date nav premium nav_ma60 navbias n_nav'.
// premium = close(sig_date)/NAV(nav_date) - 1 ; navBias = NAV/MA60(NAV) - 1 (last 60 NAV obs).
// nav_date is logged so a NAV dated >= today (lookahead) is visible.
// Usage: node -e "require('./study/均线乖离择时/build-premium.js')"
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const REL = 'strategies/2026-10-28_使用标普500_60日均线乖离度增加超额收益的策略-648c2da3.py';
let src = py2to3(fs.readFileSync(path.join(ROOT, REL), 'utf8'));

const ANCHOR = "    run_daily(log_after_close, time='15:30', reference_security=g.security)\n";
if (src.split(ANCHOR).length !== 2) throw new Error('anchor not unique');
src = src.replace(ANCHOR, ANCHOR + "    run_daily(log_premium_probe, time='09:31', reference_security=g.security)  # u-premium probe (observe-only)\n");

const PROBE = `

# ===== u-premium probe (observe-only; no orders, no state the book reads) =====
def log_premium_probe(context):
    try:
        today = context.current_dt.date()
        s = g.daily_signal
        nav = get_extras('unit_net_value', [g.security], end_date=context.previous_date, count=62)
        col = nav[g.security].dropna()
        if len(col) == 0:
            log.info('PREM %s NONAV' % today)
            return
        nav_date = col.index[-1].date()
        nav_last = float(col.iloc[-1])
        tail = [float(v) for v in col.iloc[-60:]]
        nav_ma = math.fsum(tail) / len(tail)
        navbias = nav_last / nav_ma - 1
        if s is not None:
            close = s['close']
            sig_date = s['date']
            pbias = s['bias']
        else:
            close = float('nan')
            sig_date = None
            pbias = float('nan')
        premium = close / nav_last - 1
        log.info('PREM %s %s %.4f %s %.4f %+.6f %.4f %+.6f %d %+.6f'
                 % (today, sig_date, close, nav_date, nav_last, premium, nav_ma, navbias, len(tail), pbias))
    except Exception as e:
        log.info('PREM %s ERR %s' % (context.current_dt.date(), e))
`;
const body = src + PROBE + OVERRIDE;
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!body.includes(pin)) throw new Error(`missing pin: ${pin}`);
}
const header =
  `# study variant u-premium — family: 均线乖离择时 (OBSERVE-ONLY probe)\n` +
  `# source: ${REL}\n` +
  `# construction: py2to3(source) + one added run_daily(log_premium_probe,'09:31') + appended logger + OVERRIDE\n` +
  `# control: must reproduce base e9 row (annual 34.90 / sharpe 2.02 / maxDD 9.98)\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/均线乖离择时/build-premium.js\n`;
fs.mkdirSync(path.join(__dirname, 'variants'), { recursive: true });
const out = path.join(__dirname, 'variants', 'u-premium.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out), 'bytes', (header + body).length);
