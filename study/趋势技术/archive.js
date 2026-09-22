// Records the round's research consumption event. No validated_strategies/ archive: nothing in
// this round cleared the 1.5 sharpe stage gate, so the family's epoch-6 VAL was NOT spent.
//   node -e "require('./study/趋势技术/archive.js')"
require('../../utils/consumption').record({
  key: '趋势技术', kind: 'family', stage: 'research', runId: 'run-family-2026-09-22', outcome: 'done',
  note: '8 epoch-6 TRAIN backtests (27 JQ min: used 113 -> 140), 0 VAL (no candidate passes sharpe 1.5; budget kept); '
    + 'base 33b1b1e3 no-trades on epoch 6 (avoid_future_data) -> e6-1 lookahead-clean anchor obj -0.1636 '
    + '(annual 3.67 / sharpe -0.01 / maxDD 20.03; epoch 2 was 0.2936 with today\'s close+open read at 08:00); '
    + 'edges: 趋势择时 measured as a component (gate off -41.8%, worse than buy-and-hold; pure MA20 index timer -11.7%), '
    + '动量 measured as three-period resonance (mirror -23.7%, no week/month -23.8%, loose 20d band -31.4%, all both years); '
    + 'imp-1 gate-as-exit rejected (-11.1%, maxDD 30); e6-1a probe: pre-open get_price(end_date=today) under avoid_future_data fails, not truncates. '
    + 'Family has no gate-passing member on epoch 6; ledger row 0.2936 (epoch 2) is a lookahead artifact',
});
console.log('recorded research event for 趋势技术');
