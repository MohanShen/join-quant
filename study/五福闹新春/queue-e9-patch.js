// gatekeeper patch, 2026-10-25 — corrections found by auditing the parent book itself.
// Run once: node -e "require('./study/五福闹新春/queue-e9-patch.js')"
const rq = require('../../utils/research-queue');
const F = '五福闹新春';
const q = rq.load(F);
const get = id => { const e = q.find(x => x.id === id); if (!e) throw new Error(`missing ${id}`); return e; };

const AUDIT = `\n\n⚠⚠ **GATEKEEPER CODE AUDIT of the parent file itself (2026-10-25) — three corrections, do not re-derive:**
(1) **The weight line is L118, not L87.** Both generators said L87; in \`study/五福闹新春/q-e9-pit_bf30eb36.py\` the live assignment is **L118** \`g.portfolio_value_proportion = [0.5, 0, 0.5, 0]  # 小市值/ETF轮动 (用于长回测)\`, inside \`set_params\`, with the author's other three configs commented out at L116/L117/L119/L120.
(2) **The "duplicate assignment at L3555" is L3586 and is UNREACHABLE for this edit — risk RESOLVED, no proof needed from the builder.** It sits in \`_ensure_make_record_globals\` (a 模拟盘热更新 fallback) behind \`if not pv_ok:\`, where \`pv_ok = isinstance(pv,(list,tuple)) and len(pv) >= 4\`. A 4-element edited list keeps \`pv_ok\` True, so the literal never re-fires; and if the enclosing \`need\` branch runs for another reason it rebuilds \`g.sub_account\` by RE-READING the edited value. So the feared silent revert to the parent config cannot happen. Still print both lines' final effective values as a cheap confirmation, but a failure here is no longer the expected failure mode.
(3) **\`[0,0,0.5,0]\` over \`[0,0,1,0]\` is right for a SECOND, stronger reason neither generator stated.** The book special-cases the exact literal \`[0, 0, 1, 0]\` as an author-supported **pure 五福 mode** at ≥8 sites: \`pure_wufu_mode = (g.portfolio_value_proportion == [0,0,1,0])\` at L1629/1657/1734/1774/2005, \`if g.portfolio_value_proportion != [0,0,1,0]\` at L665, and the \`init_range_bound_status\` gate at L103–104. Under the parent \`[0.5,0,0.5,0]\` every one of those is **False**; under \`[0,0,0.5,0]\` every one is **still False**; under \`[0,0,1,0]\` all of them **flip**, changing the ETF sleeve's own logic. So \`[0,0,1,0]\` would have been a logic-branch confound far worse than the fill-size one A avoided. **Build invariant to assert: \`pure_wufu_mode\` is False in both parent and variant and all 8 guards take the same branch.**
(4) Runnability of a zero-weight stock sleeve is **author-supported**, not a gamble: \`capital_balance\` returns early at L265 on \`g.portfolio_value_proportion[0] <= 0\`, and its own docstring states 「[1,0,0,0] 与 [0.5,0,0.5,0] 下策略1的收益率曲线与仓位逻辑可一致（同比例缩放下）」.`;

get('q-e9-leg').design += AUDIT;
get('imp-e9-1').design += `\n\n⚠ The L3555/L3586 risk is RESOLVED — see q-e9-leg's gatekeeper code audit (the fallback assignment is behind \`if not pv_ok:\` and cannot fire for a 4-element list). The live weight line is **L118**.`;

get('imp-e9-2').note += `\n⚠⚠ **A fourth reason, found in the gatekeeper's own code audit: it is not one line in effect.** L137 \`g.strategy_ETF_2000_proportion = g.portfolio_value_proportion[1]\` plus \`capital_balance_2(context)\` and the \`g.strategy_ETF_2000_proportion_reset\` 拨正 detector mean that moving index [1] from 0 to 0.2 **activates a whole rebalancing machine that is dormant in the parent**, not merely a capital share. So the Δ bundles (a) the 中证2000 sleeve's returns, (b) two weight reductions, and (c) a previously-inert 拨正 controller. That is three mechanisms in one run. The L3586 revert risk, by contrast, is RESOLVED (see q-e9-leg's audit) — the real objection is attribution, not build safety.`;

rq.save(F, q);
for (const id of ['q-e9-leg', 'imp-e9-1', 'imp-e9-2']) console.log(`patched ${id}`);
