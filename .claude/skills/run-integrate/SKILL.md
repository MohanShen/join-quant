---
name: run-integrate
description: Run one UNIVERSE-level round — an agent merges two families in the same universe into one strategy that beats both, or the universe promotes its best family when there is nothing to merge. Use when asked to integrate or combine strategy families, work at the type/universe level, or deliver a champion per universe.
---

# Run one universe round

The layer above `/run-family`. That loop works **one lineage**; this takes two lineages in the same
universe and **merges them into one strategy** — built from the best measured variant of each
pipeline step — and, when a universe has nothing to merge, ships its best family anyway so the
round always delivers.

**Authority**: `docs/proposals/type-integration-by-edge.md` (accepted 2026-10-07),
`harness/harness.md` (frozen bench, read-only), `screen/screen.md` §3 R (realizability).
This skill is the entry point and does not restate them.

## One strategy, not two books — the distinction this round turns on

A **blend** allocates capital across finished books. Its return cannot exceed the weighted average
of its legs; only its risk improves. This repo measured the trap twice: 七星高照's blend scored
sharpe **3.17** from legs of 2.85/1.60 — and still lost to its own small-cap leg (0.4814 vs
0.5984). Blending raises sharpe mechanically whenever correlation < 1, and the gate **is** a sharpe
threshold, so an unguarded round manufactures passes that contain nothing.

Building ONE strategy avoids that entirely, and avoids something else too: a merged strategy
declares **one universe**, so the question "do these two trade the same names?" never has to be
answered after the fact — which is fortunate, because JoinQuant exposes no holdings to answer it
with (§Why the agent).

⚠ **Revision 2 (2026-10-11)**: a round used to build a *conjunction of two edges* and refused a
pair whose edges matched. It now MERGES, and a shared edge is no longer a refusal — two families
earning the same way are exactly the ones whose entry, exit and risk steps are worth comparing.
See `docs/proposals/type-integration-by-edge.md` §5.

## Start here

```bash
node utils/integrate-queue.js           # every universe and what it should do
node utils/integrate-queue.js --next    # the single highest-value action
```

It returns one of three actions per universe:

| action | meaning |
|---|---|
| `merge` | two or more families with a measured edge — dispatch the agent (below) |
| `promote` | nothing to merge; ship the best family (§Promote) |
| `blocked` | nothing to merge AND the best family has a negative objective — report it |

## MERGE — dispatch the agent, do not do it inline

**The agent drives this step.** Dispatch `integrate-merger` (`Agent` tool,
`subagent_type: "integrate-merger"`) with the universe and its pairs. Its contract is
`.claude/agents/integrate-merger.md`; what follows is only what you, the orchestrator, need to
know to hand off and to check what comes back.

The division is deliberate:

| | |
|---|---|
| **deterministic** | which universes exist, who is in them, the promote and realizability floors, the VAL budget, the four judge rules, the per-year BAR |
| **the agent** | symbol overlap, what kind of merge the edges call for, the decomposition, the candidate set, the build |

### Why the agent and not a program

Two questions in this step have no programmatic answer, and both have been measured wrong:

- **Symbol overlap.** A shared `universe:` does not mean the two families touch the same
  instruments — PT多策略 screens to ETFs with turnover in 5e6–2e7 while 七星高照 holds 七 named
  liquid ones, an empty intersection. And it cannot be looked up: JoinQuant exposes **no
  holdings** (`trade`, `order(s)`, `position(s)`, `holding(s)` all empty; `result.orders` is a
  chart-marker count with no instrument identity). The agent reads the **selection logic** and
  judges.
- **Edge identity.** An edge name is free text. `规模` and `规模因子` are one mechanism in two
  spellings; `动量` in 七星高照 and in 趋势技术 are two mechanisms under one word. `integrate-queue`
  reports `shared` and `sameSet` as *evidence* and refuses nothing on that basis.

### What the agent must come back with

1. **An overlap judgement with its reasoning.** The bar is low on purpose: overlap, or the
   plausible possibility of large overlap, is enough to proceed. Only a provably disjoint pair
   stops, and a stop is recorded with
   `node utils/integrate-queue.js --refuse <universe> <A> <B> --why "…"`.
