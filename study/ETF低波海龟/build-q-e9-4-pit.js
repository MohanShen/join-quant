// q-e9-4 (as specified in queue.json `design`): pool hindsight test on the overlay-off arm q-e9-3.
// The hand-picked 14-name g.all_risk_etfs dict is replaced by a POINT-IN-TIME equity-ETF pool rebuilt
// every trading day (before_open) from get_all_securities(['etf'], date=previous_date), reusing the
// construction of study/ETF动量/variants/pit-pool.py (listed >= 250 calendar days, trailing-20-bar
// MEDIAN money >= 2e7, not paused, current risk holding unioned in) plus an equity-only filter.
// g.safe_etfs, vol ranking, min-hold, 10% switch band, 0.40 median gate: verbatim.
// Asserted: the only edits are (1) the g.all_risk_etfs dict block, (2) an appended pool block
// before the OVERRIDE, (3) an appended observation-only daily HOLD logger. strategies/ untouched.
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');

const q3 = fs.readFileSync(path.join(__dirname, 'variants/q-e9-3.py'), 'utf8');
if (!q3.startsWith('# q-e9-3:')) throw new Error('q-e9-3 header');
if (!q3.endsWith(OVERRIDE)) throw new Error('q-e9-3 OVERRIDE differs from live OVERRIDE');
const body = q3.slice(q3.indexOf('\n') + 1, q3.length - OVERRIDE.length);

const OLD = [
  '    # 风险资产（权益类 + 商品 + 海外）',
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
  '    # q-e9-4: risk pool = point-in-time A-share EQUITY ETF pool, rebuilt daily before the open',
  '    # (see POINT-IN-TIME EQUITY POOL block at the bottom). Was 14 hand-picked names.',
  '    g.all_risk_etfs = {}',
  "    run_daily(rebuild_pool, 'before_open')",
  "    run_daily(q4_hold_log, '14:55')   # observation only",
  ''].join('\n');

