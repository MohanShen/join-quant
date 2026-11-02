// i-2-indcap (improve; also the yield-vs-sector test for 股息率): on the REFERENCE BOOK variants/dxpit.py,
//   un-quote the author's own cc_industry (source L185-211, dxpit L192-219 — its whole body sat inside a
//   ''' docstring and nothing called it) and call it ONCE at the pinned site: on the cascade df right after
//   the gxl3 head(20) pass (base L103 / dxpit L110), before the final gxl sort / head(10) (base L104 /
//   dxpit L111). Cascade gxl -> <20 cut -> gxl2 -> gxl3 -> gxl kept VERBATIM.
//   Translation: the author's rets=rets.append(stock_list.loc[index]) row-append is replaced by collecting
//   kept index labels and one .loc[] — same rows, same order, same columns (merge adds short_name,
//   industry_2, industry_id). Industry field = finance.STK_COMPANY_INFO.industry_id (author's), cap = 2 (author's).
//   Observation: dxpit's DXPRE/DXPOST + P&L logger DROPPED. DXMON with n_qual, bfive, bten, ref_overlap vs
//   dxpit bfive, and industry composition of bfive / ref bfive / names the cap dropped (obs recomputes on a copy).
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const ref = fs.readFileSync(path.join(__dirname, 'variants', 'dxpit.py'), 'utf8');
if (!ref.endsWith(OVERRIDE)) throw new Error('dxpit.py does not end with the live OVERRIDE');
let body = ref.slice(0, ref.length - OVERRIDE.length);

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// ---- strip dxpit's observation layer ----
const H0 = '\n\n# ===== u-e9-dxpit observation helpers (nothing below feeds an order) =====\n';
const H1 = '# ===== end u-e9-dxpit observation helpers =====\n';
const i0 = body.indexOf(H0), i1 = body.indexOf(H1);
if (i0 < 0 || i1 < 0 || body.split(H0).length !== 2) throw new Error('dxpit helper block not found exactly once');
body = body.slice(0, i0) + body.slice(i1 + H1.length);
body = edit(body, "    _dxp_pos(context, 'DXPRE')  # u-e9-dxpit obs\n", '');
body = edit(body, "    _dxp_pos(context, 'DXPOST')  # u-e9-dxpit obs\n", '');
body = edit(body, "    _dxp_mon(context, df)  # u-e9-dxpit obs\n", "    _dxc_mon(context, df)  # i-2-indcap obs\n");
if (/_dxp_|after_trading_end|DXPNL/.test(body)) throw new Error('dxpit obs residue');
const STRIPPED = body;

// ---- (1) un-quote cc_industry (translated row-append, same semantics) ----
const CC_OLD =
"def cc_industry(stock_list):\n" +
"    '''\n" +
"    stocks=list(stock_list['code'])\n" +
"    \n" +
"    compinfo=finance.run_query(\n" +
"        query(\n" +
"            finance.STK_COMPANY_INFO.code,\n" +
"            finance.STK_COMPANY_INFO.short_name,\n" +
"            finance.STK_COMPANY_INFO.industry_2,\n" +
"            finance.STK_COMPANY_INFO.industry_id).filter(\n" +
"                finance.STK_COMPANY_INFO.code.in_(stocks)\n" +
"                ))\n" +
"                \n" +
"    stock_list=pd.merge(stock_list,compinfo,on='code')\n" +
"    \n" +
"    \n" +
"    p=dict.fromkeys(set(compinfo['industry_id']),0)\n" +
"    rets=pd.DataFrame()\n" +
"    \n" +
"    for index in list(stock_list.index):\n" +
"        industry_id=stock_list.loc[index].industry_id\n" +
"        num=p.get(industry_id,0)\n" +
"        if num<2: \n" +
"           rets=rets.append(stock_list.loc[index])\n" +
"        p[industry_id]=num+1\n" +
"        \n" +
"    return rets\n" +
"    '''\n";
const CC_NEW =
"def cc_industry(stock_list):\n" +
"    # i-2-indcap: un-quoted (was a ''' docstring); row-append translated to index collection, same rows/order\n" +
"    stocks=list(stock_list['code'])\n" +
"    \n" +
"    compinfo=finance.run_query(\n" +
"        query(\n" +
"            finance.STK_COMPANY_INFO.code,\n" +
"            finance.STK_COMPANY_INFO.short_name,\n" +
"            finance.STK_COMPANY_INFO.industry_2,\n" +
"            finance.STK_COMPANY_INFO.industry_id).filter(\n" +
"                finance.STK_COMPANY_INFO.code.in_(stocks)\n" +
"                ))\n" +
"                \n" +
"    stock_list=pd.merge(stock_list,compinfo,on='code')\n" +
"    \n" +
"    \n" +
"    p=dict.fromkeys(set(compinfo['industry_id']),0)\n" +
"    _keep=[]\n" +
"    \n" +
"    for index in list(stock_list.index):\n" +
"        industry_id=stock_list.loc[index].industry_id\n" +
"        num=p.get(industry_id,0)\n" +
"        if num<2: \n" +
"           _keep.append(index)\n" +
"        p[industry_id]=num+1\n" +
"        \n" +
"    rets=stock_list.loc[_keep]\n" +
"    return rets\n";
body = edit(body, CC_OLD, CC_NEW);