2. **What kind of merge this is.** Identical edge sets → the merge seeks the **better
   implementation** of one edge. Different sets → it seeks to **combine** them. Both merge; the
   answer defines what "better" means at the judge.
3. **A decomposition** of both families onto the pipeline skeleton (universe · selection · entry ·
   exit · risk overlay · sizing), each step citing the §2 row that measures it.
4. **At most 3 candidates, declared before any is run.** A sweep is not a candidate set.
5. **One built strategy per candidate**, from `enhance/strategy_template.py` so it carries the
   pins, measured on `--window train`. Never a result assembled from summed deltas.

### What you check when it returns

- the overlap judgement is **recorded**, whichever way it went;
- the candidate set was declared **before** the first run, and is ≤3;
- each candidate was **measured as one strategy**;
- `type-integrate-check.js` was run, and rule 4 (realizability at the worst leg) is reflected in
  the verdict — if either parent declares its headline `不可实现`, the result is a TRAIN comparison
  and not a tradeable claim;
- the bar it applied was **`worstTrainYear`**, not `pooled-fallback`. A fallback means a curve was
  missing and the guard judged on the pooled objective instead; it says so in `flags`, and the fix
  is to supply the `sourceFile` on the candidate and on every member, not to accept the verdict;
- when the guard flagged `pooled-objective-lower`, the round **says which it was after** —
  consistency or level (§The bar, below);
- the round is recorded as a consumption event **and** under `## 整合回合` on the type page,
  including negative results.

⚠ **VAL is yours to protect, not the agent's.** One validation per (universe, epoch); a failure is
**terminal for that universe this epoch** and does not license a fourth candidate. If the agent
asks for another VAL, refuse it and report.

## The bar — what "beat both" means since epoch 7

The sharpe gate is **1.5 at every stage**; integration no longer holds a different one. Its real
bar is **per-year sharpe domination** (epoch 8): in **every** TRAIN calendar year the candidate's
sharpe must exceed the best **parent champion's** sharpe in that **same** year.
`harness/harness.md` §4.1 is frozen authority.

⚠ Epoch 7's worst-year objective maximin is **invalidated**. An epoch-7 round still states an
epoch-7 conclusion, but it is not an epoch-8 one without re-judging.

⚠ The bar can be a **composite**: the best parent may differ by year, so the candidate faces
something no single parent achieves. Deliberate, and strictly harder. And the bar needs curves for
the candidate and every parent — 4 of 11 champions have none, so those rounds fall back to the
pooled rule and say so.

This is not a relaxation — applied to the two rounds already run it **confirms both rejections**
and sharpens them: all three 全A candidates turn out to have a **negative** worst year
(−0.0464 / −0.1014 / −0.4437), which is the measured form of what that round could only say in
prose, 「combining relocates WHICH YEAR earns; it does not add」.

What it fixes: the pooled objective is almost purely annual return (r = **0.9698**), and annual
return over TRAIN is substantially a 2022 measurement (2022 supplies a median **62%** of
log-growth across the stored curves). So a merge whose payoff is **robustness** — two
implementations of one edge, the 小盘 case — had no channel to register, and a candidate trading
the 2022 tail for 2023 steadiness lost by construction.

The pooled comparison is still printed as **evidence** and never vetoes.

## PROMOTE

When no pair survives, the universe still delivers: **ship its best family's champion.**

- No backtest is spent. The champion already cleared its own loop and its own family VAL.
- Record it: `stage: 'integrate'`, `outcome: 'promoted'`, with a note naming the family and why
  nothing was mergeable (only one family carries a measured edge, or the pair was refused).
- ⚠ If the queue reports `⚠ never validated`, say so in the note — an unvalidated champion is a
  caveat the reader must see.
- A `blocked` universe is reported, not promoted: a negative objective means the drawdown exceeded
  the return, and shipping the least-bad loser is not delivering.

## Do not

- Weight two finished books and call it integration.
- Treat a gate pass as success — see the failure mode above.
- Build on edges that are `proposed`, `refuted`, or carry `supersededBy:`.
- Refuse a pair because its edges are identical — that is what makes a merge coherent.
- Average realizability across legs.
- Touch VAL during selection, or OOS at all.
- Write a merge result into a family page — it belongs to the type.
