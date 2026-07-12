# validated_strategies/

Finalized strategies that completed the autoresearch pipeline through **VALIDATION**.

Populated by **Agent 4 (recorder)** of the autoresearch team (`research/program.md`): whenever
a strategy is *finalized* by Agent 1 and Agent 3 produces a **VAL (2024) result**, the recorder
copies that candidate here as `<expId>.py` with a header recording its identity and metrics.

- One file per finalized-and-validated strategy: `validated_strategies/<expId>.py`.
- Header comment carries: `expId`, `ideaId`, `baseExpId`, `train_objective`, `val_objective`,
  `sharpe_val`, `gate_val` (pass/fail), and `ranAt`. The gate field makes pass/fail explicit —
  this directory collects everything that *reached validation*, not only gate-passers.
- The full write-up (hypothesis, reasoning, iteration trajectory) lives in `wiki/experiments/<expId>.md`;
  this directory is the runnable-strategy counterpart, tracked in git as a durable output.
- Source of truth for the strategy body is `research/candidates/<expId>.py`; this is the archived copy.

> This directory is **tracked** (unlike the transient `research/results.tsv` / `ideas-queue.json` /
> `loop-state.json`). It is the pipeline's product shelf.