// ---- (2) the ONE call site: after gxl3 head(20), before final gxl head(10) ----
const L110 = "    df=df.sort_values(by='gxl3',ascending=False).head(g.stock_num*4)\n";
const L111 = "    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*2)\n";
body = edit(body, L110 + L111, L110 + "    df=cc_industry(df)  # i-2-indcap: author's industry cap (<=2 per industry_id), pinned site\n" + L111);
const SEM = body;

// ---- (3) DXMON + overlap/industry obs ----
const refLog = fs.readFileSync(path.join(__dirname, 'variants', 'dxpit.log.txt'), 'utf8');
const refMon = {};
for (const m of refLog.matchAll(/DXMON date=(\S+) n_qual=(\d+) bfive=(\S*) bten=/g)) refMon[m[1]] = m[3].split(',').filter(Boolean);
if (Object.keys(refMon).length !== 12) throw new Error('expected 12 reference DXMON months');
const pyDict = '{' + Object.entries(refMon).map(([d, l]) => `'${d}': [${l.map(c => `'${c}'`).join(', ')}]`).join(',\n    ') + '}';
const HELPERS = `

# ===== i-2-indcap observation helpers (nothing below feeds an order) =====
_DXC_REF_BFIVE = ${pyDict}

def _dxc_ind(codes):
    if not codes:
        return {}
    _ci = finance.run_query(query(finance.STK_COMPANY_INFO.code, finance.STK_COMPANY_INFO.industry_id, finance.STK_COMPANY_INFO.industry_2).filter(finance.STK_COMPANY_INFO.code.in_(list(codes))))
    _m = {}
    for _i in range(len(_ci)):
        _m[_ci.iloc[_i]['code']] = '%s|%s' % (_ci.iloc[_i]['industry_id'], _ci.iloc[_i]['industry_2'])
    return _m

def _dxc_mon(context, df):
    try:
        _d = str(context.current_dt.date())
        _ref = _DXC_REF_BFIVE.get(_d)
        _ov = -1 if _ref is None else len([c for c in g.bfive if c in _ref])
        _empty = 1 if df.shape[0] <= g.stock_num*2 else 0
        _pre = []
        if not _empty:
            _x = df.copy().sort_values(by='gxl',ascending=False).head(g.stock_num*16)
            if len(_x)<g.stock_num*4:
                _x = _x.head(len(_x) -g.stock_num*2)
            _x = _x.sort_values(by='gxl2',ascending=False).head(g.stock_num*8)
            _x = _x.sort_values(by='gxl3',ascending=False).head(g.stock_num*4)
            _pre = list(_x['code'])
        _m = _dxc_ind(set(_pre) | set(g.bfive) | set(g.bten) | set(_ref or []))
        _post = list(cc_industry(_x)['code']) if _pre else []
        _drop = [c for c in _pre if c not in _post]
        log.info('DXMON date=%s n_qual=%d empty=%d bfive=%s bten=%s ref_overlap=%d ref_bfive=%s n_pre20=%d n_post=%d' % (_d, df.shape[0], _empty, ','.join(g.bfive), ','.join(g.bten), _ov, ','.join(_ref or []), len(_pre), len(_post)))
        log.info('DXIND date=%s bfive=%s' % (_d, ';'.join(['%s=%s' % (c, _m.get(c, '?')) for c in g.bfive])))
        log.info('DXINDREF date=%s ref_bfive=%s' % (_d, ';'.join(['%s=%s' % (c, _m.get(c, '?')) for c in (_ref or [])])))
        log.info('DXINDBTEN date=%s bten=%s' % (_d, ';'.join(['%s=%s' % (c, _m.get(c, '?')) for c in g.bten])))
        log.info('DXDROP date=%s dropped=%s' % (_d, ';'.join(['%s=%s' % (c, _m.get(c, '?')) for c in _drop])))
    except Exception as _e:
        log.error('DXC-ERR mon err=%r' % (_e,))
# ===== end i-2-indcap observation helpers =====
`;
body = body + HELPERS;

// ---- assertions ----
for (const k of ['order_target_value', 'order_value', 'order(', 'run_monthly', 'run_daily', 'run_weekly', '.limit(12))', 'board_plan_pub_date<=d0', 'comp_value=market_cap*0.02',
  "g.bten=list(df.head(g.stock_num*2)['code'])", "g.bfive=list(df.head(g.stock_num)['code'])", 'g.stock_num = 5',
  "    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*16)\n", "    if len(df)<g.stock_num*4:\n        df=df.head(len(df) -g.stock_num*2)\n",
  "    df=df.sort_values(by='gxl2',ascending=False).head(g.stock_num*8)\n", L110, L111]) {
  if (SEM.split(k).length !== STRIPPED.split(k).length) throw new Error('verbatim element changed: ' + k);
}
if (!SEM.includes("run_monthly(main,1,time='9:30')")) throw new Error('schedule changed');
if ((SEM.match(/cc_industry\(/g) || []).length !== 2) throw new Error('expected def + exactly one call of cc_industry');
if (SEM.includes('rets.append')) throw new Error('row-append residue');
const a = STRIPPED.split('\n'), b = SEM.split('\n');
// def block: -2 quote lines, +1 comment, +1 rets= line, => 0 net; call site +1
if (b.length - a.length !== 1) throw new Error('expected net +1 line, got ' + (b.length - a.length));
if (body.slice(0, body.length - HELPERS.length) !== SEM) throw new Error('obs not additive');

const out = path.join(__dirname, 'variants', 'indcap.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
