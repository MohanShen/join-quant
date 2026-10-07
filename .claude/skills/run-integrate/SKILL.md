---
name: run-integrate
description: Run one UNIVERSE-level round — compose two families' EDGES into a single strategy that beats both, or promote the universe's best family when nothing is composable. Use when asked to integrate or combine strategy families, work at the type/universe level, or deliver a champion per universe.
---

# Run one universe round

The layer above `/run-family`. That loop works **one lineage**; this asks whether two lineages in
the same universe can be **composed into one strategy whose edge is the conjunction of theirs** —
and, when they cannot, ships the universe's best family anyway so the round always delivers.

**Authority**: `docs/proposals/type-integration-by-edge.md` (accepted 2026-10-07),
`harness/harness.md` (frozen bench, read-only), `screen/screen.md` §3 R (realizability).
This skill is the entry point and does not restate them.

## Composition, not blending — the distinction this round turns on

A **blend** allocates capital across finished books. Its return cannot exceed the weighted average
of its legs; only its risk improves. This repo measured the trap twice: 七星高照's blend scored
sharpe **3.17** from legs of 2.85/1.60 — and still lost to its own small-cap leg (0.4814 vs
0.5984). Blending raises sharpe mechanically whenever correlation < 1, and the gate **is** a sharpe
threshold, so an unguarded round manufactures passes that contain nothing.

A **conjunction** can be superadditive, and that was measured too: 红利低频's two-factor
conjunction returned **23.41% against 11.75% for the sum of its legs, at lower risk than either**.

So: take the *mechanism* from each family and build ONE strategy. Do not weight two books.

## Start here

```bash
node utils/integrate-queue.js           # every universe and what it should do
node utils/integrate-queue.js --next    # the single highest-value action
```

It returns one of three actions per universe:

| action | meaning |
|---|---|
| `compose` | admissible pairs exist — run the loop below |
| `promote` | nothing composable; ship the best family (§Promote) |
| `blocked` | nothing composable AND the best family has a negative objective — report it |

## COMPOSE

### 1. Gate the pair — the step the program cannot do

`integrate-queue.js` already removed pairs whose edges are **provably** the same by name
(`规模` ⊂ `规模因子` — one edge spelled two ways). That is a floor, not the rule.

**You must make the semantic call and record it:**

- Are these genuinely different mechanisms, or the same idea under two names? Two
  differently-named edges can still be one mechanism, and only a reader can tell.
- **Can they coexist?** Two cross-sectional screens on the same rebalance compose (a size floor and
  a dividend screen both narrow one list). A 1.5-day limit-up book and an ETF discount
  mean-reversion do not obviously compose — different horizons, different fills, possibly
  contradictory signals. If you believe they do, say why.

Refusing a pair here is a legitimate outcome. Record the reason either way.

### 2. Compose

State, before building: **which mechanism comes from which family**, and what the conjunction is
expected to do that neither leg does alone. Ground it in both families' `edge:` blocks and their
§6 findings — a composition proposed without reading them will re-run settled work.

### 3. Build and measure

One strategy file under `enhance/candidates/<expId>.py`, using the frozen cost block, run on the
frozen bench:

```bash
node utils/strategy-post-backtest.js enhance/candidates/<expId>.py "<expId>" --window train --usage-limit free
```

⚠ The executor does **not** apply the harness to a raw `strategies/*.py` — the pins live in
`enhance/strategy_template.py` for generated candidates. Build from that template; a source with no
pins is refused with `UNPINNED-STOP`.

### 4. Judge

```bash
node utils/type-integrate-check.js <candidate.json>
```

Four rules, unchanged, which are the **floor** and not the whole test:

1. **beat the best MEMBER**, not the gate (integration's threshold is 2.0, not 1.5)
2. **declare the diversification share** — attribution from stored curves; if stripping
   diversification drops sharpe below the best member, the verdict is `keep-with-caveat`.
   ⚠ This matters MORE under composition: a conjunction that also happens to diversify will look
   brilliant for the wrong reason, and the round must say which it got.
3. optimised weights must beat equal weight by more than 1pp (the ~0.15pp re-run noise floor)
4. **realizability is inherited at its WORST leg** — capacity is additive, edge is not

### 5. Acceptance, and the VAL rule

**The composite must beat or equal the best input family** — on TRAIN, and then on VAL.

- **Iterate on TRAIN only.** Selection happens here and may be re-run freely.
- **ONE VAL per (universe, epoch)**, enforced by `utils/val-budget.js` with `kind: 'type'`:

```bash
node utils/val-budget.js <universe>        # check before building the finalist
```

- **A VAL failure is TERMINAL for that universe this epoch.** It does **not** license a different
  conjunction. "The last VAL disappointed, so compose another" is selection on VAL one run at a
  time, and once that happens the only clean surface left is the 2026 OOS reserve (~9 months, 2
  tests). Report it and stop.
- Never set `JQ_ALLOW_REVAL` or `JQ_ALLOW_OOS` — those are the human's switches.

### 6. Record

```bash
node -e "require('./utils/consumption').record({key:'<universe>',kind:'type',stage:'integrate',runId:'<expId>',outcome:'<verdict>',note:'…'})"
```

Then append the round to `wiki/types/<universe>.md`'s 整合回合 section. The builder carries that
section across verbatim, so it is safe to write there.

## PROMOTE

When no pair is admissible, the universe still delivers: **ship its best family's champion.**

- No backtest is spent. The champion already cleared its own loop and its own family VAL.
- Record it: `stage: 'integrate'`, `outcome: 'promoted'`, with a note naming the family and why
  nothing was composable (all edges refuted, duplicated, or only one measured).
- ⚠ If the queue reports `⚠ never validated`, say so in the note — an unvalidated champion is a
  caveat the reader must see.
- A `blocked` universe is reported, not promoted: a negative objective means the drawdown exceeded
  the return, and shipping the least-bad loser is not delivering.

## Do not

- Weight two finished books and call it integration.
- Treat a gate pass as success — see the failure mode above.
- Compose edges that are `proposed` (unevidenced) or `refuted` (known false).
- Average realizability across legs.
- Touch VAL during selection, or OOS at all.
- Write a composition result into a family page — it belongs to the type.
