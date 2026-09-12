# research/ — new data, factors, trading ideas

Reserved for a **future auto-research pipeline** operating in a broader context
(new data, factors, and different trading ideas).

The current strategy-optimization loop was renamed to **auto-enhance** and lives in
`enhance/` (see `enhance/program.md`). Do not put the enhance loop here.

## Contents

- **`factorlib/`** — JoinQuant's 因子看板 (factor dashboard), ingested by
  `node utils/factorlib-ingest.js`. 285 stock factors with their formulas, IC mean,
  IR, quintile returns, Sharpe, drawdown and turnover, pulled at **both** the
  frictionless and the fully-costed setting so the cost erosion per factor is visible.
  Rank on the costed column; see `factorlib/README.md`.

- **`tutorials/`** — 量化课堂 (JoinQuant's quant classroom), 137 lessons across
  新手专区 / Python编程 / 策略与应用 / 数学课堂 / 经济与市场, ingested by
  `node utils/tutorial-ingest.js`. The 新手专区 因子专题 series is a complete
  factor-research methodology chain (data acquisition, winsorizing, standardizing,
  neutralizing, then return / information / turnover analysis) and several
  策略与应用 lessons map onto families already in `wiki/families/`.