const POOL = `
# ===== POINT-IN-TIME EQUITY POOL (q-e9-4; construction from study/ETF动量/variants/pit-pool.py) =====
#  - universe: get_all_securities(['etf'], date=context.previous_date) — only funds that existed then.
#  - 次新 exclusion: listed < 250 calendar days is never eligible (harness §3).
#  - liquidity floor 2e7 CNY = 1,000,000 full position / order_volume_ratio 0.05, on the trailing
#    20-bar MEDIAN money (pit-pool's rule, so one spike day cannot admit an illiquid fund); not paused.
#  - EQUITY-ONLY (queue design): display_name must not match POOL_EXCL_NAME, and code prefix must
#    not be SH 511 (bond/money ETFs), 513 (cross-border/QDII), 518 (gold). The low-vol rank would
#    otherwise degenerate to a money/short-bond fund.
#  - rebuilt every trading day; the current RISK holding is unioned in (pit-pool rule) so a name
#    drifting under the floor is handled by the strategy's own ranking/min-hold/switch band rather
#    than a forced exit. Safe-leg codes are never unioned into the risk pool.
import re as _q4re
POOL_MIN_MONEY   = 2.0e7
POOL_MIN_LISTED  = 250
POOL_LIQ_WINDOW  = 20
POOL_TYPES       = ['etf']
POOL_EXCL_NAME   = _q4re.compile(u'债|货币|现金|黄金|豆粕|商品|纳指|标普|日经|德国|恒生|港|H股|纳斯达克'
                                 u'|理财|短融|日利|添益|快线|快钱|财富宝|保证金|货基'
                                 u'|QDII|美国|美股|美元|道琼斯|中概|法国|日本|亚太|东南亚|沙特|欧洲|英国|全球|海外'
                                 u'|期货|原油|白银|能源化工|有色期货|大宗')
POOL_EXCL_PREFIX = ('511', '513', '518')
# Non-equity funds whose display_name carries no excluded word (found in run 1's POOLLIST audit):
# 159980 有色ETF大成 = 大成有色金属期货ETF (commodity futures); 159831 金ETF嘉实 = 嘉实黄金ETF.
POOL_EXCL_CODE   = ('159980.XSHE', '159831.XSHE')


def _pool_not_paused(cur, c):
    try:
        return not cur[c].paused
    except Exception:
        return False


def _pool_median_money(cand, d):
    candset = set(cand)
    out = {}
    try:
        try:
            px = get_price(cand, end_date=d, count=POOL_LIQ_WINDOW, frequency='daily',
                           fields=['money'], skip_paused=False, panel=False)
        except TypeError:
            px = get_price(cand, end_date=d, count=POOL_LIQ_WINDOW, frequency='daily',
                           fields=['money'], skip_paused=False)
        cols = list(getattr(px, 'columns', []))
        if 'code' in cols:
            for c, grp in px.groupby('code'):
                out[c] = float(grp['money'].median())
        elif 'money' in cols and getattr(px.index, 'nlevels', 1) > 1:
            s = px['money']
            for lvl in (0, 1):
                g2 = s.groupby(level=lvl).median()
                if len(candset & set(g2.index)) > 0:
                    out = dict((k, float(v)) for k, v in g2.items())
                    break
        else:
            m = px['money'].median()
            out = dict((k, float(v)) for k, v in m.items())
    except Exception as e:
        log.error('POOLWARN batched liquidity failed (%s)' % e)
        out = {}
    if len(candset & set(out.keys())) < len(candset) * 0.5:
        log.error('POOLWARN batched shape unusable (%d/%d) -> per-code fallback'
                  % (len(candset & set(out.keys())), len(candset)))
        out = {}
        for c in cand:
            try:
                p1 = get_price(c, end_date=d, count=POOL_LIQ_WINDOW, frequency='daily',
                               fields=['money'], skip_paused=False)
                out[c] = float(p1['money'].median())
            except Exception:
                continue
    return out


def rebuild_pool(context):
    d = context.previous_date
    allsec = get_all_securities(types=POOL_TYPES, date=d)
    sd = pd.to_datetime(allsec['start_date'])
    old = allsec.index[sd <= pd.Timestamp(d) - pd.Timedelta(days=POOL_MIN_LISTED)]
    names = allsec['display_name']
    cand = [c for c in old
            if not c.startswith(POOL_EXCL_PREFIX) and not POOL_EXCL_NAME.search(names[c])
            and c not in g.safe_etfs and c not in POOL_EXCL_CODE]
    med = _pool_median_money(cand, d) if cand else {}
    cur = get_current_data()
    pool = [c for c in cand if med.get(c, 0.0) >= POOL_MIN_MONEY and _pool_not_paused(cur, c)]
    held = [s for s in context.portfolio.positions
            if context.portfolio.positions[s].total_amount > 0 and s not in g.safe_etfs]
    g.all_risk_etfs = dict((c, names.get(c, c)) for c in sorted(set(pool) | set(held)))
    log.info('POOLSIZE %s listed=%d old=%d equity=%d pool=%d'
             % (str(d), len(allsec), len(old), len(cand), len(g.all_risk_etfs)))
    if getattr(g, 'q4_pool_month', None) != (d.year, d.month):
        g.q4_pool_month = (d.year, d.month)
        log.info('POOLLIST %s %s' % (str(d), ','.join('%s|%s' % (c, n) for c, n in g.all_risk_etfs.items())))


def q4_hold_log(context):
    held = [(c, p.total_amount * p.price) for c, p in context.portfolio.positions.items()
            if p.total_amount > 0]
    log.info('Q4HOLD %s %s' % (str(context.current_dt.date()),
             ';'.join('%s|%s|%.0f' % (c, etf_name(c), v) for c, v in held) or 'CASH'))
# ===== END POINT-IN-TIME EQUITY POOL =====
`;

const n = body.split(OLD).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 pool block, got ${n}`);
const i = body.indexOf(OLD);
const swapped = body.slice(0, i) + NEW + body.slice(i + OLD.length);
if (swapped.slice(0, i) !== body.slice(0, i) || swapped.slice(i + NEW.length) !== body.slice(i + OLD.length))
  throw new Error('diff escaped the pool block');
const hdr = '# q-e9-4 (pit): q-e9-3 (overlay off) with the 14 hand-picked risk ETFs -> daily point-in-time equity ETF pool. Built by study/ETF低波海龟/build-q-e9-4-pit.js\n';
const out = path.join(__dirname, 'variants', 'q-e9-4-pit.py');
fs.writeFileSync(out, hdr + swapped + POOL + OVERRIDE);
console.log('wrote', out);
